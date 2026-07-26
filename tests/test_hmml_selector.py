"""HMML 层次化方法库选择器测试（离线确定性 + 可选 LLM critic）。"""
import sys
from pathlib import Path
from unittest import TestCase, main as unittest_main

sys.path.insert(0, str(Path(__file__).parent.parent))

from modules.model_selection import HierarchicalMethodSelector, HierarchicalSelection


class TestHierarchicalSelector(TestCase):
    def setUp(self):
        self.sel = HierarchicalMethodSelector()

    def test_retrieve_evaluation(self):
        sel = self.sel.retrieve(
            "建立区域科技成果转化能力综合评价模型并对园区排序",
            data_features={"is_evaluation": True},
            top_k=5,
        )
        self.assertIsInstance(sel, HierarchicalSelection)
        self.assertTrue(len(sel.ranked_methods) > 0)
        # 评价类问题应召回评价相关方法（如 topsis/ahp）
        model_ids = {r.model_id for r in sel.ranked_methods}
        self.assertTrue(model_ids & {"topsis", "ahp", "entropy_weight"})

    def test_retrieve_prediction(self):
        sel = self.sel.retrieve(
            "基于历史数据预测城市共享单车未来需求",
            data_features={"has_time_series": True},
            top_k=5,
        )
        model_ids = {r.model_id for r in sel.ranked_methods}
        self.assertTrue(model_ids & {"arima", "linear_regression", "exponential_smoothing", "prophet"})

    def test_suggest_model_ids(self):
        sel = self.sel.retrieve("应急物资储备库选址与调配优化",
                                data_features={"is_optimization": True}, top_k=6)
        ids = self.sel.suggest_model_ids(sel)
        self.assertTrue(all(isinstance(i, str) and i for i in ids))

    def test_get_method_tree(self):
        tree = self.sel.get_method_tree()
        self.assertTrue(len(tree) > 0)
        # 每个 domain 含 subdomain，subdomain 含 method
        self.assertTrue(len(tree[0]["children"]) > 0)
        self.assertTrue(len(tree[0]["children"][0]["children"]) > 0)

    def test_optional_llm_critic(self):
        # 提供给所有候选一个固定 critic 分数，验证均值融合不报错且排序稳定
        def dummy_critic(desc, methods):
            return [0.7] * len(methods)

        sel = self.sel.retrieve("客户细分与精准营销", top_k=4, llm_critic=dummy_critic)
        self.assertTrue(sel.metadata["used_llm_critic"])
        self.assertTrue(len(sel.ranked_methods) > 0)

    def test_save(self):
        import tempfile, json
        sel = self.sel.retrieve("综合评价", data_features={"is_evaluation": True}, top_k=3)
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "out.json"
            self.sel.save(sel, str(p))
            data = json.loads(p.read_text(encoding="utf-8"))
            self.assertEqual(len(data["ranked_methods"]), 3)


if __name__ == "__main__":
    unittest_main()
