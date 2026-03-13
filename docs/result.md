# ArchMind Report

## Run Context
- Repository: `https://github.com/homerquan/ApronAI`
- Branch: `main`
- Commit: `5e57888d10f0ace760154182e388af9a654a538e`
- Output path: `result.md`
- LLM provider: `gemini`
- LLM model: `gemini/gemini-1.5-flash`
- API key source: `prompt`

## Summary Metrics
- Modules analyzed: `8`
- Dependency edges: `0`
- Cycle count: `0`
- Articulation points: `0`

## Findings
- **coupling_hotspot** (low): module:server.tests.test_main_websocket has elevated coupling pressure.
- **coupling_hotspot** (low): module:server.tests.test_main_routes has elevated coupling pressure.
- **coupling_hotspot** (low): module:server.tests.test_main_memory has elevated coupling pressure.

# Architecture Findings

## Overview
- Repository: `https://github.com/homerquan/ApronAI`
- Branch: `main`
- Commit: `5e57888d10f0ace760154182e388af9a654a538e`
- Modules analyzed: `8`
- Internal dependency edges: `0`

## Key Findings
- **coupling_hotspot**: module:server.tests.test_main_websocket has elevated coupling pressure. (targets: module:server.tests.test_main_websocket)
- **coupling_hotspot**: module:server.tests.test_main_routes has elevated coupling pressure. (targets: module:server.tests.test_main_routes)
- **coupling_hotspot**: module:server.tests.test_main_memory has elevated coupling pressure. (targets: module:server.tests.test_main_memory)

## Recommendations
- Reduce dependency pressure around module:server.tests.test_main_websocket by moving shared concerns behind narrower interfaces.
- Reduce dependency pressure around module:server.tests.test_main_routes by moving shared concerns behind narrower interfaces.
- Reduce dependency pressure around module:server.tests.test_main_memory by moving shared concerns behind narrower interfaces.
