# 层次化问题分解器（MM-Agent 层3 移植，离线优先）
#
# 设计参考 MM-Agent 的 agent/problem_decompse.py + decompose_prompt.json：
#   不同赛题类型（C 连续/优化、D 离散/网络、E 评价…）有不同「经典拆法」，
#   并随子任务数量细化。分解后再逐条精修，对应专家
#   「这类题通常要拆成数据预处理、建模、求解、敏感性分析几块」的套路记忆。
#
# 本实现（纯自研、MIT，不复制 MM-Agent 任何 CC BY-NC 提示词/代码）：
#   - 按 problem_type（题型）提供确定性「专家拆法」模板；
#   - 按 tasknum（子任务数）自动粗化/细化到目标粒度；
#   - 输出结构化 Decomposition（含每步依赖、建议阶段、建议方法族），
#     并可一键转成 DAG 依赖图对接 modules/orchestration.dag；
#   - 全程离线、可控、可人审。

from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional

from .problem_analysis_refiner import _heuristic_problem_type


# ─────────────────────────────────────────────────────────────
# 专家拆法模板（按题型，确定性）
# 每步：title 步骤名 / phase 阶段 / method_hint 建议方法族 / desc 说明
# ─────────────────────────────────────────────────────────────
_STEP = Dict  # 占位类型提示

_CANONICAL: Dict[str, List[dict]] = {
    "evaluation": [
        {"title": "数据收集与预处理", "phase": "data_prep", "method_hint": ["数据清洗", "归一化"],
         "desc": "整理待评价对象与指标数据，处理缺失与量纲。"},
        {"title": "评价指标体系构建", "phase": "modeling", "method_hint": ["指标体系", "层次结构"],
         "desc": "从题目目标抽取维度，搭建可量化指标树。"},
        {"title": "权重确定", "phase": "modeling", "method_hint": ["AHP", "熵权法", "TOPSIS"],
         "desc": "主观与客观结合确定指标权重。"},
        {"title": "综合评价与排序", "phase": "solve", "method_hint": ["TOPSIS", "灰色关联", "模糊综合评价"],
         "desc": "融合得到综合得分并对方案排序。"},
        {"title": "敏感性分析", "phase": "validate", "method_hint": ["权重扰动", "鲁棒性"],
         "desc": "扰动权重/数据检验排序稳定性。"},
        {"title": "结论与建议", "phase": "report", "method_hint": [],
         "desc": "给出排序结论与可操作建议。"},
    ],
    "prediction": [
        {"title": "数据预处理与探索", "phase": "data_prep", "method_hint": ["缺失处理", "平稳性检验"],
         "desc": "清洗时序/特征，做探索性分析。"},
        {"title": "特征工程", "phase": "modeling", "method_hint": ["滞后项", "周期特征"],
         "desc": "构造利于预测的特征与滞后结构。"},
        {"title": "模型选择与训练", "phase": "modeling", "method_hint": ["ARIMA", "Prophet", "LSTM", "线性回归"],
         "desc": "按数据特征选模型并训练/拟合。"},
        {"title": "预测与输出", "phase": "solve", "method_hint": ["多步预测", "区间预测"],
         "desc": "输出未来时刻预测值与区间。"},
        {"title": "误差评估", "phase": "validate", "method_hint": ["MAE", "RMSE", "MAPE"],
         "desc": "用验证集评估误差并诊断。"},
        {"title": "不确定性分析", "phase": "validate", "method_hint": ["残差诊断", "情景"],
         "desc": "分析预测不确定性与情景。"},
    ],
    "regression": [
        {"title": "数据预处理", "phase": "data_prep", "method_hint": ["标准化", "共线诊断"],
         "desc": "清洗与诊断自变量关系。"},
        {"title": "变量筛选", "phase": "modeling", "method_hint": ["Lasso", "相关性检验"],
         "desc": "筛选显著特征、处理多重共线。"},
        {"title": "模型拟合", "phase": "solve", "method_hint": ["线性回归", "岭回归", "逻辑回归"],
         "desc": "拟合自变量与因变量关系。"},
        {"title": "显著性检验", "phase": "validate", "method_hint": ["t检验", "R²", "AIC"],
         "desc": "检验系数显著性与模型拟合优度。"},
        {"title": "残差诊断", "phase": "validate", "method_hint": ["残差图", "异方差"],
         "desc": "诊断模型假设是否成立。"},
    ],
    "optimization": [
        {"title": "问题抽象与变量定义", "phase": "modeling", "method_hint": ["决策变量", "参数"],
         "desc": "明确决策变量、参数与可行域。"},
        {"title": "目标函数与约束建模", "phase": "modeling", "method_hint": ["线性/非线性规划"],
         "desc": "写出目标函数与约束集。"},
        {"title": "算法选型", "phase": "modeling", "method_hint": ["线性规划", "遗传算法", "粒子群", "模拟退火"],
         "desc": "按可微性/离散性选型。"},
        {"title": "求解", "phase": "solve", "method_hint": ["单纯形", "启发式"],
         "desc": "求最优解并记录过程。"},
        {"title": "结果验证与灵敏度", "phase": "validate", "method_hint": ["灵敏度分析"],
         "desc": "检验最优性与参数灵敏度。"},
        {"title": "方案对比", "phase": "report", "method_hint": [],
         "desc": "对比候选方案给出推荐。"},
    ],
    "classification": [
        {"title": "数据预处理", "phase": "data_prep", "method_hint": ["缺失", "编码"],
         "desc": "清洗与编码样本。"},
        {"title": "特征选择", "phase": "modeling", "method_hint": ["方差", "互信息"],
         "desc": "筛选判别力强的特征。"},
        {"title": "模型训练", "phase": "solve", "method_hint": ["SVM", "决策树", "随机森林", "KNN"],
         "desc": "训练分类/聚类模型。"},
        {"title": "评估", "phase": "validate", "method_hint": ["准确率", "F1", "轮廓系数"],
         "desc": "用指标评估性能。"},
        {"title": "解释", "phase": "report", "method_hint": ["特征重要度", "规则"],
         "desc": "解释模型与簇结构。"},
    ],
    "graph_network": [
        {"title": "网络建模", "phase": "modeling", "method_hint": ["邻接矩阵", "图构建"],
         "desc": "将实体与关系抽象为图。"},
        {"title": "指标计算", "phase": "modeling", "method_hint": ["中心性", "度"],
         "desc": "计算网络结构与关键节点指标。"},
        {"title": "最短路/最大流求解", "phase": "solve", "method_hint": ["Dijkstra", "最大流"],
         "desc": "求解路径或容量问题。"},
        {"title": "灵敏度与鲁棒性", "phase": "validate", "method_hint": ["边权扰动"],
         "desc": "分析结构与参数鲁棒性。"},
    ],
    "simulation": [
        {"title": "系统边界与变量定义", "phase": "modeling", "method_hint": ["状态变量", "参数"],
         "desc": "界定系统与状态变量。"},
        {"title": "动力学/规则建模", "phase": "modeling", "method_hint": ["系统动力学", "元胞自动机", "ABM"],
         "desc": "建立演化规则或方程。"},
        {"title": "仿真实验设计", "phase": "solve", "method_hint": ["情景", "蒙特卡洛"],
         "desc": "设计实验与抽样方案。"},
        {"title": "结果分析与政策建议", "phase": "report", "method_hint": ["敏感性", "政策情景"],
         "desc": "分析输出并提政策建议。"},
    ],
    "general": [
        {"title": "问题理解与假设", "phase": "modeling", "method_hint": [],
         "desc": "明确目标、变量与假设。"},
        {"title": "模型构建", "phase": "modeling", "method_hint": ["综合评价", "回归", "优化"],
         "desc": "选择建模范式并建模。"},
        {"title": "求解", "phase": "solve", "method_hint": [],
         "desc": "求解或拟合模型。"},
        {"title": "验证与分析", "phase": "validate", "method_hint": ["敏感性"],
         "desc": "验证并做敏感性分析。"},
        {"title": "结论", "phase": "report", "method_hint": [],
         "desc": "形成结论与建议。"},
    ],
}

_GENERIC_TAIL = [
    {"title": "结果可视化", "phase": "report", "method_hint": ["图表"],
     "desc": "将关键结果可视化便于解读。"},
    {"title": "结论与建议", "phase": "report", "method_hint": [],
     "desc": "凝练结论与可操作建议。"},
    {"title": "论文撰写", "phase": "report", "method_hint": [],
     "desc": "按竞赛论文结构成文。"},
]


# ─────────────────────────────────────────────────────────────
# 数据结构
# ─────────────────────────────────────────────────────────────
@dataclass
class SubTask:
    task_id: str
    title: str
    phase: str
    method_hint: List[str]
    description: str
    depends_on: List[str] = field(default_factory=list)


@dataclass
class Decomposition:
    decomposition_id: str
    problem_id: str
    problem_type: str
    tasknum: int
    tasks: List[SubTask]
    metadata: Dict = field(default_factory=dict)

    def to_dag_graph(self) -> Dict[str, List[str]]:
        """转成 {task_id: [依赖的 task_id...]}，对接 dag.parse_dependencies / compute_dag_order。"""
        return {t.task_id: list(t.depends_on) for t in self.tasks}


# ─────────────────────────────────────────────────────────────
# 分解器
# ─────────────────────────────────────────────────────────────
class ProblemDecomposer:
    """层次化问题分解器（层3）。"""

    def __init__(self, principles: Optional[Dict[str, List[dict]]] = None):
        self.principles = principles or _CANONICAL

    def decompose(self, problem_description: str, tasknum: Optional[int] = None,
                  problem_type: Optional[str] = None, problem_id: str = "") -> Decomposition:
        """把题目拆成结构化子任务。

        Args:
            problem_description: 题目/任务描述（用于启发式判题型）。
            tasknum: 期望子任务数；为 None 时用该题型默认粒度。
            problem_type: 可显式指定题型（覆盖启发式）。
            problem_id: 题目标识。
        Returns:
            Decomposition
        """
        ptype = problem_type or _heuristic_problem_type(problem_description)
        steps = list(self.principles.get(ptype, self.principles["general"]))

        if tasknum and tasknum > 0:
            steps = self._fit_to_tasknum(steps, int(tasknum))

        tasks: List[SubTask] = []
        for i, s in enumerate(steps):
            dep = [f"T{i - 1:02d}"] if i > 0 else []  # 默认线性链依赖（前序节点），对接 DAG
            tasks.append(SubTask(
                task_id=f"T{i:02d}",
                title=s["title"],
                phase=s["phase"],
                method_hint=list(s.get("method_hint", [])),
                description=s.get("desc", ""),
                depends_on=dep,
            ))

        from hashlib import md5
        rid = "DEC-" + md5((problem_description + "|" + ptype).encode("utf-8")).hexdigest()[:8]
        return Decomposition(
            decomposition_id=rid, problem_id=problem_id, problem_type=ptype,
            tasknum=len(tasks), tasks=tasks,
            metadata={"requested_tasknum": tasknum, "canonical_len": len(steps)},
        )

    @staticmethod
    def _fit_to_tasknum(steps: List[dict], tasknum: int) -> List[dict]:
        """把规范步骤粗化/细化到目标子任务数。"""
        if tasknum == len(steps):
            return steps
        if tasknum < len(steps):
            # 保留前部关键步骤，余下合并为一句「综合与报告」
            head = steps[: tasknum - 1]
            merged_desc = "；".join(s["title"] for s in steps[tasknum - 1:])
            head.append({"title": "综合分析与结论", "phase": "report",
                         "method_hint": [], "desc": f"综合前述步骤结果（{merged_desc}）并形成结论与建议。"})
            return head
        # tasknum > len：追加通用尾部直到达到目标数
        extra = list(_GENERIC_TAIL)
        out = list(steps)
        idx = 0
        while len(out) < tasknum and extra:
            out.append(extra.pop(0))
            idx += 1
        # 仍不足则补「补充分析」
        while len(out) < tasknum:
            out.append({"title": f"补充分析{len(out) - len(steps) + 1}",
                        "phase": "validate", "method_hint": [],
                        "desc": "根据评审反馈补充分析。"})
        return out

    def save(self, dec: Decomposition, output_path: str) -> None:
        from pathlib import Path
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            import json
            json.dump(asdict(dec), f, ensure_ascii=False, indent=2)


def decompose_problem(problem_description: str, tasknum: Optional[int] = None,
                      problem_type: Optional[str] = None, problem_id: str = "") -> Decomposition:
    """一行式分解。"""
    return ProblemDecomposer().decompose(
        problem_description, tasknum=tasknum, problem_type=problem_type, problem_id=problem_id,
    )


__all__ = [
    "SubTask",
    "Decomposition",
    "ProblemDecomposer",
    "decompose_problem",
]
