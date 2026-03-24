"""
音乐 Agent 服务层（子 Agent）
负责执行具体的音乐搜索和推荐任务
"""

from typing import Dict, Any, List, Optional
from dataclasses import dataclass

from config.logging_config import get_logger
from tools.music_tools import get_music_search_tool, get_music_recommender, Song, MusicRecommendation

logger = get_logger(__name__)


@dataclass
class MusicAgentResult:
    """子 Agent 返回的结果"""
    songs: List[Song]
    source: str  # 数据来源
    total_found: int  # 找到的总数
    query_type: str  # 查询类型
    message: str  # 给用户的提示信息
    metadata: Optional[Dict[str, Any]] = None  # 额外的元数据


class MusicAgentService:
    """
    音乐 Agent 服务（子 Agent）
    封装所有音乐搜索和推荐的业务逻辑
    """

    def __init__(self):
        self.search_tool = get_music_search_tool()
        self.recommender = get_music_recommender()

    async def search_songs(
        self,
        query: str,
        limit: int = 5,
        is_lyrics: bool = False
    ) -> MusicAgentResult:
        """
        搜索歌曲

        Args:
            query: 搜索关键词
            limit: 返回数量上限
            is_lyrics: 是否为歌词搜索

        Returns:
            MusicAgentResult 包含歌曲列表和元信息
        """
        logger.info(f"[子Agent] 搜索歌曲: query='{query}', limit={limit}, is_lyrics={is_lyrics}")

        result = await self.search_tool.search_songs_with_steps(
            query=query,
            limit=limit,
            is_lyrics=is_lyrics
        )

        songs = result.get("songs", [])
        source = result.get("source", "unknown")

        if not songs:
            return MusicAgentResult(
                songs=[],
                source=source,
                total_found=0,
                query_type="search",
                message=f"抱歉，没有找到《{query}》"
            )

        return MusicAgentResult(
            songs=songs,
            source=source,
            total_found=len(songs),
            query_type="search",
            message=f"找到 {len(songs)} 首相关歌曲"
        )

    async def get_songs_by_artist(
        self,
        artist: str,
        limit: int = 5
    ) -> MusicAgentResult:
        """
        获取艺术家的歌曲

        Args:
            artist: 艺术家名称
            limit: 返回数量上限

        Returns:
            MusicAgentResult 包含歌曲列表和元信息
        """
        logger.info(f"[子Agent] 获取艺术家歌曲: artist='{artist}', limit={limit}")

        songs, source = await self.search_tool.get_songs_by_artist(artist, limit=limit)

        if not songs:
            return MusicAgentResult(
                songs=[],
                source=source,
                total_found=0,
                query_type="artist",
                message=f"抱歉，没有找到{artist}的歌曲"
            )

        return MusicAgentResult(
            songs=songs,
            source=source,
            total_found=len(songs),
            query_type="artist",
            message=f"找到 {len(songs)} 首{artist}的歌曲"
        )

    async def recommend_by_mood(
        self,
        mood: str,
        limit: int = 5,
        session_id: Optional[str] = None
    ) -> MusicAgentResult:
        """
        根据心情推荐歌曲

        Args:
            mood: 心情描述
            limit: 返回数量上限
            session_id: 会话ID（用于多样性去重）

        Returns:
            MusicAgentResult 包含歌曲列表和元信息
        """
        logger.info(f"[子Agent] 心情推荐: mood='{mood}', limit={limit}, session={session_id}")

        recs = await self.recommender.recommend_by_mood(
            mood=mood,
            limit=limit,
            session_id=session_id,
            enable_diversity=True
        )

        if not recs:
            return MusicAgentResult(
                songs=[],
                source="none",
                total_found=0,
                query_type="mood",
                message=f"抱歉，没有找到适合{mood}心情的歌曲"
            )

        songs = [rec.song for rec in recs]

        return MusicAgentResult(
            songs=songs,
            source="rag_v2",
            total_found=len(songs),
            query_type="mood",
            message=f"为您推荐 {len(songs)} 首适合{mood}心情的歌曲"
        )

    async def search_songs_by_artist_with_title(
        self,
        artist: str,
        title: str,
        limit: int = 5
    ) -> MusicAgentResult:
        """
        搜索特定艺术家的特定歌曲，优先精确匹配歌名

        Args:
            artist: 艺术家名称
            title: 歌曲名称
            limit: 返回数量上限

        Returns:
            MusicAgentResult 包含匹配的歌曲列表和元信息
        """
        logger.info(f"[子Agent] 搜索特定歌曲: artist='{artist}', title='{title}'")

        import re

        def normalize(s: str) -> str:
            """标准化字符串：去除标点和空格，小写"""
            return re.sub(r'[^\w]', '', s.lower())

        title_normalized = normalize(title)

        # 获取艺术家歌曲（使用 ChromaDB 的 get_by_artist）
        songs, source = await self.search_tool.get_songs_by_artist(artist, limit=limit * 3)

        if not songs:
            return MusicAgentResult(
                songs=[],
                source=source,
                total_found=0,
                query_type="search_by_artist_title",
                message=f"抱歉，没有找到{artist}的歌曲"
            )

        # 精确匹配
        exact_matches = [s for s in songs if normalize(s.title) == title_normalized]
        # 部分匹配（包含关系）
        partial_matches = [
            s for s in songs
            if title_normalized in normalize(s.title) or normalize(s.title) in title_normalized
        ]

        # 按优先级排序：精确匹配 > 部分匹配 > 其他歌曲
        if exact_matches:
            matched_songs = exact_matches
            match_type = "精确匹配"
        elif partial_matches:
            matched_songs = partial_matches
            match_type = "部分匹配"
        else:
            matched_songs = songs
            match_type = "艺术家相关"

        logger.info(f"[子Agent] 匹配结果: {match_type}, 找到 {len(matched_songs)} 首歌曲")

        return MusicAgentResult(
            songs=matched_songs[:limit],
            source=source,
            total_found=len(matched_songs),
            query_type="search_by_artist_title",
            message=f"找到 {len(matched_songs)} 首匹配歌曲"
        )

    async def recommend_by_activity(
        self,
        activity: str,
        limit: int = 5,
        session_id: Optional[str] = None
    ) -> MusicAgentResult:
        """
        根据活动场景推荐歌曲

        Args:
            activity: 活动描述
            limit: 返回数量上限
            session_id: 会话ID（用于多样性去重）

        Returns:
            MusicAgentResult 包含歌曲列表和元信息
        """
        logger.info(f"[子Agent] 活动推荐: activity='{activity}', limit={limit}, session={session_id}")

        recs = await self.recommender.recommend_by_activity(
            activity=activity,
            limit=limit,
            session_id=session_id,
            enable_diversity=True
        )

        if not recs:
            return MusicAgentResult(
                songs=[],
                source="none",
                total_found=0,
                query_type="activity",
                message=f"抱歉，没有找到适合{activity}的歌曲"
            )

        songs = [rec.song for rec in recs]

        return MusicAgentResult(
            songs=songs,
            source="rag_v2",
            total_found=len(songs),
            query_type="activity",
            message=f"为您推荐 {len(songs)} 首适合{activity}的歌曲"
        )


# 全局服务实例
_agent_service: Optional[MusicAgentService] = None


def get_music_agent_service() -> MusicAgentService:
    """获取音乐 Agent 服务单例"""
    global _agent_service
    if _agent_service is None:
        _agent_service = MusicAgentService()
    return _agent_service
