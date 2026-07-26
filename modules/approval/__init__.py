# -*- coding: utf-8 -*-
"""
approval 子包初始化：对外暴露审批管理器。
保持向后兼容的导入路径：
    from modules.approval import ApprovalManager
"""

from .manager import ApprovalManager

__all__ = [
    "ApprovalManager",
]
