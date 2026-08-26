#!/usr/bin/env python3
"""Run the HDB2-XE0 evidence-directed Story expansion pilot.

XE0 is intentionally an additive experiment.  It freezes the current HDB2
review queue, ranks already-registered but non-production Shishuo Stories,
and sends only the selected Story evidence through the frozen HNG2 read/fill
helpers.  It never changes HDB2-F decisions, canonical data, or the production
review route.

The command is split into explicit phases:

    --prepare  freeze baseline, selection, and target plan (no API)
    --live     run the frozen Person/Temporal read/fill calls
    --rebuild  rebuild the audit/projection from immutable live results

The default is ``--prepare`` so importing or testing this module cannot make
network calls.
"""

from __future__ import annotations

import argparse
import collections
import datetime as dt
import hashlib
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

import build_hng0_2 as hng02  # noqa: E402
import historical_context_algorithm as algorithm  # noqa: E402
import historical_entity_resolver as resolver  # noqa: E402
import run_hng2_fresh_validation as frozen  # noqa: E402
import hdb2_full_frontier_common as frontier_common  # noqa: E402


XE0_ROOT = ROOT / "data/generated/hdb2-xe0"
BASELINE_PATH = XE0_ROOT / "baseline.json"
SELECTION_PATH = ROOT / "data/annotation/hdb2-xe0-story-selection.json"
REVIEW_ROOT = XE0_ROOT / "review"
SITE_REVIEW_ROOT = ROOT / "site/public/generated/review/hdb2-xe0"
PRODUCTION_SITE = ROOT / "data/derived/sc1-site.json"
CORPUS_PATH = ROOT / "data/derived/ds2-1a-shishuo-search-corpus.json"
BASELINE_REVIEW_ROOT = ROOT / "site/public/generated/review/hdb2"
BASELINE_QUEUE_PATH = ROOT / "data/annotation/hdb2-f-review-queue.json"
CATALOG = hng02.person_catalog()
MODEL = "deepseek-v4-flash"
RUN_VERSION = "hdb2-xe0-v1"
PROMPT_VERSION = "HNG2-C.3/HNG2-V1-frozen"
SCANNER_SCOPE = "H0A historical registry + explicit date patterns"
TARGET_LIMIT_PER_STORY = 2
STORY_LIMIT = 24

TYPE_WEIGHT = {
    "candidate_person": 7,
    "compositional_kinship": 6,
    "office_or_title_holder": 6,
    "identity": 4,
}

OFFICE_MARKERS = ("辟", "拜", "除", "召", "任", "授", "太尉", "太傅", "將軍", "尚書", "司空", "僕射", "太守", "刺史", "尹", "令")
KINSHIP_MARKERS = ("父", "母", "子", "女", "兄", "弟", "妻", "婿", "婚", "嫁", "兒")
IDENTITY_MARKERS = ("字", "名", "諱", "號", "号")
PERSON_LIKE_KINDS = {"named_person", "abbreviated_name", "courtesy_name", "person_title", "person_office_title", "kinship_reference"}


def read_json(path: Path, default: Any = None) -> Any:
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else default


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def stable_hash(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _catalog_forms(person_id: str) -> list[str]:
    person = CATALOG.get(str(person_id), {})
    return [str(x) for x in [person.get("canonical_name"), *(person.get("forms") or [])] if x]


def _baseline_items() -> tuple[dict[str, Any], list[dict[str, Any]]]:
    index = read_json(BASELINE_REVIEW_ROOT / "index.json", {}) or {}
    items: list[dict[str, Any]] = []
    for row in index.get("items", []):
        path = BASELINE_REVIEW_ROOT / str(row.get("item_path") or "")
        item = read_json(path, {}) or {}
        if item:
            items.append(dict(item))
    items.sort(key=lambda row: str(row.get("review_id")))
    return index, items


def _baseline_fingerprint(index: Mapping[str, Any], items: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    item_hashes = [
        {"review_id": row.get("review_id"), "sha256": stable_hash(row)}
        for row in sorted(items, key=lambda x: str(x.get("review_id")))
    ]
    return {
        "index_hash": stable_hash(index),
        "item_hashes": item_hashes,
        "items_hash": stable_hash(item_hashes),
        "item_count": len(items),
        "counts_by_type": dict(sorted(collections.Counter(str(x.get("review_type")) for x in items).items())),
        "counts_by_priority": dict(sorted(collections.Counter(str(x.get("priority")) for x in items).items())),
    }


def freeze_baseline() -> dict[str, Any]:
    index, items = _baseline_items()
    fingerprint = _baseline_fingerprint(index, items)
    if fingerprint["item_count"] != 73:
        raise RuntimeError(f"hdb2_xe0_expected_73_review_items:{fingerprint['item_count']}")
    core = {
        "schema": "hdb2-xe0-baseline-v1",
        "run_version": RUN_VERSION,
        "source": "site/public/generated/review/hdb2/index.json",
        "queue_source": str(BASELINE_QUEUE_PATH.relative_to(ROOT)),
        "frozen_before_live": True,
        "candidate_only": True,
        "canonical_write_back": False,
        "baseline_review_items": fingerprint["item_count"],
        "fingerprint": fingerprint,
        "review_ids": sorted(str(x.get("review_id")) for x in items),
    }
    core["baseline_hash"] = stable_hash(core)
    if BASELINE_PATH.is_file():
        existing = read_json(BASELINE_PATH, {}) or {}
        if existing != core:
            raise RuntimeError("hdb2_xe0_baseline_changed")
        return existing
    write_json(BASELINE_PATH, core)
    return core


def _corpus_rows() -> list[dict[str, Any]]:
    document = read_json(CORPUS_PATH, {}) or {}
    rows: list[dict[str, Any]] = []
    for row in document.get("records", []):
        if not isinstance(row, Mapping):
            continue
        story_id = str(row.get("story_id") or "")
        if story_id:
            rows.append(dict(row))
    return rows


def _production_story_ids() -> set[str]:
    site = read_json(PRODUCTION_SITE, {}) or {}
    return {str(row.get("id")) for row in site.get("stories", []) if row.get("id")}


def _item_terms(item: Mapping[str, Any]) -> list[dict[str, Any]]:
    terms: dict[str, dict[str, Any]] = {}

    def add(value: Any, kind: str, strength: int) -> None:
        text = str(value or "").strip()
        if not text or len(text) < 2:
            return
        previous = terms.get(text)
        if previous is None or int(previous["strength"]) < strength:
            terms[text] = {"term": text, "kind": kind, "strength": strength}

    surface = str(item.get("target_surface") or "")
    add(surface, "target", 70 if len(surface) >= 3 else 42)
    proposed = item.get("proposed_identity") if isinstance(item.get("proposed_identity"), Mapping) else {}
    add(proposed.get("label"), "proposal", 180)
    for candidate in item.get("candidate_people", []):
        if isinstance(candidate, Mapping):
            add(candidate.get("display_name"), "candidate", 165)
            person_id = str(candidate.get("person_id") or "")
            for form in _catalog_forms(person_id):
                add(form, "catalogue_alias", 150)
    return sorted(terms.values(), key=lambda row: (-int(row["strength"]), -len(str(row["term"])), str(row["term"])))


def _story_texts(row: Mapping[str, Any]) -> tuple[str, str]:
    main = str(row.get("main_text") or "")
    annotation = "\n".join(str(item.get("text") or "") for item in row.get("liu_annotations", []) if isinstance(item, Mapping))
    return main, annotation


def _matched_item(item: Mapping[str, Any], main: str, annotation: str) -> dict[str, Any] | None:
    terms = _item_terms(item)
    matches: list[dict[str, Any]] = []
    for term in terms:
        value = str(term["term"])
        in_main = value in main
        in_annotation = value in annotation
        if not in_main and not in_annotation:
            continue
        locations = []
        if in_main:
            locations.append("main_text")
        if in_annotation:
            locations.append("liu_annotation")
        score = int(term["strength"]) + (30 if in_main else 10) + min(24, len(value) * 3)
        matches.append({"term": value, "kind": term["kind"], "locations": locations, "score": score})
    if not matches:
        return None
    matches.sort(key=lambda row: (-int(row["score"]), -len(str(row["term"])), str(row["term"])))
    # A one-character target alone is too broad to direct expansion.  It is
    # admitted only when a candidate/full-name/alias or proposal also occurs.
    strong = [row for row in matches if row["kind"] != "target"]
    surface = str(item.get("target_surface") or "")
    if len(surface) < 2 and not strong:
        return None
    impact = TYPE_WEIGHT.get(str(item.get("review_type")), 3)
    affected = item.get("affected_facts") if isinstance(item.get("affected_facts"), Mapping) else {}
    structural = 12 * len(affected.get("marriage", [])) + 10 * len(affected.get("kinship", [])) + 8 * len(affected.get("relations", [])) + 8 * len(affected.get("office", []))
    return {
        "review_id": item.get("review_id"),
        "story_id": item.get("story_id"),
        "target_surface": surface,
        "review_type": item.get("review_type"),
        "matched_terms": matches,
        "best_match_score": int(matches[0]["score"]),
        "impact_score": impact,
        "structural_score": structural,
        "selection_value": int(matches[0]["score"]) + impact * 8 + structural,
    }


def _story_score(row: Mapping[str, Any], matches: Sequence[Mapping[str, Any]]) -> int:
    main, annotation = _story_texts(row)
    top = sorted(matches, key=lambda x: (-int(x.get("selection_value") or 0), str(x.get("review_id"))))[:6]
    score = sum(min(260, int(x.get("selection_value") or 0)) for x in top)
    score += min(100, len(matches) * 14)
    score += sum(16 for marker in IDENTITY_MARKERS if marker in main or marker in annotation)
    score += sum(9 for marker in OFFICE_MARKERS if marker in main or marker in annotation)
    score += sum(6 for marker in KINSHIP_MARKERS if marker in main or marker in annotation)
    # Penalize very long packets slightly: the pilot values focused evidence,
    # not Stories that merely contain many unrelated names.
    score -= max(0, len(main) - 220) // 80
    return score


def _story_windows(story_id: str, *, target: str = "", lane: str = "person") -> list[dict[str, Any]]:
    windows = [dict(row) for row in frozen.c1._select_story_windows(story_id, target=target, lane=lane)]
    # The frozen selector is authoritative.  It normally includes the target
    # in the main window; retain the guard so an annotation-only target is not
    # silently sent without its source text.
    if target and not any(target in str(row.get("evidence_text") or "") for row in windows):
        all_windows = [dict(row) for row in frozen.c1._story_sections(story_id)]
        candidates = [row for row in all_windows if target in str(row.get("evidence_text") or "")]
        if candidates:
            candidate = candidates[0]
            if all(str(candidate.get("ref")) != str(row.get("ref")) for row in windows):
                windows = [candidate, *windows]
            windows = windows[:4]
    return windows


def _target_plan(selection_rows: Sequence[Mapping[str, Any]], items_by_id: Mapping[str, Mapping[str, Any]]) -> list[dict[str, Any]]:
    plan: list[dict[str, Any]] = []
    for story_row in selection_rows:
        story_id = str(story_row["story_id"])
        candidates: list[dict[str, Any]] = []
        for match in story_row.get("matched_review_items", []):
            item = items_by_id.get(str(match.get("review_id")))
            if not item:
                continue
            surface = str(item.get("target_surface") or "")
            windows = _story_windows(story_id, target=surface, lane="person")
            occurrence = next((row for row in windows if surface and surface in str(row.get("evidence_text") or "")), None)
            if not occurrence:
                continue
            text = str(occurrence.get("evidence_text") or "")
            offset = text.find(surface)
            candidates.append({
                "review_id": match.get("review_id"),
                "story_id": story_id,
                "target_surface": surface,
                "review_type": item.get("review_type"),
                "exact_span": surface,
                "source_ref": occurrence.get("ref"),
                "char_start": offset,
                "selection_value": match.get("selection_value"),
                "candidate_people": [
                    {"display_name": x.get("display_name"), "person_id": x.get("person_id"), "semantic_type": x.get("semantic_type")}
                    for x in item.get("candidate_people", []) if isinstance(x, Mapping)
                ],
            })
        candidates.sort(key=lambda row: (-int(row.get("selection_value") or 0), str(row.get("review_id")), int(row.get("char_start") or 0)))
        selected: list[dict[str, Any]] = []
        seen: set[tuple[str, str]] = set()
        for row in candidates:
            key = (str(row.get("review_id")), str(row.get("target_surface")))
            if key in seen:
                continue
            seen.add(key)
            selected.append(row)
            if len(selected) >= TARGET_LIMIT_PER_STORY:
                break
        for index, row in enumerate(selected, start=1):
            row = dict(row)
            row["target_id"] = f"xe0-person-{story_id}-{index:02d}-{stable_hash({'story': story_id, 'review': row.get('review_id'), 'surface': row.get('target_surface')})[:12]}"
            row["person_source_refs"] = [str(x.get("ref")) for x in _story_windows(story_id, target=str(row.get("target_surface") or ""), lane="person")]
            plan.append(row)
    return plan


def build_selection() -> dict[str, Any]:
    baseline = freeze_baseline()
    index, baseline_items = _baseline_items()
    items_by_id = {str(row.get("review_id")): row for row in baseline_items}
    production = _production_story_ids()
    story_rows: list[dict[str, Any]] = []
    for row in _corpus_rows():
        story_id = str(row.get("story_id"))
        if not story_id or story_id in production:
            continue
        main, annotation = _story_texts(row)
        matches = [matched for item in baseline_items if (matched := _matched_item(item, main, annotation)) is not None]
        if not matches:
            continue
        score = _story_score(row, matches)
        story_rows.append({
            "story_id": story_id,
            "chapter_id": row.get("chapter_id"),
            "entry_number": row.get("entry_number"),
            "source_refs": sorted({f"xe0-shishuo-{story_id}-main", *[f"xe0-shishuo-{story_id}-liu-{x.get('annotation_id')}" for x in row.get("liu_annotations", []) if isinstance(x, Mapping)]}),
            "matched_review_items": sorted(matches, key=lambda x: (-int(x.get("selection_value") or 0), str(x.get("review_id")))),
            "matched_review_count": len(matches),
            "story_score": score,
            "selection_key": stable_hash({"story_id": story_id, "score": score, "matches": [x.get("review_id") for x in matches]}),
        })
    story_rows.sort(key=lambda row: (-int(row["story_score"]), -int(row["matched_review_count"]), str(row["selection_key"]), str(row["story_id"])))
    selected = story_rows[:STORY_LIMIT]
    if not 20 <= len(selected) <= 30:
        raise RuntimeError(f"hdb2_xe0_story_selection_out_of_range:{len(selected)}")
    target_plan = _target_plan(selected, items_by_id)
    core = {
        "schema": "hdb2-xe0-story-selection-v1",
        "run_version": RUN_VERSION,
        "algorithm_version": PROMPT_VERSION,
        "model": MODEL,
        "frozen_before_live": True,
        "candidate_only": True,
        "canonical_write_back": False,
        "baseline_hash": baseline.get("baseline_hash"),
        "baseline_review_items": baseline.get("baseline_review_items"),
        "production_story_count": len(production),
        "corpus_story_count": len(_corpus_rows()),
        "outside_production_story_count": len([row for row in _corpus_rows() if str(row.get("story_id")) not in production]),
        "story_limit": STORY_LIMIT,
        "selected_story_count": len(selected),
        "stories": selected,
        "target_plan": target_plan,
        "target_count": len(target_plan),
        "selection_method": "deterministic frontier-term and structural-impact ranking; frozen HNG2 evidence selector",
        "no_new_retrieval": True,
        "no_search_plan": True,
    }
    core["selection_hash"] = stable_hash(core)
    if SELECTION_PATH.is_file():
        existing = read_json(SELECTION_PATH, {}) or {}
        if existing != core:
            raise RuntimeError("hdb2_xe0_selection_changed")
        return existing
    write_json(SELECTION_PATH, core)
    return core


def _case_for_target(target: Mapping[str, Any]) -> dict[str, Any]:
    candidates: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for row in target.get("candidate_people", []):
        if not isinstance(row, Mapping):
            continue
        person_id = str(row.get("person_id") or "") or None
        display_name = str(row.get("display_name") or "").strip()
        if person_id and person_id in CATALOG:
            display_name = str(CATALOG[person_id].get("canonical_name") or display_name)
            forms = _catalog_forms(person_id)
        else:
            forms = [display_name] if display_name else []
        key = (str(person_id or ""), resolver.matching_normalize(display_name))
        if not display_name or key in seen:
            continue
        seen.add(key)
        candidates.append({
            "candidate_key": f"c{len(candidates)}",
            "person_id": person_id,
            "canonical_name": display_name,
            "known_forms": forms,
        })
    return {
        "story_id": target.get("story_id"),
        "observation": {
            "surface": target.get("target_surface"),
            "exact_span": target.get("exact_span"),
            "source_work": "世說新語",
        },
        "seed": {},
        "candidates": candidates,
        "constraint_checks": [],
    }


def _minimal_windows(windows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "ref": row.get("ref"),
            "work": row.get("work"),
            "layer": row.get("layer"),
            "source_form": row.get("source_form"),
            "evidence_text": row.get("evidence_text"),
        }
        for row in windows
    ]


def _known_evidence(windows: Sequence[Mapping[str, Any]]) -> dict[str, dict[str, Any]]:
    return {str(row.get("ref")): dict(row) for row in windows if row.get("ref")}


def _run_person_target(target: Mapping[str, Any], raw_dir: Path, sequence: int, *, offline: bool = False) -> tuple[dict[str, Any], int]:
    story_id = str(target.get("story_id"))
    surface = str(target.get("target_surface") or "")
    windows = _story_windows(story_id, target=surface, lane="person")
    target_input = {"surface": surface, "source_work": "世說新語", "story_id": story_id}
    if offline:
        read_transport = {"classification": "offline_fixture", "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}}
        read_payload = frozen.c1._fixture_payload("person_read", target_input, windows)
    else:
        read_prompt = algorithm.person_read_prompt(target_input, windows)
        read_transport, read_payload = frozen.semantic_call(lane="person_read", unit_id=str(target["target_id"]), prompt=read_prompt, raw_dir=raw_dir, sequence=sequence)
        sequence += 1
    read_validation = algorithm.validate_person_atoms(read_payload, windows) if read_payload is not None else None
    fill_windows = [row for row in windows if str(row.get("ref")) in {str(atom.get("evidence_ref")) for atom in (read_validation or {}).get("valid_atoms", [])}]
    grounded = read_validation or {"valid_atoms": []}
    if offline:
        fill_transport = {"classification": "offline_fixture", "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}}
        fill_payload = frozen.c1._fixture_payload("person_fill", target_input, fill_windows)
    else:
        fill_prompt = algorithm.person_atom_fill_prompt(target_input, grounded, windows)
        fill_transport, fill_payload = frozen.semantic_call(lane="person_fill", unit_id=str(target["target_id"]), prompt=fill_prompt, raw_dir=raw_dir, sequence=sequence)
        sequence += 1
    fill_validation = algorithm.validate_person_fill(fill_payload, fill_windows) if fill_payload is not None else None
    case = _case_for_target(target)
    normalization = algorithm.normalize_person_fill(
        fill_validation or {}, case=case, windows=fill_windows, known_evidence=_known_evidence(windows)
    ) if fill_validation is not None else None
    return {
        "target": dict(target),
        "story_id": story_id,
        "evidence_windows": _minimal_windows(windows),
        "person_read": {"transport": read_transport, "payload": read_payload, "validation": read_validation},
        "person_fill": {"transport": fill_transport, "payload": fill_payload, "validation": fill_validation},
        "normalization": normalization,
        "candidate_only": True,
        "canonical_write_back": False,
    }, sequence


def _run_temporal_story(story: Mapping[str, Any], raw_dir: Path, sequence: int, *, offline: bool = False) -> tuple[dict[str, Any], int]:
    story_id = str(story.get("story_id"))
    windows = _story_windows(story_id, lane="temporal")
    story_input = {"story_id": story_id, "target_unit": "Story/scene"}
    hints = algorithm.scan_visible_temporal_anchors(windows)
    if offline:
        read_transport = {"classification": "offline_fixture", "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}}
        read_payload = {"observations": []}
    else:
        read_prompt = algorithm.temporal_read_prompt(story_input, windows, hints)
        read_transport, read_payload = frozen.semantic_call(lane="temporal_read", unit_id=f"xe0-temporal-{story_id}", prompt=read_prompt, raw_dir=raw_dir, sequence=sequence)
        sequence += 1
    read_validation = algorithm.validate_temporal_atoms(read_payload, windows) if read_payload is not None else None
    fill_windows = [row for row in windows if str(row.get("ref")) in {str(atom.get("evidence_ref")) for atom in (read_validation or {}).get("valid_atoms", [])}]
    grounded = read_validation or {"valid_atoms": []}
    if offline:
        fill_transport = {"classification": "offline_fixture", "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}}
        fill_payload = {"temporal_assertions": []}
    else:
        fill_prompt = algorithm.temporal_atom_fill_prompt(story_input, grounded, windows)
        fill_transport, fill_payload = frozen.semantic_call(lane="temporal_fill", unit_id=f"xe0-temporal-{story_id}", prompt=fill_prompt, raw_dir=raw_dir, sequence=sequence)
        sequence += 1
    fill_validation = algorithm.validate_temporal_fill(fill_payload, fill_windows) if fill_payload is not None else None
    normalization = algorithm.normalize_story_temporal(fill_validation or {}, story_id=story_id) if fill_validation is not None else None
    return {
        "story_id": story_id,
        "story": story_input,
        "evidence_windows": _minimal_windows(windows),
        "visible_temporal_surfaces": hints,
        "temporal_read": {"transport": read_transport, "payload": read_payload, "validation": read_validation},
        "temporal_fill": {"transport": fill_transport, "payload": fill_payload, "validation": fill_validation},
        "normalization": normalization,
        "candidate_only": True,
        "canonical_write_back": False,
    }, sequence


def _usage_from_transport(transport: Mapping[str, Any]) -> dict[str, int]:
    usage: dict[str, int] = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
    for attempt in transport.get("attempts", []) if isinstance(transport.get("attempts"), list) else []:
        for key in usage:
            usage[key] += int((attempt.get("usage") or {}).get(key) or 0)
    for key in usage:
        usage[key] = max(usage[key], int((transport.get("usage") or {}).get(key) or 0))
    return usage


def _all_transports(results: Sequence[Mapping[str, Any]]) -> list[Mapping[str, Any]]:
    out: list[Mapping[str, Any]] = []
    for row in results:
        for key in ("person_read", "person_fill", "temporal_read", "temporal_fill"):
            value = row.get(key)
            if isinstance(value, Mapping) and isinstance(value.get("transport"), Mapping):
                out.append(value["transport"])
    return out


def _safe_existing_entity(normalization: Mapping[str, Any] | None, target: Mapping[str, Any]) -> dict[str, Any] | None:
    if not isinstance(normalization, Mapping):
        return None
    surface = str(target.get("target_surface") or "")
    entities = [row for row in normalization.get("entities", []) if isinstance(row, Mapping) and str(row.get("surface") or "") == surface]
    entity = next((row for row in entities if row.get("resolved_person_id")), None)
    if not entity:
        return None
    pid = str(entity.get("resolved_person_id") or "")
    if pid not in CATALOG or str(entity.get("entity_kind") or "") not in PERSON_LIKE_KINDS:
        return None
    identity_relations = [
        row for row in normalization.get("relations", [])
        if str(row.get("relation_class") or "") == "identity_name"
        and (str(row.get("person_a") or "") == pid or str(row.get("person_b") or "") == pid)
    ]
    kind = str(entity.get("entity_kind") or "")
    if "title" in kind or "office" in kind or kind == "person_title":
        if not identity_relations:
            return None
    if not identity_relations:
        forms = set(_catalog_forms(pid))
        if surface not in forms:
            return None
    return {
        "person_id": pid,
        "canonical_name": CATALOG[pid].get("canonical_name"),
        "surface": surface,
        "identity_resolution_basis": entity.get("identity_resolution_basis"),
        "resolution_method": entity.get("resolution_method"),
        "entity_kind": kind,
        "identity_relations": identity_relations,
        "evidence_refs": sorted({str(row.get("evidence_ref")) for row in identity_relations if row.get("evidence_ref")} | {str(entity.get("evidence_ref"))} - {""}),
        "exact_spans": sorted({str(row.get("exact_span")) for row in identity_relations if row.get("exact_span")} | {str(entity.get("exact_span"))} - {""}),
    }


def _compatible_old_item(item: Mapping[str, Any], resolution: Mapping[str, Any]) -> bool:
    pid = str(resolution.get("person_id") or "")
    proposed = item.get("proposed_identity") if isinstance(item.get("proposed_identity"), Mapping) else {}
    if str(proposed.get("person_id") or "") == pid:
        return True
    return any(str(row.get("person_id") or "") == pid for row in item.get("candidate_people", []) if isinstance(row, Mapping))


def _new_review_type(entity: Mapping[str, Any], relation: Mapping[str, Any] | None = None) -> str:
    kind = str(entity.get("entity_kind") or "")
    if kind == "structural_kinship_expression" or (relation and str(relation.get("relation_class")) in {"kinship", "marriage"}):
        return "compositional_kinship"
    if "title" in kind or "office" in kind or (relation and str(relation.get("relation_class")) == "institutional"):
        return "office_or_title_holder"
    if entity.get("identity_status") == "resolved_new_candidate":
        return "candidate_person"
    return "identity"


def _new_review_item(result: Mapping[str, Any], entity: Mapping[str, Any], relation: Mapping[str, Any] | None = None) -> dict[str, Any]:
    target = result.get("target") if isinstance(result.get("target"), Mapping) else {}
    normalization = result.get("normalization") if isinstance(result.get("normalization"), Mapping) else {}
    evidence = []
    refs = {str(entity.get("evidence_ref") or "")}
    if relation:
        refs.add(str(relation.get("evidence_ref") or ""))
    for row in result.get("evidence_windows", []):
        if str(row.get("ref")) not in refs:
            continue
        evidence.append({"evidence_ref": row.get("ref"), "source_work": row.get("work"), "source_layer": row.get("layer"), "excerpt": str(row.get("evidence_text") or "")[:1800]})
    review_type = _new_review_type(entity, relation)
    structural = 0
    if relation:
        structural = 100 if str(relation.get("relation_class")) in {"kinship", "marriage"} else 55
    status = str(entity.get("identity_status") or "unresolved")
    review_id = f"hdb2-xe0-review-{stable_hash({'story': result.get('story_id'), 'surface': entity.get('surface'), 'entity': entity.get('entity_key'), 'relation': relation.get('relation_id') if relation else None})[:20]}"
    return {
        "schema": "hdb2-xe0-review-item-v1",
        "review_id": review_id,
        "priority": "P1" if status == "resolved_new_candidate" or structural >= 100 else ("P2" if structural else "P3"),
        "priority_score": 1000 if status == "resolved_new_candidate" else (900 if structural >= 100 else 600),
        "review_type": review_type,
        "occurrence_id": f"xe0-occ-{stable_hash({'story': result.get('story_id'), 'surface': entity.get('surface'), 'entity': entity.get('entity_key')})[:20]}",
        "story_id": result.get("story_id"),
        "target_surface": entity.get("surface"),
        "occurrence_type": entity.get("entity_kind"),
        "story_context": next((str(row.get("evidence_text") or "") for row in result.get("evidence_windows", []) if row.get("layer") == "main_text"), ""),
        "relevant_annotation_context": [str(row.get("evidence_text") or "") for row in result.get("evidence_windows", []) if row.get("layer") == "liu_annotation"],
        "proposed_identity": {
            "status": status,
            "label": entity.get("resolved_label") or entity.get("surface"),
            "person_id": entity.get("resolved_person_id"),
            "candidate_person_id": entity.get("candidate_person_id"),
            "candidate_key": entity.get("candidate_key"),
            "basis": entity.get("identity_resolution_basis"),
        },
        "candidate_people": [
            {"candidate_key": row.get("candidate_key"), "display_name": row.get("canonical_name"), "person_id": row.get("person_id"), "semantic_type": "person", "source": "xe0_frozen_normalization"}
            for row in normalization.get("candidates", []) if isinstance(row, Mapping)
        ],
        "selected_evidence": evidence,
        "support_families": sorted({str(x) for x in (entity.get("context_signals") or []) if x}),
        "affected_facts": {"relations": [dict(relation)] if relation else [], "kinship": [], "marriage": [], "office": [], "person_story": []},
        "current_state": {"status": status, "candidate_only": True, "canonical_write_back": False, "source": "hdb2-xe0"},
    }


def build_audit(selection: Mapping[str, Any], person_results: Sequence[Mapping[str, Any]], temporal_results: Sequence[Mapping[str, Any]], baseline: Mapping[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    _, baseline_items = _baseline_items()
    by_id = {str(row.get("review_id")): row for row in baseline_items}
    resolutions: dict[str, list[dict[str, Any]]] = collections.defaultdict(list)
    new_items: dict[str, dict[str, Any]] = {}
    for result in person_results:
        target = result.get("target") if isinstance(result.get("target"), Mapping) else {}
        resolution = _safe_existing_entity(result.get("normalization"), target)
        review_id = str(target.get("review_id") or "")
        if resolution and review_id in by_id and _compatible_old_item(by_id[review_id], resolution):
            resolutions[review_id].append({"story_id": result.get("story_id"), **resolution})
        normalization = result.get("normalization") if isinstance(result.get("normalization"), Mapping) else {}
        target_surface = str(target.get("target_surface") or "")
        for entity in normalization.get("entities", []):
            if not isinstance(entity, Mapping) or str(entity.get("surface") or "") == target_surface:
                continue
            if str(entity.get("identity_status") or "") not in {"resolved_new_candidate", "unresolved", "ambiguous"}:
                continue
            item = _new_review_item(result, entity)
            new_items[item["review_id"]] = item
        for relation in normalization.get("relations", []):
            if not isinstance(relation, Mapping) or str(relation.get("relation_class") or "") == "identity_name":
                continue
            # An explicit outside-Story relation is candidate data with a
            # human-review consequence, even when both endpoints normalize.
            entity = next((x for x in normalization.get("entities", []) if isinstance(x, Mapping) and x.get("entity_key") == relation.get("subject_entity_key")), {})
            item = _new_review_item(result, entity, relation)
            new_items[item["review_id"]] = item
    resolved_ids = sorted(resolutions)
    remaining = [row for row in baseline_items if str(row.get("review_id")) not in set(resolved_ids)]
    old_resolved_by_type = collections.Counter(str(by_id[x].get("review_type")) for x in resolved_ids)
    old_remaining_by_type = collections.Counter(str(row.get("review_type")) for row in remaining)
    new_by_type = collections.Counter(str(row.get("review_type")) for row in new_items.values())
    old_resolved = len(resolved_ids)
    new_count = len(new_items)
    audit = {
        "schema": "hdb2-xe0-before-after-audit-v1",
        "candidate_only": True,
        "canonical_write_back": False,
        "baseline_review_items": int(baseline.get("baseline_review_items") or 0),
        "old_review_items_resolved": old_resolved,
        "old_review_items_remaining": len(remaining),
        "new_review_items_created": new_count,
        "net_review_reduction": old_resolved - new_count,
        "by_type": {
            review_type: {
                "old_review_items_resolved": int(old_resolved_by_type.get(review_type, 0)),
                "old_review_items_remaining": int(old_remaining_by_type.get(review_type, 0)),
                "new_review_items_created": int(new_by_type.get(review_type, 0)),
            }
            for review_type in sorted(set(old_resolved_by_type) | set(old_remaining_by_type) | set(new_by_type) | set(TYPE_WEIGHT))
        },
        "resolved_items": [{"review_id": review_id, "evidence": resolutions[review_id]} for review_id in resolved_ids],
        "new_review_ids": sorted(new_items),
        "selection_hash": selection.get("selection_hash"),
        "recommendation": "CONTINUE_EXPANSION" if old_resolved - new_count > 8 or (old_resolved / max(1, int(baseline.get("baseline_review_items") or 1))) > 0.2 else "STOP_EXPANSION_PROCEED_TO_HUMAN_REVIEW",
    }
    projection_items = [dict(row) for row in remaining] + [new_items[key] for key in sorted(new_items)]
    projection_items.sort(key=lambda row: (-int(row.get("priority_score") or 0), str(row.get("story_id")), str(row.get("target_surface")), str(row.get("review_id"))))
    index = {
        "schema": "hdb2-xe0-review-index-v1",
        "candidate_only": True,
        "canonical_write_back": False,
        "baseline_review_items": audit["baseline_review_items"],
        "item_count": len(projection_items),
        "old_items_remaining": len(remaining),
        "new_items_created": new_count,
        "counts_by_type": dict(sorted(collections.Counter(str(row.get("review_type")) for row in projection_items).items())),
        "counts_by_priority": dict(sorted(collections.Counter(str(row.get("priority")) for row in projection_items).items())),
        "items": [
            {"review_id": row.get("review_id"), "priority": row.get("priority"), "review_type": row.get("review_type"), "story_id": row.get("story_id"), "target_surface": row.get("target_surface"), "status": (row.get("proposed_identity") or {}).get("status"), "item_path": f"items/{row.get('review_id')}.json"}
            for row in projection_items
        ],
    }
    return audit, {"index": index, "items": projection_items}


def write_projection(projection: Mapping[str, Any]) -> None:
    for root in (REVIEW_ROOT, SITE_REVIEW_ROOT):
        item_dir = root / "items"
        item_dir.mkdir(parents=True, exist_ok=True)
        for item in projection.get("items", []):
            write_json(item_dir / f"{item['review_id']}.json", item)
        write_json(root / "index.json", projection.get("index", {}))


def build_metrics(selection: Mapping[str, Any], person_results: Sequence[Mapping[str, Any]], temporal_results: Sequence[Mapping[str, Any]], audit: Mapping[str, Any], preflight: Mapping[str, Any] | None = None) -> dict[str, Any]:
    transports = _all_transports([*person_results, *temporal_results])
    usage = {key: sum(_usage_from_transport(row).get(key, 0) for row in transports) for key in ("prompt_tokens", "completion_tokens", "total_tokens")}
    latencies = [float(row.get("elapsed_seconds") or 0) for row in transports if row.get("elapsed_seconds") is not None]
    classifications = collections.Counter(str(row.get("classification") or "unknown") for row in transports)
    person_entities = [entity for result in person_results for entity in ((result.get("normalization") or {}).get("entities", []) if isinstance(result.get("normalization"), Mapping) else [])]
    person_relations = [relation for result in person_results for relation in ((result.get("normalization") or {}).get("relations", []) if isinstance(result.get("normalization"), Mapping) else [])]
    temporal_atoms = [atom for result in temporal_results for atom in ((result.get("temporal_read") or {}).get("validation") or {}).get("valid_atoms", [])]
    temporal_assertions = [item for result in temporal_results for item in ((result.get("temporal_fill") or {}).get("validation") or {}).get("valid_temporal_assertions", [])]
    return {
        "schema": "hdb2-xe0-metrics-v1",
        "candidate_only": True,
        "canonical_write_back": False,
        "stories_added": selection.get("selected_story_count"),
        "target_count": selection.get("target_count"),
        "baseline_review_items": audit.get("baseline_review_items"),
        "old_review_items_resolved": audit.get("old_review_items_resolved"),
        "old_review_items_remaining": audit.get("old_review_items_remaining"),
        "new_review_items_created": audit.get("new_review_items_created"),
        "net_review_reduction": audit.get("net_review_reduction"),
        "by_type": audit.get("by_type"),
        "semantic_calls": len(transports),
        "person_calls": 2 * len(person_results),
        "temporal_calls": 2 * len(temporal_results),
        "evidence_rescue_calls": 0,
        "evidence_rescue_rounds": 0,
        "note": "The selected Story windows supplied direct local evidence; no separate HDB2-P1 rescue round was launched.",
        "retries": sum(max(0, len(row.get("attempts", [])) - 1) for row in transports),
        "provider_failures": int(classifications.get("provider_request_failure", 0)),
        "parse_failures": int(classifications.get("response_parse_failure", 0)),
        "truncations": int(classifications.get("response_truncated", 0)),
        "transport_classifications": dict(sorted(classifications.items())),
        "prompt_tokens": usage["prompt_tokens"],
        "completion_tokens": usage["completion_tokens"],
        "total_tokens": usage["total_tokens"],
        "median_latency": statistics.median(latencies) if latencies else 0,
        "max_latency": max(latencies) if latencies else 0,
        "valid_person_atoms": sum(len(((row.get("person_read") or {}).get("validation") or {}).get("valid_atoms", [])) for row in person_results),
        "rejected_person_atoms": sum(len(((row.get("person_read") or {}).get("validation") or {}).get("rejected_atoms", [])) for row in person_results),
        "valid_person_entities": len(person_entities),
        "valid_relation_observations": len(person_relations),
        "valid_temporal_atoms": len(temporal_atoms),
        "valid_temporal_assertions": len(temporal_assertions),
        "old_review_items_resolved_by_type": {key: value["old_review_items_resolved"] for key, value in (audit.get("by_type") or {}).items()},
        "new_review_items_by_type": {key: value["new_review_items_created"] for key, value in (audit.get("by_type") or {}).items()},
        "preflight": dict(preflight or {"status": "not_run"}),
        "scanner_scope": SCANNER_SCOPE,
    }


def _protected_hashes() -> dict[str, str]:
    paths = [
        ROOT / "data/annotation/hdb2-f-occurrence-decisions.json",
        ROOT / "data/derived/hdb2-f-relation-projection.json",
        ROOT / "data/derived/hdb2-f-kinship-projection.json",
        ROOT / "data/derived/hdb2-f-marriage-projection.json",
        ROOT / "data/derived/hdb2-f-office-projection.json",
        ROOT / "data/derived/hdb2-f-person-knowledge.json",
        ROOT / "site/public/generated/review/hdb2/index.json",
    ]
    return {str(path.relative_to(ROOT)): file_hash(path) for path in paths if path.is_file()}


def prepare() -> dict[str, Any]:
    baseline = freeze_baseline()
    selection = build_selection()
    result = {"baseline": baseline, "selection": selection}
    write_json(XE0_ROOT / "prepare-report.json", result)
    return result


def run_live(run_id: str, *, offline: bool = False) -> Path:
    prepared = prepare()
    selection = prepared["selection"]
    run_dir = XE0_ROOT / "live" / run_id
    if run_dir.exists():
        raise RuntimeError(f"hdb2_xe0_run_exists:{run_dir}")
    raw_dir = run_dir / "raw-api"
    raw_dir.mkdir(parents=True, exist_ok=False)
    before = _protected_hashes()
    person_results: list[dict[str, Any]] = []
    temporal_results: list[dict[str, Any]] = []
    sequence = 1
    for target in selection.get("target_plan", []):
        result, sequence = _run_person_target(target, raw_dir, sequence, offline=offline)
        person_results.append(result)
    for story in selection.get("stories", []):
        result, sequence = _run_temporal_story(story, raw_dir, sequence, offline=offline)
        temporal_results.append(result)
    audit, projection = build_audit(selection, person_results, temporal_results, prepared["baseline"])
    metrics = build_metrics(selection, person_results, temporal_results, audit)
    after = _protected_hashes()
    if before != after:
        raise RuntimeError("hdb2_xe0_protected_hdb2_artifact_changed")
    write_json(run_dir / "manifest.json", {
        "schema": "hdb2-xe0-live-manifest-v1",
        "run_id": run_id,
        "run_version": RUN_VERSION,
        "algorithm_version": PROMPT_VERSION,
        "model": MODEL,
        "frozen_selection_hash": selection.get("selection_hash"),
        "baseline_hash": prepared["baseline"].get("baseline_hash"),
        "candidate_only": True,
        "canonical_write_back": False,
        "offline_fixture": offline,
        "protected_hashes_before": before,
        "protected_hashes_after": after,
        "sequence_count": sequence - 1,
        "created_at": utc_now(),
    })
    write_json(run_dir / "person-results.json", {"schema": "hdb2-xe0-person-results-v1", "records": person_results, "candidate_only": True, "canonical_write_back": False})
    write_json(run_dir / "temporal-results.json", {"schema": "hdb2-xe0-temporal-results-v1", "records": temporal_results, "candidate_only": True, "canonical_write_back": False})
    write_json(run_dir / "audit.json", audit)
    write_json(run_dir / "review-projection.json", projection)
    write_json(run_dir / "metrics.json", metrics)
    write_projection(projection)
    return run_dir


def rebuild(run_id: str) -> Path:
    run_dir = XE0_ROOT / "live" / run_id
    if not run_dir.is_dir():
        raise RuntimeError(f"hdb2_xe0_missing_run:{run_id}")
    prepared = prepare()
    manifest = read_json(run_dir / "manifest.json", {}) or {}
    if manifest.get("frozen_selection_hash") != prepared["selection"].get("selection_hash"):
        raise RuntimeError("hdb2_xe0_selection_hash_mismatch")
    person = list((read_json(run_dir / "person-results.json", {}) or {}).get("records", []))
    temporal = list((read_json(run_dir / "temporal-results.json", {}) or {}).get("records", []))
    audit, projection = build_audit(prepared["selection"], person, temporal, prepared["baseline"])
    metrics = build_metrics(prepared["selection"], person, temporal, audit)
    write_json(run_dir / "audit.json", audit)
    write_json(run_dir / "review-projection.json", projection)
    write_json(run_dir / "metrics.json", metrics)
    write_projection(projection)
    return run_dir


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--prepare", action="store_true", help="freeze baseline and selection without API calls")
    mode.add_argument("--live", action="store_true", help="run frozen semantic calls")
    mode.add_argument("--rebuild", action="store_true", help="rebuild audit/projection from an existing run")
    parser.add_argument("--run-id", default=None)
    parser.add_argument("--offline-fixture", action="store_true", help="exercise the pipeline without API calls")
    args = parser.parse_args()
    if args.live:
        run_id = args.run_id or dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-HDB2-XE0"
        print(run_live(run_id, offline=args.offline_fixture))
        return 0
    if args.rebuild:
        if not args.run_id:
            raise SystemExit("--rebuild requires --run-id")
        print(rebuild(args.run_id))
        return 0
    print(json.dumps(prepare(), ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
