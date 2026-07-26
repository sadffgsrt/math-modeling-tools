# -*- coding: utf-8 -*-
"""
工作流缓存模块 (WorkflowCache)
提供简单的内存 + 文件双层缓存，用于缓存各阶段执行结果，避免重复计算。

设计目标：
- 接口与 main.py 用法保持一致：WorkflowCache(path) / get(key) / set(key, value) / has(key) / clear()
- 若构造时传入缓存目录（path），则自动持久化到磁盘（每个 key 一个 JSON 文件）
- 若未传入 path，则仅保留内存缓存（进程退出即丢失）
"""

import json
import re
import threading
from pathlib import Path
from typing import Any, Optional


def _safe_filename(key: str) -> str:
    """将缓存 key 转换为安全的文件名（仅保留字母、数字、下划线、点、连字符）。

    对于无法安全转换的字符（如中文、空格），统一替换为下划线，避免路径注入风险。
    """
    safe = re.sub(r"[^A-Za-z0-9_.\-]", "_", str(key))
    # 防止出现空文件名
    return safe or "_cache"


class WorkflowCache:
    """简单的内存 + 文件缓存。

    典型用法（与 main.py 保持一致）::

        cache = WorkflowCache(project_dir / "cache")
        cached = cache.get("stage_problem_analysis")
        if cached is None:
            cached = compute()
            cache.set("stage_problem_analysis", cached)
        cache.clear()
    """

    def __init__(self, cache_dir: Optional[Any] = None):
        # 缓存目录（可为 Path / str / None）
        self.cache_dir: Optional[Path] = Path(cache_dir) if cache_dir else None
        # 内存缓存层，保证即使不落盘也有基本能力
        self._memory: dict = {}
        # 写操作加锁，避免多线程并发写文件互相覆盖
        self._lock = threading.RLock()

        if self.cache_dir is not None:
            self.cache_dir.mkdir(parents=True, exist_ok=True)
            self._load_from_disk()

    # ─── 公共接口 ───

    def get(self, key: str) -> Any:
        """读取缓存。命中返回缓存值，未命中返回 None。"""
        with self._lock:
            return self._memory.get(key)

    def set(self, key: str, value: Any) -> None:
        """写入缓存（同时更新内存与磁盘）。"""
        with self._lock:
            self._memory[key] = value
            if self.cache_dir is not None:
                self._save_key(key, value)

    def has(self, key: str) -> bool:
        """判断 key 是否已缓存。"""
        with self._lock:
            return key in self._memory

    def clear(self) -> None:
        """清空全部缓存（内存 + 磁盘文件）。"""
        with self._lock:
            self._memory.clear()
            if self.cache_dir is not None and self.cache_dir.exists():
                for f in self.cache_dir.glob("*.json"):
                    try:
                        f.unlink()
                    except OSError:
                        # 个别文件删除失败不应中断整体清空
                        pass

    # ─── 内部持久化实现 ───

    def _load_from_disk(self) -> None:
        """启动时从缓存目录加载已有 JSON 缓存到内存（不覆盖后续内存写入）。"""
        if not self.cache_dir.exists():
            return
        for f in self.cache_dir.glob("*.json"):
            try:
                with open(f, "r", encoding="utf-8") as fh:
                    data = json.load(fh)
                # 文件结构: {"__key__": key, "__value__": value}
                key = data.get("__key__")
                if key is not None:
                    self._memory[key] = data.get("__value__")
            except (json.JSONDecodeError, OSError):
                # 损坏的缓存文件直接忽略，不影响启动
                continue

    def _save_key(self, key: str, value: Any) -> None:
        """将单个 key 持久化到磁盘（一个 key 一个 JSON 文件）。"""
        if self.cache_dir is None:
            return
        filename = _safe_filename(key) + ".json"
        path = self.cache_dir / filename
        payload = {"__key__": key, "__value__": value}
        try:
            with open(path, "w", encoding="utf-8") as fh:
                json.dump(payload, fh, ensure_ascii=False, indent=2, default=str)
        except (TypeError, OSError):
            # 无法序列化或写盘时不阻断主流程，仅内存保留
            pass
