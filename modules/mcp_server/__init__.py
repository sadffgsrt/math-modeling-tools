# -*- coding: utf-8 -*-
"""
MCP Server 模块（恢复版重建 · v3.4.2）
将工作流暴露为 MCP（Model Context Protocol）兼容服务，
支持 IDE（如 TRAE）和外部系统通过统一协议调用。

设计原则（恢复版重建）：
- 不依赖 fastapi / mcp / uvicorn 等第三方库，使用 Python 标准库 http.server。
- 提供 HTTP REST 端点 + MCP(JSON-RPC 2.0) 协议端点。
- 复用 ToolProtocolAdapter（步骤 2，恢复版重建）生成 schema 与执行调用。
- 依赖 ApprovalManager（由其它子代理恢复）注入异步审批回调；不修改 main.py。
- 53 个工具数量来自 ToolProtocolAdapter（其内部以 config/model_catalog.json 为事实来源，
  与 model_solving.ModelFactory 一致）。
"""

from .server import MCPServer, create_mcp_server

__all__ = ["MCPServer", "create_mcp_server"]
