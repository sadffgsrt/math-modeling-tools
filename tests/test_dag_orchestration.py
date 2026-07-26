"""依赖 DAG 编排测试（拓扑排序 + 线性回退 + 执行器记忆传递）。"""
import sys
from pathlib import Path
from unittest import TestCase, main as unittest_main

sys.path.insert(0, str(Path(__file__).parent.parent))

from modules.orchestration import (
    compute_dag_order,
    linear_fallback,
    parse_dependencies,
    DAGExecutor,
    DAGCycleError,
)


class TestDAGOrder(TestCase):
    def test_topo_order(self):
        graph = {
            "analyze": [],
            "model": ["analyze"],
            "solve": ["model"],
            "report": ["solve"],
        }
        order = compute_dag_order(graph)
        self.assertEqual(order, ["analyze", "model", "solve", "report"])

    def test_diamond(self):
        graph = {
            "a": [],
            "b": ["a"],
            "c": ["a"],
            "d": ["b", "c"],
        }
        order = compute_dag_order(graph)
        self.assertEqual(order[0], "a")
        self.assertEqual(order[-1], "d")
        self.assertLess(order.index("b"), order.index("d"))
        self.assertLess(order.index("c"), order.index("d"))

    def test_cycle_raises(self):
        graph = {"a": ["b"], "b": ["a"]}
        with self.assertRaises(DAGCycleError):
            compute_dag_order(graph)

    def test_linear_fallback(self):
        fb = linear_fallback(3)
        self.assertEqual(fb, {"1": [], "2": ["1"], "3": ["1", "2"]})
        order = compute_dag_order(fb)
        self.assertEqual(order, ["1", "2", "3"])

    def test_parse_dependencies(self):
        spec = [
            {"name": "analyze", "depends_on": []},
            {"name": "model", "depends_on": ["analyze"]},
            {"name": "solve", "depends_on": ["model"]},
        ]
        graph = parse_dependencies(spec)
        self.assertEqual(graph["solve"], ["model"])
        order = compute_dag_order(graph)
        self.assertEqual(order, ["analyze", "model", "solve"])


class TestDAGExecutor(TestCase):
    def test_memory_passing(self):
        ex = DAGExecutor()
        ex.add_node("load", lambda mem: {"X": [1, 2, 3]})
        ex.add_node("transform", lambda mem: {"X2": [v * 2 for v in mem["X"]]},
                    depends_on=["load"])
        ex.add_node("summarize", lambda mem: {"total": sum(mem["X2"])},
                    depends_on=["transform"])
        results = ex.run()
        self.assertEqual(results["summarize"]["status"], "success")
        self.assertEqual(ex.get_memory()["total"], 12)

    def test_node_failure_isolated(self):
        ex = DAGExecutor()
        ex.add_node("good", lambda mem: {"ok": 1})
        ex.add_node("bad", lambda mem: (_ for _ in ()).throw(RuntimeError("boom")),
                    depends_on=["good"])
        ex.add_node("after", lambda mem: {"still": mem.get("ok", 0) + 1},
                    depends_on=["bad"])
        results = ex.run()
        self.assertEqual(results["good"]["status"], "success")
        self.assertEqual(results["bad"]["status"], "failed")
        # 失败节点不应阻断后续节点执行（依赖已满足）
        self.assertEqual(results["after"]["status"], "success")
        self.assertEqual(ex.get_memory().get("still"), 2)

    def test_run_dag_helper(self):
        from modules.orchestration import run_dag
        graph = {"a": [], "b": ["a"]}
        nodes = {
            "a": lambda mem: {"v": 1},
            "b": lambda mem: {"w": mem["v"] + 1},
        }
        res = run_dag(graph, nodes)
        self.assertEqual(res["b"]["output"]["w"], 2)


if __name__ == "__main__":
    unittest_main()
