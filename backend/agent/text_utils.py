"""Agent 相关的纯函数工具（不依赖 Agent/Tool 模块），供多处复用。"""
from __future__ import annotations

import re


_THINK_RE = re.compile(r"<think>.*?</think>", re.DOTALL | re.IGNORECASE)
_THINK_OPEN_RE = re.compile(r"<think>.*", re.DOTALL | re.IGNORECASE)


def strip_think_tags(text: str) -> str:
    """
    剥掉部分模型（DeepSeek-R1、GLM-Z1 等）写在 content 里的 <think>...</think> 块。
    - 完整成对的直接删；
    - 只有开标签没有闭标签（截断/未收尾）时，从 <think> 开始到末尾全丢；
    - 也兼容裸露的 </think>（去掉）。
    """
    if not text:
        return text
    low = text.lower()
    if "<think>" not in low and "</think>" not in low:
        return text
    stripped = _THINK_RE.sub("", text)
    stripped = _THINK_OPEN_RE.sub("", stripped)
    stripped = re.sub(r"</think>", "", stripped, flags=re.IGNORECASE)
    return stripped.strip()
