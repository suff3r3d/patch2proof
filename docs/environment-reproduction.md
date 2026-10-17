# Environment reproduction

Patch2Proof can inspect the build metadata at two pinned Git revisions, create
separate source archives, and build a Docker image for each revision. The build
path is fail-closed: it does not download dependencies, guess a startup command,
or treat a successful image build as vulnerability evidence.

## From a CVE to a reviewed case

1. Run `p2p run CVE-YYYY-NNNN --dry-run --auto-approve` to obtain
   `revision-discovery-result.json` and a draft `case.json`.
2. Review the selected repository, both commits, the patch, and the target's
   build instructions. Copy the draft case to a separate manifest and edit it.
3. Supply a reviewed Dockerfile and offline dependencies when the default
   template reports that it cannot recreate the target. Set
   `policy.allow_docker_build: true` only in the reviewed manifest.
4. Inspect the plan with `uv run p2p recreate-environment path/to/case.yaml`.
5. With a local Docker daemon, the reviewed base image preloaded, and an
   authorized case, run
   `uv run p2p recreate-environment path/to/case.yaml --build`.

The command writes each attempt under
`<output_dir>/environment-runs/<run-id>/<case-id>/`. The key artifacts are
`case.json` (reviewed input), `environment-reproduction.json` (outcome),
`environment-profile.json` (detected build metadata and manifest hashes),
`docker-plan.json`, `source-pair.json` (both commit identities and source archive
SHA-256 values), and `images.json` (actual image IDs, base image IDs, and build
provenance). Each completed image and each build log is also saved separately,
so a failed second build retains evidence from the first. A failed build exits
nonzero and reports its reason. The full
LangGraph path uses the same inspection and build worker.

## Build boundaries

- CVE-only input remains dry-run. A fixing commit's parent is a candidate
  vulnerable revision and requires review before a real build.
- The default templates are only suitable for simple projects whose build
  requirements are already satisfied offline. Python requirements, project
  installation steps, and other language-specific startup/dependency steps
  require a reviewed Dockerfile and offline dependency supply.
- Both source revisions get separate build contexts. The worker requires an
  available Docker daemon, a preloaded base image, a single literal `FROM`
  instruction, an allowlisted base image, and `--network=none` for builds.
- Image construction does not execute the SafePoC or confirm a vulnerability.
  That requires a separate reviewed test adapter and paired runtime evidence.

For example, CVE-2024-27287 resolves to an ESPHome Python repository, but its
requirements and package installation exceed the generic Python template. The
environment inspection therefore requests a reviewed build definition rather
than claiming the target environment was reproduced.
