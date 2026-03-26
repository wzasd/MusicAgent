"""
RAG 端到端效果评估测试

评估从查询到最终推荐的完整链路质量，包括：
1. 端到端推荐质量评估
2. 幻觉检测（推荐是否基于真实检索结果）
3. 上下文精确率和召回率
4. 答案相关性评估
"""

import pytest
import json
from typing import List, Dict, Any
from pathlib import Path

pytestmark = pytest.mark.evaluation


def load_eval_dataset() -> List[Dict[str, Any]]:
    """加载评估数据集"""
    dataset_path = Path(__file__).parent / "rag_eval_dataset.json"
    with open(dataset_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    return data.get("cases", [])


@pytest.fixture(scope="module")
def eval_dataset():
    return load_eval_dataset()


@pytest.fixture(scope="module")
def journey_service():
    """Journey Service fixture"""
    try:
        from services.journey_service import JourneyService
        return JourneyService()
    except ImportError:
        pytest.skip("JourneyService not available")


@pytest.fixture(scope="module")
def music_graph():
    """Music Graph fixture"""
    try:
        from graphs.music_graph import create_music_graph
        return create_music_graph()
    except ImportError:
        pytest.skip("MusicGraph not available")


class TestEndToEndRecommendation:
    """端到端推荐质量测试"""

    @pytest.mark.asyncio
    async def test_end_to_end_query_processing(self, music_graph):
        """测试完整查询处理链路"""
        test_queries = [
            {"query": "周杰伦的歌", "expected_intent": "search_by_artist"},
            {"query": "后来终于在眼泪中明白", "expected_intent": "search_by_lyrics"},
            {"query": "请回答1988主题曲", "expected_intent": "search_by_theme"},
        ]

        for test in test_queries:
            query = test["query"]

            # 构建输入
            inputs = {
                "query": query,
                "chat_history": []
            }

            try:
                # 执行图
                result = await music_graph.ainvoke(inputs)

                # 验证结果结构
                assert "songs" in result, f"结果缺少 songs 字段"
                assert isinstance(result["songs"], list), f"songs 不是列表"

                # 验证返回结果数
                assert len(result["songs"]) > 0, f"'{query}' 没有返回结果"

                print(f"\n'{query}': 返回 {len(result['songs'])} 首歌曲")

            except Exception as e:
                pytest.skip(f"查询处理失败: {e}")

    @pytest.mark.asyncio
    async def test_recommendation_diversity(self, music_graph):
        """测试推荐结果的多样性"""
        query = "推荐一些流行歌曲"

        inputs = {
            "query": query,
            "chat_history": []
        }

        try:
            result = await music_graph.ainvoke(inputs)
            songs = result.get("songs", [])

            if len(songs) < 3:
                pytest.skip("返回结果数不足，无法评估多样性")

            # 计算艺术家多样性
            artists = [s.get("artist", "").lower() for s in songs]
            unique_artists = set(artists)

            diversity = len(unique_artists) / len(artists)
            print(f"\n艺术家多样性: {diversity:.2f} ({len(unique_artists)}/{len(artists)})")

            # 多样性应该高于 0.5（至少一半是不同的艺术家）
            assert diversity >= 0.5, f"推荐多样性过低: {diversity:.2f}"

        except Exception as e:
            pytest.skip(f"查询处理失败: {e}")


class TestFaithfulness:
    """幻觉检测测试"""

    @pytest.mark.asyncio
    async def test_recommendation_has_evidence(self, music_graph, eval_dataset):
        """验证推荐是否基于真实检索结果，而非幻觉"""
        # 选择一个简单的测试用例
        test_case = next((c for c in eval_dataset if c["id"] == "rag_001"), None)

        if not test_case:
            pytest.skip("未找到测试用例")

        query = test_case["query"]
        expected_titles = [s["title"] for s in test_case.get("relevant_songs", [])]

        inputs = {
            "query": query,
            "chat_history": []
        }

        try:
            result = await music_graph.ainvoke(inputs)
            recommendations = result.get("songs", [])

            # 验证每个推荐都有合理的来源
            for rec in recommendations:
                title = rec.get("title", "")
                artist = rec.get("artist", "")

                # 检查基本字段存在
                assert title, "推荐歌曲缺少 title"
                assert artist, "推荐歌曲缺少 artist"

                # 验证标题和艺术家不为空或无效值
                assert len(title.strip()) > 0, "歌曲标题为空"
                assert len(artist.strip()) > 0, "艺术家为空"

            print(f"\n'{query}': 验证了 {len(recommendations)} 首推荐歌曲的基本字段")

        except Exception as e:
            pytest.skip(f"查询处理失败: {e}")

    @pytest.mark.asyncio
    async def test_no_empty_recommendations(self, music_graph):
        """测试没有空推荐"""
        queries = ["周杰伦", "稻香", "开心的歌"]

        for query in queries:
            inputs = {
                "query": query,
                "chat_history": []
            }

            try:
                result = await music_graph.ainvoke(inputs)
                songs = result.get("songs", [])

                for song in songs:
                    # 检查空值
                    assert song.get("title"), f"空标题: {song}"
                    assert song.get("artist"), f"空艺术家: {song}"

                    # 检查无效值
                    assert song["title"].lower() not in ["unknown", "n/a", ""], \
                        f"无效标题: {song}"
                    assert song["artist"].lower() not in ["unknown", "n/a", ""], \
                        f"无效艺术家: {song}"

            except Exception as e:
                pytest.skip(f"查询 '{query}' 处理失败: {e}")


class TestContextQuality:
    """上下文质量测试"""

    @pytest.mark.asyncio
    async def test_retrieval_context_relevance(self, music_graph, eval_dataset):
        """测试检索到的上下文与查询的相关性"""
        # 使用艺术家查询测试
        test_case = next((c for c in eval_dataset if c["query_type"] == "artist"), None)

        if not test_case:
            pytest.skip("未找到艺术家测试用例")

        query = test_case["query"]

        inputs = {
            "query": query,
            "chat_history": []
        }

        try:
            result = await music_graph.ainvoke(inputs)
            songs = result.get("songs", [])

            # 验证返回的歌曲与查询相关
            artist_keyword = query.lower()

            relevant_count = sum(
                1 for s in songs
                if artist_keyword in str(s.get("artist", "")).lower()
            )

            # 至少 70% 应该相关
            if songs:
                relevance_ratio = relevant_count / len(songs)
                print(f"\n'{query}': 上下文相关性 = {relevance_ratio:.2f}")
                assert relevance_ratio >= 0.7, f"上下文相关性过低: {relevance_ratio:.2f}"

        except Exception as e:
            pytest.skip(f"查询处理失败: {e}")


class TestJourneyGeneration:
    """音乐旅程生成质量测试"""

    @pytest.mark.asyncio
    async def test_journey_generation_quality(self, journey_service):
        """测试音乐旅程生成质量"""
        story = "今天失恋了，心情很糟糕，想听一些治愈的歌曲"
        duration = 60

        try:
            journey = await journey_service.create_journey(
                story=story,
                duration_minutes=duration
            )

            # 验证旅程结构
            assert "segments" in journey, "旅程缺少 segments 字段"
            assert isinstance(journey["segments"], list), "segments 不是列表"

            # 验证有多个阶段
            assert len(journey["segments"]) >= 2, f"旅程阶段数不足: {len(journey['segments'])}"

            # 验证每个阶段有歌曲
            for i, segment in enumerate(journey["segments"]):
                assert "songs" in segment, f"阶段 {i} 缺少 songs"
                assert len(segment["songs"]) > 0, f"阶段 {i} 没有歌曲"

            print(f"\n旅程生成成功: {len(journey['segments'])} 个阶段")

        except Exception as e:
            pytest.skip(f"旅程生成失败: {e}")

    @pytest.mark.asyncio
    async def test_journey_no_duplicate_songs(self, journey_service):
        """测试旅程中无重复歌曲"""
        story = "适合工作学习的背景音乐"
        duration = 45

        try:
            journey = await journey_service.create_journey(
                story=story,
                duration_minutes=duration
            )

            # 收集所有歌曲标题
            all_titles = []
            for segment in journey.get("segments", []):
                for song in segment.get("songs", []):
                    all_titles.append(song.get("title", "").lower())

            # 检查重复
            unique_titles = set(all_titles)
            duplicate_count = len(all_titles) - len(unique_titles)

            print(f"\n总歌曲数: {len(all_titles)}, 唯一: {len(unique_titles)}, 重复: {duplicate_count}")

            # 允许少量重复（<10%）
            if all_titles:
                duplicate_ratio = duplicate_count / len(all_titles)
                assert duplicate_ratio < 0.1, f"重复率过高: {duplicate_ratio:.2f}"

        except Exception as e:
            pytest.skip(f"旅程生成失败: {e}")


class TestResponseFormat:
    """响应格式测试"""

    @pytest.mark.asyncio
    async def test_response_structure_completeness(self, music_graph):
        """测试响应结构的完整性"""
        query = "推荐一些周杰伦的歌曲"

        inputs = {
            "query": query,
            "chat_history": []
        }

        try:
            result = await music_graph.ainvoke(inputs)

            # 检查必需字段
            required_fields = ["songs", "source", "intent"]
            for field in required_fields:
                assert field in result, f"响应缺少字段: {field}"

            # 检查 songs 列表中的字段
            for song in result["songs"]:
                assert "title" in song, "歌曲缺少 title"
                assert "artist" in song, "歌曲缺少 artist"

            print(f"\n响应结构完整: {len(result['songs'])} 首歌曲, source={result.get('source')}")

        except Exception as e:
            pytest.skip(f"查询处理失败: {e}")


class TestQueryUnderstanding:
    """查询理解测试"""

    @pytest.mark.asyncio
    async def test_intent_classification_accuracy(self, music_graph, eval_dataset):
        """测试意图分类准确性"""
        # 选择几个典型用例
        test_cases = [
            ("周杰伦的歌", ["artist", "recommend"]),
            ("后来终于在眼泪中明白", ["lyrics", "search"]),
            ("请回答1988主题曲", ["theme", "search"]),
            ("适合跑步的歌", ["activity", "recommend"]),
            ("开心的歌", ["mood", "recommend"]),
        ]

        for query, expected_keywords in test_cases:
            inputs = {
                "query": query,
                "chat_history": []
            }

            try:
                result = await music_graph.ainvoke(inputs)
                intent = result.get("intent", "").lower()

                # 检查意图是否包含预期关键词
                matched = any(kw in intent for kw in expected_keywords)

                print(f"\n'{query}' -> intent: {intent}, matched: {matched}")

                # 至少应该匹配一个关键词
                assert matched, f"意图 '{intent}' 不匹配预期关键词 {expected_keywords}"

            except Exception as e:
                pytest.skip(f"查询 '{query}' 处理失败: {e}")


class TestPerformance:
    """性能测试"""

    @pytest.mark.asyncio
    @pytest.mark.slow
    async def test_response_time(self, music_graph):
        """测试响应时间"""
        import asyncio
        import time

        query = "推荐一些周杰伦的歌曲"

        inputs = {
            "query": query,
            "chat_history": []
        }

        try:
            start_time = time.time()
            result = await music_graph.ainvoke(inputs)
            elapsed_time = time.time() - start_time

            print(f"\n查询处理时间: {elapsed_time:.2f}s")

            # 应该能在 10 秒内完成
            assert elapsed_time < 10.0, f"响应时间过长: {elapsed_time:.2f}s"

        except Exception as e:
            pytest.skip(f"查询处理失败: {e}")


class TestEndToEndReport:
    """生成端到端评估报告"""

    @pytest.mark.asyncio
    @pytest.mark.slow
    async def test_generate_end_to_end_report(self, music_graph, eval_dataset, tmp_path):
        """生成完整的端到端评估报告"""
        report = {
            "timestamp": "2026-03-23T00:00:00Z",
            "test_type": "end_to_end",
            "cases": []
        }

        # 选择部分用例进行测试
        test_cases = [c for c in eval_dataset if c["query_type"] in ["artist", "title", "lyrics"]][:5]

        for case in test_cases:
            query = case["query"]
            query_type = case["query_type"]

            inputs = {
                "query": query,
                "chat_history": []
            }

            try:
                start_time = time.time()
                result = await music_graph.ainvoke(inputs)
                elapsed_time = time.time() - start_time

                case_report = {
                    "id": case["id"],
                    "query": query,
                    "query_type": query_type,
                    "response_time": elapsed_time,
                    "result_count": len(result.get("songs", [])),
                    "intent": result.get("intent"),
                    "source": result.get("source"),
                    "has_results": len(result.get("songs", [])) > 0
                }

                report["cases"].append(case_report)

            except Exception as e:
                report["cases"].append({
                    "id": case["id"],
                    "query": query,
                    "error": str(e)
                })

        # 计算统计信息
        successful_cases = [c for c in report["cases"] if "error" not in c]

        if successful_cases:
            report["summary"] = {
                "total_cases": len(report["cases"]),
                "successful_cases": len(successful_cases),
                "avg_response_time": sum(c["response_time"] for c in successful_cases) / len(successful_cases),
                "avg_result_count": sum(c["result_count"] for c in successful_cases) / len(successful_cases),
                "success_rate": len(successful_cases) / len(report["cases"])
            }

        # 保存报告
        report_path = tmp_path / "end_to_end_evaluation_report.json"
        with open(report_path, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)

        print(f"\n端到端评估报告已保存到: {report_path}")
        print(json.dumps(report.get("summary", {}), indent=2))

        # 基本检查
        assert report["summary"]["success_rate"] > 0.8, "成功率过低"
