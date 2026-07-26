# 测试：层2 问题分析 actor-critic 精炼器（离线优先）
from modules.model_selection import analyze_problem, ProblemAnalysisRefiner


class TestProblemAnalysisRefiner:
    def test_offline_analyze_returns_both_stages(self):
        pa = analyze_problem("建立区域科技成果转化能力综合评价模型并对园区排序", rounds=2)
        assert pa.understanding is not None and pa.modeling_plan is not None
        assert pa.understanding.rounds == 2
        assert pa.modeling_plan.rounds == 2
        assert pa.understanding.final_output
        assert pa.modeling_plan.final_output
        assert not pa.metadata["used_llm"]

    def test_heuristic_type_detection(self):
        assert analyze_problem("预测城市共享单车未来需求").problem_type == "prediction"
        assert analyze_problem("优化物流中心选址").problem_type == "optimization"
        assert analyze_problem("对供应商进行综合评价排序").problem_type == "evaluation"

    def test_scores_in_range(self):
        pa = analyze_problem("基于历史销量做回归预测", rounds=1)
        for stage in (pa.understanding, pa.modeling_plan):
            assert 0.0 <= stage.final_score <= 10.0

    def test_llm_failure_degrades_to_rule(self):
        # 一个总会抛异常的 llm_call，应自动降级规则而非崩溃
        def boom(req):
            raise RuntimeError("network down")

        ref = ProblemAnalysisRefiner(llm_call=boom)
        pa = ref.analyze("预测未来电力负荷", rounds=1)
        assert pa is not None
        assert not pa.metadata["used_llm"]
        assert pa.understanding.final_output

    def test_history_records_each_round(self):
        pa = analyze_problem("评价高校科研绩效", rounds=2)
        assert len(pa.understanding.history) == 2
        assert all(r.actor_output and r.critic_output for r in pa.understanding.history)
