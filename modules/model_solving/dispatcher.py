# -*- coding: utf-8 -*-
"""
调度器（dispatcher）
提供 dispatch_model(model_id, **params) 统一入口，委托 ModelFactory.solve。
"""
from __future__ import annotations

from typing import Any, Dict

from .model_factory import get_default_factory


def dispatch_model(model_id: str, **params: Any) -> Dict[str, Any]:
    """
    统一调度模型求解。
    等价于 ModelFactory().solve(model_id, **params)，但复用默认工厂实例。
    """
    return get_default_factory().solve(model_id, **params)
