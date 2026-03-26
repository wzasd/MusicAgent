"""
影视主题曲搜索引擎
通过 Tavily Web Search 搜索电视剧/电影的主题曲、片头曲、片尾曲和插曲
"""

import asyncio
import json
import re
import time
from typing import Any, Dict, List, Optional

from config.logging_config import get_logger
from tools.multilingual_search import MultilingualSearchBuilder
from tools.web_search_cache import get_cached_search, set_cached_search

logger = get_logger(__name__)


class ThemeSearchEngine:
    """影视主题曲搜索引擎（基于 Web Search）"""

    def __init__(self):
        self._api_key: Optional[str] = None

    def _get_api_key(self) -> Optional[str]:
        """懒加载获取 API Key"""
        if self._api_key is None:
            from config.settings_loader import load_settings_from_json
            settings = load_settings_from_json()
            self._api_key = settings.get("TAILYAPI_API_KEY", "")
        return self._api_key

    def _build_search_queries(self, title: str, country: Optional[str]) -> List[Dict]:
        """
        构建多个搜索查询（不同角度），用于并行搜索
        """
        queries = []
        country_prefix = country or ""

        # 查询1: 综合搜索（使用多语言构建器）
        base_params = MultilingualSearchBuilder.build_tavily_params(
            "theme", title=title, country=country_prefix
        )
        queries.append(base_params)

        # 查询2: 针对OST的搜索
        queries.append({
            "query": f'{country_prefix} "{title}" OST soundtrack 原声带 所有歌曲',
            "search_depth": "advanced",
            "max_results": 8,
            "include_answer": True,
        })

        # 查询3: 针对维基百科的搜索
        queries.append({
            "query": f'"{title}" wikipedia 主题曲 音乐',
            "search_depth": "advanced",
            "max_results": 5,
            "include_answer": True,
        })

        return queries

    async def _tavily_search_single(
        self,
        session: Any,
        api_key: str,
        params: Dict,
        timeout: float = 10.0
    ) -> Dict:
        """执行单个 Tavily 搜索"""
        import aiohttp

        try:
            async with session.post(
                "https://api.tavily.com/search",
                json={
                    "api_key": api_key,
                    **params,
                },
                headers={"Content-Type": "application/json"},
                timeout=aiohttp.ClientTimeout(total=timeout),
            ) as resp:
                if resp.status == 200:
                    return await resp.json()
                else:
                    logger.warning(f"Tavily 请求失败: {resp.status}")
                    return {}
        except Exception as e:
            logger.warning(f"Tavily 搜索异常: {e}")
            return {}

    async def _search_parallel_with_early_return(
        self,
        title: str,
        country: Optional[str],
        max_timeout: float = 6.0,
        min_results: int = 2
    ) -> List[Dict]:
        """
        并行搜索，满足条件时提前返回

        Args:
            title: 影视剧名称
            country: 国家/地区
            max_timeout: 最大等待时间（秒）
            min_results: 最小结果数，达到后提前返回

        Returns:
            合并后的搜索结果列表
        """
        import aiohttp

        api_key = self._get_api_key()
        if not api_key:
            logger.warning("Tavily API Key 未配置")
            return []

        queries = self._build_search_queries(title, country)
        logger.info(f"并行启动 {len(queries)} 个搜索查询")

        start_time = time.time()
        all_results = []
        completed_count = 0

        async with aiohttp.ClientSession() as session:
            # 创建所有搜索任务
            pending_tasks = [
                asyncio.create_task(
                    self._tavily_search_single(session, api_key, q, timeout=8.0),
                    name=f"search_{i}"
                )
                for i, q in enumerate(queries)
            ]

            # 循环等待任务完成，检查是否满足提前返回条件
            while pending_tasks and (time.time() - start_time) < max_timeout:
                # 等待任意任务完成（带短超时）
                done, pending_tasks = await asyncio.wait(
                    pending_tasks,
                    return_when=asyncio.FIRST_COMPLETED,
                    timeout=0.5
                )

                for task in done:
                    try:
                        result = task.result()
                        if result and result.get("results"):
                            all_results.extend(result.get("results", []))
                            completed_count += 1
                            logger.debug(f"搜索任务完成，当前共 {len(all_results)} 条结果")
                    except Exception as e:
                        logger.warning(f"搜索任务异常: {e}")

                # 检查是否满足提前返回条件
                if len(all_results) >= min_results * 3:  # 每个查询平均返回3条
                    logger.info(f"提前返回：已收集 {len(all_results)} 条结果")
                    # 取消剩余任务
                    for t in pending_tasks:
                        t.cancel()
                    break

            # 取消剩余未完成的任务
            for t in pending_tasks:
                t.cancel()
                try:
                    await t
                except asyncio.CancelledError:
                    pass

        elapsed = time.time() - start_time
        logger.info(f"并行搜索完成：共 {len(all_results)} 条结果，耗时 {elapsed:.2f}s")
        return all_results

    async def search_by_title(self, title: str, country: Optional[str] = None, top_k: int = 5) -> List[Dict[str, Any]]:
        """
        搜索影视作品的主题曲/插曲（支持并行搜索+提前返回）

        Args:
            title: 影视剧名称（如"权力的游戏"、"霸王别姬"）
            country: 可选，国家/地区（如"泰国"、"韩国"、"美国"）
            top_k: 返回结果数量

        Returns:
            歌曲列表，source="theme_web_search"
        """
        # 先检查缓存
        cache_key = f"{title}:{country or ''}"
        cached = await get_cached_search(cache_key, "theme")
        if cached:
            logger.info(f"影视主题曲搜索缓存命中: '{title}'")
            return cached[:top_k]

        logger.info(f"影视主题曲搜索: '{title}' country='{country}'")

        try:
            # 并行搜索（带提前返回）
            search_results = await self._search_parallel_with_early_return(
                title, country, max_timeout=6.0, min_results=2
            )

            if not search_results:
                logger.warning(f"未找到 '{title}' 的任何搜索结果")
                return []

            # 合并并去重结果
            unique_results = self._deduplicate_results(search_results)

            # 构建用于 LLM 提取的内容
            answer = ""
            for r in unique_results[:3]:  # 取前3个结果的答案
                if r.get("answer"):
                    answer = r.get("answer")
                    break

            snippets = "\n".join(
                f"[{i+1}] {r.get('content', '')[:300]}"
                for i, r in enumerate(unique_results[:10])
            )
            combined = f"搜索答案: {answer}\n\n相关内容:\n{snippets}".strip()

            if not combined:
                return []

            logger.info(f"合并搜索结果: {len(unique_results)} 条唯一来源")

            # 用 LLM 从搜索结果中提取结构化歌曲列表
            from llms.siliconflow_llm import SiliconFlowLLM
            from prompts.music_prompts import THEME_SONG_EXTRACTION_PROMPT
            llm = SiliconFlowLLM()

            extract_prompt = THEME_SONG_EXTRACTION_PROMPT.format(
                title=title,
                search_results=combined,
                top_k=top_k
            )
            response = llm.invoke_text(
                "你是专业的音乐信息提取助手，擅长从搜索结果中准确提取影视歌曲信息。只使用给定的搜索结果，不要凭记忆猜测。",
                extract_prompt,
            )

            # 解析 JSON 数组
            json_match = re.search(r'\[.*?\]', response, re.DOTALL)
            if not json_match:
                logger.warning("主题曲搜索结果解析失败")
                return []

            songs_raw = json.loads(json_match.group())
            results = []
            for item in songs_raw:
                song_title = item.get("title")
                artist = item.get("artist")
                confidence = float(item.get("confidence", 0))
                song_type = item.get("type", "主题曲")

                if not song_title or confidence < 0.3:
                    continue

                results.append({
                    "title": song_title,
                    "artist": artist or "未知艺术家",
                    "genre": [],
                    "mood": [],
                    "similarity_score": confidence,
                    "match_type": "theme_web_search",
                    "source": "theme_web_search",
                    "theme_type": song_type,
                    "from_title": title,
                    "low_confidence": confidence < 0.7,
                })

            logger.info(f"主题曲搜索结果: {len(results)} 首 (来自《{title}》)")

            # 保存到缓存
            await set_cached_search(cache_key, "theme", results)

            return results[:top_k]

        except Exception as e:
            logger.error(f"影视主题曲搜索失败: {e}")
            return []

    def _deduplicate_results(self, results: List[Dict]) -> List[Dict]:
        """根据URL去重搜索结果"""
        seen_urls = set()
        unique = []
        for r in results:
            url = r.get("url", "")
            if url and url not in seen_urls:
                seen_urls.add(url)
                unique.append(r)
            elif not url:
                unique.append(r)
        return unique


# 全局单例
_theme_search_engine: Optional[ThemeSearchEngine] = None


def get_theme_search_engine() -> ThemeSearchEngine:
    global _theme_search_engine
    if _theme_search_engine is None:
        _theme_search_engine = ThemeSearchEngine()
    return _theme_search_engine
