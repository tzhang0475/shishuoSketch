"""Frozen controlled selection for SFH2.2-A0.

The A0 cases are fixed by the experiment design.  This module resolves only
their validated mention IDs and source witnesses; evaluation expectations are
kept in a separate file and never enter a provider packet.
"""

from __future__ import annotations

from typing import Any, Mapping

from .common import GOLD_PATH, SELECTION_PATH, load_inputs, records, read_json, stable_hash, text, write_json


CASE_SPECS: tuple[dict[str, str], ...] = (
    {"key": "wang-zijing", "story_id": "02-yanyu-086", "surface": "王子敬", "source_evidence_id": "sfh1-ev-02-yanyu-086-main", "case_family": "appellation"},
    {"key": "ruan-guanglu", "story_id": "04-wenxue-024", "surface": "阮光禄", "source_evidence_id": "sfh1-ev-04-wenxue-024-main", "case_family": "office_title"},
    {"key": "xuan-wang", "story_id": "33-youhui-007", "surface": "宣王", "source_evidence_id": "sfh1-ev-33-youhui-007-main", "case_family": "ruler_title"},
    {"key": "zi-jingzhen", "story_id": "19-xianyuan-032", "surface": "字景真", "source_evidence_id": "sfh1-ev-19-xianyuan-032-liu-annotation-003", "case_family": "person_attribute"},
    {"key": "qi-huan-gong", "story_id": "02-yanyu-036", "surface": "齊桓公", "source_evidence_id": "sfh1-ev-02-yanyu-036-liu-annotation-001", "case_family": "historical_exemplum"},
    {"key": "qing", "story_id": "23-rendan-026", "surface": "卿", "source_evidence_id": "sfh1-ev-23-rendan-026-main", "case_family": "discourse_reference"},
    {"key": "wu", "story_id": "11-jiewu-003", "surface": "吾", "source_evidence_id": "sfh1-ev-11-jiewu-003-main", "case_family": "discourse_reference"},
    {"key": "zhi", "story_id": "23-rendan-038", "surface": "之", "source_evidence_id": "sfh1-ev-23-rendan-038-main", "case_family": "abbreviated_reference"},
    {"key": "tao", "story_id": "04-wenxue-097", "surface": "滔", "source_evidence_id": "sfh1-ev-04-wenxue-097-liu-annotation-003", "case_family": "annotation_person"},
    {"key": "gu", "story_id": "35-huoni-002", "surface": "嘏", "source_evidence_id": "sfh1-ev-35-huoni-002-liu-annotation-003", "case_family": "annotation_person"},
    {"key": "xue-ying", "story_id": "01-dexing-004", "surface": "薛瑩", "source_evidence_id": "sfh1-ev-01-dexing-004-liu-annotation-001", "case_family": "citation_source"},
    {"key": "yuan-fujun", "story_id": "01-dexing-045", "surface": "袁府君", "source_evidence_id": "sfh1-ev-01-dexing-045-main", "case_family": "office_title"},
    {"key": "taiqiu-zhang", "story_id": "03-zhengshi-001", "surface": "太丘長", "source_evidence_id": "sfh1-ev-03-zhengshi-001-main", "case_family": "office_title"},
    {"key": "wang-lantian", "story_id": "04-wenxue-022", "surface": "王藍田", "source_evidence_id": "sfh1-ev-04-wenxue-022-main", "case_family": "appellation"},
    {"key": "mao-hong", "story_id": "18-qiyi-004", "surface": "茂弘", "source_evidence_id": "sfh1-ev-18-qiyi-004-main", "case_family": "courtesy_name"},
    {"key": "kang", "story_id": "23-rendan-001", "surface": "康", "source_evidence_id": "sfh1-ev-23-rendan-001-main", "case_family": "abbreviated_reference"},
    {"key": "zhong-shiji", "story_id": "08-shangyu-006", "surface": "鍾士季", "source_evidence_id": "sfh1-ev-08-shangyu-006-main", "case_family": "courtesy_name"},
    {"key": "ruan-sizong", "story_id": "01-dexing-015", "surface": "阮嗣宗", "source_evidence_id": "sfh1-ev-01-dexing-015-main", "case_family": "courtesy_name"},
    {"key": "yan-zhongbi", "story_id": "08-shangyu-020", "surface": "嚴仲弼", "source_evidence_id": "sfh1-ev-08-shangyu-020-main", "case_family": "courtesy_name"},
    {"key": "wang-shi", "story_id": "05-fangzheng-034", "surface": "王師", "source_evidence_id": "sfh1-ev-05-fangzheng-034-liu-annotation-005", "case_family": "collective_reference"},
)


def _find(spec: Mapping[str, str], inputs: Mapping[str, Any]) -> dict[str, Any] | None:
    rows = [
        row for row in records(inputs.get("mentions"), "records")
        if text(row.get("story_id")) == spec["story_id"]
        and text(row.get("surface")) == spec["surface"]
        and text(row.get("source_evidence_id")) == spec["source_evidence_id"]
    ]
    return dict(sorted(rows, key=lambda row: text(row.get("mention_id")))[0]) if rows else None


def build_selection(inputs: Mapping[str, Any] | None = None) -> dict[str, Any]:
    inputs = inputs or load_inputs()
    selected: list[dict[str, Any]] = []
    missing: list[dict[str, str]] = []
    for spec in CASE_SPECS:
        mention = _find(spec, inputs)
        if not mention:
            missing.append({"key": spec["key"], "story_id": spec["story_id"], "surface": spec["surface"], "reason": "validated mention not found"})
            continue
        selected.append({
            "case_id": "sfh2-a0-" + stable_hash({"key": spec["key"], "mention_id": mention.get("mention_id")})[:20],
            "story_id": text(mention.get("story_id")),
            "mention_id": text(mention.get("mention_id")),
            "surface": text(mention.get("surface")),
            "source_evidence_id": text(mention.get("source_evidence_id")),
            "case_family": spec["case_family"],
            "selection_reason": "fixed controlled semantic-authority pilot case",
            "candidate_only": True,
            "canonical_write_back": False,
        })
    selected.sort(key=lambda row: (row["story_id"], row["mention_id"], row["case_id"]))
    result: dict[str, Any] = {
        "schema": "sfh2-a0-selection-v1",
        "pilot": "SFH2.2-A0",
        "selection_version": "sfh2-a0-controlled-v1",
        "case_count": len(selected),
        "cases": selected,
        "selection_missing_specs": missing,
        "selection_basis": "fixed occurrence selectors over the frozen SFH1 validated-mention ledger; no evaluation answer or provider output used",
        "gold_fields_present": False,
        "gold_not_in_selection": True,
        "candidate_only": True,
        "canonical_write_back": False,
    }
    result["selection_hash"] = stable_hash({key: value for key, value in result.items() if key != "selection_hash"})
    return result


def freeze_selection(path: Any = None, inputs: Mapping[str, Any] | None = None) -> dict[str, Any]:
    path = path or SELECTION_PATH
    current = build_selection(inputs)
    if path.is_file():
        previous = read_json(path, {}) or {}
        if previous != current:
            raise RuntimeError("sfh2_a0_selection_changed")
        return previous
    write_json(path, current)
    return current


def build_evaluation_gold() -> dict[str, Any]:
    """Return the reviewed evaluation-only labels, never used in prompts."""

    by_key = {spec["key"]: spec for spec in CASE_SPECS}
    # This function intentionally contains only evaluation labels.  Runtime
    # semantic code never imports this mapping.
    labels: dict[str, dict[str, Any]] = {
        "wang-zijing": {"expected_semantic_kind": "historical_person", "expected_referent_surface": "王子敬", "expected_canonical_hint": "王獻之", "must_not_resolve_to": ["王羲之", "王恭"]},
        "ruan-guanglu": {"expected_semantic_kind": "historical_person", "expected_referent_surface": "阮光禄", "expected_canonical_hint": "阮裕"},
        "xuan-wang": {"expected_semantic_kind": "historical_person", "expected_referent_surface": "宣王", "expected_canonical_hint": "司馬懿"},
        "zi-jingzhen": {"expected_semantic_kind": "person_attribute", "expected_referent_surface": "景真", "expected_attribute_type": "courtesy_name", "expected_attribute_value": "景真", "expected_bearer": "桓亮", "expected_role": "person_attribute"},
        "qi-huan-gong": {"expected_semantic_kind": "historical_person", "expected_referent_surface": "齊桓公", "expected_canonical_hint": "齊桓公", "expected_role": "historical_exemplum", "must_not_resolve_to": ["管仲", "管夷吾"]},
        "qing": {"expected_semantic_kind": "historical_person", "expected_referent_surface": "卿", "expected_canonical_hint": "庾亮"},
        "wu": {"expected_semantic_kind": "historical_person", "expected_referent_surface": "吾", "expected_canonical_hint": "曹操"},
        "zhi": {"expected_semantic_kind": "historical_person", "expected_referent_surface": "之", "expected_canonical_hint": "劉驎之"},
        "tao": {"expected_semantic_kind": "historical_person", "expected_referent_surface": "滔", "expected_canonical_hint": "伏滔", "expected_role": "annotation_person"},
        "gu": {"expected_semantic_kind": "historical_person", "expected_referent_surface": "嘏", "expected_canonical_hint": "傅嘏", "expected_role": "annotation_person"},
        "xue-ying": {"expected_semantic_kind": "historical_person", "expected_referent_surface": "薛瑩", "expected_canonical_hint": "薛瑩", "expected_role": "citation_source_person"},
        "yuan-fujun": {"expected_semantic_kind": "historical_person", "expected_referent_surface": "袁府君", "expected_canonical_hint": "袁山松", "allow_abstention": True},
        "taiqiu-zhang": {"expected_semantic_kind": "office", "expected_referent_surface": "太丘長", "expected_role": "person_attribute", "expected_attribute_type": "office_held", "expected_attribute_value": "太丘長", "expected_bearer": "陳仲弓", "expected_bearer_canonical_hint": "陳寔"},
        "wang-lantian": {"expected_semantic_kind": "historical_person", "expected_referent_surface": "王藍田", "expected_canonical_hint": "王述"},
        "mao-hong": {"expected_semantic_kind": "historical_person", "expected_referent_surface": "茂弘", "expected_canonical_hint": "王導"},
        "kang": {"expected_semantic_kind": "historical_person", "expected_referent_surface": "康", "expected_canonical_hint": "嵇康"},
        "zhong-shiji": {"expected_semantic_kind": "historical_person", "expected_referent_surface": "鍾士季", "expected_canonical_hint": "鍾會"},
        "ruan-sizong": {"expected_semantic_kind": "historical_person", "expected_referent_surface": "阮嗣宗", "expected_canonical_hint": "阮籍"},
        "yan-zhongbi": {"expected_semantic_kind": "historical_person", "expected_referent_surface": "嚴仲弼", "expected_canonical_hint": "嚴隱"},
        "wang-shi": {"expected_semantic_kind": "collective", "expected_referent_surface": "王師", "expected_role": "collective_reference", "must_not_create_person": True},
    }
    result: dict[str, Any] = {
        "schema": "sfh2-a0-evaluation-gold-v3",
        "pilot": "SFH2.2-A0",
        "evaluation_only": True,
        "not_for_provider": True,
        "records": [],
        "candidate_only": True,
        "canonical_write_back": False,
    }
    result["revision"] = {
        "authority": "human_semantic_review",
        "authority_record": "data/annotation/sfh2-a2gr-human-semantic-authority.json",
        "predecessor_stage": "SFH2.2-A2G",
        "promotion_reason": "Resolve the office-versus-person semantic boundary identified by the offline A2G audit without changing the frozen inference outputs.",
        "reaffirmed_cases": ["tao", "gu", "wang-shi"],
        "revision_id": "sfh2-a2gr-v1",
        "stage": "SFH2.2-A2GR",
        "substantive_changed_cases": ["taiqiu-zhang"],
        "previous_sha256": "82f36497b632032bc164c09fd5db97e35e20c256fc9654ac0d2c9b4c704b0b93",
    }
    for spec in CASE_SPECS:
        label = dict(labels[spec["key"]])
        label.update({"case_key": spec["key"], "story_id": spec["story_id"], "surface": spec["surface"]})
        result["records"].append(label)
    return result


def freeze_gold(path: Any = None, *, allow_version_transition: bool = False) -> dict[str, Any]:
    path = path or GOLD_PATH
    current = build_evaluation_gold()
    if path.is_file():
        previous = read_json(path, {}) or {}
        if previous != current:
            if allow_version_transition and text(previous.get("schema")) == "sfh2-a0-evaluation-gold-v1":
                write_json(path, current)
                return current
            raise RuntimeError("sfh2_a0_evaluation_gold_changed")
        return previous
    write_json(path, current)
    return current
