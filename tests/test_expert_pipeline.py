# 测试：专家级建模流水线（端到端，离线确定性）
from modules.model_selection import run_expert_pipeline, ExpertPipeline


class TestExpertPipeline:
    def test_run_offline_full_plan(self):
        plan = run_expert_pipeline(
            "建立区域科技成果转化能力综合评价模型并对园区排序",
            data_description="20 个园区 8 项指标",
            tasknum=5,
        )
        # 层2
        assert plan.analysis.understanding and plan.analysis.modeling_plan
        # 层3
        assert plan.decomposition.tasks and plan.decomposition.tasknum == 5
        # 层4
        assert plan.selection.ranked_methods
        # 层6
        assert plan.refinement.final_approach
        # 层5/7
        assert plan.dag_results
        assert all(v["status"] == "success" for v in plan.dag_results.values())
        assert not plan.metadata["used_llm"]

    def test_downstream_nodes_have_upstream_context(self):
        plan = run_expert_pipeline("预测城市共享单车需求", tasknum=6)
        # 第一个节点无上游，其余应有
        keys = list(plan.dag_results.keys())
        assert plan.dag_results[keys[0]]["output"]["has_upstream_context"] is False
        assert all(plan.dag_results[k]["output"]["has_upstream_context"] for k in keys[1:])

    def test_recommended_models_on_modeling_steps(self):
        plan = run_expert_pipeline("物流选址优化", tasknum=5)
        rec = [m for k, v in plan.dag_results.items()
               if v["output"]["phase"] in ("modeling", "solve")
               for m in v["output"]["recommended_models"]]
        assert rec, "建模/求解步骤应给出推荐模型"

    def test_save_plan_json(self, tmp_path):
        plan = run_expert_pipeline("评价高校绩效", tasknum=4)
        out = tmp_path / "plan.json"
        plan.save(str(out))
        assert out.exists() and out.stat().st_size > 0

    def test_llm_failure_degrades(self):
        def boom(req):
            raise RuntimeError("offline")

        plan = ExpertPipeline().run("预测电力负荷", llm_call=boom, analysis_rounds=1, formula_rounds=1)
        assert plan is not None
        assert not plan.metadata["used_llm"]
