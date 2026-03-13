# Agent Roles

This document defines the default execution team for ArchMind. The team is artifact-driven: each agent owns a narrow stage, writes durable files into the workspace, and never assumes later agents can recover missing context from chat logs.

## Core operating model
A run moves through:

`request -> repl startup -> provider selection -> repo fetch -> graph -> features -> analysis -> llm interpretation -> report -> evaluation`

The graph stage is first-class. Repository ingestion is not complete until the selected branch is represented as a typed architecture graph that downstream agents can inspect and analyze.

## Default agent roles

### 1. Orchestrator Agent
Responsibility: maintain run state, dispatch agents, enforce policy, and decide retries.

Inputs:
- `input/request.json`
- `WORKFLOW.md`
- current run state and artifact index

Outputs:
- `logs/orchestrator.jsonl`
- run events and checkpoints
- retry or escalation decisions

Guardrails:
- cannot mark a run complete until analysis, report, and evaluation artifacts exist
- cannot bypass provenance or evaluation requirements
- cannot persist raw API keys in workspace artifacts

### 2. Repository Ingestion Agent
Responsibility: clone the target GitHub repository and resolve the selected branch.

Outputs:
- `inventory/repository_snapshot.json`
- `inventory/source_tree.json`
- `inventory/dependency_inventory.json`

Requirements:
- input is a GitHub URL plus optional branch
- branch defaults to `main`
- capture commit sha, branch name, and fetch status explicitly

### 3. LLM Provider Agent
Responsibility: collect LLM provider configuration from the user and prepare LiteLLM-compatible settings.

Outputs:
- `input/llm_config.json`

Requirements:
- allow provider selection for OpenAI, Anthropic, and Gemini
- ask interactively for missing API keys
- never write raw API keys into durable report artifacts
- persist only safe provider metadata when needed
### 4. Graph Modeling Agent
Responsibility: transform repository structure and dependency data into a machine-usable architecture graph.

Outputs:
- `graph/architecture_graph.json`
- `graph/feature_schema.json`
- `graph/pyg_data.pt` when PyG preprocessing is active

Requirements:
- use PyTorch Geometric (PyG) for graph encoding and processing by default
- prefer `torch_geometric.data.HeteroData`
- keep the canonical JSON graph easy to inspect and diff
- version feature definitions and preprocessing assumptions

### 5. Analysis Agent
Responsibility: run explainable architecture analyses over the graph.

Outputs:
- `analysis/metrics.json`
- `analysis/findings.json`
- `analysis/dsm.csv`

Recommended initial analyses:
- DSM generation
- fan-in and fan-out coupling
- cycle and strongly connected component detection
- centrality and bridge-node analysis

### 6. LLM Interpretation Agent
Responsibility: interpret graph evidence using repository context and convert metrics into architecture findings.

Outputs:
- `analysis/explanations.md`
- `analysis/recommendations.json`

Requirements:
- ground explanations in graph metrics and identifiable repository entities
- do not invent facts not supported by the repo or graph artifacts

### 7. Report Agent
Responsibility: assemble user-facing output.

Outputs:
- `deliverables/result.md`

Requirements:
- print a concise summary to the terminal REPL
- write Markdown report to `result.md` by default unless overridden
- render a polished intro screen with ASCII art, version text, and modern prompt styling
- use progress bars for long-running stages such as repo fetch, graph build, and analysis
### 8. QA / Evaluator Agent
Responsibility: evaluate graph integrity, analysis quality, explanation groundedness, and report completeness.

Outputs:
- `eval/report.json`
- `eval/metrics.json`
- `eval/notes.md`

Requirements:
- verify graph schema validity before LLM interpretation
- verify reports are aligned with analysis artifacts
- move runs to `NeedsHumanReview` when hard gates fail

## Shared conventions
- Every agent writes a short structured log to `logs/agents.jsonl`.
- Every agent must be able to resume from existing artifacts.
- Every important decision must land in a file, not only in chat.
- The graph artifacts are shared contracts, not temporary intermediates.
