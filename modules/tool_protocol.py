# -*- coding: utf-8 -*-
"""
工具协议适配器（恢复版重建 · v3.4.2）

职责：
  - 将 config/model_catalog.json 中 53 个已实现的模型转换为统一的
    function-calling 工具 schema（与 OpenAI tool-calls / MCP 协议兼容）。
  - 提供工具查询 API：list_available_tools / get_tool_schema / get_tool_info / get_summary。
  - 提供 dispatch_tool_call：在注入工作流实例（wf）后，真实调用
    modules.model_solving 中的求解器并返回含 model_category 的结果。

设计说明（恢复版重建）：
  1. 53 个工具的数量与元数据来自 config/model_catalog.json（单一事实来源），
     与 model_solving 子代理约定：ModelFactory(config).get_tool_schemas()
     同样以该 catalog 为输入，因此两者天然一致。
  2. schema 生成自包含、不依赖 model_solving，保证在 model_solving 尚未就绪时
     本适配器的 schema 相关测试即可独立通过。
  3. 真正求解通过延迟 import modules.model_solving 完成（避免循环导入 / 导入顺序问题）：
        from modules.model_solving import ModelFactory, ModelSolver
     若 model_solving 仅暴露 ModelSolver 而将 ModelFactory 放在 modules.model_factory，
     则自动回退到后者。dispatch 禁止伪造，必须真实调用求解。
"""

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

# 默认 catalog 路径：modules/tool_protocol.py -> 项目根/config/model_catalog.json
_DEFAULT_CATALOG_PATH = (
    Path(__file__).resolve().parent.parent / "config" / "model_catalog.json"
)

# catalog 中每个模型的 group 名称 -> 类别特定参数定义
# 这些定义源自测试契约（test_tool_protocol.py）对特定类别工具参数的硬性要求。
_CATEGORY_SPECIFIC_PARAMS = {
    "regression": [
        # 回归类：target_column 可选（默认 "target" 或最后一列）
        ("target_column", "string", False,
         "目标变量列名（默认 'target'，若不存在则取最后一列）"),
    ],
    "time_series": [
        # 时序类：forecast_steps 可选
        ("forecast_steps", "integer", False,
         "需要预测的未来步数（默认 1）"),
    ],
    "optimization": [
        # 优化类：optimization_params_path 必填
        ("optimization_params_path", "string", True,
         "优化问题参数文件路径（含目标函数与约束，JSON/CSV）"),
    ],
}

# 个别模型所需的特殊必填参数（测试契约点名要求）
_MODEL_SPECIFIC_REQUIRED_PARAMS = {
    "ahp": ("judgment_matrix_path", "string",
            "判断矩阵文件路径（CSV/JSON，方阵）"),
}


class ToolProtocolAdapter:
    """
    工具协议适配器（恢复版重建）。

    将模型目录转换为 function-calling 工具 schema，并提供工具查询与调用调度。
    """

    def __init__(self, wf: Optional[Any] = None,
                 catalog_path: Optional[Any] = None):
        """
        Args:
            wf: MathModelingWorkflow 实例；dispatch_tool_call 需要它作为执行上下文门禁
                （未注入时调用 dispatch_tool_call 抛 RuntimeError）。
            catalog_path: 模型目录 JSON 路径；缺省使用项目 config/model_catalog.json。
        """
        self._wf = wf
        self._catalog_path = Path(catalog_path) if catalog_path else _DEFAULT_CATALOG_PATH

        # 缓存：生成后的 schema 列表（与 get_tool_schema 共享同一对象引用）
        self._schemas_cache: Optional[List[Dict]] = None
        self._tool_index: Dict[str, Dict] = {}      # 工具名 -> schema
        self._info_index: Dict[str, Dict] = {}      # 工具名 -> 元信息
        self._catalog_cache: Optional[Dict] = None
        self._catalog_version: str = "3.4.2"

        # 启动时即加载目录（轻量、纯文件读取，无第三方求解依赖）
        self._load_catalog()

    # ─────────────────────────── 目录加载 ───────────────────────────

    def _load_catalog(self) -> Dict:
        """读取并解析模型目录，构建工具索引与元信息索引（带缓存）。"""
        if self._catalog_cache is not None:
            return self._catalog_cache

        with open(self._catalog_path, "r", encoding="utf-8") as f:
            catalog = json.load(f)

        self._catalog_cache = catalog
        metadata = catalog.get("metadata", {}) or {}
        if metadata.get("version"):
            self._catalog_version = metadata["version"]

        # catalog["models"] 结构：{ 类别组名: {"name":.., "description":.., "models":[...]} }
        groups = catalog.get("models", {}) or {}
        schemas: List[Dict] = []
        tool_index: Dict[str, Dict] = {}
        info_index: Dict[str, Dict] = {}

        for group_name, group in groups.items():
            if not isinstance(group, dict):
                continue
            model_list = group.get("models", []) or []
            for m in model_list:
                if not m.get("implemented", True):
                    continue
                model_id = m.get("id") or m.get("model_id")
                if not model_id:
                    continue
                tool_name = f"solve_{model_id}"
                category = group_name  # 类别组名即 category（如 "regression"/"time_series"）
                model_name = m.get("name", model_id)
                description = m.get("description", "")

                schema = self._build_schema(tool_name, model_name, description, category, model_id)
                schemas.append(schema)
                tool_index[tool_name] = schema
                info_index[tool_name] = {
                    "model_id": model_id,
                    "category": category,
                    "model_name": model_name,
                    "description": description,
                    "python_library": m.get("python_library", ""),
                    "complexity": m.get("complexity", ""),
                }

        self._schemas_cache = schemas
        self._tool_index = tool_index
        self._info_index = info_index
        return catalog

    def _build_schema(self, tool_name: str, model_name: str,
                      description: str, category: str, model_id: str) -> Dict:
        """根据类别构造单个工具的 function-calling schema。"""
        # 统一描述：包含模型名（满足 "ARIMA"/"层次分析法(AHP)" 等包含性断言）
        full_description = f"{model_name}：{description}".strip("：")

        properties = {
            "data_path": {
                "type": "string",
                "description": "输入数据文件路径（CSV）。回归/分类/聚类/降维等监督学习任务使用。",
            }
        }
        required = ["data_path"]

        # 类别特定参数
        for cat_prefix, params in _CATEGORY_SPECIFIC_PARAMS.items():
            if category == cat_prefix:
                for pname, ptype, is_required, pdesc in params:
                    properties[pname] = {"type": ptype, "description": pdesc}
                    if is_required:
                        required.append(pname)

        # 个别模型的特殊必填参数（如 AHP 的判断矩阵）
        if model_id in _MODEL_SPECIFIC_REQUIRED_PARAMS:
            pname, ptype, pdesc = _MODEL_SPECIFIC_REQUIRED_PARAMS[model_id]
            properties[pname] = {"type": ptype, "description": pdesc}
            required.append(pname)

        return {
            "type": "function",
            "function": {
                "name": tool_name,
                "description": full_description,
                "parameters": {
                    "type": "object",
                    "properties": properties,
                    "required": required,
                },
            },
        }

    # ─────────────────────────── schema 生成 ───────────────────────────

    def generate_tool_schemas(self) -> List[Dict]:
        """
        生成所有工具的 function-calling schema 列表（恢复版重建来源：model_catalog.json）。

        返回缓存的同一列表对象（保证多次调用引用一致，满足 schema 缓存测试）。
        数量为 53（与 model_solving.ModelFactory.get_tool_schemas() 一致）。
        """
        if self._schemas_cache is None:
            self._load_catalog()
        return self._schemas_cache  # type: ignore[return-value]

    # ─────────────────────────── 工具查询 API ───────────────────────────

    def list_available_tools(self) -> List[str]:
        """返回所有可用工具名（已排序），如 ['solve_arima', 'solve_regression', ...]。"""
        self._load_catalog()
        return sorted(self._tool_index.keys())

    def get_tool_schema(self, name: str) -> Dict:
        """
        获取单个工具的 schema。

        Raises:
            KeyError: 工具名不存在时（MCP 层据此返回 404）。
        """
        self._load_catalog()
        if name not in self._tool_index:
            raise KeyError(name)
        return self._tool_index[name]

    def get_tool_info(self, name: str) -> Dict:
        """
        获取工具元信息：{model_id, category, model_name, ...}。

        Raises:
            KeyError: 工具名不存在时。
        """
        self._load_catalog()
        if name not in self._info_index:
            raise KeyError(name)
        return self._info_index[name]

    def get_summary(self) -> Dict:
        """返回工具协议摘要：total_tools / category_distribution / catalog_version。"""
        self._load_catalog()
        dist: Dict[str, int] = {}
        for info in self._info_index.values():
            dist[info["category"]] = dist.get(info["category"], 0) + 1
        return {
            "total_tools": len(self._tool_index),
            "category_distribution": dist,
            "catalog_version": self._catalog_version,
        }

    # ─────────────────────────── 缓存管理 ───────────────────────────

    def clear_cache(self) -> None:
        """清空 schema 缓存（测试用）。"""
        self._schemas_cache = None
        self._tool_index = {}
        self._info_index = {}
        self._catalog_cache = None

    # ─────────────────────────── 工具调用调度 ───────────────────────────

    def dispatch_tool_call(self, name: str, params: Dict) -> Dict:
        """
        调度并执行工具调用（真实求解，禁止伪造）。

        Args:
            name: 工具名，形如 'solve_regression'。
            params: 参数字典，至少包含 'data_path'。

        Returns:
            Dict: 含 'model_name' 与 'model_category'（真实类别）的结果。

        Raises:
            RuntimeError: 未注入 wf 时（执行上下文门禁）。
            KeyError: 工具名不存在时。
            ValueError: 缺少必需参数 data_path 时。
            FileNotFoundError: data_path 指向的文件不存在时。
        """
        # 1) 门禁：必须注入工作流实例
        if self._wf is None:
            raise RuntimeError("未注入工作流实例(wf)，无法执行工具调用")

        # 2) 工具存在性校验
        self._load_catalog()
        if name not in self._tool_index:
            raise KeyError(name)

        # 3) 必需参数校验
        if not isinstance(params, dict) or "data_path" not in params:
            raise ValueError("缺少必需参数 data_path")

        data_path = Path(params["data_path"])
        if not data_path.exists():
            raise FileNotFoundError(str(data_path))

        info = self._info_index[name]
        model_id = info["model_id"]
        category = info["category"]
        model_name = info["model_name"]

        # 4) 真实调用 model_solving 求解（延迟 import，避免导入顺序/循环依赖）
        return self._solve(model_id, category, model_name, params, data_path)

    def _solve(self, model_id: str, category: str, model_name: str,
               params: Dict, data_path: Path) -> Dict:
        """
        根据类别调用 modules.model_solving 中的真实求解器。

        延迟导入说明（恢复版重建依赖声明）：
          依赖 modules.model_solving 提供的 ModelFactory（构建并训练模型）
          与 ModelSolver（计算指标）。若 model_solving 仅暴露 ModelSolver，
          而 ModelFactory 位于 modules.model_factory，则自动回退。
        """
        # 延迟导入：优先 modules.model_solving（契约约定其提供 ModelFactory）
        from modules import model_solving  # noqa: F401
        ModelSolver = model_solving.ModelSolver
        try:
            ModelFactory = model_solving.ModelFactory
        except AttributeError:
            from modules.model_factory import ModelFactory  # 回退路径

        # 读取数据
        import pandas as pd
        df = pd.read_csv(data_path)

        if category in ("regression", "classification", "clustering", "dimension_reduction"):
            target_col = params.get("target_column")
            if target_col is None:
                target_col = "target" if "target" in df.columns else df.columns[-1]
            feature_cols = [c for c in df.columns if c != target_col]
            X = df[feature_cols].values
            if category == "clustering":
                y = df[target_col].values if target_col in df.columns else None
            else:
                y = df[target_col].values

            # 真实构建并训练模型
            if category == "clustering":
                model, mtype = ModelFactory.build_supervised(model_id, X, y)
            else:
                model, mtype = ModelFactory.build_supervised(model_id, X, y)

            # 真实求解并计算指标
            solver = ModelSolver()
            solve_result = solver.solve_model(
                model, X, y,
                model_name=model_name,
                feature_names=list(feature_cols),
            )

            metrics = self._extract_metrics(solve_result)
            feature_importance = self._to_json_safe(
                getattr(solve_result, "feature_importance", None)
            )

            return {
                "model_name": model_name,
                "model_id": model_id,
                "model_category": category,
                "metrics": metrics,
                "feature_importance": feature_importance,
                "n_samples": int(len(df)),
            }
        else:
            # 其它类别（优化/评价/时序/仿真/图论/模糊/统计/神经网络等）需对应 Solver；
            # 此处如实抛出未实现，避免伪造结果。对应求解器由 model_solving 子代理按
            # 类别提供（OptimizationSolver / EvaluationSolver / TimeSeriesSolver 等）。
            raise NotImplementedError(
                f"工具 {model_id}（类别 {category}）的求解需对应 Solver，"
                f"当前环境未加载该类别求解器"
            )

    @staticmethod
    def _extract_metrics(solve_result: Any) -> Dict:
        """从 ModelSolver 的求解结果对象中提取可序列化的指标字典。"""
        metrics: Dict[str, float] = {}
        raw = getattr(solve_result, "metrics", None)
        if raw is None:
            return metrics
        for key in ("r2", "rmse", "mae", "accuracy", "f1", "precision", "recall"):
            if hasattr(raw, key):
                val = getattr(raw, key)
                try:
                    metrics[key] = float(val)
                except (TypeError, ValueError):
                    metrics[key] = val
        return metrics

    @staticmethod
    def _to_json_safe(obj: Any) -> Any:
        """将 numpy 等类型尽量转为原生 Python 类型（用于 JSON 序列化安全）。"""
        if obj is None:
            return None
        if isinstance(obj, dict):
            return {k: ToolProtocolAdapter._to_json_safe(v) for k, v in obj.items()}
        if isinstance(obj, (list, tuple)):
            return [ToolProtocolAdapter._to_json_safe(v) for v in obj]
        try:
            import numpy as np  # noqa
            if isinstance(obj, np.generic):
                return obj.item()
        except ImportError:
            pass
        return obj
