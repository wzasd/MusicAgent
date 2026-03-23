"""E2E tests for /api/search endpoint."""

import pytest


@pytest.mark.e2e
class TestApiSearch:
    """Tests for POST /api/search endpoint."""

    TEST_CASES = [
        {
            "query": "周杰伦的歌",
            "description": "中文艺术家搜索",
            "expected_source_in": ["local_db", "chroma_db", "artist_web_search", "mixed"],
        },
        {
            "query": "后来终于在眼泪中明白",
            "description": "歌词搜索",
            "expected_intent": "search_by_lyrics",
        },
        {
            "query": "泰坦尼克号主题曲",
            "description": "影视主题曲搜索",
            "expected_intent": "search_by_theme",
        },
        {
            "query": "关于雨的歌",
            "description": "话题搜索",
            "expected_intent": "search_by_topic",
        },
    ]

    def test_search_endpoint_basic(self, http_client):
        """Test basic search endpoint functionality."""
        response = http_client.post("/api/search", json={
            "query": "周杰伦",
            "limit": 5
        })

        assert response.status_code == 200
        data = response.json()

        assert data.get("success") is True
        assert "songs" in data
        assert isinstance(data["songs"], list)

    def test_search_response_format(self, http_client):
        """Test that search response has correct format."""
        response = http_client.post("/api/search", json={
            "query": "Lady Gaga",
            "limit": 3
        })

        assert response.status_code == 200
        data = response.json()

        # Check response structure
        assert "success" in data
        assert "songs" in data
        assert "source" in data
        assert "intent" in data

        # Check song structure
        for song in data["songs"]:
            assert "title" in song
            assert "artist" in song
            assert song["title"]  # Not empty
            assert song["artist"]  # Not empty

    @pytest.mark.parametrize("test_case", TEST_CASES, ids=lambda x: x["description"])
    def test_search_intent_classification(self, http_client, test_case):
        """Test that different queries are classified to correct intents."""
        response = http_client.post("/api/search", json={
            "query": test_case["query"],
            "limit": 5
        })

        assert response.status_code == 200
        data = response.json()

        # Check intent if specified
        if "expected_intent" in test_case:
            assert data.get("intent") == test_case["expected_intent"], \
                f"Query '{test_case['query']}' should be classified as {test_case['expected_intent']}"

        # Check source if specified
        if "expected_source_in" in test_case:
            source = data.get("source", "")
            assert source in test_case["expected_source_in"], \
                f"Unexpected source '{source}' for query '{test_case['query']}'"

    def test_search_empty_query(self, http_client):
        """Test search with empty query."""
        response = http_client.post("/api/search", json={
            "query": "",
            "limit": 5
        })

        # Should handle gracefully (either return empty or 400)
        assert response.status_code in [200, 400]

    def test_search_with_genre_filter(self, http_client):
        """Test search with genre filter."""
        response = http_client.post("/api/search", json={
            "query": "pop music",
            "genre": "pop",
            "limit": 5
        })

        assert response.status_code == 200
        data = response.json()
        assert "songs" in data
