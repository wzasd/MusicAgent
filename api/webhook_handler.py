"""
音乐语音助手 Webhook 处理器
处理来自语音助手的流式请求，支持意图分析、音乐搜索和播控指令
"""

import json
import uuid
import re
from typing import Dict, Any, Optional, List, AsyncGenerator
from pydantic import BaseModel, Field
from dataclasses import dataclass, asdict

from config.logging_config import get_logger
from llms import get_chat_model
from tools.music_tools import Song
from graphs.music_graph import _clean_search_query
from api.music_agent_service import get_music_agent_service, MusicAgentResult
from api.search_logs import add_search_log

logger = get_logger(__name__)


# ========== 请求/响应模型 ==========

class WebhookMessage(BaseModel):
    """消息模型"""
    role: str  # "user" 或 "assistant"
    content: str


class MusicAgentWebhookRequest(BaseModel):
    """音乐助手 Webhook 请求"""
    model: str = "test"
    stream: bool = True
    messages: List[WebhookMessage]
    sessionId: Optional[str] = None


class StreamInfo(BaseModel):
    """流信息"""
    streamType: str  # "start", "partial", "final"
    streamingTextId: str
    streamContent: str


class ActionHeader(BaseModel):
    """动作头部"""
    namespace: str
    name: str


class ForwardSlot(BaseModel):
    """转发槽位"""
    key: str
    value: List[str]


class CallParams(BaseModel):
    """调用参数"""
    targetPkg: str = ""
    deviceType: str = ""
    defaultPkg: str = ""
    forwardSlot: List[ForwardSlot] = Field(default_factory=list)


class ActionPayload(BaseModel):
    """动作载荷"""
    callParams: CallParams
    responses: List[Dict[str, Any]] = Field(default_factory=list)


class Action(BaseModel):
    """播控动作"""
    header: ActionHeader
    payload: ActionPayload


class WebhookReply(BaseModel):
    """Webhook 回复内容"""
    streamInfo: StreamInfo
    action: Optional[List[Action]] = None


class MusicAgentWebhookResponse(BaseModel):
    """音乐助手 Webhook 响应"""
    errorCode: int = 0
    errorMessage: str = ""
    reply: WebhookReply


# ========== 上下文管理 ==========

@dataclass
class ConversationContext:
    """对话上下文"""
    session_id: str
    messages: List[Dict[str, str]]
    last_search_results: List[Dict[str, Any]] = None  # 上次搜索结果，用于指代消解
    last_intent: str = None  # 上次意图

    def get_last_user_message(self) -> str:
        """获取最后一条用户消息"""
        for msg in reversed(self.messages):
            if msg.get("role") == "user":
                return msg.get("content", "")
        return ""

    def get_history_text(self, limit: int = 3) -> str:
        """获取格式化的历史对话"""
        recent = self.messages[-limit*2:] if len(self.messages) > limit*2 else self.messages
        return "\n".join([
            f"{msg.get('role', 'user')}: {msg.get('content', '')}"
            for msg in recent
        ])


# ========== 意图分析增强版 ==========

ANAPHORA_RESOLUTION_PROMPT = """你是一个专业的对话理解助手，负责理解用户的音乐查询并处理指代消解。

【对话历史】
{history}

【当前用户输入】
{current_input}

【任务】
1. 分析用户当前输入的意图
2. 判断用户是想**查看列表**还是**直接播放**：
   - 查看列表：用户问"有哪些"、"都有什么"、"推荐几首"等探索性查询
   - 直接播放：用户说"播放"、"我想听"、"来一首"等明确播放意图
3. **关键：指代消解处理**
   - 如果用户输入包含指代（如"第一首"、"第二个"、"播放它"等），必须结合历史对话理解具体指代什么
   - **如果检测到选择意图（如"第一首"、"播放第二首"），把 resolved_query 直接改写成具体歌曲**
   - 例如：历史列表中有 "1. Eye of the Tiger by Survivor"，用户说"第一首" → resolved_query 应该是 "播放 Eye of the Tiger by Survivor"
4. 返回结构化的意图分析结果

【输出格式】
必须返回纯JSON：
{{
    "intent_type": "search|search_by_lyrics|recommend_by_artist|recommend_by_mood|recommend_by_activity|general_chat|select_from_results|cancel",
    "action_type": "list|play|cancel",  // list=展示列表, play=直接播放, cancel=用户拒绝/取消
    "parameters": {{
        // 根据意图类型填充
        "query": "搜索关键词",
        "artist": "艺术家",
        "mood": "心情",
        "activity": "活动",
        "selection_index": null,  // 如果选择第一首填0，第二首填1，以此类推
        "selection_type": null    // 可选：first, second, third, last
    }},
    "resolved_query": "解析后的完整查询，如果是选择意图，这里应该是具体歌曲名如'播放Eye of the Tiger'",
    "context": "上下文说明"
}}

【意图类型说明】
- search: 搜索特定歌曲
- search_by_lyrics: 按歌词搜索歌曲（用户提到"歌词"、"lyric"或引用具体歌词内容）
- recommend_by_artist: 按艺术家推荐
- recommend_by_mood: 按心情推荐
- recommend_by_activity: 按活动场景推荐
- general_chat: 普通聊天
- select_from_results: 从之前的结果中选择（如"第一首"）
- cancel: 用户拒绝、取消或表示不想继续（如"我不听了","算了","不用了"）

【action_type 判断示例】
- "周杰伦有哪些代表作" → action_type: "list"
- "播放周杰伦的稻香" → action_type: "play"
- "推荐几首适合跑步的歌" → action_type: "list"
- "来首开心的歌" → action_type: "play"
- "第一首" → action_type: "play"
- "我不听了" / "算了" → action_type: "cancel"

【指代消解示例】
历史:
user: 推荐几首跑步歌曲
assistant: 1. Eye of the Tiger by Survivor\n2. Stronger by Kanye West\n3. Can't Hold Us by Macklemore
当前: 第一首

输出:
{{
    "intent_type": "select_from_results",
    "action_type": "play",
    "parameters": {{"query": "Eye of the Tiger", "artist": "Survivor", "selection_index": 0, "selection_type": "first"}},
    "resolved_query": "播放 Eye of the Tiger by Survivor",
    "context": "用户想播放列表中的第一首歌"
}}

【另一个指代消解示例】
历史:
user: 推荐几首跑步歌曲
assistant: 1. Eye of the Tiger by Survivor\n2. Stronger by Kanye West
当前: 播放第二首

输出:
{{
    "intent_type": "select_from_results",
    "action_type": "play",
    "parameters": {{"query": "Stronger", "artist": "Kanye West", "selection_index": 1, "selection_type": "second"}},
    "resolved_query": "播放 Stronger by Kanye West",
    "context": "用户想播放列表中的第二首歌"
}}

【重要】只返回纯JSON，不要包含任何其他文字。"""


async def analyze_intent_with_context(
    current_input: str,
    history: str,
    last_results: List[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    使用LLM分析意图，支持上下文理解

    Args:
        current_input: 当前用户输入
        history: 格式化后的历史对话
        last_results: 上次的搜索结果（用于指代消解）

    Returns:
        意图分析结果
    """
    try:
        llm = get_chat_model()

        # 构建提示词
        prompt = ANAPHORA_RESOLUTION_PROMPT.format(
            history=history if history else "无",
            current_input=current_input
        )

        response = await llm.ainvoke(prompt)

        # 解析JSON
        cleaned_json = _clean_json_from_llm(response.content)
        intent_data = json.loads(cleaned_json)

        logger.info(f"意图分析结果: {intent_data.get('intent_type')}, 解析后: {intent_data.get('resolved_query')}")

        # 处理选择类意图 - 无论intent_type是什么，只要有selection_index就从上次结果中选择
        params = intent_data.get("parameters", {})
        action_type = intent_data.get("action_type", "play")
        selection_index = params.get("selection_index")
        selection_type = params.get("selection_type")

        # 如果意图包含选择意图或resolved_query包含选择关键词，但没有selection_index，尝试解析
        resolved = intent_data.get("resolved_query", "")
        intent_type_value = intent_data.get("intent_type", "")

        # 检查是否是选择意图（select_from_results）或包含选择关键词
        is_selection_intent = intent_type_value == "select_from_results"
        has_selection_keywords = any(kw in resolved for kw in [
            "第一首", "第二首", "第三首", "最后一首",
            "first", "second", "third", "last",
            "第 1", "第 2", "第 3", "1.", "2.", "3."
        ])

        logger.info(f"[Debug] intent={intent_type_value}, is_selection={is_selection_intent}, has_keywords={has_selection_keywords}, last_results={len(last_results) if last_results else 0}")

        # 只有 last_results 存在时才尝试从列表中选择
        # 对于 select_from_results 意图，优先信任 LLM 提供的 query/artist 参数
        if last_results and (is_selection_intent or has_selection_keywords):
            if selection_index is not None:
                # 有明确的选择索引
                # 检查 LLM 是否已经提供了具体的歌曲名（通过改写）
                llm_query = params.get("query", "").strip()
                llm_artist = params.get("artist", "").strip()

                if is_selection_intent and llm_query and llm_query not in ["第一首", "第二首", "第三首", "最后一首"]:
                    # LLM 已经改写了查询，提供具体歌曲名，保持 select_from_results 意图
                    # 这样后续会用 LLM 提供的 query/artist 直接搜索
                    logger.info(f"[Intent] LLM已改写查询，使用改写结果: {llm_query} by {llm_artist}")
                    # 保持 intent_type = "select_from_results"，不移除 selection_index
                elif 0 <= selection_index < len(last_results):
                    # 从列表中选择
                    selected = last_results[selection_index]
                    # 转换为搜索意图，这样后续会播放选中的歌曲
                    intent_data["intent_type"] = "search"
                    intent_data["parameters"] = {
                        "query": selected.get("title", ""),
                        "artist": selected.get("artist", ""),
                        "selection_index": selection_index
                    }
                    intent_data["resolved_query"] = f"播放《{selected.get('title')}》- {selected.get('artist')}"
                    intent_data["selected_index"] = selection_index
                    logger.info(f"意图转换: 从上次结果中选择第 {selection_index+1} 首 - {selected.get('title')}")
            elif is_selection_intent and not params.get("query"):
                # select_from_results 但没有提供具体歌曲名，也没有索引，默认第一首
                selected = last_results[0]
                intent_data["intent_type"] = "select_from_results"  # 保持原意图，让后续用 LLM 改写
                intent_data["parameters"]["query"] = selected.get("title", "")
                intent_data["parameters"]["artist"] = selected.get("artist", "")
                intent_data["parameters"]["selection_index"] = 0
                intent_data["parameters"]["selection_type"] = "first"
                intent_data["resolved_query"] = f"播放 {selected.get('title')} by {selected.get('artist')}"
                logger.info(f"默认选择第一首: {selected.get('title')}")

        # 模糊指代消解：如果action_type是play但没有具体查询参数，且有上次结果，则默认播放第一首
        elif last_results and action_type == "play":
            query = params.get("query", "")
            artist = params.get("artist", "")
            # 检查是否有实际的搜索参数（非空且不是模糊指代词）
            fuzzy_words = ["it", "that", "this", "one", "那首", "那个", "这个", "它"]
            is_fuzzy = (
                not query or
                query.lower() in fuzzy_words or
                any(word in query.lower() for word in fuzzy_words)
            )

            if is_fuzzy and len(last_results) > 0:
                selected = last_results[0]
                logger.info(f"模糊指代消解: 用户说'{query}'，默认选择上次列表第1首 - {selected.get('title')}")
                intent_data["intent_type"] = "search"
                intent_data["parameters"] = {
                    "query": selected.get("title", ""),
                    "artist": selected.get("artist", ""),
                    "selection_index": 0
                }
                intent_data["resolved_query"] = f"播放《{selected.get('title')}》- {selected.get('artist')}"
                intent_data["selected_index"] = 0

        return intent_data

    except Exception as e:
        logger.error(f"意图分析失败: {e}")
        # 降级处理：返回通用搜索意图
        return {
            "intent_type": "search",
            "parameters": {"query": current_input},
            "resolved_query": current_input,
            "context": "使用默认搜索"
        }


def _clean_json_from_llm(llm_output: str) -> str:
    """从LLM的输出中提取并清理JSON字符串"""
    # 首先尝试提取代码块中的内容
    match = re.search(r"```(?:json)?(.*?)```", llm_output, re.DOTALL)
    if match:
        return match.group(1).strip()

    # 如果没有代码块，尝试找到第一个完整的JSON对象
    text = llm_output.strip()
    start_idx = text.find('{')
    if start_idx == -1:
        return text

    # 找到匹配的结束括号
    brace_count = 0
    end_idx = start_idx
    for i, char in enumerate(text[start_idx:], start=start_idx):
        if char == '{':
            brace_count += 1
        elif char == '}':
            brace_count -= 1
            if brace_count == 0:
                end_idx = i + 1
                break

    return text[start_idx:end_idx]


# ========== 流式响应生成器 ==========

def _extract_songs_from_history(messages: List[Dict[str, str]]) -> List[Dict[str, Any]]:
    """从历史消息中解析歌曲列表

    支持多种格式:
    1. 'Eye of the Tiger' by Survivor
    2. "Stronger" by Kanye West
    3. Eye of the Tiger by Survivor (无引号)
    """
    import re

    songs = []
    logger.info(f"[Extract] 开始提取歌曲，消息数: {len(messages)}")

    for msg in messages:
        content = msg.get("content", "")
        role = msg.get("role", "unknown")

        # 跳过空内容
        if not content:
            continue

        # 匹配格式: 数字. '歌曲名' by 艺术家 或 数字. "歌曲名" by 艺术家
        pattern_quoted = r"\d+\.\s*['\"](.+?)['\"]\s+by\s+(\S+)"
        matches = re.findall(pattern_quoted, content)
        for title, artist in matches:
            songs.append({"title": title.strip(), "artist": artist.strip()})
            logger.info(f"[Extract] 带引号匹配: {title} by {artist}")

        # 匹配无引号格式: 数字. 歌曲名 by 艺术家
        # 使用 negative lookahead 避免重复匹配已匹配的
        pattern_unquoted = r"\d+\.\s*([^'\"\n\d][^'\"\n]*?)\s+by\s+([^\n,]+)"
        matches_unquoted = re.findall(pattern_unquoted, content)
        for title, artist in matches_unquoted:
            title_stripped = title.strip()
            artist_stripped = artist.strip()
            # 检查是否已存在
            if not any(s["title"] == title_stripped and s["artist"] == artist_stripped for s in songs):
                songs.append({"title": title_stripped, "artist": artist_stripped})
                logger.info(f"[Extract] 无引号匹配: {title_stripped} by {artist_stripped}")

    logger.info(f"[Extract] 总共提取 {len(songs)} 首歌曲")
    return songs


def generate_streaming_text_id() -> str:
    """生成流文本ID"""
    return uuid.uuid4().hex[:8]


async def create_play_action(song: Song) -> Action:
    """
    创建播放指令

    Args:
        song: 歌曲对象

    Returns:
        播放动作
    """
    return Action(
        header=ActionHeader(
            namespace="Media.AudioVideo",
            name="PLAY_SEARCH_SONG"
        ),
        payload=ActionPayload(
            callParams=CallParams(
                targetPkg="",
                deviceType="",
                defaultPkg="",
                forwardSlot=[
                    ForwardSlot(key="songName", value=[song.title]),
                    ForwardSlot(key="artist", value=[song.artist])
                ]
            ),
            responses=[]
        )
    )


async def stream_webhook_response(
    context: ConversationContext
) -> AsyncGenerator[str, None]:
    """
    流式生成 Webhook 响应

    Yields:
        SSE 格式的数据块
    """
    streaming_id = generate_streaming_text_id()
    accumulated_content = ""  # 跟踪已发送的完整内容，用于计算增量

    # 日志记录相关
    import time
    log_entry = None
    start_time = time.time()

    # 获取最后一条用户消息
    current_input = context.get_last_user_message()
    if not current_input:
        # 发送错误响应
        response = MusicAgentWebhookResponse(
            errorCode=400,
            errorMessage="未找到用户输入",
            reply=WebhookReply(
                streamInfo=StreamInfo(
                    streamType="final",
                    streamingTextId=streaming_id,
                    streamContent="抱歉，我没有收到您的请求。"
                )
            )
        )
        yield f"data: {response.model_dump_json(ensure_ascii=False)}\n\n"
        return

    # 发送开始帧
    start_msg = "Searching for music..."
    accumulated_content = start_msg  # 记录已发送内容
    start_response = MusicAgentWebhookResponse(
        errorCode=0,
        errorMessage="",
        reply=WebhookReply(
            streamInfo=StreamInfo(
                streamType="start",
                streamingTextId=streaming_id,
                streamContent=start_msg  # 开始帧发送完整内容
            )
        )
    )
    yield f"data: {start_response.model_dump_json(ensure_ascii=False)}\n\n"

    try:
        # 分析意图（带上下文）
        history = context.get_history_text(limit=3)
        intent_data = await analyze_intent_with_context(
            current_input=current_input,
            history=history,
            last_results=context.last_search_results
        )

        intent_type = intent_data.get("intent_type", "search")
        parameters = intent_data.get("parameters", {})
        resolved_query = intent_data.get("resolved_query", current_input)
        action_type = intent_data.get("action_type", "play")

        # 处理取消/拒绝意图
        if intent_type == "cancel" or action_type == "cancel":
            # 清理上下文
            context.last_search_results = None

            new_segment = "Okay, no problem! Let me know if you'd like to listen to music later."
            accumulated_content = accumulated_content + new_segment

            final_response = MusicAgentWebhookResponse(
                errorCode=0,
                errorMessage="",
                reply=WebhookReply(
                    streamInfo=StreamInfo(
                        streamType="final",
                        streamingTextId=streaming_id,
                        streamContent=accumulated_content
                    )
                )
            )
            yield f"data: {final_response.model_dump_json(ensure_ascii=False)}\n\n"

            # 记录日志
            if log_entry:
                log_entry.update({
                    "result_count": 0,
                    "elapsed_ms": round((time.time() - start_time) * 1000, 2),
                    "status": "cancelled",
                    "source": "user_cancel",
                })
                add_search_log(log_entry)
            return

        # 针对 recommend_by_artist 意图，默认展示列表
        if intent_type == "recommend_by_artist" and action_type not in ["list", "play"]:
            action_type = "list"

        # 初始化日志条目
        log_entry = {
            "action": "webhook_search",
            "original_query": current_input,
            "intent": intent_type,
            "parameters": parameters,
        }

        # 获取子 agent 服务
        agent_service = get_music_agent_service()

        # 调用子 agent 获取结果
        result: MusicAgentResult = None

        if intent_type == "search":
            query = parameters.get("query", current_input)
            artist = parameters.get("artist")  # 获取艺术家参数
            selection_index = parameters.get("selection_index")

            # 如果是从上次结果中选择（有selection_index），直接播放而不重新搜索
            if selection_index is not None and context.last_search_results:
                try:
                    idx = int(selection_index)
                    if 0 <= idx < len(context.last_search_results):
                        selected = context.last_search_results[idx]
                        logger.info(f"直接播放上次列表第 {idx+1} 首: {selected['title']} - {selected['artist']}")

                        song = Song(title=selected['title'], artist=selected['artist'])
                        action = await create_play_action(song)

                        new_segment = f"Now playing '{selected['title']}' by {selected['artist']}"
                        accumulated_content = accumulated_content + new_segment

                        final_response = MusicAgentWebhookResponse(
                            errorCode=0,
                            errorMessage="",
                            reply=WebhookReply(
                                streamInfo=StreamInfo(
                                    streamType="final",
                                    streamingTextId=streaming_id,
                                    streamContent=accumulated_content
                                ),
                                action=[action]
                            )
                        )

                        # 记录日志
                        log_entry = {
                            "action": "webhook_search",
                            "original_query": current_input,
                            "intent": "select_from_results",
                            "parameters": parameters,
                            "result_count": 1,
                            "elapsed_ms": round((time.time() - start_time) * 1000, 2),
                            "status": "success",
                            "source": "selection",
                            "songs": [{"title": selected['title'], "artist": selected['artist']}],
                        }
                        add_search_log(log_entry)

                        yield f"data: {final_response.model_dump_json(ensure_ascii=False)}\n\n"
                        return
                except (ValueError, TypeError) as e:
                    logger.warning(f"无效的选择索引: {selection_index}, 错误: {e}")

            query = _clean_search_query(query)

            # 检测是否为歌词搜索
            is_lyrics = "歌词" in resolved_query or "lyric" in current_input.lower()

            # 构建新内容并追加到累计内容
            if artist:
                new_segment = f"Searching for {artist}'s '{query}'..."
            else:
                new_segment = f"Searching for '{query}'..."
            accumulated_content = accumulated_content + new_segment  # 全量补充：追加到之前内容

            partial_response = MusicAgentWebhookResponse(
                errorCode=0,
                errorMessage="",
                reply=WebhookReply(
                    streamInfo=StreamInfo(
                        streamType="partial",
                        streamingTextId=streaming_id,
                        streamContent=accumulated_content  # 发送全量内容（包含之前）
                    )
                )
            )
            yield f"data: {partial_response.model_dump_json(ensure_ascii=False)}\n\n"

            # 调用子 agent - 如果有艺术家信息，使用精确搜索
            if artist:
                result = await agent_service.search_songs_by_artist_with_title(
                    artist=artist, title=query, limit=5
                )
            else:
                result = await agent_service.search_songs(query=query, limit=5, is_lyrics=is_lyrics)

        elif intent_type == "search_by_lyrics":
            # 歌词搜索 - 专门处理分支
            query = parameters.get("query", current_input)
            # 从查询中提取纯歌词内容（去除前缀如 "i want to hear the song with the lyric..."）
            from tools.lyrics_search import get_lyrics_search_engine
            lyrics_engine = get_lyrics_search_engine()
            lyrics_content = lyrics_engine.extract_lyrics_content(query)
            if not lyrics_content:
                lyrics_content = query

            logger.info(f"[LyricsSearch] 歌词搜索: query={query}, lyrics={lyrics_content[:50]}...")

            # 构建新内容并追加到累计内容
            new_segment = f"Searching for song with lyrics..."
            accumulated_content = accumulated_content + new_segment

            partial_response = MusicAgentWebhookResponse(
                errorCode=0,
                errorMessage="",
                reply=WebhookReply(
                    streamInfo=StreamInfo(
                        streamType="partial",
                        streamingTextId=streaming_id,
                        streamContent=accumulated_content
                    )
                )
            )
            yield f"data: {partial_response.model_dump_json(ensure_ascii=False)}\n\n"

            # 调用子 agent 进行歌词搜索，强制 is_lyrics=True
            result = await agent_service.search_songs(query=lyrics_content, limit=5, is_lyrics=True)

        elif intent_type == "select_from_results":
            # LLM 已经通过指代消解提供了具体歌曲名，直接搜索播放
            query = parameters.get("query", current_input)
            artist = parameters.get("artist")

            logger.info(f"[SelectFromResults] LLM改写后直接搜索: query={query}, artist={artist}")

            # 清理查询词
            query = _clean_search_query(query)

            if not query or query.strip() == "":
                # 如果LLM没有提供具体歌曲名，fallback到通用搜索
                logger.warning(f"[SelectFromResults] LLM未提供具体歌曲名，使用原始输入: {current_input}")
                query = _clean_search_query(current_input)

            # 构建响应
            if artist:
                new_segment = f"Playing '{query}' by {artist}..."
            else:
                new_segment = f"Playing '{query}'..."
            accumulated_content = accumulated_content + new_segment

            partial_response = MusicAgentWebhookResponse(
                errorCode=0,
                errorMessage="",
                reply=WebhookReply(
                    streamInfo=StreamInfo(
                        streamType="partial",
                        streamingTextId=streaming_id,
                        streamContent=accumulated_content
                    )
                )
            )
            yield f"data: {partial_response.model_dump_json(ensure_ascii=False)}\n\n"

            # 使用改写后的歌曲名直接搜索
            if artist:
                result = await agent_service.search_songs_by_artist_with_title(
                    artist=artist, title=query, limit=5
                )
            else:
                result = await agent_service.search_songs(query=query, limit=5)

            # 如果找到结果，直接播放第一首
            if result and result.songs:
                song = result.songs[0]
                action = await create_play_action(song)

                new_segment = f"Now playing '{song.title}' by {song.artist}"
                accumulated_content = accumulated_content + new_segment

                final_response = MusicAgentWebhookResponse(
                    errorCode=0,
                    errorMessage="",
                    reply=WebhookReply(
                        streamInfo=StreamInfo(
                            streamType="final",
                            streamingTextId=streaming_id,
                            streamContent=accumulated_content
                        ),
                        action=[action]
                    )
                )

                # 记录日志
                log_entry = {
                    "action": "webhook_search",
                    "original_query": current_input,
                    "intent": "select_from_results",
                    "parameters": parameters,
                    "result_count": 1,
                    "elapsed_ms": round((time.time() - start_time) * 1000, 2),
                    "status": "success",
                    "source": "llm_rewrite",
                    "songs": [{"title": song.title, "artist": song.artist}],
                }
                add_search_log(log_entry)

                # 更新上下文的搜索结果
                context.last_search_results = [
                    {"title": s.title, "artist": s.artist} for s in result.songs
                ]

                yield f"data: {final_response.model_dump_json(ensure_ascii=False)}\n\n"
                return
            else:
                # 没找到结果，返回提示
                new_segment = f"Sorry, couldn't find '{query}'"
                accumulated_content = accumulated_content + new_segment

                final_response = MusicAgentWebhookResponse(
                    errorCode=0,
                    errorMessage="",
                    reply=WebhookReply(
                        streamInfo=StreamInfo(
                            streamType="final",
                            streamingTextId=streaming_id,
                            streamContent=accumulated_content
                        ),
                        action=None
                    )
                )
                yield f"data: {final_response.model_dump_json(ensure_ascii=False)}\n\n"
                return

        elif intent_type == "recommend_by_artist":
            artist = parameters.get("artist", current_input)

            # 构建新内容并追加到累计内容
            new_segment = f"Finding songs by {artist}..."
            accumulated_content = accumulated_content + new_segment  # 全量补充

            partial_response = MusicAgentWebhookResponse(
                errorCode=0,
                errorMessage="",
                reply=WebhookReply(
                    streamInfo=StreamInfo(
                        streamType="partial",
                        streamingTextId=streaming_id,
                        streamContent=accumulated_content  # 发送全量内容
                    )
                )
            )
            yield f"data: {partial_response.model_dump_json(ensure_ascii=False)}\n\n"

            # 调用子 agent
            result = await agent_service.get_songs_by_artist(artist=artist, limit=5)

        elif intent_type == "recommend_by_mood":
            mood = parameters.get("mood", "happy")

            # 构建新内容并追加到累计内容
            new_segment = f"Recommending songs for {mood} mood..."
            accumulated_content = accumulated_content + new_segment  # 全量补充

            partial_response = MusicAgentWebhookResponse(
                errorCode=0,
                errorMessage="",
                reply=WebhookReply(
                    streamInfo=StreamInfo(
                        streamType="partial",
                        streamingTextId=streaming_id,
                        streamContent=accumulated_content  # 发送全量内容
                    )
                )
            )
            yield f"data: {partial_response.model_dump_json(ensure_ascii=False)}\n\n"

            # 调用子 agent，传递 session_id 用于多样性
            result = await agent_service.recommend_by_mood(
                mood=mood,
                limit=5,
                session_id=context.session_id
            )

        elif intent_type == "recommend_by_activity":
            activity = parameters.get("activity", "relaxing")
            selection_index = parameters.get("selection_index")

            # 如果是从上次结果中选择，直接播放
            if selection_index is not None and context.last_search_results:
                try:
                    idx = int(selection_index)
                    if 0 <= idx < len(context.last_search_results):
                        selected = context.last_search_results[idx]
                        logger.info(f"[Activity] 直接播放上次列表第 {idx+1} 首: {selected['title']} - {selected['artist']}")

                        song = Song(title=selected['title'], artist=selected['artist'])
                        action = await create_play_action(song)

                        new_segment = f"Now playing '{selected['title']}' by {selected['artist']}"
                        accumulated_content = accumulated_content + new_segment

                        final_response = MusicAgentWebhookResponse(
                            errorCode=0,
                            errorMessage="",
                            reply=WebhookReply(
                                streamInfo=StreamInfo(
                                    streamType="final",
                                    streamingTextId=streaming_id,
                                    streamContent=accumulated_content
                                ),
                                action=[action]
                            )
                        )

                        # 记录日志
                        log_entry = {
                            "action": "webhook_search",
                            "original_query": current_input,
                            "intent": "select_from_results",
                            "parameters": parameters,
                            "result_count": 1,
                            "elapsed_ms": round((time.time() - start_time) * 1000, 2),
                            "status": "success",
                            "source": "selection",
                            "songs": [{"title": selected['title'], "artist": selected['artist']}],
                        }
                        add_search_log(log_entry)

                        yield f"data: {final_response.model_dump_json(ensure_ascii=False)}\n\n"
                        return
                except (ValueError, TypeError) as e:
                    logger.warning(f"无效的选择索引: {selection_index}, 错误: {e}")

            # 构建新内容并追加到累计内容
            new_segment = f"Recommending songs for {activity}..."
            accumulated_content = accumulated_content + new_segment  # 全量补充

            partial_response = MusicAgentWebhookResponse(
                errorCode=0,
                errorMessage="",
                reply=WebhookReply(
                    streamInfo=StreamInfo(
                        streamType="partial",
                        streamingTextId=streaming_id,
                        streamContent=accumulated_content  # 发送全量内容
                    )
                )
            )
            yield f"data: {partial_response.model_dump_json(ensure_ascii=False)}\n\n"

            # 调用子 agent，传递 session_id 用于多样性
            result = await agent_service.recommend_by_activity(
                activity=activity,
                limit=5,
                session_id=context.session_id
            )

        else:
            # 通用聊天
            # 构建新内容并追加到累计内容
            new_segment = "Thinking..."
            accumulated_content = accumulated_content + new_segment  # 全量补充

            partial_response = MusicAgentWebhookResponse(
                errorCode=0,
                errorMessage="",
                reply=WebhookReply(
                    streamInfo=StreamInfo(
                        streamType="partial",
                        streamingTextId=streaming_id,
                        streamContent=accumulated_content  # 发送全量内容
                    )
                )
            )
            yield f"data: {partial_response.model_dump_json(ensure_ascii=False)}\n\n"

            # 使用LLM生成回复
            llm = get_chat_model()
            chat_prompt = f"""You are a music assistant. Please reply to the user's question briefly.

User: {current_input}

Please answer in a friendly manner."""

            response = await llm.ainvoke(chat_prompt)
            response_text = response.content.strip()

            # 构建新内容并追加到累计内容
            accumulated_content = accumulated_content + response_text  # 全量补充

            # 发送纯文本响应
            final_response = MusicAgentWebhookResponse(
                errorCode=0,
                errorMessage="",
                reply=WebhookReply(
                    streamInfo=StreamInfo(
                        streamType="final",
                        streamingTextId=streaming_id,
                        streamContent=accumulated_content  # 发送全量内容
                    )
                )
            )
            yield f"data: {final_response.model_dump_json(ensure_ascii=False)}\n\n"
            return

        # ========== 主 Agent 决策逻辑 ==========
        # 根据子 agent 返回的结果和用户意图，决定是展示列表还是播放

        if not result or not result.songs:
            # 无结果 - 全量补充
            new_segment = result.message if result else "Sorry, no songs found."
            accumulated_content = accumulated_content + new_segment  # 全量补充

            final_response = MusicAgentWebhookResponse(
                errorCode=0,
                errorMessage="",
                reply=WebhookReply(
                    streamInfo=StreamInfo(
                        streamType="final",
                        streamingTextId=streaming_id,
                        streamContent=accumulated_content  # 发送全量内容
                    )
                )
            )
            yield f"data: {final_response.model_dump_json(ensure_ascii=False)}\n\n"
            return

        songs = result.songs
        total = result.total_found

        # 计算耗时并记录日志
        elapsed_time = (time.time() - start_time) * 1000
        if log_entry:
            def _song_brief(s):
                return {"title": s.title, "artist": s.artist}
            log_entry.update({
                "result_count": len(songs),
                "elapsed_ms": round(elapsed_time, 2),
                "status": "success" if songs else "not_found",
                "source": result.metadata.get("source", "unknown") if result.metadata else "unknown",
                "songs": [_song_brief(s) for s in songs[:20]],
            })
            add_search_log(log_entry)

        # 决策逻辑：
        # 1. 如果用户明确说要列表 (action_type=list) → 展示列表
        # 2. 如果用户明确说要播放 (action_type=play) → 播放第一首
        # 3. 如果只有1首歌 → 直接播放
        # 4. 如果有多首歌 → 展示列表让用户选择

        if action_type == "play" or total == 1:
            # 播放模式：直接播放第一首
            song_to_play = songs[0]
            action = await create_play_action(song_to_play)

            if total == 1:
                new_segment = f"Playing '{song_to_play.title}' by {song_to_play.artist}"
            else:
                new_segment = f"Now playing '{songs[0].title}' by {songs[0].artist}"

            # 全量补充：追加到之前内容
            accumulated_content = accumulated_content + new_segment

            final_response = MusicAgentWebhookResponse(
                errorCode=0,
                errorMessage="",
                reply=WebhookReply(
                    streamInfo=StreamInfo(
                        streamType="final",
                        streamingTextId=streaming_id,
                        streamContent=accumulated_content  # 发送全量内容
                    ),
                    action=[action]
                )
            )

            # 保存结果到上下文（用于后续指代消解）
            context.last_search_results = [
                {"title": s.title, "artist": s.artist} for s in songs
            ]

        else:
            # 列表模式：展示歌曲列表
            display_songs = songs[:5]  # 最多展示5首
            song_list_text = "\n".join(
                [f"{i+1}. '{s.title}' by {s.artist}" for i, s in enumerate(display_songs)]
            )

            # 根据查询类型生成不同的提示语
            if intent_type == "search":
                new_segment = f"Found the following songs:\n{song_list_text}\n\nPlease tell me which one you'd like to play?"
            elif intent_type == "recommend_by_artist":
                artist = parameters.get("artist", "")
                new_segment = f"Songs by {artist}:\n{song_list_text}\n\nPlease tell me which one you'd like to play?"
            elif intent_type == "recommend_by_mood":
                mood = parameters.get("mood", "")
                new_segment = f"Songs for {mood} mood:\n{song_list_text}\n\nPlease tell me which one you'd like to play?"
            elif intent_type == "recommend_by_activity":
                activity = parameters.get("activity", "")
                new_segment = f"Songs for {activity}:\n{song_list_text}\n\nPlease tell me which one you'd like to play?"
            else:
                new_segment = f"Here are some songs:\n{song_list_text}\n\nPlease tell me which one you'd like to play?"

            # 全量补充：追加到之前内容
            accumulated_content = accumulated_content + new_segment

            final_response = MusicAgentWebhookResponse(
                errorCode=0,
                errorMessage="",
                reply=WebhookReply(
                    streamInfo=StreamInfo(
                        streamType="final",
                        streamingTextId=streaming_id,
                        streamContent=accumulated_content  # 发送全量内容
                    )
                )
            )

            # 保存结果到上下文（用于后续指代消解）
            context.last_search_results = [
                {"title": s.title, "artist": s.artist} for s in display_songs
            ]

        yield f"data: {final_response.model_dump_json(ensure_ascii=False)}\n\n"

    except Exception as e:
        logger.error(f"处理 webhook 请求失败: {e}", exc_info=True)

        # 记录错误日志
        if log_entry:
            elapsed_time = (time.time() - start_time) * 1000
            log_entry.update({
                "result_count": 0,
                "elapsed_ms": round(elapsed_time, 2),
                "status": "error",
                "error": str(e),
            })
            add_search_log(log_entry)

        # 发送错误响应 - 全量补充
        new_segment = "Sorry, an error occurred while processing your request."
        accumulated_content = accumulated_content + new_segment  # 全量补充

        error_response = MusicAgentWebhookResponse(
            errorCode=500,
            errorMessage=str(e),
            reply=WebhookReply(
                streamInfo=StreamInfo(
                    streamType="final",
                    streamingTextId=streaming_id,
                    streamContent=accumulated_content  # 发送全量内容
                )
            )
        )
        yield f"data: {error_response.model_dump_json(ensure_ascii=False)}\n\n"


# ========== 会话管理 ==========

class SessionManager:
    """会话管理器"""

    def __init__(self):
        self._sessions: Dict[str, ConversationContext] = {}

    def get_or_create_context(self, session_id: str, messages: List[Dict[str, str]]) -> ConversationContext:
        """获取或创建会话上下文"""
        if session_id not in self._sessions:
            # 从历史消息中解析歌曲列表
            extracted_songs = _extract_songs_from_history(messages)
            self._sessions[session_id] = ConversationContext(
                session_id=session_id,
                messages=messages,
                last_search_results=extracted_songs if extracted_songs else None
            )
        else:
            # 更新消息历史
            self._sessions[session_id].messages = messages

        return self._sessions[session_id]

    def update_search_results(self, session_id: str, results: List[Dict[str, Any]]):
        """更新会话的搜索结果"""
        if session_id in self._sessions:
            self._sessions[session_id].last_search_results = results

    def clear_session(self, session_id: str):
        """清除会话"""
        if session_id in self._sessions:
            del self._sessions[session_id]


# 全局会话管理器
_session_manager = SessionManager()


def get_session_manager() -> SessionManager:
    """获取会话管理器"""
    return _session_manager


# ========== 主处理函数 ==========

async def handle_music_agent_webhook(
    request: MusicAgentWebhookRequest
) -> AsyncGenerator[str, None]:
    """
    处理音乐助手 Webhook 请求

    Args:
        request: Webhook 请求

    Yields:
        SSE 格式的数据块
    """
    # 生成 session_id（如果没有提供）
    session_id = request.sessionId or str(uuid.uuid4())

    # 转换消息格式
    messages = [{"role": msg.role, "content": msg.content} for msg in request.messages]

    # 获取或创建会话上下文
    session_manager = get_session_manager()
    context = session_manager.get_or_create_context(session_id, messages)

    logger.info(f"处理 webhook 请求: session={session_id}, messages={len(messages)}")

    # 流式生成响应
    async for chunk in stream_webhook_response(context):
        yield chunk
