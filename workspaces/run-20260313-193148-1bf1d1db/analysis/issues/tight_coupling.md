## Tight Coupling

- Severity: `medium`
- Summary: Modules or services depend too heavily on each other, so a small change in one area can break many others.

### Evidence
- Dependency cycles: 0
- Top coupled modules: module:server.tests.test_main_websocket, module:server.tests.test_main_routes, module:server.tests.test_main_memory

### Recommendations
- Break cycles and reduce dependence on the hottest modules.
