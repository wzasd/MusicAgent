"""
Web Search Provider 工厂
"""

from typing import Optional, Dict, Any, Type

from tools.web_search.base import WebSearchProvider
from tools.web_search.tavily_provider import TavilyProvider
from tools.web_search.duckduckgo_provider import DuckDuckGoProvider
from config.logging_config import get_logger

logger = get_logger(__name__)

# Provider 注册表
_PROVIDERS: Dict[str, Type[WebSearchProvider]] = {
    "tavily": TavilyProvider,
    "duckduckgo": DuckDuckGoProvider,
}

# 全局实例缓存
_instances: Dict[str, WebSearchProvider] = {}


def create_web_search(
    provider: str = "tavily",
    **kwargs
) -> WebSearchProvider:
    """创建 Web Search Provider 实例

    Args:
        provider: Provider 名称 (tavily, duckduckgo)
        **kwargs: Provider 特定配置

    Returns:
        WebSearchProvider 实例

    Raises:
        ValueError: 如果 provider 不存在
    """
    provider = provider.lower()

    if provider not in _PROVIDERS:
        available = ", ".join(_PROVIDERS.keys())
        raise ValueError(f"未知的 Web Search Provider: {provider}. 可用选项: {available}")

    provider_class = _PROVIDERS[provider]
    return provider_class(**kwargs)


def get_web_search(
    provider: Optional[str] = None,
    use_fallback: bool = True,
    **kwargs
) -> WebSearchProvider:
    """获取 Web Search Provider 实例（带缓存和自动回退）

    Args:
        provider: Provider 名称，None 则自动选择
        use_fallback: 如果指定 provider 不可用，是否自动回退
        **kwargs: Provider 配置

    Returns:
        WebSearchProvider 实例
    """
    global _instances

    # 自动选择 provider
    if provider is None:
        provider = _auto_select_provider()

    provider = provider.lower()
    cache_key = f"{provider}:{hash(str(kwargs))}"

    # 检查缓存
    if cache_key in _instances:
        return _instances[cache_key]

    try:
        instance = create_web_search(provider, **kwargs)
        _instances[cache_key] = instance
        return instance
    except Exception as e:
        if use_fallback and provider != "duckduckgo":
            logger.warning(f"{provider} 初始化失败，回退到 DuckDuckGo: {e}")
            return get_web_search("duckduckgo", use_fallback=False, **kwargs)
        raise


def _auto_select_provider() -> str:
    """自动选择最佳的 provider"""
    try:
        from config.settings_loader import load_settings_from_json
        settings = load_settings_from_json()

        # 如果有 Tavily API Key，优先使用
        if settings.get("TAILYAPI_API_KEY"):
            return "tavily"
    except:
        pass

    # 默认使用 DuckDuckGo（免费）
    return "duckduckgo"


def list_providers() -> Dict[str, str]:
    """列出所有可用的 provider"""
    return {
        "tavily": "Tavily API - 专为 AI 优化，需要 API Key",
        "duckduckgo": "DuckDuckGo - 免费，无需 API Key",
    }


def clear_cache():
    """清除全局实例缓存"""
    global _instances
    _instances = {}
