"""
AgentMemory TF-IDF 语义检索测试
验证：子串命中优先（兼容），无命中时 TF-IDF 余弦相似兜底。
"""
import sys
import shutil
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


class TestAgentMemoryTFIDF(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        from modules.llm_agent.agent import AgentMemory
        self.mem = AgentMemory(Path(self.tmp) / "mem.json")

    def tearDown(self):
        try:
            shutil.rmtree(self.tmp)
        except OSError:
            pass

    def test_substring_match_kept(self):
        """子串命中优先（保持向后兼容）。"""
        self.mem.add_memory("optimization", "tool_a", "ok", True, {"overall_score": 8})
        r = self.mem.search_similar("optimization")
        self.assertEqual(len(r), 1)

    def test_tfidf_fallback_semantic(self):
        """无子串命中时 TF-IDF 词重叠命中相关记忆。"""
        self.mem.add_memory("prediction", "solve_regression", "预测回归结果", True, {"overall_score": 7})
        self.mem.add_memory("optimization", "solve_lp", "线性规划求解", True, {"overall_score": 6})
        # "回归预测" 非连续子串，但 TF-IDF 词重叠应命中 prediction 记忆
        r = self.mem.search_similar("回归预测")
        self.assertGreater(len(r), 0)
        # 首条应是 prediction（词重叠更多）
        self.assertEqual(r[0].get("problem_type"), "prediction")

    def test_no_match_returns_empty(self):
        """完全无相似时返回空。"""
        self.mem.add_memory("optimization", "tool_a", "ok", True, {})
        r = self.mem.search_similar("zzzqqq")
        self.assertEqual(len(r), 0)

    def test_tokenize_chinese_english(self):
        """分词：中文 2-gram + 英文词。"""
        from modules.llm_agent.agent import AgentMemory
        toks = AgentMemory._tokenize("线性回归 prediction")
        self.assertIn("线性", toks)
        self.assertIn("回归", toks)
        self.assertIn("prediction", toks)


if __name__ == "__main__":
    unittest.main()
