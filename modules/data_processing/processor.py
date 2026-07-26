# -*- coding: utf-8 -*-
# 数据处理模块 (Module 03)
# 功能：数据清洗、缺失值处理、特征工程及可视化分析，输出标准化数据集
# 说明：从 v3.0 蓝本（03_data_processing/processor.py）忠实移植，去掉数字前缀 import，类与接口不变。

import json
import pandas as pd
import numpy as np
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union
from dataclasses import dataclass, asdict
from datetime import datetime
import warnings
warnings.filterwarnings('ignore')


@dataclass
class DataQualityReport:
    """数据质量报告"""
    report_id: str
    dataset_name: str
    original_shape: Tuple[int, int]
    cleaned_shape: Tuple[int, int]
    missing_values: Dict[str, int]
    missing_percentage: Dict[str, float]
    duplicate_rows: int
    outlier_info: Dict
    data_types: Dict[str, str]
    statistics: Dict
    quality_score: float
    issues_found: List[str]
    recommendations: List[str]
    created_at: str


@dataclass
class FeatureInfo:
    """特征信息"""
    feature_name: str
    data_type: str
    missing_count: int
    missing_percentage: float
    unique_values: int
    mean: Optional[float]
    std: Optional[float]
    min_value: Optional[float]
    max_value: Optional[float]
    is_numeric: bool
    importance_score: float


@dataclass
class ProcessingResult:
    """数据处理结果"""
    result_id: str
    dataset_name: str
    input_path: str
    output_path: str
    original_shape: Tuple[int, int]
    processed_shape: Tuple[int, int]
    operations_applied: List[str]
    quality_report: DataQualityReport
    feature_info: List[FeatureInfo]
    created_at: str
    metadata: Dict


class DataProcessor:
    """数据处理器"""

    def __init__(self, config: Optional[Dict] = None):
        """
        初始化数据处理器

        Args:
            config: 配置参数
        """
        self.config = config or {
            "handle_missing": "auto",  # auto, drop, interpolate, fill
            "handle_outlier": "auto",  # auto, drop, clip, transform
            "scaling": "standard",     # standard, minmax, robust, none
            "remove_duplicates": True,
            "fill_value": 0,
            # 缺失值处理阈值
            "missing_delete_threshold": 0.8,  # 缺失超过此比例删除列
            "missing_interpolate_threshold": 0.3,  # 缺失超过此比例使用插值
            # 异常值处理配置
            "outlier_iqr_multiplier": 1.5,  # IQR倍数
            "outlier_quantile_lower": 0.25,  # 下四分位数
            "outlier_quantile_upper": 0.75,  # 上四分位数
            # 质量评分权重
            "quality_missing_weight": 0.5,
            "quality_duplicate_weight": 0.3,
            "quality_constant_weight": 0.2,
        }

    def process_dataset(self, data_path: str, output_dir: str,
                       dataset_name: str = "dataset") -> ProcessingResult:
        """
        处理数据集

        Args:
            data_path: 数据文件路径
            output_dir: 输出目录
            dataset_name: 数据集名称

        Returns:
            ProcessingResult: 处理结果
        """
        # 读取数据
        df = self._load_data(data_path)
        original_shape = df.shape

        operations_applied = []

        # 1. 基本清洗
        df, ops = self._basic_cleaning(df)
        operations_applied.extend(ops)

        # 2. 处理缺失值
        df, ops = self._handle_missing_values(df)
        operations_applied.extend(ops)

        # 3. 处理异常值
        df, ops = self._handle_outliers(df)
        operations_applied.extend(ops)

        # 4. 特征工程
        df, ops = self._feature_engineering(df)
        operations_applied.extend(ops)

        # 5. 数据标准化
        df, ops = self._scale_data(df)
        operations_applied.extend(ops)

        # 生成数据质量报告
        quality_report = self._generate_quality_report(
            df, original_shape, dataset_name
        )

        # 生成特征信息
        feature_info = self._analyze_features(df)

        # 保存处理后的数据
        output_path = Path(output_dir) / f"{dataset_name}_processed.csv"
        output_path.parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(output_path, index=False, encoding='utf-8-sig')

        # 构建处理结果
        result = ProcessingResult(
            result_id=f"PR-{datetime.now().strftime('%Y%m%d%H%M%S')}",
            dataset_name=dataset_name,
            input_path=data_path,
            output_path=str(output_path),
            original_shape=original_shape,
            processed_shape=df.shape,
            operations_applied=operations_applied,
            quality_report=quality_report,
            feature_info=feature_info,
            created_at=datetime.now().isoformat(),
            metadata={
                "rows_processed": original_shape[0] - df.shape[0],
                "columns_added": df.shape[1] - original_shape[1],
                "quality_score": quality_report.quality_score
            }
        )

        return result

    def _load_data(self, data_path: str) -> pd.DataFrame:
        """加载数据"""
        path = Path(data_path)

        if path.suffix == '.csv':
            return pd.read_csv(data_path, encoding='utf-8-sig')
        elif path.suffix in ['.xlsx', '.xls']:
            return pd.read_excel(data_path)
        elif path.suffix == '.json':
            return pd.read_json(data_path)
        elif path.suffix == '.tsv':
            return pd.read_csv(data_path, sep='\t')
        else:
            raise ValueError(f"不支持的文件格式: {path.suffix}")

    def _basic_cleaning(self, df: pd.DataFrame) -> Tuple[pd.DataFrame, List[str]]:
        """基本清洗"""
        ops = []

        # 删除完全重复的行
        if self.config.get("remove_duplicates", True):
            before = len(df)
            df = df.drop_duplicates()
            if len(df) < before:
                ops.append(f"删除{before - len(df)}行重复数据")

        # 清理列名
        df.columns = df.columns.str.strip()

        # 删除全为空的列
        before_cols = df.shape[1]
        df = df.dropna(axis=1, how='all')
        if df.shape[1] < before_cols:
            ops.append(f"删除{before_cols - df.shape[1]}个空列")

        return df, ops

    def _handle_missing_values(self, df: pd.DataFrame) -> Tuple[pd.DataFrame, List[str]]:
        """处理缺失值"""
        ops = []
        missing_before = df.isnull().sum().sum()

        if missing_before == 0:
            return df, ops

        strategy = self.config.get("handle_missing", "auto")

        # 分离数值列和非数值列
        numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
        categorical_cols = df.select_dtypes(exclude=[np.number]).columns.tolist()

        if strategy == "auto":
            # 自动策略：根据缺失比例选择方法（保守策略，保留更多数据）
            missing_delete_threshold = self.config.get("missing_delete_threshold", 0.8)
            missing_interpolate_threshold = self.config.get("missing_interpolate_threshold", 0.3)

            for col in df.columns:
                missing_pct = df[col].isnull().mean()

                if missing_pct > missing_delete_threshold:
                    # 缺失超过阈值，删除该列
                    df = df.drop(columns=[col])
                    ops.append(f"删除列'{col}'(缺失{missing_pct:.1%})")
                elif missing_pct > missing_interpolate_threshold:
                    # 缺失超过插值阈值，使用插值
                    if col in numeric_cols:
                        df[col] = df[col].interpolate(method='linear')
                        df[col] = df[col].fillna(df[col].median())
                        ops.append(f"插值+中位数填充列'{col}'")
                    else:
                        df[col] = df[col].fillna(df[col].mode()[0] if not df[col].mode().empty else "")
                        ops.append(f"众数填充列'{col}'")
                elif missing_pct > 0:
                    # 缺失少于阈值，使用众数/中位数填充
                    if col in numeric_cols:
                        df[col] = df[col].fillna(df[col].median())
                    else:
                        df[col] = df[col].fillna(df[col].mode()[0] if not df[col].mode().empty else "")
                    ops.append(f"填充列'{col}'")

        elif strategy == "drop":
            df = df.dropna()
            ops.append(f"删除所有含缺失值的行")

        elif strategy == "interpolate":
            df = df.interpolate(method='linear')
            ops.append(f"线性插值填充缺失值")

        elif strategy == "fill":
            fill_value = self.config.get("fill_value", 0)
            df = df.fillna(fill_value)
            ops.append(f"使用常量{fill_value}填充缺失值")

        missing_after = df.isnull().sum().sum()
        if missing_before > missing_after:
            ops.append(f"缺失值从{missing_before}减少到{missing_after}")

        return df, ops

    def _handle_outliers(self, df: pd.DataFrame) -> Tuple[pd.DataFrame, List[str]]:
        """处理异常值"""
        ops = []
        strategy = self.config.get("handle_outlier", "auto")

        if strategy == "none":
            return df, ops

        numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()

        # 获取配置项
        iqr_multiplier = self.config.get("outlier_iqr_multiplier", 1.5)
        quantile_lower = self.config.get("outlier_quantile_lower", 0.25)
        quantile_upper = self.config.get("outlier_quantile_upper", 0.75)

        for col in numeric_cols:
            Q1 = df[col].quantile(quantile_lower)
            Q3 = df[col].quantile(quantile_upper)
            IQR = Q3 - Q1

            lower_bound = Q1 - iqr_multiplier * IQR
            upper_bound = Q3 + iqr_multiplier * IQR

            outliers = ((df[col] < lower_bound) | (df[col] > upper_bound)).sum()

            if outliers > 0:
                if strategy == "auto" or strategy == "clip":
                    # 使用边界值截断
                    df[col] = df[col].clip(lower=lower_bound, upper=upper_bound)
                    ops.append(f"截断列'{col}'的{outliers}个异常值")
                elif strategy == "drop":
                    df = df[(df[col] >= lower_bound) & (df[col] <= upper_bound)]
                    ops.append(f"删除列'{col}'的{outliers}个异常值")

        return df, ops

    def _feature_engineering(self, df: pd.DataFrame) -> Tuple[pd.DataFrame, List[str]]:
        """特征工程"""
        ops = []

        # 对分类变量进行编码
        categorical_cols = df.select_dtypes(include=['object']).columns.tolist()

        for col in categorical_cols:
            n_unique = df[col].nunique()
            if n_unique <= 1:
                # 只有1个唯一值，直接删除该列（无信息量）
                df = df.drop(columns=[col])
                ops.append(f"删除常量列'{col}'(唯一值={n_unique})")
            elif n_unique <= 10:
                # 少于10个唯一值，使用独热编码
                # 如果只有2个唯一值，不使用drop_first以保留信息
                drop_first = n_unique > 2
                dummies = pd.get_dummies(df[col], prefix=col, drop_first=drop_first)
                df = pd.concat([df, dummies], axis=1)
                df = df.drop(columns=[col])
                ops.append(f"独热编码列'{col}'(唯一值={n_unique}, 编码后={len(dummies.columns)}列)")
            else:
                # 超过10个唯一值，使用标签编码
                from sklearn.preprocessing import LabelEncoder
                le = LabelEncoder()
                df[col] = le.fit_transform(df[col].astype(str))
                ops.append(f"标签编码列'{col}'(唯一值={n_unique})")

        return df, ops

    def _scale_data(self, df: pd.DataFrame) -> Tuple[pd.DataFrame, List[str]]:
        """数据标准化"""
        ops = []
        scaling = self.config.get("scaling", "none")

        if scaling == "none":
            return df, ops

        numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()

        for col in numeric_cols:
            if scaling == "standard":
                mean = df[col].mean()
                std = df[col].std()
                if std > 0:
                    df[col] = (df[col] - mean) / std
                    ops.append(f"标准化列'{col}'")
            elif scaling == "minmax":
                min_val = df[col].min()
                max_val = df[col].max()
                if max_val > min_val:
                    df[col] = (df[col] - min_val) / (max_val - min_val)
                    ops.append(f"归一化列'{col}'")
            elif scaling == "robust":
                median = df[col].median()
                q75 = df[col].quantile(0.75)
                q25 = df[col].quantile(0.25)
                iqr = q75 - q25
                if iqr > 0:
                    df[col] = (df[col] - median) / iqr
                    ops.append(f"鲁棒标准化列'{col}'")

        return df, ops

    def _generate_quality_report(self, df: pd.DataFrame,
                                original_shape: Tuple[int, int],
                                dataset_name: str) -> DataQualityReport:
        """生成数据质量报告"""
        # 获取配置项
        missing_weight = self.config.get("quality_missing_weight", 0.5)
        duplicate_weight = self.config.get("quality_duplicate_weight", 0.3)
        constant_weight = self.config.get("quality_constant_weight", 0.2)

        # 计算质量分数
        missing_total = df.isnull().sum().sum()
        total_cells = df.shape[0] * df.shape[1]
        missing_score = 1 - (missing_total / total_cells) if total_cells > 0 else 1

        duplicate_ratio = 1 - (df.shape[0] / original_shape[0]) if original_shape[0] > 0 else 1
        duplicate_score = 1 - duplicate_ratio

        # 检查常量列
        constant_cols = [col for col in df.columns if df[col].nunique() <= 1]
        constant_score = 1 - (len(constant_cols) / len(df.columns)) if len(df.columns) > 0 else 1

        quality_score = (missing_score * missing_weight +
                        duplicate_score * duplicate_weight +
                        constant_score * constant_weight) * 100

        # 生成问题列表
        issues = []
        if missing_total > 0:
            issues.append(f"存在{missing_total}个缺失值")
        if df.shape[0] < original_shape[0]:
            issues.append(f"删除了{original_shape[0] - df.shape[0]}行数据")

        # 生成建议
        recommendations = []
        if missing_score < 0.9:
            recommendations.append("建议检查数据源，减少缺失值")
        if quality_score < 80:
            recommendations.append("数据质量较低，建议进行数据审核")

        return DataQualityReport(
            report_id=f"QR-{datetime.now().strftime('%Y%m%d%H%M%S')}",
            dataset_name=dataset_name,
            original_shape=original_shape,
            cleaned_shape=df.shape,
            missing_values=df.isnull().sum().to_dict(),
            missing_percentage=(df.isnull().mean() * 100).to_dict(),
            duplicate_rows=original_shape[0] - df.shape[0],
            outlier_info={},
            data_types=df.dtypes.astype(str).to_dict(),
            statistics=df.describe().to_dict(),
            quality_score=round(quality_score, 2),
            issues_found=issues,
            recommendations=recommendations,
            created_at=datetime.now().isoformat()
        )

    def _analyze_features(self, df: pd.DataFrame) -> List[FeatureInfo]:
        """分析特征信息"""
        features = []

        for col in df.columns:
            is_numeric = pd.api.types.is_numeric_dtype(df[col])

            feature = FeatureInfo(
                feature_name=col,
                data_type=str(df[col].dtype),
                missing_count=int(df[col].isnull().sum()),
                missing_percentage=round(df[col].isnull().mean() * 100, 2),
                unique_values=int(df[col].nunique()),
                mean=round(float(df[col].mean()), 4) if is_numeric else None,
                std=round(float(df[col].std()), 4) if is_numeric else None,
                min_value=round(float(df[col].min()), 4) if is_numeric else None,
                max_value=round(float(df[col].max()), 4) if is_numeric else None,
                is_numeric=is_numeric,
                importance_score=0.0
            )
            features.append(feature)

        return features

    def save_result(self, result: ProcessingResult, output_dir: str):
        """保存处理结果"""
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        # 保存处理结果
        result_path = output_dir / "processing_result.json"
        with open(result_path, 'w', encoding='utf-8') as f:
            json.dump(asdict(result), f, ensure_ascii=False, indent=2, default=str)

        # 保存数据质量报告
        report_path = output_dir / "data_quality_report.json"
        with open(report_path, 'w', encoding='utf-8') as f:
            json.dump(asdict(result.quality_report), f, ensure_ascii=False, indent=2, default=str)

        # 保存特征信息
        feature_path = output_dir / "feature_info.json"
        with open(feature_path, 'w', encoding='utf-8') as f:
            json.dump([asdict(fi) for fi in result.feature_info], f, ensure_ascii=False, indent=2)

        print(f"处理结果已保存到: {output_dir}")

    def generate_report_md(self, result: ProcessingResult, output_path: str):
        """生成数据处理报告Markdown"""
        md_content = f"""# 数据处理报告

## 基本信息

- **处理ID**: {result.result_id}
- **数据集名称**: {result.dataset_name}
- **输入文件**: {result.input_path}
- **输出文件**: {result.output_path}
- **生成时间**: {result.created_at}

## 数据形状变化

| 指标 | 处理前 | 处理后 | 变化 |
|------|--------|--------|------|
| 行数 | {result.original_shape[0]} | {result.processed_shape[0]} | {result.processed_shape[0] - result.original_shape[0]} |
| 列数 | {result.original_shape[1]} | {result.processed_shape[1]} | {result.processed_shape[1] - result.original_shape[1]} |

## 处理操作

"""
        for i, op in enumerate(result.operations_applied, 1):
            md_content += f"{i}. {op}\n"

        md_content += f"""
## 数据质量评估

**质量分数**: {result.quality_report.quality_score}/100

### 发现的问题

"""
        for issue in result.quality_report.issues_found:
            md_content += f"- {issue}\n"

        md_content += "\n### 改进建议\n\n"
        for rec in result.quality_report.recommendations:
            md_content += f"- {rec}\n"

        md_content += "\n## 特征信息\n\n"
        md_content += "| 特征名 | 数据类型 | 缺失率 | 唯一值 | 均值 | 标准差 |\n"
        md_content += "|--------|----------|--------|--------|------|--------|\n"

        for feat in result.feature_info[:20]:  # 最多显示20个特征
            mean_str = f"{feat.mean:.4f}" if feat.mean is not None else "-"
            std_str = f"{feat.std:.4f}" if feat.std is not None else "-"
            md_content += f"| {feat.feature_name} | {feat.data_type} | {feat.missing_percentage}% | {feat.unique_values} | {mean_str} | {std_str} |\n"

        md_content += f"\n---\n\n*生成时间: {result.created_at}*\n"

        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(md_content)

        print(f"数据处理报告已保存到: {output_path}")
