"""
错误分类：把常见异常（LLM / 工具 / 网络）映射到有限种类，
供前端展示更精准的提示和 UI 图标。
"""
from __future__ import annotations

from dataclasses import dataclass


# 分类常量（前端也需要同步）
LLM_RATE_LIMIT       = "LLM_RATE_LIMIT"
LLM_CONTEXT_OVERFLOW = "LLM_CONTEXT_OVERFLOW"
LLM_AUTH             = "LLM_AUTH"
LLM_MODEL_NOT_FOUND  = "LLM_MODEL_NOT_FOUND"
LLM_TIMEOUT          = "LLM_TIMEOUT"
LLM_UNKNOWN          = "LLM_UNKNOWN"
TOOL_PERMISSION_DENIED = "TOOL_PERMISSION_DENIED"
TOOL_PATH_INVALID    = "TOOL_PATH_INVALID"
TOOL_EXEC_FAILED     = "TOOL_EXEC_FAILED"
TOOL_TIMEOUT         = "TOOL_TIMEOUT"


@dataclass
class ClassifiedError:
    category: str
    retriable: bool
    hint: str  # 前端可直接展示的简短建议


def classify_error(exc: BaseException) -> ClassifiedError:
    """
    尽力从异常类型 + 字符串识别分类。
    LiteLLM 的异常大多是 openai/anthropic SDK 原生异常或字符串消息。
    """
    msg = str(exc).lower()
    cls = type(exc).__name__.lower()

    # 认证
    if "invalid_api_key" in msg or "unauthorized" in msg or "401" in msg or "authentication" in msg:
        return ClassifiedError(LLM_AUTH, False,
            "API Key 无效或未授权，请在「设置 → 服务商」中检查此 Provider 的 Key")

    # 上下文溢出
    if "context_length_exceeded" in msg or "maximum context length" in msg or "context window" in msg:
        return ClassifiedError(LLM_CONTEXT_OVERFLOW, False,
            "对话上下文已超出模型窗口，请开启新会话或让 AutoCompact 触发（发一条空转消息）")

    # 模型不存在
    if "model_not_found" in msg or "does not exist" in msg or "invalid model" in msg or "not a valid model" in msg:
        return ClassifiedError(LLM_MODEL_NOT_FOUND, False,
            "模型 ID 不存在，请检查「设置 → 服务商」中该模型的 id 是否正确")

    # 速率限制
    if "rate_limit" in msg or "rate limit" in msg or "429" in msg or "too many requests" in msg:
        return ClassifiedError(LLM_RATE_LIMIT, True,
            "触发速率限制，稍后重试")

    # LLM 超时
    if "timeout" in msg and ("connect" in msg or "read" in msg or "request" in msg):
        return ClassifiedError(LLM_TIMEOUT, True,
            "LLM 请求超时，检查网络或稍后重试")

    # 工具 / 内置错误
    if "permissionerror" in cls or "permission denied" in msg or "已被禁用" in msg:
        return ClassifiedError(TOOL_PERMISSION_DENIED, False,
            "工具无权限或已被禁用")
    if "超出" in msg and "workspace" in msg or "sandbox_mode" in msg:
        return ClassifiedError(TOOL_PATH_INVALID, False,
            "路径超出当前会话工作目录")
    if "timeouterror" in cls or "asyncio.timeouterror" in cls:
        return ClassifiedError(TOOL_TIMEOUT, True,
            "工具执行超时")

    return ClassifiedError(LLM_UNKNOWN, False, str(exc)[:200])
