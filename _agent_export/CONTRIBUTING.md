# 贡献指南

## 如何新增模型

1. 在 `config/model_catalog.json` 中添加模型条目（设 `implemented: true`）
2. 在 `modules/model_solving/factories/` 下对应类别文件中实现求解逻辑：
   - `_base.py`：核心 ModelFactory 基类
   - `evaluation.py` / `optimization.py` / `prediction.py` / `time_series.py` / `simulation.py` / `graph.py` / `neural.py` / `fuzzy.py` / `meta_heuristic.py` / `statistics.py`
3. 在 `ModelFactory` 的 `_build_model()` 或对应 Solver 中添加分发分支
4. 运行 `python scripts/validate_catalog.py` 校验 catalog
5. 运行 `pytest tests/test_model_factory.py -v` 确认测试通过

## 如何新增阶段

1. 新建 `modules/<stage_name>/` 目录，包含 `__init__.py` + `runner.py`
2. 在 `main.py` 的 `MathModelingWorkflow.STAGES` 列表中添加阶段名
3. 在 `main.py` 的 `run_stage()` 方法中添加分发分支
4. 在 `modules/__init__.py` 中注册别名

## 代码规范

```bash
# Lint 检查
ruff check . --ignore E501

# 类型检查
mypy modules --ignore-missing-imports

# 运行测试（含覆盖率）
pytest --cov=modules --cov-report=term-missing

# 格式化
ruff format .
```

## 提交规范

使用 [Conventional Commits](https://www.conventionalcommits.org/)：
- `feat:` 新功能
- `fix:` 修复
- `refactor:` 重构
- `test:` 新增或修改测试
- `docs:` 文档变更
- `chore:` 工程配置（CI、依赖、lint 等）

## 分支策略

- `main`: 稳定版本
- `feat/*`: 新功能分支
- `fix/*`: 修复分支
- 合并前需确保 pytest 全部通过