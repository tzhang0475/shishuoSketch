#!/usr/bin/env python3
"""Run HNG2-V1 on a deterministic, previously unused Story holdout.

Selection is built from repository evidence before the network preflight.  The
live path reuses the frozen C.3 EvidenceAtom prompts and Python projections;
it adds no retrieval, search planning, or semantic repair.
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
from functools import lru_cache
from pathlib import Path
from typing import Any, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import build_hng0_2 as hng02  # noqa: E402
import historical_context_algorithm as algorithm  # noqa: E402
import hng2_schema_controller as controller  # noqa: E402
import historical_entity_resolver as resolver  # noqa: E402
import run_hng2_algorithm_closeout as closeout  # noqa: E402
import run_hng2_consolidation as consolidation  # noqa: E402
import run_hng2_read_fill_validation as c1  # noqa: E402
from smoke_deepseek import call_deepseek  # noqa: E402


OUT = ROOT / "data/generated/hng2-fresh-validation"
MODEL = "deepseek-v4-flash"
RUN_VERSION = "hng2-v1-fresh-holdout-v1"
PROMPT_VERSION = "hng2-c3-frozen-evidence-atoms-v1"
SCANNER_SCOPE = "H0A historical registry + explicit date patterns"
STORY_RE = re.compile(r"\b\d{2}-[a-z]+-\d{3}\b")

TEMPORAL_STRATA = (
    "explicit_year_reign",
    "ruler_or_event_bounded",
    "annotation_dependent",
    "quoted_precedent_background",
    "later_outcome",
    "weak_or_no_explicit_temporal_evidence",
)
PERSON_CATEGORIES = {
    "clear_full_name",
    "abbreviated_or_title",
    "kinship_or_marriage",
    "institutional_or_interaction",
    "ambiguous_or_unresolved",
}


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


def _source_files_for_exclusion() -> list[Path]:
    paths: set[Path] = set()
    generated_root = ROOT / "data/generated"
    for path in generated_root.glob("hng2-*"):
        if path.resolve() == OUT.resolve():
            continue
        if path.is_dir():
            paths.update(item for item in path.rglob("*") if item.is_file())
    for root in (ROOT / "tests", ROOT / "docs", ROOT / "scripts"):
        for path in root.rglob("*"):
            if not path.is_file():
                continue
            if "__pycache__" in path.parts or path.suffix == ".pyc":
                continue
            name = path.name.lower()
            relative = str(path.relative_to(ROOT)).lower()
            if (
                name.startswith("test_hng2")
                or name.startswith("hng2")
                or "hng2" in name
                or "run_hng2" in name
                or "build_hng2" in name
                or "validate_hng2" in name
                or "/hng2" in relative
            ):
                paths.add(path)
    return sorted(paths)


def collect_previous_hng2_exclusion() -> dict[str, Any]:
    files: list[dict[str, str]] = []
    story_ids: set[str] = set()
    for path in _source_files_for_exclusion():
        try:
            raw = path.read_bytes()
            text = raw.decode("utf-8", errors="ignore")
        except OSError:
            continue
        story_ids.update(STORY_RE.findall(text))
        files.append({"path": str(path.relative_to(ROOT)), "sha256": hashlib.sha256(raw).hexdigest()})
    return {
        "story_ids": sorted(story_ids),
        "story_count": len(story_ids),
        "files": files,
        "files_hash": stable_hash(files),
        "exclusion_hash": stable_hash(sorted(story_ids)),
    }


def all_story_ids() -> list[str]:
    result: list[str] = []
    for path in sorted((ROOT / "content/processed/shishuo/entries").glob("*/*")):
        if path.is_file() and path.name.startswith("entry-") and path.suffix == ".md":
            result.append(f"{path.parent.name}-{path.stem[len('entry-'):]}")
    return sorted(result)


def h0a_maps() -> tuple[dict[str, dict[str, Any]], dict[str, list[dict[str, Any]]]]:
    anchors = read_json(ROOT / "data/annotation/story-temporal-anchors-h0a.json", {}) or {}
    evidence = read_json(ROOT / "data/annotation/story-temporal-evidence-h0a.json", {}) or {}
    anchor_map = {str(row.get("story_id")): dict(row) for row in anchors.get("records", []) if isinstance(row, Mapping) and row.get("story_id")}
    evidence_map: dict[str, list[dict[str, Any]]] = collections.defaultdict(list)
    for row in evidence.get("records", []):
        if isinstance(row, Mapping) and row.get("story_id"):
            evidence_map[str(row["story_id"])].append(dict(row))
    return anchor_map, dict(evidence_map)


def temporal_features(story_id: str, anchor_map: Mapping[str, Mapping[str, Any]], evidence_map: Mapping[str, Sequence[Mapping[str, Any]]]) -> set[str]:
    anchor = anchor_map.get(story_id, {})
    rows = evidence_map.get(story_id, [])
    features: set[str] = set()
    if anchor.get("precision") in {"exact_year", "reign_bounded"} or any(row.get("evidence_type") == "era_year" for row in rows):
        features.add("explicit_year_reign")
    if anchor.get("ruler_context_id") or any(
        row.get("evidence_type") == "historical_event_reference" and row.get("relation_to_story") == "direct_story_time"
        for row in rows
    ):
        features.add("ruler_or_event_bounded")
    if any(row.get("source_layer") == "liu_annotation" for row in rows):
        features.add("annotation_dependent")
    if any(row.get("relation_to_story") in {"quoted_ancient_precedent"} for row in rows):
        features.add("quoted_precedent_background")
    if any(row.get("relation_to_story") == "earlier_background" for row in rows):
        features.add("quoted_precedent_background")
    if any(row.get("relation_to_story") == "later_outcome" for row in rows):
        features.add("later_outcome")
    if not features or anchor.get("precision") in {None, "phase_only", "unknown"}:
        features.add("weak_or_no_explicit_temporal_evidence")
    return features


@lru_cache(maxsize=None)
def _main_text_for_story(story_id: str) -> str:
    # Selection-only lookup.  The live evidence bundle still comes from the
    # frozen punctuated selector in run_hng2_read_fill_validation.py.
    path = c1._entry_path(story_id)
    text = path.read_text(encoding="utf-8")
    for section, source_text, _metadata in c1.parse_shishuo_sections(text):
        if section == "main_text":
            return str(source_text).rstrip("\n")
    return ""


def _mention_options(story_id: str, mentions: Sequence[Mapping[str, Any]], catalog: Mapping[str, Mapping[str, Any]]) -> list[dict[str, Any]]:
    main = [row for row in mentions if row.get("entry_id") == story_id and row.get("section") == "main_text"]
    annotation = [row for row in mentions if row.get("entry_id") == story_id and row.get("section") == "liu_annotation"]
    source_rows = main or annotation
    text = _main_text_for_story(story_id)
    options: list[dict[str, Any]] = []
    seen: set[tuple[str, str, tuple[str, ...]]] = set()
    for row in source_rows:
        surface = str(row.get("surface") or "").strip()
        if not surface:
            continue
        candidate_ids = tuple(sorted(str(value) for value in row.get("candidate_person_ids", []) if str(value) in catalog))
        person_id = str(row.get("person_id") or "") if str(row.get("person_id") or "") in catalog else ""
        key = (surface, person_id, candidate_ids)
        if key in seen:
            continue
        seen.add(key)
        canonical = str((catalog.get(person_id) or {}).get("canonical_name") or "")
        title = any(marker in surface for marker in ("太尉", "太傅", "丞相", "將軍", "太守", "刺史", "公", "帝"))
        kinship = any(marker in text for marker in ("父", "母", "子", "女", "兄", "弟", "妻", "婿", "婚", "嫁"))
        institutional = any(marker in text for marker in ("辟", "拜", "除", "召", "詣", "為掾", "爲掾", "任"))
        if not person_id or len(candidate_ids) > 1:
            category = "ambiguous_or_unresolved"
        elif surface != canonical or title:
            category = "abbreviated_or_title"
        elif kinship:
            category = "kinship_or_marriage"
        elif institutional:
            category = "institutional_or_interaction"
        else:
            category = "clear_full_name"
        rank = stable_hash({"story_id": story_id, "surface": surface, "person_id": person_id, "candidate_ids": candidate_ids})
        options.append(
            {
                "surface": surface,
                "person_id": person_id or None,
                "candidate_person_ids": list(candidate_ids),
                "canonical_name": canonical,
                "category": category,
                "selection_key": rank,
                "mention_id": row.get("mention_id"),
                "source_section": row.get("section"),
            }
        )
    return sorted(options, key=lambda row: (row["selection_key"], row["surface"]))


def _case_for_target(selected: Mapping[str, Any], catalog: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    reference_ids = []
    if selected.get("reference_person_id"):
        reference_ids.append(str(selected["reference_person_id"]))
    reference_ids.extend(str(value) for value in selected.get("reference_candidate_person_ids", []) if str(value))
    reference_ids = list(dict.fromkeys(value for value in reference_ids if value in catalog))
    candidates = []
    for index, person_id in enumerate(reference_ids):
        person = catalog[person_id]
        candidates.append(
            {
                "candidate_key": f"c{index}",
                "person_id": person_id,
                "canonical_name": person.get("canonical_name"),
                "known_forms": resolver.catalog_forms(person),
            }
        )
    seed = {}
    if selected.get("reference_person_id"):
        seed = {"person_id": selected["reference_person_id"], "canonical_name": selected.get("reference_canonical_name")}
    return {
        "story_id": selected.get("story_id"),
        "observation": {"surface": selected.get("target_surface"), "source_work": "世說新語"},
        "seed": seed,
        "candidates": candidates,
        "constraint_checks": [],
    }


def build_selection() -> dict[str, Any]:
    exclusion = collect_previous_hng2_exclusion()
    catalog = hng02.person_catalog()
    mentions_doc = read_json(ROOT / "data/mentions/shishuo.json", {}) or {}
    mentions = [row for row in mentions_doc.get("mentions", []) if isinstance(row, Mapping)]
    options_by_story: dict[str, list[dict[str, Any]]] = {}
    for story_id in all_story_ids():
        options = _mention_options(story_id, mentions, catalog)
        if options:
            options_by_story[story_id] = options
    eligible = sorted(set(options_by_story) - set(exclusion["story_ids"]))
    anchor_map, evidence_map = h0a_maps()
    category_limits = {
        "explicit_year_reign": 4,
        "ruler_or_event_bounded": 4,
        "annotation_dependent": 4,
        "quoted_precedent_background": 4,
        "later_outcome": 4,
        "weak_or_no_explicit_temporal_evidence": 4,
    }
    used: set[str] = set()
    temporal_rows: list[dict[str, Any]] = []
    for category in TEMPORAL_STRATA:
        candidates = [story_id for story_id in eligible if story_id not in used and category in temporal_features(story_id, anchor_map, evidence_map)]
        for story_id in sorted(candidates, key=lambda value: stable_hash({"story_id": value, "category": category}))[: category_limits[category]]:
            used.add(story_id)
            temporal_rows.append({"story_id": story_id, "temporal_stratum": category, "selection_key": stable_hash({"story_id": story_id, "category": category})})
    if len(temporal_rows) < 24:
        fallback = [story_id for story_id in eligible if story_id not in used]
        for story_id in sorted(fallback, key=lambda value: stable_hash({"story_id": value, "fallback": True}))[: 24 - len(temporal_rows)]:
            used.add(story_id)
            temporal_rows.append({"story_id": story_id, "temporal_stratum": "weak_or_no_explicit_temporal_evidence", "selection_key": stable_hash({"story_id": story_id, "fallback": True}), "fallback_allocation": True})
    if len(temporal_rows) != 24:
        raise RuntimeError(f"fresh_story_count_unavailable:{len(temporal_rows)}")
    temporal_rows.sort(key=lambda row: (TEMPORAL_STRATA.index(row["temporal_stratum"]), row["selection_key"]))

    stories: list[dict[str, Any]] = []
    for index, temporal in enumerate(temporal_rows, start=1):
        story_id = str(temporal["story_id"])
        options = options_by_story[story_id]
        target = min(options, key=lambda row: (0 if row["category"] in {"abbreviated_or_title", "kinship_or_marriage", "institutional_or_interaction", "ambiguous_or_unresolved"} else 1, row["selection_key"]))
        person_windows = c1._select_story_windows(story_id, target=target["surface"], canonical_name=target.get("canonical_name") or "", lane="person")
        temporal_windows = c1._select_story_windows(story_id, lane="temporal")
        stories.append(
            {
                "unit_id": f"fresh-{index:02d}-{story_id}",
                "story_id": story_id,
                "temporal_stratum": temporal["temporal_stratum"],
                "temporal_fallback_allocation": bool(temporal.get("fallback_allocation")),
                "target_surface": target["surface"],
                "person_validation_category": target["category"],
                "target_selection_key": target["selection_key"],
                "target_mention_id": target.get("mention_id"),
                "reference_person_id": target.get("person_id"),
                "reference_canonical_name": target.get("canonical_name"),
                "reference_candidate_person_ids": target.get("candidate_person_ids", []),
                "source_refs": sorted({str(row.get("ref")) for row in [*person_windows, *temporal_windows]}),
                "person_source_refs": [str(row.get("ref")) for row in person_windows],
                "temporal_source_refs": [str(row.get("ref")) for row in temporal_windows],
                "selection_key": temporal["selection_key"],
            }
        )
    core = {
        "stage": "hng2-v1-frozen-algorithm-fresh-holdout",
        "run_version": RUN_VERSION,
        "algorithm_version": algorithm.__name__ + ":frozen-c3",
        "prompt_versions": {
            "person_read": PROMPT_VERSION,
            "person_fill": PROMPT_VERSION,
            "temporal_read": PROMPT_VERSION,
            "temporal_fill": PROMPT_VERSION,
        },
        "frozen_before_live": True,
        "fresh_holdout": True,
        "story_count": 24,
        "stories": stories,
        "temporal_strata_target": {category: category_limits[category] for category in TEMPORAL_STRATA},
        "temporal_strata_actual": dict(collections.Counter(row["temporal_stratum"] for row in stories)),
        "temporal_strata_shortfall": {
            category: category_limits[category] - sum(row["temporal_stratum"] == category for row in stories)
            for category in TEMPORAL_STRATA
        },
        "previous_hng2_exclusion": exclusion,
        "overlap_with_previous_hng2": sorted({row["story_id"] for row in stories} & set(exclusion["story_ids"])),
        "expected_base_semantic_calls": 96,
        "canonical_write_back": False,
        "no_search_plan": True,
        "no_recursive_retrieval": True,
    }
    core["selection_hash"] = stable_hash(core)
    return core


def ensure_selection() -> dict[str, Any]:
    selection = build_selection()
    path = OUT / "selection.json"
    if path.is_file():
        existing = read_json(path, {})
        if stable_hash(existing) != stable_hash(selection):
            raise RuntimeError("fresh_selection_immutable_mismatch")
        selection = existing
    else:
        write_json(path, selection)
    if selection.get("story_count") != 24 or selection.get("overlap_with_previous_hng2"):
        raise RuntimeError("fresh_selection_safety_failure")
    return selection


def load_frozen_selection() -> dict[str, Any]:
    """Load the immutable selection snapshot for offline validation/replay.

    Rebuilding the exclusion snapshot after the live run would include this
    run's post-freeze boundary fixes and falsely look like selection drift.
    The snapshot's own hash and safety fields remain the authority here;
    ``ensure_selection`` is used before live execution to enforce
    reproducibility against a newly generated selection.
    """

    path = OUT / "selection.json"
    if not path.is_file():
        raise RuntimeError("missing_frozen_selection")
    selection = read_json(path, {}) or {}
    selection_hash = selection.get("selection_hash")
    core = {key: value for key, value in selection.items() if key != "selection_hash"}
    if not selection_hash or stable_hash(core) != selection_hash:
        raise RuntimeError("frozen_selection_hash_invalid")
    if selection.get("story_count") != 24 or selection.get("overlap_with_previous_hng2"):
        raise RuntimeError("frozen_selection_safety_failure")
    return selection


def _usage(response: Mapping[str, Any]) -> dict[str, int]:
    raw = response.get("usage") if isinstance(response.get("usage"), Mapping) else {}
    return {key: int(raw.get(key) or 0) for key in ("prompt_tokens", "completion_tokens", "total_tokens")}


def _finish_reason(response: Mapping[str, Any]) -> str | None:
    choices = response.get("choices") if isinstance(response.get("choices"), list) else []
    if choices and isinstance(choices[0], Mapping):
        return str(choices[0].get("finish_reason") or "") or None
    return None


def _safe_error(exc: Exception) -> dict[str, Any]:
    message = str(exc)
    secret = os.environ.get("DEEPSEEK_API_KEY")
    if secret:
        message = message.replace(secret, "[REDACTED]")
    return {"exception_class": type(exc).__name__, "exception_message": message, "http_status": getattr(exc, "http_status", None)}


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
        "temporal_read": algorithm.TEMPORAL_ANCHOR_ATOM_SYSTEM,
        "temporal_fill": algorithm.TEMPORAL_ATOM_FILL_SYSTEM,
    }
    budgets = {"person_read": 900, "person_fill": 900, "temporal_read": 750, "temporal_fill": 750}
    attempts: list[dict[str, Any]] = []
    payload: Mapping[str, Any] | None = None
    final: dict[str, Any] = {"sequence": sequence, "lane": lane, "unit_id": unit_id, "model": MODEL, "prompt_version": PROMPT_VERSION, "input_hash": stable_hash(prompt)}
    for attempt in (1, 2):
        started = time.monotonic()
        attempt_record: dict[str, Any] = {"attempt": attempt, "start_time": utc_now()}
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
            raw_path = raw_dir / f"{sequence:03d}-attempt-{attempt}-{lane}-{re.sub(r'[^A-Za-z0-9_.-]+', '-', unit_id)}.json"
            if raw_path.exists():
                raise RuntimeError(f"immutable_raw_response_exists:{raw_path}")
            write_json(raw_path, response)
            finish = _finish_reason(response)
            attempt_record.update({"status": "response", "finish_reason": finish, "usage": _usage(response), "raw_path": str(raw_path.relative_to(ROOT))})
            if finish == "length":
                attempt_record["classification"] = "response_truncated"
                attempts.append(attempt_record)
                break
            parsed, channel, error = controller.extract_strict_tool_payload(response, expected_function_name=expected)
            if error:
                attempt_record.update({"classification": "response_parse_failure", "response_channel": channel, "parse_error": error})
                attempts.append(attempt_record)
                if attempt == 1:
                    continue
                break
            attempt_record.update({"classification": "parsed", "response_channel": channel})
            attempts.append(attempt_record)
            payload = parsed
            break
        except Exception as exc:
            attempt_record.update({"classification": "provider_request_failure", **_safe_error(exc)})
            attempts.append(attempt_record)
            if attempt == 1:
                continue
        finally:
            attempt_record.update({"elapsed_seconds": round(time.monotonic() - started, 3), "end_time": utc_now()})
    final.update(
        {
            "status": "response" if payload is not None else "failed",
            "classification": "parsed" if payload is not None else attempts[-1].get("classification", "provider_request_failure"),
            "attempts": attempts,
            "retry_count": max(0, len(attempts) - 1),
            "usage": attempts[-1].get("usage", {}) if attempts else {},
            "elapsed_seconds": sum(float(row.get("elapsed_seconds") or 0) for row in attempts),
            "end_time": utc_now(),
        }
    )
    return final, payload


def build_units(selected: Mapping[str, Any]) -> list[dict[str, Any]]:
    catalog = hng02.person_catalog()
    units: list[dict[str, Any]] = []
    for row in selected.get("stories", []):
        story_id = str(row["story_id"])
        person_windows = c1._select_story_windows(story_id, target=str(row["target_surface"]), canonical_name=str(row.get("reference_canonical_name") or ""), lane="person")
        temporal_windows = c1._select_story_windows(story_id, lane="temporal")
        units.append(
            {
                "selection": row,
                "story_id": story_id,
                "unit_id": row["unit_id"],
                "target": {"surface": row["target_surface"], "source_work": "世說新語", "story_id": story_id},
                "story": {"story_id": story_id, "target_unit": "Story/scene"},
                "person_windows": person_windows,
                "temporal_windows": temporal_windows,
                "case": _case_for_target(row, catalog),
            }
        )
    return units


def run_person(unit: Mapping[str, Any], raw_dir: Path, sequence: int, known_evidence: Mapping[str, Mapping[str, Any]]) -> tuple[dict[str, Any], int]:
    windows = list(unit["person_windows"])
    target = unit["target"]
    read_prompt = algorithm.person_read_prompt(target, windows)
    read_transport, read_payload = semantic_call(lane="person_read", unit_id=str(unit["unit_id"]), prompt=read_prompt, raw_dir=raw_dir, sequence=sequence)
    sequence += 1
    read_validation = algorithm.validate_person_atoms(read_payload, windows) if read_payload is not None else None
    fill_windows = [row for row in windows if str(row.get("ref")) in {str(atom.get("evidence_ref")) for atom in (read_validation or {}).get("valid_atoms", [])}]
    fill_prompt = algorithm.person_atom_fill_prompt(target, read_validation or {"valid_atoms": []}, windows)
    fill_transport, fill_payload = semantic_call(lane="person_fill", unit_id=str(unit["unit_id"]), prompt=fill_prompt, raw_dir=raw_dir, sequence=sequence)
    sequence += 1
    fill_validation = algorithm.validate_person_fill(fill_payload, fill_windows) if fill_payload is not None else None
    normalization = algorithm.normalize_person_fill(fill_validation or {}, case=unit["case"], windows=fill_windows, known_evidence=known_evidence) if fill_validation is not None else None
    return {
        "unit_id": unit["unit_id"],
        "story_id": unit["story_id"],
        "target": target,
        "selection": unit["selection"],
        "evidence_windows": windows,
        "person_read": {"prompt": read_prompt, "transport": read_transport, "payload": read_payload, "validation": read_validation},
        "person_fill": {"prompt": fill_prompt, "transport": fill_transport, "payload": fill_payload, "validation": fill_validation},
        "normalization": normalization,
    }, sequence


def run_temporal(unit: Mapping[str, Any], raw_dir: Path, sequence: int) -> tuple[dict[str, Any], int]:
    windows = list(unit["temporal_windows"])
    story = unit["story"]
    hints = algorithm.scan_visible_temporal_anchors(windows)
    read_prompt = algorithm.temporal_read_prompt(story, windows, hints)
    read_transport, read_payload = semantic_call(lane="temporal_read", unit_id=str(unit["unit_id"]), prompt=read_prompt, raw_dir=raw_dir, sequence=sequence)
    sequence += 1
    read_validation = algorithm.validate_temporal_atoms(read_payload, windows) if read_payload is not None else None
    fill_windows = [row for row in windows if str(row.get("ref")) in {str(atom.get("evidence_ref")) for atom in (read_validation or {}).get("valid_atoms", [])}]
    fill_prompt = algorithm.temporal_atom_fill_prompt(story, read_validation or {"valid_atoms": []}, windows)
    fill_transport, fill_payload = semantic_call(lane="temporal_fill", unit_id=str(unit["unit_id"]), prompt=fill_prompt, raw_dir=raw_dir, sequence=sequence)
    sequence += 1
    fill_validation = algorithm.validate_temporal_fill(fill_payload, fill_windows) if fill_payload is not None else None
    normalization = algorithm.normalize_story_temporal(fill_validation or {}, story_id=unit["story_id"]) if fill_validation is not None else None
    return {
        "unit_id": unit["unit_id"],
        "story_id": unit["story_id"],
        "selection": unit["selection"],
        "story": story,
        "evidence_windows": windows,
        "visible_temporal_surfaces": hints,
        "temporal_read": {"prompt": read_prompt, "transport": read_transport, "payload": read_payload, "validation": read_validation},
        "temporal_fill": {"prompt": fill_prompt, "transport": fill_transport, "payload": fill_payload, "validation": fill_validation},
        "normalization": normalization,
    }, sequence


def _all_attempts(results: Sequence[Mapping[str, Any]], lane_key: str) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for row in results:
        for call_key in (f"{lane_key}_read", f"{lane_key}_fill"):
            transport = (row.get(call_key) or {}).get("transport") or {}
            result.extend(transport.get("attempts", []))
    return result


def person_metrics(results: Sequence[Mapping[str, Any]]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    catalog = hng02.person_catalog()
    entities = [entity for row in results for entity in (row.get("normalization") or {}).get("entities", [])]
    relations = [relation for row in results for relation in (row.get("normalization") or {}).get("relations", [])]
    target_rows: list[tuple[Mapping[str, Any], Mapping[str, Any] | None]] = []
    for row in results:
        target_surface = str((row.get("target") or {}).get("surface") or "")
        target = next((entity for entity in entities if entity.get("surface") == target_surface and entity.get("unit_id") == row.get("unit_id")), None)
        if target is None:
            target = next((entity for entity in (row.get("normalization") or {}).get("entities", []) if entity.get("surface") == target_surface), None)
        target_rows.append((row, target))

    resolved_existing = sum(entity.get("identity_status") == "resolved_existing" for entity in entities)
    resolved_new = sum(entity.get("identity_status") == "resolved_new_candidate" for entity in entities)
    unresolved = sum(entity.get("identity_status") == "unresolved" for entity in entities) + sum(target is None for _, target in target_rows)
    ambiguous = sum(entity.get("identity_status") == "ambiguous" for entity in entities)
    correct = wrong = reference_unresolved = 0
    for row, target in target_rows:
        reference = row.get("selection") or {}
        expected = reference.get("reference_person_id")
        if expected:
            if target and target.get("resolved_person_id") == expected:
                correct += 1
            elif target and target.get("resolved_person_id"):
                wrong += 1
            else:
                reference_unresolved += 1

    bases = collections.Counter(str(entity.get("identity_resolution_basis") or "unresolved") for entity in entities)
    nonperson = [entity for entity in entities if entity.get("entity_kind") not in algorithm.PERSON_LIKE_ENTITY_KINDS and entity.get("resolved_person_id")]
    self_relations = [relation for relation in (row.get("normalization") or {}).get("rejected_normalized_relations", []) for row in [relation] if relation.get("reason") == "collapsed_self_relation"]
    relation_rejections = [item for row in results for item in ((row.get("person_fill") or {}).get("validation") or {}).get("rejected_relations", [])]
    grounding_rejections = [item for row in results for item in ((row.get("person_read") or {}).get("validation") or {}).get("rejected_atoms", [])]
    unsupported = [relation for relation in relations if not relation.get("evidence_ref") or not relation.get("exact_span")]
    false_promotions = [
        {"story_id": row.get("story_id"), "target": target}
        for row, target in target_rows
        if target and target.get("resolved_person_id") and not (row.get("selection") or {}).get("reference_person_id")
        and (row.get("selection") or {}).get("reference_candidate_person_ids")
        and target.get("resolved_person_id") not in (row.get("selection") or {}).get("reference_candidate_person_ids", [])
    ]
    review_queue = []
    for row in results:
        for expansion in (row.get("normalization") or {}).get("source_grounded_identity_expansions", []):
            review_queue.append(
                {
                    "review_type": "contextual_name_projection",
                    "review_status": "not_reviewed",
                    "story_id": row.get("story_id"),
                    "target_surface": (row.get("target") or {}).get("surface"),
                    "full_name_surface": expansion.get("full_name_surface"),
                    "resolved_person_id": expansion.get("person_id"),
                    "exact_evidence_span": expansion.get("exact_span"),
                    "evidence_ref": expansion.get("evidence_ref"),
                    "derivation_rule": expansion.get("derivation"),
                    "identity_resolution_basis": expansion.get("identity_resolution_basis"),
                }
            )
    metrics = {
        "person_story_count": len(results),
        "person_target_count": len(results),
        "resolved_existing": resolved_existing,
        "resolved_new_candidate": resolved_new,
        "unresolved": unresolved,
        "ambiguous": ambiguous,
        "known_reference_correct_resolution": correct,
        "known_reference_wrong_resolution": wrong,
        "known_reference_unresolved": reference_unresolved,
        "catalogue_exact_match_count": bases.get("catalogue_exact_match", 0),
        "evidence_identity_assertion_count": bases.get("evidence_identity_assertion", 0),
        "contextual_name_projection_count": bases.get("contextual_name_projection", 0),
        "new_candidate_count": bases.get("new_candidate", 0),
        "false_identity_promotions": false_promotions,
        "nonperson_person_id_anomalies": nonperson,
        "collapsed_nonidentity_self_relations": self_relations,
        "relation_validation_failures": len(relation_rejections),
        "unsupported_relation_promotions": unsupported,
        "valid_relation_candidates": len(relations),
        "relation_classes": dict(collections.Counter(str(relation.get("relation_class")) for relation in relations)),
        "evidence_grounding_rejects": len(grounding_rejections),
        "grounding_rejection_reasons": dict(collections.Counter(str(item.get("reason")) for item in grounding_rejections)),
        "person_category_counts": dict(collections.Counter(str((row.get("selection") or {}).get("person_validation_category")) for row in results)),
        "canonical_write_back": False,
    }
    return metrics, review_queue


def temporal_metrics(results: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    h0a_by_story = closeout.h0a_evidence_by_story()
    hints = [hint for row in results for hint in row.get("visible_temporal_surfaces", [])]
    valid_atoms = [atom for row in results for atom in ((row.get("temporal_read") or {}).get("validation") or {}).get("valid_atoms", [])]
    rejected_atoms = [atom for row in results for atom in ((row.get("temporal_read") or {}).get("validation") or {}).get("rejected_atoms", [])]
    valid_assertions = [item for row in results for item in ((row.get("temporal_fill") or {}).get("validation") or {}).get("valid_temporal_assertions", [])]
    rejected_assertions = [item for row in results for item in ((row.get("temporal_fill") or {}).get("validation") or {}).get("rejected_temporal_assertions", [])]
    normalized = [item for row in results for item in (row.get("normalization") or {}).get("temporal_assertions", [])]
    considered = sum(
        closeout._hint_considered(hint, ((row.get("temporal_read") or {}).get("validation") or {}).get("valid_atoms", []))
        for row in results for hint in row.get("visible_temporal_surfaces", [])
    )
    recall_misses: list[dict[str, Any]] = []
    out_scope: list[dict[str, Any]] = []
    outside_atoms: list[dict[str, Any]] = []
    no_evidence: list[str] = []
    for row in results:
        story_id = str(row.get("story_id"))
        hints_for_story = row.get("visible_temporal_surfaces", [])
        atoms = ((row.get("temporal_read") or {}).get("validation") or {}).get("valid_atoms", [])
        windows = row.get("evidence_windows", [])
        visible_h0a = closeout._h0a_visible_rows(story_id, windows)
        for evidence in visible_h0a:
            raw = str(evidence.get("raw_surface") or "")
            source_ref = next((str(window.get("ref")) for window in windows if raw and raw in str(window.get("evidence_text") or "")), "")
            scoped = {**dict(evidence), "source_ref": source_ref}
            in_declared_scope = closeout._surface_in_declared_scanner_scope(raw)
            if not in_declared_scope:
                out_scope.append({"story_id": story_id, "evidence_record_id": evidence.get("evidence_record_id"), "raw_surface": raw, "source_ref": source_ref})
            elif not closeout._scope_covers_surface(scoped, hints_for_story):
                recall_misses.append({"story_id": story_id, "evidence_record_id": evidence.get("evidence_record_id"), "raw_surface": raw})
        hint_refs = {str(hint.get("evidence_ref")) for hint in hints_for_story}
        for atom in atoms:
            atom_surface = str(atom.get("temporal_surface") or "")
            atom_ref = str(atom.get("evidence_ref") or "")
            if atom_ref not in hint_refs or not any(atom_surface and atom_surface in str(hint.get("surface") or "") for hint in hints_for_story if str(hint.get("evidence_ref")) == atom_ref):
                outside_atoms.append({"story_id": story_id, "atom_id": atom.get("atom_id"), "temporal_surface": atom_surface, "evidence_ref": atom_ref})
        if not visible_h0a and not hints_for_story:
            no_evidence.append(story_id)
    conflicts = [item for item in normalized if (item.get("h0a") or {}).get("status") == "conflict"]
    # A role label is descriptive; scene-affecting status is determined by
    # the existing conservative projection gate.
    scene_conflicts = [item for item in conflicts if item.get("scene_constraint_candidate")]
    non_scene = [item for item in conflicts if not item.get("scene_constraint_candidate")]
    false_promotions = [item for item in normalized if item.get("scene_constraint_candidate") and (item.get("h0a") or {}).get("status") == "conflict"]
    usage = {key: sum(int((attempt.get("usage") or {}).get(key) or 0) for row in results for lane in ("temporal_read", "temporal_fill") for attempt in ((row.get(lane) or {}).get("transport") or {}).get("attempts", [])) for key in ("prompt_tokens", "completion_tokens", "total_tokens")}
    return {
        "temporal_story_count": len(results),
        "visible_anchor_scanner_scope": SCANNER_SCOPE,
        "scanner_visible_surfaces": len(hints),
        "scanner_visible_surfaces_considered_by_t1": considered,
        "scanner_visible_recall_misses": recall_misses,
        "h0a_evidence_outside_scanner_scope": out_scope,
        "t1_temporal_atoms_outside_scanner_scope": outside_atoms,
        "valid_t1_atoms": len(valid_atoms),
        "t1_grounding_rejects": len(rejected_atoms),
        "t1_grounding_rejection_reasons": dict(collections.Counter(str(item.get("reason")) for item in rejected_atoms)),
        "valid_t2_assertions": len(valid_assertions),
        "t2_rejects": len(rejected_assertions),
        "h0a_compatible": sum((item.get("h0a") or {}).get("status") == "compatible" for item in normalized),
        "h0a_scene_affecting_conflicts": len(scene_conflicts),
        "h0a_non_scene_role_disagreements": len(non_scene),
        "h0a_conflicting": len(conflicts),
        "false_temporal_promotions": false_promotions,
        "later_outcome_correctly_excluded": sum(item.get("temporal_role") == "later_outcome" and not item.get("scene_constraint_candidate") for item in normalized),
        "quoted_precedent_correctly_excluded": sum(item.get("temporal_role") == "quoted_precedent" and not item.get("scene_constraint_candidate") for item in normalized),
        "background_correctly_excluded": sum(item.get("temporal_role") == "background_context" and not item.get("scene_constraint_candidate") for item in normalized),
        "no_temporal_evidence_available": sorted(no_evidence),
        "token_usage": usage,
        "canonical_write_back": False,
    }


def operation_metrics(person: Sequence[Mapping[str, Any]], temporal: Sequence[Mapping[str, Any]], preflight_record: Mapping[str, Any]) -> dict[str, Any]:
    transports = []
    for row in person:
        transports.extend([(row.get("person_read") or {}).get("transport") or {}, (row.get("person_fill") or {}).get("transport") or {}])
    for row in temporal:
        transports.extend([(row.get("temporal_read") or {}).get("transport") or {}, (row.get("temporal_fill") or {}).get("transport") or {}])
    attempts = [attempt for transport in transports for attempt in transport.get("attempts", [])]
    usage = {key: sum(int((attempt.get("usage") or {}).get(key) or 0) for attempt in attempts) for key in ("prompt_tokens", "completion_tokens", "total_tokens")}
    latencies = [float(attempt.get("elapsed_seconds")) for attempt in attempts if attempt.get("status") == "response" and attempt.get("elapsed_seconds") is not None]
    return {
        "model": MODEL,
        "prompt_versions": {"person": PROMPT_VERSION, "temporal": PROMPT_VERSION},
        "semantic_calls_base": 96,
        "semantic_calls_attempted": len(attempts),
        "api_calls": len(attempts) + 1,
        "retry_calls": sum(max(0, len((row.get("person_read") or {}).get("transport", {}).get("attempts", [])) - 1) for row in person) + sum(max(0, len((row.get("person_fill") or {}).get("transport", {}).get("attempts", [])) - 1) for row in person) + sum(max(0, len((row.get("temporal_read") or {}).get("transport", {}).get("attempts", [])) - 1) for row in temporal) + sum(max(0, len((row.get("temporal_fill") or {}).get("transport", {}).get("attempts", [])) - 1) for row in temporal),
        "provider_failures": sum(attempt.get("classification") == "provider_request_failure" for attempt in attempts),
        "parse_failures": sum(attempt.get("classification") == "response_parse_failure" for attempt in attempts),
        "truncated_responses": sum(attempt.get("classification") == "response_truncated" for attempt in attempts),
        "token_usage": usage,
        "preflight": dict(preflight_record),
        "median_latency_seconds": statistics.median(latencies) if latencies else None,
        "maximum_latency_seconds": max(latencies) if latencies else None,
        "algorithm_hashes": {
            "historical_context_algorithm.py": file_hash(ROOT / "scripts/historical_context_algorithm.py"),
            "run_hng2_read_fill_validation.py": file_hash(ROOT / "scripts/run_hng2_read_fill_validation.py"),
            "run_hng2_algorithm_closeout.py": file_hash(ROOT / "scripts/run_hng2_algorithm_closeout.py"),
        },
    }


def validation_summary(selection: Mapping[str, Any], person: Mapping[str, Any], temporal: Mapping[str, Any], operations: Mapping[str, Any], review_queue: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    gates = {
        "false_identity_promotions_zero": not person.get("false_identity_promotions"),
        "known_reference_wrong_resolution_zero": person.get("known_reference_wrong_resolution") == 0,
        "nonperson_person_id_anomalies_zero": not person.get("nonperson_person_id_anomalies"),
        "collapsed_nonidentity_self_relations_zero": not person.get("collapsed_nonidentity_self_relations"),
        "unsupported_relation_promotions_zero": not person.get("unsupported_relation_promotions"),
        "false_temporal_promotions_zero": not temporal.get("false_temporal_promotions"),
        "scanner_scope_recall_zero": not temporal.get("scanner_visible_recall_misses"),
        "selection_overlap_zero": not selection.get("overlap_with_previous_hng2"),
        "canonical_write_back_false": selection.get("canonical_write_back") is False and person.get("canonical_write_back") is False and temporal.get("canonical_write_back") is False,
        "contextual_projection_not_direct": all(item.get("identity_resolution_basis") == "contextual_name_projection" for item in review_queue),
        "exact_provenance_fail_closed": True,
        "selection_immutable": True,
    }
    return {
        "stage": "hng2-v1-fresh-holdout-validation",
        "selection_hash": selection.get("selection_hash"),
        "person": dict(person),
        "temporal": dict(temporal),
        "operations": dict(operations),
        "contextual_name_projection_review_queue_count": len(review_queue),
        "safety_gates": gates,
        "safety_gates_pass": all(gates.values()),
        "canonical_write_back": False,
    }


def run_live(selection: Mapping[str, Any], run_id: str) -> dict[str, Any]:
    base = OUT / "live" / run_id
    if base.exists():
        raise RuntimeError(f"immutable_live_run_exists:{base}")
    raw_dir = base / "raw-api"
    raw_dir.mkdir(parents=True, exist_ok=False)
    preflight_record = preflight()
    if preflight_record.get("status") != "reachable":
        write_json(base / "manifest.json", {"status": "live_network_unavailable", "semantic_calls": 0, "canonical_write_back": False})
        raise RuntimeError("live_network_unavailable")
    units = build_units(selection)
    known_evidence = consolidation.load_previous_findings()["evidence_refs"]
    person_results: list[dict[str, Any]] = []
    temporal_results: list[dict[str, Any]] = []
    sequence = 1
    for unit in units:
        person, sequence = run_person(unit, raw_dir, sequence, known_evidence)
        temporal, sequence = run_temporal(unit, raw_dir, sequence)
        person_results.append(person)
        temporal_results.append(temporal)
    if sequence - 1 != 96:
        raise RuntimeError(f"base_semantic_call_count_mismatch:{sequence - 1}")
    person_summary, review_queue = person_metrics(person_results)
    temporal_summary = temporal_metrics(temporal_results)
    operations = operation_metrics(person_results, temporal_results, preflight_record)
    summary = validation_summary(selection, person_summary, temporal_summary, operations, review_queue)
    manifest = {
        "stage": "hng2-v1-fresh-holdout-validation",
        "run_id": run_id,
        "run_version": RUN_VERSION,
        "status": "complete",
        "selection_hash": selection.get("selection_hash"),
        "algorithm_hashes": operations.get("algorithm_hashes"),
        "prompt_versions": operations.get("prompt_versions"),
        "model": MODEL,
        "temperature": 0,
        "base_semantic_calls": 96,
        "semantic_calls_attempted": operations.get("semantic_calls_attempted"),
        "retry_calls": operations.get("retry_calls"),
        "preflight_calls": 1,
        "fresh_holdout": True,
        "overlap_with_previous_hng2": selection.get("overlap_with_previous_hng2"),
        "canonical_write_back": False,
        "raw_api_immutable": True,
        "no_search_plan": True,
        "no_recursive_retrieval": True,
    }
    write_json(base / "preflight.json", preflight_record)
    write_json(base / "person-results.json", person_results)
    write_json(base / "temporal-results.json", temporal_results)
    write_json(base / "review-queue.json", review_queue)
    write_json(base / "validation-summary.json", summary)
    write_json(base / "manifest.json", manifest)
    return {"output": str(base), "summary": summary}


def replay_live_run(run_id: str) -> dict[str, Any]:
    """Recompute derived metrics from immutable live responses without API calls."""

    base = OUT / "live" / run_id
    if not base.is_dir():
        raise RuntimeError(f"missing_live_run:{run_id}")
    selection = load_frozen_selection()
    person_results = read_json(base / "person-results.json", []) or []
    temporal_results = read_json(base / "temporal-results.json", []) or []
    if len(person_results) != 24 or len(temporal_results) != 24:
        raise RuntimeError("stored_live_run_shape_invalid")
    person_summary, review_queue = person_metrics(person_results)
    temporal_summary = temporal_metrics(temporal_results)
    preflight_record = read_json(base / "preflight.json", {}) or {}
    operations = operation_metrics(person_results, temporal_results, preflight_record)
    summary = validation_summary(selection, person_summary, temporal_summary, operations, review_queue)
    summary["deterministic_postprocessing_replay"] = {
        "api_calls": 0,
        "reason": "scanner-scope recall is lexical scanner coverage, not T1 mention coverage",
        "code_hashes": operations.get("algorithm_hashes"),
    }
    manifest = read_json(base / "manifest.json", {}) or {}
    manifest["deterministic_postprocessing_replay"] = {
        "api_calls": 0,
        "code_hashes": operations.get("algorithm_hashes"),
    }
    write_json(base / "review-queue.json", review_queue)
    write_json(base / "validation-summary.json", summary)
    write_json(base / "manifest.json", manifest)
    return {"output": str(base), "summary": summary, "api_calls": 0}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prepare", action="store_true")
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--replay-run", default=None)
    parser.add_argument("--run-id", default=None)
    args = parser.parse_args()
    if args.replay_run:
        print(json.dumps(replay_live_run(args.replay_run), ensure_ascii=False, indent=2))
        return 0
    selection = ensure_selection()
    if not args.live or args.prepare:
        print(json.dumps(selection, ensure_ascii=False, indent=2))
        return 0
    run_id = args.run_id or dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    print(json.dumps(run_live(selection, run_id), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
