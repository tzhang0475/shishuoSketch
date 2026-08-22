#!/usr/bin/env python3
"""Validate DS1's isolated context, candidate, review, and preview boundary."""

from __future__ import annotations

import json
from pathlib import Path
import sys
from typing import Any, Mapping

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))

from ds1_common import (  # noqa: E402
    CANDIDATE_PATH,
    CONTEXT_PATH,
    INPUT_PATHS,
    PUBLIC_PATH,
    REVIEW_PATH,
    SCHEMA_PATH,
    STORY_ID,
    TOP_LEVEL_FIELDS,
    build_context_bundle,
    read_json,
    sha256_file,
    stable_json,
    validate_scene_context,
)


def _all_strings(value: Any):
    if isinstance(value, str):
        yield value
    elif isinstance(value, Mapping):
        for child in value.values():
            yield from _all_strings(child)
    elif isinstance(value, list):
        for child in value:
            yield from _all_strings(child)


def validate(root: Path = ROOT) -> list[str]:
    errors: list[str] = []
    if not (root / SCHEMA_PATH).is_file():
        errors.append(f"missing schema: {SCHEMA_PATH}")
    for relative in INPUT_PATHS:
        if not (root / relative).is_file():
            errors.append(f"missing DS1 input: {relative}")
    if not (root / CONTEXT_PATH).is_file():
        errors.append(f"missing DS1 context bundle: {CONTEXT_PATH}")
        return errors

    context = read_json(root, CONTEXT_PATH)
    schema = read_json(root, SCHEMA_PATH)
    if context.get("schema") != "ds1-context-bundle" or context.get("story_id") != STORY_ID:
        errors.append("context bundle has the wrong schema or Story")
    expected_hashes = {relative.as_posix(): sha256_file(root, relative) for relative in INPUT_PATHS}
    if context.get("source_hashes") != expected_hashes:
        errors.append("context source hashes do not match current reviewed inputs")
    evidence_ids = context.get("evidence_bundle_ids", [])
    index = context.get("evidence_index", {})
    if evidence_ids != sorted(set(evidence_ids)):
        errors.append("context evidence_bundle_ids are not unique and sorted")
    if set(evidence_ids) != set(index):
        errors.append("context evidence_bundle_ids do not match evidence_index")
    if any(Path(text).is_absolute() for text in _all_strings(context)):
        errors.append("context contains an absolute path")
    for field in (
        "participants",
        "episodes",
        "person_states",
        "temporal_relations",
        "uncertainties",
        "reviewed_facts",
        "relationship_evidence",
    ):
        for row in context.get(field, []):
            for ref in row.get("evidence_refs", []):
                if ref not in index:
                    errors.append(f"context {field} has orphan evidence ref: {ref}")
    for row in context.get("jianshu_evidence", []):
        if row.get("evidence_ref") not in index:
            errors.append(f"context jianshu_evidence has orphan evidence ref: {row.get('evidence_ref')}")

    # Rebuilding the context in memory is the deterministic source contract;
    # compare it without writing any production or canonical artifact.
    try:
        rebuilt = build_context_bundle(root, STORY_ID)
        if rebuilt != context:
            errors.append("context bundle is not deterministic from its inputs")
    except (KeyError, TypeError, ValueError, OSError) as error:
        errors.append(f"context rebuild failed: {error}")

    candidate_path = root / CANDIDATE_PATH
    review_path = root / REVIEW_PATH
    public_path = root / PUBLIC_PATH
    if candidate_path.is_file():
        candidate = read_json(root, CANDIDATE_PATH)
        if candidate.get("story_id") != STORY_ID or candidate.get("candidate_status") != "candidate":
            errors.append("candidate has the wrong Story or status")
        if candidate.get("canonical_write_back") is not False:
            errors.append("candidate does not explicitly forbid canonical write-back")
        if candidate.get("context_sha256") != sha256_file(root, CONTEXT_PATH):
            errors.append("candidate context hash does not match the context bundle")
        if candidate.get("evidence_bundle_ids") != evidence_ids:
            errors.append("candidate evidence bundle IDs differ from the context")
        if candidate.get("validation_errors"):
            errors.append("candidate contains model validation errors")
        if candidate.get("result") is not None:
            errors.extend(
                f"candidate schema: {error.message}"
                for error in Draft202012Validator(schema).iter_errors(candidate["result"])
            )
            errors.extend(validate_scene_context(candidate["result"], evidence_ids))
    if review_path.is_file():
        review = read_json(root, REVIEW_PATH)
        if review.get("story_id") != STORY_ID:
            errors.append("review record has the wrong Story")
        if review.get("decision") not in {"pending", "accepted", "rejected", "edited"}:
            errors.append("review decision is invalid")
        if not candidate_path.is_file():
            errors.append("review exists without a candidate")
        elif review.get("candidate", {}).get("sha256") != sha256_file(root, CANDIDATE_PATH):
            errors.append("review candidate hash does not match the candidate")
        if review.get("decision") == "edited":
            errors.extend(
                f"edited value schema: {error.message}"
                for error in Draft202012Validator(schema).iter_errors(review.get("edited_value"))
            )
            errors.extend(validate_scene_context(review.get("edited_value"), evidence_ids))
    if public_path.is_file():
        if not review_path.is_file() or not candidate_path.is_file():
            errors.append("DS1 public preview exists without candidate/review")
        else:
            review = read_json(root, REVIEW_PATH)
            candidate = read_json(root, CANDIDATE_PATH)
            if review.get("decision") not in {"accepted", "edited"}:
                errors.append("DS1 public preview is present without accepted/edited review")
            expected_value = review.get("edited_value") if review.get("decision") == "edited" else candidate.get("result")
            public = read_json(root, PUBLIC_PATH)
            if public.get("story_id") != STORY_ID or public.get("stage") != "DS1":
                errors.append("DS1 public preview has the wrong identity")
            if public.get("scene_context") != expected_value:
                errors.append("DS1 public preview differs from the reviewed value")
            errors.extend(
                f"preview schema: {error.message}"
                for error in Draft202012Validator(schema).iter_errors(public.get("scene_context"))
            )
            errors.extend(validate_scene_context(public.get("scene_context"), evidence_ids))
    # Guard the intended boundary explicitly; these generated files are not
    # allowed to masquerade as any canonical or Gold artifact.
    for relative in (CONTEXT_PATH, CANDIDATE_PATH, REVIEW_PATH, PUBLIC_PATH):
        if relative.as_posix().startswith(("data/derived/", "data/people", "data/facts")):
            errors.append(f"DS1 artifact is in a protected canonical path: {relative}")
    return sorted(set(errors))


def main() -> int:
    errors = validate(ROOT)
    if errors:
        print(stable_json({"errors": errors}), end="")
        return 1
    print("DS1 validation passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
