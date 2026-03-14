## Low Cohesion

- Severity: `high`
- Summary: A module or service handles too many unrelated responsibilities.

### Evidence
- Highest dependency span: 528
- Highest function fan-in: 143
- Modules with broad span: module:com.mongodb.lang.Nullable, module:org.bson.BsonDocument, module:com.mongodb.assertions.Assertions

### Recommendations
- Split overly broad modules into more focused units.
