#!/usr/bin/env python3
"""Conservative reference parsing for HDB2-PSL1.3B.

PSL1.3A introduced a semantic pre-judgment boundary, but its deterministic
office parser still had a nearest-name fallback.  This module is an additive
adapter: it reuses the 1.3A tool, packet, validator, and downstream PSL
machinery while replacing only the reference hypotheses and the corresponding
grounded-holder guard.  The old 1.3A implementation and its artifacts remain
available as the historical comparison point.
"""

from __future__ import annotations

import copy
import hashlib
import re
from pathlib import Path
from typing import Any, Mapping, Sequence

import hdb2_psl1_3a_common as base
import hdb2_psl1_3_common as psl1_3
import hdb2_psl1_1_common as psl1_1


# Re-export the frozen 1.3A packet/tool/validation helpers.  Keeping these
# objects identical is intentional: 1.3B changes structural parsing, not the
# semantic arbitration contract.
for _name in dir(base):
    if not _name.startswith("__"):
        globals().setdefault(_name, getattr(base, _name))


ANNOTATION = ROOT / "data/annotation"
DERIVED = ROOT / "data/derived"
GENERATED = ROOT / "data/generated/hdb2-psl1-3b"
SELECTION_PATH = ANNOTATION / "hdb2-psl1-3b-selection.json"
HDB2_F_CASES_PATH = DERIVED / "hdb2-f-occurrence-cases.json"
RUN_VERSION = "hdb2-psl1-3b-v1"
# The provider-facing semantic prompt/tool is the frozen 1.3A contract.
PROMPT_VERSION = base.PROMPT_VERSION

GENERIC_PERSONAL_FORMS = {"公", "王", "劉", "某公", "某君"}
STORY_ID_RE = re.compile(r"\b\d{2}-[a-z0-9]+-\d{3}\b")
OFFICE_ROLE_STRUCTURES = {"office_holder_reference", "patron_plus_office"}
# The frozen 1.3A list focused on compound office names.  ``車騎`` is also a
# title-shaped surface in the existing HDB2 frontier and needs the same
# conservative treatment; this is a vocabulary clarification, not a holder
# fallback.
OFFICE_SURFACES = tuple(dict.fromkeys((*base.OFFICE_SURFACES, "車騎")))


def _prior_story_ids() -> set[str]:
    """Collect Story IDs from prior PSL artifacts/docs/tests.

    Selection is made from existing HDB2 cases, but exclusion is by Story,
    not occurrence.  The current 1.3B namespace is excluded so recomputing a
    frozen selection cannot make the selection self-referential.
    """
    result: set[str] = set()
    roots = (ANNOTATION, GENERATED.parent, ROOT / "docs", ROOT / "tests")
    for root in roots:
        if not root.exists():
            continue
        for path in sorted(root.rglob("*")):
            if not path.is_file():
                continue
            path_text = str(path).lower()
            if "psl" not in path_text:
                continue
            # Later PSL1.3C validation is a replay of this frozen B sample;
            # its isolated namespace must not be mistaken for an additional
            # prior Story experiment when the historical B selector is
            # rebuilt.
            if any(token in path_text for token in (
                "hdb2-psl1-3b",
                "hdb2_psl1_3b",
                "hdb2-psl1-3c",
                "hdb2_psl1_3c",
                "hdb2-psl1-3d",
                "hdb2_psl1_3d",
            )):
                continue
            try:
                result.update(STORY_ID_RE.findall(path.read_text(encoding="utf-8", errors="ignore")))
            except OSError:
                continue
    return result


def previous_story_ids() -> set[str]:
    return _prior_story_ids()


def _selection_row(row: Mapping[str, Any]) -> dict[str, Any]:
    evidence_refs = sorted({
        str(item.get("source_ref"))
        for item in row.get("evidence_items", []) or []
        if isinstance(item, Mapping) and item.get("source_ref")
    })
    key_material = {
        "occurrence_id": row.get("occurrence_id"),
        "identity_observation_id": row.get("identity_observation_id"),
        "story_id": row.get("story_id"),
        "surface": row.get("target_surface"),
        "source_refs": evidence_refs,
    }
    return {
        "occurrence_id": row.get("occurrence_id"),
        "identity_observation_id": row.get("identity_observation_id"),
        "story_id": row.get("story_id"),
        "surface": row.get("target_surface"),
        "occurrence_type": row.get("occurrence_type"),
        "selection_category": psl1_3._category(row),
        "original_hdb2_status": row.get("hdb1_original_status"),
        "candidate_set": [
            {
                "display_name": item.get("display_name"),
                "semantic_type": item.get("semantic_type") or "person",
            }
            for item in row.get("candidates", []) or []
            if isinstance(item, Mapping) and item.get("display_name")
        ],
        "source_refs": evidence_refs,
        "selection_key": stable_hash(key_material),
    }


def _category_rank(category: str) -> int:
    return {
        "office_title": 0,
        "ruler_title": 1,
        "kinship_reference": 2,
        "abbreviated_courtesy": 3,
        "ordinary_unresolved": 4,
    }.get(category, 5)


def build_selection(path: Path = SELECTION_PATH, *, limit: int = 10) -> dict[str, Any]:
    if limit != 10:
        raise ValueError("psl1_3b_selection_must_have_exactly_10_cases")
    excluded = previous_story_ids()
    all_rows = psl1_3._hdb2f_cases()
    eligible = [
        row for row in all_rows.values()
        if str(row.get("story_id") or "") and str(row.get("story_id")) not in excluded
    ]
    by_story: dict[str, list[dict[str, Any]]] = {}
    for row in eligible:
        by_story.setdefault(str(row.get("story_id")), []).append(row)

    def row_key(row: Mapping[str, Any]) -> tuple[Any, ...]:
        # This uses only frozen input structure.  No model result is read.
        return (
            _category_rank(psl1_3._category(row)),
            psl1_3._score(row),
            str(row.get("occurrence_id") or ""),
        )

    winners = [sorted(rows, key=row_key)[0] for rows in by_story.values()]
    winners.sort(key=row_key)

    # Prefer a naturally available mixture.  These are deterministic
    # preferences, not answer-based cherry-picking; remaining slots are filled
    # by the same stable structural ordering.
    preferred: list[dict[str, Any]] = []
    used_stories: set[str] = set()
    category_preferences = (
        ("office_title", 2),
        ("ruler_title", 2),
        ("kinship_reference", 2),
        ("abbreviated_courtesy", 3),
        ("ordinary_unresolved", 3),
    )
    for category, quota in category_preferences:
        for row in [item for item in winners if psl1_3._category(item) == category]:
            if len([item for item in preferred if psl1_3._category(item) == category]) >= quota:
                break
            story_id = str(row.get("story_id"))
            if story_id in used_stories:
                continue
            preferred.append(row)
            used_stories.add(story_id)
    for row in winners:
        if len(preferred) >= limit:
            break
        story_id = str(row.get("story_id"))
        if story_id not in used_stories:
            preferred.append(row)
            used_stories.add(story_id)
    if len(preferred) != limit:
        raise RuntimeError(f"psl1_3b_independent_selection_count:{len(preferred)}")

    selected = [_selection_row(row) for row in preferred]
    selected.sort(key=lambda row: str(row.get("selection_key") or ""))
    selected_story_ids = [str(row.get("story_id")) for row in selected]
    result: dict[str, Any] = {
        "schema": "hdb2-psl1-3b-selection-v1",
        "run_version": RUN_VERSION,
        "prompt_version": PROMPT_VERSION,
        "model": MODEL,
        "temperature": 0,
        "thinking": "disabled",
        "frozen_before_live": True,
        "candidate_only": True,
        "canonical_write_back": False,
        "prior_story_ids": sorted(excluded),
        "prior_story_count": len(excluded),
        "prior_story_ids_hash": stable_hash(sorted(excluded)),
        "source_input": str(HDB2_F_CASES_PATH.relative_to(ROOT)),
        "source_input_sha256": hashlib.sha256(HDB2_F_CASES_PATH.read_bytes()).hexdigest(),
        "independent_cases": selected,
        "independent_count": len(selected),
        "story_ids": selected_story_ids,
        "distinct_story_count": len(set(selected_story_ids)),
        "overlap_with_prior_story_ids": sorted(set(selected_story_ids) & excluded),
        "selection_hash": None,
    }
    result["selection_hash"] = stable_hash({key: value for key, value in result.items() if key != "selection_hash"})
    if path.is_file():
        existing = read_json(path, {}) or {}
        if existing != result:
            raise RuntimeError("hdb2_psl1_3b_selection_changed")
        return existing
    write_json(path, result)
    return result


def freeze_selection(path: Path = SELECTION_PATH) -> dict[str, Any]:
    return build_selection(path)


def build_graph(selection: Mapping[str, Any]) -> dict[str, Any]:
    """Build the same frozen graph input as 1.3A for a new selection."""
    return psl1_3.build_graph(selection)


def _recognized_person_surfaces(case: Mapping[str, Any]) -> list[str]:
    """Return independently recognized local person forms.

    A form is accepted from a local neighbor or person-like candidate.  This
    is deliberately narrower than arbitrary CJK text and is only used for an
    immediately adjacent office construction.
    """
    names: set[str] = set()
    rows = [*(case.get("local_neighbors", []) or []), *(case.get("candidates", []) or [])]
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        semantic_type = str(row.get("semantic_type") or "person")
        if semantic_type in {"location", "event", "office", "work_title", "not_person", "collective_persons"}:
            continue
        profile = row.get("profile") if isinstance(row.get("profile"), Mapping) else {}
        values: list[Any] = [row.get("display_name"), row.get("name"), profile.get("canonical_name")]
        for field in ("aliases", "courtesy_names"):
            values.extend(profile.get(field, []) or [])
        for value in values:
            text = str(value or "")
            if text and text not in OFFICE_SURFACES:
                names.add(text)
    return sorted(names, key=lambda value: (-len(value), value))


def _explicit_office_construction(
    text: str,
    target: str,
    names: Sequence[str],
) -> tuple[str, str, str, str] | None:
    """Return (holder, patron, matched_span, basis) only for explicit syntax."""
    office = next((value for value in OFFICE_SURFACES if target.endswith(value)), "")
    if not office:
        return None
    for match in re.finditer(re.escape(target), text):
        position = match.start()
        # Holder before office: X爲Y, X為Y, X時爲Y, X時為Y, 以X爲Y,
        # 以X為Y.  The holder must be a known local person form and must end
        # immediately before the construction.
        for holder in names:
            for connector in ("時爲", "時為", "爲", "為"):
                prefix = holder + connector
                if position >= len(prefix) and text[position - len(prefix):position] == prefix:
                    start = position - len(prefix)
                    return holder, "", text[start:match.end()], "explicit_holder_office_syntax"
                prefix = "以" + holder + connector
                if position >= len(prefix) and text[position - len(prefix):position] == prefix:
                    start = position - len(prefix)
                    return holder, "", text[start:match.end()], "explicit_holder_office_syntax"
        # Office before holder: only immediate adjacency is accepted.
        if target == office:
            for holder in names:
                end = match.end() + len(holder)
                if text[match.end():end] == holder:
                    return holder, "", text[match.start():end], "adjacent_office_holder_syntax"
    return None


def _office_hypotheses(case: Mapping[str, Any], target: str, text: str) -> list[dict[str, Any]]:
    office = next((value for value in OFFICE_SURFACES if target.endswith(value)), "")
    if not office:
        return []
    names = _recognized_person_surfaces(case)
    construction = _explicit_office_construction(text, target, names)
    patron = target[:-len(office)] if len(target) > len(office) else ""
    if construction:
        holder, _, matched_span, basis = construction
        needles = (holder, patron, office) if patron else (holder, office)
        evidence_ids = _evidence_ids(case, needles)
        if evidence_ids:
            if patron:
                components = [
                    _component(holder, "anchor_person"),
                    _component(patron, "patron"),
                    _component(office, "office"),
                ]
                return [_hypothesis(
                    "h0", "patron_plus_office", "person", components,
                    basis="explicit_holder_patron_office_syntax",
                    evidence_ids=evidence_ids, deterministic=True,
                )]
            return [_hypothesis(
                "h0", "office_holder_reference", "person",
                [_component(holder, "anchor_person"), _component(office, "office")],
                basis=basis, evidence_ids=evidence_ids, deterministic=True,
            )]
        # A syntactic-looking match without a source evidence ID is not a
        # deterministic holder.  Keep the surface structure, but fail closed.
        return [_hypothesis(
            "h0", "patron_plus_office" if patron else "office_holder_reference", "person",
            ([_component(patron, "patron")] if patron else []) + [_component(office, "office")],
            basis="holder_assignment_rejected_missing_evidence_id",
            evidence_ids=_evidence_ids(case, (target,)), deterministic=True,
        )]
    # No nearest-person, arbitrary-window, candidate-order, or regex-text
    # fallback.  The office meaning itself is deterministic; its referent is
    # deliberately left empty until explicit holder syntax is supplied.
    return [_hypothesis(
        "h0", "patron_plus_office" if patron else "office_holder_reference", "person",
        ([_component(patron, "patron")] if patron else []) + [_component(office, "office")],
        basis="office_surface_without_proven_holder",
        evidence_ids=_evidence_ids(case, (target,)), deterministic=True,
    )]


def build_reference_hypotheses(case: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Build 1.3A hypotheses with only conservative office parsing."""
    target = str(case.get("target_surface") or "")
    text = _text(case)
    hypotheses: list[dict[str, Any]] = []
    hypotheses.extend(_office_hypotheses(case, target, text))
    if target == "主":
        marriage = re.search(r"(?P<actor>[\u3400-\u9fff]{1,8})(?:初)?尚主", text)
        if marriage:
            actor = marriage.group("actor")
            if actor.endswith("初"):
                actor = actor[:-1]
            hypotheses.append(_hypothesis(
                "h0", "non_person", "non_person",
                [_component(actor, "anchor_person"), _component("主", "title")],
                basis="explicit_marriage_object_syntax",
                evidence_ids=_evidence_ids(case, (actor, "尚主")), deterministic=True,
            ))
    if target in {"帝", "明帝", "武帝", "文帝", "元帝", "康帝", "晉武帝"}:
        hypotheses.append(_hypothesis(
            "h0", "ruler_reference", "ruler", [_component(target, "title")],
            basis="known_ruler_title_surface", evidence_ids=_evidence_ids(case, (target,)),
            deterministic=True,
        ))
    elif target == "陛下":
        hypotheses.append(_hypothesis(
            "h0", "honorific_person_reference", "ruler", [_component(target, "title")],
            basis="honorific_ruler_reference", evidence_ids=_evidence_ids(case, (target,)),
            deterministic=True,
        ))
    identity = base._explicit_identity_hypothesis(case, target, text)
    if identity:
        hypotheses.append(identity)
    if (
        str(case.get("occurrence_type") or "") == "title_reference"
        and len(target) >= 2
        and not any(row.get("surface_structure") in OFFICE_ROLE_STRUCTURES for row in hypotheses)
    ):
        hypotheses.append(_hypothesis(
            "title", "surname_plus_title", "person",
            [_component(target[:1], "surname"), _component(target[1:], "title")],
            basis="title_surface_requires_holder_resolution",
            evidence_ids=_evidence_ids(case, (target,)), deterministic=True,
        ))
    if target == "家兄" or not hypotheses:
        kinship = base._kinship_hypothesis(case, target, text)
        if kinship:
            hypotheses.append(kinship)
    elif any(target.endswith(marker) for marker in KINSHIP_MARKERS):
        kinship = base._kinship_hypothesis(case, target, text)
        if kinship:
            hypotheses.append(kinship)
    # Generic one-character/common honorific forms must not become a whole
    # person solely because one candidate profile contains that surface.
    if target not in GENERIC_PERSONAL_FORMS:
        lexical = base._whole_form_hypothesis(case, target, text)
        if lexical:
            hypotheses.append(lexical)
    if not hypotheses:
        hypotheses.append(_hypothesis("uncertain", "uncertain", "uncertain", [], basis="no_reliable_local_structure"))

    unique: dict[tuple[Any, ...], dict[str, Any]] = {}
    for row in hypotheses:
        key = (
            row.get("surface_structure"),
            row.get("referent_type"),
            tuple((component.get("text"), component.get("role")) for component in row.get("components", [])),
        )
        unique.setdefault(key, row)
    return list(unique.values())


def reference_hypotheses(case: Mapping[str, Any]) -> dict[str, Any]:
    hypotheses = build_reference_hypotheses(case)
    deterministic = [row for row in hypotheses if row.get("deterministic")]
    ambiguous = len(hypotheses) != 1 or len(deterministic) != 1
    return {
        "hypotheses": hypotheses,
        "ambiguous": ambiguous,
        "deterministic": len(deterministic) == 1 and not ambiguous,
        "deterministic_hypothesis": deterministic[0] if len(deterministic) == 1 and not ambiguous else None,
    }


def _holder_supported_by_exact_syntax(
    case: Mapping[str, Any],
    target: str,
    holder: str,
    evidence_ids: Sequence[str],
) -> bool:
    if not holder or not evidence_ids:
        return False
    office = next((value for value in OFFICE_SURFACES if target.endswith(value)), "")
    if not office:
        return False
    allowed_ids = {str(value) for value in evidence_ids}
    for row in _source_evidence(case):
        if str(row.get("evidence_id")) not in allowed_ids:
            continue
        text = str(row.get("text") or "")
        if target == office and target + holder in text:
            return True
        for connector in ("時爲", "時為", "爲", "為"):
            if holder + connector + target in text or "以" + holder + connector + target in text:
                return True
    return False


def _structure_fields(case: Mapping[str, Any], hypothesis: Mapping[str, Any], *, arbitration: Mapping[str, Any] | None = None) -> dict[str, Any]:
    fields = base._structure_fields(case, hypothesis, arbitration=arbitration)
    fields["derivation"] = "hdb2-psl1-3b-semantic-arbitration" if arbitration else "hdb2-psl1-3b-deterministic"
    structure = str(fields.get("surface_structure") or "uncertain")
    if structure in OFFICE_ROLE_STRUCTURES:
        holder = str(fields.get("holder") or "")
        target = str(case.get("target_surface") or "")
        eids = list(fields.get("evidence_ids") or [])
        supported = _holder_supported_by_exact_syntax(case, target, holder, eids)
        if not supported:
            # These nulls are a deliberate wire-level distinction from an
            # inferred holder.  They prevent stale OfficeCompatible/direct
            # support from being generated downstream.
            fields["holder"] = None
            fields["anchor_person"] = None
            fields["holder_assignment_evidence_ids"] = []
            fields["holder_assignment_rejected_reason"] = (
                "holder_missing" if not holder else "holder_syntax_or_evidence_not_grounded"
            )
        else:
            fields["holder_assignment_evidence_ids"] = sorted(set(str(value) for value in eids))
            fields["holder_assignment_rejected_reason"] = None
        fields["holder_evidence_satisfied"] = bool(supported)
    return fields


def finalize_reference_structure(
    case: Mapping[str, Any],
    arbitration: Mapping[str, Any] | None = None,
    validation: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    info = reference_hypotheses(case)
    hypotheses = info["hypotheses"]
    chosen: dict[str, Any] | None = None
    if info["deterministic"]:
        chosen = dict(info["deterministic_hypothesis"])
    elif arbitration and (validation or {}).get("valid") is True:
        chosen = base._find_hypothesis(
            hypotheses,
            str(arbitration.get("surface_structure") or "uncertain"),
            str(arbitration.get("referent_type") or "uncertain"),
        )
        if chosen and arbitration.get("confidence") in {"low", None}:
            chosen = None
        if chosen:
            chosen["components"] = [dict(row) for row in arbitration.get("components", []) or []]
            chosen["evidence_ids"] = list(arbitration.get("supporting_evidence_ids", []) or [])
            chosen["referent_type"] = arbitration.get("referent_type")
    if chosen is None:
        chosen = _hypothesis(
            "uncertain", "uncertain", "uncertain", [],
            basis="ambiguous_without_accepted_semantic_arbitration",
        )
        return _structure_fields(case, chosen, arbitration=arbitration)
    return _structure_fields(case, chosen, arbitration=arbitration)


def apply_reference_structures(graph: Mapping[str, Any], structures: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    """Apply 1.3B structures and clear all ungrounded office compatibility."""
    result = base.apply_reference_structures(graph, structures)
    for case in result.get("cases", []) or []:
        structure = case.get("reference_structure") or {}
        if str(structure.get("surface_structure") or "") not in OFFICE_ROLE_STRUCTURES:
            continue
        if structure.get("holder"):
            continue
        # psl1.1 can independently see a candidate title in a profile.  That
        # is not local holder syntax, so it must be neutral for this occurrence.
        for predicate in case.get("deterministic_predicates", []) or []:
            if predicate.get("predicate") != "OfficeCompatible":
                continue
            predicate["value"] = 0.5
            predicate["evidence_ids"] = []
            predicate["reason"] = "holder_unproven"
        case["reference_structure_direct_support"] = []
    result["schema"] = "hdb2-psl1-3b-graph-cases-v1"
    result["reference_structure_version"] = RUN_VERSION
    result["candidate_only"] = True
    result["canonical_write_back"] = False
    return result


def clean_structural_decisions(decisions: Mapping[str, Any], graph: Mapping[str, Any]) -> dict[str, Any]:
    result = base.clean_structural_decisions(decisions, graph)
    result["schema"] = "hdb2-psl1-3b-decisions-v1"
    result["reference_structure_version"] = RUN_VERSION
    result["candidate_only"] = True
    result["canonical_write_back"] = False
    return result


def arbitration_regression_payload(case: Mapping[str, Any], hypotheses: Sequence[Mapping[str, Any]]) -> dict[str, Any] | None:
    # Keep the prior offline fixture semantics for the known ambiguous form.
    if str(case.get("target_surface") or "") != "武子":
        return None
    chosen = next((row for row in hypotheses if row.get("surface_structure") == "lexicalized_personal_form"), None)
    if not chosen:
        return None
    return {
        "surface_structure": "lexicalized_personal_form",
        "referent_type": "person",
        "components": [{"text": "武子", "role": "personal_form"}],
        "supporting_evidence_ids": list(chosen.get("evidence_ids", []) or []),
        "confidence": "high",
    }


def reference_regression_records() -> dict[str, Any]:
    """Offline regression for safe office-holder and structural semantics."""
    expected: dict[tuple[str, str], dict[str, Any]] = {
        ("05-fangzheng-011", "武子"): {"surface_structure": "lexicalized_personal_form"},
        ("05-fangzheng-028", "敦主簿"): {"surface_structure": "patron_plus_office", "holder": "何充", "patron_or_possessor": "敦"},
        ("05-fangzheng-028", "家兄"): {"surface_structure": "compositional_kinship", "anchor_person": "王敦"},
        ("34-pilou-001", "主"): {"surface_structure": "non_person"},
        ("02-yanyu-046", "謝豫章"): {"surface_structure": "surname_plus_title", "top_candidate_forbidden": True},
        ("07-shijian-005", "僕射"): {"surface_structure": "office_holder_reference", "holder": "羊祜"},
        ("08-shangyu-043", "司空"): {"surface_structure": "office_holder_reference", "holder": "劉琨"},
        ("08-shangyu-051", "大將軍"): {"surface_structure": "office_holder_reference", "holder": "王敦"},
        ("17-shangshi-002", "尚書令"): {"surface_structure": "office_holder_reference", "holder": "王濬沖"},
    }
    graphs = [psl1_3.build_graph(psl1_3.freeze_selection()), *psl1_1.load_psl1_graphs()]
    by_key: dict[tuple[str, str], Mapping[str, Any]] = {}
    for graph in graphs:
        for case in graph.get("cases", []) or []:
            key = (str(case.get("story_id") or ""), str(case.get("target_surface") or ""))
            by_key.setdefault(key, case)
    records: list[dict[str, Any]] = []
    for key, expectation in expected.items():
        case = by_key.get(key)
        if not case:
            records.append({"story_id": key[0], "surface": key[1], "passed": False, "reason": "case_missing"})
            continue
        info = reference_hypotheses(case)
        arbitration = arbitration_regression_payload(case, info["hypotheses"])
        packet = semantic_packet(case, info["hypotheses"])
        validation = validate_semantic_arbitration(arbitration, packet) if arbitration else None
        structure = finalize_reference_structure(case, arbitration, validation)
        passed = structure.get("surface_structure") == expectation["surface_structure"]
        for field in ("holder", "patron_or_possessor", "anchor_person"):
            if field in expectation:
                passed = passed and structure.get(field) == expectation[field]
        records.append({
            "story_id": key[0],
            "surface": key[1],
            "expected": expectation,
            "actual": {
                "surface_structure": structure.get("surface_structure"),
                "holder": structure.get("holder"),
                "anchor_person": structure.get("anchor_person"),
                "patron_or_possessor": structure.get("patron_or_possessor"),
                "holder_evidence_satisfied": structure.get("holder_evidence_satisfied"),
            },
            "hypotheses": info["hypotheses"],
            "passed": bool(passed),
        })
    return {
        "schema": "hdb2-psl1-3b-reference-regressions-v1",
        "records": records,
        "all_pass": all(row.get("passed") for row in records),
        "candidate_only": True,
        "canonical_write_back": False,
    }


def holder_metrics(structures: Mapping[str, Mapping[str, Any]]) -> dict[str, int]:
    office = [row for row in structures.values() if str(row.get("surface_structure") or "") in OFFICE_ROLE_STRUCTURES]
    return {
        "office_reference_count": len(office),
        "deterministic_holder_count": sum(bool(row.get("holder_evidence_satisfied")) for row in office),
        "holder_with_empty_evidence_count": sum(bool(row.get("holder")) and not row.get("holder_assignment_evidence_ids") for row in office),
        "invalid_deterministic_holder_count": sum(
            bool(row.get("holder")) and not bool(row.get("holder_evidence_satisfied")) for row in office
        ),
        "unproven_holder_null_count": sum(not row.get("holder") for row in office),
    }


def structure_summary(structures: Mapping[str, Mapping[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in structures.values():
        key = str(row.get("surface_structure") or "uncertain")
        counts[key] = counts.get(key, 0) + 1
    return dict(sorted(counts.items()))
