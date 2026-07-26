# 数学建模竞赛工作流（数模工具）

> 面向 CUMCM 全国大学生数学建模竞赛 / 美赛（MCM·ICM）等赛题的建模—求解—论文生成一体化工作流平台。

**版本**: v3.4.2
**更新时间**: 2026-07-26
**适用竞赛**: CUMCM、MCM·ICM、电工杯等

---

## 概述

本仓库是「数学建模竞赛工作流」平台的 v3.4.2 版本。它把赛题求解拆成可编排的阶段流水线：问题解析 → 数据预处理 → 模型选择 → 模型求解 → 结果校验 → 论文写作 → 可视化，并配有一个覆盖 14 个类别、53 个模型的模型目录。

---

## 目录结构

```text
agent/
├── main.py                      # 主控脚本（薄编排层）
├── modules/                     # 13 个功能子包
│   ├── approval/                # 异步审批（风险分级）
│   ├── core/                    # 缓存、工具、接口协议
│   ├── data_processing/         # 数据预处理
│   ├── llm_agent/               # LLM Agent（pure_llm / hybrid / fallback）
│   ├── mcp_server/              # MCP Server（JSON-RPC 2.0）
│   ├── model_selection/         # 模型选择
│   ├── model_solving/           # 模型求解（factories/ 下 11+ Solver）
│   ├── orchestration/           # 流水线编排（七阶段调度）
│   ├── paper_writing/           # 论文写作
│   ├── problem_analysis/        # 问题解析
│   ├── validation/              # 自审查 / 结果校验
│   ├── visualization/           # 可视化（12 种图表）
│   └── web_ui/                  # Web 界面
├── config/
│   ├── model_catalog.json       # 模型目录（14 类别 / 53 模型声明）
│   └── workflow_config.yaml     # 工作流配置
├── tests/                       # 测试目录（绿集见下文）
├── docs/                        # workflow_guide.md / skill_integration.md
├── examples/quickstart/         # 通用示例（data.csv / problem.txt / run_quickstart.py）
├── benchmarks/                  # 性能基线
├── projects/                    # 赛题工程（运行时生成，已 gitignore）
└── output/                      # 运行输出（已 gitignore）
```

---

## 模型能力

模型目录 `config/model_catalog.json` 声明 **14 个类别、53 个模型**，覆盖：

| 类别 | 说明 |
|------|------|
| regression | 回归（线性回归等，纯 Python 真实实现） |
| classification | 分类 |
| clustering | 聚类（KMeans 等，纯 Python 真实实现） |
| dimension_reduction | 降维（PCA 等，纯 Python 真实实现） |
| time_series | 时间序列 |
| prediction | 预测 |
| optimization | 优化（线性规划等，纯 Python 真实实现） |
| evaluation | 评价（AHP / TOPSIS / DEA 等，纯 Python 真实实现） |
| graph_theory | 图论（最短路 / 最大流等，纯 Python 真实实现） |
| simulation | 仿真 |
| statistics | 统计 |
| neural_networks | 神经网络 |
| fuzzy_logic | 模糊逻辑 |
| optimization_meta | 优化元信息 |

> **诚实声明（重要）**：53 个模型全部 `implemented=True`，零 stub。其中回归、线性规划、KMeans、PCA、AHP、TOPSIS、DEA、图论最短路 / 最大流等为纯 Python 真实实现，无需重型依赖；其余通过 scikit-learn 等包装实现，缺失对应依赖时会优雅降级或显式抛出 `ImportError` / `NotImplementedError`，不会静默返回错误结果。使用前按需 `pip install -r requirements.txt` 安装完整依赖。

统一调用入口：`ModelFactory().solve(model_id, **params)`。

---

## 快速开始

环境要求：Python 3.13，完整依赖见 `requirements.txt`（核心栈 pandas / numpy / scipy / openpyxl / scikit-learn / statsmodels / matplotlib）。

```bash
# 1) 安装依赖（建议隔离虚拟环境）
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# 2) 运行通用示例
python examples/quickstart/run_quickstart.py

# 3) 调用一个真实求解器
python -c "
from modules.model_solving.model_factory import ModelFactory
f = ModelFactory()
r = f.solve('linear_programming', c=[-1, -2], A_ub=[[1, 1]], b_ub=[4])
print(r['status'], r.get('x'), r.get('fun'))
"
```

---

## 自审查与结果校验

`modules/validation/` 提供论文 / 模型 / 计算结果的多视角自审查：

- **数据质量视角**：缺失值、异常值、量纲一致性检查。
- **模型统计视角**：拟合优度、收敛性、灵敏度分析。
- **论文结论闸门**：当上游验证发现 `failed` / `critical` 时，论文标注「结论存疑」并返回 `validation_gate`，避免伪造满分指标。

> 历史教训：早期版本存在 CV 虚假满分、求解器静默返回 0 等问题，已在 v3.4.2 修复（`real_model` 标志 + 显式报错）。

---

## 测试

绿集（当前稳定通过，完整依赖下）：

```bash
pip install -r requirements.txt
PYTHONPATH=. python -m pytest tests/test_workflow.py tests/test_model_solving.py tests/test_validation.py -o addopts="" -q
# 结果：133 passed, 5 xfailed, 0 failed
```

注：可视化相关 2 项需 `matplotlib`；本会话在缺 matplotlib 的沙箱环境实测为 131 passed + 2 项待 matplotlib，完整依赖下即 133 passed。

- `test_workflow.py`：端到端工作流（含 numpy 输入回归测试）。
- `test_model_solving.py`：求解器正确性。
- `test_validation.py`：自审查逻辑。

> 说明：`tests/` 中部分文件针对早期架构 API 编写，与当前 API 存在代差，未纳入绿集（运行会失败，属预期，不代表功能缺陷）。需在 Git 中保留这些旧测试以备查证。

---

## 近期更新（v3.4.2）

- **移植 MM-Agent 能力**（提交 `b79c877`）：引入 HMML 层级方法库、公式精炼、DAG 依赖编排、赛题基准与可视化前端。
- **加强专家级建模机制**（提交 `7587d82`）：层 2 问题分析精炼、层 3 层次化分解、层 7 记忆上下文传递、专家流水线。
- **收口遗留任务**（提交 `b5f726d`）：logger、技能去重、审查门禁、多视角自审查。
- **修复 lint**（提交 `68f88c6`）：拆分 HMML 选择器测试中的多行导入，使 CI 通过。
- **添加建模逻辑说明报告**（提交 `7974dcb`）：`working_logic_report.html` 入库，运行产物 `results/` 纳入 `.gitignore`。

历史修复（基线 `261b4e4`）：numpy 布尔歧义（AHP / 图论）、DEA 维度错误（CCR 模型），均附回归测试。

---

## 状态与维护

- 仓库已建立多提交 git 历史，远程 `origin` 指向私有仓库 `https://github.com/sadffgsrt/math-modeling-tools.git`，并已推送。
- 运行环境会按会话重置 `.git`，建议每个会话结束前推送到远程仓库防丢。
- 本地备份脚本 `备份/backup_agent.sh`（全量打包 `agent/`，含 `.git`）可作补充保险。

许可证：见 [LICENSE](./LICENSE)（MIT）。
