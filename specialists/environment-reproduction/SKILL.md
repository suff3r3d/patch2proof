---
name: environment-reproduction
description: Investigate and propose an evidence-backed paired build and startup environment for pinned vulnerable and fixed Patch2Proof revisions.
---

# Environment reproduction specialist

## Task and inputs

Read both pinned revisions, build manifests, lockfiles, documentation, patch context, policy, and observed build/startup diagnostics. Determine toolchain, dependency supply, build options, feature flags, generated assets, services, working directory, executable, startup arguments, and observable readiness. Investigate revision-specific differences rather than assuming one recipe works unchanged.

## Output contract

Propose one shared paired environment with justified role overrides, explicit unknowns, source evidence IDs, and bounded checks for unresolved requirements. Use [the environment specification](../../schemas/environment-spec.schema.json) as the declaration contract and [the build record](../../schemas/build-record.schema.json) for later observations; follow [the schema usage guide](../../docs/schema-usage-guide.md#7-declared-environment-versus-observed-build). A proposed version, flag, or dependency is not an observed installation. Distinguish environment repairs from source or semantic changes.

## Boundary and handoff

Do not execute model-generated shell, modify pinned source, select an unreviewed base image, or broaden build/runtime network policy. Request bounded, read-only inspection or approved Docker build operations through controlled tools. The validator checks image digests, role parity, dependency inputs, resource limits, and policy; a human reviews the concrete build recipe before execution. On failure, classify the layer and propose a new reviewed recipe rather than silently changing it.
