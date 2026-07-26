"""
数学建模竞赛工作流 - 模型求解模块测试
测试模型求解基础与高级功能
"""

import sys
import numpy as np
from pathlib import Path
from unittest import TestCase, main as unittest_main

# 添加父目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

# 导入模块
from modules import model_solving


class TestModelSolving(TestCase):
    """测试模型求解模块"""

    def setUp(self):
        import numpy as np
        from sklearn.linear_model import LinearRegression

        np.random.seed(42)
        self.X = np.random.randn(100, 5)
        self.y = 2 * self.X[:, 0] + 3 * self.X[:, 1] + np.random.randn(100) * 0.5
        self.feature_names = [f'feature_{i}' for i in range(5)]

        self.model = LinearRegression()
        self.model.fit(self.X, self.y)

    def test_solve_model(self):
        """测试模型求解"""
        solver = model_solving.ModelSolver()
        result = solver.solve_model(
            self.model, self.X, self.y,
            model_name="test_model",
            feature_names=self.feature_names
        )

        self.assertIsNotNone(result)
        self.assertGreater(result.metrics.r2, 0.5)

    def test_metrics_calculation(self):
        """测试指标计算"""
        solver = model_solving.ModelSolver()
        result = solver.solve_model(
            self.model, self.X, self.y,
            model_name="test_model"
        )

        self.assertGreater(result.metrics.r2, 0)
        self.assertGreater(result.metrics.rmse, 0)
        self.assertGreater(result.metrics.mae, 0)

    def test_feature_importance(self):
        """测试特征重要性"""
        solver = model_solving.ModelSolver()
        result = solver.solve_model(
            self.model, self.X, self.y,
            model_name="test_model",
            feature_names=self.feature_names
        )

        self.assertIsNotNone(result.feature_importance)
        self.assertEqual(len(result.feature_importance), 5)

    def test_sensitivity_analysis(self):
        """测试灵敏度分析"""
        solver = model_solving.ModelSolver()
        result = solver.solve_model(
            self.model, self.X, self.y,
            model_name="test_model"
        )

        self.assertIsNotNone(result.sensitivity_results)


class TestModelSolverAdvanced(TestCase):
    """测试模型求解模块高级功能"""

    def setUp(self):
        np.random.seed(42)
        n = 50
        self.X = np.random.randn(n, 3)
        self.y = 2 * self.X[:, 0] + 3 * self.X[:, 1] + np.random.randn(n) * 0.5
        self.feature_names = ["feature_0", "feature_1", "feature_2"]

    def test_ridge_model_solving(self):
        """测试岭回归求解"""
        from sklearn.linear_model import Ridge
        from modules import model_solving

        model = Ridge(alpha=1.0)
        model.fit(self.X, self.y)

        solver = model_solving.ModelSolver()
        result = solver.solve_model(model, self.X, self.y, model_name="岭回归", feature_names=self.feature_names)

        self.assertIsNotNone(result.metrics)
        self.assertGreater(result.metrics.r2, 0)

    def test_lasso_model_solving(self):
        """测试Lasso回归求解"""
        from sklearn.linear_model import Lasso
        from modules import model_solving

        model = Lasso(alpha=0.1)
        model.fit(self.X, self.y)

        solver = model_solving.ModelSolver()
        result = solver.solve_model(model, self.X, self.y, model_name="Lasso回归", feature_names=self.feature_names)

        self.assertIsNotNone(result.metrics)
        self.assertGreater(result.metrics.r2, 0)

    def test_metrics_range(self):
        """测试指标范围"""
        from sklearn.linear_model import LinearRegression
        from modules import model_solving

        model = LinearRegression()
        model.fit(self.X, self.y)

        solver = model_solving.ModelSolver()
        result = solver.solve_model(model, self.X, self.y, feature_names=self.feature_names)

        # R²应在合理范围内
        self.assertGreaterEqual(result.metrics.r2, -1)
        self.assertLessEqual(result.metrics.r2, 1)

        # RMSE应为正数
        self.assertGreater(result.metrics.rmse, 0)

        # MAE应为正数
        self.assertGreater(result.metrics.mae, 0)


if __name__ == "__main__":
    unittest_main()
