"""
性能基准测试：建立模型训练/推理的性能基线
测量各模型的训练时间、预测时间、内存使用
"""
import time
import json
import tracemalloc
from pathlib import Path
from typing import Dict, List, Any
import numpy as np
import pandas as pd


class PerformanceBenchmark:
    """性能基准测试器"""
    
    def __init__(self, output_dir: Path = None):
        self.output_dir = output_dir or Path("benchmarks/results")
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.results: List[Dict] = []
    
    def _measure(self, func, *args, **kwargs):
        """测量函数执行时间和内存"""
        tracemalloc.start()
        start_time = time.perf_counter()
        result = func(*args, **kwargs)
        elapsed = time.perf_counter() - start_time
        current, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        return {
            "result": result,
            "elapsed_seconds": round(elapsed, 4),
            "memory_peak_mb": round(peak / 1024 / 1024, 2),
        }
    
    def benchmark_regression_models(self, n_samples=500, n_features=10):
        """基准测试回归模型"""
        np.random.seed(42)
        X = np.random.randn(n_samples, n_features)
        y = 2 * X[:, 0] + 3 * X[:, 1] + np.random.randn(n_samples) * 0.5
        
        models = {
            "linear_regression": self._bench_linear_regression,
            "ridge": self._bench_ridge,
            "lasso": self._bench_lasso,
            "random_forest": self._bench_random_forest,
            "svr": self._bench_svr,
        }
        
        results = []
        for name, func in models.items():
            metrics = func(X, y)
            metrics["model"] = name
            metrics["category"] = "regression"
            metrics["n_samples"] = n_samples
            metrics["n_features"] = n_features
            results.append(metrics)
            print(f"  {name}: {metrics['train_time']:.4f}s train, "
                  f"{metrics['predict_time']:.6f}s predict, "
                  f"{metrics['memory_mb']:.2f}MB")
        
        return results
    
    def _bench_linear_regression(self, X, y):
        from sklearn.linear_model import LinearRegression
        train = self._measure(LinearRegression().fit, X, y)
        predict = self._measure(train["result"].predict, X)
        return {
            "train_time": train["elapsed_seconds"],
            "predict_time": predict["elapsed_seconds"],
            "memory_mb": train["memory_peak_mb"],
            "r2_score": train["result"].score(X, y),
        }
    
    def _bench_ridge(self, X, y):
        from sklearn.linear_model import Ridge
        train = self._measure(Ridge(alpha=1.0).fit, X, y)
        predict = self._measure(train["result"].predict, X)
        return {
            "train_time": train["elapsed_seconds"],
            "predict_time": predict["elapsed_seconds"],
            "memory_mb": train["memory_peak_mb"],
            "r2_score": train["result"].score(X, y),
        }
    
    def _bench_lasso(self, X, y):
        from sklearn.linear_model import Lasso
        train = self._measure(Lasso(alpha=0.1).fit, X, y)
        predict = self._measure(train["result"].predict, X)
        return {
            "train_time": train["elapsed_seconds"],
            "predict_time": predict["elapsed_seconds"],
            "memory_mb": train["memory_peak_mb"],
            "r2_score": train["result"].score(X, y),
        }
    
    def _bench_random_forest(self, X, y):
        from sklearn.ensemble import RandomForestRegressor
        train = self._measure(
            RandomForestRegressor(n_estimators=50, random_state=42).fit, X, y
        )
        predict = self._measure(train["result"].predict, X)
        return {
            "train_time": train["elapsed_seconds"],
            "predict_time": predict["elapsed_seconds"],
            "memory_mb": train["memory_peak_mb"],
            "r2_score": train["result"].score(X, y),
        }
    
    def _bench_svr(self, X, y):
        from sklearn.svm import SVR
        train = self._measure(SVR(kernel='rbf').fit, X[:200], y[:200])  # 限制样本量
        predict = self._measure(train["result"].predict, X[:200])
        return {
            "train_time": train["elapsed_seconds"],
            "predict_time": predict["elapsed_seconds"],
            "memory_mb": train["memory_peak_mb"],
            "r2_score": train["result"].score(X[:200], y[:200]),
        }
    
    def benchmark_classification_models(self, n_samples=500, n_features=10):
        """基准测试分类模型"""
        from sklearn.datasets import make_classification
        X, y = make_classification(n_samples=n_samples, n_features=n_features,
                                    n_informative=5, random_state=42)
        
        results = []
        
        # Logistic Regression
        from sklearn.linear_model import LogisticRegression
        train = self._measure(LogisticRegression(max_iter=1000).fit, X, y)
        predict = self._measure(train["result"].predict, X)
        results.append({
            "model": "logistic_regression", "category": "classification",
            "train_time": train["elapsed_seconds"], "predict_time": predict["elapsed_seconds"],
            "memory_mb": train["memory_peak_mb"], "accuracy": train["result"].score(X, y),
            "n_samples": n_samples, "n_features": n_features,
        })
        
        # SVM
        from sklearn.svm import SVC
        train = self._measure(SVC(kernel='rbf').fit, X[:200], y[:200])
        predict = self._measure(train["result"].predict, X[:200])
        results.append({
            "model": "svm", "category": "classification",
            "train_time": train["elapsed_seconds"], "predict_time": predict["elapsed_seconds"],
            "memory_mb": train["memory_peak_mb"], "accuracy": train["result"].score(X[:200], y[:200]),
            "n_samples": 200, "n_features": n_features,
        })
        
        # Random Forest
        from sklearn.ensemble import RandomForestClassifier
        train = self._measure(
            RandomForestClassifier(n_estimators=50, random_state=42).fit, X, y
        )
        predict = self._measure(train["result"].predict, X)
        results.append({
            "model": "random_forest_classifier", "category": "classification",
            "train_time": train["elapsed_seconds"], "predict_time": predict["elapsed_seconds"],
            "memory_mb": train["memory_peak_mb"], "accuracy": train["result"].score(X, y),
            "n_samples": n_samples, "n_features": n_features,
        })
        
        # KNN
        from sklearn.neighbors import KNeighborsClassifier
        train = self._measure(KNeighborsClassifier(n_neighbors=5).fit, X, y)
        predict = self._measure(train["result"].predict, X)
        results.append({
            "model": "knn", "category": "classification",
            "train_time": train["elapsed_seconds"], "predict_time": predict["elapsed_seconds"],
            "memory_mb": train["memory_peak_mb"], "accuracy": train["result"].score(X, y),
            "n_samples": n_samples, "n_features": n_features,
        })
        
        for r in results:
            print(f"  {r['model']}: {r['train_time']:.4f}s train, "
                  f"{r['predict_time']:.6f}s predict, {r['memory_mb']:.2f}MB")
        
        return results
    
    def benchmark_clustering_models(self, n_samples=500, n_features=5):
        """基准测试聚类模型"""
        np.random.seed(42)
        X = np.random.randn(n_samples, n_features)
        
        results = []
        
        # KMeans
        from sklearn.cluster import KMeans
        train = self._measure(KMeans(n_clusters=3, n_init=10, random_state=42).fit, X)
        predict = self._measure(train["result"].predict, X)
        results.append({
            "model": "kmeans", "category": "clustering",
            "train_time": train["elapsed_seconds"], "predict_time": predict["elapsed_seconds"],
            "memory_mb": train["memory_peak_mb"], "n_clusters": 3,
            "n_samples": n_samples, "n_features": n_features,
        })
        
        # DBSCAN
        from sklearn.cluster import DBSCAN
        train = self._measure(DBSCAN(eps=0.5, min_samples=5).fit, X)
        results.append({
            "model": "dbscan", "category": "clustering",
            "train_time": train["elapsed_seconds"], "predict_time": 0,
            "memory_mb": train["memory_peak_mb"],
            "n_clusters": len(set(train["result"].labels_)) - (1 if -1 in train["result"].labels_ else 0),
            "n_samples": n_samples, "n_features": n_features,
        })
        
        for r in results:
            print(f"  {r['model']}: {r['train_time']:.4f}s train, "
                  f"{r.get('predict_time', 0):.6f}s predict, {r['memory_mb']:.2f}MB")
        
        return results
    
    def benchmark_evaluation_models(self, n_alternatives=10, n_criteria=5):
        """基准测试评价模型"""
        np.random.seed(42)
        decision_matrix = np.random.rand(n_alternatives, n_criteria) * 10
        
        results = []
        
        # TOPSIS
        from modules.model_factory import EvaluationSolver
        topsis = self._measure(EvaluationSolver.topsis, decision_matrix)
        results.append({
            "model": "topsis", "category": "evaluation",
            "train_time": topsis["elapsed_seconds"], "predict_time": 0,
            "memory_mb": topsis["memory_peak_mb"],
            "n_alternatives": n_alternatives, "n_criteria": n_criteria,
        })
        
        # 熵权法
        entropy = self._measure(EvaluationSolver.entropy_weight, decision_matrix)
        results.append({
            "model": "entropy_weight", "category": "evaluation",
            "train_time": entropy["elapsed_seconds"], "predict_time": 0,
            "memory_mb": entropy["memory_peak_mb"],
            "n_alternatives": n_alternatives, "n_criteria": n_criteria,
        })
        
        # 灰色关联
        grey = self._measure(EvaluationSolver.grey_relational, decision_matrix)
        results.append({
            "model": "grey_relational", "category": "evaluation",
            "train_time": grey["elapsed_seconds"], "predict_time": 0,
            "memory_mb": grey["memory_peak_mb"],
            "n_alternatives": n_alternatives, "n_criteria": n_criteria,
        })
        
        for r in results:
            print(f"  {r['model']}: {r['train_time']:.4f}s, {r['memory_mb']:.2f}MB")
        
        return results
    
    def benchmark_optimization_models(self):
        """基准测试优化模型"""
        from modules.model_factory import OptimizationSolver, MetaHeuristicSolver
        
        c = np.array([-3.0, -5.0])
        A_ub = np.array([[1.0, 0.0], [0.0, 2.0], [1.0, 1.0]])
        b_ub = np.array([4.0, 12.0, 8.0])
        bounds = [(0, None), (0, None)]
        
        results = []
        
        # 线性规划
        lp = self._measure(
            OptimizationSolver.linear_programming, c, A_ub=A_ub, b_ub=b_ub, bounds=bounds
        )
        results.append({
            "model": "linear_programming", "category": "optimization",
            "train_time": lp["elapsed_seconds"], "predict_time": 0,
            "memory_mb": lp["memory_peak_mb"],
        })
        
        # 模拟退火
        def objective(x):
            return sum(x**2)
        sa = self._measure(
            OptimizationSolver.simulated_annealing,
            objective, np.array([0.0, 0.0, 0.0]),
            bounds=[(-5, 5)] * 3, max_iter=100,
            initial_temp=100, cooling_rate=0.95
        )
        results.append({
            "model": "simulated_annealing", "category": "optimization",
            "train_time": sa["elapsed_seconds"], "predict_time": 0,
            "memory_mb": sa["memory_peak_mb"],
        })
        
        # PSO
        pso = self._measure(
            MetaHeuristicSolver.pso,
            objective, dim=3, bounds=[(-5, 5)] * 3,
            n_particles=20, max_iter=50
        )
        results.append({
            "model": "pso", "category": "optimization_meta",
            "train_time": pso["elapsed_seconds"], "predict_time": 0,
            "memory_mb": pso["memory_peak_mb"],
        })
        
        for r in results:
            print(f"  {r['model']}: {r['train_time']:.4f}s, {r['memory_mb']:.2f}MB")
        
        return results
    
    def benchmark_time_series(self, n_points=100):
        """基准测试时间序列模型"""
        np.random.seed(42)
        data = np.cumsum(np.random.randn(n_points)) + 10
        
        results = []
        
        # ARIMA（如果 statsmodels 可用）
        try:
            from modules.model_factory import TimeSeriesSolver
            arima = self._measure(
                TimeSeriesSolver.arima, data, order=(1, 1, 1), forecast_steps=5
            )
            results.append({
                "model": "arima", "category": "time_series",
                "train_time": arima["elapsed_seconds"], "predict_time": 0,
                "memory_mb": arima["memory_peak_mb"],
                "n_points": n_points,
            })
        except Exception as e:
            print(f"  arima 跳过: {e}")
        
        # 指数平滑
        try:
            from modules.model_factory import StatisticsSolver
            es = self._measure(
                StatisticsSolver.exponential_smoothing, data
            )
            results.append({
                "model": "exponential_smoothing", "category": "statistics",
                "train_time": es["elapsed_seconds"], "predict_time": 0,
                "memory_mb": es["memory_peak_mb"],
                "n_points": n_points,
            })
        except Exception as e:
            print(f"  exponential_smoothing 跳过: {e}")
        
        # 灰色预测
        from modules.model_factory import PredictionSolver
        grey = self._measure(
            PredictionSolver.grey_prediction, data
        )
        results.append({
            "model": "grey_prediction", "category": "prediction",
            "train_time": grey["elapsed_seconds"], "predict_time": 0,
            "memory_mb": grey["memory_peak_mb"],
            "n_points": n_points,
        })
        
        for r in results:
            print(f"  {r['model']}: {r['train_time']:.4f}s, {r['memory_mb']:.2f}MB")
        
        return results
    
    def benchmark_dimension_reduction(self, n_samples=500, n_features=20):
        """基准测试降维模型"""
        np.random.seed(42)
        X = np.random.randn(n_samples, n_features)
        
        results = []
        
        # PCA
        from sklearn.decomposition import PCA
        train = self._measure(PCA(n_components=3).fit, X)
        predict = self._measure(train["result"].transform, X)
        results.append({
            "model": "pca", "category": "dimension_reduction",
            "train_time": train["elapsed_seconds"], "predict_time": predict["elapsed_seconds"],
            "memory_mb": train["memory_peak_mb"],
            "n_samples": n_samples, "n_features": n_features, "n_components": 3,
        })
        
        print(f"  pca: {results[0]['train_time']:.4f}s train, "
              f"{results[0]['predict_time']:.6f}s predict, "
              f"{results[0]['memory_mb']:.2f}MB")
        
        return results
    
    def run_all_benchmarks(self) -> Dict:
        """运行所有基准测试"""
        print("=" * 60)
        print("性能基准测试开始")
        print("=" * 60)
        
        all_results = []
        
        print("\n[1/7] 回归模型 (500 samples × 10 features)")
        all_results.extend(self.benchmark_regression_models())
        
        print("\n[2/7] 分类模型 (500 samples × 10 features)")
        all_results.extend(self.benchmark_classification_models())
        
        print("\n[3/7] 聚类模型 (500 samples × 5 features)")
        all_results.extend(self.benchmark_clustering_models())
        
        print("\n[4/7] 评价模型 (10 alternatives × 5 criteria)")
        all_results.extend(self.benchmark_evaluation_models())
        
        print("\n[5/7] 优化模型")
        all_results.extend(self.benchmark_optimization_models())
        
        print("\n[6/7] 时间序列模型 (100 points)")
        all_results.extend(self.benchmark_time_series())
        
        print("\n[7/7] 降维模型 (500 samples × 20 features)")
        all_results.extend(self.benchmark_dimension_reduction())
        
        print("\n" + "=" * 60)
        print(f"基准测试完成：共 {len(all_results)} 个模型")
        print("=" * 60)
        
        # 保存结果
        report = {
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "total_models": len(all_results),
            "results": all_results,
        }
        
        output_file = self.output_dir / "performance_baseline.json"
        output_file.write_text(
            json.dumps(report, ensure_ascii=False, indent=2, default=str),
            encoding="utf-8"
        )
        print(f"\n结果已保存到: {output_file}")
        
        return report


def main():
    """运行性能基准测试"""
    import sys
    sys.path.insert(0, str(Path(__file__).parent.parent))
    
    benchmark = PerformanceBenchmark()
    report = benchmark.run_all_benchmarks()
    
    # 打印汇总表
    print("\n" + "=" * 60)
    print("性能基线汇总")
    print("=" * 60)
    print(f"{'模型':<30} {'类别':<20} {'训练(s)':<10} {'预测(s)':<10} {'内存(MB)':<10}")
    print("-" * 80)
    for r in report["results"]:
        print(f"{r['model']:<30} {r['category']:<20} "
              f"{r['train_time']:<10.4f} {r.get('predict_time', 0):<10.6f} "
              f"{r['memory_mb']:<10.2f}")


if __name__ == "__main__":
    main()
