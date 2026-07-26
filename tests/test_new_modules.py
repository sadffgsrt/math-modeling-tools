"""
数学建模竞赛工作流 - 新增模块测试
测试 v3.3 新增 5 个模块的基本功能
"""

import sys
import numpy as np
from pathlib import Path
from unittest import TestCase, main as unittest_main

# 添加父目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))


class TestNewModules(TestCase):
    """测试 v3.3 新增 5 个模块的基本功能"""

    def test_log_aggregation(self):
        """日志聚合：解析日志文件并生成摘要"""
        from modules.log_aggregation import LogAggregator
        import tempfile
        log_content = (
            "2026-06-28 10:00:00 [INFO] 开始执行阶段: problem_analysis\n"
            "2026-06-28 10:00:05 [INFO] 阶段 problem_analysis 执行完成! 耗时: 5.0秒\n"
            "2026-06-28 10:00:06 [WARNING] 缓存读取失败\n"
            "2026-06-28 10:00:07 [ERROR] 阶段 model_solving 执行失败: ValueError\n"
        )
        with tempfile.NamedTemporaryFile(mode="w", suffix=".log",
                                          delete=False, encoding="utf-8") as f:
            f.write(log_content)
            f.flush()
            from pathlib import Path
            summary = LogAggregator().aggregate(Path(f.name))
        self.assertEqual(summary.total_lines, 4)
        self.assertEqual(summary.level_counts.get("ERROR"), 1)
        self.assertEqual(summary.level_counts.get("WARNING"), 1)
        self.assertEqual(len(summary.stage_events), 1)
        self.assertEqual(summary.stage_events[0]["duration"], 5.0)
        self.assertEqual(summary.status, "failed")  # 含执行失败 ERROR

    def test_result_export(self):
        """结果导出：导出为 CSV/JSON/Markdown"""
        from modules.result_export import ResultExporter
        import tempfile, json
        from pathlib import Path
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            # 先写入一个测试 JSON 结果文件
            (tmp_path / "test_result.json").write_text(
                json.dumps({"model": "ridge", "r2": 0.85, "rmse": 0.15}),
                encoding="utf-8"
            )
            results = ResultExporter().export_all(
                tmp_path, tmp_path / "export",
                formats=["json", "csv", "markdown"]
            )
            formats_seen = {r.format for r in results if r.status == "success"}
            self.assertIn("json", formats_seen)
            self.assertIn("csv", formats_seen)

    def test_model_interpretation(self):
        """模型解释：特征重要性（SHAP 不可用时降级）"""
        from modules.model_interpretation import ModelInterpreter
        from sklearn.ensemble import RandomForestRegressor
        X = np.random.randn(30, 4)
        y = X[:, 0] * 2 + np.random.randn(30) * 0.1
        model = RandomForestRegressor(n_estimators=10, random_state=42).fit(X, y)
        result = ModelInterpreter().interpret(
            model, X, y, feature_names=["a", "b", "c", "d"]
        )
        self.assertIn(result.status, ("success", "degraded"))
        self.assertEqual(len(result.feature_importance), 4)

    def test_hyperparameter_tuning(self):
        """超参调优：网格搜索"""
        from modules.hyperparameter_tuning import HyperparameterTuner
        from sklearn.linear_model import Ridge
        X = np.random.randn(30, 3)
        y = X[:, 0] + np.random.randn(30) * 0.1
        tuner = HyperparameterTuner(config={"cv_folds": 3})
        result = tuner.tune(
            Ridge(), {"alpha": [0.1, 1.0, 10.0]}, X, y, method="grid"
        )
        self.assertEqual(result.status, "success")
        self.assertIn("alpha", result.best_params)
        self.assertEqual(result.n_trials, 3)

    def test_model_comparison(self):
        """模型对比：多模型性能对比"""
        from modules.model_comparison import ModelComparator
        from sklearn.linear_model import LinearRegression, Ridge
        X = np.random.randn(40, 3)
        y = X[:, 0] + np.random.randn(40) * 0.1
        comparator = ModelComparator(config={"cv_folds": 3, "scoring": ["r2"]})
        result = comparator.compare(
            {"linear": LinearRegression(), "ridge": Ridge(alpha=0.1)},
            X, y, task_type="regression"
        )
        self.assertEqual(result.status, "success")
        self.assertEqual(len(result.models), 2)
        self.assertIn(result.best_model, ("linear", "ridge"))
        self.assertGreaterEqual(result.best_score, 0.0)

    def test_solving_dispatcher_import(self):
        """验证 SolvingDispatcher 可正常导入（薄编排层重构）"""
        from modules.model_solving_dispatcher import SolvingDispatcher
        self.assertTrue(hasattr(SolvingDispatcher, "dispatch"))


if __name__ == "__main__":
    unittest_main()
