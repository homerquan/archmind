from __future__ import annotations

from pathlib import Path
from typing import Any

from archmind.models import ArchitectureRequest, LLMConfig, RepositorySnapshot
from archmind.utils import ensure_dir, write_text


SEVERITY_RANK = {"high": 3, "medium": 2, "low": 1}
SEVERITY_LABEL = {"high": "High", "medium": "Medium", "low": "Low"}
GROUP_ORDER = [
    "structural_coupling",
    "cohesion_and_separation",
    "interface_design",
    "data_ownership",
    "bottlenecks_and_isolation",
    "observability",
    "security",
]
ISSUE_GROUPS = {
    "tight_coupling": "structural_coupling",
    "unclear_boundaries": "structural_coupling",
    "low_cohesion": "cohesion_and_separation",
    "poor_separation_of_concerns": "cohesion_and_separation",
    "bad_interface_api_design": "interface_design",
    "data_ownership_confusion": "data_ownership",
    "scalability_bottlenecks": "bottlenecks_and_isolation",
    "weak_fault_isolation": "bottlenecks_and_isolation",
    "lack_of_observability": "observability",
    "security_not_built_in": "security",
}
GROUP_TITLES = {
    "structural_coupling": "Structural Coupling and Boundary Breakdown",
    "cohesion_and_separation": "Low Cohesion and Separation of Concerns",
    "interface_design": "Interface and API Design",
    "data_ownership": "Data Ownership and Source of Truth",
    "bottlenecks_and_isolation": "Bottlenecks and Fault Isolation",
    "observability": "Observability Coverage",
    "security": "Security and Trust Boundaries",
}
GROUP_ASSESSMENTS = {
    "structural_coupling": (
        "Dependencies and boundaries are too entangled, so changes are likely to propagate widely "
        "and ownership lines are harder to preserve."
    ),
    "cohesion_and_separation": (
        "Responsibilities are spread across components in ways that reduce focus, making the codebase "
        "harder to understand, test, and evolve safely."
    ),
    "interface_design": (
        "Interface surfaces appear sensitive or over-consumed, which increases change risk and makes integration contracts more brittle."
    ),
    "data_ownership": (
        "Shared data responsibilities appear unclear, which raises the risk of inconsistent state and harder-to-diagnose behavior."
    ),
    "bottlenecks_and_isolation": (
        "Central chokepoints and weak isolation paths increase the chance that failures or load concentration will spread through the system."
    ),
    "observability": (
        "Instrumentation coverage is limited enough to slow diagnosis, reduce operating confidence, and make incident response harder."
    ),
    "security": (
        "Security and trust-boundary concerns are not strong enough in the architecture, which can turn local weaknesses into system-level risk."
    ),
}


def render_report(
    snapshot: RepositorySnapshot,
    request: ArchitectureRequest,
    llm_config: LLMConfig,
    graph_results: dict[str, dict[str, Any]],
    issue_assessments: list[dict[str, Any]],
    issue_summary: dict[str, Any],
) -> str:
    consolidated_issues = _consolidate_issue_assessments(issue_assessments)
    overall_score, overall_summary, top_risks, priority_actions = _overall_architecture_view(consolidated_issues)

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

    lines.extend(["", "## Issue Assessments Overview", ""])
    lines.extend(_overview_table(consolidated_issues))
    lines.extend(["", "## Issue Assessments"])
    lines.extend(_issue_sections(consolidated_issues))
    lines.extend(
        [
            "",
            "## Overall Architecture Score",
            f"**Score:** {overall_score}/10",
            "",
            "**Summary**  ",
            overall_summary,
            "",
            "**Top Risks**",
        ]
    )
    lines.extend(f"{index}. {risk}" for index, risk in enumerate(top_risks, start=1))
    lines.extend(["", "**Priority Actions**"])
    lines.extend(f"{index}. {action}" for index, action in enumerate(priority_actions, start=1))
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


def _consolidate_issue_assessments(issue_assessments: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for assessment in issue_assessments:
        group_key = ISSUE_GROUPS.get(assessment.get("id", ""), assessment.get("id", "misc"))
        grouped.setdefault(group_key, []).append(assessment)

    consolidated: list[dict[str, Any]] = []
    for group_key in GROUP_ORDER:
        group_items = grouped.get(group_key, [])
        if not group_items:
            continue
        severity = max((item.get("severity", "low") for item in group_items), key=lambda value: SEVERITY_RANK.get(value, 0))
        evidence = _dedupe_preserve(
            item
            for assessment in group_items
            for item in assessment.get("evidence", [])
            if str(item).strip()
        )
        recommendations = _dedupe_preserve(
            item
            for assessment in group_items
            for item in assessment.get("recommendations", [])
            if str(item).strip()
        )
        title = GROUP_TITLES.get(group_key) or _fallback_issue_name(group_items)
        assessment_text = GROUP_ASSESSMENTS.get(group_key) or _combined_assessment_text(group_items)
        score = _issue_score(severity, evidence, group_items)
        one_line_summary = _one_line_summary(group_key, evidence, assessment_text)
        consolidated.append(
            {
                "group_key": group_key,
                "title": title,
                "severity": severity,
                "severity_label": SEVERITY_LABEL[severity],
                "score": score,
                "assessment": assessment_text,
                "one_line_summary": one_line_summary,
                "evidence": evidence,
                "recommendations": recommendations[:3] or ["Review the related graph hotspots and narrow the highest-risk dependency paths."],
                "source_ids": [item.get("id", "") for item in group_items],
            }
        )

    remaining_keys = sorted(set(grouped) - set(GROUP_ORDER))
    for group_key in remaining_keys:
        group_items = grouped[group_key]
        severity = max((item.get("severity", "low") for item in group_items), key=lambda value: SEVERITY_RANK.get(value, 0))
        evidence = _dedupe_preserve(item for assessment in group_items for item in assessment.get("evidence", []))
        recommendations = _dedupe_preserve(item for assessment in group_items for item in assessment.get("recommendations", []))
        title = _fallback_issue_name(group_items)
        assessment_text = _combined_assessment_text(group_items)
        consolidated.append(
            {
                "group_key": group_key,
                "title": title,
                "severity": severity,
                "severity_label": SEVERITY_LABEL[severity],
                "score": _issue_score(severity, evidence, group_items),
                "assessment": assessment_text,
                "one_line_summary": _one_line_summary(group_key, evidence, assessment_text),
                "evidence": evidence,
                "recommendations": recommendations[:3],
                "source_ids": [item.get("id", "") for item in group_items],
            }
        )

    return sorted(
        consolidated,
        key=lambda item: (-SEVERITY_RANK[item["severity"]], -item["score"], item["title"]),
    )


def _overview_table(consolidated_issues: list[dict[str, Any]]) -> list[str]:
    lines = [
        "| # | Issue | Severity | Score | One-line Summary |",
        "|---|-------|----------|-------|------------------|",
    ]
    for index, issue in enumerate(consolidated_issues, start=1):
        lines.append(
            f"| {index} | {issue['title']} | {issue['severity_label']} | {issue['score']}/10 | {issue['one_line_summary']} |"
        )
    return lines


def _issue_sections(consolidated_issues: list[dict[str, Any]]) -> list[str]:
    lines: list[str] = []
    for issue in consolidated_issues:
        lines.extend(
            [
                "",
                f"### {issue['title']}",
                f"**Severity:** {issue['severity_label']}",
                "",
                "**Assessment**  ",
                issue["assessment"],
                "",
                "**Evidence**",
            ]
        )
        lines.extend(f"- {item}" for item in issue["evidence"])
        lines.extend(["", "**Recommendations**"])
        lines.extend(f"{index}. {item}" for index, item in enumerate(issue["recommendations"], start=1))
    return lines


def _overall_architecture_view(consolidated_issues: list[dict[str, Any]]) -> tuple[str, str, list[str], list[str]]:
    if not consolidated_issues:
        return "10.0", "No material architecture issues were detected in this run.", ["No major risks identified."], ["Keep monitoring future architectural drift."]

    risk_average = sum(issue["score"] for issue in consolidated_issues) / len(consolidated_issues)
    high_count = sum(1 for issue in consolidated_issues if issue["severity"] == "high")
    medium_count = sum(1 for issue in consolidated_issues if issue["severity"] == "medium")
    weighted_penalty = (risk_average * 0.62) + (high_count * 0.55) + (medium_count * 0.2)
    overall_score = max(0.5, min(10.0, 10.0 - weighted_penalty))

    leading_titles = ", ".join(issue["title"] for issue in consolidated_issues[:3])
    overall_summary = (
        f"The architecture shows its strongest risk concentration around {leading_titles}. "
        f"Across the consolidated issue set, the main pattern is structural entanglement that would make safe change, isolation, and long-term evolution harder than it should be."
    )
    top_risks = [
        f"{issue['title']}: {issue['one_line_summary']}"
        for issue in consolidated_issues[:3]
    ]
    priority_actions = _dedupe_preserve(
        recommendation
        for issue in consolidated_issues
        for recommendation in issue["recommendations"]
    )[:3]
    return f"{overall_score:.1f}", overall_summary, top_risks, priority_actions


def _issue_score(severity: str, evidence: list[str], group_items: list[dict[str, Any]]) -> float:
    base = {"high": 8.8, "medium": 6.4, "low": 3.8}[severity]
    signal_bonus = min(1.0, 0.18 * _signal_count(evidence))
    merge_bonus = min(0.6, 0.25 * (len(group_items) - 1))
    return round(min(10.0, base + signal_bonus + merge_bonus), 1)


def _signal_count(evidence: list[str]) -> int:
    signals = 0
    for item in evidence:
        text = str(item).lower()
        if "none" in text:
            continue
        if text.endswith(": 0") or text.endswith(": 0.0"):
            continue
        signals += 1
    return signals


def _one_line_summary(group_key: str, evidence: list[str], assessment_text: str) -> str:
    highlights = [item for item in evidence if "none" not in item.lower() and not item.lower().endswith(": 0")]
    if group_key == "structural_coupling":
        return "Cycles and cross-boundary links create high change-propagation risk."
    if group_key == "cohesion_and_separation":
        return "Responsibilities appear too spread out, which weakens modular clarity."
    if group_key == "interface_design":
        return "Sensitive interfaces are heavily consumed and likely brittle under change."
    if group_key == "data_ownership":
        return "Shared data responsibilities are not cleanly owned."
    if group_key == "bottlenecks_and_isolation":
        return "Central chokepoints and bridge nodes make failures harder to contain."
    if group_key == "observability":
        return "Instrumentation gaps would slow diagnosis and reduce operating confidence."
    if group_key == "security":
        return "Security coverage and trust-boundary clarity are not strong enough."
    if highlights:
        return _truncate_sentence(highlights[0].rstrip(".") + ".")
    return _truncate_sentence(assessment_text)


def _fallback_issue_name(group_items: list[dict[str, Any]]) -> str:
    for item in group_items:
        title = str(item.get("title", "")).strip()
        if title:
            return title
    return "Architecture Issue"


def _combined_assessment_text(group_items: list[dict[str, Any]]) -> str:
    summaries = _dedupe_preserve(item.get("summary", "") for item in group_items if item.get("summary"))
    if not summaries:
        return "This issue should be reviewed as part of the overall architecture assessment."
    if len(summaries) == 1:
        return summaries[0]
    joined = "; ".join(summary.rstrip(".") for summary in summaries[:2])
    return joined + "."


def _truncate_sentence(value: str, limit: int = 88) -> str:
    sentence = " ".join(value.split())
    if len(sentence) <= limit:
        return sentence
    return sentence[: limit - 3].rstrip() + "..."


def _dedupe_preserve(items) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for item in items:
        text = " ".join(str(item).split()).strip()
        key = text.lower()
        if not text or key in seen:
            continue
        seen.add(key)
        ordered.append(text)
    return ordered
