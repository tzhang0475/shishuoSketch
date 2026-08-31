"""Deterministic held-out occurrence selection for A0R-L."""

from __future__ import annotations

from typing import Any, Mapping

from .common import (
    CHALLENGE_SELECTION_PATH,
    CHALLENGE_STORIES,
    ROOT,
    a0_selection,
    load_inputs,
    records,
    read_json,
    stable_hash,
    text,
    write_json,
)

# Selection metadata describes why an occurrence is useful for a challenge;
# it is never copied into the LLM packet and is not an expected answer.
CHALLENGE_SPECS: tuple[dict[str, Any], ...] = (
    {"story_id": "09-pinzao-063", "surface": "吾", "source_evidence_id": "sfh1-ev-09-pinzao-063-main", "risk_dimensions": ["pronoun_coreference"], "reason": "validated main-text pronoun occurrence"},
    {"story_id": "09-pinzao-063", "surface": "康伯", "source_evidence_id": "sfh1-ev-09-pinzao-063-main", "risk_dimensions": ["courtesy_style_form", "multiple_contemporaries"], "reason": "validated short historical form in comparison context"},
    {"story_id": "09-pinzao-063", "surface": "文度", "source_evidence_id": "sfh1-ev-09-pinzao-063-main", "risk_dimensions": ["courtesy_style_form", "legacy_candidate_conflict"], "reason": "validated form with prior misleading retrieval candidate"},
    {"story_id": "09-pinzao-063", "surface": "庾道季", "source_evidence_id": "sfh1-ev-09-pinzao-063-main", "risk_dimensions": ["courtesy_style_form", "multiple_contemporaries"], "reason": "validated named/style form anchoring local context"},
    {"story_id": "25-paidiao-015", "surface": "周侯", "source_evidence_id": "sfh1-ev-25-paidiao-015-main", "risk_dimensions": ["title_honorific", "dialogue"], "reason": "validated title reference in dialogue"},
    {"story_id": "25-paidiao-015", "surface": "卿", "source_evidence_id": "sfh1-ev-25-paidiao-015-main", "risk_dimensions": ["pronoun_coreference", "speaker_addressee"], "reason": "validated second-person discourse surface"},
    {"story_id": "25-paidiao-015", "surface": "謝幼輿", "source_evidence_id": "sfh1-ev-25-paidiao-015-main", "risk_dimensions": ["courtesy_style_form", "dialogue"], "reason": "validated surname-plus-style form"},
    {"story_id": "25-paidiao-015", "surface": "顗", "source_evidence_id": "sfh1-ev-25-paidiao-015-liu-annotation-001", "risk_dimensions": ["abbreviated_form", "annotation_main_interaction"], "reason": "validated annotation-layer abbreviated occurrence"},
    {"story_id": "21-qiaoyi-011", "surface": "殷荆州", "source_evidence_id": "sfh1-ev-21-qiaoyi-011-main", "risk_dimensions": ["office_honorific", "multiple_forms"], "reason": "validated office-based reference"},
    {"story_id": "21-qiaoyi-011", "surface": "明府", "source_evidence_id": "sfh1-ev-21-qiaoyi-011-main", "risk_dimensions": ["title_honorific", "local_coreference"], "reason": "validated honorific in local interaction"},
    {"story_id": "21-qiaoyi-011", "surface": "我", "source_evidence_id": "sfh1-ev-21-qiaoyi-011-main", "risk_dimensions": ["pronoun_coreference", "speaker_addressee"], "reason": "validated first-person discourse occurrence"},
    {"story_id": "21-qiaoyi-011", "surface": "顧", "source_evidence_id": "sfh1-ev-21-qiaoyi-011-main", "risk_dimensions": ["abbreviated_form", "multiple_forms"], "reason": "validated surname abbreviation beside a full form"},
    {"story_id": "10-guizhen-011", "surface": "身", "source_evidence_id": "sfh1-ev-10-guizhen-011-liu-annotation-001", "risk_dimensions": ["person_attribute", "annotation_main_interaction"], "reason": "validated annotation-layer reference"},
    {"story_id": "10-guizhen-011", "surface": "帝", "source_evidence_id": "sfh1-ev-10-guizhen-011-main", "risk_dimensions": ["ruler_reference", "repeated_surface"], "reason": "first validated 帝 occurrence kept independent by source"},
    {"story_id": "10-guizhen-011", "surface": "帝", "source_evidence_id": "sfh1-ev-10-guizhen-011-liu-annotation-002", "risk_dimensions": ["ruler_reference", "repeated_surface", "annotation_main_interaction"], "reason": "second validated 帝 occurrence kept independent by source"},
    {"story_id": "10-guizhen-011", "surface": "元帝", "source_evidence_id": "sfh1-ev-10-guizhen-011-main", "risk_dimensions": ["ruler_reference", "full_form"], "reason": "validated ruler-form occurrence"},
    {"story_id": "02-yanyu-060", "surface": "簡文", "source_evidence_id": "sfh1-ev-02-yanyu-060-main", "risk_dimensions": ["ruler_reference", "local_coreference"], "reason": "validated ruler appellation in scene"},
    {"story_id": "02-yanyu-060", "surface": "上", "source_evidence_id": "sfh1-ev-02-yanyu-060-main", "risk_dimensions": ["ruler_reference", "pronoun_coreference"], "reason": "validated ruler title in dialogue"},
    {"story_id": "02-yanyu-060", "surface": "某", "source_evidence_id": "sfh1-ev-02-yanyu-060-main", "risk_dimensions": ["anonymous_anaphora", "repeated_surface"], "reason": "validated local anaphoric occurrence"},
    {"story_id": "02-yanyu-060", "surface": "宣武", "source_evidence_id": "sfh1-ev-02-yanyu-060-main", "risk_dimensions": ["ruler_reference", "title_honorific", "local_coreference"], "reason": "validated historical title in scene"},
)


def _find(spec: Mapping[str, Any], inputs: Mapping[str, Any]) -> dict[str, Any] | None:
    rows = [
        row for row in records(inputs.get("mentions"), "records")
        if text(row.get("story_id")) == text(spec.get("story_id"))
        and text(row.get("surface")) == text(spec.get("surface"))
        and text(row.get("source_evidence_id")) == text(spec.get("source_evidence_id"))
    ]
    return dict(sorted(rows, key=lambda row: (text(row.get("mention_id")), text(row.get("source_start"))))[0]) if rows else None


def build_selection(inputs: Mapping[str, Any] | None = None) -> dict[str, Any]:
    inputs = inputs or load_inputs()
    prior = []
    for path in (
        ROOT / "data/annotation/sfh2-a0-selection.json",
        ROOT / "data/annotation/sfh2-2p1-selection.json",
        ROOT / "data/annotation/sfh2-2p2-selection.json",
    ):
        prior.extend((read_json(path, {}) or {}).get("cases", []) or [])
    prior_keys = {(text(row.get("story_id")), text(row.get("mention_id"))) for row in prior if isinstance(row, Mapping)}
    prior_story_ids = {story_id for story_id, _ in prior_keys if story_id}
    story_overlap = [story_id for story_id in CHALLENGE_STORIES if story_id in prior_story_ids]
    selected: list[dict[str, Any]] = []
    missing: list[dict[str, Any]] = []
    overlap: list[dict[str, Any]] = []
    for spec in CHALLENGE_SPECS:
        mention = _find(spec, inputs)
        if not mention:
            missing.append({"story_id": spec["story_id"], "surface": spec["surface"], "source_evidence_id": spec["source_evidence_id"], "reason": "validated occurrence not found"})
            continue
        key = (text(spec["story_id"]), text(mention.get("mention_id")))
        if key in prior_keys:
            overlap.append({"story_id": spec["story_id"], "mention_id": mention.get("mention_id"), "surface": spec["surface"], "reason": "previous targeted selection overlap"})
        selected.append({
            "case_id": "sfh2-a0r-l-challenge-" + stable_hash({"story_id": spec["story_id"], "mention_id": mention.get("mention_id"), "source_evidence_id": spec["source_evidence_id"]})[:20],
            "story_id": text(spec["story_id"]),
            "mention_id": text(mention.get("mention_id")),
            "surface": text(mention.get("surface")),
            "source_evidence_id": text(mention.get("source_evidence_id")),
            "risk_dimensions": list(spec["risk_dimensions"]),
            "selection_reason": text(spec["reason"]),
            "selection_seed": "sfh2-a0r-l-heldout-v1",
            "candidate_only": True,
            "canonical_write_back": False,
        })
    selected.sort(key=lambda row: (row["story_id"], row["mention_id"], row["case_id"]))
    story_counts = {story: sum(row["story_id"] == story for row in selected) for story in CHALLENGE_STORIES}
    result: dict[str, Any] = {
        "schema": "sfh2-a0r-l-challenge-selection-v1",
        "pilot": "SFH2.2-A0R-L",
        "selection_version": "sfh2-a0r-l-heldout-v1",
        "selection_seed": "sfh2-a0r-l-heldout-v1",
        "story_ids": list(CHALLENGE_STORIES),
        "story_list_hash": stable_hash(list(CHALLENGE_STORIES)),
        "case_count": len(selected),
        "story_count": len({row["story_id"] for row in selected}),
        "cases_per_story": story_counts,
        "cases": selected,
        "missing": missing,
        "previous_targeted_overlap": overlap,
        "previous_targeted_story_overlap": story_overlap,
        "selection_basis": "fixed high-risk validated occurrences from five frozen Stories; selection metadata only, no historical answer or provider output",
        "gold_fields_present": False,
        "gold_not_in_selection": True,
        "candidate_only": True,
        "canonical_write_back": False,
    }
    result["selection_hash"] = stable_hash({key: value for key, value in result.items() if key != "selection_hash"})
    return result


def freeze_selection(path: Any = None, inputs: Mapping[str, Any] | None = None) -> dict[str, Any]:
    path = path or CHALLENGE_SELECTION_PATH
    current = build_selection(inputs)
    if path.is_file():
        previous = read_json(path, {}) or {}
        if previous != current:
            raise RuntimeError("sfh2_a0r_l_challenge_selection_changed")
        return previous
    write_json(path, current)
    return current
