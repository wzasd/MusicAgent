"""
缓存工具模块
提供简单的内存缓存实现，支持 TTL 和 LRU 淘汰
"""

import hashlib
import time
import asyncio
from typing import Dict, List, Optional, Any
from config.logging_config import get_logger

logger = get_logger(__name__)


class SimpleCache:
    """Simple in-memory cache with TTL and LRU eviction"""

    def __init__(self, max_size: int = 10000, ttl: int = 3600):
        """
        初始化缓存

        Args:
            max_size: 最大缓存条目数
            ttl: 缓存过期时间（秒），默认 1 小时
        """
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._max_size = max_size
        self._ttl = ttl
        self._lock = asyncio.Lock()

        # 统计信息
        self._hit_count = 0
        self._miss_count = 0

    def _hash_key(self, *args, **kwargs) -> str:
        """生成缓存键的哈希值"""
        key_str = "|".join(str(arg) for arg in args)
        if kwargs:
            key_str += "|" + "|".join(f"{k}={v}" for k, v in sorted(kwargs.items()))
        return hashlib.md5(key_str.encode()).hexdigest()

    async def get(self, key: str) -> Optional[Any]:
        """
        获取缓存值

        Args:
            key: 缓存键

        Returns:
            缓存值，如果不存在或已过期则返回 None
        """
        async with self._lock:
            if key in self._cache:
                entry = self._cache[key]
                # 检查是否过期
                if time.time() - entry["timestamp"] < self._ttl:
                    self._hit_count += 1
                    logger.debug(f"Cache hit: {key[:16]}...")
                    return entry["value"]
                else:
                    # 过期，删除
                    del self._cache[key]
                    logger.debug(f"Cache expired: {key[:16]}...")

            self._miss_count += 1
            return None

    async def set(self, key: str, value: Any):
        """
        设置缓存值

        Args:
            key: 缓存键
            value: 缓存值
        """
        async with self._lock:
            # 如果缓存已满，执行 LRU 淘汰
            if len(self._cache) >= self._max_size:
                self._evict_lru()

            self._cache[key] = {
                "value": value,
                "timestamp": time.time()
            }
            logger.debug(f"Cache set: {key[:16]}...")

    def _evict_lru(self):
        """LRU 淘汰：移除最旧的 10% 条目"""
        if not self._cache:
            return

        # 按时间戳排序
        sorted_keys = sorted(
            self._cache.keys(),
            key=lambda k: self._cache[k]["timestamp"]
        )

        # 移除最旧的 10%
        num_to_remove = max(1, len(sorted_keys) // 10)
        for key_to_remove in sorted_keys[:num_to_remove]:
            del self._cache[key_to_remove]

        logger.info(f"LRU eviction: removed {num_to_remove} entries")

    def get_hit_rate(self) -> float:
        """获取缓存命中率"""
        total = self._hit_count + self._miss_count
        if total == 0:
            return 0.0
        return self._hit_count / total

    def get_stats(self) -> Dict[str, Any]:
        """获取缓存统计信息"""
        return {
            "size": len(self._cache),
            "max_size": self._max_size,
            "hit_count": self._hit_count,
            "miss_count": self._miss_count,
            "hit_rate": self.get_hit_rate(),
            "ttl_seconds": self._ttl,
        }

    async def clear(self):
        """清空缓存"""
        async with self._lock:
            self._cache.clear()
            self._hit_count = 0
            self._miss_count = 0
            logger.info("Cache cleared")
