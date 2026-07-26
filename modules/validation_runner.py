# -*- coding: utf-8 -*-
# 验证阶段薄包装 runner（main.py 通过 modules.validation_runner 调用）
# 职责：从上游（数据处理 / 模型求解）获取真实数据 → DataValidator / ModelValidator
#       执行真实校验 → 返回 dict（含 status 与各项指标）。
#
# 诚实性约束：仅基于真实数据计算；依赖（numpy/pandas）缺失时清晰报错；scipy/sklearn
# 缺失时对应检查项降级为 warning。若上游结果不可得，如实说明并跳过相应校验，绝不伪造。

from pathlib import Path
from typing import Dict, Any, Optional, List

try:
    import numpy as _np
except ImportError:  # pragma: no cover
    _np = None


def _load_json(workflow, name: str) -> Optional[Dict]:
    loader = getattr(workflow, "_load_result", None)
    if callable(loader):
        try:
            val = loader(name)
            if val is not None:
                return val
        except Exception:
            pass
    results_dir = getattr(workflow, "results_dir", None)
    if results_dir is not None:
        p = Path(results_dir) / name
        if p.exists():
            import json
            with open(p, "r", encoding="utf-8") as f:
                return json.load(f)
    return None


def _load_stage(workflow, stage: str) -> Optional[Dict]:
    fname = f"{stage}.json"
    data = _load_json(workflow, fname)
    if data is not None:
        return data
    attr = getattr(workflow, f"{stage}_result", None)
    if isinstance(attr, dict):
        return attr
    cache = getattr(workflow, "cache", None)
    if cache is not None and hasattr(cache, "get"):
        try:
            cached = cache.get(f"stage_{stage}")
            if isinstance(cached, dict):
                return cached
        except Exception:
            pass
    return None


def _discover_dataset(workflow):
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


class _StoredPredictions:
    """
    轻量预测适配器：用上游真实预测结果 y_pred 实现 model.predict(X)。
    仅用于“仅有真实预测值、无可用模型对象”的场景，避免伪造数据。
    注意：交叉验证对适配器无意义（predict 忽略 X 返回已存储预测），对应检查项会由
    ModelValidator 降级为 warning，不产出任何伪造指标。
    """

    def __init__(self, y_pred):
        self._y_pred = _np.asarray(y_pred)

    def fit(self, X, y):
        return self

    def predict(self, X):
        n = X.shape[0] if hasattr(X, "shape") else len(X)
        return self._y_pred[:n]


def run_validation(workflow, **kwargs) -> Dict[str, Any]:
    """
    验证阶段入口。

    Args:
        workflow: MathModelingWorkflow 实例。
        **kwargs: 预留（如覆盖 data / y_true / y_pred）。

    Returns:
        dict: 必含 status、metrics（含 data_score / model_score / overall_score 等）。
        status 取值：completed（至少完成数据或模型校验）/ partial（部分缺失）/ failed（异常）。
    """
    if _np is None:
        raise ImportError(
            "验证阶段依赖 numpy / pandas，请先安装：\n"
            "  pip install numpy pandas"
        )
    import numpy as np

    from modules.validation.validator import DataValidator, ModelValidator

    metrics: Dict[str, Any] = {
        "data": None,
        "model": None,
        "overall_score": None,
        "overall_status": None,
    }
    notes: List[str] = []

    # —— 数据验证（基于真实数据集）——
    data = kwargs.get("data") or _discover_dataset(workflow)
    data_report = None
    if data is not None:
        dv = DataValidator()
        data_report = dv.validate_dataset(data, dataset_name="dataset")
        metrics["data"] = {
            "score": data_report.overall_score,
            "status": data_report.overall_status,
            "passed": data_report.passed_checks,
            "warning": data_report.warning_checks,
            "failed": data_report.failed_checks,
            "total_checks": data_report.total_checks,
        }
    else:
        notes.append("未发现数据集（processed_data/raw_data 无 CSV），跳过数据验证。")

    # —— 模型验证（基于真实 y_true / y_pred）——
    solving = kwargs.get("solving") or _load_stage(workflow, "model_solving") or {}
    y_true = solving.get("y_true")
    y_pred = solving.get("y_pred")
    model_report = None
    if y_true is not None and y_pred is not None:
        mv = ModelValidator()
        y_true_arr = np.asarray(y_true)
        y_pred_arr = np.asarray(y_pred)
        # 优先尝试加载真实模型对象（joblib）；否则用真实预测值构造适配器
        model_obj = None
        model_path = solving.get("model_path")
        if model_path:
            try:
                import joblib
                model_obj = joblib.load(model_path)
            except Exception:
                model_obj = None
        if model_obj is not None and hasattr(model_obj, "predict"):
            adapter = model_obj
            real_model = True
        else:
            adapter = _StoredPredictions(y_pred_arr)
            real_model = False
        X = np.zeros((len(y_true_arr), 1))  # 适配器忽略 X；真实模型若需要特征可后续扩展
        feature_names = solving.get("feature_names")
        model_report = mv.validate_model(
            adapter, X, y_true_arr,
            model_name=solving.get("model_name", "model"),
            feature_names=feature_names,
            real_model=real_model,
        )
        metrics["model"] = {
            "score": model_report.overall_score,
            "status": model_report.overall_status,
            "passed": model_report.passed_checks,
            "warning": model_report.warning_checks,
            "failed": model_report.failed_checks,
            "total_checks": model_report.total_checks,
            "r2": next((c.details.get("r2") for c in model_report.checks
                        if c.check_id == "MC-001" and "r2" in c.details), None),
        }
    else:
        notes.append("results/model_solving.json 缺少 y_true/y_pred，跳过模型验证（不伪造指标）。")

    # —— 综合评分 ——
    data_score = metrics["data"]["score"] if metrics["data"] else None
    model_score = metrics["model"]["score"] if metrics["model"] else None
    if data_score is not None and model_score is not None:
        overall = data_score * 0.4 + model_score * 0.6
    elif data_score is not None:
        overall = data_score
    elif model_score is not None:
        overall = model_score
    else:
        overall = None
    metrics["overall_score"] = round(overall, 2) if overall is not None else None
    metrics["overall_status"] = _score_to_status(overall) if overall is not None else None

    # 状态判定
    if data_report is not None or model_report is not None:
        status = "completed" if (data_report and model_report) else "partial"
    else:
        status = "failed"

    # 保存验证结果供下游（论文阶段）使用
    validation_dict = {
        "status": status,
        "overall_score": metrics["overall_score"],
        "overall_status": metrics["overall_status"],
        "data_validation": metrics["data"],
        "model_validation": metrics["model"],
        "notes": notes,
    }
    _save_result(workflow, "validation.json", validation_dict)

    # —— 多视角审查：数据质量视角 + 模型统计视角，各自独立评分与结论，再汇总 ——
    perspectives = []
    if data_report is not None:
        perspectives.append({
            "name": "数据质量视角",
            "score": data_report.overall_score,
            "status": data_report.overall_status,
            "total": data_report.total_checks,
            "passed": data_report.passed_checks,
            "warning": data_report.warning_checks,
            "failed": data_report.failed_checks,
            "failed_items": [c.check_name for c in data_report.checks if c.status == "failed"],
        })
    if model_report is not None:
        perspectives.append({
            "name": "模型统计视角",
            "score": model_report.overall_score,
            "status": model_report.overall_status,
            "total": model_report.total_checks,
            "passed": model_report.passed_checks,
            "warning": model_report.warning_checks,
            "failed": model_report.failed_checks,
            "failed_items": [c.check_name for c in model_report.checks if c.status == "failed"],
        })
    # 论文一致视角在论文撰写阶段由 PaperQualityValidator 出具（数值一致性/图表真实性）。

    return {
        "status": status,
        "metrics": metrics,             # 含 data/model/overall 评分与检查计数
        "data_validation": metrics["data"],
        "model_validation": metrics["model"],
        "overall_score": metrics["overall_score"],
        "overall_status": metrics["overall_status"],
        "perspectives": perspectives,    # 多视角独立评分与结论
        "notes": notes,
        "summary": _build_summary(metrics, notes),
    }


def _score_to_status(score: float) -> str:
    if score >= 90:
        return "excellent"
    elif score >= 75:
        return "good"
    elif score >= 60:
        return "acceptable"
    elif score >= 40:
        return "poor"
    else:
        return "critical"


def _build_summary(metrics: Dict, notes: List[str]) -> str:
    parts = []
    if metrics["data"]:
        parts.append(f"数据验证评分 {metrics['data']['score']}/100（{metrics['data']['status']}）")
    if metrics["model"]:
        parts.append(f"模型验证评分 {metrics['model']['score']}/100（{metrics['model']['status']}）")
    if metrics["overall_score"] is not None:
        parts.append(f"综合评分 {metrics['overall_score']}/100（{metrics['overall_status']}）")
    if not parts:
        parts.append("未执行任何校验（缺少真实数据）")
    if notes:
        parts.append("备注：" + "；".join(notes))
    return "；".join(parts)
