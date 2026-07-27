# 代码审查流程（CODE REVIEW PROCESS）

适用仓库：`agent/`
配套文档：`docs/CODE_REVIEW_STANDARD.md`、`docs/CODE_REVIEW_PROCESS.md`、`.github/PULL_REQUEST_TEMPLATE.md`

## 1. 角色与职责

| 角色 | 职责 |
| --- | --- |
| 作者（Author） | 提交前本地自检、填 PR 模板、回应评论、修复 Blocker/Critical |
| 审查者（Reviewer） | 至少 1 人；按标准逐项评论；拥有合入否决权 |
| 维护者（Maintainer） | 处理分歧、最终合入、保证主干绿 |

小团队约束：作者不得自审自合；至少 1 名独立审查者。

## 2. 分支与提交规范

- 功能分支：`feat/短描述`、`fix/短描述`、`refactor/短描述`、`docs/短描述`。
- 禁止直接推 `main`；所有改动走 PR。
- Commit message 前缀：`feat:` `fix:` `docs:` `refactor:` `test:` `chore:`，后接短句。
- 一次 PR 对应一个内聚改动，避免"顺手大扫除"混进功能代码。

## 3. PR 规模限制

- 单 PR 建议 < 400 行变更、< 10 个文件。
- 超过则拆 PR；巨石文件拆分（如 validator/agent）单独成 PR，不与功能改动混。
- 理由：大 PR 审查质量下降，缺陷逃逸率上升。

## 4. 评审四阶段

1. **作者自审（提交前）**：跑本地自检清单（第 5 节），确保 ruff/mypy/pytest 绿，填 PR 模板。
2. **初审（提交后 24h 内）**：审查者看"意图与结构"——是否该做、拆分是否合理、有无 Blocker/Critical。
3. **深度审（初审通过后）**：逐文件看逻辑、错误处理、测试、安全；按标准贴评论。
4. **终审与合入**：所有 Blocker/Critical 关闭；Minor/Nit 由作者酌情；维护者合入。

## 5. 本地自检清单（作者提交前必跑）

```
[ ] ruff check . --ignore E501 无新增 F/B/E 类报错
[ ] mypy modules 无新增类型错误（除已记录的 # type: ignore）
[ ] pytest 绿测集（test_workflow/test_model_solving/test_validation）全绿
[ ] 无新增裸 print()（用 logger 替代）
[ ] 无新增裸 except: / 无日志的 except Exception
[ ] 无明文密钥；凭证走 env / 本地 .env
[ ] 改动关联模块覆盖率不下降
[ ] 关联文档（标准/流程）如需更新已同步
```

## 6. CI 门禁现状与分阶段硬化路线

### 6.1 现状（2026-07-27 实测）

| 位置 | 问题 | 后果 |
| --- | --- | --- |
| `.pre-commit-config.yaml:3` | ruff 锁 `v0.1.0`，本地 `0.16.0` | 版本错配，pre-commit 可能用错规则或失败 |
| `pyproject.toml` ruff | ignore `F401/F811/F841` | 未用导入、重复定义、未用变量查不出 |
| `ci.yml:22` | `mypy ... || true` | 类型错误永不阻塞 |
| `ci.yml:24` | 只跑 3 个测试文件 + `--cov-fail-under=0` | 大量模块（web_ui/tool_protocol/runner）0% 覆盖也无感知 |
| 覆盖率基线 | 核心套件 41.5%（pyproject 写 60% 未强制） | 门槛虚设 |

### 6.2 硬化路线（渐进，不阻塞历史任务）

- **Phase 0（修版本错配）**：`.pre-commit-config.yaml` ruff rev 对齐本地 `0.16.0`；mypy rev 对齐。让本地与 CI 规则一致。
- **Phase 1（ruff 全量去 ignore）**：从 `pyproject` 移除 `F401/F811/F841` 的 ignore，改为逐文件 `# noqa` 标注原因；CI ruff 加 `--fix` 自动修。
- **Phase 2（mypy + 测试全量）**：`ci.yml` 去掉 `|| true`，mypy 失败则红；pytest 跑全量默认套件（非 legacy 测试已用 importorskip/密钥守卫，安全）。
- **Phase 3（覆盖率门槛渐进）**：`--cov-fail-under` 从 40 抬到 50 再到 60，每次只升一档，给历史代码补测缓冲。

Phase 0/1 为低风险，可立即做；Phase 2/3 需配套补测试，按季度推进。

## 7. Definition of Done（合入门槛）

- 至少 1 名独立审查者批准。
- 所有 `[Blocker]` `[Critical]` 已关闭。
- CI 全绿（对应阶段门禁）。
- 绿测集无回归。
- PR 模板填写完整，自查清单勾选。

## 8. SLA（响应时限）

| 事项 | 时限 |
| --- | --- |
| 初审 | 提交后 24h 内 |
| 作者回应评论 | 48h 内 |
| 终审合入 | 评论关闭后 24h 内 |

超时由维护者介入协调。

## 9. 分歧处理

- 审查者与作者就某条评论无法达成一致：先在 PR 评论中具名列出分歧点与各自依据。
- 仍不一致：升级到维护者裁决；裁决以"标准第几节 + 项目风险"为准，不凭职位。
- 若分歧源于标准本身模糊：记录到 `对话记录.md`，并在下一轮标准复审中修订。
- 禁止因分歧而长期挂着 PR 不处理；超过 5 个工作日无进展，维护者强制裁决。
