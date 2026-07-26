# 依赖 DAG 编排包（MM-Agent 移植，离线优先）
#
# 设计参考 MM-Agent 的 Coordinator.compute_dag_order + analyze_dependencies：
#   - 用依赖图 {node: [依赖的节点]} 做拓扑排序确定执行序；
#   - 解析失败（含环/缺失）时回退为线性链 {str(i): [str(j) for j in range(1,i)]}；
#   - 节点间经共享 memory / code_memory 传递中间产物。
#
# 本实现（纯自研、MIT）：
#   - compute_dag_order：Kahn 拓扑排序，含环检测与线性回退；
#   - DAGExecutor：按序执行节点函数，经共享 memory 传递产物，单节点失败不中断整链；
#   - 不依赖 MM-Agent 任何代码/提示词，仅标准库。

from .dag import (
    DAGCycleError,
    compute_dag_order,
    linear_fallback,
    parse_dependencies,
    build_dependency_context,
    DAGExecutor,
    run_dag,
)

__all__ = [
    "DAGCycleError",
    "compute_dag_order",
    "linear_fallback",
    "parse_dependencies",
    "build_dependency_context",
    "DAGExecutor",
    "run_dag",
]
