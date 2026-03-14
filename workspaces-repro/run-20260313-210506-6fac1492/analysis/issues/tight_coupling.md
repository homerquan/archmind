## Tight Coupling

- Severity: `low`
- Summary: Modules or services depend too heavily on each other, so a small change in one area can break many others.

### Evidence
- Dependency cycles: 0
- Function call cycles: 0
- Cross-module function calls: 0
- Top coupled modules: none

### Recommendations
- Break cycles and reduce dependence on the hottest modules.
