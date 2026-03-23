"""Integration tests for artist-based search functionality."""

import pytest


@pytest.mark.integration
class TestSearchByArtist:
    """Tests for artist-based song search (mixed mode: Local + ChromaDB + Web)."""

    async def test_chinese_artist_search(self, music_search_tool):
        """Test searching Chinese artist - 周杰伦."""
        songs, source = await music_search_tool.get_songs_by_artist("周杰伦", limit=5)

        assert len(songs) > 0, "Should find songs by 周杰伦"
        assert len(songs) >= 3, f"Expected at least 3 songs, got {len(songs)}"

        # All results should have artist containing 周杰伦 or Jay Chou
        for song in songs:
            artist_lower = song.artist.lower()
            assert "周杰伦" in song.artist or "jay" in artist_lower, \
                f"Expected artist to be 周杰伦/Jay Chou, got {song.artist}"

        # Source should be valid
        assert source in ["local_db", "chroma_db", "artist_web_search", "mixed"]

    async def test_english_artist_search(self, music_search_tool):
        """Test searching English artist - Lady Gaga."""
        songs, source = await music_search_tool.get_songs_by_artist("Lady Gaga", limit=5)

        assert len(songs) > 0, "Should find songs by Lady Gaga"

        # All results should have artist containing Lady Gaga
        for song in songs:
            assert "lady gaga" in song.artist.lower(), \
                f"Expected artist to be Lady Gaga, got {song.artist}"

    async def test_partial_artist_name(self, music_search_tool):
        """Test partial artist name matching - 'selena' should match Selena Gomez."""
        songs, source = await music_search_tool.get_songs_by_artist("selena", limit=5)

        # Should find songs with artist containing "Selena"
        found_selena = any("selena" in song.artist.lower() for song in songs)
        assert found_selena or len(songs) == 0, \
            "If results exist, should contain artist with 'Selena'"

    async def test_artist_result_format(self, music_search_tool):
        """Test that artist search returns properly formatted results."""
        songs, source = await music_search_tool.get_songs_by_artist("周杰伦", limit=3)

        assert len(songs) > 0

        for song in songs:
            # Required fields
            assert song.title, "Song must have title"
            assert song.artist, "Song must have artist"
            assert isinstance(song.to_dict(), dict), "to_dict() should return dict"

    async def test_artist_with_spaces(self, music_search_tool):
        """Test artist name without spaces - 'selenagomez' should work."""
        songs, source = await music_search_tool.get_songs_by_artist("selenagomez", limit=5)

        # This tests the 3-level matching in ChromaVectorStore.get_by_artist()
        # Results may vary, but should not crash
        assert isinstance(songs, list)
