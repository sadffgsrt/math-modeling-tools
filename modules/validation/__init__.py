"""验证模块包（从 v3.0 06 移植）。导出核心验证器。"""
from .validator import (
    DataValidator, ModelValidator, ComprehensiveValidator, PaperQualityValidator,
    ValidationCheck, ValidationReport, save_validation_report, generate_validation_md,
    ReviewGateError, gate_review,
)

__all__ = [
    "DataValidator", "ModelValidator", "ComprehensiveValidator", "PaperQualityValidator",
    "ValidationCheck", "ValidationReport", "save_validation_report", "generate_validation_md",
    "ReviewGateError", "gate_review",
]
