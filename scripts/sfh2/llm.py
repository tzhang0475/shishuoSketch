"""Bounded, replayable SFH2 semantic judgment transport.

SFH2 deliberately uses separate functions for existing-Person linking and
candidate-pair comparison.  Candidate keys are the only identity labels in
the prompts; production Person IDs remain a Python-side mapping.
"""

from __future__ import annotations

import collections
import statistics
import threading
import time
from pathlib import Path
from typing import Any, Mapping

from .common import (
    MODEL,
    OUTPUT_ROOT,
    ROOT,
    canonical_json,
    read_json,
    relative,
    stable_hash,
    text,
    utc_now,
    flags,
    write_json,
)

# The aliases above intentionally avoid importing the SFH1 transport's global
# output directory.  These local helpers keep all SFH2 raw work isolated.
from .common import compact_text

STRICT_ENDPOINT = "https://api.deepseek.com/beta/chat/completions"
PROMPT_VERSIONS = {
    "existing_person_link": "sfh2-hir1-existing-person-link-v1",
    "candidate_pair": "sfh2-hir1-candidate-pair-v1",
    "cluster_validation": "sfh2-hir1-cluster-validation-v1",
}


def _safe_slug(value: str) -> str:
    import re
    return re.sub(r"[^A-Za-z0-9_.-]+", "-", text(value)).strip("-") or "unit"


def _usage(response: Mapping[str, Any]) -> dict[str, int]:
    row = response.get("usage") if isinstance(response.get("usage"), Mapping) else {}
    return {
        "prompt_tokens": int(row.get("prompt_tokens") or 0),
        "completion_tokens": int(row.get("completion_tokens") or 0),
        "total_tokens": int(row.get("total_tokens") or 0),
    }


def _finish_reason(response: Mapping[str, Any]) -> str:
    choices = response.get("choices")
    if isinstance(choices, list) and choices and isinstance(choices[0], Mapping):
        return text(choices[0].get("finish_reason"))
    return ""


def _extract(response: Mapping[str, Any], function_name: str) -> tuple[Mapping[str, Any] | None, str | None]:
    import hng2_schema_controller as controller
    payload, _, error = controller.extract_strict_tool_payload(response, expected_function_name=function_name)
    return payload, error


def link_tool() -> dict[str, Any]:
    assessment = {
        "type": "object", "additionalProperties": False,
        "properties": {
            "candidate_key": {"type": "string"},
            "verdict": {"type": "string", "enum": ["support", "contradict", "plausible", "insufficient"]},
            "supporting_evidence_ids": {"type": "array", "items": {"type": "string"}},
            "contradicting_evidence_ids": {"type": "array", "items": {"type": "string"}},
            "reason_types": {"type": "array", "items": {"type": "string"}},
        },
        "required": ["candidate_key", "verdict", "supporting_evidence_ids", "contradicting_evidence_ids", "reason_types"],
    }
    item = {
        "type": "object", "additionalProperties": False,
        "properties": {
            "unit_id": {"type": "string"},
            "candidate_assessments": {"type": "array", "items": assessment},
            "preferred_candidate_key": {"type": ["string", "null"]},
            "resolution": {"type": "string", "enum": ["existing_person_supported", "ambiguous_existing_person", "no_existing_match", "insufficient_evidence"]},
            "explanation": {"type": "string"},
        },
        "required": ["unit_id", "candidate_assessments", "preferred_candidate_key", "resolution", "explanation"],
    }
    return {
        "type": "function",
        "function": {
            "name": "submit_sfh2_existing_person_links",
            "description": "Judge only the supplied candidate keys against supplied historical evidence.",
            "strict": True,
            "parameters": {"type": "object", "additionalProperties": False, "properties": {"records": {"type": "array", "items": item}}, "required": ["records"]},
        },
    }


def pair_tool() -> dict[str, Any]:
    item = {
        "type": "object", "additionalProperties": False,
        "properties": {
            "comparison_id": {"type": "string"},
            "verdict": {"type": "string", "enum": ["same_person", "distinct_persons", "plausibly_same", "insufficient_evidence"]},
            "supporting_evidence_ids": {"type": "array", "items": {"type": "string"}},
            "contradicting_evidence_ids": {"type": "array", "items": {"type": "string"}},
            "reason_types": {"type": "array", "items": {"type": "string"}},
            "explanation": {"type": "string"},
        },
        "required": ["comparison_id", "verdict", "supporting_evidence_ids", "contradicting_evidence_ids", "reason_types", "explanation"],
    }
    return {
        "type": "function",
        "function": {
            "name": "submit_sfh2_candidate_comparisons",
            "description": "Judge whether the two supplied occurrence dossiers refer to the same historical person.",
            "strict": True,
            "parameters": {"type": "object", "additionalProperties": False, "properties": {"records": {"type": "array", "maxItems": 1, "items": item}}, "required": ["records"]},
        },
    }


LINK_SYSTEM = """You are an evidence-grounded historical identity judge. Compare one occurrence with only the supplied existing-Person candidates. Do not invent persons, IDs, sources, or facts. A surface match alone is not identity evidence. Return only the forced function."""
PAIR_SYSTEM = """You are an evidence-grounded historical identity comparison judge. Decide whether the two supplied occurrence dossiers refer to the same historical person. Co-occurrence, same era, or similar names alone is insufficient. Preserve explicit distinctness. Return only the forced function."""
CLUSTER_SYSTEM = """You are an evidence-grounded historical identity cluster reviewer. Assess only the supplied observations and evidence. Do not invent persons or merge by surface alone. Return only the forced function."""


class SFH2Client:
    """Replayable transport with an immutable raw response directory."""

    def __init__(self, run_dir: Path, *, live: bool = False) -> None:
        self.run_dir = run_dir
        self.raw_dir = run_dir / "raw-api"
        self.raw_dir.mkdir(parents=True, exist_ok=True)
        self.live = live
        self._lock = threading.RLock()
        # Transport is an immutable record of provider attempts.  Cache hits
        # and offline misses are run-local bookkeeping, not provider
        # responses; older interrupted/replayed runs may contain those rows,
        # so do not carry them forward into a new transport file.
        self.records: list[dict[str, Any]] = [
            dict(row) for row in (read_json(run_dir / "transport.json", []) or [])
            if isinstance(row, Mapping) and row.get("classification") not in {"cache_hit", "offline_cache_miss"}
        ]
        self.initial_record_count = len(self.records)
        self.initial_record_count_by_stage = collections.Counter(text(row.get("stage")) for row in self.records)
        self.runtime_cache_hits = 0
        self.runtime_offline_cache_misses = 0
        self.runtime_cache_hits_by_stage: dict[str, int] = collections.defaultdict(int)
        self.runtime_offline_misses_by_stage: dict[str, int] = collections.defaultdict(int)
        self.runtime_cache_usage_by_stage: dict[str, list[dict[str, int]]] = collections.defaultdict(list)
        self.cache_path = OUTPUT_ROOT / "cache-index.json"
        self.cache = read_json(self.cache_path, {}) or {}
        sequence = []
        for path in self.raw_dir.glob("*.json"):
            prefix = path.name.split("-", 1)[0]
            if prefix.isdigit():
                sequence.append(int(prefix))
        self.sequence = max(sequence, default=0)

    def _record(self, row: Mapping[str, Any]) -> None:
        with self._lock:
            self.records.append(dict(row))

    def call(self, *, stage: str, unit_id: str, payload: Mapping[str, Any], tool: Mapping[str, Any], max_tokens: int = 1800) -> Mapping[str, Any] | None:
        version = PROMPT_VERSIONS[stage]
        function_name = text((tool.get("function") or {}).get("name"))
        packet_hash = stable_hash({"stage": stage, "prompt_version": version, "model": MODEL, "system": LINK_SYSTEM if stage == "existing_person_link" else PAIR_SYSTEM if stage == "candidate_pair" else CLUSTER_SYSTEM, "payload": payload, "tool": tool})
        cached = self.cache.get(packet_hash)
        if isinstance(cached, Mapping):
            raw_path = ROOT / text(cached.get("raw_path"))
            if raw_path.is_file():
                response = read_json(raw_path, {}) or {}
                parsed, error = _extract(response, function_name)
                if parsed is not None and error is None:
                    self.runtime_cache_hits += 1
                    self.runtime_cache_hits_by_stage[stage] += 1
                    self.runtime_cache_usage_by_stage[stage].append(_usage(response))
                    return parsed
        if not self.live:
            self.runtime_offline_cache_misses += 1
            self.runtime_offline_misses_by_stage[stage] += 1
            return None
        try:
            from smoke_deepseek import call_deepseek
        except Exception as exc:
            self._record({"stage": stage, "unit_id": unit_id, "packet_hash": packet_hash, "classification": "provider_import_failure", "exception_class": type(exc).__name__})
            return None
        system = LINK_SYSTEM if stage == "existing_person_link" else PAIR_SYSTEM if stage == "candidate_pair" else CLUSTER_SYSTEM
        messages = [{"role": "system", "content": system}, {"role": "user", "content": canonical_json(payload)}]
        for attempt in (1, 2):
            with self._lock:
                self.sequence += 1
                sequence = self.sequence
            started = time.monotonic()
            row: dict[str, Any] = {"sequence": sequence, "attempt": attempt, "stage": stage, "unit_id": unit_id, "packet_hash": packet_hash, "prompt_version": version, "model": MODEL, "start_time": utc_now()}
            try:
                response = call_deepseek(messages, model=MODEL, temperature=0, thinking={"type": "disabled"}, max_tokens=max_tokens, timeout=180, endpoint=STRICT_ENDPOINT, tools=[dict(tool)], tool_choice={"type": "function", "function": {"name": function_name}})
                raw_path = self.raw_dir / f"{sequence:05d}-{_safe_slug(stage)}-{_safe_slug(unit_id)}-attempt{attempt}.json"
                if raw_path.exists():
                    raise RuntimeError("sfh2_immutable_raw_response_exists")
                write_json(raw_path, response)
                row.update({"raw_path": relative(raw_path), "usage": _usage(response), "finish_reason": _finish_reason(response)})
                if _finish_reason(response) == "length":
                    row["classification"] = "response_truncated"
                    row["elapsed_seconds"] = round(time.monotonic() - started, 3)
                    row["end_time"] = utc_now()
                    self._record(row)
                    continue
                parsed, error = _extract(response, function_name)
                if error or parsed is None:
                    row.update({"classification": "response_parse_failure", "parse_error": error})
                    row["elapsed_seconds"] = round(time.monotonic() - started, 3)
                    row["end_time"] = utc_now()
                    self._record(row)
                    continue
                row["classification"] = "parsed"
                row["elapsed_seconds"] = round(time.monotonic() - started, 3)
                row["end_time"] = utc_now()
                self._record(row)
                self.cache[packet_hash] = {"raw_path": relative(raw_path), "stage": stage, "unit_id": unit_id, "prompt_version": version, "model": MODEL}
                write_json(self.cache_path, self.cache)
                return parsed
            except Exception as exc:
                message = text(exc)
                secret = __import__("os").environ.get("DEEPSEEK_API_KEY")
                if secret:
                    message = message.replace(secret, "[REDACTED]")
                row.update({"classification": "provider_request_failure", "exception_class": type(exc).__name__, "exception_message": message[:1200], "elapsed_seconds": round(time.monotonic() - started, 3), "end_time": utc_now()})
                self._record(row)
        return None

    def write_transport(self) -> None:
        write_json(self.run_dir / "transport.json", self.records)

    def _preserved_raw_usage(self) -> dict[str, Any]:
        """Summarize immutable raw responses even after an interrupted run.

        A provider process can be interrupted before it writes transport.json.
        The raw response files are still auditable and must be counted in the
        cost report, but they are not silently treated as current-prompt
        replays unless the packet cache validates them.
        """
        by_stage: dict[str, dict[str, int]] = collections.defaultdict(lambda: {"count": 0, "prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0})
        for path in sorted(self.raw_dir.glob("*.json")):
            stage = next((name for name in PROMPT_VERSIONS if f"-{_safe_slug(name)}-" in path.name), "unknown")
            response = read_json(path, {}) or {}
            usage = _usage(response)
            row = by_stage[stage]
            row["count"] += 1
            row["prompt_tokens"] += usage["prompt_tokens"]
            row["completion_tokens"] += usage["completion_tokens"]
            row["total_tokens"] += usage["total_tokens"]
        return {
            "count": sum(row["count"] for row in by_stage.values()),
            "prompt_tokens": sum(row["prompt_tokens"] for row in by_stage.values()),
            "completion_tokens": sum(row["completion_tokens"] for row in by_stage.values()),
            "total_tokens": sum(row["total_tokens"] for row in by_stage.values()),
            "by_stage": {key: dict(value) for key, value in sorted(by_stage.items())},
        }

    def metrics(self) -> dict[str, Any]:
        preserved_raw = self._preserved_raw_usage()
        by_stage: dict[str, dict[str, Any]] = {}
        for stage in PROMPT_VERSIONS:
            rows = [row for row in self.records if row.get("stage") == stage]
            replayed_usages = self.runtime_cache_usage_by_stage.get(stage, [])
            usages = [row.get("usage") or {} for row in rows]
            latencies = [float(row.get("elapsed_seconds") or 0) for row in rows if float(row.get("elapsed_seconds") or 0) > 0]
            provider_prompt = sum(int(item.get("prompt_tokens") or 0) for item in usages)
            provider_completion = sum(int(item.get("completion_tokens") or 0) for item in usages)
            provider_total = sum(int(item.get("total_tokens") or 0) for item in usages)
            replay_prompt = sum(int(item.get("prompt_tokens") or 0) for item in replayed_usages)
            replay_completion = sum(int(item.get("completion_tokens") or 0) for item in replayed_usages)
            replay_total = sum(int(item.get("total_tokens") or 0) for item in replayed_usages)
            initial_stage_count = int(self.initial_record_count_by_stage.get(stage, 0))
            new_rows = rows[initial_stage_count:] if initial_stage_count < len(rows) else []
            by_stage[stage] = {
                "calls": len(rows),
                "new_live_calls": len(new_rows) if self.live else 0,
                "cache_hits": self.runtime_cache_hits_by_stage.get(stage, 0),
                "offline_cache_misses": self.runtime_offline_misses_by_stage.get(stage, 0),
                "retries": sum(int(row.get("attempt") or 1) > 1 for row in rows),
                "provider_failures": sum(row.get("classification") == "provider_request_failure" for row in rows),
                "parse_failures": sum(row.get("classification") == "response_parse_failure" for row in rows),
                "truncations": sum(row.get("classification") == "response_truncated" for row in rows),
                "prompt_tokens": provider_prompt + replay_prompt,
                "completion_tokens": provider_completion + replay_completion,
                "total_tokens": provider_total + replay_total,
                "provider_prompt_tokens": provider_prompt,
                "provider_completion_tokens": provider_completion,
                "provider_total_tokens": provider_total,
                "replayed_prompt_tokens": replay_prompt,
                "replayed_completion_tokens": replay_completion,
                "replayed_total_tokens": replay_total,
                "median_latency_seconds": round(statistics.median(latencies), 3) if latencies else 0,
                "max_latency_seconds": round(max(latencies), 3) if latencies else 0,
            }
        provider_rows = self.records[self.initial_record_count:] if self.live else []
        all_usages = [row.get("usage") or {} for row in self.records]
        replayed_usages = [usage for values in self.runtime_cache_usage_by_stage.values() for usage in values]
        provider_prompt = sum(int(item.get("prompt_tokens") or 0) for item in all_usages)
        provider_completion = sum(int(item.get("completion_tokens") or 0) for item in all_usages)
        provider_total = sum(int(item.get("total_tokens") or 0) for item in all_usages)
        replay_prompt = sum(int(item.get("prompt_tokens") or 0) for item in replayed_usages)
        replay_completion = sum(int(item.get("completion_tokens") or 0) for item in replayed_usages)
        replay_total = sum(int(item.get("total_tokens") or 0) for item in replayed_usages)
        new_live_usages = [row.get("usage") or {} for row in provider_rows]
        return flags({
            "model": MODEL,
            "calls": len(self.records),
            "cache_hits": self.runtime_cache_hits,
            "new_live_calls": len(provider_rows),
            "offline_cache_misses": self.runtime_offline_cache_misses,
            "retries": sum(int(row.get("attempt") or 1) > 1 for row in self.records),
            "provider_failures": sum(row.get("classification") == "provider_request_failure" for row in self.records),
            "parse_failures": sum(row.get("classification") == "response_parse_failure" for row in self.records),
            "truncations": sum(row.get("classification") == "response_truncated" for row in self.records),
            "prompt_tokens": provider_prompt + replay_prompt,
            "completion_tokens": provider_completion + replay_completion,
            "total_tokens": provider_total + replay_total,
            "provider_prompt_tokens": provider_prompt,
            "provider_completion_tokens": provider_completion,
            "provider_total_tokens": provider_total,
            "replayed_prompt_tokens": replay_prompt,
            "replayed_completion_tokens": replay_completion,
            "replayed_total_tokens": replay_total,
            "new_live_prompt_tokens": sum(int(item.get("prompt_tokens") or 0) for item in new_live_usages),
            "new_live_completion_tokens": sum(int(item.get("completion_tokens") or 0) for item in new_live_usages),
            "new_live_total_tokens": sum(int(item.get("total_tokens") or 0) for item in new_live_usages),
            "preserved_raw_response_count": preserved_raw["count"],
            "preserved_raw_prompt_tokens": preserved_raw["prompt_tokens"],
            "preserved_raw_completion_tokens": preserved_raw["completion_tokens"],
            "preserved_raw_total_tokens": preserved_raw["total_tokens"],
            "preserved_raw_by_stage": preserved_raw["by_stage"],
            "by_stage": by_stage,
        })


def evidence_ids_in_payload(payload: Mapping[str, Any]) -> set[str]:
    ids: set[str] = set()
    def visit(value: Any, *, evidence_value: bool = False) -> None:
        if isinstance(value, Mapping):
            for key, item in value.items():
                if key.endswith("evidence_id") or key.endswith("evidence_ids") or key == "evidence":
                    visit(item, evidence_value=True)
                elif isinstance(item, (Mapping, list)):
                    visit(item)
        elif isinstance(value, list):
            for item in value:
                visit(item, evidence_value=evidence_value)
        elif isinstance(value, str) and evidence_value and value.strip():
            # Evidence IDs are intentionally namespaced by their producing
            # stage (profile, local-form, SFH1 packet, etc.).  Validation is
            # against the packet, not a hard-coded prefix list.
            ids.add(value)
    visit(payload)
    return ids


def validate_link_result(payload: Mapping[str, Any] | None, unit_id: str, candidate_keys: set[str], evidence_ids: set[str]) -> tuple[dict[str, Any] | None, list[str]]:
    errors: list[str] = []
    if not isinstance(payload, Mapping) or not isinstance(payload.get("records"), list):
        return None, ["provider_or_schema_failure"]
    rows = [row for row in payload.get("records", []) if isinstance(row, Mapping) and text(row.get("unit_id")) == unit_id]
    if not rows:
        return None, ["missing_unit_record"]
    row = dict(rows[0])
    preferred = row.get("preferred_candidate_key")
    if preferred == "null":
        errors.append("literal_null_candidate_key")
    if preferred is not None and text(preferred) not in candidate_keys:
        errors.append("unknown_candidate_key")
        row["preferred_candidate_key"] = None
    if text(row.get("resolution")) not in {"existing_person_supported", "ambiguous_existing_person", "no_existing_match", "insufficient_evidence"}:
        errors.append("invalid_resolution")
    normalized: list[dict[str, Any]] = []
    for assessment in row.get("candidate_assessments", []) or []:
        if not isinstance(assessment, Mapping):
            errors.append("assessment_not_object")
            continue
        item = dict(assessment)
        key = text(item.get("candidate_key"))
        if key not in candidate_keys:
            errors.append("assessment_unknown_candidate_key")
        for field in ("supporting_evidence_ids", "contradicting_evidence_ids"):
            values = item.get(field)
            if not isinstance(values, list) or any(text(value) not in evidence_ids for value in values):
                errors.append(f"invalid_{field}")
                item[field] = []
            else:
                item[field] = sorted(set(text(value) for value in values))
        normalized.append(item)
    row["candidate_assessments"] = normalized
    return (row if not errors else None), sorted(set(errors))


def validate_pair_result(payload: Mapping[str, Any] | None, comparison_id: str, evidence_ids: set[str]) -> tuple[dict[str, Any] | None, list[str]]:
    if not isinstance(payload, Mapping) or not isinstance(payload.get("records"), list):
        return None, ["provider_or_schema_failure"]
    rows = [row for row in payload.get("records", []) if isinstance(row, Mapping) and text(row.get("comparison_id")) == comparison_id]
    if not rows:
        return None, ["missing_comparison_record"]
    row = dict(rows[0])
    errors: list[str] = []
    if text(row.get("verdict")) not in {"same_person", "distinct_persons", "plausibly_same", "insufficient_evidence"}:
        errors.append("invalid_pair_verdict")
    for field in ("supporting_evidence_ids", "contradicting_evidence_ids"):
        values = row.get(field)
        if not isinstance(values, list) or any(text(value) not in evidence_ids for value in values):
            errors.append(f"invalid_{field}")
            row[field] = []
        else:
            row[field] = sorted(set(text(value) for value in values))
    row["reason_types"] = sorted(set(text(value) for value in row.get("reason_types", []) or [] if text(value)))
    return (row if not errors else None), sorted(set(errors))
