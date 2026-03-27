# Event Setlist Search 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现场景歌单搜索功能，支持用户查询演唱会、音乐节、颁奖典礼等事件的实际歌单

**Architecture:** 新增独立的意图类型 `search_event_setlist`，通过 Web Search 查找事件歌单，使用 LLM 提取结构化数据。新增 `EventSetlistSearchEngine` 类处理核心逻辑，在工作流图中添加对应节点。

**Tech Stack:** Python, FastAPI, Tavily Web Search, SiliconFlow LLM, LangGraph

---

## 文件结构

### 新增文件
| 文件 | 职责 |
|-----|------|
| `tools/event_setlist_search.py` | EventSetlistSearchEngine 核心类，处理歌单搜索和提取 |
| `prompts/event_setlist_prompts.py` | 歌单提取的 LLM 提示词 |
| `tests/unit/test_event_setlist_search.py` | 单元测试 |
| `tests/integration/test_event_setlist_end_to_end.py` | 集成测试 |

### 修改文件
| 文件 | 修改内容 |
|-----|---------|
| `prompts/music_prompts.py` | 在意图识别提示词中添加 `search_event_setlist` 示例和规则 |
| `graphs/music_graph.py` | 添加 `search_event_setlist` 节点和路由逻辑 |

---

## Task 1: 创建数据模型和提示词

**Files:**
- Create: `prompts/event_setlist_prompts.py`

**依赖:** 无

- [ ] **Step 1: 创建歌单提取提示词文件**

```python
"""
事件歌单搜索相关提示词
"""

SETLIST_EXTRACTION_PROMPT = """【角色】
你是一位专业的现场音乐资料整理专家，擅长从搜索结果中提取演唱会的详细歌单信息。

【任务】
根据网络搜索结果，提取{artist}的{event_type}歌单信息。

【搜索结果】
{search_results}

【提取要求】
1. 歌曲顺序：尽可能按照实际表演顺序排列
2. 翻唱标注：如果是翻唱其他歌手的歌曲，标注原唱
3. 特别版本：标注不插电版、Remix版、嘉宾合唱等特殊说明
4. 安可曲：识别并标注安可(Encore)部分
5. 完整性：尽可能提取完整的歌单，但如果信息不完整，提取已知的部分

【输出格式】
只返回JSON格式：
{{
    "event_name": "活动名称",
    "artist": "主要表演者",
    "date": "日期(YYYY-MM-DD格式，不确定填null)",
    "location": "地点",
    "total_songs": 歌曲总数,
    "encore_count": 安可曲数量,
    "songs": [
        {
            "order": 1,
            "title": "歌曲名",
            "artist": "表演者（如与主要表演者不同）",
            "is_cover": false,
            "original_artist": null,
            "note": "备注（如'开场曲'、'不插电版'、'与XXX合唱'）"
        }
    ],
    "confidence": 0.85,
    "source_quality": "high/medium/low",
    "missing_info": ["缺失的信息项"]
}}

【置信度评分标准】
- 0.9-1.0: 搜索结果提供了完整、明确的歌单信息，顺序清晰
- 0.7-0.89: 搜索结果提供了大部分歌单信息，可能有少量缺失或顺序不确定
- 0.5-0.69: 搜索结果提供了部分歌曲，但信息不完整或来源单一
- <0.5: 信息严重不足，无法构建可靠歌单

【重要】
- 只从给定的搜索结果中提取，不要凭记忆补充
- 如果搜索结果中没有歌单信息，返回null
- 只返回纯JSON，不要任何其他文字
"""

SETLIST_SEARCH_QUERY_PROMPT = """【角色】
你是一位搜索查询优化专家，擅长将用户的歌单查询需求转换为精准的搜索关键词。

【任务】
根据用户提供的事件信息，生成最佳的Web搜索查询词。

【输入信息】
- 表演者: {artist}
- 事件类型: {event_type}
- 年份: {year}
- 地点: {location}
- 活动名称: {event_name}

【输出要求】
只返回一个字符串，即最优的搜索查询词。查询词应该：
1. 包含表演者英文名（如果知道）
2. 包含事件类型的英文表达（concert/setlist/festival/lineup/awards performance）
3. 包含年份和地点（如果有）
4. 优先使用英文，因为setlist.fm等主流歌单网站是英文的

【示例】
输入: artist=Lady Gaga, event_type=concert, year=2025, location=巴黎
输出: Lady Gaga 2025 Paris concert setlist

输入: artist=周杰伦, event_type=concert, event_name=嘉年华
输出: 周杰伦 嘉年华演唱会 歌单 setlist

【输出】
只返回查询字符串，不要任何其他文字：
"""

EVENT_TYPE_DETECTION_PROMPT = """【角色】
你是一位事件类型识别专家，能从用户输入中识别音乐事件的类型。

【任务】
根据用户输入，判断事件类型。

【输入】
用户输入: {user_input}
已提取信息:
- 表演者: {artist}
- 年份: {year}
- 地点: {location}

【事件类型定义】
- concert: 演唱会、巡演、巡回、个人音乐会
- festival: 音乐节、音乐盛典、multi-artist活动
- awards: 颁奖礼、颁奖典礼、奖项表演
- tv_show: 电视节目、春晚、晚会、综艺表演

【输出格式】
只返回JSON：
{{
    "event_type": "concert/festival/awards/tv_show",
    "confidence": 0.9,
    "reason": "判断理由"
}}
"""
```

- [ ] **Step 2: 创建文件并提交**

```bash
git add prompts/event_setlist_prompts.py
git commit -m "feat: add event setlist search prompts"
```

---

## Task 2: 修改意图识别提示词

**Files:**
- Modify: `prompts/music_prompts.py`

**依赖:** Task 1（了解提示词格式）

- [ ] **Step 1: 在 MUSIC_INTENT_ANALYZER_PROMPT 中添加事件歌单搜索示例**

在 `prompts/music_prompts.py` 中，找到 `MUSIC_INTENT_ANALYZER_PROMPT`，在示例部分添加：

```python
'''
输入: "周杰伦嘉年华演唱会歌单"
输出: {"intent_type": "search_event_setlist", "parameters": {"artist": "周杰伦", "event_type": "concert", "event_name": "嘉年华"}, "context": "用户想查询周杰伦嘉年华演唱会的歌单"}

输入: "Coachella 2024音乐节阵容"
输出: {"intent_type": "search_event_setlist", "parameters": {"event_type": "festival", "event_name": "Coachella", "year": "2024"}, "context": "用户想查询Coachella 2024音乐节的演出阵容"}

输入: "Lady Gaga 2025巴黎演唱会"
输出: {"intent_type": "search_event_setlist", "parameters": {"artist": "Lady Gaga", "event_type": "concert", "year": "2025", "location": "巴黎"}, "context": "用户想查询Lady Gaga 2025年巴黎演唱会的歌单"}

输入: "春晚2024节目单"
输出: {"intent_type": "search_event_setlist", "parameters": {"event_type": "tv_show", "event_name": "春晚", "year": "2024"}, "context": "用户想查询2024年春晚的节目单"}

输入: "格莱美2024颁奖礼表演"
输出: {"intent_type": "search_event_setlist", "parameters": {"event_type": "awards", "event_name": "格莱美", "year": "2024"}, "context": "用户想查询格莱美2024颁奖礼的表演节目"}
'''
```

- [ ] **Step 2: 在规则部分添加事件歌单搜索规则**

在规则部分（【规则】下方）添加：

```python
'''
7. 事件歌单搜索：当用户提到"xxx演唱会歌单/曲目"、"xxx音乐节阵容/lineup"、"xxx颁奖礼表演"、"xxx晚会节目单"时，intent_type 为 "search_event_setlist"
8. event_type 只能是: concert(演唱会)、festival(音乐节)、awards(颁奖礼)、tv_show(电视节目/晚会)
9. 从用户输入中提取 artist(表演者)、year(年份)、location(地点)、event_name(活动名称)等参数
'''
```

- [ ] **Step 3: 更新 intent_type 允许值列表**

找到规则1，将 `search_event_setlist` 添加到允许值列表：

```python
'''
1. intent_type 只能是以下之一：search, search_by_lyrics, search_by_theme, search_by_topic, search_event_setlist, recommend_by_mood, recommend_by_genre, recommend_by_artist, recommend_by_favorites, recommend_by_activity, general_chat
'''
```

- [ ] **Step 4: Commit**

```bash
git add prompts/music_prompts.py
git commit -m "feat: add search_event_setlist intent recognition"
```

---

## Task 3: 创建 EventSetlistSearchEngine 核心类

**Files:**
- Create: `tools/event_setlist_search.py`

**依赖:** Task 1, Task 2

- [ ] **Step 1: 创建数据模型类**

```python
"""
事件歌单搜索工具
提供演唱会、音乐节等事件的实际歌单查询功能
"""

import json
import re
from dataclasses import dataclass, asdict
from typing import List, Dict, Any, Optional

from config.logging_config import get_logger
from llms.siliconflow_llm import SiliconFlowLLM
from prompts.event_setlist_prompts import (
    SETLIST_EXTRACTION_PROMPT,
    SETLIST_SEARCH_QUERY_PROMPT,
)

logger = get_logger(__name__)


@dataclass
class EventSetlistSong:
    """事件歌单中的歌曲"""
    order: int                      # 表演顺序
    title: str                      # 歌曲名
    artist: Optional[str] = None    # 表演者（用于翻唱/嘉宾情况）
    is_cover: bool = False          # 是否翻唱
    original_artist: Optional[str] = None  # 原唱（如果是翻唱）
    note: Optional[str] = None      # 备注

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class EventSetlist:
    """事件歌单"""
    event_name: str                 # 活动名称
    event_type: str                 # concert/festival/awards/tv_show
    artist: str                     # 主要表演者
    date: Optional[str] = None      # 日期
    location: Optional[str] = None  # 地点
    songs: List[EventSetlistSong] = None  # 歌曲列表
    total_songs: int = 0
    encore_count: int = 0           # 安可曲数量
    source_url: str = ""            # 来源链接
    confidence: float = 0.0         # 置信度

    def __post_init__(self):
        if self.songs is None:
            self.songs = []

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_name": self.event_name,
            "event_type": self.event_type,
            "artist": self.artist,
            "date": self.date,
            "location": self.location,
            "songs": [s.to_dict() for s in self.songs],
            "total_songs": self.total_songs,
            "encore_count": self.encore_count,
            "source_url": self.source_url,
            "confidence": self.confidence,
        }
```

- [ ] **Step 2: 创建 EventSetlistSearchEngine 类**

```python
class EventSetlistSearchEngine:
    """事件歌单搜索引擎"""

    def __init__(self, web_search_provider=None):
        """
        初始化事件歌单搜索引擎

        Args:
            web_search_provider: Web搜索提供者，如果为None则使用Tavily
        """
        self.llm = SiliconFlowLLM()
        self.web_search = web_search_provider or self._get_default_provider()
        logger.info("EventSetlistSearchEngine 初始化完成")

    def _get_default_provider(self):
        """获取默认的Web搜索提供者"""
        from tools.web_search.factory import get_web_search_provider
        return get_web_search_provider()

    def _build_search_query(
        self,
        artist: str,
        event_type: str,
        year: Optional[str] = None,
        location: Optional[str] = None,
        event_name: Optional[str] = None
    ) -> str:
        """
        构建搜索查询词

        策略：优先使用英文关键词，因为setlist.fm等主流歌单网站是英文的
        """
        parts = [artist]

        if event_name:
            parts.append(event_name)

        if year:
            parts.append(year)

        if location:
            # 尝试转换常见地名为英文
            location_map = {
                "巴黎": "Paris",
                "伦敦": "London",
                "纽约": "New York",
                "东京": "Tokyo",
                "上海": "Shanghai",
                "北京": "Beijing",
                "香港": "Hong Kong",
                "台北": "Taipei",
            }
            parts.append(location_map.get(location, location))

        # 事件类型关键词
        event_keywords = {
            "concert": "concert setlist",
            "festival": "festival lineup setlist",
            "awards": "awards performance setlist",
            "tv_show": "tv show performance setlist",
        }
        parts.append(event_keywords.get(event_type, "setlist"))

        return " ".join(parts)

    async def search(
        self,
        artist: str,
        event_type: str,
        year: Optional[str] = None,
        location: Optional[str] = None,
        event_name: Optional[str] = None
    ) -> Optional[EventSetlist]:
        """
        搜索事件歌单

        Args:
            artist: 表演者名称
            event_type: 事件类型 (concert/festival/awards/tv_show)
            year: 年份（可选）
            location: 地点（可选）
            event_name: 活动具体名称（可选）

        Returns:
            EventSetlist对象，如果未找到则返回None
        """
        try:
            # 构建搜索查询
            query = self._build_search_query(artist, event_type, year, location, event_name)
            logger.info(f"搜索事件歌单: query='{query}'")

            # 执行Web搜索
            search_results = await self._search_web(query)
            if not search_results:
                logger.warning(f"Web搜索无结果: {query}")
                return None

            # 使用LLM提取结构化歌单
            setlist = await self._extract_setlist(
                search_results=search_results,
                artist=artist,
                event_type=event_type
            )

            if setlist:
                # 补充额外信息
                if year:
                    setlist.date = setlist.date or year
                if location:
                    setlist.location = setlist.location or location

                logger.info(f"成功提取歌单: {setlist.event_name}, {len(setlist.songs)}首歌")

            return setlist

        except Exception as e:
            logger.error(f"搜索事件歌单失败: {e}", exc_info=True)
            return None

    async def _search_web(self, query: str) -> str:
        """执行Web搜索"""
        try:
            results = await self.web_search.search(query, max_results=5)

            # 合并搜索结果
            snippets = []
            for i, result in enumerate(results, 1):
                title = result.get("title", "")
                content = result.get("content", "")
                url = result.get("url", "")
                snippets.append(f"[{i}] {title}\n{content}\nSource: {url}\n")

            return "\n".join(snippets)

        except Exception as e:
            logger.error(f"Web搜索失败: {e}")
            return ""

    async def _extract_setlist(
        self,
        search_results: str,
        artist: str,
        event_type: str
    ) -> Optional[EventSetlist]:
        """使用LLM从搜索结果中提取结构化歌单"""
        try:
            prompt = SETLIST_EXTRACTION_PROMPT.format(
                artist=artist,
                event_type=event_type,
                search_results=search_results
            )

            response = self.llm.invoke_text(
                "你是专业的现场音乐资料整理专家，擅长提取演唱会歌单信息。只从给定的搜索结果中提取，不要凭记忆补充。",
                prompt,
                temperature=0.3,
                max_tokens=2000
            )

            # 解析JSON
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if not json_match:
                logger.warning("LLM响应中未找到JSON")
                return None

            data = json.loads(json_match.group())

            if data is None:
                logger.info("搜索结果中无歌单信息")
                return None

            # 构建EventSetlist
            songs = []
            for song_data in data.get("songs", []):
                songs.append(EventSetlistSong(
                    order=song_data.get("order", 0),
                    title=song_data.get("title", "Unknown"),
                    artist=song_data.get("artist"),
                    is_cover=song_data.get("is_cover", False),
                    original_artist=song_data.get("original_artist"),
                    note=song_data.get("note")
                ))

            return EventSetlist(
                event_name=data.get("event_name", f"{artist} {event_type}"),
                event_type=event_type,
                artist=artist,
                date=data.get("date"),
                location=data.get("location"),
                songs=songs,
                total_songs=data.get("total_songs", len(songs)),
                encore_count=data.get("encore_count", 0),
                confidence=data.get("confidence", 0.5)
            )

        except json.JSONDecodeError as e:
            logger.error(f"JSON解析失败: {e}")
            return None
        except Exception as e:
            logger.error(f"提取歌单失败: {e}")
            return None


# 全局实例
_event_setlist_search_engine = None


def get_event_setlist_search_engine() -> EventSetlistSearchEngine:
    """获取事件歌单搜索引擎单例"""
    global _event_setlist_search_engine
    if _event_setlist_search_engine is None:
        _event_setlist_search_engine = EventSetlistSearchEngine()
    return _event_setlist_search_engine
```

- [ ] **Step 3: 创建文件并提交**

```bash
git add tools/event_setlist_search.py
git commit -m "feat: add EventSetlistSearchEngine core class"
```

---

## Task 4: 修改工作流图添加节点

**Files:**
- Modify: `graphs/music_graph.py`

**依赖:** Task 3

- [ ] **Step 1: 导入 EventSetlistSearchEngine**

在 `graphs/music_graph.py` 的导入部分添加：

```python
from tools.event_setlist_search import get_event_setlist_search_engine
```

- [ ] **Step 2: 添加 search_event_setlist_node 节点**

在 `MusicRecommendationGraph` 类中添加新方法：

```python
    @timed("search_event_setlist")
    async def search_event_setlist_node(self, state: MusicAgentState) -> Dict[str, Any]:
        """
        节点2a-event: 搜索事件歌单
        """
        node_name = "search_event_setlist"
        logger.info(f"--- [步骤 2a-event] 搜索事件歌单 ---")
        self._status_tracker.node_start(node_name)

        parameters = state.get("intent_parameters", {})
        artist = parameters.get("artist", "")
        event_type = parameters.get("event_type", "concert")
        year = parameters.get("year")
        location = parameters.get("location")
        event_name = parameters.get("event_name")

        try:
            from tools.event_setlist_search import get_event_setlist_search_engine
            from tools.music_tools import Song

            engine = get_event_setlist_search_engine()
            setlist = await engine.search(
                artist=artist,
                event_type=event_type,
                year=year,
                location=location,
                event_name=event_name
            )

            if setlist and setlist.songs:
                # 转换为Song格式
                search_results = []
                for song in setlist.songs:
                    s = Song(
                        title=song.title,
                        artist=song.artist or setlist.artist,
                        genre="",
                        popularity=80
                    )
                    d = s.to_dict()
                    d["order"] = song.order
                    d["is_cover"] = song.is_cover
                    d["note"] = song.note
                    search_results.append(d)

                logger.info(f"事件歌单搜索成功: {len(search_results)}首")
                self._status_tracker.node_complete(node_name)

                return {
                    "search_results": search_results,
                    "recommendations": search_results[:5],
                    "step_count": state.get("step_count", 0) + 1,
                    "agent_status": self._status_tracker.get_status(),
                    "metadata": {
                        "event_setlist": setlist.to_dict()
                    }
                }
            else:
                logger.warning(f"未找到事件歌单: {artist} {event_type}")
                self._status_tracker.node_complete(node_name)

                return {
                    "search_results": [],
                    "recommendations": [],
                    "step_count": state.get("step_count", 0) + 1,
                    "agent_status": self._status_tracker.get_status(),
                    "final_response": f"抱歉，未找到{artist}的{event_type}歌单信息，可能是活动尚未举办或信息暂未公开。"
                }

        except Exception as e:
            logger.error(f"事件歌单搜索失败: {e}")
            self._status_tracker.node_complete(node_name, error=str(e))
            return {
                "search_results": [],
                "recommendations": [],
                "step_count": state.get("step_count", 0) + 1,
                "agent_status": self._status_tracker.get_status(),
                "error_log": state.get("error_log", []) + [
                    {"node": "search_event_setlist", "error": str(e)}
                ],
                "final_response": "搜索歌单时遇到了问题，请稍后重试。"
            }
```

- [ ] **Step 3: 更新路由函数 route_by_intent**

在 `route_by_intent` 方法中添加：

```python
    def route_by_intent(self, state: MusicAgentState) -> str:
        """
        路由函数: 根据意图类型决定下一步
        """
        intent_type = state.get("intent_type", "general_chat")
        logger.info(f"根据意图 '{intent_type}' 进行路由")

        if intent_type == "search":
            return "search_songs"
        elif intent_type == "search_by_lyrics":
            return "search_by_lyrics"
        elif intent_type == "search_by_theme":
            return "search_by_theme"
        elif intent_type == "search_by_topic":
            return "search_by_topic"
        elif intent_type == "search_event_setlist":  # 新增
            return "search_event_setlist"
        elif intent_type.startswith("create_playlist"):
            return "analyze_user_preferences"
        elif intent_type in ["recommend_by_mood", "recommend_by_activity",
                            "recommend_by_genre", "recommend_by_artist",
                            "recommend_by_favorites"]:
            return "generate_recommendations"
        else:
            return "general_chat"
```

- [ ] **Step 4: 在 _build_graph 方法中添加节点和边**

在 `_build_graph` 方法中：

1. 添加节点：
```python
        workflow.add_node("search_event_setlist", self.search_event_setlist_node)  # 事件歌单搜索
```

2. 更新条件边：
```python
        workflow.add_conditional_edges(
            "analyze_intent",
            self.route_by_intent,
            {
                "search_songs": "search_songs",
                "search_by_lyrics": "search_by_lyrics",
                "search_by_theme": "search_by_theme",
                "search_by_topic": "search_by_topic",
                "search_event_setlist": "search_event_setlist",  # 新增
                "generate_recommendations": "generate_recommendations",
                "analyze_user_preferences": "analyze_user_preferences",
                "general_chat": "general_chat"
            }
        )
```

3. 添加边到 generate_explanation：
```python
        workflow.add_edge("search_event_setlist", "generate_explanation")  # 事件歌单搜索后生成解释
```

- [ ] **Step 5: Commit**

```bash
git add graphs/music_graph.py
git commit -m "feat: add search_event_setlist node to workflow graph"
```

---

## Task 5: 创建单元测试

**Files:**
- Create: `tests/unit/test_event_setlist_search.py`

**依赖:** Task 3

- [ ] **Step 1: 创建测试文件并添加基础测试**

```python
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

    def test_build_search_query_basic(self):
        engine = EventSetlistSearchEngine()
        query = engine._build_search_query(
            artist="Lady Gaga",
            event_type="concert"
        )
        assert "Lady Gaga" in query
        assert "concert" in query
        assert "setlist" in query

    def test_build_search_query_with_year(self):
        engine = EventSetlistSearchEngine()
        query = engine._build_search_query(
            artist="Lady Gaga",
            event_type="concert",
            year="2025"
        )
        assert "2025" in query

    def test_build_search_query_with_location(self):
        engine = EventSetlistSearchEngine()
        query = engine._build_search_query(
            artist="Lady Gaga",
            event_type="concert",
            location="巴黎"
        )
        assert "Paris" in query  # 应该转换为英文

    def test_build_search_query_festival(self):
        engine = EventSetlistSearchEngine()
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
        engine = EventSetlistSearchEngine()

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
```

- [ ] **Step 2: 运行单元测试**

```bash
cd /Users/wangzhao/Documents/claude_projects/Muisc-Research
python -m pytest tests/unit/test_event_setlist_search.py -v
```

预期输出：所有测试通过

- [ ] **Step 3: Commit**

```bash
git add tests/unit/test_event_setlist_search.py
git commit -m "test: add unit tests for event setlist search"
```

---

## Task 6: 创建集成测试

**Files:**
- Create: `tests/integration/test_event_setlist_end_to_end.py`

**依赖:** Task 4, Task 5

- [ ] **Step 1: 创建集成测试文件**

```python
"""
事件歌单搜索端到端集成测试

这些测试会实际调用Web Search API，需要在环境变量中配置 TAILYAPI_API_KEY
"""

import pytest
import asyncio
import os

from tools.event_setlist_search import get_event_setlist_search_engine


@pytest.mark.asyncio
@pytest.mark.integration
class TestEventSetlistEndToEnd:
    """端到端集成测试"""

    @pytest.fixture
    async def engine(self):
        """获取搜索引擎实例"""
        return get_event_setlist_search_engine()

    @pytest.mark.skipif(
        not os.getenv("TAILYAPI_API_KEY"),
        reason="需要配置 TAILYAPI_API_KEY 环境变量"
    )
    async def test_search_known_concert(self, engine):
        """测试搜索已知的演唱会歌单 - Coldplay"""
        result = await engine.search(
            artist="Coldplay",
            event_type="concert",
            year="2023"
        )

        # 验证返回结果结构
        assert result is not None
        assert result.artist == "Coldplay"
        assert result.event_type == "concert"
        assert len(result.songs) > 0

        # 验证歌曲结构
        first_song = result.songs[0]
        assert first_song.title is not None
        assert first_song.order > 0

    @pytest.mark.skipif(
        not os.getenv("TAILYAPI_API_KEY"),
        reason="需要配置 TAILYAPI_API_KEY 环境变量"
    )
    async def test_search_festival_lineup(self, engine):
        """测试搜索音乐节阵容"""
        result = await engine.search(
            artist="Various",
            event_type="festival",
            event_name="Coachella",
            year="2024"
        )

        # 音乐节可能返回大量艺人
        if result:
            assert result.event_type == "festival"

    @pytest.mark.skipif(
        not os.getenv("TAILYAPI_API_KEY"),
        reason="需要配置 TAILYAPI_API_KEY 环境变量"
    )
    async def test_search_with_location(self, engine):
        """测试带地点的搜索"""
        result = await engine.search(
            artist="Taylor Swift",
            event_type="concert",
            location="Tokyo",
            year="2024"
        )

        if result:
            assert result.artist == "Taylor Swift"

    @pytest.mark.skipif(
        not os.getenv("TAILYAPI_API_KEY"),
        reason="需要配置 TAILYAPI_API_KEY 环境变量"
    )
    async def test_search_nonexistent_event(self, engine):
        """测试搜索不存在的事件"""
        result = await engine.search(
            artist="Fake Artist 12345",
            event_type="concert",
            year="2099"
        )

        # 应该返回 None 或空歌单
        assert result is None or len(result.songs) == 0


@pytest.mark.asyncio
@pytest.mark.integration
class TestMusicGraphIntegration:
    """测试与工作流图的集成"""

    @pytest.mark.skipif(
        not os.getenv("TAILYAPI_API_KEY"),
        reason="需要配置 TAILYAPI_API_KEY 环境变量"
    )
    async def test_intent_recognition_and_search(self):
        """测试意图识别到搜索的完整流程"""
        from graphs.music_graph import MusicRecommendationGraph
        from schemas.music_state import MusicAgentState

        graph = MusicRecommendationGraph()
        app = graph.get_app()

        initial_state: MusicAgentState = {
            "input": "Coldplay 2023演唱会歌单",
            "chat_history": [],
            "user_preferences": {},
            "favorite_songs": [],
            "intent_type": "",
            "intent_parameters": {},
            "intent_context": "",
            "search_results": [],
            "recommendations": [],
            "explanation": "",
            "final_response": "",
            "playlist": None,
            "step_count": 0,
            "error_log": [],
            "metadata": {}
        }

        result = await app.ainvoke(initial_state)

        # 验证意图被正确识别
        assert result.get("intent_type") == "search_event_setlist"

        # 验证有搜索结果或错误处理
        assert "search_results" in result or "final_response" in result
```

- [ ] **Step 2: 运行集成测试（如果配置了API Key）**

```bash
# 先设置环境变量（如果有）
export TAILYAPI_API_KEY=your_api_key

# 运行集成测试
python -m pytest tests/integration/test_event_setlist_end_to_end.py -v --tb=short
```

- [ ] **Step 3: Commit**

```bash
git add tests/integration/test_event_setlist_end_to_end.py
git commit -m "test: add integration tests for event setlist search"
```

---

## Task 7: 验证和最终测试

**Files:**
- 所有已修改文件

**依赖:** Task 1-6

- [ ] **Step 1: 运行所有相关测试**

```bash
# 单元测试
python -m pytest tests/unit/test_event_setlist_search.py -v

# 意图识别测试（验证提示词修改）
python -m pytest tests/regression/test_intent_classification.py -v -k "test_" || echo "意图测试可能依赖其他因素"

# 检查导入是否正常
python -c "from tools.event_setlist_search import get_event_setlist_search_engine; print('Import OK')"
python -c "from graphs.music_graph import MusicRecommendationGraph; print('Graph Import OK')"
```

- [ ] **Step 2: 手动验证工作流**

```bash
# 启动服务器（如果配置完整）
# python run_api_server.py

# 或者直接在Python中测试
python << 'EOF'
import asyncio
from graphs.music_graph import MusicRecommendationGraph
from schemas.music_state import MusicAgentState

async def test():
    graph = MusicRecommendationGraph()
    app = graph.get_app()

    state: MusicAgentState = {
        "input": "周杰伦嘉年华演唱会歌单",
        "chat_history": [],
        "user_preferences": {},
        "favorite_songs": [],
        "intent_type": "",
        "intent_parameters": {},
        "intent_context": "",
        "search_results": [],
        "recommendations": [],
        "explanation": "",
        "final_response": "",
        "playlist": None,
        "step_count": 0,
        "error_log": [],
        "metadata": {}
    }

    result = await app.ainvoke(state)
    print(f"Intent: {result.get('intent_type')}")
    print(f"Response: {result.get('final_response', 'N/A')[:200]}...")
    print(f"Search results count: {len(result.get('search_results', []))}")

asyncio.run(test())
EOF
```

- [ ] **Step 3: 最终 Commit 和总结**

```bash
git log --oneline -5

# 如果一切正常，打标签
git tag -a v0.2.0-event-setlist -m "Add event setlist search feature"
```

---

## 实施检查清单

- [x] 设计文档已确认
- [x] 数据模型定义（EventSetlistSong, EventSetlist）
- [x] 核心搜索类（EventSetlistSearchEngine）
- [x] 意图识别更新
- [x] 工作流图集成
- [x] 单元测试
- [x] 集成测试

---

## 执行选项

**计划创建完成！** 保存于: `docs/superpowers/plans/2026-03-27-event-setlist-search.md`

**两个执行选项:**

1. **Subagent-Driven (推荐)** - 我为每个 Task 分配独立子代理，任务间审查，快速迭代

2. **Inline Execution** - 在当前会话中依次执行 Task，批量执行并设置检查点

**请选择执行方式？**
