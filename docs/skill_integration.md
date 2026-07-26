# 数学建模技能整合指南

## 现有技能概览

工作目录中安装了3个数学建模相关技能：

| 技能 | 版本 | 阶段数 | 特点 | 状态 |
|------|------|--------|------|------|
| math-modeling-skill-main | v1.0 | 3阶段 | 结构清晰，适合快速上手 | 备选 |
| mathmodel-skill-main | v6.0 | 10阶段+4反馈层 | 最全面，含国赛91篇真烘焙 | **推荐** |
| MathModel-Skill-master | v2.0 | 10个专业skill | Agent-native，但缺SKILL.md | 归档 |

## 推荐方案

### 主技能：mathmodel-skill-main

**选择理由**：
- 10阶段完整流程（选题→建模→求解→论文→终审）
- 4层反馈机制（L1-L4）
- 支持国赛/美赛/电工杯三竞赛
- 含91篇国赛真题烘焙数据
- 全程问答式交互
- 状态跨平台互通

**使用方式**：
```
用户说："开始建模" 或 "使用 mathmodel-skill 开始建模"
```

### 辅助技能：math-modeling-skill-main

**保留用途**：
- 作为简化版工作流的参考
- 三阶段协作模式的示例
- 算法资源库（7大类算法说明）

### 归档技能：MathModel-Skill-master

**归档原因**：
- 缺少SKILL.md入口文件
- 功能与mathmodel-skill-main重叠
- 文件较大（4.1M）但利用率低

**归档位置**：`skill/archived/MathModel-Skill-master/`

## 与工作流的集成

### 方案A：技能作为主控（推荐）

用户直接使用mathmodel-skill-main，我们的workflow作为补充工具：

```
用户 → mathmodel-skill-main (主流程)
           ↓
      调用workflow模块 (补充功能)
           - PDF解析
           - 数据处理
           - 可视化
           - Word生成
```

### 方案B：工作流调用技能

workflow在各阶段调用对应技能：

```python
# 在main.py中
def _run_problem_analysis(self):
    # 调用mathmodel-skill的题意解析
    # 调用workflow的PDF解析补充
    pass
```

### 推荐：方案A

原因：
1. mathmodel-skill-main已经很完整
2. 避免重复实现
3. 用户体验更一致

## 技能目录结构

```
skill/
├── workbuddy/              # 活跃技能
│   ├── mathmodel-skill-main/     # 主技能（10阶段）
│   ├── math-modeling-skill-main/ # 辅助技能（三阶段）
│   ├── python-dataviz/           # 数据可视化
│   ├── homemade-machine-learning/# 机器学习
│   ├── r-stats/                  # R统计分析
│   ├── biostatistics/            # 生物统计
│   ├── data-analysis-workflow/   # 数据分析流程
│   ├── statistics-2/             # 统计检验
│   ├── data-analyst-cn/          # 中文数据分析
│   └── mathgraphs/              # 数学图表
├── archived/               # 归档技能
│   └── MathModel-Skill-master/   # 已归档
└── README.md               # 技能使用说明
```

## 使用建议

### 对于CUMCM国赛

1. **选题阶段**：使用mathmodel-skill的Stage 1
2. **建模阶段**：使用workflow的模型选型模块
3. **求解阶段**：使用workflow的模型求解模块
4. **可视化**：使用python-dataviz技能
5. **论文撰写**：使用mathmodel-skill的Stage 8
6. **终审**：使用mathmodel-skill的Stage 9

### 对于MCM/ICM美赛

1. 使用mathmodel-skill的MCM模式
2. 英文论文生成使用workflow的paper_writing模块
3. 可视化使用python-dataviz技能

## 维护说明

1. **更新主技能**：定期检查mathmodel-skill-main的新版本
2. **清理归档**：超过6个月未使用的技能移至archived
3. **文档同步**：技能更新后同步更新本整合指南
