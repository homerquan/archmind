from __future__ import annotations

import os

from archmind.models import LLMConfig


PROVIDER_MODELS = {
    "openai": "openai/gpt-4o-mini",
    "anthropic": "anthropic/claude-3-5-haiku-latest",
    "gemini": "gemini/gemini-1.5-flash",
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
        from litellm import completion
    except Exception:
        return None
    try:  # pragma: no cover - optional dependency and network path
        response = completion(
            model=llm_config.model,
            api_key=llm_config.api_key,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.2,
        )
        return response["choices"][0]["message"]["content"]
    except Exception:
        return None
