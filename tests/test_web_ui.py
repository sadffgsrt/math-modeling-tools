"""
数学建模竞赛工作流 - Web UI 测试
验证 HTTP 端点 + 静态文件服务 + 认证 + 工厂函数

运行：
    python -m unittest tests.test_web_ui
"""

import sys
import json
import socket
import tempfile
import shutil
import urllib.request
import urllib.error
from pathlib import Path
from unittest import TestCase, main as unittest_main

# 添加父目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))


class TestWebUI(TestCase):
    """Web UI 测试套件"""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.project_dir = Path(self.temp_dir) / "test_web_project"

    def tearDown(self):
        import gc
        gc.collect()
        try:
            shutil.rmtree(self.temp_dir)
        except PermissionError:
            pass

    # ─── 辅助方法 ───

    def _make_server(self, port=None, api_key=None, auto_open=False):
        """创建 Web UI 服务器（端口 None 时自动分配可用端口）"""
        from main import MathModelingWorkflow
        from modules.web_ui import create_web_ui

        if port is None:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind(("127.0.0.1", 0))
                port = s.getsockname()[1]

        workflow = MathModelingWorkflow(str(self.project_dir), non_interactive=True)
        return create_web_ui(
            workflow=workflow,
            host="127.0.0.1",
            port=port,
            auto_open=auto_open,
            api_key=api_key,
        )

    def _http_get(self, server, path, headers=None):
        """发起 GET 请求"""
        url = f"http://{server.host}:{server.port}{path}"
        req = urllib.request.Request(url, headers=headers or {})
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return resp.status, data

    def _http_get_raw(self, server, path, headers=None):
        """发起 GET 请求，返回原始字节数据"""
        url = f"http://{server.host}:{server.port}{path}"
        req = urllib.request.Request(url, headers=headers or {})
        with urllib.request.urlopen(req) as resp:
            return resp.status, resp.read(), resp.headers.get("Content-Type", "")

    def _http_post(self, server, path, body, headers=None):
        """发起 POST 请求"""
        url = f"http://{server.host}:{server.port}{path}"
        req = urllib.request.Request(
            url,
            data=json.dumps(body).encode("utf-8"),
            headers={"Content-Type": "application/json", **(headers or {})},
            method="POST",
        )
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return resp.status, data

    def _http_put(self, server, path, body, headers=None):
        """发起 PUT 请求"""
        url = f"http://{server.host}:{server.port}{path}"
        req = urllib.request.Request(
            url,
            data=json.dumps(body).encode("utf-8"),
            headers={"Content-Type": "application/json", **(headers or {})},
            method="PUT",
        )
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return resp.status, data

    # ─── 测试用例 ───

    def test_server_initialization(self):
        """1. 服务器初始化"""
        server = self._make_server()
        try:
            self.assertEqual(server.host, "127.0.0.1")
            self.assertEqual(server.port, server.port)
            self.assertIsNone(server.server)
            self.assertIsNone(server.thread)
            self.assertFalse(server.is_running())
            self.assertEqual(server.VERSION, "3.4.2")
        finally:
            server.stop()

    def test_static_file_serving(self):
        """2. 静态文件服务"""
        server = self._make_server()
        server.start_background()
        try:
            # index.html
            status, body, ctype = self._http_get_raw(server, "/")
            self.assertEqual(status, 200)
            self.assertIn("text/html", ctype)
            self.assertIn(b"<html", body)
            self.assertIn(b"app.js", body)

            # style.css
            status, body, ctype = self._http_get_raw(server, "/static/style.css")
            self.assertEqual(status, 200)
            self.assertIn("text/css", ctype)
            self.assertIn(b"--color-primary", body)

            # app.js
            status, body, ctype = self._http_get_raw(server, "/static/app.js")
            self.assertEqual(status, 200)
            self.assertIn("javascript", ctype)
            self.assertIn(b"function", body)
        finally:
            server.stop()

    def test_spa_hash_and_direct_view_routes(self):
        """哈希路由和直接打开视图链接都应返回 SPA 首页。"""
        server = self._make_server()
        server.start_background()
        try:
            for path in ("/#catalog", "/%23catalog", "/catalog"):
                status, body, ctype = self._http_get_raw(server, path)
                self.assertEqual(status, 200)
                self.assertIn("text/html", ctype)
                self.assertIn(b"<html", body)
                self.assertIn(b"/static/app.js", body)
        finally:
            server.stop()

    def test_api_status(self):
        """3. GET /api/status"""
        server = self._make_server()
        server.start_background()
        try:
            status, data = self._http_get(server, "/api/status")
            self.assertEqual(status, 200)
            self.assertEqual(data["version"], "3.4.2")
            self.assertEqual(data["model_count"], 53)
            self.assertEqual(data["category_count"], 14)
            # test_count 已校准为动态统计（替代原硬编码 236），随测试规模增长
            self.assertGreaterEqual(data["test_count"], 276)
            self.assertEqual(len(data["stages"]), 7)
            self.assertIn("project_dir", data)
        finally:
            server.stop()

    def test_api_catalog(self):
        """4. GET /api/catalog"""
        server = self._make_server()
        server.start_background()
        try:
            status, data = self._http_get(server, "/api/catalog")
            self.assertEqual(status, 200)
            self.assertIn("models", data)
            # 模型目录应包含 optimization 类别
            self.assertIn("optimization", data["models"])
        finally:
            server.stop()

    def test_api_config(self):
        """5. GET /api/config"""
        server = self._make_server()
        server.start_background()
        try:
            status, data = self._http_get(server, "/api/config")
            self.assertEqual(status, 200)
            # 应包含 workflow 段
            if "_raw" not in data:
                self.assertIn("workflow", data)
        finally:
            server.stop()

    def test_api_results(self):
        """6. GET /api/results"""
        server = self._make_server()
        server.start_background()
        try:
            status, data = self._http_get(server, "/api/results")
            self.assertEqual(status, 200)
            self.assertIn("results", data)
            self.assertIsInstance(data["results"], list)
        finally:
            server.stop()

    def test_api_agent_status(self):
        """7. GET /api/agent/status"""
        server = self._make_server()
        server.start_background()
        try:
            status, data = self._http_get(server, "/api/agent/status")
            self.assertEqual(status, 200)
            self.assertIn("running", data)
            self.assertFalse(data["running"])
            self.assertIn("progress", data)
        finally:
            server.stop()

    def test_api_agent_decisions(self):
        """8. GET /api/agent/decisions"""
        server = self._make_server()
        server.start_background()
        try:
            status, data = self._http_get(server, "/api/agent/decisions")
            self.assertEqual(status, 200)
            self.assertIn("history", data)
            self.assertIsInstance(data["history"], list)
        finally:
            server.stop()

    def test_api_auth(self):
        """9. 认证功能"""
        server = self._make_server(api_key="secret-key-123")
        server.start_background()
        try:
            # 无 key 应返回 401
            with self.assertRaises(urllib.error.HTTPError) as ctx:
                self._http_get(server, "/api/status")
            self.assertEqual(ctx.exception.code, 401)

            # 错误 key 应返回 401
            with self.assertRaises(urllib.error.HTTPError) as ctx:
                self._http_get(server, "/api/status",
                               headers={"Authorization": "Bearer wrong-key"})
            self.assertEqual(ctx.exception.code, 401)

            # 正确 key（header）应通过
            status, data = self._http_get(server, "/api/status",
                                           headers={"Authorization": "Bearer secret-key-123"})
            self.assertEqual(status, 200)
            self.assertEqual(data["version"], "3.4.2")

            # 正确 key（query 参数）应通过
            status, data = self._http_get(server, "/api/status?api_key=secret-key-123")
            self.assertEqual(status, 200)

            # 静态文件不应受认证限制
            status, body, _ = self._http_get_raw(server, "/static/style.css")
            self.assertEqual(status, 200)
        finally:
            server.stop()

    def test_api_404(self):
        """10. 未知端点返回 404"""
        server = self._make_server()
        server.start_background()
        try:
            with self.assertRaises(urllib.error.HTTPError) as ctx:
                self._http_get(server, "/api/nonexistent")
            self.assertEqual(ctx.exception.code, 404)
            body = ctx.exception.read().decode("utf-8")
            data = json.loads(body)
            self.assertIn("error", data)
            self.assertIn("未知端点", data["error"])
        finally:
            server.stop()

    def test_create_web_ui(self):
        """11. 工厂函数 create_web_ui"""
        from modules.web_ui import create_web_ui, WebUIServer
        from main import MathModelingWorkflow

        workflow = MathModelingWorkflow(str(self.project_dir), non_interactive=True)
        server = create_web_ui(
            workflow=workflow,
            port=9999,
            host="0.0.0.0",
            auto_open=False,
            api_key="abc",
        )
        try:
            self.assertIsInstance(server, WebUIServer)
            self.assertEqual(server.host, "0.0.0.0")
            self.assertEqual(server.port, 9999)
            self.assertFalse(server.auto_open)
            self.assertEqual(server.api_key, "abc")
            self.assertIs(server.workflow, workflow)
        finally:
            server.stop()

    def test_server_start_stop(self):
        """12. 启动停止"""
        server = self._make_server()
        self.assertFalse(server.is_running())
        server.start_background()
        self.assertTrue(server.is_running())
        server.stop()
        self.assertFalse(server.is_running())

    # ─── 额外测试：POST 端点 ───

    def test_api_analyze_empty_text(self):
        """13. POST /api/analyze 空文本应返回错误"""
        server = self._make_server()
        server.start_background()
        try:
            status, data = self._http_post(server, "/api/analyze", {"problem_text": ""})
            self.assertEqual(status, 200)
            self.assertIn("error", data)
        finally:
            server.stop()

    def test_api_results_detail_404(self):
        """14. GET /api/results/<不存在> 返回详情（含 error）"""
        server = self._make_server()
        server.start_background()
        try:
            status, data = self._http_get(server, "/api/results/nonexistent_file.csv")
            self.assertEqual(status, 200)
            self.assertIn("error", data)
        finally:
            server.stop()

    def test_api_upload_multipart(self):
        """15. POST /api/upload multipart 上传 CSV"""
        server = self._make_server()
        server.start_background()
        try:
            # 构造 multipart 请求
            csv_content = "a,b,c\n1,2,3\n4,5,6\n"
            boundary = "----TestBoundary1234"
            body = (
                f"--{boundary}\r\n"
                f'Content-Disposition: form-data; name="file"; filename="test.csv"\r\n'
                f"Content-Type: text/csv\r\n\r\n"
                f"{csv_content}\r\n"
                f"--{boundary}--\r\n"
            ).encode("utf-8")
            url = f"http://{server.host}:{server.port}/api/upload"
            req = urllib.request.Request(
                url,
                data=body,
                headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
                method="POST",
            )
            with urllib.request.urlopen(req) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                self.assertEqual(resp.status, 200)
                self.assertTrue(data["success"])
                self.assertEqual(data["uploaded"][0]["name"], "test.csv")
                self.assertEqual(data["uploaded"][0]["size"], len(csv_content))
                self.assertIn("preview", data)
                self.assertEqual(data["preview"]["rows"], 2)
                self.assertEqual(data["preview"]["cols"], 3)
        finally:
            server.stop()

    # ─── 新增测试：可视化画廊与偏好（建议线路 P1） ───

    def _seed_figures(self, server):
        """在 workflow.project_dir 下放置 dummy 图表与画廊，供画廊路由测试。"""
        import pathlib
        base = pathlib.Path(server.workflow.project_dir)
        fig_dir = base / "figures"
        fig_dir.mkdir(parents=True, exist_ok=True)
        (fig_dir / "dummy_chart.png").write_bytes(b"\x89PNG\r\n\x1a\n dummy")
        (fig_dir / "gallery.html").write_text(
            "<!DOCTYPE html><html><body>gallery</body></html>", encoding="utf-8")

    def test_gallery_route(self):
        """16. GET /gallery 返回已生成的画廊 HTML"""
        server = self._make_server()
        self._seed_figures(server)
        server.start_background()
        try:
            status, body, ctype = self._http_get_raw(server, "/gallery")
            self.assertEqual(status, 200)
            self.assertIn("text/html", ctype)
            self.assertIn(b"<html", body)
        finally:
            server.stop()

    def test_gallery_route_missing(self):
        """17. GET /gallery 未生成时返回提示页（200 html）"""
        server = self._make_server()
        server.start_background()
        try:
            status, body, ctype = self._http_get_raw(server, "/gallery")
            self.assertEqual(status, 200)
            self.assertIn("text/html", ctype)
        finally:
            server.stop()

    def test_api_gallery(self):
        """18. GET /api/gallery 列出已生成图表"""
        server = self._make_server()
        self._seed_figures(server)
        server.start_background()
        try:
            status, data = self._http_get(server, "/api/gallery")
            self.assertEqual(status, 200)
            self.assertTrue(data["gallery_exists"])
            self.assertGreaterEqual(data["count"], 1)
            self.assertIn("dummy_chart.png", [f["name"] for f in data["figures"]])
        finally:
            server.stop()

    def test_api_visualize_prefs(self):
        """19. POST /api/visualize 保存偏好并返回确定性生成计划"""
        server = self._make_server()
        server.start_background()
        try:
            status, data = self._http_post(
                server, "/api/visualize",
                {"user_pref": "我想看预测趋势和特征重要性", "max_charts": 3})
            self.assertEqual(status, 200)
            self.assertTrue(data["success"])
            plan = data["plan"]
            self.assertIn("pred_vs_actual", plan["requested_types"])
            self.assertIn("feature_importance", plan["requested_types"])
            self.assertEqual(plan["max_charts"], 3)
            self.assertTrue(data["prefs_saved"])
            import pathlib
            import json
            prefs_path = pathlib.Path(server.workflow.results_dir) / "visualization_prefs.json"
            self.assertTrue(prefs_path.exists())
            prefs = json.loads(prefs_path.read_text(encoding="utf-8"))
            self.assertEqual(prefs["max_charts"], 3)
        finally:
            server.stop()


if __name__ == "__main__":
    unittest_main()
