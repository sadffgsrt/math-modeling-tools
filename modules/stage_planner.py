"""
阶段编排单一真相（StagePlanner）。

替代此前分散在两处的阶段选择逻辑：
  - ``MathModelingWorkflow.EXECUTION_PATHS``（CLI 七阶段主线）
  - ``LLMAgent._decide_stages_by_rule``（Agent 自主路径）

二者曾因 visualization / validation 的**顺序不一致**而漂移（CLI 为
``...model_solving → visualization → validation → paper_writing``，Agent 为
``...model_solving → validation → visualization → paper_writing``）。

本模块为唯一权威来源：所有入口（CLI / Agent / WebUI）统一调用
``StagePlanner.plan(problem_type)``，消除双源定义与顺序漂移。
"""
from __future__ import annotations

from typing import Dict, List

# 规范阶段序列（visualization 统一置于 validation 之前）。
# 优化类不含可视化；其余题型含可视化。
_PLANS: Dict[str, List[str]] = {
    "optimization": ["data_processing", "model_solving", "validation", "paper_writing"],
    "prediction": ["data_processing", "model_solving", "visualization", "validation", "paper_writing"],
    "classification": ["data_processing", "model_solving", "visualization", "validation", "paper_writing"],
    "simulation": ["data_processing", "model_solving", "visualization", "validation", "paper_writing"],
    "comprehensive": ["data_processing", "model_solving", "visualization", "validation", "paper_writing"],
}

_DEFAULT_TYPE = "comprehensive"


def plan(problem_type: str) -> List[str]:
    """返回指定题型的规范阶段序列（返回副本，调用方可安全修改）。

    未知题型回退到 ``comprehensive`` 默认路径。
    """
    key = problem_type if problem_type in _PLANS else _DEFAULT_TYPE
    return list(_PLANS[key])


def has_visualization(problem_type: str) -> bool:
    """该题型是否包含可视化阶段（供 Agent / WebUI 等决策使用）。"""
    return "visualization" in plan(problem_type)


# 对外暴露的不可变视图（供 main.EXECUTION_PATHS 等引用，避免再次硬编码）
PLANS: Dict[str, List[str]] = {k: list(v) for k, v in _PLANS.items()}
