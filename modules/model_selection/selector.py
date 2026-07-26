# 模型选型模块 (Module 02)
# 功能：根据题目特征推荐适配的数学模型，列出候选模型的适用场景、优缺点对比，并给出选型建议
# 说明：从 v3.0 蓝本（02_model_selection/selector.py）忠实移植，去掉数字前缀 import，类与接口不变。
#       _load_model_catalog 已能处理 {"models": {...}} 结构（model_catalog.json 即此格式）。

import json
from pathlib import Path
from typing import Dict, List, Optional
from dataclasses import dataclass, asdict
from datetime import datetime


@dataclass
class ModelCandidate:
    """候选模型"""
    id: str
    name: str
    name_cn: str
    category: str
    description: str
    applicable_scenarios: List[str]
    pros: List[str]
    cons: List[str]
    complexity: str  # low, medium, high
    python_library: str
    suitability_score: float  # 0-100
    recommendation_reason: str


@dataclass
class ModelSelection:
    """模型选型结果"""
    selection_id: str
    problem_id: str
    problem_type: str
    selected_model: ModelCandidate
    candidate_models: List[ModelCandidate]
    comparison_matrix: Dict
    selection_rationale: str
    alternative_models: List[str]
    implementation_notes: str
    created_at: str
    metadata: Dict


class ModelSelector:
    """模型选型器"""

    def __init__(self, model_catalog_path: Optional[str] = None):
        """
        初始化模型选型器

        Args:
            model_catalog_path: 模型目录配置文件路径
        """
        self.model_catalog = self._load_model_catalog(model_catalog_path)

    def _load_model_catalog(self, catalog_path: Optional[str]) -> Dict:
        """加载模型目录"""
        default_catalog = {
            "optimization": {"models": [
                {"id": "linear_programming", "name": "线性规划", "name_cn": "线性规划",
                 "pros": ["求解速度快"], "cons": ["只能处理线性问题"], "complexity": "low",
                 "python_library": "scipy.optimize", "applicable_scenarios": ["资源分配"]}
            ]},
            "prediction": {"models": [
                {"id": "arima", "name": "ARIMA", "name_cn": "ARIMA模型",
                 "pros": ["理论成熟"], "cons": ["要求数据平稳"], "complexity": "medium",
                 "python_library": "statsmodels", "applicable_scenarios": ["时间序列"]}
            ]}
        }

        if catalog_path and Path(catalog_path).exists():
            with open(catalog_path, 'r', encoding='utf-8') as f:
                raw = json.load(f)
                # model_catalog.json的结构是 {"models": {"optimization": {"models": [...]}}}
                # 我们需要转换为 {"optimization": {"models": [...]}} 的格式
                if "models" in raw and isinstance(raw["models"], dict):
                    return raw["models"]
                return raw

        return default_catalog

    def select_model(self, problem_analysis: Dict) -> ModelSelection:
        """
        根据题目分析结果选择模型

        Args:
            problem_analysis: 题目分析结果（来自Module 01），需含
                problem_type / difficulty_level / problem_type_cn / problem_id，
                以及 metadata.variables_count、metadata.constraints_count。

        Returns:
            ModelSelection: 模型选型结果
        """
        problem_type = problem_analysis.get("problem_type", "comprehensive")
        variables_count = problem_analysis.get("metadata", {}).get("variables_count", 0)
        constraints_count = problem_analysis.get("metadata", {}).get("constraints_count", 0)
        difficulty = problem_analysis.get("difficulty_level", "medium")

        # 获取该类型下的所有候选模型
        candidates = self._get_candidates(problem_type, variables_count, constraints_count, difficulty)

        # 计算每个候选模型的适配分数
        for candidate in candidates:
            candidate.suitability_score = self._calculate_suitability(
                candidate, problem_analysis
            )

        # 按适配分数排序
        candidates.sort(key=lambda x: x.suitability_score, reverse=True)

        # 选择最优模型
        selected_model = candidates[0] if candidates else self._get_default_model()

        # 生成对比矩阵
        comparison_matrix = self._generate_comparison_matrix(candidates[:5])

        # 生成选型理由
        selection_rationale = self._generate_selection_rationale(selected_model, problem_analysis)

        # 构建选型结果
        selection = ModelSelection(
            selection_id=f"SEL-{datetime.now().strftime('%Y%m%d%H%M%S')}",
            problem_id=problem_analysis.get("problem_id", ""),
            problem_type=problem_type,
            selected_model=selected_model,
            candidate_models=candidates[:5],
            comparison_matrix=comparison_matrix,
            selection_rationale=selection_rationale,
            alternative_models=[c.name_cn for c in candidates[1:3]],
            implementation_notes=self._generate_implementation_notes(selected_model),
            created_at=datetime.now().isoformat(),
            metadata={
                "total_candidates": len(candidates),
                "top_score": selected_model.suitability_score,
                "problem_type": problem_type
            }
        )

        return selection

    def _get_candidates(self, problem_type: str, variables_count: int,
                       constraints_count: int, difficulty: str) -> List[ModelCandidate]:
        """获取候选模型列表"""
        candidates = []

        # 根据题目类型获取对应的模型
        type_models = self.model_catalog.get(problem_type, {}).get("models", [])

        for model_info in type_models:
            candidate = ModelCandidate(
                id=model_info.get("id", ""),
                name=model_info.get("name", ""),
                name_cn=model_info.get("name_cn", model_info.get("name", "")),
                category=problem_type,
                description=model_info.get("description", ""),
                applicable_scenarios=model_info.get("applicable_scenarios", []),
                pros=model_info.get("pros", []),
                cons=model_info.get("cons", []),
                complexity=model_info.get("complexity", "medium"),
                python_library=model_info.get("python_library", ""),
                suitability_score=0.0,
                recommendation_reason=""
            )
            candidates.append(candidate)

        # 如果没有找到对应类型的模型，返回默认模型
        if not candidates:
            candidates = [self._get_default_model()]

        return candidates

    def _calculate_suitability(self, candidate: ModelCandidate,
                              problem_analysis: Dict) -> float:
        """计算模型适配分数"""
        score = 50.0  # 基础分

        difficulty = problem_analysis.get("difficulty_level", "medium")
        variables_count = problem_analysis.get("metadata", {}).get("variables_count", 0)

        # 复杂度匹配
        complexity_map = {"easy": 1, "medium": 2, "high": 3}
        difficulty_score = complexity_map.get(difficulty, 2)
        candidate_complexity = complexity_map.get(candidate.complexity, 2)

        # 复杂度越接近，分数越高
        complexity_diff = abs(difficulty_score - candidate_complexity)
        score += (3 - complexity_diff) * 10

        # 变量数量影响
        if variables_count > 10 and candidate.complexity == "high":
            score += 10
        elif variables_count <= 5 and candidate.complexity == "low":
            score += 10

        # Python库支持
        if candidate.python_library:
            score += 5

        # 优缺点数量
        score += len(candidate.pros) * 2
        score -= len(candidate.cons) * 1

        return min(max(score, 0), 100)

    def _generate_comparison_matrix(self, candidates: List[ModelCandidate]) -> Dict:
        """生成对比矩阵"""
        matrix = {
            "headers": ["模型名称", "复杂度", "适配分数", "主要优点", "主要缺点"],
            "rows": []
        }

        for candidate in candidates:
            row = [
                candidate.name_cn,
                candidate.complexity,
                f"{candidate.suitability_score:.1f}",
                candidate.pros[0] if candidate.pros else "无",
                candidate.cons[0] if candidate.cons else "无"
            ]
            matrix["rows"].append(row)

        return matrix

    def _generate_selection_rationale(self, selected_model: ModelCandidate,
                                     problem_analysis: Dict) -> str:
        """生成选型理由"""
        problem_type = problem_analysis.get("problem_type_cn", "未知")
        difficulty = problem_analysis.get("difficulty_level", "medium")

        rationale = f"""
基于题目分析结果，本题属于{problem_type}问题，难度等级为{difficulty}。

选择{selected_model.name_cn}作为主要建模方法，理由如下：

1. **适用性匹配**：{selected_model.name_cn}适用于{', '.join(selected_model.applicable_scenarios[:2])}等场景，
   与本题特征高度匹配。

2. **复杂度适配**：该模型复杂度为{selected_model.complexity}，与题目难度{difficulty}相匹配，
   既能有效解决问题，又不会过度复杂。

3. **实现可行性**：可通过{selected_model.python_library}实现，
   具有成熟的库支持和丰富的文档资源。

4. **优势突出**：{selected_model.pros[0] if selected_model.pros else '具有良好的求解性能'}，
   能够有效解决本题的核心挑战。
"""
        return rationale.strip()

    def _generate_implementation_notes(self, model: ModelCandidate) -> str:
        """生成实现注意事项"""
        notes = f"""
## {model.name_cn} 实现注意事项

### 环境准备
```bash
pip install {model.python_library.split('.')[0] if '.' in model.python_library else model.python_library}
```

### 实现要点
1. 数据预处理：确保输入数据格式符合模型要求
2. 参数设置：根据题目特征合理设置模型参数
3. 结果验证：使用交叉验证或对比实验验证结果可靠性

### 注意事项
{chr(10).join(f'- {con}' for con in model.cons[:3]) if model.cons else '- 无特殊注意事项'}
"""
        return notes.strip()

    def _get_default_model(self) -> ModelCandidate:
        """获取默认模型"""
        return ModelCandidate(
            id="default",
            name="Default Model",
            name_cn="默认模型",
            category="comprehensive",
            description="通用建模方法",
            applicable_scenarios=["通用场景"],
            pros=["通用性强"],
            cons=["针对性不强"],
            complexity="medium",
            python_library="numpy/scipy",
            suitability_score=50.0,
            recommendation_reason="默认选择"
        )

    def save_selection(self, selection: ModelSelection, output_path: str):
        """保存选型结果"""
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(asdict(selection), f, ensure_ascii=False, indent=2)

        print(f"模型选型结果已保存到: {output_path}")

    def generate_comparison_md(self, selection: ModelSelection, output_path: str):
        """生成模型对比报告Markdown"""
        md_content = f"""# 模型选型报告

## 基本信息

- **选型ID**: {selection.selection_id}
- **题目ID**: {selection.problem_id}
- **题目类型**: {selection.problem_type}
- **生成时间**: {selection.created_at}

## 推荐模型

### {selection.selected_model.name_cn}

| 属性 | 值 |
|------|-----|
| **模型ID** | {selection.selected_model.id} |
| **复杂度** | {selection.selected_model.complexity} |
| **适配分数** | {selection.selected_model.suitability_score:.1f}/100 |
| **Python库** | {selection.selected_model.python_library} |

**适用场景**: {', '.join(selection.selected_model.applicable_scenarios)}

**优点**:
{chr(10).join(f'- {p}' for p in selection.selected_model.pros)}

**缺点**:
{chr(10).join(f'- {c}' for c in selection.selected_model.cons)}

## 选型理由

{selection.selection_rationale}

## 候选模型对比

| 模型名称 | 复杂度 | 适配分数 | 主要优点 | 主要缺点 |
|----------|--------|----------|----------|----------|
"""
        for candidate in selection.candidate_models:
            md_content += f"| {candidate.name_cn} | {candidate.complexity} | {candidate.suitability_score:.1f} | {candidate.pros[0] if candidate.pros else '-'} | {candidate.cons[0] if candidate.cons else '-'} |\n"

        md_content += f"""
## 替代模型

如果主选模型不适合，可以考虑以下替代方案：

{chr(10).join(f'{i+1}. {name}' for i, name in enumerate(selection.alternative_models))}

## 实现注意事项

{selection.implementation_notes}

---

*生成时间: {selection.created_at}*
"""

        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(md_content)

        print(f"模型对比报告已保存到: {output_path}")
