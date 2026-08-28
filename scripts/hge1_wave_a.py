#!/usr/bin/env python3
"""HGE1-WA: a bounded, candidate-only Story-network growth wave.

This module owns only deterministic selection, packet construction, replayable
HNG2 calls, and candidate projection.  It does not rebuild or write any
canonical Person, Relation, H0A, or H0B artifact.  The source corpus contains
research-only Stories as well as published Stories; this wave deliberately
uses the former and records the boundary in its immutable selection.
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
from typing import Any, Iterable, Mapping, Sequence

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import build_hng0_2 as hng02  # noqa: E402
import historical_context_algorithm as algorithm  # noqa: E402
import hng2_schema_controller as controller  # noqa: E402
import hda1_identity_audit as hda1  # noqa: E402
from smoke_deepseek import call_deepseek  # noqa: E402


ANNOTATION = ROOT / "data/annotation"
DERIVED = ROOT / "data/derived"
GENERATED = ROOT / "data/generated/hge1"
MODEL = "deepseek-v4-flash"
RUN_VERSION = "hge1-wave-a-v1"
PROMPT_VERSION = "hng2-c3-frozen-wave-a-v1"
SELECTION_PATH = ANNOTATION / "hge1-wave-a-selection.json"
TARGET_SELECTION_PATH = ANNOTATION / "hge1-wave-a-target-selection.json"
STORY_PATTERN = re.compile(r"\b\d{2}-[a-z]+-\d{3}\b")
RELATION_MARKERS = ("詣", "詣", "語", "謂", "問", "見", "與", "同", "從", "為", "爲", "辟", "拜", "除", "召", "父", "子", "兄", "弟", "妻", "嫁", "婚")
TEMPORAL_MARKERS = ("年", "中", "初", "末", "永嘉", "太康", "咸和", "正始", "永和", "武帝", "明帝")
GENERIC_NAME_TOKENS = set("其之是也者而以於于為爲不有無與同曰云謂問見人子女父兄弟主公君帝時年中初末故既乃然此彼" )
# These are lexical cues used only to choose a compact production target from
# an untouched Story.  They are not identity evidence and never enter a
# semantic prompt as an answer.  The source corpus is unsegmented, so a
# bounded suffix list avoids making a verb or particle part of a candidate
# Person surface (for example 魏武嘗過 -> 魏武).
PERSON_SURFACE_SUFFIXES = (
    "太丘", "法師", "中軍", "奉倩", "元方", "元禮", "泰初", "宣子",
    "嘉賓", "安道", "仲堪", "玄度", "太守", "將軍", "丞相", "主簿",
    "家奴", "家婢", "玠",
)
PERSON_SURFACE_TAILS = (
    "家奴婢", "家奴", "家婢", "好鶴", "嘗過", "被廢", "從豫", "與許",
    "詣陳", "與", "伐", "論", "常", "遭", "父", "子", "中", "就", "得",
    "云", "曰", "行", "入", "至", "過", "被", "止", "為", "爲", "者",
    "也", "矣", "之", "其", "於", "以", "而", "乃", "時", "初", "末",
    "有", "無", "謂", "問", "見", "不", "若", "如", "將", "能", "可", "令",
    "使", "取", "重", "大", "小", "聽", "讀", "成", "自", "反", "看", "語",
    "言", "處", "與", "從",
)


def read_json(path: Path, default: Any = None) -> Any:
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else default


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def stable_hash(value: Any) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def text_norm(value: Any) -> str:
    return hda1._text(value).replace(" ", "").replace("\n", "")


def corpus_records() -> list[dict[str, Any]]:
    document = read_json(DERIVED / "ds2-1a-shishuo-search-corpus.json", {}) or {}
    return [dict(row) for row in document.get("records", []) if isinstance(row, Mapping) and hda1._text(row.get("story_id"))]


def corpus_index() -> dict[str, dict[str, Any]]:
    return {hda1._text(row.get("story_id")): row for row in corpus_records()}


def production_story_ids() -> set[str]:
    document = read_json(DERIVED / "ux2-story-index.json", {}) or {}
    rows = document.get("records", []) if isinstance(document, Mapping) else []
    return {hda1._text(row.get("story_id")) for row in rows if isinstance(row, Mapping) and hda1._text(row.get("story_id"))}


def _collect_ids(value: Any, found: set[str]) -> None:
    if isinstance(value, Mapping):
        for key, item in value.items():
            # Avoid treating evidence text or source paths as a selection.
            if key in {"story_id", "story_ids", "story", "stories", "cases", "records", "selected_story_ids", "expansion_story_ids", "gold_story_ids", "withheld_story_ids"}:
                _collect_ids(item, found)
            elif isinstance(item, (Mapping, list)):
                _collect_ids(item, found)
    elif isinstance(value, list):
        for item in value:
            _collect_ids(item, found)
    elif isinstance(value, str) and STORY_PATTERN.fullmatch(value.strip()):
        found.add(value.strip())


def _prior_artifact_paths() -> list[Path]:
    """Return selection/result artifacts, excluding complete source/ranking indexes.

    Ranking files and source corpora describe the possible universe rather
    than Stories actually used by an experiment.  Including them would make
    every research-only Story falsely ineligible.  The persisted selection
    and result artifacts are the auditable experiment boundary.
    """
    paths: set[Path] = set()
    for root in (ANNOTATION, ROOT / "data/generated", DERIVED, ROOT / "tests", ROOT / "docs"):
        if not root.exists():
            continue
        for path in root.rglob("*.json"):
            name = path.name.lower()
            rel = path.relative_to(ROOT).as_posix().lower()
            relevant = any(token in name or token in rel for token in ("hng", "hdb", "psl", "xe0", "lj0", "irr", "expansion-wave", "person-expansion-wave", "story-scene-contexts", "w3-person", "w4-person"))
            if not relevant:
                continue
            excluded_universe = any(token in name for token in ("search-corpus", "punctuation", "ranking", "rescue-search", "retrieval-trace", "source-index"))
            if excluded_universe:
                continue
            paths.add(path)
    return sorted(paths)


def prior_story_ids() -> tuple[set[str], list[dict[str, Any]]]:
    found: set[str] = set()
    evidence: list[dict[str, Any]] = []
    for path in _prior_artifact_paths():
        try:
            value = read_json(path)
            before = set(found)
            _collect_ids(value, found)
            if found != before:
                evidence.append({"path": path.relative_to(ROOT).as_posix(), "sha256": file_hash(path), "story_count": len(found - before), "story_ids": sorted(found - before)})
        except (OSError, ValueError, UnicodeError):
            continue
    # The old HNG/HDB selection files occasionally contain a flat story ID
    # array under a non-standard key.  Scan only file names that are already
    # explicitly experiment artifacts, never the source corpus itself.
    for path in _prior_artifact_paths():
        if path in {ROOT / x["path"] for x in evidence}:
            continue
        try:
            raw = path.read_text(encoding="utf-8")
        except OSError:
            continue
        matches = set(STORY_PATTERN.findall(raw))
        delta = matches - found
        if delta:
            found.update(delta)
            evidence.append({"path": path.relative_to(ROOT).as_posix(), "sha256": file_hash(path), "story_count": len(delta), "story_ids": sorted(delta), "method": "bounded_artifact_text_scan"})
    return found, sorted(evidence, key=lambda row: row["path"])


def exclusion_snapshot() -> dict[str, Any]:
    ids, evidence = prior_story_ids()
    return {"story_ids": sorted(ids), "story_count": len(ids), "evidence": evidence, "hash": stable_hash({"story_ids": sorted(ids), "evidence": evidence})}


def _people_and_forms() -> tuple[dict[str, dict[str, Any]], dict[str, set[str]]]:
    people_doc = read_json(ROOT / "data/people.json", {}) or {}
    people = {hda1._text(row.get("person_id")): dict(row) for row in people_doc.get("people", []) or [] if hda1._text(row.get("person_id"))}
    forms: dict[str, set[str]] = collections.defaultdict(set)
    for pid, row in people.items():
        name = hda1._text(row.get("canonical_name"))
        if name:
            forms[name].add(pid)
    aliases = read_json(ROOT / "data/aliases.json", {}) or {}
    for alias in aliases.get("aliases", []) or []:
        if not isinstance(alias, Mapping):
            continue
        status = hda1._text(alias.get("status"))
        pids = {hda1._text(x) for x in alias.get("resolved_person_ids", []) or [] if hda1._text(x) in people}
        if status not in {"resolved", "context_dependent", "contextual"} or len(pids) != 1:
            continue
        surface = hda1._text(alias.get("surface"))
        if surface and len(surface) >= 2:
            forms[surface].update(pids)
    return people, {surface: set(pids) for surface, pids in forms.items()}


def _unknown_name_signals(text: str, known_forms: Mapping[str, set[str]]) -> int:
    known = set(known_forms)
    count = 0
    for match in re.finditer(r"[\u3400-\u9fff]{2,4}", text):
        value = match.group(0)
        if value in known or all(char in GENERIC_NAME_TOKENS for char in value):
            continue
        if any(marker in value for marker in ("太守", "將軍", "丞相", "尚書", "太傅", "司空", "僕射")):
            continue
        count += 1
    return min(count, 20)


def story_features(
    row: Mapping[str, Any],
    known_forms: Mapping[str, set[str]],
    corpus_rows: Sequence[Mapping[str, Any]] | None = None,
    unresolved_surfaces: Sequence[str] | None = None,
) -> dict[str, Any]:
    sid = hda1._text(row.get("story_id"))
    main = hda1._text(row.get("main_text"))
    search = hda1._text(row.get("search_text")) or main
    annotation_text = "\n".join(hda1._text(x.get("text")) for x in row.get("liu_annotations", []) or [] if isinstance(x, Mapping))
    combined = main + "\n" + annotation_text
    known_hits: list[dict[str, Any]] = []
    for surface, pids in sorted(known_forms.items(), key=lambda item: (-len(item[0]), item[0])):
        pos = combined.find(surface)
        if pos < 0:
            continue
        known_hits.append({"surface": surface, "person_ids": sorted(pids), "position": pos})
    if unresolved_surfaces is None:
        unresolved_doc = read_json(DERIVED / "hdb1-cross-wave-candidate-historical-db.json", {}) or {}
        unresolved_surfaces = sorted({hda1._text(x.get("surface")) for x in unresolved_doc.get("identity_observations", []) or [] if hda1._text(x.get("identity_status")) in {"unresolved", "ambiguous"} and len(hda1._text(x.get("surface"))) >= 1})
    unresolved_hits = [surface for surface in unresolved_surfaces if surface and surface in combined]
    relation_signal = sum(combined.count(marker) for marker in RELATION_MARKERS)
    temporal_signal = sum(combined.count(marker) for marker in TEMPORAL_MARKERS)
    source_rows = corpus_rows if corpus_rows is not None else corpus_records()
    chapters = [x for x in source_rows if hda1._text(x.get("chapter_id")) == hda1._text(row.get("chapter_id"))]
    return {
        "story_id": sid,
        "chapter_id": hda1._text(row.get("chapter_id")),
        "chapter_heading": row.get("chapter_heading"),
        "main_char_count": len(main),
        "annotation_char_count": len(annotation_text),
        "known_person_hits": known_hits[:30],
        "known_person_count": len({pid for hit in known_hits for pid in hit["person_ids"]}),
        "unresolved_surface_hits": unresolved_hits[:30],
        "unresolved_surface_count": len(unresolved_hits),
        "relation_marker_count": relation_signal,
        "temporal_marker_count": temporal_signal,
        "unknown_name_signal": _unknown_name_signals(search, known_forms),
        "chapter_story_count": len(chapters),
        "source_path": row.get("source_path"),
        "source_sha256": row.get("source_sha256"),
    }


def _rank_key(feature: Mapping[str, Any], channel: str) -> tuple[Any, ...]:
    if channel == "graph_guided_frontier_rich":
        score = 10 * int(feature.get("known_person_count") or 0) + 6 * int(feature.get("unresolved_surface_count") or 0) + 2 * int(feature.get("relation_marker_count") or 0) + int(feature.get("temporal_marker_count") or 0)
    elif channel == "new_person_rich":
        score = 8 * int(feature.get("unknown_name_signal") or 0) + 2 * int(feature.get("annotation_char_count") or 0) // 100
    elif channel == "relation_rich":
        score = 8 * int(feature.get("relation_marker_count") or 0) + 4 * int(feature.get("known_person_count") or 0) + int(feature.get("unresolved_surface_count") or 0)
    elif channel == "underrepresented_chapter":
        score = 1000 // max(1, int(feature.get("chapter_story_count") or 1)) + int(feature.get("unknown_name_signal") or 0)
    elif channel == "peripheral_low_connectivity":
        score = max(0, 12 - int(feature.get("known_person_count") or 0)) + int(feature.get("unknown_name_signal") or 0) - int(feature.get("relation_marker_count") or 0) // 3
    else:
        score = 0
    return (-score, stable_hash({"channel": channel, "story_id": feature.get("story_id")} ), hda1._text(feature.get("story_id")))


def build_selection() -> dict[str, Any]:
    corpus = corpus_index()
    production = production_story_ids()
    exclusion = exclusion_snapshot()
    _, known_forms = _people_and_forms()
    eligible_ids = sorted(set(corpus) - production - set(exclusion["story_ids"]))
    all_corpus_rows = list(corpus.values())
    unresolved_doc = read_json(DERIVED / "hdb1-cross-wave-candidate-historical-db.json", {}) or {}
    unresolved_surfaces = sorted({hda1._text(x.get("surface")) for x in unresolved_doc.get("identity_observations", []) or [] if hda1._text(x.get("identity_status")) in {"unresolved", "ambiguous"} and len(hda1._text(x.get("surface"))) >= 1})
    features = {
        sid: story_features(corpus[sid], known_forms, all_corpus_rows, unresolved_surfaces)
        for sid in eligible_ids
        if hda1._text(corpus[sid].get("publication_scope")) != "published"
    }
    channels = [("graph_guided_frontier_rich", 4), ("new_person_rich", 4), ("relation_rich", 4), ("underrepresented_chapter", 3), ("peripheral_low_connectivity", 3), ("random_control", 2)]
    selected: list[dict[str, Any]] = []
    used: set[str] = set()
    chapter_used: set[str] = set()
    for channel, quota in channels:
        candidates = [feature for sid, feature in features.items() if sid not in used]
        if channel == "underrepresented_chapter":
            candidates.sort(key=lambda f: (hda1._text(f.get("chapter_id")) in chapter_used, *_rank_key(f, channel)))
        elif channel == "peripheral_low_connectivity":
            candidates.sort(key=lambda f: (_rank_key(f, channel), -int(f.get("main_char_count") or 0)))
        else:
            candidates.sort(key=lambda f: _rank_key(f, channel))
        for feature in candidates[:quota]:
            sid = hda1._text(feature.get("story_id"))
            used.add(sid)
            chapter_used.add(hda1._text(feature.get("chapter_id")))
            selected.append({
                "story_id": sid,
                "selection_channel": channel,
                "selection_key": stable_hash({"story_id": sid, "channel": channel, "feature": feature}),
                "selection_basis": {key: feature.get(key) for key in ("known_person_count", "unresolved_surface_count", "unknown_name_signal", "relation_marker_count", "temporal_marker_count", "chapter_story_count")},
                "chapter_id": feature.get("chapter_id"),
                "chapter_heading": feature.get("chapter_heading"),
                "known_participants_before": [],
                "production_visible": False,
                "source_refs": [f"hge1-shishuo-main-{sid}"] + [f"hge1-shishuo-liu-{sid}-{a.get('annotation_id')}" for a in corpus[sid].get("liu_annotations", [])[:3] if isinstance(a, Mapping)],
                "source_hash": feature.get("source_sha256"),
            })
    selected.sort(key=lambda row: (hda1._text(row.get("selection_channel")), hda1._text(row.get("selection_key")), hda1._text(row.get("story_id"))))
    story_ids = [hda1._text(row.get("story_id")) for row in selected]
    core = {
        "schema": "hge1-wave-a-selection-v1",
        "wave_id": "HGE1-WA",
        "run_version": RUN_VERSION,
        "algorithm_version": "HNG2-C.3/HDB2-P2T-frozen-frontier-v1",
        "model": MODEL,
        "temperature": 0,
        "story_count": len(selected),
        "story_ids": story_ids,
        "records": selected,
        "stratum_targets": {channel: quota for channel, quota in channels},
        "stratum_actual": dict(collections.Counter(row["selection_channel"] for row in selected)),
        "production_scope_story_count": len(production),
        "prior_hng2_story_count": len(exclusion["story_ids"]),
        "prior_hng2_exclusion_hash": exclusion["hash"],
        "prior_hng2_exclusion_evidence": exclusion["evidence"],
        "overlap_with_production": sorted(set(story_ids) & production),
        "overlap_with_prior_hng2": sorted(set(story_ids) & set(exclusion["story_ids"])),
        "frozen_before_live": True,
        "candidate_only": True,
        "canonical_write_back": False,
        "selection_method": "deterministic stratified research-only Story selection; no model output",
        "selection_hash": None,
    }
    core["selection_hash"] = stable_hash({key: value for key, value in core.items() if key != "selection_hash"})
    return core


def freeze_selection(path: Path = SELECTION_PATH) -> dict[str, Any]:
    proposed = build_selection()
    if path.is_file():
        existing = read_json(path, {}) or {}
        if existing != proposed:
            raise RuntimeError("hge1_wave_a_selection_changed")
        return existing
    write_json(path, proposed)
    return proposed


def _compact(text: str, surface: str, radius: int = 500) -> str:
    if not text:
        return ""
    pos = text.find(surface) if surface else -1
    if pos < 0:
        return text[: radius * 2]
    return text[max(0, pos - radius): min(len(text), pos + len(surface) + radius)]


def build_windows(story: Mapping[str, Any], surface: str = "") -> list[dict[str, Any]]:
    sid = hda1._text(story.get("story_id"))
    main = hda1._text(story.get("main_text"))
    windows: list[dict[str, Any]] = []
    if main:
        windows.append({"ref": f"hge1-shishuo-main-{sid}", "work": "世說正文", "layer": "main_text", "source_form": "registered_local", "evidence_text": _compact(main, surface), "story_id": sid})
    for annotation in story.get("liu_annotations", []) or []:
        if not isinstance(annotation, Mapping):
            continue
        text = hda1._text(annotation.get("text"))
        if not text or (surface and surface not in text):
            continue
        aid = hda1._text(annotation.get("annotation_id"))
        windows.append({"ref": f"hge1-shishuo-liu-{sid}-{aid}", "work": "劉注", "layer": "liu_annotation", "source_form": "registered_local", "evidence_text": _compact(text, surface, 420), "story_id": sid})
    return windows[:4]


def _trim_target_surface(value: str) -> str:
    """Trim an unsegmented text chunk to a source-visible person surface.

    This is target selection only.  It intentionally does not assert that
    the resulting surface denotes a Person; READ/FILL and downstream review
    retain that responsibility.  The bounded list prevents common prose
    tails from being frozen into candidate names.
    """
    value = hda1._text(value).strip()
    if not value:
        return ""
    # First cut at an internal prose tail.  A fallback window may contain
    # several clauses (the corpus has no token boundaries), so looking only
    # at the final character would preserve text such as 支公好鶴住剡東.
    internal_tails = sorted(PERSON_SURFACE_TAILS, key=len, reverse=True)
    for tail in internal_tails:
        pos = value.find(tail, 2)
        if pos >= 2:
            value = value[:pos]
            break
    for _ in range(3):
        changed = False
        for tail in sorted(PERSON_SURFACE_TAILS, key=len, reverse=True):
            if value.endswith(tail) and len(value) - len(tail) >= 2:
                value = value[: -len(tail)]
                changed = True
                break
        if not changed:
            break
    # 家奴/家婢 is a structural phrase about a household rather than a
    # person's name.  Retain the named anchor when it is visibly present.
    for marker in ("家奴婢", "家奴", "家婢"):
        if marker in value and value.index(marker) >= 2:
            value = value[: value.index(marker)]
            break
    return value


def _target_is_useful(surface: str) -> bool:
    if len(surface) < 2 or surface in GENERIC_NAME_TOKENS:
        return False
    if all(char in GENERIC_NAME_TOKENS for char in surface):
        return False
    if surface in {"賔客", "宾客", "諸人", "時人", "有人", "家奴", "家婢"}:
        return False
    return True


def _surface_marker_hits(main: str) -> list[tuple[int, str]]:
    hits: list[tuple[int, str]] = []
    prefix_noise = GENERIC_NAME_TOKENS | set(RELATION_MARKERS) | set("咨於於其")
    for suffix in PERSON_SURFACE_SUFFIXES:
        # One- or two-character surname/prefix is the bounded historical
        # naming shape needed here.  A three-character prefix greedily pulled
        # conjunctions and neighboring people into the target surface.
        pattern = re.compile(rf"(?P<prefix>[\u3400-\u9fff]{{1,2}}){re.escape(suffix)}")
        for match in pattern.finditer(main):
            surface = match.group(0)
            prefix = hda1._text(match.group("prefix"))
            while prefix and prefix[0] in prefix_noise:
                prefix = prefix[1:]
            if not prefix:
                continue
            surface = prefix + suffix
            position = match.start() + len(match.group("prefix")) - len(prefix)
            if suffix in {"家奴", "家婢"} and suffix in surface:
                surface = surface[: surface.index(suffix)]
            if _target_is_useful(surface):
                hits.append((position, surface))
    return hits


def _fallback_surface_hits(main: str) -> list[tuple[int, str]]:
    hits: list[tuple[int, str]] = []
    for match in re.finditer(r"[\u3400-\u9fff]{2,8}", main):
        surface = _trim_target_surface(match.group(0))
        if _target_is_useful(surface):
            hits.append((match.start(), surface))
    return hits


def _target_rows(story: Mapping[str, Any], known_forms: Mapping[str, set[str]], people: Mapping[str, Mapping[str, Any]]) -> list[dict[str, Any]]:
    main = hda1._text(story.get("main_text"))
    sid = hda1._text(story.get("story_id"))
    hits: list[tuple[int, int, str, set[str]]] = []
    seen: set[tuple[int, str]] = set()
    # Catalogue forms have priority, but only exact visible forms are used.
    for surface, pids in known_forms.items():
        pos = main.find(surface)
        if pos >= 0:
            hits.append((pos, -len(surface), surface, set(pids)))
            seen.add((pos, surface))
    # When the Story is outside the production catalogue, use deterministic
    # morphology (太丘/法師/中軍/...) to select the name-sized source span.
    # This remains a lexical target choice, not a resolution.
    for pos, raw_surface in _surface_marker_hits(main):
        surface = raw_surface
        if (pos, surface) not in seen:
            hits.append((pos, -len(surface), surface, set()))
            seen.add((pos, surface))
    if not hits:
        for pos, raw_surface in _fallback_surface_hits(main):
            surface = raw_surface
            if (pos, surface) not in seen:
                hits.append((pos, -len(surface), surface, set()))
                seen.add((pos, surface))
    hits.sort(key=lambda row: (row[0], row[1], row[2]))
    chosen: list[tuple[int, str, set[str]]] = []
    if hits:
        first = hits[0]
        chosen.append((first[0], first[2], first[3]))
        # A secondary target is allowed only when the primary was a known
        # catalogue form.  Untouched research Stories otherwise get one
        # restrained target; selecting a neighboring phrase as a second
        # target would turn prose fragments into spurious candidates.
        if first[3]:
            for pos, _, surface, pids in hits[1:]:
                if surface == first[2] or (pids and pids == first[3]):
                    continue
                between = main[max(0, first[0]): pos + len(surface)]
                if any(marker in between for marker in RELATION_MARKERS):
                    chosen.append((pos, surface, pids))
                    break
    targets: list[dict[str, Any]] = []
    for index, (pos, surface, pids) in enumerate(chosen[:2], 1):
        pid = sorted(pids)[0] if len(pids) == 1 else None
        entity_kind = "named_person" if len(surface) >= 3 and (not pid or surface == hda1._text(people.get(pid, {}).get("canonical_name"))) else "courtesy_name"
        targets.append({
            "target_id": f"hge1-target-{sid}-p{index}",
            "surface": surface,
            "exact_span": surface,
            "source_ref": f"hge1-shishuo-main-{sid}",
            "reference_form": "full_name" if entity_kind == "named_person" else "courtesy",
            "entity_kind": entity_kind,
            "known_existing_person_id": pid,
            "selection_position": pos,
            "category": "main_text_person_surface" if pid else "candidate_person_surface",
        })
    return targets


def build_target_selection(selection: Mapping[str, Any]) -> dict[str, Any]:
    """Freeze the deterministic Person-target choice separately from Stories.

    The Story selection is the experimental sampling frame.  Target selection
    is another deterministic input to the live run, so it receives its own
    immutable snapshot rather than being recomputed after responses exist.
    """
    corpus = corpus_index()
    people, known_forms = _people_and_forms()
    records: list[dict[str, Any]] = []
    for record in selection.get("records", []) or []:
        sid = hda1._text(record.get("story_id"))
        story = corpus.get(sid, {})
        records.append({"story_id": sid, "targets": _target_rows(story, known_forms, people)})
    document = {
        "schema": "hge1-wave-a-target-selection-v1",
        "wave_id": "HGE1-WA",
        "selection_hash": selection.get("selection_hash"),
        "records": sorted(records, key=lambda row: row["story_id"]),
        "target_count": sum(len(row["targets"]) for row in records),
        "candidate_only": True,
        "canonical_write_back": False,
        "frozen_before_live": True,
        "target_selection_hash": None,
    }
    document["target_selection_hash"] = stable_hash({key: value for key, value in document.items() if key != "target_selection_hash"})
    return document


def freeze_target_selection(selection: Mapping[str, Any], path: Path = TARGET_SELECTION_PATH) -> dict[str, Any]:
    proposed = build_target_selection(selection)
    if path.is_file():
        existing = read_json(path, {}) or {}
        if existing != proposed:
            raise RuntimeError("hge1_wave_a_target_selection_changed")
        return existing
    write_json(path, proposed)
    return proposed


def build_wave_units(selection: Mapping[str, Any], target_selection: Mapping[str, Any] | None = None) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    corpus = corpus_index()
    people, known_forms = _people_and_forms()
    target_rows_by_story = {
        hda1._text(row.get("story_id")): list(row.get("targets", []) or [])
        for row in (target_selection or {}).get("records", []) or []
    }
    person_units: list[dict[str, Any]] = []
    temporal_units: list[dict[str, Any]] = []
    for record in selection.get("records", []) or []:
        sid = hda1._text(record.get("story_id"))
        story = corpus.get(sid, {})
        targets = target_rows_by_story.get(sid) if target_selection is not None else _target_rows(story, known_forms, people)
        if targets is None:
            targets = _target_rows(story, known_forms, people)
        for target in targets:
            semantic_target = {key: value for key, value in target.items() if key != "known_existing_person_id"}
            person_units.append({"unit_id": target["target_id"], "story_id": sid, "target": semantic_target, "private_target": target, "story": {"story_id": sid, "chapter_heading": story.get("chapter_heading")}, "windows": build_windows(story, target["surface"])})
        temporal_units.append({"unit_id": f"hge1-temporal-{sid}", "story_id": sid, "story": {"story_id": sid, "chapter_heading": story.get("chapter_heading")}, "windows": build_windows(story)})
    return person_units, temporal_units


def _usage(response: Mapping[str, Any] | None) -> dict[str, int]:
    raw = response.get("usage") if isinstance(response, Mapping) and isinstance(response.get("usage"), Mapping) else {}
    return {key: int(raw.get(key) or 0) for key in ("prompt_tokens", "completion_tokens", "total_tokens")}


def _finish_reason(response: Mapping[str, Any]) -> str | None:
    choices = response.get("choices") if isinstance(response, Mapping) else None
    if not isinstance(choices, list) or not choices or not isinstance(choices[0], Mapping):
        return None
    return hda1._text(choices[0].get("finish_reason")) or None


def _safe_error(exc: Exception) -> dict[str, Any]:
    message = str(exc)
    secret = os.environ.get("DEEPSEEK_API_KEY")
    if secret:
        message = message.replace(secret, "[REDACTED]")
    return {"exception_class": type(exc).__name__, "exception_message": message, "http_status": getattr(exc, "http_status", None)}


def semantic_call(lane: str, unit_id: str, prompt: Mapping[str, Any], raw_dir: Path, sequence: int, *, attempt: int = 1) -> tuple[dict[str, Any], Mapping[str, Any] | None]:
    expected = {"person_read": algorithm.PERSON_ATOM_FUNCTION, "person_fill": algorithm.PERSON_FILL_FUNCTION, "temporal_read": algorithm.TEMPORAL_ATOM_FUNCTION, "temporal_fill": algorithm.TEMPORAL_FILL_FUNCTION}[lane]
    systems = {"person_read": algorithm.PERSON_ATOM_SYSTEM, "person_fill": algorithm.PERSON_ATOM_FILL_SYSTEM, "temporal_read": algorithm.TEMPORAL_ATOM_SYSTEM, "temporal_fill": algorithm.TEMPORAL_ATOM_FILL_SYSTEM}
    budgets = {"person_read": 900, "person_fill": 900, "temporal_read": 750, "temporal_fill": 750}
    started = time.monotonic()
    record: dict[str, Any] = {"sequence": sequence, "attempt": attempt, "lane": lane, "unit_id": unit_id, "model": MODEL, "prompt_version": PROMPT_VERSION, "input_hash": stable_hash(prompt), "start_time": utc_now()}
    try:
        response = call_deepseek([{"role": "system", "content": systems[lane]}, {"role": "user", "content": json.dumps(prompt, ensure_ascii=False, sort_keys=True)}], model=MODEL, temperature=0, thinking={"type": "disabled"}, max_tokens=budgets[lane], timeout=180, endpoint=algorithm.STRICT_ENDPOINT, tools=[algorithm.evidence_atom_function_definition(lane)], tool_choice=algorithm.evidence_atom_tool_choice(lane))
        basename = f"{sequence:04d}-{lane}-{re.sub(r'[^A-Za-z0-9_.-]+', '-', unit_id)}"
        raw_path = raw_dir / f"{basename}.json" if attempt == 1 else raw_dir / f"{basename}-retry-{attempt}.json"
        if raw_path.exists():
            raise RuntimeError("immutable_raw_response_exists")
        write_json(raw_path, response)
        record.update({"classification": "response_truncated" if _finish_reason(response) == "length" else "response", "finish_reason": _finish_reason(response), "usage": _usage(response), "raw_path": str(raw_path.relative_to(ROOT))})
        if record["classification"] == "response_truncated":
            return record, None
        payload, channel, error = controller.extract_strict_tool_payload(response, expected_function_name=expected)
        if error:
            record.update({"classification": "response_parse_failure", "response_channel": channel, "parse_error": error})
            return record, None
        record.update({"classification": "parsed", "response_channel": channel})
        return record, payload
    except Exception as exc:
        record.update({"classification": "provider_request_failure", **_safe_error(exc)})
        return record, None
    finally:
        record["elapsed_seconds"] = round(time.monotonic() - started, 3)
        record["end_time"] = utc_now()


def _fixture_person(unit: Mapping[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    target = unit["target"]
    windows = unit["windows"]
    ref = hda1._text(target.get("source_ref"))
    text = next((hda1._text(row.get("evidence_text")) for row in windows if row.get("ref") == ref), hda1._text(windows[0].get("evidence_text")) if windows else "")
    surface = hda1._text(target.get("surface"))
    atom = {"atom_id": "p0", "atom_kind": "identity_name", "subject_surface": surface, "predicate_surface": "", "object_surface": "", "evidence_ref": ref or (windows[0].get("ref") if windows else ""), "exact_span": surface, "certainty": "explicit"}
    p1 = {"atoms": [atom]} if surface and atom["evidence_ref"] and surface in text else {"atoms": []}
    p2 = {"entities": [{"entity_key": "e0", "surface": surface, "entity_kind": target.get("entity_kind", "named_person"), "reference_form": target.get("reference_form", "full_name"), "evidence_refs": [atom["evidence_ref"]]}], "relations": []} if p1["atoms"] else {"entities": [], "relations": []}
    return p1, p2


def _fixture_temporal(unit: Mapping[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    anchors = algorithm.scan_visible_temporal_anchors(unit["windows"])
    if not anchors:
        return {"atoms": []}, {"temporal_assertions": []}
    anchor = anchors[0]
    p1 = {"atoms": [{"atom_id": "t0", "temporal_surface": anchor["surface"], "reference_surface": anchor["exact_occurrence"], "role_hint": "uncertain", "evidence_ref": anchor["evidence_ref"], "exact_span": anchor["exact_occurrence"], "certainty": "explicit"}]}
    p2 = {"temporal_assertions": [{"temporal_id": "t0", "temporal_surface": anchor["surface"], "temporal_type": "reign_period", "temporal_role": "uncertain", "reference_surface": anchor["exact_occurrence"], "evidence_ref": anchor["evidence_ref"], "exact_span": anchor["exact_occurrence"], "confidence": "low"}]}
    return p1, p2


def run_units(selection: Mapping[str, Any], *, live: bool, run_id: str) -> dict[str, Any]:
    target_selection = freeze_target_selection(selection)
    person_units, temporal_units = build_wave_units(selection, target_selection)
    base = GENERATED / "live" / run_id
    raw_dir = base / "raw-api"
    raw_dir.mkdir(parents=True, exist_ok=True)
    preflight_row = {"status": "offline_not_requested", "model": MODEL}
    if live:
        started = time.monotonic()
        try:
            response = call_deepseek([{"role": "user", "content": "Reply only with OK"}], model=MODEL, temperature=0, max_tokens=8, thinking={"type": "disabled"}, timeout=20)
            preflight_row = {"status": "reachable", "usage": _usage(response), "response_model": response.get("model"), "elapsed_seconds": round(time.monotonic() - started, 3)}
        except Exception as exc:
            preflight_row = {"model": MODEL, "status": "live_network_unavailable", **_safe_error(exc), "elapsed_seconds": round(time.monotonic() - started, 3)}
    transport: list[dict[str, Any]] = []
    person_results: list[dict[str, Any]] = []
    sequence = 0
    for unit in person_units:
        sequence += 1
        p1_prompt = algorithm.person_read_prompt(unit["target"], unit["windows"])
        if live and preflight_row.get("status") == "reachable":
            p1_transport, p1_payload = semantic_call("person_read", unit["unit_id"], p1_prompt, raw_dir, sequence)
            transport.append(p1_transport)
        else:
            p1_payload, _ = _fixture_person(unit)
            p1_transport = {"lane": "person_read", "unit_id": unit["unit_id"], "classification": "offline_fixture", "usage": {}}
        sequence += 1
        p1_validation = algorithm.validate_person_atoms(p1_payload, unit["windows"])
        p2_prompt = algorithm.person_atom_fill_prompt(unit["target"], p1_validation, unit["windows"])
        if live and preflight_row.get("status") == "reachable":
            p2_transport, p2_payload = semantic_call("person_fill", unit["unit_id"], p2_prompt, raw_dir, sequence)
            transport.append(p2_transport)
        else:
            _, p2_payload = _fixture_person(unit)
            p2_transport = {"lane": "person_fill", "unit_id": unit["unit_id"], "classification": "offline_fixture", "usage": {}}
        sequence += 1
        fill_windows = [row for row in unit["windows"] if hda1._text(row.get("ref")) in {hda1._text(atom.get("evidence_ref")) for atom in p1_validation.get("valid_atoms", [])}]
        p2_validation = algorithm.validate_person_fill(p2_payload, fill_windows)
        person_results.append({"unit_id": unit["unit_id"], "story_id": unit["story_id"], "target": unit["target"], "private_target": unit["private_target"], "windows": unit["windows"], "person_read": {"prompt": p1_prompt, "payload": p1_payload, "validation": p1_validation, "transport": p1_transport}, "person_fill": {"prompt": p2_prompt, "payload": p2_payload, "validation": p2_validation, "transport": p2_transport}})
    temporal_results: list[dict[str, Any]] = []
    for unit in temporal_units:
        sequence += 1
        visible = algorithm.scan_visible_temporal_anchors(unit["windows"])
        t1_prompt = algorithm.temporal_read_prompt(unit["story"], unit["windows"], visible_temporal_surfaces=visible)
        if live and preflight_row.get("status") == "reachable":
            t1_transport, t1_payload = semantic_call("temporal_read", unit["unit_id"], t1_prompt, raw_dir, sequence)
            transport.append(t1_transport)
        else:
            t1_payload, _ = _fixture_temporal(unit)
            t1_transport = {"lane": "temporal_read", "unit_id": unit["unit_id"], "classification": "offline_fixture", "usage": {}}
        sequence += 1
        t1_validation = algorithm.validate_temporal_atoms(t1_payload, unit["windows"])
        t2_prompt = algorithm.temporal_atom_fill_prompt(unit["story"], t1_validation, unit["windows"])
        if live and preflight_row.get("status") == "reachable":
            t2_transport, t2_payload = semantic_call("temporal_fill", unit["unit_id"], t2_prompt, raw_dir, sequence)
            transport.append(t2_transport)
        else:
            _, t2_payload = _fixture_temporal(unit)
            t2_transport = {"lane": "temporal_fill", "unit_id": unit["unit_id"], "classification": "offline_fixture", "usage": {}}
        sequence += 1
        fill_windows = [row for row in unit["windows"] if hda1._text(row.get("ref")) in {hda1._text(atom.get("evidence_ref")) for atom in t1_validation.get("valid_atoms", [])}]
        t2_validation = algorithm.validate_temporal_fill(t2_payload, fill_windows)
        temporal_results.append({"unit_id": unit["unit_id"], "story_id": unit["story_id"], "story": unit["story"], "windows": unit["windows"], "visible_temporal_surfaces": visible, "temporal_read": {"prompt": t1_prompt, "payload": t1_payload, "validation": t1_validation, "transport": t1_transport}, "temporal_fill": {"prompt": t2_prompt, "payload": t2_payload, "validation": t2_validation, "transport": t2_transport}})
    manifest = {"schema": "hge1-wave-a-live-manifest-v1", "run_id": run_id, "run_version": RUN_VERSION, "prompt_version": PROMPT_VERSION, "selection_hash": selection.get("selection_hash"), "target_selection_hash": target_selection.get("target_selection_hash"), "preflight": preflight_row, "live_requested": live, "semantic_call_count_expected": 2 * len(person_units) + 2 * len(temporal_units), "protected_hashes_before": hda1.protected_hashes(), "candidate_only": True, "canonical_write_back": False}
    write_json(base / "manifest.json", manifest)
    write_json(base / "selection.json", selection)
    write_json(base / "target-selection.json", target_selection)
    write_json(base / "story-contexts.json", [{"story_id": unit["story_id"], "windows": unit["windows"]} for unit in person_units[:: max(1, len([x for x in person_units if x["story_id"] == person_units[0]["story_id"]]))] if person_units] if person_units else [])
    write_json(base / "person-results.json", person_results)
    write_json(base / "temporal-results.json", temporal_results)
    write_json(base / "transport.json", transport)
    return {"base": base, "person_results": person_results, "temporal_results": temporal_results, "transport": transport, "preflight": preflight_row, "person_units": person_units, "temporal_units": temporal_units, "target_selection": target_selection}


def _candidate_id(story_id: str, surface: str, ref: str) -> str:
    return f"hge1-candidate-person-{stable_hash({"story_id": story_id, "surface": surface, "ref": ref})[:20]}"


def _work(ref: str) -> str:
    return "劉注" if "-liu-" in ref else "世說正文"


def build_projection(selection: Mapping[str, Any], run: Mapping[str, Any]) -> dict[str, Any]:
    people, known_forms = _people_and_forms()
    person_observations: list[dict[str, Any]] = []
    candidate_persons: dict[str, dict[str, Any]] = {}
    rejected: list[dict[str, Any]] = []
    review: list[dict[str, Any]] = []
    for result in run.get("person_results", []) or []:
        target = result.get("private_target") or result.get("target") or {}
        sid = hda1._text(result.get("story_id")); surface = hda1._text(target.get("surface")); ref = hda1._text(target.get("source_ref")); exact_span = hda1._text(target.get("exact_span")) or surface
        pid = hda1._text(target.get("known_existing_person_id")) or None
        if pid and pid in people:
            status = "resolved_existing"; basis = "catalogue_exact_match"; candidate_id = None
        else:
            candidate_id = _candidate_id(sid, surface, ref)
            status = "resolved_new_candidate" if len(surface) >= 2 else "unresolved"
            basis = "new_candidate" if status == "resolved_new_candidate" else "unresolved"
            candidate_persons[candidate_id] = {"candidate_person_id": candidate_id, "canonical_name": surface, "observed_surfaces": [surface], "story_ids": [sid], "evidence_refs": [ref], "candidate_only": True, "canonical_write_back": False}
        p1 = result.get("person_read", {}).get("validation") or {}
        p2 = result.get("person_fill", {}).get("validation") or {}
        for item in p1.get("rejected_atoms", []) or []:
            rejected.append({"lane": "person_read", "story_id": sid, "target_surface": surface, **dict(item)})
        for item in p2.get("rejected_entities", []) or []:
            rejected.append({"lane": "person_fill", "story_id": sid, "target_surface": surface, **dict(item)})
        obs = {"observation_id": f"hge1-person-observation-{stable_hash({'story_id': sid, 'surface': surface, 'ref': ref})[:22]}", "story_id": sid, "surface": surface, "exact_span": exact_span, "evidence_ref": ref, "source_work": _work(ref), "source_layer": "main_text", "status": status, "identity_resolution_basis": basis, "person_id": pid, "candidate_person_id": candidate_id, "candidate_only": True, "canonical_write_back": False, "evidence_grounding_rejects": len(p1.get("rejected_atoms", [])) + len(p2.get("rejected_entities", []))}
        person_observations.append(obs)
        if status != "resolved_existing":
            review.append({"priority": "P1", "review_type": "new_person_candidate", "story_id": sid, "surface": surface, "candidate_person_id": candidate_id, "reason": "new Story person surface requires candidate review", "candidate_only": True, "canonical_write_back": False})
    relation_candidates: list[dict[str, Any]] = []
    for result in run.get("person_results", []) or []:
        sid = hda1._text(result.get("story_id")); validation = result.get("person_fill", {}).get("validation") or {}
        for relation in validation.get("valid_relations", []) or []:
            relation_candidates.append({"candidate_id": f"hge1-relation-{stable_hash({'story_id': sid, 'relation': relation})[:24]}", "story_id": sid, "relation_class": relation.get("relation_class"), "relation_surface": relation.get("relation_surface"), "exact_span": relation.get("exact_span"), "evidence_ref": relation.get("evidence_ref"), "candidate_only": True, "canonical_write_back": False, "basis": "validated_person_card_relation", "cooccurrence_only": False})
    temporal_candidates: list[dict[str, Any]] = []
    visible_count = 0
    valid_temporal_atoms = 0
    for result in run.get("temporal_results", []) or []:
        visible_count += len(result.get("visible_temporal_surfaces", []) or [])
        validation = result.get("temporal_read", {}).get("validation") or {}
        valid_temporal_atoms += len(validation.get("valid_atoms", []) or [])
        for item in (result.get("temporal_fill", {}).get("validation") or {}).get("valid_temporal_assertions", []) or []:
            temporal_candidates.append({"candidate_id": f"hge1-temporal-{stable_hash({'story_id': result.get('story_id'), 'item': item})[:24]}", "story_id": result.get("story_id"), "temporal_role": item.get("temporal_role"), "temporal_type": item.get("temporal_type"), "temporal_surface": item.get("temporal_surface"), "exact_span": item.get("exact_span"), "evidence_ref": item.get("evidence_ref"), "candidate_only": True, "canonical_write_back": False, "h0a_write_back": False})
    story_summary: list[dict[str, Any]] = []
    for record in selection.get("records", []) or []:
        sid = hda1._text(record.get("story_id")); person = [x for x in person_observations if x.get("story_id") == sid]; relations = [x for x in relation_candidates if x.get("story_id") == sid]; temporals = [x for x in temporal_candidates if x.get("story_id") == sid]
        story_summary.append({"story_id": sid, "selection_channel": record.get("selection_channel"), "existing_persons_recovered": sorted({x.get("person_id") for x in person if x.get("person_id")}), "candidate_persons": sorted({x.get("candidate_person_id") for x in person if x.get("candidate_person_id")}), "new_identity_candidates": sum(x.get("status") == "resolved_new_candidate" for x in person), "relation_candidates": len(relations), "temporal_candidates": len(temporals), "unresolved_references": sum(x.get("status") == "unresolved" for x in person), "review_load": sum(1 for x in review if x.get("story_id") == sid)})
    return {"schema": "hge1-wave-a-candidate-db-v1", "wave_id": "HGE1-WA", "selection_hash": selection.get("selection_hash"), "person_observations": sorted(person_observations, key=lambda x: x["observation_id"]), "candidate_persons": [candidate_persons[key] for key in sorted(candidate_persons)], "relation_candidates": sorted(relation_candidates, key=lambda x: x["candidate_id"]), "temporal_candidates": sorted(temporal_candidates, key=lambda x: x["candidate_id"]), "review_items": sorted(review, key=lambda x: (x["priority"], x["story_id"], x.get("surface", ""))), "story_summary": sorted(story_summary, key=lambda x: x["story_id"]), "rejected_items": rejected, "candidate_only": True, "canonical_write_back": False, "visible_temporal_anchor_count": visible_count, "valid_temporal_atom_count": valid_temporal_atoms}


def _components(nodes: Sequence[Mapping[str, Any]], edges: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    keys = {f"{x.get('node_type')}:{x.get('node_id')}" for x in nodes}
    adj = {key: set() for key in keys}
    for edge in edges:
        source = edge.get("source") or {}; target = edge.get("target") or {}
        a = f"{source.get('node_type')}:{source.get('node_id')}"; b = f"{target.get('node_type')}:{target.get('node_id')}"
        if a in adj and b in adj:
            adj[a].add(b); adj[b].add(a)
    seen: set[str] = set(); sizes: list[int] = []
    for start in sorted(adj):
        if start in seen: continue
        stack = [start]; seen.add(start); size = 0
        while stack:
            current = stack.pop(); size += 1
            for neighbor in adj[current]:
                if neighbor not in seen: seen.add(neighbor); stack.append(neighbor)
        sizes.append(size)
    sizes.sort(reverse=True)
    return {"node_count": len(keys), "edge_count": len(edges), "connected_component_count": len(sizes), "largest_component_size": sizes[0] if sizes else 0, "isolated_node_count": sum(len(v) == 0 for v in adj.values()), "component_size_distribution": sizes[:20]}


def baseline() -> dict[str, Any]:
    graph = read_json(DERIVED / "hg0-graph-projection.json", {}) or {}
    metrics = read_json(DERIVED / "hg0-metrics.json", {}) or {}
    aggregate = read_json(DERIVED / "hdb1-cross-wave-candidate-historical-db.json", {}) or {}
    identity_summary = read_json(DERIVED / "hdb2-f-identity-summary.json", {}) or {}
    hdb2_rel = read_json(DERIVED / "hdb2-f-relation-projection.json", {}) or {}
    kin = read_json(DERIVED / "hdb2-f-kinship-projection.json", {}) or {}
    marriage = read_json(DERIVED / "hdb2-f-marriage-projection.json", {}) or {}
    office = read_json(DERIVED / "hdb2-f-office-projection.json", {}) or {}
    person_story = read_json(DERIVED / "person-story-links.json", {}) or {}
    graph_summary = _components(graph.get("nodes", []) or [], graph.get("edges", []) or [])
    return {"schema": "hge1-network-baseline-v1", "story_count": int((metrics.get("scope") or {}).get("published_stories") or len(production_story_ids())), "existing_person_count": len((read_json(ROOT / "data/people.json", {}) or {}).get("people", []) or []), "candidate_person_count": len((read_json(DERIVED / "hdb2-f-candidate-person-knowledge.json", {}) or {}).get("records", []) or []), "person_story_count": int((metrics.get("scope") or {}).get("published_person_story_links") or len([x for x in person_story.get("links", []) if x.get("entry_id") in production_story_ids()])), "identity_occurrence_count": len(aggregate.get("identity_observations", []) or []), "kinship_fact_or_candidate_count": len(kin.get("records", []) or []), "marriage_fact_or_candidate_count": len(marriage.get("records", []) or []), "office_fact_count": len(office.get("records", []) or []), "social_relation_edge_count": len(hdb2_rel.get("records", []) or []), "graph_nodes": graph_summary["node_count"], "graph_edges": graph_summary["edge_count"], "connected_components": graph_summary["connected_component_count"], "largest_component_size": graph_summary["largest_component_size"], "isolated_orphan_nodes": graph_summary["isolated_node_count"], "unresolved_identity_count": int((identity_summary.get("final_states") or {}).get("unresolved", 0)), "source_hashes": {path: file_hash(ROOT / path) for path in ["data/derived/hg0-graph-projection.json", "data/derived/hg0-metrics.json", "data/derived/hdb1-cross-wave-candidate-historical-db.json", "data/derived/hdb2-f-identity-summary.json"] if (ROOT / path).is_file()}, "protected_hashes": hda1.protected_hashes(), "candidate_only": True, "canonical_write_back": False}


def freeze_baseline(path: Path = GENERATED / "baseline.json") -> dict[str, Any]:
    proposed = baseline()
    if path.is_file():
        existing = read_json(path, {}) or {}
        if existing != proposed:
            raise RuntimeError("hge1_baseline_changed")
        return existing
    write_json(path, proposed)
    return proposed


def growth_projection(base: Mapping[str, Any], candidate_db: Mapping[str, Any], selection: Mapping[str, Any]) -> dict[str, Any]:
    story_count = len(selection.get("story_ids", []) or [])
    person_obs = list(candidate_db.get("person_observations", []) or [])
    candidate_persons = list(candidate_db.get("candidate_persons", []) or [])
    existing_reached = sorted({hda1._text(row.get("person_id")) for row in person_obs if hda1._text(row.get("person_id"))})
    relation_count = len(candidate_db.get("relation_candidates", []) or [])
    temporal_count = len(candidate_db.get("temporal_candidates", []) or [])
    # Add the wave to the actual frozen graph, retaining its node IDs.  The
    # previous implementation measured only a wave-local subgraph, which
    # made the reported component delta meaningless and accidentally used
    # ``person:person-NNN`` IDs that could not join existing Person nodes.
    base_graph = read_json(DERIVED / "hg0-graph-projection.json", {}) or {}
    nodes = [dict(node) for node in base_graph.get("nodes", []) or [] if isinstance(node, Mapping)]
    existing_node_keys = {(node.get("node_type"), node.get("node_id")) for node in nodes}
    for row in candidate_persons:
        key = ("Person", str(row.get("candidate_person_id")))
        if key not in existing_node_keys:
            nodes.append({"node_type": "Person", "node_id": str(row.get("candidate_person_id")), "label": row.get("canonical_name"), "review_status": "candidate", "scope_role": "research_candidate"})
            existing_node_keys.add(key)
    for sid in selection.get("story_ids", []) or []:
        key = ("Story", sid)
        if key not in existing_node_keys:
            nodes.append({"node_type": "Story", "node_id": sid, "label": sid, "review_status": "candidate", "scope_role": "research_candidate"})
            existing_node_keys.add(key)
    edges = [dict(edge) for edge in base_graph.get("edges", []) or [] if isinstance(edge, Mapping)]
    wave_edges: list[dict[str, Any]] = []
    for row in person_obs:
        endpoint = row.get("person_id") or row.get("candidate_person_id")
        if not endpoint:
            continue
        wave_edges.append({"edge_id": f"hge1-wave-a-person-story-{stable_hash(row)[:20]}", "edge_type": "candidate_person_story_link", "source": {"node_type": "Person", "node_id": endpoint}, "target": {"node_type": "Story", "node_id": row.get("story_id")}, "candidate_only": True, "canonical_write_back": False})
    edges.extend(wave_edges)
    # Relation cards are retained as candidates, but without resolved
    # endpoints they cannot safely become topology edges.
    combined_graph = _components(nodes, edges)
    wave_graph = _components(
        [{"node_type": "Person", "node_id": pid} for pid in existing_reached]
        + [{"node_type": "Person", "node_id": str(row.get("candidate_person_id"))} for row in candidate_persons]
        + [{"node_type": "Story", "node_id": sid} for sid in selection.get("story_ids", []) or []],
        wave_edges,
    )
    by_channel: dict[str, dict[str, Any]] = {}
    for record in selection.get("records", []) or []:
        channel = record.get("selection_channel")
        ids = {record.get("story_id")}
        obs = [x for x in person_obs if x.get("story_id") in ids]
        by_channel[channel] = {"story_count": int(by_channel.get(channel, {}).get("story_count", 0)) + 1, "existing_person_links": int(by_channel.get(channel, {}).get("existing_person_links", 0)) + sum(bool(x.get("person_id")) for x in obs), "new_person_candidates": int(by_channel.get(channel, {}).get("new_person_candidates", 0)) + sum(x.get("status") == "resolved_new_candidate" for x in obs), "relation_candidates": int(by_channel.get(channel, {}).get("relation_candidates", 0)) + sum(x.get("story_id") in ids for x in candidate_db.get("relation_candidates", []) or []), "review_items": int(by_channel.get(channel, {}).get("review_items", 0)) + sum(x.get("story_id") in ids for x in candidate_db.get("review_items", []) or [])}
    after = {"story_count": int(base.get("story_count") or 0) + story_count, "existing_person_count": int(base.get("existing_person_count") or 0), "candidate_person_count": int(base.get("candidate_person_count") or 0) + len(candidate_persons), "person_story_count": int(base.get("person_story_count") or 0) + len(person_obs), "identity_occurrence_count": int(base.get("identity_occurrence_count") or 0) + len(person_obs), "kinship_fact_or_candidate_count": int(base.get("kinship_fact_or_candidate_count") or 0), "marriage_fact_or_candidate_count": int(base.get("marriage_fact_or_candidate_count") or 0), "office_fact_count": int(base.get("office_fact_count") or 0), "social_relation_edge_count": int(base.get("social_relation_edge_count") or 0) + relation_count, "graph_nodes": combined_graph["node_count"], "graph_edges": combined_graph["edge_count"], "connected_components": combined_graph["connected_component_count"], "largest_component_size": combined_graph["largest_component_size"], "isolated_orphan_nodes": combined_graph["isolated_node_count"], "unresolved_identity_count": int(base.get("unresolved_identity_count") or 0) + sum(x.get("status") == "unresolved" for x in person_obs)}
    delta = {key: after.get(key, 0) - (base.get(key, 0) if isinstance(base.get(key, 0), (int, float)) else 0) for key in after}
    existing_link_count = sum(bool(x.get("person_id")) for x in person_obs)
    return {"schema": "hge1-wave-a-growth-projection-v1", "wave_id": "HGE1-WA", "baseline": dict(base), "after": after, "delta": delta, "existing_persons_reached_by_wave": existing_reached, "candidate_person_ids": sorted(str(x.get("candidate_person_id")) for x in candidate_persons), "wave_graph_summary": wave_graph, "combined_graph_summary": combined_graph, "channel_yield": by_channel, "new_person_candidates_per_story": round(len(candidate_persons) / story_count, 6) if story_count else 0, "new_existing_person_links_per_story": round(existing_link_count / story_count, 6) if story_count else 0, "new_edges_per_story": round((len(wave_edges) + relation_count) / story_count, 6) if story_count else 0, "resolved_identities_per_story": round(sum(x.get("status") == "resolved_existing" for x in person_obs) / story_count, 6) if story_count else 0, "unresolved_identities_per_story": round(sum(x.get("status") == "unresolved" for x in person_obs) / story_count, 6) if story_count else 0, "review_items_per_story": round(len(candidate_db.get("review_items", []) or []) / story_count, 6) if story_count else 0, "candidate_only": True, "canonical_write_back": False}


def operational_metrics(run: Mapping[str, Any]) -> dict[str, Any]:
    """Summarize provider activity without making it part of graph growth.

    Growth and candidate projections remain deterministic functions of the
    frozen run responses.  Transport timing and provider status are kept in
    the live production summary so an unavailable provider cannot be
    mistaken for a semantic result or make the growth snapshot drift.
    """
    transport = [row for row in run.get("transport", []) or [] if isinstance(row, Mapping)]
    classifications = collections.Counter(hda1._text(row.get("classification")) for row in transport)
    usages = [
        row.get("usage") for row in transport
        if isinstance(row.get("usage"), Mapping)
    ]
    latencies = [float(row.get("elapsed_seconds") or 0) for row in transport]
    return {
        "model": MODEL,
        "semantic_calls": len(transport),
        "expected_semantic_calls": 2 * len(run.get("person_units", []) or []) + 2 * len(run.get("temporal_units", []) or []),
        "retries": sum(1 for row in transport if row.get("retry_of_sequence")),
        "provider_failures": classifications["provider_request_failure"],
        "parse_failures": classifications["response_parse_failure"],
        "truncated_responses": classifications["response_truncated"],
        "prompt_tokens": sum(int(row.get("prompt_tokens") or 0) for usage in usages for row in [usage]),
        "completion_tokens": sum(int(row.get("completion_tokens") or 0) for usage in usages for row in [usage]),
        "total_tokens": sum(int(row.get("total_tokens") or 0) for usage in usages for row in [usage]),
        "median_latency_seconds": round(statistics.median(latencies), 3) if latencies else 0,
        "max_latency_seconds": round(max(latencies), 3) if latencies else 0,
        "preflight": dict(run.get("preflight") or {}),
        "offline_fixture_used": not bool(transport),
    }


def write_outputs(selection: Mapping[str, Any], run: Mapping[str, Any]) -> dict[str, Any]:
    candidate_db = build_projection(selection, run)
    base = baseline()
    growth = growth_projection(base, candidate_db, selection)
    run_base: Path = run["base"]
    write_json(run_base / "rejected-items.json", {"records": candidate_db.get("rejected_items", []), "candidate_only": True, "canonical_write_back": False})
    write_json(run_base / "production-summary.json", {"selection_hash": selection.get("selection_hash"), "story_summary": candidate_db.get("story_summary", []), "operational_metrics": operational_metrics(run), "candidate_only": True, "canonical_write_back": False})
    write_json(run_base / "candidate-db.json", candidate_db)
    for path, key in [("hge1-wave-a-person-candidates.json", "person_observations"), ("hge1-wave-a-relation-candidates.json", "relation_candidates"), ("hge1-wave-a-temporal-candidates.json", "temporal_candidates")]:
        write_json(ANNOTATION / path, {"schema": f"{key}-v1", "wave_id": "HGE1-WA", "records": candidate_db.get(key, []), "candidate_only": True, "canonical_write_back": False})
    write_json(ANNOTATION / "hge1-wave-a-review-queue.json", {"schema": "hge1-wave-a-review-queue-v1", "records": candidate_db.get("review_items", []), "candidate_only": True, "canonical_write_back": False})
    write_json(DERIVED / "hge1-wave-a-candidate-db.json", candidate_db)
    write_json(DERIVED / "hge1-wave-a-metrics.json", growth)
    write_json(DERIVED / "hge1-wave-a-gap-audit.json", {"schema": "hge1-wave-a-gap-audit-v1", "story_summary": candidate_db.get("story_summary", []), "rejected_items": candidate_db.get("rejected_items", []), "candidate_only": True, "canonical_write_back": False})
    series_path = GENERATED / "network-growth-series.json"
    series = read_json(series_path, {}) or {}
    if not series:
        series = {"schema": "hge1-network-growth-series-v1", "series": [{"wave": "baseline", **{key: base.get(key) for key in ("story_count", "existing_person_count", "candidate_person_count", "graph_nodes", "graph_edges")}}]}
    wave_row = {"wave": "HGE1-WA", **{key: growth["after"].get(key) for key in ("story_count", "existing_person_count", "candidate_person_count", "graph_nodes", "graph_edges")}}
    existing_rows = [x for x in series.get("series", []) if x.get("wave") != "HGE1-WA"]
    series["series"] = [*existing_rows, wave_row]
    series["candidate_only"] = True; series["canonical_write_back"] = False
    write_json(series_path, series)
    return {"candidate_db": candidate_db, "growth": growth, "base": base, "series": series}


def validate_selection(selection: Mapping[str, Any]) -> list[str]:
    errors: list[str] = []
    production = production_story_ids(); prior, _ = prior_story_ids(); ids = [hda1._text(x) for x in selection.get("story_ids", []) or []]
    if len(ids) != 20 or len(set(ids)) != len(ids): errors.append("story_count_not_exactly_20_or_duplicate")
    if set(ids) & production: errors.append("production_story_overlap")
    if set(ids) & prior: errors.append("prior_hng2_story_overlap")
    if selection.get("overlap_with_production") != []: errors.append("selection_declared_production_overlap")
    if selection.get("overlap_with_prior_hng2") != []: errors.append("selection_declared_prior_overlap")
    if selection.get("frozen_before_live") is not True: errors.append("not_frozen_before_live")
    if selection.get("candidate_only") is not True or selection.get("canonical_write_back") is not False: errors.append("candidate_boundary")
    expected = stable_hash({key: value for key, value in selection.items() if key != "selection_hash"})
    if selection.get("selection_hash") != expected: errors.append("selection_hash_invalid")
    return errors


def validate_target_selection(selection: Mapping[str, Any], target_selection: Mapping[str, Any]) -> list[str]:
    errors: list[str] = []
    if target_selection.get("selection_hash") != selection.get("selection_hash"):
        errors.append("target_selection_parent_hash")
    if target_selection.get("candidate_only") is not True or target_selection.get("canonical_write_back") is not False:
        errors.append("target_selection_boundary")
    if target_selection.get("frozen_before_live") is not True:
        errors.append("target_selection_not_frozen")
    records = list(target_selection.get("records", []) or [])
    expected_ids = set(hda1._text(x) for x in selection.get("story_ids", []) or [])
    actual_ids = {hda1._text(x.get("story_id")) for x in records}
    if actual_ids != expected_ids:
        errors.append("target_selection_story_coverage")
    for row in records:
        targets = list(row.get("targets", []) or [])
        if not 1 <= len(targets) <= 2:
            errors.append(f"target_count:{row.get('story_id')}")
        for target in targets:
            surface = hda1._text(target.get("surface"))
            if not surface or surface not in hda1._text((corpus_index().get(hda1._text(row.get("story_id"))) or {}).get("main_text")):
                errors.append(f"target_not_source_grounded:{row.get('story_id')}:{surface}")
    expected_hash = stable_hash({key: value for key, value in target_selection.items() if key != "target_selection_hash"})
    if target_selection.get("target_selection_hash") != expected_hash:
        errors.append("target_selection_hash_invalid")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prepare", action="store_true")
    parser.add_argument("--offline", action="store_true")
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--run-id")
    args = parser.parse_args()
    selection = freeze_selection()
    errors = validate_selection(selection)
    if errors: raise SystemExit(";".join(errors))
    target_selection = freeze_target_selection(selection)
    frozen_baseline = freeze_baseline()
    if args.prepare or (not args.live and not args.offline):
        print(json.dumps({"story_count": selection["story_count"], "story_ids": selection["story_ids"], "selection_hash": selection["selection_hash"], "target_count": target_selection["target_count"], "target_selection_hash": target_selection["target_selection_hash"], "baseline_hash": stable_hash(frozen_baseline), "validation": "ok"}, ensure_ascii=False, indent=2))
        return 0
    run_id = args.run_id or (dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ") if args.live else "offline")
    run = run_units(selection, live=args.live, run_id=run_id)
    output = write_outputs(selection, run)
    print(json.dumps({"run_id": run_id, "story_count": selection["story_count"], "person_targets": len(run["person_results"]), "semantic_calls": len(run["transport"]), "preflight": run["preflight"], "growth": output["growth"]}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
