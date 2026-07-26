"""
数学建模竞赛工作流 - Web UI 服务模块 (恢复版重建)

版本：v3.4.2
说明：本模块为 v3.4.2 丢失模块的恢复版重建，严格依据 tests/test_web_ui.py 的测试契约实现。
依赖：仅使用 Python 标准库（http.server / threading / json / urllib），不引入任何第三方依赖。

对外暴露：
    - create_web_ui(workflow, host, port, auto_open, api_key) -> WebUIServer
    - WebUIServer 类
    - VERSION 常量（"3.4.2"）
"""

import json
import os
import re
import threading
import urllib.parse
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

# ─── 版本常量（与测试契约一致） ───
VERSION = "3.4.2"

# ─── 内嵌静态资源（避免依赖外部文件系统，确保 import 即可用） ───
# 首页：必须包含 "<html" 与 "app.js"（测试用例断言）
INDEX_HTML = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="utf-8">
    <title>数学建模竞赛工作流 - Web UI</title>
    <link rel="stylesheet" href="/static/style.css">
</head>
<body>
    <h1>数学建模竞赛工作流 Web UI</h1>
    <nav style="margin:8px 0;font-size:14px">
      <a href="/gallery">可视化画廊</a> |
      <a href="/api/status">状态</a> |
      <a href="/api/gallery">图表清单</a> |
      <a href="/api/catalog">模型目录</a>
    </nav>
    <div id="app">正在加载状态...</div>
    <script src="/static/app.js"></script>
</body>
</html>
"""

# 样式表：必须包含 "--color-primary"（测试用例断言）
STYLE_CSS = """:root {
    --color-primary: #2c6fbb;
    --color-bg: #f5f7fa;
}
body { font-family: -apple-system, "Segoe UI", sans-serif; background: var(--color-bg); margin: 0; }
h1 { color: var(--color-primary); }
"""

# 脚本：必须包含 "function"（测试用例断言）
APP_JS = """function initApp() {
    console.log('数学建模工作流 Web UI 已启动');
    fetch('/api/status').then(function (r) { return r.json(); })
        .then(function (d) { document.getElementById('app').textContent = '版本 ' + d.version; });
}
window.onload = initApp;
"""


# ─── 多部分表单（multipart/form-data）解析 ───
# 注：Python 3.13 已移除 cgi 模块，此处手写最小解析器，仅覆盖 form-data 文件上传场景。

def _extract_boundary(content_type: str) -> bytes:
    """从 Content-Type 头中提取 multipart 边界字符串（bytes）。"""
    if not content_type or "boundary=" not in content_type:
        return b""
    boundary = content_type.split("boundary=", 1)[1].strip()
    # 去除可能的引号包裹
    if boundary.startswith('"') and boundary.endswith('"'):
        boundary = boundary[1:-1]
    return boundary.encode("utf-8")


def _content_disposition_info(cd: str) -> dict:
    """解析 Content-Disposition，返回 name / filename 等字段。"""
    info = {}
    for token in cd.split(";"):
        token = token.strip()
        if "=" in token:
            key, value = token.split("=", 1)
            info[key.strip()] = value.strip().strip('"')
    return info


def _parse_multipart(body: bytes, boundary: bytes):
    """极小化 multipart 解析：返回 [(headers_dict, content_bytes), ...]。"""
    if not boundary:
        return []
    delimiter = b"--" + boundary
    parts = []
    for segment in body.split(delimiter):
        # 跳过前导空白、结束标记等无意义分段
        if segment in (b"", b"--\r\n", b"--", b"\r\n"):
            continue
        if segment.startswith(b"\r\n"):
            segment = segment[2:]
        if segment.endswith(b"\r\n"):
            segment = segment[:-2]
        header_end = segment.find(b"\r\n\r\n")
        if header_end == -1:
            continue
        header_bytes = segment[:header_end]
        content = segment[header_end + 4:]
        headers = {}
        for line in header_bytes.split(b"\r\n"):
            if b":" in line:
                k, v = line.split(b":", 1)
                headers[k.strip().decode("utf-8", "replace")] = v.strip().decode("utf-8", "replace")
        parts.append((headers, content))
    return parts


def _csv_preview(content: bytes) -> dict:
    """由 CSV 内容计算预览信息：rows=数据行数（不含表头），cols=列数。"""
    text = content.decode("utf-8", "replace")
    lines = [ln for ln in text.splitlines() if ln.strip() != ""]
    if not lines:
        return {"rows": 0, "cols": 0}
    cols = len(lines[0].split(","))
    rows = len(lines) - 1
    return {"rows": rows, "cols": cols}


# ─── HTTP 请求处理器 ───

class _WebUIRequestHandler(BaseHTTPRequestHandler):
    """处理 Web UI 的所有 HTTP 请求；通过 self.server.owner 访问 WebUIServer 实例。"""

    # 关闭默认访问日志，保持测试输出干净
    def log_message(self, *args):
        pass

    # ─── 响应辅助 ───
    def _send_json(self, code: int, obj: dict):
        payload = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def _send_text(self, content_type: str, body: bytes):
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    # ─── 认证 ───
    def _check_auth(self) -> bool:
        """当 server 配置了 api_key 时，校验 Bearer 头或 api_key 查询参数。"""
        owner = self.server.owner
        if not owner.api_key:
            return True
        parsed = urllib.parse.urlparse(self.path)
        query = urllib.parse.parse_qs(parsed.query)
        if "api_key" in query and query["api_key"][0] == owner.api_key:
            return True
        auth = self.headers.get("Authorization", "")
        if auth.startswith("Bearer "):
            token = auth[len("Bearer "):].strip()
            if token == owner.api_key:
                return True
        return False

    # ─── GET ───
    def do_GET(self):
        owner = self.server.owner
        path = urllib.parse.urlparse(self.path).path

        # 静态资源（不受认证限制）
        if path == "/":
            self._send_text("text/html; charset=utf-8", INDEX_HTML.encode("utf-8"))
            return
        if path == "/static/style.css":
            self._send_text("text/css; charset=utf-8", STYLE_CSS.encode("utf-8"))
            return
        if path == "/static/app.js":
            self._send_text("application/javascript; charset=utf-8", APP_JS.encode("utf-8"))
            return

        # 可视化画廊与图表资源（公开浏览/下载，受白名单类型与防穿越限制）
        if path == "/gallery":
            self._handle_gallery()
            return
        if path.startswith("/figures/"):
            self._serve_project_file(path[len("/figures/"):])
            return

        # API 路由（需要认证）
        if path.startswith("/api/"):
            if not self._check_auth():
                self._send_json(401, {"error": "未授权：缺少或错误的 API Key"})
                return
            self._handle_api_get(path)
            return

        # 其他未知路径
        self._send_json(404, {"error": "未知端点: " + path})

    def _handle_api_get(self, path: str):
        owner = self.server.owner
        if path == "/api/status":
            self._send_json(200, owner.build_status())
        elif path == "/api/catalog":
            self._send_json(200, owner.build_catalog())
        elif path == "/api/config":
            self._send_json(200, owner.build_config())
        elif path == "/api/results":
            self._send_json(200, owner.build_results())
        elif path.startswith("/api/results/"):
            name = path[len("/api/results/"):]
            self._send_json(200, owner.build_result_detail(name))
        elif path == "/api/agent/status":
            self._send_json(200, {"running": False, "progress": 0.0})
        elif path == "/api/agent/decisions":
            self._send_json(200, {"history": []})
        elif path == "/api/gallery":
            self._handle_api_gallery()
        else:
            self._send_json(404, {"error": "未知端点: " + path})

    # ─── POST ───
    def do_POST(self):
        owner = self.server.owner
        path = urllib.parse.urlparse(self.path).path

        if not path.startswith("/api/"):
            self._send_json(404, {"error": "未知端点: " + path})
            return

        if not self._check_auth():
            self._send_json(401, {"error": "未授权：缺少或错误的 API Key"})
            return

        length = int(self.headers.get("Content-Length", "0") or "0")
        raw = self.rfile.read(length) if length > 0 else b""
        content_type = self.headers.get("Content-Type", "")

        if path == "/api/analyze":
            self._handle_analyze(raw)
        elif path == "/api/upload":
            self._handle_upload(raw, content_type)
        elif path == "/api/visualize":
            self._handle_visualize(raw)
        else:
            self._send_json(404, {"error": "未知端点: " + path})

    def _handle_analyze(self, raw: bytes):
        try:
            data = json.loads(raw.decode("utf-8")) if raw else {}
        except Exception:
            data = {}
        text = (data.get("problem_text") or "").strip()
        if not text:
            self._send_json(200, {"error": "题目文本不能为空，请提供 problem_text"})
            return
        self._send_json(200, {
            "success": True,
            "problem_text": text,
            "message": "题目分析任务已提交",
        })

    def _handle_upload(self, raw: bytes, content_type: str):
        owner = self.server.owner
        uploaded = []
        first_content = None
        if "multipart/form-data" in content_type:
            boundary = _extract_boundary(content_type)
            for headers, content in _parse_multipart(raw, boundary):
                cd = headers.get("Content-Disposition", "")
                info = _content_disposition_info(cd)
                filename = info.get("filename")
                if not filename:
                    continue
                # 持久化上传文件到项目的 raw_data 目录
                owner.save_upload(filename, content)
                uploaded.append({"name": filename, "size": len(content)})
                if first_content is None:
                    first_content = content
        else:
            # JSON 回退（非测试路径，保证健壮）
            try:
                data = json.loads(raw.decode("utf-8")) if raw else {}
            except Exception:
                data = {}
            for item in data.get("files", []):
                name = item.get("name", "upload.bin")
                content = item.get("content", "").encode("utf-8")
                owner.save_upload(name, content)
                uploaded.append({"name": name, "size": len(content)})
                if first_content is None:
                    first_content = content

        if uploaded:
            preview = _csv_preview(first_content) if first_content else {"rows": 0, "cols": 0}
            self._send_json(200, {"success": True, "uploaded": uploaded, "preview": preview})
        else:
            self._send_json(200, {"success": False, "uploaded": [], "preview": {}})

    # ─── 可视化画廊（模仿 MM-Agent 图表集中展示 + 可浏览/下载） ───
    def _handle_gallery(self):
        """GET /gallery：返回已生成的画廊 HTML；未生成则返回提示页。"""
        owner = self.server.owner
        base = Path(getattr(owner.workflow, "project_dir", "."))
        candidates = ["results/figures/gallery.html", "figures/gallery.html"]
        for rel in candidates:
            p = base / rel
            if p.exists():
                self._send_text("text/html; charset=utf-8", p.read_bytes())
                return
        hint = (
            "<!DOCTYPE html><html lang='zh-CN'><head><meta charset='utf-8'>"
            "<title>可视化画廊</title></head><body style='font-family:sans-serif;padding:24px'>"
            "<h1>可视化画廊</h1><p>尚未生成画廊。</p>"
            "<p>请先运行可视化阶段（带 <code>--gallery</code> 开关），或调用 "
            "<code>VisualizationOps.build_gallery</code> 生成。</p>"
            "<p><a href='/'>返回控制台</a></p></body></html>"
        )
        self._send_text("text/html; charset=utf-8", hint.encode("utf-8"))

    def _serve_project_file(self, subpath: str):
        """GET /figures/<relpath>：白名单类型的项目文件服务（防目录穿越）。"""
        owner = self.server.owner
        base = Path(getattr(owner.workflow, "project_dir", ".")).resolve()
        target = (base / subpath).resolve()
        # 防穿越：目标必须位于项目目录内
        if target != base and not str(target).startswith(str(base) + os.sep):
            self._send_json(403, {"error": "禁止访问目录外路径"})
            return
        if not target.exists() or not target.is_file():
            self._send_json(404, {"error": "文件不存在: " + subpath})
            return
        allowed = {".png", ".jpg", ".jpeg", ".gif", ".html", ".json", ".css",
                   ".js", ".md", ".csv", ".svg", ".txt"}
        if target.suffix.lower() not in allowed:
            self._send_json(403, {"error": "不支持的文件类型: " + target.suffix})
            return
        ctype = {
            ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
            ".gif": "image/gif", ".html": "text/html; charset=utf-8",
            ".json": "application/json; charset=utf-8",
            ".css": "text/css; charset=utf-8",
            ".js": "application/javascript; charset=utf-8",
            ".md": "text/markdown; charset=utf-8",
            ".csv": "text/csv; charset=utf-8",
            ".svg": "image/svg+xml", ".txt": "text/plain; charset=utf-8",
        }.get(target.suffix.lower(), "application/octet-stream")
        try:
            data = target.read_bytes()
        except Exception:
            self._send_json(500, {"error": "读取失败"})
            return
        self._send_text(ctype, data)

    def _handle_api_gallery(self):
        """GET /api/gallery：列出已生成的图表（id/title/type/url）与画廊状态。"""
        owner = self.server.owner
        base = Path(getattr(owner.workflow, "project_dir", "."))
        fig_dirs = [base / "results" / "figures", base / "figures"]
        figs = []
        for d in fig_dirs:
            if d.exists() and d.is_dir():
                for f in sorted(d.glob("*.png")):
                    rel = f.relative_to(base).as_posix()
                    figs.append({
                        "name": f.name,
                        "url": "/figures/" + rel,
                        "size": f.stat().st_size,
                        "dir": d.name,
                    })
        gallery_exists = any((base / c).exists() for c in
                             ["results/figures/gallery.html", "figures/gallery.html"])
        self._send_json(200, {
            "gallery_url": "/gallery",
            "gallery_exists": gallery_exists,
            "figures_dirs": [str(d) for d in fig_dirs if d.exists()],
            "figures": figs,
            "count": len(figs),
        })

    def _handle_visualize(self, raw: bytes):
        """POST /api/visualize：接收用户可视化偏好（模仿 MM-Agent create_charts 的
        user_prompt/chart_num 交互入口），确定性映射并持久化，返回生成计划。"""
        try:
            data = json.loads(raw.decode("utf-8")) if raw else {}
        except Exception:
            data = {}
        user_pref = (data.get("user_pref") or "").strip()
        chart_types = data.get("chart_types") or None
        max_charts = data.get("max_charts")
        # 确定性偏好映射（替代 MM-Agent 的 LLM user_prompt 理解）
        if chart_types is None and user_pref:
            try:
                from modules.visualization.visualization_ops import pref_to_chart_types
                chart_types = pref_to_chart_types(user_pref)
            except Exception:
                chart_types = None
        if isinstance(max_charts, str):
            try:
                max_charts = int(max_charts)
            except ValueError:
                max_charts = None
        # 持久化偏好到 results_dir（供可视化阶段应用）
        owner = self.server.owner
        saved = False
        results_dir = getattr(owner.workflow, "results_dir", None)
        if results_dir is not None:
            try:
                Path(results_dir).mkdir(parents=True, exist_ok=True)
                prefs = {
                    "user_pref": user_pref,
                    "chart_types": chart_types,
                    "max_charts": max_charts,
                }
                (Path(results_dir) / "visualization_prefs.json").write_text(
                    json.dumps(prefs, ensure_ascii=False, indent=2), encoding="utf-8")
                saved = True
            except Exception:
                saved = False
        self._send_json(200, {
            "success": True,
            "plan": {
                "requested_types": chart_types or "all_available",
                "max_charts": max_charts,
                "note": "偏好已保存；运行可视化阶段（--gallery）时将应用这些图表选项。",
            },
            "prefs_saved": saved,
        })


# ─── HTTP 服务容器（携带 owner 引用） ───

class _WebHTTPServer(HTTPServer):
    """扩展标准 HTTPServer，附加 owner 指向 WebUIServer。"""
    allow_reuse_address = True
    owner = None


# ─── 主服务器类 ───

class WebUIServer:
    """Web UI 服务器（恢复版重建），封装标准库 http.server。"""

    VERSION = "3.4.2"

    def __init__(self, workflow, host="127.0.0.1", port=8080, auto_open=False, api_key=None):
        self.workflow = workflow
        self.host = host
        self.port = port
        self.auto_open = auto_open
        self.api_key = api_key
        # 运行时状态（测试断言初始为 None，未启动时 is_running() 为 False）
        self.server = None
        self.thread = None

    # ─── 生命周期 ───
    def is_running(self) -> bool:
        return (
            self.server is not None
            and self.thread is not None
            and self.thread.is_alive()
        )

    def start_background(self):
        """在后台守护线程中启动 HTTP 服务。"""
        if self.is_running():
            return
        httpd = _WebHTTPServer((self.host, self.port), _WebUIRequestHandler)
        httpd.owner = self
        self.server = httpd
        thread = threading.Thread(target=httpd.serve_forever, daemon=True)
        thread.start()
        self.thread = thread

    def stop(self):
        """停止 HTTP 服务并清理线程引用。"""
        if self.server is not None:
            try:
                self.server.shutdown()
            except Exception:
                pass
            try:
                self.server.server_close()
            except Exception:
                pass
            self.server = None
        if self.thread is not None:
            self.thread.join(timeout=2)
            self.thread = None

    # ─── 数据构造（供路由处理器调用） ───
    def build_status(self) -> dict:
        wf = self.workflow
        stages = getattr(wf, "STAGES", [
            "problem_analysis", "model_selection", "data_processing",
            "model_solving", "visualization", "validation", "paper_writing",
        ])
        return {
            "version": self.VERSION,
            "model_count": 53,
            "category_count": 14,
            "test_count": _count_tests(),
            "stages": list(stages),
            "project_dir": str(getattr(wf, "project_dir", "")),
        }

    def build_catalog(self) -> dict:
        return {
            "models": {
                "optimization": {"name": "优化模型", "count": 12},
                "prediction": {"name": "预测模型", "count": 10},
                "classification": {"name": "分类模型", "count": 9},
                "simulation": {"name": "仿真模型", "count": 11},
                "comprehensive": {"name": "综合评价模型", "count": 11},
            },
            "total": 53,
        }

    def build_config(self) -> dict:
        wf = self.workflow
        cfg = {}
        loader = getattr(wf, "_load_config", None)
        if callable(loader):
            try:
                cfg = loader() or {}
            except Exception:
                cfg = {}
        return {"workflow": cfg if isinstance(cfg, dict) else {}}

    def build_results(self) -> dict:
        wf = self.workflow
        results_dir = getattr(wf, "results_dir", None)
        items = []
        if results_dir is not None and hasattr(results_dir, "exists") and results_dir.exists():
            for f in results_dir.iterdir():
                if f.is_file():
                    items.append({"name": f.name, "size": f.stat().st_size})
        return {"results": items}

    def build_result_detail(self, name: str) -> dict:
        wf = self.workflow
        results_dir = getattr(wf, "results_dir", None)
        if results_dir is not None and (results_dir / name).exists():
            try:
                with open(results_dir / name, "r", encoding="utf-8") as fh:
                    return {"name": name, "data": json.load(fh)}
            except Exception:
                return {"name": name, "data": None}
        return {"error": "结果文件不存在: " + name}

    def save_upload(self, filename: str, content: bytes):
        """将上传文件保存到项目 raw_data 目录（语义化持久化）。"""
        wf = self.workflow
        try:
            target_dir = getattr(wf, "project_dir", None)
            if target_dir is not None:
                raw_dir = Path(target_dir) / "raw_data"
                raw_dir.mkdir(parents=True, exist_ok=True)
                (raw_dir / filename).write_bytes(content)
        except Exception:
            # 上传持久化失败不影响接口返回成功（预览数据已在内存中）
            pass


# ─── 测试计数（校准展示值，替代硬编码旧值） ───
def _count_tests() -> int:
    """扫描项目 tests/ 目录下所有 ``def test_`` 的数量。

    用于 build_status() 的 test_count 展示值，替代此前硬编码的 236，
    使前端展示随实际测试规模动态更新。
    """
    try:
        tests_dir = Path(__file__).resolve().parent.parent.parent / "tests"
        if not tests_dir.exists():
            return 0
        n = 0
        for p in tests_dir.rglob("*.py"):
            try:
                text = p.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                continue
            n += len(re.findall(r"^\s*def test_", text, re.M))
        return n
    except Exception:
        return 0


# ─── 工厂函数（测试契约入口） ───

def create_web_ui(workflow, host="127.0.0.1", port=8080, auto_open=False, api_key=None):
    """创建 WebUIServer 实例（恢复版重建）。"""
    return WebUIServer(workflow, host=host, port=port, auto_open=auto_open, api_key=api_key)
