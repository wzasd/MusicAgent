# Webhook 歌词搜索修复计划

## 问题回顾

3个歌词搜索失败案例：
- **lyrics_002**: "sitting out here on the hood of this truck" → 错误返回 David Nail 而非 Gary Allan
- **lyrics_004**: "how i wish you could see the potential" → 错误返回播客而非歌曲
- **lyrics_005**: "fell from your heart and landed in my eyes" → 错误返回 Alicia Keys 而非 Florence + The Machine

根本原因：
1. 本地歌词数据库覆盖不足
2. Web Search 关键词不够精准
3. 搜索结果过滤机制缺失

---

## 修复方案

### Phase 1: 优化搜索关键词 (高优先级 / 低成本)

**目标**: 提升 Tavily Web Search 返回相关歌曲的概率

#### 1.1 增强歌词搜索关键词模板

**当前模板**:
```python
"lyrics": '"{lyrics}" lyrics song name artist'
```

**优化后模板**:
```python
# 多层关键词策略
"lyrics": [
    # 层级1: 精确歌词匹配（最优先）
    '"{lyrics}" song lyrics artist "{lyrics}"',

    # 层级2: 扩展音乐相关关键词
    '"{lyrics}" song title singer track music',

    # 层级3: 添加专业音乐网站限定
    '"{lyrics}" site:genius.com OR site:musicbrainz.org OR site:allmusic.com',

    # 层级4: 移除可能混淆的关键词（针对失败案例优化）
    '"{lyrics}" song -podcast -"podcast episode" -"an announcement"',
]
```

#### 1.2 按歌词特征动态调整关键词

```python
def build_lyrics_query_v2(lyrics: str) -> List[Dict]:
    """
    构建多层级歌词搜索查询
    返回多个查询配置，按优先级尝试
    """
    base_queries = []

    # 查询1: 精确匹配 + 专业音乐网站
    base_queries.append({
        "query": f'"{lyrics}" lyrics song artist',
        "include_domains": [
            "genius.com",          # 歌词网站
            "musicbrainz.org",     # 音乐数据库
            "allmusic.com",        # 音乐信息
            "discogs.com",         # 唱片数据库
            "last.fm",             # 音乐社区
            "billboard.com",       # 音乐榜单
            "azlyrics.com",        # 歌词网站
            "lyrics.com",          # 歌词网站
            "songfacts.com",       # 歌曲信息
        ],
        "search_depth": "advanced",
        "max_results": 8,
    })

    # 查询2: 扩展关键词（如果查询1无结果）
    base_queries.append({
        "query": f'"{lyrics}" song title singer track "{lyrics}"',
        "include_domains": [],  # 不限制域名，扩大搜索
        "exclude_domains": [
            "spotify.com",       # 排除可能导致返回播客的域名
        ],
        "search_depth": "advanced",
        "max_results": 10,
    })

    # 查询3: 针对播客污染的排除策略
    base_queries.append({
        "query": f'"{lyrics}" song lyrics -podcast -episode -"announcement"',
        "include_domains": [
            "genius.com",
            "musicbrainz.org",
            "wikipedia.org",
        ],
        "search_depth": "advanced",
        "max_results": 8,
    })

    return base_queries
```

#### 1.3 添加歌词特征分析优化

```python
def analyze_lyrics_features(lyrics: str) -> Dict[str, Any]:
    """
    分析歌词特征，用于优化搜索策略
    """
    features = {
        "length": len(lyrics),
        "has_quotation": '"' in lyrics or '"' in lyrics,
        "is_english": is_english_text(lyrics),
        "key_phrases": [],
        "search_hints": []
    }

    # 提取关键短语（去除常见停用词后的前3-4个词）
    words = lyrics.lower().split()
    stop_words = {"i", "you", "the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for"}
    content_words = [w for w in words if w not in stop_words]

    if len(content_words) >= 3:
        features["key_phrases"] = [" ".join(content_words[:4])]

    # 根据特征添加搜索提示
    if features["is_english"] and len(lyrics) > 50:
        # 长英文歌词可能是独立/另类音乐
        features["search_hints"].append("indie alternative rock pop")

    if "country" in lyrics.lower() or "truck" in lyrics.lower():
        # 可能乡村音乐
        features["search_hints"].append("country music")

    return features
```

---

### Phase 2: 搜索结果过滤与验证 (高优先级)

**目标**: 防止播客/非音乐内容通过验证

#### 2.1 添加结果类型检测

```python
def is_valid_song_result(result: Dict[str, Any]) -> Tuple[bool, str]:
    """
    验证搜索结果是否是有效的歌曲信息

    Returns:
        (是否有效, 原因)
    """
    title = result.get("title", "")
    content = result.get("content", "")
    url = result.get("url", "")

    # 排除播客
    podcast_indicators = [
        "podcast", "episode", "announcement", "undisclosed",
        "show notes", "listen to", "subscribe to"
    ]
    for indicator in podcast_indicators:
        if indicator in title.lower() or indicator in content.lower():
            return False, f"检测到播客内容: {indicator}"

    # 排除视频平台（除非是音乐视频）
    video_domains = ["youtube.com/watch", "vimeo.com"]
    for domain in video_domains:
        if domain in url and "music" not in content.lower():
            return False, "非音乐视频内容"

    # 必须包含歌曲相关信息
    song_indicators = ["song", "track", "lyrics", "artist", "singer", "album", "single"]
    has_song_indicator = any(ind in content.lower() for ind in song_indicators)

    if not has_song_indicator:
        return False, "缺少歌曲相关关键词"

    return True, "通过验证"
```

#### 2.2 增强 LLM 提取 Prompt

当前 Prompt 需要增强验证要求：

```python
LYRICS_IDENTIFICATION_FROM_SEARCH_V2_PROMPT = """
你是专业的歌词识别助手。请根据以下搜索结果，识别包含这段歌词的歌曲。

【歌词片段】
{lyrics}

【搜索结果】
{search_results}

【任务要求】
1. 只识别**歌曲**，忽略播客、广播剧、视频内容
2. 返回的歌曲必须明确包含或高度匹配给定的歌词片段
3. 如果不确定，confidence 必须低于 0.5
4. 如果搜索结果中没有匹配的**歌曲**，返回 null

【输出格式】
必须返回 JSON:
{{
    "title": "歌曲名",
    "artist": "艺术家名",
    "confidence": 0.0-1.0,
    "source": "搜索结果中的来源",
    "is_song": true,  // 必须是 true 才有效
    "reasoning": "判断理由"
}}

【重要规则】
- 如果搜索结果是播客、广播节目、视频内容 → 返回 null
- 如果找不到明确的歌曲匹配 → 返回 null
- confidence > 0.8 必须基于明确的歌词匹配证据
"""
```

---

### Phase 3: 本地数据库扩展 (中优先级)

**目标**: 减少对 Web Search 的依赖

#### 3.1 优先补充缺失的歌曲

基于失败案例，优先补充：
- Gary Allan - "Watching Airplanes"
- Death Cab for Cutie - "I Will Possess Your Heart"
- Florence + The Machine - "Cosmic Love"

#### 3.2 批量扩展歌词数据库

考虑使用爬虫从以下网站批量获取：
- genius.com
- azlyrics.com
- lyrics.com

---

### Phase 4: 多源交叉验证 (低优先级 / 长期)

**目标**: 提升识别准确率到 95%+

#### 4.1 双源验证策略

```python
async def search_with_cross_validation(lyrics: str) -> Optional[Dict]:
    """
    使用多个数据源交叉验证
    """
    # 源1: Tavily Web Search
    web_result = await search_with_web_fallback(lyrics)

    # 源2: 尝试 Spotify 搜索（如果配置）
    spotify_result = await search_spotify_by_lyrics(lyrics)

    # 交叉验证
    if web_result and spotify_result:
        if normalize_title(web_result["title"]) == normalize_title(spotify_result["title"]):
            return web_result  # 两个源一致，可信度高

    # 不一致时，优先返回置信度高的
    if web_result and web_result.get("confidence", 0) > 0.8:
        return web_result

    if spotify_result and spotify_result.get("confidence", 0) > 0.8:
        return spotify_result

    return None
```

---

## 实施优先级

| Phase | 任务 | 预计工作量 | 预期效果 |
|-------|------|----------|---------|
| P1 | 优化搜索关键词 (Phase 1) | 4小时 | 提升 20-30% 准确率 |
| P1 | 增强结果过滤 (Phase 2.1) | 3小时 | 消除播客污染问题 |
| P2 | 优化 LLM Prompt (Phase 2.2) | 2小时 | 提升识别准确率 |
| P3 | 补充缺失歌曲 (Phase 3) | 2小时 | 解决 3 个已知失败案例 |
| P4 | 多源验证 (Phase 4) | 1-2天 | 长期稳定性提升 |

---

## 验证计划

每完成一个 Phase，运行回归测试验证：

```bash
# 运行歌词搜索专项测试
pytest tests/regression/test_webhook_regression.py::TestWebhookRegression::test_batch_webhook_regression -v

# 查看报告
cat .cache/regression_reports/webhook_regression_failures.json
```

成功标准：
- 3 个已知失败案例全部通过
- 没有新的失败案例产生
- 报告生成正确的根因分析

---

## 相关文件

- `tools/multilingual_search.py` - 搜索关键词构建
- `tools/lyrics_search.py` - 歌词搜索逻辑
- `prompts/music_prompts.py` - LLM Prompt 模板
- `tests/regression/test_webhook_regression.py` - 回归测试

---

*计划创建时间: 2026-03-24*
