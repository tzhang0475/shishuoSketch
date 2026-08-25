#!/usr/bin/env python3
"""Close out HNG2-C with offline Person replay and H0A-focused live time validation.

The runner does not retrieve new evidence.  Person projections are rebuilt
from immutable HNG2-C.2 cards without API calls.  The temporal closeout uses
one READ and one FILL call for each frozen Story and no retry.
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
import run_hng2_evidence_atom_validation as c2  # noqa: E402
import run_hng2_read_fill_validation as c1  # noqa: E402
from smoke_deepseek import call_deepseek  # noqa: E402


OUT = ROOT / "data/generated/hng2-algorithm-closeout"
C2_RUN = ROOT / "data/generated/hng2-evidence-atom-validation/live/20260825T-HNG2-C2-01"
MODEL = "deepseek-v4-flash"
RUN_VERSION = "hng2-c3-final-closeout-v1"
PROMPT_VERSION = "hng2-c3-visible-anchor-v1"
VISIBLE_ANCHOR_SCANNER_SCOPE = "H0A historical registry + explicit date patterns"

# Existing frozen Stories only.  The categories are evaluation strata, not
# model hints and are never included in the semantic prompt.
TEMPORAL_STORIES = (
    ("exact_year", "17-shangshi-006"),
    ("ruler_reign", "01-dexing-017"),
    ("event_bounded", "05-fangzheng-032"),
    ("event_bounded_secondary", "27-jiajue-008"),
    ("later_outcome", "06-yaliang-017"),
    ("quoted_precedent", "04-wenxue-022"),
    ("background_context", "04-wenxue-094"),
    ("later_outcome_event", "20-shujie-005"),
    ("ruler_title", "09-pinzao-014"),
    ("weak_unknown", "01-dexing-014"),
)


def read_json(path: Path, default: Any = None) -> Any:
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else default


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def h0a_evidence_by_story() -> dict[str, list[dict[str, Any]]]:
    document = read_json(ROOT / "data/annotation/story-temporal-evidence-h0a.json", {}) or {}
    result: dict[str, list[dict[str, Any]]] = collections.defaultdict(list)
    for row in document.get("records", []):
        if isinstance(row, Mapping) and row.get("story_id"):
            result[str(row["story_id"])].append(dict(row))
    return dict(result)


def build_selection() -> dict[str, Any]:
    h0a = h0a_evidence_by_story()
    stories: list[dict[str, Any]] = []
    for category, story_id in TEMPORAL_STORIES:
        windows = c1._select_story_windows(story_id, lane="temporal")
        hints = algorithm.scan_visible_temporal_anchors(windows)
        stories.append(
            {
                "unit_id": f"temporal-closeout-{story_id}",
                "story_id": story_id,
                "category": category,
                "source_refs": [str(row.get("ref")) for row in windows],
                "visible_temporal_surfaces": hints,
                "h0a_evidence_ids": [str(row.get("evidence_record_id")) for row in h0a.get(story_id, [])],
                "selection_key": c1.stable_hash({"story_id": story_id, "category": category}),
            }
        )
    return {
        "stage": "hng2-c3-final-algorithm-closeout",
        "algorithm_version": RUN_VERSION,
        "frozen_before_live": True,
        "selection_method": "fixed deterministic H0A coverage strata over existing frozen Stories",
        "stories": stories,
        "story_count": len(stories),
        "semantic_call_count": len(stories) * 2,
        "required_story_ids": ["01-dexing-017", "04-wenxue-022", "06-yaliang-017"],
        "no_new_stories": True,
        "canonical_write_back": False,
    }


def ensure_selection() -> dict[str, Any]:
    selection = build_selection()
    path = OUT / "selection.json"
    if path.is_file() and c1.stable_hash(read_json(path, {})) != c1.stable_hash(selection):
        raise RuntimeError("c3_frozen_selection_mismatch")
    if not path.is_file():
        write_json(path, selection)
    if selection["story_count"] not in range(8, 13) or selection["semantic_call_count"] != 20:
        raise RuntimeError("c3_selection_shape_invalid")
    return selection


def _target_rows(result: Mapping[str, Any]) -> list[dict[str, Any]]:
    surface = str((result.get("target") or {}).get("surface") or "")
    return [dict(row) for row in (result.get("normalization") or {}).get("entities", []) if row.get("surface") == surface]


def replay_person_outputs() -> dict[str, Any]:
    """Reproject frozen C.2 Person cards with zero model calls."""

    selection = c2.build_selection()
    person_units, _, heldout_units = c1.build_units(selection)
    unit_index = {str(row["unit_id"]): row for row in [*person_units, *heldout_units]}
    known = consolidation.load_previous_findings()["evidence_refs"]
    stored_person = read_json(C2_RUN / "person-results.json", []) or []
    stored_heldout = read_json(C2_RUN / "heldout-results.json", []) or []
    frozen_rows = [*stored_person, *[row["person"] for row in stored_heldout]]
    results: list[dict[str, Any]] = []
    for stored in frozen_rows:
        unit_id = str(stored.get("unit_id"))
        unit = unit_index.get(unit_id)
        if unit is None:
            raise RuntimeError(f"person_replay_unit_missing:{unit_id}")
        validation = ((stored.get("person_fill") or {}).get("validation") or {})
        windows = stored.get("evidence_windows") or unit.get("windows") or unit.get("person_windows") or []
        normalization = algorithm.normalize_person_fill(
            validation,
            case=unit["case"],
            windows=windows,
            known_evidence=known,
        )
        replayed = {**dict(stored), "normalization": normalization, "offline_replay": True, "api_calls": 0}
        results.append(replayed)

    target_counts: collections.Counter[str] = collections.Counter()
    nonperson: list[dict[str, Any]] = []
    self_relations: list[dict[str, Any]] = []
    by_surface: dict[str, list[dict[str, Any]]] = collections.defaultdict(list)
    for row in results:
        target_rows = _target_rows(row)
        if not target_rows:
            target_counts["unresolved"] += 1
        for entity in target_rows:
            target_counts[str(entity.get("identity_status") or "unresolved")] += 1
            by_surface[str(entity.get("surface") or "")].append(entity)
        for entity in (row.get("normalization") or {}).get("entities", []):
            if entity.get("entity_kind") not in algorithm.PERSON_LIKE_ENTITY_KINDS and entity.get("resolved_person_id"):
                nonperson.append({"unit_id": row.get("unit_id"), "entity": entity})
        for relation in (row.get("normalization") or {}).get("relations", []):
            if relation.get("relation_class") != "identity_name" and relation.get("person_a") and relation.get("person_a") == relation.get("person_b"):
                self_relations.append({"unit_id": row.get("unit_id"), "relation": relation})

    def resolved(surface: str, person_id: str) -> bool:
        return any(row.get("resolved_person_id") == person_id for row in by_surface.get(surface, []))

    heldout_ids = {str(row.get("unit_id")) for row in stored_heldout}
    heldout_stable = True
    for old in frozen_rows:
        if str(old.get("unit_id")) not in heldout_ids:
            continue
        new = next(row for row in results if row.get("unit_id") == old.get("unit_id"))
        old_signature = sorted((row.get("surface"), row.get("identity_status"), row.get("resolved_person_id")) for row in _target_rows(old))
        new_signature = sorted((row.get("surface"), row.get("identity_status"), row.get("resolved_person_id")) for row in _target_rows(new))
        heldout_stable = heldout_stable and old_signature == new_signature

    relation_validation_failures = sum(
        len(((row.get("person_fill") or {}).get("validation") or {}).get("rejected_relations", []))
        for row in results
    )
    checks = {
        "yi_resolves_person_053": resolved("廙", "person-053"),
        "yu_taiwei_unchanged": resolved("庾太尉", "person-010"),
        "shan_tao_unchanged": resolved("山濤", "person-043"),
        "chen_qian_candidate_only": any(row.get("identity_status") == "resolved_new_candidate" for row in by_surface.get("陳騫", [])),
        "xuan_unresolved": not any(row.get("resolved_person_id") for row in by_surface.get("宣", [])),
        "yu_unresolved": not any(row.get("resolved_person_id") for row in by_surface.get("譽", [])),
        "heldout_unchanged": heldout_stable,
        "nonperson_person_id_zero": not nonperson,
        "collapsed_nonidentity_self_relations_zero": not self_relations,
    }
    person_lane_frozen = all(checks.values()) and relation_validation_failures == 0
    return {
        "source_run": str(C2_RUN.relative_to(ROOT)),
        "api_calls": 0,
        "results": results,
        "metrics": {
            "resolved_existing": target_counts.get("resolved_existing", 0),
            "resolved_new_candidate": target_counts.get("resolved_new_candidate", 0),
            "unresolved": target_counts.get("unresolved", 0),
            "ambiguous": target_counts.get("ambiguous", 0),
            "nonperson_person_id_anomalies": len(nonperson),
            "collapsed_nonidentity_self_relations": len(self_relations),
            "relation_validation_failures": relation_validation_failures,
            "identity_propagations": sum(len((row.get("normalization") or {}).get("source_grounded_identity_expansions", [])) for row in results),
        },
        "regression_checks": checks,
        "person_lane_frozen": person_lane_frozen,
        "canonical_write_back": False,
    }


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
    expected = algorithm.TEMPORAL_ATOM_FUNCTION if lane == "temporal_read" else algorithm.TEMPORAL_FILL_FUNCTION
    system = algorithm.TEMPORAL_ANCHOR_ATOM_SYSTEM if lane == "temporal_read" else algorithm.TEMPORAL_ATOM_FILL_SYSTEM
    max_tokens = 750
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
                {"role": "system", "content": system},
                {"role": "user", "content": json.dumps(prompt, ensure_ascii=False, sort_keys=True)},
            ],
            model=MODEL,
            temperature=0,
            thinking={"type": "disabled"},
            max_tokens=max_tokens,
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
        record.update({"status": "response", "finish_reason": finish, "usage": _usage(response), "raw_path": str(raw_path.relative_to(ROOT))})
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


def run_temporal_live(selection: Mapping[str, Any], *, run_id: str) -> dict[str, Any]:
    base = OUT / "live" / run_id
    if base.exists():
        raise RuntimeError(f"immutable_live_run_exists:{base}")
    raw_dir = base / "raw-api"
    raw_dir.mkdir(parents=True, exist_ok=False)
    preflight_record = preflight()
    write_json(base / "preflight.json", preflight_record)
    if preflight_record.get("status") != "reachable":
        write_json(base / "manifest.json", {"status": "live_network_unavailable", "semantic_calls": 0, "canonical_write_back": False})
        raise RuntimeError("live_network_unavailable")

    sequence = 1
    results: list[dict[str, Any]] = []
    for selected in selection.get("stories", []):
        story_id = str(selected["story_id"])
        unit_id = str(selected["unit_id"])
        story = {"story_id": story_id, "target_unit": "Story/scene"}
        windows = c1._select_story_windows(story_id, lane="temporal")
        hints = algorithm.scan_visible_temporal_anchors(windows)
        if c1.stable_hash(hints) != c1.stable_hash(selected.get("visible_temporal_surfaces", [])):
            raise RuntimeError(f"visible_anchor_selection_drift:{story_id}")
        t1_prompt = algorithm.temporal_read_prompt(story, windows, hints)
        t1_transport, t1 = semantic_call(lane="temporal_read", unit_id=unit_id, prompt=t1_prompt, raw_dir=raw_dir, sequence=sequence)
        sequence += 1
        t1_validation = algorithm.validate_temporal_atoms(t1, windows) if t1 is not None else None
        t2_prompt = algorithm.temporal_atom_fill_prompt(story, t1_validation or {"valid_atoms": []}, windows)
        t2_transport, t2 = semantic_call(lane="temporal_fill", unit_id=unit_id, prompt=t2_prompt, raw_dir=raw_dir, sequence=sequence)
        sequence += 1
        atom_refs = {str(row.get("evidence_ref")) for row in (t1_validation or {}).get("valid_atoms", [])}
        fill_windows = [row for row in windows if str(row.get("ref")) in atom_refs]
        t2_validation = algorithm.validate_temporal_fill(t2, fill_windows) if t2 is not None else None
        normalization = algorithm.normalize_story_temporal(t2_validation or {}, story_id=story_id) if t2_validation is not None else None
        results.append(
            {
                "unit_id": unit_id,
                "story_id": story_id,
                "category": selected.get("category"),
                "story": story,
                "evidence_windows": windows,
                "visible_temporal_surfaces": hints,
                "temporal_read": {"prompt": t1_prompt, "transport": t1_transport, "payload": t1, "validation": t1_validation},
                "temporal_fill": {"prompt": t2_prompt, "transport": t2_transport, "payload": t2, "validation": t2_validation},
                "normalization": normalization,
            }
        )
    if sequence - 1 != 20:
        raise RuntimeError(f"semantic_call_count_mismatch:{sequence - 1}")
    metrics = temporal_metrics(results, preflight_record)
    write_json(base / "temporal-results.json", results)
    write_json(base / "metrics.json", metrics)
    write_json(
        base / "manifest.json",
        {
            "stage": "hng2-c3-final-algorithm-closeout",
            "run_id": run_id,
            "status": "complete",
            "algorithm_version": RUN_VERSION,
            "selection_hash": c1.stable_hash(selection),
            "semantic_calls": 20,
            "preflight_calls": 1,
            "no_retries": True,
            "no_search": True,
            "no_followup": True,
            "candidate_projection_only": True,
            "canonical_write_back": False,
        },
    )
    write_closeout_summary(run_id, metrics)
    return {"output": str(base), "metrics": metrics}


def _hint_considered(hint: Mapping[str, Any], atoms: Sequence[Mapping[str, Any]]) -> bool:
    surface = str(hint.get("surface") or "")
    ref = str(hint.get("evidence_ref") or "")
    return any(
        str(atom.get("evidence_ref") or "") == ref
        and surface
        and surface in str(atom.get("exact_span") or "")
        for atom in atoms
    )


def _h0a_visible_rows(story_id: str, windows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    texts = {str(row.get("ref")): str(row.get("evidence_text") or "") for row in windows}
    combined = "\n".join(texts.values())
    return [row for row in h0a_evidence_by_story().get(story_id, []) if str(row.get("raw_surface") or "") and str(row.get("raw_surface")) in combined]


def _scope_covers_surface(row: Mapping[str, Any], hints: Sequence[Mapping[str, Any]]) -> bool:
    raw = str(row.get("raw_surface") or "")
    ref = str(row.get("source_ref") or row.get("evidence_ref") or "")
    return any(
        str(hint.get("evidence_ref") or "") == ref
        and (str(hint.get("surface") or "") in raw or raw in str(hint.get("surface") or ""))
        for hint in hints
    )


def _surface_in_declared_scanner_scope(surface: str) -> bool:
    """Return whether a literal is covered by the scanner's declared scope.

    This is deliberately lexical.  It does not ask whether T1 mentioned the
    surface, so a model omission cannot be misreported as scanner recall loss.
    The scope is exactly the H0A registry plus the explicit date patterns used
    by ``scan_visible_temporal_anchors``.
    """

    surface = str(surface or "")
    if not surface:
        return False
    registry = algorithm.visible_temporal_anchor_registry()
    if surface in registry or any(registered and registered in surface for registered in registry):
        return True
    era_names = [
        value for value, row in registry.items()
        if "reign_name" in row.get("registry_kinds", [])
    ]
    era_alternation = "|".join(re.escape(value) for value in sorted(era_names, key=lambda value: (-len(value), value)))
    year_number = r"(?:元|[一二三四五六七八九十百千〇零兩两0-9]+)年"
    explicit_date = re.compile(
        (rf"(?:{era_alternation}){year_number}|" if era_alternation else "")
        + year_number
        + r"|(?:歲|岁)在[甲乙丙丁戊己庚辛壬癸][子丑寅卯辰巳午未申酉戌亥]"
    )
    return bool(explicit_date.search(surface))


def temporal_metrics(results: Sequence[Mapping[str, Any]], preflight_record: Mapping[str, Any]) -> dict[str, Any]:
    transports = [transport for row in results for transport in ((row.get("temporal_read") or {}).get("transport") or {}, (row.get("temporal_fill") or {}).get("transport") or {})]
    hints = [hint for row in results for hint in row.get("visible_temporal_surfaces", [])]
    valid_atoms = [atom for row in results for atom in ((row.get("temporal_read") or {}).get("validation") or {}).get("valid_atoms", [])]
    rejected_atoms = [atom for row in results for atom in ((row.get("temporal_read") or {}).get("validation") or {}).get("rejected_atoms", [])]
    valid_assertions = [item for row in results for item in ((row.get("temporal_fill") or {}).get("validation") or {}).get("valid_temporal_assertions", [])]
    rejected_assertions = [item for row in results for item in ((row.get("temporal_fill") or {}).get("validation") or {}).get("rejected_temporal_assertions", [])]
    normalized = [item for row in results for item in (row.get("normalization") or {}).get("temporal_assertions", [])]
    considered = sum(_hint_considered(hint, ((row.get("temporal_read") or {}).get("validation") or {}).get("valid_atoms", [])) for row in results for hint in row.get("visible_temporal_surfaces", []))

    recall_misses: list[dict[str, Any]] = []
    no_evidence: list[str] = []
    h0a_outside_scope: list[dict[str, Any]] = []
    t1_outside_scope: list[dict[str, Any]] = []
    for row in results:
        story_id = str(row.get("story_id"))
        atoms = ((row.get("temporal_read") or {}).get("validation") or {}).get("valid_atoms", [])
        visible_h0a = _h0a_visible_rows(story_id, row.get("evidence_windows", []))
        hints_for_story = row.get("visible_temporal_surfaces", [])
        for evidence in visible_h0a:
            surface = str(evidence.get("raw_surface") or "")
            evidence_ref = next(
                (str(window.get("ref")) for window in row.get("evidence_windows", [])
                 if str(window.get("evidence_text") or "").find(surface) >= 0),
                "",
            )
            scoped_evidence = {**dict(evidence), "source_ref": evidence_ref}
            in_declared_scope = _surface_in_declared_scanner_scope(surface)
            if not in_declared_scope:
                h0a_outside_scope.append(
                    {"story_id": story_id, "evidence_record_id": evidence.get("evidence_record_id"), "raw_surface": surface, "source_ref": evidence_ref}
                )
            elif not _scope_covers_surface(scoped_evidence, hints_for_story):
                recall_misses.append({"story_id": story_id, "surface": surface, "evidence_id": evidence.get("evidence_record_id")})
        scoped_refs = {str(hint.get("evidence_ref") or "") for hint in hints_for_story}
        for atom in atoms:
            atom_surface = str(atom.get("temporal_surface") or "")
            atom_ref = str(atom.get("evidence_ref") or "")
            if atom_ref not in scoped_refs or not any(
                atom_surface and atom_surface in str(hint.get("surface") or "")
                for hint in hints_for_story if str(hint.get("evidence_ref") or "") == atom_ref
            ):
                t1_outside_scope.append({"story_id": story_id, "atom_id": atom.get("atom_id"), "temporal_surface": atom_surface, "evidence_ref": atom_ref})
        if not visible_h0a and not row.get("visible_temporal_surfaces"):
            no_evidence.append(story_id)

    h0a_conflicts = [
        {"story_id": row.get("story_id"), "assertion": item}
        for row in results
        for item in (row.get("normalization") or {}).get("temporal_assertions", [])
        if (item.get("h0a") or {}).get("status") == "conflict"
    ]
    non_scene_roles = {"background_context", "later_outcome", "quoted_precedent", "relative_person_time", "office_context", "uncertain"}
    conflict_explanations = []
    for row in h0a_conflicts:
        item = row["assertion"]
        h0a = item.get("h0a") or {}
        model_role = str(item.get("temporal_role") or "")
        h0a_relation = str(h0a.get("h0a_relation_to_story") or "")
        h0a_non_scene = h0a_relation in {"later_outcome", "quoted_ancient_precedent", "earlier_background", "person_activity_context", "event_context"}
        # A disagreement that conservatively keeps an assertion out of the
        # scene projection is explainable and cannot leak a false date.  This
        # includes a later narrated episode that H0A stores as direct Story
        # evidence while the model treats it as later than the primary scene.
        explainable = model_role in non_scene_roles and not item.get("scene_constraint_candidate")
        conflict_explanations.append(
            {
                "story_id": row["story_id"],
                "temporal_surface": item.get("temporal_surface"),
                "model_role": model_role,
                "h0a_relation_to_story": h0a_relation,
                "explainable_non_scene_role_disagreement": explainable,
                "explanation_kind": "both_non_scene" if h0a_non_scene else "conservative_non_scene_exclusion",
                "scene_projection_blocked": not item.get("scene_constraint_candidate"),
            }
        )
    false_promotions = [row for row in h0a_conflicts if row["assertion"].get("scene_constraint_candidate")]
    # Conflict reporting follows the actual conservative projection gate:
    # only an assertion still eligible for scene projection can affect scene
    # time.  A model role label alone is not sufficient.
    scene_conflicts = [row for row in h0a_conflicts if row["assertion"].get("scene_constraint_candidate")]
    non_scene_conflicts = [row for row in h0a_conflicts if not row["assertion"].get("scene_constraint_candidate")]
    by_story = {str(row.get("story_id")): row for row in results}
    def story_items(story_id: str) -> list[dict[str, Any]]:
        return list((by_story.get(story_id, {}).get("normalization") or {}).get("temporal_assertions", []))
    def story_atoms(story_id: str) -> list[dict[str, Any]]:
        return list(((by_story.get(story_id, {}).get("temporal_read") or {}).get("validation") or {}).get("valid_atoms", []))

    checks = {
        "dexing_017_wudi_detected": any(hint.get("surface") == "武帝" for hint in by_story["01-dexing-017"].get("visible_temporal_surfaces", [])),
        "dexing_017_wudi_considered": any("武帝" in str(atom.get("exact_span") or "") for atom in story_atoms("01-dexing-017")),
        "dexing_017_h0a_compatible": any((item.get("h0a") or {}).get("status") == "compatible" for item in story_items("01-dexing-017")),
        "wenxue_022_zhengshi_quoted_precedent": any(item.get("temporal_role") == "quoted_precedent" and not item.get("scene_constraint_candidate") for item in story_items("04-wenxue-022")),
        "yaliang_017_later_outcome_excluded": any(item.get("temporal_role") == "later_outcome" and not item.get("scene_constraint_candidate") for item in story_items("06-yaliang-017")),
    }
    usage = {key: sum(int((row.get("usage") or {}).get(key) or 0) for row in transports) for key in ("prompt_tokens", "completion_tokens", "total_tokens")}
    latencies = [float(row["elapsed_seconds"]) for row in transports if row.get("status") == "response" and row.get("elapsed_seconds") is not None]
    all_conflicts_explainable = all(row["explainable_non_scene_role_disagreement"] for row in conflict_explanations)
    temporal_lane_frozen = all(checks.values()) and not false_promotions and not recall_misses and all_conflicts_explainable
    return {
        "preflight": dict(preflight_record),
        "story_count": len(results),
        "semantic_calls": len(transports),
        "parsed_calls": sum(row.get("classification") == "parsed" for row in transports),
        "response_truncated": sum(row.get("classification") == "response_truncated" for row in transports),
        "provider_or_parse_failures": sum(row.get("classification") in {"provider_request_failure", "response_parse_failure"} for row in transports),
        "visible_temporal_surfaces_detected": len(hints),
        "visible_surfaces_considered_by_t1": considered,
        "visible_anchor_scanner_scope": VISIBLE_ANCHOR_SCANNER_SCOPE,
        "scanner_visible_surfaces": len(hints),
        "scanner_visible_surfaces_considered_by_t1": considered,
        "scanner_visible_recall_misses": recall_misses,
        "h0a_evidence_outside_scanner_scope": h0a_outside_scope,
        "t1_temporal_atoms_outside_scanner_scope": t1_outside_scope,
        "valid_t1_atoms": len(valid_atoms),
        "grounding_rejects": len(rejected_atoms),
        "grounding_rejection_reasons": dict(sorted(collections.Counter(str(row.get("reason")) for row in rejected_atoms).items())),
        "valid_t2_assertions": len(valid_assertions),
        "rejected_t2_assertions": len(rejected_assertions),
        "h0a_compatible": sum((item.get("h0a") or {}).get("status") == "compatible" for item in normalized),
        "h0a_conflicting": sum((item.get("h0a") or {}).get("status") == "conflict" for item in normalized),
        "h0a_scene_affecting_conflicts": len(scene_conflicts),
        "h0a_non_scene_role_disagreements": len(non_scene_conflicts),
        "h0a_conflict_explanations": conflict_explanations,
        "later_outcome_correctly_excluded": sum(item.get("temporal_role") == "later_outcome" and not item.get("scene_constraint_candidate") for item in normalized),
        "quoted_or_background_correctly_excluded": sum(item.get("temporal_role") in {"quoted_precedent", "background_context"} and not item.get("scene_constraint_candidate") for item in normalized),
        "visible_anchor_recall_misses": recall_misses,
        "no_temporal_evidence_available": sorted(no_evidence),
        "temporal_evidence_missed": recall_misses,
        "false_temporal_promotions": false_promotions,
        "regression_checks": checks,
        "token_usage": usage,
        "median_latency_seconds": statistics.median(latencies) if latencies else None,
        "maximum_latency_seconds": max(latencies) if latencies else None,
        "temporal_lane_frozen": temporal_lane_frozen,
        "canonical_write_back": False,
    }


def replay_temporal_run(run_id: str) -> dict[str, Any]:
    """Recompute only derived temporal projections from immutable live cards."""

    base = OUT / "live" / run_id
    results = read_json(base / "temporal-results.json", []) or []
    if len(results) != 10:
        raise RuntimeError("stored_temporal_run_shape_invalid")
    for row in results:
        validation = ((row.get("temporal_fill") or {}).get("validation") or {})
        row["normalization"] = algorithm.normalize_story_temporal(validation, story_id=str(row.get("story_id")))
        row["deterministic_postprocessing_replay"] = True
    preflight_record = read_json(base / "preflight.json", {}) or {}
    metrics = temporal_metrics(results, preflight_record)
    write_json(base / "temporal-results.json", results)
    write_json(base / "metrics.json", metrics)
    manifest = read_json(base / "manifest.json", {}) or {}
    manifest["deterministic_postprocessing_replay"] = True
    write_json(base / "manifest.json", manifest)
    write_closeout_summary(run_id, metrics)
    return {"output": str(base), "metrics": metrics, "api_calls": 0}


def write_closeout_summary(run_id: str, temporal: Mapping[str, Any]) -> dict[str, Any]:
    person = read_json(OUT / "person-offline-replay.json", {}) or {}
    preflight_usage = (temporal.get("preflight") or {}).get("usage") or {}
    semantic_usage = temporal.get("token_usage") or {}
    summary = {
        "stage": "hng2-c3-final-algorithm-closeout",
        "run_id": run_id,
        "person": {
            "metrics": person.get("metrics"),
            "regression_checks": person.get("regression_checks"),
            "lane_frozen": person.get("person_lane_frozen"),
            "api_calls": 0,
        },
        "temporal": {
            "metrics": dict(temporal),
            "lane_frozen": temporal.get("temporal_lane_frozen"),
        },
        "deepseek": {
            "preflight_calls": 1,
            "semantic_calls": int(temporal.get("semantic_calls") or 0),
            "total_calls": 1 + int(temporal.get("semantic_calls") or 0),
            "semantic_tokens": dict(semantic_usage),
            "preflight_tokens": dict(preflight_usage),
            "total_tokens_including_preflight": int(semantic_usage.get("total_tokens") or 0) + int(preflight_usage.get("total_tokens") or 0),
        },
        "frozen_algorithm": {
            "person": "SELECT -> READ EVIDENCE ATOMS -> GROUND -> FILL -> RESOLVE/NORMALIZE -> CANDIDATE DB",
            "temporal": "SELECT -> VISIBLE ANCHOR SCAN -> READ TEMPORAL ATOMS -> GROUND -> FILL -> H0A NORMALIZATION -> CANDIDATE DB",
        },
        "all_lanes_frozen": bool(person.get("person_lane_frozen")) and bool(temporal.get("temporal_lane_frozen")),
        "candidate_projection_only": True,
        "canonical_write_back": False,
    }
    write_json(OUT / "closeout-summary.json", summary)
    return summary


def write_offline_replay() -> dict[str, Any]:
    replay = replay_person_outputs()
    write_json(OUT / "person-offline-replay.json", replay)
    return replay


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prepare", action="store_true")
    parser.add_argument("--offline-replay", action="store_true")
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--run-id", default=None)
    parser.add_argument("--replay-run", default=None)
    args = parser.parse_args()
    selection = ensure_selection()
    replay = write_offline_replay()
    if args.replay_run:
        print(json.dumps({"person_replay": replay["metrics"], **replay_temporal_run(args.replay_run)}, ensure_ascii=False, indent=2))
        return 0
    if args.prepare or (not args.offline_replay and not args.live):
        print(json.dumps({"selection": selection, "person_replay": replay["metrics"], "person_lane_frozen": replay["person_lane_frozen"]}, ensure_ascii=False, indent=2))
        return 0
    if args.offline_replay:
        print(json.dumps(replay, ensure_ascii=False, indent=2))
        return 0
    run_id = args.run_id or dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    result = run_temporal_live(selection, run_id=run_id)
    print(json.dumps({"person_replay": replay["metrics"], **result}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
