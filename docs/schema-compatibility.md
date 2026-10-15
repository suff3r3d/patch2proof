# Schema history

Earlier drafts kept `0.1.0` and `0.2.0` schema directories and included a
`schema_version` field in each record. The active contract now consists of one
schema set directly under [`schemas/`](../schemas/). Its IDs have no version
suffix, and records contain no schema version field. The repository validator
loads this one schema set. Historical records are not automatically converted;
they must be transformed and reviewed before they can be accepted by the
current contract.

The current verification checks use `status: passed | failed | not_evaluated`.
A former `passed: false` value cannot be converted to one of those states
without reviewing its evidence. The current contract also requires oracle,
adapter, and case definition identities. A conversion must preserve source
bytes and references, create new record IDs where content changes, and never
invent missing observations or identities.

Structural validation does not prove that a vulnerability was reproduced. The
package validator checks references and integrity; evidence interpretation
belongs to the oracle.
