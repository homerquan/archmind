from __future__ import annotations

from archmind.llm import collect_llm_config, llm_completion
from archmind.models import LLMConfig


def test_llm_config_safe_handling_and_fallback() -> None:
    config = LLMConfig(provider="openai", model="openai/gpt-4o-mini", api_key=None, api_key_source="none")

    assert "api_key" not in config.safe_dict()
    assert llm_completion("system", "user", config) is None


def test_collect_llm_config_uses_provider_hint_without_reprompting() -> None:
    class FakeUI:
        def __init__(self) -> None:
            self.choose_calls = 0
            self.prompt_calls: list[tuple[str, bool]] = []

        def choose(self, label: str, options: list[str], default: str) -> str:
            self.choose_calls += 1
            return "openai"

        def prompt(self, label: str, default: str | None = None, secret: bool = False) -> str:
            self.prompt_calls.append((label, secret))
            return ""

    ui = FakeUI()
    config = collect_llm_config(ui, "anthropic")

    assert config.provider == "anthropic"
    assert config.model == "anthropic/claude-3-5-haiku-latest"
    assert config.api_key is None
    assert config.api_key_source == "none"
    assert ui.choose_calls == 0
    assert ui.prompt_calls == [("Anthropic API key (leave blank for local fallback)", True)]
