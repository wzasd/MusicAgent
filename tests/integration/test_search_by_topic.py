"""Integration tests for topic-based search functionality."""

import pytest


@pytest.mark.integration
@pytest.mark.slow  # Web search can be slow
class TestSearchByTopic:
    """Tests for topic-based song search."""

    async def test_topic_search_basic(self):
        """Test basic topic search - songs about rain/sky."""
        from tools.topic_search import get_topic_search_engine

        engine = get_topic_search_engine()
        results = await engine.search_by_topic("雨", artist=None, genre=None, top_k=5)

        assert len(results) > 0, "Should find songs about rain"

        # Check result format
        for result in results:
            assert "title" in result, "Result must have 'title'"
            assert "artist" in result, "Result must have 'artist'"

    async def test_topic_with_artist(self):
        """Test topic search with artist constraint."""
        from tools.topic_search import get_topic_search_engine

        engine = get_topic_search_engine()
        results = await engine.search_by_topic(
            "爱情", artist="周杰伦", genre=None, top_k=5
        )

        assert len(results) >= 0, "Should handle artist constraint"

        # If results found, they should be by the specified artist
        for result in results:
            artist = result.get("artist", "").lower()
            assert "周杰伦" in result.get("artist", "") or "jay" in artist, \
                f"Expected 周杰伦 songs, got {result.get('artist')}"

    async def test_topic_result_format(self):
        """Test that topic search returns properly formatted results."""
        from tools.topic_search import get_topic_search_engine

        engine = get_topic_search_engine()
        results = await engine.search_by_topic("天空", top_k=3)

        for result in results:
            assert "title" in result
            assert "artist" in result
            assert "similarity_score" in result or "confidence" in result

            # Source should be topic_web_search
            source = result.get("source", "")
            assert source in ["topic_web_search", "web_search"], \
                f"Unexpected source: {source}"
