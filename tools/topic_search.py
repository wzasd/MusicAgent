"""
话题歌曲搜索引擎
通过 Tavily Web Search 搜索与特定话题相关的歌曲（如：关于天空的歌、关于雨的 Lady Gaga 歌曲）
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


class TopicSearchEngine:
    """话题歌曲搜索引擎（基于 Web Search）"""

    def __init__(self):
        self._api_key: Optional[str] = None

    def _get_api_key(self) -> Optional[str]:
        """懒加载获取 API Key"""
        if self._api_key is None:
            from config.settings_loader import load_settings_from_json
            settings = load_settings_from_json()
            self._api_key = settings.get("TAILYAPI_API_KEY", "")
        return self._api_key

    def _build_search_queries(self, topic: str, artist: Optional[str], genre: Optional[str]) -> List[Dict]:
        """
        构建多个搜索查询（不同角度），用于并行搜索
        """
        queries = []

        # 查询1: 使用多语言构建器的标准查询
        base_params = MultilingualSearchBuilder.build_tavily_params(
            "topic", topic=topic, artist=artist or "", genre=genre or ""
        )
        queries.append(base_params)

        # 查询2: 歌曲推荐列表形式
        if artist:
            queries.append({
                "query": f'{artist} best songs about {topic} list',
                "search_depth": "advanced",
                "max_results": 8,
                "include_answer": True,
            })
        else:
            queries.append({
                "query": f'关于{topic}的歌曲推荐 list playlist',
                "search_depth": "advanced",
                "max_results": 8,
                "include_answer": True,
            })

        # 查询3: 歌词相关内容
        if not artist:
            queries.append({
                "query": f'"{topic}" 歌词 歌曲 推荐',
                "search_depth": "advanced",
                "max_results": 6,
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
        topic: str,
        artist: Optional[str],
        genre: Optional[str],
        max_timeout: float = 6.0,
        min_results: int = 2
    ) -> List[Dict]:
        """
        并行搜索，满足条件时提前返回
        """
        import aiohttp

        api_key = self._get_api_key()
        if not api_key:
            logger.warning("Tavily API Key 未配置")
            return []

        queries = self._build_search_queries(topic, artist, genre)
        logger.info(f"并行启动 {len(queries)} 个话题搜索查询")

        start_time = time.time()
        all_results = []

        async with aiohttp.ClientSession() as session:
            # 创建所有搜索任务
            pending_tasks = [
                asyncio.create_task(
                    self._tavily_search_single(session, api_key, q, timeout=8.0),
                    name=f"search_{i}"
                )
                for i, q in enumerate(queries)
            ]

            # 循环等待任务完成
            while pending_tasks and (time.time() - start_time) < max_timeout:
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
                            logger.debug(f"话题搜索任务完成，当前共 {len(all_results)} 条结果")
                    except Exception as e:
                        logger.warning(f"话题搜索任务异常: {e}")

                # 检查是否满足提前返回条件
                if len(all_results) >= min_results * 3:
                    logger.info(f"话题搜索提前返回：已收集 {len(all_results)} 条结果")
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
        logger.info(f"话题并行搜索完成：共 {len(all_results)} 条结果，耗时 {elapsed:.2f}s")
        return all_results

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

    async def search_by_topic(
        self,
        topic: str,
        artist: Optional[str] = None,
        genre: Optional[str] = None,
        top_k: int = 5,
    ) -> List[Dict[str, Any]]:
        """
        搜索与话题相关的歌曲

        Args:
            topic:  话题关键词（如"天空"、"雨"、"思念"）
            artist: 可选，限定艺术家（如"Lady Gaga"）
            genre:  可选，限定流派（如"流行"、"pop"）
            top_k:  返回结果数量

        Returns:
            歌曲列表，source="topic_web_search"
        """
        # 先检查缓存
        cache_key = f"{topic}:{artist or ''}:{genre or ''}"
        cached = await get_cached_search(cache_key, "topic")
        if cached:
            logger.info(f"话题歌曲搜索缓存命中: topic='{topic}'")
            return cached[:top_k]

        logger.info(f"话题歌曲搜索: topic='{topic}' artist='{artist}' genre='{genre}'")

        try:
            # 并行搜索（带提前返回）
            search_results = await self._search_parallel_with_early_return(
                topic, artist, genre, max_timeout=6.0, min_results=2
            )

            if not search_results:
                logger.warning(f"未找到话题 '{topic}' 的任何搜索结果")
                return []

            # 合并并去重结果
            unique_results = self._deduplicate_results(search_results)

            # 构建用于 LLM 提取的内容
            answer = ""
            for r in unique_results[:3]:
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

            logger.info(f"Tavily 返回答案: {answer[:120]}")

            # 构建 LLM 提取 prompt
            constraint_parts = []
            if artist:
                constraint_parts.append(f"必须是 {artist} 的歌曲")
            if genre:
                constraint_parts.append(f"风格应为 {genre}")
            constraint = f" ({', '.join(constraint_parts)})" if constraint_parts else ""

            from llms.siliconflow_llm import SiliconFlowLLM
            llm = SiliconFlowLLM()
            extract_prompt = (
                f'根据以下网络搜索结果，提取与话题"{topic}"相关的歌曲{constraint}。\n\n'
                f"{combined}\n\n"
                f"【提取规则】\n"
                f"1. 只提取搜索结果中明确提及的歌曲，不要猜测\n"
                f"2. 优先提取搜索结果中推荐、排行、列表形式的歌曲\n"
                f"3. 歌名和歌手必须与搜索结果一致\n"
                f"4. 如果没有找到符合条件的歌曲，必须返回空数组 []\n\n"
                f"【输出格式】\n"
                f'请只返回 JSON 数组（最多 {top_k} 首），格式：\n'
                '[{"title": "歌名", "artist": "演唱者", "confidence": 0.9, "source_snippet": "来源简述"}]\n\n'
                f"confidence 评分标准：\n"
                f"- 0.9-1.0: 搜索结果明确推荐该歌曲与话题相关，且有完整信息\n"
                f"- 0.7-0.89: 搜索结果提到该歌曲与话题相关，但信息不够完整\n"
                f"- 0.5-0.69: 歌曲被提及但与话题关联不明确\n"
                f"- <0.5: 不确定是否相关\n\n"
                f"重要：只从给定的搜索结果中提取，不要凭记忆猜测。只返回纯JSON数组，不要包含其他文字。"
            )
            response = llm.invoke_text(
                "你是专业的音乐信息提取助手，擅长从搜索结果中准确提取歌曲信息。只使用给定的搜索结果，不要凭记忆猜测。",
                extract_prompt,
            )

            json_match = re.search(r'\[.*?\]', response, re.DOTALL)
            if not json_match:
                logger.warning("话题搜索结果解析失败")
                return []

            songs_raw = json.loads(json_match.group())
            results = []
            for item in songs_raw:
                song_title = item.get("title")
                song_artist = item.get("artist")
                confidence = float(item.get("confidence", 0))

                if not song_title or confidence < 0.3:
                    continue

                results.append({
                    "title": song_title,
                    "artist": song_artist or "未知艺术家",
                    "genre": [genre] if genre else [],
                    "mood": [],
                    "similarity_score": confidence,
                    "match_type": "topic_web_search",
                    "source": "topic_web_search",
                    "topic": topic,
                    "low_confidence": confidence < 0.7,
                })

            logger.info(f"话题搜索结果: {len(results)} 首 (话题='{topic}')")

            # 保存到缓存
            await set_cached_search(cache_key, "topic", results)

            return results[:top_k]

        except Exception as e:
            logger.error(f"话题歌曲搜索失败: {e}")
            return []


_topic_search_engine: Optional[TopicSearchEngine] = None


def get_topic_search_engine() -> TopicSearchEngine:
    global _topic_search_engine
    if _topic_search_engine is None:
        _topic_search_engine = TopicSearchEngine()
    return _topic_search_engine
