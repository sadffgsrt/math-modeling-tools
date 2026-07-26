"""
分类类模型求解器（category: classification）
真实实现：逻辑回归（纯 Python 梯度下降）、SVM / 决策树 / 随机森林 / KNN（sklearn 包装）。
"""
from __future__ import annotations

import math
from typing import Any, Dict

from ._base import BaseModelSolver, _get_xy, register_category


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
            return self._sklearn_classifier(**params)
        raise NotImplementedError(f"模型 {self.model_id} 在恢复版尚未实现")

    def _logistic(self, **params: Any) -> Dict[str, Any]:
        X, y, features = _get_xy(params, target_column=params.get("target_column", "target"))
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

    def _sklearn_classifier(self, **params: Any) -> Dict[str, Any]:
        """统一使用 sklearn 实现 SVM / 决策树 / 随机森林 / KNN。"""
        try:
            from sklearn import svm as sk_svm
            from sklearn import tree, ensemble, neighbors
        except ImportError as e:
            raise NotImplementedError(
                f"模型 {self.model_id} 需要 sklearn 库，当前环境未安装"
            ) from e

        X, y, features = _get_xy(params, target_column=params.get("target_column", "target"))
        y_int = [int(v) for v in y]

        model_map = {
            "svm": sk_svm.SVC(kernel=params.get("kernel", "rbf"), probability=False, random_state=42),
            "decision_tree": tree.DecisionTreeClassifier(max_depth=params.get("max_depth"), random_state=42),
            "random_forest": ensemble.RandomForestClassifier(
                n_estimators=int(params.get("n_estimators", 100)),
                max_depth=params.get("max_depth"),
                random_state=42,
            ),
            "knn": neighbors.KNeighborsClassifier(n_neighbors=int(params.get("n_neighbors", 5))),
        }
        model = model_map[self.model_id]
        model.fit(X, y_int)
        preds = model.predict(X)
        acc = sum(1 for a, b in zip(preds, y_int) if a == b) / len(y_int)

        result: Dict[str, Any] = {
            "model_category": "classification",
            "model_id": self.model_id,
            "model_name": self.model_name,
            "method": f"sklearn.{self.model_id}",
            "status": "success",
            "accuracy": round(float(acc), 6),
            "n_samples": len(X),
            "n_features": len(features),
            "features": features,
        }
        if self.model_id == "svm" and hasattr(model, "support_"):
            result["support_vectors_count"] = int(model.support_.shape[0])
        return result


register_category("classification", ClassificationSolver)
