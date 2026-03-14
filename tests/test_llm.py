from __future__ import annotations

import sys
from types import SimpleNamespace

from archmind.llm import collect_llm_config, llm_completion, normalized_model_name
from archmind.models import LLMConfig


def test_llm_config_safe_handling_and_fallback() -> None:
    config = LLMConfig(provider="openai", model="openai/gpt-4o-mini", api_key=None, api_key_source="none")

    assert "api_key" not in config.safe_dict()
    assert config.safe_dict()["debug"] is False
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
    assert config.debug is False
    assert ui.choose_calls == 0
    assert ui.prompt_calls == [("Anthropic API key (leave blank for local fallback)", True)]


def test_llm_completion_turns_on_litellm_debug(monkeypatch) -> None:
    debug_calls: list[str] = []
    captured_kwargs: dict[str, object] = {}

    class FakeLiteLLM:
        def _turn_on_debug(self) -> None:
            debug_calls.append("debug")

    fake_module = FakeLiteLLM()

    def fake_completion(**kwargs):
        captured_kwargs.update(kwargs)
        return {"choices": [{"message": {"content": "ok"}}]}

    monkeypatch.setitem(sys.modules, "litellm", SimpleNamespace(completion=fake_completion, _turn_on_debug=fake_module._turn_on_debug))

    config = LLMConfig(
        provider="openai",
        model="openai/gpt-4o-mini",
        api_key="test-key",
        api_key_source="prompt",
        debug=True,
    )

    assert llm_completion("system", "user", config) == "ok"
    assert debug_calls == ["debug"]
    assert captured_kwargs["model"] == "openai/gpt-4o-mini"
    assert captured_kwargs["custom_llm_provider"] == "openai"
    assert captured_kwargs["temperature"] == 0.7


def test_llm_completion_does_not_turn_on_debug_without_flag(monkeypatch) -> None:
    debug_calls: list[str] = []

    def fake_debug() -> None:
        debug_calls.append("debug")

    def fake_completion(**kwargs):
        return {"choices": [{"message": {"content": "ok"}}]}

    monkeypatch.setitem(sys.modules, "litellm", SimpleNamespace(completion=fake_completion, _turn_on_debug=fake_debug))

    config = LLMConfig(
        provider="openai",
        model="openai/gpt-4o-mini",
        api_key="test-key",
        api_key_source="prompt",
        debug=False,
    )

    assert llm_completion("system", "user", config) == "ok"
    assert debug_calls == []


def test_normalized_model_name_adds_provider_prefix_when_missing() -> None:
    assert normalized_model_name("gemini", "gemini-1.5-flash") == "gemini/gemini-1.5-flash"
    assert normalized_model_name("gemini", "gemini/gemini-1.5-flash") == "gemini/gemini-1.5-flash"
    assert normalized_model_name("openai", "openai/gpt-4o-mini") == "openai/gpt-4o-mini"


def test_collect_llm_config_uses_gemini_3_flash_preview_by_default() -> None:
    class FakeUI:
        def prompt(self, label: str, default: str | None = None, secret: bool = False) -> str:
            return ""

    config = collect_llm_config(FakeUI(), "gemini")

    assert config.provider == "gemini"
    assert config.model == "gemini/gemini-3-flash-preview"
