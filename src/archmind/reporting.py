from __future__ import annotations

from pathlib import Path
from typing import Any

from archmind.models import ArchitectureRequest, LLMConfig, RepositorySnapshot
from archmind.utils import ensure_dir, write_text


def render_report(
    snapshot: RepositorySnapshot,
    request: ArchitectureRequest,
    llm_config: LLMConfig,
    graph_results: dict[str, dict[str, Any]],
    issue_assessments: list[dict[str, Any]],
    issue_summary: dict[str, Any],
) -> str:
    lines = [
        "# ArchMind Report",
        "",
        "## Run Context",
        f"- Repository: `{snapshot.github_url}`",
        f"- Branch: `{snapshot.branch}`",
        f"- Commit: `{snapshot.commit_sha}`",
        f"- Output folder: `{request.output_dir}`",
        f"- LLM provider: `{llm_config.provider}`",
        f"- LLM model: `{llm_config.model}`",
        f"- API key source: `{llm_config.api_key_source}`",
        "",
        "## Issue Summary",
        f"- Total issues inspected: `{issue_summary['issue_count']}`",
        f"- High severity: `{issue_summary['high_severity_count']}`",
        f"- Medium severity: `{issue_summary['medium_severity_count']}`",
        f"- Low severity: `{issue_summary['low_severity_count']}`",
        "",
        "## Graphs Generated",
    ]

    for graph_id, result in graph_results.items():
        metrics = result["metrics"]
        lines.append(
            f"- `{graph_id}`: nodes=`{metrics.get('node_count', 0)}`, "
            f"edges=`{metrics.get('edge_count', 0)}`"
        )

    lines.extend(["", "## Issue Assessments"])
    for assessment in issue_assessments:
        lines.append("")
        lines.append(assessment["markdown"].strip())
    return "\n".join(lines).strip() + "\n"


def terminal_summary(snapshot: RepositorySnapshot, graph_results: dict[str, dict[str, Any]], issue_summary: dict[str, Any]) -> str:
    dependency_metrics = graph_results.get("dependency_graph", {}).get("metrics", {})
    return (
        f"Repository: {snapshot.github_url}\n"
        f"Branch: {snapshot.branch} @ {snapshot.commit_sha[:12]}\n"
        f"Dependency modules: {dependency_metrics.get('module_count', 0)} | "
        f"Cycles: {dependency_metrics.get('cycle_count', 0)}\n"
        f"Issues: high={issue_summary['high_severity_count']}, "
        f"medium={issue_summary['medium_severity_count']}, low={issue_summary['low_severity_count']}"
    )


def write_reports(workspace: Path, output_dir: Path, markdown: str) -> tuple[Path, Path]:
    deliverable_path = workspace / "deliverables" / "result.md"
    ensure_dir(deliverable_path.parent)
    write_text(deliverable_path, markdown)
    ensure_dir(output_dir)
    exported_report_path = output_dir / "result.md"
    write_text(exported_report_path, markdown)
    return deliverable_path, exported_report_path
