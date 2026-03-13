# Roadmap

## v0
- Build a Python REPL-style CLI launched as `archmind`
- Clone the repository and default to `main` when branch is omitted
- Prompt interactively for missing repository, branch, output, provider, and API-key inputs
- Build canonical `graph/architecture_graph.json`
- Standardize PyG preprocessing into `graph/pyg_data.pt`
- Produce DSM, coupling, cycle, and centrality analysis
- Add a polished terminal intro banner with ASCII art and version display
- Add progress bars for long-running stages
- Support OpenAI, Anthropic, and Gemini through LiteLLM
- Generate terminal output plus Markdown report in `result.md`

## v1
- Improve graph extraction quality across more Python and polyglot repo layouts
- Add more architecture heuristics and richer recommendation ranking
- Add better repository-context selection for LLM interpretation
- Add machine-readable export formats alongside Markdown

## v2
- Add learned graph scoring and more advanced PyG models
- Add multi-repo or monorepo-aware architecture views
- Add richer evaluation and benchmarking
