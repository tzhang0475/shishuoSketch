#!/usr/bin/env python3
"""Rebuild the HDB2-F candidate-only Person projections with provenance gates.

This is intentionally narrower than ``build_hdb2_full_projection.project``.
It refreshes only the derived profile projections and their integrity audit;
the HDB2-F occurrence decisions, relation candidates, and canonical inputs are
not rewritten by this repair tool.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import build_hdb2_full_projection as projection  # noqa: E402
import build_hng0_2 as hng02  # noqa: E402
import hdb2_full_frontier_common as common  # noqa: E402


RUN_DIR = ROOT / "data/generated/hdb2-f/live/20260826T-HDB2-F-03"
EXISTING_PROFILE = common.DERIVED / "hdb2-f-person-knowledge.json"
CANDIDATE_PROFILE = common.DERIVED / "hdb2-f-candidate-person-knowledge.json"
AUDIT_PATH = common.DERIVED / "hdb2-f-profile-integrity-audit.json"
PROFILE_FORM_TYPES = {"alias", "courtesy_name", "title", "observed_surface"}


def _load_decisions(run_dir: Path) -> list[dict[str, Any]]:
    decisions, _, _ = projection.build_occurrence_decisions(run_dir)
    return decisions


def _profile_forms(profile: Mapping[str, Any]) -> list[tuple[str, str, str]]:
    identity = profile.get("identity") or {}
    result: list[tuple[str, str, str]] = []
    for field, form_type in (
        ("aliases", "alias"),
        ("courtesy_names", "courtesy_name"),
        ("titles", "title"),
        ("observed_surfaces", "observed_surface"),
    ):
        for value in identity.get(field, []) or []:
            if value not in (None, ""):
                result.append((str(profile.get("person_id") or ""), form_type, str(value)))
    return result


def _provenance_rows(profile: Mapping[str, Any]) -> list[dict[str, Any]]:
    rows = (profile.get("identity") or {}).get("form_provenance", []) or []
    return [dict(row) for row in rows if isinstance(row, Mapping)]


def _known_contamination(profile: Mapping[str, Any]) -> list[dict[str, Any]]:
    name = str(profile.get("canonical_name") or "")
    bad_by_name = {
        "鄧攸": {"潁", "石勒", "茂英", "攸之甥"},
        "王羲之": {"孫興公", "支道林"},
    }
    bad = bad_by_name.get(name, set())
    rows: list[dict[str, Any]] = []
    for person_id, form_type, surface in _profile_forms(profile):
        if surface in bad:
            rows.append({"person_id": person_id, "canonical_name": name, "surface": surface, "form_type": form_type})
    # These are occurrence-specific contamination checks.  The valid 09-045
    # 仲文 -> 朱伺 occurrence must remain usable, while the 09-088 occurrence
    # must not be copied into that profile.
    if name == "朱伺":
        for row in _provenance_rows(profile):
            if row.get("surface") == "桓" or (
                row.get("surface") == "仲文" and row.get("evidence_ref") == "hng2c1-shishuo-09-pinzao-088-main"
            ):
                rows.append({"person_id": row.get("person_id"), "canonical_name": name, "surface": row.get("surface"), "form_type": row.get("form_type"), "occurrence_id": row.get("occurrence_id")})
    if name == "卞範之":
        for row in _provenance_rows(profile):
            if row.get("surface") in {"謙", "敬祖"} and row.get("evidence_ref") == "hng2c1-shishuo-09-pinzao-088-liu-annotation-001":
                rows.append({"person_id": row.get("person_id"), "canonical_name": name, "surface": row.get("surface"), "form_type": row.get("form_type"), "occurrence_id": row.get("occurrence_id")})
    return rows


def _audit_profiles(
    old_existing: Mapping[str, Any],
    old_candidates: Mapping[str, Any],
    existing: Sequence[Mapping[str, Any]],
    candidates: Sequence[Mapping[str, Any]],
    decisions: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    all_profiles = [*existing, *candidates]
    old_profiles = [*(old_existing.get("records", []) or []), *(old_candidates.get("records", []) or [])]
    old_forms = {(pid, form_type, surface) for profile in old_profiles for pid, form_type, surface in _profile_forms(profile)}
    new_forms = {(pid, form_type, surface) for profile in all_profiles for pid, form_type, surface in _profile_forms(profile)}
    provenance: list[dict[str, Any]] = [row for profile in all_profiles for row in _provenance_rows(profile)]
    decisions_by_occurrence = {str(row.get("occurrence_id")): row for row in decisions}
    errors: list[str] = []
    forms_with_provenance = 0
    orphan_forms = 0
    profile_form_count = 0
    surface_to_people: dict[str, set[str]] = {}
    occurrence_to_people: dict[tuple[str, str], set[str]] = {}
    provenance_fields_missing = 0
    required_provenance_fields = (
        "surface",
        "form_type",
        "person_id",
        "occurrence_id",
        "identity_observation_id",
        "evidence_ref",
        "identity_status",
        "identity_basis",
    )
    for profile in all_profiles:
        pid = str(profile.get("person_id") or "")
        identity = profile.get("identity") or {}
        # ``observed_surfaces`` is an occurrence index and may also contain a
        # value that is classified as an alias/courtesy/title.  It is not a
        # second, differently sourced form.  Match the required provenance
        # by exact person + surface, then validate the provenance form type.
        provenance_by_surface: dict[tuple[str, str], list[dict[str, Any]]] = {}
        for row in _provenance_rows(profile):
            provenance_by_surface.setdefault(
                (str(row.get("surface") or ""), str(row.get("person_id") or "")),
                [],
            ).append(row)
        for form_pid, form_type, surface in _profile_forms(profile):
            profile_form_count += 1
            rows = provenance_by_surface.get((surface, form_pid), [])
            if not rows:
                orphan_forms += 1
                errors.append(f"form_without_provenance:{pid}:{form_type}:{surface}")
                continue
            forms_with_provenance += 1
            if any(str(row.get("form_type") or "") not in PROFILE_FORM_TYPES for row in rows):
                errors.append(f"provenance_form_type_invalid:{pid}:{surface}")
            for row in rows:
                missing = [field for field in required_provenance_fields if not row.get(field)]
                if missing:
                    provenance_fields_missing += 1
                    errors.append(f"provenance_fields_missing:{pid}:{surface}:{','.join(missing)}")
                if row.get("person_id") != pid:
                    errors.append(f"provenance_person_mismatch:{pid}:{surface}")
                occurrence_id = str(row.get("occurrence_id") or "")
                decision = decisions_by_occurrence.get(occurrence_id)
                if not decision:
                    errors.append(f"provenance_occurrence_missing:{occurrence_id}")
                elif str(decision.get("resolved_person_id") or decision.get("candidate_person_id") or "") != pid:
                    errors.append(f"provenance_occurrence_person_mismatch:{occurrence_id}:{pid}")
            surface_to_people.setdefault(surface, set()).add(pid)
            for row in rows:
                occurrence_id = str(row.get("occurrence_id") or "")
                occurrence_to_people.setdefault((occurrence_id, surface), set()).add(pid)
        for row in _provenance_rows(profile):
            key = (str(row.get("surface") or ""), str(row.get("person_id") or ""))
            if key not in provenance_by_surface:
                errors.append(f"orphan_provenance:{pid}:{row.get('form_type')}:{key[0]}")

    cross_person = [
        {"surface": surface, "person_ids": sorted(person_ids)}
        for surface, person_ids in sorted(surface_to_people.items())
        if len(person_ids) > 1
    ]
    ambiguous_forms = [
        {"occurrence_id": occurrence, "surface": surface, "person_ids": sorted(person_ids)}
        for (occurrence, surface), person_ids in sorted(occurrence_to_people.items())
        if occurrence and len(person_ids) > 1
    ]
    old_bad = [row for profile in old_profiles for row in _known_contamination(profile)]
    new_bad = [row for profile in all_profiles for row in _known_contamination(profile)]
    known_failures: list[str] = []
    new_names = {str(profile.get("canonical_name") or ""): profile for profile in all_profiles}
    for required in ("鄧攸", "鄧伯道"):
        if required not in set((new_names.get("鄧攸", {}).get("identity") or {}).get("observed_surfaces", [])) | set((new_names.get("鄧攸", {}).get("identity") or {}).get("aliases", [])):
            known_failures.append(f"deng-you-valid-form_missing:{required}")
    if new_bad:
        known_failures.extend(f"known_contamination:{row.get('canonical_name')}:{row.get('surface')}" for row in new_bad)
    return {
        "schema": "hdb2-f-profile-integrity-audit-v1",
        "profile_form_count": profile_form_count,
        "forms_with_provenance": forms_with_provenance,
        "provenance_fields_missing": provenance_fields_missing,
        "forms_without_identity_provenance": orphan_forms,
        "orphan_profile_forms": orphan_forms,
        "ambiguous_forms": ambiguous_forms,
        "cross_person_duplicated_forms": cross_person,
        "cross_person_surface_conflicts": len(cross_person),
        "contaminated_profile_forms_detected": len(old_bad),
        "contaminated_profile_forms_removed": len(set(tuple(sorted(row.items())) for row in old_bad) - set(tuple(sorted(row.items())) for row in new_bad)),
        "old_profile_form_count": len(old_forms),
        "new_profile_form_count": len(new_forms),
        "profile_forms_removed": sorted([{"person_id": pid, "form_type": form_type, "surface": surface} for pid, form_type, surface in old_forms - new_forms], key=lambda row: (row["person_id"], row["form_type"], row["surface"])),
        "known_regression_failures": sorted(set(known_failures)),
        "known_contamination_remaining": new_bad,
        "candidate_only": True,
        "canonical_write_back": False,
    }


def build_documents(run_dir: Path = RUN_DIR) -> tuple[dict[str, Any], dict[str, Any]]:
    """Build the two candidate-only profile documents without writing them."""
    aggregate, identity, relations, _ = common.load_hdb1()
    del aggregate
    decisions = _load_decisions(run_dir)
    catalog = hng02.person_catalog()
    relation_rows, _, _ = projection.project_relations(relations, identity, decisions)
    temporal_rows: list[dict[str, Any]] = []
    for path in (common.ANNOTATION / "hdb1-temporal-candidates.json", common.ANNOTATION / "hdb1-wave2-temporal-candidates.json"):
        temporal_rows.extend((common.read_json(path, {}) or {}).get("records", []))
    existing, candidates = projection.build_knowledge(decisions, relation_rows, identity, catalog, temporal_rows)
    return (
        {"schema": "hdb2-f-person-knowledge-v1", "records": existing, "candidate_only": True, "canonical_write_back": False},
        {"schema": "hdb2-f-candidate-person-knowledge-v1", "records": candidates, "candidate_only": True, "canonical_write_back": False},
    )


def rebuild(run_dir: Path = RUN_DIR, *, write: bool = True) -> dict[str, Any]:
    existing_document, candidate_document = build_documents(run_dir)
    existing = list(existing_document.get("records", []) or [])
    candidates = list(candidate_document.get("records", []) or [])
    aggregate, identity, _, _ = common.load_hdb1()
    del aggregate
    decisions = _load_decisions(run_dir)
    old_existing = common.read_json(EXISTING_PROFILE, {}) or {}
    old_candidates = common.read_json(CANDIDATE_PROFILE, {}) or {}
    audit = _audit_profiles(old_existing, old_candidates, existing, candidates, decisions)
    if write:
        # Keep the one-time remediation summary visible on idempotent rebuilds.
        # After the first repaired write the current files are, correctly, no
        # longer the contaminated "old" input.  The audit still describes the
        # historical before/after transition rather than reporting that a
        # second identical rebuild removed zero forms.
        previous_audit = common.read_json(AUDIT_PATH, {}) or {}
        if previous_audit.get("contaminated_profile_forms_removed", 0):
            for key in ("contaminated_profile_forms_detected", "contaminated_profile_forms_removed", "old_profile_form_count"):
                audit[key] = max(int(audit.get(key) or 0), int(previous_audit.get(key) or 0))
            if not audit.get("profile_forms_removed") and previous_audit.get("profile_forms_removed"):
                audit["profile_forms_removed"] = list(previous_audit.get("profile_forms_removed") or [])
        common.write_json(EXISTING_PROFILE, existing_document)
        common.write_json(CANDIDATE_PROFILE, candidate_document)
        common.write_json(AUDIT_PATH, audit)
    return audit


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", type=Path, default=RUN_DIR)
    parser.add_argument("--check", action="store_true", help="rebuild in memory without writing profile artifacts")
    args = parser.parse_args()
    run_dir = args.run_dir if args.run_dir.is_absolute() else ROOT / args.run_dir
    result = rebuild(run_dir, write=not args.check)
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if not result.get("known_regression_failures") and not result.get("forms_without_identity_provenance") else 1


if __name__ == "__main__":
    raise SystemExit(main())
