#!/usr/bin/env python3
"""Run HNG2-C.1 two-lane, two-stage semantic validation.

The runner reuses frozen HNG2-C evidence and existing Shishuo/H0A records.
It performs no retrieval, search planning, frontier growth, or canonical write.
"""

from __future__ import annotations

import argparse
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
import hng2_schema_controller as controller  # noqa: E402
import run_hng2_consolidation as consolidation  # noqa: E402
import run_hng2_schema_controller_hardening as hardening  # noqa: E402
from build_six_person_pilot import parse_shishuo_sections  # noqa: E402
from smoke_deepseek import call_deepseek  # noqa: E402


OUT = ROOT / "data/generated/hng2-read-fill-validation"
MODEL = "deepseek-v4-flash"
RUN_VERSION = "hng2-c1-read-fill-v1"
PROMPT_VERSION = "hng2-c1-split-lanes-v1"

PERSON_REGRESSION_CASE_IDS = (
    "hng1r2-hng1-raw-relation-921d528c3cf9154fa43c",  # 廙
    "hng1r2-hng1-raw-relation-2ff2066d8872cbae15f7",  # 庾太尉
    "hng1r2-hng1-raw-relation-7d036391e66574c6f83b",  # 嶠
    "hng1r2-hng1-raw-time-46252a6e46037881a4da",      # 山濤
    "hng2-live-hng2-live-w1-identity-33afe84247b036e9d9cb",  # 陳騫
    "hng1r2-hng1-raw-relation-1153a723032c48422396",  # 宣
    "hng1r2-hng1-raw-relation-e5db687ff626c0efa13e",  # 譽
    "hng1r2-hng1-raw-relation-b97bdeb3fbec092978bc",  # 虞喜
)

TEMPORAL_REGRESSION_STORIES = (
    ("reign_bounded", "01-dexing-017"),
    ("event_bounded", "05-fangzheng-032"),
    ("later_outcome_trap", "06-yaliang-017"),
    ("quoted_precedent_trap", "04-wenxue-022"),
)

HELDOUT_CATEGORIES = (
    "clear_full_name",
    "abbreviated_or_title_name",
    "kinship_or_marriage",
    "institutional_or_interaction",
    "temporally_informative_or_ambiguous",
)


def read_json(path: Path, default: Any = None) -> Any:
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else default


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def stable_hash(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _entry_path(story_id: str) -> Path:
    chapter, ordinal = story_id.rsplit("-", 1)
    return ROOT / "content/processed/shishuo/entries" / chapter / f"entry-{ordinal}.md"


def _punctuation_index() -> dict[str, Mapping[str, Any]]:
    document = read_json(ROOT / "data/annotation/wp1-punctuation.json", {}) or {}
    return {str(row.get("entry_id")): row for row in document.get("records", []) if isinstance(row, Mapping) and row.get("entry_id")}


def _story_sections(story_id: str) -> list[dict[str, Any]]:
    path = _entry_path(story_id)
    text = path.read_text(encoding="utf-8")
    punctuation = _punctuation_index().get(story_id, {})
    psections = punctuation.get("sections") if isinstance(punctuation.get("sections"), Mapping) else {}
    rows: list[dict[str, Any]] = []
    annotation_index = 0
    for section, source_text, metadata in parse_shishuo_sections(text):
        if section == "main_text":
            key = "main_text"
            ref = f"hng2c1-shishuo-{story_id}-main"
        elif section == "liu_annotation":
            annotation_index += 1
            aid = str(metadata.get("annotation_id") or f"annotation-{annotation_index:03d}")
            key = "liu_annotation" if annotation_index == 1 else f"liu_annotation_{annotation_index}"
            # The WP1 record currently exposes only the first annotation as a
            # named section.  Later blocks remain deterministic raw display.
            ref = f"hng2c1-shishuo-{story_id}-liu-{aid}"
        else:
            continue
        punctuated = psections.get(key) if isinstance(psections, Mapping) else None
        evidence_text = punctuated.get("punctuated_text") if isinstance(punctuated, Mapping) else None
        row = algorithm.prepare_evidence_window(
            {
                "ref": ref,
                "work": "世說新語",
                "layer": section,
                "source_form": "punctuated" if evidence_text else "legacy_local",
                "text": source_text.rstrip("\n"),
                "evidence_text": evidence_text,
                "locator": {"story_id": story_id, "section": section, "path": str(path.relative_to(ROOT)), **dict(metadata)},
            }
        )
        rows.append(row)
    if not any(row.get("layer") == "main_text" for row in rows):
        raise RuntimeError(f"story_main_missing:{story_id}")
    return rows


def _select_story_windows(story_id: str, *, target: str = "", canonical_name: str = "", lane: str) -> list[dict[str, Any]]:
    rows = _story_sections(story_id)
    main = next(row for row in rows if row.get("layer") == "main_text")
    others = [row for row in rows if row is not main]
    relation_markers = ("父", "母", "子", "女", "兄", "弟", "妻", "婿", "妾", "辟", "拜", "除", "召", "詣", "語")
    temporal_markers = ("年", "帝", "王", "時", "初", "末", "亂", "崩", "薨", "遇害", "過江", "永嘉", "咸和", "正始")
    markers = temporal_markers if lane == "temporal" else relation_markers

    def score(row: Mapping[str, Any]) -> tuple[int, str]:
        text = str(row.get("evidence_text") or "")
        value = (100 if target and target in text else 0) + (70 if canonical_name and canonical_name in text else 0)
        value += sum(5 for marker in markers if marker in text)
        return (-value, str(row.get("ref")))

    limit = 2000 if lane == "temporal" else 1500
    max_windows = 4
    selected = [main]
    used = len(str(main.get("evidence_text") or ""))
    for row in sorted(others, key=score):
        length = len(str(row.get("evidence_text") or ""))
        if len(selected) >= max_windows:
            break
        if used + length > limit and selected:
            continue
        selected.append(row)
        used += length
    return selected


def _old_person_windows(case_id: str, cases: Mapping[str, Mapping[str, Any]], sources: Mapping[str, Mapping[str, Any]]) -> list[dict[str, Any]]:
    bundle = algorithm.select_evidence_bundle(cases[case_id], hardening.passages_for(case_id, cases[case_id], sources), max_passages=4, max_chars=500)
    windows = [algorithm.prepare_evidence_window(row) for row in bundle.get("passages", [])]
    total = 0
    selected: list[dict[str, Any]] = []
    for row in windows:
        size = len(str(row.get("evidence_text") or ""))
        if total + size > 1500 and selected:
            continue
        selected.append(row)
        total += size
    return selected


def _prior_target_person_ids(cases: Mapping[str, Mapping[str, Any]]) -> set[str]:
    result: set[str] = set()
    for case_id in PERSON_REGRESSION_CASE_IDS:
        case = cases.get(case_id, {})
        for row in case.get("candidates", []) if isinstance(case.get("candidates"), list) else []:
            if isinstance(row, Mapping) and row.get("person_id"):
                result.add(str(row["person_id"]))
    return result


def _eligible_heldout_rows(cases: Mapping[str, Mapping[str, Any]]) -> list[dict[str, Any]]:
    catalog = hng02.person_catalog()
    hng0 = read_json(ROOT / "data/generated/hng0/hng0-selection.json", {}) or {}
    hng1 = read_json(ROOT / "data/generated/hng1/hng1-selection.json", {}) or {}
    excluded = {str(row["person_id"]) for row in hng0.get("people", []) + hng1.get("people", []) if isinstance(row, Mapping) and row.get("person_id")}
    excluded |= _prior_target_person_ids(cases)
    mentions = read_json(ROOT / "data/mentions/shishuo.json", {}) or {}
    anchors = read_json(ROOT / "data/annotation/story-temporal-anchors-h0a.json", {}) or {}
    anchor_by_story = {str(row.get("story_id")): row for row in anchors.get("records", []) if isinstance(row, Mapping)}
    result: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for mention in mentions.get("mentions", []):
        if not isinstance(mention, Mapping) or mention.get("section") != "main_text":
            continue
        pid = str(mention.get("person_id") or ""); story_id = str(mention.get("entry_id") or "")
        if not pid or pid in excluded or pid not in catalog or not story_id or (pid, story_id) in seen:
            continue
        seen.add((pid, story_id))
        surface = str(mention.get("surface") or ""); canonical = str(catalog[pid].get("canonical_name") or "")
        windows = _story_sections(story_id)
        main_text = next(str(row.get("evidence_text") or "") for row in windows if row.get("layer") == "main_text")
        annotation_text = "".join(str(row.get("evidence_text") or "") for row in windows if row.get("layer") == "liu_annotation")
        key = stable_hash({"story_id": story_id, "person_id": pid, "surface": surface})
        result.append(
            {
                "story_id": story_id,
                "person_id": pid,
                "canonical_name": canonical,
                "target_surface": surface,
                "main_text": main_text,
                "annotation_text": annotation_text,
                "h0a_precision": (anchor_by_story.get(story_id) or {}).get("precision"),
                "selection_key": key,
            }
        )
    return result


def derive_heldout_selection(cases: Mapping[str, Mapping[str, Any]]) -> list[dict[str, Any]]:
    rows = _eligible_heldout_rows(cases)
    selected: list[dict[str, Any]] = []
    used_people: set[str] = set(); used_stories: set[str] = set()

    def choose(category: str, predicate: Any) -> None:
        candidates = [row for row in rows if row["person_id"] not in used_people and row["story_id"] not in used_stories and predicate(row)]
        if not candidates:
            raise RuntimeError(f"heldout_category_empty:{category}")
        row = min(candidates, key=lambda item: item["selection_key"])
        used_people.add(row["person_id"]); used_stories.add(row["story_id"])
        windows = _select_story_windows(row["story_id"], target=row["target_surface"], canonical_name=row["canonical_name"], lane="person")
        selected.append(
            {
                "unit_id": f"heldout-{len(selected)+1:02d}-{row['story_id']}",
                "story_id": row["story_id"],
                "person_id": row["person_id"],
                "target_surface": row["target_surface"],
                "category": category,
                "source_refs": [window["ref"] for window in windows],
                "selection_key": row["selection_key"],
            }
        )

    choose("clear_full_name", lambda row: row["target_surface"] == row["canonical_name"] and row["h0a_precision"] == "event_bounded")
    choose("abbreviated_or_title_name", lambda row: row["target_surface"] != row["canonical_name"] and row["canonical_name"] in row["annotation_text"])
    choose("kinship_or_marriage", lambda row: row["target_surface"] == row["canonical_name"] and any(mark in row["main_text"] for mark in ("父", "母", "子", "女", "兄", "弟", "妻", "妾", "婿", "姻", "婚", "嫁")))
    choose("institutional_or_interaction", lambda row: row["target_surface"] == row["canonical_name"] and any(mark in row["main_text"] for mark in ("辟", "拜", "除", "召", "詣", "為掾", "爲掾")))
    choose("temporally_informative_or_ambiguous", lambda row: row["target_surface"] != row["canonical_name"] and any(mark in row["main_text"] for mark in ("帝", "登阼", "年", "時", "初", "亂", "崩")))
    return selected


def build_selection() -> dict[str, Any]:
    cases, _, sources = hardening.load_inputs()
    person_regression: list[dict[str, Any]] = []
    for case_id in PERSON_REGRESSION_CASE_IDS:
        case = cases.get(case_id)
        if not isinstance(case, Mapping):
            raise RuntimeError(f"regression_case_missing:{case_id}")
        observation = case.get("observation") if isinstance(case.get("observation"), Mapping) else {}
        windows = _old_person_windows(case_id, cases, sources)
        person_regression.append({
            "unit_id": f"person-regression-{case_id}", "case_id": case_id,
            "target_surface": observation.get("surface"), "source_refs": [row["ref"] for row in windows],
        })
    temporal_regression = []
    for category, story_id in TEMPORAL_REGRESSION_STORIES:
        windows = _select_story_windows(story_id, lane="temporal")
        temporal_regression.append({
            "unit_id": f"temporal-regression-{story_id}", "story_id": story_id,
            "category": category, "source_refs": [row["ref"] for row in windows],
        })
    heldout = derive_heldout_selection(cases)
    return {
        "stage": "hng2-c1-two-stage-read-fill-selection",
        "algorithm_version": RUN_VERSION,
        "frozen_before_live": True,
        "selection_method": "exclude HNG0/HNG1 and prior HNG2-C targets; deterministic category predicates followed by SHA-256 rank",
        "person_regression": person_regression,
        "temporal_regression": temporal_regression,
        "heldout": heldout,
        "heldout_count": len(heldout),
        "heldout_categories": list(HELDOUT_CATEGORIES),
        "heldout_semantic_call_count": len(heldout) * 4,
        "canonical_write_back": False,
    }


def ensure_selection() -> dict[str, Any]:
    selection = build_selection()
    path = OUT / "selection.json"
    if path.is_file():
        existing = read_json(path, {})
        if stable_hash(existing) != stable_hash(selection):
            raise RuntimeError("frozen_selection_mismatch")
    else:
        write_json(path, selection)
    if selection.get("heldout_count") != 5:
        raise RuntimeError("heldout_count_not_five")
    return selection


def _heldout_case(selected: Mapping[str, Any]) -> dict[str, Any]:
    catalog = hng02.person_catalog(); person = catalog.get(str(selected.get("person_id")), {})
    return {
        "story_id": selected.get("story_id"),
        "observation": {"surface": selected.get("target_surface"), "source_work": "世說新語"},
        "seed": {"person_id": selected.get("person_id"), "canonical_name": person.get("canonical_name")},
        "candidates": [{
            "candidate_key": "c0", "person_id": selected.get("person_id"),
            "canonical_name": person.get("canonical_name"), "known_forms": resolver.catalog_forms(person),
        }],
    }


def build_units(selection: Mapping[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    cases, _, sources = hardening.load_inputs()
    person_units: list[dict[str, Any]] = []
    for row in selection.get("person_regression", []):
        case_id = str(row["case_id"]); case = cases[case_id]
        observation = case.get("observation") if isinstance(case.get("observation"), Mapping) else {}
        person_units.append({
            "unit_id": row["unit_id"], "group": "person_regression", "case": case,
            "target": {"surface": observation.get("surface"), "source_work": observation.get("source_work")},
            "windows": _old_person_windows(case_id, cases, sources), "case_id": case_id,
        })
    temporal_units: list[dict[str, Any]] = []
    for row in selection.get("temporal_regression", []):
        story_id = str(row["story_id"])
        temporal_units.append({
            "unit_id": row["unit_id"], "group": "temporal_regression", "story_id": story_id,
            "story": {"story_id": story_id, "target_unit": "Story/scene"},
            "windows": _select_story_windows(story_id, lane="temporal"), "category": row.get("category"),
        })
    heldout_units: list[dict[str, Any]] = []
    for row in selection.get("heldout", []):
        story_id = str(row["story_id"]); case = _heldout_case(row)
        person_windows = _select_story_windows(story_id, target=str(row["target_surface"]), canonical_name=str(case["seed"].get("canonical_name") or ""), lane="person")
        temporal_windows = _select_story_windows(story_id, lane="temporal")
        heldout_units.append({
            "unit_id": row["unit_id"], "group": "heldout", "story_id": story_id,
            "case": case, "target": {"surface": row["target_surface"], "source_work": "世說新語", "story_id": story_id},
            "story": {"story_id": story_id, "target_unit": "Story/scene"},
            "person_windows": person_windows, "temporal_windows": temporal_windows,
            "category": row.get("category"), "person_id": row.get("person_id"),
        })
    return person_units, temporal_units, heldout_units


def usage(response: Mapping[str, Any]) -> dict[str, int]:
    raw = response.get("usage") if isinstance(response.get("usage"), Mapping) else {}
    return {key: int(raw.get(key) or 0) for key in ("prompt_tokens", "completion_tokens", "total_tokens")}


def finish_reason(response: Mapping[str, Any]) -> str | None:
    choices = response.get("choices") if isinstance(response, Mapping) else None
    return str(choices[0].get("finish_reason") or "") or None if isinstance(choices, list) and choices and isinstance(choices[0], Mapping) else None


def _safe_error(exc: Exception) -> dict[str, Any]:
    message = str(exc); secret = os.environ.get("DEEPSEEK_API_KEY")
    if secret:
        message = message.replace(secret, "[REDACTED]")
    return {"exception_class": type(exc).__name__, "exception_message": message, "http_status": getattr(exc, "http_status", None)}


def preflight() -> dict[str, Any]:
    started = time.monotonic(); record = {"start_time": utc_now(), "model": MODEL}
    try:
        response = call_deepseek([{"role": "user", "content": "Reply only with OK"}], model=MODEL, temperature=0, max_tokens=16, thinking={"type": "disabled"}, timeout=60)
        record.update({"status": "reachable", "usage": usage(response), "response_model": response.get("model")})
    except Exception as exc:
        record.update({"status": "live_network_unavailable", **_safe_error(exc)})
    record.update({"elapsed_seconds": round(time.monotonic() - started, 3), "end_time": utc_now()})
    return record


def semantic_call(*, lane: str, unit_id: str, prompt: Mapping[str, Any], raw_dir: Path, sequence: int) -> tuple[dict[str, Any], Mapping[str, Any] | None]:
    expected = {
        "person_read": algorithm.PERSON_READ_FUNCTION, "person_fill": algorithm.PERSON_FILL_FUNCTION,
        "temporal_read": algorithm.TEMPORAL_READ_FUNCTION, "temporal_fill": algorithm.TEMPORAL_FILL_FUNCTION,
    }[lane]
    systems = {
        "person_read": algorithm.PERSON_READ_SYSTEM, "person_fill": algorithm.PERSON_FILL_SYSTEM,
        "temporal_read": algorithm.TEMPORAL_READ_SYSTEM, "temporal_fill": algorithm.TEMPORAL_FILL_SYSTEM,
    }
    budgets = {"person_read": 900, "person_fill": 900, "temporal_read": 750, "temporal_fill": 750}
    started = time.monotonic()
    record: dict[str, Any] = {
        "sequence": sequence, "lane": lane, "unit_id": unit_id, "start_time": utc_now(),
        "model": MODEL, "prompt_version": PROMPT_VERSION, "input_hash": stable_hash(prompt),
    }
    try:
        response = call_deepseek(
            [{"role": "system", "content": systems[lane]}, {"role": "user", "content": json.dumps(prompt, ensure_ascii=False, sort_keys=True)}],
            model=MODEL, temperature=0, thinking={"type": "disabled"}, max_tokens=budgets[lane], timeout=180,
            endpoint=algorithm.STRICT_ENDPOINT, tools=[algorithm.read_fill_function_definition(lane)], tool_choice=algorithm.read_fill_tool_choice(lane),
        )
        raw_path = raw_dir / f"{sequence:03d}-{lane}-{re.sub(r'[^A-Za-z0-9_.-]+', '-', unit_id)}.json"
        write_json(raw_path, response)
        reason = finish_reason(response)
        record.update({"status": "response", "finish_reason": reason, "usage": usage(response), "raw_path": str(raw_path.relative_to(ROOT))})
        if reason == "length":
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


def _fixture_payload(lane: str, target: Mapping[str, Any], windows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    ref = str(windows[0].get("ref") or "") if windows else ""; text = str(windows[0].get("evidence_text") or "") if windows else ""
    surface = str(target.get("surface") or "")
    if lane == "person_read":
        return {"observations": [{"observation_id": "o0", "observation_kind": "identity_name", "subject_surface": surface, "predicate_surface": "", "object_surface": "", "evidence_ref": ref, "exact_span": surface, "certainty": "explicit"}]} if surface and surface in text else {"observations": []}
    if lane == "person_fill":
        return {"entities": [{"entity_key": "e0", "surface": surface, "entity_kind": "named_person", "reference_form": "full_name", "evidence_refs": [ref]}], "relations": []} if surface and surface in text else {"entities": [], "relations": []}
    return {"observations": []} if lane == "temporal_read" else {"temporal_assertions": []}


def _run_person_unit(unit: Mapping[str, Any], raw_dir: Path | None, sequence: int, live: bool, known_evidence: Mapping[str, Mapping[str, Any]]) -> tuple[dict[str, Any], int]:
    target = unit["target"]; windows = unit.get("windows") or unit.get("person_windows") or []
    p1_prompt = algorithm.person_read_prompt(target, windows)
    if live:
        p1_transport, p1 = semantic_call(lane="person_read", unit_id=str(unit["unit_id"]), prompt=p1_prompt, raw_dir=raw_dir, sequence=sequence); sequence += 1
    else:
        p1_transport = {"classification": "fixture", "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}}; p1 = _fixture_payload("person_read", target, windows)
    p1_validation = algorithm.validate_person_read(p1, windows) if p1 is not None else None
    p2_prompt = algorithm.person_fill_prompt(target, p1_validation or {"valid_observations": []}, windows)
    if live:
        p2_transport, p2 = semantic_call(lane="person_fill", unit_id=str(unit["unit_id"]), prompt=p2_prompt, raw_dir=raw_dir, sequence=sequence); sequence += 1
    else:
        p2_transport = {"classification": "fixture", "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}}; p2 = _fixture_payload("person_fill", target, windows)
    p2_validation = algorithm.validate_person_fill(p2, windows) if p2 is not None else None
    normalization = algorithm.normalize_person_fill(p2_validation or {}, case=unit["case"], windows=windows, known_evidence=known_evidence) if p2_validation is not None else None
    return {
        "unit_id": unit["unit_id"], "group": unit["group"], "target": target, "evidence_windows": windows,
        "person_read": {"prompt": p1_prompt, "transport": p1_transport, "payload": p1, "validation": p1_validation},
        "person_fill": {"prompt": p2_prompt, "transport": p2_transport, "payload": p2, "validation": p2_validation},
        "normalization": normalization,
    }, sequence


def _run_temporal_unit(unit: Mapping[str, Any], raw_dir: Path | None, sequence: int, live: bool) -> tuple[dict[str, Any], int]:
    story = unit["story"]; windows = unit.get("windows") or unit.get("temporal_windows") or []
    t1_prompt = algorithm.temporal_read_prompt(story, windows)
    if live:
        t1_transport, t1 = semantic_call(lane="temporal_read", unit_id=str(unit["unit_id"]), prompt=t1_prompt, raw_dir=raw_dir, sequence=sequence); sequence += 1
    else:
        t1_transport = {"classification": "fixture", "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}}; t1 = {"observations": []}
    t1_validation = algorithm.validate_temporal_read(t1, windows) if t1 is not None else None
    t2_prompt = algorithm.temporal_fill_prompt(story, t1_validation or {"valid_observations": []}, windows)
    if live:
        t2_transport, t2 = semantic_call(lane="temporal_fill", unit_id=str(unit["unit_id"]), prompt=t2_prompt, raw_dir=raw_dir, sequence=sequence); sequence += 1
    else:
        t2_transport = {"classification": "fixture", "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}}; t2 = {"temporal_assertions": []}
    t2_validation = algorithm.validate_temporal_fill(t2, windows) if t2 is not None else None
    normalization = algorithm.normalize_story_temporal(t2_validation or {}, story_id=str(unit["story_id"])) if t2_validation is not None else None
    return {
        "unit_id": unit["unit_id"], "group": unit["group"], "story": story, "category": unit.get("category"), "evidence_windows": windows,
        "temporal_read": {"prompt": t1_prompt, "transport": t1_transport, "payload": t1, "validation": t1_validation},
        "temporal_fill": {"prompt": t2_prompt, "transport": t2_transport, "payload": t2, "validation": t2_validation},
        "normalization": normalization,
    }, sequence


def _failure_stage(result: Mapping[str, Any], lane: str, *, expected: bool) -> str | None:
    read = result.get(f"{lane}_read") or {}; fill = result.get(f"{lane}_fill") or {}
    if (read.get("transport") or {}).get("classification") == "response_truncated" or (fill.get("transport") or {}).get("classification") == "response_truncated":
        return "Fill/schema failure:response_truncated"
    if read.get("payload") is None or fill.get("payload") is None:
        return "Fill/schema failure:response_parse_or_provider"
    rvalidation = read.get("validation") or {}; fvalidation = fill.get("validation") or {}
    observations = rvalidation.get("valid_observations", [])
    rejected_observations = rvalidation.get("rejected_observations", [])
    if not observations:
        if rejected_observations:
            return "Grounding failure"
        return "Read recall failure" if expected else "No evidence available"
    valid_key = "valid_entities" if lane == "person" else "valid_temporal_assertions"
    if not fvalidation.get(valid_key):
        rejected_key = "rejected_entities" if lane == "person" else "rejected_temporal_assertions"
        return "Fill/schema failure" if fvalidation.get(rejected_key) else "Fill/schema failure:empty"
    if lane == "person" and not any(row.get("identity_status") in {"resolved_existing", "resolved_new_candidate"} for row in (result.get("normalization") or {}).get("entities", [])):
        return "Normalization failure" if expected else None
    return None


def _h0a_expected(story_id: str) -> dict[str, Any]:
    anchors = read_json(ROOT / "data/annotation/story-temporal-anchors-h0a.json", {}) or {}
    evidence = read_json(ROOT / "data/annotation/story-temporal-evidence-h0a.json", {}) or {}
    return {
        "anchor": next((row for row in anchors.get("records", []) if row.get("story_id") == story_id), None),
        "evidence": [row for row in evidence.get("records", []) if row.get("story_id") == story_id],
    }


def _compare_temporal(result: Mapping[str, Any]) -> dict[str, Any]:
    story_id = str((result.get("story") or {}).get("story_id") or ""); expected = _h0a_expected(story_id)
    output = (result.get("normalization") or {}).get("temporal_assertions", [])
    compatible = sum(1 for row in output if (row.get("h0a") or {}).get("status") == "compatible")
    conflicts = sum(1 for row in output if (row.get("h0a") or {}).get("status") == "conflict")
    excluded = [row for row in output if not row.get("scene_constraint_candidate")]
    return {
        "story_id": story_id, "h0a_precision": (expected.get("anchor") or {}).get("precision"),
        "h0a_compatible": compatible, "h0a_conflicts": conflicts,
        "later_outcome_correctly_excluded": all(not row.get("scene_constraint_candidate") for row in output if row.get("temporal_role") == "later_outcome"),
        "quoted_or_background_correctly_excluded": all(not row.get("scene_constraint_candidate") for row in output if row.get("temporal_role") in {"quoted_precedent", "background_context"}),
        "excluded_non_scene_count": len(excluded),
    }


def metrics(person_results: Sequence[Mapping[str, Any]], temporal_results: Sequence[Mapping[str, Any]], heldout_results: Sequence[Mapping[str, Any]], preflight_record: Mapping[str, Any], *, live: bool) -> dict[str, Any]:
    all_results = list(person_results) + list(temporal_results)
    for row in heldout_results:
        all_results.extend([row["person"], row["temporal"]])
    transports: list[Mapping[str, Any]] = []
    for result in all_results:
        for lane in ("person_read", "person_fill", "temporal_read", "temporal_fill"):
            if isinstance(result.get(lane), Mapping):
                transports.append((result[lane].get("transport") or {}))
    token_usage = {key: sum(int((row.get("usage") or {}).get(key) or 0) for row in transports) for key in ("prompt_tokens", "completion_tokens", "total_tokens")}
    latencies = [float(row["elapsed_seconds"]) for row in transports if row.get("status") == "response" and row.get("elapsed_seconds") is not None]
    truncations = sum(row.get("classification") == "response_truncated" for row in transports)
    person_valid_obs = person_grounding_rejections = person_valid_entities = person_valid_relations = person_fill_rejections = unsupported_relations = resolved_existing = resolved_new = unresolved = 0
    temporal_obs = temporal_grounding_rejections = temporal_cards = temporal_fill_rejections = h0a_compatible = h0a_conflicts = later_excluded = quoted_excluded = 0
    failure_counts: dict[str, int] = {}
    for result in list(person_results) + [row["person"] for row in heldout_results]:
        person_valid_obs += len(((result.get("person_read") or {}).get("validation") or {}).get("valid_observations", []))
        person_grounding_rejections += len(((result.get("person_read") or {}).get("validation") or {}).get("rejected_observations", []))
        person_valid_entities += len(((result.get("person_fill") or {}).get("validation") or {}).get("valid_entities", []))
        person_valid_relations += len(((result.get("person_fill") or {}).get("validation") or {}).get("valid_relations", []))
        fill_validation = ((result.get("person_fill") or {}).get("validation") or {})
        unsupported_relations += len(fill_validation.get("rejected_relations", []))
        person_fill_rejections += len(fill_validation.get("rejected_entities", [])) + len(fill_validation.get("rejected_relations", []))
        statuses = [row.get("identity_status") for row in (result.get("normalization") or {}).get("entities", [])]
        resolved_existing += statuses.count("resolved_existing"); resolved_new += statuses.count("resolved_new_candidate")
        unresolved += sum(status in {"unresolved", "ambiguous", "not_person", "not_single_person"} for status in statuses)
        expected = result.get("group") == "person_regression" and str((result.get("target") or {}).get("surface")) not in {"宣", "譽"}
        failure = _failure_stage(result, "person", expected=expected)
        if failure:
            failure_counts[failure] = failure_counts.get(failure, 0) + 1
    temporal_comparisons = []
    for result in list(temporal_results) + [row["temporal"] for row in heldout_results]:
        temporal_obs += len(((result.get("temporal_read") or {}).get("validation") or {}).get("valid_observations", []))
        temporal_grounding_rejections += len(((result.get("temporal_read") or {}).get("validation") or {}).get("rejected_observations", []))
        temporal_fill_validation = ((result.get("temporal_fill") or {}).get("validation") or {})
        temporal_cards += len(temporal_fill_validation.get("valid_temporal_assertions", []))
        temporal_fill_rejections += len(temporal_fill_validation.get("rejected_temporal_assertions", []))
        comparison = _compare_temporal(result); temporal_comparisons.append(comparison)
        h0a_compatible += comparison["h0a_compatible"]; h0a_conflicts += comparison["h0a_conflicts"]
        later_excluded += int(comparison["later_outcome_correctly_excluded"]); quoted_excluded += int(comparison["quoted_or_background_correctly_excluded"])
        expected = result.get("group") == "temporal_regression" and result.get("category") in {"reign_bounded", "event_bounded", "later_outcome_trap", "quoted_precedent_trap"}
        failure = _failure_stage(result, "temporal", expected=expected)
        if failure:
            failure_counts[failure] = failure_counts.get(failure, 0) + 1
    prompt_tokens = [int((row.get("usage") or {}).get("prompt_tokens") or 0) for row in transports if row.get("status") == "response"]
    heldout_calls = sum(1 for row in heldout_results for branch in (row["person"], row["temporal"]) for lane in ("person_read", "person_fill", "temporal_read", "temporal_fill") if isinstance(branch.get(lane), Mapping))
    # Each branch has only its own two lanes, so the expression above counts 20.
    return {
        "live": live, "preflight": preflight_record, "semantic_calls": len(transports), "heldout_semantic_calls": heldout_calls,
        "token_usage": token_usage, "median_prompt_tokens": statistics.median(prompt_tokens) if prompt_tokens else 0,
        "maximum_prompt_tokens": max(prompt_tokens or [0]), "median_latency_seconds": statistics.median(latencies) if latencies else None,
        "maximum_latency_seconds": max(latencies) if latencies else None, "response_truncated": truncations,
        "person": {"validated_observations": person_valid_obs, "grounding_rejections": person_grounding_rejections, "valid_entities": person_valid_entities, "valid_relations": person_valid_relations, "fill_item_rejections": person_fill_rejections, "unsupported_or_rejected_relations": unsupported_relations, "resolved_existing": resolved_existing, "resolved_new_candidate": resolved_new, "unresolved": unresolved},
        "temporal": {"validated_observations": temporal_obs, "grounding_rejections": temporal_grounding_rejections, "valid_temporal_cards": temporal_cards, "fill_item_rejections": temporal_fill_rejections, "h0a_compatible": h0a_compatible, "h0a_conflicts": h0a_conflicts, "later_outcome_exclusion_checks_passed": later_excluded, "quoted_background_exclusion_checks_passed": quoted_excluded},
        "failure_stage_counts": failure_counts, "temporal_comparisons": temporal_comparisons,
        "no_search_calls": True, "no_retries": True, "no_follow_up": True, "no_frontier_expansion": True, "canonical_write_back": False,
    }


def evaluation_audit(
    person_results: Sequence[Mapping[str, Any]],
    temporal_results: Sequence[Mapping[str, Any]],
    heldout_results: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Audit target-specific outcomes without changing live projections."""

    person_rows: list[dict[str, Any]] = []
    anomalies: list[dict[str, Any]] = []
    fill_without_grounded = 0
    all_person = list(person_results) + [row["person"] for row in heldout_results]
    for result in all_person:
        target = str((result.get("target") or {}).get("surface") or "")
        entities = (result.get("normalization") or {}).get("entities", [])
        target_entities = [row for row in entities if row.get("surface") == target]
        person_rows.append({
            "unit_id": result.get("unit_id"), "group": result.get("group"), "target_surface": target,
            "target_identity_statuses": [row.get("identity_status") for row in target_entities],
            "target_resolved_person_ids": sorted({str(row.get("resolved_person_id")) for row in target_entities if row.get("resolved_person_id")}),
            "validated_read_observations": len(((result.get("person_read") or {}).get("validation") or {}).get("valid_observations", [])),
            "read_item_rejections": len(((result.get("person_read") or {}).get("validation") or {}).get("rejected_observations", [])),
            "valid_fill_entities": len(((result.get("person_fill") or {}).get("validation") or {}).get("valid_entities", [])),
            "valid_fill_relations": len(((result.get("person_fill") or {}).get("validation") or {}).get("valid_relations", [])),
        })
        if not ((result.get("person_read") or {}).get("validation") or {}).get("valid_observations") and ((result.get("person_fill") or {}).get("validation") or {}).get("valid_entities"):
            fill_without_grounded += 1
        for entity in entities:
            if entity.get("identity_status") in {"not_person", "not_single_person"} and entity.get("resolved_person_id"):
                anomalies.append({"unit_id": result.get("unit_id"), "kind": "non_person_has_resolved_person_id", "surface": entity.get("surface"), "resolved_person_id": entity.get("resolved_person_id")})
        for relation in (result.get("normalization") or {}).get("relations", []):
            if relation.get("relation_class") != "identity_name" and relation.get("person_a") and relation.get("person_a") == relation.get("person_b"):
                anomalies.append({"unit_id": result.get("unit_id"), "kind": "relation_collapsed_to_same_person", "relation_id": relation.get("relation_id"), "person_id": relation.get("person_a")})

    temporal_rows: list[dict[str, Any]] = []
    all_temporal = list(temporal_results) + [row["temporal"] for row in heldout_results]
    for result in all_temporal:
        story_id = str((result.get("story") or {}).get("story_id") or "")
        anchor = (_h0a_expected(story_id).get("anchor") or {})
        declared = result.get("category")
        normalized = (result.get("normalization") or {}).get("temporal_assertions", [])
        temporal_rows.append({
            "unit_id": result.get("unit_id"), "group": result.get("group"), "story_id": story_id,
            "declared_category": declared, "actual_h0a_precision": anchor.get("precision"),
            "selection_category_matches_h0a": True if declared not in {"reign_bounded", "event_bounded"} else anchor.get("precision") == declared,
            "validated_read_observations": len(((result.get("temporal_read") or {}).get("validation") or {}).get("valid_observations", [])),
            "read_item_rejections": len(((result.get("temporal_read") or {}).get("validation") or {}).get("rejected_observations", [])),
            "valid_fill_assertions": len(((result.get("temporal_fill") or {}).get("validation") or {}).get("valid_temporal_assertions", [])),
            "scene_constraint_candidates": sum(1 for row in normalized if row.get("scene_constraint_candidate")),
            "excluded_non_scene": sum(1 for row in normalized if not row.get("scene_constraint_candidate")),
        })

    person_by_unit = {row["unit_id"]: row for row in person_rows}
    temporal_by_unit = {row["unit_id"]: row for row in temporal_rows}
    heldout = [{
        "unit_id": row["unit_id"], "story_id": row["story_id"], "target_surface": row["target_surface"], "category": row["category"],
        "person": person_by_unit.get(row["person"]["unit_id"]), "temporal": temporal_by_unit.get(row["temporal"]["unit_id"]),
    } for row in heldout_results]
    return {
        "person": person_rows,
        "temporal": temporal_rows,
        "heldout": heldout,
        "normalization_anomalies": anomalies,
        "fill_produced_items_without_grounded_read_observation": fill_without_grounded,
        "selection_errors": [row for row in temporal_rows if not row["selection_category_matches_h0a"]],
        "evaluation_only": True,
        "canonical_write_back": False,
    }


def run(selection: Mapping[str, Any], *, live: bool, run_id: str) -> dict[str, Any]:
    person_units, temporal_units, heldout_units = build_units(selection)
    cases, _, _ = hardening.load_inputs(); previous = consolidation.load_previous_findings()
    out = OUT / ("live" if live else "offline-replay") / run_id
    raw_dir = out / "raw-api"; raw_dir.mkdir(parents=True, exist_ok=True)
    preflight_record = preflight() if live else {"status": "not_executed_offline", "api_calls": 0}
    write_json(out / "preflight.json", preflight_record)
    if live and preflight_record.get("status") != "reachable":
        write_json(out / "manifest.json", {"status": "live_network_unavailable", "selection_hash": stable_hash(selection), "semantic_calls": 0, "canonical_write_back": False})
        raise RuntimeError("live_network_unavailable")
    sequence = 1; person_results = []; temporal_results = []; heldout_results = []
    for unit in person_units:
        result, sequence = _run_person_unit(unit, raw_dir, sequence, live, previous["evidence_refs"]); person_results.append(result)
    for unit in temporal_units:
        result, sequence = _run_temporal_unit(unit, raw_dir, sequence, live); temporal_results.append(result)
    heldout_start = sequence
    for unit in heldout_units:
        person, sequence = _run_person_unit(unit, raw_dir, sequence, live, previous["evidence_refs"])
        temporal, sequence = _run_temporal_unit(unit, raw_dir, sequence, live)
        heldout_results.append({"unit_id": unit["unit_id"], "story_id": unit["story_id"], "target_surface": unit["target"]["surface"], "category": unit["category"], "person": person, "temporal": temporal})
    heldout_call_count = sequence - heldout_start
    if live and heldout_call_count != 20:
        raise RuntimeError(f"heldout_call_count_mismatch:{heldout_call_count}")
    summary = metrics(person_results, temporal_results, heldout_results, preflight_record, live=live)
    audit = evaluation_audit(person_results, temporal_results, heldout_results)
    old_metrics = read_json(ROOT / "data/generated/hng2-consolidation/live/20260825T-HNG2-C-01/metrics.json", {}) or {}
    comparison = {
        "old_one_pass": {"response_truncated": old_metrics.get("response_truncated_count"), "fill_item_rejections": sum(int(old_metrics.get(key) or 0) for key in ("rejected_entities", "rejected_relations", "rejected_temporal_assertions")), "rejected_entities": old_metrics.get("rejected_entities"), "rejected_relations": old_metrics.get("rejected_relations"), "maximum_prompt_tokens": old_metrics.get("maximum_prompt_tokens")},
        "split": {"response_truncated": summary["response_truncated"], "fill_item_rejections": summary["person"]["fill_item_rejections"] + summary["temporal"]["fill_item_rejections"], "unsupported_or_rejected_relations": summary["person"]["unsupported_or_rejected_relations"], "maximum_prompt_tokens": summary["maximum_prompt_tokens"]},
    }
    write_json(out / "person-results.json", person_results)
    write_json(out / "temporal-results.json", temporal_results)
    write_json(out / "heldout-results.json", heldout_results)
    write_json(out / "comparison-with-hng2-c.json", comparison)
    write_json(out / "evaluation-audit.json", audit)
    write_json(out / "metrics.json", summary)
    write_json(out / "manifest.json", {
        "stage": "hng2-c1-two-stage-read-fill-validation", "run_id": run_id, "status": "complete",
        "selection_hash": stable_hash(selection), "algorithm_version": RUN_VERSION,
        "semantic_call_policy": "P1+P2 per Person unit; T1+T2 per Story unit; no retries",
        "heldout_semantic_calls": heldout_call_count, "raw_api_immutable": True,
        "prior_artifacts_immutable": True, "h0a_write_back": False, "canonical_write_back": False,
    })
    return {"run_id": run_id, "output": str(out), "metrics": summary, "evaluation_audit": audit, "heldout": heldout_results, "comparison": comparison}


def summarize_existing_run(run_id: str) -> dict[str, Any]:
    out = OUT / "live" / run_id
    person_results = read_json(out / "person-results.json", []) or []
    temporal_results = read_json(out / "temporal-results.json", []) or []
    heldout_results = read_json(out / "heldout-results.json", []) or []
    if not person_results or not temporal_results or not heldout_results:
        raise RuntimeError(f"live_run_incomplete:{run_id}")
    audit = evaluation_audit(person_results, temporal_results, heldout_results)
    # Preserve the exact global selection that governed this completed run
    # before any later implementation-bug correction changes defaults.
    frozen_selection = read_json(OUT / "selection.json", {}) or {}
    write_json(out / "live-selection.json", frozen_selection)
    write_json(out / "evaluation-audit.json", audit)
    manifest = read_json(out / "manifest.json", {}) or {}
    manifest["evaluation_audit_recomputed_without_api"] = True
    manifest["raw_api_immutable"] = True
    write_json(out / "manifest.json", manifest)
    return audit


def run_temporal_correction(selection: Mapping[str, Any], story_id: str, run_id: str) -> dict[str, Any]:
    """Run one corrected frozen temporal regression after a selection bug.

    It never reruns the five held-out pairs or any valid Person result.
    """

    _, temporal_units, _ = build_units(selection)
    unit = next((row for row in temporal_units if row.get("story_id") == story_id), None)
    if unit is None:
        raise RuntimeError(f"temporal_regression_not_selected:{story_id}")
    out = OUT / "live-correction" / run_id
    raw_dir = out / "raw-api"; raw_dir.mkdir(parents=True, exist_ok=True)
    preflight_record = preflight(); write_json(out / "preflight.json", preflight_record)
    if preflight_record.get("status") != "reachable":
        raise RuntimeError("live_network_unavailable")
    result, sequence = _run_temporal_unit(unit, raw_dir, 1, True)
    if sequence != 3:
        raise RuntimeError("temporal_correction_call_count_mismatch")
    write_json(out / "live-selection.json", {"story_id": story_id, "unit_id": unit["unit_id"], "category": unit.get("category"), "source_refs": [row.get("ref") for row in unit.get("windows", [])]})
    write_json(out / "temporal-result.json", result)
    write_json(out / "temporal-comparison.json", _compare_temporal(result))
    write_json(out / "manifest.json", {
        "stage": "hng2-c1-temporal-selection-bug-correction", "run_id": run_id,
        "reason": "original declared reign-bounded Story lacked a current H0A anchor",
        "semantic_calls": 2, "heldout_calls": 0, "person_calls": 0,
        "no_valid_result_rerun": True, "raw_api_immutable": True,
        "h0a_write_back": False, "canonical_write_back": False,
    })
    return {"output": str(out), "result": result, "comparison": _compare_temporal(result)}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prepare", action="store_true", help="freeze selection only; no API")
    parser.add_argument("--offline-replay", action="store_true", help="fixture plumbing replay; no API")
    parser.add_argument("--live", action="store_true", help="approved-network live validation")
    parser.add_argument("--run-id", default=None)
    parser.add_argument("--summarize-run", default=None, metavar="RUN_ID", help="recompute evaluation audit from stored cards; no API")
    parser.add_argument("--live-temporal-correction", default=None, metavar="STORY_ID", help="run one corrected frozen H0A temporal regression only")
    args = parser.parse_args()
    selection = ensure_selection()
    if args.summarize_run:
        audit = summarize_existing_run(args.summarize_run)
        print(json.dumps({"run_id": args.summarize_run, "api_calls": 0, "selection_errors": audit["selection_errors"], "normalization_anomalies": audit["normalization_anomalies"]}, ensure_ascii=False, indent=2))
        return 0
    if args.live_temporal_correction:
        run_id = args.run_id or dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        result = run_temporal_correction(selection, args.live_temporal_correction, run_id)
        print(json.dumps({"run_id": run_id, "output": result["output"], "comparison": result["comparison"]}, ensure_ascii=False, indent=2))
        return 0
    if args.prepare or (not args.live and not args.offline_replay):
        print(json.dumps(selection, ensure_ascii=False, indent=2)); return 0
    run_id = args.run_id or (dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ") if args.live else "deterministic")
    result = run(selection, live=args.live, run_id=run_id)
    print(json.dumps({"run_id": run_id, "output": result["output"], "metrics": result["metrics"]}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
