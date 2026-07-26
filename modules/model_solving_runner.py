"""
模型求解运行器（顶层模块 modules.model_solving_runner）
供 main.py 等工作流调用：
  - run_model_solving(workflow, **kwargs)  执行所选模型求解并返回结果字典
  - check_model_implemented(workflow, model_id, model_name)  校验模型是否已登记

注意：本文件是 modules/ 下的顶层模块（与 model_solving 包平级），
与 main.py 中 `from modules.model_solving_runner import ...` 的引用一致。
"""
from __future__ import annotations

from typing import Any, Dict


def _get_selected_model(workflow: Any, kwargs: Dict[str, Any]) -> str:
    """从 workflow 或 kwargs 中提取所选模型 id（多来源兼容）。"""
    # 1. 直接参数
    if kwargs.get("selected_model"):
        return kwargs["selected_model"]
    if kwargs.get("model_id"):
        return kwargs["model_id"]
    # 2. workflow.state 字典
    state = getattr(workflow, "state", None)
    if isinstance(state, dict):
        if state.get("selected_model"):
            return state["selected_model"]
        if state.get("model_id"):
            return state["model_id"]
    # 3. workflow 属性
    sm = getattr(workflow, "selected_model", None)
    if sm:
        return sm
    raise ValueError("未找到所选模型（selected_model），请在 kwargs 或 workflow.state 中指定")


def _collect_params(workflow: Any, kwargs: Dict[str, Any]) -> Dict[str, Any]:
    """收集传给 ModelFactory.solve 的参数（data_path 等）。"""
    params: Dict[str, Any] = {}
    state = getattr(workflow, "state", None)
    if isinstance(state, dict):
        for key in ("data_path", "target_column", "forecast_steps", "optimization_params_path"):
            if key in state and state[key] is not None:
                params[key] = state[key]
    # kwargs 覆盖
    for key, val in kwargs.items():
        if key != "selected_model" and val is not None:
            params[key] = val
    return params


def check_model_implemented(workflow: Any, model_id: str, model_name: str) -> None:
    """
    校验模型是否已在目录中登记。未登记则抛 ValueError（真实校验，不静默忽略）。
    """
    from modules.model_solving.model_factory import ModelFactory

    factory = ModelFactory()
    available = set(factory.list_models())
    # 兼容别名
    if model_id not in available:
        from modules.model_solving.factories import CATALOG_ALIASES
        if model_id in CATALOG_ALIASES:
            model_id = CATALOG_ALIASES[model_id]
    if model_id not in factory.list_models():
        raise ValueError(
            f"所选模型未实现/未登记：id='{model_id}'（名称：{model_name}）。"
            f"当前目录共登记 {len(available)} 个模型。"
        )


def run_model_solving(workflow: Any, **kwargs: Any) -> Dict[str, Any]:
    """
    执行模型求解主流程：
      1. 取出所选模型；
      2. 收集参数；
      3. 调用 ModelFactory.solve 得到结果；
      4. 将结果写回 workflow.state（若可写）并返回。
    """
    from modules.model_solving.model_factory import ModelFactory

    selected_model = _get_selected_model(workflow, kwargs)
    params = _collect_params(workflow, kwargs)

    factory = ModelFactory()
    result = factory.solve(selected_model, **params)

    # 将结果回填到 workflow.state（若可写）
    state = getattr(workflow, "state", None)
    if isinstance(state, dict):
        state["model_solving_result"] = result
        state["solved_model"] = selected_model

    return result
