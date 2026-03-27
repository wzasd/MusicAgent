# 场景歌单搜索功能设计文档

**日期**: 2026-03-27
**功能**: Event Setlist Search（歌手+特定场景歌单搜索）
**作者**: Claude

---

## 1. 功能概述

支持用户查询特定音乐事件（演唱会、音乐节、颁奖典礼、电视节目）的实际歌单，例如：
- "Lady Gaga 2025巴黎演唱会歌单"
- "泰勒·斯威夫特时代巡演上海站曲目"
- "Coachella 2024音乐节 lineup"

## 2. 架构设计

```
用户输入: "Lady Gaga 2025巴黎演唱会歌单"
    ↓
意图识别: search_event_setlist
    ↓
参数提取: {
    "artist": "Lady Gaga",
    "year": "2025",
    "location": "巴黎",
    "event_type": "concert"
}
    ↓
Web Search: "Lady Gaga 2025 Paris concert setlist"
    ↓
LLM提取: 结构化歌单数据
    ↓
返回结果: 带顺序、备注的歌曲列表
```

## 3. 数据模型

```python
@dataclass
class EventSetlistSong:
    order: int                      # 表演顺序
    title: str                      # 歌曲名
    artist: Optional[str]           # 表演者（用于翻唱/嘉宾情况）
    is_cover: bool                  # 是否翻唱
    original_artist: Optional[str]  # 原唱（如果是翻唱）
    note: Optional[str]             # 备注（如"不插电版"、"嘉宾合唱"）

@dataclass
class EventSetlist:
    event_name: str                 # 活动名称
    event_type: str                 # concert/festival/awards/tv_show
    artist: str                     # 主要表演者
    date: Optional[str]             # 日期
    location: Optional[str]         # 地点
    songs: List[EventSetlistSong]
    total_songs: int
    encore_count: int               # 安可曲数量
    source_url: str                 # 来源链接
```

## 4. 意图识别

### 4.1 新增意图类型
- `intent_type`: `search_event_setlist`

### 4.2 参数结构
```json
{
  "artist": "歌手名",
  "event_type": "concert/festival/awards/tv_show",
  "year": "年份（可选）",
  "location": "地点（可选）",
  "event_name": "活动具体名称（可选）"
}
```

### 4.3 触发关键词模式

| 事件类型 | 触发词 |
|---------|--------|
| concert | 演唱会、巡演、巡回、concert、tour、live |
| festival | 音乐节、festival、lineup、阵容 |
| awards | 颁奖礼、颁奖典礼、awards、performance |
| tv_show | 晚会、春晚、节目单、tv show、show |

## 5. 组件设计

### 5.1 新增文件

| 文件 | 职责 |
|-----|------|
| `tools/event_setlist_search.py` | 事件歌单搜索核心逻辑 |
| `prompts/event_setlist_prompts.py` | 相关提示词模板 |

### 5.2 修改文件

| 文件 | 修改内容 |
|-----|---------|
| `prompts/music_prompts.py` | 在意图识别提示词中添加 `search_event_setlist` 示例和规则 |
| `graphs/music_graph.py` | 添加 `search_event_setlist` 节点和路由逻辑 |

### 5.3 EventSetlistSearchEngine 类设计

```python
class EventSetlistSearchEngine:
    """事件歌单搜索引擎"""

    def __init__(self, web_search_provider=None):
        self.web_search = web_search_provider or get_default_provider()
        self.llm = SiliconFlowLLM()

    async def search(
        self,
        artist: str,
        event_type: str,
        year: Optional[str] = None,
        location: Optional[str] = None,
        event_name: Optional[str] = None
    ) -> Optional[EventSetlist]:
        """搜索事件歌单"""

    async def _search_web(self, query: str) -> str:
        """执行网络搜索"""

    async def _extract_setlist(
        self,
        search_results: str,
        artist: str,
        event_type: str
    ) -> Optional[EventSetlist]:
        """使用LLM从搜索结果中提取结构化歌单"""

    def _build_search_query(
        self,
        artist: str,
        event_type: str,
        year: Optional[str],
        location: Optional[str]
    ) -> str:
        """构建搜索查询词"""
```

## 6. 提示词设计

### 6.1 意图识别更新

在 `MUSIC_INTENT_ANALYZER_PROMPT` 中添加：

```python
'''
输入: "周杰伦嘉年华演唱会歌单"
输出: {"intent_type": "search_event_setlist", "parameters": {"artist": "周杰伦", "event_type": "concert", "event_name": "嘉年华"}, "context": "用户想查询周杰伦嘉年华演唱会的歌单"}

输入: "Coachella 2024音乐节阵容"
输出: {"intent_type": "search_event_setlist", "parameters": {"event_type": "festival", "event_name": "Coachella", "year": "2024"}, "context": "用户想查询Coachella 2024音乐节的演出阵容"}

输入: "Lady Gaga 2025巴黎演唱会"
输出: {"intent_type": "search_event_setlist", "parameters": {"artist": "Lady Gaga", "event_type": "concert", "year": "2025", "location": "巴黎"}, "context": "用户想查询Lady Gaga 2025年巴黎演唱会的歌单"}

规则补充:
7. 事件歌单搜索：当用户提到"xxx演唱会歌单/曲目"、"xxx音乐节阵容/lineup"、"xxx颁奖礼表演"时，intent_type 为 "search_event_setlist"
8. event_type 只能是: concert(演唱会)、festival(音乐节)、awards(颁奖礼)、tv_show(电视节目)
'''
```

### 6.2 歌单提取提示词

```python
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
        {{
            "order": 1,
            "title": "歌曲名",
            "artist": "表演者（如与主要表演者不同）",
            "is_cover": false,
            "original_artist": null,
            "note": "备注（如'开场曲'、'不插电版'、'与XXX合唱'）"
        }}
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
```

## 7. 错误处理

| 场景 | 处理方式 |
|------|----------|
| 搜索结果无歌单信息 | 返回友好提示："未找到该活动的歌单信息，可能是活动尚未举办或信息暂未公开" |
| 搜索结果矛盾 | LLM标注置信度，优先选择多个来源一致的信息 |
| 部分歌曲信息缺失 | 保留已知信息，缺失字段标记为 null |
| Web Search API 失败 | 返回错误提示，建议用户稍后重试 |

## 8. API 返回格式

```json
{
  "success": true,
  "intent_type": "search_event_setlist",
  "event_setlist": {
    "event_name": "The Chromatica Ball",
    "event_type": "concert",
    "artist": "Lady Gaga",
    "date": "2025-07-15",
    "location": "Paris, France",
    "total_songs": 18,
    "encore_count": 2,
    "songs": [
      {
        "order": 1,
        "title": "Bad Romance",
        "artist": "Lady Gaga",
        "is_cover": false,
        "original_artist": null,
        "note": "开场曲"
      },
      {
        "order": 18,
        "title": "Rain On Me",
        "artist": "Lady Gaga",
        "is_cover": false,
        "original_artist": null,
        "note": "Encore"
      }
    ],
    "source_url": "https://www.setlist.fm/..."
  }
}
```

## 9. 测试用例

### 9.1 意图识别测试
- "周杰伦嘉年华演唱会歌单" → `search_event_setlist`
- "Taylor Swift Eras Tour Tokyo setlist" → `search_event_setlist`
- "Coachella 2024 lineup" → `search_event_setlist`
- "春晚2024节目单" → `search_event_setlist`

### 9.2 端到端测试
- "Lady Gaga 2025巴黎演唱会" → 返回结构化歌单
- "不存在的演唱会 2099 火星站" → 友好提示未找到

## 10. 后续扩展

- 支持缓存热门演唱会歌单
- 支持对比不同场次歌单差异
- 支持歌单导出为 Spotify/Apple Music 播放列表
