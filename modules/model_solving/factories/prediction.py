"""
预测类模型求解器（category: prediction）
真实实现：灰色预测 GM(1,1)（纯 Python）、
LSTM（简化 RNN 近似，纯 Python）、Prophet（线性趋势 + 季节性近似，纯 Python）。
"""
from __future__ import annotations

import csv
import math
import random
from typing import Any, Dict, List

from ._base import BaseModelSolver, register_category, _matmul, _transpose, _matvec, _solve


class PredictionSolver(BaseModelSolver):
    """预测类求解器"""

    model_category = "prediction"

    def solve(self, **params: Any) -> Dict[str, Any]:
        if self.model_id == "grey_prediction":
            return self._grey_prediction(**params)
        if self.model_id == "lstm":
            return self._lstm(**params)
        if self.model_id == "prophet":
            return self._prophet(**params)
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

    def _load_series(self, params: Dict[str, Any]) -> List[float]:
        series = params.get("series")
        if series is None:
            data_path = params.get("data_path")
            if data_path:
                with open(data_path, newline="", encoding="utf-8") as f:
                    rows = [r for r in csv.reader(f) if r]
                series = [float(rows[i][0]) for i in range(1, len(rows))]
        if series is None:
            raise ValueError(f"{self.model_id} 需要提供 series（序列）或 data_path（单列 CSV）")
        return [float(v) for v in series]

    def _lstm(self, **params: Any) -> Dict[str, Any]:
        """
        LSTM 的简化实现：用单隐层 RNN 学习序列，纯 Python，无需 TensorFlow。
        对短期序列预测足够可用；长序列/复杂模式建议迁移到真实 keras LSTM。
        """
        series = self._load_series(params)
        if len(series) < 5:
            raise ValueError("LSTM 简化模型至少需要 5 个观测值")
        random.seed(int(params.get("random_state", 42)))

        window = int(params.get("window", 3))
        forecast_steps = int(params.get("forecast_steps", 3))
        hidden_size = int(params.get("hidden_size", 4))
        epochs = int(params.get("epochs", 200))
        lr = float(params.get("learning_rate", 0.05))

        # 构造监督样本
        X, y = [], []
        for i in range(len(series) - window):
            X.append(series[i:i + window])
            y.append(series[i + window])
        n = len(X)
        if n < 1:
            raise ValueError(f"序列过短，无法构造 window={window} 的训练样本")

        # 初始化权重
        Wxh = [[random.uniform(-0.5, 0.5) for _ in range(window)] for _ in range(hidden_size)]
        Whh = [[random.uniform(-0.5, 0.5) for _ in range(hidden_size)] for _ in range(hidden_size)]
        Why = [random.uniform(-0.5, 0.5) for _ in range(hidden_size)]
        bh = [0.0] * hidden_size
        by = 0.0

        def rnn_step(x, h):
            new_h = []
            for i in range(hidden_size):
                s = bh[i]
                for j in range(window):
                    s += Wxh[i][j] * x[j]
                for j in range(hidden_size):
                    s += Whh[i][j] * h[j]
                new_h.append(math.tanh(s))
            out = by + sum(Why[i] * new_h[i] for i in range(hidden_size))
            return new_h, out

        # 训练
        for _ in range(epochs):
            h = [0.0] * hidden_size
            total_loss = 0.0
            for i in range(n):
                h, out = rnn_step(X[i], h)
                err = out - y[i]
                total_loss += err * err
                # 简化的 BPTT：只更新输出层权重与偏置
                for j in range(hidden_size):
                    Why[j] -= lr * err * h[j] / n
                by -= lr * err / n

        # 拟合值
        fitted = []
        h = [0.0] * hidden_size
        for i in range(n):
            h, out = rnn_step(X[i], h)
            fitted.append(out)

        # 多步预测：用最后 window 个值滚动
        last_window = list(series[-window:])
        forecast = []
        h = [0.0] * hidden_size
        for _ in range(forecast_steps):
            h, out = rnn_step(last_window, h)
            forecast.append(out)
            last_window.pop(0)
            last_window.append(out)

        mse = sum((fitted[i] - y[i]) ** 2 for i in range(n)) / n if n else 0.0
        return {
            "model_category": "prediction",
            "model_id": "lstm",
            "model_name": self.model_name,
            "method": "simple_rnn_approximation(pure_python)",
            "status": "success",
            "window": window,
            "forecast": [round(float(v), 6) for v in forecast],
            "fitted_values": [round(float(v), 6) for v in fitted],
            "mse": round(mse, 6),
        }

    def _prophet(self, **params: Any) -> Dict[str, Any]:
        """
        Prophet 的简化实现：线性趋势 + 可选 Fourier 年周期性，纯 Python。
        输入序列若为时间序列（按时间顺序），将索引视为时间步。
        """
        series = self._load_series(params)
        if len(series) < 5:
            raise ValueError("Prophet 简化模型至少需要 5 个观测值")
        forecast_steps = int(params.get("forecast_steps", 3))
        period = int(params.get("period", 0))  # 0 表示不拟合季节性

        n = len(series)
        # 线性趋势
        t = list(range(n))
        mean_t = sum(t) / n
        mean_y = sum(series) / n
        num = sum((t[i] - mean_t) * (series[i] - mean_y) for i in range(n))
        den = sum((t[i] - mean_t) ** 2 for i in range(n))
        slope = num / den if den > 1e-12 else 0.0
        intercept = mean_y - slope * mean_t

        trend = [intercept + slope * ti for ti in t]
        seasonal = [0.0] * n
        if period > 0 and n >= 2 * period:
            # 简单季节分量：每个周期位置取平均残差
            residuals = [series[i] - trend[i] for i in range(n)]
            seasonal_means = {}
            counts = {}
            for i in range(n):
                pos = i % period
                seasonal_means[pos] = seasonal_means.get(pos, 0.0) + residuals[i]
                counts[pos] = counts.get(pos, 0) + 1
            for i in range(n):
                pos = i % period
                seasonal[i] = seasonal_means[pos] / counts[pos] if counts[pos] else 0.0

        fitted = [trend[i] + seasonal[i] for i in range(n)]
        mape = sum(abs((fitted[i] - series[i]) / series[i]) for i in range(n) if series[i] != 0) / n

        forecast = []
        for s in range(1, forecast_steps + 1):
            t_future = n - 1 + s
            val = intercept + slope * t_future
            if period > 0:
                val += seasonal[t_future % period] if t_future % period < len(seasonal) else 0.0
            forecast.append(val)

        return {
            "model_category": "prediction",
            "model_id": "prophet",
            "model_name": self.model_name,
            "method": "linear_trend_plus_seasonality(pure_python)",
            "status": "success",
            "forecast": [round(float(v), 6) for v in forecast],
            "fitted_values": [round(float(v), 6) for v in fitted],
            "trend_slope": round(slope, 6),
            "trend_intercept": round(intercept, 6),
            "mape": round(mape, 6),
        }


register_category("prediction", PredictionSolver)
