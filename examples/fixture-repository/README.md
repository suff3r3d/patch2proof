# Fixture repository

The default dry-run case keeps its patch in `examples/fixtures/demo.patch` and
stores immutable source snapshots under `fixture-vulnerable/` and `fixture-fixed/`.
`source_mode: fixture` reads those directories by the manifest's revision names,
so patch hunks can be mapped to symbols and caller chains without a Git checkout
or Docker build.
