from __future__ import annotations

from pathlib import Path

from archmind.analysis import analyze_dependency_graph
from archmind.models import ArchitectureGraph, GraphEdge, GraphNode


def test_analyze_dependency_graph_detects_cycle_and_bridge(tmp_path: Path) -> None:
    graph = ArchitectureGraph(
        repository="repo",
        metadata={"graph_id": "dependency_graph"},
        nodes=[
            GraphNode("repository:root", "repository", "repo", {}),
            GraphNode("module:a", "module", "a", {}),
            GraphNode("module:b", "module", "b", {}),
            GraphNode("module:c", "module", "c", {}),
            GraphNode("module:d", "module", "d", {}),
        ],
        edges=[
            GraphEdge("module:a", "module:b", "imports", {}),
            GraphEdge("module:b", "module:a", "imports", {}),
            GraphEdge("module:b", "module:c", "imports", {}),
            GraphEdge("module:c", "module:d", "imports", {}),
        ],
    )

    metrics, findings = analyze_dependency_graph(graph, tmp_path / "dsm.csv")

    assert metrics["cycle_count"] == 1
    kinds = {item["kind"] for item in findings}
    assert "cycle" in kinds
    assert (tmp_path / "dsm.csv").exists()
