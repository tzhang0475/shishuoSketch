#!/usr/bin/env python3
"""Run HDB2-P1: deterministic retrieval plus bounded EvidenceAtom reading."""

from __future__ import annotations

import argparse
import collections
import datetime as dt
import hashlib
import json
import statistics
import sys
import time
from pathlib import Path
from typing import Any, Mapping, Sequence

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import build_hng0_2 as hng02  # noqa: E402
import hng2_schema_controller as controller  # noqa: E402
import run_hng2_fresh_validation as frozen  # noqa: E402
import solve_hdb2_constraints as solver  # noqa: E402
from hdb2_p1_common import (  # noqa: E402
    ANNOTATION,
    DERIVED,
    GENERATED,
    MODEL,
    PROMPT_VERSION,
    SYSTEM_PROMPT,
    build_source_index,
    file_hash,
    freeze_selection,
    read_json,
    search_case,
    stable_hash,
    strict_atom_tool,
    tool_choice,
    user_prompt,
    validate_atoms,
    write_json,
)
from smoke_deepseek import call_deepseek  # noqa: E402

STRICT_ENDPOINT = "https://api.deepseek.com/beta/chat/completions"
OUT = GENERATED


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def usage(response: Mapping[str, Any] | None) -> dict[str, int]:
    raw = response.get("usage") if isinstance(response, Mapping) and isinstance(response.get("usage"), Mapping) else {}
    return {key: int(raw.get(key) or 0) for key in ("prompt_tokens", "completion_tokens", "total_tokens")}


def finish_reason(response: Mapping[str, Any]) -> str | None:
    choices = response.get("choices") if isinstance(response.get("choices"), list) else []
    if choices and isinstance(choices[0], Mapping):
        return str(choices[0].get("finish_reason") or "") or None
    return None


def safe_error(exc: Exception) -> dict[str, Any]:
    return {
        "exception_class": type(exc).__name__,
        "exception_message": str(exc)[:1000],
        "http_status": getattr(exc, "http_status", None),
        "provider_error_body": str(getattr(exc, "provider_error_body", ""))[:2000],
    }


def _raw_path(raw_dir: Path, sequence: int, case_id: str, round_no: int, attempt: int) -> Path:
    return raw_dir / f"{sequence:03d}-{case_id}-round{round_no}-attempt{attempt}.json"


def semantic_call(
    case: Mapping[str, Any],
    passages: Sequence[Mapping[str, Any]],
    *,
    round_no: int,
    raw_dir: Path,
    sequence: int,
) -> tuple[dict[str, Any], dict[str, Any] | None]:
    prompt = user_prompt(case, passages)
    record: dict[str, Any] = {
        "sequence": sequence,
        "case_id": case.get("case_id"),
        "round": round_no,
        "model": MODEL,
        "prompt_version": PROMPT_VERSION,
        "input_hash": stable_hash(prompt),
        "request": {"system": SYSTEM_PROMPT, "user": prompt},
        "attempts": [],
    }
    parsed: dict[str, Any] | None = None
    for attempt in (1, 2):
        started = time.monotonic()
        attempt_row: dict[str, Any] = {"attempt": attempt, "started_at": utc_now()}
        try:
            response = call_deepseek(
                [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": json.dumps(prompt, ensure_ascii=False, sort_keys=True)},
                ],
                model=MODEL,
                temperature=0,
                thinking={"type": "disabled"},
                max_tokens=1200,
                timeout=180,
                endpoint=STRICT_ENDPOINT,
                tools=[strict_atom_tool()],
                tool_choice=tool_choice(),
            )
            path = _raw_path(raw_dir, sequence, str(case.get("case_id")), round_no, attempt)
            if path.exists():
                raise RuntimeError(f"immutable_raw_response_exists:{path}")
            write_json(path, response)
            finish = finish_reason(response)
            attempt_row.update({"status": "response", "finish_reason": finish, "usage": usage(response), "raw_path": str(path.relative_to(ROOT))})
            if finish == "length":
                attempt_row["classification"] = "response_truncated"
                record["attempts"].append(attempt_row)
                break
            payload, channel, error = controller.extract_strict_tool_payload(response, expected_function_name="submit_hdb2_identity_atoms")
            attempt_row["response_channel"] = channel
            if error:
                attempt_row.update({"classification": "response_parse_failure", "parse_error": error})
                record["attempts"].append(attempt_row)
                if attempt == 1:
                    continue
                break
            parsed = dict(payload or {})
            attempt_row["classification"] = "parsed"
            record["attempts"].append(attempt_row)
            break
        except Exception as exc:
            attempt_row.update({"classification": "provider_request_failure", **safe_error(exc)})
            record["attempts"].append(attempt_row)
            if attempt == 1:
                continue
        finally:
            attempt_row["elapsed_seconds"] = round(time.monotonic() - started, 3)
            attempt_row["ended_at"] = utc_now()
    record["status"] = "parsed" if parsed is not None else "failed"
    record["classification"] = "parsed" if parsed is not None else (record["attempts"][-1].get("classification") if record["attempts"] else "provider_request_failure")
    record["retry_count"] = max(0, len(record["attempts"]) - 1)
    record["usage"] = {key: sum(int((a.get("usage") or {}).get(key) or 0) for a in record["attempts"]) for key in ("prompt_tokens", "completion_tokens", "total_tokens")}
    record["elapsed_seconds"] = round(sum(float(a.get("elapsed_seconds") or 0) for a in record["attempts"]), 3)
    record["ended_at"] = utc_now()
    return record, parsed


def _annotate_atoms(validation: Mapping[str, Any], round_no: int) -> list[dict[str, Any]]:
    atoms: list[dict[str, Any]] = []
    for atom in validation.get("valid_atoms", []):
        row = dict(atom)
        row["original_atom_id"] = row.get("atom_id")
        row["atom_id"] = f"round{round_no}-{row.get('atom_id')}"
        row["round"] = round_no
        atoms.append(row)
    return atoms


def _protected_hashes() -> dict[str, str]:
    names = [
        "data/people.json",
        "data/derived/person-relations-r3b.json",
        "data/derived/sc1-site.json",
        "data/derived/h0b1-social-backbone.json",
        "data/annotation/story-temporal-anchors-h0a.json",
        "data/annotation/story-temporal-evidence-h0a.json",
        "data/annotation/kinship-h0b1.json",
        "data/annotation/marriages-h0b1.json",
        "data/annotation/office-tenures-h0b1.json",
    ]
    return {name: file_hash(ROOT / name) for name in names if (ROOT / name).is_file()}


def _should_round_two(first_decision: Mapping[str, Any], second_search: Mapping[str, Any]) -> bool:
    if str(first_decision.get("status")) in {"resolved_existing", "resolved_new_candidate", "conflict"}:
        return False
    return bool(second_search.get("selected_passages"))


def run_case(case: Mapping[str, Any], units: Sequence[Mapping[str, Any]], catalog: Mapping[str, Mapping[str, Any]], raw_dir: Path, sequence: int) -> tuple[dict[str, Any], int]:
    first = search_case(case, units, catalog, max_passages=4, max_chars=2000)
    transport1, payload1 = semantic_call(case, first.get("selected_passages", []), round_no=1, raw_dir=raw_dir, sequence=sequence)
    sequence += 1
    validation1 = validate_atoms(payload1, first.get("selected_passages", [])) if payload1 is not None else {"valid_atoms": [], "rejected_atoms": [{"reason": transport1.get("classification"), "item": None}]}
    atoms1 = _annotate_atoms(validation1, 1)
    preview = solver.solve_case(case, atoms1, first.get("selected_passages", []), catalog)
    used = {str(x.get("ref")) for x in first.get("selected_passages", [])}
    second = search_case(case, units, catalog, used_refs=used, max_passages=4, max_chars=2000)
    rounds = [{"round": 1, "search": first, "transport": transport1, "payload": payload1, "validation": validation1}]
    atoms = list(atoms1)
    passages = list(first.get("selected_passages", []))
    if _should_round_two(preview.get("decision", {}), second):
        transport2, payload2 = semantic_call(case, second.get("selected_passages", []), round_no=2, raw_dir=raw_dir, sequence=sequence)
        sequence += 1
        validation2 = validate_atoms(payload2, second.get("selected_passages", [])) if payload2 is not None else {"valid_atoms": [], "rejected_atoms": [{"reason": transport2.get("classification"), "item": None}]}
        rounds.append({"round": 2, "search": second, "transport": transport2, "payload": payload2, "validation": validation2})
        atoms.extend(_annotate_atoms(validation2, 2))
        passages.extend(second.get("selected_passages", []))
    unique_passages: list[dict[str, Any]] = []
    seen_refs: set[str] = set()
    for passage in passages:
        if str(passage.get("ref")) in seen_refs:
            continue
        seen_refs.add(str(passage.get("ref")))
        unique_passages.append(passage)
    unique_atoms: list[dict[str, Any]] = []
    seen_atoms: set[tuple[Any, ...]] = set()
    for atom in atoms:
        key = (atom.get("evidence_ref"), atom.get("exact_span"), atom.get("subject_surface"), atom.get("predicate_surface"), atom.get("object_surface"), atom.get("temporal_surface"))
        if key in seen_atoms:
            continue
        seen_atoms.add(key)
        unique_atoms.append(atom)
    return {
        "case_id": case.get("case_id"),
        "case": dict(case),
        "rounds": rounds,
        "all_passages": unique_passages,
        "validated_atoms": unique_atoms,
        "rejected_atoms": [item for row in rounds for item in (row.get("validation") or {}).get("rejected_atoms", [])],
        "candidate_only": True,
        "canonical_write_back": False,
    }, sequence


def _attempts(case_results: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    return [
        attempt
        for row in case_results
        for round_row in row.get("rounds", [])
        for attempt in (round_row.get("transport") or {}).get("attempts", [])
    ]


def _aggregate_metrics(
    solved: Mapping[str, Any],
    case_results: Sequence[Mapping[str, Any]],
    preflight: Mapping[str, Any],
    selection: Mapping[str, Any],
) -> dict[str, Any]:
    def report_work(value: Any) -> str:
        work = str(value or "unknown")
        return {"世說新語": "世說正文", "箋疏正文": "箋疏"}.get(work, work)

    attempts = _attempts(case_results)
    tokens = {
        key: sum(int((row.get("usage") or {}).get(key) or 0) for row in attempts)
        for key in ("prompt_tokens", "completion_tokens", "total_tokens")
    }
    latencies = [float(row.get("elapsed_seconds")) for row in attempts if row.get("classification") == "parsed" and row.get("elapsed_seconds") is not None]
    solved_cases = list(solved.get("cases", []))
    decisions = [row.get("decision", {}) for row in solved_cases]
    atoms = [atom for row in solved_cases for atom in row.get("atoms", [])]
    rejected = [item for row in case_results for item in row.get("rejected_atoms", [])]
    statuses = collections.Counter(str(row.get("status")) for row in decisions)
    source_works = collections.Counter()
    source_contribution: dict[str, dict[str, int]] = collections.defaultdict(lambda: {"search_hits": 0, "selected_windows": 0, "accepted_atoms": 0, "identity_atoms": 0, "resolved_cases_contributed": 0, "narrowed_cases_contributed": 0})
    for case_row, solved_row in zip(case_results, solved_cases):
        passage_by_ref = {str(x.get("ref")): x for x in case_row.get("all_passages", [])}
        for atom in case_row.get("validated_atoms", []):
            work = report_work((passage_by_ref.get(str(atom.get("evidence_ref"))) or {}).get("source_work"))
            source_works[work] += 1
        hit_works = {report_work(hit.get("source_work")) for rr in case_row.get("rounds", []) for hit in (rr.get("search") or {}).get("hits", [])}
        selected_works = {report_work(x.get("source_work")) for x in case_row.get("all_passages", [])}
        for work in hit_works | selected_works:
            stats = source_contribution[work]
            stats["selected_windows"] += sum(1 for x in case_row.get("all_passages", []) if report_work(x.get("source_work")) == work)
            stats["search_hits"] += sum(1 for rr in case_row.get("rounds", []) for hit in (rr.get("search") or {}).get("hits", []) if report_work(hit.get("source_work")) == work)
            accepted_for_work = sum(1 for atom in case_row.get("validated_atoms", []) if report_work((passage_by_ref.get(str(atom.get("evidence_ref"))) or {}).get("source_work")) == work)
            identity_for_work = sum(1 for atom in case_row.get("validated_atoms", []) if atom.get("atom_kind") == "identity_name" and report_work((passage_by_ref.get(str(atom.get("evidence_ref"))) or {}).get("source_work")) == work)
            stats["accepted_atoms"] += accepted_for_work
            stats["identity_atoms"] += identity_for_work
            status = str(solved_row.get("decision", {}).get("status"))
            stats["resolved_cases_contributed"] += int(status in {"resolved_existing", "resolved_new_candidate"} and identity_for_work > 0)
            stats["narrowed_cases_contributed"] += int(status == "narrowed" and accepted_for_work > 0)
    temporal_eliminations = sum(len(row.get("state_delta", {}).get("temporal_eliminations", [])) for row in solved_cases)
    for work in ("世說正文", "劉注", "箋疏", "晉書", "三國志", "資治通鑑"):
        source_contribution.setdefault(work, {"search_hits": 0, "selected_windows": 0, "accepted_atoms": 0, "identity_atoms": 0, "resolved_cases_contributed": 0, "narrowed_cases_contributed": 0})
    return {
        "schema": "hdb2-p1-metrics-v1",
        "selected_cases": len(selection.get("cases", [])),
        "blocked_relations_at_start": sum(len(row.get("blocked_relations", [])) for row in selection.get("cases", [])),
        "blocked_kinship_at_start": sum(len(row.get("blocked_kinship", [])) for row in selection.get("cases", [])),
        "blocked_marriage_at_start": sum(len(row.get("blocked_marriage", [])) for row in selection.get("cases", [])),
        "total_queries": sum(len(rr.get("search", {}).get("queries", [])) for row in case_results for rr in row.get("rounds", [])),
        "total_hits": sum(len(rr.get("search", {}).get("hits", [])) for row in case_results for rr in row.get("rounds", [])),
        "selected_passages": sum(len(row.get("all_passages", [])) for row in case_results),
        "average_passages_per_case": (sum(len(row.get("all_passages", [])) for row in case_results) / len(case_results)) if case_results else 0,
        "semantic_calls": len(attempts),
        "second_round_calls": sum(len(row.get("rounds", [])) > 1 for row in case_results),
        "retries": sum(max(0, len((rr.get("transport") or {}).get("attempts", [])) - 1) for row in case_results for rr in row.get("rounds", [])),
        "provider_failures": sum(row.get("classification") == "provider_request_failure" for row in attempts),
        "parse_failures": sum(row.get("classification") == "response_parse_failure" for row in attempts),
        "truncations": sum(row.get("classification") == "response_truncated" for row in attempts),
        "tokens": tokens,
        "median_latency_seconds": statistics.median(latencies) if latencies else None,
        "max_latency_seconds": max(latencies) if latencies else None,
        "atoms_returned": len(atoms) + len(rejected),
        "atoms_grounded": len(atoms),
        "atoms_rejected": len(rejected),
        "atom_kinds": dict(collections.Counter(str(row.get("atom_kind")) for row in atoms)),
        "source_works": dict(source_works),
        "resolution": dict(statuses),
        "candidate_count_before": sum(len(row.get("decision", {}).get("candidate_set_before", [])) for row in solved_cases),
        "candidate_count_after": sum(len(row.get("decision", {}).get("candidate_set_after", [])) for row in solved_cases),
        "candidates_eliminated_temporal": temporal_eliminations,
        "candidates_eliminated_kinship": 0,
        "candidates_eliminated_office": 0,
        "candidates_eliminated_identity_conflict": sum(int(row.get("state_delta", {}).get("candidates_eliminated_identity_conflict", 0)) for row in solved_cases),
        "blocked_relations_unblocked": sum(len(row.get("newly_unblocked_candidate_facts", [])) for row in solved_cases),
        "collapsed_nonidentity_self_relations": 0,
        "collapsed_nonidentity_self_relations_rejected": sum(len(row.get("rejected_relations", [])) for row in solved_cases),
        "source_contribution": dict(source_contribution),
        "candidate_only": True,
        "canonical_write_back": False,
        "preflight": dict(preflight),
    }


def _write_projection_artifacts(solved: Mapping[str, Any], metrics: Mapping[str, Any], case_results: Sequence[Mapping[str, Any]], selection: Mapping[str, Any]) -> None:
    atoms = [atom for row in case_results for atom in row.get("validated_atoms", [])]
    rejected = [item for row in case_results for item in row.get("rejected_atoms", [])]
    decisions = [row.get("decision", {}) for row in solved.get("cases", [])]
    unblocked = [item for row in solved.get("cases", []) for item in row.get("newly_unblocked_candidate_facts", [])]
    deltas = [row.get("person_knowledge_delta", {}) for row in solved.get("cases", [])]
    decisions_by_case = {str(row.get("case_id")): row.get("decision", {}) for row in solved.get("cases", [])}
    case_index = []
    for case in selection.get("cases", []):
        case_index.append({**dict(case), "final_decision": decisions_by_case.get(str(case.get("case_id")), {})})
    write_json(DERIVED / "hdb2-identity-case-index.json", {"schema": "hdb2-p1-identity-case-index-v1", "candidate_only": True, "canonical_write_back": False, "selection_hash": selection.get("selection_hash"), "records": case_index})
    write_json(ANNOTATION / "hdb2-new-evidence-atoms.json", {"schema": "hdb2-p1-evidence-atoms-v1", "candidate_only": True, "canonical_write_back": False, "records": atoms, "rejected": rejected})
    write_json(ANNOTATION / "hdb2-identity-decisions-candidate.json", {"schema": "hdb2-p1-identity-decisions-v1", "candidate_only": True, "canonical_write_back": False, "selection_hash": selection.get("selection_hash"), "records": decisions})
    review = [{"review_id": f"hdb2-review-{stable_hash({'case': row.get('case_id'), 'status': row.get('status')})[:20]}", "case_id": row.get("case_id"), "review_type": "identity_constraint_fusion", "review_status": "not_reviewed", "candidate_decision": row} for row in decisions if row.get("status") in {"resolved_existing", "resolved_new_candidate", "narrowed", "conflict"}]
    write_json(ANNOTATION / "hdb2-review-queue.json", {"schema": "hdb2-p1-review-queue-v1", "candidate_only": True, "canonical_write_back": False, "records": review})
    write_json(DERIVED / "hdb2-constraint-results.json", solved)
    write_json(DERIVED / "hdb2-unblocked-candidate-facts.json", {"schema": "hdb2-p1-unblocked-facts-v1", "candidate_only": True, "canonical_write_back": False, "records": unblocked})
    write_json(DERIVED / "hdb2-person-knowledge-deltas.json", {"schema": "hdb2-p1-knowledge-delta-v1", "candidate_only": True, "canonical_write_back": False, "records": deltas})
    write_json(DERIVED / "hdb2-source-contribution.json", {"schema": "hdb2-p1-source-contribution-v1", "candidate_only": True, "canonical_write_back": False, "works": metrics.get("source_contribution", {})})
    write_json(DERIVED / "hdb2-p1-metrics.json", metrics)


def _protected_hashes() -> dict[str, str]:
    names = [
        "data/people.json",
        "data/derived/person-relations-r3b.json",
        "data/derived/sc1-site.json",
        "data/derived/h0b1-social-backbone.json",
        "data/annotation/story-temporal-anchors-h0a.json",
        "data/annotation/story-temporal-evidence-h0a.json",
        "data/annotation/kinship-h0b1.json",
        "data/annotation/marriages-h0b1.json",
        "data/annotation/office-tenures-h0b1.json",
    ]
    return {name: file_hash(ROOT / name) for name in names if (ROOT / name).is_file()}


def run_live(selection: Mapping[str, Any], run_id: str) -> Path:
    base = OUT / "live" / run_id
    if base.exists():
        raise RuntimeError(f"hdb2_immutable_live_run_exists:{base}")
    base.mkdir(parents=True)
    raw_dir = base / "raw-api"
    raw_dir.mkdir()
    preflight = frozen.preflight()
    write_json(base / "preflight.json", preflight)
    if preflight.get("status") != "reachable":
        write_json(base / "manifest.json", {"schema": "hdb2-p1-live-manifest-v1", "run_id": run_id, "status": "preflight_failed", "preflight": preflight, "candidate_only": True, "canonical_write_back": False})
        raise RuntimeError("hdb2_p1_preflight_failed")
    units = build_source_index()
    catalog = hng02.person_catalog()
    case_results: list[dict[str, Any]] = []
    sequence = 1
    for case in selection.get("cases", []):
        result, sequence = run_case(case, units, catalog, raw_dir, sequence)
        case_results.append(result)
    live_doc = {"schema": "hdb2-p1-case-results-v1", "run_id": run_id, "cases": case_results, "candidate_only": True, "canonical_write_back": False}
    write_json(base / "case-results.json", live_doc)
    solved = solver.solve_run(base, selection)
    write_json(base / "constraint-results.json", solved)
    metrics = _aggregate_metrics(solved, case_results, preflight, selection)
    write_json(base / "metrics.json", metrics)
    write_json(base / "search-results.json", {"schema": "hdb2-p1-search-results-v1", "cases": [{"case_id": row.get("case_id"), "rounds": [{"round": rr.get("round"), "queries": rr.get("search", {}).get("queries", []), "hits": rr.get("search", {}).get("hits", []), "selected_passages": rr.get("search", {}).get("selected_passages", [])} for rr in row.get("rounds", [])]} for row in case_results]})
    write_json(base / "selected-passages.json", {"schema": "hdb2-p1-selected-passages-v1", "cases": [{"case_id": row.get("case_id"), "passages": row.get("all_passages", [])} for row in case_results]})
    write_json(base / "evidence-atoms.json", {"schema": "hdb2-p1-evidence-atoms-v1", "records": [atom for row in case_results for atom in row.get("validated_atoms", [])], "candidate_only": True, "canonical_write_back": False})
    write_json(base / "rejected-atoms.json", {"schema": "hdb2-p1-rejected-atoms-v1", "records": [item for row in case_results for item in row.get("rejected_atoms", [])]})
    raw_hashes = {str(path.relative_to(base)): hashlib.sha256(path.read_bytes()).hexdigest() for path in sorted(raw_dir.glob("*.json"))}
    manifest = {
        "schema": "hdb2-p1-live-manifest-v1",
        "run_id": run_id,
        "run_version": "hdb2-p1-live-v1",
        "selection_hash": selection.get("selection_hash"),
        "model": MODEL,
        "temperature": 0,
        "strict_endpoint": STRICT_ENDPOINT,
        "prompt_version": PROMPT_VERSION,
        "source_index_count": len(units),
        "raw_api_hashes": raw_hashes,
        "protected_hashes_before_live": _protected_hashes(),
        "candidate_only": True,
        "canonical_write_back": False,
        "no_search_plan": True,
        "no_research_gap_loop": True,
        "no_recursive_expansion": True,
        "semantic_call_attempts": metrics.get("semantic_calls"),
        "preflight": preflight,
    }
    manifest["manifest_hash"] = stable_hash({key: value for key, value in manifest.items() if key != "manifest_hash"})
    write_json(base / "manifest.json", manifest)
    _write_projection_artifacts(solved, metrics, case_results, selection)
    return base


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", default=None)
    parser.add_argument("--selection", type=Path, default=ANNOTATION / "hdb2-p1-selection.json")
    args = parser.parse_args()
    selection = freeze_selection(args.selection)
    run_id = args.run_id or dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ-HDB2-P1-01")
    base = run_live(selection, run_id)
    print(f"HDB2-P1 live run complete: {base.relative_to(ROOT)}")
    print(json.dumps(read_json(base / "metrics.json", {}), ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
