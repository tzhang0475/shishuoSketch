#!/usr/bin/env python3
"""Validate the isolated SFH2.2-A0R-L live-confirmation artifacts."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any, Iterable, Mapping

from sfh2_a0r.common import text as a0r_text
from sfh2_a0r.contracts import semantic_diff_paths

from sfh2_a0r_l.common import (
    A0R_ROOT,
    A0_SELECTION_PATH,
    BASELINE_COMMIT,
    CHALLENGE_SELECTION_PATH,
    CHALLENGE_STORIES,
    FUNCTION_NAMES,
    MAX_PROVIDER_ATTEMPTS,
    MODEL,
    OUT,
    PROMPT_VERSIONS,
    STRICT_ENDPOINT,
    a0_selection,
    a0r_freeze,
    architecture_freeze,
    input_hashes,
    read_json,
    stable_hash,
    text,
)
from sfh2_a0r_l.selection import build_selection

GOLD_KEYS = {
    "expected_identity", "expected_canonical_hint", "expected_role", "expected_semantic_kind",
    "expected_referent_surface", "expected_attribute_type", "expected_attribute_value",
    "expected_bearer", "must_not_resolve_to", "allow_abstention", "case_key",
}
FORBIDDEN_RUNTIME_PATTERNS = (
    re.compile(r"surface\s*=="),
    re.compile(r"surface\s+in\s+"),
    re.compile(r"canonical_hint\s*=\s*['\"](?:卿|吾|之|宣王|太丘長)"),
)


def _walk(value: Any, path: str = "") -> Iterable[tuple[str, Any]]:
    if isinstance(value, Mapping):
        for key, child in value.items():
            child_path = f"{path}.{key}" if path else str(key)
            yield child_path, child
            yield from _walk(child, child_path)
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from _walk(child, f"{path}[{index}]")


def _keys(value: Any) -> set[str]:
    return {path.rsplit(".", 1)[-1].split("[", 1)[0] for path, _ in _walk(value)}


def _errors() -> list[str]:
    errors: list[str] = []
    package = Path(__file__).resolve().parent / "sfh2_a0r_l"
    for path in sorted(package.glob("*.py")):
        content = path.read_text(encoding="utf-8")
        for pattern in FORBIDDEN_RUNTIME_PATTERNS:
            if pattern.search(content):
                errors.append(f"lexical_semantic_rule:{path.name}:{pattern.pattern}")
    return errors


def _selection_errors() -> list[str]:
    errors: list[str] = []
    actual = read_json(CHALLENGE_SELECTION_PATH, {}) or {}
    expected = build_selection()
    if actual != expected:
        errors.append("challenge_selection_drift")
    cases = actual.get("cases", []) if isinstance(actual.get("cases"), list) else []
    if actual.get("case_count") != 20 or len(cases) != 20:
        errors.append("challenge_case_count")
    if actual.get("story_count") != 5 or actual.get("story_ids") != list(CHALLENGE_STORIES):
        errors.append("challenge_story_set")
    if any(value != 4 for value in (actual.get("cases_per_story") or {}).values()):
        errors.append("challenge_not_four_per_story")
    if actual.get("previous_targeted_overlap"):
        errors.append("challenge_previous_overlap")
    if actual.get("previous_targeted_story_overlap"):
        errors.append("challenge_previous_story_overlap")
    if actual.get("gold_fields_present") is not False or actual.get("gold_not_in_selection") is not True:
        errors.append("challenge_gold_contract")
    if stable_hash({key: value for key, value in actual.items() if key != "selection_hash"}) != text(actual.get("selection_hash")):
        errors.append("challenge_selection_hash")
    if GOLD_KEYS.intersection(_keys(cases)):
        errors.append("gold_fields_in_challenge_selection")
    if len({(text(row.get("story_id")), text(row.get("mention_id"))) for row in cases if isinstance(row, Mapping)}) != 20:
        errors.append("challenge_occurrences_not_unique")

    prior: set[tuple[str, str]] = set()
    for path in (
        A0_SELECTION_PATH,
        Path("data/annotation/sfh2-2p1-selection.json"),
        Path("data/annotation/sfh2-2p2-selection.json"),
    ):
        document = read_json(path, {}) or {}
        prior.update((text(row.get("story_id")), text(row.get("mention_id"))) for row in document.get("cases", []) or [] if isinstance(row, Mapping))
    selected = {(text(row.get("story_id")), text(row.get("mention_id"))) for row in cases if isinstance(row, Mapping)}
    if prior.intersection(selected):
        errors.append("challenge_occurrence_prior_target_overlap")
    prior_stories = {story_id for story_id, _ in prior}
    if set(CHALLENGE_STORIES).intersection(prior_stories):
        errors.append("challenge_story_prior_target_overlap")
    return errors


def _freeze_errors() -> list[str]:
    errors: list[str] = []
    current = read_json(OUT / "architecture-freeze.json", {}) or {}
    expected = architecture_freeze(text((read_json(A0_SELECTION_PATH, {}) or {}).get("selection_hash")), text((read_json(CHALLENGE_SELECTION_PATH, {}) or {}).get("selection_hash")))
    if current != expected:
        errors.append("architecture_freeze_drift")
    if current.get("baseline_commit") != BASELINE_COMMIT:
        errors.append("baseline_commit_mismatch")
    if current.get("a0r_architecture_hash") != a0r_freeze().get("architecture_hash"):
        errors.append("a0r_architecture_not_frozen")
    model = current.get("model_config") or {}
    if model.get("model") != MODEL or model.get("temperature") != 0 or model.get("thinking") != {"type": "disabled"}:
        errors.append("model_config_changed")
    if model.get("endpoint") != STRICT_ENDPOINT or model.get("prompt_versions") != PROMPT_VERSIONS or model.get("function_names") != FUNCTION_NAMES:
        errors.append("provider_config_changed")
    if current.get("input_hashes") != input_hashes():
        errors.append("frozen_input_hash_drift")
    return errors


def _packet_errors() -> list[str]:
    errors: list[str] = []
    document = read_json(OUT / "case-packets.json", {}) or {}
    for cohort in ("regression", "challenge"):
        rows = document.get(cohort, []) if isinstance(document.get(cohort), list) else []
        if len(rows) != 20:
            errors.append(f"{cohort}_packet_count")
        for row in rows:
            packet = row.get("packet") if isinstance(row, Mapping) else {}
            if row.get("errors"):
                errors.append(f"{cohort}_packet_error:{row.get('case_id')}")
            if GOLD_KEYS.intersection(_keys(packet)):
                errors.append(f"gold_in_{cohort}_packet:{row.get('case_id')}")
            target = packet.get("target") if isinstance(packet, Mapping) else {}
            evidence_ids = {text(item.get("evidence_id")) for item in packet.get("source_evidence", []) or [] if isinstance(item, Mapping)} if isinstance(packet, Mapping) else set()
            if text(target.get("source_evidence_id")) not in evidence_ids:
                errors.append(f"target_evidence_missing:{row.get('case_id')}")
    return errors


def _provider_artifact_errors() -> list[str]:
    errors: list[str] = []
    for name in ("regression-pass1.json", "regression-pass2.json", "regression-pass3.json", "challenge-pass1.json", "challenge-pass2.json", "challenge-pass3.json"):
        document = read_json(OUT / name, {}) or {}
        if GOLD_KEYS.intersection(_keys(document)):
            errors.append(f"gold_in_{name}")
        if name.endswith("-pass2.json") or name.endswith("-pass3.json"):
            if {"semantic_record", "revised_semantic_record"}.intersection(_keys(document)):
                errors.append(f"complete_record_in_{name}")
    return errors


def _selector_errors() -> list[str]:
    errors: list[str] = []
    preservation = read_json(OUT / "semantic-preservation-audit.json", {}) or {}
    if int(preservation.get("selection_preservation_failures") or 0) != 0:
        errors.append("selector_copy_drift")
    safety = read_json(OUT / "storage-safety-audit.json", {}) or {}
    for key in ("production_person_creations", "canonical_writes", "alias_mutations", "profile_mutations", "substring_candidate_creation", "related_person_promotions", "attribute_person_promotions", "collective_person_promotions", "undeclared_patch_mutations"):
        if safety.get(key) != 0:
            errors.append(f"unsafe_{key}")
    if safety.get("protected_inputs_unchanged") is not True:
        errors.append("protected_inputs_changed")
    review = read_json(OUT / "challenge-human-review.json", {}) or {}
    if len(review.get("records", []) or []) != 20:
        errors.append("challenge_review_bundle_incomplete")
    if review.get("historical_correctness") != "pending_external_review":
        errors.append("challenge_review_status")
    return errors


def _transport_errors() -> list[str]:
    errors: list[str] = []
    preflight = read_json(OUT / "provider-preflight.json", {}) or {}
    if preflight and preflight.get("attempts") != 1:
        errors.append("preflight_not_one_shot")
    if preflight and preflight.get("model") != MODEL:
        errors.append("preflight_model_changed")
    transport = read_json(OUT / "transport.json", {}) or {}
    if transport.get("model") != MODEL:
        errors.append("transport_model_changed")
    if int(transport.get("new_live_attempts") or 0) > MAX_PROVIDER_ATTEMPTS:
        errors.append("provider_attempt_budget")
    for stage, prompt in PROMPT_VERSIONS.items():
        if text((transport.get("prompt_versions") or {}).get(stage)) != prompt:
            errors.append(f"transport_prompt_changed:{stage}")
    return errors


def validate(*, preflight: bool = False) -> dict[str, Any]:
    errors: list[str] = []
    errors.extend(_errors())
    errors.extend(_selection_errors())
    errors.extend(_freeze_errors())
    if not preflight:
        required = [
            "architecture-freeze.json", "provider-preflight.json", "regression-selection.json",
            "challenge-selection.json", "challenge-selection-hash.json", "case-packets.json",
            "regression-pass1.json", "regression-routing.json", "regression-pass2.json",
            "regression-pass3.json", "regression-final.json", "regression-evaluation.json",
            "challenge-pass1.json", "challenge-routing.json", "challenge-pass2.json",
            "challenge-pass3.json", "challenge-final.json", "challenge-story-consistency.json",
            "challenge-human-review.json", "challenge-human-review.md", "semantic-preservation-audit.json",
            "storage-safety-audit.json", "metrics.json", "transport.json", "validation-summary.json", "recommendation.json",
        ]
        for name in required:
            if not (OUT / name).is_file():
                errors.append(f"missing_artifact:{name}")
        errors.extend(_packet_errors())
        errors.extend(_provider_artifact_errors())
        errors.extend(_selector_errors())
        errors.extend(_transport_errors())
        metrics = read_json(OUT / "metrics.json", {}) or {}
        for key in ("production_person_creations", "canonical_writes", "alias_mutations", "profile_mutations", "selector_copy_drift", "undeclared_patch_mutations", "substring_candidate_creation", "related_person_promotions", "attribute_person_promotions", "collective_person_promotions"):
            if metrics.get(key) != 0:
                errors.append(f"metrics_{key}")
        if metrics.get("candidate_only") is not True or metrics.get("canonical_write_back") is not False:
            errors.append("metrics_storage_contract")
        if metrics.get("no_full_188_story_live_run") is not True:
            errors.append("full_story_live_run")
        summary = read_json(OUT / "validation-summary.json", {}) or {}
        if summary.get("candidate_only") is not True or summary.get("canonical_write_back") is not False:
            errors.append("summary_storage_contract")
    return {
        "schema": "sfh2-a0r-l-validation-v1",
        "preflight": preflight,
        "valid": not errors,
        "errors": sorted(set(errors)),
        "baseline_commit": BASELINE_COMMIT,
        "challenge_case_count": (read_json(CHALLENGE_SELECTION_PATH, {}) or {}).get("case_count", 0),
        "candidate_only": True,
        "canonical_write_back": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--preflight", action="store_true")
    args = parser.parse_args()
    result = validate(preflight=args.preflight)
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if result["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
