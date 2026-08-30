#!/usr/bin/env python3
"""Validate the SFH2R manual semantic-repair projection.

Validation is deliberately mechanical.  The reviewed authority file is the
source of semantic expectations; this validator checks that those records are
present in the active derived indexes and that no protected/canonical input
was written.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import manual_semantic_authority as authority  # noqa: E402
from materialize_sfh2r import (  # noqa: E402
    ALIASES,
    CANDIDATE_PROFILE,
    HDA2_OVERLAY,
    OLD_ENTITY,
    OLD_GRAPH,
    OLD_OBSERVATIONS,
    OLD_RELATIONS,
    OUT,
    PEOPLE,
    PROFILE,
    file_hash,
    records,
)


REQUIRED = (
    "repair-manifest.json",
    "alias-before-after.json",
    "profile-before-after.json",
    "occurrence-before-after.json",
    "candidate-registry-repairs.json",
    "graph-role-reprojection.json",
    "offline-replay-effects.json",
    "regression-results.json",
    "remaining-known-risk.json",
    "metrics.json",
)


def _add(errors: list[str], condition: bool, message: str) -> None:
    if not condition:
        errors.append(message)


def _forms(profile: Mapping[str, Any]) -> set[tuple[str, str]]:
    identity = profile.get("identity") or {}
    result: set[tuple[str, str]] = set()
    for field, form_type in (
        ("aliases", "alias"),
        ("courtesy_names", "courtesy_name"),
        ("titles", "title"),
        ("observed_surfaces", "observed_surface"),
    ):
        for value in identity.get(field, []) or []:
            if value not in (None, ""):
                result.add((form_type, str(value)))
    return result


def _canonical_paths() -> tuple[Path, ...]:
    return (
        ROOT / "data/people.json",
        ROOT / "data/relations.json",
        ROOT / "data/personStory.json",
        ROOT / "data/annotation/story-temporal-anchors-h0a.json",
        ROOT / "data/annotation/story-temporal-evidence-h0a.json",
        ROOT / "data/annotation/kinship-h0b1.json",
        ROOT / "data/annotation/marriages-h0b1.json",
        ROOT / "data/annotation/office-tenures-h0b1.json",
    )


def validate() -> dict[str, Any]:
    errors: list[str] = []
    missing = [name for name in REQUIRED if not (OUT / name).is_file()]
    errors.extend(f"missing_output:{name}" for name in missing)
    if missing:
        return {"schema": "sfh2r-validation-v1", "valid": False, "errors": sorted(errors), "candidate_only": True, "canonical_write_back": False}

    manifest = json.loads((OUT / "repair-manifest.json").read_text(encoding="utf-8"))
    alias_audit = json.loads((OUT / "alias-before-after.json").read_text(encoding="utf-8"))
    profile_audit = json.loads((OUT / "profile-before-after.json").read_text(encoding="utf-8"))
    occurrence_audit = json.loads((OUT / "occurrence-before-after.json").read_text(encoding="utf-8"))
    candidates = json.loads((OUT / "candidate-registry-repairs.json").read_text(encoding="utf-8"))
    roles = json.loads((OUT / "graph-role-reprojection.json").read_text(encoding="utf-8"))
    replay = json.loads((OUT / "offline-replay-effects.json").read_text(encoding="utf-8"))
    regressions = json.loads((OUT / "regression-results.json").read_text(encoding="utf-8"))
    metrics = json.loads((OUT / "metrics.json").read_text(encoding="utf-8"))

    for name, document in (
        ("manifest", manifest), ("alias", alias_audit), ("profile", profile_audit),
        ("occurrence", occurrence_audit), ("candidates", candidates), ("roles", roles),
        ("replay", replay), ("regressions", regressions), ("metrics", metrics),
    ):
        _add(errors, document.get("candidate_only") is True, f"{name}_candidate_only")
        _add(errors, document.get("canonical_write_back") is False, f"{name}_canonical_write_back")

    _add(errors, manifest.get("live_llm_calls") == 0, "live_llm_calls")
    _add(errors, manifest.get("authority") == authority.authority_reference(), "authority_reference")
    _add(errors, manifest.get("authority_sha256") == file_hash(authority.AUTHORITY_PATH), "authority_hash")

    aliases = json.loads(ALIASES.read_text(encoding="utf-8"))
    active_aliases = {
        str(row.get("alias_id")): row
        for row in records(aliases, "aliases")
        if str(row.get("alias_id") or "")
    }
    audited_aliases = {
        str(row.get("alias_id")): row
        for row in alias_audit.get("records", []) or []
        if str(row.get("alias_id") or "")
    }
    for repair in authority.alias_repairs():
        alias_id = str(repair.get("alias_id") or "")
        row = active_aliases.get(alias_id)
        audit_row = audited_aliases.get(alias_id, {})
        _add(errors, row is not None, f"alias_missing:{alias_id}")
        _add(errors, audit_row.get("after") == row, f"alias_audit_after_mismatch:{alias_id}")
        if not row:
            continue
        expected_surface = str(repair.get("corrected_surface") or repair.get("surface") or "")
        _add(errors, str(row.get("surface")) == expected_surface, f"alias_surface:{alias_id}")
        for key in ("corrected_resolution_mode", "corrected_status"):
            if repair.get(key):
                _add(errors, row.get(key.removeprefix("corrected_")) == repair.get(key), f"alias_{key}:{alias_id}")
        current_evidence = {
            str(item.get("evidence_id"))
            for item in row.get("source_evidence", []) or []
            if isinstance(item, Mapping) and str(item.get("evidence_id") or "")
        }
        removed = {str(value) for value in repair.get("remove_evidence_ids", []) or []}
        _add(errors, removed.isdisjoint(current_evidence), f"rejected_evidence_present:{alias_id}")
        keep = {str(value) for value in repair.get("keep_evidence_ids", []) or []}
        _add(errors, keep.issubset(current_evidence), f"retained_evidence_missing:{alias_id}")
        replacement = {str(value) for value in repair.get("replacement_evidence_ids", []) or []}
        _add(errors, replacement.issubset(current_evidence), f"replacement_evidence_missing:{alias_id}")
        trace = row.get("sfh2r_manual_repair") or {}
        _add(errors, trace.get("alias_id") == alias_id, f"repair_trace_missing:{alias_id}")

    # Safe W4 forms are explicitly reviewed positive controls.  They must not
    # disappear as a side effect of filtering the high-risk forms.
    for safe in authority.load_authority().get("audited_safe_w4_aliases", []) or []:
        found = any(
            str(row.get("surface")) == str(safe.get("surface"))
            and str(safe.get("person_id")) in {str(value) for value in row.get("person_ids", []) or []}
            and row.get("source_evidence")
            for row in active_aliases.values()
        )
        _add(errors, found, f"safe_w4_alias_missing:{safe.get('surface')}")

    profiles = json.loads(PROFILE.read_text(encoding="utf-8"))
    candidate_profiles = json.loads(CANDIDATE_PROFILE.read_text(encoding="utf-8"))
    all_profiles = [*records(profiles, "records"), *records(candidate_profiles, "records")]
    known_bad = {
        "鄧攸": {"潁", "石勒", "茂英", "攸之甥"},
        "王羲之": {"孫興公", "支道林"},
        "郭象": {"子少"},
        "趙至": {"桓亮", "桓景真"},
    }
    for profile in all_profiles:
        name = str(profile.get("canonical_name") or "")
        bad = {surface for _, surface in _forms(profile)} & known_bad.get(name, set())
        for surface in sorted(bad):
            errors.append(f"known_profile_contamination:{name}:{surface}")
        for provenance in (profile.get("identity") or {}).get("form_provenance", []) or []:
            _add(errors, all(str(provenance.get(key) or "") for key in ("surface", "form_type", "person_id", "occurrence_id", "identity_observation_id", "evidence_ref", "identity_status", "identity_basis")), f"profile_provenance_incomplete:{name}")
    profile_integrity = profile_audit.get("active_profile_integrity_audit") or {}
    _add(errors, not profile_integrity.get("known_contamination_remaining"), "profile_integrity_known_contamination")
    _add(errors, not profile_integrity.get("known_regression_failures"), "profile_integrity_known_regression")
    for profile in all_profiles:
        person_id = str(profile.get("person_id") or "")
        _add(errors, not person_id.startswith("sfh2r-manual-candidate-"), f"profile_production_namespace:{person_id}")

    occurrence_rows = {
        str(row.get("observation_id")): row
        for row in occurrence_audit.get("records", []) or []
        if str(row.get("observation_id") or "")
    }
    for observation_id, repair in authority.occurrence_repairs().items():
        row = occurrence_rows.get(observation_id)
        _add(errors, row is not None, f"occurrence_missing:{observation_id}")
        if not row:
            continue
        after = row.get("after") or {}
        action = str(repair.get("action") or "")
        if repair.get("replacement_display_name"):
            _add(errors, after.get("previous_identity_decision", {}).get("candidate_display_name") == repair.get("replacement_display_name"), f"occurrence_replacement_name:{observation_id}")
            _add(errors, str(after.get("previous_candidate_person_id") or "").startswith("sfh2r-manual-candidate-"), f"occurrence_replacement_namespace:{observation_id}")
        if action.startswith("suppress_") and not repair.get("replacement_display_name"):
            _add(errors, after.get("classification") == "non_person", f"occurrence_non_person:{observation_id}")
            _add(errors, not after.get("previous_candidate_person_id"), f"occurrence_candidate_leak:{observation_id}")
        if action == "retain_personhood_but_reclassify_network_role":
            replacement = repair.get("replacement") or {}
            _add(errors, after.get("network_role") == replacement.get("network_role"), f"occurrence_role:{observation_id}")
            _add(errors, after.get("core_story_graph_eligible") is False, f"occurrence_core_graph_role:{observation_id}")

    candidate_ids = {str(row.get("candidate_person_id") or "") for row in candidates.get("records", []) or []}
    _add(errors, len(candidate_ids) == len(candidates.get("records", []) or []), "candidate_ids_unique")
    _add(errors, all(value and not value.startswith("person-") for value in candidate_ids), "production_candidate_id_allocated")
    _add(errors, all(row.get("evidence_ids") for row in candidates.get("records", []) or []), "candidate_evidence_missing")
    _add(errors, not regressions.get("failed_cases"), "manual_regressions_failed")
    _add(errors, regressions.get("passed_count") == regressions.get("case_count"), "manual_regression_count")
    _add(errors, replay.get("old_sfh2_artifacts_mutated") is False, "old_sfh2_artifact_mutation")
    _add(errors, replay.get("mode") == "offline_mechanical_manual_overlay_no_llm", "replay_mode")

    xe0_path = ROOT / "data/generated/hdb2-xe0/live/20260826T-HDB2-XE0-02/manifest.json"
    xe0 = json.loads(xe0_path.read_text(encoding="utf-8")) if xe0_path.is_file() else {}
    transition = manifest.get("authorized_derived_profile_transition") or {}
    _add(errors, xe0.get("protected_hashes_before") == xe0.get("protected_hashes_after"), "xe0_immutable_hash_transition")
    _add(errors, transition.get("immutable_protected_hashes_unchanged") is True, "xe0_transition_protection")
    _add(errors, transition.get("after_authorized_derived_projection_hashes") == xe0.get("authorized_derived_projection_hashes"), "xe0_transition_manifest_mismatch")
    _add(errors, (xe0.get("authorized_derived_projection_hashes") or {}).get("data/derived/hdb2-f-person-knowledge.json") == file_hash(PROFILE), "xe0_profile_transition_hash")

    # The repair overlay is an additive projection.  A previous HDA2
    # suppression is not allowed to return through the new candidate registry.
    hda2 = json.loads(HDA2_OVERLAY.read_text(encoding="utf-8")) if HDA2_OVERLAY.is_file() else []
    suppressed = {
        (authority.normalize_form(row.get("target_surface")), str(row.get("person_id") or ""))
        for row in (hda2 if isinstance(hda2, list) else hda2.get("records", []) or [])
        if isinstance(row, Mapping) and row.get("action") == "suppress_claim"
    }
    reintroduced = [
        row for row in candidates.get("records", []) or []
        if (authority.normalize_form(row.get("surface")), str(row.get("person_id") or "")) in suppressed
    ]
    _add(errors, not reintroduced, "hda2_suppressed_identity_reentry")

    protected = manifest.get("protected_canonical_hashes") or {}
    for path in _canonical_paths():
        relative = path.relative_to(ROOT).as_posix()
        if relative in protected:
            _add(errors, protected[relative] == file_hash(path), f"protected_canonical_hash:{relative}")
    for relative, expected in (manifest.get("input_artifacts") or {}).items():
        path = ROOT / relative if relative.startswith("data/") else None
        # Input-artifact keys are logical labels, so only compare actual file
        # paths for the immutable SFH2 witnesses below.
        if path is not None and path.is_file() and relative in {"data/generated/sfh2/candidate-observations.json", "data/generated/sfh2/relation-endpoint-reprojection.json", "data/generated/sfh2/entity-consolidation.json", "data/generated/sfh2/consolidated-graph.json", "data/generated/hda2/repair-overlay.json", "data/generated/hdb2-xe0/live/20260826T-HDB2-XE0-02/manifest.json"}:
            _add(errors, expected == file_hash(path), f"input_artifact_hash:{relative}")

    output_hashes = manifest.get("output_hashes") or {}
    for name, expected in output_hashes.items():
        _add(errors, expected == file_hash(OUT / name), f"output_hash:{name}")

    return {
        "schema": "sfh2r-validation-v1",
        "valid": not errors,
        "errors": sorted(set(errors)),
        "manual_regression_count": regressions.get("case_count", 0),
        "candidate_registry_count": len(candidates.get("records", []) or []),
        "profile_form_count_after": profile_audit.get("profile_form_count_after"),
        "canonical_hashes_checked": len(protected),
        "candidate_only": True,
        "canonical_write_back": False,
    }


def main() -> int:
    result = validate()
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if result["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
