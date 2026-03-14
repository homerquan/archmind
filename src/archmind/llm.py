from __future__ import annotations

import os

from archmind.models import LLMConfig


PROVIDER_MODELS = {
    "openai": "openai/gpt-4o-mini",
    "anthropic": "anthropic/claude-3-5-haiku-latest",
    "gemini": "gemini/gemini-3-flash-preview",
}

PROVIDER_ENV_VARS = {
    "openai": ["OPENAI_API_KEY"],
    "anthropic": ["ANTHROPIC_API_KEY"],
    "gemini": ["GEMINI_API_KEY", "GOOGLE_API_KEY"],
}


def collect_llm_config(ui, provider_hint: str | None = None) -> LLMConfig:
    if provider_hint in PROVIDER_MODELS:
        provider = provider_hint
    else:
        provider = ui.choose("LLM provider", ["openai", "anthropic", "gemini"], default="openai")
    api_key, source = resolve_api_key(provider, ui)
    return LLMConfig(provider=provider, model=PROVIDER_MODELS[provider], api_key=api_key, api_key_source=source)


def resolve_api_key(provider: str, ui) -> tuple[str | None, str]:
    for env_name in PROVIDER_ENV_VARS[provider]:
        value = os.getenv(env_name)
        if value:
            return value, f"env:{env_name}"
    api_key = ui.prompt(f"{provider.title()} API key (leave blank for local fallback)", secret=True)
    if api_key:
        return api_key, "prompt"
    return None, "none"


def llm_completion(system_prompt: str, user_prompt: str, llm_config: LLMConfig) -> str | None:
    if not llm_config.api_key:
        return None
    try:  # pragma: no cover - optional dependency and network path
        import litellm
        from litellm import completion
    except Exception:
        return None
    _enable_litellm_debug(litellm)
    try:  # pragma: no cover - optional dependency and network path
        response = completion(
            model=normalized_model_name(llm_config.provider, llm_config.model),
            custom_llm_provider=llm_config.provider,
            api_key=llm_config.api_key,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.7,
        )
        return response["choices"][0]["message"]["content"]
    except Exception:
        return None


def _enable_litellm_debug(litellm_module) -> None:
    if getattr(litellm_module, "_archmind_debug_enabled", False):
        return
    litellm_module._turn_on_debug()
    litellm_module._archmind_debug_enabled = True


def normalized_model_name(provider: str, model: str) -> str:
    model_name = model.strip()
    provider_prefix = f"{provider}/"
    if model_name.startswith(provider_prefix):
        return model_name
    if "/" in model_name:
        return model_name
    return f"{provider_prefix}{model_name}"
