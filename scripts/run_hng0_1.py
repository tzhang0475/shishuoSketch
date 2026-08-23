#!/usr/bin/env python3
"""Run HNG0.1 source-driven one-hop person growth.

The default path is real-model-only.  It performs one minimal authenticated
preflight and then searches registered local source text before each bounded
DeepSeek extraction call.  If the network or credentials are unavailable, it
writes an explicit unavailable status and no model findings; it never falls
back to fixture or HNG0 relation candidates.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Mapping

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from hng0_1_common import (  # noqa: E402
    ALLOWED_RELATION_TYPES,
    ALLOWED_TEMPORAL_TYPES,
    HNG0_CANDIDATE_PATH,
    MODEL,
    OUTPUT_ROOT,
    PROMPT_VERSION,
    PROVIDER,
    REVIEW_STATUSES,
    ROOT,
    SCHEMA_VERSION,
    SELECTION_PATH,
    build_people_catalog,
    build_search_profiles,
    build_source_units,
    find_passages,
    open_passages,
    quote_matches,
    read_json,
    resolve_counterpart,
    route_sources,
    sha256_file,
    source_priority,
    stable_hash,
    temporal_warnings,
    write_json,
)
from smoke_deepseek import call_deepseek  # noqa: E402


RAW_ROOT = OUTPUT_ROOT / "raw-extractions"
PROFILE_PATH = OUTPUT_ROOT / "seed-search-profiles.json"
TRACE_PATH = OUTPUT_ROOT / "retrieval-trace.json"
EVIDENCE_PATH = OUTPUT_ROOT / "source-evidence-registry.json"
RELATION_PATH = OUTPUT_ROOT / "candidate-relations.json"
TEMPORAL_PATH = OUTPUT_ROOT / "candidate-temporal-items.json"
UNRESOLVED_PATH = OUTPUT_ROOT / "unresolved-identities.json"
NEIGHBORHOOD_PATH = OUTPUT_ROOT / "neighborhoods.json"
METRICS_PATH = OUTPUT_ROOT / "metrics.json"
AUDIT_PATH = OUTPUT_ROOT / "audit-sample.json"
MANIFEST_PATH = OUTPUT_ROOT / "manifest.json"
REVIEW_PATH = ROOT / "data/annotation/hng0-1-review.json"
FRONTEND_PATH = ROOT / "site/src/generated/hng0-1-site.json"

SYSTEM_PROMPT = """你是历史资料候选抽取器。只使用下方提供的本地原文，不使用预训练知识补足事实。
只抽取原文明确支持的一跳人物关系或时间事实；同现、同姓、推测、性格判断不能单独形成关系。
不要创建 person_id；对人物只返回原文中的称谓/表面。每条候选必须引用一个给定 evidence_ref 和其中逐字连续的 exact_quote。
关系候选只能使用给定 relation_type；时间候选只能使用给定 temporal_type。证据不足就不输出。
每条候选必须有非空 claim，简洁说明原文支持的事实；不要用 relation_type 或人物并列替代 claim。
严格只返回下列 JSON 结构，不要改字段名，不要输出 Markdown：
{"relation_candidates":[{"seed_person_id":"...","counterpart_surface":"...","relation_type":"...","direction":"seed_to_counterpart|counterpart_to_seed|undirected","claim":"...","evidence_ref":"...","exact_quote":"...","confidence":"high|medium|low","ambiguity":"...","historical_verification_open":true}],"temporal_candidates":[{"seed_person_id":"...","subject_surface":"...","temporal_type":"...","claim":"...","temporal_scope":{},"precision":"exact|circa|before|after|between|reign_period|unknown","evidence_ref":"...","exact_quote":"...","confidence":"high|medium|low","ambiguity":"...","historical_verification_open":true}]}
其中 seed_person_id 必须使用输入的 seed person_id；subject/counterpart 只能使用原文称谓。"""


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true", help="run the real DeepSeek path (default)")
    parser.add_argument("--timeout", type=int, default=180)
    parser.add_argument("--top-k", type=int, default=24)
    parser.add_argument("--open-k", type=int, default=6)
    parser.add_argument("--skip-preflight", action="store_true", help="only for controlled offline debugging")
    return parser.parse_args()


def empty_output(execution_kind: str, reason: str | None = None) -> dict[str, Any]:
    return {
        "schema": SCHEMA_VERSION,
        "stage": "hng0-1",
        "canonical_write_back": False,
        "execution_kind": execution_kind,
        "reason": reason,
        "relations": [],
        "temporal_items": [],
    }


def _content_from_response(response: Mapping[str, Any]) -> str:
    choices = response.get("choices", [])
    if not isinstance(choices, list) or not choices or not isinstance(choices[0], Mapping):
        raise ValueError("DeepSeek response has no choices")
    message = choices[0].get("message", {})
    content = message.get("content") if isinstance(message, Mapping) else None
    if not isinstance(content, str) or not content.strip():
        raise ValueError("DeepSeek response has no JSON content")
    content = content.strip()
    if content.startswith("```"):
        content = re.sub(r"^```(?:json)?\s*|\s*```$", "", content, flags=re.IGNORECASE | re.DOTALL).strip()
    return content


def _usage(response: Mapping[str, Any]) -> dict[str, Any]:
    raw = response.get("usage", {})
    return dict(raw) if isinstance(raw, Mapping) else {}


def _model_packet(profile: Mapping[str, Any], opened: list[Mapping[str, Any]]) -> dict[str, Any]:
    identity = {
        "person_id": profile.get("person_id"),
        "canonical_name": profile.get("canonical_name"),
        "courtesy_name": profile.get("courtesy_name", []),
        "aliases": profile.get("aliases", []),
        "office_titles": profile.get("office_titles", []),
        "clan": profile.get("clan"),
        "native_place": profile.get("native_place"),
    }
    passages = []
    for item in opened:
        passages.append({
            "evidence_ref": item["source_ref"],
            "work": item.get("work"),
            "source_layer": item.get("source_layer"),
            "locator": item.get("locator", {}),
            "text": item.get("snippet", ""),
        })
    return {
        "seed_identity": identity,
        "allowed_relation_types": sorted(ALLOWED_RELATION_TYPES),
        "allowed_temporal_types": sorted(ALLOWED_TEMPORAL_TYPES),
        "passages": passages,
    }


def _valid_claim_ref(row: Mapping[str, Any], opened_by_ref: Mapping[str, Mapping[str, Any]]) -> tuple[bool, str]:
    ref = str(row.get("evidence_ref") or "")
    quote = str(row.get("exact_quote") or "")
    if ref not in opened_by_ref:
        return False, "evidence_ref_not_opened"
    if not quote:
        return False, "empty_exact_quote"
    if not quote_matches(str(opened_by_ref[ref].get("snippet") or ""), quote):
        return False, "exact_quote_not_in_opened_passage"
    if not str(row.get("claim") or "").strip():
        return False, "empty_claim"
    return True, ""


def validate_and_project_response(
    *,
    seed_id: str,
    response_doc: Mapping[str, Any],
    opened: list[Mapping[str, Any]],
    catalog: Mapping[str, Mapping[str, Any]],
    seed_ids: set[str],
    temporal_by_person: Mapping[str, list[Mapping[str, Any]]],
) -> dict[str, Any]:
    """Claim-level fail-closed validation and deterministic identity projection."""

    opened_by_ref = {str(row["source_ref"]): row for row in opened}
    accepted_relations: list[dict[str, Any]] = []
    accepted_times: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    relation_rows = response_doc.get("relation_candidates", [])
    time_rows = response_doc.get("temporal_candidates", [])
    if not isinstance(relation_rows, list):
        relation_rows = []
        rejected.append({"kind": "relation_candidates", "reason": "not_an_array"})
    if not isinstance(time_rows, list):
        time_rows = []
        rejected.append({"kind": "temporal_candidates", "reason": "not_an_array"})

    for index, raw in enumerate(relation_rows):
        if not isinstance(raw, Mapping):
            rejected.append({"kind": "relation", "index": index, "reason": "not_object"})
            continue
        if str(raw.get("seed_person_id") or seed_id) != seed_id:
            rejected.append({"kind": "relation", "index": index, "reason": "seed_identity_mismatch"})
            continue
        kind = str(raw.get("relation_type") or "")
        if kind not in ALLOWED_RELATION_TYPES:
            rejected.append({"kind": "relation", "index": index, "reason": "invalid_relation_type"})
            continue
        ok, reason = _valid_claim_ref(raw, opened_by_ref)
        if not ok:
            rejected.append({"kind": "relation", "index": index, "reason": reason, "evidence_ref": raw.get("evidence_ref")})
            continue
        if raw.get("cooccurrence_only") is True or str(raw.get("basis") or "").lower() in {"cooccurrence", "co-occurrence"}:
            rejected.append({"kind": "relation", "index": index, "reason": "cooccurrence_only"})
            continue
        surface = str(raw.get("counterpart_surface") or "").strip()
        if not surface:
            rejected.append({"kind": "relation", "index": index, "reason": "empty_counterpart_surface"})
            continue
        resolution = resolve_counterpart(surface, catalog)
        if resolution["resolution_status"] == "resolved_existing_person" and resolution.get("person_id") in seed_ids:
            rejected.append({"kind": "relation", "index": index, "reason": "counterpart_is_existing_seed", "counterpart_surface": surface})
            continue
        counterpart_id = resolution.get("person_id")
        provisional = None if counterpart_id else f"hng01-unresolved-{stable_hash({'surface': surface})[:16]}"
        person_a, person_b = seed_id, counterpart_id
        direction_raw = str(raw.get("direction") or "undirected")
        if direction_raw not in {"seed_to_counterpart", "counterpart_to_seed", "undirected"}:
            direction_raw = "undirected"
        if direction_raw == "counterpart_to_seed" and counterpart_id:
            person_a, person_b = counterpart_id, seed_id
        if person_b and person_a > person_b and direction_raw == "undirected":
            person_a, person_b = person_b, person_a
        evidence_ref = str(raw["evidence_ref"])
        row = {
            "relation_id": None,
            "person_a": person_a,
            "person_b": person_b,
            "person_a_name": catalog.get(person_a, {}).get("canonical_name") if person_a else None,
            "person_b_name": catalog.get(person_b, {}).get("canonical_name") if person_b else None,
            "counterpart_surface": surface,
            "provisional_neighbor_id": provisional,
            "resolution_status": resolution["resolution_status"],
            "resolution_matches": resolution.get("matches", []),
            "relation_type": kind,
            "direction": {"kind": direction_raw, "from": person_a, "to": person_b},
            "temporal_scope": dict(raw.get("temporal_scope") or {}) if isinstance(raw.get("temporal_scope"), Mapping) else {},
            "certainty": str(raw.get("confidence") or "low"),
            "ambiguity": str(raw.get("ambiguity") or ""),
            "historical_verification_open": bool(raw.get("historical_verification_open", True)),
            "claim": str(raw.get("claim")),
            "evidence_refs": [evidence_ref],
            "evidence_quotes": [{"ref": evidence_ref, "quote": str(raw.get("exact_quote"))}],
            "source_works": [opened_by_ref[evidence_ref].get("work")],
            "extraction_method": "llm_source_extraction",
            "review_status": "candidate",
            "source_review_status": "candidate_model_output",
            "origin": "newly_extracted",
            "one_hop_only": True,
            "cooccurrence_only": False,
            "temporal_warnings": [],
        }
        row["temporal_warnings"] = temporal_warnings({"person_id": seed_id, "temporal_scope": row["temporal_scope"]}, temporal_by_person)
        accepted_relations.append(row)

    for index, raw in enumerate(time_rows):
        if not isinstance(raw, Mapping):
            rejected.append({"kind": "temporal", "index": index, "reason": "not_object"})
            continue
        if str(raw.get("seed_person_id") or seed_id) != seed_id:
            rejected.append({"kind": "temporal", "index": index, "reason": "seed_identity_mismatch"})
            continue
        kind = str(raw.get("temporal_type") or "")
        if kind not in ALLOWED_TEMPORAL_TYPES:
            rejected.append({"kind": "temporal", "index": index, "reason": "invalid_temporal_type"})
            continue
        ok, reason = _valid_claim_ref(raw, opened_by_ref)
        if not ok:
            rejected.append({"kind": "temporal", "index": index, "reason": reason, "evidence_ref": raw.get("evidence_ref")})
            continue
        subject_surface = str(raw.get("subject_surface") or "").strip()
        subject = resolve_counterpart(subject_surface, catalog) if subject_surface else {"resolution_status": "resolved_existing_person", "person_id": seed_id, "canonical_name": catalog.get(seed_id, {}).get("canonical_name"), "matches": [seed_id]}
        subject_id = subject.get("person_id")
        if subject_id and subject_id in seed_ids and subject_id != seed_id:
            rejected.append({"kind": "temporal", "index": index, "reason": "temporal_subject_outside_seed_or_neighbor", "subject_surface": subject_surface})
            continue
        scope = dict(raw.get("temporal_scope") or {}) if isinstance(raw.get("temporal_scope"), Mapping) else {}
        evidence_ref = str(raw["evidence_ref"])
        accepted_times.append({
            "temporal_id": None,
            "person_id": subject_id or seed_id,
            "subject_surface": subject_surface or catalog.get(seed_id, {}).get("canonical_name"),
            "subject_resolution_status": subject.get("resolution_status"),
            "subject_matches": subject.get("matches", []),
            "temporal_type": kind,
            "claim": str(raw.get("claim")),
            "temporal_scope": scope,
            "precision": str(raw.get("precision") or scope.get("precision") or "unknown"),
            "certainty": str(raw.get("confidence") or "low"),
            "ambiguity": str(raw.get("ambiguity") or ""),
            "historical_verification_open": bool(raw.get("historical_verification_open", True)),
            "evidence_refs": [evidence_ref],
            "evidence_quotes": [{"ref": evidence_ref, "quote": str(raw.get("exact_quote"))}],
            "source_works": [opened_by_ref[evidence_ref].get("work")],
            "extraction_method": "llm_source_extraction",
            "review_status": "candidate",
            "source_review_status": "candidate_model_output",
            "origin": "newly_extracted",
            "temporal_warnings": temporal_warnings({"person_id": subject_id or seed_id, "temporal_scope": scope}, temporal_by_person),
        })
    return {"relations": accepted_relations, "temporal_items": accepted_times, "rejected": rejected}


def merge_relations(rows: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    merged: dict[tuple[Any, ...], dict[str, Any]] = {}
    for raw in rows:
        row = dict(raw)
        a, b = row.get("person_a"), row.get("person_b") or row.get("provisional_neighbor_id")
        direction = row.get("direction", {}).get("kind") if isinstance(row.get("direction"), Mapping) else "undirected"
        key = (a or "", b or "", row.get("relation_type"), direction)
        if key not in merged:
            row["relation_id"] = f"hng01-relation-{stable_hash(key)[:20]}"
            merged[key] = row
            continue
        target = merged[key]
        target["evidence_refs"] = sorted(set(target.get("evidence_refs", [])) | set(row.get("evidence_refs", [])))
        quotes = {(str(item.get("ref")), str(item.get("quote"))) for item in target.get("evidence_quotes", [])}
        quotes.update((str(item.get("ref")), str(item.get("quote"))) for item in row.get("evidence_quotes", []))
        target["evidence_quotes"] = [{"ref": ref, "quote": quote} for ref, quote in sorted(quotes)]
        target["source_works"] = sorted(set(target.get("source_works", [])) | set(row.get("source_works", [])))
        target["temporal_warnings"] = sorted(set(target.get("temporal_warnings", [])) | set(row.get("temporal_warnings", [])))
        if row.get("claim") and row.get("claim") != target.get("claim"):
            variants = target.setdefault("claim_variants", [target.get("claim")])
            if row["claim"] not in variants:
                variants.append(row["claim"])
            target.setdefault("conflicts", []).append({"claim": row["claim"], "evidence_refs": row.get("evidence_refs", [])})
    return sorted(merged.values(), key=lambda row: row["relation_id"])


def merge_temporal(rows: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    merged: dict[tuple[Any, ...], dict[str, Any]] = {}
    for raw in rows:
        row = dict(raw)
        key = (row.get("person_id"), row.get("temporal_type"), row.get("claim"), stable_hash(row.get("temporal_scope", {}))[:10])
        if key not in merged:
            row["temporal_id"] = f"hng01-time-{stable_hash(key)[:20]}"
            merged[key] = row
            continue
        target = merged[key]
        target["evidence_refs"] = sorted(set(target.get("evidence_refs", [])) | set(row.get("evidence_refs", [])))
        target["evidence_quotes"] = sorted({(str(item.get("ref")), str(item.get("quote"))) for item in target.get("evidence_quotes", []) + row.get("evidence_quotes", [])})
        target["evidence_quotes"] = [{"ref": ref, "quote": quote} for ref, quote in target["evidence_quotes"]]
        target["source_works"] = sorted(set(target.get("source_works", [])) | set(row.get("source_works", [])))
    return sorted(merged.values(), key=lambda row: row["temporal_id"])


def default_review(relations: Iterable[Mapping[str, Any]], times: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    return {
        "schema": 1,
        "stage": "hng0-1-review-overlay",
        "canonical_write_back": False,
        "relation_decisions": {row["relation_id"]: {"review_status": "candidate", "reviewer_note": ""} for row in relations},
        "temporal_decisions": {row["temporal_id"]: {"review_status": "candidate", "reviewer_note": ""} for row in times},
    }


def _write_json_if_absent(path: Path, value: Any) -> None:
    """Raw attempts are append-only; never overwrite a previous response."""

    if path.exists():
        return
    write_json(path, value)


def _attempt_path(seed_id: str) -> Path:
    RAW_ROOT.mkdir(parents=True, exist_ok=True)
    existing = sorted(RAW_ROOT.glob(f"{seed_id}-attempt-*.json"))
    return RAW_ROOT / f"{seed_id}-attempt-{len(existing) + 1:02d}.json"


def _preflight(timeout: int) -> dict[str, Any]:
    started = utc_now()
    monotonic_start = time.monotonic()
    try:
        result = call_deepseek(
            [{"role": "user", "content": "Reply only with OK"}],
            model=MODEL,
            temperature=0,
            timeout=min(timeout, 60),
        )
        return {"status": "reachable", "started_at": started, "ended_at": utc_now(), "elapsed_seconds": round(time.monotonic() - monotonic_start, 4), "model": result.get("model"), "usage": _usage(result)}
    except Exception as exc:  # transport/auth errors are kept out of model findings
        return {"status": "unavailable", "started_at": started, "ended_at": utc_now(), "elapsed_seconds": round(time.monotonic() - monotonic_start, 4), "exception_class": type(exc).__name__, "exception_message": str(exc)}


def _route_trace(find_result: Mapping[str, Any], opened: list[Mapping[str, Any]], used: list[str], rejected: list[Mapping[str, Any]]) -> dict[str, Any]:
    return {
        "routes": find_result.get("routes", []),
        "searched": [
            {"work": item.get("work"), "reason": item.get("reason"), "query_terms": find_result.get("query_terms", [])}
            for item in find_result.get("routes", [])
        ],
        "retrieved": [
            {"source_ref": item.get("source_ref"), "work": item.get("work"), "source_layer": item.get("source_layer"), "score": item.get("score"), "matched_terms": item.get("matched_terms", [])}
            for item in find_result.get("hits", [])
        ],
        "opened": [
            {"source_ref": item.get("source_ref"), "work": item.get("work"), "source_layer": item.get("source_layer"), "locator": item.get("locator", {}), "window_start": item.get("window_start"), "window_end": item.get("window_end")}
            for item in opened
        ],
        "used": sorted(set(used)),
        "rejected_evidence": list(rejected),
    }


def _model_error_record(
    seed_id: str,
    packet: Mapping[str, Any],
    error: Exception,
    *,
    request_started_at: str | None = None,
    request_ended_at: str | None = None,
    elapsed_seconds: float | None = None,
) -> dict[str, Any]:
    return {
        "schema": 1,
        "artifact_kind": "hng0-1-raw-extraction-attempt",
        "canonical_write_back": False,
        "execution_kind": "real_model",
        "seed_person_id": seed_id,
        "prompt_version": PROMPT_VERSION,
        "model": MODEL,
        "provider": PROVIDER,
        "model_input": packet,
        "response_status": "transport_or_provider_error",
        "exception_class": type(error).__name__,
        "exception_message": str(error),
        "attempt": 1,
        "request_started_at": request_started_at,
        "request_ended_at": request_ended_at,
        "elapsed_seconds": elapsed_seconds,
        "usage": {},
    }


def _build_neighborhoods(
    profiles: Mapping[str, Mapping[str, Any]],
    hng_candidates: Mapping[str, Any],
    relations: list[Mapping[str, Any]],
    times: list[Mapping[str, Any]],
) -> dict[str, Any]:
    old_people = hng_candidates.get("people", {}) if isinstance(hng_candidates.get("people"), Mapping) else {}
    by_person: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    by_time: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for row in relations:
        if row.get("person_a"):
            by_person[str(row["person_a"])].append(row)
        if row.get("person_b"):
            by_person[str(row["person_b"])].append(row)
    for row in times:
        if row.get("person_id"):
            by_time[str(row["person_id"])].append(row)
    people: dict[str, Any] = {}
    for pid in sorted(profiles):
        old = old_people.get(pid, {}) if isinstance(old_people, Mapping) else {}
        old_person = old.get("person", {}) if isinstance(old, Mapping) else {}
        old_stories = old.get("stories", []) if isinstance(old, Mapping) else []
        old_times = old.get("temporal_spine", []) if isinstance(old, Mapping) else []
        new_relations = sorted(by_person.get(pid, []), key=lambda row: row.get("relation_id", ""))
        new_times = sorted(by_time.get(pid, []), key=lambda row: row.get("temporal_id", ""))
        nearby = sorted({
            str(row.get("person_b")) if row.get("person_a") == pid and row.get("person_b") else str(row.get("person_a"))
            for row in new_relations
            if (row.get("person_a") == pid and row.get("person_b")) or (row.get("person_b") == pid and row.get("person_a"))
        })
        people[pid] = {
            "person_id": pid,
            "person": old_person,
            "identity_profile": profiles[pid],
            "stories": old_stories,
            "existing_hng_temporal_spine": old_times,
            "newly_extracted_relations": new_relations,
            "newly_extracted_temporal_items": new_times,
            "new_neighbor_ids": nearby,
            "approximate_temporal_window": old.get("approximate_temporal_window", {}) if isinstance(old, Mapping) else {},
        }
    return {"schema": 1, "stage": "hng0-1-neighborhoods", "canonical_write_back": False, "one_hop_only": True, "people": people}


def _build_audit_sample(
    relations: list[Mapping[str, Any]],
    times: list[Mapping[str, Any]],
    unresolved: list[Mapping[str, Any]],
    evidence: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    selected: list[dict[str, Any]] = []
    for kind, rows in (("relation", relations[:10]), ("temporal", times[:5])):
        for row in rows:
            refs = row.get("evidence_refs", [])
            selected.append({
                "kind": kind,
                "candidate": row,
                "source_passages": [dict(evidence[ref]) for ref in refs if ref in evidence],
                "final_candidate_state": row.get("review_status", "candidate"),
            })
    for item in unresolved:
        candidate = item.get("candidate", {})
        if candidate.get("resolution_status") == "ambiguous_identity" or candidate.get("subject_resolution_status") == "ambiguous_identity":
            refs = candidate.get("evidence_refs", [])
            selected.append({"kind": item.get("kind", "identity"), "audit_reason": "ambiguous_identity", "candidate": candidate, "source_passages": [dict(evidence[ref]) for ref in refs if ref in evidence], "final_candidate_state": candidate.get("review_status", "candidate")})
    for row in relations + times:
        if row.get("temporal_warnings"):
            refs = row.get("evidence_refs", [])
            selected.append({"kind": "temporal_conflict", "audit_reason": "temporal_warning", "candidate": row, "source_passages": [dict(evidence[ref]) for ref in refs if ref in evidence], "final_candidate_state": row.get("review_status", "candidate")})
    # Keep deterministic order and avoid repeating the same candidate in the
    # ambiguity/conflict supplement.
    seen: set[str] = set()
    output: list[dict[str, Any]] = []
    for item in selected:
        key = stable_hash({"kind": item.get("kind"), "candidate": item.get("candidate", {})})
        if key in seen:
            continue
        seen.add(key)
        output.append(item)
    return {"schema": 1, "stage": "hng0-1-manual-audit-sample", "canonical_write_back": False, "policy": "deterministic first 10 relations, first 5 temporal items, all ambiguous identities and temporal conflicts", "items": output}


def main() -> int:
    args = parse_args()
    if args.top_k < 1 or args.open_k < 1 or args.open_k > 8:
        raise SystemExit("--top-k must be positive and --open-k must be between 1 and 8")

    profiles = build_search_profiles(ROOT)
    catalog = build_people_catalog(ROOT)
    source_units = build_source_units(ROOT)
    units_by_ref = {str(row["source_ref"]): row for row in source_units}
    selection = read_json(SELECTION_PATH)
    hng_candidates = read_json(HNG0_CANDIDATE_PATH)
    seed_ids = {str(row["person_id"]) for row in selection.get("people", []) if row.get("person_id")}
    if len(seed_ids) != 24:
        raise SystemExit(f"HNG0.1 requires the frozen 24 HNG0 seeds; found {len(seed_ids)}")

    temporal_by_person: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for pid, person in (hng_candidates.get("people", {}) or {}).items():
        for row in person.get("temporal_spine", []) if isinstance(person, Mapping) else []:
            if isinstance(row, Mapping):
                temporal_by_person[str(pid)].append(row)

    selection_hash = sha256_file(SELECTION_PATH)
    input_hash = stable_hash({"selection": selection_hash, "profiles": profiles, "source_ref_count": len(source_units), "prompt_version": PROMPT_VERSION})
    run_id = f"hng01-{input_hash[:20]}"
    preflight = {"status": "skipped"} if args.skip_preflight else _preflight(args.timeout)
    preflight_path = Path("/tmp/hng0-1-preflight.json")
    write_json(preflight_path, {"stage": "hng0-1-preflight", "run_id": run_id, **preflight})
    network_available = preflight.get("status") in {"reachable", "skipped"}
    unavailable_reason = None if network_available else str(preflight.get("exception_message") or "DeepSeek preflight unavailable")

    write_json(PROFILE_PATH, {
        "schema": SCHEMA_VERSION,
        "stage": "hng0-1-search-profiles",
        "canonical_write_back": False,
        "seed_person_ids": sorted(seed_ids),
        "one_hop_only": True,
        "profiles": {pid: profiles[pid] for pid in sorted(profiles)},
    })

    all_relations: list[dict[str, Any]] = []
    all_times: list[dict[str, Any]] = []
    all_evidence: dict[str, dict[str, Any]] = {}
    trace_people: dict[str, Any] = {}
    unresolved: list[dict[str, Any]] = []
    model_failures: list[dict[str, Any]] = []
    usage_rows: list[dict[str, Any]] = []

    for pid in sorted(seed_ids):
        profile = profiles[pid]
        find_result = find_passages(profile, source_units, top_k=args.top_k)
        opened = open_passages(find_result, units_by_ref, max_passages=args.open_k)
        for item in opened:
            all_evidence[str(item["source_ref"])] = {
                "evidence_ref": item["source_ref"],
                "source_work": item.get("work"),
                "source_layer": item.get("source_layer"),
                # Keep the exact registered unit locally.  The model still
                # receives only `snippet`; the full source here prevents a
                # reused ref opened at a different window from losing a
                # quote selected from an earlier window.
                "original_text": item.get("original_text") or item.get("snippet"),
                "model_snippet": item.get("snippet"),
                "normalized_search_text": item.get("snippet", ""),
                "locator": item.get("locator", {}),
                "source_path": item.get("source_path"),
                "source_sha256": item.get("source_sha256"),
                "window_start": item.get("window_start"),
                "window_end": item.get("window_end"),
                "parent_source_ref": item.get("source_ref"),
                "source_provenance": "registered_local_processed_source",
            }
        used: list[str] = []
        rejected: list[dict[str, Any]] = []
        response_status = "not_called"
        usage: dict[str, Any] = {}
        request_started_at: str | None = None
        request_ended_at: str | None = None
        elapsed_seconds: float | None = None
        packet = _model_packet(profile, opened)
        if not network_available:
            response_status = "live_network_unavailable"
        elif not opened:
            response_status = "no_local_passage_opened"
        else:
            messages = [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": json.dumps(packet, ensure_ascii=False, separators=(",", ":"))},
            ]
            request_started_at = utc_now()
            monotonic_start = time.monotonic()
            try:
                response = call_deepseek(messages, model=MODEL, temperature=0, response_format={"type": "json_object"}, timeout=args.timeout)
                elapsed_seconds = round(time.monotonic() - monotonic_start, 4)
                request_ended_at = utc_now()
                usage = _usage(response)
                usage_rows.append({"seed_person_id": pid, "request_started_at": request_started_at, "request_ended_at": request_ended_at, "elapsed_seconds": elapsed_seconds, **usage})
                content = _content_from_response(response)
                parsed = json.loads(content)
                projection = validate_and_project_response(seed_id=pid, response_doc=parsed, opened=opened, catalog=catalog, seed_ids=seed_ids, temporal_by_person=temporal_by_person)
                used = sorted({ref for row in projection["relations"] + projection["temporal_items"] for ref in row.get("evidence_refs", [])})
                rejected = projection["rejected"]
                all_relations.extend(projection["relations"])
                all_times.extend(projection["temporal_items"])
                for row in projection["relations"]:
                    if row.get("resolution_status") != "resolved_existing_person":
                        unresolved.append({"seed_person_id": pid, "kind": "relation", "candidate": row})
                for row in projection["temporal_items"]:
                    if row.get("subject_resolution_status") in {"unresolved_identity", "ambiguous_identity"}:
                        unresolved.append({"seed_person_id": pid, "kind": "temporal", "candidate": row})
                response_status = "model_output_validated"
                raw_record = {
                    "schema": 1,
                    "artifact_kind": "hng0-1-raw-extraction-attempt",
                    "canonical_write_back": False,
                    "execution_kind": "real_model",
                    "seed_person_id": pid,
                    "prompt_version": PROMPT_VERSION,
                    "model": MODEL,
                    "provider": PROVIDER,
                    "model_input": packet,
                    "raw_response": response,
                    "raw_content": content,
                    "normalized_output": parsed,
                    "validated_projection": projection,
                    "response_status": "model_output_validated",
                    "attempt": 1,
                    "request_started_at": request_started_at,
                    "request_ended_at": request_ended_at,
                    "elapsed_seconds": elapsed_seconds,
                    "usage": usage,
                }
                _write_json_if_absent(_attempt_path(pid), raw_record)
            except Exception as exc:
                elapsed_seconds = round(time.monotonic() - monotonic_start, 4)
                request_ended_at = utc_now()
                response_status = "model_or_protocol_failure"
                model_failures.append({"seed_person_id": pid, "exception_class": type(exc).__name__, "exception_message": str(exc)})
                _write_json_if_absent(
                    _attempt_path(pid),
                    _model_error_record(
                        pid,
                        packet,
                        exc,
                        request_started_at=request_started_at,
                        request_ended_at=request_ended_at,
                        elapsed_seconds=elapsed_seconds,
                    ),
                )
        trace_people[pid] = {
            "seed_person_id": pid,
            "route": route_sources(profile, source_units),
            "find": find_result,
            "open": [{"source_ref": item["source_ref"], "window_start": item["window_start"], "window_end": item["window_end"]} for item in opened],
            "searched": [{"work": route["work"], "reason": route["reason"], "query_terms": find_result.get("query_terms", [])} for route in find_result.get("routes", [])],
            "retrieved": [item["source_ref"] for item in find_result.get("hits", [])],
            "opened": [item["source_ref"] for item in opened],
            "used": used,
            "rejected": rejected,
            "response_status": response_status,
            "request_started_at": request_started_at,
            "request_ended_at": request_ended_at,
            "elapsed_seconds": elapsed_seconds,
            "usage": usage,
        }

    relations = merge_relations(all_relations)
    times = merge_temporal(all_times)
    for row in relations:
        row["person_a_name"] = row.get("person_a_name") or catalog.get(str(row.get("person_a")), {}).get("canonical_name")
        row["person_b_name"] = row.get("person_b_name") or catalog.get(str(row.get("person_b")), {}).get("canonical_name")
    unresolved = sorted(unresolved, key=lambda row: (row.get("seed_person_id", ""), row.get("kind", ""), stable_hash(row.get("candidate", {}))))
    trace = {
        "schema": SCHEMA_VERSION,
        "stage": "hng0-1-retrieval-trace",
        "canonical_write_back": False,
        "execution_kind": "real_model" if network_available else "live_model_unavailable",
        "run_id": run_id,
        "source_inventory_count": len(source_units),
        "people": trace_people,
    }
    evidence_doc = {
        "schema": SCHEMA_VERSION,
        "stage": "hng0-1-opened-source-evidence",
        "canonical_write_back": False,
        "source_policy": "only opened refs from registered local processed corpora; generated/model paths excluded",
        "evidence": {key: all_evidence[key] for key in sorted(all_evidence)},
    }
    relation_doc = {"schema": SCHEMA_VERSION, "stage": "hng0-1-candidate-relations", "canonical_write_back": False, "execution_kind": trace["execution_kind"], "one_hop_only": True, "relations": relations, "evidence": evidence_doc["evidence"]}
    temporal_doc = {"schema": SCHEMA_VERSION, "stage": "hng0-1-candidate-temporal-items", "canonical_write_back": False, "execution_kind": trace["execution_kind"], "one_hop_only": True, "temporal_items": times, "evidence": evidence_doc["evidence"]}
    review = read_json(REVIEW_PATH) if REVIEW_PATH.is_file() else default_review(relations, times)
    review.setdefault("relation_decisions", {})
    review.setdefault("temporal_decisions", {})
    for row in relations:
        review["relation_decisions"].setdefault(row["relation_id"], {"review_status": "candidate", "reviewer_note": ""})
    for row in times:
        review["temporal_decisions"].setdefault(row["temporal_id"], {"review_status": "candidate", "reviewer_note": ""})
    review.update({"schema": 1, "stage": "hng0-1-review-overlay", "canonical_write_back": False})
    source_work_counts = Counter()
    for ref in all_evidence.values():
        source_work_counts[str(ref.get("source_work"))] += 1
    used_source_work_counts = Counter()
    for trace in trace_people.values():
        for ref in trace.get("used", []):
            if ref in all_evidence:
                used_source_work_counts[str(all_evidence[ref].get("source_work"))] += 1
    retrieved_count = sum(len(row.get("retrieved", [])) for row in trace_people.values())
    opened_count = sum(len(row.get("opened", [])) for row in trace_people.values())
    used_count = sum(len(row.get("used", [])) for row in trace_people.values())
    retrieved_seed_count = sum(bool(row.get("retrieved")) for row in trace_people.values())
    response_latencies = sorted(
        row["elapsed_seconds"]
        for row in usage_rows
        if isinstance(row.get("elapsed_seconds"), (int, float))
    )
    median_latency = (
        response_latencies[len(response_latencies) // 2]
        if len(response_latencies) % 2 == 1
        else (response_latencies[len(response_latencies) // 2 - 1] + response_latencies[len(response_latencies) // 2]) / 2
        if response_latencies
        else None
    )
    metrics = {
        "schema": SCHEMA_VERSION,
        "stage": "hng0-1-metrics",
        "canonical_write_back": False,
        "execution_kind": trace["execution_kind"],
        "run_id": run_id,
        "searched_seed_count": len(seed_ids),
        "seeds_with_biography_hit": sum(1 for row in trace_people.values() if any(item.get("work") == "晉書" and (item.get("unit_kind") == "biography" or item.get("category") == "liezhuan") for item in row.get("find", {}).get("hits", []))),
        "retrieved_passages": retrieved_count,
        "opened_passages": opened_count,
        "used_passages": used_count,
        "new_relation_candidates": len(relations),
        "new_neighbor_count": len({row.get("person_b") for row in relations if row.get("person_b")}),
        "new_temporal_candidates": len(times),
        "relations_by_type": dict(sorted(Counter(row.get("relation_type") for row in relations).items())),
        "source_contribution": dict(sorted(source_work_counts.items())),
        "used_source_contribution": dict(sorted(used_source_work_counts.items())),
        "unresolved_identity_count": sum(1 for row in unresolved if row.get("candidate", {}).get("resolution_status") == "unresolved_identity" or row.get("candidate", {}).get("subject_resolution_status") == "unresolved_identity"),
        "ambiguous_identity_count": sum(1 for row in unresolved if row.get("candidate", {}).get("resolution_status") == "ambiguous_identity" or row.get("candidate", {}).get("subject_resolution_status") == "ambiguous_identity"),
        "evidence_validation_failures": sum(len(row.get("rejected", [])) for row in trace_people.values()),
        "temporal_conflict_count": sum(bool(row.get("temporal_warnings")) for row in times + relations),
        "retrieval_hit_seed_count": retrieved_seed_count,
        "retrieval_hit_rate": round(retrieved_seed_count / max(1, len(seed_ids)), 4),
        "retrieved_passages_per_seed": round(retrieved_count / max(1, len(seed_ids)), 4),
        "opening_precision": round(used_count / max(1, opened_count), 4),
        "evidence_use_rate": round(used_count / max(1, retrieved_count), 4),
        "new_relation_yield_per_seed": round(len(relations) / max(1, len(seed_ids)), 4),
        "new_neighbor_yield_per_seed": round(len({row.get("person_b") for row in relations if row.get("person_b")}) / max(1, len(seed_ids)), 4),
        "model_failures": model_failures,
        "api_usage": usage_rows,
        "api_response_request_count": len(response_latencies),
        "median_api_response_latency_seconds": median_latency,
        "max_api_response_latency_seconds": max(response_latencies) if response_latencies else None,
    }
    write_json(TRACE_PATH, trace)
    write_json(EVIDENCE_PATH, evidence_doc)
    write_json(RELATION_PATH, relation_doc)
    write_json(TEMPORAL_PATH, temporal_doc)
    write_json(UNRESOLVED_PATH, {"schema": SCHEMA_VERSION, "stage": "hng0-1-unresolved-identities", "canonical_write_back": False, "items": unresolved})
    write_json(NEIGHBORHOOD_PATH, _build_neighborhoods(profiles, hng_candidates, relations, times))
    write_json(AUDIT_PATH, _build_audit_sample(relations, times, unresolved, all_evidence))
    write_json(METRICS_PATH, metrics)
    write_json(REVIEW_PATH, review)
    manifest = {
        "schema": SCHEMA_VERSION,
        "stage": "hng0-1-manifest",
        "canonical_write_back": False,
        "execution_kind": trace["execution_kind"],
        "run_id": run_id,
        "provider": PROVIDER,
        "model": MODEL,
        "prompt_version": PROMPT_VERSION,
        "parameters": {"temperature": 0, "timeout": args.timeout, "find_top_k": args.top_k, "open_max": args.open_k},
        "preflight": {key: value for key, value in preflight.items() if key not in {"exception_message"} or value is None},
        "preflight_failure": unavailable_reason,
        "seed_person_ids": sorted(seed_ids),
        "one_hop_only": True,
        "source_inventory_count": len(source_units),
        "input_hash": input_hash,
        "protected_hng0_hash": sha256_file(HNG0_CANDIDATE_PATH),
        "outputs": [path.name for path in (PROFILE_PATH, TRACE_PATH, EVIDENCE_PATH, RELATION_PATH, TEMPORAL_PATH, UNRESOLVED_PATH, NEIGHBORHOOD_PATH, AUDIT_PATH, METRICS_PATH)],
        "review_overlay": str(REVIEW_PATH.relative_to(ROOT)),
        "raw_extraction_policy": "append-only attempt files; model output is candidate-only",
    }
    write_json(MANIFEST_PATH, manifest)
    print(json.dumps({"status": "pass" if network_available else "live_model_unavailable", "execution_kind": trace["execution_kind"], "seed_person_count": len(seed_ids), "relations": len(relations), "temporal_items": len(times), "retrieved": retrieved_count, "opened": opened_count, "used": used_count, "preflight": preflight.get("status"), "preflight_path": str(preflight_path)}, ensure_ascii=False, indent=2))
    return 0 if network_available else 2


if __name__ == "__main__":
    raise SystemExit(main())
