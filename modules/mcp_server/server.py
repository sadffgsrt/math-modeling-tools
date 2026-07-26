"""
MCP Server 实现（恢复版重建 · v3.4.2）
基于 Python stdlib http.server，无需第三方依赖。

端点（REST）：
  GET  /health              健康检查（返回 {"status":"ok","version":"3.4.2"}）
  GET  /tools               列出所有可用工具（含 version 字段）
  GET  /tools/<name>        获取单个工具 schema
  POST /tools/<name>/call   执行工具调用（真实求解，返回含 model_category 的结果）
  POST /approve             提交审批决策（配合异步审批回调）
  GET  /status              工作流状态
  GET  /summary             工具协议摘要

MCP 协议端点（JSON-RPC 2.0）：
  POST /mcp                 支持 methods: tools/list, tools/call, status, summary,
                            approval/respond（未知 method 返回 -32601）
"""

import json
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from typing import Dict, Optional
from urllib.parse import urlparse, parse_qs


# 本服务版本号（单一来源，恢复版重建统一为 v3.4.2）
SERVER_VERSION = "3.4.2"


class MCPRequestHandler(BaseHTTPRequestHandler):
    """HTTP 请求处理器：路由到 MCPServer 的方法（恢复版重建）。"""

    # 抑制默认日志输出（由 workflow logger 统一记录）
    def log_message(self, format, *args):
        pass

    def _check_auth(self, parsed) -> bool:
        """
        认证检查：当 api_key 已配置时，验证请求是否携带正确的 key。
        /health 端点和 OPTIONS 请求由调用方提前豁免。

        支持两种方式传递 key：
        1. 请求头 Authorization: Bearer <key>
        2. 查询参数 ?api_key=<key>

        Returns:
            bool: True 表示通过（或未启用认证），False 表示未通过
        """
        server = self.server.mcp_server  # type: ignore[attr-defined]
        api_key = server.api_key
        if api_key is None:
            return True

        # 1. 请求头 Authorization: Bearer <key>
        auth_header = self.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header[len("Bearer "):].strip()
            if token == api_key:
                return True

        # 2. 查询参数 ?api_key=<key>
        query = parse_qs(parsed.query)
        api_key_vals = query.get("api_key", [])
        if api_key_vals and api_key_vals[0] == api_key:
            return True

        return False

    def do_GET(self):
        """处理 GET 请求"""
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/") or "/"
        server = self.server.mcp_server  # type: ignore[attr-defined]

        # 认证检查：/health 端点豁免
        if path != "/health" and not self._check_auth(parsed):
            self._send_json(401, {"error": "Unauthorized"})
            return

        try:
            if path == "/health":
                response = {"status": "ok", "version": SERVER_VERSION}
            elif path == "/tools":
                response = {"tools": server.list_tools(), "version": SERVER_VERSION}
            elif path.startswith("/tools/"):
                tool_name = path[len("/tools/"):]
                schema = server.get_tool_schema(tool_name)
                response = schema
            elif path == "/status":
                response = server.get_workflow_status()
            elif path == "/summary":
                response = server.get_summary()
            else:
                self._send_json(404, {"error": f"路径不存在: {path}"})
                return
            self._send_json(200, response)
        except KeyError as e:
            self._send_json(404, {"error": str(e)})
        except (ValueError, TypeError, RuntimeError, OSError, KeyError) as e:
            server.logger.error(f"GET {path} 失败: {type(e).__name__}: {e}")
            self._send_json(500, {"error": f"内部错误: {type(e).__name__}: {e}"})

    def do_POST(self):
        """处理 POST 请求"""
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/") or "/"
        server = self.server.mcp_server  # type: ignore[attr-defined]

        # 认证检查
        if not self._check_auth(parsed):
            self._send_json(401, {"error": "Unauthorized"})
            return

        # 读取请求体
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length) if content_length > 0 else b"{}"

        try:
            arguments = json.loads(body.decode("utf-8")) if body else {}
        except json.JSONDecodeError as e:
            self._send_json(400, {"error": f"JSON 解析失败: {e}"})
            return

        try:
            if path.startswith("/tools/") and path.endswith("/call"):
                # POST /tools/<name>/call —— 真实调用求解
                tool_name = path[len("/tools/"):-len("/call")]
                result = server.call_tool(tool_name, arguments)
                self._send_json(200, result)
            elif path == "/approve":
                # POST /approve
                operation_id = arguments.get("operation_id")
                approved = arguments.get("approved", False)
                result = server.submit_approval(operation_id, approved)
                self._send_json(200, result)
            elif path == "/mcp":
                # MCP JSON-RPC 端点
                result = server.handle_mcp_request(arguments)
                self._send_json(200, result)
            else:
                self._send_json(404, {"error": f"路径不存在: {path}"})
        except KeyError as e:
            self._send_json(404, {"error": str(e)})
        except ValueError as e:
            self._send_json(400, {"error": str(e)})
        except FileNotFoundError as e:
            self._send_json(404, {"error": str(e)})
        except (ValueError, TypeError, RuntimeError, OSError, KeyError) as e:
            server.logger.error(f"POST {path} 失败: {type(e).__name__}: {e}")
            self._send_json(500, {"error": f"内部错误: {type(e).__name__}: {e}"})

    def _send_json(self, status: int, data: Dict):
        """发送 JSON 响应"""
        body = json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        """处理 CORS 预检请求"""
        self._send_json(200, {"status": "ok"})


class MCPServer:
    """
    MCP Server：将工作流暴露为 HTTP/MCP 服务（恢复版重建）。

    Args:
        workflow: MathModelingWorkflow 实例
        host: 监听地址
        port: 监听端口
        api_key: 可选 API Key 用于认证。None 时禁用认证（向后兼容）；
                 设置后所有请求需携带 Authorization: Bearer <key> 或 ?api_key=<key>
                 （/health 和 OPTIONS 请求豁免）。
    """

    def __init__(self, workflow, host: str = "127.0.0.1", port: int = 8080,
                 api_key: Optional[str] = None):
        self.workflow = workflow
        self.host = host
        self.port = port
        self.api_key = api_key
        self.logger = workflow.logger
        # 复用 ToolProtocolAdapter（恢复版重建实现）
        from modules.tool_protocol import ToolProtocolAdapter
        self.adapter = ToolProtocolAdapter(wf=workflow)
        # HTTP server 实例（延迟创建）
        self._http_server: Optional[HTTPServer] = None
        self._thread: Optional[threading.Thread] = None
        # 审批回调队列：operation_id -> threading.Event + 结果
        self._approval_events: Dict[str, threading.Event] = {}
        self._approval_results: Dict[str, bool] = {}
        # 初始化时注入异步审批回调
        self._setup_approval_callback()
        if api_key is not None:
            self.logger.info("MCP Server 已启用 API Key 认证")

    def _setup_approval_callback(self):
        """
        注入同步审批回调：当工作流请求审批时，
        通过 HTTP /approve 端点等待外部决策。
        """
        def approval_callback(operation: Dict) -> bool:
            operation_id = operation.get("operation_id", "")
            if not operation_id:
                self.logger.warning("审批请求缺少 operation_id，自动拒绝")
                return False

            # 创建事件并等待外部响应
            event = threading.Event()
            self._approval_events[operation_id] = event

            self.logger.info(f"审批请求已挂起: {operation_id}，等待 POST /approve 响应...")

            # 等待外部提交审批（超时 5 分钟）
            if event.wait(timeout=300):
                result = self._approval_results.pop(operation_id, False)
                self._approval_events.pop(operation_id, None)
                self.logger.info(f"审批 {operation_id} 结果: {'批准' if result else '拒绝'}")
                return result
            else:
                # 超时
                self._approval_events.pop(operation_id, None)
                self._approval_results.pop(operation_id, None)
                self.logger.warning(f"审批 {operation_id} 超时，自动拒绝")
                return False

        self.workflow.approval_manager.set_approval_callback(approval_callback)

    # ─── 工具协议 API ───

    def list_tools(self) -> list:
        """列出所有可用工具名（恢复版重建：来自 ToolProtocolAdapter，共 53 项）"""
        return self.adapter.list_available_tools()

    def get_tool_schema(self, tool_name: str) -> Dict:
        """获取单个工具的 schema"""
        return self.adapter.get_tool_schema(tool_name)

    def call_tool(self, tool_name: str, arguments: Dict) -> Dict:
        """执行工具调用（真实求解，返回含 model_category 的结果）"""
        return self.adapter.dispatch_tool_call(tool_name, arguments)

    def get_summary(self) -> Dict:
        """获取工具协议摘要"""
        return self.adapter.get_summary()

    def get_workflow_status(self) -> Dict:
        """获取工作流状态"""
        return self.workflow.get_status()

    # ─── 审批 API ───

    def submit_approval(self, operation_id: Optional[str], approved: bool) -> Dict:
        """
        提交审批决策（由外部系统通过 POST /approve 调用）。

        Args:
            operation_id: 操作 ID
            approved: 是否批准

        Returns:
            Dict: 提交结果
        """
        if not operation_id:
            return {"error": "缺少 operation_id"}
        if operation_id not in self._approval_events:
            return {"error": f"操作 {operation_id} 不在等待审批队列中",
                    "pending": list(self._approval_events.keys())}

        self._approval_results[operation_id] = approved
        self._approval_events[operation_id].set()
        return {"status": "submitted", "operation_id": operation_id, "approved": approved}

    # ─── MCP JSON-RPC 协议 ───

    def handle_mcp_request(self, request: Dict) -> Dict:
        """
        处理 MCP JSON-RPC 2.0 请求。

        支持的 methods:
        - tools/list: 列出所有工具（53 项 schema）
        - tools/call: 执行工具调用
        - approval/respond: 提交审批决策
        - status: 获取工作流状态
        - summary: 获取工具协议摘要

        Args:
            request: JSON-RPC 请求 dict

        Returns:
            Dict: JSON-RPC 响应
        """
        method = request.get("method", "")
        params = request.get("params", {})
        req_id = request.get("id")

        try:
            if method == "tools/list":
                result = {"tools": self.adapter.generate_tool_schemas()}
            elif method == "tools/call":
                tool_name = params.get("name", "")
                arguments = params.get("arguments", {})
                result = self.call_tool(tool_name, arguments)
            elif method == "approval/respond":
                operation_id = params.get("operation_id")
                approved = params.get("approved", False)
                result = self.submit_approval(operation_id, approved)
            elif method == "status":
                result = self.get_workflow_status()
            elif method == "summary":
                result = self.get_summary()
            else:
                return {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "error": {"code": -32601, "message": f"方法不存在: {method}"}
                }
            return {"jsonrpc": "2.0", "id": req_id, "result": result}
        except (ValueError, TypeError, RuntimeError, OSError, KeyError) as e:
            self.logger.error(f"MCP 请求处理失败: {type(e).__name__}: {e}")
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {"code": -32000, "message": f"{type(e).__name__}: {e}"}
            }

    # ─── 服务器生命周期 ───

    def start(self) -> None:
        """启动 HTTP 服务器（阻塞）"""
        self._http_server = HTTPServer((self.host, self.port), MCPRequestHandler)
        self._http_server.mcp_server = self  # type: ignore[attr-defined]
        self.logger.info(f"MCP Server 启动: http://{self.host}:{self.port}")
        self.logger.info("端点: /health /tools /tools/<name> /tools/<name>/call /approve /mcp /status")
        try:
            self._http_server.serve_forever()
        except KeyboardInterrupt:
            self.logger.info("收到中断信号，停止服务器")
            self.stop()

    def start_background(self) -> None:
        """在后台线程启动 HTTP 服务器（非阻塞）"""
        self._http_server = HTTPServer((self.host, self.port), MCPRequestHandler)
        self._http_server.mcp_server = self  # type: ignore[attr-defined]
        self._thread = threading.Thread(target=self._http_server.serve_forever, daemon=True)
        self._thread.start()
        self.logger.info(f"MCP Server 后台启动: http://{self.host}:{self.port}")

    def stop(self) -> None:
        """停止 HTTP 服务器"""
        if self._http_server:
            self._http_server.shutdown()
            self._http_server.server_close()
            self._http_server = None
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2)
            self._thread = None
        self.logger.info("MCP Server 已停止")

    def is_running(self) -> bool:
        """检查服务器是否正在运行"""
        return self._http_server is not None and self._thread is not None and self._thread.is_alive()


def create_mcp_server(workflow, host: str = "127.0.0.1", port: int = 8080,
                      api_key: Optional[str] = None) -> MCPServer:
    """
    创建 MCP Server 实例（恢复版重建）。

    Args:
        workflow: MathModelingWorkflow 实例
        host: 监听地址
        port: 监听端口
        api_key: 可选 API Key。None 时禁用认证；设置后请求需携带
                 Authorization: Bearer <key> 或 ?api_key=<key>
                 （/health 和 OPTIONS 豁免）。

    Returns:
        MCPServer 实例
    """
    return MCPServer(workflow, host=host, port=port, api_key=api_key)
