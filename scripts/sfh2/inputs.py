"""Freeze and normalize the SFH1 semantic input universe for SFH2."""

from __future__ import annotations

import collections
from pathlib import Path
from typing import Any, Mapping

from manual_semantic_authority import apply_sfh2_observation, blocked_global_forms
import sfh2r_contract
from .common import (
    INPUT_FILES,
    ROOT,
    SFH1_ROOT,
    as_records,
    file_hash,
    flags,
    normalize_form,
    read_json,
    relative,
    stable_hash,
    text,
    write_json,
)


def _doc(name: str) -> Any:
    return read_json(SFH1_ROOT / name, {}) or {}


def _effective_suppress_overlay() -> list[dict[str, Any]]:
    """Merge HDA2 suppressions with explicit SFH2R manual suppressions.

    The extra rows are mechanical translations of reviewed authority records.
    They do not infer identity and are consumed by existing deterministic
    suppression gates in SFH2 consolidation.
    """
    source = read_json(ROOT / "data/generated/hda2/repair-overlay.json", []) or []
    rows = [dict(row) for row in (source if isinstance(source, list) else source.get("records", []) or []) if isinstance(row, Mapping)]
    existing = {
        (normalize_form(row.get("target_surface")), text(row.get("person_id")))
        for row in rows
        if text(row.get("action")) == "suppress_claim"
    }
    for surface, person_id in sorted(blocked_global_forms()):
        key = (normalize_form(surface), person_id)
        if key in existing:
            continue
        rows.append({
            "action": "suppress_claim",
            "target_surface": surface,
            "person_id": person_id,
            "source": "data/annotation/sfh2r-manual-semantic-authority.json",
            "reason": "manual_semantic_authority",
        })
        existing.add(key)
    return rows


def load_documents() -> dict[str, Any]:
    return {
        "packets": _doc("story-packets.json"),
        "mentions": _doc("validated-mentions.json"),
        "semantics": _doc("reference-semantics.json"),
        "candidate_sets": _doc("candidate-sets.json"),
        "judgments": _doc("identity-judgments.json"),
        "constrained": _doc("constrained-decisions.json"),
        "final": _doc("final-decisions.json"),
        "relations": _doc("relation-assertions.json"),
        "temporal": _doc("temporal-semantics.json"),
        "people": read_json(ROOT / "data/people.json", {}) or {},
        "aliases": read_json(ROOT / "data/aliases.json", {}) or {},
        "profiles": read_json(ROOT / "data/derived/hdb2-f-person-knowledge.json", {}) or {},
        "candidate_profiles": read_json(ROOT / "data/derived/hdb2-f-candidate-person-knowledge.json", {}) or {},
        "profile_audit": read_json(ROOT / "data/derived/hdb2-f-profile-integrity-audit.json", {}) or {},
        "hda2_overlay": _effective_suppress_overlay(),
        "growth": read_json(SFH1_ROOT / "hge1-recalibrated-growth-series.json", {}) or {},
    }


def freeze_input_manifest(path: Path | None = None) -> dict[str, Any]:
    """Create the immutable SFH1 snapshot contract before any SFH2 calls."""
    path = path or (ROOT / "data/generated/sfh2/input-manifest.json")
    hashes = {
        item: file_hash(ROOT / item)
        for item in INPUT_FILES
        if (ROOT / item).is_file()
    }
    documents = load_documents()
    story_ids = sorted({text(row.get("story_id")) for row in as_records(documents["packets"], "packets") if text(row.get("story_id"))})
    mentions = as_records(documents["mentions"], "records")
    candidate_ids = sorted({text(row.get("candidate_person_id")) for row in as_records(documents["final"], "records") if text(row.get("candidate_person_id"))})
    core = flags({
        "schema": "sfh2-input-manifest-v1",
        "run_version": "sfh2-hir1-input-freeze-v1",
        "semantic_source": "data/generated/sfh1",
        "story_count": len(story_ids),
        "story_ids": story_ids,
        "validated_mention_count": len(mentions),
        "source_candidate_person_id_count": len(candidate_ids),
        "source_hashes": hashes,
        "frozen_semantic_stages": [
            "validated-mentions", "reference-semantics", "candidate-sets",
            "identity-judgments", "final-decisions", "relation-assertions",
            "temporal-semantics",
        ],
        "candidate_only": True,
        "canonical_write_back": False,
    })
    core["input_snapshot_hash"] = stable_hash({key: value for key, value in core.items() if key != "input_snapshot_hash"})
    if path.is_file():
        existing = read_json(path, {}) or {}
        if existing != core:
            # SFH2 is a frozen candidate/entity experiment.  SFH2R repairs
            # active alias/profile projections after that experiment; accept
            # only the exact pre→post transition recorded by the isolated
            # repair manifest, never arbitrary current input drift.
            if sfh2r_contract.frozen_hashes_are_current_or_authorized(
                existing.get("source_hashes"),
                hashes,
            ):
                return existing
            raise RuntimeError("sfh2_input_snapshot_changed")
        return existing
    write_json(path, core)
    return core


def _evidence_index(documents: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for packet in as_records(documents.get("packets"), "packets"):
        for evidence in packet.get("evidence", []) or []:
            if isinstance(evidence, Mapping) and text(evidence.get("evidence_id")):
                result[text(evidence.get("evidence_id"))] = dict(evidence)
    return result


def _packet_index(documents: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    return {text(row.get("story_id")): dict(row) for row in as_records(documents.get("packets"), "packets") if text(row.get("story_id"))}


def _mention_context(mention: Mapping[str, Any], packet: Mapping[str, Any], evidence: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    source_id = text(mention.get("source_evidence_id"))
    selected: list[dict[str, Any]] = []
    source = evidence.get(source_id)
    if source:
        selected.append({
            "evidence_id": source_id,
            "source_layer": source.get("source_layer"),
            "source_ref": source.get("source_ref"),
            "text": source.get("text"),
            "target_span": text(source.get("text"))[int(mention.get("source_start") or 0):int(mention.get("source_end") or 0)],
        })
    surface = text(mention.get("surface"))
    for item in packet.get("evidence", []) or []:
        if not isinstance(item, Mapping):
            continue
        item_id = text(item.get("evidence_id"))
        if item_id == source_id:
            continue
        value = text(item.get("text"))
        if surface and surface in value:
            selected.append({
                "evidence_id": item_id,
                "source_layer": item.get("source_layer"),
                "source_ref": item.get("source_ref"),
                "text": value,
            })
    selected = selected[:6]
    return {"evidence": selected, "source_evidence_id": source_id}


def _relations_by_mention(documents: Mapping[str, Any]) -> dict[str, list[dict[str, Any]]]:
    result: dict[str, list[dict[str, Any]]] = collections.defaultdict(list)
    for row in as_records(documents.get("relations"), "records"):
        for key in ("subject_mention_id", "object_mention_id"):
            mention_id = text(row.get(key))
            if mention_id:
                result[mention_id].append({
                    "relation_id": row.get("relation_id"),
                    "relation_type": row.get("relation_type"),
                    "predicate_surface": row.get("predicate_surface"),
                    "evidence_id": row.get("evidence_id"),
                    "subject_mention_id": row.get("subject_mention_id"),
                    "object_mention_id": row.get("object_mention_id"),
                    "subject_endpoint_before": row.get("subject_endpoint"),
                    "object_endpoint_before": row.get("object_endpoint"),
                })
    return result


def _semantics_index(documents: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    return {text(row.get("mention_id")): dict(row) for row in as_records(documents.get("semantics"), "records") if text(row.get("mention_id"))}


def _candidate_index(documents: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    return {text(row.get("mention_id")): dict(row) for row in as_records(documents.get("candidate_sets"), "records") if text(row.get("mention_id"))}


def _final_index(documents: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    return {text(row.get("mention_id")): dict(row) for row in as_records(documents.get("final"), "records") if text(row.get("mention_id"))}


def _temporal_index(documents: Mapping[str, Any]) -> dict[str, list[dict[str, Any]]]:
    result: dict[str, list[dict[str, Any]]] = collections.defaultdict(list)
    for row in as_records(documents.get("temporal"), "records"):
        result[text(row.get("story_id"))].append(dict(row))
    return result


def _classification(mention: Mapping[str, Any], semantic: Mapping[str, Any], final: Mapping[str, Any]) -> str:
    if text(mention.get("entity_kind")) == "non_person" or text(final.get("final_state")) == "non_person":
        return "non_person"
    if text(mention.get("entity_kind")) == "collective_person_reference":
        return "collective_reference"
    stype = text(semantic.get("semantic_type"))
    rform = text(mention.get("reference_form"))
    if stype in {"compositional_kinship", "patron_plus_office", "descriptive_person_reference"} or rform in {"kinship_reference", "pronoun_reference", "descriptive_person_reference"}:
        return "structural_reference"
    if text(final.get("candidate_person_id")):
        return "candidate_observation"
    if text(final.get("person_id")):
        return "existing_person_observation"
    return "unresolved_person_observation"


def build_candidate_observations(documents: Mapping[str, Any] | None = None) -> dict[str, Any]:
    documents = documents or load_documents()
    evidence = _evidence_index(documents)
    packets = _packet_index(documents)
    semantics = _semantics_index(documents)
    candidates = _candidate_index(documents)
    finals = _final_index(documents)
    temporals = _temporal_index(documents)
    relation_map = _relations_by_mention(documents)
    observations: list[dict[str, Any]] = []
    for mention in as_records(documents.get("mentions"), "records"):
        mention_id = text(mention.get("mention_id"))
        if not mention_id:
            continue
        story_id = text(mention.get("story_id"))
        semantic = semantics.get(mention_id, {})
        final = finals.get(mention_id, {})
        candidate = candidates.get(mention_id, {})
        packet = packets.get(story_id, {})
        source = evidence.get(text(mention.get("source_evidence_id")), {})
        obs_id = f"sfh2-observation-{stable_hash({'mention_id': mention_id, 'story_id': story_id, 'surface': mention.get('surface')})[:24]}"
        observation = flags({
            "observation_id": obs_id,
            "mention_id": mention_id,
            "story_id": story_id,
            "unit_id": obs_id,
            "surface": mention.get("surface"),
            "normalized_surface": normalize_form(mention.get("surface")),
            "semantic_reference_type": semantic.get("semantic_type", "uncertain"),
            "reference_form": mention.get("reference_form"),
            "entity_kind": mention.get("entity_kind"),
            "classification": _classification(mention, semantic, final),
            "source_evidence": {
                "evidence_id": mention.get("source_evidence_id"),
                "source_layer": source.get("source_layer"),
                "source_ref": source.get("source_ref"),
                "source_start": mention.get("source_start"),
                "source_end": mention.get("source_end"),
                "exact_span": text(source.get("text"))[int(mention.get("source_start") or 0):int(mention.get("source_end") or 0)],
            },
            "local_context": _mention_context(mention, packet, evidence),
            "liu_evidence": [
                {"evidence_id": row.get("evidence_id"), "text": row.get("text"), "source_ref": row.get("source_ref")}
                for row in packet.get("evidence", []) or []
                if isinstance(row, Mapping) and text(row.get("source_layer")) == "liu_annotation" and (text(mention.get("surface")) in text(row.get("text")) or not text(mention.get("surface")))
            ][:4],
            "reference_semantics": {
                key: semantic.get(key)
                for key in ("semantic_type", "referent_role", "anchor_mentions", "holder_mentions", "patron_or_possessor_mentions", "coreference_with", "distinct_from", "confidence")
                if key in semantic
            },
            "source_evidence_ids": sorted({text(mention.get("source_evidence_id")), *[text(row.get("evidence_id")) for row in _mention_context(mention, packet, evidence).get("evidence", [])] } - {""}),
            "previous_candidate_person_id": final.get("candidate_person_id"),
            "previous_identity_decision": {
                "final_state": final.get("final_state"),
                "person_id": final.get("person_id"),
                "candidate_person_id": final.get("candidate_person_id"),
                "candidate_display_name": final.get("candidate_display_name"),
                "failure_stage": final.get("failure_stage"),
                "evidence_ids": final.get("evidence_ids", []),
            },
            "previous_candidate_rows": candidate.get("candidates", []),
            "temporal_context": temporals.get(story_id, [])[:12],
            "relation_context": relation_map.get(mention_id, [])[:12],
            "provenance": {
                "occurrence_id": mention_id,
                "identity_observation_id": final.get("decision_id"),
                "evidence_ref": mention.get("source_evidence_id"),
                "source_hash": packet.get("source_sha256"),
            },
        })
        observations.append(flags(apply_sfh2_observation(observation)))
    observations.sort(key=lambda row: text(row.get("observation_id")))
    candidate_ids = sorted({text(row.get("previous_candidate_person_id")) for row in observations if text(row.get("previous_candidate_person_id"))})
    return flags({
        "schema": "sfh2-candidate-observations-v1",
        "records": observations,
        "observation_count": len(observations),
        "candidate_observation_count": sum(bool(text(row.get("previous_candidate_person_id"))) for row in observations),
        "entity_resolution_candidate_observation_count": sum(row.get("classification") == "candidate_observation" for row in observations),
        "source_candidate_person_id_count": len(candidate_ids),
        "source_candidate_person_ids": candidate_ids,
        "manual_semantic_authority_applied": True,
        "candidate_only": True,
        "canonical_write_back": False,
    })
