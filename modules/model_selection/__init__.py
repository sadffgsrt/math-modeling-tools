# 模型选型模块包入口（Module 02）
# 仅做类与接口的再导出，逻辑见 selector.py

from .selector import (
    ModelCandidate,
    ModelSelection,
    ModelSelector,
)

__all__ = [
    "ModelCandidate",
    "ModelSelection",
    "ModelSelector",
]
