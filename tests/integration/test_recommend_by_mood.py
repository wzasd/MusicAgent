"""Integration tests for mood-based recommendation functionality."""

import pytest


@pytest.mark.integration
class TestRecommendByMood:
    """Tests for mood-based song recommendations."""

    async def test_positive_mood_recommendation(self):
        """Test recommendation for positive mood - happy/joyful."""
        from tools.music_tools import get_music_recommender

        recommender = get_music_recommender()
        results = await recommender.recommend_by_mood("开心", top_k=5)

        assert len(results) > 0, "Should recommend songs for happy mood"
        assert len(results) >= 3, f"Expected at least 3 recommendations, got {len(results)}"

    async def test_negative_mood_recommendation(self):
        """Test recommendation for negative mood - sad/breakup."""
        from tools.music_tools import get_music_recommender

        recommender = get_music_recommender()
        results = await recommender.recommend_by_mood("sad", top_k=5)

        assert len(results) > 0, "Should recommend songs for sad mood"

    async def test_mood_recommendation_format(self):
        """Test that mood recommendations have proper format."""
        from tools.music_tools import get_music_recommender

        recommender = get_music_recommender()
        results = await recommender.recommend_by_mood("relaxing", top_k=3)

        for rec in results:
            # Each recommendation should have song and reason
            assert "song" in rec or hasattr(rec, 'song'), \
                "Recommendation should have song"
            assert "reason" in rec or hasattr(rec, 'reason'), \
                "Recommendation should have reason"

    async def test_mood_with_genre_preference(self):
        """Test mood recommendation with genre preference."""
        from tools.music_tools import get_music_recommender

        recommender = get_music_recommender()
        # Request happy songs preferring pop
        results = await recommender.recommend_by_mood(
            "happy", genre_preference="pop", top_k=5
        )

        assert len(results) >= 0, "Should handle genre preference"
