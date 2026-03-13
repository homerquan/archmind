from __future__ import annotations

import math
from pathlib import Path

from archmind.models import ArchitectureGraph
from archmind.utils import ensure_dir


PAGE_WIDTH = 842
PAGE_HEIGHT = 595


def write_graph_pdf(graph: ArchitectureGraph, output_path: Path) -> Path:
    ensure_dir(output_path.parent)
    content = _render_graph_pdf_content(graph)
    pdf_bytes = _build_pdf(content.encode("latin-1"))
    output_path.write_bytes(pdf_bytes)
    return output_path


def _render_graph_pdf_content(graph: ArchitectureGraph) -> str:
    nodes = [node for node in graph.nodes if node.type != "repository"]
    repository_nodes = [node for node in graph.nodes if node.type == "repository"]
    positions = _layout_positions(nodes)
    if repository_nodes:
        positions[repository_nodes[0].id] = (PAGE_WIDTH / 2 - 45, PAGE_HEIGHT - 70)
    title = _escape_pdf_text(str(graph.metadata.get("title", "ArchMind Graph Visualization")))
    subtitle = _escape_pdf_text(str(graph.metadata.get("graph_id", "graph")))

    lines = [
        "q",
        "0.98 0.99 1 rg 0 0 842 595 re f",
        f"BT /F1 18 Tf 36 560 Td ({title}) Tj ET",
        f"BT /F1 10 Tf 36 542 Td ({subtitle}) Tj ET",
    ]

    for edge in graph.edges:
        if edge.source not in positions or edge.target not in positions:
            continue
        x1, y1 = _edge_anchor(positions[edge.source])
        x2, y2 = _edge_anchor(positions[edge.target])
        lines.append("0.72 0.78 0.85 RG 1 w")
        lines.append(f"{x1:.2f} {y1:.2f} m {x2:.2f} {y2:.2f} l S")

    for node in graph.nodes:
        if node.id not in positions:
            continue
        x, y = positions[node.id]
        fill = _node_fill(node.type)
        label = _escape_pdf_text(_truncate(node.label, 22))
        lines.append(f"{fill} rg 0.16 0.2 0.3 RG 1 w")
        lines.append(f"{x:.2f} {y:.2f} 90 24 re B")
        lines.append(f"BT /F1 8 Tf {x + 6:.2f} {y + 8:.2f} Td ({label}) Tj ET")

    lines.append("Q")
    return "\n".join(lines) + "\n"


def _layout_positions(nodes) -> dict[str, tuple[float, float]]:
    if not nodes:
        return {}
    radius = min(PAGE_WIDTH, PAGE_HEIGHT) * 0.32
    center_x = PAGE_WIDTH / 2
    center_y = PAGE_HEIGHT / 2 - 20
    positions: dict[str, tuple[float, float]] = {}
    for index, node in enumerate(nodes):
        angle = (2 * math.pi * index) / max(1, len(nodes))
        x = center_x + radius * math.cos(angle) - 45
        y = center_y + radius * math.sin(angle) - 12
        positions[node.id] = (x, y)
    return positions


def _edge_anchor(position: tuple[float, float]) -> tuple[float, float]:
    x, y = position
    return x + 45, y + 12


def _node_fill(node_type: str) -> str:
    if node_type == "module":
        return "0.74 0.87 0.97"
    if node_type == "external_dependency":
        return "0.93 0.82 0.72"
    return "0.85 0.88 0.92"


def _truncate(value: str, max_length: int) -> str:
    if len(value) <= max_length:
        return value
    return value[: max_length - 3] + "..."


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
