"""
模型求解模块 (Module 04) - 基础求解器
移植自 v3.0 蓝本（备份/工作流/modules/04_model_solving/solver.py），保留真实求解逻辑：
模型拟合后的指标计算、特征重要性、灵敏度分析、收敛检查、结果保存与报告生成。

注意：本环境可能未安装 numpy/pandas。为保证模块可被导入（不影响 model_solving
整体加载），此处对 numpy/pandas 采用延迟导入；当真正调用 solve_model 且环境缺失
对应库时，抛出清晰的 ImportError（诚实，不编造数值）。
"""
from __future__ import annotations

import json
import warnings
from dataclasses import dataclass, asdict
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Any, Callable

warnings.filterwarnings("ignore")

# 延迟导入：缺失库时不阻塞模块导入，仅在真正求解时报错
try:
    import numpy as np
except ImportError:  # pragma: no cover
    np = None

try:
    import pandas as pd
except ImportError:  # pragma: no cover
    pd = None


def _require_np():
    if np is None:
        raise ImportError(
            "ModelSolver.solve_model 需要 numpy，当前环境未安装；"
            "请安装 numpy/scipy/sklearn 以使用完整评估逻辑"
        )
    return np


@dataclass
class ModelParameter:
    """模型参数"""

    name: str
    value: float
    description: str
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    is_tunable: bool = True


@dataclass
class SensitivityResult:
    """灵敏度分析结果"""

    parameter_name: str
    base_value: float
    variation_range: Tuple[float, float]
    impact_metrics: Dict[str, float]
    sensitivity_score: float
    conclusion: str


@dataclass
class ModelMetrics:
    """模型评估指标"""

    mse: float
    rmse: float
    mae: float
    r2: float
    mape: Optional[float] = None
    adjusted_r2: Optional[float] = None
    aic: Optional[float] = None
    bic: Optional[float] = None


@dataclass
class SolvingResult:
    """求解结果"""

    result_id: str
    model_name: str
    model_type: str
    parameters: List[ModelParameter]
    metrics: ModelMetrics
    sensitivity_results: List[SensitivityResult]
    predictions: Optional[Any] = None
    residuals: Optional[Any] = None
    feature_importance: Optional[Dict[str, float]] = None
    convergence_info: Optional[Dict] = None
    execution_time: float = 0.0
    created_at: str = ""
    metadata: Dict = None

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


class ModelSolver:
    """模型求解器（指标/特征重要性/灵敏度/收敛分析）"""

    def __init__(self, config: Optional[Dict] = None):
        self.config = config or {
            "sensitivity_variation": 0.1,
            "sensitivity_steps": 10,
            "cross_validation_folds": 5,
            "random_state": 42,
        }
        self.results_dir = None

    def solve_model(self, model, X, y, model_name="model", model_type="regression",
                   parameters=None, feature_names=None) -> SolvingResult:
        """执行模型求解，返回完整 SolvingResult。"""
        np = _require_np()
        import time
        start_time = time.time()

        if parameters is None:
            parameters = self._extract_parameters(model)

        predictions = self._predict(model, X, model_type)
        if predictions is None:
            raise ValueError(
                "模型预测失败：predict 返回 None，无法计算指标（求解无效，拒绝伪造 0 指标）")
        pred_arr = np.asarray(predictions, dtype=float)
        if not np.all(np.isfinite(pred_arr)):
            raise ValueError("模型预测包含 NaN 或 Inf，求解结果无效")
        residuals = np.asarray(y) - pred_arr
        metrics = self._calculate_metrics(y, predictions, model_type)
        feature_importance = self._extract_feature_importance(model, feature_names)
        sensitivity_failed: List[str] = []
        sensitivity_results = self._sensitivity_analysis(
            model, X, y, parameters, model_type, failed_collector=sensitivity_failed)
        convergence_info = self._check_convergence(model)

        execution_time = time.time() - start_time

        result = SolvingResult(
            result_id=f"SR-{datetime.now().strftime('%Y%m%d%H%M%S')}",
            model_name=model_name,
            model_type=model_type,
            parameters=parameters,
            metrics=metrics,
            sensitivity_results=sensitivity_results,
            predictions=predictions,
            residuals=residuals,
            feature_importance=feature_importance,
            convergence_info=convergence_info,
            execution_time=round(execution_time, 4),
            created_at=datetime.now().isoformat(),
            metadata={
                "X_shape": X.shape,
                "y_shape": y.shape if hasattr(y, "shape") else len(y),
                "model_class": type(model).__name__,
                "sensitivity_failed": sensitivity_failed,
            },
        )
        return result

    def _extract_parameters(self, model):
        np = _require_np()
        parameters = []
        if hasattr(model, "coef_"):
            coef = model.coef_
            if coef.ndim == 1:
                for i, c in enumerate(coef):
                    parameters.append(ModelParameter(name=f"coef_{i}", value=float(c),
                                                     description=f"系数_{i}", is_tunable=False))
            else:
                for i in range(coef.shape[0]):
                    for j in range(coef.shape[1]):
                        parameters.append(ModelParameter(name=f"coef_{i}_{j}", value=float(coef[i, j]),
                                                         description=f"系数_{i}_{j}", is_tunable=False))
        if hasattr(model, "intercept_"):
            intercept = model.intercept_
            if np.isscalar(intercept):
                parameters.append(ModelParameter(name="intercept", value=float(intercept),
                                                 description="截距", is_tunable=False))
        if hasattr(model, "n_estimators"):
            parameters.append(ModelParameter(name="n_estimators", value=float(model.n_estimators),
                                             description="树的数量", min_value=10, max_value=1000, is_tunable=True))
        if hasattr(model, "max_depth") and model.max_depth is not None:
            parameters.append(ModelParameter(name="max_depth", value=float(model.max_depth),
                                             description="最大深度", min_value=1, max_value=50, is_tunable=True))
        if hasattr(model, "learning_rate"):
            parameters.append(ModelParameter(name="learning_rate", value=float(model.learning_rate),
                                             description="学习率", min_value=0.001, max_value=1.0, is_tunable=True))
        if not parameters:
            parameters.append(ModelParameter(name="default", value=1.0, description="默认参数", is_tunable=False))
        return parameters

    def _predict(self, model, X, model_type):
        try:
            return model.predict(X)
        except Exception as e:  # pragma: no cover
            print(f"预测失败: {e}")
            return None

    def _calculate_metrics(self, y_true, y_pred, model_type):
        np = _require_np()
        if y_pred is None:
            return ModelMetrics(mse=0, rmse=0, mae=0, r2=0)
        y_true = np.asarray(y_true)
        y_pred = np.asarray(y_pred)
        if not np.all(np.isfinite(y_pred)) or not np.all(np.isfinite(y_true)):
            raise ValueError("y_true 或 y_pred 含 NaN/Inf，无法计算有效指标")
        if model_type == "classification":
            accuracy = float(np.mean(y_true == y_pred))
            return ModelMetrics(mse=0, rmse=0, mae=0, r2=accuracy)
        mse = float(np.mean((y_true - y_pred) ** 2))
        rmse = float(np.sqrt(mse))
        mae = float(np.mean(np.abs(y_true - y_pred)))
        ss_res = float(np.sum((y_true - y_pred) ** 2))
        ss_tot = float(np.sum((y_true - np.mean(y_true)) ** 2))
        r2 = 1 - (ss_res / ss_tot) if ss_tot > 0 else 0.0
        non_zero = y_true != 0
        mape = float(np.mean(np.abs((y_true[non_zero] - y_pred[non_zero]) / y_true[non_zero])) * 100) if non_zero.any() else None
        n = len(y_true)
        p = 1
        adjusted_r2 = 1 - (1 - r2) * (n - 1) / (n - p - 1) if n > p + 1 else r2
        return ModelMetrics(
            mse=round(mse, 6), rmse=round(rmse, 6), mae=round(mae, 6), r2=round(r2, 6),
            mape=round(mape, 2) if mape is not None else None,
            adjusted_r2=round(float(adjusted_r2), 6),
        )

    def _extract_feature_importance(self, model, feature_names=None):
        np = _require_np()
        importance = None
        if hasattr(model, "feature_importances_"):
            importance = model.feature_importances_
        elif hasattr(model, "coef_"):
            coef = model.coef_
            if coef.ndim == 1:
                importance = np.abs(coef)
            else:
                importance = np.mean(np.abs(coef), axis=0)
        if importance is None:
            return None
        if np.sum(importance) > 0:
            importance = importance / np.sum(importance)
        if feature_names and len(feature_names) == len(importance):
            return {name: round(float(imp), 4) for name, imp in zip(feature_names, importance)}
        return {f"feature_{i}": round(float(imp), 4) for i, imp in enumerate(importance)}

    def _sensitivity_analysis(self, model, X, y, parameters, model_type,
                             failed_collector: Optional[List[str]] = None):
        np = _require_np()
        results = []
        try:
            y_pred = model.predict(X)
        except Exception:
            return results
        base_mse = float(np.mean((np.asarray(y) - y_pred) ** 2))
        n_features = X.shape[1] if X.ndim > 1 else 1
        for i in range(min(n_features, 10)):
            fname = f"feature_{i}"
            std = float(X[:, i].std()) if X.ndim > 1 else float(X.std())
            if std == 0:
                continue
            X_plus = X.copy()
            X_minus = X.copy()
            if X.ndim > 1:
                X_plus[:, i] += 0.1 * std
                X_minus[:, i] -= 0.1 * std
            else:
                X_plus += 0.1 * std
                X_minus -= 0.1 * std
            try:
                pred_plus = model.predict(X_plus)
                pred_minus = model.predict(X_minus)
                mse_plus = float(np.mean((np.asarray(y) - pred_plus) ** 2))
                mse_minus = float(np.mean((np.asarray(y) - pred_minus) ** 2))
                sensitivity = abs(mse_plus - mse_minus) / (2 * base_mse + 1e-10) * 100
                if parameters and i < len(parameters):
                    fname = parameters[i].name
                if sensitivity < 5:
                    conclusion = f"特征 {fname} 对结果影响较小"
                elif sensitivity < 15:
                    conclusion = f"特征 {fname} 对结果有一定影响"
                else:
                    conclusion = f"特征 {fname} 对结果影响显著"
                results.append(SensitivityResult(
                    parameter_name=fname, base_value=float(std),
                    variation_range=(float(-0.1 * std), float(0.1 * std)),
                    impact_metrics={"base_mse": base_mse, "mse_plus": mse_plus,
                                    "mse_minus": mse_minus, "sensitivity_pct": round(sensitivity, 4)},
                    sensitivity_score=round(float(sensitivity), 2), conclusion=conclusion))
            except Exception:
                if failed_collector is not None:
                    failed_collector.append(fname)
                continue
        results.sort(key=lambda x: x.sensitivity_score, reverse=True)
        return results

    def _check_convergence(self, model):
        info = {}
        if hasattr(model, "n_iter_") and model.n_iter_ is not None:
            try:
                info["iterations"] = int(model.n_iter_)
            except (TypeError, ValueError):
                # n_iter_ 可能为数组（多目标）或非标量，跳过记录
                pass
        if hasattr(model, "score"):
            info["has_score"] = True
        if hasattr(model, "oob_score_"):
            info["oob_score"] = float(model.oob_score_)
        return info if info else None

    def save_result(self, result: SolvingResult, output_dir: str):
        np = _require_np()
        self.results_dir = Path(output_dir)
        self.results_dir.mkdir(parents=True, exist_ok=True)
        result_path = self.results_dir / "solving_result.json"
        result_dict = asdict(result)
        if result.predictions is not None:
            result_dict["predictions"] = np.asarray(result.predictions).tolist()
        if result.residuals is not None:
            result_dict["residuals"] = np.asarray(result.residuals).tolist()
        with open(result_path, "w", encoding="utf-8") as f:
            json.dump(result_dict, f, ensure_ascii=False, indent=2)
        print(f"求解结果已保存到: {self.results_dir}")

    def generate_report_md(self, result: SolvingResult, output_path: str):
        md = f"# 模型求解报告\n\n## 基本信息\n\n"
        md += f"- **结果ID**: {result.result_id}\n- **模型名称**: {result.model_name}\n"
        md += f"- **模型类型**: {result.model_type}\n- **执行时间**: {result.execution_time:.2f}秒\n"
        md += f"- **生成时间**: {result.created_at}\n\n## 模型参数\n\n"
        md += "| 参数名 | 值 | 描述 | 可调 |\n|--------|-----|------|------|\n"
        for param in result.parameters:
            md += f"| {param.name} | {param.value:.4f} | {param.description} | {'是' if param.is_tunable else '否'} |\n"
        md += f"\n## 评估指标\n\n| 指标 | 值 |\n|------|-----|\n"
        md += f"| MSE | {result.metrics.mse:.6f} |\n| RMSE | {result.metrics.rmse:.6f} |\n"
        md += f"| MAE | {result.metrics.mae:.6f} |\n| R² | {result.metrics.r2:.6f} |\n"
        if result.metrics.mape is not None:
            md += f"| MAPE | {result.metrics.mape:.2f}% |\n"
        if result.metrics.adjusted_r2 is not None:
            md += f"| 调整R² | {result.metrics.adjusted_r2:.6f} |\n"
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(md, encoding="utf-8")
        print(f"求解报告已保存到: {output_path}")


# 兼容 v3.0 的便捷别名
ModelSolver = ModelSolver


def main():
    """示例（需要 numpy/sklearn）。"""
    np = _require_np()
    from sklearn.linear_model import LinearRegression  # noqa

    X = np.random.randn(100, 5)
    y = 2 * X[:, 0] + 3 * X[:, 1] + np.random.randn(100) * 0.5
    model = LinearRegression().fit(X, y)
    solver = ModelSolver()
    result = solver.solve_model(model, X, y, model_name="linear_regression", feature_names=[f"f{i}" for i in range(5)])
    print("R²:", result.metrics.r2)


if __name__ == "__main__":
    main()
