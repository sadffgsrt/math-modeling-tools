"""
模型求解工厂包（modules.model_solving）
暴露核心 API：
  - ModelFactory        模型工厂（加载 53 模型、构建求解器、调度、生成工具 schema）
  - dispatch_model      统一调度入口
  - MODEL_CATEGORY_MAP  分类名 -> 求解器类
  - CATALOG_ALIASES     别名 -> 模型 id
  - ModelSolver         基础求解器（v3.0 移植，含指标/特征重要性/灵敏度等）
"""
from __future__ import annotations

from .model_factory import ModelFactory
from .dispatcher import dispatch_model
from .factories import MODEL_CATEGORY_MAP, CATALOG_ALIASES
from .solver import (
    ModelSolver,
    SolvingResult,
    ModelParameter,
    ModelMetrics,
    SensitivityResult,
)

__all__ = [
    "ModelFactory",
    "dispatch_model",
    "MODEL_CATEGORY_MAP",
    "CATALOG_ALIASES",
    "ModelSolver",
    "SolvingResult",
    "ModelParameter",
    "ModelMetrics",
    "SensitivityResult",
]
