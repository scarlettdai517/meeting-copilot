"""
多模型/多提供商支持
支持 OpenAI、Claude(Anthropic)、Google(Gemini)、DeepSeek、智谱(Zhipu)、Moonshot(Kimi)
API 可从 .env 或界面配置的 data/llm_config.json 读取（界面配置优先）。
"""

import os
import json
import urllib.request
from typing import Optional

# 界面配置保存路径（与 .env 并列，界面配置优先）
_CONFIG_DIR = os.path.join(os.path.dirname(__file__), "data")
LLM_CONFIG_PATH = os.path.join(_CONFIG_DIR, "llm_config.json")

# 可选依赖：非 OpenAI 的提供商按需 import，缺失时该提供商不可用
try:
    from openai import OpenAI as OpenAIClient
except ImportError:
    OpenAIClient = None

try:
    from anthropic import Anthropic
except ImportError:
    Anthropic = None

try:
    import google.generativeai as genai
except ImportError:
    genai = None


# 提供商配置：default_model 留空表示「留空则用 API 自动取第一个可用模型」
PROVIDER_CONFIG = [
    {
        "id": "openai",
        "name": "OpenAI (GPT-4o-mini / GPT-4)",
        "default_model": "",
        "env_key": "OPENAI_API_KEY",
        "env_model": "OPENAI_MODEL",
        "env_base_url": "OPENAI_BASE_URL",
        "base_url_default": "https://api.openai.com/v1",
    },
    {
        "id": "anthropic",
        "name": "Anthropic (Claude)",
        "default_model": "",
        "env_key": "ANTHROPIC_API_KEY",
        "env_model": "ANTHROPIC_MODEL",
        "env_base_url": None,
        "base_url_default": None,
    },
    {
        "id": "google",
        "name": "Google (Gemini)",
        "default_model": "",
        "env_key": "GOOGLE_API_KEY",
        "env_model": "GOOGLE_MODEL",
        "env_base_url": None,
        "base_url_default": None,
    },
    {
        "id": "deepseek",
        "name": "DeepSeek",
        "default_model": "",
        "env_key": "DEEPSEEK_API_KEY",
        "env_model": "DEEPSEEK_MODEL",
        "env_base_url": "DEEPSEEK_BASE_URL",
        "base_url_default": "https://api.deepseek.com/v1",
    },
    {
        "id": "zhipu",
        "name": "智谱 (Zhipu GLM)",
        "default_model": "",
        "env_key": "ZHIPU_API_KEY",
        "env_model": "ZHIPU_MODEL",
        "env_base_url": "ZHIPU_BASE_URL",
        "base_url_default": "https://open.bigmodel.cn/api/paas/v4",
    },
    {
        "id": "moonshot",
        "name": "月之暗面 (Moonshot/Kimi)",
        "default_model": "",
        "env_key": "MOONSHOT_API_KEY",
        "env_model": "MOONSHOT_MODEL",
        "env_base_url": "MOONSHOT_BASE_URL",
        "base_url_default": "https://api.moonshot.cn/v1",
    },
]


def load_llm_config() -> dict:
    """加载界面保存的 API 配置。格式: { "openai": {"api_key": "...", "base_url": "...", "model": "..."}, ... }"""
    if not os.path.isfile(LLM_CONFIG_PATH):
        return {}
    try:
        with open(LLM_CONFIG_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def save_llm_config(config: dict) -> None:
    """保存 API 配置到文件（供界面调用）。"""
    os.makedirs(os.path.dirname(LLM_CONFIG_PATH), exist_ok=True)
    with open(LLM_CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)


def get_provider_config(provider_id: str) -> dict:
    """
    获取某提供商的配置：先读界面配置，再回退到环境变量。
    返回 {"api_key": str, "base_url": str|None, "model": str}，其中 base_url 仅部分提供商需要。
    """
    cfg = load_llm_config().get(provider_id, {}) or {}
    for p in PROVIDER_CONFIG:
        if p["id"] != provider_id:
            continue
        api_key = (cfg.get("api_key") or "").strip() or os.getenv(p["env_key"], "").strip()
        model = (cfg.get("model") or "").strip() or os.getenv(p["env_model"], p["default_model"]).strip() or p["default_model"]
        base_url = None
        if p.get("env_base_url") or p.get("base_url_default"):
            base_url = (cfg.get("base_url") or "").strip() or os.getenv(p["env_base_url"] or "", p["base_url_default"] or "").strip()
            base_url = base_url or (p.get("base_url_default") or None)
        return {"api_key": api_key, "base_url": base_url, "model": model}
    return {"api_key": "", "base_url": None, "model": "gpt-4o-mini"}


def get_provider_list():
    """返回可用于 UI 的提供商列表 [(id, 显示名), ...]"""
    return [(p["id"], p["name"]) for p in PROVIDER_CONFIG]


def provider_has_base_url(provider_id: str) -> bool:
    """该提供商是否支持自定义 Base URL（OpenAI 兼容类）"""
    for p in PROVIDER_CONFIG:
        if p["id"] == provider_id:
            return bool(p.get("env_base_url") or p.get("base_url_default"))
    return False


def get_default_model(provider_id: str) -> str:
    """该提供商的默认模型名（空字符串表示可由 API 自动检测）"""
    for p in PROVIDER_CONFIG:
        if p["id"] == provider_id:
            return p["default_model"]
    return "gpt-4o-mini"


def get_model_placeholder(provider_id: str) -> str:
    """UI 中「模型名」输入框的占位文案"""
    default = get_default_model(provider_id)
    if not default:
        return "留空则自动使用当前账号第一个可用模型"
    return default


def get_provider_config_for_ui(provider_id: str) -> dict:
    """供 UI 展示/预填用：返回当前该提供商的配置（含已配置时的占位）。"""
    raw = get_provider_config(provider_id)
    return {
        "api_key": raw["api_key"],  # UI 用 password 输入，可显示「已配置」占位
        "base_url": raw["base_url"] or "",
        "model": raw["model"] or "",
    }


def get_model_for_provider(provider_id: str) -> str:
    """获取当前配置（界面或环境变量）下的模型名"""
    c = get_provider_config(provider_id)
    return (c["model"] or "").strip() or next(
        (p["default_model"] for p in PROVIDER_CONFIG if p["id"] == provider_id),
        "gpt-4o-mini",
    )


def _get_first_anthropic_model(api_key: str) -> Optional[str]:
    """调用 Anthropic 列出模型接口，返回当前账号第一个可用模型 ID；失败返回 None。"""
    try:
        req = urllib.request.Request(
            "https://api.anthropic.com/v1/models",
            headers={
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
            },
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())
        items = data.get("data") or []
        if items and isinstance(items[0].get("id"), str):
            return items[0]["id"]
    except Exception:
        pass
    return None


def _get_first_openai_style_model(api_key: str, base_url: str) -> Optional[str]:
    """OpenAI 及兼容接口 GET /v1/models，返回第一个模型 id；失败返回 None。"""
    try:
        url = base_url.rstrip("/") + "/models"
        req = urllib.request.Request(
            url,
            headers={"Authorization": "Bearer " + api_key},
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())
        items = data.get("data") or []
        if items and isinstance(items[0].get("id"), str):
            return items[0]["id"]
    except Exception:
        pass
    return None


def _get_first_google_model(api_key: str) -> Optional[str]:
    """调用 Google Generative AI 列出模型，返回第一个可用于生成的模型名；失败返回 None。"""
    if genai is None:
        return None
    try:
        genai.configure(api_key=api_key)
        for m in genai.list_models():
            name = getattr(m, "name", "") or ""
            if not name:
                continue
            if name.startswith("models/"):
                name = name[7:]
            methods = getattr(m, "supported_generation_methods", []) or []
            if not methods or "generateContent" in methods:
                return name
        for m in genai.list_models():
            name = getattr(m, "name", "") or ""
            if name.startswith("models/"):
                name = name[7:]
            if name:
                return name
    except Exception:
        pass
    return None


def chat_completion(
    provider_id: str,
    system_prompt: str,
    user_prompt: str,
    temperature: float = 0.2,
    model: Optional[str] = None,
) -> str:
    """
    统一对话接口：根据 provider_id 调用对应 API，返回助手回复文本。
    model 为空时使用该 provider 的 env 或默认模型。
    """
    if model is None:
        model = get_model_for_provider(provider_id)

    # OpenAI 及 OpenAI 兼容 (DeepSeek / Zhipu / Moonshot)
    if provider_id == "openai":
        return _chat_openai(system_prompt, user_prompt, temperature, model)
    if provider_id == "deepseek":
        return _chat_openai_compatible(
            provider_id, system_prompt, user_prompt, temperature, model
        )
    if provider_id == "zhipu":
        return _chat_openai_compatible(
            provider_id, system_prompt, user_prompt, temperature, model
        )
    if provider_id == "moonshot":
        return _chat_openai_compatible(
            provider_id, system_prompt, user_prompt, temperature, model
        )

    if provider_id == "anthropic":
        return _chat_anthropic(system_prompt, user_prompt, temperature, model)
    if provider_id == "google":
        return _chat_google(system_prompt, user_prompt, temperature, model)

    raise ValueError(f"不支持的提供商: {provider_id}")


def _chat_openai(
    system_prompt: str, user_prompt: str, temperature: float, model: str
) -> str:
    if OpenAIClient is None:
        raise RuntimeError("当前环境缺少依赖，请在项目目录运行：pip install -r requirements.txt 后重启应用")
    c = get_provider_config("openai")
    if not c["api_key"]:
        raise RuntimeError("请在上方「配置当前模型 API」中填写 OpenAI API Key，或在 .env 中设置 OPENAI_API_KEY")
    base = (c["base_url"] or "https://api.openai.com/v1").strip()
    use_model = (model or "").strip()
    if not use_model:
        use_model = _get_first_openai_style_model(c["api_key"], base) or "gpt-4o-mini"
    client = OpenAIClient(api_key=c["api_key"], base_url=base)
    resp = client.chat.completions.create(
        model=use_model,
        temperature=temperature,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    )
    return (resp.choices[0].message.content or "").strip()


def _get_openai_compatible_client(provider_id: str):
    """获取 OpenAI 兼容 API 的 client（DeepSeek / Zhipu / Moonshot）"""
    if OpenAIClient is None:
        raise RuntimeError("当前环境缺少依赖，请在项目目录运行：pip install -r requirements.txt 后重启应用")
    c = get_provider_config(provider_id)
    if not c["api_key"]:
        p = next((x for x in PROVIDER_CONFIG if x["id"] == provider_id), None)
        hint = p["env_key"] if p else "API Key"
        raise RuntimeError(f"请在上方「配置当前模型 API」中填写 {provider_id} 的 API Key，或在 .env 中设置 {hint}")
    return OpenAIClient(api_key=c["api_key"], base_url=c["base_url"] or None)


# OpenAI 兼容类（DeepSeek/Zhipu/Moonshot）的兜底默认模型
_OPENAI_COMPATIBLE_FALLBACK = {
    "deepseek": "deepseek-chat",
    "zhipu": "glm-4-flash",
    "moonshot": "moonshot-v1-8k",
}


def _chat_openai_compatible(
    provider_id: str,
    system_prompt: str,
    user_prompt: str,
    temperature: float,
    model: str,
) -> str:
    c = get_provider_config(provider_id)
    base = (c["base_url"] or "").strip()
    use_model = (model or "").strip()
    if not use_model and base:
        use_model = _get_first_openai_style_model(c["api_key"], base) or _OPENAI_COMPATIBLE_FALLBACK.get(provider_id, "gpt-4o-mini")
    if not use_model:
        use_model = _OPENAI_COMPATIBLE_FALLBACK.get(provider_id, "gpt-4o-mini")
    client = _get_openai_compatible_client(provider_id)
    resp = client.chat.completions.create(
        model=use_model,
        temperature=temperature,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    )
    return (resp.choices[0].message.content or "").strip()


def _chat_anthropic(
    system_prompt: str, user_prompt: str, temperature: float, model: str
) -> str:
    if Anthropic is None:
        raise RuntimeError("当前环境缺少 Claude 依赖，请在项目目录运行：pip install -r requirements.txt 后重启应用")
    c = get_provider_config("anthropic")
    if not c["api_key"]:
        raise RuntimeError("请在上方「配置当前模型 API」中填写 Anthropic API Key，或在 .env 中设置 ANTHROPIC_API_KEY")
    # 模型名为空时：用 API 自动取当前账号第一个可用模型，仅填 Key 即可用
    use_model = (model or "").strip()
    if not use_model:
        use_model = _get_first_anthropic_model(c["api_key"]) or "claude-3-5-sonnet-20240620"
    client = Anthropic(api_key=c["api_key"])
    msg = client.messages.create(
        model=use_model,
        max_tokens=8192,
        system=system_prompt,
        messages=[{"role": "user", "content": user_prompt}],
        temperature=temperature,
    )
    text = msg.content[0]
    if hasattr(text, "text"):
        return text.text.strip()
    return str(text).strip()


def _chat_google(
    system_prompt: str, user_prompt: str, temperature: float, model: str
) -> str:
    if genai is None:
        raise RuntimeError("当前环境缺少 Gemini 依赖，请在项目目录运行：pip install -r requirements.txt 后重启应用")
    c = get_provider_config("google")
    if not c["api_key"]:
        raise RuntimeError("请在上方「配置当前模型 API」中填写 Google API Key，或在 .env 中设置 GOOGLE_API_KEY")
    use_model = (model or "").strip()
    if not use_model:
        use_model = _get_first_google_model(c["api_key"]) or "gemini-1.5-flash"
    genai.configure(api_key=c["api_key"])
    generative_model = genai.GenerativeModel(
        model_name=use_model,
        system_instruction=system_prompt,
    )
    resp = generative_model.generate_content(
        user_prompt,
        generation_config={"temperature": temperature},
    )
    if not resp or not resp.text:
        raise RuntimeError("Google Gemini 未返回有效内容")
    return resp.text.strip()


def is_provider_available(provider_id: str) -> bool:
    """检查该提供商是否已配置（API Key 来自界面或环境变量）且依赖已安装"""
    c = get_provider_config(provider_id)
    if not c["api_key"]:
        return False
    if provider_id == "anthropic" and Anthropic is None:
        return False
    if provider_id == "google" and genai is None:
        return False
    if provider_id in ("openai", "deepseek", "zhipu", "moonshot") and OpenAIClient is None:
        return False
    return True
