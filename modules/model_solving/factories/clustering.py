"""
聚类类模型求解器（category: clustering）
真实实现：K-means（纯 Python Lloyd 算法）、DBSCAN / 聚类分析（sklearn 包装）。
"""
from __future__ import annotations

import random
from typing import Any, Dict, List

from ._base import BaseModelSolver, _get_x, register_category


def _dist(a: List[float], b: List[float]) -> float:
    return sum((a[i] - b[i]) ** 2 for i in range(len(a))) ** 0.5


class ClusteringSolver(BaseModelSolver):
    """聚类类求解器"""

    model_category = "clustering"

    def solve(self, **params: Any) -> Dict[str, Any]:
        if self.model_id == "kmeans":
            return self._kmeans(**params)
        if self.model_id in ("dbscan", "cluster_analysis"):
            return self._sklearn_clustering(**params)
        raise NotImplementedError(f"模型 {self.model_id} 在恢复版尚未实现")

    def _kmeans(self, **params: Any) -> Dict[str, Any]:
        X, _ = _get_x(params)
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

    def _sklearn_clustering(self, **params: Any) -> Dict[str, Any]:
        """DBSCAN 与聚类分析（KMeans + Agglomerative + 轮廓系数）的 sklearn 包装。"""
        try:
            from sklearn import cluster as sk_cluster
            from sklearn import metrics
        except ImportError as e:
            raise NotImplementedError(
                f"模型 {self.model_id} 需要 sklearn 库，当前环境未安装"
            ) from e

        X, features = _get_x(params)

        if self.model_id == "dbscan":
            eps = float(params.get("eps", 0.5))
            min_samples = int(params.get("min_samples", 5))
            model = sk_cluster.DBSCAN(eps=eps, min_samples=min_samples)
            labels = model.fit_predict(X)
            n_clusters = len(set(labels)) - (1 if -1 in labels else 0)
            noise = int(sum(1 for v in labels if v == -1))
            silhouette = None
            if n_clusters >= 2:
                silhouette = round(metrics.silhouette_score(X, labels), 6)
            return {
                "model_category": "clustering",
                "model_id": "dbscan",
                "model_name": self.model_name,
                "method": "sklearn.cluster.DBSCAN",
                "status": "success",
                "n_clusters": n_clusters,
                "noise_points": noise,
                "labels": labels.tolist(),
                "silhouette_score": silhouette,
            }

        # cluster_analysis：同时运行 KMeans 与 Agglomerative，返回对比摘要
        k = int(params.get("n_clusters", 3))
        kmeans = sk_cluster.KMeans(n_clusters=k, random_state=42, n_init="auto")
        agg = sk_cluster.AgglomerativeClustering(n_clusters=k)
        labels_km = kmeans.fit_predict(X)
        labels_agg = agg.fit_predict(X)
        return {
            "model_category": "clustering",
            "model_id": "cluster_analysis",
            "model_name": self.model_name,
            "method": "sklearn.KMeans+AglomerativeClustering",
            "status": "success",
            "n_clusters": k,
            "kmeans_labels": labels_km.tolist(),
            "agglomerative_labels": labels_agg.tolist(),
            "kmeans_inertia": round(float(kmeans.inertia_), 6),
        }


register_category("clustering", ClusteringSolver)
