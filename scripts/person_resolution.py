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
    from .reading_layers import effective_annotation_id
except ImportError:  # direct execution
    from build_six_person_pilot import parse_shishuo_sections
    from reading_layers import effective_annotation_id


MENTIONS_PATH = Path("data/mentions/shishuo.json")
PEOPLE_PATH = Path("data/people.json")
ALIASES_PATH = Path("data/aliases.json")
IDENTITY_CANDIDATES_PATH = Path("data/derived/person-identity-candidates.json")
# A small curated ER overlay is allowed to name a source-supported historical
# identity that P3A.1 did not seed as a standalone biography subject.  These
# are resolution targets only; they are never production Persons.
IDENTITY_TARGETS_PATH = Path("data/annotation/person-resolution-identity-candidates.json")
DECISIONS_PATH = Path("data/annotation/person-resolution-decisions.json")
CORPUS_INDEX_PATH = Path("data/shishuo-corpus-index.json")
GOLD_PATH = Path("data/story-chain-gold-set.json")
EXPANSION_PATH = Path("data/annotation/story-expansion-wave-1.json")
W3_EXPANSION_PATH = Path("data/annotation/story-expansion-wave-3.json")
W4_EXPANSION_PATH = Path("data/annotation/story-expansion-wave-4.json")
EFFECTIVE_PATH = Path("data/derived/person-resolution-effective.json")
QUEUE_PATH = Path("data/derived/person-resolution-review-queue.json")
COLLISIONS_PATH = Path("data/derived/person-alias-collisions.json")
REPORT_PATH = Path("docs/person-resolution-review.md")
SPAN_DECISIONS_PATH = Path("data/annotation/person-resolution-span-decisions.json")
SPAN_AUDIT_PATH = Path("data/derived/person-resolution-span-audit.json")
SPAN_REPORT_PATH = Path("docs/person-resolution-span-audit.md")
LEXICAL_ALIAS_RULES_PATH = Path("data/annotation/person-resolution-lexical-alias-rules.json")
LEXICAL_COLLISION_AUDIT_PATH = Path("data/derived/person-resolution-lexical-collision-audit.json")
MATERIALIZED_PERSON_WAVE_PATHS = (
    Path("data/annotation/person-expansion-wave-1.json"),
    Path("data/annotation/person-expansion-wave-2.json"),
    Path("data/annotation/person-expansion-wave-3.json"),
    Path("data/annotation/person-expansion-wave-4.json"),
)

RESOLUTION_STATUSES = {"resolved", "candidate_for_review", "unresolved"}
REVIEW_STATUSES = {"candidate", "reviewed", "rejected", "todo"}
TARGET_KINDS = {"production_person", "identity_candidate"}
PUBLISHED_STATES = {"production_ready", "preview_ready"}
HUAN_YI_CANDIDATE_ID = "candidate-identity-er1-1-2-193fc44098a05235f63fc215"


def _frozen_alias_document(root: Path) -> dict[str, Any] | None:
    """Use the preserved ER1 input witness for this frozen legacy overlay.

    SFH2R's reviewed alias repair is active for the new HDB2/SFH2R
    projections.  ER1's effective mention artifact is an older frozen
    projection and must remain reproducible from the alias bytes it was
    originally built with; this witness does not feed active retrieval.
    """
    try:
        try:
            from scripts import sfh2r_contract
        except ImportError:  # direct execution from scripts/
            import sfh2r_contract
        document = sfh2r_contract.pre_repair_alias_document()
    except (ImportError, OSError, ValueError, TypeError):
        document = None
    return dict(document) if isinstance(document, Mapping) else None


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


def _candidate_target(
    candidate: Mapping[str, Any],
    people_by_id: Mapping[str, Mapping[str, Any]],
    materialized_candidate_persons: Mapping[str, str] | None = None,
) -> dict[str, Any] | None:
    candidate_id = candidate.get("candidate_id")
    if isinstance(candidate_id, str) and materialized_candidate_persons:
        person_id = materialized_candidate_persons.get(candidate_id)
        if isinstance(person_id, str) and person_id in people_by_id:
            return {
                "target_kind": "production_person",
                "person_id": person_id,
                "canonical_name": str(people_by_id[person_id].get("canonical_name", candidate.get("preferred_name", ""))),
            }
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


def _materialized_candidate_persons(root: Path) -> dict[str, str]:
    """Return frozen candidate-to-Person assignments from expansion waves.

    Candidate artifacts intentionally remain identity-analysis data and may
    still say ``new_candidate`` after a wave is materialized.  The committed
    wave manifests are the authoritative bridge for the separate production
    navigation capability; without it ER1 would incorrectly treat a
    materialized identity as both a candidate and a production Person.
    """

    result: dict[str, str] = {}
    for relative in MATERIALIZED_PERSON_WAVE_PATHS:
        path = root / relative
        if not path.is_file():
            continue
        document = read_json(root, relative)
        for member in document.get("members", []):
            if not isinstance(member, Mapping):
                continue
            candidate_id = member.get("candidate_id")
            person_id = member.get("person_id")
            if not isinstance(candidate_id, str) or not isinstance(person_id, str):
                continue
            previous = result.get(candidate_id)
            if previous is not None and previous != person_id:
                raise ValueError(
                    f"candidate is assigned to multiple production Persons: {candidate_id}"
                )
            result[candidate_id] = person_id
    return result


def _identity_target_overrides(root: Path) -> list[Mapping[str, Any]]:
    path = root / IDENTITY_TARGETS_PATH
    if not path.is_file():
        return []
    document = read_json(root, IDENTITY_TARGETS_PATH)
    return [
        item
        for item in document.get("candidates", [])
        if isinstance(item, Mapping)
    ]


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
    for expansion_path in (EXPANSION_PATH, W3_EXPANSION_PATH, W4_EXPANSION_PATH):
        if not (root / expansion_path).is_file():
            continue
        expansion = read_json(root, expansion_path)
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
        return ""
    return sections.get((story_id, f"liu_annotation:{annotation_id}"), "")


def _local_context_key(mention: Mapping[str, Any]) -> tuple[str, str, str]:
    """Keep antecedents inside one Story section/annotation block only."""

    story_id = str(mention.get("entry_id") or mention.get("source_id") or "")
    section = str(mention.get("section", "main_text"))
    if section == "liu_annotation":
        metadata = mention.get("source_section_metadata", {})
        annotation_id = metadata.get("annotation_id") if isinstance(metadata, Mapping) else None
        if isinstance(annotation_id, str) and annotation_id:
            return story_id, section, annotation_id
        # An unowned Liu Mention must not inherit local context from an
        # arbitrary annotation block.  Build-time ownership resolution may
        # replace this with a canonical annotation ID; until then isolate it.
        return story_id, section, f"unresolved:{mention.get('mention_id', '')}"
    return story_id, section, "main_text"


def _with_effective_annotation_ownership(
    mention: Mapping[str, Any],
    sections: Mapping[tuple[str, str], str],
) -> Mapping[str, Any]:
    """Attach only safely derived Liu annotation ownership to a build copy."""

    if mention.get("section") != "liu_annotation":
        return mention
    story_id = str(mention.get("entry_id") or mention.get("source_id") or "")
    annotation_records = [
        {
            "id": key[1].split(":", 1)[1],
            "text": text,
        }
        for key, text in sections.items()
        if key[0] == story_id and key[1].startswith("liu_annotation:")
    ]
    annotation_id = effective_annotation_id(mention, annotation_records)
    valid_ids = {str(item["id"]) for item in annotation_records}
    if annotation_id is None or annotation_id not in valid_ids:
        return mention
    normalized = dict(mention)
    metadata = dict(mention.get("source_section_metadata", {})) if isinstance(mention.get("source_section_metadata"), Mapping) else {}
    metadata["annotation_id"] = annotation_id
    normalized["source_section_metadata"] = metadata
    if not (
        isinstance(mention.get("source_section_metadata"), Mapping)
        and isinstance(mention["source_section_metadata"].get("annotation_id"), str)
    ) and not (
        isinstance(mention.get("anchor"), Mapping)
        and isinstance(mention["anchor"].get("annotation_id"), str)
    ):
        normalized["annotation_ownership_basis"] = "canonical_annotation_match"
    return normalized


def _context(text: str, offset: int, surface: str, width: int = 42) -> tuple[str, str]:
    start = max(0, offset - width)
    end = min(len(text), offset + len(surface) + width)
    return text[start:offset], text[offset + len(surface):end]


def _semantic_prefix_start(text: str, offset: int) -> int | None:
    """Return the preceding Chinese character for a semantic span.

    Processed witnesses retain physical line endings.  A surname and a
    courtesy name can therefore be split as ``温\n太真`` even though the
    observed appellation is ``温太真``.  Allow exactly one physical line
    ending (including CRLF), but never cross a blank line or arbitrary
    whitespace.  This is a span-alignment helper, not a general whitespace
    normalizer or name recognizer.
    """

    if offset <= 0:
        return None
    candidate = offset - 1
    if text[candidate] in "\r\n":
        if text[candidate] == "\n" and candidate > 0 and text[candidate - 1] == "\r":
            candidate -= 1
        candidate -= 1
        if candidate < 0 or text[candidate] in "\r\n":
            return None
    if not re.match(r"[\u3400-\u9fff]", text[candidate]):
        return None
    return candidate


def _source_semantic_match_end(text: str, start: int, surface: str) -> int | None:
    """Match a semantic surface while tolerating one physical line ending.

    The returned offset is in the untouched source string, so callers can
    preserve the exact witness slice in provenance/display-span metadata.
    """

    if start < 0 or not surface or start >= len(text):
        return None
    cursor = start
    for index, character in enumerate(surface):
        if index:
            if text.startswith("\r\n", cursor):
                cursor += 2
            elif cursor < len(text) and text[cursor] in "\r\n":
                cursor += 1
            # A second line ending would be a paragraph/source gap, not an
            # internal break in one semantic appellation.
            if cursor < len(text) and text[cursor] in "\r\n":
                return None
        if cursor >= len(text) or text[cursor] != character:
            return None
        cursor += 1
    return cursor


def _full_surface(text: str, offset: int, surface: str) -> str | None:
    prefix_start = _semantic_prefix_start(text, offset)
    if prefix_start is None:
        return None
    prefix = text[prefix_start]
    complete = prefix + surface
    if _source_semantic_match_end(text, prefix_start, complete) is None:
        return None
    return complete


def _span_decision_id(story_id: str, section: str, offset: int, surface: str) -> str:
    """Return an opaque, stable ID for a curated contextual span rule."""

    payload = f"{story_id}\x1f{section}\x1f{offset}\x1f{surface}".encode("utf-8")
    return "span-decision-" + hashlib.sha256(payload).hexdigest()[:24]


def _derived_mention_id(
    story_id: str,
    section: str,
    offset: int,
    surface: str,
    target: Mapping[str, Any],
) -> str:
    """Return an opaque ID for a build-time-only contextual Mention."""

    payload = (
        f"{story_id}\x1f{section}\x1f{offset}\x1f{surface}\x1f{_target_key(target)}"
    ).encode("utf-8")
    return "er1-1-mention-" + hashlib.sha256(payload).hexdigest()[:24]


def _maximal_semantic_span(
    mention: Mapping[str, Any],
    result: Mapping[str, Any],
    *,
    text: str,
    alias_index: Mapping[str, list[Mapping[str, Any]]],
) -> dict[str, Any] | None:
    """Find a safe contiguous appellation extension for one canonical Mention.

    This deliberately considers only a one-character surname/title prefix and
    only when the complete surface is already present in the identity evidence
    index for the same resolved target.  It is not a general Chinese NER rule.
    """

    semantic_span = result.get("semantic_span")
    target = result.get("target")
    if (
        isinstance(semantic_span, Mapping)
        and isinstance(target, Mapping)
        and result.get("status") == "resolved"
        and isinstance(semantic_span.get("text"), str)
    ):
        offset = int(semantic_span.get("offset", -1))
        end = int(semantic_span.get("end_offset_exclusive", -1))
        text_value = str(semantic_span["text"])
        if offset >= 0 and end == offset + len(text_value) and text[offset:end] == text_value:
            return {
                "offset": offset,
                "end_offset_exclusive": end,
                "text": text_value,
                "basis": str(semantic_span.get("basis", "maximal_semantic_person_span")),
                "status": str(semantic_span.get("status", "safe")),
                "evidence_ids": sorted({
                    str(evidence_id)
                    for evidence_id in semantic_span.get("evidence_ids", [])
                    if isinstance(evidence_id, str)
                }),
            }

    surface = str(mention.get("surface", ""))
    offset = _mention_offset(mention)
    if not surface or not isinstance(target, Mapping) or result.get("status") != "resolved":
        return None
    target_key = _target_key(target)
    if offset <= 0 or offset + len(surface) > len(text):
        return None
    prefix_start = _semantic_prefix_start(text, offset)
    if prefix_start is None:
        return None
    complete = text[prefix_start] + surface
    associations = _association_candidates(alias_index, complete)
    same_target = [
        item
        for item in associations
        if _target_key(item.get("target", {})) == target_key
        and str(item.get("alias_type", "")) in {
            "surname_plus_courtesy_name",
            "office_title",
            "contextual_title",
            "posthumous_title",
            "honorific",
        }
    ]
    if not same_target:
        return None
    target_keys = {_target_key(item.get("target", {})) for item in associations}
    if len(target_keys) != 1:
        return None
    source_end = _source_semantic_match_end(text, prefix_start, complete)
    if source_end is None:
        return None
    return {
        "offset": prefix_start,
        "end_offset_exclusive": source_end,
        "text": text[prefix_start:source_end],
        "basis": "maximal_semantic_person_span",
        "status": "safe",
        "evidence_ids": sorted({
            str(evidence_id)
            for item in same_target
            for evidence_id in item.get("evidence_ids", [])
            if isinstance(evidence_id, str)
        }),
    }


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


SAFE_MAXIMAL_SURFACE_TYPES = {
    "personal_name",
    "courtesy_name",
    "surname_plus_courtesy_name",
    "established_appellation",
    "orthographic_variant",
}


def _longest_safe_semantic_resolution(
    mention: Mapping[str, Any],
    *,
    text: str,
    alias_index: Mapping[str, list[Mapping[str, Any]]],
) -> dict[str, Any] | None:
    """Resolve a short canonical alias only when a longer known appellation wins.

    The raw Mention files are historical segmentation artifacts and may carry
    ``桓子`` because that was the alias selected by the old materializer.  A
    longer, source-supported surface beginning at the same offset is a
    stronger identity signal.  This helper is deliberately limited to known
    semantic appellations; it never performs generic surname-prefix NER.
    """

    surface = str(mention.get("surface", ""))
    offset = _mention_offset(mention)
    if not surface or offset < 0 or offset + len(surface) > len(text):
        return None
    if text[offset : offset + len(surface)] != surface:
        return None

    possible: list[tuple[int, int, str, dict[str, Any], list[dict[str, Any]]]] = []
    for longer_surface in sorted(alias_index, key=lambda value: (-len(value), value)):
        if len(longer_surface) <= len(surface):
            continue
        # A canonical Mention may have been seeded on the courtesy-name
        # suffix of a complete surname+courtesy appellation (阮仲容 -> 仲容).
        # Permit only the one-character, source-contiguous surname prefix
        # when the complete known semantic surface ends at this Mention.  The
        # surface/evidence gate below still decides identity; this is not
        # blind left expansion.
        possible_starts = [offset]
        prefix_start = _semantic_prefix_start(text, offset)
        if prefix_start is not None:
            possible_starts.append(prefix_start)
        matched: tuple[int, int] | None = None
        for candidate_start in possible_starts:
            if candidate_start == offset and not longer_surface.startswith(surface):
                continue
            if candidate_start != offset and not longer_surface.endswith(surface):
                continue
            source_end = _source_semantic_match_end(text, candidate_start, longer_surface)
            if source_end is None or source_end < offset + len(surface):
                continue
            matched = (candidate_start, source_end)
            break
        if matched is None:
            continue
        start, source_end = matched
        associations = _association_candidates(alias_index, longer_surface)
        safe = [
            item
            for item in associations
            if str(item.get("alias_type", "")) in SAFE_MAXIMAL_SURFACE_TYPES
            and str(item.get("association_mode", "")) == "exact"
            and str(item.get("association_strength", "")) == "strong"
        ]
        target_keys = {_target_key(item.get("target", {})) for item in safe}
        if len(target_keys) != 1:
            continue
        target = _target_copy(safe[0]["target"])
        possible.append((len(longer_surface), start, longer_surface, target, safe))

    if not possible:
        return None
    possible.sort(key=lambda row: (-row[0], row[2], _target_key(row[3])))
    longest_length = possible[0][0]
    longest = [row for row in possible if row[0] == longest_length]
    if len({_target_key(row[3]) for row in longest}) != 1:
        # Two equally long recognized appellations with different identities
        # are still ambiguous.  Do not let longest-match become a new guess.
        return None
    _, start, longer_surface, target, associations = longest[0]
    source_end = _source_semantic_match_end(text, start, longer_surface)
    if source_end is None:
        return None
    evidence_ids = sorted({
        str(evidence_id)
        for item in associations
        for evidence_id in item.get("evidence_ids", [])
        if isinstance(evidence_id, str)
    })
    return {
        "status": "resolved",
        "target": target,
        "candidates": [target],
        "signals": [f"longest_safe_semantic_span:{longer_surface}"],
        "reasons": [],
        "review_status": "candidate",
        "decision_source": "automatic",
        "review_note": "",
        "resolution_evidence_ids": sorted({
            *evidence_ids,
            *[
                str(item)
                for item in mention.get("evidence", {}).get("evidence_ids", [])
                if isinstance(item, str)
            ],
        }),
        "resolution_mode": "exact",
        "resolution_method": "er1_1_2_longest_safe_semantic_span",
        "semantic_span": {
            "offset": start,
            "end_offset_exclusive": source_end,
            "text": text[start:source_end],
            "basis": "longest_safe_semantic_span",
            "status": "safe",
            "evidence_ids": evidence_ids,
        },
    }


def _make_review_id(mention_id: str) -> str:
    return "review-" + hashlib.sha256(mention_id.encode("utf-8")).hexdigest()[:24]


def _build_alias_index(
    root: Path,
    people: list[Mapping[str, Any]],
    aliases: list[Mapping[str, Any]],
    candidates: list[Mapping[str, Any]],
    candidate_evidence: Mapping[str, Mapping[str, Any]],
    identity_overrides: list[Mapping[str, Any]] | None = None,
    materialized_candidate_persons: Mapping[str, str] | None = None,
) -> tuple[dict[str, list[dict[str, Any]]], dict[str, dict[str, Any]], list[dict[str, Any]]]:
    people_by_id = {str(item.get("person_id")): item for item in people if isinstance(item.get("person_id"), str)}
    targets_by_key: dict[str, dict[str, Any]] = {}
    for person_id, person in sorted(people_by_id.items()):
        target = {"target_kind": "production_person", "person_id": person_id, "canonical_name": str(person.get("canonical_name", ""))}
        targets_by_key[_target_key(target)] = target
    all_candidates = [
        item
        for item in [*(candidates or []), *(identity_overrides or [])]
        if isinstance(item, Mapping)
    ]
    candidate_targets: dict[str, dict[str, Any]] = {}
    candidate_cues: dict[str, list[dict[str, str]]] = {}
    for candidate in all_candidates:
        if not isinstance(candidate, Mapping) or not isinstance(candidate.get("candidate_id"), str):
            continue
        target = _candidate_target(candidate, people_by_id, materialized_candidate_persons)
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
    for candidate in all_candidates:
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


def _lexical_alias_rules(root: Path) -> dict[str, Mapping[str, Any]]:
    """Load conservative homographic-alias guards.

    Alias registry membership is historical identity evidence, not a universal
    Mention instruction.  A rule can require a local syntax/context basis
    before an otherwise exact alias is allowed to resolve.
    """

    path = root / LEXICAL_ALIAS_RULES_PATH
    if not path.is_file():
        return {}
    document = read_json(root, LEXICAL_ALIAS_RULES_PATH)
    return {
        str(item["surface"]): item
        for item in document.get("rules", [])
        if isinstance(item, Mapping) and isinstance(item.get("surface"), str) and item.get("surface")
    }


def _homographic_alias_guard(
    mention: Mapping[str, Any],
    *,
    text: str,
    rule: Mapping[str, Any] | None,
) -> dict[str, Any] | None:
    """Return an unresolved result for a lexical alias without local basis."""

    if rule is None or str(mention.get("surface", "")) != str(rule.get("surface", "")):
        return None
    story_id = str(mention.get("entry_id") or mention.get("source_id") or "")
    allowed_stories = {str(item) for item in rule.get("allowed_story_ids", []) if isinstance(item, str)}
    patterns = [str(item) for item in rule.get("identity_context_patterns", []) if isinstance(item, str) and item]
    matched_pattern = next((pattern for pattern in patterns if re.search(pattern, text)), None)
    if story_id in allowed_stories and matched_pattern is not None:
        return None
    associations = rule.get("candidate_targets", [])
    candidates = [
        _target_copy(item)
        for item in associations
        if isinstance(item, Mapping) and item.get("target_kind") in TARGET_KINDS
    ]
    return {
        "status": "unresolved",
        "target": None,
        "candidates": candidates,
        "signals": ["homographic_alias_guard"],
        "reasons": ["homographic_lexical_alias_without_identity_basis"],
        "review_status": "candidate",
        "decision_source": "automatic",
        "review_note": str(rule.get("note", "")),
        "resolution_evidence_ids": sorted({
            str(item)
            for item in mention.get("evidence", {}).get("evidence_ids", [])
            if isinstance(item, str)
        }),
        "resolution_mode": "ambiguous",
        "resolution_method": "er1_homographic_alias_guard",
    }


def _audit_section_key(section: str, annotation_id: str | None = None) -> str:
    if section == "liu_annotation" and annotation_id:
        return f"liu_annotation:{annotation_id}"
    return section


def _audit_row_section_key(row: Mapping[str, Any]) -> str:
    section = str(row.get("section", "main_text"))
    if section == "liu_annotation":
        metadata = row.get("source_section_metadata", {})
        annotation_id = metadata.get("annotation_id") if isinstance(metadata, Mapping) else None
        return _audit_section_key(section, annotation_id if isinstance(annotation_id, str) else None)
    return section


def _audit_row_offset(row: Mapping[str, Any]) -> int:
    if isinstance(row.get("evidence"), Mapping) and isinstance(row["evidence"].get("section_offset"), int):
        return int(row["evidence"]["section_offset"])
    value = row.get("entry_relative_start")
    return int(value) if isinstance(value, int) else 0


def _compact_lexical_audit_resolution(row: Mapping[str, Any] | None) -> dict[str, Any] | None:
    if row is None:
        return None
    target = row.get("resolution_target")
    return {
        "mention_id": str(row.get("mention_id", "")),
        "resolution_status": str(row.get("resolution_status", "")),
        "resolution_target": _target_copy(target) if isinstance(target, Mapping) else None,
        "resolution_method": str(row.get("resolution_method", "")),
        "resolution_review_status": str(row.get("resolution_review_status", "")),
        "resolution_evidence_ids": sorted(
            str(item)
            for item in row.get("resolution_evidence_ids", [])
            if isinstance(item, str)
        ),
    }


def _lexical_collision_classification(
    text: str,
    offset: int,
    end: int,
    effective_row: Mapping[str, Any] | None,
    identity_target_person_id: str | None,
) -> tuple[str, str, str | None]:
    """Classify the exact 望之 span without changing the alias registry.

    The identity branch is intentionally limited to an explicit full
    appellation.  Standalone occurrences are recognized as lexical only when
    their local syntax has the ordinary verb/object-pronoun shape; otherwise
    they remain ambiguous for review.
    """

    preceding = text[max(0, offset - 1):offset]
    identity_context = text[max(0, offset - 18):min(len(text), end + 10)]
    if (
        preceding == "卞"
        or (effective_row and effective_row.get("surface") == "卞望之")
        or re.search(r"(?:卞壼|壼)字望之", identity_context)
    ):
        target = effective_row.get("resolution_target") if effective_row else None
        target_person_id = (
            str(target.get("person_id"))
            if isinstance(target, Mapping) and target.get("target_kind") == "production_person" and isinstance(target.get("person_id"), str)
            else identity_target_person_id
        )
        return "identity_name", "explicit 卞望之 full appellation; the substring is part of a person name", target_person_id

    local = text[max(0, offset - 4):min(len(text), end + 4)]
    # These are syntactic neighbors in the acquired corpus, not a global
    # title/name dictionary: verb or locative before 望之 and a following
    # predicate/report/complement after it.
    if re.search(r"(?:過|津|公|民|白|遠|逺)望之\s*(?:云|曰|如|去|峨)", local) or re.search(r"望之\s*(?:云|曰|如|去|峨)", local):
        return "lexical_verb_pronoun", "local syntax is verb + object pronoun, not a personal appellation", None
    return "ambiguous", "standalone 望之 is homographic; the local syntax does not establish identity", None


def _lexical_collision_audit(
    root: Path,
    *,
    sections: Mapping[tuple[str, str], str],
    effective_mentions: list[Mapping[str, Any]],
    identity_target_person_id: str | None,
) -> dict[str, Any]:
    """Audit every source occurrence of 望之 across the acquired corpus."""

    effective_rows: list[Mapping[str, Any]] = [
        row for row in effective_mentions if isinstance(row, Mapping)
    ]
    records: list[dict[str, Any]] = []
    for (story_id, section_key), text in sorted(sections.items(), key=lambda item: (item[0][0], item[0][1])):
        offset = 0
        while True:
            offset = text.find("望之", offset)
            if offset < 0:
                break
            end = offset + len("望之")
            overlapping = [
                row
                for row in effective_rows
                if str(row.get("entry_id") or row.get("source_id") or "") == story_id
                and _audit_row_section_key(row) == section_key
                and _audit_row_offset(row) <= offset
                and _audit_row_offset(row) + len(str(row.get("surface", ""))) >= end
            ]
            overlapping.sort(key=lambda row: (
                _audit_row_offset(row),
                len(str(row.get("surface", ""))),
                str(row.get("mention_id", "")),
            ))
            effective_row = overlapping[0] if overlapping else None
            classification, rationale, target_person_id = _lexical_collision_classification(
                text, offset, end, effective_row, identity_target_person_id
            )
            left_context, right_context = _context(text, offset, "望之", width=36)
            evidence_ids = set()
            if effective_row is not None:
                evidence_ids.update(
                    str(item)
                    for item in effective_row.get("resolution_evidence_ids", [])
                    if isinstance(item, str)
                )
                evidence = effective_row.get("evidence", {})
                if isinstance(evidence, Mapping):
                    evidence_ids.update(
                        str(item)
                        for item in evidence.get("evidence_ids", [])
                        if isinstance(item, str)
                    )
            records.append(
                {
                    "audit_record_id": "lexical-collision-" + hashlib.sha256(
                        f"{story_id}\x1f{section_key}\x1f{offset}\x1f望之".encode("utf-8")
                    ).hexdigest()[:24],
                    "story_id": story_id,
                    "section": "liu_annotation" if section_key.startswith("liu_annotation:") else section_key,
                    **(
                        {"annotation_id": section_key.split(":", 1)[1]}
                        if section_key.startswith("liu_annotation:")
                        else {}
                    ),
                    "surface": "望之",
                    "span": {"offset": offset, "end_offset_exclusive": end, "text": "望之"},
                    "left_context": left_context,
                    "right_context": right_context,
                    "current_resolution": _compact_lexical_audit_resolution(effective_row),
                    "classification": classification,
                    "target_person_id": target_person_id,
                    "evidence_ids": sorted(evidence_ids),
                    "rationale": rationale,
                }
            )
            offset = end
    records.sort(key=lambda item: (
        str(item["story_id"]),
        str(item["section"]),
        str(item.get("annotation_id", "")),
        int(item["span"]["offset"]),
        str(item["audit_record_id"]),
    ))
    return {
        "schema": 1,
        "stage": "er1-lexical-collision-audit",
        "scope": {
            "surface": "望之",
            "occurrence_count": len(records),
            "story_count": len({str(item["story_id"]) for item in records}),
            "sections": sorted({str(item["section"]) for item in records}),
        },
        "generated_from": [
            str(CORPUS_INDEX_PATH),
            str(LEXICAL_ALIAS_RULES_PATH),
            str(EFFECTIVE_PATH),
            "content/processed/shishuo/entries/",
        ],
        "policy": "A valid courtesy-name alias is not globally unique. Explicit 卞望之 remains identity evidence; standalone 望之 requires local syntax and otherwise remains unresolved or ambiguous.",
        "records": records,
    }


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
    prior_entities: list[Mapping[str, Any]],
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

    # A short one- or two-character reference may follow a complete
    # appellation in the same Story-local section.  This is intentionally
    # narrower than a global alias lookup: the prior record must itself carry
    # a complete semantic span, and the target's canonical name must end with
    # the short surface.  If multiple local entities fit, the caller receives
    # candidate_for_review rather than a guessed identity.
    # A short form may have a contextual registry association, but that
    # association is never sufficient on its own.  A compatible local
    # antecedent is the only reason it may resolve here.
    if len(surface) <= 2 and (
        not associations
        or all(str(item.get("association_mode", "")) != "exact" for item in associations)
    ):
        association_keys = {
            _target_key(item.get("target", {}))
            for item in associations
        }
        for prior in prior_entities:
            target = prior.get("target")
            if not isinstance(target, Mapping):
                continue
            prior_surface = str(prior.get("span_surface") or prior.get("surface") or "")
            canonical_name = str(target.get("canonical_name", ""))
            if (
                prior_surface
                and prior_surface != surface
                and len(prior_surface) > len(surface)
                and (prior_surface.endswith(surface) or canonical_name.endswith(surface))
            ):
                key = _target_key(target)
                if association_keys and key not in association_keys:
                    continue
                selected[key] = _target_copy(target)
                signals.append("story_local_short_form_coreference")

    return sorted(selected.values(), key=_target_sort_key), sorted(set(signals))


def resolve_mention(
    mention: Mapping[str, Any],
    *,
    text: str,
    alias_index: Mapping[str, list[Mapping[str, Any]]],
    targets_by_key: Mapping[str, Mapping[str, Any]],
    prior_targets: list[Mapping[str, Any]] = (),
    prior_entities: list[Mapping[str, Any]] = (),
    cues_by_target: Mapping[str, list[Mapping[str, str]]] | None = None,
    decision: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Resolve one canonical Mention into the ER1 effective target state."""

    mention_id = str(mention.get("mention_id", ""))
    if decision is not None:
        if decision.get("resolution_status") == "unresolved" and decision.get("target") is None:
            return {
                "status": "unresolved",
                "target": None,
                "candidates": [],
                "signals": ["human_reviewed_decision"],
                "reasons": ["human_reviewed_unresolved"],
                "review_status": "reviewed",
                "decision_source": "human_review",
                "review_note": str(decision.get("review_note", "")),
                "resolution_evidence_ids": sorted({
                    str(item)
                    for item in decision.get("evidence_ids", [])
                    if isinstance(item, str)
                }),
            }
        target = _validate_decision_target(decision, targets_by_key)
        return {
            "status": str(decision.get("resolution_status", "resolved")),
            "target": target,
            "candidates": [target] if str(decision.get("resolution_status", "resolved")) == "resolved" else [],
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

    # Explicit complete appellations take precedence over the shorter alias
    # recorded by the canonical Mention materializer.  This is the critical
    # ER1.1.2 guard for 桓子野: 桓子 is a valid 王遐 courtesy name, but it is
    # not allowed to win inside the longer 桓子野 span for 桓伊.
    longest_resolution = _longest_safe_semantic_resolution(
        mention,
        text=text,
        alias_index=alias_index,
    )
    if longest_resolution is not None:
        return longest_resolution

    local_targets, local_signals = _local_context_targets(
        mention,
        text,
        associations,
        alias_index,
        list(prior_targets),
        list(prior_entities),
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


def _effective_mention(
    mention: Mapping[str, Any],
    result: Mapping[str, Any],
    *,
    display_span: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
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
    if isinstance(display_span, Mapping):
        effective["display_span"] = {
            "offset": int(display_span["offset"]),
            "end_offset_exclusive": int(display_span["end_offset_exclusive"]),
            "text": str(display_span["text"]),
            "basis": str(display_span.get("basis", "maximal_semantic_person_span")),
            "status": str(display_span.get("status", "safe")),
            "evidence_ids": sorted({
                str(item)
                for item in display_span.get("evidence_ids", [])
                if isinstance(item, str)
            }),
        }
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
    if isinstance(result.get("resolution_method"), str) and result.get("resolution_method"):
        effective["resolution_method"] = str(result["resolution_method"])
    elif status == "resolved" and isinstance(target, Mapping) and target.get("target_kind") == "identity_candidate":
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
        "## ER1.1.2 prefix collision: 桓子野 / 桓伊",
        "",
        f"- `person-016` 王遐 retains the exact identity evidence `桓子`, but that shorter surface is not allowed to win inside the longer `桓子野` appellation.",
        f"- The curated non-production identity target `桓伊` (`{HUAN_YI_CANDIDATE_ID}`) is supported by the 05-fangzheng-055 Liu annotation and processed Jinshu evidence; it does not allocate a Person ID or create a PersonStory link.",
        "- The six canonical prefix occurrences in 05-fangzheng-055, 23-rendan-033, 23-rendan-042, 23-rendan-049, and 26-qingdi-020 use the maximal `桓子野` span and remain non-navigable identity mentions wherever projected.",
        "- In 05-fangzheng-055, the later `子野` is resolved only through the same-Story antecedent; `子野` is not a global exact alias.",
        "- The two `桓子` occurrences in the ancient 春秋 quotation in 05-fangzheng-035 are reviewed unresolved rather than assigned to 王遐.",
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


def _span_decisions(root: Path) -> list[Mapping[str, Any]]:
    if not (root / SPAN_DECISIONS_PATH).is_file():
        return []
    document = read_json(root, SPAN_DECISIONS_PATH)
    decisions = document.get("decisions", [])
    return [
        item
        for item in decisions
        if isinstance(item, Mapping)
    ]


def _validate_span_decision(
    decision: Mapping[str, Any],
    *,
    sections: Mapping[tuple[str, str], str],
    targets_by_key: Mapping[str, Mapping[str, Any]],
) -> tuple[str, str, int, int, str, dict[str, Any]]:
    story_id = str(decision.get("story_id", ""))
    section = str(decision.get("section", "main_text"))
    offset = decision.get("span_start")
    end = decision.get("span_end_exclusive")
    surface = decision.get("surface")
    if not story_id or section != "main_text" or not isinstance(offset, int) or not isinstance(end, int) or not isinstance(surface, str):
        raise ValueError(f"invalid ER1.1 span decision: {decision.get('decision_id')}")
    text = sections.get((story_id, section), "")
    if offset < 0 or end <= offset or end > len(text) or text[offset:end] != surface:
        raise ValueError(f"ER1.1 span decision does not match source text: {decision.get('decision_id')}")
    target = decision.get("target")
    if not isinstance(target, Mapping):
        raise ValueError(f"ER1.1 span decision lacks a target: {decision.get('decision_id')}")
    normalized = _target_copy(target)
    known = targets_by_key.get(_target_key(normalized))
    if known is None or known.get("canonical_name") != normalized.get("canonical_name"):
        raise ValueError(f"ER1.1 span decision target is unknown: {decision.get('decision_id')}")
    return story_id, section, offset, end, surface, _target_copy(known)


def _derived_contextual_mentions(
    root: Path,
    *,
    sections: Mapping[tuple[str, str], str],
    targets_by_key: Mapping[str, Mapping[str, Any]],
    canonical_mentions: list[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    """Project only explicitly seeded high-confidence local spans.

    These records are kept in a separate effective ``derived_mentions`` list;
    canonical Mention JSON is never rewritten.  A seed may declare a bounded
    short-form continuation (for example 庾太尉 → 亮), which is searched only
    in the same Story/section and never promoted to a global alias.
    """

    decisions = sorted(
        _span_decisions(root),
        key=lambda item: (
            str(item.get("story_id", "")),
            str(item.get("section", "")),
            int(item.get("span_start", 10**9)) if isinstance(item.get("span_start"), int) else 10**9,
            str(item.get("decision_id", "")),
        ),
    )
    canonical_ranges: dict[tuple[str, str], list[tuple[int, int]]] = defaultdict(list)
    canonical_semantic_spans: dict[tuple[str, str], list[tuple[int, int, str, str]]] = defaultdict(list)
    for mention in canonical_mentions:
        story_id = str(mention.get("entry_id") or mention.get("source_id") or "")
        section = str(mention.get("section", "main_text"))
        offset = _mention_offset(mention)
        surface = str(mention.get("surface", ""))
        if surface:
            canonical_ranges[(story_id, section)].append((offset, offset + len(surface)))
            span = mention.get("display_span")
            span_offset = span.get("offset") if isinstance(span, Mapping) else offset
            span_end = span.get("end_offset_exclusive") if isinstance(span, Mapping) else offset + len(surface)
            if isinstance(span_offset, int) and isinstance(span_end, int) and span_end > span_offset:
                target = mention.get("resolution_target")
                target_key = _target_key(target) if isinstance(target, Mapping) else ""
                canonical_semantic_spans[(story_id, section)].append(
                    (span_offset, span_end, target_key, str(mention.get("mention_id", "")))
                )

    derived: list[dict[str, Any]] = []
    seeded_short_forms: list[tuple[Mapping[str, Any], str, str, int, int, str, dict[str, Any], str]] = []
    for decision in decisions:
        story_id, section, offset, end, surface, target = _validate_span_decision(
            decision,
            sections=sections,
            targets_by_key=targets_by_key,
        )
        decision_id = str(decision.get("decision_id") or _span_decision_id(story_id, section, offset, surface))
        evidence_ids = sorted({
            str(item)
            for item in decision.get("evidence_ids", [])
            if isinstance(item, str)
        })
        existing_seed = next(
            (
                item
                for item in canonical_semantic_spans.get((story_id, section), [])
                if item[0] == offset
                and item[1] == end
                and item[2] == _target_key(target)
            ),
            None,
        )
        mention_id = existing_seed[3] if existing_seed else _derived_mention_id(story_id, section, offset, surface, target)
        record = {
            "mention_id": mention_id,
            "entry_id": story_id,
            "source_id": story_id,
            "source": "shishuo",
            "section": section,
            "surface": surface,
            "alias_type": str(decision.get("alias_type", "contextual_title")),
            "resolution_mode": str(decision.get("resolution_mode", "contextual")),
            "confidence": "high",
            "person_id": target.get("person_id") if target.get("target_kind") == "production_person" else None,
            "candidate_person_ids": [str(target["person_id"])] if target.get("target_kind") == "production_person" else [],
            "context_identity_hits": [str(target.get("canonical_name", ""))],
            "context": sections[(story_id, section)],
            "entry_relative_start": offset,
            "entry_relative_end_exclusive": end,
            "source_section_metadata": {},
            "evidence": {"section_offset": offset, "evidence_ids": evidence_ids},
            "anchor": {"text": surface, "section": section, "offset": offset},
            "resolution_status": "resolved",
            "resolution_target": target,
            "resolution_candidates": [target],
            "resolution_review_status": str(decision.get("review_status", "candidate")),
            "resolution_decision_source": "automatic",
            "resolution_evidence_ids": evidence_ids,
            "resolution_note": str(decision.get("review_note", "")),
            "resolution_method": "er1_1_contextual_span_seed",
            "assertion_status": str(decision.get("assertion_status", "attested")),
            "review_status": str(decision.get("review_status", "candidate")),
            "derived_only": True,
            "span_decision_id": decision_id,
            "display_span": {
                "offset": offset,
                "end_offset_exclusive": end,
                "text": surface,
                "basis": "er1_1_contextual_span_seed",
                "status": "safe",
                "evidence_ids": evidence_ids,
            },
        }
        if existing_seed is None:
            derived.append(record)
        for short_surface in decision.get("coreference_surfaces", []):
            if isinstance(short_surface, str) and short_surface:
                seeded_short_forms.append((decision, story_id, section, offset, end, short_surface, target, mention_id))

    existing_ranges = {
        key: list(ranges)
        for key, ranges in canonical_ranges.items()
    }
    for record in derived:
        key = (str(record["entry_id"]), str(record["section"]))
        existing_ranges.setdefault(key, []).append((int(record["display_span"]["offset"]), int(record["display_span"]["end_offset_exclusive"])))

    for decision, story_id, section, seed_offset, seed_end, short_surface, target, antecedent_id in seeded_short_forms:
        text = sections.get((story_id, section), "")
        cursor = seed_end
        while cursor < len(text):
            offset = text.find(short_surface, cursor)
            if offset < 0:
                break
            end = offset + len(short_surface)
            cursor = end
            if any(start < end and offset < finish for start, finish in existing_ranges.get((story_id, section), [])):
                continue
            mention_id = _derived_mention_id(story_id, section, offset, short_surface, target)
            evidence_ids = sorted({
                str(item)
                for item in decision.get("evidence_ids", [])
                if isinstance(item, str)
            })
            record = {
                "mention_id": mention_id,
                "entry_id": story_id,
                "source_id": story_id,
                "source": "shishuo",
                "section": section,
                "surface": short_surface,
                "alias_type": "textual_shorthand",
                "resolution_mode": "contextual",
                "confidence": "high",
                "person_id": target.get("person_id") if target.get("target_kind") == "production_person" else None,
                "candidate_person_ids": [str(target["person_id"])] if target.get("target_kind") == "production_person" else [],
                "context_identity_hits": [str(target.get("canonical_name", ""))],
                "context": text,
                "entry_relative_start": offset,
                "entry_relative_end_exclusive": end,
                "source_section_metadata": {},
                "evidence": {"section_offset": offset, "evidence_ids": evidence_ids},
                "anchor": {"text": short_surface, "section": section, "offset": offset},
                "resolution_status": "resolved",
                "resolution_target": target,
                "resolution_candidates": [target],
                "resolution_review_status": str(decision.get("review_status", "candidate")),
                "resolution_decision_source": "automatic",
                "resolution_evidence_ids": evidence_ids,
                "resolution_note": "同一故事中完整称谓之后的保守短称承接。",
                "resolution_method": "er1_1_story_local_coreference",
                "assertion_status": "attested",
                "review_status": str(decision.get("review_status", "candidate")),
                "derived_only": True,
                "span_decision_id": str(decision.get("decision_id") or _span_decision_id(story_id, section, seed_offset, str(decision.get("surface", "")))),
                "coreference_antecedent_mention_id": antecedent_id,
                "display_span": {
                    "offset": offset,
                    "end_offset_exclusive": end,
                    "text": short_surface,
                    "basis": "story_local_coreference",
                    "status": "safe",
                    "evidence_ids": evidence_ids,
                },
            }
            derived.append(record)
            existing_ranges.setdefault((story_id, section), []).append((offset, end))

    return sorted(
        derived,
        key=lambda item: (
            str(item.get("entry_id", "")),
            str(item.get("section", "")),
            int(item.get("entry_relative_start", 10**9)),
            str(item.get("mention_id", "")),
        ),
    )


def _span_audit_document(
    effective_mentions: list[Mapping[str, Any]],
    derived_mentions: list[Mapping[str, Any]],
    published_ids: set[str],
) -> dict[str, Any]:
    records: list[dict[str, Any]] = []
    for mention in effective_mentions:
        story_id = str(mention.get("entry_id") or mention.get("source_id") or "")
        if story_id not in published_ids:
            continue
        span = mention.get("display_span")
        surface = str(mention.get("surface", ""))
        if not isinstance(span, Mapping) or str(span.get("text", "")) == surface:
            continue
        records.append({
            "story_id": story_id,
            "section": str(mention.get("section", "main_text")),
            "mention_id": str(mention.get("mention_id", "")),
            "current_surface": surface,
            "proposed_surface": str(span.get("text", "")),
            "offset": int(span.get("offset", 0)),
            "end_offset_exclusive": int(span.get("end_offset_exclusive", 0)),
            "identity": mention.get("resolution_target"),
            "status": "auto_fixed",
            "basis": str(span.get("basis", "maximal_semantic_person_span")),
            "evidence_ids": list(span.get("evidence_ids", [])),
        })
    for mention in derived_mentions:
        records.append({
            "story_id": str(mention.get("entry_id", "")),
            "section": str(mention.get("section", "main_text")),
            "mention_id": str(mention.get("mention_id", "")),
            "current_surface": None,
            "proposed_surface": str(mention.get("surface", "")),
            "offset": int(mention.get("entry_relative_start", 0)),
            "end_offset_exclusive": int(mention.get("entry_relative_end_exclusive", 0)),
            "identity": mention.get("resolution_target"),
            "status": "auto_fixed",
            "basis": str(mention.get("resolution_method", "er1_1_contextual_span_seed")),
            "evidence_ids": list(mention.get("resolution_evidence_ids", [])),
        })
    records.sort(key=lambda item: (item["story_id"], item["section"], item["offset"], item["mention_id"]))
    audited_story_ids = {
        str(item.get("entry_id") or item.get("source_id") or "")
        for item in effective_mentions
        if str(item.get("entry_id") or item.get("source_id") or "") in published_ids
    }
    return {
        "schema": 1,
        "stage": "er1-1-person-span-audit",
        "published_story_count": len(published_ids),
        "audited_story_count": len(audited_story_ids),
        "auto_fixed_count": len(records),
        "review_required_count": 0,
        "records": records,
    }


def build(root: Path) -> dict[str, Any]:
    people = read_json(root, PEOPLE_PATH).get("people", [])
    aliases_document = _frozen_alias_document(root) or read_json(root, ALIASES_PATH)
    aliases = aliases_document.get("aliases", [])
    mentions = read_json(root, MENTIONS_PATH).get("mentions", [])
    candidate_document = read_json(root, IDENTITY_CANDIDATES_PATH)
    candidates = candidate_document.get("candidates", [])
    identity_overrides = _identity_target_overrides(root)
    candidate_evidence = {
        str(item.get("id")): item
        for item in candidate_document.get("evidence", [])
        if isinstance(item, Mapping) and isinstance(item.get("id"), str)
    }
    materialized_candidate_persons = _materialized_candidate_persons(root)
    alias_index, targets_by_key, candidate_metadata = _build_alias_index(
        root,
        people,
        aliases,
        candidates,
        candidate_evidence,
        identity_overrides,
        materialized_candidate_persons,
    )
    decision_map = _decision_map(root)
    lexical_alias_rules = _lexical_alias_rules(root)
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
        context_mention = _with_effective_annotation_ownership(mention, sections)
        story_id = str(context_mention.get("entry_id") or context_mention.get("source_id") or "")
        section = str(context_mention.get("section", "main_text"))
        text = _section_text(sections, context_mention)
        prior = local_state[_local_context_key(context_mention)]
        decision = decision_map.get(str(context_mention.get("mention_id")))
        automatic_result = resolve_mention(
            context_mention,
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
                if item.get("surface") == context_mention.get("surface")
                and isinstance(item.get("target"), Mapping)
            ],
            prior_entities=prior,
            cues_by_target=cues_by_target,
            decision=None,
        )
        homographic_guard = _homographic_alias_guard(
            context_mention,
            text=text,
            rule=lexical_alias_rules.get(str(context_mention.get("surface", ""))),
        )
        if homographic_guard is not None:
            automatic_result = homographic_guard
        result = automatic_result
        if decision is not None:
            reviewed_result = resolve_mention(
                context_mention,
                text=text,
                alias_index=alias_index,
                targets_by_key=targets_by_key,
                prior_targets=[
                    item["target"]
                    for item in prior
                    if item.get("surface") == context_mention.get("surface")
                    and isinstance(item.get("target"), Mapping)
                ],
                prior_entities=prior,
                cues_by_target=cues_by_target,
                decision=decision,
            )
            result = apply_reviewed_decision(automatic_result, reviewed_result)
        display_span = _maximal_semantic_span(
            context_mention,
            result,
            text=text,
            alias_index=alias_index,
        )
        effective = _effective_mention(context_mention, result, display_span=display_span)
        effective_mentions.append(effective)
        if result.get("status") == "resolved" and isinstance(result.get("target"), Mapping):
            local_state[_local_context_key(context_mention)].append({
                "offset": _mention_offset(context_mention),
                "surface": context_mention.get("surface"),
                "span_surface": display_span.get("text") if isinstance(display_span, Mapping) else context_mention.get("surface"),
                "target": result["target"],
                "decision_source": result.get("decision_source"),
                "mention_id": context_mention.get("mention_id"),
            })
        if story_id in published_ids and (
            result.get("status") != "resolved"
            or result.get("decision_source") == "human_review"
            or (isinstance(result.get("target"), Mapping) and result["target"].get("target_kind") == "identity_candidate")
        ):
            review_records.append(
                _review_record(
                    context_mention,
                    result,
                    text=text,
                    associations=_association_candidates(alias_index, str(context_mention.get("surface", ""))),
                )
            )

    effective_mentions.sort(key=lambda item: str(item.get("mention_id", "")))
    derived_mentions = _derived_contextual_mentions(
        root,
        sections=sections,
        targets_by_key=targets_by_key,
        canonical_mentions=effective_mentions,
    )
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
        "generated_from": [
            str(MENTIONS_PATH),
            str(ALIASES_PATH),
            str(IDENTITY_CANDIDATES_PATH),
            str(IDENTITY_TARGETS_PATH),
            str(DECISIONS_PATH),
            str(SPAN_DECISIONS_PATH),
            str(LEXICAL_ALIAS_RULES_PATH),
            *[str(path) for path in MATERIALIZED_PERSON_WAVE_PATHS if (root / path).is_file()],
        ],
        "source_mentions_sha256": sha256_file(root / MENTIONS_PATH),
        "decision_sha256": sha256_file(root / DECISIONS_PATH),
        "mention_count": len(effective_mentions),
        "derived_mention_count": len(derived_mentions),
        "counts": counts,
        "mentions": effective_mentions,
        "derived_mentions": derived_mentions,
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
    lexical_collision_audit = _lexical_collision_audit(
        root,
        sections=sections,
        effective_mentions=effective_mentions,
        identity_target_person_id=next(
            (
                str(item.get("person_id"))
                for item in lexical_alias_rules.get("望之", {}).get("candidate_targets", [])
                if isinstance(item, Mapping)
                and item.get("target_kind") == "production_person"
                and isinstance(item.get("person_id"), str)
            ),
            None,
        ),
    )
    write_json(root, LEXICAL_COLLISION_AUDIT_PATH, lexical_collision_audit)
    span_audit = _span_audit_document(effective_mentions, derived_mentions, published_ids)
    write_json(root, SPAN_AUDIT_PATH, span_audit)
    span_lines = [
        "# Person span audit",
        "",
        "ER1.1 keeps canonical Mention anchors immutable. This report lists the build-time span/coreference projection used for reader segmentation; derived records are not canonical Mentions or new Persons.",
        "",
        f"- published Stories audited: {span_audit['audited_story_count']} / {span_audit['published_story_count']}",
        f"- high-confidence repaired/derived spans: {span_audit['auto_fixed_count']}",
        f"- review-required partial-span cases: {span_audit['review_required_count']}",
        "",
    ]
    for item in span_audit["records"]:
        identity = item.get("identity") or {}
        proposed_surface = str(item["proposed_surface"])
        proposed_surface = proposed_surface.replace("\r\n", "` + physical source newline + `").replace("\n", "` + physical source newline + `")
        span_lines.append(
            f"- `{item['story_id']}` · `{item['section']}` · `{proposed_surface}` · "
            f"{identity.get('canonical_name', '未定')} · `{item['basis']}` · {item['status']}"
        )
    (root / SPAN_REPORT_PATH).parent.mkdir(parents=True, exist_ok=True)
    (root / SPAN_REPORT_PATH).write_text("\n".join(span_lines) + "\n", encoding="utf-8")
    (root / REPORT_PATH).parent.mkdir(parents=True, exist_ok=True)
    (root / REPORT_PATH).write_text(report, encoding="utf-8")
    return effective_document


def load_effective_mentions(root: Path) -> list[dict[str, Any]]:
    path = root / EFFECTIVE_PATH
    if path.is_file():
        document = read_json(root, EFFECTIVE_PATH)
        mentions = document.get("mentions")
        if isinstance(mentions, list):
            combined = [dict(item) for item in mentions if isinstance(item, Mapping)]
            derived = document.get("derived_mentions", [])
            if isinstance(derived, list):
                combined.extend(dict(item) for item in derived if isinstance(item, Mapping))
            return sorted(
                combined,
                key=lambda item: (
                    str(item.get("entry_id") or item.get("source_id") or ""),
                    str(item.get("section", "")),
                    _mention_offset(item),
                    str(item.get("mention_id", "")),
                ),
            )
    return [dict(item) for item in read_json(root, MENTIONS_PATH).get("mentions", []) if isinstance(item, Mapping)]
