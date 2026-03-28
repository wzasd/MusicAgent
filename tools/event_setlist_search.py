"""
事件歌单搜索工具
提供演唱会、音乐节等事件的实际歌单查询功能
"""

import json
import re
from dataclasses import dataclass, asdict
from typing import List, Dict, Any, Optional

from config.logging_config import get_logger
from llms.siliconflow_llm import SiliconFlowLLM
from prompts.event_setlist_prompts import (
    SETLIST_EXTRACTION_PROMPT,
    SETLIST_SEARCH_QUERY_PROMPT,
)

logger = get_logger(__name__)


@dataclass
class EventSetlistSong:
    """事件歌单中的歌曲"""
    order: int
    title: str
    artist: Optional[str] = None
    is_cover: bool = False
    original_artist: Optional[str] = None
    note: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class EventSetlist:
    """事件歌单"""
    event_name: str
    event_type: str
    artist: str
    date: Optional[str] = None
    location: Optional[str] = None
    songs: List[EventSetlistSong] = None
    total_songs: int = 0
    encore_count: int = 0
    source_url: str = ""
    confidence: float = 0.0

    def __post_init__(self):
        if self.songs is None:
            self.songs = []

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_name": self.event_name,
            "event_type": self.event_type,
            "artist": self.artist,
            "date": self.date,
            "location": self.location,
            "songs": [s.to_dict() for s in self.songs],
            "total_songs": self.total_songs,
            "encore_count": self.encore_count,
            "source_url": self.source_url,
            "confidence": self.confidence,
        }


class EventSetlistSearchEngine:
    """事件歌单搜索引擎"""

    def __init__(self, web_search_provider=None):
        from llms import get_llm
        self.llm = get_llm()
        self.web_search = web_search_provider or self._get_default_provider()
        logger.info("EventSetlistSearchEngine 初始化完成")

    def _get_default_provider(self):
        from tools.web_search.factory import get_web_search
        return get_web_search()

    def _build_search_query(
        self,
        artist: str,
        event_type: str,
        year: Optional[str] = None,
        location: Optional[str] = None,
        event_name: Optional[str] = None
    ) -> str:
        parts = [artist]
        if event_name:
            parts.append(event_name)
        if year:
            parts.append(year)
        if location:
            location_map = {
                "巴黎": "Paris", "伦敦": "London", "纽约": "New York",
                "东京": "Tokyo", "上海": "Shanghai", "北京": "Beijing",
                "香港": "Hong Kong", "台北": "Taipei",
            }
            parts.append(location_map.get(location, location))
        event_keywords = {
            "concert": "concert setlist",
            "festival": "festival lineup setlist",
            "awards": "awards performance setlist",
            "tv_show": "tv show performance setlist",
        }
        parts.append(event_keywords.get(event_type, "setlist"))
        return " ".join(parts)

    async def search(
        self,
        artist: str,
        event_type: str,
        year: Optional[str] = None,
        location: Optional[str] = None,
        event_name: Optional[str] = None
    ) -> Optional[EventSetlist]:
        import time
        start_time = time.time()

        try:
            # 构建查询
            query = self._build_search_query(artist, event_type, year, location, event_name)
            logger.info(f"搜索事件歌单: query='{query}'")

            # Web搜索
            web_start = time.time()
            search_results = await self._search_web(query)
            web_time = time.time() - web_start
            logger.info(f"[性能] Web搜索耗时: {web_time:.2f}秒")

            if not search_results:
                logger.warning(f"Web搜索无结果: {query}")
                return None

            # LLM提取
            llm_start = time.time()
            setlist = await self._extract_setlist(search_results, artist, event_type)
            llm_time = time.time() - llm_start
            logger.info(f"[性能] LLM提取耗时: {llm_time:.2f}秒")

            if setlist:
                if year:
                    setlist.date = setlist.date or year
                if location:
                    setlist.location = setlist.location or location
                logger.info(f"成功提取歌单: {setlist.event_name}, {len(setlist.songs)}首歌")

            total_time = time.time() - start_time
            logger.info(f"[性能] 事件歌单搜索总耗时: {total_time:.2f}秒 (Web:{web_time:.2f}s, LLM:{llm_time:.2f}s)")

            return setlist
        except Exception as e:
            logger.error(f"搜索事件歌单失败: {e}", exc_info=True)
            return None

    async def _search_web(self, query: str) -> str:
        try:
            response = await self.web_search.search(query, max_results=5)
            results = response.get("results", [])
            snippets = []
            for i, result in enumerate(results, 1):
                title = result.title
                content = result.content
                url = result.url
                snippets.append(f"[{i}] {title}\n{content}\nSource: {url}\n")
            return "\n".join(snippets)
        except Exception as e:
            logger.error(f"Web搜索失败: {e}")
            return ""

    async def _extract_setlist(
        self, search_results: str, artist: str, event_type: str
    ) -> Optional[EventSetlist]:
        try:
            prompt = SETLIST_EXTRACTION_PROMPT.format(
                artist=artist, event_type=event_type, search_results=search_results
            )
            # 使用低温度（0.3）和缓存以提高重复查询性能
            response = await self.llm.invoke_text_cached(
                "你是专业的现场音乐资料整理专家，擅长提取演唱会歌单信息。只从给定的搜索结果中提取，不要凭记忆补充。",
                prompt,
                temperature=0.3,
                max_tokens=2000
            )
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if not json_match:
                logger.warning("LLM响应中未找到JSON")
                return None
            data = json.loads(json_match.group())
            if data is None:
                logger.info("搜索结果中无歌单信息")
                return None
            songs = []
            for song_data in data.get("songs", []):
                songs.append(EventSetlistSong(
                    order=song_data.get("order", 0),
                    title=song_data.get("title", "Unknown"),
                    artist=song_data.get("artist"),
                    is_cover=song_data.get("is_cover", False),
                    original_artist=song_data.get("original_artist"),
                    note=song_data.get("note")
                ))
            return EventSetlist(
                event_name=data.get("event_name", f"{artist} {event_type}"),
                event_type=event_type, artist=artist, date=data.get("date"),
                location=data.get("location"), songs=songs,
                total_songs=data.get("total_songs", len(songs)),
                encore_count=data.get("encore_count", 0),
                confidence=data.get("confidence", 0.5)
            )
        except json.JSONDecodeError as e:
            logger.error(f"JSON解析失败: {e}")
            return None
        except Exception as e:
            logger.error(f"提取歌单失败: {e}")
            return None


_event_setlist_search_engine = None

def get_event_setlist_search_engine() -> EventSetlistSearchEngine:
    global _event_setlist_search_engine
    if _event_setlist_search_engine is None:
        _event_setlist_search_engine = EventSetlistSearchEngine()
    return _event_setlist_search_engine
