# 多 LLM 提供商支持设计文档

**创建日期**: 2026-03-26
**主题**: 添加 Kimi (Moonshot AI) LLM 提供商支持
**状态**: 待实现

---

## 1. 概述

### 1.1 目标

在现有音乐推荐 Agent 中增加对 Kimi (Moonshot AI) LLM 的支持，实现：

1. **多提供商并行**: 同时支持 SiliconFlow 和 Kimi (Moonshot AI)
2. **运行时切换**: 通过配置项 `DEFAULT_LLM_PROVIDER` 灵活切换默认 LLM
3. **向后兼容**: 现有代码无需改动即可正常工作
4. **统一接口**: 所有 LLM 提供商遵循相同的 `BaseLLM` 接口

### 1.2 背景

当前系统仅支持 SiliconFlow 作为 LLM 提供商，使用 OpenAI 兼容 API 格式。Kimi (Moonshot AI) 同样提供 OpenAI 兼容的 API，但配置项和模型名称不同。本设计将引入配置驱动的多提供商架构。

### 1.3 设计原则

- **最小侵入性**: 不破坏现有 `SiliconFlowLLM` 实现
- **配置驱动**: 通过 `setting.json` 控制提供商选择和参数
- **工厂模式**: 提供统一的 `get_llm()` 入口
- **显式优于隐式**: 提供商名称清晰可读（`siliconflow`, `moonshot`）

---

## 2. 架构设计

### 2.1 系统架构图

```
┌─────────────────────────────────────────────────────────────────┐
│                          用户代码层                              │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  llm = get_llm()  # 使用 DEFAULT_LLM_PROVIDER          │   │
│  │  llm = get_llm("moonshot")  # 显式指定                │   │
│  └─────────────────────────────────────────────────────────┘   │
└───────────────────────────┬─────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────────┐
│                        LLM 工厂层                               │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  def get_llm(provider=None):                            │   │
│  │      provider = provider or DEFAULT_LLM_PROVIDER        │   │
│  │      if provider == "moonshot":                         │   │
│  │          return MoonshotLLM(...)                        │   │
│  │      elif provider == "siliconflow":                    │   │
│  │          return SiliconFlowLLM(...)                     │   │
│  │      else: raise ValueError(...)                        │   │
│  └─────────────────────────────────────────────────────────┘   │
└───────────────────────────┬─────────────────────────────────────┘
                            ↓
        ┌───────────────────┴───────────────────┐
        ↓                                       ↓
┌───────────────────────┐           ┌───────────────────────┐
│   SiliconFlowLLM      │           │    MoonshotLLM        │
│  (已有，保持不变)      │           │      (新增)           │
├───────────────────────┤           ├───────────────────────┤
│  api_key: str         │           │  api_key: str         │
│  base_url: str        │           │  base_url: str        │
│  default_model: str   │           │  default_model: str   │
│  client: OpenAI       │           │  client: OpenAI       │
├───────────────────────┤           ├───────────────────────┤
│  invoke()             │           │  invoke()             │
│  invoke_text()        │           │  invoke_text()        │
│  ainvoke()            │           │  ainvoke()            │
│  get_model_info()     │           │  get_model_info()     │
└───────────┬───────────┘           └───────────┬───────────┘
            ↓                                   ↓
┌───────────────────────┐           ┌───────────────────────┐
│  https://api.silicon  │           │  https://api.moonshot │
│     flow.cn/v1        │           │       .cn/v1          │
└───────────────────────┘           └───────────────────────┘
```

### 2.2 类图

```
┌─────────────────┐
│   BaseLLM       │
├─────────────────┤
│ + invoke()      │
│ + invoke_text() │
│ + ainvoke()     │
└────────┬────────┘
         │
    ┌────┴────┐
    ↓         ↓
┌──────────┐  ┌──────────┐
│SiliconFlow│  │ Moonshot │
│   LLM    │  │   LLM    │
└──────────┘  └──────────┘
```

---

## 3. 配置设计

### 3.1 `setting.json` 配置项

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

### 3.2 配置项说明

| 配置项 | 类型 | 必填 | 默认值 | 说明 |
|--------|------|------|--------|------|
| `DEFAULT_LLM_PROVIDER` | string | 否 | `siliconflow` | 默认 LLM 提供商，可选 `siliconflow` 或 `moonshot` |
| `SILICONFLOW_API_KEY` | string | 条件 | - | SiliconFlow API Key（使用 SiliconFlow 时必填） |
| `SILICONFLOW_BASE_URL` | string | 否 | `https://api.siliconflow.cn/v1` | SiliconFlow API 地址 |
| `SILICONFLOW_CHAT_MODEL` | string | 否 | `deepseek-ai/DeepSeek-V3` | SiliconFlow 聊天模型 |
| `SILICONFLOW_EMBED_MODEL` | string | 否 | `BAAI/bge-m3` | SiliconFlow Embedding 模型 |
| `MOONSHOT_API_KEY` | string | 条件 | - | Moonshot API Key（使用 Kimi 时必填） |
| `MOONSHOT_BASE_URL` | string | 否 | `https://api.moonshot.cn/v1` | Moonshot API 地址 |
| `MOONSHOT_CHAT_MODEL` | string | 否 | `kimi-k2.5` | Moonshot 聊天模型 |

### 3.3 环境变量映射

`config/settings_loader.py` 需添加以下环境变量映射：

| JSON Key | 环境变量名 |
|----------|-----------|
| `DEFAULT_LLM_PROVIDER` | `DEFAULT_LLM_PROVIDER` |
| `MOONSHOT_API_KEY` | `MOONSHOT_API_KEY` |
| `MOONSHOT_BASE_URL` | `MOONSHOT_BASE_URL` |
| `MOONSHOT_CHAT_MODEL` | `MOONSHOT_CHAT_MODEL` |

---

## 4. 接口设计

### 4.1 LLM 工厂函数

**文件**: `llms/__init__.py`

```python
def get_llm(provider: Optional[str] = None) -> BaseLLM:
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
```

### 4.2 MoonshotLLM 类

**文件**: `llms/moonshot_llm.py`

```python
class MoonshotLLM(BaseLLM):
    """Moonshot AI (Kimi) LLM 实现类"""

    def __init__(self, api_key: Optional[str] = None, model_name: Optional[str] = None):
        """
        初始化 Moonshot 客户端

        Args:
            api_key: Moonshot API Key，如果不提供则从环境变量或 setting.json 读取
            model_name: 模型名称，默认使用 kimi-k2.5
        """

    def invoke(self, system_prompt: str, user_prompt: str, **kwargs) -> Dict[str, Any]:
        """调用 Moonshot API 生成回复"""

    def invoke_text(self, system_prompt: str, user_prompt: str, **kwargs) -> str:
        """只返回文本内容的便捷方法"""

    async def ainvoke(self, prompt: str, **kwargs) -> str:
        """异步调用 LLM（兼容 LangChain 接口）"""

    def get_model_info(self) -> Dict[str, Any]:
        """获取当前模型信息"""
```

### 4.3 使用示例

```python
# 示例 1: 使用默认提供商
from llms import get_llm

llm = get_llm()
result = llm.invoke_text("你是一个音乐推荐助手", "推荐一些轻松的音乐")

# 示例 2: 显式指定 Kimi
llm = get_llm("moonshot")
result = llm.invoke_text("你是一个音乐推荐助手", "推荐一些轻松的音乐")

# 示例 3: 获取模型信息
info = llm.get_model_info()
# 返回: {"provider": "Moonshot", "model": "kimi-k2.5", "api_base": "https://api.moonshot.cn/v1"}

# 示例 4: 异步调用
result = await llm.ainvoke("推荐一些适合工作的音乐")
```

---

## 5. 数据流

### 5.1 初始化流程

```
get_llm("moonshot")
    │
    ├─→ 读取 setting.json
    │   ├─→ DEFAULT_LLM_PROVIDER (备用)
    │   ├─→ MOONSHOT_API_KEY
    │   ├─→ MOONSHOT_BASE_URL
    │   └─→ MOONSHOT_CHAT_MODEL
    │
    ├─→ 设置环境变量 (settings_loader)
    │
    └─→ 实例化 MoonshotLLM
        ├─→ 读取 API Key (环境变量 → setting.json)
        ├─→ 读取 Base URL (环境变量 → setting.json → 默认值)
        ├─→ 读取 Model (环境变量 → setting.json → 默认值)
        └─→ 创建 OpenAI Client
```

### 5.2 调用流程

```
llm.invoke_text(system_prompt, user_prompt)
    │
    ├─→ 构建 messages 列表
    │   ├─→ {"role": "system", "content": system_prompt}
    │   └─→ {"role": "user", "content": user_prompt}
    │
    ├─→ 设置调用参数
    │   ├─→ model: "kimi-k2.5"
    │   ├─→ temperature: 0.7 (默认)
    │   └─→ max_tokens: 4000 (默认)
    │
    ├─→ 调用 OpenAI Client
    │   POST https://api.moonshot.cn/v1/chat/completions
    │
    └─→ 解析响应
        ├─→ 提取 content
        ├─→ 提取 token 使用量
        └─→ 返回 Dict[str, Any]
```

---

## 6. 错误处理

### 6.1 可能的错误场景

| 场景 | 错误类型 | 处理策略 |
|------|----------|----------|
| 未设置 MOONSHOT_API_KEY | `ValueError` | 提示用户配置 API Key |
| 无效的提供商名称 | `ValueError` | 列出支持的提供商 |
| API 调用失败 | `APIError` | 向上抛出，由调用方处理 |
| 网络超时 | `TimeoutError` | 重试 3 次后抛出 |

### 6.2 错误信息示例

```python
# API Key 未找到
ValueError: Moonshot API Key 未找到！请设置 MOONSHOT_API_KEY 环境变量或在 setting.json 中配置

# 无效的提供商
ValueError: 不支持的 LLM 提供商: 'openai'。支持的提供商: siliconflow, moonshot
```

---

## 7. 测试策略

### 7.1 单元测试

```python
# 测试 MoonshotLLM 初始化
def test_moonshot_llm_init_with_api_key():
    llm = MoonshotLLM(api_key="test-key", model_name="kimi-k2.5")
    assert llm.api_key == "test-key"
    assert llm.default_model == "kimi-k2.5"

# 测试工厂函数
def test_get_llm_moonshot():
    llm = get_llm("moonshot")
    assert isinstance(llm, MoonshotLLM)
    assert llm.get_model_info()["provider"] == "Moonshot"

# 测试默认提供商回退
def test_get_llm_default_fallback():
    # 当 DEFAULT_LLM_PROVIDER 未设置时，应使用 siliconflow
    llm = get_llm()
    assert isinstance(llm, SiliconFlowLLM)
```

### 7.2 集成测试

```python
# 测试实际 API 调用（需要有效 API Key）
async def test_moonshot_api_call():
    llm = get_llm("moonshot")
    result = llm.invoke_text("你是一个助手", "你好")
    assert len(result) > 0
```

---

## 8. 实现清单

### 8.1 文件变更列表

| 文件路径 | 操作 | 优先级 | 说明 |
|----------|------|--------|------|
| `llms/moonshot_llm.py` | 新增 | P0 | MoonshotLLM 类实现 |
| `llms/__init__.py` | 修改 | P0 | 添加 get_llm() 工厂函数 |
| `config/settings_loader.py` | 修改 | P0 | 添加 Moonshot 环境变量映射 |
| `setting.json` | 用户修改 | P1 | 添加 Moonshot 配置项 |

### 8.2 代码行数估算

- `llms/moonshot_llm.py`: ~150 行（参考 SiliconFlowLLM）
- `llms/__init__.py` 修改: ~30 行
- `config/settings_loader.py` 修改: ~10 行
- **总计**: ~190 行代码

---

## 9. 向后兼容性

### 9.1 兼容保证

1. **现有代码**: 直接实例化 `SiliconFlowLLM()` 的代码完全不受影响
2. **配置文件**: 未添加新配置项时系统仍使用 SiliconFlow
3. **默认行为**: 未设置 `DEFAULT_LLM_PROVIDER` 时默认为 `siliconflow`

### 9.2 迁移指南

**对于现有用户**:

1. 无需任何改动即可继续使用 SiliconFlow
2. 如需切换到 Kimi:
   - 在 `setting.json` 中添加 Moonshot 配置项
   - 设置 `DEFAULT_LLM_PROVIDER` 为 `"moonshot"`

---

## 10. 参考

### 10.1 Kimi API 文档

- 官方文档: https://platform.moonshot.cn/
- API 端点: `https://api.moonshot.cn/v1`
- 模型名称: `kimi-k2.5`

### 10.2 相关代码文件

- `llms/siliconflow_llm.py`: 参考实现
- `llms/base.py`: 基类定义
- `config/settings_loader.py`: 配置加载逻辑

---

## 11. 决策记录

| 决策 | 选择 | 理由 |
|------|------|------|
| 提供商切换方式 | 配置驱动 | 简单直观，无需代码改动 |
| 工厂函数位置 | `llms/__init__.py` | 最自然的导入路径 |
| 配置前缀 | `MOONSHOT_*` | 与 `SILICONFLOW_*` 保持一致 |
| 默认提供商 | `siliconflow` | 向后兼容 |
| 是否支持 Embedding | 否（当前版本） | Kimi 不提供 Embedding API，继续使用 SiliconFlow/Ollama |

---

**文档版本**: 1.0
**最后更新**: 2026-03-26
