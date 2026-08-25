#!/usr/bin/env python3
"""Build deterministic HDB2-P2T candidate projections from a frozen run."""

from __future__ import annotations

import collections
import hashlib
import json
import statistics
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import build_hng0_2 as hng02  # noqa: E402
import hdb2_occurrence_common as occurrence  # noqa: E402
import hdb2_p2t_common as common  # noqa: E402


def _hdb1() -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    aggregate = common.read_json(common.DERIVED / "hdb1-cross-wave-candidate-historical-db.json", {}) or {}
    return [dict(x) for x in aggregate.get("identity_observations", [])], [dict(x) for x in aggregate.get("relation_observations", [])]


def _cases_and_results(run_dir: Path, cases_path: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    cases_doc = common.read_json(cases_path, {}) or {}
    cases_by_id = {str(x.get("occurrence_id")): dict(x) for x in cases_doc.get("cases", [])}
    result_doc = common.read_json(run_dir / "python-decisions.json", {}) or {}
    results_by_id = {str(x.get("occurrence_id")): dict(x) for x in result_doc.get("records", [])}
    selection = common.read_json(common.ANNOTATION / "hdb2-p2t-occurrence-selection.json", {}) or {}
    ordered_cases = [cases_by_id[str(x.get("occurrence_id"))] for x in selection.get("cases", [])]
    ordered_results = [results_by_id.get(str(case.get("occurrence_id")), {}) for case in ordered_cases]
    return ordered_cases, ordered_results, cases_doc


def _candidate(case: Mapping[str, Any], result: Mapping[str, Any]) -> Mapping[str, Any] | None:
    key = str(result.get("candidate_key") or "")
    return next((row for row in case.get("candidates", []) if str(row.get("candidate_key")) == key), None)


def _explicit_expected_pids(case: Mapping[str, Any]) -> set[str]:
    """Conservative post-run diagnostic from visible full catalogue forms."""
    if str(case.get("occurrence_type")) in {"kinship_compositional_reference", "ruler_reference", "office_reference", "title_reference"}:
        return set()
    text = common.matching("\n".join([str(case.get("local_story_context") or ""), *[str(x or "") for x in case.get("annotation_context", [])]]))
    found: set[str] = set()
    for candidate in case.get("candidates", []):
        pid = str(candidate.get("person_id") or "")
        if not pid:
            continue
        forms = [candidate.get("display_name"), *(candidate.get("aliases") or [])]
        if any(len(common.matching(form)) >= 2 and common.matching(form) in text for form in forms if form):
            found.add(pid)
    return found


def _endpoint_after(row: Mapping[str, Any], final_by_identity: Mapping[str, Mapping[str, Any]]) -> tuple[str | None, str | None]:
    values: list[str | None] = []
    for side in ("subject", "object"):
        pid = str(row.get(f"{side}_person_id") or "") or None
        if not pid and str(row.get(f"{side}_ref") or "").startswith("unresolved:"):
            identity_id = str(row.get(f"{side}_ref")).split(":", 1)[1]
            result = final_by_identity.get(identity_id, {})
            if result.get("status") in {"explicit_resolved", "contextually_resolved"}:
                pid = str(result.get("resolved_person_id") or "") or None
        values.append(pid)
    return values[0], values[1]


def build_unblocked(cases: Sequence[Mapping[str, Any]], results: Sequence[Mapping[str, Any]], relations: Sequence[Mapping[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, int]]:
    final_by_identity = {str(case.get("identity_observation_id")): result for case, result in zip(cases, results)}
    before = collections.Counter()
    after = collections.Counter()
    unblocked: list[dict[str, Any]] = []
    for row in relations:
        unresolved_ids = [str(row.get("subject_ref")).split(":", 1)[1]] if str(row.get("subject_ref", "")).startswith("unresolved:") else []
        if str(row.get("object_ref", "")).startswith("unresolved:"):
            unresolved_ids.append(str(row.get("object_ref")).split(":", 1)[1])
        if not unresolved_ids or not any(identity_id in final_by_identity for identity_id in unresolved_ids):
            continue
        relation_class = str(row.get("relation_class") or "other")
        before[relation_class] += 1
        subject_pid, object_pid = _endpoint_after(row, final_by_identity)
        if subject_pid and object_pid and subject_pid != object_pid:
            after[relation_class] += 1
            support = [
                {"identity_observation_id": identity_id, "occurrence_decision": final_by_identity[identity_id]}
                for identity_id in unresolved_ids
                if identity_id in final_by_identity
            ]
            unblocked.append({
                "candidate_id": row.get("candidate_id"),
                "original_wave": row.get("wave_id"),
                "original_observation": row,
                "status": "newly_unblocked_candidate_fact",
                "endpoint_before": {"subject_person_id": row.get("subject_person_id"), "object_person_id": row.get("object_person_id")},
                "endpoint_after": {"subject_person_id": subject_pid, "object_person_id": object_pid},
                "identity_support": support,
                "candidate_only": True,
                "canonical_write_back": False,
            })
    unblocked.sort(key=lambda row: str(row.get("candidate_id")))
    return unblocked, {"before": sum(before.values()), "after": sum(after.values()), "before_kinship": before.get("kinship", 0), "after_kinship": after.get("kinship", 0), "before_marriage": before.get("marriage", 0), "after_marriage": after.get("marriage", 0), "before_relation": sum(before.values()) - before.get("kinship", 0) - before.get("marriage", 0), "after_relation": sum(after.values()) - after.get("kinship", 0) - after.get("marriage", 0)}


def build_knowledge_deltas(cases: Sequence[Mapping[str, Any]], results: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    catalog = hng02.person_catalog()
    by_person: dict[str, dict[str, Any]] = {}
    for case, result in zip(cases, results):
        pid = str(result.get("resolved_person_id") or "")
        if not pid or result.get("status") not in {"explicit_resolved", "contextually_resolved"}:
            continue
        candidate = _candidate(case, result) or {}
        person = catalog.get(pid, {})
        item = by_person.setdefault(pid, {
            "person_id": pid,
            "identity_gain": {"aliases": [], "titles": [], "courtesy_names": [], "occurrence_ids": []},
            "family_gain": {"kinship_candidates": [], "marriage_candidates": []},
            "office_gain": {"office_candidates": []},
            "temporal_gain": {"activity_evidence": [], "story_temporal_links": []},
            "social_gain": {"relation_candidates": [], "story_participation": []},
            "evidence_gain": {"source_works": [], "evidence_refs": []},
            "candidate_only": True,
            "canonical_write_back": False,
        })
        item["identity_gain"]["occurrence_ids"].append(case.get("occurrence_id"))
        for alias in candidate.get("aliases", []):
            if alias and alias != person.get("canonical_name"):
                item["identity_gain"]["aliases"].append(alias)
                if alias in (person.get("courtesy_forms") or []):
                    item["identity_gain"]["courtesy_names"].append(alias)
        for title in candidate.get("titles", []):
            item["identity_gain"]["titles"].append(title)
        for rel in case.get("local_relations", []):
            relation_class = str(rel.get("relation_class") or "")
            if relation_class == "kinship":
                item["family_gain"]["kinship_candidates"].append(rel)
            elif relation_class == "marriage":
                item["family_gain"]["marriage_candidates"].append(rel)
            elif relation_class == "institutional":
                item["office_gain"]["office_candidates"].append(rel)
            elif relation_class:
                item["social_gain"]["relation_candidates"].append(rel)
        item["social_gain"]["story_participation"].append({"story_id": case.get("story_id"), "surface": case.get("target_surface")})
        item["temporal_gain"]["story_temporal_links"].extend(case.get("story_temporal_context", []))
        for evidence in case.get("evidence_items", []):
            item["evidence_gain"]["evidence_refs"].append(evidence.get("source_ref"))
            item["evidence_gain"]["source_works"].append(evidence.get("source_work"))
    for item in by_person.values():
        for group in ("identity_gain", "family_gain", "office_gain", "temporal_gain", "social_gain", "evidence_gain"):
            for key, value in item[group].items():
                if isinstance(value, list):
                    seen: set[str] = set()
                    dedup: list[Any] = []
                    for row in sorted(value, key=lambda x: json.dumps(x, ensure_ascii=False, sort_keys=True)):
                        marker = json.dumps(row, ensure_ascii=False, sort_keys=True)
                        if marker not in seen:
                            seen.add(marker)
                            dedup.append(row)
                    item[group][key] = dedup
    return sorted(by_person.values(), key=lambda row: str(row.get("person_id")))


def build_review_queue(cases: Sequence[Mapping[str, Any]], results: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for case, result in zip(cases, results):
        if result.get("status") in {"explicit_resolved", "ruler_reference", "office_reference", "not_person"} and not result.get("hard_constraint_rejections"):
            continue
        priority = "P1" if result.get("status") in {"conflict", "contextually_preferred"} or case.get("blocked_marriage_count", 0) or case.get("blocked_kinship_count", 0) else "P2"
        rows.append({"review_id": f"hdb2-p2t-review-{common.stable_hash(case.get('occurrence_id'))[:20]}", "priority": priority, "occurrence_id": case.get("occurrence_id"), "story_id": case.get("story_id"), "surface": case.get("target_surface"), "decision": result, "candidate_only": True, "canonical_write_back": False})
    return sorted(rows, key=lambda row: (str(row.get("priority")), str(row.get("review_id"))))


def build_metrics(cases: Sequence[Mapping[str, Any]], results: Sequence[Mapping[str, Any]], model_records: Sequence[Mapping[str, Any]], unblocked: Sequence[Mapping[str, Any]], endpoint_counts: Mapping[str, int], p1_metrics: Mapping[str, Any]) -> dict[str, Any]:
    status_counts = collections.Counter(str(row.get("status")) for row in results)
    cascade_counts = collections.Counter(str(row.get("cascade_stage")) for row in results)
    valid_model = [row for row in model_records if row.get("llm_called")]
    parsed = [row for row in valid_model if row.get("classification") == "parsed"]
    elapsed = [float(row.get("elapsed_seconds")) for row in valid_model if row.get("elapsed_seconds") is not None]
    usages = [row.get("usage", {}) for row in valid_model if isinstance(row.get("usage"), Mapping)]
    invalid_errors = collections.Counter(error for row in model_records for error in (row.get("validation") or {}).get("errors", []) if isinstance(row.get("validation"), Mapping))
    known_wrong = 0
    known_correct = 0
    known_unresolved = 0
    nonperson = 0
    for case, result in zip(cases, results):
        expected = _explicit_expected_pids(case)
        resolved = str(result.get("resolved_person_id") or "")
        if len(expected) == 1:
            if resolved == next(iter(expected)):
                known_correct += 1
            elif resolved:
                known_wrong += 1
            else:
                known_unresolved += 1
        if str(case.get("occurrence_type")) == "generic_or_non_person_reference" and resolved:
            nonperson += 1
    return {
        "schema": "hdb2-p2t-metrics-v1",
        "occurrence_count": len(cases),
        "semantic_type_distribution": dict(collections.Counter(str(case.get("occurrence_type")) for case in cases)),
        "selection_category_distribution": dict(collections.Counter(str(case.get("selection_category")) for case in cases)),
        "cascade": {
            "python_explicit_resolved": cascade_counts.get("python_explicit", 0),
            "python_structural_handled": cascade_counts.get("python_structural", 0),
            "sent_to_llm": cascade_counts.get("llm_contextual", 0),
            "no_llm_resolution_rate": round(sum(not row.get("llm_called") and row.get("status") not in {"unresolved", "conflict"} for row in results) / len(cases), 4) if cases else 0,
        },
        "final_states": dict(status_counts),
        "safety": {
            "known_wrong_identity_promotions": known_wrong,
            "known_reference_correct": known_correct,
            "known_reference_unresolved": known_unresolved,
            "invalid_candidate_keys": invalid_errors.get("candidate_key_invalid", 0) + invalid_errors.get("candidate_key_must_be_null_outside_candidate", 0),
            "invalid_evidence_references": invalid_errors.get("evidence_reference_invalid", 0),
            "hard_constraint_rejections": sum(bool(row.get("hard_constraint_rejections")) for row in results),
            "base_person_compositional_collapses": sum(bool(row.get("resolved_person_id")) for case, row in zip(cases, results) if case.get("occurrence_type") == "kinship_compositional_reference"),
            "nonperson_person_id_anomalies": nonperson,
            "self_relation_collapses": 0,
            "same_surface_automatic_merges": 0,
        },
        "llm": {
            "contextual_calls": len(valid_model),
            "valid_payloads": len(parsed),
            "invalid_payloads": len(valid_model) - len(parsed),
            "provider_failures": sum(row.get("classification") == "provider_request_failure" for row in valid_model),
            "parse_failures": sum(row.get("classification") == "response_parse_failure" for row in valid_model),
            "truncations": sum(row.get("classification") == "response_truncated" for row in valid_model),
            "prompt_tokens": sum(int(row.get("prompt_tokens") or row.get("usage", {}).get("prompt_tokens") or 0) for row in usages),
            "completion_tokens": sum(int(row.get("completion_tokens") or row.get("usage", {}).get("completion_tokens") or 0) for row in usages),
            "total_tokens": sum(int(row.get("total_tokens") or row.get("usage", {}).get("total_tokens") or 0) for row in usages),
            "median_latency": statistics.median(elapsed) if elapsed else None,
            "max_latency": max(elapsed) if elapsed else None,
        },
        "blocked_fact_gain": {**dict(endpoint_counts), "newly_unblocked_facts": len(unblocked)},
        "person_knowledge_gain": {"persons_enriched": None},
        "comparison_p1_1": {"p1_1_occurrence_count": p1_metrics.get("occurrence_count", 25), "p1_1_final_states": {key: p1_metrics.get(key, 0) for key in ("explicit_resolved", "contextually_resolved", "contextually_preferred", "unresolved", "compositional_reference", "not_person")}},
        "candidate_only": True,
        "canonical_write_back": False,
    }


def project(run_dir: Path, *, selection_path: Path, cases_path: Path) -> dict[str, Any]:
    cases, results, cases_doc = _cases_and_results(run_dir, cases_path)
    _identity, relations = _hdb1()
    unblocked, endpoint_counts = build_unblocked(cases, results, relations)
    deltas = build_knowledge_deltas(cases, results)
    review = build_review_queue(cases, results)
    model_records = list((common.read_json(run_dir / "model-decisions.json", {}) or {}).get("records", []))
    p1_metrics = common.read_json(common.DERIVED / "hdb2-p1-1-metrics.json", {}) or {}
    metrics = build_metrics(cases, results, model_records, unblocked, endpoint_counts, p1_metrics)
    metrics["person_knowledge_gain"]["persons_enriched"] = len(deltas)
    metrics["selection_hash"] = (common.read_json(selection_path, {}) or {}).get("selection_hash")
    metrics["source_case_hash"] = common.stable_hash(cases_doc)
    common.write_json(run_dir / "production-summary.json", {"metrics": metrics, "candidate_only": True, "canonical_write_back": False})
    common.write_json(run_dir / "rejected-items.json", {"records": [row for row in model_records if (row.get("validation") or {}).get("valid") is False], "candidate_only": True, "canonical_write_back": False})
    common.write_json(common.ANNOTATION / "hdb2-p2t-occurrence-decisions.json", {"schema": "hdb2-p2t-occurrence-decisions-v1", "records": results, "candidate_only": True, "canonical_write_back": False})
    common.write_json(common.ANNOTATION / "hdb2-p2t-review-queue.json", {"schema": "hdb2-p2t-review-queue-v1", "records": review, "candidate_only": True, "canonical_write_back": False})
    common.write_json(common.DERIVED / "hdb2-p2t-person-knowledge-deltas.json", {"schema": "hdb2-p2t-person-knowledge-deltas-v1", "records": deltas, "candidate_only": True, "canonical_write_back": False})
    common.write_json(common.DERIVED / "hdb2-p2t-unblocked-facts.json", {"schema": "hdb2-p2t-unblocked-facts-v1", "records": unblocked, "candidate_only": True, "canonical_write_back": False})
    common.write_json(common.DERIVED / "hdb2-p2t-metrics.json", metrics)
    comparison = {"schema": "hdb2-p2t-comparison-v1", "p1_1_metrics": p1_metrics, "p2t_metrics": metrics, "candidate_only": True, "canonical_write_back": False}
    common.write_json(common.DERIVED / "hdb2-p2t-comparison.json", comparison)
    common.write_json(run_dir / "metrics.json", metrics)
    common.write_json(run_dir / "knowledge-deltas.json", deltas)
    common.write_json(run_dir / "unblocked-facts.json", unblocked)
    common.write_json(run_dir / "review-queue.json", review)
    return metrics


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("run_dir", type=Path)
    parser.add_argument("--selection", type=Path, default=common.ANNOTATION / "hdb2-p2t-occurrence-selection.json")
    parser.add_argument("--cases", type=Path, default=common.DERIVED / "hdb2-p2t-occurrence-cases.json")
    args = parser.parse_args()
    run_dir = args.run_dir if args.run_dir.is_absolute() else ROOT / args.run_dir
    print(json.dumps(project(run_dir, selection_path=args.selection, cases_path=args.cases), ensure_ascii=False, indent=2, sort_keys=True))
