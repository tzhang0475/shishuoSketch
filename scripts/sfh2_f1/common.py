"""Frozen F1 inputs and language-neutral execution helpers.

This module deliberately contains no historical-semantic rules.  It converts
the already-authorized F-prep selection into exact source packets, derives
provenance from structured evidence metadata, and records hashes used by the
live runner.
"""

from __future__ import annotations

import copy
import hashlib
import json
import os
from pathlib import Path
from typing import Any, Mapping

from sfh2_a0 import common as a0_common
from sfh2_a0 import pipeline as a0_pipeline
from sfh2_a0r import pipeline as a0r_pipeline
from sfh2_a0r.contracts import semantic_record_tool
from sfh2_a2 import common as a2_common
from sfh2_a2 import pipeline as a2_pipeline
from sfh2_a2r import contracts as a2r_contracts
from sfh2_a2r import pipeline as a2r_pipeline
from sfh2_a2o.provenance import derive_provenance_layer
from sfh2_a2or import contracts as a2or_contracts
from sfh2_a2or import prompt as a2or_prompt
from sfh2_a2ovb import common as a2ovb_common
from sfh2_a2ovb import contracts as a2ovb_contracts
from sfh2_a2ovb import prompt as a2ovb_prompt


ROOT = Path(__file__).resolve().parents[2]
BASELINE_COMMIT = "b30c380095772f61dcf3109b75535a70007c47ab"
OUT = ROOT / "data/generated/sfh2-f1"
SELECTION_PATH = ROOT / "data/generated/sfh2-f-prep/f1-selection.json"
READINESS_PATH = ROOT / "data/generated/sfh2-f-prep/identity-readiness.json"
CACHE_PLAN_PATH = ROOT / "data/generated/sfh2-f-prep/cache-reuse-plan.json"
SEMANTIC_ROOT = ROOT / "data/frozen/sfh2/semantic-v1"
IDENTITY_MANIFEST = ROOT / "data/frozen/sfh2/identity-v1/manifest.json"
A2OR_ROOT = ROOT / "data/generated/sfh2-a2or"
F1_RAW_DEFAULT = Path("/tmp/sfh2-f1-raw-b30c380095772f61")
FROZEN_POLICY_PATHS = {
    "checkpoint": ROOT / "data/generated/sfh2-f-prep/checkpoint-policy.json",
    "cache_reuse": ROOT / "data/generated/sfh2-f-prep/cache-reuse-plan.json",
    "provider_failure": ROOT / "data/generated/sfh2-f-prep/provider-failure-policy.json",
    "review_routing": ROOT / "data/generated/sfh2-f-prep/review-routing-policy.json",
    "stop_conditions": ROOT / "data/generated/sfh2-f-prep/f1-stop-conditions.json",
    "success_gate": ROOT / "data/generated/sfh2-f-prep/f1-success-gate.json",
}

MODEL = "deepseek-v4-flash"
TEMPERATURE = 0
THINKING = {"type": "disabled"}
ENDPOINT = "https://api.deepseek.com/beta/chat/completions"

IDENTITY_PRIMARY_PROMPT_VERSION = "sfh2-a0r-primary-historian-v1"
IDENTITY_INDEPENDENT_PROMPT_VERSION = "sfh2-a2-independent-historian-v1"
IDENTITY_ADJUDICATOR_PROMPT_VERSION = "sfh2-a2r-adjudicator-v2"
OCCURRENCE_PROMPT_VERSION = "sfh2-a2or-occurrence-function-historian-v2"
BOUNDARY_PROMPT_VERSION = "sfh2-a2ovb-blind-boundary-validator-v1"

IDENTITY_PRIMARY_FUNCTION = "submit_sfh2_a0r_primary_semantics_v1"
IDENTITY_INDEPENDENT_FUNCTION = "submit_sfh2_a2_independent_historian_v1"
IDENTITY_ADJUDICATOR_FUNCTION = "submit_sfh2_a2r_adjudication_v2"
OCCURRENCE_FUNCTION = "submit_sfh2_a2or_occurrence_function_v2"
BOUNDARY_FUNCTION = "submit_sfh2_a2ovb_boundary_validation_v1"


def text(value: Any) -> str:
    return str(value or "").strip()


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def stable_hash(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def read_json(path: Path, default: Any = None) -> Any:
    if not path.is_file():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def frozen_policy_documents() -> dict[str, dict[str, Any]]:
    """Load and minimally validate the immutable F-prep execution contracts."""

    result: dict[str, dict[str, Any]] = {}
    for name, path in FROZEN_POLICY_PATHS.items():
        document = read_json(path)
        if not isinstance(document, Mapping):
            raise RuntimeError("f1_frozen_policy_missing_or_invalid:" + name)
        if document.get("candidate_only") is not True or document.get("canonical_write_back") is not False:
            raise RuntimeError("f1_frozen_policy_safety_mismatch:" + name)
        result[name] = dict(document)
    checkpoint = result["checkpoint"]
    required_checkpoint_fields = {
        "unit_id", "request_hash", "status", "attempt", "contract_valid",
        "output_hash", "provider_witness_hash", "runtime_metadata",
    }
    if set(checkpoint.get("checkpoint_fields", [])) != required_checkpoint_fields:
        raise RuntimeError("f1_checkpoint_policy_fields_changed")
    if checkpoint.get("different_request_hash_rule") != "never silently reuse":
        raise RuntimeError("f1_checkpoint_policy_hash_rule_changed")
    failure = result["provider_failure"]
    if (failure.get("http_400") or {}).get("retry") is not False:
        raise RuntimeError("f1_http400_retry_policy_changed")
    transient = failure.get("transient_429_5xx_timeout_connection_reset") or {}
    if int(transient.get("max_retries", -1)) != 1:
        raise RuntimeError("f1_transient_retry_policy_changed")
    return result


def frozen_policy_hashes(policies: Mapping[str, Mapping[str, Any]] | None = None) -> dict[str, str]:
    documents = policies or frozen_policy_documents()
    return {
        name: file_hash(FROZEN_POLICY_PATHS[name])
        for name in documents
        if name in FROZEN_POLICY_PATHS and FROZEN_POLICY_PATHS[name].is_file()
    }


def rows(document: Any, key: str = "records") -> list[dict[str, Any]]:
    if isinstance(document, list):
        return [dict(row) for row in document if isinstance(row, Mapping)]
    if isinstance(document, Mapping) and isinstance(document.get(key), list):
        return [dict(row) for row in document[key] if isinstance(row, Mapping)]
    return []


def selection_document() -> dict[str, Any]:
    selection = read_json(SELECTION_PATH, {}) or {}
    if not isinstance(selection, Mapping):
        raise RuntimeError("f1_selection_not_object")
    return dict(selection)


def exact_key(row: Mapping[str, Any]) -> dict[str, Any]:
    key = row.get("exact_occurrence_key") if isinstance(row.get("exact_occurrence_key"), Mapping) else row
    required = ("occurrence_id", "case_id", "mention_id", "story_id", "source_evidence_id", "source_start", "source_end", "surface")
    result = {name: key.get(name) for name in required}
    if any(result.get(name) in (None, "") for name in required):
        raise RuntimeError("f1_selection_exact_key_incomplete")
    if not isinstance(result["source_start"], int) or not isinstance(result["source_end"], int):
        raise RuntimeError("f1_selection_offsets_not_integer")
    return result


def selection_rows() -> list[dict[str, Any]]:
    selection = selection_document()
    result = [dict(row) for row in selection.get("records", []) or [] if isinstance(row, Mapping)]
    if len(result) != 30 or selection.get("occurrence_count") != 30 or selection.get("story_count") != 25:
        raise RuntimeError("f1_selection_scope_changed")
    if selection.get("not_executed") is not True or selection.get("gold_used_for_selection") is not False:
        raise RuntimeError("f1_selection_execution_or_gold_flag_changed")
    if selection.get("selection_hash") != "100fe51cce719c84bb7d538373cabecc5641a60419e03e21a7f73b1a1040dffe":
        raise RuntimeError("f1_selection_hash_changed")
    keys = [exact_key(row) for row in result]
    if len({text(key["occurrence_id"]) for key in keys}) != 30:
        raise RuntimeError("f1_selection_duplicate_occurrence")
    if len({text(key["story_id"]) for key in keys}) != 25:
        raise RuntimeError("f1_selection_story_count_changed")
    for row, key in zip(result, keys):
        row["exact_occurrence_key"] = key
        row["occurrence_id"] = key["occurrence_id"]
    return result


def case_from_row(row: Mapping[str, Any]) -> dict[str, Any]:
    key = exact_key(row)
    return {
        "case_id": text(key["case_id"]),
        "occurrence_id": text(key["occurrence_id"]),
        "mention_id": text(key["mention_id"]),
        "story_id": text(key["story_id"]),
        "surface": text(key["surface"]),
        "source_evidence_id": text(key["source_evidence_id"]),
        "source_start": key["source_start"],
        "source_end": key["source_end"],
        "cohort": "f1",
    }


def load_inputs() -> dict[str, Any]:
    return a2_common.load_inputs()


def build_packet(case: Mapping[str, Any], inputs: Mapping[str, Any]) -> dict[str, Any]:
    packet = dict(a2_common.build_case_packet(case, inputs))
    provenance, errors = derive_provenance_layer(packet)
    if errors or not provenance:
        raise RuntimeError("provenance_derivation_failure:" + ";".join(errors))
    packet["provenance_layer"] = provenance
    packet["identity_is_frozen"] = False
    packet["f1_candidate_wave"] = True
    packet["gold_visible_to_model"] = False
    packet["candidate_only"] = True
    packet["canonical_write_back"] = False
    return packet


def packet_key(packet: Mapping[str, Any]) -> dict[str, Any]:
    target = packet.get("target") if isinstance(packet.get("target"), Mapping) else {}
    return {
        "occurrence_id": text(packet.get("mention_id")),
        "case_id": text(packet.get("case_id")),
        "mention_id": text(packet.get("mention_id")),
        "story_id": text(packet.get("story_id")),
        "source_evidence_id": text(target.get("source_evidence_id")),
        "source_start": target.get("source_start"),
        "source_end": target.get("source_end"),
        "surface": text(target.get("surface")),
    }


def validate_exact_occurrence(row: Mapping[str, Any], packet: Mapping[str, Any]) -> dict[str, Any]:
    expected = exact_key(row)
    actual = packet_key(packet)
    errors: list[str] = []
    for field in ("occurrence_id", "mention_id", "story_id", "source_evidence_id", "source_start", "source_end", "surface"):
        if actual.get(field) != expected.get(field):
            errors.append(f"{field}_mismatch")
    evidence = {
        text(item.get("evidence_id")): item
        for item in packet.get("source_evidence", []) or []
        if isinstance(item, Mapping) and text(item.get("evidence_id"))
    }
    source = evidence.get(text(expected["source_evidence_id"]))
    if source is None:
        errors.append("source_evidence_missing")
    else:
        source_text = text(source.get("text"))
        start, end = expected["source_start"], expected["source_end"]
        if not (0 <= start <= end <= len(source_text)):
            errors.append("source_offsets_out_of_bounds")
        elif source_text[start:end] != expected["surface"]:
            errors.append("source_slice_surface_mismatch")
        if text(packet.get("target", {}).get("exact_span")) != expected["surface"]:
            errors.append("packet_exact_span_mismatch")
    return {"valid": not errors, "errors": sorted(set(errors)), "expected": expected, "actual": actual}


def evidence_ids(packet: Mapping[str, Any]) -> set[str]:
    return {
        text(row.get("evidence_id"))
        for row in packet.get("source_evidence", []) or []
        if isinstance(row, Mapping) and text(row.get("evidence_id"))
    }


def identity_context_from_record(record: Mapping[str, Any] | None) -> tuple[dict[str, Any], dict[str, str]]:
    if not isinstance(record, Mapping):
        return {}, {key: "" for key in ("speaker_hint", "addressee_hint", "antecedent_hint", "self_reference_hint")}
    discourse = record.get("discourse") if isinstance(record.get("discourse"), Mapping) else {}
    context = {
        "semantic_kind": record.get("semantic_kind"),
        "reference_type": record.get("reference_type"),
        "referent": copy.deepcopy(record.get("referent", {})),
        "attribute_type": record.get("attribute_type", ""),
        "attribute_value": record.get("attribute_value", ""),
        "bearer_hint": record.get("bearer_hint", ""),
        "abstain": record.get("abstain", False),
    }
    discourse_context = {
        key: text(discourse.get(key))
        for key in ("speaker_hint", "addressee_hint", "antecedent_hint", "self_reference_hint")
    }
    return context, discourse_context


def readiness_by_occurrence() -> dict[str, Mapping[str, Any]]:
    document = read_json(READINESS_PATH, {}) or {}
    return {
        text(row.get("occurrence_id")): row
        for row in document.get("records", []) or []
        if isinstance(row, Mapping) and text(row.get("occurrence_id"))
    }


def frozen_identity_by_mention() -> tuple[dict[str, Mapping[str, Any]], dict[str, Mapping[str, Any]]]:
    results = rows(read_json(A2OR_ROOT / "occurrence-results.json", {}))
    packets_doc = read_json(A2OR_ROOT / "case-packets.json", {}) or {}
    packet_by_mention: dict[str, Mapping[str, Any]] = {}
    for row in packets_doc.get("packets", []) or []:
        if isinstance(row, Mapping) and isinstance(row.get("packet"), Mapping):
            packet = row["packet"]
            mention_id = text(packet.get("mention_id"))
            if mention_id:
                packet_by_mention[mention_id] = packet
    result_by_mention = {
        text(row.get("mention_id")): row
        for row in results
        if text(row.get("mention_id")) and row.get("valid") is True
    }
    return result_by_mention, packet_by_mention


def frozen_identity_context_for(row: Mapping[str, Any], packet: Mapping[str, Any]) -> dict[str, Any] | None:
    result_by_mention, packet_by_mention = frozen_identity_by_mention()
    mention_id = text(exact_key(row)["mention_id"])
    result = result_by_mention.get(mention_id)
    source_packet = packet_by_mention.get(mention_id)
    if not isinstance(result, Mapping) or not isinstance(source_packet, Mapping):
        return None
    if packet_key(source_packet)["mention_id"] != mention_id:
        return None
    for key in ("story_id", "source_evidence_id", "source_start", "source_end", "surface"):
        if packet_key(source_packet).get(key) != exact_key(row).get(key):
            return None
    identity = result.get("frozen_identity")
    if not isinstance(identity, Mapping):
        return None
    discourse = source_packet.get("frozen_discourse_context")
    return {
        "frozen_identity": copy.deepcopy(identity),
        "frozen_discourse_context": copy.deepcopy(discourse) if isinstance(discourse, Mapping) else {key: "" for key in ("speaker_hint", "addressee_hint", "antecedent_hint", "self_reference_hint")},
        "source_case_id": text(result.get("case_id")),
        "source_result_hash": stable_hash(result),
    }


def attach_identity_context(packet: Mapping[str, Any], context: Mapping[str, Any] | None) -> dict[str, Any]:
    result = copy.deepcopy(dict(packet))
    identity = context.get("frozen_identity") if isinstance(context, Mapping) else None
    discourse = context.get("frozen_discourse_context") if isinstance(context, Mapping) else None
    result["frozen_identity_context"] = copy.deepcopy(identity) if isinstance(identity, Mapping) else {}
    result["frozen_discourse_context"] = copy.deepcopy(discourse) if isinstance(discourse, Mapping) else {key: "" for key in ("speaker_hint", "addressee_hint", "antecedent_hint", "self_reference_hint")}
    result["identity_is_frozen"] = True
    return result


def input_identity_hash(context: Mapping[str, Any] | None) -> str:
    return stable_hash(context or {})


def request_hash(stage: str, prompt_version: str, system: str, payload: Mapping[str, Any], tool: Mapping[str, Any], *, function_name: str) -> str:
    return stable_hash({
        "stage": stage,
        "prompt_version": prompt_version,
        "model": MODEL,
        "temperature": TEMPERATURE,
        "thinking": THINKING,
        "endpoint": ENDPOINT,
        "function_name": function_name,
        "system": system,
        "payload": payload,
        "tool": tool,
    })


def old_a2or_request_hash(source_case_id: str, source_packet: Mapping[str, Any]) -> str:
    """Match the frozen A2OR transport request hash for an allowed cache hit."""

    payload = a2or_prompt.provider_payload(source_packet)
    return stable_hash({"stage": "occurrence_function", "case_id": source_case_id, "payload": payload})


def cache_plan_entries() -> list[Mapping[str, Any]]:
    document = read_json(CACHE_PLAN_PATH, {}) or {}
    return [row for row in document.get("entries", []) or [] if isinstance(row, Mapping)]


def a2or_cache_candidate(row: Mapping[str, Any], packet: Mapping[str, Any]) -> dict[str, Any] | None:
    key = exact_key(row)
    candidate = next((entry for entry in cache_plan_entries() if text(entry.get("occurrence_id")) == text(key["occurrence_id"]) and text(entry.get("stage")) == "occurrence_primary"), None)
    if not isinstance(candidate, Mapping) or candidate.get("exact_reuse_candidate") is not True:
        return None
    if (
        candidate.get("source_stage") != "A2OR"
        or candidate.get("model") != MODEL
        or candidate.get("temperature") != TEMPERATURE
        or candidate.get("thinking") != THINKING
        or candidate.get("prompt_version") != OCCURRENCE_PROMPT_VERSION
        or candidate.get("exact_request_witness_present") is not True
        or candidate.get("reuse_requires_current_request_hash_equality") is not True
    ):
        return None
    source_result_path = ROOT / text(candidate.get("source_result_path"))
    source_result_sha = text(candidate.get("source_result_sha256"))
    if not source_result_path.is_file() or file_hash(source_result_path) != source_result_sha:
        return None
    source_rows = rows(read_json(source_result_path, {}))
    source = next((item for item in source_rows if text(item.get("mention_id")) == text(key["mention_id"])), None)
    if not isinstance(source, Mapping) or source.get("valid") is not True:
        return None
    source_packet = next((item.get("packet") for item in (read_json(A2OR_ROOT / "case-packets.json", {}) or {}).get("packets", []) or [] if isinstance(item, Mapping) and text(item.get("case_id")) == text(candidate.get("source_case_id")) and isinstance(item.get("packet"), Mapping)), None)
    if not isinstance(source_packet, Mapping):
        return None
    source_key = packet_key(source_packet)
    for field in ("mention_id", "story_id", "source_evidence_id", "source_start", "source_end", "surface"):
        if source_key.get(field) != key.get(field):
            return None
    current_source_packet = copy.deepcopy(dict(packet))
    current_source_packet["case_id"] = text(candidate.get("source_case_id"))
    if a2or_prompt.provider_payload(current_source_packet) != a2or_prompt.provider_payload(source_packet):
        return None
    computed = old_a2or_request_hash(text(candidate.get("source_case_id")), source_packet)
    if computed != text(candidate.get("request_hash")):
        return None
    transport = source.get("transport") if isinstance(source.get("transport"), Mapping) else {}
    if text(transport.get("response_witness_sha256")) != text(candidate.get("response_witness_sha256")):
        return None
    occurrence_result = source.get("occurrence_result")
    if not isinstance(occurrence_result, Mapping):
        return None
    return {
        "source_case_id": text(candidate.get("source_case_id")),
        "source_result_path": text(candidate.get("source_result_path")),
        "source_result_sha256": source_result_sha,
        "source_request_hash": text(candidate.get("request_hash")),
        "response_witness_sha256": text(candidate.get("response_witness_sha256")),
        "occurrence_result": copy.deepcopy(occurrence_result),
        "source_transport": copy.deepcopy(transport),
    }


def boundary_cache_candidate(row: Mapping[str, Any], packet: Mapping[str, Any]) -> dict[str, Any] | None:
    """Return a frozen A2OVB result only when the current request is exact.

    F-prep intentionally records the semantic occurrence fields rather than
    the historical challenge ``case_id`` as the reusable key.  The source
    case id is used only to reproduce the old transport request hash; the
    exact occurrence key and current identity packet are checked separately.
    """

    key = exact_key(row)
    candidate = next((entry for entry in cache_plan_entries() if text(entry.get("occurrence_id")) == text(key["occurrence_id"]) and text(entry.get("stage")) == "boundary_validator"), None)
    if not isinstance(candidate, Mapping) or candidate.get("exact_reuse_candidate") is not True:
        return None
    if (
        candidate.get("source_stage") != "A2OVB"
        or candidate.get("model") != MODEL
        or candidate.get("temperature") != TEMPERATURE
        or candidate.get("thinking") != THINKING
        or candidate.get("prompt_version") != BOUNDARY_PROMPT_VERSION
        or candidate.get("exact_request_witness_present") is not True
        or candidate.get("reuse_requires_current_request_hash_equality") is not True
    ):
        return None
    source_result_path = ROOT / text(candidate.get("source_result_path"))
    source_result_sha = text(candidate.get("source_result_sha256"))
    if not source_result_path.is_file() or file_hash(source_result_path) != source_result_sha:
        return None
    source_rows = rows(read_json(source_result_path, {}))
    source = next((item for item in source_rows if text(item.get("mention_id")) == text(key["mention_id"])), None)
    if not isinstance(source, Mapping) or source.get("validator_valid") is not True:
        return None
    source_packet_rows = read_json(ROOT / "data/generated/sfh2-a2ovb/boundary-packets.json", {}) or {}
    source_packet = next((item.get("packet") for item in source_packet_rows.get("records", []) or [] if isinstance(item, Mapping) and text(item.get("case_id")) == text(candidate.get("source_case_id")) and isinstance(item.get("packet"), Mapping)), None)
    if not isinstance(source_packet, Mapping):
        return None
    source_key = packet_key(source_packet)
    for field in ("mention_id", "story_id", "source_evidence_id", "source_start", "source_end", "surface"):
        if source_key.get(field) != key.get(field):
            return None
    current_source_case_packet = copy.deepcopy(dict(packet))
    current_source_case_packet["case_id"] = text(candidate.get("source_case_id"))
    computed = stable_hash({
        "stage": "boundary_validator",
        "case_id": text(candidate.get("source_case_id")),
        "payload": a2ovb_common.provider_payload(current_source_case_packet),
    })
    if computed != text(candidate.get("request_hash")):
        return None
    source_payload = a2ovb_common.provider_payload(source_packet)
    result = source.get("validator_result")
    if not isinstance(result, Mapping) or not a2ovb_contracts.validate_boundary_payload(source_payload, result).get("valid"):
        return None
    transport = source.get("transport") if isinstance(source.get("transport"), Mapping) else {}
    if text(transport.get("response_witness_sha256")) != text(candidate.get("response_witness_sha256")):
        return None
    return {
        "source_case_id": text(candidate.get("source_case_id")),
        "source_result_path": text(candidate.get("source_result_path")),
        "source_result_sha256": source_result_sha,
        "source_request_hash": text(candidate.get("request_hash")),
        "response_witness_sha256": text(candidate.get("response_witness_sha256")),
        "validator_result": copy.deepcopy(result),
        "source_transport": copy.deepcopy(transport),
    }


def strict_schema_errors() -> dict[str, list[str]]:
    from sfh2_a0r.contracts import validate_deepseek_strict_schema

    schemas = {
        "identity_semantic_record": semantic_record_tool()["function"]["parameters"],
        "identity_adjudicator": a2r_contracts.adjudicator_tool()["function"]["parameters"],
        "occurrence_primary": a2or_contracts.occurrence_function_tool()["function"]["parameters"],
        "boundary_validator": a2ovb_contracts.boundary_tool()["function"]["parameters"],
    }
    return {name: validate_deepseek_strict_schema(schema) for name, schema in schemas.items()}


def code_hashes() -> dict[str, str]:
    paths = [
        "scripts/sfh2_a0r/common.py", "scripts/sfh2_a0r/contracts.py", "scripts/sfh2_a0r/pipeline.py",
        "scripts/sfh2_a2/common.py", "scripts/sfh2_a2/contracts.py", "scripts/sfh2_a2/comparison.py", "scripts/sfh2_a2/pipeline.py",
        "scripts/sfh2_a2r/contracts.py", "scripts/sfh2_a2r/pipeline.py",
        "scripts/sfh2_a2or/common.py", "scripts/sfh2_a2or/contracts.py", "scripts/sfh2_a2or/prompt.py",
        "scripts/sfh2_a2ovb/common.py", "scripts/sfh2_a2ovb/contracts.py", "scripts/sfh2_a2ovb/prompt.py",
    ]
    return {path: file_hash(ROOT / path) for path in paths if (ROOT / path).is_file()}


def protected_snapshot() -> dict[str, Any]:
    paths = [
        "data/annotation/sfh2-a2o-evaluation-gold.json",
        "data/frozen/sfh2/identity-v1/manifest.json",
        "data/frozen/sfh2/semantic-v1/manifest.json",
        "data/frozen/sfh2/semantic-v1/architecture.json",
        "data/frozen/sfh2/semantic-v1/schemas.json",
        "data/frozen/sfh2/semantic-v1/protected-hashes.json",
        "data/derived/sc1-site.json", "data/derived/sc1-current-site.json",
        "site/src/generated/sc1-site.json", "site/src/generated/sc1-current-site.json",
        "data/people.json", "data/aliases.json", "data/derived/h0c-historical-facts.json",
        "data/derived/person-resolution-effective.json",
    ]
    result: dict[str, Any] = {}
    for path in paths:
        absolute = ROOT / path
        if absolute.is_file():
            result[path] = {"sha256": file_hash(absolute), "size_bytes": absolute.stat().st_size}
    for directory in ("data/generated/sfh2-f-prep", "data/generated/sfh2-a2", "data/generated/sfh2-a2r", "data/generated/sfh2-a2g", "data/generated/sfh2-a2gr", "data/generated/sfh2-a2o", "data/generated/sfh2-a2ot", "data/generated/sfh2-a2os", "data/generated/sfh2-a2osp", "data/generated/sfh2-a2ov", "data/generated/sfh2-a2ovb"):
        absolute = ROOT / directory
        if absolute.is_dir():
            result[directory] = {
                "file_count": sum(1 for child in absolute.rglob("*") if child.is_file()),
                "sha256_by_file": {str(child.relative_to(ROOT)): file_hash(child) for child in sorted(absolute.rglob("*")) if child.is_file()},
            }
    return result


def snapshot_diff(before: Mapping[str, Any], after: Mapping[str, Any]) -> list[str]:
    changed: list[str] = []
    for path in sorted(set(before) | set(after)):
        if before.get(path) != after.get(path):
            changed.append(path)
    return changed


def model_configs() -> dict[str, Any]:
    return {
        "model": MODEL,
        "temperature": TEMPERATURE,
        "thinking": dict(THINKING),
        "endpoint": ENDPOINT,
        "retry_policy": "HTTP400/nonretryable; transient 429/5xx/timeout/connection-reset at most one retry",
    }


def prompt_hashes() -> dict[str, str]:
    return {
        "identity_primary": stable_hash(a0r_pipeline.PRIMARY_HISTORIAN_SYSTEM),
        "identity_independent": stable_hash(a2_pipeline.HISTORIAN_B_SYSTEM),
        "identity_adjudicator": stable_hash(a2r_pipeline.ADJUDICATOR_SYSTEM),
        "occurrence_primary": stable_hash(a2or_prompt.HISTORIAN_SYSTEM),
        "boundary_validator": stable_hash(a2ovb_prompt.HISTORIAN_SYSTEM),
    }


def tool_hashes() -> dict[str, str]:
    return {
        "identity_semantic_record": stable_hash(semantic_record_tool()),
        "identity_adjudicator": stable_hash(a2r_contracts.adjudicator_tool()),
        "occurrence_primary": stable_hash(a2or_contracts.occurrence_function_tool()),
        "boundary_validator": stable_hash(a2ovb_contracts.boundary_tool()),
    }


def external_raw_root() -> Path:
    configured = Path(os.environ.get("SFH2_F1_RAW_DIR", str(F1_RAW_DEFAULT))).expanduser().resolve()
    root = ROOT.resolve()
    if configured == root or root in configured.parents:
        raise RuntimeError("f1_raw_storage_must_be_external_to_repository")
    configured.mkdir(parents=True, exist_ok=True)
    return configured
