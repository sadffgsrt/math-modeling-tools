# -*- coding: utf-8 -*-
# 论文撰写阶段薄包装 runner（main.py 通过 modules.paper_writing_runner 调用）
# 职责：聚合上游各阶段真实结果 → PaperWriter 生成论文 → 优先写 .docx 到
#       workflow.project_dir/"paper"；若 python-docx 缺失则降级为 markdown 并清晰说明。
#
# 诚实性约束：论文内容完全由上游真实数据拼装，不伪造任何数字/结论；仅当 python-docx
# 不可用才降级 markdown（并在返回 dict 中标注 degraded=True）。

from pathlib import Path
from typing import Dict, Any, Optional


def _load_json(workflow, name: str) -> Optional[Dict]:
    loader = getattr(workflow, "_load_result", None)
    if callable(loader):
        try:
            val = loader(name)
            if val is not None:
                return val
        except Exception:
            pass
    results_dir = getattr(workflow, "results_dir", None)
    if results_dir is not None:
        p = Path(results_dir) / name
        if p.exists():
            import json
            with open(p, "r", encoding="utf-8") as f:
                return json.load(f)
    return None


def _load_stage(workflow, stage: str) -> Dict:
    fname = f"{stage}.json"
    data = _load_json(workflow, fname)
    if data is not None:
        return data
    attr = getattr(workflow, f"{stage}_result", None)
    if isinstance(attr, dict):
        return attr
    cache = getattr(workflow, "cache", None)
    if cache is not None and hasattr(cache, "get"):
        try:
            cached = cache.get(f"stage_{stage}")
            if isinstance(cached, dict):
                return cached
        except Exception:
            pass
    return {}


def run_paper_writing(workflow, **kwargs) -> Dict[str, Any]:
    """
    论文撰写阶段入口。

    Args:
        workflow: MathModelingWorkflow 实例。
        **kwargs: 允许覆盖某一阶段的输入数据。

    Returns:
        dict: 必含 output_path、status、format、degraded；另含 title、total_word_count、
        chapters_count 等。
    """
    from modules.paper_writing.writer import PaperWriter
    from modules.validation.validator import PaperQualityValidator

    # 聚合上游真实结果（缺失则使用空 dict，由 PaperWriter 按模板生成，不伪造数据）
    problem_analysis = kwargs.get("problem_analysis") or _load_stage(workflow, "problem_analysis")
    model_selection = kwargs.get("model_selection") or _load_stage(workflow, "model_selection")
    data_info = kwargs.get("data_info") or _load_stage(workflow, "data_processing")
    solving_results = kwargs.get("solving_results") or _load_stage(workflow, "model_solving")
    validation_results = kwargs.get("validation_results") or _load_stage(workflow, "validation")
    visualization_results = kwargs.get("visualization_results") or _load_stage(workflow, "visualization")

    paper_dir = Path(workflow.project_dir) / "paper"
    paper_dir.mkdir(parents=True, exist_ok=True)

    writer = PaperWriter()
    result = writer.generate_paper(
        problem_analysis, model_selection, data_info,
        solving_results, validation_results, visualization_results,
        output_dir=str(paper_dir),
    )

    # 优先生成 docx；python-docx 缺失则降级 markdown 并清晰说明
    md_path = Path(result.output_path)            # markdown 草稿始终存在，用于审查与标注
    output_path = md_path
    format_type = "md"
    degraded = False
    degrade_reason = ""

    try:
        import docx  # noqa
        docx_path = paper_dir / "paper.docx"
        writer.save_docx(result.paper_structure, str(docx_path))
        output_path = docx_path
        format_type = "docx"
    except ImportError as e:
        degraded = True
        degrade_reason = str(e)

    # —— 论文质量自审查（真实数值一致性 + 图表文件真实性）——
    figures_dir = getattr(workflow, "figures_dir", None) or str(paper_dir.parent / "figures")
    paper_md = md_path.read_text(encoding="utf-8") if md_path.exists() else ""
    pq = PaperQualityValidator()
    pq_report = pq.validate_paper(
        paper_content=paper_md,
        problem_analysis=problem_analysis,
        model_selection=model_selection,
        solving_results=solving_results,
        validation_results=validation_results,
        visualization_results=visualization_results,
        figures_dir=figures_dir,
    )

    # —— 审查结果门禁：上游模型验证未通过时，在论文草稿显著标注结论存疑 ——
    v_status = (validation_results or {}).get("overall_status")
    v_failed = (validation_results or {}).get("status") == "failed"
    if not validation_results:
        gate, note = "none", ""
    elif v_status in ("critical", "poor") or v_failed:
        gate = "failed"
        note = ("\n\n---\n\n## 模型验证状态提示\n\n"
                f"**注意：模型验证未通过（状态：{v_status or 'failed'}）。**\n"
                "本章结论存疑，提交前请复核模型与数据。\n")
    elif v_status == "acceptable":
        gate = "caution"
        note = ("\n\n---\n\n## 模型验证状态提示\n\n"
                "模型验证结果为 acceptable（可接受但非优良），结论可靠性一般，建议补充验证。\n")
    else:
        gate, note = "passed", ""
    if note and md_path.exists():
        with md_path.open("a", encoding="utf-8") as f:
            f.write(note)

    return {
        "status": "completed",
        "output_path": str(output_path),
        "format": format_type,
        "degraded": degraded,                 # True 表示因缺 python-docx 而降级为 markdown
        "degrade_reason": degrade_reason,
        "title": result.paper_structure.title,
        "total_word_count": result.metadata.get("total_word_count", 0),
        "chapters_count": len(result.paper_structure.chapters),
        "result_id": result.result_id,
        "validation_gate": gate,             # failed / caution / passed / none
        "paper_quality": {
            "score": pq_report.overall_score,
            "status": pq_report.overall_status,
            "passed": pq_report.passed_checks,
            "warning": pq_report.warning_checks,
            "failed": pq_report.failed_checks,
        },
    }
