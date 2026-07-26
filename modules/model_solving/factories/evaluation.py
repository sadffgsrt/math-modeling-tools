# -*- coding: utf-8 -*-
"""
评价类模型求解器（category: evaluation）
全部用纯 Python 真实实现：AHP / TOPSIS / 熵权法 / 综合评价 / 灰色关联 / 模糊综合评价。
DEA（数据包络分析）需要线性规划求解器：优先使用 scipy，否则清晰抛出 ImportError（诚实）。
"""
from __future__ import annotations

import math
import random
from typing import Any, Dict, List

from ._base import BaseModelSolver, register_category, _matvec, _first_present, _as_matrix

_RI = {1: 0.0, 2: 0.0, 3: 0.58, 4: 0.90, 5: 1.12, 6: 1.24, 7: 1.32,
       8: 1.41, 9: 1.45, 10: 1.49, 11: 1.51, 12: 1.48}


def _principal_eigen(A: List[List[float]]) -> tuple:
    """幂迭代求主特征对（权重向量）"""
    n = len(A)
    random.seed(0)
    v = [random.uniform(0.1, 1.0) for _ in range(n)]
    norm = math.sqrt(sum(x * x for x in v))
    v = [x / norm for x in v]
    for _ in range(1000):
        w = _matvec(A, v)
        norm = math.sqrt(sum(x * x for x in w))
        v = [x / norm for x in w]
    lam = sum(v[i] * sum(A[i][j] * v[j] for j in range(n)) for i in range(n))
    return lam, v


class EvaluationSolver(BaseModelSolver):
    """评价类求解器"""

    model_category = "evaluation"

    def solve(self, **params: Any) -> Dict[str, Any]:
        mid = self.model_id
        if mid == "ahp":
            return self._ahp(**params)
        if mid == "topsis":
            return self._topsis(**params)
        if mid == "entropy_weight":
            return self._entropy_weight(**params)
        if mid == "comprehensive_evaluation":
            return self._comprehensive(**params)
        if mid == "grey_relational":
            return self._grey_relational(**params)
        if mid == "fuzzy_evaluation":
            return self._fuzzy_evaluation(**params)
        if mid == "dea":
            return self._dea(**params)
        raise NotImplementedError(f"模型 {self.model_id} 在恢复版尚未实现")

    # ── AHP ──
    def _ahp(self, **params: Any) -> Dict[str, Any]:
        M = _first_present(params, "matrix", "judgment_matrix")
        if M is None:
            raise ValueError("AHP 需要提供 matrix（正互反判断矩阵）")
        M = _as_matrix(M)
        n = len(M)
        for i in range(n):
            for j in range(n):
                if M[i][j] <= 0:
                    raise ValueError("判断矩阵含非正数，AHP 要求正互反矩阵")
        # 正互反性检验：a_ij * a_ji ≈ 1
        for i in range(n):
            for j in range(i + 1, n):
                if abs(M[i][j] * M[j][i] - 1.0) > 0.1:
                    raise ValueError("判断矩阵不满足正互反性（a_ij * a_ji 应≈1）")
        lam, v = _principal_eigen(M)
        s = sum(v)
        weights = [x / s for x in v]
        ri = _RI.get(n, 1.5)
        ci = (lam - n) / (n - 1) if n > 1 else 0.0
        cr = ci / ri if ri > 0 else 0.0
        return {
            "model_category": "evaluation",
            "model_id": "ahp",
            "model_name": self.model_name,
            "method": "AHP",
            "status": "success",
            "weights": [round(float(w), 6) for w in weights],
            "lambda_max": round(float(lam), 6),
            "CI": round(float(ci), 6),
            "CR": round(float(cr), 6),
        }

    # ── TOPSIS ──
    def _topsis(self, **params: Any) -> Dict[str, Any]:
        dm = params["matrix"]
        n = len(dm[0])
        weights = params.get("weights") or [1.0 / n] * n
        m = len(dm)
        norm = [
            [dm[i][j] / math.sqrt(sum(dm[k][j] ** 2 for k in range(m))) for j in range(n)]
            for i in range(m)
        ]
        v = [[norm[i][j] * weights[j] for j in range(n)] for i in range(m)]
        ideal = [max(v[i][j] for i in range(m)) for j in range(n)]
        anti = [min(v[i][j] for i in range(m)) for j in range(n)]
        dpos = [math.sqrt(sum((v[i][j] - ideal[j]) ** 2 for j in range(n))) for i in range(m)]
        dneg = [math.sqrt(sum((v[i][j] - anti[j]) ** 2 for j in range(n))) for i in range(m)]
        scores = [
            dneg[i] / (dpos[i] + dneg[i]) if (dpos[i] + dneg[i]) > 0 else 0.0
            for i in range(m)
        ]
        ranking = sorted(range(m), key=lambda i: -scores[i])
        return {
            "model_category": "evaluation",
            "model_id": "topsis",
            "model_name": self.model_name,
            "method": "TOPSIS",
            "status": "success",
            "scores": [round(float(s), 6) for s in scores],
            "ranking": ranking,
        }

    # ── 熵权法 ──
    def _entropy_weight(self, **params: Any) -> Dict[str, Any]:
        dm = params["matrix"]
        m, n = len(dm), len(dm[0])
        col_sum = [sum(dm[i][j] for i in range(m)) for j in range(n)]
        p = [
            [dm[i][j] / col_sum[j] if col_sum[j] > 0 else 0.0 for j in range(n)]
            for i in range(m)
        ]
        e = [0.0] * n
        for j in range(n):
            ej = 0.0
            for i in range(m):
                if p[i][j] > 0:
                    ej -= p[i][j] * math.log(p[i][j])
            e[j] = ej / math.log(m) if m > 1 else 0.0
        d = [1 - ej for ej in e]
        s = sum(d)
        w = [dj / s if s > 0 else 1.0 / n for dj in d]
        return {
            "model_category": "evaluation",
            "model_id": "entropy_weight",
            "model_name": self.model_name,
            "method": "EntropyWeight",
            "status": "success",
            "weights": [round(float(x), 6) for x in w],
        }

    # ── 综合评价（熵权 + TOPSIS） ──
    def _comprehensive(self, **params: Any) -> Dict[str, Any]:
        dm = params["matrix"]
        wres = self._entropy_weight(matrix=dm)
        tres = self._topsis(matrix=dm, weights=wres["weights"])
        return {
            "model_category": "evaluation",
            "model_id": "comprehensive_evaluation",
            "model_name": self.model_name,
            "method": "ComprehensiveEvaluation",
            "status": "success",
            "entropy_weights": wres["weights"],
            "scores": tres["scores"],
            "ranking": tres["ranking"],
        }

    # ── 灰色关联分析 ──
    def _grey_relational(self, **params: Any) -> Dict[str, Any]:
        dm = params["matrix"]
        rho = float(params.get("rho", 0.5))
        m, n = len(dm), len(dm[0])
        ref = [max(dm[i][j] for i in range(m)) for j in range(n)]
        delta = [[abs(dm[i][j] - ref[j]) for j in range(n)] for i in range(m)]
        min_d = min(min(row) for row in delta)
        max_d = max(max(row) for row in delta)
        grades = []
        for i in range(m):
            g = sum(
                (min_d + rho * max_d) / (delta[i][j] + rho * max_d)
                for j in range(n)
            ) / n
            grades.append(g)
        ranking = sorted(range(m), key=lambda i: -grades[i])
        return {
            "model_category": "evaluation",
            "model_id": "grey_relational",
            "model_name": self.model_name,
            "method": "GreyRelationalAnalysis",
            "status": "success",
            "rho": rho,
            "grey_grades": [round(float(g), 6) for g in grades],
            "ranking": ranking,
        }

    # ── 模糊综合评价 ──
    def _fuzzy_evaluation(self, **params: Any) -> Dict[str, Any]:
        em = params["matrix"]  # 行=准则，列=评语等级
        m, n = len(em), len(em[0])
        # 各评语等级聚合隶属度（按准则求和）
        agg = [sum(em[i][j] for i in range(m)) for j in range(n)]
        s = sum(agg)
        if s > 0:
            agg = [a / s for a in agg]
        # 重心法解模糊：评语等级取 1..n
        score = sum((j + 1) * agg[j] for j in range(n)) / n  # 归一到 [0,1] 附近
        # 映射到等级标签
        if score >= 0.75:
            label = "优"
        elif score >= 0.5:
            label = "良"
        elif score >= 0.25:
            label = "中"
        else:
            label = "差"
        return {
            "model_category": "evaluation",
            "model_id": "fuzzy_evaluation",
            "model_name": self.model_name,
            "method": "FuzzyComprehensiveEvaluation",
            "status": "success",
            "evaluation_result": [round(float(a), 6) for a in agg],
            "defuzzified_score": round(float(score), 6),
            "grade_label": label,
        }

    # ── DEA（需 LP 求解器） ──
    def _dea(self, **params: Any) -> Dict[str, Any]:
        try:
            from scipy.optimize import linprog  # type: ignore
        except ImportError as e:
            raise ImportError(
                "DEA 求解需要线性规划求解器（scipy.optimize.linprog），当前环境未安装；"
                "请安装 scipy 后重试"
            ) from e
        inputs = _as_matrix(params["inputs"])
        outputs = _as_matrix(params["outputs"])
        n_in = len(inputs)
        if n_in == 0:
            raise ValueError("DEA 需要提供 inputs（输入指标矩阵，行=输入指标/列=DMU）")
        n_dmu = len(inputs[0])
        n_out = len(outputs)
        if n_out == 0:
            raise ValueError("DEA 需要提供 outputs（输出指标矩阵，行=输出指标/列=DMU）")
        # 形状校验：每行长度必须等于 DMU 数，否则下方按 DMU 索引列会越界
        for i, row in enumerate(inputs):
            if len(row) != n_dmu:
                raise ValueError(
                    f"DEA inputs 第 {i} 行长度为 {len(row)}，应等于 DMU 数 {n_dmu}"
                )
        for r, row in enumerate(outputs):
            if len(row) != n_dmu:
                raise ValueError(
                    f"DEA outputs 第 {r} 行长度为 {len(row)}，应等于 DMU 数 {n_dmu}"
                )
        eff = []
        for o in range(n_dmu):
            # 变量：theta + 每个 DMU 一个 lambda，共 1 + n_dmu 个
            c = [1.0] + [0.0] * n_dmu
            A_ub = []
            b_ub = []
            # 输入约束：sum_j lambda_j * x_ij <= theta * x_io  (i = 1..n_in)
            for i in range(n_in):
                row = [-float(inputs[i][o])] + [
                    float(inputs[i][j]) for j in range(n_dmu)
                ]
                A_ub.append(row)
                b_ub.append(0.0)
            # 输出约束：sum_j lambda_j * y_rj >= y_ro  ->  -sum_j lambda_j * y_rj <= -y_ro
            for r in range(n_out):
                row = [0.0] + [
                    -float(outputs[r][j]) for j in range(n_dmu)
                ]
                A_ub.append(row)
                b_ub.append(-float(outputs[r][o]))
            res = linprog(c, A_ub=A_ub, b_ub=b_ub, bounds=(0, None), method="highs")
            eff.append(float(res.x[0]) if res.success else float("nan"))
        return {
            "model_category": "evaluation",
            "model_id": "dea",
            "model_name": self.model_name,
            "method": "DEA_CCR(scipy)",
            "status": "success",
            "model": "CCR_input_oriented",
            "efficiency_scores": [round(e, 6) for e in eff],
        }


register_category("evaluation", EvaluationSolver)
