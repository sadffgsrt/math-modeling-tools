"""
神经网络类模型求解器（category: neural_networks）
真实实现：
- MLP：sklearn.neural_network 包装（分类/回归自动推断）。
- CNN：对单通道 2D 输入做简化卷积 + 池化特征提取（纯 Python，无需 TensorFlow）。
- neural_network：MLP 的别名，便于目录兼容。
"""
from __future__ import annotations

from typing import Any, Dict, List

from ._base import BaseModelSolver, _get_xy, _get_x, register_category


class NeuralNetworkSolver(BaseModelSolver):
    """神经网络类求解器"""

    model_category = "neural_networks"

    def solve(self, **params: Any) -> Dict[str, Any]:
        if self.model_id in ("mlp", "neural_network"):
            return self._mlp(**params)
        if self.model_id == "cnn":
            return self._cnn(**params)
        raise NotImplementedError(f"模型 {self.model_id} 在恢复版尚未实现")

    def _mlp(self, **params: Any) -> Dict[str, Any]:
        """多层感知机：用 sklearn MLP 训练并返回拟合指标。"""
        try:
            from sklearn.neural_network import MLPClassifier, MLPRegressor
        except ImportError as e:
            raise NotImplementedError(
                "MLP 需要 sklearn 库，当前环境未安装"
            ) from e

        X, y, features = _get_xy(params, target_column=params.get("target_column", "target"))
        hidden_layer_sizes = params.get("hidden_layer_sizes", (100,))
        if isinstance(hidden_layer_sizes, int):
            hidden_layer_sizes = (hidden_layer_sizes,)
        max_iter = int(params.get("max_iter", 200))
        random_state = int(params.get("random_state", 42))

        # 判断分类还是回归：目标列是否只有有限个整数值
        unique_y = sorted(set(y))
        is_classification = len(unique_y) <= 10 and all(float(v).is_integer() for v in unique_y)

        if is_classification:
            model = MLPClassifier(
                hidden_layer_sizes=hidden_layer_sizes,
                max_iter=max_iter,
                random_state=random_state,
            )
            y_train = [int(v) for v in y]
        else:
            model = MLPRegressor(
                hidden_layer_sizes=hidden_layer_sizes,
                max_iter=max_iter,
                random_state=random_state,
            )
            y_train = y

        model.fit(X, y_train)
        y_pred = model.predict(X)

        if is_classification:
            acc = sum(1 for a, b in zip(y_pred, y_train) if a == b) / len(y_train)
            metric = {"accuracy": round(float(acc), 6)}
        else:
            from ._base import _r2
            r2 = _r2(y_train, y_pred)
            metric = {"r2": round(float(r2), 6)}

        return {
            "model_category": "neural_networks",
            "model_id": self.model_id,
            "model_name": self.model_name,
            "method": f"sklearn.{type(model).__name__}",
            "status": "success",
            "task": "classification" if is_classification else "regression",
            "n_samples": len(X),
            "n_features": len(features),
            "features": features,
            **metric,
        }

    def _cnn(self, **params: Any) -> Dict[str, Any]:
        """
        简化 CNN 特征提取：对单通道 2D 输入做卷积 + 平均池化，无需 TensorFlow。
        适用于把图像/网格数据压缩为特征向量的场景。
        """
        image = params.get("image")
        if image is None:
            X, features = _get_x(params)
            # 若 X 是扁平向量，尝试 reshape 为方形图像
            if len(X) == 1 and len(X[0]) > 0:
                flat = X[0]
                size = int(len(flat) ** 0.5)
                if size * size == len(flat):
                    image = [[flat[i * size + j] for j in range(size)] for i in range(size)]
                else:
                    image = [[flat[j] for j in range(len(flat))]]
            else:
                image = X
        if not image or not isinstance(image[0], list):
            raise ValueError("CNN 需要提供 image（二维 0/1 或数值矩阵）或可 reshape 的 X")

        # 可选参数
        kernel = params.get("kernel", [[1, 0, -1], [1, 0, -1], [1, 0, -1]])
        pool_size = int(params.get("pool_size", 2))
        stride = int(params.get("stride", 1))
        kh, kw = len(kernel), len(kernel[0])
        H, W = len(image), len(image[0])

        def conv2d(img, k):
            out_h = H - kh + 1
            out_w = W - kw + 1
            out = []
            for i in range(out_h):
                row = []
                for j in range(out_w):
                    s = 0.0
                    for di in range(kh):
                        for dj in range(kw):
                            s += float(img[i + di][j + dj]) * k[di][dj]
                    row.append(s)
                out.append(row)
            return out

        def avg_pool2d(img, ps):
            out = []
            for i in range(0, len(img), ps):
                row = []
                for j in range(0, len(img[0]), ps):
                    block = [
                        img[x][y]
                        for x in range(i, min(i + ps, len(img)))
                        for y in range(j, min(j + ps, len(img[0])))
                    ]
                    row.append(sum(block) / len(block))
                out.append(row)
            return out

        conv_out = conv2d(image, kernel)
        pool_out = avg_pool2d(conv_out, pool_size)
        flat = [v for row in pool_out for v in row]

        return {
            "model_category": "neural_networks",
            "model_id": "cnn",
            "model_name": self.model_name,
            "method": "simple_conv_pool(pure_python)",
            "status": "success",
            "input_shape": (H, W),
            "feature_vector": [round(float(v), 6) for v in flat],
            "feature_dim": len(flat),
        }


register_category("neural_networks", NeuralNetworkSolver)
