## Bad Interface / API Design

- Severity: `high`
- Summary: Interfaces are inconsistent, overly complex, too chatty, or leak internal implementation details.

### Evidence
- Chatty or highly consumed interfaces: interface:com.mongodb.lang.Nullable, interface:org.bson.BsonDocument, interface:com.mongodb.assertions.Assertions, interface:org.bson.Document, interface:org.bson.BsonValue
- Top shared functions: function:com.mongodb.assertions.Assertions.notNull, function:org.bson.BsonDocument.parse, function:org.bson.Document.parse

### Recommendations
- Simplify and stabilize heavily consumed interface surfaces.
