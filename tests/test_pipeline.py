from __future__ import annotations

import subprocess
from pathlib import Path

from archmind.models import ArchitectureRequest
from archmind.pipeline import run
from archmind.ui import PromptIO, UI


def _init_repo(remote_path: Path) -> None:
    subprocess.run(["git", "init", "-b", "main", str(remote_path)], check=True, capture_output=True)
    pkg = remote_path / "demo"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("", encoding="utf-8")
    (pkg / "a.py").write_text("from demo import b\n", encoding="utf-8")
    (pkg / "b.py").write_text("import json\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(remote_path), "config", "user.email", "test@example.com"], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(remote_path), "config", "user.name", "Test User"], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(remote_path), "add", "."], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(remote_path), "commit", "-m", "init"], check=True, capture_output=True)


def test_pipeline_generates_report_and_artifacts(tmp_path: Path) -> None:
    remote_repo = tmp_path / "remote"
    remote_repo.mkdir()
    _init_repo(remote_repo)

    output_dir = tmp_path / "result"
    request = ArchitectureRequest(
        github_url=str(remote_repo),
        branch="main",
        output_dir=str(output_dir),
        llm_provider="openai",
    )
    prompt_io = PromptIO(input_fn=lambda _: "", getpass_fn=lambda _: "")
    ui = UI(prompt_io=prompt_io)

    result = run(request, ui, workspaces_root=tmp_path / "workspaces")

    workspace = Path(result["workspace"])
    assert (output_dir / "result.md").exists()
    assert (output_dir / "graph_visualization.pdf").exists()
    assert (output_dir / "metrics.json").exists()
    assert (output_dir / "findings.json").exists()
    assert (output_dir / "dsm.csv").exists()
    assert (workspace / "graph" / "architecture_graph.json").exists()
    assert (workspace / "analysis" / "metrics.json").exists()
    assert (workspace / "analysis" / "graph_visualization.pdf").exists()
    assert (workspace / "analysis" / "graph_visualization.pdf").read_bytes().startswith(b"%PDF-1.4")
    assert (workspace / "deliverables" / "result.md").exists()
    assert (workspace / "eval" / "report.json").exists()
