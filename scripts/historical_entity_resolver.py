#!/usr/bin/env python3
"""Reusable, conservative historical-entity resolution primitives.

This module is intentionally independent of the HNG experiment runners.  It
does matching and validation only; it never writes to ``data/people.json`` or
to any canonical historical artifact.  Historical source text is kept in the
evidence records passed to the functions and is never normalised in place.

The resolver is deliberately fail-closed.  A graph neighbourhood can rank a
candidate, but it cannot create an identity without an independent textual or
structural signal.
"""

from __future__ import annotations

import collections
import copy
import hashlib
import json
import re
import unicodedata
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

import build_hng0_2 as hng02

ROOT = Path(__file__).resolve().parents[1]

RESOLVER_VERSION = "hng2-hybrid-historical-entity-resolver-v1"

# This is a matching fold, not a text conversion policy.  The table covers
# the common traditional/simplified and historical-glyph forms in the local
# person catalogue and source witnesses.  It is intentionally explicit so a
# clean checkout does not depend on OpenCC or another optional package.
TRADITIONAL_TO_SIMPLIFIED = str.maketrans({
    "濤": "涛", "濤": "涛", "温": "温", "溫": "温", "刘": "刘", "劉": "刘",
    "桓": "桓", "導": "导", "导": "导", "謝": "谢", "谢": "谢", "郗": "郗",
    "鑒": "鉴", "鉴": "鉴", "庾": "庾", "亮": "亮", "陶": "陶", "侃": "侃",
    "峻": "峻", "蘇": "苏", "苏": "苏", "王": "王", "敦": "敦", "凝": "凝",
    "之": "之", "羲": "羲", "璿": "璇", "璇": "璇", "嶠": "峤", "峤": "峤",
    "隗": "隗", "廙": "廙", "劉": "刘", "華": "华", "華": "华", "顗": "顗",
    "荀": "荀", "鍾": "钟", "鍾": "钟", "鍾": "钟", "嵇": "嵇", "康": "康",
    "紹": "绍", "绍": "绍", "預": "预", "預": "预", "卞": "卞", "壼": "壸",
    "壸": "壸", "鄧": "邓", "攸": "攸", "袁": "袁", "宏": "宏", "桓": "桓",
    "郗": "郗", "簡": "简", "簡": "简", "顒": "颙", "頠": "頠", "戎": "戎",
    "伶": "伶", "阮": "阮", "籍": "籍", "王": "王", "何": "何", "曾": "曾",
    "馬": "马", "邵": "邵", "傅": "傅", "玄": "玄", "安": "安",
    "將": "将", "軍": "军", "書": "书", "從": "从",
    "孫": "孙", "祖": "祖", "父": "父", "母": "母", "弟": "弟", "兄": "兄",
    "妻": "妻", "婿": "婿", "舅": "舅", "外": "外", "預": "预", "嶠": "峤",
    "顧": "顾", "顧": "顾", "謝": "谢", "裴": "裴", "歐": "欧", "陽": "阳",
    "馮": "冯", "張": "张", "趙": "赵", "陳": "陈", "陸": "陆", "許": "许",
    "蕭": "萧", "蕭": "萧", "鄭": "郑", "韓": "韩", "韓": "韩", "魏": "魏",
    "曹": "曹", "孫": "孙", "孫": "孙", "吳": "吴", "吴": "吴", "劉": "刘",
    "寳": "宝", "寶": "宝", "彞": "彝", "彛": "彝", "龕": "龛", "龕": "龛",
})

GENERIC_ROLE_SURFACES = {
    "父", "母", "父母", "子", "女", "兄", "弟", "姊", "妹", "叔", "舅", "妻", "婿",
    "外甥", "客", "帝", "太子", "皇太子", "公主", "師", "將軍", "太尉", "太傅", "丞相",
    "侍中", "尚書", "司徒", "刺史", "太守", "長史", "掾", "其妻", "長子", "嗣",
}

SURNAME_INHERITING_KINSHIP = (
    "從父兄", "從父弟", "兄子", "弟子", "從兄", "從弟", "叔父", "祖父", "祖", "孫", "父", "兄", "弟", "子",
)
NON_INHERITING_KINSHIP = (
    "外祖", "舅", "母", "妻父", "妻", "婿", "外甥", "母舅",
)

OFFICE_TITLES = (
    "太尉", "太傅", "太保", "丞相", "相國", "尚書令", "尚書", "中書令", "中書",
    "侍中", "僕射", "大將軍", "將軍", "刺史", "太守", "司徒", "司空", "校尉", "長史", "掾",
)
DECORATOR_TYPES = ("geographic", "office", "title", "nobility", "kinship-role", "other")

ERA_ORDER = {
    "漢": 0, "魏": 1, "蜀": 1, "吳": 1, "西晉": 2, "晉": 2, "東晉": 3,
    "宋": 4, "齊": 5, "梁": 6, "陳": 7, "隋": 8, "唐": 9,
}


def _text(value: Any) -> str:
    return str(value or "").strip()


def matching_normalize(value: Any) -> str:
    """Return a lookup form; never use this value as a source quotation."""

    text = unicodedata.normalize("NFKC", _text(value)).translate(TRADITIONAL_TO_SIMPLIFIED)
    # Matching forms ignore whitespace and common source layout marks only.
    return re.sub(r"[\s\u3000\u200b\ufeff]", "", text)


def stable_hash(value: Any) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def person_catalog() -> dict[str, dict[str, Any]]:
    """Use the established HNG catalogue schema as the single source."""

    return hng02.person_catalog()


def forms_index(catalog: Mapping[str, Mapping[str, Any]]) -> dict[str, list[str]]:
    """Build a systematic matching index over the established catalogue."""

    index: dict[str, set[str]] = collections.defaultdict(set)
    for pid, person in sorted(catalog.items()):
        values: set[str] = set()
        for key in ("forms", "canonical_forms", "courtesy_forms", "alias_forms", "office_titles"):
            raw = person.get(key, [])
            if isinstance(raw, str):
                raw = [raw]
            if isinstance(raw, Sequence):
                values.update(_text(item) for item in raw if _text(item))
        canonical = _text(person.get("canonical_name"))
        if canonical:
            values.add(canonical)
        for value in values:
            key = matching_normalize(value)
            if key:
                index[key].add(str(pid))
    return {key: sorted(values) for key, values in sorted(index.items())}


def catalog_forms(person: Mapping[str, Any]) -> list[str]:
    values: set[str] = set()
    for key in ("forms", "canonical_forms", "courtesy_forms", "alias_forms", "office_titles"):
        raw = person.get(key, [])
        if isinstance(raw, str):
            raw = [raw]
        if isinstance(raw, Sequence):
            values.update(_text(item) for item in raw if _text(item))
    if _text(person.get("canonical_name")):
        values.add(_text(person.get("canonical_name")))
    return sorted(values, key=lambda x: (-len(matching_normalize(x)), matching_normalize(x), x))


def _source_ref_from_evidence(ref: str, evidence: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    source = evidence.get(str(ref), {})
    return dict(source) if isinstance(source, Mapping) else {}


def build_contextual_identity_registry(
    *,
    catalog: Mapping[str, Mapping[str, Any]],
    accepted_only: bool = True,
) -> list[dict[str, Any]]:
    """Build a read-only registry from existing identity evidence.

    The registry intentionally does not turn candidate aliases into global
    aliases.  Accepted explicit identities from the project effective
    mention layer are retained with source/story conditions.  The local
    ``aliases.json`` catalogue contributes only rows marked resolved or
    context-dependent with a unique resolved person.
    """

    rows: list[dict[str, Any]] = []
    aliases_path = ROOT / "data/aliases.json"
    if aliases_path.is_file():
        doc = json.loads(aliases_path.read_text(encoding="utf-8"))
        for alias in doc.get("aliases", []):
            if not isinstance(alias, Mapping):
                continue
            pids = [str(x) for x in alias.get("resolved_person_ids", []) if str(x)]
            if len(pids) != 1:
                continue
            status = _text(alias.get("status"))
            mode = _text(alias.get("resolution_mode"))
            if accepted_only and status not in {"resolved", "context_dependent"}:
                continue
            surface = _text(alias.get("surface"))
            if not surface or matching_normalize(surface) in {matching_normalize(x) for x in GENERIC_ROLE_SURFACES}:
                continue
            if pids[0] not in catalog:
                continue
            evidence_rows = alias.get("source_evidence", []) if isinstance(alias.get("source_evidence"), list) else []
            for evidence_row in evidence_rows[:20]:
                if not isinstance(evidence_row, Mapping):
                    continue
                rows.append({
                    "surface": surface,
                    "person_id": pids[0],
                    "conditions": {
                        "source": evidence_row.get("source"),
                        "story_id": evidence_row.get("source_id"),
                        "section": evidence_row.get("section"),
                        "context": evidence_row.get("evidence_snippet"),
                    },
                    "source": "data/aliases.json",
                    "alias_type": alias.get("alias_type"),
                    "resolution_mode": mode,
                    "review_status": "reviewed_contextual_catalogue",
                    "evidence_refs": [evidence_row.get("mention_id")] if evidence_row.get("mention_id") else [],
                })

    effective_path = ROOT / "data/derived/person-resolution-effective.json"
    if effective_path.is_file():
        doc = json.loads(effective_path.read_text(encoding="utf-8"))
        for row in doc.get("derived_mentions", []):
            if not isinstance(row, Mapping):
                continue
            pid = _text((row.get("resolution_target") or {}).get("person_id") if isinstance(row.get("resolution_target"), Mapping) else "")
            if not pid or pid not in catalog or _text(row.get("resolution_status")) != "resolved":
                continue
            review_status = _text(row.get("resolution_review_status"))
            if accepted_only and review_status not in {"accepted", "reviewed"}:
                continue
            surface = _text(row.get("surface"))
            if not surface:
                continue
            rows.append({
                "surface": surface,
                "person_id": pid,
                "conditions": {
                    "source": row.get("source"),
                    "story_id": row.get("story_id") or row.get("entry_id"),
                    "section": row.get("section"),
                    "context": row.get("context"),
                },
                "source": "data/derived/person-resolution-effective.json",
                "alias_type": row.get("alias_type"),
                "resolution_mode": row.get("resolution_method"),
                "review_status": review_status,
                "evidence_refs": list((row.get("evidence") or {}).get("evidence_ids", [])) if isinstance(row.get("evidence"), Mapping) else [],
            })
    unique: dict[tuple[str, str, str, str], dict[str, Any]] = {}
    for row in rows:
        key = (matching_normalize(row["surface"]), str(row["person_id"]), str(row["conditions"].get("story_id") or ""), str(row["conditions"].get("source") or ""))
        unique[key] = row
    return [unique[key] for key in sorted(unique)]


def is_generic_role(surface: str) -> bool:
    return matching_normalize(surface) in {matching_normalize(x) for x in GENERIC_ROLE_SURFACES}


def parse_kinship_surface(surface: str, *, seed_surname: str = "") -> dict[str, Any]:
    """Parse a kinship-bearing abbreviated surface without inventing a name."""

    raw = _text(surface)
    normalized = matching_normalize(raw)
    if not normalized:
        return {"is_kinship": False, "surface": raw, "malformed_person_surface": False}
    for marker in sorted(NON_INHERITING_KINSHIP, key=len, reverse=True):
        if marker in raw or matching_normalize(marker) in normalized:
            return {
                "is_kinship": True,
                "kinship_marker": marker,
                "surname_inheriting": False,
                "candidate_surface": raw.replace(marker, "", 1).strip("（）() "),
                "family_surname": None,
                "malformed_person_surface": False,
            }
    for marker in sorted(SURNAME_INHERITING_KINSHIP, key=len, reverse=True):
        if marker in raw or matching_normalize(marker) in normalized:
            remainder = raw.replace(marker, "", 1).strip("（）() ")
            # A chain such as 喜弟預女 is structural, not one person's name.
            if len(matching_normalize(remainder)) >= 2 and any(x in remainder for x in ("弟", "兄", "女", "子")):
                return {
                    "is_kinship": True,
                    "kinship_marker": marker,
                    "surname_inheriting": True,
                    "candidate_surface": remainder,
                    "family_surname": seed_surname or None,
                    "relation_chain": [
                        {"relation": "sibling_or_kinship", "surface": remainder[:1]},
                        {"relation": "descendant_or_affinal", "surface": remainder[1:]},
                    ],
                    "malformed_person_surface": True,
                }
            return {
                "is_kinship": True,
                "kinship_marker": marker,
                "surname_inheriting": True,
                "candidate_surface": remainder,
                "family_surname": seed_surname or None,
                "malformed_person_surface": False,
            }
    return {"is_kinship": False, "surface": raw, "malformed_person_surface": False}


def parse_structural_kinship_context(text: str, *, seed_surname: str = "") -> dict[str, Any] | None:
    """Find the local family expression around an abbreviated name."""

    raw = _text(text)
    patterns = [
        r"(從父兄|從父弟|兄子|從兄|從弟|叔父|祖父|父|兄|弟|子)([\u4e00-\u9fff]{1,2})",
        r"(外祖|舅|妻父|婿|外甥)([\u4e00-\u9fff]{1,2})",
    ]
    for pattern in patterns:
        match = re.search(pattern, raw)
        if match:
            return parse_kinship_surface(match.group(0), seed_surname=seed_surname)
    return None


def _decorated_candidate(surface: str, catalog: Mapping[str, Mapping[str, Any]], index: Mapping[str, Sequence[str]], context: str) -> dict[str, Any] | None:
    raw = _text(surface)
    folded = matching_normalize(raw)
    if len(folded) < 2:
        return None
    candidates: list[dict[str, Any]] = []
    for pid, person in sorted(catalog.items()):
        for form in catalog_forms(person):
            form_folded = matching_normalize(form)
            if len(form_folded) < 2 or not folded.endswith(form_folded) or folded == form_folded:
                continue
            prefix = folded[: -len(form_folded)]
            if len(prefix) < 1:
                continue
            # Only use unique suffixes.  A one-character suffix is too noisy
            # unless it is a known courtesy/full form of the Person.
            if len(form_folded) < 2:
                continue
            candidates.append({"person_id": pid, "form": form, "prefix": prefix})
    by_pid: dict[str, dict[str, Any]] = {}
    for row in candidates:
        by_pid.setdefault(str(row["person_id"]), row)
    if len(by_pid) != 1:
        return None
    row = next(iter(by_pid.values()))
    prefix = str(row["prefix"])
    prefix_raw = raw[: len(raw) - len(str(row["form"]))] if len(raw) >= len(str(row["form"])) else prefix
    office = any(matching_normalize(title) in prefix for title in OFFICE_TITLES)
    geographic = any(prefix.endswith(matching_normalize(mark)) or matching_normalize(mark) in prefix for mark in ("國", "郡", "州", "縣", "鄉", "邑", "里"))
    title = any(x in prefix for x in ("王", "公", "侯", "君", "夫人"))
    decorator_type = "office" if office else "geographic" if geographic else "title" if title else "other"
    if decorator_type == "other" and not any(prefix in matching_normalize(str(v)) for v in (context,)):
        return None
    return {
        "person_id": str(row["person_id"]),
        "normalized_person_surface": str(row["form"]),
        "decorator_surface": prefix_raw,
        "decorator_type": decorator_type,
        "confidence": "medium" if decorator_type != "other" else "low",
    }


def _title_candidate(surface: str, catalog: Mapping[str, Mapping[str, Any]], context: str) -> list[str]:
    raw = _text(surface)
    folded = matching_normalize(raw)
    hits: list[str] = []
    for pid, person in sorted(catalog.items()):
        canonical = matching_normalize(person.get("canonical_name"))
        surname = matching_normalize(str(person.get("surname") or ""))
        if not surname or not folded.startswith(surname):
            continue
        rest = folded[len(surname):]
        if rest and any(matching_normalize(title) == rest for title in OFFICE_TITLES):
            if canonical in matching_normalize(context) or surname in matching_normalize(context):
                hits.append(str(pid))
    return sorted(set(hits))


def temporal_gate(seed: Mapping[str, Any], evidence: Mapping[str, Any] | None = None, *, text: str = "") -> dict[str, Any]:
    """Check obvious era incompatibility without manufacturing chronology."""

    source = dict(evidence or {})
    passage = " ".join(filter(None, [_text(source.get("original_text")), _text(source.get("model_snippet")), text]))
    seed_text = " ".join(filter(None, [_text(seed.get("canonical_name")), _text(seed.get("dynasty")), _text(seed.get("era")), _text(seed.get("temporal_context"))]))
    normalized = matching_normalize(passage)
    seed_norm = matching_normalize(seed_text)
    # The explicit Liang reign-period guard is intentionally conservative: it
    # catches the known cross-era 虞預 collision while leaving unknown dates
    # alone.
    liang_marker = any(marker in normalized for marker in ("梁太清", "太清三年", "太清"))
    jin_marker = any(marker in seed_norm for marker in ("西晉", "東晉", "晉"))
    source_locator = source.get("locator") if isinstance(source.get("locator"), Mapping) else {}
    source_title = matching_normalize(" ".join(_text(source_locator.get(k)) for k in ("title", "unit_title", "page_title", "section")))
    if liang_marker and jin_marker:
        return {
            "status": "conflict",
            "reason": "source contains 梁/太清 era material but seed chronology is Jin-era",
            "constraints": ["梁太清", "晉-era seed"],
            "source_ref": source.get("evidence_ref") or source.get("source_ref"),
        }
    if source_title and any(x in source_title for x in ("梁", "太清")) and jin_marker:
        return {
            "status": "conflict",
            "reason": "source unit is Liang-era while seed is Jin-era",
            "constraints": [source_title, "晉-era seed"],
            "source_ref": source.get("evidence_ref") or source.get("source_ref"),
        }
    # If the evidence and seed explicitly share a dynasty marker, this is a
    # positive but weak compatibility signal; absent markers remain unknown.
    if any(marker in normalized and marker in seed_norm for marker in ("西晉", "東晉", "晉", "魏", "吳", "蜀")):
        return {"status": "compatible", "reason": "explicit era marker is compatible", "constraints": [], "source_ref": source.get("evidence_ref") or source.get("source_ref")}
    return {"status": "unknown", "reason": "no deterministic chronology conflict established", "constraints": [], "source_ref": source.get("evidence_ref") or source.get("source_ref")}


def _candidate_context_signals(candidate: str, person: Mapping[str, Any], *, context: str, seed_id: str, neighborhoods: Mapping[str, set[str]], pid: str) -> list[str]:
    signals: list[str] = []
    folded_context = matching_normalize(context)
    forms = {matching_normalize(x) for x in catalog_forms(person)}
    if matching_normalize(candidate) in forms:
        signals.append("exact_or_catalogue_form")
    if matching_normalize(person.get("canonical_name")) in folded_context:
        signals.append("explicit_full_name_elsewhere")
    if pid in neighborhoods.get(seed_id, set()):
        signals.append("independent_hng_neighborhood")
    return signals


def graph_support(
    *,
    seed_id: str,
    candidate_id: str,
    edges: Sequence[Mapping[str, Any]],
    current_evidence_refs: Sequence[str] = (),
    current_candidate_id: str | None = None,
    current_claim: str = "",
) -> dict[str, Any]:
    """Return independent graph support and explicitly excluded circular edges."""

    current_refs = {str(x) for x in current_evidence_refs}
    support: list[dict[str, Any]] = []
    excluded: list[dict[str, Any]] = []
    for edge in edges:
        a, b = str(edge.get("person_a") or ""), str(edge.get("person_b") or "")
        if candidate_id not in {a, b} or seed_id not in {a, b}:
            continue
        edge_refs = {str(x) for x in edge.get("evidence_refs", [])}
        circular = (
            current_candidate_id and str(edge.get("relation_id") or edge.get("source_record_id") or "") == str(current_candidate_id)
        ) or bool(current_refs & edge_refs) or (current_claim and _text(edge.get("claim")) == _text(current_claim))
        item = {
            "relation_id": edge.get("relation_id") or edge.get("source_record_id"),
            "person_a": a,
            "person_b": b,
            "relation_type": edge.get("relation_type") or edge.get("normalized_relation_type"),
            "review_status": edge.get("review_status"),
            "evidence_refs": sorted(edge_refs),
        }
        if circular:
            excluded.append({**item, "reason": "circular_same_candidate_or_evidence"})
        else:
            support.append(item)
    return {
        "graph_support_edges": sorted(support, key=lambda x: str(x.get("relation_id"))),
        "independent_graph_support_count": len(support),
        "excluded_circular_edges": sorted(excluded, key=lambda x: str(x.get("relation_id"))),
    }


def resolve_identity(
    *,
    surface: str,
    seed: Mapping[str, Any],
    context: str,
    evidence: Mapping[str, Mapping[str, Any]] | None,
    catalog: Mapping[str, Mapping[str, Any]],
    index: Mapping[str, Sequence[str]],
    contextual_registry: Sequence[Mapping[str, Any]] = (),
    neighborhoods: Mapping[str, set[str]] | None = None,
    graph_edges: Sequence[Mapping[str, Any]] = (),
    evidence_refs: Sequence[str] = (),
    candidate_id: str | None = None,
    temporal: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Resolve one surface using the frozen hybrid decision policy."""

    raw = _text(surface)
    seed_id = _text(seed.get("person_id"))
    neighborhoods = neighborhoods or {}
    if not raw or is_generic_role(raw):
        return {
            "surface": raw, "resolution_status": "unresolved", "decision_level": "UNRESOLVED",
            "resolution_method": "unresolved", "confidence": "low", "candidate_set": [],
            "context_signals": [], "temporal_status": (temporal or {}).get("status", "unknown"),
            "note": "generic role surface is not an independently identified person",
        }
    folded = matching_normalize(raw)
    direct_kin = parse_kinship_surface(raw, seed_surname=_text(seed.get("surname")))
    if direct_kin.get("malformed_person_surface"):
        return {
            "surface": raw, "resolution_status": "unresolved", "decision_level": "UNRESOLVED",
            "resolution_method": "kinship_context", "confidence": "low", "candidate_set": [],
            "context_signals": ["malformed_kinship_chain"], "kinship_parse": direct_kin,
            "temporal_status": (temporal or {}).get("status", "unknown"),
            "note": "structural kinship chain is not one person",
        }
    # Exact/catalogue form first.  A unique reviewed form is AUTO_HIGH.
    exact = sorted(set(str(x) for x in index.get(folded, [])))
    if len(exact) == 1:
        pid = exact[0]
        method = "exact_name"
        person = catalog[pid]
        if folded in {matching_normalize(x) for x in person.get("courtesy_forms", [])}:
            method = "courtesy_name"
        elif folded in {matching_normalize(x) for x in person.get("alias_forms", [])}:
            method = "alias"
        elif folded in {matching_normalize(x) for x in person.get("office_titles", [])}:
            method = "title"
        return {
            "surface": raw, "normalized_person_surface": person.get("canonical_name"), "resolved_person_id": pid,
            "resolved_label": person.get("canonical_name"), "resolution_status": "resolved_existing_person",
            "decision_level": "AUTO_HIGH", "resolution_method": method, "confidence": "high",
            "candidate_set": exact, "context_signals": _candidate_context_signals(raw, person, context=context, seed_id=seed_id, neighborhoods=neighborhoods, pid=pid),
            "temporal_status": (temporal or {}).get("status", "unknown"), "graph_support": graph_support(seed_id=seed_id, candidate_id=pid, edges=graph_edges, current_evidence_refs=evidence_refs, current_candidate_id=candidate_id),
        }
    if len(exact) > 1:
        # A direct full name in the local unit can resolve a shared form; no
        # graph-only tie breaking is allowed.
        local = [pid for pid in exact if matching_normalize(catalog[pid].get("canonical_name")) in matching_normalize(context)]
        if len(local) == 1:
            pid = local[0]
            return {
                "surface": raw, "normalized_person_surface": catalog[pid].get("canonical_name"), "resolved_person_id": pid,
                "resolved_label": catalog[pid].get("canonical_name"), "resolution_status": "resolved_existing_person",
                "decision_level": "AUTO_SUPPORTED", "resolution_method": "biography_local_context", "confidence": "high",
                "candidate_set": exact, "context_signals": ["explicit_full_name_elsewhere"], "temporal_status": (temporal or {}).get("status", "unknown"),
                "graph_support": graph_support(seed_id=seed_id, candidate_id=pid, edges=graph_edges, current_evidence_refs=evidence_refs, current_candidate_id=candidate_id),
            }
        return {
            "surface": raw, "resolution_status": "ambiguous", "decision_level": "AMBIGUOUS", "resolution_method": "ambiguous",
            "confidence": "low", "candidate_set": exact, "context_signals": [], "temporal_status": (temporal or {}).get("status", "unknown"),
        }

    # Existing reviewed contextual identity decisions are conditional and are
    # consulted before generic title parsing.
    contextual_matches = []
    for row in contextual_registry:
        if matching_normalize(row.get("surface")) != folded:
            continue
        cond = row.get("conditions") if isinstance(row.get("conditions"), Mapping) else {}
        story_id = _text(cond.get("story_id"))
        if story_id and story_id not in matching_normalize(context) and story_id not in _text(context):
            # Context may be a source passage without an explicit story id;
            # keep the row only when its evidence context is present.
            if _text(cond.get("context")) and matching_normalize(cond.get("context")) not in matching_normalize(context):
                continue
        contextual_matches.append(row)
    pids = sorted(set(str(row.get("person_id")) for row in contextual_matches if row.get("person_id")))
    if len(pids) == 1:
        pid = pids[0]
        return {
            "surface": raw, "normalized_person_surface": catalog[pid].get("canonical_name"), "resolved_person_id": pid,
            "resolved_label": catalog[pid].get("canonical_name"), "resolution_status": "resolved_existing_person",
            "decision_level": "AUTO_SUPPORTED", "resolution_method": "reviewed_contextual_alias", "confidence": "high",
            "candidate_set": pids, "context_signals": ["reviewed_contextual_identity"], "contextual_registry_rows": contextual_matches,
            "temporal_status": (temporal or {}).get("status", "unknown"),
        }

    decorated = _decorated_candidate(raw, catalog, index, context)
    if decorated:
        pid = decorated["person_id"]
        return {
            "surface": raw, "normalized_person_surface": decorated["normalized_person_surface"], "decorator_surface": decorated["decorator_surface"],
            "decorator_type": decorated["decorator_type"], "resolved_person_id": pid, "resolved_label": catalog[pid].get("canonical_name"),
            "resolution_status": "resolved_existing_person", "decision_level": "AUTO_SUPPORTED", "resolution_method": "decorated_name_suffix",
            "confidence": decorated["confidence"], "candidate_set": [pid], "context_signals": ["unique_decorated_suffix"],
            "temporal_status": (temporal or {}).get("status", "unknown"),
        }
    title_pids = _title_candidate(raw, catalog, context)
    if len(title_pids) == 1:
        pid = title_pids[0]
        return {
            "surface": raw, "normalized_person_surface": catalog[pid].get("canonical_name"), "resolved_person_id": pid,
            "resolved_label": catalog[pid].get("canonical_name"), "resolution_status": "resolved_existing_person",
            "decision_level": "AUTO_SUPPORTED", "resolution_method": "title", "confidence": "medium",
            "candidate_set": title_pids, "context_signals": ["surname_plus_office_title"], "temporal_status": (temporal or {}).get("status", "unknown"),
        }

    seed_surname = _text(seed.get("surname"))
    kin = parse_structural_kinship_context(context, seed_surname=seed_surname)
    if kin and kin.get("malformed_person_surface"):
        return {
            "surface": raw, "resolution_status": "unresolved", "decision_level": "UNRESOLVED", "resolution_method": "kinship_context",
            "confidence": "low", "candidate_set": [], "context_signals": ["malformed_kinship_chain"], "kinship_parse": kin,
            "temporal_status": (temporal or {}).get("status", "unknown"), "note": "structural kinship chain is not one person",
        }
    if kin and not kin.get("surname_inheriting"):
        # Maternal and affinal expressions do not license a seed-surname
        # concatenation and must not fall through to generic suffix matching.
        return {
            "surface": raw, "resolved_label": raw,
            "provisional_person_id": f"hng2-provisional-{stable_hash({'surface': raw, 'kinship': kin.get('kinship_marker')})[:20]}",
            "resolution_status": "provisional", "decision_level": "PROVISIONAL", "resolution_method": "kinship_context",
            "confidence": "low", "candidate_set": [], "context_signals": ["non_surname_inheriting_kinship"], "kinship_parse": kin,
            "temporal_status": (temporal or {}).get("status", "unknown"),
        }
    if kin and kin.get("surname_inheriting") and kin.get("candidate_surface"):
        candidate_surface = f"{seed_surname}{kin['candidate_surface']}" if seed_surname else str(kin["candidate_surface"])
        candidate_pids = sorted(set(index.get(matching_normalize(candidate_surface), [])))
        if len(candidate_pids) == 1:
            pid = candidate_pids[0]
            return {
                "surface": raw, "normalized_person_surface": candidate_surface, "resolved_person_id": pid,
                "resolved_label": catalog[pid].get("canonical_name"), "resolution_status": "resolved_existing_person",
                "decision_level": "AUTO_SUPPORTED", "resolution_method": "kinship_context", "confidence": "medium",
                "candidate_set": candidate_pids, "context_signals": ["surname_inheriting_kinship"], "kinship_parse": kin,
                "temporal_status": (temporal or {}).get("status", "unknown"),
            }
        if len(candidate_pids) > 1:
            return {
                "surface": raw, "resolution_status": "ambiguous", "decision_level": "AMBIGUOUS", "resolution_method": "kinship_context",
                "confidence": "low", "candidate_set": candidate_pids, "context_signals": ["surname_inheriting_kinship"], "kinship_parse": kin,
                "temporal_status": (temporal or {}).get("status", "unknown"),
            }
        return {
            "surface": raw, "normalized_person_surface": candidate_surface, "resolved_label": candidate_surface,
            "provisional_person_id": f"hng2-provisional-{stable_hash({'surface': candidate_surface})[:20]}",
            "resolution_status": "provisional", "decision_level": "PROVISIONAL", "resolution_method": "kinship_context",
            "confidence": "medium", "candidate_set": [], "context_signals": ["surname_inheriting_kinship"], "kinship_parse": kin,
            "temporal_status": (temporal or {}).get("status", "unknown"),
        }

    # Abbreviated suffix resolution is allowed only when one candidate has
    # compatible independent textual context; graph support ranks but never
    # supplies the sole reason.
    suffix_candidates: list[str] = []
    for pid, person in sorted(catalog.items()):
        if len(folded) < 2:
            continue
        if any(len(matching_normalize(form)) > len(folded) and matching_normalize(form).endswith(folded) for form in catalog_forms(person)):
            suffix_candidates.append(pid)
    if suffix_candidates:
        scored: list[tuple[int, str, list[str]]] = []
        for pid in sorted(set(suffix_candidates)):
            signals = _candidate_context_signals(raw, catalog[pid], context=context, seed_id=seed_id, neighborhoods=neighborhoods, pid=pid)
            independent = graph_support(seed_id=seed_id, candidate_id=pid, edges=graph_edges, current_evidence_refs=evidence_refs, current_candidate_id=candidate_id)
            textual = any(x in signals for x in ("explicit_full_name_elsewhere", "exact_or_catalogue_form"))
            score = len(signals) + (1 if textual else 0)
            scored.append((score, pid, signals + (["independent_graph_support"] if independent["independent_graph_support_count"] else [])))
        scored.sort(reverse=True)
        if scored and (len(scored) == 1 or scored[0][0] > scored[1][0]) and scored[0][0] >= 2:
            _, pid, signals = scored[0]
            return {
                "surface": raw, "normalized_person_surface": catalog[pid].get("canonical_name"), "resolved_person_id": pid,
                "resolved_label": catalog[pid].get("canonical_name"), "resolution_status": "resolved_existing_person",
                "decision_level": "AUTO_SUPPORTED", "resolution_method": "contextual_short_name", "confidence": "medium",
                "candidate_set": sorted(set(suffix_candidates)), "context_signals": signals,
                "graph_support": graph_support(seed_id=seed_id, candidate_id=pid, edges=graph_edges, current_evidence_refs=evidence_refs, current_candidate_id=candidate_id),
                "temporal_status": (temporal or {}).get("status", "unknown"),
            }
        return {
            "surface": raw, "resolution_status": "ambiguous", "decision_level": "AMBIGUOUS", "resolution_method": "ambiguous",
            "confidence": "low", "candidate_set": sorted(set(suffix_candidates)), "context_signals": [],
            "temporal_status": (temporal or {}).get("status", "unknown"),
        }
    if len(folded) >= 2:
        return {
            "surface": raw, "resolved_label": raw, "provisional_person_id": f"hng2-provisional-{stable_hash({'surface': raw})[:20]}",
            "resolution_status": "provisional", "decision_level": "PROVISIONAL", "resolution_method": "source_local_context",
            "confidence": "medium", "candidate_set": [], "context_signals": ["explicit_named_surface"],
            "temporal_status": (temporal or {}).get("status", "unknown"),
        }
    return {
        "surface": raw, "resolution_status": "unresolved", "decision_level": "UNRESOLVED", "resolution_method": "unresolved",
        "confidence": "low", "candidate_set": [], "context_signals": [], "temporal_status": (temporal or {}).get("status", "unknown"),
    }


def frontier_state(identity: Mapping[str, Any], *, evidence_traceable: bool, no_temporal_conflict: bool, hard_relation_count: int = 0, interaction_count: int = 0, direct_source_hit: bool = False, researched: bool = False) -> str:
    """Return an explicit HNG frontier state without creating Persons."""

    status = _text(identity.get("resolution_status"))
    label = _text(identity.get("resolved_label") or identity.get("surface"))
    if researched:
        return "researched_frontier"
    if status == "ambiguous":
        return "blocked_frontier"
    kin = identity.get("kinship_parse") if isinstance(identity.get("kinship_parse"), Mapping) else {}
    if kin.get("malformed_person_surface"):
        return "blocked_frontier"
    if not evidence_traceable or not no_temporal_conflict or not label or is_generic_role(label):
        return "blocked_frontier" if status not in {"provisional", "resolved_provisional_person"} else "weak_provisional"
    if status == "resolved_existing_person" or hard_relation_count >= 1 or interaction_count >= 2 or direct_source_hit:
        return "eligible_frontier"
    if status in {"provisional", "resolved_provisional_person"}:
        return "candidate_frontier"
    return "weak_provisional"


def validate_llm_identity_output(row: Mapping[str, Any], catalog: Mapping[str, Mapping[str, Any]], candidates: Sequence[str]) -> tuple[bool, str]:
    """Validate constrained identity-assist output without semantic repair."""

    if _text(row.get("entity_type")) not in {"person", "unknown", "role"}:
        return False, "invalid_entity_type"
    choice = _text(row.get("candidate_key"))
    if choice and choice not in {str(x) for x in candidates}:
        return False, "model_invented_candidate_key"
    if not _text(row.get("evidence_span")):
        return False, "missing_evidence_span"
    confidence = _text(row.get("confidence"))
    if confidence not in {"high", "medium", "low", "unknown"}:
        return False, "invalid_confidence"
    return True, "valid"


__all__ = [
    "RESOLVER_VERSION", "TRADITIONAL_TO_SIMPLIFIED", "matching_normalize", "stable_hash",
    "person_catalog", "forms_index", "catalog_forms", "build_contextual_identity_registry",
    "parse_kinship_surface", "parse_structural_kinship_context", "temporal_gate", "graph_support",
    "resolve_identity", "frontier_state", "is_generic_role", "validate_llm_identity_output",
]
