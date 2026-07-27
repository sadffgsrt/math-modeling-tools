# 代码审查流程 (Code Review Process)

> 配套：`CODE_REVIEW_STANDARD.md`（评什么）、`.github/PULL_REQUEST_TEMPLATE.md`（PR 模板）。
> 设计原则：辩证方法论指导。主要矛盾是"假门禁 ↔ 真实质量风险"，用统筹兼顾平衡"严格度 ↔ 交付速度"，用渐进硬化替代"一刀切"。

---

## 0. 辩证定位

**矛盾分析**
- ⭐ 主要矛盾：CI 门禁形同虚设（ruff 默认规则 + 忽略 F401/F811/F841、mypy `|| true`、覆盖率 `fail_under=0`、只跑 3 个测试文件）↔ 真实质量风险。
- 次要矛盾：质量严格度 ↔ 交付速度；自动门禁 ↔ 人工评审（互补，非对立）。

**统筹兼顾（当前阶段平衡点）**
- 速度 ↔ 质量：优先让门禁"真实运转"（跑全量测试、ruff 全量报告、mypy 上报），lint 阻断随债务清偿分阶段开启，不立即阻塞日常开发。
- 严格 ↔ 噪音：启用 BLE / T201 / F401 等规则，但用 Phase 渐进避免一次性数百误报压垮评审。
- 即时清债 ↔ 渐进：采用渐进 + 持久战，存量债务走技术债清单，新代码零容忍。

---

## 1. 角色与职责

| 角色 | 职责 |
|------|------|
| Author（提交者） | 自检通过、填 PR 模板、回应每条评论、不强行合并 |
| Reviewer（评审者） | 按标准逐条评审、带级别标签、给出方案、在 24h 内首响 |
| Maintainer（维护者） | 解决分歧、最终批准、守护主干质量闸门 |

小项目可由同一人兼 Author / Reviewer，但 `main` 分支合并须有第二人批准（或显式 self-review 记录）。

---

## 2. 分支与提交规范

- 分支：`feature/<topic>`、`fix/<topic>`、`docs/<topic>`、`refactor/<topic>`；禁止直接推 `main`。
- 提交：遵循约定式提交前缀 `feat:` / `fix:` / `docs:` / `refactor:` / `test:` / `chore:`。
- 单次提交聚焦单一关注点；改同批文件用短 message 覆盖长 message（见 AGENTS.md 协作约定）。
- 每次改动 commit 后 `git push origin main`（沙箱无凭据时由本机执行，见协作约定）。

---

## 3. PR 规模限制

- 单 PR 建议 ≤ 400 行有效改动；超过请拆分。
- 一个 PR 只解决一个问题（一个 bug、一个特性、一类清理）。
- 重构与功能改动不混在同一 PR，方便评审与 bisect。

---

## 4. 评审四阶段

**阶段一：Author 本地自检（合并前必做）**
```bash
# lint（与 CI 一致的规则集，见 Phase 路线图）
ruff check . --ignore E501
# 类型
mypy modules --ignore-missing-imports
# 全量默认测试套件（legacy 自动跳过，当前基线 313 passed）
pytest tests/ -o addopts="" -q
```
全部绿、无新增 §3 红线，才开 PR。

**阶段二：自动门禁（CI）**
CI 跑：ruff 全量、mypy 上报、全量默认测试套件、覆盖率回归地板。任一阻断项红则 PR 不可合并。

**阶段三：人工评审**
- 按 `CODE_REVIEW_STANDARD.md` 逐条检查，评论带 `[级别]` 标签。
- 重点看：设计 / 架构 / 安全 / 测试质量（机器不卡的部分）。
- 每条 `[BLOCKER]` / `[MAJOR]` 必须被解决或显式达成共识，否则不批准。

**阶段四：批准与合并**
- Maintainer 确认所有 `[BLOCKER]`/`[MAJOR]` 已处理、CI 绿、PR 模板填妥。
- 合并方式：squash 保持主干线性；合并后删除特性分支。

---

## 5. 本地自检清单（Author 开 PR 前勾选）

- [ ] `ruff check . --ignore E501` 无新增错误
- [ ] `mypy modules` 无新增类型错误
- [ ] `pytest tests/ -o addopts=""` 全绿（不低于 313 passed 基线）
- [ ] 无新增 §3 红线（宽异常 / 裸 print / 类型绕过 / 巨石 / 0% 扩大）
- [ ] 改动的覆盖薄弱模块已补测试
- [ ] PR 模板已填，含风险与测试说明

---

## 6. CI 门禁硬化路线图（Phase 0-3）

现状 CI 是假门禁。按"先真实运转、后逐步阻断"推进，避免一次性爆数百误报。

| Phase | 目标 | CI 动作 | 阻断？ | 进入条件 |
|-------|------|---------|--------|----------|
| **Phase 0（立即）** | 门禁真实运转 | 跑全量默认测试套件（替代仅 3 文件）；ruff 基础规则全量扫描并阻断；mypy 全量上报（去 `\|\| true`，不阻断）；覆盖率地板 40% | 测试失败阻断；ruff 基础错误阻断；mypy 仅报告 | 无（当前即可做） |
| **Phase 1** | 机器卡机械错误 | ruff `select` 扩展至 `E,F,W,I,N,B,BLE,T201,SIM,C4,UP,PTH`；移除 `F401/F811/F841` ignore | ruff 阻断（先修存量债务或 per-file 临时豁免） | 存量 F401/F811/F841 清零或受控豁免 |
| **Phase 2** | 类型可信 | mypy 改为 `continue-on-error: false`（阻断） | mypy 阻断 | 存量类型错误清零 |
| **Phase 3** | 覆盖率可信 | `fail_under` 由 40% 阶梯提升至 60%（与 pyproject 一致） | 覆盖率阻断 | 核心模块覆盖达 60% |

每个 Phase 切换前在 PR 中说明，避免暗改门槛。

---

## 7. Definition of Done（合并前提）

- CI 全绿（当前阶段所有阻断项通过）
- 全部 `[BLOCKER]` / `[MAJOR]` 已处理或达成共识
- 测试不降于基线（313 passed）、无新增 §3 红线
- PR 模板完整、commit message 合规
- 至少一名 Reviewer 批准（或 Maintainer 显式 self-review）

---

## 8. SLA（响应时效）

| 项 | 时限 |
|----|------|
| Reviewer 首次响应 | 24 小时内 |
| Author 回应评论 | 48 小时内 |
| 阻塞性分歧上报 Maintainer | 24 小时内 |

超时未响应可 @ 提醒；长期无响应由 Maintainer 指派替补。

---

## 9. 分歧处理

- 非对抗性分歧（设计取舍等）：在 PR 评论中摆事实、给方案，民主讨论，求同存异。
- 评审者与被评审者无法达成一致：升级 Maintainer 裁决，裁决记录进 PR。
- 禁止"为了合并而妥协质量红线"；红线问题只能修，不能让。

---

## 10. 遗留债管理

- 存量债务（83 宽异常、122 裸 print、32 类型绕过、巨石文件、41.5% 覆盖）登记为 `tech-debt` 标签 issue，不在新代码加码。
- 清债方式：跟随相关模块改动顺手修；或单列 `refactor/` PR 批量修一类。
- 每清一类，对应 Phase 推进一级，门禁随之硬化。

---

## 11. 与本仓库其他规范的衔接

- 协作约定（AGENTS.md）：commit 后 push、短 message、不碰明文 token。
- 安全红线与用户指令 #12-#15 一致：密钥只本地 / 环境变量，禁止明文上传。
- 测试纪律（工作区记忆）：不造假数据、确定性小样本、可选依赖 `importorskip` 守卫。
