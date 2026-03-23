"""
Web 搜索结果缓存管理器 - 多级缓存策略
L1: 内存缓存（5分钟TTL，最快）
L2: 文件缓存（24小时TTL，持久化）
"""

import asyncio
import hashlib
import json
import os
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from config.logging_config import get_logger

logger = get_logger(__name__)


class SearchCacheManager:
    """多级缓存管理器"""

    def __init__(self, cache_dir: Optional[str] = None, memory_ttl: int = 300, file_ttl: int = 86400):
        """
        初始化缓存管理器

        Args:
            cache_dir: 文件缓存目录，默认 ./cache/web_search
            memory_ttl: 内存缓存TTL（秒），默认300秒（5分钟）
            file_ttl: 文件缓存TTL（秒），默认86400秒（24小时）
        """
        # L1: 内存缓存（进程内，最快）
        self._memory_cache: Dict[str, Dict[str, Any]] = {}
        self._memory_ttl = memory_ttl

        # L2: 文件缓存（持久化）
        if cache_dir is None:
            cache_dir = os.path.join(os.path.dirname(__file__), "..", "cache", "web_search")
        self._cache_dir = Path(cache_dir)
        self._cache_dir.mkdir(parents=True, exist_ok=True)
        self._file_ttl = file_ttl

        logger.info(f"缓存管理器初始化完成: 内存TTL={memory_ttl}s, 文件TTL={file_ttl}s, 目录={self._cache_dir}")

    def _make_key(self, query: str, search_type: str) -> str:
        """
        生成缓存键

        Args:
            query: 搜索查询
            search_type: 搜索类型（theme/topic/lyrics等）

        Returns:
            缓存键字符串
        """
        # 使用MD5哈希生成稳定的键
        key_str = f"{search_type}:{query.lower().strip()}"
        return hashlib.md5(key_str.encode()).hexdigest()

    def _get_cache_file_path(self, key: str) -> Path:
        """获取缓存文件路径"""
        return self._cache_dir / f"{key}.json"

    async def get(self, query: str, search_type: str) -> Optional[List[Dict]]:
        """
        获取缓存结果（先查内存，再查文件）

        Args:
            query: 搜索查询
            search_type: 搜索类型

        Returns:
            缓存的结果列表，如果没有则返回None
        """
        key = self._make_key(query, search_type)

        # L1: 内存缓存
        if key in self._memory_cache:
            entry = self._memory_cache[key]
            if time.time() - entry["timestamp"] < self._memory_ttl:
                logger.debug(f"内存缓存命中: {search_type} '{query[:30]}...'")
                return entry["data"]
            else:
                # 过期，删除
                del self._memory_cache[key]

        # L2: 文件缓存
        cache_file = self._get_cache_file_path(key)
        if cache_file.exists():
            try:
                mtime = cache_file.stat().st_mtime
                if time.time() - mtime < self._file_ttl:
                    with open(cache_file, 'r', encoding='utf-8') as f:
                        data = json.load(f)

                    # 回填内存缓存
                    self._memory_cache[key] = {
                        "data": data,
                        "timestamp": time.time(),
                    }

                    logger.debug(f"文件缓存命中: {search_type} '{query[:30]}...'")
                    return data
                else:
                    # 过期，删除
                    cache_file.unlink()
            except Exception as e:
                logger.warning(f"读取缓存文件失败: {e}")
                if cache_file.exists():
                    cache_file.unlink()

        return None

    async def set(self, query: str, search_type: str, data: List[Dict]):
        """
        设置缓存（同时写入内存和文件）

        Args:
            query: 搜索查询
            search_type: 搜索类型
            data: 搜索结果数据
        """
        key = self._make_key(query, search_type)

        # L1: 内存缓存
        self._memory_cache[key] = {
            "data": data,
            "timestamp": time.time(),
        }

        # L2: 文件缓存（异步写入，不阻塞）
        asyncio.create_task(self._write_to_file(key, data))

    async def _write_to_file(self, key: str, data: List[Dict]):
        """异步写入文件缓存"""
        try:
            cache_file = self._get_cache_file_path(key)
            with open(cache_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.warning(f"写入缓存文件失败: {e}")

    async def invalidate(self, query: str, search_type: str):
        """
        使指定缓存失效

        Args:
            query: 搜索查询
            search_type: 搜索类型
        """
        key = self._make_key(query, search_type)

        # 删除内存缓存
        if key in self._memory_cache:
            del self._memory_cache[key]

        # 删除文件缓存
        cache_file = self._get_cache_file_path(key)
        if cache_file.exists():
            cache_file.unlink()

    async def clear_all(self):
        """清空所有缓存"""
        # 清空内存缓存
        self._memory_cache.clear()

        # 清空文件缓存
        for cache_file in self._cache_dir.glob("*.json"):
            try:
                cache_file.unlink()
            except Exception as e:
                logger.warning(f"删除缓存文件失败: {e}")

        logger.info("所有缓存已清空")

    def get_stats(self) -> Dict[str, Any]:
        """获取缓存统计信息"""
        memory_count = len(self._memory_cache)
        file_count = len(list(self._cache_dir.glob("*.json")))

        # 计算内存缓存总大小（近似）
        memory_size = sum(
            len(json.dumps(entry["data"]))
            for entry in self._memory_cache.values()
        )

        return {
            "memory_entries": memory_count,
            "file_entries": file_count,
            "memory_size_bytes": memory_size,
            "cache_dir": str(self._cache_dir),
        }


# 全局缓存实例
_cache_manager: Optional[SearchCacheManager] = None


def get_search_cache_manager() -> SearchCacheManager:
    """获取全局缓存管理器实例"""
    global _cache_manager
    if _cache_manager is None:
        _cache_manager = SearchCacheManager()
    return _cache_manager


async def get_cached_search(query: str, search_type: str) -> Optional[List[Dict]]:
    """
    获取缓存的搜索结果（便捷函数）

    Args:
        query: 搜索查询
        search_type: 搜索类型（theme/topic/lyrics等）

    Returns:
        缓存的结果列表，如果没有则返回None
    """
    return await get_search_cache_manager().get(query, search_type)


async def set_cached_search(query: str, search_type: str, data: List[Dict]):
    """
    设置搜索结果缓存（便捷函数）

    Args:
        query: 搜索查询
        search_type: 搜索类型
        data: 搜索结果数据
    """
    await get_search_cache_manager().set(query, search_type, data)
