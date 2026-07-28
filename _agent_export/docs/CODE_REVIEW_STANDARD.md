# 代码审查标准 (Code Review Standard)

> 适用范围：`agent/` 仓库全部新增与修改代码。
> 制定依据：本仓库实测扫描基线 + 通用 Python 审查规范 + 辩证方法论（矛盾分析 / 统筹兼顾）。
> 配套文档：`CODE_REVIEW_PROCESS.md`（流程）、`.github/PULL_REQUEST_TEMPLATE.md`（模板）。

---

## 0. 制定依据与本仓库现状基线

标准不是凭空套模板。先承认事实，再立规矩。本仓库（v3.4.2）实测扫描结果：

| 指标 | 实测值 | 说明 |
|------|--------|------|
| Python 文件数 | 120 | 不含 `.venv` / `build*` / `dist*` |
| 总代码行数 | 23,750 | 同上 |
| `except Exception` 宽捕获 | 83 处 | 错误被吞，问题难定位 |
| 裸 `print()` 调用 | 122 处 | 未走项目自带 logger，生产无日志 |
| `# noqa` / `# type: ignore` 绕过 | 32 处 | 类型检查被人为跳过 |
| 巨石文件 | validator 1201 / agent 857 / writer 737 / main 626 / web_ui 613 行 | 单文件职责过载 |
| 核心套件测试覆盖率 | 41.5% | pyproject 写 60% 但从未强制 |
| 0% 覆盖模块 | `web_ui/server.py`、`tool_protocol.py`、`*_runner.py` | 高风险路径无保护 |
| 全量默认测试套件 | 313 passed / 171 skipped / 5 xfailed | CI 却只跑其中 3 个文件 |

**矛盾分析（主要矛盾）**

| 矛盾对 | 判定 |
|--------|------|
| 假门禁（CI 不拦） ↔ 真实质量风险 | ⭐ **主要矛盾**。CI 的 lint 用默认规则且忽略 F401/F811/F841，mypy 用 `\|\| true`，覆盖率 `fail_under=0`，只跑 3 个测试文件，等于没有质量闸门。解决了它，质量与速度的紧张关系才有约束锚点。 |
| 质量严格度 ↔ 交付速度 | 次要矛盾。一次性开启全套严格规则会爆出数百处违规、阻塞日常开发，需渐进。 |
| 自动门禁 ↔ 人工评审 | 非对抗。机器卡机械错误，人卡设计与架构，二者互补。 |

**统筹兼顾（当前阶段平衡点）**：优先让门禁"真实运转"（跑全量测试、ruff 全量报告、mypy 上报），但不立即阻断开发；严格规则的阻断随债务清偿分阶段开启。禁止"只赶进度不管质量"的片面性，也禁止"一次性几百误报压垮评审"的激进。

---

## 1. 严重级别定义

评审评论必须带级别标签，格式 `[级别] 内容`。

| 级别 | 含义 | 是否阻塞合并 |
|------|------|--------------|
| `[BLOCKER]` | 安全漏洞、数据错误、破坏现有功能、违反本仓库专项红线（§3） | 必须修 |
| `[MAJOR]` | 设计缺陷、架构违背、明显逻辑错误、可维护性严重受损 | 必须讨论并修 |
| `[MINOR]` | 局部可改进：命名、重复、未用变量、异常处理不当 | 建议修 |
| `[NIT]` | 风格细节：空行、引号、注释格式 | 可选 |
| `[PRAISE]` | 写得好的地方，明确点出 | 鼓励 |

原则：一条评论只表达一个观点；给方案而非只给判断；`[BLOCKER]`/`[MAJOR]` 必须说明"为什么"和"怎么改"。

---

## 2. 审查清单

### 2.1 通用质量
- [ ] 单一职责：函数 / 类是否只做一件事
- [ ] 复杂度：单函数是否过长（建议 ≤ 60 行）、嵌套是否过深（建议 ≤ 4 层）
- [ ] 重复：是否有可提取的重复逻辑
- [ ] 命名：变量 / 函数名是否表意，避免 `tmp`、`data2`、`x` 这类含糊名
- [ ] 死代码：无未使用导入、变量、函数、分支
- [ ] 注释：解释"为什么"而非"是什么"；无废话注释

### 2.2 Python 专项（本项目重点）
- [ ] **异常处理**：禁止裸 `except:`；禁止无差别 `except Exception`（应捕获具体异常，至少在 `except` 块内记录日志）；禁止空 `except: pass`
- [ ] **日志**：禁止裸 `print()` 用于运行期输出，统一走项目 logger；`print` 仅限 CLI 调试入口
- [ ] **类型标注**：公共函数 / 方法签名有类型标注；不滥用 `# type: ignore` 掩盖真实类型问题
- [ ] **可变默认参数**：禁止 `def f(x=[])` / `={}` / `=set()`，用 `None` + 函数内初始化
- [ ] **资源管理**：文件 / 连接 / 进程用 `with` 或 `try/finally` 释放
- [ ] **导入**：无循环导入；`import` 置于文件头（测试文件的 `importorskip` 除外，已 per-file 豁免）
- [ ] **依赖**：不引入与 `pyproject` 冲突的新依赖；可选依赖须优雅降级
- [ ] **确定性**：不依赖未初始化全局顺序、不依赖哈希随机性做关键逻辑

### 2.3 本仓库高风险区（针对已识别架构债）
- [ ] **求解内核一致性**：新增模型必须能经 `ModelFactory.solve` 真实求解，不新增"声明 implemented 但无真解"的条目（当前 29/53 真解）
- [ ] **工具调度单一入口**：外部调用走 `ToolProtocolAdapter.dispatch_tool_call`，不绕过
- [ ] **阶段顺序单一真相**：阶段排列改 `modules/stage_planner.py`，不在 `main.py` 硬编码漂移
- [ ] **MCP / WebUI 错误处理**：所有异常在 `do_POST` / 路由层被捕获并返回结构化错误（JSON + 正确 HTTP 状态码），不留裸 500
- [ ] **HITL / 反思 / 多轮**：新增 agent 能力须接 `approval_manager`、`ReflectionEngine` 降级路径、`conversation` 上下文，保持 `evaluation_method` 字段语义
- [ ] **覆盖率薄弱模块**：改 `web_ui/server.py`、`tool_protocol.py`、`*_runner.py` 时同步补测试，不扩大 0% 区域

### 2.4 安全红线（一票否决）
- [ ] **密钥**：严禁明文 API Key / Token / 密码出现在代码、日志、提交；只从环境变量或本地 `.env` 读取
- [ ] **不泄露 secret**：`.env`、`*.pem`、`credentials*` 必须被 `.gitignore` 覆盖
- [ ] **注入**：LLM / 用户入参拼接到命令、SQL、模板时做转义或参数化
- [ ] **路径**：文件操作不接受未校验的绝对路径 / `..` 穿越
- [ ] **依赖安全**：不引入已知高危版本；新增依赖说明用途

### 2.5 测试质量
- [ ] 新增逻辑有对应测试；关键路径覆盖率不下降
- [ ] 测试不造假数据：不凭空编造无计算依据的数值；使用确定性小样本
- [ ] 可选依赖测试用 `importorskip` 守卫；联网 / 密钥测试用 `skipif` 守卫
- [ ] 测试名表意，失败时能定位到具体断言
- [ ] 不降低现有测试通过数（全量默认套件 313 passed 为底线）

---

## 3. 本仓库专项红线（基于实测，禁止新增）

以下为本仓库当前已存在的债务，标准明确：**评审对新代码零容忍，存量债务走技术债清单逐步清偿，不在新代码里加码**。

1. 新增 `except Exception` 宽捕获、裸 `except:`、空 `except: pass` → `[BLOCKER]`
2. 新增裸 `print()` 用于运行期输出（非 CLI 入口）→ `[MAJOR]`
3. 新增 `# noqa` / `# type: ignore` 掩盖真实问题（无注释说明必要性）→ `[MAJOR]`
4. 新增单文件 > 800 行且无拆分理由 → `[MAJOR]`
5. 扩大 `web_ui/server.py`、`tool_protocol.py`、`*_runner.py` 的 0% 覆盖区域 → `[MAJOR]`
6. 绕过 `ModelFactory.solve` / `ToolProtocolAdapter` 单一入口 → `[BLOCKER]`

---

## 4. 评论模板

```
[BLOCKER] modules/xxx.py:142 裸 except 吞掉了求解异常
  现状：except Exception: pass 会让模型失败静默通过，下游拿到空结果。
  建议：捕获具体异常（如 ValueError），至少 logger.error(...) 记录，或在工具层返回结构化错误。

[MAJOR] modules/yyy.py:30 用 print 输出求解进度
  现状：生产环境无日志可查。
  建议：import logging; logger = logging.getLogger(__name__); logger.info(...)

[MINOR] modules/zzz.py:55 函数 calc 超过 90 行，建议拆分预处理与核心计算。

[PRAISE] modules/aaa.py 的 _get_xy 抽象很干净，复用成本低，赞。
```

---

## 5. 反模式 vs 正例（来自本项目）

**反模式 1：宽异常吞错**
```python
try:
    result = solve(model_id, params)
except Exception:        # 83 处同类问题之一
    result = None        # 失败被静默吞掉
```
正例：
```python
try:
    result = ModelFactory(model_id, **params).solve()
except ValueError as e:
    logger.error("solve failed for %s: %s", model_id, e)
    return {"status": "error", "message": str(e)}
```

**反模式 2：裸 print 代替日志**
```python
print("stage", stage, "done")   # 122 处同类问题之一
```
正例：
```python
logger.info("stage %s completed", stage)
```

**反模式 3：类型绕过**
```python
x: int = parse(s)  # type: ignore   # 32 处同类问题之一
```
正例：修正 `parse` 的返回类型标注，或做显式 `cast` 并注释为何需要。

**反模式 4：可变默认参数**
```python
def add_constraint(self, items=[]):   # 跨调用共享可变状态
    items.append(...)
```
正例：
```python
def add_constraint(self, items=None):
    items = items or []
```

---

## 6. 与本流程、CI 的关系

- 本标准由 `CODE_REVIEW_PROCESS.md` 的"评审四阶段"执行。
- 标准中可机器检查的条目（§2.2 异常 / 日志 / 类型绕过、§3 红线）将逐步纳入 CI 的 ruff 规则集与 pre-commit，详见流程文档 Phase 路线图。
- 机器只卡机械错误，设计 / 架构 / 安全判断由人审，二者不互相替代。
