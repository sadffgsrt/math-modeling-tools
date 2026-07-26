"""
数学建模竞赛工作流 - MCP Server 测试
验证 HTTP 端点 + JSON-RPC 协议 + 审批回调
"""

import sys
import json
import tempfile
import shutil
import numpy as np
import pandas as pd
from pathlib import Path
from unittest import TestCase, main as unittest_main

# 添加父目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))


class TestMCPServer(TestCase):
    """步骤 3：MCP Server 测试
    验证 HTTP 端点 + JSON-RPC 协议 + 审批回调
    """

    def setUp(self):
        import urllib.request
        self.temp_dir = tempfile.mkdtemp()
        self.project_dir = Path(self.temp_dir) / "test_mcp_project"

    def tearDown(self):
        import gc
        gc.collect()
        try:
            shutil.rmtree(self.temp_dir)
        except PermissionError:
            pass

    def _make_server(self, port: int = 0):
        """创建 MCP Server（端口 0 自动分配可用端口）"""
        from main import MathModelingWorkflow
        from modules.mcp_server import create_mcp_server

        workflow = MathModelingWorkflow(str(self.project_dir), non_interactive=False)
        # 端口 0 让 OS 自动分配
        server = create_mcp_server(workflow, host="127.0.0.1", port=port)
        return server

    def _http_get(self, server, path: str):
        """发起 HTTP GET 请求"""
        import urllib.request
        url = f"http://{server.host}:{server.port}{path}"
        with urllib.request.urlopen(url) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return resp.status, data

    def _http_post(self, server, path: str, body: dict):
        """发起 HTTP POST 请求"""
        import urllib.request
        url = f"http://{server.host}:{server.port}{path}"
        req = urllib.request.Request(
            url,
            data=json.dumps(body).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return resp.status, data

    # ─── 服务器生命周期测试 ───

    def test_server_start_stop(self):
        """服务器启动和停止"""
        server = self._make_server(port=0)
        # 自动分配端口
        import socket
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(("127.0.0.1", 0))
            port = s.getsockname()[1]
        server.port = port

        server.start_background()
        self.assertTrue(server.is_running())
        server.stop()
        self.assertFalse(server.is_running())

    # ─── HTTP 端点测试 ───

    def test_health_endpoint(self):
        """GET /health 健康检查"""
        import socket
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(("127.0.0.1", 0))
            port = s.getsockname()[1]
        server = self._make_server(port=port)
        server.start_background()
        try:
            status, data = self._http_get(server, "/health")
            self.assertEqual(status, 200)
            self.assertEqual(data["status"], "ok")
        finally:
            server.stop()

    def test_list_tools_endpoint(self):
        """GET /tools 列出所有工具"""
        import socket
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(("127.0.0.1", 0))
            port = s.getsockname()[1]
        server = self._make_server(port=port)
        server.start_background()
        try:
            status, data = self._http_get(server, "/tools")
            self.assertEqual(status, 200)
            self.assertEqual(len(data["tools"]), 53)
            self.assertIn("solve_arima", data["tools"])
        finally:
            server.stop()

    def test_get_tool_schema_endpoint(self):
        """GET /tools/<name> 获取工具 schema"""
        import socket
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(("127.0.0.1", 0))
            port = s.getsockname()[1]
        server = self._make_server(port=port)
        server.start_background()
        try:
            status, data = self._http_get(server, "/tools/solve_arima")
            self.assertEqual(status, 200)
            self.assertEqual(data["function"]["name"], "solve_arima")
        finally:
            server.stop()

    def test_get_nonexistent_tool_404(self):
        """GET /tools/<不存在> 返回 404"""
        import socket
        import urllib.error
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(("127.0.0.1", 0))
            port = s.getsockname()[1]
        server = self._make_server(port=port)
        server.start_background()
        try:
            with self.assertRaises(urllib.error.HTTPError) as ctx:
                self._http_get(server, "/tools/solve_nonexistent")
            self.assertEqual(ctx.exception.code, 404)
        finally:
            server.stop()

    def test_status_endpoint(self):
        """GET /status 工作流状态"""
        import socket
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(("127.0.0.1", 0))
            port = s.getsockname()[1]
        server = self._make_server(port=port)
        server.start_background()
        try:
            status, data = self._http_get(server, "/status")
            self.assertEqual(status, 200)
            self.assertIn("project_dir", data)
            self.assertIn("current_stage", data)
        finally:
            server.stop()

    def test_summary_endpoint(self):
        """GET /summary 工具协议摘要"""
        import socket
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(("127.0.0.1", 0))
            port = s.getsockname()[1]
        server = self._make_server(port=port)
        server.start_background()
        try:
            status, data = self._http_get(server, "/summary")
            self.assertEqual(status, 200)
            self.assertEqual(data["total_tools"], 53)
        finally:
            server.stop()

    # ─── MCP JSON-RPC 协议测试 ───

    def test_mcp_tools_list(self):
        """POST /mcp method=tools/list"""
        import socket
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(("127.0.0.1", 0))
            port = s.getsockname()[1]
        server = self._make_server(port=port)
        server.start_background()
        try:
            req = {"jsonrpc": "2.0", "id": 1, "method": "tools/list"}
            status, data = self._http_post(server, "/mcp", req)
            self.assertEqual(status, 200)
            self.assertEqual(data["jsonrpc"], "2.0")
            self.assertEqual(data["id"], 1)
            self.assertIn("result", data)
            self.assertIn("tools", data["result"])
            self.assertEqual(len(data["result"]["tools"]), 53)
        finally:
            server.stop()

    def test_mcp_status_method(self):
        """POST /mcp method=status"""
        import socket
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(("127.0.0.1", 0))
            port = s.getsockname()[1]
        server = self._make_server(port=port)
        server.start_background()
        try:
            req = {"jsonrpc": "2.0", "id": 2, "method": "status"}
            status, data = self._http_post(server, "/mcp", req)
            self.assertEqual(status, 200)
            self.assertIn("project_dir", data["result"])
        finally:
            server.stop()

    def test_mcp_unknown_method_error(self):
        """POST /mcp 未知方法返回 JSON-RPC 错误"""
        import socket
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(("127.0.0.1", 0))
            port = s.getsockname()[1]
        server = self._make_server(port=port)
        server.start_background()
        try:
            req = {"jsonrpc": "2.0", "id": 3, "method": "unknown_method"}
            status, data = self._http_post(server, "/mcp", req)
            self.assertEqual(status, 200)
            self.assertIn("error", data)
            self.assertEqual(data["error"]["code"], -32601)
        finally:
            server.stop()

    # ─── 审批 API 测试 ───

    def test_approval_callback_injected(self):
        """MCP Server 初始化后注入了审批回调"""
        server = self._make_server(port=0)
        # 验证回调已注入
        self.assertIsNotNone(server.workflow.approval_manager._approval_callback)

    def test_submit_approval_nonexistent(self):
        """POST /approve 对不存在的 operation_id 返回错误"""
        import socket
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(("127.0.0.1", 0))
            port = s.getsockname()[1]
        server = self._make_server(port=port)
        server.start_background()
        try:
            status, data = self._http_post(server, "/approve",
                                            {"operation_id": "nonexistent", "approved": True})
            self.assertEqual(status, 200)
            self.assertIn("error", data)
        finally:
            server.stop()

    # ─── 工具调用端到端测试 ───

    def test_call_tool_via_http(self):
        """POST /tools/<name>/call 端到端调用"""
        import socket
        import pandas as pd

        # 准备测试数据
        np.random.seed(42)
        data = pd.DataFrame({
            'feature_1': np.random.randn(50),
            'feature_2': np.random.uniform(0, 10, 50),
            'target': 2 * np.random.randn(50) + 1,
        })
        data_path = Path(self.temp_dir) / "test_data.csv"
        data.to_csv(data_path, index=False)

        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(("127.0.0.1", 0))
            port = s.getsockname()[1]
        server = self._make_server(port=port)
        server.start_background()
        try:
            status, data = self._http_post(server, "/tools/solve_regression/call",
                                            {"data_path": str(data_path)})
            self.assertEqual(status, 200)
            self.assertIn("model_name", data)
            self.assertEqual(data["model_category"], "regression")
        finally:
            server.stop()


if __name__ == "__main__":
    unittest_main()
