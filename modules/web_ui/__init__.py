"""
数学建模竞赛工作流 - Web UI 模块包（恢复版重建）

依据 tests/test_web_ui.py 契约导出：
    - create_web_ui : 工厂函数，返回 WebUIServer 实例
    - WebUIServer   : 服务器类
    - VERSION       : 版本常量 "3.4.2"
"""

from .server import VERSION, WebUIServer, create_web_ui

__all__ = ["create_web_ui", "WebUIServer", "VERSION"]
