# -*- coding: utf-8 -*-
"""
仿真类模型求解器（category: simulation）
真实实现（纯 Python）：蒙特卡洛、元胞自动机(Game of Life)、排队论(M/M/c)、系统动力学(RK4)。
博弈论 / 基于智能体 / 离散事件需要 nashpy / mesa / simpy，诚实声明未实现。
"""
from __future__ import annotations

import math
import random
from typing import Any, Callable, Dict, List

from ._base import BaseModelSolver, register_category


class SimulationSolver(BaseModelSolver):
    """仿真类求解器"""

    model_category = "simulation"

    def solve(self, **params: Any) -> Dict[str, Any]:
        mid = self.model_id
        if mid == "monte_carlo":
            return self._monte_carlo(**params)
        if mid == "cellular_automata":
            return self._cellular_automata(**params)
        if mid == "queueing_theory":
            return self._queueing(**params)
        if mid == "system_dynamics":
            return self._system_dynamics(**params)
        if mid in ("game_theory", "agent_based", "discrete_event"):
            raise NotImplementedError(
                f"模型 {self.model_id} 在恢复版尚未实现"
                f"（需要 nashpy / mesa / simpy 库，当前环境未安装）"
            )
        raise NotImplementedError(f"模型 {self.model_id} 在恢复版尚未实现")

    def _monte_carlo(self, **params: Any) -> Dict[str, Any]:
        objective = params.get("objective")
        n = int(params.get("n_simulations", 500))
        random.seed(int(params.get("random_state", 42)))
        if objective is not None and callable(objective):
            samples = [float(objective()) for _ in range(n)]
        elif params.get("samples") is not None:
            samples = [float(v) for v in params["samples"]]
        else:
            raise NotImplementedError(
                "蒙特卡洛模拟需要提供可调用 objective() 或在程序中传入 samples 列表"
            )
        mean = sum(samples) / n
        var = sum((s - mean) ** 2 for s in samples) / max(n - 1, 1)
        return {
            "model_category": "simulation",
            "model_id": "monte_carlo",
            "model_name": self.model_name,
            "method": "MonteCarlo(pure_python)",
            "status": "success",
            "n_simulations": n,
            "mean": round(mean, 6),
            "std": round(math.sqrt(var), 6),
            "min": round(min(samples), 6),
            "max": round(max(samples), 6),
        }

    def _cellular_automata(self, **params: Any) -> Dict[str, Any]:
        import copy
        grid = params.get("initial")
        if grid is None:
            raise ValueError("元胞自动机需要提供 initial（二维 0/1 网格）")
        n_steps = int(params.get("n_steps", 3))
        g = [list(r) for r in grid]
        history = [copy.deepcopy(g)]

        def neighbors(i, j, H, W):
            cnt = 0
            for di in (-1, 0, 1):
                for dj in (-1, 0, 1):
                    if di == 0 and dj == 0:
                        continue
                    ni, nj = i + di, j + dj
                    if 0 <= ni < H and 0 <= nj < W and g[ni][nj]:
                        cnt += 1
            return cnt

        H, W = len(g), len(g[0])
        for _ in range(n_steps):
            ng = [[0] * W for _ in range(H)]
            for i in range(H):
                for j in range(W):
                    nb = neighbors(i, j, H, W)
                    if g[i][j]:
                        ng[i][j] = 1 if nb in (2, 3) else 0
                    else:
                        ng[i][j] = 1 if nb == 3 else 0
            g = ng
            history.append(copy.deepcopy(g))
        return {
            "model_category": "simulation",
            "model_id": "cellular_automata",
            "model_name": self.model_name,
            "method": "CellularAutomata(GameOfLife)",
            "status": "success",
            "history": history,
            "n_steps": n_steps,
        }

    def _queueing(self, **params: Any) -> Dict[str, Any]:
        lam = float(params["arrival_rate"])
        mu = float(params["service_rate"])
        c = int(params.get("n_servers", 1))
        rho = lam / (c * mu)
        if rho >= 1:
            return {
                "model_category": "simulation",
                "model_id": "queueing_theory",
                "model_name": self.model_name,
                "model": "M/M/c",
                "status": "unstable",
                "rho": round(rho, 6),
                "note": "系统不稳定（rho>=1）",
            }
        # Erlang C
        r = lam / mu
        # P0
        terms = [r ** k / math.factorial(k) for k in range(c)]
        sum_terms = sum(terms)
        last = (r ** c / math.factorial(c)) * (1 / (1 - rho))
        p0 = 1.0 / (sum_terms + last)
        p_wait = (r ** c / math.factorial(c)) * (1 / (1 - rho)) * p0
        avg_wait = p_wait / (c * mu - lam)
        avg_sys = avg_wait + r / c
        return {
            "model_category": "simulation",
            "model_id": "queueing_theory",
            "model_name": self.model_name,
            "model": "M/M/c",
            "status": "success",
            "rho": round(rho, 6),
            "utilization": round(rho, 6),
            "P_wait": round(p_wait, 6),
            "avg_wait_time": round(avg_wait, 6),
            "avg_system_time": round(avg_sys, 6),
        }

    def _system_dynamics(self, **params: Any) -> Dict[str, Any]:
        f = params.get("f")
        if f is None or not callable(f):
            raise NotImplementedError(
                "系统动力学需要提供可调用微分方程 f(t, y)（y 为列表）"
            )
        y0 = [float(v) for v in params["y0"]]
        t0, t1 = params.get("t_span", (0, 5))
        n = int(params.get("n_steps", 100))
        h = (t1 - t0) / n
        ts = [t0]
        ys = [list(y0)]
        t = t0
        y = list(y0)
        for _ in range(n):
            k1 = f(t, y)
            k2 = f(t + h / 2, [y[i] + h / 2 * k1[i] for i in range(len(y))])
            k3 = f(t + h / 2, [y[i] + h / 2 * k2[i] for i in range(len(y))])
            k4 = f(t + h, [y[i] + h * k3[i] for i in range(len(y))])
            y = [y[i] + h / 6 * (k1[i] + 2 * k2[i] + 2 * k3[i] + k4[i]) for i in range(len(y))]
            t += h
            ts.append(t)
            ys.append(list(y))
        return {
            "model_category": "simulation",
            "model_id": "system_dynamics",
            "model_name": self.model_name,
            "method": "RK4(pure_python)",
            "status": "success",
            "time_points": [round(float(v), 6) for v in ts],
            "trajectories": [[round(float(v), 6) for v in row] for row in ys],
        }


register_category("simulation", SimulationSolver)
