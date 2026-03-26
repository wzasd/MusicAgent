"""
用户推荐历史管理服务

管理用户的推荐历史，用于：
1. 去重：避免重复推荐相同的歌曲
2. 个性化：基于历史推荐相似/互补的歌曲
3. 会话管理：跨请求保持推荐状态
"""

import json
import os
import time
from typing import List, Dict, Any, Optional, Set
from pathlib import Path
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
import threading


@dataclass
class SongKey:
    """歌曲唯一标识"""
    title: str
    artist: str

    def __hash__(self):
        return hash((self.title.lower().strip(), self.artist.lower().strip()))

    def __eq__(self, other):
        if not isinstance(other, SongKey):
            return False
        return (
            self.title.lower().strip() == other.title.lower().strip() and
            self.artist.lower().strip() == other.artist.lower().strip()
        )

    def to_string(self) -> str:
        return f"{self.title}::{self.artist}"

    @classmethod
    def from_string(cls, s: str) -> "SongKey":
        parts = s.split("::", 1)
        if len(parts) == 2:
            return cls(title=parts[0], artist=parts[1])
        return cls(title=s, artist="Unknown")


@dataclass
class RecommendationRecord:
    """推荐记录"""
    song_key: str
    timestamp: float
    query: Optional[str] = None
    source: Optional[str] = None  # rag, local_db, web_search 等

    def to_dict(self) -> Dict[str, Any]:
        return {
            "song_key": self.song_key,
            "timestamp": self.timestamp,
            "query": self.query,
            "source": self.source
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RecommendationRecord":
        return cls(
            song_key=data["song_key"],
            timestamp=data["timestamp"],
            query=data.get("query"),
            source=data.get("source")
        )


class UserHistoryService:
    """用户推荐历史管理服务

    支持两种存储模式：
    1. 内存模式：仅使用内存缓存，适合无状态部署
    2. 持久化模式：使用文件系统存储，适合长期历史
    """

    def __init__(
        self,
        storage_path: Optional[str] = None,
        max_history_per_user: int = 100,
        memory_cache_ttl: int = 3600,  # 内存缓存 TTL（秒）
        enable_persistence: bool = False
    ):
        """
        Args:
            storage_path: 持久化存储路径（None 则只使用内存）
            max_history_per_user: 每个用户最多保留多少条记录
            memory_cache_ttl: 内存缓存过期时间（秒）
            enable_persistence: 是否启用持久化存储
        """
        self.storage_path = Path(storage_path) if storage_path else None
        self.max_history_per_user = max_history_per_user
        self.memory_cache_ttl = memory_cache_ttl
        self.enable_persistence = enable_persistence and storage_path is not None

        # 内存缓存: session_id -> {"records": [], "last_access": timestamp}
        self._memory_cache: Dict[str, Dict[str, Any]] = {}
        self._lock = threading.RLock()

        # 确保存储目录存在
        if self.enable_persistence and self.storage_path:
            self.storage_path.mkdir(parents=True, exist_ok=True)

    def _get_cache_key(self, session_id: str) -> str:
        """生成缓存键"""
        return session_id

    def _load_from_disk(self, session_id: str) -> List[RecommendationRecord]:
        """从磁盘加载用户历史"""
        if not self.enable_persistence or not self.storage_path:
            return []

        file_path = self.storage_path / f"{session_id}.json"
        if not file_path.exists():
            return []

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                records = [RecommendationRecord.from_dict(r) for r in data.get("records", [])]
                # 过滤过期记录（7天）
                cutoff_time = time.time() - 7 * 24 * 3600
                records = [r for r in records if r.timestamp > cutoff_time]
                return records
        except (json.JSONDecodeError, IOError):
            return []

    def _save_to_disk(self, session_id: str, records: List[RecommendationRecord]):
        """保存用户历史到磁盘"""
        if not self.enable_persistence or not self.storage_path:
            return

        file_path = self.storage_path / f"{session_id}.json"
        try:
            data = {
                "session_id": session_id,
                "updated_at": time.time(),
                "records": [r.to_dict() for r in records]
            }
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except IOError:
            pass  # 忽略写入错误

    def _get_records(self, session_id: str) -> List[RecommendationRecord]:
        """获取用户历史记录（优先从内存，其次从磁盘）"""
        cache_key = self._get_cache_key(session_id)

        with self._lock:
            # 检查内存缓存
            if cache_key in self._memory_cache:
                cache_entry = self._memory_cache[cache_key]
                cache_entry["last_access"] = time.time()
                return cache_entry["records"]

            # 从磁盘加载
            records = self._load_from_disk(session_id)

            # 存入内存缓存
            self._memory_cache[cache_key] = {
                "records": records,
                "last_access": time.time()
            }

            return records

    def _update_records(self, session_id: str, records: List[RecommendationRecord]):
        """更新用户历史记录"""
        cache_key = self._get_cache_key(session_id)

        with self._lock:
            self._memory_cache[cache_key] = {
                "records": records,
                "last_access": time.time()
            }

            # 异步保存到磁盘
            if self.enable_persistence:
                self._save_to_disk(session_id, records)

    def add_to_history(
        self,
        session_id: str,
        songs: List[Dict[str, Any]],
        query: Optional[str] = None,
        source: Optional[str] = None
    ):
        """添加歌曲到用户历史

        Args:
            session_id: 用户会话 ID
            songs: 歌曲列表，每个歌曲需要包含 title 和 artist
            query: 触发推荐的查询
            source: 推荐来源
        """
        if not session_id or not songs:
            return

        records = self._get_records(session_id)

        for song in songs:
            title = str(song.get("title", "")).strip()
            artist = str(song.get("artist", "")).strip()

            if not title or not artist:
                continue

            song_key = SongKey(title=title, artist=artist).to_string()

            # 检查是否已存在
            existing = [r for r in records if r.song_key == song_key]
            if existing:
                # 更新时间戳
                existing[0].timestamp = time.time()
            else:
                # 添加新记录
                records.append(RecommendationRecord(
                    song_key=song_key,
                    timestamp=time.time(),
                    query=query,
                    source=source
                ))

        # 限制历史大小，保留最新的
        if len(records) > self.max_history_per_user:
            records = sorted(records, key=lambda r: r.timestamp, reverse=True)
            records = records[:self.max_history_per_user]

        self._update_records(session_id, records)

    def get_recently_recommended(
        self,
        session_id: str,
        window: Optional[int] = None,
        return_songs: bool = False
    ) -> Set[str]:
        """获取用户最近推荐的歌曲

        Args:
            session_id: 用户会话 ID
            window: 最近 N 首，None 表示全部
            return_songs: 是否返回 SongKey 对象而不是字符串

        Returns:
            歌曲键的集合（title::artist）
        """
        if not session_id:
            return set()

        records = self._get_records(session_id)

        if window is not None:
            # 按时间排序，取最近 N 首
            records = sorted(records, key=lambda r: r.timestamp, reverse=True)
            records = records[:window]

        if return_songs:
            return {r.song_key for r in records}

        return {r.song_key for r in records}

    def filter_seen_songs(
        self,
        session_id: str,
        candidate_songs: List[Dict[str, Any]],
        window: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """过滤掉用户已听过的歌曲

        Args:
            session_id: 用户会话 ID
            candidate_songs: 候选歌曲列表
            window: 最近 N 首内去重，None 表示全部历史

        Returns:
            过滤后的歌曲列表
        """
        if not session_id or not candidate_songs:
            return candidate_songs

        history = self.get_recently_recommended(session_id, window=window)

        filtered = []
        for song in candidate_songs:
            title = str(song.get("title", "")).strip()
            artist = str(song.get("artist", "")).strip()

            if not title or not artist:
                filtered.append(song)
                continue

            song_key = SongKey(title=title, artist=artist).to_string()

            if song_key not in history:
                filtered.append(song)

        return filtered

    def is_song_seen(
        self,
        session_id: str,
        song: Dict[str, Any],
        window: Optional[int] = None
    ) -> bool:
        """检查歌曲是否已推荐过

        Args:
            session_id: 用户会话 ID
            song: 歌曲信息
            window: 最近 N 首内检查，None 表示全部历史

        Returns:
            是否已推荐过
        """
        if not session_id:
            return False

        title = str(song.get("title", "")).strip()
        artist = str(song.get("artist", "")).strip()

        if not title or not artist:
            return False

        history = self.get_recently_recommended(session_id, window=window)
        song_key = SongKey(title=title, artist=artist).to_string()

        return song_key in history

    def clear_history(self, session_id: str):
        """清空用户历史

        Args:
            session_id: 用户会话 ID
        """
        if not session_id:
            return

        cache_key = self._get_cache_key(session_id)

        with self._lock:
            if cache_key in self._memory_cache:
                del self._memory_cache[cache_key]

            if self.enable_persistence and self.storage_path:
                file_path = self.storage_path / f"{session_id}.json"
                if file_path.exists():
                    try:
                        file_path.unlink()
                    except IOError:
                        pass

    def get_history_stats(self, session_id: str) -> Dict[str, Any]:
        """获取用户历史统计

        Args:
            session_id: 用户会话 ID

        Returns:
            统计信息字典
        """
        records = self._get_records(session_id)

        if not records:
            return {
                "total_recommendations": 0,
                "unique_artists": 0,
                "first_recommendation": None,
                "last_recommendation": None
            }

        # 统计艺术家
        artists = set()
        for record in records:
            try:
                key = SongKey.from_string(record.song_key)
                artists.add(key.artist)
            except:
                pass

        timestamps = [r.timestamp for r in records]

        return {
            "total_recommendations": len(records),
            "unique_artists": len(artists),
            "first_recommendation": datetime.fromtimestamp(min(timestamps)).isoformat(),
            "last_recommendation": datetime.fromtimestamp(max(timestamps)).isoformat()
        }

    def cleanup_expired_cache(self, max_idle_time: int = 3600):
        """清理过期的内存缓存

        Args:
            max_idle_time: 最大空闲时间（秒）
        """
        now = time.time()
        expired_keys = []

        with self._lock:
            for key, entry in self._memory_cache.items():
                if now - entry["last_access"] > max_idle_time:
                    expired_keys.append(key)

            for key in expired_keys:
                del self._memory_cache[key]

    def get_session_recommendations(
        self,
        session_id: str,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """获取会话的推荐历史（按时间倒序）

        Args:
            session_id: 用户会话 ID
            limit: 返回数量限制

        Returns:
            推荐记录列表
        """
        records = self._get_records(session_id)
        records = sorted(records, key=lambda r: r.timestamp, reverse=True)

        return [
            {
                "song_key": r.song_key,
                "timestamp": r.timestamp,
                "datetime": datetime.fromtimestamp(r.timestamp).isoformat(),
                "query": r.query,
                "source": r.source
            }
            for r in records[:limit]
        ]


# 全局实例（单例模式）
_history_service: Optional[UserHistoryService] = None


def get_history_service(
    storage_path: Optional[str] = None,
    max_history_per_user: int = 100,
    enable_persistence: bool = False
) -> UserHistoryService:
    """获取全局历史服务实例

    Args:
        storage_path: 持久化存储路径
        max_history_per_user: 每个用户最大历史数
        enable_persistence: 是否启用持久化

    Returns:
        UserHistoryService 实例
    """
    global _history_service

    if _history_service is None:
        _history_service = UserHistoryService(
            storage_path=storage_path,
            max_history_per_user=max_history_per_user,
            enable_persistence=enable_persistence
        )

    return _history_service


def reset_history_service():
    """重置全局历史服务实例（主要用于测试）"""
    global _history_service
    _history_service = None
