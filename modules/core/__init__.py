"""
core 子包初始化：对外暴露缓存与工具协议基元。
保持向后兼容的导入路径：
    from modules.core import WorkflowCache, BaseTool, ToolResult, ToolRegistry
"""

from .cache import WorkflowCache
from .tools import BaseTool, ToolResult, ToolRegistry

__all__ = [
    "WorkflowCache",
    "BaseTool",
    "ToolResult",
    "ToolRegistry",
]
