"""
兼容性占位模块（恢复版未重建）。

原版 v3.4.2 的 ``ModelComparator`` 在沙箱回滚时丢失，恢复版（7a6470b）未重建。
本模块仅保留类签名占位，方法显式抛出 ``NotImplementedError``，对应测试
（``test_workflow.TestV33Modules.test_model_comparison``）标记为 xfail，
不伪造实现。

如后续需要真实能力，应基于 cross_val_score 对多模型做交叉验证性能对比。
"""
from __future__ import annotations

from typing import Any, Dict, Optional


class ModelComparator:
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config: Dict[str, Any] = config or {}

    def compare(self, models, X, y, task_type: str = "regression"):
        raise NotImplementedError(
            "ModelComparator 在恢复版未重建；对应测试标记为 xfail，"
            "不提供伪造实现。"
        )
