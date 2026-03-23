"""
影视主题曲搜索引擎
通过 Tavily Web Search 搜索电视剧/电影的主题曲、片头曲、片尾曲和插曲
"""

import json
import re
from typing import Any, Dict, List, Optional

from config.logging_config import get_logger

logger = get_logger(__name__)


class ThemeSearchEngine:
    """影视主题曲搜索引擎（基于 Web Search）"""

    async def search_by_title(self, title: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """
        搜索影视作品的主题曲/插曲

        Args:
            title: 影视剧名称（如"权力的游戏"、"霸王别姬"）
            top_k: 返回结果数量

        Returns:
            歌曲列表，source="theme_web_search"
        """
        logger.info(f"影视主题曲搜索: '{title}'")

        try:
            from config.settings_loader import load_settings_from_json
            import aiohttp

            settings = load_settings_from_json()
            api_key = settings.get("TAILYAPI_API_KEY", "")
            if not api_key:
                logger.warning("Tavily API Key 未配置，无法进行主题曲搜索")
                return []

            search_query = f'"{title}" 主题曲 片头曲 片尾曲 插曲 歌名 歌手'
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

            # 用 LLM 从搜索结果中提取结构化歌曲列表
            from llms.siliconflow_llm import SiliconFlowLLM
            llm = SiliconFlowLLM()
            extract_prompt = (
                f'根据以下网络搜索结果，提取影视作品《{title}》中的主题曲/片头曲/片尾曲/插曲信息。\n\n'
                f"{combined}\n\n"
                f"请只返回 JSON 数组（最多 {top_k} 首），格式：\n"
                '[{"title": "歌名", "artist": "演唱者", "type": "主题曲/片头曲/片尾曲/插曲", "confidence": 0.9}]\n'
                "confidence：0.9+ 非常确定，0.7-0.9 较确定，<0.7 不太确定。\n"
                "若无法找到任何歌曲，返回空数组 []。\n"
                "重要：只从给定的搜索结果中提取，不要凭记忆猜测。只返回纯JSON数组，不要包含其他文字。"
            )
            response = llm.invoke_text(
                "你是信息提取助手，只从给定的搜索结果中提取影视歌曲名和歌手名，不要凭记忆猜测。",
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
                    "theme_type": song_type,        # 主题曲 / 片头曲 / 插曲 等
                    "from_title": title,             # 来源影视剧名
                    "low_confidence": confidence < 0.7,
                })

            logger.info(f"主题曲搜索结果: {len(results)} 首 (来自《{title}》)")
            return results[:top_k]

        except Exception as e:
            logger.error(f"影视主题曲搜索失败: {e}")
            return []


# 全局单例
_theme_search_engine: Optional[ThemeSearchEngine] = None


def get_theme_search_engine() -> ThemeSearchEngine:
    global _theme_search_engine
    if _theme_search_engine is None:
        _theme_search_engine = ThemeSearchEngine()
    return _theme_search_engine
