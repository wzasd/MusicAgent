"""
意图分类回归测试

测试用户查询 → 意图分类的准确性。
失败的用例会被记录到 regression_report.json，方便分析修复。
"""

import json
import os
from datetime import datetime
from pathlib import Path

import pytest


# Valid intent types (must match graphs/music_graph.py)
VALID_INTENTS = {
    "search",
    "search_by_lyrics",
    "search_by_theme",
    "search_by_topic",
    "recommend_by_mood",
    "recommend_by_activity",
    "recommend_by_genre",
    "recommend_by_artist",
    "recommend_by_favorites",
    "create_playlist",
    "general_chat",
}


@pytest.mark.regression
class TestIntentClassification:
    """
    意图分类回归测试类。

    读取 tests/regression/intent_regression_cases.json 中的用例，
    对每个查询调用 analyze_intent()，验证返回的 intent_type 和 parameters。
    """

    @pytest.fixture(autouse=True)
    def setup_report_dir(self, regression_report_path):
        """Create report directory if not exists."""
        regression_report_path.mkdir(parents=True, exist_ok=True)

    def load_cases(self, intent_regression_cases):
        """Load test cases from JSON."""
        return intent_regression_cases

    def save_failure_report(self, failed_cases, regression_report_path):
        """Save failed cases to report file."""
        if not failed_cases:
            return

        report = {
            "timestamp": datetime.now().isoformat(),
            "total_failed": len(failed_cases),
            "failed_cases": failed_cases,
        }

        report_file = regression_report_path / "intent_regression_failures.json"
        with open(report_file, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)

        return report_file

    @pytest.mark.asyncio
    async def test_intent_classification_cases(self, intent_regression_cases, analyze_intent_func, regression_report_path):
        """
        批量测试意图分类回归用例。

        断言失败不会立即中断，而是收集所有失败用例后统一报告。
        """
        if not intent_regression_cases:
            pytest.skip("No regression cases found in intent_regression_cases.json")

        failed_cases = []
        passed = 0

        for case in intent_regression_cases:
            case_id = case.get("id", "unknown")
            query = case["query"]
            expected_intent = case["expected_intent"]
            expected_params = case.get("expected_params", {})
            tags = case.get("tags", [])

            # Call the intent analysis function
            try:
                result = await analyze_intent_func(query)
                actual_intent = result.get("intent_type")
                actual_params = result.get("intent_parameters", {})
            except Exception as e:
                failed_cases.append({
                    "id": case_id,
                    "query": query,
                    "error": str(e),
                    "expected_intent": expected_intent,
                    "actual_intent": None,
                    "tags": tags,
                })
                continue

            # Check intent type
            if actual_intent != expected_intent:
                failed_cases.append({
                    "id": case_id,
                    "query": query,
                    "expected_intent": expected_intent,
                    "actual_intent": actual_intent,
                    "expected_params": expected_params,
                    "actual_params": actual_params,
                    "tags": tags,
                    "failure_type": "intent_mismatch",
                })
                continue

            # Check parameters (only check keys that exist in expected)
            param_mismatch = False
            for key, expected_value in expected_params.items():
                if key not in actual_params:
                    param_mismatch = True
                    break
                actual_value = actual_params[key]
                # Handle None values (optional fields)
                if expected_value is None:
                    continue
                if actual_value != expected_value:
                    param_mismatch = True
                    break

            if param_mismatch:
                failed_cases.append({
                    "id": case_id,
                    "query": query,
                    "expected_intent": expected_intent,
                    "actual_intent": actual_intent,
                    "expected_params": expected_params,
                    "actual_params": actual_params,
                    "tags": tags,
                    "failure_type": "param_mismatch",
                })
                continue

            passed += 1

        # Save failure report
        if failed_cases:
            report_file = self.save_failure_report(failed_cases, regression_report_path)
            print(f"\n\n{'='*60}")
            print(f"意图分类回归测试报告")
            print(f"{'='*60}")
            print(f"通过: {passed}")
            print(f"失败: {len(failed_cases)}")
            print(f"\n失败用例详情:")
            for fc in failed_cases:
                print(f"\n  [{fc['id']}] {fc['query']}")
                print(f"    预期意图: {fc.get('expected_intent')}")
                print(f"    实际意图: {fc.get('actual_intent')}")
                if fc.get('failure_type') == 'param_mismatch':
                    print(f"    参数不匹配")
            print(f"\n详细报告: {report_file}")
            print(f"{'='*60}\n")

        # Final assertion
        assert len(failed_cases) == 0, f"{len(failed_cases)} 个意图分类用例失败，查看上面的报告"


@pytest.mark.regression
class TestIntentClassificationIndividual:
    """Individual test cases for better debugging."""

    CRITICAL_CASES = [
        # (query, expected_intent, description)
        ("后来终于在眼泪中明白", "search_by_lyrics", "经典歌词搜索"),
        ("我想听周杰伦的歌", "recommend_by_artist", "艺术家推荐"),
        ("请回答1988主题曲", "search_by_theme", "影视主题曲"),
        ("关于雨的歌", "search_by_topic", "话题搜索"),
        ("开心的时候听什么", "recommend_by_mood", "心情推荐"),
        ("跑步时听什么歌", "recommend_by_activity", "活动推荐"),
    ]

    @pytest.mark.asyncio
    @pytest.mark.parametrize("query,expected_intent,description", CRITICAL_CASES)
    async def test_critical_intent_cases(self, query, expected_intent, description, analyze_intent_func):
        """测试关键意图分类场景。"""
        result = await analyze_intent_func(query)
        actual_intent = result.get("intent_type")

        assert actual_intent == expected_intent, (
            f"[{description}] 意图识别错误:\n"
            f"  查询: {query}\n"
            f"  预期: {expected_intent}\n"
            f"  实际: {actual_intent}"
        )
