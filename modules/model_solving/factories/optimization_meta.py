# -*- coding: utf-8 -*-
"""
元启发式优化模型求解器（category: optimization_meta）
真实实现（纯 Python）：差分进化(DE)、遗传算法(GA)。
粒子群(PSO)/人工蜂群(ABC)/蚁群(ACO)需要专用库，诚实声明未实现。
"""
from __future__ import annotations

import math
import random
from typing import Any, Callable, Dict, List

from ._base import BaseModelSolver, register_category


def _rand_in(bounds):
    return [random.uniform(lo, hi) for lo, hi in bounds]


class MetaHeuristicSolver(BaseModelSolver):
    """元启发式优化求解器"""

    model_category = "optimization_meta"

    def solve(self, **params: Any) -> Dict[str, Any]:
        if self.model_id == "de":
            return self._de(**params)
        if self.model_id == "genetic_algorithm":
            return self._ga(**params)
        if self.model_id == "pso":
            return self._pso(**params)
        if self.model_id == "abc":
            return self._abc(**params)
        if self.model_id == "ant_colony":
            return self._ant_colony(**params)
        raise NotImplementedError(f"模型 {self.model_id} 在恢复版尚未实现")

    def _de(self, **params: Any) -> Dict[str, Any]:
        objective = params.get("objective")
        if objective is None or not callable(objective):
            raise NotImplementedError("差分进化需要提供可调用目标函数 objective(x)")
        random.seed(int(params.get("random_state", 42)))
        dim = int(params["dim"])
        bounds = params.get("bounds", [(-5, 5)] * dim)
        npop = int(params.get("pop_size", 20))
        max_iter = int(params.get("max_iter", 50))
        F = float(params.get("F", 0.5))
        cr = float(params.get("cr", 0.7))

        pop = [_rand_in(bounds) for _ in range(npop)]
        fit = [objective(ind) for ind in pop]
        best = min(range(npop), key=lambda i: fit[i])

        for _ in range(max_iter):
            for i in range(npop):
                idxs = [j for j in range(npop) if j != i]
                a, b, c = (pop[k] for k in random.sample(idxs, 3))
                trial = []
                for d in range(dim):
                    if random.random() < cr or d == dim - 1:
                        val = a[d] + F * (b[d] - c[d])
                        val = min(max(val, bounds[d][0]), bounds[d][1])
                        trial.append(val)
                    else:
                        trial.append(pop[i][d])
                f_trial = objective(trial)
                if f_trial < fit[i]:
                    pop[i], fit[i] = trial, f_trial
                    if f_trial < fit[best]:
                        best = i
        return {
            "model_category": "optimization_meta",
            "model_id": "de",
            "model_name": self.model_name,
            "method": "DifferentialEvolution(pure_python)",
            "status": "success",
            "best_x": [float(v) for v in pop[best]],
            "best_value": float(fit[best]),
        }

    def _ga(self, **params: Any) -> Dict[str, Any]:
        objective = params.get("objective")
        if objective is None or not callable(objective):
            raise NotImplementedError("遗传算法需要提供可调用目标函数 objective(x)")
        random.seed(int(params.get("random_state", 42)))
        dim = int(params["dim"])
        bounds = params.get("bounds", [(-5, 5)] * dim)
        npop = int(params.get("pop_size", 20))
        max_iter = int(params.get("max_iter", 50))

        def clip(ind):
            return [min(max(v, bounds[d][0]), bounds[d][1]) for d, v in enumerate(ind)]

        pop = [clip(_rand_in(bounds)) for _ in range(npop)]

        def tournament():
            a, b = random.sample(range(npop), 2)
            return pop[a] if objective(pop[a]) < objective(pop[b]) else pop[b]

        for _ in range(max_iter):
            new_pop = []
            while len(new_pop) < npop:
                p1, p2 = tournament(), tournament()
                cut = random.randrange(dim)
                child = clip(p1[:cut] + p2[cut:])
                if random.random() < 0.1:  # 变异
                    d = random.randrange(dim)
                    child[d] = random.uniform(bounds[d][0], bounds[d][1])
                new_pop.append(child)
            pop = new_pop
        best = min(pop, key=lambda ind: objective(ind))
        return {
            "model_category": "optimization_meta",
            "model_id": "genetic_algorithm",
            "model_name": self.model_name,
            "method": "GeneticAlgorithm(pure_python)",
            "status": "success",
            "best_x": [float(v) for v in best],
            "best_value": float(objective(best)),
        }

    # ── 粒子群优化 (PSO) ──
    def _pso(self, **params: Any) -> Dict[str, Any]:
        objective = params.get("objective")
        if objective is None or not callable(objective):
            raise NotImplementedError("粒子群优化需要提供可调用目标函数 objective(x)")
        random.seed(int(params.get("random_state", 42)))
        dim = int(params["dim"])
        bounds = params.get("bounds", [(-5, 5)] * dim)
        npop = int(params.get("pop_size", 30))
        max_iter = int(params.get("max_iter", 100))
        w = float(params.get("w", 0.7))          # 惯性权重
        c1 = float(params.get("c1", 1.5))        # 认知项
        c2 = float(params.get("c2", 1.5))        # 社会项

        def clip(x):
            return [min(max(v, bounds[d][0]), bounds[d][1]) for d, v in enumerate(x)]

        pos = [clip(_rand_in(bounds)) for _ in range(npop)]
        vel = [[0.0] * dim for _ in range(npop)]
        pbest = [list(p) for p in pos]
        pval = [objective(p) for p in pos]
        gbest = min(range(npop), key=lambda i: pval[i])
        conv = [pval[gbest]]

        for _ in range(max_iter):
            for i in range(npop):
                for d in range(dim):
                    r1, r2 = random.random(), random.random()
                    cog = c1 * r1 * (pbest[i][d] - pos[i][d])
                    soc = c2 * r2 * (pos[gbest][d] - pos[i][d])
                    vel[i][d] = w * vel[i][d] + cog + soc
                pos[i] = clip([pos[i][d] + vel[i][d] for d in range(dim)])
                val = objective(pos[i])
                if val < pval[i]:
                    pval[i] = val
                    pbest[i] = list(pos[i])
            gbest = min(range(npop), key=lambda i: pval[i])
            conv.append(pval[gbest])

        return {
            "model_category": "optimization_meta",
            "model_id": "pso",
            "model_name": self.model_name,
            "method": "PSO(pure_python)",
            "status": "success",
            "best_x": [float(v) for v in pbest[gbest]],
            "best_value": float(pval[gbest]),
            "convergence": [float(v) for v in conv],
        }

    # ── 人工蜂群 (ABC) ──
    def _abc(self, **params: Any) -> Dict[str, Any]:
        objective = params.get("objective")
        if objective is None or not callable(objective):
            raise NotImplementedError("人工蜂群需要提供可调用目标函数 objective(x)")
        random.seed(int(params.get("random_state", 42)))
        dim = int(params["dim"])
        bounds = params.get("bounds", [(-5, 5)] * dim)
        npop = int(params.get("pop_size", 20))      # 蜂群规模（=雇佣蜂数）
        max_iter = int(params.get("max_iter", 50))
        limit = int(params.get("limit", 50))        # 弃用阈值

        def clip(x):
            return [min(max(v, bounds[d][0]), bounds[d][1]) for d, v in enumerate(x)]

        foods = [clip(_rand_in(bounds)) for _ in range(npop)]
        fit = [objective(f) for f in foods]
        trial = [0] * npop
        best = min(range(npop), key=lambda i: fit[i])
        conv = [fit[best]]

        for _ in range(max_iter):
            # 雇佣蜂
            for i in range(npop):
                k = random.randrange(npop)
                d = random.randrange(dim)
                cand = list(foods[i])
                cand[d] = clip([foods[i][d] + random.uniform(-1, 1) * (bounds[d][1] - bounds[d][0])])[0]
                cval = objective(cand)
                if cval < fit[i]:
                    foods[i], fit[i], trial[i] = cand, cval, 0
                else:
                    trial[i] += 1
            # 观察蜂（按适应度概率选择）
            total = sum(1.0 / (1.0 + fit[i]) for i in range(npop))
            for _ in range(npop):
                r = random.random() * total
                acc = 0.0
                sel = 0
                for i in range(npop):
                    acc += 1.0 / (1.0 + fit[i])
                    if acc >= r:
                        sel = i
                        break
                k = random.randrange(npop)
                d = random.randrange(dim)
                cand = list(foods[sel])
                cand[d] = clip([foods[sel][d] + random.uniform(-1, 1) * (bounds[d][1] - bounds[d][0])])[0]
                cval = objective(cand)
                if cval < fit[sel]:
                    foods[sel], fit[sel], trial[sel] = cand, cval, 0
                else:
                    trial[sel] += 1
            # 侦察蜂
            for i in range(npop):
                if trial[i] > limit:
                    foods[i] = clip(_rand_in(bounds))
                    fit[i] = objective(foods[i])
                    trial[i] = 0
            best = min(range(npop), key=lambda i: fit[i])
            conv.append(fit[best])

        return {
            "model_category": "optimization_meta",
            "model_id": "abc",
            "model_name": self.model_name,
            "method": "ABC(pure_python)",
            "status": "success",
            "best_x": [float(v) for v in foods[best]],
            "best_value": float(fit[best]),
            "convergence": [float(v) for v in conv],
        }

    # ── 蚁群算法 (TSP) ──
    def _ant_colony(self, **params: Any) -> Dict[str, Any]:
        dist = params.get("distance_matrix")
        coords = params.get("coords")
        if dist is None:
            if coords is None:
                raise ValueError("蚁群算法需要提供 distance_matrix（距离矩阵）或 coords（坐标列表）")
            n = len(coords)
            dist = [[0.0] * n for _ in range(n)]
            for i in range(n):
                for j in range(n):
                    dist[i][j] = math.hypot(coords[i][0] - coords[j][0], coords[i][1] - coords[j][1])
        n = len(dist)
        if n < 3:
            raise ValueError("蚁群算法(TSP)至少需要 3 个城市")
        n_ants = int(params.get("n_ants", min(20, n)))
        max_iter = int(params.get("max_iter", 50))
        alpha = float(params.get("alpha", 1.0))
        beta = float(params.get("beta", 2.0))
        rho = float(params.get("rho", 0.5))        # 信息素蒸发率
        random.seed(int(params.get("random_state", 42)))

        tau = [[1.0] * n for _ in range(n)]
        best_route = None
        best_len = float("inf")

        for _ in range(max_iter):
            routes = []
            lengths = []
            for _a in range(n_ants):
                visited = [random.randrange(n)]
                while len(visited) < n:
                    cur = visited[-1]
                    probs = []
                    for j in range(n):
                        if j in visited:
                            probs.append(0.0)
                        else:
                            eta = 1.0 / (dist[cur][j] + 1e-9)
                            probs.append((tau[cur][j] ** alpha) * (eta ** beta))
                    s = sum(probs)
                    if s <= 0:
                        nxt = next(j for j in range(n) if j not in visited)
                    else:
                        r = random.random() * s
                        acc = 0.0
                        nxt = visited[-1]
                        for j in range(n):
                            acc += probs[j]
                            if acc >= r:
                                nxt = j
                                break
                    visited.append(nxt)
                length = sum(dist[visited[i]][visited[i + 1]] for i in range(n - 1)) + dist[visited[-1]][visited[0]]
                routes.append(visited)
                lengths.append(length)
                if length < best_len:
                    best_len = length
                    best_route = list(visited)
            # 信息素更新
            for i in range(n):
                for j in range(n):
                    tau[i][j] *= (1 - rho)
            for r_i, length in enumerate(lengths):
                route = routes[r_i]
                deposit = 1.0 / (length + 1e-9)
                for i in range(n - 1):
                    tau[route[i]][route[i + 1]] += deposit
                tau[route[-1]][route[0]] += deposit

        return {
            "model_category": "optimization_meta",
            "model_id": "ant_colony",
            "model_name": self.model_name,
            "method": "AntColony(TSP,pure_python)",
            "status": "success",
            "best_route": [int(v) for v in best_route],
            "best_length": round(float(best_len), 6),
        }


register_category("optimization_meta", MetaHeuristicSolver)
