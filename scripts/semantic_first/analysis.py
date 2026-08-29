"""Deterministic SFH1 audits, comparisons, and HGE1 counterfactuals."""

from __future__ import annotations

import collections
from typing import Any, Mapping, Sequence

import hda1_identity_audit as hda1
import hge1_wave_a as wave_a
import hge1_wave_b as wave_b

from .common import ROOT, read_json, stable_hash, text


REGRESSION_MENTIONS = {
    "24-jianao-009": {"required": ["謝萬"], "forbidden": ["謝萬在兄前欲起索"]},
    "02-yanyu-060": {"required": ["簡文"], "forbidden": ["簡文在暗室"]},
    "21-qiaoyi-009": {"required": ["顧長康", "裴叔則"], "forbidden": ["顧長康畫裴叔則頰"]},
    "21-qiaoyi-011": {"required": ["顧長康"], "forbidden": ["顧長康好寫起人形"]},
    "25-paidiao-028": {"required": ["支道林"], "forbidden": ["支道林因人"]},
    "02-yanyu-004": {"required": ["孔文舉"], "forbidden": ["孔文舉有二"]},
    "21-qiaoyi-005": {"required": ["羊長和"], "forbidden": ["羊長和博學工書"]},
    "18-qiyi-016": {"required": ["許掾"], "forbidden": ["許掾好遊山水"]},
    "27-jiajue-005": {"required": ["袁紹"], "forbidden": ["袁紹年少"]},
    "08-shangyu-069": {"required": ["庾文康"], "forbidden": ["世稱庾文康"]},
    "04-wenxue-023": {"required": [], "forbidden_person": ["佛經"]},
    # The person-reference span may correctly omit the existential 有.  What
    # matters is that the anonymous descriptive referent is retained without
    # promoting the whole clause to a named Person.
    "04-wenxue-030": {"required_any": ["北來道人", "有北來道人"], "forbidden_named": ["有北來道人好才理"]},
    "03-zhengshi-001": {"required": ["陳仲弓"], "forbidden": ["弓為太丘"]},
}

FORBIDDEN_IDENTITIES = {
    ("09-pinzao-088", "仲文", "朱伺"),
    ("09-pinzao-018", "潁", "鄧攸"),
    ("06-yaliang-041", "殷荆州", "王恭"),
    ("02-yanyu-086", "王子敬", "王恭"),
    ("34-pilou-001", "主", "王敦"),
    ("02-yanyu-046", "謝豫章", "謝尚"),
    ("05-fangzheng-028", "敦主簿", "王敦"),
}


def mention_regression_audit(valid_mentions: Sequence[Mapping[str, Any]], final: Sequence[Mapping[str, Any]], provider_failed_story_ids: set[str] | None = None) -> dict[str, Any]:
    provider_failed_story_ids = provider_failed_story_ids or set()
    by_story: dict[str, list[Mapping[str, Any]]] = collections.defaultdict(list)
    for row in valid_mentions:
        by_story[text(row.get("story_id"))].append(row)
    final_by_story: dict[str, list[Mapping[str, Any]]] = collections.defaultdict(list)
    for row in final:
        final_by_story[text(row.get("story_id"))].append(row)
    checks: list[dict[str, Any]] = []
    for story_id, expected in REGRESSION_MENTIONS.items():
        rows = by_story.get(story_id, [])
        person_surfaces = {text(row.get("surface")) for row in rows if text(row.get("entity_kind")) in {"person", "collective_person_reference"}}
        all_surfaces = {text(row.get("surface")) for row in rows}
        failures: list[str] = []
        for surface in expected.get("required", []):
            if surface not in person_surfaces:
                failures.append(f"missing_required:{surface}")
        required_any = expected.get("required_any", [])
        if required_any and not any(surface in person_surfaces for surface in required_any):
            failures.append(f"missing_required_any:{'|'.join(required_any)}")
        for surface in expected.get("forbidden", []):
            if surface in person_surfaces:
                failures.append(f"forbidden_boundary:{surface}")
        for surface in expected.get("forbidden_person", []):
            if surface in person_surfaces:
                failures.append(f"non_person_promoted:{surface}")
        for surface in expected.get("forbidden_named", []):
            if any(text(row.get("surface")) == surface and text(row.get("reference_form")) in {"full_name", "personal_name", "courtesy_name", "style_name"} for row in rows):
                failures.append(f"descriptive_clause_named:{surface}")
        pending = []
        if story_id in provider_failed_story_ids:
            pending = [value for value in failures if value.startswith("missing_required:")]
            failures = [value for value in failures if value not in pending]
        checks.append({"story_id": story_id, "person_surfaces": sorted(person_surfaces), "all_surfaces": sorted(all_surfaces), "failures": failures, "pending_provider": pending, "passed": not failures and not pending})
    people = {text(row.get("person_id")): text(row.get("canonical_name")) for row in (read_json(ROOT / "data/people.json", {}) or {}).get("people", []) or []}
    forbidden: list[dict[str, Any]] = []
    for story_id, surface, wrong_name in sorted(FORBIDDEN_IDENTITIES):
        matches = [row for row in final_by_story.get(story_id, []) if text(row.get("surface")) == surface and text(row.get("final_state")) == "stable_entity_resolved" and people.get(text(row.get("person_id"))) == wrong_name]
        if matches:
            forbidden.append({"story_id": story_id, "surface": surface, "wrong_person": wrong_name, "decision_ids": [row.get("decision_id") for row in matches]})
    return {
        "schema": "sfh1-known-regression-audit-v1",
        "checks": checks,
        "known_boundary_failures": sum(len(row["failures"]) for row in checks),
        "pending_provider_controls": sum(len(row["pending_provider"]) for row in checks),
        "forbidden_stable_resolutions": forbidden,
        "forbidden_stable_resolution_count": len(forbidden),
        "candidate_only": True,
        "canonical_write_back": False,
    }


def old_target_comparison(valid_mentions: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    by_story: dict[str, list[Mapping[str, Any]]] = collections.defaultdict(list)
    for mention in valid_mentions:
        by_story[text(mention.get("story_id"))].append(mention)
    rows: list[dict[str, Any]] = []
    for wave_id, path in (
        ("HGE1-WA", ROOT / "data/annotation/hge1-wave-a-target-selection.json"),
        ("HGE1-WB", ROOT / "data/annotation/hge1-wave-b-target-selection.json"),
    ):
        document = read_json(path, {}) or {}
        for story in document.get("records", []) or []:
            story_id = text(story.get("story_id"))
            new_people = [row for row in by_story.get(story_id, []) if text(row.get("entity_kind")) == "person"]
            for old in story.get("targets", []) or []:
                surface = text(old.get("surface"))
                exact = [row for row in new_people if text(row.get("surface")) == surface]
                inside = [row for row in new_people if text(row.get("surface")) and text(row.get("surface")) in surface and text(row.get("surface")) != surface]
                contains = [row for row in new_people if surface and surface in text(row.get("surface")) and text(row.get("surface")) != surface]
                nonperson = [row for row in by_story.get(story_id, []) if text(row.get("surface")) == surface and text(row.get("entity_kind")) == "non_person"]
                if exact:
                    classification = "exact_correct"
                elif len(inside) >= 2:
                    classification = "missed_multiple_mentions"
                elif inside:
                    classification = "boundary_too_long"
                elif contains:
                    classification = "boundary_too_short"
                elif nonperson:
                    classification = "non_person"
                else:
                    classification = "ambiguous"
                rows.append({
                    "wave": wave_id, "story_id": story_id, "old_target_id": old.get("target_id"),
                    "old_surface": surface, "classification": classification,
                    "new_mentions": [{"mention_id": row.get("mention_id"), "surface": row.get("surface"), "reference_form": row.get("reference_form")} for row in new_people],
                })
    counts = collections.Counter(text(row.get("classification")) for row in rows)
    count = len(rows)
    return {
        "schema": "sfh1-old-new-target-comparison-v1", "records": rows,
        "counts": dict(sorted(counts.items())), "old_target_count": count,
        "old_target_precision": round(counts["exact_correct"] / count, 6) if count else 0,
        "old_boundary_error_rate": round((counts["boundary_too_long"] + counts["boundary_too_short"] + counts["missed_multiple_mentions"]) / count, 6) if count else 0,
        "old_non_person_contamination_rate": round(counts["non_person"] / count, 6) if count else 0,
        "candidate_only": True, "canonical_write_back": False,
    }


def _wave_projection(story_ids: set[str], final: Sequence[Mapping[str, Any]], relations: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    decisions = [row for row in final if text(row.get("story_id")) in story_ids]
    person_obs = []
    candidate_people: dict[str, dict[str, Any]] = {}
    review = []
    for row in decisions:
        endpoint = text(row.get("person_id") or row.get("candidate_person_id"))
        if endpoint:
            person_obs.append({"story_id": row.get("story_id"), "person_id": row.get("person_id"), "candidate_person_id": row.get("candidate_person_id"), "status": row.get("final_state"), "observation_id": row.get("decision_id")})
        if row.get("candidate_person_id"):
            candidate_people.setdefault(text(row.get("candidate_person_id")), {"candidate_person_id": row.get("candidate_person_id"), "canonical_name": row.get("candidate_display_name") or row.get("surface")})
        if text(row.get("final_state")) in {"review_required", "genuinely_unresolved", "local_candidate_resolved", "structural_reference"}:
            review.append(row)
    rels = [row for row in relations if text(row.get("story_id")) in story_ids]
    return {"candidate_persons": list(candidate_people.values()), "person_observations": person_obs, "relation_candidates": rels, "review_items": review}


def recalibrated_growth(final: Sequence[Mapping[str, Any]], relation_projection: Mapping[str, Any]) -> dict[str, Any]:
    universe_a = set((read_json(ROOT / "data/annotation/hge1-wave-a-selection.json", {}) or {}).get("story_ids", []) or [])
    universe_b = set((read_json(ROOT / "data/annotation/hge1-wave-b-selection.json", {}) or {}).get("story_ids", []) or [])
    rels = relation_projection.get("records", []) or []
    a_db = _wave_projection(universe_a, final, rels)
    b_db = _wave_projection(universe_b, final, rels)
    selection_a = read_json(ROOT / "data/annotation/hge1-wave-a-selection.json", {}) or {}
    selection_b = read_json(ROOT / "data/annotation/hge1-wave-b-selection.json", {}) or {}
    base = read_json(ROOT / "data/generated/hge1/baseline.json", {}) or wave_a.baseline()
    a_nodes, a_edges = wave_b._graph_with_waves([selection_a], [a_db])
    ab_nodes, ab_edges = wave_b._graph_with_waves([selection_a, selection_b], [a_db, b_db])
    a_graph = wave_a._components(a_nodes, a_edges)
    ab_graph = wave_a._components(ab_nodes, ab_edges)

    def family_counts(rows: Sequence[Mapping[str, Any]]) -> dict[str, int]:
        counts = collections.Counter(text(row.get("relation_type")) for row in rows)
        return {"kinship": counts["kinship"], "marriage": counts["marriage"], "office": counts["office"], "social": counts["social"] + counts["speech"] + counts["comparison"]}

    a_family = family_counts(a_db["relation_candidates"])
    b_family = family_counts(b_db["relation_candidates"])
    a_after = dict(base)
    a_after.update({
        "story_count": int(base.get("story_count") or 0) + len(universe_a),
        "candidate_person_count": int(base.get("candidate_person_count") or 0) + len(a_db["candidate_persons"]),
        "person_story_count": int(base.get("person_story_count") or 0) + len(a_db["person_observations"]),
        "identity_occurrence_count": int(base.get("identity_occurrence_count") or 0) + len([row for row in final if text(row.get("story_id")) in universe_a]),
        "kinship_fact_or_candidate_count": int(base.get("kinship_fact_or_candidate_count") or 0) + a_family["kinship"],
        "marriage_fact_or_candidate_count": int(base.get("marriage_fact_or_candidate_count") or 0) + a_family["marriage"],
        "office_fact_count": int(base.get("office_fact_count") or 0) + a_family["office"],
        "social_relation_edge_count": int(base.get("social_relation_edge_count") or 0) + a_family["social"],
        "graph_nodes": a_graph["node_count"], "graph_edges": a_graph["edge_count"], "connected_components": a_graph["connected_component_count"], "largest_component_size": a_graph["largest_component_size"], "isolated_orphan_nodes": a_graph["isolated_node_count"],
        "unresolved_identity_count": int(base.get("unresolved_identity_count") or 0) + sum(text(row.get("final_state")) in {"review_required", "genuinely_unresolved"} for row in final if text(row.get("story_id")) in universe_a),
    })
    b_after = dict(a_after)
    b_after.update({
        "story_count": int(a_after.get("story_count") or 0) + len(universe_b),
        "candidate_person_count": int(a_after.get("candidate_person_count") or 0) + len(b_db["candidate_persons"]),
        "person_story_count": int(a_after.get("person_story_count") or 0) + len(b_db["person_observations"]),
        "identity_occurrence_count": int(a_after.get("identity_occurrence_count") or 0) + len([row for row in final if text(row.get("story_id")) in universe_b]),
        "kinship_fact_or_candidate_count": int(a_after.get("kinship_fact_or_candidate_count") or 0) + b_family["kinship"],
        "marriage_fact_or_candidate_count": int(a_after.get("marriage_fact_or_candidate_count") or 0) + b_family["marriage"],
        "office_fact_count": int(a_after.get("office_fact_count") or 0) + b_family["office"],
        "social_relation_edge_count": int(a_after.get("social_relation_edge_count") or 0) + b_family["social"],
        "graph_nodes": ab_graph["node_count"], "graph_edges": ab_graph["edge_count"], "connected_components": ab_graph["connected_component_count"], "largest_component_size": ab_graph["largest_component_size"], "isolated_orphan_nodes": ab_graph["isolated_node_count"],
        "unresolved_identity_count": int(a_after.get("unresolved_identity_count") or 0) + sum(text(row.get("final_state")) in {"review_required", "genuinely_unresolved"} for row in final if text(row.get("story_id")) in universe_b),
    })
    old = read_json(ROOT / "data/generated/hge1/network-growth-series.json", {}) or {}
    series = [
        {"wave": "baseline", **{key: base.get(key) for key in ("story_count", "existing_person_count", "candidate_person_count", "person_story_count", "graph_nodes", "graph_edges", "connected_components", "largest_component_size", "unresolved_identity_count")}},
        {"wave": "HGE1-WA-SFH1", **{key: a_after.get(key) for key in ("story_count", "existing_person_count", "candidate_person_count", "person_story_count", "graph_nodes", "graph_edges", "connected_components", "largest_component_size", "unresolved_identity_count")}},
        {"wave": "HGE1-WB-SFH1", **{key: b_after.get(key) for key in ("story_count", "existing_person_count", "candidate_person_count", "person_story_count", "graph_nodes", "graph_edges", "connected_components", "largest_component_size", "unresolved_identity_count")}},
    ]
    old_a = next((row for row in old.get("series", []) or [] if row.get("wave") == "HGE1-WA"), {})
    old_b = next((row for row in old.get("series", []) or [] if row.get("wave") == "HGE1-WB"), {})
    old_candidates = int(old_b.get("candidate_person_count") or 0) - int(base.get("candidate_person_count") or 0)
    new_candidates = len(a_db["candidate_persons"]) + len(b_db["candidate_persons"])
    completed_existing = sum(bool(row.get("subject_endpoint")) and bool(row.get("object_endpoint")) and str(row.get("subject_endpoint")).startswith("person-") and str(row.get("object_endpoint")).startswith("person-") for row in a_db["relation_candidates"] + b_db["relation_candidates"])
    new_relation_edges = len(a_db["relation_candidates"]) + len(b_db["relation_candidates"])
    return {
        "schema": "sfh1-hge1-recalibrated-growth-series-v1", "old_series": old.get("series", []), "series": series,
        "wave_a": {"after": a_after, "candidate_persons": len(a_db["candidate_persons"]), "existing_person_links": len({row.get('person_id') for row in a_db['person_observations'] if row.get('person_id')}), "relation_assertions": len(a_db["relation_candidates"]), "families": a_family},
        "wave_b": {"after": b_after, "candidate_persons": len(b_db["candidate_persons"]), "existing_person_links": len({row.get('person_id') for row in b_db['person_observations'] if row.get('person_id')}), "relation_assertions": len(b_db["relation_candidates"]), "families": b_family},
        "old_wave_candidate_persons": old_candidates, "sfh1_wave_candidate_persons": new_candidates,
        "old_candidate_person_artifacts_removed": max(0, old_candidates - new_candidates),
        "existing_person_relation_edges": completed_existing,
        "node_novelty_rate": round(new_candidates / 44, 6),
        "edge_novelty_rate": round(new_relation_edges / 44, 6),
        "densification_rate": round(completed_existing / 44, 6),
        "existing_node_edge_share": round(completed_existing / new_relation_edges, 6) if new_relation_edges else 0,
        "candidate_only": True, "canonical_write_back": False,
    }


def random_blind_audit(packets: Sequence[Mapping[str, Any]], mentions: Sequence[Mapping[str, Any]], semantics: Sequence[Mapping[str, Any]], final: Sequence[Mapping[str, Any]], relations: Sequence[Mapping[str, Any]], count: int = 30) -> dict[str, Any]:
    selected = sorted(packets, key=lambda row: stable_hash({"seed": "sfh1-random-blind-audit-v1", "story_id": row.get("story_id")}))[:count]
    selected_ids = {text(row.get("story_id")) for row in selected}
    return {
        "schema": "sfh1-random-blind-audit-v1", "selection_method": "stable_sha256_order", "story_count": len(selected),
        "selection_hash": stable_hash(sorted(selected_ids)),
        "records": [{
            "story_id": packet.get("story_id"),
            "source_evidence": [{"evidence_id": row.get("evidence_id"), "source_layer": row.get("source_layer"), "text": row.get("text")} for row in packet.get("evidence", []) or []],
            "mentions": [row for row in mentions if text(row.get("story_id")) == text(packet.get("story_id"))],
            "reference_semantics": [row for row in semantics if text(row.get("story_id")) == text(packet.get("story_id"))],
            "proposed_identities": [row for row in final if text(row.get("story_id")) == text(packet.get("story_id"))],
            "relations": [row for row in relations if text(row.get("story_id")) == text(packet.get("story_id"))],
        } for packet in selected],
        "candidate_only": True, "canonical_write_back": False,
    }


def heuristic_audit() -> dict[str, Any]:
    rows = [
        ("_target_rows", "scripts/hge1_wave_a.py", "remove_from_core_path", "Old target quota/selection is replaced by blind L1 mention reading."),
        ("_fallback_surface_hits", "scripts/hge1_wave_a.py", "retain_as_retrieval_hint", "May rank windows but cannot assert a Person."),
        ("_trim_target_surface", "scripts/hge1_wave_a.py", "deprecated", "String trimming caused compound-clause Person boundaries."),
        ("PERSON_SURFACE_SUFFIXES", "scripts/hge1_wave_a.py", "compatibility_only", "Legacy selection signal only; suffixes have no semantic authority."),
        ("PERSON_SURFACE_TAILS", "scripts/hge1_wave_a.py", "compatibility_only", "Legacy window hint only."),
        ("GENERIC_NAME_TOKENS", "scripts/hge1_wave_a.py", "retain_as_retrieval_hint", "Useful for ranking but not entity typing."),
        ("_preceding_anchor", "scripts/hdb2_psl1_3a_common.py", "remove_from_core_path", "L3 supplies grounded anchor/holder/patron semantics."),
        ("office-holder regexes", "scripts/hdb2_psl1_3b_common.py", "compatibility_only", "Explicit regex remains a diagnostic; L3 owns arbitrary office semantics."),
        ("kinship suffix rules", "scripts/hdb2_occurrence_common.py", "deprecated", "Suffix alone cannot distinguish kinship from lexicalized names."),
        ("single-character special cases", "scripts/hdb2_psl1_3c_common.py", "deprecated", "L1/L3 read local semantics; Python only retrieves candidates."),
        ("exact source grounding", "scripts/semantic_first/mention_validation.py", "retain_as_hard_deterministic_rule", "Exact evidence membership is deterministic database safety."),
    ]
    return {"schema": "sfh1-python-semantic-heuristic-audit-v1", "records": [{"heuristic": name, "location": location, "classification": classification, "reason": reason} for name, location, classification, reason in rows], "candidate_only": True, "canonical_write_back": False}


def protected_hashes() -> dict[str, str]:
    return hda1.protected_hashes()
