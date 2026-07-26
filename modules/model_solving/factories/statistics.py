# -*- coding: utf-8 -*-
"""
统计分析模型求解器（category: statistics）
真实实现（纯 Python）：单因素方差分析(ANOVA, F 检验含数值积分求 p 值)、指数平滑(Holt 线性趋势)。
"""
from __future__ import annotations

import math
from typing import Any, Dict, List

from ._base import BaseModelSolver, register_category


def _beta(a: float, b: float) -> float:
    return math.exp(math.lgamma(a) + math.lgamma(b) - math.lgamma(a + b))


def _f_pdf(x: float, d1: float, d2: float) -> float:
    if x <= 0:
        return 0.0
    return ((d1 / d2) ** (d1 / 2) * x ** (d1 / 2 - 1) / _beta(d1 / 2, d2 / 2)
            * (1 + d1 * x / d2) ** (-(d1 + d2) / 2))


def _f_sf(F: float, d1: float, d2: float) -> float:
    """F 分布生存函数 P(X>F)，用变量替换 t=1/x 后 Simpson 数值积分。"""
    if F <= 0:
        return 1.0
    upper = 1.0 / F
    N = 2000
    h = upper / N

    def g(u: float) -> float:
        if u <= 0:
            return 0.0
        x = 1.0 / u
        return _f_pdf(x, d1, d2) * (1.0 / (u * u))

    s = g(0) + g(upper)
    for k in range(1, N):
        s += 2 * g(k * h) if k % 2 == 0 else 4 * g(k * h)
    return s * h / 3.0


class StatisticsSolver(BaseModelSolver):
    """统计分析求解器"""

    model_category = "statistics"

    def solve(self, **params: Any) -> Dict[str, Any]:
        if self.model_id == "anova":
            return self._anova(**params)
        if self.model_id == "exponential_smoothing":
            return self._exp_smoothing(**params)
        raise NotImplementedError(f"模型 {self.model_id} 在恢复版尚未实现")

    def _anova(self, **params: Any) -> Dict[str, Any]:
        groups = params.get("groups")
        if groups is None:
            raise ValueError("ANOVA 需要提供 groups（多组数据列表）")
        k = len(groups)
        if k < 2:
            raise ValueError("ANOVA 至少需要两组")
        n_total = sum(len(g) for g in groups)
        grand_mean = sum(sum(g) for g in groups) / n_total
        ss_between = sum(len(g) * (sum(g) / len(g) - grand_mean) ** 2 for g in groups)
        ss_within = sum(sum((x - sum(g) / len(g)) ** 2 for x in g) for g in groups)
        df_between = k - 1
        df_within = n_total - k
        ms_between = ss_between / df_between if df_between else 0.0
        ms_within = ss_within / df_within if df_within else 0.0
        f_stat = ms_between / ms_within if ms_within > 1e-12 else float("inf")
        p_value = _f_sf(f_stat, df_between, df_within) if math.isfinite(f_stat) else 0.0

        # 组间均值
        means = [round(sum(g) / len(g), 6) for g in groups]
        return {
            "model_category": "statistics",
            "model_id": "anova",
            "model_name": self.model_name,
            "method": "ANOVA",
            "status": "success",
            "n_groups": k,
            "group_means": means,
            "f_statistic": round(float(f_stat), 6),
            "p_value": round(float(p_value), 6),
            "significant": bool(p_value < 0.05),
            "df_between": df_between,
            "df_within": df_within,
        }

    def _exp_smoothing(self, **params: Any) -> Dict[str, Any]:
        series = params.get("series")
        if series is None:
            raise ValueError("指数平滑需要提供 series（序列）")
        series = [float(v) for v in series]
        if len(series) < 3:
            raise ValueError("指数平滑至少需要 3 个观测值")
        forecast_steps = int(params.get("forecast_steps", 3))
        alpha = float(params.get("alpha", 0.3))
        beta = float(params.get("beta", 0.1))  # 趋势平滑系数

        level = series[0]
        trend = series[1] - series[0]
        fitted = [series[0]]
        for t in range(1, len(series)):
            last_level = level
            level = alpha * series[t] + (1 - alpha) * (level + trend)
            trend = beta * (level - last_level) + (1 - beta) * trend
            fitted.append(level + trend)
        forecast = [level + (h + 1) * trend for h in range(forecast_steps)]
        return {
            "model_category": "statistics",
            "model_id": "exponential_smoothing",
            "model_name": self.model_name,
            "method": "HoltLinearTrend(pure_python)",
            "library": "pure_python",
            "status": "success",
            "smoothing_level": alpha,
            "smoothing_trend": beta,
            "fitted_values": [round(float(v), 6) for v in fitted],
            "forecast": [round(float(v), 6) for v in forecast],
        }


register_category("statistics", StatisticsSolver)
