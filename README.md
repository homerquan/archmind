# ArchMind

ArchMind is a Python REPL-style CLI for understanding and analyzing software architecture from a GitHub repository. It opens with a polished terminal intro, prompts for any missing inputs, clones a selected branch, builds an architecture graph, applies PyG-based graph analysis, uses an LLM to interpret the findings in context, and produces a report on screen and in Markdown.

The repository is documentation-driven at this stage. These markdown files define the implementation contract for future code.

## Demo

Watch the ArchMind demo video: [https://youtu.be/yHiM8-ig27o](https://youtu.be/yHiM8-ig27o)

## v0 product shape
- Interface: CLI-only REPL
- Language: Python 3.11+
- Input: GitHub repository URL
- Branch selection: optional, default `main`
- Core output: architecture graph plus analysis findings
- Report output: print to terminal and export a result folder named `result` by default
- LLM access: user selects provider and supplies their own API key
- Terminal UX: ASCII-art opening intro with version, modern prompts, progress bars, and tasteful emoji or ASCII icons

## Core analysis direction
The first useful analysis set should stay concrete and explainable:
- DSM generation from the dependency graph
- coupling analysis such as fan-in, fan-out, and shared-dependency pressure
- cycle and strongly connected component detection
- centrality and bridge-node analysis to identify architectural choke points
- LLM-based interpretation that turns graph evidence into architecture findings and recommendations

## Graphs generated in v0
ArchMind now builds several graph views from the same repository scan:
- `dependency_graph`: module and external dependency relationships
- `architecture_graph`: repository, package, and module boundary structure
- `data_flow_graph`: inferred reads, writes, emits, and external data interactions
- `interface_graph`: public interfaces, entrypoints, and their consumers
- `operational_risk_graph`: inferred observability and security capability coverage

The issue-inspection rules in [knowledge/graph_catalog.json](/Volumes/1TB/Personal_projects/ArchMind/knowledge/graph_catalog.json) map each architecture issue to the graph views most relevant to that inspection.

## Default technical direction
- Python 3.11+ for the REPL, ingestion, graph processing, evaluation, and report generation
- PyTorch plus PyTorch Geometric (PyG) for graph encoding, transforms, and GNNs
- LiteLLM for provider abstraction across OpenAI, Anthropic, and Gemini
- `torch_geometric.data.HeteroData` as the default graph container
- Typed schemas for durable contracts
- JSON, JSONL, Markdown, and trusted tensor artifacts as the primary interchange formats

## Intended CLI shape
```bash
archmind [<github_url>] [--branch main] [--output result] [--llm-provider openai]
```

If a repository URL, branch, output folder, LLM provider, or API key is not provided at startup, the REPL should ask for it interactively.

## How to run
Use Python 3.11+.

### Setup with `uv`
Create a virtual environment:

```bash
uv venv
```

Activate it:

```bash
source .venv/bin/activate
```

Install runtime dependencies and the package:

```bash
uv pip install -r requirements.txt
uv pip install -e .
```

### Setup with `pip`
Create a virtual environment:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

Install runtime dependencies and the package:

```bash
python3 -m pip install -r requirements.txt
python3 -m pip install -e .
```

### Start the program
Launch the REPL:

```bash
archmind
```

Launch with startup parameters:

```bash
archmind https://github.com/example/project --branch main --output result --llm-provider openai
```

Run it without installing the console script:

```bash
PYTHONPATH=src python3 -m archmind
```

### Run tests
Install test tooling if needed:

```bash
python3 -m pip install pytest
```

Then run:

```bash
python3 -m pytest
```

## Result output structure
The user-facing export target is a folder, not a single file.

Default exported folder:

```text
result/
  result.md
  dependency_graph.pdf
  architecture_graph.pdf
  data_flow_graph.pdf
  interface_graph.pdf
  operational_risk_graph.pdf
  dependency_graph_metrics.json
  architecture_graph_metrics.json
  data_flow_graph_metrics.json
  interface_graph_metrics.json
  operational_risk_graph_metrics.json
  dependency_graph_dsm.csv
  issue_summary.json
  issue_assessments.json
```

Workspace artifacts remain under `workspaces/<run_id>/` and include:
- graph JSON files under `graph/`
- PyG payloads per graph
- PDFs per graph under `graph/`
- per-graph metrics and findings under `analysis/`
- per-issue inspection outputs under `analysis/issues/`
- evaluation files and provenance metadata

## Reading order
1. `AGENTS.md` for repo-local coding instructions
2. `SPEC.md` for system scope, domain contracts, and artifacts
3. `WORKFLOW.md` for runtime policy and execution defaults
4. `architecture.md` for module boundaries and graph flow
5. `agent_roles.md` for role definitions and artifact ownership
6. `data.md`, `eval.md`, and `security.md` for operational constraints

## Repository rules
- Treat docs as the system of record. If behavior changes, update docs before or with implementation.
- Keep every stage artifact-backed: repo fetch, graph construction, analysis, explanation, report generation, evaluation, provenance.
- Prefer explicit schemas over prompt-only conventions.
- Record seeds, versions, hashes, and feature-schema changes whenever results should be reproducible.

## Contents
- `AGENTS.md` - repo instructions for coding agents
- `SPEC.md` - system specification and domain contracts
- `agent_roles.md` - execution roles and artifact ownership
- `WORKFLOW.md` - workflow contract and runtime defaults
- `architecture.md` - module boundaries and graph-aware execution flow
- `api.md` - CLI contract and internal interfaces
- `data.md` - source ingestion, graph artifacts, and dataset handling
- `eval.md` - evaluation harness and metrics
- `security.md` - threat model and guardrails
- `roadmap.md` - milestones
- `decisions.md` - architecture decisions
- `CONTRIBUTING.md` - contribution expectations
