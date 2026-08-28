#!/usr/bin/env python3
"""HGE1-WB: adaptive, candidate-only Story growth after HGE1-WA.

Wave B deliberately imports the Wave A implementation for evidence windows,
frozen HNG2 calls, candidate projection, and graph component calculation.  It
only adds a deterministic adaptive sampling frame and an A+B comparison; the
semantic prompts and resolver behavior remain the frozen Wave A contract.
"""

from __future__ import annotations

import argparse
import collections
import datetime as dt
import hashlib
import json
import os
import statistics
import sys
import time
from pathlib import Path
from typing import Any, Mapping, Sequence

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import hda1_identity_audit as hda1  # noqa: E402
import hda2_identity_remediation as hda2  # noqa: E402
import hge1_wave_a as wave_a  # noqa: E402
import historical_context_algorithm as algorithm  # noqa: E402


ANNOTATION = ROOT / "data/annotation"
DERIVED = ROOT / "data/derived"
GENERATED = ROOT / "data/generated/hge1-wb"
MODEL = "deepseek-v4-flash"
RUN_VERSION = "hge1-wave-b-v1"
PROMPT_VERSION = wave_a.PROMPT_VERSION
SELECTION_PATH = ANNOTATION / "hge1-wave-b-selection.json"
TARGET_SELECTION_PATH = ANNOTATION / "hge1-wave-b-target-selection.json"
SERIES_PATH = ROOT / "data/generated/hge1/network-growth-series.json"


def read_json(path: Path, default: Any = None) -> Any:
    return wave_a.read_json(path, default)


def write_json(path: Path, value: Any) -> None:
    wave_a.write_json(path, value)


def stable_hash(value: Any) -> str:
    return wave_a.stable_hash(value)


def file_hash(path: Path) -> str:
    return wave_a.file_hash(path)


def utc_now() -> str:
    return wave_a.utc_now()


def text(value: Any) -> str:
    return hda1._text(value)


def corpus_index() -> dict[str, dict[str, Any]]:
    return wave_a.corpus_index()


def production_story_ids() -> set[str]:
    return wave_a.production_story_ids()


def wave_a_snapshot() -> dict[str, Any]:
    selection = read_json(wave_a.SELECTION_PATH, {}) or {}
    metrics = read_json(DERIVED / "hge1-wave-a-metrics.json", {}) or {}
    return {
        "selection_path": str(wave_a.SELECTION_PATH.relative_to(ROOT)),
        "selection_hash": selection.get("selection_hash"),
        "selection_file_hash": file_hash(wave_a.SELECTION_PATH) if wave_a.SELECTION_PATH.is_file() else None,
        "metrics_path": str((DERIVED / "hge1-wave-a-metrics.json").relative_to(ROOT)),
        "metrics_file_hash": file_hash(DERIVED / "hge1-wave-a-metrics.json") if (DERIVED / "hge1-wave-a-metrics.json").is_file() else None,
        "channel_yield": metrics.get("channel_yield", {}),
        "after": metrics.get("after", {}),
    }


def previous_story_snapshot() -> dict[str, Any]:
    ids, evidence = wave_a.prior_story_ids()
    wave_a_selection = read_json(wave_a.SELECTION_PATH, {}) or {}
    ids.update(text(value) for value in wave_a_selection.get("story_ids", []) or [])
    return {"story_ids": sorted(ids), "story_count": len(ids), "evidence": evidence, "hash": stable_hash({"story_ids": sorted(ids), "evidence": evidence})}


def _adaptive_score(feature: Mapping[str, Any], channel: str) -> int:
    relation = int(feature.get("relation_marker_count") or 0)
    known = int(feature.get("known_person_count") or 0)
    unresolved = int(feature.get("unresolved_surface_count") or 0)
    unknown = int(feature.get("unknown_name_signal") or 0)
    chapter_count = int(feature.get("chapter_story_count") or 1)
    if channel == "exploitation_relation_rich":
        return 8 * relation + 4 * known + 2 * unresolved + unknown
    if channel == "exploitation_underrepresented":
        return (1200 // max(1, chapter_count)) + 3 * relation + 2 * unknown + known
    if channel == "coverage_peripheral":
        return max(0, 12 - known) + unknown + max(0, 8 - relation)
    if channel == "coverage_underrepresented":
        return (1600 // max(1, chapter_count)) + unknown + max(0, 4 - known)
    return 0


def _pick(features: Mapping[str, Mapping[str, Any]], used: set[str], channel: str, quota: int, *, random_control: bool = False, chapter_used: set[str] | None = None) -> list[dict[str, Any]]:
    available = [feature for sid, feature in features.items() if sid not in used]
    if random_control:
        available.sort(key=lambda feature: (stable_hash({"wave": "HGE1-WB", "channel": channel, "story_id": feature.get("story_id")}), text(feature.get("story_id"))))
    else:
        available.sort(key=lambda feature: (-_adaptive_score(feature, channel), stable_hash({"channel": channel, "story_id": feature.get("story_id")} ), text(feature.get("story_id"))))
    chosen: list[dict[str, Any]] = []
    local_chapters: set[str] = set()
    for feature in available:
        chapter = text(feature.get("chapter_id"))
        if len(chosen) < quota and chapter and chapter not in local_chapters and (chapter_used is None or chapter not in chapter_used):
            chosen.append(feature)
            local_chapters.add(chapter)
            if chapter_used is not None:
                chapter_used.add(chapter)
    if len(chosen) < quota:
        for feature in available:
            if feature in chosen:
                continue
            chosen.append(feature)
            if len(chosen) >= quota:
                break
    return chosen[:quota]


def build_selection() -> dict[str, Any]:
    corpus = corpus_index()
    production = production_story_ids()
    prior = previous_story_snapshot()
    _, known_forms = wave_a._people_and_forms()
    excluded = production | set(prior["story_ids"])
    features = {
        sid: wave_a.story_features(row, known_forms, list(corpus.values()), [])
        for sid, row in corpus.items()
        if sid not in excluded and text(row.get("publication_scope")) != "published"
    }
    adaptive = wave_a_snapshot()
    channel_specs = [
        ("exploitation_relation_rich", "exploitation", 6),
        ("exploitation_underrepresented", "exploitation", 6),
        ("coverage_peripheral", "coverage", 4),
        ("coverage_underrepresented", "coverage", 3),
        ("random_control", "random_control", 5),
    ]
    selected: list[dict[str, Any]] = []
    used: set[str] = set()
    chapters: set[str] = set()
    for channel, parent_strategy, quota in channel_specs:
        chosen = _pick(features, used, channel, quota, random_control=channel == "random_control", chapter_used=chapters)
        for feature in chosen:
            sid = text(feature.get("story_id"))
            used.add(sid)
            row = corpus[sid]
            chapter = text(feature.get("chapter_id"))
            known_participants = [
                {"surface": hit.get("surface"), "person_ids": hit.get("person_ids", [])}
                for hit in feature.get("known_person_hits", [])[:10]
            ]
            selected.append({
                "story_id": sid,
                "selection_channel": channel,
                "parent_strategy": parent_strategy,
                "selection_key": stable_hash({"story_id": sid, "channel": channel, "feature": feature}),
                "selection_basis": {key: feature.get(key) for key in ("known_person_count", "unresolved_surface_count", "unknown_name_signal", "relation_marker_count", "temporal_marker_count", "chapter_story_count")},
                "wave_a_evidence": {
                    "source_channel_yield": adaptive.get("channel_yield", {}),
                    "selection_policy": "exploitation of highest Wave A relation/underrepresented yields plus coverage and deterministic controls",
                },
                "chapter_id": chapter,
                "chapter_heading": row.get("chapter_heading"),
                "known_participants_before": known_participants,
                "baseline_participant_count": int(feature.get("known_person_count") or 0),
                "graph_connectivity_class": "hub" if int(feature.get("known_person_count") or 0) >= 3 else ("connected" if int(feature.get("known_person_count") or 0) else "peripheral"),
                "production_visible": False,
                "source_refs": [f"hge1-wb-shishuo-main-{sid}"] + [f"hge1-wb-shishuo-liu-{sid}-{a.get('annotation_id')}" for a in row.get("liu_annotations", [])[:3] if isinstance(a, Mapping)],
                "source_hash": feature.get("source_sha256"),
            })
    selected.sort(key=lambda row: (text(row.get("selection_channel")), text(row.get("selection_key")), text(row.get("story_id"))))
    story_ids = [text(row.get("story_id")) for row in selected]
    core = {
        "schema": "hge1-wave-b-selection-v1",
        "wave_id": "HGE1-WB",
        "run_version": RUN_VERSION,
        "algorithm_version": "HNG2-C.3/HDB2-P2T-frozen-frontier-v1",
        "model": MODEL,
        "temperature": 0,
        "story_count": len(selected),
        "story_ids": story_ids,
        "records": selected,
        "adaptive_policy": {
            "exploitation_fraction": 0.5,
            "coverage_fraction": round(7 / 24, 6),
            "random_control_fraction": round(5 / 24, 6),
            "channel_targets": {channel: quota for channel, _, quota in channel_specs},
            "wave_a_snapshot": adaptive,
        },
        "production_scope_story_count": len(production),
        "prior_story_count": len(prior["story_ids"]),
        "prior_story_hash": prior["hash"],
        "prior_story_evidence": prior["evidence"],
        "overlap_with_production": sorted(set(story_ids) & production),
        "overlap_with_prior": sorted(set(story_ids) & set(prior["story_ids"])),
        "frozen_before_live": True,
        "candidate_only": True,
        "canonical_write_back": False,
        "selection_method": "deterministic adaptive HGE1-WA channel yield ranking; no Wave B model output used",
        "selection_hash": None,
    }
    core["selection_hash"] = stable_hash({key: value for key, value in core.items() if key != "selection_hash"})
    return core


def freeze_selection(path: Path = SELECTION_PATH) -> dict[str, Any]:
    proposed = build_selection()
    if path.is_file():
        existing = read_json(path, {}) or {}
        if existing != proposed:
            raise RuntimeError("hge1_wave_b_selection_changed")
        return existing
    write_json(path, proposed)
    return proposed


def build_target_selection(selection: Mapping[str, Any]) -> dict[str, Any]:
    people, known_forms = wave_a._people_and_forms()
    corpus = corpus_index()
    records: list[dict[str, Any]] = []
    for record in selection.get("records", []) or []:
        sid = text(record.get("story_id"))
        story = corpus.get(sid, {})
        targets = wave_a._target_rows(story, known_forms, people)
        normalized: list[dict[str, Any]] = []
        for index, target in enumerate(targets, 1):
            item = dict(target)
            item["target_id"] = f"hge1-wb-target-{sid}-p{index}"
            item["source_ref"] = f"hge1-wb-shishuo-main-{sid}"
            normalized.append(item)
        records.append({"story_id": sid, "targets": normalized})
    document = {
        "schema": "hge1-wave-b-target-selection-v1",
        "wave_id": "HGE1-WB",
        "selection_hash": selection.get("selection_hash"),
        "records": sorted(records, key=lambda row: row["story_id"]),
        "target_count": sum(len(row.get("targets", []) or []) for row in records),
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
            raise RuntimeError("hge1_wave_b_target_selection_changed")
        return existing
    write_json(path, proposed)
    return proposed


def build_wave_units(selection: Mapping[str, Any], target_selection: Mapping[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    corpus = corpus_index()
    targets_by_story = {text(row.get("story_id")): list(row.get("targets", []) or []) for row in target_selection.get("records", []) or []}
    person_units: list[dict[str, Any]] = []
    temporal_units: list[dict[str, Any]] = []
    for record in selection.get("records", []) or []:
        sid = text(record.get("story_id"))
        story = corpus.get(sid, {})
        for target in targets_by_story.get(sid, []):
            semantic_target = {key: value for key, value in target.items() if key != "known_existing_person_id"}
            person_units.append({"unit_id": target["target_id"], "story_id": sid, "target": semantic_target, "private_target": target, "story": {"story_id": sid, "chapter_heading": story.get("chapter_heading")}, "windows": wave_a.build_windows(story, target.get("surface", ""))})
        temporal_units.append({"unit_id": f"hge1-wb-temporal-{sid}", "story_id": sid, "story": {"story_id": sid, "chapter_heading": story.get("chapter_heading")}, "windows": wave_a.build_windows(story)})
    return person_units, temporal_units


def _preflight(timeout: int = 20) -> dict[str, Any]:
    started = time.monotonic()
    row: dict[str, Any] = {"model": MODEL, "start_time": utc_now()}
    try:
        response = wave_a.call_deepseek([{"role": "user", "content": "Reply only with OK"}], model=MODEL, temperature=0, max_tokens=8, thinking={"type": "disabled"}, timeout=timeout)
        row.update({"status": "reachable", "usage": wave_a._usage(response), "response_model": response.get("model")})
    except Exception as exc:
        row.update({"status": "live_network_unavailable", **wave_a._safe_error(exc)})
    row.update({"elapsed_seconds": round(time.monotonic() - started, 3), "end_time": utc_now()})
    return row


def _semantic_call_with_retry(lane: str, unit_id: str, prompt: Mapping[str, Any], raw_dir: Path, sequence: int) -> tuple[list[dict[str, Any]], Mapping[str, Any] | None]:
    """Retry only transport/parse/truncation failures with the same packet."""
    attempts: list[dict[str, Any]] = []
    payload: Mapping[str, Any] | None = None
    for attempt in (1, 2):
        record, payload = wave_a.semantic_call(lane, unit_id, prompt, raw_dir, sequence, attempt=attempt)
        if attempt > 1:
            record["retry_of_sequence"] = sequence
        attempts.append(record)
        if payload is not None:
            break
    return attempts, payload


def run_units(selection: Mapping[str, Any], target_selection: Mapping[str, Any], *, live: bool, run_id: str) -> dict[str, Any]:
    person_units, temporal_units = build_wave_units(selection, target_selection)
    base = GENERATED / "live" / run_id
    raw_dir = base / "raw-api"
    raw_dir.mkdir(parents=True, exist_ok=True)
    preflight = _preflight() if live else {"status": "offline_not_requested", "model": MODEL}
    transport: list[dict[str, Any]] = []
    person_results: list[dict[str, Any]] = []
    sequence = 0
    for unit in person_units:
        sequence += 1
        p1_prompt = algorithm.person_read_prompt(unit["target"], unit["windows"])
        if live and preflight.get("status") == "reachable":
            p1_attempts, p1_payload = _semantic_call_with_retry("person_read", unit["unit_id"], p1_prompt, raw_dir, sequence)
            transport.extend(p1_attempts)
            p1_transport = p1_attempts[-1]
        else:
            p1_payload, _ = wave_a._fixture_person(unit)
            p1_transport = {"lane": "person_read", "unit_id": unit["unit_id"], "classification": "offline_fixture", "usage": {}}
        p1_validation = algorithm.validate_person_atoms(p1_payload, unit["windows"])
        sequence += 1
        p2_prompt = algorithm.person_atom_fill_prompt(unit["target"], p1_validation, unit["windows"])
        if live and preflight.get("status") == "reachable":
            p2_attempts, p2_payload = _semantic_call_with_retry("person_fill", unit["unit_id"], p2_prompt, raw_dir, sequence)
            transport.extend(p2_attempts)
            p2_transport = p2_attempts[-1]
        else:
            _, p2_payload = wave_a._fixture_person(unit)
            p2_transport = {"lane": "person_fill", "unit_id": unit["unit_id"], "classification": "offline_fixture", "usage": {}}
        fill_refs = {text(atom.get("evidence_ref")) for atom in p1_validation.get("valid_atoms", []) or []}
        p2_validation = algorithm.validate_person_fill(p2_payload, [row for row in unit["windows"] if text(row.get("ref")) in fill_refs])
        person_results.append({"unit_id": unit["unit_id"], "story_id": unit["story_id"], "target": unit["target"], "private_target": unit["private_target"], "windows": unit["windows"], "person_read": {"prompt": p1_prompt, "payload": p1_payload, "validation": p1_validation, "transport": p1_transport}, "person_fill": {"prompt": p2_prompt, "payload": p2_payload, "validation": p2_validation, "transport": p2_transport}})
    temporal_results: list[dict[str, Any]] = []
    for unit in temporal_units:
        sequence += 1
        visible = algorithm.scan_visible_temporal_anchors(unit["windows"])
        t1_prompt = algorithm.temporal_read_prompt(unit["story"], unit["windows"], visible_temporal_surfaces=visible)
        if live and preflight.get("status") == "reachable":
            t1_attempts, t1_payload = _semantic_call_with_retry("temporal_read", unit["unit_id"], t1_prompt, raw_dir, sequence)
            transport.extend(t1_attempts)
            t1_transport = t1_attempts[-1]
        else:
            t1_payload, _ = wave_a._fixture_temporal(unit)
            t1_transport = {"lane": "temporal_read", "unit_id": unit["unit_id"], "classification": "offline_fixture", "usage": {}}
        t1_validation = algorithm.validate_temporal_atoms(t1_payload, unit["windows"])
        sequence += 1
        t2_prompt = algorithm.temporal_atom_fill_prompt(unit["story"], t1_validation, unit["windows"])
        if live and preflight.get("status") == "reachable":
            t2_attempts, t2_payload = _semantic_call_with_retry("temporal_fill", unit["unit_id"], t2_prompt, raw_dir, sequence)
            transport.extend(t2_attempts)
            t2_transport = t2_attempts[-1]
        else:
            _, t2_payload = wave_a._fixture_temporal(unit)
            t2_transport = {"lane": "temporal_fill", "unit_id": unit["unit_id"], "classification": "offline_fixture", "usage": {}}
        fill_refs = {text(atom.get("evidence_ref")) for atom in t1_validation.get("valid_atoms", []) or []}
        t2_validation = algorithm.validate_temporal_fill(t2_payload, [row for row in unit["windows"] if text(row.get("ref")) in fill_refs])
        temporal_results.append({"unit_id": unit["unit_id"], "story_id": unit["story_id"], "story": unit["story"], "windows": unit["windows"], "visible_temporal_surfaces": visible, "temporal_read": {"prompt": t1_prompt, "payload": t1_payload, "validation": t1_validation, "transport": t1_transport}, "temporal_fill": {"prompt": t2_prompt, "payload": t2_payload, "validation": t2_validation, "transport": t2_transport}})
    manifest = {"schema": "hge1-wave-b-live-manifest-v1", "run_id": run_id, "run_version": RUN_VERSION, "prompt_version": PROMPT_VERSION, "selection_hash": selection.get("selection_hash"), "target_selection_hash": target_selection.get("target_selection_hash"), "preflight": preflight, "live_requested": live, "semantic_call_count_expected": 2 * len(person_units) + 2 * len(temporal_units), "wave_a_snapshot": wave_a_snapshot(), "hda2_input_hashes": hda2.hda1_inputs(), "protected_hashes_before": hda1.protected_hashes(), "candidate_only": True, "canonical_write_back": False}
    write_json(base / "manifest.json", manifest)
    write_json(base / "selection.json", selection)
    write_json(base / "target-selection.json", target_selection)
    write_json(base / "story-contexts.json", [{"story_id": unit["story_id"], "windows": unit["windows"]} for unit in temporal_units])
    write_json(base / "person-results.json", person_results)
    write_json(base / "temporal-results.json", temporal_results)
    write_json(base / "transport.json", transport)
    return {"base": base, "person_results": person_results, "temporal_results": temporal_results, "transport": transport, "preflight": preflight, "person_units": person_units, "temporal_units": temporal_units, "target_selection": target_selection}


def _hda2_effect(candidate_db: Mapping[str, Any]) -> dict[str, Any]:
    overlay = read_json(hda2.OUT / "repair-overlay.json", []) or []
    if isinstance(overlay, Mapping):
        overlay = overlay.get("records", []) or overlay.get("items", []) or []
    wave_stories = {text(row.get("story_id")) for row in candidate_db.get("story_summary", []) or []}
    # HDA2 overlays are occurrence-scoped.  A matching surface in a different
    # Story is not permission to apply a remediation to this wave.
    relevant = [row for row in overlay if text(row.get("story_id")) in wave_stories]
    return {"overlay_claim_count": len(overlay), "candidate_surfaces_suppressed": sorted({text(row.get("target_surface")) for row in relevant if text(row.get("action")) == "suppress_claim"}), "incorrect_existing_person_links_prevented": sum(text(row.get("action")) == "suppress_claim" for row in relevant), "candidate_mappings_recovered": sum(text(row.get("action")) == "replace_with_existing_person_candidate" for row in relevant), "stories_changed": sorted({text(row.get("story_id")) for row in relevant}), "applied_to_wave": bool(relevant), "candidate_only": True, "canonical_write_back": False}


def build_projection(selection: Mapping[str, Any], run: Mapping[str, Any]) -> dict[str, Any]:
    """Use the Wave A frozen projection and change only wave labels."""
    candidate_db = dict(wave_a.build_projection(selection, run))
    candidate_db["schema"] = "hge1-wave-b-candidate-db-v1"
    candidate_db["wave_id"] = "HGE1-WB"
    candidate_db["hda2_effect"] = _hda2_effect(candidate_db)
    candidate_db["candidate_only"] = True
    candidate_db["canonical_write_back"] = False
    return candidate_db


def _graph_with_waves(selections: Sequence[Mapping[str, Any]], databases: Sequence[Mapping[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    base_graph = read_json(DERIVED / "hg0-graph-projection.json", {}) or {}
    nodes = [dict(node) for node in base_graph.get("nodes", []) or [] if isinstance(node, Mapping)]
    edges = [dict(edge) for edge in base_graph.get("edges", []) or [] if isinstance(edge, Mapping)]
    node_keys = {(node.get("node_type"), node.get("node_id")) for node in nodes}
    for selection, database in zip(selections, databases):
        wave = text(selection.get("wave_id")) or "HGE1"
        for candidate in database.get("candidate_persons", []) or []:
            key = ("Person", text(candidate.get("candidate_person_id")))
            if key not in node_keys:
                nodes.append({"node_type": "Person", "node_id": key[1], "label": candidate.get("canonical_name"), "review_status": "candidate", "scope_role": "research_candidate"})
                node_keys.add(key)
        for story_id in selection.get("story_ids", []) or []:
            key = ("Story", text(story_id))
            if key not in node_keys:
                nodes.append({"node_type": "Story", "node_id": key[1], "label": key[1], "review_status": "candidate", "scope_role": "research_candidate"})
                node_keys.add(key)
        for row in database.get("person_observations", []) or []:
            endpoint = text(row.get("person_id") or row.get("candidate_person_id"))
            story_id = text(row.get("story_id"))
            if not endpoint or not story_id:
                continue
            edge = {"edge_id": f"{wave.lower()}-person-story-{stable_hash({'wave': wave, 'row': row})[:20]}", "edge_type": "candidate_person_story_link", "source": {"node_type": "Person", "node_id": endpoint}, "target": {"node_type": "Story", "node_id": story_id}, "candidate_only": True, "canonical_write_back": False}
            if edge["edge_id"] not in {text(item.get("edge_id")) for item in edges}:
                edges.append(edge)
    return nodes, edges


def _relation_family_counts(database: Mapping[str, Any]) -> dict[str, int]:
    counts = collections.Counter()
    for row in database.get("relation_candidates", []) or []:
        family = text(row.get("relation_class"))
        if family in {"kinship", "marriage", "office", "institutional"}:
            counts[family] += 1
    return {"kinship": counts["kinship"], "marriage": counts["marriage"], "office": counts["office"] + counts["institutional"], "social": len(database.get("relation_candidates", []) or [])}


def _wave_relation_endpoint_stats(run: Mapping[str, Any]) -> dict[str, int]:
    people, known_forms = wave_a._people_and_forms()
    existing = set(people)
    complete_existing = 0
    complete_any = 0
    for result in run.get("person_results", []) or []:
        validation = result.get("person_fill", {}).get("validation") or {}
        entities = {text(row.get("entity_key")): text(row.get("surface")) for row in validation.get("valid_entities", []) or []}
        private = result.get("private_target") or {}
        if private.get("known_existing_person_id"):
            entities["e0"] = text(private.get("known_existing_person_id"))
        for relation in validation.get("valid_relations", []) or []:
            subject = entities.get(text(relation.get("subject_entity_key")), "")
            obj = entities.get(text(relation.get("object_entity_key")), "")
            subject_pids = known_forms.get(subject, set()) if subject not in existing else {subject}
            object_pids = known_forms.get(obj, set()) if obj not in existing else {obj}
            subject_pids = {pid for pid in subject_pids if pid in existing}
            object_pids = {pid for pid in object_pids if pid in existing}
            if subject_pids and object_pids and subject_pids.isdisjoint(object_pids):
                complete_existing += 1
            if (subject_pids or subject) and (object_pids or obj) and subject != obj:
                complete_any += 1
    return {"existing_node_edges": complete_existing, "candidate_aware_relation_edges": complete_any}


def _channel_yield(selection: Mapping[str, Any], database: Mapping[str, Any]) -> dict[str, dict[str, float | int]]:
    """Summarize Wave B yield by its frozen sampling channel."""
    channels = {
        text(row.get("selection_channel")): []
        for row in selection.get("records", []) or []
        if text(row.get("selection_channel"))
    }
    by_story = {text(row.get("story_id")): row for row in database.get("story_summary", []) or []}
    for record in selection.get("records", []) or []:
        channel = text(record.get("selection_channel"))
        story = by_story.get(text(record.get("story_id")))
        if channel and story:
            channels.setdefault(channel, []).append(story)
    output: dict[str, dict[str, float | int]] = {}
    for channel, rows in sorted(channels.items()):
        count = len(rows)
        totals = {
            "story_count": count,
            "new_person_candidates": sum(int(row.get("new_identity_candidates") or 0) for row in rows),
            "existing_person_links": sum(len(row.get("existing_persons_recovered", []) or []) for row in rows),
            "relation_candidates": sum(int(row.get("relation_candidates") or 0) for row in rows),
            "unresolved": sum(int(row.get("unresolved_references") or 0) for row in rows),
            "review_items": sum(int(row.get("review_load") or 0) for row in rows),
        }
        for key, value in list(totals.items()):
            if key == "story_count":
                continue
            totals[f"{key}_per_story"] = round(value / count, 6) if count else 0
        output[channel] = totals
    return output


def growth_projection(base: Mapping[str, Any], wave_a_selection: Mapping[str, Any], wave_a_db: Mapping[str, Any], wave_a_growth: Mapping[str, Any], selection: Mapping[str, Any], database: Mapping[str, Any], run: Mapping[str, Any]) -> dict[str, Any]:
    a_nodes, a_edges = _graph_with_waves([wave_a_selection], [wave_a_db])
    ab_nodes, ab_edges = _graph_with_waves([wave_a_selection, selection], [wave_a_db, database])
    a_summary = wave_a._components(a_nodes, a_edges)
    ab_summary = wave_a._components(ab_nodes, ab_edges)
    b_story_count = len(selection.get("story_ids", []) or [])
    b_candidates = list(database.get("candidate_persons", []) or [])
    b_person_obs = list(database.get("person_observations", []) or [])
    b_relation_count = len(database.get("relation_candidates", []) or [])
    b_fact_counts = _relation_family_counts(database)
    a_fact_counts = _relation_family_counts(wave_a_db)
    before_b = dict(wave_a_growth.get("after", {}) or {})
    after = dict(before_b)
    after.update({
        "story_count": int(before_b.get("story_count") or 0) + b_story_count,
        "existing_person_count": int(before_b.get("existing_person_count") or 0),
        "candidate_person_count": int(base.get("candidate_person_count") or 0) + len(wave_a_db.get("candidate_persons", []) or []) + len(b_candidates),
        "person_story_count": int(base.get("person_story_count") or 0) + len(wave_a_db.get("person_observations", []) or []) + len(b_person_obs),
        "identity_occurrence_count": int(base.get("identity_occurrence_count") or 0) + len(wave_a_db.get("person_observations", []) or []) + len(b_person_obs),
        "kinship_fact_or_candidate_count": int(base.get("kinship_fact_or_candidate_count") or 0) + a_fact_counts["kinship"] + b_fact_counts["kinship"],
        "marriage_fact_or_candidate_count": int(base.get("marriage_fact_or_candidate_count") or 0) + a_fact_counts["marriage"] + b_fact_counts["marriage"],
        "office_fact_count": int(base.get("office_fact_count") or 0) + a_fact_counts["office"] + b_fact_counts["office"],
        "social_relation_edge_count": int(base.get("social_relation_edge_count") or 0) + a_fact_counts["social"] + b_fact_counts["social"],
        "graph_nodes": ab_summary["node_count"],
        "graph_edges": ab_summary["edge_count"],
        "connected_components": ab_summary["connected_component_count"],
        "largest_component_size": ab_summary["largest_component_size"],
        "isolated_orphan_nodes": ab_summary["isolated_node_count"],
        "unresolved_identity_count": int(base.get("unresolved_identity_count") or 0) + sum(row.get("status") == "unresolved" for row in wave_a_db.get("person_observations", []) or []) + sum(row.get("status") == "unresolved" for row in b_person_obs),
    })
    delta = {key: after.get(key, 0) - before_b.get(key, 0) for key in after if isinstance(after.get(key), (int, float)) and isinstance(before_b.get(key), (int, float))}
    b_person_nodes = len({text(row.get("candidate_person_id") or row.get("person_id")) for row in b_person_obs if text(row.get("candidate_person_id") or row.get("person_id"))})
    b_graph_edges = ab_summary["edge_count"] - a_summary["edge_count"]
    endpoint_stats = _wave_relation_endpoint_stats(run)
    return {
        "schema": "hge1-wave-b-growth-projection-v1",
        "wave_id": "HGE1-WB",
        "baseline": dict(base),
        "wave_a_after_frozen": dict(wave_a_growth.get("after", {}) or {}),
        "before_wave_b": before_b,
        "after": after,
        "delta_from_wave_a": delta,
        "wave_a_graph_summary_recomputed": a_summary,
        "combined_graph_summary": ab_summary,
        "wave_b_candidate_person_ids": sorted(text(row.get("candidate_person_id")) for row in b_candidates),
        "wave_b_existing_persons_reached": sorted({text(row.get("person_id")) for row in b_person_obs if text(row.get("person_id"))}),
        "wave_b_fact_counts": b_fact_counts,
        "wave_a_fact_counts_recomputed": a_fact_counts,
        "channel_yield": _channel_yield(selection, database),
        "wave_b_relation_endpoint_stats": endpoint_stats,
        "node_novelty_rate": round(b_person_nodes / b_story_count, 6) if b_story_count else 0,
        "candidate_node_novelty_rate": round(len(b_candidates) / b_story_count, 6) if b_story_count else 0,
        "edge_novelty_rate": round(b_graph_edges / b_story_count, 6) if b_story_count else 0,
        "densification_rate": round(endpoint_stats["existing_node_edges"] / b_story_count, 6) if b_story_count else 0,
        "existing_node_edge_share": round(endpoint_stats["existing_node_edges"] / b_graph_edges, 6) if b_graph_edges else 0,
        "new_edges": b_graph_edges,
        "new_candidate_persons": len(b_candidates),
        "new_existing_person_links": len({text(row.get("person_id")) for row in b_person_obs if text(row.get("person_id"))}),
        "candidate_only": True,
        "canonical_write_back": False,
    }


def _series_row(wave: str, metrics: Mapping[str, Any], review_load: int) -> dict[str, Any]:
    return {"wave": wave, "story_count": metrics.get("story_count"), "existing_person_count": metrics.get("existing_person_count"), "candidate_person_count": metrics.get("candidate_person_count"), "person_story_count": metrics.get("person_story_count"), "graph_nodes": metrics.get("graph_nodes"), "graph_edges": metrics.get("graph_edges"), "connected_components": metrics.get("connected_components"), "largest_component": metrics.get("largest_component_size"), "unresolved_identity_count": metrics.get("unresolved_identity_count"), "human_review_load": review_load}


def build_series(base: Mapping[str, Any], wave_a_growth: Mapping[str, Any], wave_a_db: Mapping[str, Any], wave_b_growth: Mapping[str, Any], database: Mapping[str, Any]) -> dict[str, Any]:
    old = read_json(SERIES_PATH, {}) or {}
    old_rows = list(old.get("series", []) or [])
    old_by_wave = {text(row.get("wave")): dict(row) for row in old_rows}
    baseline_row = dict(old_by_wave.get("baseline", {}))
    wave_a_row = dict(old_by_wave.get("HGE1-WA", {}))
    # Preserve every historical Wave A scalar; fill only fields that the
    # original compact series did not yet expose.
    baseline_row.update({key: value for key, value in _series_row("baseline", base, 0).items() if key not in baseline_row})
    wave_a_row.update({key: value for key, value in _series_row("HGE1-WA", wave_a_growth.get("after", {}), len(wave_a_db.get("review_items", []) or [])).items() if key not in wave_a_row})
    wave_b_row = _series_row("HGE1-WB", wave_b_growth.get("after", {}), len(database.get("review_items", []) or []))
    rows = [baseline_row, wave_a_row, wave_b_row]
    marginal = [
        {"from": "baseline", "to": "HGE1-WA", "delta_stories": int(wave_a_growth.get("after", {}).get("story_count") or 0) - int(base.get("story_count") or 0), "delta_persons": int(wave_a_growth.get("after", {}).get("existing_person_count") or 0) + int(wave_a_growth.get("after", {}).get("candidate_person_count") or 0) - (int(base.get("existing_person_count") or 0) + int(base.get("candidate_person_count") or 0)), "delta_candidate_persons": int(wave_a_growth.get("after", {}).get("candidate_person_count") or 0) - int(base.get("candidate_person_count") or 0), "delta_edges": int(wave_a_growth.get("after", {}).get("graph_edges") or 0) - int(base.get("graph_edges") or 0)},
        {"from": "HGE1-WA", "to": "HGE1-WB", "delta_stories": int(wave_b_growth.get("after", {}).get("story_count") or 0) - int(wave_b_growth.get("before_wave_b", {}).get("story_count") or 0), "delta_persons": int(wave_b_growth.get("after", {}).get("existing_person_count") or 0) + int(wave_b_growth.get("after", {}).get("candidate_person_count") or 0) - (int(wave_b_growth.get("before_wave_b", {}).get("existing_person_count") or 0) + int(wave_b_growth.get("before_wave_b", {}).get("candidate_person_count") or 0)), "delta_candidate_persons": int(wave_b_growth.get("after", {}).get("candidate_person_count") or 0) - int(wave_b_growth.get("before_wave_b", {}).get("candidate_person_count") or 0), "delta_edges": int(wave_b_growth.get("after", {}).get("graph_edges") or 0) - int(wave_b_growth.get("before_wave_b", {}).get("graph_edges") or 0), "delta_existing_node_edges": wave_b_growth.get("wave_b_relation_endpoint_stats", {}).get("existing_node_edges", 0)},
    ]
    return {"schema": "hge1-network-growth-series-v2", "series": rows, "marginal_derivatives": marginal, "wave_a_values_preserved": True, "candidate_only": True, "canonical_write_back": False}


def operational_metrics(run: Mapping[str, Any]) -> dict[str, Any]:
    transport = [row for row in run.get("transport", []) or [] if isinstance(row, Mapping)]
    classes = collections.Counter(text(row.get("classification")) for row in transport)
    usages = [row.get("usage") for row in transport if isinstance(row.get("usage"), Mapping)]
    latencies = [float(row.get("elapsed_seconds") or 0) for row in transport]
    pending: list[dict[str, Any]] = []
    for lane_key, rows in (("person_read", run.get("person_results", []) or []), ("person_fill", run.get("person_results", []) or []), ("temporal_read", run.get("temporal_results", []) or []), ("temporal_fill", run.get("temporal_results", []) or [])):
        child_key = lane_key
        for result in rows:
            transport_row = (result.get(child_key) or {}).get("transport") if isinstance(result, Mapping) else {}
            if isinstance(transport_row, Mapping) and text(transport_row.get("classification")) not in {"parsed", "offline_fixture"}:
                pending.append({"lane": lane_key, "unit_id": result.get("unit_id"), "classification": transport_row.get("classification")})
    return {"model": MODEL, "semantic_calls": len(transport), "expected_semantic_calls": 2 * len(run.get("person_units", []) or []) + 2 * len(run.get("temporal_units", []) or []), "retries": sum(1 for row in transport if int(row.get("attempt") or 1) > 1), "provider_failures": classes["provider_request_failure"], "parse_failures": classes["response_parse_failure"], "truncated_responses": classes["response_truncated"], "prompt_tokens": sum(int(row.get("prompt_tokens") or 0) for usage in usages for row in [usage]), "completion_tokens": sum(int(row.get("completion_tokens") or 0) for usage in usages for row in [usage]), "total_tokens": sum(int(row.get("total_tokens") or 0) for usage in usages for row in [usage]), "median_latency_seconds": round(statistics.median(latencies), 3) if latencies else 0, "max_latency_seconds": round(max(latencies), 3) if latencies else 0, "preflight": dict(run.get("preflight") or {}), "offline_fixture_used": not bool(transport), "pending_semantic_units": pending, "live_incomplete": bool(pending)}


def write_outputs(selection: Mapping[str, Any], target_selection: Mapping[str, Any], run: Mapping[str, Any]) -> dict[str, Any]:
    database = build_projection(selection, run)
    base = wave_a.baseline()
    wave_a_selection = read_json(wave_a.SELECTION_PATH, {}) or {}
    wave_a_db = read_json(DERIVED / "hge1-wave-a-candidate-db.json", {}) or {}
    wave_a_growth = read_json(DERIVED / "hge1-wave-a-metrics.json", {}) or {}
    growth = growth_projection(base, wave_a_selection, wave_a_db, wave_a_growth, selection, database, run)
    series = build_series(base, wave_a_growth, wave_a_db, growth, database)
    run_base: Path = run["base"]
    write_json(run_base / "candidate-db.json", database)
    write_json(run_base / "production-summary.json", {"selection_hash": selection.get("selection_hash"), "story_summary": database.get("story_summary", []), "operational_metrics": operational_metrics(run), "growth": growth, "hda2_effect": database.get("hda2_effect"), "candidate_only": True, "canonical_write_back": False})
    write_json(run_base / "rejected-items.json", {"records": database.get("rejected_items", []), "candidate_only": True, "canonical_write_back": False})
    for filename, key in [("hge1-wave-b-person-candidates.json", "person_observations"), ("hge1-wave-b-relation-candidates.json", "relation_candidates"), ("hge1-wave-b-temporal-candidates.json", "temporal_candidates")]:
        write_json(ANNOTATION / filename, {"schema": f"{key}-v1", "wave_id": "HGE1-WB", "records": database.get(key, []), "candidate_only": True, "canonical_write_back": False})
    write_json(ANNOTATION / "hge1-wave-b-review-queue.json", {"schema": "hge1-wave-b-review-queue-v1", "records": database.get("review_items", []), "candidate_only": True, "canonical_write_back": False})
    write_json(DERIVED / "hge1-wave-b-candidate-db.json", database)
    write_json(DERIVED / "hge1-wave-b-metrics.json", growth)
    write_json(DERIVED / "hge1-wave-b-gap-audit.json", {"schema": "hge1-wave-b-gap-audit-v1", "story_summary": database.get("story_summary", []), "rejected_items": database.get("rejected_items", []), "hda2_effect": database.get("hda2_effect"), "candidate_only": True, "canonical_write_back": False})
    write_json(SERIES_PATH, series)
    return {"database": database, "growth": growth, "series": series, "base": base}


def rebuild_from_run(run_id: str) -> dict[str, Any]:
    """Rebuild Wave B projections from an immutable live run without API calls."""
    base = GENERATED / "live" / run_id
    if not base.is_dir():
        raise FileNotFoundError(base)
    selection = freeze_selection()
    target_selection = freeze_target_selection(selection)
    person_units, temporal_units = build_wave_units(selection, target_selection)
    manifest = read_json(base / "manifest.json", {}) or {}
    run = {
        "base": base,
        "person_results": read_json(base / "person-results.json", []) or [],
        "temporal_results": read_json(base / "temporal-results.json", []) or [],
        "transport": read_json(base / "transport.json", []) or [],
        "preflight": manifest.get("preflight", {}),
        "person_units": person_units,
        "temporal_units": temporal_units,
        "target_selection": target_selection,
    }
    return {"run": run, **write_outputs(selection, target_selection, run)}


def validate_selection(selection: Mapping[str, Any]) -> list[str]:
    errors: list[str] = []
    ids = [text(value) for value in selection.get("story_ids", []) or []]
    prior = set(selection.get("prior_story_ids", []) or [])
    if len(ids) != 24 or len(set(ids)) != 24:
        errors.append("story_count_not_exactly_24_or_duplicate")
    if len(set(ids) & production_story_ids()):
        errors.append("production_overlap")
    if selection.get("overlap_with_production") != [] or selection.get("overlap_with_prior") != []:
        errors.append("declared_overlap")
    if selection.get("frozen_before_live") is not True:
        errors.append("not_frozen_before_live")
    if selection.get("candidate_only") is not True or selection.get("canonical_write_back") is not False:
        errors.append("candidate_boundary")
    expected = stable_hash({key: value for key, value in selection.items() if key != "selection_hash"})
    if selection.get("selection_hash") != expected:
        errors.append("selection_hash_invalid")
    if prior and set(ids) & prior:
        errors.append("prior_story_overlap")
    return errors


def validate_target_selection(selection: Mapping[str, Any], target: Mapping[str, Any]) -> list[str]:
    errors: list[str] = []
    if target.get("selection_hash") != selection.get("selection_hash"):
        errors.append("parent_selection_hash")
    expected = stable_hash({key: value for key, value in target.items() if key != "target_selection_hash"})
    if target.get("target_selection_hash") != expected:
        errors.append("target_selection_hash_invalid")
    if target.get("candidate_only") is not True or target.get("canonical_write_back") is not False:
        errors.append("target_boundary")
    expected_stories = set(text(value) for value in selection.get("story_ids", []) or [])
    actual_stories = {text(row.get("story_id")) for row in target.get("records", []) or []}
    if actual_stories != expected_stories:
        errors.append("target_story_coverage")
    corpus = corpus_index()
    for row in target.get("records", []) or []:
        main = text((corpus.get(text(row.get("story_id"))) or {}).get("main_text"))
        targets = list(row.get("targets", []) or [])
        if not 1 <= len(targets) <= 2:
            errors.append(f"target_count:{row.get('story_id')}")
        for item in targets:
            if not text(item.get("surface")) or text(item.get("surface")) not in main:
                errors.append(f"target_not_grounded:{row.get('story_id')}")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prepare", action="store_true")
    parser.add_argument("--offline", action="store_true")
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--run-id")
    parser.add_argument("--rebuild-run")
    args = parser.parse_args()
    selection = freeze_selection()
    errors = validate_selection(selection)
    if errors:
        raise SystemExit(";".join(errors))
    target = freeze_target_selection(selection)
    if args.rebuild_run:
        output = rebuild_from_run(args.rebuild_run)
        print(json.dumps({"run_id": args.rebuild_run, "story_count": selection["story_count"], "growth": output["growth"], "candidate_only": True, "canonical_write_back": False}, ensure_ascii=False, indent=2, sort_keys=True))
        return 0
    if args.prepare or not args.live and not args.offline:
        print(json.dumps({"story_count": selection["story_count"], "story_ids": selection["story_ids"], "selection_hash": selection["selection_hash"], "target_count": target["target_count"], "target_selection_hash": target["target_selection_hash"], "adaptive_policy": selection["adaptive_policy"], "candidate_only": True, "canonical_write_back": False}, ensure_ascii=False, indent=2, sort_keys=True))
        return 0
    run_id = args.run_id or (dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ") if args.live else "offline")
    run = run_units(selection, target, live=args.live, run_id=run_id)
    output = write_outputs(selection, target, run)
    print(json.dumps({"run_id": run_id, "story_count": selection["story_count"], "person_targets": len(run["person_units"]), "semantic_calls": len(run["transport"]), "preflight": run["preflight"], "growth": output["growth"]}, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
