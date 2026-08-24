#!/usr/bin/env python3
"""HNG2-L live validation runner.

This module is intentionally an evaluation wrapper around the frozen HNG2
implementation.  It owns selection, live transport orchestration, claim-level
validation, and reporting; it does not alter the HNG2 resolver or source
ranking rules.  All outputs are generated candidates and remain outside the
canonical data model.
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

ROOT = Path(__file__).resolve().parents[1]
SCRIPT_DIR = ROOT / "scripts"
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import build_hng0_2 as hng02  # noqa: E402
import build_hng2 as hng2  # noqa: E402
import historical_entity_resolver as resolver  # noqa: E402
from hng0_1_common import (  # noqa: E402
    build_source_units,
    quote_matches,
    sha256_file,
    stable_hash,
    write_json,
)
from hng1_common import _load_shishuo_units, load_retrieval_sources, open_short_hits, find_punctuated_first  # noqa: E402
from srm0_4c_transport import DeepSeekTransport, classify_transport_error  # noqa: E402
from smoke_deepseek import call_deepseek  # noqa: E402


OUT = ROOT / "data/generated/hng2-live"
RAW_ROOT = OUT / "raw-api"
REVIEW_PATH = ROOT / "data/annotation/hng2-live-review.json"
SELECTION_PATH = OUT / "live-selection.json"
MODEL = "deepseek-v4-flash"
PROVIDER = "deepseek"
RESOLVER_VERSION = resolver.RESOLVER_VERSION
PROMPT_VERSION = "hng2-live-frozen-extraction-and-identity-v1"
IDENTITY_PROMPT_VERSION = "hng2-live-frozen-identity-assist-v1"
RUN_SCHEMA = 1

HARD_RELATIONS = set(hng02.HARD_RELATIONS)
DOCUMENTED_INTERACTIONS = set(hng02.DOCUMENTED_INTERACTIONS)
INTERPRETED_RELATIONS = set(hng02.INTERPRETED_RELATIONS)
RELATION_TYPES = HARD_RELATIONS | DOCUMENTED_INTERACTIONS | INTERPRETED_RELATIONS
TEMPORAL_TYPES = {
    "birth", "death", "office_tenure", "residence_activity_phase", "major_event_participation",
}
SEMANTIC_LEVELS = {"hard_relation", "documented_interaction", "interpreted_relation"}

EXTRACTION_SYSTEM_PROMPT = """你是历史资料候选抽取器。只使用所给本地原文，不使用外部知识。
只抽取原文明确支持的一跳人物关系、时间事实和人物表面；同现、同姓、推测、性格判断不能单独形成关系。
不要分配 person_id。每条候选必须引用一个给定 evidence_ref，并逐字引用其中的连续 exact_quote。
关系只使用 allowed_relation_types，时间只使用 allowed_temporal_types；证据不足就不输出。
严格返回 JSON，不要 Markdown：
{"relation_candidates":[{"counterpart_surface":"","relation_type":"","semantic_level":"","direction":"seed_to_counterpart|counterpart_to_seed|undirected","claim":"","evidence_ref":"","exact_quote":"","confidence":"high|medium|low","historical_verification_open":true}],"temporal_candidates":[{"subject_surface":"","temporal_type":"","claim":"","temporal_scope":{},"precision":"exact|circa|before|after|between|reign_period|unknown","evidence_ref":"","exact_quote":"","confidence":"high|medium|low","historical_verification_open":true}],"identity_surfaces":[{"surface":"","evidence_ref":"","exact_quote":""}]}"""

IDENTITY_SYSTEM_PROMPT = """你是受约束的历史人物表面判别器。只使用提供的原文、候选键和时间/图证据。
不得创造 person_id 或候选键，不得使用外部知识。chosen_candidate_key 只能是给定候选键，无法确定则为 null。
必须返回 JSON：{"entity_type":"person|role|unknown","chosen_candidate_key":"c0 或 null","normalized_surface":"","syntactic_relation":"","evidence_span":"","confidence":"high|medium|low|unknown","short_reason":""}"""


def read_json(path: Path, default: Any = None) -> Any:
    if not path.is_file():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def json_hash(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _compact(value: Any) -> str:
    return " ".join(str(value or "").split())


def _redact(value: Any) -> Any:
    text = str(value or "")
    secret = __import__("os").environ.get("DEEPSEEK_API_KEY")
    return text.replace(secret, "[REDACTED]") if secret else text


def _stable_key(frontier_id: str) -> str:
    return stable_hash({"stage": "hng2-live-selection-v1", "frontier_id": frontier_id})


def _load_frontier() -> list[dict[str, Any]]:
    doc = read_json(ROOT / "data/generated/hng2/frontier-selection.json", {}) or {}
    rows = [dict(row) for row in doc.get("frontiers", []) if isinstance(row, Mapping) and row.get("frontier_id")]
    return sorted(rows, key=lambda row: str(row.get("frontier_id")))


def _load_hng2_relations() -> list[dict[str, Any]]:
    doc = read_json(ROOT / "data/generated/hng2/relations.json", {}) or {}
    return [dict(row) for row in doc.get("relations", []) if isinstance(row, Mapping)]


def _frontier_label(row: Mapping[str, Any], provisional: Mapping[str, Mapping[str, Any]]) -> str:
    return _compact(row.get("label") or provisional.get(str(row.get("frontier_id")), {}).get("label") or row.get("frontier_id"))


def _selection_signals(rows: Sequence[Mapping[str, Any]]) -> dict[str, dict[str, Any]]:
    relations = _load_hng2_relations()
    degree: collections.Counter[str] = collections.Counter()
    hard: collections.Counter[str] = collections.Counter()
    interaction: collections.Counter[str] = collections.Counter()
    methods: collections.Counter[str] = collections.Counter()
    risk: collections.Counter[str] = collections.Counter()
    evidence: collections.Counter[str] = collections.Counter()
    for row in relations:
        for key in ("person_a", "person_b", "provisional_neighbor_id"):
            value = str(row.get(key) or "")
            if value:
                degree[value] += 1
                hard[value] += int(row.get("semantic_level") == "hard_relation")
                interaction[value] += int(row.get("semantic_level") == "documented_interaction")
                evidence[value] += len(row.get("evidence_refs", []))
    identities = read_json(ROOT / "data/generated/hng2/identity-resolution.json", {}) or {}
    for row in identities.get("resolutions", []):
        if not isinstance(row, Mapping):
            continue
        seed = str(row.get("seed_person_id") or "")
        if not seed:
            continue
        resolution = row.get("resolution") if isinstance(row.get("resolution"), Mapping) else {}
        method = str(resolution.get("resolution_method") or "")
        methods[f"{seed}:{method}"] += 1
        risk[seed] += int((row.get("temporal_gate") or {}).get("status") in {"unknown", "conflict"})
        risk[seed] += int(len(resolution.get("candidate_set", [])) > 1)
    catalog = resolver.person_catalog()
    index = resolver.forms_index(catalog)
    provisional = {str(row.get("frontier_id")): row for row in rows if not row.get("person_id")}
    result: dict[str, dict[str, Any]] = {}
    for row in rows:
        fid = str(row.get("frontier_id"))
        label = _frontier_label(row, provisional)
        pid = str(row.get("person_id") or "")
        forms = resolver.catalog_forms(catalog.get(pid, {})) if pid in catalog else [label]
        candidate_overlap = max((len(index.get(resolver.matching_normalize(form), [])) for form in forms if form), default=0)
        signals = {
            "frontier_id": fid,
            "person_id": pid or None,
            "label": label,
            "canonical": bool(pid and pid in catalog),
            "degree": int(degree.get(fid, 0)),
            "hard_relation_degree": int(hard.get(fid, 0)),
            "interaction_degree": int(interaction.get(fid, 0)),
            "evidence_count": int(evidence.get(fid, 0)),
            "complex_score": sum(methods.get(f"{fid}:{m}", 0) for m in ("title", "decorated_name_suffix", "kinship_context", "reviewed_contextual_alias")),
            "temporal_risk": int(risk.get(fid, 0)),
            "same_name_candidates": int(candidate_overlap),
            "short_surface": len(resolver.matching_normalize(label)) <= 2,
            "selection_key": _stable_key(fid),
        }
        result[fid] = signals
    return result


def _pick(pool: Sequence[str], signals: Mapping[str, Mapping[str, Any]], count: int, *, reverse_score: bool = True) -> list[str]:
    def key(fid: str) -> tuple[Any, ...]:
        row = signals[fid]
        score = (int(row.get("degree", 0)) * 5 + int(row.get("hard_relation_degree", 0)) * 7 + int(row.get("interaction_degree", 0)) * 2 + int(row.get("evidence_count", 0)))
        return ((-score if reverse_score else score), str(row.get("selection_key")), fid)
    return sorted(pool, key=key)[:count]


def build_live_selection() -> dict[str, Any]:
    rows = _load_frontier()
    if not rows:
        raise RuntimeError("HNG2 frontier is empty")
    provisional_doc = read_json(ROOT / "data/generated/hng2/provisional-persons.json", {}) or {}
    provisional = {str(row.get("provisional_person_id")): dict(row) for row in provisional_doc.get("persons", []) if isinstance(row, Mapping) and row.get("provisional_person_id")}
    signals = _selection_signals(rows)
    all_ids = sorted(signals)
    canonical = [fid for fid in all_ids if signals[fid]["canonical"]]
    provisional_ids = [fid for fid in all_ids if not signals[fid]["canonical"]]
    selected: dict[str, str] = {}
    canonical_rank = sorted(canonical, key=lambda fid: (-int(signals[fid]["degree"]), str(signals[fid]["selection_key"]), fid))
    high = canonical_rank[: max(2, min(2, len(canonical_rank)))]
    low = sorted(canonical_rank, key=lambda fid: (int(signals[fid]["degree"]), str(signals[fid]["selection_key"]), fid))[:2]
    middle_pool = [fid for fid in canonical_rank if fid not in set(high) | set(low)]
    middle = _pick(middle_pool, signals, 2)
    for fid in [*high, *middle, *low]:
        if fid not in selected:
            selected[fid] = "canonical_existing"
    remaining = [fid for fid in all_ids if fid not in selected]
    provisional_rank = sorted(provisional_ids, key=lambda fid: (-int(signals[fid]["degree"]), str(signals[fid]["selection_key"]), fid))
    for fid in provisional_rank:
        if len([x for x, cat in selected.items() if cat == "high_confidence_provisional"]) >= 6:
            break
        selected[fid] = "high_confidence_provisional"
    remaining = [fid for fid in all_ids if fid not in selected]
    complex_pool = sorted(remaining, key=lambda fid: (-int(signals[fid]["complex_score"]), -int(signals[fid]["hard_relation_degree"]), str(signals[fid]["selection_key"]), fid))
    for fid in complex_pool[:4]:
        selected[fid] = "complex_title_or_kinship"
    remaining = [fid for fid in all_ids if fid not in selected]
    risk_pool = sorted(remaining, key=lambda fid: (-int(signals[fid]["temporal_risk"]), -int(signals[fid]["same_name_candidates"]), -int(signals[fid]["short_surface"]), str(signals[fid]["selection_key"]), fid))
    for fid in risk_pool[:4]:
        selected[fid] = "same_name_or_temporal_risk"
    remaining = [fid for fid in all_ids if fid not in selected]
    sparse_pool = sorted(remaining, key=lambda fid: (int(signals[fid]["degree"]), int(signals[fid]["evidence_count"]), str(signals[fid]["selection_key"]), fid))
    for fid in sparse_pool[:4]:
        selected[fid] = "sparse_low_connectivity"
    if len(selected) < 24:
        for fid in sorted((set(all_ids) - set(selected)), key=lambda x: (str(signals[x]["selection_key"]), x)):
            selected[fid] = "deterministic_fill"
            if len(selected) == 24:
                break
    if len(selected) != 24:
        raise RuntimeError(f"HNG2 frontier has only {len(selected)} eligible selection rows")
    people: list[dict[str, Any]] = []
    for fid, category in sorted(selected.items(), key=lambda item: (item[1], str(signals[item[0]]["selection_key"]), item[0])):
        row = dict(next(row for row in rows if str(row.get("frontier_id")) == fid))
        people.append({
            "frontier_id": fid,
            "person_id": row.get("person_id"),
            "provisional_person_id": row.get("provisional_person_id"),
            "label": _frontier_label(row, provisional),
            "origin": row.get("origin"),
            "category": category,
            "selection_key": signals[fid]["selection_key"],
            "signals": signals[fid],
            "one_hop_only": True,
        })
    counts = dict(sorted(collections.Counter(row["category"] for row in people).items()))
    protected = {
        "data/generated/hng2/frontier-selection.json": sha256_file(ROOT / "data/generated/hng2/frontier-selection.json"),
        "data/generated/hng2/relations.json": sha256_file(ROOT / "data/generated/hng2/relations.json"),
        "data/generated/hng2/identity-resolution.json": sha256_file(ROOT / "data/generated/hng2/identity-resolution.json"),
        "data/generated/hng2/provisional-persons.json": sha256_file(ROOT / "data/generated/hng2/provisional-persons.json"),
    }
    return {
        "schema": RUN_SCHEMA,
        "stage": "hng2-live-selection",
        "frozen": True,
        "selection_method": "hng2-frontier-signal-stratified-deterministic-v1",
        "frontier_source": "data/generated/hng2/frontier-selection.json",
        "selected_count": len(people),
        "target_composition": {"canonical": 6, "high_confidence_provisional": 6, "complex_title_or_kinship": 4, "same_name_or_temporal_risk": 4, "sparse_low_connectivity": 4},
        "actual_composition": counts,
        "people": people,
        "one_hop_only": True,
        "wave_cap": 2,
        "source_hashes": protected,
        "resolver_version": RESOLVER_VERSION,
        "canonical_write_back": False,
    }


def freeze_selection() -> dict[str, Any]:
    generated = build_live_selection()
    OUT.mkdir(parents=True, exist_ok=True)
    if SELECTION_PATH.is_file():
        existing = read_json(SELECTION_PATH)
        if existing != generated:
            raise RuntimeError("live selection already exists and differs from frozen deterministic selection")
        return existing
    write_json(SELECTION_PATH, generated)
    return generated


def _profile(row: Mapping[str, Any], catalog: Mapping[str, Mapping[str, Any]], provisional: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    fid = str(row.get("frontier_id"))
    pid = str(row.get("person_id") or "")
    if pid in catalog:
        base = dict(catalog[pid])
        forms = resolver.catalog_forms(base)
        base.update({"person_id": pid, "frontier_id": fid, "forms": forms, "search_terms_original": forms, "search_terms_normalized": [resolver.matching_normalize(x) for x in forms], "frontier_origin": "canonical_person"})
        return base
    label = _compact(row.get("label") or provisional.get(str(row.get("provisional_person_id") or fid), {}).get("label") or fid)
    return {
        "person_id": fid,
        "frontier_id": fid,
        "canonical_name": label,
        "forms": [label],
        "courtesy_forms": [],
        "alias_forms": [],
        "office_titles": [],
        "surname": "",
        "search_terms_original": [label],
        "search_terms_normalized": [resolver.matching_normalize(label)],
        "frontier_origin": "hng2_provisional",
    }


def _seed_identity_gate(profile: Mapping[str, Any], unit: Mapping[str, Any]) -> dict[str, Any]:
    text = str(unit.get("text") or unit.get("original_text") or "")
    terms = [resolver.matching_normalize(x) for x in profile.get("forms", []) if len(resolver.matching_normalize(x)) >= 2]
    hit = [term for term in terms if term and term in resolver.matching_normalize(text)]
    if hit:
        return {"status": "compatible", "reason": "canonical_or_profile_form_hit", "matched_terms": sorted(set(hit))}
    return {"status": "conflict", "reason": "opened passage does not contain a seed-identifying form", "matched_terms": []}


def _source_record(item: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "evidence_ref": item.get("source_ref"),
        "source_work": item.get("work"),
        "source_layer": item.get("source_layer"),
        "source_form": item.get("source_form"),
        "source_witness": item.get("source_witness"),
        "original_text": str(item.get("original_text") or item.get("text") or ""),
        "model_snippet": str(item.get("snippet") or ""),
        "locator": item.get("locator", {}),
        "source_path": item.get("source_path"),
        "source_sha256": item.get("source_sha256"),
        "source_url": item.get("source_url"),
        "revision_id": item.get("revision_id"),
        "window_start": item.get("window_start"),
        "window_end": item.get("window_end"),
    }


def retrieve_person(row: Mapping[str, Any], profiles: Mapping[str, Mapping[str, Any]], punctuated: Sequence[Mapping[str, Any]], legacy: Sequence[Mapping[str, Any]]) -> tuple[dict[str, Any], dict[str, dict[str, Any]]]:
    fid = str(row.get("frontier_id"))
    profile = profiles[fid]
    found = find_punctuated_first(profile, punctuated, legacy, top_k=8)
    opened = open_short_hits(found, punctuated, legacy, max_passages=4)
    evidence: dict[str, dict[str, Any]] = {}
    gates: list[dict[str, Any]] = []
    accepted: list[dict[str, Any]] = []
    rejected_temporal: list[dict[str, Any]] = []
    rejected_seed: list[dict[str, Any]] = []
    for item in opened:
        ref = str(item.get("source_ref") or "")
        if not ref or ref in evidence:
            continue
        source = _source_record(item)
        evidence[ref] = source
        seed_gate = _seed_identity_gate(profile, source)
        temporal = resolver.temporal_gate(profile, source)
        decision = {"frontier_id": fid, "person_id": row.get("person_id") or fid, "evidence_ref": ref, "seed_identity": seed_gate, "temporal": temporal, "source_form": source.get("source_form"), "work": source.get("source_work")}
        gates.append(decision)
        if seed_gate["status"] == "conflict":
            rejected_seed.append({"evidence_ref": ref, "reason": seed_gate["reason"]})
        elif temporal.get("status") == "conflict":
            rejected_temporal.append({"evidence_ref": ref, "reason": temporal.get("reason"), "constraints": temporal.get("constraints", [])})
        else:
            accepted.append({**source, "temporal_status": temporal.get("status"), "seed_identity_status": seed_gate.get("status")})
    trace = {
        "wave": row.get("wave", 1),
        "frontier_id": fid,
        "person_id": row.get("person_id") or fid,
        "searched_corpora": [dict(x) for x in found.get("routes", [])],
        "retrieved_refs": [str(x.get("source_ref")) for x in found.get("hits", []) if x.get("source_ref")],
        "opened_refs": [str(x.get("source_ref")) for x in opened if x.get("source_ref")],
        "used_refs": [],
        "new_used_refs": [],
        "source_forms": sorted(set(str(x.get("source_form")) for x in opened if x.get("source_form"))),
        "source_form_by_ref": {str(x.get("source_ref")): str(x.get("source_form")) for x in opened if x.get("source_ref")},
        "routing_reason": "punctuated_first_then_legacy_fallback",
        "fallback_used": bool(found.get("fallback_used")),
        "opened_chars": sum(len(str(x.get("snippet") or "")) for x in opened),
        "seed_identity_gate_decisions": gates,
        "rejected_by_temporal_gate": rejected_temporal,
        "rejected_by_seed_identity_gate": rejected_seed,
        "candidate_passages": [{"ref": x["evidence_ref"], "work": x.get("source_work"), "source_form": x.get("source_form"), "text": x.get("model_snippet", ""), "locator": x.get("locator", {})} for x in accepted],
    }
    return trace, {str(x["evidence_ref"]): x for x in accepted}


def _model_packet(profile: Mapping[str, Any], trace: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "seed_person": {"frontier_id": profile.get("frontier_id"), "canonical_name": profile.get("canonical_name"), "aliases": profile.get("forms", [])},
        "allowed_relation_types": sorted(RELATION_TYPES),
        "allowed_temporal_types": sorted(TEMPORAL_TYPES),
        "passages": [{key: item.get(key) for key in ("ref", "work", "source_form", "text", "locator")} for item in trace.get("candidate_passages", [])],
    }


def _content_to_json(content: str) -> Mapping[str, Any]:
    value = str(content or "").strip()
    if value.startswith("```"):
        value = re.sub(r"^```(?:json)?\s*|\s*```$", "", value, flags=re.IGNORECASE | re.DOTALL).strip()
    parsed = json.loads(value)
    if not isinstance(parsed, Mapping):
        raise ValueError("model JSON is not an object")
    return parsed


def _valid_quote(ref: str, quote: str, evidence: Mapping[str, Mapping[str, Any]]) -> tuple[bool, str]:
    if not ref or ref not in evidence:
        return False, "evidence_ref_not_supplied"
    if not quote:
        return False, "empty_exact_quote"
    original = str(evidence[ref].get("original_text") or "")
    snippet = str(evidence[ref].get("model_snippet") or "")
    if quote in snippet or quote in original:
        return True, ""
    # Only boundary punctuation/whitespace normalization is allowed.
    trimmed = quote.strip(" \t\n\r，。；、：:!?！？『』「」（）()[]【】\"")
    if trimmed and (trimmed in snippet or trimmed in original):
        return True, "quote_boundary_trimmed"
    if quote_matches(snippet, quote) or quote_matches(original, quote):
        return True, "whitespace_normalized"
    return False, "exact_quote_not_in_source"


def _graph_for(seed_id: str, candidate_id: str, evidence_refs: Sequence[str], candidate_id_current: str, claim: str, graph_edges: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    return resolver.graph_support(seed_id=seed_id, candidate_id=candidate_id, edges=graph_edges, current_evidence_refs=evidence_refs, current_candidate_id=candidate_id_current, current_claim=claim)


def _candidate_forms(catalog: Mapping[str, Mapping[str, Any]], surface: str) -> list[str]:
    folded = resolver.matching_normalize(surface)
    exact = sorted(set(resolver.forms_index(catalog).get(folded, [])))
    if exact:
        return exact
    if len(folded) >= 2:
        values = []
        for pid, person in sorted(catalog.items()):
            if any(len(resolver.matching_normalize(form)) > len(folded) and resolver.matching_normalize(form).endswith(folded) for form in resolver.catalog_forms(person)):
                values.append(pid)
        return sorted(set(values))
    return []


def _identity_occurrence(surface: str, seed: Mapping[str, Any], ref: str, quote: str, context: str, evidence: Mapping[str, Mapping[str, Any]], catalog: Mapping[str, Mapping[str, Any]], contextual: Sequence[Mapping[str, Any]], graph_edges: Sequence[Mapping[str, Any]], occurrence_id: str, temporal: Mapping[str, Any]) -> dict[str, Any]:
    resolution = resolver.resolve_identity(
        surface=surface, seed=seed, context=context, evidence=evidence, catalog=catalog,
        index=resolver.forms_index(catalog), contextual_registry=contextual, graph_edges=graph_edges,
        evidence_refs=[ref], candidate_id=occurrence_id, temporal=temporal,
    )
    graph = resolution.get("graph_support") if isinstance(resolution.get("graph_support"), Mapping) else {}
    return {
        "occurrence_id": occurrence_id,
        "seed_person_id": seed.get("person_id"),
        "surface": surface,
        "evidence_ref": ref,
        "exact_quote": quote,
        "source_work": evidence.get(ref, {}).get("source_work"),
        "source_form": evidence.get(ref, {}).get("source_form"),
        "context_excerpt": context[:1000],
        "resolution": dict(resolution),
        "candidate_set": list(resolution.get("candidate_set", [])),
        "graph_support": dict(graph),
        "temporal_status": temporal.get("status", "unknown"),
        "canonical_write_back": False,
    }


def _project_extraction(seed_row: Mapping[str, Any], trace: Mapping[str, Any], evidence: Mapping[str, Mapping[str, Any]], response_doc: Mapping[str, Any], catalog: Mapping[str, Mapping[str, Any]], profiles: Mapping[str, Mapping[str, Any]], contextual: Sequence[Mapping[str, Any]], graph_edges: Sequence[Mapping[str, Any]], wave: int) -> dict[str, Any]:
    seed_id = str(seed_row.get("person_id") or seed_row.get("frontier_id"))
    seed = dict(profiles[str(seed_row.get("frontier_id"))])
    seed["person_id"] = seed_id
    opened_refs = set(str(x) for x in trace.get("opened_refs", []))
    accepted_refs = set(str(x.get("ref")) for x in trace.get("candidate_passages", []) if x.get("ref"))
    rejects: list[dict[str, Any]] = []
    relations: list[dict[str, Any]] = []
    temporal_items: list[dict[str, Any]] = []
    identities: list[dict[str, Any]] = []
    used_refs: set[str] = set()
    def evidence_for(raw: Mapping[str, Any], kind: str, index: int) -> tuple[str, str] | None:
        ref = str(raw.get("evidence_ref") or "")
        quote = str(raw.get("exact_quote") or "")
        if ref not in accepted_refs or ref not in evidence:
            rejects.append({"kind": kind, "index": index, "reason": "evidence_ref_not_opened", "evidence_ref": ref})
            return None
        ok, reason = _valid_quote(ref, quote, evidence)
        if not ok:
            rejects.append({"kind": kind, "index": index, "reason": reason, "evidence_ref": ref, "exact_quote": quote})
            return None
        if reason:
            rejects.append({"kind": kind, "index": index, "reason": reason, "evidence_ref": ref})
        return ref, quote
    for index, raw in enumerate(response_doc.get("relation_candidates", [])):
        if not isinstance(raw, Mapping):
            rejects.append({"kind": "relation", "index": index, "reason": "not_object"}); continue
        surface = _compact(raw.get("counterpart_surface"))
        relation_type = str(raw.get("relation_type") or "")
        level = str(raw.get("semantic_level") or ("hard_relation" if relation_type in HARD_RELATIONS else "documented_interaction" if relation_type in DOCUMENTED_INTERACTIONS else "interpreted_relation" if relation_type in INTERPRETED_RELATIONS else ""))
        if not surface or relation_type not in RELATION_TYPES or level not in SEMANTIC_LEVELS:
            rejects.append({"kind": "relation", "index": index, "reason": "invalid_relation_or_surface", "relation_type": relation_type, "semantic_level": level}); continue
        evidence_item = evidence_for(raw, "relation", index)
        if not evidence_item:
            continue
        ref, quote = evidence_item
        claim = _compact(raw.get("claim"))
        if not claim:
            rejects.append({"kind": "relation", "index": index, "reason": "empty_claim"}); continue
        occurrence_id = f"hng2-live-w{wave}-relation-{stable_hash({'seed': seed_id, 'index': index, 'ref': ref, 'surface': surface})[:20]}"
        source = evidence[ref]
        gate = next((g for g in trace.get("seed_identity_gate_decisions", []) if str(g.get("evidence_ref")) == ref), {})
        context = str(source.get("original_text") or source.get("model_snippet") or "")
        identity = _identity_occurrence(surface, seed, ref, quote, context, evidence, catalog, contextual, graph_edges, occurrence_id, {"status": gate.get("temporal", {}).get("status", "unknown")})
        identities.append({**identity, "candidate_kind": "relation", "wave": wave})
        used_refs.add(ref)
        relations.append({
            "relation_id": occurrence_id, "person_a": seed_id, "counterpart_surface": surface,
            "relation_type": relation_type, "semantic_level": level, "direction": str(raw.get("direction") or "undirected"),
            "claim": claim, "certainty": str(raw.get("confidence") or "low"), "historical_verification_open": bool(raw.get("historical_verification_open", True)),
            "evidence_refs": [ref], "evidence_quotes": [{"ref": ref, "quote": quote}], "source_work": source.get("source_work"), "source_form": source.get("source_form"),
            "identity_occurrence_id": occurrence_id, "wave": wave, "one_hop_only": True, "candidate_only": True, "canonical_write_back": False,
        })
    for index, raw in enumerate(response_doc.get("temporal_candidates", [])):
        if not isinstance(raw, Mapping):
            rejects.append({"kind": "temporal", "index": index, "reason": "not_object"}); continue
        temporal_type = str(raw.get("temporal_type") or "")
        if temporal_type not in TEMPORAL_TYPES:
            rejects.append({"kind": "temporal", "index": index, "reason": "invalid_temporal_type", "temporal_type": temporal_type}); continue
        evidence_item = evidence_for(raw, "temporal", index)
        if not evidence_item:
            continue
        ref, quote = evidence_item
        surface = _compact(raw.get("subject_surface") or seed.get("canonical_name"))
        claim = _compact(raw.get("claim"))
        if not claim or not surface:
            rejects.append({"kind": "temporal", "index": index, "reason": "empty_claim_or_surface"}); continue
        occurrence_id = f"hng2-live-w{wave}-temporal-{stable_hash({'seed': seed_id, 'index': index, 'ref': ref, 'surface': surface})[:20]}"
        source = evidence[ref]
        gate = next((g for g in trace.get("seed_identity_gate_decisions", []) if str(g.get("evidence_ref")) == ref), {})
        context = str(source.get("original_text") or source.get("model_snippet") or "")
        identity = _identity_occurrence(surface, seed, ref, quote, context, evidence, catalog, contextual, graph_edges, occurrence_id, {"status": gate.get("temporal", {}).get("status", "unknown")})
        identities.append({**identity, "candidate_kind": "temporal", "wave": wave})
        used_refs.add(ref)
        temporal_items.append({
            "temporal_id": occurrence_id, "person_id": seed_id, "subject_surface": surface, "temporal_type": temporal_type, "claim": claim,
            "temporal_scope": raw.get("temporal_scope") if isinstance(raw.get("temporal_scope"), Mapping) else {}, "precision": str(raw.get("precision") or "unknown"),
            "certainty": str(raw.get("confidence") or "low"), "historical_verification_open": bool(raw.get("historical_verification_open", True)),
            "evidence_refs": [ref], "evidence_quotes": [{"ref": ref, "quote": quote}], "source_work": source.get("source_work"), "source_form": source.get("source_form"),
            "identity_occurrence_id": occurrence_id, "wave": wave, "one_hop_only": True, "candidate_only": True, "canonical_write_back": False,
        })
    # Explicit identity surfaces are optional; relation/time surfaces are also
    # identity occurrences.  Add only separately cited surfaces here.
    for index, raw in enumerate(response_doc.get("identity_surfaces", [])):
        if not isinstance(raw, Mapping):
            rejects.append({"kind": "identity", "index": index, "reason": "not_object"}); continue
        surface = _compact(raw.get("surface"))
        evidence_item = evidence_for(raw, "identity", index)
        if not surface or not evidence_item:
            continue
        ref, quote = evidence_item
        source = evidence[ref]
        occurrence_id = f"hng2-live-w{wave}-identity-{stable_hash({'seed': seed_id, 'index': index, 'ref': ref, 'surface': surface})[:20]}"
        identities.append({**_identity_occurrence(surface, seed, ref, quote, str(source.get("original_text") or ""), evidence, catalog, contextual, graph_edges, occurrence_id, {"status": "unknown"}), "candidate_kind": "identity", "wave": wave})
    by_key: dict[tuple[str, str, str], dict[str, Any]] = {}
    deduped_identities: list[dict[str, Any]] = []
    for item in identities:
        key = (str(item.get("seed_person_id")), str(item.get("surface")), str(item.get("evidence_ref")))
        if key not in by_key:
            by_key[key] = item
            deduped_identities.append(item)
    trace_used = sorted(used_refs)
    return {"relations": relations, "temporal_items": temporal_items, "identities": deduped_identities, "rejected": rejects, "used_refs": trace_used, "semantic_delta_present": bool(relations or temporal_items)}


def _identity_assist_packet(item: Mapping[str, Any], catalog: Mapping[str, Mapping[str, Any]], profiles: Mapping[str, Mapping[str, Any]], graph_edges: Sequence[Mapping[str, Any]], evidence: Mapping[str, Mapping[str, Any]]) -> tuple[dict[str, Any], dict[str, str]]:
    surface = str(item.get("surface") or "")
    candidates = list(item.get("candidate_set") or [])
    if not candidates:
        candidates = _candidate_forms(catalog, surface)
    keys: dict[str, str] = {f"c{index}": pid for index, pid in enumerate(sorted(set(candidates)))}
    seed_id = str(item.get("seed_person_id") or "")
    seed = profiles.get(seed_id, {"person_id": seed_id, "canonical_name": seed_id})
    ref = str(item.get("evidence_ref") or "")
    source = evidence.get(ref, {})
    independent = []
    for key, pid in keys.items():
        independent.append({"candidate_key": key, "canonical_name": catalog.get(pid, {}).get("canonical_name"), "aliases": resolver.catalog_forms(catalog.get(pid, {})), "graph_support": resolver.graph_support(seed_id=seed_id, candidate_id=pid, edges=graph_edges, current_evidence_refs=[ref], current_candidate_id=str(item.get("occurrence_id")), current_claim="")})
    packet = {
        "seed_person": {"frontier_id": seed_id, "canonical_name": seed.get("canonical_name"), "aliases": seed.get("forms", [])},
        "surface": surface,
        "source": {"work": source.get("source_work"), "unit": source.get("locator", {}), "quote": item.get("exact_quote"), "passage": source.get("model_snippet")},
        "candidate_persons": independent,
        "temporal_constraint": {"status": item.get("temporal_status", "unknown")},
        "independent_graph_evidence": independent,
    }
    return packet, keys


def _validate_assist_output(doc: Mapping[str, Any], keys: Mapping[str, str], item: Mapping[str, Any], evidence: Mapping[str, Mapping[str, Any]], catalog: Mapping[str, Mapping[str, Any]]) -> tuple[bool, str, dict[str, Any]]:
    choice = doc.get("chosen_candidate_key")
    if choice is not None and str(choice) not in keys:
        return False, "model_invented_candidate_key", {}
    entity_type = str(doc.get("entity_type") or "")
    if entity_type not in {"person", "role", "unknown"}:
        return False, "invalid_entity_type", {}
    span = str(doc.get("evidence_span") or "")
    ref = str(item.get("evidence_ref") or "")
    ok, reason = _valid_quote(ref, span, evidence)
    if not ok:
        return False, "invalid_evidence_span:" + reason, {}
    confidence = str(doc.get("confidence") or "")
    if confidence not in {"high", "medium", "low", "unknown"}:
        return False, "invalid_confidence", {}
    if str(item.get("temporal_status")) == "conflict":
        return False, "temporal_conflict", {}
    chosen = keys.get(str(choice)) if choice is not None else None
    if chosen and chosen not in catalog:
        return False, "candidate_not_in_catalog", {}
    return True, "", {"chosen_person_id": chosen, "evidence_span": span, "entity_type": entity_type, "confidence": confidence, "short_reason": _compact(doc.get("short_reason")), "candidate_key": choice}


def _apply_identity_assist(items: Sequence[Mapping[str, Any]], transport: DeepSeekTransport, profiles: Mapping[str, Mapping[str, Any]], catalog: Mapping[str, Mapping[str, Any]], graph_edges: Sequence[Mapping[str, Any]], evidence: Mapping[str, Mapping[str, Any]], raw_dir: Path, run_id: str, counters: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    final: list[dict[str, Any]] = []
    assist_rows: list[dict[str, Any]] = []
    for item in items:
        resolution = item.get("resolution") if isinstance(item.get("resolution"), Mapping) else {}
        status = str(resolution.get("resolution_status") or "unresolved")
        if status == "resolved_existing_person":
            final.append({**dict(item), "final_status": "deterministic_resolved", "final_person_id": resolution.get("resolved_person_id"), "assist_called": False})
            continue
        # Provisional named surfaces remain candidates; only ambiguous or
        # unresolved cases get the residual semantic call.
        if status not in {"ambiguous", "unresolved"}:
            final.append({**dict(item), "final_status": "provisional", "final_person_id": None, "assist_called": False})
            continue
        packet, keys = _identity_assist_packet(item, catalog, profiles, graph_edges, evidence)
        occurrence_id = str(item.get("occurrence_id"))
        path = raw_dir / f"identity-{occurrence_id}-attempt-01.json"
        if path.is_file():
            artifact = read_json(path, {}) or {}
            call = {"success": bool(artifact.get("raw_response")), "response": artifact.get("raw_response"), "content": artifact.get("content", ""), "attempts": artifact.get("attempts", []), "failure_class": artifact.get("failure_class"), "reused": True}
        else:
            counters["identity_assist_calls"] += 1
            call = transport.call(story_id=occurrence_id, round_number=int(item.get("wave") or 1), completion_kind="identity_assist", messages=[{"role": "system", "content": IDENTITY_SYSTEM_PROMPT}, {"role": "user", "content": json.dumps(packet, ensure_ascii=False, sort_keys=True)}], max_retries=1)
            artifact = {"schema": 1, "stage": "hng2-live-raw-identity-assist", "occurrence_id": occurrence_id, "model": MODEL, "prompt_version": IDENTITY_PROMPT_VERSION, "model_input_hash": json_hash(packet), "raw_response": call.get("response"), "content": call.get("content", ""), "attempts": call.get("attempts", []), "failure_class": call.get("failure_class"), "transport_error": _redact(call.get("error")), "immutable": True, "canonical_write_back": False}
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(artifact, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        if not call.get("success"):
            final.append({**dict(item), "final_status": "unresolved", "final_person_id": None, "assist_called": True, "assist_failure": call.get("failure_class")})
            assist_rows.append({"occurrence_id": occurrence_id, "eligible": True, "status": "transport_failed", "candidate_keys": keys, "attempts": call.get("attempts", []), "canonical_write_back": False})
            counters["identity_assist_transport_failures"] += 1
            continue
        try:
            doc = _content_to_json(str(call.get("content") or ""))
            valid, reason, projected = _validate_assist_output(doc, keys, item, evidence, catalog)
        except Exception as exc:  # protocol failure belongs to the identity assist only
            valid, reason, projected = False, f"protocol:{type(exc).__name__}", {}
        if valid and projected.get("chosen_person_id"):
            final.append({**dict(item), "final_status": "llm_resolved", "final_person_id": projected["chosen_person_id"], "assist_called": True, "assist_validation": projected})
            counters["identity_llm_resolved"] += 1
            assist_status = "llm_resolved"
        elif valid:
            final.append({**dict(item), "final_status": "unresolved", "final_person_id": None, "assist_called": True, "assist_validation": projected})
            assist_status = "unresolved"
        else:
            final.append({**dict(item), "final_status": "rejected", "final_person_id": None, "assist_called": True, "assist_rejection": reason})
            counters["identity_llm_rejected"] += 1
            assist_status = "rejected"
        assist_rows.append({"occurrence_id": occurrence_id, "eligible": True, "status": assist_status, "candidate_keys": keys, "validation_error": None if valid else reason, "model_output": dict(doc) if 'doc' in locals() and isinstance(doc, Mapping) else None, "canonical_write_back": False})
    return final, assist_rows


def _merge_relations(rows: Sequence[Mapping[str, Any]], final_identities: Mapping[str, Mapping[str, Any]]) -> list[dict[str, Any]]:
    merged: dict[tuple[str, str, str, str], dict[str, Any]] = {}
    for row in sorted(rows, key=lambda item: str(item.get("relation_id"))):
        identity = final_identities.get(str(row.get("identity_occurrence_id")), {})
        endpoint = str(identity.get("final_person_id") or "")
        final_status = str(identity.get("final_status") or "")
        provisional_id = None if endpoint else (f"hng2-live-provisional-{stable_hash({'surface': row.get('counterpart_surface'), 'seed': row.get('person_a')})[:20]}" if final_status in {"provisional", "unresolved"} else None)
        if not endpoint and not provisional_id:
            continue
        key = (str(row.get("person_a")), endpoint or provisional_id or "", str(row.get("relation_type")), str(row.get("direction")))
        candidate = dict(row)
        candidate.update({"person_b": endpoint or None, "provisional_neighbor_id": provisional_id, "final_identity_status": final_status, "candidate_only": True, "canonical_write_back": False})
        if key not in merged:
            merged[key] = candidate
            continue
        target = merged[key]
        target["evidence_refs"] = sorted(set(target.get("evidence_refs", [])) | set(candidate.get("evidence_refs", [])))
        target["evidence_quotes"] = sorted({(str(x.get("ref")), str(x.get("quote"))) for x in [*target.get("evidence_quotes", []), *candidate.get("evidence_quotes", [])] if isinstance(x, Mapping)})
        target["evidence_quotes"] = [{"ref": a, "quote": b} for a, b in target["evidence_quotes"]]
        target.setdefault("merged_relation_ids", []).append(candidate.get("relation_id"))
    return sorted(merged.values(), key=lambda item: (str(item.get("person_a")), str(item.get("person_b") or item.get("provisional_neighbor_id")), str(item.get("relation_type"))))


def _wave2_selection(relations: Sequence[Mapping[str, Any]], identities: Sequence[Mapping[str, Any]], catalog: Mapping[str, Mapping[str, Any]], wave1_ids: set[str]) -> dict[str, Any]:
    by_occ = {str(row.get("occurrence_id")): row for row in identities}
    candidates: dict[str, dict[str, Any]] = {}
    for row in relations:
        identity = by_occ.get(str(row.get("identity_occurrence_id")), {})
        if str(identity.get("final_status") or "") not in {"deterministic_resolved", "llm_resolved", "provisional"}:
            continue
        endpoint = str(identity.get("final_person_id") or "")
        if endpoint and endpoint in wave1_ids:
            continue
        if endpoint and endpoint in catalog:
            fid = endpoint; label = catalog[endpoint].get("canonical_name"); status = "resolved_existing"
        else:
            fid = str(identity.get("provisional_person_id") or f"hng2-live-provisional-{stable_hash(row.get('counterpart_surface'))[:20]}")
            label = row.get("counterpart_surface"); status = "strong_provisional"
        item = candidates.setdefault(fid, {"frontier_id": fid, "person_id": endpoint or None, "provisional_person_id": None if endpoint else fid, "label": label, "evidence_refs": [], "relation_ids": [], "status": status, "one_hop_only": True})
        item["evidence_refs"] = sorted(set(item["evidence_refs"]) | set(row.get("evidence_refs", [])))
        item["relation_ids"].append(row.get("relation_id"))
    ranked = sorted(candidates.values(), key=lambda item: (-len(item.get("evidence_refs", [])), str(stable_hash(item.get("frontier_id"))), str(item.get("frontier_id"))))[:8]
    for item in ranked:
        item["wave"] = 2
        item["frontier_state"] = "eligible_frontier"
        item["eligibility_basis"] = ["explicit_candidate_identity", "traceable_evidence", "no_temporal_conflict"]
    return {"schema": RUN_SCHEMA, "stage": "hng2-live-wave-2-selection", "selected_count": len(ranked), "max_wave_2": 8, "frontiers": ranked, "wave_3_created": False, "canonical_write_back": False}


def _consolidation(identities: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    rows = [row for row in identities if row.get("final_status") in {"provisional", "llm_resolved"}]
    result: list[dict[str, Any]] = []
    for index, left in enumerate(rows):
        for right in rows[index + 1:]:
            if str(left.get("surface")) != str(right.get("surface")):
                continue
            if str(left.get("seed_person_id")) == str(right.get("seed_person_id")):
                continue
            result.append({"candidate_id": f"hng2-live-merge-{stable_hash((left.get('occurrence_id'), right.get('occurrence_id')))[:20]}", "left_occurrence_id": left.get("occurrence_id"), "right_occurrence_id": right.get("occurrence_id"), "surface": left.get("surface"), "status": "candidate", "reason": "same_surface_requires_independent_context_review", "canonical_write_back": False})
    return sorted(result, key=lambda item: str(item.get("candidate_id")))


def _audit(identities: Sequence[Mapping[str, Any]], temporal_rejections: Sequence[Mapping[str, Any]], wave2: Sequence[Mapping[str, Any]], consolidations: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    selected: list[dict[str, Any]] = []
    deterministic_sample_added = 0
    unresolved_sample_added = 0
    for row in identities:
        resolution = row.get("resolution") if isinstance(row.get("resolution"), Mapping) else {}
        graph = row.get("graph_support") if isinstance(row.get("graph_support"), Mapping) else {}
        must_show = row.get("final_status") == "llm_resolved" or graph.get("independent_graph_support_count") or row.get("final_status") in {"ambiguous", "unresolved"}
        if row.get("final_status") == "deterministic_resolved" and deterministic_sample_added < 10:
            must_show = True
            deterministic_sample_added += 1
        if row.get("final_status") in {"ambiguous", "unresolved"}:
            unresolved_sample_added += 1
        if must_show:
            selected.append({"kind": "identity", "audit_id": f"hng2-live-audit-{row.get('occurrence_id')}", "seed_person_id": row.get("seed_person_id"), "source_work": row.get("source_work") or None, "evidence_ref": row.get("evidence_ref"), "exact_quote": row.get("exact_quote"), "source_passage": row.get("context_excerpt"), "surface": row.get("surface"), "resolution_method": resolution.get("resolution_method"), "final_status": row.get("final_status"), "resolved_person_id": row.get("final_person_id"), "candidate_set": row.get("candidate_set", []), "graph_support_edges": graph.get("graph_support_edges", []), "excluded_circular_edges": graph.get("excluded_circular_edges", []), "review": "not_reviewed", "canonical_write_back": False})
    for row in temporal_rejections:
        selected.append({"kind": "temporal_conflict_rejection", "audit_id": f"hng2-live-audit-temporal-{row.get('evidence_ref')}", **dict(row), "review": "not_reviewed", "canonical_write_back": False})
    for row in wave2:
        selected.append({"kind": "wave_2_promotion", "audit_id": f"hng2-live-audit-wave2-{row.get('frontier_id')}", **dict(row), "review": "not_reviewed", "canonical_write_back": False})
    for row in consolidations:
        selected.append({"kind": "provisional_consolidation", "audit_id": f"hng2-live-audit-{row.get('candidate_id')}", **dict(row), "review": "not_reviewed", "canonical_write_back": False})
    return sorted(selected, key=lambda item: str(item.get("audit_id")))


def _usage_totals(usages: Sequence[Mapping[str, Any]]) -> dict[str, int]:
    keys = ("prompt_tokens", "completion_tokens", "total_tokens", "prompt_cache_hit_tokens", "prompt_cache_miss_tokens")
    return {key: sum(int(row.get(key) or 0) for row in usages) for key in keys}


def _write_review(relations: Sequence[Mapping[str, Any]], temporal: Sequence[Mapping[str, Any]], audit: Sequence[Mapping[str, Any]]) -> None:
    write_json(REVIEW_PATH, {
        "schema": 1,
        "stage": "hng2-live-review-overlay",
        "review_values": ["correct", "false_merge", "false_split", "bad_seed_match", "bad_temporal_rejection", "bad_llm_resolution", "uncertain", "not_reviewed"],
        "identity_decisions": {str(row.get("audit_id")): {"review_status": "not_reviewed", "reviewer_note": ""} for row in audit},
        "relation_decisions": {str(row.get("relation_id")): {"review_status": "not_reviewed", "reviewer_note": ""} for row in relations},
        "temporal_decisions": {str(row.get("temporal_id")): {"review_status": "not_reviewed", "reviewer_note": ""} for row in temporal},
        "canonical_write_back": False,
    })


def _preflight() -> dict[str, Any]:
    """Use the repository's minimal endpoint probe before JSON-mode calls.

    DeepSeek accepts the live JSON extraction contract, but a literal ``OK``
    probe should not send an empty tools array or JSON response-format request.
    This is the same endpoint and environment/key as the existing smoke
    client, and it keeps environment failure outside HNG2-L findings.
    """
    started = utc_now()
    begin = time.monotonic()
    try:
        response = call_deepseek([{"role": "user", "content": "Reply only with OK"}], model=MODEL, temperature=0, timeout=60)
        elapsed = round(time.monotonic() - begin, 6)
        usage = response.get("usage", {}) if isinstance(response, Mapping) else {}
        return {
            "status": "reachable", "classification": None, "attempts": [{
                "attempt": 1, "start_time": started, "elapsed_seconds": elapsed, "http_status": 200,
                "exception_class": None, "exception_message": None, "failure_class": None,
                "response_model": response.get("model") if isinstance(response, Mapping) else None,
                "api_usage": dict(usage) if isinstance(usage, Mapping) else {},
            }], "api_usage": dict(usage) if isinstance(usage, Mapping) else {},
        }
    except Exception as exc:  # noqa: BLE001 - preflight classifies boundary failures
        elapsed = round(time.monotonic() - begin, 6)
        match = re.search(r"HTTP\s+(\d{3})", str(exc), flags=re.IGNORECASE)
        status = int(match.group(1)) if match else None
        failure = classify_transport_error(exc, status)
        return {
            "status": "unavailable", "classification": failure, "attempts": [{
                "attempt": 1, "start_time": started, "elapsed_seconds": elapsed, "http_status": status,
                "exception_class": type(exc).__name__, "exception_message": _redact(exc), "failure_class": failure,
                "response_model": None, "api_usage": {},
            }], "api_usage": {},
        }


def run_live(*, run_id: str | None = None, quiet: bool = False) -> dict[str, Any]:
    selection = freeze_selection()
    run_id = run_id or dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    raw_dir = RAW_ROOT / run_id
    raw_dir.mkdir(parents=True, exist_ok=True)
    catalog = resolver.person_catalog()
    frontier_rows = _load_frontier()
    frontier_by_id = {str(row.get("frontier_id")): row for row in frontier_rows}
    provisional_doc = read_json(ROOT / "data/generated/hng2/provisional-persons.json", {}) or {}
    provisional = {str(row.get("provisional_person_id")): dict(row) for row in provisional_doc.get("persons", []) if isinstance(row, Mapping) and row.get("provisional_person_id")}
    selected_rows = []
    for row in selection.get("people", []):
        source = dict(frontier_by_id[str(row["frontier_id"])])
        source.update({"category": row.get("category"), "label": row.get("label"), "wave": 1})
        selected_rows.append(source)
    profiles = {str(row.get("frontier_id")): _profile(row, catalog, provisional) for row in selected_rows}
    # Freeze resolver/catalog/routing inputs before the first live request.
    hng0_edges = hng2._hng0_accepted_edges()
    contextual = resolver.build_contextual_identity_registry(catalog=catalog, accepted_only=True)
    punctuated, legacy = load_retrieval_sources()
    transport = DeepSeekTransport(connect_timeout=15, read_timeout=180, backoff_seconds=2.0)
    preflight = {**_preflight(), "run_id": run_id}
    Path("/tmp/hng2-live-preflight.json").write_text(json.dumps(preflight, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if preflight["status"] != "reachable":
        status = {"schema": RUN_SCHEMA, "stage": "hng2-live", "run_id": run_id, "execution_status": "live_network_unavailable", "failure_class": preflight.get("classification"), "selection_path": str(SELECTION_PATH.relative_to(ROOT)), "story_results_created": False, "canonical_write_back": False}
        write_json(OUT / "run-status.json", status)
        if not quiet:
            print(json.dumps({"status": "live_network_unavailable", "failure_class": preflight.get("classification"), "preflight_path": "/tmp/hng2-live-preflight.json"}, ensure_ascii=False, sort_keys=True))
        return status
    status_path = OUT / "run-status.json"
    if status_path.is_file():
        status_path.unlink()

    traces: list[dict[str, Any]] = []
    gates: list[dict[str, Any]] = []
    rejected_passages: list[dict[str, Any]] = []
    all_evidence: dict[str, dict[str, Any]] = {}
    raw_extractions: list[dict[str, Any]] = []
    relations: list[dict[str, Any]] = []
    temporal_items: list[dict[str, Any]] = []
    identities: list[dict[str, Any]] = []
    assist_candidates: list[dict[str, Any]] = []
    extraction_usages: list[dict[str, Any]] = []
    latencies: list[float] = []
    counters: dict[str, Any] = collections.Counter()
    failed_people: list[dict[str, Any]] = []
    for row in selected_rows:
        fid = str(row.get("frontier_id"))
        trace, evidence = retrieve_person(row, profiles, punctuated, legacy)
        for ref, source in evidence.items():
            all_evidence[ref] = source
        gates.extend(trace.get("seed_identity_gate_decisions", []))
        rejected_passages.extend([{**dict(item), "frontier_id": fid, "wave": 1} for item in [*trace.get("rejected_by_temporal_gate", []), *trace.get("rejected_by_seed_identity_gate", [])]])
        packet = _model_packet(profiles[fid], trace)
        artifact_path = raw_dir / f"extraction-wave-1-{fid}-attempt-01.json"
        if artifact_path.is_file():
            artifact = read_json(artifact_path, {}) or {}
            call = {"success": bool(artifact.get("raw_response")), "response": artifact.get("raw_response"), "content": artifact.get("content", ""), "attempts": artifact.get("attempts", []), "failure_class": artifact.get("failure_class"), "reused": True}
        else:
            counters["extraction_calls"] += 1
            call = transport.call(story_id=fid, round_number=1, completion_kind="source_extraction", messages=[{"role": "system", "content": EXTRACTION_SYSTEM_PROMPT}, {"role": "user", "content": json.dumps(packet, ensure_ascii=False, sort_keys=True)}], max_retries=1)
            artifact = {"schema": 1, "stage": "hng2-live-raw-extraction", "run_id": run_id, "wave": 1, "frontier_id": fid, "model": MODEL, "prompt_version": PROMPT_VERSION, "model_input_hash": json_hash(packet), "retrieved_refs": trace.get("retrieved_refs", []), "opened_refs": trace.get("opened_refs", []), "raw_response": call.get("response"), "content": call.get("content", ""), "attempts": call.get("attempts", []), "failure_class": call.get("failure_class"), "transport_error": _redact(call.get("error")), "immutable": True, "canonical_write_back": False}
            if not artifact_path.exists():
                artifact_path.write_text(json.dumps(artifact, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        raw_extractions.append({"wave": 1, "frontier_id": fid, "path": str(artifact_path.relative_to(ROOT)), "success": bool(call.get("success")), "failure_class": call.get("failure_class")})
        if not call.get("success"):
            trace["status"] = "api_transport_failed"; trace["failure_class"] = call.get("failure_class"); failed_people.append({"frontier_id": fid, "status": "api_transport_failed", "failure_class": call.get("failure_class")}); traces.append(trace); continue
        for attempt in call.get("attempts", []):
            if attempt.get("failure_class") is None:
                latencies.append(float(attempt.get("elapsed_seconds") or 0))
        usage = (call.get("response") or {}).get("usage", {}) if isinstance(call.get("response"), Mapping) else {}
        if isinstance(usage, Mapping): extraction_usages.append(dict(usage))
        try:
            response_doc = _content_to_json(str(call.get("content") or ""))
            if not isinstance(response_doc.get("relation_candidates", []), list) or not isinstance(response_doc.get("temporal_candidates", []), list):
                raise ValueError("candidate arrays missing")
        except Exception as exc:
            trace["status"] = "protocol_failed"; trace["protocol_error"] = f"{type(exc).__name__}:{exc}"; failed_people.append({"frontier_id": fid, "status": "protocol_failed", "reason": str(exc)}); traces.append(trace); counters["protocol_failures"] += 1; continue
        projected = _project_extraction(row, trace, all_evidence, response_doc, catalog, profiles, contextual, hng0_edges, 1)
        trace["status"] = "completed"; trace["used_refs"] = projected["used_refs"]; trace["new_used_refs"] = projected["used_refs"]; trace["rejected_claims"] = projected["rejected"]; traces.append(trace)
        relations.extend(projected["relations"]); temporal_items.extend(projected["temporal_items"]); identities.extend(projected["identities"]); assist_candidates.extend(projected["identities"]); counters["evidence_validation_failures"] += sum(1 for row2 in projected["rejected"] if "evidence" in str(row2.get("reason")))
    # Residual identity assist is performed only after every Wave-1 extraction
    # has been deterministically projected.
    final_identities, assist_rows = _apply_identity_assist(assist_candidates, transport, profiles, catalog, hng0_edges, all_evidence, raw_dir, run_id, counters)
    identities = final_identities
    final_by_occ = {str(row.get("occurrence_id")): row for row in identities}
    relations = _merge_relations(relations, final_by_occ)
    wave1_ids = {str(row.get("person_id")) for row in selected_rows if row.get("person_id")} | {str(row.get("frontier_id")) for row in selected_rows if not row.get("person_id")}
    wave2_selection = _wave2_selection(relations, identities, catalog, wave1_ids)
    write_json(OUT / "wave-2-selection.json", wave2_selection)
    wave2_results: list[dict[str, Any]] = []
    wave2_relations: list[dict[str, Any]] = []
    wave2_temporal: list[dict[str, Any]] = []
    wave2_identities: list[dict[str, Any]] = []
    wave2_assist: list[dict[str, Any]] = []
    for row in wave2_selection.get("frontiers", []):
        fid = str(row.get("frontier_id")); profiles[fid] = _profile(row, catalog, provisional)
        trace, evidence = retrieve_person(row, profiles, punctuated, legacy)
        for ref, source in evidence.items(): all_evidence[ref] = source
        gates.extend(trace.get("seed_identity_gate_decisions", [])); rejected_passages.extend([{**dict(item), "frontier_id": fid, "wave": 2} for item in [*trace.get("rejected_by_temporal_gate", []), *trace.get("rejected_by_seed_identity_gate", [])]])
        packet = _model_packet(profiles[fid], trace)
        artifact_path = raw_dir / f"extraction-wave-2-{fid}-attempt-01.json"
        if artifact_path.is_file():
            artifact = read_json(artifact_path, {}) or {}; call = {"success": bool(artifact.get("raw_response")), "response": artifact.get("raw_response"), "content": artifact.get("content", ""), "attempts": artifact.get("attempts", []), "failure_class": artifact.get("failure_class"), "reused": True}
        else:
            counters["extraction_calls"] += 1
            call = transport.call(story_id=fid, round_number=2, completion_kind="source_extraction", messages=[{"role": "system", "content": EXTRACTION_SYSTEM_PROMPT}, {"role": "user", "content": json.dumps(packet, ensure_ascii=False, sort_keys=True)}], max_retries=1)
            artifact = {"schema": 1, "stage": "hng2-live-raw-extraction", "run_id": run_id, "wave": 2, "frontier_id": fid, "model": MODEL, "prompt_version": PROMPT_VERSION, "model_input_hash": json_hash(packet), "retrieved_refs": trace.get("retrieved_refs", []), "opened_refs": trace.get("opened_refs", []), "raw_response": call.get("response"), "content": call.get("content", ""), "attempts": call.get("attempts", []), "failure_class": call.get("failure_class"), "immutable": True, "canonical_write_back": False}
            if not artifact_path.exists():
                artifact_path.write_text(json.dumps(artifact, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        raw_extractions.append({"wave": 2, "frontier_id": fid, "path": str(artifact_path.relative_to(ROOT)), "success": bool(call.get("success")), "failure_class": call.get("failure_class")})
        if not call.get("success"):
            trace["status"] = "api_transport_failed"; trace["failure_class"] = call.get("failure_class"); wave2_results.append({"frontier_id": fid, "status": "api_transport_failed", "failure_class": call.get("failure_class")}); traces.append(trace); continue
        for attempt in call.get("attempts", []):
            if attempt.get("failure_class") is None: latencies.append(float(attempt.get("elapsed_seconds") or 0))
        usage = (call.get("response") or {}).get("usage", {}) if isinstance(call.get("response"), Mapping) else {}
        if isinstance(usage, Mapping): extraction_usages.append(dict(usage))
        try:
            response_doc = _content_to_json(str(call.get("content") or ""))
            projected = _project_extraction(row, trace, all_evidence, response_doc, catalog, profiles, contextual, hng0_edges, 2)
            trace["status"] = "completed"; trace["used_refs"] = projected["used_refs"]; trace["new_used_refs"] = projected["used_refs"]; trace["rejected_claims"] = projected["rejected"]; traces.append(trace)
            wave2_relations.extend(projected["relations"]); wave2_temporal.extend(projected["temporal_items"]); wave2_identities.extend(projected["identities"]); wave2_assist.extend(projected["identities"]); wave2_results.append({"frontier_id": fid, "status": "completed", "relation_count": len(projected["relations"]), "temporal_count": len(projected["temporal_items"])})
        except Exception as exc:
            trace["status"] = "protocol_failed"; trace["protocol_error"] = f"{type(exc).__name__}:{exc}"; traces.append(trace); wave2_results.append({"frontier_id": fid, "status": "protocol_failed", "reason": str(exc)}); counters["protocol_failures"] += 1
    if wave2_assist:
        wave2_final, wave2_assist_rows = _apply_identity_assist(wave2_assist, transport, profiles, catalog, hng0_edges, all_evidence, raw_dir, run_id, counters)
        identities.extend(wave2_final); assist_rows.extend(wave2_assist_rows)
        wave2_by_occ = {str(row.get("occurrence_id")): row for row in wave2_final}
        relations.extend(_merge_relations(wave2_relations, wave2_by_occ))
    consolidations = _consolidation(identities)
    audit = _audit(identities, [row for row in rejected_passages if row.get("reason") and "temporal" in str(row.get("reason"))], wave2_selection.get("frontiers", []), consolidations)
    write_json(OUT / "wave-1-results.json", {"schema": RUN_SCHEMA, "run_id": run_id, "wave": 1, "researched_count": len(selected_rows), "results": [row for row in raw_extractions if row.get("wave") == 1], "failed_people": [row for row in failed_people if row.get("frontier_id") in {str(x.get("frontier_id")) for x in selected_rows}], "canonical_write_back": False})
    write_json(OUT / "wave-2-results.json", {"schema": RUN_SCHEMA, "run_id": run_id, "wave": 2, "researched_count": len(wave2_results), "results": wave2_results, "wave_3_created": False, "canonical_write_back": False})
    write_json(OUT / "retrieval-trace.json", {"schema": RUN_SCHEMA, "stage": "hng2-live-retrieval", "run_id": run_id, "records": traces, "canonical_write_back": False})
    write_json(OUT / "temporal-gate-decisions.json", {"schema": RUN_SCHEMA, "stage": "hng2-live-temporal-gate", "run_id": run_id, "decisions": gates, "canonical_write_back": False})
    write_json(OUT / "rejected-passages.json", {"schema": RUN_SCHEMA, "stage": "hng2-live-rejected-passages", "run_id": run_id, "records": rejected_passages, "canonical_write_back": False})
    write_json(OUT / "identity-deterministic.json", {"schema": RUN_SCHEMA, "stage": "hng2-live-identity-deterministic", "run_id": run_id, "records": [row for row in identities if not row.get("assist_called")], "resolver_version": RESOLVER_VERSION, "canonical_write_back": False})
    write_json(OUT / "identity-llm-assist.json", {"schema": RUN_SCHEMA, "stage": "hng2-live-identity-llm-assist", "run_id": run_id, "eligible_cases": len(assist_rows), "calls": assist_rows, "model": MODEL, "prompt_version": IDENTITY_PROMPT_VERSION, "canonical_write_back": False})
    write_json(OUT / "identity-final.json", {"schema": RUN_SCHEMA, "stage": "hng2-live-identity-final", "run_id": run_id, "records": identities, "canonical_write_back": False})
    graph_rows = [{"occurrence_id": row.get("occurrence_id"), "support_edges": (row.get("graph_support") or {}).get("graph_support_edges", []), "excluded_circular_edges": (row.get("graph_support") or {}).get("excluded_circular_edges", [])} for row in identities if (row.get("graph_support") or {}).get("graph_support_edges") or (row.get("graph_support") or {}).get("excluded_circular_edges")]
    write_json(OUT / "identity-graph-support.json", {"schema": RUN_SCHEMA, "stage": "hng2-live-identity-graph-support", "run_id": run_id, "records": graph_rows, "canonical_write_back": False})
    write_json(OUT / "relations.json", {"schema": RUN_SCHEMA, "stage": "hng2-live-relations", "run_id": run_id, "relations": relations, "canonical_write_back": False})
    write_json(OUT / "temporal-items.json", {"schema": RUN_SCHEMA, "stage": "hng2-live-temporal-items", "run_id": run_id, "temporal_items": temporal_items + wave2_temporal, "canonical_write_back": False})
    provisional_out = sorted({str(row.get("provisional_neighbor_id")) for row in relations if row.get("provisional_neighbor_id")})
    write_json(OUT / "provisional-persons.json", {"schema": RUN_SCHEMA, "stage": "hng2-live-provisional-persons", "persons": [{"provisional_person_id": pid, "label": next((r.get("counterpart_surface") for r in relations if r.get("provisional_neighbor_id") == pid), pid), "frontier_state": "candidate_frontier", "canonical_write_back": False} for pid in provisional_out], "canonical_write_back": False})
    write_json(OUT / "consolidation-candidates.json", {"schema": RUN_SCHEMA, "stage": "hng2-live-consolidation-candidates", "candidates": consolidations, "canonical_write_back": False})
    write_json(OUT / "audit-sample.json", {"schema": RUN_SCHEMA, "stage": "hng2-live-audit-sample", "items": audit, "review_values": ["correct", "false_merge", "false_split", "bad_seed_match", "bad_temporal_rejection", "bad_llm_resolution", "uncertain", "not_reviewed"], "canonical_write_back": False})
    _write_review(relations, temporal_items + wave2_temporal, audit)
    source_forms = collections.Counter(str(row.get("source_form")) for row in all_evidence.values())
    opened_source_forms = collections.Counter(str(form) for trace in traces for form in (trace.get("source_form_by_ref") or {}).values())
    used_source_forms = collections.Counter(str((all_evidence.get(str(ref)) or {}).get("source_form")) for trace in traces for ref in trace.get("used_refs", []) if (all_evidence.get(str(ref)) or {}).get("source_form"))
    gate_counts = collections.Counter(str(row.get("temporal", {}).get("status", "unknown")) for row in gates)
    status_counts = collections.Counter(str(row.get("final_status")) for row in identities)
    transport_attempts = [attempt for row in preflight.get("attempts", []) for attempt in [row]]
    for artifact in raw_extractions:
        path = ROOT / artifact["path"]; doc = read_json(path, {}) or {}; transport_attempts.extend(doc.get("attempts", []))
    for row in assist_rows:
        transport_attempts.extend(row.get("attempts", []))
    usage = _usage_totals([*extraction_usages, *[row.get("api_usage", {}) for row in preflight.get("attempts", []) if isinstance(row, Mapping)]])
    successful = [float(x) for x in latencies if x >= 0]
    transport_failures = collections.Counter(str(row.get("failure_class")) for row in transport_attempts if row.get("failure_class"))
    metrics = {
        "schema": RUN_SCHEMA, "stage": "hng2-live-metrics", "run_id": run_id, "execution_status": "completed", "canonical_write_back": False,
        "wave_1_researched_persons": len(selected_rows), "wave_1_new_persons": len({str(row.get("provisional_neighbor_id") or row.get("person_b")) for row in relations if row.get("provisional_neighbor_id") or row.get("person_b") and str(row.get("person_b")) not in wave1_ids}),
        "wave_2_eligible_persons": len(wave2_selection.get("frontiers", [])), "wave_2_researched_persons": len(wave2_results), "wave_3_created": False,
        "new_relations": len(relations), "new_temporal_items": len(temporal_items) + len(wave2_temporal),
        "retrieval": {"searched": len(traces), "retrieved": sum(len(row.get("retrieved_refs", [])) for row in traces), "opened": sum(len(row.get("opened_refs", [])) for row in traces), "used": len(set(ref for row in traces for ref in row.get("used_refs", []))), "average_open_chars": round(sum(int(row.get("opened_chars") or 0) for row in traces) / len(traces), 2) if traces else 0, "source_form_distribution": dict(sorted(source_forms.items())), "opened_source_form_distribution": dict(sorted(opened_source_forms.items())), "used_source_form_distribution": dict(sorted(used_source_forms.items())), "punctuated_first": True, "fallback_count": sum(bool(row.get("fallback_used")) for row in traces)},
        "temporal_gate": {"compatible": int(gate_counts.get("compatible", 0)), "unknown": int(gate_counts.get("unknown", 0)), "conflict": int(gate_counts.get("conflict", 0)), "rejected_by_temporal_gate": len([row for row in rejected_passages if "temporal" in str(row.get("reason"))])},
        "identity": {"total_occurrences": len(identities), "deterministic_resolved": sum(not bool(row.get("assist_called")) and row.get("final_status") == "deterministic_resolved" for row in identities), "llm_assist_eligible": len(assist_rows), "llm_calls": int(counters.get("identity_assist_calls", 0)), "llm_resolved": int(counters.get("identity_llm_resolved", 0)), "llm_rejected": int(counters.get("identity_llm_rejected", 0)), "provisional": status_counts.get("provisional", 0), "ambiguous": status_counts.get("ambiguous", 0), "unresolved": status_counts.get("unresolved", 0)},
        "graph": {"graph_assisted_cases": sum(bool((row.get("graph_support") or {}).get("graph_support_edges")) for row in identities), "independently_supported_cases": sum(int((row.get("graph_support") or {}).get("independent_graph_support_count") or 0) for row in identities), "circular_supports_excluded": sum(len((row.get("graph_support") or {}).get("excluded_circular_edges", [])) for row in identities)},
        "model": {"provider": PROVIDER, "model": MODEL, "extraction_calls": int(counters.get("extraction_calls", 0)), "identity_assist_calls": int(counters.get("identity_assist_calls", 0)), **usage, "tokens_per_researched_person": round(usage.get("total_tokens", 0) / max(1, len(selected_rows) + len(wave2_results)), 2), "median_latency_seconds": statistics.median(successful) if successful else None, "max_latency_seconds": max(successful) if successful else None, "transport_request_count": len(transport_attempts), "transport_retry_count": sum(int(row.get("attempt") or 1) > 1 for row in transport_attempts), "transport_success_count": sum(not row.get("failure_class") for row in transport_attempts), "transport_failures": dict(sorted(transport_failures.items()))},
        "validation": {"protocol_failures": int(counters.get("protocol_failures", 0)), "evidence_validation_failures": int(counters.get("evidence_validation_failures", 0)), "failed_people": failed_people},
        "evaluation_answers": {"llm_resolved_residual_cases": bool(counters.get("identity_llm_resolved")), "llm_validation_exercised": bool(counters.get("identity_assist_calls")), "deterministic_validator_rejected_llm": bool(counters.get("identity_llm_rejected")), "real_temporal_conflicts": bool(gate_counts.get("conflict")), "graph_helped_without_circular_self_confirmation": any(bool((row.get("graph_support") or {}).get("graph_support_edges")) and not (row.get("graph_support") or {}).get("excluded_circular_edges") for row in identities), "wave_2_useful_evidence": any(row.get("status") == "completed" and (row.get("relation_count", 0) or row.get("temporal_count", 0)) for row in wave2_results), "temporal_zero_explanation": "no conflicting passages were retrieved" if not gate_counts.get("conflict") else None},
    }
    write_json(OUT / "metrics.json", metrics)
    write_json(OUT / "manifest.json", {"schema": RUN_SCHEMA, "stage": "hng2-live", "run_id": run_id, "resolver_version": RESOLVER_VERSION, "prompt_version": PROMPT_VERSION, "identity_prompt_version": IDENTITY_PROMPT_VERSION, "model": {"provider": PROVIDER, "name": MODEL}, "preflight": preflight, "selection_hash": json_hash(selection), "raw_api_root": str(raw_dir.relative_to(ROOT)), "wave_cap": 2, "one_hop_only": True, "canonical_write_back": False, "hng2_baseline_hashes": selection.get("source_hashes", {}), "outputs": ["live-selection.json", "wave-1-results.json", "wave-2-selection.json", "wave-2-results.json", "retrieval-trace.json", "temporal-gate-decisions.json", "rejected-passages.json", "identity-deterministic.json", "identity-llm-assist.json", "identity-final.json", "identity-graph-support.json", "relations.json", "temporal-items.json", "provisional-persons.json", "consolidation-candidates.json", "audit-sample.json", "metrics.json", "manifest.json"], "raw_extractions": raw_extractions})
    if not quiet:
        print(json.dumps({"status": "completed", "wave_1": len(selected_rows), "wave_2": len(wave2_results), "relations": len(relations), "temporal_items": len(temporal_items) + len(wave2_temporal), "identity_assist_calls": counters.get("identity_assist_calls", 0)}, ensure_ascii=False, sort_keys=True))
    return metrics


def main() -> int:
    parser = argparse.ArgumentParser(description="Run HNG2-L live hybrid resolver validation")
    parser.add_argument("--run-id", default=None)
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args()
    result = run_live(run_id=args.run_id, quiet=args.quiet)
    return 0 if result.get("execution_status") in {"completed", None} or result.get("status") == "live_network_unavailable" else 2


if __name__ == "__main__":
    raise SystemExit(main())
