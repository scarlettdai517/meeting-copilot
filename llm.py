import os
from dotenv import load_dotenv

load_dotenv()

# 默认使用的提供商（当 UI 未选择时从环境变量读）
def _default_provider() -> str:
    return os.getenv("LLM_PROVIDER", "openai")


def chat_json(
    system_prompt: str,
    user_prompt: str,
    temperature: float = 0.2,
    provider: str | None = None,
) -> str:
    """
    统一对话接口：根据 provider 调用对应模型，返回助手回复文本。
    provider 为空时使用环境变量 LLM_PROVIDER（默认 openai）。
    """
    from providers import chat_completion

    pid = (provider or _default_provider()).strip().lower()
    return chat_completion(
        provider_id=pid,
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        temperature=temperature,
    )


# 兼容旧代码：部分脚本可能直接调 get_client
def get_client():
    """返回 OpenAI 客户端（仅当 provider=openai 时使用）。其他场景请用 chat_json(provider=...)。"""
    from openai import OpenAI

    api_key = os.getenv("OPENAI_API_KEY")
    base_url = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY not found. Put it in .env")
    return OpenAI(api_key=api_key, base_url=base_url)
