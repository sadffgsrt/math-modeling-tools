"""
预测类模型求解器（category: prediction）
真实实现（纯 Python）：灰色预测 GM(1,1)。
LSTM / Prophet 需要 tensorflow / prophet 库，诚实声明未实现。
"""
from __future__ import annotations

import csv
import math
from typing import Any, Dict, List

from ._base import BaseModelSolver, register_category, _matmul, _transpose, _matvec, _solve


class PredictionSolver(BaseModelSolver):
    """预测类求解器"""

    model_category = "prediction"

    def solve(self, **params: Any) -> Dict[str, Any]:
        if self.model_id == "grey_prediction":
            return self._grey_prediction(**params)
        if self.model_id in ("lstm", "prophet"):
            raise NotImplementedError(
                f"模型 {self.model_id} 在恢复版尚未实现"
                f"（需要 tensorflow.keras / prophet 库，当前环境未安装）"
            )
        raise NotImplementedError(f"模型 {self.model_id} 在恢复版尚未实现")

    def _grey_prediction(self, **params: Any) -> Dict[str, Any]:
        series = params.get("series")
        if series is None:
            data_path = params.get("data_path")
            if data_path:
                with open(data_path, newline="", encoding="utf-8") as f:
                    rows = [r for r in csv.reader(f) if r]
                series = [float(rows[i][0]) for i in range(1, len(rows))]
        if series is None:
            raise ValueError("灰色预测需要提供 series（序列）或 data_path（单列 CSV）")
        series = [float(v) for v in series]
        if len(series) < 4:
            raise ValueError("灰色预测 GM(1,1) 至少需要 4 个观测值")

        forecast_steps = int(params.get("forecast_steps", 3))

        # 非负平移（GM(1,1) 要求序列为正）
        offset = 0.0
        if min(series) <= 0:
            offset = -min(series) + 1.0
            series = [v + offset for v in series]

        n = len(series)
        x1 = [sum(series[:k + 1]) for k in range(n)]  # 一次累加
        B = [[-0.5 * (x1[i] + x1[i + 1]), 1.0] for i in range(n - 1)]
        Y = [series[i + 1] for i in range(n - 1)]
        BtB = _matmul(_transpose(B), B)
        BtY = _matvec(_transpose(B), Y)
        beta = _solve(BtB, BtY)
        a, b = float(beta[0]), float(beta[1])

        # 累加生成拟合值
        def x1_hat(k: int) -> float:
            return (series[0] - b / a) * math.exp(-a * k) + b / a

        # 还原为原始生成（x0 拟合）；第 0 项取原始值
        fitted = [series[0] - offset]
        for k in range(1, n):
            fitted.append(x1_hat(k) - x1_hat(k - 1) - offset)

        # 多步预测（原始序列尺度）
        forecast = []
        for s in range(1, forecast_steps + 1):
            k = n - 1 + s
            forecast.append(x1_hat(k) - x1_hat(k - 1) - offset)

        # 平均相对误差作为精度指标
        rel_err = []
        for i in range(1, n):
            base = series[i] - offset
            if base != 0:
                rel_err.append(abs((fitted[i] - base) / base))
        mape = float(sum(rel_err) / len(rel_err)) if rel_err else 0.0

        return {
            "model_category": "prediction",
            "model_id": "grey_prediction",
            "model_name": self.model_name,
            "method": "GreyPrediction",
            "model": "GM(1,1)",
            "status": "success",
            "a": round(a, 6),
            "b": round(b, 6),
            "offset": float(offset),
            "fitted_values": [round(float(v), 6) for v in fitted],
            "forecast": [round(float(v), 6) for v in forecast],
            "accuracy_level": round(mape, 6),
        }


register_category("prediction", PredictionSolver)
