# 可视化前端操作封装（MM-Agent 可视化方法参考，确定性离线实现）
#
# MM-Agent 的 ChartCreator 用 LLM（CREATE_CHART_PROMPT）生成图表“代码”再执行，
# 属 LLM 操作、非确定性、且依赖外部 API。本报告此前将其判定为高风险项。
# 本项目的根本优势是“确定性、可控、离线可跑”，因此此处不复制 LLM 制图，
# 而是把既有的确定性 ModelVisualizer（12 种 matplotlib 图）封装为一键前端操作：
#   1) generate   —— 调用 ModelVisualizer 生成全部图表；
#   2) build_gallery —— 把产物编排成静态 HTML 画廊（缩略图+元信息），可直接浏览器打开；
#   3) serve      —— 启动轻量本地静态服务预览画廊（后台线程，可停止）；
#   4) serve_webui —— 可选接入既有 WebUIServer（需传入 workflow 对象）。
#
# 纯自研、MIT；build_gallery / serve 仅用标准库，无需 matplotlib，保证可 import。

import html
import os
import threading
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from typing import Any, Dict, List, Optional

from .visualizer import ModelVisualizer, VisualizationResult


class _QuietHandler(SimpleHTTPRequestHandler):
    """静默的静态文件处理器（不打印每条请求）。"""

    def log_message(self, *args, **kwargs):  # noqa: D401
        pass


class VisualizationOps:
    """可视化前端操作封装：生成 → 编排画廊 → 预览。"""

    def __init__(self, output_dir: str = "results/figures"):
        self.output_dir = output_dir
        self._server: Optional[HTTPServer] = None
        self._thread: Optional[threading.Thread] = None

    # ── 1) 生成图表（委托 ModelVisualizer，依赖 matplotlib/numpy/pandas）──
    def generate(self, data: Any = None, y_true: Any = None, y_pred: Any = None,
                 feature_names: Optional[List[str]] = None,
                 feature_importance: Optional[Dict[str, float]] = None,
                 output_dir: Optional[str] = None,
                 chart_types: Optional[List[str]] = None,
                 max_charts: Optional[int] = None,
                 user_pref: Optional[str] = None) -> VisualizationResult:
        """生成可视化图表，返回 VisualizationResult。

        参数与 ModelVisualizer.create_all_figures 一致；此外支持用户偏好驱动：
          - chart_types: 指定要生成的图表 id 白名单（如 ["pred_vs_actual","residuals"]）。
          - max_charts: 图表数量上限（模仿 MM-Agent create_charts 的 chart_num 意图）。
          - user_pref: 自然语言偏好（模仿 MM-Agent 的 user_prompt），确定性映射为 chart_types。
        缺失依赖时抛明确 ImportError。
        """
        out = output_dir or self.output_dir
        # 用户偏好（user_pref）确定性映射为图表类型（替代 LLM 的 prompt 理解）
        if chart_types is None and user_pref:
            chart_types = pref_to_chart_types(user_pref)
        viz = ModelVisualizer()
        result = viz.create_all_figures(
            data=data, y_true=y_true, y_pred=y_pred,
            feature_names=feature_names, feature_importance=feature_importance,
            output_dir=out, chart_types=chart_types,
        )
        # 数量上限（chart_num 意图）：按已生成顺序截断
        if max_charts is not None and len(result.figures) > max_charts:
            result.figures = result.figures[:max_charts]
            result.figure_paths = [f["path"] for f in result.figures]
            result.metadata["total_figures"] = len(result.figures)
        viz.save_result(result, out)
        viz.generate_report_md(result, Path(out) / "visualization_report.md")
        return result

    # ── 2) 编排静态 HTML 画廊（纯标准库，无需 matplotlib）──
    def build_gallery(self, result: VisualizationResult,
                      title: str = "建模结果可视化画廊",
                      output_dir: Optional[str] = None) -> Path:
        """把 VisualizationResult 编排为可浏览器打开的 gallery.html。

        返回画廊文件路径。该文件相对引用各图表，离线可直接打开。
        """
        out = Path(output_dir or result.metadata.get("output_dir") or self.output_dir)
        out.mkdir(parents=True, exist_ok=True)

        cards = []
        for fig in result.figures:
            rel = os.path.relpath(fig["path"], out)
            cards.append(
                f'<div class="card">'
                f'<a href="{html.escape(rel)}" target="_blank">'
                f'<img src="{html.escape(rel)}" alt="{html.escape(fig["title"])}" loading="lazy"/></a>'
                f'<div class="meta"><b>{html.escape(fig["title"])}</b>'
                f'<span class="tag">{html.escape(fig["type"])}</span></div>'
                f'<div class="path">{html.escape(fig["path"])}</div>'
                f'</div>'
            )
        cards_html = "\n".join(cards) if cards else '<p class="empty">本次未生成图表。</p>'

        gallery = _GALLERY_TEMPLATE.replace("{{TITLE}}", html.escape(title))
        gallery = gallery.replace("{{COUNT}}", str(len(result.figures)))
        gallery = gallery.replace("{{CARDS}}", cards_html)
        gallery = gallery.replace("{{RID}}", html.escape(result.result_id))

        gallery_path = out / "gallery.html"
        gallery_path.write_text(gallery, encoding="utf-8")
        return gallery_path

    # ── 3) 启动轻量静态服务预览画廊（后台线程）──
    def serve(self, gallery_path: Optional[str] = None,
              host: str = "127.0.0.1", port: int = 8090) -> str:
        """启动本地静态服务预览画廊，返回访问 URL。

        gallery_path 缺省时尝试 output_dir/gallery.html。
        """
        if gallery_path is None:
            gallery_path = Path(self.output_dir) / "gallery.html"
        gallery_path = Path(gallery_path)
        if not gallery_path.exists():
            raise FileNotFoundError(f"画廊文件不存在：{gallery_path}，请先 build_gallery。")

        serve_root = str(gallery_path.parent)
        handler = lambda *a, **k: _QuietHandler(*a, directory=serve_root, **k)  # noqa: E731

        self._server = HTTPServer((host, port), handler)
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()
        url = f"http://{host}:{port}/{gallery_path.name}"
        return url

    def stop(self) -> None:
        """停止静态预览服务。"""
        if self._server is not None:
            self._server.shutdown()
            self._server.server_close()
            self._server = None
            self._thread = None

    # ── 4) 可选：接入既有 WebUIServer（需 workflow 对象）──
    def serve_webui(self, workflow: Any, host: str = "127.0.0.1",
                    port: int = 8080, auto_open: bool = False, api_key: Optional[str] = None):
        """启动既有的 WebUI 服务（需要 workflow 实例）。返回 WebUIServer。"""
        from .web_ui import create_web_ui  # 延迟导入，避免循环依赖
        server = create_web_ui(workflow, host=host, port=port,
                               auto_open=auto_open, api_key=api_key)
        server.start_background()
        return server


# ─────────────────────────────────────────────────────────────
# 画廊 HTML 模板
# ─────────────────────────────────────────────────────────────
_GALLERY_TEMPLATE = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>{{TITLE}}</title>
<style>
  :root { color-scheme: light; }
  body { font-family: -apple-system, "Microsoft YaHei", system-ui, sans-serif;
         margin: 0; background: #f5f7fa; color: #1f2933; }
  header { background: #1f3a5f; color: #fff; padding: 18px 24px; }
  header h1 { margin: 0; font-size: 20px; }
  header .sub { opacity: .8; font-size: 13px; margin-top: 4px; }
  main { max-width: 1100px; margin: 24px auto; padding: 0 16px; }
  .grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
          gap: 18px; }
  .card { background: #fff; border-radius: 10px; overflow: hidden;
          box-shadow: 0 1px 4px rgba(0,0,0,.08); transition: transform .15s; }
  .card:hover { transform: translateY(-3px); }
  .card img { width: 100%; height: 200px; object-fit: contain; background: #fafbfc; }
  .meta { padding: 10px 12px 2px; font-size: 15px; }
  .tag { display: inline-block; margin-left: 8px; font-size: 12px; color: #2563eb;
         background: #eaf1ff; border-radius: 6px; padding: 1px 7px; }
  .path { padding: 0 12px 12px; font-size: 11px; color: #8a94a6; word-break: break-all; }
  .empty { color: #8a94a6; }
</style>
</head>
<body>
<header>
  <h1>{{TITLE}}</h1>
  <div class="sub">共 {{COUNT}} 张图表 · 结果ID {{RID}}</div>
</header>
<main>
  <div class="grid">{{CARDS}}</div>
</main>
</body>
</html>
"""


# ─────────────────────────────────────────────────────────────
# 便捷入口
# ─────────────────────────────────────────────────────────────
def build_visualization_gallery(result: VisualizationResult,
                                 title: str = "建模结果可视化画廊",
                                 output_dir: Optional[str] = None) -> Path:
    """一行式：把 VisualizationResult 编排为画廊 HTML。"""
    return VisualizationOps().build_gallery(result, title=title, output_dir=output_dir)


# ─────────────────────────────────────────────────────────────
# 用户偏好 → 图表类型（确定性映射，模仿 MM-Agent create_charts 的 user_prompt 选图意图）
# 不依赖 LLM：用中文关键词命中，由用户描述想要的图，而非让模型生成绘图代码。
# ─────────────────────────────────────────────────────────────
_PREF_KEYWORDS: Dict[str, List[str]] = {
    "pred_vs_actual": ["预测", "趋势", "拟合", "回归", "实际", "对比", "predict"],
    "error_over_samples": ["误差", "趋势", "随样本", "变化", "预测", "error"],
    "residuals": ["残差", "误差", "分布", "诊断", "residual"],
    "feature_importance": ["重要", "贡献", "权重", "特征", "排序", "importance"],
    "data_distribution": ["分布", "直方", "数据", "特征", "distribution"],
    "correlation_heatmap": ["相关", "关联", "热力", "矩阵", "correlation"],
    "boxplot": ["箱线", "箱", "分布", "离群", "四分位", "box"],
}


def pref_to_chart_types(user_pref: str) -> Optional[List[str]]:
    """把用户自然语言偏好（user_pref）确定性映射为图表 id 列表。

    对应 MM-Agent ``ChartCreator.create_charts(paper_content, chart_num, user_prompt)``
    中 user_prompt 的作用——由用户描述想要的图。本函数用关键词命中取并集，
    命中则返回有序 id 列表，未命中返回 None（交由上层生成全部可用图）。
    """
    if not user_pref:
        return None
    text = user_pref.lower()
    hits: set = set()
    for cid, kws in _PREF_KEYWORDS.items():
        for kw in kws:
            if kw in text:
                hits.add(cid)
                break
    return sorted(hits) if hits else None


__all__ = ["VisualizationOps", "build_visualization_gallery", "pref_to_chart_types"]
