# 公式 actor-critic 精炼器（MM-Agent 移植，离线优先）
#
# 设计参考 MM-Agent 的 formula actor-critic 精炼循环：
#   mathematical_modeling() 内部走 actor → critic → improvement 的 round 轮循环，
#   每轮由 actor 生成建模公式/思路，critic 评分并指出缺陷，再基于反馈改进。
#
# 本实现（纯自研、MIT，不复制 MM-Agent 任何 CC BY-NC 提示词/代码）：
#   - 默认 rule_fallback：用确定性模板 + 规则检查清单离线完成精炼，无需任何外部依赖；
#   - hybrid / pure_llm：通过可选的 llm_call(req)->resp 回调接入 LLM，失败时自动降级为规则；
#   - 输出结构化 FormulaRefinement（每轮 actor 产出 / critic 评分 / 改进），便于沉淀与人审。
#
# 依赖：仅标准库（dataclasses/json/re/hashlib），保证离线可 import。

import hashlib
import json
import re
from dataclasses import dataclass, field, asdict
from typing import Any, Callable, Dict, List, Optional


# ─────────────────────────────────────────────────────────────
# 数据结构
# ─────────────────────────────────────────────────────────────
@dataclass
class FormulaRound:
    """单轮 actor-critic 精炼记录。"""
    round: int
    actor_output: str          # 本轮 actor 生成的建模思路/公式
    critic_output: str         # 本轮 critic 的评分与缺陷指摘
    critic_score: float        # 0~10
    improvement: str           # 基于 critic 反馈的修订说明（最后一轮为空）


@dataclass
class FormulaRefinement:
    """actor-critic 精炼的完整结果。"""
    refiner_id: str
    problem_id: str
    rounds: int
    final_approach: str        # 最终建模思路/公式文本
    candidate_methods: List[str]
    critiques: List[str]       # 各轮 critic 文本汇总
    history: List[FormulaRound]
    metadata: Dict = field(default_factory=dict)


# ─────────────────────────────────────────────────────────────
# 规则检查清单（离线 critic）
# ─────────────────────────────────────────────────────────────
# 每个检查项：命中则给分 + 不报缺陷；未命中则扣分 + 记入缺陷。
_CHECKLIST = [
    ("defines_variables", "应明确定义决策变量 / 参数符号", 2.0),
    ("states_objective", "应陈述建模目标或目标函数", 2.0),
    ("states_assumptions", "应列出关键假设", 1.5),
    ("has_formula", "应包含数学公式/表达式", 2.0),
    ("consistent_methods", "应与候选方法（如已给出）保持一致", 1.5),
    ("uses_data", "若提供了数据描述，应说明数据如何进入模型", 1.0),
]


def _heuristic_problem_type(text: str) -> str:
    """轻量题型启发式（用于规则 actor 的模板选择）。"""
    t = (text or "").lower()
    if any(k in t for k in ["预测", "forecast", "predict", "time series", "时间序列"]):
        return "prediction"
    if any(k in t for k in ["回归", "regression", "拟合", "fit"]):
        return "regression"
    if any(k in t for k in [
        "优化", "optimize", "optimization", "最小", "最大", "调度", "规划",
        "linear programming", "lp",
    ]):
        return "optimization"
    if any(k in t for k in ["分类", "classification", "聚类", "cluster"]):
        return "classification"
    if any(k in t for k in ["评价", "评估", "evaluation", "rank", "排序", "决策"]):
        return "evaluation"
    return "general"


def _rule_actor(problem_description: str, candidate_methods: List[str],
                data_description: Optional[str], problem_type: str,
                prior_feedback: Optional[str]) -> str:
    """规则 actor：基于题型模板 + 候选方法生成结构化建模思路。

    若 prior_feedback 非空（上一轮 critic 反馈），则在末尾显式引用以体现改进。
    """
    methods_line = ""
    if candidate_methods:
        methods_line = "候选建模方法：" + "、".join(candidate_methods) + "。\n"

    type_specific = {
        "prediction": (
            "目标：基于历史数据对未来进行预测。\n"
            "建议建立时间序列或回归模型，刻画变量间依赖关系并对未来时刻外推。"
        ),
        "regression": (
            "目标：拟合自变量与因变量之间的函数关系。\n"
            "建议构建回归模型，量化各特征对输出的贡献并给出显著性检验。"
        ),
        "optimization": (
            "目标：在约束条件下寻求目标最优（最大/最小）。\n"
            "建议定义决策变量与目标函数，列出约束集，选用合适的优化算法求解。"
        ),
        "classification": (
            "目标：将样本划分到已知类别。\n"
            "建议构建分类/聚类模型，明确特征空间与判别边界。"
        ),
        "evaluation": (
            "目标：对若干方案进行综合评价与排序。\n"
            "建议构造评价指标体系，确定权重并融合得到综合得分。"
        ),
        "general": (
            "目标：将实际问题抽象为可计算的数学结构。\n"
            "建议结合问题特征选择建模范式，明确变量、关系与目标。"
        ),
    }.get(problem_type, "目标：将实际问题抽象为可计算的数学结构。")

    data_line = ""
    if data_description:
        data_line = f"数据说明：{data_description}\n建模时应将以上数据作为样本/约束输入模型。\n"

    body = (
        f"一、问题理解\n{problem_description[:200]}\n\n"
        f"二、建模目标与范式\n{type_specific}\n\n"
        f"三、候选方法\n{methods_line}"
        f"四、变量与目标\n设决策变量/特征为 X，目标量为 Y；"
        "目标函数记为 F(X)，需结合问题明确其形式。\n\n"
        f"五、关键假设\n1) 数据可获取且具代表性；2) 模型结构合理可解；3) 忽略高阶噪声。\n\n"
        f"六、数据接入\n{data_line}"
        "七、建议公式骨架\n"
        "min/max  F(X)  s.t.  g_i(X) ≤ 0,  h_j(X) = 0  （按问题替换为回归/预测形式）。\n"
    )
    if prior_feedback:
        body += f"\n八、依据上一轮反馈的改进\n{prior_feedback}\n"
    return body


def _rule_critic(approach: str, candidate_methods: List[str],
                 data_description: Optional[str]) -> (float, str):
    """规则 critic：按检查清单给分并指出缺陷。返回 (score 0~10, critique_text)。"""
    text = approach or ""
    defects: List[str] = []
    score = 0.0

    checks = {
        "defines_variables": bool(re.search(r"变量|决策变量|特征|X|参数", text)),
        "states_objective": bool(re.search(r"目标|最优|min|max|预测|拟合|分类|评价|排序", text)),
        "states_assumptions": ("假设" in text),
        "has_formula": bool(re.search(r"[=≤≥<>\+\-*/^][A-Za-z0-9_]|∑|∫|min|max|s\.t\.|frac|matrix", text)),
        "consistent_methods": (not candidate_methods) or any(m in text for m in candidate_methods),
        "uses_data": (not data_description) or ("数据" in text),
    }

    for key, desc, weight in _CHECKLIST:
        if checks.get(key):
            score += weight
        else:
            defects.append(f"[{desc}] 未满足")

    score = round(min(score, 10.0), 2)
    if defects:
        critique = f"评分 {score}/10。存在缺陷：；".join(defects) + "。"
    else:
        critique = f"评分 {score}/10。结构完整，无明显缺陷。"
    return score, critique


def _rule_improvement(approach: str, critique: str, defects: List[str]) -> str:
    """规则 improvement：针对首条缺陷追加补充段落，体现“依据批评改进”。"""
    if not defects:
        return "维持当前版本（critic 未提出必须修改的缺陷）。"
    defect = defects[0]
    target = defect.split("]")[0].lstrip("[") if "]" in defect else ""
    supplement = {
        "defines_variables": "补充：显式定义决策变量 x_i 及其量纲与取值范围。",
        "states_objective": "补充：写明目标函数 F(X) 的优化方向（最大/最小）。",
        "states_assumptions": "补充：列出至少 3 条建模假设并说明其合理性。",
        "has_formula": "补充：给出核心数学公式（目标/约束/递推形式）。",
        "consistent_methods": "补充：将候选方法映射到模型步骤，保证一致性。",
        "uses_data": "补充：说明数据如何作为样本或约束进入模型。",
    }.get(target, "补充：依据批评意见完善建模表述。")
    return supplement


# ─────────────────────────────────────────────────────────────
# 精炼器
# ─────────────────────────────────────────────────────────────
class FormulaRefiner:
    """公式 actor-critic 精炼器。

    默认离线（rule_fallback）；提供 llm_call 时进入 hybrid/pure_llm，
    LLM 调用异常会自动降级为规则，保证“离线可跑、可控、不伪造”。
    """

    def __init__(self, llm_call: Optional[Callable[[Dict[str, Any]], Any]] = None):
        self.llm_call = llm_call
        self._llm_used = False  # 标记 LLM 是否真正成功参与（失败则保持 False）

    # ── 内部：actor / critic / improvement 的统一分发 ──
    def _actor(self, problem_description, candidate_methods, data_description,
               problem_type, prior_feedback, use_llm):
        if use_llm and self.llm_call is not None:
            try:
                req = {
                    "role": "formula_actor",
                    "problem_description": problem_description,
                    "candidate_methods": candidate_methods,
                    "data_description": data_description,
                    "problem_type": problem_type,
                    "prior_feedback": prior_feedback,
                }
                resp = self.llm_call(req)
                if isinstance(resp, dict):
                    text = resp.get("content") or resp.get("text") or resp.get("approach")
                    if isinstance(text, str) and text.strip():
                        self._llm_used = True
                        return text
                elif isinstance(resp, str) and resp.strip():
                    self._llm_used = True
                    return resp
            except Exception:
                pass  # 降级规则
        return _rule_actor(problem_description, candidate_methods, data_description,
                           problem_type, prior_feedback)

    def _critic(self, approach, candidate_methods, data_description, use_llm):
        if use_llm and self.llm_call is not None:
            try:
                req = {
                    "role": "formula_critic",
                    "approach": approach,
                    "candidate_methods": candidate_methods,
                    "data_description": data_description,
                }
                resp = self.llm_call(req)
                # 解析：期望返回 {"score": float, "critique": str} 或纯文本
                if isinstance(resp, dict):
                    score = resp.get("score")
                    critique = resp.get("critique") or resp.get("text") or resp.get("content")
                    if isinstance(score, (int, float)) and isinstance(critique, str):
                        self._llm_used = True
                        return round(min(max(float(score), 0.0), 10.0), 2), critique
                elif isinstance(resp, str) and resp.strip():
                    # 纯文本：用规则评分兜底，文本作为批评
                    self._llm_used = True
                    s, _ = _rule_critic(approach, candidate_methods, data_description)
                    return s, resp
            except Exception:
                pass
        return _rule_critic(approach, candidate_methods, data_description)

    def _improve(self, approach, critique, defects, use_llm):
        if use_llm and self.llm_call is not None:
            try:
                req = {
                    "role": "formula_improvement",
                    "approach": approach,
                    "critique": critique,
                }
                resp = self.llm_call(req)
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
        return _rule_improvement(approach, critique, defects)

    # ── 主入口 ──
    def refine(self, problem_description: str,
               candidate_methods: Optional[List[str]] = None,
               data_description: Optional[str] = None,
               rounds: int = 2,
               problem_id: str = "",
               llm_call: Optional[Callable[[Dict[str, Any]], Any]] = None,
               pure_llm: bool = False) -> FormulaRefinement:
        """执行 actor → critic → improvement 的 round 轮精炼。

        Args:
            problem_description: 题目/任务描述。
            candidate_methods: 候选方法名列表（来自 HMML 选择器等），可为空。
            data_description: 数据描述文本，可为空。
            rounds: 精炼轮数（对应 MM-Agent 的 task_formulas_round）。
            problem_id: 题目标识，用于结果 id。
            llm_call: 可选 LLM 回调；提供则 hybrid（pure_llm=True 时每轮都走 LLM）。
            pure_llm: 为 True 且提供 llm_call 时，actor/critic/improvement 均优先用 LLM。
        Returns:
            FormulaRefinement
        """
        if llm_call is not None:
            self.llm_call = llm_call
        use_llm = self.llm_call is not None
        self._llm_used = False  # 每轮精炼开始时重置，仅当 LLM 真正成功参与才置 True
        candidate_methods = candidate_methods or []
        problem_type = _heuristic_problem_type(problem_description)

        rounds = max(1, int(rounds))
        history: List[FormulaRound] = []
        critiques: List[str] = []
        prior_feedback: Optional[str] = None
        current_approach = self._actor(problem_description, candidate_methods,
                                       data_description, problem_type, None, use_llm)

        for r in range(1, rounds + 1):
            score, critique = self._critic(current_approach, candidate_methods,
                                           data_description, use_llm)
            critiques.append(critique)
            # 解析缺陷用于 improvement（规则模式可重算）
            _, rule_critique = _rule_critic(current_approach, candidate_methods, data_description)
            defects = [d for d in rule_critique.split("；") if d.startswith("[")]

            if r < rounds:
                improvement = self._improve(current_approach, critique, defects, use_llm)
                prior_feedback = improvement
                # 下一轮 actor 携带改进反馈（hybrid/pure_llm 走 LLM，否则规则模板引用）
                current_approach = self._actor(
                    problem_description, candidate_methods, data_description,
                    problem_type, improvement, use_llm
                )
            else:
                improvement = "（末轮，无需再改进）"

            history.append(FormulaRound(
                round=r,
                actor_output=current_approach,
                critic_output=critique,
                critic_score=score,
                improvement=improvement,
            ))

        final = history[-1].actor_output if history else current_approach
        rid = "FAC-" + hashlib.md5(
            (problem_description + "|" + "|".join(candidate_methods)).encode("utf-8")
        ).hexdigest()[:8]

        return FormulaRefinement(
            refiner_id=rid,
            problem_id=problem_id,
            rounds=rounds,
            final_approach=final,
            candidate_methods=candidate_methods,
            critiques=critiques,
            history=history,
            metadata={
                "problem_type": problem_type,
                "used_llm": self._llm_used,
                "pure_llm": bool(pure_llm and use_llm),
                "final_score": history[-1].critic_score if history else 0.0,
            },
        )

    def save(self, refinement: FormulaRefinement, output_path: str) -> None:
        from pathlib import Path
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(asdict(refinement), f, ensure_ascii=False, indent=2)


# ─────────────────────────────────────────────────────────────
# 便捷入口
# ─────────────────────────────────────────────────────────────
def refine_formulas(problem_description: str,
                    candidate_methods: Optional[List[str]] = None,
                    data_description: Optional[str] = None,
                    rounds: int = 2,
                    llm_call: Optional[Callable[[Dict[str, Any]], Any]] = None,
                    problem_id: str = "") -> FormulaRefinement:
    """一行式精炼：返回 FormulaRefinement。"""
    return FormulaRefiner(llm_call=llm_call).refine(
        problem_description,
        candidate_methods=candidate_methods,
        data_description=data_description,
        rounds=rounds,
        problem_id=problem_id,
    )


__all__ = [
    "FormulaRound",
    "FormulaRefinement",
    "FormulaRefiner",
    "refine_formulas",
]
