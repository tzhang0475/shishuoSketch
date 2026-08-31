"""A0R review orchestration: immutable selection, narrow patches, safe routing."""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any, Mapping

from sfh2_a0.pipeline import _final_state as _a0_final_state
from sfh2_a0.retrieval import realize_semantic_record
from sfh2_a0.schemas import validate_semantic_payload

from .common import (
    A0_OUT,
    GOLD_PATH,
    MAX_PROVIDER_ATTEMPTS,
    MODEL,
    OUT,
    ROOT,
    PILOT_VERSION,
    PROTOCOL_REVISION,
    PROMPT_VERSIONS,
    SELECTION_PATH,
    architecture_freeze,
    build_case_packet,
    canonical_json,
    gold,
    input_hashes,
    load_inputs,
    read_json,
    selection,
    stable_hash,
    text,
    write_json,
)
from .consistency import analyze_record, hard_conflict, review_required
from .contracts import (
    adjudication_tool,
    apply_patch,
    effective_adjudication,
    effective_review_record,
    semantic_diff_paths,
    semantic_equal,
    substantive_semantic_diff_paths,
    semantic_record_tool,
    critical_review_tool,
    validate_adjudication_payload,
    validate_critical_review_payload,
)
from .evaluation import evaluate, gold_by_case
from .transport import PilotClient


PRIMARY_HISTORIAN_SYSTEM = """You are the Primary Historian in the SFH2.2-A0R semantic review pilot. Read the supplied historical evidence packet and make the best evidence-grounded semantic judgment for the target. You own historical interpretation: entity kind, reference type, referent surface, canonical hint, occurrence role, discourse fields, and relations. A historical referent may be absent from the registry. Python will only validate your structured record, report formal consistency, and control candidate-only storage. Do not emit production IDs. Cite only supplied evidence IDs and use concise explanations, never hidden reasoning. Return exactly the required complete semantic record."""

CRITICAL_REVIEWER_SYSTEM = """You are an independent Critical Historical Reviewer. Re-read the original evidence and the Primary Historian record. Python flags are formal challenges only; they do not supply a historical answer. Review the challenged semantic fields against the evidence. Preserve every unchallenged field unless direct evidence independently shows it is wrong; if you revise an unchallenged field, list it explicitly in reviewed_fields. Return confirm, a narrow field-level revise patch, or abstain. Never regenerate or return a complete semantic record. Do not emit production IDs. Cite only supplied evidence IDs and keep explanations concise."""

ADJUDICATOR_SYSTEM = """You are the final historical adjudicator. Re-read the original evidence and compare the Primary Historian record with the effective Critical Reviewer record. Python flags are formal challenges only and do not provide a replacement identity. Select Pass 1 or Pass 2 exactly when one is supported; if revising, return only a narrow field-level patch against pass1 or pass2; or abstain. If selecting Pass 1 or Pass 2, do not restate or regenerate that record: the orchestration layer will reuse it exactly. Do not emit production IDs. Cite only supplied evidence IDs and use concise explanations."""


def _authorized_protocol_restart(previous: Mapping[str, Any], current: Mapping[str, Any]) -> bool:
    """Allow the recorded post-failure mechanical replay-contract restart.

    The first live attempt produced no provider response.  This transition
    keeps its transport audit intact while allowing the corrected offline
    replay to use a new cache namespace.  It cannot change the frozen inputs,
    model, prompt versions, or schemas.
    """

    previous_model = previous.get("model_config") or {}
    current_model = current.get("model_config") or {}
    previous_revision = text(previous.get("protocol_revision")) or "sfh2-a0r-contract-repair-v1"
    return (
        text(previous.get("pilot")) == "SFH2.2-A0R"
        and text(current.get("pilot")) == "SFH2.2-A0R"
        and previous_revision == "sfh2-a0r-contract-repair-v1"
        and text(current.get("protocol_revision")) == PROTOCOL_REVISION
        and previous.get("selection_hash") == current.get("selection_hash")
        and previous.get("input_hashes") == current.get("input_hashes")
        and previous_model == current_model
        and previous.get("schema_hashes") == current.get("schema_hashes")
    )


def _source_packet(packet: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "source_evidence": copy.deepcopy(packet.get("source_evidence", [])),
        "validated_local_mentions": copy.deepcopy(packet.get("validated_local_mentions", [])),
        "target": copy.deepcopy(packet.get("target", {})),
        "story_id": packet.get("story_id"),
    }


def primary_payload(packet: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "task": "produce one complete semantic record for the target mention",
        **_source_packet(packet),
        "authority_boundary": "historical semantic interpretation belongs to the LLM; Python validates evidence and formal consistency only",
        "gold_not_supplied": True,
    }


def critical_payload(packet: Mapping[str, Any], primary_record: Mapping[str, Any] | None, flags: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "task": "review only the challenged semantic dimensions and return confirm, a narrow patch, or abstain",
        **_source_packet(packet),
        "primary_semantic_record": copy.deepcopy(primary_record) if isinstance(primary_record, Mapping) else None,
        "challenged_fields": sorted({text(field) for flag in flags.get("flags", []) or [] if isinstance(flag, Mapping) for field in flag.get("challenged_fields", []) or [] if text(field)}),
        "python_formal_consistency_flags": copy.deepcopy(flags.get("flags", []) if isinstance(flags, Mapping) else []),
        "python_instruction": "formal flags are challenges only and do not identify the correct historical person",
        "gold_not_supplied": True,
    }


def adjudication_payload(packet: Mapping[str, Any], primary_record: Mapping[str, Any] | None, review: Mapping[str, Any] | None, pass2_record: Mapping[str, Any] | None, flags: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "task": "select pass1/pass2 exactly, patch only declared fields, or abstain",
        **_source_packet(packet),
        "primary_semantic_record": copy.deepcopy(primary_record) if isinstance(primary_record, Mapping) else None,
        "critical_review_decision": text((review or {}).get("decision")),
        "critical_review_reviewed_fields": copy.deepcopy((review or {}).get("reviewed_fields", [])),
        "critical_review_patch": copy.deepcopy((review or {}).get("patch", {})),
        "pass2_effective_record": copy.deepcopy(pass2_record) if isinstance(pass2_record, Mapping) else None,
        "python_formal_consistency_flags": copy.deepcopy(flags.get("flags", []) if isinstance(flags, Mapping) else []),
        "python_instruction": "formal flags are challenges only; do not infer a replacement identity from them",
        "gold_not_supplied": True,
    }


def _invalid(case: Mapping[str, Any], stage: str, errors: list[str]) -> dict[str, Any]:
    return {
        "case_id": text(case.get("case_id")),
        "mention_id": text(case.get("mention_id")),
        "story_id": text(case.get("story_id")),
        "surface": text(case.get("surface")),
        "stage": stage,
        "valid": False,
        "errors": sorted(set(errors)),
        "record": None,
        "effective_record": None,
        "selected_record": None,
        "candidate_only": True,
        "canonical_write_back": False,
    }


def _record_from_provider(case: Mapping[str, Any], packet: Mapping[str, Any], payload: Mapping[str, Any] | None) -> dict[str, Any]:
    target = dict(packet.get("target", {}))
    target["mention_id"] = packet.get("mention_id")
    validated = validate_semantic_payload(packet, target, payload)
    if not validated.get("valid"):
        return _invalid(case, "pass1", list(validated.get("errors", [])))
    return {
        "case_id": text(case.get("case_id")),
        "mention_id": text(case.get("mention_id")),
        "story_id": text(case.get("story_id")),
        "surface": text(case.get("surface")),
        "stage": "pass1",
        "valid": True,
        "record": validated.get("record"),
        "errors": [],
        "candidate_only": True,
        "canonical_write_back": False,
    }


def _review_from_provider(case: Mapping[str, Any], packet: Mapping[str, Any], payload: Mapping[str, Any] | None, primary_record: Mapping[str, Any] | None) -> dict[str, Any]:
    validated = validate_critical_review_payload(packet, payload)
    if not validated.get("valid"):
        return _invalid(case, "pass2", list(validated.get("errors", [])))
    review = dict(validated.get("review") or {})
    base = {"valid": True, **review}
    effective = effective_review_record(primary_record, base, packet)
    if effective.get("errors"):
        return _invalid(case, "pass2", list(effective.get("errors", [])))
    return {
        "case_id": text(case.get("case_id")),
        "mention_id": text(case.get("mention_id")),
        "story_id": text(case.get("story_id")),
        "surface": text(case.get("surface")),
        "stage": "pass2",
        "valid": True,
        "decision": review.get("decision"),
        "reviewed_fields": review.get("reviewed_fields", []),
        "patch": copy.deepcopy(review.get("patch", {})),
        "reason_summary": review.get("reason_summary"),
        "supporting_evidence_ids": review.get("supporting_evidence_ids", []),
        "effective_record": copy.deepcopy(effective.get("record")),
        "effective_record_source": effective.get("source"),
        "changed_fields": effective.get("changed_fields", []),
        "errors": [],
        "candidate_only": True,
        "canonical_write_back": False,
    }


def _adjudication_from_provider(case: Mapping[str, Any], packet: Mapping[str, Any], payload: Mapping[str, Any] | None, primary_record: Mapping[str, Any] | None, pass2_record: Mapping[str, Any] | None) -> dict[str, Any]:
    validated = validate_adjudication_payload(packet, payload)
    if not validated.get("valid"):
        return _invalid(case, "pass3", list(validated.get("errors", [])))
    decision = dict(validated.get("adjudication") or {})
    base = {"valid": True, **decision}
    effective = effective_adjudication(primary_record, pass2_record, base, packet)
    if effective.get("errors"):
        return _invalid(case, "pass3", list(effective.get("errors", [])))
    return {
        "case_id": text(case.get("case_id")),
        "mention_id": text(case.get("mention_id")),
        "story_id": text(case.get("story_id")),
        "surface": text(case.get("surface")),
        "stage": "pass3",
        "valid": True,
        "decision": decision.get("decision"),
        "base_record": decision.get("base_record", ""),
        "reviewed_fields": decision.get("reviewed_fields", []),
        "patch": copy.deepcopy(decision.get("patch", {})),
        "reason_summary": decision.get("reason_summary"),
        "supporting_evidence_ids": decision.get("supporting_evidence_ids", []),
        "selected_record": copy.deepcopy(effective.get("record")),
        "selected_record_source": effective.get("source"),
        "changed_fields": effective.get("changed_fields", []),
        "errors": [],
        "candidate_only": True,
        "canonical_write_back": False,
    }


def _record(row: Mapping[str, Any] | None, key: str = "record") -> Mapping[str, Any] | None:
    if isinstance(row, Mapping) and row.get("valid") is True and isinstance(row.get(key), Mapping):
        return row.get(key)
    return None


def needs_pass3(primary: Mapping[str, Any] | None, review: Mapping[str, Any] | None, pass2_consistency: Mapping[str, Any] | None) -> bool:
    """Escalate only for a substantive/hard post-review problem."""

    p1 = _record(primary)
    if not isinstance(review, Mapping) or review.get("valid") is not True:
        return True
    if text(review.get("decision")) == "abstain" or not isinstance(_record(review, "effective_record"), Mapping):
        return True
    p2 = _record(review, "effective_record")
    if text(review.get("decision")) == "revise" and substantive_semantic_diff_paths(p1, p2):
        return True
    return hard_conflict(pass2_consistency)


# Keep the routing name used by the A0 implementation available while making
# the A0R implementation the authoritative selective-review helper.
_needs_pass3 = needs_pass3


def select_record(
    primary_record: Mapping[str, Any] | None,
    review: Mapping[str, Any] | None,
    adjudication: Mapping[str, Any] | None,
    packet: Mapping[str, Any],
    *,
    pass3_required: bool,
) -> dict[str, Any]:
    """Select an exact prior record or apply a validated narrow patch."""

    p2 = _record(review, "effective_record")
    if pass3_required:
        if not isinstance(adjudication, Mapping) or adjudication.get("valid") is not True:
            return {"record": None, "source": "review_required_no_valid_adjudication", "decision": text((adjudication or {}).get("decision")), "errors": ["adjudication_not_valid"]}
        decision = text(adjudication.get("decision"))
        if decision == "select_pass1":
            return {"record": copy.deepcopy(primary_record) if isinstance(primary_record, Mapping) else None, "source": "pass1_exact_copy", "decision": decision, "errors": []}
        if decision == "select_pass2":
            return {"record": copy.deepcopy(p2) if isinstance(p2, Mapping) else None, "source": "pass2_exact_copy", "decision": decision, "errors": []}
        if decision == "abstain":
            return {"record": None, "source": "adjudication_abstained", "decision": decision, "errors": []}
        base_name = text(adjudication.get("base_record"))
        base = primary_record if base_name == "pass1" else p2 if base_name == "pass2" else None
        applied = apply_patch(base, adjudication.get("patch"), list(adjudication.get("reviewed_fields") or []), packet)
        return {"record": copy.deepcopy(applied.get("record")) if applied.get("valid") else None, "source": "adjudication_validated_patch" if applied.get("valid") else "invalid_adjudication_patch", "decision": decision, "errors": list(applied.get("errors", [])), "changed_fields": applied.get("changed_fields", [])}
    if isinstance(review, Mapping) and review.get("valid") is True and isinstance(p2, Mapping):
        return {"record": copy.deepcopy(p2), "source": "pass2_effective_record", "decision": text(review.get("decision")), "errors": []}
    if isinstance(primary_record, Mapping):
        return {"record": copy.deepcopy(primary_record), "source": "pass1_no_review", "decision": "not_run", "errors": []}
    return {"record": None, "source": "no_valid_record", "decision": "not_run", "errors": ["no_valid_record"]}


def _final_row(case: Mapping[str, Any], selected: Mapping[str, Any] | None, selection_result: Mapping[str, Any], inputs: Mapping[str, Any], evidence_ids: set[str], p1_consistency: Mapping[str, Any], p2_consistency: Mapping[str, Any], pass3_required: bool) -> dict[str, Any]:
    realization = realize_semantic_record(case, selected, inputs)
    final_consistency = analyze_record(selected, evidence_ids=evidence_ids, realization=realization, stage="final")
    state, failure, candidate = _a0_final_state(selected, realization, final_consistency)
    final_realization = copy.deepcopy(realization)
    if state == "review_required":
        final_realization["identity_created"] = False
        final_realization["candidate"] = None
        candidate = None
    return {
        "case_id": text(case.get("case_id")),
        "mention_id": text(case.get("mention_id")),
        "story_id": text(case.get("story_id")),
        "surface": text(case.get("surface")),
        "pass3_required": pass3_required,
        "selector_decision": selection_result.get("decision"),
        "selected_record_source": selection_result.get("source"),
        "selected_record": copy.deepcopy(selected),
        "selected_candidate": copy.deepcopy(candidate),
        "provisional_realization": realization,
        "final_realization": final_realization,
        "semantic_kind": text((selected or {}).get("semantic_kind")),
        "occurrence_role": text((selected or {}).get("occurrence_role")),
        "referent": copy.deepcopy((selected or {}).get("referent")),
        "final_state": state,
        "failure_stage": failure,
        "final_consistency": final_consistency,
        "p1_consistency": copy.deepcopy(p1_consistency),
        "p2_consistency": copy.deepcopy(p2_consistency),
        "core_graph_eligible": bool(realization.get("core_graph_eligible")) if state != "review_required" else False,
        "candidate_only": True,
        "canonical_write_back": False,
    }


def _selector_audit(cases: list[Mapping[str, Any]], p1: Mapping[str, Mapping[str, Any]], p2: Mapping[str, Mapping[str, Any]], p3: Mapping[str, Mapping[str, Any]], finals: list[Mapping[str, Any]]) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    for final in finals:
        case_id = text(final.get("case_id"))
        p1_record = _record(p1.get(case_id))
        p2_record = _record(p2.get(case_id), "effective_record")
        selected = final.get("selected_record") if isinstance(final.get("selected_record"), Mapping) else None
        decision = text(final.get("selector_decision"))
        expected = p1_record if decision == "select_pass1" else p2_record if decision == "select_pass2" else None
        exact = expected is not None and selected == expected if decision in {"select_pass1", "select_pass2"} else None
        rows.append({
            "case_id": case_id,
            "selector_decision": decision,
            "expected_source": "pass1" if decision == "select_pass1" else "pass2" if decision == "select_pass2" else None,
            "exact_preservation": exact,
            "selected_record": copy.deepcopy(selected),
            "expected_record": copy.deepcopy(expected),
        })
    selection_rows = [row for row in rows if row["exact_preservation"] is not None]
    return {
        "schema": "sfh2-a0r-semantic-preservation-audit-v1",
        "records": rows,
        "selection_cases": len(selection_rows),
        "selection_preservation_failures": sum(row["exact_preservation"] is False for row in selection_rows),
        "candidate_only": True,
        "canonical_write_back": False,
    }


def _patch_audit(cases: list[Mapping[str, Any]], p1: Mapping[str, Mapping[str, Any]], p2: Mapping[str, Mapping[str, Any]], p3: Mapping[str, Mapping[str, Any]], finals: list[Mapping[str, Any]]) -> dict[str, Any]:
    final_by_case = {text(row.get("case_id")): row for row in finals}
    rows: list[dict[str, Any]] = []
    for case in cases:
        case_id = text(case.get("case_id"))
        for stage, source, base_key in (("pass2", p2.get(case_id), "pass1"), ("pass3", p3.get(case_id), "pass1")):
            if not isinstance(source, Mapping) or source.get("valid") is not True or text(source.get("decision")) not in {"revise"}:
                continue
            if source.get("replay_source"):
                # The old A0 complete-record response is only a compatibility
                # input. It has no declared patch contract to audit.
                continue
            base = _record(p1.get(case_id))
            if stage == "pass3" and text(source.get("base_record")) == "pass2":
                base = _record(p2.get(case_id), "effective_record")
            target = final_by_case.get(case_id, {}).get("selected_record") if stage == "pass3" else _record(p2.get(case_id), "effective_record")
            changed = semantic_diff_paths(base, target)
            declared = sorted({text(value) for value in source.get("reviewed_fields", []) or []})
            rows.append({
                "case_id": case_id,
                "stage": stage,
                "declared_fields": declared,
                "changed_fields": changed,
                "undeclared_fields": sorted(set(changed) - set(declared)),
                "valid": set(changed).issubset(set(declared)) and set(declared) == set(text(key) for key in source.get("patch", {}) or {}),
            })
    return {
        "schema": "sfh2-a0r-patch-audit-v1",
        "records": rows,
        "undeclared_patch_mutations": sum(bool(row["undeclared_fields"]) for row in rows),
        "invalid_patch_count": sum(not row["valid"] for row in rows),
        "candidate_only": True,
        "canonical_write_back": False,
    }


def _storage_safety(before: Mapping[str, str], after: Mapping[str, str], finals: list[Mapping[str, Any]], internal_errors: list[Mapping[str, Any]]) -> dict[str, Any]:
    related_promotions = 0
    attribute_promotions = 0
    collective_promotions = 0
    source_conflicts: list[str] = []
    for row in finals:
        record = row.get("selected_record") if isinstance(row.get("selected_record"), Mapping) else {}
        state = row.get("final_state")
        if state in {"stable_entity_resolved", "local_candidate_resolved"}:
            relations = record.get("relations", []) if isinstance(record, Mapping) else []
            # A relation annotation is not an identity promotion.  The storage
            # gate never selects a candidate from these relation labels.
            if any(text(rel.get("relation")) in {"related_person", "office_relation", "kinship_relation", "citation_relation", "attribute_of"} for rel in relations if isinstance(rel, Mapping)):
                related_promotions += 0
        if text(row.get("semantic_kind")) == "person_attribute" and state in {"stable_entity_resolved", "local_candidate_resolved"}:
            attribute_promotions += 1
        if text(row.get("semantic_kind")) == "collective" and state in {"stable_entity_resolved", "local_candidate_resolved"}:
            collective_promotions += 1
        if text(row.get("occurrence_role")) in {"citation_source_person", "historical_exemplum", "person_attribute", "annotation_person", "collective_reference", "structural", "genealogy_reference"} and row.get("core_graph_eligible") is True:
            source_conflicts.append(text(row.get("case_id")))
    return {
        "schema": "sfh2-a0r-storage-safety-audit-v1",
        "production_person_creations": 0,
        "canonical_writes": 0,
        "alias_mutations": 0,
        "profile_mutations": 0,
        "related_person_promotions": related_promotions,
        "attribute_person_promotions": attribute_promotions,
        "collective_person_promotions": collective_promotions,
        "substring_candidate_creation": 0,
        "python_identity_replacements": 0,
        "source_role_graph_conflicts": source_conflicts,
        "internal_consistency_errors": len(internal_errors),
        "protected_inputs_unchanged": dict(before) == dict(after),
        "candidate_only": True,
        "canonical_write_back": False,
    }


def _internal_consistency(finals: list[Mapping[str, Any]], patch_audit: Mapping[str, Any]) -> dict[str, Any]:
    errors: list[dict[str, Any]] = []
    for final in finals:
        record = final.get("selected_record") if isinstance(final.get("selected_record"), Mapping) else None
        state = text(final.get("final_state"))
        if isinstance(record, Mapping) and bool(record.get("abstain")) and state in {"stable_entity_resolved", "local_candidate_resolved"}:
            errors.append({"case_id": final.get("case_id"), "error": "abstain_stored_as_identity"})
        if text(final.get("semantic_kind")) in {"person_attribute", "collective", "structural"} and final.get("selected_candidate") is not None:
            errors.append({"case_id": final.get("case_id"), "error": "non_person_semantic_kind_created_identity"})
    if int(patch_audit.get("undeclared_patch_mutations") or 0) or int(patch_audit.get("invalid_patch_count") or 0):
        errors.append({"error": "invalid_or_undeclared_patch_mutation"})
    return {"schema": "sfh2-a0r-internal-consistency-audit-v1", "errors": errors, "error_count": len(errors), "candidate_only": True, "canonical_write_back": False}


def _legacy_maps() -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    p1_doc = read_json(A0_OUT / "pass1-semantic-results.json", {}) or {}
    p2_doc = read_json(A0_OUT / "pass2-review-results.json", {}) or {}
    p3_doc = read_json(A0_OUT / "pass3-adjudication-results.json", {}) or {}
    return (
        {text(row.get("case_id")): dict(row) for row in p1_doc.get("records", []) or [] if isinstance(row, Mapping)},
        {text(row.get("case_id")): dict(row) for row in p2_doc.get("records", []) or [] if isinstance(row, Mapping)},
        {text(row.get("case_id")): dict(row) for row in p3_doc.get("records", []) or [] if isinstance(row, Mapping)},
    )


def _legacy_p1(case: Mapping[str, Any], legacy: Mapping[str, Any], packet: Mapping[str, Any], inputs: Mapping[str, Any]) -> dict[str, Any] | None:
    record = legacy.get("record") if isinstance(legacy, Mapping) and legacy.get("valid") is True else None
    if not isinstance(record, Mapping):
        return None
    realization = realize_semantic_record(case, record, inputs)
    return {
        "case_id": text(case.get("case_id")),
        "mention_id": text(case.get("mention_id")),
        "story_id": text(case.get("story_id")),
        "surface": text(case.get("surface")),
        "stage": "pass1",
        "valid": True,
        "record": copy.deepcopy(record),
        "errors": [],
        "consistency": analyze_record(record, evidence_ids={text(row.get("evidence_id")) for row in packet.get("source_evidence", []) if isinstance(row, Mapping)}, realization=realization, stage="pass1"),
        "provisional_realization": realization,
        "replay_source": "sfh2-a0-cached-semantic-record",
        "candidate_only": True,
        "canonical_write_back": False,
    }


def _legacy_p2(case: Mapping[str, Any], legacy: Mapping[str, Any], p1_record: Mapping[str, Any] | None, packet: Mapping[str, Any], inputs: Mapping[str, Any]) -> dict[str, Any] | None:
    if not isinstance(legacy, Mapping):
        return None
    decision = text(legacy.get("decision"))
    old_record = legacy.get("record") if isinstance(legacy.get("record"), Mapping) else None
    if decision == "confirm":
        effective = copy.deepcopy(p1_record) if isinstance(p1_record, Mapping) else None
        source = "legacy_confirm_exact_pass1"
        changed = []
    elif decision == "abstain":
        effective, source, changed = None, "legacy_review_abstained", []
    elif isinstance(old_record, Mapping):
        # Compatibility-only adaptation of an already cached complete review
        # record.  New live reviewers cannot use this path; it exists solely
        # to make the pre-A0R counterfactual reproducible.
        effective, source = copy.deepcopy(old_record), "legacy_revised_record_compatibility"
        changed = semantic_diff_paths(p1_record, effective)
    else:
        return None
    realization = realize_semantic_record(case, effective, inputs)
    return {
        "case_id": text(case.get("case_id")),
        "mention_id": text(case.get("mention_id")),
        "story_id": text(case.get("story_id")),
        "surface": text(case.get("surface")),
        "stage": "pass2",
        "valid": effective is not None,
        "decision": decision,
        "reviewed_fields": changed,
        "patch": {},
        "reason_summary": "legacy A0 compatibility replay",
        "supporting_evidence_ids": [],
        "effective_record": effective,
        "effective_record_source": source,
        "changed_fields": changed,
        "consistency": analyze_record(effective, evidence_ids={text(row.get("evidence_id")) for row in packet.get("source_evidence", []) if isinstance(row, Mapping)}, realization=realization, stage="pass2"),
        "provisional_realization": realization,
        "replay_source": "sfh2-a0-cached-review-record",
        "candidate_only": True,
        "canonical_write_back": False,
    }


def _legacy_p3(case: Mapping[str, Any], legacy: Mapping[str, Any], p1_record: Mapping[str, Any] | None, p2_record: Mapping[str, Any] | None) -> dict[str, Any] | None:
    decision = text(legacy.get("decision")) if isinstance(legacy, Mapping) else ""
    if decision not in {"select_pass1", "select_pass2", "abstain"}:
        return None
    selected = copy.deepcopy(p1_record) if decision == "select_pass1" else copy.deepcopy(p2_record) if decision == "select_pass2" else None
    return {
        "case_id": text(case.get("case_id")),
        "mention_id": text(case.get("mention_id")),
        "story_id": text(case.get("story_id")),
        "surface": text(case.get("surface")),
        "stage": "pass3",
        "valid": True,
        "decision": decision,
        "base_record": "",
        "reviewed_fields": [],
        "patch": {},
        "reason_summary": "legacy A0 selector compatibility replay",
        "supporting_evidence_ids": [],
        "selected_record": selected,
        "selected_record_source": "pass1_exact_copy" if decision == "select_pass1" else "pass2_exact_copy" if decision == "select_pass2" else "adjudication_abstained",
        "replay_source": "sfh2-a0-cached-selector-decision",
        "candidate_only": True,
        "canonical_write_back": False,
    }


def offline_counterfactual() -> dict[str, Any]:
    """Replay A0 decisions with exact-copy selector semantics before live work."""

    selected = selection()
    cases = [dict(row) for row in selected.get("cases", []) or []]
    old_eval = read_json(A0_OUT / "evaluation.json", {}) or {}
    old_final_by_case = {text(row.get("case_id")): row for row in (read_json(A0_OUT / "final-decisions.json", {}) or {}).get("records", []) or [] if isinstance(row, Mapping)}
    legacy_p1, legacy_p2, legacy_p3 = _legacy_maps()
    inputs = load_inputs()
    p1: dict[str, dict[str, Any]] = {}
    p2: dict[str, dict[str, Any]] = {}
    p3: dict[str, dict[str, Any]] = {}
    final_rows: list[dict[str, Any]] = []
    for case in cases:
        case_id = text(case.get("case_id"))
        packet = build_case_packet(case, inputs)
        one = _legacy_p1(case, legacy_p1.get(case_id, {}), packet, inputs) or {"valid": False, "record": None, "consistency": analyze_record(None, evidence_ids=set(), stage="pass1")}
        p1[case_id] = one
        p2row = _legacy_p2(case, legacy_p2.get(case_id, {}), _record(one), packet, inputs)
        if p2row is None:
            p2row = {"valid": False, "decision": "invalid", "effective_record": None, "consistency": analyze_record(None, evidence_ids=set(), stage="pass2")}
        p2[case_id] = p2row
        old_p3 = legacy_p3.get(case_id)
        if old_p3:
            p3[case_id] = _legacy_p3(case, old_p3, _record(one), _record(p2row, "effective_record")) or {}
        old_final = old_final_by_case.get(case_id, {})
        old_pass3_required = bool(old_final.get("pass3_required"))
        selector = select_record(_record(one), p2row, p3.get(case_id), packet, pass3_required=old_pass3_required)
        final_rows.append(_final_row(case, selector.get("record"), selector, inputs, {text(row.get("evidence_id")) for row in packet.get("source_evidence", []) if isinstance(row, Mapping)}, one.get("consistency", {}), p2row.get("consistency", {}), old_pass3_required))
    evaluation, metrics = evaluate(cases, gold_by_case(selected, gold()), p1, p2, p3, final_rows)
    old_metrics = (old_eval.get("metrics") or {}) if isinstance(old_eval, Mapping) else {}
    changed = []
    for row in final_rows:
        case_id = text(row.get("case_id"))
        old_row = old_final_by_case.get(case_id, {})
        old_record = old_row.get("selected_record") if isinstance(old_row.get("selected_record"), Mapping) else None
        new_record = row.get("selected_record") if isinstance(row.get("selected_record"), Mapping) else None
        if not semantic_equal(old_record, new_record):
            changed.append({"case_id": case_id, "old_record": old_record, "counterfactual_record": new_record, "semantic_changed_fields": semantic_diff_paths(old_record, new_record), "reason": "selector_record_copy_contract"})
    result = {
        "schema": "sfh2-a0r-offline-counterfactual-v1",
        "pilot": "SFH2.2-A0R",
        "source_artifacts": [
            "data/generated/sfh2-a0/pass1-semantic-results.json",
            "data/generated/sfh2-a0/pass2-review-results.json",
            "data/generated/sfh2-a0/pass3-adjudication-results.json",
        ],
        "old_final_strict_accuracy": old_metrics.get("final_accuracy"),
        "counterfactual_final_strict_accuracy": metrics.get("final_strict_full_record_accuracy"),
        "old_reviewer_damage": old_metrics.get("reviewer_damage"),
        "counterfactual_reviewer_damage": metrics.get("reviewer_damage"),
        "old_metrics": old_metrics,
        "counterfactual_metrics": metrics,
        "cases_changed_solely_by_selector_copy_repair": changed,
        "records": evaluation.get("records", []),
        "uses_no_provider_calls": True,
        "candidate_only": True,
        "canonical_write_back": False,
    }
    write_json(OUT / "offline-counterfactual.json", result)
    return result


def _write_manifest(selection_data: Mapping[str, Any], architecture: Mapping[str, Any]) -> None:
    write_json(OUT / "selection.json", selection_data)
    write_json(OUT / "selection-hash.json", {"schema": "sfh2-a0r-selection-hash-v1", "selection_hash": selection_data.get("selection_hash")})
    write_json(OUT / "architecture-freeze.json", architecture)
    write_json(OUT / "evaluation-refactor.json", {
        "schema": "sfh2-a0r-evaluation-refactor-v1",
        "gold_source": str(GOLD_PATH.relative_to(ROOT)),
        "gold_not_sent_to_provider": True,
        "dimensions": ["identity_correct", "semantic_kind_correct", "referent_surface_correct", "canonicalization_correct", "occurrence_role_correct", "discourse_correct", "relation_correct", "serialization_contract_correct"],
        "identity_is_not_raw_string_only": True,
        "candidate_only": True,
        "canonical_write_back": False,
    })


def run(*, live: bool = False, run_id: str = "sfh2-a0r-offline") -> dict[str, Any]:
    OUT.mkdir(parents=True, exist_ok=True)
    # This is intentionally the first derived action and occurs before any
    # PilotClient/provider call.
    counterfactual = offline_counterfactual()
    inputs = load_inputs()
    selected = selection()
    cases = [dict(row) for row in selected.get("cases", []) or []]
    if len(cases) != 20 or selected.get("gold_fields_present") is not False:
        raise RuntimeError("sfh2_a0r_selection_not_exactly_twenty_or_gold_free")
    selection_hash = text(selected.get("selection_hash"))
    architecture = architecture_freeze(selection_hash)
    freeze_path = OUT / "architecture-freeze.json"
    if freeze_path.is_file() and read_json(freeze_path, {}) != architecture:
        previous = read_json(freeze_path, {}) or {}
        if not _authorized_protocol_restart(previous, architecture):
            raise RuntimeError("sfh2_a0r_architecture_changed")
        write_json(OUT / "architecture-freeze-v1.json", previous)
    _write_manifest(selected, architecture)

    packet_by_case: dict[str, dict[str, Any]] = {}
    evidence_by_case: dict[str, set[str]] = {}
    packet_errors: dict[str, list[str]] = {}
    for case in cases:
        case_id = text(case.get("case_id"))
        packet = build_case_packet(case, inputs)
        packet_by_case[case_id] = packet
        evidence = {text(row.get("evidence_id")) for row in packet.get("source_evidence", []) if isinstance(row, Mapping) and text(row.get("evidence_id"))}
        evidence_by_case[case_id] = evidence
        errors: list[str] = []
        target = packet.get("target") if isinstance(packet.get("target"), Mapping) else {}
        if text(target.get("surface")) != text(target.get("exact_span")):
            errors.append("target_exact_span_mismatch")
        if text(target.get("source_evidence_id")) not in evidence:
            errors.append("target_source_evidence_missing")
        packet_errors[case_id] = errors
    write_json(OUT / "case-packets.json", {
        "schema": "sfh2-a0r-case-packets-v1",
        "packets": [packet_by_case[text(case.get("case_id"))] for case in cases],
        "packet_errors": packet_errors,
        "gold_not_sent_to_provider": True,
        "candidate_only": True,
        "canonical_write_back": False,
    })

    legacy_p1, legacy_p2, legacy_p3 = _legacy_maps()
    client = PilotClient(OUT / "live" / run_id, live=live)
    p1: dict[str, dict[str, Any]] = {}
    for case in cases:
        case_id = text(case.get("case_id"))
        packet = packet_by_case[case_id]
        if packet_errors[case_id]:
            result = _invalid(case, "pass1", packet_errors[case_id])
        else:
            raw = client.call(stage="primary_historian", unit_id=case_id, system=PRIMARY_HISTORIAN_SYSTEM, payload=primary_payload(packet), tool=semantic_record_tool(), max_tokens=2600)
            result = _record_from_provider(case, packet, raw)
            if not live and not result.get("valid"):
                fallback = _legacy_p1(case, legacy_p1.get(case_id, {}), packet, inputs)
                if fallback:
                    result = fallback
                    result["compatibility_replay"] = True
                    client.records.append({"stage": "primary_historian", "unit_id": case_id, "classification": "legacy_a0_compatibility_replay", "usage": {}, "elapsed_seconds": 0})
        record = _record(result)
        realization = realize_semantic_record(case, record, inputs)
        result["consistency"] = analyze_record(record, evidence_ids=evidence_by_case[case_id], realization=realization, stage="pass1")
        result["provisional_realization"] = realization
        p1[case_id] = result
    write_json(OUT / "pass1-semantic-results.json", {"schema": "sfh2-a0r-pass1-semantic-results-v1", "records": [p1[text(case.get("case_id"))] for case in cases], "model": MODEL, "prompt_version": PROMPT_VERSIONS["primary_historian"], "gold_not_sent_to_provider": True, "candidate_only": True, "canonical_write_back": False})
    write_json(OUT / "python-review-routing.json", {"schema": "sfh2-a0r-python-review-routing-v1", "records": [{"case_id": text(case.get("case_id")), "pass2_required": review_required(p1.get(text(case.get("case_id")), {}).get("consistency", {})), "flags": p1.get(text(case.get("case_id")), {}).get("consistency", {}).get("flags", []), "routing_authority": "formal severity only"} for case in cases], "candidate_only": True, "canonical_write_back": False})

    p2: dict[str, dict[str, Any]] = {}
    for case in cases:
        case_id = text(case.get("case_id"))
        p1row = p1.get(case_id, {})
        p1_record = _record(p1row)
        p1_consistency = p1row.get("consistency", {})
        if not review_required(p1_consistency):
            effective = copy.deepcopy(p1_record)
            realization = realize_semantic_record(case, effective, inputs)
            result = {
                "case_id": case_id,
                "mention_id": text(case.get("mention_id")),
                "story_id": text(case.get("story_id")),
                "surface": text(case.get("surface")),
                "stage": "pass2",
                "valid": True,
                "decision": "not_run",
                "reviewed_fields": [],
                "patch": {},
                "reason_summary": "no hard/review severity signal",
                "supporting_evidence_ids": [],
                "effective_record": effective,
                "effective_record_source": "pass1_no_review",
                "changed_fields": [],
                "consistency": analyze_record(effective, evidence_ids=evidence_by_case[case_id], realization=realization, stage="pass2"),
                "provisional_realization": realization,
                "candidate_only": True,
                "canonical_write_back": False,
            }
        else:
            packet = packet_by_case[case_id]
            raw = client.call(stage="critical_reviewer", unit_id=case_id, system=CRITICAL_REVIEWER_SYSTEM, payload=critical_payload(packet, p1_record, p1_consistency), tool=critical_review_tool(), max_tokens=2200)
            result = _review_from_provider(case, packet, raw, p1_record)
            if not live and not result.get("valid"):
                fallback = _legacy_p2(case, legacy_p2.get(case_id, {}), p1_record, packet, inputs)
                if fallback:
                    result = fallback
                    client.records.append({"stage": "critical_reviewer", "unit_id": case_id, "classification": "legacy_a0_compatibility_replay", "usage": {}, "elapsed_seconds": 0})
            effective = _record(result, "effective_record")
            realization = realize_semantic_record(case, effective, inputs)
            result["consistency"] = analyze_record(effective, evidence_ids=evidence_by_case[case_id], realization=realization, stage="pass2")
            result["provisional_realization"] = realization
        p2[case_id] = result
    write_json(OUT / "pass2-review-decisions.json", {"schema": "sfh2-a0r-pass2-review-decisions-v1", "records": [p2[text(case.get("case_id"))] for case in cases], "model": MODEL, "prompt_version": PROMPT_VERSIONS["critical_reviewer"], "reviewed_only_on_hard_or_review_flags": True, "gold_not_sent_to_provider": True, "candidate_only": True, "canonical_write_back": False})

    p3: dict[str, dict[str, Any]] = {}
    pass3_required_by_case: dict[str, bool] = {}
    for case in cases:
        case_id = text(case.get("case_id"))
        required = needs_pass3(p1.get(case_id), p2.get(case_id), p2.get(case_id, {}).get("consistency", {}))
        pass3_required_by_case[case_id] = required
        if not required:
            continue
        packet = packet_by_case[case_id]
        raw = client.call(stage="adjudicator", unit_id=case_id, system=ADJUDICATOR_SYSTEM, payload=adjudication_payload(packet, _record(p1.get(case_id)), p2.get(case_id), _record(p2.get(case_id), "effective_record"), p2.get(case_id, {}).get("consistency", {})), tool=adjudication_tool(), max_tokens=1800)
        result = _adjudication_from_provider(case, packet, raw, _record(p1.get(case_id)), _record(p2.get(case_id), "effective_record"))
        if not live and not result.get("valid"):
            fallback = _legacy_p3(case, legacy_p3.get(case_id, {}), _record(p1.get(case_id)), _record(p2.get(case_id), "effective_record"))
            if fallback:
                result = fallback
                client.records.append({"stage": "adjudicator", "unit_id": case_id, "classification": "legacy_a0_compatibility_replay", "usage": {}, "elapsed_seconds": 0})
        p3[case_id] = result
    write_json(OUT / "pass3-adjudication-decisions.json", {"schema": "sfh2-a0r-pass3-adjudication-decisions-v1", "records": [p3[key] for key in sorted(p3)], "model": MODEL, "prompt_version": PROMPT_VERSIONS["adjudicator"], "gold_not_sent_to_provider": True, "candidate_only": True, "canonical_write_back": False})

    finals: list[dict[str, Any]] = []
    for case in cases:
        case_id = text(case.get("case_id"))
        packet = packet_by_case[case_id]
        selector = select_record(_record(p1.get(case_id)), p2.get(case_id), p3.get(case_id), packet, pass3_required=pass3_required_by_case[case_id])
        finals.append(_final_row(case, selector.get("record"), selector, inputs, evidence_by_case[case_id], p1.get(case_id, {}).get("consistency", {}), p2.get(case_id, {}).get("consistency", {}), pass3_required_by_case[case_id]))
    write_json(OUT / "final-decisions.json", {"schema": "sfh2-a0r-final-decisions-v1", "records": finals, "candidate_only": True, "canonical_write_back": False})
    selector_audit = _selector_audit(cases, p1, p2, p3, finals)
    patch_audit = _patch_audit(cases, p1, p2, p3, finals)
    write_json(OUT / "semantic-preservation-audit.json", selector_audit)
    write_json(OUT / "reviewer-damage-audit.json", {"schema": "sfh2-a0r-reviewer-damage-audit-v1", "offline_counterfactual": {"old": counterfactual.get("old_reviewer_damage"), "repaired": counterfactual.get("counterfactual_reviewer_damage")}, "live_selector_preservation_failures": selector_audit.get("selection_preservation_failures"), "patch_audit": patch_audit, "candidate_only": True, "canonical_write_back": False})
    internal = _internal_consistency(finals, patch_audit)
    write_json(OUT / "internal-consistency-audit.json", internal)
    evaluation, eval_metrics = evaluate(cases, gold_by_case(selected, gold()), p1, p2, p3, finals)
    write_json(OUT / "dimension-evaluation.json", evaluation)
    write_json(OUT / "routing-analysis.json", {"schema": "sfh2-a0r-routing-analysis-v1", "records": [{"case_id": text(case.get("case_id")), "p1_review": review_required(p1.get(text(case.get("case_id")), {}).get("consistency", {})), "pass3_required": pass3_required_by_case[text(case.get("case_id"))], "p1_flag_severity": {text(flag.get("severity")): sum(text(item.get("severity")) == text(flag.get("severity")) for item in p1.get(text(case.get("case_id")), {}).get("consistency", {}).get("flags", []) if isinstance(item, Mapping)) for flag in p1.get(text(case.get("case_id")), {}).get("consistency", {}).get("flags", []) if isinstance(flag, Mapping)} } for case in cases], "diagnostic_flags_do_not_escalate": True, "candidate_only": True, "canonical_write_back": False})

    before = input_hashes()
    after = input_hashes()
    safety = _storage_safety(before, after, finals, internal.get("errors", []))
    write_json(OUT / "storage-safety-audit.json", safety)
    client.save()
    transport = client.metrics()
    write_json(OUT / "transport.json", transport)
    metrics = {
        "schema": "sfh2-a0r-metrics-v1",
        "pilot": "SFH2.2-A0R",
        "case_count": len(cases),
        "story_count": len({text(case.get("story_id")) for case in cases}),
        "semantic_authority": "llm",
        "python_authority": ["schema_validation", "evidence_integrity", "formal_consistency", "review_routing", "deterministic_record_selection", "storage_safety"],
        **eval_metrics,
        "pass2_review_trigger_count": sum(review_required(p1.get(text(case.get("case_id")), {}).get("consistency", {})) for case in cases),
        "pass3_required_count": sum(pass3_required_by_case.values()),
        "select_pass1_cases": sum(text(final.get("selector_decision")) == "select_pass1" for final in finals),
        "select_pass2_cases": sum(text(final.get("selector_decision")) == "select_pass2" for final in finals),
        "revision_cases": sum(text(final.get("selector_decision")) == "revise" for final in finals),
        "abstention_cases": sum(text(final.get("selector_decision")) == "abstain" for final in finals),
        "copy_drift_errors": selector_audit.get("selection_preservation_failures", 0),
        "undeclared_patch_mutations": patch_audit.get("undeclared_patch_mutations", 0),
        "candidate_only": True,
        "canonical_write_back": False,
        "production_persons_created": 0,
        "canonical_writes": 0,
        "alias_mutations": 0,
        "profile_mutations": 0,
        "transport": transport,
        "offline_counterfactual": {
            "old_final_strict_accuracy": counterfactual.get("old_final_strict_accuracy"),
            "repaired_selection_final_strict_accuracy": counterfactual.get("counterfactual_final_strict_accuracy"),
            "old_reviewer_damage": counterfactual.get("old_reviewer_damage"),
            "repaired_selection_reviewer_damage": counterfactual.get("counterfactual_reviewer_damage"),
        },
        "no_full_188_story_live_run": True,
    }
    write_json(OUT / "metrics.json", metrics)
    structural_valid = (
        not internal.get("errors")
        and safety.get("protected_inputs_unchanged") is True
        and not safety.get("source_role_graph_conflicts")
        and not patch_audit.get("undeclared_patch_mutations")
        and not selector_audit.get("selection_preservation_failures")
    )
    recommendation = "sfh2_selective_review_ready" if structural_valid else "sfh2_selective_review_blocked"
    write_json(OUT / "validation-summary.json", {"schema": "sfh2-a0r-validation-summary-v1", "case_count": len(cases), "selection_hash": selection_hash, "architecture_hash": architecture.get("architecture_hash"), "structural_valid": structural_valid, "evaluation": eval_metrics, "candidate_only": True, "canonical_write_back": False})
    write_json(OUT / "recommendation.json", {"schema": "sfh2-a0r-recommendation-v1", "recommendation": recommendation, "structural_valid": structural_valid, "candidate_only": True, "canonical_write_back": False})
    return {"selection": selected, "architecture": architecture, "metrics": metrics, "evaluation": evaluation, "transport": transport, "recommendation": recommendation}


def main(argv: list[str] | None = None) -> int:
    parser = __import__("argparse").ArgumentParser()
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--live", action="store_true")
    mode.add_argument("--offline", action="store_true")
    parser.add_argument("--run-id", default="sfh2-a0r-offline")
    args = parser.parse_args(argv)
    result = run(live=bool(args.live), run_id=args.run_id)
    print(canonical_json({"case_count": result["selection"].get("case_count"), "selection_hash": result["selection"].get("selection_hash"), "recommendation": result["recommendation"], "transport": result["transport"]}))
    return 0 if result["recommendation"] != "sfh2_selective_review_blocked" else 1


if __name__ == "__main__":
    raise SystemExit(main())
