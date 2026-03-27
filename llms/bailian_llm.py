"""
阿里云百炼平台 LLM 实现
使用百炼 API 进行文本生成（支持通义千问等模型）
"""

import os
from typing import Optional, Dict, Any
from openai import OpenAI
from langchain_openai import ChatOpenAI
from .base import BaseLLM


class BailianLLM(BaseLLM):
    """阿里云百炼平台 LLM 实现类"""

    def __init__(self, api_key: Optional[str] = None, model_name: Optional[str] = None):
        """
        初始化百炼客户端

        Args:
            api_key: 百炼 API 密钥，如果不提供则从环境变量或 setting.json 读取
            model_name: 模型名称，默认使用 qwen-plus
        """
        if api_key is None:
            api_key = os.getenv("BAILIAN_API_KEY")
            # 如果环境变量中没有，尝试从 setting.json 读取
            if not api_key:
                try:
                    from config.settings_loader import load_settings_from_json
                    settings = load_settings_from_json()
                    api_key = settings.get("BAILIAN_API_KEY")
                except:
                    pass
            if not api_key:
                raise ValueError("百炼 API Key 未找到！请设置 BAILIAN_API_KEY 环境变量或在 setting.json 中配置")

        super().__init__(api_key, model_name)

        # 从 setting.json 读取 base_url，如果没有则使用默认值
        base_url = os.getenv("BAILIAN_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1")
        if base_url == "https://dashscope.aliyuncs.com/compatible-mode/v1":
            try:
                from config.settings_loader import load_settings_from_json
                settings = load_settings_from_json()
                base_url = settings.get("BAILIAN_BASE_URL", base_url)
            except:
                pass

        # 初始化 OpenAI 客户端，使用百炼的 endpoint
        self.client = OpenAI(
            api_key=self.api_key,
            base_url=base_url
        )

        self.default_model = model_name or self.get_default_model()

    def get_default_model(self) -> str:
        """获取默认模型名称"""
        # 优先使用环境变量中的模型配置
        model = os.getenv("BAILIAN_CHAT_MODEL")
        if model:
            return model
        # 如果没有环境变量，尝试从 setting.json 读取
        try:
            from config.settings_loader import load_settings_from_json
            settings = load_settings_from_json()
            return settings.get("BAILIAN_CHAT_MODEL", "qwen-plus")
        except:
            # 如果都失败，使用默认值
            return "qwen-plus"

    def invoke(self, system_prompt: str, user_prompt: str, **kwargs) -> Dict[str, Any]:
        """
        调用百炼 API 生成回复

        Args:
            system_prompt: 系统提示词
            user_prompt: 用户输入
            **kwargs: 其他参数，如 temperature、max_tokens 等

        Returns:
            包含回复文本和 token 使用量的字典
        """
        try:
            # 构建消息
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ]

            # 设置默认参数
            params = {
                "model": self.default_model,
                "messages": messages,
                "temperature": kwargs.get("temperature", 0.7),
                "max_tokens": kwargs.get("max_tokens", 4000),
                "stream": False
            }

            # 调用 API
            response = self.client.chat.completions.create(**params)

            # 提取结果
            content = response.choices[0].message.content
            usage = response.usage

            return {
                "content": content,
                "token_usage": {
                    "prompt_tokens": usage.prompt_tokens,
                    "completion_tokens": usage.completion_tokens,
                    "total_tokens": usage.total_tokens
                }
            }

        except Exception as e:
            raise Exception(f"百炼 API 调用失败: {str(e)}")

    def invoke_text(self, prompt: str, **kwargs) -> str:
        """
        调用百炼 API 生成回复（简化接口）

        Args:
            prompt: 提示词
            **kwargs: 其他参数

        Returns:
            生成的文本
        """
        response = self.invoke(
            system_prompt="你是一个有帮助的AI助手。",
            user_prompt=prompt,
            **kwargs
        )
        return response["content"]


def get_chat_model() -> ChatOpenAI:
    """
    获取 LangChain 兼容的聊天模型（使用百炼）

    Returns:
        ChatOpenAI 实例
    """
    # 优先从环境变量读取 API Key
    api_key = os.getenv("BAILIAN_API_KEY")

    # 如果环境变量中没有，尝试从 setting.json 读取
    if not api_key:
        try:
            from config.settings_loader import load_settings_from_json
            settings = load_settings_from_json()
            api_key = settings.get("BAILIAN_API_KEY")
        except:
            pass

    if not api_key:
        raise ValueError("百炼 API Key 未找到！请设置 BAILIAN_API_KEY 环境变量或在 setting.json 中配置")

    # 优先使用环境变量中的模型配置
    model_name = os.getenv("BAILIAN_CHAT_MODEL")

    # 如果环境变量中没有，尝试从 setting.json 读取
    if not model_name:
        try:
            from config.settings_loader import load_settings_from_json
            settings = load_settings_from_json()
            model_name = settings.get("BAILIAN_CHAT_MODEL")
        except:
            pass

    # 如果都没有，使用默认值
    if not model_name:
        model_name = "qwen-plus"

    # 从 setting.json 读取 base_url
    base_url = os.getenv("BAILIAN_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1")
    if base_url == "https://dashscope.aliyuncs.com/compatible-mode/v1":
        try:
            from config.settings_loader import load_settings_from_json
            settings = load_settings_from_json()
            base_url = settings.get("BAILIAN_BASE_URL", base_url)
        except:
            pass

    # 创建并返回 ChatOpenAI 实例
    return ChatOpenAI(
        api_key=api_key,
        base_url=base_url,
        model=model_name,
        temperature=0.7
    )
