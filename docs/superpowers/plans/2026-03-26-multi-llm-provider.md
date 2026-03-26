# 多 LLM 提供商支持（Kimi/Moonshot）实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在现有音乐推荐 Agent 中增加 Kimi (Moonshot AI) LLM 提供商支持，实现通过配置切换 SiliconFlow 和 Kimi

**Architecture:** 基于现有 `SiliconFlowLLM` 结构，新增 `MoonshotLLM` 类，两者继承自同一 `BaseLLM`。通过 `get_llm()` 工厂函数根据 `DEFAULT_LLM_PROVIDER` 配置返回对应实例。

**Tech Stack:** Python 3.10+, OpenAI SDK (兼容模式), Pydantic

---

## 文件结构

| 文件 | 操作 | 职责 |
|------|------|------|
| `llms/moonshot_llm.py` | 创建 | `MoonshotLLM` 类实现，与 `SiliconFlowLLM` 结构一致 |
| `llms/__init__.py` | 修改 | 添加 `get_llm()` 工厂函数，支持 `siliconflow`/`moonshot` 切换 |
| `config/settings_loader.py` | 修改 | 添加 Moonshot 配置项的环境变量映射 |
| `tests/llms/test_moonshot_llm.py` | 创建 | MoonshotLLM 单元测试 |

---

## 前置检查

- [ ] **确认 BaseLLM 接口**

阅读 `llms/base.py`，确认以下抽象方法/接口：
- `invoke(system_prompt, user_prompt, **kwargs) -> Dict[str, Any]`
- `invoke_text(system_prompt, user_prompt, **kwargs) -> str`
- `ainvoke(prompt, **kwargs) -> str`
- `get_model_info() -> Dict[str, Any]`

---

## Task 1: 创建 MoonshotLLM 类

**Files:**
- Create: `llms/moonshot_llm.py`
- Reference: `llms/siliconflow_llm.py` (复制其结构)

- [ ] **Step 1.1: 创建文件框架**

```python
"""
Moonshot AI (Kimi) LLM 实现
使用 Moonshot API 进行文本生成
"""

import os
from typing import Optional, Dict, Any
from openai import OpenAI
from langchain_openai import ChatOpenAI
from .base import BaseLLM


class MoonshotLLM(BaseLLM):
    """Moonshot AI (Kimi) LLM 实现类"""
    pass


def get_chat_model() -> ChatOpenAI:
    """获取 LangChain 兼容的聊天模型（使用 Moonshot）"""
    pass
```

- [ ] **Step 1.2: 实现 `__init__` 方法**

```python
    def __init__(self, api_key: Optional[str] = None, model_name: Optional[str] = None):
        """
        初始化 Moonshot 客户端

        Args:
            api_key: Moonshot API Key，如果不提供则从环境变量或 setting.json 读取
            model_name: 模型名称，默认使用 kimi-k2.5
        """
        if api_key is None:
            api_key = os.getenv("MOONSHOT_API_KEY")
            # 如果环境变量中没有，尝试从 setting.json 读取
            if not api_key:
                try:
                    from config.settings_loader import load_settings_from_json
                    settings = load_settings_from_json()
                    api_key = settings.get("MOONSHOT_API_KEY")
                except:
                    pass
            if not api_key:
                raise ValueError("Moonshot API Key 未找到！请设置 MOONSHOT_API_KEY 环境变量或在 setting.json 中配置")

        super().__init__(api_key, model_name)

        # 从 setting.json 读取 base_url，如果没有则使用默认值
        base_url = os.getenv("MOONSHOT_BASE_URL", "https://api.moonshot.cn/v1")
        if base_url == "https://api.moonshot.cn/v1":
            try:
                from config.settings_loader import load_settings_from_json
                settings = load_settings_from_json()
                base_url = settings.get("MOONSHOT_BASE_URL", base_url)
            except:
                pass

        # 初始化 OpenAI 客户端，使用 Moonshot 的 endpoint
        self.client = OpenAI(
            api_key=self.api_key,
            base_url=base_url
        )

        self.default_model = model_name or self.get_default_model()
```

- [ ] **Step 1.3: 实现 `get_default_model` 方法**

```python
    def get_default_model(self) -> str:
        """获取默认模型名称"""
        # 优先使用环境变量中的模型配置
        model = os.getenv("MOONSHOT_CHAT_MODEL")
        if model:
            return model
        # 如果没有环境变量，尝试从 setting.json 读取
        try:
            from config.settings_loader import load_settings_from_json
            settings = load_settings_from_json()
            return settings.get("MOONSHOT_CHAT_MODEL", "kimi-k2.5")
        except:
            # 如果都失败，使用默认值
            return "kimi-k2.5"
```

- [ ] **Step 1.4: 实现 `invoke` 方法**

```python
    def invoke(self, system_prompt: str, user_prompt: str, **kwargs) -> Dict[str, Any]:
        """
        调用 Moonshot API 生成回复

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

            # 提取回复内容
            if response.choices and response.choices[0].message:
                content = response.choices[0].message.content

                # 提取 token 使用量
                usage = {}
                if hasattr(response, 'usage') and response.usage:
                    usage = {
                        'prompt_tokens': response.usage.prompt_tokens or 0,
                        'completion_tokens': response.usage.completion_tokens or 0,
                        'total_tokens': response.usage.total_tokens or 0,
                    }

                return {
                    'content': self.validate_response(content),
                    'usage': usage,
                    'model': self.default_model,
                }
            else:
                return {'content': '', 'usage': {}, 'model': self.default_model}

        except Exception as e:
            print(f"Moonshot API 调用错误: {str(e)}")
            raise e
```

- [ ] **Step 1.5: 实现 `invoke_text` 方法**

```python
    def invoke_text(self, system_prompt: str, user_prompt: str, **kwargs) -> str:
        """只返回文本内容的便捷方法（向后兼容）"""
        result = self.invoke(system_prompt, user_prompt, **kwargs)
        return result.get('content', '')
```

- [ ] **Step 1.6: 实现 `ainvoke` 方法**

```python
    async def ainvoke(self, prompt: str, **kwargs) -> str:
        """
        异步调用 LLM（兼容 LangChain 接口）

        Args:
            prompt: 提示词
            **kwargs: 其他参数

        Returns:
            生成的文本内容
        """
        import asyncio
        loop = asyncio.get_event_loop()
        # 在线程池中运行同步的 invoke
        result = await loop.run_in_executor(
            None,
            lambda: self.invoke("You are a helpful assistant.", prompt, **kwargs)
        )
        if isinstance(result, dict):
            return result.get('content', '')
        return str(result)
```

- [ ] **Step 1.7: 实现 `get_model_info` 方法**

```python
    def get_model_info(self) -> Dict[str, Any]:
        """
        获取当前模型信息

        Returns:
            模型信息字典
        """
        return {
            "provider": "Moonshot",
            "model": self.default_model,
            "api_base": "https://api.moonshot.cn/v1"
        }
```

- [ ] **Step 1.8: 实现 `get_chat_model` 函数**

```python

def get_chat_model() -> ChatOpenAI:
    """
    获取 LangChain 兼容的聊天模型（使用 Moonshot）

    Returns:
        ChatOpenAI 实例
    """
    # 优先从环境变量读取 API Key
    api_key = os.getenv("MOONSHOT_API_KEY")

    # 如果环境变量中没有，尝试从 setting.json 读取
    if not api_key:
        try:
            from config.settings_loader import load_settings_from_json
            settings = load_settings_from_json()
            api_key = settings.get("MOONSHOT_API_KEY")
        except:
            pass

    if not api_key:
        raise ValueError("Moonshot API Key 未找到！请设置 MOONSHOT_API_KEY 环境变量或在 setting.json 中配置")

    # 优先使用环境变量中的模型配置
    model_name = os.getenv("MOONSHOT_CHAT_MODEL")

    # 如果环境变量中没有，尝试从 setting.json 读取
    if not model_name:
        try:
            from config.settings_loader import load_settings_from_json
            settings = load_settings_from_json()
            model_name = settings.get("MOONSHOT_CHAT_MODEL")
        except:
            pass

    # 如果还是没有，使用默认值
    if not model_name:
        model_name = "kimi-k2.5"

    # 从 setting.json 读取 base_url，如果没有则使用默认值
    base_url = os.getenv("MOONSHOT_BASE_URL", "https://api.moonshot.cn/v1")
    if base_url == "https://api.moonshot.cn/v1":
        try:
            from config.settings_loader import load_settings_from_json
            settings = load_settings_from_json()
            base_url = settings.get("MOONSHOT_BASE_URL", base_url)
        except:
            pass

    return ChatOpenAI(
        api_key=api_key,
        base_url=base_url,
        model=model_name,
        temperature=0.7,
        max_tokens=4000
    )
```

- [ ] **Step 1.9: 提交代码**

```bash
git add llms/moonshot_llm.py
git commit -m "feat: add MoonshotLLM class for Kimi API support"
```

---

## Task 2: 添加 LLM 工厂函数

**Files:**
- Modify: `llms/__init__.py`

- [ ] **Step 2.1: 阅读现有 `__init__.py` 内容**

```bash
cat llms/__init__.py
```

- [ ] **Step 2.2: 添加工厂函数**

在 `llms/__init__.py` 中添加：

```python
from typing import Optional


def get_llm(provider: Optional[str] = None) -> "BaseLLM":
    """
    获取指定提供商的 LLM 实例

    Args:
        provider: LLM 提供商名称，可选 "siliconflow" 或 "moonshot"
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
    elif provider == "siliconflow":
        from .siliconflow_llm import SiliconFlowLLM
        return SiliconFlowLLM()
    else:
        raise ValueError(
            f"不支持的 LLM 提供商: '{provider}'。"
            f"支持的提供商: siliconflow, moonshot"
        )
```

- [ ] **Step 2.3: 确保导出**

确认 `llms/__init__.py` 包含以下导出（根据现有内容调整）：

```python
from .base import BaseLLM
from .siliconflow_llm import SiliconFlowLLM, get_chat_model as get_siliconflow_chat_model
from .moonshot_llm import MoonshotLLM, get_chat_model as get_moonshot_chat_model

__all__ = [
    "BaseLLM",
    "SiliconFlowLLM",
    "MoonshotLLM",
    "get_llm",
    "get_siliconflow_chat_model",
    "get_moonshot_chat_model",
]
```

**注意**: 如果 `__init__.py` 已有其他导出，保留它们并添加新的。

- [ ] **Step 2.4: 提交代码**

```bash
git add llms/__init__.py
git commit -m "feat: add get_llm() factory function for provider switching"
```

---

## Task 3: 添加 Moonshot 配置环境变量映射

**Files:**
- Modify: `config/settings_loader.py`

- [ ] **Step 3.1: 找到 `env_mapping` 字典**

在 `config/settings_loader.py` 中找到以下代码段：

```python
    env_mapping = {
        "SILICONFLOW_API_KEY": "SILICONFLOW_API_KEY",
        "SILICONFLOW_BASE_URL": "SILICONFLOW_BASE_URL",
        "SILICONFLOW_CHAT_MODEL": "SILICONFLOW_MODEL",
        "DASH_SCOPE_API_KEY": "DASH_SCOPE_API_KEY",
        ...
    }
```

- [ ] **Step 3.2: 添加 Moonshot 和 DEFAULT_LLM_PROVIDER 映射**

在 `env_mapping` 字典中添加以下项：

```python
    env_mapping = {
        # ... 原有配置 ...
        "DEFAULT_LLM_PROVIDER": "DEFAULT_LLM_PROVIDER",
        "MOONSHOT_API_KEY": "MOONSHOT_API_KEY",
        "MOONSHOT_BASE_URL": "MOONSHOT_BASE_URL",
        "MOONSHOT_CHAT_MODEL": "MOONSHOT_CHAT_MODEL",
    }
```

- [ ] **Step 3.3: 提交代码**

```bash
git add config/settings_loader.py
git commit -m "feat: add Moonshot configuration environment variable mappings"
```

---

## Task 4: 创建单元测试

**Files:**
- Create: `tests/llms/test_moonshot_llm.py`

- [ ] **Step 4.1: 创建测试文件框架**

```python
"""
MoonshotLLM 单元测试
"""

import pytest
import os
from unittest.mock import Mock, patch, MagicMock

# 跳过测试如果没有配置
MOONSHOT_API_KEY = os.getenv("MOONSHOT_API_KEY", "")


class TestMoonshotLLMInit:
    """测试 MoonshotLLM 初始化"""

    def test_init_with_api_key(self):
        """测试使用显式 API Key 初始化"""
        from llms.moonshot_llm import MoonshotLLM

        llm = MoonshotLLM(api_key="test-key", model_name="kimi-k2.5")

        assert llm.api_key == "test-key"
        assert llm.default_model == "kimi-k2.5"

    def test_init_without_api_key_raises(self):
        """测试未提供 API Key 时抛出异常"""
        from llms.moonshot_llm import MoonshotLLM

        # 清除可能的环境变量
        with patch.dict(os.environ, {}, clear=True):
            with patch("config.settings_loader.load_settings_from_json") as mock_load:
                mock_load.return_value = {}
                with pytest.raises(ValueError) as exc_info:
                    MoonshotLLM()

                assert "Moonshot API Key 未找到" in str(exc_info.value)

    def test_default_model_fallback(self):
        """测试默认模型回退"""
        from llms.moonshot_llm import MoonshotLLM

        with patch.dict(os.environ, {"MOONSHOT_API_KEY": "test"}):
            llm = MoonshotLLM()
            assert llm.default_model == "kimi-k2.5"


class TestMoonshotLLMMethods:
    """测试 MoonshotLLM 方法"""

    @pytest.fixture
    def mock_llm(self):
        """创建带有 mock client 的 LLM 实例"""
        from llms.moonshot_llm import MoonshotLLM

        llm = MoonshotLLM(api_key="test-key", model_name="kimi-k2.5")
        llm.client = MagicMock()
        return llm

    def test_invoke_success(self, mock_llm):
        """测试 invoke 方法成功调用"""
        # 设置 mock 响应
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = "Hello, World!"
        mock_response.usage.prompt_tokens = 10
        mock_response.usage.completion_tokens = 5
        mock_response.usage.total_tokens = 15

        mock_llm.client.chat.completions.create.return_value = mock_response

        result = mock_llm.invoke("System prompt", "User prompt")

        assert result["content"] == "Hello, World!"
        assert result["usage"]["prompt_tokens"] == 10
        assert result["usage"]["completion_tokens"] == 5
        assert result["model"] == "kimi-k2.5"

    def test_invoke_text(self, mock_llm):
        """测试 invoke_text 便捷方法"""
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = "Test response"
        mock_response.usage = Mock()

        mock_llm.client.chat.completions.create.return_value = mock_response

        result = mock_llm.invoke_text("System", "User")

        assert result == "Test response"

    def test_get_model_info(self, mock_llm):
        """测试 get_model_info 方法"""
        info = mock_llm.get_model_info()

        assert info["provider"] == "Moonshot"
        assert info["model"] == "kimi-k2.5"
        assert info["api_base"] == "https://api.moonshot.cn/v1"


class TestGetLLMFactory:
    """测试 get_llm 工厂函数"""

    def test_get_llm_moonshot(self):
        """测试获取 Moonshot 实例"""
        with patch.dict(os.environ, {"MOONSHOT_API_KEY": "test-key"}):
            from llms import get_llm
            from llms.moonshot_llm import MoonshotLLM

            llm = get_llm("moonshot")
            assert isinstance(llm, MoonshotLLM)

    def test_get_llm_siliconflow(self):
        """测试获取 SiliconFlow 实例"""
        with patch.dict(os.environ, {"SILICONFLOW_API_KEY": "test-key"}):
            from llms import get_llm
            from llms.siliconflow_llm import SiliconFlowLLM

            llm = get_llm("siliconflow")
            assert isinstance(llm, SiliconFlowLLM)

    def test_get_llm_default_provider(self):
        """测试默认提供商"""
        with patch.dict(os.environ, {
            "DEFAULT_LLM_PROVIDER": "moonshot",
            "MOONSHOT_API_KEY": "test-key"
        }):
            from llms import get_llm
            from llms.moonshot_llm import MoonshotLLM

            llm = get_llm()  # 不提供 provider 参数
            assert isinstance(llm, MoonshotLLM)

    def test_get_llm_invalid_provider(self):
        """测试无效提供商抛出异常"""
        from llms import get_llm

        with pytest.raises(ValueError) as exc_info:
            get_llm("invalid")

        assert "不支持的 LLM 提供商" in str(exc_info.value)
        assert "invalid" in str(exc_info.value)


@pytest.mark.skipif(not MOONSHOT_API_KEY, reason="未配置 MOONSHOT_API_KEY")
class TestMoonshotLLMIntegration:
    """集成测试 - 需要真实 API Key"""

    def test_real_api_call(self):
        """测试真实 API 调用（可选）"""
        from llms.moonshot_llm import MoonshotLLM

        llm = MoonshotLLM()
        result = llm.invoke_text("你是一个友好的助手", "你好，请用一句话介绍自己")

        assert len(result) > 0
        assert "Kimi" in result or "Moonshot" in result or "助手" in result
```

- [ ] **Step 4.2: 运行测试确保无语法错误**

```bash
python -m py_compile tests/llms/test_moonshot_llm.py
```

Expected: 无输出（表示语法正确）

- [ ] **Step 4.3: 提交测试代码**

```bash
git add tests/llms/test_moonshot_llm.py
git commit -m "test: add MoonshotLLM unit tests"
```

---

## Task 5: 验证测试

**Files:**
- Run: `tests/llms/test_moonshot_llm.py`

- [ ] **Step 5.1: 运行单元测试（mock 测试）**

```bash
python -m pytest tests/llms/test_moonshot_llm.py::TestMoonshotLLMInit -v
python -m pytest tests/llms/test_moonshot_llm.py::TestMoonshotLLMMethods -v
python -m pytest tests/llms/test_moonshot_llm.py::TestGetLLMFactory -v
```

Expected: 所有测试通过（5-6 个测试）

- [ ] **Step 5.2: 检查导入是否正常工作**

```bash
python -c "from llms import get_llm, MoonshotLLM, SiliconFlowLLM; print('Import OK')"
```

Expected: `Import OK`

- [ ] **Step 5.3: 提交**

```bash
git add .
git commit -m "test: verify MoonshotLLM imports and unit tests"
```

---

## Task 6: 更新配置文件示例

**Files:**
- Create/Update: `setting.json.example` 或更新 README

- [ ] **Step 6.1: 准备配置说明**

为用户提供配置示例，添加到 README 或单独的示例文件：

```json
{
  "settings": {
    "DEFAULT_LLM_PROVIDER": "moonshot",

    "SILICONFLOW_API_KEY": "sk-siliconflow-xxx",
    "SILICONFLOW_BASE_URL": "https://api.siliconflow.cn/v1",
    "SILICONFLOW_CHAT_MODEL": "Qwen/Qwen2.5-72B-Instruct",
    "SILICONFLOW_EMBED_MODEL": "BAAI/bge-m3",

    "MOONSHOT_API_KEY": "sk-moonshot-xxx",
    "MOONSHOT_BASE_URL": "https://api.moonshot.cn/v1",
    "MOONSHOT_CHAT_MODEL": "kimi-k2.5"
  }
}
```

- [ ] **Step 6.2: 更新 README.md 的 "配置密钥" 部分**

在 README.md 中找到配置表格，添加新行：

```markdown
| 字段 | 说明 |
|------|------|
| `DEFAULT_LLM_PROVIDER` | 默认 LLM 提供商：`siliconflow` 或 `moonshot` |
| `MOONSHOT_API_KEY` | Moonshot API Key（使用 Kimi 时必填）|
| `MOONSHOT_BASE_URL` | Moonshot API 地址，默认 `https://api.moonshot.cn/v1` |
| `MOONSHOT_CHAT_MODEL` | Moonshot 模型，默认 `kimi-k2.5` |
```

- [ ] **Step 6.3: 提交文档更新**

```bash
git add README.md
git commit -m "docs: add Moonshot/Kimi configuration to README"
```

---

## 验证清单

- [ ] `llms/moonshot_llm.py` 存在且包含完整 `MoonshotLLM` 类
- [ ] `llms/__init__.py` 包含 `get_llm()` 工厂函数
- [ ] `config/settings_loader.py` 包含 Moonshot 环境变量映射
- [ ] `tests/llms/test_moonshot_llm.py` 包含完整单元测试
- [ ] `get_llm("moonshot")` 返回 `MoonshotLLM` 实例
- [ ] `get_llm("siliconflow")` 返回 `SiliconFlowLLM` 实例
- [ ] 未设置 `DEFAULT_LLM_PROVIDER` 时默认为 `siliconflow`
- [ ] README 已更新配置说明
- [ ] 所有单元测试通过

---

**依赖**: 无前置依赖
**预估时间**: 60-90 分钟
**风险**: 低（纯新增功能，不影响现有代码）
