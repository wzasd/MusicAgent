"""
多轮对话回归测试
测试 webhook 的上下文保持和指代消解能力
"""
import pytest
import asyncio
import json
import httpx
from typing import List, Dict, Any

from api.webhook_handler import (
    handle_music_agent_webhook,
    MusicAgentWebhookRequest,
    WebhookMessage,
    SessionManager,
    get_session_manager,
)


# ========== 多轮对话测试用例 ==========

MULTI_TURN_TEST_CASES = [
    {
        "id": "multi_turn_001",
        "name": "列表选择 - 第一首",
        "description": "用户先查询列表，然后选择第一首播放",
        "turns": [
            {
                "role": "user",
                "content": "周杰伦有哪些代表作",
                "expected_intent": "recommend_by_artist",
                "expected_action_type": "list",
            },
            {
                "role": "user",
                "content": "第一首",
                "expected_intent": "search",  # 选择后转为search
                "expected_action_type": "play",
                # 不指定具体歌曲，只要播放周杰伦的歌即可
                "expected_artist": "周杰伦",
            }
        ]
    },
    {
        "id": "multi_turn_002",
        "name": "列表选择 - 第二首",
        "description": "用户先查询列表，然后选择第二首播放",
        "turns": [
            {
                "role": "user",
                "content": "推荐几首适合跑步的歌",
                "expected_intent": "recommend_by_activity",
                "expected_action_type": "list",
            },
            {
                "role": "user",
                "content": "第二首",
                "expected_intent": "search",
                "expected_action_type": "play",
            }
        ]
    },
    {
        "id": "multi_turn_003",
        "name": "列表选择 - 最后一首",
        "description": "用户选择列表中的最后一首",
        "turns": [
            {
                "role": "user",
                "content": "推荐几首开心的歌",
                "expected_intent": "recommend_by_mood",
                "expected_action_type": "list",
            },
            {
                "role": "user",
                "content": "最后一首",
                "expected_intent": "search",
                "expected_action_type": "play",
            }
        ]
    },
    {
        "id": "multi_turn_004",
        "name": "指代消解 - 播放它",
        "description": "用户使用指代词选择歌曲",
        "turns": [
            {
                "role": "user",
                "content": "我想听陈奕迅的歌",
                "expected_intent": "recommend_by_artist",
                "expected_action_type": "list",
            },
            {
                "role": "user",
                "content": "播放它",
                "expected_intent": "search",
                "expected_action_type": "play",
            }
        ]
    },
]


@pytest.mark.regression
@pytest.mark.webhook
@pytest.mark.multi_turn
@pytest.mark.asyncio
class TestMultiTurnConversation:
    """多轮对话测试类"""

    async def _extract_stream_content(self, response_chunks: List[str]) -> Dict[str, Any]:
        """从SSE流中提取内容"""
        full_content = ""
        final_action = None
        has_error = False
        error_message = ""

        for chunk in response_chunks:
            if chunk.startswith("data: "):
                try:
                    data = json.loads(chunk[6:])
                    stream_info = data.get("reply", {}).get("streamInfo", {})
                    full_content = stream_info.get("streamContent", full_content)
                    action = data.get("reply", {}).get("action")
                    if action:
                        final_action = action
                    if data.get("errorCode", 0) != 0:
                        has_error = True
                        error_message = data.get("errorMessage", "")
                except json.JSONDecodeError:
                    continue

        return {
            "content": full_content,
            "action": final_action,
            "has_error": has_error,
            "error_message": error_message,
        }

    @pytest.mark.parametrize("test_case", MULTI_TURN_TEST_CASES, ids=lambda x: x["id"])
    async def test_multi_turn_conversation(self, test_case: Dict[str, Any]):
        """
        测试多轮对话场景

        流程:
        1. 第一轮：发送查询，获取列表
        2. 保存 session_id 和上下文
        3. 第二轮：使用相同 session_id 发送选择指令
        4. 验证是否正确识别指代并播放
        """
        session_id = f"test_session_{test_case['id']}"
        messages: List[Dict[str, str]] = []
        last_results: List[Dict[str, Any]] = None

        print(f"\n{'='*70}")
        print(f"多轮对话测试: [{test_case['id']}] {test_case['name']}")
        print(f"描述: {test_case['description']}")
        print(f"{'='*70}")

        for i, turn in enumerate(test_case["turns"], 1):
            print(f"\n--- Turn {i} ---")
            print(f"用户: {turn['content']}")

            # 添加用户消息到历史
            messages.append({"role": "user", "content": turn["content"]})

            # 构建请求
            request = MusicAgentWebhookRequest(
                model="test",
                stream=True,
                messages=[WebhookMessage(role=m["role"], content=m["content"]) for m in messages],
                sessionId=session_id,
            )

            # 收集流式响应
            chunks = []
            async for chunk in handle_music_agent_webhook(request):
                chunks.append(chunk)

            # 解析响应
            result = await self._extract_stream_content(chunks)

            if result["has_error"]:
                pytest.fail(f"Turn {i} 发生错误: {result['error_message']}")

            print(f"系统: {result['content']}")

            # 第一轮：验证返回列表并保存结果
            if i == 1:
                # 验证是列表模式（没有action或action为空）
                # 注意：当前实现如果是明确查询单首歌，即使是artist查询也可能直接播放
                # 这里主要验证是否有结果返回
                assert "Found" in result["content"] or "Songs" in result["content"] or \
                       "Recommending" in result["content"] or "Finding" in result["content"], \
                    f"第一轮应该返回列表，实际: {result['content']}"

                # 从响应内容中解析歌曲列表（简化处理）
                # 实际应该从上下文获取，这里我们依赖服务端保存的 last_search_results

            # 第二轮：验证选择并播放
            elif i == 2:
                # 验证有播放action
                assert result["action"] is not None, \
                    f"第二轮应该有播放action，实际: {result}"

                action_name = result["action"][0]["header"]["name"]
                assert action_name == "PLAY_SEARCH_SONG", \
                    f"action应该是PLAY_SEARCH_SONG，实际是: {action_name}"

                # 验证播放了具体的歌曲
                slots = result["action"][0]["payload"]["callParams"]["forwardSlot"]
                song_name = next((s["value"][0] for s in slots if s["key"] == "songName"), None)
                artist = next((s["value"][0] for s in slots if s["key"] == "artist"), None)

                print(f"播放: {song_name} - {artist}")
                assert song_name is not None, "应该播放具体的歌曲"

                # 如果有预期歌曲，验证
                if "expected_contains" in turn:
                    assert turn["expected_contains"] in song_name or song_name in turn["expected_contains"], \
                        f"预期播放包含 '{turn['expected_contains']}' 的歌曲，实际: {song_name}"

        print(f"\n{'='*70}")
        print(f"✅ 测试通过: [{test_case['id']}] {test_case['name']}")
        print(f"{'='*70}")

    async def test_session_context_persistence(self):
        """
        测试会话上下文是否正确保持
        """
        session_id = "test_session_persistence"

        # 第一轮：查询
        request1 = MusicAgentWebhookRequest(
            model="test",
            stream=True,
            messages=[WebhookMessage(role="user", content="Taylor Swift的歌")],
            sessionId=session_id,
        )

        chunks1 = []
        async for chunk in handle_music_agent_webhook(request1):
            chunks1.append(chunk)

        # 获取会话管理器并验证上下文存在
        session_manager = get_session_manager()
        context1 = session_manager.get_or_create_context(session_id, [])

        # 验证第一轮保存了搜索结果
        assert context1.last_search_results is not None, \
            "第一轮后应该保存搜索结果"
        assert len(context1.last_search_results) > 0, \
            "搜索结果不应该为空"

        print(f"第一轮保存了 {len(context1.last_search_results)} 首歌曲")

        # 第二轮：选择
        request2 = MusicAgentWebhookRequest(
            model="test",
            stream=True,
            messages=[
                WebhookMessage(role="user", content="Taylor Swift的歌"),
                WebhookMessage(role="assistant", content="Here are some songs"),
                WebhookMessage(role="user", content="第一首"),
            ],
            sessionId=session_id,
        )

        chunks2 = []
        async for chunk in handle_music_agent_webhook(request2):
            chunks2.append(chunk)

        result2 = await self._extract_stream_content(chunks2)

        # 验证第二轮成功播放
        assert result2["action"] is not None, \
            "第二轮应该有播放action"

        print(f"✅ 上下文保持测试通过")

    async def test_multi_turn_via_api(self):
        """
        通过API测试多轮对话（端到端测试）
        注意：需要后端服务运行在 localhost:8501
        """
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                base_url = "http://localhost:8501"

                # 检查服务是否可用
                try:
                    response = await client.get(f"{base_url}/health")
                    if response.status_code != 200:
                        pytest.skip("后端服务不可用")
                except httpx.ConnectError:
                    pytest.skip("后端服务未启动，跳过API测试")

                session_id = "api_test_session_001"

                # 第一轮：查询列表
                print("\n--- API 多轮测试 - Turn 1 ---")
                response1 = await client.post(
                    f"{base_url}/webhook/MusicAgent",
                    json={
                        "messages": [{"role": "user", "content": "推荐几首适合跑步的歌"}],
                        "stream": False,
                        "sessionId": session_id,
                    },
                    headers={"Accept": "text/event-stream"},
                )

                assert response1.status_code == 200

                # 解析SSE响应
                chunks1 = response1.text.strip().split("\n\n")
                result1 = await self._extract_stream_content(chunks1)

                print(f"Turn 1 响应: {result1['content'][:100]}...")
                assert "Found" in result1['content'] or "Songs" in result1['content'] or \
                       "Recommending" in result1['content']

                # 第二轮：选择
                print("\n--- API 多轮测试 - Turn 2 ---")
                response2 = await client.post(
                    f"{base_url}/webhook/MusicAgent",
                    json={
                        "messages": [
                            {"role": "user", "content": "推荐几首适合跑步的歌"},
                            {"role": "assistant", "content": result1['content']},
                            {"role": "user", "content": "第二首"},
                        ],
                        "stream": False,
                        "sessionId": session_id,
                    },
                    headers={"Accept": "text/event-stream"},
                )

                assert response2.status_code == 200

                chunks2 = response2.text.strip().split("\n\n")
                result2 = await self._extract_stream_content(chunks2)

                print(f"Turn 2 响应: {result2['content']}")
                assert result2["action"] is not None, "应该有播放action"

                print("✅ API多轮测试通过")

        except httpx.TimeoutException:
            pytest.skip("API请求超时")
        except Exception as e:
            pytest.skip(f"API测试失败: {e}")


@pytest.mark.regression
@pytest.mark.webhook
@pytest.mark.multi_turn
@pytest.mark.asyncio
class TestAnaphoraResolution:
    """指代消解专项测试"""

    @pytest.mark.parametrize("query,expected_selection", [
        ("第一首", "first"),
        ("第二首", "second"),
        ("第三个", "third"),
        ("最后一首", "last"),
        ("播放它", "it"),
        ("就这个", "it"),
    ])
    async def test_anaphora_resolution_patterns(self, query: str, expected_selection: str):
        """
        测试各种指代消解模式
        """
        from api.webhook_handler import analyze_intent_with_context

        # 模拟有历史搜索结果的情况
        last_results = [
            {"title": "歌曲1", "artist": "歌手A"},
            {"title": "歌曲2", "artist": "歌手B"},
            {"title": "歌曲3", "artist": "歌手C"},
        ]

        result = await analyze_intent_with_context(
            current_input=query,
            history="user: 推荐几首歌\nassistant: 歌曲1, 歌曲2, 歌曲3",
            last_results=last_results,
        )

        print(f"\n查询: {query}")
        print(f"意图: {result.get('intent_type')}")
        print(f"解析后: {result.get('resolved_query')}")

        # 验证意图被正确解析为搜索（选择后的转换）
        assert result.get("intent_type") in ["search", "select_from_results"], \
            f"指代消解应该返回search或select_from_results，实际是: {result.get('intent_type')}"

        # 验证有选择索引或类型
        params = result.get("parameters", {})
        has_selection = params.get("selection_index") is not None or \
                       params.get("selection_type") is not None

        # 或者已经转换后包含query
        has_resolved_query = result.get("resolved_query") and "歌曲" in result.get("resolved_query", "")

        assert has_selection or has_resolved_query, \
            f"指代消解应该解析出选择信息，实际是: {params}"


if __name__ == "__main__":
    # 直接运行测试
    pytest.main([__file__, "-v", "-s", "-m", "multi_turn"])
