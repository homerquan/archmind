# Contributing

## How to contribute
1. Start with the docs. If behavior changes, update `SPEC.md`, `WORKFLOW.md`, `architecture.md`, or `decisions.md` first.
2. Keep all important stages artifact-backed and reproducible: repo fetch, graph construction, analysis, LLM interpretation, reporting, evaluation, provenance.
3. If graph behavior changes, update `data.md`, `eval.md`, and `decisions.md` with the new node or edge semantics, feature schema, provider behavior, or analysis assumptions.
4. Prefer small Python modules with explicit interfaces and durable file contracts.

## Contribution checklist
- [ ] Docs updated for behavioral changes
- [ ] New or changed artifacts documented
- [ ] Reproducibility notes updated: versions, commit sha, hashes, schema versions
- [ ] Evaluation updated for new behavior or metrics
- [ ] Security posture unchanged or documented in `security.md`

## Coding expectations for future implementation
- Prefer Python 3.11+ unless the docs justify another language for a specific subsystem.
- Use PyTorch Geometric (PyG) for graph encoding, processing, and future graph learning work by default.
- Use LiteLLM for supported provider integrations unless the docs justify a different abstraction.
- Keep canonical JSON graph artifacts separate from processed PyG artifacts.
- Keep LLM interpretation grounded in artifact-backed evidence.
- Keep REPL presentation concerns separate from analysis and reporting logic.
- Keep API-key handling isolated from logs, reports, and durable workspace artifacts.
- Avoid hidden global state and implicit runtime coupling between stages.
