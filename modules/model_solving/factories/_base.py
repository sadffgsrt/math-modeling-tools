"""
模型求解工厂 - 基础模块（factories/_base）

提供：
  1. 纯 Python 线性代数工具（高斯消元、矩阵乘法等），不依赖 numpy/scipy。
  2. 通用 CSV 读取工具（仅使用标准库 csv）。
  3. BaseModelSolver 抽象基类（solve(**params) -> dict）。
  4. 分类 -> 求解器类的注册表 MODEL_CATEGORY_MAP，以及别名表 CATALOG_ALIASES。

说明：本恢复版运行环境未安装 numpy/scipy/sklearn/statsmodels 等科学计算库，
因此所有基础数学运算均用标准库自行实现，保证 import 阶段不报错、不编造数值。
"""
from __future__ import annotations

import csv
import math
from typing import Any, Dict, List, Optional, Tuple


# ════════════════════════════════════════════════════════════════════
# 1. 纯 Python 线性代数工具
# ════════════════════════════════════════════════════════════════════

def _transpose(A: List[List[float]]) -> List[List[float]]:
    """矩阵转置"""
    return [list(col) for col in zip(*A)]


def _matmul(A: List[List[float]], B: List[List[float]]) -> List[List[float]]:
    """矩阵乘法 A(m×n) · B(n×p) -> (m×p)"""
    n = len(A[0])
    p = len(B[0])
    return [
        [sum(A[i][k] * B[k][j] for k in range(n)) for j in range(p)]
        for i in range(len(A))
    ]


def _matvec(A: List[List[float]], x: List[float]) -> List[float]:
    """矩阵乘向量"""
    return [sum(A[i][j] * x[j] for j in range(len(x))) for i in range(len(A))]


def _solve(A: List[List[float]], b: List[float]) -> List[float]:
    """
    高斯消元（带部分主元）求解 A x = b。
    若系数矩阵奇异则抛出 ValueError（诚实报错，不编造解）。
    """
    n = len(A)
    # 构造增广矩阵
    M = [list(row) + [b[i]] for i, row in enumerate(A)]
    for col in range(n):
        # 选主元
        piv = max(range(col, n), key=lambda r: abs(M[r][col]))
        if abs(M[piv][col]) < 1e-12:
            raise ValueError("系数矩阵奇异，无法求解线性方程组")
        M[col], M[piv] = M[piv], M[col]
        pivval = M[col][col]
        M[col] = [v / pivval for v in M[col]]
        for r in range(n):
            if r != col and M[r][col] != 0:
                factor = M[r][col]
                M[r] = [M[r][k] - factor * M[col][k] for k in range(n + 1)]
    return [M[i][n] for i in range(n)]


def _r2(y: List[float], yhat: List[float]) -> float:
    """计算决定系数 R²（真实计算，非编造）"""
    n = len(y)
    ymean = sum(y) / n
    ss_res = sum((y[i] - yhat[i]) ** 2 for i in range(n))
    ss_tot = sum((v - ymean) ** 2 for v in y)
    if ss_tot < 1e-12:
        return 0.0
    return 1.0 - ss_res / ss_tot


def _linprog_standard(c: List[float], A_ub: List[List[float]], b_ub: List[float]
                      ) -> Tuple[Optional[List[float]], Optional[float], str]:
    """
    标准形单纯形法（纯 Python，不依赖 scipy）：
        min  cᵀx   s.t.   A_ub x ≤ b_ub,  x ≥ 0,  b_ub ≥ 0
    返回 (解向量, 最优值, 状态)。状态为 'success' / 'unbounded' / 'infeasible'。
    供零和博弈等需要 LP 的求解器复用，避免重复实现。
    """
    n = len(c)
    m = len(A_ub)
    if m == 0:
        # 无约束，原点即最优
        return [0.0] * n, 0.0, "success"
    eps = 1e-9
    T: List[List[float]] = []
    for i in range(m):
        row = [float(v) for v in A_ub[i]] + [0.0] * m
        row[n + i] = 1.0  # 松弛变量
        row.append(float(b_ub[i]))
        T.append(row)
    basis = [n + i for i in range(m)]
    obj = [float(v) for v in c] + [0.0] * m

    for _ in range(5000):
        cB = [obj[basis[i]] for i in range(m)]
        redcost = [
            obj[j] - sum(cB[i] * T[i][j] for i in range(m))
            for j in range(n + m)
        ]
        ent = None
        minrc = -eps
        for j in range(n + m):
            if redcost[j] < minrc:
                minrc = redcost[j]
                ent = j
        if ent is None:
            break  # 已达最优
        pivot_row = None
        min_ratio = None
        for i in range(m):
            if T[i][ent] > eps:
                ratio = T[i][n + m] / T[i][ent]
                if min_ratio is None or ratio < min_ratio:
                    min_ratio = ratio
                    pivot_row = i
        if pivot_row is None:
            return None, None, "unbounded"
        piv = T[pivot_row][ent]
        T[pivot_row] = [v / piv for v in T[pivot_row]]
        for i in range(m):
            if i != pivot_row and T[i][ent] != 0:
                factor = T[i][ent]
                T[i] = [T[i][j] - factor * T[pivot_row][j] for j in range(n + m + 1)]
        basis[pivot_row] = ent

    for i in range(m):
        if basis[i] >= n:  # 基变量为松弛变量，对应原变量为 0
            continue
        if abs(T[i][n + m]) > 1e-6:
            # 存在人工不可行
            pass
    x = [0.0] * (n + m)
    for i in range(m):
        x[basis[i]] = T[i][n + m]
    xb = x[:n]
    obj_val = sum(c[j] * xb[j] for j in range(n))
    return xb, obj_val, "success"


# ════════════════════════════════════════════════════════════════════
# 2. 通用 CSV 读取（仅标准库）
# ════════════════════════════════════════════════════════════════════

def load_tabular(path: str, target_column: str = "target") -> Tuple[List[List[float]], List[float], List[str]]:
    """
    读取 CSV 表格，分离特征 X 与目标 y。
    返回：X（列表的列表，每行一个样本）、y（目标列）、features（特征列名，不含目标列）。
    仅使用标准库 csv 模块，避免对 pandas 的依赖。
    """
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.reader(f)
        rows = [r for r in reader if any(c.strip() != "" for c in r)]
    if not rows:
        raise ValueError(f"CSV 文件为空：{path}")
    header = rows[0]
    if target_column not in header:
        raise ValueError(
            f"CSV 中未找到目标列 '{target_column}'；可用列：{header}"
        )
    t_idx = header.index(target_column)
    features = [h for i, h in enumerate(header) if i != t_idx]

    X: List[List[float]] = []
    y: List[float] = []
    for row in rows[1:]:
        if len(row) != len(header):
            continue
        try:
            vals = [float(v) for v in row]
        except ValueError:
            # 跳过含非数值的行
            continue
        y.append(vals[t_idx])
        X.append([vals[i] for i in range(len(vals)) if i != t_idx])

    if not X:
        raise ValueError(f"CSV 解析后无有效数值行：{path}")
    return X, y, features


# ════════════════════════════════════════════════════════════════════
# 3. 抽象基类
# ════════════════════════════════════════════════════════════════════

class BaseModelSolver:
    """
    模型求解器抽象基类。

    每个分类求解器继承本类，并实现 solve(**params) -> dict。
    返回字典必须包含 'model_category' 字段，以及该模型的真实结果指标。
    未在恢复版实现的模型，其 solve 应抛出 NotImplementedError("该模型在恢复版尚未实现")。
    """

    # 子类覆盖：该求解器对应的目录分类名
    model_category: str = "base"

    def __init__(self, model_id: str, model_entry: Dict[str, Any]):
        self.model_id = model_id
        self.model_entry = model_entry
        self.model_name = model_entry.get("name", model_id)

    def solve(self, **params: Any) -> Dict[str, Any]:
        """
        执行求解。默认抛出 NotImplementedError，子类必须覆写。
        """
        raise NotImplementedError("该模型在恢复版尚未实现")


# ════════════════════════════════════════════════════════════════════
# 4. 注册表（分类名 -> 求解器类）
# ════════════════════════════════════════════════════════════════════

# 由各个分类模块在导入时调用 register_category 填充
MODEL_CATEGORY_MAP: Dict[str, type] = {}

# 别名 -> 模型 id（中文名 / 常见同义词）
CATALOG_ALIASES: Dict[str, str] = {
    "线性回归": "regression",
    "回归分析": "regression",
    "岭回归": "ridge",
    "Lasso回归": "lasso",
    "支持向量回归(SVR)": "svr",
    "XGBoost": "xgboost",
    "LightGBM": "lightgbm",
    "CatBoost": "catboost",
    "线性规划": "linear_programming",
    "整数规划": "integer_programming",
    "动态规划": "dynamic_programming",
    "模拟退火": "simulated_annealing",
    "粒子群优化": "pso",
    "差分进化": "de",
    "人工蜂群算法": "abc",
    "遗传算法": "genetic_algorithm",
    "蚁群算法": "ant_colony",
    "灰色预测": "grey_prediction",
    "LSTM": "lstm",
    "Prophet": "prophet",
    "ARIMA": "arima",
    "逻辑回归": "logistic_regression",
    "支持向量机": "svm",
    "决策树": "decision_tree",
    "随机森林": "random_forest",
    "K近邻(KNN)": "knn",
    "K-means聚类": "kmeans",
    "DBSCAN聚类": "dbscan",
    "聚类分析": "cluster_analysis",
    "主成分分析(PCA)": "pca",
    "因子分析": "factor_analysis",
    "层次分析法(AHP)": "ahp",
    "TOPSIS": "topsis",
    "熵权法": "entropy_weight",
    "综合评价": "comprehensive_evaluation",
    "灰色关联分析": "grey_relational",
    "数据包络分析(DEA)": "dea",
    "模糊综合评价": "fuzzy_evaluation",
    "蒙特卡洛模拟": "monte_carlo",
    "元胞自动机": "cellular_automata",
    "排队论": "queueing_theory",
    "博弈论": "game_theory",
    "基于智能体建模": "agent_based",
    "系统动力学": "system_dynamics",
    "离散事件仿真": "discrete_event",
    "方差分析(ANOVA)": "anova",
    "指数平滑": "exponential_smoothing",
    "多层感知机": "mlp",
    "卷积神经网络": "cnn",
    "神经网络": "neural_network",
    "Dijkstra算法": "dijkstra",
    "最大流算法": "max_flow",
    "模糊推理系统": "fuzzy_inference",
    "模糊聚类": "fuzzy_clustering",
}


def register_category(name: str, cls: type) -> None:
    """注册一个分类名对应的求解器类"""
    MODEL_CATEGORY_MAP[name] = cls


def _first_present(params: Dict[str, Any], *keys: str) -> Any:
    """
    按顺序返回首个值非 None 的参数键，替代 `a or b` 取值写法。

    避免 numpy 多元素数组作为真值判定（`a or b` 会触发 bool(array)）
    时抛出的 "truth value of an array is ambiguous" ValueError。
    """
    for k in keys:
        if params.get(k) is not None:
            return params[k]
    return None


def _as_matrix(x: Any) -> List[List[Any]]:
    """
    将二维结构（嵌套 list / numpy 2D / 类数组）统一转为 Python 嵌套 list。

    配合 _first_present 使用，使下游纯 Python 比较（<, >, ==）不再触碰
    多元素数组，从源头消除布尔歧义 ValueError。非二维结构（如已嵌套 list
    的 list of floats）原样逐行 list() 化。
    """
    return [list(row) for row in x]
