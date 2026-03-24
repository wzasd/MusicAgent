# Postman Webhook API 测试数据

**API URL**: `POST http://159.75.160.65:8501/webhook/MusicAgent`

**Header**:
```
Content-Type: application/json
```

---

## 1. 单轮搜索 - 直接播放

```json
{
  "messages": [
    {
      "role": "user",
      "content": "I want to listen to Hotel California"
    }
  ],
  "stream": false,
  "sessionId": "postman_test_001"
}
```

---

## 2. 单轮搜索 - 艺术家列表

```json
{
  "messages": [
    {
      "role": "user",
      "content": "What are some popular songs by Taylor Swift"
    }
  ],
  "stream": false,
  "sessionId": "postman_test_002"
}
```

---

## 3. 多轮对话 - 第一轮（查询列表）

```json
{
  "messages": [
    {
      "role": "user",
      "content": "Recommend some songs for running"
    }
  ],
  "stream": false,
  "sessionId": "postman_multi_turn_001"
}
```

---

## 4. 多轮对话 - 第二轮（选择第一首）

**重要**: 使用与第一轮相同的 `sessionId`

```json
{
  "messages": [
    {
      "role": "user",
      "content": "Recommend some songs for running"
    },
    {
      "role": "assistant",
      "content": "Here are some songs for running:\n1. 'Eye of the Tiger' by Survivor\n2. 'Stronger' by Kanye West\n3. 'Can't Hold Us' by Macklemore\n\nPlease tell me which one you'd like to play?"
    },
    {
      "role": "user",
      "content": "the first one"
    }
  ],
  "stream": false,
  "sessionId": "postman_multi_turn_001"
}
```

---

## 5. 多轮对话 - 第二轮（选择第二首）

```json
{
  "messages": [
    {
      "role": "user",
      "content": "Recommend some songs for running"
    },
    {
      "role": "assistant",
      "content": "Here are some songs for running:\n1. 'Eye of the Tiger' by Survivor\n2. 'Stronger' by Kanye West\n3. 'Can't Hold Us' by Macklemore\n\nPlease tell me which one you'd like to play?"
    },
    {
      "role": "user",
      "content": "the second one"
    }
  ],
  "stream": false,
  "sessionId": "postman_multi_turn_001"
}
```

---

## 6. 多轮对话 - 第二轮（指代消解 "play it"）

```json
{
  "messages": [
    {
      "role": "user",
      "content": "Songs by Ed Sheeran"
    },
    {
      "role": "assistant",
      "content": "Songs by Ed Sheeran:\n1. 'Shape of You' by Ed Sheeran\n2. 'Perfect' by Ed Sheeran\n3. 'Thinking Out Loud' by Ed Sheeran\n\nPlease tell me which one you'd like to play?"
    },
    {
      "role": "user",
      "content": "play it"
    }
  ],
  "stream": false,
  "sessionId": "postman_multi_turn_002"
}
```

---

## 7. 歌词搜索

```json
{
  "messages": [
    {
      "role": "user",
      "content": "I want to hear the song with the lyric 'Every night in my dreams'"
    }
  ],
  "stream": false,
  "sessionId": "postman_lyrics_001"
}
```

---

## 8. 心情推荐

```json
{
  "messages": [
    {
      "role": "user",
      "content": "Play some relaxing music"
    }
  ],
  "stream": false,
  "sessionId": "postman_mood_001"
}
```

---

## 9. 活动场景推荐

```json
{
  "messages": [
    {
      "role": "user",
      "content": "Music for studying"
    }
  ],
  "stream": false,
  "sessionId": "postman_activity_001"
}
```

---

## 10. 普通聊天（非音乐查询）

```json
{
  "messages": [
    {
      "role": "user",
      "content": "What's the weather today?"
    }
  ],
  "stream": false,
  "sessionId": "postman_chat_001"
}
```

---

## 多轮对话测试步骤

### 测试 "第一首" 选择流程:

1. **发送 Round 1** (使用 sessionId: `test_123`)
   - 内容: `"Recommend some songs by Taylor Swift"`
   - 预期返回: 歌曲列表

2. **发送 Round 2** (使用相同的 sessionId: `test_123`)
   - 内容: `"the first one"`
   - messages 数组要包含完整的对话历史
   - 预期返回: 播放第一首歌的 action

### 关键字段说明

| 字段 | 类型 | 说明 |
|------|------|------|
| `messages` | array | 对话历史，包含 role (user/assistant) 和 content |
| `role` | string | `"user"` 或 `"assistant"` |
| `content` | string | 消息内容 |
| `stream` | boolean | 是否流式返回，Postman 测试建议用 `false` |
| `sessionId` | string | 会话 ID，多轮对话必须保持一致 |

### 支持的指代词

- `"the first one"` / `"first song"` - 第一首
- `"the second one"` - 第二首
- `"the third one"` - 第三首
- `"the last one"` - 最后一首
- `"play it"` - 播放它（默认第一首）
- `"this one"` - 这个（默认第一首）
