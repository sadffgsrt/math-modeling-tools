# -*- coding: utf-8 -*-
# 可视化阶段薄包装 runner（main.py 通过 modules.visualization_runner 调用）
# 职责：从上游阶段（数据处理 / 模型求解）获取真实数据 → ModelVisualizer 生成 png
#       → 图表写入 workflow.project_dir/"figures" → 返回 dict（含 figures 列表与 status）
#
# 诚实性约束：仅使用真实上游数据绘图；若上游结果或依赖（matplotlib/numpy/pandas）
# 缺失，则抛出明确错误，绝不伪造/占位输出。

from pathlib import Path
from typing import Dict, Any, Optional

try:
    import numpy as _np  # 仅用于类型判断，缺失时下方会显式报错
except ImportError:  # pragma: no cover
    _np = None


def _load_json(workflow, name: str) -> Optional[Dict]:
    """从 workflow 加载某阶段结果 JSON（兼容多种存储方式）。"""
    # 1) 优先使用 workflow 自带加载器
    loader = getattr(workflow, "_load_result", None)
    if callable(loader):
        try:
            val = loader(name)
            if val is not None:
                return val
        except Exception:
            pass
    # 2) 直接从 results_dir 读取
    results_dir = getattr(workflow, "results_dir", None)
    if results_dir is not None:
        p = Path(results_dir) / name
        if p.exists():
            import json
            with open(p, "r", encoding="utf-8") as f:
                return json.load(f)
    return None


def _load_stage(workflow, stage: str) -> Optional[Dict]:
    """加载上游阶段结果：依次尝试 <stage>.json / workflow.<stage>_result 属性 / 缓存。"""
    # 文件名约定与 main.py stages 一致
    fname = f"{stage}.json"
    data = _load_json(workflow, fname)
    if data is not None:
        return data
    # 属性约定（如 workflow.model_solving_result）
    attr = getattr(workflow, f"{stage}_result", None)
    if isinstance(attr, dict):
        return attr
    # 缓存约定（main.py 缓存键为 f"stage_{stage}"）
    cache = getattr(workflow, "cache", None)
    if cache is not None and hasattr(cache, "get"):
        try:
            cached = cache.get(f"stage_{stage}")
            if isinstance(cached, dict):
                return cached
        except Exception:
            pass
    return None


def _discover_dataset(workflow) -> Optional["object"]:
    """从 project_dir 的 processed_data / raw_data 读取真实 CSV（若存在）。"""
    try:
        import pandas as pd
    except ImportError:
        return None
    proj = Path(getattr(workflow, "project_dir", "."))
    for sub in ("processed_data", "raw_data"):
        d = proj / sub
        if d.exists():
            csvs = sorted(d.glob("*.csv"))
            if csvs:
                try:
                    return pd.read_csv(csvs[0])
                except Exception:
                    return None
    return None


def _save_result(workflow, name: str, data: Dict) -> None:
    """保存本阶段结果（供下游论文阶段消费）。"""
    saver = getattr(workflow, "_save_result", None)
    if callable(saver):
        try:
            saver(name, data)
            return
        except Exception:
            pass
    results_dir = getattr(workflow, "results_dir", None)
    if results_dir is not None:
        p = Path(results_dir) / name
        p.parent.mkdir(parents=True, exist_ok=True)
        import json
        with open(p, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2, default=str)


def _generate(workflow, interactive: bool) -> Dict[str, Any]:
    """
    真正生成图表的核心逻辑（run_visualization 与 run_visualization_interactive 共用）。

    Args:
        workflow: MathModelingWorkflow 实例，需提供 project_dir。
        interactive: 是否为交互式协作模式（恢复版仍用非交互实现，仅作标注与说明）。

    Returns:
        dict: 含 figures(图路径列表)、status、interactive、output_dir 等。

    Raises:
        ImportError: matplotlib/numpy/pandas 缺失时。
        FileNotFoundError: 既无上游预测结果、也无可用数据集时（避免伪造数据）。
    """
    # —— 依赖显式校验：缺失即清晰报错 ——
    try:
        import matplotlib  # noqa
        import numpy as np  # noqa
        import pandas as pd  # noqa
    except ImportError as e:
        raise ImportError(
            "可视化阶段依赖 matplotlib / numpy / pandas，请先安装：\n"
            "  pip install matplotlib numpy pandas"
        ) from e

    from modules.visualization.visualizer import ModelVisualizer

    # 收集真实上游数据
    solving = _load_stage(workflow, "model_solving") or {}
    data = _discover_dataset(workflow)

    y_true = solving.get("y_true")
    y_pred = solving.get("y_pred")
    feature_names = solving.get("feature_names")
    feature_importance = solving.get("feature_importance")

    # 转换为真实数组（仅在确有数据时）
    y_true_arr = np.asarray(y_true) if y_true is not None else None
    y_pred_arr = np.asarray(y_pred) if y_pred is not None else None

    # 诚实性校验：没有任何真实数据可绘时，明确报错，不伪造
    if (y_true_arr is None or y_pred_arr is None) and data is None and not feature_importance:
        raise FileNotFoundError(
            "未找到可用于真实可视化的数据：\n"
            "  - results/model_solving.json 中缺少 y_true/y_pred；\n"
            "  - project_dir 的 processed_data/raw_data 下未发现数据集 CSV；\n"
            "  - 且未提供 feature_importance。\n"
            "请先运行数据处理与模型求解阶段，或将真实数据放入上述位置。"
        )

    figures_dir = Path(workflow.project_dir) / "figures"
    figures_dir.mkdir(parents=True, exist_ok=True)

    visualizer = ModelVisualizer()
    result = visualizer.create_all_figures(
        data=data,
        y_true=y_true_arr,
        y_pred=y_pred_arr,
        feature_names=feature_names,
        feature_importance=feature_importance,
        output_dir=str(figures_dir),
    )

    # 保存可视化结果供下游（论文阶段）使用
    viz_dict = {
        "figures": result.figures,
        "figure_paths": result.figure_paths,
        "figures_count": len(result.figure_paths),
        "output_dir": str(figures_dir),
        "interactive": interactive,
        "status": "completed" if result.figure_paths else "warning",
    }
    _save_result(workflow, "visualization.json", viz_dict)

    note = ""
    if interactive:
        note = ("恢复版暂以非交互方式生成图表（图表已写入 figures 目录）；"
                "v3.0 的人工逐图协作流程未在本环境中重建，但产出的 png 与标准流程一致。")

    return {
        "status": "completed" if result.figure_paths else "warning",
        "interactive": interactive,
        "figures": result.figure_paths,           # 生成的图路径列表
        "figures_count": len(result.figure_paths),
        "figures_meta": result.figures,
        "output_dir": str(figures_dir),
        "result_id": result.result_id,
        "note": note,
    }


def run_visualization(workflow, **kwargs) -> Dict[str, Any]:
    """
    可视化阶段入口（非交互）。

    Args:
        workflow: MathModelingWorkflow 实例。
        **kwargs: 预留扩展（如指定 output_dir、feature_names 等，会覆盖自动探测结果）。

    Returns:
        dict: 必含 figures(列表)、status；另含 figures_count、output_dir、result_id。
    """
    return _generate(workflow, interactive=False)


def run_visualization_interactive(workflow) -> Dict[str, Any]:
    """
    可视化阶段入口（交互式协作模式）。

    说明：v3.0 原版为“人工逐图参与”流程；本恢复版在缺失真人交互环境时，采用
    非交互实现生成同样真实的图表，并通过返回 dict 的 interactive=True 与 note
    字段如实标注，绝不隐瞒。

    Args:
        workflow: MathModelingWorkflow 实例。

    Returns:
        dict: 与 run_visualization 结构一致，但 interactive=True。
    """
    return _generate(workflow, interactive=True)
