# Evaluation

Evaluation is a hard gate, not a cosmetic afterthought. ArchMind should evaluate graph integrity, analysis usefulness, LLM grounding, and report completeness.

## Evaluation levels

### L0: Graph and schema validity
- required graph artifacts exist
- node and edge ids are unique and stable
- disallowed edge relations are absent
- `graph/feature_schema.json` matches the processed PyG artifact

### L1: Analysis quality
- DSM is generated successfully
- coupling metrics are computed for identifiable entities
- cycles and centrality findings are grounded in graph evidence

### L2: LLM grounding quality
- explanations reference graph findings and repository entities
- no unsupported architecture claims appear in the report

### L3: Report quality
- terminal summary is generated
- intro banner is generated
- progress feedback is shown for long-running steps
- Markdown report is written to the requested path
- the report includes findings, evidence, and recommendations

## Core metrics
- `graph_schema_pass` boolean
- `dsm_generated` boolean
- `coupling_metrics_coverage` in [0,1]
- `cycle_detection_pass` boolean
- `explainability_score` in [0,1]
- `grounding_pass` boolean
- `report_generated` boolean
- `repl_experience_pass` boolean
- `reproducibility_ready` boolean

## Outputs
- `eval/report.json`: pass or fail plus summary and gate decisions
- `eval/metrics.json`: machine-readable metrics
- `eval/notes.md`: concise human-readable findings
