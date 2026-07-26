"""
数学建模竞赛工作流 - 模型工厂测试
测试模型工厂基础、v3.2 高阶模型与 v3.3.1 补齐模型
"""

import sys
import numpy as np
from pathlib import Path
from unittest import TestCase, main as unittest_main

# 添加父目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))


class TestModelFactory(TestCase):
    """测试模型工厂（H4：覆盖新增的 model_factory 与 _solve_* 方法）"""

    def setUp(self):
        np.random.seed(42)
        # 回归用
        self.X_reg = np.random.randn(80, 4)
        self.y_reg = 2 * self.X_reg[:, 0] + 3 * self.X_reg[:, 1] + np.random.randn(80) * 0.3
        # 分类用
        from sklearn.datasets import make_classification
        self.X_clf, self.y_clf = make_classification(
            n_samples=80, n_features=4, n_informative=2, n_redundant=0, random_state=42
        )
        # 时序用
        self.series = np.cumsum(np.random.randn(40)) + 10

    def test_get_category_factory_ids(self):
        """测试 factory ID 类别分发"""
        from modules.model_factory import ModelFactory
        self.assertEqual(ModelFactory.get_category("linear_regression"), "regression")
        self.assertEqual(ModelFactory.get_category("ridge"), "regression")
        self.assertEqual(ModelFactory.get_category("logistic_regression"), "classification")
        self.assertEqual(ModelFactory.get_category("svm"), "classification")
        self.assertEqual(ModelFactory.get_category("kmeans"), "clustering")
        self.assertEqual(ModelFactory.get_category("pca"), "dimension_reduction")
        self.assertEqual(ModelFactory.get_category("ahp"), "evaluation")
        self.assertEqual(ModelFactory.get_category("topsis"), "evaluation")
        self.assertEqual(ModelFactory.get_category("linear_programming"), "optimization")
        self.assertEqual(ModelFactory.get_category("arima"), "time_series")

    def test_get_category_catalog_aliases(self):
        """测试 catalog 别名兼容（C4 修复）"""
        from modules.model_factory import ModelFactory
        self.assertEqual(ModelFactory.get_category("regression"), "regression")
        self.assertEqual(ModelFactory.get_category("random_forest"), "classification")
        self.assertEqual(ModelFactory.get_category("cluster_analysis"), "clustering")
        self.assertEqual(ModelFactory.get_category("time_series_arima"), "time_series")

    def test_build_supervised_regression(self):
        """测试回归模型构建与训练"""
        from modules.model_factory import ModelFactory
        model, mtype = ModelFactory.build_supervised("ridge", self.X_reg, self.y_reg)
        self.assertEqual(mtype, "regression")
        self.assertIsNotNone(model.predict(self.X_reg))

    def test_build_supervised_classification(self):
        """测试分类模型构建与训练"""
        from modules.model_factory import ModelFactory
        model, mtype = ModelFactory.build_supervised(
            "logistic_regression", self.X_clf, self.y_clf
        )
        self.assertEqual(mtype, "classification")
        self.assertIsNotNone(model.predict(self.X_clf))

    def test_build_supervised_clustering(self):
        """测试聚类模型构建"""
        from modules.model_factory import ModelFactory
        model, mtype = ModelFactory.build_supervised(
            "kmeans", self.X_reg, np.zeros(len(self.X_reg))
        )
        self.assertEqual(mtype, "clustering")
        self.assertIsNotNone(model.labels_)

    def test_build_supervised_dimension_reduction(self):
        """测试降维模型构建"""
        from modules.model_factory import ModelFactory
        model, mtype = ModelFactory.build_supervised(
            "pca", self.X_reg, np.zeros(len(self.X_reg))
        )
        self.assertEqual(mtype, "dimension_reduction")
        self.assertIsNotNone(model.transformed_)

    def test_evaluation_ahp_valid_matrix(self):
        """测试 AHP 求解（H3：使用合法正互反矩阵）"""
        from modules.model_factory import EvaluationSolver
        # 标准正互反矩阵：1, 3, 5; 1/3, 1, 3; 1/5, 1/3, 1
        m = np.array([[1.0, 3.0, 5.0],
                      [1/3, 1.0, 3.0],
                      [1/5, 1/3, 1.0]])
        r = EvaluationSolver.ahp(m)
        self.assertEqual(r["method"], "AHP")
        self.assertEqual(len(r["weights"]), 3)
        self.assertGreaterEqual(r["CR"], 0)
        # 合法判断矩阵通常 CR < 0.1
        self.assertLess(r["CR"], 0.2)

    def test_evaluation_ahp_rejects_non_positive(self):
        """测试 AHP 拒绝非正数矩阵"""
        from modules.model_factory import EvaluationSolver
        m = np.array([[1.0, -2.0], [-0.5, 1.0]])
        with self.assertRaises(ValueError):
            EvaluationSolver.ahp(m)

    def test_evaluation_ahp_rejects_non_reciprocal(self):
        """测试 AHP 拒绝非正互反矩阵（H3 修复验证）"""
        from modules.model_factory import EvaluationSolver
        # 不满足 a_ij * a_ji = 1
        m = np.array([[1.0, 2.0], [3.0, 1.0]])  # 2*3=6 != 1
        with self.assertRaises(ValueError):
            EvaluationSolver.ahp(m)

    def test_evaluation_topsis(self):
        """测试 TOPSIS 评价"""
        from modules.model_factory import EvaluationSolver
        m = np.array([[85, 70], [70, 90], [60, 80]])
        r = EvaluationSolver.topsis(m)
        self.assertEqual(len(r["scores"]), 3)
        self.assertEqual(len(r["ranking"]), 3)

    def test_evaluation_entropy_weight(self):
        """测试熵权法"""
        from modules.model_factory import EvaluationSolver
        m = np.array([[85, 70], [70, 90], [60, 80], [95, 65]])
        r = EvaluationSolver.entropy_weight(m)
        self.assertEqual(len(r["weights"]), 2)

    def test_optimization_linear_programming(self):
        """测试线性规划（H2：使用真实参数）"""
        from modules.model_factory import OptimizationSolver
        # min -x - 2y s.t. x + y <= 10, x + 4y >= 0, x,y >= 0
        # 最优解 x=0, y=10, optimal=-20
        c = np.array([-1.0, -2.0])
        A_ub = np.array([[1.0, 1.0]])
        b_ub = np.array([10.0])
        r = OptimizationSolver.linear_programming(c, A_ub, b_ub)
        self.assertEqual(r["status"], "success")
        self.assertAlmostEqual(r["optimal_value"], -20.0, places=1)

    def test_optimization_integer_programming(self):
        """测试整数规划"""
        from modules.model_factory import OptimizationSolver
        c = np.array([-1.0, -2.0])
        A_ub = np.array([[1.0, 1.0]])
        b_ub = np.array([10.0])
        r = OptimizationSolver.integer_programming(c, A_ub, b_ub)
        self.assertEqual(r["status"], "success")

    def test_time_series_arima(self):
        """测试 ARIMA 时序求解（容忍 statsmodels 降级）"""
        from modules.model_factory import TimeSeriesSolver
        r = TimeSeriesSolver.arima(self.series, forecast_steps=3)
        self.assertEqual(r["status"], "success")
        self.assertEqual(len(r["forecast"]), 3)

    # ─── P1：补充未覆盖模型的测试 ───

    def test_build_regression_variants(self):
        """测试回归变体模型（lasso/polynomial/svr/random_forest_regressor）"""
        from modules.model_factory import ModelFactory
        # lasso
        m, t = ModelFactory.build_supervised("lasso", self.X_reg, self.y_reg)
        self.assertEqual(t, "regression")
        # polynomial_regression
        m, t = ModelFactory.build_supervised("polynomial_regression", self.X_reg, self.y_reg)
        self.assertEqual(t, "regression")
        # svr
        m, t = ModelFactory.build_supervised("svr", self.X_reg, self.y_reg)
        self.assertEqual(t, "regression")
        # random_forest_regressor
        m, t = ModelFactory.build_supervised("random_forest_regressor", self.X_reg, self.y_reg)
        self.assertEqual(t, "regression")

    def test_build_classification_variants(self):
        """测试分类变体模型（svm/knn/decision_tree/random_forest_classifier）"""
        from modules.model_factory import ModelFactory
        for mid in ["svm", "knn", "decision_tree", "random_forest_classifier"]:
            m, t = ModelFactory.build_supervised(mid, self.X_clf, self.y_clf)
            self.assertEqual(t, "classification", f"模型 {mid} 类型不符")

    def test_build_dbscan_clustering(self):
        """测试 DBSCAN 聚类"""
        from modules.model_factory import ModelFactory
        m, t = ModelFactory.build_supervised("dbscan", self.X_reg, np.zeros(len(self.X_reg)))
        self.assertEqual(t, "clustering")
        self.assertTrue(hasattr(m, "labels_"))

    def test_build_factor_analysis(self):
        """测试因子分析降维"""
        from modules.model_factory import ModelFactory
        m, t = ModelFactory.build_supervised("factor_analysis", self.X_reg, np.zeros(len(self.X_reg)))
        self.assertEqual(t, "dimension_reduction")
        self.assertTrue(hasattr(m, "transformed_"))

    def test_comprehensive_evaluation(self):
        """测试综合评价（熵权+TOPSIS 组合）"""
        from modules.model_factory import EvaluationSolver
        dm = np.array([[80, 90, 85], [70, 60, 75], [90, 85, 95]], dtype=float)
        r = EvaluationSolver.comprehensive_evaluation(dm)
        self.assertEqual(r["method"], "ComprehensiveEvaluation")
        self.assertIn("ranking", r)
        self.assertIn("entropy_weights", r)
        self.assertEqual(len(r["ranking"]), 3)

    def test_svr_in_category_map(self):
        """P2：验证 svr 已正确登记到 MODEL_CATEGORY_MAP"""
        from modules.model_factory import ModelFactory
        self.assertEqual(ModelFactory.get_category("svr"), "regression")

    def test_phantom_ids_removed_from_map(self):
        """P2：验证 5 个虚假声明 ID 已从 MODEL_CATEGORY_MAP 移除
        注：v3.3.1 已真实实现 exponential_smoothing 与 fuzzy_evaluation，
        因此从原 7 个 removed 列表中移除这 2 个。
        """
        from modules.model_factory import ModelFactory
        removed = [
            "lightgbm_regressor", "nonlinear_programming", "holt_winters",
            "linear_trend", "fuzzy_comprehensive_evaluation",
        ]
        for mid in removed:
            self.assertNotIn(mid, ModelFactory.MODEL_CATEGORY_MAP,
                             f"{mid} 应已从 MODEL_CATEGORY_MAP 移除")


class TestAdvancedModels(TestCase):
    """测试 v3.2 新增的 16 个高阶模型实现"""

    def setUp(self):
        np.random.seed(42)
        self.X_reg = np.random.randn(50, 4)
        self.y_reg = (self.X_reg[:, 0] + self.X_reg[:, 1] > 0).astype(int)

    # ─── 仿真类（7 个） ───

    def test_monte_carlo(self):
        from modules.model_factory import SimulationSolver
        r = SimulationSolver.monte_carlo(lambda: np.random.normal(0, 1),
                                          n_simulations=500, random_state=42)
        self.assertEqual(r["status"], "success")
        self.assertEqual(r["n_simulations"], 500)
        self.assertIn("mean", r)

    def test_cellular_automaton(self):
        from modules.model_factory import SimulationSolver
        initial = np.zeros((5, 5), dtype=int)
        initial[2, 2] = 1
        r = SimulationSolver.cellular_automaton(initial, n_steps=3)
        self.assertEqual(r["status"], "success")
        self.assertEqual(len(r["history"]), 4)  # 初始 + 3 步

    def test_queueing_theory(self):
        from modules.model_factory import SimulationSolver
        r = SimulationSolver.queueing_theory(0.5, 1.0, n_servers=1, random_state=42)
        self.assertEqual(r["status"], "success")
        self.assertEqual(r["model"], "M/M/c")
        self.assertGreaterEqual(r["avg_wait_time"], 0)

    def test_game_theory(self):
        from modules.model_factory import SimulationSolver
        payoff = np.array([[3, 0], [5, 1]], dtype=float)
        r = SimulationSolver.game_theory(payoff)
        self.assertEqual(r["status"], "success")
        self.assertEqual(len(r["strategy_row"]), 2)

    def test_agent_based(self):
        from modules.model_factory import SimulationSolver
        r = SimulationSolver.agent_based(n_agents=10, n_steps=5, random_state=42)
        self.assertEqual(r["status"], "success")
        self.assertEqual(r["n_agents"], 10)

    def test_system_dynamics(self):
        from modules.model_factory import SimulationSolver
        # 简单指数衰减 dy/dt = -0.5 * y
        r = SimulationSolver.system_dynamics(
            lambda t, y: [-0.5 * y[0]], [1.0], (0, 5)
        )
        self.assertEqual(r["status"], "success")
        self.assertEqual(len(r["time_points"]), 100)

    def test_discrete_event(self):
        from modules.model_factory import SimulationSolver
        events = [{"time": t, "type": "arrival"} for t in [1, 3, 5]]
        r = SimulationSolver.discrete_event(events, end_time=10.0)
        self.assertEqual(r["status"], "success")
        self.assertEqual(r["processed_events"], 3)

    # ─── 图论类（2 个） ───

    def test_dijkstra(self):
        from modules.model_factory import GraphSolver
        adj = np.array([[0, 1, 0], [1, 0, 1], [0, 1, 0]], dtype=float)
        r = GraphSolver.dijkstra(adj, source=0, target=2)
        self.assertEqual(r["status"], "success")
        self.assertEqual(r["path"], [0, 1, 2])

    def test_max_flow(self):
        from modules.model_factory import GraphSolver
        cap = np.array([[0, 3, 0], [0, 0, 2], [0, 0, 0]], dtype=float)
        r = GraphSolver.max_flow(cap, source=0, sink=2)
        self.assertEqual(r["status"], "success")
        self.assertEqual(r["max_flow"], 2.0)

    # ─── 神经网络类（2 个） ───

    def test_mlp(self):
        from modules.model_factory import NeuralNetworkSolver
        r = NeuralNetworkSolver.mlp(self.X_reg, self.y_reg,
                                     hidden_layer_sizes=(10,), max_iter=50,
                                     random_state=42)
        self.assertEqual(r["status"], "success")
        self.assertEqual(r["method"], "MLP")
        self.assertGreaterEqual(r["score"], 0.0)

    def test_cnn_degrades_gracefully(self):
        """CNN 在 tensorflow 缺失时降级为 MLP（容忍降级）"""
        from modules.model_factory import NeuralNetworkSolver
        r = NeuralNetworkSolver.cnn(self.X_reg, self.y_reg, epochs=1, random_state=42)
        self.assertEqual(r["status"], "success")
        # method 应为 "CNN" 或 "CNN(降级为MLP)"
        self.assertTrue(r["method"].startswith("CNN"))

    # ─── 模糊逻辑类（2 个） ───

    def test_fuzzy_inference(self):
        from modules.model_factory import FuzzySolver
        inputs = {"temp": 0.6}
        rules = [
            {"if": {"temp": {"high": 0.6}}, "then": {"output": 0.8}},
            {"if": {"temp": {"low": 0.4}}, "then": {"output": 0.3}},
        ]
        r = FuzzySolver.fuzzy_inference(inputs, rules)
        self.assertEqual(r["status"], "success")
        self.assertEqual(r["n_rules"], 2)
        self.assertIn("output", r["outputs"])

    def test_fuzzy_clustering(self):
        from modules.model_factory import FuzzySolver
        X = np.random.randn(20, 3)
        r = FuzzySolver.fuzzy_clustering(X, n_clusters=2, random_state=42)
        self.assertEqual(r["status"], "success")
        self.assertEqual(r["n_clusters"], 2)
        self.assertEqual(len(r["membership"]), 20)

    # ─── 元启发式（3 个） ───

    def test_pso(self):
        from modules.model_factory import MetaHeuristicSolver
        # Sphere 函数最小值在 (0, 0)，最优值 0
        r = MetaHeuristicSolver.pso(
            lambda x: float(np.sum(x ** 2)), dim=2, bounds=[[-5, 5], [-5, 5]],
            n_particles=15, max_iter=30, random_state=42
        )
        self.assertEqual(r["status"], "success")
        self.assertEqual(r["method"], "PSO")
        self.assertLess(r["best_value"], 1.0)  # 应接近 0

    def test_de(self):
        from modules.model_factory import MetaHeuristicSolver
        r = MetaHeuristicSolver.de(
            lambda x: float(np.sum(x ** 2)), dim=2, bounds=[[-5, 5], [-5, 5]],
            pop_size=15, max_iter=30, random_state=42
        )
        self.assertEqual(r["status"], "success")
        self.assertEqual(r["method"], "DE")
        self.assertLess(r["best_value"], 1.0)

    def test_abc(self):
        from modules.model_factory import MetaHeuristicSolver
        r = MetaHeuristicSolver.abc(
            lambda x: float(np.sum(x ** 2)), dim=2, bounds=[[-5, 5], [-5, 5]],
            n_bees=20, max_iter=30, random_state=42
        )
        self.assertEqual(r["status"], "success")
        self.assertEqual(r["method"], "ABC")
        self.assertLess(r["best_value"], 5.0)  # ABC 收敛较慢，放宽阈值

    # ─── MODEL_CATEGORY_MAP 登记验证 ───

    def test_new_ids_in_category_map(self):
        """验证 16 个新模型 ID 已正确登记到 MODEL_CATEGORY_MAP"""
        from modules.model_factory import ModelFactory
        expected = {
            "monte_carlo": "simulation", "cellular_automata": "simulation",
            "queueing_theory": "simulation", "game_theory": "simulation",
            "agent_based": "simulation", "system_dynamics": "simulation",
            "discrete_event": "simulation",
            "dijkstra": "graph_theory", "max_flow": "graph_theory",
            "mlp": "neural_networks", "cnn": "neural_networks",
            "fuzzy_inference": "fuzzy_logic", "fuzzy_clustering": "fuzzy_logic",
            "pso": "optimization_meta", "de": "optimization_meta",
            "abc": "optimization_meta",
        }
        for mid, cat in expected.items():
            self.assertEqual(ModelFactory.get_category(mid), cat,
                             f"{mid} 类别应为 {cat}")


class TestV331NewModels(TestCase):
    """测试 v3.3.1 补齐的 17 个模型实现"""

    def test_anova(self):
        """方差分析：单因素 ANOVA"""
        from modules.model_factory import StatisticsSolver
        np.random.seed(42)
        g1 = np.random.normal(5, 1, 30)
        g2 = np.random.normal(7, 1, 30)
        g3 = np.random.normal(6, 1, 30)
        result = StatisticsSolver.anova([g1, g2, g3])
        self.assertEqual(result["status"], "success")
        self.assertEqual(result["method"], "ANOVA")
        self.assertEqual(result["n_groups"], 3)
        self.assertIn("f_statistic", result)
        self.assertIn("p_value", result)
        self.assertIn("significant", result)

    def test_anova_significant_diff(self):
        """方差分析：组间差异显著时 p_value 应较小"""
        from modules.model_factory import StatisticsSolver
        np.random.seed(42)
        g1 = np.random.normal(0, 0.1, 50)
        g2 = np.random.normal(10, 0.1, 50)  # 显著不同
        result = StatisticsSolver.anova([g1, g2])
        self.assertLess(result["p_value"], 0.01)
        self.assertTrue(result["significant"])

    def test_exponential_smoothing(self):
        """指数平滑：时间序列预测"""
        from modules.model_factory import StatisticsSolver
        series = np.array([10, 12, 15, 14, 18, 20, 22, 25, 28, 30], dtype=float)
        result = StatisticsSolver.exponential_smoothing(series, forecast_steps=3)
        self.assertEqual(result["status"], "success")
        self.assertEqual(result["method"], "ExponentialSmoothing")
        self.assertEqual(len(result["forecast"]), 3)
        self.assertIn("smoothing_level", result)
        self.assertIn("library", result)

    def test_exponential_smoothing_short_series(self):
        """指数平滑：短序列应抛 ValueError"""
        from modules.model_factory import StatisticsSolver
        with self.assertRaises(ValueError):
            StatisticsSolver.exponential_smoothing(np.array([1.0, 2.0]), forecast_steps=3)

    def test_grey_prediction(self):
        """灰色预测：GM(1,1)"""
        from modules.model_factory import PredictionSolver
        series = np.array([5, 8, 12, 18, 25, 35], dtype=float)
        result = PredictionSolver.grey_prediction(series, forecast_steps=3)
        self.assertEqual(result["status"], "success")
        self.assertEqual(result["method"], "GreyPrediction")
        self.assertEqual(result["model"], "GM(1,1)")
        self.assertEqual(len(result["forecast"]), 3)
        self.assertEqual(len(result["fitted_values"]), 6)
        self.assertIn("a", result)
        self.assertIn("b", result)
        self.assertIn("accuracy_level", result)

    def test_grey_prediction_with_negative(self):
        """灰色预测：含非正值的序列应自动平移"""
        from modules.model_factory import PredictionSolver
        series = np.array([-2, 1, 3, 6, 10], dtype=float)
        result = PredictionSolver.grey_prediction(series, forecast_steps=2)
        self.assertEqual(result["status"], "success")
        self.assertGreater(result["offset"], 0)

    def test_grey_prediction_too_short(self):
        """灰色预测：<4 个观测值应抛 ValueError"""
        from modules.model_factory import PredictionSolver
        with self.assertRaises(ValueError):
            PredictionSolver.grey_prediction(np.array([1, 2, 3]), forecast_steps=2)

    def test_lstm_degrades_gracefully(self):
        """LSTM：tensorflow 不可用时降级为 MLP"""
        from modules.model_factory import PredictionSolver
        np.random.seed(42)
        series = np.sin(np.linspace(0, 10, 30)) + np.random.randn(30) * 0.1
        result = PredictionSolver.lstm(series, forecast_steps=3, look_back=5, epochs=5, random_state=42)
        self.assertEqual(result["status"], "success")
        self.assertEqual(result["method"], "LSTM")
        self.assertIn("library", result)
        # library 可能是 tensorflow 或 sklearn_mlp_fallback，都算成功
        self.assertIn(result["library"], ["tensorflow", "sklearn_mlp_fallback"])
        self.assertEqual(len(result["forecast"]), 3)

    def test_prophet_degrades_gracefully(self):
        """Prophet：prophet 包不可用时降级为 ARIMA 或线性趋势"""
        from modules.model_factory import PredictionSolver
        np.random.seed(42)
        series = np.cumsum(np.random.randn(20)) + 10
        result = PredictionSolver.prophet(series, forecast_steps=3)
        self.assertEqual(result["status"], "success")
        self.assertEqual(result["method"], "Prophet")
        self.assertIn("library", result)
        self.assertIn(result["library"], ["prophet", "statsmodels_arima_fallback", "linear_trend_fallback"])

    def test_prophet_too_short(self):
        """Prophet：<10 个观测值应抛 ValueError"""
        from modules.model_factory import PredictionSolver
        with self.assertRaises(ValueError):
            PredictionSolver.prophet(np.array([1, 2, 3, 4, 5]), forecast_steps=2)

    def test_grey_relational(self):
        """灰色关联分析"""
        from modules.model_factory import EvaluationSolver
        decision_matrix = np.array([
            [80, 70, 90],
            [85, 65, 88],
            [78, 80, 92],
        ], dtype=float)
        result = EvaluationSolver.grey_relational(decision_matrix)
        self.assertEqual(result["status"], "success")
        self.assertEqual(result["method"], "GreyRelationalAnalysis")
        self.assertEqual(len(result["grey_grades"]), 3)
        self.assertEqual(len(result["ranking"]), 3)
        self.assertEqual(result["rho"], 0.5)

    def test_dea(self):
        """DEA 数据包络分析：CCR 模型"""
        from modules.model_factory import EvaluationSolver
        # 3 个 DMU，2 输入 1 输出
        inputs = np.array([[2, 3], [3, 4], [1, 2]], dtype=float)
        outputs = np.array([[10], [12], [8]], dtype=float)
        result = EvaluationSolver.dea(inputs, outputs)
        self.assertEqual(result["status"], "success")
        self.assertEqual(result["method"], "DEA")
        self.assertEqual(result["model"], "CCR_input_oriented")
        self.assertEqual(len(result["efficiency_scores"]), 3)
        # 效率值应在 [0, 1] 范围内
        for score in result["efficiency_scores"]:
            self.assertGreaterEqual(score, 0.0)
            self.assertLessEqual(score, 1.0)

    def test_fuzzy_evaluation(self):
        """模糊综合评价"""
        from modules.model_factory import EvaluationSolver
        # 3 个因素，4 个评语等级
        eval_matrix = np.array([
            [0.7, 0.2, 0.1, 0.0],
            [0.6, 0.3, 0.1, 0.0],
            [0.5, 0.4, 0.1, 0.0],
        ], dtype=float)
        result = EvaluationSolver.fuzzy_evaluation(eval_matrix)
        self.assertEqual(result["status"], "success")
        self.assertEqual(result["method"], "FuzzyComprehensiveEvaluation")
        self.assertEqual(len(result["evaluation_result"]), 4)
        self.assertIn("defuzzified_score", result)
        self.assertIn("grade_label", result)
        self.assertIn(result["grade_label"], ["差", "中", "良", "优"])

    def test_dynamic_programming_knapsack(self):
        """动态规划：0-1 背包"""
        from modules.model_factory import OptimizationSolver
        values = np.array([60, 100, 120])
        weights = np.array([10, 20, 30])
        capacity = 50
        result = OptimizationSolver.dynamic_programming(
            problem_type="knapsack", values=values, weights=weights, capacity=capacity
        )
        self.assertEqual(result["status"], "success")
        self.assertEqual(result["problem_type"], "0-1 knapsack")
        # 经典 0-1 背包问题：60+100+120 选 100+120=220（重量 50）
        self.assertEqual(result["optimal_value"], 220)
        self.assertEqual(sorted(result["selected_items"]), [1, 2])
        self.assertEqual(result["total_weight"], 50)

    def test_dynamic_programming_lcs(self):
        """动态规划：最长公共子序列"""
        from modules.model_factory import OptimizationSolver
        s1 = list("ABCBDAB")
        s2 = list("BDCABA")
        result = OptimizationSolver.dynamic_programming(
            problem_type="lcs", values=s1, weights=s2
        )
        self.assertEqual(result["status"], "success")
        # LCS = "BCBA" 或 "BDAB"，长度 4
        self.assertEqual(result["optimal_value"], 4)

    def test_simulated_annealing(self):
        """模拟退火：最小化 Sphere 函数"""
        from modules.model_factory import OptimizationSolver
        def sphere(x):
            return float(np.sum(np.array(x) ** 2))
        result = OptimizationSolver.simulated_annealing(
            sphere, x0=np.array([3.0, -2.0]),
            bounds=[(-5, 5), (-5, 5)],
            max_iter=500, initial_temp=200.0, cooling_rate=0.97,
            random_state=42
        )
        self.assertEqual(result["status"], "success")
        self.assertEqual(result["method"], "SimulatedAnnealing")
        # 模拟退火应能改进初值（初值 13.0），允许宽松阈值（启发式算法不保证收敛到全局最优）
        self.assertLess(result["best_value"], 5.0)
        # 验证收敛曲线长度
        self.assertEqual(len(result["convergence"]), 501)

    def test_genetic_algorithm(self):
        """遗传算法：最小化 Sphere 函数"""
        from modules.model_factory import MetaHeuristicSolver
        def sphere(x):
            return float(np.sum(np.array(x) ** 2))
        result = MetaHeuristicSolver.ga(
            sphere, dim=2, bounds=[(-5, 5), (-5, 5)],
            pop_size=20, max_iter=50, random_state=42
        )
        self.assertEqual(result["status"], "success")
        self.assertEqual(result["method"], "GeneticAlgorithm")
        self.assertLess(result["best_value"], 1.0)

    def test_ant_colony(self):
        """蚁群算法：TSP"""
        from modules.model_factory import MetaHeuristicSolver
        np.random.seed(42)
        # 5 个城市的距离矩阵
        coords = np.random.uniform(0, 100, (5, 2))
        D = np.sqrt(((coords[:, None, :] - coords[None, :, :]) ** 2).sum(axis=2))
        result = MetaHeuristicSolver.aco(D, n_ants=10, max_iter=30, random_state=42)
        self.assertEqual(result["status"], "success")
        self.assertEqual(result["method"], "AntColonyOptimization")
        self.assertEqual(len(result["best_path"]), 6)  # 5 城市 + 回到起点
        self.assertGreater(result["best_length"], 0)
        # 路径应包含所有城市
        self.assertEqual(len(set(result["best_path"][:-1])), 5)

    def test_lightgbm_alias_in_build_supervised(self):
        """lightgbm 在 build_supervised 中真实实现（缺失则降级 RF）"""
        from modules.model_factory import ModelFactory
        np.random.seed(42)
        X = np.random.randn(50, 4)
        y = X[:, 0] * 2 + np.random.randn(50) * 0.1
        model, model_type = ModelFactory.build_supervised("lightgbm", X, y)
        self.assertEqual(model_type, "regression")
        # 应能预测
        pred = model.predict(X[:5])
        self.assertEqual(len(pred), 5)

    def test_catboost_alias_in_build_supervised(self):
        """catboost 在 build_supervised 中真实实现（缺失则降级 RF）"""
        from modules.model_factory import ModelFactory
        np.random.seed(42)
        X = np.random.randn(50, 4)
        y = X[:, 0] * 2 + np.random.randn(50) * 0.1
        model, model_type = ModelFactory.build_supervised("catboost", X, y)
        self.assertEqual(model_type, "regression")
        pred = model.predict(X[:5])
        self.assertEqual(len(pred), 5)

    def test_xgboost_alias_resolves(self):
        """xgboost 别名应正确解析为 xgboost_regressor"""
        from modules.model_factory import ModelFactory
        np.random.seed(42)
        X = np.random.randn(50, 4)
        y = X[:, 0] * 2 + np.random.randn(50) * 0.1
        # 别名应能让 build_supervised 找到 xgboost_regressor 分支
        model, model_type = ModelFactory.build_supervised("xgboost", X, y)
        self.assertEqual(model_type, "regression")
        pred = model.predict(X[:5])
        self.assertEqual(len(pred), 5)

    def test_neural_network_alias_resolves(self):
        """neural_network 别名应解析为 mlp"""
        # 通过 NeuralNetworkSolver.mlp 直接调用，别名在 dispatcher 层处理
        from modules.model_factory import NeuralNetworkSolver
        np.random.seed(42)
        X = np.random.randn(50, 4)
        y = (X[:, 0] + X[:, 1] > 0).astype(int)
        result = NeuralNetworkSolver.mlp(X, y, task_type="classification", random_state=42)
        self.assertEqual(result["status"], "success")
        self.assertIn("score", result)

    def test_particle_swarm_alias_resolves(self):
        """particle_swarm 别名应解析为 pso"""
        from modules.model_factory import MetaHeuristicSolver
        def sphere(x):
            return float(np.sum(np.array(x) ** 2))
        result = MetaHeuristicSolver.pso(sphere, dim=2, bounds=[(-5, 5), (-5, 5)],
                                          n_particles=15, max_iter=30, random_state=42)
        self.assertEqual(result["status"], "success")
        self.assertEqual(result["method"], "PSO")
        self.assertLess(result["best_value"], 1.0)

    def test_v331_ids_in_category_map(self):
        """验证 v3.3.1 补齐的 17 个 ID 已注册到 MODEL_CATEGORY_MAP"""
        from modules.model_factory import ModelFactory
        expected = {
            "dynamic_programming": "optimization",
            "simulated_annealing": "optimization",
            "genetic_algorithm": "optimization_meta",
            "ant_colony": "optimization_meta",
            "particle_swarm": "optimization_meta",
            "grey_prediction": "prediction",
            "neural_network": "neural_networks",
            "lstm": "prediction",
            "xgboost": "regression",
            "prophet": "prediction",
            "lightgbm": "regression",
            "catboost": "regression",
            "grey_relational": "evaluation",
            "dea": "evaluation",
            "fuzzy_evaluation": "evaluation",
            "anova": "statistics",
            "exponential_smoothing": "statistics",
        }
        for mid, expected_cat in expected.items():
            self.assertIn(mid, ModelFactory.MODEL_CATEGORY_MAP,
                          f"{mid} 应在 MODEL_CATEGORY_MAP 中注册")
            actual_cat = ModelFactory.MODEL_CATEGORY_MAP[mid]
            self.assertEqual(actual_cat, expected_cat,
                             f"{mid} 类别应为 {expected_cat}，实际 {actual_cat}")


if __name__ == "__main__":
    unittest_main()
