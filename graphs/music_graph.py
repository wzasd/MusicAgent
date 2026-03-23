"""
音乐推荐Agent的工作流图
"""

import json
import re
import time
import uuid
from typing import Dict, Any, Optional, List

from langgraph.graph import StateGraph, END
from langgraph.graph.state import CompiledStateGraph

from config.logging_config import get_logger
from llms.siliconflow_llm import get_chat_model
from schemas.music_state import MusicAgentState, AgentStatus, NodeExecutionInfo, TokenUsageInfo
from tools.music_tools import get_music_search_tool, get_music_recommender
from prompts.music_prompts import (
    MUSIC_INTENT_ANALYZER_PROMPT,
    MUSIC_RECOMMENDATION_EXPLAINER_PROMPT,
    MUSIC_CHAT_RESPONSE_PROMPT
)
from utils.performance_monitor import timed, get_current_timer

logger = get_logger(__name__)

# 延迟初始化 llm，避免在模块导入时配置未加载
_llm = None


# Agent 状态跟踪器
class AgentStatusTracker:
    """跟踪 Agent 执行状态"""

    def __init__(self):
        self.request_id = str(uuid.uuid4())[:8]
        self.node_history: List[NodeExecutionInfo] = []
        self.current_node: Optional[str] = None
        self.start_time: Optional[float] = None
        self.status = "idle"
        self._node_order = [
            "analyze_intent",
            "search_songs",
            "generate_recommendations",
            "analyze_user_preferences",
            "enhanced_recommendations",
            "create_playlist",
            "general_chat",
            "generate_explanation",
        ]

    def start_request(self):
        """开始新请求"""
        self.start_time = time.time()
        self.status = "running"
        self.node_history = []
        self.current_node = None

    def node_start(self, node_name: str):
        """记录节点开始"""
        self.current_node = node_name
        node_info: NodeExecutionInfo = {
            "node_name": node_name,
            "status": "running",
            "start_time": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "end_time": None,
            "duration_ms": None,
            "error_message": None,
        }
        self.node_history.append(node_info)

    def node_complete(self, node_name: str, error: Optional[str] = None):
        """记录节点完成"""
        for node in self.node_history:
            if node["node_name"] == node_name and node["status"] == "running":
                node["status"] = "failed" if error else "completed"
                node["end_time"] = time.strftime("%Y-%m-%dT%H:%M:%S")
                if self.start_time:
                    node["duration_ms"] = int((time.time() - self.start_time) * 1000)
                if error:
                    node["error_message"] = error
                break

    def get_status(self) -> AgentStatus:
        """获取当前状态"""
        elapsed_ms = None
        if self.start_time:
            elapsed_ms = int((time.time() - self.start_time) * 1000)

        # 计算实际执行的节点数（去重，因为可能有重试）
        executed_nodes = set()
        for node in self.node_history:
            if node["status"] in ["completed", "failed"]:
                executed_nodes.add(node["node_name"])

        # total_nodes 应该是实际会执行的节点数，而不是预定义的列表
        # 根据当前工作流状态动态计算
        current_workflow_nodes = self._estimate_workflow_nodes()

        return {
            "request_id": self.request_id,
            "current_node": self.current_node,
            "overall_status": self.status,
            "nodes_executed": len(executed_nodes),
            "total_nodes": current_workflow_nodes,
            "node_history": self.node_history.copy(),
            "elapsed_ms": elapsed_ms,
        }

    def _estimate_workflow_nodes(self) -> int:
        """根据已执行的节点估算当前工作流的总节点数"""
        if not self.node_history:
            return 3  # 默认最小值: intent -> action -> explanation

        # 获取已执行的节点类型
        executed_types = set()
        for node in self.node_history:
            executed_types.add(node["node_name"])

        # 基础节点: 意图分析 + 生成解释 = 2个
        total = 2

        # 根据已执行的动作节点判断中间步骤
        action_nodes = executed_types - {"analyze_intent", "generate_explanation"}
        total += len(action_nodes)

        return max(total, 3)  # 至少3个节点

    def complete(self):
        """标记请求完成"""
        self.status = "completed"
        self.current_node = None

    def fail(self):
        """标记请求失败"""
        self.status = "failed"


# 全局状态跟踪器
_status_tracker = AgentStatusTracker()

def get_llm():
    """获取LLM实例（延迟初始化）"""
    global _llm
    if _llm is None:
        _llm = get_chat_model()
    return _llm


def get_agent_status_tracker() -> AgentStatusTracker:
    """获取全局 Agent 状态跟踪器"""
    global _status_tracker
    return _status_tracker


def _record_token_usage(response: Any, provider: str = "siliconflow"):
    """记录 Token 使用量"""
    timer = get_current_timer()
    if timer and hasattr(response, "usage") and response.usage:
        usage = response.usage
        timer.record_tokens(
            provider=provider,
            prompt_tokens=getattr(usage, "prompt_tokens", 0),
            completion_tokens=getattr(usage, "completion_tokens", 0),
            total_tokens=getattr(usage, "total_tokens", 0),
        )


def _clean_json_from_llm(llm_output: str) -> str:
    """从LLM的输出中提取并清理JSON字符串"""
    # 首先尝试提取代码块中的内容
    match = re.search(r"```(?:json)?(.*?)```", llm_output, re.DOTALL)
    if match:
        return match.group(1).strip()

    # 如果没有代码块，尝试找到第一个完整的JSON对象
    # 查找第一个 { 和匹配的 }
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


def _clean_search_query(query: str) -> str:
    """
    保守净化搜索词，去除常见前缀和后缀但不误伤歌曲名。
    支持迭代清理，直到无法继续清理为止。
    """
    if not query or not isinstance(query, str):
        return query

    original = query.strip()
    cleaned = original

    # 定义所有需要移除的模式
    prefix_patterns = [
        # 歌词搜索前缀（必须在最前面优先处理）
        r"^歌词[是里有]+[的]?[：:]?\s*",
        # 给我/给我来 + 内容
        r"^给我[来]?[的]?\s*",
        # 我想/我要/我想找/我要找/帮我找/帮我搜
        r"^(?:我想|我要|我想找|我要找|帮我找|帮我搜|给我来)[了]?[的]?\s*",
        # 播放/放/听/搜索/搜/找 + 量词
        r"^(?:播放|搜索|放|听|搜|找)[的]?[一]?[个首点些]?[的]?\s*",
        # 推荐
        r"^(?:推荐|荐)[的]?[一]?[个首点些]?[的]?\s*",
        # 有没有/有
        r"^(?:有没有|有)[的]?\s*",
        # 来 + 量词
        r"^来[一]?[个首点]?[的]?\s*",
        # 适合
        r"^适合\s*",
        # 一些/一点
        r"^(?:一些|一点)\s*",
        # 量词开头
        r"^[一首个点些]\s*",
    ]

    suffix_patterns = [
        r"[,，.。！!？?]$",  # 末尾标点
        r"[的吧吗呢呀啊]$",  # 语气词
        r"[的]?歌$",  # "...的歌" 或 "...歌"
        r"[的]?音乐$",  # "...的音乐"
        r"[的]?曲子$",  # "...的曲子"
        r"[的]?歌曲$",  # "...的歌曲"
        r"时[听]?$",  # "...时" 或 "...时听"
        r"^[一首个点些]$",  # 单独的量词
    ]

    # 迭代清理直到稳定
    max_iterations = 10
    for _ in range(max_iterations):
        previous = cleaned

        # 尝试去除前缀
        for pattern in prefix_patterns:
            match = re.match(pattern, cleaned)
            if match:
                extracted = cleaned[match.end():].strip()
                if extracted and len(extracted) >= 2:
                    cleaned = extracted
                    break  # 一次只应用一个前缀

        # 尝试去除后缀
        for pattern in suffix_patterns:
            match = re.search(pattern, cleaned)
            if match and match.end() == len(cleaned):  # 确保是后缀
                extracted = cleaned[:match.start()].strip()
                if extracted and len(extracted) >= 2:
                    cleaned = extracted
                    break  # 一次只应用一个后缀

        # 如果没有变化，停止迭代
        if cleaned == previous:
            break

    # 最终校验
    if len(cleaned) < 2:
        return original

    return cleaned


class MusicRecommendationGraph:
    """音乐推荐工作流图"""

    def __init__(self):
        self.workflow = self._build_graph()
        self._status_tracker = get_agent_status_tracker()

    def get_app(self) -> CompiledStateGraph:
        """获取编译后的应用"""
        return self.workflow

    @timed("analyze_intent")
    async def analyze_intent(self, state: MusicAgentState) -> Dict[str, Any]:
        """
        节点1: 分析用户意图
        识别用户想要做什么（搜索、推荐、聊天等）
        """
        node_name = "analyze_intent"
        logger.info(f"--- [步骤 1] 分析用户意图 ---")
        self._status_tracker.node_start(node_name)

        user_input = state.get("input", "")

        try:
            # 调用LLM分析意图
            prompt = MUSIC_INTENT_ANALYZER_PROMPT.format(user_input=user_input)
            response = await get_llm().ainvoke(prompt)

            # 记录 Token 使用
            _record_token_usage(response)

            # 解析JSON响应
            cleaned_json = _clean_json_from_llm(response.content)
            intent_data = json.loads(cleaned_json)

            logger.info(f"识别到意图类型: {intent_data.get('intent_type')}")

            self._status_tracker.node_complete(node_name)

            return {
                "intent_type": intent_data.get("intent_type", "general_chat"),
                "intent_parameters": intent_data.get("parameters", {}),
                "intent_context": intent_data.get("context", ""),
                "step_count": state.get("step_count", 0) + 1,
                "agent_status": self._status_tracker.get_status(),
            }

        except json.JSONDecodeError as e:
            logger.error(f"解析意图JSON失败: {str(e)}")
            self._status_tracker.node_complete(node_name, error=str(e))
            # 如果解析失败，默认为通用聊天
            return {
                "intent_type": "general_chat",
                "intent_parameters": {},
                "intent_context": user_input,
                "step_count": state.get("step_count", 0) + 1,
                "agent_status": self._status_tracker.get_status(),
                "error_log": state.get("error_log", []) + [
                    {"node": "analyze_intent", "error": "JSON解析失败"}
                ]
            }
        except Exception as e:
            logger.error(f"意图分析失败: {str(e)}")
            self._status_tracker.node_complete(node_name, error=str(e))
            return {
                "intent_type": "general_chat",
                "intent_parameters": {},
                "intent_context": user_input,
                "step_count": state.get("step_count", 0) + 1,
                "agent_status": self._status_tracker.get_status(),
                "error_log": state.get("error_log", []) + [
                    {"node": "analyze_intent", "error": str(e)}
                ]
            }
    
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
        elif intent_type.startswith("create_playlist"):
            # 创建歌单意图，先分析用户偏好
            return "analyze_user_preferences"
        elif intent_type in ["recommend_by_mood", "recommend_by_activity", 
                            "recommend_by_genre", "recommend_by_artist", 
                            "recommend_by_favorites"]:
            return "generate_recommendations"
        else:
            return "general_chat"
    
    @timed("search_songs")
    async def search_songs_node(self, state: MusicAgentState) -> Dict[str, Any]:
        """
        节点2a: 搜索歌曲
        """
        node_name = "search_songs"
        logger.info(f"--- [步骤 2a] 搜索歌曲 ---")
        self._status_tracker.node_start(node_name)

        parameters = state.get("intent_parameters", {})
        query = parameters.get("query", "")
        # 应用保守的净化兜底
        query = _clean_search_query(query)
        genre = parameters.get("genre")

        try:
            # 执行搜索
            search_tool = get_music_search_tool()
            results = await search_tool.search_songs(
                query=query,
                genre=genre,
                limit=10
            )

            # 转换为字典格式
            search_results = [song.to_dict() for song in results]

            logger.info(f"搜索到 {len(search_results)} 首歌曲")

            self._status_tracker.node_complete(node_name)

            return {
                "search_results": search_results,
                "recommendations": search_results[:5],  # 取前5首作为推荐
                "step_count": state.get("step_count", 0) + 1,
                "agent_status": self._status_tracker.get_status(),
            }

        except Exception as e:
            logger.error(f"搜索歌曲失败: {str(e)}")
            self._status_tracker.node_complete(node_name, error=str(e))
            return {
                "search_results": [],
                "recommendations": [],
                "step_count": state.get("step_count", 0) + 1,
                "agent_status": self._status_tracker.get_status(),
                "error_log": state.get("error_log", []) + [
                    {"node": "search_songs", "error": str(e)}
                ]
            }

    @timed("search_by_lyrics")
    async def search_by_lyrics_node(self, state: MusicAgentState) -> Dict[str, Any]:
        """
        节点2a-lyrics: 根据歌词搜索歌曲
        """
        node_name = "search_by_lyrics"
        logger.info(f"--- [步骤 2a-lyrics] 歌词搜索 ---")
        self._status_tracker.node_start(node_name)

        parameters = state.get("intent_parameters", {})
        lyrics = parameters.get("lyrics", "")

        try:
            from tools.lyrics_search import get_lyrics_search_engine
            lyrics_engine = get_lyrics_search_engine()

            # 执行歌词搜索（本地DB优先，未命中则 LLM 兜底）
            results = await lyrics_engine.search_with_llm_fallback(lyrics, top_k=10)

            # 转换为字典格式
            search_results = []
            for result in results:
                from tools.music_tools import Song
                song = Song(
                    title=result.get("title", "Unknown"),
                    artist=result.get("artist", "Unknown Artist"),
                    genre=result.get("genre", ["流行"]) if isinstance(result.get("genre"), list) else None,
                    popularity=int(result.get("similarity_score", 0.8) * 100)
                )
                search_results.append(song.to_dict())

            logger.info(f"歌词搜索到 {len(search_results)} 首歌曲")

            self._status_tracker.node_complete(node_name)

            return {
                "search_results": search_results,
                "recommendations": search_results[:5],
                "step_count": state.get("step_count", 0) + 1,
                "agent_status": self._status_tracker.get_status(),
            }

        except Exception as e:
            logger.error(f"歌词搜索失败: {str(e)}")
            self._status_tracker.node_complete(node_name, error=str(e))
            return {
                "search_results": [],
                "recommendations": [],
                "step_count": state.get("step_count", 0) + 1,
                "agent_status": self._status_tracker.get_status(),
                "error_log": state.get("error_log", []) + [
                    {"node": "search_by_lyrics", "error": str(e)}
                ]
            }

    @timed("search_by_theme")
    async def search_by_theme_node(self, state: MusicAgentState) -> Dict[str, Any]:
        """
        节点2a-theme: 根据影视剧名搜索主题曲/插曲
        """
        node_name = "search_by_theme"
        logger.info(f"--- [步骤 2a-theme] 影视主题曲搜索 ---")
        self._status_tracker.node_start(node_name)

        parameters = state.get("intent_parameters", {})
        title = parameters.get("title", "")
        country = parameters.get("country")

        try:
            from tools.theme_search import get_theme_search_engine
            from tools.music_tools import Song

            engine = get_theme_search_engine()
            results = await engine.search_by_title(title, country=country, top_k=10)

            search_results = []
            for result in results:
                song = Song(
                    title=result.get("title", "Unknown"),
                    artist=result.get("artist", "Unknown Artist"),
                    popularity=int(result.get("similarity_score", 0.8) * 100),
                )
                d = song.to_dict()
                d["theme_type"] = result.get("theme_type", "主题曲")
                d["from_title"] = result.get("from_title", title)
                search_results.append(d)

            logger.info(f"影视主题曲搜索到 {len(search_results)} 首")
            self._status_tracker.node_complete(node_name)

            return {
                "search_results": search_results,
                "recommendations": search_results[:5],
                "step_count": state.get("step_count", 0) + 1,
                "agent_status": self._status_tracker.get_status(),
            }

        except Exception as e:
            logger.error(f"影视主题曲搜索失败: {str(e)}")
            self._status_tracker.node_complete(node_name, error=str(e))
            return {
                "search_results": [],
                "recommendations": [],
                "step_count": state.get("step_count", 0) + 1,
                "agent_status": self._status_tracker.get_status(),
                "error_log": state.get("error_log", []) + [
                    {"node": "search_by_theme", "error": str(e)}
                ]
            }

    @timed("search_by_topic")
    async def search_by_topic_node(self, state: MusicAgentState) -> Dict[str, Any]:
        """
        节点2a-topic: 根据话题/主题词搜索相关歌曲
        """
        node_name = "search_by_topic"
        logger.info(f"--- [步骤 2a-topic] 话题歌曲搜索 ---")
        self._status_tracker.node_start(node_name)

        parameters = state.get("intent_parameters", {})
        topic = parameters.get("topic", "")
        artist = parameters.get("artist")
        genre = parameters.get("genre")

        try:
            from tools.topic_search import get_topic_search_engine
            from tools.music_tools import Song

            engine = get_topic_search_engine()
            results = await engine.search_by_topic(topic, artist=artist, genre=genre, top_k=10)

            search_results = []
            for result in results:
                song = Song(
                    title=result.get("title", "Unknown"),
                    artist=result.get("artist", "Unknown Artist"),
                    popularity=int(result.get("similarity_score", 0.8) * 100),
                )
                d = song.to_dict()
                d["topic"] = result.get("topic", topic)
                search_results.append(d)

            logger.info(f"话题搜索到 {len(search_results)} 首 (话题='{topic}')")
            self._status_tracker.node_complete(node_name)

            return {
                "search_results": search_results,
                "recommendations": search_results[:5],
                "step_count": state.get("step_count", 0) + 1,
                "agent_status": self._status_tracker.get_status(),
            }

        except Exception as e:
            logger.error(f"话题歌曲搜索失败: {str(e)}")
            self._status_tracker.node_complete(node_name, error=str(e))
            return {
                "search_results": [],
                "recommendations": [],
                "step_count": state.get("step_count", 0) + 1,
                "agent_status": self._status_tracker.get_status(),
                "error_log": state.get("error_log", []) + [
                    {"node": "search_by_topic", "error": str(e)}
                ]
            }

    @timed("generate_recommendations")
    async def generate_recommendations_node(self, state: MusicAgentState) -> Dict[str, Any]:
        """
        节点2b: 生成推荐
        根据不同的意图类型调用不同的推荐方法
        """
        node_name = "generate_recommendations"
        logger.info("--- [步骤 2b] 生成音乐推荐 ---")
        self._status_tracker.node_start(node_name)

        intent_type = state.get("intent_type")
        parameters = state.get("intent_parameters", {})

        try:
            recommender = get_music_recommender()
            search_tool = get_music_search_tool()
            recommendations = []

            if intent_type == "recommend_by_mood":
                mood = parameters.get("mood", "开心")
                recs = await recommender.recommend_by_mood(mood, limit=5)
                recommendations = [rec.to_dict() for rec in recs]

            elif intent_type == "recommend_by_activity":
                activity = parameters.get("activity", "放松")
                recs = await recommender.recommend_by_activity(activity, limit=5)
                recommendations = [rec.to_dict() for rec in recs]

            elif intent_type == "recommend_by_genre":
                genre = parameters.get("genre", "流行")
                songs = await search_tool.get_songs_by_genre(genre, limit=5)
                # 转换为推荐格式
                recommendations = [{
                    "song": song.to_dict(),
                    "reason": f"这是一首优秀的{genre}作品",
                    "similarity_score": 0.85
                } for song in songs]

            elif intent_type == "recommend_by_artist":
                artist = parameters.get("artist", "")
                songs, artist_source = await search_tool.get_songs_by_artist(artist, limit=5)
                recommendations = [{
                    "song": song.to_dict(source=artist_source),
                    "reason": f"{artist}的经典作品",
                    "similarity_score": 0.9
                } for song in songs]

            elif intent_type == "recommend_by_favorites":
                favorite_songs = parameters.get("favorite_songs", [])
                if favorite_songs:
                    recs = await recommender.recommend_by_favorites(favorite_songs, limit=5)
                    recommendations = [rec.to_dict() for rec in recs]

            logger.info(f"生成了 {len(recommendations)} 条推荐")

            self._status_tracker.node_complete(node_name)

            return {
                "recommendations": recommendations,
                "step_count": state.get("step_count", 0) + 1,
                "agent_status": self._status_tracker.get_status(),
            }

        except Exception as e:
            logger.error(f"生成推荐失败: {str(e)}")
            self._status_tracker.node_complete(node_name, error=str(e))
            return {
                "recommendations": [],
                "step_count": state.get("step_count", 0) + 1,
                "agent_status": self._status_tracker.get_status(),
                "error_log": state.get("error_log", []) + [
                    {"node": "generate_recommendations", "error": str(e)}
                ]
            }
    
    @timed("general_chat")
    async def general_chat_node(self, state: MusicAgentState) -> Dict[str, Any]:
        """
        节点2c: 通用聊天
        处理一般性的音乐话题聊天
        """
        node_name = "general_chat"
        logger.info("--- [步骤 2c] 通用音乐聊天 ---")
        self._status_tracker.node_start(node_name)

        user_message = state.get("input", "")
        chat_history = state.get("chat_history", [])

        try:
            # 格式化对话历史
            history_text = "\n".join([
                f"{msg.get('role', 'user')}: {msg.get('content', '')}"
                for msg in chat_history[-5:]  # 只取最近5条
            ])

            # 调用LLM生成回复
            prompt = MUSIC_CHAT_RESPONSE_PROMPT.format(
                chat_history=history_text,
                user_message=user_message
            )
            response = await get_llm().ainvoke(prompt)

            # 记录 Token 使用
            _record_token_usage(response)

            logger.info("生成聊天回复")

            self._status_tracker.node_complete(node_name)

            return {
                "final_response": response.content,
                "step_count": state.get("step_count", 0) + 1,
                "agent_status": self._status_tracker.get_status(),
            }

        except Exception as e:
            logger.error(f"生成聊天回复失败: {str(e)}")
            self._status_tracker.node_complete(node_name, error=str(e))
            return {
                "final_response": "抱歉，我现在遇到了一些问题。不过我很乐意和你聊音乐！你可以告诉我你喜欢什么类型的音乐吗？",
                "step_count": state.get("step_count", 0) + 1,
                "agent_status": self._status_tracker.get_status(),
                "error_log": state.get("error_log", []) + [
                    {"node": "general_chat", "error": str(e)}
                ]
            }
    
    @timed("generate_explanation")
    async def generate_explanation(self, state: MusicAgentState) -> Dict[str, Any]:
        """
        节点3: 生成推荐解释
        为搜索结果或推荐结果生成友好的解释文本
        """
        node_name = "generate_explanation"
        logger.info("--- [步骤 3] 生成推荐解释 ---")
        self._status_tracker.node_start(node_name)
        self._status_tracker.complete()

        recommendations = state.get("recommendations", [])
        user_query = state.get("input", "")
        
        if not recommendations:
            logger.warning("没有推荐结果，跳过解释生成")
            return {
                "explanation": "抱歉，没有找到合适的音乐推荐。",
                "final_response": "抱歉，没有找到符合你要求的音乐。你可以换个方式描述你的需求，或者告诉我你喜欢的歌手和风格？",
                "step_count": state.get("step_count", 0) + 1
            }
        
        try:
            # 格式化推荐结果
            songs_text = ""
            for i, rec in enumerate(recommendations, 1):
                song = rec.get("song", rec)  # 可能是搜索结果或推荐结果
                title = song.get("title", "未知")
                artist = song.get("artist", "未知")
                genre = song.get("genre", "未知")
                reason = rec.get("reason", "")
                
                songs_text += f"{i}. 《{title}》 - {artist} ({genre})\n"
                if reason:
                    songs_text += f"   推荐理由: {reason}\n"
            
            # 调用LLM生成解释
            prompt = MUSIC_RECOMMENDATION_EXPLAINER_PROMPT.format(
                user_query=user_query,
                recommended_songs=songs_text
            )
            response = await get_llm().ainvoke(prompt)
            
            explanation = response.content
            
            # 检查是否有播放列表
            playlist = state.get("playlist")
            playlist_text = ""
            if playlist:
                playlist_text = f"\n\n🎵 已为你创建 Spotify 播放列表：\n{playlist.get('url', '')}\n播放列表名称：{playlist.get('name', '')}"
            
            # 构建完整的最终回复
            final_response = f"{explanation}\n\n推荐歌曲：\n{songs_text}{playlist_text}"
            
            logger.info("成功生成推荐解释")

            self._status_tracker.node_complete(node_name)
            self._status_tracker.complete()

            return {
                "explanation": explanation,
                "final_response": final_response,
                "step_count": state.get("step_count", 0) + 1,
                "agent_status": self._status_tracker.get_status(),
            }

        except Exception as e:
            logger.error(f"生成解释失败: {str(e)}")
            self._status_tracker.node_complete(node_name, error=str(e))
            self._status_tracker.fail()
            
            # 生成简单的备用回复
            songs_list = "\n".join([
                f"{i}. 《{rec.get('song', rec).get('title', '未知')}》 - {rec.get('song', rec).get('artist', '未知')}"
                for i, rec in enumerate(recommendations, 1)
            ])
            
            return {
                "explanation": "为你找到了以下歌曲：",
                "final_response": f"为你找到了以下歌曲：\n\n{songs_list}",
                "step_count": state.get("step_count", 0) + 1,
                "agent_status": self._status_tracker.get_status(),
                "error_log": state.get("error_log", []) + [
                    {"node": "generate_explanation", "error": str(e)}
                ]
            }
    
    async def analyze_user_preferences_node(self, state: MusicAgentState) -> Dict[str, Any]:
        """
        节点: 分析用户偏好 ⭐ NEW
        从 Spotify 获取用户数据并分析偏好
        """
        logger.info("--- [步骤] 分析用户偏好 ---")
        
        try:
            from tools.mcp_adapter import get_mcp_adapter
            from schemas.music_state import UserPreferences
            
            adapter = get_mcp_adapter()
            
            # 获取用户数据
            top_tracks = await adapter.get_user_top_tracks(limit=20)
            top_artists = await adapter.get_user_top_artists(limit=20)
            
            # 分析偏好（简单实现）
            favorite_artists = [artist.name for artist in top_artists[:10]]
            
            # 提取流派（从艺术家）
            genres = []
            for artist in top_artists:
                if artist.genres:
                    genres.extend(artist.genres)
            
            # 统计流派频率
            from collections import Counter
            genre_counter = Counter(genres)
            favorite_genres = [genre for genre, _ in genre_counter.most_common(5)]
            
            # 提取年代（从歌曲年份）
            decades = []
            for song in top_tracks:
                if song.year:
                    decade = (song.year // 10) * 10
                    decades.append(f"{decade}s")
            
            decade_counter = Counter(decades)
            favorite_decades = [decade for decade, _ in decade_counter.most_common(3)]
            
            preferences: UserPreferences = {
                "favorite_genres": favorite_genres,
                "favorite_artists": favorite_artists,
                "favorite_decades": favorite_decades,
                "avoid_genres": [],
                "mood_preferences": [],
                "activity_contexts": [],
                "language_preference": "mixed"
            }
            
            logger.info(f"分析完成: 偏好流派={favorite_genres}, 偏好艺术家={favorite_artists[:3]}")
            
            return {
                "user_preferences": preferences,
                "favorite_songs": [song.to_dict() for song in top_tracks[:10]],
                "step_count": state.get("step_count", 0) + 1
            }
            
        except Exception as e:
            logger.error(f"分析用户偏好失败: {str(e)}", exc_info=True)
            # 如果失败，返回空偏好，继续执行
            return {
                "user_preferences": {},
                "favorite_songs": [],
                "step_count": state.get("step_count", 0) + 1,
                "error_log": state.get("error_log", []) + [
                    {"node": "analyze_user_preferences", "error": str(e)}
                ]
            }
    
    async def enhanced_recommendations_node(self, state: MusicAgentState) -> Dict[str, Any]:
        """
        节点: 增强推荐 ⭐ NEW
        结合用户偏好生成推荐
        """
        logger.info("--- [步骤] 生成增强推荐 ---")
        
        try:
            from tools.mcp_adapter import get_mcp_adapter
            
            adapter = get_mcp_adapter()
            user_preferences = state.get("user_preferences", {})
            intent_type = state.get("intent_type", "")
            parameters = state.get("intent_parameters", {})
            
            recommendations = []
            
            # 根据意图类型生成推荐
            if intent_type.startswith("create_playlist"):
                # 创建歌单：结合用户偏好和意图参数
                activity = parameters.get("activity", "")
                mood = parameters.get("mood", "")
                
                # 使用用户 top tracks 作为种子
                favorite_songs = state.get("favorite_songs", [])
                seed_tracks = []
                if favorite_songs:
                    for song in favorite_songs[:5]:
                        if isinstance(song, dict) and song.get("spotify_id"):
                            seed_tracks.append(song["spotify_id"])
                
                # 使用用户偏好流派
                favorite_genres = user_preferences.get("favorite_genres", [])
                seed_genres = favorite_genres[:3] if favorite_genres else ["pop"]
                
                # 如果指定了活动或心情，调整流派
                if activity:
                    activity_genre_map = {
                        "运动": ["electronic", "rock"],
                        "健身": ["electronic", "rock"],
                        "学习": ["acoustic", "jazz"],
                        "工作": ["acoustic", "jazz"],
                    }
                    for key, genres in activity_genre_map.items():
                        if key in activity:
                            seed_genres = genres[:3]
                            break
                
                # 获取推荐
                songs = await adapter.get_recommendations(
                    seed_tracks=seed_tracks if seed_tracks else None,
                    seed_genres=seed_genres,
                    limit=30  # 创建歌单需要更多歌曲
                )
                
                # 转换为推荐格式
                for song in songs:
                    recommendations.append({
                        "song": song.to_dict(),
                        "reason": f"结合你的音乐偏好推荐",
                        "similarity_score": 0.9
                    })
            else:
                # 其他推荐类型，使用原有逻辑
                recommender = get_music_recommender()
                if intent_type == "recommend_by_mood":
                    mood = parameters.get("mood", "开心")
                    recs = await recommender.recommend_by_mood(mood, limit=5)
                    recommendations = [rec.to_dict() for rec in recs]
                elif intent_type == "recommend_by_activity":
                    activity = parameters.get("activity", "放松")
                    recs = await recommender.recommend_by_activity(activity, limit=5)
                    recommendations = [rec.to_dict() for rec in recs]
            
            logger.info(f"生成了 {len(recommendations)} 条增强推荐")
            
            return {
                "recommendations": recommendations,
                "step_count": state.get("step_count", 0) + 1
            }
            
        except Exception as e:
            logger.error(f"生成增强推荐失败: {str(e)}", exc_info=True)
            return {
                "recommendations": [],
                "step_count": state.get("step_count", 0) + 1,
                "error_log": state.get("error_log", []) + [
                    {"node": "enhanced_recommendations", "error": str(e)}
                ]
            }
    
    def route_after_preferences(self, state: MusicAgentState) -> str:
        """
        路由函数: 分析用户偏好后的路由
        """
        intent_type = state.get("intent_type", "")
        if intent_type.startswith("create_playlist"):
            return "enhanced_recommendations"
        else:
            return "generate_recommendations"
    
    async def create_playlist_node(self, state: MusicAgentState) -> Dict[str, Any]:
        """
        节点: 创建播放列表 ⭐ NEW
        """
        logger.info("--- [步骤] 创建播放列表 ---")
        
        try:
            from tools.mcp_adapter import get_mcp_adapter
            from tools.music_tools import Song
            
            adapter = get_mcp_adapter()
            
            # 获取推荐结果
            recommendations = state.get("recommendations", [])
            if not recommendations:
                logger.warning("没有推荐结果，无法创建播放列表")
                return {
                    "playlist": None,
                    "step_count": state.get("step_count", 0) + 1,
                    "error_log": state.get("error_log", []) + [
                        {"node": "create_playlist", "error": "没有推荐结果"}
                    ]
                }
            
            # 提取歌曲
            songs = []
            for rec in recommendations:
                song_data = rec.get("song", rec)
                if isinstance(song_data, dict):
                    # 从字典创建 Song 对象
                    song = Song(
                        title=song_data.get("title", "未知"),
                        artist=song_data.get("artist", "未知"),
                        album=song_data.get("album"),
                        genre=song_data.get("genre"),
                        year=song_data.get("year"),
                        duration=song_data.get("duration"),
                        popularity=song_data.get("popularity"),
                        preview_url=song_data.get("preview_url"),
                        spotify_id=song_data.get("spotify_id"),
                        external_url=song_data.get("external_url")
                    )
                    songs.append(song)
            
            if not songs:
                logger.warning("无法提取歌曲信息")
                return {
                    "playlist": None,
                    "step_count": state.get("step_count", 0) + 1
                }
            
            # 生成播放列表名称和描述
            intent_type = state.get("intent_type", "")
            parameters = state.get("intent_parameters", {})
            
            if "activity" in parameters:
                playlist_name = f"适合{parameters['activity']}的歌单"
                description = f"AI 为你推荐的适合{parameters['activity']}时听的音乐"
            elif "mood" in parameters:
                playlist_name = f"{parameters['mood']}心情歌单"
                description = f"AI 为你推荐的适合{parameters['mood']}心情的音乐"
            else:
                playlist_name = "AI 推荐歌单"
                description = "AI 为你推荐的个性化音乐歌单"
            
            # 创建播放列表
            playlist = await adapter.create_playlist(
                name=playlist_name,
                songs=songs,
                description=description,
                public=False
            )
            
            if playlist:
                logger.info(f"播放列表创建成功: {playlist.url}")
                return {
                    "playlist": playlist.to_dict(),
                    "step_count": state.get("step_count", 0) + 1
                }
            else:
                return {
                    "playlist": None,
                    "step_count": state.get("step_count", 0) + 1,
                    "error_log": state.get("error_log", []) + [
                        {"node": "create_playlist", "error": "创建播放列表失败"}
                    ]
                }
                
        except Exception as e:
            logger.error(f"创建播放列表失败: {str(e)}", exc_info=True)
            return {
                "playlist": None,
                "step_count": state.get("step_count", 0) + 1,
                "error_log": state.get("error_log", []) + [
                    {"node": "create_playlist", "error": str(e)}
                ]
            }
    
    def route_after_recommendations(self, state: MusicAgentState) -> str:
        """
        路由函数: 生成推荐后的路由
        """
        intent_type = state.get("intent_type", "")
        if intent_type.startswith("create_playlist"):
            return "create_playlist"
        else:
            return "generate_explanation"
    
    def _build_graph(self) -> CompiledStateGraph:
        """构建工作流图"""
        logger.info("开始构建音乐推荐工作流图...")
        
        workflow = StateGraph(MusicAgentState)
        
        # 添加节点
        workflow.add_node("analyze_intent", self.analyze_intent)
        workflow.add_node("search_songs", self.search_songs_node)
        workflow.add_node("search_by_lyrics", self.search_by_lyrics_node)  # 歌词搜索
        workflow.add_node("search_by_theme", self.search_by_theme_node)   # 影视主题曲搜索
        workflow.add_node("search_by_topic", self.search_by_topic_node)   # 话题歌曲搜索
        workflow.add_node("generate_recommendations", self.generate_recommendations_node)
        workflow.add_node("analyze_user_preferences", self.analyze_user_preferences_node)  # ⭐ NEW
        workflow.add_node("enhanced_recommendations", self.enhanced_recommendations_node)  # ⭐ NEW
        workflow.add_node("create_playlist", self.create_playlist_node)  # ⭐ NEW
        workflow.add_node("general_chat", self.general_chat_node)
        workflow.add_node("generate_explanation", self.generate_explanation)
        
        # 设置入口点
        workflow.set_entry_point("analyze_intent")
        
        # 添加条件边：根据意图路由
        workflow.add_conditional_edges(
            "analyze_intent",
            self.route_by_intent,
            {
                "search_songs": "search_songs",
                "search_by_lyrics": "search_by_lyrics",  # 歌词搜索
                "search_by_theme": "search_by_theme",     # 影视主题曲搜索
                "search_by_topic": "search_by_topic",     # 话题歌曲搜索
                "generate_recommendations": "generate_recommendations",
                "analyze_user_preferences": "analyze_user_preferences",  # ⭐ NEW
                "general_chat": "general_chat"
            }
        )
        
        # 用户偏好分析后的路由
        workflow.add_conditional_edges(
            "analyze_user_preferences",
            self.route_after_preferences,
            {
                "enhanced_recommendations": "enhanced_recommendations",
                "generate_recommendations": "generate_recommendations"
            }
        )
        
        # 增强推荐后的路由
        workflow.add_conditional_edges(
            "enhanced_recommendations",
            self.route_after_recommendations,
            {
                "create_playlist": "create_playlist",
                "generate_explanation": "generate_explanation"
            }
        )
        
        # 搜索和推荐后生成解释
        workflow.add_edge("search_songs", "generate_explanation")
        workflow.add_edge("search_by_lyrics", "generate_explanation")  # 歌词搜索后生成解释
        workflow.add_edge("search_by_theme", "generate_explanation")   # 主题曲搜索后生成解释
        workflow.add_edge("search_by_topic", "generate_explanation")   # 话题搜索后生成解释
        workflow.add_edge("generate_recommendations", "generate_explanation")
        
        # 创建播放列表后生成解释
        workflow.add_edge("create_playlist", "generate_explanation")
        
        # 聊天和解释后结束
        workflow.add_edge("general_chat", END)
        workflow.add_edge("generate_explanation", END)
        
        # 编译图
        app = workflow.compile()
        logger.info("音乐推荐工作流图构建完成")
        
        return app

