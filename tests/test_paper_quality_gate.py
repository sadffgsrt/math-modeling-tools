"""#44 审查门禁化 + #45 多视角审查机制的单元测试。"""
import unittest

from modules.validation.validator import (
    PaperQualityValidator,
    ValidationReport,
    ReviewGateError,
    gate_review,
)


class TestMultiPerspective(unittest.TestCase):
    def setUp(self):
        self.v = PaperQualityValidator()
        self.paper = "变量 x 已定义。模型假设合理。图1 展示了结果。"
        self.pa = {"variables": [{"symbol": "x"}]}
        self.empty = {}, {}, {}, {}, {}

    def test_list_perspectives_has_8(self):
        ps = PaperQualityValidator.list_perspectives()
        self.assertEqual(len(ps), 8)
        self.assertIn("format", ps)
        self.assertIn("numerical_consistency", ps)

    def test_default_runs_all(self):
        r = self.v.validate_paper(self.paper, self.pa, *self.empty)
        self.assertEqual(set(r.metadata["perspectives"]), set(PaperQualityValidator.PERSPECTIVES))

    def test_subset_perspective(self):
        r = self.v.validate_paper(
            self.paper, self.pa, *self.empty, perspectives=["format", "standards"]
        )
        self.assertEqual(set(r.metadata["perspectives"]), {"format", "standards"})

    def test_unknown_perspective_falls_back(self):
        r = self.v.validate_paper(
            self.paper, self.pa, *self.empty, perspectives=["nonexistent"]
        )
        self.assertEqual(len(r.metadata["perspectives"]), 8)


class TestGate(unittest.TestCase):
    def _report(self, score, status):
        return ValidationReport(
            report_id="T", validation_type="paper_quality", total_checks=1,
            passed_checks=1, warning_checks=0, failed_checks=0,
            overall_score=score, overall_status=status, checks=[],
            summary="s", recommendations=[], created_at="", metadata={},
        )

    def test_pass(self):
        r = gate_review(self._report(90, "good"))
        self.assertEqual(r.overall_score, 90)

    def test_fail_low_score(self):
        with self.assertRaises(ReviewGateError):
            gate_review(self._report(50, "acceptable"), threshold=60.0)

    def test_fail_critical(self):
        with self.assertRaises(ReviewGateError):
            gate_review(self._report(80, "critical"))

    def test_fail_poor_blocked(self):
        with self.assertRaises(ReviewGateError):
            gate_review(self._report(70, "poor"))


if __name__ == "__main__":
    unittest.main()
