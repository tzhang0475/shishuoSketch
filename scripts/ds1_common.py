#!/usr/bin/env python3
"""Shared deterministic inputs and contracts for the DS1 vertical slice.

DS1 is deliberately an isolated experiment.  This module reads existing
reviewed projections and emits a compact evidence bundle; it never writes to
canonical, Gold, or production historical data.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Iterable, Mapping


ROOT = Path(__file__).resolve().parents[1]
STORY_ID = "27-jiajue-008"
PROMPT_VERSION = "ds1-v0"
MODEL = "deepseek-v4-flash"

SCHEMA_PATH = Path("schema/ds1-scene-context.schema.json")
SC1_PATH = Path("data/derived/sc1-site.json")
HR0_PATH = Path("data/derived/hr0-historical-situations.json")
HR01_PATH = Path("data/derived/hr0-1-ambiguity-benchmark.json")
H0C_PATH = Path("data/derived/h0c-historical-facts.json")
X1_2RF_PATH = Path("data/derived/x1-2rf-materialized-facts.json")
S1_ASSERTIONS_PATH = Path("data/derived/s1-jianshu-historical-assertions.json")
CONTEXT_PATH = Path("data/generated/ds1/27-jiajue-008-context.json")
CANDIDATE_PATH = Path("data/generated/ds1/27-jiajue-008.json")
REVIEW_PATH = Path("data/annotation/ds1-review.json")
PUBLIC_PATH = Path("site/public/generated/ds1/27-jiajue-008.json")

INPUT_PATHS = (
    SC1_PATH,
    HR0_PATH,
    HR01_PATH,
    H0C_PATH,
    X1_2RF_PATH,
    S1_ASSERTIONS_PATH,
)

TOP_LEVEL_FIELDS = (
    "scene_summary",
    "participant_states",
    "relationship_context",
    "reader_needed_context",
    "uncertainties",
)


def read_json(root: Path, relative: Path) -> Any:
    return json.loads((root / relative).read_text(encoding="utf-8"))


def stable_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def write_json(root: Path, relative: Path, value: Any) -> None:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(stable_json(value), encoding="utf-8")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(root: Path, relative: Path) -> str:
    digest = hashlib.sha256()
    with (root / relative).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def source_hashes(root: Path = ROOT) -> dict[str, str]:
    return {
        relative.as_posix(): sha256_file(root, relative)
        for relative in INPUT_PATHS
    }


def unique_sorted(values: Iterable[Any]) -> list[str]:
    return sorted({str(value) for value in values if value is not None})


def _locator(raw: Any) -> dict[str, Any]:
    if not isinstance(raw, Mapping):
        return {}
    allowed = (
        "artifact_type",
        "artifact_path",
        "entry_id",
        "chapter_id",
        "annotation_id",
        "source_normalized_filename",
        "witness_id",
        "source_path",
        "epub_file",
        "spine_index",
        "block_index",
        "tag",
        "page",
        "physical_page",
    )
    return {key: raw[key] for key in allowed if key in raw}


def _reading_pair(value: Any) -> dict[str, str]:
    if isinstance(value, Mapping):
        return {
            "original": str(value.get("original", "")),
            "simplified": str(value.get("simplified", value.get("original", ""))),
        }
    return {"original": str(value or ""), "simplified": str(value or "")}


def _annotation_text(annotation: Mapping[str, Any]) -> str:
    parts: list[str] = []
    for segment in annotation.get("segments", []):
        if not isinstance(segment, Mapping):
            continue
        display = segment.get("display")
        if isinstance(display, Mapping):
            parts.append(str(display.get("original", "")))
    return "".join(parts)


def _compact_evidence(
    evidence: Mapping[str, Any],
    *,
    source_layer: str | None = None,
    attribution: str | None = None,
    modality: str | None = None,
    quote: str | None = None,
    locator: Any = None,
    source: str | None = None,
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "evidence_ref": str(evidence["evidence_ref"]),
        "source": source if source is not None else str(evidence.get("source_id", "")),
        "source_layer": source_layer or str(evidence.get("source_layer", "unknown")),
        "quote": quote if quote is not None else str(evidence.get("quote", "")),
        "locator": _locator(locator if locator is not None else evidence.get("locator")),
    }
    if attribution:
        result["attribution"] = attribution
    if modality:
        result["modality"] = modality
    return result


def _sc1_evidence_index(story: Mapping[str, Any], sc1: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    all_evidence = {
        str(row.get("id")): row
        for row in sc1.get("evidence", [])
        if isinstance(row, Mapping) and row.get("id")
    }
    refs: set[str] = {str(value) for value in story.get("evidence_ids", [])}
    for annotation in story.get("reading", {}).get("annotations", []):
        refs.update(str(value) for value in annotation.get("evidence_ids", []))

    result: dict[str, dict[str, Any]] = {}
    for ref in sorted(refs):
        row = all_evidence.get(ref)
        if row is None:
            continue
        layer = "base_text" if row.get("evidence_type") == "primary_text" else "liu_annotation"
        result[ref] = _compact_evidence(
            {"evidence_ref": ref, "source_id": row.get("source_id", ""), "source_layer": layer},
            source_layer=layer,
            quote=str(row.get("quote", "")),
            locator=row.get("locator"),
        )
    return result


def _hr0_evidence_index(hr0: Mapping[str, Any], sc1_index: Mapping[str, Mapping[str, Any]]) -> dict[str, dict[str, Any]]:
    result = dict(sc1_index)
    for row in hr0.get("evidence_refs", []):
        if not isinstance(row, Mapping) or not row.get("evidence_id"):
            continue
        ref = str(row["evidence_id"])
        existing = result.get(ref, {"evidence_ref": ref})
        existing.update(
            {
                "source": str(row.get("source_id", existing.get("source", ""))),
                "source_layer": str(row.get("source_layer", existing.get("source_layer", "unknown"))),
                "locator": _locator(row.get("locator")),
            }
        )
        result[ref] = existing
    return result


def _add_annotation_persons(
    story: Mapping[str, Any],
    people_by_id: Mapping[str, Mapping[str, Any]],
    evidence_index: Mapping[str, Mapping[str, Any]],
) -> list[dict[str, Any]]:
    persons: dict[tuple[str, str], dict[str, Any]] = {}
    for annotation in story.get("reading", {}).get("annotations", []):
        evidence_refs = unique_sorted(annotation.get("evidence_ids", []))
        for segment in annotation.get("segments", []):
            if segment.get("type") != "person_mention" or not segment.get("person_id"):
                continue
            display = _reading_pair(segment.get("display"))
            person_id = str(segment["person_id"])
            surface = display["original"]
            key = (person_id, surface)
            persons.setdefault(
                key,
                {
                    "person_id": person_id,
                    "canonical_name": str(people_by_id.get(person_id, {}).get("canonical_name", person_id)),
                    "surface": surface,
                    "role": "annotation_only",
                    "presence_status": "annotation_only",
                    "evidence_refs": evidence_refs,
                },
            )
    return sorted(persons.values(), key=lambda row: (row["person_id"], row["surface"]))


def _reviewed_facts(
    story_id: str,
    h0c: Mapping[str, Any],
    x1_2rf: Mapping[str, Any],
) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]]]:
    facts: list[dict[str, Any]] = []
    evidence: dict[str, dict[str, Any]] = {}
    rows = list(h0c.get("fact_index", [])) + list(x1_2rf.get("facts", []))
    seen: set[str] = set()
    for fact in rows:
        if not isinstance(fact, Mapping) or fact.get("review_status") != "reviewed":
            continue
        subject_ids = {str(value) for value in fact.get("subject_ids", [])}
        if story_id not in subject_ids and not (
            story_id in {str(value) for value in fact.get("story_ids", [])}
        ):
            continue
        fact_id = str(fact.get("fact_id", ""))
        if not fact_id or fact_id in seen:
            continue
        seen.add(fact_id)
        evidence_ref = f"h0c-fact:{fact_id}"
        evidence[evidence_ref] = {
            "evidence_ref": evidence_ref,
            "source": str(fact.get("source_path", "")),
            "source_layer": "reviewed_canonical_fact",
            "quote": "",
            "locator": {"fact_id": fact_id, "source_path": str(fact.get("source_path", ""))},
        }
        facts.append(
            {
                "fact_id": fact_id,
                "fact_type": str(fact.get("fact_type", "unknown")),
                "subject_ids": unique_sorted(fact.get("subject_ids", [])),
                "assertion_status": str(fact.get("assertion_status", "unknown")),
                "temporal_precision": fact.get("temporal_precision"),
                "evidence_refs": [evidence_ref],
            }
        )
    facts.sort(key=lambda row: row["fact_id"])
    return facts, evidence


def build_context_bundle(root: Path = ROOT, story_id: str = STORY_ID) -> dict[str, Any]:
    if story_id != STORY_ID:
        raise ValueError(f"DS1 is intentionally scoped to {STORY_ID}, not {story_id}")

    sc1 = read_json(root, SC1_PATH)
    hr0_doc = read_json(root, HR0_PATH)
    hr01_doc = read_json(root, HR01_PATH)
    h0c = read_json(root, H0C_PATH)
    x1_2rf = read_json(root, X1_2RF_PATH)
    s1 = read_json(root, S1_ASSERTIONS_PATH)
    story = next((row for row in sc1.get("stories", []) if row.get("id") == story_id), None)
    hr0 = next((row for row in hr0_doc.get("records", []) if row.get("story_id") == story_id), None)
    hr01 = next((row for row in hr01_doc.get("records", []) if row.get("story_id") == story_id), None)
    if not isinstance(story, Mapping) or not isinstance(hr0, Mapping) or not isinstance(hr01, Mapping):
        raise ValueError(f"DS1 source records are incomplete for {story_id}")

    people_by_id = {str(row.get("id")): row for row in sc1.get("people", []) if row.get("id")}
    sc1_evidence = _sc1_evidence_index(story, sc1)
    evidence_index = _hr0_evidence_index(hr0, sc1_evidence)

    resolved_gold = hr01.get("evidence_resolved_gold", {})
    participants: list[dict[str, Any]] = []
    for row in resolved_gold.get("participant_states", hr0.get("participant_states", [])):
        if not isinstance(row, Mapping) or not row.get("person_id"):
            continue
        participants.append(
            {
                "person_id": str(row["person_id"]),
                "canonical_name": str(people_by_id.get(str(row["person_id"]), {}).get("canonical_name", row["person_id"])),
                "surface": str(row.get("surface", "")),
                "role": str(row.get("role", "uncertain")),
                "presence_status": str(row.get("presence_status", "uncertain")),
                "resolution_status": str(row.get("resolution_status", "unknown")),
                "evidence_refs": unique_sorted(row.get("evidence_ids", [])),
            }
        )
    participants.extend(_add_annotation_persons(story, people_by_id, evidence_index))
    participants.sort(key=lambda row: (row["person_id"], row["surface"], row["role"]))

    episodes = [
        {
            "episode_id": str(row.get("episode_id")),
            "kind": str(row.get("episode_kind", "unknown")),
            "presence_scope": str(row.get("presence_scope", "unknown")),
            "summary": str(row.get("summary", "")),
            "evidence_refs": unique_sorted(row.get("evidence_ids", [])),
        }
        for row in resolved_gold.get("episodes", hr0.get("episodes", []))
        if isinstance(row, Mapping)
    ]
    episodes.sort(key=lambda row: row["episode_id"])

    person_states = [
        {
            "person_id": str(row.get("person_id")),
            "state_kind": str(row.get("state_kind", "unknown")),
            "value": str(row.get("value", "")),
            "evidence_refs": unique_sorted(row.get("evidence_ids", [])),
        }
        for row in resolved_gold.get("person_states", hr0.get("person_states", []))
        if isinstance(row, Mapping) and row.get("person_id")
    ]
    person_states.sort(key=lambda row: (row["person_id"], row["state_kind"], row["value"]))

    temporal_relations = [
        {
            "anchor_surface": str(row.get("anchor_surface", "")),
            "relation_type": str(row.get("relation_type", "unknown")),
            "precision": str(row.get("precision", "unknown")),
            "expression": str(row.get("expression", "")),
            "evidence_refs": unique_sorted(row.get("evidence_ids", [])),
        }
        for row in resolved_gold.get("temporal_relations", hr0.get("temporal_relations", []))
        if isinstance(row, Mapping)
    ]
    temporal_relations.sort(key=lambda row: (row["anchor_surface"], row["relation_type"]))

    uncertainties = [
        {
            "description": str(row.get("description", "")),
            "status": str(row.get("status", "unknown")),
            "uncertainty_type": str(row.get("uncertainty_type", "unknown")),
            "evidence_refs": unique_sorted(row.get("evidence_ids", [])),
        }
        for row in resolved_gold.get("uncertainties", hr0.get("uncertainties", []))
        if isinstance(row, Mapping)
    ]
    uncertainties.sort(key=lambda row: (row["uncertainty_type"], row["description"]))

    fact_rows, fact_evidence = _reviewed_facts(story_id, h0c, x1_2rf)
    evidence_index.update(fact_evidence)

    jianshu: list[dict[str, Any]] = []
    for row in s1.get("records", []):
        if not isinstance(row, Mapping) or row.get("story_id") != story_id:
            continue
        ref = str(row.get("assertion_id"))
        evidence_index[ref] = _compact_evidence(
            {"evidence_ref": ref, "source_id": "shishuo-jianshu-yujiaxi-local", "source_layer": row.get("layer", "unknown")},
            source=str(row.get("attribution") or "shishuo-jianshu-yujiaxi-local"),
            source_layer=str(row.get("layer", "unknown")),
            attribution=str(row["attribution"]) if row.get("attribution") else None,
            modality=str(row.get("modality")) if row.get("modality") else None,
            quote=str(row.get("text", "")),
            locator=row.get("source_locator"),
        )
        jianshu.append(
            {
                "evidence_ref": ref,
                "source_layer": str(row.get("layer", "unknown")),
                "attribution": row.get("attribution"),
                "modality": row.get("modality"),
                "text": str(row.get("text", "")),
                "locator": _locator(row.get("source_locator")),
                "candidate_fact_types": unique_sorted(row.get("candidate_fact_types", [])),
            }
        )
    jianshu.sort(key=lambda row: row["evidence_ref"])

    # Only direct, reviewed relation records attached to this Story are
    # eligible.  Co-occurrence and graph proximity are intentionally absent.
    story_evidence_ids = set(evidence_index)
    participant_ids = {row["person_id"] for row in participants if row.get("role") != "annotation_only"}
    relationships: list[dict[str, Any]] = []
    for relation in sc1.get("relations", []):
        if not isinstance(relation, Mapping) or relation.get("review_status") != "reviewed":
            continue
        relation_evidence = set(unique_sorted(relation.get("evidence_ids", [])))
        resolved_relation_evidence = relation_evidence & story_evidence_ids
        endpoints = {str(relation.get("subject_id", "")), str(relation.get("object_id", ""))}
        if not resolved_relation_evidence or not (
            story_id in {str(value) for value in relation.get("story_ids", [])}
            or (endpoints & participant_ids and resolved_relation_evidence)
        ):
            continue
        relationships.append(
            {
                "relation_id": str(relation.get("id")),
                "subject_id": str(relation.get("subject_id")),
                "object_id": str(relation.get("object_id")),
                "relation_type": str(relation.get("relation_type", "unknown")),
                "label": str(relation.get("label", "")),
                "evidence_refs": sorted(resolved_relation_evidence),
            }
        )
    relationships.sort(key=lambda row: row["relation_id"])

    for ref in sorted(set().union(*(set(row.get("evidence_refs", [])) for row in participants + episodes + person_states + temporal_relations + uncertainties))):
        if ref not in evidence_index:
            raise ValueError(f"DS1 context evidence is not resolvable: {story_id}/{ref}")

    bundle: dict[str, Any] = {
        "schema": "ds1-context-bundle",
        "schema_version": 1,
        "stage": "DS1",
        "story_id": story_id,
        "bundle_id": f"ds1-context-{story_id}-v1",
        "source_hashes": source_hashes(root),
        "story": {
            "story_id": story_id,
            "title": _reading_pair(story.get("title", story_id)),
            "chapter": str(story.get("chapter_heading", story.get("chapter_display", ""))),
            "original": str(story.get("reading", {}).get("main_text", {}).get("original", story.get("text", ""))),
            "simplified": str(story.get("reading", {}).get("main_text", {}).get("simplified", story.get("text", ""))),
            "temporal_orientation": _reading_pair(story.get("temporal_orientation", {})),
            "source_entry_id": str(story.get("source_entry_id", "")),
        },
        "participants": participants,
        "episodes": episodes,
        "person_states": person_states,
        "temporal_relations": temporal_relations,
        "reviewed_facts": fact_rows,
        "relationship_evidence": relationships,
        "jianshu_evidence": jianshu,
        "uncertainties": uncertainties,
        "evidence_bundle_ids": sorted(evidence_index),
        "evidence_index": {key: evidence_index[key] for key in sorted(evidence_index)},
    }
    # hr01 is consumed to establish the source boundary, but its Gold-only
    # expected effects and resolution labels never enter the model bundle.
    if not hr01.get("evidence_resolved_gold"):
        raise ValueError(f"HR0.1 evidence-resolved view is missing for {story_id}")
    return bundle


def build_prompt(context: Mapping[str, Any]) -> list[dict[str, str]]:
    system = """You are producing a cautious DS1 scene-context candidate for one Shishuo story.
Use ONLY the evidence supplied in the user message. Do not browse, retrieve, or use outside knowledge.
Do not turn a contextual or annotation-only person into an in-scene participant.
If evidence is insufficient, abstain or preserve the uncertainty.
Every substantive claim must include one or more evidence_refs that resolve in evidence_index.
Return JSON only. The top-level keys must be exactly:
scene_summary, participant_states, relationship_context, reader_needed_context, uncertainties.
Use this shape:
scene_summary: {"text": string|null, "evidence_refs": string[]}
participant_states: [{"person_id": string|null, "surface": string, "state": string|null, "evidence_refs": string[]}]
relationship_context, reader_needed_context, uncertainties: [{"text": string|null, "evidence_refs": string[]}]
Do not add metadata, scores, facts, or fields outside this schema. An abstention uses null text and an empty evidence_refs list.
"""
    user = "Analyse this supplied DS1 context bundle and return the required JSON.\n\n" + stable_json(context)
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]


def input_hash(messages: Iterable[Mapping[str, Any]]) -> str:
    return sha256_bytes(stable_json(list(messages)).encode("utf-8"))


def parse_model_json(content: str) -> Any:
    text = content.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    return json.loads(text)


def _claim_errors(value: Any, evidence_ids: set[str], path: str) -> list[str]:
    errors: list[str] = []
    if not isinstance(value, Mapping) or set(value) != {"text", "evidence_refs"}:
        return [f"{path} must contain exactly text and evidence_refs"]
    text = value.get("text")
    refs = value.get("evidence_refs")
    if text is not None and not isinstance(text, str):
        errors.append(f"{path}.text must be string or null")
    if not isinstance(refs, list) or not all(isinstance(ref, str) for ref in refs):
        errors.append(f"{path}.evidence_refs must be a string array")
    else:
        orphaned = sorted(set(refs) - evidence_ids)
        if orphaned:
            errors.append(f"{path} has orphan evidence refs: {', '.join(orphaned)}")
        if text is not None and text.strip() and not refs:
            errors.append(f"{path} has a substantive claim without evidence_refs")
    return errors


def validate_scene_context(value: Any, evidence_bundle_ids: Iterable[str]) -> list[str]:
    errors: list[str] = []
    evidence_ids = {str(value) for value in evidence_bundle_ids}
    if not isinstance(value, Mapping) or set(value) != set(TOP_LEVEL_FIELDS):
        return ["result top-level keys must be exactly the DS1 five fields"]
    errors.extend(_claim_errors(value["scene_summary"], evidence_ids, "scene_summary"))
    for field in ("relationship_context", "reader_needed_context", "uncertainties"):
        rows = value[field]
        if not isinstance(rows, list):
            errors.append(f"{field} must be an array")
            continue
        for index, row in enumerate(rows):
            errors.extend(_claim_errors(row, evidence_ids, f"{field}[{index}]"))
    participants = value["participant_states"]
    if not isinstance(participants, list):
        errors.append("participant_states must be an array")
    else:
        for index, row in enumerate(participants):
            path = f"participant_states[{index}]"
            if not isinstance(row, Mapping) or set(row) != {"person_id", "surface", "state", "evidence_refs"}:
                errors.append(f"{path} must contain exactly person_id, surface, state, evidence_refs")
                continue
            if row["person_id"] is not None and not isinstance(row["person_id"], str):
                errors.append(f"{path}.person_id must be string or null")
            if not isinstance(row["surface"], str) or not row["surface"].strip():
                errors.append(f"{path}.surface must be non-empty")
            if row["state"] is not None and not isinstance(row["state"], str):
                errors.append(f"{path}.state must be string or null")
            refs = row["evidence_refs"]
            if not isinstance(refs, list) or not all(isinstance(ref, str) for ref in refs):
                errors.append(f"{path}.evidence_refs must be a string array")
            else:
                orphaned = sorted(set(refs) - evidence_ids)
                if orphaned:
                    errors.append(f"{path} has orphan evidence refs: {', '.join(orphaned)}")
                if (row["state"] or row["surface"]).strip() and not refs:
                    errors.append(f"{path} has a substantive state without evidence_refs")
    return sorted(errors)


def ensure_review(root: Path, candidate_sha256: str) -> dict[str, Any]:
    if (root / REVIEW_PATH).is_file():
        review = read_json(root, REVIEW_PATH)
    else:
        review = {}
    if review.get("candidate", {}).get("sha256") != candidate_sha256:
        review = {
            "schema": "ds1-review",
            "stage": "DS1",
            "story_id": STORY_ID,
            "candidate": {"path": CANDIDATE_PATH.as_posix(), "sha256": candidate_sha256},
            "decision": "pending",
            "edited_value": None,
            "review_note": "",
        }
        write_json(root, REVIEW_PATH, review)
    return review
