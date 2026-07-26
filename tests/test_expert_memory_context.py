# 测试：层7 任务间记忆上下文（build_dependency_context + DAGExecutor.context_for）
from modules.orchestration import (
    build_dependency_context,
    DAGExecutor,
    run_dag,
)


class TestDependencyContext:
    def test_build_context_from_memory(self):
        mem = {
            "T00": {"data": "清洗后指标"},
            "T01": {"note": "构建指标树"},
        }
        ctx = build_dependency_context(mem, ["T00", "T01"])
        assert "T00" in ctx and "T01" in ctx
        assert "清洗后指标" in ctx

    def test_build_context_empty_when_no_upstream(self):
        assert build_dependency_context({}, []) == ""

    def test_executor_context_for_downstream(self):
        # 线性链：T00 -> T01 -> T02，每个节点把自己的产物存入 memory（按节点名）
        def mk(name):
            def node(memory):
                memory[name] = {"payload": f"result-of-{name}"}
                return {name: memory[name]}
            return node

        ex = DAGExecutor(graph={"T00": [], "T01": ["T00"], "T02": ["T01"]})
        ex.add_node("T00", mk("T00"))
        ex.add_node("T01", mk("T01"))
        ex.add_node("T02", mk("T02"))
        results = ex.run()
        assert all(r["status"] == "success" for r in results.values())
        # 下游节点应能看到上游上下文
        ctx_t01 = ex.context_for("T01")
        ctx_t02 = ex.context_for("T02")
        assert "T00" in ctx_t01
        assert "T00" in ctx_t02 and "T01" in ctx_t02

    def test_run_dag_single_failure_does_not_block_chain(self):
        def ok(memory):
            return {"ok": 1}

        def bad(memory):
            raise ValueError("boom")

        results = run_dag(
            {"A": [], "B": ["A"], "C": ["B"]},
            {"A": ok, "B": bad, "C": ok},
        )
        assert results["A"]["status"] == "success"
        assert results["B"]["status"] == "failed"
        assert results["C"]["status"] == "success"  # 单节点失败不阻断
