# Schema contract tests

The suite validates the current schemas in `schemas/` offline.
It checks Draft 2020-12 validity, duplicate keys, offline `$ref` resolution,
valid/invalid fixtures, partial failures, three-state checks,
required oracle identity, and complete success packages. These are contract
tests. The full discovery command below also runs `tests/infrastructure/`, which
tests the implemented artifact store and semantic validator. No runtime oracle
or vulnerable target is executed.

## Docker-only workflow

Run the commands below from the repository root in one shell. The pinned Python
image is for Linux amd64. If Docker is unavailable, stop; do not run tests on the
host. Dependency acquisition uses the network; test execution does not.

```sh
dacn_test_image=python@sha256:6b1f85a08c199d29d5b6d71ab9c27bd5b3b393492e01216a15758ff69c4be8b8
docker pull --platform linux/amd64 "$dacn_test_image"
dacn_deps_volume=$(docker volume create)
docker run --rm --platform linux/amd64 --read-only \
  --memory=512m --pids-limit=64 --tmpfs /tmp:rw,nosuid,nodev,size=128m \
  --mount "type=volume,src=$dacn_deps_volume,dst=/deps" \
  --mount "type=bind,src=$PWD/requirements-dev.txt,dst=/requirements-dev.txt,readonly" \
  --mount "type=bind,src=$PWD/tests/schema/requirements-lock.txt,dst=/requirements-lock.txt,readonly" \
  "$dacn_test_image" timeout 180 sh -c \
  'python -m pip install --disable-pip-version-check --no-cache-dir --only-binary=:all: --target /deps -r /requirements-lock.txt -c /requirements-dev.txt && python -m pip freeze --path /deps > /deps/resolved-requirements.txt'
```

Proceed only after acquisition succeeds. The dependency volume is read-only
during tests; all writable container storage is the bounded temporary directory.
The workspace is read-only and Python bytecode writes are disabled.

```sh
docker run --rm --platform linux/amd64 --network none --read-only \
  --memory=512m --pids-limit=64 --tmpfs /tmp:rw,nosuid,nodev,size=128m \
  --mount "type=volume,src=$dacn_deps_volume,dst=/deps,readonly" \
  --mount "type=bind,src=$PWD,dst=/workspace,readonly" \
  --workdir /workspace --env PYTHONPATH=/deps --env PYTHONDONTWRITEBYTECODE=1 \
  "$dacn_test_image" timeout 120 python -m unittest discover -s tests -p 'test_*.py' -v
```

The lock file records the exact dependency resolution used for this schema
revision. It contains no target or CVE dependencies. Retain the dependency volume
for offline reruns; its `resolved-requirements.txt` records the installed versions.

## Fixture and compatibility limits

`fixtures.py` contains the base examples; `fixtures_current.py` contains
early-failure scenarios. They use synthetic identities and hashes
and do not represent complete replayable packages. Tests reject missing evidence
references where required. Infrastructure tests separately check real synthetic
bytes and package relationships; CVE attribution remains future oracle work.

