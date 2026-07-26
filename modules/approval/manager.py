"""
人工审批管理器 (ApprovalManager)
负责记录工作流中的各类操作、执行风险分级审批，并输出审批摘要与日志。

设计要点（与 main.py 调用保持一致）：
- 构造：ApprovalManager(project_dir, non_interactive=False) 或传入 workflow 对象
- register_operation(...) ：登记一个待审批操作，返回可变的操作 dict（初始 status="pending"）
- request_approval(op)    ：同步审批入口，返回 bool（True=批准，False=拒绝）
- request_approval_async(op)：异步审批入口（协程），返回 bool
- set_approval_callback / set_approval_callback_async / clear_approval_callback：注入自定义审批逻辑
- _save_approval_log()    ：将审批日志写入 project_dir/logs/approval_log.json（无目录则仅内存保留）
- get_approval_summary()  ：返回 dict，含 total_operations/approved/rejected/pending/executed/approval_rate

风险等级约定：
- low   ：任何模式下均自动批准（approved_by="System"）
- medium/high：非交互模式下自动批准（approved_by="NonInteractive"）；交互模式需经回调或人工确认

审批状态机：
    pending ──(批准)──> auto_approved / auto_approved_non_interactive / approved / AsyncCallback / Human
           ──(拒绝)──> rejected
    批准后执行成功 -> executed ；执行失败 -> failed
"""

import asyncio
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

# 视为「已获批准」的状态集合（批准后执行、执行成功均归类于此）
_APPROVED_STATUSES = {
    "auto_approved",
    "auto_approved_non_interactive",
    "approved",
    "executed",
}


class ApprovalManager:
    """人工审批管理器：操作登记、风险分级审批、摘要与日志持久化。"""

    def __init__(
        self,
        project_dir: Optional[Any] = None,
        non_interactive: bool = False,
        workflow: Optional[Any] = None,
    ) -> None:
        # 支持直接传入 workflow 对象（取其 project_dir 属性）
        if workflow is not None and project_dir is None:
            project_dir = getattr(workflow, "project_dir", None)

        self.project_dir: Optional[Path] = Path(project_dir) if project_dir else None
        self.non_interactive: bool = non_interactive

        # 所有登记过的操作（register_operation 返回的是列表中同一 dict 引用，
        # 因此 main.py 在审批通过后将其 status 改为 executed/failed 会同步反映到此处）
        self.operations: List[Dict[str, Any]] = []

        # 自定义审批回调（同步 / 异步）
        self._sync_callback: Optional[Callable[[Dict[str, Any]], bool]] = None
        self._async_callback: Optional[Callable[[Dict[str, Any]], Any]] = None

    # ─── 操作登记 ───

    def register_operation(
        self,
        operation_id: str,
        operation_type: str,
        description: str,
        risk_level: str,
        command: Optional[str] = None,
        source: Optional[str] = None,
    ) -> Dict[str, Any]:
        """登记一个待审批操作，返回可变的操作 dict（初始 status="pending"）。"""
        op: Dict[str, Any] = {
            "operation_id": operation_id,
            "operation_type": operation_type,
            "description": description,
            "risk_level": risk_level,
            "command": command,
            "source": source,
            "status": "pending",  # 初始：等待审批
            "approved_by": None,
            "registered_at": datetime.now().isoformat(),
        }
        self.operations.append(op)
        return op

    # ─── 审批状态写入辅助 ───

    @staticmethod
    def _set_status(op: Dict[str, Any], status: str, approved_by: Optional[str]) -> None:
        op["status"] = status
        op["approved_by"] = approved_by
        op["decided_at"] = datetime.now().isoformat()

    def approve(self, operation: Dict[str, Any], approved_by: str = "Manual") -> None:
        """便捷方法：直接标记某操作已批准（approved_by 可指定批准来源）。"""
        self._set_status(operation, "approved", approved_by)

    def reject(self, operation: Dict[str, Any], approved_by: str = "Manual") -> None:
        """便捷方法：直接标记某操作已拒绝。"""
        self._set_status(operation, "rejected", approved_by)

    # ─── 回调注入 ───

    def set_approval_callback(self, callback: Callable[[Dict[str, Any]], bool]) -> None:
        """注入同步审批回调。

        回调签名：(operation: dict) -> bool。非 callable 将抛出 TypeError。
        """
        if not callable(callback):
            raise TypeError("审批回调必须是可调用对象（callable）")
        self._sync_callback = callback

    def set_approval_callback_async(self, callback: Callable[[Dict[str, Any]], Any]) -> None:
        """注入异步审批回调。

        回调签名：(operation: dict) -> bool / Awaitable[bool]。非 callable 将抛出 TypeError。
        """
        if not callable(callback):
            raise TypeError("异步审批回调必须是可调用对象（callable）")
        self._async_callback = callback

    def clear_approval_callback(self) -> None:
        """清除全部注入的回调，恢复默认审批行为（non_interactive 优先于默认）。"""
        self._sync_callback = None
        self._async_callback = None

    # ─── 默认审批决策（无回调时） ───

    def _default_decision(self, op: Dict[str, Any]) -> bool:
        """默认审批策略（无回调时）。

        - 非交互模式 / 低风险：自动批准
        - 交互模式且非低风险：请求人工输入（EOFError 时按拒绝处理，fail-closed）
        """
        if self.non_interactive:
            self._set_status(op, "auto_approved_non_interactive", "NonInteractive")
            return True
        if op.get("risk_level") == "low":
            self._set_status(op, "auto_approved", "System")
            return True
        return self._interactive_prompt(op)

    def _interactive_prompt(self, op: Dict[str, Any]) -> bool:
        """交互模式下的提示输入（人工审批）。"""
        try:
            ans = input(
                f"审批请求 [{op.get('risk_level')}] {op.get('description')} (y/n) [y]: "
            ).strip().lower()
        except (EOFError, KeyboardInterrupt):
            ans = ""
        approved = ans in ("", "y", "yes")
        self._set_status(op, "approved" if approved else "rejected", "Human")
        return approved

    # ─── 同步审批入口 ───

    def request_approval(self, operation: Dict[str, Any]) -> bool:
        """同步审批入口。

        决策优先级：
        1. non_interactive          -> auto_approved_non_interactive
        2. risk_level == "low"      -> auto_approved (System)
        3. 同步回调已注入           -> 由回调返回值决定（异常 -> SystemError 拒绝）
        4. 异步回调已注入           -> 退化为同步调用（异常 -> SystemError 拒绝）
        5. 默认                      -> 交互提示 / 低风险自动
        """
        # 1 & 2：非交互 / 低风险自动批准（优先级最高）
        if self.non_interactive:
            self._set_status(operation, "auto_approved_non_interactive", "NonInteractive")
            return True
        if operation.get("risk_level") == "low":
            self._set_status(operation, "auto_approved", "System")
            return True

        # 3：同步回调
        if self._sync_callback is not None:
            try:
                result = self._sync_callback(operation)
            except Exception:  # noqa: BLE001 - 回调异常按系统错误拒绝
                self._set_status(operation, "rejected", "SystemError")
                return False
            if result:
                self._set_status(operation, "approved", "Callback")
                return True
            self._set_status(operation, "rejected", "Callback")
            return False

        # 4：异步回调（退化为同步调用）
        if self._async_callback is not None:
            try:
                result = self._async_callback(operation)
                if asyncio.iscoroutine(result):
                    result = asyncio.get_event_loop().run_until_complete(result)
            except Exception:  # noqa: BLE001
                self._set_status(operation, "rejected", "SystemError")
                return False
            if result:
                self._set_status(operation, "approved", "AsyncCallback")
                return True
            self._set_status(operation, "rejected", "AsyncCallback")
            return False

        # 5：默认策略
        return self._default_decision(operation)

    # ─── 异步审批入口 ───

    async def request_approval_async(self, operation: Dict[str, Any]) -> bool:
        """异步审批入口（协程）。决策逻辑与同步入口一致。"""
        if self.non_interactive:
            self._set_status(operation, "auto_approved_non_interactive", "NonInteractive")
            return True
        if operation.get("risk_level") == "low":
            self._set_status(operation, "auto_approved", "System")
            return True

        # 优先使用异步回调
        if self._async_callback is not None:
            try:
                result = await self._async_callback(operation)
            except Exception:  # noqa: BLE001
                self._set_status(operation, "rejected", "SystemError")
                return False
            if result:
                self._set_status(operation, "approved", "AsyncCallback")
                return True
            self._set_status(operation, "rejected", "AsyncCallback")
            return False

        # 退化为同步回调
        if self._sync_callback is not None:
            try:
                result = self._sync_callback(operation)
            except Exception:  # noqa: BLE001
                self._set_status(operation, "rejected", "SystemError")
                return False
            if result:
                self._set_status(operation, "approved", "Callback")
                return True
            self._set_status(operation, "rejected", "Callback")
            return False

        # 默认策略（交互提示在异步上下文中同步执行，可接受）
        return self._default_decision(operation)

    # ─── 摘要与日志持久化 ───

    def get_approval_summary(self) -> Dict[str, Any]:
        """返回审批摘要 dict。

        包含键：total_operations, approved, rejected, pending, executed, approval_rate
        （approval_rate 为百分比数值，如 100.0）。与 main.py 的 print_approval_summary 用法一致。
        """
        total = len(self.operations)
        approved = sum(1 for o in self.operations if o.get("status") in _APPROVED_STATUSES)
        rejected = sum(1 for o in self.operations if o.get("status") == "rejected")
        pending = sum(1 for o in self.operations if o.get("status") == "pending")
        executed = sum(1 for o in self.operations if o.get("status") == "executed")
        approval_rate = round(approved / total * 100, 2) if total else 0.0
        return {
            "total_operations": total,
            "approved": approved,
            "rejected": rejected,
            "pending": pending,
            "executed": executed,
            "approval_rate": approval_rate,
        }

    def _save_approval_log(self) -> None:
        """将审批日志写入 project_dir/logs/approval_log.json。

        若 project_dir 为 None 或目录不可写，则在内存中保留、不抛出。
        """
        if self.project_dir is None:
            return
        log_dir = self.project_dir / "logs"
        try:
            log_dir.mkdir(parents=True, exist_ok=True)
        except OSError:
            return
        log_path = log_dir / "approval_log.json"
        payload = {
            "updated_at": datetime.now().isoformat(),
            "summary": self.get_approval_summary(),
            "operations": self.operations,
        }
        try:
            with open(log_path, "w", encoding="utf-8") as fh:
                json.dump(payload, fh, ensure_ascii=False, indent=2, default=str)
        except OSError:
            # 写入失败不应中断主流程，仅保留内存状态
            pass
