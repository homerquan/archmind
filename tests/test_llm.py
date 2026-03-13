from __future__ import annotations

from archmind.llm import interpret_findings
from archmind.models import ArchitectureRequest, LLMConfig, RepositorySnapshot


def test_llm_config_safe_handling_and_fallback() -> None:
    snapshot = RepositorySnapshot(
        github_url="https://github.com/example/project",
        branch="main",
        commit_sha="abc123",
        fetched_at="2026-03-13T00:00:00+00:00",
        root_path="/tmp/repo",
        language_hints=["python"],
        manifests=[],
    )
    request = ArchitectureRequest(github_url=snapshot.github_url)
    config = LLMConfig(provider="openai", model="openai/gpt-4o-mini", api_key=None, api_key_source="none")
    metrics = {"module_count": 3, "edge_count": 2, "cycle_count": 1}
    findings = [
        {
            "kind": "cycle",
            "severity": "medium",
            "target_entities": ["module:a", "module:b"],
            "summary": "Dependency cycle detected.",
            "evidence": {},
        }
    ]

    explanations, recommendations = interpret_findings(snapshot, request, metrics, findings, config)

    assert "Architecture Findings" in explanations
    assert recommendations
    assert "api_key" not in config.safe_dict()
