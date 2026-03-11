"""
Provider API Key 管理：将数据库中的 provider_keys 应用到环境变量，
LiteLLM 会自动从 os.environ 读取各服务商的 API Key。
"""
import os
from loguru import logger

# provider 名称 → LiteLLM 所需的环境变量名
# 参考：https://docs.litellm.ai/docs/providers
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
    "zhipuai":       "ZHIPUAI_API_KEY",
    "baidu":         "QIANFAN_AK",
}

# provider → api_base 环境变量（部分需要）
PROVIDER_BASE_ENV_MAP: dict[str, str] = {
    "openai":   "OPENAI_API_BASE",
    "azure":    "AZURE_API_BASE",
    "ollama":   "OLLAMA_API_BASE",
    "custom":   "OPENAI_API_BASE",
}


def extract_provider(model_id: str) -> str:
    """
    从 model_id 提取 provider。
    例：'openai/gpt-4o' → 'openai'，'deepseek/deepseek-chat' → 'deepseek'
    """
    if "/" in model_id:
        return model_id.split("/")[0].lower()
    # 无前缀的视为 openai 兼容
    return "openai"


def apply_provider_key(provider: str, api_key: str | None, api_base: str | None):
    """将单个 provider 的 Key 写入 os.environ，LiteLLM 自动生效。"""
    if api_key:
        env_var = PROVIDER_ENV_MAP.get(provider)
        if env_var:
            os.environ[env_var] = api_key
            logger.info(f"已应用 {provider} API Key → {env_var}")
        else:
            # 未知 provider：尝试通用 key（适用于 OpenAI 兼容服务）
            logger.warning(f"未知 provider '{provider}'，API Key 未设置")

    if api_base:
        base_env = PROVIDER_BASE_ENV_MAP.get(provider)
        if base_env:
            os.environ[base_env] = api_base
            logger.info(f"已应用 {provider} API Base → {base_env}")


async def apply_all_provider_keys(db_manager) -> None:
    """从数据库加载所有 provider keys 并写入环境变量。"""
    keys = await db_manager.list_provider_keys()
    for row in keys:
        if row.get("api_key") or row.get("api_base"):
            apply_provider_key(row["provider"], row.get("api_key"), row.get("api_base"))
    logger.info(f"已加载 {len(keys)} 个 Provider Key 配置")
