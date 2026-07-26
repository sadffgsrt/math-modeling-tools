"""可视化前端操作封装测试（画廊编排，纯标准库、无需 matplotlib）。"""
import sys
import tempfile
from pathlib import Path
from unittest import TestCase, main as unittest_main

sys.path.insert(0, str(Path(__file__).parent.parent))

from modules.visualization import VisualizationOps, VisualizationResult


def _fake_result(tmp: Path):
    # 手工构造 VisualizationResult（不经过 matplotlib）
    f1 = tmp / "pred_vs_actual.png"
    f2 = tmp / "residuals.png"
    f1.write_text("x", encoding="utf-8")
    f2.write_text("x", encoding="utf-8")
    return VisualizationResult(
        result_id="VR-TEST",
        figures=[
            {"id": "pred_vs_actual", "title": "预测值 vs 真实值", "type": "scatter", "path": str(f1)},
            {"id": "residuals", "title": "残差分布", "type": "histogram", "path": str(f2)},
        ],
        figure_paths=[str(f1), str(f2)],
        created_at="2026-07-26T00:00:00",
        metadata={"total_figures": 2, "output_dir": str(tmp)},
    )


class TestVisualizationOps(TestCase):
    def test_build_gallery(self):
        with tempfile.TemporaryDirectory() as d:
            tmp = Path(d)
            result = _fake_result(tmp)
            ops = VisualizationOps(output_dir=str(tmp))
            gallery = ops.build_gallery(result, title="测试画廊")
            self.assertTrue(gallery.exists())
            html_text = gallery.read_text(encoding="utf-8")
            self.assertIn("预测值 vs 真实值", html_text)
            self.assertIn("pred_vs_actual.png", html_text)
            self.assertIn("共 2 张图表", html_text)

    def test_serve_and_stop(self):
        with tempfile.TemporaryDirectory() as d:
            tmp = Path(d)
            result = _fake_result(tmp)
            ops = VisualizationOps(output_dir=str(tmp))
            gallery = ops.build_gallery(result)
            url = ops.serve(gallery_path=str(gallery), port=18099)
            self.assertTrue(url.startswith("http://"))
            ops.stop()
            self.assertIsNone(ops._server)


if __name__ == "__main__":
    unittest_main()
