#!/usr/bin/env python3
"""Validate the offline SFH2.2-A2OT audit and its read-only boundary."""

from __future__ import annotations

import re
from pathlib import Path
import subprocess
import sys
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

from sfh2_a2ot.common import (  # noqa: E402
    A2O_PROTECTED_FILES,
    BASELINE_COMMIT,
    OUT,
    PROTECTED_HASHES,
    file_hash,
    load_frozen_bundle,
    read_json,
)
from sfh2_a2ot.taxonomy import NARRATIVE_FUNCTIONS, PRECEDENCE  # noqa: E402


OUTPUT_FILES = (
    "taxonomy-definition.json",
    "gold-taxonomy-audit.json",
    "gold-review-candidates.json",
    "function-consistency-matrix.json",
    "five-error-review.json",
    "metrics.json",
    "recommendation.json",
    "validation-summary.json",
)


def _git_bytes(revision: str, path: str) -> bytes:
    completed = subprocess.run(
        ["git", "show", f"{revision}:{path}"],
        cwd=ROOT,
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if completed.returncode:
        raise RuntimeError(f"git_show_failed:{path}")
    return completed.stdout


def _error(errors: list[str], message: str) -> None:
    errors.append(message)


def _walk_for_flags(value: Any, path: str = "$") -> list[str]:
    found: list[str] = []
    if isinstance(value, Mapping):
        for key, child in value.items():
            key_text = str(key)
            if key_text in {"canonical_write_back", "candidate_only"}:
                if key_text == "canonical_write_back" and child is not False:
                    found.append(f"{path}.{key_text}=not_false")
                if key_text == "candidate_only" and child is not True:
                    found.append(f"{path}.{key_text}=not_true")
            found.extend(_walk_for_flags(child, f"{path}.{key_text}"))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            found.extend(_walk_for_flags(child, f"{path}[{index}]"))
    return found


def validate() -> list[str]:
    errors: list[str] = []
    if subprocess.run(["git", "merge-base", "--is-ancestor", BASELINE_COMMIT, "HEAD"], cwd=ROOT, check=False).returncode:
        _error(errors, "baseline_not_ancestor")

    missing = [name for name in OUTPUT_FILES if not (OUT / name).is_file()]
    if missing:
        _error(errors, f"missing_outputs:{','.join(missing)}")
        return errors

    bundle = load_frozen_bundle()
    audit = read_json(OUT / "gold-taxonomy-audit.json", {}) or {}
    candidates = read_json(OUT / "gold-review-candidates.json", {}) or {}
    matrix = read_json(OUT / "function-consistency-matrix.json", {}) or {}
    metrics = read_json(OUT / "metrics.json", {}) or {}
    recommendation = read_json(OUT / "recommendation.json", {}) or {}
    validation = read_json(OUT / "validation-summary.json", {}) or {}
    taxonomy = read_json(OUT / "taxonomy-definition.json", {}) or {}

    records = audit.get("records") if isinstance(audit.get("records"), list) else []
    selected_ids = [str(row.get("case_id")) for row in bundle["selection"]]
    audit_ids = [str(row.get("case_id")) for row in records]
    if audit_ids != selected_ids:
        _error(errors, "audit_case_order_or_membership_mismatch")
    if len(records) != 26:
        _error(errors, f"audit_case_count:{len(records)}")
    if audit.get("gold_mutated") is not False:
        _error(errors, "audit_claims_gold_mutated")
    if audit.get("taxonomy_consistent_count") != 25:
        _error(errors, f"taxonomy_consistent_count:{audit.get('taxonomy_consistent_count')}")
    for row in records:
        target = row.get("target_span") if isinstance(row.get("target_span"), Mapping) else {}
        if not target.get("offsets_valid") or target.get("matched_source_text") != target.get("exact_span"):
            _error(errors, f"target_span_invalid:{row.get('case_id')}")
        target_evidence = row.get("target_evidence") if isinstance(row.get("target_evidence"), Mapping) else {}
        if row.get("provenance_layer") != target_evidence.get("source_layer"):
            _error(errors, f"provenance_not_derived_from_target_evidence:{row.get('case_id')}")
        gold = row.get("current_gold") if isinstance(row.get("current_gold"), Mapping) else {}
        function = gold.get("expected_narrative_function")
        if function not in NARRATIVE_FUNCTIONS:
            _error(errors, f"unknown_gold_function:{row.get('case_id')}:{function}")
        if row.get("candidate_only") is not True or row.get("canonical_write_back") is not False:
            _error(errors, f"unsafe_audit_boundary:{row.get('case_id')}")

    candidate_rows = candidates.get("records") if isinstance(candidates.get("records"), list) else []
    if len(candidate_rows) != 1 or candidate_rows[0].get("case_id") != "sfh2-a0r-l-challenge-c07bd51ac298529ddbc6":
        _error(errors, "expected_one_human_review_candidate_for_summon_occurrence")
    if candidates.get("gold_mutated") is not False or candidates.get("candidate_only") is not True:
        _error(errors, "candidate_artifact_boundary_invalid")
    for row in candidate_rows:
        if row.get("human_review_required") is not True or row.get("gold_mutation_performed") is not False:
            _error(errors, f"candidate_review_metadata_invalid:{row.get('case_id')}")
        proposed = row.get("proposed_label")
        if not isinstance(proposed, Mapping) or set(proposed) != {"narrative_function", "legacy_occurrence_role"}:
            _error(errors, f"candidate_label_shape_invalid:{row.get('case_id')}")

    if taxonomy.get("functions") != list(NARRATIVE_FUNCTIONS) or taxonomy.get("precedence") != PRECEDENCE:
        _error(errors, "taxonomy_definition_drift")
    if taxonomy.get("semantic_guidance_not_runtime_rules") is not True or taxonomy.get("no_surface_specific_logic") is not True:
        _error(errors, "taxonomy_boundary_metadata_missing")
    if matrix.get("latent_inconsistency_findings") != []:
        _error(errors, "unexpected_latent_inconsistency_findings")
    if recommendation.get("recommendation") != "sfh2_occurrence_gold_review_required":
        _error(errors, f"recommendation:{recommendation.get('recommendation')}")
    if recommendation.get("next_stage") != "SFH2.2-A2OR":
        _error(errors, "wrong_next_stage")
    if validation.get("provider_calls") != 0 or recommendation.get("provider_calls") != 0:
        _error(errors, "provider_calls_not_zero")

    # The A2O inputs must be byte-identical to their frozen baseline.  This
    # includes the Gold file: A2OT emits review candidates but never promotes
    # one.
    for path in A2O_PROTECTED_FILES:
        if (ROOT / path).read_bytes() != _git_bytes(BASELINE_COMMIT, path):
            _error(errors, f"a2o_input_changed:{path}")
    for path, expected_hash in PROTECTED_HASHES.items():
        if not (ROOT / path).is_file() or file_hash(ROOT / path) != expected_hash:
            _error(errors, f"protected_hash:{path}")

    # No transport implementation is reachable from the A2OT runtime.  The
    # Chinese wording in the five-case audit is descriptive review evidence;
    # reject only executable surface-based branching patterns.
    forbidden_runtime = re.compile(r"(?:surface\s*(?:==|!=|in\b)|exact_span\s*(?:==|!=|in\b))")
    for path in (ROOT / "scripts" / "sfh2_a2ot").glob("*.py"):
        source = path.read_text(encoding="utf-8")
        if any(token in source for token in ("DEEPSEEK_API_KEY", "api.deepseek.com", "requests.", "urllib.")):
            _error(errors, f"provider_access_in_a2ot:{path.name}")
        if forbidden_runtime.search(source):
            _error(errors, f"surface_specific_branch:{path.name}")

    for name in OUTPUT_FILES:
        document = read_json(OUT / name, {}) or {}
        for flag in _walk_for_flags(document):
            _error(errors, f"unsafe_output_boundary:{name}:{flag}")
    return errors


def main() -> int:
    errors = validate()
    if errors:
        print("SFH2.2-A2OT validation failed")
        print("\n".join(errors))
        return 1
    print("SFH2.2-A2OT validation passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
