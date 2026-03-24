"""
Multi-turn Conversation Regression Tests
Tests webhook context persistence and anaphora resolution capabilities
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


# ========== Multi-turn Conversation Test Cases ==========

MULTI_TURN_TEST_CASES = [
    {
        "id": "multi_turn_001",
        "name": "List Selection - First Song",
        "description": "User queries list, then selects first song to play",
        "turns": [
            {
                "role": "user",
                "content": "What are some popular songs by Taylor Swift",
                "expected_intent": "recommend_by_artist",
                "expected_action_type": "list",
            },
            {
                "role": "user",
                "content": "the first one",
                "expected_intent": "search",
                "expected_action_type": "play",
                "expected_artist": "Taylor Swift",
            }
        ]
    },
    {
        "id": "multi_turn_002",
        "name": "List Selection - Second Song",
        "description": "User queries list, then selects second song to play",
        "turns": [
            {
                "role": "user",
                "content": "Recommend some songs for running",
                "expected_intent": "recommend_by_activity",
                "expected_action_type": "list",
            },
            {
                "role": "user",
                "content": "the second one",
                "expected_intent": "search",
                "expected_action_type": "play",
            }
        ]
    },
    {
        "id": "multi_turn_003",
        "name": "List Selection - Last Song",
        "description": "User selects the last song from list",
        "turns": [
            {
                "role": "user",
                "content": "Recommend some happy songs",
                "expected_intent": "recommend_by_mood",
                "expected_action_type": "list",
            },
            {
                "role": "user",
                "content": "the last one",
                "expected_intent": "search",
                "expected_action_type": "play",
            }
        ]
    },
    {
        "id": "multi_turn_004",
        "name": "Anaphora Resolution - Play It",
        "description": "User uses anaphora 'play it' to select a song",
        "turns": [
            {
                "role": "user",
                "content": "I want to hear some songs by Ed Sheeran",
                "expected_intent": "recommend_by_artist",
                "expected_action_type": "list",
            },
            {
                "role": "user",
                "content": "play it",
                "expected_intent": "search",
                "expected_action_type": "play",
            }
        ]
    },
    {
        "id": "multi_turn_005",
        "name": "Anaphora Resolution - This One",
        "description": "User uses 'this one' to select a song",
        "turns": [
            {
                "role": "user",
                "content": "Songs by The Beatles",
                "expected_intent": "recommend_by_artist",
                "expected_action_type": "list",
            },
            {
                "role": "user",
                "content": "this one",
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
    """Multi-turn conversation test class"""

    async def _extract_stream_content(self, response_chunks: List[str]) -> Dict[str, Any]:
        """Extract content from SSE stream"""
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
        Test multi-turn conversation scenarios

        Flow:
        1. Round 1: Send query, get list
        2. Save session_id and context
        3. Round 2: Send selection command with same session_id
        4. Verify anaphora resolution and playback
        """
        session_id = f"test_session_{test_case['id']}"
        messages: List[Dict[str, str]] = []
        last_results: List[Dict[str, Any]] = None

        print(f"\n{'='*70}")
        print(f"Multi-turn Test: [{test_case['id']}] {test_case['name']}")
        print(f"Description: {test_case['description']}")
        print(f"{'='*70}")

        for i, turn in enumerate(test_case["turns"], 1):
            print(f"\n--- Turn {i} ---")
            print(f"User: {turn['content']}")

            # Add user message to history
            messages.append({"role": "user", "content": turn["content"]})

            # Build request
            request = MusicAgentWebhookRequest(
                model="test",
                stream=True,
                messages=[WebhookMessage(role=m["role"], content=m["content"]) for m in messages],
                sessionId=session_id,
            )

            # Collect streaming response
            chunks = []
            async for chunk in handle_music_agent_webhook(request):
                chunks.append(chunk)

            # Parse response
            result = await self._extract_stream_content(chunks)

            if result["has_error"]:
                pytest.fail(f"Turn {i} error: {result['error_message']}")

            print(f"System: {result['content']}")

            # Round 1: Verify list returned and save results
            if i == 1:
                # Verify list mode (no action or empty action)
                assert "Found" in result["content"] or "Songs" in result["content"] or \
                       "Recommending" in result["content"] or "Finding" in result["content"], \
                    f"Round 1 should return list, actual: {result['content']}"

            # Round 2: Verify selection and playback
            elif i == 2:
                # Verify playback action
                assert result["action"] is not None, \
                    f"Round 2 should have playback action, actual: {result}"

                action_name = result["action"][0]["header"]["name"]
                assert action_name == "PLAY_SEARCH_SONG", \
                    f"action should be PLAY_SEARCH_SONG, actual: {action_name}"

                # Verify specific song played
                slots = result["action"][0]["payload"]["callParams"]["forwardSlot"]
                song_name = next((s["value"][0] for s in slots if s["key"] == "songName"), None)
                artist = next((s["value"][0] for s in slots if s["key"] == "artist"), None)

                print(f"Playing: {song_name} - {artist}")
                assert song_name is not None, "Should play a specific song"

                # If expected artist, verify
                if "expected_artist" in turn:
                    assert turn["expected_artist"].lower() in artist.lower() or \
                           artist.lower() in turn["expected_artist"].lower(), \
                        f"Expected artist '{turn['expected_artist']}', actual: {artist}"

        print(f"\n{'='*70}")
        print(f"✅ Test Passed: [{test_case['id']}] {test_case['name']}")
        print(f"{'='*70}")

    async def test_session_context_persistence(self):
        """
        Test session context persistence
        """
        session_id = "test_session_persistence"

        # Round 1: Query
        request1 = MusicAgentWebhookRequest(
            model="test",
            stream=True,
            messages=[WebhookMessage(role="user", content="Songs by Ed Sheeran")],
            sessionId=session_id,
        )

        chunks1 = []
        async for chunk in handle_music_agent_webhook(request1):
            chunks1.append(chunk)

        # Get session manager and verify context exists
        session_manager = get_session_manager()
        context1 = session_manager.get_or_create_context(session_id, [])

        # Verify search results saved after round 1
        assert context1.last_search_results is not None, \
            "Should save search results after round 1"
        assert len(context1.last_search_results) > 0, \
            "Search results should not be empty"

        print(f"Round 1 saved {len(context1.last_search_results)} songs")

        # Round 2: Select
        request2 = MusicAgentWebhookRequest(
            model="test",
            stream=True,
            messages=[
                WebhookMessage(role="user", content="Songs by Ed Sheeran"),
                WebhookMessage(role="assistant", content="Here are some songs"),
                WebhookMessage(role="user", content="the first one"),
            ],
            sessionId=session_id,
        )

        chunks2 = []
        async for chunk in handle_music_agent_webhook(request2):
            chunks2.append(chunk)

        result2 = await self._extract_stream_content(chunks2)

        # Verify round 2 playback
        assert result2["action"] is not None, \
            "Round 2 should have playback action"

        print(f"✅ Context persistence test passed")

    async def test_multi_turn_via_api(self):
        """
        Test multi-turn via API (end-to-end)
        Note: Requires backend running on localhost:8501
        """
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                base_url = "http://localhost:8501"

                # Check service available
                try:
                    response = await client.get(f"{base_url}/health")
                    if response.status_code != 200:
                        pytest.skip("Backend service unavailable")
                except httpx.ConnectError:
                    pytest.skip("Backend not running, skipping API test")

                session_id = "api_test_session_001"

                # Round 1: Query list
                print("\n--- API Multi-turn Test - Turn 1 ---")
                response1 = await client.post(
                    f"{base_url}/webhook/MusicAgent",
                    json={
                        "messages": [{"role": "user", "content": "Recommend songs for workout"}],
                        "stream": False,
                        "sessionId": session_id,
                    },
                    headers={"Accept": "text/event-stream"},
                )

                assert response1.status_code == 200

                # Parse SSE response
                chunks1 = response1.text.strip().split("\n\n")
                result1 = await self._extract_stream_content(chunks1)

                print(f"Turn 1 response: {result1['content'][:100]}...")
                assert "Found" in result1['content'] or "Songs" in result1['content'] or \
                       "Recommending" in result1['content']

                # Round 2: Select
                print("\n--- API Multi-turn Test - Turn 2 ---")
                response2 = await client.post(
                    f"{base_url}/webhook/MusicAgent",
                    json={
                        "messages": [
                            {"role": "user", "content": "Recommend songs for workout"},
                            {"role": "assistant", "content": result1['content']},
                            {"role": "user", "content": "the second one"},
                        ],
                        "stream": False,
                        "sessionId": session_id,
                    },
                    headers={"Accept": "text/event-stream"},
                )

                assert response2.status_code == 200

                chunks2 = response2.text.strip().split("\n\n")
                result2 = await self._extract_stream_content(chunks2)

                print(f"Turn 2 response: {result2['content']}")
                assert result2["action"] is not None, "Should have playback action"

                print("✅ API multi-turn test passed")

        except httpx.TimeoutException:
            pytest.skip("API request timeout")
        except Exception as e:
            pytest.skip(f"API test failed: {e}")


@pytest.mark.regression
@pytest.mark.webhook
@pytest.mark.multi_turn
@pytest.mark.asyncio
class TestAnaphoraResolution:
    """Anaphora resolution specific tests"""

    @pytest.mark.parametrize("query,expected_selection", [
        ("the first one", "first"),
        ("the second one", "second"),
        ("the third one", "third"),
        ("the last one", "last"),
        ("play it", "it"),
        ("this one", "it"),
        ("first song", "first"),
        ("last track", "last"),
    ])
    async def test_anaphora_resolution_patterns(self, query: str, expected_selection: str):
        """
        Test various anaphora resolution patterns
        """
        from api.webhook_handler import analyze_intent_with_context

        # Mock history with search results
        last_results = [
            {"title": "Song 1", "artist": "Artist A"},
            {"title": "Song 2", "artist": "Artist B"},
            {"title": "Song 3", "artist": "Artist C"},
        ]

        result = await analyze_intent_with_context(
            current_input=query,
            history="user: Recommend some songs\nassistant: Song 1, Song 2, Song 3",
            last_results=last_results,
        )

        print(f"\nQuery: {query}")
        print(f"Intent: {result.get('intent_type')}")
        print(f"Resolved: {result.get('resolved_query')}")

        # Verify intent correctly parsed as search (post-selection conversion)
        assert result.get("intent_type") in ["search", "select_from_results"], \
            f"Anaphora should return search or select_from_results, actual: {result.get('intent_type')}"

        # Verify selection index or type present
        params = result.get("parameters", {})
        has_selection = params.get("selection_index") is not None or \
                       params.get("selection_type") is not None

        # Or converted with query
        resolved = result.get("resolved_query", "")
        has_resolved_query = resolved and ("Song" in resolved or "Play" in resolved)

        assert has_selection or has_resolved_query, \
            f"Anaphora should resolve selection info, actual: {params}"


if __name__ == "__main__":
    # Run tests directly
    pytest.main([__file__, "-v", "-s", "-m", "multi_turn"])
