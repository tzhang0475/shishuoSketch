#!/usr/bin/env python3
"""Shared DS2 pilot contracts over the existing DS1.2 local-evidence loop."""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any, Iterable, Mapping

try:
    from .ds1_2_common import (
        ALLOWED_SOURCE_LAYERS,
        MAX_TOP_K,
        MAX_TOOL_ROUNDS,
        ROOT,
        SEARCHED_SOURCE_PATHS,
        DS1_2_TOOLS,
        EvidenceRecord,
        build_evidence_registry,
        build_story_minimal_input,
        input_hash,
        project_status_for_record,
        run_tool_loop,
        source_hashes,
        stable_json,
    )
    from .ds1_2r_common import DeduplicatingLocalEvidenceSearch
    from .ds1_common import read_json, sha256_file, write_json
except ImportError:  # pragma: no cover - direct script execution fallback
    from ds1_2_common import (
        ALLOWED_SOURCE_LAYERS,
        MAX_TOP_K,
        MAX_TOOL_ROUNDS,
        ROOT,
        SEARCHED_SOURCE_PATHS,
        DS1_2_TOOLS,
        EvidenceRecord,
        build_evidence_registry,
        build_story_minimal_input,
        input_hash,
        project_status_for_record,
        run_tool_loop,
        source_hashes,
        stable_json,
    )
    from ds1_2r_common import DeduplicatingLocalEvidenceSearch
    from ds1_common import read_json, sha256_file, write_json


PILOT_STORIES = (
    "27-jiajue-008",
    "05-fangzheng-032",
    "02-yanyu-036",
    "19-xianyuan-026",
    "09-pinzao-017",
    "02-yanyu-035",
    "06-yaliang-017",
)
STAGE = "DS2"
MODEL = "deepseek-v4-flash"
PROMPT_VERSION = "ds2-context-generalization-pilot-v1"
OUTPUT_DIR = Path("data/generated/ds2")
SUMMARY_PATH = OUTPUT_DIR / "pilot-summary.json"
REVIEW_PATH = Path("data/annotation/ds2-pilot-review.json")
MAX_READER_CONTEXT = 4

EPISTEMIC_STATUSES = {"attested", "supported_inference", "uncertain", "conflicted"}
PROJECT_STATUSES = {"accepted", "not_materialized", "disputed", "unknown"}
CONFLICT_TYPES = {"identity_resolution", "participant_scope", "relation", "temporal", "other"}
CONFLICT_CONFIDENCES = {"high", "medium", "low"}
CONFLICTED_ASSERTIONS = {"disputed", "conjectural"}
UNCERTAIN_ASSERTIONS = {"unknown", "unresolved", "possible", "probable"}

FINAL_FIELDS = (
    "historical_situation",
    "participant_historical_states",
    "relationship_state",
    "reader_needed_context",
    "context_to_text_links",
    "uncertainties",
    "data_conflicts",
)
HISTORICAL_SITUATION_FIELDS = (
    "immediate_precondition",
    "stakes",
    "scene_power_structure",
    "evidence_refs",
    "epistemic_status",
    "project_status",
)

SYSTEM_PROMPT = """You are reconstructing the minimum historical context needed to understand one Shishuo scene.
Use only the supplied Story input and evidence returned by the two controlled local tools. Do not use pretrained knowledge, web search, or invented retrieval.
Ask four questions: what historical information is missing but needed; what historical state each important participant is in at this moment; what the relationship state is between important participants in THIS scene; and which 2–4 context items most materially improve a reader's understanding.
Your goal is not to collect all relevant history. Prefer omission over completeness. Do not include general biography, unrelated facts, textual variants unless essential, literary appreciation, 余韵, or authorial intent.
Data-conflict detection is a side effect. Investigate a conflict only when it materially blocks scene understanding; never silently overwrite a reviewed identity or relation.
Preserve evidence metadata. assertion_status and source_layer describe the source assertion; review_status/project_status describes project acceptance. not_materialized is not the same as disputed. A genuinely disputed source may require epistemic_status=conflicted; insufficient or uncertain support uses uncertain.
Every substantive claim must cite evidence_ref values actually returned by search_local_evidence. Every claim must include epistemic_status and project_status. Every reader_needed_context item must include why_needed. If evidence is insufficient, abstain explicitly.
Return JSON only with exactly these top-level fields:
historical_situation, participant_historical_states, relationship_state, reader_needed_context, context_to_text_links, uncertainties, data_conflicts.
historical_situation is one object with immediate_precondition, stakes, scene_power_structure, evidence_refs, epistemic_status, project_status.
"""


def build_initial_messages(minimal_input: Mapping[str, Any]) -> list[dict[str, Any]]:
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "user",
            "content": "Begin from this minimal reviewed Story input. Search only when additional evidence is needed, and synthesize the fixed JSON contract when sufficient.\n\n"
            + stable_json(minimal_input),
        },
    ]


def _record_conflicted(record: EvidenceRecord) -> bool:
    return (
        (record.assertion_status or "").strip().lower() in CONFLICTED_ASSERTIONS
        or project_status_for_record(record) == "disputed"
    )


def _record_uncertain(record: EvidenceRecord) -> bool:
    return (record.assertion_status or "").strip().lower() in UNCERTAIN_ASSERTIONS


def project_status_for_refs(refs: Iterable[str], registry: Mapping[str, EvidenceRecord]) -> str:
    records = [registry[ref] for ref in refs if ref in registry]
    if not records:
        return "unknown"
    statuses = {project_status_for_record(record) for record in records}
    if "disputed" in statuses:
        return "disputed"
    if "unknown" in statuses:
        return "unknown"
    if "not_materialized" in statuses:
        return "not_materialized"
    return "accepted"


def normalize_epistemic_status(
    status: Any,
    refs: Iterable[str],
    registry: Mapping[str, EvidenceRecord],
) -> str:
    refs = list(refs)
    if any(_record_conflicted(registry[ref]) for ref in refs if ref in registry):
        return "conflicted"
    if any(_record_uncertain(registry[ref]) for ref in refs if ref in registry):
        if status in {"attested", "supported_inference"}:
            return "uncertain"
    if status == "conflicted":
        # A model-supplied conflict label is not source evidence by itself.
        # Only the registered evidence status above can promote a claim to
        # ``conflicted``; project ``not_materialized`` remains separate.
        return "uncertain"
    if status == "uncertain":
        return "uncertain"
    if status == "attested":
        return "attested"
    if status == "supported_inference":
        return "supported_inference"
    return "uncertain" if not refs else "supported_inference"


def _unwrap_claim_collection(value: Any) -> Any:
    if isinstance(value, Mapping) and isinstance(value.get("claim_objects"), list):
        return value["claim_objects"]
    return value


def _normalize_claim_row(
    row: Mapping[str, Any],
    registry: Mapping[str, EvidenceRecord],
    *,
    extra_fields: Iterable[str] = (),
) -> dict[str, Any]:
    refs = row.get("evidence_refs", [])
    if not isinstance(refs, list):
        refs = []
    normalized = {key: row.get(key) for key in extra_fields}
    normalized["text"] = row.get("text")
    normalized["evidence_refs"] = [str(ref) for ref in refs if isinstance(ref, str)]
    normalized["epistemic_status"] = normalize_epistemic_status(
        row.get("epistemic_status"), normalized["evidence_refs"], registry
    )
    normalized["project_status"] = project_status_for_refs(normalized["evidence_refs"], registry)
    return normalized


def _normalize_conflicts(value: Any, retrieved: set[str]) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    result: list[dict[str, Any]] = []
    for row in value:
        if not isinstance(row, Mapping):
            continue
        refs = row.get("evidence_refs", [])
        refs = [str(ref) for ref in refs if isinstance(ref, str) and ref in retrieved] if isinstance(refs, list) else []
        if not refs:
            continue
        conflict_type = row.get("conflict_type")
        if conflict_type not in CONFLICT_TYPES:
            conflict_type = "other"
        existing = row.get("existing_record")
        suggested = row.get("suggested_resolution")
        if not isinstance(existing, Mapping):
            existing = {"model_value": existing}
        if not isinstance(suggested, Mapping):
            suggested = {"model_value": suggested, "not_applied": True}
        else:
            suggested = dict(suggested)
            suggested.setdefault("not_applied", True)
        result.append(
            {
                "conflict_type": conflict_type,
                "existing_record": dict(existing),
                "suggested_resolution": suggested,
                "reason": str(row.get("reason", "需要人工核查的结构化数据冲突")),
                "evidence_refs": sorted(set(refs)),
                "confidence": row.get("confidence") if row.get("confidence") in CONFLICT_CONFIDENCES else "low",
                "action": "human_review_required",
            }
        )
    return sorted(result, key=stable_json)


def normalize_ds2_result(
    result: Mapping[str, Any],
    retrieved_refs: Iterable[str],
    registry: Mapping[str, EvidenceRecord],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    normalized = deepcopy(dict(result))
    adjustments: list[dict[str, Any]] = []
    retrieved = set(retrieved_refs)

    if "relationship_state" not in normalized:
        normalized["relationship_state"] = normalized.get(
            "relationship_state_before_scene", normalized.get("relationship_context", [])
        )
    for field in FINAL_FIELDS:
        if field != "historical_situation" and normalized.get(field) is None:
            normalized[field] = []
    for field in ("participant_historical_states", "relationship_state", "reader_needed_context", "context_to_text_links", "uncertainties"):
        normalized[field] = _unwrap_claim_collection(normalized.get(field, []))
        if not isinstance(normalized[field], list):
            normalized[field] = []

    situation = normalized.get("historical_situation")
    if not isinstance(situation, Mapping):
        situation = {}
    situation = {
        "immediate_precondition": situation.get("immediate_precondition"),
        "stakes": situation.get("stakes"),
        "scene_power_structure": situation.get("scene_power_structure"),
        "evidence_refs": [ref for ref in situation.get("evidence_refs", []) if isinstance(ref, str)]
        if isinstance(situation.get("evidence_refs", []), list)
        else [],
    }
    situation["epistemic_status"] = normalize_epistemic_status(
        normalized.get("historical_situation", {}).get("epistemic_status")
        if isinstance(normalized.get("historical_situation"), Mapping)
        else None,
        situation["evidence_refs"],
        registry,
    )
    situation["project_status"] = project_status_for_refs(situation["evidence_refs"], registry)
    normalized["historical_situation"] = situation

    participants: list[dict[str, Any]] = []
    for row in normalized["participant_historical_states"]:
        if not isinstance(row, Mapping):
            continue
        claims = row.get("claim_objects") if isinstance(row.get("claim_objects"), list) else [row]
        for claim in claims:
            if isinstance(claim, Mapping):
                participants.append(_normalize_claim_row(claim, registry, extra_fields=("person_id",)))
    normalized["participant_historical_states"] = participants

    for field in ("relationship_state", "reader_needed_context", "context_to_text_links", "uncertainties"):
        rows: list[dict[str, Any]] = []
        for row in normalized[field]:
            if not isinstance(row, Mapping):
                continue
            if field == "reader_needed_context":
                item = _normalize_claim_row(row, registry)
                item["why_needed"] = row.get("why_needed")
            elif field == "context_to_text_links":
                refs = row.get("evidence_refs", [])
                refs = [str(ref) for ref in refs if isinstance(ref, str)] if isinstance(refs, list) else []
                item = {
                    "context": row.get("context"),
                    "text_span": row.get("text_span"),
                    "reading_effect": row.get("reading_effect"),
                    "evidence_refs": refs,
                    "epistemic_status": normalize_epistemic_status(row.get("epistemic_status"), refs, registry),
                    "project_status": project_status_for_refs(refs, registry),
                }
            else:
                item = _normalize_claim_row(row, registry)
            rows.append(item)
        normalized[field] = rows
    if len(normalized["reader_needed_context"]) > MAX_READER_CONTEXT:
        adjustments.append(
            {
                "field": "reader_needed_context",
                "from_count": len(normalized["reader_needed_context"]),
                "to_count": MAX_READER_CONTEXT,
                "reason": "fixed reader relevance budget",
            }
        )
        normalized["reader_needed_context"] = normalized["reader_needed_context"][:MAX_READER_CONTEXT]

    normalized["data_conflicts"] = _normalize_conflicts(normalized.get("data_conflicts", []), retrieved)
    return normalized, adjustments


def validate_ds2_result(
    result: Any,
    retrieved_refs: Iterable[str],
    registry: Mapping[str, EvidenceRecord],
) -> list[str]:
    retrieved = set(retrieved_refs)
    if not isinstance(result, Mapping) or set(result) != set(FINAL_FIELDS):
        return ["DS2 result top-level fields are invalid"]
    errors: list[str] = []
    situation = result["historical_situation"]
    if not isinstance(situation, Mapping) or set(situation) != set(HISTORICAL_SITUATION_FIELDS):
        errors.append("historical_situation shape is invalid")
    else:
        errors.extend(_validate_claim(situation, retrieved, registry, "historical_situation"))
    for field in ("participant_historical_states", "relationship_state", "reader_needed_context", "context_to_text_links", "uncertainties"):
        rows = result[field]
        if not isinstance(rows, list):
            errors.append(f"{field} must be an array")
            continue
        if field == "reader_needed_context" and len(rows) > MAX_READER_CONTEXT:
            errors.append("reader_needed_context exceeds four items")
        for index, row in enumerate(rows):
            if not isinstance(row, Mapping):
                errors.append(f"{field}[{index}] is not an object")
                continue
            required = {"evidence_refs", "epistemic_status", "project_status"}
            if field == "participant_historical_states":
                required.update({"person_id", "text"})
            elif field == "reader_needed_context":
                required.update({"text", "why_needed"})
            elif field == "context_to_text_links":
                required.update({"context", "text_span", "reading_effect"})
            else:
                required.add("text")
            errors.extend(_validate_claim(row, retrieved, registry, f"{field}[{index}]", required_fields=required))
    conflicts = result["data_conflicts"]
    if not isinstance(conflicts, list):
        errors.append("data_conflicts must be an array")
    else:
        for index, row in enumerate(conflicts):
            if not isinstance(row, Mapping):
                errors.append(f"data_conflicts[{index}] is not an object")
                continue
            fields = {"conflict_type", "existing_record", "suggested_resolution", "reason", "evidence_refs", "confidence", "action"}
            if set(row) != fields:
                errors.append(f"data_conflicts[{index}] shape is invalid")
                continue
            refs = row.get("evidence_refs")
            if row.get("conflict_type") not in CONFLICT_TYPES or row.get("confidence") not in CONFLICT_CONFIDENCES:
                errors.append(f"data_conflicts[{index}] enum is invalid")
            if not isinstance(refs, list) or not refs or not set(refs).issubset(retrieved):
                errors.append(f"data_conflicts[{index}] evidence_refs are invalid")
            if row.get("action") != "human_review_required":
                errors.append(f"data_conflicts[{index}] action is invalid")
    return sorted(errors)


def _validate_claim(
    row: Mapping[str, Any],
    retrieved: set[str],
    registry: Mapping[str, EvidenceRecord],
    path: str,
    *,
    require_text: bool = True,
    required_fields: set[str] | None = None,
) -> list[str]:
    fields = required_fields or set(HISTORICAL_SITUATION_FIELDS)
    errors: list[str] = []
    if set(row) != fields:
        errors.append(f"{path} keys are invalid")
        return errors
    refs = row.get("evidence_refs")
    if not isinstance(refs, list) or not all(isinstance(ref, str) for ref in refs):
        errors.append(f"{path}.evidence_refs are invalid")
        return errors
    if set(refs) - retrieved:
        errors.append(f"{path} cites evidence not retrieved")
    substantive = any(row.get(key) not in (None, "", []) for key in fields if key not in {"evidence_refs", "epistemic_status", "project_status"})
    if require_text and substantive and not refs:
        errors.append(f"{path} has a substantive claim without evidence")
    if row.get("epistemic_status") not in EPISTEMIC_STATUSES:
        errors.append(f"{path}.epistemic_status is invalid")
    if row.get("project_status") not in PROJECT_STATUSES:
        errors.append(f"{path}.project_status is invalid")
    expected_project = project_status_for_refs(refs, registry)
    if row.get("project_status") != expected_project:
        errors.append(f"{path}.project_status does not match evidence status")
    if expected_project == "not_materialized" and row.get("epistemic_status") == "conflicted":
        if not any(_record_conflicted(registry[ref]) for ref in refs if ref in registry):
            errors.append(f"{path} treats not_materialized alone as conflicted")
    return errors


def protected_hashes(root: Path = ROOT) -> dict[str, str]:
    """Snapshot all pre-existing research/frontend inputs, excluding DS2 output."""

    paths: list[Path] = []
    for base in (Path("data/derived"), Path("data/annotation"), Path("data/generated"), Path("site/src")):
        directory = root / base
        if not directory.is_dir():
            continue
        for path in directory.rglob("*"):
            relative = path.relative_to(root)
            if path.is_file() and relative.as_posix() != REVIEW_PATH.as_posix() and not relative.as_posix().startswith("data/generated/ds2/"):
                paths.append(relative)
    return {path.as_posix(): sha256_file(root, path) for path in sorted(paths, key=lambda item: item.as_posix())}


def summary_record(
    story_id: str,
    *,
    trace: Mapping[str, Any] | None,
    candidate: Mapping[str, Any] | None,
    error_count: int,
) -> dict[str, Any]:
    loop = trace.get("loop_summary", {}) if isinstance(trace, Mapping) else {}
    dedup = trace.get("deduplication", {}) if isinstance(trace, Mapping) else {}
    result = candidate.get("result", {}) if isinstance(candidate, Mapping) else {}
    return {
        "story_id": story_id,
        "execution_status": "success" if candidate is not None and error_count == 0 else "failed",
        "tool_rounds": int(loop.get("tool_rounds", 0)) if isinstance(loop, Mapping) else 0,
        "search_calls": int(dedup.get("search_calls", 0)) if isinstance(dedup, Mapping) else 0,
        "opened_evidence_count": len(loop.get("opened_evidence_refs", [])) if isinstance(loop, Mapping) else 0,
        "retrieved_evidence_count": len(loop.get("returned_evidence_refs", [])) if isinstance(loop, Mapping) else 0,
        "data_conflict_count": len(result.get("data_conflicts", [])) if isinstance(result, Mapping) else 0,
        "reader_context_count": len(result.get("reader_needed_context", [])) if isinstance(result, Mapping) else 0,
        "uncertainty_count": len(result.get("uncertainties", [])) if isinstance(result, Mapping) else 0,
        "final_validation_errors": error_count,
    }


def review_template() -> dict[str, Any]:
    return {
        "schema": "ds2-pilot-review",
        "schema_version": 1,
        "records": [
            {
                "story_id": story_id,
                "evidence_seeking": None,
                "scene_reconstruction": None,
                "relationship_understanding": None,
                "context_selection": None,
                "restraint": None,
                "notes": "",
            }
            for story_id in PILOT_STORIES
        ],
    }


__all__ = [
    "ALLOWED_SOURCE_LAYERS",
    "DS1_2_TOOLS",
    "DeduplicatingLocalEvidenceSearch",
    "FINAL_FIELDS",
    "MAX_READER_CONTEXT",
    "MAX_TOP_K",
    "MAX_TOOL_ROUNDS",
    "MODEL",
    "OUTPUT_DIR",
    "PILOT_STORIES",
    "PROMPT_VERSION",
    "REVIEW_PATH",
    "ROOT",
    "SEARCHED_SOURCE_PATHS",
    "STAGE",
    "SUMMARY_PATH",
    "build_evidence_registry",
    "build_initial_messages",
    "build_story_minimal_input",
    "input_hash",
    "normalize_ds2_result",
    "protected_hashes",
    "review_template",
    "run_tool_loop",
    "source_hashes",
    "stable_json",
    "summary_record",
    "validate_ds2_result",
    "write_json",
]
