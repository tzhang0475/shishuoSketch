"""Deterministic, answer-blind selection for the SFH2.2-P2 pilot."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any, Iterable, Mapping

from .common import ROOT, SELECTION_PATH, load_inputs, normalize, read_json, records, stable_hash, text, write_json

SELECTION_SEED = "sfh2-2p2-blind-v1"
TARGET_COUNT = 24
STRATUM_QUOTAS = {
    "direct_full_personal": 4,
    "courtesy_style_nickname": 4,
    "office_title_ruler_appellation": 4,
    "short_abbreviated_reference": 3,
    "coreference_pronoun_antecedent": 3,
    "annotation_biographical_person": 2,
    "historical_exemplum_citation": 2,
    "structural_non_person_control": 2,
}


def _walk(value: Any) -> Iterable[Mapping[str, Any]]:
    if isinstance(value, Mapping):
        yield value
        for child in value.values():
            yield from _walk(child)
    elif isinstance(value, list):
        for child in value:
            yield from _walk(child)


def _add_prior_doc(path: Path, *, story_ids: set[str], mention_ids: set[str], pairs: set[tuple[str, str]], reasons: Counter[str]) -> None:
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return
    for row in _walk(document):
        story_id = text(row.get("story_id"))
        mention_id = text(row.get("mention_id"))
        surface = text(row.get("surface"))
        occurrence_id = text(row.get("occurrence_id"))
        if story_id and not story_id.startswith("<"):
            story_ids.add(story_id)
        if mention_id:
            mention_ids.add(mention_id)
        if occurrence_id:
            mention_ids.add(occurrence_id)
        if story_id and not story_id.startswith("<") and surface:
            pairs.add((story_id, surface))
    reasons[str(path.relative_to(ROOT))] += 1


def prior_exclusions() -> dict[str, Any]:
    """Collect prior semantic-pilot cases without reading their answers."""
    story_ids: set[str] = set()
    mention_ids: set[str] = set()
    pairs: set[tuple[str, str]] = set()
    reasons: Counter[str] = Counter()

    explicit = [
        ROOT / "data/generated/sfh2-2p/selection.json",
        ROOT / "data/generated/sfh2-2p1/selection.json",
        ROOT / "data/generated/sfh2/human-audit-sample.json",
        ROOT / "data/generated/sfh2r1/offline-replay/human-audit-sample.json",
        ROOT / "data/generated/sfh1/random-blind-audit.json",
        ROOT / "data/annotation/sfh2r-manual-semantic-authority.json",
        ROOT / "data/annotation/sfh2r1-manual-semantic-authority.json",
    ]
    for path in explicit:
        if path.is_file():
            _add_prior_doc(path, story_ids=story_ids, mention_ids=mention_ids, pairs=pairs, reasons=reasons)

    generated = ROOT / "data/generated"
    for path in sorted(generated.rglob("selection.json")):
        relative = str(path.relative_to(ROOT))
        # Isolated later pilots are not historical prior controls for the
        # already-frozen P2 sample.  In particular, reading A0's generated
        # copy here would make the old deterministic selection drift merely
        # because a new experiment was run.
        if "sfh2-2p2" in relative or "sfh2-a0" in relative:
            continue
        if any(token in relative.lower() for token in ("psl", "lj0", "xe0", "hdb2", "sfh2")):
            _add_prior_doc(path, story_ids=story_ids, mention_ids=mention_ids, pairs=pairs, reasons=reasons)

    # Keep this explicit list limited to development controls not guaranteed
    # to be present in an experiment selection artifact.  It is an exclusion
    # list only; no identity answer is used by sampling.
    known_controls = {
        ("05-fangzheng-011", "武子"), ("05-fangzheng-028", "主簿"), ("05-fangzheng-028", "敦主簿"),
        ("34-pilou-001", "主"), ("02-yanyu-046", "謝豫章"), ("09-pinzao-018", "潁"),
        ("09-pinzao-088", "仲文"), ("09-pinzao-088", "敬祖"), ("09-pinzao-088", "桓"),
        ("06-yaliang-041", "殷荆州"), ("02-yanyu-086", "王子敬"), ("23-rendan-049", "桓"),
        ("05-fangzheng-011", "武子"), ("05-fangzheng-028", "敦主簿"),
        ("02-yanyu-054", "劉尹"), ("05-fangzheng-041", "朕"), ("05-fangzheng-041", "陛下"),
        ("25-paidiao-026", "中丞"), ("05-fangzheng-053", "阮光禄"), ("09-pinzao-040", "聘"),
        ("06-yaliang-033", "鳯"), ("33-youhui-007", "宣王"), ("08-shangyu-043", "祖車騎"),
        ("05-fangzheng-037", "孔廷尉"), ("08-shangyu-020", "士龍"), ("01-dexing-028", "勒"),
        ("27-jiajue-012", "興公"), ("19-xianyuan-032", "亮"), ("19-xianyuan-032", "字景真"),
        ("19-xianyuan-032", "景真"), ("04-wenxue-024", "阮光禄"), ("02-yanyu-036", "齊桓公"),
        ("02-yanyu-078", "車騎"), ("08-shangyu-020", "嚴仲弼"), ("25-paidiao-026", "桓宣武"),
        ("04-wenxue-069", "伯倫"), ("09-pinzao-088", "桓謙"), ("09-pinzao-088", "桓玄"),
    }
    pairs.update(known_controls)
    # Blind generalization must also avoid reusing a hand-tuned surface in a
    # new Story.  This is deliberately an exclusion-only set; it contains no
    # answer or preferred identity and is never sent to the provider.
    known_surfaces = {
        "王子敬", "阮光禄", "宣王", "字景真", "齊桓公", "潁", "嚴仲弼", "車騎", "桓宣武", "勒", "興公",
        "景真", "伯倫", "敬祖", "安國", "世將", "萬年", "子相", "大業", "子少", "無忌", "令升",
        "王丞相", "王大將軍", "王庾諸公", "主簿", "敦主簿", "主", "謝豫章", "仲文", "桓", "桓謙", "桓玄",
        "殷荆州", "武子", "劉尹", "朕", "陛下", "中丞", "聘", "鳯", "祖車騎", "孔廷尉", "士龍",
        "桓景真", "亮", "潁", "齡", "閔氏", "殷仲文", "王子敬", "支道林", "顧長康", "裴叔則", "簡文",
        "謝萬", "孔文舉", "羊長和", "許掾", "袁紹", "庾文康", "佛經", "弓為太丘", "世稱庾文康",
    }
    return {
        "story_ids": sorted(story_ids),
        "mention_ids": sorted(mention_ids),
        "story_surface_pairs": [list(pair) for pair in sorted(pairs)],
        "surfaces": sorted(known_surfaces),
        "source_documents": dict(sorted(reasons.items())),
    }


def _semantic_rows(inputs: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    return {text(row.get("mention_id")): dict(row) for row in records(inputs.get("semantics"), "records") if text(row.get("mention_id"))}


def _is_person(row: Mapping[str, Any]) -> bool:
    return text(row.get("entity_kind")) == "person"


def _role_contains(row: Mapping[str, Any], terms: tuple[str, ...]) -> bool:
    role = text(row.get("referent_role")).lower()
    return bool(role) and any(term in role for term in terms)


def _pool(row: Mapping[str, Any], semantic: Mapping[str, Any]) -> str | None:
    entity_kind = text(row.get("entity_kind"))
    reference_form = text(row.get("reference_form"))
    surface = normalize(row.get("surface"))
    if entity_kind != "person" or reference_form in {"kinship_reference", "uncertain"}:
        return "structural_non_person_control"
    if _role_contains(semantic, ("author", "citation", "cited", "source", "exemplum", "historical example")):
        return "historical_exemplum_citation"
    if "liu-annotation" in text(row.get("source_evidence_id")):
        return "annotation_biographical_person"
    if text(semantic.get("semantic_type")) in {"local_anaphoric_reference"} or reference_form == "pronoun_reference":
        return "coreference_pronoun_antecedent"
    if len(surface) <= 2 or reference_form in {"surname_reference", "abbreviated_reference"}:
        return "short_abbreviated_reference"
    if reference_form in {"office_title", "ruler_title", "honorific"}:
        return "office_title_ruler_appellation"
    if reference_form in {"courtesy_name", "style_name", "nickname"}:
        return "courtesy_style_nickname"
    if reference_form in {"full_name", "personal_name"}:
        return "direct_full_personal"
    return "direct_full_personal"


def _ordered(pool: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(pool, key=lambda row: stable_hash({"seed": SELECTION_SEED, "mention_id": row.get("mention_id"), "surface": row.get("surface")}))


def _choose(pool: list[dict[str, Any]], count: int, selected: list[dict[str, Any]]) -> list[dict[str, Any]]:
    used_stories = {text(row.get("story_id")) for row in selected}
    available = [row for row in _ordered(pool) if text(row.get("mention_id")) not in {text(item.get("mention_id")) for item in selected}]
    diverse = [row for row in available if text(row.get("story_id")) not in used_stories]
    return (diverse + [row for row in available if row not in diverse])[:count]


def build_selection(inputs: Mapping[str, Any] | None = None) -> dict[str, Any]:
    inputs = inputs or load_inputs()
    exclusions = prior_exclusions()
    excluded_stories = set(exclusions["story_ids"])
    excluded_mentions = set(exclusions["mention_ids"])
    excluded_pairs = {tuple(pair) for pair in exclusions["story_surface_pairs"]}
    excluded_surfaces = set(exclusions["surfaces"])
    semantics = _semantic_rows(inputs)
    all_mentions = [dict(row) for row in records(inputs.get("mentions"), "records") if text(row.get("mention_id"))]
    eligible: list[dict[str, Any]] = []
    exclusion_counts: Counter[str] = Counter()
    for row in all_mentions:
        story_id, mention_id, surface = text(row.get("story_id")), text(row.get("mention_id")), text(row.get("surface"))
        if story_id in excluded_stories:
            exclusion_counts["prior_story"] += 1
            continue
        if mention_id in excluded_mentions:
            exclusion_counts["prior_mention"] += 1
            continue
        if (story_id, surface) in excluded_pairs:
            exclusion_counts["prior_story_surface"] += 1
            continue
        if surface in excluded_surfaces:
            exclusion_counts["prior_surface"] += 1
            continue
        semantic = semantics.get(mention_id, {})
        stratum = _pool(row, semantic)
        if not stratum:
            exclusion_counts["no_stratum"] += 1
            continue
        row["_stratum"] = stratum
        eligible.append(row)

    selected: list[dict[str, Any]] = []
    quota_shortfalls: dict[str, int] = {}
    for stratum, quota in STRATUM_QUOTAS.items():
        pool = [row for row in eligible if row.get("_stratum") == stratum]
        chosen = _choose(pool, quota, selected)
        selected.extend(chosen)
        if len(chosen) < quota:
            quota_shortfalls[stratum] = quota - len(chosen)

    if len(selected) < TARGET_COUNT:
        remaining = [row for row in _ordered(eligible) if text(row.get("mention_id")) not in {text(item.get("mention_id")) for item in selected}]
        selected.extend(_choose(remaining, TARGET_COUNT - len(selected), selected))
    selected = selected[:TARGET_COUNT]

    cases = []
    for row in sorted(selected, key=lambda item: (text(item.get("story_id")), text(item.get("mention_id")))):
        case_id = "sfh2-2p2-" + stable_hash({"mention_id": row.get("mention_id"), "seed": SELECTION_SEED})[:20]
        cases.append({
            "case_id": case_id,
            "story_id": text(row.get("story_id")),
            "mention_id": text(row.get("mention_id")),
            "surface": text(row.get("surface")),
            "source_evidence_id": text(row.get("source_evidence_id")),
            "case_family": text(row.get("_stratum")) or "fallback",
            "selection_reason": f"deterministic blind stratum: {text(row.get('_stratum')) or 'fallback'}",
            "selection_seed": SELECTION_SEED,
            "candidate_only": True,
            "canonical_write_back": False,
        })
    selected_ids = {text(row.get("mention_id")) for row in cases}
    result = {
        "schema": "sfh2-2p2-selection-v1",
        "pilot": "SFH2.2-P2",
        "model": "deepseek-v4-flash",
        "selection_seed": SELECTION_SEED,
        "case_count": len(cases),
        "blind_case_count": len(cases),
        "gold_case_count": 0,
        "cases": cases,
        "stratum_quotas": dict(STRATUM_QUOTAS),
        "stratum_counts": dict(sorted(Counter(text(row.get("case_family")) for row in cases).items())),
        "eligible_count": len(eligible),
        "excluded_count": len(all_mentions) - len(eligible),
        "exclusion_counts": dict(sorted(exclusion_counts.items())),
        "quota_shortfalls": dict(sorted(quota_shortfalls.items())),
        "prior_story_count": len(excluded_stories),
        "prior_story_ids": sorted(excluded_stories),
        "selection_basis": "fixed-seed deterministic stratified sampling from SFH1 validated mention metadata only; no identity answers inspected",
        "gold_fields_present": False,
        "candidate_only": True,
        "canonical_write_back": False,
    }
    result["selection_hash"] = stable_hash({key: value for key, value in result.items() if key != "selection_hash"})
    # Avoid retaining internal fields in any output; this also makes an
    # accidental answer-dependent selector obvious in review.
    if len(selected_ids) != len(cases):
        raise RuntimeError("sfh2_2p2_duplicate_selection")
    return result


def freeze_selection(path: Path | None = None) -> dict[str, Any]:
    path = path or SELECTION_PATH
    current = build_selection()
    if path.is_file():
        previous = read_json(path, {}) or {}
        if previous != current:
            raise RuntimeError("sfh2_2p2_selection_changed")
        return previous
    write_json(path, current)
    return current
