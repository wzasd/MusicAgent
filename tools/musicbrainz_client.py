"""
MusicBrainz API 客户端
开源音乐百科全书，免费 API
https://musicbrainz.org/doc/MusicBrainz_API/Search
"""

import json
import time
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from urllib.parse import quote

import requests

from config.logging_config import get_logger

logger = get_logger(__name__)


@dataclass
class MBRecording:
    """MusicBrainz 录音/歌曲信息"""
    id: str
    title: str
    artist: str
    artist_id: Optional[str] = None
    album: Optional[str] = None
    album_id: Optional[str] = None
    year: Optional[int] = None
    genre: Optional[List[str]] = None
    duration: Optional[int] = None  # 毫秒
    score: Optional[int] = None  # 匹配分数


class MusicBrainzClient:
    """MusicBrainz API 客户端"""

    BASE_URL = "https://musicbrainz.org/ws/2"

    def __init__(self, app_name: str = "MusicRecommendationAgent", version: str = "1.0", contact: str = "user@example.com"):
        """
        初始化 MusicBrainz 客户端

        Args:
            app_name: 应用名称（MusicBrainz 要求）
            version: 版本号
            contact: 联系邮箱（必须提供）
        """
        self.headers = {
            "User-Agent": f"{app_name}/{version} ( {contact} )",
            "Accept": "application/json"
        }
        self.last_request_time = 0
        self.min_interval = 1.0  # MusicBrainz 要求每秒不超过 1 个请求

    def _rate_limit(self):
        """速率限制"""
        current_time = time.time()
        elapsed = current_time - self.last_request_time
        if elapsed < self.min_interval:
            time.sleep(self.min_interval - elapsed)
        self.last_request_time = time.time()

    def _make_request(self, endpoint: str, params: Dict[str, Any]) -> Optional[Dict]:
        """
        发送 API 请求

        Args:
            endpoint: API 端点
            params: 查询参数

        Returns:
            JSON 响应数据
        """
        self._rate_limit()

        url = f"{self.BASE_URL}/{endpoint}"

        try:
            response = requests.get(
                url,
                headers=self.headers,
                params=params,
                timeout=30
            )

            if response.status_code == 503:
                logger.warning("MusicBrainz API 速率限制，等待后重试")
                time.sleep(2)
                return self._make_request(endpoint, params)

            response.raise_for_status()
            return response.json()

        except requests.exceptions.RequestException as e:
            logger.error(f"MusicBrainz API 请求失败: {e}")
            return None

    def search_recordings(
        self,
        query: str,
        artist: Optional[str] = None,
        limit: int = 10,
        offset: int = 0
    ) -> List[MBRecording]:
        """
        搜索录音/歌曲

        Args:
            query: 歌曲名称
            artist: 艺术家名称（可选）
            limit: 返回数量
            offset: 分页偏移

        Returns:
            录音列表
        """
        try:
            # 构建 Lucene 查询语法
            if artist:
                search_query = f'recording:"{query}" AND artist:"{artist}"'
            else:
                search_query = f'recording:"{query}"'

            params = {
                "query": search_query,
                "fmt": "json",
                "limit": min(limit, 100),
                "offset": offset
            }

            logger.info(f"MusicBrainz 搜索录音: query='{query}', artist='{artist}'")

            data = self._make_request("recording/", params)

            if not data or "recordings" not in data:
                return []

            recordings = []
            for rec in data["recordings"]:
                try:
                    # 提取艺术家信息
                    artist_name = "Unknown Artist"
                    artist_id = None
                    if "artist-credit" in rec and rec["artist-credit"]:
                        artist_name = rec["artist-credit"][0].get("name", "Unknown Artist")
                        if "artist" in rec["artist-credit"][0]:
                            artist_id = rec["artist-credit"][0]["artist"].get("id")

                    # 提取专辑信息
                    album_name = None
                    album_id = None
                    if "releases" in rec and rec["releases"]:
                        album_name = rec["releases"][0].get("title")
                        album_id = rec["releases"][0].get("id")

                    # 提取年份
                    year = None
                    if "first-release-date" in rec:
                        date_str = rec["first-release-date"]
                        if date_str and len(date_str) >= 4:
                            try:
                                year = int(date_str[:4])
                            except ValueError:
                                pass

                    # 提取时长（转换为秒）
                    duration = None
                    if "length" in rec:
                        duration = int(rec["length"] / 1000)  # 毫秒转秒

                    # 提取标签/流派
                    genres = []
                    if "tags" in rec:
                        genres = [tag["name"] for tag in rec["tags"]]

                    recording = MBRecording(
                        id=rec.get("id", ""),
                        title=rec.get("title", "Unknown"),
                        artist=artist_name,
                        artist_id=artist_id,
                        album=album_name,
                        album_id=album_id,
                        year=year,
                        genre=genres if genres else None,
                        duration=duration,
                        score=rec.get("score")
                    )
                    recordings.append(recording)

                except Exception as e:
                    logger.debug(f"解析录音数据失败: {e}")
                    continue

            logger.info(f"MusicBrainz 找到 {len(recordings)} 首录音")
            return recordings

        except Exception as e:
            logger.error(f"MusicBrainz 搜索录音失败: {e}")
            return []

    def search_artists(self, query: str, limit: int = 10) -> List[Dict[str, Any]]:
        """
        搜索艺术家

        Args:
            query: 艺术家名称
            limit: 返回数量

        Returns:
            艺术家列表
        """
        try:
            params = {
                "query": f'artist:"{query}"',
                "fmt": "json",
                "limit": min(limit, 100)
            }

            data = self._make_request("artist/", params)

            if not data or "artists" not in data:
                return []

            artists = []
            for artist in data["artists"]:
                artists.append({
                    "id": artist.get("id"),
                    "name": artist.get("name"),
                    "sort_name": artist.get("sort-name"),
                    "type": artist.get("type"),
                    "country": artist.get("country"),
                    "score": artist.get("score")
                })

            return artists

        except Exception as e:
            logger.error(f"MusicBrainz 搜索艺术家失败: {e}")
            return []

    def get_artist_works(self, artist_id: str, limit: int = 25) -> List[MBRecording]:
        """
        获取艺术家的作品列表

        Args:
            artist_id: MusicBrainz 艺术家 ID
            limit: 返回数量

        Returns:
            录音列表
        """
        try:
            # 使用 browse 接口获取录音
            params = {
                "artist": artist_id,
                "fmt": "json",
                "limit": min(limit, 100),
                "inc": "artist-credits+releases"
            }

            data = self._make_request("recording/", params)

            if not data or "recordings" not in data:
                return []

            recordings = []
            for rec in data["recordings"]:
                try:
                    artist_name = "Unknown Artist"
                    if "artist-credit" in rec and rec["artist-credit"]:
                        artist_name = rec["artist-credit"][0].get("name", "Unknown Artist")

                    recording = MBRecording(
                        id=rec.get("id", ""),
                        title=rec.get("title", "Unknown"),
                        artist=artist_name,
                        duration=int(rec["length"] / 1000) if "length" in rec else None
                    )
                    recordings.append(recording)
                except Exception:
                    continue

            return recordings

        except Exception as e:
            logger.error(f"获取艺术家作品失败: {e}")
            return []

    def get_recording_by_isrc(self, isrc: str) -> Optional[MBRecording]:
        """
        通过 ISRC 代码查找录音

        Args:
            isrc: ISRC 代码

        Returns:
            录音信息
        """
        try:
            params = {
                "query": f'isrc:{isrc}',
                "fmt": "json",
                "limit": 1
            }

            data = self._make_request("recording/", params)

            if not data or "recordings" not in data or not data["recordings"]:
                return None

            rec = data["recordings"][0]

            artist_name = "Unknown Artist"
            if "artist-credit" in rec and rec["artist-credit"]:
                artist_name = rec["artist-credit"][0].get("name", "Unknown Artist")

            return MBRecording(
                id=rec.get("id", ""),
                title=rec.get("title", "Unknown"),
                artist=artist_name,
                duration=int(rec["length"] / 1000) if "length" in rec else None
            )

        except Exception as e:
            logger.error(f"通过 ISRC 查找录音失败: {e}")
            return None


# 全局客户端实例
_mb_client: Optional[MusicBrainzClient] = None


def get_musicbrainz_client() -> MusicBrainzClient:
    """获取 MusicBrainz 客户端（单例）"""
    global _mb_client
    if _mb_client is None:
        _mb_client = MusicBrainzClient()
    return _mb_client
