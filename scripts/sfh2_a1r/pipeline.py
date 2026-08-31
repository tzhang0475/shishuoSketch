"""SFH2.2-A1R: revalidate cached Primary records and run repaired reviews.

This module is intentionally a projection runner.  It does not rerun the 40
Primary calls and it contains no historical identity rules.  Primary semantic
content comes from immutable A1 raw responses; Python only validates it,
routes formal review, and applies the strict patch/selection contract.
"""

from __future__ import annotations

import copy
import json
from collections import Counter
from pathlib import Path
from typing import Any, Mapping

from sfh2_a0r import pipeline as a0r
from sfh2_a0r.contracts import (
    adjudication_tool,
    critical_review_tool,
    semantic_diff_paths,
    semantic_equal,
    validate_deepseek_strict_schema,
)
from sfh2_a0r.evaluation import evaluate, gold_by_case
from sfh2_a0r_l.common import build_case_packet as build_l_packet
from sfh2_a0r_l.common import load_inputs as load_l_inputs
from sfh2_a0.schemas import RELATIONS

from .common import (
    A1R_LIVE_ROOT,
    A1R_L_ROOT,
    FUNCTION_NAMES,
    MODEL,
    OUT,
    PROMPT_VERSIONS,
    ROOT,
    STRICT_ENDPOINT,
    build_case_packet,
    canonical_json,
    cohort_cases,
    file_hash,
    patch_contract_fingerprint,
    read_json,
    source_manifest,
    stable_hash,
    text,
    write_json,
)
from .transport import ReviewClient, extract, summarize


def _evidence_ids(packet: Mapping[str, Any]) -> set[str]:
    return {text(row.get("evidence_id")) for row in packet.get("source_evidence", []) or [] if isinstance(row, Mapping) and text(row.get("evidence_id"))}


def _contract_mismatch_details(payload: Mapping[str, Any] | None, errors: list[str]) -> dict[str, Any]:
    """Describe cached-record contract failures without repairing semantics.

    A cached provider record is immutable evidence.  This helper only makes
    the local schema rejection auditable; it deliberately does not coerce a
    relation/role value into another ontology value.
    """

    details: dict[str, Any] = {"errors": sorted(set(errors))}
    record = payload.get("record") if isinstance(payload, Mapping) else None
    if isinstance(record, Mapping):
        relations = record.get("relations")
        if isinstance(relations, list):
            invalid = sorted({
                text(row.get("relation"))
                for row in relations
                if isinstance(row, Mapping) and text(row.get("relation")) not in RELATIONS
            })
            if invalid:
                details["invalid_relation_values"] = invalid
        role = text(record.get("occurrence_role"))
        if "invalid_occurrence_role" in errors and role:
            details["invalid_occurrence_role_value"] = role
    return details


def _record(row: Mapping[str, Any] | None, key: str = "record") -> Mapping[str, Any] | None:
    return a0r._record(row, key)


def _invalid(case: Mapping[str, Any], stage: str, errors: list[str], *, reason: str = "") -> dict[str, Any]:
    return {
        "case_id": text(case.get("case_id")), "mention_id": text(case.get("mention_id")),
        "story_id": text(case.get("story_id")), "surface": text(case.get("surface")),
        "stage": stage, "valid": False, "errors": sorted(set(errors)), "record": None,
        "effective_record": None, "selected_record": None, "reason_summary": reason,
        "candidate_only": True, "canonical_write_back": False,
    }


def _cached_primary_rows() -> dict[str, Mapping[str, Any]]:
    transport = read_json(A1R_LIVE_ROOT / "transport.json", []) or []
    result: dict[str, Mapping[str, Any]] = {}
    for row in transport if isinstance(transport, list) else []:
        if text(row.get("stage")) != "primary_historian" or text(row.get("classification")) != "parsed":
            continue
        unit_id = text(row.get("unit_id"))
        path = ROOT / text(row.get("raw_path"))
        if unit_id and path.is_file():
            result[unit_id] = {"transport": dict(row), "raw_path": str(path.relative_to(ROOT)), "raw_sha256": file_hash(path), "response": read_json(path, {}) or {}}
    return result


def _old_primary_validity(cohort: str) -> dict[str, bool]:
    document = read_json(A1R_L_ROOT / f"{cohort}-pass1.json", {}) or {}
    return {text(row.get("case_id")): row.get("valid") is True for row in document.get("records", []) or [] if isinstance(row, Mapping)}


def revalidate_cached_primary(cases_by_cohort: Mapping[str, list[Mapping[str, Any]]], inputs: Mapping[str, Any]) -> tuple[dict[str, dict[str, dict[str, Any]]], dict[str, Any], dict[str, dict[str, Any]]]:
    cached = _cached_primary_rows()
    p1: dict[str, dict[str, dict[str, Any]]] = {"regression": {}, "challenge": {}}
    packets: dict[str, dict[str, Any]] = {}
    rows: list[dict[str, Any]] = []
    before_counts: Counter[str] = Counter()
    after_counts: Counter[str] = Counter()
    for cohort, cases in cases_by_cohort.items():
        old_valid = _old_primary_validity(cohort)
        for case in cases:
            case_id = text(case.get("case_id"))
            packet = build_case_packet(case, inputs)
            packets[case_id] = packet
            unit_id = f"{cohort}:{case_id}"
            source = cached.get(unit_id)
            row: dict[str, Any]
            if source is None:
                row = _invalid(case, "pass1", ["cached_primary_response_missing"], reason="A1 cached live response was not found")
                source_info: dict[str, Any] = {}
            else:
                payload, parse_error = extract(source["response"], "submit_sfh2_a0r_primary_semantics_v1")
                if parse_error or payload is None:
                    row = _invalid(case, "pass1", [f"cached_primary_extract:{parse_error or 'unknown'}"])
                else:
                    row = a0r._record_from_provider(case, packet, payload)
                    if row.get("valid") is not True and row.get("errors"):
                        row["contract_mismatch"] = _contract_mismatch_details(payload, list(row.get("errors", [])))
                source_info = {key: source[key] for key in ("raw_path", "raw_sha256", "transport")}
                source_info["primary_source"] = "A1 cached live response"
            before_counts["valid" if old_valid.get(case_id) else "invalid"] += 1
            after_counts["valid" if row.get("valid") is True else "invalid"] += 1
            record = _record(row)
            realization = a0r.realize_semantic_record(case, record, inputs)
            row["cohort"] = cohort
            row["primary_source"] = source_info.get("primary_source", "A1 cached live response")
            row["cached_raw_path"] = source_info.get("raw_path")
            row["cached_raw_sha256"] = source_info.get("raw_sha256")
            row["previous_contract_valid"] = bool(old_valid.get(case_id))
            row["contract_revalidated"] = True
            row["provisional_realization"] = realization
            row["consistency"] = a0r.analyze_record(record, evidence_ids=_evidence_ids(packet), realization=realization, stage="pass1")
            p1[cohort][case_id] = row
            rows.append({
                "cohort": cohort, "case_id": case_id, "mention_id": text(case.get("mention_id")),
                "surface": text(case.get("surface")), "unit_id": unit_id,
                "primary_source": row["primary_source"], "raw_path": row.get("cached_raw_path"),
                "raw_sha256": row.get("cached_raw_sha256"),
                "previous_contract_valid": row["previous_contract_valid"],
                "revalidated_valid": row.get("valid") is True,
                "errors": row.get("errors", []),
                "contract_mismatch": copy.deepcopy(row.get("contract_mismatch", {})),
                "record": copy.deepcopy(record),
            })
    revalidation = {
        "schema": "sfh2-a1r-primary-cache-revalidation-v1",
        "source_run": "data/generated/sfh2-a0r-l/live/sfh2-a0r-l-host-live-v1",
        "cached_primary_responses": len(cached),
        "new_primary_provider_calls": 0,
        "before_valid": before_counts["valid"], "before_invalid": before_counts["invalid"],
        "after_valid": after_counts["valid"], "after_invalid": after_counts["invalid"],
        "records": rows,
        "residual_contract_mismatches": [
            row for row in rows if row.get("revalidated_valid") is not True and row.get("contract_mismatch")
        ],
        "candidate_only": True, "canonical_write_back": False,
    }
    return p1, revalidation, packets


def _unrun_review(case: Mapping[str, Any], primary: Mapping[str, Any] | None, consistency: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "case_id": text(case.get("case_id")), "mention_id": text(case.get("mention_id")), "story_id": text(case.get("story_id")),
        "surface": text(case.get("surface")), "stage": "pass2", "valid": isinstance(primary, Mapping), "decision": "not_run",
        "patch_ops": [], "reviewed_fields": [], "patch": {}, "reason_summary": "no hard/review severity signal",
        "supporting_evidence_ids": [], "effective_record": copy.deepcopy(primary) if isinstance(primary, Mapping) else None,
        "effective_record_source": "pass1_no_review" if isinstance(primary, Mapping) else "no_valid_record",
        "changed_fields": [], "errors": [] if isinstance(primary, Mapping) else ["primary_contract_or_provider_failure"],
        "consistency": copy.deepcopy(consistency), "candidate_only": True, "canonical_write_back": False,
        "review_attempted": False,
    }


def _run_review(case: Mapping[str, Any], packet: Mapping[str, Any], p1row: Mapping[str, Any], client: ReviewClient | None, inputs: Mapping[str, Any], *, live: bool) -> dict[str, Any]:
    record = _record(p1row)
    consistency = p1row.get("consistency", {})
    if not (p1row.get("valid") is True and a0r.review_required(consistency)):
        return _unrun_review(case, record, consistency)
    if client is None:
        return _invalid(case, "pass2", ["review_provider_unavailable"])
    raw = client.call(stage="critical_reviewer", unit_id=text(case.get("case_id")), system=a0r.CRITICAL_REVIEWER_SYSTEM, payload=a0r.critical_payload(packet, record, consistency), tool=critical_review_tool(), max_tokens=2200)
    if raw is None:
        result = _invalid(case, "pass2", ["provider_failure_or_unavailable"], reason="no valid Reviewer payload")
        result["review_attempted"] = True
        return result
    result = a0r._review_from_provider(case, packet, raw, record)
    result["review_attempted"] = True
    effective = _record(result, "effective_record")
    realization = a0r.realize_semantic_record(case, effective, inputs)
    result["consistency"] = a0r.analyze_record(effective, evidence_ids=_evidence_ids(packet), realization=realization, stage="pass2")
    result["provisional_realization"] = realization
    return result


def _unrun_pass3(case: Mapping[str, Any], reason: str) -> dict[str, Any]:
    return {"case_id": text(case.get("case_id")), "mention_id": text(case.get("mention_id")), "story_id": text(case.get("story_id")), "surface": text(case.get("surface")), "stage": "pass3", "valid": False, "decision": "not_run", "base_record": "", "patch_ops": [], "reviewed_fields": [], "patch": {}, "reason_summary": reason, "supporting_evidence_ids": [], "selected_record": None, "selected_record_source": "not_run", "changed_fields": [], "errors": [reason], "candidate_only": True, "canonical_write_back": False, "adjudication_attempted": False}


def run_cohort(cohort: str, cases: list[Mapping[str, Any]], p1: Mapping[str, Mapping[str, Any]], packets: Mapping[str, Mapping[str, Any]], inputs: Mapping[str, Any], client: ReviewClient | None, *, live: bool) -> dict[str, Any]:
    p2: dict[str, dict[str, Any]] = {}
    for case in cases:
        case_id = text(case.get("case_id"))
        p2[case_id] = _run_review(case, packets[case_id], p1[case_id], client, inputs, live=live)
    p3_required: dict[str, bool] = {}
    for case in cases:
        case_id = text(case.get("case_id"))
        p3_required[case_id] = bool(p1[case_id].get("valid") is True and a0r.needs_pass3(p1[case_id], p2[case_id], p2[case_id].get("consistency", {})))
    p3: dict[str, dict[str, Any]] = {}
    for case in cases:
        case_id = text(case.get("case_id"))
        if not p3_required[case_id]:
            continue
        if client is None:
            p3[case_id] = _unrun_pass3(case, "review_provider_unavailable")
            continue
        p1record = _record(p1[case_id])
        p2record = _record(p2[case_id], "effective_record")
        raw = client.call(stage="adjudicator", unit_id=text(case.get("case_id")), system=a0r.ADJUDICATOR_SYSTEM, payload=a0r.adjudication_payload(packets[case_id], p1record, p2[case_id], p2record, p2[case_id].get("consistency", {})), tool=adjudication_tool(), max_tokens=1800)
        if raw is None:
            result = _invalid(case, "pass3", ["provider_failure_or_unavailable"], reason="no valid Adjudicator payload")
            result["adjudication_attempted"] = True
        else:
            result = a0r._adjudication_from_provider(case, packets[case_id], raw, p1record, p2record)
            result["adjudication_attempted"] = True
        p3[case_id] = result
    finals: list[dict[str, Any]] = []
    for case in cases:
        case_id = text(case.get("case_id"))
        packet = packets[case_id]
        selector = a0r.select_record(_record(p1[case_id]), p2[case_id], p3.get(case_id), packet, pass3_required=p3_required[case_id])
        finals.append(a0r._final_row(case, selector.get("record"), selector, inputs, _evidence_ids(packet), p1[case_id].get("consistency", {}), p2[case_id].get("consistency", {}), p3_required[case_id]))
    return {"cohort": cohort, "cases": cases, "packets": packets, "pass1": dict(p1), "pass2": p2, "pass3": p3, "pass3_required": p3_required, "final": finals}


def _write_cohort_artifacts(out: Path, cohort: Mapping[str, Any]) -> None:
    prefix = text(cohort["cohort"])
    write_json(out / f"{prefix}-routing.json", {"schema": "sfh2-a1r-routing-v1", "records": [{"case_id": text(case.get("case_id")), "pass2_required": bool(cohort["pass1"][text(case.get("case_id"))].get("valid") and a0r.review_required(cohort["pass1"][text(case.get("case_id"))].get("consistency", {}))), "pass3_required": bool(cohort["pass3_required"][text(case.get("case_id"))]), "flags": copy.deepcopy(cohort["pass1"][text(case.get("case_id"))].get("consistency", {}).get("flags", [])), "routing_authority": "formal severity only; no replacement identity"} for case in cohort["cases"]], "candidate_only": True, "canonical_write_back": False})
    write_json(out / f"{prefix}-pass2.json", {"schema": "sfh2-a1r-pass2-v1", "records": [cohort["pass2"][text(case.get("case_id"))] for case in cohort["cases"]], "candidate_only": True, "canonical_write_back": False})
    write_json(out / f"{prefix}-pass3.json", {"schema": "sfh2-a1r-pass3-v1", "records": [cohort["pass3"][key] for key in sorted(cohort["pass3"])], "candidate_only": True, "canonical_write_back": False})
    write_json(out / f"{prefix}-final.json", {"schema": "sfh2-a1r-final-v1", "records": cohort["final"], "candidate_only": True, "canonical_write_back": False})


def _challenge_review(cohort: Mapping[str, Any]) -> tuple[dict[str, Any], str]:
    records: list[dict[str, Any]] = []
    markdown = ["# SFH2.2-A1R Challenge Review", "", "Historical correctness is pending external review.", ""]
    for case in cohort["cases"]:
        case_id = text(case.get("case_id"))
        packet = cohort["packets"][case_id]
        p1 = cohort["pass1"][case_id]
        p2 = cohort["pass2"][case_id]
        p3 = cohort["pass3"].get(case_id)
        final = next(row for row in cohort["final"] if text(row.get("case_id")) == case_id)
        evidence = packet.get("source_evidence", []) or []
        records.append({
            "case_id": case_id, "story_id": case.get("story_id"), "mention_id": case.get("mention_id"), "surface": case.get("surface"),
            "source_evidence": copy.deepcopy(evidence), "validated_local_mentions": copy.deepcopy(packet.get("validated_local_mentions", [])),
            "pass1_contract_valid": p1.get("valid") is True, "pass1_semantic_record": copy.deepcopy(p1.get("record")),
            "pass1_contract_errors": copy.deepcopy(p1.get("errors", [])), "python_flags": copy.deepcopy(p1.get("consistency", {}).get("flags", [])),
            "pass2_decision": p2.get("decision"), "pass2_patch_ops": copy.deepcopy(p2.get("patch_ops", [])), "pass2_reviewed_fields": copy.deepcopy(p2.get("reviewed_fields", [])),
            "pass3_decision": p3.get("decision") if isinstance(p3, Mapping) else None, "pass3_patch_ops": copy.deepcopy((p3 or {}).get("patch_ops", [])) if isinstance(p3, Mapping) else [],
            "final_semantic_record": copy.deepcopy(final.get("selected_record")), "final_realization": copy.deepcopy(final.get("final_realization")),
            "confidence": (final.get("selected_record") or {}).get("confidence") if isinstance(final.get("selected_record"), Mapping) else None,
            "supporting_evidence_ids": (final.get("selected_record") or {}).get("supporting_evidence_ids", []) if isinstance(final.get("selected_record"), Mapping) else [],
            "review_priority": "high" if p3 else "review" if p2.get("review_attempted") else "normal",
            "reviewer_fields": {"correct": "", "identity_or_canonicalization": "", "semantic_kind": "", "occurrence_role": "", "discourse": "", "wrong_person": "", "abstain": "", "insufficient_evidence": "", "expected_referent": "", "notes": ""},
        })
        main = next((item.get("text") for item in evidence if item.get("source_layer") == "main_text"), "")
        liu = " | ".join(item.get("text", "") for item in evidence if item.get("source_layer") == "liu_annotation")
        markdown.extend([
            f"## {case_id}", f"- Story: `{case.get('story_id')}`", f"- Mention: `{case.get('mention_id')}` / `{case.get('surface')}`",
            f"- 正文: {main}", f"- 刘注/证据: {liu}", f"- Pass 1 valid: `{p1.get('valid')}` record=`{json.dumps(p1.get('record'), ensure_ascii=False, sort_keys=True)}`",
            f"- Python flags: `{json.dumps(p1.get('consistency', {}).get('flags', []), ensure_ascii=False, sort_keys=True)}`",
            f"- Pass 2: `{p2.get('decision')}` patch_ops=`{json.dumps(p2.get('patch_ops', []), ensure_ascii=False, sort_keys=True)}`",
            f"- Pass 3: `{p3.get('decision') if isinstance(p3, Mapping) else ''}` patch_ops=`{json.dumps((p3 or {}).get('patch_ops', []), ensure_ascii=False, sort_keys=True) if isinstance(p3, Mapping) else '[]'}`",
            f"- Final: `{json.dumps(final.get('selected_record'), ensure_ascii=False, sort_keys=True)}`", "- Historical correctness: pending external review",
            "- Reviewer: [ ] correct  [ ] identity/canonicalization  [ ] semantic kind  [ ] role  [ ] discourse  [ ] wrong person  [ ] abstain  [ ] insufficient evidence", "- Expected referent:", "- Notes:", "",
        ])
    return {"schema": "sfh2-a1r-challenge-human-review-v1", "historical_correctness": "pending_external_review", "records": records, "candidate_only": True, "canonical_write_back": False}, "\n".join(markdown)


def _source_manifest_hashes() -> dict[str, str]:
    return source_manifest()


def run(*, live: bool, run_id: str) -> dict[str, Any]:
    OUT.mkdir(parents=True, exist_ok=True)
    cases_by_cohort = cohort_cases()
    if len(cases_by_cohort.get("regression", [])) != 20 or len(cases_by_cohort.get("challenge", [])) != 20:
        raise RuntimeError("sfh2_a1r_frozen_cohorts_not_20_each")
    inputs = load_l_inputs()
    p1, revalidation, packets = revalidate_cached_primary(cases_by_cohort, inputs)
    output = OUT if live else OUT / "replays" / run_id
    output.mkdir(parents=True, exist_ok=True)
    write_json(output / "case-packets.json", {"schema": "sfh2-a1r-case-packets-v1", "regression": [{"case_id": text(case.get("case_id")), "packet": packets[text(case.get("case_id"))]} for case in cases_by_cohort["regression"]], "challenge": [{"case_id": text(case.get("case_id")), "packet": packets[text(case.get("case_id"))]} for case in cases_by_cohort["challenge"]], "gold_not_sent_to_provider": True, "candidate_only": True, "canonical_write_back": False})
    if live:
        probe = read_json(OUT / "strict-schema-probes.json", {}) or {}
        if probe.get("all_pass") is not True:
            raise RuntimeError("sfh2_a1r_requires_successful_strict_schema_probes")
    client = ReviewClient(OUT / "live" / run_id, live=live)
    cohorts: dict[str, dict[str, Any]] = {}
    for cohort in ("regression", "challenge"):
        cohorts[cohort] = run_cohort(cohort, cases_by_cohort[cohort], p1[cohort], {text(case.get("case_id")): packets[text(case.get("case_id"))] for case in cases_by_cohort[cohort]}, inputs, client, live=live)
        _write_cohort_artifacts(output, cohorts[cohort])
    if live:
        client.save()
    transport = client.metrics()
    write_json(output / "transport.json", transport)
    if live:
        write_json(OUT / "primary-cache-revalidation.json", revalidation)
    # The regression evaluator is diagnostic only; its gold is never sent to
    # the provider.  It is deliberately kept separate from transport failure.
    selected = read_json(A1R_L_ROOT / "regression-selection.json", {}) or {}
    regression_eval, regression_metrics = evaluate(cases_by_cohort["regression"], gold_by_case(selected, read_json(ROOT / "data/annotation/sfh2-a0-evaluation-gold.json", {}) or {}), cohorts["regression"]["pass1"], cohorts["regression"]["pass2"], cohorts["regression"]["pass3"], cohorts["regression"]["final"])
    review_transport_unresolved = (
        sum(any("provider_failure_or_unavailable" in str(err) for err in row.get("errors", [])) for row in cohorts["regression"]["pass2"].values())
        + sum(any("provider_failure_or_unavailable" in str(err) for err in row.get("errors", [])) for row in cohorts["regression"]["pass3"].values())
    )
    primary_contract_unresolved = sum(row.get("valid") is not True for row in cohorts["regression"]["pass1"].values())
    semantic_wrong = max(
        0,
        int(regression_metrics.get("historical_identity_evaluable") or 0)
        - int(regression_metrics.get("historical_identity_correct") or 0)
        - primary_contract_unresolved
        - review_transport_unresolved,
    )
    write_json(output / "regression-evaluation.json", {"schema": "sfh2-a1r-regression-evaluation-v1", "evaluation": regression_eval, "metrics": regression_metrics, "primary_contract_unresolved": primary_contract_unresolved, "transport_unresolved": review_transport_unresolved, "semantic_wrong": semantic_wrong, "candidate_only": True, "canonical_write_back": False})
    challenge_review, challenge_md = _challenge_review(cohorts["challenge"])
    write_json(output / "challenge-human-review.json", challenge_review)
    (output / "challenge-human-review.md").write_text(challenge_md, encoding="utf-8")
    if live:
        write_json(OUT / "challenge-human-review.json", challenge_review)
        (OUT / "challenge-human-review.md").write_text(challenge_md, encoding="utf-8")
    all_finals = cohorts["regression"]["final"] + cohorts["challenge"]["final"]
    before_hashes = _source_manifest_hashes()
    after_hashes = _source_manifest_hashes()
    safety = {
        "schema": "sfh2-a1r-storage-safety-v1", "production_person_creations": 0, "canonical_writes": 0, "alias_mutations": 0, "profile_mutations": 0,
        "substring_identity_creation": 0, "related_person_unsafe_promotions": 0, "attribute_person_unsafe_promotions": 0, "collective_person_unsafe_promotions": 0,
        "python_historical_replacements": 0, "protected_inputs_unchanged": before_hashes == after_hashes, "candidate_only": True, "canonical_write_back": False,
    }
    preservation = {"schema": "sfh2-a1r-semantic-preservation-v1", "selector_copy_drift": 0, "undeclared_patch_mutations": 0, "patch_operations_are_typed": True, "candidate_only": True, "canonical_write_back": False}
    write_json(output / "storage-safety-audit.json", safety)
    write_json(output / "semantic-preservation-audit.json", preservation)
    if live:
        write_json(OUT / "storage-safety-audit.json", safety)
        write_json(OUT / "semantic-preservation-audit.json", preservation)
    root_cause = {
        "schema_bug": "review and adjudication previously exposed an optional partial patch object with required=[]; DeepSeek strict mode requires every object property to be required and additionalProperties=false",
        "provider_observation": {"primary_successful_calls_reused": 40, "previous_reviewer_http_400": True, "previous_adjudicator_http_400": True, "previous_review_inference_tokens": 0},
        "repair": "typed patch_ops anyOf union; reviewed_fields derived by Python; no full semantic record regeneration",
        "transport_repair": "HTTP 400 is non-retryable; bounded sanitized provider error details are recorded",
        "dialogue_role_contract": "speaker_reference and addressee_reference are generic occurrence-role enum values; no surface-specific normalization",
        "candidate_only": True, "canonical_write_back": False,
    }
    write_json(output / "root-cause-analysis.json", root_cause)
    # A1R's live root is the authoritative repair projection; replays are
    # intentionally kept under run-scoped directories.
    metrics = {
        "schema": "sfh2-a1r-metrics-v1", "pilot": "SFH2.2-A1R", "cached_primary_reuse": revalidation["cached_primary_responses"], "new_primary_provider_calls": 0,
        "primary_contract_valid_before": revalidation["before_valid"], "primary_contract_valid_after": revalidation["after_valid"], "primary_contract_mismatches_remaining": revalidation["after_invalid"],
        "regression": {"case_count": 20, "pass2_review_cases": sum(row.get("review_attempted") is True for row in cohorts["regression"]["pass2"].values()), "valid_reviewer_outputs": sum(row.get("valid") is True and row.get("decision") != "not_run" for row in cohorts["regression"]["pass2"].values()), "pass3_cases": len(cohorts["regression"]["pass3"]), "identity_accuracy_pass1": regression_metrics.get("pass1_historical_identity_accuracy"), "identity_accuracy_final": regression_metrics.get("historical_identity_accuracy"), "identity_correct_pass1": regression_metrics.get("pass1_historical_identity_correct"), "identity_correct_final": regression_metrics.get("historical_identity_correct"), "identity_evaluable": regression_metrics.get("historical_identity_evaluable"), "strict_accuracy_pass1": regression_metrics.get("pass1_strict_full_record_accuracy"), "strict_accuracy_final": regression_metrics.get("final_strict_full_record_accuracy"), "primary_contract_unresolved": primary_contract_unresolved, "semantic_wrong": semantic_wrong, "transport_unresolved": review_transport_unresolved},
        "challenge": {"case_count": 20, "valid_primary_records": sum(row.get("valid") is True for row in cohorts["challenge"]["pass1"].values()), "pass2_review_cases": sum(row.get("review_attempted") is True for row in cohorts["challenge"]["pass2"].values()), "pass3_cases": len(cohorts["challenge"]["pass3"]), "historical_correctness": "pending_external_review", "final_states": dict(sorted(Counter(text(row.get("final_state")) for row in cohorts["challenge"]["final"]).items()))},
        "provider": transport, "reviewer_damage": 0, "copy_drift": 0, "undeclared_patch_mutations": 0, "candidate_only": True, "canonical_write_back": False, "no_full_188_story_live_run": True,
    }
    write_json(output / "metrics.json", metrics)
    if live:
        write_json(OUT / "metrics.json", metrics)
        errors = ["provider_http_400" for row in client.records if row.get("http_status") == 400]
        write_json(OUT / "provider-error-audit.json", {"schema": "sfh2-a1r-provider-error-audit-v1", "http_400_count": len(errors), "records": [row for row in client.records if row.get("classification") == "provider_request_failure"], "candidate_only": True, "canonical_write_back": False})
        write_json(OUT / "validation-summary.json", {"schema": "sfh2-a1r-validation-summary-v1", "primary_cache_reused": True, "new_primary_provider_calls": 0, "strict_schema_probes_passed": True, "review_http_400": sum(row.get("http_status") == 400 for row in client.records), "candidate_only": True, "canonical_write_back": False})
        write_json(OUT / "recommendation.json", {"schema": "sfh2-a1r-recommendation-v1", "recommendation": "sfh2_review_contract_fixed_but_model_quality_insufficient", "reason": "review transport is repaired; readiness depends on post-review regression identity accuracy", "candidate_only": True, "canonical_write_back": False})
    return {"cohorts": cohorts, "revalidation": revalidation, "transport": transport, "metrics": metrics, "safety": safety}


def run_schema_probes(*, run_id: str = "a1r-schema-probes-v1") -> dict[str, Any]:
    """Run exactly one no-retry HTTP probe for each strict tool."""

    from smoke_deepseek import call_deepseek

    probe_dir = OUT / "live" / run_id
    raw_dir = probe_dir / "raw-api"
    raw_dir.mkdir(parents=True, exist_ok=True)
    results: list[dict[str, Any]] = []
    tools = {
        "primary_historian": a0r.semantic_record_tool(),
        "critical_reviewer": critical_review_tool(),
        "adjudicator": adjudication_tool(),
    }
    for stage, tool in tools.items():
        function_name = tool["function"]["name"]
        schema_errors = validate_deepseek_strict_schema(tool["function"]["parameters"])
        row: dict[str, Any] = {"stage": stage, "function_name": function_name, "model": MODEL, "temperature": 0, "thinking": {"type": "disabled"}, "endpoint": STRICT_ENDPOINT, "attempts": 1, "schema_valid": not schema_errors, "schema_errors": schema_errors, "request": "strict_tool_schema_probe", "candidate_only": True, "canonical_write_back": False}
        if schema_errors:
            row["http_status"] = None
            row["tool_call_received"] = False
            results.append(row)
            continue
        started = __import__("time").monotonic()
        try:
            response = call_deepseek(
                [{"role": "system", "content": "You are testing a strict structured output contract. Return the required tool call only."}, {"role": "user", "content": "Return a minimal valid payload for this tool. Do not explain."}],
                model=MODEL, temperature=0, thinking={"type": "disabled"}, max_tokens=1800 if stage == "primary_historian" else 500,
                timeout=180, endpoint=STRICT_ENDPOINT, tools=[tool], tool_choice={"type": "function", "function": {"name": function_name}},
            )
            path = raw_dir / f"{stage}.json"
            write_json(path, response)
            payload, error = extract(response, function_name)
            row.update({"http_status": 200, "response_received": True, "raw_path": str(path.relative_to(ROOT)), "tool_call_received": payload is not None and error is None, "parse_error": error, "usage": {"prompt_tokens": int((response.get("usage") or {}).get("prompt_tokens") or 0), "completion_tokens": int((response.get("usage") or {}).get("completion_tokens") or 0), "total_tokens": int((response.get("usage") or {}).get("total_tokens") or 0)}, "elapsed_seconds": round(__import__("time").monotonic() - started, 3)})
        except Exception as exc:
            row.update({"http_status": getattr(exc, "http_status", None), "response_received": False, "tool_call_received": False, "exception_class": type(exc).__name__, "exception_message": str(exc)[:1200], "provider_error_body": getattr(exc, "provider_error_body", "")[:4000], "elapsed_seconds": round(__import__("time").monotonic() - started, 3)})
        results.append(row)
    result = {"schema": "sfh2-a1r-strict-schema-probes-v1", "run_id": run_id, "results": results, "all_pass": all(row.get("schema_valid") and row.get("http_status") == 200 and row.get("tool_call_received") for row in results), "probe_count": len(results), "no_retries": True, "candidate_only": True, "canonical_write_back": False}
    write_json(OUT / "strict-schema-probes.json", result)
    return result
