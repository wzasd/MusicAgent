"""
LLM模块
提供统一的LLM接口和工厂函数
"""

from typing import Optional

# 导出基类
from .base import BaseLLM

# 导出 SiliconFlow
from .siliconflow_llm import SiliconFlowLLM, get_chat_model as get_siliconflow_chat_model


def get_llm(provider: Optional[str] = None) -> "BaseLLM":
    """
    获取指定提供商的 LLM 实例

    Args:
        provider: LLM 提供商名称，可选 "siliconflow"、"moonshot" 或 "bailian"
                 如果为 None，则使用 DEFAULT_LLM_PROVIDER 配置

    Returns:
        BaseLLM 子类实例

    Raises:
        ValueError: 当指定的提供商不支持时
    """
    import os

    # 如果没有指定 provider，从配置读取默认值
    if provider is None:
        provider = os.getenv("DEFAULT_LLM_PROVIDER")
        if not provider:
            try:
                from config.settings_loader import load_settings_from_json
                settings = load_settings_from_json()
                provider = settings.get("DEFAULT_LLM_PROVIDER", "siliconflow")
            except:
                provider = "siliconflow"

    provider = provider.lower()

    if provider == "moonshot":
        from .moonshot_llm import MoonshotLLM
        return MoonshotLLM()
    elif provider == "bailian":
        from .bailian_llm import BailianLLM
        return BailianLLM()
    elif provider == "siliconflow":
        from .siliconflow_llm import SiliconFlowLLM
        return SiliconFlowLLM()
    else:
        raise ValueError(
            f"不支持的 LLM 提供商: '{provider}'。"
            f"支持的提供商: siliconflow, moonshot, bailian"
        )


def get_chat_model(provider: Optional[str] = None):
    """
    获取指定提供商的 LangChain 兼容聊天模型

    Args:
        provider: LLM 提供商名称，可选 "siliconflow"、"moonshot" 或 "bailian"
                 如果为 None，则使用 DEFAULT_LLM_PROVIDER 配置

    Returns:
        ChatOpenAI 实例

    Raises:
        ValueError: 当指定的提供商不支持时
    """
    import os

    # 如果没有指定 provider，从配置读取默认值
    if provider is None:
        provider = os.getenv("DEFAULT_LLM_PROVIDER")
        if not provider:
            try:
                from config.settings_loader import load_settings_from_json
                settings = load_settings_from_json()
                provider = settings.get("DEFAULT_LLM_PROVIDER", "siliconflow")
            except:
                provider = "siliconflow"

    provider = provider.lower()

    if provider == "moonshot":
        from .moonshot_llm import get_chat_model as get_moonshot_chat_model
        return get_moonshot_chat_model()
    elif provider == "bailian":
        from .bailian_llm import get_chat_model as get_bailian_chat_model
        return get_bailian_chat_model()
    elif provider == "siliconflow":
        from .siliconflow_llm import get_chat_model as get_siliconflow_chat_model
        return get_siliconflow_chat_model()
    else:
        raise ValueError(
            f"不支持的 LLM 提供商: '{provider}'。"
            f"支持的提供商: siliconflow, moonshot, bailian"
        )


# 尝试导入 Moonshot（如果存在）
try:
    from .moonshot_llm import MoonshotLLM, get_chat_model as get_moonshot_chat_model
except ImportError:
    MoonshotLLM = None  # type: ignore
    get_moonshot_chat_model = None  # type: ignore

# 尝试导入 Bailian（如果存在）
try:
    from .bailian_llm import BailianLLM, get_chat_model as get_bailian_chat_model
except ImportError:
    BailianLLM = None  # type: ignore
    get_bailian_chat_model = None  # type: ignore


__all__ = [
    # 基类
    "BaseLLM",
    # 工厂函数
    "get_llm",
    "get_chat_model",
    # SiliconFlow
    "SiliconFlowLLM",
    "get_siliconflow_chat_model",
    # Moonshot（条件导出）
    "MoonshotLLM",
    "get_moonshot_chat_model",
    # Bailian（条件导出）
    "BailianLLM",
    "get_bailian_chat_model",
]
