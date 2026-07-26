# -*- coding: utf-8 -*-
"""
兼容性占位模块（恢复版未重建）。

原版 v3.4.2 的 ``LogAggregator`` 在沙箱回滚时丢失，恢复版（7a6470b）未重建。
本模块仅保留类签名占位，方法显式抛出 ``NotImplementedError``，对应测试
（``test_workflow.TestV33Modules.test_log_aggregation``）标记为 xfail，
不伪造实现。

如后续需要真实能力，应解析日志文本，统计级别计数、阶段耗时与状态。
"""
from __future__ import annotations

from typing import Any, Dict, Optional

from pathlib import Path


class LogAggregator:
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config: Dict[str, Any] = config or {}

    def aggregate(self, log_path: Path):
        raise NotImplementedError(
            "LogAggregator 在恢复版未重建；对应测试标记为 xfail，"
            "不提供伪造实现。"
        )
