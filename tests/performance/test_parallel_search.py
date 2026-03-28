"""
并行搜索性能测试

测试目标:
1. 验证并行搜索功能正确性
2. 测试早返回机制（RAG 快速返回）
3. 测试错误处理（单个源失败）
4. 测试降级机制（切换到串行）
5. 性能对比（并行 vs 串行）
"""

import asyncio
import pytest
import time
from unittest.mock import AsyncMock, MagicMock, patch
from tools.music_tools import MusicSearchTool, Song


@pytest.fixture
def music_search_tool():
    """创建音乐搜索工具实例"""
    # Mock MCP adapter
    mock_mcp = AsyncMock()
    return MusicSearchTool(mcp_adapter=mock_mcp)


@pytest.mark.asyncio
async def test_parallel_search_all_sources_success(music_search_tool):
    """
    测试并行搜索 - 所有数据源都返回结果
    预期：按优先级返回 RAG 结果
    """
    # Mock RAG search
    with patch('tools.rag_music_search_v2.get_rag_music_search_v2') as mock_rag:
        mock_rag_instance = MagicMock()
        mock_rag_instance.vector_store.count.return_value = 1000
        mock_rag_instance.search = AsyncMock(return_value=[
            {
                "title": "Shape of You",
                "artist": "Ed Sheeran",
                "album": "÷",
                "genre": "Pop",
                "similarity_score": 0.85
            }
        ])
        mock_rag.return_value = mock_rag_instance

        # Mock Spotify
        music_search_tool.mcp_adapter.search_tracks = AsyncMock(return_value=[
            Song(title="Shape of You", artist="Ed Sheeran", popularity=95)
        ])

        # Mock TailyAPI
        with patch.object(music_search_tool, '_search_songs_with_tailyapi') as mock_taily:
            mock_taily.return_value = [
                Song(title="Shape of You", artist="Ed Sheeran", popularity=90)
            ]

            result = await music_search_tool.search_songs_with_steps(
                query="Shape of You",
                limit=5,
                parallel=True
            )

            # 验证返回结果
            assert result["source"] == "rag_chroma"
            assert len(result["songs"]) > 0
            assert result["songs"][0].title == "Shape of You"

            # 验证步骤记录
            assert any("并行搜索-RAG" in step.get("step_name", "") for step in result["steps"])

            print(f"✅ 并行搜索成功: {result['source']}, 耗时={result['total_elapsed_ms']:.0f}ms")


@pytest.mark.asyncio
async def test_parallel_search_rag_fallback_to_spotify(music_search_tool):
    """
    测试并行搜索 - RAG 相似度不足，回退到 Spotify
    预期：返回 Spotify 结果
    """
    # Mock RAG search with low similarity
    with patch('tools.rag_music_search_v2.get_rag_music_search_v2') as mock_rag:
        mock_rag_instance = MagicMock()
        mock_rag_instance.vector_store.count.return_value = 1000
        mock_rag_instance.search = AsyncMock(return_value=[
            {
                "title": "Test Song",
                "artist": "Test Artist",
                "similarity_score": 0.3  # 低于阈值 0.55
            }
        ])
        mock_rag.return_value = mock_rag_instance

        # Mock Spotify
        music_search_tool.mcp_adapter.search_tracks = AsyncMock(return_value=[
            Song(title="Blinding Lights", artist="The Weeknd", popularity=98)
        ])

        # Mock TailyAPI
        with patch.object(music_search_tool, '_search_songs_with_tailyapi') as mock_taily:
            mock_taily.return_value = []

            result = await music_search_tool.search_songs_with_steps(
                query="Blinding Lights",
                limit=5,
                parallel=True
            )

            # 验证返回结果
            assert result["source"] == "spotify"
            assert len(result["songs"]) > 0
            assert result["songs"][0].title == "Blinding Lights"

            # 验证步骤记录
            assert any("并行搜索-Spotify" in step.get("step_name", "") for step in result["steps"])

            print(f"✅ 回退到 Spotify 成功: {result['source']}, 耗时={result['total_elapsed_ms']:.0f}ms")


@pytest.mark.asyncio
async def test_parallel_search_all_fail_fallback_to_local(music_search_tool):
    """
    测试并行搜索 - 所有外部源失败，回退到本地数据库
    预期：返回本地数据库结果
    """
    # Mock RAG search error
    with patch('tools.rag_music_search_v2.get_rag_music_search_v2') as mock_rag:
        mock_rag_instance = MagicMock()
        mock_rag_instance.vector_store.count.return_value = 1000
        mock_rag_instance.search = AsyncMock(side_effect=Exception("RAG error"))
        mock_rag.return_value = mock_rag_instance

        # Mock Spotify error
        music_search_tool.mcp_adapter.search_tracks = AsyncMock(
            side_effect=Exception("Spotify error")
        )

        # Mock TailyAPI error
        with patch.object(music_search_tool, '_search_songs_with_tailyapi') as mock_taily:
            mock_taily.side_effect = Exception("TailyAPI error")

            # 添加本地数据
            music_search_tool.music_db = [
                Song(title="Local Song", artist="Local Artist", popularity=80)
            ]

            result = await music_search_tool.search_songs_with_steps(
                query="Local",
                limit=5,
                parallel=True
            )

            # 验证返回结果
            assert result["source"] == "local_db"
            assert len(result["songs"]) > 0
            assert result["songs"][0].title == "Local Song"

            print(f"✅ 回退到本地数据库成功: {result['source']}, 耗时={result['total_elapsed_ms']:.0f}ms")


@pytest.mark.asyncio
async def test_parallel_vs_serial_performance(music_search_tool):
    """
    性能对比测试 - 并行 vs 串行搜索（RAG 相似度低的情况）
    预期：并行搜索明显快于串行搜索
    """
    query = "Test Song"
    limit = 5

    # Mock RAG search with low similarity (100ms delay)
    async def mock_rag_search(*args, **kwargs):
        await asyncio.sleep(0.1)
        return [{
            "title": "Test Song",
            "artist": "Test Artist",
            "similarity_score": 0.3  # 低于阈值 0.55
        }]

    # Mock Spotify (300ms delay)
    async def mock_spotify_search(*args, **kwargs):
        await asyncio.sleep(0.3)
        return [Song(title="Test Song", artist="Test Artist", popularity=90)]

    # Mock TailyAPI (500ms delay)
    async def mock_taily_search(*args, **kwargs):
        await asyncio.sleep(0.5)
        return [Song(title="Test Song", artist="Test Artist", popularity=85)]

    # 测试并行搜索
    with patch('tools.rag_music_search_v2.get_rag_music_search_v2') as mock_rag:
        mock_rag_instance = MagicMock()
        mock_rag_instance.vector_store.count.return_value = 1000
        mock_rag_instance.search = mock_rag_search
        mock_rag.return_value = mock_rag_instance

        music_search_tool.mcp_adapter.search_tracks = mock_spotify_search

        with patch.object(music_search_tool, '_search_songs_with_tailyapi', mock_taily_search):
            parallel_start = time.time()
            parallel_result = await music_search_tool.search_songs_with_steps(
                query=query,
                limit=limit,
                parallel=True
            )
            parallel_elapsed = time.time() - parallel_start

    # 测试串行搜索
    with patch('tools.rag_music_search_v2.get_rag_music_search_v2') as mock_rag:
        mock_rag_instance = MagicMock()
        mock_rag_instance.vector_store.count.return_value = 1000
        mock_rag_instance.search = mock_rag_search
        mock_rag.return_value = mock_rag_instance

        music_search_tool.mcp_adapter.search_tracks = mock_spotify_search

        with patch.object(music_search_tool, '_search_songs_with_tailyapi', mock_taily_search):
            serial_start = time.time()
            serial_result = await music_search_tool.search_songs_with_steps(
                query=query,
                limit=limit,
                parallel=False
            )
            serial_elapsed = time.time() - serial_start

    # 验证结果
    print(f"\n📊 性能对比:")
    print(f"  并行搜索: {parallel_elapsed*1000:.0f}ms")
    print(f"  串行搜索: {serial_elapsed*1000:.0f}ms")
    print(f"  性能提升: {(serial_elapsed/parallel_elapsed):.1f}x")

    # 并行应该明显快于串行（至少 1.5x）
    # 串行: RAG(100ms) + Spotify(300ms) = 400ms
    # 并行: max(RAG, Spotify, TailyAPI) = 500ms（但实际上会在 Spotify 完成后返回）
    assert parallel_elapsed < serial_elapsed
    # 并行搜索应该在 600ms 内完成（Spotify 300ms + 一些开销）
    assert parallel_elapsed < 0.6


@pytest.mark.asyncio
async def test_parallel_search_with_lyrics_mode(music_search_tool):
    """
    测试并行搜索 - 歌词搜索模式
    预期：歌词搜索优先，失败后进入并行搜索
    """
    # Mock lyrics search
    with patch('tools.lyrics_search.get_lyrics_search_engine') as mock_lyrics:
        mock_lyrics_instance = MagicMock()
        mock_lyrics_instance.is_lyrics_query.return_value = True
        mock_lyrics_instance.search_with_llm_fallback = AsyncMock(return_value=[])
        mock_lyrics_instance.extract_lyrics_content.return_value = "test lyrics"
        mock_lyrics.return_value = mock_lyrics_instance

        # Mock RAG search
        with patch('tools.rag_music_search_v2.get_rag_music_search_v2') as mock_rag:
            mock_rag_instance = MagicMock()
            mock_rag_instance.vector_store.count.return_value = 1000
            mock_rag_instance.search = AsyncMock(return_value=[
                {
                    "title": "Song from Lyrics",
                    "artist": "Artist",
                    "similarity_score": 0.85
                }
            ])
            mock_rag.return_value = mock_rag_instance

            result = await music_search_tool.search_songs_with_steps(
                query="这是歌词内容",
                limit=5,
                is_lyrics=True,
                parallel=True
            )

            # 验证歌词搜索先执行
            assert any("歌词搜索" in step.get("step_name", "") for step in result["steps"])

            # 验证最终返回 RAG 结果
            assert result["source"] == "rag_chroma"

            print(f"✅ 歌词搜索 + 并行搜索成功: {result['source']}, 耗时={result['total_elapsed_ms']:.0f}ms")


@pytest.mark.asyncio
async def test_parallel_search_error_isolation(music_search_tool):
    """
    测试并行搜索 - 错误隔离
    预期：单个源失败不影响其他源
    """
    # Mock RAG error
    with patch('tools.rag_music_search_v2.get_rag_music_search_v2') as mock_rag:
        mock_rag_instance = MagicMock()
        mock_rag_instance.vector_store.count.return_value = 1000
        mock_rag_instance.search = AsyncMock(side_effect=Exception("RAG failed"))
        mock_rag.return_value = mock_rag_instance

        # Mock Spotify success
        music_search_tool.mcp_adapter.search_tracks = AsyncMock(return_value=[
            Song(title="Spotify Song", artist="Spotify Artist", popularity=95)
        ])

        # Mock TailyAPI error
        with patch.object(music_search_tool, '_search_songs_with_tailyapi') as mock_taily:
            mock_taily.side_effect = Exception("TailyAPI failed")

            result = await music_search_tool.search_songs_with_steps(
                query="Test Song",
                limit=5,
                parallel=True
            )

            # 验证返回 Spotify 结果（RAG 和 TailyAPI 都失败）
            assert result["source"] == "spotify"
            assert len(result["songs"]) > 0

            print(f"✅ 错误隔离成功: {result['source']}, 耗时={result['total_elapsed_ms']:.0f}ms")


@pytest.mark.asyncio
async def test_parallel_search_disabled(music_search_tool):
    """
    测试并行搜索 - 禁用并行模式（parallel=False）
    预期：使用串行搜索逻辑
    """
    # Mock RAG search
    with patch('tools.rag_music_search_v2.get_rag_music_search_v2') as mock_rag:
        mock_rag_instance = MagicMock()
        mock_rag_instance.vector_store.count.return_value = 1000
        mock_rag_instance.search = AsyncMock(return_value=[
            {
                "title": "Serial Song",
                "artist": "Serial Artist",
                "similarity_score": 0.85
            }
        ])
        mock_rag.return_value = mock_rag_instance

        result = await music_search_tool.search_songs_with_steps(
            query="Serial Song",
            limit=5,
            parallel=False  # 禁用并行
        )

        # 验证返回结果
        assert result["source"] == "rag_chroma"

        # 验证步骤记录（串行模式应该记录 "RAG搜索" 而不是 "并行搜索-RAG"）
        assert any("RAG搜索" in step.get("step_name", "") for step in result["steps"])

        print(f"✅ 串行搜索成功: {result['source']}, 耗时={result['total_elapsed_ms']:.0f}ms")


if __name__ == "__main__":
    # 运行所有测试
    pytest.main([__file__, "-v", "-s"])
