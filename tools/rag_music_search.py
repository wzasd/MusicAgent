"""
RAG (Retrieval-Augmented Generation) 音乐搜索模块
使用向量相似度检索音乐，替代 Spotify API
"""

import json
import os
import re
from typing import Dict, List, Optional, Any, Tuple
import numpy as np
from dataclasses import dataclass, field

from config.logging_config import get_logger

logger = get_logger(__name__)


@dataclass
class SongEmbedding:
    """歌曲向量表示"""
    song_id: str
    title: str
    artist: str
    genre: Optional[List[str]] = None
    mood: Optional[List[str]] = None
    embedding: Optional[np.ndarray] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class SimpleVectorStore:
    """简单内存向量存储"""

    def __init__(self, dimension: int = 768):
        self.dimension = dimension
        self.vectors: List[np.ndarray] = []
        self.songs: List[SongEmbedding] = []
        self._is_built = False

    def add_songs(self, songs: List[SongEmbedding]):
        """添加歌曲到向量库"""
        for song in songs:
            if song.embedding is not None:
                self.vectors.append(song.embedding)
                self.songs.append(song)
        self._is_built = False

    def build_index(self):
        """构建搜索索引（简单版本直接存储）"""
        if not self.vectors:
            logger.warning("向量库为空，无法构建索引")
            return

        # 归一化向量以便余弦相似度计算
        self.vectors = [v / (np.linalg.norm(v) + 1e-8) for v in self.vectors]
        self._is_built = True
        logger.info(f"向量索引构建完成，包含 {len(self.vectors)} 首歌曲")

    def search(self, query_embedding: np.ndarray, top_k: int = 10) -> List[Tuple[SongEmbedding, float]]:
        """
        搜索相似歌曲

        Args:
            query_embedding: 查询向量
            top_k: 返回结果数量

        Returns:
            [(歌曲, 相似度分数), ...]
        """
        if not self.vectors:
            return []

        # 归一化查询向量
        query_normalized = query_embedding / (np.linalg.norm(query_embedding) + 1e-8)

        # 计算余弦相似度
        similarities = []
        for i, vec in enumerate(self.vectors):
            similarity = np.dot(query_normalized, vec)
            similarities.append((self.songs[i], float(similarity)))

        # 按相似度排序
        similarities.sort(key=lambda x: x[1], reverse=True)

        return similarities[:top_k]


class RAGMusicSearch:
    """RAG 音乐搜索引擎"""

    def __init__(self):
        self.vector_store = SimpleVectorStore()
        self._embedding_cache: Dict[str, np.ndarray] = {}
        self._local_db_path = os.path.join(
            os.path.dirname(__file__), "..", "data", "music_database.json"
        )

    def _get_embedding_dimension(self) -> int:
        """获取嵌入维度"""
        # SiliconFlow 嵌入模型通常是 768 维
        return 768

    def _create_text_embedding(self, text: str) -> np.ndarray:
        """
        创建文本嵌入向量
        使用简单的关键词编码 + 字符级特征（无需外部API）
        """
        import hashlib

        text_lower = text.lower().strip()

        # 策略 1: 关键词匹配（英文）
        keywords = [
            "pop", "rock", "electronic", "jazz", "classical", "hip-hop", "r&b", "folk",
            "country", "metal", "punk", "indie", "alternative", "blues", "reggae",
            "happy", "sad", "energetic", "calm", "romantic", "melancholic", "upbeat",
            "relaxing", "intense", "peaceful", "passionate", "dreamy",
            "workout", "study", "party", "sleep", "driving", "dancing", "meditation",
            "work", "focus", "commute", "chill", "morning", "night",
            "acoustic", "instrumental", "vocal", "synth", "guitar", "piano", "beat",
            "melody", "harmony", "rhythm", "fast", "slow", "loud", "soft"
        ]

        keyword_vector = np.zeros(len(keywords))
        for i, keyword in enumerate(keywords):
            if keyword in text_lower:
                keyword_vector[i] = 0.5

        # 策略 2: 字符级特征（对中文更有效）
        # 使用哈希将字符映射到固定维度的向量
        char_features = np.zeros(100)
        for i, char in enumerate(text_lower):
            # 使用字符的 Unicode 码点哈希
            hash_val = int(hashlib.md5(char.encode()).hexdigest(), 16)
            idx = hash_val % 100
            char_features[idx] += 1.0 / (i + 1)  # 位置越靠前权重越高

        # 策略 3: N-gram 特征（捕捉局部模式）
        bigram_features = np.zeros(200)
        for i in range(len(text_lower) - 1):
            bigram = text_lower[i:i+2]
            hash_val = int(hashlib.md5(bigram.encode()).hexdigest(), 16)
            idx = hash_val % 200
            bigram_features[idx] += 1.0

        # 合并所有特征
        combined = np.concatenate([keyword_vector, char_features, bigram_features])

        # 扩展到 768 维
        target_dim = self._get_embedding_dimension()
        extended = np.zeros(target_dim)
        extended[:len(combined)] = combined

        # 使用正弦位置编码填充剩余维度
        for i in range(len(combined), target_dim):
            extended[i] = np.sin(i * 0.01) * 0.1

        # 归一化
        norm = np.linalg.norm(extended)
        if norm > 0:
            extended = extended / norm

        return extended

    def _create_song_embedding(self, song_data: Dict[str, Any]) -> np.ndarray:
        """为歌曲创建嵌入向量"""
        # 组合歌曲信息
        text_parts = []

        if song_data.get("title"):
            text_parts.append(song_data["title"])

        if song_data.get("artist"):
            text_parts.append(song_data["artist"])

        if song_data.get("genre"):
            genres = song_data["genre"]
            if isinstance(genres, list):
                text_parts.extend(genres)
            else:
                text_parts.append(str(genres))

        if song_data.get("mood"):
            moods = song_data["mood"]
            if isinstance(moods, list):
                text_parts.extend(moods)
            else:
                text_parts.append(str(moods))

        if song_data.get("description"):
            text_parts.append(song_data["description"])

        # 添加场景标签
        if song_data.get("tempo"):
            tempo = song_data["tempo"]
            if isinstance(tempo, (int, float)):
                if tempo > 120:
                    text_parts.extend(["fast", "energetic", "upbeat"])
                elif tempo < 80:
                    text_parts.extend(["slow", "calm", "relaxing"])
                else:
                    text_parts.extend(["moderate", "steady"])

        text = " ".join(text_parts)
        return self._create_text_embedding(text)

    def build_from_local_db(self) -> int:
        """
        从本地音乐数据库构建向量索引

        Returns:
            索引的歌曲数量
        """
        if not os.path.exists(self._local_db_path):
            logger.warning(f"本地音乐数据库不存在: {self._local_db_path}")
            return 0

        try:
            with open(self._local_db_path, 'r', encoding='utf-8') as f:
                db_data = json.load(f)

            songs_data = db_data if isinstance(db_data, list) else db_data.get("songs", [])

            song_embeddings = []
            for song_data in songs_data:
                try:
                    song_id = song_data.get("id") or f"{song_data.get('title', '')}_{song_data.get('artist', '')}"

                    embedding = SongEmbedding(
                        song_id=song_id,
                        title=song_data.get("title", "Unknown"),
                        artist=song_data.get("artist", "Unknown Artist"),
                        genre=song_data.get("genre"),
                        mood=song_data.get("mood"),
                        embedding=self._create_song_embedding(song_data),
                        metadata=song_data
                    )
                    song_embeddings.append(embedding)
                except Exception as e:
                    logger.debug(f"处理歌曲失败: {e}")
                    continue

            self.vector_store.add_songs(song_embeddings)
            self.vector_store.build_index()

            logger.info(f"从本地数据库构建索引: {len(song_embeddings)} 首歌曲")
            return len(song_embeddings)

        except Exception as e:
            logger.error(f"构建索引失败: {e}")
            return 0

    def add_llm_recommendations(self, recommendations: List[Dict[str, Any]]):
        """
        将 LLM 生成的推荐添加到向量库

        Args:
            recommendations: LLM 生成的推荐列表
        """
        song_embeddings = []

        for i, rec in enumerate(recommendations):
            try:
                song_data = rec.get("song", rec)

                # 构建歌曲描述用于嵌入
                description_parts = []
                if rec.get("reason"):
                    description_parts.append(rec["reason"])

                song_dict = {
                    "title": song_data.get("title", "Unknown"),
                    "artist": song_data.get("artist", "Unknown"),
                    "genre": song_data.get("genre", []),
                    "mood": song_data.get("mood", []),
                    "description": " ".join(description_parts),
                    **song_data
                }

                song_id = f"llm_rec_{i}_{song_data.get('title', '')}"

                embedding = SongEmbedding(
                    song_id=song_id,
                    title=song_dict["title"],
                    artist=song_dict["artist"],
                    genre=song_dict.get("genre"),
                    mood=song_dict.get("mood"),
                    embedding=self._create_song_embedding(song_dict),
                    metadata={
                        "source": "llm_recommendation",
                        "recommendation_data": rec,
                        **song_data
                    }
                )
                song_embeddings.append(embedding)

            except Exception as e:
                logger.debug(f"处理推荐失败: {e}")
                continue

        self.vector_store.add_songs(song_embeddings)
        self.vector_store.build_index()

        logger.info(f"添加 LLM 推荐到索引: {len(song_embeddings)} 首歌曲")

    def _extract_query_keywords(self, query: str) -> str:
        """提取查询核心关键词，去除常见前缀"""
        import re
        query = query.lower().strip()

        # 去除常见前缀
        prefixes = [
            r'^我想听', r'^我要听', r'^播放', r'^来[一]?[首]?', r'^搜索', r'^找[一下]?',
            r'^推荐[一]?[些]?', r'^有[没]?有', r'^给?我', r'^请?', r'^能不能',
            r'^i want to hear', r'^i want to listen', r'^play', r'^search for',
            r'^find', r'^recommend', r'^give me', r'^can you play',
        ]
        for prefix in prefixes:
            query = re.sub(prefix, '', query, flags=re.IGNORECASE)

        # 去除书名号
        query = re.sub(r'[《》]', '', query)
        # 去除多余空格
        query = ' '.join(query.split())
        return query.strip()

    def _calculate_text_similarity(self, query: str, title: str, artist: str) -> float:
        """计算查询与歌曲的文本相似度"""
        from difflib import SequenceMatcher

        query_lower = query.lower()
        title_lower = title.lower()
        artist_lower = artist.lower()

        # 标题完全匹配
        if query_lower == title_lower:
            return 1.0

        # 标题包含查询
        if query_lower in title_lower or title_lower in query_lower:
            return 0.9

        # 艺术家匹配
        if query_lower in artist_lower:
            return 0.8

        # 编辑距离相似度
        title_sim = SequenceMatcher(None, query_lower, title_lower).ratio()
        return title_sim * 0.7  # 最高 0.7

    def search(self, query: str, top_k: int = 10) -> List[Dict[str, Any]]:
        """
        搜索相似歌曲 - 混合匹配（字面匹配 + 向量相似度）

        Args:
            query: 搜索查询（可以是描述、情绪、场景等）
            top_k: 返回结果数量

        Returns:
            歌曲信息列表
        """
        if not self.vector_store.songs:
            logger.warning("向量库为空，请先构建索引")
            return []

        # 1. 查询预处理：提取核心关键词
        clean_query = self._extract_query_keywords(query)
        logger.debug(f"RAG 查询预处理: '{query}' -> '{clean_query}'")

        # 2. 向量相似度搜索
        query_embedding = self._create_text_embedding(clean_query)
        vector_results = self.vector_store.search(query_embedding, top_k=top_k * 2)

        # 3. 混合评分
        scored_songs = {}

        # 向量相似度分数
        for song_embedding, vec_score in vector_results:
            key = (song_embedding.title, song_embedding.artist)
            scored_songs[key] = {
                "song": song_embedding,
                "vector_score": vec_score,
                "text_score": 0.0
            }

        # 文本相似度分数（对 clean_query 进行字面匹配）
        for song in self.vector_store.songs:
            text_score = self._calculate_text_similarity(
                clean_query, song.title, song.artist
            )
            if text_score > 0:
                key = (song.title, song.artist)
                if key in scored_songs:
                    scored_songs[key]["text_score"] = text_score
                else:
                    scored_songs[key] = {
                        "song": song,
                        "vector_score": 0.0,
                        "text_score": text_score
                    }

        # 4. 合并分数（加权平均）
        final_results = []
        for key, data in scored_songs.items():
            # 向量分权重 0.4，文本分权重 0.6（字面匹配更可靠）
            combined_score = data["vector_score"] * 0.4 + data["text_score"] * 0.6

            song_info = {
                "title": data["song"].title,
                "artist": data["song"].artist,
                "genre": data["song"].genre,
                "mood": data["song"].mood,
                "similarity_score": combined_score,
                "vector_score": data["vector_score"],
                "text_score": data["text_score"],
                **data["song"].metadata
            }
            final_results.append(song_info)

        # 5. 按综合分数排序
        final_results.sort(key=lambda x: x["similarity_score"], reverse=True)

        return final_results[:top_k]

    def search_by_song(self, title: str, artist: Optional[str] = None, top_k: int = 5) -> List[Dict[str, Any]]:
        """
        根据歌曲搜索相似歌曲

        Args:
            title: 歌曲名称
            artist: 艺术家（可选）
            top_k: 返回结果数量

        Returns:
            相似歌曲列表
        """
        query = f"{title} {artist}" if artist else title
        return self.search(query, top_k=top_k)

    def search_by_mood(self, mood: str, top_k: int = 10) -> List[Dict[str, Any]]:
        """
        根据情绪搜索歌曲 - 直接匹配 mood 字段

        Args:
            mood: 情绪描述（如：开心、放松、专注）
            top_k: 返回结果数量

        Returns:
            匹配情绪的歌曲列表
        """
        # 构建情绪映射关系
        mood_relations = {
            "开心": ["开心", "快乐", "活力", "兴奋", "甜蜜", "幸福"],
            "快乐": ["快乐", "开心", "活力", "兴奋", "甜蜜", "幸福"],
            "放松": ["放松", "平静", "治愈", "慵懒", "安静"],
            "专注": ["专注", "平静", "放松", "治愈"],
            "运动": ["运动", "活力", "激情", "兴奋"],
            "浪漫": ["浪漫", "甜蜜", "温暖", "幸福"],
            "悲伤": ["悲伤", "伤感", "忧伤", "孤独"],
            "伤感": ["伤感", "悲伤", "忧伤", "孤独"],
            "活力": ["活力", "兴奋", "激情", "运动"],
            "兴奋": ["兴奋", "活力", "激情", "运动"],
            "平静": ["平静", "放松", "治愈", "安静"],
            "冥想": ["冥想", "平静", "放松", "安静"],
            "派对": ["派对", "活力", "兴奋", "热情"],
            "睡眠": ["睡眠", "平静", "放松", "安静"],
            "治愈": ["治愈", "放松", "平静", "温暖"],
            "温暖": ["温暖", "治愈", "浪漫", "甜蜜"],
        }

        # 获取相关情绪列表
        related_moods = mood_relations.get(mood, [mood])

        # 直接匹配 mood 字段
        matched_songs = []
        for song in self.vector_store.songs:
            song_moods = song.mood or []
            if not isinstance(song_moods, list):
                song_moods = [str(song_moods)]

            # 检查是否有匹配的情绪
            for song_mood in song_moods:
                if any(rel_mood in song_mood for rel_mood in related_moods):
                    matched_songs.append({
                        "title": song.title,
                        "artist": song.artist,
                        "genre": song.genre,
                        "mood": song.mood,
                        "similarity_score": 0.9,  # 高置信度
                        **song.metadata
                    })
                    break

        # 如果直接匹配有足够结果，返回
        if len(matched_songs) >= top_k:
            return matched_songs[:top_k]

        # 如果直接匹配不够，用向量搜索补充
        logger.info(f"直接匹配找到 {len(matched_songs)} 首，用向量搜索补充")

        # 构建查询（使用情绪关键词）
        mood_keywords = {
            "开心": "happy upbeat energetic joyful",
            "放松": "calm relaxing peaceful chill",
            "专注": "focus concentration study instrumental",
            "运动": "workout energetic intense fast",
            "浪漫": "romantic love passionate dreamy",
            "悲伤": "sad melancholic emotional slow",
            "活力": "energetic lively active dynamic",
            "平静": "meditation peaceful calm ambient",
        }
        query = mood_keywords.get(mood, mood)
        vector_results = self.search(query, top_k=top_k * 2)

        # 合并结果（去重）
        seen_titles = {s["title"] for s in matched_songs}
        for result in vector_results:
            title = result.get("title")
            if title not in seen_titles:
                matched_songs.append(result)
                seen_titles.add(title)
            if len(matched_songs) >= top_k:
                break

        return matched_songs[:top_k]

    def search_by_activity(self, activity: str, top_k: int = 10) -> List[Dict[str, Any]]:
        """
        根据活动场景搜索歌曲

        Args:
            activity: 活动描述（如：工作、学习、运动）
            top_k: 返回结果数量

        Returns:
            匹配活动的歌曲列表
        """
        activity_keywords = {
            "工作": "work focus concentration productive steady instrumental",
            "学习": "study focus concentration calm instrumental ambient",
            "运动": "workout exercise gym energetic fast beat intense",
            "通勤": "commute driving upbeat morning energetic",
            "休息": "rest relax calm peaceful quiet soft",
            "派对": "party dance upbeat lively social fun",
            "阅读": "reading calm quiet instrumental peaceful",
            "清洁": "cleaning upbeat energetic lively fast",
            "烹饪": "cooking happy upbeat relaxed cheerful",
            "睡前": "sleep bedtime calm peaceful slow ambient"
        }

        query = activity_keywords.get(activity, activity)
        return self.search(query, top_k=top_k)


# 全局 RAG 搜索实例
_rag_search: Optional[RAGMusicSearch] = None


def get_rag_music_search() -> RAGMusicSearch:
    """获取 RAG 音乐搜索实例（单例）"""
    global _rag_search
    if _rag_search is None:
        _rag_search = RAGMusicSearch()
        # 尝试加载本地数据库
        _rag_search.build_from_local_db()
    return _rag_search
