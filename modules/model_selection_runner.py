# 模型选型阶段薄包装 runner（main.py 通过 modules.model_selection_runner 调用）
# 职责：获取题目分析上下文（复用 problem_analysis 结果或重新分析）→ ModelSelector 选型 → 扁平 dict

from pathlib import Path
from typing import Dict, Optional

from modules.problem_analysis.analyzer import ProblemAnalyzer
from modules.model_selection.selector import ModelSelector, ModelSelection

# 模型目录路径（相对于 agent/config）
_CATALOG_PATH = Path(__file__).resolve().parent.parent / "config" / "model_catalog.json"

# 支持的题目文件扩展名
_PROBLEM_EXTS = [".txt", ".pdf", ".docx", ".doc"]


def _find_problem_file(project_dir: Path) -> Optional[Path]:
    """定位题目文件：优先当前项目 problem_files，回退模板目录。"""
    problem_dir = project_dir / "problem_files"
    if problem_dir.exists():
        for ext in _PROBLEM_EXTS:
            candidates = sorted(problem_dir.glob(f"*{ext}"))
            if candidates:
                return candidates[0]
    template_dir = Path(__file__).resolve().parent.parent / "projects" / ".template" / "problem_files"
    if template_dir.exists():
        for ext in _PROBLEM_EXTS:
            candidates = sorted(template_dir.glob(f"*{ext}"))
            if candidates:
                return candidates[0]
    return None


def _normalize_analysis(problem_analysis: Dict) -> Dict:
    """
    将 problem_analysis 扁平 dict 适配为 ModelSelector.select_model 期望的结构：
    - 顶层 problem_type / problem_type_cn / problem_id
    - difficulty_level（兼容扁平的 difficulty）
    - metadata.variables_count / metadata.constraints_count
    """
    return {
        "problem_id": problem_analysis.get("problem_id", ""),
        "problem_type": problem_analysis.get("problem_type", "comprehensive"),
        "problem_type_cn": problem_analysis.get("problem_type_cn", ""),
        "difficulty_level": problem_analysis.get("difficulty_level")
        or problem_analysis.get("difficulty", "medium"),
        "metadata": {
            "variables_count": problem_analysis.get("variables_count", 0),
            "constraints_count": problem_analysis.get("constraints_count", 0),
        },
    }


def _get_problem_analysis(workflow, **kwargs) -> Optional[Dict]:
    """
    获取题目分析上下文，按优先级：
    1. 显式传入的 problem_analysis
    2. workflow.problem_analysis_result 属性
    3. workflow.state["problem_analysis"]
    4. 回退：用 ProblemAnalyzer 重新分析题目文件
    """
    if kwargs.get("problem_analysis"):
        return kwargs["problem_analysis"]

    ctx = getattr(workflow, "problem_analysis_result", None)
    if ctx:
        return ctx

    state = getattr(workflow, "state", None) or {}
    ctx = state.get("problem_analysis")
    if ctx:
        return ctx

    # 回退：重新分析题目文件
    project_dir = Path(getattr(workflow, "project_dir", "projects/.template"))
    problem_file = _find_problem_file(project_dir)
    if problem_file is None:
        return None
    analyzer = ProblemAnalyzer(kwargs.get("config_path"))
    text = analyzer.read_problem_file(problem_file)
    if not text or not text.strip():
        return None
    analysis = analyzer.analyze_problem(text, problem_id=kwargs.get("problem_id", ""))
    return {
        "problem_id": analysis.problem_id,
        "problem_type": analysis.problem_type,
        "problem_type_cn": analysis.problem_type_cn,
        "difficulty": analysis.difficulty_level,
        "variables_count": len(analysis.variables),
        "constraints_count": len(analysis.constraints),
    }


def run_model_selection(workflow, **kwargs) -> Dict:
    """
    模型选型阶段入口。

    Returns:
        dict，必含键：selected_model(字符串模型中文名), suitability_score(float)，
        以及 candidate_models, comparison_matrix, selection_rationale, alternative_models 等。
    """
    catalog_path = kwargs.get("model_catalog_path") or (
        str(_CATALOG_PATH) if _CATALOG_PATH.exists() else None
    )
    selector = ModelSelector(catalog_path)

    problem_analysis = _get_problem_analysis(workflow, **kwargs)
    if problem_analysis is None:
        raise FileNotFoundError(
            "未找到题目分析上下文，且无法定位题目文件进行重新分析；"
            "请先运行题目解析阶段或提供 problem_files 下的题目文件。"
        )

    normalized = _normalize_analysis(problem_analysis)
    selection: ModelSelection = selector.select_model(normalized)

    return {
        "selected_model": selection.selected_model.name_cn,
        "selected_model_id": selection.selected_model.id,
        "suitability_score": float(selection.selected_model.suitability_score),
        "problem_type": selection.problem_type,
        "candidate_models": [
            {
                "id": c.id,
                "name": c.name,
                "name_cn": c.name_cn,
                "category": c.category,
                "suitability_score": float(c.suitability_score),
                "complexity": c.complexity,
                "python_library": c.python_library,
            }
            for c in selection.candidate_models
        ],
        "comparison_matrix": selection.comparison_matrix,
        "selection_rationale": selection.selection_rationale,
        "alternative_models": selection.alternative_models,
        "implementation_notes": selection.implementation_notes,
        "selection_id": selection.selection_id,
    }
