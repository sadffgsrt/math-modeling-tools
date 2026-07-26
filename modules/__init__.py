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
