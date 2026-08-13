#!/usr/bin/env python3
"""Validate P3A.1 open-world identity discovery artifacts."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

from jsonschema import Draft202012Validator

try:
    from .person_identity_discovery import (
        ALIASES_PATH,
        CORPUS_INDEX_PATH,
        JINSHU_INDEX_PATH,
        OCCURRENCES_PATH,
        OUTPUT_PATH,
        PEOPLE_PATH,
        SHISHUO_ENTRIES_PATH,
    )
    from .validate_wp1 import validate_source_provenance
except ImportError:
    from person_identity_discovery import (
        ALIASES_PATH,
        CORPUS_INDEX_PATH,
        JINSHU_INDEX_PATH,
        OCCURRENCES_PATH,
        OUTPUT_PATH,
        PEOPLE_PATH,
        SHISHUO_ENTRIES_PATH,
    )
    from validate_wp1 import validate_source_provenance


ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = ROOT / "schema/person-identity-candidates.schema.json"
OCCURRENCE_SCHEMA_PATH = ROOT / "schema/person-candidate-occurrences.schema.json"
PROVENANCE_MODES = {"full", "portable"}


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def validate(root: Path = ROOT, *, mode: str = "full") -> list[str]:
    errors: list[str] = []
    if mode not in PROVENANCE_MODES:
        return [f"unsupported provenance mode: {mode}"]
    try:
        document = read_json(root / OUTPUT_PATH)
        occurrences = read_json(root / OCCURRENCES_PATH)
        schema = read_json(root / SCHEMA_PATH)
        occurrence_schema = read_json(root / OCCURRENCE_SCHEMA_PATH)
        people = read_json(root / PEOPLE_PATH).get("people", [])
        corpus = read_json(root / CORPUS_INDEX_PATH).get("entries", [])
        unit_index = read_json(root / JINSHU_INDEX_PATH).get("units", [])
    except (OSError, ValueError, KeyError) as exc:
        return [f"P3A.1 cannot read required artifact/input: {exc}"]

    errors.extend(f"candidate schema: {error.message}" for error in Draft202012Validator(schema).iter_errors(document))
    errors.extend(f"occurrence schema: {error.message}" for error in Draft202012Validator(occurrence_schema).iter_errors(occurrences))

    scoped_ids = {
        str(item.get("person_id"))
        for item in people
        if isinstance(item, Mapping) and isinstance(item.get("person_id"), str)
    }
    story_ids = {
        str(item.get("id"))
        for item in corpus
        if isinstance(item, Mapping) and isinstance(item.get("id"), str)
    }
    unit_ids = {
        str(item.get("unit_id"))
        for item in unit_index
        if isinstance(item, Mapping) and isinstance(item.get("unit_id"), str)
    }

    candidates = document.get("candidates", [])
    candidate_map: dict[str, Mapping[str, Any]] = {}
    evidence_map: dict[str, Mapping[str, Any]] = {}
    for evidence in document.get("evidence", []):
        if not isinstance(evidence, Mapping):
            continue
        evidence_id = evidence.get("id")
        if not isinstance(evidence_id, str) or evidence_id in evidence_map:
            errors.append(f"duplicate/invalid P3A.1 evidence ID: {evidence_id!r}")
        else:
            evidence_map[evidence_id] = evidence

    if len(candidates) != document.get("discovery_counts", {}).get("candidate_identity_count"):
        errors.append("candidate identity count does not match candidates length")
    for candidate in candidates:
        if not isinstance(candidate, Mapping):
            continue
        candidate_id = candidate.get("candidate_id")
        if not isinstance(candidate_id, str) or candidate_id in candidate_map:
            errors.append(f"duplicate/invalid candidate ID: {candidate_id!r}")
            continue
        candidate_map[candidate_id] = candidate
        status = candidate.get("status")
        matched = candidate.get("matched_person_id")
        state = candidate.get("materialization_state")
        if status == "already_materialized":
            if matched not in scoped_ids or state != "already_materialized":
                errors.append(f"already-materialized candidate has invalid registry match: {candidate_id}")
        elif matched is not None or state != "new_candidate":
            errors.append(f"new candidate carries a production identity: {candidate_id}")
        if status in {"strong_candidate", "candidate"} and not candidate.get("preferred_name"):
            errors.append(f"eligible candidate lacks a preferred name: {candidate_id}")
        surfaces = candidate.get("surfaces", [])
        surface_keys: set[tuple[str, str]] = set()
        for surface in surfaces:
            if not isinstance(surface, Mapping):
                continue
            key = (str(surface.get("surface")), str(surface.get("surface_type")))
            if key in surface_keys:
                errors.append(f"duplicate candidate surface identity: {candidate_id}/{key}")
            surface_keys.add(key)
            if surface.get("association_mode") == "exact" and surface.get("surface_type") in {"office_title", "contextual_title", "posthumous_title"}:
                errors.append(f"contextual/title surface was projected as exact: {candidate_id}/{surface.get('surface')}")
            for evidence_id in surface.get("evidence_ids", []):
                if evidence_id not in evidence_map:
                    errors.append(f"candidate surface evidence does not resolve: {candidate_id}/{evidence_id}")
        for evidence_id in [*candidate.get("identity_evidence_ids", []), *candidate.get("evidence_ids", [])]:
            if evidence_id not in evidence_map:
                errors.append(f"candidate evidence does not resolve: {candidate_id}/{evidence_id}")
        if not set(candidate.get("shishuo_story_ids", [])).issubset(story_ids):
            errors.append(f"candidate references an unknown Shishuo Story: {candidate_id}")
        if not set(candidate.get("current_sc1_story_ids", [])).issubset(story_ids):
            errors.append(f"candidate references an unknown current Story: {candidate_id}")
        for metric, value in candidate.get("metrics", {}).items():
            if isinstance(value, (int, float)) and value < 0:
                errors.append(f"candidate metric is negative: {candidate_id}/{metric}")

    occurrence_rows = occurrences.get("occurrences", [])
    if len(occurrence_rows) != occurrences.get("occurrence_count"):
        errors.append("candidate occurrence count does not match occurrences length")
    occurrence_ids: set[str] = set()
    artifact_hashes: dict[str, str] = {}
    trusted_records: dict[str, list[dict[str, Any]]] | None = None
    for occurrence in occurrence_rows:
        if not isinstance(occurrence, Mapping):
            continue
        occurrence_id = occurrence.get("occurrence_id")
        if occurrence_id in occurrence_ids:
            errors.append(f"duplicate occurrence ID: {occurrence_id}")
        occurrence_ids.add(str(occurrence_id))
        candidate_id = occurrence.get("candidate_id")
        candidate = candidate_map.get(str(candidate_id))
        if candidate is None:
            errors.append(f"occurrence points to unknown candidate: {candidate_id}")
        elif candidate.get("materialization_state") != "new_candidate":
            errors.append(f"occurrence points to an already-materialized candidate: {candidate_id}")
        source_id = occurrence.get("source_id")
        if source_id not in story_ids:
            errors.append(f"candidate occurrence points to unknown Story: {source_id}")
        if occurrence.get("section") not in {"main_text", "liu_annotation"}:
            errors.append(f"candidate occurrence has invalid section: {occurrence_id}")
        for evidence_id in occurrence.get("evidence_ids", []):
            evidence = evidence_map.get(evidence_id)
            if evidence is None:
                errors.append(f"candidate occurrence evidence does not resolve: {occurrence_id}/{evidence_id}")
            elif evidence.get("candidate_id") != candidate_id:
                errors.append(f"candidate occurrence evidence owner mismatch: {occurrence_id}/{evidence_id}")

    for evidence_id, evidence in evidence_map.items():
        locator = evidence.get("locator", {})
        if not isinstance(locator, Mapping):
            errors.append(f"evidence locator is not an object: {evidence_id}")
            continue
        artifact_path = locator.get("artifact_path")
        if not isinstance(artifact_path, str):
            errors.append(f"evidence lacks artifact path: {evidence_id}")
        else:
            path = root / artifact_path
            if not path.is_file():
                errors.append(f"evidence artifact does not exist: {evidence_id}/{artifact_path}")
            else:
                actual = artifact_hashes.setdefault(artifact_path, _sha256(path))
                if locator.get("artifact_sha256") != actual:
                    errors.append(f"evidence artifact hash mismatch: {evidence_id}/{artifact_path}")
        provenance = locator.get("source_provenance")
        if not isinstance(provenance, Mapping):
            errors.append(f"evidence lacks source provenance: {evidence_id}")
        else:
            errors.extend(
                validate_source_provenance(
                    root,
                    dict(provenance),
                    label=f"P3A.1 Evidence {evidence_id} source_provenance",
                    mode=mode,
                    trusted_records=trusted_records,
                )
            )

    unresolved = document.get("unresolved_surface_clusters", [])
    for row in unresolved:
        if row.get("not_ranked_as_person") is not True:
            errors.append(f"unresolved surface is not explicitly excluded: {row.get('surface')}")
        if row.get("surface") in {candidate.get("preferred_name") for candidate in candidates}:
            errors.append(f"unresolved surface masquerades as a candidate identity: {row.get('surface')}")
        if not set(row.get("story_ids", [])).issubset(story_ids):
            errors.append(f"unresolved surface references unknown Story: {row.get('surface')}")

    for gap in document.get("current_sc1_open_world_gaps", []):
        if gap.get("story_id") not in story_ids:
            errors.append(f"open-world gap references unknown Story: {gap.get('story_id')}")
        for item in gap.get("candidates", []):
            if item.get("candidate_id") not in candidate_map:
                errors.append(f"open-world gap references unknown candidate: {item.get('candidate_id')}")

    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--mode", choices=sorted(PROVENANCE_MODES), default="full")
    args = parser.parse_args()
    errors = validate(args.root, mode=args.mode)
    if errors:
        for error in errors:
            print(error)
        return 1
    print(f"P3A.1 identity discovery artifacts valid ({args.mode})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
