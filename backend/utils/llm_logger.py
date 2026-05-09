"""LLM 调用日志：每轮请求/响应（含原生格式）按天写入 logs/llm-YYYY-MM-DD.log。

日志格式：JSON Lines（每行一个 JSON 对象），便于 grep / jq 处理。
"""
import json
from datetime import datetime
from pathlib import Path
from threading import Lock
from typing import Any

from loguru import logger


_LOGS_DIR = Path(__file__).resolve().parent.parent.parent / "logs"
_LOCK = Lock()
_REDACT_KEYS = {"api_key", "authorization", "Authorization"}


def _redact(obj: Any) -> Any:
    """递归脱敏：屏蔽 api_key / Authorization 等敏感字段。"""
    if isinstance(obj, dict):
        return {
            k: ("***REDACTED***" if k in _REDACT_KEYS and v else _redact(v))
            for k, v in obj.items()
        }
    if isinstance(obj, list):
        return [_redact(v) for v in obj]
    return obj


def _serialize_response(response: Any) -> Any:
    """将 LiteLLM ModelResponse 序列化为可 JSON 化的原生 dict。"""
    if response is None:
        return None
    # LiteLLM ModelResponse 是 pydantic 模型
    for attr in ("model_dump", "dict"):
        fn = getattr(response, attr, None)
        if callable(fn):
            try:
                return fn()
            except Exception:
                pass
    if isinstance(response, (dict, list, str, int, float, bool)):
        return response
    return str(response)


def log_llm_call(
    request: dict,
    response: Any,
    duration_ms: float,
    stream: bool = False,
    error: str | None = None,
) -> None:
    """同步追加一条 LLM 调用日志（线程安全）。

    Args:
        request: 传给 litellm 的 kwargs（messages/tools/model 等）
        response: 非流式为 LiteLLM 响应对象；流式为聚合后的 dict
        duration_ms: 调用耗时
        stream: 是否流式
        error: 出错信息（成功调用为 None）
    """
    try:
        _LOGS_DIR.mkdir(parents=True, exist_ok=True)
        today = datetime.now().strftime("%Y-%m-%d")
        log_file = _LOGS_DIR / f"llm-{today}.log"

        entry = {
            "ts": datetime.now().isoformat(timespec="milliseconds"),
            "stream": stream,
            "duration_ms": round(duration_ms, 2),
            "model": request.get("model"),
            "request": _redact(request),
            "response": _serialize_response(response),
        }
        if error:
            entry["error"] = error

        line = json.dumps(entry, ensure_ascii=False, default=str)
        with _LOCK:
            with open(log_file, "a", encoding="utf-8") as f:
                f.write(line + "\n")
    except Exception as e:
        # 日志失败绝不影响主流程
        logger.warning(f"写入 LLM 日志失败: {e}")
