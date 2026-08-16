#!/usr/bin/env python3
"""Re-open the frozen X1.1/X1.2A punctuation backlog with S1 evidence.

This stage is deliberately conservative.  Jianshu can clear the former
editorial-reference bottleneck, but it cannot turn an underspecified X1.2A
candidate into a canonical fact or resolve an ambiguous title by itself.
"""

from __future__ import annotations

from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys

from s1_jianshu_common import (
    ALIGNMENT_PATH,
    CACHE_ROOT,
    X1_2A_FACT_REVIEW_PATH,
    X1_2A_PERSON_REVIEW_PATH,
    X1_2A_STORY_REVIEW_PATH,
    X1_SELECTION_PATH,
    discover_payloads,
    load_story_records,
    protected_s1_input_hashes,
    read_json,
    relative_path,
    sha256_file,
    stable_id,
    write_json,
    x1_selection_by_story,
)


ROOT = Path(__file__).resolve().parents[1]
BACKLOG_OUTPUT = Path("data/derived/s1-jianshu-backlog-reresolution.json")
MATERIALIZATION_OUTPUT = Path("data/derived/s1-jianshu-materialization-manifest.json")
X1_2A_MATERIALIZATION_PATH = Path("data/derived/x1-2a-materialization-manifest.json")
X1_2A_CANONICAL_PATH = Path("data/derived/x1-2a-canonical-facts.json")
X1_2P_DEPENDENCY_PATH = Path("data/derived/x1-2p-dependency-audit.json")
GLYPH_AUDIT_PATH = Path("data/derived/s1-jianshu-glyph-audit.json")
STRUCTURE_AUDIT_PATH = Path("data/derived/s1-jianshu-structure-audit.json")
HISTORICAL_ASSERTIONS_PATH = Path("data/derived/s1-jianshu-historical-assertions.json")
SOURCE_CITATIONS_PATH = Path("data/derived/s1-jianshu-source-citations.json")


def clean_search_text(text: str) -> str:
    return re.sub(r"\s+", "", text).replace("�", "").replace("●", "")


def pdf_fallback_lookup(story_ids: set[str], glyph_issues: list[dict]) -> dict[str, list[dict]]:
    """Use the text-bearing PDF only for selected glyph-affected Stories."""

    payload = discover_payloads()["pdf"]
    terms_by_story: defaultdict[str, set[str]] = defaultdict(set)
    for issue in glyph_issues:
        story_id = issue.get("story_id")
        if story_id not in story_ids:
            continue
        context = str(issue.get("context", ""))
        # A few characters around the anomaly make a stable page-search key;
        # the PDF itself remains the verification source for the full reading.
        runs = re.findall(r"[\u3400-\u9fff]{3,8}", context)
        for run in runs:
            terms_by_story[story_id].add(run)
    if not terms_by_story:
        return {}
    try:
        completed = subprocess.run(
            ["pdftotext", "-layout", str(payload), "-"],
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
        )
        if completed.returncode != 0:
            return {story_id: [{"status": "unavailable", "reason": completed.stderr.strip()}] for story_id in terms_by_story}
    except (FileNotFoundError, subprocess.SubprocessError) as exc:
        return {story_id: [{"status": "unavailable", "reason": str(exc)}] for story_id in terms_by_story}
    pages = completed.stdout.split("\f")
    result: defaultdict[str, list[dict]] = defaultdict(list)
    for story_id, terms in sorted(terms_by_story.items()):
        for term in sorted(terms, key=lambda value: (-len(value), value)):
            normalized_term = clean_search_text(term)
            if len(normalized_term) < 3:
                continue
            for page_number, page in enumerate(pages, start=1):
                normalized_page = clean_search_text(page)
                if normalized_term not in normalized_page:
                    continue
                result[story_id].append(
                    {
                        "status": "found",
                        "term": term,
                        "physical_page": page_number,
                        "excerpt": " ".join(page.split())[:420],
                        "source_id": "shishuo-jianshu-yujiaxi-local-pdf",
                    }
                )
                break
        if not result[story_id]:
            result[story_id].append({"status": "not_found", "source_id": "shishuo-jianshu-yujiaxi-local-pdf"})
    compact = {story_id: sorted(rows, key=lambda row: (row.get("physical_page", 0), row.get("term", ""))) for story_id, rows in sorted(result.items())}
    write_json(CACHE_ROOT / "pdf-fallback-review.json", {
        "schema": "s1-jianshu-pdf-fallback-review-1",
        "pdf_sha256": sha256_file(relative_path(payload) if payload.is_relative_to(ROOT) else Path(relative_path(payload))),
        "stories": compact,
    })
    return compact


def assertion_index() -> dict[str, list[dict]]:
    document = read_json(HISTORICAL_ASSERTIONS_PATH)
    index: defaultdict[str, list[dict]] = defaultdict(list)
    for row in document.get("records", []):
        index[str(row.get("story_id"))].append(row)
    return index


def main() -> int:
    try:
        selection = x1_selection_by_story()
        selection_ids = set(selection)
        alignment = read_json(ALIGNMENT_PATH)
        alignment_by_story = {str(row["story_id"]): row for row in alignment.get("records", [])}
        stories = {str(row["story_id"]): row for row in load_story_records()}
        x1_2a_story = {str(row["story_id"]): row for row in read_json(X1_2A_STORY_REVIEW_PATH).get("records", [])}
        x1_2a_fact = {str(row["review_item_id"]): row for row in read_json(X1_2A_FACT_REVIEW_PATH).get("records", [])}
        x1_2a_person = {str(row["review_item_id"]): row for row in read_json(X1_2A_PERSON_REVIEW_PATH).get("records", [])}
        x1_2p_dependency = read_json(X1_2P_DEPENDENCY_PATH)
        glyph = read_json(GLYPH_AUDIT_PATH)
        glyph_by_story: defaultdict[str, list[dict]] = defaultdict(list)
        for row in glyph.get("issues", []):
            if row.get("story_id"):
                glyph_by_story[str(row["story_id"])].append(row)
        fallback = pdf_fallback_lookup(selection_ids, glyph.get("issues", []))
        assertions = assertion_index()

        story_rows = []
        for story_id in sorted(selection_ids):
            align = alignment_by_story.get(story_id, {})
            old = x1_2a_story.get(story_id, {})
            alignment_class = align.get("alignment_class", "unmatched")
            punctuation_accepted = alignment_class in {"exact", "near_exact", "known_minor_variant"} and bool(align.get("editorial_segmentation_available"))
            issue_rows = glyph_by_story.get(story_id, [])
            fallback_rows = fallback.get(story_id, [])
            glyph_status = "clean"
            if issue_rows:
                glyph_status = "fallback_verified" if any(row.get("status") == "found" for row in fallback_rows) else "review_required"
            participant_gate = old.get("participant_gate", {})
            blocking = []
            if not punctuation_accepted:
                blocking.append("jianshu_alignment_or_segmentation_unresolved")
            if glyph_status == "review_required":
                blocking.append("glyph_fallback_unresolved")
            if participant_gate.get("status") in {"deferred_until_story_projection", "not_evaluated"}:
                blocking.append("participant_review_not_evaluated")
            story_rows.append(
                {
                    "review_item_id": stable_id("s1-story-reresolution", story_id),
                    "story_id": story_id,
                    "selection_epoch": "X1.1",
                    "selection_mode": selection[story_id].get("selection_mode"),
                    "selection_provenance": selection[story_id],
                    "x1_2a_review_status": old.get("review_status"),
                    "x1_2p_status": "unresolved",
                    "jianshu_alignment": {
                        "alignment_class": alignment_class,
                        "source_locator": align.get("source_locator"),
                        "editorial_segmentation_available": align.get("editorial_segmentation_available", False),
                        "meaningful_variant": align.get("meaningful_variant", False),
                    },
                    "glyph_status": glyph_status,
                    "glyph_issue_ids": [row["issue_id"] for row in issue_rows],
                    "pdf_fallback": fallback_rows,
                    "punctuation_gate": "accepted_by_s1_jianshu_policy" if punctuation_accepted else "unresolved",
                    "review_status": "accepted" if punctuation_accepted else "unresolved",
                    "production_eligibility": "still_unresolved" if blocking else "production_eligible",
                    "eligible_for_rematerialization": False,
                    "blocking_reasons": blocking,
                    "review_reason": (
                        "The aligned Jianshu EPUB supplies scholarly editorial segmentation under the prospective S1 policy; no canonical characters are changed. "
                        + ("Participant semantics still require the existing review gate." if blocking else "All existing gates evaluated for this overlay pass.")
                    )
                    if punctuation_accepted
                    else "The Jianshu alignment/segmentation evidence is not yet sufficient to clear the editorial gate.",
                    "evidence_refs": [
                        {
                            "source_id": "shishuo-jianshu-yujiaxi-local-epub",
                            "source_locator": align.get("source_locator"),
                            "alignment_id": align.get("alignment_id"),
                        }
                    ],
                }
            )

        fact_rows = []
        for dependency in sorted(x1_2p_dependency.get("fact_records", []), key=lambda row: row.get("dependency_id", "")):
            review = x1_2a_fact.get(str(dependency.get("source_review_item_id")), {})
            story_id = str(dependency.get("story_id"))
            story_review = next(row for row in story_rows if row["story_id"] == story_id)
            candidates = [row for row in assertions.get(story_id, []) if dependency.get("fact_layer") in row.get("candidate_fact_types", [])]
            explicit = [row for row in candidates if row.get("modality") in {"explicit", "probable"} and row.get("layer") == "jianshu_note"]
            if story_review["punctuation_gate"] == "accepted_by_s1_jianshu_policy":
                dependency_state = "independent_unresolved"
                reason = "Jianshu clears the editorial reference dependency, but the X1.2A candidate still lacks a fully specified endpoint/semantic claim that can be canonicalized safely."
            else:
                dependency_state = "blocked_by_story_punctuation"
                reason = "The aligned Story has not cleared the Jianshu editorial gate; the original historical review remains unresolved."
            fact_rows.append(
                {
                    "dependency_id": dependency["dependency_id"],
                    "source_review_item_id": dependency.get("source_review_item_id"),
                    "story_id": story_id,
                    "fact_layer": dependency.get("fact_layer"),
                    "selection_mode": review.get("selection_mode"),
                    "selection_provenance": review.get("selection_provenance"),
                    "x1_2a_review_status": review.get("review_status"),
                    "x1_2p_primary_blocker": dependency.get("primary_blocker"),
                    "s1_dependency_state": dependency_state,
                    "jianshu_assertion_ids": [row["assertion_id"] for row in candidates[:30]],
                    "explicit_jianshu_note_ids": [row["assertion_id"] for row in explicit[:30]],
                    "candidate_assertion_count": len(candidates),
                    "review_status": "unresolved",
                    "materialization_status": "not_materialized",
                    "review_reason": reason,
                    "evidence_ids": sorted(set(dependency.get("evidence_ids", []))),
                }
            )

        identity_rows = []
        for review in sorted(x1_2a_person.values(), key=lambda row: row.get("review_item_id", "")):
            if review.get("review_status") != "unresolved":
                continue
            story_id = str(review.get("story_id"))
            identity_rows.append(
                {
                    "review_item_id": review.get("review_item_id"),
                    "story_id": story_id,
                    "surface": review.get("surface"),
                    "selection_mode": review.get("selection_mode"),
                    "selection_provenance": review.get("selection_provenance"),
                    "x1_2a_review_status": review.get("review_status"),
                    "jianshu_story_alignment": alignment_by_story.get(story_id, {}).get("alignment_class"),
                    "identity_dependency": "independent_identity_ambiguity",
                    "candidate_alias_matches": [row["candidate_id"] for row in read_json(Path("data/derived/s1-jianshu-alias-candidates.json")).get("records", []) if row.get("surface") == review.get("surface")][:20],
                    "review_status": "unresolved",
                    "resolved_person_id": None,
                    "new_person_created": False,
                    "materialization_status": "not_materialized",
                    "review_reason": "Jianshu provides contextual discussion but no sufficiently secure occurrence-level identity for this generic title/surface; the existing title-collision safeguard remains in force.",
                    "evidence_ids": review.get("evidence_ids", []),
                }
            )

        old_materialization = read_json(X1_2A_MATERIALIZATION_PATH)
        old_canonical = read_json(X1_2A_CANONICAL_PATH)
        source_hashes = {
            "x1_1_selection": sha256_file(X1_SELECTION_PATH),
            "x1_2a_review_manifest": sha256_file(Path("data/derived/x1-2a-review-manifest.json")),
            "x1_2a_story_review": sha256_file(X1_2A_STORY_REVIEW_PATH),
            "x1_2a_fact_review": sha256_file(X1_2A_FACT_REVIEW_PATH),
            "x1_2a_person_review": sha256_file(X1_2A_PERSON_REVIEW_PATH),
            "x1_2a_materialization": sha256_file(X1_2A_MATERIALIZATION_PATH),
            "x1_2a_canonical_facts": sha256_file(X1_2A_CANONICAL_PATH),
            "x1_2p_dependency": sha256_file(X1_2P_DEPENDENCY_PATH),
            "alignment": sha256_file(ALIGNMENT_PATH),
            "structure_audit": sha256_file(STRUCTURE_AUDIT_PATH),
            "glyph_audit": sha256_file(GLYPH_AUDIT_PATH),
        }
        materialization = {
            "schema": "s1-jianshu-materialization-manifest-1",
            "stage": "S1.4",
            "source_hashes": source_hashes,
            "canonical_story_additions": [],
            "canonical_person_additions": [],
            "canonical_fact_additions": [],
            "canonical_entity_additions": [],
            "release_scope": "no new canonical records; existing X1.2A extension is protected",
            "protected_x1_2a_materialization_sha256": sha256_file(X1_2A_MATERIALIZATION_PATH),
            "protected_x1_2a_canonical_fact_count": len(old_canonical.get("fact_index", [])),
            "no_ml_write_back": True,
            "no_new_story_selection": True,
            "policy": "Only accepted records with a complete non-punctuation review may be released; S1 adds no release when participant/identity gates remain open.",
        }
        write_json(MATERIALIZATION_OUTPUT, materialization)
        result = {
            "schema": "s1-jianshu-backlog-reresolution-1",
            "stage": "S1.4",
            "source_hashes": source_hashes,
            "frozen_scope": {
                "selection_epoch": "X1.1",
                "story_count": len(selection_ids),
                "story_ids": sorted(selection_ids),
                "new_story_selection": False,
            },
            "stories": story_rows,
            "facts": fact_rows,
            "identities": identity_rows,
            "counts": {
                "stories_total": len(story_rows),
                "stories_punctuation_accepted": sum(row["punctuation_gate"] == "accepted_by_s1_jianshu_policy" for row in story_rows),
                "stories_production_eligible": sum(row["production_eligibility"] == "production_eligible" for row in story_rows),
                "stories_materialized": 0,
                "stories_still_unresolved": sum(row["production_eligibility"] == "still_unresolved" for row in story_rows),
                "facts_total": len(fact_rows),
                "facts_accepted": 0,
                "facts_unresolved": len(fact_rows),
                "facts_rejected": 0,
                "identities_total": len(identity_rows),
                "identities_existing_person_mappings": 0,
                "identities_new_persons": 0,
                "identities_unresolved": len(identity_rows),
                "identities_rejected": 0,
            },
            "existing_x1_2a_extension": {
                "materialization_manifest_sha256": sha256_file(X1_2A_MATERIALIZATION_PATH),
                "canonical_fact_index_sha256": sha256_file(X1_2A_CANONICAL_PATH),
                "canonical_fact_count": len(old_canonical.get("fact_index", [])),
                "preserved_without_mutation": True,
            },
            "source_value": {
                "pdf_fallback_story_count": sum(bool(rows) for rows in fallback.values()),
                "historical_assertion_count": len(read_json(HISTORICAL_ASSERTIONS_PATH).get("records", [])),
                "citation_count": len(read_json(SOURCE_CITATIONS_PATH).get("records", [])),
                "alias_candidate_count": len(read_json(Path("data/derived/s1-jianshu-alias-candidates.json")).get("records", [])),
                "policy_result": "Jianshu clears the former independent-editorial-reference requirement for aligned Stories, but does not erase participant, identity, or fact-semantic review gates.",
            },
            "policy": {
                "selection_channel_is_not_textual_evidence": True,
                "minor_variants_do_not_overwrite_canonical_text": True,
                "meaningful_variants_remain_review_required": True,
                "candidate_assertions_are_not_canonical_facts": True,
                "quoted_sources_commentary_and_canonical_facts_remain_distinct": True,
            },
        }
        write_json(BACKLOG_OUTPUT, result)
        print(result["counts"])
        return 0
    except Exception as exc:
        print(f"S1 backlog re-resolution failed: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
