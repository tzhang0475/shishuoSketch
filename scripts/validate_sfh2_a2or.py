#!/usr/bin/env python3
"""Validate the SFH2.2-A2OR Gold promotion and live rerun contract."""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

from sfh2_a0r.contracts import validate_deepseek_strict_schema  # noqa: E402
from sfh2_a2or.common import (  # noqa: E402
    A2O_ROOT,
    A2OT_ROOT,
    BASELINE_COMMIT,
    GOLD_PATH,
    OUT,
    by_case,
    file_hash,
    load_frozen_a2o,
    old_gold_map,
    read_json,
    stable_hash,
    text,
)
from sfh2_a2or.contracts import occurrence_function_tool  # noqa: E402
from sfh2_a2or.pipeline import _case_packets_document, _selection_verification  # noqa: E402
from sfh2_a2or.prompt import HISTORIAN_SYSTEM, provider_payload  # noqa: E402


REQUIRED_OUTPUTS = (
    "architecture.json",
    "selection-verification.json",
    "case-packets.json",
    "occurrence-results.json",
    "projected-legacy-roles.json",
    "evaluation.json",
    "paired-comparison.json",
    "known-error-recovery.json",
    "regression-audit.json",
    "confusion-matrix.json",
    "error-analysis.json",
    "metrics.json",
    "recommendation.json",
    "transport.json",
    "storage-safety-audit.json",
    "validation-summary.json",
    "clarified-occurrence-semantics.md",
)

PROTECTED_A2O_PATHS = tuple(
    path for path in A2O_ROOT.glob("*") if path.is_file() and path.name != "replays"
)
PROTECTED_A2OT_PATHS = tuple(path for path in A2OT_ROOT.glob("*") if path.is_file())
OLD_GOLD_SHA256 = "b9076bf6bf82e86f91762d1bb2dd0f761fb7a4593a0d224d18162e931a1c5941"
FROZEN_SC1_SHA256 = "cc82c6738fcbf4fc14c12005a459048e71ce329492867d0910562fc6fdfda0d8"
CURRENT_SC1_SHA256 = "b916530264285dd7fa1d2e27a7a1dff8cd2ed794dfb3b84985881f8f209d8f6a"
IDENTITY_MANIFEST_SHA256 = "f60e4eb84c5af10d644ac09dbcbdfba93cc435660868c3e38486563604dcc95e"


def _git_bytes(revision: str, path: str) -> bytes | None:
    completed = subprocess.run(["git", "show", f"{revision}:{path}"], cwd=ROOT, check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    return completed.stdout if completed.returncode == 0 else None


def _walk_flags(value: Any, path: str = "$") -> list[str]:
    errors: list[str] = []
    if isinstance(value, Mapping):
        for key, child in value.items():
            child_path = f"{path}.{key}"
            if key == "candidate_only" and child is not True:
                errors.append(f"{child_path}=not_true")
            if key == "canonical_write_back" and child is not False:
                errors.append(f"{child_path}=not_false")
            errors.extend(_walk_flags(child, child_path))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            errors.extend(_walk_flags(child, f"{path}[{index}]"))
    return errors


def validate() -> dict[str, Any]:
    errors: list[str] = []
    if subprocess.run(["git", "merge-base", "--is-ancestor", BASELINE_COMMIT, "HEAD"], cwd=ROOT, check=False).returncode:
        errors.append("baseline_not_ancestor")

    missing = [name for name in REQUIRED_OUTPUTS if not (OUT / name).is_file()]
    if missing:
        errors.append("missing_outputs:" + ",".join(missing))
        return {"schema": "sfh2-a2or-validator-v1", "valid": False, "errors": errors}

    bundle = load_frozen_a2o()
    architecture = read_json(OUT / "architecture.json", {}) or {}
    selection = read_json(OUT / "selection-verification.json", {}) or {}
    packets = read_json(OUT / "case-packets.json", {}) or {}
    results_doc = read_json(OUT / "occurrence-results.json", {}) or {}
    evaluation = read_json(OUT / "evaluation.json", {}) or {}
    paired = read_json(OUT / "paired-comparison.json", {}) or {}
    transport = read_json(OUT / "transport.json", {}) or {}
    recommendation = read_json(OUT / "recommendation.json", {}) or {}
    authority = read_json(ROOT / "data/annotation/sfh2-a2or-human-semantic-authority.json", {}) or {}
    gold_document = read_json(GOLD_PATH, {}) or {}

    expected_ids = [text(row.get("case_id")) for row in bundle["selections"]]
    packet_rows = packets.get("packets", []) if isinstance(packets.get("packets"), list) else []
    result_rows = results_doc.get("records", []) if isinstance(results_doc.get("records"), list) else []
    eval_rows = evaluation.get("records", []) if isinstance(evaluation.get("records"), list) else []
    if [text(row.get("case_id")) for row in packet_rows] != expected_ids:
        errors.append("packet_case_order_mismatch")
    if [text(row.get("case_id")) for row in result_rows] != expected_ids:
        errors.append("result_case_order_mismatch")
    if [text(row.get("case_id")) for row in eval_rows] != expected_ids:
        errors.append("evaluation_case_order_mismatch")
    if architecture.get("case_count") != 26 or selection.get("case_count") != 26:
        errors.append("case_count_not_26")
    if selection.get("selection_hash") != bundle["selection_document"].get("selection_hash"):
        errors.append("selection_hash_changed")
    if selection.get("packet_hashes") != _selection_verification(bundle).get("packet_hashes"):
        errors.append("packet_hashes_changed")
    if selection.get("gold_used_for_selection") is not False:
        errors.append("gold_used_for_selection")

    tool = occurrence_function_tool()
    if validate_deepseek_strict_schema(tool["function"]["parameters"]):
        errors.append("strict_schema_invalid")
    if tool["function"]["name"] != "submit_sfh2_a2or_occurrence_function_v2":
        errors.append("wrong_function_name")
    if architecture.get("model_config", {}).get("prompt_version") != "sfh2-a2or-occurrence-function-historian-v2":
        errors.append("prompt_version_missing")
    if architecture.get("model_config", {}).get("model") != "deepseek-v4-flash":
        errors.append("model_config_changed")
    if architecture.get("model_config", {}).get("temperature") != 0 or architecture.get("model_config", {}).get("thinking") != {"type": "disabled"}:
        errors.append("sampling_config_changed")
    if architecture.get("same_evidence_packets") is not True or architecture.get("identity_is_frozen") is not True:
        errors.append("frozen_input_boundary_missing")

    encoded_packets = json.dumps(packets, ensure_ascii=False, sort_keys=True)
    for forbidden in ("expected_narrative_function", "expected_legacy_occurrence_role", "review_status"):
        if forbidden in encoded_packets:
            errors.append("gold_leak_in_packets:" + forbidden)
    for row in packet_rows:
        packet = row.get("packet") if isinstance(row.get("packet"), Mapping) else {}
        encoded_provider = json.dumps(provider_payload(packet), ensure_ascii=False, sort_keys=True)
        if any(token in encoded_provider for token in ("expected_narrative_function", "expected_legacy_occurrence_role", "review_status")):
            errors.append("gold_leak_in_provider_payload:" + text(row.get("case_id")))
    for forbidden in ("宣武", "齊桓公", "滔", "嘏", "王師", "薛瑩", "字景真", "expected_narrative_function"):
        if forbidden in HISTORIAN_SYSTEM:
            errors.append("gold_case_text_in_v2_prompt:" + forbidden)

    if len(result_rows) != 26 or sum(row.get("valid") is True for row in result_rows) != 26:
        errors.append("valid_result_count_not_26")
    for row in result_rows:
        occurrence = row.get("occurrence_result")
        if isinstance(occurrence, Mapping):
            if set(occurrence) != {"case_id", "narrative_function", "confidence", "supporting_evidence_ids", "reason_summary"}:
                errors.append("identity_or_extra_output_fields:" + text(row.get("case_id")))
        if row.get("identity_preserved") is not True or row.get("candidate_only") is not True or row.get("canonical_write_back") is not False:
            errors.append("result_safety_boundary:" + text(row.get("case_id")))

    if transport.get("schema_probe_calls") != 1 or transport.get("case_calls") != 26 or transport.get("provider_calls") != 27:
        errors.append("provider_call_count_invalid")
    if transport.get("provider_attempts") != 27:
        errors.append("provider_attempt_count_invalid")
    if transport.get("provider_failures") != 0 or transport.get("invalid_payloads") != 0 or transport.get("retries") != 0:
        errors.append("transport_failures_or_retries_present")
    if (OUT / "raw-api").exists():
        errors.append("raw_provider_payload_under_output")

    # The active Gold is the one explicitly permitted mutation.  Compare
    # record semantics with the immutable A2OT audit witness, not with model
    # output and not with string similarity.
    active_gold = by_case(gold_document)
    previous_gold = old_gold_map(bundle)
    changed = [case_id for case_id in expected_ids if active_gold.get(case_id) != previous_gold.get(case_id)]
    if changed != ["sfh2-a0r-l-challenge-c07bd51ac298529ddbc6"]:
        errors.append("gold_substantive_mutation_set_invalid")
    if file_hash(GOLD_PATH) != authority.get("new_gold_sha256"):
        errors.append("authority_new_gold_hash_invalid")
    if authority.get("previous_gold_sha256") != OLD_GOLD_SHA256:
        errors.append("authority_previous_gold_hash_invalid")
    if authority.get("substantive_gold_mutation_count") != 1 or authority.get("review_status") != "reviewed":
        errors.append("human_authority_metadata_invalid")
    record = authority.get("records", [{}])[0] if isinstance(authority.get("records"), list) and authority.get("records") else {}
    if record.get("source_start") != 8 or record.get("source_end") != 10 or record.get("reviewed_gold", {}).get("narrative_function") != "participant":
        errors.append("reviewed_gold_boundary_invalid")

    if evaluation.get("metrics", {}).get("provenance_accuracy", {}).get("accuracy") != 1.0:
        errors.append("provenance_not_100_percent")
    if evaluation.get("metrics", {}).get("identity_preservation", {}).get("accuracy") != 1.0:
        errors.append("identity_not_preserved")
    if recommendation.get("recommendation") != "sfh2_occurrence_model_quality_insufficient":
        errors.append("recommendation_does_not_match_frozen_result")
    if paired.get("regression_count") != 2:
        errors.append("paired_regression_count_unexpected")

    # A2O and A2OT generated experiment bytes are historical inputs.  The
    # Gold revision is deliberately excluded from this byte-identity check.
    for path in (*PROTECTED_A2O_PATHS, *PROTECTED_A2OT_PATHS):
        relative = str(path.relative_to(ROOT))
        revision = "3d9d45e91c1746e74704d9e48537cdb2625a0a8" if path in PROTECTED_A2OT_PATHS else "1ac588e8ae54bd4745f3d091360d02e65e3f55ac"
        historical = _git_bytes(revision, relative)
        if historical is not None and path.read_bytes() != historical:
            errors.append("historical_artifact_changed:" + relative)

    forbidden_runtime = re.compile(r"surface\s*(?:==|!=|in\b)|exact_span\s*(?:==|!=|in\b)")
    for path in (ROOT / "scripts/sfh2_a2or").glob("*.py"):
        source = path.read_text(encoding="utf-8")
        if forbidden_runtime.search(source):
            errors.append("surface_specific_runtime_rule:" + path.name)
    for name in REQUIRED_OUTPUTS:
        document = read_json(OUT / name, {}) if name.endswith(".json") else {}
        for flag in _walk_flags(document):
            errors.append(f"unsafe_output_boundary:{name}:{flag}")

    protected = {
        "data/derived/sc1-site.json": FROZEN_SC1_SHA256,
        "data/derived/sc1-current-site.json": CURRENT_SC1_SHA256,
        "data/frozen/sfh2/identity-v1/manifest.json": IDENTITY_MANIFEST_SHA256,
    }
    for relative, expected_hash in protected.items():
        if not (ROOT / relative).is_file() or file_hash(ROOT / relative) != expected_hash:
            errors.append("protected_hash_changed:" + relative)

    replay_dirs = sorted((OUT / "replays").glob("*") if (OUT / "replays").is_dir() else [])
    if len(replay_dirs) >= 2:
        first = {path.name: path.read_bytes() for path in replay_dirs[0].iterdir() if path.is_file()}
        second = {path.name: path.read_bytes() for path in replay_dirs[1].iterdir() if path.is_file()}
        if first != second:
            errors.append("offline_replays_not_identical")

    return {
        "schema": "sfh2-a2or-validator-v1",
        "baseline_commit": BASELINE_COMMIT,
        "case_count": len(expected_ids),
        "provider_calls": transport.get("provider_calls"),
        "gold_mutation_count": len(changed),
        "protected_historical_inputs_unchanged": not any(error.startswith("historical_artifact_changed:") for error in errors),
        "errors": sorted(set(errors)),
        "valid": not errors,
        "candidate_only": True,
        "canonical_write_back": False,
    }


def main() -> int:
    result = validate()
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if result["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
