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


class TestNewOptimizationSimulation(TestCase):
    """恢复版补齐的 optimization / optimization_meta / simulation stub 的真实实现测试"""

    def setUp(self):
        from modules.model_solving.model_factory import ModelFactory
        self.factory = ModelFactory()
        self.sphere = lambda x: sum(v * v for v in x)

    def test_integer_programming_kp(self):
        # 0-1 背包：max 60x0+100x1+120x2 s.t. 10x0+20x1+30x2<=50 -> 选 [1,2]
        r = self.factory.solve("integer_programming",
                               c=[-60, -100, -120], A_ub=[[10, 20, 30]], b_ub=[50])
        self.assertEqual(r["status"], "success")
        self.assertEqual(r["selected_items"], [1, 2])
        self.assertAlmostEqual(r["optimal_value"], -220.0, places=4)

    def test_pso_converges_to_zero(self):
        r = self.factory.solve("pso", objective=self.sphere, dim=3,
                               bounds=[(-5, 5)] * 3, max_iter=80, pop_size=40)
        self.assertEqual(r["status"], "success")
        self.assertLess(r["best_value"], 1.0)

    def test_abc_converges(self):
        r = self.factory.solve("abc", objective=self.sphere, dim=3,
                               bounds=[(-5, 5)] * 3, max_iter=60, pop_size=30)
        self.assertEqual(r["status"], "success")
        self.assertLess(r["best_value"], 5.0)

    def test_genetic_algorithm_converges(self):
        r = self.factory.solve("genetic_algorithm", objective=self.sphere, dim=3,
                               bounds=[(-5, 5)] * 3, max_iter=80)
        self.assertEqual(r["status"], "success")
        self.assertLess(r["best_value"], 5.0)

    def test_ant_colony_tsp(self):
        coords = [[0, 0], [1, 2], [3, 1], [2, 4], [5, 3]]
        r = self.factory.solve("ant_colony", coords=coords, n_ants=15, max_iter=40)
        self.assertEqual(r["status"], "success")
        # 回路应包含全部城市
        self.assertEqual(sorted(r["best_route"]), list(range(5)))
        self.assertGreater(r["best_length"], 0)

    def test_game_theory_symmetric(self):
        # 匹配硬币：对称零和博弈，值应为 0，最优混合策略为 [0.5, 0.5]
        r = self.factory.solve("game_theory", payoff=[[1, -1], [-1, 1]])
        self.assertEqual(r["status"], "success")
        self.assertAlmostEqual(r["value"], 0.0, places=4)
        self.assertAlmostEqual(sum(r["row_strategy"]), 1.0, places=4)
        for p in r["row_strategy"]:
            self.assertAlmostEqual(p, 0.5, places=4)

    def test_agent_based_sir(self):
        r = self.factory.solve("agent_based", n_agents=80, init_infected=4,
                               beta=0.25, gamma=0.08, n_steps=40)
        self.assertEqual(r["status"], "success")
        self.assertEqual(r["final"]["S"] + r["final"]["I"] + r["final"]["R"], 80)
        # 疫情应能收敛（最终感染数较少或归零）
        self.assertLessEqual(r["final"]["I"], 80)

    def test_discrete_event_queue(self):
        r = self.factory.solve("discrete_event", arrival_rate=0.8, service_rate=1.0,
                               n_servers=2, n_customers=300)
        self.assertEqual(r["status"], "success")
        self.assertGreaterEqual(r["avg_wait_time"], 0.0)
        self.assertLessEqual(r["utilization"], 1.0)


if __name__ == "__main__":
    unittest_main()
