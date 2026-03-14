from __future__ import annotations

import csv
from collections import defaultdict
from pathlib import Path
from typing import Any

from archmind.models import ArchitectureGraph


def analyze_graph_bundle(graphs: dict[str, ArchitectureGraph], analysis_dir: Path) -> dict[str, dict[str, Any]]:
    analysis_dir.mkdir(parents=True, exist_ok=True)
    results: dict[str, dict[str, Any]] = {}
    for graph_id, graph in graphs.items():
        if graph_id == "dependency_graph":
            metrics, findings = analyze_dependency_graph(graph, analysis_dir / "dependency_graph_dsm.csv")
        elif graph_id == "architecture_graph":
            metrics, findings = analyze_architecture_graph(graph)
        elif graph_id == "data_flow_graph":
            metrics, findings = analyze_data_flow_graph(graph)
        elif graph_id == "interface_graph":
            metrics, findings = analyze_interface_graph(graph)
        elif graph_id == "function_graph":
            metrics, findings = analyze_function_graph(graph)
        elif graph_id == "operational_risk_graph":
            metrics, findings = analyze_operational_risk_graph(graph)
        else:
            metrics, findings = analyze_generic_graph(graph)
        results[graph_id] = {"metrics": metrics, "findings": findings}
    return results


def analyze_generic_graph(graph: ArchitectureGraph) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    adjacency = _adjacency(graph, exclude_edge_types={"contains"})
    indegree, outdegree = _degrees(adjacency)
    metrics = {
        "graph_id": graph.metadata.get("graph_id"),
        "node_count": len(graph.nodes),
        "edge_count": len(graph.edges),
        "node_types": _count_by(graph.nodes, "type"),
        "edge_types": _count_by(graph.edges, "type"),
        "indegree": indegree,
        "outdegree": outdegree,
    }
    findings = []
    return metrics, findings


def analyze_dependency_graph(graph: ArchitectureGraph, dsm_path: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    adjacency = _adjacency(graph, include_edge_types={"imports"}, source_type="module", target_type="module")
    reverse = _reverse_graph(adjacency)
    sccs = strongly_connected_components(adjacency)
    cycles = [component for component in sccs if len(component) > 1]
    articulations = articulation_points(adjacency)
    dsm_rows = write_dsm(adjacency, dsm_path)
    fan_out = {module: len(targets) for module, targets in adjacency.items()}
    fan_in = {module: len(reverse.get(module, set())) for module in adjacency}
    total_modules = max(1, len(adjacency) - 1)
    centrality = {
        module: round((fan_in[module] + fan_out[module]) / max(1, 2 * total_modules), 3)
        for module in adjacency
    }
    top_coupled_modules = [
        {
            "module": module,
            "fan_in": fan_in[module],
            "fan_out": fan_out[module],
            "centrality": centrality[module],
        }
        for module in sorted(
            adjacency,
            key=lambda module: (fan_in[module] + fan_out[module], fan_in[module], fan_out[module], module),
            reverse=True,
        )[:5]
    ]
    dependency_diversity = [
        {
            "module": module,
            "dependency_span": fan_in[module] + fan_out[module],
        }
        for module in sorted(adjacency, key=lambda module: (fan_in[module] + fan_out[module], module), reverse=True)[:5]
    ]

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

    metrics = {
        "graph_id": "dependency_graph",
        "node_count": len(graph.nodes),
        "edge_count": len(graph.edges),
        "module_count": len(adjacency),
        "dsm_generated": bool(dsm_rows),
        "fan_in": fan_in,
        "fan_out": fan_out,
        "strongly_connected_components": sccs,
        "cycle_count": len(cycles),
        "articulation_points": articulations,
        "centrality": centrality,
        "top_coupled_modules": top_coupled_modules,
        "dependency_diversity": dependency_diversity,
    }
    return metrics, findings


def analyze_architecture_graph(graph: ArchitectureGraph) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    adjacency = _adjacency(graph, include_edge_types={"depends_on"}, source_type="package", target_type="package")
    sccs = strongly_connected_components(adjacency)
    cycles = [component for component in sccs if len(component) > 1]
    indegree, outdegree = _degrees(adjacency)
    boundary_hotspots = [
        {
            "package": package,
            "incoming": indegree[package],
            "outgoing": outdegree[package],
        }
        for package in sorted(adjacency, key=lambda name: (indegree[name] + outdegree[name], name), reverse=True)[:5]
    ]
    findings: list[dict[str, Any]] = []
    for package in boundary_hotspots[:3]:
        if package["incoming"] + package["outgoing"] == 0:
            continue
        findings.append(
            {
                "kind": "boundary_hotspot",
                "severity": "medium",
                "target_entities": [package["package"]],
                "summary": f"{package['package']} has heavy cross-package dependency pressure.",
                "evidence": package,
            }
        )
    for component in cycles:
        findings.append(
            {
                "kind": "package_cycle",
                "severity": "high" if len(component) > 2 else "medium",
                "target_entities": component,
                "summary": f"Package-level cycle detected across {', '.join(component)}.",
                "evidence": {"component_size": len(component)},
            }
        )

    metrics = {
        "graph_id": "architecture_graph",
        "node_count": len(graph.nodes),
        "edge_count": len(graph.edges),
        "package_count": len(adjacency),
        "cross_package_dependency_count": sum(len(targets) for targets in adjacency.values()),
        "package_cycles": cycles,
        "boundary_hotspots": boundary_hotspots,
    }
    return metrics, findings


def analyze_data_flow_graph(graph: ArchitectureGraph) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    writer_counts = defaultdict(set)
    reader_counts = defaultdict(set)
    emitter_counts = defaultdict(set)
    module_targets = defaultdict(set)

    for edge in graph.edges:
        if edge.type == "writes_to":
            writer_counts[edge.target].add(edge.source)
            module_targets[edge.source].add(edge.target)
        elif edge.type == "reads_from":
            reader_counts[edge.target].add(edge.source)
            module_targets[edge.source].add(edge.target)
        elif edge.type == "emits_to":
            emitter_counts[edge.target].add(edge.source)
            module_targets[edge.source].add(edge.target)
        elif edge.type == "uses":
            module_targets[edge.source].add(edge.target)

    multi_writer_targets = sorted(target for target, writers in writer_counts.items() if len(writers) > 1)
    shared_targets = sorted(
        target
        for target in set(writer_counts) | set(reader_counts) | set(emitter_counts)
        if len(writer_counts[target] | reader_counts[target] | emitter_counts[target]) > 1
    )
    mixed_concern_modules = sorted(module for module, targets in module_targets.items() if len(targets) > 1)

    findings: list[dict[str, Any]] = []
    for target in multi_writer_targets[:5]:
        findings.append(
            {
                "kind": "multi_writer_target",
                "severity": "high",
                "target_entities": [target],
                "summary": f"{target} has multiple inferred writers.",
                "evidence": {"writers": sorted(writer_counts[target])},
            }
        )
    for module in mixed_concern_modules[:5]:
        findings.append(
            {
                "kind": "mixed_data_flow",
                "severity": "medium",
                "target_entities": [module],
                "summary": f"{module} touches multiple inferred data or service targets.",
                "evidence": {"targets": sorted(module_targets[module])},
            }
        )

    metrics = {
        "graph_id": "data_flow_graph",
        "node_count": len(graph.nodes),
        "edge_count": len(graph.edges),
        "multi_writer_targets": multi_writer_targets,
        "shared_targets": shared_targets,
        "mixed_concern_modules": mixed_concern_modules,
        "reader_counts": {key: len(value) for key, value in reader_counts.items()},
        "writer_counts": {key: len(value) for key, value in writer_counts.items()},
        "emitter_counts": {key: len(value) for key, value in emitter_counts.items()},
    }
    return metrics, findings


def analyze_interface_graph(graph: ArchitectureGraph) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    consumer_counts = defaultdict(set)
    public_symbol_counts: dict[str, int] = {}
    entrypoints: list[str] = []

    for node in graph.nodes:
        if node.type == "api":
            public_symbol_counts[node.id] = int(node.metadata.get("public_symbol_count", 0))
            if node.metadata.get("entrypoint"):
                entrypoints.append(node.id)

    for edge in graph.edges:
        if edge.target.startswith("interface:") and edge.type == "calls":
            consumer_counts[edge.target].add(edge.source)

    top_interfaces = [
        {
            "interface": interface_id,
            "consumers": len(consumer_counts[interface_id]),
            "public_symbol_count": public_symbol_counts.get(interface_id, 0),
        }
        for interface_id in sorted(
            public_symbol_counts,
            key=lambda interface_id: (
                len(consumer_counts[interface_id]),
                public_symbol_counts.get(interface_id, 0),
                interface_id,
            ),
            reverse=True,
        )[:5]
    ]
    chatty_interfaces = [item["interface"] for item in top_interfaces if item["consumers"] >= 2]

    findings: list[dict[str, Any]] = []
    for item in top_interfaces[:3]:
        if item["consumers"] == 0:
            continue
        findings.append(
            {
                "kind": "interface_pressure",
                "severity": "medium" if item["consumers"] < 4 else "high",
                "target_entities": [item["interface"]],
                "summary": f"{item['interface']} has multiple consumers and may be a sensitive interface surface.",
                "evidence": item,
            }
        )

    metrics = {
        "graph_id": "interface_graph",
        "node_count": len(graph.nodes),
        "edge_count": len(graph.edges),
        "entrypoint_count": len(entrypoints),
        "top_interfaces": top_interfaces,
        "chatty_interfaces": chatty_interfaces,
    }
    return metrics, findings


def analyze_function_graph(graph: ArchitectureGraph) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    adjacency = _adjacency(graph, include_edge_types={"calls"}, source_type="function", target_type="function")
    reverse = _reverse_graph(adjacency)
    indegree, outdegree = _degrees(adjacency)
    sccs = strongly_connected_components(adjacency)
    cycles = [component for component in sccs if len(component) > 1]
    articulations = articulation_points(adjacency)
    node_lookup = {node.id: node for node in graph.nodes}

    cross_module_call_count = 0
    for source, targets in adjacency.items():
        source_module = node_lookup.get(source).metadata.get("module") if node_lookup.get(source) else None
        for target in targets:
            target_module = node_lookup.get(target).metadata.get("module") if node_lookup.get(target) else None
            if source_module and target_module and source_module != target_module:
                cross_module_call_count += 1

    top_callers = [
        {
            "function": function_id,
            "module": node_lookup.get(function_id).metadata.get("module", ""),
            "fan_out": outdegree[function_id],
            "fan_in": indegree[function_id],
        }
        for function_id in sorted(
            adjacency,
            key=lambda function_id: (outdegree[function_id], indegree[function_id], function_id),
            reverse=True,
        )[:5]
    ]
    top_shared_functions = [
        {
            "function": function_id,
            "module": node_lookup.get(function_id).metadata.get("module", ""),
            "fan_in": indegree[function_id],
            "fan_out": outdegree[function_id],
        }
        for function_id in sorted(
            adjacency,
            key=lambda function_id: (indegree[function_id], outdegree[function_id], function_id),
            reverse=True,
        )[:5]
    ]
    entrypoint_functions = sorted(
        node.id
        for node in graph.nodes
        if node.type == "function" and bool(node.metadata.get("entrypoint"))
    )

    findings: list[dict[str, Any]] = []
    for component in cycles:
        findings.append(
            {
                "kind": "function_cycle",
                "severity": "high" if len(component) > 2 else "medium",
                "target_entities": component,
                "summary": f"Function call cycle detected across {', '.join(component)}.",
                "evidence": {"component_size": len(component)},
            }
        )
    for item in top_shared_functions[:3]:
        if item["fan_in"] == 0:
            continue
        findings.append(
            {
                "kind": "function_hotspot",
                "severity": "high" if item["fan_in"] >= 3 else "medium",
                "target_entities": [item["function"]],
                "summary": f"{item['function']} is called by multiple internal functions.",
                "evidence": item,
            }
        )

    metrics = {
        "graph_id": "function_graph",
        "node_count": len(graph.nodes),
        "edge_count": len(graph.edges),
        "function_count": len(adjacency),
        "call_edge_count": sum(len(targets) for targets in adjacency.values()),
        "cycle_count": len(cycles),
        "strongly_connected_components": sccs,
        "articulation_points": articulations,
        "cross_module_call_count": cross_module_call_count,
        "top_callers": top_callers,
        "top_shared_functions": top_shared_functions,
        "entrypoint_function_count": len(entrypoint_functions),
        "entrypoint_functions": entrypoint_functions,
    }
    return metrics, findings


def analyze_operational_risk_graph(graph: ArchitectureGraph) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    modules = [node.id for node in graph.nodes if node.type == "module"]
    observability_modules: set[str] = set()
    security_modules: set[str] = set()
    for edge in graph.edges:
        if edge.target == "capability:observability":
            observability_modules.add(edge.source)
        elif edge.target.startswith("capability:"):
            security_modules.add(edge.source)

    observability_coverage = round(len(observability_modules) / max(1, len(modules)), 3)
    security_coverage = round(len(security_modules) / max(1, len(modules)), 3)
    missing_observability = sorted(module for module in modules if module not in observability_modules)
    missing_security = sorted(module for module in modules if module not in security_modules)

    findings: list[dict[str, Any]] = []
    if observability_coverage < 0.5:
        findings.append(
            {
                "kind": "observability_gap",
                "severity": "high" if observability_coverage < 0.25 else "medium",
                "target_entities": missing_observability[:5],
                "summary": "Observability coverage appears low across analyzed modules.",
                "evidence": {"coverage": observability_coverage},
            }
        )
    if security_coverage < 0.5:
        findings.append(
            {
                "kind": "security_gap",
                "severity": "high" if security_coverage < 0.25 else "medium",
                "target_entities": missing_security[:5],
                "summary": "Security-related coverage appears low across analyzed modules.",
                "evidence": {"coverage": security_coverage},
            }
        )

    metrics = {
        "graph_id": "operational_risk_graph",
        "node_count": len(graph.nodes),
        "edge_count": len(graph.edges),
        "module_count": len(modules),
        "observability_coverage": observability_coverage,
        "security_coverage": security_coverage,
        "missing_observability": missing_observability,
        "missing_security": missing_security,
    }
    return metrics, findings


def _count_by(items: list[Any], attribute: str) -> dict[str, int]:
    counts: dict[str, int] = defaultdict(int)
    for item in items:
        counts[getattr(item, attribute)] += 1
    return dict(counts)


def _adjacency(
    graph: ArchitectureGraph,
    include_edge_types: set[str] | None = None,
    exclude_edge_types: set[str] | None = None,
    source_type: str | None = None,
    target_type: str | None = None,
) -> dict[str, set[str]]:
    nodes_by_id = {node.id: node for node in graph.nodes}
    adjacency: dict[str, set[str]] = defaultdict(set)
    for node in graph.nodes:
        if source_type is None or node.type == source_type:
            adjacency[node.id] = set()
    for edge in graph.edges:
        if include_edge_types and edge.type not in include_edge_types:
            continue
        if exclude_edge_types and edge.type in exclude_edge_types:
            continue
        source_node = nodes_by_id.get(edge.source)
        target_node = nodes_by_id.get(edge.target)
        if source_node is None or target_node is None:
            continue
        if source_type and source_node.type != source_type:
            continue
        if target_type and target_node.type != target_type:
            continue
        adjacency[source_node.id].add(target_node.id)
    return dict(adjacency)


def _reverse_graph(adjacency: dict[str, set[str]]) -> dict[str, set[str]]:
    reverse = {node: set() for node in adjacency}
    for source, targets in adjacency.items():
        for target in targets:
            reverse.setdefault(target, set()).add(source)
    return reverse


def _degrees(adjacency: dict[str, set[str]]) -> tuple[dict[str, int], dict[str, int]]:
    reverse = _reverse_graph(adjacency)
    indegree = {node: len(reverse.get(node, set())) for node in adjacency}
    outdegree = {node: len(targets) for node, targets in adjacency.items()}
    return indegree, outdegree


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
