"""
分类类模型求解器（category: classification）
真实实现（纯 Python）：逻辑回归（梯度下降）。
SVM / 决策树 / 随机森林 / KNN 需要 sklearn，诚实声明未实现。
"""
from __future__ import annotations

import math
from typing import Any, Dict, List

from ._base import BaseModelSolver, load_tabular, register_category


def _sigmoid(z: float) -> float:
    if z < -30:
        return 0.0
    if z > 30:
        return 1.0
    return 1.0 / (1.0 + math.exp(-z))


class ClassificationSolver(BaseModelSolver):
    """分类类求解器"""

    model_category = "classification"

    def solve(self, **params: Any) -> Dict[str, Any]:
        if self.model_id == "logistic_regression":
            return self._logistic(**params)
        if self.model_id in ("svm", "decision_tree", "random_forest", "knn"):
            raise NotImplementedError(
                f"模型 {self.model_id} 在恢复版尚未实现"
                f"（需要 sklearn 库，当前环境未安装）"
            )
        raise NotImplementedError(f"模型 {self.model_id} 在恢复版尚未实现")

    def _logistic(self, **params: Any) -> Dict[str, Any]:
        data_path = params.get("data_path")
        if not data_path:
            raise ValueError("逻辑回归需要提供 data_path（CSV，需含 'target' 列，取值 0/1）")
        target_column = params.get("target_column", "target")
        X, y, features = load_tabular(data_path, target_column=target_column)

        # 二值化目标
        yb = [1 if v > 0.5 else 0 for v in y]
        n = len(X)
        p = len(X[0])
        lr = float(params.get("learning_rate", 0.1))
        epochs = int(params.get("epochs", 200))

        w = [0.0] * p
        b = 0.0
        for _ in range(epochs):
            gw = [0.0] * p
            gb = 0.0
            for i in range(n):
                z = sum(w[j] * X[i][j] for j in range(p)) + b
                err = _sigmoid(z) - yb[i]
                for j in range(p):
                    gw[j] += err * X[i][j]
                gb += err
            for j in range(p):
                w[j] -= lr * gw[j] / n
            b -= lr * gb / n

        # 评估
        correct = 0
        for i in range(n):
            z = sum(w[j] * X[i][j] for j in range(p)) + b
            pred = 1 if _sigmoid(z) > 0.5 else 0
            if pred == yb[i]:
                correct += 1
        acc = correct / n if n else 0.0

        return {
            "model_category": "classification",
            "model_id": "logistic_regression",
            "model_name": self.model_name,
            "method": "logistic_regression(pure_python_gd)",
            "status": "success",
            "accuracy": round(float(acc), 6),
            "coefficients": {features[j]: round(float(w[j]), 6) for j in range(p)},
            "intercept": round(float(b), 6),
            "n_samples": n,
        }
