"""
Web Search 模块 - 支持多 Provider 的网页搜索

支持的 Provider:
- tavily: Tavily API (需要 API Key)
- duckduckgo: DuckDuckGo (无需 API Key，免费)

用法:
    from tools.web_search import get_web_search

    # 使用默认 provider
    search = get_web_search()
    results = await search.search("周杰伦新歌")

    # 指定 provider
    search = get_web_search(provider="duckduckgo")
    results = await search.search("Taylor Swift latest album")
"""

from typing import List, Dict, Any, Optional
from tools.web_search.base import WebSearchProvider, SearchResult
from tools.web_search.factory import create_web_search, get_web_search, list_providers

__all__ = [
    "WebSearchProvider",
    "SearchResult",
    "create_web_search",
    "get_web_search",
    "list_providers",
]
