# 问题分析 actor-critic 精炼器（MM-Agent 层2 移植，离线优先）
#
# 设计参考 MM-Agent 的 agent/problem_analysis.py：
#   ProblemUnderstanding 在「问题分析」与「建模方案」两步都走
#   actor → critic → improvement 的 round 轮循环，模拟专家内心的「自我辩论」：
#   先给方案，再以挑剔评审视角找漏洞，最后修订。
#
# 本实现（纯自研、MIT，不复制 MM-Agent 任何 CC BY-NC 提示词/代码）：
#   - 把层2拆成两段：问题理解(understanding) 与 建模方案(modeling_plan)，每段各自 actor-critic；
#   - 默认 rule_fallback：用确定性模板 + 检查清单离线完成，无需外部依赖；
#   - hybrid / pure_llm：经可选 llm_call(req)->resp 接入 LLM，失败时自动降级规则；
#   - 结构化输出 ProblemAnalysis（含每段每轮历史），便于沉淀与人审。
#
# 仅依赖标准库（dataclasses/json/re/hashlib）。

import hashlib
import json
import re
from dataclasses import dataclass, field, asdict
from typing import Any, Callable, Dict, List, Optional


# ─────────────────────────────────────────────────────────────
# 数据结构
# ─────────────────────────────────────────────────────────────
@dataclass
class AnalysisRound:
    """单段单轮 actor-critic 记录。"""
    round: int
    actor_output: str
    critic_output: str
    critic_score: float        # 0~10
    improvement: str


@dataclass
class AnalysisStage:
    """一段（理解或方案）的完整精炼结果。"""
    stage: str                 # "understanding" / "modeling_plan"
    rounds: int
    final_output: str
    history: List[AnalysisRound]
    final_score: float


@dataclass
class ProblemAnalysis:
    """专家级问题建模分析（层2 产出）。"""
    analysis_id: str
    problem_id: str
    problem_type: str
    understanding: AnalysisStage
    modeling_plan: AnalysisStage
    metadata: Dict = field(default_factory=dict)


# ─────────────────────────────────────────────────────────────
# 题型启发式 + 专家拆法模板（离线）
# ─────────────────────────────────────────────────────────────
def _heuristic_problem_type(text: str) -> str:
    """轻量题型判断（C 连续/优化、D 离散/网络、E 评价等）。"""
    t = (text or "").lower()
    if any(k in t for k in ["预测", "forecast", "predict", "time series", "时间序列"]):
        return "prediction"
    if any(k in t for k in ["回归", "regression", "拟合", "fit"]):
        return "regression"
    if any(k in t for k in [
        "优化", "optimize", "optimization", "最小", "最大", "调度", "规划",
        "linear programming", "lp", "选址", "排班",
    ]):
        return "optimization"
    if any(k in t for k in ["分类", "classification", "聚类", "cluster", "分群"]):
        return "classification"
    if any(k in t for k in ["评价", "评估", "evaluation", "rank", "排序", "决策", "优选"]):
        return "evaluation"
    if any(k in t for k in ["网络", "图", "路径", "最短", "路由", "network", "graph"]):
        return "graph_network"
    if any(k in t for k in ["仿真", "模拟", "动态", "扩散", "传播", "simulation"]):
        return "simulation"
    return "general"


# 题型 → 建模范式与候选方法族（专家记忆，离线可跑，不依赖 LLM）
_TYPE_PARADIGM = {
    "prediction": ("时间序列/回归预测", ["ARIMA", "指数平滑", "Prophet", "灰色预测", "LSTM", "线性回归"]),
    "regression": ("回归拟合", ["线性回归", "岭回归", "Lasso", "逻辑回归"]),
    "optimization": ("约束优化", ["线性规划", "整数规划", "非线性规划", "遗传算法", "粒子群", "模拟退火", "差分进化"]),
    "classification": ("分类/聚类", ["SVM", "决策树", "随机森林", "KNN", "K-Means", "DBSCAN"]),
    "evaluation": ("综合评价", ["AHP", "TOPSIS", "熵权法", "灰色关联", "模糊综合评价", "主成分分析"]),
    "graph_network": ("图与网络", ["Dijkstra 最短路", "最大流", "排队论", "蒙特卡洛"]),
    "simulation": ("系统仿真", ["系统动力学", "元胞自动机", "离散事件仿真", "基于智能体仿真", "蒙特卡洛"]),
    "general": ("通用建模", ["综合评价", "回归", "优化", "分类"]),
}

# 题型 → 常见问题理解检查项
_TYPE_OBJECTIVE_HINT = {
    "prediction": "预测未来时刻的目标量，并给出置信/误差估计",
    "regression": "量化自变量对因变量的函数关系并检验显著性",
    "optimization": "在约束下求目标最优（最大收益/最小成本等）",
    "classification": "将样本划分到已知类别或发现自然簇",
    "evaluation": "构造指标体系对方案综合评价与排序",
    "graph_network": "刻画网络结构与流量/路径最优",
    "simulation": "刻画系统动态演化并评估政策/参数效应",
    "general": "将实际问题抽象为可计算结构",
}


# ─────────────────────────────────────────────────────────────
# 规则检查清单（离线 critic）
# ─────────────────────────────────────────────────────────────
_UNDERSTAND_CHECKLIST = [
    ("identifies_type", "应判断题型/建模范式", 2.0),
    ("states_objectives", "应明确研究目标/待求量", 2.0),
    ("states_givens", "应列出已知条件/数据", 1.5),
    ("states_constraints", "应识别约束/边界条件", 1.5),
    ("states_assumptions", "应提出关键假设", 1.5),
    ("defines_unknowns", "应区分已知与未知", 1.5),
]

_PLAN_CHECKLIST = [
    ("states_paradigm", "应明确建模范式", 2.0),
    ("lists_methods", "应给出候选方法族", 2.0),
    ("maps_variables", "应把问题与变量/目标对应", 2.0),
    ("states_validation", "应说明验证/敏感性思路", 2.0),
    ("consistent_type", "应与题型一致", 2.0),
]


def _rule_understanding_actor(problem_description: str, data_description: Optional[str],
                              problem_type: str, prior_feedback: Optional[str]) -> str:
    obj = _TYPE_OBJECTIVE_HINT.get(problem_type, _TYPE_OBJECTIVE_HINT["general"])
    body = (
        f"一、题型判断\n本题偏向「{problem_type}」类建模问题。\n\n"
        f"二、研究目标\n{obj}。\n\n"
        f"三、已知条件/数据\n{data_description or '（未提供，需从题目中提取或假设可获取）'}\n\n"
        f"四、待求量/决策变量\n需明确输出什么（预测值/最优解/分类标签/综合得分等）。\n\n"
        f"五、约束与边界\n识别物理、资源、时间或伦理约束。\n\n"
        f"六、关键假设\n1) 数据可获取且具代表性；2) 忽略高阶噪声；3) 模型结构合理可解。\n\n"
        f"七、已知与未知\n列出已知输入与需估计的未知量。\n"
    )
    if prior_feedback:
        body += f"\n八、依据上一轮反馈的改进\n{prior_feedback}\n"
    return body


def _rule_plan_actor(problem_description: str, problem_type: str,
                     prior_feedback: Optional[str],
                     data_description: Optional[str] = None) -> str:
    paradigm, methods = _TYPE_PARADIGM.get(problem_type, _TYPE_PARADIGM["general"])
    body = (
        f"一、建模范式\n建议采用「{paradigm}」范式。\n\n"
        f"二、候选方法族\n{ '、'.join(methods) }（具体选型交由 HMML 层次化检索确定）。\n\n"
        f"三、变量与目标映射\n将题目实体映射为决策变量 X 与目标 Y，目标函数记为 F(X)。\n\n"
        f"四、求解与验证思路\n1) 数据预处理；2) 模型拟合/优化求解；"
        "3) 残差/误差分析；4) 敏感性分析；5) 多模型对比。\n\n"
        f"五、风险提示\n注意过拟合、量纲、假设偏离现实等风险。\n"
    )
    if prior_feedback:
        body += f"\n六、依据上一轮反馈的改进\n{prior_feedback}\n"
    return body


def _rule_critic_understanding(text: str) -> (float, str):
    checks = {
        "identifies_type": bool(re.search(r"题型|范式|类建模|偏向", text)),
        "states_objectives": bool(re.search(r"目标|待求|预测|最优|分类|评价|排序", text)),
        "states_givens": ("已知条件" in text or "数据" in text),
        "states_constraints": ("约束" in text or "边界" in text),
        "states_assumptions": ("假设" in text),
        "defines_unknowns": ("未知" in text or "已知" in text),
    }
    score = 0.0
    defects: List[str] = []
    for key, desc, weight in _UNDERSTAND_CHECKLIST:
        if checks.get(key):
            score += weight
        else:
            defects.append(f"[{desc}] 未满足")
    score = round(min(score, 10.0), 2)
    critique = (f"评分 {score}/10。缺陷：；".join(defects) + "。") if defects else f"评分 {score}/10。理解完整。"
    return score, critique


def _rule_critic_plan(text: str, problem_type: str) -> (float, str):
    _, methods = _TYPE_PARADIGM.get(problem_type, _TYPE_PARADIGM["general"])
    checks = {
        "states_paradigm": ("范式" in text or "建模" in text),
        "lists_methods": any(m in text for m in methods),
        "maps_variables": ("变量" in text or "X" in text or "目标函数" in text),
        "states_validation": ("验证" in text or "敏感性" in text or "残差" in text),
        "consistent_type": (problem_type in text or _TYPE_PARADIGM.get(problem_type, ("",))[0] in text),
    }
    score = 0.0
    defects: List[str] = []
    for key, desc, weight in _PLAN_CHECKLIST:
        if checks.get(key):
            score += weight
        else:
            defects.append(f"[{desc}] 未满足")
    score = round(min(score, 10.0), 2)
    critique = (f"评分 {score}/10。缺陷：；".join(defects) + "。") if defects else f"评分 {score}/10。方案完整。"
    return score, critique


def _rule_improvement(stage: str, critique: str, defects: List[str]) -> str:
    if not defects:
        return "维持当前版本（critic 未提出必须修改的缺陷）。"
    defect = defects[0].split("]")[0].lstrip("[") if "]" in defects[0] else ""
    table = {
        "identifies_type": "补充：明确本题所属建模范式与题型。",
        "states_objectives": "补充：写出具体研究目标与待求量。",
        "states_givens": "补充：列出题目给出的已知条件与数据。",
        "states_constraints": "补充：写出关键约束与边界条件。",
        "states_assumptions": "补充：列出至少 3 条建模假设。",
        "defines_unknowns": "补充：区分已知输入与需估计的未知量。",
        "states_paradigm": "补充：写明采用的建模范式。",
        "lists_methods": "补充：给出候选方法族（可引用 HMML 检索结果）。",
        "maps_variables": "补充：将问题实体映射为变量与目标函数。",
        "states_validation": "补充：说明验证与敏感性分析思路。",
        "consistent_type": "补充：使方案与判定题型保持一致。",
    }
    return table.get(defect, "补充：依据批评意见完善表述。")


# ─────────────────────────────────────────────────────────────
# 精炼器
# ─────────────────────────────────────────────────────────────
class ProblemAnalysisRefiner:
    """问题分析 actor-critic 精炼器（层2）。

    默认离线（rule_fallback）；提供 llm_call 时进入 hybrid/pure_llm，
    LLM 调用异常自动降级规则，保证离线可跑、可控、不伪造。
    """

    def __init__(self, llm_call: Optional[Callable[[Dict[str, Any]], Any]] = None):
        self.llm_call = llm_call
        self._llm_used = False

    # ── 内部：actor / critic / improvement 的统一分发（两段共用） ──
    def _dispatch(self, role: str, payload: Dict[str, Any], rule_fn: Callable[..., str],
                  use_llm: bool) -> str:
        if use_llm and self.llm_call is not None:
            try:
                req = {"role": role, **payload}
                resp = self.llm_call(req)
                if isinstance(resp, dict):
                    text = resp.get("content") or resp.get("text") or resp.get("output")
                    if isinstance(text, str) and text.strip():
                        self._llm_used = True
                        return text
                elif isinstance(resp, str) and resp.strip():
                    self._llm_used = True
                    return resp
            except Exception:
                pass
        return rule_fn(**payload)

    def _improve(self, stage_name: str, current: str, critique: str,
                 defects: List[str], use_llm: bool) -> str:
        """规则 improvement 的统一分发（LLM 优先，异常降级规则）。"""
        if use_llm and self.llm_call is not None:
            try:
                role = "understanding_improvement" if stage_name == "understanding" else "plan_improvement"
                resp = self.llm_call({"role": role, "approach": current, "critique": critique})
                if isinstance(resp, dict):
                    text = resp.get("content") or resp.get("text") or resp.get("improvement")
                    if isinstance(text, str) and text.strip():
                        self._llm_used = True
                        return text
                elif isinstance(resp, str) and resp.strip():
                    self._llm_used = True
                    return resp
            except Exception:
                pass
        return _rule_improvement(stage_name, critique, defects)

    def _stage(self, stage_name: str, problem_description: str, data_description: Optional[str],
               problem_type: str, rounds: int, use_llm: bool) -> AnalysisStage:
        is_understand = stage_name == "understanding"
        prior: Optional[str] = None
        current = self._dispatch(
            "understanding_actor" if is_understand else "plan_actor",
            {
                "problem_description": problem_description,
                "data_description": data_description,
                "problem_type": problem_type,
                "prior_feedback": prior,
            },
            _rule_understanding_actor if is_understand else _rule_plan_actor,
            use_llm,
        )
        history: List[AnalysisRound] = []
        for r in range(1, rounds + 1):
            if is_understand:
                score, critique = _rule_critic_understanding(current)
                crit_fn = _rule_critic_understanding
            else:
                score, critique = _rule_critic_plan(current, problem_type)
                def _crit_fn(t, _pt=problem_type):
                    return _rule_critic_plan(t, _pt)
                crit_fn = _crit_fn
            _, rule_critique = crit_fn(current)
            defects = [d for d in rule_critique.split("；") if d.startswith("[")]
            if r < rounds:
                improvement = self._improve(stage_name, current, critique, defects, use_llm)
                prior = improvement
                current = self._dispatch(
                    "understanding_actor" if is_understand else "plan_actor",
                    {
                        "problem_description": problem_description,
                        "data_description": data_description,
                        "problem_type": problem_type,
                        "prior_feedback": improvement,
                    },
                    _rule_understanding_actor if is_understand else _rule_plan_actor,
                    use_llm,
                )
            else:
                improvement = "（末轮，无需再改进）"
            history.append(AnalysisRound(
                round=r, actor_output=current, critic_output=critique,
                critic_score=score, improvement=improvement,
            ))
        return AnalysisStage(
            stage=stage_name, rounds=rounds,
            final_output=history[-1].actor_output, history=history,
            final_score=history[-1].critic_score,
        )

    def analyze(self, problem_description: str, data_description: Optional[str] = None,
                rounds: int = 2, problem_id: str = "",
                llm_call: Optional[Callable[[Dict[str, Any]], Any]] = None,
                pure_llm: bool = False) -> ProblemAnalysis:
        """执行层2 精炼：问题理解 → 建模方案（每段 actor-critic-improvement）。

        Args:
            problem_description: 题目/任务描述。
            data_description: 数据描述（可选）。
            rounds: 每段精炼轮数（对应 MM-Agent 的 round=3，默认 2 兼顾成本）。
            problem_id: 题目标识。
            llm_call: 可选 LLM 回调；提供则 hybrid（pure_llm=True 每段走 LLM）。
            pure_llm: 为 True 且提供 llm_call 时，actor/critic/improvement 均优先用 LLM。
        Returns:
            ProblemAnalysis
        """
        if llm_call is not None:
            self.llm_call = llm_call
        use_llm = self.llm_call is not None
        self._llm_used = False
        problem_type = _heuristic_problem_type(problem_description)
        rounds = max(1, int(rounds))

        understanding = self._stage("understanding", problem_description, data_description,
                                    problem_type, rounds, use_llm)
        modeling_plan = self._stage("modeling_plan", problem_description, data_description,
                                    problem_type, rounds, use_llm)

        rid = "PAR-" + hashlib.md5(
            (problem_description + "|" + (problem_type or "")).encode("utf-8")
        ).hexdigest()[:8]
        return ProblemAnalysis(
            analysis_id=rid, problem_id=problem_id, problem_type=problem_type,
            understanding=understanding, modeling_plan=modeling_plan,
            metadata={
                "used_llm": self._llm_used,
                "pure_llm": bool(pure_llm and use_llm),
                "understand_score": understanding.final_score,
                "plan_score": modeling_plan.final_score,
            },
        )

    def save(self, analysis: ProblemAnalysis, output_path: str) -> None:
        from pathlib import Path
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(asdict(analysis), f, ensure_ascii=False, indent=2)


def analyze_problem(problem_description: str, data_description: Optional[str] = None,
                    rounds: int = 2, llm_call: Optional[Callable[[Dict[str, Any]], Any]] = None,
                    problem_id: str = "") -> ProblemAnalysis:
    """一行式问题分析精炼。"""
    return ProblemAnalysisRefiner(llm_call=llm_call).analyze(
        problem_description, data_description=data_description, rounds=rounds, problem_id=problem_id,
    )


__all__ = [
    "AnalysisRound",
    "AnalysisStage",
    "ProblemAnalysis",
    "ProblemAnalysisRefiner",
    "analyze_problem",
]
