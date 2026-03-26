"""
多语言搜索工具 - 支持中英日韩等多种语言的音乐搜索
"""

import re
from typing import Dict, List, Optional


class MultilingualSearchBuilder:
    """多语言搜索查询构建器"""

    # 按语言定义搜索模板 - 歌词搜索已优化
    TEMPLATES = {
        "zh": {
            "theme": '{country} "{title}" 主题曲 OST 歌名 演唱者',
            "topic": '{artist} 关于{topic}的歌曲 "{topic}" 歌词 推荐',
            "lyrics": '"{lyrics}" 歌词 歌名 歌手 歌曲',
            "video_bgm": '"{video_title}" BGM 背景音乐 是什么歌',
        },
        "en": {
            "theme": '"{title}" theme song soundtrack OST "{title}" song artist',
            "topic": '{artist} songs about {topic} tracklist lyrics',
            # 歌词搜索模板已优化 - 使用 build_lyrics_query_v2 获取多层策略
            "lyrics": '"{lyrics}" lyrics song artist',
            "video_bgm": '"{video_title}" background music BGM song',
        },
        "ja": {
            "theme": '"{title}" 主題歌 挿入歌 アーティスト 歌手',
            "topic": '{artist} {topic} について 歌 曲名',
            "lyrics": '"{lyrics}" 歌詞 曲名 アーティスト 歌曲',
            "video_bgm": '"{video_title}" BGM 曲名',
        },
        "ko": {
            "theme": '"{title}" OST 주제가 삽입가 수록곡 가수',
            "topic": '{artist} {topic} 관련 노래 곡명',
            "lyrics": '"{lyrics}" 가사 노래 제목 가수 歌曲',
            "video_bgm": '"{video_title}" BGM 배경음악 곡명',
        }
    }

    # 歌词搜索专业音乐网站 - 按优先级排序
    LYRICS_DOMAINS = [
        # 专业歌词网站
        "genius.com",
        "azlyrics.com",
        "lyrics.com",
        "metrolyrics.com",
        "songlyrics.com",
        # 音乐数据库
        "musicbrainz.org",
        "allmusic.com",
        "discogs.com",
        # 音乐社区
        "last.fm",
        "songfacts.com",
        # 百科
        "en.wikipedia.org",
        "wikidata.org",
    ]

    # 可能导致播客/非音乐内容的域名 - 用于排除
    PODCAST_DOMAINS = [
        "spotify.com/show",  # Spotify 播客
        "apple.com/podcast",
        "podcasts.apple.com",
    ]

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
    构建歌词搜索参数 - Phase 1 优化版

    使用多层搜索策略提升准确率：
    1. 专业音乐网站限定搜索
    2. 扩展关键词搜索
    3. 排除播客内容的搜索
    """
    return build_lyrics_query_v2(lyrics)[0]


def analyze_lyrics_features(lyrics: str) -> Dict:
    """
    分析歌词特征，用于优化搜索策略

    Returns:
        {
            "length": 歌词长度,
            "is_english": 是否为英文,
            "key_phrases": 关键短语列表,
            "search_hints": 搜索提示词列表,
            "genre_hints": 流派提示列表,
        }
    """
    features = {
        "length": len(lyrics),
        "is_english": False,
        "key_phrases": [],
        "search_hints": [],
        "genre_hints": [],
    }

    text_lower = lyrics.lower().strip()

    # 检测是否为英文
    en_chars = len(re.findall(r'[a-zA-Z]', lyrics))
    total_chars = len(re.sub(r'\s', '', lyrics))
    if total_chars > 0 and en_chars / total_chars > 0.5:
        features["is_english"] = True

    # 提取关键短语（去除停用词后的前4-5个词）
    words = text_lower.split()
    stop_words = {
        "i", "you", "he", "she", "it", "we", "they",
        "the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for",
        "of", "with", "by", "from", "up", "about", "into", "through",
        "me", "my", "mine", "your", "yours", "his", "her", "hers", "its", "our", "ours", "their", "theirs",
        "am", "is", "are", "was", "were", "be", "been", "being",
        "this", "that", "these", "those",
    }
    content_words = [w for w in words if w not in stop_words and len(w) > 1]

    if len(content_words) >= 3:
        # 取前4个词作为关键短语
        features["key_phrases"].append(" ".join(content_words[:4]))

    # 根据歌词内容推断流派提示
    genre_keywords = {
        "country": ["truck", "country", "whiskey", "beer", "dirt road", "small town", "farm", "cowboy", "western"],
        "rock": ["rock", "guitar", "band", "roll", "hell", "devil", "wild"],
        "indie": ["wish", "dream", "heart", "love", "stars", "cosmic", "potential", "possess"],
        "pop": ["baby", "dance", "party", "tonight", "forever", "always"],
        "rnb": ["baby", "love", "girl", "boy", "heart", "tear"],
    }

    for genre, keywords in genre_keywords.items():
        if any(kw in text_lower for kw in keywords):
            features["genre_hints"].append(genre)

    # 根据歌词特征添加搜索提示
    if features["is_english"] and len(lyrics) > 40:
        # 长英文歌词可能是独立/另类音乐
        if "indie" not in features["genre_hints"]:
            features["search_hints"].append("indie alternative")

    if "country" in features["genre_hints"]:
        features["search_hints"].append("country music")

    return features


def build_lyrics_query_v2(lyrics: str) -> List[Dict]:
    """
    构建多层歌词搜索查询 - Phase 1 核心优化

    返回多个查询配置，按优先级排序。系统应依次尝试，
    直到获得满意结果。

    Args:
        lyrics: 歌词片段

    Returns:
        查询配置列表，每个配置是 Tavily API 参数字典
    """
    # 分析歌词特征
    features = analyze_lyrics_features(lyrics)

    # 清理歌词（移除首尾引号）
    clean_lyrics = lyrics.strip('"""''')

    # 构建流派限定词
    genre_filter = ""
    if features["genre_hints"]:
        genre_filter = " " + " ".join(features["genre_hints"][:2])

    base_queries = []

    # ========== 查询 1: 专业音乐网站精确搜索 ==========
    query1_terms = [f'"{clean_lyrics}"', "lyrics", "song", "artist"]
    if features["search_hints"]:
        query1_terms.extend(features["search_hints"][:2])

    base_queries.append({
        "query": " ".join(query1_terms),
        "search_depth": "advanced",
        "max_results": 8,
        "include_domains": MultilingualSearchBuilder.LYRICS_DOMAINS[:10],  # 专业音乐网站
        "exclude_domains": MultilingualSearchBuilder.PODCAST_DOMAINS,
        "include_answer": True,
        "strategy": "lyrics_precise",  # 标记策略类型
    })

    # ========== 查询 2: 扩展关键词 + 排除播客 ==========
    query2 = f'"{clean_lyrics}" song title singer track music{genre_filter}'
    base_queries.append({
        "query": query2,
        "search_depth": "advanced",
        "max_results": 10,
        "include_domains": [],  # 不限制域名，扩大搜索
        "exclude_domains": MultilingualSearchBuilder.PODCAST_DOMAINS,
        "include_answer": True,
        "strategy": "lyrics_extended",
    })

    # ========== 查询 3: 关键短语搜索（用于长歌词） ==========
    if features["key_phrases"] and len(clean_lyrics) > 50:
        key_phrase = features["key_phrases"][0]
        query3 = f'"{key_phrase}" lyrics song artist{genre_filter}'
        base_queries.append({
            "query": query3,
            "search_depth": "advanced",
            "max_results": 8,
            "include_domains": MultilingualSearchBuilder.LYRICS_DOMAINS[:8],
            "exclude_domains": MultilingualSearchBuilder.PODCAST_DOMAINS,
            "include_answer": True,
            "strategy": "lyrics_key_phrase",
        })

    # ========== 查询 4: 维基百科保底搜索 ==========
    query4 = f'"{clean_lyrics}" song site:wikipedia.org'
    base_queries.append({
        "query": query4,
        "search_depth": "basic",  # 基础搜索即可
        "max_results": 5,
        "include_domains": ["en.wikipedia.org", "en.wikipedia.org"],
        "include_answer": True,
        "strategy": "lyrics_wikipedia_fallback",
    })

    return base_queries


def is_english_text(text: str) -> bool:
    """检测文本是否主要为英文"""
    if not text:
        return False
    en_chars = len(re.findall(r'[a-zA-Z]', text))
    total_chars = len(re.sub(r'\s', '', text))
    if total_chars == 0:
        return False
    return en_chars / total_chars > 0.5
