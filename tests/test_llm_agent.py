"""
数学建模竞赛工作流 - LLM Agent 测试
验证 3 种决策模式：pure_llm / hybrid / rule_fallback
"""

import sys
import json
import tempfile
import shutil
import numpy as np
import pandas as pd
from pathlib import Path
from unittest import TestCase, main as unittest_main

# 添加父目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))


class TestLLMAgent(TestCase):
    """步骤 4：LLM Agent 测试
    验证 3 种决策模式：pure_llm / hybrid / rule_fallback
    """

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.project_dir = Path(self.temp_dir) / "test_llm_agent_project"
        # 准备题目文件
        self.problem_text = """
        问题一：生产调度优化问题
        某工厂有若干加工工位，需要调度作业顺序。
        设作业当前位置为x，需要访问的工位为y_i。
        约束条件：
        1. 设备只能沿轨道单向移动
        2. 每个工位同一时间只能被一台设备访问
        目标：最小化总完成时间
        """
        self.problem_file = Path(self.temp_dir) / "problem.txt"
        self.problem_file.write_text(self.problem_text, encoding="utf-8")

    def tearDown(self):
        import gc
        gc.collect()
        try:
            shutil.rmtree(self.temp_dir)
        except PermissionError:
            pass

    def _make_workflow(self):
        """创建非交互模式工作流"""
        from main import MathModelingWorkflow
        return MathModelingWorkflow(str(self.project_dir), non_interactive=True)

    def _make_mock_llm(self, tool_name: str = "solve_regression",
                        arguments: dict = None):
        """
        创建 mock LLM 调用函数。
        模拟 LLM 通过 tool-calling 返回决策。
        """
        if arguments is None:
            arguments = {"data_path": str(self.temp_dir / "mock_data.csv")}

        call_count = [0]

        def mock_llm(request: dict) -> dict:
            call_count[0] += 1
            # 第一次调用返回 tool_call，第二次返回文本（结束）
            if call_count[0] == 1:
                return {
                    "tool_calls": [{
                        "id": f"call_{call_count[0]}",
                        "type": "function",
                        "function": {
                            "name": tool_name,
                            "arguments": json.dumps(arguments),
                        }
                    }]
                }
            else:
                return {"content": "决策完成，已选择最优模型。"}

        return mock_llm

    # ─── 模式校验测试 ───

    def test_invalid_mode_raises(self):
        """无效模式抛 ValueError"""
        from modules.llm_agent import create_llm_agent
        workflow = self._make_workflow()
        with self.assertRaises(ValueError):
            create_llm_agent(workflow, mode="invalid_mode")

    def test_pure_llm_without_llm_call_degrades(self):
        """pure_llm 模式无 llm_call 自动降级到 rule_fallback"""
        from modules.llm_agent import create_llm_agent
        workflow = self._make_workflow()
        agent = create_llm_agent(workflow, mode="pure_llm", llm_call=None)
        self.assertEqual(agent.mode, "rule_fallback")

    def test_hybrid_without_llm_call_degrades(self):
        """hybrid 模式无 llm_call 自动降级到 rule_fallback"""
        from modules.llm_agent import create_llm_agent
        workflow = self._make_workflow()
        agent = create_llm_agent(workflow, mode="hybrid", llm_call=None)
        self.assertEqual(agent.mode, "rule_fallback")

    # ─── rule_fallback 模式测试 ───

    def test_rule_fallback_returns_result(self):
        """rule_fallback 模式返回结果结构正确"""
        from modules.llm_agent import run_with_llm
        workflow = self._make_workflow()
        result = run_with_llm(workflow, problem_text=self.problem_text, mode="rule_fallback")
        self.assertEqual(result["mode"], "rule_fallback")
        self.assertIn("stages", result)
        self.assertIn("decisions", result)
        self.assertTrue(len(result["decisions"]) > 0)

    def test_rule_fallback_decides_stages(self):
        """rule_fallback 根据 problem_type 决策阶段序列"""
        from modules.llm_agent import run_with_llm
        workflow = self._make_workflow()
        result = run_with_llm(workflow, problem_text=self.problem_text, mode="rule_fallback")
        # 问题文本是优化类，应有 data_processing/model_solving/validation/paper_writing
        decisions = result["decisions"]
        rule_decision = [d for d in decisions if d.get("type") == "rule_based"][0]
        self.assertIn("data_processing", rule_decision["execution_path"])
        self.assertIn("model_solving", rule_decision["execution_path"])

    def test_rule_fallback_optimization_skips_visualization(self):
        """优化类问题在 rule_fallback 下跳过 visualization"""
        from modules.llm_agent import LLMAgent
        workflow = self._make_workflow()
        agent = LLMAgent(workflow, mode="rule_fallback")
        path = agent._decide_stages_by_rule("optimization")
        self.assertNotIn("visualization", path)
        self.assertIn("validation", path)

    def test_rule_fallback_prediction_includes_visualization(self):
        """预测类问题在 rule_fallback 下包含 visualization"""
        from modules.llm_agent import LLMAgent
        workflow = self._make_workflow()
        agent = LLMAgent(workflow, mode="rule_fallback")
        path = agent._decide_stages_by_rule("prediction")
        self.assertIn("visualization", path)

    # ─── hybrid 模式测试 ───

    def test_hybrid_mode_with_mock_llm(self):
        """hybrid 模式使用 mock LLM 选择模型"""
        from modules.llm_agent import run_with_llm
        import pandas as pd

        # 准备数据文件
        np.random.seed(42)
        data = pd.DataFrame({
            'feature_1': np.random.randn(50),
            'feature_2': np.random.uniform(0, 10, 50),
            'target': 2 * np.random.randn(50) + 1,
        })
        data_path = Path(self.temp_dir) / "mock_data.csv"
        data.to_csv(data_path, index=False)

        # 创建 mock LLM
        mock_llm = self._make_mock_llm(
            tool_name="solve_regression",
            arguments={"data_path": str(data_path)},
        )

        workflow = self._make_workflow()
        result = run_with_llm(
            workflow,
            problem_text=self.problem_text,
            mode="hybrid",
            llm_call=mock_llm,
        )

        self.assertEqual(result["mode"], "hybrid")
        self.assertTrue(len(result["decisions"]) > 0)
        # 应有模型选择决策
        model_decisions = [d for d in result["decisions"] if d.get("type") == "model_selection"]
        self.assertGreater(len(model_decisions), 0)

    def test_hybrid_llm_failure_falls_back_to_rule(self):
        """hybrid 模式 LLM 失败时退化到规则"""
        from modules.llm_agent import run_with_llm

        def failing_llm(request):
            raise RuntimeError("LLM 服务不可用")

        workflow = self._make_workflow()
        result = run_with_llm(
            workflow,
            problem_text=self.problem_text,
            mode="hybrid",
            llm_call=failing_llm,
        )

        self.assertEqual(result["mode"], "hybrid")
        # 即使 LLM 失败，工作流应继续
        self.assertIn("stages", result)

    # ─── pure_llm 模式测试 ───

    def test_pure_llm_with_mock_llm(self):
        """pure_llm 模式使用 mock LLM 自主决策"""
        from modules.llm_agent import run_with_llm
        import pandas as pd

        # 准备数据文件
        np.random.seed(42)
        data = pd.DataFrame({
            'feature_1': np.random.randn(50),
            'feature_2': np.random.uniform(0, 10, 50),
            'target': 2 * np.random.randn(50) + 1,
        })
        data_path = Path(self.temp_dir) / "mock_data.csv"
        data.to_csv(data_path, index=False)

        mock_llm = self._make_mock_llm(
            tool_name="solve_regression",
            arguments={"data_path": str(data_path)},
        )

        workflow = self._make_workflow()
        result = run_with_llm(
            workflow,
            problem_text=self.problem_text,
            mode="pure_llm",
            llm_call=mock_llm,
        )

        self.assertEqual(result["mode"], "pure_llm")
        # pure_llm 模式应有 tool_calls
        self.assertGreater(len(result["tool_calls"]), 0)
        self.assertEqual(result["tool_calls"][0]["tool_name"], "solve_regression")

    def test_pure_llm_max_rounds_limit(self):
        """pure_llm 模式有最大轮次限制（10）"""
        from modules.llm_agent import LLMAgent

        call_count = [0]

        def always_tool_call(request):
            # 仅统计 agent 主循环的调用（反思 critique 也会复用同一 llm_call，单独归属）
            if request.get("role") == "agent":
                call_count[0] += 1
            return {
                "tool_calls": [{
                    "id": f"call_{call_count[0]}",
                    "type": "function",
                    "function": {
                        "name": "solve_regression",
                        "arguments": json.dumps({"data_path": "nonexistent.csv"}),
                    }
                }]
            }

        workflow = self._make_workflow()
        agent = LLMAgent(workflow, mode="pure_llm", llm_call=always_tool_call)
        result = agent.run(problem_text=self.problem_text)

        # 主循环应在 10 轮内停止
        self.assertLessEqual(call_count[0], 10)

    # ─── 题目输入测试 ───

    def test_run_with_problem_file(self):
        """通过文件路径输入题目"""
        from modules.llm_agent import run_with_llm
        workflow = self._make_workflow()
        result = run_with_llm(
            workflow,
            problem_file=str(self.problem_file),
            mode="rule_fallback",
        )
        self.assertIn("problem_analysis", result)

    def test_run_without_problem_raises(self):
        """无题目输入抛 ValueError"""
        from modules.llm_agent import run_with_llm
        workflow = self._make_workflow()
        with self.assertRaises(ValueError):
            run_with_llm(workflow, mode="rule_fallback")

    # ─── 结果结构测试 ───

    def test_result_has_required_fields(self):
        """结果包含必需字段"""
        from modules.llm_agent import run_with_llm
        workflow = self._make_workflow()
        result = run_with_llm(workflow, problem_text=self.problem_text, mode="rule_fallback")
        for field in ["mode", "stages", "decisions", "tool_calls", "success"]:
            self.assertIn(field, result)

    def test_decision_recorded(self):
        """决策被记录到 decisions 字段"""
        from modules.llm_agent import run_with_llm
        workflow = self._make_workflow()
        result = run_with_llm(workflow, problem_text=self.problem_text, mode="rule_fallback")
        self.assertGreater(len(result["decisions"]), 0)
        decision = result["decisions"][0]
        self.assertIn("type", decision)


if __name__ == "__main__":
    unittest_main()
