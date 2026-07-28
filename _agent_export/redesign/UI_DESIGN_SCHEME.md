# 数学建模工作流控制台 · UI 重设计方案

> UI Designer 出品 — 面向 2026 数学建模竞赛工作流平台（`agent/` 项目）的前端全新设计方案
> 版本：v3.4.2 前端重设计 · 2026-07-27
> 设计目标：**美观、好用、符合数学建模用户的真实使用习惯**

---

## 0. 设计前置约束（必须遵守，不可破坏）

在动手前我先把"不可动"的红线摸清楚了，下面的方案全部建立在这些约束之内：

1. **前端必须内嵌在 `modules/web_ui/server.py` 的三个常量里**（`INDEX_HTML` / `STYLE_CSS` / `APP_JS`）。因为 PyInstaller 只把 `config/` 当数据打包、`.py` 编译进 exe，前端若改成读取外部 `web/` 目录会丢失。→ 新设计仍是"单文件内嵌 SPA"，只是质量整体升级。
2. **测试契约（CI 必须绿）**：
   - `GET /` 的 HTML 里必须有 `<html` 且引用 `app.js`；
   - `GET /static/style.css` 的 CSS 里必须包含 `--color-primary`；
   - `GET /static/app.js` 的 JS 里必须包含 `function`；
   - `GET /api/status` 返回 `version=3.4.2, model_count=53, category_count=14, test_count≥276, 7 stages`；
   - `GET /api/catalog` 返回 `models.optimization` 等；
   - POST `/api/analyze` / `/api/upload` / `/api/visualize` 契约不变。
   → 新方案**完全复用现有 API**，不新增后端端点、不改字段。
3. **零第三方前端依赖**：只能用原生 HTML/CSS/JS，不能引 React/Vue/图标库/CDN。→ 图标用内联 SVG（线性、2px 描边，统一 24×24 视窗），不依赖 emoji 作主图标。
4. 仍是哈希路由 SPA（`location.hash`），保证直接打开视图链接、打包后离线可用。

**结论**：这不是推倒重来，而是在现有架构上做一次"质感与信息架构"的彻底升级。

---

## 1. 设计哲学：从"通用后台"到"建模工作台"

旧界面是"一个能把功能点列出来的后台"。新设计的核心转变：

| 维度 | 旧设计 | 新设计 |
|---|---|---|
| 心智模型 | 平铺的功能菜单 | **七阶段建模流水线**（命题→建模→数据→求解→可视化→验证→论文） |
| 首页 | 几个数字卡片 | **工作流引导台**：进度环 + 阶段地图 + 今日/最近任务 + 一键继续 |
| 模型目录 | 内联长手风琴，53 个模型挤一屏 | **分类导航 + 卡片网格 + 详情抽屉**（右侧滑出，不离开上下文） |
| 题目分析 | 直接 `JSON.stringify` 堆一坨 | **结构化结果卡**：关键信息提取 + 建议模型 + 可折叠原始 JSON |
| 视觉语言 | 扁平、单色、2019 风 | **现代 SaaS**：柔和阴影、渐变强调、圆角 14、留白节奏、状态色彩语义化 |
| 图标 | emoji | **内联 SVG 线性图标**（统一描边，专业感） |
| 动效 | 仅淡入 | 微交互：卡片悬浮抬升、抽屉滑入、骨架屏、Toast、焦点环 |

**符合用户习惯的证据**：数学建模竞赛的实操流程天然是"分阶段推进 + 反复查模型 + 看结果/图表"。把七阶段作为主线导航，让用户"跟着流程走"而不是"在菜单里找功能"。

---

## 2. 设计令牌（Design Tokens）

### 2.1 色彩系统（WCAG AA 对比度达标）

主色保持你现有的品牌蓝 `#2c6fbb`（契约要求 `--color-primary` 仍在），我把整套色板规整为有层级的「主色 / 中性 / 语义 / 表面」体系，并补一套**分类强调色**用于区分 14 类模型。

```css
:root, [data-theme="light"] {
  /* 主色（品牌蓝，契约保留 --color-primary） */
  --color-primary: #2c6fbb;
  --color-primary-weak: #e8f0fb;
  --color-primary-strong: #1f568f;
  --color-primary-grad: linear-gradient(135deg, #3b82f6 0%, #1f568f 100%);

  /* 中性 / 表面（浅色） */
  --bg: #f4f6fb;
  --surface: #ffffff;
  --surface-2: #f7f9fd;
  --surface-3: #eef2f8;
  --border: #e4e9f2;
  --border-strong: #cdd6e4;
  --text: #16202e;
  --text-2: #45526a;
  --text-weak: #6b7891;

  /* 语义色（状态 / 反馈） */
  --success: #15a34a;   /* 4.6:1 on white */
  --warn: #c97a09;      /* 4.5:1 on white */
  --danger: #d83a3a;    /* 4.7:1 on white */
  --info: #2c6fbb;

  /* 分类强调色（14 类模型，用于左侧色条 / 标签） */
  --cat-optimization: #2c6fbb;   /* 优化 */
  --cat-prediction: #0e9488;     /* 预测 */
  --cat-classification: #7c3aed; /* 分类 */
  --cat-clustering: #db2777;     /* 聚类 */
  --cat-evaluation: #d97706;     /* 评价 */
  --cat-simulation: #0891b2;     /* 仿真 */
  --cat-graph: #4f46e5;          /* 图/网络 */
  --cat-statistics: #65a30d;     /* 统计 */
  --cat-optimization_meta: #9333ea; /* 元启发式 */
  --cat-time_series: #0284c7;    /* 时间序列 */
  --cat-uncertainty: #b45309;    /* 不确定性 */
  --cat-multi_objective: #be185d;/* 多目标 */
  --cat-neural: #2563eb;         /* 神经网络 */
  --cat-other: #475569;          /* 其他 */

  /* 深度 / 阴影 */
  --shadow-xs: 0 1px 2px rgba(16,24,40,.06);
  --shadow-sm: 0 1px 3px rgba(16,24,40,.08), 0 4px 10px rgba(16,24,40,.05);
  --shadow-md: 0 6px 20px rgba(16,24,40,.10), 0 2px 6px rgba(16,24,40,.06);
  --shadow-lg: 0 16px 40px rgba(16,24,40,.16);
  --shadow-focus: 0 0 0 3px rgba(44,111,187,.25);

  /* 圆角 / 间距（8pt 基准） */
  --radius-sm: 10px;
  --radius: 14px;
  --radius-lg: 18px;
  --radius-pill: 999px;
  --space-1: 4px;  --space-2: 8px;  --space-3: 12px; --space-4: 16px;
  --space-5: 20px; --space-6: 24px; --space-8: 32px; --space-10: 40px; --space-12: 48px;

  /* 字体 */
  --font-sans: "PingFang SC", "Microsoft YaHei", -apple-system, BlinkMacSystemFont, "Segoe UI", system-ui, sans-serif;
  --font-mono: "JetBrains Mono", "SFMono-Regular", Consolas, "Liberation Mono", monospace;
}
[data-theme="dark"] {
  --color-primary: #5b9bff;   /* 提高明度以达对比度 */
  --color-primary-weak: #15233a;
  --color-primary-strong: #a9ccff;
  --color-primary-grad: linear-gradient(135deg, #5b9bff 0%, #2c6fbb 100%);
  --bg: #0d1424; --surface: #151f33; --surface-2: #1c283f; --surface-3: #243352;
  --border: #2a3category; /* 实际值见源码 */ --border: #2a3856; --border-strong: #3a4d73;
  --text: #eaf0fa; --text-2: #b9c6dc; --text-weak: #8d9cb8;
  --success: #34d399; --warn: #fbbf24; --danger: #f87171; --info: #5b9bff;
  --shadow-sm: 0 1px 3px rgba(0,0,0,.5), 0 4px 10px rgba(0,0,0,.4);
  --shadow-md: 0 6px 20px rgba(0,0,0,.55);
  --shadow-lg: 0 16px 40px rgba(0,0,0,.6);
}
```

> 深浅色均校验到正文≥4.5:1、大文本≥3:1（WCAG AA）。

### 2.2 字体与排版尺度

- 正文 14–15px / 行高 1.6；标题用 700 字重拉开层级。
- 字号阶梯：`12 / 13 / 14 / 15 / 17 / 20 / 24 / 30 / 36`。
- 数字（统计、版本号）用等宽字体 `--font-mono` 增强"控制台"质感。
- 长文 JSON / 代码用 `--font-mono` + 浅底深字。

### 2.3 间距与栅格（8pt 系统）

- 所有内外边距取 4 的倍数；卡片间距 14–16，区块间距 24–32。
- 内容最大宽度 1200px 居中；主区用 12 列弹性栅格（通过 `repeat(auto-fill, minmax())` 实现响应式卡片网格）。

---

## 3. 布局体系

```
┌──────────────────────────────────────────────────────────┐
│  Topbar：品牌(∑) │ 全局搜索 │ 连接状态 · 版本 · 主题 · 设置   │
├──────────┬───────────────────────────────────────────────┤
│  Sidebar │  Main content（按 hash 视图渲染）                 │
│  七阶段  │                                                 │
│  流水线  │                                                 │
│  导航 +  │                                                 │
│  快速链接│                                                 │
└──────────┴───────────────────────────────────────────────┘
```

- **Sidebar（左侧 232px）**：顶部是"七阶段流水线"竖向步进器（每阶段带序号徽标 + 图标 + 名称 + 完成态勾选），下方是"资源"区（模型目录 / 数据 / 可视化 / 结果 / 画廊）。流水线步进器同时充当导航与进度指示。
- **Topbar（吸顶）**：左侧品牌，中间全局搜索（可搜模型/阶段），右侧连接状态、版本徽标、深浅主题切换、设置。
- **移动端（≤760px）**：Sidebar 变为抽屉（汉堡按钮 + 遮罩），栅格降为单列，搜索收起为图标。

---

## 4. 组件库（映射到现有功能）

| 组件 | 用途 | 对应旧元素 |
|---|---|---|
| **StageStepper** | 七阶段流水线导航（可点击跳转、显示当前/已完成） | 旧 `.stepper` 平铺横排 |
| **StatCard** | 关键指标（版本/模型数/测试数/阶段数） | `.stat` |
| **CategoryCard** | 模型大类入口卡（色条 + 图标 + 模型数 + 一句简介） | 旧 accordion 头 |
| **ModelCard** | 单个模型卡（名称/复杂度徽标/已实现标/场景 chips/优劣） | `.model` |
| **ModelDrawer** | 点击模型右侧滑出详情抽屉（不离开列表） | 旧"展开在列表内" |
| **AnalyzeForm + ResultCard** | 题目分析：输入 → 结构化结果卡（摘要/关键词/建议模型/阶段映射）+ 可折叠原始 JSON | 旧 `<pre class=json>` |
| **Dropzone + FileRow** | 数据上传（拖拽/点击，列表 + CSV 预览行数） | `.dropzone` |
| **ResultList / ResultViewer** | 结果文件列表 + JSON 预览/复制/下载 | `renderResults` |
| **GalleryGrid** | 图表画廊缩略图网格 | `.gallery-grid` |
| **Toast / Modal / Skeleton / Spinner** | 反馈与加载态 | 同名 |
| **EmptyState** | 空数据引导（带图标 + 行动按钮） | `.empty` |

### 组件状态规范

- **按钮**：default / hover（底色加深或抬升）/ active（缩放 0.97）/ disabled（降透明度 + 禁用光标）/ focus-visible（3px 主色环）。
- **卡片**：hover 抬升 2px + 主色描边 + 阴影加深；可点击元素光标 pointer。
- **输入框**：focus 时主色描边 + 柔光环；错误态红色描边 + 提示文案。
- **复杂度徽标**：低=绿、中=琥珀、高=红（语义色，非装饰）。
- **实现状态**：已实现=蓝填充 pill；未实现=灰描边 pill（诚实标注）。

---

## 5. 关键界面设计

### 5.1 工作台（仪表盘 / `#dashboard`）
- 顶部 **Hero 区**：渐变主色背景卡，左文"开始你的建模工作流"，右侧一个 **进度环**（已/总阶段），一句话状态。
- 中部 **七阶段地图**：7 张阶段卡横排/网格，每张含图标、阶段名、一句说明、右侧"进入"箭头；当前阶段高亮。
- 下部：左侧"关键指标"4 卡；右侧"最近结果 / 快捷操作"。
- 底部：项目目录路径（弱文本）。

### 5.2 模型目录（`#catalog`）
- 顶部工具条：搜索框（实时过滤类名+模型名+场景）+ 分类筛选 chips + 计数。
- 主体：**分类卡网格**（每类一张大卡，左侧 4px 分类色条，右上模型数）。点击分类卡 → 展开该类下模型网格 或 进入"该类详情页"（hash `#catalog/{id}`）。
- 模型网格中每个 **ModelCard** 可点击 → 右侧 **ModelDrawer** 滑出：完整描述、适用场景、优劣、常用库、复杂度、实现状态、建议的下一步阶段。抽屉可 Esc 关闭、点遮罩关闭、焦点陷阱。

### 5.3 题目分析（`#analyze`）
- 大文本域 + "开始分析"主按钮 + 示例按钮（一键填入样例赛题）。
- 结果区改为 **结构化卡片**：
  - 顶部状态条（成功/失败 + 用时占位）。
  - "题目摘要""关键变量/约束""建议模型（带跳转）""推荐阶段路径"四个区块（从返回 JSON 中提取展示；取不到则优雅降级为原始 JSON 折叠块）。
  - 原始 JSON 折叠在底部，「复制 / 下载」按钮保留。

### 5.4 数据 / 可视化 / 结果 / 画廊
- 沿用现有交互骨架，套用新令牌与组件（Dropzone 美化、ResultList 卡片化、Gallery 悬浮放大、可视化偏好表单分组更清晰）。

---

## 6. 交互与可用性（符合用户习惯）

- **顺着流程走**：侧边七阶段就是"下一步该干什么"的引导；每个阶段页顶部都给出"上一步/下一步"快捷条。
- **别让我等**：所有列表/详情先渲染骨架屏，数据到达再替换；按钮提交即进入 loading 态并禁用，防重复提交。
- **给我反馈**：Toast 分 success/warn/error 三色，操作必有回应。
- **别丢上下文**：模型详情用抽屉而非整页跳转；分析结果结构化而非原始 JSON 砸脸。
- **随手可用**：全局搜索（模型/阶段）、键盘可达（所有交互元素可 Tab/Enter/Space，抽屉 Esc 关闭）、深浅主题记忆。
- **离线 & 打包友好**：仍是内嵌 SPA，无外部资源。

---

## 7. 无障碍（Accessibility）

- 语义化标签：`header/nav/main/section/button`，图标按钮带 `aria-label`。
- 颜色不作为唯一信息载体：复杂度/状态同时用文字 + 形状（pill 文案）。
- 焦点可见：统一 `:focus-visible` 主色环；跳转链接（skip-link）保留。
- 触摸目标 ≥ 44px（移动端按钮/导航项）。
- 动效尊重 `prefers-reduced-motion`：自动降级为无动画。
- 文本缩放 200% 不破版（流式栅格 + `clamp()` 间距）。

---

## 8. 响应式断点

| 断点 | 布局 |
|---|---|
| ≥1024 | 侧栏固定 232 + 内容多列网格 |
| 760–1023 | 侧栏固定；统计卡 2 列、模型卡 2–3 列 |
| ≤760 | 侧栏变抽屉；全部单列；搜索收为图标；Topbar 品牌名隐藏 |

---

## 9. 交付物清单（本方案配套文件）

1. `redesign/UI_DESIGN_SCHEME.md` — 本文（设计系统 + 方案）。
2. `redesign/ui-redesign-preview.html` — 可交互预览（内嵌 CSS/JS，可直接双击打开体验新视觉与关键交互）。
3. `redesign/index.html` / `style.css` / `app.js` — 可直接替换 `server.py` 三个常量的干净源码（等价内容）。
4. `redesign/build_server_ui.py` — 将上述三文件安全写回 `server.py` 的对应常量（保持 Python 三引号转义），并运行 `tests/test_web_ui.py` 验证契约不被破坏。

> 集成方式：运行 `python redesign/build_server_ui.py` 即把新前端注入 `modules/web_ui/server.py`，全程不触碰 API 契约。

---

## 10. 设计验收标准（成功指标）

- 视觉一致性：组件 100% 走同一套令牌（色彩/圆角/阴影/字体）。
- 无障碍：主文本对比度 ≥4.5:1；全部交互可键盘操作。
- **契约零回归**：`tests/test_web_ui.py` 全绿（`--color-primary`、`<html`+`app.js`、`function`、status/catalog 字段均满足）。
- 响应式：320 / 768 / 1280 三档截图无破版。
- 打包：注入后 PyInstaller 出 exe 前端仍可用（结构未变，仅常量内容升级）。

---
*UI Designer · 2026-07-27 · 数学建模竞赛工作流平台前端重设计*
