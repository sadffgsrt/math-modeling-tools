# MM-Bench 式赛题基准（MM-Agent 移植，离线优先）
#
# 设计参考 MM-Agent 的 MMBench：
#   - 一组历年赛题 JSON（background / problem_requirement / dataset_description /
#     variable_description）+ 评估脚本；原版需 OpenAI key 评分，且数据 CC BY-NC。
# 本实现（纯自研、MIT）：
#   - 自研代表性赛题 fixture（不复制 MM-Bench 数据），覆盖评价/预测/优化/分类四类；
#   - 离线确定性 harness：对每道题跑「层次化方法选择 + 公式 actor-critic 精炼」，
#     再用规则自审查（self-review）判定“能否跑通 + 产物合格”，无需任何外部密钥；
#   - 输出逐题结果与汇总，便于把赛题当回归基准持续跟踪。

import json
import os
import sys
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Dict, List, Optional

# 将仓库根加入 sys.path（tests/benchmarks/ -> 上两级 = agent/）
_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from modules.model_selection import (  # noqa: E402
    HierarchicalMethodSelector,
    FormulaRefiner,
)


@dataclass
class ProblemResult:
    problem_id: str
    title: str
    problem_type: str
    selected_top: List[str]
    suggested_model_ids: List[str]
    final_score: float
    self_review_pass: bool
    self_review_notes: List[str]
    expected_hit: int
    error: Optional[str] = None


@dataclass
class BenchmarkReport:
    name: str
    total: int
    passed: int
    results: List[ProblemResult] = field(default_factory=list)
    metadata: Dict = field(default_factory=dict)


# 自审查阈值（规则驱动，离线可复现）
_MIN_METHODS = 1
_MIN_FORMULA_SCORE = 6.0


def _load_problem(path: Path) -> Dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _self_review(problem: Dict, selection, refinement, suggested_ids: List[str]) -> (bool, List[str], int):
    """规则自审查：判定产物是否合格。返回 (pass, notes, expected_hit)。"""
    notes: List[str] = []
    ok = True

    # 1) 方法选择非空
    if len(selection.ranked_methods) < _MIN_METHODS:
        ok = False
        notes.append("方法选择为空，未检索到候选方法")
    else:
        notes.append(f"检索到 {len(selection.ranked_methods)} 个候选方法")

    # 2) 公式精炼产物非空且分数达标
    if not refinement.final_approach.strip():
        ok = False
        notes.append("公式精炼未产生最终建模思路")
    elif refinement.metadata.get("final_score", 0) < _MIN_FORMULA_SCORE:
        ok = False
        notes.append(f"公式精炼得分 {refinement.metadata.get('final_score')} 低于阈值 {_MIN_FORMULA_SCORE}")
    else:
        notes.append(f"公式精炼得分 {refinement.metadata.get('final_score')}（达标）")

    # 3) 与预期方法的交集（参考性，不致命）
    expected = set(problem.get("expected_methods", []))
    hit = len(expected & set(suggested_ids))
    if expected:
        notes.append(f"命中预期方法 {hit}/{len(expected)}")
    return ok, notes, hit


class BenchmarkHarness:
    """MM-Bench 式离线基准运行器。"""

    def __init__(self, problems_dir: Optional[str] = None,
                 top_k: int = 6, rounds: int = 2):
        self.problems_dir = Path(problems_dir or (Path(__file__).parent / "problems"))
        self.top_k = top_k
        self.rounds = rounds
        self.selector = HierarchicalMethodSelector()
        self.refiner = FormulaRefiner()

    def list_problems(self) -> List[Path]:
        return sorted(self.problems_dir.glob("*.json"))

    def run_problem(self, problem_path: Path) -> ProblemResult:
        try:
            problem = _load_problem(problem_path)
            pid = problem.get("id", problem_path.stem)
            title = problem.get("title", "")
            ptype = problem.get("type", "general")
            desc = problem.get("problem_requirement") or problem.get("background") or ""

            # 数据特征（从题型简单映射，供解法感知检索）
            features = {
                "evaluation": {"is_evaluation": True},
                "prediction": {"has_time_series": True},
                "optimization": {"is_optimization": True},
                "classification": {"has_labels": True},
            }.get(ptype, {})

            selection = self.selector.retrieve(
                problem_description=desc,
                data_features=features or None,
                top_k=self.top_k,
                problem_id=pid,
            )
            suggested_ids = self.selector.suggest_model_ids(selection)
            top = [r.method for r in selection.ranked_methods]

            refinement = self.refiner.refine(
                problem_description=desc,
                candidate_methods=top,
                data_description=problem.get("dataset_description"),
                rounds=self.rounds,
                problem_id=pid,
            )

            passed, notes, hit = _self_review(problem, selection, refinement, suggested_ids)
            return ProblemResult(
                problem_id=pid, title=title, problem_type=ptype,
                selected_top=top, suggested_model_ids=suggested_ids,
                final_score=refinement.metadata.get("final_score", 0.0),
                self_review_pass=passed, self_review_notes=notes,
                expected_hit=hit,
            )
        except Exception as e:
            return ProblemResult(
                problem_id=problem_path.stem, title=problem_path.stem,
                problem_type="error", selected_top=[], suggested_model_ids=[],
                final_score=0.0, self_review_pass=False,
                self_review_notes=[f"运行异常：{e}"], expected_hit=0,
                error=str(e),
            )

    def run_all(self, name: str = "mmbench_style_benchmark") -> BenchmarkReport:
        results: List[ProblemResult] = []
        for p in self.list_problems():
            results.append(self.run_problem(p))
        passed = sum(1 for r in results if r.self_review_pass)
        return BenchmarkReport(
            name=name, total=len(results), passed=passed, results=results,
            metadata={"top_k": self.top_k, "rounds": self.rounds},
        )

    def save(self, report: BenchmarkReport, output_path: str) -> None:
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(asdict(report), f, ensure_ascii=False, indent=2)


# ─────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────
def _main() -> int:
    harness = BenchmarkHarness()
    report = harness.run_all()
    out_dir = Path(__file__).resolve().parent.parent.parent / "results" / "benchmarks"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / "benchmark_report.json"
    harness.save(report, str(out_file))

    print(f"=== {report.name} ===")
    print(f"总计 {report.total} 题，自审查通过 {report.passed} 题\n")
    for r in report.results:
        flag = "PASS" if r.self_review_pass else "FAIL"
        print(f"[{flag}] {r.problem_id} ({r.problem_type}) {r.title}")
        for n in r.self_review_notes:
            print(f"      - {n}")
    print(f"\n报告已写入：{out_file}")
    return 0 if report.passed == report.total else 1


if __name__ == "__main__":
    raise SystemExit(_main())
