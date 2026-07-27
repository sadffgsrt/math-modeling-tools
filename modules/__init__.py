"""
数学建模竞赛工作流 - 模块包 (v3.4.2 恢复版)

说明：v3.4.2 原实现层在会话中断时因未纳入版本管理而丢失，
本目录为按 v3.0 蓝本 + 测试契约重建的恢复版。
- 核心 7 阶段逻辑来自 备份/工作流/modules/01~07（忠实移植）
- llm_agent / mcp_server / web_ui / approval / core / tool_protocol 为按测试契约重建
"""

import logging

__version__ = "3.4.2"

_logger = logging.getLogger("mathmodeling")

# ── 稳定聚合门面（facade）──
# 调用方优先从 modules 顶层导入，避免深路径耦合，便于未来重组子包：
#   from modules import dispatch_model, ToolProtocolAdapter, plan_stages, ApprovalManager
# 注意：此为增量再导出，不删除旧深路径导入（向后兼容）。
from .model_solving import ModelFactory, dispatch_model
from .tool_protocol import ToolProtocolAdapter
from .stage_planner import plan as plan_stages, PLANS as STAGE_PLANS
from .approval import ApprovalManager

__all__ = [
    "__version__",
    "ModelFactory",
    "dispatch_model",
    "ToolProtocolAdapter",
    "plan_stages",
    "STAGE_PLANS",
    "ApprovalManager",
]

