from __future__ import annotations

from pathlib import Path

from archmind.models import ArchitectureRequest, LLMConfig, RepositorySnapshot
from archmind.utils import ensure_dir, write_text


def render_report(
    snapshot: RepositorySnapshot,
    request: ArchitectureRequest,
    llm_config: LLMConfig,
    metrics: dict,
    findings: list[dict],
    explanations_markdown: str,
) -> str:
    findings_md = "\n".join(
        f"- **{item['kind']}** ({item['severity']}): {item['summary']}" for item in findings
    ) or "- No findings."
    lines = [
        "# ArchMind Report",
        "",
        "## Run Context",
        f"- Repository: `{snapshot.github_url}`",
        f"- Branch: `{snapshot.branch}`",
        f"- Commit: `{snapshot.commit_sha}`",
        f"- Output path: `{request.output_markdown_path}`",
        f"- LLM provider: `{llm_config.provider}`",
        f"- LLM model: `{llm_config.model}`",
        f"- API key source: `{llm_config.api_key_source}`",
        "",
        "## Summary Metrics",
        f"- Modules analyzed: `{metrics['module_count']}`",
        f"- Dependency edges: `{metrics['edge_count']}`",
        f"- Cycle count: `{metrics['cycle_count']}`",
        f"- Articulation points: `{len(metrics['articulation_points'])}`",
        "",
        "## Findings",
        findings_md,
        "",
        explanations_markdown.strip(),
        "",
    ]
    return "\n".join(lines).strip() + "\n"


def terminal_summary(snapshot: RepositorySnapshot, metrics: dict, findings: list[dict]) -> str:
    top = findings[0]["summary"] if findings else "No major structural findings detected."
    return (
        f"Repository: {snapshot.github_url}\n"
        f"Branch: {snapshot.branch} @ {snapshot.commit_sha[:12]}\n"
        f"Modules: {metrics['module_count']} | Edges: {metrics['edge_count']} | Cycles: {metrics['cycle_count']}\n"
        f"Top finding: {top}"
    )


def write_reports(workspace: Path, output_path: Path, markdown: str) -> Path:
    deliverable_path = workspace / "deliverables" / "result.md"
    ensure_dir(deliverable_path.parent)
    write_text(deliverable_path, markdown)
    write_text(output_path, markdown)
    return deliverable_path
