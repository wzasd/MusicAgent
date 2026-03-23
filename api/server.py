"""
FastAPI后端服务器
支持SSE流式输出音乐推荐
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path
from typing import AsyncGenerator, Dict, Any, Optional, List

# 添加项目根目录到Python路径（如果还没有）
project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

# 在导入其他模块之前加载配置
try:
    from config.settings_loader import load_and_setup_settings
    load_and_setup_settings()
except Exception as e:
    print(f"警告: 无法从 setting.json 加载配置: {e}")

from config.logging_config import get_logger
from music_agent import MusicRecommendationAgent
from utils.performance_monitor import PerformanceContext, get_current_timer
from services import PlaylistRecommendationService
from services.journey_service import MusicJourneyService, MoodPoint
from tools.music_tools import get_music_search_tool
from graphs.music_graph import get_agent_status_tracker, _clean_search_query
from llms.siliconflow_llm import get_chat_model
from prompts.music_prompts import MUSIC_INTENT_ANALYZER_PROMPT

logger = get_logger(__name__)

app = FastAPI(title="Music Recommendation API", version="1.0.0")

# 配置CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 全局Agent实例
_agent: Optional[MusicRecommendationAgent] = None
_playlist_service: Optional[PlaylistRecommendationService] = None
_journey_service: Optional[MusicJourneyService] = None

# 搜索日志存储（内存中，最近50条）
_search_logs: List[Dict[str, Any]] = []
_MAX_LOGS = 50


def add_search_log(log_entry: Dict[str, Any]):
    """添加搜索日志"""
    global _search_logs
    from datetime import datetime
    log_entry["timestamp"] = datetime.now().isoformat()
    _search_logs.insert(0, log_entry)  # 新日志放前面
    if len(_search_logs) > _MAX_LOGS:
        _search_logs = _search_logs[:_MAX_LOGS]


def get_search_logs(limit: int = 20) -> List[Dict[str, Any]]:
    """获取最近搜索日志"""
    return _search_logs[:limit]


def get_agent() -> MusicRecommendationAgent:
    """获取Agent实例（单例模式）"""
    global _agent
    if _agent is None:
        _agent = MusicRecommendationAgent()
    return _agent


def get_playlist_service() -> PlaylistRecommendationService:
    """获取歌单服务实例（单例模式）"""
    global _playlist_service
    if _playlist_service is None:
        _playlist_service = PlaylistRecommendationService()
    return _playlist_service


def get_journey_service() -> MusicJourneyService:
    """获取旅程服务实例（单例模式）"""
    global _journey_service
    if _journey_service is None:
        _journey_service = MusicJourneyService()
    return _journey_service


# 请求模型
class RecommendationRequest(BaseModel):
    query: str
    genre: Optional[str] = None
    mood: Optional[str] = None
    user_preferences: Optional[Dict[str, Any]] = None


class PlaylistRequest(BaseModel):
    query: str
    target_size: int = 30
    create_spotify_playlist: bool = False
    public: bool = False
    user_preferences: Optional[Dict[str, Any]] = None


class JourneyRequest(BaseModel):
    story: Optional[str] = None
    mood_transitions: Optional[List[Dict[str, Any]]] = None  # [{time, mood, intensity}]
    duration: int = 60  # 总时长（分钟）
    user_preferences: Optional[Dict[str, Any]] = None
    context: Optional[Dict[str, Any]] = None  # 天气、地点、时间等


class SearchRequest(BaseModel):
    """歌曲搜索请求"""
    query: str
    genre: Optional[str] = None
    limit: int = 20


async def stream_recommendations(
    query: str,
    genre: Optional[str] = None,
    mood: Optional[str] = None,
    user_preferences: Optional[Dict[str, Any]] = None
) -> AsyncGenerator[str, None]:
    """
    流式生成推荐结果 - 增强版，带完整性能监控和Agent状态跟踪

    Yields:
        SSE格式的数据块
    """
    import time

    # 使用性能监控上下文
    async with PerformanceContext() as timer:
        start_time = time.time()
        first_token_time = None
        inference_start_time = None

        # 获取Agent状态跟踪器
        status_tracker = get_agent_status_tracker()
        status_tracker.start_request()

        try:
            agent = get_agent()

            # 发送开始事件
            yield f"data: {json.dumps({'type': 'start', 'message': '开始分析你的需求...', 'trace_id': id(timer)}, ensure_ascii=False)}\n\n"
            await asyncio.sleep(0.1)

            # 发送初始Agent状态
            yield f"data: {json.dumps({'type': 'agent_status', 'status': status_tracker.get_status()}, ensure_ascii=False)}\n\n"

            # 发送思考事件
            yield f"data: {json.dumps({'type': 'thinking', 'message': '正在理解你的音乐偏好...'}, ensure_ascii=False)}\n\n"
            await asyncio.sleep(0.2)

            # 记录推理开始时间
            inference_start_time = time.time()

            # 执行推荐
            result = await agent.get_recommendations(
                query=query,
                user_preferences=user_preferences
            )

            # 发送Agent状态更新
            final_status = status_tracker.get_status()
            yield f"data: {json.dumps({'type': 'agent_status', 'status': final_status}, ensure_ascii=False)}\n\n"

            # 发送响应文本（流式输出）
            if result.get("success") and result.get("response"):
                response_text = result["response"]

                # 记录首字时间
                if first_token_time is None:
                    first_token_time = time.time()

                # 逐字符或逐词流式输出
                words = response_text.split()
                for i, word in enumerate(words):
                    partial_text = " ".join(words[:i+1])
                    yield f"data: {json.dumps({'type': 'response', 'text': partial_text, 'is_complete': False}, ensure_ascii=False)}\n\n"
                    await asyncio.sleep(0.05)  # 控制输出速度

                # 发送完整响应
                yield f"data: {json.dumps({'type': 'response', 'text': response_text, 'is_complete': True}, ensure_ascii=False)}\n\n"

            # 记录推理结束时间
            inference_end_time = time.time()
            inference_time = inference_end_time - (inference_start_time or start_time)

            # 发送推荐歌曲（逐个发送）
            if result.get("success") and result.get("recommendations"):
                recommendations = result["recommendations"]
                yield f"data: {json.dumps({'type': 'recommendations_start', 'count': len(recommendations)}, ensure_ascii=False)}\n\n"

                for i, rec in enumerate(recommendations):
                    song = rec.get("song", rec)
                    yield f"data: {json.dumps({'type': 'song', 'song': song, 'index': i, 'total': len(recommendations)}, ensure_ascii=False)}\n\n"
                    await asyncio.sleep(0.1)

                yield f"data: {json.dumps({'type': 'recommendations_complete'}, ensure_ascii=False)}\n\n"

            # 计算总耗时
            total_time = time.time() - start_time
            first_token_latency = (first_token_time - start_time) if first_token_time else None

            # 从计时器获取详细指标
            perf_summary = timer.get_summary()
            flat_timings = timer.get_flat_timings()

            # search_time 从计时器中获取（由装饰器自动记录，单位已经是ms）
            search_time_ms = (
                flat_timings.get('music_search_total_ms', 0) +
                flat_timings.get('spotify_search_total_ms', 0) +
                flat_timings.get('tailyapi_search_total_ms', 0) +
                flat_timings.get('recommend_by_activity_total_ms', 0) +
                flat_timings.get('recommend_by_mood_total_ms', 0)
            )

            # 记录详细日志用于调试
            logger.info(f"性能指标 - 总时间: {total_time*1000:.2f}ms, "
                       f"首字延迟: {first_token_latency*1000 if first_token_latency else 0:.2f}ms, "
                       f"推理时间: {inference_time*1000:.2f}ms, "
                       f"搜索时间: {search_time_ms:.2f}ms")

            # 发送性能指标 - 增强版
            performance_metrics = {
                'type': 'performance',
                'metrics': {
                    'total_time_ms': round(total_time * 1000, 2),
                    'first_token_latency_ms': round(first_token_latency * 1000, 2) if first_token_latency else None,
                    'inference_time_ms': round(inference_time * 1000, 2),
                    'search_time_ms': round(search_time_ms, 2) if search_time_ms > 0 else None,
                    # 新增详细指标
                    'node_timings': perf_summary.get('timings', {}),
                    'token_usage': perf_summary.get('token_usage', {}),
                    'api_calls': {
                        'spotify_search': len(timer.timings.get('spotify_search', [])),
                        'llm_calls': (
                            len(timer.timings.get('node_analyze_intent', [])) +
                            len(timer.timings.get('node_generate_explanation', []))
                        ),
                    }
                }
            }
            yield f"data: {json.dumps(performance_metrics, ensure_ascii=False)}\n\n"

            # 发送完成事件
            yield f"data: {json.dumps({'type': 'complete', 'success': True}, ensure_ascii=False)}\n\n"

        except Exception as e:
            logger.error(f"流式推荐失败: {str(e)}", exc_info=True)
            # 即使出错也发送已收集的性能指标
            try:
                perf_summary = timer.get_summary()
                yield f"data: {json.dumps({'type': 'error', 'message': str(e), 'partial_metrics': perf_summary}, ensure_ascii=False)}\n\n"
            except:
                yield f"data: {json.dumps({'type': 'error', 'message': str(e)}, ensure_ascii=False)}\n\n"


async def stream_playlist(
    query: str,
    target_size: int = 30,
    create_spotify_playlist: bool = False,
    public: bool = False,
    user_preferences: Optional[Dict[str, Any]] = None
) -> AsyncGenerator[str, None]:
    """
    流式生成歌单
    
    Yields:
        SSE格式的数据块
    """
    try:
        service = get_playlist_service()
        
        # 发送开始事件
        yield f"data: {json.dumps({'type': 'start', 'message': '开始生成你的专属歌单...'}, ensure_ascii=False)}\n\n"
        await asyncio.sleep(0.1)
        
        # 分析查询
        yield f"data: {json.dumps({'type': 'thinking', 'message': '正在分析你的需求...'}, ensure_ascii=False)}\n\n"
        await asyncio.sleep(0.2)
        
        # 准备种子
        yield f"data: {json.dumps({'type': 'thinking', 'message': '正在准备推荐种子...'}, ensure_ascii=False)}\n\n"
        await asyncio.sleep(0.2)
        
        # 获取推荐
        yield f"data: {json.dumps({'type': 'thinking', 'message': '正在从Spotify获取推荐...'}, ensure_ascii=False)}\n\n"
        
        # 执行歌单生成
        result = await service.generate_smart_playlist(
            user_query=query,
            user_preferences=user_preferences or {},
            target_size=target_size,
            create_spotify_playlist=create_spotify_playlist,
            public=public
        )
        
        # 发送上下文信息
        if result.get("context"):
            yield f"data: {json.dumps({'type': 'context', 'context': result['context']}, ensure_ascii=False)}\n\n"
        
        # 发送种子摘要
        if result.get("seed_summary"):
            yield f"data: {json.dumps({'type': 'seed_summary', 'seed_summary': result['seed_summary']}, ensure_ascii=False)}\n\n"
        
        # 发送歌曲列表（逐个发送）
        if result.get("songs"):
            songs = result["songs"]
            yield f"data: {json.dumps({'type': 'songs_start', 'count': len(songs)}, ensure_ascii=False)}\n\n"
            
            for i, song in enumerate(songs):
                yield f"data: {json.dumps({'type': 'song', 'song': song, 'index': i, 'total': len(songs)}, ensure_ascii=False)}\n\n"
                await asyncio.sleep(0.05)
            
            yield f"data: {json.dumps({'type': 'songs_complete'}, ensure_ascii=False)}\n\n"
        
        # 发送播放列表信息
        if result.get("playlist"):
            yield f"data: {json.dumps({'type': 'playlist', 'playlist': result['playlist']}, ensure_ascii=False)}\n\n"
        
        # 发送完成事件
        yield f"data: {json.dumps({'type': 'complete', 'success': True}, ensure_ascii=False)}\n\n"
        
    except Exception as e:
        logger.error(f"流式歌单生成失败: {str(e)}", exc_info=True)
        yield f"data: {json.dumps({'type': 'error', 'message': str(e)}, ensure_ascii=False)}\n\n"


async def stream_journey(
    story: Optional[str] = None,
    mood_transitions: Optional[List[Dict[str, Any]]] = None,
    duration: int = 60,
    user_preferences: Optional[Dict[str, Any]] = None,
    context: Optional[Dict[str, Any]] = None
) -> AsyncGenerator[str, None]:
    """
    流式生成音乐旅程
    
    Yields:
        SSE格式的数据块
    """
    try:
        service = get_journey_service()
        
        # 发送开始事件
        yield f"data: {json.dumps({'type': 'journey_start', 'message': '开始生成你的音乐旅程...'}, ensure_ascii=False)}\n\n"
        await asyncio.sleep(0.1)
        
        # 转换情绪点
        mood_points = None
        if mood_transitions:
            mood_points = [
                MoodPoint(
                    time=float(mt.get("time", 0)),
                    mood=mt.get("mood", "中性"),
                    intensity=float(mt.get("intensity", 0.5))
                )
                for mt in mood_transitions
            ]
        
        # 分析故事或情绪曲线
        if story:
            yield f"data: {json.dumps({'type': 'thinking', 'message': '正在分析你的故事...'}, ensure_ascii=False)}\n\n"
        elif mood_transitions:
            yield f"data: {json.dumps({'type': 'thinking', 'message': '正在分析情绪曲线...'}, ensure_ascii=False)}\n\n"
        await asyncio.sleep(0.2)
        
        # 生成旅程（这里可以进一步拆分步骤）
        result = await service.generate_journey(
            story=story,
            mood_transitions=mood_points,
            duration=duration,
            user_preferences=user_preferences,
            context=context
        )
        
        if not result.get("success"):
            yield f"data: {json.dumps({'type': 'error', 'message': result.get('error', '生成旅程失败')}, ensure_ascii=False)}\n\n"
            return
        
        segments = result.get("segments", [])
        total_segments = len(segments)
        
        # 发送旅程信息
        yield f"data: {json.dumps({'type': 'journey_info', 'total_segments': total_segments, 'total_duration': result.get('total_duration', 0), 'total_songs': result.get('total_songs', 0)}, ensure_ascii=False)}\n\n"
        
        # 逐个发送片段
        for i, segment in enumerate(segments):
            # 发送过渡点事件
            if i > 0:
                prev_segment = segments[i - 1]
                yield f"data: {json.dumps({'type': 'transition_point', 'from_segment': i-1, 'to_segment': i, 'from_mood': prev_segment.get('mood', ''), 'to_mood': segment.get('mood', '')}, ensure_ascii=False)}\n\n"
                await asyncio.sleep(0.1)
            
            # 发送片段开始
            yield f"data: {json.dumps({'type': 'segment_start', 'segment_id': i, 'segment': segment}, ensure_ascii=False)}\n\n"
            await asyncio.sleep(0.1)
            
            # 发送片段中的歌曲
            songs = segment.get("songs", [])
            for j, song in enumerate(songs):
                yield f"data: {json.dumps({'type': 'song', 'song': song, 'segment_id': i, 'index': j, 'total': len(songs)}, ensure_ascii=False)}\n\n"
                await asyncio.sleep(0.05)
            
            # 发送片段完成
            yield f"data: {json.dumps({'type': 'segment_complete', 'segment_id': i, 'segment': segment}, ensure_ascii=False)}\n\n"
            await asyncio.sleep(0.1)
        
        # 发送完成事件
        yield f"data: {json.dumps({'type': 'journey_complete', 'success': True, 'result': result}, ensure_ascii=False)}\n\n"
        
    except Exception as e:
        logger.error(f"流式旅程生成失败: {str(e)}", exc_info=True)
        yield f"data: {json.dumps({'type': 'error', 'message': str(e)}, ensure_ascii=False)}\n\n"


@app.get("/")
async def root():
    """健康检查"""
    return {"status": "ok", "service": "Music Recommendation API"}


@app.get("/health")
async def health():
    """健康检查"""
    return {"status": "healthy"}


@app.post("/api/recommendations/stream")
async def stream_recommendations_endpoint(request: RecommendationRequest):
    """
    流式获取音乐推荐（SSE）
    """
    return StreamingResponse(
        stream_recommendations(
            query=request.query,
            genre=request.genre,
            mood=request.mood,
            user_preferences=request.user_preferences
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )


@app.post("/api/playlist/stream")
async def stream_playlist_endpoint(request: PlaylistRequest):
    """
    流式生成歌单（SSE）
    """
    return StreamingResponse(
        stream_playlist(
            query=request.query,
            target_size=request.target_size,
            create_spotify_playlist=request.create_spotify_playlist,
            public=request.public,
            user_preferences=request.user_preferences
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )


@app.post("/api/recommendations")
async def get_recommendations(request: RecommendationRequest):
    """
    获取音乐推荐（非流式，兼容旧接口）
    """
    try:
        agent = get_agent()
        result = await agent.get_recommendations(
            query=request.query,
            user_preferences=request.user_preferences
        )
        return result
    except Exception as e:
        logger.error(f"获取推荐失败: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/playlist")
async def generate_playlist(request: PlaylistRequest):
    """
    生成歌单（非流式，兼容旧接口）
    """
    try:
        service = get_playlist_service()
        result = await service.generate_smart_playlist(
            user_query=request.query,
            user_preferences=request.user_preferences or {},
            target_size=request.target_size,
            create_spotify_playlist=request.create_spotify_playlist,
            public=request.public
        )
        return {"success": True, **result}
    except Exception as e:
        logger.error(f"生成歌单失败: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/journey/stream")
async def stream_journey_endpoint(request: JourneyRequest):
    """
    流式生成音乐旅程（SSE）
    """
    return StreamingResponse(
        stream_journey(
            story=request.story,
            mood_transitions=request.mood_transitions,
            duration=request.duration,
            user_preferences=request.user_preferences,
            context=request.context
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )


@app.post("/api/journey")
async def generate_journey(request: JourneyRequest):
    """
    生成音乐旅程（非流式，兼容旧接口）
    """
    try:
        service = get_journey_service()
        
        # 转换情绪点
        mood_points = None
        if request.mood_transitions:
            mood_points = [
                MoodPoint(
                    time=float(mt.get("time", 0)),
                    mood=mt.get("mood", "中性"),
                    intensity=float(mt.get("intensity", 0.5))
                )
                for mt in request.mood_transitions
            ]
        
        result = await service.generate_journey(
            story=request.story,
            mood_transitions=mood_points,
            duration=request.duration,
            user_preferences=request.user_preferences,
            context=request.context
        )
        return result
    except Exception as e:
        logger.error(f"生成旅程失败: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


def _clean_json_from_llm(llm_output: str) -> str:
    """从 LLM 输出中提取纯 JSON"""
    import re
    # 尝试提取 markdown 代码块
    match = re.search(r"```(?:json)?(.*?)```", llm_output, re.DOTALL)
    if match:
        return match.group(1).strip()

    # 尝试找到第一个完整的 JSON 对象
    text = llm_output.strip()
    start_idx = text.find('{')
    if start_idx == -1:
        return text

    brace_count = 0
    end_idx = start_idx
    for i, char in enumerate(text[start_idx:], start=start_idx):
        if char == '{':
            brace_count += 1
        elif char == '}':
            brace_count -= 1
            if brace_count == 0:
                end_idx = i + 1
                break

    return text[start_idx:end_idx]


@app.get("/api/logs")
async def get_logs(limit: int = 20):
    """
    获取最近的搜索日志
    """
    try:
        logs = get_search_logs(limit=limit)
        return {
            "success": True,
            "count": len(logs),
            "logs": logs
        }
    except Exception as e:
        logger.error(f"获取日志失败: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/search")
async def search_music(request: SearchRequest):
    """
    使用LLM意图分析提取槽位，然后搜索歌曲。
    - 优先歌词搜索（如果是歌词查询）
    - 优先 Spotify/MCP
    - 失败或无结果时自动回退到 TailyAPI
    - 仍无结果时使用本地 JSON 数据库模糊匹配
    """
    try:
        original_query = request.query

        # ===== 使用 LLM 进行意图分析和槽位提取 =====
        llm = get_chat_model()
        intent_prompt = MUSIC_INTENT_ANALYZER_PROMPT.format(user_input=original_query)

        try:
            response = await llm.ainvoke(intent_prompt)
            cleaned_json = _clean_json_from_llm(response.content)
            intent_data = json.loads(cleaned_json)

            intent_type = intent_data.get("intent_type", "search")
            parameters = intent_data.get("parameters", {})

            logger.info(f"搜索请求: 原始='{original_query}', 意图='{intent_type}', 参数={parameters}")
        except Exception as e:
            logger.warning(f"LLM意图分析失败: {e}, 使用默认搜索")
            intent_type = "search"
            parameters = {"query": original_query}

        # 记录搜索日志
        log_entry = {
            "action": "search",
            "original_query": original_query,
            "intent": intent_type,
            "parameters": parameters,
        }

        # 根据意图类型执行不同搜索
        search_tool = get_music_search_tool()
        start_time = __import__('time').time()

        # 执行搜索并获取来源信息
        search_result = None
        source = "unknown"

        if intent_type == "search_by_lyrics":
            # 歌词搜索
            lyrics = parameters.get("lyrics", original_query)
            search_result = await search_tool.search_songs_with_steps(
                query=lyrics,
                genre=request.genre,
                limit=request.limit,
                is_lyrics=True,
            )
            songs = search_result.get("songs", [])
            source = search_result.get("source", "unknown")
        elif intent_type == "search_by_topic":
            # 话题歌曲搜索
            topic = parameters.get("topic", original_query)
            topic_artist = parameters.get("artist")
            topic_genre = parameters.get("genre")
            from tools.topic_search import get_topic_search_engine
            from tools.music_tools import Song
            topic_engine = get_topic_search_engine()
            topic_results = await topic_engine.search_by_topic(
                topic, artist=topic_artist, genre=topic_genre, top_k=request.limit
            )
            songs = []
            for r in topic_results:
                song = Song(
                    title=r.get("title", "Unknown"),
                    artist=r.get("artist", "Unknown Artist"),
                    popularity=int(r.get("similarity_score", 0.8) * 100),
                )
                d = song.to_dict()
                d["topic"] = r.get("topic", topic)
                songs.append(d)
            source = "topic_web_search"
        elif intent_type == "search_by_theme":
            # 影视主题曲搜索
            title = parameters.get("title", original_query)
            from tools.theme_search import get_theme_search_engine
            from tools.music_tools import Song
            theme_engine = get_theme_search_engine()
            theme_results = await theme_engine.search_by_title(title, top_k=request.limit)
            songs = []
            for r in theme_results:
                song = Song(
                    title=r.get("title", "Unknown"),
                    artist=r.get("artist", "Unknown Artist"),
                    popularity=int(r.get("similarity_score", 0.8) * 100),
                )
                d = song.to_dict()
                d["theme_type"] = r.get("theme_type", "主题曲")
                d["from_title"] = r.get("from_title", title)
                songs.append(d)
            source = "theme_web_search"
        elif intent_type == "search":
            # 普通歌曲搜索
            query = parameters.get("query", original_query)
            cleaned_query = _clean_search_query(query)
            search_result = await search_tool.search_songs_with_steps(
                query=cleaned_query,
                genre=request.genre,
                limit=request.limit,
            )
            songs = search_result.get("songs", [])
            source = search_result.get("source", "unknown")
        elif intent_type == "recommend_by_artist":
            # 艺术家搜索：用元数据精确匹配，不做语义搜索
            artist_name = parameters.get("artist") or original_query
            artist_songs = await search_tool.get_songs_by_artist(artist_name, limit=request.limit)
            if artist_songs:
                songs = [s.to_dict() for s in artist_songs]
                source = "artist_metadata"
            else:
                songs = []
                source = "artist_not_found"
        elif intent_type == "recommend_by_genre":
            # 流派搜索
            genre_name = parameters.get("genre") or original_query
            genre_songs = await search_tool.get_songs_by_genre(genre_name, limit=request.limit)
            if genre_songs:
                songs = [s.to_dict() for s in genre_songs]
                source = "genre_search"
            else:
                songs = []
                source = "genre_not_found"
        elif intent_type == "recommend_by_activity":
            # 活动场景推荐
            activity = parameters.get("activity", "放松")
            from tools.music_tools import get_music_recommender
            recommender = get_music_recommender()
            recs = await recommender.recommend_by_activity(activity, limit=request.limit)
            # 将推荐转换为歌曲列表，并附加推荐理由
            songs = []
            for rec in recs:
                song_dict = rec.song.to_dict()
                song_dict['reason'] = rec.reason
                song_dict['similarity_score'] = rec.similarity_score
                songs.append(song_dict)
            source = "activity_recommendation"
        elif intent_type == "recommend_by_mood":
            # 心情推荐
            mood = parameters.get("mood", "开心")
            from tools.music_tools import get_music_recommender
            recommender = get_music_recommender()
            recs = await recommender.recommend_by_mood(mood, limit=request.limit)
            # 将推荐转换为歌曲列表，并附加推荐理由
            songs = []
            for rec in recs:
                song_dict = rec.song.to_dict()
                song_dict['reason'] = rec.reason
                song_dict['similarity_score'] = rec.similarity_score
                songs.append(song_dict)
            source = "mood_recommendation"
        else:
            # 其他情况使用默认搜索
            cleaned_query = _clean_search_query(original_query)
            search_result = await search_tool.search_songs_with_steps(
                query=cleaned_query,
                genre=request.genre,
                limit=request.limit,
            )
            songs = search_result.get("songs", [])
            source = search_result.get("source", "unknown")

        # 计算耗时
        elapsed_time = (__import__('time').time() - start_time) * 1000

        # 完成日志记录
        def _song_brief(s):
            d = s.to_dict() if hasattr(s, 'to_dict') else s
            return {"title": d.get("title", ""), "artist": d.get("artist", "")}

        log_entry.update({
            "result_count": len(songs),
            "elapsed_ms": round(elapsed_time, 2),
            "status": "success",
            "source": source,
            "songs": [_song_brief(s) for s in songs[:20]],
        })
        add_search_log(log_entry)

        return {
            "success": True,
            "count": len(songs),
            "songs": [s.to_dict() if hasattr(s, 'to_dict') else s for s in songs],
            "intent": intent_type,
            "parameters": parameters,
            "source": source,
        }
    except Exception as e:
        # 记录失败日志
        elapsed_time = (__import__('time').time() - start_time) * 1000
        log_entry.update({
            "result_count": 0,
            "elapsed_ms": round(elapsed_time, 2),
            "status": "error",
            "error": str(e)
        })
        add_search_log(log_entry)
        logger.error(f"搜索歌曲失败: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    
    port = int(os.getenv("API_PORT", "8501"))
    uvicorn.run(
        "api.server:app",
        host="0.0.0.0",
        port=port,
        reload=True,
        log_level="info"
    )

