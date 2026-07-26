# tests

测试套件。

- 绿集（当前稳定）：`test_workflow.py`、`test_model_solving.py`、`test_validation.py` → 110 passed / 19 xfailed / 0 failed。
- `test_model_factory.py` 等文件面向已丢失的原版架构 API，与恢复版存在代差，保留供参考但**未纳入绿集**。

运行绿集：

```bash
PYTHONPATH=. python -m pytest tests/test_workflow.py tests/test_model_solving.py tests/test_validation.py -o addopts="" -q
```
