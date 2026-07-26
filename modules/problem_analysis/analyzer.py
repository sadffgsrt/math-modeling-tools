# -*- coding: utf-8 -*-
# 题目解析模块 (Module 01)
# 功能：解析竞赛题目，提取题目类型、变量、约束、目标与子问题等结构化信息
# 说明：本文件从 v3.0 蓝本（01_problem_analysis/analyzer.py）忠实移植，去掉数字前缀 import，
#       类与接口保持不变。

import re
import json
from pathlib import Path
from typing import List, Dict, Optional, Union
from dataclasses import dataclass, field
from datetime import datetime

@dataclass
class Variable:
    name: str
    symbol: str
    description: str = ""
    unit: str = ""
    type: str = "continuous"

@dataclass
class Constraint:
    name: str
    expression: str
    description: str = ""
    type: str = "inequality"

@dataclass
class Objective:
    name: str
    expression: str
    description: str = ""
    direction: str = "minimize"

@dataclass
class SubProblem:
    id: str
    title: str
    description: str
    difficulty: str = "medium"

@dataclass
class ProblemAnalysis:
    problem_id: str
    title: str
    problem_type: str
    problem_type_cn: str
    description: str
    difficulty_level: str
    variables: List[Variable] = field(default_factory=list)
    constraints: List[Constraint] = field(default_factory=list)
    objectives: List[Objective] = field(default_factory=list)
    sub_problems: List[SubProblem] = field(default_factory=list)
    keywords: List[str] = field(default_factory=list)

class ProblemAnalyzer:
    PROBLEM_TYPES = {
        "optimization": {"keywords": ["优化", "最大", "最小", "最优", "调度", "分配"], "cn_name": "优化类"},
        "prediction": {"keywords": ["预测", "估计", "推断", "回归"], "cn_name": "预测类"},
        "classification": {"keywords": ["分类", "识别", "判断", "诊断"], "cn_name": "分类类"},
        "simulation": {"keywords": ["模拟", "仿真", "动态"], "cn_name": "仿真类"},
        "comprehensive": {"keywords": ["综合", "全面", "系统", "整体"], "cn_name": "综合类"}
    }
    # 支持物理公式风格的变量提取模式
    VARIABLE_PATTERNS = [
        r"设.*?为\s*([a-zA-Z])",
        r"其中\s*([a-zA-Z])\s*(?:表示|是|为)\s*(.+?)(?:[，。,\n]|$)",
        r"令\s*([a-zA-Z])\s*表示\s*(.+?)(?:[，。,\n]|$)",
        r"([a-zA-Z])\s*(?:为|是|表示)\s*(.+?)(?:的)(.+?)(?:[，。,\n]|$)",
        r"([a-zA-Z])\s*[=:]\s*(.+?)(?:[，。,\n]|$)",
        r"(?:变量|参数|常量)\s*([a-zA-Z])\s*(.+?)(?:[，。,\n]|$)",
        r"(?:其中|式中)\s*([a-zA-Z])\s*(?:为|表示|代表)\s*(.+?)(?:[，。,\n]|$)",
        r"(?:物理量|参数|变量)\s*([a-zA-Z])\s*(?:表示|代表|对应)\s*(.+?)(?:[，。,\n]|$)",
        r"([a-zA-Z])\s*(?:的|为)\s*(?:单位|量纲)\s*(?:是|为|表示)\s*(.+?)(?:[，。,\n]|$)",
    ]
    CONSTRAINT_PATTERNS = [
        r"(?:约束|限制|条件|要求)[：:]\s*(.+?)(?:[。\n]|$)",
        r"(?:满足|符合)\s*(.+?)(?:[。\n]|$)",
        r"(\w+)\s*[<>≤≥]\s*(\d+)",
        r"(?:不能|不得|必须|需要)\s*(.+?)(?:[。\n]|$)",
        r"(?:最大|最小|最多|最少|上限|下限)\s*(.+?)(?:[。\n]|$)",
    ]

    def __init__(self, config_path=None):
        self.config = self._load_config(config_path)

    def _load_config(self, config_path):
        if config_path and Path(config_path).exists():
            with open(config_path, "r", encoding="utf-8") as f:
                return json.load(f)
        return {}

    def read_problem_file(self, file_path):
        file_path = Path(file_path)
        suffix = file_path.suffix.lower()
        if not file_path.exists():
            raise FileNotFoundError(f"文件不存在: {file_path}")
        if suffix == ".pdf":
            return self._read_pdf(file_path)
        elif suffix in [".docx", ".doc"]:
            return self._read_docx(file_path)
        else:
            return file_path.read_text(encoding="utf-8")

    def _read_pdf(self, file_path):
        from PyPDF2 import PdfReader
        reader = PdfReader(str(file_path))
        return "\n".join([p.extract_text() or "" for p in reader.pages])

    def _read_docx(self, file_path):
        from docx import Document
        doc = Document(str(file_path))
        return "\n".join([p.text for p in doc.paragraphs if p.text.strip()])

    def analyze_problem(self, problem_text, problem_id=""):
        problem_type = self._detect_problem_type(problem_text)
        title = self._extract_title(problem_text)
        return ProblemAnalysis(
            problem_id=problem_id or f"PROB-{datetime.now().strftime('%Y%m%d%H%M%S')}",
            title=title, problem_type=problem_type,
            problem_type_cn=self.PROBLEM_TYPES[problem_type]["cn_name"],
            description=problem_text[:500], difficulty_level="medium",
            variables=self._extract_variables(problem_text),
            constraints=self._extract_constraints(problem_text),
            objectives=[Objective(name="目标函数", expression="f(x)", direction="minimize")],
            sub_problems=self._extract_sub_problems(problem_text),
            keywords=self._extract_keywords(problem_text)
        )

    def _detect_problem_type(self, text):
        scores = {pt: sum(1 for kw in info["keywords"] if kw in text) for pt, info in self.PROBLEM_TYPES.items()}
        return max(scores, key=scores.get) if max(scores.values()) > 0 else "comprehensive"

    def _extract_title(self, text):
        for line in text.strip().split("\n")[:5]:
            if line.strip() and len(line.strip()) > 5:
                return line.strip()[:100]
        return "数学建模问题"

    def _extract_variables(self, text):
        variables, seen = [], set()
        for pattern in self.VARIABLE_PATTERNS:
            for match in re.finditer(pattern, text):
                symbol = match.group(1)
                if symbol not in seen:
                    seen.add(symbol)
                    desc = match.group(2) if len(match.groups()) > 1 else ""
                    variables.append(Variable(name=f"变量{symbol}", symbol=symbol, description=desc.strip()))
        return variables[:20]

    def _extract_constraints(self, text):
        constraints = []
        for pattern in self.CONSTRAINT_PATTERNS:
            for i, match in enumerate(re.finditer(pattern, text)):
                expr = match.group(1) if match.groups() else match.group(0)
                constraints.append(Constraint(name=f"约束{i+1}", expression=expr.strip()))
        return constraints[:15]

    def _extract_sub_problems(self, text):
        sub_problems = []
        patterns = [
            r"(?:问题|子问题)\s*[一二三四五六七八九十\d]+[:：]\s*(.+?)(?:\n|$)",
            r"(?:问题|子问题)\s*(\d+)[:：]\s*(.+?)(?:\n|$)",
            r"\d+\.\s*(.+?)(?:\n|$)"
        ]
        for pattern in patterns:
            for match in re.finditer(pattern, text):
                if len(match.groups()) >= 1:
                    title = match.group(1).strip() if len(match.groups()) == 1 else match.group(2).strip()
                    sub = SubProblem(
                        id=f"SP-{len(sub_problems)+1}",
                        title=title[:50],
                        description=title,
                        difficulty="medium"
                    )
                    sub_problems.append(sub)
        return sub_problems[:5]

    def _extract_keywords(self, text):
        keywords = []
        common_keywords = ["优化", "模型", "求解", "分析", "预测", "分类"]
        for kw in common_keywords:
            if kw in text:
                keywords.append(kw)
        return keywords[:5]
