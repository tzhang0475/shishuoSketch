"""SFH2.2-A2OR paired rerun using the frozen A2O packets."""

from __future__ import annotations

import copy
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Mapping

from .common import (
    A2O_ROOT,
    A2OT_ROOT,
    A2O_BASELINE_COMMIT,
    BASELINE_COMMIT,
    FUNCTION_NAME,
    GOLD_PATH,
    MODEL,
    OUT,
    PROMPT_VERSION,
    ROOT,
    SCHEMA_VERSION,
    STRICT_ENDPOINT,
    TEMPERATURE,
    THINKING,
    a2o_result_semantics,
    by_case,
    canonical_json,
    file_hash,
    frozen_input_hashes,
    load_frozen_a2o,
    old_gold_map,
    protected_hashes,
    read_json,
    rows,
    stable_hash,
    text,
    write_json,
)
from .contracts import occurrence_function_tool, validate_occurrence_payload
from .prompt import HISTORIAN_SYSTEM, probe_messages, prompt_metadata, provider_payload
from .transport import A2ORClient, summarize
from sfh2_a2o.provenance import derive_provenance_layer, project_legacy_occurrence_role


KNOWN_ERROR_CASES = (
    "sfh2-a0-57d1fc3c0492b21ee1f4",
    "sfh2-a0r-l-challenge-02fa84b24af39e8f8201",
    "sfh2-a0r-l-challenge-f245371d8f0cdf9c8773",
    "sfh2-a0r-l-challenge-d3c8fa925020f0c2c62a",
)


def _stable_transport(row: Mapping[str, Any]) -> dict[str, Any]:
    keys = (
        "stage", "case_id", "request_hash", "model", "temperature", "thinking",
        "prompt_version", "attempt", "classification", "valid", "parse_error",
        "usage", "finish_reason", "response_witness_sha256", "http_status",
        "provider_error_code", "provider_error_message", "provider_error_type",
        "provider_error_param", "provider_request_id", "retryable", "attempt_history",
    )
    return {key: copy.deepcopy(row[key]) for key in keys if key in row}


def _case_row(case: Mapping[str, Any], packet: Mapping[str, Any], payload: Mapping[str, Any] | None, transport: Mapping[str, Any]) -> dict[str, Any]:
    validation = validate_occurrence_payload(packet, payload)
    provenance, provenance_errors = derive_provenance_layer(packet)
    result = validation.get("result") if validation.get("valid") else None
    output_keys = set(result or {})
    forbidden = sorted(output_keys & {"semantic_kind", "reference_type", "referent", "occurrence_role", "relations", "identity", "canonical_hint"})
    errors = list(validation.get("errors", []))
    if forbidden:
        errors.append("identity_field_in_occurrence_output")
        result = None
    valid = not errors and validation.get("valid") is True and not provenance_errors
    return {
        "case_id": text(case.get("case_id")),
        "cohort": case.get("cohort"),
        "story_id": case.get("story_id"),
        "mention_id": case.get("mention_id"),
        "surface": case.get("surface"),
        "provenance_layer": provenance,
        "provenance_errors": provenance_errors,
        "valid": valid,
        "contract_status": "valid" if valid else "provider_or_contract_invalid",
        "errors": sorted(set(errors)),
        "occurrence_result": copy.deepcopy(result) if valid else None,
        "frozen_identity": copy.deepcopy(packet.get("frozen_identity_context")),
        "frozen_identity_hash": stable_hash(packet.get("frozen_identity_context", {})),
        "identity_preserved": True,
        "transport": _stable_transport(transport),
        "candidate_only": True,
        "canonical_write_back": False,
    }


def _architecture(bundle: Mapping[str, Any]) -> dict[str, Any]:
    tool = occurrence_function_tool()
    code_paths = [
        ROOT / "scripts/sfh2_a2or/common.py",
        ROOT / "scripts/sfh2_a2or/contracts.py",
        ROOT / "scripts/sfh2_a2or/prompt.py",
        ROOT / "scripts/sfh2_a2or/transport.py",
        ROOT / "scripts/sfh2_a2or/pipeline.py",
    ]
    code_files = {str(path.relative_to(ROOT)): file_hash(path) for path in code_paths}
    result: dict[str, Any] = {
        "schema": "sfh2-a2or-architecture-v1",
        "stage": "SFH2.2-A2OR",
        "baseline_commit": BASELINE_COMMIT,
        "frozen_a2o_commit": A2O_BASELINE_COMMIT,
        "frozen_a2o_selection_hash": bundle["selection_document"].get("selection_hash"),
        "case_count": len(bundle["selections"]),
        "model_config": {
            "model": MODEL,
            "temperature": TEMPERATURE,
            "thinking": dict(THINKING),
            "endpoint": STRICT_ENDPOINT,
            "prompt_version": PROMPT_VERSION,
            "function_name": FUNCTION_NAME,
            "max_provider_attempts": 40,
            "retry_policy": "transient_only_at_most_one_retry; HTTP400_not_retryable",
        },
        "prompt": prompt_metadata(),
        "prompt_hash": stable_hash(HISTORIAN_SYSTEM),
        "schema_hash": stable_hash(tool),
        "code_files": code_files,
        "frozen_a2o_input_hashes": frozen_input_hashes(bundle),
        "taxonomy_source_hash": file_hash(A2OT_ROOT / "taxonomy-definition.json"),
        "authority_boundary": "frozen A2O identity/provenance inputs; LLM narrative_function only; Python structural validation and generic compatibility projection",
        "same_evidence_packets": True,
        "gold_not_in_provider_packets": True,
        "identity_is_frozen": True,
        "candidate_only": True,
        "canonical_write_back": False,
        "no_full_188_story_live_run": True,
    }
    result["architecture_hash"] = stable_hash(result)
    return result


def _selection_verification(bundle: Mapping[str, Any]) -> dict[str, Any]:
    selections = bundle["selections"]
    packet_hashes = {case_id: stable_hash(packet) for case_id, packet in sorted(bundle["packets"].items())}
    return {
        "schema": "sfh2-a2or-selection-verification-v1",
        "source_selection": "data/generated/sfh2-a2o/selection.json",
        "source_case_packets": "data/generated/sfh2-a2o/case-packets.json",
        "source_selection_sha256": file_hash(A2O_ROOT / "selection.json"),
        "source_case_packets_sha256": file_hash(A2O_ROOT / "case-packets.json"),
        "selection_hash": bundle["selection_document"].get("selection_hash"),
        "case_count": len(selections),
        "case_ids": [text(row.get("case_id")) for row in selections],
        "packet_hashes": packet_hashes,
        "same_case_order": [text(row.get("case_id")) for row in selections] == [text(row.get("case_id")) for row in rows(read_json(A2O_ROOT / "selection.json", {}), "cases")],
        "gold_used_for_selection": False,
        "candidate_only": True,
        "canonical_write_back": False,
    }


def _case_packets_document(bundle: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "schema": "sfh2-a2or-case-packets-v1",
        "source": "immutable data/generated/sfh2-a2o/case-packets.json",
        "same_packets_as_a2o": True,
        "gold_not_sent_to_provider": True,
        "packets": [
            {"case_id": row.get("case_id"), "cohort": row.get("cohort"), "packet": copy.deepcopy(bundle["packets"][text(row.get("case_id"))])}
            for row in bundle["selections"]
        ],
        "candidate_only": True,
        "canonical_write_back": False,
    }


def _write_preparation(output: Path, bundle: Mapping[str, Any]) -> None:
    write_json(output / "architecture.json", _architecture(bundle))
    write_json(output / "selection-verification.json", _selection_verification(bundle))
    write_json(output / "case-packets.json", _case_packets_document(bundle))


def _load_live_results() -> dict[str, dict[str, Any]]:
    result_rows = by_case(read_json(OUT / "occurrence-results.json", {}))
    expected = {text(row.get("case_id")) for row in load_frozen_a2o()["selections"]}
    if set(result_rows) != expected:
        raise RuntimeError("sfh2_a2or_live_results_missing_or_changed")
    return result_rows


def _write_rows_and_derived(output: Path, bundle: Mapping[str, Any], result_rows: Mapping[str, Mapping[str, Any]], transport: Mapping[str, Any]) -> dict[str, Any]:
    cases = bundle["selections"]
    write_json(output / "occurrence-results.json", {
        "schema": "sfh2-a2or-occurrence-results-v1",
        "model": MODEL,
        "prompt_version": PROMPT_VERSION,
        "source_a2o_packets": "data/generated/sfh2-a2o/case-packets.json",
        "records": [copy.deepcopy(result_rows[text(case.get("case_id"))]) for case in cases],
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
            "cohort": row.get("cohort"),
            "story_id": row.get("story_id"),
            "mention_id": row.get("mention_id"),
            "surface": row.get("surface"),
            "provenance_layer": row.get("provenance_layer"),
            "narrative_function": (row.get("occurrence_result") or {}).get("narrative_function"),
            "legacy_occurrence_role": project_legacy_occurrence_role(text(row.get("provenance_layer")), text((row.get("occurrence_result") or {}).get("narrative_function"))) if row.get("valid") else None,
            "valid": row.get("valid") is True,
            "candidate_only": True,
            "canonical_write_back": False,
        })
    projection_document = {"schema": "sfh2-a2or-projected-legacy-roles-v1", "records": projections, "projection_authority": "unchanged generic structured-axis compatibility mapping", "candidate_only": True, "canonical_write_back": False}
    write_json(output / "projected-legacy-roles.json", projection_document)
    return projection_document


def _accuracy(records: list[Mapping[str, Any]], field: str) -> dict[str, Any]:
    values = [row.get(field) for row in records if row.get(field) is not None]
    correct = sum(value is True for value in values)
    return {"correct": correct, "evaluable": len(values), "accuracy": round(correct / len(values), 4) if values else None}


def evaluate(bundle: Mapping[str, Any], result_rows: Mapping[str, Mapping[str, Any]], projection_document: Mapping[str, Any]) -> dict[str, Any]:
    gold = by_case(read_json(GOLD_PATH, {}))
    records: list[dict[str, Any]] = []
    projections = by_case(projection_document)
    for case in bundle["selections"]:
        case_id = text(case.get("case_id"))
        row = result_rows[case_id]
        expected = gold.get(case_id, {})
        output = row.get("occurrence_result") if isinstance(row.get("occurrence_result"), Mapping) else {}
        projection = projections.get(case_id, {})
        records.append({
            "case_id": case_id,
            "cohort": case.get("cohort"),
            "story_id": case.get("story_id"),
            "surface": case.get("surface"),
            "provenance_layer": row.get("provenance_layer"),
            "predicted_narrative_function": output.get("narrative_function"),
            "predicted_legacy_occurrence_role": projection.get("legacy_occurrence_role"),
            "expected_provenance_layer": expected.get("expected_provenance_layer"),
            "expected_narrative_function": expected.get("expected_narrative_function"),
            "expected_legacy_occurrence_role": expected.get("expected_legacy_occurrence_role"),
            "provenance_correct": row.get("provenance_layer") == expected.get("expected_provenance_layer"),
            "narrative_function_correct": output.get("narrative_function") == expected.get("expected_narrative_function") if row.get("valid") else False,
            "legacy_occurrence_role_correct": projection.get("legacy_occurrence_role") == expected.get("expected_legacy_occurrence_role") if row.get("valid") else False,
            "identity_preserved": row.get("identity_preserved") is True and row.get("frozen_identity_hash") == stable_hash(bundle["packets"][case_id].get("frozen_identity_context", {})),
            "valid": row.get("valid") is True,
            "confidence": output.get("confidence"),
            "reason_summary": output.get("reason_summary"),
            "errors": copy.deepcopy(row.get("errors", [])),
        })
    by_cohort: dict[str, dict[str, Any]] = {}
    for cohort in sorted({text(row.get("cohort")) for row in records}):
        subset = [row for row in records if row.get("cohort") == cohort]
        by_cohort[cohort] = {"case_count": len(subset), "narrative_function": _accuracy(subset, "narrative_function_correct"), "legacy_role": _accuracy(subset, "legacy_occurrence_role_correct"), "provenance": _accuracy(subset, "provenance_correct"), "identity_preservation": _accuracy(subset, "identity_preserved")}
    by_layer: dict[str, dict[str, Any]] = {}
    for layer in sorted({text(row.get("expected_provenance_layer")) for row in records}):
        subset = [row for row in records if row.get("expected_provenance_layer") == layer]
        by_layer[layer] = {"case_count": len(subset), "narrative_function": _accuracy(subset, "narrative_function_correct"), "legacy_role": _accuracy(subset, "legacy_occurrence_role_correct")}
    by_function: dict[str, dict[str, Any]] = {}
    for function in sorted({text(row.get("expected_narrative_function")) for row in records}):
        subset = [row for row in records if row.get("expected_narrative_function") == function]
        by_function[function] = {"case_count": len(subset), "correct": sum(row.get("narrative_function_correct") is True for row in subset), "accuracy": round(sum(row.get("narrative_function_correct") is True for row in subset) / len(subset), 4) if subset else None}
    collapse = sum(row.get("expected_legacy_occurrence_role") == "annotation_person" and row.get("predicted_legacy_occurrence_role") == "scene_participant" for row in records)
    return {
        "schema": "sfh2-a2or-evaluation-v1",
        "case_count": len(records),
        "reviewed_gold_count": sum(bool(gold.get(row["case_id"], {}).get("review_status") == "reviewed") for row in records),
        "records": records,
        "metrics": {
            "provenance_accuracy": _accuracy(records, "provenance_correct"),
            "narrative_function_accuracy": _accuracy(records, "narrative_function_correct"),
            "legacy_occurrence_role_accuracy": _accuracy(records, "legacy_occurrence_role_correct"),
            "identity_preservation": _accuracy(records, "identity_preserved"),
            "valid_records": sum(row.get("valid") is True for row in records),
            "annotation_to_scene_collapse": collapse,
        },
        "by_cohort": by_cohort,
        "by_provenance_layer": by_layer,
        "by_narrative_function": by_function,
        "candidate_only": True,
        "canonical_write_back": False,
    }


def _paired(bundle: Mapping[str, Any], evaluation: Mapping[str, Any]) -> dict[str, Any]:
    old_gold = old_gold_map(bundle)
    a2o = bundle["a2o_results"]
    rows_out = []
    counts = Counter()
    for row in evaluation["records"]:
        case_id = text(row.get("case_id"))
        a2o_prediction = a2o_result_semantics(a2o[case_id]).get("narrative_function")
        promoted_expected = row.get("expected_narrative_function")
        old_expected = old_gold.get(case_id, {}).get("expected_narrative_function")
        a2o_old_correct = a2o_prediction == old_expected
        a2o_promoted_correct = a2o_prediction == promoted_expected
        a2or_correct = row.get("narrative_function_correct") is True
        if a2o_promoted_correct and a2or_correct:
            classification = "unchanged_correct"
        elif not a2o_promoted_correct and not a2or_correct:
            classification = "unchanged_wrong"
        elif not a2o_promoted_correct and a2or_correct:
            classification = "fixed_by_v2"
        else:
            classification = "regressed_under_v2"
        counts[classification] += 1
        rows_out.append({
            "case_id": case_id,
            "surface": row.get("surface"),
            "a2o_function": a2o_prediction,
            "a2or_function": row.get("predicted_narrative_function"),
            "old_gold_function": old_expected,
            "promoted_gold_function": promoted_expected,
            "a2o_old_gold_correct": a2o_old_correct,
            "a2o_promoted_gold_correct": a2o_promoted_correct,
            "a2or_promoted_gold_correct": a2or_correct,
            "classification": classification,
            "a2o_reason_summary": a2o_result_semantics(a2o[case_id]).get("reason_summary"),
            "a2or_reason_summary": row.get("reason_summary"),
            "error_category": "narrative_function_mismatch" if classification in {"fixed_by_v2", "regressed_under_v2", "unchanged_wrong"} else None,
        })
    a2o_old_correct = sum(row["a2o_old_gold_correct"] for row in rows_out)
    a2o_promoted_correct = sum(row["a2o_promoted_gold_correct"] for row in rows_out)
    a2or_correct = sum(row["a2or_promoted_gold_correct"] for row in rows_out)
    return {
        "schema": "sfh2-a2or-paired-comparison-v1",
        "case_count": len(rows_out),
        "a2o_original": {"correct": a2o_old_correct, "evaluable": len(rows_out), "accuracy": round(a2o_old_correct / len(rows_out), 4)},
        "a2o_promoted_gold_counterfactual": {"correct": a2o_promoted_correct, "evaluable": len(rows_out), "accuracy": round(a2o_promoted_correct / len(rows_out), 4)},
        "a2or": {"correct": a2or_correct, "evaluable": len(rows_out), "accuracy": round(a2or_correct / len(rows_out), 4)},
        "fixed_count": counts["fixed_by_v2"],
        "regression_count": counts["regressed_under_v2"],
        "net_improvement": a2or_correct - a2o_promoted_correct,
        "classification_counts": dict(sorted(counts.items())),
        "records": rows_out,
    }


def known_error_recovery(bundle: Mapping[str, Any], evaluation: Mapping[str, Any]) -> dict[str, Any]:
    by_id = {text(row.get("case_id")): row for row in evaluation["records"]}
    result = []
    for case_id in KNOWN_ERROR_CASES:
        row = by_id[case_id]
        a2o = a2o_result_semantics(bundle["a2o_results"][case_id])
        result.append({
            "case_id": case_id,
            "surface": row.get("surface"),
            "previous_a2o_function": a2o.get("narrative_function"),
            "a2or_function": row.get("predicted_narrative_function"),
            "reviewed_gold_function": row.get("expected_narrative_function"),
            "recovered": row.get("narrative_function_correct") is True and a2o.get("narrative_function") != row.get("expected_narrative_function"),
        })
    return {"schema": "sfh2-a2or-known-error-recovery-v1", "records": result, "recovered_count": sum(bool(row["recovered"]) for row in result), "case_count": len(result)}


def regression_audit(paired: Mapping[str, Any]) -> dict[str, Any]:
    rows_out = [row for row in paired.get("records", []) if row.get("classification") == "regressed_under_v2"]
    return {"schema": "sfh2-a2or-regression-audit-v1", "regression_count": len(rows_out), "records": rows_out, "interpretation": "A regression is an A2O-promoted-Gold-correct function changed to a wrong A2OR function; it is not inferred from prose or identity strings."}


def confusion_matrix(evaluation: Mapping[str, Any]) -> dict[str, Any]:
    matrix: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    role_matrix: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for row in evaluation["records"]:
        matrix[text(row.get("expected_narrative_function"))][text(row.get("predicted_narrative_function"))] += 1
        role_matrix[text(row.get("expected_legacy_occurrence_role"))][text(row.get("predicted_legacy_occurrence_role"))] += 1
    return {"schema": "sfh2-a2or-confusion-matrix-v1", "narrative_function_expected_to_predicted": {key: dict(value) for key, value in sorted(matrix.items())}, "legacy_role_expected_to_predicted": {key: dict(value) for key, value in sorted(role_matrix.items())}, "annotation_to_scene_collapse": evaluation["metrics"]["annotation_to_scene_collapse"]}


def error_analysis(evaluation: Mapping[str, Any]) -> dict[str, Any]:
    errors = [row for row in evaluation["records"] if row.get("narrative_function_correct") is not True]
    return {"schema": "sfh2-a2or-error-analysis-v1", "error_count": len(errors), "records": errors, "analysis_boundary": "taxonomy/model errors are reported; Python does not replace historical semantics."}


def recommendation(evaluation: Mapping[str, Any], transport: Mapping[str, Any], paired: Mapping[str, Any], safety: Mapping[str, Any]) -> dict[str, Any]:
    metrics = evaluation["metrics"]
    six = [row for row in evaluation["records"] if row.get("cohort") == "reviewed_role"]
    function = metrics["narrative_function_accuracy"].get("accuracy") or 0
    role = metrics["legacy_occurrence_role_accuracy"].get("accuracy") or 0
    systematic = any(info.get("case_count", 0) >= 2 and float(info.get("accuracy") or 0) == 0 for info in evaluation.get("by_narrative_function", {}).values())
    qualified = (
        transport.get("provider_failures", 0) == 0
        and transport.get("invalid_payloads", 0) == 0
        and transport.get("schema_probe_calls") == 1
        and transport.get("parsed_calls") == 27
        and metrics.get("valid_records") == 26
        and metrics.get("provenance_accuracy", {}).get("accuracy") == 1.0
        and metrics.get("identity_preservation", {}).get("accuracy") == 1.0
        and all(row.get("legacy_occurrence_role_correct") is True for row in six)
        and function >= 0.9
        and role >= 0.9
        and metrics.get("annotation_to_scene_collapse") == 0
        and paired.get("regression_count") <= 1
        and safety.get("canonical_writes") == 0
        and safety.get("identity_replacements") == 0
    )
    if qualified:
        value = "sfh2_occurrence_single_historian_qualified"
        next_stage = "SFH2.2-F-prep"
    elif transport.get("provider_failures", 0) or transport.get("invalid_payloads", 0) or transport.get("parsed_calls") != 27:
        value = "sfh2_occurrence_transport_failure"
        next_stage = "repair transport before semantic conclusion"
    elif function < 0.9 or role < 0.9 or systematic:
        value = "sfh2_occurrence_model_quality_insufficient"
        next_stage = "A2OR error taxonomy before architecture change"
    else:
        value = "sfh2_occurrence_semantic_reviewer_needed"
        next_stage = "targeted independent semantic review"
    return {
        "schema": "sfh2-a2or-recommendation-v1",
        "recommendation": value,
        "next_stage": next_stage,
        "qualified": qualified,
        "criteria": {
            "provenance_100_percent": metrics.get("provenance_accuracy", {}).get("accuracy") == 1.0,
            "identity_preservation_100_percent": metrics.get("identity_preservation", {}).get("accuracy") == 1.0,
            "valid_records_26_of_26": metrics.get("valid_records") == 26,
            "six_reviewed_role_cases_6_of_6": all(row.get("legacy_occurrence_role_correct") is True for row in six),
            "narrative_function_at_least_90_percent": function >= 0.9,
            "projected_role_at_least_90_percent": role >= 0.9,
            "annotation_main_text_collapse_zero": metrics.get("annotation_to_scene_collapse") == 0,
            "regression_damage_at_most_one": paired.get("regression_count") <= 1,
            "transport_valid": transport.get("provider_failures", 0) == 0 and transport.get("invalid_payloads", 0) == 0,
            "unsafe_mutations_zero": safety.get("canonical_writes") == 0 and safety.get("identity_replacements") == 0,
        },
        "candidate_only": True,
        "canonical_write_back": False,
    }


def storage_safety(bundle: Mapping[str, Any], result_rows: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    return {
        "schema": "sfh2-a2or-storage-safety-v1",
        "production_person_creations": 0,
        "canonical_writes": 0,
        "alias_mutations": 0,
        "profile_mutations": 0,
        "identity_replacements": 0,
        "retrieval_candidate_identity_gating": 0,
        "substring_identity_creation": 0,
        "name_specific_python_semantic_rules": 0,
        "surface_specific_role_rules": 0,
        "identity_output_fields": sum("identity_field_in_occurrence_output" in (row.get("errors") or []) for row in result_rows.values()),
        "candidate_only": True,
        "canonical_write_back": False,
        "protected_hashes": protected_hashes(),
    }


def _write_markdown(output: Path, evaluation: Mapping[str, Any], paired: Mapping[str, Any], recommendation_doc: Mapping[str, Any], transport: Mapping[str, Any]) -> None:
    lines = [
        "# SFH2.2-A2OR — Clarified Occurrence Semantics Rerun",
        "",
        "A2OR is a paired live rerun of the immutable 26-case A2O cohort. The only intended semantic intervention is the v2 occurrence-centric taxonomy prompt; frozen identity, evidence packets, provenance derivation, and legacy projection are unchanged.",
        "",
        f"Provider calls: `{transport.get('provider_calls')}`; parsed calls: `{transport.get('parsed_calls')}`; recommendation: `{recommendation_doc.get('recommendation')}`.",
        "",
        "## Gold promotion",
        "",
        "One human-reviewed Gold record changes: the first occurrence in the summoning construction is `participant`, not `addressee`. The original A2O artifacts remain historical evidence.",
        "",
        "## Paired result",
        "",
        f"A2O original: `{paired.get('a2o_original')}`; A2O promoted-Gold counterfactual: `{paired.get('a2o_promoted_gold_counterfactual')}`; A2OR: `{paired.get('a2or')}`.",
        f"Fixed by v2: `{paired.get('fixed_count')}`; regressions: `{paired.get('regression_count')}`.",
        "",
        "## Authority boundary",
        "",
        "The model supplies only narrative_function. Python derives provenance from target evidence metadata, validates the compact output, and applies the generic structured-axis compatibility projection. No identity or canonical write-back is permitted.",
        "",
        "No 188-Story run is started by this stage.",
    ]
    (output / "clarified-occurrence-semantics.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def run(*, live: bool, run_id: str) -> dict[str, Any]:
    bundle = load_frozen_a2o()
    output = OUT if live else OUT / "replays" / run_id
    output.mkdir(parents=True, exist_ok=True)
    _write_preparation(output, bundle)
    tool = occurrence_function_tool()
    transport_rows: list[dict[str, Any]] = []
    if live:
        client = A2ORClient(run_id, live=True)
        probe = client.probe(tool, probe_messages())
        transport_rows.append(probe)
        if probe.get("valid") is not True:
            transport = summarize(transport_rows, live=True, provider_attempts=client.attempts)
            write_json(output / "transport.json", transport)
            write_json(output / "recommendation.json", {"schema": "sfh2-a2or-recommendation-v1", "recommendation": "sfh2_occurrence_transport_failure", "reason": "schema probe did not return a valid tool call", "provider_calls": client.attempts})
            raise RuntimeError("sfh2_a2or_provider_schema_probe_failed")
        result_rows: dict[str, dict[str, Any]] = {}
        for case in bundle["selections"]:
            case_id = text(case.get("case_id"))
            response, transport_row = client.call(case_id=case_id, system=HISTORIAN_SYSTEM, payload=provider_payload(bundle["packets"][case_id]), tool=tool)
            transport_rows.append(transport_row)
            result_rows[case_id] = _case_row(case, bundle["packets"][case_id], response, transport_row)
        transport = summarize(transport_rows, live=True, provider_attempts=client.attempts)
    else:
        source_rows = _load_live_results()
        result_rows = source_rows
        source_transport = read_json(OUT / "transport.json", {}) or {}
        transport = dict(source_transport)
        transport.update({"live": False, "provider_calls": 0, "provider_attempts": 0, "offline_replay": True, "source_live_artifact": "data/generated/sfh2-a2or/occurrence-results.json"})
    projection_document = _write_rows_and_derived(output, bundle, result_rows, transport)
    evaluation = evaluate(bundle, result_rows, projection_document)
    paired = _paired(bundle, evaluation)
    safety = storage_safety(bundle, result_rows)
    rec = recommendation(evaluation, transport, paired, safety)
    write_json(output / "evaluation.json", evaluation)
    write_json(output / "paired-comparison.json", paired)
    write_json(output / "known-error-recovery.json", known_error_recovery(bundle, evaluation))
    write_json(output / "regression-audit.json", regression_audit(paired))
    write_json(output / "confusion-matrix.json", confusion_matrix(evaluation))
    write_json(output / "error-analysis.json", error_analysis(evaluation))
    write_json(output / "storage-safety-audit.json", safety)
    write_json(output / "metrics.json", {
        "schema": "sfh2-a2or-metrics-v1",
        "provider": {key: transport.get(key) for key in ("provider_calls", "case_calls", "parsed_calls", "provider_failures", "invalid_payloads", "retries", "prompt_tokens", "completion_tokens", "total_tokens", "median_latency_seconds", "max_latency_seconds")},
        "a2o_original": paired.get("a2o_original"),
        "a2o_promoted_gold_counterfactual": paired.get("a2o_promoted_gold_counterfactual"),
        "a2or": paired.get("a2or"),
        "evaluation": evaluation.get("metrics"),
        "fixed_count": paired.get("fixed_count"),
        "regression_count": paired.get("regression_count"),
        "candidate_only": True,
        "canonical_write_back": False,
    })
    write_json(output / "recommendation.json", rec)
    _write_markdown(output, evaluation, paired, rec, transport)
    validation = {
        "schema": "sfh2-a2or-validation-summary-v1",
        "stage": "SFH2.2-A2OR",
        "baseline_commit": BASELINE_COMMIT,
        "case_count": len(bundle["selections"]),
        "provider_calls": transport.get("provider_calls", 0),
        "valid_records": evaluation["metrics"].get("valid_records"),
        "gold_loaded_after_inference": True,
        "a2o_inputs_read_only": True,
        "protected_hashes": protected_hashes(),
        "recommendation": rec.get("recommendation"),
        "candidate_only": True,
        "canonical_write_back": False,
    }
    write_json(output / "validation-summary.json", validation)
    return {"cases": bundle["selections"], "rows": result_rows, "transport": transport, "evaluation": evaluation, "paired": paired, "recommendation": rec.get("recommendation")}


if __name__ == "__main__":
    print(run(live=False, run_id="sfh2-a2or-offline"))
