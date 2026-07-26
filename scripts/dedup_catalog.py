"""
去重 model_catalog.json 中的重复模型 ID，并添加 implemented 字段。

实现映射（基于 model_factory.py 的 MODEL_CATEGORY_MAP）：
- regression: linear_regression, ridge, lasso, polynomial_regression,
              random_forest_regressor, svr, xgboost_regressor(降级 RF)
- classification: logistic_regression, svm, random_forest_classifier,
                  knn, decision_tree
- clustering: kmeans, dbscan
- dimension_reduction: pca, factor_analysis
- evaluation: ahp, entropy_weight, topsis, comprehensive_evaluation
- optimization: linear_programming, integer_programming, nonlinear_programming
- time_series: arima, linear_trend
"""
import json
from pathlib import Path

CATALOG_PATH = Path(__file__).parent.parent / "config" / "model_catalog.json"

# 已实现模型 ID 清单（与 model_factory.py 对应 + catalog 别名）
# 严格按 factory 实际方法核对：EvaluationSolver.{ahp,entropy_weight,topsis,comprehensive_evaluation}
# OptimizationSolver.{linear_programming,integer_programming}
# TimeSeriesSolver.{arima, _linear_trend}
# build_supervised.{ridge,lasso,polynomial_regression,random_forest,svr,xgboost_regressor(降级RF),
#                   logistic_regression,svm,knn,decision_tree,kmeans,dbscan,pca,factor_analysis}
IMPLEMENTED_IDS = {
    # 回归（factory IDs）
    "linear_regression", "ridge", "lasso", "polynomial_regression",
    "random_forest_regressor", "svr", "xgboost_regressor",
    # catalog 中的别名
    "regression",  # catalog 用 regression 表示线性回归
    # 分类
    "logistic_regression", "svm",
    "random_forest_classifier",
    "knn", "decision_tree",
    "random_forest",  # catalog 中的 random_forest 已实现（按 y 类型自动判定回归/分类）
    # 聚类
    "kmeans", "dbscan", "cluster_analysis",  # catalog 用 cluster_analysis
    # 降维
    "pca", "factor_analysis",
    # 评价
    "ahp", "entropy_weight", "topsis", "comprehensive_evaluation",
    # 优化
    "linear_programming", "integer_programming",
    # 时序
    "arima", "linear_trend", "time_series_arima",
}

# 灰色关联与灰色预测是不同概念，统一拼写
SPELLING_NORMALIZE = {
    "gray_relational": "grey_relational",  # 统一为 grey_ 前缀
}


def main():
    data = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))

    seen_ids = set()
    removed = []
    stats = {"before": 0, "after": 0, "implemented": 0, "not_implemented": 0}

    for cat_name, cat_info in data["models"].items():
        unique_models = []
        for model in cat_info["models"]:
            stats["before"] += 1
            mid = model["id"]

            # 拼写归一化
            mid_normalized = SPELLING_NORMALIZE.get(mid, mid)
            if mid != mid_normalized:
                model["id"] = mid_normalized
                mid = mid_normalized

            # 去重：已见过的 ID 直接跳过
            if mid in seen_ids:
                removed.append((cat_name, mid))
                continue
            seen_ids.add(mid)

            # 添加 implemented 字段
            implemented = mid in IMPLEMENTED_IDS
            model["implemented"] = implemented
            if implemented:
                stats["implemented"] += 1
                # 已实现模型无需 implementation_note
                model.pop("implementation_note", None)
            else:
                stats["not_implemented"] += 1
                # 未实现模型添加说明
                if "implementation_note" not in model:
                    model["implementation_note"] = "尚未在 model_factory.py 中实现"

            unique_models.append(model)
            stats["after"] += 1

        cat_info["models"] = unique_models

    # 写回
    CATALOG_PATH.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )

    print(f"=== 去重与标记完成 ===")
    print(f"原始模型数: {stats['before']}")
    print(f"去重后模型数: {stats['after']}")
    print(f"已实现: {stats['implemented']}")
    print(f"未实现: {stats['not_implemented']}")
    print(f"移除重复: {len(removed)} 个")
    for cat, mid in removed:
        print(f"  - {cat}: {mid}")


if __name__ == "__main__":
    main()
