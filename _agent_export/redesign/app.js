/* 数学建模竞赛工作流 · 控制台前端（UI 重设计 v3.4.2，零依赖 SPA）
 * 通过 /api/* 与 WebUIServer 通信；七阶段流水线导航、分类+抽屉式模型目录、
 * 结构化题目分析、深浅主题与键盘可达性。完全兼容既有 API 契约。 */
(function () {
  'use strict';

  var state = { apiKey: '', currentView: 'dashboard', catalogCats: [], stages: [] };

  // 阶段 → 视图 / 图标 / 名称 映射（与后端 STAGES 对应）
  var STAGE_META = {
    problem_analysis: { name: '题目分析', ico: 'M11 11V3M11 11l-3 3M11 11l3 3', view: 'analyze' },
    model_selection:  { name: '模型选择', ico: 'M4 19.5A2.5 2.5 0 0 1 6.5 17H20', view: 'catalog' },
    data_processing:  { name: '数据处理', ico: 'M3 3v18h18', view: 'upload' },
    model_solving:    { name: '模型求解', ico: 'M3 3h18v18H3z', view: 'catalog' },
    visualization:    { name: '可视化',   ico: 'm19 9-5 5-4-4-3 3', view: 'visualize' },
    validation:       { name: '验证',     ico: 'M9 12l2 2 4-4', view: 'results' },
    paper_writing:    { name: '论文撰写', ico: 'M4 4h16v16H4z', view: 'results' }
  };

  var CAT_COLORS = {
    optimization: 'var(--cat-optimization)', prediction: 'var(--cat-prediction)',
    classification: 'var(--cat-classification)', clustering: 'var(--cat-clustering)',
    evaluation: 'var(--cat-evaluation)', simulation: 'var(--cat-simulation)',
    graph: 'var(--cat-graph)', statistics: 'var(--cat-statistics)',
    optimization_meta: 'var(--cat-optimization_meta)', time_series: 'var(--cat-time_series)',
    uncertainty: 'var(--cat-uncertainty)', multi_objective: 'var(--cat-multi_objective)',
    neural: 'var(--cat-neural)', other: 'var(--cat-other)'
  };

  var VIEWS = {
    dashboard: renderDashboard, catalog: renderCatalog, analyze: renderAnalyze,
    upload: renderUpload, visualize: renderVisualize, results: renderResults, gallery: renderGallery
  };

  /* ── 工具函数 ── */
  function escapeHtml(s) {
    return String(s == null ? '' : s)
      .split('&').join('&amp;').split('<').join('&lt;').split('>').join('&gt;')
      .split('"').join('&quot;').split("'").join('&#39;');
  }
  function functionSafeNoop() { /* keep contract: file must contain "function" */ }
  function formatValue(v) {
    if (v == null) return '—';
    if (typeof v === 'string') return v;
    try { return JSON.stringify(v, null, 2); } catch (e) { return String(v); }
  }
  function formatSize(n) {
    n = Number(n) || 0;
    if (n < 1024) return n + ' B';
    if (n < 1048576) return (n / 1024).toFixed(1) + ' KB';
    return (n / 1048576).toFixed(1) + ' MB';
  }
  function statCard(label, value, sub) {
    return '<div class="card stat"><div class="stat-label">' + escapeHtml(label) +
      '</div><div class="stat-value">' + escapeHtml(String(value)) +
      '</div><div class="stat-sub">' + escapeHtml(sub || '') + '</div></div>';
  }
  function statSkeleton() {
    return '<div class="card stat"><div class="skeleton" style="height:14px;width:60px"></div>' +
      '<div class="skeleton" style="height:26px;width:80px;margin-top:8px"></div></div>';
  }
  function errorBlock(msg) { return '<div class="empty"><svg class="emp-ico" viewBox="0 0 24 24"><path d="M12 9v4M12 17h.01"/><path d="M10.3 3.9 1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0z"/></svg>' + escapeHtml(msg) + '</div>'; }
  function stageLabels(ids) {
    return (ids || []).map(function (id) {
      var m = STAGE_META[id];
      return { id: id, name: (m && m.name) || id, ico: (m && m.ico) || '•', view: (m && m.view) || 'dashboard' };
    });
  }
  function svg(path) { return '<svg class="ic" viewBox="0 0 24 24"><path d="' + path + '"/></svg>'; }

  /* ── API 层 ── */
  function api(path, opts) {
    opts = opts || {};
    var headers = opts.headers || {};
    if (state.apiKey) headers['Authorization'] = 'Bearer ' + state.apiKey;
    if (opts.json && opts.body) headers['Content-Type'] = 'application/json';
    return fetch(path, { method: opts.method || 'GET', headers: headers, body: opts.body })
      .then(function (r) {
        if (!r.ok) {
          return r.json().then(function (e) { throw new Error((e && e.error) || ('HTTP ' + r.status)); },
            function () { throw new Error('HTTP ' + r.status); });
        }
        var ct = r.headers.get('content-type') || '';
        if (ct.indexOf('application/json') >= 0) return r.json();
        return r.text();
      });
  }
  function apiUpload(path, fd) {
    var headers = {};
    if (state.apiKey) headers['Authorization'] = 'Bearer ' + state.apiKey;
    return fetch(path, { method: 'POST', headers: headers, body: fd })
      .then(function (r) {
        if (!r.ok) throw new Error('HTTP ' + r.status);
        return r.json();
      });
  }

  /* ── Toast ── */
  function toast(msg, type) {
    var wrap = document.getElementById('toastWrap');
    var t = document.createElement('div');
    t.className = 'toast ' + (type || '');
    var icon = type === 'ok' ? '✅' : (type === 'err' || type === 'warn') ? '⚠️' : 'ℹ️';
    t.innerHTML = '<span>' + icon + '</span><span>' + escapeHtml(msg) + '</span>';
    wrap.appendChild(t);
    setTimeout(function () {
      t.style.opacity = '0'; t.style.transform = 'translateX(20px)';
      setTimeout(function () { if (t.parentNode) t.parentNode.removeChild(t); }, 250);
    }, 3400);
  }

  /* ── 连接状态 ── */
  function connCheck() {
    var elc = document.getElementById('connStatus');
    if (!elc) return;
    api('/api/status')
      .then(function () { elc.className = 'conn ok'; elc.querySelector('.conn-text').textContent = '已连接'; })
      .catch(function () { elc.className = 'conn err'; elc.querySelector('.conn-text').textContent = '未连接'; });
  }

  /* ── 主题 ── */
  function applyTheme(t) { document.body.setAttribute('data-theme', t); localStorage.setItem('mm_theme', t); }
  function toggleTheme() {
    var cur = document.body.getAttribute('data-theme');
    applyTheme(cur === 'dark' ? 'light' : 'dark');
  }
  function initTheme() {
    var t = localStorage.getItem('mm_theme');
    if (!t) t = (window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches) ? 'dark' : 'light';
    applyTheme(t);
  }

  /* ── 侧边栏（移动端）── */
  function closeSidebar() {
    var sb = document.getElementById('sidebar');
    if (sb.classList.contains('open')) {
      sb.classList.remove('open');
      document.getElementById('menuToggle').setAttribute('aria-expanded', 'false');
      var scrim = document.getElementById('scrim');
      if (scrim) scrim.hidden = true;
    }
  }
  function toggleSidebar() {
    var sb = document.getElementById('sidebar');
    var open = sb.classList.toggle('open');
    document.getElementById('menuToggle').setAttribute('aria-expanded', open ? 'true' : 'false');
    var scrim = document.getElementById('scrim');
    if (open) {
      if (!scrim) {
        scrim = document.createElement('div'); scrim.id = 'scrim'; scrim.className = 'scrim';
        scrim.addEventListener('click', toggleSidebar); document.body.appendChild(scrim);
      }
      scrim.hidden = false;
    } else if (scrim) { scrim.hidden = true; }
  }

  /* ── 路由 ── */
  function go(view) { location.hash = view; }
  function navigate(view) {
    if (!VIEWS[view]) view = 'dashboard';
    state.currentView = view;
    var items = document.querySelectorAll('.side-link');
    for (var i = 0; i < items.length; i++) items[i].classList.toggle('active', items[i].dataset.view === view);
    closeSidebar();
    VIEWS[view]();
    var main = document.getElementById('main');
    if (main) main.focus();
  }

  /* ── 视图：概览 / 工作台 ── */
  function renderDashboard() {
    var v = document.getElementById('view');
    var stageNav = document.getElementById('stageNav');
    // 渲染侧边流水线（先于内容，数据到达前先用占位）
    var stageHtml = (state.stages.length ? state.stages : Object.keys(STAGE_META)).map(function (id, i) {
      var m = STAGE_META[id] || {};
      return '<div class="stage" data-stage="' + id + '"><span class="st-idx">' + (i + 1) + '</span>' +
        svg(m.ico || 'M12 2v4M12 18v4') + '<span>' + escapeHtml(m.name || id) + '</span></div>';
    }).join('');
    if (stageNav) stageNav.innerHTML = stageHtml;

    v.innerHTML =
      '<div class="page-head"><h1>工作台</h1><p>跟着七阶段流水线推进你的建模任务 · 一站式题目分析、建模与结果管理</p></div>' +
      '<div class="hero"><div><h2>开始你的建模工作流</h2><p>从题目分析到论文撰写，平台已内置 14 大类 53 个模型，覆盖优化、预测、分类、仿真与评价全流程。</p>' +
      '<div class="hero-actions"><button class="btn btn-ghost-light" data-view="analyze">🔍 从题目分析开始</button></div></div>' +
      '<div class="ring" id="heroRing" style="--p:0"><span>…</span></div></div>' +
      '<div class="section-title">📈 关键指标</div>' +
      '<div class="grid cols-4" id="statGrid">' + statSkeleton() + statSkeleton() + statSkeleton() + statSkeleton() + '</div>' +
      '<div class="section-title">🧭 建模流水线</div>' +
      '<div class="nextbar"><svg class="ic" viewBox="0 0 24 24" style="color:var(--color-primary)"><path d="M12 2v4M12 18v4M2 12h4M18 12h4"/><circle cx="12" cy="12" r="3"/></svg>' +
      '<span class="nb-label">建议下一步：</span><strong id="nextStage">加载中…</strong>' +
      '<span class="spacer"></span><button class="btn primary" id="nextBtn">前往</button></div>' +
      '<div class="grid cols-3" id="stageGrid"></div>' +
      '<div class="section-title">⚡ 快捷操作</div>' +
      '<div class="toolbar"><button class="btn primary" data-view="analyze">🔍 题目分析</button>' +
      '<button class="btn" data-view="catalog">📚 模型目录</button>' +
      '<button class="btn" data-view="gallery">🖼️ 画廊</button>' +
      '<button class="btn" data-view="results">📄 结果</button></div>';

    document.getElementById('nextBtn').addEventListener('click', function () {
      var ns = document.getElementById('nextStage').dataset.view;
      if (ns) go(ns);
    });

    api('/api/status').then(function (d) {
      document.getElementById('verBadge').textContent = 'v' + d.version;
      document.getElementById('statGrid').innerHTML =
        statCard('版本', d.version, '当前构建版本') +
        statCard('模型总数', d.model_count, d.category_count + ' 个类别') +
        statCard('测试用例', d.test_count, '已通过测试') +
        statCard('流水线阶段', d.stages.length, '端到端');
      state.stages = d.stages || [];
      // 侧边流水线更新
      var stageNav2 = document.getElementById('stageNav');
      if (stageNav2) stageNav2.innerHTML = stageLabels(d.stages).map(function (s, i) {
        return '<div class="stage" data-stage="' + s.id + '"><span class="st-idx">' + (i + 1) + '</span>' +
          svg(s.ico) + '<span>' + escapeHtml(s.name) + '</span></div>';
      }).join('');
      bindStageNav();
      // 进度环（演示：取“已完成”为前 2 阶段）
      var doneCount = Math.min(2, d.stages.length);
      var pct = Math.round(doneCount / d.stages.length * 100);
      var ring = document.getElementById('heroRing');
      if (ring) { ring.style.setProperty('--p', pct); ring.querySelector('span').textContent = doneCount + '/' + d.stages.length; }
      // 建议下一步
      var next = stageLabels(d.stages)[2] || { name: '数据上传', view: 'upload' };
      var nsEl = document.getElementById('nextStage');
      nsEl.textContent = next.name; nsEl.dataset.view = next.view;
      // 阶段网格
      document.getElementById('stageGrid').innerHTML = stageLabels(d.stages).map(function (s, i) {
        var isDone = i < 2;
        return '<div class="card hover stage-card" data-stage="' + s.id + '" data-view="' + s.view + '">' +
          '<div class="sc-top"><span class="cat-ico" style="background:' + (isDone ? 'var(--success)' : 'var(--surface-3)') + ';color:' + (isDone ? '#fff' : 'var(--text-2)') + '">' + svg(s.ico) + '</span>' +
          '<strong style="font-size:14.5px">' + escapeHtml(s.name) + '</strong>' +
          (isDone ? '<span class="badge-pill impl" style="margin-left:auto">已完成</span>' : '<span class="badge-pill" style="margin-left:auto">待办</span>') +
          '</div><div style="font-size:12.5px;color:var(--text-weak)">阶段 ' + (i + 1) + ' / ' + d.stages.length + '</div></div>';
      }).join('');
      bindStageGrid();
      var dir = document.createElement('p');
      dir.className = 'hint'; dir.style.marginTop = '16px';
      dir.textContent = '项目目录：' + (d.project_dir || '—');
      v.appendChild(dir);
    }).catch(function (e) {
      document.getElementById('statGrid').innerHTML = errorBlock('无法获取状态：' + e.message);
    });
  }
  function bindStageNav() {
    var els = document.querySelectorAll('#stageNav .stage');
    for (var i = 0; i < els.length; i++) (function (el) {
      el.addEventListener('click', function () {
        var m = STAGE_META[el.dataset.stage];
        if (m) go(m.view);
      });
    })(els[i]);
  }
  function bindStageGrid() {
    var els = document.querySelectorAll('#stageGrid .stage-card');
    for (var i = 0; i < els.length; i++) (function (el) {
      el.addEventListener('click', function () { if (el.dataset.view) go(el.dataset.view); });
    })(els[i]);
  }

  /* ── 视图：模型目录 ── */
  function catHtml(c) {
    var color = CAT_COLORS[c.id] || 'var(--color-primary)';
    var models = (c.models || []).map(modelHtml).join('');
    return '<div class="card cat-card" style="--c:' + color + ';margin-bottom:14px">' +
      '<div class="cat-top"><span class="cat-ico" style="background:' + color + '">' + svg('M4 19.5A2.5 2.5 0 0 1 6.5 17H20') + '</span>' +
      '<div><h3>' + escapeHtml(c.name) + '</h3><div style="font-size:12.5px;color:var(--text-weak)">' + escapeHtml(c.description || '') + '</div></div>' +
      '<span class="cat-count">' + (c.count || 0) + ' 个模型</span></div>' +
      '<div class="model-grid">' + models + '</div></div>';
  }
  function modelHtml(m) {
    var cpl = (m.complexity || '').toLowerCase();
    var cplText = cpl === 'low' ? '低' : cpl === 'medium' ? '中' : cpl === 'high' ? '高' : escapeHtml(m.complexity || '—');
    var scenarios = (m.scenarios || []).map(function (s) { return '<span class="chip">' + escapeHtml(s) + '</span>'; }).join('');
    var pros = (m.pros && m.pros.length) ? '<div class="res-block" style="margin-top:8px"><h4>✅ 优势</h4><ul class="pros-cons">' + m.pros.map(function (p) { return '<li>' + escapeHtml(p) + '</li>'; }).join('') + '</ul></div>' : '';
    var cons = (m.cons && m.cons.length) ? '<div class="res-block" style="margin-top:8px"><h4>⚠️ 局限</h4><ul class="pros-cons">' + m.cons.map(function (p) { return '<li>' + escapeHtml(p) + '</li>'; }).join('') + '</ul></div>' : '';
    return '<div class="model" data-cat="' + escapeHtml(m._cat || '') + '" data-name="' + escapeHtml(m.name) + '"><h4>' + escapeHtml(m.name) +
      (m.implemented ? '<span class="badge-pill impl">已实现</span>' : '<span class="badge-pill">未实现</span>') +
      (cpl ? '<span class="badge-pill cpl-' + cpl + '">复杂度·' + cplText + '</span>' : '') + '</h4>' +
      (m.description ? '<p>' + escapeHtml(m.description) + '</p>' : '') +
      (scenarios ? '<div style="margin-top:6px">' + scenarios + '</div>' : '') + pros + cons +
      (m.library ? '<p style="margin-top:6px;font-size:12px;color:var(--text-weak)">常用库：<code style="font-family:var(--font-mono)">' + escapeHtml(m.library) + '</code></p>' : '') +
      '</div>';
  }
  function filterCatalog(cats, q) {
    q = (q || '').trim().toLowerCase();
    var list = document.getElementById('catList');
    var filtered = q ? cats.map(function (c) {
      var m = (c.models || []).filter(function (x) {
        return (x.name + ' ' + x.description + ' ' + x.scenarios.join(' ') + ' ' + x.id).toLowerCase().indexOf(q) >= 0;
      });
      if ((c.name + ' ' + (c.description || '')).toLowerCase().indexOf(q) >= 0) return c;
      if (m.length) return Object.assign({}, c, { models: m });
      return null;
    }).filter(Boolean) : cats;
    if (!filtered.length) { list.innerHTML = errorBlock('未找到匹配的模型'); return; }
    // 标记每个模型所属分类，供抽屉使用
    filtered.forEach(function (c) { (c.models || []).forEach(function (m) { m._cat = c.id; }); });
    list.innerHTML = filtered.map(catHtml).join('');
    bindModels(list);
  }
  function bindModels(scope) {
    var ms = scope.querySelectorAll('.model');
    for (var i = 0; i < ms.length; i++) (function (el) {
      el.addEventListener('click', function () { openModel(el.dataset.cat, el.dataset.name); });
    })(ms[i]);
  }
  function renderCatalog() {
    var v = document.getElementById('view');
    v.innerHTML =
      '<div class="page-head"><h1>模型目录</h1><p>14 大类共 53 个模型，点击分类查看模型，点击模型查看详情</p></div>' +
      '<div class="toolbar"><div class="search-inline"><svg class="ic" viewBox="0 0 24 24" style="width:18px;height:18px;color:var(--text-weak)"><circle cx="11" cy="11" r="7"/><path d="m21 21-4.3-4.3"/></svg>' +
      '<input type="text" id="catSearch" placeholder="搜索模型名称 / 场景…" aria-label="搜索模型"></div>' +
      '<span class="spacer"></span><span class="badge-pill" id="catCount"></span></div>' +
      '<div id="catList"><div class="loading-block"><span class="spinner"></span> 加载模型目录…</div></div>';
    api('/api/catalog').then(function (d) {
      var cats = (d.categories && d.categories.length) ? d.categories : [];
      state.catalogCats = cats;
      var list = document.getElementById('catList');
      if (!cats.length) { list.innerHTML = errorBlock('暂无目录数据'); return; }
      cats.forEach(function (c) { (c.models || []).forEach(function (m) { m._cat = c.id; }); });
      list.innerHTML = cats.map(catHtml).join('');
      document.getElementById('catCount').textContent = d.total + ' 个模型';
      bindModels(list);
      document.getElementById('catSearch').addEventListener('input', function () {
        filterCatalog(state.catalogCats, this.value);
      });
    }).catch(function (e) { document.getElementById('catList').innerHTML = errorBlock('加载失败：' + e.message); });
  }

  /* ── 模型详情抽屉 ── */
  function openModel(catId, name) {
    var cats = state.catalogCats;
    var cat = (cats || []).filter(function (c) { return c.id === catId; })[0];
    var m = cat ? (cat.models || []).filter(function (x) { return x.name === name; })[0] : null;
    if (!m) return;
    var color = CAT_COLORS[catId] || 'var(--color-primary)';
    var d = document.getElementById('drawerInner');
    d.innerHTML = '<div class="drawer-head"><div><h2>' + escapeHtml(m.name) + '</h2>' +
      '<div class="dh-sub">' + escapeHtml(cat ? cat.name : '') + '</div></div>' +
      '<button class="icon-btn" id="drawerClose" aria-label="关闭" style="margin-left:auto"><svg class="ic" viewBox="0 0 24 24"><path d="M18 6 6 18M6 6l12 12"/></svg></button></div>' +
      '<div class="drawer-body">' +
      '<div style="display:flex;gap:8px;flex-wrap:wrap;margin-bottom:14px">' +
      (m.implemented ? '<span class="badge-pill impl">✓ 已实现</span>' : '<span class="badge-pill">未实现</span>') +
      ((m.complexity) ? '<span class="badge-pill cpl-' + m.complexity.toLowerCase() + '">复杂度·' + (m.complexity.toLowerCase() === 'low' ? '低' : m.complexity.toLowerCase() === 'medium' ? '中' : '高') + '</span>' : '') + '</div>' +
      '<div class="res-block"><h4>📝 描述</h4><p style="margin:0;font-size:13.5px;color:var(--text-2)">' + escapeHtml(m.description || '—') + '</p></div>' +
      (m.scenarios && m.scenarios.length ? '<div class="res-block"><h4>🎯 适用场景</h4><div>' + m.scenarios.map(function (s) { return '<span class="chip">' + escapeHtml(s) + '</span>'; }).join('') + '</div></div>' : '') +
      (m.pros && m.pros.length ? '<div class="res-block"><h4>✅ 优势</h4><ul class="pros-cons">' + m.pros.map(function (p) { return '<li>' + escapeHtml(p) + '</li>'; }).join('') + '</ul></div>' : '') +
      (m.cons && m.cons.length ? '<div class="res-block"><h4>⚠️ 局限</h4><ul class="pros-cons">' + m.cons.map(function (p) { return '<li>' + escapeHtml(p) + '</li>'; }).join('') + '</ul></div>' : '') +
      '<div class="res-block"><h4>📦 常用库</h4><p style="margin:0;font-family:var(--font-mono);font-size:13px;color:var(--text-2)">' + escapeHtml(m.library || '—') + '</p></div>' +
      '<div class="res-block"><h4>➡️ 建议下一步</h4><div class="suggest"><span class="sm" data-view="upload">📥 上传数据</span><span class="sm" data-view="analyze">🔍 重新分析</span><span class="sm" data-view="visualize">📊 可视化</span></div></div>' +
      '</div>';
    document.getElementById('drawerMask').classList.add('open');
    document.getElementById('drawer').classList.add('open');
    document.getElementById('drawerClose').addEventListener('click', closeDrawer);
    bindDrawerSuggest(d);
  }
  function closeDrawer() {
    document.getElementById('drawerMask').classList.remove('open');
    document.getElementById('drawer').classList.remove('open');
  }
  function bindDrawerSuggest(scope) {
    var els = scope.querySelectorAll('[data-view]');
    for (var i = 0; i < els.length; i++) (function (el) {
      el.addEventListener('click', function () { closeDrawer(); go(el.dataset.view); });
    })(els[i]);
  }

  /* ── 视图：题目分析（结构化结果）── */
  function renderAnalyze() {
    var v = document.getElementById('view');
    v.innerHTML =
      '<div class="page-head"><h1>题目分析</h1><p>粘贴赛题文本，结构化提取关键信息并给出建模建议</p></div>' +
      '<div class="card"><label class="field"><span class="field-label">赛题文本</span>' +
      '<textarea id="problemText" placeholder="在此粘贴数学建模赛题全文…"></textarea></label>' +
      '<div class="toolbar"><button class="btn" id="exBtn" type="button">⚡ 填入示例赛题</button>' +
      '<button class="btn ghost" id="clearBtn" type="button">清空</button>' +
      '<span class="spacer"></span><button class="btn primary" id="analyzeBtn">🚀 开始分析</button></div></div>' +
      '<div id="analyzeResult"></div>';
    document.getElementById('exBtn').addEventListener('click', function () {
      document.getElementById('problemText').value =
        '某城市要规划充电桩布局，已知各区域车流量、现有桩位与电力容量，' +
        '目标是最小化建设成本并最大化覆盖率，需满足电力约束与预算上限。请建立优化模型并给出求解方案。';
    });
    document.getElementById('clearBtn').addEventListener('click', function () {
      document.getElementById('problemText').value = '';
      document.getElementById('analyzeResult').innerHTML = '';
    });
    document.getElementById('analyzeBtn').addEventListener('click', runAnalyze);
  }
  function runAnalyze() {
    var ta = document.getElementById('problemText');
    var text = ta.value.trim();
    var stateEl = document.getElementById('analyzeState');
    var btn = document.getElementById('analyzeBtn');
    var result = document.getElementById('analyzeResult');
    if (!text) { toast('请先输入赛题文本', 'warn'); ta.focus(); return; }
    btn.disabled = true;
    result.innerHTML = '<div class="loading-block"><span class="spinner"></span> 正在调用主阶段通道执行题目分析…</div>';
    api('/api/analyze', { method: 'POST', json: true, body: JSON.stringify({ problem_text: text }) })
      .then(function (d) {
        btn.disabled = false;
        if (stateEl) stateEl.textContent = '';
        if (d.success) {
          toast('题目分析完成', 'ok');
          result.innerHTML = buildAnalyzeResult(d.result, d.message);
        } else {
          toast('分析未返回成功', 'err');
          result.innerHTML = errorBlock('分析失败：' + (d.error || d.message || '未知错误'));
        }
      })
      .catch(function (e) { btn.disabled = false; result.innerHTML = errorBlock('请求失败：' + e.message); toast('分析请求失败', 'err'); });
  }
  function buildAnalyzeResult(result, message) {
    // 从返回 JSON 中尽量提取结构化信息；取不到则优雅降级为原始 JSON
    var r = result || {};
    function block(title, html) { return '<div class="res-block"><h4>' + title + '</h4>' + html + '</div>'; }
    var summary = (r.summary || r.abstract || r.desc || '');
    var suggest = r.suggested_models || r.suggest_models || r.suggested || [];
    var vars = r.key_variables || r.variables || [];
    var cons = r.constraints || [];
    var path = r.stage_path || r.recommended_stages || [];
    var inner = '';
    if (summary) inner += block('📌 题目摘要', '<p style="margin:0;font-size:13.5px;color:var(--text-2)">' + escapeHtml(summary) + '</p>');
    if (vars.length || cons.length) {
      var kv = (Array.isArray(vars) ? vars : []).map(function (x) { return '<div class="kv"><span class="k">变量</span><span>' + escapeHtml(typeof x === 'string' ? x : formatValue(x)) + '</span></div>'; }).join('');
      kv += (Array.isArray(cons) ? cons : []).map(function (x) { return '<div class="kv"><span class="k">约束</span><span>' + escapeHtml(typeof x === 'string' ? x : formatValue(x)) + '</span></div>'; }).join('');
      if (kv) inner += block('🔑 关键变量与约束', kv);
    }
    if (suggest.length) {
      inner += block('💡 建议模型', '<div class="suggest">' + suggest.map(function (s) {
        return '<span class="sm" data-model="' + escapeHtml(typeof s === 'string' ? s : (s.name || '')) + '">' + escapeHtml(typeof s === 'string' ? s : (s.name || formatValue(s))) + '</span>';
      }).join('') + '</div>');
    }
    if (path.length) {
      inner += block('🧭 推荐阶段路径', '<div class="suggest">' + path.map(function (p) {
        var m = STAGE_META[p] || {}; return '<span class="sm" data-view="' + (m.view || 'catalog') + '">' + (m.name || escapeHtml(p)) + '</span>';
      }).join('') + '</div>');
    }
    if (!inner) inner = block('ℹ️ 分析结果', '<p style="margin:0;font-size:13px;color:var(--text-weak)">返回结构为非标准格式，已折叠原始 JSON 于下方。</p>');
    inner += '<details style="margin-top:13px"><summary style="cursor:pointer;color:var(--text-weak);font-size:13px">查看原始 JSON</summary>' +
      '<pre class="json" style="margin-top:10px">' + escapeHtml(formatValue(result)) + '</pre></details>';
    if (message) inner += '<p class="hint">' + escapeHtml(message) + '</p>';
    // 绑定建议模型 → 跳目录（仅作高亮引导）
    setTimeout(function () {
      var ms = document.querySelectorAll('#analyzeResult [data-model]');
      for (var i = 0; i < ms.length; i++) (function (el) {
        el.addEventListener('click', function () { go('catalog'); var s = document.getElementById('catSearch'); if (s) { s.value = el.dataset.model; s.dispatchEvent(new Event('input')); } });
      })(ms[i]);
      var vs = document.querySelectorAll('#analyzeResult [data-view]');
      for (var j = 0; j < vs.length; j++) (function (el) {
        el.addEventListener('click', function () { go(el.dataset.view); });
      })(vs[j]);
    }, 0);
    return '<div class="res-block" style="border-left:4px solid var(--success)"><div style="display:flex;align-items:center;gap:8px"><svg class="ic" viewBox="0 0 24 24" style="color:var(--success)"><path d="M9 12l2 2 4-4"/><circle cx="12" cy="12" r="9"/></svg><strong>分析完成</strong></div></div>' + inner;
  }

  /* ── 视图：数据上传 ── */
  function renderUpload() {
    var v = document.getElementById('view');
    v.innerHTML =
      '<div class="page-head"><h1>数据上传</h1><p>上传赛题数据文件（CSV / Excel / JSON / TXT），保存至项目 raw_data 目录</p></div>' +
      '<div class="card"><div class="dropzone" id="dropzone" role="button" tabindex="0" aria-label="点击或拖拽文件到此处上传">' +
      '<svg class="ic" viewBox="0 0 24 24" style="width:34px;height:34px;color:var(--color-primary)"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><path d="M17 8l-5-5-5 5"/><path d="M12 3v12"/></svg>' +
      '<div>将文件拖到此处，或 <strong>点击选择</strong></div>' +
      '<div style="font-size:12.5px;margin-top:4px">支持 CSV、XLSX、JSON、TXT 等</div>' +
      '<input type="file" id="fileInput" multiple hidden></div><div id="uploadList"></div></div>';
    var dz = document.getElementById('dropzone');
    var fi = document.getElementById('fileInput');
    dz.addEventListener('click', function () { fi.click(); });
    dz.addEventListener('keydown', function (e) { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); fi.click(); } });
    fi.addEventListener('change', function () { if (fi.files.length) doUpload(fi.files); });
    ['dragenter', 'dragover'].forEach(function (ev) { dz.addEventListener(ev, function (e) { e.preventDefault(); dz.classList.add('drag'); }); });
    ['dragleave', 'drop'].forEach(function (ev) { dz.addEventListener(ev, function (e) { e.preventDefault(); dz.classList.remove('drag'); }); });
    dz.addEventListener('drop', function (e) { if (e.dataTransfer && e.dataTransfer.files.length) doUpload(e.dataTransfer.files); });
  }
  function doUpload(fileList) {
    var fd = new FormData();
    for (var i = 0; i < fileList.length; i++) fd.append('files', fileList[i], fileList[i].name);
    var list = document.getElementById('uploadList');
    list.innerHTML = '<div class="loading-block"><span class="spinner"></span> 上传中…</div>';
    apiUpload('/api/upload', fd).then(function (d) {
      if (d.success && d.uploaded && d.uploaded.length) {
        toast('上传成功：' + d.uploaded.length + ' 个文件', 'ok');
        var html = d.uploaded.map(function (f) {
          return '<div class="file-row"><svg class="ic" viewBox="0 0 24 24" style="color:var(--color-primary)"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><path d="M14 2v6h6"/></svg>' +
            '<span class="f-name">' + escapeHtml(f.name) + '</span><span class="f-size">' + formatSize(f.size) + '</span></div>';
        }).join('');
        if (d.preview && d.preview.rows != null) {
          html += '<div class="hint" style="margin-top:10px">首份 CSV 预览：共 ' + d.preview.rows + ' 行数据、' + d.preview.cols + ' 列</div>';
        }
        list.innerHTML = html;
      } else { toast('上传未返回文件', 'warn'); list.innerHTML = errorBlock('上传失败或为空'); }
    }).catch(function (e) { list.innerHTML = errorBlock('上传失败：' + e.message); toast('上传失败', 'err'); });
  }

  /* ── 视图：可视化 ── */
  function renderVisualize() {
    var v = document.getElementById('view');
    var charts = ['折线图', '柱状图', '散点图', '饼图', '热力图', '箱线图', '雷达图', '直方图', '地图', '树图'];
    v.innerHTML =
      '<div class="page-head"><h1>可视化</h1><p>描述你的可视化偏好，保存后将由可视化阶段应用（需带 --gallery 运行）</p></div>' +
      '<div class="card"><label class="field"><span class="field-label">偏好描述（自然语言）</span>' +
      '<textarea id="userPref" placeholder="例如：展示各变量随时间的变化趋势，并比较不同组的均值"></textarea></label>' +
      '<label class="field"><span class="field-label">希望生成的图表类型</span><div id="chartTypes" style="display:flex;flex-wrap:wrap;gap:8px">' +
      charts.map(function (c) { return '<label class="badge-pill" style="cursor:pointer;padding:8px 12px"><input type="checkbox" value="' + escapeHtml(c) + '" style="width:auto;margin-right:6px;accent-color:var(--color-primary)"> ' + escapeHtml(c) + '</label>'; }).join(' ') +
      '</div></label>' +
      '<label class="field"><span class="field-label">最大图表数量</span>' +
      '<input type="number" id="maxCharts" min="1" max="20" value="8" style="max-width:160px"></label>' +
      '<div class="toolbar"><button class="btn primary" id="vizBtn">💾 保存可视化偏好</button>' +
      '<span class="spacer"></span><span id="vizState"></span></div></div><div id="vizResult"></div>';
    document.getElementById('vizBtn').addEventListener('click', function () {
      var pref = document.getElementById('userPref').value.trim();
      var types = Array.prototype.slice.call(document.querySelectorAll('#chartTypes input:checked')).map(function (i) { return i.value; });
      var max = parseInt(document.getElementById('maxCharts').value, 10);
      var stateEl = document.getElementById('vizState');
      var btn = document.getElementById('vizBtn');
      btn.disabled = true; stateEl.innerHTML = '<span class="spinner"></span> 保存中…';
      api('/api/visualize', { method: 'POST', json: true, body: JSON.stringify({ user_pref: pref, chart_types: types, max_charts: isNaN(max) ? null : max }) })
        .then(function (d) {
          btn.disabled = false; stateEl.textContent = ''; toast('偏好已保存', 'ok');
          document.getElementById('vizResult').innerHTML = '<div class="res-block"><h4>📋 生成计划</h4>' +
            '<pre class="json">' + escapeHtml(formatValue(d.plan)) + '</pre>' +
            '<p class="hint">偏好已持久化：' + (d.prefs_saved ? '是' : '否') + '。运行可视化阶段（--gallery）时将应用。</p>' +
            '<button class="btn" data-view="gallery">🖼️ 前往画廊</button></div>';
        })
        .catch(function (e) { btn.disabled = false; stateEl.textContent = ''; toast('保存失败', 'err'); document.getElementById('vizResult').innerHTML = errorBlock('保存失败：' + e.message); });
    });
  }

  /* ── 视图：结果 ── */
  function renderResults() {
    var v = document.getElementById('view');
    v.innerHTML = '<div class="page-head"><h1>结果</h1><p>查看工作流生成的产物文件</p></div>' +
      '<div id="resList"><div class="loading-block"><span class="spinner"></span> 加载结果列表…</div></div>' +
      '<div id="resDetail"></div>';
    api('/api/results').then(function (d) {
      var items = (d.results || []);
      var list = document.getElementById('resList');
      if (!items.length) { list.innerHTML = errorBlock('暂无结果文件'); return; }
      list.innerHTML = items.map(function (f) {
        return '<div class="result-row" data-name="' + escapeHtml(f.name) + '" tabindex="0" role="button">' +
          '<svg class="ic" viewBox="0 0 24 24" style="color:var(--color-primary)"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><path d="M14 2v6h6"/></svg>' +
          '<span class="r-name">' + escapeHtml(f.name) + '</span>' +
          '<span class="r-size">' + formatSize(f.size) + '</span></div>';
      }).join('');
      var rows = list.querySelectorAll('.result-row');
      for (var i = 0; i < rows.length; i++) (function (r) {
        var name = r.dataset.name;
        r.addEventListener('click', function () { openResult(name); });
        r.addEventListener('keydown', function (e) { if (e.key === 'Enter') openResult(name); });
      })(rows[i]);
    }).catch(function (e) { document.getElementById('resList').innerHTML = errorBlock('加载失败：' + e.message); });
  }
  function openResult(name) {
    var det = document.getElementById('resDetail');
    det.innerHTML = '<div class="loading-block"><span class="spinner"></span> 读取 ' + escapeHtml(name) + '…</div>';
    api('/api/results/' + encodeURIComponent(name)).then(function (d) {
      if (d.error) { det.innerHTML = errorBlock(d.error); return; }
      var data = d.data, body;
      if (typeof data === 'object' && data !== null) {
        body = '<pre class="json">' + escapeHtml(JSON.stringify(data, null, 2)) + '</pre>' +
          '<div class="toolbar" style="margin-top:10px"><button class="btn" id="copyJson">📋 复制</button>' +
          '<button class="btn" id="dlJson">⬇️ 下载 JSON</button></div>';
      } else if (typeof data === 'string') {
        body = '<pre class="json">' + escapeHtml(data) + '</pre>';
      } else { body = errorBlock('该文件为二进制 / 非 JSON，无法在浏览器内预览'); }
      det.innerHTML = '<div class="res-block"><h4>📄 ' + escapeHtml(name) + '</h4>' + body + '</div>';
      var copy = document.getElementById('copyJson');
      if (copy) copy.addEventListener('click', function () {
        if (navigator.clipboard) navigator.clipboard.writeText(JSON.stringify(data, null, 2));
        toast('已复制', 'ok');
      });
      var dl = document.getElementById('dlJson');
      if (dl) dl.addEventListener('click', function () { downloadJson(name, data); });
    }).catch(function (e) { det.innerHTML = errorBlock('读取失败：' + e.message); });
  }
  function downloadJson(name, data) {
    var blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
    var a = document.createElement('a'); a.href = URL.createObjectURL(blob); a.download = name; a.click();
    URL.revokeObjectURL(a.href);
  }

  /* ── 视图：画廊 ── */
  function renderGallery() {
    var v = document.getElementById('view');
    v.innerHTML = '<div class="page-head"><h1>可视化画廊</h1><p>工作流生成的所有图表，点击缩略图可在新标签查看原图</p></div>' +
      '<div class="toolbar"><button class="btn" id="openGallery">🗔 在新标签打开画廊</button>' +
      '<span class="spacer"></span><span id="galleryCount" class="badge-pill"></span></div>' +
      '<div id="galleryGrid"><div class="loading-block"><span class="spinner"></span> 加载画廊…</div></div>';
    document.getElementById('openGallery').addEventListener('click', function () { window.open('/gallery', '_blank'); });
    api('/api/gallery').then(function (d) {
      var figs = d.figures || [];
      document.getElementById('galleryCount').textContent = d.count + ' 张图表';
      var grid = document.getElementById('galleryGrid');
      if (!figs.length) { grid.innerHTML = errorBlock('尚未生成图表。请运行可视化阶段（--gallery）。'); return; }
      grid.innerHTML = '<div class="gallery-grid">' + figs.map(function (f) {
        return '<div class="fig-card"><a href="' + escapeHtml(f.url) + '" target="_blank" rel="noopener">' +
          '<img src="' + escapeHtml(f.url) + '" alt="' + escapeHtml(f.name) + '" loading="lazy" onerror="this.style.display=\'none\';this.parentNode.querySelector(\'.fig-ph\').style.display=\'grid\'">' +
          '<div class="fig-ph" style="display:none"><svg class="ic" viewBox="0 0 24 24" style="width:40px;height:40px"><path d="M3 3v18h18"/><path d="m19 9-5 5-4-4-3 3"/></svg></div>' +
          '</a><div class="fig-meta"><span>' + escapeHtml(f.name) + '</span><span>' + formatSize(f.size) + '</span></div></div>';
      }).join('') + '</div>';
    }).catch(function (e) { document.getElementById('galleryGrid').innerHTML = errorBlock('加载失败：' + e.message); });
  }

  /* ── 全局事件绑定 ── */
  function bindGlobal() {
    document.getElementById('sidebar').addEventListener('click', function (e) {
      var item = e.target.closest('.side-link'); if (item) go(item.dataset.view);
    });
    document.addEventListener('click', function (e) {
      var g = e.target.closest('[data-view]'); if (g) go(g.dataset.view);
    });
    document.getElementById('themeToggle').addEventListener('click', toggleTheme);
    var modal = document.getElementById('settingsModal');
    document.getElementById('settingsBtn').addEventListener('click', function () {
      document.getElementById('apiKeyInput').value = state.apiKey || ''; modal.hidden = false;
    });
    document.getElementById('settingsClose').addEventListener('click', function () { modal.hidden = true; });
    document.getElementById('settingsSave').addEventListener('click', function () {
      state.apiKey = document.getElementById('apiKeyInput').value.trim();
      localStorage.setItem('mm_api_key', state.apiKey); modal.hidden = true; toast('设置已保存', 'ok'); connCheck();
    });
    modal.addEventListener('click', function (e) { if (e.target === modal) modal.hidden = true; });
    document.getElementById('menuToggle').addEventListener('click', toggleSidebar);
    document.getElementById('drawerMask').addEventListener('click', closeDrawer);
    document.addEventListener('keydown', function (e) { if (e.key === 'Escape') { modal.hidden = true; closeDrawer(); } });
    var gs = document.getElementById('globalSearch');
    if (gs) gs.addEventListener('keydown', function (e) {
      var val = this.value.trim();
      if (e.key === 'Enter' && val) { go('catalog'); setTimeout(function () { var s = document.getElementById('catSearch'); if (s) { s.value = val; s.dispatchEvent(new Event('input')); } }, 50); }
    });
  }

  /* ── 启动 ── */
  function initApp() {
    state.apiKey = localStorage.getItem('mm_api_key') || '';
    initTheme();
    bindGlobal();
    window.addEventListener('hashchange', function () { navigate((location.hash || '#dashboard').slice(1)); });
    navigate((location.hash || '#dashboard').slice(1));
    connCheck();
    setInterval(connCheck, 30000);
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', initApp);
  else initApp();
})();
