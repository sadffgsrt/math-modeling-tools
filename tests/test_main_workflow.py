"""
数学建模竞赛工作流 - 主控脚本测试
测试工作流初始化、缓存机制与配置加载
"""

import sys
import json
import tempfile
import shutil
from pathlib import Path
from unittest import TestCase, main as unittest_main

# 添加父目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))


class TestMainWorkflow(TestCase):
    """测试主控脚本"""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.project_dir = Path(self.temp_dir) / "test_project"

    def tearDown(self):
        import gc
        gc.collect()  # 强制垃圾回收，关闭文件句柄
        try:
            shutil.rmtree(self.temp_dir)
        except PermissionError:
            # Windows上日志文件可能被占用，忽略
            pass

    def test_workflow_initialization(self):
        """测试工作流初始化"""
        from main import MathModelingWorkflow

        workflow = MathModelingWorkflow(str(self.project_dir))
        self.assertIsNotNone(workflow)
        self.assertTrue(self.project_dir.exists())

    def test_workflow_status(self):
        """测试工作流状态"""
        from main import MathModelingWorkflow

        workflow = MathModelingWorkflow(str(self.project_dir))
        status = workflow.get_status()

        self.assertIn("project_dir", status)
        self.assertIn("current_stage", status)
        self.assertIn("stages", status)

    def test_workflow_state_persistence(self):
        """测试状态持久化"""
        from main import MathModelingWorkflow

        workflow = MathModelingWorkflow(str(self.project_dir))
        workflow.state["project_id"] = "TEST-001"
        workflow._save_state()

        # 重新加载
        workflow2 = MathModelingWorkflow(str(self.project_dir))
        self.assertEqual(workflow2.state["project_id"], "TEST-001")


class TestCacheMechanism(TestCase):
    """测试缓存机制"""

    def test_cache_set_and_get(self):
        """测试缓存设置和获取"""
        from main import WorkflowCache
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as temp_dir:
            cache = WorkflowCache(Path(temp_dir))

            # 设置缓存
            cache.set("test_key", {"value": 123})

            # 获取缓存
            result = cache.get("test_key")
            self.assertEqual(result["value"], 123)

    def test_cache_clear(self):
        """测试缓存清理"""
        from main import WorkflowCache
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as temp_dir:
            cache = WorkflowCache(Path(temp_dir))

            cache.set("key1", "value1")
            cache.set("key2", "value2")

            cache.clear()

            self.assertIsNone(cache.get("key1"))
            self.assertIsNone(cache.get("key2"))


class TestConfigLoading(TestCase):
    """测试配置加载"""

    def test_config_file_exists(self):
        """测试配置文件存在"""
        from pathlib import Path

        config_path = Path(__file__).parent.parent / "config" / "workflow_config.yaml"
        self.assertTrue(config_path.exists())

    def test_model_catalog_exists(self):
        """测试模型目录存在"""
        from pathlib import Path

        catalog_path = Path(__file__).parent.parent / "config" / "model_catalog.json"
        self.assertTrue(catalog_path.exists())

    def test_model_catalog_structure(self):
        """测试模型目录结构"""
        import json
        from pathlib import Path

        catalog_path = Path(__file__).parent.parent / "config" / "model_catalog.json"
        with open(catalog_path, 'r', encoding='utf-8') as f:
            catalog = json.load(f)

        self.assertIn("metadata", catalog)
        self.assertIn("models", catalog)
        self.assertGreater(len(catalog["models"]), 0)

    def test_no_duplicate_model_ids(self):
        """测试模型目录无重复 ID（C3 修复验证）"""
        catalog_path = Path(__file__).parent.parent / "config" / "model_catalog.json"
        with open(catalog_path, 'r', encoding='utf-8') as f:
            catalog = json.load(f)

        all_ids = []
        for cat_info in catalog["models"].values():
            all_ids.extend(m["id"] for m in cat_info["models"])
        duplicates = [x for x in all_ids if all_ids.count(x) > 1]
        self.assertEqual(len(set(duplicates)), 0,
                         f"模型目录存在重复 ID: {set(duplicates)}")

    def test_implemented_field_exists(self):
        """测试所有模型都有 implemented 字段（C4 修复验证）"""
        catalog_path = Path(__file__).parent.parent / "config" / "model_catalog.json"
        with open(catalog_path, 'r', encoding='utf-8') as f:
            catalog = json.load(f)

        for cat_name, cat_info in catalog["models"].items():
            for model in cat_info["models"]:
                self.assertIn("implemented", model,
                              f"{cat_name}/{model['id']} 缺少 implemented 字段")


if __name__ == "__main__":
    unittest_main()
