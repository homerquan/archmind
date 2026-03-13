from __future__ import annotations

import json
import shutil
from pathlib import Path

from archmind.analysis import analyze_graph
from archmind.evaluation import evaluate
from archmind.graphing import build_architecture_graph, encode_pyg, save_pyg_payload
from archmind.llm import collect_llm_config, interpret_findings
from archmind.models import ArchitectureRequest
from archmind.reporting import render_report, terminal_summary, write_reports
from archmind.repository import build_snapshot, clone_repository, source_tree
from archmind.utils import ensure_dir, sha256_file, utc_now_iso, workspace_dir, write_json, write_text
from archmind.visualization import write_graph_pdf


def run(request: ArchitectureRequest, ui, workspaces_root: Path | None = None) -> dict:
    root = workspaces_root or Path.cwd() / "workspaces"
    workspace = workspace_dir(root)
    ensure_dir(workspace)

    write_json(workspace / "input" / "request.json", request.to_dict())
    llm_config = collect_llm_config(ui, request.llm_provider)
    write_json(workspace / "input" / "llm_config.json", llm_config.safe_dict())

    repo_path = workspace / "source" / "repo"
    with ui.progress("Fetching repository", total=1) as advance:
        clone_repository(request.github_url, request.branch, repo_path)
        advance()

    snapshot = build_snapshot(repo_path, request.github_url, request.branch)
    write_json(workspace / "inventory" / "repository_snapshot.json", snapshot.to_dict())
    write_json(workspace / "inventory" / "source_tree.json", source_tree(repo_path))

    with ui.progress("Building architecture graph", total=3) as advance:
        graph, feature_schema, dependency_inventory = build_architecture_graph(snapshot, repo_path)
        write_json(workspace / "graph" / "architecture_graph.json", graph.to_dict())
        advance()
        write_json(workspace / "graph" / "feature_schema.json", feature_schema)
        advance()
        write_json(workspace / "inventory" / "dependency_inventory.json", dependency_inventory)
        advance()

    with ui.progress("Encoding graph and running analysis", total=4) as advance:
        pyg_payload = encode_pyg(graph)
        save_pyg_payload(pyg_payload, workspace / "graph" / "pyg_data.pt")
        advance()
        metrics, findings = analyze_graph(graph, workspace / "analysis" / "dsm.csv")
        write_json(workspace / "analysis" / "metrics.json", metrics)
        write_json(workspace / "analysis" / "findings.json", findings)
        advance()
        write_graph_pdf(graph, workspace / "analysis" / "graph_visualization.pdf")
        advance()
        explanations_markdown, recommendations = interpret_findings(snapshot, request, metrics, findings, llm_config)
        write_text(workspace / "analysis" / "explanations.md", explanations_markdown)
        write_json(workspace / "analysis" / "recommendations.json", recommendations)
        advance()

    report_markdown = render_report(snapshot, request, llm_config, metrics, findings, explanations_markdown)
    output_dir = Path(request.output_dir).expanduser().resolve()
    report_path, exported_report_path = write_reports(workspace, output_dir, report_markdown)
    _export_result_bundle(workspace, output_dir)

    ui.success("Analysis complete.")
    ui.info(terminal_summary(snapshot, metrics, findings), icon="📌")

    evaluate(workspace, metrics, findings, report_path)
    _write_provenance(workspace, report_path, exported_report_path)

    return {
        "workspace": str(workspace),
        "report_path": str(report_path),
        "output_path": str(exported_report_path),
        "output_dir": str(output_dir),
    }


def _write_provenance(workspace: Path, report_path: Path, output_path: Path) -> None:
    manifest = {
        "generated_at": utc_now_iso(),
        "artifacts": [
            "input/request.json",
            "input/llm_config.json",
            "inventory/repository_snapshot.json",
            "graph/architecture_graph.json",
            "graph/feature_schema.json",
            "graph/pyg_data.pt",
            "analysis/metrics.json",
            "analysis/findings.json",
            "analysis/graph_visualization.pdf",
            "analysis/explanations.md",
            "deliverables/result.md",
            "eval/report.json",
        ],
    }
    write_json(workspace / "provenance" / "manifest.json", manifest)

    hashes = {}
    for path in workspace.rglob("*"):
        if path.is_file():
            hashes[str(path.relative_to(workspace))] = sha256_file(path)
    hashes["user_output"] = sha256_file(output_path)
    write_json(workspace / "provenance" / "hashes.json", hashes)


def _export_result_bundle(workspace: Path, output_dir: Path) -> None:
    ensure_dir(output_dir)
    export_map = {
        workspace / "analysis" / "graph_visualization.pdf": output_dir / "graph_visualization.pdf",
        workspace / "analysis" / "metrics.json": output_dir / "metrics.json",
        workspace / "analysis" / "findings.json": output_dir / "findings.json",
        workspace / "analysis" / "dsm.csv": output_dir / "dsm.csv",
    }
    for source, target in export_map.items():
        if source.exists():
            ensure_dir(target.parent)
            shutil.copy2(source, target)
