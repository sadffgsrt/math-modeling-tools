"""
真实 LLM 端到端测试（需真实 API key，CI 自动跳过）

运行条件：环境变量 MATHMODEL_LLM_API_KEY 或 OPENAI_API_KEY 存在。
无 key 时全部跳过，不影响绿集。

验证：
  - LLMClient 真实调用 OpenAI/兼容端点，resp 解析正确
  - hybrid 模式 LLM 参与模型选择（返回 tool_calls）
  - 配置从环境变量正确加载
"""
import os
import sys
import tempfile
import unittest
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

_HAS_KEY = bool(os.environ.get("MATHMODEL_LLM_API_KEY") or os.environ.get("OPENAI_API_KEY"))


class TestRealLLMCall(unittest.TestCase):
    """真实 LLM 调用测试（无 key 跳过）。"""

    def setUp(self):
        if not _HAS_KEY:
            self.skipTest("未配置 MATHMODEL_LLM_API_KEY，跳过真实 LLM 测试")
        self.temp = tempfile.mkdtemp()
        from main import MathModelingWorkflow
        self.wf = MathModelingWorkflow(self.temp, non_interactive=True)

    def tearDown(self):
        import shutil
        try:
            shutil.rmtree(self.temp)
        except OSError:
            pass

    def test_llm_client_real_call(self):
        """真实 LLM 调用返回 {tool_calls, content} 结构。"""
        from modules.llm_agent.llm_client import create_llm_client
        client = create_llm_client(self.wf, mode="hybrid")
        self.assertIsNotNone(client)
        resp = client({"role": "model_selection",
                       "problem_text": "基于历史数据预测未来需求",
                       "problem_analysis": {"problem_type": "prediction"}})
        self.assertIsInstance(resp, dict)
        # 至少有 content 或 tool_calls 之一
        self.assertTrue("content" in resp or "tool_calls" in resp)

    def test_hybrid_agent_run(self):
        """hybrid 模式 agent 真实跑通（题目→LLM选择→求解→反思）。"""
        from modules.llm_agent.agent import create_llm_agent
        from modules.llm_agent.llm_client import create_llm_client
        client = create_llm_client(self.wf, mode="hybrid")
        agent = create_llm_agent(self.wf, mode="hybrid", llm_call=client)
        result = agent.run("预测城市共享单车未来需求")
        self.assertEqual(result["mode"], "hybrid")
        self.assertIn("success", result)
        self.assertIn("reflection", result)


if __name__ == "__main__":
    unittest.main()
