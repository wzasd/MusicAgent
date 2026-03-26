"""pytest fixtures and shared utilities."""

import json
import os
import sys
from pathlib import Path

import pytest

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


def pytest_configure(config):
    """Register custom markers."""
    config.addinivalue_line("markers", "webhook: marks tests as webhook tests")
    config.addinivalue_line("markers", "regression: marks tests as regression tests")
    config.addinivalue_line("markers", "e2e: marks tests as end-to-end tests")
    config.addinivalue_line("markers", "integration: marks tests as integration tests")
    config.addinivalue_line("markers", "unit: marks tests as unit tests")


# ==================== Fixtures for Unit Tests ====================

@pytest.fixture
def sample_song_data():
    """Sample song data for testing."""
    return {
        "title": "Test Song",
        "artist": "Test Artist",
        "album": "Test Album",
        "genre": ["pop"],
        "year": 2024,
        "duration_ms": 180000,
        "popularity": 80,
        "preview_url": "https://example.com/preview.mp3",
        "spotify_id": "spotify123",
    }


# ==================== Fixtures for Integration Tests ====================

@pytest.fixture(scope="session")
def music_search_tool():
    """Get MusicSearchTool instance."""
    from tools.music_tools import get_music_search_tool

    return get_music_search_tool()


@pytest.fixture(scope="session")
def lyrics_engine():
    """Get LyricsSearchEngine instance."""
    from tools.lyrics_search import get_lyrics_search_engine

    return get_lyrics_search_engine()


@pytest.fixture(scope="session")
def music_graph_llm():
    """Get LLM instance from music_graph."""
    from graphs.music_graph import get_llm

    return get_llm()


@pytest.fixture
def analyze_intent_func():
    """Get a wrapper for analyze_intent that works with plain queries."""
    import json
    from graphs.music_graph import MusicRecommendationGraph, _clean_json_from_llm, get_llm, MUSIC_INTENT_ANALYZER_PROMPT

    async def _analyze(query: str) -> dict:
        """Simple wrapper to analyze intent from a query string."""
        graph = MusicRecommendationGraph()
        # Call the method with proper state structure
        state = {"input": query, "step_count": 0}
        result = await graph.analyze_intent(state)
        return {
            "intent_type": result.get("intent_type"),
            "intent_parameters": result.get("intent_parameters", {}),
            "intent_context": result.get("intent_context", ""),
        }

    return _analyze


# ==================== Fixtures for E2E Tests ====================

@pytest.fixture(scope="session")
def api_base_url():
    """Base URL for API endpoints."""
    return os.getenv("API_BASE_URL", "http://localhost:8501")


@pytest.fixture
def http_client(api_base_url):
    """HTTP client for E2E tests."""
    import httpx

    return httpx.Client(base_url=api_base_url, timeout=30.0)


# ==================== Regression Test Fixtures ====================

@pytest.fixture(scope="session")
def intent_regression_cases():
    """Load intent classification regression cases."""
    cases_file = Path(__file__).parent / "regression" / "intent_regression_cases.json"
    if cases_file.exists():
        with open(cases_file, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data.get("cases", [])
    return []


@pytest.fixture
def regression_report_path():
    """Path for saving regression test reports."""
    return PROJECT_ROOT / ".cache" / "regression_reports"
