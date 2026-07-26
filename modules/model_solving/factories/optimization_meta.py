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
        if self.model_id in ("pso", "abc", "ant_colony"):
            raise NotImplementedError(
                f"模型 {self.model_id} 在恢复版尚未实现"
                f"（需要 pyswarm / scikit-opt / deap 等专用库，当前环境未安装）"
            )
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


register_category("optimization_meta", MetaHeuristicSolver)
