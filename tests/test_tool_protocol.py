"""
数学建模竞赛工作流 - 工具协议适配器测试
验证 schema 生成、工具查询、tool_call 调度
"""

import sys
import json
import tempfile
import shutil
import numpy as np
import pandas as pd
from pathlib import Path
from unittest import TestCase, main as unittest_main

# 添加父目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))


class TestToolProtocol(TestCase):
    """步骤 2：工具协议适配器测试
    验证 schema 生成、工具查询、tool_call 调度
    """

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.project_dir = Path(self.temp_dir) / "test_tool_project"

    def tearDown(self):
        import gc
        gc.collect()
        try:
            shutil.rmtree(self.temp_dir)
        except PermissionError:
            pass

    def _make_adapter(self, wf=None):
        """创建 ToolProtocolAdapter 实例（不注入 wf，仅测试 schema 生成）"""
        from modules.tool_protocol import ToolProtocolAdapter
        catalog_path = Path(__file__).parent.parent / "config" / "model_catalog.json"
        return ToolProtocolAdapter(wf=wf, catalog_path=catalog_path)

    # ─── Schema 生成测试 ───

    def test_generate_tool_schemas_returns_list(self):
        """generate_tool_schemas 返回非空列表"""
        adapter = self._make_adapter()
        schemas = adapter.generate_tool_schemas()
        self.assertIsInstance(schemas, list)
        self.assertGreater(len(schemas), 0)

    def test_all_schemas_have_required_fields(self):
        """所有 schema 包含 type/function/name/description/parameters"""
        adapter = self._make_adapter()
        schemas = adapter.generate_tool_schemas()
        for schema in schemas:
            self.assertEqual(schema["type"], "function")
            self.assertIn("function", schema)
            func = schema["function"]
            self.assertIn("name", func)
            self.assertIn("description", func)
            self.assertIn("parameters", func)
            params = func["parameters"]
            self.assertEqual(params["type"], "object")
            self.assertIn("properties", params)
            self.assertIn("required", params)

    def test_tool_name_format(self):
        """工具名遵循 solve_<model_id> 格式"""
        adapter = self._make_adapter()
        schemas = adapter.generate_tool_schemas()
        for schema in schemas:
            name = schema["function"]["name"]
            self.assertTrue(name.startswith("solve_"),
                            f"工具名 '{name}' 不以 'solve_' 开头")

    def test_all_tools_have_data_path_param(self):
        """所有工具的 parameters 包含 data_path 属性"""
        adapter = self._make_adapter()
        schemas = adapter.generate_tool_schemas()
        for schema in schemas:
            props = schema["function"]["parameters"]["properties"]
            self.assertIn("data_path", props,
                          f"工具 {schema['function']['name']} 缺少 data_path 参数")
            self.assertIn("data_path", schema["function"]["parameters"]["required"])

    def test_tool_count_matches_catalog(self):
        """生成的工具数 = catalog 中 implemented=true 的模型数（55）"""
        adapter = self._make_adapter()
        schemas = adapter.generate_tool_schemas()
        self.assertEqual(len(schemas), 53)

    # ─── 工具查询 API 测试 ───

    def test_list_available_tools(self):
        """list_available_tools 返回排序的工具名列表"""
        adapter = self._make_adapter()
        tools = adapter.list_available_tools()
        self.assertIsInstance(tools, list)
        self.assertEqual(len(tools), 53)
        self.assertEqual(tools, sorted(tools))  # 已排序

    def test_get_tool_schema_existing(self):
        """get_tool_schema 返回已存在工具的 schema"""
        adapter = self._make_adapter()
        schema = adapter.get_tool_schema("solve_arima")
        self.assertEqual(schema["function"]["name"], "solve_arima")
        self.assertIn("ARIMA", schema["function"]["description"])

    def test_get_tool_schema_nonexistent(self):
        """get_tool_schema 对不存在的工具抛出 KeyError"""
        adapter = self._make_adapter()
        with self.assertRaises(KeyError):
            adapter.get_tool_schema("solve_nonexistent_model")

    def test_get_tool_info(self):
        """get_tool_info 返回工具元信息"""
        adapter = self._make_adapter()
        info = adapter.get_tool_info("solve_arima")
        self.assertEqual(info["model_id"], "arima")
        self.assertEqual(info["category"], "time_series")
        self.assertIn("ARIMA", info["model_name"])

    # ─── 类别特定参数测试 ───

    def test_optimization_tool_has_optimization_params(self):
        """优化类工具包含 optimization_params_path 参数且为 required"""
        adapter = self._make_adapter()
        schema = adapter.get_tool_schema("solve_linear_programming")
        params = schema["function"]["parameters"]
        self.assertIn("optimization_params_path", params["properties"])
        self.assertIn("optimization_params_path", params["required"])

    def test_ahp_tool_has_judgment_matrix(self):
        """AHP 工具包含 judgment_matrix_path 且为 required"""
        adapter = self._make_adapter()
        schema = adapter.get_tool_schema("solve_ahp")
        params = schema["function"]["parameters"]
        self.assertIn("judgment_matrix_path", params["properties"])
        self.assertIn("judgment_matrix_path", params["required"])

    def test_regression_tool_has_target_column(self):
        """回归类工具包含 target_column 参数（非 required）"""
        adapter = self._make_adapter()
        schema = adapter.get_tool_schema("solve_regression")
        params = schema["function"]["parameters"]
        self.assertIn("target_column", params["properties"])
        self.assertNotIn("target_column", params["required"])

    def test_time_series_tool_has_forecast_steps(self):
        """时序类工具包含 forecast_steps 参数"""
        adapter = self._make_adapter()
        schema = adapter.get_tool_schema("solve_arima")
        params = schema["function"]["parameters"]
        self.assertIn("forecast_steps", params["properties"])

    # ─── dispatch_tool_call 测试 ───

    def test_dispatch_without_wf_raises(self):
        """未注入 wf 时调用 dispatch_tool_call 抛 RuntimeError"""
        adapter = self._make_adapter(wf=None)
        with self.assertRaises(RuntimeError):
            adapter.dispatch_tool_call("solve_arima", {"data_path": "test.csv"})

    def test_dispatch_unknown_tool_raises(self):
        """dispatch_tool_call 对未知工具抛 KeyError"""
        from main import MathModelingWorkflow

        workflow = MathModelingWorkflow(str(self.project_dir))
        adapter = self._make_adapter(wf=workflow)
        with self.assertRaises(KeyError):
            adapter.dispatch_tool_call("solve_nonexistent", {"data_path": "test.csv"})

    def test_dispatch_missing_data_path_raises(self):
        """dispatch_tool_call 缺少 data_path 抛 ValueError"""
        from main import MathModelingWorkflow

        workflow = MathModelingWorkflow(str(self.project_dir))
        adapter = self._make_adapter(wf=workflow)
        with self.assertRaises(ValueError):
            adapter.dispatch_tool_call("solve_arima", {})

    def test_dispatch_nonexistent_file_raises(self):
        """dispatch_tool_call 对不存在的数据文件抛 FileNotFoundError"""
        from main import MathModelingWorkflow

        workflow = MathModelingWorkflow(str(self.project_dir))
        adapter = self._make_adapter(wf=workflow)
        with self.assertRaises(FileNotFoundError):
            adapter.dispatch_tool_call(
                "solve_arima",
                {"data_path": "nonexistent_file.csv"},
            )

    def test_dispatch_regression_success(self):
        """dispatch_tool_call 成功执行回归模型（端到端）"""
        from main import MathModelingWorkflow
        import pandas as pd

        # 准备测试数据
        np.random.seed(42)
        data = pd.DataFrame({
            'feature_1': np.random.randn(50),
            'feature_2': np.random.uniform(0, 10, 50),
            'target': 2 * np.random.randn(50) + 1,
        })
        data_path = Path(self.temp_dir) / "test_data.csv"
        data.to_csv(data_path, index=False)

        workflow = MathModelingWorkflow(str(self.project_dir), non_interactive=True)
        adapter = self._make_adapter(wf=workflow)
        result = adapter.dispatch_tool_call(
            "solve_regression",
            {"data_path": str(data_path)},
        )
        self.assertIn("model_name", result)
        self.assertEqual(result["model_category"], "regression")

    # ─── 缓存与摘要测试 ───

    def test_schema_caching(self):
        """schema 生成后缓存，第二次调用不重新加载"""
        adapter = self._make_adapter()
        schemas1 = adapter.generate_tool_schemas()
        schemas2 = adapter.generate_tool_schemas()
        self.assertIs(schemas1, schemas2)  # 同一对象引用

    def test_clear_cache(self):
        """clear_cache 后重新生成 schema"""
        adapter = self._make_adapter()
        adapter.generate_tool_schemas()
        adapter.clear_cache()
        self.assertIsNone(adapter._schemas_cache)
        # 重新生成
        schemas = adapter.generate_tool_schemas()
        self.assertEqual(len(schemas), 53)

    def test_get_summary(self):
        """get_summary 返回正确的摘要信息"""
        adapter = self._make_adapter()
        summary = adapter.get_summary()
        self.assertEqual(summary["total_tools"], 53)
        self.assertIn("category_distribution", summary)
        self.assertGreater(len(summary["category_distribution"]), 0)
        self.assertEqual(summary["catalog_version"], "3.4.2")


if __name__ == "__main__":
    unittest_main()
