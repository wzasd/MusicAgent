"""
歌词搜索工具 - 支持通过歌词片段查找歌曲
"""

import json
import os
from typing import Dict, List, Optional, Any
from difflib import SequenceMatcher

from config.logging_config import get_logger

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

            if total_sim > 0.3:  # 阈值
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


# 全局实例
_lyrics_search_engine: Optional[LyricsSearchEngine] = None


def get_lyrics_search_engine() -> LyricsSearchEngine:
    """获取歌词搜索引擎单例"""
    global _lyrics_search_engine
    if _lyrics_search_engine is None:
        _lyrics_search_engine = LyricsSearchEngine()
    return _lyrics_search_engine
