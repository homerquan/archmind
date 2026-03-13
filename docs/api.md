# REPL Contract and Internal Interfaces

ArchMind v0 is REPL-only. There is no public HTTP API in scope for the first version.

## Startup command

```bash
archmind [<github_url>] [--branch main] [--output result.md] [--llm-provider openai]
```

## Startup inputs
- `github_url`: optional GitHub repository URL; if omitted, ask in the REPL
- `--branch`: optional branch name, defaults to `main`
- `--output`: optional Markdown output path, defaults to `result.md`
- `--llm-provider`: optional provider name, default can be prompted or configured

## User-visible outputs
- intro banner with ASCII art and version text
- progress bars for long-running stages
- concise findings printed inside the terminal REPL
- full Markdown report written to the output path

## Interactive prompts
- ask for repository URL when missing
- ask for branch when the user wants something other than `main`
- ask for output path when the user wants something other than `result.md`
- ask for LLM provider and API key when they are not already configured

## Internal interfaces worth preserving

### Repository fetch
- input: `github_url`, `branch`
- output: `inventory/repository_snapshot.json`

### Graph build
- input: repository snapshot and dependency inventory
- output: `graph/architecture_graph.json`

### PyG encode
- input: canonical graph plus feature schema config
- output: `graph/pyg_data.pt`

### LLM configuration
- input: provider selection and API key
- output: `input/llm_config.json`

### Analyze
- input: graph artifacts
- output: `analysis/metrics.json`, `analysis/findings.json`, `analysis/dsm.csv`

### Interpret
- input: analysis artifacts plus selected repository context
- output: `analysis/explanations.md`, `analysis/recommendations.json`

### Report
- input: findings and explanations
- output: `deliverables/result.md`
