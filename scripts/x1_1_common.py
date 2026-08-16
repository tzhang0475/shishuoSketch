#!/usr/bin/env python3
"""Shared deterministic inputs and scoring helpers for X1.1.

X1.1 is deliberately an overlay.  It reads the protected H0C/HG0/ML0
artifacts and the wider canonical Story/PersonStory boundary, but it does not
write back to any of those layers.  The functions in this module therefore
also make the scope boundary explicit for the individual builders.
"""

from __future__ import annotations

from collections import Counter, defaultdict
import hashlib
import json
import math
from pathlib import Path
import re
from typing import Any, Iterable, Mapping

try:
    from scripts.build_six_person_pilot import parse_frontmatter, parse_shishuo_sections
except ModuleNotFoundError:  # direct execution from scripts/
    from build_six_person_pilot import parse_frontmatter, parse_shishuo_sections


ROOT = Path(__file__).resolve().parents[1]

POOL_PATH = Path("data/derived/x1-1-candidate-pool.json")
SELECTION_PATH = Path("data/derived/x1-1-selection-manifest.json")
REVIEW_PATH = Path("data/derived/x1-1-review-results.json")
INFO_GAIN_PATH = Path("data/derived/x1-1-information-gain.json")
BIAS_PATH = Path("data/derived/x1-1-bias-audit.json")
ONTOLOGY_PATH = Path("data/derived/x1-1-ontology-gap-candidates.json")
RECOMMENDATION_PATH = Path("data/derived/x1-1-next-epoch-recommendation.json")
SUMMARY_PATH = Path("data/derived/x1-1-summary.json")

CORPUS_PATH = Path("data/shishuo-corpus-index.json")
PUNCTUATION_PATH = Path("data/annotation/wp1-punctuation.json")
PEOPLE_PATH = Path("data/people.json")
MENTIONS_PATH = Path("data/mentions/shishuo.json")
EVIDENCE_PATH = Path("data/evidence/wp1-evidence.json")
LINKS_PATH = Path("data/derived/person-story-links.json")
SC1_PATH = Path("data/derived/sc1-site.json")
H0C_FACTS_PATH = Path("data/derived/h0c-historical-facts.json")
H0C_GRAPH_PATH = Path("data/derived/h0c-graph-projection.json")
H0C_PARTICIPANT_PATH = Path("data/derived/h0c-participant-freeze.json")
H0C_PROTECTION_PATH = Path("data/derived/h0c-protection-manifest.json")
HG0_GRAPH_PATH = Path("data/derived/hg0-graph-projection.json")
HG0_UNIVERSE_PATH = Path("data/derived/hg0-graph-universe.json")
HG0_ONTOLOGY_PATH = Path("data/derived/hg0-ontology.json")
HG0_AUDIT_PATH = Path("data/derived/hg0-sufficiency-audit.json")
HG0_BIAS_PATH = Path("data/derived/hg0-bias-audit.json")
HG0_PROTECTION_PATH = Path("data/derived/hg0-protection-manifest.json")
ML0_DATASET_PATH = Path("data/derived/ml0-dataset-manifest.json")
ML0_BIAS_PATH = Path("data/derived/ml0-bias-diagnostic.json")
ML0_RECOMMENDATION_PATH = Path("data/derived/ml0-expansion-recommendation.json")
ML0_EXPERIMENT_PATH = Path("data/derived/ml0-experiment-manifest.json")
ML0_METRICS_PATH = Path("data/derived/ml0-metrics.json")
ML0_GNN_PATH = Path("data/derived/ml0-gnn-results.json")
ML0_ABLATION_PATH = Path("data/derived/ml0-ablation-results.json")
ML0_LINK_PATH = Path("data/derived/ml0-link-feasibility.json")
ML0_TEMPORAL_PATH = Path("data/derived/ml0-temporal-feasibility.json")
ML0_PROTECTION_PATH = Path("data/derived/ml0-protection-manifest.json")

EPOCH = "X1.1"
SOURCE_GRAPH_VERSION = "HG0"
SOURCE_ML_VERSION = "ML0"
BATCH_SIZE = 20
SEED = 20260816
RATIOS: dict[str, float] = {
    "graph_guided": 0.40,
    "coverage_guided": 0.30,
    "stratified_random": 0.15,
    "counter_model": 0.15,
}
CHANNEL_ORDER = tuple(RATIOS)

HIGH_PRIORITY_LAYERS = ("family", "office", "event", "temporal")
MEDIUM_PRIORITY_LAYERS = ("clan", "geographic", "service_political")
EXTERNAL_LAYERS = HIGH_PRIORITY_LAYERS + MEDIUM_PRIORITY_LAYERS

OFFICE_TERMS = (
    "太尉", "丞相", "太傅", "尚書", "尚书", "大司馬", "大司马", "刺史",
    "將軍", "将军", "中書令", "中书令", "侍中", "司徒", "司空", "參軍", "参军",
    "右軍", "右军", "校尉", "令", "守", "牧",
)
EVENT_TERMS = (
    "王敦", "蘇峻", "苏峻", "八王", "永嘉", "淝水", "北伐", "南渡", "過江", "过江",
    "石勒", "劉曜", "刘曜", "孫恩", "孙恩", "亂", "乱", "兵", "討", "讨",
)
TEMPORAL_TERMS = (
    "年", "帝", "王", "即位", "在位", "咸和", "太寧", "太宁", "永和", "太元",
    "建武", "永嘉", "興寧", "兴宁", "元帝", "明帝", "成帝", "穆帝", "哀帝",
)
FAMILY_TERMS = (
    "父", "母", "子", "兄", "弟", "姊", "姐", "妹", "夫", "妻", "婚", "嫁", "娶",
    "女", "婿", "甥", "舅", "叔", "伯", "昆季", "家", "族",
)
LOCATION_TERMS = (
    "京口", "建康", "建業", "建业", "洛", "洛陽", "洛阳", "武昌", "會稽", "会稽",
    "吳", "吴", "荊州", "荆州", "揚州", "扬州", "江東", "江东", "江左", "中原",
    "彭城", "襄陽", "襄阳", "廣陵", "广陵", "姑孰", "新亭", "東山", "东山",
)
ONTOLOGY_CLUES: dict[str, tuple[str, ...]] = {
    "recommendation_patronage": ("薦", "荐", "舉", "举", "辟", "徵", "征", "召", "拔"),
    "literary_association": ("文", "詩", "诗", "賦", "赋", "文章", "著", "作", "筆", "笔"),
    "teacher_student": ("師", "师", "弟子", "受學", "受学", "授", "業", "业"),
    "marriage_mediation": ("婚", "嫁", "娶", "婿", "壻", "女", "媒", "姻"),
    "reputation_evaluation": ("評", "评", "品", "名", "聲", "声", "譽", "誉", "稱", "称"),
    "retreat_reclusion": ("隱", "隐", "遯", "遁", "居", "東山", "东山", "高臥", "高卧"),
    "office_sponsorship": ("薦", "荐", "辟", "拜", "除", "任", "尚書", "尚书"),
}


def read(path: Path | str) -> Any:
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


def write(path: Path | str, value: Any) -> None:
    target = ROOT / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=False) + "\n", encoding="utf-8")


def sha256_file(path: Path | str) -> str:
    digest = hashlib.sha256()
    with (ROOT / path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def canonical_hash(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def stable_hash(*values: object) -> str:
    material = "|".join(str(value) for value in values)
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def unique(values: Iterable[object]) -> list[str]:
    return sorted({str(value) for value in values if isinstance(value, str) and value})


def bounded(value: float) -> float:
    return round(max(0.0, min(1.0, value)), 8)


def log_norm(value: int | float, maximum: int | float) -> float:
    if value <= 0 or maximum <= 0:
        return 0.0
    return bounded(math.log1p(float(value)) / math.log1p(float(maximum)))


def parse_entry(entry: Mapping[str, Any]) -> dict[str, Any]:
    path = ROOT / str(entry["path"])
    text = path.read_text(encoding="utf-8")
    metadata = parse_frontmatter(text)
    main_text = ""
    annotation_texts: list[str] = []
    annotation_ids: list[str] = []
    for section, body, section_metadata in parse_shishuo_sections(text):
        if section == "main_text":
            main_text = body.rstrip("\n")
        elif section == "liu_annotation":
            annotation_texts.append(body.rstrip("\n"))
            annotation_ids.append(str(section_metadata.get("annotation_id", f"annotation-{len(annotation_ids)+1:03d}")))
    return {
        "metadata": metadata,
        "main_text": main_text,
        "annotation_text": "\n".join(annotation_texts),
        "annotation_ids": annotation_ids,
        "source_path": str(entry["path"]),
        "source_sha256": str(entry.get("entry_sha256") or hashlib.sha256(path.read_bytes()).hexdigest()),
        "global_ordinal": int(entry.get("global_ordinal", 10**9)),
    }


def source_layers_for_link(link: Mapping[str, Any]) -> list[str]:
    return unique(
        presence.get("source_layer")
        for presence in link.get("presences", [])
        if isinstance(presence, Mapping)
    )


def build_context() -> dict[str, Any]:
    corpus = read(CORPUS_PATH)
    entries = {str(item["id"]): item for item in corpus.get("entries", []) if isinstance(item, Mapping)}
    chapter_headings = {
        str(item["id"]): str(item.get("heading", item["id"]))
        for item in corpus.get("chapters", [])
        if isinstance(item, Mapping) and isinstance(item.get("id"), str)
    }
    punctuation = {
        str(item["entry_id"]): item
        for item in read(PUNCTUATION_PATH).get("records", [])
        if isinstance(item, Mapping) and isinstance(item.get("entry_id"), str)
    }
    people = {
        str(item["person_id"]): item
        for item in read(PEOPLE_PATH).get("people", [])
        if isinstance(item, Mapping) and isinstance(item.get("person_id"), str)
    }
    production_story_ids = {
        str(item["id"])
        for item in read(SC1_PATH).get("stories", [])
        if isinstance(item, Mapping) and isinstance(item.get("id"), str)
    }
    links = [item for item in read(LINKS_PATH).get("links", []) if isinstance(item, Mapping)]
    links_by_story: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for link in links:
        story_id = link.get("entry_id")
        if isinstance(story_id, str):
            links_by_story[story_id].append(link)
    mentions = [item for item in read(MENTIONS_PATH).get("mentions", []) if isinstance(item, Mapping)]
    mentions_by_story: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for mention in mentions:
        story_id = mention.get("entry_id") or mention.get("source_id")
        if isinstance(story_id, str):
            mentions_by_story[story_id].append(mention)
    evidence_records = [item for item in read(EVIDENCE_PATH).get("records", []) if isinstance(item, Mapping)]
    evidence_ids = {str(item["id"]) for item in evidence_records if isinstance(item.get("id"), str)}
    evidence_by_story: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for evidence in evidence_records:
        locator = evidence.get("locator")
        if isinstance(locator, Mapping) and isinstance(locator.get("entry_id"), str):
            evidence_by_story[str(locator["entry_id"])].append(evidence)

    hg0_graph = read(HG0_GRAPH_PATH)
    hg0_nodes = {(str(node.get("node_type")), str(node.get("node_id"))): node for node in hg0_graph.get("nodes", []) if isinstance(node, Mapping)}
    fact_index = {
        str(item.get("fact_id")): item
        for item in read(H0C_FACTS_PATH).get("fact_index", [])
        if isinstance(item, Mapping) and isinstance(item.get("fact_id"), str)
    }
    person_layer_counts: dict[str, Counter[str]] = defaultdict(Counter)
    person_story_degrees: Counter[str] = Counter()
    external_person_pairs: set[tuple[str, str]] = set()
    person_graph_degrees: Counter[str] = Counter()
    for edge in hg0_graph.get("edges", []):
        if not isinstance(edge, Mapping):
            continue
        layers = set(edge.get("layer_memberships", []))
        layers.discard("reification_support")
        endpoint_people: set[str] = set()
        for endpoint in (edge.get("source"), edge.get("target")):
            if isinstance(endpoint, Mapping) and endpoint.get("node_type") == "Person":
                endpoint_people.add(str(endpoint.get("node_id")))
        if not endpoint_people:
            for fact_id in edge.get("fact_ids", []):
                fact = fact_index.get(str(fact_id), {})
                for subject_id in fact.get("subject_ids", []):
                    if str(subject_id) in people:
                        endpoint_people.add(str(subject_id))
        for person_id in endpoint_people:
            person_graph_degrees[person_id] += 1
            for layer in layers:
                person_layer_counts[person_id][str(layer)] += 1
            if edge.get("edge_type") == "person_story_link":
                person_story_degrees[person_id] += 1
        if len(endpoint_people) == 2 and layers & set(EXTERNAL_LAYERS):
            external_person_pairs.add(tuple(sorted(endpoint_people)))

    # Current-published category baselines are used only to detect coverage
    # and selection concentration, never as historical importance scores.
    published_chapters = Counter(story_id.split("-", 1)[0] for story_id in production_story_ids)
    max_published_story_degree = max(person_story_degrees.values(), default=1)
    return {
        "entries": entries,
        "chapter_headings": chapter_headings,
        "punctuation": punctuation,
        "people": people,
        "production_story_ids": production_story_ids,
        "links": links,
        "links_by_story": links_by_story,
        "mentions_by_story": mentions_by_story,
        "evidence_ids": evidence_ids,
        "evidence_by_story": evidence_by_story,
        "hg0_graph": hg0_graph,
        "hg0_nodes": hg0_nodes,
        "person_layer_counts": person_layer_counts,
        "person_story_degrees": person_story_degrees,
        "person_graph_degrees": person_graph_degrees,
        "external_person_pairs": external_person_pairs,
        "published_chapters": published_chapters,
        "max_published_story_degree": max_published_story_degree,
    }


def _text_signal(text: str, terms: Iterable[str]) -> list[str]:
    return sorted({term for term in terms if term and term in text})


def make_candidate_record(context: Mapping[str, Any], story_id: str) -> dict[str, Any]:
    entries = context["entries"]
    entry = entries[story_id]
    parsed = parse_entry(entry)
    main_text = parsed["main_text"]
    annotation_text = parsed["annotation_text"]
    searchable_text = main_text + "\n" + annotation_text
    punc = context["punctuation"].get(story_id, {})
    links = sorted(context["links_by_story"].get(story_id, []), key=lambda row: str(row.get("id", "")))
    person_ids = unique(link.get("person_id") for link in links if link.get("person_id") in context["people"])
    evidence_ids = unique(
        [evidence_id for link in links for evidence_id in link.get("evidence_ids", [])]
        + [evidence.get("id") for evidence in context["evidence_by_story"].get(story_id, [])]
    )
    link_ids = unique(link.get("id") for link in links)
    reviewed_links = [link for link in links if link.get("review_status") == "reviewed"]
    candidate_links = [link for link in links if link.get("review_status") != "reviewed"]
    mention_rows = context["mentions_by_story"].get(story_id, [])
    unresolved_mentions = [
        mention for mention in mention_rows
        if not isinstance(mention.get("person_id"), str) or mention.get("person_id") not in context["people"]
    ]
    exact_identity_surfaces = unique(
        mention.get("surface") for mention in mention_rows
        if isinstance(mention.get("person_id"), str) and mention.get("person_id") in context["people"]
    )
    chapter = story_id.split("-", 1)[0]
    layer_counts = context["person_layer_counts"]
    coverage_gaps: list[str] = []
    for layer in EXTERNAL_LAYERS:
        if person_ids and not any(layer_counts[person_id].get(layer, 0) for person_id in person_ids):
            coverage_gaps.append(layer)
    pair_count = 0
    missing_external_pair_count = 0
    for index, left in enumerate(person_ids):
        for right in person_ids[index + 1:]:
            pair_count += 1
            if tuple(sorted((left, right))) not in context["external_person_pairs"]:
                missing_external_pair_count += 1
    person_external_layers = sorted({
        layer
        for person_id in person_ids
        for layer in EXTERNAL_LAYERS
        if layer_counts[person_id].get(layer, 0)
    })
    signals = {
        "office_terms": _text_signal(searchable_text, OFFICE_TERMS),
        "event_terms": _text_signal(searchable_text, EVENT_TERMS),
        "temporal_terms": _text_signal(searchable_text, TEMPORAL_TERMS),
        "family_terms": _text_signal(searchable_text, FAMILY_TERMS),
        "location_terms": _text_signal(searchable_text, LOCATION_TERMS),
    }
    ontology_clues = {
        name: _text_signal(searchable_text, terms)
        for name, terms in ONTOLOGY_CLUES.items()
        if _text_signal(searchable_text, terms)
    }
    # A candidate Story that has a non-disputed canonical witness and at least
    # one resolved PersonStory route is reviewable.  Reader publication is a
    # later gate and is intentionally not treated as eligibility here.
    rejection_reasons: list[str] = []
    if story_id in context["production_story_ids"]:
        rejection_reasons.append("already_in_published_production_scope")
    if not (ROOT / parsed["source_path"]).is_file():
        rejection_reasons.append("canonical_source_missing")
    if not parsed["source_sha256"]:
        rejection_reasons.append("canonical_source_hash_missing")
    if not punc:
        rejection_reasons.append("punctuation_review_record_missing")
    elif punc.get("status") == "disputed":
        rejection_reasons.append("punctuation_record_disputed")
    if not person_ids:
        rejection_reasons.append("no_resolved_production_person_path")
    if not evidence_ids:
        rejection_reasons.append("no_local_evidence_reference")
    eligible = not rejection_reasons

    evidence_quality = bounded(
        (0.45 if punc.get("status") == "candidate" else 0.0)
        + (0.30 if reviewed_links else 0.0)
        + (0.15 if evidence_ids else 0.0)
        + (0.10 if parsed["source_sha256"] else 0.0)
    )
    underrepresented_chapter = 1.0 / max(1, context["published_chapters"].get(chapter, 0))
    underrepresented_chapter = bounded(min(1.0, underrepresented_chapter * 8.0))
    person_degree_mean = (
        sum(context["person_story_degrees"].get(person_id, 0) for person_id in person_ids) / len(person_ids)
        if person_ids else 0.0
    )
    degree_signal = bounded(1.0 - person_degree_mean / max(1, context["max_published_story_degree"]))
    structural_bridge = bounded(
        0.45 * log_norm(max(0, len(person_ids) - 1), 4)
        + 0.35 * log_norm(missing_external_pair_count, 3)
        + 0.20 * log_norm(len(person_external_layers), len(EXTERNAL_LAYERS))
    )
    external_layer_value = bounded(
        0.65 * log_norm(len(person_external_layers), len(EXTERNAL_LAYERS))
        + 0.35 * log_norm(len(set(coverage_gaps) & set(EXTERNAL_LAYERS)), len(EXTERNAL_LAYERS))
    )
    temporal_value = bounded(
        0.55 * log_norm(len(signals["temporal_terms"]) + len(signals["event_terms"]), 8)
        + 0.45 * log_norm(sum(layer_counts[p].get("temporal", 0) for p in person_ids), 8)
    )
    coverage_value = bounded(
        0.55 * log_norm(sum(3 if layer in HIGH_PRIORITY_LAYERS else 1 for layer in coverage_gaps), 12)
        + 0.25 * underrepresented_chapter
        + 0.20 * degree_signal
    )
    graph_score = bounded(
        0.38 * structural_bridge
        + 0.25 * external_layer_value
        + 0.20 * temporal_value
        + 0.17 * bounded(1.0 - degree_signal)
    )
    coverage_score = bounded(
        0.58 * coverage_value
        + 0.18 * evidence_quality
        + 0.14 * underrepresented_chapter
        + 0.10 * bounded(log_norm(len(ontology_clues), 4))
    )
    model_proxy_score = bounded(
        0.60 * bounded(person_degree_mean / max(1, context["max_published_story_degree"]))
        + 0.25 * bounded(sum(context["person_graph_degrees"].get(p, 0) for p in person_ids) / max(1, len(person_ids) * 20))
        + 0.15 * bounded(len(person_ids) / 4)
    )
    independent_signals: list[str] = []
    if evidence_quality >= 0.75:
        independent_signals.append("qualified_local_source_and_evidence")
    if underrepresented_chapter >= 0.35:
        independent_signals.append("underrepresented_chapter")
    if signals["event_terms"]:
        independent_signals.append("explicit_event_or_political_surface")
    if signals["office_terms"]:
        independent_signals.append("explicit_office_surface")
    if signals["family_terms"]:
        independent_signals.append("family_or_marriage_surface")
    if signals["location_terms"]:
        independent_signals.append("location_surface")
    if ontology_clues:
        independent_signals.append("possible_ontology_gap_surface")
    if unresolved_mentions:
        independent_signals.append("reviewable_non_production_identity_surface")
    independent_score = bounded(
        0.28 * evidence_quality
        + 0.18 * underrepresented_chapter
        + 0.17 * log_norm(len(signals["event_terms"]), 4)
        + 0.13 * log_norm(len(signals["office_terms"]), 4)
        + 0.12 * log_norm(len(signals["family_terms"]), 5)
        + 0.07 * log_norm(len(signals["location_terms"]), 4)
        + 0.05 * log_norm(len(ontology_clues), 4)
    )
    return {
        "story_id": story_id,
        "chapter": chapter,
        "chapter_heading": context["chapter_headings"].get(chapter, chapter),
        "global_ordinal": parsed["global_ordinal"],
        "source": {
            "path": parsed["source_path"],
            "sha256": parsed["source_sha256"],
            "main_text_length": len(main_text),
            "annotation_count": len(parsed["annotation_ids"]),
            "source_witness_status": str(entry.get("primary_witness_status", "unknown")),
        },
        "publication_boundary": {
            "in_published_scope": story_id in context["production_story_ids"],
            "production_scope": "published_story_scope",
            "current_status": "out_of_scope_research_boundary",
        },
        "person_connections": {
            "production_person_ids": person_ids,
            "production_person_names": [context["people"][person_id].get("canonical_name") for person_id in person_ids],
            "reviewed_link_count": len(reviewed_links),
            "candidate_link_count": len(candidate_links),
            "link_ids": link_ids,
            "evidence_ids": evidence_ids,
            "source_layers": sorted({layer for link in links for layer in source_layers_for_link(link)}),
            "unresolved_or_non_production_mention_count": len(unresolved_mentions),
            "identity_surfaces": exact_identity_surfaces,
        },
        "evidence": {
            "local_evidence_count": len(evidence_ids),
            "local_evidence_ids": evidence_ids,
            "punctuation_status": punc.get("status"),
            "punctuation_review_status": punc.get("review_status"),
            "evidence_quality": round(evidence_quality, 8),
        },
        "signals": signals,
        "ontology_clues": ontology_clues,
        "coverage": {
            "missing_layers_for_connected_persons": sorted(coverage_gaps),
            "person_external_layers": person_external_layers,
            "underrepresented_chapter_signal": round(underrepresented_chapter, 8),
            "person_degree_signal": round(degree_signal, 8),
        },
        "structural": {
            "person_count": len(person_ids),
            "person_pair_count": pair_count,
            "missing_external_pair_count": missing_external_pair_count,
            "structural_bridge_value": round(structural_bridge, 8),
            "external_layer_value": round(external_layer_value, 8),
        },
        "scores": {
            "graph_guided_score": round(graph_score, 8),
            "coverage_guided_score": round(coverage_score, 8),
            "model_proxy_score": round(model_proxy_score, 8),
            "counter_model_independent_score": round(independent_score, 8),
            "temporal_value": round(temporal_value, 8),
            "coverage_value": round(coverage_value, 8),
        },
        "independent_value_signals": independent_signals,
        "model_proxy_policy": "ML0 has no Story-level ranking output; this diagnostic proxy uses current published PersonStory and HG0 Person incidence only. It is not a neural model score or historical importance score.",
        "eligible": eligible,
        "rejection_reasons": sorted(rejection_reasons),
    }


def source_hashes() -> dict[str, str]:
    paths = {
        "h0c_facts": H0C_FACTS_PATH,
        "h0c_graph": H0C_GRAPH_PATH,
        "h0c_participant_freeze": H0C_PARTICIPANT_PATH,
        "h0c_protection": H0C_PROTECTION_PATH,
        "hg0_graph": HG0_GRAPH_PATH,
        "hg0_universe": HG0_UNIVERSE_PATH,
        "hg0_ontology": HG0_ONTOLOGY_PATH,
        "hg0_audit": HG0_AUDIT_PATH,
        "hg0_bias": HG0_BIAS_PATH,
        "hg0_protection": HG0_PROTECTION_PATH,
        "ml0_dataset": ML0_DATASET_PATH,
        "ml0_bias": ML0_BIAS_PATH,
        "ml0_recommendation": ML0_RECOMMENDATION_PATH,
        "ml0_experiment": ML0_EXPERIMENT_PATH,
        "ml0_metrics": ML0_METRICS_PATH,
        "ml0_gnn": ML0_GNN_PATH,
        "ml0_ablation": ML0_ABLATION_PATH,
        "ml0_link": ML0_LINK_PATH,
        "ml0_temporal": ML0_TEMPORAL_PATH,
        "ml0_protection": ML0_PROTECTION_PATH,
        "person_story_links": LINKS_PATH,
        "corpus_index": CORPUS_PATH,
        "punctuation": PUNCTUATION_PATH,
        "people": PEOPLE_PATH,
    }
    return {name: sha256_file(path) for name, path in paths.items()}


def hashable_selection_records(records: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "story_id": str(row.get("story_id")),
            "selection_mode": str(row.get("selection_mode")),
            "selection_rank": int(row.get("selection_rank", 0)),
            "global_rank": int(row.get("global_rank", 0)),
            "selection_score": row.get("selection_score"),
            "candidate_pool_hash": str(row.get("candidate_pool_hash")),
        }
        for row in records
    ]
