#!/usr/bin/env python3
"""Deterministic P3A Person expansion candidate analysis.

This module is deliberately an analysis layer.  It reads existing resolved
mentions and structured evidence, but never creates a Person, PersonStoryLink,
Relation, or publication record.  In particular, unresolved surfaces remain
outside the ranked identity universe.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[1]

PEOPLE_PATH = Path("data/people.json")
ALIASES_PATH = Path("data/aliases.json")
SHISHUO_MENTIONS_PATH = Path("data/mentions/shishuo.json")
JINSHU_MENTIONS_PATH = Path("data/mentions/jinshu.json")
CORPUS_INDEX_PATH = Path("data/shishuo-corpus-index.json")
RELATIONS_PATH = Path("data/annotation/wp1-relations.json")
PERSON_STORY_INDEX_PATH = Path("data/derived/person-story-index.json")
STORY_CHAIN_PATH = Path("data/story-chain-gold-set.json")
PERSON_SKETCH_PATH = Path("data/annotation/person-sketches.json")
SC1_BUNDLE_PATH = Path("data/derived/sc1-site.json")
P3A1_PATH = Path("data/derived/person-identity-candidates.json")
P3A1_OCCURRENCES_PATH = Path("data/derived/person-candidate-occurrences.json")
P3A_PATH = Path("data/derived/person-expansion-candidates.json")
UNRESOLVED_PATH = Path("data/derived/person-expansion-unresolved-surfaces.json")
REPORT_PATH = Path("docs/person-expansion-candidates.md")


# The positive weights sum to 1.0.  Ambiguity is an explicit subtraction,
# rather than being hidden inside the evidence score.
WEIGHTS: dict[str, float] = {
    "current_story_coverage": 0.22,
    "story_unlock_potential": 0.22,
    "current_network_connectivity": 0.16,
    "corpus_story_coverage": 0.12,
    "identity_evidence_quality": 0.12,
    "clan_bridge_value": 0.06,
    "naming_richness": 0.05,
    "source_depth": 0.05,
    "ambiguity_risk": 0.15,
}

STABLE_ALIAS_TYPES = {
    "personal_name",
    "courtesy_name",
    "surname_plus_courtesy_name",
    "orthographic_variant",
}
USEFUL_ALIAS_TYPES = {
    "personal_name",
    "courtesy_name",
    "surname_plus_courtesy_name",
    "office_title",
    "contextual_title",
    "textual_shorthand",
    "orthographic_variant",
}
FAMILY_RELATION_SUBTYPES = {
    "parent_child",
    "uncle_niece",
    "collateral_kinship",
    "spouse",
}
LAYER_ORDER = {
    "main_text": 0,
    "liu_annotation": 1,
    "unit_text": 2,
}


def read_json(root: Path, relative: Path) -> Any:
    return __import__("json").loads((root / relative).read_text(encoding="utf-8"))


def write_json(root: Path, relative: Path, value: Any) -> None:
    import json

    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=False) + "\n",
        encoding="utf-8",
    )


def _sorted_unique(values: Iterable[str]) -> list[str]:
    return sorted({value for value in values if isinstance(value, str) and value})


def _bounded(value: float, ceiling: float) -> float:
    if ceiling <= 0:
        return 0.0
    return max(0.0, min(float(value) / float(ceiling), 1.0))


def _normalization_max(values: Iterable[float]) -> float:
    return max([float(value) for value in values] + [1.0])


def _round(value: float) -> float:
    return round(float(value), 6)


def _mention_layer(mention: Mapping[str, Any]) -> str:
    source = str(mention.get("source", ""))
    section = str(mention.get("section", ""))
    if source == "jinshu":
        return "jinshu_" + (section or "unit_text")
    return section or "unknown"


def _story_id(mention: Mapping[str, Any]) -> str | None:
    value = mention.get("entry_id") or mention.get("source_id")
    return value if isinstance(value, str) and value else None


def _alias_person_ids(alias: Mapping[str, Any]) -> set[str]:
    values: set[str] = set()
    for key in ("person_ids", "resolved_person_ids"):
        raw = alias.get(key, [])
        if isinstance(raw, list):
            values.update(value for value in raw if isinstance(value, str) and value)
    return values


def _source_evidence_count(value: Mapping[str, Any]) -> int:
    """Count explicit source/evidence objects without parsing quotations."""

    count = 0
    source_evidence = value.get("source_evidence")
    if isinstance(source_evidence, list):
        count += sum(isinstance(item, Mapping) for item in source_evidence)
    evidence = value.get("evidence")
    if isinstance(evidence, Mapping):
        if evidence.get("provenance") or evidence.get("evidence_ids"):
            count += 1
    return count


def _display_name(profile: Mapping[str, Any]) -> str:
    """Choose a deterministic review label, never a generated Person name."""

    stable = profile.get("stable_name_surfaces", {})
    if isinstance(stable, Mapping) and stable:
        ranked = sorted(
            ((str(surface), int(count)) for surface, count in stable.items()),
            key=lambda item: (-item[1], len(item[0]), item[0]),
        )
        return ranked[0][0]
    names = profile.get("all_surfaces", {})
    if isinstance(names, Mapping) and names:
        ranked = sorted(
            ((str(surface), int(count)) for surface, count in names.items()),
            key=lambda item: (-item[1], len(item[0]), item[0]),
        )
        return ranked[0][0]
    return str(profile["source_person_id"])


def _identity_anchor(alias_type: str, resolution_mode: str, surface: str) -> bool:
    if alias_type in STABLE_ALIAS_TYPES:
        return True
    return resolution_mode == "exact" and bool(surface) and len(surface) >= 2


def _alias_mode(alias: Mapping[str, Any], mention: Mapping[str, Any] | None = None) -> str:
    mode = alias.get("resolution_mode")
    if isinstance(mode, str) and mode:
        return mode
    if isinstance(mention, Mapping):
        value = mention.get("resolution_mode")
        if isinstance(value, str) and value:
            return value
    return "ambiguous"


def _candidate_seed(
    current_person_ids: set[str],
    aliases: Sequence[Mapping[str, Any]],
    shishuo_mentions: Sequence[Mapping[str, Any]],
    jinshu_mentions: Sequence[Mapping[str, Any]],
    relations: Sequence[Mapping[str, Any]],
) -> dict[str, dict[str, Any]]:
    """Collect existing non-scoped identity keys without resolving surfaces."""

    profiles: dict[str, dict[str, Any]] = {}

    def ensure(person_id: str) -> dict[str, Any]:
        profile = profiles.setdefault(
            person_id,
            {
                "source_person_id": person_id,
                "alias_ids": set(),
                "aliases": [],
                "mentions": [],
                "shishuo_mentions": [],
                "jinshu_mentions": [],
                "all_surfaces": Counter(),
                "stable_name_surfaces": Counter(),
                "source_evidence_count": 0,
                "identity_records": set(),
            },
        )
        return profile

    for alias in aliases:
        if not isinstance(alias, Mapping):
            continue
        for person_id in sorted(_alias_person_ids(alias) - current_person_ids):
            profile = ensure(person_id)
            alias_id = alias.get("alias_id")
            if isinstance(alias_id, str):
                profile["alias_ids"].add(alias_id)
            profile["aliases"].append(alias)
            profile["source_evidence_count"] += _source_evidence_count(alias)
            profile["identity_records"].add("alias:" + str(alias.get("alias_id", "")))
            surface = alias.get("surface")
            if isinstance(surface, str) and surface:
                profile["all_surfaces"][surface] += 1
                if _identity_anchor(
                    str(alias.get("alias_type", "")),
                    _alias_mode(alias),
                    surface,
                ):
                    profile["stable_name_surfaces"][surface] += 1

    for source_name, mentions in (
        ("shishuo", shishuo_mentions),
        ("jinshu", jinshu_mentions),
    ):
        for mention in mentions:
            if not isinstance(mention, Mapping):
                continue
            person_id = mention.get("person_id")
            if not isinstance(person_id, str) or not person_id or person_id in current_person_ids:
                continue
            profile = ensure(person_id)
            profile["mentions"].append(mention)
            profile[source_name + "_mentions"].append(mention)
            profile["source_evidence_count"] += _source_evidence_count(mention)
            profile["identity_records"].add(
                str(mention.get("mention_id") or mention.get("source_id") or "mention")
            )
            alias_id = mention.get("alias_id")
            if isinstance(alias_id, str):
                profile["alias_ids"].add(alias_id)
            surface = mention.get("surface")
            if isinstance(surface, str) and surface:
                profile["all_surfaces"][surface] += 1
                alias_type = str(mention.get("alias_type", ""))
                mode = _alias_mode({}, mention)
                if _identity_anchor(alias_type, mode, surface):
                    profile["stable_name_surfaces"][surface] += 1

    for relation in relations:
        if not isinstance(relation, Mapping):
            continue
        for endpoint in (relation.get("subject_id"), relation.get("object_id")):
            if isinstance(endpoint, str) and endpoint and endpoint not in current_person_ids:
                profile = ensure(endpoint)
                profile["identity_records"].add("relation:" + str(relation.get("id", "")))

    return profiles


def _profile_aliases(profile: Mapping[str, Any], aliases_by_id: Mapping[str, Mapping[str, Any]]) -> list[Mapping[str, Any]]:
    result: list[Mapping[str, Any]] = []
    seen: set[str] = set()
    for alias in profile.get("aliases", []):
        alias_id = str(alias.get("alias_id", ""))
        if alias_id not in seen:
            seen.add(alias_id)
            result.append(alias)
    for alias_id in sorted(profile.get("alias_ids", set())):
        alias = aliases_by_id.get(alias_id)
        if alias is not None and alias_id not in seen:
            seen.add(alias_id)
            result.append(alias)
    return result


def _collect_unresolved_surfaces(
    shishuo_mentions: Sequence[Mapping[str, Any]],
    current_person_ids: set[str],
    corpus_order: Mapping[str, int],
) -> list[dict[str, Any]]:
    grouped: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for mention in shishuo_mentions:
        if mention.get("person_id") is None and isinstance(mention.get("surface"), str):
            grouped[str(mention["surface"])].append(mention)

    rows: list[dict[str, Any]] = []
    for surface, mentions in grouped.items():
        if len(mentions) < 2:
            continue
        story_ids = _sorted_unique(
            str(value)
            for value in (_story_id(mention) for mention in mentions)
            if value
        )
        story_ids.sort(key=lambda value: (corpus_order.get(value, 10**9), value))
        candidate_ids = _sorted_unique(
            candidate
            for mention in mentions
            for candidate in (mention.get("candidate_person_ids") or [])
            if isinstance(candidate, str)
        )
        if len(set(candidate_ids) - current_person_ids) == 0:
            reason = "unresolved_scoped_identity" if candidate_ids else "unresolved_no_stable_identity"
        else:
            reason = "unresolved_non_scoped_candidate_requires_review"
        rows.append(
            {
                "surface": surface,
                "mention_count": len(mentions),
                "story_count": len(story_ids),
                "story_ids": story_ids,
                "candidate_person_ids": candidate_ids,
                "reason_code": reason,
                "not_ranked_as_person": True,
            }
        )
    rows.sort(key=lambda row: (-row["mention_count"], -row["story_count"], row["surface"]))
    return rows


def _current_story_ids(root: Path) -> list[str]:
    bundle = read_json(root, SC1_BUNDLE_PATH)
    gold = read_json(root, Path("data/story-chain-gold-set.json"))
    gold_ids = [str(item["entry_id"]) for item in gold.get("records", [])]
    # SC0 remains the frozen gold set, while M2 publishes an explicit union
    # of SC0 and the Story Expansion manifest.  P3A's current-coverage
    # metrics should see the live readable Story set, but must still prove
    # that every frozen SC0 Story remains present in that set.  The old
    # story_chain field was SC0-only and is no longer a suitable live-set
    # source after M2.
    stories = bundle.get("stories", [])
    ids = [
        str(story.get("id"))
        for story in stories
        if isinstance(story, Mapping)
        and isinstance(story.get("id"), str)
        and story.get("publication_state") != "blocked"
    ]
    if gold_ids and not set(gold_ids).issubset(ids):
        raise ValueError("SC1 live Story IDs do not contain the frozen SC0 Gold Set")
    return ids or gold_ids


def _relation_metrics(
    root: Path,
    current_person_ids: set[str],
) -> tuple[dict[str, set[str]], dict[str, set[str]], dict[str, set[str]]]:
    direct_counts: dict[str, set[str]] = defaultdict(set)
    connected: dict[str, set[str]] = defaultdict(set)
    family_connections: dict[str, set[str]] = defaultdict(set)
    relations = read_json(root, RELATIONS_PATH).get("records", [])
    for relation in relations:
        if relation.get("relation_basis") != "direct" or relation.get("review_status") != "reviewed":
            continue
        subject = relation.get("subject_id")
        object_id = relation.get("object_id")
        if not isinstance(subject, str) or not isinstance(object_id, str):
            continue
        if subject in current_person_ids and object_id not in current_person_ids:
            candidate, current = object_id, subject
        elif object_id in current_person_ids and subject not in current_person_ids:
            candidate, current = subject, object_id
        else:
            continue
        relation_id = str(relation.get("id", ""))
        direct_counts[candidate].add(relation_id)
        connected[candidate].add(current)
        if relation.get("relation_subtype") in FAMILY_RELATION_SUBTYPES:
            family_connections[candidate].add(relation_id)
    return direct_counts, connected, family_connections


def _make_profile(
    profile: dict[str, Any],
    *,
    aliases_by_id: Mapping[str, Mapping[str, Any]],
    corpus_order: Mapping[str, int],
    current_story_ids: Sequence[str],
    current_person_ids: set[str],
    direct_relation_ids: Mapping[str, set[str]],
    connected_current: Mapping[str, set[str]],
    family_connections: Mapping[str, set[str]],
) -> dict[str, Any] | None:
    shishuo = list(profile["shishuo_mentions"])
    if not shishuo:
        # A Jinshu-only ID is not a Story-expansion candidate in this phase.
        return None
    aliases = _profile_aliases(profile, aliases_by_id)
    stable_surfaces = profile["stable_name_surfaces"]
    if not stable_surfaces:
        # A resolved generic/contextual surface is still useful for the
        # unresolved audit, but is not a stable Person candidate.
        return None

    current_story_set = set(current_story_ids)
    story_layers: dict[str, set[str]] = defaultdict(set)
    all_story_ids: set[str] = set()
    all_surfaces = Counter()
    alias_ids: set[str] = set(profile["alias_ids"])
    exact_alias_ids: set[str] = set()
    contextual_alias_ids: set[str] = set()
    alias_types: set[str] = set()
    source_families: set[str] = set()
    high_confidence = 0
    non_high_confidence = 0
    ambiguous_surfaces: set[str] = set()
    evidence_ids: set[str] = set()
    stable_alias_surfaces: set[str] = set(stable_surfaces)

    for alias in aliases:
        alias_id = alias.get("alias_id")
        if isinstance(alias_id, str):
            alias_ids.add(alias_id)
        alias_type = str(alias.get("alias_type", ""))
        alias_types.add(alias_type)
        mode = _alias_mode(alias)
        if mode == "exact":
            exact_alias_ids.add(str(alias_id))
        else:
            contextual_alias_ids.add(str(alias_id))
        for source_evidence in alias.get("source_evidence", []):
            if isinstance(source_evidence, Mapping):
                evidence_ids.add(str(source_evidence.get("mention_id") or source_evidence.get("source_id") or "alias-evidence"))

    for mention in profile["mentions"]:
        source = str(mention.get("source", ""))
        source_families.add(source)
        surface = mention.get("surface")
        if isinstance(surface, str) and surface:
            all_surfaces[surface] += 1
        story_id = _story_id(mention)
        if source == "shishuo" and story_id:
            all_story_ids.add(story_id)
            story_layers[story_id].add(str(mention.get("section", "unknown")))
        if mention.get("confidence") == "high":
            high_confidence += 1
        else:
            non_high_confidence += 1
        if isinstance(surface, str) and len(set(mention.get("candidate_person_ids") or [])) > 1:
            ambiguous_surfaces.add(surface)
        evidence = mention.get("evidence")
        if isinstance(evidence, Mapping):
            ids = evidence.get("evidence_ids", [])
            if isinstance(ids, list):
                evidence_ids.update(str(item) for item in ids if isinstance(item, str))

    main_story_ids = {
        story_id for story_id, layers in story_layers.items() if "main_text" in layers
    }
    liu_story_ids = {
        story_id for story_id, layers in story_layers.items() if "liu_annotation" in layers
    }
    liu_only_story_ids = liu_story_ids - main_story_ids
    shared_story_ids: set[str] = set()
    # The caller adds current-person story sets to the profile before scoring.
    current_story_presence = profile.get("current_story_presence", {})
    for story_id in all_story_ids:
        if current_story_presence.get(story_id):
            shared_story_ids.add(story_id)
    unlock_story_ids = shared_story_ids - current_story_set

    direct_ids = set(direct_relation_ids.get(profile["source_person_id"], set()))
    connected_ids = set(connected_current.get(profile["source_person_id"], set()))
    family_ids = set(family_connections.get(profile["source_person_id"], set()))

    current_main = main_story_ids & current_story_set
    current_liu = liu_story_ids & current_story_set
    current_liu_only = liu_only_story_ids & current_story_set
    current_weighted = len(current_main) + 0.5 * len(current_liu_only)
    corpus_story_count = len(all_story_ids)
    useful_alias_count = len(exact_alias_ids) + 0.4 * len(contextual_alias_ids)
    source_layer_names = sorted(
        {_mention_layer(mention) for mention in profile["mentions"]},
        key=lambda item: (LAYER_ORDER.get(item, 9), item),
    )
    stable_name_anchor = bool(stable_alias_surfaces)

    risk_flags: list[str] = []
    if not exact_alias_ids:
        risk_flags.append("no_exact_alias")
    if not stable_name_anchor:
        risk_flags.append("no_stable_name_anchor")
    if ambiguous_surfaces:
        risk_flags.append("multiple_candidate_surface_context")
    if non_high_confidence:
        risk_flags.append("non_high_confidence_mentions")
    if not evidence_ids and profile["source_evidence_count"] == 0:
        risk_flags.append("no_structured_evidence")
    if len(source_families) == 1:
        risk_flags.append("single_source_family")

    metrics = {
        "current_main_text_story_count": len(current_main),
        "current_liu_annotation_story_count": len(current_liu),
        "current_liu_annotation_only_story_count": len(current_liu_only),
        "current_weighted_story_coverage": _round(current_weighted),
        "corpus_story_count": corpus_story_count,
        "mention_count": len(shishuo),
        "shishuo_mention_count": len(shishuo),
        "source_mention_count": len(profile["mentions"]),
        "direct_relation_to_current_count": len(direct_ids),
        "shared_story_with_current_count": len(shared_story_ids),
        "unlock_story_count": len(unlock_story_ids),
        "family_relation_to_current_count": len(family_ids),
    }
    evidence_summary = {
        "exact_alias_count": len(exact_alias_ids),
        "contextual_alias_count": len(contextual_alias_ids),
        "high_confidence_mention_count": high_confidence,
        "source_evidence_count": profile["source_evidence_count"],
        "source_layers": source_layer_names,
        "source_families": sorted(source_families),
        "stable_name_surfaces": sorted(stable_name_anchor and stable_surfaces or []),
        "alias_types": sorted(alias_types),
        "evidence_keys": sorted(evidence_ids),
    }
    return {
        "source_person_id": profile["source_person_id"],
        "canonical_name": _display_name(profile),
        "metrics": metrics,
        "evidence_summary": evidence_summary,
        "all_story_ids": sorted(all_story_ids, key=lambda value: (corpus_order.get(value, 10**9), value)),
        "current_story_ids": sorted((main_story_ids | liu_story_ids) & current_story_set, key=lambda value: (corpus_order.get(value, 10**9), value)),
        "shared_story_ids": sorted(shared_story_ids, key=lambda value: (corpus_order.get(value, 10**9), value)),
        "unlock_story_ids": sorted(unlock_story_ids, key=lambda value: (corpus_order.get(value, 10**9), value)),
        "connected_current_person_ids": sorted(connected_ids),
        "direct_relation_ids": sorted(direct_ids),
        "risk_flags": sorted(risk_flags),
        "stable_name_anchor": stable_name_anchor,
        "alias_ids": sorted(alias_ids),
        "ambiguity_surface_count": len(ambiguous_surfaces),
    }


def _make_p3a1_profile(
    candidate: Mapping[str, Any],
    occurrences: Sequence[Mapping[str, Any]],
    *,
    corpus_order: Mapping[str, int],
    current_story_ids: Sequence[str],
    current_story_presence: Mapping[str, set[str]],
) -> dict[str, Any] | None:
    """Adapt an eligible P3A.1 proposal to the existing ranking math.

    This is a ranking projection only.  The candidate ID remains distinct
    from a production `person_id`, and no Relation data is synthesized.
    """

    candidate_id = str(candidate.get("candidate_id"))
    if candidate.get("status") != "strong_candidate" or candidate.get("materialization_state") != "new_candidate":
        return None
    rows = [row for row in occurrences if row.get("candidate_id") == candidate_id]
    story_layers: dict[str, set[str]] = defaultdict(set)
    story_ids: set[str] = set()
    for row in rows:
        story_id = row.get("source_id")
        if isinstance(story_id, str):
            story_ids.add(story_id)
            story_layers[story_id].add(str(row.get("section", "unknown")))
    main_story_ids = {story_id for story_id, layers in story_layers.items() if "main_text" in layers}
    liu_story_ids = {story_id for story_id, layers in story_layers.items() if "liu_annotation" in layers}
    current_set = set(current_story_ids)
    shared_story_ids = {story_id for story_id in story_ids if current_story_presence.get(story_id)}
    exact_count = sum(item.get("association_mode") == "exact" for item in candidate.get("surfaces", []))
    contextual_count = sum(item.get("association_mode") != "exact" for item in candidate.get("surfaces", []))
    high_confidence = sum(item.get("confidence") == "strong_candidate" for item in rows)
    source_families = {"jinshu"}
    if rows:
        source_families.add("shishuo")
    source_layers = sorted(
        {layer for item in candidate.get("surfaces", []) for layer in item.get("source_layers", [])}
        | {str(row.get("section")) for row in rows},
        key=lambda value: (LAYER_ORDER.get(value, 9), value),
    )
    identity_evidence = list(candidate.get("identity_evidence_ids", []))
    occurrence_evidence = list(candidate.get("evidence_ids", []))
    risk_flags = set(candidate.get("risk_flags", []))
    if candidate.get("status") == "candidate":
        risk_flags.add("candidate_identity_requires_review")
    return {
        "source_person_id": candidate_id,
        "candidate_id": candidate_id,
        "identity_kind": "p3a1_candidate",
        "canonical_name": str(candidate.get("preferred_name")),
        "metrics": {
            "current_main_text_story_count": len(main_story_ids & current_set),
            "current_liu_annotation_story_count": len(liu_story_ids & current_set),
            "current_liu_annotation_only_story_count": len((liu_story_ids - main_story_ids) & current_set),
            "current_weighted_story_coverage": _round(
                len(main_story_ids & current_set) + 0.5 * len((liu_story_ids - main_story_ids) & current_set)
            ),
            "corpus_story_count": len(story_ids),
            "mention_count": len(rows),
            "shishuo_mention_count": len(rows),
            "source_mention_count": len(rows),
            "direct_relation_to_current_count": 0,
            "shared_story_with_current_count": len(shared_story_ids),
            "unlock_story_count": len(shared_story_ids - current_set),
            "family_relation_to_current_count": 0,
        },
        "evidence_summary": {
            "exact_alias_count": exact_count,
            "contextual_alias_count": contextual_count,
            "high_confidence_mention_count": high_confidence,
            "source_evidence_count": len(set(identity_evidence + occurrence_evidence)),
            "source_layers": source_layers,
            "source_families": sorted(source_families),
            "stable_name_surfaces": [str(candidate.get("preferred_name"))],
            "alias_types": sorted({str(item.get("surface_type")) for item in candidate.get("surfaces", [])}),
            "evidence_keys": sorted(set(identity_evidence + occurrence_evidence)),
        },
        "all_story_ids": sorted(story_ids, key=lambda value: (corpus_order.get(value, 10**9), value)),
        "current_story_ids": sorted(story_ids & current_set, key=lambda value: (corpus_order.get(value, 10**9), value)),
        "shared_story_ids": sorted(shared_story_ids, key=lambda value: (corpus_order.get(value, 10**9), value)),
        "unlock_story_ids": sorted(shared_story_ids - current_set, key=lambda value: (corpus_order.get(value, 10**9), value)),
        "connected_current_person_ids": sorted({person_id for story_id in shared_story_ids for person_id in current_story_presence.get(story_id, set())}),
        "direct_relation_ids": [],
        "risk_flags": sorted(risk_flags),
        "stable_name_anchor": True,
        "alias_ids": [],
        "ambiguity_surface_count": sum(item.get("association_mode") == "ambiguous" for item in candidate.get("surfaces", [])),
    }


def _components(
    profile: Mapping[str, Any],
    maxima: Mapping[str, float],
) -> dict[str, float]:
    metrics = profile["metrics"]
    evidence = profile["evidence_summary"]
    identity = (
        0.30 * (1.0 if profile["stable_name_anchor"] else 0.0)
        + 0.25 * _bounded(evidence["exact_alias_count"], 3.0)
        + 0.20 * _bounded(evidence["high_confidence_mention_count"], 5.0)
        + 0.15 * _bounded(len(evidence["source_families"]), 2.0)
        + 0.10 * _bounded(evidence["source_evidence_count"], 4.0)
    )
    ambiguity_ratio = _bounded(
        profile["ambiguity_surface_count"],
        max(1.0, len(evidence["stable_name_surfaces"])),
    )
    non_high_ratio = _bounded(
        metrics["mention_count"] - evidence["high_confidence_mention_count"],
        max(1.0, metrics["mention_count"]),
    )
    risk = (
        0.25 * (0.0 if evidence["exact_alias_count"] else 1.0)
        + 0.25 * ambiguity_ratio
        + 0.20 * non_high_ratio
        + 0.15 * (0.0 if evidence["source_evidence_count"] else 1.0)
        + 0.15 * (0.0 if profile["stable_name_anchor"] else 1.0)
    )
    useful_alias = evidence["exact_alias_count"] + 0.4 * evidence["contextual_alias_count"]
    return {
        "current_story_coverage": _bounded(metrics["current_weighted_story_coverage"], maxima["current_story_coverage"]),
        "story_unlock_potential": _bounded(metrics["unlock_story_count"], maxima["story_unlock_potential"]),
        "current_network_connectivity": _bounded(metrics["direct_relation_to_current_count"], maxima["current_network_connectivity"]),
        "corpus_story_coverage": _bounded(metrics["corpus_story_count"], maxima["corpus_story_coverage"]),
        "identity_evidence_quality": _round(identity),
        "clan_bridge_value": _bounded(metrics["family_relation_to_current_count"], maxima["clan_bridge_value"]),
        "naming_richness": _bounded(useful_alias, maxima["naming_richness"]),
        "source_depth": _bounded(len(evidence["source_families"]), maxima["source_depth"]),
        "ambiguity_risk": _round(risk),
    }


def calculate_score(components: Mapping[str, float], weights: Mapping[str, float] = WEIGHTS) -> float:
    positive = sum(
        float(weights[name]) * float(components.get(name, 0.0))
        for name in weights
        if name != "ambiguity_risk"
    )
    value = 100.0 * (positive - float(weights["ambiguity_risk"]) * float(components.get("ambiguity_risk", 0.0)))
    return _round(max(0.0, min(100.0, value)))


def assign_tier(score: float, ambiguity_risk: float) -> str:
    if score >= 60.0 and ambiguity_risk <= 0.35:
        return "A"
    if score >= 40.0 and ambiguity_risk <= 0.60:
        return "B"
    if score >= 20.0 and ambiguity_risk <= 0.80:
        return "C"
    return "deferred"


def _sort_profiles(profiles: Sequence[Mapping[str, Any]]) -> list[Mapping[str, Any]]:
    return sorted(
        profiles,
        key=lambda profile: (
            -float(profile["score"]),
            -float(profile["components"]["current_story_coverage"]),
            -float(profile["components"]["story_unlock_potential"]),
            -float(profile["components"]["corpus_story_coverage"]),
            str(profile["canonical_name"]),
            str(profile["person_key"]),
        ),
    )


def build_analysis(root: Path = ROOT) -> tuple[dict[str, Any], dict[str, Any], str]:
    people = read_json(root, PEOPLE_PATH).get("people", [])
    current_person_ids = {
        str(person.get("person_id"))
        for person in people
        if isinstance(person, Mapping) and isinstance(person.get("person_id"), str)
    }
    aliases = read_json(root, ALIASES_PATH).get("aliases", [])
    aliases_by_id = {
        str(alias.get("alias_id")): alias
        for alias in aliases
        if isinstance(alias, Mapping) and isinstance(alias.get("alias_id"), str)
    }
    shishuo_mentions = read_json(root, SHISHUO_MENTIONS_PATH).get("mentions", [])
    jinshu_mentions = read_json(root, JINSHU_MENTIONS_PATH).get("mentions", [])
    corpus_entries = read_json(root, CORPUS_INDEX_PATH).get("entries", [])
    corpus_order = {
        str(entry.get("id")): int(entry.get("global_ordinal", 10**9))
        for entry in corpus_entries
        if isinstance(entry, Mapping) and isinstance(entry.get("id"), str)
    }
    relations = read_json(root, RELATIONS_PATH).get("records", [])
    person_story_index = read_json(root, PERSON_STORY_INDEX_PATH)
    story_chain_gold = read_json(root, STORY_CHAIN_PATH)
    person_sketch_source = read_json(root, PERSON_SKETCH_PATH)
    current_story_ids = _current_story_ids(root)
    current_story_set = set(current_story_ids)
    p3a1_document = read_json(root, P3A1_PATH) if (root / P3A1_PATH).is_file() else None
    p3a1_occurrences = (
        read_json(root, P3A1_OCCURRENCES_PATH).get("occurrences", [])
        if (root / P3A1_OCCURRENCES_PATH).is_file()
        else []
    )

    # Current resolved Person presence is the only basis for co-occurrence and
    # unlock calculations.  Candidate IDs are never inferred from surfaces.
    current_story_presence: dict[str, set[str]] = defaultdict(set)
    for mention in shishuo_mentions:
        person_id = mention.get("person_id")
        story_id = _story_id(mention)
        if isinstance(person_id, str) and person_id in current_person_ids and story_id:
            current_story_presence[story_id].add(person_id)

    direct_ids, connected_current, family_connections = _relation_metrics(root, current_person_ids)
    seeds = _candidate_seed(
        current_person_ids,
        aliases,
        shishuo_mentions,
        jinshu_mentions,
        relations,
    )
    eligible: list[dict[str, Any]] = []
    for seed in seeds.values():
        seed["current_story_presence"] = current_story_presence
        profile = _make_profile(
            seed,
            aliases_by_id=aliases_by_id,
            corpus_order=corpus_order,
            current_story_ids=current_story_ids,
            current_person_ids=current_person_ids,
            direct_relation_ids=direct_ids,
            connected_current=connected_current,
            family_connections=family_connections,
        )
        if profile is not None:
            eligible.append(profile)

    p3a1_eligible_count = 0
    if isinstance(p3a1_document, Mapping):
        for candidate in p3a1_document.get("candidates", []):
            profile = _make_p3a1_profile(
                candidate,
                p3a1_occurrences,
                corpus_order=corpus_order,
                current_story_ids=current_story_ids,
                current_story_presence=current_story_presence,
            )
            if profile is not None:
                eligible.append(profile)
                p3a1_eligible_count += 1

    maxima = {
        "current_story_coverage": _normalization_max(
            profile["metrics"]["current_weighted_story_coverage"] for profile in eligible
        ),
        "story_unlock_potential": _normalization_max(
            profile["metrics"]["unlock_story_count"] for profile in eligible
        ),
        "current_network_connectivity": _normalization_max(
            profile["metrics"]["direct_relation_to_current_count"] for profile in eligible
        ),
        "corpus_story_coverage": _normalization_max(
            profile["metrics"]["corpus_story_count"] for profile in eligible
        ),
        "clan_bridge_value": _normalization_max(
            profile["metrics"]["family_relation_to_current_count"] for profile in eligible
        ),
        "naming_richness": _normalization_max(
            profile["evidence_summary"]["exact_alias_count"]
            + 0.4 * profile["evidence_summary"]["contextual_alias_count"]
            for profile in eligible
        ),
        "source_depth": _normalization_max(
            len(profile["evidence_summary"]["source_families"]) for profile in eligible
        ),
    }
    scored: list[dict[str, Any]] = []
    for profile in eligible:
        components = _components(profile, maxima)
        score = calculate_score(components)
        tier = assign_tier(score, components["ambiguity_risk"])
        scored.append(
            {
                "person_key": "candidate:" + str(profile["source_person_id"]),
                "source_person_id": None if profile.get("identity_kind") == "p3a1_candidate" else profile["source_person_id"],
                "candidate_id": profile.get("candidate_id"),
                "identity_kind": profile.get("identity_kind", "existing_structured_candidate"),
                "canonical_name": profile["canonical_name"],
                "score": score,
                "tier": tier,
                "components": components,
                "metrics": profile["metrics"],
                "evidence_summary": profile["evidence_summary"],
                "top_current_story_ids": profile["current_story_ids"][:10],
                "top_unlock_story_ids": profile["unlock_story_ids"][:20],
                "connected_current_person_ids": profile["connected_current_person_ids"],
                "risk_flags": profile["risk_flags"],
                "direct_relation_ids": profile["direct_relation_ids"],
            }
        )
    scored = _sort_profiles(scored)
    for rank, candidate in enumerate(scored, start=1):
        candidate["rank"] = rank
    # Keep rank ordering as the first visible field in each row for review.
    scored = [
        {
            key: candidate[key]
            for key in (
                "rank", "person_key", "source_person_id", "candidate_id", "identity_kind", "canonical_name", "score", "tier",
                "components", "metrics", "evidence_summary", "top_current_story_ids",
                "top_unlock_story_ids", "connected_current_person_ids", "risk_flags",
                "direct_relation_ids",
            )
        }
        for candidate in scored
    ]

    unresolved = _collect_unresolved_surfaces(shishuo_mentions, current_person_ids, corpus_order)
    current_gaps: list[dict[str, Any]] = []
    candidate_ids = {
        str(mention.get("person_id"))
        for mention in shishuo_mentions
        if isinstance(mention.get("person_id"), str)
        and mention.get("person_id") not in current_person_ids
    }
    shishuo_by_story: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for mention in shishuo_mentions:
        story_id = _story_id(mention)
        if story_id in current_story_set:
            shishuo_by_story[story_id].append(mention)
    for story_id in current_story_ids:
        resolved_noncurrent = _sorted_unique(
            str(mention.get("person_id"))
            for mention in shishuo_by_story.get(story_id, [])
            if isinstance(mention.get("person_id"), str)
            and mention.get("person_id") not in current_person_ids
            and mention.get("person_id") in candidate_ids
        )
        if resolved_noncurrent:
            current_gaps.append(
                {
                    "story_id": story_id,
                    "unscoped_resolved_candidate_person_ids": resolved_noncurrent,
                }
            )
    if isinstance(p3a1_document, Mapping):
        current_gaps = [
            {
                "story_id": gap.get("story_id"),
                "unscoped_resolved_candidate_person_ids": [
                    str(item.get("candidate_id"))
                    for item in gap.get("candidates", [])
                    if isinstance(item, Mapping) and isinstance(item.get("candidate_id"), str)
                ],
            }
            for gap in p3a1_document.get("current_sc1_open_world_gaps", [])
            if isinstance(gap, Mapping) and gap.get("candidates")
        ]

    tiers = Counter(candidate["tier"] for candidate in scored)
    strong_identity_count = sum(
        candidate["components"]["identity_evidence_quality"] >= 0.6
        for candidate in scored
    )
    story_coverages = [candidate["metrics"]["corpus_story_count"] for candidate in scored]
    normalization = {
        "method": "bounded_linear_max_of_eligible_candidates",
        "count_components": maxima,
        "identity_evidence_quality": {
            "formula": "0.30 stable_name_anchor + 0.25 exact_alias/3 + 0.20 high_confidence_mentions/5 + 0.15 source_families/2 + 0.10 source_evidence/4",
            "bounds": "each signal is capped at 1.0",
        },
        "ambiguity_risk": {
            "formula": "0.25 no_exact_alias + 0.25 ambiguous_surface_ratio + 0.20 non_high_confidence_ratio + 0.15 no_structured_evidence + 0.15 no_stable_name_anchor",
            "bounds": "each signal is capped at 1.0",
        },
    }
    document = {
        "schema": 1,
        "stage": "p3a-person-expansion-ranking",
        "generated_from": [
            str(PEOPLE_PATH),
            str(ALIASES_PATH),
            str(SHISHUO_MENTIONS_PATH),
            str(JINSHU_MENTIONS_PATH),
            str(CORPUS_INDEX_PATH),
            str(RELATIONS_PATH),
            str(PERSON_STORY_INDEX_PATH),
            str(STORY_CHAIN_PATH),
            str(PERSON_SKETCH_PATH),
            str(SC1_BUNDLE_PATH),
            str(P3A1_PATH),
            str(P3A1_OCCURRENCES_PATH),
        ],
        "candidate_identity_policy": {
            "eligible_identity_source": "existing non-scoped person_id in structured data or P3A.1 strong open-world identity candidate",
            "stable_name_requirement": "at least one personal/courtesy/surname-plus-courtesy/orthographic alias or exact named surface",
            "unresolved_surfaces": "reported separately and never ranked as Persons",
            "scoped_person_ids_excluded": sorted(current_person_ids),
            "p3a1_source": str(P3A1_PATH),
            "p3a1_eligible_statuses": ["strong_candidate"],
        },
        "input_counts": {
            "scoped_person_count": len(current_person_ids),
            "shishuo_mention_count": len(shishuo_mentions),
            "jinshu_mention_count": len(jinshu_mentions),
            "canonical_story_count": len(corpus_entries),
            "current_sc1_story_count": len(current_story_ids),
            "current_person_story_link_count": int(person_story_index.get("reviewed_link_count", 0)),
            "sc0_gold_story_count": len(story_chain_gold.get("records", [])),
            "person_sketch_record_count": len(person_sketch_source.get("records", [])),
            "eligible_identity_seed_count": len(seeds),
            "p3a1_candidate_identity_count": int(
                p3a1_document.get("discovery_counts", {}).get("candidate_identity_count", 0)
                if isinstance(p3a1_document, Mapping) else 0
            ),
            "p3a1_strong_candidate_count": int(
                p3a1_document.get("discovery_counts", {}).get("strong_candidate_count", 0)
                if isinstance(p3a1_document, Mapping) else 0
            ),
            "p3a1_eligible_candidate_count": p3a1_eligible_count,
        },
        "weights": WEIGHTS,
        "normalization": normalization,
        "candidate_count": len(scored),
        "distribution": {
            "tier_a_count": tiers.get("A", 0),
            "tier_b_count": tiers.get("B", 0),
            "tier_c_count": tiers.get("C", 0),
            "deferred_count": tiers.get("deferred", 0),
            "candidates_in_current_sc1": sum(bool(candidate["top_current_story_ids"]) for candidate in scored),
            "median_corpus_story_coverage": _round(
                sorted(story_coverages)[len(story_coverages) // 2] if story_coverages else 0
            ),
            "max_corpus_story_coverage": max(story_coverages or [0]),
            "strong_identity_evidence_count": strong_identity_count,
        },
        "candidates": scored,
        "current_live_story_gaps": current_gaps,
        "unresolved_surface_count": len(unresolved),
        "unresolved_surface_artifact": str(UNRESOLVED_PATH),
        "notes": [
            "Current Story coverage and unlock potential use resolved Shishuo Person IDs only.",
            "Shared Story appearances are navigation opportunities, not Relation records.",
            "Only reviewed direct Relation records contribute to direct relation metrics; derived Relations are excluded.",
            "This artifact does not materialize Persons or alter any canonical identity, Mention, Relation, or publication data.",
            "P3A.1 candidate IDs remain review keys and are not production person_id values.",
        ],
    }
    unresolved_document = {
        "schema": 1,
        "stage": "p3a-unresolved-surface-audit",
        "generated_from": [str(SHISHUO_MENTIONS_PATH), str(CORPUS_INDEX_PATH), str(PEOPLE_PATH)],
        "not_person_candidates": True,
        "surface_count": len(unresolved),
        "surfaces": unresolved,
        "notes": [
            "These clusters are unresolved or scoped-only surfaces; they are not new Person identities.",
            "No identity is inferred from frequency, co-occurrence, Jinshu text, or semantic similarity.",
        ],
    }
    report = render_report(document, unresolved_document)
    return document, unresolved_document, report


def render_report(document: Mapping[str, Any], unresolved_document: Mapping[str, Any]) -> str:
    candidates = list(document.get("candidates", []))
    distribution = document.get("distribution", {})
    candidate_names = {
        str(candidate.get("candidate_id")): str(candidate.get("canonical_name"))
        for candidate in candidates
        if isinstance(candidate, Mapping) and isinstance(candidate.get("candidate_id"), str)
    }
    lines = [
        "# P3A Person Expansion Candidate Ranking",
        "",
        "> Decision-support analysis only. This report does not materialize Persons, relations, PersonStory links, or publication records.",
        "",
        "## Scope result",
        "",
        f"The current structured repository contains **{document['input_counts']['scoped_person_count']} scoped Persons** and **{document['input_counts']['canonical_story_count']} canonical Shishuo Stories**. The eligible non-scoped identity universe is **{document['candidate_count']}**; P3A.1 supplied **{document['input_counts'].get('p3a1_eligible_candidate_count', 0)}** strong open-world review keys.",
        "",
    ]
    if not candidates:
        lines.extend(
            [
                "No additional stable Person identity is currently available for ranking. All resolved Shishuo/Jinshu `person_id` values are already in the seven-Person registry; other recurring surfaces remain unresolved or point only to scoped Persons.",
                "",
                "This is an intentional stopping point: P3A does not turn a surface such as `王公` or `太傅` into a Person. An identity-resolution/materialization review pass is required before a P3B wave can be recommended.",
                "",
            ]
        )
    lines.extend(
        [
            "## Ranking dimensions and weights",
            "",
            "The composite is deterministic and interpretable:",
            "",
            "`score = 100 × (positive weighted components − 0.15 × ambiguity_risk)`",
            "",
            "Positive components use bounded linear normalization. Count dimensions are divided by the largest value in the eligible candidate universe and capped at 1. Identity evidence and ambiguity use the documented bounded sub-formulas in the generated JSON.",
            "",
            "| Dimension | Weight | Meaning |",
            "| --- | ---: | --- |",
        ]
    )
    labels = {
        "current_story_coverage": "Current SC1 Story coverage",
        "story_unlock_potential": "Potentially connected non-SC1 Stories",
        "current_network_connectivity": "Reviewed direct Relation connectivity",
        "corpus_story_coverage": "Full Shishuo Story coverage",
        "identity_evidence_quality": "Identity/evidence quality",
        "clan_bridge_value": "Supported family/clan bridge value",
        "naming_richness": "Useful historical naming forms",
        "source_depth": "Distinct source-family depth",
        "ambiguity_risk": "Ambiguity penalty",
    }
    for key, weight in document["weights"].items():
        lines.append(f"| {labels[key]} | {weight:.2f} | {key} |")
    lines.extend(
        [
            "",
            "Main-text Story presence receives more current-coverage weight than Liu-annotation-only presence. Shared Stories are kept separate from direct Relations and never create a Relation record.",
            "",
            "## Distribution",
            "",
            f"- Candidate identities: **{document['candidate_count']}**",
            f"- Tier A / B / C / deferred: **{distribution.get('tier_a_count', 0)} / {distribution.get('tier_b_count', 0)} / {distribution.get('tier_c_count', 0)} / {distribution.get('deferred_count', 0)}**",
            f"- Candidates in current SC1: **{distribution.get('candidates_in_current_sc1', 0)}**",
            f"- Median / maximum corpus Story coverage: **{distribution.get('median_corpus_story_coverage', 0)} / {distribution.get('max_corpus_story_coverage', 0)}**",
            f"- Strong identity-evidence candidates: **{distribution.get('strong_identity_evidence_count', 0)}**",
            "",
            "## Top candidates",
            "",
        ]
    )
    if candidates:
        for candidate in candidates[:15]:
            metrics = candidate["metrics"]
            lines.extend(
                [
                    f"### {candidate['canonical_name']}",
                    "",
                    f"Rank: **{candidate['rank']}** · Score: **{candidate['score']:.2f}** · Tier: **{candidate['tier']}**",
                    "",
                    f"- Current Stories: {metrics['current_main_text_story_count']} main-text, {metrics['current_liu_annotation_only_story_count']} Liu-annotation-only",
                    f"- Corpus Stories: {metrics['corpus_story_count']} · unlock potential: {metrics['unlock_story_count']}",
                    f"- Direct reviewed Relations to current scope: {metrics['direct_relation_to_current_count']} · shared Stories: {metrics['shared_story_with_current_count']}",
                    f"- Risks: {', '.join(candidate['risk_flags']) if candidate['risk_flags'] else 'none recorded'}",
                    "",
                ]
            )
    else:
        lines.extend(["There are no ranked identities, so a top-15 list cannot be truthfully produced.", ""])

    lines.extend(["## Current live Story gaps", ""])
    gaps = document.get("current_live_story_gaps", [])
    if gaps:
        for gap in gaps:
            labels = [
                f"{candidate_names.get(candidate_id, candidate_id)} (`{candidate_id}`)"
                for candidate_id in gap["unscoped_resolved_candidate_person_ids"]
            ]
            lines.append(
                f"- `{gap['story_id']}` — {', '.join(labels)}"
            )
    else:
        lines.append("No supported open-world candidate appears in the current SC1 Stories. The visible gaps are unresolved surfaces, not stable candidate identities.")
    lines.extend(["", "## Unresolved surface audit", ""])
    lines.append("These are review clusters, not ranked Persons. Frequency alone does not establish identity.")
    lines.extend(["", "| Surface | Mentions | Stories | Existing candidate IDs | Reason |", "| --- | ---: | ---: | --- | --- |"])
    for row in unresolved_document.get("surfaces", []):
        ids = ", ".join(row["candidate_person_ids"]) or "—"
        lines.append(f"| {row['surface']} | {row['mention_count']} | {row['story_count']} | {ids} | {row['reason_code']} |")
    if not unresolved_document.get("surfaces"):
        lines.append("| — | 0 | 0 | — | no recurring unresolved surfaces |")
    lines.extend(
        [
            "",
            "## Recommended P3B wave",
            "",
            "This is a review recommendation only; no Person is materialized by P3A. Recommend the top **30** ranked P3A.1-backed candidates for a staged P3B review:",
            "",
            "- Wave 1: ranks 1–10, prioritizing current SC1 gaps and the strongest Story traversal payoff.",
            "- Wave 2: ranks 11–30, subject to identity/evidence review before materialization.",
            "",
            "The exact wave boundary remains editorial: contextual surface associations, single-source biographies, and candidate identity risks must be reviewed before any P3B registry change.",
            "",
            "## Method and safeguards",
            "",
            "- Candidate keys are derived analysis keys (`candidate:<existing-source-id>` or `candidate:<p3a1-candidate-id>`), not production Person IDs.",
            "- Current Story coverage, corpus coverage, and unlock Stories use resolved Shishuo mentions only.",
            "- Direct connectivity counts only `reviewed` + `direct` Relation records. Derived Relations and co-occurrence are not counted as direct edges.",
            "- Jinshu evidence can strengthen source depth/evidence for an eligible identity, but Jinshu text does not create Shishuo Story links.",
            "- P3A.1 strong candidates are ranking inputs only; no Sanguozhi data, external research, canonical text, Mention, Relation, PersonStory, punctuation, or frontend data is changed by P3A.",
            "",
        ]
    )
    return "\n".join(lines)


def build(root: Path = ROOT) -> tuple[Path, Path, Path]:
    document, unresolved, report = build_analysis(root)
    write_json(root, P3A_PATH, document)
    write_json(root, UNRESOLVED_PATH, unresolved)
    report_path = root / REPORT_PATH
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(report, encoding="utf-8")
    return root / P3A_PATH, root / UNRESOLVED_PATH, report_path


if __name__ == "__main__":
    paths = build()
    for path in paths:
        print(path)
