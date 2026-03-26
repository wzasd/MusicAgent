"""
Web Search Provider 抽象基类
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Dict, Any, Optional


@dataclass
class SearchResult:
    """搜索结果数据结构"""
    title: str
    url: str
    content: str  # 摘要/内容片段
    source: str   # 来源网站域名
    score: Optional[float] = None  # 相关性分数（如果有）
    raw_data: Optional[Dict[str, Any]] = None  # 原始数据


class WebSearchProvider(ABC):
    """Web Search Provider 抽象基类"""

    name: str = "base"

    def __init__(self, **kwargs):
        """初始化 Provider

        Args:
            **kwargs: Provider 特定配置参数
        """
        self.config = kwargs

    @abstractmethod
    async def search(
        self,
        query: str,
        top_k: int = 5,
        include_answer: bool = False,
        **kwargs
    ) -> Dict[str, Any]:
        """执行搜索

        Args:
            query: 搜索查询
            top_k: 返回结果数量
            include_answer: 是否包含 AI 生成的答案摘要
            **kwargs: 额外参数

        Returns:
            {
                "results": List[SearchResult],
                "answer": Optional[str],  # AI 摘要（如果支持）
                "query": str,  # 实际执行的查询
                "total_results": int,
                "provider": str,  # provider 名称
            }
        """
        pass

    @abstractmethod
    async def health_check(self) -> bool:
        """检查 provider 是否可用"""
        pass

    def format_for_llm(self, search_response: Dict[str, Any]) -> str:
        """将搜索结果格式化为 LLM 可用的文本

        Args:
            search_response: search() 返回的结果

        Returns:
            格式化后的文本
        """
        results = search_response.get("results", [])
        answer = search_response.get("answer", "")

        lines = []
        if answer:
            lines.append(f"搜索摘要: {answer}\n")

        lines.append("相关搜索结果:")
        for i, r in enumerate(results[:10], 1):
            lines.append(f"[{i}] {r.title}")
            lines.append(f"    来源: {r.source}")
            lines.append(f"    内容: {r.content[:300]}...")
            lines.append("")

        return "\n".join(lines)
