# Data and graph artifacts

This project manages three data classes:
- repository evidence used to understand the codebase structure
- graph artifacts used for analysis
- optional training or evaluation datasets used for future model development

## Repository evidence classes
- Repository snapshot: GitHub URL, branch, commit sha, language hints
- Source tree inventory: directories, packages, modules, files, entrypoints
- Dependency inventory: imports, manifests, internal references, external dependencies

## Graph artifacts
Graph artifacts are first-class data products, not temporary intermediates.

Required artifacts:
- `graph/architecture_graph.json`: canonical inspectable architecture graph
- `graph/feature_schema.json`: feature definitions and preprocessing metadata
- `graph/pyg_data.pt`: processed PyG artifact when graph encoding is active
- `input/llm_config.json`: safe provider configuration without raw secret leakage

Recommended v0 node types:
- repository
- package
- module
- file
- class_or_symbol
- external_dependency
- entrypoint

Recommended v0 edge types:
- contains
- imports
- depends_on
- calls
- inherits_from
- implements
- uses

## PyG guidance
- Use PyTorch Geometric (PyG) for graph encoding, preprocessing, transforms, and future graph learning work.
- Prefer `torch_geometric.data.HeteroData`.
- Keep the canonical JSON graph and the PyG artifact separate.
- Document feature names, embedding provenance, vocabularies, and normalization stats in `graph/feature_schema.json`.
- Do not accept untrusted `.pt` artifacts from outside the controlled workspace.

## Source provenance
Track at minimum:
- GitHub URL
- selected branch
- resolved commit sha
- access time
- transform history
- trust level

## LLM configuration handling
- Support OpenAI, Anthropic, and Gemini through LiteLLM.
- Never write raw API keys into reports, logs, or durable analysis artifacts.
- If configuration metadata is persisted, store only safe fields such as provider, selected model, and key source.
