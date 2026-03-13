from __future__ import annotations

from archmind import cli
from archmind.models import ArchitectureRequest
from archmind.ui import PromptIO


def test_collect_request_prompts_for_missing_inputs(monkeypatch) -> None:
    answers = iter([
        "https://github.com/example/project",
        "",
        "",
        "anthropic",
    ])
    prompt_io = PromptIO(input_fn=lambda _: next(answers), getpass_fn=lambda _: "")
    captured: dict[str, ArchitectureRequest] = {}

    def fake_run(request, ui, workspaces_root):
        captured["request"] = request
        return {}

    monkeypatch.setattr(cli, "run", fake_run)
    exit_code = cli.main([], prompt_io=prompt_io)

    assert exit_code == 0
    assert captured["request"].github_url == "https://github.com/example/project"
    assert captured["request"].branch == "main"
    assert captured["request"].output_markdown_path == "result.md"
    assert captured["request"].llm_provider == "anthropic"
