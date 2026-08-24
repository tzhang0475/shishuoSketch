#!/usr/bin/env python3
"""Validate the HNG2 Historical Entity Schema V1 offline projection."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parents[1]
SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from historical_entity_schema import (  # noqa: E402
    CONSTRAINT_STATUSES,
    DISCOURSE_ROLES,
    ENTITY_KINDS,
    GRAPH_ACTIONS,
    IDENTITY_STATUSES,
    MENTION_SCOPES,
    REFERENCE_FORMS,
    RESEARCH_ACTIONS,
    RESEARCH_GAP_STATUSES,
    SEMANTIC_LEVELS,
    SCHEMA_VERSION,
)
from build_hng2_schema_replay import (  # noqa: E402
    INPUT_FILES,
    OUTPUT_FILES,
    OUTPUT_ROOT,
    hash_tree,
    read_json,
    sha256_file,
)


class ValidationError(Exception):
    pass


def _read(name: str) -> dict[str, Any]:
    value = read_json(OUTPUT_ROOT / name)
    if not isinstance(value, dict):
        raise ValidationError(f"missing_or_non_object:{name}")
    return value


def _canonical_false(value: Mapping[str, Any], label: str, errors: list[str]) -> None:
    if value.get("canonical_write_back") is not False:
        errors.append(f"canonical_write_back:{label}")


def _protected_roots() -> dict[str, Path]:
    roots = {}
    for name in ("hng0", "hng0-1", "hng0-2", "hng0-2r", "hng1", "hng1r", "hng1r2", "hng2", "hng2-live"):
        roots[name] = ROOT / "data/generated" / name
    roots["srm0"] = ROOT / "data/generated/srm0"
    return roots


def validate(*, mode: str = "portable") -> list[str]:
    errors: list[str] = []
    for name in OUTPUT_FILES:
        if not (OUTPUT_ROOT / name).is_file():
            errors.append(f"missing:{name}")
    if errors:
        return errors
    try:
        manifest = _read("manifest.json")
        cases_doc = _read("cases.json")
        mentions_doc = _read("mentions.json")
        interpretations_doc = _read("entity-interpretations.json")
        candidates_doc = _read("candidates.json")
        constraints_doc = _read("constraint-checks.json")
        decisions_doc = _read("identity-decisions.json")
        actions_doc = _read("graph-actions.json")
        gaps_doc = _read("research-gaps.json")
        relations_doc = _read("relation-assertions.json")
        validation_doc = _read("validation-cases.json")
        metrics = _read("metrics.json")
    except Exception as exc:
        return [f"read_error:{type(exc).__name__}:{exc}"]

    for label, doc in (("cases", cases_doc), ("mentions", mentions_doc), ("interpretations", interpretations_doc), ("candidates", candidates_doc), ("constraints", constraints_doc), ("decisions", decisions_doc), ("actions", actions_doc), ("gaps", gaps_doc), ("relations", relations_doc), ("validation", validation_doc)):
        _canonical_false(doc, label, errors)
    if manifest.get("schema") != SCHEMA_VERSION:
        errors.append("schema_version")
    if manifest.get("canonical_write_back") is not False:
        errors.append("manifest_canonical_write_back")
    if manifest.get("model", {}).get("model_calls") != 0 or manifest.get("model", {}).get("api_calls") != 0:
        errors.append("model_calls_nonzero")
    if metrics.get("model_calls") != 0 or metrics.get("api_calls") != 0:
        errors.append("metrics_model_calls_nonzero")

    cases = cases_doc.get("cases", [])
    regression_case_records = validation_doc.get("regression_case_records", [])
    mentions = mentions_doc.get("mentions", [])
    interpretations = interpretations_doc.get("interpretations", [])
    decisions = decisions_doc.get("decisions", [])
    actions = actions_doc.get("actions", [])
    gaps = gaps_doc.get("gaps", [])
    case_ids = {str(row.get("case_id")) for row in cases if isinstance(row, Mapping)}
    if len(case_ids) != len(cases):
        errors.append("duplicate_case_id")
    allowed_mention_keys = {"mention_id", "surface", "exact_span", "source_ref", "source_work", "locator", "start", "end"}
    for row in mentions:
        if not isinstance(row, Mapping):
            errors.append("malformed_mention")
            continue
        if set(row) - allowed_mention_keys:
            errors.append(f"mention_contains_inference:{row.get('mention_id')}")
        for key in ("mention_id", "surface", "exact_span", "source_ref", "source_work"):
            if not str(row.get(key) or "").strip():
                errors.append(f"empty_mention:{row.get('mention_id')}:{key}")
    for row in interpretations:
        if row.get("entity_kind") not in ENTITY_KINDS:
            errors.append(f"entity_kind:{row.get('mention_id')}")
        if row.get("reference_form") not in REFERENCE_FORMS:
            errors.append(f"reference_form:{row.get('mention_id')}")
        if row.get("mention_scope") not in MENTION_SCOPES:
            errors.append(f"mention_scope:{row.get('mention_id')}")
        if row.get("discourse_role") not in DISCOURSE_ROLES:
            errors.append(f"discourse_role:{row.get('mention_id')}")
    for row in decisions + [record.get("decision", {}) | {"case_id": record.get("case_id")} for record in regression_case_records if isinstance(record, Mapping) and isinstance(record.get("decision"), Mapping)]:
        status = row.get("identity_status")
        if status not in IDENTITY_STATUSES:
            errors.append(f"identity_status:{row.get('case_id')}:{status}")
        if status == "provisional":
            errors.append(f"stale_provisional_identity_status:{row.get('case_id')}")
        if status == "resolved_existing" and not row.get("person_id"):
            errors.append(f"resolved_existing_without_person:{row.get('case_id')}")
        if status == "resolved_new_candidate" and not row.get("provisional_person_id"):
            errors.append(f"resolved_new_without_provisional:{row.get('case_id')}")
    for group in candidates_doc.get("case_candidates", []):
        for candidate in group.get("candidates", []) if isinstance(group, Mapping) else []:
            key = str(candidate.get("candidate_key") or "")
            if not (key.startswith("c") and key[1:].isdigit()):
                errors.append(f"non_local_candidate_key:{key}")
    for group in constraints_doc.get("case_constraints", []):
        for check in group.get("checks", []) if isinstance(group, Mapping) else []:
            if check.get("status") not in CONSTRAINT_STATUSES:
                errors.append(f"constraint_status:{group.get('case_id')}:{check.get('status')}")
            if check.get("computed_by") != "python":
                errors.append(f"constraint_not_python:{group.get('case_id')}")
    action_by_case = {str(row.get("case_id")): row for row in actions if isinstance(row, Mapping)}
    interp_by_mention = {str(row.get("mention_id")): row for row in interpretations if isinstance(row, Mapping)}
    decision_by_case = {str(row.get("case_id")): row for row in decisions if isinstance(row, Mapping)}
    for case_id, action in action_by_case.items():
        if action.get("action") not in GRAPH_ACTIONS:
            errors.append(f"graph_action:{case_id}")
        if action.get("frontier_status") not in {"eligible", "candidate", "blocked", "needs_identity_review", "needs_semantic_parse", "researched"}:
            errors.append(f"frontier_status:{case_id}")
        status = decision_by_case.get(case_id, {}).get("identity_status")
        if status in {"ambiguous", "not_person", "not_single_person"} and action.get("frontier_status") == "eligible":
            errors.append(f"unsafe_frontier:{case_id}")
        if status == "resolved_existing" and action.get("action") != "link_existing":
            errors.append(f"existing_not_linked:{case_id}")
        if status == "resolved_new_candidate" and action.get("node_type") != "provisional_person":
            errors.append(f"new_not_provisional_node:{case_id}")
    for gap in gaps:
        if gap.get("status") not in RESEARCH_GAP_STATUSES or gap.get("next_best_action") not in RESEARCH_ACTIONS:
            errors.append(f"research_gap_enum:{gap.get('case_id')}")
    for row in relations_doc.get("relations", []):
        if row.get("semantic_level") not in SEMANTIC_LEVELS:
            errors.append(f"invalid_semantic_level:{row.get('relation_id')}")
        if not str(row.get("relation_semantics_description") or "").strip():
            errors.append(f"empty_relation_description:{row.get('relation_id')}")
        if row.get("canonical_write_back") is not False:
            errors.append(f"relation_canonical_write_back:{row.get('relation_id')}")
    if validation_doc.get("all_passed") is not True:
        errors.append("regression_cases_not_all_passed")
    for row in validation_doc.get("regression_cases", []):
        if row.get("passed") is not True:
            errors.append(f"regression_failed:{row.get('case_id')}:{row.get('label')}")

    # Metatextual authors are not silently narrative participants.
    for row in interpretations:
        if row.get("mention_scope") == "metatextual" and row.get("discourse_role") == "cited_author" and row.get("discourse_role") == "event_participant":
            errors.append(f"metatextual_participant:{row.get('mention_id')}")
    # Semantic assessment cannot replace or mutate Python hard constraints.
    for case in cases + regression_case_records:
        if not case.get("semantic_assessment", {}).get("hard_constraints_immutable", False):
            errors.append(f"hard_constraints_not_immutable:{case.get('case_id')}")
        if "constraint_checks" not in case:
            errors.append(f"missing_case_constraints:{case.get('case_id')}")

    # Replayed frozen artifacts and protected project layers must remain byte-identical.
    for label, expected in (manifest.get("protected_artifact_hashes") or {}).items():
        current = hash_tree(_protected_roots().get(label, ROOT / "data/generated" / label))
        if current != expected:
            errors.append(f"protected_artifact_changed:{label}")
    for key, path in INPUT_FILES.items():
        expected = (manifest.get("input_hashes") or {}).get(str(path.relative_to(ROOT)))
        if expected and path.is_file() and sha256_file(path) != expected:
            errors.append(f"input_changed:{key}")
    if mode == "full":
        protected_files = [
            ROOT / "data/people.json", ROOT / "data/aliases.json",
            ROOT / "data/derived/person-story-links.json", ROOT / "data/story-chain-gold-set.json",
        ]
        for path in protected_files:
            key = str(path.relative_to(ROOT))
            expected = (manifest.get("project_input_hashes") or {}).get(key)
            if expected and path.is_file() and sha256_file(path) != expected:
                errors.append(f"project_input_changed:{key}")
    return sorted(set(errors))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("portable", "full"), default="portable")
    args = parser.parse_args()
    errors = validate(mode=args.mode)
    if errors:
        for error in errors:
            print(f"ERROR {error}")
        return 1
    print(f"HNG2-S {args.mode} validation passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
