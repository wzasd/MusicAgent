"""
事件歌单搜索单元测试
"""

import pytest
from dataclasses import asdict

from tools.event_setlist_search import (
    EventSetlistSong,
    EventSetlist,
    EventSetlistSearchEngine,
)


class TestEventSetlistSong:
    """测试 EventSetlistSong 数据类"""

    def test_basic_creation(self):
        song = EventSetlistSong(
            order=1,
            title="Bad Romance",
            artist="Lady Gaga"
        )
        assert song.order == 1
        assert song.title == "Bad Romance"
        assert song.artist == "Lady Gaga"
        assert song.is_cover is False
        assert song.note is None

    def test_cover_song(self):
        song = EventSetlistSong(
            order=5,
            title="Imagine",
            artist="Lady Gaga",
            is_cover=True,
            original_artist="John Lennon",
            note="Piano version"
        )
        assert song.is_cover is True
        assert song.original_artist == "John Lennon"
        assert song.note == "Piano version"

    def test_to_dict(self):
        song = EventSetlistSong(
            order=1,
            title="Test Song",
            artist="Test Artist",
            note="Encore"
        )
        d = song.to_dict()
        assert d["order"] == 1
        assert d["title"] == "Test Song"
        assert d["note"] == "Encore"


class TestEventSetlist:
    """测试 EventSetlist 数据类"""

    def test_basic_creation(self):
        songs = [
            EventSetlistSong(order=1, title="Song 1"),
            EventSetlistSong(order=2, title="Song 2"),
        ]
        setlist = EventSetlist(
            event_name="Test Concert",
            event_type="concert",
            artist="Test Artist",
            songs=songs,
            total_songs=2,
            encore_count=1
        )
        assert setlist.event_name == "Test Concert"
        assert len(setlist.songs) == 2
        assert setlist.total_songs == 2

    def test_to_dict(self):
        songs = [EventSetlistSong(order=1, title="Song 1")]
        setlist = EventSetlist(
            event_name="Test",
            event_type="concert",
            artist="Artist",
            songs=songs,
            confidence=0.85
        )
        d = setlist.to_dict()
        assert d["event_name"] == "Test"
        assert d["confidence"] == 0.85
        assert len(d["songs"]) == 1

    def test_empty_songs_default(self):
        setlist = EventSetlist(
            event_name="Test",
            event_type="concert",
            artist="Artist"
        )
        assert setlist.songs == []


class TestEventSetlistSearchEngine:
    """测试 EventSetlistSearchEngine"""

    @pytest.fixture
    def mock_web_search(self):
        """创建一个 mock web search provider"""
        class MockWebSearch:
            async def search(self, query, max_results=5):
                return []
        return MockWebSearch()

    def test_build_search_query_basic(self, mock_web_search):
        engine = EventSetlistSearchEngine(web_search_provider=mock_web_search)
        query = engine._build_search_query(
            artist="Lady Gaga",
            event_type="concert"
        )
        assert "Lady Gaga" in query
        assert "concert" in query
        assert "setlist" in query

    def test_build_search_query_with_year(self, mock_web_search):
        engine = EventSetlistSearchEngine(web_search_provider=mock_web_search)
        query = engine._build_search_query(
            artist="Lady Gaga",
            event_type="concert",
            year="2025"
        )
        assert "2025" in query

    def test_build_search_query_with_location(self, mock_web_search):
        engine = EventSetlistSearchEngine(web_search_provider=mock_web_search)
        query = engine._build_search_query(
            artist="Lady Gaga",
            event_type="concert",
            location="巴黎"
        )
        assert "Paris" in query  # 应该转换为英文

    def test_build_search_query_festival(self, mock_web_search):
        engine = EventSetlistSearchEngine(web_search_provider=mock_web_search)
        query = engine._build_search_query(
            artist="Various",
            event_type="festival",
            event_name="Coachella",
            year="2024"
        )
        assert "Coachella" in query
        assert "festival" in query
        assert "lineup" in query

    @pytest.mark.asyncio
    async def test_search_with_mock(self, monkeypatch):
        """使用mock测试搜索流程"""
        # 创建 mock web search provider
        class MockWebSearch:
            async def search(self, query, max_results=5):
                return [{
                    "title": "Lady Gaga Concert Setlist",
                    "content": "1. Bad Romance 2. Poker Face 3. Shallow",
                    "url": "https://example.com"
                }]

        engine = EventSetlistSearchEngine(web_search_provider=MockWebSearch())

        # Mock web search
        async def mock_search(query, max_results=5):
            return [{
                "title": "Lady Gaga Concert Setlist",
                "content": "1. Bad Romance 2. Poker Face 3. Shallow",
                "url": "https://example.com"
            }]

        # Mock LLM extraction
        def mock_invoke_text(system, prompt, **kwargs):
            return '''
            {
                "event_name": "The Chromatica Ball",
                "artist": "Lady Gaga",
                "date": "2022-07-17",
                "location": "London",
                "total_songs": 3,
                "encore_count": 0,
                "songs": [
                    {"order": 1, "title": "Bad Romance", "is_cover": false, "note": ""},
                    {"order": 2, "title": "Poker Face", "is_cover": false, "note": ""},
                    {"order": 3, "title": "Shallow", "is_cover": false, "note": ""}
                ],
                "confidence": 0.9
            }
            '''

        monkeypatch.setattr(engine.web_search, "search", mock_search)
        monkeypatch.setattr(engine.llm, "invoke_text", mock_invoke_text)

        result = await engine.search(
            artist="Lady Gaga",
            event_type="concert"
        )

        assert result is not None
        assert result.event_name == "The Chromatica Ball"
        assert len(result.songs) == 3
        assert result.songs[0].title == "Bad Romance"
