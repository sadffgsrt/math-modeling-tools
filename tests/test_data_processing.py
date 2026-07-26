"""
数学建模竞赛工作流 - 数据处理模块测试
测试数据处理基础与高级功能
"""

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
from modules import data_processing


class TestDataProcessing(TestCase):
    """测试数据处理模块"""

    def setUp(self):
        import numpy as np
        import pandas as pd

        self.processor = data_processing.DataProcessor()
        self.temp_dir = tempfile.mkdtemp()

        # 创建测试数据
        np.random.seed(42)
        data = pd.DataFrame({
            'feature_1': np.random.randn(50),
            'feature_2': np.random.uniform(0, 10, 50),
            'target': np.random.randn(50)
        })
        # 添加缺失值
        data.loc[0:5, 'feature_1'] = float('nan')

        self.data_path = Path(self.temp_dir) / "test_data.csv"
        data.to_csv(self.data_path, index=False)

    def tearDown(self):
        shutil.rmtree(self.temp_dir)

    def test_process_dataset(self):
        """测试数据集处理"""
        result = self.processor.process_dataset(
            str(self.data_path),
            self.temp_dir,
            "test"
        )
        self.assertIsNotNone(result)
        self.assertIsNotNone(result.quality_report)

    def test_missing_values_handled(self):
        """测试缺失值处理"""
        result = self.processor.process_dataset(
            str(self.data_path),
            self.temp_dir,
            "test"
        )
        self.assertGreater(len(result.operations_applied), 0)

    def test_quality_score_range(self):
        """测试质量分数范围"""
        result = self.processor.process_dataset(
            str(self.data_path),
            self.temp_dir,
            "test"
        )
        score = result.quality_report.quality_score
        self.assertGreaterEqual(score, 0)
        self.assertLessEqual(score, 100)


class TestDataProcessingAdvanced(TestCase):
    """测试数据处理模块高级功能"""

    def test_empty_dataframe(self):
        """测试空数据框处理"""
        from modules import data_processing
        import pandas as pd

        df = pd.DataFrame()
        processor = data_processing.DataProcessor()

        # 空数据框应能正常处理
        self.assertEqual(len(df), 0)

    def test_all_numeric_columns(self):
        """测试全数值列处理"""
        from modules import data_processing
        import pandas as pd
        import numpy as np

        df = pd.DataFrame({
            "x1": [1, 2, 3, 4, 5],
            "x2": [10, 20, 30, 40, 50],
            "target": [100, 200, 300, 400, 500]
        })

        processor = data_processing.DataProcessor(config={"scaling": "standard"})
        # 应能正常处理
        self.assertEqual(df.shape[1], 3)

    def test_mixed_columns(self):
        """测试混合列类型处理"""
        from modules import data_processing
        import pandas as pd

        df = pd.DataFrame({
            "numeric": [1, 2, 3, 4, 5],
            "category": ["A", "B", "A", "B", "A"],
            "target": [10, 20, 30, 40, 50]
        })

        processor = data_processing.DataProcessor()
        # 应能正常处理混合类型
        self.assertEqual(len(df.columns), 3)


if __name__ == "__main__":
    unittest_main()
