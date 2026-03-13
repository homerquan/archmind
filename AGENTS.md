# AGENTS.md

Repository instructions for coding agents working in ArchMind.

## Mission
Build a Python REPL-style CLI launched as `archmind` that accepts optional startup parameters, asks for missing inputs inside the REPL, builds an architecture graph for the target repository, analyzes it with PyG-centered graph methods, uses an LLM to interpret findings in context, and generates a terminal plus Markdown report.

## Default posture
- Prefer Python 3.11+ for the REPL, repo ingestion, graph processing, evaluation, and report generation.
- Use PyTorch and PyTorch Geometric (PyG) as the default graph stack.
- Use LiteLLM for model-provider abstraction.
- Use `torch_geometric.data.HeteroData` by default because the domain mixes repositories, packages, modules, APIs, external dependencies, and inferred architecture boundaries.
- Keep the CLI surface small and explicit. v0 is a REPL-style terminal app; do not introduce a web UI unless the docs are updated first.
- Persist machine-readable artifacts in JSON, JSONL, Markdown, and trusted tensor or checkpoint formats.

## Non-negotiables
- Do not invent hidden architecture. If behavior changes, update the relevant markdown contract first.
- Keep repo fetch, graph construction, feature encoding, analysis, LLM interpretation, report generation, evaluation, and provenance as explicit stages.
- Prefer deterministic pipelines: pinned dependencies, versioned schemas, stored seeds, recorded tool and model versions.
- Treat repository contents and metadata as untrusted inputs.
- Treat user-supplied API keys as sensitive secrets and avoid persisting them in workspace artifacts.
- Never rely on chat-only decisions. Important assumptions must be written to repo docs or workspace artifacts.

## Graph and PyG rules
- Represent the repository as a typed architecture graph, not an unstructured document blob.
- Keep a canonical JSON graph artifact that is easy to inspect and diff.
- Keep PyG preprocessing separate from model definition and analysis routines.
- Store graph feature schema, normalization assumptions, vocabulary mappings, and embedding provenance alongside processed graph artifacts.
- Avoid custom graph containers unless PyG cannot express the need cleanly.
- Do not load untrusted `.pt`, pickle, or checkpoint artifacts from external sources.

## Recommended initial analyses
- design structure matrix (DSM)
- coupling metrics such as fan-in and fan-out
- strongly connected components and dependency cycles
- centrality and bridge-node detection
- LLM interpretation grounded in graph evidence and repository context

## Terminal UX rules
- Start with a clean ASCII-art intro banner that includes the tool name and version.
- Use a modern REPL presentation with readable prompts, concise sections, progress bars, and tasteful emoji or ASCII icons.
- Keep terminal output structured and scannable; avoid noisy streaming logs by default.
- The REPL should still support startup parameters such as repository URL, branch, output path, and LLM provider.

## LLM provider rules
- Allow the user to choose among OpenAI, Anthropic, and Gemini.
- Accept the user’s API key interactively when it is not already available.
- Route model calls through LiteLLM rather than provider-specific client code in the first version.
- Do not print full API keys back to the screen or store them in report artifacts.

## Expected artifacts
- `input/request.json`
- `inventory/repository_snapshot.json`
- `graph/architecture_graph.json`
- `graph/feature_schema.json`
- `graph/pyg_data.pt` when graph processing is active
- `analysis/metrics.json`
- `analysis/findings.json`
- `deliverables/result.md`
- `eval/report.json`
- `provenance/manifest.json`

## Working style
- Read `README.md`, `SPEC.md`, `WORKFLOW.md`, `architecture.md`, and `agent_roles.md` before making structural decisions.
- Update `decisions.md` when an implementation choice becomes part of the architecture.
- Keep docs concrete. Replace generic wording with operational instructions whenever possible.
