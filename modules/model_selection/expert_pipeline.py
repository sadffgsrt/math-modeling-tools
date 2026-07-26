# 专家级建模流水线（串联 MM-Agent 层2/3/4/6/7，离线优先）
#
# 把分散的「专家机制」串成一条可人审的工作流：
#   层2 问题分析精炼 → 层3 层次化分解 → 层4 方法检索 → 层6 公式精炼 → 层5/7 DAG 排序与记忆传递
#
# 设计原则（契合本平台「确定性、可控、离线、人主导」）：
#   - 默认全离线（规则 fallback），每一步都可单独调用与人审；
#   - 可选 llm_call 注入 LLM 增强（层2/层6），异常自动降级规则；
#   - 不复制 MM-Agent 任何 CC BY-NC 提示词/代码，纯自研 MIT。
#
# 仅依赖本包内模块 + 标准库（json/hashlib）。

import json
from dataclasses import dataclass, field, asdict
from typing import Any, Callable, Dict, List, Optional

from .problem_analysis_refiner import ProblemAnalysisRefiner, ProblemAnalysis
from .problem_decomposition import ProblemDecomposer, Decomposition
from .hierarchical_selector import HierarchicalMethodSelector, HierarchicalSelection
from .formula_refiner import FormulaRefiner, FormulaRefinement


# 题型 → 检索用数据特征（喂给 HMML 选择器的方法类匹配）
_TYPE_FEATURES = {
    "evaluation": {"is_evaluation": True},
    "prediction": {"has_time_series": True},
    "regression": {"has_labels": True},
    "optimization": {"is_optimization": True},
    "classification": {"has_labels": True},
    "graph_network": {},
    "simulation": {},
    "general": {},
}


@dataclass
class ExpertPlan:
    """专家级建模流水线的完整产出。"""
    plan_id: str
    problem_id: str
    analysis: ProblemAnalysis
    decomposition: Decomposition
    selection: HierarchicalSelection
    refinement: FormulaRefinement
    dag_results: Dict[str, Dict[str, Any]]
    metadata: Dict = field(default_factory=dict)

    def summary(self) -> str:
        lines = []
        lines.append(f"# 专家级建模方案（{self.plan_id}）")
        lines.append(f"- 题型：{self.analysis.problem_type}")
        lines.append(f"- 问题理解评分：{self.analysis.understanding.final_score}/10｜方案评分：{self.analysis.modeling_plan.final_score}/10")
        lines.append(f"- 子任务拆解（{self.decomposition.tasknum} 步）：")
        for t in self.decomposition.tasks:
            lines.append(f"    {t.task_id} {t.title}（{t.phase}）依赖={t.depends_on}")
        lines.append(f"- 推荐建模方法（Top {self.selection.top_k}）：")
        for r in self.selection.ranked_methods:
            lines.append(f"    {r.method}（{r.domain}/{r.subdomain}，得分 {r.score}）")
        lines.append(f"- 公式精炼：{self.refinement.metadata.get('final_score', 0)}/10，共 {self.refinement.rounds} 轮")
        lines.append(f"- DAG 执行：{len(self.dag_results)} 个节点，"
                     f"成功 {sum(1 for v in self.dag_results.values() if v.get('status')=='success')} 个")
        return "\n".join(lines)

    def save(self, output_path: str) -> None:
        from pathlib import Path
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump({
                "plan_id": self.plan_id,
                "problem_id": self.problem_id,
                "analysis": asdict(self.analysis),
                "decomposition": asdict(self.decomposition),
                "selection": asdict(self.selection),
                "refinement": asdict(self.refinement),
                "dag_results": self.dag_results,
                "metadata": self.metadata,
            }, f, ensure_ascii=False, indent=2)


class ExpertPipeline:
    """专家级建模流水线编排器。"""

    def __init__(self, hmml_path: Optional[str] = None,
                 llm_call: Optional[Callable[[Dict[str, Any]], Any]] = None):
        self.selector = HierarchicalMethodSelector(hmml_path)
        self.decomposer = ProblemDecomposer()
        self.llm_call = llm_call

    def run(self, problem_description: str, data_description: Optional[str] = None,
            data_features: Optional[Dict] = None, tasknum: Optional[int] = None,
            top_k: int = 6, analysis_rounds: int = 2, formula_rounds: int = 2,
            problem_id: str = "", llm_call: Optional[Callable[[Dict[str, Any]], Any]] = None,
            pure_llm: bool = False) -> ExpertPlan:
        """端到端跑通专家级建模流水线。

        Args:
            problem_description: 题目/任务描述。
            data_description: 数据描述文本（可选）。
            data_features: 检索用数据特征（不传则按题型自动推断）。
            tasknum: 期望子任务数（不传则按题型默认粒度）。
            top_k: HMML 检索返回方法数。
            analysis_rounds / formula_rounds: 层2 / 层6 精炼轮数。
            problem_id: 题目标识。
            llm_call: 可选 LLM 回调，注入层2/层6 的 hybrid 增强。
            pure_llm: 为 True 且提供 llm_call 时，层2/层6 每段走 LLM。
        Returns:
            ExpertPlan
        """
        llm = llm_call or self.llm_call

        # 层2：问题分析精炼
        analysis = ProblemAnalysisRefiner(llm_call=llm).analyze(
            problem_description, data_description=data_description,
            rounds=analysis_rounds, problem_id=problem_id, pure_llm=pure_llm,
        )

        # 层3：层次化分解
        decomposition = self.decomposer.decompose(
            problem_description, tasknum=tasknum, problem_type=analysis.problem_type,
            problem_id=problem_id,
        )

        # 层4：方法检索（按题型推断特征，除非显式给定）
        feats = data_features if data_features is not None else _TYPE_FEATURES.get(
            analysis.problem_type, {})
        selection = self.selector.retrieve(
            problem_description, data_features=feats, top_k=top_k, problem_id=problem_id,
        )

        # 层6：公式精炼（候选方法来自检索结果）
        candidate_methods = [r.method for r in selection.ranked_methods]
        refinement = FormulaRefiner(llm_call=llm).refine(
            problem_description, candidate_methods=candidate_methods,
            data_description=data_description, rounds=formula_rounds,
            problem_id=problem_id, pure_llm=pure_llm,
        )

        # 层5/7：DAG 排序 + 任务间记忆传递
        dag_results = self._run_dag(decomposition, selection, refinement, analysis)

        from hashlib import md5
        pid = "EXPERT-" + md5((problem_description + "|" + (problem_id or "")).encode("utf-8")).hexdigest()[:8]
        return ExpertPlan(
            plan_id=pid, problem_id=problem_id, analysis=analysis,
            decomposition=decomposition, selection=selection, refinement=refinement,
            dag_results=dag_results,
            metadata={
                # 仅当层2/层6 真正成功调用 LLM 才记为 True（异常降级时为 False）
                "used_llm": bool(analysis.metadata.get("used_llm") or refinement.metadata.get("used_llm")),
                "pure_llm": bool(pure_llm and llm is not None),
                "data_features": feats,
            },
        )

    def _run_dag(self, decomposition: Decomposition, selection: HierarchicalSelection,
                 refinement: FormulaRefinement, analysis: ProblemAnalysis) -> Dict[str, Dict[str, Any]]:
        """按分解的依赖图执行节点，节点间经 memory 传递上游产物（层7）。"""
        from modules.orchestration import DAGExecutor, build_dependency_context

        recommended = [r.method for r in selection.ranked_methods[:3]]
        graph = decomposition.to_dag_graph()
        ex = DAGExecutor(graph=graph)

        for t in decomposition.tasks:
            # 用闭包捕获当前子任务信息
            def make_node(task=t, rec=recommended):
                def node(memory):
                    ctx = build_dependency_context(memory, graph.get(task.task_id, []))
                    rec_models = rec if task.phase in ("modeling", "solve") else []
                    payload = {
                        "task": task.title,
                        "phase": task.phase,
                        "description": task.description,
                        "method_hint": task.method_hint,
                        "recommended_models": rec_models,
                        "has_upstream_context": bool(ctx),
                    }
                    # 以节点名为主键存入共享 memory，供下游任务（层7）读取前置产物
                    memory[task.task_id] = payload
                    return {task.task_id: payload}
                return node
            ex.add_node(t.task_id, make_node())

        results = ex.run(fallback_linear=True)
        # 解包：把 {task_id: payload} 还原为可直接阅读的 output
        dag_results: Dict[str, Dict[str, Any]] = {}
        for name, val in results.items():
            out = val.get("output") or {}
            unwrapped = out.get(name, out)
            dag_results[name] = {**val, "output": unwrapped}
        return dag_results


def run_expert_pipeline(problem_description: str, data_description: Optional[str] = None,
                        data_features: Optional[Dict] = None, tasknum: Optional[int] = None,
                        top_k: int = 6, analysis_rounds: int = 2, formula_rounds: int = 2,
                        llm_call: Optional[Callable[[Dict[str, Any]], Any]] = None,
                        problem_id: str = "") -> ExpertPlan:
    """一行式专家级建模流水线。"""
    return ExpertPipeline().run(
        problem_description, data_description=data_description, data_features=data_features,
        tasknum=tasknum, top_k=top_k, analysis_rounds=analysis_rounds,
        formula_rounds=formula_rounds, llm_call=llm_call, problem_id=problem_id,
    )


__all__ = [
    "ExpertPlan",
    "ExpertPipeline",
    "run_expert_pipeline",
]
