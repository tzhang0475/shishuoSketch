#!/usr/bin/env python3
"""Python-owned constraint fusion for HDB2-P1.

The solver consumes only validated, source-grounded atoms.  Model output can
add evidence, but it cannot select IDs, merge candidates, or write canonical
facts.
"""

from __future__ import annotations

import argparse
import collections
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

import build_hng0_2 as hng02  # noqa: E402
import historical_entity_resolver as resolver  # noqa: E402
from hdb2_p1_common import (  # noqa: E402
    ANNOTATION,
    DERIVED,
    candidate_matches,
    read_json,
    source_work_for_ref,
    stable_hash,
    write_json,
)


IDENTITY_MARKERS = ("字", "名", "諱", "號", "号")
GENERIC = {"父", "母", "子", "女", "兄", "弟", "妻", "婿", "帝", "太子", "客", "主", "王", "公"}


def _is_named_surface(value: Any) -> bool:
    text = str(value or "").strip()
    return bool(text) and text not in GENERIC and len(resolver.matching_normalize(text)) >= 2


def _identity_links(case: Mapping[str, Any], atoms: Sequence[Mapping[str, Any]], catalog: Mapping[str, Mapping[str, Any]], index: Mapping[str, Sequence[str]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    targets = {resolver.matching_normalize(x) for x in case.get("target_surfaces", []) if x}
    generic_targets = {"帝", "太子", "父", "母", "兄", "弟", "子", "女", "客", "主"}
    supports: list[dict[str, Any]] = []
    new_candidates: list[dict[str, Any]] = []
    for atom in atoms:
        if str(atom.get("atom_kind")) != "identity_name":
            continue
        subject = str(atom.get("subject_surface") or "")
        obj = str(atom.get("object_surface") or "")
        if not subject or not obj:
            continue
        sides = [(subject, obj), (obj, subject)]
        for left, right in sides:
            left_norm = resolver.matching_normalize(left)
            target_surface = next((surface for surface in case.get("target_surfaces", []) if resolver.matching_normalize(surface) == left_norm or (left_norm.endswith(resolver.matching_normalize(surface)) and left_norm != resolver.matching_normalize(surface))), None)
            if target_surface is None:
                continue
            matches = candidate_matches(right, catalog, index)
            basis = "evidence_identity_assertion"
            # A full source name containing an abbreviated target is a
            # contextual projection, not a global alias.  It is allowed only
            # when that full name maps uniquely in the existing catalogue.
            if not matches and left_norm != resolver.matching_normalize(target_surface):
                matches = candidate_matches(left, catalog, index)
                basis = "contextual_name_projection"
            if len(matches) == 1:
                supports.append({"target_surface": target_surface, "person_id": matches[0], "person_surface": right if basis == "explicit_name_evidence" else left, "atom_id": atom.get("atom_id"), "basis": basis, "evidence_ref": atom.get("evidence_ref"), "exact_span": atom.get("exact_span")})
            elif not matches and target_surface not in generic_targets:
                predicate = str(atom.get("predicate_surface") or "")
                # A location phrase is not a person.  For explicit 名/諱/字
                # syntax, keep the named subject as the new candidate label;
                # do not turn a malformed object into a person.
                if any(marker in predicate for marker in ("字", "名", "諱", "號")):
                    label = left if _is_named_surface(left) else right
                    if any(marker in label for marker in ("人", "郡", "國", "縣", "州", "鄉")):
                        continue
                    if _is_named_surface(label) or len(resolver.matching_normalize(label)) == 1:
                        new_candidates.append({"target_surface": target_surface, "person_surface": label, "atom_id": atom.get("atom_id"), "evidence_ref": atom.get("evidence_ref"), "exact_span": atom.get("exact_span"), "basis": "new_candidate"})
    return supports, new_candidates


def _candidate_rows(case: Mapping[str, Any], atoms: Sequence[Mapping[str, Any]], catalog: Mapping[str, Mapping[str, Any]], index: Mapping[str, Sequence[str]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    rows: list[dict[str, Any]] = []
    before = [{"candidate_key": f"c{i}", "person_id": str(pid), "source": "hdb1_current_candidate"} for i, pid in enumerate(sorted({str(x) for x in case.get("current_candidate_person_ids", []) if x}))]
    for row in before: rows.append(dict(row))
    for surface in case.get("target_surfaces", []):
        for pid in candidate_matches(str(surface), catalog, index):
            if not any(x.get("person_id") == pid for x in rows):
                rows.append({"candidate_key": f"c{len(rows)}", "person_id": pid, "source": "catalogue_exact_match", "surface": surface})
    supports, new_candidates = _identity_links(case, atoms, catalog, index)
    for support in supports:
        pid = str(support["person_id"])
        if not any(x.get("person_id") == pid for x in rows):
            rows.append({"candidate_key": f"c{len(rows)}", "person_id": pid, "source": "evidence_identity_assertion", "surface": support.get("target_surface")})
    for new in new_candidates:
        label = str(new.get("person_surface") or "")
        key = f"n{len([x for x in rows if x.get('person_id') is None])}"
        rows.append({"candidate_key": key, "person_id": None, "canonical_candidate_label": label, "person_surface": label, "source": "new_candidate", "surface": new.get("target_surface"), "atom_id": new.get("atom_id")})
    return before, rows, supports


def _temporal_eliminations(case: Mapping[str, Any], rows: Sequence[Mapping[str, Any]]) -> tuple[set[str], list[dict[str, Any]]]:
    # HDB2 only uses reviewed, bounded H0A activity records as hard gates.
    anchors = read_json(ANNOTATION / "person-activity-anchors-h0a.json", {}) or {}
    by_person: dict[str, list[Mapping[str, Any]]] = collections.defaultdict(list)
    for row in anchors.get("records", []):
        if str(row.get("review_status")) == "reviewed" and str(row.get("assertion_status")) in {"attested", "reviewed"}:
            by_person[str(row.get("person_id"))].append(row)
    story_ids = {str(x) for x in case.get("story_ids", [])}
    # A Story-owned temporal candidate is never transferred to another Story;
    # this function can only reject an explicit non-overlap for the same case.
    intervals: list[tuple[int, int]] = []
    for row in case.get("story_temporal_constraints", []):
        anchor = row.get("h0a_current_anchor") or {}
        start = anchor.get("start_year_ce"); end = anchor.get("end_year_ce")
        if isinstance(start, int) and isinstance(end, int): intervals.append((start, end))
    eliminated: set[str] = set(); evidence: list[dict[str, Any]] = []
    if not intervals: return eliminated, evidence
    for row in rows:
        pid = str(row.get("person_id") or "")
        if not pid: continue
        for act in by_person.get(pid, []):
            start = act.get("start_year_ce"); end = act.get("end_year_ce")
            if not isinstance(start, int) or not isinstance(end, int): continue
            if all(end < lo or start > hi for lo, hi in intervals):
                eliminated.add(pid)
                evidence.append({"candidate_person_id": pid, "constraint_type": "temporal", "status": "conflict", "reason": "reviewed_activity_interval_does_not_overlap_story_interval", "activity": dict(act), "story_ids": sorted(story_ids)})
                break
    return eliminated, evidence


def _constraint_rows(atoms: Sequence[Mapping[str, Any]], case: Mapping[str, Any], catalog: Mapping[str, Mapping[str, Any]], index: Mapping[str, Sequence[str]], supports: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    constraints: list[dict[str, Any]] = []
    for atom in atoms:
        kind = str(atom.get("atom_kind") or "")
        if kind == "identity_name": ctype, status = "name", "strong_support"
        elif kind == "kinship": ctype, status = "kinship", "support"
        elif kind == "office": ctype, status = "office", "support"
        elif kind == "temporal_activity": ctype, status = "temporal", "support"
        elif kind == "location_origin": ctype, status = "location", "support"
        else: ctype, status = "source_local_context", "support"
        constraints.append({"constraint_id": f"hdb2-constraint-{stable_hash({'case': case.get('case_id'), 'atom': atom.get('atom_id'), 'type': ctype})[:20]}", "constraint_type": ctype, "constraint_scope": "case", "candidate_person_id": None, "status": status, "computed_by": "python_hdb2_atom_projection", "independent": True, "atom_id": atom.get("atom_id"), "evidence_refs": [atom.get("evidence_ref")], "exact_span": atom.get("exact_span"), "reason_code": f"accepted_{kind}"})
    for support in supports:
        constraints.append({"constraint_id": f"hdb2-constraint-{stable_hash({'case': case.get('case_id'), 'atom': support.get('atom_id'), 'pid': support.get('person_id')})[:20]}", "constraint_type": "name", "constraint_scope": "candidate", "candidate_person_id": support.get("person_id"), "status": "strong_support", "computed_by": "python_hdb2_identity_propagation", "independent": True, "atom_id": support.get("atom_id"), "evidence_refs": [support.get("evidence_ref")], "exact_span": support.get("exact_span"), "reason_code": "explicit_identity_evidence"})
    return constraints


def _decision(case: Mapping[str, Any], before: Sequence[Mapping[str, Any]], candidates: Sequence[Mapping[str, Any]], supports: Sequence[Mapping[str, Any]], eliminated: set[str], new_candidates: Sequence[Mapping[str, Any]], temporal_evidence: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    support_ids = sorted({str(x.get("person_id")) for x in supports if x.get("person_id") and str(x.get("person_id")) not in eliminated})
    surviving = [x for x in candidates if not x.get("person_id") or str(x.get("person_id")) not in eliminated]
    if len(support_ids) > 1:
        status = "conflict"
    elif len(support_ids) == 1:
        status = "resolved_existing"
    elif new_candidates and len(new_candidates) == 1:
        status = "resolved_new_candidate"
    elif len(surviving) > 1 and (len(surviving) < len(before) or surviving):
        status = "narrowed"
    else:
        status = "unresolved"
    bases = sorted({str(x.get("basis")) for x in supports if x.get("basis")})
    basis = bases[0] if len(bases) == 1 else ("new_candidate" if status == "resolved_new_candidate" else "unresolved")
    return {"case_id": case.get("case_id"), "status": status, "candidate_set_before": [x.get("person_id") for x in before if x.get("person_id")], "candidate_set_after": [x.get("person_id") or x.get("candidate_key") for x in surviving], "resolved_person_id": support_ids[0] if len(support_ids) == 1 and status == "resolved_existing" else None, "new_entity_label": new_candidates[0].get("canonical_candidate_label") if status == "resolved_new_candidate" else None, "identity_resolution_basis": basis, "identity_support": list(supports), "new_candidate_support": list(new_candidates), "temporal_eliminations": sorted(eliminated), "temporal_hard_evidence": list(temporal_evidence), "candidate_only": True, "canonical_write_back": False}


def _unblocked(case: Mapping[str, Any], decision: Mapping[str, Any], atoms: Sequence[Mapping[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    pid = str(decision.get("resolved_person_id") or "")
    if not pid: return [], []
    obs = {str(x) for x in case.get("observation_ids", [])}; out = []; rejected = []
    for row in [*case.get("blocked_relations", []), *case.get("blocked_kinship", []), *case.get("blocked_marriage", [])]:
        subject_unresolved = str(row.get("subject_ref") or "") in {f"unresolved:{x}" for x in obs}
        object_unresolved = str(row.get("object_ref") or "") in {f"unresolved:{x}" for x in obs}
        if not (subject_unresolved or object_unresolved): continue
        other_pid = row.get("object_person_id") if subject_unresolved else row.get("subject_person_id")
        if not other_pid: continue
        if str(other_pid) == pid:
            rejected.append({"candidate_id": row.get("candidate_id"), "reason": "collapsed_nonidentity_self_relation", "identity_case_id": case.get("case_id"), "resolved_person_id": pid, "original_observation": dict(row), "candidate_only": True, "canonical_write_back": False})
            continue
        out.append({"candidate_id": f"hdb2-unblocked-{stable_hash({'case': case.get('case_id'), 'candidate': row.get('candidate_id'), 'pid': pid})[:20]}", "original_wave": row.get("wave_id"), "original_observation": dict(row), "identity_case_id": case.get("case_id"), "new_identity_support": [dict(x) for x in atoms], "resolved_person_id": pid, "other_person_id": other_pid, "resolution_basis": "evidence_identity_assertion", "candidate_only": True, "canonical_write_back": False, "status": "newly_unblocked_candidate_fact"})
    return out, rejected


def knowledge_delta(case: Mapping[str, Any], atoms: Sequence[Mapping[str, Any]], decision: Mapping[str, Any], passages: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    by = collections.defaultdict(list)
    for atom in atoms:
        kind = str(atom.get("atom_kind") or "")
        if kind == "identity_name": by["identity_evidence"].append(dict(atom))
        elif kind == "kinship": by["kinship_candidates"].append(dict(atom))
        elif kind == "office": by["office_candidates"].append(dict(atom))
        elif kind == "temporal_activity": by["activity_constraints_added"].append(dict(atom))
        elif kind == "location_origin": by["location_evidence"].append(dict(atom))
        else: by["social_observations"].append(dict(atom))
    return {"case_id": case.get("case_id"), "identity_gain": {"resolved_surface": case.get("target_surfaces"), "resolved_person_id": decision.get("resolved_person_id"), "identity_evidence": by["identity_evidence"]}, "temporal_gain": {"activity_constraints_added": by["activity_constraints_added"], "story_time_constraints_supported": []}, "family_gain": {"kinship_candidates": by["kinship_candidates"], "marriage_candidates": []}, "office_gain": {"office_candidates": by["office_candidates"]}, "social_gain": {"newly_unblocked_relations": []}, "source_gain": {"new_source_works": sorted({source_work_for_ref(str(a.get("evidence_ref")), passages) for a in atoms})}, "candidate_only": True, "canonical_write_back": False}


def solve_case(case: Mapping[str, Any], atoms: Sequence[Mapping[str, Any]], passages: Sequence[Mapping[str, Any]], catalog: Mapping[str, Mapping[str, Any]] | None = None) -> dict[str, Any]:
    catalog = catalog or hng02.person_catalog(); index = resolver.forms_index(catalog)
    before, candidates, supports = _candidate_rows(case, atoms, catalog, index)
    new_candidates = [x for x in candidates if x.get("person_id") is None]
    eliminated, temporal_evidence = _temporal_eliminations(case, candidates)
    constraints = _constraint_rows(atoms, case, catalog, index, supports)
    decision = _decision(case, before, candidates, supports, eliminated, new_candidates, temporal_evidence)
    unblocked, self_rejections = _unblocked(case, decision, atoms)
    delta = {"candidate_count_before": len(before), "candidate_count_after": len(decision.get("candidate_set_after", [])), "added_candidates": [x for x in candidates if x not in before], "upgraded_candidates": [], "added_constraints": constraints, "preserved_constraints": [], "changed_constraints": [], "identity_propagations": list(supports), "new_evidence": list(atoms), "conflicts": temporal_evidence}
    delta["candidates_eliminated_temporal"] = len(eliminated); delta["candidates_eliminated_kinship"] = 0; delta["candidates_eliminated_office"] = 0; delta["candidates_eliminated_identity_conflict"] = 1 if decision.get("status") == "conflict" else 0
    delta["newly_unblocked_count"] = len(unblocked)
    delta["collapsed_nonidentity_self_relations"] = list(self_rejections)
    knowledge = knowledge_delta(case, atoms, decision, passages); knowledge["social_gain"]["newly_unblocked_relations"] = unblocked
    return {"case_id": case.get("case_id"), "case": dict(case), "atoms": list(atoms), "constraints": constraints, "candidates": candidates, "decision": decision, "state_delta": delta, "newly_unblocked_candidate_facts": unblocked, "rejected_relations": self_rejections, "person_knowledge_delta": knowledge, "candidate_only": True, "canonical_write_back": False}


def solve_run(run_dir: Path, selection: Mapping[str, Any] | None = None) -> dict[str, Any]:
    selection = selection or read_json(ANNOTATION / "hdb2-p1-selection.json", {}) or {}
    live = read_json(run_dir / "case-results.json", {}) or {}
    rows = live.get("cases", live if isinstance(live, list) else [])
    catalog = hng02.person_catalog()
    results = []
    for row in rows:
        case = row.get("case") or {}
        atoms = row.get("validated_atoms", [])
        passages = row.get("all_passages", [])
        results.append(solve_case(case, atoms, passages, catalog))
    return {"schema": "hdb2-p1-constraint-results-v1", "run_id": live.get("run_id"), "candidate_only": True, "canonical_write_back": False, "cases": results, "selection_hash": selection.get("selection_hash")}


def main() -> int:
    parser = argparse.ArgumentParser(); parser.add_argument("run_dir", type=Path); parser.add_argument("--output", type=Path)
    args = parser.parse_args(); result = solve_run(args.run_dir)
    output = args.output or args.run_dir / "constraint-results.json"; write_json(output, result); print(f"solved {len(result['cases'])} cases")
    return 0


if __name__ == "__main__": raise SystemExit(main())
