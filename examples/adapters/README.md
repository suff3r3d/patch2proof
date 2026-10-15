# Reviewed adapter template

Patch2Proof intentionally does not guess how an application starts. A real
case supplies a reviewed adapter that is registered by deployment code, not by
the model. The adapter receives a typed `SafePoC`, a role (`vulnerable` or
`fixed`) and a scoped run directory; it returns structured observations such as
`entrypoint_invoked`, `patch_slice_reached`, `semantic_transition`,
`oracle_signal` and `repeatable`.

The adapter must:

- use a fixed, reviewed test fixture for the case;
- use the same SafePoC and fixture for both roles;
- write raw logs/trace under the supplied run directory;
- return provenance IDs for those artifacts;
- never accept a command, URL, credential or host path from the model;
- fail closed when the fixture or oracle is unavailable.

For a first implementation, create a separate lab package and call:

```python
from patch2proof.tools.test_adapters import register_adapter

register_adapter("my-case-v1", my_reviewed_role_adapter)
```

Do not use the synthetic `fixture_simulated_differential` adapter as evidence
for a real claim. The proof bundle marks all simulation as `candidate`.
