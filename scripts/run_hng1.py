#!/usr/bin/env python3
"""Run the frozen HNG1 fresh-person generalization evaluation.

Preparation is deterministic and offline.  Live mode performs one approved
network preflight, then one bounded source-extraction call per fresh seed.  A
transport/environment failure never becomes a fabricated historical finding.
"""

from __future__ import annotations

import argparse
import collections
import datetime as dt
import hashlib
import json
import re
import statistics
import sys
import time
from pathlib import Path
from typing import Any, Mapping, Sequence

SCRIPT_DIR = Path(__file__).resolve().parent
ROOT = SCRIPT_DIR.parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import build_hng0_2 as hng02  # noqa: E402
from hng0_1_common import (  # noqa: E402
    ALLOWED_RELATION_TYPES,
    ALLOWED_TEMPORAL_TYPES,
    build_people_catalog,
    quote_matches,
    sha256_file,
    stable_hash,
    write_json,
)
from hng1_common import (  # noqa: E402
    build_fresh_profiles,
    build_hng1_selection,
    find_punctuated_first,
    load_retrieval_sources,
    open_short_hits,
)
from srm0_4c_transport import DeepSeekTransport, classify_transport_error  # noqa: E402
from smoke_deepseek import call_deepseek  # noqa: E402


OUTPUT_ROOT = ROOT / "data/generated/hng1"
SELECTION_PATH = OUTPUT_ROOT / "hng1-selection.json"
PROFILE_PATH = OUTPUT_ROOT / "search-profiles.json"
TRACE_PATH = OUTPUT_ROOT / "retrieval-trace.json"
EVIDENCE_PATH = OUTPUT_ROOT / "source-evidence-registry.json"
RAW_ROOT = OUTPUT_ROOT / "raw-extractions"
IDENTITY_PATH = OUTPUT_ROOT / "identity-resolution.json"
RELATION_PATH = OUTPUT_ROOT / "relations.json"
TEMPORAL_PATH = OUTPUT_ROOT / "temporal-items.json"
NEIGHBOR_PATH = OUTPUT_ROOT / "neighborhoods.json"
UNRESOLVED_PATH = OUTPUT_ROOT / "unresolved-identities.json"
AUDIT_PATH = OUTPUT_ROOT / "audit-sample.json"
METRICS_PATH = OUTPUT_ROOT / "metrics.json"
MANIFEST_PATH = OUTPUT_ROOT / "manifest.json"
REVIEW_PATH = ROOT / "data/annotation/hng1-review.json"

MODEL = "deepseek-v4-flash"
PROVIDER = "deepseek"
PROMPT_VERSION = "hng1-frozen-hng02r-source-extraction-v1"
RUN_SCHEMA = 1

# The extraction vocabulary is deliberately compatible with HNG0.2's
# normalizer, while exposing the repaired grandparent class to the model.
EXTRACTION_RELATION_TYPES = set(ALLOWED_RELATION_TYPES) | hng02.HARD_RELATIONS | hng02.DOCUMENTED_INTERACTIONS | hng02.INTERPRETED_RELATIONS
EXTRACTION_TEMPORAL_TYPES = set(ALLOWED_TEMPORAL_TYPES)

SYSTEM_PROMPT = """你是历史资料候选抽取器。只使用提供的本地原文，不使用预训练知识补足事实。
只抽取原文明确支持的一跳人物关系或时间事实；同现、同姓、推测、性格判断不能单独形成关系。
不要给对方人物分配 person_id，只返回原文中的称谓或表面。每条候选必须引用一个给定 evidence_ref 和其中逐字连续的 exact_quote。
关系须属于给定 relation_type；时间须属于给定 temporal_type；证据不足就不输出。不要把一次共同出现写成稳定关系。
严格只返回 JSON，不要 Markdown：
{"relation_candidates":[{"seed_person_id":"...","counterpart_surface":"...","relation_type":"...","direction":"seed_to_counterpart|counterpart_to_seed|undirected","claim":"...","evidence_ref":"...","exact_quote":"...","confidence":"high|medium|low","ambiguity":"...","historical_verification_open":true}],"temporal_candidates":[{"seed_person_id":"...","subject_surface":"...","temporal_type":"...","claim":"...","temporal_scope":{},"precision":"exact|circa|before|after|between|reign_period|unknown","evidence_ref":"...","exact_quote":"...","confidence":"high|medium|low","ambiguity":"...","historical_verification_open":true}]}
"""


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def read_json(path: Path, default: Any = None) -> Any:
    if not path.is_file():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def json_hash(value: Any) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def write_if_absent(path: Path, value: Any) -> None:
    if not path.exists():
        write_json(path, value)


def selection_and_profiles(count_per_stratum: int = 12) -> tuple[dict[str, Any], dict[str, dict[str, Any]]]:
    generated = build_hng1_selection(count_per_stratum=count_per_stratum)
    if SELECTION_PATH.is_file():
        existing = read_json(SELECTION_PATH)
        if existing != generated:
            raise RuntimeError("existing HNG1 selection differs from deterministic frozen selection")
        selection = existing
    else:
        selection = generated
        write_json(SELECTION_PATH, selection)
    profiles = build_fresh_profiles(selection)
    if PROFILE_PATH.is_file():
        existing_profiles = read_json(PROFILE_PATH)
        if existing_profiles.get("profiles") != profiles:
            raise RuntimeError("existing HNG1 profiles differ from frozen selection")
    else:
        write_json(PROFILE_PATH, {
            "schema": 1,
            "stage": "hng1-search-profiles",
            "canonical_write_back": False,
            "selection_hash": json_hash(selection),
            "one_hop_only": True,
            "profiles": profiles,
        })
    return selection, profiles


def model_packet(profile: Mapping[str, Any], opened: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    return {
        "seed_identity": {
            "person_id": profile.get("person_id"),
            "canonical_name": profile.get("canonical_name"),
            "courtesy_name": profile.get("courtesy_name", []),
            "aliases": profile.get("aliases", []),
            "office_titles": profile.get("office_titles", []),
            "clan": profile.get("clan"),
            "native_place": profile.get("native_place"),
        },
        "allowed_relation_types": sorted(EXTRACTION_RELATION_TYPES),
        "allowed_temporal_types": sorted(EXTRACTION_TEMPORAL_TYPES),
        "passages": [
            {
                "evidence_ref": item.get("source_ref"),
                "work": item.get("work"),
                "source_layer": item.get("source_layer"),
                "source_form": item.get("source_form"),
                "text": item.get("snippet", ""),
            }
            for item in opened
        ],
    }


def response_content(response: Mapping[str, Any]) -> str:
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


def normalize_direction(value: Any) -> dict[str, str]:
    if isinstance(value, Mapping):
        kind = str(value.get("kind") or "undirected")
    else:
        kind = str(value or "undirected")
    if kind not in {"seed_to_counterpart", "counterpart_to_seed", "undirected"}:
        kind = "undirected"
    return {"kind": kind}


def _forbidden_model_identity_fields(row: Mapping[str, Any]) -> list[str]:
    forbidden = {"person_id", "person_a", "person_b", "resolved_person_id", "counterpart_person_id", "resolved_identity", "provisional_neighbor_id"}
    return sorted(key for key in forbidden if key in row)


def _candidate_evidence(row: Mapping[str, Any], opened_by_ref: Mapping[str, Mapping[str, Any]]) -> tuple[bool, str, str, str]:
    ref = str(row.get("evidence_ref") or "")
    quote = str(row.get("exact_quote") or "")
    if ref not in opened_by_ref:
        return False, "evidence_ref_not_opened", ref, quote
    if not quote:
        return False, "empty_exact_quote", ref, quote
    if not quote_matches(str(opened_by_ref[ref].get("snippet") or ""), quote):
        return False, "exact_quote_not_in_opened_passage", ref, quote
    if not str(row.get("claim") or "").strip():
        return False, "empty_claim", ref, quote
    return True, "", ref, quote


def project_response(*, seed_id: str, response_doc: Mapping[str, Any], opened: Sequence[Mapping[str, Any]], profiles: Mapping[str, Mapping[str, Any]], catalog: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    """Claim-level fail-closed projection using the frozen HNG0.2R resolver."""

    opened_by_ref = {str(row.get("source_ref")): row for row in opened}
    relations: list[dict[str, Any]] = []
    temporal: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    resolutions: dict[str, dict[str, Any]] = {}
    resolution_rows: list[dict[str, Any]] = []

    for index, raw in enumerate(response_doc.get("relation_candidates", [])):
        if not isinstance(raw, Mapping):
            rejected.append({"kind": "relation", "index": index, "reason": "not_object"})
            continue
        forbidden = _forbidden_model_identity_fields(raw)
        if forbidden:
            rejected.append({"kind": "relation", "index": index, "reason": "model_assigned_person_id", "fields": forbidden})
            continue
        if str(raw.get("seed_person_id") or seed_id) != seed_id:
            rejected.append({"kind": "relation", "index": index, "reason": "seed_identity_mismatch"})
            continue
        relation_type = str(raw.get("relation_type") or "")
        if relation_type not in EXTRACTION_RELATION_TYPES:
            rejected.append({"kind": "relation", "index": index, "reason": "invalid_relation_type", "relation_type": relation_type})
            continue
        surface = str(raw.get("counterpart_surface") or "").strip()
        if not surface:
            rejected.append({"kind": "relation", "index": index, "reason": "empty_counterpart_surface"})
            continue
        ok, reason, ref, quote = _candidate_evidence(raw, opened_by_ref)
        if not ok:
            rejected.append({"kind": "relation", "index": index, "reason": reason, "evidence_ref": ref})
            continue
        rid = f"hng1-raw-relation-{stable_hash({'seed': seed_id, 'index': index, 'ref': ref, 'surface': surface})[:20]}"
        opened_row = opened_by_ref[ref]
        row = {
            "relation_id": rid,
            "person_a": seed_id,
            "person_a_name": profiles.get(seed_id, {}).get("canonical_name"),
            "counterpart_surface": surface,
            "relation_type": relation_type,
            "direction": normalize_direction(raw.get("direction")),
            "temporal_scope": dict(raw.get("temporal_scope") or {}) if isinstance(raw.get("temporal_scope"), Mapping) else {},
            "certainty": str(raw.get("confidence") or "low"),
            "ambiguity": str(raw.get("ambiguity") or ""),
            "historical_verification_open": bool(raw.get("historical_verification_open", True)),
            "claim": str(raw.get("claim") or ""),
            "evidence_refs": [ref],
            "evidence_quotes": [{"ref": ref, "quote": quote}],
            "source_works": [opened_row.get("work")],
            "source_forms": [opened_row.get("source_form") or "legacy_local"],
            "source_witnesses": [opened_row.get("source_witness")],
            "extraction_method": "hng1-live-source-extraction",
            "review_status": "candidate",
            "source_review_status": "candidate_model_output",
            "origin": "hng1-live-extraction",
            "one_hop_only": True,
            "cooccurrence_only": False,
            "temporal_warnings": [],
        }
        identity = hng02.resolution_for_candidate(
            row,
            seed_profiles=profiles,
            evidence={ref: opened_row},
            catalog=catalog,
            exact_index=hng02.forms_index(catalog),
            surface_key="counterpart_surface",
            allow_decorated=True,
        )
        resolutions[rid] = identity
        resolution_rows.append(identity)
        relations.append(row)

    for index, raw in enumerate(response_doc.get("temporal_candidates", [])):
        if not isinstance(raw, Mapping):
            rejected.append({"kind": "temporal", "index": index, "reason": "not_object"})
            continue
        forbidden = _forbidden_model_identity_fields(raw)
        if forbidden:
            rejected.append({"kind": "temporal", "index": index, "reason": "model_assigned_person_id", "fields": forbidden})
            continue
        if str(raw.get("seed_person_id") or seed_id) != seed_id:
            rejected.append({"kind": "temporal", "index": index, "reason": "seed_identity_mismatch"})
            continue
        temporal_type = str(raw.get("temporal_type") or "")
        if temporal_type not in EXTRACTION_TEMPORAL_TYPES:
            rejected.append({"kind": "temporal", "index": index, "reason": "invalid_temporal_type", "temporal_type": temporal_type})
            continue
        ok, reason, ref, quote = _candidate_evidence(raw, opened_by_ref)
        if not ok:
            rejected.append({"kind": "temporal", "index": index, "reason": reason, "evidence_ref": ref})
            continue
        surface = str(raw.get("subject_surface") or profiles.get(seed_id, {}).get("canonical_name") or seed_id).strip()
        tid = f"hng1-raw-time-{stable_hash({'seed': seed_id, 'index': index, 'ref': ref, 'surface': surface})[:20]}"
        opened_row = opened_by_ref[ref]
        row = {
            "temporal_id": tid,
            "person_id": seed_id,
            "subject_surface": surface,
            "temporal_type": temporal_type,
            "claim": str(raw.get("claim") or ""),
            "temporal_scope": dict(raw.get("temporal_scope") or {}) if isinstance(raw.get("temporal_scope"), Mapping) else {},
            "precision": str(raw.get("precision") or "unknown"),
            "certainty": str(raw.get("confidence") or "low"),
            "ambiguity": str(raw.get("ambiguity") or ""),
            "historical_verification_open": bool(raw.get("historical_verification_open", True)),
            "evidence_refs": [ref],
            "evidence_quotes": [{"ref": ref, "quote": quote}],
            "source_works": [opened_row.get("work")],
            "source_forms": [opened_row.get("source_form") or "legacy_local"],
            "source_witnesses": [opened_row.get("source_witness")],
            "extraction_method": "hng1-live-source-extraction",
            "review_status": "candidate",
            "source_review_status": "candidate_model_output",
            "origin": "hng1-live-extraction",
            "temporal_warnings": [],
        }
        identity = hng02.resolution_for_candidate(
            row,
            seed_profiles=profiles,
            evidence={ref: opened_row},
            catalog=catalog,
            exact_index=hng02.forms_index(catalog),
            surface_key="subject_surface",
            allow_decorated=True,
        )
        resolutions[tid] = identity
        resolution_rows.append(identity)
        temporal.append(row)

    return {
        "relations": relations,
        "temporal_items": temporal,
        "resolutions": resolution_rows,
        "resolution_map": resolutions,
        "rejected": rejected,
        "used_refs": sorted({str(row.get("evidence_refs", [""])[0]) for row in [*relations, *temporal] if row.get("evidence_refs")}),
        "semantic_delta_present": bool(relations or temporal),
    }


def preflight(transport: DeepSeekTransport) -> dict[str, Any]:
    # Keep the preflight compatible with the repository's known-good minimal
    # client: it deliberately omits JSON mode because the probe asks for the
    # literal OK and is not an extraction completion.  HNG1 extraction calls
    # still use the persistent SRM transport and JSON mode below.
    started = utc_now()
    monotonic_start = time.monotonic()
    try:
        response = call_deepseek(
            [{"role": "user", "content": "Reply only with OK"}],
            model=MODEL,
            temperature=0,
            timeout=60,
        )
        elapsed = round(time.monotonic() - monotonic_start, 6)
        usage = response.get("usage", {}) if isinstance(response, Mapping) else {}
        attempt = {
            "story_id": "hng1-preflight",
            "round": 0,
            "completion_kind": "preflight",
            "attempt": 1,
            "actual_request": True,
            "start_time": started,
            "elapsed_seconds": elapsed,
            "http_status": 200,
            "exception_class": None,
            "exception_message": None,
            "failure_class": None,
            "response_model": response.get("model") if isinstance(response, Mapping) else None,
            "api_usage": dict(usage) if isinstance(usage, Mapping) else {},
        }
        return {"status": "reachable", "failure_class": None, "attempts": [attempt], "api_usage": dict(usage) if isinstance(usage, Mapping) else {}}
    except Exception as exc:  # transport/auth errors stay outside model findings
        elapsed = round(time.monotonic() - monotonic_start, 6)
        status_match = re.search(r"HTTP\s+(\d{3})", str(exc), flags=re.IGNORECASE)
        status = int(status_match.group(1)) if status_match else None
        failure = classify_transport_error(exc, status)
        attempt = {
            "story_id": "hng1-preflight",
            "round": 0,
            "completion_kind": "preflight",
            "attempt": 1,
            "actual_request": True,
            "start_time": started,
            "elapsed_seconds": elapsed,
            "http_status": status,
            "exception_class": type(exc).__name__,
            "exception_message": str(exc),
            "failure_class": failure,
            "response_model": None,
            "api_usage": {},
        }
        return {"status": "unavailable", "failure_class": failure, "attempts": [attempt], "api_usage": {}}


def evidence_record(item: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "evidence_ref": item.get("source_ref"),
        "source_work": item.get("work"),
        "source_layer": item.get("source_layer"),
        "source_form": item.get("source_form"),
        "source_witness": item.get("source_witness"),
        "original_text": item.get("original_text", ""),
        "model_snippet": item.get("snippet", ""),
        "locator": item.get("locator", {}),
        "source_path": item.get("source_path"),
        "source_sha256": item.get("source_sha256"),
        "source_url": item.get("source_url"),
        "revision_id": item.get("revision_id"),
        "window_start": item.get("window_start"),
        "window_end": item.get("window_end"),
    }


def _aggregate_usage(rows: Sequence[Mapping[str, Any]]) -> dict[str, int]:
    keys = ("prompt_tokens", "completion_tokens", "total_tokens")
    return {key: sum(int(row.get(key) or 0) for row in rows) for key in keys}


def _safe_attempt_stats(attempts: Sequence[Mapping[str, Any]]) -> dict[str, int]:
    counts = collections.Counter()
    for row in attempts:
        if int(row.get("attempt") or 1) > 1:
            counts["transport_retry_count"] += 1
        if row.get("failure_class"):
            counts[f"{row.get('failure_class')}_count"] += 1
        if row.get("failure_class") is None:
            counts["transport_success_count"] += 1
    return dict(counts)


def _normalized_projection(raw_relations: Sequence[Mapping[str, Any]], raw_temporal: Sequence[Mapping[str, Any]], resolutions: Mapping[str, Mapping[str, Any]], evidence: Mapping[str, Mapping[str, Any]], catalog: Mapping[str, Mapping[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    relations, _ = hng02.normalize_relations(raw_relations, resolutions=resolutions, evidence=evidence, catalog=catalog)
    temporal = hng02.normalize_temporal(raw_temporal, resolutions=resolutions, catalog=catalog)
    by_id = {str(row.get("relation_id")): row for row in raw_relations}
    for row in relations:
        raw_ids = row.get("candidate_ids", [])
        source_forms: set[str] = set()
        source_witnesses: set[str] = set()
        for raw_id in raw_ids:
            raw = by_id.get(str(raw_id), {})
            source_forms.update(str(value) for value in raw.get("source_forms", []) if value)
            source_witnesses.update(str(value) for value in raw.get("source_witnesses", []) if value)
        row["source_forms"] = sorted(source_forms) or ["legacy_local"]
        row["source_witnesses"] = sorted(source_witnesses)
        row["origin"] = "hng1-live-extraction"
        row["extraction_method"] = "hng1-live-source-extraction"
        row["one_hop_only"] = True
    raw_time_by_id = {str(row.get("temporal_id")): row for row in raw_temporal}
    for row in temporal:
        raw = raw_time_by_id.get(str(row.get("candidate_ids", [""])[0]), {})
        row["source_forms"] = sorted({str(value) for value in raw.get("source_forms", []) if value}) or ["legacy_local"]
        row["source_witnesses"] = sorted({str(value) for value in raw.get("source_witnesses", []) if value})
        row["origin"] = "hng1-live-extraction"
        row["extraction_method"] = "hng1-live-source-extraction"
    return relations, temporal


def _audit_sample(resolutions: Sequence[Mapping[str, Any]], relations: Sequence[Mapping[str, Any]], temporal: Sequence[Mapping[str, Any]], evidence: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    def item(kind: str, row: Mapping[str, Any]) -> dict[str, Any]:
        refs = row.get("supporting_evidence_refs") or row.get("evidence_refs") or []
        return {
            "kind": kind,
            "candidate_id": row.get("candidate_id") or row.get("relation_id") or row.get("temporal_id"),
            "source_passages": [
                {"ref": str(ref), "text": evidence.get(str(ref), {}).get("original_text"), "source_work": evidence.get(str(ref), {}).get("source_work")}
                for ref in refs if str(ref) in evidence
            ],
            "extracted_surface": row.get("surface") or row.get("counterpart_surface") or row.get("subject_surface"),
            "resolver_method": row.get("resolution_method"),
            "resolved_identity": row.get("resolved_person_id") or row.get("provisional_person_id"),
            "resolution_status": row.get("resolution_status") or row.get("subject_resolution_status"),
            "relation_type": row.get("normalized_relation_type") or row.get("relation_type"),
            "semantic_level": row.get("semantic_level"),
            "evidence_refs": list(refs),
            "confidence": row.get("confidence") or row.get("certainty"),
            "claim": row.get("claim"),
            "temporal_warning": row.get("temporal_warnings", []),
        }

    out: list[dict[str, Any]] = []
    resolved = [row for row in resolutions if row.get("resolution_status") == "resolved_existing_person"]
    provisional = [row for row in resolutions if row.get("resolution_status") == "resolved_provisional_person"]
    ambiguous = [row for row in resolutions if row.get("resolution_status") == "ambiguous_identity"]
    out.extend(item("resolved_existing_identity", row) for row in resolved[:20])
    out.extend(item("provisional_identity", row) for row in provisional[:20])
    out.extend(item("ambiguous_identity", row) for row in ambiguous)
    out.extend(item("normalized_relation", row) for row in relations[:20])
    out.extend(item("documented_political_interaction", row) for row in relations if row.get("normalized_relation_type") == "documented_political_interaction")
    out.extend(item("kinship_relation", row) for row in relations if row.get("semantic_level") == "hard_relation" and row.get("normalized_relation_type") in {"parent_child", "grandparent_grandchild", "sibling", "uncle_nephew", "cousin_clan_kin", "marriage", "affinal_relation"})
    return {
        "schema": 1,
        "stage": "hng1-audit-sample",
        "canonical_write_back": False,
        "items": out,
        "requested_sample": {"resolved_existing": 20, "provisional": 20, "ambiguous": "all", "relations": 20, "documented_political": 10, "kinship": 10},
    }


def run_live(*, count_per_stratum: int = 12) -> dict[str, Any]:
    selection, profiles = selection_and_profiles(count_per_stratum)
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    RAW_ROOT.mkdir(parents=True, exist_ok=True)
    catalog = build_people_catalog(ROOT)
    punctuated, legacy = load_retrieval_sources()
    transport = DeepSeekTransport(connect_timeout=15, read_timeout=180, backoff_seconds=2.0)
    pf = preflight(transport)
    write_json(Path("/tmp/hng1-preflight.json"), pf)

    trace_rows: list[dict[str, Any]] = []
    evidence: dict[str, dict[str, Any]] = {}
    raw_relations: list[dict[str, Any]] = []
    raw_temporal: list[dict[str, Any]] = []
    resolution_rows: list[dict[str, Any]] = []
    usages: list[dict[str, Any]] = []
    successful_latencies: list[float] = []
    all_attempts: list[dict[str, Any]] = list(pf.get("attempts", []))
    rejected_claims: list[dict[str, Any]] = []
    story_statuses: list[dict[str, Any]] = []
    model_calls = 0
    protocol_failures = 0
    semantic_failures = 0
    execution_failure = pf.get("status") != "reachable"

    for selected in selection.get("people", []):
        pid = str(selected.get("person_id"))
        profile = profiles[pid]
        find_result = find_punctuated_first(profile, punctuated, legacy, top_k=8)
        opened = open_short_hits(find_result, punctuated, legacy, max_passages=6)
        for item in opened:
            evidence[str(item["source_ref"])] = evidence_record(item)
        trace = {
            "seed_person_id": pid,
            "stratum": selected.get("stratum"),
            "routes": find_result.get("routes", []),
            "searched": [{"work": row.get("work"), "reason": row.get("reason")} for row in find_result.get("routes", [])],
            "retrieved": [
                {key: hit.get(key) for key in ("source_ref", "work", "source_layer", "source_form", "score", "matched_terms")}
                for hit in find_result.get("hits", [])
            ],
            "opened": [str(item.get("source_ref")) for item in opened],
            "used": [],
            "source_forms": dict(sorted(collections.Counter(str(item.get("source_form")) for item in opened).items())),
            "fallback_used": bool(find_result.get("fallback_used")),
            "status": "pending",
        }

        if execution_failure:
            trace["status"] = "execution_environment_failure"
            trace["failure_class"] = pf.get("failure_class")
            trace_rows.append(trace)
            story_statuses.append({"person_id": pid, "status": "execution_environment_failure", "failure_class": pf.get("failure_class")})
            continue

        packet = model_packet(profile, opened)
        raw_path = RAW_ROOT / f"{pid}-attempt-01.json"
        if raw_path.is_file():
            raw_artifact = read_json(raw_path)
            call = {
                "success": bool(raw_artifact.get("raw_response")),
                "response": raw_artifact.get("raw_response"),
                "content": raw_artifact.get("content", ""),
                "failure_class": raw_artifact.get("failure_class"),
                "attempts": raw_artifact.get("attempts", []),
                "reused": True,
            }
        else:
            model_calls += 1
            call = transport.call(
                story_id=pid,
                round_number=1,
                completion_kind="source_extraction",
                messages=[{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": json.dumps(packet, ensure_ascii=False, sort_keys=True)}],
                max_retries=1,
            )
            raw_artifact = {
                "schema": 1,
                "stage": "hng1-raw-extraction",
                "canonical_write_back": False,
                "seed_person_id": pid,
                "model": MODEL,
                "prompt_version": PROMPT_VERSION,
                "model_input_hash": json_hash(packet),
                "retrieved_refs": [str(item.get("source_ref")) for item in opened],
                "raw_response": call.get("response"),
                "content": call.get("content", ""),
                "attempts": call.get("attempts", []),
                "failure_class": call.get("failure_class"),
                "transport_error": call.get("error"),
                "immutable": True,
            }
            write_if_absent(raw_path, raw_artifact)

        attempts = call.get("attempts", [])
        all_attempts.extend(attempts)
        stats = _safe_attempt_stats(attempts)
        if call.get("success"):
            for attempt in attempts:
                if attempt.get("failure_class") is None:
                    successful_latencies.append(float(attempt.get("elapsed_seconds") or 0))
            usage = (call.get("response") or {}).get("usage", {}) if isinstance(call.get("response"), Mapping) else {}
            if isinstance(usage, Mapping):
                usages.append(dict(usage))
            try:
                response_doc = json.loads(str(call.get("content") or ""))
                if not isinstance(response_doc, Mapping) or not isinstance(response_doc.get("relation_candidates", []), list) or not isinstance(response_doc.get("temporal_candidates", []), list):
                    raise ValueError("response schema lacks candidate arrays")
            except Exception as exc:  # protocol failure, raw response remains immutable
                protocol_failures += 1
                trace["status"] = "protocol_failure"
                trace["failure_class"] = "protocol_failure"
                trace["protocol_error"] = type(exc).__name__
                story_statuses.append({"person_id": pid, "status": "protocol_failure", "reason": str(exc)})
                trace_rows.append(trace)
                continue
            projected = project_response(seed_id=pid, response_doc=response_doc, opened=opened, profiles=profiles, catalog=catalog)
            raw_relations.extend(projected["relations"])
            raw_temporal.extend(projected["temporal_items"])
            resolution_rows.extend(projected["resolutions"])
            rejected_claims.extend({"seed_person_id": pid, **row} for row in projected["rejected"])
            trace["used"] = projected["used_refs"]
            trace["rejected_evidence_or_claims"] = projected["rejected"]
            if (response_doc.get("relation_candidates") or response_doc.get("temporal_candidates")) and not projected["semantic_delta_present"]:
                semantic_failures += 1
                trace["status"] = "semantic_failure"
                story_statuses.append({"person_id": pid, "status": "semantic_failure", "rejected_count": len(projected["rejected"])})
            else:
                trace["status"] = "valid_model_response"
                story_statuses.append({"person_id": pid, "status": "valid_model_response", "candidate_count": len(projected["relations"]) + len(projected["temporal_items"])})
        else:
            trace["status"] = "transport_failure"
            trace["failure_class"] = call.get("failure_class")
            story_statuses.append({"person_id": pid, "status": "transport_failure", "failure_class": call.get("failure_class")})
        trace_rows.append(trace)

    resolution_map = {str(row.get("candidate_id")): row for row in resolution_rows if row.get("candidate_id")}
    normalized_relations, normalized_temporal = _normalized_projection(raw_relations, raw_temporal, resolution_map, evidence, catalog)
    unresolved = [row for row in resolution_rows if row.get("resolution_status") in {"unresolved_identity", "ambiguous_identity"}]
    neighborhoods: list[dict[str, Any]] = []
    for selected in selection.get("people", []):
        pid = str(selected.get("person_id"))
        rels = [row for row in normalized_relations if row.get("person_a") == pid]
        times = [row for row in normalized_temporal if row.get("person_id") == pid]
        nearby = sorted({str(row.get("person_b")) for row in rels if row.get("person_b")} | {str(row.get("provisional_neighbor_id")) for row in rels if row.get("provisional_neighbor_id")})
        refs = sorted({str(ref) for row in [*rels, *times] for ref in row.get("evidence_refs", [])})
        neighborhoods.append({
            "person_id": pid,
            "canonical_name": profiles[pid].get("canonical_name"),
            "seed": True,
            "one_hop_only": True,
            "nearby_person_ids": nearby,
            "relations": [row.get("relation_id") for row in rels],
            "temporal_items": [row.get("temporal_id") for row in times],
            "evidence_refs": refs,
            "approximate_temporal_window": {},
        })

    source_form_counts = collections.Counter()
    used_source_counts = collections.Counter()
    for row in trace_rows:
        source_form_counts.update(row.get("source_forms", {}))
        for ref in row.get("used", []):
            used_source_counts[str(evidence.get(str(ref), {}).get("source_form") or "unknown")] += 1
    status_counts = collections.Counter(str(row.get("status")) for row in story_statuses)
    identity_counts = collections.Counter(str(row.get("resolution_status")) for row in resolution_rows)
    method_counts = collections.Counter(str(row.get("resolution_method")) for row in resolution_rows)
    level_counts = collections.Counter(str(row.get("semantic_level")) for row in normalized_relations)
    type_counts = collections.Counter(str(row.get("normalized_relation_type")) for row in normalized_relations)
    all_successful = successful_latencies
    usage = _aggregate_usage(usages)
    transport_stats = _safe_attempt_stats(all_attempts)
    metrics = {
        "schema": 1,
        "stage": "hng1-metrics",
        "canonical_write_back": False,
        "execution_kind": "execution_environment_failure" if execution_failure else "real_model",
        "live_model_findings": bool(not execution_failure and (raw_relations or raw_temporal)),
        "preflight": pf,
        "seed_count": len(selection.get("people", [])),
        "seed_person_ids": [str(row.get("person_id")) for row in selection.get("people", [])],
        "story_status_counts": dict(sorted(status_counts.items())),
        "protocol_failure_count": protocol_failures,
        "semantic_failure_count": semantic_failures,
        "transport_failure_count": status_counts.get("transport_failure", 0),
        "identity_occurrence_count": len(resolution_rows),
        "identity_status_counts": dict(sorted(identity_counts.items())),
        "resolved_by_method": dict(sorted(method_counts.items())),
        "resolved_existing_rate": round(identity_counts.get("resolved_existing_person", 0) / len(resolution_rows), 6) if resolution_rows else 0,
        "resolved_provisional_rate": round(identity_counts.get("resolved_provisional_person", 0) / len(resolution_rows), 6) if resolution_rows else 0,
        "unresolved_rate": round(identity_counts.get("unresolved_identity", 0) / len(resolution_rows), 6) if resolution_rows else 0,
        "ambiguous_rate": round(identity_counts.get("ambiguous_identity", 0) / len(resolution_rows), 6) if resolution_rows else 0,
        "normalized_relation_count": len(normalized_relations),
        "relation_level_counts": dict(sorted(level_counts.items())),
        "relation_type_counts": dict(sorted(type_counts.items())),
        "evidence_backed_relation_rate": round(sum(bool(row.get("evidence_refs")) for row in normalized_relations) / len(normalized_relations), 6) if normalized_relations else 0,
        "new_neighbor_count": len({str(row.get("person_b")) for row in normalized_relations if row.get("person_b")} | {str(row.get("provisional_neighbor_id")) for row in normalized_relations if row.get("provisional_neighbor_id")}),
        "new_neighbor_yield_per_seed": round((len({str(row.get("person_b")) for row in normalized_relations if row.get("person_b")} | {str(row.get("provisional_neighbor_id")) for row in normalized_relations if row.get("provisional_neighbor_id")})) / len(selection.get("people", [])), 6) if selection.get("people") else 0,
        "temporal_candidate_count": len(normalized_temporal),
        "retrieval_hit_rate": round(sum(bool(row.get("retrieved")) for row in trace_rows) / len(trace_rows), 6) if trace_rows else 0,
        "opening_precision": round(sum(len(row.get("used", [])) for row in trace_rows) / sum(len(row.get("opened", [])) for row in trace_rows), 6) if sum(len(row.get("opened", [])) for row in trace_rows) else 0,
        "evidence_use_rate": round(len({ref for row in trace_rows for ref in row.get("used", [])}) / len({ref for row in trace_rows for ref in row.get("opened", [])}), 6) if {ref for row in trace_rows for ref in row.get("opened", [])} else 0,
        "retrieved_passages": sum(len(row.get("retrieved", [])) for row in trace_rows),
        "opened_passages": sum(len(row.get("opened", [])) for row in trace_rows),
        "used_evidence_refs": len({ref for row in trace_rows for ref in row.get("used", [])}),
        "punctuated_first_hit_count": sum(1 for row in trace_rows if any(item.get("source_form") == "punctuated" for item in row.get("retrieved", []))),
        "legacy_fallback_count": sum(1 for row in trace_rows if row.get("fallback_used")),
        "source_form_usage": dict(sorted(source_form_counts.items())),
        "used_source_contribution": dict(sorted(used_source_counts.items())),
        "api_request_count": model_calls,
        "api_usage": usage,
        "transport_metrics": {
            "transport_request_count": sum(1 for row in all_attempts if row.get("actual_request") is not False),
            "transport_retry_count": transport_stats.get("transport_retry_count", 0),
            "transport_success_count": transport_stats.get("transport_success_count", 0),
            "tls_failure_count": transport_stats.get("tls_failure_count", 0),
            "read_timeout_count": transport_stats.get("read_timeout_count", 0),
            "connect_timeout_count": transport_stats.get("connect_timeout_count", 0),
            "server_error_count": transport_stats.get("server_error_count", 0),
        },
        "latency": {
            "successful_request_count": len(all_successful),
            "median_successful_seconds": statistics.median(all_successful) if all_successful else 0,
            "max_successful_seconds": max(all_successful) if all_successful else 0,
        },
        "rejected_claim_count": len(rejected_claims),
        "evidence_validation_failures": sum(1 for row in rejected_claims if "evidence" in str(row.get("reason"))),
        "model": MODEL,
        "provider": PROVIDER,
        "prompt_version": PROMPT_VERSION,
        "one_hop_only": True,
    }

    manifest = {
        "schema": 1,
        "stage": "hng1-manifest",
        "canonical_write_back": False,
        "execution_kind": metrics["execution_kind"],
        "live_model_findings": metrics["live_model_findings"],
        "provider": PROVIDER,
        "model": MODEL,
        "prompt_version": PROMPT_VERSION,
        "resolver_version": hng02.DECORATED_RESOLVER_VERSION,
        "resolver_source_hash": sha256_file(SCRIPT_DIR / "build_hng0_2.py"),
        "resolver_builder_hash": sha256_file(SCRIPT_DIR / "build_hng0_2r.py"),
        "hng02r_manifest_hash": sha256_file(ROOT / "data/generated/hng0-2r/manifest.json"),
        "selection_hash": json_hash(selection),
        "seed_person_ids": [str(row.get("person_id")) for row in selection.get("people", [])],
        "one_hop_only": True,
        "preflight": pf,
        "model_calls": model_calls,
        "raw_extraction_hashes": {
            str(path.relative_to(OUTPUT_ROOT)): sha256_file(path)
            for path in sorted(RAW_ROOT.glob("*.json"))
            if path.is_file()
        },
        "raw_extraction_policy": "append-only attempt files; no canonical identity assignment",
        "source_policy": "registered local corpora only; punctuated-first with legacy fallback; no web",
        "outputs": [
            "hng1-selection.json", "search-profiles.json", "retrieval-trace.json", "source-evidence-registry.json",
            "identity-resolution.json", "relations.json", "temporal-items.json", "neighborhoods.json",
            "unresolved-identities.json", "audit-sample.json", "metrics.json", "manifest.json",
        ],
    }
    write_json(TRACE_PATH, {"schema": 1, "stage": "hng1-retrieval-trace", "canonical_write_back": False, "trace": trace_rows})
    write_json(EVIDENCE_PATH, {"schema": 1, "stage": "hng1-source-evidence-registry", "canonical_write_back": False, "evidence": dict(sorted(evidence.items()))})
    write_json(IDENTITY_PATH, {"schema": 1, "stage": "hng1-identity-resolution", "canonical_write_back": False, "resolver_version": hng02.DECORATED_RESOLVER_VERSION, "resolutions": sorted(resolution_rows, key=lambda row: (str(row.get("candidate_kind")), str(row.get("candidate_id"))))})
    write_json(RELATION_PATH, {"schema": 1, "stage": "hng1-normalized-relations", "canonical_write_back": False, "relations": normalized_relations, "evidence": dict(sorted(evidence.items())), "rejected": rejected_claims})
    write_json(TEMPORAL_PATH, {"schema": 1, "stage": "hng1-temporal-items", "canonical_write_back": False, "temporal_items": normalized_temporal, "evidence": dict(sorted(evidence.items()))})
    write_json(NEIGHBOR_PATH, {"schema": 1, "stage": "hng1-neighborhoods", "canonical_write_back": False, "people": neighborhoods})
    write_json(UNRESOLVED_PATH, {"schema": 1, "stage": "hng1-unresolved-identities", "canonical_write_back": False, "items": sorted(unresolved, key=lambda row: (str(row.get("seed_person_id")), str(row.get("surface"))))})
    write_json(AUDIT_PATH, _audit_sample(resolution_rows, normalized_relations, normalized_temporal, evidence))
    write_json(METRICS_PATH, metrics)
    write_json(MANIFEST_PATH, manifest)
    review = {
        "schema": 1,
        "stage": "hng1-review-overlay",
        "canonical_write_back": False,
        "relation_decisions": {str(row.get("relation_id")): {"review_status": "candidate", "reviewer_note": ""} for row in normalized_relations},
        "temporal_decisions": {str(row.get("temporal_id")): {"review_status": "candidate", "reviewer_note": ""} for row in normalized_temporal},
        "identity_decisions": {str(row.get("candidate_id")): {"review_status": "candidate", "reviewer_note": ""} for row in resolution_rows},
    }
    write_json(REVIEW_PATH, review)
    return {"selection": selection, "metrics": metrics, "manifest": manifest, "statuses": story_statuses}


def prepare(*, count_per_stratum: int = 12) -> dict[str, Any]:
    selection, profiles = selection_and_profiles(count_per_stratum)
    return {"selection": selection, "profiles": profiles}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--prepare", action="store_true", help="write deterministic frozen selection/profiles only")
    mode.add_argument("--live", action="store_true", help="perform the approved-network live HNG1 run")
    parser.add_argument("--count-per-stratum", type=int, default=12)
    args = parser.parse_args()
    if args.live:
        result = run_live(count_per_stratum=args.count_per_stratum)
        print(json.dumps({"status": "pass" if result["metrics"].get("execution_kind") == "real_model" else "execution_environment_failure", "metrics": result["metrics"]}, ensure_ascii=False, indent=2))
        return 0 if result["metrics"].get("execution_kind") == "real_model" else 2
    result = prepare(count_per_stratum=args.count_per_stratum)
    print(json.dumps({"status": "prepared", "seed_count": len(result["selection"].get("people", [])), "selection": [row.get("person_id") for row in result["selection"].get("people", [])]}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
