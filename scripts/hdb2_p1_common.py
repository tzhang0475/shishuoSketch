#!/usr/bin/env python3
"""Shared deterministic infrastructure for the HDB2-P1 identity pilot.

This module is deliberately candidate-only.  It reads the frozen HDB1
projection, searches already registered local witnesses, and produces small
evidence windows.  It never writes canonical data and never asks a model to
choose an identity or plan a search.
"""

from __future__ import annotations

import collections
import hashlib
import json
import re
import unicodedata
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

import build_hng0_2 as hng02
import historical_entity_resolver as resolver

ROOT = Path(__file__).resolve().parents[1]
ANNOTATION = ROOT / "data/annotation"
DERIVED = ROOT / "data/derived"
GENERATED = ROOT / "data/generated/hdb2-p1"
MODEL = "deepseek-v4-flash"
RUN_VERSION = "hdb2-p1-v1"
PROMPT_VERSION = "hdb2-p1-evidence-atoms-v1"
ATOM_KINDS = {"identity_name", "kinship", "office", "temporal_activity", "location_origin", "person_mention", "other"}
CERTAINTIES = {"explicit", "probable", "unclear"}
SOURCE_WORKS = ("世說正文", "劉注", "箋疏", "晉書", "三國志", "資治通鑑")
IDENTITY_MARKERS = ("字", "名", "諱", "號", "号")
KINSHIP_MARKERS = ("父", "母", "子", "女", "兄", "弟", "叔", "舅", "妻", "婿", "婚", "嫁", "從")
OFFICE_MARKERS = ("辟", "拜", "除", "任", "授", "召", "領", "守", "刺史", "太守", "將軍", "尚書", "太尉", "太傅", "令", "掾")


def read_json(path: Path, default: Any = None) -> Any:
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else default


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def stable_hash(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def text_norm(value: Any) -> str:
    return resolver.matching_normalize(unicodedata.normalize("NFKC", str(value or "")))


def load_hdb1() -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    aggregate = read_json(DERIVED / "hdb1-cross-wave-candidate-historical-db.json", {}) or {}
    registry = list(aggregate.get("candidate_identity_registry", []))
    identity = list(aggregate.get("identity_observations", []))
    relations = list(aggregate.get("relation_observations", []))
    return aggregate, registry, identity, relations


def _temporal_rows() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for path in (ANNOTATION / "hdb1-temporal-candidates.json", ANNOTATION / "hdb1-wave2-temporal-candidates.json"):
        doc = read_json(path, {}) or {}
        rows.extend(dict(row) for row in doc.get("records", []) if isinstance(row, Mapping))
    return rows


def _person_ids_for_observations(observation_ids: set[str], identity: Sequence[Mapping[str, Any]]) -> list[str]:
    result = set()
    for row in identity:
        if str(row.get("identity_observation_id")) not in observation_ids:
            continue
        pid = str(row.get("resolved_person_id") or "")
        if pid:
            result.add(pid)
    return sorted(result)


def _related_rows(cluster: Mapping[str, Any], relations: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    obs = {str(x) for x in cluster.get("observation_ids", [])}
    candidates = {str(x) for x in cluster.get("candidate_ids", [])}
    tokens = {f"unresolved:{x}" for x in obs} | {f"provisional:{x}" for x in candidates}
    out = []
    for row in relations:
        if str(row.get("subject_ref") or "") in tokens or str(row.get("object_ref") or "") in tokens:
            out.append(dict(row))
    return sorted(out, key=lambda x: (str(x.get("story_id")), str(x.get("candidate_id"))))


def build_case(cluster: Mapping[str, Any], relations: Sequence[Mapping[str, Any]], identity: Sequence[Mapping[str, Any]], temporal: Sequence[Mapping[str, Any]], catalog: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    cluster_id = str(cluster.get("candidate_identity_id"))
    related = _related_rows(cluster, relations)
    story_ids = sorted({str(x) for x in cluster.get("story_ids", []) if x})
    blocked = [x for x in related if x.get("novelty") == "unresolved_endpoint"]
    blocked_kin = [x for x in blocked if x.get("relation_class") == "kinship"]
    blocked_mar = [x for x in blocked if x.get("relation_class") == "marriage"]
    blocked_rel = [x for x in blocked if x.get("relation_class") not in {"kinship", "marriage"}]
    neighbors = []
    for row in related:
        for endpoint in ("subject", "object"):
            if str(row.get(f"{endpoint}_ref") or "") not in {f"unresolved:{x}" for x in cluster.get("observation_ids", [])}:
                pid = str(row.get(f"{endpoint}_person_id") or "")
                if pid and pid in catalog:
                    neighbors.append({"person_id": pid, "canonical_name": catalog[pid].get("canonical_name"), "relation_surface": row.get("relation_surface"), "relation_class": row.get("relation_class"), "story_id": row.get("story_id"), "evidence_ref": row.get("evidence_ref")})
    neighbor_ids = sorted({str(x["person_id"]) for x in neighbors})
    story_temporal = [dict(x) for x in temporal if str(x.get("story_id")) in story_ids]
    office_hints = [dict(x) for x in related if x.get("relation_class") == "institutional" or x.get("office_title")]
    kin_hints = [dict(x) for x in related if x.get("relation_class") in {"kinship", "marriage"}]
    candidate_person_ids = _person_ids_for_observations({str(x) for x in cluster.get("observation_ids", [])}, identity)
    temporal_available = bool(story_temporal)
    office_available = bool(office_hints)
    score = (5 * len(blocked_mar) + 4 * len(blocked_kin + []) + 2 * len(blocked_rel) + 2 * len(story_ids) + len(neighbor_ids) + int(temporal_available) + int(office_available))
    case_material = {"cluster_id": cluster_id, "surfaces": cluster.get("observed_surfaces", []), "stories": story_ids}
    return {
        "case_id": f"hdb2-case-{stable_hash(case_material)[:20]}",
        "candidate_identity_id": cluster_id,
        "target_surfaces": sorted({str(x) for x in cluster.get("observed_surfaces", []) if x}),
        "observation_ids": sorted({str(x) for x in cluster.get("observation_ids", []) if x}),
        "story_ids": story_ids,
        "current_candidate_person_ids": candidate_person_ids,
        "blocked_relations": blocked_rel,
        "blocked_kinship": blocked_kin,
        "blocked_marriage": blocked_mar,
        "resolved_neighbors": sorted(neighbors, key=lambda x: (str(x.get("person_id")), str(x.get("story_id")), str(x.get("evidence_ref")))),
        "office_hints": office_hints,
        "kinship_hints": kin_hints,
        "story_temporal_constraints": story_temporal,
        "current_status": str(cluster.get("status") or "unresolved_surface_cluster"),
        "priority_score": score,
        "selection_key": stable_hash({"score": score, "case": case_material, "blocked": [x.get("candidate_id") for x in blocked]}),
    }


def build_selection() -> dict[str, Any]:
    aggregate, registry, identity, relations = load_hdb1()
    catalog = hng02.person_catalog()
    temporal = _temporal_rows()
    unresolved = [x for x in registry if x.get("status") == "unresolved_surface_cluster"]
    cases = [build_case(x, relations, identity, temporal, catalog) for x in unresolved]
    cases.sort(key=lambda x: (-int(x["priority_score"]), -len(x["story_ids"]), str(x["selection_key"]), str(x["case_id"])))
    selected = cases[:24]
    if len(selected) != 24:
        raise RuntimeError(f"hdb2_p1_requires_24_unresolved_cases:{len(selected)}")
    core = {
        "schema": "hdb2-p1-selection-v1",
        "run_version": RUN_VERSION,
        "algorithm_version": "HNG2-C.3/HNG2-V1-frozen",
        "model": MODEL,
        "temperature": 0,
        "selection_method": "deterministic structural priority over HDB1 unresolved identity registry",
        "frozen_before_live": True,
        "candidate_only": True,
        "canonical_write_back": False,
        "source_inputs": {
            "aggregate": "data/derived/hdb1-cross-wave-candidate-historical-db.json",
            "registry_status": "unresolved_surface_cluster",
            "registry_hash": stable_hash(registry),
            "relation_observation_hash": stable_hash(relations),
            "temporal_candidate_hash": stable_hash(temporal),
        },
        "selected_case_count": 24,
        "cases": selected,
        "selection_hash": None,
    }
    core["selection_hash"] = stable_hash({k: v for k, v in core.items() if k != "selection_hash"})
    return core


def freeze_selection(path: Path) -> dict[str, Any]:
    proposed = build_selection()
    if path.is_file():
        existing = read_json(path, {}) or {}
        if existing != proposed:
            raise RuntimeError("hdb2_p1_frozen_selection_changed")
        return existing
    write_json(path, proposed)
    return proposed


def _text_after_marker(path: Path) -> str:
    raw = path.read_text(encoding="utf-8")
    marker = "## Original source (exact)"
    if marker in raw:
        raw = raw.split(marker, 1)[1]
    return raw.strip()


def _unit(ref: str, work: str, layer: str, text: str, path: Path | None = None, locator: Mapping[str, Any] | None = None, source_form: str = "legacy_local", story_id: str | None = None) -> dict[str, Any] | None:
    text = str(text or "").strip()
    if not text:
        return None
    return {"ref": ref, "source_work": work, "source_layer": layer, "evidence_text": text, "source_path": str(path.relative_to(ROOT)) if path and path.is_file() else None, "source_sha256": file_hash(path) if path and path.is_file() else None, "locator": dict(locator or {}), "source_form": source_form, "story_id": story_id}


def build_source_index() -> list[dict[str, Any]]:
    units: list[dict[str, Any]] = []
    shishuo = read_json(DERIVED / "ds2-1a-shishuo-search-corpus.json", {}) or {}
    for row in shishuo.get("records", []):
        sid = str(row.get("story_id") or "")
        main = _unit(f"hdb2-shishuo-main-{sid}", "世說新語", "main_text", row.get("main_text", ""), ROOT / str(row.get("source_path")) if row.get("source_path") else None, {"story_id": sid, "chapter": row.get("chapter_heading")}, "punctuated_local", sid)
        if main: units.append(main)
        for ann in row.get("liu_annotations", []):
            aid = str(ann.get("annotation_id") or "annotation")
            item = _unit(f"hdb2-shishuo-liu-{sid}-{aid}", "劉注", "liu_annotation", ann.get("text", ""), ROOT / str(row.get("source_path")) if row.get("source_path") else None, {"story_id": sid, "annotation_id": aid}, "punctuated_local", sid)
            if item: units.append(item)
    # The repository has an already-built, local Yu Jiaxi Jianshu cache.  Use
    # its structured note blocks as a separate searchable witness when it is
    # present; no EPUB/PDF parsing or new acquisition is performed here.
    try:
        import s1_jianshu_common as jianshu  # type: ignore

        for row in jianshu.load_story_records():
            sid = str(row.get("story_id") or "")
            for block_index, block in enumerate(row.get("blocks", [])):
                block_type = str(block.get("block_type") or "")
                if block_type not in {"jianshu_note", "base_text"}:
                    continue
                work = "箋疏" if block_type == "jianshu_note" else "箋疏正文"
                item = _unit(
                    f"hdb2-jianshu-{sid}-{block_index:03d}",
                    work,
                    "jianshu_note" if block_type == "jianshu_note" else "base_text",
                    block.get("text", ""),
                    None,
                    {"story_id": sid, "block_id": block.get("block_id"), "block_type": block_type, "source_locator": block.get("source_locator", {})},
                    "punctuated_local",
                    sid,
                )
                if item:
                    item["source_sha256"] = block.get("text_sha256")
                    item["source_path"] = "sources/downloads/shishuo/ssjx-2016-epub-transcription/世说新语笺疏 -- (南朝宋)刘义庆 著、(南朝梁)刘孝标 注、余嘉锡 笺疏、周祖谟 余淑宜 整理 -- 2016 -- cj5_9602 -- 1d7f4607a0d0e81517e61e8a06373bb0 -- Anna’s Archive.epub"
                    units.append(item)
    except (ImportError, FileNotFoundError):
        pass
    index = read_json(ROOT / "data/jinshu-unit-index.json", {}) or {}
    for row in index.get("units", []):
        path = ROOT / str(row.get("file_path"))
        if not path.is_file(): continue
        text = _text_after_marker(path)
        item = _unit(f"hdb2-jinshu-{row.get('unit_id')}", "晉書", "biography" if row.get("category") == "liezhuan" else "historical_text", text, path, {"unit_id": row.get("unit_id"), "title": row.get("title"), "volume": row.get("volume")}, "legacy_local")
        if item: units.append(item)
    sgz = read_json(DERIVED / "sgz1-sanguozhi-complete-corpus.json", {}) or {}
    for row in sgz.get("records", []):
        path = ROOT / str(row.get("processed_path"))
        if not path.is_file(): continue
        item = _unit(f"hdb2-sgz-{row.get('global_juan')}-{row.get('title')}", "三國志", "biography", path.read_text(encoding="utf-8"), path, {"juan": row.get("global_juan"), "title": row.get("title")}, "punctuated_local")
        if item: units.append(item)
    ztj = read_json(DERIVED / "ztj0-processed-corpus.json", {}) or {}
    for row in (ztj.get("primary", {}) or {}).get("records", []):
        if row.get("kind") != "volume": continue
        path = ROOT / str(row.get("processed_path"))
        if not path.is_file(): continue
        doc = read_json(path, {}) or {}
        text = doc.get("source_text") if isinstance(doc, Mapping) else ""
        item = _unit(f"hdb2-ztj-{int(row.get('file_number') or 0):03d}", "資治通鑑", "chronicle", text, path, {"volume": row.get("juan_surface")}, "legacy_local")
        if item: units.append(item)
    return sorted(units, key=lambda x: (str(x.get("source_work")), str(x.get("ref"))))


def query_terms(case: Mapping[str, Any], catalog: Mapping[str, Mapping[str, Any]]) -> list[dict[str, str]]:
    terms: list[dict[str, str]] = []
    seen: set[str] = set()
    def add(term: str, category: str) -> None:
        term = " ".join(str(term or "").split())
        if not term or len(text_norm(term)) < 1 or term in seen: return
        seen.add(term); terms.append({"term": term, "category": category})
    for surface in case.get("target_surfaces", []):
        add(surface, "observed_surface")
        for marker in ("字", "名", "諱", "號"):
            add(f"{surface}{marker}", "name_identity_template")
    for pid in case.get("current_candidate_person_ids", []):
        person = catalog.get(str(pid), {})
        for form in [person.get("canonical_name"), *(person.get("forms") or [])]: add(str(form), "candidate_form")
    for neighbor in case.get("resolved_neighbors", []):
        name = str(neighbor.get("canonical_name") or "")
        for surface in case.get("target_surfaces", []):
            add(f"{surface} {name}", "neighbor_context")
    for clue in case.get("office_hints", []):
        office = str(clue.get("office_title") or clue.get("relation_surface") or "")
        for surface in case.get("target_surfaces", []): add(f"{surface} {office}", "office_context")
    for marker in ("父", "子", "兄", "弟"):
        for surface in case.get("target_surfaces", []): add(f"{surface}{marker}", "kinship_context")
    return terms


def _window(text: str, start: int, end: int, radius: int = 360) -> tuple[str, int, int]:
    lo = max(0, start - radius); hi = min(len(text), max(end, start + 1) + radius)
    return text[lo:hi], lo, hi


def search_case(case: Mapping[str, Any], units: Sequence[Mapping[str, Any]], catalog: Mapping[str, Mapping[str, Any]], *, used_refs: set[str] | None = None, max_passages: int = 4, max_chars: int = 2000) -> dict[str, Any]:
    used_refs = set(used_refs or set())
    terms = query_terms(case, catalog)
    target_norm = [text_norm(x) for x in case.get("target_surfaces", [])]
    neighbor_norm = [text_norm(x.get("canonical_name")) for x in case.get("resolved_neighbors", []) if x.get("canonical_name")]
    hits: list[dict[str, Any]] = []
    for unit in units:
        ref = str(unit.get("ref")); text = str(unit.get("evidence_text") or "")
        if ref in used_refs: continue
        norm = text_norm(text)
        local: list[tuple[int, dict[str, str]]] = []
        for query in terms:
            qn = text_norm(query["term"])
            pos = norm.find(qn)
            if pos >= 0: local.append((pos, query))
        if not local: continue
        pos, query = sorted(local, key=lambda x: (x[0], -len(text_norm(x[1]["term"]))))[0]
        # Norm and source text have only whitespace-fold differences in the
        # project corpora.  Find a conservative source position using the
        # literal query as a fallback.
        literal_pos = text.find(query["term"])
        if literal_pos < 0: literal_pos = max(0, min(len(text) - 1, pos))
        span, lo, hi = _window(text, literal_pos, literal_pos + len(query["term"]))
        score = 0
        score += 30 * sum(bool(text_norm(s) and text_norm(s) in norm) for s in case.get("target_surfaces", []))
        score += 200 * (1 if query["category"] == "name_identity_template" else 0)
        score += 80 * (1 if query["category"] == "candidate_form" else 0)
        score += 8 * sum(bool(x and x in norm) for x in neighbor_norm)
        score += 6 * sum(marker in span for marker in IDENTITY_MARKERS)
        score += 4 * sum(marker in span for marker in KINSHIP_MARKERS)
        score += 4 * sum(marker in span for marker in OFFICE_MARKERS)
        score += 3 * (1 if unit.get("source_layer") in {"biography", "liu_annotation"} else 0)
        hits.append({"ref": ref, "source_work": unit.get("source_work"), "source_layer": unit.get("source_layer"), "evidence_text": span, "source_window_start": lo, "source_window_end": hi, "source_path": unit.get("source_path"), "source_sha256": unit.get("source_sha256"), "locator": unit.get("locator", {}), "source_form": unit.get("source_form"), "query": query, "score": score, "story_id": unit.get("story_id")})
    hits.sort(key=lambda x: (-int(x.get("score") or 0), str(x.get("source_work")), str(x.get("ref"))))
    selected: list[dict[str, Any]] = []
    total = 0
    for hit in hits:
        if len(selected) >= max_passages: break
        text = str(hit.get("evidence_text") or "")
        if total + len(text) > max_chars and selected: continue
        selected.append(hit); total += len(text)
    return {"queries": terms, "hits": hits, "selected_passages": selected, "selected_count": len(selected), "selected_chars": total, "used_refs": sorted(used_refs)}


def evidence_map(passages: Sequence[Mapping[str, Any]]) -> dict[str, Mapping[str, Any]]:
    return {str(x.get("ref")): x for x in passages if x.get("ref")}


def source_work_for_ref(ref: str, passages: Sequence[Mapping[str, Any]]) -> str:
    return str((evidence_map(passages).get(str(ref)) or {}).get("source_work") or "unknown")


def source_window_text(passages: Sequence[Mapping[str, Any]], ref: str) -> str:
    return str((evidence_map(passages).get(str(ref)) or {}).get("evidence_text") or "")


def strict_atom_tool() -> dict[str, Any]:
    atom = {
        "type": "object",
        "properties": {
            "atom_id": {"type": "string", "pattern": "^a[0-9]+$", "description": "本次回答内部的局部断言编号，不是数据库 ID。"},
            "atom_kind": {"type": "string", "enum": sorted(ATOM_KINDS), "description": "原文明确相关信息的类别；只抽取与当前身份问题有关的证据。"},
            "subject_surface": {"type": "string", "description": "原文中的主体文字；必须逐字出现在 exact_span 中。"},
            "predicate_surface": {"type": "string", "description": "原文中的关系、身份、官职或亲属文字；必须逐字出现在 exact_span 中。"},
            "object_surface": {"type": "string", "description": "原文中的对象文字；必须逐字出现在 exact_span 中。"},
            "temporal_surface": {"type": "string", "description": "原文中的时间文字；没有则为空；不得改写。"},
            "evidence_ref": {"type": "string", "description": "只能复制系统提供的 source passage ref。"},
            "exact_span": {"type": "string", "description": "支持该 atom 的最短连续原文，必须原样出现在同一 passage。"},
            "certainty": {"type": "string", "enum": sorted(CERTAINTIES), "description": "原文是否明确表达该 atom，不是数据库最终真值。"},
        },
        "required": ["atom_id", "atom_kind", "subject_surface", "predicate_surface", "object_surface", "temporal_surface", "evidence_ref", "exact_span", "certainty"],
        "additionalProperties": False,
    }
    return {"type": "function", "function": {"name": "submit_hdb2_identity_atoms", "description": "提交由给定历史原文直接支持的身份相关 EvidenceAtoms；不得创建人物 ID。", "strict": True, "parameters": {"type": "object", "properties": {"atoms": {"type": "array", "maxItems": 8, "items": atom, "description": "最多八条与当前目标身份有关的原文证据原子。"}}, "required": ["atoms"], "additionalProperties": False}}}


def tool_choice() -> dict[str, Any]:
    return {"type": "function", "function": {"name": "submit_hdb2_identity_atoms"}}


SYSTEM_PROMPT = """只阅读系统提供的历史原文，抽取与当前目标身份有关的明确 EvidenceAtoms。保留原文中的姓名、字、官职、亲属词和时间文字；每条 atom 必须有同一 passage 中逐字连续的 exact_span。不得根据共现臆造关系，不得创建 Person ID、候选 ID 或判断数据库真值。信息不足时可以返回空 atoms；只抽取解决当前身份问题所需的最少证据。"""


def user_prompt(case: Mapping[str, Any], passages: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    return {"task": "read historical identity evidence", "target_surfaces": list(case.get("target_surfaces", [])), "source_passages": [{"ref": x.get("ref"), "work": x.get("source_work"), "layer": x.get("source_layer"), "evidence_text": x.get("evidence_text"), "locator": x.get("locator", {})} for x in passages]}


def validate_atoms(payload: Any, passages: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    if not isinstance(payload, Mapping) or not isinstance(payload.get("atoms"), list):
        return {"valid_atoms": [], "rejected_atoms": [{"reason": "atoms_missing_or_not_array", "item": payload}]}
    pmap = evidence_map(passages)
    valid: list[dict[str, Any]] = []; rejected: list[dict[str, Any]] = []; seen: set[str] = set()
    for item in payload["atoms"]:
        if not isinstance(item, Mapping): rejected.append({"reason": "atom_not_object", "item": item}); continue
        atom = dict(item); reason = None
        aid = str(atom.get("atom_id") or "")
        if not re.fullmatch(r"a[0-9]+", aid): reason = "invalid_atom_id"
        elif aid in seen: reason = "duplicate_atom_id"
        elif str(atom.get("atom_kind") or "") not in ATOM_KINDS: reason = "invalid_atom_kind"
        elif str(atom.get("certainty") or "") not in CERTAINTIES: reason = "invalid_certainty"
        elif str(atom.get("evidence_ref") or "") not in pmap: reason = "evidence_ref_missing"
        elif not str(atom.get("exact_span") or ""): reason = "exact_span_empty"
        elif str(atom.get("exact_span")) not in str(pmap.get(str(atom.get("evidence_ref")), {}).get("evidence_text") or ""): reason = "exact_span_not_in_evidence_text"
        else:
            span = str(atom.get("exact_span"))
            for field in ("subject_surface", "predicate_surface", "object_surface", "temporal_surface"):
                value = str(atom.get(field) or "")
                if value and value not in span:
                    reason = f"{field}_not_in_span"; break
        if reason:
            rejected.append({"reason": reason, "item": atom})
        else:
            seen.add(aid); valid.append(atom)
    return {"valid_atoms": valid, "rejected_atoms": rejected}


def candidate_matches(surface: str, catalog: Mapping[str, Mapping[str, Any]], index: Mapping[str, Sequence[str]]) -> list[str]:
    key = resolver.matching_normalize(surface)
    return sorted({str(x) for x in index.get(key, []) if str(x) in catalog}) if key else []
