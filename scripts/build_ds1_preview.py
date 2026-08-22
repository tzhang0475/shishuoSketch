#!/usr/bin/env python3
"""Materialize the accepted DS1 review into an optional Story Sketch preview."""

from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))

from ds1_common import (  # noqa: E402
    CANDIDATE_PATH,
    CONTEXT_PATH,
    PUBLIC_PATH,
    REVIEW_PATH,
    STORY_ID,
    read_json,
    sha256_file,
    validate_scene_context,
    write_json,
)


def main() -> int:
    public_path = ROOT / PUBLIC_PATH
    candidate_path = ROOT / CANDIDATE_PATH
    review_path = ROOT / REVIEW_PATH
    if not candidate_path.is_file() or not review_path.is_file():
        if public_path.exists():
            public_path.unlink()
        return 0

    candidate = read_json(ROOT, CANDIDATE_PATH)
    review = read_json(ROOT, REVIEW_PATH)
    decision = review.get("decision")
    if decision not in {"accepted", "edited"}:
        if public_path.exists():
            public_path.unlink()
        return 0
    expected_sha = sha256_file(ROOT, CANDIDATE_PATH)
    if review.get("candidate", {}).get("sha256") != expected_sha:
        raise SystemExit("DS1 review does not match the current candidate; leave preview unpublished")
    context = read_json(ROOT, CONTEXT_PATH)
    value = review.get("edited_value") if decision == "edited" else candidate.get("result")
    errors = validate_scene_context(value, context.get("evidence_bundle_ids", []))
    if errors:
        raise SystemExit("DS1 reviewed value is invalid: " + "; ".join(errors))

    write_json(
        ROOT,
        PUBLIC_PATH,
        {
            "schema": "ds1-scene-context-preview",
            "schema_version": 1,
            "stage": "DS1",
            "story_id": STORY_ID,
            "review_status": decision,
            "candidate_sha256": expected_sha,
            "evidence_bundle_ids": context["evidence_bundle_ids"],
            "scene_context": value,
        },
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
