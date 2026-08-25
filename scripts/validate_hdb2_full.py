#!/usr/bin/env python3
"""Validate HDB2-F safety, freeze, provenance, and offline replay invariants."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

import build_hdb2_full_frontier as builder  # noqa: E402
import build_hdb2_full_projection as projection  # noqa: E402
import hdb2_full_frontier_common as common  # noqa: E402
import hdb2_occurrence_common as occ  # noqa: E402

LOCAL_KEY = re.compile(r"^c\d+$")
FORBIDDEN_KEYS = {"person_id", "provisional_person_id", "graph_id", "priority_score", "canonical_graph_action", "surface_cluster_decision"}
PERSON_ID = re.compile(r"\bperson-\d+\b")


def _walk(value: Any, path: str = "") -> list[tuple[str, str, Any]]:
    found: list[tuple[str, str, Any]] = []
    if isinstance(value, Mapping):
        for key, child in value.items():
            current = f"{path}.{key}" if path else str(key)
            found.append(("key", current, key))
            found.extend(_walk(child, current))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            found.extend(_walk(child, f"{path}[{index}]"))
    elif isinstance(value, str):
        found.append(("string", path, value))
    return found


def _hashes(paths: list[Path]) -> dict[str, str]:
    return {str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest() for path in sorted(paths) if path.is_file()}


def validate(run_dir: Path) -> dict[str, Any]:
    errors: list[str] = []
    ledger, selection, cases_doc = builder.build(write=False)
    stored_selection = common.read_json(builder.SELECTION, {}) or {}
    if stored_selection != selection:
        errors.append("frontier_selection_changed")
    if selection.get("candidate_only") is not True or selection.get("canonical_write_back") is not False or selection.get("frozen_before_live") is not True:
        errors.append("selection_candidate_invariant")
    if selection.get("remaining_hdb2_f_live_frontier") != len(cases_doc.get("cases", [])):
        errors.append("frontier_case_count")
    prior_ids = set()
    for path in (common.ANNOTATION / "hdb2-p1-1-occurrence-selection.json", common.ANNOTATION / "hdb2-p2t-occurrence-selection.json"):
        doc = common.read_json(path, {}) or {}
        prior_ids |= {str(x.get("identity_observation_id")) for x in doc.get("cases", [])}
    selected_ids = {str(x.get("identity_observation_id")) for x in selection.get("cases", [])}
    if not selected_ids.isdisjoint(prior_ids):
        errors.append("frontier_prior_overlap")
    if len(selected_ids) != len(selection.get("cases", [])):
        errors.append("frontier_duplicate_identity_ids")

    # Rescue can add evidence and candidates before the single contextual
    # call.  Replay validation must use that immutable processed packet, not
    # the pre-live frontier case document, or a legitimate post-rescue local
    # key would be mistaken for an invalid model key.
    processed_contexts = common.read_json(run_dir / "occurrence-contexts.json", {}) or {}
    cases_by_id = {str(x.get("occurrence_id")): x for x in processed_contexts.get("cases", [])}
    if not cases_by_id:
        cases_by_id = {str(x.get("occurrence_id")): x for x in cases_doc.get("cases", [])}
    for case in cases_doc.get("cases", []):
        keys = [str(x.get("candidate_key")) for x in case.get("candidates", [])]
        if any(not LOCAL_KEY.fullmatch(key) for key in keys):
            errors.append(f"nonlocal_candidate_key:{case.get('occurrence_id')}")
        if case.get("exact_span") and not any(str(case.get("exact_span")) in str(item.get("text") or "") for item in case.get("evidence_items", [])):
            errors.append(f"ungrounded_occurrence:{case.get('occurrence_id')}")
        packet = occ.user_prompt(case)
        for kind, path, value in _walk(packet):
            if kind == "key" and value in FORBIDDEN_KEYS:
                errors.append(f"forbidden_prompt_key:{path}")
            if kind == "string" and PERSON_ID.search(value):
                errors.append(f"person_id_in_prompt:{path}")

    model_doc = common.read_json(run_dir / "model-decisions.json", {}) or {}
    py_doc = common.read_json(run_dir / "python-decisions.json", {}) or {}
    model_records = list(model_doc.get("records", []))
    python_records = list(py_doc.get("records", []))
    py_by_occ = {str(x.get("occurrence_id")): x for x in python_records}
    if len(python_records) != len(cases_doc.get("cases", [])):
        errors.append("python_decision_count")
    for record in python_records:
        if str(record.get("status")) not in common.FINAL_STATES:
            errors.append(f"invalid_final_status:{record.get('occurrence_id')}")
        if record.get("status") in {"compositional_reference", "ruler_reference", "office_reference", "not_person"} and record.get("resolved_person_id"):
            errors.append(f"structural_person_id:{record.get('occurrence_id')}")
        if record.get("status") == "contextually_resolved" and not record.get("resolved_person_id") and not record.get("candidate_person_id"):
            # A ruler context can be semantically useful without resolving a
            # catalogue Person; the projection must not call it existing.
            if record.get("occurrence_type") not in {"ruler_reference"}:
                errors.append(f"contextual_without_endpoint:{record.get('occurrence_id')}")
    for model in model_records:
        payload = model.get("payload") if isinstance(model.get("payload"), Mapping) else {}
        if model.get("call_type") == "contextual_disambiguation" and model.get("classification") == "parsed":
            case = cases_by_id.get(str(model.get("occurrence_id")))
            if case:
                validation = occ.validate_model_payload(payload, case)
                if validation.get("valid") is False:
                    # Invalid model output must remain an unresolved decision,
                    # never a mutated candidate state.
                    record = py_by_occ.get(str(model.get("occurrence_id")), {})
                    if record.get("status") not in {"unresolved", "conflict"}:
                        errors.append(f"invalid_model_mutated_state:{model.get('occurrence_id')}")
        if model.get("call_type") == "evidence_rescue":
            validation = model.get("validation") or {}
            if not isinstance(validation.get("valid_atoms", []), list):
                errors.append(f"rescue_validation_shape:{model.get('occurrence_id')}")

    relation_doc = common.read_json(run_dir / "relation-projection.json", {}) or {}
    relation_rows = list(relation_doc.get("records", []))
    for row in relation_rows:
        state = row.get("after", {}).get("state")
        subject = row.get("after", {}).get("subject", {})
        object_ = row.get("after", {}).get("object", {})
        if state == "rejected_self_relation":
            continue
        ids = {subject.get("person_id"), object_.get("person_id")} - {None, ""}
        if len(ids) == 1 and subject.get("type") == object_.get("type") == "existing":
            errors.append(f"surviving_self_relation:{row.get('candidate_id')}")
        if state in {"both_existing_resolved", "existing_plus_candidate", "both_candidate_resolved"} and subject.get("type") not in {"existing", "candidate"}:
            errors.append(f"endpoint_state_mismatch:{row.get('candidate_id')}")
    protected = common.protected_hashes()
    manifest = common.read_json(run_dir / "manifest.json", {}) or {}
    if manifest.get("protected_hashes_before") != manifest.get("protected_hashes_after"):
        errors.append("manifest_protected_hash_mismatch")
    for relative, expected in protected.items():
        if manifest.get("protected_hashes_before", {}).get(relative) != expected:
            errors.append(f"protected_hash_mismatch:{relative}")
    for relative, expected in (manifest.get("raw_api_hashes") or {}).items():
        path = ROOT / relative
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            errors.append(f"raw_api_changed:{relative}")

    # Reproject twice.  These are additive derived/review artifacts and no
    # network or raw response is touched by the projection.
    projection_paths = [
        common.DERIVED / name for name in (
            "hdb2-f-relation-projection.json", "hdb2-f-kinship-projection.json", "hdb2-f-marriage-projection.json", "hdb2-f-office-projection.json", "hdb2-f-candidate-person-registry.json", "hdb2-f-person-knowledge.json", "hdb2-f-candidate-person-knowledge.json", "hdb2-f-endpoint-bottleneck-audit.json", "hdb2-f-network-completion-metrics.json", "hdb2-f-identity-summary.json", "hdb2-f-metrics.json", "hdb2-f-unblocked-candidate-facts.json",
        )
    ] + [common.ANNOTATION / name for name in ("hdb2-f-occurrence-decisions.json", "hdb2-f-candidate-person-review.json", "hdb2-f-review-queue.json")]
    projection.project(run_dir)
    first_hashes = _hashes(projection_paths)
    projection.project(run_dir)
    second_hashes = _hashes(projection_paths)
    if first_hashes != second_hashes:
        errors.append("projection_not_byte_deterministic")

    result = {
        "valid": not errors,
        "errors": sorted(set(errors)),
        "candidate_only": True,
        "canonical_write_back": False,
        "frontier_count": len(selection.get("cases", [])),
        "protected_hashes_unchanged": not any(x.startswith("protected_") or x.startswith("manifest_protected") for x in errors),
        "deterministic_projection": "projection_not_byte_deterministic" not in errors,
    }
    common.write_json(run_dir / "validation.json", result)
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("run_dir", type=Path)
    args = parser.parse_args()
    run_dir = args.run_dir if args.run_dir.is_absolute() else ROOT / args.run_dir
    result = validate(run_dir)
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if result["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
