# 性能基准测试（Performance Baseline）

本目录提供数学建模竞赛工作流的**模型训练 / 推理性能基线**，用于量化各模型的训练时间、预测时间与内存占用，便于后续性能对比、回归检测与瓶颈定位。

## 1. 测试环境要求

| 依赖        | 版本要求     | 用途                          |
| ----------- | ------------ | ----------------------------- |
| Python      | 3.8 及以上   | 运行环境                      |
| numpy       | 1.20+        | 数值计算 / 数据生成           |
| scipy       | 1.6+         | 优化求解（线性规划、SA、PSO） |
| scikit-learn| 1.0+         | 回归 / 分类 / 聚类 / 降维     |
| pandas      | 1.3+         | 数据结构支持                  |
| statsmodels | 0.13+（可选）| ARIMA / 指数平滑（缺失自动跳过）|

> 说明：当 `statsmodels` 未安装时，ARIMA 与指数平滑测试会自动跳过并打印提示，不影响其他模型测试。

## 2. 运行方法

在工作流根目录（`工作流/`）下执行：

```powershell
python -m benchmarks.performance_baseline
```

运行结束后会：

1. 在控制台打印每个模型的训练时间、预测时间、内存峰值；
2. 在 `benchmarks/results/performance_baseline.json` 中保存完整基线数据。

## 3. 测试覆盖的 7 大类别

| 序号 | 类别              | 中文名称   | 涵盖模型                                                     |
| ---- | ----------------- | ---------- | ------------------------------------------------------------ |
| 1    | regression        | 回归       | LinearRegression / Ridge / Lasso / RandomForest / SVR       |
| 2    | classification    | 分类       | LogisticRegression / SVM / RandomForest / KNN                |
| 3    | clustering        | 聚类       | KMeans / DBSCAN                                              |
| 4    | evaluation        | 评价       | TOPSIS / 熵权法 / 灰色关联                                   |
| 5    | optimization      | 优化       | 线性规划 / 模拟退火 / PSO（粒子群）                          |
| 6    | time_series       | 时序预测   | ARIMA / 指数平滑 / 灰色预测 GM(1,1)                          |
| 7    | dimension_reduction | 降维     | PCA                                                          |

## 4. 基线指标说明

每个模型测量以下三项核心指标：

| 指标              | 字段名            | 单位 | 含义                                                |
| ----------------- | ----------------- | ---- | --------------------------------------------------- |
| 训练时间          | `train_time`      | 秒   | 模型拟合（`fit`）所消耗的墙钟时间                   |
| 预测时间          | `predict_time`    | 秒   | 模型推理（`predict` / `transform`）所消耗的墙钟时间 |
| 内存峰值          | `memory_mb`       | MB   | 测试期间 Python 进程的内存峰值（tracemalloc 追踪）  |

> 附加指标：回归模型附带 `r2_score`；分类模型附带 `accuracy`；聚类模型附带 `n_clusters`。

## 5. 结果文件格式（JSON）

结果保存于 `benchmarks/results/performance_baseline.json`，结构如下：

```json
{
  "timestamp": "2026-07-01 12:34:56",
  "total_models": 19,
  "results": [
    {
      "model": "linear_regression",
      "category": "regression",
      "train_time": 0.0034,
      "predict_time": 0.00012,
      "memory_mb": 0.05,
      "r2_score": 0.8876,
      "n_samples": 500,
      "n_features": 10
    }
  ]
}
```

## 6. 性能等级定义

依据训练时间（`train_time`）将模型性能划分为 4 个等级：

| 等级 | 中文   | 训练时间范围 | 适用场景                                         |
| ---- | ------ | ------------ | ------------------------------------------------ |
| 快速 | Fast   | < 1 s        | 线性模型、轻量求解器，可用于实时交互            |
| 中等 | Medium | 1 s – 5 s    | 中等规模集成模型、迭代优化器                     |
| 较慢 | Slow   | 5 s – 30 s   | 大规模集成、复杂启发式优化                       |
| 慢   | Very Slow | > 30 s     | 超参搜索、深度学习；需评估是否需要优化或并行化   |

## 7. 单元测试

性能基准本身的功能正确性由 `tests/test_performance.py` 验证（**不测试实际性能数值，仅验证 API 与流程正确性**）。运行：

```powershell
python -m unittest tests.test_performance
```

> 注意：性能基准测试因运行较慢，**不纳入常规单元测试套件**，需单独运行。

## 8. 目录结构

```
工作流/
├── benchmarks/
│   ├── __init__.py
│   ├── performance_baseline.py     # 性能基准测试主程序
│   ├── PERFORMANCE_BASELINE.md     # 本文档
│   └── results/                    # 运行时自动生成
│       └── performance_baseline.json
└── tests/
    └── test_performance.py         # 功能正确性单元测试
```
