#!/usr/bin/env python3
"""Run the isolated HNG2-C.2 Evidence-Atom validation.

The runner reuses the exact HNG2-C.1 regression and held-out units.  It makes
no search, retrieval, frontier, graph, H0A, or canonical writes.
"""

from __future__ import annotations

import argparse
import collections
import datetime as dt
import json
import os
import re
import statistics
import sys
import time
from pathlib import Path
from typing import Any, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import historical_context_algorithm as algorithm  # noqa: E402
import hng2_schema_controller as controller  # noqa: E402
import run_hng2_consolidation as consolidation  # noqa: E402
import run_hng2_read_fill_validation as c1  # noqa: E402
from smoke_deepseek import call_deepseek  # noqa: E402


OUT = ROOT / "data/generated/hng2-evidence-atom-validation"
MODEL = "deepseek-v4-flash"
RUN_VERSION = "hng2-c2-evidence-atom-v1"
PROMPT_VERSION = "hng2-c2-evidence-atoms-v1"
C1_RUN = ROOT / "data/generated/hng2-read-fill-validation/live/20260825T-HNG2-C1-01"
C1_CORRECTION = ROOT / "data/generated/hng2-read-fill-validation/live-correction/20260825T-HNG2-C1-TFIX-01"


def read_json(path: Path, default: Any = None) -> Any:
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else default


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def build_selection() -> dict[str, Any]:
    frozen = c1.build_selection()
    stored = read_json(ROOT / "data/generated/hng2-read-fill-validation/selection.json", {}) or {}
    for key in ("person_regression", "temporal_regression", "heldout"):
        if stored and stored.get(key) != frozen.get(key):
            raise RuntimeError(f"c1_frozen_selection_mismatch:{key}")
    return {
        "stage": "hng2-c2-evidence-atom-validation",
        "algorithm_version": RUN_VERSION,
        "frozen_before_live": True,
        "selection_source": "exact HNG2-C.1 regression and held-out selection",
        "person_regression": frozen["person_regression"],
        "temporal_regression": frozen["temporal_regression"],
        "heldout": frozen["heldout"],
        "person_regression_count": len(frozen["person_regression"]),
        "temporal_regression_count": len(frozen["temporal_regression"]),
        "heldout_count": len(frozen["heldout"]),
        "semantic_call_count": len(frozen["person_regression"]) * 2 + len(frozen["temporal_regression"]) * 2 + len(frozen["heldout"]) * 4,
        "no_new_targets": True,
        "canonical_write_back": False,
    }


def ensure_selection() -> dict[str, Any]:
    selection = build_selection()
    path = OUT / "selection.json"
    if path.is_file() and c1.stable_hash(read_json(path, {})) != c1.stable_hash(selection):
        raise RuntimeError("c2_frozen_selection_mismatch")
    if not path.is_file():
        write_json(path, selection)
    if selection["semantic_call_count"] != 44:
        raise RuntimeError("semantic_call_count_not_44")
    return selection


def _usage(response: Mapping[str, Any]) -> dict[str, int]:
    raw = response.get("usage") if isinstance(response.get("usage"), Mapping) else {}
    return {key: int(raw.get(key) or 0) for key in ("prompt_tokens", "completion_tokens", "total_tokens")}


def _finish_reason(response: Mapping[str, Any]) -> str | None:
    choices = response.get("choices") if isinstance(response, Mapping) else None
    if not isinstance(choices, list) or not choices or not isinstance(choices[0], Mapping):
        return None
    return str(choices[0].get("finish_reason") or "") or None


def _safe_error(exc: Exception) -> dict[str, Any]:
    message = str(exc)
    secret = os.environ.get("DEEPSEEK_API_KEY")
    if secret:
        message = message.replace(secret, "[REDACTED]")
    return {
        "exception_class": type(exc).__name__,
        "exception_message": message,
        "http_status": getattr(exc, "http_status", None),
    }


def preflight() -> dict[str, Any]:
    started = time.monotonic()
    record: dict[str, Any] = {"start_time": utc_now(), "model": MODEL}
    try:
        response = call_deepseek(
            [{"role": "user", "content": "Reply only with OK"}],
            model=MODEL,
            temperature=0,
            max_tokens=16,
            thinking={"type": "disabled"},
            timeout=60,
        )
        record.update({"status": "reachable", "usage": _usage(response), "response_model": response.get("model")})
    except Exception as exc:
        record.update({"status": "live_network_unavailable", **_safe_error(exc)})
    record.update({"elapsed_seconds": round(time.monotonic() - started, 3), "end_time": utc_now()})
    return record


def semantic_call(*, lane: str, unit_id: str, prompt: Mapping[str, Any], raw_dir: Path, sequence: int) -> tuple[dict[str, Any], Mapping[str, Any] | None]:
    expected = {
        "person_read": algorithm.PERSON_ATOM_FUNCTION,
        "person_fill": algorithm.PERSON_FILL_FUNCTION,
        "temporal_read": algorithm.TEMPORAL_ATOM_FUNCTION,
        "temporal_fill": algorithm.TEMPORAL_FILL_FUNCTION,
    }[lane]
    systems = {
        "person_read": algorithm.PERSON_ATOM_SYSTEM,
        "person_fill": algorithm.PERSON_ATOM_FILL_SYSTEM,
        "temporal_read": algorithm.TEMPORAL_ATOM_SYSTEM,
        "temporal_fill": algorithm.TEMPORAL_ATOM_FILL_SYSTEM,
    }
    budgets = {"person_read": 900, "person_fill": 900, "temporal_read": 750, "temporal_fill": 750}
    started = time.monotonic()
    record: dict[str, Any] = {
        "sequence": sequence,
        "lane": lane,
        "unit_id": unit_id,
        "start_time": utc_now(),
        "model": MODEL,
        "prompt_version": PROMPT_VERSION,
        "input_hash": c1.stable_hash(prompt),
    }
    try:
        response = call_deepseek(
            [
                {"role": "system", "content": systems[lane]},
                {"role": "user", "content": json.dumps(prompt, ensure_ascii=False, sort_keys=True)},
            ],
            model=MODEL,
            temperature=0,
            thinking={"type": "disabled"},
            max_tokens=budgets[lane],
            timeout=180,
            endpoint=algorithm.STRICT_ENDPOINT,
            tools=[algorithm.evidence_atom_function_definition(lane)],
            tool_choice=algorithm.evidence_atom_tool_choice(lane),
        )
        raw_path = raw_dir / f"{sequence:03d}-{lane}-{re.sub(r'[^A-Za-z0-9_.-]+', '-', unit_id)}.json"
        if raw_path.exists():
            raise RuntimeError(f"immutable_raw_response_exists:{raw_path}")
        write_json(raw_path, response)
        finish = _finish_reason(response)
        record.update({
            "status": "response",
            "finish_reason": finish,
            "usage": _usage(response),
            "raw_path": str(raw_path.relative_to(ROOT)),
        })
        if finish == "length":
            record["classification"] = "response_truncated"
            return record, None
        payload, channel, error = controller.extract_strict_tool_payload(response, expected_function_name=expected)
        if error:
            record.update({"classification": "response_parse_failure", "response_channel": channel, "parse_error": error})
            return record, None
        record.update({"classification": "parsed", "response_channel": channel})
        return record, payload
    except Exception as exc:
        record.update({"status": "provider_request_failure", "classification": "provider_request_failure", **_safe_error(exc)})
        return record, None
    finally:
        record.update({"elapsed_seconds": round(time.monotonic() - started, 3), "end_time": utc_now()})


def _first_target_window(target: Mapping[str, Any], windows: Sequence[Mapping[str, Any]]) -> tuple[str, str, str]:
    surface = str(target.get("surface") or "")
    for row in windows:
        text = str(row.get("evidence_text") or "")
        if surface and surface in text:
            return str(row.get("ref") or ""), text, surface
    return "", "", surface


def _fixture_payload(lane: str, target: Mapping[str, Any], windows: Sequence[Mapping[str, Any]], atoms: Sequence[Mapping[str, Any]] | None = None) -> dict[str, Any]:
    ref, text, surface = _first_target_window(target, windows)
    if lane == "person_read":
        return {"atoms": [{"atom_id": "p0", "atom_kind": "identity_name", "subject_surface": surface, "predicate_surface": "", "object_surface": "", "evidence_ref": ref, "exact_span": surface, "certainty": "explicit"}]} if ref else {"atoms": []}
    if lane == "person_fill":
        return {"entities": [{"entity_key": "e0", "surface": surface, "entity_kind": "named_person", "reference_form": "full_name", "evidence_refs": [ref]}], "relations": []} if atoms and ref else {"entities": [], "relations": []}
    temporal_patterns = ("正始之音", "咸和六年", "永和九年", "武帝")
    if lane == "temporal_read":
        for row in windows:
            evidence = str(row.get("evidence_text") or "")
            for value in temporal_patterns:
                if value not in evidence:
                    continue
                temporal = "正始" if value == "正始之音" else value
                role = "quoted_precedent" if value == "正始之音" else ("later_outcome" if "遇害" in evidence else "scene_time")
                return {"atoms": [{"atom_id": "t0", "temporal_surface": temporal, "reference_surface": value, "role_hint": role, "evidence_ref": row.get("ref"), "exact_span": value, "certainty": "explicit"}]}
        return {"atoms": []}
    if atoms:
        atom = atoms[0]
        surface = str(atom.get("temporal_surface") or "")
        return {"temporal_assertions": [{"temporal_id": "t0", "temporal_surface": surface, "temporal_type": "exact_year" if "年" in surface else "reign_period", "temporal_role": atom.get("role_hint"), "reference_surface": atom.get("reference_surface"), "evidence_ref": atom.get("evidence_ref"), "exact_span": atom.get("exact_span"), "confidence": "high"}]}
    return {"temporal_assertions": []}


def _run_person(unit: Mapping[str, Any], raw_dir: Path, sequence: int, live: bool, known_evidence: Mapping[str, Mapping[str, Any]]) -> tuple[dict[str, Any], int]:
    target = unit["target"]
    windows = unit.get("windows") or unit.get("person_windows") or []
    p1_prompt = algorithm.person_read_prompt(target, windows)
    if live:
        p1_transport, p1 = semantic_call(lane="person_read", unit_id=str(unit["unit_id"]), prompt=p1_prompt, raw_dir=raw_dir, sequence=sequence)
    else:
        p1_transport, p1 = {"classification": "fixture", "usage": {}}, _fixture_payload("person_read", target, windows)
    sequence += 1
    p1_validation = algorithm.validate_person_atoms(p1, windows) if p1 is not None else None
    p2_prompt = algorithm.person_atom_fill_prompt(target, p1_validation or {"valid_atoms": []}, windows)
    if live:
        p2_transport, p2 = semantic_call(lane="person_fill", unit_id=str(unit["unit_id"]), prompt=p2_prompt, raw_dir=raw_dir, sequence=sequence)
    else:
        p2_transport, p2 = {"classification": "fixture", "usage": {}}, _fixture_payload("person_fill", target, windows, (p1_validation or {}).get("valid_atoms"))
    sequence += 1
    fill_windows = [row for row in windows if str(row.get("ref")) in {str(atom.get("evidence_ref")) for atom in (p1_validation or {}).get("valid_atoms", [])}]
    p2_validation = algorithm.validate_person_fill(p2, fill_windows) if p2 is not None else None
    normalization = algorithm.normalize_person_fill(p2_validation or {}, case=unit["case"], windows=fill_windows, known_evidence=known_evidence) if p2_validation is not None else None
    return {
        "unit_id": unit["unit_id"],
        "group": unit["group"],
        "target": target,
        "evidence_windows": windows,
        "person_read": {"prompt": p1_prompt, "transport": p1_transport, "payload": p1, "validation": p1_validation},
        "person_fill": {"prompt": p2_prompt, "transport": p2_transport, "payload": p2, "validation": p2_validation},
        "normalization": normalization,
    }, sequence


def _run_temporal(unit: Mapping[str, Any], raw_dir: Path, sequence: int, live: bool) -> tuple[dict[str, Any], int]:
    story = unit["story"]
    windows = unit.get("windows") or unit.get("temporal_windows") or []
    t1_prompt = algorithm.temporal_read_prompt(story, windows)
    if live:
        t1_transport, t1 = semantic_call(lane="temporal_read", unit_id=str(unit["unit_id"]), prompt=t1_prompt, raw_dir=raw_dir, sequence=sequence)
    else:
        t1_transport, t1 = {"classification": "fixture", "usage": {}}, _fixture_payload("temporal_read", {}, windows)
    sequence += 1
    t1_validation = algorithm.validate_temporal_atoms(t1, windows) if t1 is not None else None
    t2_prompt = algorithm.temporal_atom_fill_prompt(story, t1_validation or {"valid_atoms": []}, windows)
    if live:
        t2_transport, t2 = semantic_call(lane="temporal_fill", unit_id=str(unit["unit_id"]), prompt=t2_prompt, raw_dir=raw_dir, sequence=sequence)
    else:
        t2_transport, t2 = {"classification": "fixture", "usage": {}}, _fixture_payload("temporal_fill", {}, windows, (t1_validation or {}).get("valid_atoms"))
    sequence += 1
    fill_windows = [row for row in windows if str(row.get("ref")) in {str(atom.get("evidence_ref")) for atom in (t1_validation or {}).get("valid_atoms", [])}]
    t2_validation = algorithm.validate_temporal_fill(t2, fill_windows) if t2 is not None else None
    normalization = algorithm.normalize_story_temporal(t2_validation or {}, story_id=str(unit["story_id"])) if t2_validation is not None else None
    return {
        "unit_id": unit["unit_id"],
        "group": unit["group"],
        "story": story,
        "category": unit.get("category"),
        "evidence_windows": windows,
        "temporal_read": {"prompt": t1_prompt, "transport": t1_transport, "payload": t1, "validation": t1_validation},
        "temporal_fill": {"prompt": t2_prompt, "transport": t2_transport, "payload": t2, "validation": t2_validation},
        "normalization": normalization,
    }, sequence


def _c1_results() -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    person = read_json(C1_RUN / "person-results.json", []) or []
    temporal = read_json(C1_RUN / "temporal-results.json", []) or []
    heldout = read_json(C1_RUN / "heldout-results.json", []) or []
    correction = read_json(C1_CORRECTION / "temporal-result.json", {}) or {}
    if correction:
        temporal = [correction if str((row.get("story") or {}).get("story_id")) == "02-yanyu-011" else row for row in temporal]
        if not any(str((row.get("story") or {}).get("story_id")) == "01-dexing-017" for row in temporal):
            temporal = [correction, *[row for row in temporal if str((row.get("story") or {}).get("story_id")) != "02-yanyu-011"]]
    return person, temporal, heldout


def _old_grounding_counts() -> dict[str, Any]:
    person, temporal, heldout = _c1_results()
    person_rows = [*person, *[row["person"] for row in heldout]]
    temporal_rows = [*temporal, *[row["temporal"] for row in heldout]]

    def lane(rows: Sequence[Mapping[str, Any]], key: str) -> dict[str, Any]:
        returned = grounded = 0
        reasons: collections.Counter[str] = collections.Counter()
        for row in rows:
            validation = ((row.get(key) or {}).get("validation") or {})
            valid = validation.get("valid_observations", [])
            rejected = validation.get("rejected_observations", [])
            grounded += len(valid)
            returned += len(valid) + len(rejected)
            reasons.update(str(item.get("reason")) for item in rejected)
        return {"returned": returned, "grounded": grounded, "rejected": returned - grounded, "rejection_reasons": dict(sorted(reasons.items()))}

    return {"person_read": lane(person_rows, "person_read"), "temporal_read": lane(temporal_rows, "temporal_read")}


def _target_rows(result: Mapping[str, Any]) -> list[dict[str, Any]]:
    surface = str((result.get("target") or {}).get("surface") or "")
    return [row for row in (result.get("normalization") or {}).get("entities", []) if row.get("surface") == surface]


def summarize(person: Sequence[Mapping[str, Any]], temporal: Sequence[Mapping[str, Any]], heldout: Sequence[Mapping[str, Any]], preflight_record: Mapping[str, Any], *, live: bool) -> tuple[dict[str, Any], dict[str, Any]]:
    person_rows = [*person, *[row["person"] for row in heldout]]
    temporal_rows = [*temporal, *[row["temporal"] for row in heldout]]
    transports = []
    for row in person_rows:
        transports.extend([(row.get("person_read") or {}).get("transport") or {}, (row.get("person_fill") or {}).get("transport") or {}])
    for row in temporal_rows:
        transports.extend([(row.get("temporal_read") or {}).get("transport") or {}, (row.get("temporal_fill") or {}).get("transport") or {}])

    def read_counts(rows: Sequence[Mapping[str, Any]], key: str) -> dict[str, Any]:
        returned = grounded = 0
        reasons: collections.Counter[str] = collections.Counter()
        for row in rows:
            payload = (row.get(key) or {}).get("payload") or {}
            validation = (row.get(key) or {}).get("validation") or {}
            returned += len(payload.get("atoms", [])) if isinstance(payload.get("atoms"), list) else 0
            grounded += len(validation.get("valid_atoms", []))
            reasons.update(str(item.get("reason")) for item in validation.get("rejected_atoms", []))
        return {"atoms_returned": returned, "atoms_grounded": grounded, "atoms_rejected": returned - grounded, "rejection_reasons": dict(sorted(reasons.items()))}

    person_fill = {
        "valid_entities": sum(len(((row.get("person_fill") or {}).get("validation") or {}).get("valid_entities", [])) for row in person_rows),
        "rejected_entities": sum(len(((row.get("person_fill") or {}).get("validation") or {}).get("rejected_entities", [])) for row in person_rows),
        "valid_relations": sum(len(((row.get("person_fill") or {}).get("validation") or {}).get("valid_relations", [])) for row in person_rows),
        "rejected_relations": sum(len(((row.get("person_fill") or {}).get("validation") or {}).get("rejected_relations", [])) for row in person_rows),
        "normalized_relations": sum(len((row.get("normalization") or {}).get("relations", [])) for row in person_rows),
        "collapsed_self_relations_rejected": sum(len((row.get("normalization") or {}).get("rejected_normalized_relations", [])) for row in person_rows),
    }
    target_statuses = collections.Counter(
        str(entity.get("identity_status"))
        for row in person_rows
        for entity in _target_rows(row)
    )
    person_fill["target_identity_statuses"] = dict(sorted(target_statuses.items()))
    person_fill["unsupported_relations"] = person_fill["rejected_relations"]

    normalized_temporal = [item for row in temporal_rows for item in (row.get("normalization") or {}).get("temporal_assertions", [])]
    temporal_fill = {
        "valid_assertions": sum(len(((row.get("temporal_fill") or {}).get("validation") or {}).get("valid_temporal_assertions", [])) for row in temporal_rows),
        "rejected_assertions": sum(len(((row.get("temporal_fill") or {}).get("validation") or {}).get("rejected_temporal_assertions", [])) for row in temporal_rows),
        "h0a_compatible": sum((row.get("h0a") or {}).get("status") == "compatible" for row in normalized_temporal),
        "h0a_conflicting": sum((row.get("h0a") or {}).get("status") == "conflict" for row in normalized_temporal),
        "scene_time_eligible": sum(bool(row.get("scene_constraint_candidate")) for row in normalized_temporal),
        "later_outcome_excluded": sum(row.get("temporal_role") == "later_outcome" and not row.get("scene_constraint_candidate") for row in normalized_temporal),
        "quoted_precedent_or_background_excluded": sum(row.get("temporal_role") in {"quoted_precedent", "background_context"} and not row.get("scene_constraint_candidate") for row in normalized_temporal),
    }

    nonperson_pid = []
    projected_self = []
    for row in person_rows:
        for entity in (row.get("normalization") or {}).get("entities", []):
            if entity.get("entity_kind") not in algorithm.PERSON_LIKE_ENTITY_KINDS and entity.get("resolved_person_id"):
                nonperson_pid.append({"unit_id": row.get("unit_id"), "surface": entity.get("surface"), "person_id": entity.get("resolved_person_id")})
        for relation in (row.get("normalization") or {}).get("relations", []):
            if relation.get("relation_class") != "identity_name" and relation.get("person_a") and relation.get("person_a") == relation.get("person_b"):
                projected_self.append({"unit_id": row.get("unit_id"), "relation": relation})

    by_target = {str((row.get("target") or {}).get("surface")): _target_rows(row) for row in person_rows}
    def resolves(surface: str, canonical: str) -> bool:
        return any(row.get("identity_status") == "resolved_existing" and row.get("resolved_person_id") and str((row.get("resolver_result") or {}).get("resolved_label") or "") == canonical for row in by_target.get(surface, []))

    quoted_atoms = [atom for row in temporal_rows if str((row.get("story") or {}).get("story_id")) == "04-wenxue-022" for atom in ((row.get("temporal_read") or {}).get("validation") or {}).get("valid_atoms", [])]
    later_rows = [item for row in temporal_rows if str((row.get("story") or {}).get("story_id")) == "06-yaliang-017" for item in (row.get("normalization") or {}).get("temporal_assertions", [])]
    reign_rows = [item for row in temporal_rows if str((row.get("story") or {}).get("story_id")) == "01-dexing-017" for item in (row.get("normalization") or {}).get("temporal_assertions", [])]
    regressions = {
        "yi_resolves_wangyi": resolves("廙", "王廙"),
        "yu_taiwei_resolves_yuliang": resolves("庾太尉", "庾亮"),
        "shan_tao_resolves": resolves("山濤", "山濤"),
        "xuan_unresolved_if_unsupported": not any(row.get("identity_status") == "resolved_existing" for row in by_target.get("宣", [])),
        "yu_unresolved_if_unsupported": not any(row.get("identity_status") == "resolved_existing" for row in by_target.get("譽", [])),
        "chen_qian_candidate_only": any(row.get("identity_status") == "resolved_new_candidate" for row in by_target.get("陳騫", [])),
        "location_never_receives_person_id": not nonperson_pid,
        "non_identity_self_relation_not_projected": not projected_self,
        "zhengshi_quoted_precedent_survives_read": any("正始之音" in str(atom.get("exact_span") or "") and atom.get("role_hint") == "quoted_precedent" for atom in quoted_atoms),
        "later_outcome_not_scene_time": bool(later_rows) and all(not row.get("scene_constraint_candidate") for row in later_rows if row.get("temporal_role") == "later_outcome"),
        "dexing_017_reign_h0a_compatible": any((row.get("h0a") or {}).get("status") == "compatible" for row in reign_rows),
    }

    usage = {key: sum(int((row.get("usage") or {}).get(key) or 0) for row in transports) for key in ("prompt_tokens", "completion_tokens", "total_tokens")}
    latencies = [float(row["elapsed_seconds"]) for row in transports if row.get("status") == "response" and row.get("elapsed_seconds") is not None]
    metrics = {
        "live": live,
        "preflight": dict(preflight_record),
        "semantic_calls": len(transports),
        "parsed_calls": sum(row.get("classification") == "parsed" for row in transports),
        "response_truncated": sum(row.get("classification") == "response_truncated" for row in transports),
        "provider_or_parse_failures": sum(row.get("classification") in {"provider_request_failure", "response_parse_failure"} for row in transports),
        "token_usage": usage,
        "median_latency_seconds": statistics.median(latencies) if latencies else None,
        "maximum_latency_seconds": max(latencies) if latencies else None,
        "person_read": read_counts(person_rows, "person_read"),
        "person_fill": person_fill,
        "temporal_read": read_counts(temporal_rows, "temporal_read"),
        "temporal_fill": temporal_fill,
        "normalization_anomalies": {"nonperson_with_person_id": nonperson_pid, "projected_nonidentity_self_relation": projected_self},
        "regression_checks": regressions,
        "canonical_write_back": False,
    }
    before = _old_grounding_counts()
    comparison = {
        "hng2_c1": before,
        "hng2_c2": {"person_read": metrics["person_read"], "temporal_read": metrics["temporal_read"]},
        "person_rejection_delta": metrics["person_read"]["atoms_rejected"] - before["person_read"]["rejected"],
        "temporal_rejection_delta": metrics["temporal_read"]["atoms_rejected"] - before["temporal_read"]["rejected"],
        "person_rejection_decreased": metrics["person_read"]["atoms_rejected"] < before["person_read"]["rejected"],
        "temporal_rejection_decreased": metrics["temporal_read"]["atoms_rejected"] < before["temporal_read"]["rejected"],
    }
    return metrics, comparison


def evaluation_report(
    metrics: Mapping[str, Any],
    comparison: Mapping[str, Any],
    person: Sequence[Mapping[str, Any]],
    temporal: Sequence[Mapping[str, Any]],
    heldout: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    heldout_rows: list[dict[str, Any]] = []
    for row in heldout:
        person_result = row["person"]
        temporal_result = row["temporal"]
        target_rows = _target_rows(person_result)
        temporal_projection = (temporal_result.get("normalization") or {}).get("temporal_assertions", [])
        heldout_rows.append(
            {
                "story_id": row.get("story_id"),
                "target_surface": row.get("target_surface"),
                "category": row.get("category"),
                "person_atoms_grounded": len(((person_result.get("person_read") or {}).get("validation") or {}).get("valid_atoms", [])),
                "person_relations_valid": len(((person_result.get("person_fill") or {}).get("validation") or {}).get("valid_relations", [])),
                "target_identity_statuses": [item.get("identity_status") for item in target_rows],
                "target_person_ids": [item.get("resolved_person_id") for item in target_rows if item.get("resolved_person_id")],
                "temporal_atoms_grounded": len(((temporal_result.get("temporal_read") or {}).get("validation") or {}).get("valid_atoms", [])),
                "temporal_assertions_valid": len(((temporal_result.get("temporal_fill") or {}).get("validation") or {}).get("valid_temporal_assertions", [])),
                "scene_time_candidates": sum(bool(item.get("scene_constraint_candidate")) for item in temporal_projection),
                "excluded_temporal_roles": [item.get("temporal_role") for item in temporal_projection if not item.get("scene_constraint_candidate")],
            }
        )
    checks = metrics.get("regression_checks") or {}
    remaining_layers: list[dict[str, str]] = []
    if not checks.get("yi_resolves_wangyi"):
        remaining_layers.append({"case": "廙 / 王廙", "failure_layer": "identity resolver", "reason": "grounded evidence and Fill survived, but the abbreviated target remained unresolved"})
    if not checks.get("dexing_017_reign_h0a_compatible"):
        remaining_layers.append({"case": "01-dexing-017 武帝", "failure_layer": "Read extraction", "reason": "model-visible evidence contained 武帝, but T1 did not return that atom"})
    return {
        "grounding_improvement": {
            "person_rejection_decreased": comparison.get("person_rejection_decreased"),
            "temporal_rejection_decreased": comparison.get("temporal_rejection_decreased"),
        },
        "heldout": heldout_rows,
        "normalization_invariants": metrics.get("normalization_anomalies"),
        "regression_checks": checks,
        "remaining_failure_layers": remaining_layers,
        "person_lane_ready_to_freeze": not any(row["failure_layer"] == "identity resolver" for row in remaining_layers),
        "temporal_needs_final_h0a_validation": any(row["failure_layer"] in {"Read extraction", "temporal normalizer"} for row in remaining_layers),
        "candidate_projection_only": True,
        "canonical_write_back": False,
    }


def run(selection: Mapping[str, Any], *, live: bool, run_id: str) -> dict[str, Any]:
    person_units, temporal_units, heldout_units = c1.build_units(selection)
    known = consolidation.load_previous_findings()
    base = OUT / ("live" if live else "offline-replay") / run_id
    if live and base.exists():
        raise RuntimeError(f"immutable_live_run_exists:{base}")
    raw_dir = base / "raw-api"
    raw_dir.mkdir(parents=True, exist_ok=True)
    preflight_record = preflight() if live else {"status": "not_executed_offline", "api_calls": 0}
    write_json(base / "preflight.json", preflight_record)
    if live and preflight_record.get("status") != "reachable":
        write_json(base / "manifest.json", {"status": "live_network_unavailable", "semantic_calls": 0, "canonical_write_back": False})
        raise RuntimeError("live_network_unavailable")

    sequence = 1
    person_results: list[dict[str, Any]] = []
    temporal_results: list[dict[str, Any]] = []
    heldout_results: list[dict[str, Any]] = []
    for unit in person_units:
        result, sequence = _run_person(unit, raw_dir, sequence, live, known["evidence_refs"])
        person_results.append(result)
    for unit in temporal_units:
        result, sequence = _run_temporal(unit, raw_dir, sequence, live)
        temporal_results.append(result)
    heldout_start = sequence
    for unit in heldout_units:
        person_result, sequence = _run_person(unit, raw_dir, sequence, live, known["evidence_refs"])
        temporal_result, sequence = _run_temporal(unit, raw_dir, sequence, live)
        heldout_results.append({
            "unit_id": unit["unit_id"],
            "story_id": unit["story_id"],
            "target_surface": unit["target"]["surface"],
            "category": unit.get("category"),
            "person": person_result,
            "temporal": temporal_result,
        })
    if live and sequence - heldout_start != 20:
        raise RuntimeError("heldout_call_count_mismatch")
    if sequence - 1 != 44:
        raise RuntimeError(f"semantic_call_count_mismatch:{sequence - 1}")

    metrics, comparison = summarize(person_results, temporal_results, heldout_results, preflight_record, live=live)
    evaluation = evaluation_report(metrics, comparison, person_results, temporal_results, heldout_results)
    write_json(base / "person-results.json", person_results)
    write_json(base / "temporal-results.json", temporal_results)
    write_json(base / "heldout-results.json", heldout_results)
    write_json(base / "comparison-with-hng2-c1.json", comparison)
    write_json(base / "evaluation.json", evaluation)
    write_json(base / "metrics.json", metrics)
    write_json(base / "manifest.json", {
        "stage": "hng2-c2-evidence-atom-grounding-fix",
        "run_id": run_id,
        "status": "complete",
        "algorithm_version": RUN_VERSION,
        "selection_hash": c1.stable_hash(selection),
        "semantic_calls": sequence - 1,
        "preflight_calls": 1 if live else 0,
        "no_retries": True,
        "no_search": True,
        "no_new_targets": True,
        "raw_api_immutable": True,
        "candidate_projection_only": True,
        "canonical_write_back": False,
    })
    return {"output": str(base), "metrics": metrics, "comparison": comparison, "evaluation": evaluation}


def summarize_existing_run(run_id: str) -> dict[str, Any]:
    """Recompute deterministic reports from immutable live responses/results."""

    base = OUT / "live" / run_id
    person = read_json(base / "person-results.json", []) or []
    temporal = read_json(base / "temporal-results.json", []) or []
    heldout = read_json(base / "heldout-results.json", []) or []
    preflight_record = read_json(base / "preflight.json", {}) or {}
    if len(person) != 8 or len(temporal) != 4 or len(heldout) != 5:
        raise RuntimeError("stored_run_shape_invalid")
    metrics, comparison = summarize(person, temporal, heldout, preflight_record, live=True)
    evaluation = evaluation_report(metrics, comparison, person, temporal, heldout)
    write_json(base / "metrics.json", metrics)
    write_json(base / "comparison-with-hng2-c1.json", comparison)
    write_json(base / "evaluation.json", evaluation)
    manifest = read_json(base / "manifest.json", {}) or {}
    manifest["deterministic_postprocessing_replay"] = True
    write_json(base / "manifest.json", manifest)
    return {"output": str(base), "metrics": metrics, "comparison": comparison, "evaluation": evaluation, "api_calls": 0}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prepare", action="store_true")
    parser.add_argument("--offline-replay", action="store_true")
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--run-id", default=None)
    parser.add_argument("--summarize-run", default=None)
    args = parser.parse_args()
    selection = ensure_selection()
    if args.summarize_run:
        print(json.dumps(summarize_existing_run(args.summarize_run), ensure_ascii=False, indent=2))
        return 0
    if args.prepare or (not args.live and not args.offline_replay):
        print(json.dumps(selection, ensure_ascii=False, indent=2))
        return 0
    run_id = args.run_id or (dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ") if args.live else "deterministic")
    result = run(selection, live=args.live, run_id=run_id)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
