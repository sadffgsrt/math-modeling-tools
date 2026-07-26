# -*- coding: utf-8 -*-
"""
模型工厂（ModelFactory）
职责：
  - 从 config/model_catalog.json 加载全部模型（恰好 53 个）；
  - list_models() 返回 53 个模型 id；
  - build_model(model_id) 按分类构造对应求解器实例；
  - solve(model_id, **params) 调用求解器并返回含 model_category 的结果字典；
  - get_tool_schemas() 为每个模型生成 function schema（name=solve_<model_id>），
    共 53 条（dict 形式）。
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

from .factories import MODEL_CATEGORY_MAP, CATALOG_ALIASES


class ModelFactory:
    """模型工厂：加载目录、登记 53 个模型、构建求解器、调度求解。"""

    def __init__(self, catalog_path: str = None):
        # 默认目录：agent/config/model_catalog.json
        if catalog_path is None:
            default = Path(__file__).resolve().parent.parent.parent / "config" / "model_catalog.json"
            catalog_path = str(default)
        self.catalog_path = Path(catalog_path)
        self._catalog: Dict[str, Any] = {}
        self._models: Dict[str, Dict[str, Any]] = {}
        self.load_catalog()

    # ── 目录加载 ──
    def load_catalog(self) -> "ModelFactory":
        if not self.catalog_path.exists():
            raise FileNotFoundError(f"模型目录不存在：{self.catalog_path}")
        with open(self.catalog_path, "r", encoding="utf-8") as f:
            self._catalog = json.load(f)
        self._models = {}
        for cat_key, cat_val in self._catalog.get("models", {}).items():
            for m in cat_val.get("models", []):
                entry = dict(m)
                entry["category"] = cat_key  # 记录所属分类
                mid = entry.get("id")
                if not mid:
                    continue
                # 别名也指向同一 id，便于兼容中文名调用
                self._models[mid] = entry
        return self

    # ── 列表 / 查询 ──
    def list_models(self) -> List[str]:
        """返回全部模型 id（升序），长度应为 53。"""
        return sorted(self._models.keys())

    def get_model(self, model_id: str) -> Dict[str, Any]:
        """返回目录条目（支持别名）。不存在则抛 KeyError。"""
        if model_id in CATALOG_ALIASES:
            model_id = CATALOG_ALIASES[model_id]
        if model_id not in self._models:
            raise KeyError(f"模型 '{model_id}' 不在目录中（共 {len(self._models)} 个）")
        return self._models[model_id]

    def get_category(self, model_id: str) -> str:
        """返回模型所属分类名。"""
        return self.get_model(model_id)["category"]

    # ── 构建 / 求解 ──
    def build_model(self, model_id: str) -> Any:
        """按分类构造对应求解器实例。"""
        entry = self.get_model(model_id)
        cls = MODEL_CATEGORY_MAP.get(entry["category"])
        if cls is None:
            raise KeyError(f"分类 '{entry['category']}' 暂无对应求解器类（未实现）")
        return cls(model_id, entry)

    def solve(self, model_id: str, **params: Any) -> Dict[str, Any]:
        """调度求解：解析别名 -> 构建求解器 -> 调用 solve。"""
        if model_id in CATALOG_ALIASES:
            model_id = CATALOG_ALIASES[model_id]
        solver = self.build_model(model_id)
        return solver.solve(**params)

    # ── 工具 schema 生成 ──
    def get_tool_schemas(self) -> Dict[str, Dict[str, Any]]:
        """为每个模型生成 function schema，返回 dict[model_id] = schema（共 53 条）。"""
        schemas: Dict[str, Dict[str, Any]] = {}
        for mid in self.list_models():
            entry = self._models[mid]
            schemas[mid] = self._build_schema(mid, entry)
        return schemas

    def _build_schema(self, model_id: str, entry: Dict[str, Any]) -> Dict[str, Any]:
        category = entry["category"]
        name = entry.get("name", model_id)
        desc = entry.get("description", "")
        description = f"{name}：{desc}".strip()

        properties: Dict[str, Any] = {
            "data_path": {
                "type": "string",
                "description": "数据文件路径（CSV）。回归/分类/聚类/降维类模型使用；"
                               "其它模型可通过对应参数或 JSON 文件传入数据。",
            }
        }
        required = ["data_path"]

        # 按分类补充常用参数（保持与 tools 契约一致）
        if category == "regression":
            properties["target_column"] = {
                "type": "string",
                "description": "目标列名（默认 'target'）",
            }
            properties["alpha"] = {
                "type": "number",
                "description": "正则化系数（ridge / lasso 使用）",
            }
        elif category == "time_series":
            properties["forecast_steps"] = {
                "type": "integer",
                "description": "预测步数（默认 3）",
            }
            properties["order"] = {
                "type": "array",
                "description": "ARIMA 阶数 [p,d,q]",
            }
        elif category == "optimization":
            properties["optimization_params_path"] = {
                "type": "string",
                "description": "线性规划参数 JSON 路径（含 c / A_ub / b_ub）",
            }
            required.append("optimization_params_path")
        elif category == "evaluation" and model_id == "ahp":
            properties["judgment_matrix_path"] = {
                "type": "string",
                "description": "判断矩阵 JSON 路径",
            }
            required.append("judgment_matrix_path")

        return {
            "type": "function",  # OpenAI function-calling 风格
            "function": {
                "name": f"solve_{model_id}",
                "description": description,
                "parameters": {
                    "type": "object",
                    "properties": properties,
                    "required": required,
                },
            },
        }


# 便捷单例（供 dispatcher 使用）
_default_factory: Dict[str, ModelFactory] = {}


def get_default_factory() -> ModelFactory:
    """返回（惰性创建的）默认工厂实例。"""
    key = "default"
    if key not in _default_factory:
        _default_factory[key] = ModelFactory()
    return _default_factory[key]
