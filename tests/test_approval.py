"""
数学建模竞赛工作流 - 异步审批管理器测试
验证向后兼容 + 同步/异步回调注入 + 异常处理
"""

import sys
import tempfile
import shutil
from pathlib import Path
from unittest import TestCase, main as unittest_main

# 添加父目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))


class TestApprovalAsync(TestCase):
    """步骤 1：异步审批管理器测试
    验证向后兼容 + 同步/异步回调注入 + 异常处理
    """

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.project_dir = Path(self.temp_dir) / "test_approval_project"

    def tearDown(self):
        import gc
        gc.collect()
        try:
            shutil.rmtree(self.temp_dir)
        except PermissionError:
            pass

    def _make_manager(self, non_interactive=False):
        from modules.approval import ApprovalManager
        return ApprovalManager(self.project_dir, non_interactive=non_interactive)

    def _make_medium_operation(self, manager, op_id="test_op_001"):
        """构造一个 medium 风险的待审批操作"""
        return manager.register_operation(
            operation_id=op_id,
            operation_type="stage_execution",
            description="测试操作",
            risk_level="medium",
            command="workflow.run_stage('test')",
            source="AI",
        )

    # ─── 向后兼容测试 ───

    def test_low_risk_auto_approved(self):
        """低风险自动批准（向后兼容）"""
        manager = self._make_manager(non_interactive=False)
        op = manager.register_operation(
            operation_id="low_001",
            operation_type="read_file",
            description="读取文件",
            risk_level="low",
        )
        approved = manager.request_approval(op)
        self.assertTrue(approved)
        self.assertEqual(op["status"], "auto_approved")
        self.assertEqual(op["approved_by"], "System")

    def test_non_interactive_auto_approved(self):
        """非交互模式自动批准（向后兼容）"""
        manager = self._make_manager(non_interactive=True)
        op = self._make_medium_operation(manager)
        approved = manager.request_approval(op)
        self.assertTrue(approved)
        self.assertEqual(op["status"], "auto_approved_non_interactive")
        self.assertEqual(op["approved_by"], "NonInteractive")

    def test_request_approval_signature_unchanged(self):
        """request_approval 签名与返回值类型不变（向后兼容）"""
        manager = self._make_manager(non_interactive=True)
        op = self._make_medium_operation(manager)
        result = manager.request_approval(op)
        self.assertIsInstance(result, bool)

    # ─── 同步回调注入测试 ───

    def test_sync_callback_approved(self):
        """注入同步回调：批准"""
        manager = self._make_manager(non_interactive=False)
        manager.set_approval_callback(lambda op: True)
        op = self._make_medium_operation(manager)
        approved = manager.request_approval(op)
        self.assertTrue(approved)
        self.assertEqual(op["status"], "approved")
        self.assertEqual(op["approved_by"], "Callback")

    def test_sync_callback_rejected(self):
        """注入同步回调：拒绝"""
        manager = self._make_manager(non_interactive=False)
        manager.set_approval_callback(lambda op: False)
        op = self._make_medium_operation(manager)
        approved = manager.request_approval(op)
        self.assertFalse(approved)
        self.assertEqual(op["status"], "rejected")

    def test_sync_callback_exception_rejected(self):
        """同步回调抛异常：自动拒绝并记录 SystemError"""
        manager = self._make_manager(non_interactive=False)

        def bad_callback(op):
            raise RuntimeError("模拟回调失败")

        manager.set_approval_callback(bad_callback)
        op = self._make_medium_operation(manager)
        approved = manager.request_approval(op)
        self.assertFalse(approved)
        self.assertEqual(op["approved_by"], "SystemError")

    def test_clear_callback_restores_default(self):
        """清除回调后恢复默认行为（non_interactive 优先级高于默认）"""
        manager = self._make_manager(non_interactive=True)
        manager.set_approval_callback(lambda op: False)
        manager.clear_approval_callback()
        op = self._make_medium_operation(manager)
        # non_interactive 优先于默认回调，应自动批准
        approved = manager.request_approval(op)
        self.assertTrue(approved)
        self.assertEqual(op["status"], "auto_approved_non_interactive")

    # ─── 异步回调注入测试 ───

    def test_async_callback_approved(self):
        """注入异步回调：批准"""
        import asyncio

        manager = self._make_manager(non_interactive=False)

        async def async_approve(op):
            return True

        manager.set_approval_callback_async(async_approve)
        op = self._make_medium_operation(manager)

        loop = asyncio.new_event_loop()
        try:
            approved = loop.run_until_complete(manager.request_approval_async(op))
        finally:
            loop.close()

        self.assertTrue(approved)
        self.assertEqual(op["status"], "approved")
        self.assertEqual(op["approved_by"], "AsyncCallback")

    def test_async_callback_rejected(self):
        """注入异步回调：拒绝"""
        import asyncio

        manager = self._make_manager(non_interactive=False)

        async def async_reject(op):
            return False

        manager.set_approval_callback_async(async_reject)
        op = self._make_medium_operation(manager)

        loop = asyncio.new_event_loop()
        try:
            approved = loop.run_until_complete(manager.request_approval_async(op))
        finally:
            loop.close()

        self.assertFalse(approved)
        self.assertEqual(op["status"], "rejected")

    def test_async_callback_exception_rejected(self):
        """异步回调抛异常：自动拒绝"""
        import asyncio

        manager = self._make_manager(non_interactive=False)

        async def bad_async(op):
            raise ValueError("异步回调模拟失败")

        manager.set_approval_callback_async(bad_async)
        op = self._make_medium_operation(manager)

        loop = asyncio.new_event_loop()
        try:
            approved = loop.run_until_complete(manager.request_approval_async(op))
        finally:
            loop.close()

        self.assertFalse(approved)
        self.assertEqual(op["approved_by"], "SystemError")

    def test_async_low_risk_auto_approved(self):
        """异步入口：低风险自动批准"""
        import asyncio

        manager = self._make_manager(non_interactive=False)
        op = manager.register_operation(
            operation_id="async_low_001",
            operation_type="read_file",
            description="异步低风险",
            risk_level="low",
        )

        loop = asyncio.new_event_loop()
        try:
            approved = loop.run_until_complete(manager.request_approval_async(op))
        finally:
            loop.close()

        self.assertTrue(approved)
        self.assertEqual(op["status"], "auto_approved")

    def test_async_non_interactive_auto_approved(self):
        """异步入口：非交互模式自动批准"""
        import asyncio

        manager = self._make_manager(non_interactive=True)
        op = self._make_medium_operation(manager)

        loop = asyncio.new_event_loop()
        try:
            approved = loop.run_until_complete(manager.request_approval_async(op))
        finally:
            loop.close()

        self.assertTrue(approved)
        self.assertEqual(op["status"], "auto_approved_non_interactive")

    # ─── 注入类型校验 ───

    def test_set_callback_type_check(self):
        """set_approval_callback 类型校验"""
        manager = self._make_manager()
        with self.assertRaises(TypeError):
            manager.set_approval_callback("not_callable")

    def test_set_async_callback_type_check(self):
        """set_approval_callback_async 类型校验"""
        manager = self._make_manager()
        with self.assertRaises(TypeError):
            manager.set_approval_callback_async(123)

    # ─── 审批摘要与状态一致性 ───

    def test_approval_summary_after_async(self):
        """异步审批后摘要统计正确"""
        import asyncio

        manager = self._make_manager(non_interactive=False)

        async def async_approve(op):
            return True

        manager.set_approval_callback_async(async_approve)
        op = self._make_medium_operation(manager)

        loop = asyncio.new_event_loop()
        try:
            loop.run_until_complete(manager.request_approval_async(op))
        finally:
            loop.close()

        summary = manager.get_approval_summary()
        self.assertEqual(summary["total_operations"], 1)
        self.assertEqual(summary["approved"], 1)
        self.assertEqual(summary["approval_rate"], 100.0)


if __name__ == "__main__":
    unittest_main()
