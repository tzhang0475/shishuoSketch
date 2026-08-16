#!/usr/bin/env python3
"""Validate the isolated NL0 StorySketch gold set and lazy shards."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys
from typing import Any, Mapping

from jsonschema import Draft202012Validator


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))

from build_nl0_story_sketch import (  # noqa: E402
    CANDIDATES_PATH,
    GOLD_PATH,
    H0C_FACTS_PATH,
    HR0_PATH,
    HR01_PATH,
    METRICS_PATH,
    PROTECTED_PATHS,
    PROTECTION_PATH,
    PUBLIC_MANIFEST_PATH,
    PUBLIC_ROOT,
    SC1_PATH,
    SCHEMA_PATH,
    SPEC_PATH,
    X1_2RF_FACTS_PATH,
    build_documents,
    sha256_file,
    stable_json,
)


def read_json(root: Path, relative: Path) -> Any:
    return json.loads((root / relative).read_text(encoding="utf-8"))


def validate(root: Path = ROOT) -> list[str]:
    errors: list[str] = []
    required = [
        SPEC_PATH,
        SCHEMA_PATH,
        SC1_PATH,
        HR0_PATH,
        HR01_PATH,
        H0C_FACTS_PATH,
        X1_2RF_FACTS_PATH,
        CANDIDATES_PATH,
        GOLD_PATH,
        METRICS_PATH,
        PROTECTION_PATH,
        PUBLIC_MANIFEST_PATH,
    ]
    for relative in required:
        if not (root / relative).is_file():
            errors.append(f"missing NL0 artifact: {relative}")
    if errors:
        return errors

    schema = read_json(root, SCHEMA_PATH)
    spec = read_json(root, SPEC_PATH)
    candidates = read_json(root, CANDIDATES_PATH)
    gold = read_json(root, GOLD_PATH)
    metrics = read_json(root, METRICS_PATH)
    protection = read_json(root, PROTECTION_PATH)
    manifest = read_json(root, PUBLIC_MANIFEST_PATH)
    sc1 = read_json(root, SC1_PATH)
    hr0 = read_json(root, HR0_PATH)
    hr01 = read_json(root, HR01_PATH)
    h0c = read_json(root, H0C_FACTS_PATH)
    x1_2rf = read_json(root, X1_2RF_FACTS_PATH)

    for label, document in (("candidates", candidates), ("gold", gold)):
        schema_errors = sorted(
            Draft202012Validator(schema).iter_errors(document),
            key=lambda error: list(error.absolute_path),
        )
        errors.extend(
            f"{label} schema: {error.message} at /{'/'.join(str(part) for part in error.absolute_path)}"
            for error in schema_errors
        )

    story_ids = {str(row.get("id")) for row in sc1.get("stories", [])}
    published_story_ids = {
        str(row.get("id"))
        for row in sc1.get("stories", [])
        if row.get("publication_state") in {"production_ready", "preview_ready"}
    }
    hr0_by_story = {str(row.get("story_id")): row for row in hr0.get("records", [])}
    hr01_by_story = {str(row.get("story_id")): row for row in hr01.get("records", [])}
    evidence_by_story = {
        story_id: {str(ref.get("evidence_id")): ref for ref in record.get("evidence_refs", [])}
        for story_id, record in hr0_by_story.items()
    }
    h0c_fact_ids = {str(row.get("fact_id")) for row in h0c.get("fact_index", [])}
    x1_2rf_fact_ids = {str(row.get("fact_id")) for row in x1_2rf.get("facts", [])}

    selected = sorted(str(value) for value in spec.get("scope", {}).get("selected_story_ids", []))
    candidate_records = candidates.get("records", [])
    gold_records = gold.get("records", [])
    candidate_by_story = {str(row.get("story_id")): row for row in candidate_records}
    gold_by_story = {str(row.get("story_id")): row for row in gold_records}
    if len(selected) < 5 or len(selected) > 8:
        errors.append(f"NL0 selected Story count outside 5–8: {len(selected)}")
    if selected != sorted(candidate_by_story) or selected != sorted(gold_by_story):
        errors.append("NL0 selected Story universe differs between spec/candidates/gold")
    if any(story_id not in story_ids for story_id in selected):
        errors.append("NL0 contains an unknown Story ID")
    if any(story_id not in published_story_ids for story_id in selected):
        errors.append("NL0 contains a non-published Story")
    if any(story_id not in hr0_by_story or story_id not in hr01_by_story for story_id in selected):
        errors.append("NL0 selected Story lacks HR0 or HR0.1 grounding")

    expected_hashes = {
        relative.as_posix(): sha256_file(root, relative)
        for relative in [SPEC_PATH, SCHEMA_PATH, SC1_PATH, HR0_PATH, HR01_PATH, H0C_FACTS_PATH, X1_2RF_FACTS_PATH]
    }
    for label, document in (("candidates", candidates), ("gold", gold), ("metrics", metrics)):
        if document.get("source_hashes") != expected_hashes:
            errors.append(f"{label} source_hashes do not match current inputs")
        if document.get("policy") != {
            "canonical_data_write_back": False,
            "canonical_fact_materialization": False,
            "llm": False,
            "rag": False,
            "generated_fields_may_abstain": True,
            "frontend_requires_accepted_review": True,
        }:
            errors.append(f"{label} policy is not the NL0 no-write-back policy")
    if any(Path(str(path)).is_absolute() for path in expected_hashes):
        errors.append("NL0 contains an absolute input path")

    def check_claim(story_id: str, claim: Mapping[str, Any] | None, role: str, story_evidence: set[str]) -> None:
        if claim is None:
            return
        if claim.get("claim_type") != role:
            errors.append(f"{story_id} claim type mismatch for {role}")
        evidence_ids = {str(value) for value in claim.get("evidence_ids", [])}
        if not evidence_ids:
            errors.append(f"{story_id} {role} claim has no evidence")
        if not evidence_ids.issubset(story_evidence):
            errors.append(f"{story_id} {role} claim has an orphan evidence reference")
        text = claim.get("text", {})
        if not text.get("original") or not text.get("simplified"):
            errors.append(f"{story_id} {role} claim has incomplete bilingual text")

    for label, records in (("candidate", candidate_records), ("gold", gold_records)):
        for record in records:
            story_id = str(record.get("story_id"))
            story_evidence = set(evidence_by_story.get(story_id, {}))
            check_claim(story_id, record.get("era_profile"), "era_profile", story_evidence)
            check_claim(story_id, record.get("scene_core"), "scene_core", story_evidence)
            for claim in record.get("essential_background", []):
                check_claim(story_id, claim, "essential_background", story_evidence)
            check_claim(story_id, record.get("resonance"), "resonance", story_evidence)
            if len(record.get("essential_background", [])) > 2:
                errors.append(f"{story_id} has more than two background items")
            if label == "candidate" and record.get("review_status") != "reviewed":
                errors.append(f"{story_id} candidate record is not reviewed")
            if label == "candidate" and record.get("review_decision") != "accepted":
                errors.append(f"{story_id} candidate record is not accepted for the Gold slice")
            if label == "gold" and record.get("review_status") != "accepted":
                errors.append(f"{story_id} Gold record is not accepted")
            support = {str(row.get("evidence_id")): row for row in record.get("supporting_evidence", [])}
            claim_evidence = {
                str(evidence_id)
                for _, claim in [*([("era_profile", record.get("era_profile"))] if record.get("era_profile") else []), ("scene_core", record.get("scene_core")), *[("essential_background", row) for row in record.get("essential_background", [])], *([("resonance", record.get("resonance"))] if record.get("resonance") else [])]
                for evidence_id in claim.get("evidence_ids", [])
            }
            if set(support) != claim_evidence:
                errors.append(f"{story_id} supporting_evidence does not exactly cover claims")
            for evidence_id, support_row in support.items():
                ref = evidence_by_story.get(story_id, {}).get(evidence_id)
                if ref is None:
                    errors.append(f"{story_id} supporting evidence is orphaned: {evidence_id}")
                    continue
                if support_row.get("source_layer") != ref.get("source_layer"):
                    errors.append(f"{story_id} source layer changed for {evidence_id}")
                if support_row.get("nl0_review_status") != "reviewed":
                    errors.append(f"{story_id} evidence link is not reviewed: {evidence_id}")
            grounded = record.get("grounded_inputs", {})
            if grounded.get("hr0_situation_id") != hr0_by_story.get(story_id, {}).get("situation_id"):
                errors.append(f"{story_id} HR0 situation reference is invalid")
            if not set(grounded.get("hr0_1_case_ids", [])).issubset(set(hr01_by_story.get(story_id, {}).get("case_ids", []))):
                errors.append(f"{story_id} HR0.1 case reference is invalid")
            if not set(grounded.get("historical_fact_ids", [])).issubset(h0c_fact_ids | x1_2rf_fact_ids):
                errors.append(f"{story_id} historical fact reference is invalid")

    if set(gold_by_story) != {story_id for story_id, row in candidate_by_story.items() if row.get("review_decision") == "accepted"}:
        errors.append("Gold records do not equal accepted candidate records")

    protected = protection.get("protected_inputs", {})
    expected_protected = {path.as_posix(): sha256_file(root, path) for path in PROTECTED_PATHS}
    if protected != expected_protected:
        errors.append("NL0 protected input hashes changed")
    if any(protection.get("write_back", {}).values()):
        errors.append("NL0 protection manifest permits write-back")

    if manifest.get("shards", {}).keys() and "manifest.json" in manifest.get("shards", {}):
        errors.append("NL0 manifest self-reference is not allowed")
    expected_shard_names = {f"story-sketch/{story_id}.json" for story_id in sorted(gold_by_story)}
    expected_shard_names.update(
        f"evidence/{evidence_id}.json"
        for record in gold_records
        for evidence_id in {
            str(value)
            for support in record.get("supporting_evidence", [])
            for value in [support.get("evidence_id")]
        }
    )
    actual_shard_names = {
        path.relative_to(root / PUBLIC_ROOT).as_posix()
        for path in (root / PUBLIC_ROOT).rglob("*.json")
        if path.name != "manifest.json"
    }
    if actual_shard_names != expected_shard_names:
        errors.append("NL0 shard directory does not match Gold Story universe")
    for relative in sorted(expected_shard_names):
        path = root / PUBLIC_ROOT / relative
        if not path.is_file():
            errors.append(f"missing NL0 shard: {relative}")
            continue
        expected = manifest.get("shards", {}).get(relative)
        if not expected:
            errors.append(f"NL0 manifest lacks shard: {relative}")
        elif expected.get("sha256") != sha256_file(root, PUBLIC_ROOT / relative) or expected.get("bytes") != path.stat().st_size:
            errors.append(f"NL0 shard hash/size mismatch: {relative}")
        payload = read_json(root, PUBLIC_ROOT / relative)
        if relative.startswith("story-sketch/"):
            if payload.get("review_status") != "accepted":
                errors.append(f"NL0 shard is not accepted: {relative}")
            if any(row.get("nl0_review_status") != "reviewed" for row in payload.get("supporting_evidence", [])):
                errors.append(f"NL0 shard contains an unreviewed evidence link: {relative}")
        else:
            if payload.get("projection") != "nl0_story_sketch_evidence" or payload.get("nl0_review_status") != "reviewed":
                errors.append(f"NL0 evidence shard is not reviewed: {relative}")
    manifest_text = (root / PUBLIC_MANIFEST_PATH).read_text(encoding="utf-8")
    if str(root) in manifest_text or any(Path(str(path)).is_absolute() for path in manifest.get("source_hashes", {})):
        errors.append("NL0 manifest contains an absolute path")
    for volatile_key in ("generated_at", "timestamp", "build_time", "built_at"):
        if volatile_key in manifest_text:
            errors.append(f"NL0 manifest contains volatile field: {volatile_key}")

    first = build_documents(root)
    second = build_documents(root)
    for key in ("candidates", "gold", "metrics", "protection", "shards", "manifest"):
        if stable_json(first[key]) != stable_json(second[key]):
            errors.append(f"NL0 builder is nondeterministic for {key}")
    return errors


def main() -> int:
    errors = validate(ROOT)
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1
    print(json.dumps({"status": "pass", "stage": "NL0"}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
