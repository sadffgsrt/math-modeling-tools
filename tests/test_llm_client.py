"""
LLM 客户端测试
验证：
  - load_llm_config 配置优先级（环境变量 > .env > local > 模板）
  - LLMClient.__call__ 解析 OpenAI resp 为 {tool_calls, content}（mock openai）
  - 无 api_key 时抛明确 ValueError
不依赖真实 LLM，全 mock。
"""
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).parent.parent))


class TestLoadConfig(unittest.TestCase):
    def test_template_defaults(self):
        from modules.llm_agent.llm_client import load_llm_config
        # 清环境变量，用模板
        env_keys = ["MATHMODEL_LLM_API_KEY", "OPENAI_API_KEY",
                    "MATHMODEL_LLM_BASE_URL", "MATHMODEL_LLM_MODEL"]
        saved = {k: os.environ.pop(k, None) for k in env_keys}
        try:
            cfg = load_llm_config()
            self.assertEqual(cfg["model"], "gpt-4o-mini")
            self.assertIn(cfg["temperature"], (0.2,))  # 模板值
            self.assertIsInstance(cfg["max_tokens"], int)
        finally:
            for k, v in saved.items():
                if v is not None:
                    os.environ[k] = v

    def test_env_overrides_template(self):
        from modules.llm_agent.llm_client import load_llm_config
        saved = {"MATHMODEL_LLM_API_KEY": os.environ.get("MATHMODEL_LLM_API_KEY"),
                 "MATHMODEL_LLM_MODEL": os.environ.get("MATHMODEL_LLM_MODEL")}
        os.environ["MATHMODEL_LLM_API_KEY"] = "sk-test-env"
        os.environ["MATHMODEL_LLM_MODEL"] = "gpt-4o"
        try:
            cfg = load_llm_config()
            self.assertEqual(cfg["api_key"], "sk-test-env")
            self.assertEqual(cfg["model"], "gpt-4o")
        finally:
            for k, v in saved.items():
                if v is not None:
                    os.environ[k] = v
                elif k in os.environ:
                    del os.environ[k]


class TestLLMClientCall(unittest.TestCase):
    def test_no_key_raises(self):
        from modules.llm_agent.llm_client import LLMClient
        client = LLMClient(api_key="", model="gpt-4o-mini", tool_schemas=[])
        with self.assertRaises(ValueError) as ctx:
            client({"role": "agent", "problem_text": "x"})
        self.assertIn("API key", str(ctx.exception))

    def test_call_parses_tool_calls(self):
        from modules.llm_agent.llm_client import LLMClient
        # mock OpenAI 模块（避免真实调用）
        fake_message = MagicMock()
        fake_message.content = "已完成"
        fake_tc = MagicMock()
        fake_tc.function.name = "solve_regression"
        fake_tc.function.arguments = '{"data_path":"x.csv"}'
        fake_message.tool_calls = [fake_tc]
        fake_choice = MagicMock()
        fake_choice.message = fake_message
        fake_resp = MagicMock()
        fake_resp.choices = [fake_choice]
        fake_create = MagicMock(return_value=fake_resp)
        fake_client = MagicMock()
        fake_client.chat.completions.create = fake_create

        with patch("openai.OpenAI", return_value=fake_client):
            client = LLMClient(api_key="sk-test", model="gpt-4o-mini",
                               tool_schemas=[{"type": "function", "function": {"name": "solve_regression"}}])
            resp = client({"role": "model_selection", "problem_text": "预测问题",
                           "problem_analysis": {"problem_type": "prediction"}})
        self.assertEqual(resp["content"], "已完成")
        self.assertEqual(len(resp["tool_calls"]), 1)
        self.assertEqual(resp["tool_calls"][0]["function"]["name"], "solve_regression")
        self.assertIn("data_path", resp["tool_calls"][0]["function"]["arguments"])
        # 验证 create 被调用且带 tools
        _, kwargs = fake_create.call_args
        self.assertEqual(kwargs["model"], "gpt-4o-mini")
        self.assertIn("tools", kwargs)

    def test_call_no_tools_when_schemas_empty(self):
        from modules.llm_agent.llm_client import LLMClient
        fake_message = MagicMock()
        fake_message.content = "无工具"
        fake_message.tool_calls = None
        fake_choice = MagicMock()
        fake_choice.message = fake_message
        fake_resp = MagicMock()
        fake_resp.choices = [fake_choice]
        fake_create = MagicMock(return_value=fake_resp)
        fake_client = MagicMock()
        fake_client.chat.completions.create = fake_create

        with patch("openai.OpenAI", return_value=fake_client):
            client = LLMClient(api_key="sk-test", model="gpt-4o-mini", tool_schemas=[])
            resp = client({"role": "agent", "problem_text": "x"})
        self.assertEqual(resp["tool_calls"], [])
        self.assertEqual(resp["content"], "无工具")
        _, kwargs = fake_create.call_args
        self.assertNotIn("tools", kwargs)


class TestCreateLLMClient(unittest.TestCase):
    def test_rule_fallback_returns_none(self):
        from modules.llm_agent.llm_client import create_llm_client
        self.assertIsNone(create_llm_client(workflow=None, mode="rule_fallback"))

    def test_hybrid_returns_client_with_schemas(self):
        from modules.llm_agent.llm_client import create_llm_client
        # 无 wf 时 tool_schemas 为空但不报错
        client = create_llm_client(workflow=None, mode="hybrid")
        self.assertIsNotNone(client)
        self.assertIsInstance(client.tool_schemas, list)


if __name__ == "__main__":
    unittest.main()
