#!/usr/bin/env python3
"""Materialize the reviewed SFH2R semantic-repair overlay.

The authority file is the semantic input to this stage.  This module never
decides whether a historical reading is correct: it applies the already
reviewed alias/occurrence/role records, validates their coordinates, and
builds an isolated candidate-only audit projection.  In particular, it does
not rerun SFH1/SFH2 model calls and it does not rewrite the old SFH2 output.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Mapping, Sequence

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import manual_semantic_authority as authority  # noqa: E402
import sfh2r_contract  # noqa: E402
from sfh2 import common as sfh2_common  # noqa: E402


OUT = ROOT / "data/generated/sfh2r"
ALIASES = ROOT / "data/aliases.json"
PEOPLE = ROOT / "data/people.json"
OLD_OBSERVATIONS = ROOT / "data/generated/sfh2/candidate-observations.json"
OLD_GRAPH = ROOT / "data/generated/sfh2/consolidated-graph.json"
OLD_RELATIONS = ROOT / "data/generated/sfh2/relation-endpoint-reprojection.json"
OLD_ENTITY = ROOT / "data/generated/sfh2/entity-consolidation.json"
PROFILE = ROOT / "data/derived/hdb2-f-person-knowledge.json"
CANDIDATE_PROFILE = ROOT / "data/derived/hdb2-f-candidate-person-knowledge.json"
PROFILE_AUDIT = ROOT / "data/derived/hdb2-f-profile-integrity-audit.json"
HDA2_OVERLAY = ROOT / "data/generated/hda2/repair-overlay.json"


def read(path: Path, default: Any = None) -> Any:
    if not path.is_file():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def write(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def file_hash(path: Path) -> str | None:
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None


def value_hash(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def records(document: Any, *keys: str) -> list[dict[str, Any]]:
    if isinstance(document, list):
        return [dict(row) for row in document if isinstance(row, Mapping)]
    if not isinstance(document, Mapping):
        return []
    for key in keys:
        rows = document.get(key)
        if isinstance(rows, list):
            return [dict(row) for row in rows if isinstance(row, Mapping)]
    return []


def _git_file(relative: str) -> tuple[bytes | None, str]:
    """Read the pre-repair committed witness for the one-time audit.

    The resulting bytes are stored in the audit artifact.  Runtime validation
    never calls git and therefore does not depend on repository history.
    """
    try:
        result = subprocess.run(
            ["git", "show", f"HEAD:{relative}"],
            cwd=ROOT,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
    except (OSError, subprocess.CalledProcessError):
        return None, "unavailable"
    return result.stdout, "git:HEAD"


def _before_document(path: Path, audit_name: str) -> tuple[Any, str]:
    previous = read(OUT / audit_name, {}) or {}
    if isinstance(previous, Mapping) and previous.get("before_document") is not None:
        return previous.get("before_document"), "sfh2r-audit"
    raw, source = _git_file(path.relative_to(ROOT).as_posix())
    if raw is not None:
        try:
            return json.loads(raw.decode("utf-8")), source
        except (UnicodeDecodeError, json.JSONDecodeError):
            pass
    return read(path, {}), "current-fallback"


def _alias_rows(document: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        str(row.get("alias_id")): dict(row)
        for row in records(document, "aliases")
        if str(row.get("alias_id") or "")
    }


def _alias_audit() -> dict[str, Any]:
    """Build a compact before/after audit of exactly the reviewed aliases."""
    previous = read(OUT / "alias-before-after.json", {}) or {}
    before, before_source = _before_document(ALIASES, "alias-before-after.json")
    after = read(ALIASES, {}) or {}
    before_file_sha256 = previous.get("before_file_sha256") if isinstance(previous, Mapping) else None
    if not before_file_sha256:
        raw, _ = _git_file(ALIASES.relative_to(ROOT).as_posix())
        if raw is not None:
            before_file_sha256 = hashlib.sha256(raw).hexdigest()
    old_rows = _alias_rows(before if isinstance(before, Mapping) else {})
    new_rows = _alias_rows(after if isinstance(after, Mapping) else {})
    rows: list[dict[str, Any]] = []
    for repair in authority.alias_repairs():
        alias_id = str(repair.get("alias_id") or "")
        rows.append({
            "alias_id": alias_id,
            "before": old_rows.get(alias_id),
            "after": new_rows.get(alias_id),
            "manual_authority": repair,
            "before_evidence_ids": sorted(
                str(row.get("evidence_id"))
                for row in (old_rows.get(alias_id, {}).get("source_evidence", []) or [])
                if isinstance(row, Mapping) and str(row.get("evidence_id") or "")
            ),
            "after_evidence_ids": sorted(
                str(row.get("evidence_id"))
                for row in (new_rows.get(alias_id, {}).get("source_evidence", []) or [])
                if isinstance(row, Mapping) and str(row.get("evidence_id") or "")
            ),
        })
    return {
        "schema": "sfh2r-alias-before-after-v1",
        "authority": authority.authority_reference(),
        "before_source": before_source,
        "before_file_sha256": before_file_sha256,
        "before_document": before,
        "before_registry_sha256": value_hash(before),
        "after_file_sha256": file_hash(ALIASES),
        "after_registry_sha256": value_hash(after),
        "records": rows,
        "safe_w4_aliases": authority.load_authority().get("audited_safe_w4_aliases", []),
        "candidate_only": True,
        "canonical_write_back": False,
    }


def _profile_forms(profile: Mapping[str, Any]) -> set[tuple[str, str, str]]:
    identity = profile.get("identity") or {}
    result: set[tuple[str, str, str]] = set()
    for field, form_type in (
        ("aliases", "alias"),
        ("courtesy_names", "courtesy_name"),
        ("titles", "title"),
        ("observed_surfaces", "observed_surface"),
    ):
        for surface in identity.get(field, []) or []:
            if surface not in (None, ""):
                result.add((str(profile.get("person_id") or ""), form_type, str(surface)))
    return result


def _profile_audit() -> dict[str, Any]:
    previous = read(OUT / "profile-before-after.json", {}) or {}
    if isinstance(previous, Mapping) and previous.get("before_document") is not None:
        before, before_source = previous.get("before_document"), "sfh2r-audit"
    else:
        before, before_source = _before_document(PROFILE, "profile-before-after.json")
    if isinstance(previous, Mapping) and previous.get("before_candidate_document") is not None:
        before_candidates, before_candidate_source = previous.get("before_candidate_document"), "sfh2r-audit"
    else:
        before_candidates, before_candidate_source = _before_document(CANDIDATE_PROFILE, "profile-before-after.json")
    after = read(PROFILE, {}) or {}
    after_candidates = read(CANDIDATE_PROFILE, {}) or {}
    target_ids = sorted({
        str(row.get("current_person_id") or "")
        for row in authority.alias_repairs()
        if str(row.get("current_person_id") or "")
    })
    old_records = records(before, "records")
    new_records = records(after, "records")
    old_by_id = {str(row.get("person_id")): row for row in old_records}
    new_by_id = {str(row.get("person_id")): row for row in new_records}
    changed: list[dict[str, Any]] = []
    for person_id in target_ids:
        old = old_by_id.get(person_id, {})
        new = new_by_id.get(person_id, {})
        old_forms = sorted(_profile_forms(old))
        new_forms = sorted(_profile_forms(new))
        changed.append({
            "person_id": person_id,
            "before": old,
            "after": new,
            "forms_removed": [list(row) for row in sorted(set(old_forms) - set(new_forms))],
            "forms_added": [list(row) for row in sorted(set(new_forms) - set(old_forms))],
            "manual_authority_records": [
                row for row in authority.alias_repairs()
                if str(row.get("current_person_id") or "") == person_id
            ],
        })
    all_old = set().union(*(_profile_forms(row) for row in [*old_records, *records(before_candidates, "records")])) if (old_records or records(before_candidates, "records")) else set()
    all_new = set().union(*(_profile_forms(row) for row in [*new_records, *records(after_candidates, "records")])) if (new_records or records(after_candidates, "records")) else set()
    return {
        "schema": "sfh2r-profile-before-after-v1",
        "authority": authority.authority_reference(),
        "before_source": before_source,
        "before_candidate_source": before_candidate_source,
        "before_document": before,
        "before_candidate_document": before_candidates,
        "before_profile_sha256": value_hash(before),
        "after_profile_sha256": file_hash(PROFILE),
        "before_candidate_profile_sha256": value_hash(before_candidates),
        "after_candidate_profile_sha256": file_hash(CANDIDATE_PROFILE),
        "target_person_ids": target_ids,
        "records": changed,
        "profile_forms_removed": [list(row) for row in sorted(all_old - all_new)],
        "profile_forms_added": [list(row) for row in sorted(all_new - all_old)],
        "profile_form_count_before": len(all_old),
        "profile_form_count_after": len(all_new),
        "active_profile_integrity_audit": read(PROFILE_AUDIT, {}) or {},
        "candidate_only": True,
        "canonical_write_back": False,
    }


def _observation_audit() -> dict[str, Any]:
    old_doc = read(OLD_OBSERVATIONS, {}) or {}
    old_rows = {
        str(row.get("observation_id")): dict(row)
        for row in records(old_doc, "records")
        if str(row.get("observation_id") or "")
    }
    repaired: list[dict[str, Any]] = []
    missing: list[str] = []
    for observation_id, repair in sorted(authority.occurrence_repairs().items()):
        before = old_rows.get(observation_id)
        if before is None:
            missing.append(observation_id)
            continue
        after = authority.apply_sfh2_observation(before)
        repaired.append({
            "observation_id": observation_id,
            "story_id": repair.get("story_id"),
            "surface": repair.get("surface"),
            "before": before,
            "after": after,
            "manual_authority": repair,
        })
    return {
        "schema": "sfh2r-occurrence-before-after-v1",
        "authority": authority.authority_reference(),
        "source_artifact": "data/generated/sfh2/candidate-observations.json",
        "source_artifact_sha256": file_hash(OLD_OBSERVATIONS),
        "records": repaired,
        "missing_observation_ids": missing,
        "manual_repair_count": len(repaired),
        "candidate_only": True,
        "canonical_write_back": False,
    }


def _candidate_registry(observations: Mapping[str, Any]) -> dict[str, Any]:
    observation_by_id = {
        str(row.get("observation_id")): (row.get("before") or row.get("after") or row)
        for row in records(observations, "records")
        if str(row.get("observation_id") or "")
    }
    rows: list[dict[str, Any]] = []
    for repair in authority.occurrence_repairs().values():
        name = str(repair.get("replacement_display_name") or "")
        if not name:
            continue
        candidate_id = authority._manual_candidate_id(name)
        source_row = observation_by_id.get(str(repair.get("observation_id")), {})
        evidence_ids = sorted({
            str(value)
            for value in (
                repair.get("supporting_evidence_ids")
                or source_row.get("source_evidence_ids")
                or []
            )
            if str(value)
        })
        rows.append({
            "candidate_person_id": candidate_id,
            "display_name": name,
            "observation_ids": [str(repair.get("observation_id"))],
            "story_ids": [str(repair.get("story_id"))],
            "surface": repair.get("surface"),
            "evidence_ids": evidence_ids,
            "network_role": "narrative_reference",
            "identity_basis": "manual_semantic_authority",
            "candidate_only": True,
            "canonical_write_back": False,
        })
    unique = {str(row["candidate_person_id"]): row for row in rows}
    return {
        "schema": "sfh2r-candidate-registry-repairs-v1",
        "authority": authority.authority_reference(),
        "records": [unique[key] for key in sorted(unique)],
        "production_person_ids_allocated": [],
        "candidate_only": True,
        "canonical_write_back": False,
    }


def _role_reprojection(observations: Mapping[str, Any]) -> dict[str, Any]:
    old_by_id = {
        str(row.get("observation_id")): row
        for row in records(observations, "records")
        if str(row.get("observation_id") or "")
    }
    rows: list[dict[str, Any]] = []
    for repair in authority.occurrence_repairs().values():
        replacement = repair.get("replacement") if isinstance(repair.get("replacement"), Mapping) else {}
        role = replacement.get("network_role")
        if not role:
            if replacement.get("attribute_type"):
                role = "person_attribute"
            else:
                continue
        row = old_by_id.get(str(repair.get("observation_id")), {})
        rows.append({
            "observation_id": repair.get("observation_id"),
            "story_id": repair.get("story_id"),
            "surface": repair.get("surface"),
            "historical_personhood": role == "historical_exemplum",
            "network_role": role,
            "core_story_graph_eligible": bool(replacement.get("core_story_graph_eligible", False)),
            "identity_display_name": replacement.get("identity_display_name") or replacement.get("bearer_display_name"),
            "before_classification": row.get("classification"),
            "after_classification": "historical_context_reference" if role == "historical_exemplum" else "non_person",
            "core_graph_action": "exclude" if not replacement.get("core_story_graph_eligible", False) else "retain",
            "manual_authority": repair,
        })
    return {
        "schema": "sfh2r-graph-role-reprojection-v1",
        "authority": authority.authority_reference(),
        "role_vocabulary": [
            "narrative_participant", "narrative_reference", "annotation_biographical_person",
            "citation_author", "historical_exemplum", "genealogy_ancestor", "anonymous_person",
            "person_attribute", "structural_reference",
        ],
        "role_authority": authority.load_authority().get("role_authority", []),
        "records": rows,
        "excluded_from_core_story_graph": [row["observation_id"] for row in rows if not row["core_story_graph_eligible"]],
        "historical_registry_preserved": True,
        "candidate_only": True,
        "canonical_write_back": False,
    }


def _all_observation_replay() -> dict[str, Any]:
    old_doc = read(OLD_OBSERVATIONS, {}) or {}
    old_rows = records(old_doc, "records")
    new_rows = [authority.apply_sfh2_observation(row) for row in old_rows]
    def counts(rows: Sequence[Mapping[str, Any]]) -> dict[str, int]:
        return dict(sorted(Counter(str(row.get("classification") or "" ) for row in rows).items()))
    old_ids = sorted({str(row.get("previous_candidate_person_id")) for row in old_rows if str(row.get("previous_candidate_person_id") or "")})
    new_ids = sorted({str(row.get("previous_candidate_person_id")) for row in new_rows if str(row.get("previous_candidate_person_id") or "")})
    old_graph = read(OLD_GRAPH, {}) or {}
    old_relations = read(OLD_RELATIONS, {}) or {}
    packet_doc = read(ROOT / "data/generated/sfh1/story-packets.json", {}) or {}
    packet_story_count = len({
        str(row.get("story_id"))
        for row in records(packet_doc, "packets")
        if str(row.get("story_id") or "")
    })
    return {
        "schema": "sfh2r-offline-repair-replay-v1",
        "mode": "offline_mechanical_manual_overlay_no_llm",
        "stories": packet_story_count or len({str(row.get("story_id")) for row in old_rows if str(row.get("story_id") or "")}),
        "observation_count_before": len(old_rows),
        "observation_count_after": len(new_rows),
        "classification_counts_before": counts(old_rows),
        "classification_counts_after": counts(new_rows),
        "candidate_ids_before": len(old_ids),
        "candidate_ids_after": len(new_ids),
        "candidate_ids_added_by_review": sorted(set(new_ids) - set(old_ids)),
        "manual_observation_actions": dict(sorted(Counter(str(row.get("action")) for row in authority.occurrence_repairs().values()).items())),
        "core_story_graph_exclusions": [
            str(row.get("observation_id"))
            for row in authority.occurrence_repairs().values()
            if ((row.get("replacement") or {}).get("core_story_graph_eligible") is False)
        ],
        "old_graph_summary_preserved": old_graph.get("summary", {}),
        "relation_projection_sha256_preserved": file_hash(OLD_RELATIONS),
        "relation_record_count_preserved": len(records(old_relations, "records")),
        "old_sfh2_artifacts_mutated": False,
        "interpretation": "Offline repair effects only; this is not new semantic-model performance.",
        "story_ids_with_observations": len({str(row.get("story_id")) for row in old_rows if str(row.get("story_id") or "")} ),
        "candidate_only": True,
        "canonical_write_back": False,
    }


def _regressions(alias_doc: Mapping[str, Any], profile_doc: Mapping[str, Any], occurrence_doc: Mapping[str, Any], candidates: Mapping[str, Any], roles: Mapping[str, Any]) -> dict[str, Any]:
    active_aliases = records(read(ALIASES, {}) or {}, "aliases")
    alias_by_surface_person = {
        (str(row.get("surface")), str(person)): row
        for row in active_aliases
        for person in row.get("person_ids", []) or []
    }
    occurrence_by_id = {str(row.get("observation_id")): row for row in occurrence_doc.get("records", []) or []}
    cases: list[dict[str, Any]] = []
    for repair in authority.alias_repairs():
        alias_id = str(repair.get("alias_id"))
        after = next((row.get("after") for row in alias_doc.get("records", []) if row.get("alias_id") == alias_id), None)
        expected_surface = str(repair.get("corrected_surface") or repair.get("surface"))
        actual = alias_by_surface_person.get((expected_surface, str(repair.get("current_person_id"))))
        kept = {str(row.get("evidence_id")) for row in (actual or {}).get("source_evidence", []) or [] if isinstance(row, Mapping)}
        removed = {str(value) for value in repair.get("remove_evidence_ids", []) or []}
        passed = bool(actual) and removed.isdisjoint(kept)
        if repair.get("keep_evidence_ids"):
            passed = passed and set(str(value) for value in repair["keep_evidence_ids"]).issubset(kept)
        if repair.get("corrected_resolution_mode"):
            passed = passed and actual.get("resolution_mode") == repair.get("corrected_resolution_mode")
        cases.append({
            "case_id": f"alias:{alias_id}",
            "kind": "alias_repair",
            "surface": repair.get("surface"),
            "person_id": repair.get("current_person_id"),
            "expected_from_manual_authority": {
                "surface": expected_surface,
                "resolution_mode": repair.get("corrected_resolution_mode"),
                "status": repair.get("corrected_status"),
                "removed_evidence_ids": sorted(removed),
            },
            "observed": {"surface": actual.get("surface") if actual else None, "evidence_ids": sorted(kept), "after_present": after is not None},
            "passed": passed,
            "basis": "manual_semantic_authority_mechanical_assertion",
        })
    for observation_id, repair in sorted(authority.occurrence_repairs().items()):
        row = occurrence_by_id.get(observation_id, {})
        action = str(repair.get("action"))
        replacement = repair.get("replacement_display_name")
        after = row.get("after") or {}
        if replacement:
            passed = str(after.get("previous_identity_decision", {}).get("candidate_display_name") or "") == replacement and str(after.get("previous_candidate_person_id") or "").startswith("sfh2r-manual-candidate-")
        elif action.startswith("suppress_"):
            passed = after.get("classification") == "non_person" and not after.get("previous_candidate_person_id")
        else:
            passed = bool(after.get("network_role") or after.get("manual_semantic_repair"))
        cases.append({
            "case_id": f"occurrence:{observation_id}",
            "kind": "occurrence_repair",
            "story_id": repair.get("story_id"),
            "surface": repair.get("surface"),
            "expected_from_manual_authority": repair,
            "observed": {"classification": after.get("classification"), "candidate_person_id": after.get("previous_candidate_person_id"), "network_role": after.get("network_role")},
            "passed": passed,
            "basis": "manual_semantic_authority_mechanical_assertion",
        })
    safe_cases: list[dict[str, Any]] = []
    for safe in authority.load_authority().get("audited_safe_w4_aliases", []) or []:
        actual = alias_by_surface_person.get((str(safe.get("surface")), str(safe.get("person_id"))))
        safe_cases.append({"surface": safe.get("surface"), "person_id": safe.get("person_id"), "present": bool(actual), "passed": bool(actual), "basis": "manual_safe_alias_regression"})
    cases.extend({"case_id": f"safe_w4:{row['surface']}", "kind": "safe_alias", **row} for row in safe_cases)
    return {
        "schema": "sfh2r-regression-results-v1",
        "cases": cases,
        "passed_count": sum(bool(row.get("passed")) for row in cases),
        "case_count": len(cases),
        "failed_cases": [row.get("case_id") for row in cases if not row.get("passed")],
        "known_false_links_blocked": {
            "趙至_not_桓亮": not any(
                str(row.get("canonical_name")) == "趙至"
                and any(form_surface in {"桓亮", "桓景真"} for _, _, form_surface in _profile_forms(row))
                for row in records(profile_doc, "records")
            ),
            "郭象_not_子少": not any(str(row.get("canonical_name")) == "郭象" and "子少" in str(row.get("identity")) for row in records(profile_doc, "records")),
        },
        "candidate_registry_count": len(candidates.get("records", []) or []),
        "role_reprojection_count": len(roles.get("records", []) or []),
        "candidate_only": True,
        "canonical_write_back": False,
    }


def _remaining_risks() -> dict[str, Any]:
    return {
        "schema": "sfh2r-remaining-known-risk-v1",
        "authority_boundary": "Only the reviewed SFH2R records are materialized; unreviewed occurrences remain governed by prior outputs.",
        "risks": [
            {"risk": "shared_courtesy_forms", "forms": ["景真", "敬祖", "萬年", "無忌", "安國", "大業", "世將", "子相"], "mitigation": "active aliases are contextual/shared_or_contextual and cannot be used as global exact keys"},
            {"risk": "unreviewed_short_forms", "mitigation": "not expanded or semantically rejudged by this repair"},
            {"risk": "old_artifact_provenance", "mitigation": "old SFH2/HDB2 artifacts remain immutable audit inputs; active profile indexes carry the repair overlay"},
        ],
        "candidate_only": True,
        "canonical_write_back": False,
    }


def _metrics(alias_doc: Mapping[str, Any], profiles: Mapping[str, Any], occurrences: Mapping[str, Any], candidates: Mapping[str, Any], roles: Mapping[str, Any], replay: Mapping[str, Any], regressions: Mapping[str, Any]) -> dict[str, Any]:
    removed = sum(len(row.get("manual_authority", {}).get("remove_evidence_ids", []) or []) for row in alias_doc.get("records", []) or [])
    before_evidence = sum(
        len(row.get("before", {}).get("source_evidence", []) or [])
        for row in alias_doc.get("records", []) or []
    )
    after_evidence = sum(
        len(row.get("after", {}).get("source_evidence", []) or [])
        for row in alias_doc.get("records", []) or []
    )
    retained = sum(len(row.get("after_evidence_ids", []) or []) for row in alias_doc.get("records", []) or [])
    suppressed = sum(1 for row in occurrences.get("records", []) or [] if str(row.get("manual_authority", {}).get("action", "")).startswith("suppress_"))
    replaced = sum(1 for row in occurrences.get("records", []) or [] if row.get("manual_authority", {}).get("replacement_display_name"))
    roles_excluded = sum(1 for row in roles.get("records", []) or [] if not row.get("core_story_graph_eligible"))
    return {
        "schema": "sfh2r-metrics-v1",
        "alias_records_repaired": len(alias_doc.get("records", []) or []),
        "evidence_rows_removed_explicitly": removed,
        "evidence_rows_removed_total": max(0, before_evidence - after_evidence),
        "evidence_rows_removed_by_replacement": max(0, before_evidence - after_evidence - removed),
        "evidence_rows_retained_after_repair": retained,
        "exact_aliases_downgraded": sum(str(row.get("manual_authority", {}).get("action", "")).startswith("downgrade_") for row in alias_doc.get("records", []) or []),
        "corrupt_aliases_replaced": sum(row.get("manual_authority", {}).get("action") == "replace_corrupt_alias_surface" for row in alias_doc.get("records", []) or []),
        "occurrence_identities_suppressed": suppressed,
        "occurrence_identities_replaced": replaced,
        "person_attributes_reclassified": sum(row.get("after", {}).get("classification") == "non_person" for row in occurrences.get("records", []) or []),
        "historical_exempla_removed_from_core_graph": sum(row.get("network_role") == "historical_exemplum" for row in roles.get("records", []) or []),
        "citation_author_occurrences_removed_from_core_graph": 0,
        "candidate_historical_entities_created_or_reused": len(candidates.get("records", []) or []),
        "profile_forms_removed": len(profiles.get("profile_forms_removed", []) or []),
        "downstream_candidate_matches_eliminated": len(profiles.get("profile_forms_removed", []) or []),
        "targeted_regression_pass_rate": (regressions.get("passed_count", 0) / regressions.get("case_count", 1)) if regressions.get("case_count") else 1.0,
        "offline_replay": replay,
        "llm_calls": 0,
        "llm_tokens": 0,
        "canonical_writes": 0,
        "candidate_only": True,
        "canonical_write_back": False,
    }


def _canonical_hashes() -> dict[str, str | None]:
    names = [
        "data/people.json", "data/relations.json", "data/personStory.json",
        "data/annotation/story-temporal-anchors-h0a.json",
        "data/annotation/story-temporal-evidence-h0a.json",
        "data/annotation/kinship-h0b1.json", "data/annotation/marriages-h0b1.json",
        "data/annotation/office-tenures-h0b1.json",
    ]
    return {name: file_hash(ROOT / name) for name in names}


def _xe0_profile_transition() -> dict[str, Any]:
    """Record the explicit XE0 derived-profile baseline migration.

    SFH2R intentionally rebuilds the active candidate-only profile.  XE0's
    immutable HDB2-F hashes remain unchanged, while its separately versioned
    derived-profile hash is updated through the existing migration helper.
    """
    path = ROOT / "data/generated/hdb2-xe0/live/20260826T-HDB2-XE0-02/manifest.json"
    current = read(path, {}) or {}
    raw, source = _git_file(path.relative_to(ROOT).as_posix())
    before = {}
    if raw is not None:
        try:
            before = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            before = {}
    return {
        "manifest": str(path.relative_to(ROOT)),
        "before_source": source,
        "before_authorized_derived_projection_hashes": before.get("authorized_derived_projection_hashes", {}),
        "after_authorized_derived_projection_hashes": current.get("authorized_derived_projection_hashes", {}),
        "authorized_derived_projection_version": current.get("authorized_derived_projection_version"),
        "immutable_protected_hashes_unchanged": current.get("protected_hashes_before") == current.get("protected_hashes_after"),
        "reason": "SFH2R provenance-gated active profile cleanup; canonical and immutable HDB2-F semantic artifacts remain protected.",
    }


def _active_input_transition() -> dict[str, Any]:
    """Capture the exact pre/post hashes for SFH2/HDA2 compatibility.

    The active alias/profile projections are intentionally repaired in this
    stage.  Earlier experiments retain their pre-repair snapshots, so their
    validators need an explicit, auditable bridge.  On a replay after this
    commit, reuse the first SFH2R ``before_hashes`` rather than treating the
    repaired HEAD as the historical before image.
    """
    previous = read(OUT / "repair-manifest.json", {}) or {}
    previous_transition = previous.get("active_input_transition") if isinstance(previous, Mapping) else None
    if isinstance(previous_transition, Mapping) and isinstance(previous_transition.get("before_hashes"), Mapping):
        active_paths = set(sfh2r_contract.ACTIVE_REPAIR_INPUTS)
        before = {
            str(key): str(value)
            for key, value in previous_transition["before_hashes"].items()
            if str(key) in active_paths and str(value)
        }
        before_source = "sfh2r-manifest"
    else:
        before = {}
        before_source = "git:HEAD"
    # New downstream projections may be added to the transition after the
    # first materialization.  Their historical before-image is still the
    # checkout that received this repair, never the already-repaired working
    # tree.  This keeps the bridge fail-closed on an explicit byte pair.
    for relative in sfh2r_contract.ACTIVE_REPAIR_INPUTS:
        if relative in before:
            continue
        raw, _ = _git_file(relative)
        if raw is not None:
            before[relative] = hashlib.sha256(raw).hexdigest()
    after = {
        relative: digest
        for relative in sfh2r_contract.ACTIVE_REPAIR_INPUTS
        if (digest := file_hash(ROOT / relative)) is not None
    }
    return {
        "before_source": before_source,
        "before_hashes": before,
        "after_hashes": after,
        "changed_paths": sorted(
            path for path in sorted(set(before) | set(after))
            if before.get(path) != after.get(path)
        ),
        "semantic_basis": "manual_semantic_authority_only",
    }


def build() -> dict[str, Any]:
    # The separate command is idempotent and applies no semantic logic of its
    # own.  It is invoked here so a clean checkout can run this entry point
    # directly; an already repaired checkout reuses its preserved audit.
    import apply_sfh2r_alias_repairs  # noqa: PLC0415
    apply_sfh2r_alias_repairs.materialize()

    aliases_after = read(ALIASES, {}) or {}
    profiles_after = read(PROFILE, {}) or {}
    observations_doc = _observation_audit()
    alias_doc = _alias_audit()
    profile_doc = _profile_audit()
    candidate_doc = _candidate_registry(observations_doc)
    role_doc = _role_reprojection(read(OLD_OBSERVATIONS, {}) or {})
    replay_doc = _all_observation_replay()
    regression_doc = _regressions(alias_doc, profiles_after, observations_doc, candidate_doc, role_doc)
    risk_doc = _remaining_risks()
    metrics_doc = _metrics(alias_doc, profile_doc, observations_doc, candidate_doc, role_doc, replay_doc, regression_doc)
    xe0_transition = _xe0_profile_transition()
    active_input_transition = _active_input_transition()

    write(OUT / "alias-before-after.json", alias_doc)
    write(OUT / "profile-before-after.json", profile_doc)
    write(OUT / "occurrence-before-after.json", observations_doc)
    write(OUT / "candidate-registry-repairs.json", candidate_doc)
    write(OUT / "graph-role-reprojection.json", role_doc)
    write(OUT / "offline-replay-effects.json", replay_doc)
    write(OUT / "regression-results.json", regression_doc)
    write(OUT / "remaining-known-risk.json", risk_doc)
    write(OUT / "metrics.json", metrics_doc)

    manifest_core = {
        "schema": "sfh2r-manifest-v1",
        "authority": authority.authority_reference(),
        "authority_sha256": file_hash(authority.AUTHORITY_PATH),
        "input_artifacts": {
            "aliases_before": alias_doc.get("before_registry_sha256"),
            "aliases_after": alias_doc.get("after_registry_sha256"),
            "profile_before": profile_doc.get("before_profile_sha256"),
            "profile_after": profile_doc.get("after_profile_sha256"),
            "candidate_profile_before": profile_doc.get("before_candidate_profile_sha256"),
            "candidate_profile_after": profile_doc.get("after_candidate_profile_sha256"),
            "sfh2_observations": file_hash(OLD_OBSERVATIONS),
            "sfh2_relations": file_hash(OLD_RELATIONS),
            "sfh2_entity_consolidation": file_hash(OLD_ENTITY),
            "sfh2_graph": file_hash(OLD_GRAPH),
            "hda2_overlay": file_hash(HDA2_OVERLAY),
            "data/generated/hdb2-xe0/live/20260826T-HDB2-XE0-02/manifest.json": file_hash(ROOT / "data/generated/hdb2-xe0/live/20260826T-HDB2-XE0-02/manifest.json"),
        },
        "authorized_derived_profile_transition": xe0_transition,
        "active_input_transition": active_input_transition,
        "protected_canonical_hashes": _canonical_hashes(),
        "source_artifacts_preserved": True,
        "old_artifacts_preserved_for_audit": True,
        "live_llm_calls": 0,
        "candidate_only": True,
        "canonical_write_back": False,
    }
    output_hashes = {
        path.name: file_hash(path)
        for path in sorted(OUT.glob("*.json"))
        if path.name != "repair-manifest.json"
    }
    manifest_core["output_hashes"] = output_hashes
    manifest_core["manifest_hash"] = value_hash(manifest_core)
    write(OUT / "repair-manifest.json", manifest_core)
    return manifest_core


if __name__ == "__main__":
    result = build()
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
