"""
可视化用户偏好驱动生成测试
验证：
  - pref_to_chart_types 的确定性关键词映射
  - VisualizationOps.generate 的 chart_types / user_pref / max_charts 行为
（模仿 MM-Agent create_charts 的 user_prompt/chart_num 交互意图，确定性实现）
"""
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


class TestPrefMapping(unittest.TestCase):
    def test_none_on_empty(self):
        from modules.visualization.visualization_ops import pref_to_chart_types
        self.assertIsNone(pref_to_chart_types(""))
        self.assertIsNone(pref_to_chart_types(None))

    def test_keyword_hit(self):
        from modules.visualization.visualization_ops import pref_to_chart_types
        ids = pref_to_chart_types("我想看预测趋势和特征重要性")
        self.assertIn("pred_vs_actual", ids)
        self.assertIn("feature_importance", ids)

    def test_no_hit_returns_none(self):
        from modules.visualization.visualization_ops import pref_to_chart_types
        self.assertIsNone(pref_to_chart_types("完全无关的描述xyz"))


class TestGenerateChartSelection(unittest.TestCase):
    def setUp(self):
        self.out = tempfile.mkdtemp(prefix="vizpref_")

    def tearDown(self):
        import shutil
        try:
            shutil.rmtree(self.out)
        except OSError:  # safe-delete 拦截时忽略，临时目录由系统回收
            pass

    def _fake(self):
        import numpy as np
        import pandas as pd
        np.random.seed(0)
        n = 60
        data = pd.DataFrame({f"x{i}": np.random.randn(n) for i in range(4)})
        y_true = np.random.randn(n)
        y_pred = y_true + np.random.randn(n) * 0.3
        return data, y_true, y_pred

    def test_chart_types_filter(self):
        from modules.visualization.visualization_ops import VisualizationOps
        data, y_true, y_pred = self._fake()
        res = VisualizationOps(output_dir=self.out).generate(
            data=data, y_true=y_true, y_pred=y_pred,
            feature_names=["x0", "x1", "x2", "x3"],
            feature_importance={"x0": 0.4, "x1": 0.3, "x2": 0.2, "x3": 0.1},
            chart_types=["pred_vs_actual", "feature_importance"])
        ids = {f["id"] for f in res.figures}
        self.assertEqual(ids, {"pred_vs_actual", "feature_importance"})

    def test_user_pref_mapping(self):
        from modules.visualization.visualization_ops import VisualizationOps
        data, y_true, y_pred = self._fake()
        res = VisualizationOps(output_dir=self.out).generate(
            data=data, y_true=y_true, y_pred=y_pred,
            feature_names=["x0", "x1", "x2", "x3"],
            user_pref="预测趋势")
        ids = {f["id"] for f in res.figures}
        self.assertIn("pred_vs_actual", ids)
        self.assertIn("error_over_samples", ids)

    def test_max_charts(self):
        from modules.visualization.visualization_ops import VisualizationOps
        data, y_true, y_pred = self._fake()
        res = VisualizationOps(output_dir=self.out).generate(
            data=data, y_true=y_true, y_pred=y_pred,
            feature_names=["x0", "x1", "x2", "x3"],
            max_charts=2)
        self.assertLessEqual(len(res.figures), 2)


if __name__ == "__main__":
    unittest.main()
