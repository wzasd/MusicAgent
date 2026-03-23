"""Integration tests for lyrics search functionality."""

import pytest


@pytest.mark.integration
class TestSearchByLyrics:
    """Tests for lyrics-based song search."""

    async def test_local_db_hit(self, lyrics_engine):
        """Test searching lyrics that exist in local database."""
        # "后来终于在眼泪中明白" should find "后来" by 刘若英
        results = lyrics_engine.search_by_lyrics("后来终于在眼泪中明白", top_k=5)

        assert len(results) > 0, "Should find at least one result"
        # Check that "后来" is in the results
        titles = [r["title"] for r in results]
        assert any("后来" in t for t in titles), f"Expected '后来' in {titles}"

        # Check source is local db
        assert results[0].get("source") == "lyrics_db"

    async def test_web_fallback(self, lyrics_engine):
        """Test searching lyrics not in local DB - should use web search fallback."""
        # "燃烧我的卡路里" is not in the small local DB
        query = "燃烧我的卡路里"
        results = await lyrics_engine.search_with_web_fallback(query, top_k=5)

        assert len(results) > 0, "Should find at least one result via web fallback"
        # Check that result contains expected keywords
        titles = [r["title"] for r in results]
        assert any("卡路里" in t for t in titles), f"Expected '卡路里' in {titles}"

        # Source should indicate web search
        source = results[0].get("source", "")
        assert source in ["web_search", "llm_lyrics", "lyrics_db"], f"Unexpected source: {source}"

    async def test_lyrics_result_format(self, lyrics_engine):
        """Test that lyrics search returns properly formatted results."""
        results = await lyrics_engine.search_with_web_fallback("后来", top_k=3)

        assert len(results) > 0

        for result in results:
            # Required fields
            assert "title" in result, "Result must have 'title'"
            assert "artist" in result, "Result must have 'artist'"
            assert result["title"], "Title should not be empty"
            assert result["artist"], "Artist should not be empty"

    @pytest.mark.slow
    async def test_obscure_lyrics(self, lyrics_engine):
        """Test with obscure/less common lyrics."""
        # A less common Chinese lyric
        results = await lyrics_engine.search_with_web_fallback("遥远的她", top_k=5)

        # May or may not find results, but should not crash
        assert isinstance(results, list)
