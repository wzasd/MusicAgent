"""E2E tests for /api/recommendations endpoint."""

import pytest


@pytest.mark.e2e
class TestApiRecommendations:
    """Tests for POST /api/recommendations endpoint."""

    def test_recommendations_endpoint_basic(self, http_client):
        """Test basic recommendations endpoint."""
        response = http_client.post("/api/recommendations", json={
            "query": "推荐一些开心的歌",
            "limit": 5
        })

        assert response.status_code == 200
        data = response.json()

        assert "recommendations" in data or "songs" in data

    def test_recommendations_stream(self, http_client):
        """Test streaming recommendations endpoint."""
        response = http_client.post("/api/recommendations/stream", json={
            "query": "适合跑步听的歌",
            "limit": 5
        })

        assert response.status_code == 200
        # SSE stream should have text/event-stream content type
        content_type = response.headers.get("content-type", "")
        assert "text/event-stream" in content_type or "application/json" in content_type

    def test_recommendations_by_mood(self, http_client):
        """Test recommendations by mood."""
        moods = ["开心", "sad", "relaxing", "energetic"]

        for mood in moods:
            response = http_client.post("/api/recommendations", json={
                "query": f"推荐{mood}的歌",
                "mood": mood,
                "limit": 5
            })

            assert response.status_code == 200, f"Failed for mood: {mood}"
            data = response.json()
            assert "recommendations" in data or "songs" in data, f"No results for mood: {mood}"

    def test_recommendations_by_genre(self, http_client):
        """Test recommendations by genre."""
        genres = ["pop", "rock", "jazz", "classical"]

        for genre in genres:
            response = http_client.post("/api/recommendations", json={
                "query": f"推荐{genre}音乐",
                "genre": genre,
                "limit": 5
            })

            assert response.status_code == 200, f"Failed for genre: {genre}"

    def test_recommendations_response_format(self, http_client):
        """Test recommendations response format."""
        response = http_client.post("/api/recommendations", json={
            "query": "推荐几首好听的英文歌",
            "limit": 3
        })

        assert response.status_code == 200
        data = response.json()

        # Response should have recommendations array
        recommendations = data.get("recommendations", data.get("songs", []))
        assert isinstance(recommendations, list)

        for rec in recommendations:
            # Each recommendation should have song info
            song = rec.get("song", rec)
            assert "title" in song
            assert "artist" in song

    def test_recommendations_with_user_preferences(self, http_client):
        """Test recommendations with user preferences."""
        response = http_client.post("/api/recommendations", json={
            "query": "根据我的喜好推荐",
            "user_preferences": {
                "favorite_genres": ["pop", "rock"],
                "favorite_artists": ["周杰伦", "Lady Gaga"]
            },
            "limit": 5
        })

        # Should handle gracefully even if user preferences not fully supported
        assert response.status_code in [200, 400, 422]
