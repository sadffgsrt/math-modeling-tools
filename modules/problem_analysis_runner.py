# 题目解析阶段薄包装 runner（main.py 通过 modules.problem_analysis_runner 调用）
# 职责：定位题目文件 → ProblemAnalyzer 分析 → 转换为扁平 dict 供 main.py 与各下游阶段消费

from pathlib import Path
from typing import Dict, List, Optional

from modules.problem_analysis.analyzer import ProblemAnalyzer

# 支持的题目文件扩展名
_PROBLEM_EXTS = [".txt", ".pdf", ".docx", ".doc"]


def _find_problem_file(project_dir: Path) -> Optional[Path]:
    """在项目目录的 problem_files 下查找题目文件；找不到则回退到 projects/.template 模板。"""
    # 优先：当前项目的 problem_files
    problem_dir = project_dir / "problem_files"
    if problem_dir.exists():
        for ext in _PROBLEM_EXTS:
            candidates = sorted(problem_dir.glob(f"*{ext}"))
            if candidates:
                return candidates[0]
    # 回退：全局模板目录（projects/.template/problem_files）
    template_dir = Path(__file__).resolve().parent.parent / "projects" / ".template" / "problem_files"
    if template_dir.exists():
        for ext in _PROBLEM_EXTS:
            candidates = sorted(template_dir.glob(f"*{ext}"))
            if candidates:
                return candidates[0]
    return None


def run_problem_analysis(workflow, **kwargs) -> Dict:
    """
    题目解析阶段入口。

    Args:
        workflow: MathModelingWorkflow 实例，至少提供 project_dir 属性。
        **kwargs: 可传入 problem_id 等。

    Returns:
        dict，必含键：problem_id, title, problem_type, problem_type_cn, description,
        difficulty(对应 difficulty_level), variables_count, constraints_count,
        variables, constraints, objectives, sub_problems, keywords。
    """
    project_dir = Path(getattr(workflow, "project_dir", "projects/.template"))

    problem_file = _find_problem_file(project_dir)
    if problem_file is None:
        raise FileNotFoundError(
            f"未找到题目文件（支持 {_PROBLEM_EXTS}），请将其放入: {project_dir / 'problem_files'}"
        )

    analyzer = ProblemAnalyzer(kwargs.get("config_path"))
    text = analyzer.read_problem_file(problem_file)
    if not text or not text.strip():
        raise ValueError(f"题目文件内容为空: {problem_file}")

    analysis = analyzer.analyze_problem(text, problem_id=kwargs.get("problem_id", ""))

    # 由 dataclass 转换为扁平字典，便于 JSON 序列化与下游消费
    return {
        "problem_id": analysis.problem_id,
        "title": analysis.title,
        "problem_type": analysis.problem_type,
        "problem_type_cn": analysis.problem_type_cn,
        "description": analysis.description,
        "difficulty": analysis.difficulty_level,
        "variables_count": len(analysis.variables),
        "constraints_count": len(analysis.constraints),
        "variables": [vars(v) for v in analysis.variables],
        "constraints": [vars(c) for c in analysis.constraints],
        "objectives": [vars(o) for o in analysis.objectives],
        "sub_problems": [vars(s) for s in analysis.sub_problems],
        "keywords": analysis.keywords,
        # 保留原始分析对象的来源路径，便于调试
        "source_file": str(problem_file),
    }
