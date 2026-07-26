"""MM-Bench 式赛题基准测试（离线确定性 harness）。"""
import sys
from pathlib import Path
from unittest import TestCase, main as unittest_main

sys.path.insert(0, str(Path(__file__).parent.parent))

from tests.benchmarks.harness import BenchmarkHarness


class TestBenchmarks(TestCase):
    def setUp(self):
        self.harness = BenchmarkHarness(top_k=6, rounds=2)

    def test_problems_exist(self):
        problems = self.harness.list_problems()
        self.assertGreaterEqual(len(problems), 3)

    def test_run_single(self):
        p = self.harness.list_problems()[0]
        res = self.harness.run_problem(p)
        self.assertIsNotNone(res.problem_id)
        self.assertTrue(res.self_review_pass, msg="\n".join(res.self_review_notes))
        self.assertTrue(len(res.selected_top) > 0)

    def test_run_all_pass(self):
        report = self.harness.run_all()
        self.assertEqual(report.passed, report.total,
                         msg="存在未通过自审查的赛题：" +
                         ", ".join(r.problem_id for r in report.results
                                   if not r.self_review_pass))


if __name__ == "__main__":
    unittest_main()
