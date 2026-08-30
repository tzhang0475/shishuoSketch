"""Validate the frozen SFH2.2-P2 blind pilot contract."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Iterable, Mapping

from sfh2_2p2.common import MODEL, OUT, PILOT_VERSION, PROMPT_VERSIONS, ROOT, SELECTION_PATH, architecture_freeze, input_hashes, load_inputs, read_json, stable_hash, text
from sfh2_2p2.selection import build_selection

FORBIDDEN_GOLD_KEYS = {
    "expected_identity", "expected_person_id", "expected_proposal_kind", "expected_identity_type",
    "expected_bearer", "expected_attribute_type", "expected_network_role", "must_not_resolve_to",
    "must_not_resolve_to_names", "evaluation_mode",
}
EXCLUDED_ROLES = {"citation_author", "historical_exemplum", "person_attribute", "collective_reference", "structural_reference", "genealogy_ancestor"}


def _walk(value: Any) -> Iterable[tuple[str, Any]]:
    if isinstance(value, Mapping):
        for key, child in value.items():
            yield text(key), child
            yield from _walk(child)
    elif isinstance(value, list):
        for child in value:
            yield from _walk(child)


def _rows(document: Any, key: str = "records") -> list[dict[str, Any]]:
    value = document.get(key) if isinstance(document, Mapping) else None
    return [dict(row) for row in value or [] if isinstance(row, Mapping)]


def _gold_leaks(value: Any) -> list[str]:
    return sorted({key for key, _ in _walk(value) if key in FORBIDDEN_GOLD_KEYS})


def _selection_errors(selection: Mapping[str, Any]) -> list[str]:
    errors: list[str] = []
    if selection.get("case_count") != 24 or selection.get("blind_case_count") != 24 or selection.get("gold_case_count") != 0:
        errors.append("selection_not_24_blind_cases")
    if selection.get("gold_fields_present") is not False:
        errors.append("selection_gold_fields_flag")
    cases = selection.get("cases") if isinstance(selection.get("cases"), list) else []
    if len({text(row.get("case_id")) for row in cases if isinstance(row, Mapping)}) != len(cases):
        errors.append("selection_case_ids_not_unique")
    if len({text(row.get("mention_id")) for row in cases if isinstance(row, Mapping)}) != len(cases):
        errors.append("selection_mention_ids_not_unique")
    if _gold_leaks(cases):
        errors.append("gold_fields_in_selection_cases")
    if any(not isinstance(row, Mapping) or text(row.get("selection_seed")) != text(selection.get("selection_seed")) for row in cases):
        errors.append("selection_seed_mismatch")
    return errors


def _raw_registration_errors() -> list[str]:
    errors: list[str] = []
    live_root = OUT / "live"
    if not live_root.is_dir():
        return errors
    for path in sorted(live_root.glob("*/transport.json")):
        document = read_json(path, None)
        if not isinstance(document, list):
            continue
        seen: set[str] = set()
        for row in document:
            if not isinstance(row, Mapping):
                errors.append(f"raw_transport_row_invalid:{path.parent.name}")
                continue
            raw_path = text(row.get("raw_path"))
            if raw_path:
                if raw_path in seen:
                    errors.append(f"raw_path_reused:{raw_path}")
                seen.add(raw_path)
                if not (ROOT / raw_path).is_file():
                    errors.append(f"raw_path_missing:{raw_path}")
    return errors


def validate(*, preflight: bool = False) -> dict[str, Any]:
    errors: list[str] = []
    selection = read_json(SELECTION_PATH, {}) or {}
    errors.extend(_selection_errors(selection))
    try:
        computed_selection = build_selection(load_inputs())
        if computed_selection != selection:
            errors.append("selection_rebuild_drift")
    except Exception as exc:
        errors.append(f"selection_rebuild_error:{type(exc).__name__}")
        computed_selection = {}
    selection_hash = text(selection.get("selection_hash"))
    generated_selection = read_json(OUT / "selection.json", {}) or {}
    if generated_selection != selection:
        errors.append("generated_selection_drift")
    if _gold_leaks(generated_selection):
        errors.append("gold_fields_in_generated_selection")
    hash_doc = read_json(OUT / "selection-hash.json", {}) or {}
    if hash_doc.get("selection_hash") != selection_hash:
        errors.append("selection_hash_artifact_mismatch")
    architecture = read_json(OUT / "architecture-freeze.json", {}) or {}
    expected_architecture = architecture_freeze(selection_hash)
    if architecture != expected_architecture:
        errors.append("architecture_freeze_drift")
    if preflight:
        return {
            "schema": "sfh2-2p2-validation-v1",
            "preflight": True,
            "valid": not errors,
            "errors": sorted(set(errors)),
            "selection_hash": selection_hash,
            "case_count": selection.get("case_count", 0),
        }

    manifest = read_json(OUT / "input-manifest.json", {}) or {}
    if manifest.get("selection_hash") != selection_hash:
        errors.append("manifest_selection_drift")
    if manifest.get("input_hashes") != input_hashes():
        errors.append("input_hash_drift")
    if manifest.get("model") != MODEL or manifest.get("prompt_versions") != PROMPT_VERSIONS:
        errors.append("model_or_prompt_drift")
    if manifest.get("gold_not_sent_to_provider") is not True or manifest.get("selection_blind") is not True:
        errors.append("provider_blindness_contract")

    cases = _rows(selection, "cases")
    prior_stories = {text(value) for value in selection.get("prior_story_ids", []) or [] if text(value)}
    if any(text(row.get("story_id")) in prior_stories for row in cases):
        errors.append("prior_story_overlap")
    if _gold_leaks(read_json(OUT / "case-packets.json", {}) or {}):
        errors.append("gold_fields_in_provider_packets")
    eligibility = read_json(OUT / "eligibility-audit.json", {}) or {}
    if eligibility.get("answers_inspected") is not False:
        errors.append("eligibility_answers_inspected")
    if eligibility.get("selection_seed") != selection.get("selection_seed"):
        errors.append("eligibility_seed_drift")
    if eligibility.get("selected_case_ids") != [text(row.get("case_id")) for row in cases]:
        errors.append("eligibility_case_ids_drift")
    review_doc = read_json(OUT / "human-review.json", {}) or {}
    if _gold_leaks(review_doc):
        errors.append("gold_fields_in_human_review")
    if review_doc.get("historical_correctness") != "pending_external_review":
        errors.append("human_review_status_not_pending")
    if len(_rows(read_json(OUT / "case-packets.json", {}) or {}, "packets")) != 24:
        errors.append("case_packet_count")

    proposal_doc = read_json(OUT / "entity-proposals.json", {}) or {}
    candidate_doc = read_json(OUT / "candidate-sets.json", {}) or {}
    equivalence_doc = read_json(OUT / "equivalence-judgments.json", {}) or {}
    final_doc = read_json(OUT / "final-decisions.json", {}) or {}
    proposals = _rows(proposal_doc)
    candidate_sets = _rows(candidate_doc)
    equivalences = _rows(equivalence_doc)
    finals = _rows(final_doc)
    if len(proposals) != 24:
        errors.append("proposal_count")
    if len(candidate_sets) != 24:
        errors.append("candidate_set_count")
    if len(finals) != 24:
        errors.append("final_count")
    if len({text(row.get("case_id")) for row in proposals}) != len(proposals):
        errors.append("proposal_case_ids_not_unique")
    if len({text(row.get("case_id")) for row in finals}) != len(finals):
        errors.append("final_case_ids_not_unique")

    production_ids = {text(row.get("person_id")) for row in (load_inputs().get("people") or {}).get("people", []) or [] if isinstance(row, Mapping)}
    registry_doc = read_json(OUT / "candidate-registry.json", {}) or {}
    registry = _rows(registry_doc)
    if any(text(row.get("candidate_person_id")).startswith("person-") for row in registry):
        errors.append("production_person_in_candidate_registry")
    if any(row.get("candidate_only") is not True or row.get("canonical_write_back") is not False for row in registry):
        errors.append("candidate_registry_storage_contract")
    for row in candidate_sets:
        for candidate in row.get("candidates", []) or []:
            if not isinstance(candidate, Mapping):
                errors.append("candidate_not_object")
                continue
            person_id = text(candidate.get("person_id"))
            if person_id and person_id not in production_ids:
                errors.append(f"unknown_production_person:{person_id}")
            basis = " ".join(text(item) for item in candidate.get("retrieval_basis", []) or []).lower()
            if any(token in basis for token in ("substring", "co_occurrence", "local_context_scan", "nearest")):
                errors.append("unsafe_retrieval_basis")

    for row in equivalences:
        for assessment in row.get("candidate_assessments", []) or []:
            if not isinstance(assessment, Mapping):
                continue
            relation = text(assessment.get("relation_to_target"))
            if relation in {"related_person", "office_relation", "kinship_relation", "citation_relation", "attribute_of"} and text(row.get("same_person_candidate_key")) == text(assessment.get("candidate_key")):
                errors.append("non_identity_relation_promoted")
    for row in finals:
        if row.get("candidate_only") is not True or row.get("canonical_write_back") is not False:
            errors.append(f"final_storage_contract:{row.get('case_id')}")
        if row.get("final_state") in {"stable_entity_resolved", "local_candidate_resolved"} and text(row.get("selected_relation_to_target")) != "same_person":
            errors.append(f"final_non_identity_promotion:{row.get('case_id')}")
        proposal = next((item for item in proposals if text(item.get("case_id")) == text(row.get("case_id"))), {})
        proposal_data = proposal.get("candidate_proposal") if isinstance(proposal.get("candidate_proposal"), Mapping) else {}
        if text(proposal_data.get("proposal_kind")) == "person_attribute" and row.get("final_state") in {"stable_entity_resolved", "local_candidate_resolved"}:
            errors.append(f"attribute_as_person:{row.get('case_id')}")
        if text(row.get("network_role")) in EXCLUDED_ROLES and row.get("core_graph_eligible") is True:
            errors.append(f"excluded_role_graph_eligible:{row.get('case_id')}")

    safety = read_json(OUT / "automatic-safety-audit.json", {}) or {}
    for key in ("production_person_creation", "canonical_fact_writes", "global_alias_writes", "profile_mutations", "occurrence_derived_alias_creation", "substring_candidate_creation", "related_person_promotions", "attribute_person_promotions", "internal_consistency_error_count"):
        if safety.get(key) != 0:
            errors.append(f"safety_{key}")
    if safety.get("protected_storage_unchanged") is not True:
        errors.append("protected_storage_changed")
    internal = read_json(OUT / "internal-consistency-audit.json", {}) or {}
    if internal.get("errors") or internal.get("error_count") != 0:
        errors.append("internal_consistency_errors")
    metrics = read_json(OUT / "metrics-pre-review.json", {}) or {}
    if metrics.get("candidate_only") is not True or metrics.get("canonical_write_back") is not False:
        errors.append("metrics_storage_contract")
    if metrics.get("historical_accuracy") != "pending_external_review":
        errors.append("historical_accuracy_scored_prematurely")
    if metrics.get("no_full_188_story_live_run") is not True:
        errors.append("full_corpus_live_run_flag")
    transport = read_json(OUT / "transport.json", {}) or {}
    if transport.get("model") != MODEL or int(transport.get("new_live_calls") or 0) > 60:
        errors.append("provider_budget_or_model")
    by_stage = transport.get("by_stage") if isinstance(transport.get("by_stage"), Mapping) else {}
    for stage in PROMPT_VERSIONS:
        if int((by_stage.get(stage) or {}).get("calls") or 0) > 26:
            errors.append(f"stage_provider_budget:{stage}")
    errors.extend(_raw_registration_errors())
    return {
        "schema": "sfh2-2p2-validation-v1",
        "preflight": False,
        "valid": not errors,
        "errors": sorted(set(errors)),
        "selection_hash": selection_hash,
        "case_count": len(cases),
        "provider_calls": transport.get("new_live_calls", transport.get("calls", 0)),
        "candidate_only": True,
        "canonical_write_back": False,
        "historical_accuracy": "pending_external_review",
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
