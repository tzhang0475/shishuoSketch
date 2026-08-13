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
    from .reading_layers import (
        READER_LABELS,
        canonical_reading_sections,
        canonical_sections,
        validate_punctuation_round_trip,
    )
except ImportError:  # pragma: no cover - direct script execution
    from reading_layers import (
        READER_LABELS,
        canonical_reading_sections,
        canonical_sections,
        validate_punctuation_round_trip,
    )


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
    except (OSError, ValueError) as exc:
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


def load_unified_person_registry(root: Path, errors: list[str]) -> dict[str, dict[str, Any]]:
    path = root / "data/people.json"
    try:
        document = read_json(path)
    except (OSError, ValueError) as exc:
        errors.append(str(exc))
        return {}
    records = document.get("people") if isinstance(document, dict) else None
    if not isinstance(records, list):
        errors.append(f"{path} must contain a people array")
        return {}
    indexed: dict[str, dict[str, Any]] = {}
    for index, record in enumerate(records):
        if not isinstance(record, dict) or not isinstance(record.get("person_id"), str):
            errors.append(f"{path}.people[{index}] must contain a person_id")
            continue
        person_id = record["person_id"]
        if person_id in indexed:
            errors.append(f"{path}: duplicate person_id: {person_id!r}")
        indexed[person_id] = record
    return indexed


def validate_person_registry(
    records_by_kind: dict[str, list[dict[str, Any]]],
    root: Path,
    unified_people: dict[str, dict[str, Any]],
) -> list[str]:
    """Ensure WP1 Person projections are derived from the unified registry."""
    errors: list[str] = []
    projected_people = {record.get("id"): record for record in records_by_kind.get("people", [])}
    if set(projected_people) != set(unified_people):
        errors.append(
            "WP1 Person projection IDs do not match the unified data/people.json registry"
        )

    mention_index: dict[str, dict[str, Any]] = {}
    for relative_path in ("data/mentions/shishuo.json", "data/mentions/jinshu.json"):
        try:
            document = read_json(root / relative_path)
        except ValueError as exc:
            errors.append(str(exc))
            continue
        key = "mentions"
        for mention in document.get(key, []) if isinstance(document, dict) else []:
            if isinstance(mention, dict) and isinstance(mention.get("mention_id"), str):
                mention_index[mention["mention_id"]] = mention

    for person_id, registry_person in unified_people.items():
        scope_role = registry_person.get("scope_role")
        if scope_role not in {"primary", "supporting"}:
            errors.append(
                f"Unified Person {person_id} must declare scope_role primary or supporting"
            )
        projected = projected_people.get(person_id)
        if projected is None:
            continue
        if projected.get("canonical_name") != registry_person.get("canonical_name"):
            errors.append(f"Person {person_id} canonical_name disagrees with unified registry")
        if projected.get("scope_role") != scope_role or projected.get("scope") != scope_role:
            errors.append(f"Person {person_id} scope projection disagrees with unified registry")

        if scope_role != "supporting":
            continue
        source_evidence = registry_person.get("source_evidence")
        if not isinstance(source_evidence, list) or not source_evidence:
            errors.append(f"Supporting Person {person_id} must have source_evidence")
            continue
        for evidence_index, item in enumerate(source_evidence):
            label = f"Unified Person {person_id} source_evidence[{evidence_index}]"
            if not isinstance(item, dict):
                errors.append(f"{label} must be an object")
                continue
            mention_id = item.get("mention_id")
            mention = mention_index.get(mention_id)
            if mention is None:
                errors.append(f"{label} references a nonexistent mention_id: {mention_id!r}")
                continue
            provenance = item.get("provenance")
            mention_provenance = mention.get("evidence", {}).get("provenance", {})
            if not isinstance(provenance, dict):
                errors.append(f"{label} must contain provenance")
                continue
            for key in ("source_path", "source_sha256"):
                if provenance.get(key) != mention_provenance.get(key):
                    errors.append(f"{label} {key} disagrees with the cited mention provenance")
            if item.get("source_id") != mention.get("source_id"):
                errors.append(f"{label} source_id disagrees with the cited mention")

    return errors


R1_ROLE_PAIRS = {
    ("kinship", "parent_child"): {
        ("父", "子"),
        ("父", "女"),
        ("母", "子"),
        ("母", "女"),
    },
    ("kinship", "uncle_niece"): {
        ("叔父", "姪女"),
        ("伯父", "姪女"),
        ("舅父", "姪女"),
    },
    ("kinship", "collateral_kinship"): {
        ("從伯", "從子"),
        ("從父", "從子"),
        ("從父", "從女"),
        ("從母", "從子"),
        ("從母", "從女"),
    },
    ("marriage", "spouse"): {( "配偶", "配偶")},
}


def validate_relation_records(
    records_by_kind: dict[str, list[dict[str, Any]]],
    *,
    root: Path | None = None,
    unified_people: dict[str, dict[str, Any]] | None = None,
) -> list[str]:
    """Validate the small reviewed R1 relation model beyond JSON Schema."""
    errors: list[str] = []
    people = {record.get("id"): record for record in records_by_kind.get("people", [])}
    stories = {record.get("id"): record for record in records_by_kind.get("stories", [])}
    evidence = {record.get("id"): record for record in records_by_kind.get("evidence", [])}
    relations = {record.get("id"): record for record in records_by_kind.get("relations", [])}
    shishuo_entries: dict[str, dict[str, Any]] = {}
    jinshu_units: dict[str, dict[str, Any]] = {}
    if root is not None:
        shishuo_entries = load_index(
            root, "data/shishuo-corpus-index.json", "entries", "id", errors
        )
        jinshu_units = load_index(
            root, "data/jinshu-unit-index.json", "units", "unit_id", errors
        )

    for person in people.values():
        if person.get("scope") == "supporting":
            evidence_ids = person.get("evidence_ids")
            if person.get("assertion_status") != "attested" or not isinstance(evidence_ids, list) or not evidence_ids:
                errors.append(
                    f"Supporting Person {person.get('id')} must be attested with non-empty evidence_ids"
                )

    seen_semantic_edges: dict[tuple[Any, ...], str] = {}
    for relation in records_by_kind.get("relations", []):
        relation_id = relation.get("id")
        subject_id = relation.get("subject_id")
        object_id = relation.get("object_id")
        relation_type = relation.get("relation_type")
        subtype = relation.get("relation_subtype")
        reviewed = relation.get("review_status") == "reviewed"

        if isinstance(subject_id, str) and subject_id == object_id:
            errors.append(f"Relation {relation_id} must not connect a person to themself")
        if unified_people is not None:
            if subject_id not in unified_people:
                errors.append(f"Relation {relation_id} subject_id is absent from unified Person registry: {subject_id!r}")
            if object_id not in unified_people:
                errors.append(f"Relation {relation_id} object_id is absent from unified Person registry: {object_id!r}")

        if reviewed and isinstance(subtype, str) and isinstance(subject_id, str) and isinstance(object_id, str):
            endpoint_key = (
                tuple(sorted((subject_id, object_id)))
                if subtype == "spouse"
                else (subject_id, object_id)
            )
            semantic_key = (relation_type, subtype, endpoint_key)
            previous = seen_semantic_edges.get(semantic_key)
            if previous is not None:
                errors.append(
                    f"Reviewed Relations {previous} and {relation_id} duplicate the same semantic edge"
                )
            else:
                seen_semantic_edges[semantic_key] = str(relation_id)

        for field, collection, label in (
            ("source_entry_ids", shishuo_entries, "Shishuo entry"),
            ("source_unit_ids", jinshu_units, "Jinshu unit"),
        ):
            values = relation.get(field, [])
            if not isinstance(values, list):
                continue
            for value in values:
                if root is not None and value not in collection:
                    errors.append(
                        f"Relation {relation_id} {field} references a nonexistent {label}: {value!r}"
                    )

        basis = relation.get("relation_basis")
        derived_ids = relation.get("derived_from_relation_ids", [])
        if basis == "direct" and derived_ids:
            errors.append(f"Direct Relation {relation_id} cannot declare derived_from_relation_ids")
        elif basis == "derived":
            if not isinstance(derived_ids, list) or not derived_ids:
                errors.append(f"Derived Relation {relation_id} must have derived_from_relation_ids")
            for source_relation_id in derived_ids if isinstance(derived_ids, list) else []:
                source_relation = relations.get(source_relation_id)
                if source_relation is None:
                    errors.append(
                        f"Derived Relation {relation_id} references a nonexistent source Relation: {source_relation_id!r}"
                    )
                    continue
                if source_relation.get("review_status") != "reviewed":
                    errors.append(
                        f"Derived Relation {relation_id} source Relation {source_relation_id} is not reviewed"
                    )
                if source_relation.get("relation_basis") != "direct":
                    errors.append(
                        f"Derived Relation {relation_id} source Relation {source_relation_id} is not direct Gold data"
                    )
            if relation.get("evidence_ids"):
                errors.append(
                    f"Derived Relation {relation_id} must not carry direct evidence_ids; use derived_from_relation_ids"
                )
            if reviewed and relation.get("assertion_status") != "inferred":
                errors.append(f"Reviewed Derived Relation {relation_id} must have assertion_status='inferred'")
            continue
        elif basis not in {"direct", "derived"}:
            errors.append(f"Relation {relation_id} must declare relation_basis direct or derived")

        if not reviewed:
            continue

        if relation_type not in {"kinship", "marriage"}:
            errors.append(
                f"Reviewed Relation {relation_id} is outside the R1 hard-relation scope: {relation_type!r}"
            )
        if relation.get("assertion_status") != "attested":
            errors.append(f"Reviewed Relation {relation_id} must have assertion_status='attested'")

        evidence_ids = relation.get("evidence_ids")
        relation_evidence = [evidence.get(item) for item in evidence_ids or []]
        if not isinstance(evidence_ids, list) or not evidence_ids:
            errors.append(f"Reviewed Relation {relation_id} must have evidence_ids")
        elif not any(
            isinstance(item, dict) and item.get("evidence_type") in {"primary_text", "annotation"}
            for item in relation_evidence
        ):
            errors.append(
                f"Reviewed Relation {relation_id} must use direct primary-text or annotation evidence; co-occurrence alone is insufficient"
            )

        source_entry_ids = relation.get("source_entry_ids", [])
        source_unit_ids = relation.get("source_unit_ids", [])
        story_ids = relation.get("story_ids", [])
        if not (source_entry_ids or source_unit_ids or story_ids):
            errors.append(
                f"Reviewed Relation {relation_id} must identify at least one source entry, Jinshu unit, or story"
            )
        for story_id in story_ids if isinstance(story_ids, list) else []:
            if story_id not in stories:
                errors.append(f"Relation {relation_id} story_ids: referenced ID does not exist: {story_id!r}")

        if not isinstance(subtype, str) or not isinstance(relation.get("role_a"), str) or not isinstance(relation.get("role_b"), str):
            errors.append(f"Reviewed Relation {relation_id} must declare relation_subtype, role_a, and role_b")
        else:
            allowed_roles = R1_ROLE_PAIRS.get((relation_type, subtype))
            if allowed_roles is None or (relation.get("role_a"), relation.get("role_b")) not in allowed_roles:
                errors.append(
                    f"Relation {relation_id} has incompatible relation subtype/roles: "
                    f"{relation_type!r}/{subtype!r} {relation.get('role_a')!r}/{relation.get('role_b')!r}"
                )

            if subtype == "spouse":
                if not isinstance(subject_id, str) or not isinstance(object_id, str) or subject_id >= object_id:
                    errors.append(
                        f"Symmetric spouse Relation {relation_id} must use canonical endpoint order subject_id < object_id"
                    )

    return errors


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
    """Validate punctuation records without treating them as source text."""
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
            canonical = canonical_reading_sections(base_path)
        except (OSError, UnicodeError, ValueError) as exc:
            errors.append(f"{label} canonical entry cannot be parsed: {exc}")
            continue
        if metadata.get("entry_id") != entry_id:
            errors.append(f"{label} entry_id disagrees with canonical entry metadata")
        record_sections = record.get("sections")
        section_names = tuple(
            section_name
            for section_name in ("main_text", "liu_annotation")
            if isinstance(record_sections, dict) and section_name in record_sections
        )
        errors.extend(
            validate_punctuation_round_trip(
                record,
                canonical,
                section_names=section_names,
                allow_missing_punctuated=record.get("status") in {"candidate", "disputed"},
            )
        )

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
    unified_people: dict[str, dict[str, Any]] = {}
    if root is not None:
        unified_people = load_unified_person_registry(root, errors)
        errors.extend(validate_person_registry(records_by_kind, root, unified_people))

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

    relation_source_entries = (
        load_index(root, "data/shishuo-corpus-index.json", "entries", "id", errors)
        if root is not None else {}
    )
    relation_source_units = (
        load_index(root, "data/jinshu-unit-index.json", "units", "unit_id", errors)
        if root is not None else {}
    )
    for relation in relations.values():
        add_ref_error(errors, f"Relation {relation.get('id')} subject_id", relation.get("subject_id"), people)
        add_ref_error(errors, f"Relation {relation.get('id')} object_id", relation.get("object_id"), people)
        refs(f"Relation {relation.get('id')} story_ids", relation.get("story_ids"), stories)
        if "source_entry_ids" in relation:
            refs(
                f"Relation {relation.get('id')} source_entry_ids",
                relation.get("source_entry_ids"),
                relation_source_entries,
            )
        if "source_unit_ids" in relation:
            refs(
                f"Relation {relation.get('id')} source_unit_ids",
                relation.get("source_unit_ids"),
                relation_source_units,
            )
        refs(f"Relation {relation.get('id')} evidence_ids", relation.get("evidence_ids"), evidence)

    for era in eras.values():
        refs(f"Era {era.get('id')} story_ids", era.get("story_ids"), stories)
        refs(f"Era {era.get('id')} person_ids", era.get("person_ids"), people)
        refs(f"Era {era.get('id')} evidence_ids", era.get("evidence_ids"), evidence)

    for item in evidence.values():
        add_ref_error(errors, f"Evidence {item.get('id')} source_id", item.get("source_id"), sources)

    if root is not None:
        errors.extend(validate_canonical_provenance(root, records_by_kind, sources, mode=mode))

    errors.extend(
        validate_relation_records(
            records_by_kind,
            root=root,
            unified_people=unified_people if root is not None else None,
        )
    )

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

    def validate_display_pair(value: Any, label: str) -> None:
        if not isinstance(value, dict):
            errors.append(f"{label} must be an object with original and simplified forms")
            return
        for key in ("original", "simplified"):
            if not isinstance(value.get(key), str) or not value.get(key):
                errors.append(f"{label}.{key} must be a non-empty string")

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

        labels = reading.get("labels")
        if not isinstance(labels, dict) or set(labels) != set(READER_LABELS):
            errors.append(f"{label}.labels does not match the reader-label contract")
        elif isinstance(labels, dict):
            for key in READER_LABELS:
                validate_display_pair(labels.get(key), f"{label}.labels.{key}")

        people_by_id = {
            record.get("id"): record for record in records_by_kind["people"]
        }
        person_display = reading.get("person_display")
        if not isinstance(person_display, dict) or set(person_display) != set(people_by_id):
            errors.append(f"{label}.person_display IDs do not match canonical Person IDs")
        elif isinstance(person_display, dict):
            for person_id, person in people_by_id.items():
                display = person_display.get(person_id)
                if not isinstance(display, dict):
                    errors.append(f"{label}.person_display.{person_id} is missing")
                    continue
                validate_display_pair(display.get("name"), f"{label}.person_display.{person_id}.name")
                if isinstance(display.get("name"), dict) and display["name"].get("original") != person.get("canonical_name"):
                    errors.append(f"{label}.person_display.{person_id}.name.original changes canonical_name")
                aliases = display.get("aliases")
                canonical_aliases = person.get("aliases", [])
                if not isinstance(aliases, list) or len(aliases) != len(canonical_aliases):
                    errors.append(f"{label}.person_display.{person_id}.aliases do not match canonical aliases")
                elif isinstance(aliases, list):
                    for alias_index, (display_alias, canonical_alias) in enumerate(zip(aliases, canonical_aliases)):
                        alias_label = f"{label}.person_display.{person_id}.aliases[{alias_index}]"
                        if not isinstance(display_alias, dict):
                            errors.append(f"{alias_label} is not an object")
                            continue
                        validate_display_pair(display_alias.get("surface"), f"{alias_label}.surface")
                        if isinstance(display_alias.get("surface"), dict) and display_alias["surface"].get("original") != canonical_alias.get("surface"):
                            errors.append(f"{alias_label}.surface.original changes canonical alias surface")

        mention_display = reading.get("mention_display")
        mentions_by_id = {
            record.get("id"): record for record in records_by_kind["mentions"]
        }
        if not isinstance(mention_display, dict) or set(mention_display) != set(mentions_by_id):
            errors.append(f"{label}.mention_display IDs do not match canonical Mention IDs")
        elif isinstance(mention_display, dict):
            for mention_id, mention in mentions_by_id.items():
                display = mention_display.get(mention_id)
                if not isinstance(display, dict):
                    errors.append(f"{label}.mention_display.{mention_id} is missing")
                    continue
                validate_display_pair(display.get("surface"), f"{label}.mention_display.{mention_id}.surface")
                if isinstance(display.get("surface"), dict) and display["surface"].get("original") != mention.get("surface"):
                    errors.append(f"{label}.mention_display.{mention_id}.surface.original changes canonical mention")

        source_display = reading.get("source_display")
        sources_by_id = {
            record.get("id"): record for record in records_by_kind["sources"]
        }
        if not isinstance(source_display, dict) or set(source_display) != set(sources_by_id):
            errors.append(f"{label}.source_display IDs do not match canonical Source IDs")
        elif isinstance(source_display, dict):
            for source_id, source in sources_by_id.items():
                display = source_display.get(source_id)
                if not isinstance(display, dict):
                    errors.append(f"{label}.source_display.{source_id} is missing")
                    continue
                for field in ("work", "edition"):
                    validate_display_pair(display.get(field), f"{label}.source_display.{source_id}.{field}")
                    if isinstance(display.get(field), dict) and display[field].get("original") != source.get(field):
                        errors.append(f"{label}.source_display.{source_id}.{field}.original changes canonical source title")
    vite_path = root / "site/src/generated/wp1-site.json"
    try:
        if (root / "data/derived/wp1-site.json").read_bytes() != vite_path.read_bytes():
            errors.append("site/src/generated/wp1-site.json bytes differ from data/derived/wp1-site.json")
    except OSError as exc:
        errors.append(f"cannot compare generated bundle bytes: {exc}")
    try:
        vite_bundle = read_json(vite_path)
        if vite_bundle != bundle:
            errors.append("site/src/generated/wp1-site.json differs from data/derived/wp1-site.json")
    except (OSError, ValueError) as exc:
        errors.append(str(exc))
    obsolete_public_path = root / "site/public/data/wp1-site.json"
    if obsolete_public_path.exists():
        errors.append("obsolete runtime bundle exists: site/public/data/wp1-site.json")
    return errors


def validate_repository(root: Path, mode: str = "full") -> list[str]:
    errors: list[str] = []
    errors.extend(validate_punctuation(root, mode=mode))
    try:
        from .validate_shishuo_reading_layer import validate_reading_layer
    except ImportError:  # pragma: no cover - direct script execution
        from validate_shishuo_reading_layer import validate_reading_layer
    errors.extend(validate_reading_layer(root, mode=mode))
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
