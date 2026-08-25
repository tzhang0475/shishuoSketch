#!/usr/bin/env python3
"""Run HDB2-F over the frozen, occurrence-level identity frontier.

The runner has no search planner or recursive loop.  It uses the frozen P2T
contextual card at most once per occurrence and permits one deterministic P1
EvidenceAtom rescue round only for structurally valuable residuals.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
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
import hdb2_full_frontier_common as common  # noqa: E402
import hdb2_p1_common as p1  # noqa: E402
import hdb2_occurrence_common as occ  # noqa: E402
import hng2_schema_controller as controller  # noqa: E402
import historical_context_algorithm as frozen_algorithm  # noqa: E402
from smoke_deepseek import call_deepseek  # noqa: E402


MODEL = common.MODEL
CONTEXT_FUNCTION = "submit_hdb2_occurrence_identity_decision"
RESCUE_FUNCTION = "submit_hdb2_identity_atoms"


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def usage(response: Mapping[str, Any] | None) -> dict[str, int]:
    raw = response.get("usage") if isinstance(response, Mapping) and isinstance(response.get("usage"), Mapping) else {}
    return {key: int(raw.get(key) or 0) for key in ("prompt_tokens", "completion_tokens", "total_tokens")}


def finish_reason(response: Mapping[str, Any]) -> str | None:
    choices = response.get("choices") if isinstance(response, Mapping) else None
    if isinstance(choices, list) and choices and isinstance(choices[0], Mapping):
        return str(choices[0].get("finish_reason") or "") or None
    return None


def safe_error(exc: Exception) -> dict[str, Any]:
    message = str(exc)
    secret = os.environ.get("DEEPSEEK_API_KEY")
    if secret:
        message = message.replace(secret, "[REDACTED]")
    return {"exception_class": type(exc).__name__, "exception_message": message[:1000], "http_status": getattr(exc, "http_status", None)}


def preflight() -> dict[str, Any]:
    started = time.monotonic()
    record: dict[str, Any] = {"status": "unknown", "model": MODEL, "endpoint": frozen_algorithm.STRICT_ENDPOINT, "started_at": utc_now()}
    try:
        response = call_deepseek(
            [{"role": "user", "content": "Reply only with OK."}],
            model=MODEL,
            temperature=0,
            thinking={"type": "disabled"},
            max_tokens=16,
            timeout=60,
            endpoint=frozen_algorithm.STRICT_ENDPOINT,
        )
        record.update({"status": "reachable", "response_model": response.get("model"), "usage": usage(response)})
    except Exception as exc:
        record.update({"status": "provider_request_failure", **safe_error(exc)})
    record.update({"elapsed_seconds": round(time.monotonic() - started, 3), "ended_at": utc_now()})
    return record


def _raw_path(raw_dir: Path, sequence: int, kind: str, attempt: int) -> Path:
    return raw_dir / f"{sequence:04d}-{kind}-attempt{attempt}.json"


def _context_call(case: Mapping[str, Any], sequence: int, raw_dir: Path) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]]:
    packet = occ.user_prompt(case)
    request = {
        "messages": [
            {"role": "system", "content": occ.SYSTEM_PROMPT},
            {"role": "user", "content": json.dumps(packet, ensure_ascii=False, sort_keys=True)},
        ],
        "model": MODEL,
        "temperature": 0,
        "thinking": {"type": "disabled"},
        "max_tokens": 900,
        "endpoint": frozen_algorithm.STRICT_ENDPOINT,
        "tools": [occ.strict_tool()],
        "tool_choice": occ.tool_choice(),
    }
    record: dict[str, Any] = {
        "sequence": sequence,
        "call_type": "contextual_disambiguation",
        "occurrence_id": case.get("occurrence_id"),
        "story_id": case.get("story_id"),
        "target_surface": case.get("target_surface"),
        "model": MODEL,
        "prompt_version": occ.PROMPT_VERSION,
        "input_hash": common.stable_hash(packet),
        "attempts": [],
    }
    payload: dict[str, Any] = {}
    validation: dict[str, Any] = {"valid": False, "errors": ["not_called"], "payload": {}}
    parsed = False
    for attempt in (1, 2):
        started = time.monotonic()
        attempt_row: dict[str, Any] = {"attempt": attempt, "started_at": utc_now()}
        try:
            response = call_deepseek(
                request["messages"],
                model=MODEL,
                temperature=0,
                thinking={"type": "disabled"},
                max_tokens=900,
                timeout=180,
                endpoint=frozen_algorithm.STRICT_ENDPOINT,
                tools=[occ.strict_tool()],
                tool_choice=occ.tool_choice(),
            )
            path = _raw_path(raw_dir, sequence, "context", attempt)
            if path.exists():
                raise RuntimeError(f"immutable_raw_response_exists:{path.name}")
            common.write_json(path, response)
            finish = finish_reason(response)
            attempt_row.update({"classification": "response", "finish_reason": finish, "usage": usage(response), "raw_path": str(path.relative_to(ROOT))})
            if finish == "length":
                attempt_row["classification"] = "response_truncated"
                record["attempts"].append(attempt_row)
                break
            extracted, channel, parse_error = controller.extract_strict_tool_payload(response, expected_function_name=CONTEXT_FUNCTION)
            attempt_row["response_channel"] = channel
            if parse_error or not isinstance(extracted, Mapping):
                attempt_row.update({"classification": "response_parse_failure", "parse_error": parse_error or "payload_not_object"})
                record["attempts"].append(attempt_row)
                if attempt == 1:
                    continue
                break
            payload = dict(extracted)
            validation = occ.validate_model_payload(payload, case)
            attempt_row.update({"classification": "parsed", "validation": {"valid": validation.get("valid"), "errors": validation.get("errors", [])}})
            parsed = True
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
    record["classification"] = "parsed" if parsed else (record["attempts"][-1].get("classification") if record["attempts"] else "provider_request_failure")
    record["retry_count"] = max(0, len(record["attempts"]) - 1)
    record["usage"] = {key: sum(int((x.get("usage") or {}).get(key) or 0) for x in record["attempts"]) for key in ("prompt_tokens", "completion_tokens", "total_tokens")}
    record["elapsed_seconds"] = round(sum(float(x.get("elapsed_seconds") or 0) for x in record["attempts"]), 3)
    result = common.apply_contextual(case, payload, validation)
    model_record = {"sequence": sequence, "call_type": "contextual_disambiguation", "occurrence_id": case.get("occurrence_id"), "payload": payload, "validation": validation, "classification": record["classification"]}
    return record, model_record, result, request


def _rescue_case(case: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "case_id": case.get("occurrence_id"),
        "target_surfaces": [case.get("target_surface")],
        "current_candidate_person_ids": [str(x.get("person_id")) for x in case.get("candidates", []) if x.get("person_id")],
        "resolved_neighbors": [{"canonical_name": x.get("display_name")} for x in case.get("local_neighbors", []) if x.get("display_name")],
        "office_hints": list(case.get("office_context", [])),
        "kinship_hints": list(case.get("kinship_context", [])),
    }


def _rescue_call(case: Mapping[str, Any], passages: Sequence[Mapping[str, Any]], sequence: int, raw_dir: Path) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    prompt = p1.user_prompt(_rescue_case(case), passages)
    request = {
        "messages": [
            {"role": "system", "content": p1.SYSTEM_PROMPT},
            {"role": "user", "content": json.dumps(prompt, ensure_ascii=False, sort_keys=True)},
        ],
        "model": MODEL,
        "temperature": 0,
        "thinking": {"type": "disabled"},
        "max_tokens": 1200,
        "endpoint": frozen_algorithm.STRICT_ENDPOINT,
        "tools": [p1.strict_atom_tool()],
        "tool_choice": p1.tool_choice(),
    }
    record: dict[str, Any] = {"sequence": sequence, "call_type": "evidence_rescue", "occurrence_id": case.get("occurrence_id"), "input_hash": common.stable_hash(prompt), "attempts": []}
    payload: dict[str, Any] = {}
    validation: dict[str, Any] = {"valid_atoms": [], "rejected_atoms": [{"reason": "not_called", "item": None}]}
    parsed = False
    for attempt in (1, 2):
        started = time.monotonic()
        attempt_row: dict[str, Any] = {"attempt": attempt, "started_at": utc_now()}
        try:
            response = call_deepseek(
                request["messages"],
                model=MODEL,
                temperature=0,
                thinking={"type": "disabled"},
                max_tokens=1200,
                timeout=180,
                endpoint=frozen_algorithm.STRICT_ENDPOINT,
                tools=[p1.strict_atom_tool()],
                tool_choice=p1.tool_choice(),
            )
            path = _raw_path(raw_dir, sequence, "rescue", attempt)
            if path.exists():
                raise RuntimeError(f"immutable_raw_response_exists:{path.name}")
            common.write_json(path, response)
            finish = finish_reason(response)
            attempt_row.update({"classification": "response", "finish_reason": finish, "usage": usage(response), "raw_path": str(path.relative_to(ROOT))})
            if finish == "length":
                attempt_row["classification"] = "response_truncated"
                record["attempts"].append(attempt_row)
                break
            extracted, channel, parse_error = controller.extract_strict_tool_payload(response, expected_function_name=RESCUE_FUNCTION)
            attempt_row["response_channel"] = channel
            if parse_error or not isinstance(extracted, Mapping):
                attempt_row.update({"classification": "response_parse_failure", "parse_error": parse_error or "payload_not_object"})
                record["attempts"].append(attempt_row)
                if attempt == 1:
                    continue
                break
            payload = dict(extracted)
            validation = p1.validate_atoms(payload, passages)
            attempt_row.update({"classification": "parsed", "validation": {"valid_atoms": len(validation.get("valid_atoms", [])), "rejected_atoms": len(validation.get("rejected_atoms", []))}})
            parsed = True
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
    record["classification"] = "parsed" if parsed else (record["attempts"][-1].get("classification") if record["attempts"] else "provider_request_failure")
    record["retry_count"] = max(0, len(record["attempts"]) - 1)
    record["usage"] = {key: sum(int((x.get("usage") or {}).get(key) or 0) for x in record["attempts"]) for key in ("prompt_tokens", "completion_tokens", "total_tokens")}
    record["elapsed_seconds"] = round(sum(float(x.get("elapsed_seconds") or 0) for x in record["attempts"]), 3)
    return record, {"sequence": sequence, "call_type": "evidence_rescue", "occurrence_id": case.get("occurrence_id"), "payload": payload, "validation": validation, "classification": record["classification"]}, request


def _append_rescue_evidence(case: dict[str, Any], passages: Sequence[Mapping[str, Any]], atoms: Sequence[Mapping[str, Any]], catalog: Mapping[str, Mapping[str, Any]], index: Mapping[str, Sequence[str]], identity: Sequence[Mapping[str, Any]], relations: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    existing_refs = {str(x.get("source_ref")) for x in case.get("evidence_items", [])}
    for passage in passages:
        ref = str(passage.get("ref") or "")
        if not ref or ref in existing_refs:
            continue
        text = str(passage.get("evidence_text") or "")
        case.setdefault("evidence_items", []).append({
            "evidence_id": f"ev-{common.stable_hash({'ref': ref, 'text': text})[:20]}",
            "source_ref": ref,
            "source_work": passage.get("source_work"),
            "source_layer": passage.get("source_layer"),
            "text": text,
            "locator": passage.get("locator", {}),
        })
    added: list[dict[str, Any]] = []
    for atom in atoms:
        added.extend(common.candidate_from_atom(case, atom, catalog, index))
    common._reindex_case(case, catalog, identity, relations)
    return added


def _update_case_result(result: dict[str, Any], case: Mapping[str, Any], *, rescue: Mapping[str, Any] | None = None) -> dict[str, Any]:
    result = dict(result)
    result["occurrence_id"] = case.get("occurrence_id")
    result["identity_observation_id"] = case.get("identity_observation_id")
    result["target_surface"] = case.get("target_surface")
    result["candidate_count_after"] = len(case.get("candidates", []))
    result["candidate_set_after"] = [x.get("person_id") or x.get("display_name") for x in case.get("candidates", [])]
    result["rescue_attempted"] = bool(rescue and rescue.get("attempted"))
    result["rescue_reasons"] = list((rescue or {}).get("reasons", []))
    result["rescue_useful"] = bool((rescue or {}).get("useful"))
    result["candidate_only"] = True
    result["canonical_write_back"] = False
    return result


def run(args: argparse.Namespace) -> Path:
    # Build and compare before preflight.  This is the freeze boundary: no
    # network work happens until the ledger, cases, and selection are equal to
    # their deterministic on-disk forms.
    import build_hdb2_full_frontier as builder

    ledger, selection, cases_doc = builder.build(write=True)
    frozen_selection = common.read_json(builder.SELECTION, {}) or {}
    if frozen_selection != selection:
        raise RuntimeError("hdb2_f_frontier_selection_changed_before_live")
    frozen_cases = common.read_json(builder.CASES, {}) or {}
    if common.stable_hash(frozen_cases) != common.stable_hash(cases_doc):
        raise RuntimeError("hdb2_f_cases_changed_before_live")
    cases = list(cases_doc.get("cases", []))
    catalog = hng02.person_catalog()
    import historical_entity_resolver as resolver
    index = resolver.forms_index(catalog)
    aggregate, identity, relations, registry = common.load_hdb1()
    units = occ._source_units()
    run_id = args.run_id or dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-HDB2-F"
    run_dir = common.GENERATED / "live" / run_id
    if run_dir.exists():
        raise RuntimeError(f"hdb2_f_run_exists:{run_dir}")
    raw_dir = run_dir / "raw-api"
    raw_dir.mkdir(parents=True, exist_ok=False)
    before = common.protected_hashes()
    preflight_record = preflight()
    common.write_json(run_dir / "preflight.json", preflight_record)
    if preflight_record.get("status") != "reachable":
        raise RuntimeError("hdb2_f_preflight_failed")

    prompt_records: list[dict[str, Any]] = []
    model_records: list[dict[str, Any]] = []
    python_records: list[dict[str, Any]] = []
    rescue_search: list[dict[str, Any]] = []
    rescue_passages: list[dict[str, Any]] = []
    rescue_atoms: list[dict[str, Any]] = []
    rejected_items: list[dict[str, Any]] = []
    call_records: list[dict[str, Any]] = []
    processed_cases: list[dict[str, Any]] = []
    context_sequence = 0
    rescue_sequence = 10000
    for sequence, original_case in enumerate(cases, start=1):
        case = json.loads(json.dumps(original_case, ensure_ascii=False))
        initial = common.deterministic_cascade(case)
        eligible, reasons = common.rescue_eligible(case, identity)
        rescue_info: dict[str, Any] = {"attempted": False, "reasons": reasons, "useful": False}
        final = initial
        # High-value ambiguous/unresolved cases get the one allowed P1
        # evidence rescue before their single contextual adjudication call.
        if eligible and (initial.get("llm_called") or initial.get("status") == "unresolved") and initial.get("status") not in common.STRUCTURAL_STATES:
            rescue_info["attempted"] = True
            search = p1.search_case(_rescue_case(case), units, catalog, used_refs={str(x.get("source_ref")) for x in case.get("evidence_items", [])}, max_passages=4, max_chars=2000)
            search_row = {"occurrence_id": case.get("occurrence_id"), "reasons": reasons, **search}
            rescue_search.append(search_row)
            selected = list(search.get("selected_passages", []))
            if selected:
                rescue_sequence += 1
                transport, model_record, request = _rescue_call(case, selected, rescue_sequence, raw_dir)
                model_records.append({**transport, **model_record, "request": request})
                call_records.append(transport)
                validation = model_record.get("validation", {})
                valid_atoms = list(validation.get("valid_atoms", []))
                rejected = list(validation.get("rejected_atoms", []))
                for item in rejected:
                    rejected_items.append({"occurrence_id": case.get("occurrence_id"), "stage": "evidence_rescue", **item})
                if valid_atoms:
                    rescue_info["useful"] = True
                added = _append_rescue_evidence(case, selected, valid_atoms, catalog, index, identity, relations)
                rescue_info["added_candidates"] = added
                rescue_info["valid_atoms"] = len(valid_atoms)
                rescue_info["rejected_atoms"] = len(rejected)
                for atom in valid_atoms:
                    rescue_atoms.append({"occurrence_id": case.get("occurrence_id"), **atom})
                for passage in selected:
                    rescue_passages.append({"occurrence_id": case.get("occurrence_id"), **passage})
                final = common.deterministic_cascade(case)
            else:
                rescue_info["valid_atoms"] = 0
                rescue_info["rejected_atoms"] = 0
        if final.get("llm_called"):
            context_sequence += 1
            transport, model_record, final, request = _context_call(case, context_sequence, raw_dir)
            model_records.append({**transport, **model_record, "request": request})
            call_records.append(transport)
            prompt_records.append({"sequence": context_sequence, "call_type": "contextual_disambiguation", "occurrence_id": case.get("occurrence_id"), "request": request})
        else:
            prompt_records.append({"sequence": sequence, "call_type": "python_or_rescue", "occurrence_id": case.get("occurrence_id"), "contextual_call": False})
        final = _update_case_result(final, case, rescue=rescue_info)
        final["sequence"] = sequence
        final["rescue_call_count"] = int(rescue_info.get("attempted"))
        final["contextual_call_count"] = int(final.get("llm_called") is True)
        python_records.append(final)
        processed_cases.append(case)

    after = common.protected_hashes()
    if before != after:
        raise RuntimeError("hdb2_f_protected_input_changed")
    manifest = {
        "schema": "hdb2-f-live-manifest-v1",
        "run_id": run_id,
        "run_version": common.RUN_VERSION,
        "algorithm_version": common.ALGORITHM_VERSION,
        "prompt_version": occ.PROMPT_VERSION,
        "model": MODEL,
        "temperature": 0,
        "thinking": "disabled",
        "endpoint": frozen_algorithm.STRICT_ENDPOINT,
        "selection_hash": selection.get("selection_hash"),
        "occurrence_count": len(cases),
        "candidate_only": True,
        "canonical_write_back": False,
        "search_plan_calls": 0,
        "recursive_rounds": 0,
        "frontier_selection_immutable": True,
        "preflight": preflight_record,
        "protected_hashes_before": before,
        "protected_hashes_after": after,
        "raw_api_hashes": {str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest() for path in sorted(raw_dir.glob("*.json"))},
        "created_at": utc_now(),
    }
    common.write_json(run_dir / "manifest.json", manifest)
    common.write_json(run_dir / "frontier.json", {"selection": selection, "ledger_counts": ledger.get("counts"), "candidate_only": True, "canonical_write_back": False})
    common.write_json(run_dir / "occurrence-contexts.json", {"cases": processed_cases, "candidate_only": True, "canonical_write_back": False})
    common.write_json(run_dir / "contextual-packets.json", {"records": prompt_records, "candidate_only": True, "canonical_write_back": False})
    common.write_json(run_dir / "contextual-decisions.json", {"records": [x for x in model_records if x.get("call_type") == "contextual_disambiguation"], "candidate_only": True, "canonical_write_back": False})
    common.write_json(run_dir / "rescue-search-results.json", {"records": rescue_search, "candidate_only": True, "canonical_write_back": False})
    common.write_json(run_dir / "rescue-selected-passages.json", {"records": rescue_passages, "candidate_only": True, "canonical_write_back": False})
    common.write_json(run_dir / "rescue-evidence-atoms.json", {"records": rescue_atoms, "candidate_only": True, "canonical_write_back": False})
    common.write_json(run_dir / "python-decisions.json", {"records": python_records, "candidate_only": True, "canonical_write_back": False})
    common.write_json(run_dir / "rejected-items.json", {"records": rejected_items, "candidate_only": True, "canonical_write_back": False})
    common.write_json(run_dir / "model-decisions.json", {"records": model_records, "candidate_only": True, "canonical_write_back": False})

    from build_hdb2_full_projection import project  # local import avoids cycle
    project(run_dir)
    print(json.dumps({"run_dir": str(run_dir.relative_to(ROOT)), "frontier_occurrences": len(cases), "contextual_calls": sum(x.get("call_type") == "contextual_disambiguation" for x in model_records), "rescue_calls": sum(x.get("call_type") == "evidence_rescue" for x in model_records)}, ensure_ascii=False, indent=2, sort_keys=True))
    return run_dir


def replay(run_dir: Path) -> Path:
    """Replay only deterministic HDB2-F post-processing; never call API."""
    model_doc = common.read_json(run_dir / "model-decisions.json", {}) or {}
    contexts = common.read_json(run_dir / "occurrence-contexts.json", {}) or {}
    records = common.read_json(run_dir / "python-decisions.json", {}) or {}
    fixed: list[dict[str, Any]] = []
    for row in records.get("records", []):
        item = dict(row)
        if item.get("status") in common.STRUCTURAL_STATES:
            item["resolved_person_id"] = None
            item["candidate_person_id"] = None
        item["candidate_only"] = True
        item["canonical_write_back"] = False
        fixed.append(item)
    common.write_json(run_dir / "python-decisions.json", {"records": fixed, "candidate_only": True, "canonical_write_back": False})
    from build_hdb2_full_projection import project
    project(run_dir)
    manifest = common.read_json(run_dir / "manifest.json", {}) or {}
    manifest["replayed_without_api"] = True
    manifest["postprocessing_replay_hash"] = common.stable_hash({"contexts": contexts, "model": model_doc, "python": fixed})
    common.write_json(run_dir / "manifest.json", manifest)
    return run_dir


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id")
    parser.add_argument("--replay", type=Path)
    args = parser.parse_args()
    if args.replay:
        replay(args.replay if args.replay.is_absolute() else ROOT / args.replay)
        return 0
    run(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
