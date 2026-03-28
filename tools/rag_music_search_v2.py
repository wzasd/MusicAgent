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
from tools.diversity_ranker import MMRanker, dither_by_field
from services.user_history_service import UserHistoryService, get_history_service

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

        # 初始化 Embedding 缓存
        from utils.cache import SimpleCache
        self._embedding_cache = SimpleCache(max_size=10000, ttl=3600)

        if use_chroma:
            self.vector_store = ChromaVectorStore()
        else:
            from tools.rag_music_search import SimpleVectorStore
            self.vector_store = SimpleVectorStore()

        # 读取 embedding 配置
        # 优先级：EMBED_API_KEY > SILICONFLOW_API_KEY > "ollama"（本地 Ollama 默认值）
        try:
            from config.settings_loader import load_settings_from_json
            settings = load_settings_from_json()
            self._embed_base_url = settings.get("OLLAMA_BASE_URL", "http://localhost:11434/v1")
            self._embed_model = settings.get("OLLAMA_EMBED_MODEL", "bge-m3:latest")
            self._embed_api_key = (
                settings.get("EMBED_API_KEY")
                or settings.get("SILICONFLOW_API_KEY")
                or "ollama"
            )
        except Exception:
            self._embed_base_url = "http://localhost:11434/v1"
            self._embed_model = "bge-m3:latest"
            self._embed_api_key = "ollama"

        # 初始化多样性组件
        self.diversity_ranker = MMRanker()
        self._user_history: Optional[UserHistoryService] = None

    async def _create_embedding(self, text: str) -> List[float]:
        """使用本地 Ollama bge-m3 创建文本嵌入（带缓存）"""
        # 检查缓存
        cache_key = self._embedding_cache._hash_key(text)
        cached = await self._embedding_cache.get(cache_key)
        if cached:
            logger.debug(f"Embedding cache hit: {text[:32]}...")
            return cached

        # 未命中， 调用 API
        try:
            from openai import AsyncOpenAI
            client = AsyncOpenAI(api_key=self._embed_api_key, base_url=self._embed_base_url)
            resp = await client.embeddings.create(model=self._embed_model, input=text)
            embedding = resp.data[0].embedding

            # 缓存结果
            await self._embedding_cache.set(cache_key, embedding)
            logger.debug(f"Embedding cached: {text[:32]}...")

            return embedding
        except Exception as e:
            logger.error(f"生成嵌入失败: {e}")
            return []

    def get_user_history(self) -> UserHistoryService:
        """获取用户历史服务（延迟初始化）"""
        if self._user_history is None:
            try:
                from config.settings_loader import load_settings_from_json
                settings = load_settings_from_json()
                storage_path = settings.get("USER_HISTORY_PATH", "./data/user_histories")
                enable_persistence = settings.get("ENABLE_HISTORY_PERSISTENCE", False)
            except Exception:
                storage_path = "./data/user_histories"
                enable_persistence = False

            self._user_history = get_history_service(
                storage_path=storage_path,
                enable_persistence=enable_persistence
            )
        return self._user_history

    async def search_with_diversity(
        self,
        query: str,
        top_k: int = 10,
        session_id: Optional[str] = None,
        enable_mmr: bool = True,
        enable_dithering: bool = True,
        mmr_lambda: float = 0.7,
        candidate_multiplier: int = 5,
        randomness: float = 0.1,
        temperature: float = 1.2,
        **kwargs
    ) -> List[Dict[str, Any]]:
        """带多样性的搜索

        流程：
        1. 获取更大的候选池 (top_k * candidate_multiplier)，带随机扰动
        2. 过滤用户历史（避免重复推荐）
        3. 为候选添加 embedding
        4. MMR 重排序
        5. 艺术家打散
        6. 记录到用户历史

        Args:
            query: 搜索查询
            top_k: 返回结果数
            session_id: 用户会话 ID（用于历史去重）
            enable_mmr: 是否启用 MMR 重排序
            enable_dithering: 是否启用艺术家打散
            mmr_lambda: MMR 相关性权重 (0-1)，越高越注重相关性
            candidate_multiplier: 候选池扩大倍数
            randomness: 随机扰动强度 (0-1)，越大结果越多样
            temperature: 采样温度，>1 增加多样性
            **kwargs: 其他搜索参数

        Returns:
            多样性增强后的结果列表
        """
        if self.use_chroma and self.vector_store.count() == 0:
            logger.warning("ChromaDB 为空，请先构建数据库")
            return []

        # 1. 获取更大的候选池，启用随机性
        candidate_count = top_k * candidate_multiplier
        candidates = await self.search(
            query,
            top_k=candidate_count,
            randomness=randomness,
            temperature=temperature
        )

        if not candidates:
            return []

        # 2. 用户历史去重
        if session_id:
            user_history = self.get_user_history()
            candidates = user_history.filter_seen_songs(session_id, candidates)
            logger.debug(f"用户历史过滤后剩余 {len(candidates)} 首候选歌曲")

        if not candidates:
            logger.warning("所有候选歌曲都在用户历史中，无法去重推荐")
            return []

        # 3. 为候选歌曲添加 embedding（MMR 需要）
        query_embedding = await self._create_embedding(query)
        if not query_embedding:
            # Embedding 失败，返回普通结果
            return candidates[:top_k]

        # 获取候选歌曲的 embeddings
        # 注意：由于 ChromaDB 查询返回的结果不包含 embedding，
        # 我们需要重新查询或使用向量存储的原始方法
        for candidate in candidates:
            # 如果没有 embedding，用一个占位符（后续 MMR 会处理为 0 向量）
            if "embedding" not in candidate:
                candidate["embedding"] = None

        # 4. MMR 重排序
        if enable_mmr and candidates:
            self.diversity_ranker.lambda_param = mmr_lambda
            # MMR 需要更多候选来产生多样化结果，留余量给打散
            mmr_results = self.diversity_ranker.rank(
                candidates,
                query_embedding,
                top_k=top_k * 2,
                embedding_key="embedding"
            )
            candidates = mmr_results
            logger.debug(f"MMR 重排序后剩余 {len(candidates)} 首歌曲")

        # 5. 艺术家打散
        if enable_dithering and candidates:
            candidates = dither_by_field(
                candidates,
                field="artist",
                max_consecutive_same=2
            )
            logger.debug(f"艺术家打散后剩余 {len(candidates)} 首歌曲")

        # 6. 截取最终数量
        final_results = candidates[:top_k]

        # 7. 记录到用户历史
        if session_id and final_results:
            user_history = self.get_user_history()
            user_history.add_to_history(
                session_id=session_id,
                songs=final_results,
                query=query,
                source="rag_diversity"
            )
            logger.debug(f"已将 {len(final_results)} 首歌曲添加到用户历史")

        return final_results

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

    async def search(
        self,
        query: str,
        top_k: int = 10,
        randomness: float = 0.0,
        temperature: float = 1.0
    ) -> List[Dict[str, Any]]:
        """语义搜索歌曲，自动去重（按 title+artist）

        Args:
            query: 搜索查询
            top_k: 返回结果数
            randomness: 随机扰动强度 (0-1)，越大结果越多样
            temperature: 采样温度，>1 增加多样性，<1 增加确定性
        """
        if self.use_chroma and self.vector_store.count() == 0:
            logger.warning("ChromaDB 为空，请先构建数据库")
            return []

        # 生成查询嵌入
        query_embedding = await self._create_embedding(query)
        if not query_embedding:
            return []

        # 添加随机扰动到查询 embedding（如果启用随机性）
        if randomness > 0:
            query_embedding = self._add_embedding_noise(query_embedding, randomness)

        # 多取一些结果以保证去重后仍有足够候选
        # 如果有随机性，获取更多的候选以供随机采样
        candidate_multiplier = 5 if randomness > 0 else 3
        raw_results = self.vector_store.search(query_embedding, top_k=top_k * candidate_multiplier)

        # 按 (title, artist) 去重，保留相似度最高的
        seen = {}
        for r in raw_results:
            key = (r["title"].lower().strip(), r["artist"].lower().strip())
            if key not in seen or r["similarity_score"] > seen[key]["similarity_score"]:
                seen[key] = r

        deduped = list(seen.values())

        # 应用温度采样（如果启用随机性）
        if randomness > 0 and temperature != 1.0 and len(deduped) > top_k:
            deduped = self._apply_temperature_sampling(deduped, temperature, top_k)
        else:
            deduped = sorted(deduped, key=lambda x: x["similarity_score"], reverse=True)

        return deduped[:top_k]

    def _add_embedding_noise(self, embedding: List[float], intensity: float) -> List[float]:
        """向 embedding 添加随机扰动以增加多样性

        Args:
            embedding: 原始 embedding 向量
            intensity: 扰动强度 (0-1)

        Returns:
            添加噪声后的 embedding
        """
        import random

        emb_array = np.array(embedding)

        # 生成高斯噪声，强度与 embedding 范数相关
        noise = np.random.normal(0, intensity * 0.1, emb_array.shape)

        # 添加噪声并重新归一化
        noisy_emb = emb_array + noise
        norm = np.linalg.norm(noisy_emb)
        if norm > 0:
            noisy_emb = noisy_emb / norm

        return noisy_emb.tolist()

    def _apply_temperature_sampling(
        self,
        candidates: List[Dict[str, Any]],
        temperature: float,
        top_k: int
    ) -> List[Dict[str, Any]]:
        """应用温度采样从候选池中选择结果

        温度 > 1: 增加低分候选被选择的机会（更多样）
        温度 < 1: 更倾向于高分候选（更确定）

        Args:
            candidates: 候选歌曲列表
            temperature: 采样温度
            top_k: 需要返回的数量

        Returns:
            采样后的结果
        """
        import random

        if not candidates or temperature == 1.0:
            return sorted(candidates, key=lambda x: x["similarity_score"], reverse=True)

        # 基于相似度分数计算选择概率
        scores = np.array([c["similarity_score"] for c in candidates])

        # 应用温度缩放
        # 温度越高，概率分布越平缓；温度越低，概率分布越尖锐
        if temperature != 1.0:
            # 将分数转换为 logits 并应用温度
            # 使用 softmax 的逆温度形式
            exp_scores = np.exp(scores / temperature)
            probabilities = exp_scores / np.sum(exp_scores)
        else:
            probabilities = scores / np.sum(scores)

        # 确保概率有效
        probabilities = np.nan_to_num(probabilities, nan=1.0 / len(candidates))
        if probabilities.sum() == 0:
            probabilities = np.ones(len(candidates)) / len(candidates)

        # 无放回采样 top_k 个结果
        selected_indices = np.random.choice(
            len(candidates),
            size=min(top_k * 2, len(candidates)),  # 多采一些以供后续排序
            replace=False,
            p=probabilities
        )

        # 按原始相似度排序采样结果
        selected = [candidates[i] for i in selected_indices]
        return sorted(selected, key=lambda x: x["similarity_score"], reverse=True)

    async def search_by_mood(self, mood: str, top_k: int = 10, randomness: float = 0.15, temperature: float = 1.5) -> List[Dict]:
        """根据情绪搜索

        Args:
            mood: 情绪标签
            top_k: 返回结果数
            randomness: 随机扰动强度 (0-1)
            temperature: 采样温度，>1 增加多样性
        """
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
        return await self.search(expanded_query, top_k=top_k, randomness=randomness, temperature=temperature)

    async def search_by_activity(self, activity: str, top_k: int = 10, randomness: float = 0.15, temperature: float = 1.5) -> List[Dict]:
        """根据活动场景搜索

        Args:
            activity: 活动描述
            top_k: 返回结果数
            randomness: 随机扰动强度 (0-1)
            temperature: 采样温度，>1 增加多样性
        """
        activity_expansions = {
            "工作": "工作 办公 专注 背景音乐 work focus productive background",
            "学习": "学习 阅读 安静 集中 study reading calm concentration",
            "运动": "运动 健身 跑步 节奏 workout gym running energetic",
            "睡前": "睡前 放松 安眠 轻音乐 sleep bedtime relax ambient",
            "开车": "开车 驾驶 提神 节奏 driving commute upbeat",
        }
        expanded_query = activity_expansions.get(activity, activity)
        return await self.search(expanded_query, top_k=top_k, randomness=randomness, temperature=temperature)


# 全局实例
_rag_search_v2: Optional[RAGMusicSearchV2] = None


def get_rag_music_search_v2(use_chroma: bool = True) -> RAGMusicSearchV2:
    """获取 RAG 搜索实例"""
    global _rag_search_v2
    if _rag_search_v2 is None:
        _rag_search_v2 = RAGMusicSearchV2(use_chroma=use_chroma)
    return _rag_search_v2
