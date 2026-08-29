#!/usr/bin/env python3
"""Validate the committed SFH1 experimental projection."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from semantic_first.analysis import protected_hashes
from semantic_first.common import OUT, file_hash, read_json, stable_hash, text
from semantic_first.source_packets import validation_universe


def validate() -> list[str]:
    errors: list[str] = []
    required = [
        "manifest.json", "story-packets.json", "mention-results.json", "validated-mentions.json",
        "reference-semantics.json", "candidate-sets.json", "identity-judgments.json",
        "constrained-decisions.json", "final-decisions.json", "relation-assertions.json",
        "temporal-semantics.json", "mention-audit.json", "metrics.json",
        "hge1-recalibrated-growth-series.json", "python-semantic-heuristic-audit.json",
        "random-blind-audit.json",
    ]
    for name in required:
        if not (OUT / name).is_file():
            errors.append(f"missing_artifact:{name}")
    if errors:
        return errors
    manifest = read_json(OUT / "manifest.json", {}) or {}
    universe = validation_universe()
    if int(universe.get("current_story_count") or 0) != 187 or int(manifest.get("story_count") or 0) != int(universe.get("story_count") or 0):
        errors.append("story_universe_not_frozen_187_plus_regressions")
    if text(manifest.get("universe_hash")) != text(universe.get("universe_hash")):
        errors.append("universe_hash_drift")
    for name, expected in (manifest.get("artifact_hashes") or {}).items():
        path = OUT / name
        if path.is_file() and stable_hash(read_json(path)) != expected:
            errors.append(f"artifact_hash_drift:{name}")
    if manifest.get("protected_hashes") != protected_hashes():
        errors.append("protected_historical_truth_hash_drift")
    packets = read_json(OUT / "story-packets.json", {}) or {}
    packet_evidence = {text(evidence.get("evidence_id")): text(evidence.get("text")) for packet in packets.get("packets", []) or [] for evidence in packet.get("evidence", []) or []}
    mentions = (read_json(OUT / "validated-mentions.json", {}) or {}).get("records", []) or []
    mention_ids: set[str] = set()
    for row in mentions:
        mention_id = text(row.get("mention_id")); evidence_id = text(row.get("source_evidence_id")); surface = text(row.get("surface"))
        if not mention_id or mention_id in mention_ids:
            errors.append(f"duplicate_or_empty_mention_id:{mention_id}")
        mention_ids.add(mention_id)
        if evidence_id not in packet_evidence or surface not in packet_evidence.get(evidence_id, ""):
            errors.append(f"ungrounded_mention:{mention_id}")
        start = row.get("source_start"); end = row.get("source_end")
        if not isinstance(start, int) or not isinstance(end, int) or packet_evidence.get(evidence_id, "")[start:end] != surface:
            errors.append(f"invalid_offsets:{mention_id}")
    decisions = (read_json(OUT / "final-decisions.json", {}) or {}).get("records", []) or []
    if any(text(row.get("person_id")).startswith("person-") and text(row.get("person_id")) not in {text(p.get("person_id")) for p in (read_json(ROOT / "data/people.json", {}) or {}).get("people", []) or []} for row in decisions):
        errors.append("llm_created_production_person_id")
    if any(row.get("candidate_only") is not True or row.get("canonical_write_back") is not False for row in decisions):
        errors.append("storage_gate_flags_invalid")
    if any(text(row.get("entity_kind")) == "non_person" and (row.get("person_id") or row.get("candidate_person_id")) for row in decisions):
        errors.append("non_person_candidate_anomaly")
    audit = read_json(OUT / "mention-audit.json", {}) or {}
    known = audit.get("known_regressions") or {}
    if int(known.get("known_boundary_failures") or 0):
        errors.append("known_boundary_regression")
    if int(known.get("forbidden_stable_resolution_count") or 0):
        errors.append("forbidden_stable_resolution")
    by_story = {}
    for row in decisions:
        by_story.setdefault(text(row.get("story_id")), []).append(row)
    mechanically_one = sum(sum(bool(item.get("candidate_person_id")) for item in rows) == 1 for rows in by_story.values())
    if decisions and mechanically_one == len(by_story):
        errors.append("mechanical_one_candidate_per_story")
    blind = read_json(OUT / "random-blind-audit.json", {}) or {}
    if int(blind.get("story_count") or 0) < 30:
        errors.append("blind_audit_too_small")
    recalibrated = read_json(OUT / "hge1-recalibrated-growth-series.json", {}) or {}
    if [row.get("wave") for row in recalibrated.get("series", []) or []] != ["baseline", "HGE1-WA-SFH1", "HGE1-WB-SFH1"]:
        errors.append("invalid_recalibrated_growth_series")
    return sorted(set(errors))


def main() -> int:
    errors = validate()
    print(json.dumps({"status": "ok" if not errors else "failed", "errors": errors}, ensure_ascii=False, indent=2))
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
