## Scalability Bottlenecks

- Severity: `medium`
- Summary: The architecture contains centralized or blocking components that limit growth.

### Evidence
- Shared flow targets: none
- Top dependency hotspots: module:server.tests.test_main_websocket, module:server.tests.test_main_routes, module:server.tests.test_main_memory

### Recommendations
- Reduce central chokepoints and shorten synchronous dependency paths.
