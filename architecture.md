# Architecture

ArchMind should be implemented as a small, explicit Python REPL-style CLI pipeline with clear stage boundaries. The architecture is intentionally biased toward inspectable artifacts over hidden in-memory coupling.

## Top-level modules
- REPL Layer: parses optional startup `github_url`, `branch`, `output`, and `llm_provider` arguments, then manages the interactive session.
- Repository Fetcher: clones the selected GitHub branch and records fetch metadata.
- Source Inventory Builder: extracts source tree and dependency information.
- Graph Builder: turns repository evidence into `graph/architecture_graph.json`.
- Feature Encoder: transforms graph metadata into model-ready features and writes `graph/feature_schema.json`.
- PyG Processing Layer: builds `graph/pyg_data.pt` and supports graph-based analysis.
- Analysis Engine: runs DSM, coupling metrics, cycle detection, and centrality analysis.
- LiteLLM Provider Layer: manages provider selection and model invocation for OpenAI, Anthropic, and Gemini.
- LLM Interpretation Layer: turns graph signals into grounded explanations and prioritized findings.
- Report Generator: prints the REPL summary and writes `deliverables/result.md`.
- Evaluator: validates graph integrity, explanation groundedness, and report completeness.

## Canonical execution flow
1. Parse REPL startup input
2. Collect any missing repository, branch, output, provider, or API-key inputs interactively
3. Fetch repository and selected branch
4. Build source inventories
5. Build canonical architecture graph
6. Encode features and process the graph with PyG
7. Run explainable analyses
8. Use an LLM through LiteLLM to interpret the findings in repository context
9. Generate REPL and Markdown reports
10. Evaluate outputs

## Graph architecture
The graph is a shared contract between repository ingestion, analysis, LLM interpretation, and reporting.

Recommended v0 node families:
- repository
- package
- module
- file
- class_or_symbol
- external_dependency
- entrypoint

Recommended v0 edge families:
- contains
- imports
- depends_on
- calls
- inherits_from
- implements
- uses

Default representation rules:
- canonical graph persisted as JSON for debugging and diffability
- processed graph represented as PyG `HeteroData`
- feature definitions versioned in `graph/feature_schema.json`

## Initial analysis methods
- DSM for structural dependency visibility
- fan-in and fan-out coupling
- strongly connected components and cycle detection
- centrality and bridge-node analysis

## Module boundaries
- REPL startup and display logic must be isolated from graph analysis.
- Provider selection and secret handling must be isolated from report generation.
- Repo fetch must be isolated from graph analysis.
- PyG preprocessing must not silently mutate the canonical JSON graph.
- LLM interpretation must consume artifact-backed metrics and findings.
- Report generation must not invent findings absent from analysis artifacts.

## Determinism strategy
- pin dependencies
- record commit sha and tool versions
- version feature schemas
- hash important inputs and outputs in `provenance/hashes.json`
