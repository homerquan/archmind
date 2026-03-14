## Poor Separation of Concerns

- Severity: `low`
- Summary: Business logic, infrastructure code, UI behavior, and data access are mixed together.

### Evidence
- Mixed concern modules: none
- Cross-module function calls: 0

### Recommendations
- Separate domain logic from persistence and transport concerns.
