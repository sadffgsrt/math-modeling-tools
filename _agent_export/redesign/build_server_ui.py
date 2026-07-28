#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
build_server_ui.py -- 将 redesign/ 下的全新前端安全注入 modules/web_ui/server.py

做法：
  1. 读取 index.html / style.css / app.js（它们即 server.py 中 INDEX_HTML / STYLE_CSS / APP_JS 的新内容）。
  2. 将内容转义为 Python 三引号字符串的安全形式（避免与现有三引号冲突），
     通过正则替换 server.py 中已有的三个常量赋值（常量名 = 三引号包裹的内容）。
  3. 不改动任何 API 路由、HTTP 处理器、build_* 方法、工厂函数与测试契约。
  4. 注入后运行 tests/test_web_ui.py 验证契约不被破坏。

用法：
    python redesign/build_server_ui.py              注入并跑测试
    python redesign/build_server_ui.py --check-only  只校验三件套存在、不写文件
    python redesign/build_server_ui.py --dry-run     写临时文件 preview_server.py 不覆盖原文件
"""
from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent  # agent/
SERVER = ROOT / "modules" / "web_ui" / "server.py"


def read_text(name: str) -> str:
    p = HERE / name
    if not p.exists():
        raise SystemExit(f"[ERROR] 缺少源文件：{p}")
    return p.read_text(encoding="utf-8")


def to_py_triple(src: str) -> str:
    """把任意文本安全地包进 Python 三引号字符串。

    策略：优先使用不被内容包含的定界符；若内容同时含 ''' 与 \"\"\"，
    则对 \"\"\" 做最小化转义（替换为 \\\"\\\"\\"，并在结尾补 \"\"\" 防止截断）。
    这里采用最稳妥方案：检测内容是否包含 \"\"\"，若包含则整体用 r'''...''' 并把内部 ''' 转义。
    """
    if '"""' not in src and "'''" not in src:
        return '"""' + src + '"""'
    if "'''" not in src:
        # 内容里有 \"\"\" 但没有 '''，用 ''' 包裹
        return "'''" + src + "'''"
    # 两者都有：用 \"\"\" 包裹，并把内部 \"\"\" 转义为 \\\"\\\"\\\"
    escaped = src.replace('"""', '\\"\\"\\"')
    return '"""' + escaped + '"""'


# 匹配形如：  NAME = """...."""   或  NAME = '''....'''   （非贪婪，跨行）
CONST_RE = re.compile(
    r"(?P<name>INDEX_HTML|STYLE_CSS|APP_JS)\s*=\s*(?P<delim>\"\"\"|''')"
    r"(?P<body>.*?)(?P=delim)",
    re.DOTALL,
)


def build_new_server(old_text: str, html: str, css: str, js: str) -> str:
    repl = {
        "INDEX_HTML": to_py_triple(html),
        "STYLE_CSS": to_py_triple(css),
        "APP_JS": to_py_triple(js),
    }

    def _sub(m: re.Match) -> str:
        name = m.group("name")
        return f"{name} = {repl[name]}"

    new_text, n = CONST_RE.subn(_sub, old_text)
    if n != 3:
        raise SystemExit(f"[ERROR] 仅在 server.py 中找到 {n} 个目标常量（应为 3 个）。未注入，避免破坏。")
    return new_text


def run_tests() -> int:
    # 在 agent/ 目录运行测试；pytest 不可用则回退到 unittest
    try:
        rc = subprocess.call(
            [sys.executable, "-m", "pytest", "tests/test_web_ui.py", "-q",
             "-o", "addopts=", "-p", "no:cacheprovider"],
            cwd=str(ROOT),
        )
        if rc in (0, 1, 2, 3, 4, 5):  # pytest ran (even if some failed) → 不用回退到 unittest
            return rc
    except FileNotFoundError:
        pass
    return subprocess.call(
        [sys.executable, "-m", "unittest", "tests.test_web_ui", "-v"],
        cwd=str(ROOT),
    )


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check-only", action="store_true", help="只校验源文件存在，不写 server.py")
    ap.add_argument("--dry-run", action="store_true", help="写 preview_server.py 而不覆盖原文件")
    args = ap.parse_args()

    html = read_text("index.html")
    css = read_text("style.css")
    js = read_text("app.js")

    if args.check_only:
        print("[OK] 三件套齐全：index.html / style.css / app.js")
        # 快速契约自检
        assert "<html" in html and "app.js" in html, "INDEX_HTML 必须含 <html 与 app.js"
        assert "--color-primary" in css, "STYLE_CSS 必须含 --color-primary"
        assert "function" in js, "APP_JS 必须含 function"
        print("[OK] 前端契约自检通过（<html/app.js, --color-primary, function）")
        return 0

    if not SERVER.exists():
        raise SystemExit(f"[ERROR] 未找到 server.py：{SERVER}")

    old_text = SERVER.read_text(encoding="utf-8")
    # 备份
    backup = SERVER.with_suffix(".py.bak_" + "ui")
    shutil.copy2(SERVER, backup)
    print(f"[INFO] 已备份原 server.py -> {backup.name}")

    new_text = build_new_server(old_text, html, css, js)

    if args.dry_run:
        out = ROOT / "preview_server.py"
        out.write_text(new_text, encoding="utf-8")
        print(f"[DRY-RUN] 已写入 {out}（未覆盖 server.py）")
        target = out
    else:
        SERVER.write_text(new_text, encoding="utf-8")
        print(f"[OK] 已注入新前端到 {SERVER}")
        target = SERVER

    print("[INFO] 运行 tests/test_web_ui.py 验证契约…")
    rc = run_tests()
    if rc != 0:
        # 回滚
        shutil.copy2(backup, target)
        print("[ROLLBACK] 测试未通过，已回滚到备份。")
        return rc
    print("[OK] 测试通过，契约零回归。")
    print(f"[DONE] 下一步：在 agent/ 启动 Web UI 即可看到新界面（serve 端不变）。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
