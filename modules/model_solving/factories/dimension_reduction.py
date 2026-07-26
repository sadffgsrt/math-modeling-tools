"""
降维类模型求解器（category: dimension_reduction）
真实实现（纯 Python）：PCA（协方差矩阵 + 幂迭代求主成分）。
因子分析需要 sklearn，诚实声明未实现。
"""
from __future__ import annotations

import csv
import math
import random
from typing import Any, Dict, List

from ._base import BaseModelSolver, register_category, _matvec


def _power_iteration(C: List[List[float]], n: int) -> tuple:
    """对对称矩阵 C 求主特征对（幂迭代）"""
    random.seed(0)
    v = [random.uniform(-1, 1) for _ in range(n)]
    norm = math.sqrt(sum(x * x for x in v))
    v = [x / norm for x in v]
    for _ in range(500):
        w = _matvec(C, v)
        norm = math.sqrt(sum(x * x for x in w))
        if norm < 1e-12:
            break
        v = [x / norm for x in w]
    # Rayleigh 商
    lam = sum(v[i] * sum(C[i][j] * v[j] for j in range(n)) for i in range(n))
    return lam, v


class DimensionReductionSolver(BaseModelSolver):
    """降维类求解器"""

    model_category = "dimension_reduction"

    def solve(self, **params: Any) -> Dict[str, Any]:
        if self.model_id == "pca":
            return self._pca(**params)
        if self.model_id == "factor_analysis":
            raise NotImplementedError(
                "模型 factor_analysis 在恢复版尚未实现（需要 sklearn 库，当前环境未安装）"
            )
        raise NotImplementedError(f"模型 {self.model_id} 在恢复版尚未实现")

    def _pca(self, **params: Any) -> Dict[str, Any]:
        data_path = params.get("data_path")
        if not data_path:
            raise ValueError("PCA 需要提供 data_path（CSV 特征表）")
        with open(data_path, newline="", encoding="utf-8") as f:
            rows = [r for r in csv.reader(f) if any(c.strip() for c in r)]
        rows = rows[1:] if rows else []
        X = []
        for row in rows:
            try:
                X.append([float(v) for v in row])
            except ValueError:
                continue
        if not X:
            raise ValueError("CSV 解析后无有效数值行")
        n = len(X)
        p = len(X[0])
        k = min(int(params.get("n_components", 2)), p)

        # 去中心
        mean = [sum(X[i][j] for i in range(n)) / n for j in range(p)]
        Xc = [[X[i][j] - mean[j] for j in range(p)] for i in range(n)]
        # 协方差矩阵
        C = [[0.0] * p for _ in range(p)]
        for a in range(p):
            for b in range(p):
                C[a][b] = sum(Xc[i][a] * Xc[i][b] for i in range(n)) / (n - 1)

        components = []
        evals = []
        total_var = sum(C[i][i] for i in range(p))
        for _ in range(k):
            lam, vec = _power_iteration(C, p)
            evals.append(lam)
            components.append(vec)
            # 除痕以便求下一主成分
            for a in range(p):
                for b in range(p):
                    C[a][b] -= lam * vec[a] * vec[b]

        # 投影
        transformed = [[sum(Xc[i][j] * components[c][j] for j in range(p)) for c in range(k)]
                       for i in range(n)]
        explained = [float(ev / total_var) if total_var > 0 else 0.0 for ev in evals]

        return {
            "model_category": "dimension_reduction",
            "model_id": "pca",
            "model_name": self.model_name,
            "method": "pca(pure_python_power_iteration)",
            "status": "success",
            "n_components": k,
            "explained_variance_ratio": [round(e, 6) for e in explained],
            "components": [[round(float(v), 6) for v in comp] for comp in components],
            "transformed": [[round(float(v), 6) for v in row] for row in transformed],
        }


register_category("dimension_reduction", DimensionReductionSolver)
