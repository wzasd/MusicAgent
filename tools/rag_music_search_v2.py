"""
RAG (Retrieval-Augmented Generation) 音乐搜索模块 V2
使用 SiliconFlow Embedding + ChromaDB 持久化存储
"""

import json
import os
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
import numpy as np

from config.logging_config import get_logger

logger = get_logger(__name__)


@dataclass
class RAGSong:
    """RAG 歌曲数据结构"""
    id: str
    title: str
    artist: str
    album: Optional[str] = None
    genre: Optional[List[str]] = None
    mood: Optional[List[str]] = None
    scenes: Optional[List[str]] = None
    description: Optional[str] = None
    year: Optional[int] = None
    duration: Optional[int] = None
    source: str = "unknown"
    embedding: Optional[List[float]] = None


class ChromaVectorStore:
    """基于 ChromaDB 的持久化向量存储"""

    def __init__(self, collection_name: str = "music_songs", persist_dir: str = "./data/chroma_db"):
        self.collection_name = collection_name
        self.persist_dir = persist_dir
        self._collection = None
        self._client = None
        self._init_chroma()

    def _init_chroma(self):
        """初始化 ChromaDB"""
        try:
            import chromadb
            from chromadb.config import Settings

            # 创建持久化客户端
            self._client = chromadb.PersistentClient(
                path=self.persist_dir,
                settings=Settings(anonymized_telemetry=False)
            )

            # 获取或创建集合
            self._collection = self._client.get_or_create_collection(
                name=self.collection_name,
                metadata={"hnsw:space": "cosine"}  # 使用余弦相似度
            )

            logger.info(f"ChromaDB 初始化完成: {self.persist_dir}, 集合: {self.collection_name}")

        except ImportError:
            logger.error("ChromaDB 未安装，请运行: pip install chromadb")
            raise
        except Exception as e:
            logger.error(f"ChromaDB 初始化失败: {e}")
            raise

    def add_songs(self, songs: List[RAGSong]):
        """批量添加歌曲"""
        if not songs:
            return

        ids = []
        embeddings = []
        documents = []
        metadatas = []

        for song in songs:
            if song.embedding is None:
                continue

            ids.append(song.id)
            embeddings.append(song.embedding)
            documents.append(f"{song.title} {song.artist} {song.description or ''}")
            metadatas.append({
                "title": song.title,
                "artist": song.artist,
                "album": song.album or "",
                "genre": json.dumps(song.genre or [], ensure_ascii=False),
                "mood": json.dumps(song.mood or [], ensure_ascii=False),
                "scenes": json.dumps(song.scenes or [], ensure_ascii=False),
                "description": song.description or "",
                "year": song.year or 0,
                "duration": song.duration or 0,
                "source": song.source,
            })

        if ids:
            self._collection.add(
                ids=ids,
                embeddings=embeddings,
                documents=documents,
                metadatas=metadatas
            )
            logger.info(f"添加 {len(ids)} 首歌曲到 ChromaDB")

    def search(self, query_embedding: List[float], top_k: int = 10, filters: Optional[Dict] = None) -> List[Dict]:
        """搜索相似歌曲"""
        try:
            where_clause = None
            if filters:
                where_clause = filters

            results = self._collection.query(
                query_embeddings=[query_embedding],
                n_results=top_k,
                where=where_clause,
                include=["metadatas", "distances"]
            )

            songs = []
            if results["ids"] and results["ids"][0]:
                for i, song_id in enumerate(results["ids"][0]):
                    metadata = results["metadatas"][0][i]
                    distance = results["distances"][0][i]

                    # ChromaDB 返回的是距离 (0-2, 0=相同), 转换为相似度 (0-1)
                    similarity = 1 - (distance / 2)

                    song = {
                        "id": song_id,
                        "title": metadata["title"],
                        "artist": metadata["artist"],
                        "album": metadata.get("album", ""),
                        "genre": json.loads(metadata.get("genre", "[]")),
                        "mood": json.loads(metadata.get("mood", "[]")),
                        "scenes": json.loads(metadata.get("scenes", "[]")),
                        "description": metadata.get("description", ""),
                        "year": metadata.get("year"),
                        "duration": metadata.get("duration"),
                        "source": metadata.get("source", "unknown"),
                        "similarity_score": max(0, min(1, similarity)),
                    }
                    songs.append(song)

            return songs

        except Exception as e:
            logger.error(f"搜索失败: {e}")
            return []

    def get_by_artist(self, artist: str, top_k: int = 10) -> List[Dict]:
        """通过艺术家名查找歌曲：精确匹配 → 文档包含 → 去空格模糊匹配"""
        def _make_result(rid, m, score):
            return {
                "id": rid,
                "title": m["title"],
                "artist": m["artist"],
                "album": m.get("album", ""),
                "genre": json.loads(m.get("genre", "[]")),
                "mood": json.loads(m.get("mood", "[]")),
                "description": m.get("description", ""),
                "year": m.get("year"),
                "duration": m.get("duration"),
                "source": m.get("source", "unknown"),
                "similarity_score": score,
            }

        try:
            # 第1步：精确匹配（大小写变体）
            variants = list({artist, artist.lower(), artist.upper(), artist.title()})
            for variant in variants:
                results = self._collection.get(
                    where={"artist": {"$eq": variant}},
                    limit=top_k,
                    include=["metadatas"]
                )
                if results["ids"]:
                    return [_make_result(rid, m, 1.0)
                            for rid, m in zip(results["ids"], results["metadatas"])]

            # 第2步：前缀文档搜索 + 子串匹配（大小写变体）
            # 处理 "selena" → "Selena Gomez"，"selenagomez" → "Selena Gomez"
            artist_nospace = artist.lower().replace(" ", "")
            raw_prefix = artist_nospace[:min(6, len(artist_nospace))]
            prefix_variants = list({raw_prefix, raw_prefix.capitalize(), raw_prefix.upper()})
            for pfx in prefix_variants:
                results = self._collection.get(
                    where_document={"$contains": pfx},
                    limit=200,
                    include=["metadatas"]
                )
                if results["ids"]:
                    # 用去空格子串匹配：artist_nospace ⊆ stored_artist_nospace
                    # 这样 "selena" 匹配 "selenagomez"，"selenagomez" 也匹配自身
                    matched = [_make_result(rid, m, 0.9)
                               for rid, m in zip(results["ids"], results["metadatas"])
                               if artist_nospace in m["artist"].lower().replace(" ", "")]
                    if matched:
                        return matched[:top_k]

            return []
        except Exception as e:
            logger.error(f"按艺术家查找失败: {e}")
            return []

    def count(self) -> int:
        """获取歌曲数量"""
        return self._collection.count()


class RAGMusicSearchV2:
    """RAG 音乐搜索引擎 V2 - 使用真实 Embedding + ChromaDB"""

    def __init__(self, use_chroma: bool = True):
        self.use_chroma = use_chroma

        if use_chroma:
            self.vector_store = ChromaVectorStore()
        else:
            from tools.rag_music_search import SimpleVectorStore
            self.vector_store = SimpleVectorStore()

        # 读取 embedding 配置
        try:
            from config.settings_loader import load_settings_from_json
            settings = load_settings_from_json()
            self._embed_base_url = settings.get("OLLAMA_BASE_URL", "http://localhost:11434/v1")
            self._embed_model = settings.get("OLLAMA_EMBED_MODEL", "bge-m3:latest")
            self._embed_api_key = "ollama"
        except Exception:
            self._embed_base_url = "http://localhost:11434/v1"
            self._embed_model = "bge-m3:latest"
            self._embed_api_key = "ollama"

    async def _create_embedding(self, text: str) -> List[float]:
        """使用本地 Ollama bge-m3 创建文本嵌入"""
        try:
            from openai import AsyncOpenAI
            client = AsyncOpenAI(api_key=self._embed_api_key, base_url=self._embed_base_url)
            resp = await client.embeddings.create(model=self._embed_model, input=text)
            return resp.data[0].embedding
        except Exception as e:
            logger.error(f"生成嵌入失败: {e}")
            return []

    async def build_from_local_db(self) -> int:
        """从本地 JSON 数据库构建索引"""
        if not os.path.exists(self._local_db_path):
            logger.warning(f"本地数据库不存在: {self._local_db_path}")
            return 0

        try:
            with open(self._local_db_path, 'r', encoding='utf-8') as f:
                db_data = json.load(f)

            songs_data = db_data if isinstance(db_data, list) else db_data.get("songs", [])

            songs = []
            for song_data in songs_data:
                try:
                    rag_song = RAGSong(
                        id=song_data.get("id") or f"{song_data.get('title', '')}_{song_data.get('artist', '')}",
                        title=song_data.get("title", "Unknown"),
                        artist=song_data.get("artist", "Unknown Artist"),
                        album=song_data.get("album"),
                        genre=song_data.get("genre"),
                        mood=song_data.get("mood"),
                        scenes=song_data.get("scenes"),
                        description=song_data.get("description"),
                        year=song_data.get("year"),
                        duration=song_data.get("duration"),
                        source=song_data.get("source", "local"),
                        embedding=song_data.get("embedding"),
                    )
                    songs.append(rag_song)
                except Exception as e:
                    logger.debug(f"处理歌曲失败: {e}")
                    continue

            if self.use_chroma:
                self.vector_store.add_songs(songs)
            else:
                # 内存存储需要重新生成嵌入
                pass

            logger.info(f"从本地数据库加载: {len(songs)} 首歌曲")
            return len(songs)

        except Exception as e:
            logger.error(f"加载数据库失败: {e}")
            return 0

    async def search(self, query: str, top_k: int = 10) -> List[Dict[str, Any]]:
        """语义搜索歌曲，自动去重（按 title+artist）"""
        if self.use_chroma and self.vector_store.count() == 0:
            logger.warning("ChromaDB 为空，请先构建数据库")
            return []

        # 生成查询嵌入
        query_embedding = await self._create_embedding(query)
        if not query_embedding:
            return []

        # 多取一些结果以保证去重后仍有 top_k 条
        raw_results = self.vector_store.search(query_embedding, top_k=top_k * 3)

        # 按 (title, artist) 去重，保留相似度最高的
        seen = {}
        for r in raw_results:
            key = (r["title"].lower().strip(), r["artist"].lower().strip())
            if key not in seen or r["similarity_score"] > seen[key]["similarity_score"]:
                seen[key] = r

        deduped = sorted(seen.values(), key=lambda x: x["similarity_score"], reverse=True)
        return deduped[:top_k]

    async def search_by_mood(self, mood: str, top_k: int = 10) -> List[Dict]:
        """根据情绪搜索"""
        # 扩展情绪描述以获得更好的语义匹配
        mood_expansions = {
            "开心": "开心 快乐 愉快 欢乐 upbeat happy joyful",
            "放松": "放松 舒缓 安静 平静 calm relaxing peaceful",
            "专注": "专注 集中 学习 工作 focus concentration study work",
            "悲伤": "悲伤 忧伤  melancholic sad emotional",
            "运动": "运动 跑步 健身 节奏感 workout energetic beat",
            "浪漫": "浪漫 爱情 温柔 romantic love soft gentle",
        }
        expanded_query = mood_expansions.get(mood, mood)
        return await self.search(expanded_query, top_k=top_k)

    async def search_by_activity(self, activity: str, top_k: int = 10) -> List[Dict]:
        """根据活动场景搜索"""
        activity_expansions = {
            "工作": "工作 办公 专注 背景音乐 work focus productive background",
            "学习": "学习 阅读 安静 集中 study reading calm concentration",
            "运动": "运动 健身 跑步 节奏 workout gym running energetic",
            "睡前": "睡前 放松 安眠 轻音乐 sleep bedtime relax ambient",
            "开车": "开车 驾驶 提神 节奏 driving commute upbeat",
        }
        expanded_query = activity_expansions.get(activity, activity)
        return await self.search(expanded_query, top_k=top_k)


# 全局实例
_rag_search_v2: Optional[RAGMusicSearchV2] = None


def get_rag_music_search_v2(use_chroma: bool = True) -> RAGMusicSearchV2:
    """获取 RAG 搜索实例"""
    global _rag_search_v2
    if _rag_search_v2 is None:
        _rag_search_v2 = RAGMusicSearchV2(use_chroma=use_chroma)
    return _rag_search_v2
