"""公式 actor-critic 精炼器测试（rule_fallback 离线 + hybrid mock LLM）。"""
import sys
import tempfile
import json
from pathlib import Path
from unittest import TestCase, main as unittest_main

sys.path.insert(0, str(Path(__file__).parent.parent))

from modules.model_selection import FormulaRefiner, FormulaRefinement


class TestFormulaRefinerRuleFallback(TestCase):
    def setUp(self):
        self.ref = FormulaRefiner()

    def test_refine_basic(self):
        out = self.ref.refine(
            "建立区域科技成果转化能力综合评价模型并对园区排序",
            candidate_methods=["topsis", "ahp"],
            data_description="12 个园区 × 8 个指标",
            rounds=2,
        )
        self.assertIsInstance(out, FormulaRefinement)
        self.assertEqual(out.rounds, 2)
        self.assertTrue(out.final_approach.strip())
        self.assertEqual(len(out.history), 2)
        # 规则 critic 应给出达标分数（>=6）
        self.assertGreaterEqual(out.metadata["final_score"], 6.0)
        self.assertFalse(out.metadata["used_llm"])

    def test_refine_single_round(self):
        out = self.ref.refine("预测共享单车需求", rounds=1)
        self.assertEqual(len(out.history), 1)
        self.assertEqual(out.history[0].improvement, "（末轮，无需再改进）")

    def test_critique_present(self):
        out = self.ref.refine("优化应急物资调配", rounds=2)
        self.assertTrue(all(c.startswith("评分") for c in out.critiques))

    def test_save(self):
        out = self.ref.refine("综合评价", rounds=1)
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "fac.json"
            self.ref.save(out, str(p))
            data = json.loads(p.read_text(encoding="utf-8"))
            self.assertEqual(data["rounds"], 1)


class TestFormulaRefinerHybrid(TestCase):
    def _mock_llm(self, req):
        role = req.get("role")
        if role == "formula_actor":
            return {"content": f"[LLM actor] 针对「{req.get('problem_type')}」的建模思路。"}
        if role == "formula_critic":
            return {"score": 9.0, "critique": "结构完整，无明显缺陷。"}
        if role == "formula_improvement":
            return {"content": "依据批评补充变量定义。"}
        return {}

    def test_hybrid_uses_llm(self):
        ref = FormulaRefiner(llm_call=self._mock_llm)
        out = ref.refine("客户细分", candidate_methods=["kmeans"],
                         rounds=2, pure_llm=True)
        self.assertTrue(out.metadata["used_llm"])
        self.assertIn("[LLM actor]", out.final_approach)
        self.assertAlmostEqual(out.metadata["final_score"], 9.0, places=1)

    def test_hybrid_llm_failure_falls_back(self):
        def broken(req):
            raise RuntimeError("LLM unavailable")

        ref = FormulaRefiner(llm_call=broken)
        out = ref.refine("综合评价", rounds=1)
        # 降级为规则，仍可产出且分数达标
        self.assertFalse(out.metadata["used_llm"])
        self.assertTrue(out.final_approach.strip())
        self.assertGreaterEqual(out.metadata["final_score"], 6.0)


if __name__ == "__main__":
    unittest_main()
