"""
LLM 响应缓存模块
基于温度的分级缓存系统，减少重复 LLM 调用
"""

import hashlib
from typing import Optional, Dict, Any
from utils.cache import SimpleCache
from config.logging_config import get_logger

logger = get_logger(__name__)


class LLMResponseCache:
    """LLM 响应缓存管理器 - 基于温度的分级缓存"""

    # 缓存版本号，用于缓存键生成
    CACHE_VERSION = "v1"

    # 温度阈值配置
    MAX_CACHEABLE_TEMPERATURE = 0.5  # 高于此温度不缓存
    DETERMINISTIC_THRESHOLD = 0.3    # 低于此温度长期缓存

    def __init__(self):
        """初始化两个缓存池"""
        # 确定性缓存池（低温度调用，长期缓存）
        self._deterministic_cache = SimpleCache(
            max_size=5000,
            ttl=86400 * 7  # 7天
        )

        # 半确定性缓存池（中等温度调用，短期缓存）
        self._semi_deterministic_cache = SimpleCache(
            max_size=2500,
            ttl=3600  # 1小时
        )

        logger.info(
            f"LLM缓存初始化完成 - "
            f"确定性缓存TTL: 7天 (温度≤{self.DETERMINISTIC_THRESHOLD}), "
            f"半确定性缓存TTL: 1小时 (温度{self.DETERMINISTIC_THRESHOLD}-{self.MAX_CACHEABLE_TEMPERATURE})"
        )

    async def get(
        self,
        system_prompt: str,
        user_prompt: str,
        model: str,
        temperature: float,
        max_tokens: int,
        **kwargs
    ) -> Optional[Dict[str, Any]]:
        """
        尝试从缓存获取 LLM 响应

        Args:
            system_prompt: 系统提示词
            user_prompt: 用户提示词
            model: 模型名称
            temperature: 温度参数
            max_tokens: 最大 token 数
            **kwargs: 其他参数

        Returns:
            缓存的响应（字典格式），如果未命中或不可缓存则返回 None
        """
        # 检查是否可缓存
        if temperature > self.MAX_CACHEABLE_TEMPERATURE:
            logger.debug(f"温度 {temperature} > {self.MAX_CACHEABLE_TEMPERATURE}，跳过缓存")
            return None

        # 生成缓存键
        cache_key = self._get_cache_key(
            system_prompt, user_prompt, model, temperature, max_tokens, **kwargs
        )
        if cache_key is None:
            return None

        # 选择缓存池
        cache_pool = self._select_cache_pool(temperature)

        # 尝试获取缓存
        cached_response = await cache_pool.get(cache_key)

        if cached_response:
            pool_name = "确定性" if temperature <= self.DETERMINISTIC_THRESHOLD else "半确定性"
            logger.info(f"✅ LLM缓存命中 ({pool_name}池, 温度={temperature})")
            return cached_response

        return None

    async def set(
        self,
        system_prompt: str,
        user_prompt: str,
        model: str,
        temperature: float,
        max_tokens: int,
        response: Dict[str, Any],
        **kwargs
    ):
        """
        缓存 LLM 响应

        Args:
            system_prompt: 系统提示词
            user_prompt: 用户提示词
            model: 模型名称
            temperature: 温度参数
            max_tokens: 最大 token 数
            response: LLM 响应（字典格式）
            **kwargs: 其他参数
        """
        # 检查是否可缓存
        if temperature > self.MAX_CACHEABLE_TEMPERATURE:
            logger.debug(f"温度 {temperature} > {self.MAX_CACHEABLE_TEMPERATURE}，不缓存")
            return

        # 生成缓存键
        cache_key = self._get_cache_key(
            system_prompt, user_prompt, model, temperature, max_tokens, **kwargs
        )
        if cache_key is None:
            return

        # 选择缓存池并缓存
        cache_pool = self._select_cache_pool(temperature)
        await cache_pool.set(cache_key, response)

        pool_name = "确定性" if temperature <= self.DETERMINISTIC_THRESHOLD else "半确定性"
        logger.info(f"💾 LLM响应已缓存 ({pool_name}池, 温度={temperature})")

    def _get_cache_key(
        self,
        system_prompt: str,
        user_prompt: str,
        model: str,
        temperature: float,
        max_tokens: int,
        **kwargs
    ) -> Optional[str]:
        """
        生成缓存键（基于所有影响输出的参数）

        Args:
            system_prompt: 系统提示词
            user_prompt: 用户提示词
            model: 模型名称
            temperature: 温度参数
            max_tokens: 最大 token 数
            **kwargs: 其他参数

        Returns:
            SHA256 哈希的缓存键，如果不可缓存则返回 None
        """
        # 高温度不缓存
        if temperature > self.MAX_CACHEABLE_TEMPERATURE:
            return None

        # 归一化 prompt（去除多余空格）
        normalized_system = ' '.join(system_prompt.split())
        normalized_user = ' '.join(user_prompt.split())

        # 构建键的部分
        key_parts = [
            self.CACHE_VERSION,
            model,
            normalized_system,
            normalized_user,
            f"t:{temperature}",
            f"m:{max_tokens}",
        ]

        # 添加其他影响输出的参数（如 top_p, frequency_penalty 等）
        for k in sorted(kwargs.keys()):
            if k in ['top_p', 'frequency_penalty', 'presence_penalty', 'stop']:
                key_parts.append(f"{k}:{kwargs[k]}")

        # 使用 SHA256 哈希
        key_str = "|".join(key_parts)
        cache_key = hashlib.sha256(key_str.encode('utf-8')).hexdigest()

        return cache_key

    def _select_cache_pool(self, temperature: float) -> SimpleCache:
        """
        根据温度选择合适的缓存池

        Args:
            temperature: 温度参数

        Returns:
            对应的缓存池
        """
        if temperature <= self.DETERMINISTIC_THRESHOLD:
            return self._deterministic_cache
        else:
            return self._semi_deterministic_cache

    def get_stats(self) -> Dict[str, Any]:
        """
        获取缓存统计信息

        Returns:
            包含两个缓存池统计信息的字典
        """
        deterministic_stats = self._deterministic_cache.get_stats()
        semi_deterministic_stats = self._semi_deterministic_cache.get_stats()

        return {
            "deterministic_cache": deterministic_stats,
            "semi_deterministic_cache": semi_deterministic_stats,
            "config": {
                "max_cacheable_temperature": self.MAX_CACHEABLE_TEMPERATURE,
                "deterministic_threshold": self.DETERMINISTIC_THRESHOLD,
            }
        }

    async def clear(self):
        """清空所有缓存"""
        await self._deterministic_cache.clear()
        await self._semi_deterministic_cache.clear()
        logger.info("所有LLM缓存已清空")


# 全局单例
_llm_cache_instance: Optional[LLMResponseCache] = None


def get_llm_cache() -> LLMResponseCache:
    """获取 LLM 缓存单例"""
    global _llm_cache_instance
    if _llm_cache_instance is None:
        _llm_cache_instance = LLMResponseCache()
    return _llm_cache_instance
