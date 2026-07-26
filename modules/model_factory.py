"""
兼容性桥接模块（恢复版重建）。

原版 v3.4.2 在 modules 顶层直接暴露 ``ModelFactory`` 与各 ``*Solver`` 类；
恢复版（7a6470b）将其重组到 ``modules.model_solving`` 子包。本模块仅做重导出，
使依赖旧导入路径（``from modules.model_factory import ...``）的测试与代码仍可运行，
不重复实现逻辑。

恢复版真实实现位置：
  - ``modules.model_solving.model_factory.ModelFactory``
  - ``modules.model_solving.factories.*`` 各分类求解器
"""
from __future__ import annotations

from .model_solving.model_factory import ModelFactory
from .model_solving.factories import (
    MODEL_CATEGORY_MAP,
    CATALOG_ALIASES,
    BaseModelSolver,
    RegressionSolver,
    OptimizationSolver,
    MetaHeuristicSolver,
    PredictionSolver,
    TimeSeriesSolver,
    ClassificationSolver,
    ClusteringSolver,
    DimensionReductionSolver,
    EvaluationSolver,
    SimulationSolver,
    StatisticsSolver,
    NeuralNetworkSolver,
    GraphSolver,
    FuzzySolver,
)

__all__ = [
    "ModelFactory",
    "MODEL_CATEGORY_MAP",
    "CATALOG_ALIASES",
    "BaseModelSolver",
    "RegressionSolver",
    "OptimizationSolver",
    "MetaHeuristicSolver",
    "PredictionSolver",
    "TimeSeriesSolver",
    "ClassificationSolver",
    "ClusteringSolver",
    "DimensionReductionSolver",
    "EvaluationSolver",
    "SimulationSolver",
    "StatisticsSolver",
    "NeuralNetworkSolver",
    "GraphSolver",
    "FuzzySolver",
]
