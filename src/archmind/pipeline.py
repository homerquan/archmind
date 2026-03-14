from __future__ import annotations

import shutil
from pathlib import Path

from archmind.analysis import analyze_graph_bundle
from archmind.evaluation import evaluate
from archmind.graphing import build_graph_bundle, encode_pyg, save_pyg_payload
from archmind.inspection import inspect_knowledge_issues
from archmind.llm import collect_llm_config
from archmind.models import ArchitectureRequest
from archmind.reporting import render_report, terminal_summary, write_reports
from archmind.repository import build_snapshot, clone_repository, source_tree
from archmind.utils import ensure_dir, sha256_file, utc_now_iso, workspace_dir, write_json
from archmind.visualization import write_graph_pdf


def run(request: ArchitectureRequest, ui, workspaces_root: Path | None = None) -> dict:
    root = workspaces_root or Path.cwd() / "workspaces"
    workspace = workspace_dir(root)
    ensure_dir(workspace)

    write_json(workspace / "input" / "request.json", request.to_dict())
    llm_config = collect_llm_config(ui, request.llm_provider, debug=request.debug)
    write_json(workspace / "input" / "llm_config.json", llm_config.safe_dict())

    repo_path = workspace / "source" / "repo"
    with ui.progress("Fetching repository", total=1) as advance:
        _, resolved_branch = clone_repository(request.github_url, request.branch, repo_path)
        advance()

    snapshot = build_snapshot(repo_path, request.github_url, resolved_branch)
    write_json(workspace / "inventory" / "repository_snapshot.json", snapshot.to_dict())
    write_json(workspace / "inventory" / "source_tree.json", source_tree(repo_path))

    with ui.progress("Building graph bundle", total=5) as advance:
        graphs, feature_schemas, dependency_inventory = build_graph_bundle(snapshot, repo_path)
        write_json(workspace / "inventory" / "dependency_inventory.json", dependency_inventory)
        advance()
        for graph_id, graph in graphs.items():
            write_json(workspace / "graph" / f"{graph_id}.json", graph.to_dict())
        advance()
        for graph_id, schema in feature_schemas.items():
            write_json(workspace / "graph" / f"{graph_id}_feature_schema.json", schema)
        advance()
        for graph_id, graph in graphs.items():
            save_pyg_payload(encode_pyg(graph), workspace / "graph" / f"{graph_id}_pyg_data.pt")
        advance()
        for graph_id, graph in graphs.items():
            write_graph_pdf(graph, workspace / "graph" / f"{graph_id}.pdf")
        advance()

    with ui.progress("Analyzing graphs and issues", total=4) as advance:
        graph_results = analyze_graph_bundle(graphs, workspace / "analysis")
        for graph_id, result in graph_results.items():
            write_json(workspace / "analysis" / f"{graph_id}_metrics.json", result["metrics"])
            write_json(workspace / "analysis" / f"{graph_id}_findings.json", result["findings"])
        advance()
        issue_assessments, issue_summary = inspect_knowledge_issues(snapshot, request, graph_results, llm_config)
        write_json(workspace / "analysis" / "issue_summary.json", issue_summary)
        write_json(
            workspace / "analysis" / "issue_assessments.json",
            [
                {key: value for key, value in item.items() if key != "markdown"}
                for item in issue_assessments
            ],
        )
        for issue in issue_assessments:
            write_json(
                workspace / "analysis" / "issues" / f"{issue['id']}.json",
                {key: value for key, value in issue.items() if key != "markdown"},
            )
            (workspace / "analysis" / "issues").mkdir(parents=True, exist_ok=True)
            (workspace / "analysis" / "issues" / f"{issue['id']}.md").write_text(issue["markdown"], encoding="utf-8")
        advance()
        report_markdown = render_report(snapshot, request, llm_config, graph_results, issue_assessments, issue_summary)
        output_dir = Path(request.output_dir).expanduser().resolve()
        report_path, exported_report_path = write_reports(workspace, output_dir, report_markdown)
        advance()
        _export_result_bundle(workspace, output_dir, graphs)
        advance()

    ui.success("Analysis complete.")
    ui.info(terminal_summary(snapshot, graph_results, issue_summary), icon="📌")

    evaluate(workspace, graph_results.get("dependency_graph", {}).get("metrics", {}), issue_assessments, report_path)
    _write_provenance(workspace, exported_report_path)

    return {
        "workspace": str(workspace),
        "report_path": str(report_path),
        "output_path": str(exported_report_path),
        "output_dir": str(output_dir),
    }


def _write_provenance(workspace: Path, exported_report_path: Path) -> None:
    artifact_paths = sorted(
        str(path.relative_to(workspace))
        for path in workspace.rglob("*")
        if path.is_file() and "provenance/" not in str(path.relative_to(workspace))
    )
    manifest = {
        "generated_at": utc_now_iso(),
        "artifacts": artifact_paths,
    }
    write_json(workspace / "provenance" / "manifest.json", manifest)

    hashes = {}
    for path in workspace.rglob("*"):
        if path.is_file():
            hashes[str(path.relative_to(workspace))] = sha256_file(path)
    hashes["user_output"] = sha256_file(exported_report_path)
    write_json(workspace / "provenance" / "hashes.json", hashes)


def _export_result_bundle(workspace: Path, output_dir: Path, graphs) -> None:
    ensure_dir(output_dir)
    export_map = {
        workspace / "analysis" / "issue_summary.json": output_dir / "issue_summary.json",
        workspace / "analysis" / "issue_assessments.json": output_dir / "issue_assessments.json",
        workspace / "analysis" / "dependency_graph_dsm.csv": output_dir / "dependency_graph_dsm.csv",
    }
    for graph_id in graphs:
        export_map[workspace / "analysis" / f"{graph_id}_metrics.json"] = output_dir / f"{graph_id}_metrics.json"
        export_map[workspace / "analysis" / f"{graph_id}_findings.json"] = output_dir / f"{graph_id}_findings.json"
        export_map[workspace / "graph" / f"{graph_id}.pdf"] = output_dir / f"{graph_id}.pdf"
    for source, target in export_map.items():
        if source.exists():
            ensure_dir(target.parent)
            shutil.copy2(source, target)
