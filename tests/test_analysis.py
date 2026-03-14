from __future__ import annotations

from pathlib import Path

from archmind.analysis import analyze_dependency_graph, analyze_function_graph
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


def test_analyze_function_graph_detects_cross_module_hotspot() -> None:
    graph = ArchitectureGraph(
        repository="repo",
        metadata={"graph_id": "function_graph"},
        nodes=[
            GraphNode("module:a", "module", "a", {}),
            GraphNode("module:b", "module", "b", {}),
            GraphNode("function:a.entry", "function", "a.entry", {"module": "a", "entrypoint": True}),
            GraphNode("function:a.worker", "function", "a.worker", {"module": "a", "entrypoint": False}),
            GraphNode("function:b.shared", "function", "b.shared", {"module": "b", "entrypoint": False}),
        ],
        edges=[
            GraphEdge("module:a", "function:a.entry", "contains", {}),
            GraphEdge("module:a", "function:a.worker", "contains", {}),
            GraphEdge("module:b", "function:b.shared", "contains", {}),
            GraphEdge("function:a.entry", "function:a.worker", "calls", {}),
            GraphEdge("function:a.entry", "function:b.shared", "calls", {}),
            GraphEdge("function:a.worker", "function:b.shared", "calls", {}),
        ],
    )

    metrics, findings = analyze_function_graph(graph)

    assert metrics["function_count"] == 3
    assert metrics["cross_module_call_count"] == 2
    assert metrics["entrypoint_function_count"] == 1
    kinds = {item["kind"] for item in findings}
    assert "function_hotspot" in kinds
