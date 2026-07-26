"""
兼容性桥接模块（恢复版重建）。

原版 v3.4.2 在 modules 顶层提供 ``SolvingDispatcher`` 类；恢复版（7a6470b）将其
重组为 ``modules.model_solving.dispatcher.dispatch_model`` 函数。本模块提供
``SolvingDispatcher`` 类包装该入口，保留旧导入路径 ``from modules.model_solving_dispatcher
import SolvingDispatcher``。

恢复版真实实现位置：``modules.model_solving.dispatcher.dispatch_model``
"""
from __future__ import annotations

from typing import Any, Dict

from .model_solving.dispatcher import dispatch_model


class SolvingDispatcher:
    """薄包装：将原版 ``SolvingDispatcher.dispatch`` 转发到恢复版 ``dispatch_model``。

    恢复版 ``main.py`` 在 ``MathModelingWorkflow.__init__`` 中以
    ``SolvingDispatcher(self)`` 创建实例（传入 workflow 供 ToolProtocolAdapter 访问），
    因此此处保留接受 ``workflow`` 参数的构造签名。
    """

    def __init__(self, workflow=None):
        self.workflow = workflow

    # 保留旧路径下对 ``dispatch`` 属性的访问（测试据此判断导入成功）
    dispatch = staticmethod(dispatch_model)

    def dispatch_model(self, model_id: str, **params: Any) -> Dict[str, Any]:
        return dispatch_model(model_id, **params)
