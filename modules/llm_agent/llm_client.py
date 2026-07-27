"""LLM 客户端封装（自研 MIT，借鉴 MM-Agent 的 config 驱动 + 统一 resp 格式设计，未复制其代码/提示词）。

把 OpenAI / 兼容端点（DeepSeek、Moonshot、本地 vLLM 等）调用封装为 llm_call(req)->resp 接口，
供 LLMAgent 的 hybrid / pure_llm 模式使用。

配置优先级（高→低）：
  1. 环境变量 MATHMODEL_LLM_API_KEY / OPENAI_API_KEY 等
  2. 项目根 .env（简易解析，无需 python-dotenv）
  3. config/llm_config.local.yaml（用户本地，.gitignore 排除）
  4. config/llm_config.yaml（模板，入库）

安全：API key 仅本地读取，.env 与 local 配置被 .gitignore 排除，绝不上传。
"""

import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
_DEFAULT_CONFIG = _PROJECT_ROOT / "config" / "llm_config.yaml"
_LOCAL_CONFIG = _PROJECT_ROOT / "config" / "llm_config.local.yaml"
_DOTENV = _PROJECT_ROOT / ".env"


def _parse_dotenv(path: Path) -> Dict[str, str]:
    """简易 .env 解析（KEY=VALUE，忽略 # 注释与空行；不引入 python-dotenv 依赖）。"""
    out: Dict[str, str] = {}
    if not path.exists():
        return out
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        out[k.strip()] = v.strip().strip('"').strip("'")
    return out


def _load_yaml(path: Path) -> Dict[str, Any]:
    """读 YAML 配置（依赖 PyYAML；缺失或失败返回空 dict）。"""
    if not path.exists():
        return {}
    try:
        import yaml
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def load_llm_config(config_path: Optional[str] = None) -> Dict[str, Any]:
    """加载 LLM 配置（优先级：环境变量 > .env > local > 模板）。

    返回 {api_key, base_url, model, temperature, max_tokens}。
    api_key 为空字符串时，LLMClient 调用会抛明确 ValueError。
    """
    # 1. 模板默认
    cfg: Dict[str, Any] = _load_yaml(Path(config_path) if config_path else _DEFAULT_CONFIG)
    # 2. local 覆盖（非空值）
    local = _load_yaml(_LOCAL_CONFIG)
    for k, v in local.items():
        if v:
            cfg[k] = v
    # 3. .env 覆盖
    for k, v in _parse_dotenv(_DOTENV).items():
        if v:
            cfg[k] = v
    # 4. 环境变量最高
    api_key = (os.environ.get("MATHMODEL_LLM_API_KEY")
               or os.environ.get("OPENAI_API_KEY")
               or str(cfg.get("api_key") or ""))
    base_url = (os.environ.get("MATHMODEL_LLM_BASE_URL")
                or os.environ.get("OPENAI_BASE_URL")
                or str(cfg.get("base_url") or ""))
    model = os.environ.get("MATHMODEL_LLM_MODEL") or str(cfg.get("model") or "gpt-4o-mini")
    try:
        temperature = float(os.environ.get("MATHMODEL_LLM_TEMPERATURE")
                            or cfg.get("temperature", 0.2))
    except (TypeError, ValueError):
        temperature = 0.2
    try:
        max_tokens = int(os.environ.get("MATHMODEL_LLM_MAX_TOKENS")
                         or cfg.get("max_tokens", 2000))
    except (TypeError, ValueError):
        max_tokens = 2000
    return {
        "api_key": api_key, "base_url": base_url, "model": model,
        "temperature": temperature, "max_tokens": max_tokens,
    }


# role → system prompt（自研，未复制 MM-Agent 提示词）
_SYSTEM_PROMPTS: Dict[str, str] = {
    "model_selection": (
        "你是数学建模方法选择专家。根据题目文本与分析，从可用工具中选择最合适的建模方法。"
        "通过 tool_calls 返回选中的工具（每个工具含 name 与 arguments）。"
        "若信息不足以判断，不要调用工具，用 content 说明需要补充的信息。"
    ),
    "agent": (
        "你是数学建模自主 agent。通过反复调用可用工具完成建模：分析题目→选择方法→求解→反思。"
        "每轮可调用一个或多个工具，根据返回结果决定下一步。任务完成后用 content 给出总结，不再调用工具。"
    ),
    "default": "你是数学建模助手。根据用户请求，使用可用工具完成建模任务。",
}


class LLMClient:
    """LLM 客户端：封装 OpenAI/兼容端点调用为 llm_call(req)->resp 接口。

    借鉴 MM-Agent 的 config 驱动 + 统一 resp 格式设计，自研实现。
    resp 格式：{"tool_calls": [{"function": {"name": str, "arguments": str}}, ...], "content": str}
    与 LLMAgent._llm_model_selection / _pure_llm_loop 期望的契约一致。
    """

    def __init__(self, api_key: Optional[str] = None, base_url: Optional[str] = None,
                 model: Optional[str] = None, temperature: Optional[float] = None,
                 max_tokens: Optional[int] = None,
                 tool_schemas: Optional[List[Dict]] = None,
                 config_path: Optional[str] = None):
        # 任一核心字段未显式传入则从配置加载
        if api_key is None or base_url is None or model is None:
            cfg = load_llm_config(config_path)
            api_key = api_key if api_key is not None else cfg["api_key"]
            base_url = base_url if base_url is not None else cfg["base_url"]
            model = model if model is not None else cfg["model"]
            if temperature is None:
                temperature = cfg["temperature"]
            if max_tokens is None:
                max_tokens = cfg["max_tokens"]
        self.api_key = api_key or ""
        self.base_url = base_url or None
        self.model = model or "gpt-4o-mini"
        self.temperature = temperature if temperature is not None else 0.2
        self.max_tokens = max_tokens if max_tokens is not None else 2000
        self.tool_schemas = tool_schemas or []
        self._client = None  # 延迟创建，避免无 key 时 import 即报错

    def _get_client(self):
        """延迟创建 OpenAI 客户端（首次调用时）。"""
        if self._client is None:
            if not self.api_key:
                raise ValueError(
                    "未配置 LLM API key。请在 .env 设 MATHMODEL_LLM_API_KEY，"
                    "或在 config/llm_config.local.yaml 填 api_key，"
                    "或设环境变量 OPENAI_API_KEY。"
                )
            try:
                from openai import OpenAI
            except ImportError as e:
                raise ImportError("需安装 openai：pip install openai") from e
            kwargs: Dict[str, Any] = {"api_key": self.api_key}
            if self.base_url:
                kwargs["base_url"] = self.base_url
            self._client = OpenAI(**kwargs)
        return self._client

    def __call__(self, req: Dict[str, Any]) -> Dict[str, Any]:
        """llm_call 契约：req → {tool_calls, content}。

        req 字段：role / problem_text / problem_analysis / history。
        """
        client = self._get_client()
        role = req.get("role", "default")
        problem_text = req.get("problem_text", "")
        system_prompt = _SYSTEM_PROMPTS.get(role, _SYSTEM_PROMPTS["default"])

        user_content = problem_text
        if req.get("problem_analysis"):
            user_content += "\n\n[题目分析]" + json.dumps(
                req["problem_analysis"], ensure_ascii=False, default=str)
        if req.get("history"):
            for h in req["history"]:
                user_content += f"\n[已调用工具]{h.get('tool', '?')} 状态:{h.get('status', '?')}"

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content},
        ]
        kwargs: Dict[str, Any] = {
            "model": self.model, "messages": messages,
            "temperature": self.temperature, "max_tokens": self.max_tokens,
        }
        if self.tool_schemas:
            kwargs["tools"] = self.tool_schemas

        resp = client.chat.completions.create(**kwargs)
        choice = resp.choices[0].message
        tool_calls: List[Dict[str, Any]] = []
        if choice.tool_calls:
            for tc in choice.tool_calls:
                fn = tc.function
                tool_calls.append({
                    "function": {
                        "name": fn.name,
                        "arguments": fn.arguments or "{}",
                    }
                })
        return {"tool_calls": tool_calls, "content": choice.content}


def create_llm_client(workflow: Any = None, config_path: Optional[str] = None,
                     mode: str = "hybrid") -> Optional["LLMClient"]:
    """便捷工厂：从 workflow 拿 tool_schemas，构造 LLMClient。

    mode 为 rule_fallback 时返回 None（agent 走规则，无需 LLM）。
    """
    if mode == "rule_fallback":
        return None
    tool_schemas: List[Dict] = []
    try:
        from modules.tool_protocol import ToolProtocolAdapter
        adapter = ToolProtocolAdapter(wf=workflow)
        tool_schemas = adapter.generate_tool_schemas()
    except Exception:
        pass
    return LLMClient(tool_schemas=tool_schemas, config_path=config_path)


__all__ = ["LLMClient", "load_llm_config", "create_llm_client"]
