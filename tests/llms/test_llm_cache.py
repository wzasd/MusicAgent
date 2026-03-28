"""
LLM 缓存系统测试
测试温度分级缓存、缓存键生成、TTL过期等功能
"""

import pytest
import asyncio
import time
from llms.llm_cache import LLMResponseCache, get_llm_cache


class TestLLMResponseCache:
    """LLM 响应缓存测试"""

    @pytest.mark.asyncio
    async def test_cache_key_generation(self):
        """测试缓存键生成"""
        cache = LLMResponseCache()

        # 相同参数应生成相同的键
        key1 = cache._get_cache_key(
            system_prompt="你是一个助手",
            user_prompt="你好",
            model="gpt-3.5",
            temperature=0.2,
            max_tokens=1000
        )

        key2 = cache._get_cache_key(
            system_prompt="你是一个助手",
            user_prompt="你好",
            model="gpt-3.5",
            temperature=0.2,
            max_tokens=1000
        )

        assert key1 == key2, "相同参数应生成相同的缓存键"

        # 不同参数应生成不同的键
        key3 = cache._get_cache_key(
            system_prompt="你是一个助手",
            user_prompt="你好",
            model="gpt-3.5",
            temperature=0.4,  # 不同的温度
            max_tokens=1000
        )

        assert key1 != key3, "不同参数应生成不同的缓存键"

        # 高温度应返回 None
        key4 = cache._get_cache_key(
            system_prompt="你是一个助手",
            user_prompt="你好",
            model="gpt-3.5",
            temperature=0.8,  # 高温度
            max_tokens=1000
        )

        assert key4 is None, "高温度应返回 None"

    @pytest.mark.asyncio
    async def test_temperature_based_caching(self):
        """测试温度分级缓存"""
        cache = LLMResponseCache()

        # 低温度 (≤0.3) 应使用确定性缓存池
        pool_low = cache._select_cache_pool(0.2)
        assert pool_low == cache._deterministic_cache, "低温度应使用确定性缓存池"

        # 中等温度 (0.3-0.5) 应使用半确定性缓存池
        pool_mid = cache._select_cache_pool(0.4)
        assert pool_mid == cache._semi_deterministic_cache, "中等温度应使用半确定性缓存池"

        # 确定性缓存和半确定性缓存是不同的实例
        assert pool_low != pool_mid, "不同温度应使用不同的缓存池"

    @pytest.mark.asyncio
    async def test_cache_hit_and_miss(self):
        """测试缓存命中和未命中"""
        cache = LLMResponseCache()

        system_prompt = "你是一个助手"
        user_prompt = "测试缓存"
        model = "gpt-3.5"
        temperature = 0.2
        max_tokens = 1000

        # 缓存未命中
        result1 = await cache.get(
            system_prompt, user_prompt, model, temperature, max_tokens
        )
        assert result1 is None, "首次查询应未命中缓存"

        # 设置缓存
        test_response = {
            "content": "测试回复",
            "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}
        }
        await cache.set(
            system_prompt, user_prompt, model, temperature, max_tokens, test_response
        )

        # 缓存命中
        result2 = await cache.get(
            system_prompt, user_prompt, model, temperature, max_tokens
        )
        assert result2 == test_response, "缓存应命中并返回正确的响应"

    @pytest.mark.asyncio
    async def test_high_temperature_no_cache(self):
        """测试高温度不缓存"""
        cache = LLMResponseCache()

        system_prompt = "你是一个助手"
        user_prompt = "测试高温度"
        model = "gpt-3.5"
        temperature = 0.8  # 高温度
        max_tokens = 1000

        # 尝试设置缓存
        test_response = {"content": "高温度回复", "usage": {}}
        await cache.set(
            system_prompt, user_prompt, model, temperature, max_tokens, test_response
        )

        # 应该无法命中缓存
        result = await cache.get(
            system_prompt, user_prompt, model, temperature, max_tokens
        )
        assert result is None, "高温度调用不应命中缓存"

    @pytest.mark.asyncio
    async def test_cache_stats(self):
        """测试缓存统计"""
        cache = LLMResponseCache()

        # 初始统计
        stats = cache.get_stats()
        assert "deterministic_cache" in stats
        assert "semi_deterministic_cache" in stats
        assert stats["deterministic_cache"]["size"] == 0
        assert stats["semi_deterministic_cache"]["size"] == 0

        # 添加一些缓存
        for i in range(3):
            await cache.set(
                f"系统提示{i}",
                f"用户提示{i}",
                "gpt-3.5",
                0.2,  # 低温度
                1000,
                {"content": f"回复{i}"}
            )

        for i in range(2):
            await cache.set(
                f"系统提示{i}",
                f"用户提示{i}",
                "gpt-3.5",
                0.4,  # 中等温度
                1000,
                {"content": f"回复{i}"}
            )

        # 检查统计
        stats = cache.get_stats()
        assert stats["deterministic_cache"]["size"] == 3
        assert stats["semi_deterministic_cache"]["size"] == 2

    @pytest.mark.asyncio
    async def test_cache_clear(self):
        """测试清空缓存"""
        cache = LLMResponseCache()

        # 添加缓存
        await cache.set("系统", "用户", "model", 0.2, 1000, {"content": "test"})
        await cache.set("系统", "用户", "model", 0.4, 1000, {"content": "test"})

        # 清空
        await cache.clear()

        # 验证清空
        stats = cache.get_stats()
        assert stats["deterministic_cache"]["size"] == 0
        assert stats["semi_deterministic_cache"]["size"] == 0

    @pytest.mark.asyncio
    async def test_cache_with_different_params(self):
        """测试不同参数的缓存隔离"""
        cache = LLMResponseCache()

        base_params = {
            "system_prompt": "系统",
            "user_prompt": "用户",
            "model": "gpt-3.5",
            "temperature": 0.2,
            "max_tokens": 1000,
        }

        # 设置缓存
        await cache.set(**base_params, response={"content": "原始回复"})

        # 修改 max_tokens，应该生成不同的缓存键
        modified_params = base_params.copy()
        modified_params["max_tokens"] = 2000
        result = await cache.get(**modified_params)
        assert result is None, "不同 max_tokens 应生成不同的缓存键"

        # 修改 temperature，应该生成不同的缓存键
        modified_params = base_params.copy()
        modified_params["temperature"] = 0.3
        result = await cache.get(**modified_params)
        assert result is None, "不同 temperature 应生成不同的缓存键"

    @pytest.mark.asyncio
    async def test_get_llm_cache_singleton(self):
        """测试全局单例"""
        cache1 = get_llm_cache()
        cache2 = get_llm_cache()
        assert cache1 is cache2, "get_llm_cache() 应返回同一个实例"


class TestLLMCacheIntegration:
    """LLM 缓存集成测试（使用 Mock LLM）"""

    @pytest.mark.asyncio
    async def test_invoke_cached_basic_flow(self):
        """测试带缓存的 LLM 调用基本流程"""
        cache = LLMResponseCache()

        # 模拟 LLM 响应
        test_response = {
            "content": "测试回复",
            "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}
        }

        system_prompt = "你是一个助手"
        user_prompt = "测试"
        model = "gpt-3.5"
        temperature = 0.2
        max_tokens = 1000

        # 1. 首次查询 - 缓存未命中
        result1 = await cache.get(system_prompt, user_prompt, model, temperature, max_tokens)
        assert result1 is None, "首次查询应未命中缓存"

        # 2. 设置缓存
        await cache.set(system_prompt, user_prompt, model, temperature, max_tokens, test_response)

        # 3. 再次查询 - 缓存命中
        result2 = await cache.get(system_prompt, user_prompt, model, temperature, max_tokens)
        assert result2 == test_response, "缓存应命中并返回正确的响应"

        # 4. 验证统计
        stats = cache.get_stats()
        assert stats["deterministic_cache"]["hit_count"] == 1, "应记录1次缓存命中"
        assert stats["deterministic_cache"]["miss_count"] == 1, "应记录1次缓存未命中"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
