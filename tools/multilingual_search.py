"""
多语言搜索工具 - 支持中英日韩等多种语言的音乐搜索
"""

import re
from typing import Dict, List, Optional


class MultilingualSearchBuilder:
    """多语言搜索查询构建器"""

    # 按语言定义搜索模板
    TEMPLATES = {
        "zh": {
            "theme": '{country} "{title}" 主题曲 OST 歌名 演唱者',
            "topic": '{artist} 关于{topic}的歌曲 "{topic}" 歌词 推荐',
            "lyrics": '"{lyrics}" 歌词 歌名 歌手',
            "video_bgm": '"{video_title}" BGM 背景音乐 是什么歌',
        },
        "en": {
            "theme": '"{title}" theme song soundtrack OST "{title}" song artist',
            "topic": '{artist} songs about {topic} tracklist lyrics',
            "lyrics": '"{lyrics}" lyrics song name artist',
            "video_bgm": '"{video_title}" background music BGM song',
        },
        "ja": {
            "theme": '"{title}" 主題歌 挿入歌 アーティスト 歌手',
            "topic": '{artist} {topic} について 歌 曲名',
            "lyrics": '"{lyrics}" 歌詞 曲名 アーティスト',
            "video_bgm": '"{video_title}" BGM 曲名',
        },
        "ko": {
            "theme": '"{title}" OST 주제가 삽입가 수록곡 가수',
            "topic": '{artist} {topic} 관련 노래 곡명',
            "lyrics": '"{lyrics}" 가사 노래 제목 가수',
            "video_bgm": '"{video_title}" BGM 배경음악 곡명',
        }
    }

    # 按语言优化搜索域
    INCLUDE_DOMAINS = {
        "zh": [
            "baike.baidu.com",
            "music.163.com",
            "y.qq.com",
            "zh.wikipedia.org",
            "kugou.com",
            "kuwo.cn",
            "douban.com",
            "bilibili.com",
        ],
        "en": [
            "en.wikipedia.org",
            "genius.com",
            "discogs.com",
            "musicbrainz.org",
            "allmusic.com",
            "last.fm",
            "billboard.com",
            "youtube.com",
        ],
        "ja": [
            "ja.wikipedia.org",
            "utaten.com",
            "j-lyric.net",
            "anison.info",
            "www.uta-net.com",
        ],
        "ko": [
            "ko.wikipedia.org",
            "melon.com",
            "genie.co.kr",
            "bugs.co.kr",
        ]
    }

    @staticmethod
    def detect_language(text: str) -> str:
        """
        检测文本语言
        返回: "zh" | "en" | "ja" | "ko"
        """
        if not text:
            return "en"

        text = text.strip()

        # 日文假名
        if re.search(r'[\u3040-\u309F\u30A0-\u30FF]', text):
            return "ja"

        # 韩文
        if re.search(r'[\uAC00-\uD7AF]', text):
            return "ko"

        # 中文字符占比高
        cn_chars = len(re.findall(r'[\u4e00-\u9fff]', text))
        total_chars = len(re.sub(r'\s', '', text))
        if total_chars > 0 and cn_chars / total_chars > 0.3:
            return "zh"

        # 默认英文
        return "en"

    @classmethod
    def build_query(cls, query_type: str, **kwargs) -> str:
        """
        构建多语言搜索查询

        Args:
            query_type: 查询类型 (theme/topic/lyrics/video_bgm)
            **kwargs: 模板变量

        Returns:
            构建好的搜索查询字符串
        """
        # 检测输入语言
        text = (kwargs.get("title") or
                kwargs.get("topic") or
                kwargs.get("lyrics") or
                kwargs.get("video_title") or "")

        lang = cls.detect_language(text)

        # 获取模板，默认英文
        templates = cls.TEMPLATES.get(lang, cls.TEMPLATES["en"])
        template = templates.get(query_type, templates.get("theme", ""))

        if not template:
            # 如果找不到模板，使用简单拼接
            parts = [v for v in kwargs.values() if v and isinstance(v, str)]
            return " ".join(parts)

        return template.format(**kwargs)

    @classmethod
    def get_domains(cls, text: str) -> List[str]:
        """
        获取对应语言的推荐搜索域名

        Args:
            text: 搜索文本

        Returns:
            推荐域名列表
        """
        lang = cls.detect_language(text)
        return cls.INCLUDE_DOMAINS.get(lang, cls.INCLUDE_DOMAINS["en"])

    @classmethod
    def build_tavily_params(cls, query_type: str, **kwargs) -> Dict:
        """
        构建 Tavily 搜索参数

        Returns:
            Tavily API 参数字典
        """
        # 获取查询文本用于检测语言
        text = (kwargs.get("title") or
                kwargs.get("topic") or
                kwargs.get("lyrics") or "")

        query = cls.build_query(query_type, **kwargs)
        domains = cls.get_domains(text)

        return {
            "query": query,
            "search_depth": "advanced",  # 深度搜索
            "max_results": 10,           # 增加结果数
            "include_domains": domains,  # 优先搜索音乐相关网站
            "include_answer": True,
        }


def build_theme_query(title: str, country: Optional[str] = None) -> Dict:
    """
    构建影视主题曲搜索参数
    """
    return MultilingualSearchBuilder.build_tavily_params(
        "theme",
        title=title,
        country=country or ""
    )


def build_topic_query(topic: str, artist: Optional[str] = None, genre: Optional[str] = None) -> Dict:
    """
    构建话题歌曲搜索参数
    """
    return MultilingualSearchBuilder.build_tavily_params(
        "topic",
        topic=topic,
        artist=artist or "",
        genre=genre or ""
    )


def build_lyrics_query(lyrics: str) -> Dict:
    """
    构建歌词搜索参数
    """
    return MultilingualSearchBuilder.build_tavily_params(
        "lyrics",
        lyrics=lyrics
    )
