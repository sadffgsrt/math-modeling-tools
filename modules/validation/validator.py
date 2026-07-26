"""
模型与数据验证模块 (Module 06) —— 从 v3.0 蓝本 06_validation/validator.py 忠实移植
功能：数据验证（完整性/一致性/准确性/时效性/唯一性）、模型验证（正确性/稳定性/
      泛化能力/可解释性）、综合验证、论文质量验证。

移植说明：
- 保留 v3.0 全部真实校验逻辑（基于 numpy/pandas 的统计量计算）。
- numpy / pandas 采用懒加载占位：保证本模块【可被导入】；真正校验时若缺失则抛出
  明确的 ImportError。
- scipy（残差正态性 Shapiro 检验）与 sklearn（交叉验证）为可选依赖：缺失时对应
  检查项降级为 warning 并给出说明，不影响其余真实校验。
"""

import json
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
from datetime import datetime
import warnings
warnings.filterwarnings('ignore')

# —— 依赖懒加载占位（保证模块可被 import）——
try:
    import numpy as np
except ImportError:  # pragma: no cover
    np = None
try:
    import pandas as pd
except ImportError:  # pragma: no cover
    pd = None


@dataclass
class ValidationCheck:
    """验证检查项"""
    check_id: str
    check_name: str
    check_type: str  # data_quality, data_consistency, model_correctness, model_stability, model_generalization
    status: str  # passed, warning, failed
    score: float  # 0-100
    message: str
    details: Dict
    recommendation: str


@dataclass
class ValidationReport:
    """验证报告"""
    report_id: str
    validation_type: str  # data, model, comprehensive
    total_checks: int
    passed_checks: int
    warning_checks: int
    failed_checks: int
    overall_score: float
    overall_status: str  # excellent, good, acceptable, poor, critical
    checks: List[ValidationCheck]
    summary: str
    recommendations: List[str]
    created_at: str
    metadata: Dict


def _require_numpy_pandas():
    """校验 numpy/pandas 可用性，缺失即抛出明确 ImportError。"""
    if np is None or pd is None:
        raise ImportError(
            "验证模块需要 numpy 与 pandas，请先安装：\n"
            "  pip install numpy pandas"
        )


class DataValidator:
    """数据验证器（移植自 v3.0，逻辑不变）"""

    def __init__(self, config: Optional[Dict] = None):
        self.config = config or {
            "missing_threshold": 0.3,
            "duplicate_threshold": 0.1,
            "outlier_threshold": 0.05,
            "correlation_threshold": 0.95,
            "variance_threshold": 0.01
        }

    def validate_dataset(self, data: "pd.DataFrame",
                        dataset_name: str = "dataset") -> ValidationReport:
        _require_numpy_pandas()
        checks = []
        checks.extend(self._check_completeness(data))
        checks.extend(self._check_consistency(data))
        checks.extend(self._check_accuracy(data))
        checks.extend(self._check_timeliness(data))
        checks.extend(self._check_uniqueness(data))

        passed = sum(1 for c in checks if c.status == "passed")
        warnings = sum(1 for c in checks if c.status == "warning")
        failed = sum(1 for c in checks if c.status == "failed")
        overall_score = np.mean([c.score for c in checks]) if checks else 0

        if overall_score >= 90:
            overall_status = "excellent"
        elif overall_score >= 75:
            overall_status = "good"
        elif overall_score >= 60:
            overall_status = "acceptable"
        elif overall_score >= 40:
            overall_status = "poor"
        else:
            overall_status = "critical"

        recommendations = self._generate_recommendations(checks)
        summary = (f"数据集'{dataset_name}'验证完成。共{len(checks)}项检查，"
                   f"{passed}项通过，{warnings}项警告，{failed}项失败。"
                   f"总体评分：{overall_score:.1f}/100。")

        return ValidationReport(
            report_id=f"DVR-{datetime.now().strftime('%Y%m%d%H%M%S')}",
            validation_type="data",
            total_checks=len(checks),
            passed_checks=passed,
            warning_checks=warnings,
            failed_checks=failed,
            overall_score=round(overall_score, 2),
            overall_status=overall_status,
            checks=checks,
            summary=summary,
            recommendations=recommendations,
            created_at=datetime.now().isoformat(),
            metadata={
                "dataset_name": dataset_name,
                "shape": data.shape,
                "columns": list(data.columns)
            }
        )

    def _check_completeness(self, data: "pd.DataFrame") -> List[ValidationCheck]:
        checks = []
        missing_ratio = data.isnull().mean().mean()
        missing_threshold = self.config.get("missing_threshold", 0.3)

        if missing_ratio == 0:
            status, score, message = "passed", 100, "数据完整，无缺失值"
        elif missing_ratio < missing_threshold:
            status, score, message = "warning", 80 - missing_ratio * 100, f"存在{missing_ratio:.1%}的缺失值"
        else:
            status, score, message = "failed", max(0, 50 - missing_ratio * 100), f"缺失值过多：{missing_ratio:.1%}"

        checks.append(ValidationCheck(
            check_id="DC-001", check_name="缺失值检查", check_type="data_quality",
            status=status, score=round(score, 2), message=message,
            details={"missing_ratio": missing_ratio, "missing_by_column": data.isnull().sum().to_dict()},
            recommendation="考虑使用插值、填充或删除缺失值" if status != "passed" else ""
        ))

        empty_rows = (data.isnull().all(axis=1)).sum()
        empty_ratio = empty_rows / len(data) if len(data) > 0 else 0
        if empty_ratio == 0:
            status, score, message = "passed", 100, "无完全空行"
        elif empty_ratio < 0.05:
            status, score, message = "warning", 90, f"存在{empty_rows}行完全空行"
        else:
            status, score, message = "failed", 60, f"空行过多：{empty_rows}行({empty_ratio:.1%})"

        checks.append(ValidationCheck(
            check_id="DC-002", check_name="空行检查", check_type="data_quality",
            status=status, score=score, message=message,
            details={"empty_rows": empty_rows, "empty_ratio": empty_ratio},
            recommendation="删除完全空行" if status != "passed" else ""
        ))
        return checks

    def _check_consistency(self, data: "pd.DataFrame") -> List[ValidationCheck]:
        checks = []
        type_issues = []
        for col in data.columns:
            try:
                pd.to_numeric(data[col], errors='raise')
            except (ValueError, TypeError):
                if data[col].dtype == 'object':
                    unique_types = data[col].apply(type).nunique()
                    if unique_types > 1:
                        type_issues.append(col)
        if not type_issues:
            status, score, message = "passed", 100, "数据类型一致"
        else:
            status, score, message = "warning", 85, f"以下列存在混合类型：{', '.join(type_issues[:3])}"

        checks.append(ValidationCheck(
            check_id="DC-003", check_name="数据类型一致性检查", check_type="data_consistency",
            status=status, score=score, message=message,
            details={"type_issues": type_issues},
            recommendation="统一数据列的类型" if type_issues else ""
        ))

        numeric_cols = data.select_dtypes(include=[np.number]).columns
        range_issues = []
        for col in numeric_cols:
            col_data = data[col].dropna()
            if len(col_data) > 0:
                q1 = col_data.quantile(0.25)
                q3 = col_data.quantile(0.75)
                iqr = q3 - q1
                lower = q1 - 3 * iqr
                upper = q3 + 3 * iqr
                extreme_outliers = ((col_data < lower) | (col_data > upper)).sum()
                if extreme_outliers > 0:
                    range_issues.append({"column": col, "extreme_outliers": int(extreme_outliers)})

        if not range_issues:
            status, score, message = "passed", 100, "数值范围合理"
        else:
            status, score, message = "warning", 80, "以下列存在极端异常值"

        checks.append(ValidationCheck(
            check_id="DC-004", check_name="数值范围检查", check_type="data_consistency",
            status=status, score=score, message=message,
            details={"range_issues": range_issues},
            recommendation="检查并处理极端异常值" if range_issues else ""
        ))
        return checks

    def _check_accuracy(self, data: "pd.DataFrame") -> List[ValidationCheck]:
        checks = []
        numeric_data = data.select_dtypes(include=[np.number])
        if numeric_data.shape[1] >= 2:
            corr_matrix = numeric_data.corr().abs()
            upper_tri = corr_matrix.where(np.triu(np.ones(corr_matrix.shape), k=1).astype(bool))
            high_corr_pairs = []
            threshold = self.config.get("correlation_threshold", 0.95)
            for col in upper_tri.columns:
                high_corr = upper_tri.index[upper_tri[col] > threshold].tolist()
                for corr_col in high_corr:
                    high_corr_pairs.append({
                        "col1": col, "col2": corr_col,
                        "correlation": float(corr_matrix.loc[corr_col, col])
                    })
            if not high_corr_pairs:
                status, score, message = "passed", 100, "无高度相关的特征对"
            else:
                status, score, message = "warning", 85, f"发现{len(high_corr_pairs)}对高度相关特征"
        else:
            high_corr_pairs, status, score, message = [], "passed", 100, "数值列不足，跳过相关性检查"

        checks.append(ValidationCheck(
            check_id="DC-005", check_name="特征相关性检查", check_type="data_quality",
            status=status, score=score, message=message,
            details={"high_corr_pairs": high_corr_pairs[:5]},
            recommendation="考虑删除冗余特征" if high_corr_pairs else ""
        ))

        low_var_cols = []
        variance_threshold = self.config.get("variance_threshold", 0.01)
        for col in numeric_data.columns:
            variance = numeric_data[col].var()
            if variance < variance_threshold:
                low_var_cols.append({"column": col, "variance": float(variance)})
        if not low_var_cols:
            status, score, message = "passed", 100, "无低方差特征"
        else:
            status, score, message = "warning", 90, f"发现{len(low_var_cols)}个低方差特征"

        checks.append(ValidationCheck(
            check_id="DC-006", check_name="特征方差检查", check_type="data_quality",
            status=status, score=score, message=message,
            details={"low_var_cols": low_var_cols},
            recommendation="考虑删除低方差特征" if low_var_cols else ""
        ))
        return checks

    def _check_timeliness(self, data: "pd.DataFrame") -> List[ValidationCheck]:
        checks = []
        date_cols = []
        for col in data.columns:
            if data[col].dtype == 'datetime64[ns]':
                date_cols.append(col)
            elif data[col].dtype == 'object':
                try:
                    pd.to_datetime(data[col], errors='raise')
                    date_cols.append(col)
                except Exception:
                    pass
        if date_cols:
            status, score, message = "passed", 100, f"发现{len(date_cols)}个时间列"
        else:
            status, score, message = "passed", 100, "未发现时间列（非必需）"
        checks.append(ValidationCheck(
            check_id="DC-007", check_name="时效性检查", check_type="data_quality",
            status=status, score=score, message=message,
            details={"date_columns": date_cols}, recommendation=""
        ))
        return checks

    def _check_uniqueness(self, data: "pd.DataFrame") -> List[ValidationCheck]:
        checks = []
        duplicate_rows = data.duplicated().sum()
        duplicate_ratio = duplicate_rows / len(data) if len(data) > 0 else 0
        duplicate_threshold = self.config.get("duplicate_threshold", 0.1)
        if duplicate_ratio == 0:
            status, score, message = "passed", 100, "无重复行"
        elif duplicate_ratio < duplicate_threshold:
            status, score, message = "warning", 85, f"存在{duplicate_rows}行重复数据({duplicate_ratio:.1%})"
        else:
            status, score, message = "failed", 60, f"重复数据过多：{duplicate_rows}行({duplicate_ratio:.1%})"
        checks.append(ValidationCheck(
            check_id="DC-008", check_name="重复行检查", check_type="data_quality",
            status=status, score=score, message=message,
            details={"duplicate_rows": int(duplicate_rows), "duplicate_ratio": duplicate_ratio},
            recommendation="删除重复行" if status != "passed" else ""
        ))
        return checks

    def _generate_recommendations(self, checks: List[ValidationCheck]) -> List[str]:
        recommendations = []
        for check in checks:
            if check.status in ["warning", "failed"] and check.recommendation:
                recommendations.append(f"[{check.check_name}] {check.recommendation}")
        if not recommendations:
            recommendations.append("数据质量良好，无需特别处理")
        return recommendations


class ModelValidator:
    """模型验证器（移植自 v3.0，逻辑不变；sklearn/scipy 为可选依赖）"""

    def __init__(self, config: Optional[Dict] = None):
        self.config = config or {
            "cv_folds": 5,
            "significance_level": 0.05,
            "min_r2": 0.5,
            "max_rmse_ratio": 0.3
        }

    def validate_model(self, model: Any, X: "np.ndarray", y: "np.ndarray",
                      model_name: str = "model",
                      feature_names: Optional[List[str]] = None,
                      real_model: bool = True) -> ValidationReport:
        _require_numpy_pandas()
        checks = []
        checks.extend(self._check_correctness(model, X, y, model_name))
        checks.extend(self._check_stability(model, X, y, model_name, real_model))
        checks.extend(self._check_generalization(model, X, y, model_name))
        checks.extend(self._check_interpretability(model, X, y, feature_names))

        passed = sum(1 for c in checks if c.status == "passed")
        warnings = sum(1 for c in checks if c.status == "warning")
        failed = sum(1 for c in checks if c.status == "failed")
        overall_score = np.mean([c.score for c in checks]) if checks else 0

        if overall_score >= 90:
            overall_status = "excellent"
        elif overall_score >= 75:
            overall_status = "good"
        elif overall_score >= 60:
            overall_status = "acceptable"
        elif overall_score >= 40:
            overall_status = "poor"
        else:
            overall_status = "critical"

        recommendations = self._generate_recommendations(checks)
        summary = (f"模型'{model_name}'验证完成。共{len(checks)}项检查，"
                   f"{passed}项通过，{warnings}项警告，{failed}项失败。"
                   f"总体评分：{overall_score:.1f}/100。")

        return ValidationReport(
            report_id=f"MVR-{datetime.now().strftime('%Y%m%d%H%M%S')}",
            validation_type="model",
            total_checks=len(checks),
            passed_checks=passed,
            warning_checks=warnings,
            failed_checks=failed,
            overall_score=round(overall_score, 2),
            overall_status=overall_status,
            checks=checks,
            summary=summary,
            recommendations=recommendations,
            created_at=datetime.now().isoformat(),
            metadata={"model_name": model_name, "X_shape": X.shape, "y_shape": y.shape}
        )

    def validate_from_results(self, metrics: Optional[Dict] = None,
                              cv_metrics: Optional[Dict] = None,
                              residuals: Optional["np.ndarray"] = None) -> List[ValidationCheck]:
        """基于已有的结果摘要（而非原始数据/模型）重建模型验证检查。

        用于验证阶段仅有求解指标、交叉验证摘要或残差时，仍能产出结构化检查项。
        - metrics["r2"]        -> MC-001 拟合优度
        - cv_metrics["cv_std"] -> MC-003 交叉验证稳定性（有明确摘要时按摘要判定，不降级）
        - residuals（数组）    -> MC-006 残差正态性（Shapiro-Wilk；scipy 缺失则诚实降级 warning）
        """
        _require_numpy_pandas()
        checks: List[ValidationCheck] = []
        metrics = metrics or {}
        min_r2 = self.config.get("min_r2", 0.5)

        # MC-001 拟合优度
        r2 = metrics.get("r2")
        if r2 is not None:
            if r2 >= 0.8:
                status, score, message = "passed", 95, f"模型拟合优秀 (R²={r2:.4f})"
            elif r2 >= min_r2:
                status, score, message = "passed", 80, f"模型拟合良好 (R²={r2:.4f})"
            elif r2 >= 0.3:
                status, score, message = "warning", 60, f"模型拟合一般 (R²={r2:.4f})"
            else:
                status, score, message = "failed", 30, f"模型拟合较差 (R²={r2:.4f})"
            checks.append(ValidationCheck(
                check_id="MC-001", check_name="拟合优度检查", check_type="model_correctness",
                status=status, score=score, message=message,
                details={"r2": float(r2)},
                recommendation="考虑增加特征或调整模型参数" if status != "passed" else ""))

        # MC-003 交叉验证稳定性（依据传入的 CV 摘要判定，非降级路径）
        if cv_metrics is not None:
            cv_std = cv_metrics.get("cv_std")
            cv_mean = cv_metrics.get("cv_mean")
            if cv_std is not None:
                if cv_std < 0.05:
                    status, score, message = "passed", 95, f"模型稳定性优秀 (std={cv_std:.4f})"
                elif cv_std < 0.1:
                    status, score, message = "passed", 85, f"模型稳定性良好 (std={cv_std:.4f})"
                elif cv_std < 0.2:
                    status, score, message = "warning", 70, f"模型稳定性一般 (std={cv_std:.4f})"
                else:
                    status, score, message = "failed", 50, f"模型稳定性较差 (std={cv_std:.4f})"
                checks.append(ValidationCheck(
                    check_id="MC-003", check_name="交叉验证稳定性检查", check_type="model_stability",
                    status=status, score=score, message=message,
                    details={"cv_mean": cv_mean, "cv_std": float(cv_std)},
                    recommendation="考虑增加数据量或简化模型" if status != "passed" else ""))

        # MC-006 残差正态性
        if residuals is not None:
            res_arr = np.asarray(residuals, dtype=float)
            if len(res_arr) >= 8:
                try:
                    from scipy import stats
                    _, p_value = stats.shapiro(res_arr[:min(5000, len(res_arr))])
                    if p_value > 0.05:
                        status, score, message = "passed", 90, "残差近似正态分布"
                    else:
                        status, score, message = "warning", 70, "残差偏离正态分布"
                    checks.append(ValidationCheck(
                        check_id="MC-006", check_name="残差正态性检查", check_type="model_correctness",
                        status=status, score=score, message=message,
                        details={"shapiro_p_value": float(p_value)},
                        recommendation="考虑数据变换或使用非参数模型" if status != "passed" else ""))
                except ImportError:
                    checks.append(ValidationCheck(
                        check_id="MC-006", check_name="残差正态性检查", check_type="model_correctness",
                        status="warning", score=70,
                        message="scipy 未安装，跳过残差正态性检验（Shapiro-Wilk）",
                        details={}, recommendation="安装 scipy 以启用残差正态性检验"))
                except Exception as e:
                    checks.append(ValidationCheck(
                        check_id="MC-006", check_name="残差正态性检查", check_type="model_correctness",
                        status="warning", score=60, message=f"残差正态性检验失败：{str(e)[:50]}",
                        details={"error": str(e)}, recommendation=""))

        return checks

    def _check_correctness(self, model, X, y, model_name) -> List[ValidationCheck]:
        checks = []
        try:
            y_pred = model.predict(X)
            mse = np.mean((y - y_pred) ** 2)
            rmse = np.sqrt(mse)
            mae = np.mean(np.abs(y - y_pred))
            ss_res = np.sum((y - y_pred) ** 2)
            ss_tot = np.sum((y - np.mean(y)) ** 2)
            r2 = 1 - (ss_res / ss_tot) if ss_tot > 0 else 0
            min_r2 = self.config.get("min_r2", 0.5)

            if r2 >= 0.8:
                status, score, message = "passed", 95, f"模型拟合优秀 (R²={r2:.4f})"
            elif r2 >= min_r2:
                status, score, message = "passed", 80, f"模型拟合良好 (R²={r2:.4f})"
            elif r2 >= 0.3:
                status, score, message = "warning", 60, f"模型拟合一般 (R²={r2:.4f})"
            else:
                status, score, message = "failed", 30, f"模型拟合较差 (R²={r2:.4f})"

            checks.append(ValidationCheck(
                check_id="MC-001", check_name="拟合优度检查", check_type="model_correctness",
                status=status, score=score, message=message,
                details={"r2": r2, "mse": mse, "rmse": rmse, "mae": mae},
                recommendation="考虑增加特征或调整模型参数" if status != "passed" else ""
            ))

            # 残差正态性（依赖 scipy；缺失则跳过并说明）
            residuals = y - y_pred
            if len(residuals) >= 8:
                try:
                    from scipy import stats
                    _, p_value = stats.shapiro(residuals[:min(5000, len(residuals))])
                    if p_value > 0.05:
                        status, score, message = "passed", 90, "残差近似正态分布"
                    else:
                        status, score, message = "warning", 70, "残差偏离正态分布"
                    checks.append(ValidationCheck(
                        check_id="MC-002", check_name="残差正态性检查", check_type="model_correctness",
                        status=status, score=score, message=message,
                        details={"shapiro_p_value": float(p_value)},
                        recommendation="考虑数据变换或使用非参数模型" if status != "passed" else ""
                    ))
                except ImportError:
                    checks.append(ValidationCheck(
                        check_id="MC-002", check_name="残差正态性检查", check_type="model_correctness",
                        status="warning", score=70,
                        message="scipy 未安装，跳过残差正态性检验（Shapiro-Wilk）",
                        details={}, recommendation="安装 scipy 以启用残差正态性检验"
                    ))
                except Exception as e:
                    checks.append(ValidationCheck(
                        check_id="MC-002", check_name="残差正态性检查", check_type="model_correctness",
                        status="warning", score=60, message=f"残差正态性检验失败：{str(e)[:50]}",
                        details={"error": str(e)}, recommendation=""
                    ))
        except Exception as e:
            checks.append(ValidationCheck(
                check_id="MC-000", check_name="模型预测检查", check_type="model_correctness",
                status="failed", score=0, message=f"模型预测失败：{str(e)}",
                details={"error": str(e)}, recommendation="检查模型是否已正确训练"
            ))
        return checks

    def _check_stability(self, model, X, y, model_name,
                        real_model: bool = True) -> List[ValidationCheck]:
        checks = []
        # 未提供真实模型对象（仅有预测值适配器）时，交叉验证无统计意义，
        # 诚实降级为 warning，避免对"记忆预测值"的适配器给出虚假满分。
        if not real_model:
            checks.append(ValidationCheck(
                check_id="MC-003", check_name="交叉验证稳定性检查", check_type="model_stability",
                status="warning", score=70,
                message="未提供真实模型对象（仅有预测值适配器），跳过交叉验证，不评估稳定性",
                details={}, recommendation="提供训练好的模型对象以启用真实交叉验证"))
            return checks
        cv_folds = self.config.get("cv_folds", 5)
        try:
            from sklearn.model_selection import cross_val_score
            cv_scores = cross_val_score(model, X, y, cv=min(cv_folds, len(X)),
                                       scoring='r2', error_score='raise')
            mean_score = np.mean(cv_scores)
            std_score = np.std(cv_scores)
            if std_score < 0.05:
                status, score, message = "passed", 95, f"模型稳定性优秀 (std={std_score:.4f})"
            elif std_score < 0.1:
                status, score, message = "passed", 85, f"模型稳定性良好 (std={std_score:.4f})"
            elif std_score < 0.2:
                status, score, message = "warning", 70, f"模型稳定性一般 (std={std_score:.4f})"
            else:
                status, score, message = "failed", 50, f"模型稳定性较差 (std={std_score:.4f})"
            checks.append(ValidationCheck(
                check_id="MC-003", check_name="交叉验证稳定性检查", check_type="model_stability",
                status=status, score=score, message=message,
                details={"cv_scores": cv_scores.tolist(), "mean_score": float(mean_score),
                         "std_score": float(std_score)},
                recommendation="考虑增加数据量或简化模型" if status != "passed" else ""
            ))
        except ImportError:
            checks.append(ValidationCheck(
                check_id="MC-003", check_name="交叉验证稳定性检查", check_type="model_stability",
                status="warning", score=70, message="sklearn未安装，跳过交叉验证",
                details={}, recommendation="安装scikit-learn以启用交叉验证"
            ))
        except Exception as e:
            checks.append(ValidationCheck(
                check_id="MC-003", check_name="交叉验证稳定性检查", check_type="model_stability",
                status="warning", score=60, message=f"交叉验证失败：{str(e)[:50]}",
                details={"error": str(e)}, recommendation="检查数据和模型兼容性"
            ))
        return checks

    def _check_generalization(self, model, X, y, model_name) -> List[ValidationCheck]:
        checks = []
        try:
            y_pred = model.predict(X)
            residuals = np.abs(y - y_pred)
            mean_residual = np.mean(residuals)
            max_residual = np.max(residuals)
            y_range = np.max(y) - np.min(y) if np.max(y) != np.min(y) else 1
            error_ratio = mean_residual / y_range
            max_error_ratio = max_residual / y_range
            max_rmse_ratio = self.config.get("max_rmse_ratio", 0.3)
            if error_ratio < 0.1:
                status, score, message = "passed", 95, f"泛化能力优秀 (平均误差比={error_ratio:.2%})"
            elif error_ratio < max_rmse_ratio:
                status, score, message = "passed", 80, f"泛化能力良好 (平均误差比={error_ratio:.2%})"
            elif error_ratio < 0.5:
                status, score, message = "warning", 60, f"泛化能力一般 (平均误差比={error_ratio:.2%})"
            else:
                status, score, message = "failed", 40, f"泛化能力较差 (平均误差比={error_ratio:.2%})"
            checks.append(ValidationCheck(
                check_id="MC-004", check_name="泛化能力检查", check_type="model_generalization",
                status=status, score=score, message=message,
                details={"mean_error_ratio": error_ratio, "max_error_ratio": max_error_ratio,
                         "mean_residual": float(mean_residual), "max_residual": float(max_residual)},
                recommendation="考虑增加正则化或收集更多数据" if status != "passed" else ""
            ))
        except Exception as e:
            checks.append(ValidationCheck(
                check_id="MC-004", check_name="泛化能力检查", check_type="model_generalization",
                status="warning", score=50, message=f"泛化能力检查失败：{str(e)[:50]}",
                details={"error": str(e)}, recommendation=""
            ))
        return checks

    def _check_interpretability(self, model, X, y,
                               feature_names: Optional[List[str]] = None) -> List[ValidationCheck]:
        checks = []
        has_importance = hasattr(model, 'feature_importances_') or hasattr(model, 'coef_')
        if has_importance:
            status, score, message = "passed", 90, "模型支持特征重要性分析"
            if hasattr(model, 'feature_importances_'):
                importance = model.feature_importances_
            elif hasattr(model, 'coef_'):
                importance = np.abs(model.coef_)
                if importance.ndim > 1:
                    importance = np.mean(importance, axis=0)
            if np.sum(importance) > 0:
                importance = importance / np.sum(importance)
            top_indices = np.argsort(importance)[::-1][:5]
            top_features = []
            for idx in top_indices:
                if feature_names and idx < len(feature_names):
                    top_features.append({"feature": feature_names[idx], "importance": float(importance[idx])})
            details = {"top_features": top_features}
        else:
            status, score, message, details = "warning", 70, "模型不支持特征重要性分析", {}
        checks.append(ValidationCheck(
            check_id="MC-005", check_name="可解释性检查", check_type="model_correctness",
            status=status, score=score, message=message, details=details,
            recommendation="考虑使用可解释性更强的模型" if status != "passed" else ""
        ))
        return checks

    def _generate_recommendations(self, checks: List[ValidationCheck]) -> List[str]:
        recommendations = []
        for check in checks:
            if check.status in ["warning", "failed"] and check.recommendation:
                recommendations.append(f"[{check.check_name}] {check.recommendation}")
        if not recommendations:
            recommendations.append("模型验证通过，无需特别处理")
        return recommendations


class ComprehensiveValidator:
    """综合验证器（移植自 v3.0）"""

    def __init__(self, config: Optional[Dict] = None):
        self.data_validator = DataValidator(config)
        self.model_validator = ModelValidator(config)

    def validate_all(self, data: "pd.DataFrame", model: Any, X: "np.ndarray", y: "np.ndarray",
                    dataset_name: str = "dataset", model_name: str = "model",
                    feature_names: Optional[List[str]] = None) -> Dict:
        _require_numpy_pandas()
        data_report = self.data_validator.validate_dataset(data, dataset_name)
        model_report = self.model_validator.validate_model(model, X, y, model_name, feature_names)
        overall_score = (data_report.overall_score * 0.4 + model_report.overall_score * 0.6)
        all_recommendations = data_report.recommendations + model_report.recommendations
        return {
            "data_validation": data_report,
            "model_validation": model_report,
            "overall_score": round(overall_score, 2),
            "overall_status": self._get_overall_status(overall_score),
            "recommendations": all_recommendations,
            "summary": (f"综合验证完成。数据评分：{data_report.overall_score:.1f}，"
                        f"模型评分：{model_report.overall_score:.1f}，"
                        f"综合评分：{overall_score:.1f}")
        }

    def _get_overall_status(self, score: float) -> str:
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


class PaperQualityValidator:
    """论文质量检查器（移植自 v3.0，基于建模论文质量检查标准）"""

    def __init__(self, config: Optional[Dict] = None):
        self.config = config or {}

    def validate_paper(self, paper_content: str, problem_analysis: Dict,
                       model_selection: Dict, solving_results: Dict,
                       validation_results: Dict, visualization_results: Dict,
                       figures_dir: Optional[str] = None) -> ValidationReport:
        _require_numpy_pandas()
        checks = []
        checks.extend(self._check_standards(paper_content, problem_analysis, model_selection))
        checks.extend(self._check_assumptions(paper_content, problem_analysis))
        checks.extend(self._check_model_selection(paper_content, model_selection, problem_analysis))
        checks.extend(self._check_argumentation(paper_content, solving_results))
        checks.extend(self._check_figures(paper_content, visualization_results))
        checks.extend(self._check_numerical_consistency(paper_content, solving_results, validation_results))
        checks.extend(self._check_figures_exist(visualization_results, figures_dir))
        checks.extend(self._check_format(paper_content))

        passed = sum(1 for c in checks if c.status == "passed")
        warnings = sum(1 for c in checks if c.status == "warning")
        failed = sum(1 for c in checks if c.status == "failed")
        overall_score = np.mean([c.score for c in checks]) if checks else 0

        if overall_score >= 90:
            overall_status = "excellent"
        elif overall_score >= 75:
            overall_status = "good"
        elif overall_score >= 60:
            overall_status = "acceptable"
        elif overall_score >= 40:
            overall_status = "poor"
        else:
            overall_status = "critical"

        recommendations = self._generate_recommendations(checks)
        summary = (f"论文质量检查完成。共{len(checks)}项检查，"
                   f"{passed}项通过，{warnings}项警告，{failed}项失败。"
                   f"总体评分：{overall_score:.1f}/100。")

        return ValidationReport(
            report_id=f"PQR-{datetime.now().strftime('%Y%m%d%H%M%S')}",
            validation_type="paper_quality",
            total_checks=len(checks),
            passed_checks=passed,
            warning_checks=warnings,
            failed_checks=failed,
            overall_score=round(overall_score, 2),
            overall_status=overall_status,
            checks=checks,
            summary=summary,
            recommendations=recommendations,
            created_at=datetime.now().isoformat(),
            metadata={
                "paper_length": len(paper_content),
                "has_figures": ("图" in paper_content) or ("figure" in paper_content.lower())
            }
        )

    def _check_standards(self, paper_content, problem_analysis, model_selection) -> List[ValidationCheck]:
        checks = []
        variables = problem_analysis.get("variables", [])
        if variables:
            defined_vars = [v.get("symbol", "") for v in variables if v.get("symbol")]
            missing_defs = [var for var in defined_vars if var and var not in paper_content]
            if not missing_defs:
                checks.append(ValidationCheck(
                    check_id="STD-001", check_name="变量定义完整性", check_type="standards",
                    status="passed", score=100, message=f"所有{len(defined_vars)}个变量都有定义",
                    details={"defined_variables": defined_vars, "missing": missing_defs},
                    recommendation=""))
            else:
                checks.append(ValidationCheck(
                    check_id="STD-001", check_name="变量定义完整性", check_type="standards",
                    status="warning", score=max(0, 100 - len(missing_defs) * 20),
                    message=f"有{len(missing_defs)}个变量未在论文中定义",
                    details={"defined_variables": defined_vars, "missing": missing_defs},
                    recommendation="请确保所有变量都在论文中有明确的定义和解释"))
        else:
            checks.append(ValidationCheck(
                check_id="STD-001", check_name="变量定义完整性", check_type="standards",
                status="warning", score=60, message="题目分析中未提取到变量信息",
                details={}, recommendation="建议在题目分析阶段提取变量信息"))

        has_assumptions = ("假设" in paper_content) and (("条件" in paper_content) or ("前提" in paper_content))
        if has_assumptions:
            checks.append(ValidationCheck(
                check_id="STD-002", check_name="假设条件明确性", check_type="standards",
                status="passed", score=100, message="论文中明确列出了假设条件",
                details={}, recommendation=""))
        else:
            checks.append(ValidationCheck(
                check_id="STD-002", check_name="假设条件明确性", check_type="standards",
                status="failed", score=40, message="论文中未明确列出假设条件",
                details={}, recommendation="请在论文中明确列出所有假设条件"))

        problem_type = problem_analysis.get("problem_type", "")
        model_name = model_selection.get("selected_model", {}).get("name", "")
        if problem_type and model_name:
            checks.append(ValidationCheck(
                check_id="STD-003", check_name="模型与问题匹配度", check_type="standards",
                status="passed", score=85,
                message=f"模型'{model_name}'适用于{problem_type}类问题",
                details={"problem_type": problem_type, "model_name": model_name},
                recommendation=""))
        return checks

    def _check_assumptions(self, paper_content, problem_analysis) -> List[ValidationCheck]:
        checks = []
        has_assumption_section = ("假设" in paper_content) and (("##" in paper_content) or ("###" in paper_content))
        if has_assumption_section:
            assumption_keywords = ["假设", "前提", "条件", "限定"]
            assumption_count = sum(1 for kw in assumption_keywords if kw in paper_content)
            if assumption_count >= 2:
                status, score, message = "passed", 90, f"论文列出了{assumption_count}个相关假设条件"
            else:
                status, score, message = "warning", 70, "假设条件可能不够充分"
        else:
            status, score, message = "failed", 30, "未找到明确的假设条件章节"
        checks.append(ValidationCheck(
            check_id="ASM-001", check_name="假设合理性", check_type="assumption",
            status=status, score=score, message=message,
            details={"assumption_count": assumption_count if has_assumption_section else 0},
            recommendation="请在论文中添加假设条件章节" if status != "passed" else ""))
        return checks

    def _check_model_selection(self, paper_content, model_selection, problem_analysis) -> List[ValidationCheck]:
        checks = []
        selected_model = model_selection.get("selected_model", {})
        model_name = selected_model.get("name", "")
        suitability_score = model_selection.get("suitability_score", 0)
        has_model_basis = ("选择" in paper_content) or ("采用" in paper_content) or ("使用" in paper_content)
        has_model_reason = ("因为" in paper_content) or ("由于" in paper_content) or ("基于" in paper_content)
        if has_model_basis and has_model_reason:
            checks.append(ValidationCheck(
                check_id="MOD-001", check_name="模型选择依据", check_type="model_selection",
                status="passed", score=90, message="论文中说明了模型选择的依据",
                details={"model_name": model_name, "suitability_score": suitability_score}, recommendation=""))
        elif has_model_basis:
            checks.append(ValidationCheck(
                check_id="MOD-001", check_name="模型选择依据", check_type="model_selection",
                status="warning", score=70, message="论文中提到了模型选择，但理由不够充分",
                details={"model_name": model_name}, recommendation="建议更详细地说明模型选择的理由"))
        else:
            checks.append(ValidationCheck(
                check_id="MOD-001", check_name="模型选择依据", check_type="model_selection",
                status="failed", score=40, message="论文中未说明模型选择依据",
                details={}, recommendation="请在论文中说明为什么选择该模型"))

        if suitability_score >= 80:
            status, score = "passed", suitability_score
        elif suitability_score >= 60:
            status, score = "warning", suitability_score
        else:
            status, score = "failed", suitability_score
        checks.append(ValidationCheck(
            check_id="MOD-002", check_name="模型适配度", check_type="model_selection",
            status=status, score=float(score), message=f"模型适配分数：{suitability_score}/100",
            details={"suitability_score": suitability_score},
            recommendation="" if status == "passed" else "考虑是否需要选择更合适的模型"))
        return checks

    def _check_argumentation(self, paper_content, solving_results) -> List[ValidationCheck]:
        checks = []
        key_sections = ["问题分析", "模型建立", "模型求解", "结果分析"]
        found_sections = [s for s in key_sections if s in paper_content]
        if len(found_sections) >= 3:
            status, score, message = "passed", 90, f"论文包含{len(found_sections)}个关键论证环节"
        elif len(found_sections) >= 2:
            status, score, message = "warning", 70, f"论文缺少部分关键论证环节（仅{len(found_sections)}个）"
        else:
            status, score, message = "failed", 40, "论文论证结构不完整"
        checks.append(ValidationCheck(
            check_id="ARG-001", check_name="论证完整性", check_type="argumentation",
            status=status, score=score, message=message,
            details={"found_sections": found_sections},
            recommendation="建议补充缺失的论证环节" if status != "passed" else ""))

        has_results = ("结果" in paper_content) or ("求解" in paper_content)
        has_analysis = ("分析" in paper_content) or ("讨论" in paper_content)
        if has_results and has_analysis:
            status, score, message = "passed", 85, "论文包含结果展示和分析讨论"
        elif has_results:
            status, score, message = "warning", 65, "论文有结果展示但缺少分析讨论"
        else:
            status, score, message = "failed", 30, "论文缺少结果展示"
        checks.append(ValidationCheck(
            check_id="ARG-002", check_name="结果分析完整性", check_type="argumentation",
            status=status, score=score, message=message, details={},
            recommendation="请添加模型求解结果的展示与分析" if status != "passed" else ""))
        return checks

    def _check_figures(self, paper_content, visualization_results) -> List[ValidationCheck]:
        checks = []
        figures_count = visualization_results.get("figures_count", 0) if visualization_results else 0
        if figures_count > 0:
            checks.append(ValidationCheck(
                check_id="FIG-001", check_name="图表完整性", check_type="figures",
                status="passed", score=90, message=f"论文包含{figures_count}个可视化图表",
                details={"figures_count": figures_count}, recommendation=""))
        else:
            checks.append(ValidationCheck(
                check_id="FIG-001", check_name="图表完整性", check_type="figures",
                status="warning", score=50, message="论文中未找到可视化图表",
                details={}, recommendation="建议添加图表来展示分析结果"))

        figure_indicators = ["图", "Fig", "figure", "图表"]
        has_figure_refs = any(ind in paper_content for ind in figure_indicators)
        if has_figure_refs:
            checks.append(ValidationCheck(
                check_id="FIG-002", check_name="图表引用规范", check_type="figures",
                status="passed", score=85, message="论文中正确引用了图表", details={}, recommendation=""))
        else:
            checks.append(ValidationCheck(
                check_id="FIG-002", check_name="图表引用规范", check_type="figures",
                status="warning", score=60, message="论文中未找到对图表的引用",
                details={}, recommendation="请在论文中引用并解释图表内容"))
        return checks

    def _check_format(self, paper_content) -> List[ValidationCheck]:
        checks = []
        has_abstract = ("摘要" in paper_content) or ("abstract" in paper_content.lower())
        if has_abstract:
            checks.append(ValidationCheck(
                check_id="FMT-001", check_name="摘要完整性", check_type="format",
                status="passed", score=100, message="论文包含摘要", details={}, recommendation=""))
        else:
            checks.append(ValidationCheck(
                check_id="FMT-001", check_name="摘要完整性", check_type="format",
                status="failed", score=30, message="论文缺少摘要",
                details={}, recommendation="请添加论文摘要"))

        has_keywords = ("关键词" in paper_content) or ("keyword" in paper_content.lower())
        if has_keywords:
            status, score = "passed", 100
        else:
            status, score = "warning", 60
        checks.append(ValidationCheck(
            check_id="FMT-002", check_name="关键词", check_type="format",
            status=status, score=score, message="论文包含关键词" if has_keywords else "论文缺少关键词",
            details={}, recommendation="" if has_keywords else "建议添加关键词"))

        has_chapters = any(f"第{i}章" in paper_content or f"{i}、" in paper_content
                          for i in ["一", "二", "三", "四", "五", "六", "七"])
        if has_chapters:
            status, score = "passed", 90
        else:
            status, score = "warning", 60
        checks.append(ValidationCheck(
            check_id="FMT-003", check_name="章节结构", check_type="format",
            status=status, score=score, message="论文具有清晰的章节结构" if has_chapters else "论文章节结构不够清晰",
            details={}, recommendation="" if has_chapters else "建议使用规范的章节编号和标题"))

        has_references = ("参考文献" in paper_content) or ("references" in paper_content.lower())
        if has_references:
            status, score = "passed", 100
        else:
            status, score = "warning", 60
        checks.append(ValidationCheck(
            check_id="FMT-004", check_name="参考文献", check_type="format",
            status=status, score=score, message="论文包含参考文献" if has_references else "论文缺少参考文献",
            details={}, recommendation="" if has_references else "建议添加参考文献"))
        return checks

    def _check_numerical_consistency(self, paper_content, solving_results,
                                    validation_results) -> List[ValidationCheck]:
        """核对论文中展示的 R² / 验证评分与上游真实数值是否一致（防止数值被覆盖或写死）。"""
        import re
        checks = []
        # R² 一致性
        r2_true = (solving_results or {}).get("metrics", {}).get("r2")
        if r2_true is not None:
            m = re.search(r"R[²2^]?\s*[=:]\s*([0-9]+(?:\.[0-9]+)?)", paper_content)
            if m:
                r2_paper = float(m.group(1))
                if abs(r2_paper - float(r2_true)) <= 0.01:
                    status, score, message = "passed", 95, f"论文 R²={r2_paper:.4f} 与求解结果一致"
                else:
                    status, score, message = "failed", 30, (
                        f"论文 R²={r2_paper:.4f} 与求解结果 R²={float(r2_true):.4f} 不一致")
            else:
                status, score, message = "warning", 70, "论文未展示 R²，但求解结果含 R²"
            checks.append(ValidationCheck(
                check_id="NUM-001", check_name="R²数值一致性", check_type="numerical",
                status=status, score=score, message=message,
                details={"r2_true": r2_true, "r2_paper": (float(m.group(1)) if m else None)},
                recommendation="请核对论文中 R² 是否与模型求解结果一致" if status != "passed" else ""))
        # 验证综合评分一致性
        score_true = (validation_results or {}).get("overall_score")
        if score_true is not None:
            m = re.search(r"综合验证评分[为是]?\s*\**\s*([0-9]+(?:\.[0-9]+)?)", paper_content)
            if m:
                score_paper = float(m.group(1))
                if abs(score_paper - float(score_true)) <= 1.0:
                    status, score, message = "passed", 90, f"论文验证评分与上游一致（{score_paper:.1f}）"
                else:
                    status, score, message = "warning", 60, (
                        f"论文验证评分 {score_paper:.1f} 与上游 {float(score_true):.1f} 偏差较大")
            else:
                status, score, message = "warning", 70, "论文未展示综合验证评分"
            checks.append(ValidationCheck(
                check_id="NUM-002", check_name="验证评分一致性", check_type="numerical",
                status=status, score=score, message=message,
                details={"score_true": score_true, "score_paper": (float(m.group(1)) if m else None)},
                recommendation="" if status == "passed" else "请核对论文中验证评分与上游结果"))
        return checks

    def _check_figures_exist(self, visualization_results, figures_dir) -> List[ValidationCheck]:
        """若提供图表目录，核对可视化图表是否真实生成文件（而非仅依赖计数声明）。"""
        checks = []
        claimed = (visualization_results or {}).get("figures_count", 0) if visualization_results else 0
        if not figures_dir:
            return checks
        from pathlib import Path
        d = Path(figures_dir)
        exts = ("*.png", "*.svg", "*.jpg", "*.jpeg")
        real_files = []
        if d.exists():
            for ext in exts:
                real_files.extend(d.glob(ext))
        if claimed > 0 and len(real_files) == 0:
            status, score, message = "failed", 30, (
                f"论文/可视化声称有 {claimed} 个图表，但目录 {figures_dir} 未找到任何图片文件")
        elif len(real_files) > 0:
            status, score, message = "passed", 90, f"图表目录真实存在 {len(real_files)} 个图片文件"
        else:
            status, score, message = "warning", 60, f"未发现图表文件（claimed={claimed}）"
        checks.append(ValidationCheck(
            check_id="FIG-003", check_name="图表文件真实性", check_type="figures",
            status=status, score=score, message=message,
            details={"claimed": claimed, "real_files": len(real_files)},
            recommendation="请确认可视化模块已真实写出图片文件" if status != "passed" else ""))
        return checks

    def _generate_recommendations(self, checks: List[ValidationCheck]) -> List[str]:
        recommendations = []
        for check in checks:
            if check.status in ["warning", "failed"] and check.recommendation:
                recommendations.append(check.recommendation)
        return list(set(recommendations))[:10]


def save_validation_report(report: ValidationReport, output_path: str):
    """保存验证报告 JSON"""
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(asdict(report), f, ensure_ascii=False, indent=2, default=str)
    print(f"验证报告已保存到: {output_path}")


def generate_validation_md(report: ValidationReport, output_path: str):
    """生成验证报告 Markdown"""
    status_emoji = {"excellent": "🟢", "good": "🟡", "acceptable": "🟠", "poor": "🔴", "critical": "⛔"}
    check_status_emoji = {"passed": "✅", "warning": "⚠️", "failed": "❌"}

    md_content = f"""# 验证报告

## 基本信息

- **报告ID**: {report.report_id}
- **验证类型**: {report.validation_type}
- **生成时间**: {report.created_at}

## 总体评估

{status_emoji.get(report.overall_status, "❓")} **整体状态**: {report.overall_status.upper()}
**总体评分**: {report.overall_score}/100

| 检查类型 | 数量 |
|----------|------|
| ✅ 通过 | {report.passed_checks} |
| ⚠️ 警告 | {report.warning_checks} |
| ❌ 失败 | {report.failed_checks} |
| **总计** | **{report.total_checks}** |

## 摘要

{report.summary}

## 详细检查结果

"""
    for check in report.checks:
        emoji = check_status_emoji.get(check.status, "❓")
        md_content += f"### {emoji} {check.check_name}\n\n"
        md_content += f"- **状态**: {check.status.upper()}\n"
        md_content += f"- **评分**: {check.score}/100\n"
        md_content += f"- **说明**: {check.message}\n"
        if check.recommendation:
            md_content += f"- **建议**: {check.recommendation}\n"
        md_content += "\n"

    md_content += "## 改进建议\n\n"
    for i, rec in enumerate(report.recommendations, 1):
        md_content += f"{i}. {rec}\n"
    md_content += f"\n---\n\n*生成时间: {report.created_at}*\n"

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(md_content)
    print(f"验证报告Markdown已保存到: {output_path}")


def main():
    """示例用法（依赖齐全时可运行）"""
    _require_numpy_pandas()
    np.random.seed(42)
    n_samples = 100
    X = np.random.randn(n_samples, 5)
    y = 2 * X[:, 0] + 3 * X[:, 1] + np.random.randn(n_samples) * 0.5
    data = pd.DataFrame(X, columns=[f'feature_{i}' for i in range(5)])
    data['target'] = y
    data.loc[0:5, 'feature_0'] = np.nan
    data.loc[10:15, 'feature_1'] = data.loc[10:15, 'feature_1'] * 100

    print("=" * 60)
    print("数据验证示例")
    print("=" * 60)
    data_validator = DataValidator()
    data_report = data_validator.validate_dataset(data, "sample_data")
    print(f"数据验证评分: {data_report.overall_score}/100  状态: {data_report.overall_status}")

    output_dir = Path("output")
    output_dir.mkdir(exist_ok=True)
    save_validation_report(data_report, output_dir / "data_validation.json")
    generate_validation_md(data_report, output_dir / "data_validation.md")

    try:
        from sklearn.linear_model import LinearRegression
        X_clean = data.drop('target', axis=1).fillna(0).values
        y_clean = data['target'].values
        model = LinearRegression()
        model.fit(X_clean, y_clean)
        print("\n" + "=" * 60)
        print("模型验证示例")
        print("=" * 60)
        model_validator = ModelValidator()
        model_report = model_validator.validate_model(
            model, X_clean, y_clean, "linear_regression",
            feature_names=[f'feature_{i}' for i in range(5)])
        print(f"模型验证评分: {model_report.overall_score}/100  状态: {model_report.overall_status}")
        save_validation_report(model_report, output_dir / "model_validation.json")
        generate_validation_md(model_report, output_dir / "model_validation.md")
    except ImportError:
        print("sklearn未安装，跳过模型验证示例")


if __name__ == "__main__":
    main()
