## Weak Fault Isolation

- Severity: `high`
- Summary: Failures in one component easily spread to others, causing cascading outages.

### Evidence
- Articulation points: module:com.mongodb.AwsCredential, module:com.mongodb.ClusterFixture, module:com.mongodb.ConnectionString, module:com.mongodb.DB, module:com.mongodb.DBObjectCodec
- Function bridge points: function:com.mongodb.AbstractConnectionStringTest.testValidAuth, function:com.mongodb.AuthConnectionStringTest.assertMechanismProperties, function:com.mongodb.AuthConnectionStringTest.getMongoCredential, function:com.mongodb.AuthenticationMechanism.getMechanismName, function:com.mongodb.AutoEncryptionSettings.builder
- Cycle count: 27

### Recommendations
- Introduce isolation boundaries around bridge nodes and cycle-heavy paths.
