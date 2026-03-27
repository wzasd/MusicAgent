"""
歌词搜索工具 - 支持通过歌词片段查找歌曲
"""

import json
import os
import re
from typing import Dict, List, Optional, Any
from difflib import SequenceMatcher

from config.logging_config import get_logger
from tools.multilingual_search import MultilingualSearchBuilder, build_lyrics_query_v2
from tools.web_search_cache import get_cached_search, set_cached_search

logger = get_logger(__name__)


class LyricsSearchEngine:
    """歌词搜索引擎 - 通过歌词片段找歌"""

    def __init__(self, lyrics_db_path: Optional[str] = None):
        if lyrics_db_path is None:
            lyrics_db_path = os.path.join(
                os.path.dirname(__file__), "..", "data", "lyrics_database.json"
            )
        self.lyrics_db_path = lyrics_db_path
        self._mappings: List[Dict[str, Any]] = []
        self._load_database()

    def _load_database(self):
        """加载歌词数据库"""
        try:
            if os.path.exists(self.lyrics_db_path):
                with open(self.lyrics_db_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self._mappings = data.get("mappings", [])
                logger.info(f"歌词数据库加载成功: {len(self._mappings)} 条映射")
            else:
                logger.warning(f"歌词数据库不存在: {self.lyrics_db_path}")
                self._mappings = []
        except Exception as e:
            logger.error(f"加载歌词数据库失败: {e}")
            self._mappings = []

    def _similarity(self, a: str, b: str) -> float:
        """计算两个字符串的相似度"""
        return SequenceMatcher(None, a.lower(), b.lower()).ratio()

    def search_by_lyrics(self, lyrics_query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """
        通过歌词片段搜索歌曲

        Args:
            lyrics_query: 歌词片段或描述
            top_k: 返回结果数量

        Returns:
            匹配的歌曲列表，包含相似度分数
        """
        if not self._mappings:
            return []

        results = []
        # 先用 extract_lyrics_content 提取纯歌词，再做相似度比对
        query_clean = self.extract_lyrics_content(lyrics_query).lower().strip()
        if not query_clean:
            query_clean = lyrics_query.lower().strip()

        for mapping in self._mappings:
            # 计算与歌词片段的相似度
            fragment_sim = self._similarity(query_clean, mapping["lyrics_fragment"])

            # 计算与完整歌词的相似度
            full_lyrics_sim = self._similarity(query_clean, mapping.get("full_lyrics", ""))

            # 计算与歌名的相似度
            title_sim = self._similarity(query_clean, mapping["title"])

            # 综合相似度（加权）
            total_sim = max(fragment_sim * 1.5, full_lyrics_sim * 1.2, title_sim)

            if total_sim > 0.5:  # 提高阈值，减少误匹配
                results.append({
                    "title": mapping["title"],
                    "artist": mapping["artist"],
                    "genre": mapping.get("genre", []),
                    "mood": mapping.get("mood", []),
                    "matched_lyrics": mapping["lyrics_fragment"],
                    "similarity_score": total_sim,
                    "match_type": "lyrics" if fragment_sim > title_sim else "title"
                })

        # 按相似度排序
        results.sort(key=lambda x: x["similarity_score"], reverse=True)

        logger.info(f"歌词搜索 '{lyrics_query}': 找到 {len(results)} 首匹配歌曲")
        return results[:top_k]

    def is_lyrics_query(self, query: str) -> bool:
        """
        判断是否是歌词搜索请求 - 支持中英文

        Args:
            query: 用户输入

        Returns:
            是否是歌词搜索
        """
        query_lower = query.lower().strip()

        import re

        # ===== 中文模式 =====
        # 匹配 "歌词是xxx", "歌词里有xxx" 等
        if re.search(r'歌词[是里有为][:：]?\s*[\u4e00-\u9fa5]{3,}', query_lower):
            return True

        # 匹配 "歌词" + 至少5个中文字符
        if '歌词' in query_lower and len(re.findall(r'[\u4e00-\u9fa5]', query_lower)) >= 8:
            if not any(x in query_lower for x in ['歌词网', '歌词本', '歌词版']):
                return True

        # 匹配 "xxx是什么歌"
        if '是什么歌' in query_lower and len(query_lower) > 10:
            return True

        # ===== 英文模式 =====
        # 匹配 "song with the lyric(s) ..." 或 "what song has the lyric ..."
        en_patterns = [
            r'\blyric[s]?\b.{3,}',          # "lyric ..." or "lyrics ..."
            r'\bwhat song\b.{3,}',           # "what song ..."
            r'\bsong with.{3,}lyric',        # "song with ... lyric"
            r'\bwhat.{0,10}(song|music)\b.+\blyric',
        ]
        for pattern in en_patterns:
            if re.search(pattern, query_lower):
                return True

        return False

    def extract_lyrics_content(self, query: str) -> str:
        """
        从歌词搜索查询中提取纯歌词内容（去除前缀后缀），支持中英文

        Args:
            query: 原始查询，如 "i want to hear the song with the lyric \"xxx\""

        Returns:
            纯歌词内容
        """
        import re
        query_clean = query.strip()

        # ===== 英文：提取引号内容（优先） =====
        quoted = re.search(r'["\u201c\u201d](.*?)["\u201d]', query_clean)
        if quoted:
            return quoted.group(1).strip()

        # ===== 中文前缀清理 =====
        query_clean = re.sub(r'^.*?歌词[是里有为][:：]?\s*', '', query_clean)
        query_clean = re.sub(r'^有首歌歌词[是里有][:：]?\s*', '', query_clean)

        # ===== 英文前缀清理 =====
        # "i want to hear the song with the lyric ..."
        query_clean = re.sub(
            r'^.{0,40}?\b(?:lyric[s]?|song)\b\s+(?:is|are|goes?|says?|that\s+goes?|with|has|have|containing)\s*[:\-]?\s*',
            '', query_clean, flags=re.IGNORECASE
        )
        # "what song has the lyric ..."
        query_clean = re.sub(
            r'^(?:what|which)\s+(?:song|music|track)\s+(?:has|have|contains?)\s+(?:the\s+)?lyric[s]?\s*[:\-]?\s*',
            '', query_clean, flags=re.IGNORECASE
        )

        # ===== 中文后缀清理 =====
        query_clean = re.sub(r'[，,、。]+.*$', '', query_clean)
        query_clean = re.sub(r'[的首歌曲音乐]*$', '', query_clean)
        query_clean = re.sub(r'[是]?[什什么]?[么歌]+?$', '', query_clean)

        return query_clean.strip()


    async def search_with_llm_fallback(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """歌词搜索入口（兼容旧调用），内部走 web search 兜底。"""
        return await self.search_with_web_fallback(query, top_k=top_k)

    async def search_with_web_fallback(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """
        歌词搜索：本地数据库优先，命中不了则用 Tavily Web Search 查歌词来源。
        Phase 1 优化：使用多层搜索策略提升准确率

        Args:
            query: 用户原始输入（含歌词片段）
            top_k: 返回结果数量

        Returns:
            歌曲列表，source 字段标记来源 ("lyrics_db" 或 "web_search")
        """
        # Step 1: 本地数据库匹配
        local_results = self.search_by_lyrics(query, top_k=top_k)
        if local_results and local_results[0]["similarity_score"] >= 0.6:
            logger.info(f"歌词本地命中: {local_results[0]['title']} (score={local_results[0]['similarity_score']:.2f})")
            for r in local_results:
                r["source"] = "lyrics_db"
            return local_results

        # Step 2: 检查缓存
        lyrics_content = self.extract_lyrics_content(query)
        if not lyrics_content:
            lyrics_content = query

        cache_key = lyrics_content[:100]  # 限制缓存键长度
        cached = await get_cached_search(cache_key, "lyrics")
        if cached:
            logger.info(f"歌词搜索缓存命中: '{lyrics_content[:30]}...'")
            return cached[:top_k]

        logger.info(f"本地未命中，使用 Web Search 识别歌词: '{lyrics_content}'")

        try:
            from config.settings_loader import load_settings_from_json
            import aiohttp

            settings = load_settings_from_json()
            api_key = settings.get("TAILYAPI_API_KEY", "")
            if not api_key:
                logger.warning("Tavily API Key 未配置，跳过 Web Search")
                return local_results

            # Phase 1 优化：使用多层搜索策略
            query_configs = build_lyrics_query_v2(lyrics_content)

            for attempt, search_params in enumerate(query_configs, 1):
                strategy = search_params.pop("strategy", "unknown")
                logger.info(f"尝试搜索策略 {attempt}/{len(query_configs)}: {strategy}")

                try:
                    async with aiohttp.ClientSession() as session:
                        async with session.post(
                            "https://api.tavily.com/search",
                            json={
                                "api_key": api_key,
                                **search_params,
                            },
                            headers={"Content-Type": "application/json"},
                            timeout=aiohttp.ClientTimeout(total=15),
                        ) as resp:
                            if resp.status != 200:
                                logger.warning(f"Tavily 请求失败 (策略 {strategy}): {resp.status}")
                                continue
                            data = await resp.json()

                    answer = data.get("answer", "")
                    results_list = data.get("results", [])

                    if not results_list and not answer:
                        logger.info(f"策略 {strategy} 无结果，尝试下一策略")
                        continue

                    snippets = "\n".join(
                        f"[{i+1}] {r.get('content', '')[:350]}"
                        for i, r in enumerate(results_list[:8])
                    )
                    combined = f"搜索答案: {answer}\n\n相关内容:\n{snippets}".strip()

                    logger.info(f"策略 {strategy} 返回 {len(results_list)} 条结果")

                    # 用 LLM 从 web 内容中提取结构化信息
                    from llms import get_llm
                    from prompts.music_prompts import LYRICS_IDENTIFICATION_FROM_SEARCH_PROMPT
                    llm = get_llm()

                    # 使用安全的字符串替换而不是 format()，避免搜索结果中的 {} 被解析为占位符
                    extract_prompt = LYRICS_IDENTIFICATION_FROM_SEARCH_PROMPT
                    extract_prompt = extract_prompt.replace("{lyrics}", lyrics_content)
                    extract_prompt = extract_prompt.replace("{search_results}", combined)
                    response = llm.invoke_text(
                        "你是专业的歌词识别助手，擅长通过歌词片段识别歌曲。只使用给定的搜索结果，不要凭记忆猜测。",
                        extract_prompt,
                    )

                    # 调试日志
                    logger.debug(f"LLM 响应: {response[:500]}...")

                    json_match = re.search(r'\{[\s\S]*?\}', response, re.DOTALL)
                    if not json_match:
                        logger.warning(f"策略 {strategy} 结果解析失败，尝试下一策略")
                        continue

                    json_str = json_match.group()
                    logger.debug(f"提取的 JSON: {json_str[:300]}...")

                    try:
                        extracted = json.loads(json_str)
                    except json.JSONDecodeError as e:
                        logger.warning(f"策略 {strategy} JSON解析失败: {e}, 内容: {json_str[:200]}")
                        continue

                    # 确保 extracted 是字典
                    if not isinstance(extracted, dict):
                        logger.warning(f"策略 {strategy} 解析结果不是字典: {type(extracted)}")
                        continue

                    title = extracted.get("title")
                    artist = extracted.get("artist")
                    confidence = float(extracted.get("confidence", 0))

                    # 验证结果有效性
                    if not title or confidence < 0.3:
                        logger.info(f"策略 {strategy} 识别置信度过低 ({confidence})，尝试下一策略")
                        continue

                    # 检查是否是播客/非音乐内容
                    result_title = (title or "").lower()
                    result_artist = (artist or "").lower()
                    podcast_indicators = ["podcast", "episode", "announcement", "undisclosed", "show notes"]
                    if any(ind in result_title or ind in result_artist for ind in podcast_indicators):
                        logger.warning(f"策略 {strategy} 返回播客内容，尝试下一策略")
                        continue

                    logger.info(f"Web Search 识别成功 (策略 {strategy}): {title} - {artist} (confidence={confidence})")

                    result = [{
                        "title": title,
                        "artist": artist or "未知艺术家",
                        "genre": [],
                        "mood": [],
                        "matched_lyrics": lyrics_content,
                        "similarity_score": confidence,
                        "match_type": "web_search",
                        "source": "web_search",
                        "search_strategy": strategy,
                        "low_confidence": confidence < 0.7,
                    }]

                    # 保存到缓存
                    await set_cached_search(cache_key, "lyrics", result)

                    return result

                except Exception as e:
                    import traceback
                    logger.warning(f"策略 {strategy} 执行失败: {e}")
                    logger.debug(f"策略 {strategy} 异常详情: {traceback.format_exc()}")
                    continue

            # 所有策略都失败
            logger.warning("所有搜索策略均未返回有效结果")
            return local_results

        except Exception as e:
            logger.error(f"Web Search 歌词识别失败: {e}")
            return local_results


# 全局实例
_lyrics_search_engine: Optional[LyricsSearchEngine] = None


def get_lyrics_search_engine() -> LyricsSearchEngine:
    """获取歌词搜索引擎单例"""
    global _lyrics_search_engine
    if _lyrics_search_engine is None:
        _lyrics_search_engine = LyricsSearchEngine()
    return _lyrics_search_engine
