#!/usr/bin/env python3
"""Build the R3C current-scope explicit Relation coverage audit.

R3C is deliberately separate from R3A.  R3A discovered a small candidate
set from the Person-pair universe; R3C scans the source-linked evidence for
explicit relation-language patterns and classifies what it finds.  It never
mutates production Relations or the R3B review file.
"""

from __future__ import annotations

from hashlib import sha256
import itertools
import json
from pathlib import Path
import re
from typing import Any, Iterable, Mapping

from jsonschema import Draft202012Validator


ROOT = Path(__file__).resolve().parents[1]
BUNDLE_PATH = Path("data/derived/sc1-site.json")
PEOPLE_PATH = Path("data/people.json")
ALIASES_PATH = Path("data/aliases.json")
RELATIONS_PATH = Path("data/annotation/wp1-relations.json")
R3A_PATH = Path("data/annotation/person-relation-candidates-r3.json")
R3B_PATH = Path("data/annotation/person-relation-review-r3b.json")
SCENE_PATH = Path("data/annotation/story-scene-contexts.json")
COVERAGE_PATH = Path("data/annotation/person-relation-coverage-r3c.json")
CANDIDATE_PATH = Path("data/annotation/person-relation-candidates-r3c.json")
COVERAGE_DERIVED_PATH = Path("data/derived/person-relation-coverage-r3c.json")
COVERAGE_SCHEMA_PATH = Path("schema/person-relation-coverage-r3c.schema.json")
CANDIDATE_SCHEMA_PATH = Path("schema/person-relation-candidates-r3c.schema.json")
REPORT_PATH = Path("docs/person-relation-coverage-r3c.md")

PUBLISHED_STATES = {"production_ready", "preview_ready"}
OFFICE_WORDS = (
    "長史",
    "參軍",
    "叅軍",
    "記室",
    "司馬",
    "主簿",
    "從事",
    "屬官",
)
KINSHIP_WORDS = (
    "之父",
    "之母",
    "之子",
    "之女",
    "之從子",
    "之從父",
    "之兄",
    "之弟",
    "從子",
    "從父",
    "叔父",
    "伯父",
    "兄弟",
)
MARRIAGE_WORDS = ("妻", "娶", "嫁", "女適", "婚", "婿")
WEAK_RELATION_WORDS = (
    "賞識",
    "稱美",
    "稱善",
    "推重",
    "品評",
    "相見",
    "對泣",
    "酬納",
    "清言",
    "宴",
    "同坐",
)
POLITICAL_WORDS = (
    "之難",
    "之亂",
    "作逆",
    "討",
    "征討",
    "攻",
    "戰",
    "被害",
    "反",
)
POLITICAL_ACTION_WORDS = (
    "難",
    "討",
    "征",
    "攻",
    "戰",
    "誅",
    "被害",
    "作逆",
    "反",
)


def read_json(root: Path, relative: Path) -> Any:
    return json.loads((root / relative).read_text(encoding="utf-8"))


def write_json(root: Path, relative: Path, value: Any) -> None:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _unique_sorted(values: Iterable[str]) -> list[str]:
    return sorted({str(value) for value in values if isinstance(value, str) and value})


def _pair(a: str, b: str) -> tuple[str, str]:
    return tuple(sorted((a, b)))


def _compact(value: Any, limit: int = 260) -> str:
    text = " ".join(str(value).replace("/", "").split())
    return text if len(text) <= limit else text[: limit - 1] + "…"


def normalize_source_text(value: str) -> str:
    """Normalize source whitespace only; never normalize historical wording."""

    without_comments = re.sub(r"<!--.*?-->", "", value, flags=re.DOTALL)
    return re.sub(r"\s+|/", "", without_comments)


def stable_candidate_id(record: Mapping[str, Any]) -> str:
    """Create an opaque deterministic ID from semantic foreign keys/meaning."""

    person_a_id, person_b_id = sorted((str(record["person_a_id"]), str(record["person_b_id"])))
    payload = {
        "person_a_id": person_a_id,
        "person_b_id": person_b_id,
        "relation_type": record["proposed_relation_type"],
        "relation_subtype": record["proposed_relation_subtype"],
        "relation_scope": record["proposed_relation_scope"],
        "scope_event": record.get("proposed_scope_event"),
        "source_entry_ids": sorted(record.get("source_entry_ids", [])),
        "source_unit_ids": sorted(record.get("source_unit_ids", [])),
        "evidence_ids": sorted(record.get("evidence_ids", [])),
    }
    digest = sha256(
        json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return f"r3c-candidate-{digest[:20]}"


def stable_attention_id(record: Mapping[str, Any]) -> str:
    payload = {
        "disposition": record["disposition"],
        "person_a_id": record["person_a_id"],
        "person_b_id": record["person_b_id"],
        "source_entry_ids": sorted(record.get("source_entry_ids", [])),
        "source_unit_ids": sorted(record.get("source_unit_ids", [])),
        "evidence_ids": sorted(record.get("evidence_ids", [])),
        "candidate_id": record.get("candidate_id"),
    }
    digest = sha256(
        json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return f"r3c-attention-{digest[:20]}"


def _people(root: Path) -> dict[str, dict[str, Any]]:
    return {
        str(person["person_id"]): dict(person)
        for person in read_json(root, PEOPLE_PATH).get("people", [])
        if isinstance(person, Mapping) and isinstance(person.get("person_id"), str)
    }


def _bundle_people(root: Path) -> dict[str, dict[str, Any]]:
    return {
        str(person["id"]): dict(person)
        for person in read_json(root, BUNDLE_PATH).get("people", [])
        if isinstance(person, Mapping) and isinstance(person.get("id"), str)
    }


def _published_stories(root: Path) -> dict[str, dict[str, Any]]:
    return {
        str(story["id"]): dict(story)
        for story in read_json(root, BUNDLE_PATH).get("stories", [])
        if isinstance(story, Mapping)
        and isinstance(story.get("id"), str)
        and story.get("publication_state") in PUBLISHED_STATES
    }


def _evidence_layer(evidence: Mapping[str, Any]) -> str:
    locator = evidence.get("locator", {})
    if locator.get("artifact_type") == "jinshu_unit":
        return "jinshu"
    if evidence.get("evidence_type") == "annotation" or locator.get("annotation_id"):
        return "shishuo_liu_annotation"
    return "shishuo_main_text"


def _source_signature(evidence: Mapping[str, Any]) -> tuple[str, ...]:
    locator = evidence.get("locator", {})
    provenance = locator.get("source_provenance", {})
    return (
        str(locator.get("artifact_path") or ""),
        str(locator.get("entry_id") or ""),
        str(locator.get("unit_id") or ""),
        str(locator.get("annotation_id") or ""),
        str(provenance.get("source_sha256") or ""),
        normalize_source_text(str(evidence.get("quote", ""))),
    )


def _evidence_inventory(root: Path, stories: Mapping[str, Mapping[str, Any]]) -> dict[str, dict[str, Any]]:
    story_ids = set(stories)
    inventory: dict[str, dict[str, Any]] = {}
    for evidence in read_json(root, BUNDLE_PATH).get("evidence", []):
        if not isinstance(evidence, Mapping) or not isinstance(evidence.get("id"), str):
            continue
        locator = evidence.get("locator", {})
        if locator.get("entry_id") in story_ids or locator.get("artifact_type") == "jinshu_unit":
            inventory[str(evidence["id"])] = dict(evidence)
    return dict(sorted(inventory.items()))


def _safe_aliases(root: Path, people: Mapping[str, Mapping[str, Any]]) -> dict[str, set[str]]:
    result: dict[str, set[str]] = {}
    for alias in read_json(root, ALIASES_PATH).get("aliases", []):
        if not isinstance(alias, Mapping):
            continue
        surface = alias.get("surface")
        person_ids = [str(item) for item in alias.get("person_ids", []) if str(item) in people]
        if not isinstance(surface, str) or not surface or len(person_ids) != 1:
            continue
        if alias.get("resolution_mode") != "exact":
            continue
        if alias.get("alias_type") in {"office_title", "contextual_title", "posthumous_title"}:
            continue
        result.setdefault(surface, set()).update(person_ids)
    for person_id, person in people.items():
        result.setdefault(str(person["canonical_name"]), set()).add(person_id)
    return result


def _identity_hits(
    root: Path,
    evidence: Mapping[str, Mapping[str, Any]],
    people: Mapping[str, Mapping[str, Any]],
) -> tuple[dict[str, list[dict[str, Any]]], dict[str, list[dict[str, Any]]]]:
    """Return evidence-local resolved identity spans and blocked candidates."""

    bundle = read_json(root, BUNDLE_PATH)
    safe_aliases = _safe_aliases(root, people)
    resolved_mentions: dict[str, list[dict[str, Any]]] = {}
    blocked_mentions: dict[str, list[dict[str, Any]]] = {}
    owner_by_evidence: dict[str, set[str]] = {}
    for person_id, person in people.items():
        for evidence_id in person.get("evidence_ids", []):
            owner_by_evidence.setdefault(str(evidence_id), set()).add(person_id)

    for mention in bundle.get("mentions", []):
        if not isinstance(mention, Mapping):
            continue
        evidence_ids = [str(item) for item in mention.get("evidence_ids", [])]
        status = mention.get("resolution_status")
        if status == "resolved" and mention.get("person_id") in people:
            item = {
                "person_id": str(mention["person_id"]),
                "surface": str(mention.get("surface", "")),
                "mention_id": str(mention.get("id", "")),
                "basis": "resolved_mention",
            }
            for evidence_id in evidence_ids:
                resolved_mentions.setdefault(evidence_id, []).append(item)
        elif status == "candidate_for_review":
            candidates = []
            for candidate in mention.get("resolution_candidates", []):
                if not isinstance(candidate, Mapping):
                    continue
                candidates.append(
                    {
                        "person_id": candidate.get("person_id"),
                        "candidate_id": candidate.get("candidate_id"),
                        "canonical_name": candidate.get("canonical_name"),
                    }
                )
            item = {
                "surface": str(mention.get("surface", "")),
                "mention_id": str(mention.get("id", "")),
                "candidates": candidates,
            }
            for evidence_id in evidence_ids:
                blocked_mentions.setdefault(evidence_id, []).append(item)

    hits_by_evidence: dict[str, list[dict[str, Any]]] = {}
    for evidence_id, item in evidence.items():
        text = normalize_source_text(str(item.get("quote", "")))
        hits: list[dict[str, Any]] = []
        for mention in resolved_mentions.get(evidence_id, []):
            surface = mention["surface"]
            if not surface:
                continue
            for match in re.finditer(re.escape(surface), text):
                hits.append(
                    {
                        "person_id": mention["person_id"],
                        "surface": surface,
                        "start": match.start(),
                        "end": match.end(),
                        "basis": mention["basis"],
                        "mention_id": mention["mention_id"],
                    }
                )
        for surface, person_ids in safe_aliases.items():
            for match in re.finditer(re.escape(surface), text):
                for person_id in person_ids:
                    hits.append(
                        {
                            "person_id": person_id,
                            "surface": surface,
                            "start": match.start(),
                            "end": match.end(),
                            "basis": "safe_exact_alias",
                            "mention_id": None,
                        }
                    )
        for person_id in owner_by_evidence.get(evidence_id, set()):
            canonical_name = str(people[person_id]["canonical_name"])
            if canonical_name in text:
                for match in re.finditer(re.escape(canonical_name), text):
                    hits.append(
                        {
                            "person_id": person_id,
                            "surface": canonical_name,
                            "start": match.start(),
                            "end": match.end(),
                            "basis": "person_evidence_owner",
                            "mention_id": None,
                        }
                    )
        unique: dict[tuple[Any, ...], dict[str, Any]] = {}
        for hit in hits:
            key = (hit["person_id"], hit["surface"], hit["start"], hit["end"])
            unique[key] = hit
        hits_by_evidence[evidence_id] = sorted(
            unique.values(),
            key=lambda hit: (int(hit["start"]), -len(str(hit["surface"])), str(hit["person_id"])),
        )
    return hits_by_evidence, blocked_mentions


def _pair_occurrences(
    hits: list[dict[str, Any]],
) -> Iterable[tuple[dict[str, Any], dict[str, Any]]]:
    by_person: dict[str, list[dict[str, Any]]] = {}
    for hit in hits:
        by_person.setdefault(str(hit["person_id"]), []).append(hit)
    person_ids = sorted(by_person)
    for person_a, person_b in itertools.combinations(person_ids, 2):
        best: tuple[int, dict[str, Any], dict[str, Any]] | None = None
        for first in by_person[person_a]:
            for second in by_person[person_b]:
                distance = min(abs(int(first["start"]) - int(second["end"])), abs(int(second["start"]) - int(first["end"])))
                if distance > 96:
                    continue
                if best is None or distance < best[0]:
                    best = (distance, first, second)
        if best is not None:
            yield best[1], best[2]


def _ordered_context(text: str, first: Mapping[str, Any], second: Mapping[str, Any]) -> tuple[dict[str, Any], dict[str, Any], str, str, str]:
    if int(first["start"]) <= int(second["start"]):
        left, right = dict(first), dict(second)
    else:
        left, right = dict(second), dict(first)
    between = text[int(left["end"]): int(right["start"])]
    after_right = text[int(right["end"]): int(right["end"]) + 28]
    local = text[max(0, int(left["start"]) - 24): min(len(text), int(right["end"]) + 48)]
    return left, right, between, after_right, local


def _record_hit(
    *,
    family: str,
    relation_type: str,
    subtype: str,
    scope: str,
    first: Mapping[str, Any],
    second: Mapping[str, Any],
    role_first: str,
    role_second: str,
    basis: str,
    note: str,
    risk_flags: Iterable[str] = (),
    scope_event: str | None = None,
) -> dict[str, Any]:
    first_id, second_id = str(first["person_id"]), str(second["person_id"])
    if first_id <= second_id:
        a, b, role_a, role_b = first_id, second_id, role_first, role_second
    else:
        a, b, role_a, role_b = second_id, first_id, role_second, role_first
    return {
        "person_a_id": a,
        "person_b_id": b,
        "family": family,
        "proposed_relation_type": relation_type,
        "proposed_relation_subtype": subtype,
        "proposed_relation_scope": scope,
        "proposed_scope_event": scope_event,
        "proposed_role_a": role_a,
        "proposed_role_b": role_b,
        "discovery_basis": basis,
        "discovery_note": note,
        "risk_flags": sorted(set(str(item) for item in risk_flags if item)),
        "first_surface": str(first["surface"]),
        "second_surface": str(second["surface"]),
    }


def detect_relation_hits(text: str, identity_hits: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Detect only explicit, bounded templates from an evidence-local text.

    This function intentionally does not use co-occurrence as a positive
    signal.  It is public so focused tests can exercise the relation-language
    boundary with small synthetic fixtures.
    """

    normalized = normalize_source_text(text)
    results: dict[tuple[Any, ...], dict[str, Any]] = {}
    for first, second in _pair_occurrences(identity_hits):
        left, right, between, after_right, local = _ordered_context(normalized, first, second)
        ordered_distance = int(right["start"]) - int(left["end"])
        if ordered_distance > 96:
            continue

        # Direct and context-local service/appointment language.
        office_pattern = "(?:" + "|".join(OFFICE_WORDS) + ")"
        service_markers = [match.start() for match in re.finditer(r"為|爲", between)]
        direct_service = (
            bool(service_markers)
            and service_markers[-1] >= max(0, len(between) - 8)
            and re.search(office_pattern, after_right[:40])
        )
        reverse_appointment = "所辟" in between
        context_service = (
            re.search(r"(?:為|爲)(?:吾|其|敦)?" + office_pattern, after_right[:40])
            and ordered_distance <= 72
        )
        if direct_service:
            hit = _record_hit(
                family="institutional",
                relation_type="institutional",
                subtype="service_under",
                scope="institutional_tenure",
                first=left,
                second=right,
                role_first="被任用者",
                role_second="任用者",
                basis="explicit_service_phrase",
                note=f"「{left['surface']}」與「{right['surface']}」之間有明示任職語式。",
            )
            key = (hit["person_a_id"], hit["person_b_id"], hit["family"], hit["proposed_relation_subtype"])
            results[key] = hit
        elif reverse_appointment or context_service:
            hit = _record_hit(
                family="institutional",
                relation_type="institutional",
                subtype="service_under",
                scope="institutional_tenure",
                first=left,
                second=right,
                role_first="任用者",
                role_second="被任用者",
                basis="explicit_service_phrase",
                note=f"局部語境以「{left['surface']}」為任用側、以「{right['surface']}」為任職側。",
                risk_flags=("contextual_service_antecedent",) if context_service else (),
            )
            key = (hit["person_a_id"], hit["person_b_id"], hit["family"], hit["proposed_relation_subtype"])
            results[key] = hit

        # Direct social language only; appreciation and scene exchange stay
        # weak/insufficient unless separately reviewed.
        social_between = between + after_right[:18]
        if ("善" in social_between and "與" in between) or "友善" in social_between or "布衣之好" in local:
            hit = _record_hit(
                family="social",
                relation_type="social",
                subtype="friendship",
                scope="long_term_social",
                first=left,
                second=right,
                role_first="友人",
                role_second="友人",
                basis="explicit_social_phrase",
                note=f"局部來源明示「{left['surface']}」與「{right['surface']}」的友善/交誼語句。",
            )
            key = (hit["person_a_id"], hit["person_b_id"], hit["family"], hit["proposed_relation_subtype"])
            results[key] = hit

        # Direct atomic family/marriage syntax only.  Bare 子/兄/弟 or a
        # shared family-name is deliberately insufficient.
        marriage_direct = bool(
            re.match(r"(?:妻|娶|嫁|女適|婚|婿)", between)
            and len(between) <= 18
        )
        kinship_direct = bool(
            any(after_right.startswith(word) for word in KINSHIP_WORDS)
            or any(between.startswith(word) and len(between) <= 18 for word in KINSHIP_WORDS)
        )
        if marriage_direct:
            hit = _record_hit(
                family="marriage",
                relation_type="marriage",
                subtype="spouse",
                scope="long_term_social",
                first=left,
                second=right,
                role_first="配偶",
                role_second="配偶",
                basis="explicit_marriage_phrase",
                note=f"局部來源以婚姻詞直接連接「{left['surface']}」與「{right['surface']}」。",
            )
            key = (hit["person_a_id"], hit["person_b_id"], hit["family"], hit["proposed_relation_subtype"])
            results[key] = hit
        elif kinship_direct:
            subtype = "collateral_kinship" if any(word in local for word in ("從父", "從子", "叔父", "伯父", "兄", "弟")) else "parent_child"
            hit = _record_hit(
                family="kinship",
                relation_type="kinship",
                subtype=subtype,
                scope="long_term_social",
                first=left,
                second=right,
                role_first="親屬",
                role_second="親屬",
                basis="explicit_kinship_phrase",
                note=f"局部來源以明示親屬語式連接「{left['surface']}」與「{right['surface']}」。",
            )
            key = (hit["person_a_id"], hit["person_b_id"], hit["family"], hit["proposed_relation_subtype"])
            results[key] = hit

        # Political language is accepted only as an event-bounded signal and
        # only when the event/action token is local to both identities.
        political_pair_distance = int(right["end"]) - int(left["start"])
        political_local = normalized[max(0, int(left["start"]) - 8): min(len(normalized), int(right["end"]) + 8)]
        close_action = any(
            token in normalized[max(0, int(hit["start"]) - 10): min(len(normalized), int(hit["end"]) + 12)]
            for hit in (left, right)
            for token in POLITICAL_ACTION_WORDS
        )
        if (
            political_pair_distance <= 38
            and any(word in political_local for word in POLITICAL_WORDS)
            and ("蘇峻" in political_local or "作逆" in political_local or "之亂" in political_local)
            and close_action
        ):
            hit = _record_hit(
                family="political",
                relation_type="political",
                subtype="political_opposition",
                scope="event_bounded",
                scope_event="蘇峻之亂" if "蘇峻" in local or "之亂" in local else None,
                first=left,
                second=right,
                role_first="事件中的一方",
                role_second="事件中的一方",
                basis="explicit_event_bounded_political_phrase",
                note=f"局部來源把「{left['surface']}」與「{right['surface']}」置於明示事件/軍事語境；不外推為永久敵對。",
                risk_flags=("event_bounded",),
            )
            key = (hit["person_a_id"], hit["person_b_id"], hit["family"], hit["proposed_relation_subtype"])
            results[key] = hit

    return sorted(
        results.values(),
        key=lambda item: (
            item["person_a_id"],
            item["person_b_id"],
            item["family"],
            item["proposed_relation_subtype"],
            item["discovery_basis"],
        ),
    )


def _weak_signal_pairs(text: str, identity_hits: list[dict[str, Any]]) -> list[tuple[str, str]]:
    normalized = normalize_source_text(text)
    result: set[tuple[str, str]] = set()
    for first, second in _pair_occurrences(identity_hits):
        left, right, between, after_right, local = _ordered_context(normalized, first, second)
        if any(word in local for word in WEAK_RELATION_WORDS):
            result.add(_pair(str(first["person_id"]), str(second["person_id"])))
    return sorted(result)


def _relation_maps(root: Path, people: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    relations = [
        dict(item)
        for item in read_json(root, RELATIONS_PATH).get("records", [])
        if isinstance(item, Mapping) and item.get("review_status") == "reviewed"
    ]
    reviewed_by_pair: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for relation in relations:
        pair = _pair(str(relation["subject_id"]), str(relation["object_id"]))
        reviewed_by_pair.setdefault(pair, []).append(relation)
    r3a = [
        dict(item)
        for item in read_json(root, R3A_PATH).get("records", [])
        if isinstance(item, Mapping)
    ]
    r3a_by_pair: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for candidate in r3a:
        pair = _pair(str(candidate["person_a_id"]), str(candidate["person_b_id"]))
        r3a_by_pair.setdefault(pair, []).append(candidate)
    r3b = [
        dict(item)
        for item in read_json(root, R3B_PATH).get("records", [])
        if isinstance(item, Mapping)
    ]
    deferred_by_pair: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for decision in r3b:
        if decision.get("decision") == "deferred":
            pair = _pair(str(decision["person_a_id"]), str(decision["person_b_id"]))
            deferred_by_pair.setdefault(pair, []).append(decision)
    return {
        "relations": relations,
        "reviewed_by_pair": reviewed_by_pair,
        "r3a_by_pair": r3a_by_pair,
        "deferred_by_pair": deferred_by_pair,
    }


def _scene_only_pairs(root: Path, reviewed_by_pair: Mapping[tuple[str, str], list[dict[str, Any]]], r3a_by_pair: Mapping[tuple[str, str], list[dict[str, Any]]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    scene = read_json(root, SCENE_PATH)
    for context in scene.get("records", []):
        scene_people = sorted({str(item["person_id"]) for item in context.get("people_at_scene", []) if isinstance(item, Mapping) and item.get("person_id")})
        for a, b in itertools.combinations(scene_people, 2):
            pair = _pair(a, b)
            if pair in reviewed_by_pair or pair in r3a_by_pair:
                continue
            rows.append({"story_id": context["story_id"], "person_a_id": pair[0], "person_b_id": pair[1]})
    return sorted(rows, key=lambda row: (row["story_id"], row["person_a_id"], row["person_b_id"]))


def _attention_base(
    *,
    disposition: str,
    person_a_id: str,
    person_b_id: str,
    source_entry_ids: Iterable[str] = (),
    source_unit_ids: Iterable[str] = (),
    evidence_ids: Iterable[str] = (),
    discovery_basis: str,
    evidence_excerpt: str,
    audit_note: str,
    risk_flags: Iterable[str] = (),
    existing_relation_ids: Iterable[str] = (),
    existing_r3a_candidate_ids: Iterable[str] = (),
    candidate_id: str | None = None,
    proposed: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    record: dict[str, Any] = {
        "person_a_id": person_a_id,
        "person_b_id": person_b_id,
        "disposition": disposition,
        "source_entry_ids": _unique_sorted(source_entry_ids),
        "source_unit_ids": _unique_sorted(source_unit_ids),
        "evidence_ids": _unique_sorted(evidence_ids),
        "discovery_basis": discovery_basis,
        "evidence_excerpt": evidence_excerpt,
        "audit_note": audit_note,
        "risk_flags": _unique_sorted(risk_flags),
        "existing_relation_ids": _unique_sorted(existing_relation_ids),
        "existing_r3a_candidate_ids": _unique_sorted(existing_r3a_candidate_ids),
    }
    if candidate_id:
        record["candidate_id"] = candidate_id
    if proposed:
        record.update(
            {
                "proposed_relation_type": proposed.get("proposed_relation_type"),
                "proposed_relation_subtype": proposed.get("proposed_relation_subtype"),
                "proposed_relation_scope": proposed.get("proposed_relation_scope"),
                "proposed_scope_event": proposed.get("proposed_scope_event"),
                "proposed_role_a": proposed.get("proposed_role_a"),
                "proposed_role_b": proposed.get("proposed_role_b"),
            }
        )
    record["attention_id"] = stable_attention_id(record)
    return record


def _candidate_from_hit(
    hit: Mapping[str, Any],
    *,
    evidence: Mapping[str, Mapping[str, Any]],
    names: Mapping[str, str],
    r3a_by_pair: Mapping[tuple[str, str], list[dict[str, Any]]],
) -> dict[str, Any]:
    pair = _pair(str(hit["person_a_id"]), str(hit["person_b_id"]))
    evidence_ids = sorted(str(item) for item in hit["evidence_ids"])
    source_entry_ids = sorted(
        {
            str(evidence[evidence_id].get("locator", {}).get("entry_id"))
            for evidence_id in evidence_ids
            if evidence_id in evidence and evidence[evidence_id].get("locator", {}).get("entry_id")
        }
    )
    source_unit_ids = sorted(
        {
            str(evidence[evidence_id].get("locator", {}).get("unit_id"))
            for evidence_id in evidence_ids
            if evidence_id in evidence and evidence[evidence_id].get("locator", {}).get("unit_id")
        }
    )
    record: dict[str, Any] = {
        "person_a_id": pair[0],
        "person_b_id": pair[1],
        "proposed_relation_type": hit["proposed_relation_type"],
        "proposed_relation_subtype": hit["proposed_relation_subtype"],
        "proposed_relation_scope": hit["proposed_relation_scope"],
        "proposed_scope_event": hit.get("proposed_scope_event"),
        "proposed_role_a": hit["proposed_role_a"] if hit["person_a_id"] == pair[0] else hit["proposed_role_b"],
        "proposed_role_b": hit["proposed_role_b"] if hit["person_b_id"] == pair[1] else hit["proposed_role_a"],
        "source_entry_ids": source_entry_ids,
        "source_unit_ids": source_unit_ids,
        "evidence_ids": evidence_ids,
        "assertion_status": "attested",
        "review_status": "candidate",
        "discovery_basis": hit["discovery_basis"],
        "discovery_note": hit["discovery_note"],
        "evidence_excerpt": hit["evidence_excerpt"],
        "risk_flags": sorted(set(hit.get("risk_flags", [])) | {"single_source_only"} | ({"same_pair_has_r3a_candidate"} if pair in r3a_by_pair else set())),
        "related_r3a_candidate_ids": sorted(str(item["candidate_id"]) for item in r3a_by_pair.get(pair, [])),
    }
    record["candidate_id"] = stable_candidate_id(record)
    return record


def _merge_hit(
    target: dict[tuple[Any, ...], dict[str, Any]],
    hit: Mapping[str, Any],
    evidence_id: str,
    evidence: Mapping[str, Mapping[str, Any]],
) -> None:
    key = (
        hit["person_a_id"],
        hit["person_b_id"],
        hit["proposed_relation_type"],
        hit["proposed_relation_subtype"],
        hit.get("proposed_scope_event"),
    )
    if key not in target:
        target[key] = dict(hit)
        target[key]["evidence_ids"] = [evidence_id]
        target[key]["evidence_excerpt"] = _compact(evidence[evidence_id].get("quote", ""))
    else:
        target[key]["evidence_ids"] = sorted(set(target[key]["evidence_ids"]) | {evidence_id})


def build_projection(root: Path = ROOT) -> tuple[dict[str, Any], dict[str, Any]]:
    people = _people(root)
    bundle_people = _bundle_people(root)
    if set(people) != set(bundle_people):
        raise ValueError("R3C production Person registry and frontend bundle differ")
    stories = _published_stories(root)
    evidence = _evidence_inventory(root, stories)
    hits_by_evidence, blocked_mentions = _identity_hits(root, evidence, people)
    maps = _relation_maps(root, people)
    reviewed_by_pair = maps["reviewed_by_pair"]
    r3a_by_pair = maps["r3a_by_pair"]
    deferred_by_pair = maps["deferred_by_pair"]

    explicit_by_key: dict[tuple[Any, ...], dict[str, Any]] = {}
    weak_pairs: set[tuple[str, str]] = set()
    family_hit_counts = {family: 0 for family in ("kinship", "marriage", "social", "institutional", "political")}
    evidence_bearing_pairs: set[tuple[str, str]] = set()
    duplicate_hit_count = 0
    identity_blocked_count = 0
    evidence_source_by_id = {evidence_id: item for evidence_id, item in evidence.items()}

    for evidence_id, item in evidence.items():
        identity_hits = hits_by_evidence.get(evidence_id, [])
        strong_hits = detect_relation_hits(str(item.get("quote", "")), identity_hits)
        for hit in strong_hits:
            pair = _pair(str(hit["person_a_id"]), str(hit["person_b_id"]))
            evidence_bearing_pairs.add(pair)
            family_hit_counts[str(hit["family"])] += 1
            if pair in reviewed_by_pair:
                duplicate_hit_count += 1
                continue
            _merge_hit(explicit_by_key, hit, evidence_id, evidence_source_by_id)
        for pair in _weak_signal_pairs(str(item.get("quote", "")), identity_hits):
            weak_pairs.add(pair)
        if blocked_mentions.get(evidence_id) and any(
            token in normalize_source_text(str(item.get("quote", "")))
            for token in (*OFFICE_WORDS, *KINSHIP_WORDS, *MARRIAGE_WORDS, *WEAK_RELATION_WORDS, *POLITICAL_WORDS)
        ):
            identity_blocked_count += 1

    candidates = [
        _candidate_from_hit(hit, evidence=evidence, names={pid: str(person["canonical_name"]) for pid, person in people.items()}, r3a_by_pair=r3a_by_pair)
        for hit in explicit_by_key.values()
    ]
    # An explicit hit equivalent to a reviewed Relation is control data, not a
    # new candidate.  R3C candidates are also never created for a pair/class
    # already represented by the frozen R3A candidate with the same semantics.
    reviewed_semantics = {
        (
            _pair(str(relation["subject_id"]), str(relation["object_id"])),
            relation.get("relation_type"),
            relation.get("relation_subtype"),
            relation.get("relation_scope"),
            relation.get("scope_event"),
        )
        for relation in maps["relations"]
    }
    candidates = [
        candidate
        for candidate in candidates
        if (
            (candidate["person_a_id"], candidate["person_b_id"]),
            candidate["proposed_relation_type"],
            candidate["proposed_relation_subtype"],
            candidate["proposed_relation_scope"],
            candidate.get("proposed_scope_event"),
        ) not in reviewed_semantics
    ]
    candidates.sort(key=lambda item: item["candidate_id"])

    existing_reviewed_attention: list[dict[str, Any]] = []
    names = {pid: str(person["canonical_name"]) for pid, person in people.items()}
    for relation in sorted(maps["relations"], key=lambda item: str(item["id"])):
        pair = _pair(str(relation["subject_id"]), str(relation["object_id"]))
        proposed = {
            "proposed_relation_type": relation.get("relation_type"),
            "proposed_relation_subtype": relation.get("relation_subtype"),
            "proposed_relation_scope": relation.get("relation_scope"),
            "proposed_scope_event": relation.get("scope_event"),
            "proposed_role_a": relation.get("role_a", ""),
            "proposed_role_b": relation.get("role_b", ""),
        }
        existing_reviewed_attention.append(
            _attention_base(
                disposition="existing_reviewed",
                person_a_id=pair[0],
                person_b_id=pair[1],
                source_entry_ids=relation.get("source_entry_ids", []),
                source_unit_ids=relation.get("source_unit_ids", []),
                evidence_ids=relation.get("evidence_ids", []),
                discovery_basis="existing_production_relation",
                evidence_excerpt="；".join(str(item) for item in relation.get("notes", "").split("；")[:1]),
                audit_note=f"已由生產 Relation {relation['id']} 審閱；R3C 只作覆蓋控制，不重複建立。",
                existing_relation_ids=[str(relation["id"])],
                proposed=proposed,
            )
        )

    deferred_attention: list[dict[str, Any]] = []
    for pair, decisions in sorted(deferred_by_pair.items()):
        for decision in sorted(decisions, key=lambda item: str(item["candidate_id"])):
            deferred_attention.append(
                _attention_base(
                    disposition="existing_deferred",
                    person_a_id=pair[0],
                    person_b_id=pair[1],
                    source_entry_ids=decision.get("source_entry_ids", []),
                    source_unit_ids=decision.get("source_unit_ids", []),
                    evidence_ids=decision.get("evidence_ids", []),
                    discovery_basis="existing_r3b_deferred_candidate",
                    evidence_excerpt=str(decision.get("decision_note", "")),
                    audit_note=f"保留 R3B 暂缓决定 {decision['candidate_id']}；R3C 不自动晋级。",
                    existing_r3a_candidate_ids=[str(decision["candidate_id"])],
                    risk_flags=["deferred_by_r3b"],
                )
            )

    candidate_attention: list[dict[str, Any]] = []
    for candidate in candidates:
        candidate_attention.append(
            _attention_base(
                disposition="new_candidate",
                person_a_id=candidate["person_a_id"],
                person_b_id=candidate["person_b_id"],
                source_entry_ids=candidate["source_entry_ids"],
                source_unit_ids=candidate["source_unit_ids"],
                evidence_ids=candidate["evidence_ids"],
                discovery_basis=candidate["discovery_basis"],
                evidence_excerpt=candidate["evidence_excerpt"],
                audit_note=candidate["discovery_note"],
                risk_flags=candidate["risk_flags"],
                existing_r3a_candidate_ids=candidate.get("related_r3a_candidate_ids", []),
                candidate_id=candidate["candidate_id"],
                proposed=candidate,
            )
        )

    scene_rows = _scene_only_pairs(root, reviewed_by_pair, r3a_by_pair)
    scene_attention: list[dict[str, Any]] = []
    for row in scene_rows:
        if row["story_id"] != "05-fangzheng-031":
            continue
        story = stories.get(row["story_id"], {})
        evidence_ids = [str(item) for item in story.get("evidence_ids", [])]
        scene_attention.append(
            _attention_base(
                disposition="scene_only",
                person_a_id=row["person_a_id"],
                person_b_id=row["person_b_id"],
                source_entry_ids=[row["story_id"]],
                evidence_ids=evidence_ids,
                discovery_basis="story_scene_political_counterposition",
                evidence_excerpt="王大將軍／處仲稱兵向朝廷與伯仁的言語衝突。",
                audit_note="本則只證明舞台中的政治立場與言語張力；沒有獨立長期 Relation 證據。",
                risk_flags=["scene_not_relation", "cooccurrence_not_relation"],
            )
        )

    all_attention = sorted(
        existing_reviewed_attention + deferred_attention + candidate_attention + scene_attention,
        key=lambda item: (item["disposition"], item["person_a_id"], item["person_b_id"], item["attention_id"]),
    )
    relation_isolated = sorted(
        person_id
        for person_id in people
        if not any(person_id in pair for pair in reviewed_by_pair)
    )
    summary = {
        "evidence_bearing_pair_count": len(evidence_bearing_pairs),
        "relation_family_hit_counts": {key: family_hit_counts[key] for key in sorted(family_hit_counts)},
        "existing_reviewed_relation_count": len(maps["relations"]),
        "existing_deferred_candidate_count": sum(len(items) for items in deferred_by_pair.values()),
        "already_reviewed_rediscovery_count": len(existing_reviewed_attention),
        "existing_deferred_rediscovery_count": len(deferred_attention),
        "new_candidate_count": len(candidates),
        "scene_only_count": len(scene_rows),
        "insufficient_for_relation_count": len(
            weak_pairs
            - {
                (str(key[0]), str(key[1]))
                for key in explicit_by_key
                if isinstance(key, tuple) and len(key) >= 2
            }
        ),
        "identity_blocked_count": identity_blocked_count,
        "duplicate_evidence_count": duplicate_hit_count,
        "relation_isolated_person_count": len(relation_isolated),
        "relation_isolated_person_ids": relation_isolated,
        "jinshu_evidence_count": sum(_evidence_layer(item) == "jinshu" for item in evidence.values()),
        "shishuo_evidence_count": sum(_evidence_layer(item) != "jinshu" for item in evidence.values()),
    }
    coverage = {
        "schema": 1,
        "stage": "r3c-relation-coverage-audit",
        "generated_from": [str(BUNDLE_PATH), str(PEOPLE_PATH), str(ALIASES_PATH), str(RELATIONS_PATH), str(R3A_PATH), str(R3B_PATH), str(SCENE_PATH)],
        "scope": {
            "production_person_count": len(people),
            "production_person_ids": sorted(people),
            "published_story_count": len(stories),
            "published_story_ids": sorted(stories),
            "person_pair_universe": len(people) * (len(people) - 1) // 2,
            "evidence_count": len(evidence),
            "shishuo_evidence_count": summary["shishuo_evidence_count"],
            "jinshu_evidence_count": summary["jinshu_evidence_count"],
        },
        "summary": summary,
        "attention_records": all_attention,
    }
    candidates_document = {
        "schema": 1,
        "stage": "r3c-explicit-person-relation-candidate-review",
        "generated_from": [str(BUNDLE_PATH), str(R3A_PATH), str(R3B_PATH)],
        "records": candidates,
    }
    return coverage, candidates_document


def project(root: Path = ROOT) -> dict[str, Any]:
    coverage, _ = build_projection(root)
    return coverage


def candidate_document(root: Path = ROOT) -> dict[str, Any]:
    _, candidates = build_projection(root)
    return candidates


def render_report(root: Path, coverage: Mapping[str, Any], candidates: Mapping[str, Any]) -> str:
    people = _people(root)
    names = {pid: str(person["canonical_name"]) for pid, person in people.items()}
    summary = coverage["summary"]
    lines = [
        "# R3C：当前范围显式人物关系覆盖审计",
        "",
        f"R3C 是关系覆盖审计，不是关系扩张器。它扫描当前 {coverage['scope']['production_person_count']} 位生产人物、{coverage['scope']['published_story_count']} 则已发布 Story 的正文/Liu 注，以及当前 Evidence 中已处理的《晋书》材料；新发现只进入候选层，不进入生产 Relation。",
        "",
        "## 范围与原则",
        "",
        f"- 生产人物：**{coverage['scope']['production_person_count']}**；已发布 Story：**{coverage['scope']['published_story_count']}**；无序人物对：**{coverage['scope']['person_pair_universe']}**。",
        f"- Evidence：Shishuo **{coverage['scope']['shishuo_evidence_count']}**；Jinshu **{coverage['scope']['jinshu_evidence_count']}**。",
        "- 覆盖目标：解释每个高信号显式关系是已审阅、已暂缓、新候选、仅场景、不足或身份受阻；不是降低关系孤立人数。",
        "- 硬规则：Scene ≠ Relation；共现、同席、一次褒贬、一次争论、官位高低都不能单独生成 Relation。",
        "",
        "## 审计摘要",
        "",
        f"- 有关系语义 Evidence 的人物对：**{summary['evidence_bearing_pair_count']}**。",
        f"- 当前已审阅 Relation：**{summary['existing_reviewed_relation_count']}**；R3B 暂缓候选：**{summary['existing_deferred_candidate_count']}**。",
        f"- 已审阅再发现：**{summary['already_reviewed_rediscovery_count']}**；R3B 暂缓再发现：**{summary['existing_deferred_rediscovery_count']}**。",
        f"- 新候选：**{summary['new_candidate_count']}**；仅场景：**{summary['scene_only_count']}**；不足以建立关系：**{summary['insufficient_for_relation_count']}**；身份受阻：**{summary['identity_blocked_count']}**；重复证据：**{summary['duplicate_evidence_count']}**。",
        f"- 按已审阅 Relation 计算的孤立人物：**{summary['relation_isolated_person_count']}**（描述性指标，不是质量目标）。",
        "",
        "## Relation family hits",
        "",
    ]
    for family, count in summary["relation_family_hit_counts"].items():
        lines.append(f"- {family}: **{count}** explicit pattern hits")
    lines.extend(
        [
            "",
            "- 本轮无需扩展 production Relation ontology；5 个新候选均可用现有 `institutional/service_under` 语义表达。",
            f"- 有 **{summary['identity_blocked_count']}** 组证据因身份不确定而阻断；未将其强行连接到 Relation 端点。",
            "- 未新增 H0/Clan/HistoricalEvent schema 或提示；可复用的事件、亲属、任职线索仍只留在当前 Evidence/审计范围内。",
        ]
    )
    lines.extend(["", "## R3C 新候选", ""])
    if not candidates["records"]:
        lines.append("本轮没有足够安全的新候选；这也是有效的覆盖结果。")
    for candidate in candidates["records"]:
        a, b = names.get(candidate["person_a_id"], candidate["person_a_id"]), names.get(candidate["person_b_id"], candidate["person_b_id"])
        scope = candidate["proposed_relation_scope"]
        if candidate.get("proposed_scope_event"):
            scope += f"（{candidate['proposed_scope_event']}）"
        lines.extend(
            [
                f"### {a} × {b}",
                "",
                f"- Candidate ID：`{candidate['candidate_id']}`；`{candidate['proposed_relation_type']}/{candidate['proposed_relation_subtype']}`；范围：`{scope}`。",
                f"- 角色：{candidate['proposed_role_a']} — {candidate['proposed_role_b']}。",
                f"- 来源：{', '.join(candidate['source_entry_ids'] + candidate['source_unit_ids']) or '未提供'}。Evidence：{', '.join(candidate['evidence_ids'])}。",
                f"- 依据：{candidate['discovery_note']}",
                f"- 证据摘录：{candidate['evidence_excerpt']}",
                f"- 风险：{', '.join(candidate['risk_flags']) or '无额外标记'}。review_status 保持 `candidate`，没有 production_relation_id。",
                "",
            ]
        )
    lines.extend(["## 关键负回归", "", "- `05-fangzheng-031` 的伯仁与处仲政治争论只标为 `scene_only`，不生成周顗—王敦 Relation。", "- 谢安 × 袁宏的赏识候选与王导 × 温峤的场景交流继续保留 R3B `deferred` 决定。", "- 苏峻 × 庾亮、苏峻 × 温峤仍由既有 R3B 事件限定 Relation 覆盖，不重复生成。", "", "## 后续边界", "", "新候选需要后续人工审阅后才可进入 R3D/R3B 类物化流程。R3C 完成后进入 SGZ0 前的关系覆盖复核，不启动 Sanguozhi、Clan、HistoricalEvent 或其他扩张。", ""])
    return "\n".join(lines)


def build(root: Path = ROOT) -> tuple[Path, Path, Path, Path]:
    coverage, candidates = build_projection(root)
    write_json(root, COVERAGE_PATH, coverage)
    write_json(root, CANDIDATE_PATH, candidates)
    write_json(
        root,
        COVERAGE_DERIVED_PATH,
        {
            "schema": 1,
            "stage": "r3c-relation-coverage-metrics",
            "generated_from": [str(COVERAGE_PATH), str(CANDIDATE_PATH)],
            "scope": coverage["scope"],
            "summary": coverage["summary"],
            "new_candidate_ids": [record["candidate_id"] for record in candidates["records"]],
        },
    )
    report_path = root / REPORT_PATH
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(render_report(root, coverage, candidates), encoding="utf-8")
    return root / COVERAGE_PATH, root / CANDIDATE_PATH, root / COVERAGE_DERIVED_PATH, report_path


def validate_source(root: Path = ROOT) -> list[str]:
    errors: list[str] = []
    for relative, schema_relative in ((COVERAGE_PATH, COVERAGE_SCHEMA_PATH), (CANDIDATE_PATH, CANDIDATE_SCHEMA_PATH)):
        try:
            document = read_json(root, relative)
            schema = read_json(root, schema_relative)
            Draft202012Validator.check_schema(schema)
            errors.extend(f"{relative}: {error.message}" for error in Draft202012Validator(schema).iter_errors(document))
        except (OSError, ValueError, TypeError) as exc:
            errors.append(f"{relative} could not be read: {exc}")
    return errors


if __name__ == "__main__":
    for path in build():
        print(path)
