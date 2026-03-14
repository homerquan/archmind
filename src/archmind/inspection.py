from __future__ import annotations

from typing import Any

from archmind.knowledge import graph_support_map, load_graph_catalog, load_issue_definitions
from archmind.llm import llm_completion
from archmind.models import ArchitectureRequest, LLMConfig, RepositorySnapshot


def inspect_knowledge_issues(
    snapshot: RepositorySnapshot,
    request: ArchitectureRequest,
    graph_results: dict[str, dict[str, Any]],
    llm_config: LLMConfig,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    issues = load_issue_definitions()
    support = graph_support_map()
    catalog = {item["id"]: item for item in load_graph_catalog()}
    assessments: list[dict[str, Any]] = []
    for issue in issues:
        graphs_used = support.get(issue["id"], [])
        issue_context = {
            graph_id: {
                "graph": catalog.get(graph_id, {}),
                "metrics": graph_results.get(graph_id, {}).get("metrics", {}),
                "findings": graph_results.get(graph_id, {}).get("findings", []),
            }
            for graph_id in graphs_used
        }
        assessment = _assess_issue(snapshot, request, issue, issue_context, llm_config)
        assessments.append(assessment)
    summary = {
        "issue_count": len(assessments),
        "high_severity_count": sum(1 for item in assessments if item["severity"] == "high"),
        "medium_severity_count": sum(1 for item in assessments if item["severity"] == "medium"),
        "low_severity_count": sum(1 for item in assessments if item["severity"] == "low"),
    }
    return assessments, summary


def _assess_issue(
    snapshot: RepositorySnapshot,
    request: ArchitectureRequest,
    issue: dict[str, Any],
    issue_context: dict[str, Any],
    llm_config: LLMConfig,
) -> dict[str, Any]:
    severity, evidence, recommendations = _heuristic_assessment(issue["id"], issue_context)
    markdown = _issue_markdown(issue, severity, evidence, recommendations)
    if llm_config.api_key:
        llm_markdown = _llm_issue_interpretation(snapshot, request, issue, issue_context, llm_config)
        if llm_markdown:
            markdown = llm_markdown
    return {
        "id": issue["id"],
        "title": issue["title"],
        "summary": issue["summary"],
        "severity": severity,
        "graphs_used": sorted(issue_context),
        "evidence": evidence,
        "recommendations": recommendations,
        "markdown": markdown,
    }


def _heuristic_assessment(issue_id: str, issue_context: dict[str, Any]) -> tuple[str, list[str], list[str]]:
    dep = issue_context.get("dependency_graph", {}).get("metrics", {})
    arch = issue_context.get("architecture_graph", {}).get("metrics", {})
    data = issue_context.get("data_flow_graph", {}).get("metrics", {})
    interface = issue_context.get("interface_graph", {}).get("metrics", {})
    function = issue_context.get("function_graph", {}).get("metrics", {})
    operational = issue_context.get("operational_risk_graph", {}).get("metrics", {})

    if issue_id == "tight_coupling":
        cycle_count = dep.get("cycle_count", 0)
        function_cycles = function.get("cycle_count", 0)
        hotspots = dep.get("top_coupled_modules", [])
        cross_module_calls = function.get("cross_module_call_count", 0)
        severity = "high" if cycle_count > 0 or function_cycles > 0 else "medium" if hotspots or cross_module_calls else "low"
        evidence = [
            f"Dependency cycles: {cycle_count}",
            f"Function call cycles: {function_cycles}",
            f"Cross-module function calls: {cross_module_calls}",
            f"Top coupled modules: {', '.join(item['module'] for item in hotspots[:3]) or 'none'}",
        ]
        recommendations = ["Break cycles and reduce dependence on the hottest modules."]
    elif issue_id == "unclear_boundaries":
        cross = arch.get("cross_package_dependency_count", 0)
        cross_module_calls = function.get("cross_module_call_count", 0)
        hotspots = arch.get("boundary_hotspots", [])
        severity = "high" if cross >= 5 or cross_module_calls >= 10 else "medium" if cross >= 2 or cross_module_calls >= 4 else "low"
        evidence = [
            f"Cross-package dependencies: {cross}",
            f"Cross-module function calls: {cross_module_calls}",
            f"Boundary hotspots: {', '.join(item['package'] for item in hotspots[:3]) or 'none'}",
        ]
        recommendations = ["Clarify package ownership and narrow cross-boundary dependencies."]
    elif issue_id == "low_cohesion":
        diversity = dep.get("dependency_diversity", [])
        score = diversity[0]["dependency_span"] if diversity else 0
        shared = function.get("top_shared_functions", [])
        shared_fan_in = shared[0]["fan_in"] if shared else 0
        severity = "high" if score >= 5 or shared_fan_in >= 4 else "medium" if score >= 3 or shared_fan_in >= 2 else "low"
        evidence = [
            f"Highest dependency span: {score}",
            f"Highest function fan-in: {shared_fan_in}",
            f"Modules with broad span: {', '.join(item['module'] for item in diversity[:3]) or 'none'}",
        ]
        recommendations = ["Split overly broad modules into more focused units."]
    elif issue_id == "poor_separation_of_concerns":
        mixed = data.get("mixed_concern_modules", [])
        cross_module_calls = function.get("cross_module_call_count", 0)
        severity = "high" if len(mixed) >= 3 or cross_module_calls >= 10 else "medium" if mixed or cross_module_calls >= 4 else "low"
        evidence = [
            f"Mixed concern modules: {', '.join(mixed[:5]) or 'none'}",
            f"Cross-module function calls: {cross_module_calls}",
        ]
        recommendations = ["Separate domain logic from persistence and transport concerns."]
    elif issue_id == "bad_interface_api_design":
        chatty = interface.get("chatty_interfaces", [])
        shared = function.get("top_shared_functions", [])
        severity = "high" if len(chatty) >= 2 or any(item["fan_in"] >= 4 for item in shared[:3]) else "medium" if chatty or shared else "low"
        evidence = [
            f"Chatty or highly consumed interfaces: {', '.join(chatty[:5]) or 'none'}",
            f"Top shared functions: {', '.join(item['function'] for item in shared[:3]) or 'none'}",
        ]
        recommendations = ["Simplify and stabilize heavily consumed interface surfaces."]
    elif issue_id == "data_ownership_confusion":
        multi = data.get("multi_writer_targets", [])
        severity = "high" if multi else "low"
        evidence = [f"Multi-writer targets: {', '.join(multi[:5]) or 'none'}"]
        recommendations = ["Assign a clear owner for each shared data target."]
    elif issue_id == "scalability_bottlenecks":
        hotspots = dep.get("top_coupled_modules", [])
        shared = data.get("shared_targets", [])
        severity = "high" if shared or dep.get("cycle_count", 0) > 0 else "medium" if hotspots else "low"
        evidence = [
            f"Shared flow targets: {', '.join(shared[:5]) or 'none'}",
            f"Top dependency hotspots: {', '.join(item['module'] for item in hotspots[:3]) or 'none'}",
        ]
        recommendations = ["Reduce central chokepoints and shorten synchronous dependency paths."]
    elif issue_id == "weak_fault_isolation":
        articulations = dep.get("articulation_points", [])
        function_articulations = function.get("articulation_points", [])
        cycles = dep.get("cycle_count", 0)
        severity = "high" if articulations or function_articulations or cycles else "low"
        evidence = [
            f"Articulation points: {', '.join(articulations[:5]) or 'none'}",
            f"Function bridge points: {', '.join(function_articulations[:5]) or 'none'}",
            f"Cycle count: {cycles}",
        ]
        recommendations = ["Introduce isolation boundaries around bridge nodes and cycle-heavy paths."]
    elif issue_id == "lack_of_observability":
        coverage = operational.get("observability_coverage", 0.0)
        severity = "high" if coverage < 0.25 else "medium" if coverage < 0.5 else "low"
        evidence = [f"Observability coverage: {coverage}"]
        recommendations = ["Add logging, metrics, or tracing to poorly instrumented modules."]
    elif issue_id == "security_not_built_in":
        coverage = operational.get("security_coverage", 0.0)
        severity = "high" if coverage < 0.25 else "medium" if coverage < 0.5 else "low"
        evidence = [f"Security capability coverage: {coverage}"]
        recommendations = ["Make trust boundaries and security-sensitive paths explicit."]
    else:
        severity = "low"
        evidence = ["No heuristic implemented."]
        recommendations = ["Review manually."]
    return severity, evidence, recommendations


def _issue_markdown(issue: dict[str, Any], severity: str, evidence: list[str], recommendations: list[str]) -> str:
    lines = [
        f"## {issue['title']}",
        "",
        f"- Severity: `{severity}`",
        f"- Summary: {issue['summary']}",
        "",
        "### Evidence",
    ]
    lines.extend(f"- {item}" for item in evidence)
    lines.extend(["", "### Recommendations"])
    lines.extend(f"- {item}" for item in recommendations)
    return "\n".join(lines) + "\n"


def _llm_issue_interpretation(
    snapshot: RepositorySnapshot,
    request: ArchitectureRequest,
    issue: dict[str, Any],
    issue_context: dict[str, Any],
    llm_config: LLMConfig,
) -> str | None:
    system_prompt = (
        "You are an architecture inspection assistant. "
        "Assess one architecture issue at a time. "
        "Ground every claim in the supplied graph evidence and repository facts."
    )
    user_prompt = (
        f"Repository: {snapshot.github_url}\n"
        f"Branch: {snapshot.branch}\n"
        f"Issue: {issue['title']}\n"
        f"Issue summary: {issue['summary']}\n"
        f"Inspection goal: {issue['inspection_goal']}\n"
        f"Relevant graph analyses: {issue_context}\n"
        "Write markdown with sections Severity, Evidence, and Recommendations. "
        "Keep it concise and evidence-grounded."
    )
    return llm_completion(system_prompt, user_prompt, llm_config)
