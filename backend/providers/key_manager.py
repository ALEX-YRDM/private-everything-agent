"""
Provider API Key 管理：
1. 对已知 provider（openai/anthropic/...），写入 os.environ 供 LiteLLM 自动读取。
2. 同时维护内存注册表（_registry），供自定义 / 未知 provider 在调用时直接注入 api_key+api_base。
"""
import os
from loguru import logger

# provider 名称 → LiteLLM 所需的环境变量名
PROVIDER_ENV_MAP: dict[str, str] = {
    "openai":        "OPENAI_API_KEY",
    "anthropic":     "ANTHROPIC_API_KEY",
    "deepseek":      "DEEPSEEK_API_KEY",
    "gemini":        "GEMINI_API_KEY",
    "groq":          "GROQ_API_KEY",
    "mistral":       "MISTRAL_API_KEY",
    "together_ai":   "TOGETHERAI_API_KEY",
    "openrouter":    "OPENROUTER_API_KEY",
    "xai":           "XAI_API_KEY",
    "perplexity":    "PERPLEXITYAI_API_KEY",
    "cohere":        "COHERE_API_KEY",
    "azure":         "AZURE_API_KEY",
    "volcengine":    "VOLCENGINE_API_KEY",
    "moonshot":      "MOONSHOT_API_KEY",
    "zai":       "ZAI_API_KEY",
    "dashscope":     "DASHSCOPE_API_KEY",
    "minimax":       "MINIMAX_API_KEY",
}

# provider → api_base 环境变量
PROVIDER_BASE_ENV_MAP: dict[str, str] = {
    "openai":   "OPENAI_API_BASE",
    "azure":    "AZURE_API_BASE",
    "ollama":   "OLLAMA_API_BASE",
}

# 内存注册表：provider → {api_key, api_base}
# 所有 provider 都写入此表，方便 LiteLLM 调用时直接注入
_registry: dict[str, dict] = {}


def extract_provider(model_id: str) -> str:
    """
    从 model_id 提取 provider 前缀。
    'openai/gpt-4o' → 'openai'，'deepseek/deepseek-chat' → 'deepseek'，
    'gpt-4o'（无前缀）→ 'openai'
    """
    if "/" in model_id:
        return model_id.split("/")[0].lower()
    return "openai"


def apply_provider_key(provider: str, api_key: str | None, api_base: str | None):
    """
    写入 os.environ（已知 provider）并更新内存注册表（全部 provider）。
    两者同时维护，确保已知和自定义 provider 都能正确传 key。
    """
    # 写入内存注册表（所有 provider 都记录，含自定义）
    _registry[provider] = {
        "api_key":  api_key or None,
        "api_base": api_base or None,
    }

    if api_key:
        env_var = PROVIDER_ENV_MAP.get(provider)
        if env_var:
            os.environ[env_var] = api_key
            logger.info(f"已应用 {provider} API Key → {env_var}")
        else:
            logger.info(f"自定义 provider '{provider}' API Key 已写入注册表（非标准 provider）")

    if api_base:
        base_env = PROVIDER_BASE_ENV_MAP.get(provider)
        if base_env:
            os.environ[base_env] = api_base
            logger.info(f"已应用 {provider} API Base → {base_env}")


def get_provider_credentials(model_id: str) -> dict:
    """
    根据 model_id 前缀查询内存注册表，返回 {api_key, api_base}。
    供 LiteLLMProvider 在每次调用时直接注入，优先于环境变量。
    对于已知 provider 也注入，确保自定义 base URL 生效。
    """
    provider = extract_provider(model_id)
    creds = _registry.get(provider, {})
    return {
        "api_key":  creds.get("api_key"),
        "api_base": creds.get("api_base"),
    }


async def apply_all_provider_keys(db_manager) -> None:
    """从数据库加载所有 provider keys，写入 os.environ 并填充内存注册表。"""
    keys = await db_manager.list_provider_keys()
    for row in keys:
        if row.get("api_key") or row.get("api_base"):
            apply_provider_key(row["provider"], row.get("api_key"), row.get("api_base"))
    logger.info(f"已加载 {len(keys)} 个 Provider Key 配置")
