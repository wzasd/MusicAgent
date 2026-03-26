"""
多样性排序模块

提供推荐结果多样性增强功能：
1. MMR (Maximal Marginal Relevance) 算法 - 平衡相关性和多样性
2. 艺术家打散 - 避免同一艺术家连续出现
3. 相似度去重 - 基于向量相似度去重
"""

from typing import List, Dict, Any, Optional, Set, Tuple
from collections import defaultdict, deque
import math
import numpy as np


class MMRanker:
    """MMR (Maximal Marginal Relevance) 重排序器

    MMR = λ * Sim(doc, query) - (1-λ) * max Sim(doc, selected_docs)

    通过平衡查询相关性和结果多样性，避免推荐结果过于同质化。
    """

    def __init__(self, lambda_param: float = 0.7):
        """
        Args:
            lambda_param: 相关性权重 (0-1)，越高越注重相关性
                         0.5 = 平衡, 0.7 = 偏向相关性, 0.3 = 偏向多样性
        """
        self.lambda_param = lambda_param

    def rank(
        self,
        documents: List[Dict[str, Any]],
        query_embedding: List[float],
        top_k: int = 10,
        embedding_key: str = "embedding"
    ) -> List[Dict[str, Any]]:
        """MMR 重排序

        Args:
            documents: 候选文档列表，每个文档需要包含 embedding
            query_embedding: 查询向量
            top_k: 返回结果数
            embedding_key: 文档中 embedding 的键名

        Returns:
            MMR 重排序后的文档列表
        """
        if not documents:
            return []

        # 标准化查询向量
        query_embedding = np.array(query_embedding)
        query_norm = np.linalg.norm(query_embedding)
        if query_norm > 0:
            query_embedding = query_embedding / query_norm

        # 准备文档 embedding
        doc_embeddings = []
        for doc in documents:
            emb = doc.get(embedding_key)
            if emb is None:
                # 如果没有 embedding，使用零向量（会被排在后面）
                emb = np.zeros(len(query_embedding))
            else:
                emb = np.array(emb)
                norm = np.linalg.norm(emb)
                if norm > 0:
                    emb = emb / norm
            doc_embeddings.append(emb)

        selected_indices = []
        remaining_indices = list(range(len(documents)))

        while len(selected_indices) < top_k and remaining_indices:
            mmr_scores = []

            for idx in remaining_indices:
                # 相关性得分：与查询的相似度
                sim_to_query = float(np.dot(doc_embeddings[idx], query_embedding))

                # 多样性得分：与已选文档的最大相似度
                if selected_indices:
                    sims_to_selected = [
                        float(np.dot(doc_embeddings[idx], doc_embeddings[s]))
                        for s in selected_indices
                    ]
                    max_sim_to_selected = max(sims_to_selected)
                else:
                    max_sim_to_selected = 0.0

                # MMR 分数
                mmr_score = (
                    self.lambda_param * sim_to_query -
                    (1 - self.lambda_param) * max_sim_to_selected
                )
                mmr_scores.append((idx, mmr_score))

            # 选择 MMR 分数最高的文档
            best_idx, best_score = max(mmr_scores, key=lambda x: x[1])
            selected_indices.append(best_idx)
            remaining_indices.remove(best_idx)

        # 按选择顺序返回文档
        return [documents[i] for i in selected_indices]

    def rank_with_scores(
        self,
        documents: List[Dict[str, Any]],
        query_embedding: List[float],
        top_k: int = 10,
        embedding_key: str = "embedding"
    ) -> List[Tuple[Dict[str, Any], float]]:
        """MMR 重排序并返回分数

        Returns:
            (文档, MMR分数) 的列表
        """
        if not documents:
            return []

        query_embedding = np.array(query_embedding)
        query_norm = np.linalg.norm(query_embedding)
        if query_norm > 0:
            query_embedding = query_embedding / query_norm

        doc_embeddings = []
        for doc in documents:
            emb = doc.get(embedding_key)
            if emb is None:
                emb = np.zeros(len(query_embedding))
            else:
                emb = np.array(emb)
                norm = np.linalg.norm(emb)
                if norm > 0:
                    emb = emb / norm
            doc_embeddings.append(emb)

        selected_indices = []
        selected_scores = []
        remaining_indices = list(range(len(documents)))

        while len(selected_indices) < top_k and remaining_indices:
            mmr_scores = []

            for idx in remaining_indices:
                sim_to_query = float(np.dot(doc_embeddings[idx], query_embedding))

                if selected_indices:
                    sims_to_selected = [
                        float(np.dot(doc_embeddings[idx], doc_embeddings[s]))
                        for s in selected_indices
                    ]
                    max_sim_to_selected = max(sims_to_selected)
                else:
                    max_sim_to_selected = 0.0

                mmr_score = (
                    self.lambda_param * sim_to_query -
                    (1 - self.lambda_param) * max_sim_to_selected
                )
                mmr_scores.append((idx, mmr_score))

            best_idx, best_score = max(mmr_scores, key=lambda x: x[1])
            selected_indices.append(best_idx)
            selected_scores.append(best_score)
            remaining_indices.remove(best_idx)

        return [(documents[i], score) for i, score in zip(selected_indices, selected_scores)]


def dither_by_artist(
    songs: List[Dict[str, Any]],
    max_consecutive_same_artist: int = 2,
    artist_key: str = "artist"
) -> List[Dict[str, Any]]:
    """艺术家打散重排

    使用 Round-Robin 风格打散，避免同一艺术家连续出现。
    同时保留相似度的大致顺序。

    Args:
        songs: 歌曲列表
        max_consecutive_same_artist: 允许同一艺术家连续出现的最大次数
        artist_key: 艺术家字段名

    Returns:
        打散后的歌曲列表
    """
    if not songs:
        return []

    if len(songs) <= 2:
        return songs.copy()

    # 按艺术家分组，同时保留原始顺序
    artist_groups = defaultdict(deque)
    for i, song in enumerate(songs):
        artist = str(song.get(artist_key, "Unknown")).strip()
        # 使用 (原始索引, 歌曲) 保持组内顺序
        artist_groups[artist].append((i, song))

    # 轮询取歌，优先从数量多的组取
    result = []
    last_artists = []  # 记录最近使用的艺术家

    while artist_groups:
        # 按组大小降序排序，优先从大的组取
        sorted_artists = sorted(
            artist_groups.keys(),
            key=lambda a: len(artist_groups[a]),
            reverse=True
        )

        # 跳过最近使用过的艺术家（如果有其他选择）
        for artist in sorted_artists:
            if artist in last_artists and len(sorted_artists) > 1:
                continue

            if artist_groups[artist]:
                idx, song = artist_groups[artist].popleft()
                result.append(song)

                # 更新最近使用记录
                last_artists.append(artist)
                if len(last_artists) > max_consecutive_same_artist:
                    last_artists.pop(0)

                # 清理空组
                if not artist_groups[artist]:
                    del artist_groups[artist]

                break
        else:
            # 所有艺术家都被跳过，强制取一个
            artist = sorted_artists[0]
            if artist_groups[artist]:
                idx, song = artist_groups[artist].popleft()
                result.append(song)
                last_artists = [artist]
                if not artist_groups[artist]:
                    del artist_groups[artist]

        if len(result) >= len(songs):
            break

    return result


def dither_by_field(
    items: List[Dict[str, Any]],
    field: str,
    max_consecutive_same: int = 2
) -> List[Dict[str, Any]]:
    """通用字段打散重排

    Args:
        items: 项目列表
        field: 要打散的字段名
        max_consecutive_same: 允许同一值连续出现的最大次数

    Returns:
        打散后的列表
    """
    if not items:
        return []

    if len(items) <= 2:
        return items.copy()

    # 按字段分组
    field_groups = defaultdict(deque)
    for item in items:
        value = str(item.get(field, "Unknown")).strip()
        field_groups[value].append(item)

    # 轮询取项
    result = []
    last_values = []

    while field_groups:
        sorted_values = sorted(
            field_groups.keys(),
            key=lambda v: len(field_groups[v]),
            reverse=True
        )

        for value in sorted_values:
            if value in last_values and len(sorted_values) > 1:
                continue

            if field_groups[value]:
                result.append(field_groups[value].popleft())
                last_values.append(value)
                if len(last_values) > max_consecutive_same:
                    last_values.pop(0)

                if not field_groups[value]:
                    del field_groups[value]
                break
        else:
            value = sorted_values[0]
            if field_groups[value]:
                result.append(field_groups[value].popleft())
                last_values = [value]
                if not field_groups[value]:
                    del field_groups[value]

        if len(result) >= len(items):
            break

    return result


def deduplicate_by_similarity(
    documents: List[Dict[str, Any]],
    threshold: float = 0.95,
    embedding_key: str = "embedding",
    keep_first: bool = True
) -> List[Dict[str, Any]]:
    """基于向量相似度的去重

    如果两个文档的相似度超过阈值，认为是重复的。

    Args:
        documents: 文档列表
        threshold: 相似度阈值（0-1），超过则认为是重复
        embedding_key: embedding 字段名
        keep_first: 保留第一个还是相似度最高的

    Returns:
        去重后的文档列表
    """
    if not documents:
        return []

    if len(documents) <= 1:
        return documents.copy()

    # 准备 embedding
    embeddings = []
    for doc in documents:
        emb = doc.get(embedding_key)
        if emb is None:
            embeddings.append(None)
        else:
            emb = np.array(emb)
            norm = np.linalg.norm(emb)
            if norm > 0:
                emb = emb / norm
            embeddings.append(emb)

    to_remove = set()

    for i in range(len(documents)):
        if i in to_remove or embeddings[i] is None:
            continue

        for j in range(i + 1, len(documents)):
            if j in to_remove or embeddings[j] is None:
                continue

            similarity = float(np.dot(embeddings[i], embeddings[j]))

            if similarity >= threshold:
                # 认为是重复的
                if keep_first:
                    to_remove.add(j)
                else:
                    # 比较原始相似度分数，保留高的
                    score_i = documents[i].get("similarity_score", 0)
                    score_j = documents[j].get("similarity_score", 0)
                    if score_i >= score_j:
                        to_remove.add(j)
                    else:
                        to_remove.add(i)

    return [doc for i, doc in enumerate(documents) if i not in to_remove]


def compute_diversity_score(
    documents: List[Dict[str, Any]],
    embedding_key: str = "embedding"
) -> float:
    """计算结果列表的多样性分数

    使用平均成对距离作为多样性度量。

    Args:
        documents: 文档列表
        embedding_key: embedding 字段名

    Returns:
        多样性分数 (0-1)，越高表示多样性越好
    """
    if not documents or len(documents) < 2:
        return 0.0

    # 准备 embedding
    embeddings = []
    for doc in documents:
        emb = doc.get(embedding_key)
        if emb is not None:
            emb = np.array(emb)
            norm = np.linalg.norm(emb)
            if norm > 0:
                emb = emb / norm
            embeddings.append(emb)

    if len(embeddings) < 2:
        return 0.0

    # 计算平均成对距离
    total_distance = 0.0
    count = 0

    for i in range(len(embeddings)):
        for j in range(i + 1, len(embeddings)):
            # 余弦距离 = 1 - 余弦相似度
            distance = 1 - float(np.dot(embeddings[i], embeddings[j]))
            total_distance += distance
            count += 1

    if count == 0:
        return 0.0

    # 归一化到 0-1
    avg_distance = total_distance / count
    return min(avg_distance, 1.0)


# 便捷函数：一站式多样性增强
def enhance_diversity(
    documents: List[Dict[str, Any]],
    query_embedding: List[float],
    top_k: int = 10,
    mmr_lambda: float = 0.7,
    enable_mmr: bool = True,
    enable_dithering: bool = True,
    dither_by: str = "artist",
    similarity_threshold: float = 0.95,
    embedding_key: str = "embedding"
) -> Dict[str, Any]:
    """一站式多样性增强

    执行完整的多样性增强流程：
    1. 相似度去重
    2. MMR 重排序
    3. 艺术家/字段打散

    Args:
        documents: 候选文档列表
        query_embedding: 查询向量
        top_k: 返回结果数
        mmr_lambda: MMR 相关性权重
        enable_mmr: 是否启用 MMR
        enable_dithering: 是否启用打散
        dither_by: 打散字段名
        similarity_threshold: 去重相似度阈值
        embedding_key: embedding 字段名

    Returns:
        {
            "results": 增强后的结果列表,
            "diversity_score": 多样性分数,
            "original_count": 原始数量,
            "final_count": 最终数量
        }
    """
    original_count = len(documents)

    # 1. 相似度去重
    documents = deduplicate_by_similarity(
        documents, threshold=similarity_threshold, embedding_key=embedding_key
    )

    # 2. MMR 重排序
    if enable_mmr and query_embedding is not None:
        ranker = MMRanker(lambda_param=mmr_lambda)
        documents = ranker.rank(
            documents, query_embedding, top_k=top_k * 2, embedding_key=embedding_key
        )

    # 3. 打散
    if enable_dithering and documents:
        documents = dither_by_field(documents, field=dither_by, max_consecutive_same=2)

    # 4. 截取最终数量
    final_results = documents[:top_k]

    # 5. 计算多样性分数
    diversity_score = compute_diversity_score(final_results, embedding_key=embedding_key)

    return {
        "results": final_results,
        "diversity_score": diversity_score,
        "original_count": original_count,
        "final_count": len(final_results)
    }
