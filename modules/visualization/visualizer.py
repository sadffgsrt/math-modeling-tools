"""
结果可视化模块 (Module 05) —— 从 v3.0 蓝本 05_visualization/visualizer.py 忠实移植
功能：生成图表（预测值 vs 真实值、残差、特征重要性、数据分布、相关性热力图、
      误差分析、箱线图等），支持结果的直观展示。

移植说明：
- 保留 v3.0 的全部真实绘图逻辑（matplotlib），输出 png 到指定目录。
- 依赖采用“懒加载 + 缺失即清晰报错”策略，保证在本环境（未安装 numpy/pandas/
  matplotlib/scipy 等）下模块【可被导入】，而真正绘图时若依赖缺失则抛出明确的
  ImportError，绝不伪造/占位输出。
- scipy 用于残差 Q-Q 图，缺失时仅跳过该子图并给出说明，不影响其余图表。
"""

import json
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, asdict
from datetime import datetime
import warnings
warnings.filterwarnings('ignore')

# —— 依赖懒加载：仅占位，真正使用时再校验，保证本模块可被 import ——
try:
    import numpy as np
except ImportError:  # pragma: no cover - 依赖缺失时由运行入口显式报错
    np = None
try:
    import pandas as pd
except ImportError:  # pragma: no cover
    pd = None


@dataclass
class FigureConfig:
    """图表配置"""
    figure_id: str
    title: str
    figure_type: str  # line, bar, scatter, heatmap, box, histogram, pie, contour, 3d
    x_label: str = ""
    y_label: str = ""
    width: int = 10
    height: int = 6
    dpi: int = 300
    style: str = "seaborn-v0_8-whitegrid"
    palette: str = "husl"
    save_format: str = "png"


@dataclass
class VisualizationResult:
    """可视化结果"""
    result_id: str
    figures: List[Dict]
    figure_paths: List[str]
    created_at: str
    metadata: Dict


class ModelVisualizer:
    """模型可视化器（移植自 v3.0 ModelVisualizer，绘图逻辑保持不变）"""

    def __init__(self, config: Optional[Dict] = None):
        """初始化可视化器"""
        self.config = config or {
            "default_style": "seaborn-v0_8-whitegrid",
            "default_palette": "husl",
            "default_dpi": 300,
            "default_format": "png",
            "figure_dir": "figures"
        }
        self.figures_created = []

    def create_all_figures(self, data: "pd.DataFrame",
                          y_true: "np.ndarray",
                          y_pred: "np.ndarray",
                          feature_names: Optional[List[str]] = None,
                          feature_importance: Optional[Dict[str, float]] = None,
                          output_dir: str = "figures") -> VisualizationResult:
        """
        创建所有可视化图表（真实绘图逻辑，依赖 matplotlib/numpy/pandas）。

        Args:
            data: 原始数据（DataFrame）；可为 None（仅当不需要数据分布类图表时）。
            y_true: 真实值（np.ndarray）；可为 None（跳过预测/残差/误差类图表）。
            y_pred: 预测值（np.ndarray）；可为 None。
            feature_names: 特征名称。
            feature_importance: 特征重要性 dict。
            output_dir: 输出目录。

        Returns:
            VisualizationResult: 含生成图表的路径列表。

        Raises:
            ImportError: 当 matplotlib / numpy / pandas 任一缺失时，清晰报错。
        """
        # —— 依赖显式校验：缺失即抛出明确 ImportError，不进入“伪造输出”分支 ——
        if np is None or pd is None:
            raise ImportError(
                "可视化模块需要 numpy 与 pandas，请先安装：\n"
                "  pip install numpy pandas"
            )
        try:
            import matplotlib  # noqa
        except ImportError as e:
            raise ImportError(
                "可视化模块需要 matplotlib 来生成图表，请先安装：\n"
                "  pip install matplotlib"
            ) from e

        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        figures = []
        figure_paths = []

        # 1. 预测值 vs 真实值散点图（需 y_true/y_pred）
        if y_true is not None and y_pred is not None:
            fig_path = self._plot_prediction_vs_actual(y_true, y_pred, output_path)
            if fig_path:
                figures.append({
                    "id": "pred_vs_actual",
                    "title": "预测值 vs 真实值",
                    "type": "scatter",
                    "path": str(fig_path)
                })
                figure_paths.append(str(fig_path))

            # 2. 残差分布图
            fig_path = self._plot_residuals(y_true, y_pred, output_path)
            if fig_path:
                figures.append({
                    "id": "residuals",
                    "title": "残差分布",
                    "type": "histogram",
                    "path": str(fig_path)
                })
                figure_paths.append(str(fig_path))

            # 6. 误差随样本变化图
            fig_path = self._plot_error_over_samples(y_true, y_pred, output_path)
            if fig_path:
                figures.append({
                    "id": "error_over_samples",
                    "title": "误差随样本变化",
                    "type": "line",
                    "path": str(fig_path)
                })
                figure_paths.append(str(fig_path))

        # 3. 特征重要性图（需 feature_importance）
        if feature_importance:
            fig_path = self._plot_feature_importance(feature_importance, output_path)
            if fig_path:
                figures.append({
                    "id": "feature_importance",
                    "title": "特征重要性",
                    "type": "bar",
                    "path": str(fig_path)
                })
                figure_paths.append(str(fig_path))

        # 4. 数据分布图（需 data + feature_names）
        if data is not None and feature_names:
            fig_path = self._plot_data_distribution(data, feature_names[:6], output_path)
            if fig_path:
                figures.append({
                    "id": "data_distribution",
                    "title": "数据分布",
                    "type": "histogram",
                    "path": str(fig_path)
                })
                figure_paths.append(str(fig_path))

        # 5. 相关性热力图（需 data）
        if data is not None:
            fig_path = self._plot_correlation_heatmap(data, output_path)
            if fig_path:
                figures.append({
                    "id": "correlation_heatmap",
                    "title": "特征相关性",
                    "type": "heatmap",
                    "path": str(fig_path)
                })
                figure_paths.append(str(fig_path))

        # 7. 箱线图（需 data + feature_names）
        if data is not None and feature_names:
            fig_path = self._plot_boxplot(data, feature_names[:6], output_path)
            if fig_path:
                figures.append({
                    "id": "boxplot",
                    "title": "特征箱线图",
                    "type": "box",
                    "path": str(fig_path)
                })
                figure_paths.append(str(fig_path))

        result = VisualizationResult(
            result_id=f"VR-{datetime.now().strftime('%Y%m%d%H%M%S')}",
            figures=figures,
            figure_paths=figure_paths,
            created_at=datetime.now().isoformat(),
            metadata={
                "total_figures": len(figures),
                "output_dir": str(output_path)
            }
        )
        return result

    def _get_plot_style(self):
        """获取绘图样式，配置中文字体（仅在使用时导入 matplotlib）。"""
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        try:
            plt.style.use(self.config.get("default_style", "seaborn-v0_8-whitegrid"))
        except Exception:
            pass
        # 配置中文字体（缺失时 matplotlib 自动回退，不报错）
        plt.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei', 'DejaVu Sans']
        plt.rcParams['axes.unicode_minus'] = False
        return plt

    def _plot_prediction_vs_actual(self, y_true: "np.ndarray", y_pred: "np.ndarray",
                                   output_dir: Path) -> Optional[Path]:
        """绘制预测值 vs 真实值散点图"""
        try:
            plt = self._get_plot_style()
            fig, ax = plt.subplots(figsize=(10, 6))

            ax.scatter(y_true, y_pred, alpha=0.6, edgecolors='w', linewidth=0.5)

            min_val = min(np.min(y_true), np.min(y_pred))
            max_val = max(np.max(y_true), np.max(y_pred))
            ax.plot([min_val, max_val], [min_val, max_val], 'r--', lw=2, label='完美预测')

            ax.set_xlabel('真实值', fontsize=12)
            ax.set_ylabel('预测值', fontsize=12)
            ax.set_title('预测值 vs 真实值', fontsize=14)
            ax.legend()
            ax.grid(True, alpha=0.3)

            ss_res = np.sum((y_true - y_pred) ** 2)
            ss_tot = np.sum((y_true - np.mean(y_true)) ** 2)
            r2 = 1 - (ss_res / ss_tot) if ss_tot > 0 else 0

            ax.text(0.05, 0.95, f'R² = {r2:.4f}', transform=ax.transAxes,
                    fontsize=12, verticalalignment='top',
                    bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))

            fig_path = output_dir / f"pred_vs_actual.{self.config.get('default_format', 'png')}"
            plt.tight_layout()
            plt.savefig(fig_path, dpi=self.config.get("default_dpi", 300), bbox_inches='tight')
            plt.close()
            return fig_path
        except Exception as e:
            print(f"创建预测散点图失败: {e}")
            return None

    def _plot_residuals(self, y_true: "np.ndarray", y_pred: "np.ndarray",
                       output_dir: Path) -> Optional[Path]:
        """绘制残差分布图（含直方图与 Q-Q 图；scipy 缺失时仅画直方图）"""
        try:
            plt = self._get_plot_style()
            residuals = y_true - y_pred

            fig, axes = plt.subplots(1, 2, figsize=(14, 5))

            # 残差直方图（始终绘制）
            axes[0].hist(residuals, bins=30, edgecolor='black', alpha=0.7)
            axes[0].axvline(x=0, color='r', linestyle='--', linewidth=2)
            axes[0].set_xlabel('残差', fontsize=12)
            axes[0].set_ylabel('频数', fontsize=12)
            axes[0].set_title('残差分布直方图', fontsize=14)
            axes[0].grid(True, alpha=0.3)

            # 残差 Q-Q 图（依赖 scipy；缺失时跳过并说明）
            try:
                from scipy import stats
                stats.probplot(residuals, dist="norm", plot=axes[1])
                axes[1].set_title('残差Q-Q图', fontsize=14)
                axes[1].grid(True, alpha=0.3)
            except ImportError:
                axes[1].text(0.5, 0.5, 'scipy 未安装\n已跳过 Q-Q 图',
                             transform=axes[1].transAxes, ha='center', va='center',
                             fontsize=12)
                axes[1].set_title('残差Q-Q图（已跳过）', fontsize=14)
                axes[1].set_xticks([])
                axes[1].set_yticks([])

            fig_path = output_dir / f"residuals.{self.config.get('default_format', 'png')}"
            plt.tight_layout()
            plt.savefig(fig_path, dpi=self.config.get("default_dpi", 300), bbox_inches='tight')
            plt.close()
            return fig_path
        except Exception as e:
            print(f"创建残差图失败: {e}")
            return None

    def _plot_feature_importance(self, feature_importance: Dict[str, float],
                                output_dir: Path) -> Optional[Path]:
        """绘制特征重要性图"""
        try:
            plt = self._get_plot_style()

            sorted_imp = sorted(feature_importance.items(), key=lambda x: x[1], reverse=True)[:15]
            features = [x[0] for x in sorted_imp]
            importance = [x[1] for x in sorted_imp]

            fig, ax = plt.subplots(figsize=(10, 6))

            colors = plt.cm.viridis(np.linspace(0.3, 0.9, len(features)))
            bars = ax.barh(range(len(features)), importance, color=colors)

            ax.set_yticks(range(len(features)))
            ax.set_yticklabels(features)
            ax.set_xlabel('重要性', fontsize=12)
            ax.set_title('特征重要性排名', fontsize=14)
            ax.invert_yaxis()

            for bar, imp in zip(bars, importance):
                ax.text(bar.get_width() + 0.01, bar.get_y() + bar.get_height()/2,
                        f'{imp:.3f}', va='center', fontsize=10)

            ax.grid(True, alpha=0.3, axis='x')

            fig_path = output_dir / f"feature_importance.{self.config.get('default_format', 'png')}"
            plt.tight_layout()
            plt.savefig(fig_path, dpi=self.config.get("default_dpi", 300), bbox_inches='tight')
            plt.close()
            return fig_path
        except Exception as e:
            print(f"创建特征重要性图失败: {e}")
            return None

    def _plot_data_distribution(self, data: "pd.DataFrame", feature_names: List[str],
                               output_dir: Path) -> Optional[Path]:
        """绘制数据分布图"""
        try:
            plt = self._get_plot_style()

            n_features = min(len(feature_names), 6)
            n_cols = 3
            n_rows = (n_features + n_cols - 1) // n_cols

            fig, axes = plt.subplots(n_rows, n_cols, figsize=(14, 4 * n_rows))
            axes = axes.flatten() if n_features > 1 else [axes]

            for i, name in enumerate(feature_names[:n_features]):
                if name in data.columns:
                    ax = axes[i]
                    data[name].hist(bins=20, ax=ax, edgecolor='black', alpha=0.7)
                    ax.set_title(name, fontsize=12)
                    ax.set_xlabel('')
                    ax.set_ylabel('')
                    ax.grid(True, alpha=0.3)

            for i in range(n_features, len(axes)):
                axes[i].set_visible(False)

            fig_path = output_dir / f"data_distribution.{self.config.get('default_format', 'png')}"
            plt.suptitle('特征数据分布', fontsize=14, y=1.02)
            plt.tight_layout()
            plt.savefig(fig_path, dpi=self.config.get("default_dpi", 300), bbox_inches='tight')
            plt.close()
            return fig_path
        except Exception as e:
            print(f"创建数据分布图失败: {e}")
            return None

    def _plot_correlation_heatmap(self, data: "pd.DataFrame",
                                 output_dir: Path) -> Optional[Path]:
        """绘制相关性热力图"""
        try:
            plt = self._get_plot_style()

            numeric_data = data.select_dtypes(include=[np.number])
            if numeric_data.shape[1] < 2:
                return None

            corr_matrix = numeric_data.corr()

            fig, ax = plt.subplots(figsize=(10, 8))
            im = ax.imshow(corr_matrix, cmap='coolwarm', aspect='auto', vmin=-1, vmax=1)
            plt.colorbar(im, ax=ax)

            tick_range = range(len(corr_matrix.columns))
            ax.set_xticks(tick_range)
            ax.set_yticks(tick_range)
            ax.set_xticklabels(corr_matrix.columns, rotation=45, ha='right')
            ax.set_yticklabels(corr_matrix.columns)

            for i in range(len(corr_matrix)):
                for j in range(len(corr_matrix)):
                    ax.text(j, i, f'{corr_matrix.iloc[i, j]:.2f}',
                            ha='center', va='center', fontsize=8,
                            color='white' if abs(corr_matrix.iloc[i, j]) > 0.5 else 'black')

            ax.set_title('特征相关性热力图', fontsize=14)

            fig_path = output_dir / f"correlation_heatmap.{self.config.get('default_format', 'png')}"
            plt.tight_layout()
            plt.savefig(fig_path, dpi=self.config.get("default_dpi", 300), bbox_inches='tight')
            plt.close()
            return fig_path
        except Exception as e:
            print(f"创建热力图失败: {e}")
            return None

    def _plot_error_over_samples(self, y_true: "np.ndarray", y_pred: "np.ndarray",
                                output_dir: Path) -> Optional[Path]:
        """绘制误差随样本变化图"""
        try:
            plt = self._get_plot_style()
            errors = np.abs(y_true - y_pred)

            fig, axes = plt.subplots(1, 2, figsize=(14, 5))

            axes[0].plot(range(len(errors)), errors, 'b-', alpha=0.7, linewidth=0.8)
            axes[0].axhline(y=np.mean(errors), color='r', linestyle='--',
                            label=f'平均误差: {np.mean(errors):.4f}')
            axes[0].set_xlabel('样本索引', fontsize=12)
            axes[0].set_ylabel('绝对误差', fontsize=12)
            axes[0].set_title('误差随样本变化', fontsize=14)
            axes[0].legend()
            axes[0].grid(True, alpha=0.3)

            sorted_errors = np.sort(errors)
            cumulative = np.arange(1, len(sorted_errors) + 1) / len(sorted_errors)
            axes[1].plot(sorted_errors, cumulative, 'b-', linewidth=2)
            axes[1].set_xlabel('绝对误差', fontsize=12)
            axes[1].set_ylabel('累积概率', fontsize=12)
            axes[1].set_title('误差累积分布', fontsize=14)
            axes[1].grid(True, alpha=0.3)

            fig_path = output_dir / f"error_analysis.{self.config.get('default_format', 'png')}"
            plt.tight_layout()
            plt.savefig(fig_path, dpi=self.config.get("default_dpi", 300), bbox_inches='tight')
            plt.close()
            return fig_path
        except Exception as e:
            print(f"创建误差分析图失败: {e}")
            return None

    def _plot_boxplot(self, data: "pd.DataFrame", feature_names: List[str],
                     output_dir: Path) -> Optional[Path]:
        """绘制箱线图"""
        try:
            plt = self._get_plot_style()

            numeric_features = [f for f in feature_names if f in data.columns and
                                pd.api.types.is_numeric_dtype(data[f])]
            if not numeric_features:
                return None

            fig, ax = plt.subplots(figsize=(12, 6))

            data_to_plot = [data[f].dropna().values for f in numeric_features[:8]]

            bp = ax.boxplot(data_to_plot, tick_labels=numeric_features[:len(data_to_plot)],
                           patch_artist=True)

            colors = plt.cm.Set3(np.linspace(0, 1, len(data_to_plot)))
            for patch, color in zip(bp['boxes'], colors):
                patch.set_facecolor(color)

            ax.set_xlabel('特征', fontsize=12)
            ax.set_ylabel('值', fontsize=12)
            ax.set_title('特征箱线图', fontsize=14)
            ax.tick_params(axis='x', rotation=45)
            ax.grid(True, alpha=0.3, axis='y')

            fig_path = output_dir / f"boxplot.{self.config.get('default_format', 'png')}"
            plt.tight_layout()
            plt.savefig(fig_path, dpi=self.config.get("default_dpi", 300), bbox_inches='tight')
            plt.close()
            return fig_path
        except Exception as e:
            print(f"创建箱线图失败: {e}")
            return None

    def save_result(self, result: VisualizationResult, output_dir: str):
        """保存可视化结果 JSON"""
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        result_path = output_path / "visualization_result.json"
        with open(result_path, 'w', encoding='utf-8') as f:
            json.dump(asdict(result), f, ensure_ascii=False, indent=2)
        print(f"可视化结果已保存到: {output_path}")

    def generate_report_md(self, result: VisualizationResult, output_path: str):
        """生成可视化报告 Markdown"""
        md_content = f"""# 可视化报告

## 基本信息

- **结果ID**: {result.result_id}
- **生成时间**: {result.created_at}
- **图表总数**: {result.metadata.get('total_figures', 0)}

## 图表列表

"""
        for i, fig in enumerate(result.figures, 1):
            md_content += f"### {i}. {fig['title']}\n\n"
            md_content += f"- **图表ID**: {fig['id']}\n"
            md_content += f"- **图表类型**: {fig['type']}\n"
            md_content += f"- **文件路径**: `{fig['path']}`\n\n"

        md_content += f"""
## 使用说明

所有图表已保存到目录：`{result.metadata.get('output_dir', 'figures/')}`

图表格式：{self.config.get('default_format', 'png')}，分辨率：{self.config.get('default_dpi', 300)} DPI

---

*生成时间: {result.created_at}*
"""
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(md_content)
        print(f"可视化报告已保存到: {output_path}")


def main():
    """示例用法（仅在依赖齐全时可运行；缺失依赖会在此明确报错）。"""
    if np is None or pd is None:
        raise ImportError("示例需要 numpy 与 pandas：pip install numpy pandas")
    try:
        import matplotlib  # noqa
    except ImportError:
        raise ImportError("示例需要 matplotlib：pip install matplotlib")

    np.random.seed(42)
    n_samples, n_features = 100, 5
    X = np.random.randn(n_samples, n_features)
    y = 2 * X[:, 0] + 3 * X[:, 1] + np.random.randn(n_samples) * 0.5
    feature_names = [f'feature_{i}' for i in range(n_features)]
    y_pred = y + np.random.randn(n_samples) * 0.2
    data = pd.DataFrame(X, columns=feature_names)
    feature_importance = {
        'feature_0': 0.35, 'feature_1': 0.45, 'feature_2': 0.10,
        'feature_3': 0.05, 'feature_4': 0.05
    }
    visualizer = ModelVisualizer()
    output_dir = Path("output/figures")
    output_dir.mkdir(parents=True, exist_ok=True)
    result = visualizer.create_all_figures(
        data, y, y_pred,
        feature_names=feature_names,
        feature_importance=feature_importance,
        output_dir=str(output_dir)
    )
    print(f"生成图表数: {len(result.figures)}")
    visualizer.save_result(result, "output")
    visualizer.generate_report_md(result, "output/visualization_report.md")


if __name__ == "__main__":
    main()
