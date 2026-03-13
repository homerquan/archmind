from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def knowledge_dir() -> Path:
    return Path(__file__).resolve().parents[2] / "knowledge"


def load_knowledge_index(base_dir: Path | None = None) -> dict[str, Any]:
    base = base_dir or knowledge_dir()
    return json.loads((base / "index.json").read_text(encoding="utf-8"))


def load_graph_catalog(base_dir: Path | None = None) -> list[dict[str, Any]]:
    base = base_dir or knowledge_dir()
    index = load_knowledge_index(base)
    graph_catalog = index.get("graph_catalog", "graph_catalog.json")
    return json.loads((base / graph_catalog).read_text(encoding="utf-8"))["graphs"]


def load_issue_definitions(base_dir: Path | None = None) -> list[dict[str, Any]]:
    base = base_dir or knowledge_dir()
    index = load_knowledge_index(base)
    issues: list[dict[str, Any]] = []
    for name in index["files"]:
        issues.append(json.loads((base / name).read_text(encoding="utf-8")))
    return issues


def graph_support_map(base_dir: Path | None = None) -> dict[str, list[str]]:
    mapping: dict[str, list[str]] = {}
    for graph in load_graph_catalog(base_dir):
        for issue_id in graph.get("supports_issues", []):
            mapping.setdefault(issue_id, []).append(graph["id"])
    return mapping
