#!/usr/bin/env python3
"""Build the isolated SFH2R.1 closeout projection.

SFH2R.1 is a reviewed semantic-authority sync layered after SFH2R.  The
authority file supplies every semantic decision; this module only invokes the
mechanical alias materializer, rebuilds candidate-only profile projections,
and records hashes/audits needed for deterministic validation.
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import apply_sfh2r1_alias_repairs  # noqa: E402
import manual_semantic_authority as authority  # noqa: E402
import rebuild_hdb2_f_profiles as profile_builder  # noqa: E402
import sfh2r_contract  # noqa: E402


OUT = ROOT / "data/generated/sfh2r1"

PROTECTED_CANONICAL_PATHS = (
    "data/people.json",
    "data/relations.json",
    "data/personStory.json",
    "data/annotation/story-temporal-anchors-h0a.json",
    "data/annotation/story-temporal-evidence-h0a.json",
    "data/annotation/kinship-h0b1.json",
    "data/annotation/marriages-h0b1.json",
    "data/annotation/office-tenures-h0b1.json",
)


def read(path: Path, default: Any = None) -> Any:
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else default


def write(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def file_hash(path: Path) -> str | None:
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None


def protected_hashes() -> dict[str, str | None]:
    return {path: file_hash(ROOT / path) for path in PROTECTED_CANONICAL_PATHS}


def _profile_forms(profile: Mapping[str, Any]) -> set[tuple[str, str]]:
    identity = profile.get("identity") if isinstance(profile.get("identity"), Mapping) else {}
    return {
        (form_type, str(surface))
        for field, form_type in (
            ("aliases", "alias"),
            ("courtesy_names", "courtesy_name"),
            ("titles", "title"),
            ("observed_surfaces", "observed_surface"),
        )
        for surface in identity.get(field, []) or []
        if surface not in (None, "")
    }


def _profile_audit(before: Mapping[str, Any], after: Mapping[str, Any], before_candidates: Mapping[str, Any], after_candidates: Mapping[str, Any]) -> dict[str, Any]:
    before_rows = {str(row.get("person_id")): row for row in before.get("records", []) or [] if isinstance(row, Mapping)}
    after_rows = {str(row.get("person_id")): row for row in after.get("records", []) or [] if isinstance(row, Mapping)}
    before_candidates_rows = {str(row.get("person_id")): row for row in before_candidates.get("records", []) or [] if isinstance(row, Mapping)}
    after_candidates_rows = {str(row.get("person_id")): row for row in after_candidates.get("records", []) or [] if isinstance(row, Mapping)}
    person_ids = sorted(set(before_rows) | set(after_rows) | set(before_candidates_rows) | set(after_candidates_rows))
    records: list[dict[str, Any]] = []
    removed: list[dict[str, Any]] = []
    added: list[dict[str, Any]] = []
    for person_id in person_ids:
        old = before_rows.get(person_id, before_candidates_rows.get(person_id, {}))
        new = after_rows.get(person_id, after_candidates_rows.get(person_id, {}))
        old_forms = _profile_forms(old)
        new_forms = _profile_forms(new)
        record = {
            "person_id": person_id,
            "before": old,
            "after": new,
            "forms_removed": [{"form_type": typ, "surface": surface} for typ, surface in sorted(old_forms - new_forms)],
            "forms_added": [{"form_type": typ, "surface": surface} for typ, surface in sorted(new_forms - old_forms)],
        }
        records.append(record)
        removed.extend({"person_id": person_id, **item} for item in record["forms_removed"])
        added.extend({"person_id": person_id, **item} for item in record["forms_added"])
    return {
        "schema": "sfh2r1-profile-before-after-v1",
        "authority": authority.authority_reference(authority.AUTHORITY_V2_PATH),
        "records": records,
        "profile_forms_removed": sorted(removed, key=lambda row: (row["person_id"], row["form_type"], row["surface"])),
        "profile_forms_added": sorted(added, key=lambda row: (row["person_id"], row["form_type"], row["surface"])),
        "profile_form_count_before": sum(len(_profile_forms(row)) for row in [*before_rows.values(), *before_candidates_rows.values()]),
        "profile_form_count_after": sum(len(_profile_forms(row)) for row in [*after_rows.values(), *after_candidates_rows.values()]),
        "candidate_only": True,
        "canonical_write_back": False,
    }


def _offline_replay_summary() -> dict[str, Any]:
    """Return stable, compact effects from the already-run offline replay.

    The replay is deliberately not invoked here.  SFH2R.1 is a materialization
    and closeout stage, so this function only summarizes an existing isolated
    replay directory.  Keeping the summary small makes the closeout manifest
    useful without copying the replay payloads into it.
    """

    replay = OUT / "offline-replay"
    metrics = read(replay / "metrics.json", {}) or {}
    graph = read(replay / "consolidated-graph.json", {}) or {}
    relation = read(replay / "relation-endpoint-reprojection.json", {}) or {}
    if not isinstance(metrics, Mapping):
        return {}
    graph_summary = graph.get("summary") if isinstance(graph.get("summary"), Mapping) else {}
    endpoint_counts = relation.get("endpoint_state_counts") if isinstance(relation.get("endpoint_state_counts"), Mapping) else {}
    return {
        "replay_root": "data/generated/sfh2r1/offline-replay",
        "stories_retained": metrics.get("stories_retained"),
        "person_mentions": metrics.get("person_mentions"),
        "candidate_observations": metrics.get("candidate_observations"),
        "original_sfh1_candidate_person_ids": metrics.get("original_sfh1_candidate_person_ids"),
        "candidate_ids_merged_with_candidate_ids": metrics.get("candidate_ids_merged_with_candidate_ids"),
        "unique_new_candidate_entities": metrics.get("unique_new_candidate_entities"),
        "anonymous_structural_references": metrics.get("anonymous_structural_references"),
        "unresolved_entities": metrics.get("unresolved_entities"),
        "existing_persons_reached_before": metrics.get("existing_persons_reached_before"),
        "existing_persons_reached_after": metrics.get("existing_persons_reached_after"),
        "endpoint_complete_relations_before": metrics.get("endpoint_complete_relations_before"),
        "endpoint_complete_relations_after": metrics.get("endpoint_complete_relations_after"),
        "relation_endpoint_state_counts": dict(sorted((str(k), v) for k, v in endpoint_counts.items())),
        "graph_nodes_before": metrics.get("graph_nodes_before"),
        "graph_nodes_after": metrics.get("graph_nodes_after", graph_summary.get("node_count")),
        "graph_edges_before": metrics.get("edge_count_before"),
        "graph_edges_after": metrics.get("edge_count_after", graph_summary.get("edge_count")),
        "graph_components_before": metrics.get("graph_components_before"),
        "graph_components_after": metrics.get("graph_components_after", graph_summary.get("connected_component_count")),
        "largest_component_before": metrics.get("largest_component_before"),
        "largest_component_after": metrics.get("largest_component_after", graph_summary.get("largest_component_size")),
        "semantic_role_excluded_observation_count": len(graph.get("semantic_role_excluded_observation_ids", []) or []),
        "forbidden_identity_merge_count": metrics.get("forbidden_identity_merge_count"),
        "explicit_distinct_cluster_violations": metrics.get("explicit_distinct_cluster_violations"),
        "suppressed_hda2_claim_reentry_count": metrics.get("suppressed_hda2_claim_reentry_count"),
        "dense_packet_recovered": metrics.get("dense_packet_recovered"),
        "dense_packet_still_failed": metrics.get("dense_packet_still_failed"),
        "llm_calls": (metrics.get("cost") or {}).get("calls", 0) if isinstance(metrics.get("cost"), Mapping) else 0,
        "new_live_llm_calls": (metrics.get("cost") or {}).get("new_live_calls", 0) if isinstance(metrics.get("cost"), Mapping) else 0,
        "new_live_tokens": (metrics.get("cost") or {}).get("new_live_total_tokens", 0) if isinstance(metrics.get("cost"), Mapping) else 0,
        "candidate_only": True,
        "canonical_write_back": False,
    }


def build() -> dict[str, Any]:
    OUT.mkdir(parents=True, exist_ok=True)
    previous_manifest = read(OUT / "repair-manifest.json", {}) or {}
    protected_before = protected_hashes()
    previous_protected_after = previous_manifest.get("protected_canonical_hashes_after") if isinstance(previous_manifest, Mapping) else None
    if isinstance(previous_protected_after, Mapping) and {
        str(key): value for key, value in previous_protected_after.items()
    } != protected_before:
        raise RuntimeError("sfh2r1_protected_canonical_input_drift")
    previous_transition = previous_manifest.get("active_input_transition") if isinstance(previous_manifest, Mapping) else None
    current_before = sfh2r_contract.current_repair_input_hashes()
    if (
        isinstance(previous_transition, Mapping)
        and isinstance(previous_transition.get("after_hashes"), Mapping)
        and current_before == {str(key): str(value) for key, value in previous_transition["after_hashes"].items()}
    ):
        # An idempotent replay keeps the original pre-SFH2R.1 witness instead
        # of turning the already repaired tree into a fictitious new baseline.
        transition_before = {
            str(key): str(value)
            for key, value in (previous_transition.get("before_hashes") or {}).items()
            if str(key) and str(value)
        }
        transition_before_source = "sfh2r1-manifest"
    else:
        transition_before = current_before
        transition_before_source = "current_post_sfh2r_baseline"

    # The first authority was materialized by SFH2R.  Calling its idempotent
    # command here documents the required order and makes this entry point
    # usable from a checkout that has all preceding commits.
    import apply_sfh2r_alias_repairs  # noqa: PLC0415
    apply_sfh2r_alias_repairs.materialize()

    alias_audit = apply_sfh2r1_alias_repairs.materialize()
    before_profiles = read(OUT / "profile-before-after.json", {}) or {}
    before_existing = before_profiles.get("before_document") if isinstance(before_profiles, Mapping) else None
    before_candidates = before_profiles.get("before_candidate_document") if isinstance(before_profiles, Mapping) else None
    if not isinstance(before_existing, Mapping):
        before_existing = read(profile_builder.EXISTING_PROFILE, {}) or {}
    if not isinstance(before_candidates, Mapping):
        before_candidates = read(profile_builder.CANDIDATE_PROFILE, {}) or {}

    profile_audit_summary = profile_builder.rebuild(write=True)
    after_existing = read(profile_builder.EXISTING_PROFILE, {}) or {}
    after_candidates = read(profile_builder.CANDIDATE_PROFILE, {}) or {}
    profile_audit = _profile_audit(before_existing, after_existing, before_candidates, after_candidates)
    # Preserve the actual input documents so a later deterministic replay can
    # reproduce the same before/after audit rather than treating repaired
    # output as a newly contaminated before-image.
    profile_audit["before_document"] = before_existing
    profile_audit["before_candidate_document"] = before_candidates
    profile_audit["profile_builder_integrity"] = profile_audit_summary
    write(OUT / "profile-before-after.json", profile_audit)

    # Keep a compact active-index audit separate from the older SFH2R report.
    active_aliases = read(ROOT / "data/aliases.json", {}) or {}
    alias_rows = alias_audit.get("records", []) if isinstance(alias_audit, Mapping) else []
    active_forms = [
        {
            "alias_id": row.get("alias_id"),
            "surface": row.get("surface"),
            "person_ids": row.get("person_ids", []),
            "resolved_person_ids": row.get("resolved_person_ids", []),
            "status": row.get("status"),
            "resolution_mode": row.get("resolution_mode"),
            "source_evidence_ids": [item.get("evidence_id") for item in row.get("source_evidence", []) or [] if isinstance(item, Mapping)],
        }
        for row in active_aliases.get("aliases", []) or []
        if isinstance(row, Mapping) and any(row.get("alias_id") == item.get("alias_id") for item in alias_rows)
    ]
    write(OUT / "active-identity-index-audit.json", {
        "schema": "sfh2r1-active-identity-index-audit-v1",
        "authority": authority.authority_reference(authority.AUTHORITY_V2_PATH),
        "records": active_forms,
        "candidate_only": True,
        "canonical_write_back": False,
    })

    transition_after = sfh2r_contract.current_repair_input_hashes()
    active_input_transition = {
        "before_source": transition_before_source,
        "before_hashes": transition_before,
        "after_hashes": transition_after,
        "changed_paths": sorted(
            path for path in sorted(set(transition_before) | set(transition_after))
            if transition_before.get(path) != transition_after.get(path)
        ),
        "semantic_basis": "sfh2r1_manual_semantic_authority_only",
    }
    repair_manifest = {
        "schema": "sfh2r1-repair-manifest-v1",
        "authority": authority.authority_reference(authority.AUTHORITY_V2_PATH),
        "authority_sha256": file_hash(authority.AUTHORITY_V2_PATH),
        "preceding_authority": authority.authority_reference(authority.AUTHORITY_PATH),
        "preceding_manifest": "data/generated/sfh2r/repair-manifest.json",
        "active_input_transition": active_input_transition,
        "protected_canonical_hashes_before": protected_before,
        "protected_canonical_hashes_after": protected_hashes(),
        "live_llm_calls": 0,
        "candidate_only": True,
        "canonical_write_back": False,
    }
    write(OUT / "repair-manifest.json", repair_manifest)

    summary = {
        "schema": "sfh2r1-closeout-summary-v1",
        "authority_files": [authority.authority_reference(authority.AUTHORITY_PATH), authority.authority_reference(authority.AUTHORITY_V2_PATH)],
        "authority_hashes": {
            authority.authority_reference(authority.AUTHORITY_PATH): file_hash(authority.AUTHORITY_PATH),
            authority.authority_reference(authority.AUTHORITY_V2_PATH): file_hash(authority.AUTHORITY_V2_PATH),
        },
        "second_pass_alias_repairs": len(alias_rows),
        "second_pass_evidence_rows_removed": sum(len(row.get("removed_evidence_ids", []) or []) for row in alias_rows),
        "second_pass_evidence_rows_retained": sum(len(row.get("retained_evidence_ids", []) or []) for row in alias_rows),
        "profile_forms_removed": len(profile_audit.get("profile_forms_removed", [])),
        "profile_forms_added": len(profile_audit.get("profile_forms_added", [])),
        "active_alias_sha256": file_hash(ROOT / "data/aliases.json"),
        "active_profile_sha256": file_hash(profile_builder.EXISTING_PROFILE),
        "active_candidate_profile_sha256": file_hash(profile_builder.CANDIDATE_PROFILE),
        "active_input_transition": active_input_transition,
        "repair_manifest_sha256": file_hash(OUT / "repair-manifest.json"),
        "candidate_only": True,
        "canonical_write_back": False,
    }
    replay_summary = _offline_replay_summary()
    if replay_summary:
        write(OUT / "offline-replay-effects.json", {
            "schema": "sfh2r1-offline-replay-effects-v1",
            "source": "data/generated/sfh2r1/offline-replay",
            **replay_summary,
            "candidate_only": True,
            "canonical_write_back": False,
        })
        summary["offline_replay_effects"] = replay_summary
    write(OUT / "closeout-summary.json", summary)
    return summary


if __name__ == "__main__":
    print(json.dumps(build(), ensure_ascii=False, indent=2, sort_keys=True))
