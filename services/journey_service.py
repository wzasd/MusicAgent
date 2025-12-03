"""
音乐旅程编排服务
根据故事情节、情绪曲线或场景变化生成连贯的音乐旅程
"""

from __future__ import annotations

import json
import math
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from config.logging_config import get_logger
import re

try:
    from llms.siliconflow_llm import SiliconFlowLLM
except Exception as llm_import_error:  # noqa: BLE001
    SiliconFlowLLM = None  # type: ignore[assignment]
    llm_fallback_warning = str(llm_import_error)
else:
    llm_fallback_warning = ""
from prompts.music_prompts import (
    MUSIC_JOURNEY_ANALYZER_PROMPT,
    MUSIC_JOURNEY_GENERATOR_PROMPT,
    MUSIC_TRANSITION_OPTIMIZER_PROMPT,
)
from schemas.music_state import UserPreferences
from tools.mcp_adapter import MCPClientAdapter
from tools.music_tools import Song, get_music_search_tool

logger = get_logger(__name__)


class BasicJourneyLLM:
    """本地兜底LLM，避免依赖外部大模型。"""

    default_moods = ["放松", "专注", "活力", "平静", "浪漫", "疗愈"]

    async def ainvoke(self, prompt: str) -> str:
        """模拟LLM返回JSON，基于简单规则分段。"""
        story = self._extract_story(prompt) or "旅程开始→旅程进行→旅程结束"
        duration = self._extract_duration(prompt)
        segments = self._build_segments(story, duration)
        return json.dumps({"segments": segments}, ensure_ascii=False)

    def _extract_story(self, prompt: str) -> str:
        match = re.search(r"用户故事：(.+?)\n", prompt)
        return match.group(1).strip() if match else ""

    def _extract_duration(self, prompt: str) -> int:
        match = re.search(r"总时长：(\d+)", prompt)
        return int(match.group(1)) if match else 60

    def _build_segments(self, story: str, total_duration: int) -> List[Dict[str, Any]]:
        parts = re.split(r"[→->]+", story)
        stages = [p.strip() for p in parts if p.strip()]
        if not stages:
            stages = ["开启", "发展", "高潮", "收束"]

        duration_per_stage = max(total_duration / max(len(stages), 1), 10)
        segments = []
        current_time = 0.0

        for idx, stage in enumerate(stages):
            mood = self.default_moods[idx % len(self.default_moods)]
            segments.append(
                {
                    "segment_id": idx,
                    "mood": mood,
                    "description": stage,
                    "duration": duration_per_stage,
                    "intensity": 0.5 + 0.1 * (idx % 3),
                    "start_time": current_time,
                }
            )
            current_time += duration_per_stage

        # 调整最后一个片段，确保总时长接近目标
        actual_total = sum(seg["duration"] for seg in segments)
        if actual_total > 0 and total_duration > 0:
            ratio = total_duration / actual_total
            current_start = 0.0
            for seg in segments:
                seg["duration"] *= ratio
                seg["start_time"] = current_start
                current_start += seg["duration"]

        return segments


class MoodPoint:
    """情绪点"""
    def __init__(self, time: float, mood: str, intensity: float = 0.5):
        """
        Args:
            time: 时间点（0-1，相对位置）
            mood: 情绪类型（如：开心、放松、兴奋等）
            intensity: 情绪强度（0-1）
        """
        self.time = time
        self.mood = mood
        self.intensity = intensity
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "time": self.time,
            "mood": self.mood,
            "intensity": self.intensity
        }


class JourneySegment:
    """旅程片段"""
    def __init__(
        self,
        segment_id: int,
        start_time: float,
        duration: float,
        mood: str,
        description: str,
        songs: List[Song],
        transition_from: Optional[int] = None
    ):
        """
        Args:
            segment_id: 片段ID
            start_time: 开始时间（分钟）
            duration: 持续时间（分钟）
            mood: 情绪类型
            description: 片段描述
            songs: 该片段的歌曲列表
            transition_from: 从哪个片段过渡而来
        """
        self.segment_id = segment_id
        self.start_time = start_time
        self.duration = duration
        self.mood = mood
        self.description = description
        self.songs = songs
        self.transition_from = transition_from
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "segment_id": self.segment_id,
            "start_time": self.start_time,
            "duration": self.duration,
            "mood": self.mood,
            "description": self.description,
            "songs": [song.to_dict() for song in self.songs],
            "transition_from": self.transition_from,
            "total_songs": len(self.songs)
        }


class MusicJourneyService:
    """音乐旅程编排服务"""
    
    def __init__(
        self,
        mcp_adapter: Optional[MCPClientAdapter] = None,
        llm: Optional[SiliconFlowLLM] = None
    ):
        """
        初始化旅程服务
        
        Args:
            mcp_adapter: MCP客户端适配器
            llm: LLM实例
        """
        self.mcp_adapter = mcp_adapter or MCPClientAdapter()
        if llm is not None:
            self.llm = llm
        elif SiliconFlowLLM is not None:
            self.llm = SiliconFlowLLM()
        else:
            self.llm = BasicJourneyLLM()
            if llm_fallback_warning:
                logger.warning(
                    "SiliconFlowLLM 加载失败，将使用内置规则引擎。原因: %s",
                    llm_fallback_warning,
                )
        self._search_tool = None
        logger.info("MusicJourneyService 初始化完成")
    
    def _get_search_tool(self):
        """获取搜索工具"""
        if self._search_tool is None:
            self._search_tool = get_music_search_tool()
        return self._search_tool
    
    async def generate_journey(
        self,
        story: Optional[str] = None,
        mood_transitions: Optional[List[MoodPoint]] = None,
        duration: int = 60,
        user_preferences: Optional[UserPreferences] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        生成音乐旅程
        
        Args:
            story: 故事情节描述（如："早晨起床→通勤路上→工作中→下班放松→夜晚休息"）
            mood_transitions: 情绪曲线点列表
            duration: 总时长（分钟）
            user_preferences: 用户偏好
            context: 额外上下文（天气、地点、时间等）
            
        Returns:
            包含旅程片段的字典
        """
        try:
            logger.info(
                f"开始生成音乐旅程: story={story}, duration={duration}分钟"
            )
            
            # 1. 分析故事情节和情绪变化点
            if story:
                segments_plan = await self._analyze_story(story, duration)
            elif mood_transitions:
                segments_plan = await self._analyze_mood_curve(mood_transitions, duration)
            else:
                raise ValueError("必须提供 story 或 mood_transitions 之一")
            
            # 2. 为每个阶段生成匹配的音乐
            segments = []
            for i, plan in enumerate(segments_plan):
                logger.info(f"生成片段 {i+1}/{len(segments_plan)}: {plan['mood']}")
                
                songs = await self._generate_segment_songs(
                    mood=plan["mood"],
                    description=plan["description"],
                    duration=plan["duration"],
                    user_preferences=user_preferences,
                    context=context
                )
                
                segment = JourneySegment(
                    segment_id=i,
                    start_time=plan["start_time"],
                    duration=plan["duration"],
                    mood=plan["mood"],
                    description=plan["description"],
                    songs=songs,
                    transition_from=i-1 if i > 0 else None
                )
                segments.append(segment)
            
            # 3. 优化过渡关系，确保音乐风格平滑过渡
            optimized_segments = await self._optimize_transitions(segments)
            
            # 4. 计算总时长和统计信息
            total_duration = sum(seg.duration for seg in optimized_segments)
            total_songs = sum(len(seg.songs) for seg in optimized_segments)
            
            journey_result = {
                "success": True,
                "segments": [seg.to_dict() for seg in optimized_segments],
                "total_duration": total_duration,
                "total_songs": total_songs,
                "mood_progression": [seg.mood for seg in optimized_segments],
                "created_at": datetime.now().isoformat()
            }
            
            logger.info(
                f"音乐旅程生成完成: {len(optimized_segments)}个片段, "
                f"{total_songs}首歌曲, 总时长{total_duration}分钟"
            )
            
            return journey_result
            
        except Exception as e:
            logger.error(f"生成音乐旅程失败: {str(e)}", exc_info=True)
            return {
                "success": False,
                "error": str(e),
                "segments": [],
                "total_duration": 0,
                "total_songs": 0
            }
    
    async def _analyze_story(
        self,
        story: str,
        total_duration: int
    ) -> List[Dict[str, Any]]:
        """
        分析故事情节，提取阶段和情绪变化
        
        Args:
            story: 故事描述
            total_duration: 总时长（分钟）
            
        Returns:
            片段计划列表
        """
        try:
            prompt = MUSIC_JOURNEY_ANALYZER_PROMPT.format(
                story=story,
                total_duration=total_duration
            )
            
            response = await self.llm.ainvoke(prompt)
            
            # 解析LLM返回的JSON
            try:
                # 尝试提取JSON部分
                if "```json" in response:
                    json_start = response.find("```json") + 7
                    json_end = response.find("```", json_start)
                    response = response[json_start:json_end].strip()
                elif "```" in response:
                    json_start = response.find("```") + 3
                    json_end = response.find("```", json_start)
                    response = response[json_start:json_end].strip()
                
                plan_data = json.loads(response)
                segments = plan_data.get("segments", [])
                
                # 验证和规范化数据
                normalized_segments = []
                current_time = 0.0
                
                for i, seg in enumerate(segments):
                    duration = float(seg.get("duration", total_duration / len(segments)))
                    normalized_segments.append({
                        "segment_id": i,
                        "start_time": current_time,
                        "duration": duration,
                        "mood": seg.get("mood", "中性"),
                        "description": seg.get("description", ""),
                        "intensity": float(seg.get("intensity", 0.5))
                    })
                    current_time += duration
                
                # 如果总时长不匹配，按比例调整
                actual_total = sum(s["duration"] for s in normalized_segments)
                if actual_total > 0:
                    ratio = total_duration / actual_total
                    for seg in normalized_segments:
                        seg["duration"] *= ratio
                        seg["start_time"] = sum(
                            s["duration"] for s in normalized_segments
                            if normalized_segments.index(s) < normalized_segments.index(seg)
                        )
                
                return normalized_segments
                
            except json.JSONDecodeError as e:
                logger.warning(f"LLM返回的JSON解析失败: {e}，使用默认分段")
                return self._default_segments(story, total_duration)
                
        except Exception as e:
            logger.error(f"分析故事情节失败: {str(e)}")
            return self._default_segments(story, total_duration)
    
    async def _analyze_mood_curve(
        self,
        mood_points: List[MoodPoint],
        total_duration: int
    ) -> List[Dict[str, Any]]:
        """
        分析情绪曲线，生成分段计划
        
        Args:
            mood_points: 情绪点列表（按时间排序）
            total_duration: 总时长（分钟）
            
        Returns:
            片段计划列表
        """
        if not mood_points:
            return self._default_segments("", total_duration)
        
        # 确保情绪点按时间排序
        sorted_points = sorted(mood_points, key=lambda p: p.time)
        
        segments = []
        for i in range(len(sorted_points)):
            start_point = sorted_points[i]
            end_point = sorted_points[i + 1] if i + 1 < len(sorted_points) else MoodPoint(1.0, start_point.mood, start_point.intensity)
            
            start_time = start_point.time * total_duration
            end_time = end_point.time * total_duration
            duration = end_time - start_time
            
            # 使用插值计算中间情绪
            avg_mood = start_point.mood  # 简化：使用起始情绪
            avg_intensity = (start_point.intensity + end_point.intensity) / 2
            
            segments.append({
                "segment_id": i,
                "start_time": start_time,
                "duration": duration,
                "mood": avg_mood,
                "description": f"从{start_point.mood}过渡到{end_point.mood}",
                "intensity": avg_intensity
            })
        
        return segments
    
    def _default_segments(
        self,
        story: str,
        total_duration: int
    ) -> List[Dict[str, Any]]:
        """生成默认分段（后备方案）"""
        # 简单分段：根据故事中的关键词或默认分段
        default_moods = ["放松", "专注", "活力", "平静"]
        num_segments = min(4, max(2, total_duration // 15))
        
        segments = []
        segment_duration = total_duration / num_segments
        
        for i in range(num_segments):
            mood = default_moods[i % len(default_moods)]
            segments.append({
                "segment_id": i,
                "start_time": i * segment_duration,
                "duration": segment_duration,
                "mood": mood,
                "description": f"{mood}阶段",
                "intensity": 0.5
            })
        
        return segments
    
    async def _generate_segment_songs(
        self,
        mood: str,
        description: str,
        duration: float,
        user_preferences: Optional[UserPreferences] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> List[Song]:
        """
        为单个片段生成匹配的歌曲
        
        Args:
            mood: 情绪类型
            description: 片段描述
            duration: 片段时长（分钟）
            user_preferences: 用户偏好
            context: 上下文
            
        Returns:
            歌曲列表
        """
        try:
            # 估算需要的歌曲数量（假设平均每首3-4分钟）
            target_songs = max(1, int(duration / 3.5))
            
            # 使用MCP适配器获取推荐
            # 根据情绪映射到Spotify流派
            mood_to_genres = {
                "开心": ["pop", "dance", "electronic"],
                "快乐": ["pop", "dance", "electronic"],
                "放松": ["chill", "acoustic", "jazz", "ambient"],
                "专注": ["lo-fi", "ambient", "acoustic"],
                "活力": ["rock", "electronic", "dance"],
                "兴奋": ["rock", "electronic", "dance"],
                "平静": ["ambient", "acoustic", "chill"],
                "悲伤": ["acoustic", "sad", "indie", "mellow"],
                "浪漫": ["acoustic", "pop", "r-n-b", "soul"],
            }
            
            genres = mood_to_genres.get(mood, ["pop"])
            
            # 获取推荐歌曲
            songs = await self.mcp_adapter.get_recommendations(
                seed_genres=genres[:3],
                limit=target_songs * 2  # 获取更多候选，后续可以筛选
            )
            
            # 如果MCP返回为空，使用本地搜索工具
            if not songs:
                search_tool = self._get_search_tool()
                # 尝试根据情绪搜索
                query = f"{mood} {description}"
                songs = await search_tool.search_songs(query, limit=target_songs)
            
            # 限制歌曲数量
            return songs[:target_songs]
            
        except Exception as e:
            logger.error(f"生成片段歌曲失败: {str(e)}")
            return []
    
    async def _optimize_transitions(
        self,
        segments: List[JourneySegment]
    ) -> List[JourneySegment]:
        """
        优化片段之间的过渡，确保音乐风格平滑过渡
        
        Args:
            segments: 原始片段列表
            
        Returns:
            优化后的片段列表
        """
        if len(segments) <= 1:
            return segments
        
        try:
            # 使用LLM分析过渡关系
            transitions_info = []
            for i in range(len(segments) - 1):
                from_seg = segments[i]
                to_seg = segments[i + 1]
                
                transitions_info.append({
                    "from": {
                        "mood": from_seg.mood,
                        "last_song": from_seg.songs[-1].to_dict() if from_seg.songs else None
                    },
                    "to": {
                        "mood": to_seg.mood,
                        "first_song": to_seg.songs[0].to_dict() if to_seg.songs else None
                    }
                })
            
            # 如果有明显的风格跳跃，尝试调整
            optimized = segments.copy()
            
            for i in range(len(optimized) - 1):
                from_seg = optimized[i]
                to_seg = optimized[i + 1]
                
                # 如果两个片段的情绪差异很大，尝试在过渡点添加过渡歌曲
                if from_seg.songs and to_seg.songs:
                    # 简单的过渡优化：如果最后和第一首歌风格差异大，可以交换或调整
                    # 这里简化处理，实际可以使用更复杂的相似度算法
                    pass
            
            return optimized
            
        except Exception as e:
            logger.warning(f"优化过渡失败: {str(e)}，返回原始片段")
            return segments
    
    def interpolate_mood(
        self,
        point1: MoodPoint,
        point2: MoodPoint,
        t: float
    ) -> MoodPoint:
        """
        在两个情绪点之间插值
        
        Args:
            point1: 起始情绪点
            point2: 结束情绪点
            t: 插值参数（0-1）
            
        Returns:
            插值后的情绪点
        """
        # 如果情绪相同，直接返回
        if point1.mood == point2.mood:
            intensity = point1.intensity + (point2.intensity - point1.intensity) * t
            time = point1.time + (point2.time - point1.time) * t
            return MoodPoint(time, point1.mood, intensity)
        
        # 如果情绪不同，使用强度插值，情绪在中间点切换
        if t < 0.5:
            intensity = point1.intensity + (point2.intensity - point1.intensity) * (t * 2)
            mood = point1.mood
        else:
            intensity = point1.intensity + (point2.intensity - point1.intensity) * ((t - 0.5) * 2)
            mood = point2.mood
        
        time = point1.time + (point2.time - point1.time) * t
        return MoodPoint(time, mood, intensity)
    
    def calculate_song_similarity(
        self,
        song1: Song,
        song2: Song
    ) -> float:
        """
        计算两首歌曲的相似度（0-1）
        
        Args:
            song1: 第一首歌
            song2: 第二首歌
            
        Returns:
            相似度分数（0-1）
        """
        score = 0.0
        factors = 0
        
        # 1. 流派相似度（权重：0.4）
        if song1.genre and song2.genre:
            if song1.genre.lower() == song2.genre.lower():
                score += 0.4
            # 可以扩展：流派相似度映射（如：pop和dance相似）
            factors += 0.4
        elif not song1.genre and not song2.genre:
            score += 0.2  # 都没有流派信息，给一个基础分
            factors += 0.4
        
        # 2. 艺术家相似度（权重：0.3）
        if song1.artist and song2.artist:
            if song1.artist.lower() == song2.artist.lower():
                score += 0.3
            # 可以扩展：艺术家相似度（需要额外数据）
            factors += 0.3
        
        # 3. 年代相似度（权重：0.2）
        if song1.year and song2.year:
            year_diff = abs(song1.year - song2.year)
            # 10年内相似度较高
            if year_diff <= 5:
                score += 0.2
            elif year_diff <= 10:
                score += 0.1
            factors += 0.2
        
        # 4. 流行度相似度（权重：0.1）
        if song1.popularity is not None and song2.popularity is not None:
            pop_diff = abs(song1.popularity - song2.popularity)
            # 流行度差异越小，相似度越高
            if pop_diff <= 10:
                score += 0.1
            elif pop_diff <= 20:
                score += 0.05
            factors += 0.1
        
        # 归一化
        if factors > 0:
            return score / factors
        return 0.5  # 默认相似度
    
    def find_transition_path(
        self,
        from_songs: List[Song],
        to_songs: List[Song],
        max_transition_songs: int = 2
    ) -> List[Song]:
        """
        寻找从一组歌曲到另一组歌曲的最佳过渡路径
        
        Args:
            from_songs: 起始歌曲列表
            to_songs: 目标歌曲列表
            max_transition_songs: 最大过渡歌曲数量
            
        Returns:
            过渡歌曲列表
        """
        if not from_songs or not to_songs:
            return []
        
        # 找到最相似的起始和结束歌曲对
        best_pair = None
        best_similarity = 0.0
        
        for from_song in from_songs:
            for to_song in to_songs:
                sim1 = self.calculate_song_similarity(from_song, to_song)
                if sim1 > best_similarity:
                    best_similarity = sim1
                    best_pair = (from_song, to_song)
        
        # 如果相似度已经很高（>0.7），不需要过渡歌曲
        if best_similarity > 0.7:
            return []
        
        # 简化：返回空列表，实际可以使用更复杂的图算法
        # 这里可以调用MCP获取相似歌曲作为过渡
        return []


# 导出
__all__ = ["MusicJourneyService", "MoodPoint", "JourneySegment"]

