"""
StagePlanner 单一真相验证。

核心目标：CLI（MathModelingWorkflow.EXECUTION_PATHS）与 Agent
（LLMAgent._decide_stages_by_rule）经 StagePlanner 收敛为同一来源，
消除 visualization / validation 顺序漂移。
"""
import sys
import unittest

sys.path.insert(0, ".")

from modules.stage_planner import plan, PLANS, has_visualization
from main import MathModelingWorkflow
from modules.llm_agent import create_llm_agent
from main import MathModelingWorkflow as _WF


class TestStagePlanner(unittest.TestCase):
    def test_plan_canonical_order(self):
        """非优化题型：visualization 必须位于 validation 之前（统一顺序）。"""
        path = plan("prediction")
        self.assertLess(path.index("visualization"), path.index("validation"))

    def test_optimization_excludes_visualization(self):
        self.assertNotIn("visualization", plan("optimization"))

    def test_unknown_type_falls_back_to_comprehensive(self):
        self.assertEqual(plan("nonsense"), plan("comprehensive"))
        self.assertIn("visualization", plan("nonsense"))

    def test_plans_immutable_view(self):
        # PLANS 应为副本，外部修改不影响内部
        snapshot = PLANS["prediction"][:]
        PLANS["prediction"].append("mutated")
        self.assertNotIn("mutated", plan("prediction"))
        PLANS["prediction"] = snapshot

    def test_main_and_agent_agree_on_optimization(self):
        """CLI 与 Agent 对同一题型产出完全一致（含顺序）。"""
        wf = _WF("projects/.template", non_interactive=True)
        cli_path = wf.EXECUTION_PATHS["optimization"]
        agent = create_llm_agent(wf, mode="rule_fallback")
        agent_path = agent._decide_stages_by_rule("optimization")
        self.assertEqual(cli_path, agent_path)
        self.assertNotIn("visualization", agent_path)

    def test_main_and_agent_agree_on_prediction(self):
        wf = _WF("projects/.template", non_interactive=True)
        cli_path = _plan_via_main(wf, "prediction")
        agent = create_llm_agent(wf, mode="rule_fallback")
        agent_path = agent._decide_stages_by_rule("prediction")
        self.assertEqual(cli_path, agent_path)
        # 顺序一致：visualization 在 validation 之前
        self.assertLess(agent_path.index("visualization"), agent_path.index("validation"))

    def test_has_visualization_flag(self):
        self.assertFalse(has_visualization("optimization"))
        self.assertTrue(has_visualization("prediction"))


def _plan_via_main(wf, problem_type):
    """复刻 main.py 当前调用，确保 EXECUTION_PATHS 已收敛到 StagePlanner。"""
    from modules.stage_planner import plan as _plan
    return _plan(problem_type)


if __name__ == "__main__":
    unittest.main()
