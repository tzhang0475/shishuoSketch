#!/usr/bin/env python3
"""Validate the isolated SFH2.2-P1 pilot contract and safety gates."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from sfh2_2p1.common import OUT, SELECTION_PATH, file_hash, input_hashes, load_inputs, stable_hash, text
from sfh2_2p1.selection import build_selection


def _rows(value: Any, *keys: str) -> list[dict[str, Any]]:
    if isinstance(value, list):
        return [dict(row) for row in value if isinstance(row, Mapping)]
    if isinstance(value, Mapping):
        for key in keys:
            if isinstance(value.get(key), list):
                return [dict(row) for row in value[key] if isinstance(row, Mapping)]
    return []


def _walk(value: Any):
    if isinstance(value, Mapping):
        for key, item in value.items():
            yield str(key), item
            yield from _walk(item)
    elif isinstance(value, list):
        for item in value:
            yield from _walk(item)


def validate() -> dict[str, Any]:
    errors: list[str] = []
    selection = json.loads(SELECTION_PATH.read_text(encoding="utf-8")) if SELECTION_PATH.is_file() else {}
    expected_selection = build_selection(load_inputs())
    if selection != expected_selection:
        errors.append("selection_not_frozen_or_reproducible")
    if selection.get("case_count") != 10 or selection.get("gold_case_count") != 10 or selection.get("blind_case_count") != 0:
        errors.append("selection_size_contract")
    if selection.get("selection_hash") != stable_hash({key: value for key, value in selection.items() if key != "selection_hash"}):
        errors.append("selection_hash_invalid")
    cases = _rows(selection, "cases")
    case_ids = {text(row.get("case_id")) for row in cases}
    if len(case_ids) != 10:
        errors.append("selection_case_ids_not_unique")

    manifest = json.loads((OUT / "input-manifest.json").read_text(encoding="utf-8")) if (OUT / "input-manifest.json").is_file() else {}
    if manifest.get("selection_hash") != selection.get("selection_hash"):
        errors.append("input_manifest_selection_drift")
    if manifest.get("input_hashes") != input_hashes(load_inputs()):
        errors.append("pilot_input_hash_drift")
    if manifest.get("model") != "deepseek-v4-flash":
        errors.append("model_drift")
    if manifest.get("gold_not_sent_to_provider") is not True:
        errors.append("gold_visibility_contract")

    packets_doc = json.loads((OUT / "case-packets.json").read_text(encoding="utf-8")) if (OUT / "case-packets.json").is_file() else {}
    packets = _rows(packets_doc, "packets")
    if len(packets) != 10:
        errors.append("case_packet_count")
    forbidden_gold_keys = {"expected_identity", "expected_person_id", "must_not_resolve_to", "must_not_resolve_to_names", "expected_proposal_kind", "expected_identity_type", "expected_bearer", "expected_attribute_type", "expected_network_role", "evaluation_mode"}
    for key, _ in _walk(packets):
        if key in forbidden_gold_keys:
            errors.append(f"gold_leaked_to_provider_packet:{key}")
            break
    if any(row.get("gold_not_sent_to_provider") is not True for row in packets):
        # The flag belongs to the document, not each packet; do not fail when
        # it is absent from individual packet rows.
        pass

    proposal_doc = json.loads((OUT / "entity-proposals.json").read_text(encoding="utf-8")) if (OUT / "entity-proposals.json").is_file() else {}
    proposals = _rows(proposal_doc, "records")
    if len(proposals) != 10:
        errors.append("proposal_count")
    proposal_by_case = {text(row.get("case_id")): row for row in proposals}

    inputs = load_inputs()
    production_ids = {text(row.get("person_id")) for row in (inputs.get("people") or {}).get("people", []) or [] if isinstance(row, Mapping)}
    candidate_doc = json.loads((OUT / "candidate-sets.json").read_text(encoding="utf-8")) if (OUT / "candidate-sets.json").is_file() else {}
    candidate_sets = _rows(candidate_doc, "records")
    if len(candidate_sets) != 10:
        errors.append("candidate_set_count")
    candidate_by_case = {text(row.get("case_id")): row for row in candidate_sets}
    for row in candidate_sets:
        for candidate in row.get("candidates", []) or []:
            if not isinstance(candidate, Mapping):
                errors.append("candidate_not_object")
                continue
            person_id = text(candidate.get("person_id"))
            if person_id and person_id not in production_ids:
                errors.append(f"unknown_production_person:{person_id}")
            candidate_person_id = text(candidate.get("candidate_person_id"))
            if candidate_person_id.startswith("person-"):
                errors.append(f"candidate_uses_production_id:{candidate_person_id}")
            basis = " ".join(text(value) for value in candidate.get("retrieval_basis", []) or [])
            if any(value in basis.lower() for value in ("substring", "co_occurrence", "local_context_scan", "nearest")):
                errors.append("unsafe_retrieval_basis")

    registry_doc = json.loads((OUT / "candidate-registry.json").read_text(encoding="utf-8")) if (OUT / "candidate-registry.json").is_file() else {}
    registry = _rows(registry_doc, "records")
    registry_ids = {text(row.get("candidate_person_id")) for row in registry}
    if any(value.startswith("person-") for value in registry_ids):
        errors.append("production_id_in_candidate_registry")
    if any(row.get("candidate_only") is not True or row.get("canonical_write_back") is not False for row in registry):
        errors.append("candidate_registry_storage_contract")

    equivalence_doc = json.loads((OUT / "equivalence-judgments.json").read_text(encoding="utf-8")) if (OUT / "equivalence-judgments.json").is_file() else {}
    equivalences = _rows(equivalence_doc, "records")
    equivalence_by_case = {text(row.get("case_id")): row for row in equivalences}
    for row in equivalences:
        assessments = row.get("candidate_assessments", []) or []
        same = [item for item in assessments if isinstance(item, Mapping) and text(item.get("relation_to_target")) == "same_person"]
        declared_same = text(row.get("same_person_candidate_key"))
        if declared_same:
            same_keys = {text(item.get("candidate_key")) for item in same}
            if declared_same not in same_keys:
                errors.append(f"declared_same_person_not_supported:{row.get('case_id')}")
            if any(text(item.get("relation_to_target")) != "same_person" and text(item.get("candidate_key")) == declared_same for item in assessments if isinstance(item, Mapping)):
                errors.append(f"same_person_relation_mismatch:{row.get('case_id')}")

    final_doc = json.loads((OUT / "final-decisions.json").read_text(encoding="utf-8")) if (OUT / "final-decisions.json").is_file() else {}
    finals = _rows(final_doc, "records")
    if len(finals) != 10:
        errors.append("final_count")
    final_by_case = {text(row.get("case_id")): row for row in finals}
    for case in cases:
        case_id = text(case.get("case_id"))
        final = final_by_case.get(case_id, {})
        if final.get("candidate_only") is not True or final.get("canonical_write_back") is not False:
            errors.append(f"final_storage_contract:{case_id}")
        if final.get("final_state") in {"stable_entity_resolved", "local_candidate_resolved"}:
            relation = text(final.get("selected_relation_to_target"))
            if relation != "same_person":
                errors.append(f"non_identity_relation_promoted:{case_id}")
            selected = final.get("selected_candidate") if isinstance(final.get("selected_candidate"), Mapping) else {}
            if text(selected.get("person_id")) in {text(value) for value in case.get("must_not_resolve_to", []) or []}:
                errors.append(f"forbidden_mapping:{case_id}")
            if text(selected.get("display_name")) in {text(value) for value in case.get("must_not_resolve_to_names", []) or []}:
                errors.append(f"forbidden_mapping_name:{case_id}")
        if text(case.get("expected_proposal_kind")) == "person_attribute" and final.get("final_state") in {"stable_entity_resolved", "local_candidate_resolved"}:
            errors.append(f"attribute_promoted_as_person:{case_id}")

    safety = json.loads((OUT / "identity-safety-audit.json").read_text(encoding="utf-8")) if (OUT / "identity-safety-audit.json").is_file() else {}
    for key in ("related_person_promotions", "attribute_promotions", "forbidden_mapping_violations", "global_alias_writes", "profile_mutations", "substring_candidate_generation", "profile_contamination", "hda2_suppressed_claim_reentry"):
        if safety.get(key) != 0:
            errors.append(f"safety_{key}")
    storage = json.loads((OUT / "storage-safety-audit.json").read_text(encoding="utf-8")) if (OUT / "storage-safety-audit.json").is_file() else {}
    if storage.get("unchanged") is not True or storage.get("production_person_creation") != 0 or storage.get("canonical_fact_writes") != 0:
        errors.append("storage_safety")

    transport = json.loads((OUT / "transport.json").read_text(encoding="utf-8")) if (OUT / "transport.json").is_file() else {}
    if transport.get("model") != "deepseek-v4-flash":
        errors.append("transport_model_drift")
    if int(transport.get("new_live_calls") or 0) > 30:
        errors.append("total_live_call_budget_exceeded")
    by_stage = transport.get("by_stage") if isinstance(transport.get("by_stage"), Mapping) else {}
    if int((by_stage.get("entity_proposal") or {}).get("calls") or 0) > 12:
        errors.append("proposal_call_budget_exceeded")
    if int((by_stage.get("identity_equivalence") or {}).get("calls") or 0) > 12:
        errors.append("equivalence_call_budget_exceeded")

    metrics = json.loads((OUT / "metrics.json").read_text(encoding="utf-8")) if (OUT / "metrics.json").is_file() else {}
    if metrics.get("candidate_only") is not True or metrics.get("canonical_write_back") is not False:
        errors.append("metrics_storage_contract")
    if metrics.get("no_full_188_story_live_run") is not True:
        errors.append("full_corpus_live_run_flag")
    return {
        "schema": "sfh2-2p1-validation-v1",
        "valid": not errors,
        "errors": sorted(set(errors)),
        "selection_hash": selection.get("selection_hash"),
        "case_count": len(cases),
        "proposal_accuracy": metrics.get("proposal_accuracy"),
        "proposal_realization_rate": metrics.get("proposal_realization_rate"),
        "related_person_promotions": safety.get("related_person_promotions", 0),
        "attribute_promotions": safety.get("attribute_promotions", 0),
        "forbidden_mapping_violations": safety.get("forbidden_mapping_violations", 0),
        "candidate_registry_count": len(registry),
        "candidate_only": True,
        "canonical_write_back": False,
    }


def main() -> int:
    result = validate()
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if result["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
