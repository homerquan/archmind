# Decisions

Record architecture and product decisions here when they affect implementation.

## ADR template

### Decision: <short title>
- Date: YYYY-MM-DD
- Status: Proposed | Accepted | Deprecated
- Context:
- Decision:
- Consequences:
- Alternatives considered:

---

### Decision: Ship v0 as a Python REPL-style CLI
- Date: 2026-03-13
- Status: Accepted
- Context: The first release needs to stay simple, local, and easy to reason about.
- Decision: Keep v0 terminal-only, implement it in Python, and expose the workflow through a REPL-style interface launched as `archmind`, with optional startup parameters and interactive prompting for missing inputs.
- Consequences: No web UI or service layer should be introduced unless the docs are updated first.
- Alternatives considered: single-shot CLI only, web UI, local desktop app, background service

### Decision: Use GitHub URL plus optional branch as the only v0 input
- Date: 2026-03-13
- Status: Accepted
- Context: The first release should operate on a single repository with minimal user input.
- Decision: Accept a GitHub repository URL and optional branch, with branch defaulting to `main`, and collect missing values interactively inside the REPL.
- Consequences: Runtime and infrastructure inputs are out of scope for v0.
- Alternatives considered: local path input, multi-repo input, mixed repository and telemetry input

### Decision: Adopt Python and PyTorch Geometric as the default graph stack
- Date: 2026-03-13
- Status: Accepted
- Context: The system needs a concrete implementation direction for architecture graph encoding, preprocessing, and analysis.
- Decision: Use Python 3.11+, PyTorch, and PyTorch Geometric (PyG) by default. Represent multi-entity architecture graphs with `torch_geometric.data.HeteroData` unless a documented exception is approved.
- Consequences: Future code generation should target a Python-first architecture and avoid introducing a competing graph framework without an ADR.
- Alternatives considered: networkx-only pipelines, DGL, custom graph containers

### Decision: Start with explainable structural analyses before advanced learned optimization
- Date: 2026-03-13
- Status: Accepted
- Context: The first useful version should produce credible, inspectable results quickly.
- Decision: Prioritize DSM, coupling metrics, cycle detection, centrality, and LLM-grounded interpretation before more advanced GNN or RL features.
- Consequences: Early versions stay easier to validate and debug.
- Alternatives considered: starting with RL-driven optimization first

### Decision: Use LiteLLM for first-version provider abstraction
- Date: 2026-03-13
- Status: Accepted
- Context: The first version should let users bring their own provider keys without multiplying provider-specific client logic.
- Decision: Support OpenAI, Anthropic, and Gemini through LiteLLM, with provider choice and API key entry available in the REPL.
- Consequences: Secret handling and provider configuration need explicit safeguards in the terminal flow.
- Alternatives considered: single-provider support, direct provider SDK integrations only
