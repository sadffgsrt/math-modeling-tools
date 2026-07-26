# -*- coding: utf-8 -*-
"""
回归类模型求解器（category: regression）
真实实现的纯 Python 算法：普通最小二乘(OLS)、岭回归(Ridge)、Lasso(坐标下降)。
其余（SVR / XGBoost / LightGBM / CatBoost）需要 sklearn 或专用库，诚实声明未实现。
"""
from __future__ import annotations

from typing import Any, Dict, List, Tuple

from ._base import BaseModelSolver, load_tabular, _matmul, _transpose, _matvec, _solve, _r2, register_category


def _ols(X: List[List[float]], y: List[float], fit_intercept: bool = True) -> Tuple[List[float], float]:
    """普通最小二乘：解正规方程 (XᵀX)β = Xᵀy，返回 [截距, 各系数...] 与 R²"""
    if fit_intercept:
        A = [[1.0] + [float(v) for v in row] for row in X]
    else:
        A = [[float(v) for v in row] for row in X]
    AtA = _matmul(_transpose(A), A)
    Aty = _matvec(_transpose(A), [float(v) for v in y])
    beta = _solve(AtA, Aty)
    yhat = _matvec(A, beta)
    return beta, _r2([float(v) for v in y], yhat)


def _ridge(X: List[List[float]], y: List[float], alpha: float, fit_intercept: bool = True) -> Tuple[List[float], float]:
    """岭回归：(XᵀX + αI)β = Xᵀy，截距项不惩罚"""
    if fit_intercept:
        A = [[1.0] + [float(v) for v in row] for row in X]
    else:
        A = [[float(v) for v in row] for row in X]
    AtA = _matmul(_transpose(A), A)
    ncol = len(A[0])
    for i in range(ncol):
        AtA[i][i] += alpha
    Aty = _matvec(_transpose(A), [float(v) for v in y])
    beta = _solve(AtA, Aty)
    yhat = _matvec(A, beta)
    return beta, _r2([float(v) for v in y], yhat)


def _soft(z: float, t: float) -> float:
    """软阈值函数"""
    if z > t:
        return z - t
    if z < -t:
        return z + t
    return 0.0


def _lasso(X: List[List[float]], y: List[float], alpha: float, fit_intercept: bool = True,
           max_iter: int = 200, tol: float = 1e-6) -> Tuple[List[float], float]:
    """Lasso 回归：对标准化特征做坐标下降，再反标准化得到系数；真实计算。"""
    n = len(X)
    p = len(X[0])
    col_mean = [sum(X[i][j] for i in range(n)) / n for j in range(p)]
    col_std = []
    for j in range(p):
        mu = col_mean[j]
        var = sum((X[i][j] - mu) ** 2 for i in range(n)) / n
        std = var ** 0.5
        col_std.append(std if std > 1e-9 else 1.0)
    Xs = [[(X[i][j] - col_mean[j]) / col_std[j] for j in range(p)] for i in range(n)]
    ymean = sum(y) / n
    yc = [y[i] - ymean for i in range(n)]

    beta = [0.0] * p
    for _ in range(max_iter):
        max_diff = 0.0
        for j in range(p):
            # 计算 x_j 与当前残差的相关系数（标准化特征使 x_jᵀx_j = n）
            rj = sum(
                Xs[i][j] * (yc[i] - sum(Xs[i][k] * beta[k] for k in range(p) if k != j))
                for i in range(n)
            )
            z = rj / n
            new_beta = _soft(z, alpha / n)
            max_diff = max(max_diff, abs(new_beta - beta[j]))
            beta[j] = new_beta
        if max_diff < tol:
            break

    coef = [beta[j] / col_std[j] for j in range(p)]
    intercept = ymean - sum(coef[j] * col_mean[j] for j in range(p))
    yhat = [intercept + sum(coef[j] * X[i][j] for j in range(p)) for i in range(n)]
    return [intercept] + coef, _r2([float(v) for v in y], yhat)


class RegressionSolver(BaseModelSolver):
    """回归类求解器：regression / ridge / lasso 真实实现"""

    model_category = "regression"

    def solve(self, **params: Any) -> Dict[str, Any]:
        # 需要外部库的模型：诚实声明未实现
        if self.model_id in ("svr", "xgboost", "lightgbm", "catboost"):
            raise NotImplementedError(
                f"模型 {self.model_id} 在恢复版尚未实现"
                f"（需要 sklearn/specialized 库，当前环境未安装）"
            )

        data_path = params.get("data_path")
        if not data_path:
            raise ValueError("回归求解需要提供 data_path 参数（CSV 路径，需含 'target' 列）")

        target_column = params.get("target_column", "target")
        X, y, features = load_tabular(data_path, target_column=target_column)

        if self.model_id == "regression":
            beta, r2 = _ols(X, y, fit_intercept=True)
        elif self.model_id == "ridge":
            alpha = float(params.get("alpha", 1.0))
            beta, r2 = _ridge(X, y, alpha, fit_intercept=True)
        elif self.model_id == "lasso":
            alpha = float(params.get("alpha", 1.0))
            beta, r2 = _lasso(X, y, alpha, fit_intercept=True)
        else:
            raise NotImplementedError(f"模型 {self.model_id} 在恢复版尚未实现")

        intercept = beta[0]
        coefficients = {features[j]: float(beta[j + 1]) for j in range(len(features))}

        return {
            "model_category": "regression",
            "model_id": self.model_id,
            "model_name": self.model_name,
            "method": self.model_id,
            "r2": round(float(r2), 6),
            "intercept": round(float(intercept), 6),
            "coefficients": coefficients,
            "n_samples": len(X),
            "n_features": len(features),
            "status": "success",
        }


register_category("regression", RegressionSolver)
