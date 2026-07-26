# 依赖 DAG 编排（MM-Agent 移植，离线优先）
#
# 对应 MM-Agent 的 Coordinator.compute_dag_order / analyze_dependencies：
#   - 拓扑排序确定建模步骤的执行顺序；
#   - 解析失败（含环、悬挂依赖）回退为线性链；
#   - 节点间经共享 memory 传递中间产物。
#
# 纯自研、MIT，仅依赖标准库。

from collections import deque
from typing import Any, Callable, Dict, List, Optional


class DAGCycleError(Exception):
    """依赖图存在环时抛出。"""


def compute_dag_order(graph: Dict[str, List[str]]) -> List[str]:
    """对依赖图做拓扑排序，返回执行顺序。

    graph 语义：{node: [该 node 依赖的前置节点...]}。
    使用 Kahn 算法；若检测到环，抛 DAGCycleError（调用方应回退线性链）。
    """
    nodes = set(graph.keys())
    # 收集所有出现过的节点（含仅作为依赖出现的）
    for deps in graph.values():
        nodes.update(deps)

    indeg = {n: 0 for n in nodes}
    adj: Dict[str, List[str]] = {n: [] for n in nodes}
    for node, deps in graph.items():
        for d in deps:
            if d not in nodes:
                # 悬挂依赖：忽略并忽略该边（不阻断整体解析）
                continue
            adj[d].append(node)
            indeg[node] += 1

    queue = deque(sorted([n for n in nodes if indeg[n] == 0]))
    order: List[str] = []
    while queue:
        n = queue.popleft()
        order.append(n)
        for m in adj[n]:
            indeg[m] -= 1
            if indeg[m] == 0:
                queue.append(m)

    if len(order) != len(nodes):
        raise DAGCycleError("依赖图存在环，无法拓扑排序")
    return order


def linear_fallback(n: int) -> Dict[str, List[str]]:
    """线性链回退：构建 {str(i): [str(j) for j in range(1, i)]}（i 从 1 到 n）。

    与 MM-Agent 的 analyze_dependencies 失败回退一致：每个步骤仅依赖其前一序号步骤。
    """
    n = max(1, int(n))
    return {str(i): [str(j) for j in range(1, i)] for i in range(1, n + 1)}


def parse_dependencies(spec: List[Dict[str, Any]]) -> Dict[str, List[str]]:
    """从步骤清单解析依赖图。

    spec 每项形如 {"name": str, "depends_on": List[str]（可选）}。
    返回 {name: [deps...]}；若 spec 为空或非法，返回线性链回退。
    """
    if not spec:
        return {}
    graph: Dict[str, List[str]] = {}
    valid = True
    for step in spec:
        if not isinstance(step, dict) or "name" not in step:
            valid = False
            break
        name = str(step["name"])
        deps = step.get("depends_on") or []
        if not isinstance(deps, list):
            deps = [deps]
        graph[name] = [str(d) for d in deps]
    if not valid:
        # 无法解析：退化为与 spec 等长的线性链（用原始 name 列表若出现部分有效则尽量保留）
        names = [str(s.get("name", i + 1)) for i, s in enumerate(spec)]
        return {names[i]: names[:i] for i in range(len(names))}
    return graph


# ─────────────────────────────────────────────────────────────
# 执行器
# ─────────────────────────────────────────────────────────────
NodeFn = Callable[[Dict[str, Any]], Optional[Dict[str, Any]]]


class DAGExecutor:
    """按依赖序执行节点，经共享 memory 传递中间产物。

    设计要点：
      - 节点函数签名 fn(memory: Dict) -> Optional[Dict]，返回的 dict 会并入 memory；
      - 单节点抛异常时记录错误、标记失败，不中断整链（保证“可控、离线可跑”）；
      - 解析失败（环）自动回退线性链；允许显式指定 fallback 顺序。
    """

    def __init__(self, graph: Optional[Dict[str, List[str]]] = None,
                 memory: Optional[Dict[str, Any]] = None):
        self.graph = graph or {}
        self.memory: Dict[str, Any] = memory or {}
        self._nodes: Dict[str, NodeFn] = {}
        self._results: Dict[str, Dict[str, Any]] = {}

    def add_node(self, name: str, func: NodeFn, depends_on: Optional[List[str]] = None) -> "DAGExecutor":
        """注册一个节点函数，可选显式声明依赖（会并入 graph）。返回 self 便于链式。"""
        self._nodes[name] = func
        if depends_on is not None:
            self.graph[name] = list(depends_on)
        return self

    def order(self, fallback_linear: bool = True) -> List[str]:
        """计算执行顺序；含环且允许回退时返回线性链（按注册顺序）。"""
        try:
            return compute_dag_order(self.graph)
        except DAGCycleError:
            if fallback_linear:
                names = list(self._nodes.keys())
                return names  # 线性顺序（与注册顺序一致）
            raise

    def run(self, fallback_linear: bool = True) -> Dict[str, Dict[str, Any]]:
        """执行全部节点，返回 {node: {status, output, error}}。"""
        order = self.order(fallback_linear=fallback_linear)
        for name in order:
            fn = self._nodes.get(name)
            if fn is None:
                self._results[name] = {"status": "skipped", "output": None,
                                       "error": "未注册的节点"}
                continue
            try:
                out = fn(self.memory)
                if isinstance(out, dict):
                    self.memory.update(out)
                self._results[name] = {
                    "status": "success",
                    "output": out,
                    "error": None,
                    "produced_keys": list(out.keys()) if isinstance(out, dict) else [],
                }
            except Exception as e:  # 单节点失败不阻断整链
                self._results[name] = {
                    "status": "failed",
                    "output": None,
                    "error": str(e),
                    "produced_keys": [],
                }
        return self._results

    def get_memory(self) -> Dict[str, Any]:
        return self.memory

    def get_result(self, name: str) -> Dict[str, Any]:
        return self._results.get(name, {})


# ─────────────────────────────────────────────────────────────
# 便捷入口
# ─────────────────────────────────────────────────────────────
def run_dag(graph: Dict[str, List[str]], nodes: Dict[str, NodeFn],
            memory: Optional[Dict[str, Any]] = None) -> Dict[str, Dict[str, Any]]:
    """给定依赖图与节点函数表，直接执行并返回结果。"""
    ex = DAGExecutor(graph=graph, memory=memory)
    for name, fn in nodes.items():
        ex.add_node(name, fn)
    return ex.run()


__all__ = [
    "DAGCycleError",
    "compute_dag_order",
    "linear_fallback",
    "parse_dependencies",
    "DAGExecutor",
    "run_dag",
]
