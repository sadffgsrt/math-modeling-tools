"""
数学建模竞赛工作流 - 模型验证模块测试
测试验证基础与高级功能
"""

import sys
from pathlib import Path
from unittest import TestCase, main as unittest_main

# 添加父目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

# 导入模块
from modules import validation


class TestValidation(TestCase):
    """测试模型验证模块"""

    def setUp(self):
        import numpy as np
        import pandas as pd

        np.random.seed(42)
        self.data = pd.DataFrame({
            'feature_1': np.random.randn(100),
            'feature_2': np.random.uniform(0, 10, 100),
            'target': np.random.randn(100)
        })

    def test_data_validation(self):
        """测试数据验证"""
        validator = validation.DataValidator()
        report = validator.validate_dataset(self.data, "test")

        self.assertIsNotNone(report)
        self.assertGreater(report.total_checks, 0)

    def test_validation_score_range(self):
        """测试验证分数范围"""
        validator = validation.DataValidator()
        report = validator.validate_dataset(self.data, "test")

        self.assertGreaterEqual(report.overall_score, 0)
        self.assertLessEqual(report.overall_score, 100)

    def test_validation_status(self):
        """测试验证状态"""
        validator = validation.DataValidator()
        report = validator.validate_dataset(self.data, "test")

        self.assertIn(report.overall_status, ["excellent", "good", "acceptable", "poor", "critical"])


class TestValidationAdvanced(TestCase):
    """测试验证模块高级功能"""

    def test_high_quality_data(self):
        """测试高质量数据验证"""
        from modules import validation
        import pandas as pd
        import numpy as np

        np.random.seed(42)
        df = pd.DataFrame({
            "x1": np.random.randn(100),
            "x2": np.random.randn(100),
            "target": np.random.randn(100)
        })

        validator = validation.DataValidator()
        report = validator.validate_dataset(df, "high_quality")

        self.assertGreater(report.overall_score, 80)

    def test_low_quality_data(self):
        """测试低质量数据验证"""
        from modules import validation
        import pandas as pd
        import numpy as np

        # 创建有大量缺失值的数据
        df = pd.DataFrame({
            "x1": [np.nan] * 50 + list(range(50)),
            "x2": list(range(50)) + [np.nan] * 50,
            "target": list(range(100))
        })

        validator = validation.DataValidator()
        report = validator.validate_dataset(df, "low_quality")

        # 应检测到质量问题
        self.assertLess(report.overall_score, 90)

    def test_paper_quality_validator(self):
        """测试论文质量检查器"""
        from modules import validation

        validator = validation.PaperQualityValidator()

        # 模拟输入数据
        paper_content = """
        # 数学建模论文

        ## 摘要
        本文研究了优化问题。

        ## 问题分析
        设x为决策变量。

        ## 模型建立
        选择线性规划模型。

        ## 结果分析
        R²=0.95，RMSE=0.05。

        ## 参考文献
        [1] 张三. 数学建模. 2020.
        """

        result = validator.validate_paper(
            paper_content=paper_content,
            problem_analysis={"problem_type": "optimization", "variables": [], "constraints": []},
            model_selection={"selected_model": {"name": "线性规划"}},
            solving_results={"metrics": {"r2": 0.95, "rmse": 0.05}},
            validation_results={},
            visualization_results={}
        )

        self.assertIsNotNone(result)
        self.assertGreater(result.overall_score, 0)

    def test_model_validator_from_results_r2(self):
        """测试基于结果的模型验证（R² 拟合优度，P1 新增）"""
        from modules import validation

        validator = validation.ModelValidator()
        # 优秀 R²
        checks = validator.validate_from_results(metrics={"r2": 0.9})
        self.assertTrue(any(c.check_id == "MC-001" and c.status == "passed" for c in checks))
        # 较差 R²
        checks = validator.validate_from_results(metrics={"r2": 0.1})
        self.assertTrue(any(c.check_id == "MC-001" and c.status == "failed" for c in checks))

    def test_model_validator_from_results_cv_and_normality(self):
        """测试基于结果的模型验证（CV 稳定性 + 残差正态性，P1 新增）"""
        import numpy as np
        from modules import validation

        validator = validation.ModelValidator()
        # CV 稳定
        checks = validator.validate_from_results(
            metrics={"r2": 0.8},
            cv_metrics={"cv_mean": 0.75, "cv_std": 0.05},
        )
        check_ids = {c.check_id for c in checks}
        self.assertIn("MC-001", check_ids)
        self.assertIn("MC-003", check_ids)
        self.assertTrue(any(c.check_id == "MC-003" and c.status == "passed" for c in checks))

        # 残差正态性（正态分布残差）
        np.random.seed(42)
        residuals = np.random.normal(0, 1, 100)
        checks = validator.validate_from_results(
            metrics={"r2": 0.8},
            residuals=residuals,
        )
        self.assertTrue(any(c.check_id == "MC-006" for c in checks))


if __name__ == "__main__":
    unittest_main()
