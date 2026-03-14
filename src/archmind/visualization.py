from __future__ import annotations

from collections import defaultdict
from pathlib import Path

from archmind.models import ArchitectureGraph
from archmind.utils import ensure_dir


GRAPH_RENDER_LIMITS = {
    "dependency_graph": 140,
    "architecture_graph": 180,
    "data_flow_graph": 120,
    "interface_graph": 160,
    "function_graph": 180,
    "operational_risk_graph": 120,
}

NODE_COLORS = {
    "repository": "#1d3557",
    "package": "#457b9d",
    "module": "#8ecae6",
    "function": "#a8dadc",
    "api": "#ffb703",
    "entrypoint": "#fb8500",
    "database": "#e76f51",
    "cache": "#f4a261",
    "queue": "#e9c46a",
    "external_service": "#d4a373",
    "external_dependency": "#b08968",
    "metric": "#90be6d",
    "security_capability": "#f94144",
}

EDGE_COLORS = {
    "imports": "#577590",
    "depends_on": "#277da1",
    "calls": "#4d908e",
    "contains": "#adb5bd",
    "reads_from": "#90be6d",
    "writes_to": "#f3722c",
    "emits_to": "#f8961e",
    "uses": "#f94144",
    "implements": "#7b2cbf",
    "evaluated_by": "#6c757d",
}


def write_graph_pdf(graph: ArchitectureGraph, output_path: Path) -> Path:
    ensure_dir(output_path.parent)
    try:
        _write_graph_pdf_with_matplotlib(graph, output_path)
    except Exception:
        output_path.write_bytes(_fallback_pdf_bytes(graph))
    return output_path


def _write_graph_pdf_with_matplotlib(graph: ArchitectureGraph, output_path: Path) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import networkx as nx

    graph_id = str(graph.metadata.get("graph_id", "graph"))
    rendered = _renderable_graph(graph)
    nx_graph = _to_networkx(rendered)

    figure, axis = plt.subplots(figsize=(16, 10), constrained_layout=True)
    axis.set_facecolor("#f8fbff")
    figure.patch.set_facecolor("#f8fbff")

    title = str(graph.metadata.get("title", "ArchMind Graph Visualization"))
    subtitle = (
        f"{graph_id} | rendered nodes={nx_graph.number_of_nodes()} of total={len(graph.nodes)}"
        f" | rendered edges={nx_graph.number_of_edges()} of total={len(graph.edges)}"
    )
    axis.set_title(f"{title}\n{subtitle}", fontsize=15, fontweight="bold", loc="left")

    if nx_graph.number_of_nodes() == 0:
        axis.text(
            0.02,
            0.75,
            "No graphable entities detected for this graph.",
            transform=axis.transAxes,
            fontsize=14,
            fontweight="bold",
            color="#1d3557",
        )
        axis.text(
            0.02,
            0.68,
            "This usually means the current language scanner did not extract any nodes.",
            transform=axis.transAxes,
            fontsize=11,
            color="#495057",
        )
        axis.axis("off")
        figure.savefig(output_path, format="pdf", bbox_inches="tight")
        plt.close(figure)
        return

    if nx_graph.number_of_edges() == 0:
        axis.text(
            0.02,
            0.04,
            "Graph contains nodes but no inferred relationships.",
            transform=axis.transAxes,
            fontsize=10,
            color="#6c757d",
        )

    positions = _layout_positions(nx_graph, graph_id)
    node_ids = list(nx_graph.nodes)
    node_sizes = [_node_size(nx_graph, node_id) for node_id in node_ids]
    node_colors = [NODE_COLORS.get(nx_graph.nodes[node_id].get("type", ""), "#ced4da") for node_id in node_ids]
    edge_colors = [EDGE_COLORS.get(data.get("type", ""), "#adb5bd") for _, _, data in nx_graph.edges(data=True)]
    edge_widths = [_edge_width(data.get("type", "")) for _, _, data in nx_graph.edges(data=True)]

    nx.draw_networkx_edges(
        nx_graph,
        positions,
        ax=axis,
        edge_color=edge_colors,
        width=edge_widths,
        alpha=0.25,
        arrows=nx_graph.is_directed(),
        arrowsize=8,
        connectionstyle="arc3,rad=0.06",
    )
    nx.draw_networkx_nodes(
        nx_graph,
        positions,
        ax=axis,
        node_size=node_sizes,
        node_color=node_colors,
        linewidths=0.6,
        edgecolors="#1d3557",
        alpha=0.96,
    )

    labels = _label_subset(nx_graph)
    nx.draw_networkx_labels(nx_graph, positions, labels=labels, ax=axis, font_size=7, font_family="DejaVu Sans")

    axis.axis("off")
    figure.savefig(output_path, format="pdf", bbox_inches="tight")
    plt.close(figure)


def _renderable_graph(graph: ArchitectureGraph) -> ArchitectureGraph:
    graph_id = str(graph.metadata.get("graph_id", "graph"))
    limit = GRAPH_RENDER_LIMITS.get(graph_id, 140)
    if len(graph.nodes) <= limit:
        return graph

    adjacency = _undirected_adjacency(graph)
    nodes_by_id = {node.id: node for node in graph.nodes}
    ranked_nodes = sorted(
        graph.nodes,
        key=lambda node: (
            len(adjacency.get(node.id, set())),
            _node_priority(node.type),
            node.label,
        ),
        reverse=True,
    )

    selected_ids: set[str] = set()
    for node in ranked_nodes[: min(30, limit)]:
        selected_ids.add(node.id)
        if len(selected_ids) >= limit:
            break
        neighbors = sorted(
            adjacency.get(node.id, set()),
            key=lambda neighbor: len(adjacency.get(neighbor, set())),
            reverse=True,
        )
        for neighbor in neighbors[:8]:
            selected_ids.add(neighbor)
            if len(selected_ids) >= limit:
                break
        if len(selected_ids) >= limit:
            break

    important_types = {"repository", "entrypoint", "package", "database", "queue", "external_service", "security_capability"}
    for node in graph.nodes:
        if node.type in important_types:
            selected_ids.add(node.id)
        if len(selected_ids) >= limit:
            break

    selected_ids = set(list(selected_ids)[:limit])
    nodes = [node for node in graph.nodes if node.id in selected_ids]
    edges = [edge for edge in graph.edges if edge.source in selected_ids and edge.target in selected_ids]
    metadata = dict(graph.metadata)
    metadata["render_sampled"] = True
    metadata["rendered_node_count"] = len(nodes)
    metadata["rendered_edge_count"] = len(edges)
    return ArchitectureGraph(repository=graph.repository, nodes=nodes, edges=edges, metadata=metadata)


def _to_networkx(graph: ArchitectureGraph):
    import networkx as nx

    nx_graph = nx.DiGraph()
    for node in graph.nodes:
        nx_graph.add_node(node.id, type=node.type, label=node.label, metadata=node.metadata)
    for edge in graph.edges:
        if edge.source in nx_graph and edge.target in nx_graph:
            nx_graph.add_edge(edge.source, edge.target, type=edge.type, metadata=edge.metadata)
    return nx_graph


def _layout_positions(nx_graph, graph_id: str):
    import networkx as nx

    if nx_graph.number_of_nodes() == 1:
        only = next(iter(nx_graph.nodes))
        return {only: (0.0, 0.0)}

    if graph_id in {"data_flow_graph", "operational_risk_graph", "interface_graph"}:
        layers = _layer_mapping(nx_graph, graph_id)
        for node_id, layer in layers.items():
            nx_graph.nodes[node_id]["layer"] = layer
        return nx.multipartite_layout(nx_graph, subset_key="layer", align="vertical")

    if graph_id == "architecture_graph":
        return nx.kamada_kawai_layout(nx_graph.to_undirected())

    if graph_id == "function_graph":
        initial = nx.kamada_kawai_layout(nx_graph.to_undirected())
        return nx.spring_layout(
            nx_graph,
            seed=7,
            pos=initial,
            k=1.2 / max(1, nx_graph.number_of_nodes() ** 0.25),
            iterations=120,
        )

    if graph_id == "dependency_graph":
        return nx.spring_layout(nx_graph, seed=11, k=1.0 / max(1, nx_graph.number_of_nodes() ** 0.3), iterations=100)

    return nx.kamada_kawai_layout(nx_graph.to_undirected())


def _layer_mapping(nx_graph, graph_id: str) -> dict[str, int]:
    mapping: dict[str, int] = {}
    for node_id, attrs in nx_graph.nodes(data=True):
        node_type = attrs.get("type", "")
        if graph_id == "data_flow_graph":
            if node_type == "module":
                mapping[node_id] = 0
            else:
                mapping[node_id] = 1
        elif graph_id == "interface_graph":
            if node_type == "entrypoint":
                mapping[node_id] = 0
            elif node_type == "module":
                mapping[node_id] = 1
            else:
                mapping[node_id] = 2
        elif graph_id == "operational_risk_graph":
            if node_type == "module":
                mapping[node_id] = 0
            else:
                mapping[node_id] = 1
        else:
            mapping[node_id] = 0
    return mapping
def _label_subset(nx_graph) -> dict[str, str]:
    ranked = sorted(
        nx_graph.degree,
        key=lambda item: (item[1], nx_graph.nodes[item[0]].get("label", item[0])),
        reverse=True,
    )
    label_budget = 40 if nx_graph.number_of_nodes() > 80 else 70
    selected = {node_id for node_id, _ in ranked[:label_budget]}
    labels = {}
    for node_id in selected:
        label = str(nx_graph.nodes[node_id].get("label", node_id))
        labels[node_id] = _truncate(label, 26)
    return labels


def _node_size(nx_graph, node_id: str) -> float:
    degree = nx_graph.degree[node_id]
    node_type = nx_graph.nodes[node_id].get("type", "")
    base = 160
    if node_type in {"package", "module", "function"}:
        base = 120
    if node_type in {"database", "queue", "external_service", "security_capability", "metric"}:
        base = 220
    return base + min(900, degree * 22)


def _edge_width(edge_type: str) -> float:
    if edge_type in {"calls", "imports", "depends_on"}:
        return 0.8
    if edge_type in {"writes_to", "reads_from", "emits_to"}:
        return 1.0
    return 0.6


def _undirected_adjacency(graph: ArchitectureGraph) -> dict[str, set[str]]:
    adjacency: dict[str, set[str]] = defaultdict(set)
    for node in graph.nodes:
        adjacency[node.id] = set()
    for edge in graph.edges:
        adjacency.setdefault(edge.source, set()).add(edge.target)
        adjacency.setdefault(edge.target, set()).add(edge.source)
    return dict(adjacency)


def _node_priority(node_type: str) -> int:
    ordering = {
        "repository": 7,
        "package": 6,
        "module": 5,
        "function": 4,
        "api": 4,
        "entrypoint": 6,
        "database": 6,
        "queue": 6,
        "external_service": 6,
        "external_dependency": 3,
        "metric": 5,
        "security_capability": 5,
    }
    return ordering.get(node_type, 1)


def _truncate(value: str, max_length: int) -> str:
    if len(value) <= max_length:
        return value
    return value[: max_length - 3] + "..."


def _fallback_pdf_bytes(graph: ArchitectureGraph) -> bytes:
    title = _escape_pdf_text(str(graph.metadata.get("title", "ArchMind Graph Visualization")))
    subtitle = _escape_pdf_text(str(graph.metadata.get("graph_id", "graph")))
    lines = [
        "q",
        "0.98 0.99 1 rg 0 0 842 595 re f",
        f"BT /F1 18 Tf 36 560 Td ({title}) Tj ET",
        f"BT /F1 10 Tf 36 542 Td ({subtitle}) Tj ET",
        f"BT /F1 12 Tf 36 500 Td (Visualization backend unavailable. Nodes={len(graph.nodes)} Edges={len(graph.edges)}) Tj ET",
        "Q",
    ]
    return _build_pdf("\n".join(lines).encode("latin-1"))


def _escape_pdf_text(value: str) -> str:
    return value.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def _build_pdf(content_stream: bytes) -> bytes:
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 842 595] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        f"<< /Length {len(content_stream)} >>\nstream\n".encode("latin-1") + content_stream + b"endstream",
    ]

    chunks = [b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n"]
    offsets: list[int] = []
    for index, obj in enumerate(objects, start=1):
        offsets.append(sum(len(chunk) for chunk in chunks))
        chunks.append(f"{index} 0 obj\n".encode("latin-1"))
        chunks.append(obj)
        chunks.append(b"\nendobj\n")

    xref_offset = sum(len(chunk) for chunk in chunks)
    chunks.append(f"xref\n0 {len(objects) + 1}\n".encode("latin-1"))
    chunks.append(b"0000000000 65535 f \n")
    for offset in offsets:
        chunks.append(f"{offset:010d} 00000 n \n".encode("latin-1"))
    chunks.append(
        (
            f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\n"
            f"startxref\n{xref_offset}\n%%EOF\n"
        ).encode("latin-1")
    )
    return b"".join(chunks)
