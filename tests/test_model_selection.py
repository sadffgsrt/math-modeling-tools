"""
数学建模竞赛工作流 - 模型选型模块测试
测试所有模型选型相关的核心功能
"""

import sys
from pathlib import Path
from unittest import TestCase, main as unittest_main

# 添加父目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

# 导入模块
from modules import model_selection


class TestModelSelection(TestCase):
    """测试模型选型模块"""

    def setUp(self):
        self.selector = model_selection.ModelSelector()
        self.sample_analysis = {
            "problem_id": "TEST-001",
            "problem_type": "optimization",
            "problem_type_cn": "优化类",
            "difficulty_level": "medium",
            "metadata": {
                "variables_count": 8,
                "constraints_count": 5
            }
        }

    def test_select_model_returns_result(self):
        """测试模型选型返回结果"""
        result = self.selector.select_model(self.sample_analysis)
        self.assertIsNotNone(result)
        self.assertIsNotNone(result.selected_model)

    def test_selected_model_has_name(self):
        """测试选中模型有名称"""
        result = self.selector.select_model(self.sample_analysis)
        self.assertTrue(len(result.selected_model.name_cn) > 0)

    def test_candidates_list(self):
        """测试候选模型列表"""
        result = self.selector.select_model(self.sample_analysis)
        self.assertGreater(len(result.candidate_models), 0)

    def test_suitability_score_range(self):
        """测试适配分数范围"""
        result = self.selector.select_model(self.sample_analysis)
        score = result.selected_model.suitability_score
        self.assertGreaterEqual(score, 0)
        self.assertLessEqual(score, 100)


if __name__ == "__main__":
    unittest_main()
