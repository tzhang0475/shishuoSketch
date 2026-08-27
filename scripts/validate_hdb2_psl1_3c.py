#!/usr/bin/env python3
"""Validate the isolated HDB2-PSL1.3C boundary repair.

This validator is deliberately offline.  PSL1.3C replays the frozen 1.3B
responses after rebuilding the candidate-only profile projections; it does
not perform a new semantic run.  The two saved invalid 1.3B responses are
kept as audit evidence and are accepted here only when the repaired graph
fails closed instead of promoting their old result.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import hdb2_psl1_3c_common as layer  # noqa: E402
import hdb2_psl1_3b_common as prior_b  # noqa: E402
import rebuild_hdb2_f_profiles as profile_builder  # noqa: E402
import run_hdb2_psl1_3c as runner  # noqa: E402


DEFAULT_RUN = layer.GENERATED / "live/20260828T-HDB2-PSL1-3C-REPLAY-12"
EXPECTED_REPLAY_FAILURES = {
    ("23-rendan-049", "surface_structure_not_in_hypotheses"),
    ("09-pinzao-018", "accepted_candidate_key_invalid"),
    ("09-pinzao-018", "literal_null_invalid:accepted_candidate_key"),
}


def _load(path: Path, default: Any = None) -> Any:
    return layer.read_json(path, default)


def _records(path: Path, key: str = "records") -> list[dict[str, Any]]:
    document = _load(path, {}) or {}
    return [dict(row) for row in document.get(key, []) or [] if isinstance(row, Mapping)]


def _case(final: Mapping[str, Any], story_id: str, surface: str) -> dict[str, Any] | None:
    return next(
        (
            dict(row)
            for row in final.get("records", []) or []
            if str(row.get("story_id")) == story_id and str(row.get("surface")) == surface
        ),
        None,
    )


def _profile_validation(errors: list[str]) -> dict[str, Any]:
    existing = _load(profile_builder.EXISTING_PROFILE, {}) or {}
    candidates = _load(profile_builder.CANDIDATE_PROFILE, {}) or {}
    audit = _load(profile_builder.AUDIT_PATH, {}) or {}
    for name, document in (("existing", existing), ("candidate", candidates)):
        if document.get("candidate_only") is not True or document.get("canonical_write_back") is not False:
            errors.append(f"{name}_profile_safety_flags_invalid")
    if audit.get("candidate_only") is not True or audit.get("canonical_write_back") is not False:
        errors.append("profile_audit_safety_flags_invalid")
    if audit.get("forms_without_identity_provenance", 0):
        errors.append("profile_forms_without_identity_provenance")
    if audit.get("orphan_profile_forms", 0):
        errors.append("orphan_profile_forms")
    if audit.get("ambiguous_forms"):
        errors.append("ambiguous_profile_forms")
    if audit.get("known_regression_failures"):
        errors.append("profile_known_regression_failed")
    if audit.get("known_contamination_remaining"):
        errors.append("known_profile_contamination_remaining")

    # Rebuild in memory as a deterministic integrity check.  This does not
    # rewrite either candidate profile or the historical audit's old-form
    # comparison fields.
    expected_existing, expected_candidates = profile_builder.build_documents()
    if expected_existing != existing or expected_candidates != candidates:
        errors.append("profile_documents_not_reproducible")

    return {
        "profile_form_count": audit.get("profile_form_count", 0),
        "forms_with_provenance": audit.get("forms_with_provenance", 0),
        "forms_without_identity_provenance": audit.get("forms_without_identity_provenance", 0),
        "contaminated_profile_forms_detected": audit.get("contaminated_profile_forms_detected", 0),
        "contaminated_profile_forms_removed": audit.get("contaminated_profile_forms_removed", 0),
        "cross_person_surface_conflicts": audit.get("cross_person_surface_conflicts", 0),
        "known_regression_failures": list(audit.get("known_regression_failures", []) or []),
    }


def _validate_run(run_dir: Path, errors: list[str]) -> dict[str, Any]:
    manifest = _load(run_dir / "manifest.json", {}) or {}
    selection = _load(run_dir / "selection.json", {}) or {}
    frozen = layer.freeze_selection()
    if selection != frozen:
        errors.append("frozen_selection_changed")
    if manifest.get("candidate_only") is not True or manifest.get("canonical_write_back") is not False:
        errors.append("manifest_safety_flags_invalid")
    if manifest.get("replayed_without_api") is not True or manifest.get("api_calls_this_run") != 0:
        errors.append("replay_not_offline")
    expected_hashes = runner._c_protected_hashes()
    if manifest.get("protected_hashes_before") != manifest.get("protected_hashes_after"):
        errors.append("protected_hashes_changed")
    if manifest.get("protected_hashes_after") != expected_hashes:
        errors.append("protected_hashes_do_not_match_current")

    failures = _records(run_dir / "validation-failures.json")
    failure_pairs = {
        (str(row.get("story_id")), str(error))
        for row in failures
        for error in row.get("errors", []) or []
    }
    unexpected = sorted(failure_pairs - EXPECTED_REPLAY_FAILURES)
    if unexpected:
        errors.extend(f"unexpected_replay_failure:{story}:{reason}" for story, reason in unexpected)

    graph = _load(run_dir / "graph.json", {}) or {}
    structures = {
        str(row.get("mention_id")): row
        for row in _records(run_dir / "reference-structures.json")
        if row.get("mention_id")
    }
    cases = {
        str(row.get("mention_id")): row
        for row in graph.get("cases", []) or []
        if row.get("mention_id")
    }
    if set(structures) != set(cases):
        errors.append("reference_structure_case_coverage_invalid")
    for mention_id, structure in structures.items():
        if structure.get("candidate_only") is not True or structure.get("canonical_write_back") is not False:
            errors.append(f"reference_structure_safety_invalid:{mention_id}")
        if structure.get("surface_structure") in layer.OFFICE_ROLE_STRUCTURES:
            if structure.get("holder") and not structure.get("holder_assignment_evidence_ids"):
                errors.append(f"holder_with_empty_evidence:{mention_id}")
            if not structure.get("holder"):
                case = cases.get(mention_id, {})
                for predicate in case.get("deterministic_predicates", []) or []:
                    if predicate.get("predicate") == "OfficeCompatible" and (
                        float(predicate.get("value", 0.5)) > 0.5 or predicate.get("evidence_ids")
                    ):
                        errors.append(f"ungrounded_office_compatible:{mention_id}")

    final = _load(run_dir / "decisions-final.json", {}) or {}
    if final.get("candidate_only") is not True or final.get("canonical_write_back") is not False:
        errors.append("final_safety_flags_invalid")
    final_rows = [dict(row) for row in final.get("records", []) or []]
    for row in final_rows:
        state = str(row.get("result_state") or "")
        if state in {"stable_entity_resolved", "local_candidate_resolved"} and row.get("reviewer_invalid_demoted"):
            errors.append(f"invalid_reviewer_left_resolution:{row.get('mention_id')}")

    # The two known bad B responses must fail closed in C.  The first is now
    # structurally uncertain; the second is prevented from remaining a stable
    # identity even though its saved reviewer payload is the literal string
    # "null".
    bad_review = _case(final, "09-pinzao-018", "潁")
    if bad_review and bad_review.get("result_state") in {"stable_entity_resolved", "local_candidate_resolved"}:
        errors.append("invalid_reviewer_regression_not_demoted")
    bad_surface = _case(final, "09-pinzao-018", "潁")
    if bad_surface and bad_surface.get("top_candidate") == "鄧攸":
        errors.append("潁_wrong_identity_survived")
    for story_id, surface, forbidden in (
        ("09-pinzao-088", "桓", {"朱伺", "卞範之"}),
        ("23-rendan-049", "桓", {"朱伺", "卞範之"}),
    ):
        row = _case(final, story_id, surface)
        if row and row.get("result_state") in {"stable_entity_resolved", "local_candidate_resolved"} and row.get("top_candidate") in forbidden:
            errors.append(f"single_character_wrong_identity:{story_id}")

    return {
        "run_dir": str(run_dir.relative_to(ROOT)),
        "case_count": len(cases),
        "final_count": len(final_rows),
        "saved_validation_failures": len(failures),
        "unexpected_validation_failures": unexpected,
        "reviewer_invalid_demotions": sum(bool(row.get("reviewer_invalid_demoted")) for row in final_rows),
        "state_counts": {
            state: sum(str(row.get("result_state")) == state for row in final_rows)
            for state in sorted({str(row.get("result_state")) for row in final_rows})
        },
    }


def validate(run_dir: Path | None = None) -> dict[str, Any]:
    errors: list[str] = []
    profile_metrics = _profile_validation(errors)
    prior = prior_b.reference_regression_records()
    if prior.get("all_pass") is not True:
        errors.append("prior_psl1_3b_reference_regression_failed")
    c_regressions = layer.reference_regression_records()
    if c_regressions.get("all_pass") is not True:
        errors.append("psl1_3c_reference_regression_failed")
    details: dict[str, Any] = {
        "candidate_only": True,
        "canonical_write_back": False,
        "profile_integrity": profile_metrics,
        "prior_b_reference_regressions": prior,
        "reference_regressions": c_regressions,
        "protected_profile_projections_are_rebuilt": True,
    }
    if run_dir is not None:
        details.update(_validate_run(run_dir, errors))
    return {"valid": not errors, "errors": sorted(set(errors)), **details}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", type=Path, default=DEFAULT_RUN)
    args = parser.parse_args()
    run_dir = args.run_dir if args.run_dir.is_absolute() else ROOT / args.run_dir
    result = validate(run_dir)
    if run_dir.is_dir():
        layer.write_json(run_dir / "validation.json", result)
        summary = _load(run_dir / "validation-summary.json", {}) or {}
        summary.update({
            "schema": "hdb2-psl1-3c-validation-summary-v1",
            "valid": result.get("valid") is True,
            "validator_errors": list(result.get("errors", []) or []),
            "candidate_only": True,
            "canonical_write_back": False,
        })
        layer.write_json(run_dir / "validation-summary.json", summary)
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if result.get("valid") else 1


if __name__ == "__main__":
    raise SystemExit(main())
