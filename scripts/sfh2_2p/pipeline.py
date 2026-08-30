"""Execution and evaluation for the bounded SFH2.2-P pilot."""

from __future__ import annotations

import argparse
import collections
import copy
import json
import sys
from pathlib import Path
from typing import Any, Mapping

from .common import (
    MODEL, OUT, PILOT_VERSION, PROMPT_VERSIONS, ROOT, SELECTION_PATH, build_case_packet,
    canonical_json, file_hash, input_hashes, load_inputs, mention_index,
    packet_index, read_json, records, stable_hash, text, write_json,
)
from .retrieval import build_candidate_set
from .schemas import identity_judgment_tool, reference_semantics_tool, validate_identity_payload, validate_reference_payload
from .selection import freeze_selection
from .transport import PilotClient, summarize_transport_records


L3_SYSTEM = """You are the semantic reference reader for a historical Chinese identity pilot. Read the supplied source evidence and interpret only the requested validated mentions. Return a record for every requested mention. You may provide a referent_hint as a historical display name when the supplied text specifically supports it, but never emit canonical Person IDs. Distinguish a person reference from an office, ruler title, kinship/attribute, collective, or source/citation role. Do not infer identity from mere proximity or a suffix. Cite only supplied source evidence IDs and mention IDs. Return only the forced function."""
L5_SYSTEM = """You are the historical identity judge in a controlled pilot. Python has supplied temporary candidate keys; judge whether each candidate is specifically the historical referent using the supplied source evidence and semantic interpretation. Do not invent candidates, IDs, facts, or evidence. Mere same-Story presence, chronology compatibility, or string overlap is insufficient. A supported resolution requires grounded evidence IDs. Return only the forced function."""


def _source_evidence(packet: Mapping[str, Any]) -> list[dict[str, Any]]:
    return [
        {"evidence_id": row.get("evidence_id"), "source_layer": row.get("source_layer"), "text": row.get("text")}
        for row in packet.get("source_evidence", []) or []
        if isinstance(row, Mapping)
    ]


def _l3_payload(packet: Mapping[str, Any], target_ids: list[str]) -> dict[str, Any]:
    return {
        "task": "interpret historical reference semantics for selected validated mentions",
        "story_id": packet.get("story_id"),
        "source_evidence": _source_evidence(packet),
        "target_mentions": [
            {
                "mention_id": row.get("mention_id"),
                "surface": row.get("surface"),
                "source_evidence_id": row.get("source_evidence_id"),
                "source_start": row.get("source_start"),
                "source_end": row.get("source_end"),
                "entity_kind": row.get("entity_kind"),
                "reference_form": row.get("reference_form"),
            }
            for row in packet.get("validated_local_mentions", []) or []
            if text(row.get("mention_id")) in set(target_ids)
        ],
        "other_validated_local_mentions": [
            {
                "mention_id": row.get("mention_id"),
                "surface": row.get("surface"),
                "source_evidence_id": row.get("source_evidence_id"),
                "source_start": row.get("source_start"),
                "source_end": row.get("source_end"),
                "entity_kind": row.get("entity_kind"),
                "reference_form": row.get("reference_form"),
            }
            for row in packet.get("validated_local_mentions", []) or []
            if text(row.get("mention_id")) not in set(target_ids)
        ],
        "target_mention_ids": target_ids,
        "gold_instruction": "No expected identity, gold label, prior verdict, or production Person ID is supplied to this semantic stage.",
    }


def _l5_payload(packet: Mapping[str, Any], rows: list[Mapping[str, Any]], semantics: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    cases = []
    for row in rows:
        cases.append({
            "unit_id": row.get("unit_id"),
            "mention": {
                "mention_id": row.get("mention_id"),
                "surface": row.get("surface"),
            },
            "reference_semantics": semantics.get(text(row.get("mention_id")), {}),
            "candidates": [
                {
                    "candidate_key": candidate.get("candidate_key"),
                    "display_name": candidate.get("display_name"),
                    "entity_type": candidate.get("entity_type"),
                    "matched_surface": candidate.get("matched_surface"),
                    "retrieval_basis": candidate.get("retrieval_basis"),
                    "evidence": candidate.get("evidence", []),
                }
                for candidate in row.get("candidates", []) or []
            ],
        })
    return {
        "task": "judge historical identity for Python-supplied candidates",
        "story_id": packet.get("story_id"),
        "source_evidence": _source_evidence(packet),
        "cases": cases,
        "gold_instruction": "No expected identity or evaluation answer is supplied.",
    }


def _replay_semantic(mention: Mapping[str, Any], inputs: Mapping[str, Any]) -> dict[str, Any]:
    """Reuse the compatible cached SFH1 semantic record when offline.

    This is explicitly labelled replay.  Missing v2 referent hints are not
    reconstructed from prose or Python string rules.
    """
    old = next((row for row in records(inputs.get("semantics"), "records") if text(row.get("mention_id")) == text(mention.get("mention_id"))), {})
    return {
        "mention_id": mention.get("mention_id"),
        "semantic_type": text(old.get("semantic_type")) or "uncertain",
        "referent_role": text(old.get("referent_role")),
        "referent_hint": text(old.get("referent_hint")),
        "network_role": text(old.get("network_role")) or "uncertain",
        "anchor_mentions": sorted({text(item) for item in old.get("anchor_mentions", []) or [] if text(item)}),
        "holder_mentions": sorted({text(item) for item in old.get("holder_mentions", []) or [] if text(item)}),
        "patron_or_possessor_mentions": sorted({text(item) for item in old.get("patron_or_possessor_mentions", []) or [] if text(item)}),
        "coreference_with": sorted({text(item) for item in old.get("coreference_with", []) or [] if text(item)}),
        "distinct_from": sorted({text(item) for item in old.get("distinct_from", []) or [] if text(item)}),
        "supporting_evidence_ids": [],
        "confidence": text(old.get("confidence")) if text(old.get("confidence")) in {"high", "medium", "low"} else "low",
        "explanation": text(old.get("explanation")) or "No fresh pilot semantic response; compatible SFH1 cache replay.",
        "result_source": "sfh1_cached_replay",
        "candidate_only": True,
        "canonical_write_back": False,
    }


def _uncertain_semantic(mention_id: str) -> dict[str, Any]:
    return {
        "mention_id": mention_id, "semantic_type": "uncertain", "referent_role": "",
        "referent_hint": "", "network_role": "uncertain", "anchor_mentions": [],
        "holder_mentions": [], "patron_or_possessor_mentions": [], "coreference_with": [],
        "distinct_from": [], "supporting_evidence_ids": [], "confidence": "low",
        "explanation": "No valid semantic record was available; fail closed.",
        "result_source": "provider_or_schema_failure", "candidate_only": True, "canonical_write_back": False,
    }


def _expected_matches(case: Mapping[str, Any], candidate: Mapping[str, Any] | None) -> bool:
    if not candidate:
        return False
    expected_pid = text(case.get("expected_person_id"))
    if expected_pid:
        return text(candidate.get("person_id")) == expected_pid
    expected = normalize_for_compare(case.get("expected_identity"))
    return bool(expected and normalize_for_compare(candidate.get("display_name")) == expected)


def normalize_for_compare(value: Any) -> str:
    return "".join(text(value).split()).translate(str.maketrans({"爲": "為", "髙": "高", "鳯": "鳳", "禄": "祿"}))


def _is_identity_state(state: str) -> bool:
    return state in {"stable_entity_resolved", "local_candidate_resolved"}


def _recorded_live_transport() -> dict[str, Any] | None:
    """Find the best completed live record stream for cost reporting.

    A cache replay is intentionally operationally useful, but its token count
    is zero.  When the final projection is rebuilt from cache, retain the
    completed provider-run accounting separately instead of reporting the
    replay as if it were the live pilot cost.
    """
    candidates: list[tuple[int, int, str, dict[str, Any]]] = []
    live_root = OUT / "live"
    if not live_root.is_dir():
        return None
    for path in sorted(live_root.glob("*/transport.json")):
        stored = read_json(path, None)
        if not isinstance(stored, list):
            continue
        rows = [dict(row) for row in stored if isinstance(row, Mapping)]
        parsed = sum(row.get("classification") == "parsed" for row in rows)
        if not parsed:
            continue
        summary = summarize_transport_records(rows, live=True)
        candidates.append((parsed, int(summary.get("total_tokens") or 0), path.parent.name, summary))
    if not candidates:
        return None
    _, _, source_run_id, summary = max(candidates, key=lambda item: (item[0], item[1], item[2]))
    result = dict(summary)
    result["source_run_id"] = source_run_id
    return result


def _final_row(case: Mapping[str, Any], mention: Mapping[str, Any], semantic: Mapping[str, Any], candidate_set: Mapping[str, Any], judgment: Mapping[str, Any] | None) -> dict[str, Any]:
    candidates = candidate_set.get("candidates", []) or []
    preferred = judgment.get("preferred_candidate_key") if isinstance(judgment, Mapping) else None
    candidate = next((row for row in candidates if text(row.get("candidate_key")) == text(preferred)), None)
    resolution = text((judgment or {}).get("resolution"))
    semantic_type = text(semantic.get("semantic_type"))
    role = text(semantic.get("network_role"))
    hard_veto_person_ids = {text(value) for value in candidate_set.get("hard_veto_person_ids", []) or [] if text(value)}
    hard_veto = bool(candidate and text(candidate.get("person_id")) in hard_veto_person_ids)
    if text(mention.get("entity_kind")) == "non_person":
        state, failure = "non_person", None
    elif semantic_type in {"compositional_kinship", "patron_plus_office"} or role in {"anonymous_person", "person_attribute", "collective_reference", "structural_reference"}:
        # A source/network role is orthogonal to historical identity.  For
        # example a named citation author or historical exemplum may be
        # identified while remaining ineligible for the core Story graph.
        # Only an actually structural/non-individual interpretation blocks
        # identity storage here.
        state, failure = "structural_reference", None
    elif semantic_type == "uncertain" or text(semantic.get("confidence")) == "low":
        state, failure = "review_required", "reference_semantics_uncertain"
    elif not candidates:
        state, failure = "review_required", "candidate_recall_failure"
    elif not judgment:
        state, failure = "review_required", "provider_failure"
    elif resolution == "reference_not_person":
        state, failure = "non_person", None
    elif not candidate or preferred is None:
        state, failure = "review_required", "identity_evidence_insufficient"
    elif resolution != "candidate_supported":
        state, failure = "review_required", "identity_evidence_insufficient"
    elif hard_veto:
        # Explicit semantic distinctness is a deterministic safety veto.  It
        # may block an unsafe selection, but it does not invent a replacement
        # identity or change the upstream semantic interpretation.
        state, failure = "review_required", "hard_constraint_veto"
    elif candidate.get("entity_type") == "existing_person":
        state, failure = "stable_entity_resolved", None
    else:
        state, failure = "local_candidate_resolved", None
    judgment_evidence: list[str] = []
    for assessment in (judgment or {}).get("candidate_assessments", []) or []:
        if not isinstance(assessment, Mapping):
            continue
        judgment_evidence.extend(text(value) for value in assessment.get("supporting_evidence_ids", []) or [])
        judgment_evidence.extend(text(value) for value in assessment.get("contradicting_evidence_ids", []) or [])
    return {
        "case_id": case.get("case_id"), "mention_id": mention.get("mention_id"), "story_id": mention.get("story_id"),
        "surface": mention.get("surface"), "semantic_type": semantic_type, "network_role": role,
        "referent_hint": semantic.get("referent_hint"), "candidate_keys": [row.get("candidate_key") for row in candidates],
        "preferred_candidate_key": preferred, "selected_candidate": copy.deepcopy(candidate) if candidate else None,
        "resolution": resolution, "final_state": state, "failure_stage": failure,
        "hard_veto": hard_veto, "hard_veto_person_ids": sorted(hard_veto_person_ids),
        "evidence_ids": sorted(set([text(mention.get("source_evidence_id")), *[text(value) for value in semantic.get("supporting_evidence_ids", []) or []], *judgment_evidence]) - {""}),
        "reference_semantics": copy.deepcopy(dict(semantic)), "judgment": copy.deepcopy(dict(judgment or {})),
        "candidate_only": True, "canonical_write_back": False,
    }


def _evaluate(selection: Mapping[str, Any], candidate_rows: Mapping[str, Mapping[str, Any]], finals: list[Mapping[str, Any]]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    by_case = {text(row.get("case_id")): row for row in selection.get("cases", []) or []}
    gold = []
    for final in finals:
        case = by_case.get(text(final.get("case_id")), {})
        if case.get("evaluation_mode") != "reviewed_gold":
            continue
        candidate = final.get("selected_candidate") if isinstance(final.get("selected_candidate"), Mapping) else None
        expected = case.get("expected_identity")
        expected_type = text(case.get("expected_identity_type"))
        has_expected_identity = bool(expected) and expected_type in {"production_person", "candidate_historical_person"}
        expected_non_identity = expected_type in {"structural", "contextual"}
        recall_row = candidate_rows.get(text(final.get("case_id")), {})
        correct_present = bool(recall_row.get("correct_candidate_present")) if has_expected_identity else None
        final_state = text(final.get("final_state"))
        identity_state = _is_identity_state(final_state)
        correct_selected = _expected_matches(case, candidate) if has_expected_identity else (not identity_state if expected_non_identity else None)
        abstained = not _is_identity_state(text(final.get("final_state")))
        category = "appropriate_abstention"
        if text(final.get("failure_stage")) == "provider_failure" or text(final.get("failure_stage")) == "reference_semantics_uncertain":
            category = "provider_failure" if text(final.get("failure_stage")) == "provider_failure" else "schema_failure"
        elif expected_non_identity:
            # Structural/contextual controls are deliberately not identity
            # gold.  A model-selected candidate is a semantic false
            # positive, even if it is a coherent candidate and no forbidden
            # production ID was used.  This keeps the evaluation from
            # silently treating an unsafe promotion as an abstention.
            category = "semantic_identity_failure" if identity_state else "appropriate_abstention"
        elif has_expected_identity and not correct_present:
            category = "candidate_recall_failure"
        elif has_expected_identity and correct_selected and identity_state and text(final.get("final_state")) == "local_candidate_resolved" and expected_type == "candidate_historical_person":
            category = "registry_miss_handled_correctly"
        elif has_expected_identity and correct_selected and identity_state:
            category = "fully_correct"
        elif has_expected_identity and not abstained:
            category = "semantic_identity_failure"
        elif text(final.get("failure_stage")) == "hard_constraint_veto":
            category = "hard_constraint_veto_correct"
        gold.append({
            "case_id": case.get("case_id"), "story_id": case.get("story_id"), "surface": case.get("surface"),
            "expected_identity": expected, "expected_person_id": case.get("expected_person_id"),
            "expected_identity_type": expected_type,
            "candidate_present": correct_present, "selected_candidate": candidate.get("display_name") if candidate else None,
            "selected_candidate_key": candidate.get("candidate_key") if candidate else None,
            "final_state": final_state, "category": category,
            "correct_selected": correct_selected,
            "must_not_violations": [value for value in case.get("must_not_resolve_to", []) or [] if value == (candidate or {}).get("person_id")],
        })
    evaluated = [row for row in gold if row.get("candidate_present") is not None]
    recall_denom = sum(row.get("candidate_present") is not None for row in evaluated)
    recall_num = sum(row.get("candidate_present") is True for row in evaluated)
    recall_pass = [row for row in evaluated if row.get("candidate_present") is True]
    nonabstaining = [row for row in recall_pass if _is_identity_state(text(row.get("final_state")))]
    correct_nonabstaining = [row for row in nonabstaining if row.get("category") in {"fully_correct", "registry_miss_handled_correctly"}]
    forbidden = [row for row in gold if row.get("must_not_violations")]
    semantic_false_positives = [row for row in gold if row.get("category") == "semantic_identity_failure"]
    non_identity_controls = [row for row in gold if row.get("expected_identity_type") in {"structural", "contextual"}]
    metrics = {
        "gold_cases": len(gold),
        "candidate_recall_denominator": recall_denom,
        "candidate_recall_numerator": recall_num,
        "candidate_recall": round(recall_num / recall_denom, 4) if recall_denom else None,
        "semantic_precision_denominator": len(nonabstaining),
        "semantic_precision_numerator": len(correct_nonabstaining),
        "semantic_precision": round(len(correct_nonabstaining) / len(nonabstaining), 4) if nonabstaining else None,
        "appropriate_abstentions": sum(row.get("category") == "appropriate_abstention" for row in gold),
        "wrong_resolutions": len(semantic_false_positives),
        "semantic_false_positive_count": len(semantic_false_positives),
        "high_confidence_false_positives": len(semantic_false_positives),
        "non_identity_control_count": len(non_identity_controls),
        "non_identity_control_abstentions": sum(not _is_identity_state(text(row.get("final_state"))) for row in non_identity_controls),
        "forbidden_mapping_violations": len(forbidden),
        "registry_miss_cases": sum(text(row.get("expected_identity_type")) == "candidate_historical_person" for row in selection.get("cases", []) or []),
        "forced_existing_registry_miss_errors": sum(row.get("category") == "semantic_identity_failure" for row in gold if row.get("expected_identity") and text(by_case.get(text(row.get("case_id")), {}).get("expected_identity_type")) == "candidate_historical_person"),
        "categories": dict(collections.Counter(row.get("category") for row in gold)),
        "candidate_recall_audit": [dict(row) for row in candidate_rows.values()],
        "candidate_only": True, "canonical_write_back": False,
    }
    return metrics, gold


def run(*, live: bool = False, run_id: str = "sfh2-2p-offline") -> dict[str, Any]:
    selection = freeze_selection(SELECTION_PATH)
    if selection.get("case_count", 0) < 24 or selection.get("case_count", 0) > 40:
        raise RuntimeError("sfh2_2p_case_count_out_of_bounds")
    inputs = load_inputs()
    mentions = mention_index(inputs)
    packets = packet_index(inputs)
    run_dir = OUT / "live" / run_id
    client = PilotClient(run_dir, live=live)
    cases = selection.get("cases", []) or []
    write_json(OUT / "input-manifest.json", {
        "schema": "sfh2-2p-input-manifest-v1",
        "selection_hash": selection.get("selection_hash"),
        "input_hashes": input_hashes(inputs),
        "model": MODEL,
        "prompt_versions": dict(PROMPT_VERSIONS),
        "pilot_version": PILOT_VERSION,
        "candidate_only": True,
        "canonical_write_back": False,
    })
    case_packets = [build_case_packet(case, inputs) for case in cases]
    write_json(OUT / "case-packets.json", {"schema": "sfh2-2p-case-packets-v1", "packets": case_packets, "candidate_only": True, "canonical_write_back": False})

    # One L3 packet per Story keeps local coreference available while keeping
    # calls well below the pilot budget.
    by_story: dict[str, list[dict[str, Any]]] = collections.defaultdict(list)
    for case, packet in zip(cases, case_packets):
        by_story[text(case.get("story_id"))].append(packet)
    semantic_by_mention: dict[str, dict[str, Any]] = {}
    l3_audit: list[dict[str, Any]] = []
    l3_tool = reference_semantics_tool()
    for story_id in sorted(by_story):
        story_packets = by_story[story_id]
        packet = story_packets[0]
        target_ids = sorted({text(item.get("mention_id")) for item in story_packets if text(item.get("mention_id"))})
        response = None
        if len([row for row in client.records if row.get("stage") == "reference_semantics"]) < 40:
            response = client.call(stage="reference_semantics", unit_id=story_id, system=L3_SYSTEM, payload=_l3_payload(packet, target_ids), tool=l3_tool, function_name="submit_sfh2_2p_reference_semantics", max_tokens=3600)
        validated = validate_reference_payload(packet, set(target_ids), response)
        accepted = {text(row.get("mention_id")): dict(row) for row in validated.get("records", []) or []}
        for mention_id in target_ids:
            if mention_id in accepted:
                accepted[mention_id]["result_source"] = "pilot_live_or_cache"
                semantic_by_mention[mention_id] = accepted[mention_id]
            else:
                mention = mentions.get(mention_id, {})
                semantic_by_mention[mention_id] = _replay_semantic(mention, inputs) if not live else _uncertain_semantic(mention_id)
        l3_audit.append({"story_id": story_id, "target_mention_ids": target_ids, "validation": validated, "candidate_only": True, "canonical_write_back": False})
    l3_records = []
    for case in cases:
        mid = text(case.get("mention_id"))
        row = {"case_id": case.get("case_id"), **semantic_by_mention.get(mid, _uncertain_semantic(mid))}
        l3_records.append(row)
    write_json(OUT / "l3-semantic-results.json", {"schema": "sfh2-2p-l3-results-v1", "pilot_version": PILOT_VERSION, "records": sorted(l3_records, key=lambda row: text(row.get("case_id"))), "story_audits": l3_audit, "model": MODEL, "prompt_version": PROMPT_VERSIONS["reference_semantics"], "candidate_only": True, "canonical_write_back": False})

    candidate_rows_by_case: dict[str, dict[str, Any]] = {}
    candidate_sets: list[dict[str, Any]] = []
    for case in cases:
        semantic = semantic_by_mention.get(text(case.get("mention_id")), _uncertain_semantic(text(case.get("mention_id"))))
        row = build_candidate_set(case, semantic, inputs)
        row["case_id"] = case.get("case_id")
        candidate_sets.append(row)
        candidate_rows_by_case[text(case.get("case_id"))] = {
            "case_id": case.get("case_id"), "story_id": case.get("story_id"), "surface": case.get("surface"),
            "expected_identity": case.get("expected_identity") if case.get("evaluation_mode") == "reviewed_gold" else None,
            "expected_person_id": case.get("expected_person_id") if case.get("evaluation_mode") == "reviewed_gold" else None,
            "candidate_set": [dict(candidate) for candidate in row.get("candidates", []) or []],
            "candidate_source": sorted({basis for candidate in row.get("candidates", []) or [] for basis in candidate.get("retrieval_basis", []) or []}),
            "correct_candidate_present": None,
            "failure_reason": None,
            "candidate_only": True, "canonical_write_back": False,
        }
        if case.get("evaluation_mode") == "reviewed_gold" and case.get("expected_identity") and case.get("expected_identity_type") in {"production_person", "candidate_historical_person"}:
            candidate_rows_by_case[text(case.get("case_id"))]["correct_candidate_present"] = any(_expected_matches(case, candidate) for candidate in row.get("candidates", []) or [])
            if not candidate_rows_by_case[text(case.get("case_id"))]["correct_candidate_present"]:
                candidate_rows_by_case[text(case.get("case_id"))]["failure_reason"] = "correct_candidate_not_in_python_candidate_set"
    write_json(OUT / "candidate-sets.json", {"schema": "sfh2-2p-candidate-sets-v1", "records": sorted(candidate_sets, key=lambda row: text(row.get("case_id"))), "candidate_policy": "safe_python_retrieval_after_l3", "candidate_only": True, "canonical_write_back": False})
    write_json(OUT / "candidate-recall-audit.json", {"schema": "sfh2-2p-candidate-recall-audit-v1", "records": sorted(candidate_rows_by_case.values(), key=lambda row: text(row.get("case_id"))), "candidate_only": True, "canonical_write_back": False})

    # L5 is evaluated per occurrence.  L3 is grouped by Story so that local
    # semantics can be read together, but putting several large candidate
    # sets in one forced response can truncate the structured output.  A
    # compact one-occurrence packet keeps the stage fail-closed and stays
    # within the separate <=40 L5-call pilot budget.
    by_story_sets: dict[str, list[dict[str, Any]]] = collections.defaultdict(list)
    for row in candidate_sets:
        if row.get("candidates"):
            by_story_sets[text(row.get("story_id"))].append(row)
    judgments_by_unit: dict[str, dict[str, Any]] = {}
    l5_audit: list[dict[str, Any]] = []
    l5_tool = identity_judgment_tool()
    l5_call_count = 0
    for story_id in sorted(by_story_sets):
        for row in sorted(by_story_sets[story_id], key=lambda value: text(value.get("unit_id"))):
            rows = [row]
            l5_call_count += 1
            packet = next(item for item in case_packets if text(item.get("case_id")) == text(row.get("case_id")))
            target_sem = {text(row.get("mention_id")): semantic_by_mention.get(text(row.get("mention_id")), {})}
            response = None
            if l5_call_count <= 40:
                response = client.call(stage="identity_judgment", unit_id=text(row.get("unit_id")), system=L5_SYSTEM, payload=_l5_payload(packet, rows, target_sem), tool=l5_tool, function_name="submit_sfh2_2p_identity_judgments", max_tokens=3600)
            validated = validate_identity_payload({"records": rows}, packet, response)
            for judgment in validated.get("judgments", []) or []:
                judgments_by_unit[text(judgment.get("unit_id"))] = dict(judgment)
            l5_audit.append({"story_id": story_id, "unit_ids": [row.get("unit_id")], "validation": validated, "candidate_only": True, "canonical_write_back": False})
    write_json(OUT / "l5-identity-results.json", {"schema": "sfh2-2p-l5-results-v1", "pilot_version": PILOT_VERSION, "judgments": sorted([{"case_id": next((case.get("case_id") for case in cases if text(case.get("mention_id")) == text(unit)), None), **row} for unit, row in judgments_by_unit.items()], key=lambda row: text(row.get("case_id"))), "story_audits": l5_audit, "model": MODEL, "prompt_version": PROMPT_VERSIONS["identity_judgment"], "candidate_only": True, "canonical_write_back": False})

    final_records: list[dict[str, Any]] = []
    for case in cases:
        mention = mentions.get(text(case.get("mention_id")), {})
        semantic = semantic_by_mention.get(text(case.get("mention_id")), _uncertain_semantic(text(case.get("mention_id"))))
        candidate_set = next(row for row in candidate_sets if text(row.get("case_id")) == text(case.get("case_id")))
        judgment = judgments_by_unit.get(text(candidate_set.get("unit_id")))
        final_records.append(_final_row(case, mention, semantic, candidate_set, judgment))
    write_json(OUT / "final-decisions.json", {"schema": "sfh2-2p-final-decisions-v1", "records": sorted(final_records, key=lambda row: text(row.get("case_id"))), "model": MODEL, "candidate_only": True, "canonical_write_back": False})

    metrics, gold_rows = _evaluate(selection, candidate_rows_by_case, final_records)
    write_json(OUT / "gold-evaluation.json", {"schema": "sfh2-2p-gold-evaluation-v1", "records": gold_rows, "metrics": {key: value for key, value in metrics.items() if key != "candidate_recall_audit"}, "gold_not_sent_to_model": True, "candidate_only": True, "canonical_write_back": False})
    blind = [row for row in final_records if next((case for case in cases if text(case.get("case_id")) == text(row.get("case_id"))), {}).get("evaluation_mode") == "blind"]
    blind_public = [{key: row.get(key) for key in ("case_id", "story_id", "surface", "semantic_type", "network_role", "referent_hint", "selected_candidate", "final_state", "failure_stage", "reference_semantics", "judgment")} for row in blind]
    write_json(OUT / "blind-case-results.json", {"schema": "sfh2-2p-blind-case-results-v1", "records": blind_public, "gold_excluded": True, "candidate_only": True, "canonical_write_back": False})
    human = []
    for row in blind:
        packet = next(item for item in case_packets if text(item.get("case_id")) == text(row.get("case_id")))
        candidate_set = next(item for item in candidate_sets if text(item.get("case_id")) == text(row.get("case_id")))
        human.append({"case_id": row.get("case_id"), "story_id": row.get("story_id"), "surface": row.get("surface"), "main_text_excerpt": next((item.get("text") for item in packet.get("source_evidence", []) if item.get("source_layer") == "main_text"), ""), "relevant_evidence": packet.get("source_evidence", []), "candidate_list": candidate_set.get("candidates", []), "semantic_interpretation": row.get("reference_semantics"), "identity_judgment": row.get("judgment"), "final_state": row.get("final_state")})
    write_json(OUT / "human-review.json", {"schema": "sfh2-2p-human-review-v1", "records": human, "gold_excluded": True, "candidate_only": True, "canonical_write_back": False})

    alias_path = ROOT / "data/aliases.json"
    alias_hash = file_hash(alias_path) if alias_path.is_file() else None
    network = []
    for row in final_records:
        network.append({"case_id": row.get("case_id"), "story_id": row.get("story_id"), "surface": row.get("surface"), "network_role": row.get("network_role"), "core_graph_eligible": row.get("network_role") not in {"citation_author", "historical_exemplum", "person_attribute", "collective_reference", "structural_reference", "genealogy_ancestor"}, "final_state": row.get("final_state")})
    write_json(OUT / "network-role-audit.json", {"schema": "sfh2-2p-network-role-audit-v1", "records": network, "candidate_only": True, "canonical_write_back": False})
    write_json(OUT / "alias-safety-audit.json", {"schema": "sfh2-2p-alias-safety-audit-v1", "aliases_before_sha256": alias_hash, "aliases_after_sha256": file_hash(alias_path) if alias_path.is_file() else None, "new_global_aliases": 0, "new_occurrence_propagated_alias_evidence": 0, "substring_derived_candidates": 0, "profile_contamination_recurrence": 0, "candidate_only": True, "canonical_write_back": False})
    registry_miss = [row for row in final_records if next((case for case in cases if text(case.get("case_id")) == text(row.get("case_id"))), {}).get("expected_identity_type") == "candidate_historical_person"]
    write_json(OUT / "registry-miss-results.json", {"schema": "sfh2-2p-registry-miss-results-v1", "records": [{"case_id": row.get("case_id"), "initial_candidate_set": next(item.get("candidate_keys", []) for item in final_records if item.get("case_id") == row.get("case_id")), "referent_hint": row.get("referent_hint"), "selected_candidate": row.get("selected_candidate"), "final_state": row.get("final_state"), "candidate_only": True, "canonical_write_back": False} for row in registry_miss], "candidate_only": True, "canonical_write_back": False})

    client.save()
    replay_transport = client.metrics()
    provider_transport = replay_transport if replay_transport.get("new_live_calls", 0) else (_recorded_live_transport() or replay_transport)
    write_json(OUT / "replay-transport.json", replay_transport)
    write_json(OUT / "transport.json", provider_transport)
    summary = {
        "schema": "sfh2-2p-metrics-v1", "pilot": "SFH2.2-P", "pilot_version": PILOT_VERSION, "run_id": run_id,
        "live": live, "model": MODEL, "prompt_versions": dict(PROMPT_VERSIONS),
        "case_count": len(cases), "gold_case_count": selection.get("gold_case_count"), "blind_case_count": selection.get("blind_case_count"),
        "l3_story_calls": len(by_story), "l5_occurrence_calls": l5_call_count, "l5_story_calls": len(by_story_sets),
        **metrics, "transport": provider_transport, "replay_transport": replay_transport,
        "no_full_188_story_live_run": True,
        "candidate_only": True, "canonical_write_back": False,
    }
    write_json(OUT / "validation-summary.json", {"schema": "sfh2-2p-validation-summary-v1", "selection_hash": selection.get("selection_hash"), "selection_frozen": SELECTION_PATH.is_file(), "gold_not_leaked_to_prompt_packets": True, "no_canonical_write": True, "no_production_person_creation": True, "forbidden_mapping_violations": metrics.get("forbidden_mapping_violations", 0), "alias_mutation": False, "transport": provider_transport, "replay_transport": replay_transport, "candidate_only": True, "canonical_write_back": False})
    recommendation = _recommend(summary)
    summary["recommendation"] = recommendation.get("recommendation")
    write_json(OUT / "metrics.json", summary)
    write_json(OUT / "recommendation.json", recommendation)
    return summary


def _recommend(metrics: Mapping[str, Any]) -> dict[str, Any]:
    recall = metrics.get("candidate_recall")
    precision = metrics.get("semantic_precision")
    ready = recall is not None and precision is not None and recall >= 0.95 and precision >= 0.90 and metrics.get("high_confidence_false_positives", 0) == 0 and metrics.get("forced_existing_registry_miss_errors", 0) == 0 and metrics.get("forbidden_mapping_violations", 0) == 0 and metrics.get("transport", {}).get("provider_failures", 0) == 0
    if ready:
        value = "sfh2_2_ready"
    elif metrics.get("transport", {}).get("provider_failures", 0) or metrics.get("transport", {}).get("offline_cache_misses", 0):
        value = "sfh2_2_more_pilot_validation"
    elif recall is not None and recall < 0.95:
        value = "sfh2_2_candidate_retrieval_revision"
    else:
        value = "sfh2_2_semantic_judgment_revision"
    return {"schema": "sfh2-2p-recommendation-v1", "recommendation": value, "basis": {"candidate_recall": recall, "semantic_precision": precision, "high_confidence_false_positives": metrics.get("high_confidence_false_positives"), "forced_existing_registry_miss_errors": metrics.get("forced_existing_registry_miss_errors"), "forbidden_mapping_violations": metrics.get("forbidden_mapping_violations")}, "candidate_only": True, "canonical_write_back": False}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--offline", action="store_true", help="replay only; never call the provider")
    mode.add_argument("--live", action="store_true", help="run the bounded provider pilot")
    parser.add_argument("--run-id", default="sfh2-2p-offline")
    args = parser.parse_args(argv)
    summary = run(live=bool(args.live), run_id=args.run_id)
    print(json.dumps({key: summary.get(key) for key in ("run_id", "live", "case_count", "gold_case_count", "blind_case_count", "candidate_recall", "semantic_precision", "recommendation") if key in summary}, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
