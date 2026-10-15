"""Offline validation against the single repository schema set."""

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker
from referencing import Registry, Resource


Record = dict[str, Any]  # External JSON is schema-validated at every boundary.
RECORD_TYPES = frozenset({
    "source-record", "artifact-record", "vulnerability-record", "environment-spec",
    "build-record", "execution-record", "verification-result", "case-manifest",
})


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def canonical_json(value: Any) -> bytes:
    return (json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False,
                       separators=(",", ":")) + "\n").encode("utf-8")


def decode_json(data: bytes) -> Any:
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("duplicate JSON key")
            result[key] = value
        return result

    def reject_constant(_value):
        raise ValueError("non-finite JSON number")

    return json.loads(data, object_pairs_hook=unique, parse_constant=reject_constant)


def pointer(parts) -> str:
    return "".join("/" + str(part).replace("~", "~0").replace("/", "~1") for part in parts)


@dataclass(frozen=True)
class Diagnostic:
    code: str
    failure_class: str
    message: str
    record_id: str | None = None
    path: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


class ContractError(ValueError):
    def __init__(self, diagnostics: tuple[Diagnostic, ...]):
        self.diagnostics = diagnostics
        super().__init__("; ".join(item.message for item in diagnostics))


class SchemaCatalog:
    """Load trusted repository schemas; never retrieve schemas over the network."""

    def __init__(self, schema_root: Path):
        self.schemas = {}
        for name in sorted(RECORD_TYPES | {"common"}):
            path = Path(schema_root) / f"{name}.schema.json"
            schema = decode_json(path.read_bytes())
            expected = f"urn:dacn:schema:{name}"
            if schema.get("$id") != expected:
                raise ValueError(f"incorrect schema identity for {name}")
            Draft202012Validator.check_schema(schema)
            self.schemas[expected] = schema
        self.registry = Registry().with_resources([
            (uri, Resource.from_contents(schema)) for uri, schema in self.schemas.items()
        ])
        self.validators = {
            uri: Draft202012Validator(schema, registry=self.registry, format_checker=FormatChecker())
            for uri, schema in self.schemas.items()
        }

    def validate(self, record: Any) -> tuple[Diagnostic, ...]:
        if not isinstance(record, dict):
            return (Diagnostic("schema_invalid", "metadata_failure", "Record must be an object."),)
        identifier = record.get("id") if isinstance(record.get("id"), str) else None
        name = record.get("schema")
        if not isinstance(name, str) or name not in RECORD_TYPES:
            return (Diagnostic("unsupported_schema", "metadata_failure", "Unknown record schema.", identifier, "/schema"),)
        try:
            canonical_json(record)
        except (TypeError, ValueError, UnicodeError, RecursionError):
            return (Diagnostic("invalid_json", "metadata_failure", "Record is not finite, serializable JSON.", identifier),)
        validator = self.validators[f"urn:dacn:schema:{name}"]
        errors = sorted(validator.iter_errors(record), key=lambda error: pointer(error.absolute_path))
        return tuple(Diagnostic(
            "schema_invalid", "metadata_failure",
            f"Schema constraint failed: {error.validator}.", identifier, pointer(error.absolute_path),
        ) for error in errors)

    def require_valid(self, record: Any) -> None:
        diagnostics = self.validate(record)
        if diagnostics:
            raise ContractError(diagnostics)
