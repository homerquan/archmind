from __future__ import annotations

from pathlib import Path

from archmind.graphing import build_architecture_graph
from archmind.models import RepositorySnapshot


def test_build_architecture_graph_detects_internal_and_external_imports(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    pkg = repo / "sample"
    pkg.mkdir(parents=True)
    (pkg / "__init__.py").write_text("", encoding="utf-8")
    (pkg / "a.py").write_text("from sample import b\nimport requests\n", encoding="utf-8")
    (pkg / "b.py").write_text("from sample import a\n", encoding="utf-8")

    snapshot = RepositorySnapshot(
        github_url="https://github.com/example/project",
        branch="main",
        commit_sha="abc123",
        fetched_at="2026-03-13T00:00:00+00:00",
        root_path=str(repo),
        language_hints=["python"],
        manifests=[],
    )

    graph, feature_schema, inventory = build_architecture_graph(snapshot, repo)

    node_ids = {node.id for node in graph.nodes}
    assert "module:sample.a" in node_ids
    assert "module:sample.b" in node_ids
    assert "external:requests" in node_ids
    assert feature_schema["schema_version"] == 1
    assert inventory["modules"]["sample.a"]["internal_imports"] == ["sample.b"]
    assert inventory["modules"]["sample.a"]["external_imports"] == ["requests"]
