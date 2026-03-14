## Tight Coupling

- Severity: `high`
- Summary: Modules or services depend too heavily on each other, so a small change in one area can break many others.

### Evidence
- Dependency cycles: 27
- Function call cycles: 29
- Cross-module function calls: 1571
- Top coupled modules: module:com.mongodb.lang.Nullable, module:org.bson.BsonDocument, module:com.mongodb.assertions.Assertions

### Recommendations
- Break cycles and reduce dependence on the hottest modules.
