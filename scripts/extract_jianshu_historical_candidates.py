#!/usr/bin/env python3
"""Extract compact, attributed Jianshu candidate assertions and citations."""

from __future__ import annotations

from collections import Counter
import re
from pathlib import Path
import sys

from s1_jianshu_common import (
    CACHE_ROOT,
    GLYPH_AUDIT_PATH,
    ALIGNMENT_PATH,
    classify_attribution,
    hash_value,
    load_story_records,
    read_json,
    sha256_file,
    stable_id,
    write_json,
)


ROOT = Path(__file__).resolve().parents[1]
PEOPLE_PATH = Path("data/people.json")
ALIASES_PATH = Path("data/aliases.json")
ALIAS_OUTPUT = Path("data/derived/s1-jianshu-alias-candidates.json")
ASSERTION_OUTPUT = Path("data/derived/s1-jianshu-historical-assertions.json")
CITATION_OUTPUT = Path("data/derived/s1-jianshu-source-citations.json")

OFFICE_TERMS = ("太傅", "太尉", "丞相", "司徒", "司空", "尚書", "尚书", "刺史", "將軍", "将军", "令", "尹", "侍中", "參軍", "参军", "僕射", "仆射")
FAMILY_TERMS = ("父", "母", "兄", "弟", "姊", "妹", "子", "女", "妻", "夫", "娶", "婚", "外甥", "從兄", "从兄")
EVENT_TERMS = ("伐", "討", "讨", "敗", "败", "誅", "诛", "亂", "乱", "起兵", "篡", "卒", "薨", "崩")
LOCATION_TERMS = ("郡", "州", "縣", "县", "京", "江", "山", "城", "里", "居", "徙", "鎮", "镇")
SOURCE_NAMES = {
    "晉書": "晉書",
    "晋书": "晉書",
    "晉陽秋": "晉陽秋",
    "晋阳秋": "晉陽秋",
    "中興書": "中興書",
    "中兴书": "中興書",
    "世語": "世語",
    "世语": "世語",
    "後漢書": "後漢書",
    "后汉书": "後漢書",
    "漢書": "漢書",
    "汉书": "漢書",
    "三國志": "三國志",
    "三国志": "三國志",
    "人物別傳": "人物別傳",
    "人物别传": "人物別傳",
    "別傳": "別傳",
    "别传": "別傳",
    "家傳": "家傳",
    "家传": "家傳",
    "譜": "譜",
    "谱": "譜",
    "御覽": "太平御覽",
    "御览": "太平御覽",
    "太平御覽": "太平御覽",
    "太平御览": "太平御覽",
    "建康實錄": "建康實錄",
    "建康实录": "建康實錄",
    "晉紀": "晉紀",
    "晋纪": "晉紀",
}


def excerpt(text: str, limit: int = 360) -> str:
    return text if len(text) <= limit else text[: limit - 1] + "…"


def modality(text: str) -> str:
    if any(term in text for term in ("未詳", "未详", "未可知", "不可考", "不知", "未知")):
        return "unknown"
    if any(term in text for term in ("疑", "疑為", "疑为", "誤", "误", "不確", "不确")):
        return "disputed"
    if "或" in text:
        return "possible"
    if any(term in text for term in ("當作", "当作", "當為", "当为", "蓋", "盖", "宜")):
        return "probable"
    return "explicit"


def candidate_fact_types(text: str) -> list[str]:
    types: list[str] = []
    if any(term in text for term in ("字", "小字", "別名", "别名", "一名", "即", "當作", "当作")):
        types.append("identity")
    if any(term in text for term in OFFICE_TERMS):
        types.append("office")
    if any(term in text for term in FAMILY_TERMS):
        types.append("family")
    if any(term in text for term in EVENT_TERMS):
        types.append("event")
    if re.search(r"(?:漢|晋|晉|太|永|元|咸|建|隆|嘉|泰|義|义|興|兴)[和熙寧宁康安平始初嘉太元永咸建隆義义興兴][一二三四五六七八九十百零〇0-9]", text) or re.search(r"\d{3,4}年", text):
        types.append("temporal")
    if any(term in text for term in LOCATION_TERMS):
        types.append("geographic")
    if any(term in text for term in ("佐", "從", "从", "辟", "舉", "举", "攻", "拒", "附", "忠", "反")):
        types.append("service_political")
    return sorted(set(types)) or ["historical_context"]


def alias_candidates(stories: list[dict]) -> list[dict]:
    people = read_json(PEOPLE_PATH).get("people", [])
    people_by_id = {str(row.get("person_id")): row for row in people}
    alias_index: dict[str, list[dict]] = {}
    for alias in read_json(ALIASES_PATH).get("aliases", []):
        surface = alias.get("surface")
        if surface:
            alias_index.setdefault(str(surface), []).append(alias)

    def resolution(surface: str | None, canonical_candidate: str | None) -> dict:
        matches = alias_index.get(surface or "", []) if surface else []
        person_ids = sorted({str(person_id) for alias in matches for person_id in alias.get("person_ids", [])})
        resolved_ids = sorted({str(person_id) for alias in matches for person_id in alias.get("resolved_person_ids", [])})
        all_ids = sorted(set(person_ids) | set(resolved_ids))
        contradictory = any(
            set(alias.get("person_ids", [])) != set(alias.get("resolved_person_ids", []))
            and alias.get("resolved_person_ids")
            for alias in matches
        )
        exact_resolved = all(
            alias.get("resolution_mode") == "exact" and alias.get("status") == "resolved"
            for alias in matches
        )
        if contradictory:
            state = "conflict"
        elif len(all_ids) > 1 or (matches and not exact_resolved):
            state = "ambiguous"
        elif len(all_ids) == 1:
            state = "existing_mapping"
        else:
            state = "new_candidate"
        return {
            "resolution_state": state,
            "existing_alias_ids": sorted(str(alias.get("alias_id")) for alias in matches),
            "matched_person_ids": all_ids,
            "matched_canonical_names": sorted(
                str(people_by_id[person_id].get("canonical_name"))
                for person_id in all_ids
                if person_id in people_by_id
            ),
            "comparison_basis": "data/aliases.json surface mapping; canonical name retained as candidate context",
        }

    rows: list[dict] = []
    for story in stories:
        text = story["base_text"]
        for match in re.finditer(r"([\u3400-\u9fff]{1,8})(字|小字|別名|别名|一名)([\u3400-\u9fff]{1,4})", text):
            before = match.group(1)
            surface = match.group(3)
            record = {
                "candidate_id": stable_id("s1-alias", story["story_id"], "base", match.start(), before, surface),
                "surface": surface,
                "canonical_name_candidate": before,
                "alias_type": {"字": "字", "小字": "小字", "別名": "别称", "别名": "别称", "一名": "别称"}[match.group(2)],
                "story_id": story["story_id"],
                "source_layer": "base_text_embedded_annotation",
                "source_locator": story["source_locator"],
                "evidence_text": excerpt(match.group(0), 160),
                "attribution": None,
                "review_required": True,
            }
            record.update(resolution(surface, before))
            rows.append(record)
        for block in story["blocks"]:
            if block["block_type"] not in {"liu_annotation", "jianshu_note"}:
                continue
            text = block["text"]
            for match in re.finditer(r"([\u3400-\u9fff]{1,8})(字|小字|別名|别名|一名)([\u3400-\u9fff]{1,4})", text):
                record = {
                    "candidate_id": stable_id("s1-alias", story["story_id"], block["block_id"], match.start(), match.group(3)),
                    "surface": match.group(3),
                    "canonical_name_candidate": match.group(1),
                    "alias_type": {"字": "字", "小字": "小字", "別名": "别称", "别名": "别称", "一名": "别称"}[match.group(2)],
                    "story_id": story["story_id"],
                    "source_layer": block["block_type"],
                    "source_locator": block["source_locator"],
                    "evidence_text": excerpt(match.group(0), 160),
                    "attribution": block.get("attribution"),
                    "review_required": True,
                }
                record.update(resolution(match.group(3), match.group(1)))
                rows.append(record)
    appendix = read_json(Path(".cache/shishuo-reference/jianshu/alias-appendix.json"))
    for appendix_record in appendix.get("records", []):
        record = {
            "candidate_id": stable_id("s1-alias-appendix", appendix_record["appendix_id"]),
            "surface": None,
            "canonical_name_candidate": None,
            "alias_type": "appendix_available_as_toc_only",
            "story_id": None,
            "source_layer": "appendix",
            "source_locator": appendix_record["source_locator"],
            "evidence_text": appendix_record["heading"],
            "attribution": None,
            "review_required": True,
            "appendix_content_present": appendix_record.get("available_in_spine", False),
        }
        record.update(resolution(None, None))
        rows.append(record)
    return sorted({row["candidate_id"]: row for row in rows}.values(), key=lambda row: row["candidate_id"])


def extract_candidates(stories: list[dict]) -> tuple[list[dict], list[dict]]:
    assertions: list[dict] = []
    citations: list[dict] = []
    for story in stories:
        for block in story["blocks"]:
            if block["block_type"] not in {"liu_annotation", "jianshu_note", "collation_note"}:
                continue
            text = block["text"]
            types = candidate_fact_types(text)
            assertion = {
                "assertion_id": stable_id("s1-assertion", story["story_id"], block["block_id"]),
                "story_id": story["story_id"],
                "layer": block["block_type"],
                "attribution": block.get("attribution"),
                "attribution_explicit": block.get("attribution_explicit", False),
                "source_locator": block["source_locator"],
                "text": excerpt(text),
                "text_sha256": block["text_sha256"],
                "candidate_fact_types": types,
                "modality": modality(text),
                "candidate_status": "candidate",
                "canonicalization_status": "not_materialized",
                "extraction_quality": "structural_approximation" if block["block_type"] == "liu_annotation" else "block_exact",
            }
            assertions.append(assertion)
            seen_sources: set[str] = set()
            for surface, normalized in SOURCE_NAMES.items():
                for match in re.finditer(re.escape(surface), text):
                    key = (surface, match.start())
                    if str(key) in seen_sources:
                        continue
                    seen_sources.add(str(key))
                    left = max(0, match.start() - 80)
                    right = min(len(text), match.end() + 180)
                    citations.append(
                        {
                            "citation_id": stable_id("s1-citation", story["story_id"], block["block_id"], match.start(), surface),
                            "story_id": story["story_id"],
                            "layer": block["block_type"],
                            "attribution": block.get("attribution"),
                            "citation_surface": surface,
                            "normalized_source": normalized,
                            "quoted_passage": text[left:right],
                            "source_locator": block["source_locator"],
                            "assertion_id": assertion["assertion_id"],
                            "review_status": "candidate",
                        }
                    )
    assertions.sort(key=lambda row: row["assertion_id"])
    citations = sorted({row["citation_id"]: row for row in citations}.values(), key=lambda row: row["citation_id"])
    return assertions, citations


def build() -> dict:
    stories = load_story_records()
    aliases = alias_candidates(stories)
    assertions, citations = extract_candidates(stories)
    alignment = read_json(ALIGNMENT_PATH)
    source_hashes = {
        "epub": read_json(Path(".cache/shishuo-reference/jianshu/parse-metadata.json"))["epub_sha256"],
        "structure_audit": sha256_file(Path("data/derived/s1-jianshu-structure-audit.json")),
        "alignment": sha256_file(ALIGNMENT_PATH),
    }
    write_json(ALIAS_OUTPUT, {
        "schema": "s1-jianshu-alias-candidates-1",
        "stage": "S1.3",
        "source_hashes": source_hashes,
        "comparison_targets": [PEOPLE_PATH.as_posix(), ALIASES_PATH.as_posix()],
        "records": aliases,
        "counts": dict(sorted(Counter(row["resolution_state"] for row in aliases).items())),
        "policy": "Alias extraction never creates a Person or edits the global alias index automatically.",
    })
    write_json(ASSERTION_OUTPUT, {
        "schema": "s1-jianshu-historical-assertions-1",
        "stage": "S1.3",
        "source_hashes": source_hashes,
        "records": assertions,
        "counts": {
            "total": len(assertions),
            "by_layer": dict(sorted(Counter(row["layer"] for row in assertions).items())),
            "by_modality": dict(sorted(Counter(row["modality"] for row in assertions).items())),
            "by_fact_type": dict(sorted(Counter(kind for row in assertions for kind in row["candidate_fact_types"]).items())),
        },
        "policy": "All assertions are candidates; quoted source, scholarly commentary, and canonical facts remain distinct layers.",
    })
    write_json(CITATION_OUTPUT, {
        "schema": "s1-jianshu-source-citations-1",
        "stage": "S1.3",
        "source_hashes": source_hashes,
        "records": citations,
        "counts": {
            "total": len(citations),
            "by_source": dict(sorted(Counter(row["normalized_source"] for row in citations).items())),
        },
        "policy": "Citations form a future source-expansion map; S1 does not ingest the cited works.",
    })
    return {"aliases": len(aliases), "assertions": len(assertions), "citations": len(citations)}


def main() -> int:
    try:
        result = build()
    except Exception as exc:
        print(f"S1 Jianshu candidate extraction failed: {exc}", file=sys.stderr)
        return 2
    print(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
