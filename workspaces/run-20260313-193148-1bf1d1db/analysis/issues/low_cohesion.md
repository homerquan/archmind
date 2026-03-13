## Low Cohesion

- Severity: `low`
- Summary: A module or service handles too many unrelated responsibilities.

### Evidence
- Highest dependency span: 0
- Modules with broad span: module:server.tests.test_main_websocket, module:server.tests.test_main_routes, module:server.tests.test_main_memory

### Recommendations
- Split overly broad modules into more focused units.
