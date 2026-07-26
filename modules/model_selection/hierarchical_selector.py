# 层次化方法库检索选择器（HMML 移植，离线优先）
#
# 设计参考 MM-Agent 的 HMML + MethodRetriever/MethodScorer：
#   - HMML 为 领域(domain) → 子领域(subdomain) → 方法(method) 三层树；
#   - MethodScorer 用 parent_weight/child_weight 综合父子节点得分。
# 本实现：
#   - 以确定性规则（关键词重叠 + 数据特征匹配）复刻双路检索（问题感知 + 解法感知），离线可跑；
#   - 可选 llm_critic 回调（hybrid 模式）做 LLM 打分精炼，未提供时优雅降级为规则打分；
#   - 不复制 MM-Agent 任何 CC BY-NC 提示词/代码，纯自研、MIT。
#
# 依赖：仅标准库（json/re/dataclasses），保证可被 import。

import json
import re
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Callable, Dict, List, Optional

_PARENT_WEIGHT = 0.5
_CHILD_WEIGHT = 0.5


@dataclass
class RankedMethod:
    method: str
    method_class: str
    model_id: Optional[str]
    category: str
    domain: str
    subdomain: str
    description: str
    score: float
    reason: str


@dataclass
class HierarchicalSelection:
    selection_id: str
    problem_id: str
    ranked_methods: List[RankedMethod]
    top_k: int
    rationale: str
    metadata: Dict = field(default_factory=dict)


def _tokenize(text: str) -> set:
    """粗分词：保留中文二元 + 英文单词，用于关键词重叠计算。"""
    if not text:
        return set()
    text = text.lower()
    en = set(re.findall(r"[a-z0-9_]+", text))
    # 中文按字符 + 2-gram
    zh = re.findall(r"[\u4e00-\u9fff]", text)
    grams = set(zh)
    for i in range(len(zh) - 1):
        grams.add(zh[i] + zh[i + 1])
    return en | grams


def _overlap(query_tokens: set, keywords: List[str]) -> float:
    """返回 0-1 的关键词重叠度（关键词命中率）。"""
    if not keywords:
        return 0.0
    kw_tokens = _tokenize(" ".join(keywords))
    if not kw_tokens:
        return 0.0
    hit = query_tokens & kw_tokens
    return len(hit) / len(kw_tokens)


class HierarchicalMethodSelector:
    """层次化方法检索选择器。"""

    def __init__(self, hmml_path: Optional[str] = None):
        if hmml_path is None:
            hmml_path = Path(__file__).resolve().parent.parent.parent / "config" / "hmml_method_library.json"
        self.hmml_path = Path(hmml_path)
        self.hmml = self._load()
        self.domains = self.hmml.get("domains", [])

    def _load(self) -> Dict:
        with open(self.hmml_path, "r", encoding="utf-8") as f:
            return json.load(f)

    # ── 树结构访问（兼容可选 LLM critic 的"方法树"输入） ──
    def get_method_tree(self) -> List[Dict]:
        """返回扁平化的方法树（领域→子领域→方法），便于接入 LLM critic。"""
        tree = []
        for d in self.domains:
            domain_node = {
                "method": d.get("domain", ""),
                "description": d.get("description", ""),
                "keywords": d.get("keywords", []),
                "children": [],
            }
            for sd in d.get("subdomains", []):
                sub_node = {
                    "method": sd.get("subdomain", ""),
                    "description": "",
                    "keywords": [],
                    "children": [],
                }
                for m in sd.get("methods", []):
                    sub_node["children"].append({
                        "method": m.get("method", ""),
                        "description": m.get("description", ""),
                        "method_class": m.get("method_class", ""),
                        "model_id": m.get("model_id"),
                        "keywords": m.get("keywords", []),
                    })
                domain_node["children"].append(sub_node)
            tree.append(domain_node)
        return tree

    def _flatten_leaves(self) -> List[Dict]:
        leaves = []
        for d in self.domains:
            d_kw = d.get("keywords", [])
            for sd in d.get("subdomains", []):
                for m in sd.get("methods", []):
                    leaves.append({
                        "method": m.get("method", ""),
                        "method_class": m.get("method_class", ""),
                        "model_id": m.get("model_id"),
                        "description": m.get("description", ""),
                        "keywords": m.get("keywords", []),
                        "domain": d.get("domain", ""),
                        "domain_keywords": d_kw,
                        "subdomain": sd.get("subdomain", ""),
                        "subdomain_keywords": sd.get("keywords", []),
                    })
        return leaves

    @staticmethod
    def _feature_score(method: Dict, features: Optional[Dict]) -> float:
        """解法感知：数据特征与模型类别的匹配度（0-1）。"""
        if not features:
            return 0.0
        cls = method.get("method_class", "")
        score = 0.0
        if features.get("has_time_series") and cls in ("prediction", "neural_networks"):
            score += 0.5
        if features.get("has_labels") and cls in ("classification", "clustering"):
            score += 0.5
        if features.get("is_optimization") and cls in ("optimization", "optimization_meta"):
            score += 0.6
        if features.get("is_evaluation") and cls == "evaluation":
            score += 0.6
        if features.get("small_sample") and cls in ("evaluation", "prediction"):
            score += 0.2
        if features.get("needs_interpretability") and cls in ("regression", "classification", "evaluation"):
            score += 0.2
        return min(score, 1.0)

    def retrieve(self, problem_description: str, data_features: Optional[Dict] = None,
                 top_k: int = 6, llm_critic: Optional[Callable[[str, List[Dict]], List[float]]] = None,
                 problem_id: str = "") -> HierarchicalSelection:
        """
        检索候选建模方法（双路：问题感知 + 解法感知）。

        Args:
            problem_description: 题目/任务描述文本（问题感知）。
            data_features: 数据特征 dict（解法感知），如
                {"has_time_series": bool, "has_labels": bool, "is_optimization": bool,
                 "is_evaluation": bool, "small_sample": bool, "needs_interpretability": bool}。
            top_k: 返回前 k 个方法。
            llm_critic: 可选回调 (problem_description, methods) -> List[float]，hybrid 模式用 LLM 打分。
            problem_id: 题目标识（用于结果 id）。
        Returns:
            HierarchicalSelection
        """
        query = _tokenize(problem_description)
        leaves = self._flatten_leaves()

        # 1) 子节点（方法）原始分：关键词重叠 + 特征匹配
        for m in leaves:
            kw_score = _overlap(query, m["keywords"] + m["domain_keywords"] + m["subdomain_keywords"])
            feat_score = self._feature_score(m, data_features)
            m["child_raw"] = 0.6 * kw_score + 0.4 * feat_score

        # 2) 父节点（领域/子领域）相关性：关键词重叠
        for m in leaves:
            parent_rel = max(
                _overlap(query, m["domain_keywords"]),
                _overlap(query, m["subdomain_keywords"]),
            )
            m["parent_rel"] = parent_rel
            m["score"] = _PARENT_WEIGHT * parent_rel + _CHILD_WEIGHT * m["child_raw"]

        # 3) 可选 LLM critic 精炼（hybrid）
        if llm_critic is not None:
            critic_scores = llm_critic(problem_description, [
                {"method": m["method"], "description": m["description"]} for m in leaves
            ])
            for m, cs in zip(leaves, critic_scores):
                # critic 分与规则分取均值，避免完全被 LLM 主导
                m["score"] = 0.5 * m["score"] + 0.5 * max(0.0, min(1.0, cs))

        leaves.sort(key=lambda x: x["score"], reverse=True)
        top = leaves[:top_k]

        ranked = []
        for i, m in enumerate(top):
            reason = self._make_reason(m, problem_description, data_features)
            ranked.append(RankedMethod(
                method=m["method"], method_class=m["method_class"], model_id=m["model_id"],
                category=m["method_class"], domain=m["domain"], subdomain=m["subdomain"],
                description=m["description"], score=round(m["score"], 3), reason=reason,
            ))

        rationale = self._make_rationale(ranked, problem_description)
        return HierarchicalSelection(
            selection_id=f"HMML-{abs(hash(problem_description)) % 10**8:08d}",
            problem_id=problem_id,
            ranked_methods=ranked,
            top_k=top_k,
            rationale=rationale,
            metadata={
                "total_methods": len(leaves),
                "used_llm_critic": llm_critic is not None,
                "data_features": data_features or {},
            },
        )

    @staticmethod
    def _make_reason(m: Dict, problem: str, features: Optional[Dict]) -> str:
        parts = []
        if m["parent_rel"] > 0.1:
            parts.append(f"属于「{m['domain']}/{m['subdomain']}」领域，与题目主题相关")
        if m["child_raw"] > 0.3:
            parts.append("方法关键词与题目描述高度匹配")
        if features:
            if features.get("has_time_series") and m["method_class"] == "prediction":
                parts.append("题目含时间序列数据，适合预测类方法")
            if features.get("is_optimization") and m["method_class"] in ("optimization", "optimization_meta"):
                parts.append("题目含资源/约束优化目标")
            if features.get("is_evaluation") and m["method_class"] == "evaluation":
                parts.append("题目为方案评价/排序")
        if not parts:
            parts.append("作为候选方法纳入，建议结合领域知识进一步筛选")
        return "；".join(parts) + f"。（{m['description']}）"

    @staticmethod
    def _make_rationale(ranked: List[RankedMethod], problem: str) -> str:
        if not ranked:
            return "未检索到匹配方法，建议人工补充领域知识或扩大方法库。"
        lines = [f"基于题目特征，推荐优先考察以下 {len(ranked)} 个建模方法："]
        for i, r in enumerate(ranked, 1):
            lines.append(f"{i}. 【{r.method}】（{r.domain}/{r.subdomain}，得分 {r.score}）{r.reason}")
        return "\n".join(lines)

    def suggest_model_ids(self, selection: HierarchicalSelection) -> List[str]:
        """把排名方法映射回 model_catalog 的模型 id（无效 id 自动跳过）。"""
        return [r.model_id for r in selection.ranked_methods if r.model_id]

    def save(self, selection: HierarchicalSelection, output_path: str):
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(asdict(selection), f, ensure_ascii=False, indent=2)
