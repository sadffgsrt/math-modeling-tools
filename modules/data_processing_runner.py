# -*- coding: utf-8 -*-
# 数据处理阶段薄包装 runner（main.py 通过 modules.data_processing_runner 调用）
# 职责：扫描 raw_data 数据文件 → DataProcessor 处理 → 写入 processed_data → 返回 ProcessingResult.asdict()

from pathlib import Path
from typing import Dict, List, Optional
from dataclasses import asdict

from modules.data_processing.processor import DataProcessor, ProcessingResult

# 支持的数据文件扩展名
_DATA_EXTS = [".csv", ".xlsx", ".xls", ".json", ".tsv"]


def _find_data_files(raw_dir: Path) -> List[Path]:
    """扫描 raw_data 目录下所有支持的数据文件。"""
    if not raw_dir.exists():
        return []
    files: List[Path] = []
    for ext in _DATA_EXTS:
        files.extend(sorted(raw_dir.glob(f"*{ext}")))
    return files


def run_data_processing(workflow, **kwargs) -> Dict:
    """
    数据处理阶段入口。

    Returns:
        ProcessingResult 的 asdict()，含键：result_id, input_path, output_path,
        original_shape, processed_shape, operations_applied, quality_report 等。
    """
    project_dir = Path(getattr(workflow, "project_dir", "projects/.template"))
    raw_dir = project_dir / "raw_data"
    out_dir = project_dir / "processed_data"
    out_dir.mkdir(parents=True, exist_ok=True)

    # 支持显式指定数据文件
    data_file = kwargs.get("data_file")
    if data_file:
        files = [Path(data_file)]
    else:
        files = _find_data_files(raw_dir)

    if not files:
        raise FileNotFoundError(
            f"未在 {raw_dir} 找到数据文件（支持 {_DATA_EXTS}），请先放入原始数据"
        )

    processor = DataProcessor(kwargs.get("config"))

    first_result: Optional[ProcessingResult] = None
    for f in files:
        dataset_name = f.stem
        result = processor.process_dataset(str(f), str(out_dir), dataset_name)
        if first_result is None:
            first_result = result

    # 返回首个数据集的处理结果（其余已落盘到 processed_data）
    return asdict(first_result)
