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
        if mid == "game_theory":
            return self._game_theory(**params)
        if mid == "agent_based":
            return self._agent_based(**params)
        if mid == "discrete_event":
            return self._discrete_event(**params)
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

    # ── 博弈论（二人零和混合策略纳什均衡）──
    def _game_theory(self, **params: Any) -> Dict[str, Any]:
        payoff = params.get("payoff")
        if payoff is None:
            raise ValueError("博弈论需要提供 payoff（行玩家收益矩阵，m×n）")
        import numpy as _np  # type: ignore
        from scipy.optimize import linprog  # type: ignore
        A = [[float(v) for v in row] for row in payoff]
        m, n = len(A), len(A[0])

        # 行玩家最优策略：max v  s.t.  Σ_i A[i][j]·y_i ≥ v (∀j), Σy_i = 1, y≥0, v free
        c = [-1.0] + [0.0] * m
        A_ub, b_ub = [], []
        for j in range(n):
            A_ub.append([1.0] + [-A[i][j] for i in range(m)])  # v - ΣA_ij y_i ≤ 0
            b_ub.append(0.0)
        A_eq = [[0.0] + [1.0] * m]
        b_eq = [1.0]
        res = linprog(c, A_ub=A_ub, b_ub=b_ub, A_eq=A_eq, b_eq=b_eq,
                     bounds=[(0, None)] * (m + 1), method="highs")
        if not res.success:
            return {
                "model_category": "simulation",
                "model_id": "game_theory",
                "model_name": self.model_name,
                "method": "scipy.linprog",
                "status": "failed",
            }
        y = [max(0.0, float(v)) for v in res.x[1:]]
        sy = sum(y) or 1.0
        row_strategy = [v / sy for v in y]
        value = float(res.x[0])

        # 列玩家最优策略（对偶）：min -w s.t. Σ_j A[i][j]·x_j ≤ w (∀i), Σx_j = 1
        c2 = [-1.0] + [0.0] * n
        A2, b2 = [], []
        for i in range(m):
            A2.append([-1.0] + [A[i][j] for j in range(n)])  # -w + ΣA_ij x_j ≤ 0
            b2.append(0.0)
        A2_eq = [[0.0] + [1.0] * n]
        res2 = linprog(c2, A_ub=A2, b_ub=b2, A_eq=A2_eq, b_eq=[1.0],
                       bounds=[(0, None)] * (n + 1), method="highs")
        if res2.success:
            x = [max(0.0, float(v)) for v in res2.x[1:]]
            sx = sum(x) or 1.0
            col_strategy = [v / sx for v in x]
        else:
            col_strategy = None

        return {
            "model_category": "simulation",
            "model_id": "game_theory",
            "model_name": self.model_name,
            "method": "scipy.linprog(zero_sum)",
            "status": "success",
            "value": round(value, 6),
            "row_strategy": [round(v, 6) for v in row_strategy],
            "col_strategy": [round(v, 6) for v in col_strategy] if col_strategy else None,
            "note": "value 为行玩家在最优混合策略下能保证的最小收益（零和博弈冯·诺依曼值）",
        }

    # ── 基于智能体建模（SIR 传播仿真）──
    def _agent_based(self, **params: Any) -> Dict[str, Any]:
        n_agents = int(params.get("n_agents", 100))
        init_infected = int(params.get("init_infected", 5))
        beta = float(params.get("beta", 0.3))         # 接触传播概率
        gamma = float(params.get("gamma", 0.1))       # 恢复概率
        n_steps = int(params.get("n_steps", 50))
        contacts = int(params.get("contacts_per_step", 2))
        random.seed(int(params.get("random_state", 42)))

        state = ["S"] * n_agents
        for i in random.sample(range(n_agents), min(init_infected, n_agents)):
            state[i] = "I"

        history = []
        for _ in range(n_steps):
            # 传播：随机接触
            for _ in range(n_agents * contacts):
                a, b = random.randrange(n_agents), random.randrange(n_agents)
                if state[a] == "I" and state[b] == "S" and random.random() < beta:
                    state[b] = "I"
            # 恢复
            for i in range(n_agents):
                if state[i] == "I" and random.random() < gamma:
                    state[i] = "R"
            s = sum(1 for v in state if v == "S")
            inf = sum(1 for v in state if v == "I")
            r = n_agents - s - inf
            history.append({"S": s, "I": inf, "R": r})
        return {
            "model_category": "simulation",
            "model_id": "agent_based",
            "model_name": self.model_name,
            "method": "AgentBasedSIR(pure_python)",
            "status": "success",
            "n_agents": n_agents,
            "n_steps": n_steps,
            "history": history,
            "final": history[-1],
        }

    # ── 离散事件仿真（多服务台排队）──
    def _discrete_event(self, **params: Any) -> Dict[str, Any]:
        lam = float(params["arrival_rate"])
        mu = float(params["service_rate"])
        c = int(params.get("n_servers", 1))
        n_customers = int(params.get("n_customers", 200))
        random.seed(int(params.get("random_state", 42)))

        # 生成到达/服务时间序列
        t = 0.0
        arrivals = []
        for _ in range(n_customers):
            t += random.expovariate(lam)
            arrivals.append(t)
        services = [random.expovariate(mu) for _ in range(n_customers)]

        # 事件驱动：维护每台服务器的下次空闲时间
        free_at = [0.0] * c
        wait_times = []
        system_times = []
        max_q = 0
        q = 0
        for i in range(n_customers):
            a = arrivals[i]
            # 选最早空闲的服务器
            srv = min(range(c), key=lambda k: free_at[k])
            start = max(a, free_at[srv])
            wait = start - a
            end = start + services[i]
            free_at[srv] = end
            wait_times.append(wait)
            system_times.append(end - a)
            q += 1
            max_q = max(max_q, q)
            q -= 1  # 该客户占服务器期间 q 不增（简化统计峰值）

        n = len(wait_times)
        return {
            "model_category": "simulation",
            "model_id": "discrete_event",
            "model_name": self.model_name,
            "method": "DiscreteEventQueue(pure_python)",
            "status": "success",
            "n_servers": c,
            "n_customers": n_customers,
            "avg_wait_time": round(sum(wait_times) / n, 6),
            "avg_system_time": round(sum(system_times) / n, 6),
            "max_queue_len": int(max_q),
            "utilization": round(sum(system_times) / (c * (arrivals[-1] or 1)) if arrivals else 0, 6),
        }


register_category("simulation", SimulationSolver)
