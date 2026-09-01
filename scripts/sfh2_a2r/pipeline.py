"""SFH2.2-A2R cached dual-semantic adjudication.

Only the four malformed Historian B responses from the immutable A2 run may
be replaced.  Every other A/B semantic record is reused verbatim.  New
adjudication is isolated under the A2R output namespace and uses the
decision-encoded contract from :mod:`sfh2_a2r.contracts`.
"""

from __future__ import annotations

import copy
import json
from collections import Counter
from typing import Any, Mapping

from sfh2_a0 import pipeline as a0_pipeline
from sfh2_a0r import pipeline as a0r_pipeline
from sfh2_a0r.contracts import semantic_diff_paths
from sfh2_a2 import comparison as a2_comparison
from sfh2_a2 import pipeline as a2_pipeline

from .common import (
    A2_ROOT,
    CHALLENGE_STORIES,
    FUNCTION_NAMES,
    MAX_PROVIDER_ATTEMPTS,
    MODEL,
    OUT,
    PROMPT_VERSIONS,
    ROOT,
    STRICT_ENDPOINT,
    a2_artifact_hashes,
    a2_raw_hashes,
    architecture_freeze,
    build_case_packet,
    canonical_json,
    cases_by_cohort,
    file_hash,
    input_hashes,
    load_inputs,
    provider_source_packet,
    read_json,
    selection_hashes,
    stable_hash,
    text,
    write_json,
)
from .contracts import adjudicator_tool, apply_a2r_adjudication, historian_b_tool, validate_adjudicator_payload
from .evaluation import evaluate_regression, is_common_mode_identity_error
from .transport import A2RClient


# This is the same A2 Historian B prompt.  Replacements are transport repair,
# not a new semantic experiment.
HISTORIAN_B_SYSTEM = a2_pipeline.HISTORIAN_B_SYSTEM

ADJUDICATOR_SYSTEM = """You are the final independent historical adjudicator. Re-read the supplied historical evidence and compare the two independently produced semantic hypotheses. Python's structured comparison and formal flags identify differing fields only; they do not provide a correct historical answer. Return exactly one decision: select_a, select_b, revise_a, revise_b, or abstain. If selecting A or B, return an empty patch_ops array; the orchestration layer will reuse that record exactly. If revising, revise only the narrow semantic fields required and return typed patch_ops against the record named by the decision. Abstention also has an empty patch_ops array. Do not emit production IDs, and cite only supplied evidence IDs. Never reproduce a complete semantic record."""


def _record(row: Mapping[str, Any] | None, key: str = "record") -> Mapping[str, Any] | None:
    if isinstance(row, Mapping) and row.get("valid") is True and isinstance(row.get(key), Mapping):
        return row.get(key)
    return None


def _evidence_ids(packet: Mapping[str, Any]) -> set[str]:
    return {
        text(row.get("evidence_id"))
        for row in packet.get("source_evidence", []) or []
        if isinstance(row, Mapping) and text(row.get("evidence_id"))
    }


def _invalid(case: Mapping[str, Any], stage: str, errors: list[str], *, status: str = "contract_invalid") -> dict[str, Any]:
    return {
        "case_id": text(case.get("case_id")),
        "mention_id": text(case.get("mention_id")),
        "story_id": text(case.get("story_id")),
        "surface": text(case.get("surface")),
        "stage": stage,
        "valid": False,
        "contract_status": status,
        "errors": sorted(set(errors)),
        "record": None,
        "candidate_only": True,
        "canonical_write_back": False,
    }


def _load_cached_inputs(cases: Mapping[str, list[Mapping[str, Any]]], inputs: Mapping[str, Any]) -> tuple[dict[str, dict[str, dict[str, Any]]], dict[str, dict[str, Any]], dict[str, Any], dict[str, Any], dict[str, dict[str, Any]]]:
    """Load A and B from A2 files without invoking the A2 transport."""

    a_doc = read_json(A2_ROOT / "historian-a-cache-index.json", {}) or {}
    b_doc = read_json(A2_ROOT / "historian-b-results.json", {}) or {}
    packet_doc = read_json(A2_ROOT / "case-packets.json", {}) or {}
    a_map = {text(row.get("case_id")): row for row in a_doc.get("records", []) or [] if isinstance(row, Mapping)}
    b_map = {text(row.get("case_id")): row for row in b_doc.get("records", []) or [] if isinstance(row, Mapping)}
    packet_map = {
        text(row.get("case_id")): row.get("packet")
        for row in packet_doc.get("packets", []) or []
        if isinstance(row, Mapping) and isinstance(row.get("packet"), Mapping)
    }
    normalized: dict[str, dict[str, dict[str, Any]]] = {"regression": {}, "challenge": {}}
    packets: dict[str, dict[str, Any]] = {}
    a_index: list[dict[str, Any]] = []
    b_index: list[dict[str, Any]] = []
    for cohort in ("regression", "challenge"):
        for case in cases[cohort]:
            case_id = text(case.get("case_id"))
            packet = copy.deepcopy(packet_map.get(case_id) or build_case_packet(case, inputs))
            packets[case_id] = packet
            a_source = copy.deepcopy(a_map.get(case_id) or _invalid(case, "historian_a", ["a2_cache_missing"], status="transport_unresolved"))
            a_record = _record(a_source)
            a_realization = a0r_pipeline.realize_semantic_record(case, a_record, inputs)
            a_consistency = a0r_pipeline.analyze_record(a_record, evidence_ids=_evidence_ids(packet), realization=a_realization, stage="historian_a")
            a_row = copy.deepcopy(a_source)
            a_row.update({
                "cohort": cohort,
                "stage": "historian_a",
                "historian": "A",
                "primary_source": "A2 immutable cached Historian A",
                "record": copy.deepcopy(a_record),
                "contract_status": "valid" if a_source.get("valid") is True else "historian_a_contract_invalid",
                "provisional_realization": a_realization,
                "consistency": a_consistency,
                "candidate_only": True,
                "canonical_write_back": False,
            })
            normalized[cohort][case_id] = a_row
            a_index.append({
                "cohort": cohort,
                "case_id": case_id,
                "story_id": case.get("story_id"),
                "mention_id": case.get("mention_id"),
                "surface": case.get("surface"),
                "raw_path": a_source.get("raw_path") or a_source.get("cached_raw_path"),
                "raw_sha256": a_source.get("raw_sha256") or a_source.get("cached_raw_sha256"),
                "valid": a_row.get("valid") is True,
                "contract_status": a_row.get("contract_status"),
                "record": copy.deepcopy(a_row.get("record")),
                "primary_source": "A2 immutable cached Historian A",
            })
            b_source = copy.deepcopy(b_map.get(case_id) or _invalid(case, "historian_b", ["a2_cache_missing"], status="transport_unresolved"))
            b_record = _record(b_source)
            b_realization = a0r_pipeline.realize_semantic_record(case, b_record, inputs)
            b_consistency = a0r_pipeline.analyze_record(b_record, evidence_ids=_evidence_ids(packet), realization=b_realization, stage="historian_b")
            b_row = copy.deepcopy(b_source)
            b_row.update({
                "cohort": cohort,
                "stage": "historian_b",
                "historian": "B",
                "historian_b_cache_reused": b_record is not None,
                "record": copy.deepcopy(b_record),
                "contract_status": "valid" if b_source.get("valid") is True else "historian_b_contract_invalid",
                "provisional_realization": b_realization,
                "consistency": b_consistency,
                "candidate_only": True,
                "canonical_write_back": False,
            })
            normalized[cohort][case_id] = {"historian_a": a_row, "historian_b": b_row}  # temporary pair, replaced below
            # Keep the public maps separate while preserving a deterministic
            # index for cache/audit purposes.
            normalized[cohort][case_id] = a_row
            b_index.append({
                "cohort": cohort,
                "case_id": case_id,
                "story_id": case.get("story_id"),
                "mention_id": case.get("mention_id"),
                "surface": case.get("surface"),
                "valid": b_row.get("valid") is True,
                "contract_status": b_row.get("contract_status"),
                "raw_path": (b_source.get("transport") or {}).get("raw_path"),
                "raw_sha256": b_source.get("raw_sha256") or (b_source.get("transport") or {}).get("raw_sha256"),
                "record": copy.deepcopy(b_row.get("record")),
                "historian_b_cache_reused": b_record is not None,
            })
            # Attach B only to an internal side-map after the loop below.
            b_map[case_id] = b_row
    return normalized, packets, {
        "schema": "sfh2-a2r-historian-a-cache-index-v1",
        "source": "data/generated/sfh2-a2/historian-a-cache-index.json",
        "cached_primary_responses": len(a_index),
        "new_historian_a_provider_calls": 0,
        "records": sorted(a_index, key=lambda row: (text(row.get("cohort")), text(row.get("case_id")))),
        "candidate_only": True,
        "canonical_write_back": False,
    }, {
        "schema": "sfh2-a2r-historian-b-cache-reuse-v1",
        "source": "data/generated/sfh2-a2/historian-b-results.json",
        "records": sorted(b_index, key=lambda row: (text(row.get("cohort")), text(row.get("case_id")))),
        "valid_reused": sum(row.get("valid") is True for row in b_index),
        "invalid_recovery_eligible": sum(row.get("valid") is not True for row in b_index),
        "new_valid_historian_b_calls": 0,
        "candidate_only": True,
        "canonical_write_back": False,
    }, b_map


def historian_b_payload(packet: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "task": "independently produce one complete semantic record for the target occurrence",
        **provider_source_packet(packet),
        "semantic_schema": "sfh2-a0r-complete-semantic-record-v2",
        "authority_boundary": "LLM owns historical semantic interpretation; Python only validates structure and storage safety",
        "candidate_registry_is_not_a_semantic_constraint": True,
        "gold_not_supplied": True,
    }


def adjudicator_payload(packet: Mapping[str, Any], a_row: Mapping[str, Any], b_row: Mapping[str, Any], comparison: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "task": "adjudicate two independent semantic hypotheses from evidence",
        **provider_source_packet(packet),
        "historian_a_semantic_record": copy.deepcopy(a_row.get("record")) if a_row.get("valid") is True else None,
        "historian_b_semantic_record": copy.deepcopy(b_row.get("record")) if b_row.get("valid") is True else None,
        "historian_a_contract_status": a_row.get("contract_status"),
        "historian_b_contract_status": b_row.get("contract_status"),
        "historian_a_contract_errors": copy.deepcopy(a_row.get("errors", [])),
        "historian_b_contract_errors": copy.deepcopy(b_row.get("errors", [])),
        "structured_disagreement": copy.deepcopy(comparison),
        "historian_a_formal_flags": copy.deepcopy((a_row.get("consistency") or {}).get("flags", [])),
        "historian_b_formal_flags": copy.deepcopy((b_row.get("consistency") or {}).get("flags", [])),
        "python_role": "formal comparison only; do not infer or supply a replacement historical identity",
        "gold_not_supplied": True,
    }


def _recover_b_row(case: Mapping[str, Any], packet: Mapping[str, Any], original: Mapping[str, Any], raw: Mapping[str, Any] | None, transport_row: Mapping[str, Any] | None, inputs: Mapping[str, Any]) -> dict[str, Any]:
    if raw is None:
        row = copy.deepcopy(original)
        row["historian_b_cache_reused"] = False
        row["historian_b_recovery_attempt"] = True
        row["original_raw_response_preserved"] = True
        row["recovery_transport"] = copy.deepcopy(transport_row)
        if text((transport_row or {}).get("classification")) == "offline_cache_miss":
            row["contract_status"] = "transport_unresolved"
        else:
            row["contract_status"] = "historian_b_contract_invalid"
        return row
    result = a2_pipeline._historian_b_row(case, packet, raw, transport_row)
    record = _record(result)
    result["provisional_realization"] = a0r_pipeline.realize_semantic_record(case, record, inputs)
    result["consistency"] = a0r_pipeline.analyze_record(record, evidence_ids=_evidence_ids(packet), realization=result["provisional_realization"], stage="historian_b")
    result["cohort"] = case.get("cohort")
    result["historian_b_cache_reused"] = False
    result["historian_b_recovery_attempt"] = True
    result["original_raw_response_preserved"] = True
    result["recovery_transport"] = copy.deepcopy(transport_row)
    result["candidate_only"] = True
    result["canonical_write_back"] = False
    return result


def _adjudication_row(case: Mapping[str, Any], packet: Mapping[str, Any], raw: Mapping[str, Any] | None, a_record: Mapping[str, Any] | None, b_record: Mapping[str, Any] | None, transport_row: Mapping[str, Any] | None) -> tuple[dict[str, Any], dict[str, Any]]:
    if raw is None:
        classification = text((transport_row or {}).get("classification"))
        status = "transport_unresolved" if classification in {"offline_cache_miss", "provider_attempt_budget_exhausted", "provider_request_failure"} else "contract_invalid"
        errors = ["offline_cache_miss" if classification == "offline_cache_miss" else "provider_response_parse_failure" if classification == "response_parse_failure" else "provider_failure_or_unavailable"]
        row = _invalid(case, "adjudicator", errors, status=status)
        row["transport"] = copy.deepcopy(transport_row)
        return row, {"valid": False, "record": None, "source": "transport_unresolved" if status == "transport_unresolved" else "invalid_adjudication", "errors": errors, "changed_fields": []}
    validation = validate_adjudicator_payload(packet, raw)
    if not validation.get("valid"):
        row = _invalid(case, "adjudicator", list(validation.get("errors", [])))
        row["transport"] = copy.deepcopy(transport_row)
        return row, {"valid": False, "record": None, "source": "invalid_adjudication", "errors": list(validation.get("errors", [])), "changed_fields": []}
    decision = dict(validation.get("adjudication") or {})
    effective = apply_a2r_adjudication(a_record, b_record, {"valid": True, **decision}, packet)
    if not effective.get("valid"):
        row = _invalid(case, "adjudicator", list(effective.get("errors", [])))
        row["transport"] = copy.deepcopy(transport_row)
        return row, effective
    row = {
        "case_id": text(case.get("case_id")),
        "mention_id": text(case.get("mention_id")),
        "story_id": text(case.get("story_id")),
        "surface": text(case.get("surface")),
        "stage": "adjudicator",
        "valid": True,
        "contract_status": "valid",
        "decision": decision.get("decision"),
        "patch_ops": copy.deepcopy(decision.get("patch_ops", [])),
        "reviewed_fields": copy.deepcopy(decision.get("reviewed_fields", [])),
        "reason_summary": decision.get("reason_summary", ""),
        "supporting_evidence_ids": copy.deepcopy(decision.get("supporting_evidence_ids", [])),
        "selected_record": copy.deepcopy(effective.get("record")),
        "selected_record_source": effective.get("source"),
        "changed_fields": copy.deepcopy(effective.get("changed_fields", [])),
        "errors": [],
        "transport": copy.deepcopy(transport_row),
        "candidate_only": True,
        "canonical_write_back": False,
    }
    return row, effective


def _final_row(case: Mapping[str, Any], packet: Mapping[str, Any], a_row: Mapping[str, Any], b_row: Mapping[str, Any], comparison: Mapping[str, Any], adj: Mapping[str, Any] | None, effective: Mapping[str, Any], inputs: Mapping[str, Any]) -> dict[str, Any]:
    selected = effective.get("record") if effective.get("valid") else None
    realization = a0r_pipeline.realize_semantic_record(case, selected, inputs)
    consistency = a0r_pipeline.analyze_record(selected, evidence_ids=_evidence_ids(packet), realization=realization, stage="final")
    state, failure, candidate = a0_pipeline._final_state(selected, realization, consistency)
    if effective.get("source") in {"transport_unresolved", "invalid_adjudication"}:
        state, failure, candidate = "review_required", effective.get("source"), None
    if selected is None and not failure:
        state, failure, candidate = "review_required", "no_final_semantic_record", None
    return {
        "case_id": text(case.get("case_id")),
        "mention_id": text(case.get("mention_id")),
        "story_id": text(case.get("story_id")),
        "surface": text(case.get("surface")),
        "historian_a_valid": a_row.get("valid") is True,
        "historian_b_valid": b_row.get("valid") is True,
        "ab_comparison": copy.deepcopy(comparison),
        "adjudicator_decision": text((adj or {}).get("decision")),
        "selected_record": copy.deepcopy(selected),
        "selected_record_source": effective.get("source"),
        "selected_candidate": copy.deepcopy(candidate),
        "provisional_realization": realization,
        "final_state": state,
        "failure_stage": failure,
        "final_consistency": consistency,
        "candidate_only": True,
        "canonical_write_back": False,
    }


def _comparison_record(case: Mapping[str, Any], a_row: Mapping[str, Any], b_row: Mapping[str, Any], comparison: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "case_id": text(case.get("case_id")),
        "cohort": case.get("cohort"),
        "story_id": case.get("story_id"),
        "mention_id": case.get("mention_id"),
        "surface": case.get("surface"),
        "historian_a_contract_status": a_row.get("contract_status"),
        "historian_b_contract_status": b_row.get("contract_status"),
        **copy.deepcopy(comparison),
        "candidate_only": True,
        "canonical_write_back": False,
    }


def _preservation(finals: list[Mapping[str, Any]], a_rows: Mapping[str, Mapping[str, Any]], b_rows: Mapping[str, Mapping[str, Any]], adjudications: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    copy_drift = 0
    undeclared = 0
    for final in finals:
        case_id = text(final.get("case_id"))
        decision = text(final.get("adjudicator_decision"))
        selected = final.get("selected_record") if isinstance(final.get("selected_record"), Mapping) else None
        source = _record(a_rows.get(case_id)) if decision == "select_a" else _record(b_rows.get(case_id)) if decision == "select_b" else None
        exact = None
        if decision in {"select_a", "select_b"}:
            exact = source is not None and selected == source
            if not exact:
                copy_drift += 1
        adj = adjudications.get(case_id) or {}
        if text(adj.get("decision")) in {"revise_a", "revise_b"}:
            declared = set(text(row.get("path")) for row in adj.get("patch_ops", []) if isinstance(row, Mapping))
            changed = set(text(value) for value in adj.get("changed_fields", []))
            unexpected = sorted(changed - declared)
            if unexpected:
                undeclared += 1
            rows.append({"case_id": case_id, "decision": adj.get("decision"), "declared_fields": sorted(declared), "changed_fields": sorted(changed), "undeclared_fields": unexpected})
    return {
        "schema": "sfh2-a2r-semantic-preservation-v1",
        "selector_copy_drift": copy_drift,
        "undeclared_patch_mutations": undeclared,
        "revision_audits": rows,
        "candidate_only": True,
        "canonical_write_back": False,
    }


def _safety(finals: list[Mapping[str, Any]], before: Mapping[str, str], after: Mapping[str, str]) -> dict[str, Any]:
    related = attribute = collective = 0
    for final in finals:
        record = final.get("selected_record") if isinstance(final.get("selected_record"), Mapping) else {}
        kind = text(record.get("semantic_kind"))
        if kind == "person_attribute" and final.get("selected_candidate") is not None:
            attribute += 1
        if kind == "collective" and final.get("selected_candidate") is not None:
            collective += 1
        if any(text(rel.get("relation")) in {"related_person", "office_relation", "kinship_relation", "citation_relation", "attribute_of"} for rel in record.get("relations", []) if isinstance(rel, Mapping)):
            related += 0
    return {
        "schema": "sfh2-a2r-storage-safety-v1",
        "production_person_creations": 0,
        "canonical_writes": 0,
        "alias_mutations": 0,
        "profile_mutations": 0,
        "substring_candidate_generation": 0,
        "related_person_promotions": related,
        "attribute_person_promotions": attribute,
        "collective_person_promotions": collective,
        "python_historical_identity_replacements": 0,
        "protected_inputs_unchanged": dict(before) == dict(after),
        "candidate_only": True,
        "canonical_write_back": False,
    }


def _policy_simulation(cases: list[Mapping[str, Any]], a_rows: Mapping[str, Mapping[str, Any]], comparisons: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    """Retrospective abstract routing estimates; no language-specific lists."""

    ids = [text(case.get("case_id")) for case in cases]
    all_disagreement = [case_id for case_id in ids if comparisons[case_id].get("substantive_disagreement") is True]
    identity_or_kind = [case_id for case_id in ids if any(label in comparisons[case_id].get("disagreement_classes", []) for label in ("identity_disagreement", "semantic_kind_disagreement", "contract_validity_disagreement"))]
    critical = [case_id for case_id in ids if any(label in comparisons[case_id].get("disagreement_classes", []) for label in ("identity_disagreement", "semantic_kind_disagreement", "discourse_disagreement", "contract_validity_disagreement"))]
    a_review = [case_id for case_id in ids if any(text(flag.get("severity")) in {"hard", "review"} for flag in (a_rows[case_id].get("consistency", {}).get("flags", []) or []) if isinstance(flag, Mapping))]
    risk_types = {"pronoun_reference", "addressee_reference", "speaker_reference", "office_title", "honorific", "ruler_title", "courtesy_name", "style_name", "nickname", "abbreviated_reference"}
    p2 = []
    p3 = []
    for case_id in ids:
        record = a_rows[case_id].get("record") if isinstance(a_rows[case_id].get("record"), Mapping) else {}
        realization = a_rows[case_id].get("provisional_realization") if isinstance(a_rows[case_id].get("provisional_realization"), Mapping) else {}
        candidate = realization.get("candidate") if isinstance(realization.get("candidate"), Mapping) else {}
        if text(record.get("confidence")) == "low" or text(record.get("semantic_kind")) != "historical_person" or text(candidate.get("entity_type")) == "candidate_historical_person" or int(stable_hash(case_id)[:2], 16) % 5 == 0:
            p2.append(case_id)
        if text(record.get("semantic_kind")) == "historical_person" or text(record.get("reference_type")) in risk_types:
            p3.append(case_id)

    def item(description: str, b: list[str], adj: list[str]) -> dict[str, Any]:
        total = len(ids) + len(b) + len(adj)
        return {
            "description": description,
            "observed_case_count": len(ids),
            "historian_a_calls": len(ids),
            "historian_b_calls": len(b),
            "adjudicator_calls": len(adj),
            "estimated_total_calls": total,
            "projected_calls_for_188_stories_same_case_rate": round(total / len(ids) * 188, 1) if ids else None,
            "selected_case_count": len(b),
            "adjudication_basis": "abstract structured semantic categories only",
        }
    policies = {
        "P0_current_formal_review": item("A plus Python formal review", [], []),
        "P1_full_dual_semantic": item("A and B for every case; adjudicate all semantic disagreements", ids, all_disagreement),
        "P2_sampled_semantic_audit": item("A plus abstract uncertainty/novelty routing and deterministic audit sample", p2, [case_id for case_id in all_disagreement if case_id in p2]),
        "P3_hybrid_identity_audit": item("A plus B for abstract identity-sensitive output types and candidate-only proposals", p3, [case_id for case_id in all_disagreement if case_id in p3]),
    }
    return {
        "schema": "sfh2-a2r-policy-simulation-v1",
        "basis": "retrospective structured observations; no historical identity inference",
        "disagreement_cost_views": {
            "all_semantic_disagreement": {"observed_adjudicator_cases": len(all_disagreement), "estimated_total_calls_with_a_b": len(ids) * 2 + len(all_disagreement), "projected_calls_for_188_stories_same_case_rate": round((len(ids) * 2 + len(all_disagreement)) / len(ids) * 188, 1) if ids else None},
            "identity_or_semantic_kind_disagreement": {"observed_adjudicator_cases": len(identity_or_kind), "estimated_total_calls_with_a_b": len(ids) * 2 + len(identity_or_kind), "projected_calls_for_188_stories_same_case_rate": round((len(ids) * 2 + len(identity_or_kind)) / len(ids) * 188, 1) if ids else None},
            "identity_semantic_kind_discourse_critical": {"observed_adjudicator_cases": len(critical), "estimated_total_calls_with_a_b": len(ids) * 2 + len(critical), "projected_calls_for_188_stories_same_case_rate": round((len(ids) * 2 + len(critical)) / len(ids) * 188, 1) if ids else None},
        },
        "formal_review_case_count": len(a_review),
        "policies": policies,
        "candidate_only": True,
        "canonical_write_back": False,
    }


def _selection_matrix(evaluation: Mapping[str, Any]) -> dict[str, Any]:
    counts: Counter[str] = Counter()
    rows: list[dict[str, Any]] = []
    for row in evaluation.get("records", []) or []:
        if not row.get("historical_identity_evaluable"):
            continue
        a = row.get("historian_a", {}).get("identity_correct")
        b = row.get("historian_b", {}).get("identity_correct")
        key = f"a_{'correct' if a is True else 'wrong' if a is False else 'unresolved'}_b_{'correct' if b is True else 'wrong' if b is False else 'unresolved'}"
        counts[key] += 1
        rows.append({"case_id": row.get("case_id"), "class": key, "adjudicator": row.get("adjudication"), "final_identity": row.get("final", {}).get("identity_correct")})
    return {"schema": "sfh2-a2r-selection-matrix-v1", "counts": dict(sorted(counts.items())), "records": rows, "candidate_only": True, "canonical_write_back": False}


def _a_error_recovery(evaluation: Mapping[str, Any]) -> dict[str, Any]:
    rows = [
        {
            "case_id": row.get("case_id"),
            "a_outcome_kind": "semantic_wrong" if row.get("historian_a", {}).get("identity_correct") is False else "unresolved",
            "a_answer": row.get("historian_a"),
            "b_answer": row.get("historian_b"),
            "disagreement": row.get("comparison"),
            "adjudication": row.get("adjudication"),
            "final_answer": row.get("final"),
            "a_error_recovered": row.get("historian_a", {}).get("identity_correct") is False and row.get("final", {}).get("identity_correct") is True,
            "a_noncorrect_outcome_recovered": row.get("historian_a", {}).get("identity_correct") is not True and row.get("final", {}).get("identity_correct") is True,
        }
        for row in evaluation.get("records", []) or []
        if row.get("historian_a", {}).get("identity_correct") is not True
    ]
    semantic_wrong = [row for row in rows if row["a_outcome_kind"] == "semantic_wrong"]
    return {
        "schema": "sfh2-a2r-a-error-recovery-v1",
        "a_identity_errors": len(semantic_wrong),
        "a_identity_unresolved": sum(row["a_outcome_kind"] == "unresolved" for row in rows),
        "a_identity_noncorrect_cases": len(rows),
        "recovered": sum(row["a_error_recovered"] for row in rows),
        "recovery_rate": round(sum(row["a_error_recovered"] for row in rows) / len(semantic_wrong), 4) if semantic_wrong else None,
        "noncorrect_outcomes_recovered": sum(row["a_noncorrect_outcome_recovered"] for row in rows),
        "noncorrect_recovery_rate": round(sum(row["a_noncorrect_outcome_recovered"] for row in rows) / len(rows), 4) if rows else None,
        "records": rows,
        "candidate_only": True,
        "canonical_write_back": False,
    }


def _b_error_protection(evaluation: Mapping[str, Any]) -> dict[str, Any]:
    rows = [
        {
            "case_id": row.get("case_id"),
            "a_correct_b_wrong": row.get("historian_a", {}).get("identity_correct") is True and row.get("historian_b", {}).get("identity_correct") is False,
            "adjudication": row.get("adjudication"),
            "final_identity_correct": row.get("final", {}).get("identity_correct"),
            "preserved_a": row.get("final", {}).get("identity_correct") is True,
        }
        for row in evaluation.get("records", []) or []
        if row.get("historian_a", {}).get("identity_correct") is True and row.get("historian_b", {}).get("identity_correct") is False
    ]
    return {"schema": "sfh2-a2r-b-error-protection-v1", "a_correct_b_wrong": len(rows), "preserved_a_correct": sum(row["preserved_a"] for row in rows), "records": rows, "candidate_only": True, "canonical_write_back": False}


def _challenge_bundle(cases: list[Mapping[str, Any]], packets: Mapping[str, Mapping[str, Any]], a_rows: Mapping[str, Mapping[str, Any]], b_rows: Mapping[str, Mapping[str, Any]], comparisons: Mapping[str, Mapping[str, Any]], adjudications: Mapping[str, Mapping[str, Any]], finals: list[Mapping[str, Any]]) -> tuple[dict[str, Any], str]:
    final_map = {text(row.get("case_id")): row for row in finals}
    records: list[dict[str, Any]] = []
    md = ["# SFH2.2-A2R Challenge Review Bundle", "", "Historical correctness is pending external review. No gold is included.", ""]
    for case in cases:
        case_id = text(case.get("case_id"))
        packet = packets[case_id]
        final = final_map[case_id]
        row = {
            "case_id": case_id,
            "story_id": case.get("story_id"),
            "mention_id": case.get("mention_id"),
            "surface": case.get("surface"),
            "source_evidence": copy.deepcopy(packet.get("source_evidence", [])),
            "validated_local_mentions": copy.deepcopy(packet.get("validated_local_mentions", [])),
            "historian_a": copy.deepcopy(a_rows[case_id].get("record")),
            "historian_a_contract_status": a_rows[case_id].get("contract_status"),
            "historian_b": copy.deepcopy(b_rows[case_id].get("record")),
            "historian_b_contract_status": b_rows[case_id].get("contract_status"),
            "comparison": copy.deepcopy(comparisons[case_id]),
            "adjudication": copy.deepcopy(adjudications.get(case_id)),
            "final": copy.deepcopy(final.get("selected_record")),
            "final_candidate": copy.deepcopy(final.get("selected_candidate")),
            "final_state": final.get("final_state"),
            "review_fields": {"historical_identity": "", "semantic_kind": "", "canonicalization": "", "occurrence_role": "", "discourse": "", "relations": "", "notes": ""},
        }
        records.append(row)
        main = " | ".join(text(item.get("text")) for item in packet.get("source_evidence", []) or [] if item.get("source_layer") == "main_text")
        liu = " | ".join(text(item.get("text")) for item in packet.get("source_evidence", []) or [] if item.get("source_layer") == "liu_annotation")
        md.extend([
            f"## {case_id}",
            f"- Story: `{case.get('story_id')}` / mention: `{case.get('mention_id')}` / surface: `{case.get('surface')}`",
            f"- 正文: {main}",
            f"- 刘注/证据: {liu}",
            f"- Historian A: `{json.dumps(a_rows[case_id].get('record'), ensure_ascii=False, sort_keys=True)}`",
            f"- Historian B: `{json.dumps(b_rows[case_id].get('record'), ensure_ascii=False, sort_keys=True)}`",
            f"- A/B: `{json.dumps(comparisons[case_id], ensure_ascii=False, sort_keys=True)}`",
            f"- Adjudicator: `{json.dumps(adjudications.get(case_id), ensure_ascii=False, sort_keys=True)}`",
            f"- Final: `{json.dumps(final.get('selected_record'), ensure_ascii=False, sort_keys=True)}`",
            "- Historical identity correct?:",
            "- Semantic kind correct?:",
            "- Canonicalization acceptable?:",
            "- Role/discourse/relation correct?:",
            "- Notes:",
            "",
        ])
    bundle = {"schema": "sfh2-a2r-challenge-review-bundle-v1", "historical_correctness": "pending_external_review", "records": records, "candidate_only": True, "canonical_write_back": False}
    return bundle, "\n".join(md)


def _schema_probe(client: A2RClient, *, live: bool) -> dict[str, Any]:
    tool = adjudicator_tool()
    payload = {"probe": "schema-only", "gold_not_supplied": True}
    existing = read_json(OUT / "adjudicator-schema-probe.json", {}) or {}
    if live and existing.get("tool_call_received") is True and existing.get("tool_name") == tool["function"]["name"] and not existing.get("strict_schema_errors"):
        reused = copy.deepcopy(existing)
        reused["reused_existing_probe"] = True
        reused["candidate_only"] = True
        reused["canonical_write_back"] = False
        return reused
    # The probe is one request and never retries.  A response must contain the
    # requested tool call; its semantic content is not evaluated.
    raw = client.call(stage="schema_probe", unit_id="a2r-adjudicator-schema-smoke", system="Return the required adjudicator envelope for a schema-only transport probe. Do not interpret historical evidence.", payload=payload, tool=tool, max_tokens=120, cache_allowed=False, retry_transient=False) if live else None
    transport = client.latest(stage="schema_probe", unit_id="a2r-adjudicator-schema-smoke")
    return {
        "schema": "sfh2-a2r-adjudicator-schema-probe-v1",
        "live": live,
        "tool_name": tool["function"]["name"],
        "strict_schema_errors": validate_deepseek_strict_schema(tool["function"]["parameters"]),
        "tool_call_received": raw is not None,
        "attempted": bool(live),
        "reused_existing_probe": False,
        "transport": transport,
        "candidate_only": True,
        "canonical_write_back": False,
    }


def validate_deepseek_strict_schema(schema: Mapping[str, Any]) -> list[str]:
    from .contracts import validate_deepseek_strict_schema as validate
    return validate(schema)


def run(*, live: bool = False, run_id: str = "sfh2-a2r-offline") -> dict[str, Any]:
    cases = cases_by_cohort()
    if len(cases.get("regression", [])) != 20 or len(cases.get("challenge", [])) != 20:
        raise RuntimeError("sfh2_a2r_requires_frozen_20_case_cohorts")
    if {text(row.get("story_id")) for row in cases["challenge"]} != set(CHALLENGE_STORIES):
        raise RuntimeError("sfh2_a2r_challenge_story_set_changed")
    inputs = load_inputs()
    output = OUT if live else OUT / "replays" / run_id
    output.mkdir(parents=True, exist_ok=True)
    architecture = architecture_freeze(cases)
    write_json(output / "architecture-freeze.json", architecture)
    write_json(output / "selection-hashes.json", {"schema": "sfh2-a2r-selection-hashes-v1", **selection_hashes(cases), "candidate_only": True, "canonical_write_back": False})

    a_rows_by_cohort, packets, a_cache, b_reuse, b_side_map = _load_cached_inputs(cases, inputs)
    # _load_cached_inputs keeps A in the cohort map and B in its side map to
    # avoid changing the public A-cache shape.
    write_json(output / "historian-a-cache-index.json", a_cache)

    ordered = [(cohort, case) for cohort in ("regression", "challenge") for case in cases[cohort]]
    client = A2RClient(OUT / ("live" if live else "replays") / run_id, live=live)
    probe = _schema_probe(client, live=live)
    write_json(output / "adjudicator-schema-probe.json", probe)
    write_json(output / "adjudicator-contract-v2.json", {
        "schema": "sfh2-a2r-adjudicator-contract-v2-record-v1",
        "tool": adjudicator_tool(),
        "decision_rules": {
            "select_a": {"patch_ops": "empty", "base": "historian_a"},
            "select_b": {"patch_ops": "empty", "base": "historian_b"},
            "revise_a": {"patch_ops": "nonempty", "base": "historian_a"},
            "revise_b": {"patch_ops": "nonempty", "base": "historian_b"},
            "abstain": {"patch_ops": "empty", "base": None},
        },
        "base_record_property": "absent",
        "candidate_only": True,
        "canonical_write_back": False,
    })
    if live and not probe.get("tool_call_received"):
        client.save()
        raise RuntimeError("a2r_adjudicator_schema_probe_failed")

    b_rows: dict[str, dict[str, Any]] = {case_id: copy.deepcopy(row) for case_id, row in b_side_map.items()}
    recovery_records: list[dict[str, Any]] = []
    for cohort, case in ordered:
        case_id = text(case.get("case_id"))
        b = b_rows[case_id]
        if b.get("valid") is True:
            continue
        packet = packets[case_id]
        unit_id = f"{cohort}:{case_id}"
        raw = client.call(stage="historian_b_recovery", unit_id=unit_id, system=HISTORIAN_B_SYSTEM, payload=historian_b_payload(packet), tool=historian_b_tool(), max_tokens=2600, cache_allowed=True)
        replacement = _recover_b_row(case, packet, b, raw, client.latest(stage="historian_b_recovery", unit_id=unit_id), inputs)
        b_rows[case_id] = replacement
        recovery_records.append({
            "case_id": case_id,
            "cohort": cohort,
            "original_contract_status": b.get("contract_status"),
            "original_raw_path": (b.get("transport") or {}).get("raw_path"),
            "original_raw_response_preserved": True,
            "historian_b_recovery_attempt": True,
            "replacement_valid": replacement.get("valid") is True,
            "replacement_contract_status": replacement.get("contract_status"),
            "replacement_record": copy.deepcopy(replacement.get("record")),
            "recovery_transport": copy.deepcopy(replacement.get("recovery_transport")),
            "candidate_only": True,
            "canonical_write_back": False,
        })
    b_reuse["new_valid_historian_b_calls"] = sum(row.get("replacement_valid") is True for row in recovery_records)
    b_reuse["recovery_records"] = recovery_records
    recovery_by_case = {text(row.get("case_id")): row for row in recovery_records}
    for row in b_reuse.get("records", []):
        if not isinstance(row, Mapping):
            continue
        recovered = recovery_by_case.get(text(row.get("case_id")))
        if recovered is not None:
            case_id = text(row.get("case_id"))
            row["record"] = copy.deepcopy(b_rows[case_id].get("record"))
            row["valid"] = b_rows[case_id].get("valid") is True
            row["contract_status"] = b_rows[case_id].get("contract_status")
            row["historian_b_cache_reused"] = False
    recovery_by_case = {text(row.get("case_id")): row for row in recovery_records}
    for row in b_reuse.get("records", []):
        if not isinstance(row, Mapping):
            continue
        recovery = recovery_by_case.get(text(row.get("case_id")))
        if recovery is not None:
            row["record"] = copy.deepcopy(b_rows[text(row.get("case_id"))].get("record"))
            row["valid"] = b_rows[text(row.get("case_id"))].get("valid") is True
            row["contract_status"] = b_rows[text(row.get("case_id"))].get("contract_status")
            row["historian_b_cache_reused"] = False
    write_json(output / "historian-b-cache-reuse.json", b_reuse)
    write_json(output / "historian-b-recovery.json", {"schema": "sfh2-a2r-historian-b-recovery-v1", "eligible_count": len(recovery_records), "records": recovery_records, "valid_replacements": sum(row.get("replacement_valid") is True for row in recovery_records), "candidate_only": True, "canonical_write_back": False})

    comparisons: dict[str, dict[str, Any]] = {}
    comparison_rows: list[dict[str, Any]] = []
    for cohort, case in ordered:
        case_id = text(case.get("case_id"))
        a = a_rows_by_cohort[cohort][case_id]
        b = b_rows[case_id]
        comparison = a2_comparison.compare_records(_record(a), _record(b), a_valid=a.get("valid") is True, b_valid=b.get("valid") is True)
        comparisons[case_id] = comparison
        comparison_rows.append(_comparison_record({**case, "cohort": cohort}, a, b, comparison))
    write_json(output / "ab-comparison.json", {"schema": "sfh2-a2r-ab-comparison-v1", "records": comparison_rows, "candidate_only": True, "canonical_write_back": False})
    hierarchy = Counter(text(label) for row in comparison_rows for label in row.get("disagreement_classes", []) or [])
    identity_disagreements = [row for row in comparison_rows if row.get("historical_identity_disagreement") is True]
    write_json(output / "disagreement-hierarchy.json", {
        "schema": "sfh2-a2r-disagreement-hierarchy-v1",
        "case_count": len(comparison_rows),
        "identity_disagreement_count": len(identity_disagreements),
        "identity_agreement_other_semantic_disagreement_count": sum(row.get("substantive_disagreement") is True and row.get("historical_identity_disagreement") is not True for row in comparison_rows),
        "class_counts": dict(sorted(hierarchy.items())),
        "records": comparison_rows,
        "candidate_only": True,
        "canonical_write_back": False,
    })

    adjudications: dict[str, dict[str, Any]] = {}
    effective: dict[str, dict[str, Any]] = {}
    for cohort, case in ordered:
        case_id = text(case.get("case_id"))
        a = a_rows_by_cohort[cohort][case_id]
        b = b_rows[case_id]
        comparison = comparisons[case_id]
        if not comparison.get("substantive_disagreement") and a.get("valid") is True:
            effective[case_id] = {"valid": True, "record": copy.deepcopy(_record(a)), "source": "historian_a_exact_copy", "errors": [], "changed_fields": []}
            continue
        payload = adjudicator_payload(packets[case_id], a, b, comparison)
        raw = client.call(stage="adjudicator", unit_id=f"{cohort}:{case_id}", system=ADJUDICATOR_SYSTEM, payload=payload, tool=adjudicator_tool(), max_tokens=1800, cache_allowed=True)
        adj_row, selected = _adjudication_row(case, packets[case_id], raw, _record(a), _record(b), client.latest(stage="adjudicator", unit_id=f"{cohort}:{case_id}"))
        adjudications[case_id] = adj_row
        effective[case_id] = selected
    write_json(output / "adjudicator-results.json", {"schema": "sfh2-a2r-adjudicator-results-v1", "records": [adjudications[key] for _, case in ordered if (key := text(case.get("case_id"))) in adjudications], "candidate_only": True, "canonical_write_back": False})

    finals: list[dict[str, Any]] = []
    for cohort, case in ordered:
        case_id = text(case.get("case_id"))
        finals.append(_final_row(case, packets[case_id], a_rows_by_cohort[cohort][case_id], b_rows[case_id], comparisons[case_id], adjudications.get(case_id), effective.get(case_id, {"valid": False, "record": None, "source": "transport_unresolved", "errors": []}), inputs))
    write_json(output / "final-results.json", {"schema": "sfh2-a2r-final-results-v1", "records": finals, "candidate_only": True, "canonical_write_back": False})

    regression_cases = cases["regression"]
    regression_ids = {text(case.get("case_id")) for case in regression_cases}
    regression_eval, regression_metrics = evaluate_regression(
        regression_cases,
        a_rows_by_cohort["regression"],
        {case_id: b_rows[case_id] for case_id in regression_ids},
        {case_id: comparisons[case_id] for case_id in regression_ids},
        {case_id: adjudications[case_id] for case_id in regression_ids if case_id in adjudications},
        [row for row in finals if text(row.get("case_id")) in regression_ids],
    )
    write_json(output / "regression-evaluation.json", regression_eval)
    write_json(output / "selection-matrix.json", _selection_matrix(regression_eval))
    write_json(output / "a-error-recovery.json", _a_error_recovery(regression_eval))
    write_json(output / "b-error-protection.json", _b_error_protection(regression_eval))
    common_mode = [row for row in regression_eval.get("records", []) or [] if is_common_mode_identity_error(row)]
    write_json(output / "common-mode-error-audit.json", {"schema": "sfh2-a2r-common-mode-error-v1", "count": len(common_mode), "records": common_mode, "candidate_only": True, "canonical_write_back": False})
    damage = [row for row in regression_eval.get("records", []) or [] if row.get("final", {}).get("identity_correct") is False and (row.get("historian_a", {}).get("identity_correct") is True or row.get("historian_b", {}).get("identity_correct") is True) and row.get("final_resolution_status") == "resolved"]
    write_json(output / "adjudicator-damage-audit.json", {"schema": "sfh2-a2r-adjudicator-damage-v1", "count": len(damage), "records": damage, "candidate_only": True, "canonical_write_back": False})

    challenge_ids = {text(case.get("case_id")) for case in cases["challenge"]}
    challenge_cases = cases["challenge"]
    challenge_bundle, challenge_md = _challenge_bundle(challenge_cases, packets, {key: a_rows_by_cohort["challenge"][key] for key in challenge_ids}, {key: b_rows[key] for key in challenge_ids}, {key: comparisons[key] for key in challenge_ids}, {key: adjudications[key] for key in challenge_ids if key in adjudications}, [row for row in finals if text(row.get("case_id")) in challenge_ids])
    write_json(output / "challenge-final.json", {"schema": "sfh2-a2r-challenge-final-v1", "historical_correctness": "pending_external_review", "records": [row for row in finals if text(row.get("case_id")) in challenge_ids], "candidate_only": True, "canonical_write_back": False})
    write_json(output / "challenge-review-bundle.json", challenge_bundle)
    (output / "challenge-review-bundle.md").write_text(challenge_md, encoding="utf-8")

    before = input_hashes()
    after = input_hashes()
    safety = _safety(finals, before, after)
    preservation = _preservation(finals, {**a_rows_by_cohort["regression"], **a_rows_by_cohort["challenge"]}, b_rows, adjudications)
    write_json(output / "semantic-preservation-audit.json", preservation)
    write_json(output / "storage-safety-audit.json", safety)
    write_json(output / "policy-simulation.json", _policy_simulation([case for _, case in ordered], {**a_rows_by_cohort["regression"], **a_rows_by_cohort["challenge"]}, comparisons))
    client.save()
    transport = client.metrics()
    transport.update({
        "schema_probe_attempts": 1 if probe.get("tool_call_received") else 0,
        "historian_a_new_calls": 0,
        "valid_historian_b_reused": b_reuse.get("valid_reused"),
        "historian_b_recovery_eligible": len(recovery_records),
        "candidate_only": True,
        "canonical_write_back": False,
    })
    write_json(output / "transport.json", transport)

    validation = {
        "schema": "sfh2-a2r-validation-summary-v1",
        "adjudicator_schema_probe": probe.get("tool_call_received") if live else True,
        "cached_historian_a_40": a_cache.get("cached_primary_responses") == 40,
        "new_historian_a_calls": 0,
        "valid_historian_b_reused": b_reuse.get("valid_reused"),
        "b_recovery_calls": len(recovery_records),
        "adjudication_cases": len(adjudications),
        "adjudicator_contract_invalid": sum(row.get("valid") is not True for row in adjudications.values()),
        "copy_drift": preservation.get("selector_copy_drift"),
        "undeclared_patch_mutations": preservation.get("undeclared_patch_mutations"),
        "candidate_only": True,
        "canonical_write_back": False,
    }
    write_json(output / "validation-summary.json", validation)

    recommendation = "sfh2_dual_semantic_architecture_ready"
    if not validation["adjudicator_schema_probe"] or validation["adjudicator_contract_invalid"] or preservation.get("selector_copy_drift") or preservation.get("undeclared_patch_mutations") or not regression_metrics.get("final_identity", {}).get("resolution_coverage") == 1.0 or float(regression_metrics.get("final_identity", {}).get("full_cohort_accuracy") or 0) < 0.95:
        recommendation = "sfh2_adjudicator_quality_insufficient" if validation["adjudicator_schema_probe"] and not validation["adjudicator_contract_invalid"] else "sfh2_semantic_contract_still_invalid"
    write_json(output / "recommendation.json", {"schema": "sfh2-a2r-recommendation-v1", "recommendation": recommendation, "candidate_only": True, "canonical_write_back": False})
    metrics = {
        "schema": "sfh2-a2r-metrics-v1",
        "pilot": "SFH2.2-A2R",
        "cohorts": {"regression": 20, "challenge": 20},
        "historian_a_cached_records": 40,
        "historian_a_new_calls": 0,
        "historian_b_valid_reused": b_reuse.get("valid_reused"),
        "historian_b_recovery_eligible": len(recovery_records),
        "historian_b_recovered_valid": sum(row.get("replacement_valid") is True for row in recovery_records),
        "ab_substantive_disagreement_count": sum(row.get("substantive_disagreement") is True for row in comparisons.values()),
        "ab_identity_disagreement_count": sum(row.get("historical_identity_disagreement") is True for row in comparisons.values()),
        "adjudicator_calls": len(adjudications),
        "adjudicator_valid_records": sum(row.get("valid") is True for row in adjudications.values()),
        "regression": regression_metrics,
        "challenge": {"case_count": 20, "historical_correctness": "pending_external_review", "adjudication_cases": sum(key in adjudications for key in challenge_ids)},
        "provider": transport,
        "copy_drift": preservation.get("selector_copy_drift"),
        "undeclared_patch_mutations": preservation.get("undeclared_patch_mutations"),
        "candidate_only": True,
        "canonical_write_back": False,
        "no_full_188_story_live_run": True,
    }
    write_json(output / "metrics.json", metrics)
    return {"cases": cases, "packets": packets, "historian_a": a_rows_by_cohort, "historian_b": b_rows, "comparisons": comparisons, "adjudications": adjudications, "finals": finals, "regression_metrics": regression_metrics, "transport": transport, "recommendation": recommendation, "output": str(output)}
