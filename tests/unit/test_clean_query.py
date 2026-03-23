"""Unit tests for _clean_search_query function."""

import pytest


# Import the function to test
# Note: This requires importing from graphs.music_graph
# We test the function behavior directly


class TestCleanSearchQuery:
    """Tests for query cleaning function."""

    TEST_CASES = [
        # (input_query, expected_contains)
        ("帮我找一首周杰伦的歌", "周杰伦"),
        ("我想听稻香", "稻香"),
        ("来首快乐的歌", "快乐"),
        ("给我推荐几首摇滚", "摇滚"),
        ("有没有关于爱情的歌曲", "爱情"),
        ("播放一首周杰伦的晴天", "晴天"),
        # English queries should pass through
        ("the sky is the limit", "the sky is the limit"),
        ("play me a song by Lady Gaga", "play me a song by Lady Gaga"),
        # Edge cases
        ("周杰伦", "周杰伦"),  # Already clean
        ("", ""),  # Empty
    ]

    @pytest.mark.parametrize("query,expected", TEST_CASES)
    def test_clean_query(self, query, expected):
        """Test that query cleaning works correctly."""
        # Import here to avoid loading heavy dependencies
        try:
            from graphs.music_graph import _clean_search_query

            result = _clean_search_query(query)
            # The result should contain the expected substring
            assert expected in result, f"Expected '{expected}' in '{result}'"
        except ImportError:
            # If we can't import, mark as skip
            pytest.skip("Cannot import _clean_search_query")

    def test_clean_query_removes_prefixes(self):
        """Test that common prefixes are removed."""
        try:
            from graphs.music_graph import _clean_search_query

            result = _clean_search_query("帮我找一首周杰伦的歌")
            # Should not contain the prefix
            assert not result.startswith("帮我")
            assert not result.startswith("我想")
            assert "周杰伦" in result
        except ImportError:
            pytest.skip("Cannot import _clean_search_query")

    def test_clean_query_handles_special_chars(self):
        """Test handling of special characters."""
        try:
            from graphs.music_graph import _clean_search_query

            result = _clean_search_query("周杰伦《稻香》")
            assert "周杰伦" in result
            assert "稻香" in result
        except ImportError:
            pytest.skip("Cannot import _clean_search_query")
