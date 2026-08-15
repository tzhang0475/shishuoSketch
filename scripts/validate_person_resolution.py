#!/usr/bin/env python3
"""Validate ER1's effective contextual Person-resolution layer.

This validator treats the canonical Mention file as immutable segmentation and
checks that the ER1 projection only changes resolution semantics.  It also
checks that a reviewed decision cannot be lost when the automatic resolver is
rebuilt.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

from jsonschema import Draft202012Validator

try:
    from .person_resolution import (
        COLLISIONS_PATH,
        DECISIONS_PATH,
        EFFECTIVE_PATH,
        IDENTITY_CANDIDATES_PATH,
        IDENTITY_TARGETS_PATH,
        HUAN_YI_CANDIDATE_ID,
        QUEUE_PATH,
        SPAN_AUDIT_PATH,
        SPAN_DECISIONS_PATH,
        LEXICAL_ALIAS_RULES_PATH,
        _published_story_ids,
        _load_sections,
        _target_key,
        read_json,
    )
except ImportError:  # direct execution
    from person_resolution import (
        COLLISIONS_PATH,
        DECISIONS_PATH,
        EFFECTIVE_PATH,
        IDENTITY_CANDIDATES_PATH,
        IDENTITY_TARGETS_PATH,
        HUAN_YI_CANDIDATE_ID,
        QUEUE_PATH,
        SPAN_AUDIT_PATH,
        SPAN_DECISIONS_PATH,
        LEXICAL_ALIAS_RULES_PATH,
        _published_story_ids,
        _load_sections,
        _target_key,
        read_json,
    )


ROOT = Path(__file__).resolve().parents[1]
PEOPLE_PATH = Path("data/people.json")
ALIASES_PATH = Path("data/aliases.json")
MENTIONS_PATH = Path("data/mentions/shishuo.json")
CANDIDATES_PATH = Path("data/derived/person-identity-candidates.json")
IDENTITY_TARGETS_SCHEMA_PATH = Path("schema/person-resolution-identity-candidates.schema.json")
EVIDENCE_PATH = Path("data/evidence/wp1-evidence.json")
CORPUS_PATH = Path("data/shishuo-corpus-index.json")
DECISION_SCHEMA_PATH = Path("schema/person-resolution-decision.schema.json")
EFFECTIVE_SCHEMA_PATH = Path("schema/person-resolution-effective.schema.json")
QUEUE_SCHEMA_PATH = Path("schema/person-resolution-review-queue.schema.json")
COLLISION_SCHEMA_PATH = Path("schema/person-alias-collisions.schema.json")
SPAN_DECISION_SCHEMA_PATH = Path("schema/person-resolution-span-decision.schema.json")
SPAN_AUDIT_SCHEMA_PATH = Path("schema/person-resolution-span-audit.schema.json")
LEXICAL_ALIAS_RULES_SCHEMA_PATH = Path("schema/person-resolution-lexical-alias-rules.schema.json")
SC1_PATH = Path("data/derived/sc1-site.json")

RESOLUTION_FIELDS = {
    "person_id",
    "candidate_person_ids",
    "confidence",
    "resolution_mode",
    "resolution_method",
    "resolution_status",
    "resolution_target",
    "resolution_candidates",
    "resolution_review_status",
    "resolution_decision_source",
    "resolution_evidence_ids",
    "resolution_note",
}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _schema_errors(root: Path, schema_path: Path, value: Any, label: str) -> list[str]:
    try:
        schema = read_json(root, schema_path)
        Draft202012Validator.check_schema(schema)
        return [f"{label}: {error.message}" for error in Draft202012Validator(schema).iter_errors(value)]
    except Exception as exc:  # schema errors must be reported, not hidden
        return [f"{label} schema validation failed: {exc}"]


def _target_valid(
    target: Any,
    *,
    people_by_id: Mapping[str, Mapping[str, Any]],
    candidates_by_id: Mapping[str, Mapping[str, Any]],
    label: str,
) -> list[str]:
    errors: list[str] = []
    if target is None:
        return errors
    if not isinstance(target, Mapping):
        return [f"{label} is not an object"]
    kind = target.get("target_kind")
    name = target.get("canonical_name")
    if kind == "production_person":
        person_id = target.get("person_id")
        person = people_by_id.get(str(person_id))
        if person is None:
            errors.append(f"{label} references unknown production Person: {person_id!r}")
        elif name != person.get("canonical_name"):
            errors.append(f"{label} canonical_name disagrees with production Person: {person_id}")
        if "candidate_id" in target:
            errors.append(f"{label} production target carries candidate_id")
    elif kind == "identity_candidate":
        candidate_id = target.get("candidate_id")
        candidate = candidates_by_id.get(str(candidate_id))
        if candidate is None:
            errors.append(f"{label} references unknown identity candidate: {candidate_id!r}")
        elif name != candidate.get("preferred_name"):
            errors.append(f"{label} canonical_name disagrees with identity candidate: {candidate_id}")
        elif candidate.get("status") == "already_materialized":
            errors.append(f"{label} uses an already-materialized candidate as a non-production target: {candidate_id}")
        if "person_id" in target:
            errors.append(f"{label} identity-candidate target carries person_id")
    else:
        errors.append(f"{label} has invalid target_kind: {kind!r}")
    return errors


def validate(root: Path = ROOT) -> list[str]:
    errors: list[str] = []
    try:
        people_document = read_json(root, PEOPLE_PATH)
        aliases_document = read_json(root, ALIASES_PATH)
        raw_document = read_json(root, MENTIONS_PATH)
        candidates_document = read_json(root, CANDIDATES_PATH)
        evidence_document = read_json(root, EVIDENCE_PATH)
        corpus_document = read_json(root, CORPUS_PATH)
        decisions_document = read_json(root, DECISIONS_PATH)
        identity_targets_document = read_json(root, IDENTITY_TARGETS_PATH)
        effective = read_json(root, EFFECTIVE_PATH)
        queue = read_json(root, QUEUE_PATH)
        collisions = read_json(root, COLLISIONS_PATH)
        span_decisions_document = read_json(root, SPAN_DECISIONS_PATH)
        span_audit = read_json(root, SPAN_AUDIT_PATH)
        lexical_alias_rules = read_json(root, LEXICAL_ALIAS_RULES_PATH)
    except (OSError, ValueError, KeyError) as exc:
        return [f"ER1 cannot read required artifact: {exc}"]

    for number, decision in enumerate(decisions_document.get("decisions", [])):
        errors.extend(_schema_errors(root, DECISION_SCHEMA_PATH, decision, f"ER1 decision {number}"))
    errors.extend(_schema_errors(root, IDENTITY_TARGETS_SCHEMA_PATH, identity_targets_document, "ER1.1.2 identity targets"))
    # The span schema describes the committed decision document (including
    # its schema/stage envelope), not an individual decision row.
    errors.extend(_schema_errors(root, SPAN_DECISION_SCHEMA_PATH, span_decisions_document, "ER1.1 span decisions"))
    errors.extend(_schema_errors(root, SPAN_AUDIT_SCHEMA_PATH, span_audit, "ER1.1 span audit"))
    errors.extend(_schema_errors(root, LEXICAL_ALIAS_RULES_SCHEMA_PATH, lexical_alias_rules, "ER1 homographic alias rules"))
    errors.extend(_schema_errors(root, EFFECTIVE_SCHEMA_PATH, effective, "ER1 effective resolution"))
    errors.extend(_schema_errors(root, QUEUE_SCHEMA_PATH, queue, "ER1 review queue"))
    errors.extend(_schema_errors(root, COLLISION_SCHEMA_PATH, collisions, "ER1 alias collisions"))

    people = [item for item in people_document.get("people", []) if isinstance(item, Mapping)]
    people_by_id = {str(item.get("person_id")): item for item in people if isinstance(item.get("person_id"), str)}
    aliases = [item for item in aliases_document.get("aliases", []) if isinstance(item, Mapping)]
    candidate_rows = [item for item in candidates_document.get("candidates", []) if isinstance(item, Mapping)]
    candidates_by_id = {str(item.get("candidate_id")): item for item in candidate_rows if isinstance(item.get("candidate_id"), str)}
    identity_target_rows = [
        item
        for item in identity_targets_document.get("candidates", [])
        if isinstance(item, Mapping)
    ]
    for candidate in identity_target_rows:
        candidate_id = candidate.get("candidate_id")
        if isinstance(candidate_id, str):
            if candidate_id in candidates_by_id:
                errors.append(f"ER1.1.2 identity target duplicates a P3A.1 candidate ID: {candidate_id}")
            candidates_by_id[candidate_id] = candidate
    huan_yi = candidates_by_id.get(HUAN_YI_CANDIDATE_ID)
    if not isinstance(huan_yi, Mapping) or huan_yi.get("preferred_name") != "桓伊":
        errors.append("ER1.1.2 missing curated 桓伊 identity target")
    else:
        surface_map = {
            str(item.get("surface")): item
            for item in huan_yi.get("surfaces", [])
            if isinstance(item, Mapping)
        }
        if surface_map.get("桓子野", {}).get("association_mode") != "exact":
            errors.append("ER1.1.2 桓子野 is not a safe exact semantic span")
        if surface_map.get("子野", {}).get("association_mode") == "exact":
            errors.append("ER1.1.2 子野 was promoted to a global exact alias")
    evidence_ids = {
        str(item.get("id"))
        for item in [*candidates_document.get("evidence", []), *evidence_document.get("records", [])]
        if isinstance(item, Mapping) and isinstance(item.get("id"), str)
    }
    try:
        sc1_document = read_json(root, SC1_PATH)
    except (OSError, ValueError):
        sc1_document = {}
    evidence_ids.update(
        str(item.get("id"))
        for item in sc1_document.get("evidence", [])
        if isinstance(item, Mapping) and isinstance(item.get("id"), str)
    )
    overlay_evidence_ids = {
        str(evidence_id)
        for candidate in identity_target_rows
        for evidence_id in [
            *candidate.get("identity_evidence_ids", []),
            *candidate.get("evidence_ids", []),
            *[
                item
                for surface in candidate.get("surfaces", [])
                if isinstance(surface, Mapping)
                for item in surface.get("evidence_ids", [])
            ],
        ]
        if isinstance(evidence_id, str)
    }
    missing_overlay_evidence = sorted(overlay_evidence_ids - evidence_ids)
    errors.extend(
        f"ER1.1.2 identity target Evidence does not resolve: {evidence_id}"
        for evidence_id in missing_overlay_evidence
    )
    raw_mentions = [item for item in raw_document.get("mentions", []) if isinstance(item, Mapping)]
    raw_by_id = {str(item.get("mention_id")): item for item in raw_mentions if isinstance(item.get("mention_id"), str)}
    if not any(
        alias.get("surface") == "桓子"
        and "person-016" in alias.get("person_ids", [])
        and alias.get("resolution_mode") == "exact"
        for alias in aliases
    ):
        errors.append("ER1.1.2 removed the valid 王遐/桓子 exact identity evidence")
    story_ids = {
        str(item.get("id"))
        for item in corpus_document.get("entries", [])
        if isinstance(item, Mapping) and isinstance(item.get("id"), str)
    }

    if effective.get("mention_count") != len(effective.get("mentions", [])):
        errors.append("ER1 effective mention_count does not match mentions length")
    if effective.get("source_mentions_sha256") != sha256_file(root / MENTIONS_PATH):
        errors.append("ER1 effective projection is stale relative to canonical Mention data")
    if effective.get("decision_sha256") != sha256_file(root / DECISIONS_PATH):
        errors.append("ER1 effective projection is stale relative to human decisions")
    effective_rows = [item for item in effective.get("mentions", []) if isinstance(item, Mapping)]
    effective_by_id: dict[str, Mapping[str, Any]] = {}
    for row in effective_rows:
        mention_id = row.get("mention_id")
        if not isinstance(mention_id, str) or mention_id in effective_by_id:
            errors.append(f"ER1 duplicate/invalid effective Mention ID: {mention_id!r}")
            continue
        effective_by_id[mention_id] = row
        raw = raw_by_id.get(mention_id)
        if raw is None:
            errors.append(f"ER1 effective Mention is not canonical: {mention_id}")
            continue
        for field in ("entry_id", "section", "surface", "alias_id", "alias_type"):
            if row.get(field) != raw.get(field):
                errors.append(f"ER1 changed immutable Mention field {field}: {mention_id}")
        raw_anchor = raw.get("evidence", {}) if isinstance(raw.get("evidence"), Mapping) else {}
        row_anchor = row.get("evidence", {}) if isinstance(row.get("evidence"), Mapping) else {}
        if row_anchor.get("section_offset") != raw_anchor.get("section_offset"):
            errors.append(f"ER1 changed immutable Mention anchor: {mention_id}")
        status = row.get("resolution_status")
        target = row.get("resolution_target")
        candidates = row.get("resolution_candidates", [])
        if status not in {"resolved", "candidate_for_review", "unresolved"}:
            errors.append(f"ER1 invalid resolution status: {mention_id}")
        if status == "unresolved" and target is not None:
            errors.append(f"ER1 unresolved Mention has a target: {mention_id}")
        if status == "candidate_for_review" and not isinstance(candidates, list):
            errors.append(f"ER1 review Mention candidates are not a list: {mention_id}")
        if status == "candidate_for_review" and len(candidates) < 1:
            errors.append(f"ER1 candidate_for_review lacks a concrete identity candidate: {mention_id}")
        errors.extend(_target_valid(target, people_by_id=people_by_id, candidates_by_id=candidates_by_id, label=f"ER1 target {mention_id}"))
        for number, candidate in enumerate(candidates):
            errors.extend(_target_valid(candidate, people_by_id=people_by_id, candidates_by_id=candidates_by_id, label=f"ER1 candidate {mention_id}[{number}]"))
        for evidence_id in row.get("resolution_evidence_ids", []):
            if evidence_id not in evidence_ids:
                errors.append(f"ER1 resolution Evidence does not resolve: {mention_id}/{evidence_id}")
        if row.get("resolution_decision_source") == "human_review" and row.get("resolution_review_status") != "reviewed":
            errors.append(f"ER1 human resolution is not reviewed: {mention_id}")

    if set(effective_by_id) != set(raw_by_id):
        errors.append("ER1 effective Mention IDs do not exactly cover canonical Mentions")

    derived_rows = [item for item in effective.get("derived_mentions", []) if isinstance(item, Mapping)]
    if effective.get("derived_mention_count") != len(derived_rows):
        errors.append("ER1 derived_mention_count does not match derived_mentions length")
    derived_ids: set[str] = set()
    sections = _load_sections(root)
    for row in derived_rows:
        mention_id = row.get("mention_id")
        if not isinstance(mention_id, str) or mention_id in derived_ids or mention_id in raw_by_id:
            errors.append(f"ER1.1 duplicate/invalid derived Mention ID: {mention_id!r}")
            continue
        derived_ids.add(mention_id)
        story_id = str(row.get("entry_id", ""))
        section = str(row.get("section", ""))
        if story_id not in story_ids:
            errors.append(f"ER1.1 derived Mention references unknown Story: {mention_id}")
        if row.get("derived_only") is not True:
            errors.append(f"ER1.1 derived Mention is not marked derived_only: {mention_id}")
        errors.extend(_target_valid(row.get("resolution_target"), people_by_id=people_by_id, candidates_by_id=candidates_by_id, label=f"ER1.1 target {mention_id}"))
        span = row.get("display_span")
        if not isinstance(span, Mapping):
            errors.append(f"ER1.1 derived Mention lacks display_span: {mention_id}")
            continue
        offset = span.get("offset")
        end = span.get("end_offset_exclusive")
        text = span.get("text")
        canonical = sections.get((story_id, section), "")
        if not isinstance(offset, int) or not isinstance(end, int) or not isinstance(text, str) or end <= offset or canonical[offset:end] != text:
            errors.append(f"ER1.1 derived Mention span does not round-trip: {mention_id}")
        for evidence_id in row.get("resolution_evidence_ids", []):
            if evidence_id not in evidence_ids:
                errors.append(f"ER1.1 derived Mention Evidence does not resolve: {mention_id}/{evidence_id}")

    span_decisions = [item for item in span_decisions_document.get("decisions", []) if isinstance(item, Mapping)]
    decision_ids: set[str] = set()
    for decision in span_decisions:
        decision_id = decision.get("decision_id")
        if not isinstance(decision_id, str) or decision_id in decision_ids:
            errors.append(f"ER1.1 duplicate/invalid span decision ID: {decision_id!r}")
        else:
            decision_ids.add(decision_id)
        story_id = str(decision.get("story_id", ""))
        section = str(decision.get("section", ""))
        offset = decision.get("span_start")
        end = decision.get("span_end_exclusive")
        surface = decision.get("surface")
        canonical = sections.get((story_id, section), "")
        if not isinstance(offset, int) or not isinstance(end, int) or not isinstance(surface, str) or canonical[offset:end] != surface:
            errors.append(f"ER1.1 span decision does not match canonical text: {decision_id}")
        errors.extend(_target_valid(decision.get("target"), people_by_id=people_by_id, candidates_by_id=candidates_by_id, label=f"ER1.1 decision {decision_id}"))
        for evidence_id in decision.get("evidence_ids", []):
            if evidence_id not in evidence_ids:
                errors.append(f"ER1.1 decision Evidence does not resolve: {decision_id}/{evidence_id}")

    if span_audit.get("auto_fixed_count") != len(span_audit.get("records", [])):
        errors.append("ER1.1 span audit auto_fixed_count does not match records")
    if span_audit.get("review_required_count") != 0:
        errors.append("ER1.1 unexpected unreviewed span audit records require manual review")
    published_story_ids = _published_story_ids(root)
    audited_story_ids = {
        str(item.get("entry_id") or item.get("source_id") or "")
        for item in effective_rows
        if str(item.get("entry_id") or item.get("source_id") or "") in published_story_ids
    }
    if span_audit.get("published_story_count") != len(published_story_ids):
        errors.append("ER1.1 span audit published_story_count is stale")
    if span_audit.get("audited_story_count") != len(audited_story_ids):
        errors.append("ER1.1 span audit audited_story_count is stale")

    regression_derived = [item for item in derived_rows if item.get("entry_id") == "06-yaliang-017"]
    expected_surfaces = {"庾太尉", "亮"}
    if not expected_surfaces.issubset({str(item.get("surface")) for item in regression_derived}):
        errors.append("ER1.1 06-yaliang-017 lacks the expected 庾太尉/亮 derived spans")
    if any(item.get("surface") == "亮" and item.get("resolution_target", {}).get("canonical_name") != "庾亮" for item in regression_derived):
        errors.append("ER1.1 06-yaliang-017 local 亮 span does not resolve to 庾亮")

    decisions = [item for item in decisions_document.get("decisions", []) if isinstance(item, Mapping)]
    if decisions_document.get("schema") != 1 or decisions_document.get("stage") != "er1-person-resolution-decisions":
        errors.append("ER1 human decision document has invalid schema/stage")
    decision_by_id: dict[str, Mapping[str, Any]] = {}
    for decision in decisions:
        mention_id = decision.get("mention_id")
        if not isinstance(mention_id, str) or mention_id in decision_by_id:
            errors.append(f"ER1 duplicate/invalid human decision: {mention_id!r}")
            continue
        decision_by_id[mention_id] = decision
        if mention_id not in raw_by_id:
            errors.append(f"ER1 decision references unknown Mention: {mention_id}")
        errors.extend(_target_valid(decision.get("target"), people_by_id=people_by_id, candidates_by_id=candidates_by_id, label=f"ER1 decision {mention_id}"))
        for evidence_id in decision.get("evidence_ids", []):
            if evidence_id not in evidence_ids:
                errors.append(f"ER1 decision Evidence does not resolve: {mention_id}/{evidence_id}")
        effective_row = effective_by_id.get(mention_id)
        if effective_row is None:
            continue
        if effective_row.get("resolution_decision_source") != "human_review":
            errors.append(f"ER1 reviewed decision was not applied: {mention_id}")
        if effective_row.get("resolution_status") != decision.get("resolution_status") or effective_row.get("resolution_target") != decision.get("target"):
            errors.append(f"ER1 effective result disagrees with reviewed decision: {mention_id}")

    queue_records = [item for item in queue.get("records", []) if isinstance(item, Mapping)]
    queue_ids: set[str] = set()
    for record in queue_records:
        review_id = record.get("review_id")
        mention_id = record.get("mention_id")
        if not isinstance(review_id, str) or review_id in queue_ids:
            errors.append(f"ER1 duplicate/invalid review ID: {review_id!r}")
        else:
            queue_ids.add(review_id)
        effective_row = effective_by_id.get(str(mention_id))
        if effective_row is None:
            errors.append(f"ER1 review queue references unknown Mention: {mention_id!r}")
            continue
        if record.get("story_id") not in story_ids:
            errors.append(f"ER1 review queue references unknown Story: {record.get('story_id')!r}")
        if record.get("resolution_status") != effective_row.get("resolution_status"):
            errors.append(f"ER1 review queue status disagrees with effective Mention: {mention_id}")
        if record.get("resolution_status") == "candidate_for_review" and len(record.get("candidates", [])) < 1:
            errors.append(f"ER1 review queue candidate lacks a concrete identity: {mention_id}")

    collision_records = [item for item in collisions.get("records", []) if isinstance(item, Mapping)]
    if collisions.get("collision_count") != len(collision_records):
        errors.append("ER1 collision_count does not match records length")
    collision_by_surface = {str(item.get("surface")): item for item in collision_records}
    wen_du = collision_by_surface.get("文度")
    if wen_du is None:
        errors.append("ER1 collision registry lacks 文度")
    else:
        keys = {
            _target_key(identity)
            for identity in wen_du.get("candidate_identities", [])
            if isinstance(identity, Mapping)
        }
        if "production_person:person-015" not in keys:
            errors.append("ER1 文度 collision registry lacks 孫晷/person-015")
        if not any(key.startswith("identity_candidate:candidate-identity-067-") for key in keys):
            errors.append("ER1 文度 collision registry lacks 王坦之 candidate")
    for row in collision_records:
        if row.get("resolution_policy") != "never globally unique; require Story-local evidence or human review":
            errors.append(f"ER1 collision has unsafe global policy: {row.get('surface')}")

    regression_ids = {
        str(item.get("mention_id"))
        for item in raw_mentions
        if item.get("entry_id") == "05-fangzheng-058" and item.get("surface") == "文度"
    }
    if not regression_ids:
        errors.append("ER1 regression Story has no 文度 Mentions")
    for mention_id in sorted(regression_ids):
        row = effective_by_id.get(mention_id, {})
        target = row.get("resolution_target")
        if row.get("resolution_status") != "resolved" or not isinstance(target, Mapping) or target.get("target_kind") != "identity_candidate" or target.get("candidate_id") != "candidate-identity-067-liezhuan-002-e72bf92e965f":
            errors.append(f"ER1 王文度 regression is not resolved to 王坦之: {mention_id}")
        if row.get("person_id") == "person-015":
            errors.append(f"ER1 王文度 regression still navigates to 孫晷: {mention_id}")

    # ER1.1.2 prefix-collision gold regressions.  The canonical Mention may
    # still have the old short surface 桓子, but its effective target and
    # build-time display span must be 桓伊/桓子野 whenever the source text
    # contains the longer recognized appellation.
    huan_prefix_story_ids = {
        "05-fangzheng-055",
        "23-rendan-033",
        "23-rendan-042",
        "23-rendan-049",
        "26-qingdi-020",
    }
    huan_rows = [
        row
        for row in effective_rows
        if row.get("surface") == "桓子" and row.get("entry_id") in huan_prefix_story_ids
    ]
    for row in huan_rows:
        target = row.get("resolution_target")
        if row.get("person_id") == "person-016":
            errors.append(f"ER1.1.2 prefix collision still resolves to 王遐: {row.get('mention_id')}")
        if not isinstance(target, Mapping) or target.get("candidate_id") != HUAN_YI_CANDIDATE_ID:
            errors.append(f"ER1.1.2 桓子野 does not resolve to 桓伊: {row.get('mention_id')}")
        span = row.get("display_span")
        if not isinstance(span, Mapping) or span.get("text") != "桓子野":
            errors.append(f"ER1.1.2 maximal 桓子野 span is missing: {row.get('mention_id')}")

    huan_short_rows = [
        row
        for row in effective.get("derived_mentions", [])
        if isinstance(row, Mapping)
        and row.get("entry_id") == "05-fangzheng-055"
        and row.get("surface") == "子野"
    ]
    if not huan_short_rows or any(
        not isinstance(row.get("resolution_target"), Mapping)
        or row["resolution_target"].get("candidate_id") != HUAN_YI_CANDIDATE_ID
        or row.get("coreference_antecedent_mention_id") != "shishuo-p3b-wave-1-78fd849d96483f177986b7e2"
        for row in huan_short_rows
    ):
        errors.append("ER1.1.2 05-fangzheng-055 子野 local coreference is missing or unsafe")

    ancient_quote_ids = {
        "shishuo-p3b-wave-1-6e59def2507645e74bf6a736",
        "shishuo-p3b-wave-1-49ee363817c8c77394cecf83",
    }
    for mention_id in sorted(ancient_quote_ids):
        row = effective_by_id.get(mention_id, {})
        if row.get("resolution_status") != "unresolved" or row.get("person_id") is not None:
            errors.append(f"ER1.1.2 ancient quoted 桓子 incorrectly resolves to 王遐: {mention_id}")

    return errors


if __name__ == "__main__":
    problems = validate()
    if problems:
        print("ER1 person-resolution validation failed:")
        for problem in problems:
            print(f"- {problem}")
        raise SystemExit(1)
    print("ER1 person-resolution validation passed")
