# Security and safety

ArchMind handles untrusted source code metadata, runtime telemetry, infrastructure data, incident history, and processed graph artifacts. The security posture must cover all of them.

## Threat model

### 1. Prompt injection through source evidence
- malicious text in repository files, tickets, incidents, runbooks, or metadata

Mitigations:
- treat all external content as untrusted
- keep repo policy above source content in prompts
- isolate tool execution inside per-run workspaces
- restrict network egress to allowlisted domains

### 2. Supply-chain risk
- unpinned dependencies
- arbitrary parsers or adapters
- model or checkpoint drift

Mitigations:
- pin dependencies and record versions
- log provenance for generated artifacts and model artifacts
- keep permissions minimal

### 3. Unsafe graph and tensor deserialization
- loading untrusted `.pt`, pickle, or checkpoint files
- accepting externally supplied processed graph artifacts

Mitigations:
- only load trusted model and tensor artifacts from controlled workspaces
- prefer rebuilding PyG artifacts from canonical JSON graph inputs
- checksum graph and model artifacts

### 4. Data exfiltration
- agents reading secrets or unrelated local files
- agents uploading code or telemetry to unapproved endpoints

Mitigations:
- secret scanning
- sandboxed environment variables
- strict network controls
- explicit allowed command list

### 5. API-key handling risk
- user-supplied LLM API keys leaked through logs, reports, or saved config

Mitigations:
- collect keys interactively or through environment variables
- never print full keys back to the terminal
- never store raw keys in workspace artifacts
- persist only safe provider metadata when necessary

### 6. Risky recommendations
- architecture suggestions that optimize one metric while harming safety, operability, or ownership boundaries

Mitigations:
- require explainability and tradeoff reporting
- evaluate safety flags on migration paths
- route risky outputs to human review

## Operational posture checklist
- [ ] Workspace isolation enabled
- [ ] Network egress policy set
- [ ] Allowed tools and commands documented
- [ ] Logging enabled
- [ ] Provenance manifest required
- [ ] Graph artifacts validated before model use
- [ ] Evaluation gates required
