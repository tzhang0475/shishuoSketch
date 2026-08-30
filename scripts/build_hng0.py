#!/usr/bin/env python3
"""Build the HNG0 one-hop historical navigation graph pilot.

HNG0 is deliberately a candidate/review projection.  It reads existing
canonical and derived records, but never writes back to the Person, relation,
fact, event, or Story registries.  The browser bundle contains the same
candidate rows plus a local review overlay so that review can happen without
turning a candidate into a canonical fact.
"""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable, Mapping


ROOT = Path(__file__).resolve().parents[1]
PEOPLE_PATH = ROOT / "data/people.json"
ALIASES_PATH = ROOT / "data/aliases.json"
SC1_PATH = ROOT / "data/derived/sc1-site.json"
PERSON_STORY_PATH = ROOT / "data/derived/person-story-links.json"
CORPUS_INDEX_PATH = ROOT / "data/shishuo-corpus-index.json"
RELATION_CANDIDATE_PATH = ROOT / "data/derived/person-relation-candidates-r3.json"
H0B1_BACKBONE_PATH = ROOT / "data/derived/h0b1-social-backbone.json"
H0C_FACTS_PATH = ROOT / "data/derived/h0c-historical-facts.json"
H0C_OFFICES_PATH = ROOT / "data/derived/h0c-offices.json"
H0C_LOCATIONS_PATH = ROOT / "data/derived/h0c-locations.json"
H0C_LOCATION_FACTS_PATH = ROOT / "data/derived/h0c-location-facts.json"
H0C_EVENTS_PATH = ROOT / "data/derived/h0c-events.json"
H0C_PARTICIPATION_PATH = ROOT / "data/derived/h0c-event-participations.json"
H0C_ACTIVITIES_PATH = ROOT / "data/derived/h0c-person-activities.json"
TEMPORAL_ANCHORS_PATH = ROOT / "data/annotation/story-temporal-anchors-h0a.json"
WP1_EVIDENCE_PATH = ROOT / "data/evidence/wp1-evidence.json"
DS2_PERSON_SURFACE_PATH = ROOT / "data/derived/ds2-1a-person-research-surface.json"

OUTPUT_ROOT = ROOT / "data/generated/hng0"
SELECTION_PATH = OUTPUT_ROOT / "hng0-selection.json"
CANDIDATE_PATH = OUTPUT_ROOT / "hng0-candidates.json"
PROJECTION_PATH = OUTPUT_ROOT / "hng0-reviewed-projection.json"
NEIGHBORHOOD_PATH = OUTPUT_ROOT / "hng0-neighborhoods.json"
RETRIEVAL_TRACE_PATH = OUTPUT_ROOT / "hng0-retrieval-trace.json"
METRICS_PATH = OUTPUT_ROOT / "hng0-metrics.json"
MANIFEST_PATH = OUTPUT_ROOT / "hng0-manifest.json"
REVIEW_PATH = ROOT / "data/annotation/hng0-review.json"
FRONTEND_PATH = ROOT / "site/src/generated/hng0-site.json"


def _frozen_alias_document(root: Path) -> dict[str, Any] | None:
    """Read the pre-SFH2R alias witness for this frozen HNG0 projection."""
    try:
        import sfh2r_contract
        document = sfh2r_contract.pre_repair_alias_document()
    except (ImportError, OSError, ValueError, TypeError):
        document = None
    return document if isinstance(document, Mapping) else None


def _alias_source_hash(root: Path) -> str:
    try:
        import sfh2r_contract
        value = sfh2r_contract.pre_repair_alias_file_hash()
    except (ImportError, OSError, ValueError, TypeError):
        value = None
    return value or sha256_file(root / ALIASES_PATH.relative_to(root))

REVIEW_STATUSES = {"candidate", "accepted", "rejected", "uncertain", "needs_more_evidence"}
TIME_PRECISIONS = {"exact", "circa", "before", "after", "between", "reign_period", "unknown"}
RELATION_TYPES = {
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


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def stable_hash(value: Any) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def compact(value: Any) -> str:
    return " ".join(str(value or "").split())


def norm(value: Any) -> str:
    return unicodedata.normalize("NFKC", compact(value))


def pair(value: Any) -> dict[str, str] | None:
    if value is None or compact(value) == "":
        return None
    text = str(value)
    # This is intentionally a small deterministic display fold.  It is not a
    # source-text rewrite and never changes the original evidence quotation.
    simplified = text.translate(str.maketrans({
        "長": "长", "從": "从", "陽": "阳", "晉": "晋", "與": "与",
        "為": "为", "縣": "县", "書": "书", "國": "国", "門": "门",
        "會": "会", "東": "东", "學": "学", "時": "时", "後": "后",
        "傳": "传", "親": "亲", "屬": "属", "據": "据", "應": "应",
        "開": "开", "見": "见", "於": "于", "無": "无", "舊": "旧",
        "華": "华", "賢": "贤", "劉": "刘", "謝": "谢", "嶠": "峤",
        "溫": "温", "侃": "侃", "導": "导", "庾": "庾", "國": "国",
    }))
    return {"original": text, "simplified": simplified}


def unique_strings(values: Iterable[Any]) -> list[str]:
    return sorted({compact(value) for value in values if compact(value)})


def source_work(source_id: Any, path: Any = None) -> str:
    text = f"{source_id or ''} {path or ''}".lower()
    if str(source_id) == "source-002":
        return "晉書"
    if str(source_id) == "source-001":
        return "世說新語"
    if "jinshu" in text or "晉書" in text:
        return "晉書"
    if "sanguozhi" in text or "三國志" in text:
        return "三國志"
    if "tongjian" in text or "zztj" in text or "資治" in text:
        return "資治通鑑"
    if "shishuo" in text or "世說" in text:
        return "世說新語"
    return "既有项目记录"


def review_status(value: Any, default: str = "candidate") -> str:
    value = str(value or "")
    if value == "reviewed":
        return "accepted"
    return value if value in REVIEW_STATUSES else default


def certainty(value: Any) -> str:
    value = str(value or "unknown")
    return value if value in {"attested", "reported", "inferred", "unknown"} else "unknown"


def precision(value: Any, start: Any = None, end: Any = None) -> str:
    raw = str(value or "").lower()
    if start is not None and end is not None:
        try:
            start_i, end_i = int(start), int(end)
            if start_i == end_i:
                return "exact"
            if raw in {"reign_bounded", "reign_period", "reign"}:
                return "reign_period"
            return "between"
        except (TypeError, ValueError):
            pass
    if raw in {"exact", "year", "year_exact"}:
        return "exact"
    if raw in {"circa", "approximate", "approx"}:
        return "circa"
    if raw in {"before", "before_only"}:
        return "before"
    if raw in {"after", "after_only"}:
        return "after"
    if raw in {"reign_bounded", "reign_period", "reign"}:
        return "reign_period"
    if raw in {"year_range", "event_bounded", "between"}:
        return "between" if start is not None or end is not None else "unknown"
    return "unknown"


def parse_entry(root: Path, row: Mapping[str, Any]) -> dict[str, Any]:
    path = root / str(row["path"])
    text = path.read_text(encoding="utf-8")
    original_marker = "## Original source (exact)"
    main_marker = "## Main text"
    annotation_marker = "## Top-level parenthetical annotation blocks"
    original = ""
    if original_marker in text:
        original = text.split(original_marker, 1)[1].split(main_marker, 1)[0].strip()
    main_text = ""
    if main_marker in text:
        main_text = text.split(main_marker, 1)[1].split(annotation_marker, 1)[0].strip()
    annotations: list[dict[str, Any]] = []
    if annotation_marker in text:
        section = text.split(annotation_marker, 1)[1]
        matches = list(re.finditer(r"^### (annotation-[^\n]+)\n.*?\n\n(.*?)(?=\n\n### |\Z)", section, re.MULTILINE | re.DOTALL))
        for match in matches:
            annotations.append({"annotation_id": match.group(1).strip(), "text": match.group(2).strip()})
    return {
        "story_id": row["id"],
        "chapter_id": str(row["id"]).rsplit("-", 1)[0],
        "chapter_heading": "",
        "ordinal": row.get("ordinal"),
        "global_ordinal": row.get("global_ordinal"),
        "path": str(row["path"]),
        "source_sha256": row.get("entry_sha256"),
        "original_text": original,
        "main_text": main_text,
        "liu_annotations": annotations,
    }


def collect_source_context(root: Path, paths: Iterable[Path], wanted: set[str]) -> dict[str, list[dict[str, Any]]]:
    """Find provenance-bearing source records for derived evidence IDs.

    The H0C files sometimes point at a source evidence ID without embedding a
    duplicate quotation.  Those references remain useful and are represented
    as a derived-record reference; this function does not invent a quote.
    """
    found: dict[str, list[dict[str, Any]]] = defaultdict(list)

    def visit(value: Any, file_path: Path, parent: Mapping[str, Any] | None = None) -> None:
        if isinstance(value, Mapping):
            refs: list[str] = []
            for key in ("evidence_ids", "source_evidence_ids", "supporting_evidence_ids"):
                raw = value.get(key)
                if isinstance(raw, list):
                    refs.extend(str(item) for item in raw if item)
            for raw in value.get("source_refs", []) if isinstance(value.get("source_refs"), list) else []:
                if isinstance(raw, Mapping) and raw.get("evidence_id"):
                    refs.append(str(raw["evidence_id"]))
            record_id = next((value.get(key) for key in ("id", "fact_id", "record_id", "anchor_id", "activity_id", "tenure_id", "event_id", "relation_id") if value.get(key)), None)
            source_path = value.get("source_path") or value.get("artifact_path")
            quote = value.get("quote") or value.get("quoted_source") or value.get("evidence_excerpt")
            for ref in refs:
                if ref in wanted:
                    item = {
                        "source_file": str(file_path.relative_to(root)),
                        "source_record_id": str(record_id) if record_id else None,
                        "source_path": str(source_path) if source_path else None,
                        "quote": str(quote) if quote else None,
                        "source_layer": value.get("source_layer") or value.get("evidence_type") or "derived_record",
                        "work": source_work(value.get("source_id"), source_path or file_path),
                    }
                    if item not in found[ref]:
                        found[ref].append(item)
            for child in value.values():
                visit(child, file_path, value)
        elif isinstance(value, list):
            for child in value:
                visit(child, file_path, parent)

    for path in sorted(set(paths)):
        if path.is_file():
            try:
                visit(read_json(path), path)
            except (OSError, json.JSONDecodeError):
                continue
    return found


def build_evidence_registry(root: Path, wanted: set[str], sc1: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    registry: dict[str, dict[str, Any]] = {}
    source_display = {str(row.get("id")): row for row in sc1.get("sources", []) if isinstance(row, Mapping)}
    pools: list[Mapping[str, Any]] = []
    pools.extend(row for row in sc1.get("evidence", []) if isinstance(row, Mapping))
    wp1 = read_json(root / WP1_EVIDENCE_PATH.relative_to(root))
    pools.extend(row for row in wp1.get("records", []) if isinstance(row, Mapping))
    for item in pools:
        ref = str(item.get("id") or "")
        if not ref or ref not in wanted:
            continue
        locator = item.get("locator") if isinstance(item.get("locator"), Mapping) else {}
        provenance = locator.get("source_provenance") if isinstance(locator.get("source_provenance"), Mapping) else {}
        source = source_display.get(str(item.get("source_id")), {})
        source_work_name = source.get("work") if isinstance(source.get("work"), str) else source_work(item.get("source_id"))
        registry[ref] = {
            "evidence_ref": ref,
            "source_work": source_work_name,
            "source_layer": item.get("evidence_type") or "historical_evidence",
            "original_text": item.get("quote") or None,
            "normalized_search_text": norm(item.get("quote")),
            "locator": locator,
            "source_path": locator.get("artifact_path") or provenance.get("source_path"),
            "source_sha256": locator.get("artifact_sha256") or provenance.get("source_sha256"),
            "assertion_status": item.get("assertion_status") or "unknown",
            "source_review_status": item.get("review_status") or "unknown",
            "provenance_kind": "source_text" if item.get("quote") else "source_record_reference",
        }
    input_paths = [
        root / relative for relative in [
            "data/derived/h0b1-social-backbone.json", "data/derived/h0c-historical-facts.json",
            "data/derived/h0c-offices.json", "data/derived/h0c-locations.json",
            "data/derived/h0c-location-facts.json", "data/derived/h0c-events.json",
            "data/derived/h0c-event-participations.json", "data/derived/h0c-person-activities.json",
            "data/annotation/story-temporal-anchors-h0a.json", "data/evidence/wp1-evidence.json",
            "data/derived/sc1-site.json", "data/derived/person-story-links.json",
        ]
    ]
    contexts = collect_source_context(root, input_paths, wanted)
    for ref in sorted(wanted):
        if ref in registry:
            continue
        context = contexts.get(ref, [])
        best = sorted(context, key=lambda row: (not bool(row.get("quote")), row.get("source_file", ""), row.get("source_record_id") or ""))[0] if context else {}
        registry[ref] = {
            "evidence_ref": ref,
            "source_work": best.get("work") or "既有项目记录",
            "source_layer": best.get("source_layer") or "derived_record",
            "original_text": best.get("quote") or None,
            "normalized_search_text": norm(best.get("quote")),
            "locator": {"source_file": best.get("source_file"), "source_record_id": best.get("source_record_id")},
            "source_path": best.get("source_path") or best.get("source_file"),
            "source_sha256": None,
            "assertion_status": "unknown",
            "source_review_status": "unknown",
            "provenance_kind": "source_record_reference" if context else "unresolved_reference",
        }
    return {key: registry[key] for key in sorted(registry)}


def relation_type(raw_type: Any, subtype: Any = None, proposed: Any = None) -> str | None:
    value = str(subtype or proposed or raw_type or "").lower()
    if value in {"parent_child", "parent-child"} or "parent" in value:
        return "parent_child"
    if value == "sibling" or "sibling" in value:
        return "sibling"
    if "uncle" in value or "niece" in value or "nephew" in value:
        return "uncle_nephew"
    if "collateral" in value or "cousin" in value or "kin" in value or value == "kinship":
        return "cousin_clan_kin"
    if value in {"spouse", "marriage"} or "marriage" in value:
        return "marriage"
    if "affinal" in value:
        return "affinal_relation"
    if "friend" in value or "social" in value:
        return "explicit_friendship_association"
    if "service" in value or "institutional" in value or "served" in value or "appointment" in value:
        return "recruitment_served_under"
    if "teacher" in value or "student" in value:
        return "teacher_student"
    if "politic" in value or "opposition" in value or "cooperation" in value:
        return "explicit_political_cooperation_opposition"
    if "event" in value:
        return "shared_explicit_event"
    return None


def relation_direction(kind: str, person_a: str, person_b: str) -> dict[str, str]:
    directed = kind in {"parent_child", "uncle_nephew", "recruitment_served_under", "teacher_student", "superior_subordinate"}
    return {"kind": "directed" if directed else "undirected", "from": person_a, "to": person_b}


def make_relation(
    row: Mapping[str, Any],
    person_a: str,
    person_b: str,
    kind: str,
    method: str,
    status: str,
    evidence_ids: Iterable[Any],
    source_review_status: Any,
    source_story_ids: Iterable[Any] = (),
    label: Any = None,
    temporal: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    evidence = sorted({str(item) for item in evidence_ids if item})
    source_id = str(row.get("id") or row.get("relation_id") or row.get("candidate_id") or row.get("fact_id") or stable_hash(row)[:16])
    relation_id = f"hng0-relation-{hashlib.sha256(source_id.encode('utf-8')).hexdigest()[:20]}"
    return {
        "relation_id": relation_id,
        "person_a": person_a,
        "person_b": person_b,
        "person_a_name": None,
        "person_b_name": None,
        "relation_type": kind,
        "direction": relation_direction(kind, person_a, person_b),
        "temporal_scope": temporal,
        "certainty": certainty(row.get("assertion_status")),
        "evidence_refs": evidence,
        "extraction_method": method,
        "review_status": status,
        "source_review_status": str(source_review_status or "unknown"),
        "source_record_id": source_id,
        "source_story_ids": sorted({str(item) for item in source_story_ids if item}),
        "label": compact(label) or None,
        "notes": row.get("notes"),
    }


def build_selection(people: list[Mapping[str, Any]], links: list[Mapping[str, Any]], relations: list[Mapping[str, Any]], sc1: Mapping[str, Any], ds2: Mapping[str, Any]) -> dict[str, Any]:
    story_degree = Counter(str(row.get("person_id")) for row in links if row.get("person_id"))
    relation_degree: Counter[str] = Counter()
    for row in relations:
        for key in ("subject_id", "object_id", "person_a_id", "person_b_id"):
            if row.get(key):
                relation_degree[str(row[key])] += 1
    sketch_map = sc1.get("person_sketches", {}) if isinstance(sc1.get("person_sketches"), Mapping) else {}
    ds2_people = ds2.get("people", {}) if isinstance(ds2.get("people"), Mapping) else {}
    scored: list[dict[str, Any]] = []
    for person in people:
        pid = str(person["person_id"])
        source_evidence = person.get("source_evidence") if isinstance(person.get("source_evidence"), list) else []
        sketch = sketch_map.get(pid, {}) if isinstance(sketch_map, Mapping) else {}
        alias_count = len(sketch.get("aliases", [])) if isinstance(sketch, Mapping) else 0
        jinshu_count = len((ds2_people.get(pid) or {}).get("historical_biography_entries", [])) if isinstance(ds2_people.get(pid), Mapping) else 0
        signals = {
            "story_degree": story_degree[pid],
            "relation_degree": relation_degree[pid],
            "evidence_density": len(source_evidence) + alias_count,
            "jinshu_entry_count": jinshu_count,
        }
        score = signals["story_degree"] * 10 + signals["relation_degree"] * 25 + min(signals["evidence_density"], 20) + min(jinshu_count, 5) * 3
        scored.append({"person_id": pid, "canonical_name": person.get("canonical_name"), "score": score, "signals": signals, "selection_key": hashlib.sha256(pid.encode("utf-8")).hexdigest()})
    scored.sort(key=lambda row: (-row["score"], row["selection_key"], row["person_id"]))
    total = len(scored)
    high = scored[:12]
    middle_start = max(12, total // 2 - 3)
    middle = scored[middle_start:middle_start + 6]
    low = scored[-6:]
    selected_rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    for stratum, rows in (("high_connectivity", high), ("middle_connectivity", middle), ("low_connectivity", low)):
        for row in rows:
            if row["person_id"] in seen:
                continue
            seen.add(row["person_id"])
            selected_rows.append({**row, "stratum": stratum, "rank": scored.index(row) + 1})
    selected_rows.sort(key=lambda row: (row["stratum"], row["rank"], row["selection_key"]))
    return {
        "schema": 1,
        "stage": "hng0-selection",
        "selection_method": "score_stratified_deterministic",
        "seed_person_count": len(selected_rows),
        "source_person_count": total,
        "one_hop_only": True,
        "selection_signals": ["story_degree", "relation_degree", "evidence_density", "jinshu_entry_count"],
        "people": selected_rows,
        "source_hashes": {
            "data/people.json": sha256_file(ROOT / "data/people.json"),
            "data/derived/person-story-links.json": sha256_file(PERSON_STORY_PATH),
            "data/derived/sc1-site.json": sha256_file(SC1_PATH),
        },
        "canonical_write_back": False,
    }


def build_hng0_data(root: Path = ROOT) -> dict[str, Any]:
    people_doc = read_json(root / PEOPLE_PATH.relative_to(root))
    aliases_doc = _frozen_alias_document(root) or read_json(root / ALIASES_PATH.relative_to(root))
    sc1 = read_json(root / SC1_PATH.relative_to(root))
    person_story_doc = read_json(root / PERSON_STORY_PATH.relative_to(root))
    corpus = read_json(root / CORPUS_INDEX_PATH.relative_to(root))
    relation_candidates_doc = read_json(root / RELATION_CANDIDATE_PATH.relative_to(root))
    backbone = read_json(root / H0B1_BACKBONE_PATH.relative_to(root))
    h0c_facts = read_json(root / H0C_FACTS_PATH.relative_to(root))
    offices_doc = read_json(root / H0C_OFFICES_PATH.relative_to(root))
    locations_doc = read_json(root / H0C_LOCATIONS_PATH.relative_to(root))
    location_facts_doc = read_json(root / H0C_LOCATION_FACTS_PATH.relative_to(root))
    events_doc = read_json(root / H0C_EVENTS_PATH.relative_to(root))
    participation_doc = read_json(root / H0C_PARTICIPATION_PATH.relative_to(root))
    activities_doc = read_json(root / H0C_ACTIVITIES_PATH.relative_to(root))
    anchors_doc = read_json(root / TEMPORAL_ANCHORS_PATH.relative_to(root))
    ds2 = read_json(root / DS2_PERSON_SURFACE_PATH.relative_to(root)) if (root / DS2_PERSON_SURFACE_PATH.relative_to(root)).exists() else {}

    people = [row for row in people_doc.get("people", []) if isinstance(row, Mapping)]
    people_by_id = {str(row["person_id"]): row for row in people}
    aliases = [row for row in aliases_doc.get("aliases", []) if isinstance(row, Mapping)]
    links = [row for row in person_story_doc.get("links", []) if isinstance(row, Mapping)]
    story_rows = [row for row in corpus.get("entries", []) if isinstance(row, Mapping)]
    story_index = {str(row["id"]): row for row in story_rows}
    chapter_headings = {str(row["id"]): str(row.get("heading") or row["id"]) for row in corpus.get("chapters", []) if isinstance(row, Mapping)}
    parsed_stories = {}
    for story_id in sorted(story_index):
        parsed = parse_entry(root, story_index[story_id])
        parsed["chapter_heading"] = chapter_headings.get(parsed["chapter_id"], parsed["chapter_id"])
        parsed_stories[story_id] = parsed
    published_story_ids = {str(row.get("id")) for row in sc1.get("stories", []) if row.get("id")}
    selection = build_selection(people, links, relation_candidates_doc.get("candidates", []), sc1, ds2)
    seed_ids = {row["person_id"] for row in selection["people"]}

    # PersonStory is the only source for the broad story association layer.
    # Participant/scene semantics are not inferred here.
    links_by_person: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for link in links:
        pid, story_id = str(link.get("person_id") or ""), str(link.get("entry_id") or "")
        if pid in seed_ids and story_id in parsed_stories:
            links_by_person[pid].append(link)
    stories_by_person: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for pid in sorted(links_by_person):
        for link in sorted(links_by_person[pid], key=lambda row: (parsed_stories[str(row["entry_id"])].get("global_ordinal") or 0, str(row["entry_id"]))):
            story_id = str(link["entry_id"])
            story = parsed_stories[story_id]
            layers = sorted({str(p.get("source_layer")) for p in link.get("presences", []) if isinstance(p, Mapping) and p.get("source_layer")})
            if layers == ["main_text"]:
                presence = "main_text"
            elif layers == ["liu_annotation"]:
                presence = "liu_annotation_only"
            elif "main_text" in layers and "liu_annotation" in layers:
                presence = "both"
            else:
                presence = "liu_annotation_only"
            excerpt_source = story["main_text"] if story["main_text"] else " ".join(item["text"] for item in story["liu_annotations"])
            excerpt = compact(excerpt_source)[:140]
            stories_by_person[pid].append({
                "story_id": story_id,
                "chapter_id": story["chapter_id"],
                "chapter_heading": story["chapter_heading"],
                "story_ordinal": story.get("ordinal"),
                "global_ordinal": story.get("global_ordinal"),
                "source_presence": presence,
                "person_story_link_id": link.get("id"),
                "link_basis": link.get("link_basis"),
                "resolution_status": link.get("resolution_status"),
                "confidence": link.get("confidence"),
                "review_status": link.get("review_status"),
                "research_scope": "published" if story_id in published_story_ids else "research_only",
                "short_excerpt": excerpt,
                "evidence_refs": sorted({str(ref) for ref in link.get("evidence_ids", []) if ref}),
            })

    relation_rows: list[dict[str, Any]] = []
    relation_keys: set[tuple[str, str, str]] = set()
    sc1_relations = [row for row in sc1.get("relations", []) if isinstance(row, Mapping)]
    for row in sc1_relations:
        a, b = str(row.get("subject_id") or ""), str(row.get("object_id") or "")
        kind = relation_type(row.get("relation_type"), row.get("relation_subtype"))
        refs = row.get("evidence_ids") if isinstance(row.get("evidence_ids"), list) else []
        if not a or not b or not kind or not refs or not (a in seed_ids or b in seed_ids):
            continue
        key = (min(a, b), max(a, b), kind)
        if key in relation_keys:
            continue
        relation_keys.add(key)
        status = "accepted" if row.get("review_status") == "reviewed" else "candidate"
        relation_rows.append(make_relation(row, a, b, kind, "existing_reviewed_relation", status, refs, row.get("review_status"), row.get("story_ids") or row.get("source_entry_ids"), row.get("label"), row.get("time")))

    for row in relation_candidates_doc.get("candidates", []):
        if not isinstance(row, Mapping) or row.get("cooccurrence_only") is True or row.get("materialized_relation_id"):
            continue
        a, b = str(row.get("person_a_id") or ""), str(row.get("person_b_id") or "")
        kind = relation_type(row.get("proposed_relation_class"), proposed=row.get("proposed_relation_class"))
        refs = row.get("evidence_ids") if isinstance(row.get("evidence_ids"), list) else []
        if not a or not b or not kind or not refs or not (a in seed_ids or b in seed_ids):
            continue
        key = (min(a, b), max(a, b), kind)
        if key in relation_keys:
            continue
        relation_keys.add(key)
        relation_rows.append(make_relation(row, a, b, kind, "reviewed_relation_candidate", "candidate", refs, row.get("review_status"), row.get("source_entry_ids"), f"{row.get('proposed_role_a') or ''} / {row.get('proposed_role_b') or ''}"))

    # Same-clan is allowed only when both memberships are explicit structured
    # records.  It is never inferred from surname or Story co-occurrence.
    clan_map = {str(row.get("clan_id")): row for row in backbone.get("clans", []) if isinstance(row, Mapping)}
    memberships = [row for row in backbone.get("clan_memberships", []) if isinstance(row, Mapping)]
    members_by_clan: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for row in memberships:
        if row.get("clan_id") and row.get("person_id") in people_by_id:
            members_by_clan[str(row["clan_id"])].append(row)
    for clan_id in sorted(members_by_clan):
        members = sorted(members_by_clan[clan_id], key=lambda row: str(row.get("person_id")))
        for index, left in enumerate(members):
            for right in members[index + 1:]:
                a, b = str(left["person_id"]), str(right["person_id"])
                if a not in seed_ids and b not in seed_ids:
                    continue
                kind = "same_clan"
                key = (min(a, b), max(a, b), kind)
                if key in relation_keys:
                    continue
                relation_keys.add(key)
                refs = list(left.get("evidence_ids", [])) + list(right.get("evidence_ids", []))
                clan = clan_map.get(clan_id, {})
                relation_rows.append(make_relation({"id": f"{clan_id}:{a}:{b}", "assertion_status": left.get("assertion_status"), "notes": "同族关系仅来自现有显式族属记录。"}, a, b, kind, "existing_explicit_clan_membership", "candidate", refs, left.get("review_status"), label=clan.get("canonical_name")))

    relation_rows.sort(key=lambda row: row["relation_id"])
    for row in relation_rows:
        row["person_a_name"] = people_by_id.get(row["person_a"], {}).get("canonical_name")
        row["person_b_name"] = people_by_id.get(row["person_b"], {}).get("canonical_name")

    # Temporal spine inputs.
    offices = [row for row in offices_doc.get("tenures", []) if isinstance(row, Mapping)]
    office_entities = {str(row.get("office_id")): row for row in offices_doc.get("entities", []) if isinstance(row, Mapping)}
    locations = {str(row.get("location_id")): row for row in locations_doc.get("records", []) if isinstance(row, Mapping)}
    events = {str(row.get("event_id")): row for row in events_doc.get("records", []) if isinstance(row, Mapping)}
    participations = [row for row in participation_doc.get("records", []) if isinstance(row, Mapping)]
    activities = [row for row in activities_doc.get("records", []) if isinstance(row, Mapping)]
    location_facts = [row for row in location_facts_doc.get("records", []) if isinstance(row, Mapping)]
    anchors = {str(row.get("story_id")): row for row in read_json(root / TEMPORAL_ANCHORS_PATH.relative_to(root)).get("records", []) if isinstance(row, Mapping)}
    temporal_items: list[dict[str, Any]] = []

    def add_time(row: Mapping[str, Any], person_id: str, kind: str, label: Any, start: Any, end: Any, raw_precision: Any, refs: Iterable[Any], method: str, source_story_ids: Iterable[Any] = (), extra: Mapping[str, Any] | None = None) -> None:
        refs_clean = sorted({str(ref) for ref in refs if ref})
        if not person_id or person_id not in seed_ids or not refs_clean:
            return
        item_id = str(row.get("id") or row.get("tenure_id") or row.get("event_participation_id") or row.get("activity_id") or row.get("location_fact_id") or row.get("anchor_id") or stable_hash(row)[:20])
        try:
            start_value = int(start) if start is not None else None
        except (TypeError, ValueError):
            start_value = None
        try:
            end_value = int(end) if end is not None else None
        except (TypeError, ValueError):
            end_value = None
        data = {
            "temporal_id": f"hng0-time-{hashlib.sha256(item_id.encode('utf-8')).hexdigest()[:20]}",
            "person_id": person_id,
            "kind": kind,
            "label": compact(label) or kind,
            "start_year": start_value,
            "end_year": end_value,
            "precision": precision(raw_precision, start_value, end_value),
            "temporal_scope": {"start_year": start_value, "end_year": end_value, "precision": precision(raw_precision, start_value, end_value)},
            "certainty": certainty(row.get("assertion_status")),
            "evidence_refs": refs_clean,
            "extraction_method": method,
            "review_status": review_status(row.get("review_status")),
            "source_review_status": str(row.get("review_status") or "unknown"),
            "source_record_id": item_id,
            "source_story_ids": sorted({str(item) for item in source_story_ids if item}),
        }
        if extra:
            data.update(dict(extra))
        if not any(item["temporal_id"] == data["temporal_id"] for item in temporal_items):
            temporal_items.append(data)

    for row in offices:
        pid = str(row.get("person_id") or "")
        entity = office_entities.get(str(row.get("office_id")), {})
        add_time(row, pid, "office_tenure", row.get("office_title") or entity.get("canonical_name"), row.get("start_year_ce"), row.get("end_year_ce"), row.get("temporal_precision"), row.get("evidence_ids", []), "existing_office_tenure")
    for row in participations:
        pid, event_id = str(row.get("person_id") or ""), str(row.get("event_id") or "")
        event = events.get(event_id, {})
        add_time(row, pid, "major_event_participation", event.get("canonical_name") or event_id, row.get("start_year_ce") or event.get("start_year_ce"), row.get("end_year_ce") or event.get("end_year_ce"), row.get("temporal_precision") or event.get("temporal_precision"), row.get("evidence_ids", []) + event.get("evidence_ids", []), "existing_event_participation", [row.get("story_id")] if row.get("story_id") else [])
    for row in activities:
        pid = str(row.get("person_id") or "")
        event = events.get(str(row.get("event_id") or ""), {})
        label = row.get("label") or row.get("activity_type") or event.get("canonical_name")
        add_time(row, pid, "major_activity_phase", label, (row.get("time") or {}).get("start_year_ce") if isinstance(row.get("time"), Mapping) else None, (row.get("time") or {}).get("end_year_ce") if isinstance(row.get("time"), Mapping) else None, row.get("precision") or (row.get("time") or {}).get("precision") if isinstance(row.get("time"), Mapping) else None, row.get("evidence_ids", []), "existing_person_activity", [row.get("story_id")] if row.get("story_id") else [])
    for row in location_facts:
        pid = str(row.get("subject_id") or "")
        location = locations.get(str(row.get("location_id")), {})
        add_time(row, pid, "residence_activity_location", location.get("canonical_name") or row.get("location_id"), row.get("start_year_ce"), row.get("end_year_ce"), row.get("temporal_precision"), row.get("evidence_ids", []), "existing_location_fact", extra={"location_role": row.get("location_role")})
    for pid in sorted(links_by_person):
        for story in stories_by_person[pid]:
            anchor = anchors.get(story["story_id"])
            if not anchor:
                continue
            add_time(anchor, pid, "story_temporal_anchor", anchor.get("rationale") or anchor.get("precision") or "故事时代定位", anchor.get("start_year_ce"), anchor.get("end_year_ce"), anchor.get("precision"), anchor.get("evidence_ids", []), "existing_story_temporal_anchor", [story["story_id"]], {"story_id": story["story_id"], "anchor_id": anchor.get("anchor_id")})
    temporal_items.sort(key=lambda row: (row["person_id"], row["start_year"] is None, row["start_year"] or 9999, row["temporal_id"]))

    wanted_refs: set[str] = set()
    for row in relation_rows:
        wanted_refs.update(row["evidence_refs"])
    for row in temporal_items:
        wanted_refs.update(row["evidence_refs"])
    for rows in stories_by_person.values():
        for row in rows:
            wanted_refs.update(row["evidence_refs"])
    person_records: dict[str, dict[str, Any]] = {}
    sketch_map = sc1.get("person_sketches", {}) if isinstance(sc1.get("person_sketches"), Mapping) else {}
    aliases_by_person: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for alias in aliases:
        for pid in alias.get("person_ids", []) if isinstance(alias.get("person_ids"), list) else []:
            aliases_by_person[str(pid)].append(alias)
    memberships_by_person: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for row in memberships:
        memberships_by_person[str(row.get("person_id"))].append(row)
    temporal_by_person: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in temporal_items:
        temporal_by_person[row["person_id"]].append(row)
    relation_by_person: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in relation_rows:
        if row["person_a"] in seed_ids:
            relation_by_person[row["person_a"]].append(row)
        if row["person_b"] in seed_ids and row["person_b"] != row["person_a"]:
            relation_by_person[row["person_b"]].append(row)
    for pid in sorted(seed_ids):
        person = people_by_id[pid]
        sketch = sketch_map.get(pid, {}) if isinstance(sketch_map, Mapping) else {}
        identity = sketch.get("identity", {}) if isinstance(sketch, Mapping) else {}
        alias_rows: list[dict[str, Any]] = []
        for alias in sorted(aliases_by_person.get(pid, []), key=lambda row: (str(row.get("surface") or ""), str(row.get("alias_id") or ""))):
            refs: list[str] = []
            for source in alias.get("source_evidence", []) if isinstance(alias.get("source_evidence"), list) else []:
                if isinstance(source, Mapping):
                    refs.extend(str(ref) for ref in source.get("evidence_ids", []) if ref)
            alias_rows.append({"surface": pair(alias.get("surface")), "alias_type": alias.get("alias_type"), "status": alias.get("status"), "evidence_refs": sorted(set(refs))})
            wanted_refs.update(refs)
        for alias in sketch.get("aliases", []) if isinstance(sketch, Mapping) else []:
            refs = [str(ref) for ref in alias.get("evidence_ids", []) if ref]
            if refs:
                wanted_refs.update(refs)
        clan_rows = memberships_by_person.get(pid, [])
        clan = None
        if clan_rows:
            c = clan_map.get(str(clan_rows[0].get("clan_id")), {})
            clan = {"clan_id": c.get("clan_id"), "name": pair(c.get("canonical_name")), "locality": pair(c.get("locality_label")), "review_status": c.get("review_status"), "evidence_refs": sorted({str(ref) for row in clan_rows for ref in row.get("evidence_ids", []) if ref})}
            wanted_refs.update(clan["evidence_refs"])
        office_labels = unique_strings([row.get("label") for row in temporal_by_person[pid] if row.get("kind") == "office_tenure"] + [row.get("surface") for row in alias_rows if row.get("alias_type") == "office_title"])
        person_records[pid] = {
            "person_id": pid,
            "person": {
                "name": pair(person.get("canonical_name")),
                "courtesy_name": pair((identity.get("courtesy_name") or {}).get("original") if isinstance(identity.get("courtesy_name"), Mapping) else identity.get("courtesy_name")),
                "aliases": alias_rows,
                "title_office_appellations": [pair(value) for value in office_labels],
                "clan": clan,
                "native_place": None,
                "review_status": person.get("review_status"),
                "evidence_refs": sorted({str(ref) for ref in identity.get("evidence_ids", []) if ref} | {str(ref) for ref in sketch.get("profile_evidence_ids", []) if ref}),
            },
            "stories": stories_by_person.get(pid, []),
            "relations": sorted(relation_by_person.get(pid, []), key=lambda row: row["relation_id"]),
            "temporal_spine": temporal_by_person.get(pid, []),
            "nearby_person_ids": sorted({row["person_b"] if row["person_a"] == pid else row["person_a"] for row in relation_by_person.get(pid, [])}),
            "approximate_temporal_window": {
                "start_year": min((row["start_year"] for row in temporal_by_person.get(pid, []) if row["start_year"] is not None), default=None),
                "end_year": max((row["end_year"] for row in temporal_by_person.get(pid, []) if row["end_year"] is not None), default=None),
                "precision": "between" if any(row["start_year"] is not None or row["end_year"] is not None for row in temporal_by_person.get(pid, [])) else "unknown",
            },
        }
    evidence_registry = build_evidence_registry(root, wanted_refs, sc1)
    for record in person_records.values():
        record["person"]["evidence_refs"] = sorted(set(record["person"]["evidence_refs"]) & set(evidence_registry))

    retrieval_trace: dict[str, dict[str, Any]] = {}
    for pid in sorted(seed_ids):
        person_evidence = set(person_records[pid]["person"].get("evidence_refs", []))
        story_evidence = {ref for story in stories_by_person.get(pid, []) for ref in story.get("evidence_refs", [])}
        relation_evidence = {ref for relation in relation_by_person.get(pid, []) for ref in relation.get("evidence_refs", [])}
        temporal_evidence = {ref for item in temporal_by_person.get(pid, []) for ref in item.get("evidence_refs", [])}
        searched_refs = sorted(person_evidence | story_evidence | relation_evidence | temporal_evidence)
        opened_refs = sorted(ref for ref in searched_refs if evidence_registry.get(ref, {}).get("provenance_kind") == "source_text")
        corpora = sorted({evidence_registry.get(ref, {}).get("source_work", "既有项目记录") for ref in searched_refs})
        retrieval_trace[pid] = {
            "person_id": pid,
            "method": "existing_local_projection",
            "llm_calls": 0,
            "searched_corpora": corpora,
            "searched_refs": searched_refs,
            "retrieved_refs": sorted(story_evidence | relation_evidence | temporal_evidence),
            "opened_refs": opened_refs,
            "used_evidence_refs": sorted(story_evidence | relation_evidence | temporal_evidence),
        }

    relation_source_counts = Counter()
    relation_type_counts = Counter()
    for row in relation_rows:
        relation_type_counts[row["relation_type"]] += 1
        for ref in row["evidence_refs"]:
            relation_source_counts[evidence_registry.get(ref, {}).get("source_work", "unknown")] += 1
    temporal_source_counts = Counter()
    for row in temporal_items:
        for ref in row["evidence_refs"]:
            temporal_source_counts[evidence_registry.get(ref, {}).get("source_work", "unknown")] += 1
    relation_status_counts = Counter(row["review_status"] for row in relation_rows)
    temporal_status_counts = Counter(row["review_status"] for row in temporal_items)
    precision_counts = Counter(row["precision"] for row in temporal_items)
    discovered = sorted({endpoint for row in relation_rows if row["person_a"] in seed_ids or row["person_b"] in seed_ids for endpoint in (row["person_a"], row["person_b"]) if endpoint not in seed_ids})
    candidates = {
        "schema": 1,
        "stage": "hng0-candidate",
        "canonical_write_back": False,
        "scope": {"seed_person_ids": sorted(seed_ids), "one_hop_only": True, "source_person_count": len(people_by_id), "source_story_count": len(story_index)},
        "people": {pid: person_records[pid] for pid in sorted(person_records)},
        "relations": relation_rows,
        "temporal_items": temporal_items,
        "evidence": evidence_registry,
        "retrieval_trace": retrieval_trace,
        "source_policy": {"cooccurrence_only_relations": "excluded", "surname_only_relations": "excluded", "candidate_only": True, "source_text_missing_is_explicit": True},
    }
    metrics = {
        "schema": 1,
        "stage": "hng0-metrics",
        "seed_person_count": len(seed_ids),
        "discovered_one_hop_person_count": len(discovered),
        "candidate_relation_count": len(relation_rows),
        "relation_status_counts": dict(sorted(relation_status_counts.items())),
        "relations_by_type": dict(sorted(relation_type_counts.items())),
        "evidence_backed_relation_rate": round(sum(bool(row["evidence_refs"]) for row in relation_rows) / len(relation_rows), 4) if relation_rows else 0.0,
        "temporal_item_count": len(temporal_items),
        "temporal_review_status_counts": dict(sorted(temporal_status_counts.items())),
        "temporal_precision_counts": dict(sorted(precision_counts.items())),
        "source_work_contribution": dict(sorted((relation_source_counts + temporal_source_counts).items())),
        "orphan_unresolved_identity_count": len([row for row in relation_rows if row["person_a"] not in people_by_id or row["person_b"] not in people_by_id]),
        "evidence_validation_failures": len([ref for row in relation_rows + temporal_items for ref in row["evidence_refs"] if ref not in evidence_registry]),
        "source_text_unresolved_reference_count": sum(1 for row in evidence_registry.values() if row["provenance_kind"] == "unresolved_reference"),
        "average_one_hop_neighborhood_size": round(sum(len(person_records[pid]["nearby_person_ids"]) for pid in person_records) / len(person_records), 3) if person_records else 0.0,
    }
    return {"selection": selection, "candidates": candidates, "metrics": metrics}


def default_overlay(candidates: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "schema": 1,
        "stage": "hng0-review-overlay",
        "canonical_write_back": False,
        "relation_decisions": {row["relation_id"]: {"review_status": row["review_status"], "reviewer_note": ""} for row in candidates.get("relations", [])},
        "temporal_decisions": {row["temporal_id"]: {"review_status": row["review_status"], "reviewer_note": ""} for row in candidates.get("temporal_items", [])},
    }


def merge_overlay(candidates: Mapping[str, Any], overlay: Mapping[str, Any]) -> dict[str, Any]:
    relation_decisions = overlay.get("relation_decisions", {}) if isinstance(overlay.get("relation_decisions"), Mapping) else {}
    temporal_decisions = overlay.get("temporal_decisions", {}) if isinstance(overlay.get("temporal_decisions"), Mapping) else {}
    relations = []
    for row in candidates.get("relations", []):
        item = dict(row)
        decision = relation_decisions.get(row["relation_id"], {})
        if isinstance(decision, Mapping) and decision.get("review_status") in REVIEW_STATUSES:
            item["review_status"] = decision["review_status"]
        relations.append(item)
    temporal = []
    for row in candidates.get("temporal_items", []):
        item = dict(row)
        decision = temporal_decisions.get(row["temporal_id"], {})
        if isinstance(decision, Mapping) and decision.get("review_status") in REVIEW_STATUSES:
            item["review_status"] = decision["review_status"]
        temporal.append(item)
    people = {}
    for pid, source in candidates.get("people", {}).items():
        item = dict(source)
        item["relations"] = [row for row in relations if row["person_a"] == pid or row["person_b"] == pid]
        item["temporal_spine"] = [row for row in temporal if row["person_id"] == pid]
        people[pid] = item
    return {"schema": 1, "stage": "hng0-reviewed-projection", "canonical_write_back": False, "people": people, "relations": relations, "temporal_items": temporal, "evidence": candidates.get("evidence", {})}


def build_frontend_bundle(candidates: Mapping[str, Any], projection: Mapping[str, Any], selection: Mapping[str, Any], metrics: Mapping[str, Any]) -> dict[str, Any]:
    labels = {str(row["person_id"]): row.get("canonical_name") or row["person_id"] for row in selection.get("people", [])}
    for row in candidates.get("relations", []):
        labels.setdefault(row["person_a"], row.get("person_a_name") or row["person_a"])
        labels.setdefault(row["person_b"], row.get("person_b_name") or row["person_b"])
    return {
        "schema": 1,
        "stage": "hng0-frontend-review",
        "canonical_write_back": False,
        "selection": selection,
        "metrics": metrics,
        "person_labels": dict(sorted(labels.items())),
        "people": projection.get("people", {}),
        "relations": projection.get("relations", []),
        "temporal_items": projection.get("temporal_items", []),
        "evidence": projection.get("evidence", {}),
        "review_storage": "localStorage:shishuoSketch.hng0-review",
    }


def ensure_overlay(candidates: Mapping[str, Any]) -> dict[str, Any]:
    overlay = read_json(REVIEW_PATH) if REVIEW_PATH.exists() else default_overlay(candidates)
    changed = False
    if not isinstance(overlay, Mapping):
        overlay = default_overlay(candidates)
        changed = True
    overlay = dict(overlay)
    overlay.setdefault("schema", 1)
    overlay.setdefault("stage", "hng0-review-overlay")
    overlay.setdefault("canonical_write_back", False)
    for key, rows, default in (("relation_decisions", candidates.get("relations", []), "candidate"), ("temporal_decisions", candidates.get("temporal_items", []), "candidate")):
        decisions = dict(overlay.get(key, {})) if isinstance(overlay.get(key), Mapping) else {}
        for row in rows:
            item_id = row["relation_id"] if key == "relation_decisions" else row["temporal_id"]
            if item_id not in decisions:
                decisions[item_id] = {"review_status": row.get("review_status", default), "reviewer_note": ""}
                changed = True
        overlay[key] = {item_id: decisions[item_id] for item_id in sorted(decisions)}
    if changed or not REVIEW_PATH.exists():
        write_json(REVIEW_PATH, overlay)
    return overlay


def write_outputs(root: Path = ROOT) -> dict[str, Any]:
    data = build_hng0_data(root)
    candidates = data["candidates"]
    overlay = ensure_overlay(candidates)
    projection = merge_overlay(candidates, overlay)
    neighborhoods = {pid: projection["people"][pid] for pid in sorted(projection["people"])}
    frontend = build_frontend_bundle(candidates, projection, data["selection"], data["metrics"])
    write_json(SELECTION_PATH, data["selection"])
    write_json(CANDIDATE_PATH, candidates)
    write_json(PROJECTION_PATH, projection)
    write_json(NEIGHBORHOOD_PATH, {"schema": 1, "stage": "hng0-neighborhoods", "canonical_write_back": False, "people": neighborhoods})
    write_json(RETRIEVAL_TRACE_PATH, {"schema": 1, "stage": "hng0-retrieval-trace", "canonical_write_back": False, "method": "existing_local_projection", "people": candidates.get("retrieval_trace", {})})
    write_json(METRICS_PATH, data["metrics"])
    manifest = {
        "schema": 1,
        "stage": "hng0-manifest",
        "canonical_write_back": False,
        "source_inputs": [
            "data/people.json", "data/aliases.json", "data/derived/person-story-links.json", "data/shishuo-corpus-index.json",
            "data/derived/sc1-site.json", "data/derived/person-relation-candidates-r3.json", "data/derived/h0b1-social-backbone.json",
            "data/derived/h0c-historical-facts.json", "data/derived/h0c-offices.json", "data/derived/h0c-locations.json",
            "data/derived/h0c-location-facts.json", "data/derived/h0c-events.json", "data/derived/h0c-event-participations.json",
            "data/derived/h0c-person-activities.json", "data/annotation/story-temporal-anchors-h0a.json", "data/evidence/wp1-evidence.json",
        ],
        "source_hashes": {relative: (_alias_source_hash(root) if relative == "data/aliases.json" else sha256_file(root / relative)) for relative in [
            "data/people.json", "data/aliases.json", "data/derived/person-story-links.json", "data/shishuo-corpus-index.json",
            "data/derived/sc1-site.json", "data/derived/person-relation-candidates-r3.json", "data/derived/h0b1-social-backbone.json",
            "data/derived/h0c-historical-facts.json", "data/derived/h0c-offices.json", "data/derived/h0c-locations.json",
            "data/derived/h0c-location-facts.json", "data/derived/h0c-events.json", "data/derived/h0c-event-participations.json",
            "data/derived/h0c-person-activities.json", "data/annotation/story-temporal-anchors-h0a.json", "data/evidence/wp1-evidence.json",
        ]},
        "outputs": ["hng0-selection.json", "hng0-candidates.json", "hng0-reviewed-projection.json", "hng0-neighborhoods.json", "hng0-retrieval-trace.json", "hng0-metrics.json"],
        "frontend_bundle": "site/src/generated/hng0-site.json",
        "review_overlay": "data/annotation/hng0-review.json",
    }
    write_json(MANIFEST_PATH, manifest)
    write_json(FRONTEND_PATH, frontend)
    return {**data, "overlay": overlay, "projection": projection, "frontend": frontend}


def main() -> int:
    result = write_outputs()
    print(json.dumps({"status": "pass", "seed_person_count": result["selection"]["seed_person_count"], "relations": len(result["candidates"]["relations"]), "temporal_items": len(result["candidates"]["temporal_items"]), "evidence": len(result["candidates"]["evidence"])}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
