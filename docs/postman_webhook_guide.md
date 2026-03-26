# Postman Webhook 测试配置

## 基础配置

| 配置项 | 值 |
|-------|-----|
| **Method** | POST |
| **URL** | `http://159.75.160.65:8501/webhook/MusicAgent` |
| **Content-Type** | `application/json` |

---

## Headers 配置

在 Postman 的 **Headers** 标签页添加：

| Key | Value |
|-----|-------|
| `Content-Type` | `application/json` |

**截图示意：**
```
┌─────────────────────────────────────────┐
│ Headers                                 │
├─────────────────┬───────────────────────┤
│ Content-Type    │ application/json      │
└─────────────────┴───────────────────────┘
```

---

## Body 配置

在 Postman 的 **Body** 标签页选择 **raw** + **JSON** 格式：

### 场景 1：列表展示（询问艺术家歌曲）

```json
{
  "model": "test",
  "stream": true,
  "messages": [
    {
      "role": "user",
      "content": "周杰伦有哪些代表作"
    }
  ],
  "sessionId": "test_session_001"
}
```

**预期结果：** 返回歌曲列表，`action` 字段为 `null`

---

### 场景 2：选择播放（指代消解）

```json
{
  "model": "test",
  "stream": true,
  "messages": [
    {
      "role": "user",
      "content": "第一首"
    }
  ],
  "sessionId": "test_session_001"
}
```

**注意：** `sessionId` 必须与场景 1 相同，才能正确关联上下文

**预期结果：** 返回播放动作，包含 `PLAY_SEARCH_SONG` action

---

### 场景 3：直接播放

```json
{
  "model": "test",
  "stream": true,
  "messages": [
    {
      "role": "user",
      "content": "播放周杰伦的稻香"
    }
  ],
  "sessionId": "test_session_002"
}
```

**预期结果：** 直接返回播放动作

---

### 场景 4：歌词搜索

```json
{
  "model": "test",
  "stream": true,
  "messages": [
    {
      "role": "user",
      "content": "有首歌歌词是后来终于在眼泪中明白"
    }
  ],
  "sessionId": "test_session_003"
}
```

---

### 场景 5：心情推荐

```json
{
  "model": "test",
  "stream": true,
  "messages": [
    {
      "role": "user",
      "content": "推荐几首开心的歌"
    }
  ],
  "sessionId": "test_session_004"
}
```

---

### 场景 6：场景推荐

```json
{
  "model": "test",
  "stream": true,
  "messages": [
    {
      "role": "user",
      "content": "适合跑步时听的歌"
    }
  ],
  "sessionId": "test_session_005"
}
```

---

## Postman 设置步骤

1. **创建新请求**：点击 `+` 新建一个 HTTP 请求

2. **设置 Method 和 URL**：
   ```
   POST  http://159.75.160.65:8501/webhook/MusicAgent
   ```

3. **配置 Headers**：
   - 切换到 Headers 标签
   - 添加 `Content-Type: application/json`

4. **配置 Body**：
   - 切换到 Body 标签
   - 选择 `raw` 选项
   - 右侧下拉选择 `JSON`
   - 粘贴上面的 JSON 内容

5. **发送请求**：
   - 点击 **Send** 按钮

6. **查看响应**：
   - 由于 SSE 流式响应，Postman 会以 `data: {...}` 格式显示多条数据

---

## 响应示例

### 正常响应（SSE 流）

```
data: {"errorCode":0,"errorMessage":"","reply":{"streamInfo":{"streamType":"start","streamingTextId":"xxx","streamContent":"正在为您搜索..."},"action":null}}

data: {"errorCode":0,"errorMessage":"","reply":{"streamInfo":{"streamType":"partial","streamingTextId":"xxx","streamContent":"正在为您查找周杰伦的歌曲..."},"action":null}}

data: {"errorCode":0,"errorMessage":"","reply":{"streamInfo":{"streamType":"final","streamingTextId":"xxx","streamContent":"周杰伦的歌曲有：\n1. 《青花瓷》...","action":null}}
```

### 带播放动作的响应

```json
{
  "errorCode": 0,
  "errorMessage": "",
  "reply": {
    "streamInfo": {
      "streamType": "final",
      "streamingTextId": "xxx",
      "streamContent": "正在为您播放周杰伦的《青花瓷》"
    },
    "action": [
      {
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
      }
    ]
  }
}
```

---

## 常见问题

### 1. 返回 "Field required" 错误

**错误信息：**
```json
{"detail":[{"type":"missing","loc":["body","messages"],"msg":"Field required"}]}
```

**原因：** 请求体格式不正确

**解决：** 确保 Content-Type 设置为 `application/json`，且 Body 选择 raw + JSON

---

### 2. 指代消解不工作（"第一首"无法识别）

**原因：** `sessionId` 不一致

**解决：** 确保列表查询和"第一首"查询使用相同的 `sessionId`

---

### 3. 响应时间过长

**原因：** LLM 处理需要时间

**解决：** 在 Postman 设置中增加超时时间：
- File → Settings → General → Request timeout in ms
- 设置为 30000 (30秒) 或更长

---

## 测试检查清单

| 测试项 | 期望结果 | 状态 |
|-------|---------|------|
| 列表查询返回歌曲列表 | action 为 null | ⬜ |
| 相同 sessionId 下"第一首" | 有 PLAY_SEARCH_SONG action | ⬜ |
| 不同 sessionId 下"第一首" | 无法识别（正常行为） | ⬜ |
| 直接播放请求 | 有 PLAY_SEARCH_SONG action | ⬜ |
| 歌词搜索 | 返回匹配的歌曲 | ⬜ |
| 心情推荐 | 返回推荐列表 | ⬜ |
