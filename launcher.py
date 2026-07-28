"""数学建模工作流 - WebUI 启动器（PyInstaller 打包入口）。

启动 WebUIServer 并自动打开浏览器，用户在浏览器中操作控制台。
打包后资源（config/）位于 sys._MEIPASS，启动时 chdir 到该目录使相对路径生效；
用户数据目录默认放在 exe 旁（可写）。
"""
import os
import sys
import time
import webbrowser
from pathlib import Path


def _resource_root() -> Path:
    """PyInstaller 打包后资源根目录；非打包时为脚本目录。"""
    if getattr(sys, "frozen", False):
        return Path(sys._MEIPASS)
    return Path(__file__).resolve().parent


def _writable_root() -> Path:
    """可写目录：exe 旁（打包）或脚本目录。"""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def main():
    import argparse
    parser = argparse.ArgumentParser(description="数学建模工作流 - WebUI 启动器")
    parser.add_argument("--port", type=int, default=8080, help="WebUI 端口")
    parser.add_argument("--host", default="127.0.0.1", help="监听地址")
    parser.add_argument("--project", default=None,
                        help="项目数据目录（默认 exe 旁 runtime_project）")
    parser.add_argument("--no-browser", action="store_true", help="不自动打开浏览器")
    args = parser.parse_args()

    # 切换到资源根，使 config/ 等相对路径生效；资源根加入 sys.path
    res = _resource_root()
    os.chdir(res)
    sys.path.insert(0, str(res))

    from main import MathModelingWorkflow
    from modules.web_ui import create_web_ui

    project_dir = Path(args.project) if args.project else _writable_root() / "runtime_project"
    project_dir.mkdir(parents=True, exist_ok=True)

    wf = MathModelingWorkflow(str(project_dir), non_interactive=True)
    # 端口被占时自动递增找空闲端口（避免双击崩溃）
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
        print(f"[launcher] 端口 {args.port}~{args.port + 11} 均被占用，请用 --port 指定其他端口")
        input("[launcher] 按回车键退出...")
        return

    url = f"http://{args.host}:{actual_port}/"
    if not args.no_browser:
        try:
            webbrowser.open(url)
        except Exception:
            pass
    print(f"[launcher] WebUI 已启动: {url}")
    print(f"[launcher] 项目数据目录: {project_dir}")
    print("[launcher] 按 Ctrl+C 退出...")
    try:
        while server.is_running():
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n[launcher] 正在停止...")
    finally:
        server.stop()


if __name__ == "__main__":
    main()
