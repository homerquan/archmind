from __future__ import annotations

import getpass
import shutil
import sys
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Callable, Iterator

from archmind import __version__


try:
    from rich.console import Console
    from rich.progress import BarColumn, Progress, SpinnerColumn, TextColumn, TimeElapsedColumn
except Exception:  # pragma: no cover - optional dependency
    Console = None
    Progress = None


ASCII_BANNER = r"""
    ___              __    __  ___ _           __
   /   |  __________/ /_  /  |/  /(_)___  ____/ /
  / /| | / ___/ ___/ __ \/ /|_/ // / __ \/ __  /
 / ___ |/ /  / /__/ / / / /  / // / / / / /_/ /
/_/  |_/_/   \___/_/ /_/_/  /_//_/_/ /_/\__,_/
"""


@dataclass
class PromptIO:
    input_fn: Callable[[str], str] = input
    getpass_fn: Callable[[str], str] = getpass.getpass


class UI:
    def __init__(self, prompt_io: PromptIO | None = None, stream=None) -> None:
        self.prompt_io = prompt_io or PromptIO()
        self.stream = stream or sys.stdout
        self.console = Console(file=self.stream) if Console is not None else None

    def banner(self) -> None:
        title = f"ArchMind v{__version__}"
        if self.console:
            self.console.print(f"[bold cyan]{ASCII_BANNER}[/bold cyan]")
            self.console.print(f"[bold white]{title}[/bold white]")
            self.console.print("[dim]Architecture analysis REPL[/dim]")
        else:
            print(ASCII_BANNER, file=self.stream)
            print(title, file=self.stream)
            print("Architecture analysis REPL", file=self.stream)

    def info(self, message: str, icon: str = "•") -> None:
        line = f"{icon} {message}"
        if self.console:
            self.console.print(line)
        else:
            print(line, file=self.stream)

    def success(self, message: str) -> None:
        self.info(message, icon="✓")

    def warning(self, message: str) -> None:
        self.info(message, icon="!")

    def prompt(self, label: str, default: str | None = None, secret: bool = False) -> str:
        prompt_label = label if default is None else f"{label} [{default}]"
        raw = self.prompt_io.getpass_fn(f"{prompt_label}: ") if secret else self.prompt_io.input_fn(f"{prompt_label}: ")
        value = raw.strip()
        if not value and default is not None:
            return default
        return value

    def choose(self, label: str, options: list[str], default: str) -> str:
        choices = ", ".join(f"{option}{' *' if option == default else ''}" for option in options)
        while True:
            value = self.prompt(f"{label} ({choices})", default=default).lower()
            if value in options:
                return value
            self.warning(f"Choose one of: {', '.join(options)}")

    @contextmanager
    def progress(self, description: str, total: int = 1) -> Iterator[Callable[[int], None]]:
        if self.console and Progress is not None:
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                TextColumn("{task.completed}/{task.total}"),
                TimeElapsedColumn(),
                console=self.console,
                transient=True,
            ) as progress:
                task_id = progress.add_task(description, total=total)

                def advance(step: int = 1) -> None:
                    progress.advance(task_id, step)

                yield advance
        else:
            width = min(32, max(10, shutil.get_terminal_size((80, 20)).columns - len(description) - 12))
            completed = 0

            def render() -> None:
                filled = int(width * completed / total) if total else width
                bar = "#" * filled + "-" * (width - filled)
                print(f"[{bar}] {completed}/{total} {description}", file=self.stream)

            render()

            def advance(step: int = 1) -> None:
                nonlocal completed
                completed = min(total, completed + step)
                render()

            yield advance
