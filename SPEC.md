# ArchMind Specification

Status: Draft v1

Purpose: define a Python REPL-style CLI launched as `archmind` that accepts optional startup parameters, asks for missing inputs interactively, builds an architecture graph for a GitHub repository, analyzes it with PyG-centered graph methods, uses an LLM through LiteLLM to interpret the findings in context, and generates terminal plus Markdown reports.

Design principles:
- Spec-first: repo docs define behavior before implementation details do.
- Reproducible: the system must preserve enough metadata to reproduce outputs.
- Inspectable: important state must live in workspace artifacts, not in hidden prompts.
- Graph-native: repository structure and dependency relationships should be modeled explicitly as a graph.
- Explainable: LLM outputs must be grounded in graph evidence.

## 1. Product scope
ArchMind v0 is intentionally narrow.

In scope:
- Python REPL-style CLI only
- single GitHub repository URL as primary input
- optional branch selection with default `main`
- architecture graph construction from the selected repository state
- PyG-assisted graph analysis
- LLM interpretation of graph findings
- terminal summary and Markdown report output
- intro banner with ASCII art and version text
- progress bars for long-running stages
- user-selected LLM provider and API key entry

Out of scope for v0:
- web UI
- multi-repo orchestration
- runtime telemetry ingestion
- infrastructure graph ingestion
- autonomous refactoring

## 2. Problem statement
Repository-scale architecture is hard to understand because dependency structure, module boundaries, and coupling are spread across files, packages, and build metadata. Engineers need a fast way to answer questions such as:
- where is the real coupling?
- which modules are hard to change safely?
- where are the cycle-heavy or choke-point areas?
- what architectural findings matter most right now?

ArchMind addresses this by:
1. fetching a GitHub repository at a selected branch,
2. extracting repository structure and dependency evidence,
3. converting that evidence into a typed architecture graph,
4. running useful initial graph analyses,
5. using an LLM to explain what those graph signals mean in context,
6. producing a readable report.

## 3. Goals and non-goals

### 3.1 Goals
- Build a reproducible architecture graph from a GitHub repository.
- Keep the first version CLI-only and easy to run locally.
- Standardize graph encoding, processing, and graph learning on PyTorch Geometric (PyG).
- Start with useful, explainable analyses rather than an overbroad platform.
- Produce a report on screen and in Markdown.

### 3.2 Non-goals
- Replacing human architecture judgment for high-stakes changes.
- Fully autonomous production refactoring.
- A full SaaS control plane.
- A broad observability platform.

## 4. Default implementation direction
- Language: Python 3.11+
- Interface: REPL-style CLI only
- Primary input: GitHub URL and optional branch
- Default branch: `main`
- Default output file: `result.md`
- Command: `archmind`
- Missing startup inputs collected interactively in the REPL
- Graph stack: PyTorch plus PyTorch Geometric (PyG)
- LLM gateway: LiteLLM
- Supported LLM providers: OpenAI, Anthropic, Gemini
- Default graph object: `torch_geometric.data.HeteroData`
- Artifact formats: JSON, JSONL, CSV, Markdown, and trusted tensor or checkpoint formats

## 5. Main components
1. REPL Layer
   - Parses startup input such as repository URL, branch, and output file path.
   - Presents an intro banner, version text, and interactive terminal session.
   - Shows progress bars for long-running operations.

2. Repository Fetcher
   - Resolves and clones the selected GitHub repository and branch.
   - Records commit sha and fetch metadata.

3. Graph Builder
   - Converts repository structure and dependency evidence into a canonical architecture graph.
   - Emits inspectable JSON and processed PyG artifacts.

4. Analysis Engine
   - Runs the initial useful analysis set:
     - design structure matrix (DSM)
     - fan-in and fan-out coupling
     - strongly connected components and cycles
     - centrality and bridge-node analysis

5. LLM Provider Layer
   - Collects provider choice and API key when not already configured.
   - Routes calls through LiteLLM.

6. LLM Interpretation Layer
   - Uses graph findings plus repository context to generate grounded explanations and recommendations.

7. Report Generator
   - Prints a concise terminal summary inside the REPL.
   - Writes the full report to Markdown.

8. Evaluator
   - Checks graph integrity, analysis completeness, explanation groundedness, and report completeness.

## 6. Core domain model

### 6.1 ArchitectureRequest
Suggested fields:
- `github_url`
- `branch`
- `output_markdown_path`
- `llm_provider`

### 6.2 RepositorySnapshot
Suggested fields:
- `github_url`
- `branch`
- `commit_sha`
- `fetched_at`
- `language_hints`
- `manifests`

### 6.3 ArchitectureGraph
The canonical graph artifact linking architecture entities and relationships.

Requirements:
- stored as `graph/architecture_graph.json`
- easy to inspect and diff
- stable ids for nodes and edges
- sufficient metadata to rebuild the PyG representation

Recommended v0 node types:
- `repository`
- `package`
- `module`
- `file`
- `class_or_symbol`
- `external_dependency`
- `entrypoint`

Recommended v0 edge types:
- `contains`
- `imports`
- `depends_on`
- `calls`
- `inherits_from`
- `implements`
- `uses`

### 6.4 AnalysisFinding
Suggested fields:
- `finding_id`
- `kind`
- `target_entities`
- `evidence`
- `severity`
- `summary`

### 6.5 PyGGraphData
The processed graph artifact used by analysis code.

Requirements:
- represented with `torch_geometric.data.HeteroData` by default
- stored as `graph/pyg_data.pt` only after preprocessing is complete
- accompanied by `graph/feature_schema.json`

`feature_schema.json` should document:
- node and edge feature names
- embedding sources or transforms
- categorical vocabularies
- normalization statistics
- schema version

### 6.6 Report
Suggested outputs:
- terminal summary
- Markdown report written to `result.md` by default

### 6.7 TerminalSession
Suggested fields:
- `version`
- `intro_banner_rendered`
- `startup_arguments`
- `interactive_commands`
- `progress_events`

### 6.8 LLMConfig
Suggested fields:
- `provider`
- `model`
- `api_key_source`

## 7. PyG and graph-analysis guidance
- Use PyG whenever graph structure affects metric computation, ranking, hotspot detection, or future learned analysis.
- Keep graph construction deterministic and separate from analysis routines.
- Convert raw metadata into features during preprocessing, not ad hoc inside analysis code.
- Keep node and edge ids stable across reruns when semantic entities are unchanged.
- Document every new node type, edge type, or feature family in `data.md` and `decisions.md` when it changes system behavior.

## 8. LLM grounding guidance
- The LLM should interpret graph evidence, not replace it.
- Every narrative finding should point back to graph metrics, entity ids, or repository evidence.
- The LLM may summarize and prioritize findings, but it must not invent architecture facts unsupported by artifacts.
- Provider access should flow through LiteLLM.
- Raw API keys must not be written into reports or durable artifacts.

## 8.1 Terminal UX guidance
- The REPL should open with an ASCII-art banner and version number.
- Terminal sections should be concise, scannable, and visually structured.
- Emoji or simple ASCII icons are allowed when they improve readability.
- Progress bars should be used for repo fetch, graph build, and analysis stages.
- The interface should feel modern without hiding command behavior or output artifacts.

## 9. Workspace layout

```text
/workspaces/<run_id>/
  input/
    request.json
  inventory/
    repository_snapshot.json
    source_tree.json
    dependency_inventory.json
  graph/
    architecture_graph.json
    feature_schema.json
    pyg_data.pt
  analysis/
    metrics.json
    findings.json
    dsm.csv
    explanations.md
    recommendations.json
  eval/
    report.json
    metrics.json
    notes.md
  logs/
    orchestrator.jsonl
    agents.jsonl
  provenance/
    manifest.json
    hashes.json
  deliverables/
    result.md
```

## 10. Interfaces

### 10.1 CLI interface
```bash
archmind [<github_url>] [--branch main] [--output result.md] [--llm-provider openai]
```

### 10.2 Internal graph interface
- `build_graph(repository_snapshot, dependency_inventory) -> architecture_graph.json`
- `encode_graph(architecture_graph, feature_schema) -> pyg_data.pt`
- `analyze_graph(pyg_data) -> metrics.json, findings.json, dsm.csv`

### 10.3 Reporting interface
- `generate_report(findings, explanations, output_path) -> result.md`

## 11. Evaluation contract
Success must be defined before implementation:
- graph validity: schema-valid graph with consistent ids and legal edge relations
- analysis quality: useful, explainable coupling and structure findings
- LLM grounding: explanations trace back to graph evidence
- report completeness: terminal summary and Markdown output both generated
- reproducibility: commit sha, branch, and versions sufficient to reproduce outputs

See `eval.md` for metrics and required reports.
