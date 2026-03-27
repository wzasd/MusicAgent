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
