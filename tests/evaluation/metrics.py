"""
RAG 评估指标实现

提供检索质量和端到端效果的评估指标：
- Recall@K: 前 K 个结果中命中相关文档的比例
- Precision@K: 前 K 个结果的精确率
- NDCG@K: 考虑排序位置的归一化折扣累积增益
- MRR: 第一个相关文档的倒数排名
- MAP: 平均精确率均值
"""

from typing import List, Dict, Any, Optional
import math


def compute_recall_at_k(
    results: List[Dict[str, Any]],
    relevant_items: List[Dict[str, Any]],
    k: int = 10,
    key_field: str = "title"
) -> float:
    """
    计算 Recall@K

    Args:
        results: 检索结果列表
        relevant_items: 相关文档列表
        k: 考虑的前 K 个结果
        key_field: 用于匹配的关键字段

    Returns:
        Recall@K 值 (0-1)
    """
    if not relevant_items:
        return 0.0

    # 提取前 K 个结果的 key
    result_keys = {str(r.get(key_field, "")).lower().strip() for r in results[:k]}

    # 提取相关文档的 key
    relevant_keys = {str(r.get(key_field, "")).lower().strip() for r in relevant_items}

    # 计算命中数
    hits = len(result_keys & relevant_keys)

    return hits / len(relevant_keys)


def compute_precision_at_k(
    results: List[Dict[str, Any]],
    relevant_items: List[Dict[str, Any]],
    k: int = 10,
    key_field: str = "title"
) -> float:
    """
    计算 Precision@K

    Args:
        results: 检索结果列表
        relevant_items: 相关文档列表
        k: 考虑的前 K 个结果
        key_field: 用于匹配的关键字段

    Returns:
        Precision@K 值 (0-1)
    """
    if k == 0 or not results:
        return 0.0

    # 提取相关文档的 key 集合
    relevant_keys = {str(r.get(key_field, "")).lower().strip() for r in relevant_items}

    # 计算前 K 个中的命中数
    hits = sum(
        1 for r in results[:k]
        if str(r.get(key_field, "")).lower().strip() in relevant_keys
    )

    return hits / min(k, len(results))


def compute_dcg_at_k(relevances: List[float], k: int) -> float:
    """
    计算 DCG@K (Discounted Cumulative Gain)

    Args:
        relevances: 相关性分数列表（已按排名排序）
        k: 考虑的前 K 个结果

    Returns:
        DCG@K 值
    """
    dcg = 0.0
    for i, rel in enumerate(relevances[:k]):
        # 使用 +2 因为排名从 1 开始，而 i 从 0 开始
        dcg += rel / math.log2(i + 2)
    return dcg


def compute_ndcg_at_k(
    results: List[Dict[str, Any]],
    relevant_items: List[Dict[str, Any]],
    k: int = 10,
    key_field: str = "title",
    relevance_field: str = "relevance"
) -> float:
    """
    计算 NDCG@K (Normalized Discounted Cumulative Gain)

    Args:
        results: 检索结果列表
        relevant_items: 相关文档列表（包含相关性分数）
        k: 考虑的前 K 个结果
        key_field: 用于匹配的关键字段
        relevance_field: 相关性分数字段

    Returns:
        NDCG@K 值 (0-1)
    """
    if not relevant_items:
        return 0.0

    # 构建相关文档的映射（key -> relevance）
    relevance_map = {
        str(r.get(key_field, "")).lower().strip(): r.get(relevance_field, 1.0)
        for r in relevant_items
    }

    # 构建实际结果的相关性列表
    actual_relevances = []
    for r in results[:k]:
        key = str(r.get(key_field, "")).lower().strip()
        actual_relevances.append(relevance_map.get(key, 0.0))

    # 构建理想相关性列表（按相关性降序）
    ideal_relevances = sorted(relevance_map.values(), reverse=True)[:k]

    # 计算 DCG 和 IDCG
    dcg = compute_dcg_at_k(actual_relevances, k)
    idcg = compute_dcg_at_k(ideal_relevances, k)

    if idcg == 0:
        return 0.0

    return dcg / idcg


def compute_mrr(
    results: List[Dict[str, Any]],
    relevant_items: List[Dict[str, Any]],
    key_field: str = "title"
) -> float:
    """
    计算 MRR (Mean Reciprocal Rank)

    Args:
        results: 检索结果列表
        relevant_items: 相关文档列表
        key_field: 用于匹配的关键字段

    Returns:
        MRR 值 (0-1)
    """
    if not relevant_items:
        return 0.0

    # 提取相关文档的 key 集合
    relevant_keys = {str(r.get(key_field, "")).lower().strip() for r in relevant_items}

    # 找到第一个相关文档的排名
    for i, r in enumerate(results):
        key = str(r.get(key_field, "")).lower().strip()
        if key in relevant_keys:
            return 1.0 / (i + 1)

    return 0.0


def compute_ap(
    results: List[Dict[str, Any]],
    relevant_items: List[Dict[str, Any]],
    key_field: str = "title"
) -> float:
    """
    计算 AP (Average Precision)

    Args:
        results: 检索结果列表
        relevant_items: 相关文档列表
        key_field: 用于匹配的关键字段

    Returns:
        AP 值 (0-1)
    """
    if not relevant_items:
        return 0.0

    # 提取相关文档的 key 集合
    relevant_keys = {str(r.get(key_field, "")).lower().strip() for r in relevant_items}

    # 计算每个位置的精确率
    precisions = []
    num_hits = 0

    for i, r in enumerate(results):
        key = str(r.get(key_field, "")).lower().strip()
        if key in relevant_keys:
            num_hits += 1
            precisions.append(num_hits / (i + 1))

    if not precisions:
        return 0.0

    return sum(precisions) / len(relevant_keys)


def compute_hit_rate_at_k(
    results: List[Dict[str, Any]],
    relevant_items: List[Dict[str, Any]],
    k: int = 10,
    key_field: str = "title"
) -> float:
    """
    计算 Hit Rate@K (是否有至少一个相关文档在前 K 个结果中)

    Args:
        results: 检索结果列表
        relevant_items: 相关文档列表
        k: 考虑的前 K 个结果
        key_field: 用于匹配的关键字段

    Returns:
        Hit Rate (0 或 1)
    """
    if not relevant_items:
        return 0.0

    # 提取相关文档的 key 集合
    relevant_keys = {str(r.get(key_field, "")).lower().strip() for r in relevant_items}

    # 检查前 K 个结果中是否有相关文档
    for r in results[:k]:
        key = str(r.get(key_field, "")).lower().strip()
        if key in relevant_keys:
            return 1.0

    return 0.0


def evaluate_retrieval(
    results: List[Dict[str, Any]],
    relevant_items: List[Dict[str, Any]],
    k_values: List[int] = [1, 3, 5, 10],
    key_field: str = "title",
    relevance_field: str = "relevance"
) -> Dict[str, Any]:
    """
    综合评估检索质量

    Args:
        results: 检索结果列表
        relevant_items: 相关文档列表
        k_values: 需要计算的 K 值列表
        key_field: 用于匹配的关键字段
        relevance_field: 相关性分数字段

    Returns:
        包含所有指标的字典
    """
    metrics = {
        "mrr": compute_mrr(results, relevant_items, key_field),
        "ap": compute_ap(results, relevant_items, key_field),
    }

    # 计算各 K 值的指标
    for k in k_values:
        metrics[f"recall@{k}"] = compute_recall_at_k(results, relevant_items, k, key_field)
        metrics[f"precision@{k}"] = compute_precision_at_k(results, relevant_items, k, key_field)
        metrics[f"ndcg@{k}"] = compute_ndcg_at_k(results, relevant_items, k, key_field, relevance_field)
        metrics[f"hit_rate@{k}"] = compute_hit_rate_at_k(results, relevant_items, k, key_field)

    return metrics


def compare_metrics(
    current: Dict[str, float],
    baseline: Dict[str, float],
    warning_threshold: float = 0.05,
    error_threshold: float = 0.10
) -> List[Dict[str, Any]]:
    """
    对比当前指标与基线，检测回归

    Args:
        current: 当前指标值
        baseline: 基线指标值
        warning_threshold: 警告阈值（下降比例）
        error_threshold: 错误阈值（下降比例）

    Returns:
        回归警报列表
    """
    alerts = []

    for metric_name, current_value in current.items():
        if metric_name not in baseline:
            continue

        baseline_value = baseline[metric_name]
        change = current_value - baseline_value
        change_ratio = change / baseline_value if baseline_value != 0 else 0

        if change_ratio <= -error_threshold:
            alerts.append({
                "metric": metric_name,
                "severity": "error",
                "previous": baseline_value,
                "current": current_value,
                "change": change,
                "change_ratio": change_ratio
            })
        elif change_ratio <= -warning_threshold:
            alerts.append({
                "metric": metric_name,
                "severity": "warning",
                "previous": baseline_value,
                "current": current_value,
                "change": change,
                "change_ratio": change_ratio
            })

    return alerts


# 用于 LLM 评估的提示模板
ANSWER_RELEVANCE_PROMPT = """\
请评估以下推荐结果与用户查询的相关性。

用户查询: {query}

推荐结果:
{recommendations}

请从 1-5 分评估相关性：
1 - 完全不相关
2 - 稍微相关
3 - 一般相关
4 - 非常相关
5 - 完美匹配

请以 JSON 格式返回：
{{
    "score": 分数,
    "reason": "评分理由"
}}
"""

FAITHFULNESS_PROMPT = """\
请评估推荐结果是否忠实于检索到的上下文（防止幻觉）。

检索到的上下文:
{context}

推荐结果:
{recommendations}

请检查每个推荐是否有检索上下文的支持。
请以 JSON 格式返回：
{{
    "faithfulness_score": 0-1 的分数,
    "unsupported_items": ["不支持的推荐项"],
    "analysis": "分析说明"
}}
"""

CONTEXT_PRECISION_PROMPT = """\
请评估检索到的上下文中有多少比例对回答问题是有用的。

用户查询: {query}

检索到的上下文:
{context}

请评估有用上下文的比例。
请以 JSON 格式返回：
{{
    "precision_score": 0-1 的分数,
    "useful_count": 有用的文档数量,
    "total_count": 总文档数量,
    "analysis": "分析说明"
}}
"""

CONTEXT_RECALL_PROMPT = """\
请评估回答问题所需的上下文有多少被成功检索到。

用户查询: {query}

检索到的上下文:
{context}

已知的相关文档（ground truth）:
{ground_truth}

请评估检索覆盖程度。
请以 JSON 格式返回：
{{
    "recall_score": 0-1 的分数,
    "retrieved_relevant_count": 检索到的相关文档数量,
    "total_relevant_count": 总相关文档数量,
    "analysis": "分析说明"
}}
"""
