from __future__ import annotations

import os
from typing import Any

from archmind.models import AnalysisResult, ArchitectureRequest, LLMConfig, RepositorySnapshot


PROVIDER_MODELS = {
    "openai": "openai/gpt-4o-mini",
    "anthropic": "anthropic/claude-3-5-haiku-latest",
    "gemini": "gemini/gemini-1.5-flash",
}

PROVIDER_ENV_VARS = {
    "openai": ["OPENAI_API_KEY"],
    "anthropic": ["ANTHROPIC_API_KEY"],
    "gemini": ["GEMINI_API_KEY", "GOOGLE_API_KEY"],
}


def collect_llm_config(ui, provider_hint: str | None = None) -> LLMConfig:
    provider = ui.choose("LLM provider", ["openai", "anthropic", "gemini"], default=provider_hint or "openai")
    api_key, source = resolve_api_key(provider, ui)
    return LLMConfig(provider=provider, model=PROVIDER_MODELS[provider], api_key=api_key, api_key_source=source)


def resolve_api_key(provider: str, ui) -> tuple[str | None, str]:
    for env_name in PROVIDER_ENV_VARS[provider]:
        value = os.getenv(env_name)
        if value:
            return value, f"env:{env_name}"
    api_key = ui.prompt(f"{provider.title()} API key (leave blank for local fallback)", secret=True)
    if api_key:
        return api_key, "prompt"
    return None, "none"


def interpret_findings(
    snapshot: RepositorySnapshot,
    request: ArchitectureRequest,
    metrics: dict[str, Any],
    findings: list[dict[str, Any]],
    llm_config: LLMConfig,
) -> tuple[str, list[dict[str, Any]]]:
    if llm_config.api_key:
        content = _litellm_interpret(snapshot, request, metrics, findings, llm_config)
        if content is not None:
            recommendations = _recommendations_from_findings(findings)
            return content, recommendations
    return _fallback_interpretation(snapshot, metrics, findings)


def _litellm_interpret(
    snapshot: RepositorySnapshot,
    request: ArchitectureRequest,
    metrics: dict[str, Any],
    findings: list[dict[str, Any]],
    llm_config: LLMConfig,
) -> str | None:
    try:  # pragma: no cover - optional dependency and network path
        from litellm import completion
    except Exception:
        return None

    system_prompt = (
        "You are an architecture analysis assistant. "
        "Ground every claim in the provided repository facts and graph findings. "
        "Do not invent code structure not present in the evidence."
    )
    user_prompt = (
        f"Repository: {snapshot.github_url}\n"
        f"Branch: {snapshot.branch}\n"
        f"Commit: {snapshot.commit_sha}\n"
        f"Requested output file: {request.output_markdown_path}\n"
        f"Metrics: {metrics}\n"
        f"Findings: {findings}\n"
        "Write a concise markdown explanation with sections for Overview, Key Findings, and Recommendations."
    )
    try:  # pragma: no cover - optional dependency and network path
        response = completion(
            model=llm_config.model,
            api_key=llm_config.api_key,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.2,
        )
        return response["choices"][0]["message"]["content"]
    except Exception:
        return None


def _fallback_interpretation(
    snapshot: RepositorySnapshot,
    metrics: dict[str, Any],
    findings: list[dict[str, Any]],
) -> tuple[str, list[dict[str, Any]]]:
    top_findings = findings[:5]
    lines = [
        "# Architecture Findings",
        "",
        "## Overview",
        f"- Repository: `{snapshot.github_url}`",
        f"- Branch: `{snapshot.branch}`",
        f"- Commit: `{snapshot.commit_sha}`",
        f"- Modules analyzed: `{metrics['module_count']}`",
        f"- Internal dependency edges: `{metrics['edge_count']}`",
        "",
        "## Key Findings",
    ]
    if not top_findings:
        lines.append("- No major structural findings were detected in the initial analysis set.")
    for finding in top_findings:
        lines.append(
            f"- **{finding['kind']}**: {finding['summary']} "
            f"(targets: {', '.join(finding['target_entities'])})"
        )
    lines.extend(["", "## Recommendations"])
    recommendations = _recommendations_from_findings(findings)
    if not recommendations:
        lines.append("- Keep the dependency graph stable and rerun after larger refactors.")
    for item in recommendations:
        lines.append(f"- {item['summary']}")
    return "\n".join(lines) + "\n", recommendations


def _recommendations_from_findings(findings: list[dict[str, Any]]) -> list[dict[str, Any]]:
    recommendations: list[dict[str, Any]] = []
    for finding in findings:
        kind = finding["kind"]
        targets = finding["target_entities"]
        if kind == "cycle":
            recommendations.append(
                {
                    "kind": "break_cycle",
                    "targets": targets,
                    "summary": f"Break the dependency cycle involving {', '.join(targets)} with an interface or dependency inversion boundary.",
                }
            )
        elif kind == "bridge_node":
            recommendations.append(
                {
                    "kind": "stabilize_bridge",
                    "targets": targets,
                    "summary": f"Review {targets[0]} as a bridge module and isolate responsibilities if it is coordinating unrelated flows.",
                }
            )
        elif kind == "coupling_hotspot":
            recommendations.append(
                {
                    "kind": "reduce_coupling",
                    "targets": targets,
                    "summary": f"Reduce dependency pressure around {targets[0]} by moving shared concerns behind narrower interfaces.",
                }
            )
    return recommendations[:5]
