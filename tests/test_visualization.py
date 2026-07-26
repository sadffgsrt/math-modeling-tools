"""
数学建模竞赛工作流 - 结果可视化模块测试
测试所有可视化相关的核心功能
"""

# 设置非交互式后端，避免显示依赖
import matplotlib
matplotlib.use("Agg")

import sys
import tempfile
import shutil
import numpy as np
import pandas as pd
from pathlib import Path
from unittest import TestCase, main as unittest_main

# 添加父目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

# 导入模块
from modules import visualization


class TestVisualization(TestCase):
    """测试结果可视化模块"""

    def setUp(self):
        import numpy as np
        import pandas as pd

        np.random.seed(42)
        self.n_samples = 50
        self.X = np.random.randn(self.n_samples, 3)
        self.y = self.X[:, 0] + self.X[:, 1] + np.random.randn(self.n_samples) * 0.3
        self.y_pred = self.y + np.random.randn(self.n_samples) * 0.2
        self.data = pd.DataFrame(self.X, columns=['f1', 'f2', 'f3'])
        self.feature_importance = {'f1': 0.4, 'f2': 0.35, 'f3': 0.25}
        self.temp_dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.temp_dir)

    def test_create_figures(self):
        """测试创建图表"""
        visualizer = visualization.ModelVisualizer()
        result = visualizer.create_all_figures(
            self.data, self.y, self.y_pred,
            feature_names=['f1', 'f2', 'f3'],
            feature_importance=self.feature_importance,
            output_dir=self.temp_dir
        )

        self.assertIsNotNone(result)
        self.assertGreater(len(result.figures), 0)

    def test_figures_created(self):
        """测试图表文件创建"""
        visualizer = visualization.ModelVisualizer()
        result = visualizer.create_all_figures(
            self.data, self.y, self.y_pred,
            feature_names=['f1', 'f2', 'f3'],
            feature_importance=self.feature_importance,
            output_dir=self.temp_dir
        )

        for fig_path in result.figure_paths:
            self.assertTrue(Path(fig_path).exists())

    def test_create_scatter_plot(self):
        """测试散点图创建（真实值 vs 预测值）"""
        visualizer = visualization.ModelVisualizer()
        # 直接调用私有方法测试散点图生成
        fig_path = visualizer._plot_prediction_vs_actual(
            self.y, self.y_pred, Path(self.temp_dir)
        )
        self.assertIsNotNone(fig_path)
        self.assertTrue(fig_path.exists())
        self.assertGreater(fig_path.stat().st_size, 0)
        self.assertEqual(fig_path.suffix, '.png')

    def test_create_residual_plot(self):
        """测试残差图创建"""
        visualizer = visualization.ModelVisualizer()
        # 直接调用残差图绘制方法（包含直方图和 Q-Q 图）
        fig_path = visualizer._plot_residuals(
            self.y, self.y_pred, Path(self.temp_dir)
        )
        self.assertIsNotNone(fig_path)
        self.assertTrue(fig_path.exists())
        self.assertGreater(fig_path.stat().st_size, 0)
        self.assertEqual(fig_path.suffix, '.png')

    def test_create_feature_importance_plot(self):
        """测试特征重要性图"""
        visualizer = visualization.ModelVisualizer()
        fig_path = visualizer._plot_feature_importance(
            self.feature_importance, Path(self.temp_dir)
        )
        self.assertIsNotNone(fig_path)
        self.assertTrue(fig_path.exists())
        self.assertGreater(fig_path.stat().st_size, 0)
        self.assertEqual(fig_path.suffix, '.png')

    def test_create_distribution_plot(self):
        """测试分布图"""
        visualizer = visualization.ModelVisualizer()
        fig_path = visualizer._plot_data_distribution(
            self.data, ['f1', 'f2', 'f3'], Path(self.temp_dir)
        )
        self.assertIsNotNone(fig_path)
        self.assertTrue(fig_path.exists())
        self.assertGreater(fig_path.stat().st_size, 0)
        self.assertEqual(fig_path.suffix, '.png')

    def test_create_correlation_heatmap(self):
        """测试相关性热力图"""
        visualizer = visualization.ModelVisualizer()
        fig_path = visualizer._plot_correlation_heatmap(
            self.data, Path(self.temp_dir)
        )
        self.assertIsNotNone(fig_path)
        self.assertTrue(fig_path.exists())
        self.assertGreater(fig_path.stat().st_size, 0)
        self.assertEqual(fig_path.suffix, '.png')

    def test_empty_feature_importance(self):
        """测试无特征重要性时的处理"""
        visualizer = visualization.ModelVisualizer()
        # 不传 feature_importance，验证不会生成特征重要性图
        result = visualizer.create_all_figures(
            self.data, self.y, self.y_pred,
            feature_names=['f1', 'f2', 'f3'],
            feature_importance=None,
            output_dir=self.temp_dir
        )
        self.assertIsNotNone(result)
        # 确认图表列表中不包含 feature_importance
        fig_ids = [fig['id'] for fig in result.figures]
        self.assertNotIn('feature_importance', fig_ids)

    def test_single_feature(self):
        """测试单特征场景"""
        np.random.seed(42)
        X = np.random.randn(50, 1)
        y = X[:, 0] + np.random.randn(50) * 0.3
        y_pred = y + np.random.randn(50) * 0.2
        data = pd.DataFrame(X, columns=['f1'])
        visualizer = visualization.ModelVisualizer()
        result = visualizer.create_all_figures(
            data, y, y_pred,
            feature_names=['f1'],
            feature_importance={'f1': 1.0},
            output_dir=self.temp_dir
        )
        self.assertIsNotNone(result)
        self.assertGreater(len(result.figures), 0)
        for fig_path in result.figure_paths:
            self.assertTrue(Path(fig_path).exists())

    def test_large_dataset(self):
        """测试大数据集（1000+ 样本）"""
        np.random.seed(42)
        n_samples = 1500
        X = np.random.randn(n_samples, 4)
        y = X[:, 0] * 2 + X[:, 1] * 3 + np.random.randn(n_samples) * 0.5
        y_pred = y + np.random.randn(n_samples) * 0.3
        data = pd.DataFrame(X, columns=['f1', 'f2', 'f3', 'f4'])
        visualizer = visualization.ModelVisualizer()
        result = visualizer.create_all_figures(
            data, y, y_pred,
            feature_names=['f1', 'f2', 'f3', 'f4'],
            feature_importance={'f1': 0.4, 'f2': 0.3, 'f3': 0.2, 'f4': 0.1},
            output_dir=self.temp_dir
        )
        self.assertIsNotNone(result)
        self.assertEqual(len(result.figure_paths), len(result.figures))
        for fig_path in result.figure_paths:
            self.assertTrue(Path(fig_path).exists())
            self.assertGreater(Path(fig_path).stat().st_size, 0)

    def test_output_dir_creation(self):
        """测试输出目录自动创建"""
        nested_dir = Path(self.temp_dir) / "nested" / "figures"
        self.assertFalse(nested_dir.exists())
        visualizer = visualization.ModelVisualizer()
        result = visualizer.create_all_figures(
            self.data, self.y, self.y_pred,
            feature_names=['f1', 'f2', 'f3'],
            feature_importance=self.feature_importance,
            output_dir=str(nested_dir)
        )
        self.assertTrue(nested_dir.exists())
        self.assertGreater(len(result.figures), 0)

    def test_figure_file_formats(self):
        """测试图表文件格式（PNG）"""
        visualizer = visualization.ModelVisualizer()
        result = visualizer.create_all_figures(
            self.data, self.y, self.y_pred,
            feature_names=['f1', 'f2', 'f3'],
            feature_importance=self.feature_importance,
            output_dir=self.temp_dir
        )
        for fig_path in result.figure_paths:
            self.assertTrue(fig_path.endswith('.png'))
            self.assertEqual(Path(fig_path).suffix, '.png')

    def test_figure_metadata(self):
        """测试图表元数据（标题、轴标签等）"""
        visualizer = visualization.ModelVisualizer()
        result = visualizer.create_all_figures(
            self.data, self.y, self.y_pred,
            feature_names=['f1', 'f2', 'f3'],
            feature_importance=self.feature_importance,
            output_dir=self.temp_dir
        )
        # 验证每个图表的元数据字段完整
        for fig in result.figures:
            self.assertIn('id', fig)
            self.assertIn('title', fig)
            self.assertIn('type', fig)
            self.assertIn('path', fig)
            self.assertTrue(fig['title'])  # 标题非空
            self.assertTrue(fig['id'])     # ID 非空
        # 验证结果元数据
        self.assertIn('total_figures', result.metadata)
        self.assertEqual(result.metadata['total_figures'], len(result.figures))
        self.assertIn('output_dir', result.metadata)

    def test_model_visualizer_with_clustering(self):
        """测试聚类结果可视化"""
        np.random.seed(42)
        # 模拟聚类数据：3 个簇
        n_per_cluster = 30
        X = np.vstack([
            np.random.randn(n_per_cluster, 2) + np.array([0, 0]),
            np.random.randn(n_per_cluster, 2) + np.array([5, 5]),
            np.random.randn(n_per_cluster, 2) + np.array([-5, 5])
        ])
        cluster_labels = np.repeat([0, 1, 2], n_per_cluster)
        data = pd.DataFrame(X, columns=['x', 'y'])
        data['cluster'] = cluster_labels
        # 用簇中心作为"预测值"模拟聚类评估
        y_true = X[:, 0]
        centers = np.array([0.0, 5.0, -5.0])
        y_pred = centers[cluster_labels]
        visualizer = visualization.ModelVisualizer()
        result = visualizer.create_all_figures(
            data, y_true, y_pred,
            feature_names=['x', 'y', 'cluster'],
            feature_importance={'x': 0.6, 'y': 0.3, 'cluster': 0.1},
            output_dir=self.temp_dir
        )
        self.assertIsNotNone(result)
        self.assertGreater(len(result.figures), 0)
        # 验证相关性热力图包含 cluster 列
        fig_ids = [fig['id'] for fig in result.figures]
        self.assertIn('correlation_heatmap', fig_ids)

    def test_model_visualizer_with_time_series(self):
        """测试时序数据可视化"""
        np.random.seed(42)
        n = 100
        # 生成时序数据：趋势 + 季节 + 噪声
        dates = pd.date_range('2024-01-01', periods=n, freq='D')
        trend = np.linspace(0, 10, n)
        season = np.sin(np.linspace(0, 4 * np.pi, n)) * 2
        noise = np.random.randn(n) * 0.5
        y_true = trend + season + noise
        y_pred = trend + season  # 预测不含噪声
        data = pd.DataFrame({
            'value': y_true,
            'trend': trend,
            'day_index': np.arange(n)
        }, index=dates)
        visualizer = visualization.ModelVisualizer()
        result = visualizer.create_all_figures(
            data, y_true, y_pred,
            feature_names=['value', 'trend', 'day_index'],
            feature_importance={'value': 0.5, 'trend': 0.4, 'day_index': 0.1},
            output_dir=self.temp_dir
        )
        self.assertIsNotNone(result)
        self.assertGreater(len(result.figures), 0)
        # 验证误差随样本变化图存在（适合时序数据）
        fig_ids = [fig['id'] for fig in result.figures]
        self.assertIn('error_over_samples', fig_ids)


if __name__ == "__main__":
    unittest_main()
