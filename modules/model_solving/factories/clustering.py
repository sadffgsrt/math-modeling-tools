# -*- coding: utf-8 -*-
"""
聚类类模型求解器（category: clustering）
真实实现（纯 Python）：K-means（Lloyd 算法）。
DBSCAN / 聚类分析需要 sklearn，诚实声明未实现。
"""
from __future__ import annotations

import csv
import random
from typing import Any, Dict, List

from ._base import BaseModelSolver, register_category


def _dist(a: List[float], b: List[float]) -> float:
    return sum((a[i] - b[i]) ** 2 for i in range(len(a))) ** 0.5


class ClusteringSolver(BaseModelSolver):
    """聚类类求解器"""

    model_category = "clustering"

    def solve(self, **params: Any) -> Dict[str, Any]:
        if self.model_id == "kmeans":
            return self._kmeans(**params)
        if self.model_id in ("dbscan", "cluster_analysis"):
            raise NotImplementedError(
                f"模型 {self.model_id} 在恢复版尚未实现（需要 sklearn 库，当前环境未安装）"
            )
        raise NotImplementedError(f"模型 {self.model_id} 在恢复版尚未实现")

    def _kmeans(self, **params: Any) -> Dict[str, Any]:
        data_path = params.get("data_path")
        if not data_path:
            raise ValueError("K-means 需要提供 data_path（CSV 特征表）")
        with open(data_path, newline="", encoding="utf-8") as f:
            rows = [r for r in csv.reader(f) if any(c.strip() for c in r)]
        header = rows[0]
        X = []
        for row in rows[1:]:
            try:
                X.append([float(v) for v in row])
            except ValueError:
                continue
        if not X:
            raise ValueError("CSV 解析后无有效数值行")
        n = len(X)
        k = int(params.get("n_clusters", 3))
        max_iter = int(params.get("max_iter", 100))
        random.seed(int(params.get("random_state", 42)))
        # 随机选择初始质心
        centroids = [list(X[i]) for i in random.sample(range(n), k)]

        labels = [0] * n
        for _ in range(max_iter):
            # 分配
            changed = False
            for i in range(n):
                d = min(range(k), key=lambda c: _dist(X[i], centroids[c]))
                if d != labels[i]:
                    labels[i] = d
                    changed = True
            # 更新
            new_c = [[0.0] * len(X[0]) for _ in range(k)]
            cnt = [0] * k
            for i in range(n):
                c = labels[i]
                for j in range(len(X[0])):
                    new_c[c][j] += X[i][j]
                cnt[c] += 1
            for c in range(k):
                if cnt[c] > 0:
                    new_c[c] = [v / cnt[c] for v in new_c[c]]
            centroids = new_c
            if not changed:
                break

        inertia = sum(_dist(X[i], centroids[labels[i]]) ** 2 for i in range(n))
        return {
            "model_category": "clustering",
            "model_id": "kmeans",
            "model_name": self.model_name,
            "method": "kmeans(pure_python)",
            "status": "success",
            "n_clusters": k,
            "labels": labels,
            "centroids": [[round(float(v), 6) for v in c] for c in centroids],
            "inertia": round(float(inertia), 6),
        }


register_category("clustering", ClusteringSolver)
