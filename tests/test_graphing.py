from __future__ import annotations

from pathlib import Path

from archmind.graphing import build_graph_bundle
from archmind.models import RepositorySnapshot


def test_build_graph_bundle_detects_internal_and_external_imports(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    pkg = repo / "sample"
    pkg.mkdir(parents=True)
    (pkg / "__init__.py").write_text("", encoding="utf-8")
    (pkg / "a.py").write_text(
        "from sample import b\n"
        "import requests\n\n"
        "def alpha():\n"
        "    return b.beta()\n\n"
        "def gamma():\n"
        "    return alpha()\n",
        encoding="utf-8",
    )
    (pkg / "b.py").write_text(
        "from sample import a\n\n"
        "def beta():\n"
        "    return 1\n",
        encoding="utf-8",
    )

    snapshot = RepositorySnapshot(
        github_url="https://github.com/example/project",
        branch="main",
        commit_sha="abc123",
        fetched_at="2026-03-13T00:00:00+00:00",
        root_path=str(repo),
        language_hints=["python"],
        manifests=[],
    )

    graphs, feature_schemas, inventory = build_graph_bundle(snapshot, repo)
    dependency_graph = graphs["dependency_graph"]
    data_flow_graph = graphs["data_flow_graph"]
    function_graph = graphs["function_graph"]

    node_ids = {node.id for node in dependency_graph.nodes}
    function_node_ids = {node.id for node in function_graph.nodes}
    function_edges = {(edge.source, edge.target, edge.type) for edge in function_graph.edges}
    assert "module:sample.a" in node_ids
    assert "module:sample.b" in node_ids
    assert "external:requests" in node_ids
    assert "function:sample.a.alpha" in function_node_ids
    assert "function:sample.a.gamma" in function_node_ids
    assert "function:sample.b.beta" in function_node_ids
    assert ("function:sample.a.alpha", "function:sample.b.beta", "calls") in function_edges
    assert ("function:sample.a.gamma", "function:sample.a.alpha", "calls") in function_edges
    assert feature_schemas["dependency_graph"]["schema_version"] == 1
    assert inventory["modules"]["sample.a"]["internal_imports"] == ["sample.b"]
    assert inventory["modules"]["sample.a"]["external_imports"] == ["requests"]
    assert inventory["modules"]["sample.a"]["function_count"] == 2
    assert data_flow_graph.metadata["graph_id"] == "data_flow_graph"
    assert function_graph.metadata["graph_id"] == "function_graph"


def test_build_graph_bundle_supports_java_modules_and_methods(tmp_path: Path) -> None:
    repo = tmp_path / "repo-java"
    java_dir = repo / "src" / "main" / "java" / "com" / "example"
    java_dir.mkdir(parents=True)
    (java_dir / "App.java").write_text(
        "package com.example;\n"
        "import com.example.Util;\n"
        "public class App {\n"
        "    public void run() {\n"
        "        Util.help();\n"
        "        helper();\n"
        "    }\n"
        "    private void helper() {\n"
        "        Util.help();\n"
        "    }\n"
        "}\n",
        encoding="utf-8",
    )
    (java_dir / "Util.java").write_text(
        "package com.example;\n"
        "public class Util {\n"
        "    public static void help() {\n"
        "    }\n"
        "}\n",
        encoding="utf-8",
    )

    snapshot = RepositorySnapshot(
        github_url="https://github.com/example/java-project",
        branch="main",
        commit_sha="abc123",
        fetched_at="2026-03-13T00:00:00+00:00",
        root_path=str(repo),
        language_hints=["java"],
        manifests=[],
    )

    graphs, feature_schemas, inventory = build_graph_bundle(snapshot, repo)
    dependency_graph = graphs["dependency_graph"]
    function_graph = graphs["function_graph"]

    dependency_node_ids = {node.id for node in dependency_graph.nodes}
    function_node_ids = {node.id for node in function_graph.nodes}
    function_edges = {(edge.source, edge.target, edge.type) for edge in function_graph.edges}

    assert "module:com.example.App" in dependency_node_ids
    assert "module:com.example.Util" in dependency_node_ids
    assert "function:com.example.App.run" in function_node_ids
    assert "function:com.example.App.helper" in function_node_ids
    assert "function:com.example.Util.help" in function_node_ids
    assert ("function:com.example.App.run", "function:com.example.Util.help", "calls") in function_edges
    assert ("function:com.example.App.run", "function:com.example.App.helper", "calls") in function_edges
    assert inventory["modules"]["com.example.App"]["function_count"] == 2
    assert feature_schemas["function_graph"]["schema_version"] == 1
