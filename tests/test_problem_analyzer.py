"""
数学建模竞赛工作流 - 题目解析模块测试
测试所有题目解析相关的核心功能
"""

import sys
import tempfile
from pathlib import Path
from unittest import TestCase, main as unittest_main

# 添加父目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

# 导入模块
from modules import problem_analysis


class TestProblemAnalyzer(TestCase):
    """测试题目解析模块"""

    def setUp(self):
        self.analyzer = problem_analysis.ProblemAnalyzer()
        self.sample_text = """
        问题一：生产调度优化问题

        某工厂有若干加工工位，需要调度作业顺序。
        设作业当前位置为x，需要访问的工位为y_i。
        设备移动速度为v，每个工位的加工时间为t_i。

        约束条件：
        1. 设备只能沿轨道单向移动
        2. 每个工位同一时间只能被一台设备访问
        3. 加工过程中不能中断

        目标：最小化总完成时间
        """

    def test_analyze_problem_type(self):
        """测试题目类型识别"""
        result = self.analyzer.analyze_problem(self.sample_text)
        self.assertEqual(result.problem_type, "optimization")
        self.assertEqual(result.problem_type_cn, "优化类")

    def test_analyze_extracts_variables(self):
        """测试变量提取"""
        result = self.analyzer.analyze_problem(self.sample_text)
        self.assertGreater(len(result.variables), 0)

    def test_analyze_extracts_constraints(self):
        """测试约束条件提取"""
        result = self.analyzer.analyze_problem(self.sample_text)
        self.assertGreater(len(result.constraints), 0)

    def test_analyze_generates_sub_problems(self):
        """测试子问题生成"""
        result = self.analyzer.analyze_problem(self.sample_text)
        self.assertGreater(len(result.sub_problems), 0)

    def test_difficulty_assessment(self):
        """测试难度评估"""
        result = self.analyzer.analyze_problem(self.sample_text)
        self.assertIn(result.difficulty_level, ["easy", "medium", "hard"])

    def test_read_txt_file(self):
        """测试TXT文件读取"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False,
                                         encoding='utf-8') as f:
            f.write(self.sample_text)
            temp_path = f.name

        try:
            text = self.analyzer.read_problem_file(temp_path)
            self.assertIn("调度", text)
        finally:
            Path(temp_path).unlink()

    def test_read_nonexistent_file(self):
        """测试读取不存在的文件"""
        with self.assertRaises(FileNotFoundError):
            self.analyzer.read_problem_file("/nonexistent/file.txt")


if __name__ == "__main__":
    unittest_main()
