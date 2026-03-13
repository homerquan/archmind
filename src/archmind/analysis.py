from __future__ import annotations

import csv
from collections import defaultdict
from pathlib import Path
from typing import Any

from archmind.models import ArchitectureGraph


def _internal_module_graph(graph: ArchitectureGraph) -> dict[str, set[str]]:
    adjacency: dict[str, set[str]] = defaultdict(set)
    modules = {node.id for node in graph.nodes if node.type == "module"}
    for module in modules:
        adjacency[module] = set()
    for edge in graph.edges:
        if edge.type == "imports" and edge.source in modules and edge.target in modules:
            adjacency[edge.source].add(edge.target)
    return dict(adjacency)


def _reverse_graph(adjacency: dict[str, set[str]]) -> dict[str, set[str]]:
    reverse = {node: set() for node in adjacency}
    for source, targets in adjacency.items():
        for target in targets:
            reverse.setdefault(target, set()).add(source)
    return reverse


def strongly_connected_components(adjacency: dict[str, set[str]]) -> list[list[str]]:
    index = 0
    indices: dict[str, int] = {}
    lowlinks: dict[str, int] = {}
    stack: list[str] = []
    on_stack: set[str] = set()
    components: list[list[str]] = []

    def visit(node: str) -> None:
        nonlocal index
        indices[node] = index
        lowlinks[node] = index
        index += 1
        stack.append(node)
        on_stack.add(node)

        for neighbor in adjacency.get(node, set()):
            if neighbor not in indices:
                visit(neighbor)
                lowlinks[node] = min(lowlinks[node], lowlinks[neighbor])
            elif neighbor in on_stack:
                lowlinks[node] = min(lowlinks[node], indices[neighbor])

        if lowlinks[node] == indices[node]:
            component: list[str] = []
            while stack:
                item = stack.pop()
                on_stack.remove(item)
                component.append(item)
                if item == node:
                    break
            components.append(sorted(component))

    for node in adjacency:
        if node not in indices:
            visit(node)

    return sorted(components, key=lambda component: (-len(component), component))


def articulation_points(adjacency: dict[str, set[str]]) -> list[str]:
    undirected: dict[str, set[str]] = {node: set(targets) for node, targets in adjacency.items()}
    for source, targets in adjacency.items():
        for target in targets:
            undirected.setdefault(target, set()).add(source)

    index = 0
    indices: dict[str, int] = {}
    lowlinks: dict[str, int] = {}
    parent: dict[str, str | None] = {}
    points: set[str] = set()

    def dfs(node: str) -> None:
        nonlocal index
        indices[node] = index
        lowlinks[node] = index
        index += 1
        children = 0

        for neighbor in undirected.get(node, set()):
            if neighbor not in indices:
                parent[neighbor] = node
                children += 1
                dfs(neighbor)
                lowlinks[node] = min(lowlinks[node], lowlinks[neighbor])
                if parent.get(node) is None and children > 1:
                    points.add(node)
                if parent.get(node) is not None and lowlinks[neighbor] >= indices[node]:
                    points.add(node)
            elif neighbor != parent.get(node):
                lowlinks[node] = min(lowlinks[node], indices[neighbor])

    for node in undirected:
        if node not in indices:
            parent[node] = None
            dfs(node)

    return sorted(points)


def write_dsm(adjacency: dict[str, set[str]], path: Path) -> list[list[str]]:
    modules = sorted(adjacency)
    rows: list[list[str]] = [["module", *modules]]
    for module in modules:
        row = [module]
        for target in modules:
            row.append("1" if target in adjacency[module] else "0")
        rows.append(row)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerows(rows)
    return rows


def analyze_graph(graph: ArchitectureGraph, dsm_path: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    adjacency = _internal_module_graph(graph)
    reverse = _reverse_graph(adjacency)
    modules = sorted(adjacency)
    sccs = strongly_connected_components(adjacency)
    cycles = [component for component in sccs if len(component) > 1]
    articulations = articulation_points(adjacency)
    dsm_rows = write_dsm(adjacency, dsm_path)

    fan_out = {module: len(targets) for module, targets in adjacency.items()}
    fan_in = {module: len(reverse.get(module, set())) for module in adjacency}
    total_modules = max(1, len(modules) - 1)
    centrality = {
        module: round((fan_in[module] + fan_out[module]) / max(1, 2 * total_modules), 3)
        for module in modules
    }

    top_coupled = sorted(
        modules,
        key=lambda module: (fan_in[module] + fan_out[module], fan_in[module], fan_out[module], module),
        reverse=True,
    )[:5]
    findings: list[dict[str, Any]] = []

    for component in cycles:
        findings.append(
            {
                "kind": "cycle",
                "severity": "high" if len(component) > 2 else "medium",
                "target_entities": component,
                "summary": f"Dependency cycle detected across {', '.join(component)}.",
                "evidence": {"component_size": len(component)},
            }
        )

    for module in articulations[:5]:
        findings.append(
            {
                "kind": "bridge_node",
                "severity": "medium",
                "target_entities": [module],
                "summary": f"{module} behaves like a bridge node in the dependency graph.",
                "evidence": {
                    "fan_in": fan_in[module],
                    "fan_out": fan_out[module],
                    "centrality": centrality[module],
                },
            }
        )

    for module in top_coupled[:3]:
        findings.append(
            {
                "kind": "coupling_hotspot",
                "severity": "medium" if (fan_in[module] + fan_out[module]) > 1 else "low",
                "target_entities": [module],
                "summary": f"{module} has elevated coupling pressure.",
                "evidence": {
                    "fan_in": fan_in[module],
                    "fan_out": fan_out[module],
                    "centrality": centrality[module],
                },
            }
        )

    metrics = {
        "module_count": len(modules),
        "edge_count": sum(len(targets) for targets in adjacency.values()),
        "dsm_generated": bool(dsm_rows),
        "fan_in": fan_in,
        "fan_out": fan_out,
        "strongly_connected_components": sccs,
        "cycle_count": len(cycles),
        "articulation_points": articulations,
        "centrality": centrality,
    }
    return metrics, findings
