# modules

核心功能模块集合，按工作流阶段划分。

| 子包 | 职责 |
|------|------|
| `approval/` | 异步审批与风险分级 |
| `core/` | 缓存、工具函数、接口协议 |
| `data_processing/` | 数据预处理与清洗 |
| `llm_agent/` | LLM Agent 决策（pure_llm / hybrid / fallback） |
| `mcp_server/` | MCP Server（JSON-RPC 2.0） |
| `model_selection/` | 模型选择策略 |
| `model_solving/` | 模型求解器工厂（11+ Solver 文件） |
| `paper_writing/` | 论文生成 |
| `problem_analysis/` | 问题解析与拆分 |
| `validation/` | 论文 / 模型 / 计算结果自审查 |
| `visualization/` | 12 种可视化图表 |
| `web_ui/` | Web 界面 |
