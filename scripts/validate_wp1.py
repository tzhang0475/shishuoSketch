#!/usr/bin/env python3
"""Validate WP1 schemas, references, canonical provenance, and static output."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

try:
    from jsonschema import Draft202012Validator
except ImportError as exc:  # pragma: no cover - exercised only in incomplete environments
    raise SystemExit("WP1 validation requires the Python 'jsonschema' package") from exc

try:
    from .reading_layers import canonical_sections, validate_punctuation_round_trip
except ImportError:  # pragma: no cover - direct script execution
    from reading_layers import canonical_sections, validate_punctuation_round_trip


OBJECTS = {
    "Source": ("schema/source.schema.json", "data/sources/wp1-sources.json", "sources"),
    "Story": ("schema/story.schema.json", "data/annotation/wp1-stories.json", "stories"),
    "Person": ("schema/person.schema.json", "data/annotation/wp1-people.json", "people"),
    "Mention": ("schema/mention.schema.json", "data/annotation/wp1-mentions.json", "mentions"),
    "Relation": ("schema/relation.schema.json", "data/annotation/wp1-relations.json", "relations"),
    "Era": ("schema/era.schema.json", "data/annotation/wp1-eras.json", "eras"),
    "Evidence": ("schema/evidence.schema.json", "data/evidence/wp1-evidence.json", "evidence"),
}

PUNCTUATION_SCHEMA = "schema/punctuation.schema.json"
PUNCTUATION_DATA = "data/annotation/wp1-punctuation.json"

PROVENANCE_MODES = ("full", "portable")
SHISHUO_PROVENANCE_LOCK = "sources/registry/shishuo-provenance.lock.json"
PORTABLE_SOURCE_AVAILABILITIES = {
    "git-ignored-upstream-payload",
    "ignored-upstream-payload",
    "external-source-payload",
}


def read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise ValueError(f"missing JSON file: {path}")
    except json.JSONDecodeError as exc:
        raise ValueError(f"malformed JSON in {path}: line {exc.lineno}, column {exc.colno}: {exc.msg}")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def frontmatter_fields(path: Path) -> dict[str, str]:
    """Read only simple scalar fields from a derived Markdown front matter."""
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        raise ValueError(f"{path} has no YAML front matter")
    end = text.find("\n---\n", 4)
    if end < 0:
        raise ValueError(f"{path} has no YAML front matter terminator")
    fields: dict[str, str] = {}
    for line in text[4:end].splitlines():
        if not line or line[0].isspace() or ":" not in line:
            continue
        key, raw = line.split(":", 1)
        value = raw.strip()
        if len(value) >= 2 and value[0] == '"' and value[-1] == '"':
            try:
                value = json.loads(value)
            except json.JSONDecodeError:
                value = value[1:-1]
        fields[key.strip()] = value
    return fields


def resolve_relative_file(root: Path, value: Any, label: str, errors: list[str]) -> Path | None:
    if not isinstance(value, str) or not value:
        errors.append(f"{label}: path must be a non-empty relative string")
        return None
    relative = Path(value)
    if relative.is_absolute() or ".." in relative.parts:
        errors.append(f"{label}: path must remain inside the repository: {value!r}")
        return None
    path = (root / relative).resolve()
    try:
        path.relative_to(root.resolve())
    except ValueError:
        errors.append(f"{label}: path escapes the repository: {value!r}")
        return None
    if not path.is_file():
        errors.append(f"{label}: file does not exist: {value!r}")
        return None
    return path


def resolve_relative_path(root: Path, value: Any, label: str, errors: list[str]) -> Path | None:
    """Resolve a repository-relative path without requiring the file to exist."""
    if not isinstance(value, str) or not value:
        errors.append(f"{label}: path must be a non-empty relative string")
        return None
    relative = Path(value)
    if relative.is_absolute() or ".." in relative.parts:
        errors.append(f"{label}: path must remain inside the repository: {value!r}")
        return None
    path = (root / relative).resolve()
    try:
        path.relative_to(root.resolve())
    except ValueError:
        errors.append(f"{label}: path escapes the repository: {value!r}")
        return None
    return path


def _trusted_source_records(root: Path, errors: list[str]) -> dict[str, list[dict[str, Any]]]:
    """Load committed file identities used when ignored source payloads are absent.

    The Jinshu/Wikisource lock already records source-text files inside each
    volume record.  The small Shishuo lock supplies the equivalent record for
    the Kanripo payload, without copying any source text into Git.
    """
    lock_paths: list[Path] = []
    shishuo_lock = root / SHISHUO_PROVENANCE_LOCK
    if shishuo_lock.is_file():
        lock_paths.append(shishuo_lock)
    downloads_root = root / "sources/downloads"
    if downloads_root.is_dir():
        lock_paths.extend(sorted(downloads_root.glob("**/manifest.lock.json")))

    by_path: dict[str, list[dict[str, Any]]] = {}

    def add_record(
        descriptor: Any,
        *,
        witness_id: Any,
        availability: Any,
        lock_path: Path,
        source_identity: Any,
        registry_path: Any,
    ) -> None:
        if not isinstance(descriptor, dict):
            return
        source_path = descriptor.get("path")
        source_sha256 = descriptor.get("sha256")
        if not isinstance(source_path, str) or not isinstance(source_sha256, str):
            return
        if not isinstance(witness_id, str) or not witness_id:
            errors.append(f"trusted provenance {lock_path}: file record has no witness_id: {source_path!r}")
            return
        record = {
            "witness_id": witness_id,
            "source_path": source_path,
            "source_sha256": source_sha256,
            "availability": availability,
            "lock_path": lock_path.as_posix(),
            "source_identity": source_identity,
            "registry_path": registry_path,
        }
        by_path.setdefault(Path(source_path).as_posix(), []).append(record)

    for lock_path in lock_paths:
        try:
            document = read_json(lock_path)
        except ValueError as exc:
            errors.append(str(exc))
            continue
        if not isinstance(document, dict):
            errors.append(f"trusted provenance {lock_path} must contain a JSON object")
            continue
        top_witness = document.get("witness_id")
        top_availability = document.get("availability")
        top_identity = document.get("source_identity")
        top_registry = document.get("registry_path")

        for descriptor in document.get("files", []):
            add_record(
                descriptor,
                witness_id=descriptor.get("witness_id", top_witness) if isinstance(descriptor, dict) else top_witness,
                availability=descriptor.get("availability", top_availability) if isinstance(descriptor, dict) else top_availability,
                lock_path=lock_path,
                source_identity=descriptor.get("source_identity", top_identity) if isinstance(descriptor, dict) else top_identity,
                registry_path=descriptor.get("registry_path", top_registry) if isinstance(descriptor, dict) else top_registry,
            )

        for record in document.get("records", []):
            if not isinstance(record, dict):
                continue
            record_witness = record.get("witness_id", top_witness)
            record_availability = record.get("availability", top_availability)
            record_identity = record.get("source_identity")
            if not isinstance(record_identity, dict):
                record_identity = {
                    key: record[key]
                    for key in (
                        "source_url",
                        "retrieval_url",
                        "api_url",
                        "api_endpoint",
                        "revision_id",
                        "revision_timestamp",
                        "page_id",
                        "identifier",
                    )
                    if key in record
                }
            if not record_identity:
                record_identity = top_identity
            record_registry = record.get("registry_path", top_registry)
            direct_path = record.get("path")
            direct_sha256 = record.get("sha256")
            if isinstance(direct_path, str) and isinstance(direct_sha256, str):
                add_record(
                    {"path": direct_path, "sha256": direct_sha256},
                    witness_id=record_witness,
                    availability=record_availability,
                    lock_path=lock_path,
                    source_identity=record_identity,
                    registry_path=record_registry,
                )
            text_path = record.get("text_path")
            text_sha256 = record.get("text_sha256")
            if isinstance(text_path, str) and isinstance(text_sha256, str):
                add_record(
                    {"path": text_path, "sha256": text_sha256},
                    witness_id=record_witness,
                    availability=record_availability,
                    lock_path=lock_path,
                    source_identity=record_identity,
                    registry_path=record_registry,
                )
            for descriptor in record.get("files", []):
                add_record(
                    descriptor,
                    witness_id=descriptor.get("witness_id", record_witness) if isinstance(descriptor, dict) else record_witness,
                    availability=descriptor.get("availability", record_availability) if isinstance(descriptor, dict) else record_availability,
                    lock_path=lock_path,
                    source_identity=descriptor.get("source_identity", record_identity) if isinstance(descriptor, dict) else record_identity,
                    registry_path=descriptor.get("registry_path", record_registry) if isinstance(descriptor, dict) else record_registry,
                )

    return by_path


def validate_source_provenance(
    root: Path,
    provenance: dict[str, Any],
    *,
    label: str,
    mode: str = "full",
    trusted_records: dict[str, list[dict[str, Any]]] | None = None,
) -> list[str]:
    """Validate an upstream source locator in strict or clean-checkout mode."""
    errors: list[str] = []
    if mode not in PROVENANCE_MODES:
        return [f"{label}: unsupported provenance validation mode: {mode!r}"]
    source_path_value = provenance.get("source_path")
    source_path = resolve_relative_path(root, source_path_value, f"{label} source_path", errors)
    source_sha256 = provenance.get("source_sha256")
    if not isinstance(source_sha256, str) or not source_sha256:
        errors.append(f"{label} source_sha256 must be a non-empty string")
    witness_id = provenance.get("witness_id")
    if not isinstance(witness_id, str) or not witness_id:
        errors.append(f"{label} witness_id must be a non-empty string")
    if source_path is None or not isinstance(source_path_value, str):
        return errors

    if source_path.is_file():
        actual_source_hash = sha256_file(source_path)
        if source_sha256 != actual_source_hash:
            errors.append(
                f"{label} source_sha256 does not match {source_path_value!r}: "
                f"{source_sha256!r} != {actual_source_hash!r}"
            )
        return errors

    if mode == "full":
        errors.append(f"{label} source_path: file does not exist: {source_path_value!r}")
        return errors

    trusted_records = trusted_records if trusted_records is not None else _trusted_source_records(root, errors)
    candidates = trusted_records.get(Path(source_path_value).as_posix(), [])
    if not candidates:
        errors.append(
            f"{label} source_path is missing and has no committed trusted provenance record: "
            f"{source_path_value!r}"
        )
        return errors

    matching = [
        record
        for record in candidates
        if record.get("witness_id") == witness_id and record.get("source_sha256") == source_sha256
    ]
    if not matching:
        expected = "; ".join(
            f"witness_id={record.get('witness_id')!r}, source_sha256={record.get('source_sha256')!r}"
            for record in candidates
        )
        if not any(record.get("witness_id") == witness_id for record in candidates):
            errors.append(
                f"{label} missing source witness_id does not match committed trusted metadata: "
                f"{witness_id!r} (trusted: {expected})"
            )
        elif not any(record.get("source_sha256") == source_sha256 for record in candidates):
            errors.append(
                f"{label} missing source_sha256 does not match committed trusted metadata: "
                f"{source_sha256!r} (trusted: {expected})"
            )
        else:
            errors.append(f"{label} missing source provenance does not match committed trusted metadata")
        return errors

    if not any(record.get("availability") in PORTABLE_SOURCE_AVAILABILITIES for record in matching):
        locations = ", ".join(str(record.get("lock_path")) for record in matching)
        errors.append(
            f"{label} missing source is not explicitly registered as an ignored/external payload "
            f"in committed metadata: {locations}"
        )

    if not any(
        isinstance(record.get("source_identity"), dict) and record.get("source_identity")
        for record in matching
    ):
        errors.append(
            f"{label} committed trusted metadata has no source/revision identity for "
            f"{source_path_value!r}"
        )

    for record in matching:
        registry_path = record.get("registry_path")
        if registry_path is not None:
            registry_file = resolve_relative_path(root, registry_path, f"{label} registry_path", errors)
            if registry_file is not None and not registry_file.is_file():
                errors.append(f"{label} registry_path does not exist: {registry_path!r}")

    return errors


def load_index(
    root: Path,
    relative_path: str,
    collection_key: str,
    id_key: str,
    errors: list[str],
) -> dict[str, dict[str, Any]]:
    path = root / relative_path
    try:
        document = read_json(path)
    except ValueError as exc:
        errors.append(str(exc))
        return {}
    records = document.get(collection_key) if isinstance(document, dict) else None
    if not isinstance(records, list):
        errors.append(f"{path} must contain a {collection_key} array")
        return {}
    indexed: dict[str, dict[str, Any]] = {}
    for record in records:
        if not isinstance(record, dict) or not isinstance(record.get(id_key), str):
            errors.append(f"{path}.{collection_key} contains a record without {id_key}")
            continue
        record_id = record[id_key]
        if record_id in indexed:
            errors.append(f"{path}: duplicate {id_key}: {record_id!r}")
        indexed[record_id] = record
    return indexed


def path_text(path: Any) -> str:
    if not path:
        return "$"
    return "$" + "".join(f"[{item}]" if isinstance(item, int) else f".{item}" for item in path)


def record_list(document: Any, path: Path) -> list[dict[str, Any]]:
    if not isinstance(document, dict) or not isinstance(document.get("records"), list):
        raise ValueError(f"{path} must be an object with a records array")
    records = document["records"]
    if not all(isinstance(record, dict) for record in records):
        raise ValueError(f"{path}.records must contain JSON objects")
    return records


def validate_schema(schema_path: Path, records: list[dict[str, Any]], label: str) -> list[str]:
    errors: list[str] = []
    try:
        schema = read_json(schema_path)
        Draft202012Validator.check_schema(schema)
        validator = Draft202012Validator(schema)
    except Exception as exc:
        return [f"{label}: invalid JSON Schema {schema_path}: {exc}"]
    for index, record in enumerate(records):
        for error in sorted(validator.iter_errors(record), key=lambda item: list(item.path)):
            errors.append(f"{label} record {index} {path_text(error.path)}: {error.message}")
    return errors


def add_ref_error(errors: list[str], label: str, ref: Any, collection: dict[str, dict[str, Any]]) -> None:
    if not isinstance(ref, str) or ref not in collection:
        errors.append(f"{label}: referenced ID does not exist: {ref!r}")


def validate_canonical_provenance(
    root: Path,
    records_by_kind: dict[str, list[dict[str, Any]]],
    sources: dict[str, dict[str, Any]],
    mode: str = "full",
) -> list[str]:
    """Validate artifact/source provenance against the canonical indexes and files."""
    errors: list[str] = []
    trusted_records = _trusted_source_records(root, errors) if mode == "portable" else None
    shishuo_entries = load_index(
        root,
        "data/shishuo-corpus-index.json",
        "entries",
        "id",
        errors,
    )
    jinshu_units = load_index(
        root,
        "data/jinshu-unit-index.json",
        "units",
        "unit_id",
        errors,
    )

    legacy_jinshu_mentions_path = root / "data/mentions/jinshu.json"
    if legacy_jinshu_mentions_path.is_file():
        try:
            legacy_document = read_json(legacy_jinshu_mentions_path)
            legacy_mentions = legacy_document.get("mentions", []) if isinstance(legacy_document, dict) else []
            if not isinstance(legacy_mentions, list):
                errors.append(f"{legacy_jinshu_mentions_path} must contain a mentions array")
            else:
                for index, mention in enumerate(legacy_mentions):
                    unit_id = mention.get("unit_id") if isinstance(mention, dict) else None
                    if not isinstance(unit_id, str) or unit_id not in jinshu_units:
                        errors.append(
                            f"Jinshu mention record {index} references a nonexistent unit_id: {unit_id!r}"
                        )
        except ValueError as exc:
            errors.append(str(exc))

    for story in records_by_kind["stories"]:
        entry_id = story.get("source_entry_id")
        if not isinstance(entry_id, str) or entry_id not in shishuo_entries:
            errors.append(
                f"Story {story.get('id')} source_entry_id does not exist in the canonical Shishuo index: {entry_id!r}"
            )

    for evidence in records_by_kind["evidence"]:
        evidence_id = evidence.get("id")
        locator = evidence.get("locator")
        if not isinstance(locator, dict):
            continue
        artifact_type = locator.get("artifact_type")
        if artifact_type == "shishuo_entry":
            reference_id = locator.get("entry_id")
            index_record = shishuo_entries.get(reference_id)
            index_path_key = "path"
            index_hash_key = "entry_sha256"
            metadata_id_key = "entry_id"
        elif artifact_type == "jinshu_unit":
            reference_id = locator.get("unit_id")
            index_record = jinshu_units.get(reference_id)
            index_path_key = "file_path"
            index_hash_key = None
            metadata_id_key = "unit_id"
        else:
            errors.append(f"Evidence {evidence_id} has unknown artifact_type: {artifact_type!r}")
            continue

        if not isinstance(reference_id, str) or index_record is None:
            collection_name = "Shishuo entry" if artifact_type == "shishuo_entry" else "Jinshu unit"
            errors.append(
                f"Evidence {evidence_id} references a nonexistent {collection_name}: {reference_id!r}"
            )
            continue

        artifact_path_value = locator.get("artifact_path")
        artifact_path = resolve_relative_file(
            root,
            artifact_path_value,
            f"Evidence {evidence_id} artifact_path",
            errors,
        )
        expected_path = index_record.get(index_path_key)
        if isinstance(artifact_path_value, str) and isinstance(expected_path, str):
            if Path(artifact_path_value).as_posix() != Path(expected_path).as_posix():
                errors.append(
                    f"Evidence {evidence_id} artifact_path does not match {artifact_type} index: "
                    f"{artifact_path_value!r} != {expected_path!r}"
                )
        if artifact_path is None:
            continue

        actual_artifact_hash = sha256_file(artifact_path)
        recorded_artifact_hash = locator.get("artifact_sha256")
        if recorded_artifact_hash != actual_artifact_hash:
            errors.append(
                f"Evidence {evidence_id} artifact_sha256 does not match {artifact_path_value!r}: "
                f"{recorded_artifact_hash!r} != {actual_artifact_hash!r}"
            )
        if index_hash_key and index_record.get(index_hash_key) != actual_artifact_hash:
            errors.append(
                f"Evidence {evidence_id} artifact hash disagrees with the Shishuo index for {reference_id!r}"
            )

        try:
            artifact_text = artifact_path.read_text(encoding="utf-8")
            metadata = frontmatter_fields(artifact_path)
        except (OSError, UnicodeError, ValueError) as exc:
            errors.append(f"Evidence {evidence_id} artifact metadata cannot be read: {exc}")
            continue
        if metadata.get(metadata_id_key) != reference_id:
            errors.append(
                f"Evidence {evidence_id} {metadata_id_key} disagrees with artifact metadata: "
                f"{reference_id!r} != {metadata.get(metadata_id_key)!r}"
            )
        quote = evidence.get("quote")
        if not isinstance(quote, str) or quote not in artifact_text:
            errors.append(f"Evidence {evidence_id} quote is not present in {artifact_path_value!r}")
        if locator.get("chapter_id") is not None and locator.get("chapter_id") != metadata.get("chapter_id"):
            errors.append(f"Evidence {evidence_id} chapter_id disagrees with artifact metadata")
        if (
            locator.get("source_normalized_filename") is not None
            and locator.get("source_normalized_filename") != metadata.get("source_normalized_filename")
        ):
            errors.append(f"Evidence {evidence_id} source_normalized_filename disagrees with artifact metadata")

        source = sources.get(evidence.get("source_id"))
        provenance = locator.get("source_provenance")
        if not isinstance(provenance, dict):
            continue
        if source is not None and provenance.get("witness_id") != source.get("witness_id"):
            errors.append(
                f"Evidence {evidence_id} source provenance witness does not match source record: "
                f"{provenance.get('witness_id')!r} != {source.get('witness_id')!r}"
            )
        errors.extend(
            validate_source_provenance(
                root,
                provenance,
                label=f"Evidence {evidence_id} source_provenance",
                mode=mode,
                trusted_records=trusted_records,
            )
        )
        source_path_value = provenance.get("source_path")
        if metadata.get("source_path") != source_path_value:
            errors.append(
                f"Evidence {evidence_id} source provenance path disagrees with artifact metadata: "
                f"{source_path_value!r} != {metadata.get('source_path')!r}"
            )
        if metadata.get("source_sha256") != provenance.get("source_sha256"):
            errors.append(f"Evidence {evidence_id} source provenance hash disagrees with artifact metadata")
        if artifact_type == "jinshu_unit" and metadata.get("source_witness") != provenance.get("witness_id"):
            errors.append(f"Evidence {evidence_id} Jinshu source witness disagrees with artifact metadata")

    return errors


def validate_punctuation_reference(
    root: Path,
    reference: dict[str, Any],
    *,
    label: str,
    mode: str,
    trusted_records: dict[str, list[dict[str, Any]]] | None,
) -> list[str]:
    """Validate a punctuation reference, including ignored payloads in portable mode."""
    errors: list[str] = []
    path_value = reference.get("path")
    path = resolve_relative_path(root, path_value, f"{label} path", errors)
    witness_id = reference.get("witness_id")
    sha256 = reference.get("sha256")
    if not isinstance(witness_id, str) or not witness_id:
        errors.append(f"{label} witness_id must be a non-empty string")
    if not isinstance(sha256, str) or not sha256:
        errors.append(f"{label} sha256 must be a non-empty string")
    if path is None or not isinstance(path_value, str):
        return errors

    if path.is_file():
        actual = sha256_file(path)
        if sha256 != actual:
            errors.append(
                f"{label} sha256 does not match {path_value!r}: {sha256!r} != {actual!r}"
            )
        return errors

    if mode == "full":
        errors.append(f"{label} path: file does not exist: {path_value!r}")
        return errors

    trusted_records = trusted_records if trusted_records is not None else _trusted_source_records(root, errors)
    candidates = trusted_records.get(Path(path_value).as_posix(), [])
    matches = [
        record
        for record in candidates
        if record.get("witness_id") == witness_id and record.get("source_sha256") == sha256
    ]
    if not matches:
        errors.append(
            f"{label} missing path has no matching committed witness/hash record: "
            f"witness_id={witness_id!r}, sha256={sha256!r}"
        )
        return errors
    if not any(
        isinstance(record.get("source_identity"), dict) and record.get("source_identity")
        for record in matches
    ):
        errors.append(f"{label} committed record has no source/revision identity")
    return errors


def validate_punctuation(root: Path, mode: str = "full") -> list[str]:
    """Validate the reviewed reading layer without treating it as source text."""
    errors: list[str] = []
    path = root / PUNCTUATION_DATA
    try:
        document = read_json(path)
        records = record_list(document, path)
    except ValueError as exc:
        return [str(exc)]

    errors.extend(validate_schema(root / PUNCTUATION_SCHEMA, [document], "Punctuation document"))
    ids = [record.get("id") for record in records]
    if len(ids) != len(set(ids)):
        errors.append("Punctuation: duplicate IDs within records")
    entry_ids = [record.get("entry_id") for record in records]
    if len(entry_ids) != len(set(entry_ids)):
        errors.append("Punctuation: duplicate entry_id values within records")

    shishuo_entries = load_index(root, "data/shishuo-corpus-index.json", "entries", "id", errors)
    trusted_records = _trusted_source_records(root, errors) if mode == "portable" else None
    for index, record in enumerate(records):
        label = f"Punctuation record {index}"
        entry_id = record.get("entry_id")
        index_record = shishuo_entries.get(entry_id)
        if index_record is None:
            errors.append(f"{label} references a nonexistent Shishuo entry: {entry_id!r}")

        base_path_value = record.get("base_canonical_entry_path")
        base_path = resolve_relative_file(root, base_path_value, f"{label} base_canonical_entry_path", errors)
        if base_path is None:
            continue
        actual_hash = sha256_file(base_path)
        if record.get("base_canonical_entry_sha256") != actual_hash:
            errors.append(
                f"{label} base_canonical_entry_sha256 does not match {base_path_value!r}: "
                f"{record.get('base_canonical_entry_sha256')!r} != {actual_hash!r}"
            )
        if index_record is not None:
            expected_path = index_record.get("path")
            if Path(base_path_value).as_posix() != Path(expected_path).as_posix():
                errors.append(f"{label} canonical path does not match the Shishuo index")
            if index_record.get("entry_sha256") != actual_hash:
                errors.append(f"{label} canonical hash disagrees with the Shishuo index")
        try:
            metadata = frontmatter_fields(base_path)
            canonical = canonical_sections(base_path)
        except (OSError, UnicodeError, ValueError) as exc:
            errors.append(f"{label} canonical entry cannot be parsed: {exc}")
            continue
        if metadata.get("entry_id") != entry_id:
            errors.append(f"{label} entry_id disagrees with canonical entry metadata")
        errors.extend(validate_punctuation_round_trip(record, canonical))

        references = record.get("references", [])
        if isinstance(references, list):
            canonical_reference_count = 0
            for reference_index, reference in enumerate(references):
                if not isinstance(reference, dict):
                    continue
                reference_label = f"{label} reference {reference_index}"
                errors.extend(
                    validate_punctuation_reference(
                        root,
                        reference,
                        label=reference_label,
                        mode=mode,
                        trusted_records=trusted_records,
                    )
                )
                if reference.get("kind") == "canonical_entry":
                    canonical_reference_count += 1
                    if reference.get("path") != base_path_value:
                        errors.append(f"{reference_label} path does not match the base canonical path")
                    if reference.get("sha256") != record.get("base_canonical_entry_sha256"):
                        errors.append(f"{reference_label} hash does not match the base canonical hash")
            if canonical_reference_count == 0:
                errors.append(f"{label} has no canonical_entry reference")

    return errors


def validate_references(
    records_by_kind: dict[str, list[dict[str, Any]]],
    root: Path | None = None,
    mode: str = "full",
) -> list[str]:
    errors: list[str] = []
    by_kind = {
        kind: {record["id"]: record for record in records}
        for kind, records in records_by_kind.items()
    }
    global_ids: dict[str, str] = {}
    for kind, records in records_by_kind.items():
        for record in records:
            record_id = record.get("id")
            if record_id in global_ids:
                errors.append(f"duplicate ID {record_id!r}: {global_ids[record_id]} and {kind}")
            else:
                global_ids[record_id] = kind

    sources = by_kind["sources"]
    stories = by_kind["stories"]
    people = by_kind["people"]
    mentions = by_kind["mentions"]
    relations = by_kind["relations"]
    eras = by_kind["eras"]
    evidence = by_kind["evidence"]

    def refs(label: str, values: Any, collection: dict[str, dict[str, Any]]) -> None:
        if isinstance(values, list):
            for value in values:
                add_ref_error(errors, label, value, collection)

    for kind in ("stories", "people", "mentions", "relations", "eras"):
        for record in records_by_kind[kind]:
            if record.get("assertion_status") != "attested":
                continue
            evidence_ids = record.get("evidence_ids")
            if not isinstance(evidence_ids, list) or not evidence_ids:
                errors.append(
                    f"{kind.title()} {record.get('id')} is attested but has no evidence_ids"
                )
    for story in stories.values():
        for index, place in enumerate(story.get("places", [])):
            if place.get("assertion_status") == "attested" and not place.get("evidence_ids"):
                errors.append(
                    f"Story {story.get('id')} place {index} is attested but has no evidence_ids"
                )

    for story in stories.values():
        refs(f"Story {story.get('id')} source_ids", story.get("source_ids"), sources)
        refs(f"Story {story.get('id')} evidence_ids", story.get("evidence_ids"), evidence)
        refs(f"Story {story.get('id')} person_ids", story.get("person_ids"), people)
        refs(f"Story {story.get('id')} mention_ids", story.get("mention_ids"), mentions)
        refs(f"Story {story.get('id')} relation_ids", story.get("relation_ids"), relations)
        refs(f"Story {story.get('id')} era_ids", story.get("era_ids"), eras)
        for mention_id in story.get("mention_ids", []):
            mention = mentions.get(mention_id)
            if mention and mention.get("story_id") != story.get("id"):
                errors.append(f"Story {story['id']} includes Mention {mention_id} with a different story_id")
        for relation_id in story.get("relation_ids", []):
            relation = relations.get(relation_id)
            if relation and story.get("id") not in relation.get("story_ids", []):
                errors.append(f"Story {story['id']} includes Relation {relation_id} without reciprocal story reference")
        for era_id in story.get("era_ids", []):
            era = eras.get(era_id)
            if era and story.get("id") not in era.get("story_ids", []):
                errors.append(f"Story {story['id']} includes Era {era_id} without reciprocal story reference")

    for person in people.values():
        refs(f"Person {person.get('id')} story_ids", person.get("story_ids"), stories)
        refs(f"Person {person.get('id')} evidence_ids", person.get("evidence_ids"), evidence)
        for alias in person.get("aliases", []):
            refs(f"Person {person.get('id')} alias {alias.get('surface')} evidence_ids", alias.get("evidence_ids"), evidence)

    for mention in mentions.values():
        add_ref_error(errors, f"Mention {mention.get('id')} story_id", mention.get("story_id"), stories)
        if mention.get("person_id") is not None:
            add_ref_error(errors, f"Mention {mention.get('id')} person_id", mention.get("person_id"), people)
        refs(f"Mention {mention.get('id')} candidate_person_ids", mention.get("candidate_person_ids"), people)
        refs(f"Mention {mention.get('id')} evidence_ids", mention.get("evidence_ids"), evidence)
        if mention.get("anchor", {}).get("section") != mention.get("section"):
            errors.append(f"Mention {mention.get('id')} anchor section does not match section")

    for relation in relations.values():
        add_ref_error(errors, f"Relation {relation.get('id')} subject_id", relation.get("subject_id"), people)
        add_ref_error(errors, f"Relation {relation.get('id')} object_id", relation.get("object_id"), people)
        refs(f"Relation {relation.get('id')} story_ids", relation.get("story_ids"), stories)
        refs(f"Relation {relation.get('id')} evidence_ids", relation.get("evidence_ids"), evidence)

    for era in eras.values():
        refs(f"Era {era.get('id')} story_ids", era.get("story_ids"), stories)
        refs(f"Era {era.get('id')} person_ids", era.get("person_ids"), people)
        refs(f"Era {era.get('id')} evidence_ids", era.get("evidence_ids"), evidence)

    for item in evidence.values():
        add_ref_error(errors, f"Evidence {item.get('id')} source_id", item.get("source_id"), sources)

    if root is not None:
        errors.extend(validate_canonical_provenance(root, records_by_kind, sources, mode=mode))

    return errors


def validate_manifest(root: Path, records_by_kind: dict[str, list[dict[str, Any]]]) -> list[str]:
    errors: list[str] = []
    path = root / "data/manifest/milestone-1.json"
    try:
        manifest = read_json(path)
    except ValueError as exc:
        return [str(exc)]
    people = {record["id"] for record in records_by_kind["people"]}
    stories = {record["id"] for record in records_by_kind["stories"]}
    eras = {record["id"] for record in records_by_kind["eras"]}
    scope = manifest.get("scope", {})
    people_scope = scope.get("people", {})
    if people_scope.get("target_count") != 6:
        errors.append("manifest scope.people.target_count must be 6")
    for person_id in people_scope.get("ids", []):
        add_ref_error(errors, "manifest scope.people.ids", person_id, {item: {} for item in people})
    stories_scope = scope.get("stories", {})
    for story_id in stories_scope.get("validated_ids", []):
        add_ref_error(errors, "manifest scope.stories.validated_ids", story_id, {item: {} for item in stories})
    eras_scope = scope.get("eras", {})
    for era_id in eras_scope.get("candidate_ids", []) + eras_scope.get("validated_ids", []):
        add_ref_error(errors, "manifest scope.eras IDs", era_id, {item: {} for item in eras})
    sample = manifest.get("sample", {})
    add_ref_error(errors, "manifest sample.story_id", sample.get("story_id"), {item: {} for item in stories})
    add_ref_error(errors, "manifest sample.era_id", sample.get("era_id"), {item: {} for item in eras})
    add_ref_error(errors, "manifest sample.relation_id", sample.get("relation_id"), {item: {} for item in {r["id"] for r in records_by_kind["relations"]}})
    return errors


def validate_bundle(root: Path, records_by_kind: dict[str, list[dict[str, Any]]]) -> list[str]:
    errors: list[str] = []
    path = root / "data/derived/wp1-site.json"
    try:
        bundle = read_json(path)
    except ValueError as exc:
        return [str(exc)]
    for kind in records_by_kind:
        records = bundle.get(kind)
        if not isinstance(records, list):
            errors.append(f"derived bundle missing array: {kind}")
            continue
        expected = {record["id"] for record in records_by_kind[kind]}
        actual = {record.get("id") for record in records}
        if expected != actual:
            errors.append(f"derived bundle {kind} IDs do not match annotation records")

    try:
        punctuation_records = record_list(
            read_json(root / PUNCTUATION_DATA), root / PUNCTUATION_DATA
        )
    except ValueError:
        punctuation_records = []
    punctuation_by_entry = {
        record.get("entry_id"): record
        for record in punctuation_records
        if isinstance(record.get("entry_id"), str)
    }
    for story in bundle.get("stories", []):
        if not isinstance(story, dict):
            continue
        punctuation = punctuation_by_entry.get(story.get("id"))
        if punctuation is None:
            continue
        reading = story.get("reading")
        label = f"derived bundle story {story.get('id')} reading"
        if not isinstance(reading, dict):
            errors.append(f"{label} is missing")
            continue
        if reading.get("entry_id") != story.get("id"):
            errors.append(f"{label}.entry_id does not match the story")
        if reading.get("punctuation_record_id") != punctuation.get("id"):
            errors.append(f"{label}.punctuation_record_id does not match the punctuation record")
        if reading.get("base_canonical_entry_sha256") != punctuation.get("base_canonical_entry_sha256"):
            errors.append(f"{label}.base_canonical_entry_sha256 does not match the punctuation record")
        conversion = reading.get("conversion")
        if not isinstance(conversion, dict) or not conversion.get("library") or not conversion.get("config"):
            errors.append(f"{label}.conversion is incomplete")
        main_reading = reading.get("main_text")
        punctuation_sections = punctuation.get("sections")
        punctuation_sections = punctuation_sections if isinstance(punctuation_sections, dict) else {}
        main_punctuation = punctuation_sections.get("main_text", {})
        if not isinstance(main_reading, dict) or not isinstance(main_punctuation, dict):
            errors.append(f"{label}.main_text is incomplete")
        else:
            if main_reading.get("original") != main_punctuation.get("punctuated_text"):
                errors.append(f"{label}.main_text.original does not match reviewed punctuation")
            if not isinstance(main_reading.get("simplified"), str) or not main_reading.get("simplified"):
                errors.append(f"{label}.main_text.simplified is empty")
        annotation_readings = reading.get("annotations")
        annotation_punctuation = punctuation_sections.get("liu_annotation", {})
        if not isinstance(annotation_readings, list) or len(annotation_readings) != 1:
            errors.append(f"{label}.annotations must contain the reviewed Liu annotation")
        elif isinstance(annotation_punctuation, dict):
            annotation_reading = annotation_readings[0]
            if annotation_reading.get("original") != annotation_punctuation.get("punctuated_text"):
                errors.append(f"{label}.annotations[0].original does not match reviewed punctuation")
            if not isinstance(annotation_reading.get("simplified"), str) or not annotation_reading.get("simplified"):
                errors.append(f"{label}.annotations[0].simplified is empty")
    public_path = root / "site/public/data/wp1-site.json"
    try:
        public_bundle = read_json(public_path)
        if public_bundle != bundle:
            errors.append("site/public/data/wp1-site.json differs from data/derived/wp1-site.json")
    except ValueError as exc:
        errors.append(str(exc))
    return errors


def validate_repository(root: Path, mode: str = "full") -> list[str]:
    errors: list[str] = []
    errors.extend(validate_punctuation(root, mode=mode))
    records_by_kind: dict[str, list[dict[str, Any]]] = {}
    for label, (schema_rel, data_rel, kind) in OBJECTS.items():
        schema_path = root / schema_rel
        data_path = root / data_rel
        try:
            records = record_list(read_json(data_path), data_path)
        except ValueError as exc:
            errors.append(f"{label}: {exc}")
            continue
        records_by_kind[kind] = records
        errors.extend(validate_schema(schema_path, records, label))
        ids = [record.get("id") for record in records]
        if len(ids) != len(set(ids)):
            errors.append(f"{label}: duplicate IDs within records")
    if len(records_by_kind) == len(OBJECTS):
        errors.extend(validate_references(records_by_kind, root=root, mode=mode))
        errors.extend(validate_manifest(root, records_by_kind))
        errors.extend(validate_bundle(root, records_by_kind))
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument(
        "--mode",
        choices=PROVENANCE_MODES,
        default="full",
        help="full requires source payloads locally; portable verifies missing ignored payloads against committed locks",
    )
    args = parser.parse_args()
    errors = validate_repository(args.root, mode=args.mode)
    if errors:
        print("WP1 validation failed:")
        for error in errors:
            print(f"- {error}")
        return 1
    print(
        "WP1 validation passed: schemas, IDs, references, evidence, manifest, and static bundle "
        f"(provenance mode: {args.mode})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
