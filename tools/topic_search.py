"""
话题歌曲搜索引擎
通过 Tavily Web Search 搜索与特定话题相关的歌曲（如：关于天空的歌、关于雨的 Lady Gaga 歌曲）
"""

import json
import re
from typing import Any, Dict, List, Optional

from config.logging_config import get_logger

logger = get_logger(__name__)


class TopicSearchEngine:
    """话题歌曲搜索引擎（基于 Web Search）"""

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
        parts = []
        if artist:
            parts.append(artist)
        parts.append(f"关于{topic}")
        if genre:
            parts.append(genre)
        parts.append("歌曲 推荐 歌名 歌手")
        search_query = " ".join(parts)

        logger.info(f"话题歌曲搜索: topic='{topic}' artist='{artist}' genre='{genre}'")

        try:
            from config.settings_loader import load_settings_from_json
            import aiohttp

            settings = load_settings_from_json()
            api_key = settings.get("TAILYAPI_API_KEY", "")
            if not api_key:
                logger.warning("Tavily API Key 未配置，无法进行话题搜索")
                return []

            async with aiohttp.ClientSession() as session:
                async with session.post(
                    "https://api.tavily.com/search",
                    json={
                        "api_key": api_key,
                        "query": search_query,
                        "search_depth": "basic",
                        "include_answer": True,
                        "max_results": 5,
                    },
                    headers={"Content-Type": "application/json"},
                    timeout=aiohttp.ClientTimeout(total=10),
                ) as resp:
                    if resp.status != 200:
                        logger.error(f"Tavily 请求失败: {resp.status}")
                        return []
                    data = await resp.json()

            answer = data.get("answer", "")
            snippets = "\n".join(
                r.get("content", "")[:400] for r in data.get("results", [])[:4]
            )
            combined = f"搜索答案: {answer}\n\n相关内容: {snippets}".strip()

            if not combined:
                return []

            logger.info(f"Tavily 返回答案: {answer[:120]}")

            # 构建 LLM 提取 prompt
            constraint = ""
            if artist:
                constraint += f"，只列出 {artist} 的歌曲"
            if genre:
                constraint += f"，风格为 {genre}"

            from llms.siliconflow_llm import SiliconFlowLLM
            llm = SiliconFlowLLM()
            extract_prompt = (
                f'根据以下网络搜索结果，提取与话题"{topic}"相关的歌曲{constraint}。\n\n'
                f"{combined}\n\n"
                f"请只返回 JSON 数组（最多 {top_k} 首），格式：\n"
                '[{"title": "歌名", "artist": "演唱者", "confidence": 0.9}]\n'
                "confidence：0.9+ 非常确定，0.7-0.9 较确定，<0.7 不太确定。\n"
                "若无法找到，返回空数组 []。\n"
                "重要：只从给定的搜索结果中提取，不要凭记忆猜测。只返回纯JSON数组，不要包含其他文字。"
            )
            response = llm.invoke_text(
                "你是信息提取助手，只从给定的搜索结果中提取歌曲名和歌手名，不要凭记忆猜测。",
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
