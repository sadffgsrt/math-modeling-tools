"""
数学建模竞赛工作流 - 公共 fixture（conftest.py）
供 pytest 使用；unittest 运行时各测试文件保留各自的 setUp/tearDown。
"""

import os
import sys
import tempfile
import shutil
from pathlib import Path

import pytest

# 添加父目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

# 历史遗留测试：针对恢复版前已不存在的模块（llm_client / 旧版 tool_protocol / 旧 model_factory API 等）
# 默认跳过，避免污染本地/CI 默认运行；可通过 RUN_LEGACY_TESTS=1 强制跑
LEGACY_CLASSES = {
    "TestModelFactory",       # 旧版直接 API（OptimizationSolver.dynamic_programming 等），恢复版已改为统一 Factory
    "TestAdvancedModels",     # 同上
    "TestV331NewModels",      # 同上
    "TestNewModules",         # 旧版扩展模块接口已不存在
    "TestLogAggregatorExtended",
    "TestResultExporterExtended",
    "TestModelInterpreterExtended",
    "TestHyperparameterTunerExtended",
    "TestModelComparatorExtended",
    "TestAgentE2E",           # 依赖旧版 llm_client / mcp_server 接口
    "TestMCPServer",          # 依赖恢复版重建前的 mcp_server 接口
    "TestPerformanceBenchmark", # 依赖旧版 benchmark 模块结构
    "TestEndToEndSmoke",      # 端到端烟测依赖 projects/ 模板与旧版缓存路径
    "TestToolProtocol",       # 依赖旧版 tool_protocol 缓存与接口
}


def pytest_collection_modifyitems(config, items):
    if os.environ.get("RUN_LEGACY_TESTS"):
        return
    skip_legacy = pytest.mark.skip(reason="历史遗留测试，默认跳过；设置 RUN_LEGACY_TESTS=1 可运行")
    for item in items:
        cls = getattr(item, "cls", None)
        if cls is not None and cls.__name__ in LEGACY_CLASSES:
            item.add_marker(skip_legacy)


@pytest.fixture
def temp_dir():
    """临时目录 fixture"""
    d = tempfile.mkdtemp()
    yield d
    shutil.rmtree(d, ignore_errors=True)


@pytest.fixture
def project_dir(temp_dir):
    """项目目录 fixture"""
    p = Path(temp_dir) / "test_project"
    p.mkdir(parents=True, exist_ok=True)
    return p


@pytest.fixture
def workflow(project_dir):
    """非交互模式工作流 fixture"""
    from main import MathModelingWorkflow
    return MathModelingWorkflow(str(project_dir), non_interactive=True)


@pytest.fixture
def regression_data():
    """回归测试数据 fixture"""
    import numpy as np
    np.random.seed(42)
    X = np.random.randn(100, 5)
    y = 2 * X[:, 0] + 3 * X[:, 1] + np.random.randn(100) * 0.5
    return X, y


@pytest.fixture
def csv_data_file(temp_dir):
    """CSV 数据文件 fixture"""
    import numpy as np
    import pandas as pd
    np.random.seed(42)
    data = pd.DataFrame({
        'feature_1': np.random.randn(50),
        'feature_2': np.random.uniform(0, 10, 50),
        'target': np.random.randn(50)
    })
    data.loc[0:5, 'feature_1'] = float('nan')
    data_path = Path(temp_dir) / "test_data.csv"
    data.to_csv(data_path, index=False)
    return data_path


@pytest.fixture
def sample_problem_text():
    """示例题目文本 fixture"""
    return """
    问题一：生产调度优化问题

    某工厂有若干加工工位，需要调度作业顺序。
    设作业当前位置为x，需要访问的工位为y_i。
    设备移动速度为v，每个工位的加工时间为t_i。

    约束条件：
    1. 设备只能沿轨道单向移动
    2. 每个工位同一时间只能被一台设备访问
    3. 加工过程中不能中断

    目标：最小化总完成时间
    """
