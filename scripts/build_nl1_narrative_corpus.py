#!/usr/bin/env python3
"""Build the reviewed NL1 Story-centered narrative corpus.

NL1 is an annotation/projection layer.  It reads existing Story, HR0/HR0.1,
NL0 and reviewed-fact data and writes only derived narrative annotations.  It
does not create canonical facts, Persons, Relations, dates, or Story records.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Iterable, Mapping


ROOT = Path(__file__).resolve().parents[1]

SPEC_PATH = Path("data/annotation/nl1-narrative-review.json")
SCHEMA_PATH = Path("schema/nl1-narrative-corpus.schema.json")
SC1_PATH = Path("data/derived/sc1-site.json")
HR0_PATH = Path("data/derived/hr0-historical-situations.json")
HR01_PATH = Path("data/derived/hr0-1-ambiguity-benchmark.json")
H0C_FACTS_PATH = Path("data/derived/h0c-historical-facts.json")
X1_2RF_FACTS_PATH = Path("data/derived/x1-2rf-materialized-facts.json")
NL0_GOLD_PATH = Path("data/derived/nl0-story-sketch-gold.json")
SCENE_CONTEXTS_PATH = Path("data/derived/story-scene-contexts.json")
S1_ASSERTIONS_PATH = Path("data/derived/s1-jianshu-historical-assertions.json")
S1_CITATIONS_PATH = Path("data/derived/s1-jianshu-source-citations.json")

CONTEXT_PATH = Path("data/derived/nl1-narrative-context.json")
SELECTION_PATH = Path("data/derived/nl1-narrative-selection-gold.json")
METRICS_PATH = Path("data/derived/nl1-metrics.json")
SUMMARY_PATH = Path("data/derived/nl1-summary.json")
PROTECTION_PATH = Path("data/derived/nl1-protection-manifest.json")

INPUT_PATHS = (
    SPEC_PATH,
    SCHEMA_PATH,
    SC1_PATH,
    HR0_PATH,
    HR01_PATH,
    H0C_FACTS_PATH,
    X1_2RF_FACTS_PATH,
    NL0_GOLD_PATH,
    SCENE_CONTEXTS_PATH,
    S1_ASSERTIONS_PATH,
    S1_CITATIONS_PATH,
)

PROTECTED_PATHS = (
    SC1_PATH,
    HR0_PATH,
    HR01_PATH,
    H0C_FACTS_PATH,
    X1_2RF_FACTS_PATH,
    NL0_GOLD_PATH,
    S1_ASSERTIONS_PATH,
    S1_CITATIONS_PATH,
)

ROLES = ("background", "in_scene", "off_scene", "person_glimpse", "resonance")
ROLE_LABELS = {
    "background": "底色",
    "in_scene": "入画",
    "off_scene": "画外",
    "person_glimpse": "人物一瞥",
    "resonance": "余韵",
}
ROLE_GUARDS = {
    "background": "补入本则没有明确支持的精确年代、家世或长期历史结论。",
    "in_scene": "把正文只提及、回忆或注释中的人物全部写成当前场景在场者。",
    "off_scene": "把画外人物或注释背景改写为当前场景的行动者。",
    "person_glimpse": "把一句动作、发言或品评扩展成未经支持的稳定性格或历史评价。",
    "resonance": "把本则扩写为泛化的时代感慨、政治寓意或未经支持的后世结论。",
}

POLICY = {
    "canonical_data_write_back": False,
    "canonical_fact_materialization": False,
    "llm": False,
    "rag": False,
    "automatic_narrative_materialization": False,
    "generated_fields_may_abstain": True,
    "uncertainty_preserved": True,
}


def read_json(root: Path, relative: Path) -> Any:
    return json.loads((root / relative).read_text(encoding="utf-8"))


def sha256_file(root: Path, relative: Path) -> str:
    digest = hashlib.sha256()
    with (root / relative).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def stable_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def sorted_unique(values: Iterable[Any]) -> list[str]:
    return sorted({str(value) for value in values if value is not None})


def pair(value: Any, fallback: Any = None) -> dict[str, str]:
    if isinstance(value, Mapping):
        original = str(value.get("original") or value.get("simplified") or "")
        simplified = str(value.get("simplified") or value.get("original") or "")
        if original or simplified:
            return {"original": original, "simplified": simplified}
    if value is not None:
        text = str(value)
        return {"original": text, "simplified": text}
    if fallback is not None:
        return pair(fallback)
    return {"original": "未明", "simplified": "未明"}


def compact_locator(locator: Mapping[str, Any] | None) -> dict[str, Any]:
    locator = locator or {}
    keys = (
        "artifact_type",
        "entry_id",
        "chapter_id",
        "artifact_path",
        "annotation_id",
        "source_normalized_filename",
        "normalized_line_start",
        "normalized_line_end",
        "page_marker_start",
        "page_marker_end",
    )
    return {key: locator[key] for key in keys if key in locator and locator[key] is not None}


def source_hashes(root: Path) -> dict[str, str]:
    return {path.as_posix(): sha256_file(root, path) for path in INPUT_PATHS}


def source_layer(evidence: Mapping[str, Any], hr0_ref: Mapping[str, Any] | None = None) -> str:
    if hr0_ref and hr0_ref.get("source_layer"):
        return str(hr0_ref["source_layer"])
    evidence_type = str(evidence.get("evidence_type") or "")
    return {
        "primary_text": "base_text",
        "annotation": "liu_annotation",
        "source": "quoted_source",
    }.get(evidence_type, "unknown")


def build_evidence_index(
    story: Mapping[str, Any],
    hr0: Mapping[str, Any] | None,
    sc1_evidence: Mapping[str, Mapping[str, Any]],
) -> dict[str, Mapping[str, Any]]:
    hr0_refs = {
        str(row["evidence_id"]): row
        for row in (hr0 or {}).get("evidence_refs", [])
        if row.get("evidence_id")
    }
    result: dict[str, Mapping[str, Any]] = {}
    for evidence_id in story.get("evidence_ids", []):
        evidence_id = str(evidence_id)
        evidence = sc1_evidence.get(evidence_id, {})
        ref = hr0_refs.get(evidence_id)
        locator = (ref or {}).get("locator") or evidence.get("locator") or {}
        result[evidence_id] = {
            "evidence_id": evidence_id,
            "source_id": str((ref or {}).get("source_id") or evidence.get("source_id") or "unknown"),
            "source_layer": source_layer(evidence, ref),
            "evidence_type": str((ref or {}).get("evidence_type") or evidence.get("evidence_type") or "unknown"),
            "source_review_status": str((ref or {}).get("review_status") or evidence.get("review_status") or "unknown"),
            "assertion_status": str((ref or {}).get("assertion_status") or evidence.get("assertion_status") or "unknown"),
            "locator": compact_locator(locator),
        }
    return result


def normalize_role(value: str | None) -> str:
    value = str(value or "unknown")
    return {
        "present": "present",
        "speaker": "speaker",
        "actor": "actor",
        "referenced": "referenced",
        "reported_subject": "reported_subject",
        "comparand": "comparand",
        "annotation_only": "annotation_only",
    }.get(value, "unknown")


def normalize_presence(value: str | None) -> str:
    value = str(value or "unknown")
    return {
        "in_scene": "in_scene",
        "mentioned": "referenced",
        "reported": "reported",
        "contextual": "contextual",
    }.get(value, value if value in {"referenced", "unknown"} else "unknown")


def person_surface(
    person_id: str | None,
    raw_surface: Any,
    display_people: Mapping[str, Any],
) -> dict[str, str]:
    if raw_surface is not None:
        return pair(raw_surface)
    if person_id and person_id in display_people:
        return pair(display_people[person_id].get("name"), "未解析人物")
    return {"original": "未解析人物", "simplified": "未解析人物"}


def evidence_ids_from(value: Any) -> list[str]:
    if isinstance(value, Mapping):
        return sorted_unique(value.get("evidence_ids", []))
    return sorted_unique(value or [])


def claim_pair_from_selection(selection: Mapping[str, Any]) -> dict[str, str]:
    return pair(selection.get("text"))


def fact_ids_for_story(
    story_id: str,
    story_evidence_ids: set[str],
    h0c: Mapping[str, Any],
    x1_2rf: Mapping[str, Any],
) -> list[str]:
    result: set[str] = set()
    for fact in h0c.get("fact_index", []):
        if fact.get("review_status") != "reviewed":
            continue
        subjects = {str(value) for value in fact.get("subject_ids", [])}
        evidence = {str(value) for value in fact.get("evidence_ids", [])}
        if story_id in subjects or story_evidence_ids & evidence:
            result.add(str(fact.get("fact_id")))
    for fact in x1_2rf.get("facts", []):
        evidence = {str(value) for value in fact.get("evidence_ids", [])}
        if story_evidence_ids & evidence:
            result.add(str(fact.get("fact_id")))
    return sorted(result)


def review_item(
    item_id: str,
    text: Any,
    evidence_ids: Iterable[str],
    kind: str,
    assertion_status: str = "attested",
) -> dict[str, Any]:
    return {
        "item_id": item_id,
        "text": pair(text),
        "assertion_status": assertion_status if assertion_status in {"attested", "reported", "inferred", "disputed", "unknown"} else "unknown",
        "evidence_ids": sorted_unique(evidence_ids),
        "review_status": "reviewed",
        "kind": kind,
    }


def normalize_participants(
    story_id: str,
    spec_record: Mapping[str, Any],
    hr0: Mapping[str, Any] | None,
    display_people: Mapping[str, Any],
) -> list[dict[str, Any]]:
    raw_rows = (hr0 or {}).get("participant_states") if hr0 else None
    if raw_rows is None:
        raw_rows = spec_record.get("scene_participants", [])
    result: list[dict[str, Any]] = []
    for index, row in enumerate(raw_rows or [], start=1):
        person_id = str(row["person_id"]) if row.get("person_id") else None
        evidence_ids = sorted_unique(row.get("evidence_ids", []))
        result.append(
            {
                "participant_id": f"{story_id}-participant-{index:02d}",
                "person_id": person_id,
                "surface": person_surface(person_id, row.get("surface"), display_people),
                "role": normalize_role(row.get("role")),
                "presence_status": normalize_presence(row.get("presence_status")),
                "evidence_ids": evidence_ids,
                "review_note": str(row.get("review_note") or "沿用当前 Story 语义的参与/被述及区分。"),
                "review_status": "reviewed",
            }
        )
    return result


def normalize_person_states(
    story_id: str,
    spec_record: Mapping[str, Any],
    hr0: Mapping[str, Any] | None,
    display_people: Mapping[str, Any],
) -> list[dict[str, Any]]:
    rows = list((hr0 or {}).get("person_states", []) if hr0 else [])
    rows.extend(spec_record.get("person_states", []))
    result: list[dict[str, Any]] = []
    for index, row in enumerate(rows, start=1):
        person_id = str(row["person_id"]) if row.get("person_id") else None
        modality = str(row.get("modality") or "unknown")
        if modality not in {"none", "reported", "probable", "possible", "disputed", "unknown"}:
            modality = "unknown"
        result.append(
            {
                "state_id": str(row.get("state_id") or f"{story_id}-state-{index:02d}"),
                "person_id": person_id,
                "surface": person_surface(person_id, row.get("surface"), display_people),
                "state_kind": str(row.get("state_kind") or "story_context"),
                "value": pair(row.get("value") or row.get("description") or "本则保留人物状态，但不作额外推断。"),
                "modality": modality,
                "evidence_ids": sorted_unique(row.get("evidence_ids", [])),
                "review_status": "reviewed",
            }
        )
    return result


def normalize_relationships(story_id: str, spec_record: Mapping[str, Any]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for index, row in enumerate(spec_record.get("relationship_context", []), start=1):
        scope = str(row.get("relation_scope") or "story_context")
        if scope not in {"explicit_story_relation", "story_context", "reviewed_fact_context", "not_inferred", "uncertain"}:
            scope = "uncertain"
        result.append(
            {
                "relationship_id": str(row.get("relationship_id") or f"{story_id}-relationship-{index:02d}"),
                "relation_scope": scope,
                "subject_person_id": str(row["subject_person_id"]) if row.get("subject_person_id") else None,
                "object_person_id": str(row["object_person_id"]) if row.get("object_person_id") else None,
                "description": pair(row.get("description") or "本则保留关系语境，不生成新的直接关系。"),
                "evidence_ids": sorted_unique(row.get("evidence_ids", [])),
                "review_status": "reviewed",
            }
        )
    hr0 = spec_record.get("_hr0")
    for row in (hr0 or {}).get("person_states", []):
        if row.get("state_kind") != "family_context":
            continue
        result.append(
            {
                "relationship_id": f"{story_id}-relationship-family-{row.get('state_id', 'x')}",
                "relation_scope": "story_context",
                "subject_person_id": str(row["person_id"]) if row.get("person_id") else None,
                "object_person_id": None,
                "description": pair(row.get("value")),
                "evidence_ids": sorted_unique(row.get("evidence_ids", [])),
                "review_status": "reviewed",
            }
        )
    return result


def uncertainty_dimension(description: str) -> str:
    if any(token in description for token in ("年", "年代", "日期", "时间", "时", "时期", "晏驾")):
        return "temporal"
    if any(token in description for token in ("人物", "称", "端点", "身份", "称号", "映射")):
        return "identity"
    if any(token in description for token in ("参与", "在场", "现场", "背景")):
        return "presence_or_context"
    return "semantic_scope"


def normalize_uncertainties(
    story_id: str,
    spec_record: Mapping[str, Any],
    hr0: Mapping[str, Any] | None,
    main_evidence_id: str,
) -> list[dict[str, Any]]:
    rows = list((hr0 or {}).get("uncertainties", []) if hr0 else [])
    rows.extend(spec_record.get("uncertainties", []))
    if not rows:
        rows.append(
            {
                "uncertainty_id": "default-temporal",
                "description": "本则没有可安全采用的绝对年代；NL1 保留未知。",
                "evidence_ids": [main_evidence_id],
            }
        )
    result: list[dict[str, Any]] = []
    for index, row in enumerate(rows, start=1):
        description = str(row.get("description") or "本项仍需进一步证据。")
        status = str(row.get("status") or "unresolved")
        if status not in {"unresolved", "partially_resolved", "abstained"}:
            status = "unresolved"
        result.append(
            {
                "uncertainty_id": f"{story_id}-uncertainty-{index:02d}",
                "dimension": str(row.get("dimension") or uncertainty_dimension(description)),
                "description": pair(description),
                "evidence_ids": sorted_unique(row.get("evidence_ids", []) or [main_evidence_id]),
                "status": status,
                "review_status": "reviewed",
            }
        )
    return result


def build_context_record(
    spec_record: Mapping[str, Any],
    story: Mapping[str, Any],
    hr0: Mapping[str, Any] | None,
    hr01: Mapping[str, Any] | None,
    nl0: Mapping[str, Any] | None,
    display_people: Mapping[str, Any],
    h0c: Mapping[str, Any],
    x1_2rf: Mapping[str, Any],
) -> dict[str, Any]:
    story_id = str(spec_record["story_id"])
    main_evidence_id = f"evidence-sc1-{story_id}-main"
    story_evidence_ids = {str(value) for value in story.get("evidence_ids", [])}
    if main_evidence_id not in story_evidence_ids:
        main_evidence_id = sorted(story_evidence_ids)[0]

    if spec_record.get("current_scene"):
        scene_summary = pair(spec_record["current_scene"])
    elif hr0 and hr0.get("episodes"):
        scene_summary = pair("；".join(str(row.get("summary")) for row in hr0["episodes"] if row.get("summary")))
    else:
        scene_summary = pair(story.get("reading", {}).get("main_text") or story.get("text"))
    source_text = pair(story.get("reading", {}).get("main_text") or story.get("text"))
    episodes = hr0.get("episodes", []) if hr0 else []
    episode_ids = [str(row.get("episode_id")) for row in episodes if row.get("episode_id")]
    if not episode_ids:
        episode_ids = [str(value) for value in spec_record.get("episode_ids", [])] or ["e1"]
    participants = normalize_participants(story_id, spec_record, hr0, display_people)
    scene_evidence = {main_evidence_id}
    scene_evidence.update(evidence_ids_from(scene_summary))
    for participant in participants:
        scene_evidence.update(participant["evidence_ids"])

    role_selections = spec_record.get("role_selections", {})
    stakes: list[dict[str, Any]] = []
    background = role_selections.get("background")
    if background:
        stakes.append(
            review_item(
                f"{story_id}-stakes-01",
                background.get("text"),
                background.get("evidence_ids", []),
                "historical_stakes",
            )
        )
    prior_events = [
        review_item(f"{story_id}-prior-{index:02d}", row.get("text"), row.get("evidence_ids", []), "prior_event")
        for index, row in enumerate(spec_record.get("prior_events", []), start=1)
    ]
    later_events = [
        review_item(f"{story_id}-later-{index:02d}", row.get("text"), row.get("evidence_ids", []), "later_event")
        for index, row in enumerate(spec_record.get("later_events", []), start=1)
    ]
    person_states = normalize_person_states(story_id, spec_record, hr0, display_people)
    relationship_context = normalize_relationships(story_id, {**spec_record, "_hr0": hr0})
    uncertainties = normalize_uncertainties(story_id, spec_record, hr0, main_evidence_id)
    for row in stakes + prior_events + later_events:
        scene_evidence.update(row["evidence_ids"])
    for row in person_states + relationship_context + uncertainties:
        scene_evidence.update(row["evidence_ids"])

    hr0_evidence = {
        str(row["evidence_id"]): row
        for row in (hr0 or {}).get("evidence_refs", [])
        if row.get("evidence_id")
    }
    sc1_evidence = {str(row["id"]): row for row in []}
    # The caller supplies SC1 evidence through the temporary field below; this
    # branch is replaced in build_context_record_with_evidence.
    del sc1_evidence

    source_spans: list[dict[str, Any]] = []
    # The actual evidence metadata is attached by build_context_record_with_evidence.
    return {
        "context_id": f"narrative-context-nl1-{story_id}",
        "story_id": story_id,
        "selection_categories": sorted_unique(spec_record["selection_categories"]),
        "review_status": "reviewed",
        "review_note": str(spec_record["review_note"]),
        "current_scene": {
            "scene_id": f"{story_id}-scene",
            "summary": scene_summary,
            "source_text": source_text,
            "episode_ids": episode_ids,
            "participant_states": participants,
            "evidence_ids": sorted(scene_evidence),
            "review_status": "reviewed",
        },
        "historical_stakes": stakes,
        "person_states": person_states,
        "relationship_context": relationship_context,
        "prior_events": prior_events,
        "later_events": later_events,
        "key_source_spans": source_spans,
        "uncertainties": uncertainties,
        "grounded_inputs": {
            "hr0_situation_id": str(hr0["situation_id"]) if hr0 and hr0.get("situation_id") else None,
            "hr0_1_case_ids": sorted_unique((hr01 or {}).get("case_ids", [])),
            "nl0_sketch_id": f"story-sketch-nl0-{story_id}" if nl0 else None,
            "historical_fact_ids": fact_ids_for_story(story_id, story_evidence_ids, h0c, x1_2rf),
            "source_scope": sorted_unique(
                ["SC1", "H0C"]
                + (["HR0", "HR0.1"] if hr0 else [])
                + (["NL0"] if nl0 else [])
                + (["story_scene_context_selection"] if not hr0 else [])
            ),
        },
    }


def build_context_record_with_evidence(
    spec_record: Mapping[str, Any],
    story: Mapping[str, Any],
    hr0: Mapping[str, Any] | None,
    hr01: Mapping[str, Any] | None,
    nl0: Mapping[str, Any] | None,
    display_people: Mapping[str, Any],
    h0c: Mapping[str, Any],
    x1_2rf: Mapping[str, Any],
    sc1_evidence: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    record = build_context_record(spec_record, story, hr0, hr01, nl0, display_people, h0c, x1_2rf)
    evidence_index = build_evidence_index(story, hr0, sc1_evidence)
    referenced: set[str] = set(record["current_scene"]["evidence_ids"])
    for key in ("historical_stakes", "person_states", "relationship_context", "prior_events", "later_events", "uncertainties"):
        for row in record[key]:
            referenced.update(row["evidence_ids"])
    spans: list[dict[str, Any]] = []
    for evidence_id in sorted(referenced):
        if evidence_id not in evidence_index:
            continue
        meta = evidence_index[evidence_id]
        spans.append(
            {
                "evidence_id": evidence_id,
                "source_layer": meta["source_layer"],
                "evidence_type": meta["evidence_type"],
                "span_role": "scene" if evidence_id == f"evidence-sc1-{record['story_id']}-main" else "annotation_or_context",
                "locator": meta["locator"],
                "source_review_status": meta["source_review_status"],
                "review_status": "reviewed",
            }
        )
    record["key_source_spans"] = spans
    return record


def attach_s1_lineage(
    context: dict[str, Any],
    story_id: str,
    s1_assertions_by_story: Mapping[str, list[str]],
    s1_citations_by_story: Mapping[str, list[str]],
) -> dict[str, Any]:
    """Attach existing Jianshu lineage without promoting it to a claim.

    S1 assertions/citations are source-discovery and scholarly context inputs.
    NL1 keeps their IDs available for review, but selected narrative claims
    still need Story-local evidence IDs in the selection document.
    """

    assertion_ids = sorted_unique(s1_assertions_by_story.get(story_id, []))
    citation_ids = sorted_unique(s1_citations_by_story.get(story_id, []))
    grounded = context["grounded_inputs"]
    grounded["s1_assertion_ids"] = assertion_ids
    grounded["s1_citation_ids"] = citation_ids
    if assertion_ids or citation_ids:
        grounded["source_scope"] = sorted_unique([*grounded["source_scope"], "S1-Jianshu"])
    return context


def selection_candidate(
    candidate_id: str,
    role: str,
    status: str,
    text: Any,
    evidence_ids: Iterable[str],
    reason: str,
    source_scope: str,
    rejection_reason: str | None = None,
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "candidate_id": candidate_id,
        "role": role,
        "candidate_status": status,
        "text": pair(text) if text is not None else None,
        "supporting_evidence": sorted_unique(evidence_ids),
        "selection_reason": reason,
        "source_scope": source_scope,
    }
    if rejection_reason:
        result["rejection_reason"] = rejection_reason
    return result


def build_role_selection(
    story_id: str,
    role: str,
    spec_record: Mapping[str, Any],
    story_evidence_ids: set[str],
) -> dict[str, Any]:
    role_data = (spec_record.get("role_selections") or {}).get(role)
    abstention_reason = (spec_record.get("abstentions") or {}).get(role)
    main_evidence_id = f"evidence-sc1-{story_id}-main"
    if main_evidence_id not in story_evidence_ids:
        main_evidence_id = sorted(story_evidence_ids)[0]
    candidates: list[dict[str, Any]] = []
    selected_ids: list[str] = []
    abstained_ids: list[str] = []
    if role_data:
        evidence_ids = sorted_unique(role_data.get("evidence_ids", []))
        candidate_id = f"{story_id}-{role}-selected"
        candidates.append(
            selection_candidate(
                candidate_id,
                role,
                "selected",
                role_data.get("text"),
                evidence_ids,
                str(role_data.get("reason") or "正文/既有 reviewed context 支持该叙事选择。"),
                str(role_data.get("source_scope") or "reviewed_story_evidence"),
            )
        )
        selected_ids.append(candidate_id)
        state = "selected"
    else:
        candidate_id = f"{story_id}-{role}-abstained"
        abstention_reason = str(abstention_reason or f"当前证据不足以安全选择{ROLE_LABELS[role]}。")
        candidates.append(
            selection_candidate(
                candidate_id,
                role,
                "abstained",
                None,
                [main_evidence_id],
                abstention_reason,
                "review_abstention",
            )
        )
        abstained_ids.append(candidate_id)
        state = "abstained"
    guard_id = f"{story_id}-{role}-rejected-guard"
    guard_evidence = [main_evidence_id]
    annotation_id = f"evidence-sc1-{story_id}-annotation-001"
    if role in {"background", "off_scene"} and annotation_id in story_evidence_ids:
        guard_evidence.append(annotation_id)
    candidates.append(
        selection_candidate(
            guard_id,
            role,
            "rejected",
            ROLE_GUARDS[role],
            guard_evidence,
            "保留为反向审核候选，防止叙事投影越过正文/已审语义边界。",
            "review_guard",
            ROLE_GUARDS[role],
        )
    )
    return {
        "role": role,
        "role_label": ROLE_LABELS[role],
        "selection_state": state,
        "selected_candidate_ids": selected_ids,
        "rejected_candidate_ids": [guard_id],
        "abstained_candidate_ids": abstained_ids,
        "candidates": candidates,
    }


def build_selection_record(
    spec_record: Mapping[str, Any],
    story: Mapping[str, Any],
    context: Mapping[str, Any],
) -> dict[str, Any]:
    story_id = str(spec_record["story_id"])
    story_evidence_ids = {str(value) for value in story.get("evidence_ids", [])}
    return {
        "selection_id": f"narrative-selection-nl1-{story_id}",
        "story_id": story_id,
        "context_id": str(context["context_id"]),
        "selection_categories": sorted_unique(spec_record["selection_categories"]),
        "review_status": "reviewed_gold",
        "review_note": str(spec_record["review_note"]),
        "roles": {
            role: build_role_selection(story_id, role, spec_record, story_evidence_ids)
            for role in ROLES
        },
    }


def build_metrics(
    context_records: list[Mapping[str, Any]],
    selection_records: list[Mapping[str, Any]],
    source_hashes_value: Mapping[str, str],
    selected_ids: list[str],
) -> dict[str, Any]:
    category_counts: dict[str, int] = {}
    for record in context_records:
        for category in record["selection_categories"]:
            category_counts[category] = category_counts.get(category, 0) + 1
    role_distribution: dict[str, dict[str, int]] = {}
    candidate_status_counts: dict[str, int] = {"selected": 0, "rejected": 0, "abstained": 0}
    selected_by_role: dict[str, int] = {}
    rejected_by_role: dict[str, int] = {}
    abstained_by_role: dict[str, int] = {}
    for record in selection_records:
        for role in ROLES:
            selection = record["roles"][role]
            state = selection["selection_state"]
            role_distribution.setdefault(role, {"stories": 0, "selected": 0, "abstained": 0, "rejected": 0})["stories"] += 1
            role_distribution[role][state] += 1
            role_distribution[role]["rejected"] += len(selection["rejected_candidate_ids"])
            selected_by_role[role] = selected_by_role.get(role, 0) + len(selection["selected_candidate_ids"])
            rejected_by_role[role] = rejected_by_role.get(role, 0) + len(selection["rejected_candidate_ids"])
            abstained_by_role[role] = abstained_by_role.get(role, 0) + len(selection["abstained_candidate_ids"])
            for candidate in selection["candidates"]:
                candidate_status_counts[candidate["candidate_status"]] += 1
    context_counts = {
        "records": len(context_records),
        "episodes": sum(len(row["current_scene"]["episode_ids"]) for row in context_records),
        "participant_states": sum(len(row["current_scene"]["participant_states"]) for row in context_records),
        "person_states": sum(len(row["person_states"]) for row in context_records),
        "relationship_context_items": sum(len(row["relationship_context"]) for row in context_records),
        "historical_stakes": sum(len(row["historical_stakes"]) for row in context_records),
        "prior_events": sum(len(row["prior_events"]) for row in context_records),
        "later_events": sum(len(row["later_events"]) for row in context_records),
        "uncertainties": sum(len(row["uncertainties"]) for row in context_records),
        "source_spans": sum(len(row["key_source_spans"]) for row in context_records),
        "stories_with_uncertainties": sum(bool(row["uncertainties"]) for row in context_records),
    }
    source_layers: dict[str, int] = {}
    stories_with_s1_assertions = 0
    stories_with_s1_citations = 0
    s1_assertion_count = 0
    s1_citation_count = 0
    for record in context_records:
        for span in record["key_source_spans"]:
            source_layers[span["source_layer"]] = source_layers.get(span["source_layer"], 0) + 1
        assertion_ids = record["grounded_inputs"].get("s1_assertion_ids", [])
        citation_ids = record["grounded_inputs"].get("s1_citation_ids", [])
        stories_with_s1_assertions += bool(assertion_ids)
        stories_with_s1_citations += bool(citation_ids)
        s1_assertion_count += len(assertion_ids)
        s1_citation_count += len(citation_ids)
    patterns = {
        "scene_nucleus_selected": selected_by_role.get("in_scene", 0),
        "explicit_omission_guards": sum(rejected_by_role.values()),
        "stories_with_resonance": role_distribution["resonance"]["selected"],
        "stories_with_background": role_distribution["background"]["selected"],
        "stories_with_off_scene": role_distribution["off_scene"]["selected"],
        "stories_with_person_glimpse": role_distribution["person_glimpse"]["selected"],
        "identity_or_presence_uncertainty_stories": sum(
            any(row["dimension"] in {"identity", "presence_or_context"} for row in record["uncertainties"])
            for record in context_records
        ),
    }
    return {
        "schema": "nl1-metrics",
        "stage": "NL1",
        "schema_version": "v0",
        "source_hashes": dict(source_hashes_value),
        "policy": dict(POLICY),
        "scope": {"story_count": len(selected_ids), "selected_story_ids": selected_ids},
        "selection_categories": dict(sorted(category_counts.items())),
        "context": context_counts,
        "selection": {
            "records": len(selection_records),
            "roles": len(selection_records) * len(ROLES),
            "candidate_status_counts": candidate_status_counts,
            "selected_by_role": selected_by_role,
            "rejected_by_role": rejected_by_role,
            "abstained_by_role": abstained_by_role,
        },
        "role_distribution": role_distribution,
        "source_layer_counts": dict(sorted(source_layers.items())),
        "s1_lineage": {
            "stories_with_assertions": stories_with_s1_assertions,
            "assertion_ids": s1_assertion_count,
            "stories_with_citations": stories_with_s1_citations,
            "citation_ids": s1_citation_count,
            "promotion_to_canonical_fact": False,
        },
        "selection_patterns": patterns,
        "unresolved_annotation_issues": [
            "some title/alias surfaces remain unresolved and are retained as null Person endpoints",
            "most Stories retain unknown or relative chronology rather than a derived date",
            "rejected candidates are narrative boundary guards, not claims that the underlying source is false",
        ],
        "nl1_e_readiness": {
            "ready": True,
            "pass_a_context_selection": True,
            "pass_b_evidence_grounding": True,
            "rejection_labels": True,
            "abstention_labels": True,
            "note": "The corpus separates reviewed context, selected narrative roles, rejected overreach, and abstention without requiring an LLM or retrieval layer.",
        },
    }


def build_documents(root: Path = ROOT) -> dict[str, Any]:
    spec = read_json(root, SPEC_PATH)
    sc1 = read_json(root, SC1_PATH)
    hr0_doc = read_json(root, HR0_PATH)
    hr01_doc = read_json(root, HR01_PATH)
    h0c = read_json(root, H0C_FACTS_PATH)
    x1_2rf = read_json(root, X1_2RF_FACTS_PATH)
    nl0 = read_json(root, NL0_GOLD_PATH)
    s1_assertions = read_json(root, S1_ASSERTIONS_PATH)
    s1_citations = read_json(root, S1_CITATIONS_PATH)
    # This file is an explicit selection/audit input.  NL1 does not copy its
    # candidate narrative text into accepted context without a review record.
    _scene_contexts = read_json(root, SCENE_CONTEXTS_PATH)
    del _scene_contexts

    selected_ids = sorted_unique(spec["scope"]["selected_story_ids"])
    stories_by_id = {str(row["id"]): row for row in sc1.get("stories", [])}
    sc1_evidence = {str(row["id"]): row for row in sc1.get("evidence", [])}
    display_people = sc1.get("display", {}).get("people", {})
    hr0_by_story = {str(row["story_id"]): row for row in hr0_doc.get("records", [])}
    hr01_by_story = {str(row["story_id"]): row for row in hr01_doc.get("records", [])}
    nl0_by_story = {str(row["story_id"]): row for row in nl0.get("records", [])}
    s1_assertions_by_story: dict[str, list[str]] = {}
    for row in s1_assertions.get("records", []):
        story_id = row.get("story_id")
        assertion_id = row.get("assertion_id")
        if story_id and assertion_id:
            s1_assertions_by_story.setdefault(str(story_id), []).append(str(assertion_id))
    s1_citations_by_story: dict[str, list[str]] = {}
    for row in s1_citations.get("records", []):
        story_id = row.get("story_id")
        citation_id = row.get("citation_id")
        if story_id and citation_id:
            s1_citations_by_story.setdefault(str(story_id), []).append(str(citation_id))
    spec_by_story = {str(row["story_id"]): row for row in spec.get("records", [])}
    if set(spec_by_story) != set(selected_ids):
        raise ValueError("NL1 review spec records do not equal its frozen Story scope")
    missing = [story_id for story_id in selected_ids if story_id not in stories_by_id]
    if missing:
        raise ValueError(f"NL1 review spec contains unknown Stories: {missing}")

    hashes = source_hashes(root)
    contexts: list[dict[str, Any]] = []
    selections: list[dict[str, Any]] = []
    for story_id in selected_ids:
        spec_record = spec_by_story[story_id]
        story = stories_by_id[story_id]
        hr0 = hr0_by_story.get(story_id)
        context = build_context_record_with_evidence(
            spec_record,
            story,
            hr0,
            hr01_by_story.get(story_id),
            nl0_by_story.get(story_id),
            display_people,
            h0c,
            x1_2rf,
            sc1_evidence,
        )
        attach_s1_lineage(context, story_id, s1_assertions_by_story, s1_citations_by_story)
        contexts.append(context)
        selections.append(build_selection_record(spec_record, story, context))

    context_document = {
        "schema": "narrative-context",
        "stage": "NL1",
        "schema_version": "v0",
        "document_kind": "narrative_context",
        "scope": {
            "story_count": len(selected_ids),
            "selected_story_ids": selected_ids,
            "selection_policy": str(spec["scope"]["selection_policy"]),
        },
        "records": contexts,
        "counts": build_metrics(contexts, selections, hashes, selected_ids)["context"],
        "source_hashes": hashes,
        "policy": dict(POLICY),
    }
    selection_document = {
        "schema": "narrative-selection",
        "stage": "NL1",
        "schema_version": "v0",
        "document_kind": "narrative_selection",
        "scope": {
            "story_count": len(selected_ids),
            "selected_story_ids": selected_ids,
            "selection_policy": str(spec["scope"]["selection_policy"]),
        },
        "records": selections,
        "counts": build_metrics(contexts, selections, hashes, selected_ids)["selection"],
        "source_hashes": hashes,
        "policy": dict(POLICY),
    }
    metrics = build_metrics(contexts, selections, hashes, selected_ids)
    protection = {
        "schema": "nl1-protection-manifest",
        "stage": "NL1",
        "schema_version": "v0",
        "protected_inputs": {path.as_posix(): sha256_file(root, path) for path in PROTECTED_PATHS},
        "write_back": {
            "canonical_stories": False,
            "canonical_people": False,
            "canonical_mentions": False,
            "canonical_person_story": False,
            "canonical_relations": False,
            "canonical_facts": False,
            "hr0": False,
            "hr0_1": False,
            "nl0": False,
        },
        "selection_freeze": {
            "selected_story_ids": selected_ids,
            "review_spec_sha256": sha256_file(root, SPEC_PATH),
        },
    }
    summary = {
        "schema": "nl1-summary",
        "stage": "NL1",
        "schema_version": "v0",
        "source_hashes": hashes,
        "scope": {"story_count": len(selected_ids), "selected_story_ids": selected_ids},
        "counts": {
            "stories": len(selected_ids),
            "context_records": len(contexts),
            "selection_records": len(selections),
            "selected_candidates": metrics["selection"]["candidate_status_counts"]["selected"],
            "rejected_candidates": metrics["selection"]["candidate_status_counts"]["rejected"],
            "abstained_candidates": metrics["selection"]["candidate_status_counts"]["abstained"],
            "uncertainties": metrics["context"]["uncertainties"],
        },
        "role_distribution": metrics["role_distribution"],
        "selection_categories": metrics["selection_categories"],
        "s1_lineage": metrics["s1_lineage"],
        "unresolved_annotation_issues": metrics["unresolved_annotation_issues"],
        "recurring_patterns": metrics["selection_patterns"],
        "nl1_e_readiness": metrics["nl1_e_readiness"],
        "policy": dict(POLICY),
    }
    return {
        "context": context_document,
        "selection": selection_document,
        "metrics": metrics,
        "summary": summary,
        "protection": protection,
    }


def write_documents(root: Path = ROOT) -> None:
    documents = build_documents(root)
    outputs = {
        CONTEXT_PATH: documents["context"],
        SELECTION_PATH: documents["selection"],
        METRICS_PATH: documents["metrics"],
        SUMMARY_PATH: documents["summary"],
        PROTECTION_PATH: documents["protection"],
    }
    for relative, document in outputs.items():
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(stable_json(document), encoding="utf-8")
    print(
        f"NL1 built {documents['summary']['counts']['stories']} Stories, "
        f"{documents['summary']['counts']['selected_candidates']} selected narrative candidates, "
        f"{documents['summary']['counts']['rejected_candidates']} rejected guards, "
        f"{documents['summary']['counts']['abstained_candidates']} abstentions."
    )


if __name__ == "__main__":
    write_documents(ROOT)
