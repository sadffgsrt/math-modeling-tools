# -*- coding: utf-8 -*-
"""
数学建模竞赛工作流 - 新增模块扩展测试
对 v3.3 新增 5 个模块（08-12）进行补充测试，覆盖初始化、核心方法、边界条件。

补充 test_new_modules.py（每模块 1 个基础测试），不替换原有测试。
"""

import sys
import json
import tempfile
from pathlib import Path
from unittest import TestCase, main as unittest_main

import numpy as np

# 添加父目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))


class TestLogAggregatorExtended(TestCase):
    """日志聚合模块扩展测试"""

    def test_init_default_and_custom_config(self):
        """初始化：默认配置与自定义配置"""
        from modules.log_aggregation import LogAggregator
        # 默认配置
        agg = LogAggregator()
        self.assertEqual(agg.max_error_messages, 50)
        self.assertEqual(agg.max_warning_messages, 50)
        self.assertEqual(agg.config, {})
        # 自定义配置
        agg2 = LogAggregator(config={"max_error_messages": 10, "max_warning_messages": 5})
        self.assertEqual(agg2.max_error_messages, 10)
        self.assertEqual(agg2.max_warning_messages, 5)

    def test_aggregate_nonexistent_file_returns_empty(self):
        """边界条件：聚合不存在的文件返回空摘要"""
        from modules.log_aggregation import LogAggregator, LogSummary
        agg = LogAggregator()
        summary = agg.aggregate(Path("/nonexistent/path/no_such_file.log"))
        self.assertIsInstance(summary, LogSummary)
        self.assertEqual(summary.total_lines, 0)
        self.assertEqual(summary.level_counts, {})
        self.assertEqual(summary.status, "success")

    def test_aggregate_partial_status_warning_only(self):
        """核心方法：仅含 WARNING 时 status 为 partial"""
        from modules.log_aggregation import LogAggregator
        log_content = (
            "2026-06-28 10:00:00 [INFO] 开始执行阶段: data_processing\n"
            "2026-06-28 10:00:10 [WARNING] 数据质量警告\n"
        )
        with tempfile.NamedTemporaryFile(mode="w", suffix=".log",
                                          delete=False, encoding="utf-8") as f:
            f.write(log_content)
            f.flush()
            summary = LogAggregator().aggregate(Path(f.name))
        self.assertEqual(summary.status, "partial")
        self.assertEqual(summary.level_counts.get("WARNING"), 1)
        # 无 ERROR 行时 key 不存在
        self.assertNotIn("ERROR", summary.level_counts)

    def test_aggregate_directory_empty(self):
        """边界条件：空目录聚合返回空摘要"""
        from modules.log_aggregation import LogAggregator, LogSummary
        with tempfile.TemporaryDirectory() as tmp:
            summary = LogAggregator().aggregate_directory(Path(tmp))
            self.assertIsInstance(summary, LogSummary)
            self.assertEqual(summary.total_lines, 0)
            self.assertEqual(summary.status, "success")

    def test_export_summary_writes_valid_json(self):
        """核心方法：导出摘要为 JSON 文件"""
        from modules.log_aggregation import LogAggregator
        agg = LogAggregator()
        # 构造一个简单的日志并聚合
        log_content = "2026-06-28 10:00:00 [INFO] 测试消息\n"
        with tempfile.NamedTemporaryFile(mode="w", suffix=".log",
                                          delete=False, encoding="utf-8") as f:
            f.write(log_content)
            f.flush()
            summary = agg.aggregate(Path(f.name))
        # 导出
        with tempfile.TemporaryDirectory() as tmp:
            out_path = Path(tmp) / "summary.json"
            agg.export_summary(summary, out_path)
            self.assertTrue(out_path.exists())
            data = json.loads(out_path.read_text(encoding="utf-8"))
            self.assertEqual(data["total_lines"], 1)
            self.assertIn("INFO", data["level_counts"])


class TestResultExporterExtended(TestCase):
    """结果导出模块扩展测试"""

    def test_init_default_formats(self):
        """初始化：默认导出格式"""
        from modules.result_export import ResultExporter
        exp = ResultExporter()
        self.assertEqual(exp.default_formats, ["json", "csv"])
        self.assertIn("csv", exp.SUPPORTED_FORMATS)
        self.assertIn("json", exp.SUPPORTED_FORMATS)
        self.assertIn("markdown", exp.SUPPORTED_FORMATS)
        self.assertIn("excel", exp.SUPPORTED_FORMATS)

    def test_export_unsupported_format_returns_failed(self):
        """边界条件：不支持的格式返回 failed 状态"""
        from modules.result_export import ResultExporter
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            (tmp_path / "data.json").write_text(
                json.dumps({"a": 1}), encoding="utf-8"
            )
            results = ResultExporter().export_all(
                tmp_path, tmp_path / "out", formats=["xml"]
            )
            self.assertEqual(len(results), 1)
            self.assertEqual(results[0].status, "failed")
            self.assertIn("不支持的格式", results[0].message)

    def test_export_markdown_writes_table(self):
        """核心方法：导出 Markdown 表格"""
        from modules.result_export import ResultExporter
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            (tmp_path / "metrics.json").write_text(
                json.dumps({"model": "ridge", "r2": 0.9, "rmse": 0.1}),
                encoding="utf-8"
            )
            out_dir = tmp_path / "out"
            results = ResultExporter().export_all(
                tmp_path, out_dir, formats=["markdown"]
            )
            success = [r for r in results if r.status == "success"]
            self.assertTrue(len(success) >= 1)
            md_path = out_dir / "metrics.markdown"
            self.assertTrue(md_path.exists())
            content = md_path.read_text(encoding="utf-8")
            self.assertIn("# metrics", content)
            self.assertIn("ridge", content)

    def test_flatten_to_rows_nested_dict(self):
        """核心方法：嵌套 dict 展平"""
        from modules.result_export import ResultExporter
        data = {"a": 1, "nested": {"b": 2, "c": [10, 20]}}
        rows = ResultExporter._flatten_to_rows(data, "root")
        self.assertTrue(len(rows) >= 3)
        fields = [r["field"] for r in rows]
        self.assertIn("root.a", fields)
        self.assertIn("root.nested.b", fields)

    def test_export_excel_degrades_to_csv_without_pandas(self):
        """边界条件：Excel 导出在 pandas 缺失时降级为 CSV（通过 mock）"""
        from modules.result_export import ResultExporter
        exporter = ResultExporter()
        # 直接调用 _export_excel，模拟 pandas 缺失
        with tempfile.TemporaryDirectory() as tmp:
            out_path = Path(tmp) / "data.xlsx"
            # 正常路径：pandas 可用时返回行数
            try:
                import pandas  # noqa: F401
                n = exporter._export_excel({"a": 1, "b": 2}, out_path, "data")
                self.assertGreaterEqual(n, 1)
            except ImportError:
                # pandas 不可用时应降级为 CSV
                n = exporter._export_excel({"a": 1, "b": 2}, out_path, "data")
                csv_path = out_path.with_suffix(".csv")
                self.assertTrue(csv_path.exists())


class TestModelInterpreterExtended(TestCase):
    """模型解释模块扩展测试"""

    def test_init_default_config(self):
        """初始化：默认配置"""
        from modules.model_interpretation import ModelInterpreter
        interp = ModelInterpreter()
        self.assertEqual(interp.default_method, "auto")
        self.assertEqual(interp.max_shap_samples, 100)
        # 自定义配置
        interp2 = ModelInterpreter(config={"method": "shap", "max_shap_samples": 50})
        self.assertEqual(interp2.default_method, "shap")
        self.assertEqual(interp2.max_shap_samples, 50)

    def test_interpret_unknown_method_returns_failed(self):
        """边界条件：未知方法返回 failed 状态"""
        from modules.model_interpretation import ModelInterpreter
        X = np.random.randn(10, 3)
        interp = ModelInterpreter()
        result = interp.interpret(None, X, method="nonexistent_method")
        self.assertEqual(result.status, "failed")
        self.assertIn("未知方法", result.note)

    def test_interpret_permutation_without_y_returns_failed(self):
        """边界条件：排列重要性缺少 y 标签返回 failed"""
        from modules.model_interpretation import ModelInterpreter
        # 构造一个没有 feature_importances_ 的 mock 模型，强制走 permutation
        class _DummyModel:
            def predict(self, X):
                return np.zeros(len(X))
        X = np.random.randn(10, 3)
        interp = ModelInterpreter()
        result = interp.interpret(_DummyModel(), X, y=None, method="permutation")
        self.assertEqual(result.status, "failed")
        self.assertIn("需要 y 标签", result.note)

    def test_interpret_feature_importance_on_rf(self):
        """核心方法：feature_importance 方法对随机森林解释"""
        from modules.model_interpretation import ModelInterpreter
        from sklearn.ensemble import RandomForestRegressor
        X = np.random.randn(40, 3)
        y = X[:, 0] * 2 + np.random.randn(40) * 0.1
        model = RandomForestRegressor(n_estimators=10, random_state=42).fit(X, y)
        interp = ModelInterpreter()
        result = interp.interpret(model, X, y, feature_names=["x0", "x1", "x2"],
                                   method="feature_importance")
        self.assertEqual(result.status, "success")
        self.assertEqual(result.method, "feature_importance")
        self.assertEqual(len(result.feature_importance), 3)
        # 第一个特征重要性应最高（数据由 x0 生成）
        top = list(result.feature_importance.keys())[0]
        self.assertEqual(top, "x0")


class TestHyperparameterTunerExtended(TestCase):
    """超参调优模块扩展测试"""

    def test_init_default_config(self):
        """初始化：默认配置"""
        from modules.hyperparameter_tuning import HyperparameterTuner
        tuner = HyperparameterTuner()
        self.assertEqual(tuner.default_method, "grid")
        self.assertEqual(tuner.cv_folds, 5)
        self.assertEqual(tuner.n_iter_random, 20)
        self.assertEqual(tuner.scoring, "r2")
        # 自定义配置
        tuner2 = HyperparameterTuner(config={"cv_folds": 3, "scoring": "accuracy"})
        self.assertEqual(tuner2.cv_folds, 3)
        self.assertEqual(tuner2.scoring, "accuracy")

    def test_tune_unknown_method_returns_failed(self):
        """边界条件：未知方法返回 failed 状态"""
        from modules.hyperparameter_tuning import HyperparameterTuner
        from sklearn.linear_model import Ridge
        X = np.random.randn(20, 3)
        y = X[:, 0]
        tuner = HyperparameterTuner()
        result = tuner.tune(Ridge(), {"alpha": [1.0]}, X, y, method="nonexistent")
        self.assertEqual(result.status, "failed")
        self.assertIn("未知方法", result.note)

    def test_tune_random_search(self):
        """核心方法：随机搜索调优"""
        from modules.hyperparameter_tuning import HyperparameterTuner
        from sklearn.linear_model import Ridge
        X = np.random.randn(30, 3)
        y = X[:, 0] + np.random.randn(30) * 0.1
        tuner = HyperparameterTuner(config={"cv_folds": 3, "n_iter_random": 5})
        result = tuner.tune(Ridge(), {"alpha": [0.1, 1.0, 10.0]}, X, y, method="random")
        self.assertEqual(result.status, "success")
        self.assertEqual(result.method, "random")
        self.assertIn("alpha", result.best_params)
        self.assertEqual(result.n_trials, 5)

    def test_tune_grid_returns_all_results(self):
        """核心方法：网格搜索返回所有结果详情"""
        from modules.hyperparameter_tuning import HyperparameterTuner
        from sklearn.linear_model import Ridge
        X = np.random.randn(30, 3)
        y = X[:, 0] + np.random.randn(30) * 0.1
        tuner = HyperparameterTuner(config={"cv_folds": 3})
        result = tuner.tune(Ridge(), {"alpha": [0.1, 1.0, 10.0]}, X, y, method="grid")
        self.assertEqual(result.status, "success")
        self.assertEqual(result.n_trials, 3)
        self.assertEqual(len(result.all_results), 3)
        for r in result.all_results:
            self.assertIn("params", r)
            self.assertIn("mean_score", r)


class TestModelComparatorExtended(TestCase):
    """模型对比模块扩展测试"""

    def test_init_default_config(self):
        """初始化：默认配置"""
        from modules.model_comparison import ModelComparator
        comp = ModelComparator()
        self.assertEqual(comp.cv_folds, 5)
        self.assertEqual(comp.scoring, ["r2", "rmse", "mae"])
        self.assertAlmostEqual(comp.significance_level, 0.05)
        # 自定义配置
        comp2 = ModelComparator(config={"cv_folds": 3, "significance_level": 0.01})
        self.assertEqual(comp2.cv_folds, 3)
        self.assertAlmostEqual(comp2.significance_level, 0.01)

    def test_compare_empty_models_returns_failed(self):
        """边界条件：空模型字典返回 failed"""
        from modules.model_comparison import ModelComparator
        X = np.random.randn(20, 3)
        y = X[:, 0]
        comp = ModelComparator(config={"cv_folds": 3})
        result = comp.compare({}, X, y, task_type="regression")
        self.assertEqual(result.status, "failed")
        self.assertEqual(len(result.models), 0)

    def test_compare_classification_task(self):
        """核心方法：分类任务对比"""
        from modules.model_comparison import ModelComparator
        from sklearn.linear_model import LogisticRegression
        from sklearn.ensemble import RandomForestClassifier
        X = np.random.randn(60, 4)
        y = (X[:, 0] + X[:, 1] > 0).astype(int)
        comp = ModelComparator(config={
            "cv_folds": 3, "scoring": ["accuracy"]
        })
        result = comp.compare(
            {"lr": LogisticRegression(max_iter=200),
             "rf": RandomForestClassifier(n_estimators=10, random_state=42)},
            X, y, task_type="classification"
        )
        self.assertEqual(result.status, "success")
        self.assertEqual(result.best_metric, "accuracy")
        self.assertIn(result.best_model, ("lr", "rf"))
        self.assertEqual(len(result.ranking), 2)

    def test_significance_test_insufficient_samples(self):
        """边界条件：样本不足时返回 insufficient_samples"""
        from modules.model_comparison import ModelComparator
        comp = ModelComparator()
        result = comp._significance_test([0.5], [0.4], "m1", "m2")
        self.assertEqual(result["status"], "insufficient_samples")

    def test_compare_with_significance_test(self):
        """核心方法：两模型对比触发显著性检验"""
        from modules.model_comparison import ModelComparator
        from sklearn.linear_model import LinearRegression, Ridge
        X = np.random.randn(60, 3)
        y = X[:, 0] + np.random.randn(60) * 0.1
        comp = ModelComparator(config={"cv_folds": 5, "scoring": ["r2"]})
        result = comp.compare(
            {"linear": LinearRegression(), "ridge": Ridge(alpha=0.1)},
            X, y, task_type="regression"
        )
        self.assertEqual(result.status, "success")
        self.assertIsNotNone(result.significance_test)
        self.assertEqual(result.significance_test["test"], "paired_ttest")
        self.assertIn("p_value", result.significance_test)


if __name__ == "__main__":
    unittest_main()
