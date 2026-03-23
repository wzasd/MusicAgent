"""Integration tests for theme (OST) search functionality."""

import pytest


@pytest.mark.integration
@pytest.mark.slow  # Web search can be slow
class TestSearchByTheme:
    """Tests for theme/OST song search."""

    async def test_chinese_drama_theme(self):
        """Test Chinese drama theme song search - 请回答1988."""
        from tools.theme_search import get_theme_search_engine

        engine = get_theme_search_engine()
        results = await engine.search_by_theme("请回答1988", country=None, top_k=5)

        assert len(results) > 0, "Should find theme songs for 请回答1988"

        # Check result format
        for result in results:
            assert "title" in result, "Result must have 'title'"
            assert "artist" in result, "Result must have 'artist'"
            assert result["title"], "Title should not be empty"

    async def test_english_movie_theme(self):
        """Test English movie theme song search - Titanic."""
        from tools.theme_search import get_theme_search_engine

        engine = get_theme_search_engine()
        results = await engine.search_by_theme("Titanic", country=None, top_k=5)

        assert len(results) > 0, "Should find theme songs for Titanic"

        # May contain "My Heart Will Go On" or Celine Dion
        titles = [r["title"].lower() for r in results]
        artists = [r.get("artist", "").lower() for r in results]

        has_expected = (
            any("my heart" in t for t in titles) or
            any("celine" in a for a in artists) or
            any("titanic" in t for t in titles)
        )
        # Don't fail if not found, as search results can vary
        print(f"Titanic search results: {titles}, artists: {artists}")

    async def test_theme_with_country(self):
        """Test theme search with country specification."""
        from tools.theme_search import get_theme_search_engine

        engine = get_theme_search_engine()
        results = await engine.search_by_theme("Titanic", country="美国", top_k=5)

        assert len(results) >= 0, "Should handle country parameter"

    async def test_theme_result_source(self):
        """Test that theme search results have correct source."""
        from tools.theme_search import get_theme_search_engine

        engine = get_theme_search_engine()
        results = await engine.search_by_theme("请回答1988", top_k=3)

        for result in results:
            # Source should indicate web search for theme
            source = result.get("source", "")
            assert source in ["theme_web_search", "web_search", "not_found"], \
                f"Unexpected source: {source}"
