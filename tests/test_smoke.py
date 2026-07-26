"""
端到端冒烟测试 (v3.4.2)
从题目输入到论文输出的完整流程验证。
使用非交互模式，所有审批自动批准。
"""
import pytest
import tempfile
import shutil
from pathlib import Path


@pytest.fixture
def tmp_project():
    """隔离的项目目录"""
    d = tempfile.mkdtemp()
    yield Path(d)
    shutil.rmtree(d, ignore_errors=True)


@pytest.fixture
def workflow(tmp_project):
    """非交互模式工作流"""
    import sys
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from main import MathModelingWorkflow
    return MathModelingWorkflow(str(tmp_project), non_interactive=True)


class TestEndToEndSmoke:
    """端到端冒烟测试"""

    def test_workflow_init(self, workflow):
        """工作流初始化正常"""
        assert workflow.project_dir.exists()
        assert workflow.approval_manager is not None
        assert workflow.approval_manager.non_interactive is True
        status = workflow.get_status()
        assert "current_stage" in status
        assert "stages" in status

    def test_run_all_no_error(self, workflow):
        """run_all() 完整流程不抛异常"""
        results = workflow.run_all()
        assert isinstance(results, dict)
        assert len(results) > 0

    def test_problem_analysis_stage(self, workflow):
        """题目解析阶段可执行"""
        result = workflow.run_stage("problem_analysis")
        assert result is not None

    def test_model_selection_stage(self, workflow):
        """模型选型阶段可执行"""
        # 先执行题目解析
        workflow.run_stage("problem_analysis")
        result = workflow.run_stage("model_selection")
        assert result is not None

    def test_data_processing_stage(self, workflow):
        """数据处理阶段可执行"""
        result = workflow.run_stage("data_processing")
        assert result is not None

    def test_model_solving_stage(self, workflow):
        """模型求解阶段可执行"""
        result = workflow.run_stage("model_solving")
        assert result is not None

    def test_visualization_stage(self, workflow):
        """可视化阶段可执行"""
        result = workflow.run_stage("visualization")
        assert result is not None

    def test_validation_stage(self, workflow):
        """验证阶段可执行"""
        result = workflow.run_stage("validation")
        assert result is not None

    def test_paper_writing_stage(self, workflow):
        """论文撰写阶段可执行"""
        result = workflow.run_stage("paper_writing")
        assert result is not None

    def test_get_status(self, workflow):
        """状态查询正常"""
        status = workflow.get_status()
        assert "stages" in status
        for stage in workflow.STAGES:
            assert stage in status["stages"]

    def test_cache_enabled(self, workflow):
        """缓存默认启用"""
        assert workflow.no_cache is False
        assert workflow.cache is not None

    def test_approval_non_interactive(self, workflow):
        """非交互模式下高风险操作自动批准"""
        op = workflow.approval_manager.request_approval({
            "operation_id": "test_critical",
            "risk_level": "critical",
            "description": "测试极高风险操作",
        })
        assert op["status"] == "auto_approved_non_interactive"

    def test_llm_agent_rule_fallback(self, workflow):
        """LLM Agent 无 LLM 时降级到规则模式"""
        from modules.llm_agent import run_with_llm
        result = run_with_llm(
            workflow,
            problem_text="这是一个测试优化问题，求最小化生产成本。",
            mode="hybrid",
            llm_call=None,
        )
        assert result["mode"] == "rule_fallback"
        assert "stages" in result

    def test_tool_protocol_schemas(self, workflow):
        """工具协议适配器可生成 schema"""
        from modules.tool_protocol import ToolProtocolAdapter
        adapter = ToolProtocolAdapter(wf=workflow)
        schemas = adapter.generate_tool_schemas()
        assert len(schemas) > 0
        assert schemas[0]["type"] == "function"

    def test_llm_client_import(self):
        """LLM 客户端模块可导入"""
        from modules.llm_client import LLMConfig
        config = LLMConfig()
        assert config.is_configured() is False  # 未设置 API Key 时

    def test_llm_client_analyze_no_api(self):
        """无 API Key 时 LLM 分析应优雅降级"""
        from modules.llm_client import LLMClient
        client = LLMClient()
        # 没有 API Key 时，analyze_problem 应返回空分析而非抛异常
        result = client.analyze_problem("测试题目")
        assert isinstance(result, dict)
        assert "problem_type" in result

    def test_performance_report(self, workflow):
        """性能报告可获取"""
        workflow.run_stage("problem_analysis")
        report = workflow.get_performance_report()
        assert "stage_times" in report
        if report["stage_times"]:
            assert "total_time" in report

    def test_clear_cache(self, workflow):
        """清空缓存正常"""
        workflow.run_stage("problem_analysis")
        workflow.clear_cache()
        status = workflow.get_status()
        assert status is not None

    def test_catalog_integrity(self):
        """catalog 文件完整（所有模型有 implemented 字段）"""
        import json
        catalog_path = Path(__file__).parent.parent / "config" / "model_catalog.json"
        assert catalog_path.exists()
        catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
        models = catalog.get("models", {})
        assert len(models) > 0
        for cat_name, cat_info in models.items():
            for m in cat_info.get("models", []):
                assert "implemented" in m, f"模型 {m.get('id')} 缺少 implemented 字段"
                assert isinstance(m["implemented"], bool), f"模型 {m.get('id')} implemented 不是 bool"

    def test_projects_template_exists(self, workflow):
        """模板目录自动创建"""
        from main import MathModelingWorkflow
        template = MathModelingWorkflow.ensure_template_exists()
        assert template.exists()
        readme = template / "problem_files" / "README.md"
        assert readme.exists()
