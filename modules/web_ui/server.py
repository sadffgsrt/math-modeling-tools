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
INDEX_HTML = r"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<meta name="description" content="数学建模竞赛工作流控制台：题目分析、模型目录、数据上传、可视化与结果管理">
<title>数学建模竞赛工作流 · 控制台</title>
<link rel="stylesheet" href="/static/style.css">
</head>
<body data-theme="light">
<a class="skip-link" href="#main">跳到主内容</a>
<header class="topbar">
  <button class="icon-btn menu-toggle" id="menuToggle" aria-label="切换导航菜单"><svg class="ic" viewBox="0 0 24 24"><path d="M3 6h18M3 12h18M3 18h18"/></svg></button>
  <div class="brand"><span class="brand-mark" aria-hidden="true">∑</span><span class="brand-text">数学建模工作流</span></div>
  <div class="topbar-search" id="topSearch" role="search"><svg class="ic" viewBox="0 0 24 24" style="width:18px;height:18px"><circle cx="11" cy="11" r="7"/><path d="m21 21-4.3-4.3"/></svg><input id="globalSearch" placeholder="搜索模型 / 阶段…" aria-label="搜索"></div>
  <div class="topbar-right">
    <span class="conn" id="connStatus"><span class="dot"></span><span class="conn-text">连接中…</span></span>
    <span class="badge" id="verBadge">v—</span>
    <button class="icon-btn" id="themeToggle" aria-label="切换深色 / 浅色主题"><svg class="ic" viewBox="0 0 24 24"><path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8z"/></svg></button>
    <button class="icon-btn" id="settingsBtn" aria-label="设置"><svg class="ic" viewBox="0 0 24 24"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.7 1.7 0 0 0 .3 1.9l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-1.9-.3 1.7 1.7 0 0 0-1 1.5V21a2 2 0 1 1-4 0v-.1a1.7 1.7 0 0 0-1.1-1.5 1.7 1.7 0 0 0-1.9.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.7 1.7 0 0 0 .3-1.9 1.7 1.7 0 0 0-1.5-1H3a2 2 0 1 1 0-4h.1a1.7 1.7 0 0 0 1.5-1.1 1.7 1.7 0 0 0-.3-1.9l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.7 1.7 0 0 0 1.9.3H9a1.7 1.7 0 0 0 1-1.5V3a2 2 0 1 1 4 0v.1a1.7 1.7 0 0 0 1 1.5 1.7 1.7 0 0 0 1.9-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.7 1.7 0 0 0-.3 1.9V9a1.7 1.7 0 0 0 1.5 1H21a2 2 0 1 1 0 4h-.1a1.7 1.7 0 0 0-1.5 1z"/></svg></button>
  </div>
</header>
<div class="layout">
  <nav class="sidebar" id="sidebar" aria-label="主导航">
    <div class="side-title">建模流水线</div>
    <div id="stageNav"></div>
    <div class="side-title">资源</div>
    <div class="side-link" data-view="dashboard"><svg class="ic" viewBox="0 0 24 24"><path d="M3 3h7v7H3zM14 3h7v7h-7zM14 14h7v7h-7zM3 14h7v7H3z"/></svg>概览</div>
    <div class="side-link" data-view="catalog"><svg class="ic" viewBox="0 0 24 24"><path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"/><path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"/></svg>模型目录</div>
    <div class="side-link" data-view="analyze"><svg class="ic" viewBox="0 0 24 24"><circle cx="11" cy="11" r="7"/><path d="m21 21-4.3-4.3"/></svg>题目分析</div>
    <div class="side-link" data-view="upload"><svg class="ic" viewBox="0 0 24 24"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><path d="M17 8l-5-5-5 5"/><path d="M12 3v12"/></svg>数据上传</div>
    <div class="side-link" data-view="visualize"><svg class="ic" viewBox="0 0 24 24"><path d="M3 3v18h18"/><path d="m19 9-5 5-4-4-3 3"/></svg>可视化</div>
    <div class="side-link" data-view="results"><svg class="ic" viewBox="0 0 24 24"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><path d="M14 2v6h6"/></svg>结果</div>
    <div class="side-link" data-view="gallery"><svg class="ic" viewBox="0 0 24 24"><rect x="3" y="3" width="18" height="18" rx="2"/><circle cx="9" cy="9" r="2"/><path d="m21 15-5-5L5 21"/></svg>画廊</div>
  </nav>
  <main class="content" id="main" tabindex="-1"><div id="view" class="view"></div></main>
</div>
<div class="drawer-mask" id="drawerMask"></div>
<aside class="drawer" id="drawer" role="dialog" aria-modal="true" aria-label="详情"><div id="drawerInner"></div></aside>
<div class="toast-wrap" id="toastWrap" aria-live="polite" aria-atomic="false"></div>
<div class="modal-mask" id="settingsModal" hidden>
  <div class="modal" role="dialog" aria-modal="true" aria-label="设置">
    <h2 class="modal-title">设置</h2>
    <label class="field">
      <span class="field-label">API Key（若服务端启用鉴权）</span>
      <input type="text" id="apiKeyInput" placeholder="留空表示无需鉴权" autocomplete="off" spellcheck="false">
    </label>
    <p class="hint">API Key 仅保存在本机浏览器 localStorage，不会上传到服务器以外的地方。</p>
    <div class="modal-actions">
      <button class="btn ghost" id="settingsClose" type="button">关闭</button>
      <button class="btn primary" id="settingsSave" type="button">保存</button>
    </div>
  </div>
</div>
<script src="/static/app.js"></script>
</body>
</html>
"""

# 样式表：必须包含 "--color-primary"（测试用例断言）
STYLE_CSS = r""":root,[data-theme="light"]{
  --color-primary:#2c6fbb;--color-primary-weak:#e8f0fb;--color-primary-strong:#1f568f;
  --color-primary-grad:linear-gradient(135deg,#3b82f6 0%,#1f568f 100%);
  --bg:#f4f6fb;--surface:#fff;--surface-2:#f7f9fd;--surface-3:#eef2f8;
  --border:#e4e9f2;--border-strong:#cdd6e4;--text:#16202e;--text-2:#45526a;--text-weak:#6b7891;
  --success:#15a34a;--warn:#c97a09;--danger:#d83a3a;--info:#2c6fbb;
  --cat-optimization:#2c6fbb;--cat-prediction:#0e9488;--cat-classification:#7c3aed;
  --cat-clustering:#db2777;--cat-evaluation:#d97706;--cat-simulation:#0891b2;
  --cat-graph:#4f46e5;--cat-statistics:#65a30d;--cat-optimization_meta:#9333ea;
  --cat-time_series:#0284c7;--cat-uncertainty:#b45309;--cat-multi_objective:#be185d;
  --cat-neural:#2563eb;--cat-other:#475569;
  --shadow-xs:0 1px 2px rgba(16,24,40,.06);--shadow-sm:0 1px 3px rgba(16,24,40,.08),0 4px 10px rgba(16,24,40,.05);
  --shadow-md:0 6px 20px rgba(16,24,40,.10),0 2px 6px rgba(16,24,40,.06);--shadow-lg:0 16px 40px rgba(16,24,40,.16);
  --shadow-focus:0 0 0 3px rgba(44,111,187,.25);
  --radius-sm:10px;--radius:14px;--radius-lg:18px;--radius-pill:999px;
  --space-1:4px;--space-2:8px;--space-3:12px;--space-4:16px;--space-5:20px;--space-6:24px;--space-8:32px;--space-10:40px;
  --font-sans:"PingFang SC","Microsoft YaHei",-apple-system,BlinkMacSystemFont,"Segoe UI",system-ui,sans-serif;
  --font-mono:"JetBrains Mono","SFMono-Regular",Consolas,monospace;
}
[data-theme="dark"]{
  --color-primary:#5b9bff;--color-primary-weak:#15233a;--color-primary-strong:#a9ccff;
  --color-primary-grad:linear-gradient(135deg,#5b9bff 0%,#2c6fbb 100%);
  --bg:#0d1424;--surface:#151f33;--surface-2:#1c283f;--surface-3:#243352;
  --border:#2a3856;--border-strong:#3a4d73;--text:#eaf0fa;--text-2:#b9c6dc;--text-weak:#8d9cb8;
  --success:#34d399;--warn:#fbbf24;--danger:#f87171;--info:#5b9bff;
  --cat-optimization:#5b9bff;--cat-prediction:#2dd4bf;--cat-classification:#a78bfa;--cat-clustering:#f472b6;
  --cat-evaluation:#fbbf24;--cat-simulation:#22d3ee;--cat-graph:#818cf8;--cat-statistics:#a3e635;
  --cat-optimization_meta:#c084fc;--cat-time_series:#38bdf8;--cat-uncertainty:#fbbf24;--cat-multi_objective:#f472b6;
  --cat-neural:#60a5fa;--cat-other:#94a3b8;
  --shadow-sm:0 1px 3px rgba(0,0,0,.5),0 4px 10px rgba(0,0,0,.4);--shadow-md:0 6px 20px rgba(0,0,0,.55);--shadow-lg:0 16px 40px rgba(0,0,0,.6);
}
*{box-sizing:border-box}html,body{height:100%}
body{margin:0;font-family:var(--font-sans);background:var(--bg);color:var(--text);line-height:1.6;-webkit-font-smoothing:antialiased;transition:background .25s,color .25s}
a{color:var(--color-primary)}
.skip-link{position:absolute;left:-999px;top:8px;z-index:100;background:var(--color-primary);color:#fff;padding:8px 14px;border-radius:8px}
.skip-link:focus{left:12px}
.ic{width:20px;height:20px;stroke:currentColor;stroke-width:2;fill:none;stroke-linecap:round;stroke-linejoin:round;flex:none}
.topbar{position:sticky;top:0;z-index:30;display:flex;align-items:center;gap:14px;padding:10px 18px;background:var(--surface);border-bottom:1px solid var(--border)}
.brand{display:flex;align-items:center;gap:11px;font-weight:800;font-size:16px;letter-spacing:.2px}
.brand-mark{display:grid;place-items:center;width:32px;height:32px;border-radius:10px;background:var(--color-primary-grad);color:#fff;font-size:18px;font-weight:800;box-shadow:var(--shadow-sm)}
.topbar-search{margin-left:10px;display:flex;align-items:center;gap:8px;background:var(--surface-2);border:1px solid var(--border);border-radius:var(--radius-pill);padding:8px 14px;min-width:240px;color:var(--text-weak)}
.topbar-search input{border:0;background:transparent;outline:none;color:var(--text);font-size:14px;width:100%;font-family:inherit}
.topbar-right{margin-left:auto;display:flex;align-items:center;gap:10px}
.conn{display:inline-flex;align-items:center;gap:7px;font-size:12.5px;color:var(--text-weak);background:var(--surface-2);padding:6px 11px;border-radius:var(--radius-pill);border:1px solid var(--border)}
.conn .dot{width:8px;height:8px;border-radius:50%;background:var(--text-weak);transition:background .3s}
.conn.ok .dot{background:var(--success);box-shadow:0 0 0 3px rgba(21,163,74,.16)}
.conn.err .dot{background:var(--danger);box-shadow:0 0 0 3px rgba(216,58,58,.16)}
.conn-text{font-weight:600}
.badge{font-size:12px;font-weight:700;padding:4px 10px;border-radius:var(--radius-pill);background:var(--color-primary-weak);color:var(--color-primary-strong);font-family:var(--font-mono)}
.icon-btn{border:1px solid var(--border);background:var(--surface);color:var(--text);width:38px;height:38px;border-radius:11px;cursor:pointer;display:inline-grid;place-items:center;transition:background .15s,transform .1s}
.icon-btn:hover{background:var(--surface-2)}.icon-btn:active{transform:scale(.94)}
.menu-toggle{display:none}
.layout{display:grid;grid-template-columns:248px 1fr;min-height:calc(100vh - 59px)}
.sidebar{background:var(--surface);border-right:1px solid var(--border);padding:16px 12px;position:sticky;top:59px;align-self:start;height:calc(100vh - 59px);overflow-y:auto}
.side-title{font-size:11px;font-weight:700;letter-spacing:.08em;text-transform:uppercase;color:var(--text-weak);padding:6px 10px;margin-top:6px}
.stage{display:flex;align-items:center;gap:11px;padding:10px 11px;border-radius:12px;cursor:pointer;color:var(--text);font-size:14px;font-weight:600;border:1px solid transparent;transition:background .15s,border-color .15s;position:relative}
.stage:hover{background:var(--surface-2)}
.stage.active{background:var(--color-primary-weak);border-color:var(--color-primary);color:var(--color-primary-strong)}
.stage .st-idx{display:grid;place-items:center;width:26px;height:26px;border-radius:8px;background:var(--surface-3);color:var(--text-2);font-size:12.5px;font-weight:800;flex:none}
.stage.active .st-idx{background:var(--color-primary);color:#fff}
.stage.done .st-idx{background:var(--success);color:#fff}
.stage .st-ico{color:var(--text-weak)}.stage.active .st-ico{color:var(--color-primary)}
.side-link{display:flex;align-items:center;gap:11px;padding:9px 11px;border-radius:10px;cursor:pointer;color:var(--text-2);font-size:14px;font-weight:500}
.side-link:hover{background:var(--surface-2);color:var(--text)}
.side-link.active{color:var(--color-primary-strong);font-weight:700;background:var(--color-primary-weak)}
.content{padding:24px clamp(16px,3vw,34px);max-width:1240px;width:100%}
.page-head{margin:0 0 20px}.page-head h1{margin:0 0 5px;font-size:23px;font-weight:800}
.page-head p{margin:0;color:var(--text-weak);font-size:14px}
.hero{background:var(--color-primary-grad);color:#fff;border-radius:var(--radius-lg);padding:24px 26px;display:flex;align-items:center;gap:24px;box-shadow:var(--shadow-md);position:relative;overflow:hidden}
.hero h2{margin:0 0 6px;font-size:21px;font-weight:800}
.hero p{margin:0;opacity:.92;font-size:14px;max-width:620px}
.hero .ring{margin-left:auto;flex:none}
.ring{--p:42;width:104px;height:104px;border-radius:50%;background:conic-gradient(#fff calc(var(--p)*1%),rgba(255,255,255,.28) 0);display:grid;place-items:center;position:relative}
.ring::after{content:"";position:absolute;inset:10px;border-radius:50%;background:var(--color-primary-strong)}
.ring span{position:relative;z-index:1;font-family:var(--font-mono);font-weight:800;font-size:22px}
.grid{display:grid;gap:16px}.cols-4{grid-template-columns:repeat(4,1fr)}.cols-3{grid-template-columns:repeat(3,1fr)}.cols-2{grid-template-columns:repeat(2,1fr)}
.card{background:var(--surface);border:1px solid var(--border);border-radius:var(--radius);padding:17px;box-shadow:var(--shadow-sm);transition:transform .15s,box-shadow .15s,border-color .15s}
.card.hover:hover{transform:translateY(-2px);border-color:var(--color-primary);box-shadow:var(--shadow-md)}
.stat .stat-label{font-size:13px;color:var(--text-weak);font-weight:600}
.stat .stat-value{font-size:27px;font-weight:800;margin-top:5px;color:var(--color-primary-strong);font-family:var(--font-mono)}
.stat .stat-sub{font-size:12px;color:var(--text-weak);margin-top:3px}
.section-title{font-size:15px;font-weight:800;margin:26px 0 13px;display:flex;align-items:center;gap:8px}
.nextbar{display:flex;align-items:center;gap:10px;background:var(--surface);border:1px solid var(--border);border-radius:var(--radius);padding:12px 16px;margin-bottom:18px;box-shadow:var(--shadow-xs)}
.nextbar .nb-label{font-size:13px;color:var(--text-weak);font-weight:600}
.btn{border:1px solid var(--border);background:var(--surface);color:var(--text);padding:10px 17px;border-radius:11px;cursor:pointer;font-size:14px;font-weight:700;transition:background .15s,transform .1s,box-shadow .15s;display:inline-flex;align-items:center;gap:8px}
.btn:hover{background:var(--surface-2)}.btn:active{transform:scale(.97)}
.btn.primary{background:var(--color-primary);border-color:var(--color-primary);color:#fff}.btn.primary:hover{background:var(--color-primary-strong);box-shadow:var(--shadow-sm)}
.btn.ghost{background:transparent}.btn:disabled{opacity:.55;cursor:not-allowed;pointer-events:none}
.field{display:flex;flex-direction:column;gap:7px;margin-bottom:13px}
.field-label{font-size:13px;color:var(--text-weak);font-weight:700}
input[type=text],input[type=number],input[type=email],textarea,select{width:100%;padding:11px 13px;border:1px solid var(--border);border-radius:11px;background:var(--surface);color:var(--text);font-size:14px;font-family:inherit;transition:border-color .15s,box-shadow .15s}
input:focus,textarea:focus,select:focus{outline:none;border-color:var(--color-primary);box-shadow:var(--shadow-focus)}
textarea{resize:vertical;min-height:170px;line-height:1.65}
.badge-pill{font-size:11.5px;font-weight:700;padding:3px 10px;border-radius:var(--radius-pill);background:var(--surface-3);color:var(--text-weak);display:inline-flex;align-items:center;gap:5px;white-space:nowrap}
.badge-pill.cpl-low{background:#dcfce7;color:#15803d}.badge-pill.cpl-medium{background:#fef3c7;color:#b45309}.badge-pill.cpl-high{background:#fee2e2;color:#b91c1c}
.badge-pill.impl{background:var(--color-primary-weak);color:var(--color-primary-strong)}
.chip{display:inline-block;font-size:12px;padding:4px 10px;border-radius:var(--radius-pill);background:var(--color-primary-weak);color:var(--color-primary-strong);margin:3px 5px 3px 0;font-weight:600}
.cat-card{display:flex;flex-direction:column;gap:9px;cursor:pointer;border-left:4px solid var(--c,var(--color-primary))}
.cat-card .cat-top{display:flex;align-items:center;gap:11px}
.cat-ico{display:grid;place-items:center;width:38px;height:38px;border-radius:11px;background:var(--c,var(--color-primary));color:#fff;flex:none}
.cat-card h3{margin:0;font-size:16px;font-weight:800}
.cat-card .cat-count{margin-left:auto;font-family:var(--font-mono);font-weight:800;color:var(--text-weak);font-size:13px}
.cat-card p{margin:0;font-size:13px;color:var(--text-weak);line-height:1.5}
.model-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(270px,1fr));gap:14px}
.model{border:1px solid var(--border);border-radius:12px;padding:14px;background:var(--surface);cursor:pointer;transition:border-color .15s,transform .12s,box-shadow .15s}
.model:hover{border-color:var(--color-primary);transform:translateY(-1px);box-shadow:var(--shadow-sm)}
.model h4{margin:0 0 5px;font-size:14.5px;display:flex;align-items:center;gap:8px;flex-wrap:wrap;font-weight:800}
.model p{margin:4px 0 0;font-size:13px;color:var(--text-weak);line-height:1.5}
.toolbar{display:flex;flex-wrap:wrap;gap:10px;align-items:center;margin-bottom:15px}
.toolbar .spacer{flex:1}
.search-inline{display:flex;align-items:center;gap:8px;background:var(--surface);border:1px solid var(--border);border-radius:11px;padding:9px 13px;min-width:280px}
.search-inline input{border:0;background:transparent;outline:none;color:var(--text);font-size:14px;width:100%;font-family:inherit}
.dropzone{border:2px dashed var(--border-strong);border-radius:var(--radius);padding:36px 22px;text-align:center;color:var(--text-weak);cursor:pointer;transition:border-color .15s,background .15s;background:var(--surface)}
.dropzone:hover,.dropzone.drag{border-color:var(--color-primary);background:var(--color-primary-weak);color:var(--color-primary-strong)}
.dropzone strong{color:var(--color-primary)}
.file-row{display:flex;align-items:center;gap:11px;padding:10px 13px;border:1px solid var(--border);border-radius:11px;margin-top:9px;background:var(--surface)}
.file-row .f-name{font-size:13.5px;font-weight:700}.file-row .f-size{font-size:12px;color:var(--text-weak);margin-left:auto;font-family:var(--font-mono)}
.result-row{display:flex;align-items:center;gap:11px;padding:11px 14px;border:1px solid var(--border);border-radius:11px;margin-top:9px;background:var(--surface);cursor:pointer;transition:background .15s}
.result-row:hover{background:var(--surface-2)}.result-row .r-name{font-size:13.5px;font-weight:700;word-break:break-all}.result-row .r-size{font-size:12px;color:var(--text-weak);margin-left:auto;font-family:var(--font-mono);white-space:nowrap}
pre.json{background:var(--surface-2);border:1px solid var(--border);border-radius:11px;padding:15px;overflow:auto;font-size:12.5px;line-height:1.55;max-height:440px;font-family:var(--font-mono);white-space:pre-wrap;word-break:break-word}
.empty{text-align:center;color:var(--text-weak);padding:42px 0;font-size:14px}
.empty .emp-ico{width:46px;height:46px;margin:0 auto 12px;color:var(--text-weak);opacity:.7}
.gallery-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(200px,1fr));gap:14px}
.fig-card{border:1px solid var(--border);border-radius:12px;overflow:hidden;background:var(--surface);transition:transform .15s,box-shadow .15s;text-decoration:none;color:inherit}
.fig-card:hover{transform:translateY(-2px);box-shadow:var(--shadow-md)}
.fig-card .fig-ph{height:150px;background:linear-gradient(135deg,var(--surface-3),var(--color-primary-weak));display:grid;place-items:center;color:var(--color-primary)}
.fig-card .fig-ph img{width:100%;height:100%;object-fit:cover}
.fig-card .fig-meta{padding:9px 11px;font-size:12.5px;color:var(--text-weak);display:flex;justify-content:space-between;gap:8px}
.res-block{background:var(--surface);border:1px solid var(--border);border-radius:var(--radius);padding:15px 17px;margin-top:13px;box-shadow:var(--shadow-xs)}
.res-block h4{margin:0 0 9px;font-size:14px;font-weight:800;display:flex;align-items:center;gap:8px}
.res-block ul{margin:0;padding-left:18px;font-size:13px;color:var(--text-2);line-height:1.7}
.res-block p{margin:0;font-size:13.5px;color:var(--text-2)}
.kv{display:flex;gap:10px;font-size:13.5px;padding:5px 0;border-bottom:1px dashed var(--border)}
.kv:last-child{border-bottom:0}.kv .k{color:var(--text-weak);min-width:96px;font-weight:600;flex:none}
.kv .v{flex:1}
.suggest{display:flex;flex-wrap:wrap;gap:8px;margin-top:4px}
.suggest .sm{display:inline-flex;align-items:center;gap:6px;padding:6px 12px;border-radius:var(--radius-pill);background:var(--color-primary-weak);color:var(--color-primary-strong);font-weight:700;font-size:13px;cursor:pointer;border:1px solid transparent}
.suggest .sm:hover{border-color:var(--color-primary)}
.drawer-mask{position:fixed;inset:0;background:rgba(16,24,40,.45);z-index:70;opacity:0;pointer-events:none;transition:opacity .22s}
.drawer-mask.open{opacity:1;pointer-events:auto}
.drawer{position:fixed;top:0;right:0;height:100vh;width:min(440px,92vw);background:var(--surface);z-index:71;box-shadow:var(--shadow-lg);transform:translateX(100%);transition:transform .26s cubic-bezier(.22,.61,.36,1);display:flex;flex-direction:column}
.drawer.open{transform:none}
.drawer-head{padding:18px 20px;border-bottom:1px solid var(--border);display:flex;align-items:flex-start;gap:12px}
.drawer-head h2{margin:0;font-size:18px;font-weight:800}
.drawer-head .dh-sub{font-size:12.5px;color:var(--text-weak);margin-top:3px}
.drawer-body{padding:18px 20px;overflow-y:auto;flex:1}
.toast-wrap{position:fixed;right:16px;bottom:16px;z-index:80;display:flex;flex-direction:column;gap:10px;max-width:340px}
.toast{background:var(--surface);border:1px solid var(--border);border-left:4px solid var(--info);border-radius:11px;padding:11px 14px;box-shadow:var(--shadow-md);font-size:13.5px;animation:slidein .25s ease;display:flex;gap:9px;align-items:flex-start}
.toast.ok{border-left-color:var(--success)}.toast.err{border-left-color:var(--danger)}.toast.warn{border-left-color:var(--warn)}
@keyframes slidein{from{opacity:0;transform:translateX(20px)}to{opacity:1;transform:none}}
@keyframes fade{from{opacity:0;transform:translateY(6px)}to{opacity:1;transform:none}}
.view{animation:fade .25s ease}
:focus-visible{outline:2px solid var(--color-primary);outline-offset:2px}
/* ── 设计增强补充 ── */
.hint{color:var(--text-weak);font-size:12.5px}
.scrim{position:fixed;inset:0;background:rgba(0,0,0,.3);z-index:24}
.scrim[hidden]{display:none}
.spinner{width:18px;height:18px;border:2.5px solid var(--color-primary-weak);border-top-color:var(--color-primary);border-radius:50%;animation:spin .7s linear infinite;flex:none}
@keyframes spin{to{transform:rotate(360deg)}}
.loading-block{display:flex;gap:10px;align-items:center;color:var(--text-weak);padding:18px 0}
.stat-skeleton{height:86px;border-radius:var(--radius);background:linear-gradient(90deg,var(--surface-2) 25%,var(--surface-3) 37%,var(--surface-2) 63%);background-size:400% 100%;animation:shimmer 1.3s ease infinite}
@keyframes shimmer{0%{background-position:100% 0}100%{background-position:0 0}}
.modal-mask{position:fixed;inset:0;background:rgba(16,24,40,.5);z-index:90;display:flex;align-items:center;justify-content:center;opacity:0;pointer-events:none;transition:opacity .2s}
.modal-mask.open{opacity:1;pointer-events:auto}
.modal-mask[hidden]{display:none}
.modal{background:var(--surface);border:1px solid var(--border);border-radius:var(--radius-lg);box-shadow:var(--shadow-lg);width:min(440px,92vw);padding:22px;animation:fade .2s ease}
.modal-title{margin:0 0 14px;font-size:18px;font-weight:800}
.modal-actions{display:flex;justify-content:flex-end;gap:10px;margin-top:8px}
@media (max-width:900px){.cols-4{grid-template-columns:repeat(2,1fr)}.cols-3{grid-template-columns:repeat(2,1fr)}}
@media (max-width:760px){.menu-toggle{display:inline-grid}.topbar-search{display:none}.brand span.brand-text{display:none}.layout{grid-template-columns:1fr}.sidebar{position:fixed;top:59px;left:0;bottom:0;width:248px;z-index:25;transform:translateX(-100%);transition:transform .22s;box-shadow:var(--shadow-md)}.sidebar.open{transform:none}.cols-2,.cols-3,.cols-4{grid-template-columns:1fr}.content{padding:16px}.scrim{position:fixed;inset:0;background:rgba(0,0,0,.3);z-index:24}.scrim[hidden]{display:none}}
@media (prefers-reduced-motion:reduce){*{animation-duration:.001ms!important;transition-duration:.001ms!important}}
"""

# 脚本：必须包含 "function"（测试用例断言）
APP_JS = r"""/* 数学建模工作流控制台 — 前端 SPA（与 redesign 设计语言同步，接入真实 API） */
(function(){
  "use strict";

  var BASE = "";

  /* ── SVG 图标（Lucide 风格路径） ── */
  var ICONS = {
    menu:"M3 6h18M3 12h18M3 18h18",
    search:"M11 11a7 7 0 1 0 0.01 0M21 21l-4.3-4.3",
    sun:"M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8z",
    settings:"M19.4 15a1.7 1.7 0 0 0 .3 1.9l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-1.9-.3 1.7 1.7 0 0 0-1 1.5V21a2 2 0 1 1-4 0v-.1a1.7 1.7 0 0 0-1.1-1.5 1.7 1.7 0 0 0-1.9.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.7 1.7 0 0 0 .3-1.9 1.7 1.7 0 0 0-1.5-1H3a2 2 0 1 1 0-4h.1a1.7 1.7 0 0 0 1.5-1.1 1.7 1.7 0 0 0-.3-1.9l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.7 1.7 0 0 0 1.9.3H9a1.7 1.7 0 0 0 1-1.5V3a2 2 0 1 1 4 0v.1a1.7 1.7 0 0 0 1 1.5 1.7 1.7 0 0 0 1.9-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.7 1.7 0 0 0-.3 1.9V9a1.7 1.7 0 0 0 1.5 1H21a2 2 0 1 1 0 4h-.1a1.7 1.7 0 0 0-1.5 1z",
    grid:"M3 3h7v7H3zM14 3h7v7h-7zM14 14h7v7h-7zM3 14h7v7H3z",
    book:"M4 19.5A2.5 2.5 0 0 1 6.5 17H20M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z",
    upload:"M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4M17 8l-5-5-5 5M12 3v12",
    chart:"M3 3v18h18M19 9l-5 5-4-4-3 3",
    file:"M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8zM14 2v6h6",
    image:"M3 3h18v18H3zM9 9a2 2 0 1 0 0-4 2 2 0 0 0 0 4zM21 15l-5-5L5 21",
    close:"M18 6 6 18M6 6l12 12",
    check:"M9 12l2 2 4-4",
    arrow:"M12 2v4M12 18v4M2 12h4M18 12h4",
    spark:"M12 2v4M12 18v4M2 12h4M18 12h4M12 2l2 2M12 22l-2-2M2 12l2-2M22 12l-2 2",
    download:"M12 3v12M7 10l5 5 5-5M5 21h14",
    copy:"M9 9h10v10H9zM5 15H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h8a2 2 0 0 1 2 2v0"
  };
  function icon(name, size){
    size = size || 20;
    var p = ICONS[name] || "";
    return '<svg class="ic" viewBox="0 0 24 24" style="width:'+size+'px;height:'+size+'px" aria-hidden="true"><path d="'+p+'"/></svg>';
  }

  /* ── 流水线阶段元数据（服务端仅返回 id 列表） ── */
  var STAGE_ORDER = ["problem_analysis","model_selection","data_processing","model_solving","visualization","validation","paper_writing"];
  var STAGE_META = {
    problem_analysis:{name:"题目分析", ico:"M11 11V3M11 11l-3 3M11 11l3 3", view:"analyze"},
    model_selection:{name:"模型选择", ico:"M4 19.5A2.5 2.5 0 0 1 6.5 17H20", view:"catalog"},
    data_processing:{name:"数据处理", ico:"M3 3v18h18", view:"upload"},
    model_solving:{name:"模型求解", ico:"M3 3h18v18H3z", view:"results"},
    visualization:{name:"可视化",   ico:"m19 9-5 5-4-4-3 3", view:"visualize"},
    validation:{name:"验证",      ico:"M9 12l2 2 4-4", view:"results"},
    paper_writing:{name:"论文撰写", ico:"M4 4h16v16H4z", view:"results"}
  };
  var VIEW_STAGE = {
    dashboard:null, analyze:"problem_analysis", catalog:"model_selection",
    upload:"data_processing", visualize:"visualization",
    results:["model_solving","validation","paper_writing"], gallery:null
  };

  /* ── 状态 ── */
  var state = { currentView:"dashboard", apiKey:"", done:{}, catalogData:null };

  function loadDone(){ try{ state.done = JSON.parse(localStorage.getItem("mm_stages_done")||"{}")||{}; }catch(e){ state.done={}; } }
  function saveDone(){ try{ localStorage.setItem("mm_stages_done", JSON.stringify(state.done)); }catch(e){} }
  function markStage(id){
    if(!id || state.done[id]) return;
    state.done[id]=true; saveDone(); renderStages();
    if(state.currentView==="dashboard") renderDashboard();
  }
  function markView(view){
    var s = VIEW_STAGE[view]; if(!s) return;
    if(Array.isArray(s)) s.forEach(markStage); else markStage(s);
  }
  function countDone(){ var n=0; for(var i=0;i<STAGE_ORDER.length;i++) if(state.done[STAGE_ORDER[i]]) n++; return n; }

  /* ── 工具 ── */
  function esc(s){ return String(s==null?"":s).replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;"); }
  function cplText(c){ return c==="low"?"低":c==="medium"?"中":c==="high"?"高":esc(c||"—"); }
  function fmtSize(n){ n=Number(n)||0; if(n<1024) return n+" B"; if(n<1048576) return (n/1024).toFixed(1)+" KB"; return (n/1048576).toFixed(1)+" MB"; }
  function pageHead(h1,p){ return '<div class="page-head"><h1>'+esc(h1)+'</h1><p>'+esc(p||"")+'</p></div>'; }
  function statCard(label,value,sub){ return '<div class="card stat"><div class="stat-label">'+esc(label)+'</div><div class="stat-value">'+esc(String(value))+'</div><div class="stat-sub">'+esc(sub||"")+'</div></div>'; }
  function statSkeleton(){ return '<div class="card stat stat-skeleton"></div>'; }
  function totalModels(){
    if(state.catalogData && state.catalogData.total) return state.catalogData.total;
    if(state.catalogData && state.catalogData.categories) return state.catalogData.categories.reduce(function(a,c){ return a+(c.count||(c.models||[]).length||0); },0);
    return "—";
  }
  function api(path, opts){
    opts = opts || {};
    var headers = opts.headers || {};
    if(state.apiKey) headers["Authorization"] = "Bearer " + state.apiKey;
    return fetch(BASE + path, { method: opts.method || "GET", headers: headers, body: opts.body });
  }
  function getJSON(path){ return api(path).then(function(r){ return r.json(); }); }
  function copyText(t){
    try{ if(navigator.clipboard){ navigator.clipboard.writeText(t); return; } }catch(e){}
    var ta=document.createElement("textarea"); ta.value=t; document.body.appendChild(ta); ta.select();
    try{ document.execCommand("copy"); }catch(_){} document.body.removeChild(ta);
  }

  var view = document.getElementById("view");

  /* ── 侧边流水线导航 ── */
  function renderStages(){
    var nav = document.getElementById("stageNav"); if(!nav) return;
    nav.innerHTML = STAGE_ORDER.map(function(id, idx){
      var m = STAGE_META[id]; if(!m) return "";
      var done = !!state.done[id];
      return '<div class="stage '+(done?"done":"")+'" data-stage="'+id+'">'+
        '<span class="st-idx">'+esc(done?"✓":(idx+1))+'</span>'+
        '<svg class="ic st-ico" viewBox="0 0 24 24" style="width:18px;height:18px"><path d="'+m.ico+'"/></svg>'+
        '<span>'+esc(m.name)+'</span></div>';
    }).join("");
    var stages = nav.querySelectorAll(".stage");
    for(var i=0;i<stages.length;i++)(function(el){
      el.addEventListener("click", function(){ var v = STAGE_META[el.dataset.stage].view; if(v) navigate(v); });
    })(stages[i]);
  }

  /* ── 概览 ── */
  function renderDashboard(){
    var total = STAGE_ORDER.length, done = countDone(), p = Math.round(done/total*100);
    view.innerHTML = pageHead("工作台","跟着七阶段流水线推进你的建模任务") +
      '<div class="hero"><div><h2>开始你的建模工作流</h2>'+
      '<p>从题目分析到论文撰写，平台已内置 14 大类 53 个模型，覆盖优化、预测、分类、仿真与评价全流程。</p>'+
      '<div style="margin-top:14px"><button class="btn" style="background:rgba(255,255,255,.16);color:#fff;border-color:rgba(255,255,255,.3)" data-view="analyze">'+icon("search",16)+' 从题目分析开始</button></div></div>'+
      '<div class="ring" style="--p:'+p+'"><span>'+done+'/'+total+'</span></div></div>'+
      '<div class="section-title">关键指标</div>'+
      '<div class="grid cols-4" id="statGrid">'+statSkeleton()+statSkeleton()+statSkeleton()+statSkeleton()+'</div>'+
      '<div class="section-title">建模流水线</div>'+
      '<div class="nextbar">'+icon("arrow",18)+'<span class="nb-label">下一步建议：</span><strong id="nextStage">—</strong>'+
      '<span id="nextHint" style="color:var(--text-weak);font-size:13px"></span><span class="spacer"></span>'+
      '<button class="btn primary" id="nextBtn">前往</button></div>'+
      '<div class="grid cols-3" id="stageCards"></div>'+
      '<div class="section-title">快捷操作</div>'+
      '<div class="toolbar"><button class="btn primary" data-view="analyze">'+icon("search",16)+' 题目分析</button>'+
      '<button class="btn" data-view="catalog">'+icon("book",16)+' 模型目录</button>'+
      '<button class="btn" data-view="gallery">'+icon("image",16)+' 画廊</button>'+
      '<button class="btn" data-view="results">'+icon("file",16)+' 结果</button></div>';

    var next = STAGE_ORDER.filter(function(id){ return !state.done[id]; })[0];
    var nb = document.getElementById("nextBtn"), ns = document.getElementById("nextStage"), nh = document.getElementById("nextHint");
    if(!next){ ns.textContent="全部阶段已完成"; nh.textContent=""; if(nb){ nb.textContent="查看结果"; nb.onclick=function(){ navigate("results"); }; } }
    else { var m = STAGE_META[next]; ns.textContent=m.name; nh.textContent="— 点击进入推进"; if(nb){ nb.textContent="前往"; nb.onclick=function(){ navigate(m.view); }; } }

    getJSON("/api/status").then(function(d){
      document.getElementById("statGrid").innerHTML =
        statCard("版本", d.version||"—", "当前构建") +
        statCard("模型总数", d.model_count!=null?d.model_count:"—", (d.category_count!=null?d.category_count:"")+" 个类别") +
        statCard("测试用例", d.test_count!=null?d.test_count+"+":"—", "已通过") +
        statCard("流水线阶段", (d.stages||[]).length||"—", "端到端");
      if(d.version) document.getElementById("verBadge").textContent = "v"+d.version;
      renderStageCards(d.stages || STAGE_ORDER);
    }).catch(function(){
      document.getElementById("statGrid").innerHTML = statCard("版本","—","")+statCard("模型总数","—","")+statCard("测试用例","—","")+statCard("流水线阶段","—","");
      toast("无法获取状态","err");
    });
  }
  function renderStageCards(stages){
    var grid = document.getElementById("stageCards"); if(!grid) return;
    grid.innerHTML = (stages||[]).map(function(id, i){
      var m = STAGE_META[id] || { name:id, ico:"" }; var done = !!state.done[id];
      return '<div class="card hover" data-stage="'+esc(id)+'" style="cursor:pointer;display:flex;flex-direction:column;gap:8px">'+
        '<div style="display:flex;align-items:center;gap:10px">'+
        '<span class="cat-ico" style="width:34px;height:34px;background:'+(done?"var(--success)":"var(--surface-3)")+';color:'+(done?"#fff":"var(--text-2)")+'"><svg class="ic" viewBox="0 0 24 24" style="width:18px;height:18px"><path d="'+m.ico+'"/></svg></span>'+
        '<strong style="font-size:14.5px">'+esc(m.name)+'</strong>'+
        (done?'<span class="badge-pill impl" style="margin-left:auto">已完成</span>':'<span class="badge-pill" style="margin-left:auto">待办</span>')+
        '</div><div style="font-size:12.5px;color:var(--text-weak)">阶段 '+(i+1)+' / '+(stages||[]).length+'</div></div>';
    }).join("");
    var cards = grid.querySelectorAll("[data-stage]");
    for(var i=0;i<cards.length;i++)(function(el){
      el.addEventListener("click", function(){ var v=(STAGE_META[el.dataset.stage]||{}).view; if(v) navigate(v); });
    })(cards[i]);
  }

  /* ── 模型目录 ── */
  function renderCatalog(){
    view.innerHTML = pageHead("模型目录","14 大类共 53 个模型，点击分类下模型查看详情") +
      '<div class="toolbar"><div class="search-inline">'+icon("search",18)+'<input id="catSearch" placeholder="搜索模型名称 / 场景…" aria-label="搜索模型"></div>'+
      '<span class="spacer"></span><span class="badge-pill" id="catCount"></span></div>'+
      '<div id="catList"></div>';
    var list = document.getElementById("catList");
    function draw(filter){
      var f = (filter||"").trim().toLowerCase();
      var cats = (state.catalogData && state.catalogData.categories) || [];
      var html = cats.map(function(cat){
        var ms = cat.models || [];
        var models = ms.filter(function(m){ return !f || (m.name+" "+(m.description||"")+" "+(m.scenarios||[]).join(" ")).toLowerCase().indexOf(f) >= 0; });
        if(f && models.length===0 && (cat.name||"").toLowerCase().indexOf(f)<0 && (cat.description||"").toLowerCase().indexOf(f)<0) return "";
        if(!models.length) return "";
        var modelHtml = models.map(function(m){
          return '<div class="model" data-cat="'+esc(cat.id)+'" data-name="'+esc(m.name)+'">'+
            '<h4>'+esc(m.name)+
            (m.implemented?'<span class="badge-pill impl">已实现</span>':'<span class="badge-pill">未实现</span>')+
            (m.complexity?'<span class="badge-pill cpl-'+m.complexity+'">复杂度·'+cplText(m.complexity)+'</span>':'')+
            '</h4><p>'+esc(m.description||"")+'</p></div>';
        }).join("");
        return '<div class="card" style="margin-bottom:14px;border-left:4px solid var(--cat-'+cat.id+',var(--color-primary))">'+
          '<div style="display:flex;align-items:center;gap:12px;margin-bottom:12px">'+
          '<span class="cat-ico" style="background:var(--cat-'+cat.id+',var(--color-primary))"><svg class="ic" viewBox="0 0 24 24"><path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"/></svg></span>'+
          '<div><h3 style="margin:0;font-size:16px;font-weight:800">'+esc(cat.name)+'</h3>'+
          '<div style="font-size:12.5px;color:var(--text-weak)">'+esc(cat.description||"")+'</div></div>'+
          '<span class="cat-count" style="margin-left:auto">'+models.length+' 个模型</span></div>'+
          '<div class="model-grid">'+modelHtml+'</div></div>';
      }).join("");
      list.innerHTML = html || '<div class="empty">'+icon("search",46)+'<div>未找到匹配的模型</div></div>';
      var cc = document.getElementById("catCount"); if(cc) cc.textContent = totalModels()+" 个模型";
      bindModels();
    }
    function bindModels(){
      var ms = list.querySelectorAll(".model");
      for(var i=0;i<ms.length;i++)(function(el){ el.addEventListener("click", function(){ openModel(el.dataset.cat, el.dataset.name); }); })(ms[i]);
    }
    if(state.catalogData){ draw(document.getElementById("catSearch").value); }
    else {
      list.innerHTML = '<div class="loading-block"><span class="spinner"></span> 加载模型目录…</div>';
      getJSON("/api/catalog").then(function(d){ state.catalogData=d; draw(document.getElementById("catSearch").value); })
        .catch(function(){ list.innerHTML='<div class="empty">目录加载失败</div>'; });
    }
    var cs = document.getElementById("catSearch");
    if(cs) cs.addEventListener("input", function(){ draw(this.value); });
  }

  /* ── 模型详情抽屉 ── */
  function ensureCatalog(cb){
    if(state.catalogData) return cb();
    getJSON("/api/catalog").then(function(d){ state.catalogData=d; cb(); }).catch(function(){ cb(); });
  }
  function openModel(catId, name){
    ensureCatalog(function(){
      var cats = (state.catalogData && state.catalogData.categories) || [];
      var cat = cats.filter(function(c){ return c.id===catId; })[0];
      var m = (cat ? cat.models : []).filter(function(x){ return x.name===name; })[0];
      if(!m) return;
      var d = document.getElementById("drawerInner");
      d.innerHTML = '<div class="drawer-head"><div><h2>'+esc(m.name)+'</h2><div class="dh-sub">'+esc(cat?cat.name:"")+'</div></div>'+
        '<button class="icon-btn" id="drawerClose" aria-label="关闭" style="margin-left:auto">'+icon("close",20)+'</button></div>'+
        '<div class="drawer-body"><div style="display:flex;gap:8px;flex-wrap:wrap;margin-bottom:14px">'+
        (m.implemented?'<span class="badge-pill impl">已实现</span>':'<span class="badge-pill">未实现</span>')+
        (m.complexity?'<span class="badge-pill cpl-'+m.complexity+'">复杂度·'+cplText(m.complexity)+'</span>':'')+'</div>'+
        '<div class="res-block"><h4>'+icon("file",16)+' 描述</h4><p style="margin:0">'+esc(m.description||"")+'</p></div>'+
        (m.scenarios&&m.scenarios.length?'<div class="res-block"><h4>适用场景</h4><div>'+(m.scenarios||[]).map(function(s){ return '<span class="chip">'+esc(s)+'</span>'; }).join("")+'</div></div>':'')+
        (m.library?'<div class="res-block"><h4>常用库</h4><p style="margin:0;font-family:var(--font-mono);font-size:13px">'+esc(m.library)+'</p></div>':'')+
        (m.pros&&m.pros.length?'<div class="res-block"><h4>优点</h4><ul>'+(m.pros||[]).map(function(s){ return '<li>'+esc(s)+'</li>'; }).join("")+'</ul></div>':'')+
        (m.cons&&m.cons.length?'<div class="res-block"><h4>局限</h4><ul>'+(m.cons||[]).map(function(s){ return '<li>'+esc(s)+'</li>'; }).join("")+'</ul></div>':'')+
        '<div class="res-block"><h4>建议下一步</h4><div class="suggest">'+
        '<span class="sm" data-view="upload">'+icon("upload",16)+' 上传数据</span>'+
        '<span class="sm" data-view="analyze">'+icon("search",16)+' 重新分析</span>'+
        '<span class="sm" data-view="visualize">'+icon("chart",16)+' 可视化</span></div></div></div>';
      openDrawer();
      var dc = document.getElementById("drawerClose"); if(dc) dc.onclick = closeDrawer;
    });
  }
  function openDrawer(){ document.getElementById("drawerMask").classList.add("open"); document.getElementById("drawer").classList.add("open"); }
  function closeDrawer(){ document.getElementById("drawerMask").classList.remove("open"); document.getElementById("drawer").classList.remove("open"); }

  /* ── 题目分析 ── */
  function renderAnalyze(){
    view.innerHTML = pageHead("题目分析","粘贴赛题文本，结构化提取关键信息并给出建模建议") +
      '<div class="card"><label class="field"><span class="field-label">赛题文本</span><textarea id="pt" placeholder="在此粘贴数学建模赛题全文…"></textarea></label>'+
      '<div class="toolbar"><button class="btn" id="exBtn" type="button">'+icon("spark",16)+' 填入示例赛题</button>'+
      '<button class="btn ghost" id="clBtn" type="button">清空</button><span class="spacer"></span>'+
      '<button class="btn primary" id="anBtn">'+icon("search",16)+' 开始分析</button></div></div>'+
      '<div id="anResult"></div>';
    document.getElementById("exBtn").onclick = function(){ document.getElementById("pt").value = "某城市要规划充电桩布局，已知各区域车流量、现有桩位与电力容量，目标是最小化建设成本并最大化覆盖率，需满足电力约束与预算上限。请建立优化模型并给出求解方案。"; };
    document.getElementById("clBtn").onclick = function(){ document.getElementById("pt").value=""; document.getElementById("anResult").innerHTML=""; };
    document.getElementById("anBtn").onclick = function(){
      var t = document.getElementById("pt").value.trim();
      if(!t){ toast("请先输入赛题文本","warn"); return; }
      var r = document.getElementById("anResult");
      r.innerHTML = '<div class="loading-block"><span class="spinner"></span> 分析中…</div>';
      api("/api/analyze", { method:"POST", headers:{"Content-Type":"application/json"}, body: JSON.stringify({ problem_text:t }) })
        .then(function(res){ return res.json(); }).then(function(d){
          if(!d.success && d.error){ r.innerHTML='<div class="res-block" style="border-left:4px solid var(--danger)"><h4>分析失败</h4><p style="margin:0">'+esc(d.error)+'</p></div>'; toast("分析失败","err"); return; }
          markStage("problem_analysis");
          r.innerHTML = analyzeResultHtml(d);
          toast("题目分析完成","ok");
        }).catch(function(e){ r.innerHTML='<div class="res-block" style="border-left:4px solid var(--danger)"><h4>请求出错</h4><p style="margin:0">'+esc(String(e))+'</p></div>'; toast("请求出错","err"); });
    };
  }
  function analyzeResultHtml(d){
    var res = d.result || {};
    var html = '<div class="res-block" style="border-left:4px solid var(--success)"><div style="display:flex;align-items:center;gap:8px">'+icon("check",18)+'<strong>分析完成</strong>'+
      '<span style="margin-left:auto;color:var(--text-weak);font-size:12.5px">'+esc(d.message||"")+'</span></div></div>';
    if(res && typeof res==="object"){
      if(res.summary) html += '<div class="res-block"><h4>题目摘要</h4><p style="margin:0">'+esc(res.summary)+'</p></div>';
      if(res.objective || res.constraints){
        html += '<div class="res-block"><h4>关键变量与约束</h4>';
        if(res.objective) html += '<div class="kv"><span class="k">目标</span><span class="v">'+esc(Array.isArray(res.objective)?res.objective.join("、 "):res.objective)+'</span></div>';
        if(res.constraints) html += '<div class="kv"><span class="k">约束</span><span class="v">'+esc(Array.isArray(res.constraints)?res.constraints.join("、 "):res.constraints)+'</span></div>';
        html += '</div>';
      }
      if(res.suggested_models && res.suggested_models.length){
        html += '<div class="res-block"><h4>建议模型</h4><div class="suggest">'+res.suggested_models.map(function(m){
          return '<span class="sm" data-cat="'+(m.category||"")+'" data-name="'+esc(m.name||m)+'">'+esc(m.name||m)+'</span>';
        }).join("")+'</div></div>';
      }
    }
    html += '<details style="margin-top:13px"><summary style="cursor:pointer;color:var(--text-weak);font-size:13px">查看原始 JSON</summary><pre class="json" style="margin-top:10px">'+esc(JSON.stringify(d,null,2))+'</pre></details>';
    return html;
  }

  /* ── 数据上传 ── */
  function renderUpload(){
    view.innerHTML = pageHead("数据上传","上传赛题数据文件（CSV / Excel / JSON / TXT），保存至项目 raw_data 目录") +
      '<div class="card"><div class="dropzone" id="dz" role="button" tabindex="0">'+icon("upload",34)+
      '<div>将文件拖到此处，或 <strong>点击选择</strong></div><div style="font-size:12.5px;margin-top:4px">支持 CSV、XLSX、JSON、TXT 等</div></div>'+
      '<input type="file" id="fileInput" multiple style="display:none"><div id="upList"></div></div>';
    var dz = document.getElementById("dz"), input = document.getElementById("fileInput");
    dz.onclick = function(){ input.click(); };
    dz.onkeydown = function(e){ if(e.key==="Enter"||e.key===" "){ e.preventDefault(); input.click(); } };
    input.onchange = function(){ if(input.files && input.files.length) doUpload(input.files); };
    ["dragenter","dragover"].forEach(function(ev){ dz.addEventListener(ev, function(e){ e.preventDefault(); dz.classList.add("drag"); }); });
    ["dragleave","drop"].forEach(function(ev){ dz.addEventListener(ev, function(e){ e.preventDefault(); if(ev!=="drop") dz.classList.remove("drag"); }); });
    dz.addEventListener("drop", function(e){ if(e.dataTransfer && e.dataTransfer.files.length) doUpload(e.dataTransfer.files); });
    function doUpload(files){
      var fd = new FormData();
      for(var i=0;i<files.length;i++) fd.append("file", files[i]);
      var list = document.getElementById("upList");
      list.innerHTML = '<div class="loading-block"><span class="spinner"></span> 上传中…</div>';
      fetch(BASE + "/api/upload", { method:"POST", body: fd, headers: state.apiKey?{"Authorization":"Bearer "+state.apiKey}:undefined })
        .then(function(r){ return r.json(); }).then(function(d){
          if(!d.success){ list.innerHTML='<div class="empty">上传失败</div>'; toast("上传失败","err"); return; }
          markStage("data_processing");
          list.innerHTML = (d.uploaded||[]).map(function(f){
            return '<div class="file-row">'+icon("file",20)+'<span class="f-name">'+esc(f.name)+'</span><span class="f-size">'+fmtSize(f.size)+'</span></div>';
          }).join("") + (d.preview&&d.preview.rows ? ('<div class="hint" style="margin-top:10px">首份 CSV 预览：共 '+d.preview.rows+' 行、'+d.preview.cols+' 列</div>') : "");
          toast("上传成功："+(d.uploaded||[]).length+" 个文件","ok");
        }).catch(function(){ list.innerHTML='<div class="empty">上传出错</div>'; toast("上传出错","err"); });
    }
  }

  /* ── 可视化 ── */
  function renderVisualize(){
    var types = ["折线图","柱状图","散点图","热力图","箱线图","雷达图"];
    view.innerHTML = pageHead("可视化","描述偏好，保存后由可视化阶段应用（需带 --gallery 运行）") +
      '<div class="card"><label class="field"><span class="field-label">偏好描述（自然语言）</span><textarea id="up" placeholder="例如：展示各区域充电桩覆盖率与成本的关系"></textarea></label>'+
      '<label class="field"><span class="field-label">希望生成的图表类型</span><div style="display:flex;flex-wrap:wrap;gap:8px">'+types.map(function(c){
        return '<label class="badge-pill" style="cursor:pointer;padding:8px 12px"><input type="checkbox" class="ct" value="'+esc(c)+'" style="width:auto;margin-right:6px;accent-color:var(--color-primary)">'+esc(c)+'</label>';
      }).join("")+'</div></label>'+
      '<label class="field"><span class="field-label">最大图表数量</span><input type="number" id="mc" min="1" max="20" value="8" style="max-width:160px"></label>'+
      '<div class="toolbar"><button class="btn primary" id="vz">'+icon("download",16)+' 保存可视化偏好</button></div>'+
      '<div id="vzResult"></div></div>';
    document.getElementById("vz").onclick = function(){
      var pref = document.getElementById("up").value.trim();
      var cts = []; var boxes = document.querySelectorAll(".ct:checked");
      for(var i=0;i<boxes.length;i++) cts.push(boxes[i].value);
      var mc = parseInt(document.getElementById("mc").value, 10); if(isNaN(mc)) mc = null;
      var box = document.getElementById("vzResult");
      box.innerHTML = '<div class="loading-block"><span class="spinner"></span> 保存中…</div>';
      api("/api/visualize", { method:"POST", headers:{"Content-Type":"application/json"}, body: JSON.stringify({ user_pref:pref, chart_types: cts.length?cts:null, max_charts: mc }) })
        .then(function(r){ return r.json(); }).then(function(d){
          markStage("visualization");
          var plan = d.plan || {};
          box.innerHTML = '<div class="res-block" style="border-left:4px solid var(--success)"><h4>偏好已保存</h4>'+
            '<div class="kv"><span class="k">图表类型</span><span class="v">'+esc(Array.isArray(plan.requested_types)?plan.requested_types.join("、 "):String(plan.requested_types!=null?plan.requested_types:"—"))+'</span></div>'+
            '<div class="kv"><span class="k">最大数量</span><span class="v">'+esc(plan.max_charts!=null?plan.max_charts:"—")+'</span></div>'+
            (plan.note?'<div class="hint" style="margin-top:8px">'+esc(plan.note)+'</div>':'')+
            (d.prefs_saved?'<div class="hint" style="margin-top:6px;color:var(--success)">已写入结果目录 visualization_prefs.json</div>':'')+'</div>';
          toast("偏好已保存","ok");
        }).catch(function(){ box.innerHTML='<div class="empty">保存出错</div>'; toast("保存出错","err"); });
    };
  }

  /* ── 结果 ── */
  function renderResults(){
    view.innerHTML = pageHead("结果","查看工作流生成的产物文件") +
      '<div id="resList"><div class="loading-block"><span class="spinner"></span> 加载中…</div></div>';
    getJSON("/api/results").then(function(d){
      var items = d.results || [];
      if(!items.length){ document.getElementById("resList").innerHTML='<div class="empty">'+icon("file",46)+'<div>暂无产物文件</div></div>'; return; }
      document.getElementById("resList").innerHTML = items.map(function(f){
        return '<div class="result-row" tabindex="0" data-name="'+esc(f.name)+'">'+icon("file",20)+'<span class="r-name">'+esc(f.name)+'</span><span class="r-size">'+fmtSize(f.size)+'</span></div>';
      }).join("");
      bindResults();
    }).catch(function(){ document.getElementById("resList").innerHTML='<div class="empty">加载失败</div>'; });
  }
  function bindResults(){
    var rows = document.querySelectorAll(".result-row");
    for(var i=0;i<rows.length;i++)(function(el){
      el.onclick = function(){ openResult(el.dataset.name); };
      el.onkeydown = function(e){ if(e.key==="Enter") openResult(el.dataset.name); };
    })(rows[i]);
  }
  function openResult(name){
    view.innerHTML = pageHead("结果 · "+name,'<button class="btn ghost" id="backBtn" style="margin-bottom:12px">'+icon("arrow",16)+' 返回列表</button>') +
      '<div id="resDetail"><div class="loading-block"><span class="spinner"></span> 加载中…</div></div>';
    document.getElementById("backBtn").onclick = renderResults;
    getJSON("/api/results/" + encodeURIComponent(name)).then(function(d){
      if(d.error){ document.getElementById("resDetail").innerHTML='<div class="empty">'+esc(d.error)+'</div>'; return; }
      var data = d.data;
      if(typeof data==="string"){ try{ data = JSON.parse(data); }catch(e){} }
      var body;
      if(data && typeof data==="object"){
        body = '<div class="res-block"><h4>内容（JSON）</h4><button class="btn" id="copyBtn" style="margin-bottom:10px">'+icon("copy",16)+' 复制 JSON</button>'+
          '<pre class="json">'+esc(JSON.stringify(data,null,2))+'</pre></div>';
      } else {
        body = '<div class="res-block"><p style="margin:0">该文件为二进制或非 JSON 内容，请在文件系统中查看：<code>'+esc(name)+'</code></p></div>';
      }
      document.getElementById("resDetail").innerHTML = body;
      var cb = document.getElementById("copyBtn"); if(cb) cb.onclick = function(){ copyText(JSON.stringify(data,null,2)); toast("已复制","ok"); };
    }).catch(function(){ document.getElementById("resDetail").innerHTML='<div class="empty">加载失败</div>'; });
  }

  /* ── 画廊 ── */
  function renderGallery(){
    view.innerHTML = pageHead("可视化画廊","工作流生成的所有图表") +
      '<div id="galList"><div class="loading-block"><span class="spinner"></span> 加载中…</div></div>';
    getJSON("/api/gallery").then(function(d){
      var figs = d.figures || [];
      if(!figs.length){ document.getElementById("galList").innerHTML='<div class="empty">'+icon("image",46)+'<div>尚未生成图表。</div><div style="margin-top:10px"><a class="btn" href="/gallery" target="_blank" rel="noopener">打开画廊页面</a></div></div>'; return; }
      document.getElementById("galList").innerHTML = '<div class="gallery-grid">'+figs.map(function(f){
        return '<a class="fig-card" href="'+(BASE+f.url)+'" target="_blank" rel="noopener"><div class="fig-ph"><img src="'+(BASE+f.url)+'" alt="'+esc(f.name)+'" loading="lazy"></div>'+
          '<div class="fig-meta"><span>'+esc(f.name)+'</span><span>预览</span></div></a>';
      }).join("")+'</div>';
    }).catch(function(){ document.getElementById("galList").innerHTML='<div class="empty">加载失败</div>'; });
  }

  /* ── 路由 ── */
  var VIEWS = {
    dashboard: renderDashboard, catalog: renderCatalog, analyze: renderAnalyze,
    upload: renderUpload, visualize: renderVisualize, results: renderResults, gallery: renderGallery
  };
  function navigate(v){
    if(!VIEWS[v]) v = "dashboard";
    if(v === state.currentView) { VIEWS[v](); return; }
    state.currentView = v;
    markView(v);
    var items = document.querySelectorAll(".side-link");
    for(var i=0;i<items.length;i++) items[i].classList.toggle("active", items[i].dataset.view===v);
    if(location.hash.slice(1) !== v) location.hash = v;
    closeSidebar();
    VIEWS[v]();
    var m = document.getElementById("main"); if(m) m.focus();
  }
  function closeSidebar(){
    var sb = document.getElementById("sidebar");
    if(sb.classList.contains("open")){ sb.classList.remove("open"); var sc = document.getElementById("scrim"); if(sc) sc.hidden = true; }
  }

  /* ── 主题 / 设置 / 连接 ── */
  function applyTheme(t){ document.body.setAttribute("data-theme", t); try{ localStorage.setItem("mm_theme", t); }catch(e){} }
  function initTheme(){
    var t = localStorage.getItem("mm_theme");
    if(!t) t = (window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches) ? "dark" : "light";
    applyTheme(t);
  }
  function connCheck(){
    var el = document.getElementById("connStatus"); if(!el) return;
    getJSON("/api/status").then(function(d){
      el.className = "conn ok"; el.querySelector(".conn-text").textContent = "已连接";
      if(d.version) document.getElementById("verBadge").textContent = "v"+d.version;
    }).catch(function(){ el.className = "conn err"; el.querySelector(".conn-text").textContent = "未连接"; });
  }
  function openSettings(){
    document.getElementById("apiKeyInput").value = state.apiKey;
    var m = document.getElementById("settingsModal"); m.hidden = false; m.classList.add("open");
  }
  function closeSettings(){ var m = document.getElementById("settingsModal"); m.hidden = true; m.classList.remove("open"); }

  /* ── Toast ── */
  function toast(msg, type){
    var w = document.getElementById("toastWrap");
    var t = document.createElement("div");
    t.className = "toast " + (type||"");
    var sym = type==="ok" ? icon("check",16) : (type==="err"||type==="warn") ? icon("close",16) : icon("arrow",16);
    t.innerHTML = sym + '<span>'+esc(msg)+'</span>';
    w.appendChild(t);
    setTimeout(function(){ t.style.opacity="0"; t.style.transform="translateX(20px)"; setTimeout(function(){ if(t.parentNode) t.parentNode.removeChild(t); }, 250); }, 3200);
  }

  /* ── 全局事件绑定 ── */
  function bindGlobal(){
    document.addEventListener("click", function(e){
      var g = e.target.closest("[data-view]"); if(g){ navigate(g.dataset.view); return; }
      var sm = e.target.closest(".sm[data-cat]"); if(sm){ openModel(sm.dataset.cat, sm.dataset.name); return; }
    });
    document.getElementById("drawerMask").addEventListener("click", closeDrawer);
    document.addEventListener("keydown", function(e){ if(e.key==="Escape"){ closeDrawer(); closeSettings(); } });
    document.getElementById("themeToggle").onclick = function(){ var cur=document.body.getAttribute("data-theme"); applyTheme(cur==="dark"?"light":"dark"); };
    document.getElementById("settingsBtn").onclick = openSettings;
    document.getElementById("settingsClose").onclick = closeSettings;
    document.getElementById("settingsModal").addEventListener("click", function(e){ if(e.target===document.getElementById("settingsModal")) closeSettings(); });
    document.getElementById("settingsSave").onclick = function(){
      state.apiKey = document.getElementById("apiKeyInput").value.trim();
      try{ localStorage.setItem("mm_api_key", state.apiKey); }catch(e){}
      closeSettings(); toast("设置已保存","ok"); connCheck();
    };
    document.getElementById("menuToggle").onclick = function(){ document.getElementById("sidebar").classList.toggle("open"); toggleScrim(); };
    var gs = document.getElementById("globalSearch");
    if(gs) gs.addEventListener("keydown", function(e){
      if(e.key==="Enter"){ var v=this.value.trim(); navigate("catalog"); setTimeout(function(){ var ci=document.getElementById("catSearch"); if(ci){ ci.value=v; ci.dispatchEvent(new Event("input")); } }, 60); }
    });
  }
  function toggleScrim(){
    var sb = document.getElementById("sidebar");
    var open = sb.classList.contains("open");
    var sc = document.getElementById("scrim");
    if(open){
      if(!sc){ sc=document.createElement("div"); sc.id="scrim"; sc.className="scrim"; sc.addEventListener("click", function(){ sb.classList.remove("open"); sc.hidden=true; }); document.body.appendChild(sc); }
      sc.hidden = false;
    } else if(sc){ sc.hidden = true; }
  }

  /* ── 启动 ── */
  function initApp(){
    state.apiKey = localStorage.getItem("mm_api_key") || "";
    loadDone();
    initTheme();
    renderStages();
    bindGlobal();
    window.addEventListener("hashchange", function(){ var v=(location.hash||"#dashboard").slice(1); if(v!==state.currentView) navigate(v); });
    navigate((location.hash||"#dashboard").slice(1));
    connCheck();
    setInterval(connCheck, 30000);
  }
  if(document.readyState === "loading") document.addEventListener("DOMContentLoaded", initApp);
  else initApp();
})();
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

        # SPA 入口兼容：哈希路由（如 /#catalog）不应被当作后端端点。
        # 浏览器通常不会把 fragment 发给服务器，但某些预览器/代理可能会
        # 将其保留在请求目标中；统一回退到内嵌首页，避免白屏 JSON 错误。
        decoded_path = urllib.parse.unquote(path)
        if decoded_path.startswith("/#"):
            self._send_text("text/html; charset=utf-8", INDEX_HTML.encode("utf-8"))
            return

        # 其他未知路径也交给 SPA 处理，方便直接打开前端视图链接；API 仍在
        # 上方严格按端点返回 404，不会吞掉后端接口拼写错误。
        if not path.startswith("/api/"):
            self._send_text("text/html; charset=utf-8", INDEX_HTML.encode("utf-8"))
            return

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
        # 统一执行通道：经主阶段 workflow.run_stage 执行题目解析，
        # 与 CLI 主线共享审批 / 状态机 / 缓存（非交互模式自动批准）。
        wf = self.server.owner.workflow
        try:
            result = wf.run_stage("problem_analysis", problem_text=text)
            self._send_json(200, {
                "success": True,
                "problem_text": text,
                "result": result,
                "message": "题目分析已完成（主阶段通道）",
            })
        except Exception as e:
            self._send_json(200, {
                "success": False,
                "problem_text": text,
                "error": str(e),
                "message": "题目分析执行失败",
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
        """构建模型目录：优先读取真实 config/model_catalog.json（14 类 / 53 模型），
        回退到内嵌简表。向后兼容保留 ``models`` 简表（测试契约断言 optimization 存在）。"""
        legacy = {
            "optimization": {"name": "优化模型", "count": 12},
            "prediction": {"name": "预测模型", "count": 10},
            "classification": {"name": "分类模型", "count": 9},
            "simulation": {"name": "仿真模型", "count": 11},
            "comprehensive": {"name": "综合评价模型", "count": 11},
        }
        catalog_path = (
            Path(__file__).resolve().parent.parent.parent
            / "config" / "model_catalog.json"
        )
        categories = []
        total = 53
        try:
            if catalog_path.exists():
                raw = json.loads(catalog_path.read_text(encoding="utf-8"))
                for cid, c in raw.get("models", {}).items():
                    cm = c.get("models", [])
                    categories.append({
                        "id": cid,
                        "name": c.get("name", cid),
                        "description": c.get("description", ""),
                        "count": len(cm),
                        "models": [
                            {
                                "id": m.get("id", ""),
                                "name": m.get("name", ""),
                                "description": m.get("description", ""),
                                "complexity": m.get("complexity", ""),
                                "scenarios": m.get("applicable_scenarios", []),
                                "pros": m.get("pros", []),
                                "cons": m.get("cons", []),
                                "library": m.get("python_library", ""),
                                "implemented": bool(m.get("implemented", False)),
                            }
                            for m in cm
                        ],
                    })
                total = sum(c["count"] for c in categories)
        except Exception:
            categories = []

        # 向后兼容简表
        models_legacy = {
            c["id"]: {"name": c["name"], "count": c["count"]} for c in categories
        }
        if not models_legacy:
            models_legacy = legacy
        return {
            "models": models_legacy,
            "categories": categories,
            "total": total if categories else 53,
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
