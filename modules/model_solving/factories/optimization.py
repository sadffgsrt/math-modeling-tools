"""
优化类模型求解器（category: optimization）
真实实现（纯 Python）：线性规划(单纯形 / scipy)、动态规划(背包/LCS)、模拟退火。
整数规划需要 MILP 求解器，诚实声明未实现。
"""
from __future__ import annotations

import json
import math
import random
from typing import Any, Dict, List, Optional, Tuple

from ._base import BaseModelSolver, register_category


# ───────────────────────── 线性规划：纯 Python 单纯形 ─────────────────────────

def _simplex_standard(c: List[float], A_ub: List[List[float]], b_ub: List[float]
                      ) -> Tuple[Optional[List[float]], Optional[float], str]:
    """
    标准形单纯形法：min cᵀx  s.t. A_ub x ≤ b_ub, x ≥ 0, b_ub ≥ 0。
    返回 (解向量, 最优值, 状态)。支持 scipy 未安装时的真实求解。
    """
    n = len(c)
    m = len(A_ub)
    eps = 1e-9
    T: List[List[float]] = []
    for i in range(m):
        row = [float(v) for v in A_ub[i]] + [0.0] * m
        row[n + i] = 1.0  # 松弛变量
        row.append(float(b_ub[i]))
        T.append(row)
    basis = [n + i for i in range(m)]
    obj = [float(v) for v in c] + [0.0] * m

    for _ in range(2000):
        cB = [obj[basis[i]] for i in range(m)]
        redcost = [
            obj[j] - sum(cB[i] * T[i][j] for i in range(m))
            for j in range(n + m)
        ]
        # 最小化：选最负的检验数作为入基
        ent = None
        minrc = -eps
        for j in range(n + m):
            if redcost[j] < minrc:
                minrc = redcost[j]
                ent = j
        if ent is None:
            break  # 已达最优
        pivot_row = None
        min_ratio = None
        for i in range(m):
            if T[i][ent] > eps:
                ratio = T[i][n + m] / T[i][ent]
                if min_ratio is None or ratio < min_ratio:
                    min_ratio = ratio
                    pivot_row = i
        if pivot_row is None:
            return None, None, "unbounded"
        piv = T[pivot_row][ent]
        T[pivot_row] = [v / piv for v in T[pivot_row]]
        for i in range(m):
            if i != pivot_row and T[i][ent] != 0:
                factor = T[i][ent]
                T[i] = [T[i][j] - factor * T[pivot_row][j] for j in range(n + m + 1)]
        basis[pivot_row] = ent

    x = [0.0] * (n + m)
    for i in range(m):
        x[basis[i]] = T[i][n + m]
    xb = x[:n]
    obj_val = sum(c[j] * xb[j] for j in range(n))
    return xb, obj_val, "success"


class OptimizationSolver(BaseModelSolver):
    """优化类求解器"""

    model_category = "optimization"

    def solve(self, **params: Any) -> Dict[str, Any]:
        if self.model_id == "linear_programming":
            return self._solve_linear_programming(**params)
        if self.model_id == "dynamic_programming":
            return self._solve_dynamic_programming(**params)
        if self.model_id == "simulated_annealing":
            return self._solve_simulated_annealing(**params)
        if self.model_id == "integer_programming":
            return self._solve_integer_programming(**params)
        raise NotImplementedError(f"模型 {self.model_id} 在恢复版尚未实现")

    # ── 线性规划 ──
    def _solve_linear_programming(self, **params: Any) -> Dict[str, Any]:
        c, A_ub, b_ub = self._load_lp_params(params)
        # 优先使用 scipy（若环境安装了）
        try:
            from scipy.optimize import linprog  # type: ignore
            res = linprog(c, A_ub=A_ub, b_ub=b_ub, bounds=(0, None), method="highs")
            if res.success:
                return {
                    "model_category": "optimization",
                    "model_id": "linear_programming",
                    "model_name": self.model_name,
                    "method": "scipy.linprog",
                    "status": "success",
                    "x": [float(v) for v in res.x],
                    "optimal_value": float(res.fun),
                }
            raise RuntimeError(res.message)
        except ImportError:
            pass  # 退回纯 Python 单纯形

        # 纯 Python 单纯形（仅支持标准形 b_ub ≥ 0）
        if any(b < 0 for b in b_ub):
            raise NotImplementedError(
                "当前纯 Python 单纯形仅支持 b_ub ≥ 0 的标准形式；"
                "更一般的线性规划请在安装 scipy 后使用 scipy.optimize.linprog"
            )
        x, val, status = _simplex_standard(c, A_ub, b_ub)
        if status != "success":
            return {
                "model_category": "optimization",
                "model_id": "linear_programming",
                "model_name": self.model_name,
                "method": "pure_python_simplex",
                "status": status,
            }
        return {
            "model_category": "optimization",
            "model_id": "linear_programming",
            "model_name": self.model_name,
            "method": "pure_python_simplex",
            "status": "success",
            "x": [float(v) for v in x],
            "optimal_value": float(val),
        }

    def _load_lp_params(self, params: Dict[str, Any]):
        """从直接参数或 JSON 文件加载 LP 参数"""
        c = params.get("c")
        A_ub = params.get("A_ub")
        b_ub = params.get("b_ub")
        path = params.get("optimization_params_path") or params.get("params_path")
        if (c is None or A_ub is None or b_ub is None) and path:
            with open(path, "r", encoding="utf-8") as f:
                cfg = json.load(f)
            c = cfg.get("c")
            A_ub = cfg.get("A_ub")
            b_ub = cfg.get("b_ub")
        if c is None or A_ub is None or b_ub is None:
            raise ValueError(
                "线性规划需要提供 c / A_ub / b_ub 参数，或通过 optimization_params_path 提供 JSON"
            )
        return [float(v) for v in c], [[float(v) for v in row] for row in A_ub], [float(v) for v in b_ub]

    # ── 动态规划 ──
    def _solve_dynamic_programming(self, **params: Any) -> Dict[str, Any]:
        problem_type = params.get("problem_type", "knapsack")
        if problem_type == "knapsack":
            values = [float(v) for v in params["values"]]
            weights = [float(w) for w in params["weights"]]
            capacity = float(params["capacity"])
            n = len(values)
            # DP 表
            dp = [[0.0] * (int(capacity) + 1) for _ in range(n + 1)]
            keep = [[False] * (int(capacity) + 1) for _ in range(n + 1)]
            for i in range(1, n + 1):
                wi = int(weights[i - 1])
                vi = values[i - 1]
                for w in range(int(capacity) + 1):
                    if wi <= w and dp[i - 1][w - wi] + vi > dp[i - 1][w]:
                        dp[i][w] = dp[i - 1][w - wi] + vi
                        keep[i][w] = True
                    else:
                        dp[i][w] = dp[i - 1][w]
            # 回溯选中物品
            selected = []
            w = int(capacity)
            for i in range(n, 0, -1):
                if keep[i][w]:
                    selected.append(i - 1)
                    w -= int(weights[i - 1])
            selected.sort()
            return {
                "model_category": "optimization",
                "model_id": "dynamic_programming",
                "model_name": self.model_name,
                "problem_type": "0-1 knapsack",
                "status": "success",
                "optimal_value": float(dp[n][int(capacity)]),
                "selected_items": selected,
                "total_weight": int(capacity) - w,
            }
        if problem_type == "lcs":
            s1 = list(params["values"])
            s2 = list(params["weights"])
            m, n = len(s1), len(s2)
            dp = [[0] * (n + 1) for _ in range(m + 1)]
            for i in range(1, m + 1):
                for j in range(1, n + 1):
                    if s1[i - 1] == s2[j - 1]:
                        dp[i][j] = dp[i - 1][j - 1] + 1
                    else:
                        dp[i][j] = max(dp[i - 1][j], dp[i][j - 1])
            # 回溯
            i, j, seq = m, n, []
            while i > 0 and j > 0:
                if s1[i - 1] == s2[j - 1]:
                    seq.append(s1[i - 1])
                    i -= 1
                    j -= 1
                elif dp[i - 1][j] >= dp[i][j - 1]:
                    i -= 1
                else:
                    j -= 1
            seq.reverse()
            return {
                "model_category": "optimization",
                "model_id": "dynamic_programming",
                "model_name": self.model_name,
                "problem_type": "longest_common_subsequence",
                "status": "success",
                "optimal_value": int(dp[m][n]),
                "lcs": seq,
            }
        raise ValueError(f"动态规划不支持的问题类型：{problem_type}")

    # ── 模拟退火 ──
    def _solve_simulated_annealing(self, **params: Any) -> Dict[str, Any]:
        objective = params.get("objective")
        if objective is None or not callable(objective):
            raise NotImplementedError(
                "模拟退火需要提供可调用目标函数 objective(x)；工具调用场景下请在程序中传入"
            )
        import random as _r
        _r.seed(int(params.get("random_state", 42)))
        x0 = [float(v) for v in params.get("x0", [0.0, 0.0])]
        bounds = params.get("bounds", [(-5, 5)] * len(x0))
        max_iter = int(params.get("max_iter", 500))
        T0 = float(params.get("initial_temp", 200.0))
        cooling = float(params.get("cooling_rate", 0.97))

        def within(x):
            return all(bounds[i][0] <= x[i] <= bounds[i][1] for i in range(len(x)))

        cur = list(x0)
        cur_val = objective(cur)
        best, best_val = list(cur), cur_val
        T = T0
        conv = [cur_val]
        for _ in range(max_iter):
            prop = [
                min(max(cur[i] + _r.uniform(-1, 1) * (bounds[i][1] - bounds[i][0]) * 0.1,
                        bounds[i][0]), bounds[i][1])
                for i in range(len(cur))
            ]
            prop_val = objective(prop)
            if prop_val < cur_val or _r.random() < math.exp((cur_val - prop_val) / T):
                cur, cur_val = prop, prop_val
                if cur_val < best_val:
                    best, best_val = list(cur), cur_val
            T *= cooling
            conv.append(cur_val)
        return {
            "model_category": "optimization",
            "model_id": "simulated_annealing",
            "model_name": self.model_name,
            "method": "pure_python_simulated_annealing",
            "status": "success",
            "best_x": [float(v) for v in best],
            "best_value": float(best_val),
            "convergence": [float(v) for v in conv],
        }

    # ── 整数规划（0-1 ILP）──
    def _solve_integer_programming(self, **params: Any) -> Dict[str, Any]:
        c, A_ub, b_ub = self._load_lp_params(params)
        n = len(c)
        # 优先使用 scipy 的整数规划求解器（若环境安装了）
        try:
            import numpy as _np  # type: ignore
            from scipy.optimize import milp, LinearConstraint, Bounds  # type: ignore
            res = milp(
                c=_np.array(c, dtype=float),
                constraints=LinearConstraint(_np.array(A_ub, dtype=float), lb=-_np.inf, ub=_np.array(b_ub, dtype=float)),
                bounds=Bounds(lb=0.0, ub=1.0),
                integrality=1,
            )
            if res.success:
                x = [int(round(float(v))) for v in res.x]
                return {
                    "model_category": "optimization",
                    "model_id": "integer_programming",
                    "model_name": self.model_name,
                    "method": "scipy.optimize.milp",
                    "status": "success",
                    "x": x,
                    "selected_items": [i for i in range(n) if x[i] == 1],
                    "optimal_value": float(res.fun),
                }
            return {
                "model_category": "optimization",
                "model_id": "integer_programming",
                "model_name": self.model_name,
                "method": "scipy.optimize.milp",
                "status": "infeasible",
            }
        except ImportError:
            pass  # 退回纯 Python 枚举

        # 纯 Python 回退：完全枚举 0/1 组合（仅适用于小规模 n<=16）
        if n > 16:
            raise NotImplementedError(
                "纯 Python 整数规划回退仅支持变量数 n<=16 的 0-1 枚举；"
                "更大规模请在安装 scipy 后使用 scipy.optimize.milp"
            )
        best = None
        best_val = float("inf")
        for mask in range(1 << n):
            x = [(mask >> i) & 1 for i in range(n)]
            feasible = True
            for i in range(len(A_ub)):
                if sum(A_ub[i][j] * x[j] for j in range(n)) > b_ub[i] + 1e-9:
                    feasible = False
                    break
            if not feasible:
                continue
            val = sum(c[j] * x[j] for j in range(n))
            if val < best_val:
                best_val = val
                best = x
        if best is None:
            return {
                "model_category": "optimization",
                "model_id": "integer_programming",
                "model_name": self.model_name,
                "method": "pure_python_enumeration",
                "status": "infeasible",
            }
        return {
            "model_category": "optimization",
            "model_id": "integer_programming",
            "model_name": self.model_name,
            "method": "pure_python_enumeration",
            "status": "success",
            "x": best,
            "selected_items": [i for i in range(n) if best[i] == 1],
            "optimal_value": float(best_val),
        }


register_category("optimization", OptimizationSolver)
