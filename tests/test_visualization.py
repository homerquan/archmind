from __future__ import annotations

from pathlib import Path

from archmind.models import ArchitectureGraph, GraphEdge, GraphNode
from archmind.visualization import _renderable_graph, write_graph_pdf


def test_write_graph_pdf_creates_pdf_for_non_empty_graph(tmp_path: Path) -> None:
    graph = ArchitectureGraph(
        repository="repo",
        metadata={"graph_id": "dependency_graph", "title": "Dependency Graph"},
        nodes=[
            GraphNode("module:a", "module", "a", {}),
            GraphNode("module:b", "module", "b", {}),
            GraphNode("external:req", "external_dependency", "requests", {}),
        ],
        edges=[
            GraphEdge("module:a", "module:b", "imports", {}),
            GraphEdge("module:a", "external:req", "depends_on", {}),
        ],
    )

    output_path = tmp_path / "graph.pdf"
    write_graph_pdf(graph, output_path)

    assert output_path.exists()
    assert output_path.read_bytes().startswith(b"%PDF")
    assert output_path.stat().st_size > 200


def test_renderable_graph_samples_large_graphs() -> None:
    nodes = [GraphNode(f"function:n{index}", "function", f"n{index}", {}) for index in range(240)]
    edges = [GraphEdge(f"function:n{index}", f"function:n{index + 1}", "calls", {}) for index in range(239)]
    graph = ArchitectureGraph(
        repository="repo",
        metadata={"graph_id": "function_graph", "title": "Function Graph"},
        nodes=nodes,
        edges=edges,
    )

    rendered = _renderable_graph(graph)

    assert rendered.metadata["render_sampled"] is True
    assert len(rendered.nodes) <= 180
    assert len(rendered.edges) <= len(graph.edges)
