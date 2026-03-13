from __future__ import annotations

import ast
import json
from collections import defaultdict
from pathlib import Path
from typing import Any

from archmind.models import ArchitectureGraph, GraphEdge, GraphNode, RepositorySnapshot
from archmind.utils import compact_path, write_text


def _module_name_from_path(path: Path) -> str:
    without_suffix = path.with_suffix("")
    parts = list(without_suffix.parts)
    if parts and parts[-1] == "__init__":
        parts = parts[:-1]
    return ".".join(parts)


def discover_python_modules(repo_root: Path) -> dict[str, Path]:
    modules: dict[str, Path] = {}
    for path in repo_root.rglob("*.py"):
        if ".git" in path.parts or "__pycache__" in path.parts:
            continue
        rel = path.relative_to(repo_root)
        module_name = _module_name_from_path(rel)
        if module_name:
            modules[module_name] = path
    return dict(sorted(modules.items()))


def _resolve_import(current_module: str, level: int, module: str | None) -> str | None:
    if level == 0:
        return module
    parts = current_module.split(".")
    if current_module and parts:
        parts = parts[:-1]
    if level > 1:
        parts = parts[: max(0, len(parts) - (level - 1))]
    if module:
        parts.extend(module.split("."))
    return ".".join(part for part in parts if part)


def parse_dependencies(repo_root: Path, modules: dict[str, Path]) -> dict[str, dict[str, set[str]]]:
    dependency_map: dict[str, dict[str, set[str]]] = {}
    module_names = set(modules)
    for module_name, path in modules.items():
        internal: set[str] = set()
        external: set[str] = set()
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    target = alias.name
                    internal_target = _longest_internal_match(target, module_names)
                    if internal_target:
                        internal.add(internal_target)
                    else:
                        external.add(target.split(".")[0])
            elif isinstance(node, ast.ImportFrom):
                base = _resolve_import(module_name, node.level, node.module)
                for alias in node.names:
                    if alias.name == "*":
                        if base:
                            internal_target = _longest_internal_match(base, module_names)
                            if internal_target:
                                internal.add(internal_target)
                            else:
                                external.add(base.split(".")[0])
                        continue
                    candidate = f"{base}.{alias.name}" if base else alias.name
                    internal_target = _longest_internal_match(candidate, module_names)
                    if internal_target:
                        internal.add(internal_target)
                    elif base:
                        external.add(base.split(".")[0])
        dependency_map[module_name] = {"internal": internal, "external": external}
    return dependency_map


def _longest_internal_match(import_name: str, module_names: set[str]) -> str | None:
    parts = import_name.split(".")
    for index in range(len(parts), 0, -1):
        candidate = ".".join(parts[:index])
        if candidate in module_names:
            return candidate
    return None


def build_architecture_graph(snapshot: RepositorySnapshot, repo_root: Path) -> tuple[ArchitectureGraph, dict[str, Any], dict[str, Any]]:
    modules = discover_python_modules(repo_root)
    dependencies = parse_dependencies(repo_root, modules)

    nodes: list[GraphNode] = [
        GraphNode(
            id="repository:root",
            type="repository",
            label=Path(snapshot.root_path).name,
            metadata={"branch": snapshot.branch, "commit_sha": snapshot.commit_sha},
        )
    ]
    edges: list[GraphEdge] = []
    external_nodes: dict[str, GraphNode] = {}

    for module_name, path in modules.items():
        rel = compact_path(path, repo_root)
        depth = len(module_name.split("."))
        internal_count = len(dependencies[module_name]["internal"])
        external_count = len(dependencies[module_name]["external"])
        nodes.append(
            GraphNode(
                id=f"module:{module_name}",
                type="module",
                label=module_name,
                metadata={
                    "path": rel,
                    "path_depth": depth,
                    "internal_import_count": internal_count,
                    "external_import_count": external_count,
                },
            )
        )
        edges.append(
            GraphEdge(
                source="repository:root",
                target=f"module:{module_name}",
                type="contains",
                metadata={"path": rel},
            )
        )
        for target in sorted(dependencies[module_name]["internal"]):
            edges.append(
                GraphEdge(
                    source=f"module:{module_name}",
                    target=f"module:{target}",
                    type="imports",
                    metadata={},
                )
            )
        for dependency in sorted(dependencies[module_name]["external"]):
            external_id = f"external:{dependency}"
            if external_id not in external_nodes:
                external_nodes[external_id] = GraphNode(
                    id=external_id,
                    type="external_dependency",
                    label=dependency,
                    metadata={"top_level_package": dependency},
                )
            edges.append(
                GraphEdge(
                    source=f"module:{module_name}",
                    target=external_id,
                    type="depends_on",
                    metadata={},
                )
            )

    nodes.extend(external_nodes.values())
    graph = ArchitectureGraph(
        repository=snapshot.github_url,
        nodes=nodes,
        edges=edges,
        metadata={
            "module_count": len(modules),
            "external_dependency_count": len(external_nodes),
        },
    )
    feature_schema = {
        "node_features": [
            "path_depth",
            "internal_import_count",
            "external_import_count",
            "in_degree",
            "out_degree",
        ],
        "edge_types": ["contains", "imports", "depends_on"],
        "schema_version": 1,
    }
    inventory = {
        "modules": {
            module: {
                "path": compact_path(path, repo_root),
                "internal_imports": sorted(dependencies[module]["internal"]),
                "external_imports": sorted(dependencies[module]["external"]),
            }
            for module, path in modules.items()
        }
    }
    return graph, feature_schema, inventory


def encode_pyg(graph: ArchitectureGraph) -> dict[str, Any]:
    module_ids = [node.id for node in graph.nodes if node.type == "module"]
    external_ids = [node.id for node in graph.nodes if node.type == "external_dependency"]
    features: dict[str, list[list[int]]] = defaultdict(list)
    node_index = {node.id: idx for idx, node in enumerate(graph.nodes)}

    in_degree = defaultdict(int)
    out_degree = defaultdict(int)
    for edge in graph.edges:
        out_degree[edge.source] += 1
        in_degree[edge.target] += 1

    for node in graph.nodes:
        if node.type not in {"module", "external_dependency", "repository"}:
            continue
        features[node.type].append(
            [
                int(node.metadata.get("path_depth", 0)),
                int(node.metadata.get("internal_import_count", 0)),
                int(node.metadata.get("external_import_count", 0)),
                in_degree[node.id],
                out_degree[node.id],
            ]
        )

    edge_index: dict[str, list[list[int]]] = defaultdict(lambda: [[], []])
    for edge in graph.edges:
        key = f"{edge.source.split(':', 1)[0]}::{edge.type}::{edge.target.split(':', 1)[0]}"
        edge_index[key][0].append(node_index[edge.source])
        edge_index[key][1].append(node_index[edge.target])

    payload = {
        "backend": "fallback-json",
        "node_types": {
            "module": module_ids,
            "external_dependency": external_ids,
        },
        "features": dict(features),
        "edge_index": dict(edge_index),
    }

    try:  # pragma: no cover - optional dependency path
        import torch
        from torch_geometric.data import HeteroData

        data = HeteroData()
        for node_type, rows in features.items():
            data[node_type].x = torch.tensor(rows, dtype=torch.float32)
        for edge_key, indices in edge_index.items():
            src_type, edge_type, dst_type = edge_key.split("::")
            data[(src_type, edge_type, dst_type)].edge_index = torch.tensor(indices, dtype=torch.long)
        payload = data
    except Exception:
        pass

    return payload


def save_pyg_payload(payload: Any, path: Path) -> None:
    try:  # pragma: no cover - optional dependency path
        import torch
        from torch_geometric.data import HeteroData

        if isinstance(payload, HeteroData):
            path.parent.mkdir(parents=True, exist_ok=True)
            torch.save(payload, path)
            return
    except Exception:
        pass
    write_text(path, json.dumps(payload, indent=2, sort_keys=True) + "\n")
