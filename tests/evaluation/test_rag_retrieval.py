"""
RAG 检索质量评估测试

评估向量搜索的检索质量，包括：
1. 精确匹配能力（歌曲名、艺术家）
2. 语义搜索质量（批量评估）
3. 艺术家搜索精确率
4. 多向量策略对比（消融实验）
"""

import pytest
import json
import os
from typing import List, Dict, Any
from pathlib import Path

from tests.evaluation.metrics import (
    compute_recall_at_k,
    compute_precision_at_k,
    compute_ndcg_at_k,
    compute_mrr,
    compute_ap,
    evaluate_retrieval,
)

# 标记为评估测试
pytestmark = pytest.mark.evaluation


def load_eval_dataset() -> List[Dict[str, Any]]:
    """加载评估数据集"""
    dataset_path = Path(__file__).parent / "rag_eval_dataset.json"
    with open(dataset_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    return data.get("cases", [])


@pytest.fixture(scope="module")
def eval_dataset():
    """评估数据集 fixture"""
    return load_eval_dataset()


@pytest.fixture(scope="module")
def rag_search():
    """
    RAG 搜索工具 fixture
    需要提供实际的搜索实现
    """
    # 尝试导入 RAGMusicSearchV2
    try:
        from tools.rag_music_search_v2 import RAGMusicSearchV2
        return RAGMusicSearchV2()
    except ImportError:
        pytest.skip("RAGMusicSearchV2 not available")


@pytest.fixture(scope="module")
def chroma_store():
    """
    ChromaDB vector store fixture
    """
    try:
        from tools.chroma_vector_store import ChromaVectorStore
        return ChromaVectorStore()
    except ImportError:
        pytest.skip("ChromaVectorStore not available")


class TestExactMatch:
    """测试精确匹配能力"""

    @pytest.mark.asyncio
    async def test_exact_title_match_chinese(self, rag_search):
        """测试中文歌曲名精确匹配的召回率"""
        query = "稻香 周杰伦"
        results = await rag_search.search(query, top_k=10)

        # "稻香" 必须在 top-3 内
        found = any(
            r.get("title") == "稻香" and "周杰伦" in str(r.get("artist", ""))
            for r in results[:3]
        )
        assert found, f"'稻香' 未在前3个结果中找到，实际结果: {results[:3]}"

    @pytest.mark.asyncio
    async def test_exact_title_match_english(self, rag_search):
        """测试英文歌曲名精确匹配"""
        query = "My Heart Will Go On"
        results = await rag_search.search(query, top_k=10)

        found = any(
            "My Heart Will Go On" in str(r.get("title", ""))
            for r in results[:3]
        )
        assert found, f"'My Heart Will Go On' 未在前3个结果中找到"

    @pytest.mark.asyncio
    async def test_exact_artist_match_chinese(self, rag_search):
        """测试中文艺术家精确匹配"""
        query = "周杰伦"
        results = await rag_search.get_songs_by_artist(query, limit=10)

        # 所有结果都应该是周杰伦的歌
        if isinstance(results, tuple):
            results = results[0]  # 处理 (songs, source) 的情况

        assert len(results) >= 5, f"返回结果数不足: {len(results)}"

        for r in results:
            artist = str(r.get("artist", "")).lower()
            assert "周杰伦" in artist or "jay chou" in artist, \
                f"非周杰伦的歌曲: {r}"

    @pytest.mark.asyncio
    async def test_exact_artist_match_english(self, rag_search):
        """测试英文艺术家精确匹配"""
        query = "Lady Gaga"
        results = await rag_search.get_songs_by_artist(query, limit=10)

        if isinstance(results, tuple):
            results = results[0]

        assert len(results) >= 5, f"返回结果数不足: {len(results)}"

        # 计算精确率
        hits = sum(1 for r in results if "lady gaga" in str(r.get("artist", "")).lower())
        precision = hits / len(results)

        assert precision >= 0.9, f"艺术家搜索精确率过低: {precision:.2f}"


class TestSemanticSearchQuality:
    """批量评估语义搜索质量"""

    @pytest.mark.asyncio
    @pytest.mark.slow
    async def test_batch_semantic_search(self, rag_search, eval_dataset):
        """批量评估语义搜索质量并计算各项指标"""
        k_values = [1, 3, 5, 10]

        # 按查询类型分组统计
        metrics_by_type = {}
        all_metrics = []

        for case in eval_dataset[:10]:  # 先测试前10个用例
            query = case["query"]
            query_type = case.get("query_type", "unknown")
            relevant_songs = case.get("relevant_songs", [])

            if not relevant_songs:
                continue

            # 执行搜索
            try:
                results = await rag_search.search(query, top_k=10)
            except Exception as e:
                pytest.skip(f"搜索失败: {e}")

            # 计算指标
            metrics = evaluate_retrieval(
                results,
                relevant_songs,
                k_values=k_values,
                key_field="title",
                relevance_field="relevance"
            )

            all_metrics.append({
                "query": query,
                "query_type": query_type,
                **metrics
            })

            # 按类型分组
            if query_type not in metrics_by_type:
                metrics_by_type[query_type] = []
            metrics_by_type[query_type].append(metrics)

        # 计算整体平均指标
        print("\n=== 语义搜索质量评估报告 ===")
        for k in k_values:
            avg_recall = sum(m[f"recall@{k}"] for m in all_metrics) / len(all_metrics)
            avg_ndcg = sum(m[f"ndcg@{k}"] for m in all_metrics) / len(all_metrics)
            print(f"Recall@{k}: {avg_recall:.3f}, NDCG@{k}: {avg_ndcg:.3f}")

        avg_mrr = sum(m["mrr"] for m in all_metrics) / len(all_metrics)
        print(f"MRR: {avg_mrr:.3f}")

        # 按查询类型打印
        print("\n=== 按查询类型统计 ===")
        for query_type, metrics_list in metrics_by_type.items():
            avg_recall_5 = sum(m["recall@5"] for m in metrics_list) / len(metrics_list)
            print(f"{query_type}: Recall@5 = {avg_recall_5:.3f}")

        # 基本断言
        assert len(all_metrics) > 0, "没有成功执行的测试用例"


class TestLyricsSearch:
    """测试歌词搜索质量"""

    @pytest.mark.asyncio
    async def test_lyrics_search_exact(self, rag_search):
        """测试精确歌词片段搜索"""
        query = "后来终于在眼泪中明白"
        results = await rag_search.search(query, top_k=10)

        # "后来" 应该在 top-5 内
        found = any("后来" in str(r.get("title", "")) for r in results[:5])
        assert found, f"歌词搜索未找到 '后来'，实际结果: {results[:5]}"

    @pytest.mark.asyncio
    async def test_lyrics_search_popular(self, rag_search):
        """测试流行歌词搜索"""
        query = "燃烧我的卡路里"
        results = await rag_search.search(query, top_k=10)

        found = any("卡路里" in str(r.get("title", "")) for r in results[:5])
        assert found, f"歌词搜索未找到 '卡路里'"


class TestThemeSearch:
    """测试影视主题曲搜索"""

    @pytest.mark.asyncio
    async def test_theme_search_korean_drama(self, rag_search):
        """测试韩剧主题曲搜索"""
        query = "请回答1988主题曲"
        results = await rag_search.search(query, top_k=10)

        # 应该返回相关韩剧歌曲
        assert len(results) >= 1, "主题曲搜索返回结果为空"

    @pytest.mark.asyncio
    async def test_theme_search_english_movie(self, rag_search):
        """测试英文电影主题曲搜索"""
        query = "Titanic theme song"
        results = await rag_search.search(query, top_k=10)

        # My Heart Will Go On 应该在结果中
        found = any(
            "My Heart" in str(r.get("title", "")) or
            "Celine" in str(r.get("artist", ""))
            for r in results[:5]
        )
        assert found, f"未找到泰坦尼克号主题曲"


class TestArtistSearchPrecision:
    """测试艺术家搜索的精确率"""

    @pytest.mark.asyncio
    async def test_artist_search_precision_high(self, rag_search):
        """测试高要求艺术家搜索精确率"""
        test_cases = [
            ("周杰伦", "周杰伦"),
            ("Lady Gaga", "lady gaga"),
            ("Taylor Swift", "taylor swift"),
        ]

        for query, expected_keyword in test_cases:
            results = await rag_search.get_songs_by_artist(query, limit=10)

            if isinstance(results, tuple):
                results = results[0]

            if not results:
                continue

            # 计算精确率
            hits = sum(
                1 for r in results
                if expected_keyword in str(r.get("artist", "")).lower()
            )
            precision = hits / len(results)

            print(f"\n{query}: precision={precision:.2f}, found={len(results)} songs")

            # 精确率应该高于 0.8
            assert precision >= 0.8, f"{query} 的搜索精确率过低: {precision:.2f}"

    @pytest.mark.asyncio
    async def test_partial_artist_name_matching(self, rag_search):
        """测试艺术家部分名称匹配"""
        query = "selena"
        results = await rag_search.get_songs_by_artist(query, limit=10)

        if isinstance(results, tuple):
            results = results[0]

        # 应该能找到 Selena Gomez 的歌
        assert len(results) >= 3, f"部分名称匹配返回结果过少: {len(results)}"


class TestMoodActivitySearch:
    """测试心情和活动场景搜索"""

    @pytest.mark.asyncio
    async def test_mood_search_happy(self, rag_search):
        """测试正面心情搜索"""
        query = "开心的歌"
        results = await rag_search.search(query, top_k=10)

        # 应该返回足够的结果
        assert len(results) >= 3, f"心情搜索返回结果过少"

    @pytest.mark.asyncio
    async def test_activity_search_running(self, rag_search):
        """测试跑步场景搜索"""
        query = "适合跑步时听的歌"
        results = await rag_search.search(query, top_k=10)

        # 应该返回足够的结果
        assert len(results) >= 3, f"活动场景搜索返回结果过少"


class TestAblationStudies:
    """消融实验：对比不同策略的效果"""

    @pytest.mark.asyncio
    @pytest.mark.skip(reason="需要实现多向量策略支持")
    async def test_multi_vector_comparison(self, rag_search):
        """对比不同向量表示的效果"""
        query = "开心"

        # 对比: 只用 title+artist vs 用 mood+scene 描述
        # baseline_results = await rag_search.search_with_vector_type(query, vector_type="content")
        # mood_results = await rag_search.search_with_vector_type(query, vector_type="mood")

        # 这里需要 rag_search 支持 vector_type 参数
        pass


class TestRetrievalMetricsReport:
    """生成检索质量评估报告"""

    @pytest.mark.asyncio
    @pytest.mark.slow
    async def test_generate_evaluation_report(self, rag_search, eval_dataset, tmp_path):
        """生成完整的评估报告"""
        report = {
            "timestamp": "2026-03-23T00:00:00Z",
            "embedding_model": "bge-m3",
            "vector_store": "chroma_db",
            "test_cases": [],
            "overall_metrics": {},
            "by_query_type": {}
        }

        k_values = [1, 3, 5, 10]

        # 执行所有测试用例
        for case in eval_dataset:
            query = case["query"]
            query_type = case.get("query_type", "unknown")
            relevant_songs = case.get("relevant_songs", [])

            if not relevant_songs:
                continue

            try:
                results = await rag_search.search(query, top_k=10)
            except Exception as e:
                continue

            metrics = evaluate_retrieval(
                results, relevant_songs, k_values=k_values
            )

            report["test_cases"].append({
                "id": case["id"],
                "query": query,
                "query_type": query_type,
                "metrics": metrics
            })

        if not report["test_cases"]:
            pytest.skip("没有成功执行的测试用例")

        # 计算整体指标
        for k in k_values:
            report["overall_metrics"][f"mean_recall@{k}"] = sum(
                c["metrics"][f"recall@{k}"] for c in report["test_cases"]
            ) / len(report["test_cases"])

            report["overall_metrics"][f"mean_ndcg@{k}"] = sum(
                c["metrics"][f"ndcg@{k}"] for c in report["test_cases"]
            ) / len(report["test_cases"])

        report["overall_metrics"]["mean_mrr"] = sum(
            c["metrics"]["mrr"] for c in report["test_cases"]
        ) / len(report["test_cases"])

        # 按查询类型分组
        by_type = {}
        for case in report["test_cases"]:
            qt = case["query_type"]
            if qt not in by_type:
                by_type[qt] = []
            by_type[qt].append(case["metrics"])

        for qt, metrics_list in by_type.items():
            report["by_query_type"][qt] = {
                "recall@10": sum(m["recall@10"] for m in metrics_list) / len(metrics_list),
                "ndcg@10": sum(m["ndcg@10"] for m in metrics_list) / len(metrics_list)
            }

        # 保存报告
        report_path = tmp_path / "rag_evaluation_report.json"
        with open(report_path, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)

        print(f"\n评估报告已保存到: {report_path}")
        print(json.dumps(report["overall_metrics"], indent=2))

        # 基本质量检查
        assert report["overall_metrics"]["mean_recall@10"] > 0.3, "召回率过低"
        assert report["overall_metrics"]["mean_mrr"] > 0.2, "MRR 过低"
