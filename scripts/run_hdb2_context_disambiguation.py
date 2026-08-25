#!/usr/bin/env python3
"""Run the bounded HDB2-P1.1 occurrence-level identity pilot.

The runner consumes the frozen occurrence projection, makes exactly one
candidate-disambiguation call per occurrence, and writes only isolated
candidate/audit artifacts.  It performs no retrieval and no canonical write.
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

import historical_context_algorithm as frozen_algorithm  # noqa: E402
import hdb2_occurrence_common as common  # noqa: E402
import hng2_schema_controller as controller  # noqa: E402
from smoke_deepseek import call_deepseek  # noqa: E402


MODEL = common.MODEL
RUN_VERSION = common.RUN_VERSION
PROMPT_VERSION = common.PROMPT_VERSION
OUT = common.GENERATED


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
    return {
        "exception_class": type(exc).__name__,
        "exception_message": message,
        "http_status": getattr(exc, "http_status", None),
    }


def file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def protected_files() -> list[Path]:
    # These are read-only inputs for this pilot.  Their hashes are captured so
    # a later validator can prove that the occurrence experiment did not write
    # into canonical or frozen historical namespaces.
    relative = [
        "data/people.json",
        "data/relations.json",
        "data/personStory.json",
        "data/annotation/story-temporal-anchors-h0a.json",
        "data/annotation/story-temporal-evidence-h0a.json",
        "data/annotation/h0b-1-kinship-facts.json",
        "data/annotation/h0b-1-marriage-unions.json",
        "data/annotation/h0b-1-office-tenures.json",
        "data/derived/hdb1-cross-wave-candidate-historical-db.json",
        "data/derived/hdb2-constraint-results.json",
        "data/generated/hdb2-p1/live/20260825T-HDB2-P1-03/case-results.json",
    ]
    return [ROOT / item for item in relative if (ROOT / item).is_file()]


def protected_hashes() -> dict[str, str]:
    return {str(path.relative_to(ROOT)): file_hash(path) for path in protected_files()}


def preflight() -> dict[str, Any]:
    started = time.monotonic()
    # Connectivity preflight is intentionally non-semantic.  The actual
    # occurrence calls below are the only calls sent to the strict Beta
    # endpoint with the forced function.
    record: dict[str, Any] = {"status": "unknown", "start_time": utc_now(), "model": MODEL, "endpoint": "https://api.deepseek.com/chat/completions"}
    try:
        response = call_deepseek(
            [{"role": "user", "content": "Reply only with OK."}],
            model=MODEL,
            temperature=0,
            thinking={"type": "disabled"},
            max_tokens=16,
            timeout=60,
        )
        record.update({"status": "reachable", "usage": usage(response), "response_model": response.get("model")})
    except Exception as exc:
        record.update({"status": "provider_request_failure", **safe_error(exc)})
    record.update({"elapsed_seconds": round(time.monotonic() - started, 3), "end_time": utc_now()})
    return record


def semantic_call(case: Mapping[str, Any], *, sequence: int, raw_dir: Path) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]]:
    prompt = common.user_prompt(case)
    request = {
        "messages": [
            {"role": "system", "content": common.SYSTEM_PROMPT},
            {"role": "user", "content": json.dumps(prompt, ensure_ascii=False, sort_keys=True)},
        ],
        "model": MODEL,
        "temperature": 0,
        "thinking": {"type": "disabled"},
        "max_tokens": 900,
        "endpoint": frozen_algorithm.STRICT_ENDPOINT,
        "tool_choice": common.tool_choice(),
        "tools": [common.strict_tool()],
    }
    record: dict[str, Any] = {
        "sequence": sequence,
        "occurrence_id": case.get("occurrence_id"),
        "story_id": case.get("story_id"),
        "target_surface": case.get("target_surface"),
        "model": MODEL,
        "prompt_version": PROMPT_VERSION,
        "input_hash": common.stable_hash(prompt),
        "start_time": utc_now(),
    }
    payload: dict[str, Any] = {}
    validation: dict[str, Any]
    final: dict[str, Any]
    started = time.monotonic()
    try:
        response = call_deepseek(
            request["messages"],
            model=MODEL,
            temperature=0,
            thinking={"type": "disabled"},
            max_tokens=900,
            timeout=180,
            endpoint=frozen_algorithm.STRICT_ENDPOINT,
            tools=[common.strict_tool()],
            tool_choice=common.tool_choice(),
        )
        raw_path = raw_dir / f"{sequence:03d}-{str(case.get('occurrence_id')).replace('/', '-')}.json"
        if raw_path.exists():
            raise RuntimeError(f"raw_response_exists:{raw_path.name}")
        common.write_json(raw_path, response)
        finish = finish_reason(response)
        record.update({"status": "response", "finish_reason": finish, "usage": usage(response), "raw_path": str(raw_path.relative_to(ROOT))})
        if finish == "length":
            record["classification"] = "response_truncated"
            validation = {"valid": False, "errors": ["response_truncated"], "payload": {}}
        else:
            extracted, channel, parse_error = controller.extract_strict_tool_payload(
                response,
                expected_function_name="submit_hdb2_occurrence_identity_decision",
            )
            record["response_channel"] = channel
            if parse_error or not isinstance(extracted, Mapping):
                record.update({"classification": "response_parse_failure", "parse_error": parse_error or "payload_not_object"})
                validation = {"valid": False, "errors": ["response_parse_failure"], "payload": {}}
            else:
                payload = dict(extracted)
                record["classification"] = "parsed"
                validation = common.validate_model_payload(payload, case)
                record["validation"] = {"valid": validation.get("valid"), "errors": validation.get("errors", [])}
        final = common.python_decision(case, payload, validation)
    except Exception as exc:
        record.update({"status": "provider_request_failure", "classification": "provider_request_failure", **safe_error(exc)})
        validation = {"valid": False, "errors": ["provider_request_failure"], "payload": {}}
        final = common.python_decision(case, payload, validation)
    record.update({"elapsed_seconds": round(time.monotonic() - started, 3), "end_time": utc_now()})
    return record, {"occurrence_id": case.get("occurrence_id"), "payload": payload, "classification": record.get("classification"), "response_channel": record.get("response_channel"), "validation": validation}, final, request


def load_frozen(selection_path: Path, cases_path: Path) -> tuple[dict[str, Any], dict[str, Any], list[dict[str, Any]]]:
    selection = common.read_json(selection_path, {}) or {}
    cases_doc = common.read_json(cases_path, {}) or {}
    if not selection.get("frozen_before_live") or selection.get("canonical_write_back") is not False:
        raise RuntimeError("selection_not_frozen_candidate_only")
    proposed = common.build_selection(cases_doc)
    if selection != proposed:
        raise RuntimeError("frozen_selection_mismatch")
    by_id = {str(case.get("occurrence_id")): case for case in cases_doc.get("cases", [])}
    ordered: list[dict[str, Any]] = []
    for item in selection.get("cases", []):
        occurrence_id = str(item.get("occurrence_id"))
        if occurrence_id not in by_id:
            raise RuntimeError(f"selection_case_missing:{occurrence_id}")
        ordered.append(by_id[occurrence_id])
    if len(ordered) < 20 or len(ordered) > 30:
        raise RuntimeError("occurrence_count_out_of_range")
    return selection, cases_doc, ordered


def run(args: argparse.Namespace) -> Path:
    selection, cases_doc, cases = load_frozen(args.selection, args.cases)
    run_id = args.run_id or dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-HDB2-P1-1"
    out = OUT / "live" / run_id
    if out.exists():
        raise RuntimeError(f"run_output_exists:{out}")
    raw_dir = out / "raw-api"
    raw_dir.mkdir(parents=True, exist_ok=False)
    before_hashes = protected_hashes()

    preflight_record = preflight()
    common.write_json(out / "preflight.json", preflight_record)
    if preflight_record.get("status") != "reachable":
        raise RuntimeError("strict_endpoint_preflight_failed")

    prompt_records: list[dict[str, Any]] = []
    model_records: list[dict[str, Any]] = []
    python_records: list[dict[str, Any]] = []
    call_records: list[dict[str, Any]] = []
    for sequence, case in enumerate(cases, start=1):
        record, model_record, final, request = semantic_call(case, sequence=sequence, raw_dir=raw_dir)
        prompt_records.append({"sequence": sequence, "occurrence_id": case.get("occurrence_id"), "request": request})
        # Keep the provider envelope classification and the Python-side
        # payload validation together so replay can distinguish transport,
        # parse, truncation, and semantic-validation failures.
        model_records.append({"sequence": sequence, **record, **model_record})
        python_records.append({"sequence": sequence, **final})
        call_records.append(record)

    comparisons = common.build_comparison(cases, python_records)
    metrics = common.build_metrics(cases, python_records, comparisons, {
        "candidate_key_invalid": sum("candidate_key_invalid" in x.get("validation", {}).get("errors", []) for x in model_records),
        "evidence_reference_invalid": sum("evidence_reference_invalid" in x.get("validation", {}).get("errors", []) for x in model_records),
    })
    all_usage = [x.get("usage", {}) for x in call_records if isinstance(x.get("usage"), Mapping)]
    elapsed = [float(x.get("elapsed_seconds")) for x in call_records if x.get("elapsed_seconds") is not None]
    operational = {
        "semantic_calls": len(cases),
        "preflight_calls": 1,
        "provider_failures": sum(x.get("classification") == "provider_request_failure" for x in call_records),
        "parse_failures": sum(x.get("classification") == "response_parse_failure" for x in call_records),
        "truncated_responses": sum(x.get("classification") == "response_truncated" for x in call_records),
        "valid_model_payloads": sum(x.get("validation", {}).get("valid") is True for x in model_records),
        "invalid_model_payloads": sum(x.get("validation", {}).get("valid") is False for x in model_records),
        "prompt_tokens": sum(int(x.get("prompt_tokens") or 0) for x in all_usage),
        "completion_tokens": sum(int(x.get("completion_tokens") or 0) for x in all_usage),
        "total_tokens": sum(int(x.get("total_tokens") or 0) for x in all_usage),
        "median_latency": statistics.median(elapsed) if elapsed else None,
        "max_latency": max(elapsed) if elapsed else None,
    }
    metrics["operational"] = operational
    metrics["candidate_only"] = True
    metrics["canonical_write_back"] = False
    audit = common.build_audit(cases, python_records)
    after_hashes = protected_hashes()
    if before_hashes != after_hashes:
        raise RuntimeError("protected_hash_changed_during_run")

    manifest = {
        "schema": "hdb2-p1-1-live-manifest-v1",
        "run_id": run_id,
        "run_version": RUN_VERSION,
        "algorithm_version": cases_doc.get("algorithm_version"),
        "prompt_version": PROMPT_VERSION,
        "model": MODEL,
        "temperature": 0,
        "thinking": "disabled",
        "endpoint": frozen_algorithm.STRICT_ENDPOINT,
        "selection_hash": selection.get("selection_hash"),
        "source_case_hash": selection.get("source_case_hash"),
        "occurrence_count": len(cases),
        "retrieval_calls": 0,
        "search_calls": 0,
        "candidate_only": True,
        "canonical_write_back": False,
        "preflight": preflight_record,
        "protected_hashes_before": before_hashes,
        "protected_hashes_after": after_hashes,
        "raw_api_files": sorted(str(x.relative_to(ROOT)) for x in raw_dir.glob("*.json")),
        "raw_api_hashes": {str(x.relative_to(ROOT)): file_hash(x) for x in sorted(raw_dir.glob("*.json"))},
        "call_records_hash": common.stable_hash(call_records),
        "created_at": utc_now(),
    }
    common.write_json(out / "manifest.json", manifest)
    common.write_json(out / "prompts.json", {"prompt_version": PROMPT_VERSION, "records": prompt_records})
    common.write_json(out / "model-decisions.json", {"records": model_records, "candidate_only": True, "canonical_write_back": False})
    common.write_json(out / "python-decisions.json", {"records": python_records, "candidate_only": True, "canonical_write_back": False})
    common.write_json(out / "comparison.json", comparisons)
    common.write_json(out / "metrics.json", metrics)
    common.write_json(out / "audit-cases.json", audit)
    # Review/derived projections are additive and deliberately separate from
    # the immutable live run and HDB1/HDB2-P1 inputs.
    common.write_json(common.ANNOTATION / "hdb2-p1-1-context-decisions.json", {"schema": "hdb2-p1-1-context-decisions-v1", "run_id": run_id, "records": python_records, "candidate_only": True, "canonical_write_back": False})
    common.write_json(common.DERIVED / "hdb2-p1-1-comparison.json", comparisons)
    common.write_json(common.DERIVED / "hdb2-p1-1-metrics.json", metrics)
    common.write_json(common.DERIVED / "hdb2-p1-1-audit-cases.json", audit)
    print(json.dumps({"run_dir": str(out.relative_to(ROOT)), "occurrences": len(cases), "semantic_calls": len(cases), "metrics": metrics}, ensure_ascii=False, indent=2, sort_keys=True))
    return out


def replay(run_dir: Path, *, selection_path: Path, cases_path: Path) -> Path:
    """Reproject frozen raw/model decisions without any network call."""
    selection, cases_doc, cases = load_frozen(selection_path, cases_path)
    model_doc = common.read_json(run_dir / "model-decisions.json", {}) or {}
    by_sequence = {int(row.get("sequence")): row for row in model_doc.get("records", []) if str(row.get("sequence", "")).isdigit()}
    python_records: list[dict[str, Any]] = []
    call_records: list[dict[str, Any]] = []
    for sequence, case in enumerate(cases, start=1):
        model = by_sequence.get(sequence, {})
        payload = model.get("payload", {}) if isinstance(model.get("payload"), Mapping) else {}
        if model.get("classification") == "parsed":
            validation = common.validate_model_payload(payload, case)
        else:
            validation = model.get("validation", {"valid": False, "errors": [str(model.get("classification") or "missing_model_record")], "payload": {}})
        python_records.append({"sequence": sequence, **common.python_decision(case, payload, validation)})
        call_records.append(model)
    comparisons = common.build_comparison(cases, python_records)
    metrics = common.build_metrics(cases, python_records, comparisons, {
        "candidate_key_invalid": sum("candidate_key_invalid" in x.get("validation", {}).get("errors", []) for x in call_records),
        "evidence_reference_invalid": sum("evidence_reference_invalid" in x.get("validation", {}).get("errors", []) for x in call_records),
    })
    metrics["replayed_without_api"] = True
    metrics["candidate_only"] = True
    metrics["canonical_write_back"] = False
    audit = common.build_audit(cases, python_records)
    common.write_json(run_dir / "python-decisions.json", {"records": python_records, "candidate_only": True, "canonical_write_back": False})
    common.write_json(run_dir / "comparison.json", comparisons)
    common.write_json(run_dir / "metrics.json", metrics)
    common.write_json(run_dir / "audit-cases.json", audit)
    common.write_json(common.ANNOTATION / "hdb2-p1-1-context-decisions.json", {"schema": "hdb2-p1-1-context-decisions-v1", "run_id": run_dir.name, "records": python_records, "candidate_only": True, "canonical_write_back": False})
    common.write_json(common.DERIVED / "hdb2-p1-1-comparison.json", comparisons)
    common.write_json(common.DERIVED / "hdb2-p1-1-metrics.json", metrics)
    common.write_json(common.DERIVED / "hdb2-p1-1-audit-cases.json", audit)
    manifest = common.read_json(run_dir / "manifest.json", {}) or {}
    manifest["postprocessing_replay_hash"] = common.stable_hash({"python": python_records, "comparison": comparisons, "metrics": metrics})
    manifest["replayed_without_api"] = True
    manifest.setdefault("raw_api_hashes", {str(x.relative_to(ROOT)): file_hash(x) for x in sorted((run_dir / "raw-api").glob("*.json"))})
    common.write_json(run_dir / "manifest.json", manifest)
    print(json.dumps({"run_dir": str(run_dir), "replayed_without_api": True, "metrics": metrics}, ensure_ascii=False, indent=2, sort_keys=True))
    return run_dir


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--selection", type=Path, default=common.ANNOTATION / "hdb2-p1-1-occurrence-selection.json")
    parser.add_argument("--cases", type=Path, default=common.DERIVED / "hdb2-p1-1-occurrence-cases.json")
    parser.add_argument("--run-id")
    parser.add_argument("--replay", type=Path, help="reproject an existing run without API calls")
    args = parser.parse_args()
    if args.replay:
        replay(args.replay if args.replay.is_absolute() else ROOT / args.replay, selection_path=args.selection, cases_path=args.cases)
        return 0
    run(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
