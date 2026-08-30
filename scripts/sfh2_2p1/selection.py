"""Frozen, occurrence-level SFH2.2-P1 selection.

The expected values are evaluation metadata only.  The P1 provider packet
builder never copies them into a prompt.
"""

from __future__ import annotations

from typing import Any, Mapping

from .common import SELECTION_PATH, load_inputs, normalize, read_json, stable_hash, text, write_json


CASE_SPECS: tuple[dict[str, Any], ...] = (
    {
        "key": "wang-zijing-wang-xianzhi",
        "story_id": "02-yanyu-086",
        "surface": "王子敬",
        "source_evidence_id": "sfh1-ev-02-yanyu-086-main",
        "case_family": "full_appellation",
        "reason": "correct the reviewed identity direction from 王羲之 to 王獻之",
        "expected_proposal_kind": "historical_person",
        "expected_identity": "王獻之",
        "expected_referent_surface": "王子敬",
        "expected_identity_type": "candidate_historical_person",
        "must_not_resolve_to": ["person-001", "person-030"],
        "must_not_resolve_to_names": ["王羲之", "王恭"],
    },
    {
        "key": "ruan-guanglu-yuan-yu",
        "story_id": "04-wenxue-024",
        "surface": "阮光禄",
        "source_evidence_id": "sfh1-ev-04-wenxue-024-main",
        "case_family": "office_title",
        "reason": "test office/title to historical full-name proposal",
        "expected_proposal_kind": "historical_person",
        "expected_identity": "阮裕",
        "expected_referent_surface": "阮光禄",
        "expected_identity_type": "candidate_historical_person",
        "must_not_resolve_to": [],
        "must_not_resolve_to_names": [],
    },
    {
        "key": "xuanwang-simayi",
        "story_id": "33-youhui-007",
        "surface": "宣王",
        "source_evidence_id": "sfh1-ev-33-youhui-007-main",
        "case_family": "ruler_title",
        "reason": "test ruler/posthumous title to historical full-name proposal",
        "expected_proposal_kind": "historical_person",
        "expected_identity": "司馬懿",
        "expected_referent_surface": "宣王",
        "expected_identity_type": "candidate_historical_person",
        "must_not_resolve_to": [],
        "must_not_resolve_to_names": [],
    },
    {
        "key": "zi-jing-attribute",
        "story_id": "19-xianyuan-032",
        "surface": "字景真",
        "source_evidence_id": "sfh1-ev-19-xianyuan-032-liu-annotation-003",
        "case_family": "person_attribute",
        "reason": "prevent a courtesy-name attribute phrase from becoming a Person",
        "expected_proposal_kind": "person_attribute",
        "expected_identity": None,
        "expected_referent_surface": "景真",
        "expected_attribute_type": "courtesy_name",
        "expected_bearer": "桓亮",
        "expected_identity_type": "structural",
        "must_not_resolve_to": ["person-070"],
        "must_not_resolve_to_names": ["趙至"],
    },
    {
        "key": "qi-huan-gong-exemplum",
        "story_id": "02-yanyu-036",
        "surface": "齊桓公",
        "source_evidence_id": "sfh1-ev-02-yanyu-036-liu-annotation-001",
        "case_family": "historical_exemplum",
        "reason": "proposal-first ruler entity must not collapse to related 管仲/管夷吾",
        "expected_proposal_kind": "historical_person",
        "expected_identity": "齊桓公",
        "expected_referent_surface": "齊桓公",
        "expected_network_role": "historical_exemplum",
        "expected_identity_type": "candidate_historical_person",
        "must_not_resolve_to": [],
        "must_not_resolve_to_names": ["管仲", "管夷吾"],
    },
    {
        "key": "ying-person",
        "story_id": "09-pinzao-018",
        "surface": "潁",
        "source_evidence_id": "sfh1-ev-09-pinzao-018-main",
        "case_family": "abbreviated_person",
        "reason": "treat the explicitly introduced 王丞相之弟 as a Person without inventing a full name",
        "expected_proposal_kind": "historical_person",
        "expected_identity": "潁",
        "expected_referent_surface": "潁",
        "expected_identity_type": "candidate_historical_person",
        "expected_identity_is_surface": True,
        "must_not_resolve_to": ["person-022"],
        "must_not_resolve_to_names": ["鄧攸"],
    },
    {
        "key": "yan-zhongbi-yan-yin",
        "story_id": "08-shangyu-020",
        "surface": "嚴仲弼",
        "source_evidence_id": "sfh1-ev-08-shangyu-020-main",
        "case_family": "courtesy_name",
        "reason": "converge the whole courtesy-name form on 嚴隱",
        "expected_proposal_kind": "historical_person",
        "expected_identity": "嚴隱",
        "expected_referent_surface": "嚴仲弼",
        "expected_identity_type": "candidate_historical_person",
        "must_not_resolve_to": [],
        "must_not_resolve_to_names": [],
    },
    {
        "key": "cheqi-xiexuan",
        "story_id": "02-yanyu-078",
        "surface": "車騎",
        "source_evidence_id": "sfh1-ev-02-yanyu-078-main",
        "case_family": "office_title",
        "reason": "positive short office/appellation control for 謝玄",
        "expected_proposal_kind": "historical_person",
        "expected_identity": "謝玄",
        "expected_referent_surface": "車騎",
        "expected_identity_type": "candidate_historical_person",
        "must_not_resolve_to": [],
        "must_not_resolve_to_names": [],
    },
    {
        "key": "huan-xuanwu-huan-wen",
        "story_id": "25-paidiao-026",
        "surface": "桓宣武",
        "source_evidence_id": "sfh1-ev-25-paidiao-026-main",
        "case_family": "office_title",
        "reason": "positive historical title control for 桓溫",
        "expected_proposal_kind": "historical_person",
        "expected_identity": "桓溫",
        "expected_referent_surface": "桓宣武",
        "expected_identity_type": "production_person",
        "expected_person_id": "person-008",
        "must_not_resolve_to": [],
        "must_not_resolve_to_names": [],
    },
    {
        "key": "le-shile",
        "story_id": "01-dexing-028",
        "surface": "勒",
        "source_evidence_id": "sfh1-ev-01-dexing-028-liu-annotation-004",
        "case_family": "registry_miss",
        "reason": "known registry-miss semantic referent must not fall back to 王隱",
        "expected_proposal_kind": "historical_person",
        "expected_identity": "石勒",
        "expected_referent_surface": "勒",
        "expected_identity_type": "candidate_historical_person",
        "must_not_resolve_to": ["person-054"],
        "must_not_resolve_to_names": ["王隱"],
    },
)


def _find_mention(spec: Mapping[str, Any], inputs: Mapping[str, Any]) -> dict[str, Any] | None:
    rows = [
        row for row in inputs.get("mentions", {}).get("records", []) or []
        if isinstance(row, Mapping)
        and text(row.get("story_id")) == text(spec.get("story_id"))
        and text(row.get("surface")) == text(spec.get("surface"))
        and text(row.get("source_evidence_id")) == text(spec.get("source_evidence_id"))
    ]
    return dict(sorted(rows, key=lambda row: text(row.get("mention_id")))[0]) if rows else None


def build_selection(inputs: Mapping[str, Any] | None = None) -> dict[str, Any]:
    inputs = inputs or load_inputs()
    selected, missing = [], []
    for spec in CASE_SPECS:
        mention = _find_mention(spec, inputs)
        if not mention:
            missing.append({"key": spec["key"], "story_id": spec["story_id"], "surface": spec["surface"], "reason": "not present in frozen SFH1 validated mentions"})
            continue
        row = {
            "case_id": f"sfh2-2p1-{stable_hash({'key': spec['key'], 'mention_id': mention['mention_id']})[:20]}",
            "story_id": text(mention.get("story_id")),
            "mention_id": text(mention.get("mention_id")),
            "surface": text(mention.get("surface")),
            "source_evidence_id": text(mention.get("source_evidence_id")),
            "case_family": spec["case_family"],
            "evaluation_mode": "reviewed_gold",
            "reason_selected": spec["reason"],
            "expected_proposal_kind": spec["expected_proposal_kind"],
            "expected_identity": spec.get("expected_identity"),
            "expected_referent_surface": spec.get("expected_referent_surface"),
            "expected_identity_type": spec["expected_identity_type"],
            "expected_person_id": spec.get("expected_person_id"),
            "expected_attribute_type": spec.get("expected_attribute_type"),
            "expected_bearer": spec.get("expected_bearer"),
            "expected_network_role": spec.get("expected_network_role"),
            "must_not_resolve_to": sorted(set(text(value) for value in spec.get("must_not_resolve_to", []) if text(value))),
            "must_not_resolve_to_names": sorted(set(text(value) for value in spec.get("must_not_resolve_to_names", []) if text(value))),
            "selection_source": "frozen_sfh1_validated_mentions",
            "candidate_only": True,
            "canonical_write_back": False,
        }
        if spec.get("expected_identity_is_surface"):
            row["expected_identity_is_surface"] = True
        selected.append(row)
    selected.sort(key=lambda row: (row["story_id"], row["mention_id"], row["case_id"]))
    result = {
        "schema": "sfh2-2p1-selection-v1",
        "pilot": "SFH2.2-P1",
        "model": "deepseek-v4-flash",
        "prompt_versions": {
            "entity_proposal": "sfh2-2p1-entity-proposal-v3",
            "identity_equivalence": "sfh2-2p1-identity-equivalence-v1",
        },
        "case_count": len(selected),
        "gold_case_count": len(selected),
        "blind_case_count": 0,
        "cases": selected,
        "selection_missing_specs": missing,
        "selection_basis": "deterministic occurrence selectors over frozen SFH1 validated mentions; no provider output used",
        "candidate_only": True,
        "canonical_write_back": False,
    }
    result["selection_hash"] = stable_hash({key: value for key, value in result.items() if key != "selection_hash"})
    return result


def freeze_selection(path: Any = None) -> dict[str, Any]:
    path = path or SELECTION_PATH
    selection = build_selection()
    if path.is_file():
        previous = read_json(path, {}) or {}
        if previous != selection:
            raise RuntimeError("sfh2_2p1_selection_changed")
        return previous
    write_json(path, selection)
    return selection
