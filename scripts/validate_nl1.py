#!/usr/bin/env python3
"""Validate the isolated NL1 narrative context/selection corpus."""

from __future__ import annotations

import json
from pathlib import Path
import sys
from typing import Any, Mapping

from jsonschema import Draft202012Validator


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))

from build_nl1_narrative_corpus import (  # noqa: E402
    CONTEXT_PATH,
    H0C_FACTS_PATH,
    HR01_PATH,
    HR0_PATH,
    INPUT_PATHS,
    METRICS_PATH,
    NL0_GOLD_PATH,
    POLICY,
    PROTECTED_PATHS,
    PROTECTION_PATH,
    ROLES,
    SC1_PATH,
    SCENE_CONTEXTS_PATH,
    SCHEMA_PATH,
    SELECTION_PATH,
    S1_ASSERTIONS_PATH,
    S1_CITATIONS_PATH,
    SPEC_PATH,
    SUMMARY_PATH,
    X1_2RF_FACTS_PATH,
    build_documents,
    sha256_file,
    stable_json,
)


def read_json(root: Path, relative: Path) -> Any:
    return json.loads((root / relative).read_text(encoding="utf-8"))


def validate(root: Path = ROOT) -> list[str]:
    errors: list[str] = []
    required = [
        SPEC_PATH,
        SCHEMA_PATH,
        SC1_PATH,
        HR0_PATH,
        HR01_PATH,
        H0C_FACTS_PATH,
        X1_2RF_FACTS_PATH,
        NL0_GOLD_PATH,
        SCENE_CONTEXTS_PATH,
        CONTEXT_PATH,
        SELECTION_PATH,
        METRICS_PATH,
        SUMMARY_PATH,
        PROTECTION_PATH,
    ]
    for relative in required:
        if not (root / relative).is_file():
            errors.append(f"missing NL1 artifact: {relative}")
    if errors:
        return errors

    schema = read_json(root, SCHEMA_PATH)
    spec = read_json(root, SPEC_PATH)
    context = read_json(root, CONTEXT_PATH)
    selection = read_json(root, SELECTION_PATH)
    metrics = read_json(root, METRICS_PATH)
    summary = read_json(root, SUMMARY_PATH)
    protection = read_json(root, PROTECTION_PATH)
    sc1 = read_json(root, SC1_PATH)
    hr0 = read_json(root, HR0_PATH)
    hr01 = read_json(root, HR01_PATH)
    h0c = read_json(root, H0C_FACTS_PATH)
    x1_2rf = read_json(root, X1_2RF_FACTS_PATH)
    nl0 = read_json(root, NL0_GOLD_PATH)
    s1_assertions = read_json(root, S1_ASSERTIONS_PATH)
    s1_citations = read_json(root, S1_CITATIONS_PATH)

    for label, document in (("context", context), ("selection", selection)):
        schema_errors = sorted(
            Draft202012Validator(schema).iter_errors(document),
            key=lambda error: list(error.absolute_path),
        )
        errors.extend(
            f"{label} schema: {error.message} at /{'/'.join(str(part) for part in error.absolute_path)}"
            for error in schema_errors
        )

    expected_hashes = {path.as_posix(): sha256_file(root, path) for path in INPUT_PATHS}
    for label, document in (("context", context), ("selection", selection), ("metrics", metrics), ("summary", summary)):
        if document.get("source_hashes") != expected_hashes:
            errors.append(f"{label} source_hashes do not match current inputs")
        if document.get("policy") != POLICY:
            errors.append(f"{label} policy is not the NL1 no-write-back policy")

    story_by_id = {str(row.get("id")): row for row in sc1.get("stories", [])}
    people_ids = {str(row.get("id")) for row in sc1.get("people", [])}
    evidence_by_story = {
        story_id: {str(evidence_id) for evidence_id in story.get("evidence_ids", [])}
        for story_id, story in story_by_id.items()
    }
    hr0_by_story = {str(row.get("story_id")): row for row in hr0.get("records", [])}
    hr01_by_story = {str(row.get("story_id")): row for row in hr01.get("records", [])}
    nl0_by_story = {str(row.get("story_id")): row for row in nl0.get("records", [])}
    s1_assertion_ids = {str(row.get("assertion_id")) for row in s1_assertions.get("records", []) if row.get("assertion_id")}
    s1_citation_ids = {str(row.get("citation_id")) for row in s1_citations.get("records", []) if row.get("citation_id")}
    h0c_fact_ids = {str(row.get("fact_id")) for row in h0c.get("fact_index", [])}
    x1_2rf_fact_ids = {str(row.get("fact_id")) for row in x1_2rf.get("facts", [])}

    selected = sorted(str(value) for value in spec.get("scope", {}).get("selected_story_ids", []))
    context_ids = sorted(str(row.get("story_id")) for row in context.get("records", []))
    selection_ids = sorted(str(row.get("story_id")) for row in selection.get("records", []))
    if len(selected) != 30:
        errors.append(f"NL1 Story scope must contain 30 Stories, found {len(selected)}")
    if selected != context_ids or selected != selection_ids:
        errors.append("NL1 Story scope differs between spec, context, and selection outputs")
    if any(story_id not in story_by_id for story_id in selected):
        errors.append("NL1 contains an unknown Story ID")
    if any(story_by_id[story_id].get("publication_state") not in {"preview_ready", "production_ready"} for story_id in selected if story_id in story_by_id):
        errors.append("NL1 contains a Story outside the existing reader-ready projection")

    def check_evidence(story_id: str, evidence_ids: Any, label: str) -> None:
        ids = {str(value) for value in evidence_ids or []}
        if not ids:
            errors.append(f"{story_id} {label} has no evidence")
        if not ids.issubset(evidence_by_story.get(story_id, set())):
            errors.append(f"{story_id} {label} has an orphan evidence reference")

    def check_person(story_id: str, person_id: Any, label: str) -> None:
        if person_id is not None and str(person_id) not in people_ids:
            errors.append(f"{story_id} {label} has an orphan Person reference: {person_id}")

    context_by_story = {str(row.get("story_id")): row for row in context.get("records", [])}
    for record in context.get("records", []):
        story_id = str(record.get("story_id"))
        if record.get("review_status") != "reviewed":
            errors.append(f"{story_id} context is not reviewed")
        scene = record.get("current_scene", {})
        check_evidence(story_id, scene.get("evidence_ids"), "current_scene")
        for participant in scene.get("participant_states", []):
            check_person(story_id, participant.get("person_id"), "participant")
            check_evidence(story_id, participant.get("evidence_ids"), "participant")
        for key in ("historical_stakes", "person_states", "relationship_context", "prior_events", "later_events", "uncertainties"):
            for row in record.get(key, []):
                check_evidence(story_id, row.get("evidence_ids"), key)
        for row in record.get("person_states", []):
            check_person(story_id, row.get("person_id"), "person_state")
        for row in record.get("relationship_context", []):
            check_person(story_id, row.get("subject_person_id"), "relationship subject")
            check_person(story_id, row.get("object_person_id"), "relationship object")
        for span in record.get("key_source_spans", []):
            check_evidence(story_id, [span.get("evidence_id")], "source span")
            locator = span.get("locator") or {}
            if any(Path(str(value)).is_absolute() for value in locator.values() if isinstance(value, str)):
                errors.append(f"{story_id} source span contains an absolute locator")
        grounded = record.get("grounded_inputs", {})
        hr0_row = hr0_by_story.get(story_id)
        hr01_row = hr01_by_story.get(story_id)
        if grounded.get("hr0_situation_id") != (hr0_row or {}).get("situation_id"):
            errors.append(f"{story_id} HR0 situation reference is invalid")
        if not set(grounded.get("hr0_1_case_ids", [])).issubset(set((hr01_row or {}).get("case_ids", []))):
            errors.append(f"{story_id} HR0.1 case reference is invalid")
        expected_nl0 = f"story-sketch-nl0-{story_id}" if story_id in nl0_by_story else None
        if grounded.get("nl0_sketch_id") != expected_nl0:
            errors.append(f"{story_id} NL0 grounding reference is invalid")
        if not set(grounded.get("historical_fact_ids", [])).issubset(h0c_fact_ids | x1_2rf_fact_ids):
            errors.append(f"{story_id} historical fact reference is invalid")
        if not set(grounded.get("s1_assertion_ids", [])).issubset(s1_assertion_ids):
            errors.append(f"{story_id} S1 assertion lineage is invalid")
        if not set(grounded.get("s1_citation_ids", [])).issubset(s1_citation_ids):
            errors.append(f"{story_id} S1 citation lineage is invalid")

    selection_by_story = {str(row.get("story_id")): row for row in selection.get("records", [])}
    for record in selection.get("records", []):
        story_id = str(record.get("story_id"))
        if record.get("review_status") != "reviewed_gold":
            errors.append(f"{story_id} selection record is not reviewed_gold")
        if record.get("context_id") != context_by_story.get(story_id, {}).get("context_id"):
            errors.append(f"{story_id} selection context reference is invalid")
        roles = record.get("roles", {})
        if set(roles) != set(ROLES):
            errors.append(f"{story_id} does not expose exactly the five NL1 narrative roles")
        for role in ROLES:
            selection_row = roles.get(role, {})
            if selection_row.get("role") != role:
                errors.append(f"{story_id} role key mismatch: {role}")
            if selection_row.get("role_label") != {"background": "底色", "in_scene": "入画", "off_scene": "画外", "person_glimpse": "人物一瞥", "resonance": "余韵"}[role]:
                errors.append(f"{story_id} role label mismatch: {role}")
            candidates = selection_row.get("candidates", [])
            candidate_by_id = {str(row.get("candidate_id")): row for row in candidates}
            if len(candidate_by_id) != len(candidates):
                errors.append(f"{story_id} {role} candidate IDs are not unique")
            selected_ids = set(selection_row.get("selected_candidate_ids", []))
            rejected_ids = set(selection_row.get("rejected_candidate_ids", []))
            abstained_ids = set(selection_row.get("abstained_candidate_ids", []))
            if selected_ids & rejected_ids or selected_ids & abstained_ids or rejected_ids & abstained_ids:
                errors.append(f"{story_id} {role} selected/rejected/abstained IDs overlap")
            if not rejected_ids:
                errors.append(f"{story_id} {role} has no explicit rejected candidate")
            for candidate_id, candidate in candidate_by_id.items():
                if candidate.get("role") != role:
                    errors.append(f"{story_id} {role} candidate has wrong role")
                status = candidate.get("candidate_status")
                expected_set = {"selected": selected_ids, "rejected": rejected_ids, "abstained": abstained_ids}.get(status, set())
                if candidate_id not in expected_set:
                    errors.append(f"{story_id} {role} candidate/status index mismatch: {candidate_id}")
                check_evidence(story_id, candidate.get("supporting_evidence"), f"{role} candidate")
                if status in {"selected", "rejected"} and not candidate.get("text"):
                    errors.append(f"{story_id} {role} {status} candidate has no text")
                if status == "abstained" and candidate.get("text") is not None:
                    errors.append(f"{story_id} {role} abstention contains narrative text")
                if status == "rejected" and not candidate.get("rejection_reason"):
                    errors.append(f"{story_id} {role} rejection has no rejection_reason")
            state = selection_row.get("selection_state")
            if state == "selected" and not selected_ids:
                errors.append(f"{story_id} {role} says selected but has no selected candidate")
            if state == "abstained" and selected_ids:
                errors.append(f"{story_id} {role} says abstained but has a selected candidate")

    protection_expected = {path.as_posix(): sha256_file(root, path) for path in PROTECTED_PATHS}
    if protection.get("protected_inputs") != protection_expected:
        errors.append("NL1 protected input hashes changed")
    if any(protection.get("write_back", {}).values()):
        errors.append("NL1 protection manifest permits write-back")
    if protection.get("selection_freeze", {}).get("selected_story_ids") != selected:
        errors.append("NL1 selection freeze does not match selected Story scope")
    if protection.get("selection_freeze", {}).get("review_spec_sha256") != sha256_file(root, SPEC_PATH):
        errors.append("NL1 review-spec hash does not match")

    # The checked-in generated outputs must be exactly what the deterministic
    # builder would produce from the current protected inputs.
    documents = build_documents(root)
    expected_documents = {
        "context": context,
        "selection": selection,
        "metrics": metrics,
        "summary": summary,
        "protection": protection,
    }
    for key, expected in expected_documents.items():
        if stable_json(documents[key]) != stable_json(expected):
            errors.append(f"checked-in NL1 {key} does not match deterministic builder output")
    first = build_documents(root)
    second = build_documents(root)
    for key in first:
        if stable_json(first[key]) != stable_json(second[key]):
            errors.append(f"NL1 builder is nondeterministic for {key}")

    for document in (context, selection, metrics, summary, protection):
        text = stable_json(document)
        for volatile in ("generated_at", "timestamp", "build_time", "built_at"):
            if volatile in text:
                errors.append(f"NL1 artifact contains volatile field: {volatile}")
        if str(root) in text:
            errors.append("NL1 artifact contains an absolute repository path")

    return sorted(set(errors))


def main() -> int:
    errors = validate(ROOT)
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1
    print("NL1 validation passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
