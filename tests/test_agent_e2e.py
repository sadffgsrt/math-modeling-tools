"""
Agent 端到端集成测试
验证 Agent 能否自主完成完整建模流程（题目解析 → 模型选择 → 求解 → 反思）

测试场景：
1. 端到端 rule_fallback 模式：优化类问题完整流程
2. 端到端 rule_fallback 模式：预测类问题完整流程
3. 端到端 hybrid 模式：mock LLM 自主选择模型
4. 端到端 pure_llm 模式：mock LLM tool-calling 全流程
5. 反思引擎评估：验证反思报告结构
6. 记忆系统：验证经验积累和检索
7. MCP Server 端到端：HTTP 调用完整流程
8. 决策持久化：验证历史保存
"""
import sys
import json
import tempfile
import shutil
import socket
import gc
from pathlib import Path
from unittest import TestCase, main as unittest_main

sys.path.insert(0, str(Path(__file__).parent.parent))

import numpy as np
import pandas as pd


def _get_free_port():
    """获取一个可用端口"""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class TestAgentE2E(TestCase):
    """Agent 端到端集成测试：验证自主建模全流程"""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.project_dir = Path(self.temp_dir) / "e2e_project"

        # 准备优化类题目
        self.optimization_problem = """
        问题一：生产调度优化问题

        某工厂有若干加工工位，需要调度作业顺序。
        设作业当前位置为x，需要访问的工位为y_i。
        设备移动速度为v，每个工位的加工时间为t_i。

        约束条件：
        1. 设备只能沿轨道单向移动
        2. 每个工位同一时间只能被一台设备访问
        3. 加工过程中不能中断

        目标：最小化总完成时间
        """

        # 准备预测类题目
        self.prediction_problem = """
        问题一：城市交通流量预测

        某城市需要预测未来一周的交通流量。
        已知过去 30 天的每小时交通流量数据。
        设时间为t，交通流量为y_t。

        目标：预测未来 7 天的交通流量
        """

        # 准备回归测试数据
        np.random.seed(42)
        n = 100
        self.regression_data = pd.DataFrame({
            'feature_1': np.random.randn(n),
            'feature_2': np.random.uniform(0, 10, n),
            'feature_3': np.random.randn(n) * 2,
            'target': 2 * np.random.randn(n) + 1 + np.random.randn(n) * 0.3,
        })
        self.data_path = Path(self.temp_dir) / "regression_data.csv"
        self.regression_data.to_csv(self.data_path, index=False)

        # 准备优化参数
        self.opt_params = {
            "c": [-3.0, -5.0],
            "A_ub": [[1.0, 0.0], [0.0, 2.0], [1.0, 1.0]],
            "b_ub": [4.0, 12.0, 8.0],
            "bounds": [[0, None], [0, None]],
        }
        self.opt_params_path = Path(self.temp_dir) / "opt_params.json"
        self.opt_params_path.write_text(
            json.dumps(self.opt_params), encoding="utf-8"
        )

    def tearDown(self):
        gc.collect()
        try:
            shutil.rmtree(self.temp_dir)
        except PermissionError:
            pass

    def _make_workflow(self):
        """创建非交互工作流"""
        from main import MathModelingWorkflow
        return MathModelingWorkflow(str(self.project_dir), non_interactive=True)

    def _make_mock_llm_for_regression(self):
        """创建针对回归问题的 mock LLM"""
        call_count = [0]

        def mock_llm(request):
            call_count[0] += 1
            if call_count[0] == 1:
                return {
                    "tool_calls": [{
                        "id": f"call_{call_count[0]}",
                        "type": "function",
                        "function": {
                            "name": "solve_regression",
                            "arguments": json.dumps({
                                "data_path": str(self.data_path)
                            }),
                        }
                    }]
                }
            return {"content": "建模完成，已选择线性回归模型。"}

        return mock_llm

    # ═══════════════════════════════════════════════════════
    # 测试 1：rule_fallback 模式 - 优化类完整流程
    # ═══════════════════════════════════════════════════════

    def test_e2e_rule_fallback_optimization(self):
        """端到端：rule_fallback 模式处理优化类问题"""
        from modules.llm_agent import run_with_llm

        workflow = self._make_workflow()
        result = run_with_llm(
            workflow,
            problem_text=self.optimization_problem,
            mode="rule_fallback",
        )

        # 验证基本结构
        self.assertEqual(result["mode"], "rule_fallback")
        self.assertTrue(result["success"])

        # 验证题目解析完成
        self.assertIn("problem_analysis", result)
        analysis = result["problem_analysis"]
        self.assertEqual(analysis["problem_type"], "optimization")

        # 验证阶段序列（优化类无 visualization）
        decisions = result["decisions"]
        rule_decision = [d for d in decisions if d.get("type") == "rule_based"][0]
        path = rule_decision["execution_path"]
        self.assertIn("data_processing", path)
        self.assertIn("model_solving", path)
        self.assertIn("validation", path)
        self.assertNotIn("visualization", path)

        # 验证反思报告存在
        self.assertIn("reflection", result)
        reflection = result["reflection"]
        self.assertIn("overall_score", reflection)
        self.assertGreaterEqual(reflection["overall_score"], 0)
        self.assertLessEqual(reflection["overall_score"], 10)

    # ═══════════════════════════════════════════════════════
    # 测试 2：rule_fallback 模式 - 预测类完整流程
    # ═══════════════════════════════════════════════════════

    def test_e2e_rule_fallback_prediction(self):
        """端到端：rule_fallback 模式处理预测类问题"""
        from modules.llm_agent import run_with_llm

        workflow = self._make_workflow()
        result = run_with_llm(
            workflow,
            problem_text=self.prediction_problem,
            mode="rule_fallback",
        )

        self.assertEqual(result["mode"], "rule_fallback")

        # 验证阶段序列（预测类含 visualization）
        decisions = result["decisions"]
        rule_decision = [d for d in decisions if d.get("type") == "rule_based"][0]
        path = rule_decision["execution_path"]
        self.assertIn("visualization", path)

    # ═══════════════════════════════════════════════════════
    # 测试 3：hybrid 模式 - mock LLM 选择模型
    # ═══════════════════════════════════════════════════════

    def test_e2e_hybrid_with_mock_llm(self):
        """端到端：hybrid 模式使用 mock LLM 选择回归模型"""
        from modules.llm_agent import run_with_llm

        mock_llm = self._make_mock_llm_for_regression()
        workflow = self._make_workflow()

        result = run_with_llm(
            workflow,
            problem_text=self.optimization_problem,
            mode="hybrid",
            llm_call=mock_llm,
        )

        self.assertEqual(result["mode"], "hybrid")

        # 验证 LLM 参与了模型选择
        model_decisions = [
            d for d in result["decisions"]
            if d.get("type") == "model_selection"
        ]
        self.assertGreater(len(model_decisions), 0)

        # 验证有 tool_call 执行
        if result["tool_calls"]:
            tc = result["tool_calls"][0]
            self.assertEqual(tc["tool_name"], "solve_regression")
            self.assertEqual(tc["status"], "success")

    # ═══════════════════════════════════════════════════════
    # 测试 4：pure_llm 模式 - mock LLM tool-calling 全流程
    # ═══════════════════════════════════════════════════════

    def test_e2e_pure_llm_tool_calling(self):
        """端到端：pure_llm 模式 mock LLM 通过 tool-calling 自主建模"""
        from modules.llm_agent import run_with_llm

        mock_llm = self._make_mock_llm_for_regression()
        workflow = self._make_workflow()

        result = run_with_llm(
            workflow,
            problem_text=self.optimization_problem,
            mode="pure_llm",
            llm_call=mock_llm,
        )

        self.assertEqual(result["mode"], "pure_llm")

        # 验证有 tool_call
        self.assertGreater(len(result["tool_calls"]), 0)
        first_call = result["tool_calls"][0]
        self.assertEqual(first_call["tool_name"], "solve_regression")

        # 验证决策被记录
        self.assertGreater(len(result["decisions"]), 0)

    # ═══════════════════════════════════════════════════════
    # 测试 5：反思引擎评估
    # ═══════════════════════════════════════════════════════

    def test_reflection_engine_evaluates_result(self):
        """反思引擎正确评估执行结果"""
        from modules.llm_agent import ReflectionEngine

        engine = ReflectionEngine(llm_call=None)

        # 模拟执行结果
        problem_analysis = {"problem_type": "optimization"}
        tool_calls = [
            {"tool_name": "solve_regression", "status": "success",
             "result": {"r2": 0.85}},
        ]
        stages = [
            {"name": "problem_analysis", "status": "completed"},
            {"name": "data_processing", "status": "completed"},
            {"name": "model_solving", "status": "completed"},
        ]

        reflection = engine.evaluate_result(problem_analysis, tool_calls, stages)

        # 验证反思报告结构
        self.assertIn("model_selection_score", reflection)
        self.assertIn("result_quality_score", reflection)
        self.assertIn("stage_completeness_score", reflection)
        self.assertIn("overall_score", reflection)
        self.assertIn("improvement_suggestions", reflection)
        self.assertIn("evaluation_method", reflection)
        self.assertEqual(reflection["evaluation_method"], "rule_based")

        # 验证评分范围
        for score_key in ["model_selection_score", "result_quality_score",
                          "stage_completeness_score", "overall_score"]:
            score = reflection[score_key]
            self.assertGreaterEqual(score, 0)
            self.assertLessEqual(score, 10)

    def test_reflection_engine_failed_calls(self):
        """反思引擎对失败 tool_call 给出低分"""
        from modules.llm_agent import ReflectionEngine

        engine = ReflectionEngine(llm_call=None)
        tool_calls = [
            {"tool_name": "solve_xxx", "status": "failed", "error": "test"},
        ]
        stages = []

        reflection = engine.evaluate_result({}, tool_calls, stages)

        # 失败调用应导致模型选择评分较低
        self.assertLessEqual(reflection["model_selection_score"], 5)
        # 应有改进建议
        self.assertGreater(len(reflection["improvement_suggestions"]), 0)

    def test_reflection_suggest_next_action(self):
        """反思引擎建议下一步行动"""
        from modules.llm_agent import ReflectionEngine

        engine = ReflectionEngine(llm_call=None)

        # 高分 → complete
        good_reflection = {"overall_score": 8, "improvement_suggestions": []}
        action = engine.suggest_next_action(good_reflection)
        self.assertEqual(action["action"], "complete")

        # 中分 → refine
        mid_reflection = {"overall_score": 5, "improvement_suggestions": ["优化参数"]}
        action = engine.suggest_next_action(mid_reflection)
        self.assertEqual(action["action"], "refine")

        # 低分 → retry
        bad_reflection = {"overall_score": 2, "improvement_suggestions": ["重试"]}
        action = engine.suggest_next_action(bad_reflection)
        self.assertEqual(action["action"], "retry")

    # ═══════════════════════════════════════════════════════
    # 测试 6：记忆系统
    # ═══════════════════════════════════════════════════════

    def test_memory_system_accumulates_experience(self):
        """记忆系统积累建模经验"""
        from modules.llm_agent import AgentMemory

        memory_file = Path(self.temp_dir) / "memory.json"
        memory = AgentMemory(memory_file)

        # 添加两条记忆
        memory.add_memory(
            problem_type="optimization",
            tool_used="solve_linear_programming",
            result_summary="成功求解 LP",
            success=True,
            reflection={"overall_score": 8.5},
        )
        memory.add_memory(
            problem_type="optimization",
            tool_used="solve_regression",
            result_summary="回归 r2=0.7",
            success=False,
            reflection={"overall_score": 4.0},
        )

        # 验证记忆数量
        self.assertEqual(len(memory.memories), 2)

        # 验证文件持久化
        self.assertTrue(memory_file.exists())
        saved = json.loads(memory_file.read_text(encoding="utf-8"))
        self.assertEqual(saved["total"], 2)

        # 验证相似问题搜索（成功的优先）
        similar = memory.search_similar("optimization")
        self.assertEqual(len(similar), 2)
        self.assertTrue(similar[0]["success"])  # 成功的排前面

        # 验证最佳实践
        best = memory.get_best_practice("optimization")
        self.assertIsNotNone(best)
        self.assertTrue(best["success"])

    def test_memory_system_summary(self):
        """记忆系统摘要统计"""
        from modules.llm_agent import AgentMemory

        memory_file = Path(self.temp_dir) / "memory2.json"
        memory = AgentMemory(memory_file)

        memory.add_memory("optimization", "tool_a", "ok", True, {"overall_score": 8})
        memory.add_memory("prediction", "tool_b", "ok", True, {"overall_score": 7})
        memory.add_memory("optimization", "tool_c", "fail", False, {"overall_score": 3})

        summary = memory.get_summary()
        self.assertEqual(summary["total_memories"], 3)
        self.assertEqual(summary["successful"], 2)
        self.assertAlmostEqual(summary["success_rate"], 66.7, places=1)
        self.assertEqual(summary["problem_type_distribution"]["optimization"], 2)
        self.assertEqual(summary["problem_type_distribution"]["prediction"], 1)

    # ═══════════════════════════════════════════════════════
    # 测试 7：MCP Server 端到端
    # ═══════════════════════════════════════════════════════

    def test_mcp_server_e2e_list_and_call(self):
        """MCP Server 端到端：列出工具 + 调用工具"""
        import urllib.request

        from modules.mcp_server import create_mcp_server

        port = _get_free_port()
        workflow = self._make_workflow()
        server = create_mcp_server(workflow, port=port)
        server.start_background()

        try:
            # 1. 列出工具
            url = f"http://127.0.0.1:{port}/tools"
            with urllib.request.urlopen(url) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            self.assertEqual(len(data["tools"]), 53)

            # 2. 获取工具 schema
            url = f"http://127.0.0.1:{port}/tools/solve_regression"
            with urllib.request.urlopen(url) as resp:
                schema = json.loads(resp.read().decode("utf-8"))
            self.assertEqual(schema["function"]["name"], "solve_regression")

            # 3. 调用工具
            url = f"http://127.0.0.1:{port}/tools/solve_regression/call"
            payload = json.dumps({"data_path": str(self.data_path)}).encode("utf-8")
            req = urllib.request.Request(
                url, data=payload,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req) as resp:
                result = json.loads(resp.read().decode("utf-8"))
            self.assertEqual(result["model_category"], "regression")
        finally:
            server.stop()

    def test_mcp_server_with_auth(self):
        """MCP Server 认证：无 key 返回 401，有 key 通过"""
        import urllib.request
        import urllib.error

        from modules.mcp_server import create_mcp_server

        port = _get_free_port()
        workflow = self._make_workflow()
        server = create_mcp_server(workflow, port=port, api_key="secret123")
        server.start_background()

        try:
            # /health 豁免认证
            url = f"http://127.0.0.1:{port}/health"
            with urllib.request.urlopen(url) as resp:
                self.assertEqual(resp.status, 200)

            # /tools 无 key 返回 401
            url = f"http://127.0.0.1:{port}/tools"
            with self.assertRaises(urllib.error.HTTPError) as ctx:
                urllib.request.urlopen(url)
            self.assertEqual(ctx.exception.code, 401)

            # /tools 有 key 通过
            req = urllib.request.Request(url)
            req.add_header("Authorization", "Bearer secret123")
            with urllib.request.urlopen(req) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            self.assertEqual(len(data["tools"]), 53)
        finally:
            server.stop()

    # ═══════════════════════════════════════════════════════
    # 测试 8：决策持久化
    # ═══════════════════════════════════════════════════════

    def test_decision_history_persisted(self):
        """决策历史持久化到文件"""
        from modules.llm_agent import run_with_llm

        workflow = self._make_workflow()
        result = run_with_llm(
            workflow,
            problem_text=self.optimization_problem,
            mode="rule_fallback",
        )

        # 验证历史文件存在
        history_file = workflow.project_dir / "results" / "llm_decisions.json"
        self.assertTrue(history_file.exists())

        # 验证历史内容
        history = json.loads(history_file.read_text(encoding="utf-8"))
        self.assertIn("history", history)
        self.assertGreater(len(history["history"]), 0)

        # 验证记录结构
        record = history["history"][0]
        self.assertIn("timestamp", record)
        self.assertIn("mode", record)
        self.assertEqual(record["mode"], "rule_fallback")
        self.assertIn("decisions", record)
        self.assertIn("success", record)

    def test_decision_history_appends(self):
        """多次运行追加到历史（非覆盖）"""
        from modules.llm_agent import run_with_llm

        workflow = self._make_workflow()

        # 第一次运行
        run_with_llm(workflow, problem_text=self.optimization_problem,
                     mode="rule_fallback")

        # 第二次运行
        run_with_llm(workflow, problem_text=self.prediction_problem,
                     mode="rule_fallback")

        history_file = workflow.project_dir / "results" / "llm_decisions.json"
        history = json.loads(history_file.read_text(encoding="utf-8"))
        self.assertGreaterEqual(len(history["history"]), 2)

    # ═══════════════════════════════════════════════════════
    # 测试 9：Agent 记忆文件生成
    # ═══════════════════════════════════════════════════════

    def test_agent_memory_file_created(self):
        """Agent 运行后生成记忆文件"""
        from modules.llm_agent import run_with_llm

        workflow = self._make_workflow()
        run_with_llm(
            workflow,
            problem_text=self.optimization_problem,
            mode="rule_fallback",
        )

        memory_file = workflow.project_dir / "results" / "agent_memory.json"
        self.assertTrue(memory_file.exists())

        memory_data = json.loads(memory_file.read_text(encoding="utf-8"))
        self.assertGreater(len(memory_data["memories"]), 0)

        mem = memory_data["memories"][0]
        self.assertEqual(mem["problem_type"], "optimization")
        self.assertIn("success", mem)
        self.assertIn("timestamp", mem)

    # ═══════════════════════════════════════════════════════
    # 测试 10：ToolProtocol 端到端
    # ═══════════════════════════════════════════════════════

    def test_tool_protocol_e2e_dispatch(self):
        """ToolProtocolAdapter 端到端：生成 schema → 调用 → 获取结果"""
        from modules.tool_protocol import ToolProtocolAdapter

        workflow = self._make_workflow()
        adapter = ToolProtocolAdapter(wf=workflow)

        # 1. 生成所有 schema
        schemas = adapter.generate_tool_schemas()
        self.assertEqual(len(schemas), 53)

        # 2. 查找回归工具
        tool_names = adapter.list_available_tools()
        self.assertIn("solve_regression", tool_names)

        # 3. 获取 schema
        schema = adapter.get_tool_schema("solve_regression")
        self.assertEqual(schema["function"]["name"], "solve_regression")
        self.assertIn("data_path", schema["function"]["parameters"]["required"])

        # 4. 执行调用
        result = adapter.dispatch_tool_call(
            "solve_regression",
            {"data_path": str(self.data_path)},
        )
        self.assertEqual(result["model_category"], "regression")

    # ═══════════════════════════════════════════════════════
    # 测试 11：完整 Agent 流程（反思 + 记忆 + 持久化）
    # ═══════════════════════════════════════════════════════

    def test_full_agent_pipeline_with_reflection_and_memory(self):
        """完整 Agent 流程：执行 → 反思 → 记忆 → 持久化"""
        from modules.llm_agent import run_with_llm

        workflow = self._make_workflow()
        result = run_with_llm(
            workflow,
            problem_text=self.optimization_problem,
            mode="rule_fallback",
        )

        # 验证完整流程产出
        self.assertTrue(result["success"])
        self.assertIn("reflection", result)
        self.assertIn("stages", result)
        self.assertIn("decisions", result)

        # 验证反思报告
        reflection = result["reflection"]
        self.assertGreater(reflection["overall_score"], 0)

        # 验证文件产出
        results_dir = workflow.project_dir / "results"
        self.assertTrue((results_dir / "llm_decisions.json").exists())
        self.assertTrue((results_dir / "agent_memory.json").exists())
        self.assertTrue((results_dir / "problem_analysis.json").exists())

    # ═══════════════════════════════════════════════════════
    # 测试 12：统一 Tool 接口
    # ═══════════════════════════════════════════════════════

    def test_tool_registry(self):
        """ToolRegistry 注册和执行"""
        from modules.core import BaseTool, ToolResult, ToolRegistry

        # 创建自定义工具
        class DummyTool(BaseTool):
            @property
            def name(self):
                return "dummy_tool"
            @property
            def description(self):
                return "测试工具"
            @property
            def category(self):
                return "test"
            def get_schema(self):
                return {"type": "function", "function": {
                    "name": self.name, "description": self.description,
                    "parameters": {"type": "object", "properties": {}},
                }}
            def execute(self, **kwargs):
                return ToolResult(success=True, data={"result": "ok"})

        registry = ToolRegistry()
        registry.register(DummyTool())

        # 验证注册
        self.assertEqual(len(registry.list_names()), 1)
        self.assertIn("dummy_tool", registry.list_names())

        # 验证执行
        result = registry.execute("dummy_tool")
        self.assertTrue(result.success)
        self.assertEqual(result.data["result"], "ok")

        # 验证摘要
        summary = registry.get_summary()
        self.assertEqual(summary["total_tools"], 1)

        # 验证不存在工具
        result = registry.execute("nonexistent")
        self.assertFalse(result.success)


if __name__ == "__main__":
    unittest_main()
