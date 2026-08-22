#!/usr/bin/env python3
"""Deterministic lexical search over the complete local Shishuo research corpus.

This is a research index only.  It never creates PersonStory links and never
reads generated/model-output directories.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Iterable, Mapping

try:
    from .build_ds2_1a_person_research import (
        OUTPUT_PATH as PERSON_SURFACE_PATH,
        ROOT,
        SHISHUO_SEARCH_OUTPUT_PATH,
        compact_text,
        fold,
        source_excerpt,
    )
except ImportError:  # direct execution: python scripts/search_shishuo_research.py
    from build_ds2_1a_person_research import (  # type: ignore
        OUTPUT_PATH as PERSON_SURFACE_PATH,
        ROOT,
        SHISHUO_SEARCH_OUTPUT_PATH,
        compact_text,
        fold,
        source_excerpt,
    )


def read_json(root: Path, relative: Path) -> Any:
    return json.loads((root / relative).read_text(encoding="utf-8"))


def ngram_terms(query: str) -> list[str]:
    compact = compact_text(query)
    terms = [compact] if compact else []
    for width in (3, 2):
        terms.extend(compact[index : index + width] for index in range(len(compact) - width + 1))
    return sorted(set(term for term in terms if term), key=lambda value: (-len(value), value))


def person_link_status(
    story_id: str,
    person_id: str | None,
    links_by_story: Mapping[str, list[Mapping[str, Any]]],
) -> str | None:
    links = links_by_story.get(story_id, [])
    if person_id is not None:
        links = [link for link in links if str(link.get("person_id")) == person_id]
    if not links:
        return None
    statuses = {str(link.get("review_status")) for link in links}
    if "reviewed" in statuses:
        return "reviewed"
    if "candidate" in statuses:
        return "candidate"
    return sorted(statuses)[0] if statuses else None


def person_search_terms(surface: Mapping[str, Any], person_id: str | None) -> list[str]:
    if person_id is None:
        return []
    person = surface.get("people", {}).get(person_id)
    if not isinstance(person, Mapping):
        raise ValueError(f"unknown Person: {person_id}")
    terms = [str(person.get("canonical_name", ""))]
    for alias in person.get("reviewed_context", {}).get("aliases", []):
        if isinstance(alias, Mapping) and alias.get("surface"):
            terms.append(str(alias["surface"]))
    return sorted(set(term for term in terms if term), key=lambda value: (-len(value), value))


def score_layer(text: str, query: str, entity_terms: Iterable[str], linked: bool) -> int:
    folded_text = fold(compact_text(text))
    folded_query = fold(compact_text(query))
    if not folded_query or folded_query not in folded_text:
        terms = ngram_terms(query)
        overlap = sum(1 for term in terms if len(term) > 1 and fold(term) in folded_text)
        if overlap == 0:
            return 0
        score = overlap * 4
    else:
        score = 100 + len(folded_query) * 3
    for term in entity_terms:
        if fold(compact_text(term)) in folded_text:
            score += 12
    if linked:
        score += 20
    return score


def search_records(
    records: Iterable[Mapping[str, Any]],
    query: str,
    *,
    links: Iterable[Mapping[str, Any]] = (),
    surface: Mapping[str, Any] | None = None,
    person_id: str | None = None,
    layers: set[str] | None = None,
    chapter: str | None = None,
    exclude_stories: set[str] | None = None,
    scope: str = "all",
    top_k: int = 10,
) -> dict[str, Any]:
    """Return compact top-k layer hits while scanning every eligible record."""

    if not compact_text(query):
        raise ValueError("query must contain searchable text")
    if top_k < 1:
        raise ValueError("top_k must be positive")
    if top_k > 50:
        raise ValueError("top_k must not exceed 50")
    layers = layers or {"main_text", "liu_annotation"}
    invalid_layers = layers - {"main_text", "liu_annotation"}
    if invalid_layers:
        raise ValueError(f"unsupported search layers: {sorted(invalid_layers)}")
    exclude_stories = exclude_stories or set()
    links_by_story: dict[str, list[Mapping[str, Any]]] = {}
    for link in links:
        if isinstance(link, Mapping):
            links_by_story.setdefault(str(link.get("entry_id")), []).append(link)
    entity_terms = person_search_terms(surface or {}, person_id) if person_id else []

    candidates: list[tuple[int, str, str, dict[str, Any]]] = []
    raw_match_count = 0
    for record in records:
        story_id = str(record.get("story_id", ""))
        if not story_id or story_id in exclude_stories:
            continue
        if chapter and str(record.get("chapter_id")) != chapter:
            continue
        if scope != "all" and record.get("publication_scope") != scope:
            continue
        link_status = person_link_status(story_id, person_id, links_by_story)
        linked = link_status is not None
        layers_to_search: list[tuple[str, str, str]] = []
        if "main_text" in layers:
            layers_to_search.append(("main_text", str(record.get("main_text", "")), f"shishuo-evidence-{story_id}-main"))
        if "liu_annotation" in layers:
            for annotation in record.get("liu_annotations", []):
                if isinstance(annotation, Mapping):
                    evidence_ids = annotation.get("evidence_ids", [])
                    evidence_ref = str(evidence_ids[0]) if evidence_ids else ""
                    layers_to_search.append(("liu_annotation", str(annotation.get("text", "")), evidence_ref))
        for source_layer, text, evidence_ref in layers_to_search:
            score = score_layer(text, query, entity_terms, linked)
            if score <= 0:
                continue
            raw_match_count += 1
            hit = {
                "story_id": story_id,
                "chapter": record.get("chapter_heading"),
                "chapter_id": record.get("chapter_id"),
                "source_layer": source_layer,
                "evidence_ref": evidence_ref,
                "excerpt": source_excerpt(text, (query, *entity_terms)),
                "person_link_status": link_status,
                "existing_person_link": linked,
                "publication_scope": record.get("publication_scope"),
                "score": score,
            }
            candidates.append((score, story_id, source_layer, hit))
    candidates.sort(key=lambda item: (-item[0], item[1], item[2], str(item[3].get("evidence_ref", ""))))
    return {
        "query": query,
        "raw_match_count": raw_match_count,
        "hits": [item[3] for item in candidates[:top_k]],
    }


def query(root: Path = ROOT, **kwargs: Any) -> dict[str, Any]:
    search_document = read_json(root, SHISHUO_SEARCH_OUTPUT_PATH)
    surface = read_json(root, PERSON_SURFACE_PATH)
    links_document = read_json(root, Path("data/derived/person-story-links.json"))
    return search_records(
        search_document.get("records", []),
        links=links_document.get("links", []),
        surface=surface,
        **kwargs,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--query", required=True)
    parser.add_argument("--top-k", type=int, default=10)
    parser.add_argument("--person")
    parser.add_argument("--layer", action="append", choices=("main_text", "liu_annotation"))
    parser.add_argument("--chapter")
    parser.add_argument("--exclude-story", action="append", default=[])
    parser.add_argument("--scope", choices=("all", "published", "research_only"), default="all")
    args = parser.parse_args()
    result = query(
        ROOT,
        query=args.query,
        person_id=args.person,
        layers=set(args.layer) if args.layer else None,
        chapter=args.chapter,
        exclude_stories=set(args.exclude_story),
        scope=args.scope,
        top_k=args.top_k,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
