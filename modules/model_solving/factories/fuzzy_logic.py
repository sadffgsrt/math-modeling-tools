"""
模糊逻辑类模型求解器（category: fuzzy_logic）
真实实现：
- 模糊综合评价（已在 evaluation.py 实现）。
- 模糊推理系统（Mamdani 简化规则推理，纯 Python）。
- 模糊聚类（简化软划分 / FCM 近似，纯 Python）。
"""
from __future__ import annotations

import math
from typing import Any, Dict, List

from ._base import BaseModelSolver, _get_x, register_category


def _triangular(x: float, a: float, b: float, c: float) -> float:
    """三角隶属函数：a 左端，b 顶点，c 右端。"""
    if x <= a or x >= c:
        return 0.0
    if x <= b:
        return (x - a) / (b - a) if b != a else 1.0
    return (c - x) / (c - b) if c != b else 1.0


class FuzzySolver(BaseModelSolver):
    """模糊逻辑类求解器"""

    model_category = "fuzzy_logic"

    def solve(self, **params: Any) -> Dict[str, Any]:
        if self.model_id == "fuzzy_inference":
            return self._fuzzy_inference(**params)
        if self.model_id == "fuzzy_clustering":
            return self._fuzzy_clustering(**params)
        raise NotImplementedError(f"模型 {self.model_id} 在恢复版尚未实现")

    def _fuzzy_inference(self, **params: Any) -> Dict[str, Any]:
        """
        简化 Mamdani 模糊推理。

        参数示例：
            variables = {
                "temperature": {"low": (0, 0, 20), "medium": (10, 25, 40), "high": (30, 50, 50)},
                "humidity": {"low": (0, 0, 50), "high": (40, 100, 100)},
            }
            rules = [
                # 每个规则：[(变量, 标签, 是否取反), ...], 输出标签权重
                ([("temperature", "high", False), ("humidity", "low", False)], "cooling_strong"),
                ([("temperature", "medium", False), ("humidity", "high", False)], "cooling_weak"),
            ]
            output_terms = {
                "cooling_strong": (50, 100, 100),
                "cooling_weak": (0, 30, 60),
            }
            inputs = {"temperature": 35, "humidity": 45}
            output_variable = "cooling"
        """
        variables = params.get("variables", {})
        rules = params.get("rules", [])
        output_terms = params.get("output_terms", {})
        inputs = params.get("inputs", {})

        if not rules or not output_terms:
            raise ValueError(
                "模糊推理需要提供 rules、output_terms 和 inputs"
            )

        # 计算每条规则激活度
        activations = []
        for antecedents, consequent in rules:
            strength = 1.0
            for var_name, term, negate in antecedents:
                if var_name not in variables or term not in variables[var_name]:
                    raise ValueError(f"未知变量/标签：{var_name}/{term}")
                a, b, c = variables[var_name][term]
                mu = _triangular(inputs.get(var_name, 0.0), a, b, c)
                if negate:
                    mu = 1.0 - mu
                strength = min(strength, mu)
            activations.append((strength, consequent))

        # 对输出语言项聚合（取最大）
        aggregated = {term: 0.0 for term in output_terms}
        for strength, consequent in activations:
            if consequent not in aggregated:
                aggregated[consequent] = 0.0
            aggregated[consequent] = max(aggregated[consequent], strength)

        # 重心法解模糊
        numerator = 0.0
        denominator = 0.0
        for term, mu in aggregated.items():
            if term not in output_terms:
                continue
            a, b, c = output_terms[term]
            # 三角形质心 = (a + b + c) / 3
            centroid = (a + b + c) / 3.0
            numerator += mu * centroid
            denominator += mu

        output_value = numerator / denominator if denominator > 0 else 0.0

        return {
            "model_category": "fuzzy_logic",
            "model_id": "fuzzy_inference",
            "model_name": self.model_name,
            "method": "Mamdani_simplified(pure_python)",
            "status": "success",
            "output": round(float(output_value), 6),
            "rule_activations": [
                {"strength": round(float(s), 6), "consequent": c} for s, c in activations
            ],
            "aggregated": {k: round(float(v), 6) for k, v in aggregated.items()},
        }

    def _fuzzy_clustering(self, **params: Any) -> Dict[str, Any]:
        """
        简化模糊 C 均值（FCM）实现，纯 Python。
        返回软划分隶属度矩阵与聚类中心。
        """
        X, features = _get_x(params)
        n = len(X)
        p = len(X[0])
        k = int(params.get("n_clusters", 3))
        if k > n:
            k = n
        m = float(params.get("fuzziness", 2.0))
        max_iter = int(params.get("max_iter", 50))
        tol = float(params.get("tol", 1e-4))
        random_seed = int(params.get("random_state", 42))
        import random
        random.seed(random_seed)

        # 初始化隶属度（随机并归一化）
        U = []
        for _ in range(n):
            row = [random.random() for _ in range(k)]
            s = sum(row)
            U.append([v / s for v in row])

        def dist(a, b):
            return math.sqrt(sum((a[i] - b[i]) ** 2 for i in range(p)))

        centers = [[0.0] * p for _ in range(k)]
        for _ in range(max_iter):
            # 更新中心
            for j in range(k):
                num = [0.0] * p
                den = 0.0
                for i in range(n):
                    w = U[i][j] ** m
                    for d in range(p):
                        num[d] += w * X[i][d]
                    den += w
                if den > 0:
                    centers[j] = [v / den for v in num]
            # 更新隶属度
            max_diff = 0.0
            for i in range(n):
                for j in range(k):
                    d_ij = dist(X[i], centers[j])
                    d_ij = max(d_ij, 1e-12)
                    inv_sum = sum((1.0 / max(dist(X[i], centers[c]), 1e-12)) ** (2.0 / (m - 1)) for c in range(k))
                    new_u = 1.0 / (d_ij ** (2.0 / (m - 1)) * inv_sum)
                    max_diff = max(max_diff, abs(new_u - U[i][j]))
                    U[i][j] = new_u
            if max_diff < tol:
                break

        labels = [max(range(k), key=lambda c: U[i][c]) for i in range(n)]
        return {
            "model_category": "fuzzy_logic",
            "model_id": "fuzzy_clustering",
            "model_name": self.model_name,
            "method": "fuzzy_c_means(pure_python)",
            "status": "success",
            "n_clusters": k,
            "labels": labels,
            "membership": [[round(float(v), 6) for v in row] for row in U],
            "centers": [[round(float(v), 6) for v in c] for c in centers],
            "features": features,
        }


register_category("fuzzy_logic", FuzzySolver)
