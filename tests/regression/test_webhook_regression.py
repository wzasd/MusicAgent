"""
Webhook 处理器回归测试

测试从实际使用场景中收集的用例，验证语音助手对特定查询的处理结果。
失败的用例会被记录到 webhook_regression_failures.json，方便分析和改进。

测试用例来源：
1. 直接歌曲名称搜索
2. 歌词片段搜索

历史记录：
- 2026-03-24: 添加初始测试用例（包含 PASS 和 FAILED 案例）
"""

import json
import pytest
import asyncio
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List

from api.webhook_handler import (
    handle_music_agent_webhook,
    MusicAgentWebhookRequest,
    WebhookMessage,
    ConversationContext,
    stream_webhook_response,
    analyze_intent_with_context,
)
from api.music_agent_service import get_music_agent_service


# ========== 回归测试用例库 ==========

# 直接歌曲名称搜索用例
DIRECT_SONG_TEST_CASES = [
    {
        "id": "direct_001",
        "query": "I want to listen to the song Let's Kill This Love",
        "expected_song": "Let's Kill This Love",
        "expected_artist": "BLACKPINK",
        "description": "英文歌名 - Let's Kill This Love",
        "status": "FAILED",
        "actual_result": "La La La Love - Various Artists",
        "notes": "ChromaDB 数据质量问题：RAG 搜索返回了不匹配的艺术家",
        "root_cause_analysis": {
            "probable_cause": "ChromaDB RAG 语义搜索精度不足",
            "explanation": """
1. ChromaDB 中可能存在多首标题相似的歌曲（如 "La La La Love"）
2. 语义搜索基于 embedding 相似度，可能因训练数据偏差返回非预期结果
3. 查询 "Let's Kill This Love" 与 "La La La Love" 在向量空间中可能距离较近
            """,
            "technical_details": {
                "search_layer": "rag_music_search_v2.py -> ChromaDB vector search",
                "failure_point": "Embedding similarity matching",
                "similarity_score": "0.81 (较高但实际不匹配)"
            },
            "suggested_fixes": [
                "增加艺术家名称作为搜索过滤条件",
                "优化 embedding 模型，使用音乐专用模型",
                "在 RAG 结果上增加二次验证层（标题精确匹配）",
                "扩充 ChromaDB 数据，添加更多 K-pop 歌曲"
            ]
        },
        "added_at": "2026-03-24"
    },
    {
        "id": "direct_002",
        "query": "I want to listen to the song Love story",
        "expected_song": "Love Story",
        "expected_artist": "Taylor Swift",
        "description": "英文歌名 - Love Story",
        "status": "FAILED",
        "actual_result": "A Love Story - Carlos Márquez",
        "notes": "ChromaDB 返回了错误的艺术家版本",
        "root_cause_analysis": {
            "probable_cause": "ChromaDB 数据覆盖偏差",
            "explanation": "ChromaDB 中 Taylor Swift 的 'Love Story' 可能缺失或被其他同名歌曲覆盖",
            "suggested_fixes": [
                "扩充 ChromaDB 数据，确保热门歌曲覆盖",
                "增加元数据过滤（流派、年代等）"
            ]
        },
        "added_at": "2026-03-24"
    },
    {
        "id": "direct_003",
        "query": "I want to listen to the song hotel california",
        "expected_song": "Hotel California",
        "expected_artist": "Eagles",
        "description": "英文歌名 - Hotel California",
        "status": "FAILED",
        "actual_result": "Hotel California - Lenaïg",
        "notes": "ChromaDB 返回了翻唱版本而非原版",
        "root_cause_analysis": {
            "probable_cause": "ChromaDB 缺少原版或翻唱版本排名靠前",
            "explanation": "Eagles 的原版 'Hotel California' 在 ChromaDB 中可能缺失，或 Lenaïg 的翻唱版本相似度更高",
            "suggested_fixes": [
                "添加原版歌曲标记，优先返回原版",
                "扩充经典摇滚歌曲数据"
            ]
        },
        "added_at": "2026-03-24"
    },
    {
        "id": "direct_004",
        "query": "I want to listen to the song take it easy",
        "expected_song": "Take It Easy",
        "expected_artist": "Eagles",
        "description": "英文歌名 - Take It Easy",
        "status": "FAILED",
        "actual_result": "Take It Easy - Jackson Browne",
        "notes": "返回了另一版本（Jackson Browne 确实也是原唱之一）",
        "root_cause_analysis": {
            "probable_cause": "同一歌曲多个版本",
            "explanation": "'Take It Easy' 由 Jackson Browne 和 Glenn Frey 共同创作，两个艺术家都有演唱版本",
            "suggested_fixes": [
                "返回多个版本供用户选择",
                "增加版本 popularity 排序"
            ]
        },
        "added_at": "2026-03-24"
    },
    {
        "id": "direct_005",
        "query": "I want to listen to the song every storm",
        "expected_song": "Every Storm (Runs Out of Rain)",
        "expected_artist": "Gary Allan",
        "description": "英文歌名 - Every Storm",
        "status": "FAILED",
        "actual_result": "Ein Sturm zieht auf - Grinding Moon",
        "notes": "ChromaDB 完全匹配失败，返回了德语歌曲",
        "root_cause_analysis": {
            "probable_cause": "ChromaDB 缺少乡村音乐数据",
            "explanation": "Gary Allan 的乡村歌曲在 ChromaDB 中缺失，搜索返回了语义相近的德语歌曲",
            "suggested_fixes": [
                "扩充乡村音乐数据",
                "增加语言检测和过滤"
            ]
        },
        "added_at": "2026-03-24"
    },
]

# 歌词片段搜索用例 - 包含详细的失败根因分析
LYRICS_TEST_CASES = [
    {
        "id": "lyrics_001",
        "query": 'I want to hear the song with the lyric "Every night in my dreams"',
        "expected_song": "My Heart Will Go On",
        "expected_artist": "Celine Dion",
        "lyrics_snippet": "Every night in my dreams",
        "description": "歌词片段 - My Heart Will Go On (泰坦尼克号主题曲)",
        "status": "PASS",
        "added_at": "2026-03-24"
    },
    {
        "id": "lyrics_002",
        "query": 'I want to hear the song with the lyric "sitting out here on the hood of this truck"',
        "expected_song": "Watching Airplanes",
        "expected_artist": "Gary Allan",
        "lyrics_snippet": "sitting out here on the hood of this truck",
        "description": "歌词片段 - Watching Airplanes (乡村音乐)",
        "status": "FAILED",
        "actual_result": "night's on fire (david nail)",
        "notes": "歌词搜索结果错误，返回了错误的歌曲",
        "root_cause_analysis": {
            "probable_cause": "Web Search 语义匹配错误",
            "explanation": """
1. 本地歌词数据库可能缺少这首歌（Gary Allan - Watching Airplanes 是2007年乡村歌曲）
2. Tavily Web Search 搜索时，"sitting out here on the hood of this truck" 与 David Nail 的 "Night's On Fire" 在搜索结果中被错误关联
3. LLM 从搜索结果中提取时，可能因歌词片段过于具体但没有足够上下文，导致误判
            """,
            "technical_details": {
                "search_layer": "lyrics_search.py -> search_with_web_fallback()",
                "failure_point": "Tavily API 搜索结果质量或 LLM 提取逻辑",
                "confidence_threshold": "当前 < 0.3 会放弃结果，但此案例可能返回了高置信度的错误匹配"
            },
            "suggested_fixes": [
                "扩展本地歌词数据库，增加更多乡村音乐歌词",
                "优化 LLM 提取 Prompt，要求更严格的匹配验证",
                "添加歌曲类型过滤，避免将歌词查询与播客/其他内容混淆",
                "考虑使用更专业的音乐歌词 API（如 Musixmatch）作为额外数据源"
            ]
        },
        "added_at": "2026-03-24"
    },
    {
        "id": "lyrics_003",
        "query": 'I want to hear the song with the lyric "closed off from love, i didn\'t need the pain"',
        "expected_song": "Bleeding Love",
        "expected_artist": "Leona Lewis",
        "lyrics_snippet": "closed off from love, i didn't need the pain",
        "description": "歌词片段 - Bleeding Love (流行经典)",
        "status": "PASS",
        "added_at": "2026-03-24"
    },
    {
        "id": "lyrics_004",
        "query": 'I want to hear the song with the lyric "how i wish you could see the potential"',
        "expected_song": "I Will Possess Your Heart",
        "expected_artist": "Death Cab for Cutie",
        "lyrics_snippet": "how i wish you could see the potential",
        "description": "歌词片段 - I Will Possess Your Heart (独立摇滚)",
        "status": "FAILED",
        "actual_result": "播客：An Announcement! (Undisclosed: Toward Justice)",
        "notes": "歌词搜索失败，错误地返回了播客内容",
        "root_cause_analysis": {
            "probable_cause": "搜索意图识别错误或搜索结果污染",
            "explanation": """
1. 可能原因 A: 意图分析器没有正确识别为歌词搜索，而是作为普通搜索处理了
2. 可能原因 B: Tavily Web Search 搜索该歌词时，返回了播客节目的页面（播客页面可能包含歌词引用但主要是播客内容）
3. 可能原因 C: LLM 提取时，从搜索结果中错误地提取了播客标题而非歌曲信息

具体检查点：
- lyrics_search.py:is_lyrics_query() 是否正确返回 True?
- Tavily 搜索返回的结果中是否包含歌曲信息？
- LYRICS_IDENTIFICATION_FROM_SEARCH_PROMPT 是否足够严格？
            """,
            "technical_details": {
                "search_layer": "music_tools.py -> search_songs_with_steps() 第0层歌词搜索",
                "failure_point": "可能在意图识别层或 Web Search 结果提取层",
                "code_path": [
                    "webhook_handler.py:analyze_intent_with_context()",
                    "music_agent_service.py:search_songs()",
                    "music_tools.py:search_songs_with_steps() 第0层",
                    "lyrics_search.py:search_with_web_fallback()"
                ]
            },
            "suggested_fixes": [
                "在 LLM 提取结果中增加 source_type 验证，过滤掉播客/视频等非音乐内容",
                "优化 is_lyrics_query() 的英文模式匹配，确保 'song with the lyric' 被正确识别",
                "在歌词搜索失败时，返回明确的错误信息而非让上层使用其他搜索方式",
                "考虑添加结果验证层：如果返回的不是歌曲（无艺术家信息），则视为失败"
            ],
            "verification_steps": [
                "检查 Tavily API 对该歌词的原始搜索结果",
                "检查 LLM 提取 Prompt 的输出格式",
                "确认播客结果是如何通过验证的（confidence 阈值问题？）"
            ]
        },
        "added_at": "2026-03-24"
    },
    {
        "id": "lyrics_005",
        "query": 'I want to hear the song with the lyric "fell from your heart and landed in my eyes"',
        "expected_song": "Cosmic Love",
        "expected_artist": "Florence + The Machine",
        "lyrics_snippet": "fell from your heart and landed in my eyes",
        "description": "歌词片段 - Cosmic Love (独立流行)",
        "status": "FAILED",
        "actual_result": "Tears Always Win (Alicia Keys)",
        "notes": "歌词搜索结果错误，返回了错误的歌曲",
        "root_cause_analysis": {
            "probable_cause": "语义相似度匹配错误",
            "explanation": """
1. 本地歌词数据库缺少 Florence + The Machine 的 Cosmic Love
2. Web Search 时，Tavily 可能返回了包含相似情感表达（"heart", "eyes", "fall"）的歌曲
3. "fell from your heart" 和 "Tears Always Win" 在情感主题上可能相似（失恋/情感）
4. LLM 提取时可能选择了置信度较高但实际错误的匹配

歌词对比：
- 预期: "A falling star fell from your heart and landed in my eyes" (Cosmic Love)
- 实际返回: Alicia Keys - Tears Always Win

可能的混淆点：
- 都涉及 "fall/fell" 和情感主题
- 都是女性歌手
- 都关于情感失落
            """,
            "technical_details": {
                "search_layer": "lyrics_search.py -> search_with_web_fallback()",
                "failure_point": "Tavily 搜索结果质量或 LLM 语义理解",
                "lyrics_db_coverage": "本地数据库覆盖不足（特别是2009-2010年代的独立音乐）"
            },
            "suggested_fixes": [
                "扩展本地歌词数据库，增加 Florence + The Machine 等独立音乐歌词",
                "优化搜索查询构建，使用 MultilingualSearchBuilder 增强歌词特定搜索",
                "增加 LLM 提取后的验证步骤：检查提取的歌名是否包含歌词中的关键词",
                "考虑使用 lyrics genius API 或类似专业歌词服务作为数据源"
            ]
        },
        "added_at": "2026-03-24"
    },
]

# 多轮对话选择测试用例 - 验证 LLM 改写功能
MULTI_TURN_SELECTION_CASES = [
    {
        "id": "multi_turn_001",
        "description": "选择第一首 - 从历史消息提取歌曲",
        "messages": [
            {"role": "user", "content": "Recommend some songs for running"},
            {"role": "assistant", "content": "Here are some songs for running:\n1. Eye of the Tiger by Survivor\n2. Stronger by Kanye West\n3. Can't Hold Us by Macklemore"},
            {"role": "user", "content": "the first one"}
        ],
        "expected_song": "Eye of the Tiger",
        "expected_artist": "Survivor",
        "expected_intent": "select_from_results",
        "status": "PASS",
        "added_at": "2026-03-25"
    },
    {
        "id": "multi_turn_002",
        "description": "选择第二首 - 从历史消息提取歌曲",
        "messages": [
            {"role": "user", "content": "Recommend some classic rock songs"},
            {"role": "assistant", "content": "1. Hotel California by Eagles\n2. Bohemian Rhapsody by Queen\n3. Stairway to Heaven by Led Zeppelin"},
            {"role": "user", "content": "the second one"}
        ],
        "expected_song": "Bohemian Rhapsody",
        "expected_artist": "Queen",
        "expected_intent": "select_from_results",
        "status": "PASS",
        "added_at": "2026-03-25"
    },
    {
        "id": "multi_turn_003",
        "description": "播放最后一首",
        "messages": [
            {"role": "user", "content": "推荐几首周杰伦的歌"},
            {"role": "assistant", "content": "1. 晴天 by 周杰伦\n2. 稻香 by 周杰伦\n3. 七里香 by 周杰伦"},
            {"role": "user", "content": "最后一首"}
        ],
        "expected_song": "七里香",
        "expected_artist": "周杰伦",
        "expected_intent": "select_from_results",
        "status": "PASS",
        "added_at": "2026-03-25"
    },
    {
        "id": "multi_turn_004",
        "description": "模糊指代 - play it",
        "messages": [
            {"role": "user", "content": "Songs by Ed Sheeran"},
            {"role": "assistant", "content": "1. Shape of You by Ed Sheeran\n2. Perfect by Ed Sheeran\n3. Thinking Out Loud by Ed Sheeran"},
            {"role": "user", "content": "play it"}
        ],
        "expected_song": "Shape of You",
        "expected_artist": "Ed Sheeran",
        "expected_intent": "select_from_results",
        "status": "PASS",
        "added_at": "2026-03-25"
    },
]

# 合并所有测试用例
ALL_WEBHOOK_TEST_CASES = DIRECT_SONG_TEST_CASES + LYRICS_TEST_CASES + MULTI_TURN_SELECTION_CASES


# ========== 辅助函数 ==========

async def collect_stream_response(stream_generator) -> Dict[str, Any]:
    """收集流式响应的所有数据"""
    chunks = []
    final_response = None

    async for chunk in stream_generator:
        chunks.append(chunk)
        # 解析 SSE 数据
        if chunk.startswith("data: "):
            data_str = chunk[6:].strip()
            try:
                data = json.loads(data_str)
                if data.get("reply", {}).get("streamInfo", {}).get("streamType") == "final":
                    final_response = data
            except json.JSONDecodeError:
                pass

    return {
        "chunks": chunks,
        "final_response": final_response,
        "response_count": len(chunks)
    }


def extract_played_song(final_response: Dict[str, Any]) -> Dict[str, Any]:
    """从最终响应中提取播放的歌曲信息"""
    if not final_response:
        return None

    reply = final_response.get("reply", {})
    actions = reply.get("action", [])
    stream_info = reply.get("streamInfo", {})
    stream_content = stream_info.get("streamContent", "")

    result = {
        "title": None,
        "artist": None,
        "has_play_action": False,
        "stream_content": stream_content
    }

    # 从 action 中提取歌曲信息
    if actions is None:
        actions = []
    for action in actions:
        if action.get("header", {}).get("name") == "PLAY_SEARCH_SONG":
            result["has_play_action"] = True
            forward_slots = action.get("payload", {}).get("callParams", {}).get("forwardSlot", [])
            for slot in forward_slots:
                if slot.get("key") == "songName":
                    result["title"] = slot.get("value", [None])[0] if slot.get("value") else None
                elif slot.get("key") == "artist":
                    result["artist"] = slot.get("value", [None])[0] if slot.get("value") else None

    return result


def normalize_string(s: str) -> str:
    """标准化字符串用于比较（支持 Unicode 规范化）"""
    if not s:
        return ""
    import unicodedata
    # 1. 转换为小写
    s = s.lower().strip()
    # 2. Unicode 规范化（NFD 分解 + 移除组合字符）
    s = unicodedata.normalize('NFD', s)
    s = ''.join(c for c in s if unicodedata.category(c) != 'Mn')
    # 3. 移除引号
    s = s.replace("'", "").replace('"', "")
    return s


def is_song_match(actual: Dict[str, Any], expected_song: str, expected_artist: str) -> bool:
    """检查歌曲是否匹配（支持模糊匹配）"""
    actual_title = actual.get("title", "") or ""
    actual_artist = actual.get("artist", "") or ""

    # 标准化
    actual_title_norm = normalize_string(actual_title)
    actual_artist_norm = normalize_string(actual_artist)
    expected_song_norm = normalize_string(expected_song)
    expected_artist_norm = normalize_string(expected_artist)

    # 标题匹配（支持部分匹配）
    title_match = (
        expected_song_norm in actual_title_norm or
        actual_title_norm in expected_song_norm or
        expected_song_norm == actual_title_norm
    )

    # 艺术家匹配（支持部分匹配）
    artist_match = (
        expected_artist_norm in actual_artist_norm or
        actual_artist_norm in expected_artist_norm or
        expected_artist_norm == actual_artist_norm
    )

    return title_match and artist_match


# ========== 测试类 ==========

@pytest.mark.regression
@pytest.mark.webhook
class TestWebhookRegression:
    """
    Webhook 处理器回归测试

    测试从实际使用场景收集的用例，验证：
    1. 意图分析是否正确
    2. 返回的歌曲是否匹配预期
    3. 播控指令是否正确生成
    """

    @pytest.fixture(autouse=True)
    def setup_report_dir(self, regression_report_path):
        """Create report directory if not exists."""
        regression_report_path.mkdir(parents=True, exist_ok=True)

    def save_failure_report(self, failed_cases: List[Dict], regression_report_path: Path, all_cases: List[Dict] = None):
        """Save failed cases to report file with detailed root cause analysis."""
        if not failed_cases:
            return None

        all_cases = all_cases or ALL_WEBHOOK_TEST_CASES

        # 构建失败分类统计
        failure_categories = {}
        for case in failed_cases:
            root_cause = case.get("root_cause_category", "unknown")
            failure_categories[root_cause] = failure_categories.get(root_cause, 0) + 1

        report = {
            "timestamp": datetime.now().isoformat(),
            "summary": {
                "total_tested": len(all_cases),
                "total_passed": len(all_cases) - len(failed_cases),
                "total_failed": len(failed_cases),
                "pass_rate": f"{((len(all_cases) - len(failed_cases)) / len(all_cases) * 100):.1f}%",
                "failure_categories": failure_categories,
            },
            "failed_cases": failed_cases,
            "known_failures": [c for c in failed_cases if c.get("is_known_failure")],
            "new_failures": [c for c in failed_cases if not c.get("is_known_failure")],
            "root_cause_summary": self._generate_root_cause_summary(failed_cases),
        }

        report_file = regression_report_path / "webhook_regression_failures.json"
        with open(report_file, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)

        return report_file

    def _generate_root_cause_summary(self, failed_cases: List[Dict]) -> Dict[str, Any]:
        """生成根因分析摘要"""
        summary = {
            "web_search_quality_issues": [],
            "local_db_coverage_gaps": [],
            "intent_classification_issues": [],
            "llm_extraction_issues": [],
            "recommendations": []
        }

        for case in failed_cases:
            analysis = case.get("root_cause_analysis", {})
            if not analysis:
                continue

            case_summary = {
                "id": case.get("id"),
                "query": case.get("query"),
                "probable_cause": analysis.get("probable_cause"),
                "suggested_fixes": analysis.get("suggested_fixes", [])
            }

            # 分类问题
            cause = analysis.get("probable_cause", "").lower()
            if "web search" in cause or "tavily" in cause:
                summary["web_search_quality_issues"].append(case_summary)
            elif "database" in cause or "coverage" in cause:
                summary["local_db_coverage_gaps"].append(case_summary)
            elif "intent" in cause or "识别" in cause:
                summary["intent_classification_issues"].append(case_summary)
            elif "llm" in cause or "提取" in cause:
                summary["llm_extraction_issues"].append(case_summary)

            # 收集所有修复建议
            summary["recommendations"].extend(analysis.get("suggested_fixes", []))

        # 去重建议
        summary["recommendations"] = list(set(summary["recommendations"]))

        return summary

    @pytest.mark.asyncio
    @pytest.mark.parametrize("test_case", DIRECT_SONG_TEST_CASES, ids=lambda x: x["id"])
    async def test_direct_song_search(self, test_case):
        """
        测试直接歌曲名称搜索

        对于标记为 FAILED 的已知失败用例，我们记录但不失败测试，
        以便跟踪修复进度。
        """
        query = test_case["query"]
        expected_song = test_case["expected_song"]
        expected_artist = test_case["expected_artist"]
        is_known_failure = test_case.get("status") == "FAILED"

        # 创建请求
        request = MusicAgentWebhookRequest(
            model="test",
            stream=True,
            messages=[WebhookMessage(role="user", content=query)],
            sessionId=f"test_{test_case['id']}"
        )

        # 收集流式响应
        response_data = await collect_stream_response(
            handle_music_agent_webhook(request)
        )

        # 提取播放的歌曲
        final_response = response_data.get("final_response")
        played_song = extract_played_song(final_response)

        # 断言验证
        assert played_song is not None, f"[{test_case['id']}] 没有收到最终响应"
        assert played_song.get("has_play_action"), f"[{test_case['id']}] 没有生成播放指令"

        # 验证歌曲匹配
        is_match = is_song_match(
            played_song,
            expected_song,
            expected_artist
        )

        if not is_match:
            error_msg = (
                f"[{test_case['id']}] 歌曲不匹配\n"
                f"  查询: {query}\n"
                f"  预期: {expected_song} - {expected_artist}\n"
                f"  实际: {played_song.get('title')} - {played_song.get('artist')}\n"
                f"  已知问题: {test_case.get('notes', 'N/A')}\n"
                f"  响应内容: {played_song.get('stream_content', '')[:200]}"
            )

            if is_known_failure:
                # 已知失败，记录但不失败测试
                pytest.xfail(f"[已知失败] {error_msg}")
            else:
                pytest.fail(error_msg)

    @pytest.mark.asyncio
    @pytest.mark.parametrize("test_case", LYRICS_TEST_CASES, ids=lambda x: x["id"])
    async def test_lyrics_search(self, test_case):
        """
        测试歌词片段搜索

        对于标记为 FAILED 的已知失败用例，我们记录但不失败测试，
        以便跟踪修复进度。
        """
        query = test_case["query"]
        expected_song = test_case["expected_song"]
        expected_artist = test_case["expected_artist"]
        is_known_failure = test_case.get("status") == "FAILED"

        # 创建请求
        request = MusicAgentWebhookRequest(
            model="test",
            stream=True,
            messages=[WebhookMessage(role="user", content=query)],
            sessionId=f"test_{test_case['id']}"
        )

        # 收集流式响应
        response_data = await collect_stream_response(
            handle_music_agent_webhook(request)
        )

        # 提取播放的歌曲
        final_response = response_data.get("final_response")
        played_song = extract_played_song(final_response)

        # 验证基本响应
        if played_song is None:
            if is_known_failure:
                pytest.skip(f"[{test_case['id']}] 已知失败: 没有收到最终响应")
            else:
                pytest.fail(f"[{test_case['id']}] 没有收到最终响应")

        # 验证歌曲匹配
        is_match = is_song_match(
            played_song,
            expected_song,
            expected_artist
        )

        if not is_match:
            error_msg = (
                f"[{test_case['id']}] 歌曲不匹配\n"
                f"  查询: {query}\n"
                f"  预期: {expected_song} - {expected_artist}\n"
                f"  实际: {played_song.get('title')} - {played_song.get('artist')}\n"
                f"  已知问题: {test_case.get('notes', 'N/A')}\n"
                f"  响应内容: {played_song.get('stream_content', '')[:200]}"
            )

            if is_known_failure:
                # 已知失败，记录但不失败测试
                pytest.xfail(f"[已知失败] {error_msg}")
            else:
                pytest.fail(error_msg)

    @pytest.mark.asyncio
    async def test_batch_webhook_regression(self, regression_report_path):
        """
        批量运行所有回归测试用例，生成完整报告（包含根因分析）

        这个测试会运行所有用例并收集失败情况，最后生成详细报告。
        报告包含：
        - 失败分类统计
        - 根因分析摘要
        - 修复建议汇总
        """
        results = {
            "passed": [],
            "failed": [],
            "skipped": []
        }

        for test_case in ALL_WEBHOOK_TEST_CASES:
            case_id = test_case["id"]

            # 支持两种用例格式：单轮(query)和多轮(messages)
            if "query" in test_case:
                # 单轮查询格式
                query = test_case["query"]
                messages = [WebhookMessage(role="user", content=query)]
            elif "messages" in test_case:
                # 多轮对话格式 - 提取最后一条用户消息作为查询描述
                messages = [WebhookMessage(role=m["role"], content=m["content"]) for m in test_case["messages"]]
                query = test_case["messages"][-1]["content"]  # 用于日志和报告
            else:
                # 跳过无效用例
                results["skipped"].append({"id": case_id, "reason": "无效的用例格式"})
                continue

            expected_song = test_case["expected_song"]
            expected_artist = test_case["expected_artist"]
            is_known_failure = test_case.get("status") == "FAILED"

            try:
                # 创建请求
                request = MusicAgentWebhookRequest(
                    model="test",
                    stream=True,
                    messages=messages,
                    sessionId=f"test_{case_id}"
                )

                # 收集响应
                response_data = await collect_stream_response(
                    handle_music_agent_webhook(request)
                )

                # 提取播放的歌曲
                final_response = response_data.get("final_response")
                played_song = extract_played_song(final_response)

                # 验证
                if played_song is None:
                    raise AssertionError("没有收到最终响应")

                is_match = is_song_match(played_song, expected_song, expected_artist)

                if is_match:
                    results["passed"].append({
                        "id": case_id,
                        "query": query,
                        "result": f"{played_song.get('title')} - {played_song.get('artist')}"
                    })
                else:
                    failure_info = {
                        "id": case_id,
                        "query": query,
                        "expected": f"{expected_song} - {expected_artist}",
                        "actual": f"{played_song.get('title')} - {played_song.get('artist')}",
                        "is_known_failure": is_known_failure,
                        "stream_content": played_song.get("stream_content", "")[:200]
                    }

                    # 添加根因分析（如果存在）
                    if test_case.get("root_cause_analysis"):
                        failure_info["root_cause_analysis"] = test_case["root_cause_analysis"]
                        failure_info["root_cause_category"] = test_case["root_cause_analysis"].get("probable_cause", "unknown")

                    if test_case.get("actual_result"):
                        failure_info["historical_failure"] = test_case["actual_result"]
                    if test_case.get("notes"):
                        failure_info["notes"] = test_case["notes"]

                    results["failed"].append(failure_info)

            except Exception as e:
                error_info = {
                    "id": case_id,
                    "query": query,
                    "error": str(e),
                    "is_known_failure": is_known_failure,
                    "notes": test_case.get("notes", "")
                }
                if test_case.get("root_cause_analysis"):
                    error_info["root_cause_analysis"] = test_case["root_cause_analysis"]
                results["failed"].append(error_info)

        # 生成报告
        if results["failed"]:
            report_file = self.save_failure_report(results["failed"], regression_report_path, ALL_WEBHOOK_TEST_CASES)

            # 打印详细报告
            print(f"\n\n{'='*70}")
            print(f"📊 Webhook 回归测试报告")
            print(f"{'='*70}")
            print(f"总计: {len(ALL_WEBHOOK_TEST_CASES)}")
            print(f"通过: {len(results['passed'])} ✅")
            print(f"失败: {len(results['failed'])} ❌")
            print(f"通过率: {((len(ALL_WEBHOOK_TEST_CASES) - len(results['failed'])) / len(ALL_WEBHOOK_TEST_CASES) * 100):.1f}%")

            known_failures = [f for f in results["failed"] if f.get("is_known_failure")]
            new_failures = [f for f in results["failed"] if not f.get("is_known_failure")]

            if known_failures:
                print(f"\n📌 已知失败 (已记录根因，待修复): {len(known_failures)}")
                for f in known_failures:
                    analysis = f.get("root_cause_analysis", {})
                    print(f"  [{f['id']}] {f['query'][:60]}...")
                    print(f"    预期: {f.get('expected', 'N/A')}")
                    print(f"    实际: {f.get('actual', f.get('error', 'N/A'))}")
                    if analysis:
                        print(f"    根因: {analysis.get('probable_cause', 'N/A')}")

            if new_failures:
                print(f"\n⚠️  新发现的失败 (需要调查): {len(new_failures)}")
                for f in new_failures:
                    print(f"  [{f['id']}] {f['query'][:60]}...")
                    print(f"    错误: {f.get('error', f.get('actual', 'N/A'))}")

            # 输出根因分析摘要
            report_data = json.loads(open(report_file).read())
            root_cause_summary = report_data.get("root_cause_summary", {})

            if root_cause_summary.get("recommendations"):
                print(f"\n💡 建议修复方向:")
                for i, rec in enumerate(root_cause_summary["recommendations"][:5], 1):
                    print(f"   {i}. {rec}")

            print(f"\n📄 详细报告: {report_file}")
            print(f"{'='*70}\n")

        # 只有新失败才导致测试失败
        new_failures = [f for f in results["failed"] if not f.get("is_known_failure")]
        assert len(new_failures) == 0, f"发现 {len(new_failures)} 个新的回归失败"

    @pytest.mark.asyncio
    @pytest.mark.parametrize("test_case", MULTI_TURN_SELECTION_CASES, ids=lambda x: x["id"])
    async def test_multi_turn_selection(self, test_case):
        """
        测试多轮对话选择功能 - 验证 LLM 改写和指代消解
        """
        messages = test_case["messages"]
        expected_song = test_case["expected_song"]
        expected_artist = test_case["expected_artist"]

        # 创建请求
        request = MusicAgentWebhookRequest(
            model="test",
            stream=True,
            messages=[WebhookMessage(role=m["role"], content=m["content"]) for m in messages],
            sessionId=f"test_{test_case['id']}_{datetime.now().strftime('%H%M%S')}"
        )

        # 收集流式响应
        response_data = await collect_stream_response(
            handle_music_agent_webhook(request)
        )

        # 提取播放的歌曲
        final_response = response_data.get("final_response")
        played_song = extract_played_song(final_response)

        # 验证基本响应
        assert played_song is not None, f"[{test_case['id']}] 没有收到最终响应"
        assert played_song.get("has_play_action"), f"[{test_case['id']}] 没有生成播放指令"

        # 验证歌曲匹配
        is_match = is_song_match(played_song, expected_song, expected_artist)

        if not is_match:
            error_msg = (
                f"[{test_case['id']}] 多轮选择歌曲不匹配\n"
                f"  描述: {test_case.get('description', 'N/A')}\n"
                f"  最后用户输入: {messages[-1]['content']}\n"
                f"  预期: {expected_song} - {expected_artist}\n"
                f"  实际: {played_song.get('title')} - {played_song.get('artist')}\n"
                f"  响应内容: {played_song.get('stream_content', '')[:200]}"
            )
            pytest.fail(error_msg)

    @pytest.mark.asyncio
    async def test_llm_rewrite_selection(self):
        """专门测试 LLM 改写功能 - 验证 '第一首' 被改写成具体歌曲名"""
        from api.webhook_handler import analyze_intent_with_context

        messages = [
            {"role": "user", "content": "Recommend songs for running"},
            {"role": "assistant", "content": "1. Eye of the Tiger by Survivor\n2. Stronger by Kanye West"},
            {"role": "user", "content": "the first one"}
        ]

        history_text = "\n".join([f"{m['role']}: {m['content']}" for m in messages[:-1]])
        current_input = messages[-1]["content"]

        last_results = [
            {"title": "Eye of the Tiger", "artist": "Survivor"},
            {"title": "Stronger", "artist": "Kanye West"}
        ]

        intent_result = await analyze_intent_with_context(
            current_input=current_input,
            history=history_text,
            last_results=last_results
        )

        # 验证意图
        assert intent_result.get("intent_type") == "select_from_results", \
            f"意图应为 select_from_results，实际是 {intent_result.get('intent_type')}"

        # 验证 LLM 是否提供了改写的歌曲名
        params = intent_result.get("parameters", {})
        resolved_query = intent_result.get("resolved_query", "")

        assert "Eye of the Tiger" in resolved_query or params.get("query") == "Eye of the Tiger", \
            f"LLM 应将 '第一首' 改写成 'Eye of the Tiger'，resolved_query={resolved_query}, params={params}"

        print(f"\n✅ LLM 改写验证通过: 'the first one' -> {resolved_query or params.get('query')}")


@pytest.mark.regression
@pytest.mark.webhook
@pytest.mark.asyncio
class TestWebhookIntentAnalysis:
    """测试 webhook 的意图分析功能"""

    @pytest.mark.parametrize("query,expected_intent", [
        ("I want to listen to the song Let's Kill This Love", "search"),
        ('I want to hear the song with the lyric "Every night in my dreams"', "search_by_lyrics"),
        ("Play me some Taylor Swift", "recommend_by_artist"),
    ])
    async def test_intent_classification(self, query, expected_intent):
        """测试意图分类是否正确"""
        result = await analyze_intent_with_context(
            current_input=query,
            history="",
            last_results=None
        )

        actual_intent = result.get("intent_type")

        assert actual_intent == expected_intent, (
            f"意图识别错误:\n"
            f"  查询: {query}\n"
            f"  预期: {expected_intent}\n"
            f"  实际: {actual_intent}"
        )
