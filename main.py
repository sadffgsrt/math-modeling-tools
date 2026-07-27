"""
数学建模竞赛工作流 - 主控脚本 (v3.4.2)
功能：整合所有模块，提供统一的入口和流程控制
核心原则：main.py是薄编排层，所有逻辑由模块文件实现
性能优化：延迟导入、缓存机制、并行处理
"""

import json
import sys
import logging
import time
import functools
from pathlib import Path
from typing import Dict, Optional, Any
from datetime import datetime

logger = logging.getLogger("mathmodeling")

# 添加当前目录到路径
sys.path.insert(0, str(Path(__file__).parent))

# 性能监控装饰器
def timing_decorator(func):
    """计时装饰器，记录函数执行时间"""
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        start_time = time.time()
        result = func(*args, **kwargs)
        end_time = time.time()
        execution_time = end_time - start_time
        # 获取logger
        logger = logging.getLogger("mathmodeling")
        logger.debug(f"[性能] {func.__name__} 执行耗时: {execution_time:.2f}秒")
        return result
    return wrapper

# 缓存机制 & 审批管理器再导出（保持向后兼容：from main import WorkflowCache/ApprovalManager）
# - WorkflowCache 已抽取到 modules/core/cache.py
# - ApprovalManager 已拆分到 modules/approval/manager.py
from modules.core.cache import WorkflowCache
from modules.approval import ApprovalManager
from modules.stage_planner import plan as _plan_stages, PLANS as _STAGE_PLANS


def setup_logger(project_dir: Path) -> logging.Logger:
    """配置日志系统"""
    logger = logging.getLogger("mathmodeling")
    logger.setLevel(logging.DEBUG)
    logger.handlers.clear()

    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(logging.Formatter("[%(levelname)s] %(message)s"))

    log_dir = project_dir / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    file_handler = logging.FileHandler(
        log_dir / f"workflow_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log",
        encoding='utf-8', delay=True
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))

    logger.addHandler(console_handler)
    logger.addHandler(file_handler)
    return logger


class MathModelingWorkflow:
    """数学建模工作流控制器 - 薄编排层"""

    STAGES = [
        "problem_analysis", "model_selection", "data_processing",
        "model_solving", "visualization", "validation", "paper_writing"
    ]

    # 阶段中文名映射（run_stage / run_all 共用，避免重复定义）
    _STAGE_NAMES = {
        "problem_analysis": "题目解析", "model_selection": "模型选型",
        "data_processing": "数据处理", "model_solving": "模型求解",
        "visualization": "结果可视化", "validation": "模型验证",
        "paper_writing": "论文撰写",
    }

    # 执行路径配置表（单一真相见 modules.stage_planner；此处引用该权威来源，避免再次硬编码）
    EXECUTION_PATHS = _STAGE_PLANS

    # 模块配置路径
    CONFIG_DIR = Path(__file__).parent / "config"

    def __init__(self, project_dir: str = "projects/.template",
                 no_cache: bool = False, non_interactive: bool = False):
        # 首次运行时自动创建默认模板目录，避免 FileNotFoundError
        if project_dir == "projects/.template":
            self.ensure_template_exists()
        self.project_dir = Path(project_dir)
        self.state_file = self.project_dir / "state" / "workflow_state.json"
        self.results_dir = self.project_dir / "results"
        self._ensure_directories()
        self.logger = setup_logger(self.project_dir)
        self.state = self._load_state()

        # 初始化缓存
        self.no_cache = no_cache
        if no_cache:
            self.cache = None
            self.logger.info("缓存已禁用")
        else:
            self.cache = WorkflowCache(self.project_dir / "cache")

        # 初始化人工审批管理器
        self.non_interactive = non_interactive
        self.gallery = False  # --gallery 开关：可视化后生成可浏览画廊
        self.approval_manager = ApprovalManager(self.project_dir, non_interactive=non_interactive)
        self.logger.info(f"人工审批管理器已初始化（{'非交互模式，自动批准' if non_interactive else '交互模式'}）")

        # 步骤 3 前置修复：在 __init__ 中创建 SolvingDispatcher 实例（供 ToolProtocolAdapter 访问）
        from modules.model_solving_dispatcher import SolvingDispatcher
        self.dispatcher = SolvingDispatcher(self)

        # 性能监控
        self.stage_times = {}
        self.total_start_time = None

        self.logger.info("数学建模工作流已初始化")
        self.logger.info(f"项目目录: {self.project_dir}")
        if not no_cache:
            self.logger.info(f"缓存目录: {self.project_dir / 'cache'}")

    def _ensure_directories(self):
        for d in ["problem_files", "raw_data", "processed_data",
                   "models", "results", "figures", "paper", "state", "logs"]:
            (self.project_dir / d).mkdir(parents=True, exist_ok=True)

    @classmethod
    def ensure_template_exists(cls) -> Path:
        """确保 projects/.template 模板目录存在；首次运行若缺失则自动创建，避免 FileNotFoundError。"""
        template_dir = Path(__file__).parent / "projects" / ".template"
        if not template_dir.exists():
            for d in ["problem_files", "raw_data", "processed_data",
                      "models", "results", "figures", "paper", "state", "logs"]:
                (template_dir / d).mkdir(parents=True, exist_ok=True)
            # 写入占位 README 指导用户放置题目文件
            (template_dir / "problem_files" / "README.md").write_text(
                "# 题目文件目录\n\n请将竞赛题目文件（PDF / TXT / DOCX）放入此目录后运行：\n    python main.py --all\n",
                encoding="utf-8")
        return template_dir

    def _load_state(self) -> Dict:
        if self.state_file.exists():
            with open(self.state_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {
            "project_id": "", "project_name": "",
            "current_stage": "problem_analysis",
            "stages": {s: {"status": "pending"} for s in self.STAGES},
            "created_at": datetime.now().isoformat()
        }

    def _load_config(self) -> Dict:
        """加载工作流配置文件"""
        config_file = self.CONFIG_DIR / "workflow_config.yaml"
        if config_file.exists():
            try:
                import yaml
                with open(config_file, 'r', encoding='utf-8') as f:
                    return yaml.safe_load(f) or {}
            except Exception as e:
                self.logger.warning(f"加载配置文件失败: {e}")
        return {}

    def _save_state(self):
        self.state["updated_at"] = datetime.now().isoformat()
        with open(self.state_file, 'w', encoding='utf-8') as f:
            json.dump(self.state, f, ensure_ascii=False, indent=2)

    def _load_result(self, filename: str) -> Optional[Dict]:
        path = self.results_dir / filename
        if path.exists():
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
        return None

    def _save_result(self, filename: str, data: Any):
        self.results_dir.mkdir(parents=True, exist_ok=True)
        with open(self.results_dir / filename, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2, default=str)

    # ─── 阶段调度 ───

    @timing_decorator
    def run_stage(self, stage: str, **kwargs) -> Dict:
        self.logger.info(f"{'='*60}")
        self.logger.info(f"开始执行阶段: {stage}")

        # 检查缓存
        cache_key = f"stage_{stage}"
        if not self.no_cache and self.cache:
            cached_result = self.cache.get(cache_key)
            if cached_result and not kwargs.get("force_refresh", False):
                self.logger.info(f"阶段 {stage} 使用缓存结果")
                return cached_result

        # 注册操作并请求审批（_STAGE_NAMES 见类属性）
        operation = self.approval_manager.register_operation(
            operation_id=f"stage_{stage}_{datetime.now().strftime('%Y%m%d%H%M%S')}",
            operation_type="stage_execution",
            description=f"执行{self._STAGE_NAMES.get(stage, stage)}阶段",
            risk_level="medium",
            command=f"workflow.run_stage('{stage}')",
            source="AI"
        )
        if not self.approval_manager.request_approval(operation):
            raise PermissionError(f"阶段 {stage} 未获人工批准，无法执行")

        self.state["current_stage"] = stage
        self.state["stages"][stage] = {"status": "running", "started_at": datetime.now().isoformat()}
        stage_start_time = time.time()

        try:
            # getattr 反射调用 _run_{stage} 薄包装（包装内再委托到 modules/NN_xxx/runner.py）
            result = getattr(self, f"_run_{stage}")(**kwargs)

            # 缓存结果
            if not self.no_cache and self.cache:
                self.cache.set(cache_key, result)

            self.state["stages"][stage] = {
                "status": "completed",
                "started_at": self.state["stages"][stage].get("started_at"),
                "completed_at": datetime.now().isoformat(),
            }
            self._save_state()

            stage_time = time.time() - stage_start_time
            self.stage_times[stage] = stage_time
            self.logger.info(f"阶段 {stage} 执行完成! 耗时: {stage_time:.2f}秒")

            operation["status"] = "executed"
            operation["executed_at"] = datetime.now().isoformat()
            self.approval_manager._save_approval_log()
            return result

        except Exception as e:
            self.state["stages"][stage] = {"status": "failed", "error": str(e)}
            self._save_state()
            self.logger.error(f"阶段 {stage} 执行失败: {e}")
            operation["status"] = "failed"
            operation["executed_at"] = datetime.now().isoformat()
            operation["execution_result"] = {"success": False, "error": str(e)}
            self.approval_manager._save_approval_log()
            raise

    def get_approval_summary(self) -> Dict:
        """获取审批摘要"""
        return self.approval_manager.get_approval_summary()

    def print_approval_summary(self):
        """输出审批摘要（经统一 logger 输出，保持与全流程一致）"""
        s = self.get_approval_summary()
        self.logger.info(f"\n{'='*60}\n审批摘要\n{'='*60}")
        self.logger.info(f"总操作数: {s['total_operations']}  已批准: {s['approved']}  已拒绝: {s['rejected']}")
        self.logger.info(f"待审批: {s['pending']}  已执行: {s['executed']}  批准率: {s['approval_rate']}%")
        self.logger.info(f"{'='*60}")

    # ─── 阶段运行器（薄包装 → modules/NN_xxx/runner.py）───
    # run_stage 通过 getattr(self, f"_run_{stage}") 反射调用下列方法

    def _run_problem_analysis(self, **kwargs) -> Dict:
        from modules.problem_analysis_runner import run_problem_analysis
        return run_problem_analysis(self, **kwargs)

    def _run_model_selection(self, **kwargs) -> Dict:
        from modules.model_selection_runner import run_model_selection
        return run_model_selection(self, **kwargs)

    def _run_data_processing(self, **kwargs) -> Dict:
        from modules.data_processing_runner import run_data_processing
        return run_data_processing(self, **kwargs)

    def _check_model_implemented(self, model_id: str, model_name: str) -> None:
        """校验所选模型是否已在 model_factory 中实现（薄包装）"""
        from modules.model_solving_runner import check_model_implemented
        return check_model_implemented(self, model_id, model_name)

    def _run_model_solving(self, **kwargs) -> Dict:
        from modules.model_solving_runner import run_model_solving
        return run_model_solving(self, **kwargs)

    def _maybe_build_gallery(self, result: Dict) -> None:
        """若启用 --gallery，基于可视化结果生成可浏览的 HTML 画廊。

        画廊写入与图表相同的 output_dir，Web UI 的 /gallery 可直接浏览/下载。
        """
        if not getattr(self, "gallery", False):
            return
        meta = result.get("figures_meta") or []
        if not meta:
            self.logger.warning("无图表元信息，跳过画廊生成")
            return
        try:
            from datetime import datetime
            from modules.visualization.visualizer import VisualizationResult
            from modules.visualization.visualization_ops import VisualizationOps
            res = VisualizationResult(
                result_id=result.get("result_id", "VZ"),
                figures=meta,
                figure_paths=result.get("figures", []) or [m.get("path") for m in meta],
                created_at=datetime.now().isoformat(),
                metadata={
                    "total_figures": result.get("figures_count", len(meta)),
                    "output_dir": result.get("output_dir", "figures"),
                },
            )
            out = result.get("output_dir", "figures")
            gpath = VisualizationOps(output_dir=out).build_gallery(
                res, title="建模结果可视化画廊", output_dir=out)
            self.logger.info(f"可视化画廊已生成: {gpath}")
        except Exception as e:
            self.logger.warning(f"画廊生成失败（不影响主流程）: {e}")

    def _run_visualization(self, **kwargs) -> Dict:
        """可视化阶段 - 人工协作模式（薄包装）"""
        from modules.visualization_runner import run_visualization
        result = run_visualization(self, **kwargs)
        self._maybe_build_gallery(result)
        return result

    def _run_visualization_interactive(self) -> Dict:
        """可视化阶段 - 人工全程参与协作模式（薄包装）"""
        from modules.visualization_runner import run_visualization_interactive
        result = run_visualization_interactive(self)
        self._maybe_build_gallery(result)
        return result

    def _run_validation(self, **kwargs) -> Dict:
        from modules.validation_runner import run_validation
        return run_validation(self, **kwargs)

    def _run_paper_writing(self, **kwargs) -> Dict:
        from modules.paper_writing_runner import run_paper_writing
        return run_paper_writing(self, **kwargs)

    # ─── 公共方法 ───

    def _confirm(self, prompt: str, default: str = "y") -> str:
        """统一的 input() 交互封装，处理 EOFError 与默认值（简化交互逻辑）。"""
        try:
            return input(prompt).strip().lower() or default
        except EOFError:
            return default

    def _print_stage_summary(self, stage_name: str, result: Dict) -> None:
        """输出阶段执行结果摘要（经统一 logger；仅基本类型 / 列表 / dict 的简要信息）。"""
        if not isinstance(result, dict):
            return
        self.logger.info(f"\n阶段 '{stage_name}' 执行完成:")
        for key, value in result.items():
            if isinstance(value, (str, int, float, bool)):
                self.logger.info(f"  {key}: {value}")
            elif isinstance(value, list):
                self.logger.info(f"  {key}: {len(value)} 项")
            elif isinstance(value, dict):
                self.logger.info(f"  {key}: {len(value)} 个键")

    def run_all(self) -> Dict:
        """
        运行所有阶段 - 智能问题分析模式
        前置分析 → 动态模型匹配 → 多分支执行路径

        Returns:
            Dict: 各阶段执行结果
        """
        results = {}
        self.logger.info(f"\n{'='*60}\n数学建模竞赛工作流 - 智能问题分析模式\n{'='*60}")
        self.logger.info(f"项目目录: {self.project_dir}  共 {len(self.STAGES)} 个阶段")
        self.logger.info(f"说明: 前置分析 → 动态模型匹配 → 多分支执行路径\n{'='*60}\n")

        # 阶段1: 前置分析
        self.logger.info(f"\n{'='*60}\n【前置分析阶段】\n{'='*60}")
        try:
            results["problem_analysis"] = self.run_stage("problem_analysis")
            analysis = results["problem_analysis"]
            self.logger.info(f"\n分析报告: 类型={analysis.get('problem_type', '未知')} "
                             f"复杂度={analysis.get('difficulty', '未知')} "
                             f"变量={analysis.get('variables_count', 0)} 约束={analysis.get('constraints_count', 0)}")
            if self._confirm("\n请确认分析结果是否正确？(y/n): ", "y") == 'n':
                self.logger.error("请修改题目文件后重新运行")
                return results
        except Exception as e:
            self.logger.error(f"前置分析失败: {e}")
            results["problem_analysis"] = {"error": str(e)}
            return results

        # 阶段2: 动态模型匹配
        self.logger.info(f"\n{'='*60}\n【动态模型匹配阶段】\n{'='*60}")
        try:
            results["model_selection"] = self.run_stage("model_selection")
            sel = results["model_selection"]
            self.logger.info(f"\n模型选择: {sel.get('selected_model', '未知')} 适配分数={sel.get('suitability_score', 0)}")
            if self._confirm("\n请确认模型选择是否合适？(y/n): ", "y") == 'n':
                self.logger.info("将跳过模型选型，使用默认模型")
                results["model_selection"] = {"selected_model": "线性回归", "status": "skipped"}
        except Exception as e:
            self.logger.error(f"模型匹配失败: {e}")
            results["model_selection"] = {"error": str(e)}
            return results

        # 阶段3-7: 多分支执行路径
        self.logger.info(f"\n{'='*60}\n【执行阶段】\n{'='*60}")
        problem_type = results.get("problem_analysis", {}).get("problem_type", "comprehensive")
        complexity = results.get("problem_analysis", {}).get("difficulty", "medium")
        execution_path = _plan_stages(problem_type)
        self.logger.info(f"\n执行路径: {problem_type} + {complexity}复杂度  共 {len(execution_path)} 个阶段")

        for stage in execution_path:
            stage_name = self._STAGE_NAMES.get(stage, stage)
            self.logger.info(f"\n{'-'*60}\n阶段: {stage_name} ({stage})\n{'-'*60}")
            if results:
                prev_stage = list(results.keys())[-1]
                if isinstance(results[prev_stage], dict) and "error" not in results[prev_stage]:
                    self.logger.info(f"上一阶段 '{self._STAGE_NAMES.get(prev_stage, prev_stage)}' 执行成功")

            choice = self._confirm(f"\n是否执行阶段 '{stage_name}'？(y/n/q): ", "y")
            if choice == 'q':
                self.logger.info("用户中止工作流")
                break
            if choice == 'n':
                self.logger.info(f"跳过阶段 '{stage_name}'")
                results[stage] = {"status": "skipped", "message": "用户跳过"}
                continue

            try:
                # 可视化阶段走交互式入口；其余阶段走标准调度（带审批/缓存）
                if stage == "visualization":
                    results[stage] = self._run_visualization_interactive()
                else:
                    results[stage] = self.run_stage(stage)
                self._print_stage_summary(stage_name, results[stage])
            except Exception as e:
                self.logger.error(f"阶段 {stage} 失败: {e}")
                results[stage] = {"error": str(e)}
                self.logger.error(f"\n[错误] 阶段 '{stage_name}' 执行失败: {e}")
                if self._confirm("是否继续执行下一阶段？(y/n): ", "n") != 'y':
                    break

        self.logger.info(f"\n{'='*60}\n工作流执行完成!\n{'='*60}")
        if self.stage_times:
            total_time = sum(self.stage_times.values())
            self.logger.info(f"\n性能统计:\n{'-'*40}")
            for stage, t in self.stage_times.items():
                self.logger.info(f"  {stage}: {t:.2f}秒")
            self.logger.info(f"{'-'*40}\n  总耗时: {total_time:.2f}秒  平均: {total_time/len(self.stage_times):.2f}秒")
            cache_dir = self.project_dir / "cache"
            cache_files = list(cache_dir.glob("*.json")) if cache_dir.exists() else []
            self.logger.info(f"  缓存文件数: {len(cache_files)}")

        self.logger.info("工作流执行完成!")
        self.logger.info(f"性能统计: {self.stage_times}")
        return results

    def get_status(self) -> Dict:
        return {
            "project_dir": str(self.project_dir),
            "current_stage": self.state.get("current_stage"),
            "stages": {n: i.get("status") for n, i in self.state.get("stages", {}).items()}
        }

    def get_performance_report(self) -> Dict:
        """获取性能报告"""
        cache_files = list((self.project_dir / "cache").glob("*.json")) if (self.project_dir / "cache").exists() else []
        total = sum(self.stage_times.values()) if self.stage_times else 0
        return {
            "stage_times": self.stage_times,
            "total_time": total,
            "average_time": total / len(self.stage_times) if self.stage_times else 0,
            "cache_files_count": len(cache_files),
            "cache_size_mb": sum(f.stat().st_size for f in cache_files) / (1024 * 1024) if cache_files else 0,
        }

    def clear_cache(self):
        """清空缓存"""
        self.cache.clear()
        self.logger.info("缓存已清空")

    def print_status(self):
        status = self.get_status()
        self.logger.info(f"项目目录: {status['project_dir']}")
        self.logger.info(f"当前阶段: {status['current_stage']}")
        for stage, s in status['stages'].items():
            emoji = {"pending": "[待定]", "running": "[运行中]", "completed": "[完成]", "failed": "[失败]"}.get(s, "[?]")
            self.logger.info(f"  {emoji} {stage}: {s}")


def main():
    import argparse
    parser = argparse.ArgumentParser(description="数学建模竞赛工作流")
    parser.add_argument("--project", default="projects/.template", help="项目目录")
    parser.add_argument("--stage", help="要运行的阶段")
    parser.add_argument("--all", action="store_true", help="运行所有阶段（人工参与模式）")
    parser.add_argument("--status", action="store_true", help="显示状态")
    parser.add_argument("--performance", action="store_true", help="显示性能报告")
    parser.add_argument("--clear-cache", action="store_true", help="清空缓存")
    parser.add_argument("--no-cache", action="store_true", help="禁用缓存，重新执行所有阶段")
    parser.add_argument("--non-interactive", action="store_true",
                        help="非交互模式：所有审批自动批准（用于测试/CI 环境）")
    parser.add_argument("--gallery", action="store_true",
                        help="可视化阶段完成后生成可浏览的 HTML 画廊（经 Web UI 的 /gallery 查看）")
    parser.add_argument("--agent", action="store_true",
                        help="Agent 模式：题目→方法选择→求解→反思自主运行")
    parser.add_argument("--multi-turn", action="store_true",
                        help="Agent 多轮对话模式（需配合 --agent）：在对话上下文中连续多轮建模")
    parser.add_argument("--mode", default="rule_fallback",
                        choices=["rule_fallback", "hybrid", "pure_llm"],
                        help="Agent 模式（hybrid/pure_llm 需配置 LLM API key）")
    parser.add_argument("--problem", default=None,
                        help="题目文本（agent 模式；未指定则交互输入）")
    parser.add_argument("--llm-config", default=None,
                        help="LLM 配置文件路径（默认 config/llm_config.yaml）")
    parser.add_argument("--data-path", default=None,
                        help="数据文件路径（agent 求解时使用）")
    parser.add_argument("--mcp", action="store_true",
                        help="启动 MCP 服务，外部 agent 可经 /tools 调用平台 53 个工具")
    parser.add_argument("--mcp-port", type=int, default=8090, help="MCP 服务端口")
    parser.add_argument("--mcp-key", default=None, help="MCP 认证 key（可选）")
    args = parser.parse_args()

    wf = MathModelingWorkflow(args.project, no_cache=args.no_cache,
                              non_interactive=args.non_interactive)
    wf.gallery = args.gallery
    if args.agent:
        from modules.llm_agent.agent import create_llm_agent
        from modules.llm_agent.llm_client import create_llm_client

        def _log_agent_result(result):
            logger.info(f"\n{'='*40}\nAgent 完成\n{'='*40}")
            logger.info(f"模式: {result['mode']}  成功: {result['success']}")
            logger.info(f"工具调用: {len(result.get('tool_calls', []))} 次")
            for tc in result.get("tool_calls", []):
                logger.info(f"  - {tc.get('tool_name', tc.get('name', '?'))}: {tc.get('status', '?')}")
            refl = result.get("reflection", {})
            logger.info(f"反思综合分: {refl.get('overall_score', '?')}/10  方法: {refl.get('evaluation_method', '?')}")
            crit = refl.get("llm_critique", {})
            if crit.get("available"):
                logger.info(f"LLM 深度 critique: {crit.get('critique', '')[:200]}")
            for ap in result.get("approvals", []):
                logger.info(f"审批[{ap.get('step')}] {ap.get('status')} (by {ap.get('approved_by')})")

        llm_client = create_llm_client(wf, config_path=args.llm_config, mode=args.mode)
        agent = create_llm_agent(wf, mode=args.mode, llm_call=llm_client)

        if args.multi_turn:
            print("进入多轮对话模式（输入 exit/quit 或空行退出）")
            problem = args.problem or ""
            if not problem:
                try:
                    problem = input("第1轮 题目/需求: ").strip()
                except EOFError:
                    problem = ""
            turn = 1
            while problem:
                result = agent.chat(problem, data_path=args.data_path)
                _log_agent_result(result)
                try:
                    problem = input(f"第{turn + 1}轮 (exit 退出): ").strip()
                except EOFError:
                    problem = ""
                if problem.lower() in ("exit", "quit"):
                    break
                turn += 1
            return

        problem = args.problem
        if not problem:
            try:
                problem = input("请输入题目文本: ").strip()
            except EOFError:
                problem = ""
        if not problem:
            logger.error("题目文本不能为空（用 --problem 指定）")
        else:
            result = agent.run(problem, data_path=args.data_path)
            _log_agent_result(result)
        return
    if args.mcp:
        from modules.mcp_server import create_mcp_server
        server = create_mcp_server(wf, host="127.0.0.1",
                                    port=args.mcp_port, api_key=args.mcp_key)
        server.start_background()
        logger.info(f"\n{'='*40}\nMCP 服务已启动\n{'='*40}")
        logger.info(f"地址: http://127.0.0.1:{args.mcp_port}")
        logger.info(f"端点: GET /tools | GET /tools/<name> | POST /tools/<name>/call | POST /mcp")
        logger.info(f"工具数: {len(server.list_tools())}")
        if args.mcp_key:
            logger.info("认证: 已启用（请求需带 Authorization: Bearer <key> 或 ?api_key=<key>）")
        logger.info("按 Ctrl+C 退出...")
        import time
        try:
            while server.is_running():
                time.sleep(1)
        except KeyboardInterrupt:
            logger.info("\n正在停止 MCP 服务...")
            server.stop()
        return
    if args.status:
        wf.print_status()
    elif args.performance:
        report = wf.get_performance_report()
        logger.info(f"\n性能报告:\n{'='*40}")
        logger.info(f"总耗时: {report['total_time']:.2f}秒  平均每阶段: {report['average_time']:.2f}秒")
        logger.info(f"缓存文件数: {report['cache_files_count']}  缓存大小: {report['cache_size_mb']:.2f}MB")
        logger.info(f"\n各阶段耗时:")
        for stage, t in report['stage_times'].items():
            logger.info(f"  {stage}: {t:.2f}秒")
    elif args.clear_cache:
        wf.clear_cache()
    elif args.all:
        wf.run_all()
    elif args.stage:
        wf.run_stage(args.stage)
    else:
        wf.print_status()


if __name__ == "__main__":
    main()
