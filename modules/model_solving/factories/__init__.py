# -*- coding: utf-8 -*-
"""
factories 包：汇总各分类求解器，并暴露注册表。
导入本模块会触发所有分类模块的 register_category 调用，从而填充
MODEL_CATEGORY_MAP（分类名 -> 求解器类）与 CATALOG_ALIASES（别名 -> 模型 id）。
"""
from __future__ import annotations

# 先导入 _base，获得注册表容器
from ._base import (
    MODEL_CATEGORY_MAP,
    CATALOG_ALIASES,
    BaseModelSolver,
    register_category,
)

# 导入各分类求解器（导入即注册到 MODEL_CATEGORY_MAP）
from .regression import RegressionSolver
from .optimization import OptimizationSolver
from .optimization_meta import MetaHeuristicSolver
from .prediction import PredictionSolver
from .time_series import TimeSeriesSolver
from .classification import ClassificationSolver
from .clustering import ClusteringSolver
from .dimension_reduction import DimensionReductionSolver
from .evaluation import EvaluationSolver
from .simulation import SimulationSolver
from .statistics import StatisticsSolver
from .neural_networks import NeuralNetworkSolver
from .graph_theory import GraphSolver
from .fuzzy_logic import FuzzySolver

# 显式登记各分类（双重保险，防止漏注册）
register_category("regression", RegressionSolver)
register_category("optimization", OptimizationSolver)
register_category("optimization_meta", MetaHeuristicSolver)
register_category("prediction", PredictionSolver)
register_category("time_series", TimeSeriesSolver)
register_category("classification", ClassificationSolver)
register_category("clustering", ClusteringSolver)
register_category("dimension_reduction", DimensionReductionSolver)
register_category("evaluation", EvaluationSolver)
register_category("simulation", SimulationSolver)
register_category("statistics", StatisticsSolver)
register_category("neural_networks", NeuralNetworkSolver)
register_category("graph_theory", GraphSolver)
register_category("fuzzy_logic", FuzzySolver)

# 统一导出
__all__ = [
    "MODEL_CATEGORY_MAP",
    "CATALOG_ALIASES",
    "BaseModelSolver",
    "register_category",
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
