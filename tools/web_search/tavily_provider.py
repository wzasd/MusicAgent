"""
Tavily Web Search Provider

Tavily 是一个专为 AI 应用设计的搜索 API，提供结构化结果和 AI 摘要
"""

import aiohttp
from typing import List, Dict, Any, Optional

from tools.web_search.base import WebSearchProvider, SearchResult
from config.logging_config import get_logger

logger = get_logger(__name__)


class TavilyProvider(WebSearchProvider):
    """Tavily 搜索 Provider

    特点:
    - 专为 AI 应用优化
    - 提供 AI 生成的答案摘要
    - 结构化搜索结果
    - 需要 API Key
    """

    name = "tavily"
    API_URL = "https://api.tavily.com/search"

    def __init__(self, api_key: Optional[str] = None, **kwargs):
        """
        Args:
            api_key: Tavily API Key，如果不提供则从 settings 读取
            **kwargs: 其他参数
                - search_depth: basic 或 advanced
                - include_domains: 指定包含的域名列表
                - exclude_domains: 指定排除的域名列表
        """
        super().__init__(**kwargs)
        self._api_key = api_key
        self.search_depth = kwargs.get("search_depth", "basic")
        self.include_domains = kwargs.get("include_domains")
        self.exclude_domains = kwargs.get("exclude_domains")

    def _get_api_key(self) -> str:
        """获取 API Key"""
        if self._api_key:
            return self._api_key

        try:
            from config.settings_loader import load_settings_from_json
            settings = load_settings_from_json()
            return settings.get("TAILYAPI_API_KEY", "")
        except Exception as e:
            logger.warning(f"无法加载 settings: {e}")
            return ""

    async def search(
        self,
        query: str,
        top_k: int = 5,
        include_answer: bool = True,
        **kwargs
    ) -> Dict[str, Any]:
        """执行 Tavily 搜索

        Args:
            query: 搜索查询
            top_k: 返回结果数量
            include_answer: 是否包含 AI 生成的答案
            **kwargs: 额外参数
                - search_depth: basic 或 advanced
                - time_range: 时间范围 (day, week, month, year)

        Returns:
            标准格式的搜索结果
        """
        api_key = self._get_api_key()
        if not api_key:
            logger.error("Tavily API Key 未配置")
            return {
                "results": [],
                "answer": None,
                "query": query,
                "total_results": 0,
                "provider": self.name,
                "error": "API Key not configured",
            }

        try:
            payload = {
                "api_key": api_key,
                "query": query,
                "max_results": top_k,
                "include_answer": include_answer,
                "search_depth": kwargs.get("search_depth", self.search_depth),
            }

            # 添加可选参数
            if self.include_domains:
                payload["include_domains"] = self.include_domains
            if self.exclude_domains:
                payload["exclude_domains"] = self.exclude_domains
            if kwargs.get("time_range"):
                payload["time_range"] = kwargs["time_range"]

            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.API_URL,
                    json=payload,
                    headers={"Content-Type": "application/json"},
                    timeout=aiohttp.ClientTimeout(total=30),
                ) as resp:
                    if resp.status != 200:
                        error_text = await resp.text()
                        logger.error(f"Tavily 请求失败: {resp.status}, {error_text}")
                        return {
                            "results": [],
                            "answer": None,
                            "query": query,
                            "total_results": 0,
                            "provider": self.name,
                            "error": f"HTTP {resp.status}: {error_text}",
                        }

                    data = await resp.json()

            # 转换为标准格式
            results = []
            for r in data.get("results", []):
                results.append(SearchResult(
                    title=r.get("title", ""),
                    url=r.get("url", ""),
                    content=r.get("content", ""),
                    source=r.get("source", self._extract_domain(r.get("url", ""))),
                    score=r.get("score"),
                    raw_data=r
                ))

            return {
                "results": results,
                "answer": data.get("answer") if include_answer else None,
                "query": query,
                "total_results": len(results),
                "provider": self.name,
                "raw_response": data,  # 保留原始响应供高级使用
            }

        except Exception as e:
            logger.error(f"Tavily 搜索失败: {e}")
            return {
                "results": [],
                "answer": None,
                "query": query,
                "total_results": 0,
                "provider": self.name,
                "error": str(e),
            }

    async def health_check(self) -> bool:
        """检查 Tavily 是否可用"""
        api_key = self._get_api_key()
        if not api_key:
            return False

        try:
            result = await self.search("test", top_k=1, include_answer=False)
            return "error" not in result
        except Exception as e:
            logger.error(f"Tavily 健康检查失败: {e}")
            return False

    def _extract_domain(self, url: str) -> str:
        """从 URL 提取域名"""
        try:
            from urllib.parse import urlparse
            parsed = urlparse(url)
            domain = parsed.netloc
            if domain.startswith("www."):
                domain = domain[4:]
            return domain
        except:
            return url
