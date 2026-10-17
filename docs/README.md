# Documentation

Start with the guide for the task at hand. The JSON files in [schemas](../schemas/README.md)
define the current record contracts; historical designs do not override them.

| Document | Purpose |
| --- | --- |
| [Package foundation](package-foundation.md) | Implemented storage API, validation CLI, integrity checks and limits. |
| [Schema usage](schema-usage-guide.md) | How producers populate the eight current record types. |
| [Schema compatibility](schema-compatibility.md) | Historical version differences; the active schemas are unversioned. |
| [Revision discovery contract](revision-discovery-contract.md) | CVE-only input and evidence-backed candidate revision pairs. |
| [Environment reproduction](environment-reproduction.md) | Paired source preparation, offline Docker builds, and review boundaries. |
| [Verification and execution contract](verification-contract.md) | Evidence requirements, verdict rules, adapter boundaries and paired execution. |

Storage and package validation are implemented. Paired Docker builds require a
reviewed case and offline inputs; target execution and a CVE-specific oracle
are not implied by valid package records.
Read [AGENTS.md](../AGENTS.md) for repository rules and
[test instructions](../tests/schema/README.md) for Docker-only checks.

## Historical design material

The [archive](archive/README.md) preserves the comprehensive schema plan,
field design and consistency review. Consult it for earlier reasoning or deferred
requirements, not instructions for current producers. Repeated MVP field lists
were removed from the old proposal; use the usage guide and versioned schemas.
