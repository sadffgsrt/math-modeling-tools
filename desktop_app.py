"""数学建模工作流 - 桌面应用（PyWebView 壳）。

把 WebUI 包成原生桌面窗口：后台启动 WebUIServer，前台用 pywebview 窗口加载。
双击 exe 即弹出应用窗口，无需手动开浏览器。
"""
import os
import sys
import time
from pathlib import Path


def _resource_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys._MEIPASS)
    return Path(__file__).resolve().parent


def _writable_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def main():
    import argparse
    parser = argparse.ArgumentParser(description="数学建模工作流 - 桌面应用")
    parser.add_argument("--port", type=int, default=8080, help="WebUI 端口（被占用时换一个）")
    parser.add_argument("--host", default="127.0.0.1", help="监听地址")
    args = parser.parse_args()

    res = _resource_root()
    os.chdir(res)
    sys.path.insert(0, str(res))

    import webview
    from main import MathModelingWorkflow
    from modules.web_ui import create_web_ui

    project_dir = _writable_root() / "runtime_project"
    project_dir.mkdir(parents=True, exist_ok=True)

    wf = MathModelingWorkflow(str(project_dir), non_interactive=True)
    # 端口被占时自动递增找空闲端口
    server = None
    actual_port = args.port
    for offset in range(12):
        try_port = args.port + offset
        try:
            srv = create_web_ui(wf, host=args.host, port=try_port, auto_open=False)
            srv.start_background()
            if srv.is_running():
                server = srv
                actual_port = try_port
                break
        except (PermissionError, OSError):
            continue
    if server is None:
        print(f"[desktop] 端口 {args.port}~{args.port + 11} 均被占用，请用 --port 指定其他端口")
        input("[desktop] 按回车键退出...")
        return
    # 等待 HTTP 服务就绪
    for _ in range(20):
        if server.is_running():
            break
        time.sleep(0.1)

    url = f"http://{args.host}:{actual_port}/"
    webview.create_window(
        "数学建模竞赛工作流", url, width=1280, height=860, min_size=(900, 600))
    # 窗口关闭后退出
    try:
        webview.start()
    except Exception as e:
        print(f"[desktop] 桌面窗口启动失败：{e}")
        print(f"[desktop] 可改用 WebUI 版，或访问浏览器：{url}")
        input("[desktop] 按回车键退出...")
    server.stop()


if __name__ == "__main__":
    main()
