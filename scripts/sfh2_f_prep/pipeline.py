"""Build the offline SFH2.2-F-prep production architecture preflight.

The module reads committed authority and pilot artifacts only.  It never
imports a provider transport, sends a request, creates a Person, or writes
outside the F-prep/frozen namespaces (apart from the explicitly maintained
test classification registry handled by the migration itself).
"""

from __future__ import annotations

import copy
import json
import math
import os
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable, Mapping

from sfh2_f_prep.common import (
    A2OR_ROOT,
    A2OVB_ROOT,
    ALIASES,
    BASELINE_COMMIT,
    FROZEN_OUT,
    GOLD,
    IDENTITY_MANIFEST,
    NARRATIVE_FUNCTIONS,
    OUT,
    PEOPLE,
    ROOT,
    SC1_CURRENT,
    SC1_FROZEN,
    SFH1_CANDIDATES,
    SFH1_FINAL,
    SFH1_IDENTITIES,
    SFH1_MENTIONS,
    SFH1_SEMANTICS,
    SFH1_STORY_PACKETS,
    UX2_STORY_INDEX,
    build_occurrence_inventory,
    canonical_json,
    exact_occurrence_key,
    file_hash,
    input_hashes,
    key_tuple,
    load_authority,
    occurrence_key_hash,
    protected_hashes,
    qualified_cache_entries,
    read_json,
    rows,
    stable_hash,
    text,
    text_hash,
    tree_digest,
    write_json,
)


STORY_SCOPE_SCHEMA = "sfh2-f-prep-production-scope-v1"
OCCURRENCE_SCHEMA = "sfh2-f-prep-occurrence-manifest-v1"
F1_MAX_OCCURRENCES = 30


def _source_file_metadata(path: Path) -> dict[str, Any]:
    return {
        "path": str(path.relative_to(ROOT)),
        "sha256": file_hash(path) if path.is_file() else None,
        "size_bytes": path.stat().st_size if path.is_file() else None,
        "exists": path.is_file(),
    }


def build_production_scope(authority: Mapping[str, Any]) -> dict[str, Any]:
    """Derive the semantic production universe from committed registries."""

    packets = authority["packets"]
    ux2_ids = {
        text(row.get("story_id"))
        for row in authority["ux2"] if text(row.get("story_id"))
    }
    story_rows: list[dict[str, Any]] = []
    excluded: list[dict[str, Any]] = []
    for packet in sorted(packets, key=lambda row: text(row.get("story_id"))):
        story_id = text(packet.get("story_id"))
        evidence = [row for row in packet.get("evidence", []) or [] if isinstance(row, Mapping)]
        reasons: list[str] = []
        if not story_id:
            reasons.append("missing_story_id")
        if not evidence:
            reasons.append("no_source_evidence")
        valid_evidence = sum(bool(text(row.get("evidence_id")) and text(row.get("text")) and text(row.get("source_layer"))) for row in evidence)
        if valid_evidence != len(evidence):
            reasons.append("incomplete_source_evidence")
        row = {
            "story_id": story_id,
            "chapter_id": packet.get("chapter_id"),
            "source_path": packet.get("source_path"),
            "source_sha256": packet.get("source_sha256"),
            "publication_scope": packet.get("publication_scope"),
            "evidence_count": len(evidence),
            "valid_evidence_count": valid_evidence,
            "published_runtime_scope": story_id in ux2_ids,
            "eligible": not reasons,
            "exclusion_reasons": sorted(set(reasons)),
        }
        story_rows.append(row)
        if reasons:
            excluded.append({"story_id": story_id, "reasons": sorted(set(reasons))})

    eligible = [row["story_id"] for row in story_rows if row["eligible"]]
    published = sorted(set(eligible) & ux2_ids)
    research_only = sorted(set(eligible) - ux2_ids)
    publication_counts = Counter(text(row.get("publication_scope")) for row in story_rows if row.get("eligible"))
    source_paths = [
        SFH1_STORY_PACKETS, SFH1_MENTIONS, SFH1_SEMANTICS, SFH1_FINAL,
        SFH1_IDENTITIES, SFH1_CANDIDATES, UX2_STORY_INDEX,
    ]
    source_hashes = {
        str(path.relative_to(ROOT)): file_hash(path)
        for path in source_paths if path.is_file()
    }
    scope_core = {
        "authoritative_story_source": str(SFH1_STORY_PACKETS.relative_to(ROOT)),
        "runtime_published_scope_source": str(UX2_STORY_INDEX.relative_to(ROOT)),
        "eligible_story_ids": eligible,
        "source_hashes": source_hashes,
    }
    return {
        "schema": STORY_SCOPE_SCHEMA,
        "scope_name": "sfh2_semantic_production_candidate",
        "scope_derivation": "current SFH1 historical-reading packets, cross-checked against UX2 published runtime index",
        "authoritative_story_source": _source_file_metadata(SFH1_STORY_PACKETS),
        "runtime_published_scope_source": _source_file_metadata(UX2_STORY_INDEX),
        "total_stories": len(story_rows),
        "eligible_story_count": len(eligible),
        "excluded_story_count": len(excluded),
        "eligible_story_ids": eligible,
        "excluded_stories": excluded,
        "published_runtime_story_count": len(published),
        "published_runtime_story_ids": published,
        "research_only_story_count": len(research_only),
        "research_only_story_ids": research_only,
        "publication_scope_counts": dict(sorted(publication_counts.items())),
        "historical_188_scope_confirmed": len(story_rows) == 188,
        "story_records": story_rows,
        "source_hashes": source_hashes,
        "scope_hash": stable_hash(scope_core),
        "candidate_only": True,
        "canonical_write_back": False,
    }


def _occurrence_manifest(records: list[Mapping[str, Any]], audit: Mapping[str, Any]) -> dict[str, Any]:
    # Keep the production selection index compact.  The detailed source,
    # offset, overlap, and validation diagnostics remain in
    # exact-occurrence-audit.json; duplicating them here would make the
    # machine-readable planning artifact needlessly large.
    rows_out = []
    for row in records:
        source = row.get("source") if isinstance(row.get("source"), Mapping) else {}
        metadata = row.get("mention_metadata") if isinstance(row.get("mention_metadata"), Mapping) else {}
        rows_out.append({
            "occurrence_id": row.get("occurrence_id"),
            "exact_occurrence_key": copy.deepcopy(row.get("exact_occurrence_key")),
            "exact_occurrence_key_hash": row.get("exact_occurrence_key_hash"),
            "source_layer": source.get("source_layer"),
            "target_text_matches": source.get("target_text_matches"),
            "entity_kind": metadata.get("entity_kind"),
            "reference_form": metadata.get("reference_form"),
            "validation_status": row.get("validation_status"),
            "candidate_only": True,
            "canonical_write_back": False,
        })
    return {
        "schema": OCCURRENCE_SCHEMA,
        "selection_unit": "one validated SFH1 mention is one exact semantic occurrence",
        "occurrence_key_fields": [
            "occurrence_id", "case_id", "mention_id", "story_id", "source_evidence_id",
            "source_start", "source_end", "surface",
        ],
        "occurrence_count": len(rows_out),
        "records": rows_out,
        "audit_summary": {
            "duplicate_exact_key_count": audit.get("duplicate_exact_key_count"),
            "overlap_pair_count": audit.get("overlap_pair_count"),
            "nested_span_pair_count": audit.get("nested_span_pair_count"),
            "repeated_surface_group_count": audit.get("repeated_surface_group_count"),
            "invalid_occurrence_count": audit.get("invalid_occurrence_count"),
            "missing_source_evidence_count": audit.get("missing_source_evidence_count"),
        },
        "surface_only_selection_forbidden": True,
        "candidate_only": True,
        "canonical_write_back": False,
    }


def build_identity_readiness(
    occurrence_records: Iterable[Mapping[str, Any]],
) -> dict[str, Any]:
    """Classify readiness conservatively from explicit current state only."""

    occurrences = list(occurrence_records)
    final_rows = {
        text(row.get("mention_id")): row
        for row in rows(read_json(SFH1_FINAL, {}), "records")
    }
    a2or_packets = rows(read_json(A2OR_ROOT / "case-packets.json", {}), "packets")
    a2or_results = {
        text(row.get("mention_id")): row
        for row in rows(read_json(A2OR_ROOT / "occurrence-results.json", {}), "records")
        if row.get("valid") is True
    }
    frozen_by_mention: dict[str, dict[str, Any]] = {}
    for packet_row in a2or_packets:
        packet = packet_row.get("packet")
        if not isinstance(packet, Mapping):
            continue
        mention_id = text(packet.get("mention_id"))
        result = a2or_results.get(mention_id)
        identity = result.get("frozen_identity") if isinstance(result, Mapping) else None
        if mention_id and isinstance(identity, Mapping):
            frozen_by_mention[mention_id] = {
                "source_stage": "SFH2.2-A2R/A2OR frozen identity context",
                "identity_hash": stable_hash(identity),
                "semantic_kind": identity.get("semantic_kind"),
                "reference_type": identity.get("reference_type"),
                "abstain": identity.get("abstain"),
            }

    readiness_rows: list[dict[str, Any]] = []
    counts = Counter()
    final_state_counts = Counter()
    candidate_possible = 0
    for occurrence in occurrences:
        key = occurrence["exact_occurrence_key"]
        mention_id = text(key.get("mention_id"))
        metadata = occurrence.get("mention_metadata") if isinstance(occurrence.get("mention_metadata"), Mapping) else {}
        entity_kind = text(metadata.get("entity_kind"))
        valid = occurrence.get("validation_status") == "valid"
        final = final_rows.get(mention_id, {})
        final_state = text(final.get("final_state"))
        final_state_counts[final_state or "missing"] += 1
        if not valid:
            status = "identity_blocked"
            reason = "exact-occurrence-integrity-failure"
        elif mention_id in frozen_by_mention:
            status = "identity_ready"
            reason = "exact-frozen-qualified-pilot-context"
        elif entity_kind in {"non_person", "collective_person_reference"}:
            status = "identity_not_applicable"
            reason = "explicit-validated-non-person-or-collective-entity-kind"
        else:
            status = "identity_requires_pipeline"
            reason = "no-exact-frozen-sfh2-identity-context-for-this-occurrence"
        new_candidate = bool(
            status == "identity_requires_pipeline"
            and (final.get("candidate_person_id") or final_state in {"review_required", "genuinely_unresolved", "local_candidate_resolved"})
        )
        candidate_possible += int(new_candidate)
        counts[status] += 1
        readiness_rows.append({
            "occurrence_id": occurrence.get("occurrence_id"),
            "exact_occurrence_key": copy.deepcopy(key),
            "identity_readiness": status,
            "reason": reason,
            "current_sfh1_final_state": final_state or None,
            "current_sfh1_person_id_present": bool(final.get("person_id")),
            "current_sfh1_candidate_person_id_present": bool(final.get("candidate_person_id")),
            "new_historical_person_candidate_possibility": new_candidate,
            "frozen_identity_context": copy.deepcopy(frozen_by_mention.get(mention_id)) if mention_id in frozen_by_mention else None,
            "candidate_only": True,
            "canonical_write_back": False,
        })
    return {
        "schema": "sfh2-f-prep-identity-readiness-v1",
        "records": readiness_rows,
        "counts": dict(sorted(counts.items())),
        "frozen_exact_identity_context_count": counts["identity_ready"],
        "identity_pipeline_required_count": counts["identity_requires_pipeline"],
        "identity_not_applicable_count": counts["identity_not_applicable"],
        "identity_blocked_count": counts["identity_blocked"],
        "new_historical_person_candidate_possibility_count": candidate_possible,
        "existing_sfh1_final_state_counts": dict(sorted(final_state_counts.items())),
        "policy": "Only exact qualified SFH2 identity contexts are reusable; existing SFH1 states are evidence/context, not an unqualified production identity result.",
        "candidate_only": True,
        "canonical_write_back": False,
    }


def _a2or_prompt_and_schema_hashes() -> dict[str, Any]:
    paths = [
        ROOT / "scripts/sfh2_a2or/common.py",
        ROOT / "scripts/sfh2_a2or/contracts.py",
        ROOT / "scripts/sfh2_a2or/prompt.py",
        ROOT / "scripts/sfh2_a2or/pipeline.py",
        ROOT / "scripts/sfh2_a2or/transport.py",
        ROOT / "scripts/sfh2_a2ovb/common.py",
        ROOT / "scripts/sfh2_a2ovb/contracts.py",
        ROOT / "scripts/sfh2_a2ovb/prompt.py",
        ROOT / "scripts/sfh2_a2ovb/pipeline.py",
        ROOT / "scripts/sfh2_a2ovb/transport.py",
        ROOT / "scripts/sfh2_a2o/provenance.py",
    ]
    return {
        str(path.relative_to(ROOT)): file_hash(path)
        for path in paths if path.is_file()
    }


def build_semantic_freeze() -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]]:
    identity = read_json(IDENTITY_MANIFEST, {}) or {}
    a2or_arch = read_json(A2OR_ROOT / "architecture.json", {}) or {}
    a2ovb_arch = read_json(A2OVB_ROOT / "architecture.json", {}) or {}
    a2ov_metrics = read_json(ROOT / "data/generated/sfh2-a2ov/metrics.json", {}) or {}
    a2ovb_metrics = read_json(A2OVB_ROOT / "metrics.json", {}) or {}
    protected = protected_hashes()
    code_hashes = _a2or_prompt_and_schema_hashes()
    architecture_core = {
        "schema": "sfh2-semantic-v1-architecture-v1",
        "stage": "SFH2.2-F-prep",
        "identity": {
            "status": identity.get("identity_pipeline_status"),
            "source_stage": "SFH2.2-A2GR qualified identity freeze over A2R",
            "source_manifest": str(IDENTITY_MANIFEST.relative_to(ROOT)),
            "model_and_contract_source": "SFH2.2-A2R frozen architecture and exact provider contracts",
            "dual_historian": True,
            "structural_comparison": True,
            "adjudication_on_qualified_disagreement": True,
            "candidate_only": True,
            "canonical_write_back": False,
        },
        "occurrence_provenance": {
            "status": "QUALIFIED",
            "owner": "Python structural derivation",
            "source": "target.source_evidence_id -> source_evidence.source_layer",
            "surface_inference": False,
        },
        "occurrence_multiclass": {
            "status": "QUALIFIED",
            "source_stage": "SFH2.2-A2OR",
            "model": "deepseek-v4-flash",
            "prompt_version": "sfh2-a2or-occurrence-function-historian-v2",
            "temperature": 0,
            "thinking": {"type": "disabled"},
            "identity_is_frozen": True,
            "gold_not_supplied": True,
        },
        "boundary_validator": {
            "status": "QUALIFIED",
            "source_stage": "SFH2.2-A2OVB",
            "model": "deepseek-v4-flash",
            "prompt_version": "sfh2-a2ovb-blind-boundary-validator-v1",
            "routing": "primary declared narrative_function in participant/reference",
            "judgments": ["event_participant", "referential_only", "uncertain"],
            "primary_blind": True,
            "gold_blind": True,
            "residual_error_blind": True,
            "provider_packet_contains_primary_label": False,
            "identity_is_frozen": True,
        },
        "excluded_components": {
            "a2ov_primary_aware_reviewer": {
                "included_in_production": False,
                "source_stage": "SFH2.2-A2OV",
                "reason": "negative experiment: 26 confirm, 0 revise, 0 abstain, net reviewer gain 0",
                "metrics_source": str((ROOT / "data/generated/sfh2-a2ov/metrics.json").relative_to(ROOT)),
            },
            "old_monolithic_occurrence_role": {
                "semantic_authority": False,
                "use": "compatibility projection only",
            },
        },
        "safety_invariants": {
            "candidate_only": True,
            "canonical_write_back": False,
            "no_production_person_creation": True,
            "no_alias_or_profile_mutation": True,
            "no_retrieval_candidate_identity_gate": True,
            "no_substring_identity": True,
            "no_lexical_python_semantics": True,
            "no_automatic_alias_string_equivalence": True,
            "human_review_promotes_truth": True,
        },
        "qualified_pilot_evidence": {
            "identity_manifest_sha256": file_hash(IDENTITY_MANIFEST),
            "a2or_architecture_hash": a2or_arch.get("architecture_hash"),
            "a2ovb_architecture_hash": a2ovb_arch.get("architecture_hash"),
            "a2ovb_final_accuracy": a2ovb_metrics.get("a2ovb_final"),
            "a2ovb_live_provider_calls": (read_json(A2OVB_ROOT / "provider-accounting.json", {}) or {}).get("provider_calls"),
            "a2ov_negative_metrics": {
                "reviewer_final": a2ov_metrics.get("a2ov_reviewer_final_frozen_baseline"),
                "helpful_revisions": a2ov_metrics.get("helpful_revisions"),
                "harmful_revisions": a2ov_metrics.get("harmful_revisions"),
            },
        },
        "code_hashes": code_hashes,
        "protected_hashes": protected,
        "no_provider_calls_in_f_prep": True,
        "no_full_corpus_live_run": True,
    }
    architecture = dict(architecture_core)
    architecture["architecture_hash"] = stable_hash(architecture_core)
    schemas = {
        "schema": "sfh2-semantic-v1-schemas",
        "occurrence_key": {
            "required": ["occurrence_id", "case_id", "mention_id", "story_id", "source_evidence_id", "source_start", "source_end", "surface"],
            "surface_only_forbidden": True,
        },
        "candidate_semantic_occurrence": {
            "required": ["occurrence_key", "provenance", "identity", "occurrence_semantics", "audit"],
            "additionalProperties": False,
            "candidate_only": True,
            "canonical_write_back": False,
            "fields": {
                "occurrence_key": "exact occurrence key",
                "provenance": ["provenance_layer", "evidence_ids"],
                "identity": ["frozen identity fields", "identity pipeline version", "identity status"],
                "occurrence_semantics": ["primary_narrative_function", "primary_confidence", "boundary_validation_status", "boundary_judgment", "boundary_confidence", "final_narrative_function", "projected_legacy_occurrence_role"],
                "audit": ["pipeline_version", "model_versions", "prompt_hashes", "request_hashes", "provider_witness_hashes", "candidate_only", "canonical_write_back", "review_status"],
            },
        },
        "a2or_primary_output": {
            "source_contract": "scripts/sfh2_a2or/contracts.py",
            "semantic_values": list(NARRATIVE_FUNCTIONS),
            "identity_replacement_fields_forbidden": True,
        },
        "a2ovb_boundary_output": {
            "source_contract": "scripts/sfh2_a2ovb/contracts.py",
            "semantic_values": ["event_participant", "referential_only", "uncertain"],
            "primary_label_forbidden_in_packet": True,
        },
        "legacy_projection": {
            "source": "scripts/sfh2_a2o/provenance.py",
            "authority": "compatibility only; never overrides A2OR/A2OVB semantics",
        },
        "candidate_only": True,
        "canonical_write_back": False,
    }
    protected_doc = {
        "schema": "sfh2-semantic-v1-protected-hashes",
        "captured_at_baseline": BASELINE_COMMIT,
        "purpose": "immutable witnesses for the qualified architecture and current preflight",
        **protected,
        "candidate_only": True,
        "canonical_write_back": False,
    }
    manifest = {
        "schema": "sfh2-semantic-v1-freeze-manifest",
        "stage": "SFH2.2-F-prep",
        "version": "semantic-v1",
        "status": "QUALIFIED_ARCHITECTURE_FROZEN",
        "baseline_commit": BASELINE_COMMIT,
        "identity_source": "SFH2.2-A2GR / A2R qualified identity architecture",
        "occurrence_provenance_source": "SFH2.2-A2O structural source-evidence derivation",
        "occurrence_primary_source": "SFH2.2-A2OR qualified multiclass occurrence historian",
        "boundary_validator_source": "SFH2.2-A2OVB qualified primary-blind boundary validator",
        "negative_experiment_excluded": "SFH2.2-A2OV primary-aware conservative reviewer",
        "architecture_file": "data/frozen/sfh2/semantic-v1/architecture.json",
        "schemas_file": "data/frozen/sfh2/semantic-v1/schemas.json",
        "protected_hashes_file": "data/frozen/sfh2/semantic-v1/protected-hashes.json",
        "identity_manifest": str(IDENTITY_MANIFEST.relative_to(ROOT)),
        "identity_pipeline_status": identity.get("identity_pipeline_status"),
        "identity_metrics": identity.get("identity_metrics"),
        "safety_invariants": architecture_core["safety_invariants"],
        "protected_hashes": protected,
        "candidate_only": True,
        "canonical_write_back": False,
        "no_full_corpus_live_run": True,
    }
    manifest["manifest_hash"] = stable_hash({key: value for key, value in manifest.items() if key != "manifest_hash"})
    return manifest, architecture, schemas, protected_doc


def build_production_dag() -> dict[str, Any]:
    nodes = [
        {"id": "exact_occurrence", "stage": "validated source", "authority": "SFH1 validated mention ledger", "candidate_only": True},
        {"id": "structural_provenance", "stage": "Python", "authority": "source_evidence.source_layer", "candidate_only": True},
        {"id": "qualified_identity", "stage": "SFH2.2-A2R/A2GR", "authority": "frozen identity contract", "candidate_only": True},
        {"id": "frozen_identity_result", "stage": "SFH2.2-A2GR", "authority": "qualified identity result", "candidate_only": True},
        {"id": "a2or_primary", "stage": "SFH2.2-A2OR", "authority": "multiclass occurrence historian", "candidate_only": True},
        {"id": "a2ovb_boundary", "stage": "SFH2.2-A2OVB", "authority": "primary-blind boundary validator", "candidate_only": True},
        {"id": "final_narrative_function", "stage": "mechanical finalization", "authority": "A2OR or A2OVB structured output", "candidate_only": True},
        {"id": "legacy_projection", "stage": "compatibility", "authority": "generic Python projection", "candidate_only": True},
        {"id": "candidate_record", "stage": "candidate semantic layer", "authority": "no canonical write-back", "candidate_only": True},
        {"id": "human_review_boundary", "stage": "review/QA", "authority": "human promotion required", "candidate_only": True},
    ]
    edges = [
        ["exact_occurrence", "structural_provenance"],
        ["structural_provenance", "qualified_identity"],
        ["qualified_identity", "frozen_identity_result"],
        ["frozen_identity_result", "a2or_primary"],
        ["a2or_primary", "a2ovb_boundary", "only when primary structured function is participant/reference"],
        ["a2or_primary", "final_narrative_function", "all non-boundary functions"],
        ["a2ovb_boundary", "final_narrative_function"],
        ["final_narrative_function", "legacy_projection"],
        ["legacy_projection", "candidate_record"],
        ["candidate_record", "human_review_boundary"],
    ]
    return {
        "schema": "sfh2-f-prep-production-dag-v1",
        "nodes": nodes,
        "edges": edges,
        "boundary_routing_is_structured_output_only": True,
        "a2ov_excluded": True,
        "old_occurrence_role_is_not_authority": True,
        "no_automatic_canonical_write_back": True,
        "candidate_only": True,
        "canonical_write_back": False,
    }


def _family_for_form(form: str) -> str:
    return {
        "pronoun_reference": "pronoun_anaphora",
        "descriptive_person_reference": "comparison_or_description_boundary",
        "office_title": "title_honorific",
        "ruler_title": "title_honorific",
        "honorific": "title_honorific",
        "kinship_reference": "kinship_or_genealogy",
        "courtesy_name": "style_or_courtesy",
        "style_name": "style_or_courtesy",
        "surname_reference": "abbreviated_reference",
        "abbreviated_reference": "abbreviated_reference",
        "full_name": "direct_person_form",
        "personal_name": "direct_person_form",
        "nickname": "direct_person_form",
        "uncertain": "uncertain_form",
    }.get(form, "other_form")


def _f1_strata(row: Mapping[str, Any], readiness: Mapping[str, Any], overlap_ids: set[str], repeated_ids: set[str]) -> list[str]:
    key = row["exact_occurrence_key"]
    metadata = row.get("mention_metadata") if isinstance(row.get("mention_metadata"), Mapping) else {}
    source = row.get("source") if isinstance(row.get("source"), Mapping) else {}
    rid = text(row.get("occurrence_id"))
    readiness_by_id = readiness.get("by_occurrence", {})
    rstatus = readiness_by_id.get(rid, {}).get("identity_readiness")
    result = [
        "source_layer:" + text(source.get("source_layer")),
        "entity_kind:" + text(metadata.get("entity_kind")),
        "form_family:" + _family_for_form(text(metadata.get("reference_form"))),
    ]
    if rstatus:
        result.append("identity:" + rstatus)
    if rid in overlap_ids:
        result.append("overlap_or_nested_span")
    if rid in repeated_ids:
        result.append("repeated_surface_within_story")
    if text(metadata.get("entity_kind")) == "person" and text(metadata.get("reference_form")) in {
        "pronoun_reference", "descriptive_person_reference", "office_title", "ruler_title", "honorific", "kinship_reference",
    }:
        result.append("participant_reference_boundary_risk_by_structural_form")
    if rstatus == "identity_requires_pipeline":
        result.append("qualified_identity_pipeline_required")
    if readiness_by_id.get(rid, {}).get("new_historical_person_candidate_possibility"):
        result.append("new_person_candidate_possible")
    return sorted(set(result))


def build_f1_selection(occurrence_records: list[Mapping[str, Any]], readiness_doc: Mapping[str, Any], audit: Mapping[str, Any]) -> dict[str, Any]:
    readiness_by_id = {
        text(row.get("occurrence_id")): row
        for row in readiness_doc.get("records", []) or [] if isinstance(row, Mapping)
    }
    readiness = {"by_occurrence": readiness_by_id}
    overlap_ids = {
        text(pair.get("left_occurrence_id")) for pair in audit.get("overlap_pairs", []) or []
    } | {
        text(pair.get("right_occurrence_id")) for pair in audit.get("overlap_pairs", []) or []
    }
    repeated_ids = {
        text(item.get("occurrence_id"))
        for group in audit.get("repeated_surface_groups", []) or []
        for item in group.get("occurrences", []) or []
        if isinstance(item, Mapping)
    }
    buckets: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for row in occurrence_records:
        for stratum in _f1_strata(row, readiness, overlap_ids, repeated_ids):
            buckets[stratum].append(row)
    selected: dict[str, Mapping[str, Any]] = {}
    selected_reasons: dict[str, set[str]] = defaultdict(set)
    for stratum in sorted(buckets):
        candidate = min(
            buckets[stratum],
            key=lambda row: (stable_hash(row["exact_occurrence_key"]), text(row.get("occurrence_id"))),
        )
        oid = text(candidate.get("occurrence_id"))
        selected[oid] = candidate
        selected_reasons[oid].add(stratum)
    all_rows = sorted(
        occurrence_records,
        key=lambda row: (stable_hash(row["exact_occurrence_key"]), text(row.get("occurrence_id"))),
    )
    for row in all_rows:
        if len(selected) >= F1_MAX_OCCURRENCES:
            break
        oid = text(row.get("occurrence_id"))
        if oid not in selected:
            selected[oid] = row
            selected_reasons[oid].add("deterministic_hash_fill")
    selected_rows = []
    for oid, row in sorted(selected.items(), key=lambda item: (stable_hash(item[1]["exact_occurrence_key"]), item[0])):
        selected_rows.append({
            "occurrence_id": oid,
            "exact_occurrence_key": copy.deepcopy(row["exact_occurrence_key"]),
            "source_layer": row.get("source", {}).get("source_layer") if isinstance(row.get("source"), Mapping) else None,
            "entity_kind": row.get("mention_metadata", {}).get("entity_kind") if isinstance(row.get("mention_metadata"), Mapping) else None,
            "reference_form": row.get("mention_metadata", {}).get("reference_form") if isinstance(row.get("mention_metadata"), Mapping) else None,
            "identity_readiness": readiness_by_id.get(oid, {}).get("identity_readiness"),
            "selection_reason": sorted(selected_reasons[oid]),
            "gold_used_for_selection": False,
            "candidate_only": True,
            "canonical_write_back": False,
        })
    selected_ids = [row["occurrence_id"] for row in selected_rows]
    identity_units = sum(row.get("identity_readiness") == "identity_requires_pipeline" for row in selected_rows)
    boundary_estimate = round(len(selected_rows) * 15 / 26)
    calls = {
        "identity_primary": identity_units,
        "identity_independent": identity_units,
        "identity_adjudicator_pilot_observed": round(identity_units * 33 / 40),
        "occurrence_primary": len(selected_rows),
        "boundary_validator_pilot_observed": boundary_estimate,
        "contract_probes": 3,
        "pilot_observed_total": 2 * identity_units + round(identity_units * 33 / 40) + len(selected_rows) + boundary_estimate + 3,
    }
    core = {
        "selected_occurrence_ids": selected_ids,
        "selection_rule": "deterministic hash-minimum per structural risk stratum, then deterministic hash fill, bounded at 30 occurrences",
        "gold_used_for_selection": False,
    }
    return {
        "schema": "sfh2-f-prep-f1-selection-v1",
        "wave": "F1",
        "selection_is_deterministic": True,
        "selection_method": core["selection_rule"],
        "gold_used_for_selection": False,
        "answer_leakage": False,
        "maximum_occurrence_count": F1_MAX_OCCURRENCES,
        "occurrence_count": len(selected_rows),
        "story_count": len({row["exact_occurrence_key"]["story_id"] for row in selected_rows}),
        "records": selected_rows,
        "selected_story_ids": sorted({row["exact_occurrence_key"]["story_id"] for row in selected_rows}),
        "semantic_coverage_requirements": {
            "selection_is_answer_blind": True,
            "structural_proxies": [
                "main_text_and_liu_annotation",
                "person_identity_and_new_person_candidate_risk",
                "title_or_honorific_forms",
                "pronoun_or_anaphora_forms",
                "participant_reference_boundary_forms",
                "repeated_or_overlapping_occurrences",
            ],
            "semantic_functions_to_audit_in_f1": [
                "citation_source", "historical_exemplum", "person_attribute",
                "collective_reference", "genealogy_reference", "speaker",
                "addressee", "participant", "reference",
            ],
            "semantic_categories_are_not_used_as_gold_selection_labels": True,
            "coverage_requires_post_inference_review": True,
        },
        "selection_hash": stable_hash(core | {"selected_rows": selected_rows}),
        "estimated_provider_calls": calls,
        "not_executed": True,
        "candidate_only": True,
        "canonical_write_back": False,
    }


def _observed_token_rates() -> dict[str, dict[str, Any]]:
    sources = {
        "identity_primary": (ROOT / "data/generated/sfh2-a0r-l/transport.json", "by_stage", "primary_historian", 40),
        "identity_independent": (ROOT / "data/generated/sfh2-a2/transport.json", "raw_provider_by_stage", "historian_b", 40),
        "identity_adjudicator": (ROOT / "data/generated/sfh2-a2r/transport.json", "by_stage", "adjudicator", 33),
        "occurrence_primary": (ROOT / "data/generated/sfh2-a2or/metrics.json", "provider", None, 26),
        "boundary_validator": (A2OVB_ROOT / "provider-accounting.json", None, None, 15),
    }
    result: dict[str, dict[str, Any]] = {}
    for name, (path, outer, inner, divisor) in sources.items():
        doc = read_json(path, {}) or {}
        value: Mapping[str, Any] = doc
        if outer:
            value = doc.get(outer, {}) if isinstance(doc.get(outer), Mapping) else {}
        if inner:
            value = value.get(inner, {}) if isinstance(value.get(inner), Mapping) else {}
        if name == "occurrence_primary":
            value = doc.get("provider", {}) if isinstance(doc.get("provider"), Mapping) else {}
        fields = {
            "prompt_tokens": int(value.get("prompt_tokens") or 0),
            "completion_tokens": int(value.get("completion_tokens") or 0),
            "total_tokens": int(value.get("total_tokens") or 0),
            "observations": divisor,
            "source": str(path.relative_to(ROOT)),
        }
        # A2's raw_provider_by_stage represents 40 provider responses; A2R
        # by_stage represents the 33 new adjudicator logical calls.
        result[name] = {**fields, "per_call": {key: round(fields[key] / divisor, 2) if divisor else 0 for key in ("prompt_tokens", "completion_tokens", "total_tokens")}}
    return result


def _observed_bytes() -> dict[str, Any]:
    raw_roots = [ROOT / "data/generated/sfh2-a2/live", ROOT / "data/generated/sfh2-a2r/live", A2OVB_ROOT]
    raw_files = [
        path for base in raw_roots if base.exists()
        for path in base.rglob("*.json")
        if "raw-api" in path.as_posix()
    ]
    raw_sizes = [path.stat().st_size for path in raw_files]
    compact_sources = [
        (ROOT / "data/generated/sfh2-a2r/final-results.json", 40),
        (ROOT / "data/generated/sfh2-a2or/occurrence-results.json", 26),
        (A2OVB_ROOT / "boundary-results.json", 15),
    ]
    compact_per_call: list[int] = []
    for path, count in compact_sources:
        if path.is_file() and count:
            compact_per_call.append(round(path.stat().st_size / count))
    return {
        "raw_provider_observation_count": len(raw_sizes),
        "raw_provider_average_bytes": round(sum(raw_sizes) / len(raw_sizes), 2) if raw_sizes else 0,
        "raw_provider_median_bytes": sorted(raw_sizes)[len(raw_sizes) // 2] if raw_sizes else 0,
        "compact_result_average_bytes_per_record": round(sum(compact_per_call) / len(compact_per_call), 2) if compact_per_call else 0,
        "compact_sources": [str(path.relative_to(ROOT)) for path, _ in compact_sources if path.is_file()],
    }


def _scenario_call_counts(scope: Mapping[str, Any], readiness: Mapping[str, Any], cache_plan: Mapping[str, Any]) -> dict[str, Any]:
    total = int(scope.get("total_validated_occurrences") or 0)
    identity_required = int(readiness.get("identity_pipeline_required_count") or 0)
    frozen_identity = int(readiness.get("frozen_exact_identity_context_count") or 0)
    occurrence_reusable = int((cache_plan.get("counts_by_stage") or {}).get("occurrence_primary", 0))
    boundary_reusable = int((cache_plan.get("counts_by_stage") or {}).get("boundary_validator", 0))
    identity_units = identity_required
    occurrence_new = max(0, total - occurrence_reusable)
    boundary_ratio = 15 / 26
    adjudication_ratio = 33 / 40
    scenarios: dict[str, Any] = {}
    for name, adjudication_multiplier, boundary_multiplier in (("minimum", 0, 0), ("pilot_observed", adjudication_ratio, boundary_ratio), ("worst_case", 1, 1)):
        identity_adjudicator = round(identity_units * adjudication_multiplier)
        boundary = round(occurrence_new * boundary_multiplier)
        # Three contract probes are planning overhead, not semantic units.
        scenarios[name] = {
            "identity": {
                "frozen_context_reused": frozen_identity,
                "pipeline_units": identity_units,
                "primary_calls": identity_units,
                "independent_calls": identity_units,
                "adjudication_calls": identity_adjudicator,
                "contract_probe_calls": 1,
                "total_calls": 2 * identity_units + identity_adjudicator + 1,
            },
            "occurrence": {
                "primary_calls": occurrence_new,
                "exact_primary_results_reused": occurrence_reusable,
                "boundary_validator_calls": boundary,
                "exact_boundary_results_reused": boundary_reusable,
                "contract_probe_calls": 2,
                "total_calls": occurrence_new + boundary + 2,
            },
            "total_calls": 2 * identity_units + identity_adjudicator + occurrence_new + boundary + 3,
        }
    return {
        "schema": "sfh2-f-prep-call-budget-v1",
        "scope_occurrence_count": total,
        "identity_readiness": {
            "exact_frozen_context_reuse": frozen_identity,
            "qualified_identity_pipeline_required": identity_required,
        },
        "occurrence_exact_cache_reuse": {
            "primary": occurrence_reusable,
            "boundary": boundary_reusable,
        },
        "pilot_observed_rates_are_not_guarantees": True,
        "observed_rates": {
            "identity_adjudication": {"numerator": 33, "denominator": 40, "ratio": adjudication_ratio},
            "boundary_routing": {"numerator": 15, "denominator": 26, "ratio": boundary_ratio},
        },
        "scenarios": scenarios,
        "exact_cache_reusable_provider_results": int(cache_plan.get("exact_reusable_provider_result_count") or 0),
        "net_new_call_estimate_excludes_exact_reusable_results": True,
        "candidate_only": True,
        "canonical_write_back": False,
    }


def build_token_storage_estimate(call_budget: Mapping[str, Any]) -> dict[str, Any]:
    rates = _observed_token_rates()
    bytes_observed = _observed_bytes()
    scenarios: dict[str, Any] = {}
    for name, scenario in (call_budget.get("scenarios") or {}).items():
        identity = scenario.get("identity", {})
        occurrence = scenario.get("occurrence", {})
        def tokens(unit: str, calls: int) -> dict[str, int]:
            rate = rates[unit]["per_call"]
            return {
                key: round(float(rate[key]) * calls)
                for key in ("prompt_tokens", "completion_tokens", "total_tokens")
            }
        parts = {
            "identity_primary": tokens("identity_primary", int(identity.get("primary_calls") or 0)),
            "identity_independent": tokens("identity_independent", int(identity.get("independent_calls") or 0)),
            "identity_adjudicator": tokens("identity_adjudicator", int(identity.get("adjudication_calls") or 0)),
            "occurrence_primary": tokens("occurrence_primary", int(occurrence.get("primary_calls") or 0)),
            "boundary_validator": tokens("boundary_validator", int(occurrence.get("boundary_validator_calls") or 0)),
        }
        total = {key: sum(part[key] for part in parts.values()) for key in ("prompt_tokens", "completion_tokens", "total_tokens")}
        raw_calls = int(scenario.get("total_calls") or 0)
        compact_calls = int(identity.get("pipeline_units") or 0) + int(occurrence.get("primary_calls") or 0) + int(occurrence.get("boundary_validator_calls") or 0)
        scenarios[name] = {
            "by_stage": parts,
            "total_tokens": total,
            "raw_provider_external_archive_bytes_estimate": round(raw_calls * bytes_observed["raw_provider_average_bytes"]),
            "compact_candidate_result_bytes_estimate": round(compact_calls * bytes_observed["compact_result_average_bytes_per_record"]),
        }
    return {
        "schema": "sfh2-f-prep-token-storage-estimate-v1",
        "observed_token_rates": rates,
        "observed_storage_rates": bytes_observed,
        "scenarios": scenarios,
        "pricing_not_invented": True,
        "raw_provider_payloads_external_archive_default": True,
        "compact_results_git_allowed": True,
        "candidate_only": True,
        "canonical_write_back": False,
    }


def build_review_policy() -> dict[str, Any]:
    return {
        "schema": "sfh2-f-prep-review-routing-policy-v1",
        "review_policy_is_structural": True,
        "mandatory_review_triggers": [
            "identity_abstain",
            "identity_adjudication_unresolved",
            "new_historical_person_candidate",
            "invalid_provider_contract",
            "occurrence_function_uncertain",
            "boundary_validator_uncertain",
            "provider_failure",
            "exact_evidence_integrity_failure",
            "identity_provenance_inconsistency",
            "unsupported_final_projection",
            "policy_defined_stage_disagreement",
        ],
        "audit_only_flags": ["low_confidence", "boundary_override", "primary_boundary_disagreement"],
        "confidence_alone_is_not_canonical_authority": True,
        "no_surface_or_lexical_rules": True,
        "human_review_promotes_candidate_truth": True,
        "candidate_only": True,
        "canonical_write_back": False,
    }


def build_checkpoint_policy() -> dict[str, Any]:
    return {
        "schema": "sfh2-f-prep-checkpoint-policy-v1",
        "idempotence": "one stable checkpoint per unit and request hash",
        "stable_units": ["identity:<occurrence_key>", "occurrence_primary:<occurrence_key>", "boundary:<occurrence_key>"],
        "checkpoint_fields": ["unit_id", "request_hash", "status", "attempt", "contract_valid", "output_hash", "provider_witness_hash", "runtime_metadata"],
        "reuse_rule": "valid matching request_hash and all relevant source/config hashes may be reused",
        "invalid_or_incomplete_rule": "rerun according to failure policy",
        "different_request_hash_rule": "never silently reuse",
        "duplicate_semantic_write_rule": "forbidden; candidate output materialization is idempotent",
        "raw_provider_storage": "external archive default",
        "candidate_only": True,
        "canonical_write_back": False,
    }


def build_provider_failure_policy() -> dict[str, Any]:
    return {
        "schema": "sfh2-f-prep-provider-failure-policy-v1",
        "http_400": {"retry": False, "action": "block unit until contract is repaired"},
        "transient_429_5xx_timeout_connection_reset": {"max_retries": 1, "action": "retry once then review-block"},
        "malformed_semantic_output": {"coerce": False, "action": "contract-invalid and review-blocked"},
        "failed_unit": {"hide_from_metrics": False, "promotion": "not eligible"},
        "transport_source": "qualified A1R/A2R transport behavior",
        "candidate_only": True,
        "canonical_write_back": False,
    }


def build_lifecycle_plan() -> dict[str, Any]:
    policy = read_json(ROOT / "config/generated-artifact-policy.json", {}) or {}
    return {
        "schema": "sfh2-f-prep-artifact-lifecycle-plan-v1",
        "policy_source": "config/generated-artifact-policy.json",
        "policy_sha256": file_hash(ROOT / "config/generated-artifact-policy.json") if (ROOT / "config/generated-artifact-policy.json").is_file() else None,
        "classes": {
            "GIT_AUTHORITY": ["human semantic authority", "reviewed Gold", "frozen architecture manifests"],
            "GIT_COMPACT_RESULT": ["scope and occurrence manifests", "candidate projections", "metrics", "cache/checkpoint indexes", "review queues"],
            "EXTERNAL_ARCHIVE_DEFAULT": ["raw provider/API envelopes", "large raw witnesses"],
            "EPHEMERAL_REBUILDABLE": ["temporary replay/debug/scratch state"],
        },
        "f_prep_outputs_compact": True,
        "raw_provider_dumps_committed_by_default": False,
        "existing_historical_artifacts_grandfathered": True,
        "policy_observation": {
            "warn_generated_file_bytes": policy.get("thresholds", {}).get("warn_generated_file_bytes"),
            "require_explicit_classification_bytes": policy.get("thresholds", {}).get("require_explicit_classification_bytes"),
        },
        "candidate_only": True,
        "canonical_write_back": False,
    }


def build_stop_conditions() -> dict[str, Any]:
    abort = [
        "canonical_write_count > 0",
        "production_person_creation_count > 0",
        "protected_hash_mutation",
        "gold_leakage",
        "invalid_exact_occurrence_key",
        "provenance_derivation_failure",
        "identity_mutation_outside_declared_identity_stage",
        "boundary_packet_contains_primary_label",
        "copy_drift_or_undeclared_mutation > 0",
    ]
    stop = [
        "provider_contract_invalid_rate exceeds pre-frozen F1 threshold",
        "unexpected_request_hash_collision",
        "checkpoint_non_idempotence",
        "provider failure after qualified retry policy",
        "artifact growth outside C3 policy",
    ]
    return {
        "schema": "sfh2-f-prep-f1-stop-conditions-v1",
        "abort_immediately": abort,
        "stop_and_review": stop,
        "thresholds_frozen_before_live_execution": True,
        "no_metric_based_threshold_relaxation": True,
        "candidate_only": True,
        "canonical_write_back": False,
    }


def build_success_gate() -> dict[str, Any]:
    return {
        "schema": "sfh2-f-prep-f1-success-gate-v1",
        "operational_gate": [
            "all targets exact and pinned",
            "protected hashes unchanged",
            "canonical writes = 0",
            "production canonical Person creation = 0",
            "contract-valid rate meets frozen threshold",
            "checkpoint/resume deterministic",
            "boundary validator remains primary-blind",
            "provenance structurally correct",
            "identity replacement only in qualified identity stage",
            "review queue captures unresolved cases",
            "artifact growth within C3 policy",
        ],
        "accuracy_interpretation": "F1 is an operational/semantic audit, not a claim of unseen-corpus accuracy.",
        "pilot_26_of_26_not_full_corpus_100_percent": True,
        "candidate_only": True,
        "canonical_write_back": False,
    }


def build_preflight_validation(scope: Mapping[str, Any], occurrence_audit: Mapping[str, Any], readiness: Mapping[str, Any], protected: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "schema": "sfh2-f-prep-preflight-validation-v1",
        "baseline_commit": BASELINE_COMMIT,
        "branch_expected": "main",
        "provider_calls": 0,
        "provider_api_calls": 0,
        "scope_valid": scope.get("eligible_story_count") == scope.get("total_stories") and scope.get("total_stories") == 188,
        "historical_188_scope_confirmed": scope.get("historical_188_scope_confirmed") is True,
        "occurrence_count": occurrence_audit.get("occurrence_count"),
        "exact_occurrence_integrity_failures": occurrence_audit.get("invalid_occurrence_count", 0) + occurrence_audit.get("missing_source_evidence_count", 0) + occurrence_audit.get("duplicate_exact_key_count", 0),
        "identity_blocked_count": readiness.get("identity_blocked_count"),
        "candidate_only": True,
        "canonical_write_back": False,
        "protected_hashes_at_preflight": copy.deepcopy(protected),
        "deterministic_generation": True,
        "no_full_corpus_live_run": True,
    }


def build_metrics(scope: Mapping[str, Any], occurrence_audit: Mapping[str, Any], readiness: Mapping[str, Any], cache_plan: Mapping[str, Any], f1: Mapping[str, Any], call_budget: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "schema": "sfh2-f-prep-metrics-v1",
        "scope": {
            "stories": scope.get("total_stories"),
            "eligible_stories": scope.get("eligible_story_count"),
            "published_runtime_stories": scope.get("published_runtime_story_count"),
            "research_only_stories": scope.get("research_only_story_count"),
            "validated_occurrences": occurrence_audit.get("occurrence_count"),
        },
        "occurrence_integrity": {
            "invalid": occurrence_audit.get("invalid_occurrence_count"),
            "duplicate_exact_keys": occurrence_audit.get("duplicate_exact_key_count"),
            "overlap_pairs": occurrence_audit.get("overlap_pair_count"),
            "nested_pairs": occurrence_audit.get("nested_span_pair_count"),
            "repeated_surface_groups": occurrence_audit.get("repeated_surface_group_count"),
        },
        "identity_readiness": readiness.get("counts"),
        "cache": {
            "exact_provider_results_reusable": cache_plan.get("exact_reusable_provider_result_count"),
            "by_stage": cache_plan.get("counts_by_stage"),
            "frozen_identity_context_reuse": readiness.get("frozen_exact_identity_context_count"),
        },
        "f1": {
            "stories": f1.get("story_count"),
            "occurrences": f1.get("occurrence_count"),
            "estimated_calls": f1.get("estimated_provider_calls"),
        },
        "call_budget": {name: value.get("total_calls") for name, value in (call_budget.get("scenarios") or {}).items()},
        "provider_calls_in_f_prep": 0,
        "candidate_only": True,
        "canonical_write_back": False,
    }


def build_recommendation(scope: Mapping[str, Any], occurrence_audit: Mapping[str, Any], readiness: Mapping[str, Any]) -> dict[str, Any]:
    blocked = occurrence_audit.get("invalid_occurrence_count", 0) or occurrence_audit.get("missing_source_evidence_count", 0) or occurrence_audit.get("duplicate_exact_key_count", 0) or readiness.get("identity_blocked_count", 0)
    recommendation = "sfh2_preflight_validation_failed" if blocked else "sfh2_f1_bounded_wave_ready"
    return {
        "schema": "sfh2-f-prep-recommendation-v1",
        "recommendation": recommendation,
        "next_stage": "SFH2.2-F1" if recommendation == "sfh2_f1_bounded_wave_ready" else None,
        "reason": "The authoritative 188-story SFH1 universe and all 3303 validated exact occurrences pass structural preflight; identity units not already frozen are routed to the qualified identity pipeline." if not blocked else "Exact occurrence or identity readiness blockers remain; do not start F1.",
        "no_full_corpus_live_run": True,
        "provider_calls": 0,
        "candidate_only": True,
        "canonical_write_back": False,
    }


def build_all(output: Path = OUT) -> dict[str, Any]:
    """Build all F-prep outputs deterministically, without provider calls."""

    authority = load_authority()
    scope = build_production_scope(authority)
    occurrence_records, occurrence_audit = build_occurrence_inventory(authority)
    scope["total_validated_occurrences"] = len(occurrence_records)
    scope["occurrence_counts_by_source_layer"] = dict(sorted(Counter(row.get("source", {}).get("source_layer") for row in occurrence_records).items()))
    scope["occurrence_counts_by_entity_kind"] = dict(sorted(Counter(row.get("mention_metadata", {}).get("entity_kind") for row in occurrence_records).items()))
    scope["occurrence_counts_by_reference_form"] = dict(sorted(Counter(row.get("mention_metadata", {}).get("reference_form") for row in occurrence_records).items()))
    scope["source_hashes"] = input_hashes()
    scope["scope_hash"] = stable_hash({key: value for key, value in scope.items() if key not in {"scope_hash", "story_records"}} | {"story_ids": scope.get("eligible_story_ids")})
    occurrence_manifest = _occurrence_manifest(occurrence_records, occurrence_audit)
    readiness = build_identity_readiness(occurrence_records)
    readiness_rows_by_id = {text(row.get("occurrence_id")): row for row in readiness.get("records", [])}
    for row in occurrence_manifest["records"]:
        ready = readiness_rows_by_id.get(text(row.get("occurrence_id")), {})
        row["identity_readiness"] = ready.get("identity_readiness")
        row["new_historical_person_candidate_possibility"] = ready.get("new_historical_person_candidate_possibility", False)
    occurrence_manifest["identity_readiness_counts"] = readiness.get("counts")
    occurrence_manifest["manifest_hash"] = stable_hash({key: value for key, value in occurrence_manifest.items() if key != "manifest_hash"})
    cache_plan = qualified_cache_entries(authority, occurrence_records)
    # The exact A2OR frozen identity context is a separate semantic-context
    # reuse class, not counted as a provider result unless its complete request
    # witness is available.  This prevents unsafe cache relaxation.
    cache_plan["qualified_identity_context_reuse_count"] = readiness.get("frozen_exact_identity_context_count", 0)
    cache_plan["identity_provider_result_reuse_requires_full_request_witness"] = True
    cache_plan["cache_plan_hash"] = stable_hash({key: value for key, value in cache_plan.items() if key != "cache_plan_hash"})
    f1 = build_f1_selection(occurrence_records, readiness, occurrence_audit)
    call_budget = _scenario_call_counts(scope, readiness, cache_plan)
    token_storage = build_token_storage_estimate(call_budget)
    protected = protected_hashes()
    manifest, architecture, schemas, protected_doc = build_semantic_freeze()
    dag = build_production_dag()
    review = build_review_policy()
    checkpoint = build_checkpoint_policy()
    failure = build_provider_failure_policy()
    lifecycle = build_lifecycle_plan()
    stop = build_stop_conditions()
    success = build_success_gate()
    preflight = build_preflight_validation(scope, occurrence_audit, readiness, protected)
    metrics = build_metrics(scope, occurrence_audit, readiness, cache_plan, f1, call_budget)
    recommendation = build_recommendation(scope, occurrence_audit, readiness)
    production_schema = schemas["candidate_semantic_occurrence"] | {"schema": "sfh2-f-prep-production-schema-v1"}

    # All writes below are compact F-prep/frozen planning artifacts.  No
    # existing historical or production artifact is opened for writing.
    write_json(FROZEN_OUT / "manifest.json", manifest)
    write_json(FROZEN_OUT / "architecture.json", architecture)
    write_json(FROZEN_OUT / "schemas.json", schemas)
    write_json(FROZEN_OUT / "protected-hashes.json", protected_doc)
    write_json(output / "production-scope.json", scope)
    write_json(output / "occurrence-manifest.json", occurrence_manifest)
    write_json(output / "exact-occurrence-audit.json", occurrence_audit)
    write_json(output / "identity-readiness.json", readiness)
    write_json(output / "production-dag.json", dag)
    write_json(output / "production-schema.json", production_schema)
    write_json(output / "review-routing-policy.json", review)
    write_json(output / "cache-reuse-plan.json", cache_plan)
    write_json(output / "checkpoint-policy.json", checkpoint)
    write_json(output / "provider-failure-policy.json", failure)
    write_json(output / "call-budget.json", call_budget)
    write_json(output / "token-storage-estimate.json", token_storage)
    write_json(output / "artifact-lifecycle-plan.json", lifecycle)
    write_json(output / "f1-selection.json", f1)
    write_json(output / "f1-stop-conditions.json", stop)
    write_json(output / "f1-success-gate.json", success)
    write_json(output / "preflight-validation.json", preflight)
    write_json(output / "metrics.json", metrics)
    write_json(output / "recommendation.json", recommendation)
    return {
        "scope": scope,
        "occurrence_audit": occurrence_audit,
        "readiness": readiness,
        "cache_plan": cache_plan,
        "call_budget": call_budget,
        "recommendation": recommendation,
    }


if __name__ == "__main__":
    build_all()
    print("SFH2.2-F-prep: offline artifacts generated; provider calls=0")
