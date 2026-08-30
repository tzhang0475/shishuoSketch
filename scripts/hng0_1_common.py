#!/usr/bin/env python3
"""Shared, local-only primitives for HNG0.1.

HNG0.1 deliberately keeps the source-driven growth layer separate from HNG0.
The functions in this module build a deterministic source inventory, perform
lexical FIND/OPEN retrieval, and project only evidence-validated model claims.
They never write canonical Persons, Relations, Events, or Facts.
"""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[1]
HNG0_ROOT = ROOT / "data/generated/hng0"
OUTPUT_ROOT = ROOT / "data/generated/hng0-1"
SELECTION_PATH = HNG0_ROOT / "hng0-selection.json"
HNG0_CANDIDATE_PATH = HNG0_ROOT / "hng0-candidates.json"
PEOPLE_PATH = ROOT / "data/people.json"
ALIASES_PATH = ROOT / "data/aliases.json"
CORPUS_INDEX_PATH = ROOT / "data/shishuo-corpus-index.json"
JINSHU_INDEX_PATH = ROOT / "data/jinshu-unit-index.json"
JIANSU_BUNDLE_PATH = ROOT / "data/derived/x1-2r-jianshu-evidence-bundles.json"

MODEL = "deepseek-v4-flash"
PROVIDER = "deepseek"
PROMPT_VERSION = "hng0-1-source-driven-extraction-v2"
SCHEMA_VERSION = 1

REVIEW_STATUSES = {"candidate", "accepted", "rejected", "uncertain", "needs_more_evidence"}
ALLOWED_RELATION_TYPES = {
    "parent_child",
    "sibling",
    "uncle_nephew",
    "cousin_clan_kin",
    "marriage",
    "affinal_relation",
    "same_clan",
    "superior_subordinate",
    "recruitment_served_under",
    "teacher_student",
    "explicit_friendship_association",
    "explicit_political_cooperation_opposition",
    "shared_explicit_event",
}
ALLOWED_TEMPORAL_TYPES = {
    "birth",
    "death",
    "office_tenure",
    "residence_activity_phase",
    "major_event_participation",
}
RELATION_TERMS = (
    "父", "母", "子", "女", "兄", "弟", "兄子", "從兄", "從弟", "叔", "舅",
    "婿", "妻", "尚主", "友善", "與", "善", "游", "從游", "辟", "引", "為", "佐",
    "掾", "黨", "謀", "攻", "討", "不協", "薦", "任", "拜", "事", "師",
)
TRADITIONAL_FOLD = str.maketrans({
    "長": "长", "從": "从", "陽": "阳", "晉": "晋", "與": "与", "為": "为",
    "縣": "县", "書": "书", "國": "国", "門": "门", "會": "会", "東": "东",
    "學": "学", "時": "时", "後": "后", "傳": "传", "親": "亲", "屬": "属",
    "據": "据", "應": "应", "開": "开", "見": "见", "於": "于", "無": "无",
    "舊": "旧", "華": "华", "賢": "贤", "劉": "刘", "謝": "谢", "嶠": "峤",
    "溫": "温", "導": "导", "侃": "侃", "國": "国", "陸": "陆", "機": "机",
    "庾": "庾", "陶": "陶", "王": "王", "桓": "桓", "顧": "顾",
})


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def stable_hash(value: Any) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def compact(value: Any) -> str:
    return " ".join(str(value or "").split())


def search_normalize(value: Any) -> str:
    """Search convenience form; never use this to rewrite evidence quotes."""

    text = unicodedata.normalize("NFKC", str(value or "")).translate(TRADITIONAL_FOLD)
    return "".join(text.split())


def original_normalize(value: Any) -> str:
    return unicodedata.normalize("NFKC", compact(value))


def unique_strings(values: Iterable[Any]) -> list[str]:
    return sorted({compact(item) for item in values if compact(item)})


def parse_frontmatter_text(path: Path, marker: str = "## Original source (exact)") -> str:
    text = path.read_text(encoding="utf-8")
    if marker in text:
        value = text.split(marker, 1)[1]
        value = value.split("\n---", 1)[0]
        value = value.split("\n## ", 1)[0]
        return value.strip()
    return text


def _pair_surface(value: Any) -> list[str]:
    if isinstance(value, Mapping):
        values = [value.get("original"), value.get("simplified")]
        return unique_strings(values)
    return [compact(value)] if compact(value) else []


def _alias_surface(row: Mapping[str, Any]) -> list[str]:
    values: list[str] = []
    values.extend(_pair_surface(row.get("surface")))
    values.extend(_pair_surface(row.get("name")))
    return unique_strings(values)


def build_people_catalog(
    root: Path = ROOT,
    aliases_document: Mapping[str, Any] | None = None,
) -> dict[str, dict[str, Any]]:
    people_doc = read_json(root / PEOPLE_PATH.relative_to(root))
    aliases_doc = aliases_document if isinstance(aliases_document, Mapping) else read_json(root / ALIASES_PATH.relative_to(root))
    people = {str(row["person_id"]): row for row in people_doc.get("people", []) if isinstance(row, Mapping) and row.get("person_id")}
    aliases_by_person: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for row in aliases_doc.get("aliases", []):
        if not isinstance(row, Mapping):
            continue
        for pid in row.get("person_ids", []) if isinstance(row.get("person_ids"), list) else []:
            aliases_by_person[str(pid)].append(row)
    catalog: dict[str, dict[str, Any]] = {}
    for pid, person in sorted(people.items()):
        values = person.get("canonical_name") or person.get("name") or ""
        courtesy = person.get("courtesy_name") or person.get("zi") or ""
        aliases = list(person.get("aliases", [])) if isinstance(person.get("aliases"), list) else []
        surfaces: list[str] = [str(values), *(_pair_surface(courtesy))]
        office_titles: list[str] = []
        clan = ""
        if isinstance(person.get("clan"), Mapping):
            clan = compact(person["clan"].get("canonical_name") or person["clan"].get("name"))
        for row in aliases + aliases_by_person.get(pid, []):
            surfaces.extend(_alias_surface(row))
            alias_type = str(row.get("alias_type") or "")
            if "office" in alias_type or "title" in alias_type:
                office_titles.extend(_alias_surface(row))
        surfaces.extend([clan])
        catalog[pid] = {
            "person_id": pid,
            "canonical_name": compact(person.get("canonical_name") or person.get("name")),
            "courtesy_name": unique_strings(_pair_surface(courtesy)),
            "aliases": unique_strings(surfaces),
            "office_titles": unique_strings(office_titles),
            "clan": clan or None,
            "native_place": compact(person.get("native_place")) or None,
            "review_status": person.get("review_status"),
        }
    return catalog


def build_search_profiles(
    root: Path = ROOT,
    aliases_document: Mapping[str, Any] | None = None,
) -> dict[str, dict[str, Any]]:
    """Build the frozen 24-seed search profiles, without existing relations."""

    catalog = build_people_catalog(root, aliases_document)
    selection = read_json(root / SELECTION_PATH.relative_to(root))
    hng_candidates = read_json(root / HNG0_CANDIDATE_PATH.relative_to(root))
    hng_people = hng_candidates.get("people", {})
    seeds = [str(row["person_id"]) for row in selection.get("people", []) if row.get("person_id")]
    profiles: dict[str, dict[str, Any]] = {}
    for pid in seeds:
        base = dict(catalog.get(pid, {"person_id": pid, "canonical_name": pid}))
        old = hng_people.get(pid, {}) if isinstance(hng_people, Mapping) else {}
        person = old.get("person", {}) if isinstance(old, Mapping) else {}
        if isinstance(person, Mapping):
            base["courtesy_name"] = unique_strings([*base.get("courtesy_name", []), *(_pair_surface(person.get("courtesy_name")))])
            base["aliases"] = unique_strings([*base.get("aliases", []), *(
                surface for alias in person.get("aliases", []) if isinstance(alias, Mapping)
                for surface in _pair_surface(alias.get("surface"))
            )])
            base["office_titles"] = unique_strings([*base.get("office_titles", []), *(
                surface for alias in person.get("title_office_appellations", []) if isinstance(alias, Mapping)
                for surface in _pair_surface(alias)
            )])
            if not base.get("clan") and isinstance(person.get("clan"), Mapping):
                base["clan"] = compact(person["clan"].get("name")) or None
        stories = old.get("stories", []) if isinstance(old, Mapping) else []
        known_relatives: list[str] = []
        for relation in old.get("relations", []) if isinstance(old, Mapping) else []:
            if not isinstance(relation, Mapping) or relation.get("relation_type") not in {"parent_child", "sibling", "uncle_nephew", "cousin_clan_kin", "marriage", "affinal_relation", "same_clan"}:
                continue
            other_id = relation.get("person_b") if relation.get("person_a") == pid else relation.get("person_a")
            other = catalog.get(str(other_id), {})
            if other.get("canonical_name"):
                known_relatives.append(str(other["canonical_name"]))
        story_appellations = unique_strings(
            story.get("short_excerpt", "")[:80]
            for story in stories
            if isinstance(story, Mapping) and story.get("short_excerpt")
        )
        temporal = old.get("temporal_spine", []) if isinstance(old, Mapping) else []
        terms = unique_strings([
            base.get("canonical_name"),
            *base.get("courtesy_name", []),
            *base.get("aliases", []),
            *base.get("office_titles", []),
            base.get("clan"),
            base.get("native_place"),
            *known_relatives,
        ])
        terms = [term for term in terms if len(search_normalize(term)) >= 2]
        profiles[pid] = {
            **base,
            "known_relatives": unique_strings(known_relatives),
            "story_appellations": story_appellations,
            "temporal_spine": temporal,
            "search_terms_original": terms,
            "search_terms_normalized": unique_strings(search_normalize(term) for term in terms),
            "seed": True,
            "one_hop_only": True,
        }
    return profiles


def _source_unit(
    *,
    source_ref: str,
    work: str,
    source_layer: str,
    text: str,
    source_path: str,
    locator: Mapping[str, Any],
    source_sha256: str | None = None,
    metadata: Mapping[str, Any] | None = None,
) -> dict[str, Any] | None:
    text = str(text or "")
    if not text.strip():
        return None
    row: dict[str, Any] = {
        "source_ref": source_ref,
        "work": work,
        "source_layer": source_layer,
        "text": text,
        "normalized_search_text": search_normalize(text),
        "source_path": source_path,
        "source_sha256": source_sha256,
        "locator": dict(locator),
    }
    if metadata:
        row.update(dict(metadata))
    return row


def _load_jinshu_units(root: Path) -> list[dict[str, Any]]:
    index = read_json(root / JINSHU_INDEX_PATH.relative_to(root))
    rows: list[dict[str, Any]] = []
    for item in index.get("units", []):
        if not isinstance(item, Mapping) or not item.get("unit_id") or item.get("category") == "editorial":
            continue
        rel = str(item.get("file_path") or "")
        path = root / rel
        if not path.is_file():
            continue
        text = parse_frontmatter_text(path)
        row = _source_unit(
            source_ref=f"hng01-jinshu-{item['unit_id']}",
            work="晉書",
            source_layer="primary_text",
            text=text,
            source_path=rel,
            source_sha256=str(item.get("unit_text_sha256") or sha256_file(path)),
            locator={"unit_id": item["unit_id"], "volume": item.get("volume"), "title": item.get("title"), "category": item.get("category")},
            metadata={"unit_kind": item.get("unit_kind"), "source_witness": item.get("source_witness")},
        )
        if row:
            rows.append(row)
    return rows


def _load_shishuo_units(root: Path) -> list[dict[str, Any]]:
    index = read_json(root / CORPUS_INDEX_PATH.relative_to(root))
    rows: list[dict[str, Any]] = []
    for item in sorted(index.get("entries", []), key=lambda x: str(x.get("id"))):
        if not isinstance(item, Mapping) or not item.get("id"):
            continue
        story_id = str(item["id"])
        rel = str(item.get("path") or "")
        path = root / rel
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8")
        original = text.split("## Original source (exact)", 1)[1].split("## Main text", 1)[0].strip() if "## Original source (exact)" in text else ""
        main = text.split("## Main text", 1)[1].split("## Top-level parenthetical annotation blocks", 1)[0].strip() if "## Main text" in text else ""
        main_row = _source_unit(
            source_ref=f"hng01-shishuo-{story_id}-main",
            work="世說新語",
            source_layer="main_text",
            text=main or original,
            source_path=rel,
            source_sha256=str(item.get("entry_sha256") or sha256_file(path)),
            locator={"story_id": story_id, "chapter_id": item.get("chapter_id"), "entry_number": item.get("ordinal")},
            metadata={"story_id": story_id, "canonical_source": True},
        )
        if main_row:
            rows.append(main_row)
        if "## Top-level parenthetical annotation blocks" not in text:
            continue
        section = text.split("## Top-level parenthetical annotation blocks", 1)[1]
        matches = list(re.finditer(r"^### (annotation-[^\n]+)\n.*?\n\n(.*?)(?=\n\n### |\Z)", section, re.MULTILINE | re.DOTALL))
        for match in matches:
            aid, annotation = match.group(1).strip(), match.group(2).strip()
            row = _source_unit(
                source_ref=f"hng01-shishuo-{story_id}-{aid}",
                work="世說新語",
                source_layer="liu_annotation",
                text=annotation,
                source_path=rel,
                source_sha256=str(item.get("entry_sha256") or sha256_file(path)),
                locator={"story_id": story_id, "annotation_id": aid, "chapter_id": item.get("chapter_id")},
                metadata={"story_id": story_id, "canonical_source": True},
            )
            if row:
                rows.append(row)
    return rows


def _load_jianshu_units(root: Path) -> list[dict[str, Any]]:
    if not (root / JIANSU_BUNDLE_PATH.relative_to(root)).is_file():
        return []
    doc = read_json(root / JIANSU_BUNDLE_PATH.relative_to(root))
    rows: list[dict[str, Any]] = []
    for record in doc.get("records", []):
        if not isinstance(record, Mapping):
            continue
        story_id = str((record.get("canonical_source") or {}).get("story_id") or "")
        for layer in ("collation_note", "jianshu_note", "other_scholar_note"):
            for block in (record.get("blocks") or {}).get(layer, []):
                if not isinstance(block, Mapping) or not block.get("text"):
                    continue
                bid = str(block.get("block_id") or stable_hash(block)[:20])
                row = _source_unit(
                    source_ref=f"hng01-jianshu-{story_id}-{bid}",
                    work="余嘉錫笺疏",
                    source_layer=str(block.get("layer") or layer),
                    text=str(block["text"]),
                    source_path="data/derived/x1-2r-jianshu-evidence-bundles.json",
                    source_sha256=str(block.get("text_sha256") or ""),
                    locator={"story_id": story_id, "block_id": bid, "block_type": block.get("block_type")},
                    metadata={"story_id": story_id, "speaker": block.get("attribution"), "source_labels": block.get("source_labels", [])},
                )
                if row:
                    rows.append(row)
    return rows


def _load_sgz_units(root: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for path in sorted((root / "content/processed/sanguozhi/sgz1").glob("volume-*.md")):
        text = path.read_text(encoding="utf-8")
        front = text.split("---", 2)[1] if text.startswith("---") else ""
        volume = re.search(r"global_juan:\s*(\d+)", front)
        volume_no = int(volume.group(1)) if volume else None
        source_hash = (re.search(r"source_sha256:\s*([^\n]+)", front) or [None, None])[1]
        pattern = re.compile(r"^## (main_text|pei_annotation) · ([^\n]+)\n\n(.*?)(?=\n\n## |\Z)", re.MULTILINE | re.DOTALL)
        for index, match in enumerate(pattern.finditer(text), 1):
            layer, heading, body = match.groups()
            row = _source_unit(
                source_ref=f"hng01-sgz-{volume_no:03d}-{index:06d}",
                work="三國志",
                source_layer=layer,
                text=body.strip(),
                source_path=str(path.relative_to(root)),
                source_sha256=str(source_hash or sha256_file(path)).strip('"'),
                locator={"global_juan": volume_no, "heading": heading, "segment": index},
                metadata={"section": "魏書" if volume_no and volume_no <= 30 else "蜀書" if volume_no and volume_no <= 45 else "吳書", "source_witness": "sanguozhi-wikisource"},
            )
            if row:
                rows.append(row)
    return rows


def _load_ztj_units(root: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    base = root / "content/processed/zizhi-tongjian/volumes"
    for path in sorted(base.glob("volume-*.json")):
        doc = read_json(path)
        for index, block in enumerate(doc.get("chronicle_blocks", []), 1):
            if not isinstance(block, Mapping):
                continue
            main = str(block.get("main_text") or "")
            row = _source_unit(
                source_ref=f"hng01-ztj-{doc.get('juan_number') or path.stem}-{index:04d}-main",
                work="資治通鑑",
                source_layer="main_text",
                text=main,
                source_path=str(path.relative_to(root)),
                source_sha256=str(doc.get("source_sha256") or sha256_file(path)),
                locator={"volume": doc.get("juan_number"), "block_id": block.get("block_id"), "chronicle_name": block.get("chronicle_name")},
                metadata={"source_witness": doc.get("source_witness")},
            )
            if row:
                rows.append(row)
            for aindex, annotation in enumerate(block.get("annotations", []), 1):
                if not isinstance(annotation, Mapping):
                    continue
                ann_text = str(annotation.get("text") or annotation.get("original_text") or "")
                ann = _source_unit(
                    source_ref=f"hng01-ztj-{doc.get('juan_number') or path.stem}-{index:04d}-hu-{aindex:04d}",
                    work="資治通鑑",
                    source_layer="hu_annotation",
                    text=ann_text,
                    source_path=str(path.relative_to(root)),
                    source_sha256=str(doc.get("source_sha256") or sha256_file(path)),
                    locator={"volume": doc.get("juan_number"), "block_id": block.get("block_id"), "annotation": aindex},
                    metadata={"source_witness": doc.get("source_witness")},
                )
                if ann:
                    rows.append(ann)
    return rows


def build_source_units(root: Path = ROOT) -> list[dict[str, Any]]:
    """Build only from registered/processed source directories, never generated output."""

    units: list[dict[str, Any]] = []
    for loader in (_load_jinshu_units, _load_shishuo_units, _load_jianshu_units, _load_sgz_units, _load_ztj_units):
        units.extend(loader(root))
    units.sort(key=lambda row: str(row["source_ref"]))
    return units


def route_sources(profile: Mapping[str, Any], units: Sequence[Mapping[str, Any]]) -> list[dict[str, str]]:
    """Return deterministic source routing reasons, not a semantic answer."""

    has_jinshu = any(u.get("work") == "晉書" and any(t in search_normalize(u.get("text")) for t in profile.get("search_terms_normalized", [])) for u in units)
    has_sgz = any(u.get("work") == "三國志" and any(t in search_normalize(u.get("text")) for t in profile.get("search_terms_normalized", [])) for u in units)
    routes = [
        {"work": "晉書", "reason": "人物的本地晋书单位优先用于传记/任官检索。"},
        {"work": "世說新語", "reason": "人物的刘注和其他世说故事用于语境与关系线索。"},
        {"work": "余嘉錫笺疏", "reason": "已登记的同故事笺疏用于后出考辨线索。"},
        {"work": "資治通鑑", "reason": "通鉴及胡注用于事件/时序兼容性检索。"},
        {"work": "三國志", "reason": "三国志仅作为有本地命中或三国时期线索时的补充来源。"},
    ]
    if has_sgz:
        routes[-1]["reason"] = "本地三国志存在人物名/别名命中，提前保留为相关史源。"
    if not has_jinshu:
        routes[0]["reason"] = "晋书未发现直接检索命中，仍保留为首选传记路由并记录空命中。"
    return routes


def _term_hits(text: str, terms: Sequence[str]) -> list[str]:
    folded = search_normalize(text)
    return sorted({term for term in terms if term and term in folded}, key=lambda x: (-len(x), x))


def _fold_with_offsets(text: str) -> tuple[str, list[int]]:
    """Fold search text while retaining raw-character offsets for OPEN."""

    folded_chars: list[str] = []
    offsets: list[int] = []
    for raw_index, char in enumerate(str(text or "")):
        normalized = unicodedata.normalize("NFKC", char).translate(TRADITIONAL_FOLD)
        for folded_char in normalized:
            if folded_char.isspace():
                continue
            folded_chars.append(folded_char)
            offsets.append(raw_index)
    return "".join(folded_chars), offsets


def find_passages(profile: Mapping[str, Any], units: Sequence[Mapping[str, Any]], *, top_k: int = 24) -> dict[str, Any]:
    """FIND: broad deterministic lexical ranking; no source text is sent yet."""

    terms = [search_normalize(x) for x in profile.get("search_terms_original", []) if len(search_normalize(x)) >= 2]
    canonical = search_normalize(profile.get("canonical_name"))
    routes = route_sources(profile, units)
    priority = {row["work"]: index for index, row in enumerate(routes)}
    scored: list[dict[str, Any]] = []
    for unit in units:
        text = str(unit.get("text") or "")
        hits = _term_hits(text, terms)
        if not hits:
            continue
        relation_hits = [term for term in RELATION_TERMS if term in text]
        canonical_hit = bool(canonical and canonical in search_normalize(text))
        unit_score = len(hits) * 5 + len(relation_hits) * 2 + priority.get(str(unit.get("work")), 9) * -1
        if canonical_hit:
            unit_score += 40
        if unit.get("work") == "晉書" and unit.get("unit_kind") == "biography" and canonical_hit:
            unit_score += 24
        # This is only a ranking signal.  It never creates a relation.
        co_mentions = []
        for other in terms:
            if other in hits:
                continue
            if other in search_normalize(text):
                co_mentions.append(other)
        unit_score += min(len(co_mentions), 3) * 4
        scored.append({
            "source_ref": unit["source_ref"],
            "score": unit_score,
            "matched_terms": hits,
            "relation_term_hits": relation_hits,
            "co_mention_terms": sorted(co_mentions),
            "work": unit.get("work"),
            "source_layer": unit.get("source_layer"),
            "locator": unit.get("locator", {}),
            "unit_kind": unit.get("unit_kind"),
            "category": unit.get("locator", {}).get("category") if isinstance(unit.get("locator"), Mapping) else None,
        })
    scored.sort(key=lambda row: (-int(row["score"]), priority.get(str(row.get("work")), 9), str(row["source_ref"])))
    return {
        "profile_person_id": profile.get("person_id"),
        "routes": routes,
        "query_terms": profile.get("search_terms_original", []),
        "raw_match_count": len(scored),
        "hits": scored[: max(1, min(int(top_k), 100))],
    }


def open_passages(find_result: Mapping[str, Any], units_by_ref: Mapping[str, Mapping[str, Any]], *, max_passages: int = 8, window_chars: int = 1400) -> list[dict[str, Any]]:
    """OPEN: use source offsets around lexical hits, never sentence segmentation."""

    opened: list[dict[str, Any]] = []
    for hit in list(find_result.get("hits", []))[: max(1, min(max_passages, 8))]:
        ref = str(hit.get("source_ref") or "")
        unit = units_by_ref.get(ref)
        if not unit:
            continue
        text = str(unit.get("text") or "")
        folded, folded_offsets = _fold_with_offsets(text)
        offsets: list[int] = []
        for term in hit.get("matched_terms", []):
            index = folded.find(search_normalize(term))
            if index >= 0:
                offsets.append(folded_offsets[index])
        center = min(offsets) if offsets else 0
        start = max(0, center - window_chars // 2)
        end = min(len(text), start + window_chars)
        snippet = text[start:end]
        opened.append({
            "source_ref": ref,
            "work": unit.get("work"),
            "source_layer": unit.get("source_layer"),
            "locator": unit.get("locator", {}),
            "snippet": snippet,
            "original_text": text,
            "window_start": start,
            "window_end": end,
            "source_path": unit.get("source_path"),
            "source_sha256": unit.get("source_sha256"),
            "score": hit.get("score", 0),
            "matched_terms": hit.get("matched_terms", []),
        })
    return opened


def quote_matches(source: str, quote: str) -> bool:
    """Exact quote check with only whitespace and boundary punctuation tolerance."""

    source = str(source or "")
    quote = str(quote or "").strip()
    if not quote:
        return False
    if quote in source:
        return True
    def fold(value: str) -> str:
        return re.sub(r"\s+", "", value)
    if fold(quote) in fold(source):
        return True
    boundary = "「」『』“”\"'，。；：、？！,.;:!?()（）[]【】"
    trimmed = quote.strip(boundary).strip()
    return bool(trimmed and fold(trimmed) in fold(source))


def resolve_counterpart(surface: str, catalog: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    folded = search_normalize(surface)
    matches: list[str] = []
    for pid, person in sorted(catalog.items()):
        forms = [person.get("canonical_name"), *person.get("courtesy_name", []), *person.get("aliases", []), *person.get("office_titles", [])]
        if folded and any(folded == search_normalize(form) for form in forms if form):
            matches.append(pid)
    if len(matches) == 1:
        pid = matches[0]
        return {"resolution_status": "resolved_existing_person", "person_id": pid, "canonical_name": catalog[pid].get("canonical_name"), "matches": matches}
    if len(matches) > 1:
        return {"resolution_status": "ambiguous_identity", "person_id": None, "canonical_name": None, "matches": matches}
    return {"resolution_status": "unresolved_identity", "person_id": None, "canonical_name": None, "matches": []}


def temporal_warnings(candidate: Mapping[str, Any], temporal_by_person: Mapping[str, Sequence[Mapping[str, Any]]]) -> list[str]:
    warnings: list[str] = []
    scope = candidate.get("temporal_scope") if isinstance(candidate.get("temporal_scope"), Mapping) else {}
    start = scope.get("start_year")
    end = scope.get("end_year")
    try:
        cstart, cend = int(start) if start is not None else None, int(end) if end is not None else None
    except (TypeError, ValueError):
        cstart = cend = None
    pid = str(candidate.get("person_id") or candidate.get("seed_person_id") or "")
    if cstart is None and cend is None:
        return warnings
    for item in temporal_by_person.get(pid, []):
        istart, iend = item.get("start_year"), item.get("end_year")
        try:
            if istart is not None and iend is not None:
                istart, iend = int(istart), int(iend)
        except (TypeError, ValueError):
            continue
        if iend is not None and cstart is not None and iend < cstart:
            warnings.append("temporal_conflict: candidate starts after an existing end")
        if cend is not None and istart is not None and cend < istart:
            warnings.append("temporal_conflict: candidate ends before an existing start")
    return sorted(set(warnings))


def source_priority(work: str) -> int:
    return {"晉書": 1, "世說新語": 2, "余嘉錫笺疏": 3, "資治通鑑": 4, "三國志": 5}.get(work, 9)
