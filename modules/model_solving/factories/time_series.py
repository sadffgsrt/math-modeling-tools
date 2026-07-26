"""
时间序列类模型求解器（category: time_series）
arima：优先使用 statsmodels；若环境未安装则清晰抛出 ImportError（诚实）。
"""
from __future__ import annotations

import csv
from typing import Any, Dict

from ._base import BaseModelSolver, register_category


class TimeSeriesSolver(BaseModelSolver):
    """时间序列类求解器"""

    model_category = "time_series"

    def solve(self, **params: Any) -> Dict[str, Any]:
        if self.model_id == "arima":
            return self._arima(**params)
        raise NotImplementedError(f"模型 {self.model_id} 在恢复版尚未实现")

    def _arima(self, **params: Any) -> Dict[str, Any]:
        series = params.get("series")
        if series is None:
            data_path = params.get("data_path")
            if data_path:
                with open(data_path, newline="", encoding="utf-8") as f:
                    rows = [r for r in csv.reader(f) if r]
                series = [float(rows[i][0]) for i in range(1, len(rows))]
        if series is None:
            raise ValueError("ARIMA 需要提供 series（序列）或 data_path（单列 CSV）")
        series = [float(v) for v in series]
        forecast_steps = int(params.get("forecast_steps", 3))
        order = params.get("order", (1, 1, 1))
        if isinstance(order, list):
            order = tuple(order)

        try:
            import numpy as _np  # noqa
            from statsmodels.tsa.arima.model import ARIMA  # type: ignore
        except ImportError as e:
            raise ImportError(
                "ARIMA 求解需要 statsmodels 库，当前环境未安装；"
                "请在环境中安装 statsmodels 后重试（pip install statsmodels）"
            ) from e

        model = ARIMA(series, order=order)
        fitted = model.fit()
        forecast = fitted.forecast(steps=forecast_steps)
        fc = list(forecast) if hasattr(forecast, "__iter__") else [float(forecast)]
        return {
            "model_category": "time_series",
            "model_id": "arima",
            "model_name": self.model_name,
            "method": "statsmodels.arima",
            "status": "success",
            "order": list(order),
            "forecast": [round(float(v), 6) for v in fc],
        }


register_category("time_series", TimeSeriesSolver)
