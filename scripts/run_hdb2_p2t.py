#!/usr/bin/env python3
"""Run the HDB2-P2T three-stage occurrence integration test."""

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
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import historical_context_algorithm as frozen_algorithm  # noqa: E402
import hdb2_occurrence_common as occurrence  # noqa: E402
import hdb2_p2t_common as common  # noqa: E402
import hng2_schema_controller as controller  # noqa: E402
from smoke_deepseek import call_deepseek  # noqa: E402


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def usage(response: Mapping[str, Any]) -> dict[str, int]:
    raw = response.get("usage") if isinstance(response.get("usage"), Mapping) else {}
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
    return {"exception_class": type(exc).__name__, "exception_message": message, "http_status": getattr(exc, "http_status", None)}


def preflight() -> dict[str, Any]:
    started = time.monotonic()
    record: dict[str, Any] = {"model": common.MODEL, "endpoint": "https://api.deepseek.com/chat/completions", "start_time": utc_now()}
    try:
        response = call_deepseek([{"role": "user", "content": "Reply only with OK."}], model=common.MODEL, temperature=0, thinking={"type": "disabled"}, max_tokens=16, timeout=60)
        record.update({"status": "reachable", "usage": usage(response), "response_model": response.get("model")})
    except Exception as exc:
        record.update({"status": "provider_request_failure", **safe_error(exc)})
    record.update({"elapsed_seconds": round(time.monotonic() - started, 3), "end_time": utc_now()})
    return record


def load_frozen(selection_path: Path, cases_path: Path) -> tuple[dict[str, Any], dict[str, Any], list[dict[str, Any]]]:
    selection = common.read_json(selection_path, {}) or {}
    cases_doc = common.read_json(cases_path, {}) or {}
    if selection != common.build_selection(cases_doc):
        raise RuntimeError("p2t_selection_changed_after_freeze")
    if selection.get("occurrence_count") != 40 or selection.get("candidate_only") is not True or selection.get("canonical_write_back") is not False:
        raise RuntimeError("p2t_selection_invariant")
    by_id = {str(case.get("occurrence_id")): case for case in cases_doc.get("cases", [])}
    ordered = []
    for row in selection.get("cases", []):
        occurrence_id = str(row.get("occurrence_id"))
        if occurrence_id not in by_id:
            raise RuntimeError(f"p2t_case_missing:{occurrence_id}")
        ordered.append(by_id[occurrence_id])
    return selection, cases_doc, ordered


def semantic_call(case: Mapping[str, Any], *, sequence: int, raw_dir: Path) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]]:
    packet = occurrence.user_prompt(case)
    request = {
        "messages": [
            {"role": "system", "content": occurrence.SYSTEM_PROMPT},
            {"role": "user", "content": json.dumps(packet, ensure_ascii=False, sort_keys=True)},
        ],
        "model": common.MODEL,
        "temperature": 0,
        "thinking": {"type": "disabled"},
        "max_tokens": 900,
        "endpoint": frozen_algorithm.STRICT_ENDPOINT,
        "tools": [occurrence.strict_tool()],
        "tool_choice": occurrence.tool_choice(),
    }
    started = time.monotonic()
    record: dict[str, Any] = {
        "sequence": sequence,
        "occurrence_id": case.get("occurrence_id"),
        "story_id": case.get("story_id"),
        "target_surface": case.get("target_surface"),
        "classification": "unknown",
        "model": common.MODEL,
        "prompt_version": common.PROMPT_VERSION,
        "input_hash": common.stable_hash(packet),
        "start_time": utc_now(),
    }
    payload: dict[str, Any] = {}
    try:
        response = call_deepseek(
            request["messages"],
            model=common.MODEL,
            temperature=0,
            thinking={"type": "disabled"},
            max_tokens=900,
            timeout=180,
            endpoint=frozen_algorithm.STRICT_ENDPOINT,
            tools=[occurrence.strict_tool()],
            tool_choice=occurrence.tool_choice(),
        )
        raw_path = raw_dir / f"{sequence:03d}-{str(case.get('occurrence_id')).replace('/', '-')}.json"
        if raw_path.exists():
            raise RuntimeError(f"raw_response_exists:{raw_path.name}")
        common.write_json(raw_path, response)
        finish = finish_reason(response)
        record.update({"status": "response", "finish_reason": finish, "usage": usage(response), "raw_path": str(raw_path.relative_to(ROOT))})
        if finish == "length":
            record.update({"classification": "response_truncated", "response_channel": "tool_call"})
            validation = {"valid": False, "errors": ["response_truncated"], "payload": {}}
        else:
            extracted, channel, parse_error = controller.extract_strict_tool_payload(response, expected_function_name="submit_hdb2_occurrence_identity_decision")
            record["response_channel"] = channel
            if parse_error or not isinstance(extracted, Mapping):
                record.update({"classification": "response_parse_failure", "parse_error": parse_error or "payload_not_object"})
                validation = {"valid": False, "errors": ["response_parse_failure"], "payload": {}}
            else:
                payload = dict(extracted)
                validation = occurrence.validate_model_payload(payload, case)
                record.update({"classification": "parsed", "validation": {"valid": validation.get("valid"), "errors": validation.get("errors", [])}})
    except Exception as exc:
        record.update({"status": "provider_request_failure", "classification": "provider_request_failure", **safe_error(exc)})
        validation = {"valid": False, "errors": ["provider_request_failure"], "payload": {}}
    final = common.apply_llm_result(case, payload, validation)
    record.update({"elapsed_seconds": round(time.monotonic() - started, 3), "end_time": utc_now()})
    model_record = {
        "sequence": sequence,
        "occurrence_id": case.get("occurrence_id"),
        "classification": record.get("classification"),
        "payload": payload,
        "validation": validation,
        "response_channel": record.get("response_channel"),
        "llm_called": True,
    }
    return record, model_record, final, request


def run(args: argparse.Namespace) -> Path:
    selection, cases_doc, cases = load_frozen(args.selection, args.cases)
    run_id = args.run_id or dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-HDB2-P2T"
    run_dir = common.GENERATED / "live" / run_id
    if run_dir.exists():
        raise RuntimeError(f"p2t_run_exists:{run_dir}")
    raw_dir = run_dir / "raw-api"
    raw_dir.mkdir(parents=True, exist_ok=False)
    protected_before = common.protected_input_hashes()
    preflight_record = preflight()
    common.write_json(run_dir / "preflight.json", preflight_record)
    if preflight_record.get("status") != "reachable":
        raise RuntimeError("p2t_preflight_failed")

    prompt_records: list[dict[str, Any]] = []
    model_records: list[dict[str, Any]] = []
    python_records: list[dict[str, Any]] = []
    call_records: list[dict[str, Any]] = []
    for sequence, case in enumerate(cases, start=1):
        deterministic = common.deterministic_cascade(case)
        if deterministic.get("llm_called"):
            record, model_record, final, request = semantic_call(case, sequence=sequence, raw_dir=raw_dir)
            prompt_records.append({"sequence": sequence, "occurrence_id": case.get("occurrence_id"), "llm_called": True, "request": request})
            model_records.append({"sequence": sequence, **record, **model_record})
            call_records.append(record)
        else:
            final = deterministic
            final["identity_observation_id"] = case.get("identity_observation_id")
            prompt_records.append({"sequence": sequence, "occurrence_id": case.get("occurrence_id"), "llm_called": False})
            model_records.append({"sequence": sequence, "occurrence_id": case.get("occurrence_id"), "classification": "not_called_python", "payload": None, "validation": None, "llm_called": False})
        python_records.append({"sequence": sequence, **final})

    protected_after = common.protected_input_hashes()
    if protected_before != protected_after:
        raise RuntimeError("p2t_protected_input_changed")
    manifest = {
        "schema": "hdb2-p2t-live-manifest-v1",
        "run_id": run_id,
        "run_version": common.RUN_VERSION,
        "prompt_version": common.PROMPT_VERSION,
        "model": common.MODEL,
        "temperature": 0,
        "thinking": "disabled",
        "endpoint": frozen_algorithm.STRICT_ENDPOINT,
        "selection_hash": selection.get("selection_hash"),
        "occurrence_count": len(cases),
        "candidate_only": True,
        "canonical_write_back": False,
        "new_retrieval_calls": 0,
        "search_plan_calls": 0,
        "preflight": preflight_record,
        "protected_hashes_before": protected_before,
        "protected_hashes_after": protected_after,
        "raw_api_hashes": {str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest() for path in sorted(raw_dir.glob("*.json"))},
        "call_records_hash": common.stable_hash(call_records),
        "created_at": utc_now(),
    }
    common.write_json(run_dir / "manifest.json", manifest)
    common.write_json(run_dir / "prompt-packets.json", {"records": prompt_records, "candidate_only": True, "canonical_write_back": False})
    common.write_json(run_dir / "model-decisions.json", {"records": model_records, "candidate_only": True, "canonical_write_back": False})
    common.write_json(run_dir / "python-decisions.json", {"records": python_records, "candidate_only": True, "canonical_write_back": False})
    from build_hdb2_p2t_projection import project  # local import avoids runner/projection import cycle
    project(run_dir, selection_path=args.selection, cases_path=args.cases)
    print(json.dumps({"run_dir": str(run_dir.relative_to(ROOT)), "occurrences": len(cases), "llm_calls": sum(x.get("llm_called") is True for x in model_records)}, ensure_ascii=False, indent=2, sort_keys=True))
    return run_dir


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--selection", type=Path, default=common.ANNOTATION / "hdb2-p2t-occurrence-selection.json")
    parser.add_argument("--cases", type=Path, default=common.DERIVED / "hdb2-p2t-occurrence-cases.json")
    parser.add_argument("--run-id")
    args = parser.parse_args()
    run(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
