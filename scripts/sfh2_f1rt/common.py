"""Frozen inputs and transport-only mechanics for SFH2.2-F1RT.

F1RT is intentionally not a new semantic pipeline.  It reuses the frozen F1
source packets, prompts, semantic schema, and qualified identity comparison
logic while testing two bounded structured-output transport contracts.  This
module owns exact occurrence validation, envelope attachment, and compact
artifact construction; it never guesses a historical meaning from text.
"""

from __future__ import annotations

import copy
import hashlib
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any, Mapping

from sfh2_a0 import pipeline as a0_pipeline
from sfh2_a0 import schemas as a0_schemas
from sfh2_a0r import contracts as a0r_contracts
from sfh2_a0r import pipeline as a0r_pipeline
from sfh2_a2 import contracts as a2_contracts
from sfh2_a2 import pipeline as a2_pipeline
from sfh2_a2.comparison import compare_records
from sfh2_a2r import contracts as a2r_contracts
from sfh2_a2r import pipeline as a2r_pipeline
from sfh2_a2ovb import common as a2ovb_common
from sfh2_a2ovb import contracts as a2ovb_contracts
from sfh2_a2ovb import prompt as a2ovb_prompt

from sfh2_f1 import common as f1_common


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "data/generated/sfh2-f1rt"
F1_ROOT = ROOT / "data/generated/sfh2-f1"
F1R_ROOT = ROOT / "data/generated/sfh2-f1r"
F1RP_ROOT = ROOT / "data/generated/sfh2-f1rp"
F1_PREP_ROOT = ROOT / "data/generated/sfh2-f-prep"
SEMANTIC_ROOT = ROOT / "data/frozen/sfh2/semantic-v1"
IDENTITY_MANIFEST = ROOT / "data/frozen/sfh2/identity-v1/manifest.json"
POLICY_ROOT = ROOT / "data/frozen/sfh2/production-policy-v2"

BASELINE_COMMIT = "dbf6cf46db2236096a47f0c960935ea3e255faa4"
MODEL = "deepseek-v4-flash"
TEMPERATURE = 0
THINKING = {"type": "disabled"}
ENDPOINT = "https://api.deepseek.com/beta/chat/completions"

RECOVERY_POLICY_VERSION = "sfh2-f1rt-transport-policy-v3-candidate"
BODY_CONTRACT_VERSION = "sfh2-identity-semantic-body-transport-v2"
BODY_FUNCTION_PRIMARY = "submit_sfh2_identity_semantic_body_primary_v2"
BODY_FUNCTION_INDEPENDENT = "submit_sfh2_identity_semantic_body_independent_v2"
RECOVERY_MAX_NETWORK_RETRIES = 1

FAILURE_CLASSES = ("invalid_json", "truncated_output", "record_shape_invalid", "immutable_id_mismatch", "schema_field_invalid", "provider_transport_failure", "other")
RECOVERY_CLASSES = ("terminal_identity_block", "recovered_intermediate_failure", "terminal_boundary_failure", "nonsemantic_probe_failure")
BODY_ENVELOPE_FIELDS = (
    "case_id", "occurrence_id", "mention_id", "story_id", "source_evidence_id",
    "source_start", "source_end", "surface", "request_hash", "candidate_person_id",
    "pipeline_id", "stage_id",
)
BODY_FORBIDDEN_PROVIDER_FIELDS = set(BODY_ENVELOPE_FIELDS)

INVALID_JSON = "invalid_json"
TRUNCATED_OUTPUT = "truncated_output"
RECORD_SHAPE_INVALID = "record_shape_invalid"
IMMUTABLE_ID_MISMATCH = "immutable_id_mismatch"
SCHEMA_FIELD_INVALID = "schema_field_invalid"
PROVIDER_TRANSPORT_FAILURE = "provider_transport_failure"


def text(value: Any) -> str:
    return str(value or "").strip()


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def stable_hash(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_json(path: Path, default: Any = None) -> Any:
    if not path.is_file():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def rows(document: Any, key: str = "records") -> list[dict[str, Any]]:
    if isinstance(document, list):
        return [dict(row) for row in document if isinstance(row, Mapping)]
    if isinstance(document, Mapping) and isinstance(document.get(key), list):
        return [dict(row) for row in document[key] if isinstance(row, Mapping)]
    return []


def by_occurrence(document: Any, key: str = "records") -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for row in rows(document, key):
        occurrence_id = text(row.get("occurrence_id")) or text(row.get("case_id"))
        if occurrence_id:
            result[occurrence_id] = row
    return result


def exact_key(row: Mapping[str, Any]) -> dict[str, Any]:
    key = row.get("occurrence_key") if isinstance(row.get("occurrence_key"), Mapping) else row
    names = ("occurrence_id", "case_id", "mention_id", "story_id", "source_evidence_id", "source_start", "source_end", "surface")
    result = {name: key.get(name) for name in names}
    if any(result.get(name) in (None, "") for name in names):
        raise RuntimeError("f1rt_exact_key_incomplete")
    if not isinstance(result["source_start"], int) or not isinstance(result["source_end"], int):
        raise RuntimeError("f1rt_exact_key_offsets_not_integer")
    return result


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
        "cohort": "f1rt",
    }


def validate_exact_occurrence(row: Mapping[str, Any], packet: Mapping[str, Any]) -> dict[str, Any]:
    expected = exact_key(row)
    actual = packet_key(packet)
    errors: list[str] = []
    for field in ("occurrence_id", "mention_id", "story_id", "source_evidence_id", "source_start", "source_end", "surface"):
        if actual.get(field) != expected.get(field):
            errors.append(field + "_mismatch")
    evidence_rows = {
        text(item.get("evidence_id")): item
        for item in packet.get("source_evidence", []) or []
        if isinstance(item, Mapping) and text(item.get("evidence_id"))
    }
    source = evidence_rows.get(text(expected["source_evidence_id"]))
    if source is None:
        errors.append("source_evidence_missing")
    else:
        source_text = text(source.get("text"))
        start, end = expected["source_start"], expected["source_end"]
        if not (0 <= start <= end <= len(source_text)):
            errors.append("source_offsets_out_of_bounds")
        elif source_text[start:end] != expected["surface"]:
            errors.append("source_slice_surface_mismatch")
        target = packet.get("target") if isinstance(packet.get("target"), Mapping) else {}
        if text(target.get("exact_span")) != expected["surface"]:
            errors.append("packet_exact_span_mismatch")
    return {"valid": not errors, "errors": sorted(set(errors)), "expected": expected, "actual": actual}


def evidence_ids(packet: Mapping[str, Any]) -> set[str]:
    return {
        text(row.get("evidence_id"))
        for row in packet.get("source_evidence", []) or []
        if isinstance(row, Mapping) and text(row.get("evidence_id"))
    }


def load_bundle() -> dict[str, Any]:
    selection = read_json(F1_PREP_ROOT / "f1-selection.json", {}) or {}
    selection_rows = f1_common.selection_rows()
    if len(selection_rows) != 30:
        raise RuntimeError("f1rt_selection_count_changed")
    inputs = f1_common.load_inputs()
    cases: dict[str, dict[str, Any]] = {}
    packets: dict[str, dict[str, Any]] = {}
    selection_by_occurrence: dict[str, dict[str, Any]] = {}
    for selected in selection_rows:
        case = f1_common.case_from_row(selected)
        packet = f1_common.build_packet(case, inputs)
        exact = f1_common.validate_exact_occurrence(selected, packet)
        if not exact.get("valid"):
            raise RuntimeError("f1rt_invalid_exact_occurrence:" + text(case.get("occurrence_id")))
        occurrence_id = text(case["occurrence_id"])
        cases[occurrence_id] = case
        packets[occurrence_id] = packet
        selection_by_occurrence[occurrence_id] = dict(selected)
    identity_results = by_occurrence(read_json(F1_ROOT / "identity-results.json", {}))
    if set(identity_results) != set(cases):
        raise RuntimeError("f1rt_identity_result_case_set_changed")
    failure_audit = read_json(F1R_ROOT / "transport-failure-audit.json", {}) or {}
    return {
        "selection": selection,
        "selection_rows": selection_rows,
        "selection_by_occurrence": selection_by_occurrence,
        "cases": cases,
        "packets": packets,
        "inputs": inputs,
        "identity_results": identity_results,
        "failure_audit": failure_audit,
        "f1rp_handoff": read_json(F1RP_ROOT / "transport-recovery-handoff.json", {}) or {},
    }


def attach_identity_context(packet: Mapping[str, Any], identity_row: Mapping[str, Any]) -> dict[str, Any]:
    result = copy.deepcopy(dict(packet))
    context = identity_row.get("context") if isinstance(identity_row.get("context"), Mapping) else {}
    result["frozen_identity_context"] = copy.deepcopy(context.get("frozen_identity") or {})
    result["frozen_discourse_context"] = copy.deepcopy(context.get("frozen_discourse_context") or {key: "" for key in ("speaker_hint", "addressee_hint", "antecedent_hint", "self_reference_hint")})
    result["identity_is_frozen"] = True
    return result


def old_request(stage: str, prompt_version: str, system: str, payload: Mapping[str, Any], tool: Mapping[str, Any], function_name: str) -> str:
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


def recovery_request(original_request_hash: str, semantic_request: Mapping[str, Any], attempt_class: str = "recovery_replay_1") -> str:
    return stable_hash({
        "original_semantic_request_hash": original_request_hash,
        "semantic_request": copy.deepcopy(dict(semantic_request)),
        "recovery_policy_version": RECOVERY_POLICY_VERSION,
        "attempt_class": attempt_class,
    })


def identity_payloads(packet: Mapping[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    return a0r_pipeline.primary_payload(packet), a2_pipeline.historian_b_payload(packet)


def old_contracts() -> dict[str, Any]:
    return {
        "identity_primary": a0r_contracts.semantic_record_tool(),
        "identity_independent": a2_contracts.historian_b_tool(),
        "identity_adjudicator": a2r_contracts.adjudicator_tool(),
        "boundary_validator": a2ovb_contracts.boundary_tool(),
    }


def semantic_body_tool(source_tool: Mapping[str, Any], function_name: str, description: str) -> dict[str, Any]:
    """Clone the qualified full semantic schema minus Python-owned IDs."""

    tool = copy.deepcopy(dict(source_tool))
    function = tool["function"]
    function["name"] = function_name
    function["description"] = description
    parameters = function["parameters"]
    record_schema = parameters["properties"]["record"]
    properties = dict(record_schema["properties"])
    required = list(record_schema["required"])
    for field in ("mention_id", "surface"):
        properties.pop(field, None)
        required = [item for item in required if item != field]
    record_schema["properties"] = properties
    record_schema["required"] = required
    errors = a0r_contracts.validate_deepseek_strict_schema(parameters)
    if errors:
        raise RuntimeError("f1rt_body_schema_invalid:" + ";".join(errors))
    return tool


def body_tools() -> dict[str, dict[str, Any]]:
    return {
        "identity_primary": semantic_body_tool(
            a0r_contracts.semantic_record_tool(), BODY_FUNCTION_PRIMARY,
            "Return only the complete evidence-grounded semantic identity body. Python attaches the immutable occurrence envelope; do not emit routing IDs or production IDs.",
        ),
        "identity_independent": semantic_body_tool(
            a2_contracts.historian_b_tool(), BODY_FUNCTION_INDEPENDENT,
            "Return only an independent complete evidence-grounded semantic identity body. Python attaches the immutable occurrence envelope; do not emit routing IDs or production IDs.",
        ),
    }


def validate_semantic_body(packet: Mapping[str, Any], payload: Mapping[str, Any] | None) -> dict[str, Any]:
    if not isinstance(payload, Mapping):
        return {"valid": False, "record": None, "body": None, "errors": ["provider_or_schema_failure"]}
    if set(payload) != {"record"}:
        return {
            "valid": False,
            "record": None,
            "body": copy.deepcopy(payload.get("record")) if isinstance(payload.get("record"), Mapping) else None,
            "errors": ["body_outer_properties_not_exact"],
        }
    body = payload.get("record")
    if not isinstance(body, Mapping):
        return {"valid": False, "record": None, "body": None, "errors": ["record_not_object"]}
    allowed = set(a0_schemas.semantic_record_schema()["properties"]) - {"mention_id", "surface"}
    errors: list[str] = []
    extra = sorted(set(body) - allowed)
    missing = sorted(allowed - set(body))
    if extra:
        errors.append("body_forbidden_or_unexpected_fields:" + ",".join(extra))
    if missing:
        errors.append("body_missing_fields:" + ",".join(missing))
    if errors:
        return {"valid": False, "record": None, "body": copy.deepcopy(dict(body)), "errors": errors}
    target = dict(packet.get("target") or {})
    target["mention_id"] = text(packet.get("mention_id"))
    # The provider does not own these two fields.  They are attached only
    # after the body has passed the body allow-list check.
    full_record = copy.deepcopy(dict(body))
    full_record["mention_id"] = text(packet.get("mention_id"))
    full_record["surface"] = text(target.get("surface"))
    validated = a0_schemas.validate_semantic_payload(packet, target, {"record": full_record})
    if not validated.get("valid"):
        return {"valid": False, "record": None, "body": copy.deepcopy(dict(body)), "errors": sorted(set(validated.get("errors", [])))}
    return {"valid": True, "record": copy.deepcopy(validated["record"]), "body": copy.deepcopy(dict(body)), "errors": []}


def identity_result_from_body(case: Mapping[str, Any], packet: Mapping[str, Any], payload: Mapping[str, Any] | None, transport: Mapping[str, Any], inputs: Mapping[str, Any], stage: str) -> dict[str, Any]:
    validated = validate_semantic_body(packet, payload)
    record = validated.get("record") if validated.get("valid") is True else None
    result: dict[str, Any] = {
        "case_id": text(case.get("case_id")),
        "occurrence_id": text(case.get("occurrence_id")),
        "mention_id": text(case.get("mention_id")),
        "story_id": text(case.get("story_id")),
        "surface": text(case.get("surface")),
        "stage": stage,
        "valid": validated.get("valid") is True,
        "contract_status": "valid" if validated.get("valid") is True else "identity_body_contract_invalid",
        "record": record,
        "semantic_body": copy.deepcopy(validated.get("body")),
        "errors": sorted(set(validated.get("errors", []))),
        "transport": copy.deepcopy(transport),
        "candidate_only": True,
        "canonical_write_back": False,
    }
    if record is not None:
        realization = a0r_pipeline.realize_semantic_record(case, record, inputs)
        result["provisional_realization"] = realization
        result["consistency"] = a0r_pipeline.analyze_record(record, evidence_ids=evidence_ids(packet), realization=realization, stage=stage)
    else:
        result["provisional_realization"] = a0r_pipeline.realize_semantic_record(case, None, inputs)
        result["consistency"] = a0r_pipeline.analyze_record(None, evidence_ids=evidence_ids(packet), realization=result["provisional_realization"], stage=stage)
    return result


def identity_result_from_full(case: Mapping[str, Any], packet: Mapping[str, Any], payload: Mapping[str, Any] | None, transport: Mapping[str, Any], inputs: Mapping[str, Any], stage: str) -> dict[str, Any]:
    if stage == "identity_primary":
        result = a0r_pipeline._record_from_provider(case, packet, payload)
    else:
        result = a2_pipeline._historian_b_row(case, packet, payload, transport)
    result["stage"] = stage
    result["contract_status"] = "valid" if result.get("valid") is True else "identity_contract_invalid"
    result["transport"] = copy.deepcopy(transport)
    record = result.get("record") if result.get("valid") is True and isinstance(result.get("record"), Mapping) else None
    realization = a0r_pipeline.realize_semantic_record(case, record, inputs)
    result["provisional_realization"] = realization
    result["consistency"] = a0r_pipeline.analyze_record(record, evidence_ids=evidence_ids(packet), realization=realization, stage=stage)
    result["candidate_only"] = True
    result["canonical_write_back"] = False
    return result


def classify_transport_failure(row: Mapping[str, Any], contract_errors: list[str] | None = None) -> str:
    if text(row.get("classification")) == "provider_request_failure":
        return PROVIDER_TRANSPORT_FAILURE
    parse_error = text(row.get("parse_error"))
    finish = text(row.get("finish_reason"))
    errors = set(contract_errors or [])
    # A length-terminated response is specifically truncation even though
    # the provider envelope may also expose invalid JSON in its arguments.
    if (
        finish == "length"
        or text(row.get("classification")) == "response_truncated"
        or text(row.get("transport_classification")) == "response_truncated"
        or text(row.get("failure_category")) == "truncated_output"
        or text(row.get("root_cause")) == "truncated_output"
    ):
        return TRUNCATED_OUTPUT
    if parse_error == "function_arguments_invalid_json" or text(row.get("classification")) == "response_parse_failure":
        return INVALID_JSON
    if "record_not_object" in errors:
        return RECORD_SHAPE_INVALID
    if any("mention_id" in value or "case_id" in value or "surface_mismatch" in value for value in errors):
        return IMMUTABLE_ID_MISMATCH
    if errors:
        return SCHEMA_FIELD_INVALID
    return "other"


def failure_inventory(bundle: Mapping[str, Any]) -> dict[str, Any]:
    audit = bundle["failure_audit"]
    invalid = []
    for row in audit.get("invalid_payloads", []) or []:
        item = dict(row)
        item["inventory_source"] = "response_level"
        item["contract_errors"] = list((item.get("stage_row") or {}).get("errors") or [])
        item["failure_class"] = classify_transport_failure(item, item["contract_errors"])
        invalid.append(item)
    for row in audit.get("parsed_contract_diagnostics", []) or []:
        item = dict(row)
        item["inventory_source"] = "parsed_contract_diagnostic"
        item["failure_class"] = classify_transport_failure(item, list(item.get("contract_errors") or []))
        invalid.append(item)
    by_key: dict[tuple[str, str], dict[str, Any]] = {}
    for item in invalid:
        occurrence_id = text(item.get("occurrence_id"))
        stage = text(item.get("stage"))
        if (occurrence_id, stage) in by_key:
            raise RuntimeError("f1rt_duplicate_invalid_stage_unit:" + occurrence_id + ":" + stage)
        case = bundle["cases"].get(occurrence_id)
        if case is None:
            raise RuntimeError("f1rt_failure_occurrence_not_in_selection:" + occurrence_id)
        item["exact_occurrence_key"] = exact_key(case)
        item["terminal"] = item.get("recovery_class") in {"terminal_identity_block", "terminal_boundary_failure"}
        item["provider_transport_success"] = bool(item.get("provider_transport_success"))
        by_key[(occurrence_id, stage)] = item
    records = sorted(by_key.values(), key=lambda row: (text(row.get("occurrence_id")), text(row.get("stage"))))
    class_counts = Counter(text(row.get("failure_class")) for row in records)
    recovery_counts = Counter(text(row.get("recovery_class")) for row in records)
    terminal_identity_occurrences = {
        text(row.get("occurrence_id"))
        for row in records
        if row.get("recovery_class") == "terminal_identity_block"
    }
    return {
        "schema": "sfh2-f1rt-failure-inventory-v1",
        "historical_response_level_failure_count": len(audit.get("invalid_payloads", []) or []),
        "parsed_contract_diagnostic_count": len(audit.get("parsed_contract_diagnostics", []) or []),
        "full_invalid_stage_unit_count": len(records),
        "identity_invalid_stage_unit_count": sum(text(row.get("stage")).startswith("identity_") for row in records),
        "boundary_invalid_stage_unit_count": sum(text(row.get("stage")) == "boundary_validator" for row in records),
        # A terminal identity block is represented by one or more failed
        # historian stage units.  Keep both units and distinct occurrences so
        # the transport report cannot confuse the two denominators.
        "terminal_identity_block_count": sum(row.get("recovery_class") == "terminal_identity_block" for row in records),
        "terminal_identity_block_stage_unit_count": sum(row.get("recovery_class") == "terminal_identity_block" for row in records),
        "terminal_identity_block_case_count": len(terminal_identity_occurrences),
        "records": records,
        "failure_class_counts": dict(sorted(class_counts.items())),
        "recovery_class_counts": dict(sorted(recovery_counts.items())),
        "source_stage": "SFH2.2-F1R retained compact evidence",
        "raw_provider_storage": "external_archive_default",
        "candidate_only": True,
        "canonical_write_back": False,
    }


def failure_request_material(bundle: Mapping[str, Any], row: Mapping[str, Any]) -> dict[str, Any]:
    occurrence_id = text(row.get("occurrence_id"))
    stage = text(row.get("stage"))
    packet = bundle["packets"][occurrence_id]
    identity = bundle["identity_results"][occurrence_id]
    if stage == "identity_primary":
        payload = a0r_pipeline.primary_payload(packet)
        tool = a0r_contracts.semantic_record_tool()
        system = a0r_pipeline.PRIMARY_HISTORIAN_SYSTEM
        prompt_version = "sfh2-a0r-primary-historian-v1"
        function_name = "submit_sfh2_a0r_primary_semantics_v1"
    elif stage == "identity_independent":
        payload = a2_pipeline.historian_b_payload(packet)
        tool = a2_contracts.historian_b_tool()
        system = a2_pipeline.HISTORIAN_B_SYSTEM
        prompt_version = "sfh2-a2-independent-historian-v1"
        function_name = "submit_sfh2_a2_independent_historian_v1"
    elif stage == "boundary_validator":
        context_packet = attach_identity_context(packet, identity)
        payload = a2ovb_common.provider_payload(context_packet)
        tool = a2ovb_contracts.boundary_tool()
        system = a2ovb_prompt.HISTORIAN_SYSTEM
        prompt_version = "sfh2-a2ovb-blind-boundary-validator-v1"
        function_name = "submit_sfh2_a2ovb_boundary_validation_v1"
    else:
        raise RuntimeError("f1rt_unknown_failure_stage:" + stage)
    request = old_request(stage, prompt_version, system, payload, tool, function_name)
    return {
        "stage": stage,
        "prompt_version": prompt_version,
        "function_name": function_name,
        "system": system,
        "payload": payload,
        "tool": tool,
        "original_request_hash_reconstructed": request,
        "original_request_hash_stored": text(row.get("request_hash")),
        "original_request_hash_matches": request == text(row.get("request_hash")),
        "case_id": text(bundle["cases"][occurrence_id].get("case_id")),
    }


def failure_inventory_with_requests(bundle: Mapping[str, Any], inventory: Mapping[str, Any]) -> dict[str, Any]:
    records = []
    for row in inventory["records"]:
        item = copy.deepcopy(row)
        material = failure_request_material(bundle, item)
        item["original_request"] = {
            "prompt_version": material["prompt_version"],
            "function_name": material["function_name"],
            "request_hash_reconstructed": material["original_request_hash_reconstructed"],
            "request_hash_stored": material["original_request_hash_stored"],
            "hash_matches": material["original_request_hash_matches"],
        }
        item["recovery_request_hash"] = recovery_request(text(item.get("request_hash")), material["payload"])
        item["recovery_attempt"] = "recovery_replay_1"
        records.append(item)
    return {**dict(inventory), "records": records}


def body_schema_document() -> dict[str, Any]:
    tools = body_tools()
    allowed = sorted(set(a0_schemas.semantic_record_schema()["properties"]) - {"mention_id", "surface"})
    return {
        "schema": "sfh2-identity-semantic-body-transport-v2",
        "contract_version": BODY_CONTRACT_VERSION,
        "provider_response_shape": "{record: semantic_body}",
        "provider_owned_semantic_fields": allowed,
        "python_owned_immutable_envelope_fields": list(BODY_ENVELOPE_FIELDS),
        "provider_forbidden_fields": sorted(BODY_FORBIDDEN_PROVIDER_FIELDS),
        "primary_tool": tools["identity_primary"],
        "independent_tool": tools["identity_independent"],
        "primary_tool_hash": stable_hash(tools["identity_primary"]),
        "independent_tool_hash": stable_hash(tools["identity_independent"]),
        "full_qualified_schema_hash": stable_hash(a0r_contracts.semantic_record_tool()),
        "id_attachment_rule": "validate semantic body first; attach exact Python envelope from the already-validated execution unit; provider fields cannot overwrite it",
        "candidate_only": True,
        "canonical_write_back": False,
    }


def normalized_semantic(record: Mapping[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(record, Mapping):
        return None
    referent = record.get("referent") if isinstance(record.get("referent"), Mapping) else {}
    discourse = record.get("discourse") if isinstance(record.get("discourse"), Mapping) else {}
    return {
        "semantic_kind": record.get("semantic_kind"),
        "reference_type": record.get("reference_type"),
        "referent_surface_form": referent.get("surface_form"),
        "referent_canonical_hint": referent.get("canonical_hint"),
        "occurrence_role": record.get("occurrence_role"),
        "bearer_hint": record.get("bearer_hint"),
        "attribute_type": record.get("attribute_type"),
        "attribute_value": record.get("attribute_value"),
        "abstain": record.get("abstain"),
        "speaker_hint": discourse.get("speaker_hint"),
        "addressee_hint": discourse.get("addressee_hint"),
    }


def normalized_semantic_core(record: Mapping[str, Any] | None) -> dict[str, Any] | None:
    """Return transport-relevant semantic identity fields.

    Body-v2 intentionally permits a historian to render the target surface
    and discourse context differently while preserving the identity meaning.
    The control comparison therefore keeps the required identity/attribute
    fields in its compatibility core and reports presentation/context drift
    separately.  This is comparison logic only; it does not choose a meaning.
    """

    normalized = normalized_semantic(record)
    if normalized is None:
        return None
    fields = (
        "semantic_kind",
        "reference_type",
        "referent_canonical_hint",
        "occurrence_role",
        "bearer_hint",
        "attribute_type",
        "attribute_value",
        "abstain",
    )
    return {field: normalized.get(field) for field in fields}


def control_selection(bundle: Mapping[str, Any]) -> dict[str, Any]:
    """Select six valid identity records without Gold or answer inspection.

    The ranking uses only structural/transport properties and identity-form
    fields already present in the historical valid record.  It does not read
    Gold or any F1RP decision.
    """

    identity = bundle["identity_results"]
    candidates = []
    category_order = {
        "full_name": 0,
        "personal_name": 1,
        "courtesy_name": 2,
        "pronoun_reference": 3,
        "office_title": 4,
        "kinship_reference": 5,
        "surname_reference": 6,
        "abbreviated_reference": 7,
    }
    for occurrence_id, row in identity.items():
        a = row.get("historian_primary") if isinstance(row.get("historian_primary"), Mapping) else {}
        b = row.get("historian_independent") if isinstance(row.get("historian_independent"), Mapping) else {}
        if a.get("valid") is not True or b.get("valid") is not True:
            continue
        record = a.get("record") if isinstance(a.get("record"), Mapping) else {}
        ref_type = text(record.get("reference_type"))
        candidates.append({
            "occurrence_id": occurrence_id,
            "case": copy.deepcopy(bundle["cases"][occurrence_id]),
            "identity_form_category": ref_type or "other",
            "category_rank": category_order.get(ref_type, 99),
            "primary_transport_valid": True,
            "independent_transport_valid": True,
            "historical_candidate_context_available": bool(row.get("candidate_proposal")),
            "selection_basis": "valid primary and independent identity transport; deterministic identity-form diversity ranking; Gold not read",
        })
    candidates.sort(key=lambda row: (int(row["category_rank"]), not row["historical_candidate_context_available"], text(row["occurrence_id"])))
    chosen: list[dict[str, Any]] = []
    seen_categories: set[str] = set()
    for item in candidates:
        category = text(item["identity_form_category"])
        if category not in seen_categories or len(chosen) >= 6:
            chosen.append(item)
            seen_categories.add(category)
        if len(chosen) == 6:
            break
    if len(chosen) < 6:
        for item in candidates:
            if item not in chosen:
                chosen.append(item)
            if len(chosen) == 6:
                break
    if len(chosen) != 6:
        raise RuntimeError("f1rt_control_cohort_less_than_six")
    chosen.sort(key=lambda row: text(row["occurrence_id"]))
    return {
        "schema": "sfh2-f1rt-arm-b-control-selection-v1",
        "selection_rule": "deterministic valid-primary-and-independent identity transport controls with identity-form diversity; no Gold or answer labels",
        "control_count": len(chosen),
        "records": chosen,
        "candidate_only": True,
        "canonical_write_back": False,
    }


def protected_paths() -> list[str]:
    return [
        "data/generated/sfh2-a2", "data/generated/sfh2-a2r", "data/generated/sfh2-a2g", "data/generated/sfh2-a2gr",
        "data/generated/sfh2-a2o", "data/generated/sfh2-a2ot", "data/generated/sfh2-a2or", "data/generated/sfh2-a2os", "data/generated/sfh2-a2osp", "data/generated/sfh2-a2ov", "data/generated/sfh2-a2ovb",
        "data/generated/sfh2-f-prep", "data/generated/sfh2-f1", "data/generated/sfh2-f1r", "data/generated/sfh2-f1rp",
        "data/frozen/sfh2/semantic-v1", "data/frozen/sfh2/identity-v1", "data/frozen/sfh2/production-policy-v2",
        "data/annotation/sfh2-a2o-evaluation-gold.json", "data/annotation/sfh2-f1rp-human-authority.json", "data/annotation/sfh2-reviewed-candidate-person-registry.json", "data/annotation/sfh2-f1-reviewed-controls.json",
        "data/derived/sc1-site.json", "data/derived/sc1-current-site.json", "data/people.json", "data/aliases.json",
        "data/derived/h0c-historical-facts.json", "data/derived/x1-2a-canonical-facts.json",
    ]


def protected_snapshot() -> dict[str, Any]:
    result: dict[str, Any] = {}
    for relative in protected_paths():
        path = ROOT / relative
        if path.is_file():
            result[relative] = {"sha256": file_hash(path), "size_bytes": path.stat().st_size}
        elif path.is_dir():
            files = {
                str(child.relative_to(ROOT)): file_hash(child)
                for child in sorted(path.rglob("*"))
                if child.is_file()
            }
            result[relative] = {"file_count": len(files), "sha256_by_file": files}
    return result


def snapshot_diff(before: Mapping[str, Any], after: Mapping[str, Any]) -> list[str]:
    changed: list[str] = []
    for path in sorted(set(before) | set(after)):
        if before.get(path) != after.get(path):
            changed.append(path)
    return changed


def code_hashes() -> dict[str, str]:
    paths = [
        "scripts/sfh2_f1rt/common.py", "scripts/sfh2_f1rt/transport.py", "scripts/run_sfh2_f1rt.py",
        "scripts/sfh2_f1/common.py", "scripts/sfh2_f1/pipeline.py", "scripts/sfh2_a0r/contracts.py", "scripts/sfh2_a0r/pipeline.py",
        "scripts/sfh2_a2/contracts.py", "scripts/sfh2_a2/pipeline.py", "scripts/sfh2_a2/comparison.py", "scripts/sfh2_a2r/contracts.py", "scripts/sfh2_a2r/pipeline.py",
        "scripts/sfh2_a2ovb/contracts.py", "scripts/sfh2_a2ovb/common.py", "scripts/sfh2_a2ovb/prompt.py", "scripts/sfh2_a0/schemas.py",
    ]
    return {path: file_hash(ROOT / path) for path in paths if (ROOT / path).is_file()}


def f1_identity_row(bundle: Mapping[str, Any], occurrence_id: str) -> Mapping[str, Any]:
    return bundle["identity_results"][occurrence_id]


def f1rp_human_artifacts_hashes() -> dict[str, str]:
    return {
        path: file_hash(ROOT / path)
        for path in (
            "data/annotation/sfh2-f1rp-human-authority.json",
            "data/annotation/sfh2-reviewed-candidate-person-registry.json",
            "data/annotation/sfh2-f1-reviewed-controls.json",
        )
        if (ROOT / path).is_file()
    }


def source_hashes(bundle: Mapping[str, Any]) -> dict[str, str]:
    paths = [
        F1_PREP_ROOT / "f1-selection.json", F1_ROOT / "identity-results.json",
        F1R_ROOT / "transport-failure-audit.json", F1RP_ROOT / "transport-recovery-handoff.json",
        SEMANTIC_ROOT / "manifest.json", IDENTITY_MANIFEST,
    ]
    return {str(path.relative_to(ROOT)): file_hash(path) for path in paths if path.is_file()}


def candidate_envelope(case: Mapping[str, Any], request_hash: str, stage: str, record: Mapping[str, Any] | None = None) -> dict[str, Any]:
    key = exact_key(case)
    envelope = {
        "case_id": key["case_id"],
        "occurrence_id": key["occurrence_id"],
        "mention_id": key["mention_id"],
        "story_id": key["story_id"],
        "source_evidence_id": key["source_evidence_id"],
        "source_start": key["source_start"],
        "source_end": key["source_end"],
        "surface": key["surface"],
        "request_hash": request_hash,
        "stage_id": stage,
        "pipeline_id": "sfh2-f1rt",
        "candidate_only": True,
        "canonical_write_back": False,
    }
    if isinstance(record, Mapping):
        envelope["semantic_body_hash"] = stable_hash(record)
    return envelope


def human_safe_record(row: Mapping[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(row, Mapping):
        return None
    return {
        key: copy.deepcopy(row.get(key))
        for key in ("valid", "contract_status", "errors", "record", "semantic_body", "transport")
        if key in row
    }
