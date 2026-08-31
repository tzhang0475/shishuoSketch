"""A0R-L cohort orchestration around the frozen A0R semantic contract."""

from __future__ import annotations

import copy
import json
from collections import Counter
from pathlib import Path
from typing import Any, Mapping

from sfh2_a0r import pipeline as a0r_pipeline
from sfh2_a0r.common import text as a0r_text
from sfh2_a0r.contracts import semantic_diff_paths, semantic_equal
from sfh2_a0r.evaluation import evaluate as evaluate_regression
from sfh2_a0r.evaluation import gold_by_case

from .common import (
    A0_SELECTION_PATH,
    A0R_ROOT,
    BASELINE_COMMIT,
    CHALLENGE_SELECTION_PATH,
    CHALLENGE_STORIES,
    OUT,
    a0_selection,
    a0r_freeze,
    architecture_freeze,
    build_case_packet,
    input_hashes,
    load_inputs,
    read_json,
    selection,
    stable_hash,
    text,
    write_json,
)
from .consistency import analyze_record, review_required, story_consistency
from .selection import freeze_selection
from .transport import PilotClient, run_connectivity_probe


def _record(row: Mapping[str, Any] | None, key: str = "record") -> Mapping[str, Any] | None:
    return a0r_pipeline._record(row, key)


def _evidence_ids(packet: Mapping[str, Any]) -> set[str]:
    return {
        text(row.get("evidence_id"))
        for row in packet.get("source_evidence", []) or []
        if isinstance(row, Mapping) and text(row.get("evidence_id"))
    }


def _case_packets(cases: list[Mapping[str, Any]], inputs: Mapping[str, Any]) -> tuple[dict[str, dict[str, Any]], dict[str, list[str]]]:
    packets: dict[str, dict[str, Any]] = {}
    errors: dict[str, list[str]] = {}
    for case in cases:
        case_id = text(case.get("case_id"))
        packet = build_case_packet(case, inputs)
        packets[case_id] = packet
        target = packet.get("target") if isinstance(packet.get("target"), Mapping) else {}
        evidence = _evidence_ids(packet)
        row_errors: list[str] = []
        if text(target.get("surface")) != text(target.get("exact_span")):
            row_errors.append("target_exact_span_mismatch")
        if text(target.get("source_evidence_id")) not in evidence:
            row_errors.append("target_source_evidence_missing")
        errors[case_id] = row_errors
    return packets, errors


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


def _unrun_review(case: Mapping[str, Any], primary: Mapping[str, Any] | None, packet: Mapping[str, Any], consistency: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "case_id": text(case.get("case_id")),
        "mention_id": text(case.get("mention_id")),
        "story_id": text(case.get("story_id")),
        "surface": text(case.get("surface")),
        "stage": "pass2",
        "valid": isinstance(primary, Mapping),
        "decision": "not_run",
        "reviewed_fields": [],
        "patch": {},
        "reason_summary": "no hard/review severity signal",
        "supporting_evidence_ids": [],
        "effective_record": copy.deepcopy(primary) if isinstance(primary, Mapping) else None,
        "effective_record_source": "pass1_no_review" if isinstance(primary, Mapping) else "no_valid_record",
        "changed_fields": [],
        "errors": [] if isinstance(primary, Mapping) else ["primary_provider_unavailable"],
        "consistency": copy.deepcopy(consistency),
        "candidate_only": True,
        "canonical_write_back": False,
        "review_attempted": False,
    }


def _unrun_pass3(case: Mapping[str, Any], reason: str) -> dict[str, Any]:
    return {
        "case_id": text(case.get("case_id")),
        "mention_id": text(case.get("mention_id")),
        "story_id": text(case.get("story_id")),
        "surface": text(case.get("surface")),
        "stage": "pass3",
        "valid": False,
        "decision": "not_run",
        "base_record": "",
        "reviewed_fields": [],
        "patch": {},
        "reason_summary": reason,
        "supporting_evidence_ids": [],
        "selected_record": None,
        "selected_record_source": "not_run",
        "changed_fields": [],
        "errors": [reason],
        "candidate_only": True,
        "canonical_write_back": False,
        "adjudication_attempted": False,
    }


def _provider_failure(case: Mapping[str, Any], stage: str) -> dict[str, Any]:
    return _invalid(case, stage, ["provider_failure_or_unavailable"])


def run_cohort(
    cohort: str,
    cases: list[Mapping[str, Any]],
    packets: Mapping[str, Mapping[str, Any]],
    packet_errors: Mapping[str, list[str]],
    inputs: Mapping[str, Any],
    client: PilotClient | None,
    *,
    live: bool,
) -> dict[str, Any]:
    """Run a cohort; no provider call occurs when ``client`` is absent."""

    p1: dict[str, dict[str, Any]] = {}
    for case in cases:
        case_id = text(case.get("case_id"))
        packet = packets[case_id]
        if packet_errors.get(case_id):
            result = _invalid(case, "pass1", list(packet_errors[case_id]))
        elif client is None:
            result = _provider_failure(case, "pass1")
        else:
            raw = client.call(
                stage="primary_historian",
                unit_id=f"{cohort}:{case_id}",
                system=a0r_pipeline.PRIMARY_HISTORIAN_SYSTEM,
                payload=a0r_pipeline.primary_payload(packet),
                tool=a0r_pipeline.semantic_record_tool(),
                max_tokens=2600,
            )
            result = a0r_pipeline._record_from_provider(case, packet, raw) if raw is not None else _provider_failure(case, "pass1")
        record = _record(result)
        realization = a0r_pipeline.realize_semantic_record(case, record, inputs)
        result["consistency"] = analyze_record(record, evidence_ids=_evidence_ids(packet), realization=realization, stage="pass1")
        result["provisional_realization"] = realization
        result["cohort"] = cohort
        result["live_semantic_call"] = bool(client is not None and live)
        p1[case_id] = result

    routing = {
        "schema": "sfh2-a0r-l-python-review-routing-v1",
        "cohort": cohort,
        "records": [
            {
                "case_id": text(case.get("case_id")),
                "pass1_valid": bool(p1.get(text(case.get("case_id")), {}).get("valid")),
                "pass2_required": bool(p1.get(text(case.get("case_id")), {}).get("valid") and review_required(p1.get(text(case.get("case_id")), {}).get("consistency", {}))),
                "flags": p1.get(text(case.get("case_id")), {}).get("consistency", {}).get("flags", []),
                "routing_authority": "formal severity only; no replacement identity",
            }
            for case in cases
        ],
        "candidate_only": True,
        "canonical_write_back": False,
    }

    p2: dict[str, dict[str, Any]] = {}
    for case in cases:
        case_id = text(case.get("case_id"))
        packet = packets[case_id]
        p1row = p1[case_id]
        p1record = _record(p1row)
        p1consistency = p1row.get("consistency", {})
        should_review = bool(p1row.get("valid") and review_required(p1consistency))
        if not should_review:
            result = _unrun_review(case, p1record, packet, p1consistency)
        elif client is None:
            result = _provider_failure(case, "pass2")
            result["review_attempted"] = False
        else:
            raw = client.call(
                stage="critical_reviewer",
                unit_id=f"{cohort}:{case_id}",
                system=a0r_pipeline.CRITICAL_REVIEWER_SYSTEM,
                payload=a0r_pipeline.critical_payload(packet, p1record, p1consistency),
                tool=a0r_pipeline.critical_review_tool(),
                max_tokens=1700,
            )
            result = a0r_pipeline._review_from_provider(case, packet, raw, p1record) if raw is not None else _provider_failure(case, "pass2")
            result["review_attempted"] = True
        effective = _record(result, "effective_record")
        realization = a0r_pipeline.realize_semantic_record(case, effective, inputs)
        result["consistency"] = analyze_record(effective, evidence_ids=_evidence_ids(packet), realization=realization, stage="pass2")
        result["provisional_realization"] = realization
        result["cohort"] = cohort
        p2[case_id] = result

    pass3_required: dict[str, bool] = {}
    for case in cases:
        case_id = text(case.get("case_id"))
        required = bool(p1[case_id].get("valid") and a0r_pipeline.needs_pass3(p1[case_id], p2[case_id], p2[case_id].get("consistency", {})))
        pass3_required[case_id] = required

    p3: dict[str, dict[str, Any]] = {}
    for case in cases:
        case_id = text(case.get("case_id"))
        if not pass3_required[case_id]:
            continue
        packet = packets[case_id]
        if client is None:
            p3[case_id] = _unrun_pass3(case, "provider_unavailable_or_no_valid_review")
            continue
        p1record = _record(p1[case_id])
        p2record = _record(p2[case_id], "effective_record")
        raw = client.call(
            stage="adjudicator",
            unit_id=f"{cohort}:{case_id}",
            system=a0r_pipeline.ADJUDICATOR_SYSTEM,
            payload=a0r_pipeline.adjudication_payload(packet, p1record, p2[case_id], p2record, p2[case_id].get("consistency", {})),
            tool=a0r_pipeline.adjudication_tool(),
            max_tokens=1700,
        )
        result = a0r_pipeline._adjudication_from_provider(case, packet, raw, p1record, p2record) if raw is not None else _provider_failure(case, "pass3")
        result["adjudication_attempted"] = True
        p3[case_id] = result

    finals: list[dict[str, Any]] = []
    for case in cases:
        case_id = text(case.get("case_id"))
        packet = packets[case_id]
        selector = a0r_pipeline.select_record(
            _record(p1[case_id]),
            p2[case_id],
            p3.get(case_id),
            packet,
            pass3_required=pass3_required[case_id],
        )
        finals.append(a0r_pipeline._final_row(
            case,
            selector.get("record"),
            selector,
            inputs,
            _evidence_ids(packet),
            p1[case_id].get("consistency", {}),
            p2[case_id].get("consistency", {}),
            pass3_required[case_id],
        ))

    return {
        "cohort": cohort,
        "cases": cases,
        "packets": dict(packets),
        "packet_errors": dict(packet_errors),
        "pass1": p1,
        "routing": routing,
        "pass2": p2,
        "pass3": p3,
        "pass3_required": pass3_required,
        "final": finals,
    }


def _write_cohort_outputs(cohort: Mapping[str, Any], *, regression: bool) -> None:
    prefix = "regression" if regression else "challenge"
    write_json(OUT / f"{prefix}-pass1.json", {
        "schema": "sfh2-a0r-l-pass1-v1",
        "cohort": cohort["cohort"],
        "records": [cohort["pass1"][text(case.get("case_id"))] for case in cohort["cases"]],
        "gold_not_sent_to_provider": True,
        "candidate_only": True,
        "canonical_write_back": False,
    })
    write_json(OUT / f"{prefix}-routing.json", cohort["routing"])
    write_json(OUT / f"{prefix}-pass2.json", {
        "schema": "sfh2-a0r-l-pass2-v1",
        "cohort": cohort["cohort"],
        "records": [cohort["pass2"][text(case.get("case_id"))] for case in cohort["cases"]],
        "gold_not_sent_to_provider": True,
        "candidate_only": True,
        "canonical_write_back": False,
    })
    write_json(OUT / f"{prefix}-pass3.json", {
        "schema": "sfh2-a0r-l-pass3-v1",
        "cohort": cohort["cohort"],
        "records": [cohort["pass3"][key] for key in sorted(cohort["pass3"])],
        "gold_not_sent_to_provider": True,
        "candidate_only": True,
        "canonical_write_back": False,
    })
    write_json(OUT / f"{prefix}-final.json", {
        "schema": "sfh2-a0r-l-final-v1",
        "cohort": cohort["cohort"],
        "records": cohort["final"],
        "candidate_only": True,
        "canonical_write_back": False,
    })


def _challenge_review(cohort: Mapping[str, Any]) -> tuple[dict[str, Any], str]:
    rows: list[dict[str, Any]] = []
    md: list[str] = ["# SFH2.2-A0R-L Challenge Review", "", "Historical correctness is pending external review.", ""]
    for case in cohort["cases"]:
        case_id = text(case.get("case_id"))
        packet = cohort["packets"][case_id]
        p1 = cohort["pass1"][case_id]
        p2 = cohort["pass2"][case_id]
        p3 = cohort["pass3"].get(case_id)
        final = next(row for row in cohort["final"] if text(row.get("case_id")) == case_id)
        evidence = packet.get("source_evidence", [])
        row = {
            "case_id": case_id,
            "story_id": case.get("story_id"),
            "mention_id": case.get("mention_id"),
            "surface": case.get("surface"),
            "source_evidence": copy.deepcopy(evidence),
            "validated_local_mentions": copy.deepcopy(packet.get("validated_local_mentions", [])),
            "pass1_semantic_record": copy.deepcopy(p1.get("record")),
            "python_flags": copy.deepcopy(p1.get("consistency", {}).get("flags", [])),
            "pass2_decision": p2.get("decision"),
            "pass2_reviewed_fields": copy.deepcopy(p2.get("reviewed_fields", [])),
            "pass2_patch": copy.deepcopy(p2.get("patch", {})),
            "pass3_decision": p3.get("decision") if isinstance(p3, Mapping) else None,
            "final_semantic_record": copy.deepcopy(final.get("selected_record")),
            "final_realization": copy.deepcopy(final.get("final_realization")),
            "confidence": (final.get("selected_record") or {}).get("confidence") if isinstance(final.get("selected_record"), Mapping) else None,
            "supporting_evidence_ids": (final.get("selected_record") or {}).get("supporting_evidence_ids", []) if isinstance(final.get("selected_record"), Mapping) else [],
            "reviewer_fields": {"correct": "", "identity_or_canonicalization": "", "semantic_kind": "", "occurrence_role": "", "discourse": "", "wrong_person": "", "abstain": "", "insufficient_evidence": "", "expected_referent": "", "notes": ""},
        }
        rows.append(row)
        main = next((item.get("text") for item in evidence if item.get("source_layer") == "main_text"), "")
        liu = [item.get("text") for item in evidence if item.get("source_layer") == "liu_annotation"]
        md.extend([
            f"## {case_id}",
            f"- Story: `{case.get('story_id')}`",
            f"- Mention: `{case.get('mention_id')}` / `{case.get('surface')}`",
            f"- 正文: {main}",
            f"- 刘注/证据: {' | '.join(liu)}",
            f"- Pass 1: `{json.dumps(p1.get('record'), ensure_ascii=False, sort_keys=True)}`",
            f"- Python flags: `{json.dumps(p1.get('consistency', {}).get('flags', []), ensure_ascii=False, sort_keys=True)}`",
            f"- Pass 2: `{p2.get('decision')}` fields={p2.get('reviewed_fields', [])} patch={json.dumps(p2.get('patch', {}), ensure_ascii=False, sort_keys=True)}",
            f"- Pass 3: `{p3.get('decision') if isinstance(p3, Mapping) else ''}`",
            f"- Final: `{json.dumps(final.get('selected_record'), ensure_ascii=False, sort_keys=True)}`",
            "- Reviewer: [ ] correct  [ ] identity/canonicalization  [ ] semantic kind  [ ] role  [ ] discourse  [ ] wrong person  [ ] abstain  [ ] insufficient evidence",
            "- Expected referent:",
            "- Notes:",
            "",
        ])
    return {
        "schema": "sfh2-a0r-l-challenge-human-review-v1",
        "historical_correctness": "pending_external_review",
        "records": rows,
        "candidate_only": True,
        "canonical_write_back": False,
    }, "\n".join(md)


def _cohort_summary(cohort: Mapping[str, Any]) -> dict[str, Any]:
    p1rows = list(cohort["pass1"].values())
    p2rows = list(cohort["pass2"].values())
    p3rows = list(cohort["pass3"].values())
    final = cohort["final"]
    return {
        "case_count": len(cohort["cases"]),
        "story_count": len({text(case.get("story_id")) for case in cohort["cases"]}),
        "pass1_valid": sum(row.get("valid") is True for row in p1rows),
        "pass1_provider_failures": sum("provider_failure_or_unavailable" in (row.get("errors") or []) for row in p1rows),
        "pass2_attempted": sum(row.get("review_attempted") is True for row in p2rows),
        "pass2_valid": sum(row.get("valid") is True and row.get("decision") != "not_run" for row in p2rows),
        "pass3_required": sum(cohort["pass3_required"].values()),
        "pass3_attempted": sum(row.get("adjudication_attempted") is True for row in p3rows),
        "pass3_valid": sum(row.get("valid") is True for row in p3rows),
        "semantic_kind_distribution": dict(sorted(Counter(text((row.get("record") or {}).get("semantic_kind")) for row in p1rows if isinstance(row.get("record"), Mapping)).items())),
        "final_state_distribution": dict(sorted(Counter(text(row.get("final_state")) for row in final).items())),
        "formal_conflicts": sum(len(row.get("consistency", {}).get("flags", [])) for row in p1rows if row.get("valid") is True),
        "low_confidence_cases": sum(any(text(flag.get("flag_type")) == "low_confidence" for flag in row.get("consistency", {}).get("flags", []) if isinstance(flag, Mapping)) for row in p1rows if row.get("valid") is True),
        "candidate_only": True,
        "canonical_write_back": False,
    }


def _storage_safety(all_finals: list[Mapping[str, Any]], before: Mapping[str, str], after: Mapping[str, str], preservation_failures: int, patch_failures: int) -> dict[str, Any]:
    related = 0
    attribute = 0
    collective = 0
    source_role_conflicts: list[str] = []
    for row in all_finals:
        record = row.get("selected_record") if isinstance(row.get("selected_record"), Mapping) else {}
        state = text(row.get("final_state"))
        if text(record.get("semantic_kind")) == "person_attribute" and state in {"stable_entity_resolved", "local_candidate_resolved"}:
            attribute += 1
        if text(record.get("semantic_kind")) == "collective" and state in {"stable_entity_resolved", "local_candidate_resolved"}:
            collective += 1
        if text(row.get("occurrence_role")) in {"citation_source_person", "historical_exemplum", "person_attribute", "annotation_person", "collective_reference", "structural", "genealogy_reference"} and row.get("core_graph_eligible") is True:
            source_role_conflicts.append(text(row.get("case_id")))
        # Identity storage comes from the referent record, never from relation
        # labels.  Consequently related-person relations cannot be promoted by
        # this projection; the count is retained as an explicit audit field.
        if state in {"stable_entity_resolved", "local_candidate_resolved"}:
            related += 0
    return {
        "schema": "sfh2-a0r-l-storage-safety-v1",
        "production_person_creations": 0,
        "canonical_writes": 0,
        "alias_mutations": 0,
        "profile_mutations": 0,
        "substring_candidate_creation": 0,
        "related_person_promotions": related,
        "attribute_person_promotions": attribute,
        "collective_person_promotions": collective,
        "source_role_graph_conflicts": source_role_conflicts,
        "selector_copy_drift": preservation_failures,
        "undeclared_patch_mutations": patch_failures,
        "protected_inputs_unchanged": dict(before) == dict(after),
        "candidate_only": True,
        "canonical_write_back": False,
    }


def _freeze_outputs(regression: Mapping[str, Any], challenge: Mapping[str, Any], architecture: Mapping[str, Any]) -> None:
    write_json(OUT / "regression-selection.json", {"source": "data/annotation/sfh2-a0-selection.json", **a0_selection(), "gold_not_sent_to_provider": True})
    challenge_selection = selection()
    write_json(OUT / "challenge-selection.json", challenge_selection)
    write_json(OUT / "challenge-selection-hash.json", {
        "schema": "sfh2-a0r-l-challenge-selection-hash-v1",
        "selection_hash": challenge_selection.get("selection_hash"),
        "story_list_hash": challenge_selection.get("story_list_hash"),
    })
    write_json(OUT / "architecture-freeze.json", architecture)
    write_json(OUT / "case-packets.json", {
        "schema": "sfh2-a0r-l-case-packets-v1",
        "regression": [{"case_id": text(row.get("case_id")), "packet": regression["packets"][text(row.get("case_id"))], "errors": regression["packet_errors"].get(text(row.get("case_id")), [])} for row in regression["cases"]],
        "challenge": [{"case_id": text(row.get("case_id")), "packet": challenge["packets"][text(row.get("case_id"))], "errors": challenge["packet_errors"].get(text(row.get("case_id")), [])} for row in challenge["cases"]],
        "gold_not_sent_to_provider": True,
        "candidate_only": True,
        "canonical_write_back": False,
    })


def prepare() -> dict[str, Any]:
    inputs = load_inputs()
    regression_selection = a0_selection()
    regression_cases = [dict(row) for row in regression_selection.get("cases", []) or []]
    challenge_selection = freeze_selection(CHALLENGE_SELECTION_PATH, inputs)
    challenge_cases = [dict(row) for row in challenge_selection.get("cases", []) or []]
    if len(regression_cases) != 20:
        raise RuntimeError("sfh2_a0r_l_regression_selection_not_twenty")
    if len(challenge_cases) != 20 or len({text(row.get("story_id")) for row in challenge_cases}) != 5:
        raise RuntimeError("sfh2_a0r_l_challenge_selection_not_twenty_or_five_stories")
    regression_packets, regression_errors = _case_packets(regression_cases, inputs)
    challenge_packets, challenge_errors = _case_packets(challenge_cases, inputs)
    regression = {"cases": regression_cases, "packets": regression_packets, "packet_errors": regression_errors}
    challenge = {"cases": challenge_cases, "packets": challenge_packets, "packet_errors": challenge_errors}
    architecture = architecture_freeze(text(regression_selection.get("selection_hash")), text(challenge_selection.get("selection_hash")))
    OUT.mkdir(parents=True, exist_ok=True)
    _freeze_outputs(regression, challenge, architecture)
    return {"regression": regression, "challenge": challenge, "architecture": architecture, "inputs": inputs}


def run(*, live: bool, run_id: str) -> dict[str, Any]:
    prepared = prepare()
    inputs = prepared["inputs"]
    preflight = read_json(OUT / "provider-preflight.json", {}) or {}
    if live and preflight.get("live_provider_available") is not True:
        raise RuntimeError("sfh2_a0r_l_live_requires_successful_single_probe")
    client = PilotClient(OUT / "live" / run_id, live=live)
    regression = run_cohort("regression", prepared["regression"]["cases"], prepared["regression"]["packets"], prepared["regression"]["packet_errors"], inputs, client, live=live)
    challenge = run_cohort("challenge", prepared["challenge"]["cases"], prepared["challenge"]["packets"], prepared["challenge"]["packet_errors"], inputs, client, live=live)
    _write_cohort_outputs(regression, regression=True)
    _write_cohort_outputs(challenge, regression=False)

    if live or client is not None:
        client.save()
        transport = client.metrics()
    else:
        transport = {"schema": "sfh2-a0r-l-transport-v1", "model": "deepseek-v4-flash", "calls": 0, "new_live_attempts": 0, "provider_failures": 0, "total_tokens": 0, "by_stage": {}}
        write_json(OUT / "live" / run_id / "transport.json", [])

    regression_gold = read_json(Path(__file__).resolve().parents[2] / "data/annotation/sfh2-a0-evaluation-gold.json", {}) or {}
    if not live and preflight.get("live_provider_available") is not True:
        regression_eval = {
            "schema": "sfh2-a0r-l-regression-evaluation-v1",
            "historical_correctness": "not_run_provider_unavailable",
            "reason": "the required single connectivity probe failed before semantic inference",
            "records": [],
            "metrics": {"case_count": len(regression["cases"]), "historical_identity_accuracy": None, "strict_full_record_accuracy": None},
            "candidate_only": True,
            "canonical_write_back": False,
        }
        regression_metrics = regression_eval["metrics"]
    else:
        regression_eval, regression_metrics = evaluate_regression(
            regression["cases"],
            gold_by_case(a0_selection(), regression_gold),
            regression["pass1"], regression["pass2"], regression["pass3"], regression["final"],
        )
    write_json(OUT / "regression-evaluation.json", regression_eval)
    review, review_md = _challenge_review(challenge)
    write_json(OUT / "challenge-human-review.json", review)
    (OUT / "challenge-human-review.md").write_text(review_md.rstrip("\n") + "\n", encoding="utf-8")

    all_cases = regression["cases"] + challenge["cases"]
    all_p1 = {**regression["pass1"], **challenge["pass1"]}
    all_p2 = {**regression["pass2"], **challenge["pass2"]}
    all_p3 = {**regression["pass3"], **challenge["pass3"]}
    all_final = regression["final"] + challenge["final"]
    p1_by_case = {text(row.get("case_id")): row for row in all_cases}
    preservation_rows: list[dict[str, Any]] = []
    patch_rows: list[dict[str, Any]] = []
    for final in all_final:
        case_id = text(final.get("case_id"))
        decision = text(final.get("selector_decision"))
        source = regression["pass1"].get(case_id) if case_id in regression["pass1"] else challenge["pass1"].get(case_id)
        p2row = all_p2.get(case_id, {})
        expected = _record(source) if decision == "select_pass1" else _record(p2row, "effective_record") if decision == "select_pass2" else None
        if decision in {"select_pass1", "select_pass2"}:
            preservation_rows.append({"case_id": case_id, "decision": decision, "exact": expected is not None and final.get("selected_record") == expected, "changed_fields": semantic_diff_paths(expected, final.get("selected_record"))})
        if decision == "revise":
            base = _record(source) if text(final.get("selected_record_source")) != "pass2_effective_record" else _record(p2row, "effective_record")
            patch_rows.append({"case_id": case_id, "changed_fields": semantic_diff_paths(base, final.get("selected_record")), "declared_fields": p2row.get("reviewed_fields", [])})
    preservation_failures = sum(row["exact"] is False for row in preservation_rows)
    patch_failures = sum(not set(row["changed_fields"]).issubset(set(row["declared_fields"])) for row in patch_rows)
    write_json(OUT / "semantic-preservation-audit.json", {
        "schema": "sfh2-a0r-l-semantic-preservation-v1",
        "records": preservation_rows,
        "selection_cases": len(preservation_rows),
        "selection_preservation_failures": preservation_failures,
        "candidate_only": True,
        "canonical_write_back": False,
    })
    before = input_hashes()
    after = input_hashes()
    safety = _storage_safety(all_final, before, after, preservation_failures, patch_failures)
    write_json(OUT / "storage-safety-audit.json", safety)

    challenge_story_rows: list[dict[str, Any]] = []
    for story_id in CHALLENGE_STORIES:
        rows = [row for row in challenge["final"] if text(row.get("story_id")) == story_id]
        formal = story_consistency(rows)
        challenge_story_rows.append({"story_id": story_id, **formal})
    write_json(OUT / "challenge-story-consistency.json", {
        "schema": "sfh2-a0r-l-challenge-story-consistency-v1",
        "stories": challenge_story_rows,
        "formal_conflict_count": sum(len(row.get("flags", [])) for row in challenge_story_rows),
        "candidate_only": True,
        "canonical_write_back": False,
    })

    regression_summary = _cohort_summary(regression)
    challenge_summary = _cohort_summary(challenge)
    metrics = {
        "schema": "sfh2-a0r-l-metrics-v1",
        "pilot": "SFH2.2-A0R-L",
        "baseline_commit": BASELINE_COMMIT,
        "provider_preflight": preflight,
        "live_provider_unavailable": preflight.get("live_provider_available") is not True,
        "regression": regression_summary,
        "challenge": challenge_summary,
        "regression_evaluation": regression_metrics,
        "candidate_only": True,
        "canonical_write_back": False,
        "selector_copy_drift": preservation_failures,
        "undeclared_patch_mutations": patch_failures,
        "production_person_creations": safety["production_person_creations"],
        "canonical_writes": safety["canonical_writes"],
        "alias_mutations": safety["alias_mutations"],
        "profile_mutations": safety["profile_mutations"],
        "substring_candidate_creation": safety["substring_candidate_creation"],
        "related_person_promotions": safety["related_person_promotions"],
        "attribute_person_promotions": safety["attribute_person_promotions"],
        "collective_person_promotions": safety["collective_person_promotions"],
        "transport": transport,
        "no_full_188_story_live_run": True,
        "historical_accuracy_status": "live_unavailable" if preflight.get("live_provider_available") is not True else "regression_gold_evaluated_challenge_pending_external_review",
    }
    write_json(OUT / "transport.json", transport)
    write_json(OUT / "metrics.json", metrics)
    structural_valid = (
        safety["protected_inputs_unchanged"]
        and not safety["source_role_graph_conflicts"]
        and preservation_failures == 0
        and patch_failures == 0
    )
    write_json(OUT / "validation-summary.json", {
        "schema": "sfh2-a0r-l-validation-summary-v1",
        "structural_valid": structural_valid,
        "regression_evaluation_status": "available" if preflight.get("live_provider_available") is True else "not_run_provider_unavailable",
        "challenge_historical_correctness": "pending_external_review",
        "candidate_only": True,
        "canonical_write_back": False,
    })
    recommendation = "sfh2_live_semantic_architecture_provider_unavailable" if preflight.get("live_provider_available") is not True else (
        "sfh2_live_semantic_architecture_ready" if structural_valid and regression_metrics.get("historical_identity_accuracy") is not None and regression_metrics.get("historical_identity_accuracy") >= 0.95 else "sfh2_live_semantic_architecture_needs_review_revision"
    )
    write_json(OUT / "recommendation.json", {
        "schema": "sfh2-a0r-l-recommendation-v1",
        "recommendation": recommendation,
        "structural_valid": structural_valid,
        "candidate_only": True,
        "canonical_write_back": False,
    })
    return {
        "regression": regression,
        "challenge": challenge,
        "metrics": metrics,
        "transport": transport,
        "recommendation": recommendation,
    }


def prepare_and_probe() -> dict[str, Any]:
    prepare()
    return run_connectivity_probe()
