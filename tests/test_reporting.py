from __future__ import annotations

from archmind.models import ArchitectureRequest, LLMConfig, RepositorySnapshot
from archmind.reporting import render_report


def test_render_report_formats_issue_assessments_for_scannability() -> None:
    snapshot = RepositorySnapshot(
        github_url="https://github.com/example/project",
        branch="main",
        commit_sha="abc123def456",
        fetched_at="2026-03-14T00:00:00+00:00",
        root_path="/tmp/repo",
        language_hints=["python"],
        manifests=[],
    )
    request = ArchitectureRequest(
        github_url=snapshot.github_url,
        branch="main",
        output_dir="result",
        llm_provider="openai",
    )
    llm_config = LLMConfig(
        provider="openai",
        model="openai/gpt-4o-mini",
        api_key=None,
        api_key_source="none",
    )
    graph_results = {
        "dependency_graph": {"metrics": {"node_count": 10, "edge_count": 12}, "findings": []},
        "function_graph": {"metrics": {"node_count": 20, "edge_count": 30}, "findings": []},
    }
    issue_assessments = [
        {
            "id": "tight_coupling",
            "title": "Tight Coupling",
            "summary": "Modules or services depend too heavily on each other.",
            "severity": "high",
            "graphs_used": ["dependency_graph"],
            "evidence": ["Dependency cycles: 5", "Top coupled modules: module:a, module:b"],
            "recommendations": ["Break cycles.", "Reduce fan-in on central modules."],
            "markdown": "### Severity: High",
        },
        {
            "id": "unclear_boundaries",
            "title": "Unclear Service or Module Boundaries",
            "summary": "Responsibilities overlap and ownership becomes unclear.",
            "severity": "high",
            "graphs_used": ["architecture_graph"],
            "evidence": ["Cross-package dependencies: 12", "Boundary hotspots: package:core"],
            "recommendations": ["Clarify ownership."],
            "markdown": "### Architecture Inspection: Low Cohesion",
        },
        {
            "id": "lack_of_observability",
            "title": "Lack of Observability",
            "summary": "Instrumentation coverage is too limited.",
            "severity": "medium",
            "graphs_used": ["operational_risk_graph"],
            "evidence": ["Observability coverage: 0.31"],
            "recommendations": ["Add tracing and metrics."],
            "markdown": "#### 1. Severity: Medium",
        },
    ]
    issue_summary = {
        "issue_count": 3,
        "high_severity_count": 2,
        "medium_severity_count": 1,
        "low_severity_count": 0,
    }

    report = render_report(snapshot, request, llm_config, graph_results, issue_assessments, issue_summary)

    assert "## Issue Assessments Overview" in report
    assert "| # | Issue | Severity | Score | One-line Summary |" in report
    assert "### Structural Coupling and Boundary Breakdown" in report
    assert "**Severity:** High" in report
    assert "**Assessment**" in report
    assert "**Evidence**" in report
    assert "**Recommendations**" in report
    assert "### Tight Coupling" not in report
    assert "### Severity: High" not in report
    assert "## Overall Architecture Score" in report
    assert "**Score:** " in report
    assert "**Top Risks**" in report
    assert "**Priority Actions**" in report
