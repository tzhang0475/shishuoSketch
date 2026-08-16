#!/usr/bin/env python3
"""Validate the X1.2R extension-only review boundary."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
from typing import Any, Mapping

try:
    from scripts.x1_2r_common import (
        CANONICAL_EXTENSION_PATH,
        CHANNEL_AUDIT_PATH,
        CITATION_PATH,
        CONFLICT_PATH,
        EVIDENCE_BUNDLES_PATH,
        FACT_REOPEN_PATH,
        FACT_REVIEW_PATH,
        IDENTITY_REVIEW_PATH,
        MATERIALIZATION_PATH,
        PARTICIPANT_REVIEW_PATH,
        S1_ALIGNMENT_PATH,
        S1_ASSERTIONS_PATH,
        S1_CITATIONS_PATH,
        SUMMARY_PATH,
        X1_2A_CANONICAL_FACTS_PATH,
        X1_2A_FACT_REVIEW_PATH,
        X1_2A_MATERIALIZATION_PATH,
        X1_2A_PERSON_REVIEW_PATH,
        X1_2A_REVIEW_MANIFEST_PATH,
        X1_2A_STORY_REVIEW_PATH,
        X1_2P_DEPENDENCY_PATH,
        X1_2P_STORY_REVIEW_PATH,
        load_people_by_id,
        previous_x1_2a_hashes,
        previous_x1_2p_hashes,
        protected_hashes,
        read,
        selected_ids,
        sha256_file,
        source_hashes,
        write,
    )
except ModuleNotFoundError:  # direct execution from scripts/
    from x1_2r_common import (
        CANONICAL_EXTENSION_PATH,
        CHANNEL_AUDIT_PATH,
        CITATION_PATH,
        CONFLICT_PATH,
        EVIDENCE_BUNDLES_PATH,
        FACT_REOPEN_PATH,
        FACT_REVIEW_PATH,
        IDENTITY_REVIEW_PATH,
        MATERIALIZATION_PATH,
        PARTICIPANT_REVIEW_PATH,
        S1_ALIGNMENT_PATH,
        S1_ASSERTIONS_PATH,
        S1_CITATIONS_PATH,
        SUMMARY_PATH,
        X1_2A_CANONICAL_FACTS_PATH,
        X1_2A_FACT_REVIEW_PATH,
        X1_2A_MATERIALIZATION_PATH,
        X1_2A_PERSON_REVIEW_PATH,
        X1_2A_REVIEW_MANIFEST_PATH,
        X1_2A_STORY_REVIEW_PATH,
        X1_2P_DEPENDENCY_PATH,
        X1_2P_STORY_REVIEW_PATH,
        load_people_by_id,
        previous_x1_2a_hashes,
        previous_x1_2p_hashes,
        protected_hashes,
        read,
        selected_ids,
        sha256_file,
        source_hashes,
        write,
    )


ROOT = Path(__file__).resolve().parents[1]
STATES = {"accepted", "unresolved", "rejected"}
ROLES = {"present", "speaker", "actor", "referenced", "off_frame", "annotation_only", "uncertain"}


def _read(path: Path) -> Any:
    return read(path)


def _required_documents() -> dict[str, Any]:
    paths = {
        "bundles": EVIDENCE_BUNDLES_PATH,
        "participant": PARTICIPANT_REVIEW_PATH,
        "identity": IDENTITY_REVIEW_PATH,
        "reopen": FACT_REOPEN_PATH,
        "facts": FACT_REVIEW_PATH,
        "citations": CITATION_PATH,
        "conflicts": CONFLICT_PATH,
        "extension": CANONICAL_EXTENSION_PATH,
        "materialization": MATERIALIZATION_PATH,
        "yield": Path("data/derived/x1-2r-realized-yield.json"),
        "channels": CHANNEL_AUDIT_PATH,
        "summary": SUMMARY_PATH,
    }
    return {name: _read(path) for name, path in paths.items()}


def _check_hash(errors: list[str], label: str, recorded: str | None, path: Path) -> None:
    actual = sha256_file(path)
    if recorded != actual:
        errors.append(f"{label} hash mismatch: recorded {recorded}, actual {actual}")


def validate() -> list[str]:
    errors: list[str] = []
    try:
        docs = _required_documents()
    except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
        return [f"X1.2R artifacts cannot be read: {exc}"]

    selected = selected_ids()
    selected_set = set(selected)
    bundles = docs["bundles"]
    participant = docs["participant"]
    identity = docs["identity"]
    facts = docs["facts"]
    extension = docs["extension"]
    materialization = docs["materialization"]

    if len(selected) != 20 or len(selected_set) != 20:
        errors.append("frozen X1.1 selection is not exactly 20 unique Stories")
    if bundles.get("stage") != "x1-2r-jianshu-evidence-bundles":
        errors.append("evidence bundle stage is invalid")
    if bundles.get("scope", {}).get("new_story_selection_performed") is not False:
        errors.append("evidence bundle records a new Story selection")
    if bundles.get("scope", {}).get("selected_story_ids") != selected:
        errors.append("evidence bundle Story scope differs from frozen selection ordering")
    bundle_rows = bundles.get("records", [])
    if {row.get("story_id") for row in bundle_rows} != selected_set or len(bundle_rows) != 20:
        errors.append("evidence bundles do not cover exactly the frozen 20 Stories")
    for row in bundle_rows:
        for layer in ("base_text", "liu_annotation", "jianshu_note", "collation_note", "other_scholar_note"):
            for block in row.get("blocks", {}).get(layer, []):
                if not block.get("source_locator") or not block.get("text_sha256"):
                    errors.append(f"{row.get('story_id')} {layer} block lacks locator/hash")
        if row.get("evidence_bundle_status") != "aligned":
            errors.append(f"{row.get('story_id')} evidence bundle is not aligned")

    participant_rows = participant.get("records", [])
    if participant.get("stage") != "x1-2r-participant-review":
        errors.append("participant review stage is invalid")
    if {row.get("story_id") for row in participant_rows} != selected_set or len(participant_rows) != 20:
        errors.append("participant review does not cover exactly the frozen 20 Stories")
    people = load_people_by_id()
    for story in participant_rows:
        if story.get("participant_gate") not in {"pass", "unresolved"}:
            errors.append(f"{story.get('story_id')} participant gate is invalid")
        for row in story.get("all_reviewed_surfaces", []):
            if row.get("role") not in ROLES:
                errors.append(f"{story.get('story_id')} has invalid participant role")
            if row.get("review_status") != "reviewed":
                errors.append(f"{story.get('story_id')} has unreviewed participant surface")
            if row.get("hard_participation") and row.get("source_section") != "main_text":
                errors.append(f"{story.get('story_id')} annotation/non-main surface became hard participation")
            if row.get("hard_participation") and row.get("person_id") not in people:
                errors.append(f"{story.get('story_id')} hard participant is not a production Person")
            if row.get("role") == "annotation_only" and row.get("hard_participation"):
                errors.append(f"{story.get('story_id')} annotation-only Person is hard")
        gap = story.get("hard_participant_coverage_gap", {})
        if not isinstance(gap, Mapping) or gap.get("status") not in {"none", "unresolved"}:
            errors.append(f"{story.get('story_id')} has invalid hard-participant coverage-gap status")
        if not story.get("hard_participants") and not gap.get("reason"):
            errors.append(f"{story.get('story_id')} has no hard participant but no explicit coverage-gap reason")

    identity_rows = identity.get("records", [])
    if len(identity_rows) != 3:
        errors.append(f"expected 3 unresolved X1.2A identity candidates, found {len(identity_rows)}")
    if any(row.get("review_status") not in STATES for row in identity_rows):
        errors.append("identity review contains an invalid top-level state")
    if any(row.get("review_status") != "accepted" and row.get("materialization_status") != "not_materialized" for row in identity_rows):
        errors.append("unresolved/rejected identity leaked toward materialization")
    if any(row.get("new_person_created") for row in identity_rows):
        errors.append("X1.2R identity review created a Person without an explicit canonical entity record")

    fact_rows = facts.get("records", [])
    if len(fact_rows) != 58:
        errors.append(f"expected 58 X1.2A unresolved fact candidates, found {len(fact_rows)}")
    for row in fact_rows:
        if row.get("review_status") not in STATES:
            errors.append(f"{row.get('review_item_id')} has invalid fact state")
        if row.get("review_status") != "accepted" and row.get("materialization_status") != "not_materialized":
            errors.append(f"{row.get('review_item_id')} unresolved/rejected fact leaked toward materialization")
        if row.get("review_status") == "accepted" and not row.get("new_evidence_refs"):
            errors.append(f"{row.get('review_item_id')} accepted without new evidence")
        if row.get("reopen_status") == "reopened_due_to_new_source" and not row.get("new_evidence_assertion_ids"):
            errors.append(f"{row.get('review_item_id')} reopened without a Jianshu assertion")
        if row.get("no_ml_write_back") is not True:
            errors.append(f"{row.get('review_item_id')} does not record ML write-back protection")

    citations = docs["citations"]
    citation_rows = citations.get("records", [])
    if any(row.get("verification_status") != "citation_only" or row.get("research_only") is not True or row.get("canonical_fact_created") for row in citation_rows):
        errors.append("citation candidate was treated as verified/canonical evidence")
    if any(row.get("story_id") not in selected_set for row in citation_rows):
        errors.append("citation artifact escaped the frozen 20-Story scope")

    # The ignored source payloads are available in a full local checkout but
    # intentionally absent in portable CI.  When present, verify their bytes;
    # when absent, the committed S1 registration hash remains the contract.
    try:
        try:
            from scripts.s1_jianshu_common import discover_payloads, sha256_path
        except ModuleNotFoundError:
            from s1_jianshu_common import discover_payloads, sha256_path
        payloads = discover_payloads()
        actual_payload_hashes = {kind: sha256_path(path) for kind, path in payloads.items()}
        if actual_payload_hashes != bundles.get("source_hashes", {}).get("jianshu_payloads"):
            errors.append("live Jianshu payload hashes differ from the evidence-bundle registration")
    except (FileNotFoundError, OSError, RuntimeError, ValueError):
        pass

    try:
        tracked = subprocess.run(
            ["git", "ls-files", "sources/downloads/shishuo", ".cache/shishuo-reference/jianshu"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=True,
        ).stdout.splitlines()
        if any(path.endswith((".epub", ".pdf", "story-records.jsonl")) for path in tracked):
            errors.append("raw Jianshu payload/cache is Git-tracked")
    except (OSError, subprocess.SubprocessError):
        pass

    if extension.get("canonical_scope") != "x1-2r-canonical-extension":
        errors.append("canonical extension scope is invalid")
    if extension.get("prior_extension", {}).get("path") != str(X1_2A_CANONICAL_FACTS_PATH):
        errors.append("prior X1.2A extension path is not protected")
    if extension.get("prior_extension", {}).get("sha256") != sha256_file(X1_2A_CANONICAL_FACTS_PATH):
        errors.append("prior X1.2A extension hash is not current")
    old_fact_ids = {row.get("fact_id") for row in read(X1_2A_CANONICAL_FACTS_PATH).get("fact_index", [])}
    new_fact_ids = {row.get("fact_id") for row in extension.get("fact_index", [])}
    if old_fact_ids & new_fact_ids:
        errors.append("X1.2R duplicates an X1.2A fact ID")
    if any(row.get("story_id") not in selected_set for row in extension.get("stories", [])):
        errors.append("canonical Story extension escaped the frozen selection")
    extension_stories = {row.get("story_id"): row for row in extension.get("stories", [])}
    extension_participants = {row.get("participant_id"): row for row in extension.get("participant_records", [])}
    extension_links = {row.get("link_id"): row for row in extension.get("person_story_links", [])}
    extension_mentions = {row.get("mention_id"): row for row in extension.get("mention_projections", [])}
    if set(extension_stories) - selected_set:
        errors.append("canonical Story extension escaped the frozen selection")
    if len(extension_participants) != len(extension.get("participant_records", [])):
        errors.append("canonical extension contains duplicate participant IDs")
    if len(extension_links) != len(extension.get("person_story_links", [])):
        errors.append("canonical extension contains duplicate PersonStory link IDs")
    if len(extension_mentions) != len(extension.get("mention_projections", [])):
        errors.append("canonical extension contains duplicate Mention projection IDs")
    for story_id, story in extension_stories.items():
        if any(participant_id not in extension_participants for participant_id in story.get("participant_record_ids", [])):
            errors.append(f"{story_id} references a missing extension participant record")
        if any(link_id not in extension_links for link_id in story.get("person_story_link_ids", [])):
            errors.append(f"{story_id} references a missing extension PersonStory link")
    for row in extension.get("participant_records", []):
        if row.get("story_id") not in extension_stories:
            errors.append("extension participant record has a non-extension Story")
        if row.get("hard_participation") and row.get("source_section") != "main_text":
            errors.append("extension non-main participant became hard")
        if row.get("role") == "annotation_only" and row.get("hard_participation"):
            errors.append("extension annotation-only participant became hard")
    for row in extension.get("person_story_links", []):
        if row.get("person_id") not in people:
            errors.append("extension PersonStory link points to a non-production Person")
        if row.get("story_id") not in extension_stories:
            errors.append("extension PersonStory link has a non-extension Story")
        if row.get("participant_id") not in extension_participants:
            errors.append("extension PersonStory link has a missing participant record")
    for row in extension.get("mention_projections", []):
        if row.get("mention_id") not in extension_mentions:
            errors.append("extension Mention projection index is inconsistent")
        if row.get("story_id") not in extension_stories:
            errors.append("extension Mention projection has a non-extension Story")
        if row.get("person_id") not in people:
            errors.append("extension Mention projection points to a non-production Person")
    counts = extension.get("counts", {})
    for key, actual in {
        "stories": len(extension.get("stories", [])),
        "persons": len(extension.get("entities", [])),
        "facts": len(extension.get("fact_index", [])),
        "participant_records": len(extension.get("participant_records", [])),
        "person_story_links": len(extension.get("person_story_links", [])),
        "mention_projections": len(extension.get("mention_projections", [])),
    }.items():
        if counts.get(key) != actual:
            errors.append(f"canonical extension count mismatch for {key}")

    expected_x1_2a = previous_x1_2a_hashes()
    expected_x1_2p = previous_x1_2p_hashes()
    recorded_materialization = materialization.get("source_hashes", {})
    for key, value in expected_x1_2a.items():
        name = f"x1_2a_{key}"
        if name in recorded_materialization and recorded_materialization[name] != value:
            errors.append(f"{name} protection hash changed")
    if recorded_materialization.get("x1_2p_story_review") != expected_x1_2p["story_review"]:
        errors.append("X1.2P story review protection hash changed")
    if recorded_materialization.get("x1_2p_dependency_audit") != expected_x1_2p["dependency_audit"]:
        errors.append("X1.2P dependency protection hash changed")
    if materialization.get("preservation", {}).get("no_new_story_selection") is not True:
        errors.append("materialization does not preserve the no-new-selection boundary")
    if materialization.get("preservation", {}).get("no_ml_write_back") is not True:
        errors.append("materialization does not preserve ML write-back protection")

    # Validate every recorded derived hash after all files have been written.
    _check_hash(errors, "participant source evidence bundle", participant.get("source_hashes", {}).get("evidence_bundles"), EVIDENCE_BUNDLES_PATH)
    _check_hash(errors, "identity source participant review", identity.get("source_hashes", {}).get("participant_review"), PARTICIPANT_REVIEW_PATH)
    _check_hash(errors, "fact source participant review", facts.get("source_hashes", {}).get("participant_review"), PARTICIPANT_REVIEW_PATH)
    _check_hash(errors, "materialization extension", materialization.get("extension_sha256"), CANONICAL_EXTENSION_PATH)
    _check_hash(errors, "summary materialization", read(SUMMARY_PATH).get("source_hashes", {}).get("materialization"), MATERIALIZATION_PATH)

    summary = docs["summary"]
    if summary.get("scope", {}).get("selected_story_ids") != selected:
        errors.append("summary selection scope changed")
    if summary.get("stop_boundary") != ["X1.2B", "HG1.1", "ML1.1", "ER2"]:
        errors.append("X1.2R stop boundary is incomplete")
    if summary.get("protection", {}).get("x1_2a_extension_protected") is not True:
        errors.append("summary does not protect X1.2A extension")

    return errors


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args()
    errors = validate()
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        raise SystemExit(1)
    print("X1.2R validation passed")


if __name__ == "__main__":
    main()
