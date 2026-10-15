"""Case-local immutable records and streamed content-addressed artifacts."""

from contextlib import contextmanager
from dataclasses import dataclass
import hashlib
import io
import os
from pathlib import Path, PureWindowsPath
import stat
from typing import BinaryIO, Iterator
from uuid import uuid4

from .contracts import Record, SchemaCatalog, canonical_json, decode_json


CHUNK_SIZE = 64 * 1024
DEFAULT_MAX_ARTIFACT_BYTES = 64 * 1024 * 1024
DEFAULT_MAX_RECORD_BYTES = 1024 * 1024


class StorageError(ValueError):
    def __init__(self, code: str, message: str, failure_class: str = "metadata_failure"):
        self.code, self.failure_class = code, failure_class
        super().__init__(message)


def relative_parts(path: str) -> tuple[str, ...]:
    if not isinstance(path, str) or not path or "\\" in path or "\x00" in path:
        raise StorageError("unsafe_path", "A portable case-relative path is required.")
    parts = tuple(path.split("/"))
    if PureWindowsPath(path).drive or any(part in ("", ".", "..") for part in parts):
        raise StorageError("unsafe_path", "Absolute, empty, dot, and parent path segments are forbidden.")
    return parts


@contextmanager
def directory_fd(root: Path, parts: tuple[str, ...] = (), *, create: bool = False) -> Iterator[int]:
    """Anchor every traversal; reject symlinks, including intermediate directories."""
    fd = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        for part in parts:
            if create:
                try:
                    os.mkdir(part, mode=0o700, dir_fd=fd)
                    os.fsync(fd)
                except FileExistsError:
                    pass
            next_fd = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
            os.close(fd)
            fd = next_fd
        yield fd
    finally:
        os.close(fd)


@contextmanager
def open_case_file(root: Path, relative_path: str) -> Iterator[BinaryIO]:
    parts = relative_parts(relative_path)
    with directory_fd(root, parts[:-1]) as parent:
        fd = os.open(parts[-1], os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=parent)
        try:
            if not stat.S_ISREG(os.fstat(fd).st_mode):
                raise StorageError("not_regular_file", "Evidence must be a regular file.")
            stream = os.fdopen(fd, "rb")
        except BaseException:
            os.close(fd)
            raise
        with stream:
            yield stream


def measure(stream: BinaryIO, max_bytes: int) -> tuple[str, int]:
    digest, size = hashlib.sha256(), 0
    while chunk := stream.read(min(CHUNK_SIZE, max_bytes - size + 1)):
        size += len(chunk)
        if size > max_bytes:
            raise StorageError("size_limit", "Artifact exceeds the configured byte limit.", "resource_failure")
        digest.update(chunk)
    return digest.hexdigest(), size


@dataclass(frozen=True)
class ArtifactRef:
    id: str
    sha256: str

    def to_dict(self) -> dict[str, str]:
        return {"id": self.id, "sha256": self.sha256}


@dataclass(frozen=True)
class StoredArtifact:
    reference: ArtifactRef
    path: str
    size_bytes: int
    record: Record


class CaseStore:
    """Write-once API. Reusing an ID requires byte-identical canonical JSON."""

    def __init__(self, root: Path, catalog: SchemaCatalog, *,
                 max_artifact_bytes: int = DEFAULT_MAX_ARTIFACT_BYTES,
                 max_record_bytes: int = DEFAULT_MAX_RECORD_BYTES):
        if max_artifact_bytes < 0 or max_record_bytes < 1:
            raise ValueError("storage limits must be nonnegative; record limit must be positive")
        self.root = Path(root).absolute()
        self.catalog = catalog
        self.max_artifact_bytes = max_artifact_bytes
        self.max_record_bytes = max_record_bytes

    @staticmethod
    def record_path(identifier: str) -> str:
        return f"records/{hashlib.sha256(identifier.encode('utf-8')).hexdigest()}.json"

    def _prepare(self) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        with directory_fd(self.root, ("records",), create=True):
            pass
        with directory_fd(self.root, ("artifacts", "sha256"), create=True):
            pass

    @contextmanager
    def _staged(self, parts: tuple[str, ...]):
        with directory_fd(self.root, parts) as parent:
            name = f".pending-{uuid4().hex}"
            fd = os.open(name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                         0o600, dir_fd=parent)
            try:
                with os.fdopen(fd, "wb") as stream:
                    yield parent, name, stream
            finally:
                os.unlink(name, dir_fd=parent)

    @staticmethod
    def _publish(parent: int, temporary: str, final: str, stream: BinaryIO) -> bool:
        stream.flush()
        os.fsync(stream.fileno())
        os.fchmod(stream.fileno(), 0o444)
        try:
            os.link(temporary, final, src_dir_fd=parent, dst_dir_fd=parent, follow_symlinks=False)
        except FileExistsError:
            return False
        os.fsync(parent)
        return True

    def put_record(self, record: Record) -> str:
        self.catalog.require_valid(record)
        data = canonical_json(record)
        if len(data) > self.max_record_bytes:
            raise StorageError("record_size_limit", "Record exceeds the metadata byte limit.", "resource_failure")
        if record["schema"] == "artifact-record" and record["available"]:
            with open_case_file(self.root, record["path"]) as source:
                if measure(source, self.max_artifact_bytes) != (record["sha256"], record["size_bytes"]):
                    raise StorageError("artifact_integrity", "Artifact bytes must match before their record can be published.")
        self._prepare()
        path = self.record_path(record["id"])
        with self._staged(("records",)) as (parent, name, stream):
            stream.write(data)
            if not self._publish(parent, name, path.split("/")[-1], stream):
                with open_case_file(self.root, path) as existing:
                    if existing.read(self.max_record_bytes + 1) != data:
                        raise StorageError("record_conflict", "An immutable record ID already has different content.")
        return path

    def put_artifact(self, source: BinaryIO, *, identifier: str, case_id: str,
                     kind: str, provenance: Record,
                     derived_from: tuple[ArtifactRef, ...] = ()) -> StoredArtifact:
        self._prepare()
        with self._staged(("artifacts", "sha256")) as (parent, name, stream):
            digest, size = hashlib.sha256(), 0
            while True:
                chunk = source.read(min(CHUNK_SIZE, self.max_artifact_bytes - size + 1))
                if not isinstance(chunk, bytes):
                    raise StorageError("non_binary_input", "Artifact source must return bytes.")
                if not chunk:
                    break
                size += len(chunk)
                if size > self.max_artifact_bytes:
                    raise StorageError("size_limit", "Artifact exceeds the configured byte limit.", "resource_failure")
                stream.write(chunk)
                digest.update(chunk)
            sha256 = digest.hexdigest()
            path = f"artifacts/sha256/{sha256}"
            record = {
                "schema": "artifact-record",
                "id": identifier, "case_id": case_id, "provenance": provenance,
                "kind": kind, "available": True, "path": path,
                "sha256": sha256, "size_bytes": size,
            }
            if derived_from:
                record["derived_from"] = [ref.to_dict() for ref in derived_from]
            self.catalog.require_valid(record)
            if not self._publish(parent, name, sha256, stream):
                with open_case_file(self.root, path) as existing:
                    if measure(existing, self.max_artifact_bytes) != (sha256, size):
                        raise StorageError("artifact_conflict", "Existing content-addressed bytes are corrupt.")
        # Bytes become durable before the record is published. A failed record
        # publication can leave a complete unreferenced blob, never a partial one.
        self.put_record(record)
        return StoredArtifact(ArtifactRef(identifier, sha256), path, size, record)

    def put_bytes(self, data: bytes, **metadata) -> StoredArtifact:
        return self.put_artifact(io.BytesIO(data), **metadata)

    def load_records(self, *, max_records: int = 10000) -> list[Record]:
        if max_records < 1:
            raise ValueError("max_records must be positive")
        with directory_fd(self.root, ("records",)) as parent:
            names = []
            with os.scandir(parent) as entries:
                for entry in entries:
                    if entry.name.endswith(".json"):
                        names.append(entry.name)
                        if len(names) > max_records:
                            raise StorageError("record_count_limit", "Package has too many records.", "resource_failure")
        records = []
        for name in sorted(names):
            path = f"records/{name}"
            with open_case_file(self.root, path) as stream:
                data = stream.read(self.max_record_bytes + 1)
            if len(data) > self.max_record_bytes:
                raise StorageError("record_size_limit", "Record exceeds the metadata byte limit.", "resource_failure")
            try:
                record = decode_json(data)
            except (ValueError, UnicodeError, RecursionError) as error:
                raise StorageError("malformed_record", "Stored record is not strict JSON.") from error
            self.catalog.require_valid(record)
            if self.record_path(record["id"]) != path:
                raise StorageError("record_identity_mismatch", "Record filename does not match its ID.")
            records.append(record)
        return records
