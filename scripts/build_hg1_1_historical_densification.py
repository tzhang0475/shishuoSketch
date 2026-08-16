#!/usr/bin/env python3
"""Build HG1.1 from reviewed historical extensions without mutating HG0.

HG1.1 is a downstream projection.  It makes a small, explicit distinction
that HG0 intentionally did not make: reviewed Person--Person service and
political assertions get a direct typed edge *in addition to* their existing
reified Story/Event context.  No edge is inferred from co-occurrence.

The temporal projection is equally conservative.  Only reviewed direct Story
anchors and reviewed service/event contexts are resolved.  Candidate H0A/H0B
constraints are retained as audit metadata, never promoted into the reviewed
temporal result.
"""

from __future__ import annotations

from collections import Counter, defaultdict
import copy
import hashlib
import json
import re
from pathlib import Path
from typing import Any, Iterable, Mapping


ROOT = Path(__file__).resolve().parents[1]

INPUTS = {
    "sc1": Path("data/derived/sc1-site.json"),
    "h0c_facts": Path("data/derived/h0c-historical-facts.json"),
    "h0c_service": Path("data/derived/h0c-service-political-facts.json"),
    "hg0_graph": Path("data/derived/hg0-graph-projection.json"),
    "hg0_ontology": Path("data/derived/hg0-ontology.json"),
    "hg0_temporal": Path("data/derived/hg0-temporal-projection.json"),
    "hg0_protection": Path("data/derived/hg0-protection-manifest.json"),
    "h0b1_temporal": Path("data/derived/h0b1-social-temporal-constraints.json"),
    "e0_orientations": Path("data/derived/e0-story-era-orientations.json"),
    "era_cards": Path("data/annotation/era-cards-e0.json"),
    "r3a_candidates": Path("data/derived/person-relation-candidates-r3.json"),
    "r3c_candidates": Path("data/annotation/person-relation-candidates-r3c.json"),
    "r3b_review": Path("data/derived/person-relations-r3b.json"),
    "jinshu_units": Path("data/jinshu-unit-index.json"),
    "x1_facts": Path("data/derived/x1-2rf-materialized-facts.json"),
    "x1_selection": Path("data/derived/x1-1-selection-manifest.json"),
    "x1r_bundles": Path("data/derived/x1-2r-jianshu-evidence-bundles.json"),
    "s1_assertions": Path("data/derived/s1-jianshu-historical-assertions.json"),
    "ml0_metrics": Path("data/derived/ml0-metrics.json"),
    "ux1_manifest": Path("site/public/generated/history/manifest.json"),
}

OUTPUTS = {
    "relation_candidates": Path("data/derived/hg1-1-relation-candidates.json"),
    "relation_review": Path("data/derived/hg1-1-relation-review.json"),
    "relation_materialization": Path("data/derived/hg1-1-relation-materialization.json"),
    "fact_extension": Path("data/derived/hg1-1-fact-extension.json"),
    "temporal_constraints": Path("data/derived/hg1-1-temporal-constraints.json"),
    "ontology": Path("data/derived/hg1-1-ontology.json"),
    "graph": Path("data/derived/hg1-1-graph-projection.json"),
    "temporal_projection": Path("data/derived/hg1-1-temporal-projection.json"),
    "delta": Path("data/derived/hg1-1-hg0-delta.json"),
    "coverage": Path("data/derived/hg1-1-relation-depth-coverage.json"),
    "ux_delta": Path("data/derived/hg1-1-ux-coverage-delta.json"),
    "ml_readiness": Path("data/derived/hg1-1-ml1-1-readiness.json"),
    "protection": Path("data/derived/hg1-1-protection-manifest.json"),
    "metrics": Path("data/derived/hg1-1-metrics.json"),
    "summary": Path("data/derived/hg1-1-summary.json"),
}

# Captured immediately before HG1.1 refreshed UX1.  Keeping the baseline in
# the HG1.1 artifact makes the before/after comparison reproducible after the
# UX1 manifest has legitimately changed.
UX1_PRE_HG1_BASELINE = {
    "capture_commit": "2b89105242f209ff63703cbddbd7656899678690",
    "manifest_sha256": "f0e1f1049041543171d631757c926d363d216ed06f91d75e6488d256fc5f1cfc",
    "person_shards": 75,
    "story_shards": 143,
    "era_shards": 11,
    "relation_shards": 12,
    "evidence_shards": 108,
    "story_temporal_context_rows": 6,
    "person_family_rows": 14,
    "relation_shards_with_evidence": 6,
    "era_cards_with_people": 0,
    "era_cards_with_story_links": 3,
    "era_story_link_count": 7,
    "era_cards_with_historical_depth": 3,
}

DIRECT_EDGE_TYPES = {
    "relation_kinship",
    "relation_social",
    "relation_institutional",
    "relation_political",
    "kinship_collateral_kinship",
    "kinship_uncle_niece",
    "parent_of",
    "spouse_union",
}
FAMILY_EDGE_TYPES = {
    "relation_kinship",
    "kinship_collateral_kinship",
    "kinship_uncle_niece",
    "parent_of",
    "spouse_union",
}
RELATION_MARKERS = re.compile(
    r"父|母|子|女|兄|弟|姊|妹|妻|夫|婚|娶|婿|甥|舅|叔|從父|從子|友|善|交|相知|相識|薦|辟|屬官|任|為吏|為官|反|討|奉|救|援|賞|譽|評",
)


def read_json(relative: Path) -> Any:
    return json.loads((ROOT / relative).read_text(encoding="utf-8"))


def write_json(relative: Path, value: Any) -> None:
    path = ROOT / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def sha256_file(relative: Path) -> str:
    digest = hashlib.sha256()
    with (ROOT / relative).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def stable_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def stable_id(prefix: str, value: Any, length: int = 22) -> str:
    digest = hashlib.sha256(stable_json(value).encode("utf-8")).hexdigest()[:length]
    return f"{prefix}-{digest}"


def sorted_unique(values: Iterable[Any]) -> list[str]:
    return sorted({str(value) for value in values if value is not None and str(value)})


def normalize_temporal_precision(value: Any) -> str:
    value = str(value or "unknown")
    return {
        "exact_year": "exact",
        "reign_bounded": "bounded",
        "event_bounded": "bounded",
        "year_range": "bounded",
        "phase_only": "broad_period",
        "broad_period": "broad_period",
        "unknown": "unknown",
    }.get(value, "unknown")


def temporal_state(precision: str) -> str:
    if precision == "exact":
        return "exact"
    if precision in {"bounded", "broad_period"}:
        return "bounded" if precision == "bounded" else "broad_period"
    return "unknown"


def pair(original: Any, simplified: Any | None = None) -> dict[str, str] | None:
    if original is None and simplified is None:
        return None
    first = "" if original is None else str(original)
    second = first if simplified is None else str(simplified)
    return {"original": first, "simplified": second}


def relation_edge_type(relation: Mapping[str, Any]) -> str | None:
    relation_type = relation.get("relation_type")
    subtype = relation.get("relation_subtype")
    if relation_type == "kinship":
        return {
            "collateral_kinship": "kinship_collateral_kinship",
            "uncle_niece": "kinship_uncle_niece",
            "parent_child": "parent_of",
        }.get(subtype, "relation_kinship")
    if relation_type == "marriage" and subtype == "spouse":
        return "spouse_union"
    if relation_type == "social":
        return "relation_social"
    if relation_type == "institutional":
        return "relation_institutional"
    if relation_type == "political":
        return "relation_political"
    return None


def relation_is_direct(relation: Mapping[str, Any]) -> bool:
    return relation.get("relation_basis") == "direct" and relation_edge_type(relation) is not None


def relation_time(relation_id: str, relation: Mapping[str, Any], service_by_relation: Mapping[str, list[Mapping[str, Any]]]) -> dict[str, Any]:
    contexts = service_by_relation.get(relation_id, [])
    bounded = [row for row in contexts if row.get("review_status") == "reviewed" and row.get("start_year_ce") is not None]
    if bounded:
        first = sorted(bounded, key=lambda row: (row.get("start_year_ce"), row.get("end_year_ce"), str(row.get("service_context_fact_id"))))[0]
        return {
            "status": "event_bounded" if first.get("temporal_precision") == "event_bounded" else "bounded",
            "label": pair(relation.get("scope_event") or first.get("scope_event") or (first.get("event_ids") or [None])[0]),
            "start_year": first.get("start_year_ce"),
            "end_year": first.get("end_year_ce"),
            "event_ids": sorted_unique(first.get("event_ids", [])),
            "source_fact_ids": [str(first.get("service_context_fact_id"))],
        }
    existing = relation.get("time") or {}
    return {
        "status": existing.get("status", "unknown"),
        "label": existing.get("label"),
        "start_year": existing.get("start_year"),
        "end_year": existing.get("end_year"),
        "event_ids": [],
        "source_fact_ids": [],
    }


def source_hashes(paths: Iterable[Path]) -> dict[str, str]:
    return {
        path.as_posix(): sha256_file(path)
        for path in sorted({Path(path) for path in paths}, key=lambda item: item.as_posix())
    }


def build_relation_layers() -> dict[str, Any]:
    sc1 = read_json(INPUTS["sc1"])
    h0c_facts = read_json(INPUTS["h0c_facts"]).get("fact_index", [])
    h0c_fact_by_id = {str(row.get("fact_id")): row for row in h0c_facts}
    service_rows = read_json(INPUTS["h0c_service"]).get("records", [])
    service_by_relation: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for row in service_rows:
        if row.get("relation_id"):
            service_by_relation[str(row["relation_id"])].append(row)

    r3a = read_json(INPUTS["r3a_candidates"])
    r3c = read_json(INPUTS["r3c_candidates"])
    r3b = read_json(INPUTS["r3b_review"])
    candidates_by_id = {str(row.get("candidate_id")): row for row in r3a.get("candidates", [])}
    decisions = {str(row.get("candidate_id")): row for row in r3b.get("decisions", [])}
    materialized_by_id = {str(row.get("id")): row for row in r3b.get("materialized_relations", [])}
    sc_relations = sorted(
        [row for row in sc1.get("relations", []) if row.get("review_status") == "reviewed"],
        key=lambda row: str(row.get("id")),
    )
    sc_relation_by_id = {str(row.get("id")): row for row in sc_relations}

    candidate_records: list[dict[str, Any]] = []
    for candidate_id in sorted(candidates_by_id):
        candidate = candidates_by_id[candidate_id]
        decision = decisions.get(candidate_id, {})
        disposition = str(decision.get("decision") or candidate.get("review_disposition") or "unresolved")
        status = "accepted" if disposition == "approved" else "unresolved" if disposition == "deferred" else "rejected"
        candidate_records.append({
            "candidate_id": candidate_id,
            "source": "R3A/R3B_explicit_relation_review",
            "subject_id": candidate.get("person_a_id"),
            "object_id": candidate.get("person_b_id"),
            "proposed_relation_class": candidate.get("proposed_relation_class"),
            "proposed_relation_subtype": candidate.get("canonical_relation_subtype") or candidate.get("proposed_relation_subtype"),
            "source_entry_ids": sorted_unique(candidate.get("source_entry_ids", [])),
            "evidence_ids": sorted_unique(candidate.get("evidence_ids", [])),
            "selection_basis": candidate.get("discovery_basis"),
            "cooccurrence_only": False,
            "decision": disposition,
            "review_status": status,
            "review_reason": decision.get("decision_note") or candidate.get("discovery_note"),
            "materialized_relation_id": decision.get("production_relation_id") or candidate.get("materialized_relation_id"),
        })

    # R3C is the existing Jinshu/coverage candidate surface.  It is included
    # for a complete HG1.1 audit, but has no HG1.1 review decision and must
    # therefore remain unresolved.
    for candidate in sorted(r3c.get("records", []), key=lambda row: str(row.get("candidate_id"))):
        candidate_records.append({
            "candidate_id": str(candidate.get("candidate_id")),
            "source": "R3C_existing_jinshu_relation_candidate",
            "subject_id": candidate.get("person_a_id"),
            "object_id": candidate.get("person_b_id"),
            "proposed_relation_class": candidate.get("proposed_relation_type"),
            "proposed_relation_subtype": candidate.get("proposed_relation_subtype"),
            "source_entry_ids": sorted_unique(candidate.get("source_entry_ids", [])),
            "source_unit_ids": sorted_unique(candidate.get("source_unit_ids", [])),
            "evidence_ids": sorted_unique(candidate.get("evidence_ids", [])),
            "selection_basis": candidate.get("discovery_basis"),
            "cooccurrence_only": False,
            "decision": "unresolved",
            "review_status": "unresolved",
            "review_reason": "Existing R3C/Jinshu candidate is retained for HG1.1 review but no explicit approval record exists; no relation is inferred.",
            "materialized_relation_id": None,
        })

    # The seven R3 candidates do not include the earlier reviewed family/gold
    # surface.  Record those explicit reviewed relations as accepted inputs,
    # rather than treating their absence from R3A as a gap.
    for relation in sc_relations:
        relation_id = str(relation.get("id"))
        if relation_id in materialized_by_id or any(row.get("materialized_relation_id") == relation_id for row in candidate_records):
            continue
        candidate_records.append({
            "candidate_id": f"existing-reviewed-{relation_id}",
            "source": "H0C_reviewed_relation",
            "subject_id": relation.get("subject_id"),
            "object_id": relation.get("object_id"),
            "proposed_relation_class": relation.get("relation_type"),
            "proposed_relation_subtype": relation.get("relation_subtype"),
            "source_entry_ids": sorted_unique(relation.get("story_ids", [])),
            "evidence_ids": sorted_unique(relation.get("evidence_ids", [])),
            "selection_basis": "existing_reviewed_canonical_relation",
            "cooccurrence_only": False,
            "decision": "approved_existing_reviewed_fact",
            "review_status": "accepted",
            "review_reason": "Already reviewed in the protected H0C/Relation contract; HG1.1 only changes downstream graph projection where needed.",
            "materialized_relation_id": relation_id,
        })

    selected_story_ids = sorted(
        str(row.get("story_id"))
        for row in read_json(INPUTS["x1_selection"]).get("records", [])
        if row.get("story_id")
    )
    selected_story_set = set(selected_story_ids)
    assertions = read_json(INPUTS["s1_assertions"]).get("records", [])
    relation_scan: list[dict[str, Any]] = []
    for row in sorted(assertions, key=lambda item: str(item.get("assertion_id"))):
        if str(row.get("story_id")) not in selected_story_set:
            continue
        candidate_types = set(row.get("candidate_fact_types", []))
        if not candidate_types.intersection({"family", "service_political", "historical_context"}):
            continue
        if not RELATION_MARKERS.search(str(row.get("text", ""))):
            continue
        relation_scan.append({
            "candidate_id": f"jianshu-relation-scan-{row.get('assertion_id')}",
            "source": "S1_Jianshu_story_bundle_scan",
            "assertion_id": row.get("assertion_id"),
            "story_id": row.get("story_id"),
            "source_layer": row.get("layer"),
            "attribution": row.get("attribution"),
            "modality": row.get("modality"),
            "candidate_fact_types": sorted(candidate_types),
            "source_locator": row.get("source_locator"),
            "review_status": "unresolved",
            "review_reason": "Potential relational language was detected, but HG1.1 does not infer endpoints from a broad note scan; explicit endpoint review remains required.",
            "cooccurrence_only": False,
        })

    accepted_relations: list[dict[str, Any]] = []
    review_records: list[dict[str, Any]] = []
    candidate_to_relation = {
        str(row.get("source_candidate_id")): str(row.get("id"))
        for row in r3b.get("materialized_relations", [])
    }
    for relation in sc_relations:
        relation_id = str(relation.get("id"))
        fact = h0c_fact_by_id.get(relation_id, {})
        detail = materialized_by_id.get(relation_id, {})
        candidate_id = detail.get("source_candidate_id") or next(
            (row.get("candidate_id") for row in candidate_records if row.get("materialized_relation_id") == relation_id),
            None,
        )
        evidence_ids = sorted_unique(
            list(relation.get("evidence_ids", []))
            + list(fact.get("evidence_ids", []))
            + [evidence_id for context in service_by_relation.get(relation_id, []) for evidence_id in context.get("evidence_ids", [])]
            + list(detail.get("evidence_ids", []))
        )
        # R3B carries the reviewed scope/event fields; the SC1 row is the
        # protected base projection and may contain null placeholders.  Let
        # the reviewed materialization override those placeholders without
        # changing the canonical relation itself.
        time = relation_time(relation_id, {**relation, **detail}, service_by_relation)
        direct_projection_status = "add_hg1_1_direct_edge" if relation_is_direct(relation) and relation_edge_type(relation) in {"relation_institutional", "relation_political"} else "already_in_hg0_direct_or_contextual"
        review_item = {
            "review_item_id": stable_id("hg1-1-relation-review", {"relation_id": relation_id}),
            "candidate_id": candidate_id,
            "relation_id": relation_id,
            "source_fact_ids": [relation_id],
            "source_path": fact.get("source_path") or "data/derived/person-relations-r3b.json",
            "subject_id": relation.get("subject_id"),
            "object_id": relation.get("object_id"),
            "relation_type": relation.get("relation_type"),
            "relation_subtype": relation.get("relation_subtype"),
            "relation_scope": relation.get("relation_scope"),
            "scope_event": relation.get("scope_event"),
            "review_status": "accepted",
            "review_decision": "accepted_existing_reviewed_relation",
            "assertion_status": relation.get("assertion_status"),
            "evidence_ids": evidence_ids,
            "review_reason": detail.get("notes") or relation.get("notes") or "Protected reviewed relation reused without changing its historical meaning.",
            "direct_projection_status": direct_projection_status,
            "materialization_status": "inherited_h0c_canonical_fact",
        }
        review_records.append(review_item)
        accepted_relations.append({
            "schema": 1,
            "relation_id": relation_id,
            "fact_id": relation_id,
            "fact_key": f"relation:{relation_id}",
            "fact_type": "relation",
            "subject_id": relation.get("subject_id"),
            "object_id": relation.get("object_id"),
            "subject_ids": [relation.get("subject_id"), relation.get("object_id")],
            "relation_type": relation.get("relation_type"),
            "relation_subtype": relation.get("relation_subtype"),
            "relation_basis": relation.get("relation_basis"),
            "relation_scope": relation.get("relation_scope"),
            "scope_event": relation.get("scope_event"),
            "role_a": relation.get("role_a"),
            "role_b": relation.get("role_b"),
            "label": relation.get("label"),
            "story_ids": sorted_unique(relation.get("story_ids", [])),
            "source_entry_ids": sorted_unique(relation.get("source_entry_ids", [])),
            "source_unit_ids": sorted_unique(relation.get("source_unit_ids", [])),
            "evidence_ids": evidence_ids,
            "provenance_refs": [
                {
                    "source_path": fact.get("source_path") or "data/derived/person-relations-r3b.json",
                    "source_fact_id": relation_id,
                    "source_candidate_id": candidate_id,
                    "service_context_fact_ids": sorted_unique(row.get("service_context_fact_id") for row in service_by_relation.get(relation_id, [])),
                }
            ],
            "time": time,
            "assertion_status": relation.get("assertion_status"),
            "review_status": "reviewed",
            "review_item_id": review_item["review_item_id"],
            "direct_projection_status": direct_projection_status,
            "materialization_status": "inherited_h0c_canonical_fact",
            "notes": relation.get("notes"),
        })

    for candidate in candidate_records:
        if candidate.get("review_status") != "unresolved" or candidate.get("materialized_relation_id"):
            continue
        review_records.append({
            "review_item_id": stable_id("hg1-1-relation-review", {"candidate_id": candidate["candidate_id"]}),
            "candidate_id": candidate["candidate_id"],
            "relation_id": None,
            "source_fact_ids": [],
            "source_path": "data/derived/person-relation-candidates-r3.json",
            "subject_id": candidate.get("subject_id"),
            "object_id": candidate.get("object_id"),
            "relation_type": candidate.get("proposed_relation_class"),
            "relation_subtype": candidate.get("proposed_relation_subtype"),
            "review_status": "unresolved",
            "review_decision": "deferred_from_prior_review" if candidate.get("decision") == "deferred" else "awaiting_hg1_1_review",
            "assertion_status": "unknown",
            "evidence_ids": candidate.get("evidence_ids", []),
            "review_reason": candidate.get("review_reason"),
            "direct_projection_status": "not_materialized",
            "materialization_status": "not_materialized",
        })

    # Keep the broad Jianshu language scan auditable as review records too.
    # These are deliberately unresolved: lexical relation markers do not
    # resolve two endpoints, and therefore never become graph edges.
    for candidate in relation_scan:
        review_records.append({
            "review_item_id": stable_id("hg1-1-relation-review", {"candidate_id": candidate["candidate_id"]}),
            "candidate_id": candidate["candidate_id"],
            "relation_id": None,
            "source_fact_ids": [],
            "source_assertion_ids": [candidate.get("assertion_id")],
            "source_path": "data/derived/s1-jianshu-historical-assertions.json",
            "story_id": candidate.get("story_id"),
            "subject_id": None,
            "object_id": None,
            "relation_type": None,
            "relation_subtype": None,
            "review_status": "unresolved",
            "review_decision": "endpoint_review_required",
            "assertion_status": candidate.get("modality") or "unknown",
            "evidence_ids": [],
            "review_reason": candidate.get("review_reason"),
            "direct_projection_status": "not_materialized",
            "materialization_status": "not_materialized",
        })

    review_records.sort(key=lambda row: (str(row.get("review_status")), str(row.get("relation_id") or ""), str(row.get("candidate_id") or ""), str(row.get("review_item_id"))))
    accepted_relations.sort(key=lambda row: str(row["relation_id"]))
    relation_candidates = {
        "schema": 1,
        "stage": "hg1-1-relation-mining",
        "scope": {
            "production_person_count": len({str(row.get("id")) for row in sc1.get("people", [])}),
            "production_story_count": len(sc1.get("stories", [])),
            "selected_x1_1_story_count": len(selected_story_ids),
            "selected_x1_1_story_ids": selected_story_ids,
        },
        "policy": {
            "cooccurrence_is_not_a_relation": True,
            "missing_edge_is_not_negative": True,
            "direct_relation_requires_explicit_endpoints": True,
            "contextual_service_event_edges_remain_separate": True,
        },
        "source_hashes": source_hashes([
            INPUTS["sc1"], INPUTS["h0c_facts"], INPUTS["h0c_service"], INPUTS["r3a_candidates"],
            INPUTS["r3c_candidates"], INPUTS["r3b_review"], INPUTS["jinshu_units"], INPUTS["x1r_bundles"], INPUTS["s1_assertions"],
        ]),
        "candidate_count": len(candidate_records) + len(relation_scan),
        "r3_candidate_count": len(candidate_records),
        "jianshu_potential_relation_surface_count": len(relation_scan),
        "cooccurrence_only_pair_count_audited": r3a.get("cooccurrence_only_pair_count", 0),
        "records": sorted(candidate_records, key=lambda row: str(row.get("candidate_id"))),
        "source_scan": sorted(relation_scan, key=lambda row: str(row.get("candidate_id"))),
    }
    review = {
        "schema": 1,
        "stage": "hg1-1-reviewed-relation-materialization",
        "source_hashes": relation_candidates["source_hashes"],
        "scope": relation_candidates["scope"],
        "records": review_records,
        "counts": {
            "accepted": sum(row.get("review_status") == "accepted" for row in review_records),
            "unresolved": sum(row.get("review_status") == "unresolved" for row in review_records),
            "rejected": sum(row.get("review_status") == "rejected" for row in review_records),
            "direct_projection_additions": sum(row.get("direct_projection_status") == "add_hg1_1_direct_edge" for row in review_records),
        },
        "protection": "H0C relation facts are inherited; HG1.1 changes only their downstream projection.",
    }
    materialization = {
        "schema": 1,
        "stage": "hg1-1-reviewed-relation-projection",
        "source_hashes": relation_candidates["source_hashes"],
        "records": accepted_relations,
        "counts": {
            "reviewed_relation_records": len(accepted_relations),
            "direct_person_relation_records": sum(relation_is_direct(row) for row in accepted_relations),
            "new_hg1_1_direct_edge_records": sum(row["direct_projection_status"] == "add_hg1_1_direct_edge" for row in accepted_relations),
            "new_canonical_relation_facts": 0,
        },
        "policy": "This is a downstream HG1.1 projection of reviewed H0C relations, not a rewrite of H0C facts.",
    }
    return relation_candidates, review, materialization


def build_temporal_constraints() -> dict[str, Any]:
    sc1 = read_json(INPUTS["sc1"])
    facts = read_json(INPUTS["h0c_facts"]).get("fact_index", [])
    reviewed_anchors = {
        str(row.get("subject_ids", [None])[0]): row
        for row in facts
        if row.get("fact_type") == "story_temporal_anchor" and row.get("review_status") == "reviewed" and row.get("subject_ids")
    }
    h0b1 = {str(row.get("story_id")): row for row in read_json(INPUTS["h0b1_temporal"]).get("records", [])}
    orientations = {
        str(row.get("story_id")): row
        for row in read_json(INPUTS["e0_orientations"]).get("records", [])
        if row.get("review_status") == "reviewed"
    }
    era_cards = {
        str(row.get("era_card_id")): row
        for row in read_json(INPUTS["era_cards"]).get("records", [])
    }
    service_rows = [row for row in read_json(INPUTS["h0c_service"]).get("records", []) if row.get("review_status") == "reviewed"]
    service_by_story: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for row in service_rows:
        for story_id in row.get("story_ids", []):
            service_by_story[str(story_id)].append(row)

    def era_for_interval(start: int | None, end: int | None) -> tuple[str | None, Mapping[str, Any] | None]:
        if start is None or end is None:
            return None, None
        choices = []
        for era_id, card in era_cards.items():
            card_start = card.get("start_year_ce")
            card_end = card.get("end_year_ce")
            if card_start is None or card_end is None:
                continue
            if card_start <= start and end <= card_end:
                choices.append((card_end - card_start, era_id, card))
        if not choices:
            return None, None
        _, era_id, card = sorted(choices, key=lambda item: (item[0], item[1]))[0]
        return era_id, card

    records: list[dict[str, Any]] = []
    for story in sorted(sc1.get("stories", []), key=lambda row: str(row.get("id"))):
        story_id = str(story.get("id"))
        anchor = reviewed_anchors.get(story_id)
        h0b_row = h0b1.get(story_id, {})
        direct = []
        if anchor:
            anchor_id = str(anchor.get("fact_id"))
            direct = [
                row for row in h0b_row.get("direct_constraints", [])
                if str(row.get("anchor_id")) == anchor_id
            ]
        chosen = sorted(
            [row for row in direct if row.get("start_year_ce") is not None and row.get("end_year_ce") is not None],
            key=lambda row: (str(row.get("precision")), row.get("start_year_ce"), row.get("end_year_ce")),
        )
        if anchor and chosen:
            direct_row = chosen[0]
            precision = normalize_temporal_precision(direct_row.get("precision") or anchor.get("temporal_precision"))
            start = direct_row.get("start_year_ce")
            end = direct_row.get("end_year_ce")
            era_id = h0b_row.get("suggested_era_card_id")
            era = era_cards.get(str(era_id)) if era_id else None
            if not era:
                era_id, era = era_for_interval(start, end)
            orientation = orientations.get(story_id)
            label = orientation.get("label") if orientation else (era or {}).get("title")
            records.append({
                "constraint_id": stable_id("hg1-1-temporal", {"story_id": story_id, "basis": "reviewed_direct_anchor", "fact_id": anchor.get("fact_id")}),
                "story_id": story_id,
                "resolution_status": "resolved",
                "review_status": "reviewed",
                "precision": precision,
                "temporal_state": temporal_state(precision),
                "start_year_ce": start,
                "end_year_ce": end,
                "label": label,
                "era_card_id": era_id,
                "event_ids": sorted_unique(direct_row.get("event_ids", [])),
                "source_fact_ids": [str(anchor.get("fact_id"))],
                "evidence_ids": sorted_unique(list(anchor.get("evidence_ids", [])) + list(direct_row.get("evidence_ids", []))),
                "derivation_provenance": {
                    "basis": "reviewed_direct_story_temporal_anchor",
                    "h0c_fact_id": anchor.get("fact_id"),
                    "h0b1_constraint_id": h0b_row.get("constraint_id"),
                    "anchor_precision": anchor.get("temporal_precision"),
                    "person_tenure_used": False,
                },
                "candidate_input": None,
            })
            continue

        contextual = [
            row for row in service_by_story.get(story_id, [])
            if row.get("start_year_ce") is not None and row.get("end_year_ce") is not None
        ]
        if contextual:
            intervals = {(row.get("start_year_ce"), row.get("end_year_ce")) for row in contextual}
            start, end = sorted(intervals)[0]
            era_id, era = era_for_interval(start, end)
            event_ids = sorted_unique(event_id for row in contextual for event_id in row.get("event_ids", []))
            event_label = next((row.get("context_type") for row in contextual if row.get("context_type")), None)
            records.append({
                "constraint_id": stable_id("hg1-1-temporal", {"story_id": story_id, "basis": "reviewed_service_event_context", "fact_ids": sorted_unique(row.get("service_context_fact_id") for row in contextual)}),
                "story_id": story_id,
                "resolution_status": "resolved",
                "review_status": "reviewed",
                "precision": "bounded",
                "temporal_state": "bounded",
                "start_year_ce": start,
                "end_year_ce": end,
                "label": (era or {}).get("title") or pair(event_label),
                "era_card_id": era_id,
                "event_ids": event_ids,
                "source_fact_ids": sorted_unique(row.get("service_context_fact_id") for row in contextual),
                "evidence_ids": sorted_unique(evidence_id for row in contextual for evidence_id in row.get("evidence_ids", [])),
                "derivation_provenance": {
                    "basis": "reviewed_service_political_event_context",
                    "service_context_fact_ids": sorted_unique(row.get("service_context_fact_id") for row in contextual),
                    "person_tenure_used": False,
                    "story_id_explicitly_listed_in_source_context": True,
                },
                "candidate_input": None,
            })
            continue

        candidate_precision = normalize_temporal_precision(h0b_row.get("constraint_precision")) if h0b_row else "unknown"
        unknown_reason = "no_reviewed_story_temporal_constraint"
        if h0b_row.get("constraint_precision") not in (None, "unknown"):
            unknown_reason = "candidate_temporal_constraint_not_reviewed"
        records.append({
            "constraint_id": stable_id("hg1-1-temporal", {"story_id": story_id, "basis": "unknown"}),
            "story_id": story_id,
            "resolution_status": "unknown",
            "review_status": "unresolved",
            "precision": "unknown",
            "temporal_state": "unknown",
            "start_year_ce": None,
            "end_year_ce": None,
            "label": None,
            "era_card_id": None,
            "event_ids": [],
            "source_fact_ids": [],
            "evidence_ids": [],
            "derivation_provenance": {
                "basis": "no_reviewed_temporal_projection",
                "person_tenure_used": False,
                "unknown_reason": unknown_reason,
            },
            "candidate_input": {
                "h0b1_constraint_id": h0b_row.get("constraint_id"),
                "candidate_precision": candidate_precision,
                "candidate_review_status": h0b_row.get("review_status"),
                "not_projected_as_reviewed": True,
            } if h0b_row else None,
        })

    records.sort(key=lambda row: str(row["story_id"]))
    return {
        "schema": 1,
        "stage": "hg1-1-story-temporal-resolution",
        "scope": {
            "production_story_count": len(records),
            "production_story_ids": [row["story_id"] for row in records],
        },
        "policy": {
            "reviewed_only": True,
            "unknown_is_not_false": True,
            "person_tenure_does_not_date_story_without_explicit_story_tie": True,
            "candidate_temporal_constraints_are_audit_only": True,
        },
        "source_hashes": source_hashes([
            INPUTS["sc1"], INPUTS["h0c_facts"], INPUTS["h0c_service"], INPUTS["h0b1_temporal"],
            INPUTS["e0_orientations"], INPUTS["era_cards"],
        ]),
        "counts": {
            "resolved": sum(row["resolution_status"] == "resolved" for row in records),
            "unknown": sum(row["resolution_status"] == "unknown" for row in records),
            "exact": sum(row["precision"] == "exact" for row in records),
            "bounded": sum(row["precision"] == "bounded" for row in records),
            "broad_period": sum(row["precision"] == "broad_period" for row in records),
            "candidate_broad_period_not_projected": sum(row.get("candidate_input", {}).get("candidate_precision") == "broad_period" for row in records if row.get("candidate_input")),
            "person_tenure_only_resolutions": 0,
        },
        "records": records,
    }


def extension_fact_projection() -> dict[str, Any]:
    document = read_json(INPUTS["x1_facts"])
    facts = [
        copy.deepcopy(row)
        for row in document.get("facts", document.get("records", []))
        if row.get("review_status") == "reviewed" and row.get("review_decision") == "accepted"
    ]
    for row in facts:
        row["materialization_status"] = "inherited_x1_2rf_reviewed_extension"
        row["hg1_1_projection_only"] = True
    facts.sort(key=lambda row: str(row.get("fact_id")))
    return {
        "schema": 1,
        "stage": "hg1-1-inherited-reviewed-fact-extension",
        "source_hashes": source_hashes([INPUTS["x1_facts"]]),
        "facts": facts,
        "counts": {
            "reviewed_extension_facts": len(facts),
            "new_canonical_facts_created_by_hg1_1": 0,
        },
        "policy": "X1.2RF facts are consumed downstream; H0C and X1 canonical files are not rewritten.",
    }


def make_hg1_edge(
    edge_type: str,
    source_type: str,
    source_id: str,
    target_type: str,
    target_id: str,
    fact_type: str,
    fact_id: str,
    fact_key: str,
    evidence_ids: Iterable[str],
    assertion_status: str,
    graph_layer: str,
    temporal: Mapping[str, Any],
    relation_id: str | None = None,
    provenance_refs: Iterable[Mapping[str, Any]] = (),
    attributes: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    source = {"node_type": source_type, "node_id": source_id}
    target = {"node_type": target_type, "node_id": target_id}
    edge_id = stable_id("edge-hg1-1", {"edge_type": edge_type, "source": source, "target": target, "fact_id": fact_id})
    start = temporal.get("start_year")
    end = temporal.get("end_year")
    status = str(temporal.get("status") or "unknown")
    return {
        "edge_id": edge_id,
        "edge_type": edge_type,
        "source": source,
        "target": target,
        "source_facts": [{"fact_type": fact_type, "fact_id": fact_id, "fact_key": fact_key}],
        "fact_ids": [fact_id],
        "relation_ids": [relation_id] if relation_id else [],
        "evidence_ids": sorted_unique(evidence_ids),
        "provenance_refs": [dict(row) for row in provenance_refs],
        "temporal": {
            "start_year_ce": start,
            "end_year_ce": end,
            "precision": status,
            "basis": temporal.get("basis") or "reviewed_extension_fact",
            "temporal_state": "unknown" if status == "unknown" else "bounded" if status != "exact" else "exact",
            "event_ids": sorted_unique(temporal.get("event_ids", [])),
        },
        "graph_layer": graph_layer,
        "layer_memberships": sorted_unique([graph_layer, "temporal"] if status != "unknown" else [graph_layer]),
        "projection_role": "semantic_direct",
        "review_status": "reviewed",
        "assertion_status": assertion_status,
        "uncertainty_state": assertion_status if assertion_status in {"attested", "reported", "inferred"} else "reviewed",
        "edge_status": "materialized",
        "semantic_key": f"{edge_type}|{source_type}:{source_id}|{target_type}:{target_id}|{fact_id}",
        "attributes": dict(attributes or {}),
    }


def build_graph(materialization: Mapping[str, Any], fact_extension: Mapping[str, Any], temporal: Mapping[str, Any]) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
    hg0 = copy.deepcopy(read_json(INPUTS["hg0_graph"]))
    ontology = copy.deepcopy(read_json(INPUTS["hg0_ontology"]))
    nodes = list(hg0.get("nodes", []))
    edges = list(hg0.get("edges", []))
    existing_node_ids = {str(node.get("node_id")) for node in nodes}
    existing_edge_keys = {str(edge.get("semantic_key")) for edge in edges}
    service_rows = read_json(INPUTS["h0c_service"]).get("records", [])
    service_by_relation: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for row in service_rows:
        service_by_relation[str(row.get("relation_id"))].append(row)

    new_nodes: list[dict[str, Any]] = []
    new_edges: list[dict[str, Any]] = []
    for fact in fact_extension.get("facts", []):
        fact_type = fact.get("fact_type")
        if fact_type == "office_tenure":
            person_id = str(fact.get("person_id"))
            office_id = str(fact.get("office_id"))
            node_id = stable_id("node-hg1-1-tenure", fact.get("fact_id"))
            if node_id not in existing_node_ids:
                node = {
                    "node_id": node_id,
                    "node_type": "OfficeTenure",
                    "label": fact.get("office_title") or office_id,
                    "canonical_reference": f"OfficeTenure:{fact.get('fact_id')}",
                    "scope_role": "historical_fact",
                    "reified_fact_node": True,
                    "source_fact": {"fact_type": fact_type, "fact_id": fact.get("fact_id"), "fact_key": fact.get("fact_key")},
                    "fact_ids": [fact.get("fact_id")],
                    "evidence_ids": sorted_unique(fact.get("evidence_ids", [])),
                    "review_status": "reviewed",
                    "assertion_status": fact.get("assertion_status"),
                    "uncertainty_state": fact.get("temporal_precision") or "unknown",
                    "temporal": {
                        "start_year_ce": fact.get("start_year_ce"),
                        "end_year_ce": fact.get("end_year_ce"),
                        "precision": fact.get("temporal_precision") or "unknown",
                        "temporal_state": "unknown" if not fact.get("start_year_ce") else "bounded",
                    },
                }
                new_nodes.append(node)
                existing_node_ids.add(node_id)
            time = {
                "status": fact.get("temporal_precision") or "unknown",
                "start_year": fact.get("start_year_ce"),
                "end_year": fact.get("end_year_ce"),
                "basis": "x1_2rf_reviewed_office_tenure",
            }
            new_edges.append(make_hg1_edge("has_office_tenure", "Person", person_id, "OfficeTenure", node_id, fact_type, str(fact.get("fact_id")), str(fact.get("fact_key")), fact.get("evidence_ids", []), str(fact.get("assertion_status")), "office", time, provenance_refs=fact.get("provenance_refs", [])))
            new_edges.append(make_hg1_edge("tenure_for_office", "OfficeTenure", node_id, "Office", office_id, fact_type, str(fact.get("fact_id")), str(fact.get("fact_key")), fact.get("evidence_ids", []), str(fact.get("assertion_status")), "office", time, provenance_refs=fact.get("provenance_refs", [])))
        elif fact_type == "location_fact" and fact.get("subject_id") and fact.get("location_id"):
            time = {
                "status": fact.get("temporal_precision") or "unknown",
                "start_year": fact.get("start_year_ce"),
                "end_year": fact.get("end_year_ce"),
                "basis": "x1_2rf_reviewed_location_fact",
            }
            new_edges.append(make_hg1_edge("held_office_at", "Person", str(fact.get("subject_id")), "Location", str(fact.get("location_id")), fact_type, str(fact.get("fact_id")), str(fact.get("fact_key")), fact.get("evidence_ids", []), str(fact.get("assertion_status")), "geographic", time, provenance_refs=fact.get("provenance_refs", []), attributes={"location_role": fact.get("location_role")}))

    for relation in materialization.get("records", []):
        if relation.get("direct_projection_status") != "add_hg1_1_direct_edge":
            continue
        edge_type = relation_edge_type(relation)
        if not edge_type:
            continue
        graph_layer = "office" if edge_type == "relation_institutional" else "service_political" if edge_type == "relation_political" else "family"
        temporal_info = relation.get("time") or {"status": "unknown"}
        edge = make_hg1_edge(
            edge_type,
            "Person",
            str(relation.get("subject_id")),
            "Person",
            str(relation.get("object_id")),
            "relation",
            str(relation.get("fact_id")),
            str(relation.get("fact_key")),
            relation.get("evidence_ids", []),
            str(relation.get("assertion_status")),
            graph_layer,
            {**temporal_info, "basis": "reviewed_direct_relation"},
            relation_id=str(relation.get("relation_id")),
            provenance_refs=relation.get("provenance_refs", []),
            attributes={
                "relation_subtype": relation.get("relation_subtype"),
                "relation_scope": relation.get("relation_scope"),
                "scope_event": relation.get("scope_event"),
                "label": relation.get("label"),
                "direct_relation": True,
                "contextual_projection_retained": True,
            },
        )
        if edge["semantic_key"] not in existing_edge_keys:
            new_edges.append(edge)
            existing_edge_keys.add(edge["semantic_key"])

    nodes.extend(new_nodes)
    edges.extend(new_edges)
    nodes.sort(key=lambda node: (str(node.get("node_type")), str(node.get("node_id"))))
    edges.sort(key=lambda edge: str(edge.get("edge_id")))
    graph = hg0
    graph.update({
        "stage": "hg1-1-graph-projection",
        "graph_id": "hg1-1-published-story-scope",
        "nodes": nodes,
        "edges": edges,
        "node_counts": dict(sorted(Counter(str(node.get("node_type")) for node in nodes).items())),
        "edge_counts": dict(sorted(Counter(str(edge.get("edge_type")) for edge in edges).items())),
        "projection_roles": dict(sorted(Counter(str(edge.get("projection_role")) for edge in edges).items())),
        "layer_counts": dict(sorted(Counter(str(edge.get("graph_layer")) for edge in edges).items())),
        "edge_type_catalog": sorted(set(hg0.get("edge_type_catalog", [])) | {str(edge.get("edge_type")) for edge in new_edges}),
        "policy": "HG1.1 is a derived projection. Direct reviewed Person relations and contextual/reified paths remain separate; co-occurrence is never promoted.",
        "hg0_input_sha256": sha256_file(INPUTS["hg0_graph"]),
        "new_edge_ids": sorted(str(edge.get("edge_id")) for edge in new_edges),
        "new_node_ids": sorted(str(node.get("node_id")) for node in new_nodes),
    })
    return graph, new_nodes, new_edges


def build_ontology() -> dict[str, Any]:
    ontology = copy.deepcopy(read_json(INPUTS["hg0_ontology"]))
    additions = [
        {
            "edge_type": "relation_institutional",
            "source": "Person",
            "target": "Person",
            "layer": "office",
            "symmetric": False,
            "meaning": "Explicit reviewed Person-to-Person service/appointment relation; the reified OfficeTenure or Story context remains separately available.",
        },
        {
            "edge_type": "relation_political",
            "source": "Person",
            "target": "Person",
            "layer": "service_political",
            "symmetric": False,
            "meaning": "Explicit reviewed, scope-limited political act/opposition; never an inferred faction or permanent allegiance.",
        },
    ]
    existing = {str(row.get("edge_type")): row for row in ontology.get("edge_types", [])}
    for row in additions:
        existing[row["edge_type"]] = row
    ontology["schema"] = 1
    ontology["stage"] = "hg1-1-ontology"
    ontology["edge_types"] = [existing[key] for key in sorted(existing)]
    ontology["hg0_ontology_sha256"] = sha256_file(INPUTS["hg0_ontology"])
    ontology["extension_policy"] = "Only two direct edge types are added because HG0 had explicit reified service/political contexts but no direct typed Person-to-Person representation for reviewed R3B assertions. No new historical relation schema is introduced."
    return ontology


def build_temporal_projection(graph: Mapping[str, Any], hg0_temporal: Mapping[str, Any]) -> dict[str, Any]:
    rows = {str(row.get("edge_id")): copy.deepcopy(row) for row in hg0_temporal.get("edge_temporal_index", [])}
    for edge in graph.get("edges", []):
        edge_id = str(edge.get("edge_id"))
        if edge_id in rows:
            continue
        temporal = edge.get("temporal") or {}
        rows[edge_id] = {
            "edge_id": edge_id,
            "edge_type": edge.get("edge_type"),
            "source": edge.get("source"),
            "target": edge.get("target"),
            "start_year_ce": temporal.get("start_year_ce"),
            "end_year_ce": temporal.get("end_year_ce"),
            "precision": temporal.get("precision", "unknown"),
            "basis": temporal.get("basis", "unknown"),
            "temporal_state": temporal.get("temporal_state", "unknown"),
            "source_fact_ids": sorted_unique(edge.get("fact_ids", [])),
        }
    ordered = [rows[key] for key in sorted(rows)]
    state_distribution = Counter(str(row.get("temporal_state", "unknown")) for row in ordered)
    precision_distribution = Counter(str(row.get("precision", "unknown")) for row in ordered)
    contract = copy.deepcopy(hg0_temporal.get("slice_query_contract", {}))
    contract["temporal_leakage_rule"] = "HG1.1 strict slices may use only reviewed bounded/exact relations and Story constraints; unknown/candidate inputs stay in an explicit uncertain bucket."
    return {
        "schema": 1,
        "stage": "hg1-1-temporal-projection",
        "scope_id": "published_story_scope",
        "edge_temporal_index": ordered,
        "coverage": {
            "edge_count": len(ordered),
            "state_distribution": dict(sorted(state_distribution.items())),
            "precision_distribution": dict(sorted(precision_distribution.items())),
            "bounded_edge_count": sum(row.get("temporal_state") == "bounded" for row in ordered),
            "exact_edge_count": sum(row.get("temporal_state") == "exact" for row in ordered),
            "unknown_edge_count": sum(row.get("temporal_state") == "unknown" for row in ordered),
        },
        "slice_query_contract": contract,
        "example_queries": [],
        "policy": "Canonical temporal facts remain unchanged. HG1.1 adds only derived temporal rows for the rebuilt graph.",
    }


def person_relation_coverage(hg0: Mapping[str, Any], graph: Mapping[str, Any]) -> dict[str, Any]:
    people = sorted(str(node.get("node_id")) for node in graph.get("nodes", []) if node.get("node_type") == "Person")

    def profile(source: Mapping[str, Any]) -> dict[str, Any]:
        direct = defaultdict(list)
        context = Counter()
        for edge in source.get("edges", []):
            source_node = edge.get("source", {})
            target_node = edge.get("target", {})
            endpoint_people = []
            if source_node.get("node_type") == "Person": endpoint_people.append(str(source_node.get("node_id")))
            if target_node.get("node_type") == "Person": endpoint_people.append(str(target_node.get("node_id")))
            for person_id in endpoint_people:
                layer = str(edge.get("graph_layer") or "unclassified")
                context[(person_id, layer)] += 1
                if edge.get("edge_type") in DIRECT_EDGE_TYPES and source_node.get("node_type") == "Person" and target_node.get("node_type") == "Person":
                    other = target_node.get("node_id") if str(source_node.get("node_id")) == person_id else source_node.get("node_id")
                    direct[person_id].append({"edge_id": edge.get("edge_id"), "edge_type": edge.get("edge_type"), "neighbor_id": str(other)})
        rows = []
        for person_id in people:
            rows.append({
                "person_id": person_id,
                "direct_relation_count": len(direct.get(person_id, [])),
                "direct_relation_types": dict(sorted(Counter(row["edge_type"] for row in direct.get(person_id, [])).items())),
                "direct_neighbor_ids": sorted({row["neighbor_id"] for row in direct.get(person_id, [])}),
                "family_context_count": sum(context[(person_id, layer)] for layer in {"family"}),
                "office_context_count": sum(context[(person_id, layer)] for layer in {"office"}),
                "event_context_count": sum(context[(person_id, layer)] for layer in {"event"}),
                "geographic_context_count": sum(context[(person_id, layer)] for layer in {"geographic"}),
                "clan_context_count": sum(context[(person_id, layer)] for layer in {"clan"}),
                "service_political_context_count": sum(context[(person_id, layer)] for layer in {"service_political"}),
            })
        return {"rows": rows, "persons_with_direct_relation": sum(bool(direct.get(person_id)) for person_id in people)}

    before = profile(hg0)
    after = profile(graph)
    before_by = {row["person_id"]: row for row in before["rows"]}
    after_by = {row["person_id"]: row for row in after["rows"]}
    delta_rows = []
    for person_id in people:
        delta_rows.append({
            "person_id": person_id,
            "direct_relation_count_delta": after_by[person_id]["direct_relation_count"] - before_by[person_id]["direct_relation_count"],
            "family_context_count_delta": after_by[person_id]["family_context_count"] - before_by[person_id]["family_context_count"],
            "office_context_count_delta": after_by[person_id]["office_context_count"] - before_by[person_id]["office_context_count"],
            "service_political_context_count_delta": after_by[person_id]["service_political_context_count"] - before_by[person_id]["service_political_context_count"],
        })
    return {
        "schema": 1,
        "stage": "hg1-1-relation-depth-coverage",
        "policy": "Coverage is structural availability, not historical importance.",
        "before": {
            "direct_person_relation_edges": sum(row["direct_relation_count"] for row in before["rows"]) // 2,
            "persons_with_direct_relation_context": before["persons_with_direct_relation"],
            "rows": before["rows"],
        },
        "after": {
            "direct_person_relation_edges": sum(row["direct_relation_count"] for row in after["rows"]) // 2,
            "persons_with_direct_relation_context": after["persons_with_direct_relation"],
            "rows": after["rows"],
        },
        "delta": {
            "direct_person_relation_edges": sum(row["direct_relation_count"] for row in after["rows"]) // 2 - sum(row["direct_relation_count"] for row in before["rows"]) // 2,
            "persons_with_direct_relation_context": after["persons_with_direct_relation"] - before["persons_with_direct_relation"],
            "person_rows": delta_rows,
        },
        "layer_definitions": {
            "direct_relation": sorted(DIRECT_EDGE_TYPES),
            "family": sorted(FAMILY_EDGE_TYPES),
            "contextual": ["story", "event", "office", "geographic", "clan", "service_political"],
        },
    }


def graph_delta(hg0: Mapping[str, Any], graph: Mapping[str, Any], temporal: Mapping[str, Any], fact_extension: Mapping[str, Any]) -> dict[str, Any]:
    old_edges = {str(row.get("semantic_key")): row for row in hg0.get("edges", [])}
    new_edges = {str(row.get("semantic_key")): row for row in graph.get("edges", [])}
    added_keys = sorted(set(new_edges) - set(old_edges))
    return {
        "schema": 1,
        "stage": "hg1-1-hg0-delta",
        "from": {"graph_id": hg0.get("graph_id"), "sha256": sha256_file(INPUTS["hg0_graph"]), "nodes": len(hg0.get("nodes", [])), "edges": len(hg0.get("edges", []))},
        "to": {"graph_id": graph.get("graph_id"), "nodes": len(graph.get("nodes", [])), "edges": len(graph.get("edges", []))},
        "added_nodes": sorted(set(str(row.get("node_id")) for row in graph.get("nodes", [])) - set(str(row.get("node_id")) for row in hg0.get("nodes", []))),
        "added_edges": [new_edges[key] for key in added_keys],
        "counts": {
            "added_nodes": len(set(str(row.get("node_id")) for row in graph.get("nodes", [])) - set(str(row.get("node_id")) for row in hg0.get("nodes", []))),
            "added_edges": len(added_keys),
            "added_direct_person_relation_edges": sum(new_edges[key].get("source", {}).get("node_type") == "Person" and new_edges[key].get("target", {}).get("node_type") == "Person" and new_edges[key].get("projection_role") == "semantic_direct" for key in added_keys),
            "inherited_x1_reviewed_facts": len(fact_extension.get("facts", [])),
            "resolved_story_temporal_rows": temporal.get("counts", {}).get("resolved", 0),
        },
        "separation_policy": "Direct reviewed Person relations are added as typed edges; existing Story/Event/Office/Location/Clan/Service reified context remains in the graph and is not collapsed.",
    }


def ux_coverage_delta(temporal: Mapping[str, Any]) -> dict[str, Any]:
    manifest = read_json(INPUTS["ux1_manifest"]) if INPUTS["ux1_manifest"].exists() else {}
    counts_after = {
        "person_shards": manifest.get("scope", {}).get("person_count", 0),
        "story_shards": manifest.get("scope", {}).get("published_story_count", 0),
        "era_shards": manifest.get("scope", {}).get("era_count", 0),
        "relation_shards": manifest.get("scope", {}).get("reviewed_relation_count", 0),
        "evidence_shards": 0,
    }
    shards = manifest.get("shards", {})
    counts_after["evidence_shards"] = sum(str(path).startswith("evidence/") for path in shards)
    story_rows = 0
    person_family = 0
    relation_with_evidence = 0
    era_cards_with_people = 0
    era_cards_with_story_links = 0
    era_story_link_count = 0
    era_cards_with_historical_depth = 0
    history_root = ROOT / "site/public/generated/history"
    for path in sorted((history_root / "story").glob("*.json")):
        try:
            story_rows += len(read_json(Path("site/public/generated/history") / "story" / path.name).get("historical_context", []))
        except FileNotFoundError:
            pass
    for path in sorted((history_root / "person").glob("*.json")):
        person_family += len(read_json(Path("site/public/generated/history") / "person" / path.name).get("family", []))
    for path in sorted((history_root / "relation").glob("*.json")):
        relation_with_evidence += bool(read_json(Path("site/public/generated/history") / "relation" / path.name).get("evidence_ids"))
    for path in sorted((history_root / "era").glob("*.json")):
        era = read_json(Path("site/public/generated/history") / "era" / path.name)
        era_cards_with_people += bool(era.get("people"))
        era_cards_with_story_links += bool(era.get("story_ids"))
        era_story_link_count += len(era.get("story_ids", []))
        era_cards_with_historical_depth += bool(
            era.get("people") or era.get("events") or era.get("offices") or era.get("locations") or era.get("story_ids")
        )
    counts_after.update({
        "story_temporal_context_rows": story_rows,
        "person_family_rows": person_family,
        "relation_shards_with_evidence": relation_with_evidence,
        "era_cards_with_people": era_cards_with_people,
        "era_cards_with_story_links": era_cards_with_story_links,
        "era_story_link_count": era_story_link_count,
        "era_cards_with_historical_depth": era_cards_with_historical_depth,
    })
    return {
        "schema": 1,
        "stage": "hg1-1-ux1-coverage-delta",
        "policy": "UX1 shard counts are presentation coverage, not historical importance.",
        "before": UX1_PRE_HG1_BASELINE,
        "after": counts_after,
        "delta": {key: counts_after.get(key, 0) - UX1_PRE_HG1_BASELINE.get(key, 0) for key in sorted(counts_after)},
        "temporal_resolution_rows_available": temporal.get("counts", {}),
        "after_manifest_sha256": sha256_file(INPUTS["ux1_manifest"]) if INPUTS["ux1_manifest"].exists() else None,
    }


def readiness(coverage: Mapping[str, Any], temporal: Mapping[str, Any], graph: Mapping[str, Any]) -> dict[str, Any]:
    direct = coverage.get("after", {}).get("direct_person_relation_edges", 0)
    temporal_resolved = temporal.get("counts", {}).get("resolved", 0)
    return {
        "schema": 1,
        "stage": "hg1-1-ml1-1-readiness",
        "graph_id": graph.get("graph_id"),
        "policy": "Readiness is a research recommendation, not a model result. No ML artifacts are generated by HG1.1.",
        "layers": {
            "direct_person_relations": {"status": "pilot_only", "reason": f"{direct} direct Person relation edges are available across 75 Persons; service/political edges remain scope-limited."},
            "family_marriage": {"status": "pilot_only", "reason": "Reviewed family edges exist but endpoint coverage remains sparse."},
            "office_service": {"status": "pilot_only", "reason": "Reviewed office/service context is useful for controlled experiments but remains thin."},
            "temporal": {"status": "pilot_only", "reason": f"{temporal_resolved} of 143 Story intervals are resolved from reviewed constraints; unknown remains explicit."},
            "combined_heterogeneous": {"status": "usable_for_diagnostic_pilot", "reason": "The graph is deterministic and typed, but future ML must remain ablation- and uncertainty-aware."},
        },
        "ml1_1_recommendation": "defer_training_until_hg1_1_snapshot_is_reviewed",
        "forbidden_outputs": ["embeddings", "negative_samples", "political_factions", "historical_importance_ranking"],
    }


def protection_manifest(temporal: Mapping[str, Any], graph: Mapping[str, Any], fact_extension: Mapping[str, Any]) -> dict[str, Any]:
    protected = [
        INPUTS["h0c_facts"], INPUTS["hg0_graph"], INPUTS["hg0_ontology"], INPUTS["hg0_temporal"],
        INPUTS["r3b_review"], INPUTS["x1_facts"], INPUTS["x1_selection"], INPUTS["s1_assertions"],
        INPUTS["ml0_metrics"],
    ]
    existing = [path for path in protected if path.exists()]
    h0c_facts = read_json(INPUTS["h0c_facts"]).get("fact_index", [])
    hg0 = read_json(INPUTS["hg0_graph"])
    return {
        "schema": 1,
        "stage": "hg1-1-protection-manifest",
        "protected_input_hashes": source_hashes(existing),
        "protected_counts": {
            "h0c_fact_count": len(h0c_facts),
            "hg0_node_count": len(hg0.get("nodes", [])),
            "hg0_edge_count": len(hg0.get("edges", [])),
            "x1_reviewed_extension_fact_count": len(fact_extension.get("facts", [])),
            "hg1_story_temporal_row_count": len(temporal.get("records", [])),
            "hg1_graph_node_count": len(graph.get("nodes", [])),
            "hg1_graph_edge_count": len(graph.get("edges", [])),
        },
        "write_back": {
            "h0c": False,
            "hg0": False,
            "ml0": False,
            "x1": False,
            "s1": False,
        },
        "policy": "HG1.1 outputs are downstream projections. Existing canonical and protected artifacts are not rewritten.",
    }


def main() -> int:
    for path in INPUTS.values():
        if not path.exists():
            raise SystemExit(f"missing required HG1.1 input: {path}")
    relation_candidates, relation_review, relation_materialization = build_relation_layers()
    temporal = build_temporal_constraints()
    fact_extension = extension_fact_projection()
    graph, new_nodes, new_edges = build_graph(relation_materialization, fact_extension, temporal)
    ontology = build_ontology()
    hg0_temporal = read_json(INPUTS["hg0_temporal"])
    temporal_projection = build_temporal_projection(graph, hg0_temporal)
    hg0 = read_json(INPUTS["hg0_graph"])
    coverage = person_relation_coverage(hg0, graph)
    delta = graph_delta(hg0, graph, temporal, fact_extension)
    ux_delta = ux_coverage_delta(temporal)
    ml_readiness = readiness(coverage, temporal, graph)
    protection = protection_manifest(temporal, graph, fact_extension)

    metrics = {
        "schema": 1,
        "stage": "hg1-1-metrics",
        "graph": {
            "hg0_nodes": len(hg0.get("nodes", [])),
            "hg0_edges": len(hg0.get("edges", [])),
            "hg1_nodes": len(graph.get("nodes", [])),
            "hg1_edges": len(graph.get("edges", [])),
            "new_nodes": len(new_nodes),
            "new_edges": len(new_edges),
            "new_direct_person_relation_edges": delta["counts"]["added_direct_person_relation_edges"],
        },
        "relation": {
            "reviewed_relation_records": relation_materialization["counts"]["reviewed_relation_records"],
            "direct_person_relation_records": relation_materialization["counts"]["direct_person_relation_records"],
            "new_direct_projection_records": relation_materialization["counts"]["new_hg1_1_direct_edge_records"],
            "candidate_count": relation_candidates["candidate_count"],
            "unresolved_review_count": relation_review["counts"]["unresolved"],
        },
        "temporal": temporal["counts"],
        "fact_extension": fact_extension["counts"],
        "ux1": ux_delta,
    }
    summary = {
        "schema": 1,
        "stage": "hg1-1-historical-relationship-densification",
        "status": "complete_projection",
        "relation": {
            "accepted_reviewed_relations": relation_review["counts"]["accepted"],
            "unresolved_relations": relation_review["counts"]["unresolved"],
            "new_canonical_relation_facts": 0,
            "new_direct_graph_edges": delta["counts"]["added_direct_person_relation_edges"],
        },
        "temporal": temporal["counts"],
        "canonical_delta": {
            "stories_added": 0,
            "persons_added": 0,
            "h0c_facts_modified": 0,
            "new_hg1_1_canonical_facts": 0,
            "inherited_x1_reviewed_facts_projected": fact_extension["counts"]["reviewed_extension_facts"],
        },
        "ml1_1_readiness": ml_readiness["ml1_1_recommendation"],
        "stop_boundary": ["ML1.1", "X1.2B", "ER2"],
    }

    documents = {
        "relation_candidates": relation_candidates,
        "relation_review": relation_review,
        "relation_materialization": relation_materialization,
        "fact_extension": fact_extension,
        "temporal_constraints": temporal,
        "ontology": ontology,
        "graph": graph,
        "temporal_projection": temporal_projection,
        "delta": delta,
        "coverage": coverage,
        "ux_delta": ux_delta,
        "ml_readiness": ml_readiness,
        "protection": protection,
        "metrics": metrics,
        "summary": summary,
    }
    for key, value in documents.items():
        write_json(OUTPUTS[key], value)
    print(json.dumps({
        "status": "pass",
        "graph": {"nodes": len(graph.get("nodes", [])), "edges": len(graph.get("edges", []))},
        "new_nodes": len(new_nodes),
        "new_edges": len(new_edges),
        "relation_review": relation_review["counts"],
        "temporal": temporal["counts"],
    }, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
