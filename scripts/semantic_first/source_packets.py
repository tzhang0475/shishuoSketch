"""L0 deterministic Story/source packet construction."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from .common import ROOT, file_hash, read_json, stable_hash, text

CORPUS_PATH = ROOT / "data/derived/ds2-1a-shishuo-search-corpus.json"
PRODUCTION_PATH = ROOT / "data/derived/ux2-story-index.json"
WAVE_A_PATH = ROOT / "data/annotation/hge1-wave-a-selection.json"
WAVE_B_PATH = ROOT / "data/annotation/hge1-wave-b-selection.json"

# All but one known regression Story already belongs to the frozen 187-Story
# production/growth universe.  The remaining Story is carried as an explicit
# regression control, without changing the HGE1 cumulative scope.
REQUIRED_REGRESSION_STORY_IDS = {
    "04-wenxue-023",
    "09-pinzao-088", "09-pinzao-018", "06-yaliang-041", "02-yanyu-086",
    "34-pilou-001", "02-yanyu-046", "05-fangzheng-028", "05-fangzheng-011",
    "23-rendan-049", "10-guizhen-016", "08-shangyu-020", "01-dexing-028",
    "09-pinzao-008", "33-youhui-007", "08-shangyu-043", "05-fangzheng-037",
    "02-yanyu-054", "05-fangzheng-041", "25-paidiao-026", "05-fangzheng-053",
    "09-pinzao-040", "06-yaliang-033",
}


def corpus_index() -> dict[str, dict[str, Any]]:
    document = read_json(CORPUS_PATH, {}) or {}
    return {
        text(row.get("story_id")): dict(row)
        for row in document.get("records", []) or []
        if isinstance(row, Mapping) and text(row.get("story_id"))
    }


def production_story_ids() -> list[str]:
    document = read_json(PRODUCTION_PATH, {}) or {}
    return sorted({
        text(row.get("story_id"))
        for row in document.get("records", []) or []
        if isinstance(row, Mapping) and text(row.get("story_id"))
    })


def selected_story_ids(path: Path) -> list[str]:
    document = read_json(path, {}) or {}
    return sorted({text(value) for value in document.get("story_ids", []) or [] if text(value)})


def validation_universe() -> dict[str, Any]:
    production = production_story_ids()
    wave_a = selected_story_ids(WAVE_A_PATH)
    wave_b = selected_story_ids(WAVE_B_PATH)
    current_story_ids = sorted(set(production) | set(wave_a) | set(wave_b))
    story_ids = sorted(set(current_story_ids) | REQUIRED_REGRESSION_STORY_IDS)
    source_hashes = {
        str(path.relative_to(ROOT)): file_hash(path)
        for path in (CORPUS_PATH, PRODUCTION_PATH, WAVE_A_PATH, WAVE_B_PATH)
    }
    core = {
        "schema": "sfh1-validation-universe-v1",
        "production_story_ids": production,
        "wave_a_story_ids": wave_a,
        "wave_b_story_ids": wave_b,
        "story_ids": story_ids,
        "current_story_ids": current_story_ids,
        "current_story_count": len(current_story_ids),
        "regression_story_ids": sorted(REQUIRED_REGRESSION_STORY_IDS),
        "extra_regression_story_ids": sorted(REQUIRED_REGRESSION_STORY_IDS - set(current_story_ids)),
        "production_story_count": len(production),
        "wave_a_story_count": len(wave_a),
        "wave_b_story_count": len(wave_b),
        "story_count": len(story_ids),
        "source_hashes": source_hashes,
        "candidate_only": True,
        "canonical_write_back": False,
    }
    core["universe_hash"] = stable_hash(core)
    return core


def _evidence_rows(story: Mapping[str, Any]) -> list[dict[str, Any]]:
    story_id = text(story.get("story_id"))
    rows: list[dict[str, Any]] = []
    main = text(story.get("main_text"))
    if main:
        rows.append({
            "evidence_id": f"sfh1-ev-{story_id}-main",
            "story_id": story_id,
            "source_layer": "main_text",
            "source_ref": story.get("source_path"),
            "text": main,
            "source_start": 0,
            "source_end": len(main),
            "text_hash": stable_hash(main),
        })
    for annotation in story.get("liu_annotations", []) or []:
        if not isinstance(annotation, Mapping):
            continue
        value = text(annotation.get("text"))
        if not value:
            continue
        annotation_id = text(annotation.get("annotation_id")) or f"annotation-{len(rows):03d}"
        rows.append({
            "evidence_id": f"sfh1-ev-{story_id}-liu-{annotation_id}",
            "story_id": story_id,
            "source_layer": "liu_annotation",
            "source_ref": (annotation.get("source_locator") or {}).get("source_path") if isinstance(annotation.get("source_locator"), Mapping) else story.get("source_path"),
            "annotation_id": annotation_id,
            "text": value,
            "source_start": 0,
            "source_end": len(value),
            "text_hash": stable_hash(value),
        })
    return rows


def build_story_packets(universe: Mapping[str, Any] | None = None) -> dict[str, Any]:
    universe = dict(universe or validation_universe())
    corpus = corpus_index()
    packets: list[dict[str, Any]] = []
    for story_id in universe.get("story_ids", []) or []:
        story = corpus.get(text(story_id))
        if not story:
            continue
        evidence = _evidence_rows(story)
        packets.append({
            "packet_id": f"sfh1-story-{story_id}",
            "story_id": story_id,
            "chapter_id": story.get("chapter_id"),
            "chapter_heading": story.get("chapter_heading"),
            "publication_scope": story.get("publication_scope"),
            "evidence": evidence,
            "source_path": story.get("source_path"),
            "source_sha256": story.get("source_sha256"),
            "source_provenance": story.get("source_provenance"),
            "packet_hash": stable_hash({"story_id": story_id, "evidence": evidence}),
            "candidate_only": True,
            "canonical_write_back": False,
        })
    return {
        "schema": "sfh1-historical-reading-packets-v1",
        "universe_hash": universe.get("universe_hash"),
        "story_count": len(packets),
        "packets": packets,
        "candidate_only": True,
        "canonical_write_back": False,
    }


def evidence_index(packet: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        text(row.get("evidence_id")): dict(row)
        for row in packet.get("evidence", []) or []
        if isinstance(row, Mapping) and text(row.get("evidence_id"))
    }
