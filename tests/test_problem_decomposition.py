# 测试：层3 层次化问题分解器
from modules.orchestration import compute_dag_order

from modules.model_selection import decompose_problem, ProblemDecomposer


class TestProblemDecomposition:
    def test_decompose_evaluation_default(self):
        d = decompose_problem("建立区域科技成果转化能力综合评价模型并排序")
        assert d.problem_type == "evaluation"
        assert d.tasks
        # 每个后续任务依赖前序（线性链）
        for i, t in enumerate(d.tasks):
            if i == 0:
                assert t.depends_on == []
            else:
                assert t.depends_on == [f"T{i-1:02d}"]

    def test_tasknum_smaller_merges_tail(self):
        d = decompose_problem("综合评价问题", tasknum=3, problem_type="evaluation")
        assert d.tasknum == 3
        assert d.tasks[-1].title == "综合分析与结论"

    def test_tasknum_larger_appends_tail(self):
        d = decompose_problem("综合评价问题", tasknum=8, problem_type="evaluation")
        assert d.tasknum == 8
        titles = [t.title for t in d.tasks]
        assert any("可视化" in t or "论文撰写" in t for t in titles)

    def test_to_dag_graph_no_self_loop(self):
        d = decompose_problem("预测问题", tasknum=5, problem_type="prediction")
        g = d.to_dag_graph()
        for node, deps in g.items():
            assert node not in deps, "依赖图不应含自环"

    def test_dag_topo_order_matches_linear(self):
        d = decompose_problem("优化问题", tasknum=4, problem_type="optimization")
        order = compute_dag_order(d.to_dag_graph())
        assert order == [f"T{i:02d}" for i in range(4)]

    def test_phase_mapping_present(self):
        d = decompose_problem("对客户分群", problem_type="classification")
        phases = {t.phase for t in d.tasks}
        assert "modeling" in phases and "solve" in phases
