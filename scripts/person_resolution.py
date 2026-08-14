#!/usr/bin/env python3
"""ER1 contextual Person-resolution overlay.

The canonical Mention files remain the historical segmentation/provenance
layer.  This module builds a deterministic, reviewable effective-resolution
projection on top of them.  A resolution target may be a production Person
or a known P3A.1 identity candidate; materialization is deliberately not part
of this layer.
"""

from __future__ import annotations

from collections import defaultdict
import hashlib
import json
from pathlib import Path
import re
from typing import Any, Iterable, Mapping

try:
    from .build_six_person_pilot import parse_shishuo_sections
except ImportError:  # direct execution
    from build_six_person_pilot import parse_shishuo_sections


MENTIONS_PATH = Path("data/mentions/shishuo.json")
PEOPLE_PATH = Path("data/people.json")
ALIASES_PATH = Path("data/aliases.json")
IDENTITY_CANDIDATES_PATH = Path("data/derived/person-identity-candidates.json")
DECISIONS_PATH = Path("data/annotation/person-resolution-decisions.json")
CORPUS_INDEX_PATH = Path("data/shishuo-corpus-index.json")
GOLD_PATH = Path("data/story-chain-gold-set.json")
EXPANSION_PATH = Path("data/annotation/story-expansion-wave-1.json")
EFFECTIVE_PATH = Path("data/derived/person-resolution-effective.json")
QUEUE_PATH = Path("data/derived/person-resolution-review-queue.json")
COLLISIONS_PATH = Path("data/derived/person-alias-collisions.json")
REPORT_PATH = Path("docs/person-resolution-review.md")

RESOLUTION_STATUSES = {"resolved", "candidate_for_review", "unresolved"}
REVIEW_STATUSES = {"candidate", "reviewed", "rejected", "todo"}
TARGET_KINDS = {"production_person", "identity_candidate"}
PUBLISHED_STATES = {"production_ready", "preview_ready"}


def read_json(root: Path, relative: Path) -> Any:
    return json.loads((root / relative).read_text(encoding="utf-8"))


def write_json(root: Path, relative: Path, value: Any) -> None:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=False) + "\n",
        encoding="utf-8",
    )


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _target_key(target: Mapping[str, Any]) -> str:
    kind = str(target.get("target_kind", ""))
    identifier = target.get("person_id") if kind == "production_person" else target.get("candidate_id")
    return f"{kind}:{identifier}"


def _target_sort_key(target: Mapping[str, Any]) -> tuple[str, str, str]:
    return (
        _target_key(target),
        str(target.get("canonical_name", "")),
        str(target.get("candidate_id", "")),
    )


def _target_copy(target: Mapping[str, Any]) -> dict[str, Any]:
    result = {
        "target_kind": str(target["target_kind"]),
        "canonical_name": str(target.get("canonical_name", "")),
    }
    if target.get("target_kind") == "production_person":
        result["person_id"] = str(target["person_id"])
    else:
        result["candidate_id"] = str(target["candidate_id"])
    return result


def _candidate_status(candidate: Mapping[str, Any]) -> str:
    return str(candidate.get("status", ""))


def _candidate_target(candidate: Mapping[str, Any], people_by_id: Mapping[str, Mapping[str, Any]]) -> dict[str, Any] | None:
    status = _candidate_status(candidate)
    if status == "already_materialized":
        person_id = candidate.get("matched_person_id")
        if isinstance(person_id, str) and person_id in people_by_id:
            return {
                "target_kind": "production_person",
                "person_id": person_id,
                "canonical_name": str(people_by_id[person_id].get("canonical_name", candidate.get("preferred_name", ""))),
            }
        return None
    if status in {"strong_candidate", "candidate"} and isinstance(candidate.get("preferred_name"), str) and candidate.get("preferred_name"):
        return {
            "target_kind": "identity_candidate",
            "candidate_id": str(candidate["candidate_id"]),
            "canonical_name": str(candidate["preferred_name"]),
        }
    return None


def _association(
    target: Mapping[str, Any],
    *,
    surface: str,
    alias_type: str,
    association_mode: str,
    association_strength: str,
    evidence_ids: Iterable[str] = (),
    basis: str,
) -> dict[str, Any]:
    return {
        "target": _target_copy(target),
        "surface": surface,
        "alias_type": alias_type,
        "association_mode": association_mode,
        "association_strength": association_strength,
        "evidence_ids": sorted({str(item) for item in evidence_ids if isinstance(item, str)}),
        "basis": basis,
    }


def _identity_cues(
    candidate: Mapping[str, Any],
    evidence_by_id: Mapping[str, Mapping[str, Any]],
    evidence_ids_override: Iterable[str] | None = None,
) -> list[dict[str, str]]:
    """Recover only explicit local X字Y-style cues from candidate evidence."""

    cues: list[dict[str, str]] = []
    candidate_name = str(candidate.get("preferred_name", ""))
    evidence_ids = list(dict.fromkeys([
        *(
            [str(item) for item in evidence_ids_override if isinstance(item, str)]
            if evidence_ids_override is not None
            else [
                *[str(item) for item in candidate.get("identity_evidence_ids", []) if isinstance(item, str)],
                *[str(item) for item in candidate.get("evidence_ids", []) if isinstance(item, str)],
            ]
        ),
    ]))
    pattern = re.compile(r"([\u3400-\u9fff]{1,3})[字名諱]([\u3400-\u9fff]{1,4})")
    for evidence_id in evidence_ids:
        evidence = evidence_by_id.get(evidence_id)
        if not evidence:
            continue
        quote = str(evidence.get("quote", ""))
        for match in pattern.finditer(quote):
            left = match.group(1)
            courtesy = match.group(2)
            # The candidate evidence itself is the identity bridge.  Keep
            # only a name-to-courtesy cue whose left side ends with the
            # candidate's own name suffix.  A biography can contain many
            # unrelated X字Y constructions; accepting all of them would turn
            # every courtesy name into a collision with every candidate.
            if candidate_name and left.endswith(candidate_name[-2:]):
                cues.append(
                    {
                        "left_form": left,
                        "surface": courtesy,
                        "cue": f"{left}字{courtesy}",
                        "evidence_id": evidence_id,
                    }
                )
    unique: dict[tuple[str, str, str], dict[str, str]] = {}
    for cue in cues:
        unique[(cue["left_form"], cue["surface"], cue["evidence_id"])] = cue
    return [unique[key] for key in sorted(unique)]


def _published_story_ids(root: Path) -> set[str]:
    gold = read_json(root, GOLD_PATH)
    ids = {str(item["entry_id"]) for item in gold.get("records", []) if isinstance(item, Mapping) and isinstance(item.get("entry_id"), str)}
    if (root / EXPANSION_PATH).is_file():
        expansion = read_json(root, EXPANSION_PATH)
        ids.update(
            str(item["story_id"])
            for item in expansion.get("records", [])
            if isinstance(item, Mapping) and isinstance(item.get("story_id"), str)
        )
    return ids


def _load_sections(root: Path) -> dict[tuple[str, str], str]:
    result: dict[tuple[str, str], str] = {}
    corpus = read_json(root, CORPUS_INDEX_PATH).get("entries", [])
    for entry in corpus:
        if not isinstance(entry, Mapping) or not isinstance(entry.get("id"), str):
            continue
        path = root / str(entry.get("path", ""))
        if not path.is_file():
            continue
        for section, text, metadata in parse_shishuo_sections(path.read_text(encoding="utf-8")):
            if section == "main_text":
                result[(str(entry["id"]), section)] = text.rstrip("\n")
            elif section == "liu_annotation":
                annotation_id = str(metadata.get("annotation_id", "annotation-001"))
                result[(str(entry["id"]), f"{section}:{annotation_id}")] = text.rstrip("\n")
    return result


def _mention_offset(mention: Mapping[str, Any]) -> int:
    value = mention.get("evidence", {}).get("section_offset", 0)
    return value if isinstance(value, int) else 0


def _section_text(sections: Mapping[tuple[str, str], str], mention: Mapping[str, Any]) -> str:
    story_id = str(mention.get("entry_id") or mention.get("source_id") or "")
    section = str(mention.get("section", "main_text"))
    if section == "main_text":
        return sections.get((story_id, section), "")
    metadata = mention.get("source_section_metadata", {})
    annotation_id = metadata.get("annotation_id") if isinstance(metadata, Mapping) else None
    if not isinstance(annotation_id, str):
        annotation_id = "annotation-001"
    return sections.get((story_id, f"liu_annotation:{annotation_id}"), "")


def _local_context_key(mention: Mapping[str, Any]) -> tuple[str, str, str]:
    """Keep antecedents inside one Story section/annotation block only."""

    story_id = str(mention.get("entry_id") or mention.get("source_id") or "")
    section = str(mention.get("section", "main_text"))
    if section == "liu_annotation":
        metadata = mention.get("source_section_metadata", {})
        annotation_id = metadata.get("annotation_id") if isinstance(metadata, Mapping) else None
        return story_id, section, str(annotation_id or "annotation-001")
    return story_id, section, "main_text"


def _context(text: str, offset: int, surface: str, width: int = 42) -> tuple[str, str]:
    start = max(0, offset - width)
    end = min(len(text), offset + len(surface) + width)
    return text[start:offset], text[offset + len(surface):end]


def _full_surface(text: str, offset: int, surface: str) -> str | None:
    if offset <= 0:
        return None
    prefix = text[offset - 1:offset]
    if not prefix or not re.match(r"[\u3400-\u9fff]", prefix):
        return None
    return prefix + surface


def _target_names(targets: Iterable[Mapping[str, Any]]) -> list[str]:
    return [str(target.get("canonical_name", "")) for target in targets]


def _association_candidates(
    alias_index: Mapping[str, list[Mapping[str, Any]]],
    surface: str,
) -> list[dict[str, Any]]:
    unique: dict[str, dict[str, Any]] = {}
    for item in alias_index.get(surface, []):
        key = _target_key(item["target"])
        if key not in unique:
            unique[key] = dict(item)
        else:
            unique[key]["evidence_ids"] = sorted({
                *unique[key].get("evidence_ids", []),
                *item.get("evidence_ids", []),
            })
            if item.get("association_strength") == "strong":
                unique[key]["association_strength"] = "strong"
    return sorted(unique.values(), key=lambda item: _target_sort_key(item["target"]))


def _target_from_association(item: Mapping[str, Any]) -> dict[str, Any]:
    return _target_copy(item["target"])


def _make_review_id(mention_id: str) -> str:
    return "review-" + hashlib.sha256(mention_id.encode("utf-8")).hexdigest()[:24]


def _build_alias_index(
    root: Path,
    people: list[Mapping[str, Any]],
    aliases: list[Mapping[str, Any]],
    candidates: list[Mapping[str, Any]],
    candidate_evidence: Mapping[str, Mapping[str, Any]],
) -> tuple[dict[str, list[dict[str, Any]]], dict[str, dict[str, Any]], list[dict[str, Any]]]:
    people_by_id = {str(item.get("person_id")): item for item in people if isinstance(item.get("person_id"), str)}
    targets_by_key: dict[str, dict[str, Any]] = {}
    for person_id, person in sorted(people_by_id.items()):
        target = {"target_kind": "production_person", "person_id": person_id, "canonical_name": str(person.get("canonical_name", ""))}
        targets_by_key[_target_key(target)] = target
    candidate_targets: dict[str, dict[str, Any]] = {}
    candidate_cues: dict[str, list[dict[str, str]]] = {}
    for candidate in candidates:
        if not isinstance(candidate, Mapping) or not isinstance(candidate.get("candidate_id"), str):
            continue
        target = _candidate_target(candidate, people_by_id)
        if target is None:
            continue
        target_key = _target_key(target)
        targets_by_key[target_key] = target
        candidate_targets[str(candidate["candidate_id"])] = target
        candidate_name = str(candidate.get("preferred_name", ""))
        cue_evidence = dict(candidate_evidence)
        # P3A.1 was intentionally open-world but its earlier closed-world
        # Mention scan can attach an evidence row to the materialized alias
        # owner.  An explicit X字Y statement is stronger than that stale
        # owner field, so recover matching identity cues from the shared
        # evidence pool without changing the P3A.1 artifact itself.
        for evidence_id, evidence in candidate_evidence.items():
            quote = str(evidence.get("quote", ""))
            if len(candidate_name) < 2:
                continue
            if any(
                match.group(1).endswith(candidate_name[-2:])
                for match in re.finditer(r"([\u3400-\u9fff]{1,3})[字名諱]([\u3400-\u9fff]{1,4})", quote)
            ):
                cue_evidence[evidence_id] = evidence
        candidate_cues[str(candidate["candidate_id"])] = _identity_cues(candidate, cue_evidence, cue_evidence.keys())

    alias_index: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for alias in aliases:
        surface = alias.get("surface")
        if not isinstance(surface, str) or not surface:
            continue
        mode = str(alias.get("resolution_mode", "ambiguous"))
        for person_id in alias.get("person_ids", []):
            if not isinstance(person_id, str) or person_id not in people_by_id:
                continue
            target = targets_by_key[f"production_person:{person_id}"]
            alias_index[surface].append(
                _association(
                    target,
                    surface=surface,
                    alias_type=str(alias.get("alias_type", "")),
                    association_mode=mode,
                    association_strength="strong" if mode == "exact" else "medium",
                    evidence_ids=[str(item.get("evidence_id")) for item in alias.get("source_evidence", []) if isinstance(item, Mapping) and isinstance(item.get("evidence_id"), str)],
                    basis="production_alias_registry",
                )
            )

    # P3A.1 surfaces are identity candidates, not production aliases.  They
    # are deliberately included here so materialization status cannot hide a
    # competing historical identity.
    for candidate in candidates:
        candidate_id = candidate.get("candidate_id") if isinstance(candidate, Mapping) else None
        if not isinstance(candidate_id, str) or candidate_id not in candidate_targets:
            continue
        target = candidate_targets[candidate_id]
        strength = "strong" if _candidate_status(candidate) in {"strong_candidate", "already_materialized"} else "medium"
        for surface_record in candidate.get("surfaces", []):
            if not isinstance(surface_record, Mapping) or not isinstance(surface_record.get("surface"), str):
                continue
            surface = str(surface_record["surface"])
            alias_index[surface].append(
                _association(
                    target,
                    surface=surface,
                    alias_type=str(surface_record.get("surface_type", "unknown_person_like_surface")),
                    association_mode=str(surface_record.get("association_mode", "ambiguous")),
                    association_strength=str(surface_record.get("association_strength", strength)),
                    evidence_ids=surface_record.get("evidence_ids", []),
                    basis="p3a1_candidate_surface",
                )
            )
        for cue in candidate_cues.get(candidate_id, []):
            evidence_ids = [cue["evidence_id"]]
            alias_index[cue["surface"]].append(
                _association(
                    target,
                    surface=cue["surface"],
                    alias_type="courtesy_name",
                    association_mode="exact",
                    association_strength="strong",
                    evidence_ids=evidence_ids,
                    basis="p3a1_explicit_identity_cue",
                )
            )
            canonical_name = str(target.get("canonical_name", ""))
            if canonical_name and len(canonical_name) >= 2:
                surname_form = canonical_name[0] + cue["surface"]
                alias_index[surname_form].append(
                    _association(
                        target,
                        surface=surname_form,
                        alias_type="surname_plus_courtesy_name",
                        association_mode="exact",
                        association_strength="strong",
                        evidence_ids=evidence_ids,
                        basis="p3a1_explicit_identity_cue",
                    )
                )

    # Stable de-duplication of identical semantic associations.
    for surface, values in list(alias_index.items()):
        unique: dict[tuple[str, str, str], dict[str, Any]] = {}
        for value in values:
            key = (_target_key(value["target"]), str(value.get("alias_type", "")), str(value.get("association_mode", "")))
            if key not in unique:
                unique[key] = dict(value)
            else:
                unique[key]["evidence_ids"] = sorted({
                    *unique[key].get("evidence_ids", []),
                    *value.get("evidence_ids", []),
                })
        alias_index[surface] = sorted(unique.values(), key=lambda item: (_target_sort_key(item["target"]), str(item.get("alias_type", "")), str(item.get("association_mode", ""))))

    return alias_index, targets_by_key, [
        {
            "candidate_id": candidate_id,
            "target": _target_copy(target),
            "cues": sorted(cues, key=lambda cue: (cue["surface"], cue["left_form"], cue["evidence_id"])),
        }
        for candidate_id, target in sorted(candidate_targets.items())
        for cues in [candidate_cues.get(candidate_id, [])]
    ]


def _decision_map(root: Path) -> dict[str, Mapping[str, Any]]:
    document = read_json(root, DECISIONS_PATH)
    decisions = document.get("decisions", [])
    result: dict[str, Mapping[str, Any]] = {}
    for decision in decisions:
        if not isinstance(decision, Mapping) or not isinstance(decision.get("mention_id"), str):
            continue
        if decision.get("review_status") == "reviewed":
            result[str(decision["mention_id"])] = decision
    return result


def _validate_decision_target(
    decision: Mapping[str, Any],
    targets_by_key: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    target = decision.get("target")
    if not isinstance(target, Mapping) or target.get("target_kind") not in TARGET_KINDS:
        raise ValueError(f"reviewed decision has invalid target: {decision.get('mention_id')}")
    normalized = _target_copy(target)
    key = _target_key(normalized)
    known = targets_by_key.get(key)
    if known is None:
        raise ValueError(f"reviewed decision target is not a known identity: {decision.get('mention_id')}")
    if normalized.get("canonical_name") != known.get("canonical_name"):
        raise ValueError(f"reviewed decision target name mismatch: {decision.get('mention_id')}")
    return _target_copy(known)


def _local_context_targets(
    mention: Mapping[str, Any],
    text: str,
    associations: list[Mapping[str, Any]],
    alias_index: Mapping[str, list[Mapping[str, Any]]],
    prior_targets: list[Mapping[str, Any]],
    cues_by_target: Mapping[str, list[Mapping[str, str]]],
) -> tuple[list[dict[str, Any]], list[str]]:
    """Find only strong same-Story signals for a colliding surface."""

    surface = str(mention.get("surface", ""))
    offset = _mention_offset(mention)
    candidates_by_key = {_target_key(item["target"]): item for item in associations}
    selected: dict[str, dict[str, Any]] = {}
    signals: list[str] = []

    full = _full_surface(text, offset, surface)
    if full:
        for item in alias_index.get(full, []):
            key = _target_key(item["target"])
            if key in candidates_by_key:
                selected[key] = _target_copy(item["target"])
                signals.append(f"explicit_full_surface:{full}")

    # An explicit full canonical name already transmitted in the same local
    # Story is a safe antecedent for a subsequent compatible courtesy name.
    for item in associations:
        target = item["target"]
        canonical_name = str(target.get("canonical_name", ""))
        if canonical_name and canonical_name in text[:offset]:
            selected[_target_key(target)] = _target_copy(target)
            signals.append(f"story_local_full_name:{canonical_name}")

    # X字Y / X名Y cues from the candidate's own evidence are accepted only
    # when that exact cue is present in the same local section.
    window_start = max(0, offset - 120)
    window_end = min(len(text), offset + len(surface) + 80)
    local_window = text[window_start:window_end]
    for item in associations:
        key = _target_key(item["target"])
        canonical_name = str(item["target"].get("canonical_name", ""))
        # A Liu annotation often states the identity in the compact form
        # ``凝之字叔平`` rather than repeating the surname.  The canonical
        # identity's final two characters plus an explicit 字/名/諱 cue is a
        # safe local bridge; it is not a global alias rule.
        if canonical_name and len(canonical_name) >= 2:
            local_name_cue = re.escape(canonical_name[-2:]) + r"[字名諱]" + re.escape(surface)
            reverse_name_cue = re.escape(canonical_name[-2:]) + r"[字名諱]"
            if re.search(local_name_cue, local_window) or (
                surface in local_window and re.search(reverse_name_cue, local_window)
            ):
                selected[key] = _target_copy(item["target"])
                signals.append(f"explicit_local_name_cue:{canonical_name[-2:]}字{surface}")
        for cue in cues_by_target.get(key, []):
            if str(cue.get("cue", "")) in local_window and str(cue.get("surface", "")) == surface:
                selected[key] = _target_copy(item["target"])
                signals.append(f"explicit_identity_cue:{cue['cue']}")

    # A resolved prior mention of the same colliding courtesy name is a local
    # antecedent.  It never crosses Story or section boundaries.
    for prior in prior_targets:
        key = _target_key(prior)
        if key in candidates_by_key:
            selected[key] = _target_copy(prior)
            signals.append("story_local_antecedent")

    return sorted(selected.values(), key=_target_sort_key), sorted(set(signals))


def resolve_mention(
    mention: Mapping[str, Any],
    *,
    text: str,
    alias_index: Mapping[str, list[Mapping[str, Any]]],
    targets_by_key: Mapping[str, Mapping[str, Any]],
    prior_targets: list[Mapping[str, Any]] = (),
    cues_by_target: Mapping[str, list[Mapping[str, str]]] | None = None,
    decision: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Resolve one canonical Mention into the ER1 effective target state."""

    mention_id = str(mention.get("mention_id", ""))
    if decision is not None:
        target = _validate_decision_target(decision, targets_by_key)
        return {
            "status": "resolved",
            "target": target,
            "candidates": [target],
            "signals": ["human_reviewed_decision"],
            "reasons": [],
            "review_status": "reviewed",
            "decision_source": "human_review",
            "review_note": str(decision.get("review_note", "")),
            "resolution_evidence_ids": sorted({str(item) for item in decision.get("evidence_ids", []) if isinstance(item, str)}),
        }

    surface = str(mention.get("surface", ""))
    associations = _association_candidates(alias_index, surface)
    candidate_targets = [_target_from_association(item) for item in associations]
    cues_by_target = cues_by_target or {}
    local_targets, local_signals = _local_context_targets(
        mention,
        text,
        associations,
        alias_index,
        list(prior_targets),
        cues_by_target,
    )
    reasons: list[str] = []
    signals = list(local_signals)

    if local_targets:
        if len(local_targets) == 1:
            target = local_targets[0]
            association = next((item for item in associations if _target_key(item["target"]) == _target_key(target)), None)
            return {
                "status": "resolved",
                "target": target,
                "candidates": candidate_targets,
                "signals": signals,
                "reasons": [],
                "review_status": "candidate",
                "decision_source": "automatic",
                "review_note": "",
                "resolution_evidence_ids": sorted({
                    *[str(item) for item in (association or {}).get("evidence_ids", []) if isinstance(item, str)],
                    *[str(item) for item in mention.get("evidence", {}).get("evidence_ids", []) if isinstance(item, str)],
                }),
            }
        reasons.append("multiple_compatible_local_antecedents")

    unique_associations = [
        item
        for item in associations
        if _target_key(item["target"]) == _target_key(candidate_targets[0])
    ] if len(candidate_targets) == 1 else []
    unique_is_exact = bool(unique_associations) and all(
        str(item.get("association_mode", "")) == "exact"
        for item in unique_associations
    )

    if len(candidate_targets) == 1 and not reasons and unique_is_exact:
        target = candidate_targets[0]
        return {
            "status": "resolved",
            "target": target,
            "candidates": candidate_targets,
            "signals": ["unique_exact_or_structured_alias"],
            "reasons": [],
            "review_status": "candidate",
            "decision_source": "automatic",
            "review_note": "",
            "resolution_evidence_ids": sorted({str(item) for item in mention.get("evidence", {}).get("evidence_ids", []) if isinstance(item, str)}),
            "resolution_mode": "exact",
        }

    # A legacy production Mention may already carry a single contextual
    # target from the reviewed/structured pipeline.  Preserve that existing
    # decision as contextual evidence, but never use a contextual registry
    # entry to resolve a previously unresolved surface globally.  This keeps
    # existing safe Person controls working while making the distinction
    # explicit in the effective layer.
    raw_person_id = mention.get("person_id")
    if len(candidate_targets) == 1 and not reasons and not unique_is_exact:
        target = candidate_targets[0]
        if (
            isinstance(raw_person_id, str)
            and _target_key(target) == f"production_person:{raw_person_id}"
        ):
            return {
                "status": "resolved",
                "target": target,
                "candidates": candidate_targets,
                "signals": ["existing_contextual_resolution"],
                "reasons": [],
                "review_status": "candidate",
                "decision_source": "automatic",
                "review_note": "",
                "resolution_evidence_ids": sorted({
                    *[str(item) for item in unique_associations[0].get("evidence_ids", []) if isinstance(item, str)],
                    *[str(item) for item in mention.get("evidence", {}).get("evidence_ids", []) if isinstance(item, str)],
                }),
                "resolution_mode": "contextual",
            }

    if len(candidate_targets) > 1 or (len(candidate_targets) == 1 and not unique_is_exact):
        if len(candidate_targets) > 1:
            reasons.extend(
                ["shared_alias_surface", "insufficient_unique_local_context"]
                if not reasons
                else ["shared_alias_surface"]
            )
        else:
            reasons.append("contextual_surface_requires_local_evidence")
        return {
            "status": "candidate_for_review",
            "target": None,
            "candidates": candidate_targets,
            "signals": sorted(set(signals)),
            "reasons": sorted(set(reasons)),
            "review_status": "candidate",
            "decision_source": "automatic",
            "review_note": "",
            "resolution_evidence_ids": sorted({str(item) for item in mention.get("evidence", {}).get("evidence_ids", []) if isinstance(item, str)}),
            "resolution_mode": "ambiguous",
        }

    if isinstance(raw_person_id, str):
        target = targets_by_key.get(f"production_person:{raw_person_id}")
        if target is not None:
            return {
                "status": "resolved",
                "target": _target_copy(target),
                "candidates": [_target_copy(target)],
                "signals": ["existing_production_resolution_without_collision"],
                "reasons": [],
                "review_status": "candidate",
                "decision_source": "automatic",
                "review_note": "",
                "resolution_evidence_ids": sorted({str(item) for item in mention.get("evidence", {}).get("evidence_ids", []) if isinstance(item, str)}),
                "resolution_mode": str(mention.get("resolution_mode") or "exact"),
            }
    return {
        "status": "unresolved",
        "target": None,
        "candidates": [],
        "signals": [],
        "reasons": ["insufficient_identity_evidence"],
        "review_status": "candidate",
        "decision_source": "automatic",
        "review_note": "",
        "resolution_evidence_ids": sorted({str(item) for item in mention.get("evidence", {}).get("evidence_ids", []) if isinstance(item, str)}),
    }


def apply_reviewed_decision(
    automatic_result: Mapping[str, Any],
    reviewed_result: Mapping[str, Any],
) -> dict[str, Any]:
    """Keep a reviewed result authoritative while recording later conflicts."""

    automatic_target = automatic_result.get("target")
    reviewed_target = reviewed_result.get("target")
    automatic_key = _target_key(automatic_target) if isinstance(automatic_target, Mapping) else None
    reviewed_key = _target_key(reviewed_target) if isinstance(reviewed_target, Mapping) else None
    if automatic_result.get("status") == reviewed_result.get("status") and automatic_key == reviewed_key:
        return dict(reviewed_result)
    return {
        **reviewed_result,
        "review_conflict": {
            "automatic_status": automatic_result.get("status"),
            "automatic_target": automatic_target,
            "automatic_reasons": list(automatic_result.get("reasons", [])),
        },
    }


def _effective_mention(mention: Mapping[str, Any], result: Mapping[str, Any]) -> dict[str, Any]:
    effective = dict(mention)
    target = result.get("target")
    status = str(result.get("status"))
    effective["resolution_status"] = status
    effective["resolution_target"] = _target_copy(target) if isinstance(target, Mapping) else None
    effective["resolution_candidates"] = [
        _target_copy(item)
        for item in result.get("candidates", [])
        if isinstance(item, Mapping)
    ]
    effective["resolution_review_status"] = str(result.get("review_status", "candidate"))
    effective["resolution_decision_source"] = str(result.get("decision_source", "automatic"))
    effective["resolution_evidence_ids"] = sorted({str(item) for item in result.get("resolution_evidence_ids", []) if isinstance(item, str)})
    effective["resolution_note"] = str(result.get("review_note", ""))
    if isinstance(result.get("resolution_mode"), str) and result.get("resolution_mode"):
        effective["resolution_mode"] = str(result["resolution_mode"])
    if isinstance(result.get("review_conflict"), Mapping):
        effective["resolution_conflict"] = dict(result["review_conflict"])
    if isinstance(target, Mapping) and target.get("target_kind") == "production_person" and status == "resolved":
        effective["person_id"] = str(target["person_id"])
        effective["candidate_person_ids"] = [str(target["person_id"])]
        # Keep the canonical Mention's review confidence when the automatic
        # resolver merely supplies a safer target.  This preserves the
        # existing PersonStory distinction between supporting and candidate
        # Mention evidence; resolution certainty and editorial review status
        # are separate concepts.
        if result.get("decision_source") == "automatic" and mention.get("confidence") in {"high", "medium", "low"}:
            effective["confidence"] = mention.get("confidence")
        else:
            effective["confidence"] = "high"
    else:
        # A correctly identified non-materialized or uncertain Mention must
        # not create a production PersonStory/navigation edge.
        effective["person_id"] = None
        effective["candidate_person_ids"] = []
        if status == "candidate_for_review":
            effective["confidence"] = "low"
        elif status == "unresolved":
            effective["confidence"] = "unresolved"
        else:
            effective["confidence"] = "high"
    if status == "resolved" and isinstance(target, Mapping) and target.get("target_kind") == "identity_candidate":
        effective["resolution_mode"] = "exact"
        effective["resolution_method"] = "er1_identity_candidate_resolution"
    elif status == "candidate_for_review":
        effective["resolution_mode"] = "ambiguous"
        effective["resolution_method"] = "er1_candidate_for_review"
    elif status == "unresolved":
        effective["resolution_mode"] = "ambiguous"
        effective["resolution_method"] = "er1_unresolved"
    return effective


def _queue_candidate(
    association: Mapping[str, Any],
    *,
    chosen_target: Mapping[str, Any] | None,
    reasons: list[str],
) -> dict[str, Any]:
    target = association.get("target", {})
    return {
        **_target_copy(target),
        "alias_basis": str(association.get("alias_type", "")),
        "evidence_basis": str(association.get("basis", "")),
        "evidence_ids": sorted({str(item) for item in association.get("evidence_ids", []) if isinstance(item, str)}),
        "supporting_signals": [
            str(association.get("association_mode", "")),
            str(association.get("association_strength", "")),
        ],
        "conflicting_signals": list(reasons) if chosen_target is None or _target_key(target) != _target_key(chosen_target) else [],
    }


def _review_record(
    mention: Mapping[str, Any],
    result: Mapping[str, Any],
    *,
    text: str,
    associations: list[Mapping[str, Any]],
) -> dict[str, Any]:
    offset = _mention_offset(mention)
    context_before, context_after = _context(text, offset, str(mention.get("surface", "")))
    target = result.get("target")
    candidates = [
        _queue_candidate(item, chosen_target=target if isinstance(target, Mapping) else None, reasons=[str(item) for item in result.get("reasons", [])])
        for item in associations
    ]
    recommended = _target_copy(target) if isinstance(target, Mapping) else None
    return {
        "review_id": _make_review_id(str(mention.get("mention_id", ""))),
        "mention_id": str(mention.get("mention_id", "")),
        "story_id": str(mention.get("entry_id") or mention.get("source_id") or ""),
        "section": str(mention.get("section", "main_text")),
        "surface": str(mention.get("surface", "")),
        "context_before": context_before,
        "context_after": context_after,
        "resolution_status": str(result.get("status")),
        "candidates": candidates,
        "recommended_target": recommended,
        "ambiguity_reasons": sorted({str(item) for item in result.get("reasons", [])}),
        "automatic_confidence": "high" if result.get("status") == "resolved" else "low" if result.get("status") == "candidate_for_review" else "unresolved",
        "review_status": str(result.get("review_status", "candidate")),
        "review_note": str(result.get("review_note", "")),
        "decision_source": str(result.get("decision_source", "automatic")),
        "evidence_ids": sorted({
            *[str(item) for item in mention.get("evidence", {}).get("evidence_ids", []) if isinstance(item, str)],
            *[str(item) for item in result.get("resolution_evidence_ids", []) if isinstance(item, str)],
        }),
        **(
            {"review_conflict": dict(result["review_conflict"])}
            if isinstance(result.get("review_conflict"), Mapping)
            else {}
        ),
    }


def _collision_document(
    alias_index: Mapping[str, list[Mapping[str, Any]]],
    effective_mentions: list[Mapping[str, Any]],
    published_ids: set[str],
) -> dict[str, Any]:
    by_surface: dict[str, list[Mapping[str, Any]]] = {}
    for surface, associations in alias_index.items():
        target_keys = {_target_key(item["target"]) for item in associations}
        if len(target_keys) > 1:
            by_surface[surface] = associations
    records: list[dict[str, Any]] = []
    for surface in sorted(by_surface):
        associations = by_surface[surface]
        occurrences = [item for item in effective_mentions if item.get("surface") == surface]
        published_occurrences = [item for item in occurrences if str(item.get("entry_id") or item.get("source_id")) in published_ids]
        target_records: dict[str, dict[str, Any]] = {}
        for association in associations:
            target = association["target"]
            key = _target_key(target)
            target_records.setdefault(
                key,
                {
                    **_target_copy(target),
                    "alias_types": [],
                    "association_modes": [],
                    "evidence_ids": [],
                },
            )
            row = target_records[key]
            if association.get("alias_type") not in row["alias_types"]:
                row["alias_types"].append(association.get("alias_type"))
            if association.get("association_mode") not in row["association_modes"]:
                row["association_modes"].append(association.get("association_mode"))
            row["evidence_ids"] = sorted({*row["evidence_ids"], *association.get("evidence_ids", [])})
        current_resolutions = [
            {
                "mention_id": str(item.get("mention_id")),
                "story_id": str(item.get("entry_id") or item.get("source_id")),
                "resolution_status": item.get("resolution_status"),
                "target": item.get("resolution_target"),
            }
            for item in published_occurrences
            if item.get("resolution_status") != "unresolved"
        ]
        records.append(
            {
                "surface": surface,
                "candidate_identities": sorted(target_records.values(), key=_target_sort_key),
                "alias_types": sorted({str(item.get("alias_type", "")) for item in associations}),
                "occurrence_count": len(occurrences),
                "story_count": len({str(item.get("entry_id") or item.get("source_id")) for item in occurrences}),
                "published_occurrence_count": len(published_occurrences),
                "published_story_count": len({str(item.get("entry_id") or item.get("source_id")) for item in published_occurrences}),
                "current_automatic_resolutions": sorted(current_resolutions, key=lambda item: (item["story_id"], item["mention_id"])),
                "resolution_policy": "never globally unique; require Story-local evidence or human review",
            }
        )
    return {
        "schema": 1,
        "stage": "er1-person-alias-collisions",
        "generated_from": [str(IDENTITY_CANDIDATES_PATH), str(ALIASES_PATH), str(MENTIONS_PATH)],
        "collision_count": len(records),
        "records": records,
    }


def _render_report(
    queue: Mapping[str, Any],
    collisions: Mapping[str, Any],
    *,
    wang_candidate_id: str,
) -> str:
    counts = queue.get("counts", {})
    lines = [
        "# Person resolution review",
        "",
        "ER1 builds a deterministic effective-resolution overlay above the canonical Mention anchors. It does not materialize Persons or rewrite canonical text. A reviewed decision in `data/annotation/person-resolution-decisions.json` takes precedence over automatic output.",
        "",
        "## Summary",
        "",
        f"- published Mention records audited: {counts.get('published_mention_count', 0)}",
        f"- safely auto-resolved: {counts.get('auto_resolved_safe_count', 0)}",
        f"- candidate for review: {counts.get('candidate_for_review_count', 0)}",
        f"- unresolved: {counts.get('unresolved_count', 0)}",
        f"- reviewed decisions applied: {counts.get('reviewed_decision_count', 0)}",
        f"- shared identity surfaces: {collisions.get('collision_count', 0)}",
        "",
        "## Resolution precedence",
        "",
        "1. reviewed human decision; 2. explicit full identity; 3. same-Story/section local antecedent; 4. explicit identity cue in the local Liu annotation; 5. unique exact alias; 6. shared alias as candidate_for_review; 7. insufficient evidence as unresolved.",
        "",
        "Production status is a navigation capability, not an identity-confidence signal. An identity-candidate target is displayed as identified but remains non-navigable until a later materialization review.",
        "",
        "## Known regression: 05-fangzheng-058",
        "",
        f"- identity candidate: `王坦之` ({wang_candidate_id})",
        "- `王文度` is a local surname + courtesy-name cue; subsequent `文度` mentions inherit the same Story-local antecedent.",
        "- all seven affected Mentions are reviewed to 王坦之 and no longer resolve to 孫晷 / `person-015`.",
        "- 王坦之 is not a production Person, so these surfaces remain non-navigable in the reader.",
        "",
        "## Shared alias collisions",
        "",
    ]
    for record in collisions.get("records", [])[:40]:
        names = "、".join(str(item.get("canonical_name", "")) for item in record.get("candidate_identities", []))
        lines.append(
            f"- `{record.get('surface')}` → {names} · {record.get('published_occurrence_count', 0)} published occurrences; never globally exact"
        )
    lines.extend(["", "## Review queue", ""])
    queue_records = queue.get("records", [])
    for record in queue_records:
        if record.get("resolution_status") == "resolved" and record.get("review_status") != "reviewed":
            continue
        lines.extend(
            [
                f"### {record.get('story_id')} · {record.get('surface')}",
                "",
                f"- Mention: `{record.get('mention_id')}` · section: `{record.get('section')}` · status: `{record.get('resolution_status')}` · review: `{record.get('review_status')}`",
                f"- Context: {record.get('context_before', '')}【{record.get('surface', '')}】{record.get('context_after', '')}",
            ]
        )
        if record.get("recommended_target"):
            lines.append(f"- Recommendation: {record['recommended_target'].get('canonical_name', '')}")
        if record.get("ambiguity_reasons"):
            lines.append(f"- Reasons: {'、'.join(record['ambiguity_reasons'])}")
        lines.append("- Candidates:")
        for candidate in record.get("candidates", []):
            sign = "；".join(candidate.get("supporting_signals", []))
            conflict = "；".join(candidate.get("conflicting_signals", [])) or "无"
            lines.append(f"  - {candidate.get('canonical_name')} · {candidate.get('target_kind')} · supporting: {sign} · conflicting: {conflict}")
        if record.get("review_note"):
            lines.append(f"- Review note: {record['review_note']}")
        if record.get("review_conflict"):
            conflict = record["review_conflict"]
            automatic_target = conflict.get("automatic_target") or {}
            lines.append(
                f"- Automatic-review conflict: automatic={conflict.get('automatic_status')}"
                f"/{automatic_target.get('canonical_name', '无目标')}；已审核决定优先保留。"
            )
        lines.append("")
    lines.extend(
        [
            "## Manual correction workflow",
            "",
            "审阅此报告后，编辑 `data/annotation/person-resolution-decisions.json`，保留稳定的 Mention ID 与 Evidence ID；然后重新运行 `python3 scripts/build_person_resolution.py`，再重建 PersonStory 与 SC1。自动解析器更新不得覆盖已审核决定；若新证据与决定冲突，应进入报告而不是静默改写决定。",
            "",
        ]
    )
    return "\n".join(lines)


def build(root: Path) -> dict[str, Any]:
    people = read_json(root, PEOPLE_PATH).get("people", [])
    aliases = read_json(root, ALIASES_PATH).get("aliases", [])
    mentions = read_json(root, MENTIONS_PATH).get("mentions", [])
    candidate_document = read_json(root, IDENTITY_CANDIDATES_PATH)
    candidates = candidate_document.get("candidates", [])
    candidate_evidence = {
        str(item.get("id")): item
        for item in candidate_document.get("evidence", [])
        if isinstance(item, Mapping) and isinstance(item.get("id"), str)
    }
    alias_index, targets_by_key, candidate_metadata = _build_alias_index(
        root,
        people,
        aliases,
        candidates,
        candidate_evidence,
    )
    decision_map = _decision_map(root)
    sections = _load_sections(root)
    cues_by_target: dict[str, list[dict[str, str]]] = defaultdict(list)
    for item in candidate_metadata:
        target_key = _target_key(item["target"])
        cues_by_target[target_key].extend(item.get("cues", []))
    for key in list(cues_by_target):
        cues_by_target[key] = sorted(cues_by_target[key], key=lambda item: (item.get("surface", ""), item.get("left_form", ""), item.get("evidence_id", "")))

    sorted_mentions = sorted(
        [item for item in mentions if isinstance(item, Mapping)],
        key=lambda item: (
            str(item.get("entry_id") or item.get("source_id") or ""),
            str(item.get("section", "")),
            _mention_offset(item),
            str(item.get("mention_id", "")),
        ),
    )
    local_state: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    effective_mentions: list[dict[str, Any]] = []
    review_records: list[dict[str, Any]] = []
    published_ids = _published_story_ids(root)
    for mention in sorted_mentions:
        story_id = str(mention.get("entry_id") or mention.get("source_id") or "")
        section = str(mention.get("section", "main_text"))
        text = _section_text(sections, mention)
        prior = local_state[_local_context_key(mention)]
        decision = decision_map.get(str(mention.get("mention_id")))
        automatic_result = resolve_mention(
            mention,
            text=text,
            alias_index=alias_index,
            targets_by_key=targets_by_key,
            # A local antecedent is only compatible when it repeats the same
            # historical surface. This prevents an unrelated resolved name
            # earlier in the Story from becoming evidence for a later shared
            # courtesy name.
            prior_targets=[
                item["target"]
                for item in prior
                if item.get("surface") == mention.get("surface")
                and isinstance(item.get("target"), Mapping)
            ],
            cues_by_target=cues_by_target,
            decision=None,
        )
        result = automatic_result
        if decision is not None:
            reviewed_result = resolve_mention(
                mention,
                text=text,
                alias_index=alias_index,
                targets_by_key=targets_by_key,
                prior_targets=[
                    item["target"]
                    for item in prior
                    if item.get("surface") == mention.get("surface")
                    and isinstance(item.get("target"), Mapping)
                ],
                cues_by_target=cues_by_target,
                decision=decision,
            )
            result = apply_reviewed_decision(automatic_result, reviewed_result)
        effective = _effective_mention(mention, result)
        effective_mentions.append(effective)
        if result.get("status") == "resolved" and isinstance(result.get("target"), Mapping):
            local_state[_local_context_key(mention)].append({
                "offset": _mention_offset(mention),
                "surface": mention.get("surface"),
                "target": result["target"],
                "decision_source": result.get("decision_source"),
            })
        if story_id in published_ids and (
            result.get("status") != "resolved"
            or result.get("decision_source") == "human_review"
            or (isinstance(result.get("target"), Mapping) and result["target"].get("target_kind") == "identity_candidate")
        ):
            review_records.append(
                _review_record(
                    mention,
                    result,
                    text=text,
                    associations=_association_candidates(alias_index, str(mention.get("surface", ""))),
                )
            )

    effective_mentions.sort(key=lambda item: str(item.get("mention_id", "")))
    review_records.sort(key=lambda item: (
        str(item.get("story_id", "")),
        str(item.get("section", "")),
        next((_mention_offset(mention) for mention in mentions if mention.get("mention_id") == item.get("mention_id")), 10**9),
        str(item.get("mention_id", "")),
        str(item.get("surface", "")),
    ))
    counts = {
        "mention_count": len(effective_mentions),
        "published_mention_count": sum(str(item.get("entry_id") or item.get("source_id")) in published_ids for item in effective_mentions),
        "auto_resolved_safe_count": sum(item.get("resolution_status") == "resolved" and item.get("resolution_decision_source") == "automatic" for item in effective_mentions if str(item.get("entry_id") or item.get("source_id")) in published_ids),
        "candidate_for_review_count": sum(item.get("resolution_status") == "candidate_for_review" for item in effective_mentions if str(item.get("entry_id") or item.get("source_id")) in published_ids),
        "unresolved_count": sum(item.get("resolution_status") == "unresolved" for item in effective_mentions if str(item.get("entry_id") or item.get("source_id")) in published_ids),
        "reviewed_decision_count": sum(item.get("resolution_decision_source") == "human_review" for item in effective_mentions if str(item.get("entry_id") or item.get("source_id")) in published_ids),
    }
    effective_document = {
        "schema": 1,
        "stage": "er1-effective-person-resolution",
        "generated_from": [str(MENTIONS_PATH), str(ALIASES_PATH), str(IDENTITY_CANDIDATES_PATH), str(DECISIONS_PATH)],
        "source_mentions_sha256": sha256_file(root / MENTIONS_PATH),
        "decision_sha256": sha256_file(root / DECISIONS_PATH),
        "mention_count": len(effective_mentions),
        "counts": counts,
        "mentions": effective_mentions,
    }
    collision_document = _collision_document(alias_index, effective_mentions, published_ids)
    queue_document = {
        "schema": 1,
        "stage": "er1-person-resolution-review-queue",
        "generated_from": [str(EFFECTIVE_PATH), str(COLLISIONS_PATH)],
        "counts": {
            **counts,
            "review_queue_record_count": len(review_records),
        },
        "records": review_records,
    }
    wang_candidate_id = "candidate-identity-067-liezhuan-002-e72bf92e965f"
    report = _render_report(queue_document, collision_document, wang_candidate_id=wang_candidate_id)
    write_json(root, EFFECTIVE_PATH, effective_document)
    write_json(root, QUEUE_PATH, queue_document)
    write_json(root, COLLISIONS_PATH, collision_document)
    (root / REPORT_PATH).parent.mkdir(parents=True, exist_ok=True)
    (root / REPORT_PATH).write_text(report, encoding="utf-8")
    return effective_document


def load_effective_mentions(root: Path) -> list[dict[str, Any]]:
    path = root / EFFECTIVE_PATH
    if path.is_file():
        document = read_json(root, EFFECTIVE_PATH)
        mentions = document.get("mentions")
        if isinstance(mentions, list):
            return [dict(item) for item in mentions if isinstance(item, Mapping)]
    return [dict(item) for item in read_json(root, MENTIONS_PATH).get("mentions", []) if isinstance(item, Mapping)]
