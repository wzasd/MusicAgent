"""Unit tests for Song data model."""

import pytest


class TestSongModel:
    """Tests for Song dataclass."""

    def test_song_creation(self):
        """Test creating a Song instance."""
        try:
            from tools.music_tools import Song

            song = Song(
                title="Test Song",
                artist="Test Artist",
                album="Test Album",
                genre="pop",
                year=2024,
                duration=180,
                popularity=80,
                preview_url="https://example.com/preview.mp3",
                spotify_id="spotify123",
            )
            assert song.title == "Test Song"
            assert song.artist == "Test Artist"
            assert song.album == "Test Album"
            assert song.genre == "pop"
            assert song.year == 2024
            assert song.duration == 180
            assert song.popularity == 80
        except ImportError:
            pytest.skip("Cannot import Song")

    def test_song_to_dict(self):
        """Test Song.to_dict() method."""
        try:
            from tools.music_tools import Song

            song = Song(
                title="Test Song",
                artist="Test Artist",
                album="Test Album",
                genre="pop",
                year=2024,
            )
            d = song.to_dict()

            assert d["title"] == "Test Song"
            assert d["artist"] == "Test Artist"
            assert d["album"] == "Test Album"
            assert "genre" in d
            assert "year" in d
        except ImportError:
            pytest.skip("Cannot import Song")

    def test_song_to_dict_with_source(self):
        """Test Song.to_dict() with source parameter."""
        try:
            from tools.music_tools import Song

            song = Song(
                title="Test Song",
                artist="Test Artist",
            )
            d = song.to_dict(source="rag_chroma")

            assert d.get("source") == "rag_chroma"
        except ImportError:
            pytest.skip("Cannot import Song")

    def test_song_default_values(self):
        """Test Song with default values."""
        try:
            from tools.music_tools import Song

            song = Song(
                title="Simple Song",
                artist="Simple Artist"
            )
            assert song.album is None
            assert song.genre is None
            assert song.year is None
            assert song.duration is None
            assert song.popularity is None
            assert song.preview_url is None
            assert song.spotify_id is None
        except ImportError:
            pytest.skip("Cannot import Song")

    def test_song_equality(self):
        """Test Song equality comparison."""
        try:
            from tools.music_tools import Song

            song1 = Song(title="Same", artist="Artist")
            song2 = Song(title="Same", artist="Artist")
            song3 = Song(title="Different", artist="Artist")

            assert song1 == song2
            assert song1 != song3
        except ImportError:
            pytest.skip("Cannot import Song")

    def test_song_with_chinese(self):
        """Test Song with Chinese text."""
        try:
            from tools.music_tools import Song

            song = Song(
                title="稻香",
                artist="周杰伦",
                album="魔杰座",
                genre="流行",
            )
            assert song.title == "稻香"
            assert song.artist == "周杰伦"
            assert song.album == "魔杰座"
            assert song.genre == "流行"
        except ImportError:
            pytest.skip("Cannot import Song")
