"""
神经网络类模型求解器（category: neural_networks）
MLP / CNN / 神经网络均需要 sklearn 或 tensorflow / pytorch，诚实声明未实现。
"""
from __future__ import annotations

from typing import Any, Dict

from ._base import BaseModelSolver, register_category


class NeuralNetworkSolver(BaseModelSolver):
    """神经网络类求解器"""

    model_category = "neural_networks"

    def solve(self, **params: Any) -> Dict[str, Any]:
        raise NotImplementedError(
            f"模型 {self.model_id} 在恢复版尚未实现"
            f"（需要 sklearn.neural_network / tensorflow / pytorch，当前环境未安装）"
        )


register_category("neural_networks", NeuralNetworkSolver)
