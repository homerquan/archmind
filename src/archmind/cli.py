from __future__ import annotations

import argparse
from pathlib import Path
from typing import Sequence

from archmind import __version__
from archmind.models import ArchitectureRequest
from archmind.pipeline import run
from archmind.ui import PromptIO, UI


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="archmind", description="Analyze repository architecture in a REPL-style CLI.")
    parser.add_argument("github_url", nargs="?", help="Git repository URL or path.")
    parser.add_argument("--branch", help="Target branch. Defaults to main.")
    parser.add_argument("--output", help="Output folder. Defaults to ./result.")
    parser.add_argument("--llm-provider", choices=["openai", "anthropic", "gemini"], help="LLM provider to use.")
    parser.add_argument("--debug", action="store_true", help="Enable debug logging, including LiteLLM debug output.")
    parser.add_argument("--version", action="version", version=f"archmind {__version__}")
    return parser


def main(argv: Sequence[str] | None = None, prompt_io: PromptIO | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    ui = UI(prompt_io=prompt_io)
    ui.banner()
    request = _collect_request(args, ui)
    run(request, ui, workspaces_root=Path.cwd() / "workspaces")
    return 0


def _collect_request(args, ui: UI) -> ArchitectureRequest:
    github_url = args.github_url or ui.prompt("Repository URL or path")
    branch = ui.prompt("Branch", default=args.branch or "main")
    output_dir = ui.prompt("Output folder", default=args.output or "result")
    provider = args.llm_provider or ui.choose("LLM provider", ["openai", "anthropic", "gemini"], default="openai")
    return ArchitectureRequest(
        github_url=github_url,
        branch=branch,
        output_dir=output_dir,
        llm_provider=provider,
        debug=args.debug,
    )


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
