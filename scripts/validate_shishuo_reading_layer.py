#!/usr/bin/env python3
"""Validate the CRL1 corpus-wide Shishuo reading layer."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

import yaml
from jsonschema import Draft202012Validator
from opencc import OpenCC

try:
    from .build_six_person_pilot import parse_shishuo_sections
    from .reading_layers import strip_display_punctuation
except ImportError:  # pragma: no cover - direct script execution
    from build_six_person_pilot import parse_shishuo_sections
    from reading_layers import strip_display_punctuation


READING_SCHEMA = "schema/reading-layer.schema.json"
READING_DATA = "data/derived/shishuo-reading-layer.json"
PUNCTUATION_DATA = "data/annotation/wp1-punctuation.json"
QUALIFICATION_DATA = "data/reading-source-qualification.json"
QUALIFICATION_SCHEMA = "schema/reading-source-qualification.schema.json"
REVIEW_QUEUE_JSON = "data/derived/punctuation-review-queue.json"
QUEUE_DATA = "content/curated/shishuo/reading-layer/review-queue.yaml"
INDEX_DATA = "data/shishuo-corpus-index.json"


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_main_text(path: Path) -> str:
    for section, body, _metadata in parse_shishuo_sections(path.read_text(encoding="utf-8")):
        if section == "main_text":
            return body.strip("\n")
    raise ValueError(f"canonical entry has no main text: {path}")


def _qualification_map(root: Path, errors: list[str]) -> dict[str, dict[str, Any]]:
    try:
        document = read_json(root / QUALIFICATION_DATA)
        schema = read_json(root / QUALIFICATION_SCHEMA)
    except (OSError, json.JSONDecodeError) as exc:
        errors.append(f"CRL1.1 qualification cannot be read: {exc}")
        return {}
    for error in sorted(Draft202012Validator(schema).iter_errors(document), key=lambda item: list(item.path)):
        location = ".".join(str(item) for item in error.path) or "document"
        errors.append(f"CRL1.1 qualification schema {location}: {error.message}")
    records = document.get("records", []) if isinstance(document, dict) else []
    result: dict[str, dict[str, Any]] = {}
    for record in records:
        if isinstance(record, dict) and isinstance(record.get("id"), str):
            result[record["id"]] = record
    for record in result.values():
        source = record.get("source", {})
        source_path = root / str(source.get("path", ""))
        if not source_path.is_file():
            errors.append(f"CRL1.1 qualification source is missing: {source.get('path')!r}")
        else:
            actual = sha256_file(source_path)
            if actual != source.get("sha256"):
                errors.append(
                    f"CRL1.1 qualification source hash mismatch: {source.get('path')!r}: "
                    f"{source.get('sha256')!r} != {actual!r}"
                )
        metadata = record.get("metadata", {})
        for key in ("path", "registry_path"):
            metadata_path = root / str(metadata.get(key, ""))
            if not metadata_path.is_file():
                errors.append(f"CRL1.1 qualification {key} is missing: {metadata.get(key)!r}")
            else:
                hash_key = "sha256" if key == "path" else "registry_sha256"
                actual = sha256_file(metadata_path)
                if actual != metadata.get(hash_key):
                    errors.append(
                        f"CRL1.1 qualification {key} hash mismatch: {metadata.get(key)!r}"
                    )
    return result


def validate_reading_layer(root: Path, mode: str = "full") -> list[str]:
    """Validate derived CRL1 products.

    ``mode`` is accepted deliberately so callers can use the same explicit
    full/portable validation command as WP1.  Upstream witness path/hash
    validation remains in ``validate_wp1.validate_punctuation``; this function
    validates the derived layer and its canonical artifact contract.
    """

    errors: list[str] = []
    qualifications = _qualification_map(root, errors)
    reading_path = root / READING_DATA
    schema_path = root / READING_SCHEMA
    try:
        document = read_json(reading_path)
        schema = read_json(schema_path)
    except (OSError, json.JSONDecodeError) as exc:
        return [f"CRL1 cannot read required JSON: {exc}"]
    schema_errors = sorted(Draft202012Validator(schema).iter_errors(document), key=lambda error: list(error.path))
    for error in schema_errors:
        location = ".".join(str(item) for item in error.path) or "document"
        errors.append(f"CRL1 schema {location}: {error.message}")

    try:
        index = read_json(root / INDEX_DATA)
        punctuation = read_json(root / PUNCTUATION_DATA)
        queue = yaml.safe_load((root / QUEUE_DATA).read_text(encoding="utf-8"))
        bucket_queue = read_json(root / REVIEW_QUEUE_JSON)
    except (OSError, json.JSONDecodeError, yaml.YAMLError) as exc:
        return errors + [f"CRL1 cannot read index/annotation/queue: {exc}"]

    entries = index.get("entries", [])
    entry_by_id = {entry.get("id"): entry for entry in entries}
    punctuation_by_entry = {
        record.get("entry_id"): record for record in punctuation.get("records", [])
    }
    records = document.get("records", [])
    ids = [record.get("entry_id") for record in records]
    if len(ids) != len(set(ids)):
        errors.append("CRL1 has duplicate entry IDs")
    if ids != [entry.get("id") for entry in sorted(entries, key=lambda item: item.get("global_ordinal", 0))]:
        errors.append("CRL1 records are not in canonical global order")
    if document.get("entry_count") != len(entries):
        errors.append(f"CRL1 entry_count does not equal the canonical index: {document.get('entry_count')} != {len(entries)}")
    if len(records) != len(entries):
        errors.append(f"CRL1 record count does not equal the canonical index: {len(records)} != {len(entries)}")

    converter = OpenCC("t2s")
    reader_ready_ids: set[str] = set()
    for index_number, record in enumerate(records):
        label = f"CRL1 record {index_number}"
        entry_id = record.get("entry_id")
        entry = entry_by_id.get(entry_id)
        punctuation_record = punctuation_by_entry.get(entry_id)
        if entry is None:
            errors.append(f"{label} references nonexistent Shishuo entry: {entry_id!r}")
            continue
        if punctuation_record is None:
            errors.append(f"{label} has no punctuation record: {entry_id!r}")
            continue
        review_status = punctuation_record.get("review_status")
        punctuation_basis = punctuation_record.get("punctuation_basis")
        exact_transfer = punctuation_record.get("exact_transfer")
        qualification_id = punctuation_record.get("source_qualification_id")
        if review_status not in {"reviewed", "unreviewed"}:
            errors.append(f"{label} has invalid review_status: {review_status!r}")
        if punctuation_basis not in {
            "human_reviewed", "trusted_reference_exact", "reference_candidate", "disputed"
        }:
            errors.append(f"{label} has invalid punctuation_basis: {punctuation_basis!r}")
        if not isinstance(exact_transfer, bool):
            errors.append(f"{label} exact_transfer must be boolean")
        if review_status == "reviewed" and punctuation_basis != "human_reviewed":
            errors.append(f"{label} reviewed record must use human_reviewed punctuation_basis")
        if review_status == "unreviewed" and punctuation_basis == "human_reviewed":
            errors.append(f"{label} unreviewed record cannot use human_reviewed punctuation_basis")
        if punctuation_basis == "human_reviewed" and qualification_id is not None:
            errors.append(f"{label} human-reviewed record must not depend on a machine qualification ID")
        if punctuation_basis in {"reference_candidate", "trusted_reference_exact"}:
            if not isinstance(qualification_id, str) or qualification_id not in qualifications:
                errors.append(f"{label} machine punctuation has no resolving qualification record")
        if punctuation_basis == "trusted_reference_exact":
            qualification = qualifications.get(qualification_id, {})
            if qualification.get("qualification") != "qualified":
                errors.append(f"{label} trusted_reference_exact requires a qualified source")
            if qualification.get("allows_trusted_reference_promotion") is not True:
                errors.append(f"{label} trusted_reference_exact is not allowed by source qualification")
            if exact_transfer is not True:
                errors.append(f"{label} trusted_reference_exact requires exact_transfer=true")
        if punctuation_basis == "reference_candidate" and review_status != "unreviewed":
            errors.append(f"{label} reference_candidate must remain unreviewed")
        if punctuation_basis == "disputed" and punctuation_record.get("status") != "disputed":
            errors.append(f"{label} disputed punctuation_basis must retain status=disputed")
        if record.get("punctuation_record_id") != punctuation_record.get("id"):
            errors.append(f"{label} punctuation_record_id does not resolve to the entry record")
        if record.get("base_canonical_entry_path") != entry.get("path"):
            errors.append(f"{label} canonical path disagrees with the Shishuo index")
        if record.get("base_canonical_entry_sha256") != entry.get("entry_sha256"):
            errors.append(f"{label} canonical hash disagrees with the Shishuo index")

        canonical_path = root / str(entry.get("path"))
        if not canonical_path.is_file():
            errors.append(f"{label} canonical artifact is missing: {entry.get('path')!r}")
            continue
        canonical = canonical_main_text(canonical_path)
        main = record.get("main_text", {})
        original = main.get("original") if isinstance(main, dict) else None
        simplified = main.get("simplified") if isinstance(main, dict) else None
        available = main.get("available") if isinstance(main, dict) else None
        if available != isinstance(original, str) or available != bool(available):
            errors.append(f"{label} main_text.available disagrees with original")
        if original is None:
            if simplified is not None:
                errors.append(f"{label} has simplified text without original punctuation")
        else:
            if not isinstance(simplified, str) or not simplified:
                errors.append(f"{label} simplified reading is missing")
            elif converter.convert(original) != simplified:
                errors.append(f"{label} simplified reading is not deterministic OpenCC t2s output")
            if strip_display_punctuation(original) != strip_display_punctuation(canonical):
                errors.append(f"{label} punctuation round-trip changes the canonical sequence")

        status = record.get("status")
        ready_expected = bool(
            original
            and not record.get("round_trip_errors")
            and isinstance(simplified, str)
            and simplified
            and (
                (review_status == "reviewed" and punctuation_basis == "human_reviewed")
                or (
                    review_status == "unreviewed"
                    and punctuation_basis == "trusted_reference_exact"
                )
            )
        )
        if record.get("story_reader_ready") != ready_expected:
            errors.append(f"{label} story_reader_ready violates the CRL1 status rule")
        if record.get("story_reader_ready"):
            reader_ready_ids.add(str(entry_id))
        if status in {"candidate", "disputed"} and record.get("story_reader_ready"):
            errors.append(f"{label} candidate/disputed record is reader-ready")
        alignment = record.get("alignment", {})
        if alignment.get("transfer_class") not in {
            "exact_character_transfer",
            "one_to_one_metadata_transfer",
            "character_mismatch_around_punctuation",
            "punctuation_boundary_disagreement",
            "structural_or_boundary_mismatch",
            "missing_reference",
        }:
            errors.append(f"{label} has invalid alignment transfer_class")
        if alignment.get("reference_case") in {None, ""}:
            errors.append(f"{label} has no alignment reference_case")
        if exact_transfer:
            if alignment.get("alignment_class") != "exact-agreement":
                errors.append(f"{label} exact_transfer does not have exact-agreement alignment")
            if alignment.get("transfer_class") != "exact_character_transfer":
                errors.append(f"{label} exact_transfer has the wrong transfer_class")
            if not original or strip_display_punctuation(original) != strip_display_punctuation(canonical):
                errors.append(f"{label} exact_transfer does not round-trip exactly")
        elif alignment.get("alignment_class") == "exact-agreement" and original:
            errors.append(f"{label} exact-agreement punctuation with a candidate must declare exact_transfer=true")

        if alignment.get("status") != status and status != "reviewed":
            errors.append(f"{label} alignment status does not match punctuation status")
        automatic = record.get("automatic_comparison")
        if status == "reviewed" and automatic is None:
            errors.append(f"{label} reviewed record lacks the machine comparison audit")

    queue_records = queue.get("records", []) if isinstance(queue, dict) else []
    queue_ids = [item.get("entry_id") for item in queue_records]
    expected_queue_ids = {
        record.get("entry_id")
        for record in records
        if record.get("punctuation_basis") in {"reference_candidate", "disputed"}
        and not (
            record.get("punctuation_basis") == "reference_candidate"
            and record.get("exact_transfer") is True
        )
    }
    if len(queue_ids) != len(set(queue_ids)):
        errors.append("CRL1 review queue has duplicate entry IDs")
    if set(queue_ids) != expected_queue_ids:
        errors.append("CRL1 review queue does not exactly project non-ready/non-reviewed records")
    for item in queue_records:
        entry_id = item.get("entry_id")
        if entry_id not in entry_by_id:
            errors.append(f"CRL1 queue references nonexistent Shishuo entry: {entry_id!r}")
        if item.get("status") not in {"candidate", "disputed"}:
            errors.append(f"CRL1 queue item has invalid status: {entry_id!r}")

    bucket_records = bucket_queue.get("records", []) if isinstance(bucket_queue, dict) else []
    bucket_ids = [item.get("entry_id") for item in bucket_records]
    if bucket_ids != ids:
        errors.append("CRL1.1 bucket queue does not represent entries in canonical order")
    expected_buckets: dict[str, str] = {}
    for record in records:
        record_entry_id = record.get("entry_id")
        rs = record.get("review_status")
        basis = record.get("punctuation_basis")
        exact = record.get("exact_transfer") is True
        ready = record.get("story_reader_ready") is True
        if ready and basis in {"human_reviewed", "trusted_reference_exact"}:
            expected_bucket = "A_trusted_reference_ready"
        elif rs == "unreviewed" and basis == "reference_candidate" and exact:
            expected_bucket = "B_exact_transfer_awaiting_source_qualification"
        elif rs == "unreviewed" and basis == "reference_candidate" and record.get("status") == "candidate":
            expected_bucket = "C_punctuation_review_candidate"
        else:
            expected_bucket = "D_disputed_structural_review"
        expected_buckets[record_entry_id] = expected_bucket
    seen_bucket_ids: set[str] = set()
    for item in bucket_records:
        entry_id = item.get("entry_id")
        if entry_id in seen_bucket_ids:
            errors.append(f"CRL1.1 bucket queue has duplicate entry ID: {entry_id!r}")
        seen_bucket_ids.add(entry_id)
        if expected_buckets.get(entry_id) != item.get("bucket"):
            errors.append(f"CRL1.1 bucket mismatch for {entry_id!r}")
        if item.get("source_qualification_id") and item.get("source_qualification_id") not in qualifications:
            errors.append(f"CRL1.1 bucket references unknown qualification: {entry_id!r}")
    declared_counts = bucket_queue.get("bucket_counts", {}) if isinstance(bucket_queue, dict) else {}
    actual_counts: dict[str, int] = {}
    for item in bucket_records:
        actual_counts[item.get("bucket")] = actual_counts.get(item.get("bucket"), 0) + 1
    if declared_counts != actual_counts:
        errors.append(f"CRL1.1 bucket counts are incorrect: {declared_counts!r} != {actual_counts!r}")

    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--mode", choices=("full", "portable"), default="full")
    args = parser.parse_args()
    errors = validate_reading_layer(args.root.resolve(), mode=args.mode)
    if errors:
        print("CRL1 validation failed:")
        print("\n".join(f"- {error}" for error in errors))
        return 1
    print(f"CRL1 validation passed (provenance mode: {args.mode})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
