"""
性能基准测试模块的单元测试
验证 PerformanceBenchmark 的功能正确性（不测试实际性能数值）
"""
import sys
import json
import tempfile
import shutil
from pathlib import Path
from unittest import TestCase, main as unittest_main

sys.path.insert(0, str(Path(__file__).parent.parent))



class TestPerformanceBenchmark(TestCase):
    """测试性能基准测试模块"""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        from benchmarks.performance_baseline import PerformanceBenchmark
        self.benchmark = PerformanceBenchmark(output_dir=Path(self.temp_dir))

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_benchmark_initialization(self):
        """测试基准测试器初始化"""
        self.assertTrue(self.benchmark.output_dir.exists())
        self.assertEqual(self.benchmark.results, [])

    def test_measure_function(self):
        """测试 _measure 方法测量时间和内存"""
        def dummy_func():
            return sum(range(1000))

        result = self.benchmark._measure(dummy_func)
        self.assertIn("result", result)
        self.assertIn("elapsed_seconds", result)
        self.assertIn("memory_peak_mb", result)
        self.assertEqual(result["result"], 499500)
        self.assertGreaterEqual(result["elapsed_seconds"], 0)

    def test_benchmark_regression_models(self):
        """测试回归模型基准测试"""
        results = self.benchmark.benchmark_regression_models(n_samples=100, n_features=5)
        self.assertGreater(len(results), 0)
        for r in results:
            self.assertIn("model", r)
            self.assertIn("train_time", r)
            self.assertIn("predict_time", r)
            self.assertIn("memory_mb", r)
            self.assertIn("r2_score", r)

    def test_benchmark_clustering_models(self):
        """测试聚类模型基准测试"""
        results = self.benchmark.benchmark_clustering_models(n_samples=100, n_features=3)
        self.assertGreater(len(results), 0)
        for r in results:
            self.assertIn("model", r)
            self.assertEqual(r["category"], "clustering")

    def test_benchmark_evaluation_models(self):
        """测试评价模型基准测试"""
        results = self.benchmark.benchmark_evaluation_models(n_alternatives=5, n_criteria=3)
        self.assertGreater(len(results), 0)
        for r in results:
            self.assertIn("model", r)
            self.assertEqual(r["category"], "evaluation")

    def test_benchmark_dimension_reduction(self):
        """测试降维模型基准测试"""
        results = self.benchmark.benchmark_dimension_reduction(n_samples=100, n_features=10)
        self.assertGreater(len(results), 0)
        self.assertEqual(results[0]["model"], "pca")

    def test_run_all_benchmarks(self):
        """测试完整基准测试运行"""
        report = self.benchmark.run_all_benchmarks()
        self.assertIn("timestamp", report)
        self.assertIn("total_models", report)
        self.assertIn("results", report)
        self.assertGreater(report["total_models"], 0)

        # 验证结果文件生成
        output_file = self.benchmark.output_dir / "performance_baseline.json"
        self.assertTrue(output_file.exists())
        saved = json.loads(output_file.read_text(encoding="utf-8"))
        self.assertEqual(saved["total_models"], report["total_models"])


if __name__ == "__main__":
    unittest_main()
