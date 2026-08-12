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


OBJECTS = {
    "Source": ("schema/source.schema.json", "data/sources/wp1-sources.json", "sources"),
    "Story": ("schema/story.schema.json", "data/annotation/wp1-stories.json", "stories"),
    "Person": ("schema/person.schema.json", "data/annotation/wp1-people.json", "people"),
    "Mention": ("schema/mention.schema.json", "data/annotation/wp1-mentions.json", "mentions"),
    "Relation": ("schema/relation.schema.json", "data/annotation/wp1-relations.json", "relations"),
    "Era": ("schema/era.schema.json", "data/annotation/wp1-eras.json", "eras"),
    "Evidence": ("schema/evidence.schema.json", "data/evidence/wp1-evidence.json", "evidence"),
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
) -> list[str]:
    """Validate artifact/source provenance against the canonical indexes and files."""
    errors: list[str] = []
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
        source_path_value = provenance.get("source_path")
        source_path = resolve_relative_file(
            root,
            source_path_value,
            f"Evidence {evidence_id} source_provenance.source_path",
            errors,
        )
        if source_path is not None:
            actual_source_hash = sha256_file(source_path)
            if provenance.get("source_sha256") != actual_source_hash:
                errors.append(
                    f"Evidence {evidence_id} source_sha256 does not match {source_path_value!r}: "
                    f"{provenance.get('source_sha256')!r} != {actual_source_hash!r}"
                )
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


def validate_references(
    records_by_kind: dict[str, list[dict[str, Any]]],
    root: Path | None = None,
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
        errors.extend(validate_canonical_provenance(root, records_by_kind, sources))

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
    public_path = root / "site/public/data/wp1-site.json"
    try:
        public_bundle = read_json(public_path)
        if public_bundle != bundle:
            errors.append("site/public/data/wp1-site.json differs from data/derived/wp1-site.json")
    except ValueError as exc:
        errors.append(str(exc))
    return errors


def validate_repository(root: Path) -> list[str]:
    errors: list[str] = []
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
        errors.extend(validate_references(records_by_kind, root=root))
        errors.extend(validate_manifest(root, records_by_kind))
        errors.extend(validate_bundle(root, records_by_kind))
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    errors = validate_repository(args.root)
    if errors:
        print("WP1 validation failed:")
        for error in errors:
            print(f"- {error}")
        return 1
    print("WP1 validation passed: schemas, IDs, references, evidence, manifest, and static bundle")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
