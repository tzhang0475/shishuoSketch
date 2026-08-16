#!/usr/bin/env python3
"""Build the X1.2A evidence-review manifest.

The decisions in this file are intentionally conservative and explicit.  The
X1.1 ranking is retained as selection provenance only; it is never consulted
as evidence for accepting a historical fact.
"""

from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
from typing import Any, Mapping

try:
    from scripts.x1_2a_common import (
        EPOCH,
        FACT_REVIEW_PATH,
        ONTOLOGY_REVIEW_PATH,
        PERSON_REVIEW_PATH,
        REVIEW_MANIFEST_PATH,
        STORY_REVIEW_PATH,
        X1_1_INPUTS,
        action_rows,
        all_production_ids,
        candidate_by_story,
        evidence_by_id,
        evidence_ref,
        fact_candidates,
        load_x1_1,
        mentions_by_story,
        person_candidates,
        protected_hashes,
        punctuation_by_story,
        read,
        review_by_story,
        selection_by_story,
        sha256_file,
        source_entry,
        stable_id,
        story_selection_provenance,
        unique,
        write,
    )
except ModuleNotFoundError:  # direct execution from scripts/
    from x1_2a_common import (
        EPOCH,
        FACT_REVIEW_PATH,
        ONTOLOGY_REVIEW_PATH,
        PERSON_REVIEW_PATH,
        REVIEW_MANIFEST_PATH,
        STORY_REVIEW_PATH,
        X1_1_INPUTS,
        action_rows,
        all_production_ids,
        candidate_by_story,
        evidence_by_id,
        evidence_ref,
        fact_candidates,
        load_x1_1,
        mentions_by_story,
        person_candidates,
        protected_hashes,
        punctuation_by_story,
        read,
        review_by_story,
        selection_by_story,
        sha256_file,
        source_entry,
        stable_id,
        story_selection_provenance,
        unique,
        write,
    )


ROOT = Path(__file__).resolve().parents[1]


# These are review conclusions, not automatic rules.  Each accepted entry is
# tied below to an exact source-backed semantic shape that the materializer
# knows how to construct.  Everything else remains unresolved or rejected.
ACCEPTED_SERVICE_STORY = "23-rendan-032"
ACCEPTED_OFFICE_STORY = "04-wenxue-080"
ACCEPTED_EVENT_STORIES = {
    "15-zixin-001": "new_event_context",
    "15-zixin-002": "existing_event_context",
    "19-xianyuan-017": "existing_event_context",
    "36-chouxi-001": "existing_event_context",
}

IDENTITY_DECISIONS: dict[tuple[str, str], dict[str, Any]] = {
    ("01-dexing-024", "郗公"): {
        "review_status": "accepted",
        "resolved_person_id": "person-002",
        "canonical_name": "郗鑒",
        "reason": "Liu annotation explicitly identifies 郗公's subject as 郗鑒; the main-text family actions are consistent with the same subject.",
    },
    ("02-yanyu-033", "王丞相"): {
        "review_status": "accepted",
        "resolved_person_id": "person-003",
        "canonical_name": "王導",
        "reason": "The Story-local Liu annotation names 丞相王導 in the immediately related account; this is a local antecedent decision, not a global title alias.",
    },
    ("02-yanyu-033", "丞相"): {
        "review_status": "accepted",
        "resolved_person_id": "person-003",
        "canonical_name": "王導",
        "reason": "The repeated bare title follows the Story's 王丞相 antecedent and the Liu annotation's explicit 王導 identification.",
    },
    ("23-rendan-032", "王公"): {
        "review_status": "accepted",
        "resolved_person_id": "person-003",
        "canonical_name": "王導",
        "reason": "The Liu annotation says 王濛別傳曰丞相王導; the main text makes 王公 the employer of 王長史 and 謝仁祖. This remains Story-local.",
    },
    ("26-qingdi-004", "王公"): {
        "review_status": "accepted",
        "resolved_person_id": "person-003",
        "canonical_name": "王導",
        "reason": "The Story's Liu annotation explicitly supplies 王導 for the otherwise contextual 王公 surface; no global 王公 mapping is introduced.",
    },
    ("05-fangzheng-039", "王丞相"): {
        "review_status": "unresolved",
        "reason": "王敦 is present in the local annotation, but the 王丞相 surface is not given a sufficiently specific local antecedent; title collision remains open.",
    },
    ("05-fangzheng-039", "王公"): {
        "review_status": "unresolved",
        "reason": "The local source contains both 王敦 and contextual 王公 language without a safe occurrence-level resolution.",
    },
    ("04-wenxue-021", "王丞相"): {
        "review_status": "unresolved",
        "reason": "The opening title is a historical attribution with no Story-local reviewed person antecedent; global title resolution is prohibited.",
    },
}


def direct_story_evidence(story_id: str, evidence: Mapping[str, Mapping[str, Any]]) -> list[str]:
    ids = []
    for evidence_id, row in evidence.items():
        locator = row.get("locator", {})
        if isinstance(locator, Mapping) and locator.get("entry_id") == story_id:
            ids.append(evidence_id)
    return sorted(ids)


def fact_decision(row: Mapping[str, Any]) -> dict[str, Any]:
    story_id = str(row["story_id"])
    layer = str(row["fact_layer"])
    key = (story_id, layer)

    if story_id == ACCEPTED_OFFICE_STORY and layer == "office":
        return {
            "review_status": "accepted",
            "review_reason": "The main text explicitly states that 習鑿齒 was appointed 荊州治中; identity and office semantics are secure, while tenure chronology remains unknown.",
            "review_notes": "Accept an Office and OfficeTenure extension plus its held_office_at LocationFact. No date is inferred from 未三十 or from later biography.",
            "materialization_status": "accepted_for_canonical_extension",
            "materialization_kinds": ["office_tenure"],
        }
    if story_id == ACCEPTED_OFFICE_STORY and layer == "geographic":
        return {
            "review_status": "accepted",
            "review_reason": "荊州 is explicitly the jurisdiction named by the office phrase 荊州治中.",
            "review_notes": "Create a historical Location with unknown modern mapping and a typed held_office_at fact; do not flatten this into a generic residence fact.",
            "materialization_status": "accepted_for_canonical_extension",
            "materialization_kinds": ["location_fact"],
        }
    if story_id == ACCEPTED_SERVICE_STORY and layer == "service_political":
        return {
            "review_status": "accepted",
            "review_reason": "The main text explicitly says 王長史 and 謝仁祖 were 王公掾; Liu's local note identifies 王公 as 丞相王導.",
            "review_notes": "Materialize two typed service_under facts for the already canonical Persons 王濛 and 謝尚. This is not a new reviewed Relation and carries no faction interpretation or date.",
            "materialization_status": "accepted_for_canonical_extension",
            "materialization_kinds": ["service_political"],
        }
    if layer == "event" and story_id in ACCEPTED_EVENT_STORIES:
        mode = ACCEPTED_EVENT_STORIES[story_id]
        if mode == "new_event_context":
            return {
                "review_status": "accepted",
                "review_reason": "The Liu annotation explicitly records 齊萬年反 in the local historical account.",
                "review_notes": "Materialize a single event entity and a context-only Story–Event fact with unknown absolute chronology; no PersonParticipation is inferred because the endpoint identity is not production.",
                "materialization_status": "accepted_for_canonical_extension",
                "materialization_kinds": ["event", "event_story_context"],
            }
        return {
            "review_status": "accepted",
            "review_reason": "The local primary/annotation evidence explicitly names the 趙王倫 rebellion, which is represented by the existing 八王之亂 event entity.",
            "review_notes": "Materialize a context-only Story–Event link. The event context is not a hard Story participant interval and does not rewrite H0A.",
            "materialization_status": "accepted_for_canonical_extension",
            "materialization_kinds": ["event_story_context"],
        }
    if layer == "clan":
        return {
            "review_status": "rejected",
            "review_reason": "The candidate is a coverage/surname surface and supplies no explicit clan identity or branch evidence for an accepted endpoint.",
            "review_notes": "Surname, co-occurrence, and model coverage cannot create ClanMembership.",
            "materialization_status": "not_materialized",
            "materialization_kinds": [],
        }
    if layer == "family":
        return {
            "review_status": "unresolved",
            "review_reason": "The source contains a family or marriage surface, but at least one endpoint is non-production or the exact kinship semantics are not safely resolved in the current ontology.",
            "review_notes": "Record missing endpoints for a later review; do not allocate a Person or infer kinship from surname, locality, or co-occurrence.",
            "materialization_status": "not_materialized",
            "materialization_kinds": [],
        }
    if layer == "office":
        return {
            "review_status": "unresolved",
            "review_reason": "An office-like surface is present, but the responsible Person is non-production, title context is ambiguous, or the candidate action does not identify a concrete tenure.",
            "review_notes": "Relative office language is retained as a gap; no absolute year or global title resolution is added.",
            "materialization_status": "not_materialized",
            "materialization_kinds": [],
        }
    if layer == "event":
        return {
            "review_status": "unresolved",
            "review_reason": "The evidence suggests historical background or a named figure, but it does not establish a reusable Event identity and Story context without interpretive expansion.",
            "review_notes": "Background is not automatically EventParticipation; preserve as a review gap.",
            "materialization_status": "not_materialized",
            "materialization_kinds": [],
        }
    if layer == "geographic":
        return {
            "review_status": "unresolved",
            "review_reason": "A place surface is present, but its typed relation to a production Person or Story is not explicit enough for a LocationFact.",
            "review_notes": "Do not turn a travel, office, or contextual place mention into residence or activity without a typed source claim.",
            "materialization_status": "not_materialized",
            "materialization_kinds": [],
        }
    if layer == "service_political":
        return {
            "review_status": "unresolved",
            "review_reason": "The candidate may indicate political or institutional context, but the source does not safely resolve both endpoints into an existing, non-interpretive fact.",
            "review_notes": "No faction, allegiance, or new Relation is inferred. Missing endpoints and relation scope remain explicit gaps.",
            "materialization_status": "not_materialized",
            "materialization_kinds": [],
        }
    if layer == "temporal":
        return {
            "review_status": "rejected",
            "review_reason": "The candidate is a keyword/coverage signal rather than a direct temporal assertion with a bounded interval.",
            "review_notes": "No H0A anchor or H0B constraint is rewritten; unknown remains unknown.",
            "materialization_status": "not_materialized",
            "materialization_kinds": [],
        }
    return {
        "review_status": "unresolved",
        "review_reason": "No safe existing H0C semantic target was established during evidence review.",
        "review_notes": "Retain the candidate as a gap.",
        "materialization_status": "not_materialized",
        "materialization_kinds": [],
    }


def review_story(
    story_id: str,
    selections: Mapping[str, Mapping[str, Any]],
    reviews: Mapping[str, Mapping[str, Any]],
    punctuation: Mapping[str, Mapping[str, Any]],
    evidence: Mapping[str, Mapping[str, Any]],
    production_stories: set[str],
) -> dict[str, Any]:
    source = source_entry(story_id)
    source_evidence = unique(reviews[story_id].get("evidence_ids", []) + direct_story_evidence(story_id, evidence))
    punc = punctuation.get(story_id, {})
    source_ok = bool(source["exists"] and source["sha256"] == reviews[story_id].get("source", {}).get("sha256"))
    punctuation_ok = punc.get("status") == "reviewed" and punc.get("review_status") == "reviewed" and punc.get("punctuation_basis") == "human_reviewed"
    duplicate = story_id in production_stories
    if duplicate:
        overall = "rejected"
        reason = "Story is already in the production scope; X1.1 selection freeze should have excluded it."
    elif not source_ok or not source_evidence:
        overall = "unresolved"
        reason = "Source identity or evidence route failed the integrity gate."
    elif not punctuation_ok:
        overall = "unresolved"
        reason = "Canonical source and Story identity are secure, but the punctuation record remains unreviewed; production Story promotion is blocked."
    else:
        overall = "accepted"
        reason = "Story identity, source, punctuation, and evidence gates passed."
    return {
        "review_item_id": stable_id("x1-2a-story-review", story_id),
        "source_candidate_id": f"{story_id}:ADD_STORY",
        "story_id": story_id,
        "review_type": "story_integrity",
        "selection_provenance": story_selection_provenance(story_id, selections),
        "source": source,
        "source_sha256_verified": source_ok,
        "duplicate_canonical_story": duplicate,
        "evidence_ids": source_evidence,
        "evidence_refs": [evidence_ref(item, evidence) for item in source_evidence],
        "punctuation": {
            "record_id": punc.get("id"),
            "status": punc.get("status"),
            "review_status": punc.get("review_status"),
            "punctuation_basis": punc.get("punctuation_basis"),
            "gate_passed": punctuation_ok,
        },
        "participant_gate": {
            "person_story_is_not_participation": True,
            "status": "deferred_until_story_projection",
            "reason": "X1.2A does not promote PersonStory or Mention rows into hard participation; a future Story projection must review role semantics separately.",
        },
        "review_status": overall,
        "review_reason": reason,
        "review_notes": "The Story may remain a research overlay even when independent source-backed facts are accepted. No canonical source text is edited.",
        "materialization_status": "canonical_story" if overall == "accepted" else "not_materialized",
        "canonical_production_eligible": overall == "accepted",
    }


def review_person(
    row: Mapping[str, Any],
    evidence: Mapping[str, Mapping[str, Any]],
    direct_evidence: Mapping[str, list[str]],
) -> dict[str, Any]:
    key = (str(row["story_id"]), str(row["surface"]))
    decision = dict(IDENTITY_DECISIONS.get(key, {
        "review_status": "unresolved",
        "reason": "No occurrence-level identity evidence is sufficient for a safe existing-Person match or new-Person allocation.",
    }))
    ids = unique(row.get("evidence_ids", []) + direct_evidence.get(str(row["story_id"]), []))
    return {
        **dict(row),
        "evidence_ids": ids,
        "evidence_refs": [evidence_ref(item, evidence) for item in ids],
        "resolved_person_id": decision.get("resolved_person_id"),
        "canonical_name": decision.get("canonical_name"),
        "review_status": decision["review_status"],
        "review_reason": decision["reason"],
        "review_notes": "Accepted identity decisions are Story-local overlay decisions only; they are not written into the global alias index while the parent Story remains outside production.",
        "materialization_status": "deferred_until_story_promotion" if decision["review_status"] == "accepted" else "not_materialized",
        "new_person_created": False,
    }


def review_ontology(ontology: Mapping[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for candidate in sorted(ontology.get("candidates", []), key=lambda row: str(row.get("candidate_relation_semantics"))):
        frequency = int(candidate.get("frequency", 0))
        classification = "possible_new_semantic_type" if frequency >= 3 else "one_off_surface"
        rows.append({
            "review_item_id": stable_id("x1-2a-ontology-review", candidate.get("candidate_relation_semantics")),
            "source_candidate_id": f"ontology:{candidate.get('candidate_relation_semantics')}",
            "review_type": "ontology_gap",
            "candidate_relation_semantics": candidate.get("candidate_relation_semantics"),
            "supporting_story_ids": sorted(candidate.get("supporting_story_ids", [])),
            "evidence_ids": sorted(candidate.get("supporting_evidence_ids", [])),
            "frequency": frequency,
            "classification": classification,
            "review_status": "accepted",
            "review_reason": "The recurring surface pattern is a valid future ontology review target, but the current evidence does not justify a new canonical edge type in X1.2A.",
            "review_notes": "Recommendation only; HG0 ontology remains byte-identical and no new Relation is materialized.",
            "materialization_status": "not_materialized",
            "ontology_change": False,
        })
    return rows


def build() -> dict[str, Any]:
    inputs = load_x1_1()
    selection = inputs["selection_manifest"]
    review = inputs["review_results"]
    ontology = inputs["ontology_gap_candidates"]
    selections = selection_by_story(selection)
    reviews = review_by_story(review)
    pool = candidate_by_story(inputs["candidate_pool"])
    evidence = evidence_by_id()
    punctuation = punctuation_by_story()
    _people, production_stories = all_production_ids()
    direct_evidence = {
        story_id: direct_story_evidence(story_id, evidence)
        for story_id in selections
    }

    story_rows = [
        review_story(story_id, selections, reviews, punctuation, evidence, production_stories)
        for story_id in sorted(selections)
    ]
    person_rows = [review_person(row, evidence, direct_evidence) for row in person_candidates(review, selections)]
    fact_rows = []
    for row in fact_candidates(review, selections):
        decision = fact_decision(row)
        ids = unique(row.get("evidence_ids", []) + direct_evidence.get(str(row["story_id"]), []))
        fact_rows.append({
            **row,
            "evidence_ids": ids,
            "evidence_refs": [evidence_ref(item, evidence) for item in ids],
            **decision,
        })
    ontology_rows = review_ontology(ontology)

    review_items = story_rows + person_rows + fact_rows + ontology_rows
    counts = {
        "story_candidate_count": len(story_rows),
        "person_identity_candidate_count": len(person_rows),
        "fact_candidate_count": len(fact_rows),
        "ontology_gap_candidate_count": len(ontology_rows),
        "review_item_count": len(review_items),
        "story_review_status": dict(sorted(Counter(row["review_status"] for row in story_rows).items())),
        "person_review_status": dict(sorted(Counter(row["review_status"] for row in person_rows).items())),
        "fact_review_status": dict(sorted(Counter(row["review_status"] for row in fact_rows).items())),
        "ontology_review_status": dict(sorted(Counter(row["review_status"] for row in ontology_rows).items())),
        "accepted_fact_materialization_count": sum(row["review_status"] == "accepted" for row in fact_rows),
    }
    if counts["story_candidate_count"] != 20 or counts["person_identity_candidate_count"] != 8 or counts["fact_candidate_count"] != 88 or counts["ontology_gap_candidate_count"] != 7:
        raise ValueError(f"X1.1 review overlay cardinality changed: {counts}")

    source_hashes = {
        "x1_1": {name: sha256_file(path) for name, path in X1_1_INPUTS.items()},
        "protected": protected_hashes(),
    }
    manifest = {
        "schema": 1,
        "stage": "x1-2a-review-manifest",
        "review_epoch": EPOCH,
        "source_selection_epoch": "X1.1",
        "review_mode": "controlled_source_review",
        "selection_frozen_before_review": True,
        "research_selection_provenance_only": True,
        "source_hashes": source_hashes,
        "selection_snapshot_sha256": selection.get("selection_snapshot_sha256"),
        "candidate_pool_counts": inputs["candidate_pool"].get("counts", {}),
        "counts": counts,
        "story_reviews": story_rows,
        "person_reviews": person_rows,
        "fact_reviews": fact_rows,
        "ontology_gap_reviews": ontology_rows,
        "review_policy": {
            "top_level_states": ["accepted", "unresolved", "rejected"],
            "story_before_fact": True,
            "identity_before_dependent_fact": True,
            "accepted_fact_requires_evidence": True,
            "person_story_is_not_participation": True,
            "unknown_over_false_precision": True,
            "no_global_title_mapping": True,
            "no_ontology_change": True,
            "no_ml_write_back": True,
        },
        "policy_notes": [
            "The X1.1 selection score and channel explain why an item was reviewed; they are not evidence.",
            "Accepted independent facts are written only to the X1.2A canonical extension and do not rewrite protected H0C/HG0 projections.",
            "Selected Stories remain outside published Story scope until punctuation and participant projection gates pass.",
        ],
    }
    write(REVIEW_MANIFEST_PATH, manifest)
    write(STORY_REVIEW_PATH, {
        "schema": 1, "stage": "x1-2a-story-review", "review_epoch": EPOCH,
        "source_review_manifest_sha256": sha256_file(REVIEW_MANIFEST_PATH),
        "records": story_rows,
    })
    write(PERSON_REVIEW_PATH, {
        "schema": 1, "stage": "x1-2a-person-review", "review_epoch": EPOCH,
        "source_review_manifest_sha256": sha256_file(REVIEW_MANIFEST_PATH),
        "records": person_rows,
    })
    write(FACT_REVIEW_PATH, {
        "schema": 1, "stage": "x1-2a-fact-review", "review_epoch": EPOCH,
        "source_review_manifest_sha256": sha256_file(REVIEW_MANIFEST_PATH),
        "records": fact_rows,
    })
    write(ONTOLOGY_REVIEW_PATH, {
        "schema": 1, "stage": "x1-2a-ontology-gap-review", "review_epoch": EPOCH,
        "source_review_manifest_sha256": sha256_file(REVIEW_MANIFEST_PATH),
        "ontology_change_count": 0,
        "records": ontology_rows,
    })
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args()
    manifest = build()
    print(json.dumps({
        "stage": manifest["stage"],
        "counts": manifest["counts"],
        "accepted_fact_materialization_count": manifest["counts"]["accepted_fact_materialization_count"],
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
