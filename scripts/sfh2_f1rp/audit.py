"""Materialize the offline SFH2.2-F1RP reviewed overlay and policy.

F1RP is intentionally an offline authority/policy stage.  It reads the
immutable F1/F1R evidence and writes only a new reviewed overlay, candidate
entity registry, versioned policy, and compact audit products.  It never
imports a provider client, mutates active Gold, or writes canonical data.

All semantic decisions in this module are keyed by the exact occurrence IDs
already selected by F1.  The compatibility function is a prospective,
structured-axis projection; it does not inspect surfaces or infer meaning
from offsets.
"""

from __future__ import annotations

import copy
import hashlib
import json
import subprocess
from collections import Counter
from pathlib import Path
from typing import Any, Mapping

from sfh2_f1 import common as f1


ROOT = Path(__file__).resolve().parents[2]
BASELINE_COMMIT = "56d3ba8ceb15897806c43cd4e20b2ca75c51df0f"
OUT = ROOT / "data/generated/sfh2-f1rp"
F1_ROOT = ROOT / "data/generated/sfh2-f1"
F1R_ROOT = ROOT / "data/generated/sfh2-f1r"
F1_PREP_ROOT = ROOT / "data/generated/sfh2-f-prep"
SEMANTIC_ROOT = ROOT / "data/frozen/sfh2/semantic-v1"
POLICY_ROOT = ROOT / "data/frozen/sfh2/production-policy-v2"
ACTIVE_GOLD = ROOT / "data/annotation/sfh2-a2o-evaluation-gold.json"

SCHEMA_VERSION = "sfh2-f1rp-v1"

EXACT_KEY_FIELDS = (
    "occurrence_id",
    "case_id",
    "mention_id",
    "story_id",
    "source_evidence_id",
    "source_start",
    "source_end",
    "surface",
)

PROTECTED_FILES = (
    "data/annotation/sfh2-a2o-evaluation-gold.json",
    "data/frozen/sfh2/identity-v1/manifest.json",
    "data/frozen/sfh2/semantic-v1/manifest.json",
    "data/frozen/sfh2/semantic-v1/architecture.json",
    "data/frozen/sfh2/semantic-v1/schemas.json",
    "data/frozen/sfh2/semantic-v1/protected-hashes.json",
    "data/derived/sc1-site.json",
    "data/derived/sc1-current-site.json",
    "site/src/generated/sc1-site.json",
    "site/src/generated/sc1-current-site.json",
    "data/people.json",
    "data/aliases.json",
    "data/derived/h0c-historical-facts.json",
    "data/derived/person-resolution-effective.json",
)

PROTECTED_DIRECTORIES = (
    "data/generated/sfh2-f-prep",
    "data/generated/sfh2-f1",
    "data/generated/sfh2-f1r",
    "data/generated/sfh2-a2",
    "data/generated/sfh2-a2r",
    "data/generated/sfh2-a2g",
    "data/generated/sfh2-a2gr",
    "data/generated/sfh2-a2o",
    "data/generated/sfh2-a2ot",
    "data/generated/sfh2-a2or",
    "data/generated/sfh2-a2os",
    "data/generated/sfh2-a2osp",
    "data/generated/sfh2-a2ov",
    "data/generated/sfh2-a2ovb",
    "data/frozen/sfh2/semantic-v1",
)

POLICY_FILES = (
    "review-routing-policy.json",
    "compatibility-projection-policy.json",
    "semantic-consistency-policy.json",
)


# These are reviewed occurrence decisions, not runtime lexical rules.  The
# key is an immutable occurrence identity; the source record supplies the
# exact source context and is checked against the expected coordinates below.
DECISION_SPECS: tuple[dict[str, Any], ...] = (
    {
        "occurrence_id": "sfh1-mention-4212d15b7a219584954587d8",
        "decision_kind": "semantic_function_and_target_reason_review",
        "identity_applicability": "person_identity_required",
        "narrative_function": "addressee",
        "legacy_occurrence_role": "addressee_reference",
        "reason_target_alignment": "reviewed_drift",
        "target_status": "valid",
        "root_cause": "same_surface_reason_target_drift",
        "semantic_basis": "The pinned nested person occurrence is the recipient of 桓公's question. The later 子野 occurrence that introduces the reply is a different target.",
        "review_reason": "The target is the exact 子野 span inside 桓子野 in the question construction; speaker semantics belong to the later occurrence.",
    },
    {
        "occurrence_id": "sfh1-mention-2d1f96737b7b0ef11588f7e5",
        "decision_kind": "semantic_function_review",
        "identity_applicability": "person_identity_required",
        "narrative_function": "reference",
        "legacy_occurrence_role": "annotation_person",
        "reason_target_alignment": "exact",
        "target_status": "valid",
        "root_cause": "historical_exemplum_scope_overreach",
        "semantic_basis": "堯 is the temporal-historical anchor in 堯時隱人 inside the biography of 巢父; the occurrence does not itself inherit the main-discourse exemplum function.",
        "review_reason": "The relevant example figure is 巢父. This inner occurrence is a background reference within the cited biography.",
    },
    {
        "occurrence_id": "sfh1-mention-ab9210bb6f88d713e884fe26",
        "decision_kind": "semantic_function_and_applicability_review",
        "identity_applicability": "identity_not_applicable",
        "narrative_function": "person_attribute",
        "legacy_occurrence_role": "person_attribute",
        "reason_target_alignment": "exact",
        "target_status": "valid",
        "root_cause": "office_attribute_vs_person_reference",
        "semantic_basis": "In 年十八剌史周俊命爲主簿, the target expresses the office held by the bearer 周俊. The failed boundary response has no semantic authority.",
        "review_reason": "The office expression itself is the attribute-bearing value; the human bearer remains separate.",
    },
    {
        "occurrence_id": "sfh1-mention-e2c43c63a28c758a1c1192f1",
        "decision_kind": "identity_applicability_and_semantic_confirmation",
        "identity_applicability": "identity_not_applicable",
        "narrative_function": "person_attribute",
        "legacy_occurrence_role": "person_attribute",
        "reason_target_alignment": "exact",
        "target_status": "valid",
        "root_cause": "office_attribute_vs_person_reference",
        "semantic_basis": "湘州刺史 is an office expression and remains a person-attribute projection; the office's human bearer does not make the office token a historical-person identity target.",
        "review_reason": "The reviewed F1 interpretation is retained while historical-person identity applicability is removed.",
    },
    {
        "occurrence_id": "sfh1-mention-55b97afde3e7fb4c074361b8",
        "decision_kind": "upstream_target_block",
        "identity_applicability": "ambiguous",
        "narrative_function": None,
        "legacy_occurrence_role": None,
        "reason_target_alignment": "upstream_target_invalid",
        "target_status": "upstream_mention_review_required",
        "root_cause": "upstream_mention_target_error",
        "semantic_basis": None,
        "review_reason": "The selected span is the 康 component of the source title 康别傳, while stored explanations discuss a different later person occurrence. Resolve the upstream mention annotation before semantic promotion.",
    },
    {
        "occurrence_id": "sfh1-mention-7be0675e1cbc7d93e92349be",
        "decision_kind": "non_person_projection_review",
        "identity_applicability": "identity_not_applicable",
        "narrative_function": "reference",
        "legacy_occurrence_role": "other",
        "reason_target_alignment": "exact",
        "target_status": "valid",
        "root_cause": "legacy_projection_entity_kind_blindness",
        "semantic_basis": "江南 is a non-person geographic reference in the annotation; person-specific annotation_person output is not appropriate.",
        "review_reason": "The authoritative axes remain entity_kind=non_person and narrative_function=reference. Production projection v2 therefore uses the generic other fallback.",
    },
    {
        "occurrence_id": "sfh1-mention-ba0a6bfd3b70867199867b3a",
        "decision_kind": "boundary_override_acceptance",
        "identity_applicability": "person_identity_required",
        "narrative_function": "reference",
        "legacy_occurrence_role": "scene_reference",
        "reason_target_alignment": "exact",
        "target_status": "valid",
        "root_cause": "reviewed_boundary_override",
        "semantic_basis": "孔巖 is the comparison standard in the exact evaluative statement and is not thereby an event participant.",
        "review_reason": "The A2OVB referential_only override is accepted as a useful reviewed production control.",
    },
    {
        "occurrence_id": "sfh1-mention-63d90ef457a6a2419f9b1588",
        "decision_kind": "boundary_override_acceptance",
        "identity_applicability": "person_identity_required",
        "narrative_function": "participant",
        "legacy_occurrence_role": "annotation_person",
        "reason_target_alignment": "exact",
        "target_status": "valid",
        "root_cause": "reviewed_boundary_override",
        "semantic_basis": "爰 is the person formally proposed in the narrated memorial/succession action and is genuinely event-involved.",
        "review_reason": "The A2OVB event_participant override is accepted as a useful reviewed production control.",
    },
    {
        "occurrence_id": "sfh1-mention-ff73ef4d86b3e237614ab6af",
        "decision_kind": "semantic_confirmation_with_reason_drift_review",
        "identity_applicability": "person_identity_required",
        "narrative_function": "participant",
        "legacy_occurrence_role": "scene_participant",
        "reason_target_alignment": "reviewed_drift",
        "target_status": "valid",
        "root_cause": "same_surface_reason_target_drift",
        "semantic_basis": "The pinned opening span inside 王祥 is the actor in the narrator-framed serving event; the primary explanation discussed a later 祥 occurrence.",
        "review_reason": "The semantic label is retained, but reason-target drift is recorded as a reviewed audit finding.",
    },
)


EXPECTED_DECISION_KEYS: dict[str, dict[str, Any]] = {
    "sfh1-mention-4212d15b7a219584954587d8": {
        "case_id": "sfh1-mention-4212d15b7a219584954587d8",
        "mention_id": "sfh1-mention-4212d15b7a219584954587d8",
        "story_id": "05-fangzheng-055",
        "source_evidence_id": "sfh1-ev-05-fangzheng-055-main",
        "source_start": 4,
        "source_end": 6,
        "surface": "子野",
    },
    "sfh1-mention-2d1f96737b7b0ef11588f7e5": {
        "case_id": "sfh1-mention-2d1f96737b7b0ef11588f7e5",
        "mention_id": "sfh1-mention-2d1f96737b7b0ef11588f7e5",
        "story_id": "25-paidiao-028",
        "source_evidence_id": "sfh1-ev-25-paidiao-028-liu-annotation-001",
        "source_start": 26,
        "source_end": 27,
        "surface": "堯",
    },
    "sfh1-mention-ab9210bb6f88d713e884fe26": {
        "case_id": "sfh1-mention-ab9210bb6f88d713e884fe26",
        "mention_id": "sfh1-mention-ab9210bb6f88d713e884fe26",
        "story_id": "08-shangyu-020",
        "source_evidence_id": "sfh1-ev-08-shangyu-020-liu-annotation-008",
        "source_start": 18,
        "source_end": 20,
        "surface": "剌史",
    },
    "sfh1-mention-e2c43c63a28c758a1c1192f1": {
        "case_id": "sfh1-mention-e2c43c63a28c758a1c1192f1",
        "mention_id": "sfh1-mention-e2c43c63a28c758a1c1192f1",
        "story_id": "01-dexing-023",
        "source_evidence_id": "sfh1-ev-01-dexing-023-liu-annotation-001",
        "source_start": 16,
        "source_end": 20,
        "surface": "湘州刺史",
    },
    "sfh1-mention-55b97afde3e7fb4c074361b8": {
        "case_id": "sfh1-mention-55b97afde3e7fb4c074361b8",
        "mention_id": "sfh1-mention-55b97afde3e7fb4c074361b8",
        "story_id": "14-rongzhi-005",
        "source_evidence_id": "sfh1-ev-14-rongzhi-005-liu-annotation-001",
        "source_start": 10,
        "source_end": 11,
        "surface": "康",
    },
    "sfh1-mention-7be0675e1cbc7d93e92349be": {
        "case_id": "sfh1-mention-7be0675e1cbc7d93e92349be",
        "mention_id": "sfh1-mention-7be0675e1cbc7d93e92349be",
        "story_id": "05-fangzheng-027",
        "source_evidence_id": "sfh1-ev-05-fangzheng-027-liu-annotation-003",
        "source_start": 1,
        "source_end": 3,
        "surface": "江南",
    },
    "sfh1-mention-ba0a6bfd3b70867199867b3a": {
        "case_id": "sfh1-mention-ba0a6bfd3b70867199867b3a",
        "mention_id": "sfh1-mention-ba0a6bfd3b70867199867b3a",
        "story_id": "09-pinzao-040",
        "source_evidence_id": "sfh1-ev-09-pinzao-040-main",
        "source_start": 17,
        "source_end": 19,
        "surface": "孔巖",
    },
    "sfh1-mention-63d90ef457a6a2419f9b1588": {
        "case_id": "sfh1-mention-63d90ef457a6a2419f9b1588",
        "mention_id": "sfh1-mention-63d90ef457a6a2419f9b1588",
        "story_id": "07-shijian-019",
        "source_evidence_id": "sfh1-ev-07-shijian-019-liu-annotation-003",
        "source_start": 25,
        "source_end": 26,
        "surface": "爰",
    },
    "sfh1-mention-ff73ef4d86b3e237614ab6af": {
        "case_id": "sfh1-mention-ff73ef4d86b3e237614ab6af",
        "mention_id": "sfh1-mention-ff73ef4d86b3e237614ab6af",
        "story_id": "01-dexing-014",
        "source_evidence_id": "sfh1-ev-01-dexing-014-main",
        "source_start": 1,
        "source_end": 2,
        "surface": "祥",
    },
}


def _copy(value: Any) -> Any:
    return copy.deepcopy(value)


def _text(value: Any) -> str:
    return str(value or "").strip()


def _rows(document: Any, key: str = "records") -> list[dict[str, Any]]:
    return f1.rows(document, key=key)


def _occurrence_id(row: Mapping[str, Any]) -> str:
    key = row.get("occurrence_key") if isinstance(row.get("occurrence_key"), Mapping) else row
    return _text(row.get("occurrence_id") or key.get("occurrence_id") or row.get("mention_id"))


def _index(document: Any, key: str = "occurrence_id", list_key: str = "records") -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for row in _rows(document, key=list_key):
        value = _text(row.get(key) or _occurrence_id(row))
        if value:
            result[value] = row
    return result


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _serialized_file_hash(value: Any) -> str:
    rendered = json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    return hashlib.sha256(rendered.encode("utf-8")).hexdigest()


def _git_value(*args: str) -> str:
    try:
        return subprocess.check_output(["git", *args], cwd=ROOT, text=True, stderr=subprocess.DEVNULL).strip()
    except (OSError, subprocess.CalledProcessError):
        return ""


def _key(row: Mapping[str, Any]) -> dict[str, Any]:
    raw = row.get("exact_occurrence_key") if isinstance(row.get("exact_occurrence_key"), Mapping) else row.get("occurrence_key")
    if not isinstance(raw, Mapping):
        raw = row
    result = {name: raw.get(name) for name in EXACT_KEY_FIELDS}
    if any(result[name] in (None, "") for name in EXACT_KEY_FIELDS):
        raise RuntimeError("f1rp_exact_occurrence_key_incomplete")
    if not isinstance(result["source_start"], int) or not isinstance(result["source_end"], int):
        raise RuntimeError("f1rp_exact_occurrence_offsets_invalid")
    return result


def _source_context(acceptance: Mapping[str, Any]) -> dict[str, Any]:
    context = acceptance.get("source_context")
    if not isinstance(context, Mapping):
        raise RuntimeError("f1rp_source_context_missing")
    return _copy(context)


def _assert_expected_key(key: Mapping[str, Any], occurrence_id: str) -> None:
    expected = EXPECTED_DECISION_KEYS.get(occurrence_id)
    if expected is None:
        raise RuntimeError("f1rp_unknown_review_occurrence:" + occurrence_id)
    for field, value in expected.items():
        if key.get(field) != value:
            raise RuntimeError("f1rp_review_occurrence_key_mismatch:" + occurrence_id + ":" + field)


def _protected_paths() -> list[str]:
    paths: set[str] = set(PROTECTED_FILES)
    for directory in PROTECTED_DIRECTORIES:
        absolute = ROOT / directory
        if absolute.is_dir():
            paths.update(str(path.relative_to(ROOT)) for path in absolute.rglob("*") if path.is_file())
    for pattern in ("docs/sfh2-f1-*", "docs/sfh2-f1r-*"):
        paths.update(str(path.relative_to(ROOT)) for path in ROOT.glob(pattern) if path.is_file())
    return sorted(path for path in paths if (ROOT / path).is_file())


def _protected_snapshot() -> dict[str, Any]:
    return {
        "files": {
            path: {
                "sha256": f1.file_hash(ROOT / path),
                "size_bytes": (ROOT / path).stat().st_size,
            }
            for path in _protected_paths()
        }
    }


def _snapshot_digest(snapshot: Mapping[str, Any]) -> str:
    return f1.stable_hash(snapshot)


def _load_inputs() -> dict[str, Any]:
    return {
        "selection": f1.selection_rows(),
        "f1_identity": _index(f1.read_json(F1_ROOT / "identity-results.json", {})),
        "f1_primary": _index(f1.read_json(F1_ROOT / "occurrence-primary-results.json", {})),
        "f1_boundary": _index(f1.read_json(F1_ROOT / "boundary-results.json", {})),
        "f1_candidate": _index(f1.read_json(F1_ROOT / "candidate-semantic-records.json", {})),
        "f1_review_queue": _index(f1.read_json(F1_ROOT / "review-queue.json", {})),
        "f1r_acceptance": _index(f1.read_json(F1R_ROOT / "semantic-acceptance-review.json", {})),
        "f1r_inventory": _index(f1.read_json(F1R_ROOT / "review-inventory.json", {})),
        "f1r_trigger": _index(f1.read_json(F1R_ROOT / "review-trigger-matrix.json", {}), list_key="policy_v2_counterfactual_records"),
        "f1r_applicability": _index(f1.read_json(F1R_ROOT / "identity-applicability-audit.json", {})),
        "f1r_groups": f1.read_json(F1R_ROOT / "new-person-review-groups.json", {}) or {},
        "f1r_transport": f1.read_json(F1R_ROOT / "transport-failure-audit.json", {}) or {},
        "f1r_policy_candidate": f1.read_json(F1R_ROOT / "review-policy-v2-candidate.json", {}) or {},
        "f1r_metrics": f1.read_json(F1R_ROOT / "metrics.json", {}) or {},
        "f1r_burden": f1.read_json(F1R_ROOT / "review-burden-counterfactual.json", {}) or {},
        "semantic_manifest": f1.read_json(SEMANTIC_ROOT / "manifest.json", {}) or {},
        "semantic_architecture": f1.read_json(SEMANTIC_ROOT / "architecture.json", {}) or {},
    }


def _decision_map() -> dict[str, dict[str, Any]]:
    return {str(spec["occurrence_id"]): dict(spec) for spec in DECISION_SPECS}


def _human_authority(inputs: Mapping[str, Any]) -> tuple[dict[str, Any], dict[str, dict[str, Any]]]:
    acceptance = inputs["f1r_acceptance"]
    records: list[dict[str, Any]] = []
    for spec in DECISION_SPECS:
        occurrence_id = str(spec["occurrence_id"])
        previous = acceptance.get(occurrence_id)
        if not isinstance(previous, Mapping):
            raise RuntimeError("f1rp_f1r_acceptance_missing:" + occurrence_id)
        key = _key(previous)
        _assert_expected_key(key, occurrence_id)
        source_context = _source_context(previous)
        record = {
            "occurrence_key": key,
            "source_context": source_context,
            "previous_f1r_state": {
                "identity_applicability": previous.get("identity_applicability"),
                "identity_status": previous.get("identity_status"),
                "identity_review": previous.get("identity_review"),
                "primary_function": previous.get("primary_function"),
                "final_function": previous.get("final_function"),
                "projected_legacy_occurrence_role": previous.get("projected_legacy_occurrence_role"),
                "reason_target_alignment": previous.get("reason_target_alignment"),
                "review_class": previous.get("review_class"),
            },
            "decision_kind": spec["decision_kind"],
            "identity_applicability": spec["identity_applicability"],
            "narrative_function": spec["narrative_function"],
            "legacy_occurrence_role": spec["legacy_occurrence_role"],
            "reason_target_alignment": spec["reason_target_alignment"],
            "target_status": spec["target_status"],
            "root_cause": spec["root_cause"],
            "semantic_basis": spec["semantic_basis"],
            "review_reason": spec["review_reason"],
            "review_status": "reviewed",
            "authority": "human_semantic_review",
            "source_stage": "SFH2.2-F1R",
            "candidate_only": True,
            "canonical_write_back": False,
            "production_person_created": False,
        }
        records.append(record)
    document = {
        "schema": "sfh2-f1rp-human-authority-v1",
        "authority": "human_semantic_review",
        "source_stage": "SFH2.2-F1R",
        "review_status": "reviewed",
        "record_count": len(records),
        "provider_calls": 0,
        "active_gold_path": "data/annotation/sfh2-a2o-evaluation-gold.json",
        "active_gold_sha256": f1.file_hash(ACTIVE_GOLD),
        "active_gold_mutated": False,
        "candidate_only": True,
        "canonical_write_back": False,
        "records": records,
    }
    return document, {str(row["occurrence_key"]["occurrence_id"]): row for row in records}


def _candidate_registry(inputs: Mapping[str, Any]) -> dict[str, Any]:
    source = inputs["f1r_groups"]
    groups = [_copy(row) for row in source.get("groups", []) if isinstance(row, Mapping)]
    if len(groups) != 11:
        raise RuntimeError("f1rp_candidate_group_count_changed")
    for group in groups:
        group["human_entity_review"] = "confirmed_candidate_identity"
        group["canonical_promotion"] = False
        group["review_status"] = "reviewed"
        group["candidate_only"] = True
        group["canonical_write_back"] = False
        group["production_person_created"] = False
        group["source_stage"] = "SFH2.2-F1R"
    members = sum(len(group.get("occurrence_members", [])) for group in groups)
    return {
        "schema": "sfh2-reviewed-candidate-person-registry-v1",
        "registry_status": "human_reviewed_candidate_only",
        "source_stage": "SFH2.2-F1R",
        "source_path": "data/generated/sfh2-f1r/new-person-review-groups.json",
        "source_sha256": f1.file_hash(F1R_ROOT / "new-person-review-groups.json"),
        "registry_lookup_order": [
            "canonical Person registry",
            "human-reviewed candidate Person registry",
            "new LLM historical-person candidate",
        ],
        "lookup_semantics": {
            "exact_structured_identity_only": True,
            "fuzzy_matching": False,
            "substring_matching": False,
            "suffix_heuristics": False,
            "alias_count_inference": False,
            "automatic_name_similarity": False,
        },
        "group_count": len(groups),
        "occurrence_level_proposal_count": members,
        "candidate_only": True,
        "canonical_write_back": False,
        "canonical_person_creation": 0,
        "groups": groups,
    }


def _controls(authority: Mapping[str, Any]) -> dict[str, Any]:
    controls: list[dict[str, Any]] = []
    for row in authority["records"]:
        key = row["occurrence_key"]
        if row["target_status"] == "upstream_mention_review_required":
            control_status = "invalid/upstream-target-control"
            label: dict[str, Any] | None = None
        else:
            control_status = "reviewed_production_control"
            label = {
                "identity_applicability": row["identity_applicability"],
                "narrative_function": row["narrative_function"],
                "legacy_occurrence_role": row["legacy_occurrence_role"],
            }
        controls.append({
            "control_id": "sfh2-f1-control-" + str(key["occurrence_id"]),
            "occurrence_key": _copy(key),
            "source_context": _copy(row["source_context"]),
            "control_status": control_status,
            "human_decision": label,
            "identity_applicability": row["identity_applicability"],
            "reason_target_alignment": row["reason_target_alignment"],
            "target_status": row["target_status"],
            "semantic_basis": row["semantic_basis"],
            "review_reason": row["review_reason"],
            "review_status": "reviewed",
            "candidate_only": True,
            "canonical_write_back": False,
            "production_person_created": False,
        })
    return {
        "schema": "sfh2-f1-reviewed-controls-v1",
        "source_stage": "SFH2.2-F1R",
        "provider_calls": 0,
        "record_count": len(controls),
        "candidate_only": True,
        "canonical_write_back": False,
        "records": controls,
    }


def _review_routing_policy() -> dict[str, Any]:
    return {
        "schema": "sfh2-production-review-routing-policy-v2",
        "policy_version": "production-policy-v2",
        "policy_status": "approved",
        "provider_calls": 0,
        "approved_by": "human_semantic_review",
        "source_stage": "SFH2.2-F1R",
        "activated_for_future_waves": True,
        "mandatory_review_triggers": [
            "identity_adjudication_unresolved",
            "terminal_or_degraded_provider_contract",
            "new_historical_person_entity",
            "occurrence_function_uncertain",
            "terminal_boundary_failure",
            "semantic_output_unresolved",
            "semantic_audit_candidate",
            "reason_target_alignment_failure",
            "unsupported_final_projection",
            "exact_evidence_integrity_failure",
            "upstream_mention_repair_required",
        ],
        "audit_only_triggers": [
            "resolved_stage_disagreement_only",
            "reviewed_candidate_entity_reuse",
            "reviewed_semantic_decision",
            "reviewed_target_drift",
            "boundary_override",
            "low_confidence",
        ],
        "candidate_entity_policy": {
            "reviewed_candidate_entity_does_not_trigger_new_entity_review": True,
            "unreviewed_candidate_entity_remains_mandatory": True,
            "candidate_only": True,
            "canonical_write_back": False,
        },
        "confidence_alone_is_not_canonical_authority": True,
        "review_policy_is_structural": True,
        "no_surface_or_lexical_rules": True,
        "human_review_promotes_candidate_truth": True,
        "boundary_override_alone_is_audit_only": True,
        "low_confidence_alone_is_audit_only": True,
    }


def _compatibility_projection_policy() -> dict[str, Any]:
    return {
        "schema": "sfh2-production-compatibility-projection-v2",
        "policy_version": "production-policy-v2",
        "policy_status": "approved",
        "provider_calls": 0,
        "source_stage": "SFH2.2-F1RP",
        "historical_projection_path": "scripts/sfh2_a2o/provenance.py",
        "historical_projection_mutated": False,
        "authoritative_axes": ["provenance_layer", "narrative_function", "entity_kind", "semantic_kind"],
        "rules": [
            {"when": {"narrative_function": "historical_exemplum"}, "emit": "historical_exemplum"},
            {"when": {"narrative_function": "collective_reference"}, "emit": "collective_reference"},
            {"when": {"narrative_function": "person_attribute"}, "emit": "person_attribute"},
            {"when": {"narrative_function": "genealogy_reference"}, "emit": "genealogy_reference"},
            {"when": {"narrative_function": "citation_source", "entity_kind": "person"}, "emit": "citation_source_person"},
            {"when": {"narrative_function": "speaker", "entity_kind": "person"}, "emit": "speaker_reference"},
            {"when": {"narrative_function": "addressee", "entity_kind": "person"}, "emit": "addressee_reference"},
            {"when": {"semantic_kind": "office", "narrative_function": "person_attribute"}, "emit": "person_attribute"},
            {"when": {"semantic_kind": "office", "narrative_function": "other"}, "emit": "other"},
            {"when": {"entity_kind": "non_person", "narrative_function": "reference"}, "emit": "other"},
            {"when": {"entity_kind": "non_person", "narrative_function": "participant"}, "emit": "other"},
            {"when": {"provenance_layer": "liu_annotation", "entity_kind": "person", "narrative_function": "participant"}, "emit": "annotation_person"},
            {"when": {"provenance_layer": "liu_annotation", "entity_kind": "person", "narrative_function": "reference"}, "emit": "annotation_person"},
            {"when": {"provenance_layer": "main_text", "entity_kind": "person", "narrative_function": "participant"}, "emit": "scene_participant"},
            {"when": {"provenance_layer": "main_text", "entity_kind": "person", "narrative_function": "reference"}, "emit": "scene_reference"},
            {"when": {"narrative_function": "structural"}, "emit": "structural"},
            {"when": {"narrative_function": "other_or_uncertain"}, "emit": "other"},
        ],
        "generic_fallback": "other",
        "non_person_invariant": "A known non-person target must never emit the person-specific annotation_person role.",
        "reviewed_control": {
            "occurrence_id": "sfh1-mention-7be0675e1cbc7d93e92349be",
            "entity_kind": "non_person",
            "narrative_function": "reference",
            "legacy_occurrence_role": "other",
        },
        "no_new_legacy_enum": True,
        "no_surface_or_lexical_rules": True,
        "candidate_only": True,
        "canonical_write_back": False,
    }


def _semantic_consistency_policy() -> dict[str, Any]:
    return {
        "schema": "sfh2-production-semantic-consistency-policy-v2",
        "policy_version": "production-policy-v2",
        "policy_status": "approved",
        "provider_calls": 0,
        "source_stage": "SFH2.2-F1RP",
        "office_invariant": {
            "when": {
                "semantic_kind": "office",
                "narrative_function_in": ["reference", "participant", "speaker", "addressee"],
            },
            "flag": "office_semantic_consistency_review",
            "python_may_correct": False,
            "human_exact_occurrence_review_required": True,
        },
        "target_alignment": {
            "allowed_values": ["unchecked", "exact", "drift_suspected", "reviewed_drift"],
            "surface_inference": False,
            "exact_occurrence_key_required": True,
        },
        "reviewed_controls": {
            "records": [
                {"occurrence_id": "sfh1-mention-4212d15b7a219584954587d8", "status": "reviewed_drift"},
                {"occurrence_id": "sfh1-mention-ff73ef4d86b3e237614ab6af", "status": "reviewed_drift"},
                {"occurrence_id": "sfh1-mention-55b97afde3e7fb4c074361b8", "status": "upstream_target_invalid"},
            ],
        },
        "candidate_only": True,
        "canonical_write_back": False,
        "no_surface_or_lexical_rules": True,
    }


def _identity_semantic_context(identity: Mapping[str, Any]) -> dict[str, Any]:
    context = identity.get("context") if isinstance(identity.get("context"), Mapping) else {}
    frozen = context.get("frozen_identity") if isinstance(context.get("frozen_identity"), Mapping) else {}
    candidate = identity.get("candidate_proposal") if isinstance(identity.get("candidate_proposal"), Mapping) else None
    return {
        "semantic_kind": frozen.get("semantic_kind"),
        "reference_type": frozen.get("reference_type"),
        "referent": _copy(frozen.get("referent", {})),
        "bearer_hint": frozen.get("bearer_hint", ""),
        "attribute_type": frozen.get("attribute_type", ""),
        "attribute_value": frozen.get("attribute_value", ""),
        "identity_status": identity.get("status"),
        "final_state": identity.get("final_state"),
        "candidate_proposal": _copy(candidate),
    }


def _entity_kind(applicability: Mapping[str, Any], identity: Mapping[str, Any]) -> str:
    value = _text(applicability.get("validated_entity_kind"))
    if value:
        if value == "collective_person_reference":
            return "non_person"
        return value
    semantic_kind = _text(_identity_semantic_context(identity).get("semantic_kind"))
    return "person" if semantic_kind == "historical_person" else (semantic_kind or "unknown")


def project_legacy_occurrence_role_v2(
    provenance_layer: str | None,
    narrative_function: str | None,
    entity_kind: str | None,
    semantic_kind: str | None,
) -> str:
    """Project structured semantic axes to the prospective legacy role.

    This function intentionally has no access to an occurrence surface,
    source text, or offsets.  It maps declared semantic categories only.
    """

    layer = _text(provenance_layer)
    function = _text(narrative_function)
    entity = _text(entity_kind)
    semantic = _text(semantic_kind)
    if function == "historical_exemplum":
        return "historical_exemplum"
    if function == "collective_reference":
        return "collective_reference"
    if function == "person_attribute":
        return "person_attribute"
    if function == "genealogy_reference":
        return "genealogy_reference"
    if semantic == "office":
        return "other"
    if entity == "non_person":
        return "other"
    if function == "citation_source" and entity in {"", "person", "historical_person"}:
        return "citation_source_person"
    if function == "speaker" and entity in {"", "person", "historical_person"}:
        return "speaker_reference"
    if function == "addressee" and entity in {"", "person", "historical_person"}:
        return "addressee_reference"
    if layer == "liu_annotation" and entity in {"", "person", "historical_person"} and function in {"participant", "reference"}:
        return "annotation_person"
    if layer == "main_text" and entity in {"", "person", "historical_person"} and function == "participant":
        return "scene_participant"
    if layer == "main_text" and entity in {"", "person", "historical_person"} and function == "reference":
        return "scene_reference"
    if function == "structural":
        return "structural"
    return "other"


def _confirmed_candidate_members(registry: Mapping[str, Any]) -> tuple[dict[str, str], set[str]]:
    occurrence_to_group: dict[str, str] = {}
    group_ids: set[str] = set()
    for group in registry.get("groups", []) or []:
        if not isinstance(group, Mapping):
            continue
        group_id = _text(group.get("group_id"))
        group_ids.add(group_id)
        for member in group.get("occurrence_members", []) or []:
            if not isinstance(member, Mapping):
                continue
            key = member.get("occurrence_key") if isinstance(member.get("occurrence_key"), Mapping) else {}
            occurrence_id = _text(key.get("occurrence_id"))
            if occurrence_id:
                occurrence_to_group[occurrence_id] = group_id
    return occurrence_to_group, group_ids


def _projection_records(inputs: Mapping[str, Any], authority_by_id: Mapping[str, Mapping[str, Any]], registry: Mapping[str, Any]) -> dict[str, Any]:
    app = inputs["f1r_applicability"]
    identity = inputs["f1_identity"]
    acceptance = inputs["f1r_acceptance"]
    candidate_members, _ = _confirmed_candidate_members(registry)
    records: list[dict[str, Any]] = []
    for selection in inputs["selection"]:
        key = f1.exact_key(selection)
        occurrence_id = _text(key["occurrence_id"])
        old = acceptance.get(occurrence_id, {})
        old_function = old.get("final_function")
        old_role = old.get("projected_legacy_occurrence_role")
        identity_row = identity.get(occurrence_id, {})
        applicability = app.get(occurrence_id, {})
        semantic_context = _identity_semantic_context(identity_row)
        entity_kind = _entity_kind(applicability, identity_row)
        overlay = authority_by_id.get(occurrence_id)
        blocked = bool(overlay and overlay.get("target_status") != "valid")
        final_function = None if blocked else (overlay.get("narrative_function") if overlay else old_function)
        v2_role = None if blocked or final_function is None else project_legacy_occurrence_role_v2(
            old.get("source_context", {}).get("source_layer"),
            final_function,
            entity_kind,
            semantic_context.get("semantic_kind"),
        )
        flags: list[str] = []
        if semantic_context.get("semantic_kind") == "office" and final_function in {"reference", "participant", "speaker", "addressee"}:
            flags.append("office_semantic_consistency_review")
        if entity_kind == "non_person" and v2_role == "annotation_person":
            flags.append("non_person_person_role_violation")
        records.append({
            "occurrence_key": key,
            "source_layer": old.get("source_context", {}).get("source_layer"),
            "entity_kind": entity_kind,
            "semantic_kind": semantic_context.get("semantic_kind"),
            "historical_f1r_function": old_function,
            "historical_f1r_role": old_role,
            "reviewed_overlay_function": overlay.get("narrative_function") if overlay else None,
            "production_v2_function": final_function,
            "production_v2_role": v2_role,
            "projection_changed": old_role != v2_role,
            "confirmed_candidate_group_id": candidate_members.get(occurrence_id),
            "target_status": overlay.get("target_status") if overlay else "valid_or_unreviewed",
            "flags": flags,
            "candidate_only": True,
            "canonical_write_back": False,
        })
    non_person_violations = [row for row in records if "non_person_person_role_violation" in row["flags"]]
    return {
        "schema": "sfh2-f1rp-compatibility-projection-v2-validation-v1",
        "source_stage": "SFH2.2-F1RP",
        "provider_calls": 0,
        "historical_projection_unchanged": True,
        "record_count": len(records),
        "non_person_annotation_person_violations": len(non_person_violations),
        "candidate_only": True,
        "canonical_write_back": False,
        "records": records,
    }


def _post_review_queue(inputs: Mapping[str, Any], authority_by_id: Mapping[str, Mapping[str, Any]], registry: Mapping[str, Any], projection: Mapping[str, Any]) -> dict[str, Any]:
    trigger_rows = inputs["f1r_trigger"]
    acceptance = inputs["f1r_acceptance"]
    candidate_members, _ = _confirmed_candidate_members(registry)
    records: list[dict[str, Any]] = []
    for selection in inputs["selection"]:
        key = f1.exact_key(selection)
        occurrence_id = _text(key["occurrence_id"])
        trigger = trigger_rows.get(occurrence_id, {})
        acceptance_row = acceptance.get(occurrence_id, {})
        authority = authority_by_id.get(occurrence_id)
        before = [str(value) for value in trigger.get("counterfactual_mandatory_reasons", [])]
        existing_audit = [str(value) for value in trigger.get("counterfactual_audit_only_reasons", [])]
        post: list[str] = []
        audit_only = [
            "resolved_stage_disagreement_only"
            if value == "policy_defined_stage_disagreement"
            else value
            for value in existing_audit
        ]
        removed: list[dict[str, str]] = []

        for reason in before:
            if reason == "new_historical_person_entity" and occurrence_id in candidate_members:
                removed.append({"trigger": reason, "reason": "human-reviewed candidate entity may be reused"})
                if "reviewed_candidate_entity_reuse" not in audit_only:
                    audit_only.append("reviewed_candidate_entity_reuse")
                continue
            if reason == "semantic_audit_candidate" and authority is not None and authority.get("target_status") == "valid":
                removed.append({"trigger": reason, "reason": "human semantic decision is now explicit authority"})
                if "reviewed_semantic_decision" not in audit_only:
                    audit_only.append("reviewed_semantic_decision")
                continue
            if reason == "reason_target_alignment_failure" and authority is not None:
                if authority.get("target_status") == "upstream_mention_review_required":
                    if "upstream_mention_repair_required" not in post:
                        post.append("upstream_mention_repair_required")
                elif authority.get("reason_target_alignment") == "reviewed_drift":
                    removed.append({"trigger": reason, "reason": "human reviewed target drift without semantic replacement"})
                    if "reviewed_target_drift" not in audit_only:
                        audit_only.append("reviewed_target_drift")
                    continue
                else:
                    post.append(reason)
                continue
            if reason == "unsupported_final_projection" and occurrence_id in authority_by_id:
                projection_row = next((row for row in projection["records"] if _text(row["occurrence_key"]["occurrence_id"]) == occurrence_id), {})
                if projection_row.get("production_v2_role") == "other":
                    removed.append({"trigger": reason, "reason": "approved structured compatibility projection v2"})
                    audit_only.append("compatibility_projection_v2_applied")
                    continue
            post.append(reason)

        if authority is not None and authority.get("target_status") == "upstream_mention_review_required":
            if "upstream_mention_repair_required" not in post:
                post.append("upstream_mention_repair_required")
        if authority is not None and authority.get("target_status") == "valid":
            if authority.get("decision_kind") == "non_person_projection_review":
                if "compatibility_projection_v2_applied" not in audit_only:
                    audit_only.append("compatibility_projection_v2_applied")
            if authority.get("reason_target_alignment") == "reviewed_drift" and "reviewed_target_drift" not in audit_only:
                audit_only.append("reviewed_target_drift")
            if "reviewed_semantic_decision" not in audit_only:
                audit_only.append("reviewed_semantic_decision")
        if occurrence_id in candidate_members and "reviewed_candidate_entity_reuse" not in audit_only:
            audit_only.append("reviewed_candidate_entity_reuse")

        post = list(dict.fromkeys(post))
        audit_only = list(dict.fromkeys(audit_only))
        mandatory = bool(post)
        if mandatory:
            status = "mandatory_review"
            review_unit = "occurrence:" + occurrence_id
        elif audit_only:
            status = "audit_only"
            review_unit = None
        else:
            status = "no_review_required"
            review_unit = None
        records.append({
            "occurrence_key": key,
            "current_f1_mandatory": bool(inputs["f1_review_queue"].get(occurrence_id, {}).get("mandatory_review")),
            "f1r_policy_v2_before_human_decisions": bool(trigger.get("counterfactual_mandatory")),
            "pre_human_policy_v2_reasons": before,
            "post_review_mandatory_reasons": post,
            "post_review_audit_only_reasons": audit_only,
            "removed_by_human_promotion": removed,
            "mandatory_review": mandatory,
            "review_status": status,
            "review_unit": review_unit,
            "candidate_entity_group_id": candidate_members.get(occurrence_id),
            "candidate_entity_review_required": False if occurrence_id in candidate_members else ("new_historical_person_entity" in post),
            "identity_status": acceptance_row.get("identity_status"),
            "target_status": authority.get("target_status") if authority else "valid_or_unreviewed",
            "candidate_only": True,
            "canonical_write_back": False,
        })
    mandatory_count = sum(1 for row in records if row["mandatory_review"])
    entity_units = len({row["candidate_entity_group_id"] for row in records if row["candidate_entity_review_required"] and row.get("candidate_entity_group_id")})
    occurrence_units = len({row["review_unit"] for row in records if row["mandatory_review"] and row.get("review_unit")})
    return {
        "schema": "sfh2-f1rp-post-review-queue-v1",
        "source_stage": "SFH2.2-F1RP",
        "provider_calls": 0,
        "current_f1_mandatory_occurrences": sum(1 for row in records if row["current_f1_mandatory"]),
        "f1r_policy_v2_before_human_decisions_mandatory_occurrences": sum(1 for row in records if row["f1r_policy_v2_before_human_decisions"]),
        "post_review_mandatory_occurrences": mandatory_count,
        "post_review_mandatory_occurrence_units": occurrence_units,
        "post_review_entity_review_units": entity_units,
        "post_review_audit_only_occurrences": sum(1 for row in records if row["review_status"] == "audit_only"),
        "post_review_no_review_occurrences": sum(1 for row in records if row["review_status"] == "no_review_required"),
        "candidate_entity_review_units_after_confirmation": entity_units,
        "records": records,
        "candidate_only": True,
        "canonical_write_back": False,
    }


def _post_review_burden(inputs: Mapping[str, Any], queue: Mapping[str, Any], registry: Mapping[str, Any]) -> dict[str, Any]:
    scope = f1.read_json(F1_PREP_ROOT / "production-scope.json", {}) or {}
    scope_count = int(scope.get("total_validated_occurrences", 0))
    current = int(queue["current_f1_mandatory_occurrences"])
    before = int(queue["f1r_policy_v2_before_human_decisions_mandatory_occurrences"])
    post = int(queue["post_review_mandatory_occurrences"])
    current_entity = int(inputs["f1r_burden"].get("pilot_observation", {}).get("current_deduplicated_review_units_observed", 0))
    before_entity = int(inputs["f1r_burden"].get("pilot_observation", {}).get("counterfactual_deduplicated_review_units_observed", 0))
    post_entity = int(queue["post_review_entity_review_units"] + queue["post_review_mandatory_occurrence_units"])
    return {
        "schema": "sfh2-f1rp-post-review-burden-v1",
        "source_stage": "SFH2.2-F1RP",
        "provider_calls": 0,
        "scope_occurrences": scope_count,
        "scope_source": "data/generated/sfh2-f-prep/production-scope.json",
        "pilot_observation": {
            "current_f1_mandatory_occurrences": current,
            "f1r_policy_v2_before_human_decisions_mandatory_occurrences": before,
            "post_review_mandatory_occurrences": post,
            "current_f1_entity_or_occurrence_units": current_entity,
            "f1r_policy_v2_before_human_decisions_entity_or_occurrence_units": before_entity,
            "post_review_entity_or_occurrence_units": post_entity,
            "confirmed_candidate_entity_groups": int(registry.get("group_count", 0)),
        },
        "full_scope_estimate_from_f1_rates_only": {
            "current_f1_mandatory_occurrences": scope_count * current / 30 if scope_count else 0,
            "f1r_policy_v2_before_human_decisions_mandatory_occurrences": scope_count * before / 30 if scope_count else 0,
            "post_review_mandatory_occurrences": scope_count * post / 30 if scope_count else 0,
            "current_f1_entity_or_occurrence_units": scope_count * current_entity / 30 if scope_count else 0,
            "f1r_policy_v2_before_human_decisions_entity_or_occurrence_units": scope_count * before_entity / 30 if scope_count else 0,
            "post_review_entity_or_occurrence_units": scope_count * post_entity / 30 if scope_count else 0,
        },
        "warning": "F1 rates are pilot observations, not a full-corpus semantic or workload guarantee.",
        "candidate_only": True,
        "canonical_write_back": False,
    }


def _upstream_repair(authority_by_id: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    row = authority_by_id["sfh1-mention-55b97afde3e7fb4c074361b8"]
    return {
        "schema": "sfh2-f1rp-upstream-mention-repair-candidates-v1",
        "source_stage": "SFH2.2-F1RP",
        "provider_calls": 0,
        "record_count": 1,
        "records": [{
            "occurrence_key": _copy(row["occurrence_key"]),
            "source_context": _copy(row["source_context"]),
            "reason": row["review_reason"],
            "root_cause": "upstream_mention_target_error",
            "target_status": "upstream_mention_review_required",
            "semantic_promotion_blocked": True,
            "human_approval_required": True,
            "upstream_file_mutation": False,
            "semantic_label": None,
            "candidate_only": True,
            "canonical_write_back": False,
        }],
        "candidate_only": True,
        "canonical_write_back": False,
    }


def _unresolved_items(inputs: Mapping[str, Any], queue: Mapping[str, Any], authority_by_id: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    blocked = {
        _text(row.get("occurrence_id")): row
        for row in inputs["f1r_transport"].get("terminal_identity_blocks", []) or []
        if isinstance(row, Mapping)
    }
    records: list[dict[str, Any]] = []
    for row in queue["records"]:
        if not row["mandatory_review"]:
            continue
        occurrence_id = _text(row["occurrence_key"]["occurrence_id"])
        if occurrence_id in blocked:
            disposition = "transport_blocked_identity"
        elif occurrence_id in authority_by_id and authority_by_id[occurrence_id].get("target_status") == "upstream_mention_review_required":
            disposition = "upstream_target_blocked"
        elif "terminal_boundary_failure" in row["post_review_mandatory_reasons"]:
            disposition = "terminal_boundary_transport_failure"
        elif "degraded_identity_path" in row["post_review_mandatory_reasons"]:
            disposition = "degraded_identity_path_requires_review"
        else:
            disposition = "policy_mandatory_review"
        records.append({
            "occurrence_key": _copy(row["occurrence_key"]),
            "disposition": disposition,
            "post_review_mandatory_reasons": _copy(row["post_review_mandatory_reasons"]),
            "target_status": row.get("target_status"),
            "semantic_label": None,
            "semantic_claim_withheld": True,
            "candidate_only": True,
            "canonical_write_back": False,
        })
    return {
        "schema": "sfh2-f1rp-unresolved-items-v1",
        "source_stage": "SFH2.2-F1RP",
        "provider_calls": 0,
        "record_count": len(records),
        "terminal_identity_block_count": sum(1 for row in records if row["disposition"] == "transport_blocked_identity"),
        "upstream_target_block_count": sum(1 for row in records if row["disposition"] == "upstream_target_blocked"),
        "records": records,
        "candidate_only": True,
        "canonical_write_back": False,
    }


def _transport_handoff(inputs: Mapping[str, Any]) -> dict[str, Any]:
    source = inputs["f1r_transport"]
    invalid = []
    for row in source.get("invalid_payloads", []) or []:
        if not isinstance(row, Mapping):
            continue
        invalid.append({
            key: _copy(row.get(key))
            for key in (
                "occurrence_id", "story_id", "surface", "stage", "request_hash",
                "transport_classification", "root_cause", "root_cause_confidence",
                "recovery_class", "final_identity_resolved", "contract_errors",
                "provider_transport_success",
            )
            if key in row
        })
    terminal = []
    for row in source.get("terminal_identity_blocks", []) or []:
        if not isinstance(row, Mapping):
            continue
        terminal.append({
            "occurrence_id": row.get("occurrence_id"),
            "story_id": row.get("story_id"),
            "surface": row.get("surface"),
            "classification": row.get("classification"),
            "reason": row.get("reason"),
            "recovery_possible_from_stored_f1": row.get("recovery_possible_from_stored_f1"),
        })
    return {
        "schema": "sfh2-f1rp-transport-recovery-handoff-v1",
        "source_stage": "SFH2.2-F1R",
        "future_stage": "SFH2.2-F1RT",
        "provider_calls": 0,
        "replay_performed": False,
        "invalid_payload_count": len(invalid),
        "terminal_identity_block_count": len(terminal),
        "invalid_payloads": invalid,
        "terminal_identity_blocks": terminal,
        "reason": "F1 had four identity structured-output failures and one truncated boundary response; no recovery replay is performed in F1RP.",
        "candidate_only": True,
        "canonical_write_back": False,
    }


def _decision_materialization(authority: Mapping[str, Any], registry: Mapping[str, Any], controls: Mapping[str, Any], inputs: Mapping[str, Any]) -> dict[str, Any]:
    protected = _protected_snapshot()
    return {
        "schema": "sfh2-f1rp-decision-materialization-v1",
        "source_stage": "SFH2.2-F1R",
        "provider_calls": 0,
        "active_gold_mutated": False,
        "active_gold_sha256": f1.file_hash(ACTIVE_GOLD),
        "human_decision_count": authority["record_count"],
        "candidate_entity_group_count": registry["group_count"],
        "reviewed_control_count": controls["record_count"],
        "historical_outputs_rewritten": False,
        "protected_snapshot": {
            "digest": _snapshot_digest(protected),
            "path_hashes": _copy(protected["files"]),
        },
        "records": _copy(authority["records"]),
        "candidate_only": True,
        "canonical_write_back": False,
    }


def _reviewed_entity_decisions(registry: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "schema": "sfh2-f1rp-reviewed-entity-decisions-v1",
        "source_stage": "SFH2.2-F1R",
        "provider_calls": 0,
        "confirmed_candidate_entity_groups": registry["group_count"],
        "occurrence_level_proposals": registry["occurrence_level_proposal_count"],
        "canonical_person_creation": 0,
        "groups": _copy(registry["groups"]),
        "candidate_only": True,
        "canonical_write_back": False,
    }


def _reviewed_semantic_overlay(authority: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "schema": "sfh2-f1rp-reviewed-semantic-overlay-v1",
        "source_stage": "SFH2.2-F1R",
        "provider_calls": 0,
        "overlay_is_not_historical_rewrite": True,
        "active_gold_mutated": False,
        "records": _copy(authority["records"]),
        "candidate_only": True,
        "canonical_write_back": False,
    }


def _policy_manifest(inputs: Mapping[str, Any], policy_docs: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    protected = _protected_snapshot()["files"]
    return {
        "schema": "sfh2-production-policy-v2-manifest",
        "version": "production-policy-v2",
        "status": "APPROVED_POLICY_FROZEN",
        "stage": "SFH2.2-F1RP",
        "provider_calls": 0,
        "approved_by": "human_semantic_review",
        "source_stage": "SFH2.2-F1R",
        "source_policy_candidate": "data/generated/sfh2-f1r/review-policy-v2-candidate.json",
        "source_policy_candidate_sha256": f1.file_hash(F1R_ROOT / "review-policy-v2-candidate.json"),
        "policy_file_hashes": {name: _serialized_file_hash(policy_docs[name]) for name in POLICY_FILES},
        "semantic_v1_status": inputs["semantic_manifest"].get("status"),
        "semantic_v1_manifest_sha256": f1.file_hash(SEMANTIC_ROOT / "manifest.json"),
        "semantic_v1_architecture_sha256": f1.file_hash(SEMANTIC_ROOT / "architecture.json"),
        "identity_manifest_sha256": f1.file_hash(ROOT / "data/frozen/sfh2/identity-v1/manifest.json"),
        "transport_recovery_required_before_f2": True,
        "next_stage": "SFH2.2-F1RT",
        "f2_status": "blocked",
        "no_f2_execution": True,
        "protected_hashes": {
            path: value["sha256"]
            for path, value in protected.items()
            if path in {
                "data/annotation/sfh2-a2o-evaluation-gold.json",
                "data/frozen/sfh2/identity-v1/manifest.json",
                "data/derived/sc1-site.json",
                "data/derived/sc1-current-site.json",
                "data/people.json",
                "data/aliases.json",
                "data/derived/h0c-historical-facts.json",
                "data/derived/person-resolution-effective.json",
            }
        },
        "candidate_only": True,
        "canonical_write_back": False,
    }


def _metrics(inputs: Mapping[str, Any], authority: Mapping[str, Any], registry: Mapping[str, Any], controls: Mapping[str, Any], queue: Mapping[str, Any], projection: Mapping[str, Any], unresolved: Mapping[str, Any], transport: Mapping[str, Any], policy_manifest: Mapping[str, Any], before: Mapping[str, Any], after: Mapping[str, Any]) -> dict[str, Any]:
    protected_hashes = {
        "active_gold": f1.file_hash(ACTIVE_GOLD),
        "identity_manifest": f1.file_hash(ROOT / "data/frozen/sfh2/identity-v1/manifest.json"),
        "sc1_frozen": f1.file_hash(ROOT / "data/derived/sc1-site.json"),
        "sc1_current": f1.file_hash(ROOT / "data/derived/sc1-current-site.json"),
        "people": f1.file_hash(ROOT / "data/people.json"),
        "aliases": f1.file_hash(ROOT / "data/aliases.json"),
        "canonical_historical_facts": f1.file_hash(ROOT / "data/derived/h0c-historical-facts.json"),
        "person_resolution_effective": f1.file_hash(ROOT / "data/derived/person-resolution-effective.json"),
    }
    return {
        "schema": "sfh2-f1rp-metrics-v1",
        "stage": "SFH2.2-F1RP",
        "baseline_commit": BASELINE_COMMIT,
        "head": _git_value("rev-parse", "HEAD"),
        "branch": _git_value("rev-parse", "--abbrev-ref", "HEAD"),
        "provider_calls": 0,
        "human_semantic_decisions_materialized": authority["record_count"],
        "confirmed_candidate_entity_groups": registry["group_count"],
        "candidate_occurrence_proposals": registry["occurrence_level_proposal_count"],
        "reviewed_control_count": controls["record_count"],
        "current_f1_mandatory_occurrences": queue["current_f1_mandatory_occurrences"],
        "f1r_policy_v2_before_human_decisions_mandatory_occurrences": queue["f1r_policy_v2_before_human_decisions_mandatory_occurrences"],
        "post_review_mandatory_occurrences": queue["post_review_mandatory_occurrences"],
        "post_review_entity_review_units": queue["post_review_entity_review_units"],
        "post_review_mandatory_occurrence_units": queue["post_review_mandatory_occurrence_units"],
        "post_review_audit_only_occurrences": queue["post_review_audit_only_occurrences"],
        "transport_invalid_payloads": transport["invalid_payload_count"],
        "terminal_identity_blocks": transport["terminal_identity_block_count"],
        "unresolved_post_review_items": unresolved["record_count"],
        "upstream_target_block_count": unresolved["upstream_target_block_count"],
        "compatibility_projection_v2_records": projection["record_count"],
        "compatibility_projection_v2_changed_records": sum(1 for row in projection["records"] if row["projection_changed"]),
        "compatibility_projection_v2_non_person_violations": projection["non_person_annotation_person_violations"],
        "canonical_person_creation": 0,
        "canonical_writes": 0,
        "alias_mutations": 0,
        "profile_mutations": 0,
        "sc1_mutations": 0,
        "frontend_mutations": 0,
        "active_gold_mutated": False,
        "historical_outputs_rewritten": False,
        "production_policy_v2_approved": True,
        "semantic_v1_frozen": True,
        "transport_recovery_required": True,
        "protected_hashes": protected_hashes,
        "protected_hash_audit": {
            "before_digest": _snapshot_digest(before),
            "after_digest": _snapshot_digest(after),
            "unchanged": before == after,
            "changed_paths": sorted(set(before.get("files", {})) ^ set(after.get("files", {}))) + [
                path for path in sorted(set(before.get("files", {})) & set(after.get("files", {})))
                if before["files"][path] != after["files"][path]
            ],
            "protected_hashes": protected_hashes,
            "protected_path_hashes": _copy(before.get("files", {})),
        },
        "candidate_only": True,
        "canonical_write_back": False,
    }


def _recommendation(queue: Mapping[str, Any], unresolved: Mapping[str, Any], transport: Mapping[str, Any], policy_manifest: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "schema": "sfh2-f1rp-recommendation-v1",
        "recommendation": "sfh2_f1rp_transport_recovery_test_required",
        "next_stage": "SFH2.2-F1RT",
        "provider_calls": 0,
        "f2_status": "blocked",
        "reason": "Human semantic decisions and candidate-level entity authority are materialized, but three terminal identity blocks caused by structured-output failure require bounded transport-recovery qualification before F2.",
        "semantic_v1_status": "frozen_and_qualified",
        "production_policy_v2_status": policy_manifest["status"],
        "human_decisions_complete_for_reviewed_f1_items": True,
        "terminal_identity_blocks": transport["terminal_identity_block_count"],
        "post_review_unresolved_items": unresolved["record_count"],
        "candidate_only": True,
        "canonical_write_back": False,
    }


def _write_doc(documents: Mapping[str, Any]) -> None:
    metrics = documents["metrics.json"]
    queue = documents["post-review-queue.json"]
    text = f"""# SFH2.2-F1RP — Human Decision Promotion & Production Policy Approval

This is an offline authority and policy stage based on the immutable SFH2.2-F1R
acceptance review. It does not rewrite F1/F1R predictions, active Gold, or
canonical data. Provider calls: **0**.

## Materialized decisions

Nine exact-occurrence human decisions were recorded in
`data/annotation/sfh2-f1rp-human-authority.json`. The active A2 Gold remains
unchanged. Eight reviewed production controls were carried forward; `康` is
kept only as an upstream-target-blocked control with no semantic label.

The reviewed decisions are:

- `子野` → `addressee`; the pinned nested occurrence is the recipient of the
  question, while the later reply occurrence is different.
- `堯` → `reference`; it is a temporal anchor inside the biography of 巢父.
- `剌史` and `湘州刺史` → `person_attribute`; office expressions are not
  historical-person identity targets.
- `孔巖` → `reference` and `爰` → `participant`; both A2OVB overrides are
  accepted as reviewed controls.
- `祥` remains `participant`, with reviewed reason-target drift.
- `江南` remains `reference`, with a non-person-compatible legacy fallback of
  `other`.
- `康` remains blocked until the upstream mention annotation is repaired.

The 11 F1R candidate entity groups are confirmed only in
`data/annotation/sfh2-reviewed-candidate-person-registry.json`. They are not
canonical Persons and cannot create canonical records.

## Approved production policy v2

`data/frozen/sfh2/production-policy-v2/` is a new approved policy namespace;
the historical F-prep/F1 policy remains unchanged. Reviewed candidate entity
hits are audit-only for entity reuse. Unresolved adjudication, degraded or
terminal provider paths, uncertain semantics, target drift, unsupported
projection, evidence-integrity failures, and upstream mention repair remain
mandatory review triggers. Boundary overrides and low confidence alone remain
audit-only.

Compatibility projection v2 consumes structured `provenance_layer`,
`narrative_function`, `entity_kind`, and `semantic_kind`. A known non-person
cannot emit the person-specific `annotation_person` role. The historical
`scripts/sfh2_a2o/provenance.py` projector is not changed.

## Queue impact and blocker

The stored F1 queue had {metrics['current_f1_mandatory_occurrences']} mandatory
occurrences. F1R's inactive policy-v2 counterfactual had
{metrics['f1r_policy_v2_before_human_decisions_mandatory_occurrences']}. After
human decisions and reviewed-entity reuse, the approved policy yields
{metrics['post_review_mandatory_occurrences']} mandatory occurrences and
{metrics['post_review_entity_review_units']} unconfirmed entity review units.
The remaining queue is dominated by degraded/terminal transport paths plus the
upstream `康` target and the invalid `剌史` boundary response.

F1's five invalid semantic responses and three terminal identity blocks are
carried into the handoff for **SFH2.2-F1RT**. No transport replay is performed
here, and F2 is blocked until that bounded recovery stage qualifies the failure
path.

## Safety boundary

All outputs remain candidate-only with `canonical_write_back=false`. The
protected snapshot digest is unchanged, and no active Gold, semantic-v1,
historical experiment output, SC1, canonical Person/alias/fact, or frontend
artifact was modified. F1/F1R outputs remain historical evidence rather than
retrospectively rewritten predictions.
"""
    (ROOT / "docs/sfh2-f1rp-human-decision-promotion.md").write_text(text, encoding="utf-8")


def run(output: Path = OUT, *, materialize_repository_overlays: bool = True) -> dict[str, dict[str, Any]]:
    """Build F1RP documents without provider/API access."""

    inputs = _load_inputs()
    before = _protected_snapshot()
    authority, authority_by_id = _human_authority(inputs)
    registry = _candidate_registry(inputs)
    controls = _controls(authority)
    policy_docs: dict[str, dict[str, Any]] = {
        "review-routing-policy.json": _review_routing_policy(),
        "compatibility-projection-policy.json": _compatibility_projection_policy(),
        "semantic-consistency-policy.json": _semantic_consistency_policy(),
    }
    policy_manifest = _policy_manifest(inputs, policy_docs)
    projection = _projection_records(inputs, authority_by_id, registry)
    queue = _post_review_queue(inputs, authority_by_id, registry, projection)
    burden = _post_review_burden(inputs, queue, registry)
    upstream = _upstream_repair(authority_by_id)
    unresolved = _unresolved_items(inputs, queue, authority_by_id)
    transport = _transport_handoff(inputs)
    decision_materialization = _decision_materialization(authority, registry, controls, inputs)
    reviewed_entities = _reviewed_entity_decisions(registry)
    reviewed_overlay = _reviewed_semantic_overlay(authority)
    after = _protected_snapshot()
    policy_manifest = _policy_manifest(inputs, policy_docs)
    metrics = _metrics(inputs, authority, registry, controls, queue, projection, unresolved, transport, policy_manifest, before, after)
    recommendation = _recommendation(queue, unresolved, transport, policy_manifest)

    documents: dict[str, dict[str, Any]] = {
        "decision-materialization.json": decision_materialization,
        "reviewed-entity-decisions.json": reviewed_entities,
        "reviewed-semantic-overlay.json": reviewed_overlay,
        "post-review-queue.json": queue,
        "post-review-burden.json": burden,
        "compatibility-projection-v2-validation.json": projection,
        "upstream-mention-repair-candidates.json": upstream,
        "unresolved-f1-items.json": unresolved,
        "transport-recovery-handoff.json": transport,
        "metrics.json": metrics,
        "recommendation.json": recommendation,
    }
    for name, document in documents.items():
        f1.write_json(output / name, document)

    if materialize_repository_overlays:
        f1.write_json(ROOT / "data/annotation/sfh2-f1rp-human-authority.json", authority)
        f1.write_json(ROOT / "data/annotation/sfh2-reviewed-candidate-person-registry.json", registry)
        f1.write_json(ROOT / "data/annotation/sfh2-f1-reviewed-controls.json", controls)
        for name, document in policy_docs.items():
            f1.write_json(POLICY_ROOT / name, document)
        f1.write_json(POLICY_ROOT / "manifest.json", policy_manifest)
        _write_doc(documents)
        # Recompute the safety assertion after all new overlay files exist.
        final = _protected_snapshot()
        if before != final:
            raise RuntimeError("f1rp_protected_artifact_mutation:" + ",".join(sorted(set(before) ^ set(final))))
        metrics["protected_hash_audit"] = {
            "before_digest": _snapshot_digest(before),
            "after_digest": _snapshot_digest(final),
            "unchanged": before == final,
            "changed_paths": [],
            "protected_hashes": metrics["protected_hashes"],
            "protected_path_hashes": _copy(before.get("files", {})),
        }
        f1.write_json(output / "metrics.json", metrics)
    return documents
