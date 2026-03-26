# 音乐推荐API服务器

基于FastAPI的流式音乐推荐API服务器，支持SSE（Server-Sent Events）流式输出。

## 功能特性

- ✅ SSE流式输出推荐结果
- ✅ 实时状态更新（思考、处理中、完成）
- ✅ 支持音乐推荐和歌单生成
- ✅ CORS支持，可与前端无缝集成
- ✅ 自动API文档（Swagger UI）

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 配置环境变量

确保设置了必要的环境变量（或在`setting.json`中配置）：

```bash
export SILICONFLOW_API_KEY="your-api-key"
export API_PORT=8501  # 可选，默认8501
export API_HOST=0.0.0.0  # 可选，默认0.0.0.0
```

### 3. 启动服务器

```bash
# 方式1: 使用启动脚本
python api/start_server.py

# 方式2: 直接使用uvicorn
uvicorn api.server:app --host 0.0.0.0 --port 8501 --reload
```

### 4. 访问API文档

启动后访问：http://localhost:8501/docs

## API端点

### 流式推荐接口

**POST** `/api/recommendations/stream`

流式获取音乐推荐，使用SSE格式返回。

**请求体：**
```json
{
  "query": "想运动，来点劲爆的",
  "genre": "电子",
  "mood": "兴奋",
  "user_preferences": {}
}
```

**响应格式（SSE）：**
```
data: {"type": "start", "message": "开始分析你的需求..."}

data: {"type": "thinking", "message": "正在理解你的音乐偏好..."}

data: {"type": "response", "text": "根据你的需求...", "is_complete": false}

data: {"type": "song", "song": {...}, "index": 0, "total": 5}

data: {"type": "complete", "success": true}
```

### 流式歌单生成接口

**POST** `/api/playlist/stream`

流式生成智能歌单。

**请求体：**
```json
{
  "query": "适合早晨通勤的活力歌单",
  "target_size": 30,
  "create_spotify_playlist": false,
  "public": false,
  "user_preferences": {}
}
```

### 非流式接口（兼容）

- **POST** `/api/recommendations` - 获取推荐（非流式）
- **POST** `/api/playlist` - 生成歌单（非流式）

---

### Webhook 语音助手接口

**POST** `/webhook/MusicAgent`

专为语音助手设计的流式接口，支持意图分析、音乐搜索和播控指令，返回 SSE 流式响应。

**请求体：**
```json
{
  "model": "test",
  "stream": true,
  "messages": [
    {"role": "user", "content": "周杰伦有哪些代表作"}
  ],
  "sessionId": "user_session_001"
}
```

**参数说明：**

| 字段 | 类型 | 必填 | 说明 |
|-----|------|------|------|
| `model` | string | 否 | 模型标识，默认 "test" |
| `stream` | boolean | 否 | 是否流式输出，默认 true |
| `messages` | array | 是 | 消息列表，最后一个为用户当前输入 |
| `messages[].role` | string | 是 | 角色："user" 或 "assistant" |
| `messages[].content` | string | 是 | 消息内容 |
| `sessionId` | string | 否 | 会话ID，用于维护上下文和指代消解 |

**响应格式（SSE）：**

```
data: {"errorCode":0,"errorMessage":"","reply":{"streamInfo":{"streamType":"start","streamingTextId":"xxx","streamContent":"正在为您搜索..."},"action":null}}

data: {"errorCode":0,"errorMessage":"","reply":{"streamInfo":{"streamType":"partial","streamingTextId":"xxx","streamContent":"正在为您查找周杰伦的歌曲..."},"action":null}}

data: {"errorCode":0,"errorMessage":"","reply":{"streamInfo":{"streamType":"final","streamingTextId":"xxx","streamContent":"周杰伦的歌曲有：\n1. 《青花瓷》- 周杰伦\n2. 《一路向北》- 周杰伦\n...\n\n请告诉我您想播放第几首？"},"action":null}}
```

**流类型说明：**

| streamType | 说明 |
|-----------|------|
| `start` | 开始处理 |
| `partial` | 中间状态更新 |
| `final` | 最终结果 |

**播控动作（Action）：**

当需要播放歌曲时，`action` 字段包含播放指令：

```json
{
  "action": [{
    "header": {
      "namespace": "Media.AudioVideo",
      "name": "PLAY_SEARCH_SONG"
    },
    "payload": {
      "callParams": {
        "forwardSlot": [
          {"key": "songName", "value": ["青花瓷"]},
          {"key": "artist", "value": ["周杰伦"]}
        ]
      }
    }
  }]
}
```

**交互流程示例：**

**场景1：列表展示（无播放动作）**
```bash
curl -X POST http://localhost:8501/webhook/MusicAgent \
  -H "Content-Type: application/json" \
  -d '{
    "model": "test",
    "stream": true,
    "messages": [{"role": "user", "content": "周杰伦有哪些代表作"}],
    "sessionId": "session_001"
  }'
```
响应：返回歌曲列表，`action` 为 null

**场景2：选择播放（有播放动作）**
```bash
curl -X POST http://localhost:8501/webhook/MusicAgent \
  -H "Content-Type: application/json" \
  -d '{
    "model": "test",
    "stream": true,
    "messages": [{"role": "user", "content": "第一首"}],
    "sessionId": "session_001"
  }'
```
响应：返回播放指令，包含 `PLAY_SEARCH_SONG` 动作

**场景3：直接播放（有播放动作）**
```bash
curl -X POST http://localhost:8501/webhook/MusicAgent \
  -H "Content-Type: application/json" \
  -d '{
    "model": "test",
    "stream": true,
    "messages": [{"role": "user", "content": "播放周杰伦的稻香"}],
    "sessionId": "session_002"
  }'
```
响应：直接返回播放指令

**支持的意图类型：**

| 意图 | 示例查询 | 行为 |
|-----|---------|------|
| `search` | "播放稻香" | 直接搜索播放 |
| `search_by_lyrics` | "歌词是后来终于在眼泪中明白" | 歌词搜索 |
| `search_by_theme` | "泰坦尼克号主题曲" | 影视主题曲搜索 |
| `search_by_topic` | "关于雨的歌" | 话题搜索 |
| `recommend_by_artist` | "周杰伦的歌" | 艺术家歌曲 |
| `recommend_by_mood` | "推荐几首开心的歌" | 心情推荐 |
| `recommend_by_activity` | "适合跑步的歌" | 场景推荐 |
| `anaphora_resolution` | "第一首" | 指代消解（需要sessionId） |

**架构说明：**

Webhook 接口采用主/子 Agent 架构：
- **主 Agent** (`webhook_handler.py`)：处理意图分析、对话管理、决策逻辑
- **子 Agent** (`music_agent_service.py`)：执行具体的音乐搜索和推荐任务
- **复用率**：约 82% 的代码复用现有工具层（`tools/music_tools.py`）

**注意事项：**

1. **sessionId 重要性**：用于维护会话上下文，实现指代消解（如"第一首"）
2. **流式响应**：始终使用 SSE 格式，即使 `stream=false` 也返回单条 SSE 数据
3. **超时设置**：建议客户端设置 30 秒超时，LLM 处理可能需要时间
4. **错误处理**：`errorCode` 非 0 时表示错误，`errorMessage` 包含详情

---

| 事件类型 | 说明 |
|---------|------|
| `start` | 开始处理 |
| `thinking` | 思考/处理中 |
| `response` | 响应文本（流式输出） |
| `recommendations_start` | 开始获取推荐 |
| `song` | 单个歌曲数据 |
| `recommendations_complete` | 推荐完成 |
| `songs_start` | 开始获取歌曲列表 |
| `songs_complete` | 歌曲列表完成 |
| `context` | 上下文信息 |
| `seed_summary` | 种子摘要 |
| `playlist` | 播放列表信息 |
| `complete` | 全部完成 |
| `error` | 错误信息 |

## 前端集成

前端使用`fetch` API读取SSE流：

```typescript
const response = await fetch('/api/recommendations/stream', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ query: '...' }),
});

const reader = response.body?.getReader();
const decoder = new TextDecoder();

while (true) {
  const { done, value } = await reader.read();
  if (done) break;
  
  const text = decoder.decode(value);
  // 解析SSE数据
  const lines = text.split('\n');
  for (const line of lines) {
    if (line.startsWith('data: ')) {
      const data = JSON.parse(line.slice(6));
      // 处理事件
    }
  }
}
```

## 开发

### 代码结构

```
api/
├── server.py              # FastAPI主服务器
├── webhook_handler.py     # Webhook语音助手接口（主Agent）
├── music_agent_service.py # 音乐Agent服务（子Agent）
├── start_server.py        # 启动脚本
└── README.md             # 本文档
```

### 调试

启用详细日志：

```bash
uvicorn api.server:app --log-level debug
```

## 注意事项

1. SSE连接需要保持打开状态，确保前端正确处理连接关闭
2. 流式输出速度可通过`asyncio.sleep()`调整
3. 生产环境建议使用反向代理（如Nginx）处理SSE连接
4. 确保CORS配置正确，允许前端域名访问

