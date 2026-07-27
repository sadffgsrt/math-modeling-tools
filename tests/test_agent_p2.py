"""
Agent P2 能力测试：HITL 关键步骤审批 / LLM 深度 critique / 多轮对话上下文。

覆盖：
1. HITL：非交互模式自动批准；注入拒绝回调则阻断执行（blocked_by_human，无工具调用）
2. LLM critique：配置 llm_call 时 method="llm"；未配置时 method="rule_based_only"；
   evaluate_result 的 evaluation_method 仍为 "rule_based"（向后兼容）
3. 多轮对话：chat() 累积 conversation；后续轮 LLM 能看到历史
4. 向后兼容：run() 仍返回全部必需字段
"""

import sys
import json
import tempfile
import shutil
from pathlib import Path
from unittest import TestCase, main as unittest_main

sys.path.insert(0, str(Path(__file__).parent.parent))


class TestAgentP2(TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.project_dir = Path(self.temp_dir) / "p2_project"

    def tearDown(self):
        import gc
        gc.collect()
        try:
            shutil.rmtree(self.temp_dir)
        except PermissionError:
            pass

    def _wf(self, non_interactive=True):
        from main import MathModelingWorkflow
        return MathModelingWorkflow(str(self.project_dir), non_interactive=non_interactive)

    # ─────────────────────────────────────────────────────
    # 1. HITL 关键步骤审批
    # ─────────────────────────────────────────────────────

    def test_hitl_auto_approve_non_interactive(self):
        """非交互模式：关键步骤自动批准，approvals 记录完整。"""
        from modules.llm_agent import run_with_llm
        wf = self._wf(non_interactive=True)
        result = run_with_llm(wf, problem_text="预测未来一周交通流量。", mode="rule_fallback")
        self.assertIn("approvals", result)
        self.assertEqual(len(result["approvals"]), 1)
        ap = result["approvals"][0]
        self.assertEqual(ap["step"], "execute_solving")
        self.assertTrue(ap["approved"])
        # 非交互模式 -> NonInteractive 自动批准
        self.assertEqual(ap["approved_by"], "NonInteractive")

    def test_hitl_human_reject_blocks_execution(self):
        """人类拒绝：关键步骤被阻断，不发起任何工具调用，记录 blocked_by_human。"""
        from modules.llm_agent import run_with_llm
        wf = self._wf(non_interactive=False)
        # 注入拒绝回调（绕过交互式 input 提示）
        wf.approval_manager.set_approval_callback(lambda op: False)
        result = run_with_llm(wf, problem_text="请做回归分析。", mode="rule_fallback")
        ap = result["approvals"][0]
        self.assertFalse(ap["approved"])
        self.assertEqual(ap["status"], "rejected")
        # 关键步骤拒绝 -> 阻断执行
        blocked = [d for d in result["decisions"] if d.get("type") == "blocked_by_human"]
        self.assertEqual(len(blocked), 1)
        self.assertEqual(len(result["tool_calls"]), 0)

    def test_hitl_approval_does_not_break_hybrid(self):
        """HITL 自动批准下 hybrid 模式仍能正常选模型并执行（无回归）。"""
        from modules.llm_agent import run_with_llm
        import numpy as np
        import pandas as pd

        # 非共线数据（规避正规方程奇异），确保回归可解
        np.random.seed(42)
        data = pd.DataFrame({
            "f1": np.random.randn(50),
            "f2": np.random.uniform(0, 10, 50),
            "target": 2 * np.random.randn(50) + 1,
        })
        dp = Path(self.temp_dir) / "d.csv"
        data.to_csv(dp, index=False)

        def mock_llm(req):
            return {"tool_calls": [{
                "id": "c1", "type": "function",
                "function": {"name": "solve_regression",
                             "arguments": json.dumps({"data_path": str(dp)})},
            }]}

        wf = self._wf(non_interactive=True)
        result = run_with_llm(wf, problem_text="请回归分析。", mode="hybrid", llm_call=mock_llm)
        self.assertTrue(result["approvals"][0]["approved"])
        self.assertGreater(len(result["tool_calls"]), 0)
        self.assertEqual(result["tool_calls"][0]["status"], "success")

    # ─────────────────────────────────────────────────────
    # 2. LLM 深度 critique
    # ─────────────────────────────────────────────────────

    def test_llm_critique_available_with_llm(self):
        """配置 llm_call 时，reflection 含 llm_critique 且 method='llm'。"""
        from modules.llm_agent import run_with_llm
        wf = self._wf(non_interactive=True)

        def mock_critique(req):
            self.assertEqual(req["role"], "reflection")
            return {"content": "方法选择合理；建议补充残差分析；存在过拟合风险。", "tool_calls": []}

        result = run_with_llm(wf, problem_text="预测问题。", mode="rule_fallback", llm_call=mock_critique)
        crit = result["reflection"]["llm_critique"]
        self.assertEqual(crit["method"], "llm")
        self.assertTrue(crit["available"])
        self.assertIn("残差", crit["critique"])

    def test_llm_critique_rule_based_only_without_llm(self):
        """未配置 llm_call 时，llm_critique method='rule_based_only'（优雅降级）。"""
        from modules.llm_agent import run_with_llm
        from modules.llm_agent import ReflectionEngine

        # evaluate_result 直接调用也应保持 evaluation_method='rule_based'
        eng = ReflectionEngine(llm_call=None)
        refl = eng.evaluate_result({"problem_type": "optimization"}, [], [])
        self.assertEqual(refl["evaluation_method"], "rule_based")

        wf = self._wf(non_interactive=True)
        result = run_with_llm(wf, problem_text="优化调度。", mode="rule_fallback")
        crit = result["reflection"]["llm_critique"]
        self.assertEqual(crit["method"], "rule_based_only")
        self.assertFalse(crit["available"])
        # 仍保留规则反思结构
        self.assertEqual(result["reflection"]["evaluation_method"], "rule_based")

    def test_llm_critique_fallback_on_exception(self):
        """llm_call 抛异常时，critique 降级为 llm_failed，主流程不受影响。"""
        from modules.llm_agent import run_with_llm
        wf = self._wf(non_interactive=True)

        def bad_llm(req):
            raise RuntimeError("LLM 服务不可用")

        result = run_with_llm(wf, problem_text="预测问题。", mode="rule_fallback", llm_call=bad_llm)
        crit = result["reflection"]["llm_critique"]
        self.assertEqual(crit["method"], "llm_failed")
        self.assertFalse(crit["available"])
        self.assertTrue(result["success"])

    # ─────────────────────────────────────────────────────
    # 3. 多轮对话上下文
    # ─────────────────────────────────────────────────────

    def test_multiturn_chat_accumulates_conversation(self):
        """chat() 多轮累积 conversation，角色交替 user/assistant。"""
        from modules.llm_agent import create_llm_agent
        wf = self._wf(non_interactive=True)
        agent = create_llm_agent(wf, mode="rule_fallback")
        r1 = agent.chat("第一轮：预测问题")
        r2 = agent.chat("第二轮：基于第一轮优化模型")
        roles = [m["role"] for m in r2["conversation"]]
        self.assertEqual(roles, ["user", "assistant", "user", "assistant"])
        # 持久化文件生成
        conv_file = wf.project_dir / "results" / "agent_conversation.json"
        self.assertTrue(conv_file.exists())

    def test_multiturn_history_visible_to_llm(self):
        """多轮下，LLM（pure_llm）能看到逐步累积的对话历史。"""
        from modules.llm_agent import create_llm_agent
        wf = self._wf(non_interactive=True)
        captured = []

        def mock_llm(req):
            # 仅统计 agent 角色调用的历史长度（reflection critique 也复用同一 llm_call，history=[]）
            if req.get("role") == "agent":
                captured.append(len(req.get("history") or []))
            return {"content": "完成"}

        agent = create_llm_agent(wf, mode="pure_llm", llm_call=mock_llm)
        agent.chat("第1轮需求")
        agent.chat("第2轮细化")
        # 第1轮 history=1（user），第2轮 history=3（user/assistant/user）
        self.assertEqual(captured, [1, 3])

    def test_run_backward_compat_fields(self):
        """run() 仍返回全部必需字段（向后兼容）。"""
        from modules.llm_agent import run_with_llm
        wf = self._wf(non_interactive=True)
        result = run_with_llm(wf, problem_text="优化调度。", mode="rule_fallback")
        for field in ["mode", "success", "problem_analysis", "decisions",
                      "tool_calls", "stages", "reflection", "approvals", "conversation"]:
            self.assertIn(field, result)


if __name__ == "__main__":
    unittest_main()
