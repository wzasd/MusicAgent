"""
DuckDuckGo Web Search Provider

使用 duckduckgo-search 库进行搜索，无需 API Key
"""

import asyncio
from typing import List, Dict, Any, Optional

from tools.web_search.base import WebSearchProvider, SearchResult
from config.logging_config import get_logger

logger = get_logger(__name__)


class DuckDuckGoProvider(WebSearchProvider):
    """DuckDuckGo 搜索 Provider

    特点:
    - 无需 API Key，完全免费
    - 支持文本搜索
    - 速率限制较严格（建议间隔 1-2 秒）
    """

    name = "duckduckgo"

    def __init__(self, max_results: int = 10, region: str = "wt-wt", **kwargs):
        """
        Args:
            max_results: 每次搜索最大结果数
            region: 区域设置 (wt-wt=全球, cn-zh=中国, us-en=美国等)
            **kwargs: 其他参数
        """
        super().__init__(**kwargs)
        self.max_results = max_results
        self.region = region
        self._last_search_time = 0
        self._min_interval = 1.0  # 最小请求间隔（秒）

    async def _rate_limit(self):
        """简单的速率限制"""
        import time
        now = time.time()
        elapsed = now - self._last_search_time
        if elapsed < self._min_interval:
            await asyncio.sleep(self._min_interval - elapsed)
        self._last_search_time = time.time()

    async def search(
        self,
        query: str,
        top_k: int = 5,
        include_answer: bool = False,
        **kwargs
    ) -> Dict[str, Any]:
        """执行 DuckDuckGo 搜索

        Args:
            query: 搜索查询
            top_k: 返回结果数量
            include_answer: 是否尝试获取即时答案（DuckDuckGo 的抽象答案）
            **kwargs: 额外参数
                - region: 覆盖默认区域设置
                - time_range: 时间范围 (d=天, w=周, m=月, y=年)

        Returns:
            标准格式的搜索结果
        """
        await self._rate_limit()

        try:
            # 导入 ddgs 库 (新版 duckduckgo-search)
            from ddgs import DDGS

            region = kwargs.get("region", self.region)
            time_range = kwargs.get("time_range")

            # 在线程池中执行同步的 DDGS 调用
            loop = asyncio.get_event_loop()

            ddgs = DDGS()
            # 执行文本搜索
            results = await loop.run_in_executor(
                None,
                lambda: list(ddgs.text(
                    query,
                    max_results=max(top_k, self.max_results),
                    region=region,
                    timelimit=time_range,
                ))
            )

            # 尝试获取即时答案
            answer = ""
            if include_answer:
                try:
                    # DuckDuckGo 的 answers 功能
                    answer_results = await loop.run_in_executor(
                        None,
                        lambda: list(ddgs.answers(query))
                    )
                    if answer_results:
                        answer = answer_results[0].get("text", "")
                except Exception as e:
                    logger.debug(f"DuckDuckGo 答案获取失败: {e}")

            # 转换为标准格式
            search_results = []
            for r in results[:top_k]:
                # 提取域名
                url = r.get("href", "")
                source = self._extract_domain(url)

                search_results.append(SearchResult(
                    title=r.get("title", ""),
                    url=url,
                    content=r.get("body", ""),
                    source=source,
                    raw_data=r
                ))

            return {
                "results": search_results,
                "answer": answer if answer else None,
                "query": query,
                "total_results": len(search_results),
                "provider": self.name,
            }

        except ImportError:
            logger.error("ddgs 库未安装，请运行: pip install ddgs")
            raise
        except Exception as e:
            logger.error(f"DuckDuckGo 搜索失败: {e}")
            return {
                "results": [],
                "answer": None,
                "query": query,
                "total_results": 0,
                "provider": self.name,
                "error": str(e),
            }

    async def health_check(self) -> bool:
        """检查 DuckDuckGo 是否可用"""
        try:
            result = await self.search("test", top_k=1)
            return len(result.get("results", [])) > 0
        except Exception as e:
            logger.error(f"DuckDuckGo 健康检查失败: {e}")
            return False

    def _extract_domain(self, url: str) -> str:
        """从 URL 提取域名"""
        try:
            from urllib.parse import urlparse
            parsed = urlparse(url)
            domain = parsed.netloc
            # 移除 www. 前缀
            if domain.startswith("www."):
                domain = domain[4:]
            return domain
        except:
            return url
