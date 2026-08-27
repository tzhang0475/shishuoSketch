#!/usr/bin/env python3
"""HDB2-PSL1.1 reference-structure safety layer.

This module is deliberately a thin, candidate-only adapter around the frozen
PSL1 implementation.  It does not change the PSL1 weights, predicate wire
contract, or collective inference algorithm.  It adds a deterministic
reference-structure pass before inference and a stricter reviewer transition
after inference.
"""

from __future__ import annotations

import collections
import hashlib
import json
import math
import re
from pathlib import Path
from typing import Any, Mapping, Sequence

import build_hng0_2 as hng02
import hdb2_lj0_common as lj0
import hdb2_psl1_common as psl1
import historical_entity_resolver as resolver


ROOT = Path(__file__).resolve().parents[1]
ANNOTATION = ROOT / "data/annotation"
DERIVED = ROOT / "data/derived"
PSL1_SELECTION = ANNOTATION / "hdb2-psl1-selection.json"
PSL1_RUN = ROOT / "data/generated/hdb2-psl1/live/20260827T-HDB2-PSL1-02"
SELECTION_PATH = ANNOTATION / "hdb2-psl1-1-selection.json"
MODEL = psl1.MODEL
STRICT_ENDPOINT = psl1.STRICT_ENDPOINT
RUN_VERSION = "hdb2-psl1-1-v1"
PROMPT_VERSION = "hdb2-psl1-identity-predicates-v1"
REVIEW_PROMPT_VERSION = "hdb2-psl1-adversarial-review-v1"

DEVELOPMENT_CASES = (
    {"story_id": "34-pilou-001", "surface": "主", "label": "主 → 王敦"},
    {"story_id": "02-yanyu-046", "surface": "謝豫章", "label": "謝豫章 → 謝尚"},
    {"story_id": "05-fangzheng-028", "surface": "敦主簿", "label": "敦主簿 → 王敦"},
)

REFERENCE_TYPES = {
    "person_reference",
    "office_reference",
    "marriage_object_reference",
    "kinship_compositional_reference",
    "ruler_reference",
    "title_reference",
    "unknown",
}

KINSHIP_SUFFIXES = ("兒", "子", "女", "兄", "弟", "父", "母", "妻", "婿")
OFFICE_SUFFIXES = ("主簿", "尹", "太守", "長史", "尚書", "將軍", "司空", "僕射", "廷尉", "侍中")
IDENTITY_MARKERS = ("字", "名", "諱", "號")


def read_json(path: Path, default: Any = None) -> Any:
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else default


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def stable_hash(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def matching(value: Any) -> str:
    return resolver.matching_normalize(str(value or ""))


def _text(case: Mapping[str, Any]) -> str:
    pieces = [str(case.get("story_context") or ""), str(case.get("target_surface") or "")]
    pieces.extend(str(value or "") for value in case.get("annotation_context", []) or [])
    pieces.extend(
        str(row.get("text") or "")
        for row in case.get("evidence_items", []) or []
        if str(row.get("family") or "") not in {"confirmed_story_profile", "candidate_profile"}
        and str(row.get("kind") or "") != "candidate_profile"
    )
    return "\n".join(piece for piece in pieces if piece)


def _structural_text(case: Mapping[str, Any]) -> str:
    """Return source-facing context used by the deterministic parser.

    Candidate biographies are useful dossiers but are not local syntax.  Do
    not let an unrelated biography containing the same office word create a
    holder assignment for the current Story occurrence.
    """
    pieces = [str(case.get("story_context") or "")]
    pieces.extend(str(value or "") for value in case.get("annotation_context", []) or [])
    for row in case.get("evidence_items", []) or []:
        family = str(row.get("family") or "")
        kind = str(row.get("kind") or "")
        if family in {"relevant_source_evidence", "story_local_context"} and kind not in {"biography", "candidate_profile"}:
            pieces.append(str(row.get("text") or ""))
    return "\n".join(piece for piece in pieces if piece)


def _evidence_ids(case: Mapping[str, Any], needles: Sequence[str]) -> list[str]:
    result: list[str] = []
    for row in case.get("evidence_items", []) or []:
        evidence_id = str(row.get("evidence_id") or "")
        value = str(row.get("text") or "")
        family = str(row.get("family") or "")
        if family in {"confirmed_story_profile", "candidate_profile", "known_participants", "era_chronology"}:
            continue
        if evidence_id and all(needle in value for needle in needles if needle):
            result.append(evidence_id)
    return sorted(set(result))[:8]


def _distinct_mentions(text: str, target: str) -> list[str]:
    """Return only explicit, locally coordinated/separately introduced names."""
    found: list[str] = []
    # A、B / A與B are explicit separate mentions, unlike simple adjacency.
    for match in re.finditer(r"([\u3400-\u9fff]{1,8})[、與和]([\u3400-\u9fff]{1,8})", text):
        left, right = match.group(1), match.group(2)
        if target in (left, right):
            found.extend((left, right))
    # In the common biographical construction A年...，B..., A and B are
    # separately introduced references unless an identity marker connects
    # them.  Keep the pattern intentionally narrow.
    for match in re.finditer(r"([\u3400-\u9fff]{2,8})年[^，。；]{0,16}[，,]([\u3400-\u9fff]{2,8})", text):
        left, right = match.group(1), match.group(2)
        # The second mention is often immediately followed by its verb
        # (e.g. ``謝豫章將送客``), so compare by anchored containment while
        # retaining the actual target surface rather than the whole clause.
        if target == left or target.startswith(left) or left.startswith(target):
            found.extend((target, right))
        elif target in right:
            found.extend((left, target))
    return sorted(set(found), key=lambda value: (len(value), value))


def build_reference_structure(case: Mapping[str, Any]) -> dict[str, Any]:
    """Build a small deterministic semantic structure for one target.

    Text surfaces in this object are copied from the supplied case.  It is an
    audit/constraint object, not a canonical relation or identity claim.
    """
    target = str(case.get("target_surface") or "")
    text = _structural_text(case)
    structure: dict[str, Any] = {
        "reference_head": target,
        "reference_type": "person_reference",
        "holder": "",
        "anchor_person": "",
        "patron_or_possessor": "",
        "syntactic_role": "referent",
        "explicit_distinct_mentions": [],
        "evidence_ids": [],
        "derivation": "deterministic",
    }

    # X爲Y / X爲Y主簿: X is the office holder.  When Y is a compound
    # expression such as 敦主簿, the leading component is a patron/possessor;
    # when Y is exactly the office surface (e.g. 謝鯤爲長史), the target is
    # directly bound to X as its holder.  Both branches are syntactic and
    # source-grounded; neither is a substring alias.
    office_surface = next((value for value in OFFICE_SUFFIXES if target.endswith(value)), "")
    office = None
    if office_surface:
        # Parse immediately around the target occurrence.  Prefer a complete
        # supplied local-neighbor name before 爲; this avoids absorbing a
        # preceding connective such as 時 into the holder.
        local_names = set()
        for row in [*(case.get("local_neighbors", []) or []), *(case.get("candidates", []) or [])]:
            display_name = str(row.get("display_name") or "")
            if display_name:
                local_names.add(display_name)
            profile = row.get("profile") if isinstance(row.get("profile"), Mapping) else {}
            for field in ("canonical_name", "aliases", "courtesy_names"):
                values = profile.get(field, []) if field != "canonical_name" else [profile.get(field)]
                local_names.update(str(value) for value in values or [] if value)
        local_names = sorted(local_names, key=lambda value: (-len(value), value))
        holder = ""
        has_immediate_verb = False
        # There may be a synthetic target copy appended to the case after the
        # story/annotation text.  Inspect every occurrence and choose only an
        # occurrence whose immediately preceding character is 爲.
        for target_match in re.finditer(re.escape(target), text):
            prefix = text[:target_match.start()]
            predicate_index = len(prefix) - 1
            if predicate_index < 0 or prefix[predicate_index] not in {"爲", "為"}:
                continue
            has_immediate_verb = True
            holder = next(
                (
                    name for name in local_names
                    if prefix[predicate_index - len(name):predicate_index] == name
                ),
                "",
            )
            if not holder:
                match = re.search(r"([\u3400-\u9fff]{1,4})$", prefix[:predicate_index])
                holder = match.group(1) if match else ""
            if holder:
                break
        patron = target[:-len(office_surface)]
        office = {"holder": holder, "patron": patron if has_immediate_verb else "", "office": office_surface}
    if office and office.get("patron"):
        holder = str(office["holder"])
        patron = str(office["patron"])
        office_surface = str(office["office"])
        structure.update({
            "reference_head": office_surface,
            "reference_type": "office_reference",
            "holder": holder,
            "anchor_person": patron,
            "patron_or_possessor": patron,
            "syntactic_role": "office_object_patron",
            "explicit_distinct_mentions": sorted(set((holder, patron))),
            "evidence_ids": _evidence_ids(case, (holder, patron, office_surface)),
        })
    elif office and office.get("holder") and target == office.get("office"):
        # An exact office target in ``X爲Y`` is a holder reference.  This is a
        # deterministic direct reference fact, not an AliasMatch.  Keep the
        # holder separate from the office surface so role vetoes cannot treat
        # the office word as a second person mention.
        holder = str(office["holder"])
        office_surface = str(office["office"])
        structure.update({
            "reference_head": office_surface,
            "reference_type": "office_reference",
            "holder": holder,
            "anchor_person": holder,
            "patron_or_possessor": "",
            "syntactic_role": "office_holder",
            "explicit_distinct_mentions": [],
            "evidence_ids": _evidence_ids(case, (holder, office_surface)),
        })

    # X初尚主 / X尚主: 主 is a marriage/object reference, not X.
    marriage = re.search(r"(?P<actor>[\u3400-\u9fff]{1,8})(?:初)?尚主", text)
    if target == "主" and marriage:
        actor = marriage.group("actor")
        if actor.endswith("初"):
            actor = actor[:-1]
        structure.update({
            "reference_head": "主",
            "reference_type": "marriage_object_reference",
            "holder": "",
            "anchor_person": actor,
            "patron_or_possessor": "",
            "syntactic_role": "marriage_object",
            "explicit_distinct_mentions": [actor, "主"],
            "evidence_ids": _evidence_ids(case, (actor, "尚主")),
        })

    if target.endswith(KINSHIP_SUFFIXES) and len(target) > 1:
        base = target[:-1]
        structure.update({
            "reference_head": base,
            "reference_type": "kinship_compositional_reference",
            "anchor_person": base,
            "syntactic_role": "kinship_referent",
            "explicit_distinct_mentions": [base, target],
            "evidence_ids": _evidence_ids(case, (target,)),
        })

    if target in {"帝", "明帝", "武帝", "文帝", "元帝", "晉武帝"}:
        structure.update({
            "reference_head": target,
            "reference_type": "ruler_reference",
            "syntactic_role": "ruler_reference",
            "evidence_ids": _evidence_ids(case, (target,)),
        })
    elif structure["reference_type"] == "person_reference" and (
        target.endswith(OFFICE_SUFFIXES) or str(case.get("occurrence_type") or "") in {"title_reference", "office_reference"}
    ):
        structure.update({
            "reference_head": target,
            "reference_type": "office_reference" if target.endswith(OFFICE_SUFFIXES) else "title_reference",
            "syntactic_role": "office_or_title_referent",
            "evidence_ids": _evidence_ids(case, (target,)),
        })

    distinct = _distinct_mentions(text, target)
    if distinct:
        structure["explicit_distinct_mentions"] = sorted(set(distinct))
        structure["evidence_ids"] = sorted(set(structure.get("evidence_ids", [])) | set(_evidence_ids(case, distinct)))[:8]

    return structure


def _profile_forms(candidate: Mapping[str, Any]) -> list[str]:
    profile = candidate.get("profile") if isinstance(candidate.get("profile"), Mapping) else {}
    values = [candidate.get("display_name"), profile.get("canonical_name")]
    for key in ("aliases", "courtesy_names", "titles"):
        values.extend(profile.get(key, []) or [])
    registry = candidate.get("ruler_registry") if isinstance(candidate.get("ruler_registry"), Mapping) else {}
    canonical_title = registry.get("canonical_title") if isinstance(registry.get("canonical_title"), Mapping) else {}
    personal_name = registry.get("personal_name") if isinstance(registry.get("personal_name"), Mapping) else {}
    values.extend(
        value for value in (
            canonical_title.get("original"), canonical_title.get("simplified"),
            personal_name.get("original"), personal_name.get("simplified"),
        ) if value
    )
    for alias in registry.get("aliases", []) or []:
        if isinstance(alias, Mapping):
            values.extend(value for value in (alias.get("original"), alias.get("simplified")) if value)
    return sorted(set(str(value) for value in values if value), key=lambda value: (len(value), value))


def _candidate_matches(candidate: Mapping[str, Any], surface: str) -> bool:
    wanted = matching(surface)
    return bool(wanted) and any(matching(form) == wanted for form in _profile_forms(candidate))


def _catalog_context_candidates(case: Mapping[str, Any], candidates: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Add only catalogue people named by a grounded structural clue.

    The narrow surname-plus-kinship branch is generic: it is not tied to a
    fixture identity and is needed for 謝鯤 in ``謝豫章``.
    """
    structure = case.get("reference_structure") or {}
    text = _text(case)
    catalog = hng02.person_catalog()
    index = resolver.forms_index(catalog)
    knowledge = lj0.load_person_knowledge()
    existing = {str(row.get("person_id")) for row in candidates if row.get("person_id")}
    additions: list[dict[str, Any]] = []
    target = str(case.get("target_surface") or "")
    surname = target[:1]
    # A grounded "X之子/女/父" clue can expose a same-surname full name
    # without using substring containment as identity evidence.
    if surname and any(marker in text for marker in ("之子", "之女", "之父", "之母")):
        for person_id, person in sorted(catalog.items()):
            name = str(person.get("canonical_name") or "")
            if not name.startswith(surname) or person_id in existing or len(name) < 2:
                continue
            tail = name[-1:]
            if tail not in text or f"{tail}之" not in text:
                continue
            additions.append({
                "display_name": name,
                "person_id": str(person_id),
                "source": "reference_structure_context",
                "semantic_type": "person",
                "profile": lj0._candidate_profile(str(person_id), name, knowledge),
            })
    return additions


def _rekey_candidates(candidates: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()
    for row in candidates:
        display = str(row.get("display_name") or row.get("name") or "")
        pid = str(row.get("person_id") or "")
        typ = str(row.get("semantic_type") or "person")
        key = (pid, matching(display), typ)
        if not display or key in seen:
            continue
        seen.add(key)
        result.append(dict(row))
    # Preserve frozen LJ0/PSL1 c-keys.  Newly discovered contextual
    # candidates are appended deterministically and receive the next key.
    used = {str(row.get("candidate_key")) for row in result if re.fullmatch(r"c\d+", str(row.get("candidate_key") or ""))}
    next_number = 0
    for row in result:
        key = str(row.get("candidate_key") or "")
        if not re.fullmatch(r"c\d+", key):
            while f"c{next_number}" in used:
                next_number += 1
            row["candidate_key"] = f"c{next_number}"
            used.add(row["candidate_key"])
        row.setdefault("candidate_node_id", f"person:{row.get('person_id')}" if row.get("person_id") else f"local:psl1-1:{row.get('candidate_key')}")
    return result


def _role_vetoes(case: Mapping[str, Any], candidate: Mapping[str, Any]) -> list[str]:
    structure = case.get("reference_structure") or {}
    result: list[str] = []
    target = str(case.get("target_surface") or "")
    forms = _profile_forms(candidate)
    distinct = [str(value) for value in structure.get("explicit_distinct_mentions", []) if value]
    # Target is an object/reference and candidate is the actor.
    if structure.get("reference_type") == "marriage_object_reference" and any(_candidate_matches(candidate, value) for value in distinct if value != target):
        result.append("ActorObjectMismatch")
    # Office object/possessor is not its holder.
    if structure.get("reference_type") == "office_reference":
        patron = str(structure.get("patron_or_possessor") or "")
        holder = str(structure.get("holder") or "")
        if patron and any(matching(form) == matching(patron) for form in forms):
            result.append("PossessorVsHolderMismatch")
        if holder and not any(matching(form) == matching(holder) for form in forms) and patron and any(matching(form) == matching(patron) for form in forms):
            result.append("RoleMismatch")
    # Separately introduced references cannot share a candidate when that
    # candidate's supplied forms identify the other mention.
    if len(distinct) >= 2 and target in distinct:
        for other in distinct:
            if other != target and any(matching(form) == matching(other) for form in forms):
                result.append("ExplicitDistinct")
    return sorted(set(result))


def _direct_reference_support(case: Mapping[str, Any], candidate_key: str) -> bool:
    """Return whether syntax directly binds an office target to a holder.

    This is intentionally narrower than AliasMatch.  It allows an explicit
    ``X爲Y`` source statement to survive the reviewer veto for a title/office
    mention, while keeping ordinary contextual proximity non-identifying.
    """
    structure = case.get("reference_structure") or {}
    if structure.get("reference_type") != "office_reference":
        return False
    holder = str(structure.get("holder") or "")
    if not holder:
        return False
    candidate = next(
        (row for row in case.get("candidates", []) if str(row.get("candidate_key")) == str(candidate_key)),
        None,
    )
    if not candidate or not _candidate_matches(candidate, holder):
        return False
    if not _evidence_ids(case, (holder, str(structure.get("reference_head") or ""))):
        return False
    vetoes = (case.get("psl1_1_role_vetoes") or {}).get(str(candidate_key), [])
    return not any(vetoes)


def _tighten_deterministic(case: dict[str, Any]) -> None:
    structure = case.get("reference_structure") or {}
    target = str(case.get("target_surface") or "")
    candidates = {str(row.get("candidate_key")): row for row in case.get("candidates", [])}
    # Remove legacy substring-driven AliasMatch and recompute it against the
    # referential head only.  Structural prefixes such as 敦主簿 are never
    # aliases for the patron 敦/王敦.
    for row in case.get("deterministic_predicates", []) or []:
        key = str(row.get("candidate_key"))
        candidate = candidates.get(key)
        if not candidate:
            continue
        if str(row.get("predicate")) == "AliasMatch":
            head = str(structure.get("reference_head") or target)
            positive = structure.get("reference_type") != "marriage_object_reference" and _candidate_matches(candidate, head)
            if structure.get("reference_type") == "title_reference" and _candidate_matches(candidate, target):
                positive = True
            row.update({
                "value": 1.0 if positive else 0.5,
                "evidence_ids": list(structure.get("evidence_ids", [])) if positive else [],
                "reason": "reference_head_exact_form" if positive else "reference_head_not_candidate_form",
            })
        elif str(row.get("predicate")) == "OfficeCompatible":
            holder = str(structure.get("holder") or "")
            patron = str(structure.get("patron_or_possessor") or "")
            if holder:
                positive = _candidate_matches(candidate, holder)
                row.update({
                    "value": 1.0 if positive else 0.0 if patron and _candidate_matches(candidate, patron) else 0.5,
                    "evidence_ids": list(structure.get("evidence_ids", [])) if positive else [],
                    "reason": "syntactic_office_holder" if positive else "not_syntactic_office_holder",
                })
            elif structure.get("reference_type") == "marriage_object_reference":
                row.update({
                    "value": 0.5,
                    "evidence_ids": [],
                    "reason": "marriage_object_not_office_reference",
                })


def augment_graph(graph: Mapping[str, Any]) -> dict[str, Any]:
    """Attach structures, candidate expansions, and role vetoes to a PSL1 graph."""
    result = json.loads(json.dumps(graph, ensure_ascii=False))
    for case in result.get("cases", []):
        case["reference_structure"] = build_reference_structure(case)
        expanded = [*case.get("candidates", [])]
        expanded.extend(_catalog_context_candidates(case, expanded))
        case["candidates"] = _rekey_candidates(expanded)
        case["candidate_keys"] = [row.get("candidate_key") for row in case["candidates"]]
        _tighten_deterministic(case)
        vetoes = {str(key): list(value) for key, value in (case.get("psl1_hard_vetoes") or {}).items()}
        for candidate in case.get("candidates", []):
            reasons = _role_vetoes(case, candidate)
            if reasons:
                vetoes[str(candidate.get("candidate_key"))] = sorted(set(vetoes.get(str(candidate.get("candidate_key")), []) + reasons))
        case["psl1_1_role_vetoes"] = vetoes
        case["psl1_hard_vetoes"] = vetoes
        case["reference_structure_direct_support"] = sorted(
            str(candidate.get("candidate_key"))
            for candidate in case.get("candidates", [])
            if _direct_reference_support({**case, "psl1_1_role_vetoes": vetoes}, str(candidate.get("candidate_key")))
        )
        case["candidate_only"] = True
        case["canonical_write_back"] = False
    result["schema"] = "hdb2-psl1-1-graph-cases-v1"
    result["reference_structure_version"] = "hdb2-psl1-1-reference-structure-v1"
    result["candidate_only"] = True
    result["canonical_write_back"] = False
    return result


def wire_packet(case: Mapping[str, Any], cases: Sequence[Mapping[str, Any]], graph: Mapping[str, Any]) -> dict[str, Any]:
    packet = psl1.wire_packet(case, cases, graph)
    packet["task"] = "grounded PSL1.1 identity predicate evaluation"
    packet["reference_structure"] = {
        key: value for key, value in (case.get("reference_structure") or {}).items()
        if key not in {"evidence_ids"}
    }
    packet["reference_structure_constraints"] = {
        "substring_is_not_identity": True,
        "office_holder_differs_from_patron": True,
        "marriage_object_differs_from_actor": True,
        "explicit_distinct_is_hard": True,
    }
    return packet


def reviewer_packet(case: Mapping[str, Any], cases: Sequence[Mapping[str, Any]], graph: Mapping[str, Any], decision: Mapping[str, Any]) -> dict[str, Any]:
    packet = psl1.reviewer_packet(case, cases, graph, decision)
    packet["task"] = "adversarial review of one PSL1.1 identity ranking"
    packet["reference_structure"] = {
        key: value for key, value in (case.get("reference_structure") or {}).items()
        if key not in {"evidence_ids"}
    }
    packet["role_vetoes"] = {
        str(key): list(value) for key, value in (case.get("psl1_1_role_vetoes") or {}).items()
    }
    return packet


def infer_graph(graph: Mapping[str, Any], llm_predicates: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    decisions = psl1.infer_graph(graph, llm_predicates)
    by_id = {str(case.get("mention_id")): case for case in graph.get("cases", [])}
    for row in decisions.get("records", []):
        case = by_id.get(str(row.get("mention_id")), {})
        row["reference_structure"] = case.get("reference_structure") or {}
        row["role_vetoes"] = case.get("psl1_1_role_vetoes") or {}
        row["reference_structure_veto_count"] = sum(
            1 for reasons in (case.get("psl1_1_role_vetoes") or {}).values()
            if any(reason in {"RoleMismatch", "PossessorVsHolderMismatch", "ActorObjectMismatch", "ExplicitDistinct"} for reason in reasons)
        )
        direct_keys = {
            str(key) for key in case.get("reference_structure_direct_support", [])
            if not ((case.get("psl1_hard_vetoes") or {}).get(str(key)) or [])
        }
        if len(direct_keys) == 1:
            # The underlying PSL1 scorer remains unchanged.  Promote only an
            # explicit syntactic holder assignment (X爲office) to a stable
            # title/office referent; this is a direct reference fact and not
            # a generic contextual compatibility score.
            direct_key = next(iter(direct_keys))
            ranking_by_key = {str(item.get("candidate_key")): item for item in row.get("candidate_rankings", [])}
            direct_row = ranking_by_key.get(direct_key)
            if direct_row:
                direct_row["raw_score"] = max(float(direct_row.get("raw_score") or 0), psl1.HIGH_RAW_SCORE_THRESHOLD)
                direct_row.setdefault("supporting_predicates", []).append({
                    "predicate": "OfficeCompatible",
                    "value": 1.0,
                    "evidence_ids": list((case.get("reference_structure") or {}).get("evidence_ids", [])),
                    "reason": "deterministic_syntactic_office_holder",
                    "direct_reference_support": True,
                })
                direct_row["supporting_predicates"] = sorted(
                    direct_row["supporting_predicates"],
                    key=lambda item: (str(item.get("predicate")), stable_hash(item)),
                )
                # Recalculate display probabilities from the adjusted raw
                # scores so the audit ranking remains internally coherent.
                raw_scores = {
                    str(item.get("candidate_key")): float(item.get("raw_score") or 0)
                    for item in row.get("candidate_rankings", [])
                    if not item.get("hard_conflict")
                }
                if raw_scores:
                    maximum = max(raw_scores.values())
                    denominator = sum(math.exp(value - maximum) for value in raw_scores.values())
                    for item in row.get("candidate_rankings", []):
                        key = str(item.get("candidate_key"))
                        item["link"] = round(math.exp(raw_scores[key] - maximum) / denominator, 6) if key in raw_scores else 0.0
                row["candidate_rankings"] = sorted(
                    row.get("candidate_rankings", []),
                    key=lambda item: (-float(item.get("link") or 0), -float(item.get("raw_score") or 0), str(item.get("candidate_key"))),
                )
                row["top_candidate_key"] = direct_key
                row["top_candidate"] = direct_row.get("candidate")
                row["top_candidate_person_id"] = direct_row.get("candidate_person_id")
                row["direct_reference_support"] = True
                row["result_state"] = (
                    "stable_entity_resolved"
                    if str(direct_row.get("candidate_node_id") or "").startswith(("person:", "ruler:"))
                    else "local_candidate_resolved"
                )
        row["candidate_only"] = True
        row["canonical_write_back"] = False
    decisions["schema"] = "hdb2-psl1-1-decisions-v1"
    decisions["reference_structure_version"] = "hdb2-psl1-1-reference-structure-v1"
    decisions["candidate_only"] = True
    decisions["canonical_write_back"] = False
    return decisions


def _direct_identity_fact(case: Mapping[str, Any], decision: Mapping[str, Any]) -> bool:
    key = str(decision.get("top_candidate_key") or "")
    if _direct_reference_support(case, key):
        return True
    for row in case.get("deterministic_predicates", []) or []:
        if str(row.get("candidate_key")) == key and str(row.get("predicate")) == "AliasMatch" and float(row.get("value", 0.5)) > 0.5 and row.get("evidence_ids"):
            return True
    return False


def apply_reviewer(decisions: Mapping[str, Any], reviewer_rows: Sequence[Mapping[str, Any]], graph: Mapping[str, Any]) -> dict[str, Any]:
    """Apply reviewer output with a fail-closed reject-top transition."""
    by_id = {str(row.get("mention_id")): dict(row) for row in reviewer_rows}
    case_by_id = {str(row.get("mention_id")): row for row in graph.get("cases", [])}
    result: list[dict[str, Any]] = []
    for original in decisions.get("records", []):
        row = dict(original)
        review = by_id.get(str(row.get("mention_id")))
        row["reviewer_required"] = str(row.get("result_state")) in {"stable_entity_resolved", "review_required"}
        if not review or (review.get("validation") or {}).get("valid") is not True:
            result.append(row)
            continue
        payload = review.get("payload") or {}
        verdict = payload.get("verdict")
        accepted = payload.get("accepted_candidate_key")
        ranking = {str(item.get("candidate_key")): item for item in row.get("candidate_rankings", [])}
        case = case_by_id.get(str(row.get("mention_id")), {})
        if verdict == "resolve":
            safe = accepted in ranking and not ranking[accepted].get("hard_conflict") and bool(payload.get("direct_identity_support"))
            if safe:
                candidate = ranking[accepted]
                row.update({
                    "top_candidate_key": accepted,
                    "top_candidate": candidate.get("candidate"),
                    "top_candidate_person_id": candidate.get("candidate_person_id"),
                    "result_state": "stable_entity_resolved" if str(candidate.get("candidate_node_id") or "").startswith(("person:", "ruler:")) else "local_candidate_resolved",
                    "reviewer_resolved": True,
                })
        elif verdict == "reject_top_candidate":
            # A reject with no deterministic direct identity proof can never
            # leave a stable state.  It also cannot promote an alternate key.
            if not _direct_identity_fact(case, row):
                row["result_state"] = "review_required" if row.get("top_candidate_key") and any(not item.get("hard_conflict") for item in row.get("candidate_rankings", [])) else "genuinely_unresolved"
                row["reviewer_rejected_top_candidate"] = True
        elif verdict == "genuinely_unresolved":
            row["result_state"] = "genuinely_unresolved"
        else:
            row["result_state"] = "review_required"
        row["reviewer_verdict"] = verdict
        row["reviewer_accepted_candidate_key"] = accepted
        row["reviewer_direct_identity_support"] = list(payload.get("direct_identity_support", []))
        row["reviewer_identity_contradictions"] = list(payload.get("identity_contradictions", []))
        row["reviewer_rejected_top_candidate"] = verdict == "reject_top_candidate"
        row["reviewer_reason_types"] = list(payload.get("reason_types", []))
        row["candidate_only"] = True
        row["canonical_write_back"] = False
        result.append(row)
    return {
        "schema": "hdb2-psl1-1-final-decisions-v1",
        "selection_hash": decisions.get("selection_hash"),
        "records": result,
        "candidate_only": True,
        "canonical_write_back": False,
    }


def load_frozen_predicate_records() -> list[dict[str, Any]]:
    document = read_json(PSL1_RUN / "model-predicate-results.json", {}) or {}
    return [
        dict(row) for row in document.get("records", [])
        if row.get("call_type") == "predicate_evaluation"
    ]


def load_frozen_reviewer_records() -> list[dict[str, Any]]:
    document = read_json(PSL1_RUN / "model-predicate-results.json", {}) or {}
    return [
        dict(row) for row in document.get("records", [])
        if row.get("call_type") == "adversarial_review"
    ]


def load_psl1_graphs() -> tuple[dict[str, Any], dict[str, Any]]:
    selection = read_json(PSL1_SELECTION, {}) or {}
    regression = psl1.load_regression_cases()
    holdout = psl1.load_holdout_cases({"holdout_cases": selection.get("holdout_cases", [])})
    return augment_graph(psl1.build_graph_cases(regression)), augment_graph(psl1.build_graph_cases(holdout))


def build_independent_selection(path: Path = SELECTION_PATH, *, limit: int = 10) -> dict[str, Any]:
    """Select unseen existing-Person occurrences without reading PSL output."""
    items = lj0.load_review_items()
    psl1_selection = read_json(PSL1_SELECTION, {}) or {}
    excluded = {
        str(row.get("occurrence_id"))
        for row in [*psl1_selection.get("regression_cases", []), *psl1_selection.get("holdout_cases", [])]
    }
    development_ids = {
        str(item.get("occurrence_id"))
        for item in items
        if any(str(item.get("story_id")) == row["story_id"] and str(item.get("target_surface")) == row["surface"] for row in DEVELOPMENT_CASES)
    }
    excluded |= development_ids

    def tags(item: Mapping[str, Any]) -> list[str]:
        facts = item.get("affected_facts") or {}
        result: list[str] = []
        typ = str(item.get("occurrence_type") or "")
        review_type = str(item.get("review_type") or "")
        surface = str(item.get("target_surface") or "")
        if review_type == "office_or_title_holder" or typ in {"title_reference", "office_reference"}:
            result.append("office_title")
        if typ == "ruler_reference" or surface in {"帝", "明帝", "武帝", "文帝", "元帝", "晉武帝"}:
            result.append("ruler_reference")
        if typ in {"abbreviated_person_name", "courtesy_name_reference"}:
            result.append("abbreviated_courtesy")
        if review_type == "identity":
            result.append("difficult_identity")
        if any(len(facts.get(key, []) or []) for key in ("kinship", "marriage", "relations")):
            result.append("relationship_sensitive")
        if len(item.get("candidate_people", []) or []) >= 2:
            result.append("same_story_multi_person")
        if typ in {"kinship_reference", "kinship_compositional_reference"} or surface.endswith(KINSHIP_SUFFIXES):
            result.append("compositional")
        if not result:
            result.append("other")
        return result

    def rank(item: Mapping[str, Any]) -> tuple[Any, ...]:
        facts = item.get("affected_facts") or {}
        structural = 10 * len(facts.get("marriage", []) or []) + 8 * len(facts.get("kinship", []) or []) + 4 * len(facts.get("relations", []) or [])
        return (-structural, str(item.get("story_id") or ""), str(item.get("occurrence_id") or ""))

    eligible = [
        item for item in items
        if str(item.get("occurrence_id")) not in excluded
        and any(str(candidate.get("person_id") or "").startswith("person-") for candidate in item.get("candidate_people", []) or [])
    ]
    by_tag: dict[str, list[Mapping[str, Any]]] = collections.defaultdict(list)
    for item in eligible:
        for tag in tags(item):
            by_tag[tag].append(item)
    for rows in by_tag.values():
        rows.sort(key=rank)

    selected: list[Mapping[str, Any]] = []
    selected_ids: set[str] = set()
    # These quotas are preferences only.  A missing category is recorded as a
    # shortfall and filled from the deterministic structural ranking below.
    for tag, quota in (("office_title", 2), ("ruler_reference", 2), ("abbreviated_courtesy", 2), ("relationship_sensitive", 2), ("same_story_multi_person", 2), ("compositional", 1), ("difficult_identity", 1), ("other", 1)):
        for item in by_tag.get(tag, [])[:]:
            if len([x for x in selected if tag in tags(x)]) >= quota:
                break
            oid = str(item.get("occurrence_id"))
            if oid in selected_ids:
                continue
            selected.append(item)
            selected_ids.add(oid)
    for item in sorted(eligible, key=rank):
        if len(selected) >= limit:
            break
        oid = str(item.get("occurrence_id"))
        if oid not in selected_ids:
            selected.append(item)
            selected_ids.add(oid)
    if len(selected) != limit:
        raise RuntimeError(f"psl1_1_independent_selection_count:{len(selected)}")

    rows: list[dict[str, Any]] = []
    for item in sorted(selected, key=lambda row: (str(row.get("story_id")), str(row.get("occurrence_id")))):
        candidate_set = sorted({
            (str(candidate.get("label") or candidate.get("display_name") or ""), str(candidate.get("person_id") or ""))
            for candidate in item.get("candidate_people", []) or []
            if str(candidate.get("person_id") or "").startswith("person-")
        })
        source_refs = sorted({
            str(evidence.get("evidence_ref"))
            for evidence in item.get("selected_evidence", []) or []
            if evidence.get("evidence_ref")
        })
        key_material = {
            "occurrence_id": item.get("occurrence_id"),
            "identity_observation_id": item.get("identity_observation_id"),
            "story_id": item.get("story_id"),
            "surface": item.get("target_surface"),
            "candidate_set": candidate_set,
            "source_refs": source_refs,
        }
        rows.append({
            "occurrence_id": item.get("occurrence_id"),
            "identity_observation_id": item.get("identity_observation_id"),
            "story_id": item.get("story_id"),
            "surface": item.get("target_surface"),
            "occurrence_type": item.get("occurrence_type"),
            "candidate_set": [{"display_name": name, "person_id": pid} for name, pid in candidate_set],
            "selection_categories": tags(item),
            "selection_reason": ";".join(tags(item)),
            "source_refs": source_refs,
            "selection_key": stable_hash(key_material),
        })
    result: dict[str, Any] = {
        "schema": "hdb2-psl1-1-selection-v1",
        "run_version": RUN_VERSION,
        "prompt_version": PROMPT_VERSION,
        "review_prompt_version": REVIEW_PROMPT_VERSION,
        "model": MODEL,
        "temperature": 0,
        "thinking": "disabled",
        "frozen_before_live": True,
        "candidate_only": True,
        "canonical_write_back": False,
        "development_cases": list(DEVELOPMENT_CASES),
        "development_occurrence_ids": sorted(development_ids),
        "excluded_psl1_occurrence_ids": sorted(excluded - development_ids),
        "independent_cases": rows,
        "independent_count": len(rows),
        "selection_hash": None,
    }
    result["selection_hash"] = stable_hash({key: value for key, value in result.items() if key != "selection_hash"})
    if path.is_file():
        existing = read_json(path, {}) or {}
        if existing != result:
            raise RuntimeError("hdb2_psl1_1_independent_selection_changed")
        return existing
    write_json(path, result)
    return result


def freeze_selection(path: Path = SELECTION_PATH) -> dict[str, Any]:
    return build_independent_selection(path)


def development_lookup(graphs: Sequence[Mapping[str, Any]]) -> dict[tuple[str, str], dict[str, Any]]:
    return {
        (str(case.get("story_id")), str(case.get("target_surface"))): case
        for graph in graphs for case in graph.get("cases", [])
    }


def safety_metrics(graphs: Sequence[Mapping[str, Any]], decisions: Sequence[Mapping[str, Any]], validation_failures: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    metrics = {
        "reference_structure_vetoes": 0,
        "role_mismatch_rejections": 0,
        "possessor_holder_rejections": 0,
        "actor_object_rejections": 0,
        "explicit_distinct_rejections": 0,
        "reviewer_rejected_stable_cases": 0,
        # Provider payload errors are audit diagnostics.  They are kept
        # separate from the hard safety counters below because an invalid
        # payload must be ignored, not treated as a state mutation.
        "invalid_candidate_key_payloads": 0,
        "invalid_evidence_reference_payloads": 0,
        "invalid_candidate_keys": 0,
        "invalid_evidence_references": 0,
        "candidate_only": True,
        "canonical_write_back": False,
    }
    seen: set[tuple[str, str, str]] = set()
    for graph in graphs:
        for case in graph.get("cases", []):
            for key, reasons in (case.get("psl1_1_role_vetoes") or {}).items():
                if reasons:
                    metrics["reference_structure_vetoes"] += 1
                for reason in reasons:
                    if reason == "RoleMismatch":
                        metrics["role_mismatch_rejections"] += 1
                    elif reason == "PossessorVsHolderMismatch":
                        metrics["possessor_holder_rejections"] += 1
                    elif reason == "ActorObjectMismatch":
                        metrics["actor_object_rejections"] += 1
                    elif reason == "ExplicitDistinct":
                        metrics["explicit_distinct_rejections"] += 1
    for row in decisions:
        if row.get("reviewer_rejected_top_candidate") and row.get("reviewer_required"):
            metrics["reviewer_rejected_stable_cases"] += 1
    for failure in validation_failures:
        for error in failure.get("errors", []):
            if "candidate" in str(error).lower() and "invalid" in str(error).lower():
                metrics["invalid_candidate_key_payloads"] += 1
            if "evidence_reference_invalid" in str(error):
                metrics["invalid_evidence_reference_payloads"] += 1
    return metrics


def development_state_changes(old_decisions: Sequence[Mapping[str, Any]], new_decisions: Sequence[Mapping[str, Any]], graphs: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    old = {str(row.get("occurrence_id")): row for row in old_decisions}
    case_by_id = {str(case.get("occurrence_id")): case for graph in graphs for case in graph.get("cases", [])}
    result: list[dict[str, Any]] = []
    for row in new_decisions:
        prior = old.get(str(row.get("occurrence_id")), {})
        if prior.get("result_state") == row.get("result_state") and prior.get("top_candidate") == row.get("top_candidate"):
            continue
        result.append({
            "story_id": row.get("story_id"),
            "surface": row.get("surface"),
            "occurrence_id": row.get("occurrence_id"),
            "psl1_state": prior.get("result_state"),
            "psl1_candidate": prior.get("top_candidate"),
            "psl1_1_state": row.get("result_state"),
            "psl1_1_candidate": row.get("top_candidate"),
            "reference_structure": case_by_id.get(str(row.get("occurrence_id")), {}).get("reference_structure", {}),
            "role_vetoes": row.get("role_vetoes", {}),
        })
    return sorted(result, key=lambda row: (str(row.get("story_id")), str(row.get("occurrence_id"))))
