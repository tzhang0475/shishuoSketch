"""Frozen, deterministic SFH2.2-P case selection.

Selection is intentionally written separately from inference.  The expected
values below are evaluation metadata only; ``pipeline.py`` strips them before
constructing every provider packet.
"""

from __future__ import annotations

from typing import Any, Mapping

from .common import SELECTION_PATH, stable_hash, text, write_json, read_json, load_inputs, mention_index, packet_index


# These are occurrence selectors, not semantic rules.  Every selector is
# resolved against the already frozen SFH1 validated-mention ledger.
CASE_SPECS: tuple[dict[str, Any], ...] = (
    # Registry-miss / referent-hint cases.
    {"key": "勒-shile", "story_id": "01-dexing-028", "surface": "勒", "source_evidence_id": "sfh1-ev-01-dexing-028-liu-annotation-004", "family": "registry_missing", "reason": "reviewed abbreviated referent with a full-name anchor in supplied evidence", "expected": "石勒", "expected_type": "candidate_historical_person", "must_not": ["person-054"]},
    {"key": "興公-sunchuo", "story_id": "27-jiajue-012", "surface": "興公", "source_evidence_id": "sfh1-ev-27-jiajue-012-main", "family": "registry_missing", "reason": "reviewed courtesy/appellation whose production registry is incomplete", "expected": "孫綽", "expected_type": "candidate_historical_person", "must_not": ["person-015"]},
    {"key": "亮-huanliang", "story_id": "19-xianyuan-032", "surface": "亮", "source_evidence_id": "sfh1-ev-19-xianyuan-032-liu-annotation-004", "family": "registry_missing", "reason": "reviewed abbreviated name disambiguated by Liu annotation", "expected": "桓亮", "expected_type": "candidate_historical_person", "must_not": ["person-070"]},
    {"key": "桓景真-huanliang", "story_id": "19-xianyuan-032", "surface": "桓景真", "source_evidence_id": "sfh1-ev-19-xianyuan-032-main", "family": "shared_contextual", "reason": "whole-form occurrence supplies context for the shared courtesy name 景真", "expected": "桓亮", "expected_type": "candidate_historical_person", "must_not": ["person-070"]},
    {"key": "字景真-attribute", "story_id": "19-xianyuan-032", "surface": "字景真", "source_evidence_id": "sfh1-ev-19-xianyuan-032-liu-annotation-003", "family": "shared_contextual", "reason": "attribute phrase must not become an independent Person", "expected": None, "expected_type": "structural", "must_not": ["person-070"]},
    # Shared/contextual forms.
    {"key": "伯倫-liuling", "story_id": "04-wenxue-069", "surface": "伯倫", "source_evidence_id": "sfh1-ev-04-wenxue-069-liu-annotation-001", "family": "shared_contextual", "reason": "reviewed 劉伶 courtesy-name context", "expected": "劉伶", "expected_type": "production_person", "expected_person_id": "person-047", "must_not": []},
    {"key": "敬祖-huanqian", "story_id": "09-pinzao-088", "surface": "敬祖", "source_evidence_id": "sfh1-ev-09-pinzao-088-liu-annotation-001", "family": "shared_contextual", "reason": "reviewed 桓謙 courtesy-name context, shared with 卞範之", "expected": "桓謙", "expected_type": "candidate_historical_person", "must_not": ["person-066"]},
    # Office/title and role-sensitive cases.
    {"key": "王丞相-wangdao", "story_id": "02-yanyu-036", "surface": "王丞相", "source_evidence_id": "sfh1-ev-02-yanyu-036-main", "family": "office_title", "reason": "office title must be resolved contextually and not through a global alias", "expected": "王導", "expected_type": "production_person", "expected_person_id": "person-003", "must_not": ["person-054"]},
    {"key": "王大將軍-wangdun", "story_id": "05-fangzheng-031", "surface": "王大將軍", "source_evidence_id": "sfh1-ev-05-fangzheng-031-main", "family": "office_title", "reason": "reviewed 王敦 office context must not retrieve 王隱", "expected": "王敦", "expected_type": "production_person", "expected_person_id": "person-011", "must_not": ["person-054"]},
    {"key": "主簿-hechong", "story_id": "05-fangzheng-028", "surface": "主簿", "source_evidence_id": "sfh1-ev-05-fangzheng-028-main", "family": "office_title", "reason": "office holder and 王敦 patron must remain separate", "expected": "何充", "expected_type": "production_person", "expected_person_id": "person-025", "must_not": ["person-011"]},
    {"key": "謝豫章-xiekun", "story_id": "02-yanyu-046", "surface": "謝豫章", "source_evidence_id": "sfh1-ev-02-yanyu-046-main", "family": "office_title", "reason": "title/name reference is distinct from the child 謝尚", "expected": "謝鯤", "expected_type": "production_person", "expected_person_id": "person-023", "must_not": ["person-018"]},
    # Existing-person positive controls.
    {"key": "宣王-simayi", "story_id": "33-youhui-007", "surface": "宣王", "source_evidence_id": "sfh1-ev-33-youhui-007-main", "family": "existing_person", "reason": "ruler-title direction with historical source context", "expected": "司馬懿", "expected_type": "candidate_historical_person", "must_not": []},
    {"key": "祖車騎-zuti", "story_id": "08-shangyu-043", "surface": "祖車騎", "source_evidence_id": "sfh1-ev-08-shangyu-043-main", "family": "existing_person", "reason": "posthumous office/appellation with local full-name evidence", "expected": "祖逖", "expected_type": "candidate_historical_person", "must_not": ["person-011"]},
    {"key": "孔廷尉-kongtan", "story_id": "05-fangzheng-037", "surface": "孔廷尉", "source_evidence_id": "sfh1-ev-05-fangzheng-037-main", "family": "existing_person", "reason": "office-holder direction grounded by local 孔坦 mention", "expected": "孔坦", "expected_type": "candidate_historical_person", "must_not": []},
    {"key": "劉尹-liudan", "story_id": "02-yanyu-054", "surface": "劉尹", "source_evidence_id": "sfh1-ev-02-yanyu-054-main", "family": "existing_person", "reason": "local 真長 and supplied historical context distinguish 劉惔 from other 劉尹 uses", "expected": "劉惔", "expected_type": "production_person", "expected_person_id": "person-009", "must_not": ["person-071"]},
    {"key": "士龍-luyun", "story_id": "08-shangyu-020", "surface": "士龍", "source_evidence_id": "sfh1-ev-08-shangyu-020-liu-annotation-007", "family": "existing_person", "reason": "courtesy-name direction is supplied by the 陸雲 annotation", "expected": "陸雲", "expected_type": "candidate_historical_person", "must_not": []},
    {"key": "阮光祿-yuan yu", "story_id": "04-wenxue-024", "surface": "阮光禄", "source_evidence_id": "sfh1-ev-04-wenxue-024-main", "family": "existing_person", "reason": "office/title direction with Liu source evidence", "expected": "阮裕", "expected_type": "candidate_historical_person", "must_not": []},
    {"key": "聘-xiepin", "story_id": "09-pinzao-040", "surface": "聘", "source_evidence_id": "sfh1-ev-09-pinzao-040-liu-annotation-001", "family": "existing_person", "reason": "directional genealogy: 謝奉弟聘", "expected": "謝聘", "expected_type": "candidate_historical_person", "must_not": []},
    {"key": "朕-kangdi", "story_id": "05-fangzheng-041", "surface": "朕", "source_evidence_id": "sfh1-ev-05-fangzheng-041-main", "family": "existing_person", "reason": "ruler pronoun must use the surrounding accession context", "expected": "康帝", "expected_type": "candidate_historical_person", "must_not": []},
    # Negative/safety controls.
    {"key": "仲文-not-zhusi", "story_id": "09-pinzao-088", "surface": "仲文", "source_evidence_id": "sfh1-ev-09-pinzao-088-main", "family": "negative_control", "reason": "local comparison identifies 殷仲文, not 朱伺", "expected": "殷仲文", "expected_type": "candidate_historical_person", "must_not": ["person-031"]},
    {"key": "潁-not-dengyou", "story_id": "09-pinzao-018", "surface": "潁", "source_evidence_id": "sfh1-ev-09-pinzao-018-main", "family": "negative_control", "reason": "comparison participant is not the profile-borrowed 鄧攸", "expected": None, "expected_type": "contextual", "must_not": ["person-022"]},
    {"key": "殷荊州-not-wanggong", "story_id": "06-yaliang-041", "surface": "殷荆州", "source_evidence_id": "sfh1-ev-06-yaliang-041-main", "family": "negative_control", "reason": "office/title reference is distinct from nearby 王恭", "expected": "殷仲堪", "expected_type": "candidate_historical_person", "must_not": ["person-030"]},
    {"key": "王子敬-not-wanggong", "story_id": "02-yanyu-086", "surface": "王子敬", "source_evidence_id": "sfh1-ev-02-yanyu-086-main", "family": "negative_control", "reason": "full historical appellation is not 王恭/王孝伯", "expected": "王羲之", "expected_type": "production_person", "expected_person_id": "person-001", "must_not": ["person-030"]},
    {"key": "武子-not-kinship", "story_id": "05-fangzheng-011", "surface": "武子", "source_evidence_id": "sfh1-ev-05-fangzheng-011-main", "family": "negative_control", "reason": "whole-form personal/courtesy interpretation must not be forced into suffix kinship", "expected": "王濟", "expected_type": "candidate_historical_person", "must_not": []},
    {"key": "桓-local", "story_id": "23-rendan-049", "surface": "桓", "source_evidence_id": "sfh1-ev-23-rendan-049-main", "family": "negative_control", "reason": "single-character surname requires local antecedent reasoning", "expected": "桓伊", "expected_type": "candidate_historical_person", "must_not": []},
    # Blind controls are intentionally gold-free to the provider.
    {"key": "blind-cheqi", "story_id": "02-yanyu-078", "surface": "車騎", "source_evidence_id": "sfh1-ev-02-yanyu-078-main", "family": "blind_control", "reason": "short office/appellation with multiple local historical people", "blind": True},
    {"key": "blind-guyanxian", "story_id": "08-shangyu-020", "surface": "顧彦先", "source_evidence_id": "sfh1-ev-08-shangyu-020-main", "family": "blind_control", "reason": "courtesy-name form in a dense multi-person catalogue", "blind": True},
    {"key": "blind-yan仲弼", "story_id": "08-shangyu-020", "surface": "嚴仲弼", "source_evidence_id": "sfh1-ev-08-shangyu-020-main", "family": "blind_control", "reason": "whole-form courtesy-name reference", "blind": True},
    {"key": "blind-qihuangong", "story_id": "02-yanyu-036", "surface": "齊桓公", "source_evidence_id": "sfh1-ev-02-yanyu-036-liu-annotation-001", "family": "blind_control", "reason": "ruler reference in annotation/exemplum context", "blind": True},
    {"key": "blind-huanxuanwu", "story_id": "25-paidiao-026", "surface": "桓宣武", "source_evidence_id": "sfh1-ev-25-paidiao-026-main", "family": "blind_control", "reason": "office/title reference with local historical participants", "blind": True},
)


UNAVAILABLE_REVIEWED_CASES = [
    {"story_id": "05-fangzheng-015", "surface": "伯倫", "reason": "the Story is in the corpus but outside the frozen SFH1 188-Story packet universe; not expanded for this pilot"},
    {"story_id": "05-fangzheng-015", "surface": "山該字伯倫", "reason": "same frozen-universe boundary; no validated mention packet"},
    {"story_id": "<registered alias evidence>", "surface": "景真", "reason": "the clean 趙至 witness is in the reviewed alias/source registry, not as a validated mention in the current 188-Story SFH1 universe"},
    {"story_id": "<registered alias evidence>", "surface": "安國 / 萬年 / 子相", "reason": "shared-form controls are represented by reviewed registry evidence but not all have validated Story mentions in the frozen pilot universe"},
]


def _find_mention(spec: Mapping[str, Any], inputs: Mapping[str, Any]) -> dict[str, Any] | None:
    found = [
        row for row in inputs.get("mentions", {}).get("records", []) or []
        if isinstance(row, Mapping)
        and text(row.get("story_id")) == text(spec.get("story_id"))
        and text(row.get("surface")) == text(spec.get("surface"))
        and (not spec.get("source_evidence_id") or text(row.get("source_evidence_id")) == text(spec.get("source_evidence_id")))
    ]
    return dict(sorted(found, key=lambda row: text(row.get("mention_id")))[0]) if found else None


def build_selection(inputs: Mapping[str, Any] | None = None) -> dict[str, Any]:
    inputs = inputs or load_inputs()
    selected: list[dict[str, Any]] = []
    missing: list[dict[str, Any]] = []
    for spec in CASE_SPECS:
        mention = _find_mention(spec, inputs)
        if not mention:
            missing.append({"key": spec.get("key"), "story_id": spec.get("story_id"), "surface": spec.get("surface"), "reason": "not present in validated SFH1 mention ledger"})
            continue
        case_id = f"sfh2-2p-{stable_hash({'key': spec.get('key'), 'mention_id': mention.get('mention_id')})[:20]}"
        blind = bool(spec.get("blind"))
        row = {
            "case_id": case_id,
            "story_id": text(mention.get("story_id")),
            "mention_id": text(mention.get("mention_id")),
            "surface": text(mention.get("surface")),
            "source_evidence_id": text(mention.get("source_evidence_id")),
            "case_family": text(spec.get("family")),
            "evaluation_mode": "blind" if blind else "reviewed_gold",
            "reason_selected": text(spec.get("reason")),
            "expected_semantic_class": None if blind else text(mention.get("reference_form")),
            "expected_identity": None if blind else spec.get("expected"),
            "expected_identity_type": None if blind else spec.get("expected_type"),
            "expected_person_id": None if blind else spec.get("expected_person_id"),
            "must_not_resolve_to": [] if blind else sorted(set(text(value) for value in spec.get("must_not", []) if text(value))),
            "selection_source": "frozen_sfh1_validated_mentions",
            "candidate_only": True,
            "canonical_write_back": False,
        }
        selected.append(row)
    selected.sort(key=lambda row: (row["story_id"], row["mention_id"], row["case_id"]))
    core = {
        "schema": "sfh2-2p-selection-v1",
        "pilot": "SFH2.2-P",
        "model": "deepseek-v4-flash",
        "prompt_versions": {"reference_semantics": "sfh2-2p-l3-reference-semantics-v1", "identity_judgment": "sfh2-2p-l5-identity-judgment-v1"},
        "case_count": len(selected),
        "gold_case_count": sum(row["evaluation_mode"] == "reviewed_gold" for row in selected),
        "blind_case_count": sum(row["evaluation_mode"] == "blind" for row in selected),
        "cases": selected,
        "unavailable_reviewed_cases": UNAVAILABLE_REVIEWED_CASES,
        "selection_missing_specs": missing,
        "selection_basis": "deterministic occurrence selectors over frozen SFH1 validated mentions; no provider output used",
        "candidate_only": True,
        "canonical_write_back": False,
    }
    core["selection_hash"] = stable_hash({key: value for key, value in core.items() if key != "selection_hash"})
    return core


def freeze_selection(path: Any = None) -> dict[str, Any]:
    path = path or SELECTION_PATH
    selection = build_selection()
    if path.is_file():
        previous = read_json(path, {}) or {}
        if previous != selection:
            raise RuntimeError("sfh2_2p_selection_changed")
        return previous
    write_json(path, selection)
    return selection
