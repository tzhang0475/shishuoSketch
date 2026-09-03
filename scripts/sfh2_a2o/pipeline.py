"""SFH2.2-A2O occurrence-semantics decomposition pilot.

The frozen A2R identity record is input to this pilot.  The only semantic
provider decision made here is ``narrative_function``.  Provenance is copied
from source metadata and the legacy role is a generic projection of those two
structured axes.
"""

from __future__ import annotations

import copy
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Mapping

from .common import (
    A2G_ROLE_AUDIT_PATH,
    A2R_FINAL_PATH,
    BASELINE_COMMIT,
    GOLD_PATH,
    MODEL,
    OUT,
    PROMPT_VERSION,
    ROOT,
    SCHEMA_VERSION,
    STRICT_ENDPOINT,
    TEMPERATURE,
    THINKING,
    all_cases,
    build_case_packet,
    canonical_json,
    file_hash,
    input_hashes,
    load_inputs,
    provider_payload,
    read_json,
    selection_document,
    stable_hash,
    text,
    write_json,
)
from .contracts import occurrence_function_tool, validate_occurrence_payload
from .provenance import derive_provenance_layer, project_legacy_occurrence_role
from .transport import A2OClient, summarize


HISTORIAN_SYSTEM = """You are the Occurrence Semantic Historian for the SFH2.2-A2O pilot. The supplied provenance_layer is structural source metadata and must be preserved; do not infer it from wording. The supplied frozen identity and semantic kind are not under review and must not be changed. Determine only the target occurrence's narrative_function from the exact evidence. Choose one of: participant, reference, speaker, addressee, collective_reference, person_attribute, citation_source, historical_exemplum, genealogy_reference, structural, other, uncertain. Return only the required compact structured result, cite supplied evidence IDs, and do not emit identity, canonical, occurrence_role, candidate, or production-ID fields."""


def _rows(document: Any, key: str = "records") -> list[dict[str, Any]]:
    if isinstance(document, Mapping) and isinstance(document.get(key), list):
        return [dict(row) for row in document[key] if isinstance(row, Mapping)]
    if isinstance(document, list):
        return [dict(row) for row in document if isinstance(row, Mapping)]
    return []


def _identity_fields(record: Mapping[str, Any] | None) -> dict[str, Any]:
    if not isinstance(record, Mapping):
        return {}
    return {
        "semantic_kind": record.get("semantic_kind"),
        "reference_type": record.get("reference_type"),
        "referent": copy.deepcopy(record.get("referent", {})),
        "attribute_type": record.get("attribute_type", ""),
        "attribute_value": record.get("attribute_value", ""),
        "bearer_hint": record.get("bearer_hint", ""),
        "abstain": record.get("abstain", False),
    }


def architecture_freeze(cases: list[Mapping[str, Any]]) -> dict[str, Any]:
    code_paths = [
        ROOT / "scripts/sfh2_a2o/common.py",
        ROOT / "scripts/sfh2_a2o/contracts.py",
        ROOT / "scripts/sfh2_a2o/provenance.py",
        ROOT / "scripts/sfh2_a2o/transport.py",
        ROOT / "scripts/sfh2_a2o/pipeline.py",
    ]
    code_files = {str(path.relative_to(ROOT)): file_hash(path) for path in code_paths if path.is_file()}
    selection = selection_document(cases, load_inputs(), {text(row.get("case_id")): {} for row in cases})
    result: dict[str, Any] = {
        "schema": "sfh2-a2o-architecture-freeze-v1",
        "pilot": "SFH2.2-A2O",
        "baseline_commit": BASELINE_COMMIT,
        "selection_hash": selection["selection_hash"],
        "case_count": len(cases),
        "reviewed_role_case_count": selection["reviewed_role_case_count"],
        "challenge_case_count": selection["challenge_case_count"],
        "model_config": {
            "model": MODEL,
            "temperature": TEMPERATURE,
            "thinking": dict(THINKING),
            "endpoint": STRICT_ENDPOINT,
            "prompt_version": PROMPT_VERSION,
            "function_name": "submit_sfh2_a2o_occurrence_function_v1",
            "max_provider_attempts": 40,
            "retry_policy": "transient_only_at_most_one_retry; HTTP400_not_retryable",
        },
        "prompt_hash": stable_hash(HISTORIAN_SYSTEM),
        "schema_hash": stable_hash(occurrence_function_tool()),
        "code_files": code_files,
        "input_hashes": input_hashes(),
        "authority_boundary": "frozen identity input; structural provenance; LLM narrative_function; Python compatibility projection and storage safety",
        "provenance_is_structural": True,
        "identity_is_frozen": True,
        "identity_not_in_a2o_output": True,
        "gold_not_in_provider_packets": True,
        "candidate_only": True,
        "canonical_write_back": False,
        "no_full_188_story_live_run": True,
    }
    result["architecture_hash"] = stable_hash({key: value for key, value in result.items() if key != "architecture_hash"})
    return result


def _stable_transport(row: Mapping[str, Any]) -> dict[str, Any]:
    keys = ("stage", "case_id", "request_hash", "model", "temperature", "thinking", "prompt_version", "attempt", "classification", "valid", "parse_error", "usage", "finish_reason", "raw_witness_sha256", "http_status", "provider_error_code", "provider_error_message", "provider_request_id", "retryable")
    return {key: copy.deepcopy(row[key]) for key in keys if key in row}


def _invalid_result(case: Mapping[str, Any], packet: Mapping[str, Any], errors: list[str], transport: Mapping[str, Any] | None = None) -> dict[str, Any]:
    provenance, provenance_errors = derive_provenance_layer(packet)
    return {
        "case_id": text(case.get("case_id")),
        "cohort": case.get("cohort"),
        "story_id": case.get("story_id"),
        "mention_id": case.get("mention_id"),
        "surface": case.get("surface"),
        "provenance_layer": provenance,
        "provenance_errors": provenance_errors,
        "valid": False,
        "contract_status": "provider_or_contract_invalid",
        "errors": sorted(set(errors)),
        "occurrence_result": None,
        "frozen_identity": copy.deepcopy(packet.get("frozen_identity_context")),
        "identity_preserved": True,
        "transport": _stable_transport(transport or {}),
        "candidate_only": True,
        "canonical_write_back": False,
    }


def _result_row(case: Mapping[str, Any], packet: Mapping[str, Any], payload: Mapping[str, Any] | None, transport: Mapping[str, Any] | None) -> dict[str, Any]:
    validation = validate_occurrence_payload(packet, payload)
    provenance, provenance_errors = derive_provenance_layer(packet)
    if not validation["valid"]:
        return _invalid_result(case, packet, validation["errors"], transport)
    result = validation["result"]
    # Identity fields are intentionally absent from the provider result.  The
    # wrapper records the frozen input hash/state solely to prove preservation.
    output_keys = set(result or {})
    identity_leaks = sorted(output_keys & {"semantic_kind", "reference_type", "referent", "occurrence_role", "relations", "identity", "canonical_hint"})
    errors = ["identity_field_in_occurrence_output"] if identity_leaks else []
    return {
        "case_id": text(case.get("case_id")),
        "cohort": case.get("cohort"),
        "story_id": case.get("story_id"),
        "mention_id": case.get("mention_id"),
        "surface": case.get("surface"),
        "provenance_layer": provenance,
        "provenance_errors": provenance_errors,
        "valid": not errors,
        "contract_status": "valid" if not errors else "contract_invalid_identity_field",
        "errors": errors,
        "occurrence_result": copy.deepcopy(result) if not errors else None,
        "frozen_identity": copy.deepcopy(packet.get("frozen_identity_context")),
        "identity_preserved": not errors,
        "transport": _stable_transport(transport or {}),
        "candidate_only": True,
        "canonical_write_back": False,
    }


def _case_packets(cases: list[Mapping[str, Any]], inputs: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    return {text(case.get("case_id")): build_case_packet(case, inputs) for case in cases}


def _load_offline_rows(source_path: Path, cases: list[Mapping[str, Any]]) -> dict[str, dict[str, Any]]:
    document = read_json(source_path, {}) or {}
    source = {text(row.get("case_id")): dict(row) for row in _rows(document) if text(row.get("case_id"))}
    expected = {text(case.get("case_id")) for case in cases}
    if set(source) != expected:
        raise RuntimeError("sfh2_a2o_offline_source_case_set_mismatch")
    return source


def _a2r_baseline() -> dict[str, Any]:
    audit = _rows(read_json(A2G_ROLE_AUDIT_PATH, {}))
    evaluable = [row for row in audit if text(row.get("gold_role"))]
    correct = sum((row.get("stage_roles") or {}).get("final_a2r") == row.get("gold_role") for row in evaluable)
    return {
        "case_count": len(evaluable),
        "correct": correct,
        "accuracy": round(correct / len(evaluable), 4) if evaluable else None,
        "source": str(A2G_ROLE_AUDIT_PATH.relative_to(ROOT)),
    }


def evaluate(cases: list[Mapping[str, Any]], rows: Mapping[str, Mapping[str, Any]], gold_document: Mapping[str, Any]) -> dict[str, Any]:
    gold_map = {text(row.get("case_id")): row for row in _rows(gold_document) if text(row.get("case_id"))}
    evaluated: list[dict[str, Any]] = []
    for case in cases:
        case_id = text(case.get("case_id"))
        row = rows[case_id]
        gold = gold_map.get(case_id, {})
        output = row.get("occurrence_result") if isinstance(row.get("occurrence_result"), Mapping) else {}
        provenance_ok = row.get("provenance_layer") == gold.get("expected_provenance_layer") if gold.get("expected_provenance_layer") else None
        function_ok = output.get("narrative_function") == gold.get("expected_narrative_function") if gold.get("expected_narrative_function") else None
        projected = project_legacy_occurrence_role(text(row.get("provenance_layer")), text(output.get("narrative_function"))) if row.get("valid") else None
        legacy_ok = projected == gold.get("expected_legacy_occurrence_role") if gold.get("expected_legacy_occurrence_role") else None
        reviewed = text(gold.get("review_status")) == "reviewed"
        evaluated.append({
            "case_id": case_id,
            "cohort": case.get("cohort"),
            "story_id": case.get("story_id"),
            "surface": case.get("surface"),
            "source_evidence_id": case.get("source_evidence_id"),
            "gold_review_status": gold.get("review_status"),
            "reviewed_for_primary_metrics": reviewed,
            "provenance_layer": row.get("provenance_layer"),
            "narrative_function": output.get("narrative_function"),
            "projected_legacy_occurrence_role": projected,
            "expected_provenance_layer": gold.get("expected_provenance_layer"),
            "expected_narrative_function": gold.get("expected_narrative_function"),
            "expected_legacy_occurrence_role": gold.get("expected_legacy_occurrence_role"),
            "provenance_correct": provenance_ok,
            "narrative_function_correct": function_ok,
            "legacy_occurrence_role_correct": legacy_ok,
            "identity_preserved": row.get("identity_preserved") is True,
            "valid": row.get("valid") is True,
            "errors": copy.deepcopy(row.get("errors", [])),
        })

    reviewed_rows = [row for row in evaluated if row["reviewed_for_primary_metrics"]]

    def accuracy(field: str, source: list[Mapping[str, Any]] = reviewed_rows) -> dict[str, Any]:
        values = [row.get(field) for row in source if row.get(field) is not None]
        return {"correct": sum(value is True for value in values), "evaluable": len(values), "accuracy": round(sum(value is True for value in values) / len(values), 4) if values else None}

    by_layer: dict[str, dict[str, Any]] = {}
    for layer in sorted({text(row.get("expected_provenance_layer")) for row in reviewed_rows}):
        subset = [row for row in reviewed_rows if row.get("expected_provenance_layer") == layer]
        by_layer[layer] = {
            "case_count": len(subset),
            "provenance": accuracy("provenance_correct", subset),
            "narrative_function": accuracy("narrative_function_correct", subset),
            "legacy_role": accuracy("legacy_occurrence_role_correct", subset),
        }
    by_function: dict[str, dict[str, Any]] = {}
    for function in sorted({text(row.get("expected_narrative_function")) for row in reviewed_rows}):
        subset = [row for row in reviewed_rows if row.get("expected_narrative_function") == function]
        by_function[function] = {
            "case_count": len(subset),
            "correct": sum(row.get("narrative_function_correct") is True for row in subset),
            "accuracy": round(sum(row.get("narrative_function_correct") is True for row in subset) / len(subset), 4) if subset else None,
        }
    return {
        "schema": "sfh2-a2o-evaluation-v1",
        "case_count": len(evaluated),
        "reviewed_gold_count": len(reviewed_rows),
        "review_required_count": len(evaluated) - len(reviewed_rows),
        "records": evaluated,
        "metrics": {
            "provenance_accuracy": accuracy("provenance_correct"),
            "narrative_function_accuracy": accuracy("narrative_function_correct"),
            "legacy_occurrence_role_accuracy": accuracy("legacy_occurrence_role_correct"),
            "identity_preservation": {"correct": sum(row["identity_preserved"] for row in reviewed_rows), "evaluable": len(reviewed_rows), "accuracy": round(sum(row["identity_preserved"] for row in reviewed_rows) / len(reviewed_rows), 4) if reviewed_rows else None},
            "valid_occurrence_records": sum(row["valid"] for row in evaluated),
            "reviewed_valid_occurrence_records": sum(row["valid"] for row in reviewed_rows),
        },
        "by_provenance_layer": by_layer,
        "by_narrative_function": by_function,
        "a2r_six_case_baseline": _a2r_baseline(),
        "candidate_only": True,
        "canonical_write_back": False,
    }


def confusion_matrix(evaluation: Mapping[str, Any]) -> dict[str, Any]:
    rows = [row for row in evaluation.get("records", []) if row.get("reviewed_for_primary_metrics")]
    matrix: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for row in rows:
        matrix[text(row.get("expected_provenance_layer"))][text(row.get("provenance_layer"))] += 1
    function_matrix: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for row in rows:
        function_matrix[text(row.get("expected_narrative_function"))][text(row.get("narrative_function"))] += 1
    role_rows = [row for row in rows if row.get("expected_legacy_occurrence_role")]
    # The "before" side must come from the immutable A2R role audit, not from
    # the A2O projection being evaluated.  This keeps the comparison honest:
    # A2O is allowed to improve the representation, but it cannot rewrite its
    # own baseline.  The lookup is keyed by frozen case_id and contains no
    # surface or identity interpretation.
    a2r_audit_rows = _rows(read_json(A2G_ROLE_AUDIT_PATH, {}))
    a2r_annotation_collapse = sum(
        text(row.get("gold_role")) == "annotation_person"
        and text((row.get("stage_roles") or {}).get("final_a2r")) == "scene_participant"
        for row in a2r_audit_rows
    )
    return {
        "schema": "sfh2-a2o-confusion-matrix-v1",
        "provenance_expected_to_predicted": {key: dict(value) for key, value in sorted(matrix.items())},
        "narrative_function_expected_to_predicted": {key: dict(value) for key, value in sorted(function_matrix.items())},
        "annotation_participant_collapsed_to_scene_participant": {
            "before_a2r_six_case_count": a2r_annotation_collapse,
            "after_a2o_count": sum(
                row.get("expected_legacy_occurrence_role") == "annotation_person"
                and row.get("projected_legacy_occurrence_role") == "scene_participant"
                for row in role_rows
            ),
        },
        "candidate_only": True,
        "canonical_write_back": False,
    }


def error_analysis(evaluation: Mapping[str, Any]) -> dict[str, Any]:
    errors = [row for row in evaluation.get("records", []) if row.get("reviewed_for_primary_metrics") and (row.get("narrative_function_correct") is False or row.get("legacy_occurrence_role_correct") is False)]
    return {
        "schema": "sfh2-a2o-error-analysis-v1",
        "reviewed_mismatch_count": len(errors),
        "records": errors,
        "interpretation": "A2O errors are narrative-function model errors or contract failures; provenance remains a structural source-metadata projection.",
        "candidate_only": True,
        "canonical_write_back": False,
    }


def storage_safety(cases: list[Mapping[str, Any]], rows: Mapping[str, Mapping[str, Any]], before_hashes: Mapping[str, str]) -> dict[str, Any]:
    identity_leaks = sum("identity_field_in_occurrence_output" in (row.get("errors") or []) for row in rows.values())
    return {
        "schema": "sfh2-a2o-storage-safety-v1",
        "production_person_creations": 0,
        "canonical_writes": 0,
        "alias_mutations": 0,
        "profile_mutations": 0,
        "identity_replacements": 0,
        "retrieval_candidate_identity_gating": 0,
        "substring_identity_creation": 0,
        "name_specific_python_semantic_rules": 0,
        "surface_specific_role_rules": 0,
        "identity_field_output_leaks": identity_leaks,
        "candidate_only": True,
        "canonical_write_back": False,
        "protected_input_hashes": dict(before_hashes),
        "protected_inputs_present": all((ROOT / path).is_file() for path in before_hashes),
    }


def recommendation(evaluation: Mapping[str, Any], transport: Mapping[str, Any], safety: Mapping[str, Any], confusion: Mapping[str, Any]) -> tuple[str, dict[str, Any]]:
    metrics = evaluation.get("metrics", {})
    six = evaluation.get("a2r_six_case_baseline", {})
    six_rows = [row for row in evaluation.get("records", []) if row.get("cohort") == "reviewed_role"]
    six_ok = all(row.get("legacy_occurrence_role_correct") is True for row in six_rows)
    fn = metrics.get("narrative_function_accuracy", {})
    qualified = (
        transport.get("provider_failures", 0) == 0
        and transport.get("invalid_payloads", 0) == 0
        and metrics.get("provenance_accuracy", {}).get("accuracy") == 1.0
        and metrics.get("identity_preservation", {}).get("accuracy") == 1.0
        and six_ok
        and float(fn.get("accuracy") or 0) >= 0.9
        and confusion.get("annotation_participant_collapsed_to_scene_participant", {}).get("after_a2o_count") == 0
        and safety.get("canonical_writes") == 0
        and safety.get("production_person_creations") == 0
        and safety.get("identity_replacements") == 0
    )
    if qualified:
        value = "sfh2_occurrence_semantics_qualified"
        next_stage = "SFH2.2-F-prep"
    elif float(fn.get("accuracy") or 0) < 0.9:
        value = "sfh2_occurrence_model_quality_insufficient"
        next_stage = "A2O error taxonomy before architecture change"
    else:
        value = "sfh2_occurrence_representation_promising_needs_review"
        next_stage = "SFH2.2-A2O review / targeted refinement"
    return value, {
        "schema": "sfh2-a2o-recommendation-v1",
        "recommendation": value,
        "next_stage": next_stage,
        "qualified": qualified,
        "criteria": {
            "provenance_100_percent": metrics.get("provenance_accuracy", {}).get("accuracy") == 1.0,
            "identity_preservation_100_percent": metrics.get("identity_preservation", {}).get("accuracy") == 1.0,
            "six_reviewed_role_cases_correct": six_ok,
            "expanded_narrative_function_at_least_90_percent": float(fn.get("accuracy") or 0) >= 0.9,
            "no_annotation_to_scene_collapse": confusion.get("annotation_participant_collapsed_to_scene_participant", {}).get("after_a2o_count") == 0,
            "transport_valid": transport.get("provider_failures", 0) == 0 and transport.get("invalid_payloads", 0) == 0,
            "unsafe_writes_zero": safety.get("canonical_writes") == 0 and safety.get("production_person_creations") == 0,
        },
        "a2r_baseline_reference": six,
        "candidate_only": True,
        "canonical_write_back": False,
    }


def _write_markdown(output: Path, evaluation: Mapping[str, Any], rec: Mapping[str, Any], cases: list[Mapping[str, Any]]) -> None:
    lines = [
        "# SFH2.2-A2O — Occurrence Semantics Decomposition Pilot",
        "",
        "Identity is frozen from SFH2.2-A2GR. `provenance_layer` is copied from the target evidence metadata; only `narrative_function` is supplied by the occurrence historian. Legacy `occurrence_role` is a compatibility projection.",
        "",
        f"Pilot cases: {len(cases)}; reviewed Gold cases: {evaluation.get('reviewed_gold_count')}; provider calls are recorded separately.",
        "",
        "## Boundary",
        "",
        "Python does not inspect Chinese surfaces or choose identities. It derives source provenance from `source_evidence_id`, validates the compact provider contract, and applies the generic compatibility projection.",
        "",
        "## Results",
        "",
        f"- Provenance accuracy: `{evaluation.get('metrics', {}).get('provenance_accuracy')}`",
        f"- Narrative-function accuracy: `{evaluation.get('metrics', {}).get('narrative_function_accuracy')}`",
        f"- Projected legacy-role accuracy: `{evaluation.get('metrics', {}).get('legacy_occurrence_role_accuracy')}`",
        f"- Identity preservation: `{evaluation.get('metrics', {}).get('identity_preservation')}`",
        f"- A2R six-case baseline: `{evaluation.get('a2r_six_case_baseline')}`",
        f"- Recommendation: `{rec.get('recommendation')}`",
        "",
        "## Cohort",
        "",
        "The cohort contains the six frozen A2G role cases and all 20 frozen A0R-L challenge mentions. Selection is deterministic, does not use Gold or model results, and retains the repeated occurrences as separate mention records.",
        "",
        "## Interpretation",
        "",
        "The decomposition preserves the distinction between participation in Liu's annotation narrative and participation in the Shishuo main-text scene. Any remaining function mismatch is a semantic historian limitation, not a Python historical replacement. This pilot does not start the 188-Story run.",
    ]
    (output / "occurrence-semantics.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def run(*, live: bool, run_id: str) -> dict[str, Any]:
    cases = all_cases()
    inputs = load_inputs()
    packets = _case_packets(cases, inputs)
    output = OUT if live else OUT / "replays" / run_id
    output.mkdir(parents=True, exist_ok=True)
    freeze = architecture_freeze(cases)
    selection = selection_document(cases, inputs, packets)
    write_json(output / "architecture-freeze.json", freeze)
    write_json(output / "selection.json", selection)
    write_json(output / "case-packets.json", {
        "schema": "sfh2-a2o-case-packets-v1",
        "packets": [{"case_id": case.get("case_id"), "cohort": case.get("cohort"), "packet": packets[text(case.get("case_id"))]} for case in cases],
        "gold_not_sent_to_provider": True,
        "identity_is_frozen": True,
        "candidate_only": True,
        "canonical_write_back": False,
    })

    transport_rows: list[dict[str, Any]] = []
    if live:
        client = A2OClient(run_id, live=True)
        probe = client.probe(occurrence_function_tool())
        transport_rows.append(probe)
        if probe.get("valid") is not True:
            transport = summarize(transport_rows, live=True, client_attempts=client.attempts)
            write_json(output / "transport.json", transport)
            raise RuntimeError("sfh2_a2o_provider_schema_probe_failed")
        result_rows: dict[str, dict[str, Any]] = {}
        for case in cases:
            case_id = text(case.get("case_id"))
            payload = provider_payload(packets[case_id])
            response, transport_row = client.call(case_id=case_id, system=HISTORIAN_SYSTEM, payload=payload, tool=occurrence_function_tool())
            transport_rows.append(transport_row)
            result_rows[case_id] = _result_row(case, packets[case_id], response, transport_row)
        transport = summarize(transport_rows, live=True, client_attempts=client.attempts)
    else:
        source_path = OUT / "occurrence-results.json"
        result_rows = _load_offline_rows(source_path, cases)
        source_transport = read_json(OUT / "transport.json", {}) or {}
        transport = dict(source_transport) if isinstance(source_transport, Mapping) else {}
        transport.update({"live": False, "provider_attempts": 0, "offline_replay": True, "source_live_artifact": str(source_path.relative_to(ROOT))})

    write_json(output / "occurrence-results.json", {
        "schema": "sfh2-a2o-occurrence-results-v1",
        "model": MODEL,
        "prompt_version": PROMPT_VERSION,
        "records": [result_rows[text(case.get("case_id"))] for case in cases],
        "gold_not_sent_to_provider": True,
        "identity_is_frozen": True,
        "candidate_only": True,
        "canonical_write_back": False,
    })
    write_json(output / "transport.json", transport)
    projections = []
    for case in cases:
        row = result_rows[text(case.get("case_id"))]
        projections.append({
            "case_id": row["case_id"],
            "story_id": row["story_id"],
            "mention_id": row["mention_id"],
            "surface": row["surface"],
            "provenance_layer": row["provenance_layer"],
            "narrative_function": (row.get("occurrence_result") or {}).get("narrative_function"),
            "legacy_occurrence_role": project_legacy_occurrence_role(text(row.get("provenance_layer")), text((row.get("occurrence_result") or {}).get("narrative_function"))) if row.get("valid") else None,
            "valid": row.get("valid") is True,
            "candidate_only": True,
            "canonical_write_back": False,
        })
    write_json(output / "projected-legacy-roles.json", {"schema": "sfh2-a2o-projected-legacy-roles-v1", "records": projections, "projection_authority": "generic structured-axis compatibility mapping", "candidate_only": True, "canonical_write_back": False})

    # Gold is loaded only after provider inference has been completed.
    gold = read_json(GOLD_PATH, {}) or {}
    evaluation = evaluate(cases, result_rows, gold)
    write_json(output / "evaluation.json", evaluation)
    confusion = confusion_matrix(evaluation)
    write_json(output / "confusion-matrix.json", confusion)
    errors = error_analysis(evaluation)
    write_json(output / "error-analysis.json", errors)
    safety = storage_safety(cases, result_rows, input_hashes())
    write_json(output / "storage-safety-audit.json", safety)
    rec_value, rec = recommendation(evaluation, transport, safety, confusion)
    write_json(output / "metrics.json", {
        "schema": "sfh2-a2o-metrics-v1",
        "pilot": "SFH2.2-A2O",
        "provider": {key: transport.get(key) for key in ("provider_calls", "case_calls", "parsed_calls", "provider_failures", "invalid_payloads", "retries", "prompt_tokens", "completion_tokens", "total_tokens", "median_latency_seconds", "max_latency_seconds")},
        "evaluation": evaluation.get("metrics", {}),
        "six_case_comparison": {"a2r": evaluation.get("a2r_six_case_baseline"), "a2o": {"correct": sum(row.get("legacy_occurrence_role_correct") is True for row in evaluation.get("records", []) if row.get("cohort") == "reviewed_role"), "evaluable": sum(row.get("legacy_occurrence_role_correct") is not None for row in evaluation.get("records", []) if row.get("cohort") == "reviewed_role")}},
        "candidate_only": True,
        "canonical_write_back": False,
    })
    write_json(output / "recommendation.json", rec)
    _write_markdown(output, evaluation, rec, cases)
    validation = {
        "schema": "sfh2-a2o-validation-summary-v1",
        "pilot": "SFH2.2-A2O",
        "baseline_commit": BASELINE_COMMIT,
        "provider_calls": transport.get("provider_calls", 0),
        "case_count": len(cases),
        "reviewed_gold_count": evaluation.get("reviewed_gold_count"),
        "strict_schema_errors": [],
        "candidate_only": True,
        "canonical_write_back": False,
        "recommendation": rec_value,
    }
    write_json(output / "validation-summary.json", validation)
    return {"cases": cases, "packets": packets, "rows": result_rows, "evaluation": evaluation, "transport": transport, "safety": safety, "recommendation": rec_value}
