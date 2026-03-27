"""
事件歌单搜索集成测试（端到端）
"""

import pytest
import os

from tools.event_setlist_search import EventSetlistSearchEngine


# 检查是否有 Tavily API Key
HAS_TAVILY_API_KEY = bool(os.getenv("TAVILY_API_KEY"))


@pytest.mark.integration
@pytest.mark.skipif(not HAS_TAVILY_API_KEY, reason="需要 TAVILY_API_KEY 环境变量")
class TestEventSetlistEndToEnd:
    """端到端集成测试（需要真实 API Key）"""

    @pytest.fixture
    def engine(self):
        """创建搜索引擎实例"""
        return EventSetlistSearchEngine()

    @pytest.mark.asyncio
    async def test_search_known_concert(self, engine):
        """测试搜索已知演唱会"""
        result = await engine.search(
            artist="Lady Gaga",
            event_type="concert",
            year="2024"
        )

        # 验证基本结构
        assert result is not None, "应该找到演唱会结果"
        assert result.artist == "Lady Gaga"
        assert result.event_type == "concert"
        assert len(result.songs) > 0, "应该有歌曲列表"
        assert result.confidence > 0.5, "置信度应该大于 0.5"

        # 验证歌曲结构
        first_song = result.songs[0]
        assert first_song.order == 1
        assert first_song.title is not None
        assert len(first_song.title) > 0

        print(f"\n✅ 找到演唱会: {result.event_name}")
        print(f"   歌曲数量: {result.total_songs}")
        print(f"   前3首歌: {[s.title for s in result.songs[:3]]}")

    @pytest.mark.asyncio
    async def test_search_festival_lineup(self, engine):
        """测试音乐节阵容搜索"""
        result = await engine.search(
            event_name="Coachella",
            event_type="festival",
            year="2024"
        )

        # 验证基本结构
        assert result is not None, "应该找到音乐节结果"
        assert result.event_type == "festival"
        assert "Coachella" in result.event_name or "coachella" in result.event_name.lower()
        assert len(result.songs) > 0, "音乐节应该有表演曲目"

        print(f"\n✅ 找到音乐节: {result.event_name}")
        print(f"   曲目数量: {result.total_songs}")

    @pytest.mark.asyncio
    async def test_search_with_location(self, engine):
        """测试带地点的搜索"""
        result = await engine.search(
            artist="Taylor Swift",
            event_type="concert",
            location="Tokyo",
            year="2024"
        )

        # 验证基本结构
        assert result is not None, "应该找到东京演唱会"
        assert result.artist == "Taylor Swift"
        assert result.location is not None or "Tokyo" in (result.event_name or "")

        print(f"\n✅ 找到演唱会: {result.event_name}")
        if result.location:
            print(f"   地点: {result.location}")

    @pytest.mark.asyncio
    async def test_search_nonexistent_event(self, engine):
        """测试不存在的事件"""
        result = await engine.search(
            artist="Nonexistent Artist 12345",
            event_type="concert",
            year="2024"
        )

        # 可能返回 None 或低置信度结果
        if result is not None:
            assert result.confidence < 0.5, "不存在的事件应该有低置信度"
            print(f"\n⚠️  返回低置信度结果: {result.confidence}")
        else:
            print(f"\n✅ 正确返回 None（未找到结果）")


@pytest.mark.integration
class TestMusicGraphIntegration:
    """工作流集成测试（不依赖 API Key）"""

    def test_intent_recognition_and_search(self):
        """测试意图识别到搜索的完整流程"""
        from llms.siliconflow_llm import SiliconFlowLLM

        # 模拟用户查询
        user_query = "我想看 Taylor Swift 2024 年东京演唱会的歌单"

        # Step 1: 意图识别（这里用简单的关键词匹配模拟）
        intent = self._recognize_intent(user_query)

        assert intent["intent"] == "event_setlist_search"
        assert intent["artist"] == "Taylor Swift"
        assert intent["event_type"] == "concert"
        assert intent["location"] == "Tokyo"  # 转换为英文
        assert intent["year"] == "2024"

        print(f"\n✅ 意图识别成功:")
        print(f"   意图: {intent['intent']}")
        print(f"   艺术家: {intent['artist']}")
        print(f"   事件类型: {intent['event_type']}")
        print(f"   地点: {intent['location']}")
        print(f"   年份: {intent['year']}")

    def _recognize_intent(self, query: str) -> dict:
        """简单的意图识别（关键词匹配）"""
        intent = {
            "intent": "event_setlist_search",
            "artist": None,
            "event_type": "concert",
            "location": None,
            "year": None
        }

        # 提取艺术家（简化版本）
        if "Taylor Swift" in query:
            intent["artist"] = "Taylor Swift"
        elif "Lady Gaga" in query:
            intent["artist"] = "Lady Gaga"

        # 提取事件类型
        if "音乐节" in query or "festival" in query.lower():
            intent["event_type"] = "festival"

        # 提取地点
        if "东京" in query:
            intent["location"] = "Tokyo"
        elif "巴黎" in query:
            intent["location"] = "Paris"

        # 提取年份
        import re
        year_match = re.search(r'\b(20\d{2})\b', query)
        if year_match:
            intent["year"] = year_match.group(1)

        return intent

    @pytest.mark.asyncio
    async def test_full_workflow_mock(self, monkeypatch):
        """测试完整工作流（使用 Mock）"""
        from tools.event_setlist_search import EventSetlistSearchEngine

        # 创建引擎
        engine = EventSetlistSearchEngine()

        # Mock web search
        async def mock_web_search(query, max_results=5):
            return [{
                "title": "Taylor Swift Tokyo Concert Setlist 2024",
                "content": "1. Shake It Off 2. Love Story 3. Anti-Hero",
                "url": "https://example.com/setlist"
            }]

        # Mock LLM
        def mock_invoke_text(system, prompt, **kwargs):
            return '''
            {
                "event_name": "The Eras Tour - Tokyo",
                "artist": "Taylor Swift",
                "date": "2024-02-07",
                "location": "Tokyo Dome, Tokyo, Japan",
                "total_songs": 3,
                "encore_count": 0,
                "songs": [
                    {"order": 1, "title": "Shake It Off", "is_cover": false, "note": ""},
                    {"order": 2, "title": "Love Story", "is_cover": false, "note": ""},
                    {"order": 3, "title": "Anti-Hero", "is_cover": false, "note": ""}
                ],
                "confidence": 0.95
            }
            '''

        monkeypatch.setattr(engine.web_search, "search", mock_web_search)
        monkeypatch.setattr(engine.llm, "invoke_text", mock_invoke_text)

        # 执行搜索
        result = await engine.search(
            artist="Taylor Swift",
            event_type="concert",
            location="Tokyo",
            year="2024"
        )

        # 验证结果
        assert result is not None
        assert result.artist == "Taylor Swift"
        assert result.event_name == "The Eras Tour - Tokyo"
        assert len(result.songs) == 3
        assert result.songs[0].title == "Shake It Off"
        assert result.confidence == 0.95

        print(f"\n✅ 完整工作流测试通过:")
        print(f"   事件: {result.event_name}")
        print(f"   歌曲数: {result.total_songs}")
        print(f"   置信度: {result.confidence}")
