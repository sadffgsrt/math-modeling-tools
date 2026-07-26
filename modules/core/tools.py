"""
工具协议基元模块 (tools.py)
提供统一的工具抽象与注册表，供 LLM Agent / ToolProtocolAdapter 等模块复用。

组件：
- ToolResult  : 工具执行结果的统一数据结构（dataclass）
- BaseTool    : 所有工具的抽象基类，定义 name/description/category 与 get_schema/execute
- ToolRegistry: 工具注册表，负责注册、按名执行、列举与摘要
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional


@dataclass
class ToolResult:
    """工具执行结果的统一结构。

    Attributes:
        success: 是否执行成功
        data   : 执行返回的数据（默认空 dict）
        error  : 失败时的错误信息（默认空字符串）
    """

    success: bool
    data: Dict[str, Any] = field(default_factory=dict)
    error: str = ""


class BaseTool(ABC):
    """所有工具的抽象基类。

    子类必须实现：
    - name         (属性): 工具唯一名称
    - description  (属性): 工具人类可读描述
    - category     (属性): 工具分类（如 regression / time_series / test）
    - get_schema() (方法): 返回符合 OpenAI tool-calling 规范的 schema dict
    - execute()    (方法): 实际执行逻辑，返回 ToolResult

    示例子类见 tests/test_agent_e2e.py::TestToolRegistry。
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """工具唯一名称。"""

    @property
    @abstractmethod
    def description(self) -> str:
        """工具人类可读描述。"""

    @property
    @abstractmethod
    def category(self) -> str:
        """工具分类（如 regression / time_series / test）。"""

    @abstractmethod
    def get_schema(self) -> Dict[str, Any]:
        """返回工具 schema（OpenAI function calling 规范）。"""

    @abstractmethod
    def execute(self, **kwargs: Any) -> ToolResult:
        """执行工具逻辑，返回 ToolResult。"""

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} name={self.name!r} category={self.category!r}>"


class ToolRegistry:
    """工具注册表：注册工具、按名称执行、列举与摘要。"""

    def __init__(self) -> None:
        self._tools: Dict[str, BaseTool] = {}

    def register(self, tool: BaseTool) -> None:
        """注册一个工具实例（按 tool.name 索引，重名覆盖）。"""
        if not isinstance(tool, BaseTool):
            raise TypeError(f"注册对象必须是 BaseTool 子类实例，收到: {type(tool)}")
        self._tools[tool.name] = tool

    def execute(self, name: str, **kwargs: Any) -> ToolResult:
        """按名称执行工具。

        - 工具不存在：返回 success=False 的 ToolResult（不抛异常）
        - 执行过程抛异常：捕获并返回 success=False，错误信息写入 error 字段
        """
        tool = self._tools.get(name)
        if tool is None:
            return ToolResult(success=False, error=f"工具未找到: {name}")
        try:
            return tool.execute(**kwargs)
        except Exception as exc:  # noqa: BLE001 - 注册表需兜底，避免单工具失败中断整体
            return ToolResult(success=False, error=str(exc))

    def list_names(self) -> List[str]:
        """返回已注册工具名称列表（按注册顺序）。"""
        return list(self._tools.keys())

    def get(self, name: str) -> Optional[BaseTool]:
        """按名称获取工具实例（不存在返回 None）。"""
        return self._tools.get(name)

    def get_summary(self) -> Dict[str, Any]:
        """返回注册表摘要信息。"""
        return {
            "total_tools": len(self._tools),
            "names": list(self._tools.keys()),
        }
