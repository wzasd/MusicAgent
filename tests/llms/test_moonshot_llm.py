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
