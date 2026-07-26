"""
图论类模型求解器（category: graph_theory）
真实实现（纯 Python）：Dijkstra 最短路、最大流(Edmonds-Karp)。
"""
from __future__ import annotations

import heapq
from collections import deque
from typing import Any, Dict, List

from ._base import BaseModelSolver, register_category, _first_present, _as_matrix


class GraphSolver(BaseModelSolver):
    """图论类求解器"""

    model_category = "graph_theory"

    def solve(self, **params: Any) -> Dict[str, Any]:
        if self.model_id == "dijkstra":
            return self._dijkstra(**params)
        if self.model_id == "max_flow":
            return self._max_flow(**params)
        raise NotImplementedError(f"模型 {self.model_id} 在恢复版尚未实现")

    def _dijkstra(self, **params: Any) -> Dict[str, Any]:
        # 支持邻接矩阵或邻接表
        adj = _first_present(params, "adj", "graph")
        adj = [[float(v) for v in row] for row in _as_matrix(adj)]
        n = len(adj)
        source = int(params.get("source", 0))
        target = params.get("target")
        # 构建邻接表
        graph: List[List] = [[] for _ in range(n)]
        for i in range(n):
            for j in range(n):
                if adj[i][j] and adj[i][j] > 0:
                    if adj[i][j] == float("inf"):
                        continue
                    graph[i].append((j, adj[i][j]))
        dist = [float("inf")] * n
        prev = [-1] * n
        dist[source] = 0.0
        pq = [(0.0, source)]
        while pq:
            d, u = heapq.heappop(pq)
            if d > dist[u]:
                continue
            for v, w in graph[u]:
                if dist[u] + w < dist[v]:
                    dist[v] = dist[u] + w
                    prev[v] = u
                    heapq.heappush(pq, (dist[v], v))
        # 若指定目标，回溯路径
        path = None
        if target is not None:
            target = int(target)
            if dist[target] < float("inf"):
                path = []
                cur = target
                while cur != -1:
                    path.append(cur)
                    cur = prev[cur]
                path.reverse()
        return {
            "model_category": "graph_theory",
            "model_id": "dijkstra",
            "model_name": self.model_name,
            "method": "Dijkstra(pure_python)",
            "status": "success",
            "source": source,
            "target": target,
            "shortest_distance": round(float(dist[target if target is not None else source]), 6),
            "path": path,
            "distances": [round(d, 6) for d in dist],
        }

    def _max_flow(self, **params: Any) -> Dict[str, Any]:
        cap = _first_present(params, "capacity", "cap", "graph")
        cap = [[float(v) for v in row] for row in _as_matrix(cap)]
        n = len(cap)
        source = int(params.get("source", 0))
        sink = int(params.get("sink", n - 1))
        # 剩余容量图
        residual = [list(row) for row in cap]
        total = 0.0
        while True:
            parent = [-1] * n
            parent[source] = source
            q = deque([source])
            while q:
                u = q.popleft()
                for v in range(n):
                    if residual[u][v] > 1e-12 and parent[v] == -1:
                        parent[v] = u
                        q.append(v)
            if parent[sink] == -1:
                break
            # 找瓶颈
            path_flow = float("inf")
            v = sink
            while v != source:
                u = parent[v]
                path_flow = min(path_flow, residual[u][v])
                v = u
            v = sink
            while v != source:
                u = parent[v]
                residual[u][v] -= path_flow
                residual[v][u] += path_flow
                v = u
            total += path_flow
        return {
            "model_category": "graph_theory",
            "model_id": "max_flow",
            "model_name": self.model_name,
            "method": "EdmondsKarp(pure_python)",
            "status": "success",
            "source": source,
            "sink": sink,
            "max_flow": round(float(total), 6),
        }


register_category("graph_theory", GraphSolver)
