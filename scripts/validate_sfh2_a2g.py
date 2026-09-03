#!/usr/bin/env python3
"""Validate the offline SFH2.2-A2G Gold/ontology audit.

The validator is intentionally evaluation-only.  It checks that the audit
was derived from the frozen A0/A2/A2R inputs, that the corrected metrics are
structural, and that no provider or historical-data mutation is represented
by the new compact artifacts.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data/generated/sfh2-a2g"
GOLD_PATH = ROOT / "data/annotation/sfh2-a0-evaluation-gold.json"
SELECTION_PATH = ROOT / "data/annotation/sfh2-a0-selection.json"
PACKETS_PATH = ROOT / "data/generated/sfh2-a2/case-packets.json"
A2R_ROOT = ROOT / "data/generated/sfh2-a2r"
BASELINE_COMMIT = "57af9d9bb4b418b15cc9b5aff7f4b2390d8c7608"
SELECTION_HASH = "b8162d9d470c6359c67a8ed31aa31ef82149c12d92dd9a694b62327fc204bbc3"
FROZEN_SC1_SHA256 = "cc82c6738fcbf4fc14c12005a459048e71ce329492867d0910562fc6fdfda0d8"
CURRENT_SC1_SHA256 = "b916530264285dd7fa1d2e27a7a1dff8cd2ed794dfb3b84985881f8f209d8f6a"

REQUIRED_OUTPUTS = (
    "architecture-freeze.json",
    "gold-ontology-audit.json",
    "gold-review-candidates.json",
    "occurrence-role-audit.json",
    "disagreement-taxonomy.json",
    "metrics.json",
    "recommendation.json",
    "input-hashes.json",
)


def load_json(path: Path, default: Any = None) -> Any:
    if not path.is_file():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def text(value: Any) -> str:
    return str(value or "").strip()


def _record_map(document: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    return {
        text(row.get("case_id")): row
        for row in document.get("records", []) or []
        if isinstance(row, Mapping) and text(row.get("case_id"))
    }


def _frozen_input_hashes() -> dict[str, str]:
    paths = [
        GOLD_PATH,
        SELECTION_PATH,
        PACKETS_PATH,
        ROOT / "data/generated/sfh2-a2/historian-a-cache-index.json",
        ROOT / "data/generated/sfh2-a2/historian-b-results.json",
        ROOT / "data/generated/sfh2-a2/final-results.json",
        A2R_ROOT / "regression-evaluation.json",
        A2R_ROOT / "selection-matrix.json",
        A2R_ROOT / "ab-comparison.json",
        A2R_ROOT / "final-results.json",
        ROOT / "data/derived/sc1-site.json",
        ROOT / "data/derived/sc1-current-site.json",
        ROOT / "site/src/generated/sc1-site.json",
        ROOT / "site/src/generated/sc1-current-site.json",
    ]
    return {
        str(path.relative_to(ROOT)): file_hash(path)
        for path in paths
        if path.is_file()
    }


def _source_ids(packet: Mapping[str, Any]) -> set[str]:
    return {
        text(row.get("evidence_id"))
        for row in packet.get("source_evidence", []) or []
        if isinstance(row, Mapping) and text(row.get("evidence_id"))
    }


def _case_ids(selection: Mapping[str, Any]) -> set[str]:
    return {
        text(row.get("case_id"))
        for row in selection.get("cases", []) or []
        if isinstance(row, Mapping) and text(row.get("case_id"))
    }


def _provider_value_errors(value: Any, path: str = "$") -> list[str]:
    """Detect nonzero provider-call markers in newly generated outputs."""

    errors: list[str] = []
    if isinstance(value, Mapping):
        for key, child in value.items():
            child_path = f"{path}.{key}"
            if key in {"provider_calls", "new_provider_calls", "provider_attempts"}:
                if isinstance(child, (int, float)) and child != 0:
                    errors.append(f"provider_calls_nonzero:{child_path}")
            errors.extend(_provider_value_errors(child, child_path))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            errors.extend(_provider_value_errors(child, f"{path}[{index}]"))
    return errors


def validate(*, require_outputs: bool = True) -> dict[str, Any]:
    errors: list[str] = []
    selection = load_json(SELECTION_PATH, {}) or {}
    gold = load_json(GOLD_PATH, {}) or {}
    packets_doc = load_json(PACKETS_PATH, {}) or {}
    a2r_evaluation = load_json(A2R_ROOT / "regression-evaluation.json", {}) or {}
    comparison = load_json(A2R_ROOT / "ab-comparison.json", {}) or {}

    selection_cases = selection.get("cases", []) or []
    selection_ids = _case_ids(selection)
    if len(selection_cases) != 20 or len(selection_ids) != 20:
        errors.append("frozen_selection_not_20")
    if selection.get("selection_hash") != SELECTION_HASH:
        errors.append("selection_hash_mismatch")

    output_docs = {
        name: load_json(OUT / name, {}) or {}
        for name in REQUIRED_OUTPUTS
    }
    if require_outputs:
        errors.extend(
            f"missing_output:{name}"
            for name in REQUIRED_OUTPUTS
            if not (OUT / name).is_file()
        )

    architecture = output_docs["architecture-freeze.json"]
    if architecture:
        if architecture.get("baseline_commit") != BASELINE_COMMIT:
            errors.append("baseline_commit_mismatch")
        if architecture.get("mode") != "offline_evaluation_only":
            errors.append("not_offline_only")
        if architecture.get("provider_calls") != 0:
            errors.append("architecture_provider_calls_nonzero")
        if architecture.get("gold_in_provider_prompt") is not False:
            errors.append("gold_prompt_boundary_missing")
        if architecture.get("identity_equivalence_inferred_by_python") is not False:
            errors.append("python_identity_inference_not_prohibited")
        if architecture.get("selection_hash") != SELECTION_HASH:
            errors.append("architecture_selection_hash_mismatch")
        if architecture.get("selection_case_count") != 20:
            errors.append("architecture_selection_count_mismatch")

    input_hash_doc = output_docs["input-hashes.json"]
    recorded_hashes = input_hash_doc.get("files", {}) if isinstance(input_hash_doc, Mapping) else {}
    if input_hash_doc and input_hash_doc.get("selection_hash") != SELECTION_HASH:
        errors.append("input_hash_selection_mismatch")
    if isinstance(recorded_hashes, Mapping):
        for relative, expected in recorded_hashes.items():
            path = ROOT / relative
            if not path.is_file():
                errors.append(f"protected_input_missing:{relative}")
            elif file_hash(path) != expected:
                errors.append(f"protected_input_changed:{relative}")
    if recorded_hashes and recorded_hashes != _frozen_input_hashes():
        errors.append("frozen_input_hash_inventory_changed")

    for relative, expected in {
        "data/derived/sc1-site.json": FROZEN_SC1_SHA256,
        "data/derived/sc1-current-site.json": CURRENT_SC1_SHA256,
        "site/src/generated/sc1-site.json": FROZEN_SC1_SHA256,
        "site/src/generated/sc1-current-site.json": CURRENT_SC1_SHA256,
    }.items():
        path = ROOT / relative
        if not path.is_file() or file_hash(path) != expected:
            errors.append(f"sc1_protected_hash_mismatch:{relative}")

    gold_audit = output_docs["gold-ontology-audit.json"]
    audits = gold_audit.get("records", []) if isinstance(gold_audit, Mapping) else []
    if len(audits) != 20:
        errors.append("gold_audit_not_20")
    if isinstance(gold_audit, Mapping) and gold_audit.get("gold_mutated") is not False:
        errors.append("gold_mutation_marker")
    if any(
        isinstance(row, Mapping) and row.get("replacement_historical_answer") is not None
        for row in audits
    ):
        errors.append("replacement_answer_in_audit")

    packet_map = {
        text(row.get("case_id")): row.get("packet", {})
        for row in packets_doc.get("packets", []) or []
        if isinstance(row, Mapping) and row.get("cohort") == "regression"
    }
    audit_ids = {
        text(row.get("case_id"))
        for row in audits
        if isinstance(row, Mapping)
    }
    if audit_ids != selection_ids:
        errors.append("gold_audit_case_set_mismatch")
    for row in audits:
        if not isinstance(row, Mapping):
            continue
        case_id = text(row.get("case_id"))
        packet = packet_map.get(case_id, {})
        valid_source_ids = _source_ids(packet if isinstance(packet, Mapping) else {})
        for evidence_id in row.get("source_context", {}).get("source_evidence", []) or []:
            if not isinstance(evidence_id, Mapping):
                continue
            value = text(evidence_id.get("evidence_id"))
            if value and value not in valid_source_ids:
                errors.append(f"source_evidence_not_in_frozen_packet:{case_id}:{value}")

    role_audit = output_docs["occurrence-role-audit.json"]
    if role_audit.get("gold_role_case_count") != 6:
        errors.append("role_case_count_mismatch")
    if role_audit.get("gold_mutated") is not False:
        errors.append("role_gold_mutation_marker")

    taxonomy = output_docs["disagreement-taxonomy.json"]
    if taxonomy.get("total_comparisons") != 40:
        errors.append("comparison_count_mismatch")
    if taxonomy.get("substantive_disagreement_count") != 33:
        errors.append("substantive_disagreement_count_mismatch")
    requested = taxonomy.get("requested_buckets", {})
    expected_buckets = {
        "identity_or_semantic_kind_critical": 13,
        "occurrence_role_critical": 6,
        "discourse_or_relation_only": 11,
        "contract_validity_critical": 3,
        "metadata_only_difference_within_substantive": 0,
    }
    if requested != expected_buckets:
        errors.append("disagreement_taxonomy_bucket_mismatch")
    if taxonomy.get("identity_equivalence_inferred_by_python") is not False:
        errors.append("taxonomy_python_identity_inference")

    metrics = output_docs["metrics.json"]
    if metrics.get("provider_calls") != 0 or metrics.get("provider_or_network_used") is not False:
        errors.append("metrics_provider_boundary")
    if metrics.get("joint_identity_failure_count") != 1:
        errors.append("joint_identity_failure_count_mismatch")
    frozen_eval_rows = _record_map(a2r_evaluation)
    recomputed_joint = 0
    for row in frozen_eval_rows.values():
        if row.get("historical_identity_evaluable") is True:
            a = row.get("historian_a", {})
            b = row.get("historian_b", {})
            if (
                isinstance(a, Mapping)
                and isinstance(b, Mapping)
                and a.get("identity_correct") is False
                and b.get("identity_correct") is False
            ):
                recomputed_joint += 1
    if recomputed_joint != metrics.get("joint_identity_failure_count"):
        errors.append("joint_identity_not_reproducible")
    if metrics.get("a2r_substantive_disagreement_count") != 33:
        errors.append("metrics_substantive_count_mismatch")
    if metrics.get("gold_ontology_boundary_conflict_count") != 1:
        errors.append("boundary_conflict_count_mismatch")

    recommendation = output_docs["recommendation.json"]
    if recommendation.get("recommendation") != "gold_review_required":
        errors.append("recommendation_not_gold_review_required")
    if recommendation.get("human_gold_promotion_required") is not True:
        errors.append("human_gold_review_boundary_missing")
    if recommendation.get("gold_mutated") is not False:
        errors.append("recommendation_gold_mutation_marker")

    for name, document in output_docs.items():
        errors.extend(
            f"{name}:{error}"
            for error in _provider_value_errors(document)
        )

    # The generator is deliberately a pure offline reader.  This lightweight
    # source audit guards against accidentally turning the evaluation script
    # into a provider client in a later edit.
    generator = ROOT / "scripts/run_sfh2_a2g.py"
    if generator.is_file():
        source = generator.read_text(encoding="utf-8")
        for forbidden in ("requests", "urllib", "httpx", "openai", "DEEPSEEK_API_KEY"):
            if forbidden in source:
                errors.append(f"offline_generator_network_dependency:{forbidden}")

    return {
        "schema": "sfh2-a2g-validation-v1",
        "valid": not errors,
        "errors": sorted(set(errors)),
        "baseline_commit": BASELINE_COMMIT,
        "selection_hash": SELECTION_HASH,
        "provider_calls": 0,
        "gold_mutated": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--preflight",
        action="store_true",
        help="validate frozen inputs/contracts without requiring generated outputs",
    )
    args = parser.parse_args()
    result = validate(require_outputs=not args.preflight)
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if result["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
