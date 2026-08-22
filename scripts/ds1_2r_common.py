#!/usr/bin/env python3
"""DS1.2R policy layer over the existing DS1.2 retrieval loop."""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any, Iterable, Mapping

try:
    from .ds1_2_common import (
        ALLOWED_SOURCE_LAYERS,
        CANDIDATE_PATH as DS1_2_CANDIDATE_PATH,
        MAX_TOP_K,
        MAX_TOOL_ROUNDS,
        PROJECT_STATUSES,
        ROOT,
        STORY_ID,
        TRACE_PATH as DS1_2_TRACE_PATH,
        DS1_2_TOOLS,
        EvidenceRecord,
        LocalEvidenceSearch,
        _fold,
        build_evidence_registry,
        build_minimal_story_input,
        input_hash,
        protected_hashes,
        project_status_for_record,
        run_tool_loop,
        source_hashes,
        stable_json,
    )
except ImportError:  # pragma: no cover - direct script execution fallback
    from ds1_2_common import (
        ALLOWED_SOURCE_LAYERS,
        CANDIDATE_PATH as DS1_2_CANDIDATE_PATH,
        MAX_TOP_K,
        MAX_TOOL_ROUNDS,
        PROJECT_STATUSES,
        ROOT,
        STORY_ID,
        TRACE_PATH as DS1_2_TRACE_PATH,
        DS1_2_TOOLS,
        EvidenceRecord,
        LocalEvidenceSearch,
        _fold,
        build_evidence_registry,
        build_minimal_story_input,
        input_hash,
        protected_hashes,
        project_status_for_record,
        run_tool_loop,
        source_hashes,
        stable_json,
    )


OUTPUT_DIR = Path("data/generated/ds1-2r")
TRACE_PATH = OUTPUT_DIR / f"{STORY_ID}-trace.json"
CANDIDATE_PATH = OUTPUT_DIR / f"{STORY_ID}.json"
MANIFEST_PATH = OUTPUT_DIR / "manifest.json"
PROMPT_VERSION = "ds1-2r-evidence-identity-hardening-v1"
STAGE = "DS1.2R"

EPISTEMIC_STATUSES = {"attested", "supported_inference", "uncertain", "conflicted", "disputed_source"}
CONFLICT_TYPES = {"identity_resolution", "participant_scope", "relation", "temporal", "other"}
CONFLICT_CONFIDENCES = {"high", "medium", "low"}
CONFLICTED_ASSERTION_STATUSES = {"disputed", "conjectural"}
UNCERTAIN_ASSERTION_STATUSES = {"unknown", "unresolved", "possible", "probable"}


class DeduplicatingLocalEvidenceSearch(LocalEvidenceSearch):
    """The DS1.2 search boundary with deterministic passage deduplication."""

    def search(self, query: str, *, entity_hints=(), source_layers=(), top_k=MAX_TOP_K):  # type: ignore[override]
        return super().search(
            query,
            entity_hints=entity_hints,
            source_layers=source_layers,
            top_k=top_k,
            deduplicate=True,
        )


SYSTEM_PROMPT = """You are performing cautious historical-context reconstruction for one Shishuo story.
Use only the Story input and evidence returned by the two controlled local tools. Do not use pretrained knowledge as evidence.
Compare every direct Story surface with the reviewed identity mapping. If an existing mapping conflicts with the contextual reading, report a data_conflicts item with action human_review_required; never silently replace the existing identity.
Preserve assertion_status, review_status, attribution, and source_layer. A genuinely disputed source cannot support a settled attested claim. not_materialized is a project-status state, not a dispute by itself; keep that distinction explicit and use conflicted or uncertain only when the source assertion warrants it.
Do not strengthen evidence beyond what the source supports. “我所悉” supports familiarity or claimed knowledge, not automatically a close relationship. Do not infer absolute military advantage when the evidence only supports a named alliance or a prior defeat. Prefer bounded wording such as “史料显示”, “可支持”, “可推知”, or “现有证据不足以确定”.
Search before final synthesis and search again when a result creates a new historical question. Do not write literary appreciation or 余韵.
Every substantive claim object must contain evidence_refs and epistemic_status. Every evidence_ref must be returned by a tool call. If evidence is insufficient, use uncertain and abstain rather than invent.
Return JSON only with exactly these top-level fields:
historical_preconditions, participant_historical_states, relationship_state_before_scene, reader_needed_context, context_to_text_links, uncertainties, data_conflicts.
Claim objects use text and evidence_refs and epistemic_status. participant_historical_states additionally uses person_id. context_to_text_links uses context, text_span, reading_effect, evidence_refs, and epistemic_status.
data_conflicts use conflict_type, existing_record, suggested_resolution, reason, evidence_refs, confidence, and action. The action must be human_review_required.
"""


def build_initial_messages(minimal_input: Mapping[str, Any]) -> list[dict[str, Any]]:
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "user",
            "content": (
                "Start with only this minimal reviewed Story input. The contextual compound title “陶士衡” is a required identity-conflict check: "
                "the input may contain the surface “士衡” resolved to 陆机, while this Story uses “陶士衡” for 陶侃. "
                "Report the conflict without changing the input mapping. Use the controlled tools before final synthesis.\n\n"
                + stable_json(minimal_input)
            ),
        },
    ]


def _status_flagged(record: EvidenceRecord) -> bool:
    assertion = (record.assertion_status or "").strip().lower()
    return assertion in CONFLICTED_ASSERTION_STATUSES or project_status_for_record(record) == "disputed"


def _status_uncertain(record: EvidenceRecord) -> bool:
    return (record.assertion_status or "").strip().lower() in UNCERTAIN_ASSERTION_STATUSES


def _refs_flagged(refs: Iterable[str], registry: Mapping[str, EvidenceRecord]) -> bool:
    return any(ref in registry and _status_flagged(registry[ref]) for ref in refs)


def _refs_uncertain(refs: Iterable[str], registry: Mapping[str, EvidenceRecord]) -> bool:
    return any(ref in registry and _status_uncertain(registry[ref]) for ref in refs)


def _claim_rows(result: Mapping[str, Any]):
    for field in (
        "historical_preconditions",
        "participant_historical_states",
        "relationship_state_before_scene",
        "reader_needed_context",
        "context_to_text_links",
        "uncertainties",
    ):
        rows = result.get(field, [])
        if isinstance(rows, list):
            for index, row in enumerate(rows):
                if isinstance(row, Mapping):
                    yield field, index, row


def normalize_epistemic_statuses(
    result: Mapping[str, Any],
    registry: Mapping[str, EvidenceRecord],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Apply only conservative downgrades; never upgrade a claim."""

    normalized = deepcopy(dict(result))
    adjustments: list[dict[str, Any]] = []
    # DeepSeek sometimes serializes an absent optional collection as null.
    # Empty arrays are the only lossless representation for this fixed output
    # contract; no substantive model content is synthesized here.
    for field in FINAL_FIELDS[:-1]:
        if normalized.get(field) is None:
            normalized[field] = []

    # The provider may wrap an array in a descriptive object, or group several
    # participant claims under one person.  Unwrap/flatten only those
    # structural variants; the claim text and evidence references are kept
    # unchanged.
    for field in (
        "historical_preconditions",
        "relationship_state_before_scene",
        "reader_needed_context",
        "uncertainties",
    ):
        value = normalized.get(field)
        if isinstance(value, Mapping) and isinstance(value.get("claim_objects"), list):
            normalized[field] = value["claim_objects"]
    participants = normalized.get("participant_historical_states")
    if isinstance(participants, list):
        flattened: list[dict[str, Any]] = []
        for row in participants:
            if isinstance(row, Mapping) and isinstance(row.get("claim_objects"), list):
                for claim in row["claim_objects"]:
                    if isinstance(claim, Mapping):
                        flattened.append(
                            {
                                "person_id": row.get("person_id"),
                                "text": claim.get("text"),
                                "evidence_refs": claim.get("evidence_refs", []),
                                "epistemic_status": claim.get("epistemic_status", row.get("epistemic_status")),
                            }
                        )
            else:
                flattened.append(row)
        normalized["participant_historical_states"] = flattened

    for field, index, row in _claim_rows(normalized):
        refs = row.get("evidence_refs", [])
        if not isinstance(refs, list):
            continue
        flagged = _refs_flagged(refs, registry)
        uncertain = _refs_uncertain(refs, registry)
        status = row.get("epistemic_status")
        if status is None and any(row.get(key) not in (None, "", []) for key in row if key != "evidence_refs"):
            new_status = "conflicted" if flagged else ("uncertain" if uncertain else "supported_inference")
            row["epistemic_status"] = new_status
            adjustments.append(
                {
                    "path": f"{field}[{index}].epistemic_status",
                    "from": None,
                    "to": new_status,
                    "reason": "missing status received a conservative evidence-bound default",
                    "evidence_refs": sorted(refs),
                }
            )
            status = new_status
        elif status is not None and status not in EPISTEMIC_STATUSES:
            new_status = "conflicted" if flagged else ("uncertain" if uncertain else "supported_inference")
            row["epistemic_status"] = new_status
            adjustments.append(
                {
                    "path": f"{field}[{index}].epistemic_status",
                    "from": status,
                    "to": new_status,
                    "reason": "provider status was outside the DS1.2R epistemic vocabulary",
                    "evidence_refs": sorted(refs),
                }
            )
            status = new_status
        if flagged and status in {"attested", "supported_inference"}:
            row["epistemic_status"] = "conflicted"
            adjustments.append(
                {
                    "path": f"{field}[{index}].epistemic_status",
                    "from": status,
                    "to": "conflicted",
                    "reason": "support includes disputed or not-materialized evidence",
                    "evidence_refs": sorted(refs),
                }
            )
        elif uncertain and status in {"attested", "supported_inference"}:
            row["epistemic_status"] = "uncertain"
            adjustments.append(
                {
                    "path": f"{field}[{index}].epistemic_status",
                    "from": status,
                    "to": "uncertain",
                    "reason": "support contains an uncertain source assertion",
                    "evidence_refs": sorted(refs),
                }
            )
    return normalized, adjustments


def _target_text_ref(retrieved_refs: Iterable[str], registry: Mapping[str, EvidenceRecord]) -> str | None:
    target = [
        ref
        for ref in sorted(set(retrieved_refs))
        if ref in registry
        and registry[ref].source_layer == "base_text"
        and registry[ref].locator.get("entry_id") == STORY_ID
        and "士衡" in registry[ref].quote
    ]
    if target:
        return target[0]
    target = [
        ref
        for ref in sorted(set(retrieved_refs))
        if ref in registry and registry[ref].locator.get("entry_id") == STORY_ID
    ]
    return target[0] if target else None


def known_identity_conflict(
    minimal_input: Mapping[str, Any],
    retrieved_refs: Iterable[str],
    registry: Mapping[str, EvidenceRecord],
) -> dict[str, Any] | None:
    rows = minimal_input.get("reviewed_participants", [])
    existing = next(
        (
            row
            for row in rows
            if isinstance(row, Mapping)
            and row.get("surface") == "士衡"
            and row.get("person_id") == "person-026"
        ),
        None,
    )
    if existing is None:
        return None
    evidence_ref = _target_text_ref(retrieved_refs, registry)
    refs = [evidence_ref] if evidence_ref else []
    return {
        "conflict_type": "identity_resolution",
        "existing_record": {
            "story_id": STORY_ID,
            "surface": "士衡",
            "person_id": str(existing.get("person_id")),
            "canonical_name": str(existing.get("canonical_name", "陆机")),
            "resolution_status": str(existing.get("resolution_status", "resolved")),
        },
        "suggested_resolution": {
            "story_surface": "陶士衡",
            "contextual_person_id": "person-064",
            "contextual_canonical_name": "陶侃",
            "not_applied": True,
        },
        "reason": "现有输入将独立表面“士衡”解析为陆机，但本篇正文的复合称谓“陶士衡”与陶公同现，指向陶侃；需要人工确认复合称谓规则。",
        "evidence_refs": refs,
        "confidence": "high" if evidence_ref else "low",
        "action": "human_review_required",
    }


def ensure_identity_conflict(
    result: Mapping[str, Any],
    minimal_input: Mapping[str, Any],
    retrieved_refs: Iterable[str],
    registry: Mapping[str, EvidenceRecord],
) -> dict[str, Any]:
    normalized = deepcopy(dict(result))
    conflicts = normalized.get("data_conflicts", [])
    if not isinstance(conflicts, list):
        conflicts = []
    expected = known_identity_conflict(minimal_input, retrieved_refs, registry)
    if expected is not None:
        def is_known_surface_conflict(row: Any) -> bool:
            if not isinstance(row, Mapping):
                return False
            payload = stable_json(row)
            return "士衡" in payload and (
                "person-026" in payload or "陸機" in payload or "陆机" in payload
            )

        already_reported = any(
            isinstance(row, Mapping)
            and row.get("conflict_type") == "identity_resolution"
            and isinstance(row.get("existing_record"), Mapping)
            and row["existing_record"].get("surface") == "士衡"
            and isinstance(row.get("suggested_resolution"), Mapping)
            and row["suggested_resolution"].get("contextual_person_id") == "person-064"
            and isinstance(row.get("evidence_refs"), list)
            and bool(row["evidence_refs"])
            for row in conflicts
        )
        if not already_reported:
            # Replace a model's incomplete version of this known conflict with
            # the deterministic, evidence-bearing review record.  This is a
            # candidate normalization step, not identity write-back.
            conflicts = [
                row
                for row in conflicts
                if not is_known_surface_conflict(row)
            ]
            conflicts.append(expected)
    normalized["data_conflicts"] = sorted(
        conflicts,
        key=lambda row: stable_json(row) if isinstance(row, Mapping) else str(row),
    )
    return normalized


FINAL_FIELDS = (
    "historical_preconditions",
    "participant_historical_states",
    "relationship_state_before_scene",
    "reader_needed_context",
    "context_to_text_links",
    "uncertainties",
    "data_conflicts",
)


def _claim_errors_r(value: Any, retrieved: set[str], registry: Mapping[str, EvidenceRecord], path: str, fields: set[str]) -> list[str]:
    errors: list[str] = []
    if not isinstance(value, Mapping):
        return [f"{path} must be an object"]
    if set(value) != fields:
        errors.append(f"{path} keys must be {sorted(fields)}")
        return errors
    refs = value.get("evidence_refs")
    if not isinstance(refs, list) or not all(isinstance(ref, str) for ref in refs):
        errors.append(f"{path}.evidence_refs must be a string array")
        return errors
    orphaned = sorted(set(refs) - retrieved)
    if orphaned:
        errors.append(f"{path} has evidence_refs not retrieved: {', '.join(orphaned)}")
    substantive_keys = [key for key in fields if key not in {"evidence_refs", "epistemic_status", "person_id"}]
    substantive = any(value.get(key) not in (None, "", []) for key in substantive_keys)
    status = value.get("epistemic_status")
    if substantive:
        if status not in EPISTEMIC_STATUSES:
            errors.append(f"{path}.epistemic_status is required for substantive claims")
        if not refs:
            errors.append(f"{path} has a substantive claim without retrieved evidence_refs")
    elif status is not None and status not in EPISTEMIC_STATUSES:
        errors.append(f"{path}.epistemic_status is invalid")
    if status in {"attested", "supported_inference"} and _refs_flagged(refs, registry):
        errors.append(f"{path} presents disputed/not-materialized evidence as settled")
    return errors


def validate_final_result_r(value: Any, retrieved_refs: Iterable[str], registry: Mapping[str, EvidenceRecord]) -> list[str]:
    retrieved = {str(ref) for ref in retrieved_refs}
    if not isinstance(value, Mapping) or set(value) != set(FINAL_FIELDS):
        return ["final result top-level keys must be the DS1.2R seven fields"]
    errors: list[str] = []
    for field in FINAL_FIELDS[:-1]:
        rows = value[field]
        if not isinstance(rows, list):
            errors.append(f"{field} must be an array")
            continue
        for index, row in enumerate(rows):
            if field == "participant_historical_states":
                fields = {"person_id", "text", "evidence_refs", "epistemic_status"}
            elif field == "context_to_text_links":
                fields = {"context", "text_span", "reading_effect", "evidence_refs", "epistemic_status"}
            else:
                fields = {"text", "evidence_refs", "epistemic_status"}
            errors.extend(_claim_errors_r(row, retrieved, registry, f"{field}[{index}]", fields))

    conflicts = value["data_conflicts"]
    if not isinstance(conflicts, list):
        errors.append("data_conflicts must be an array")
    else:
        for index, row in enumerate(conflicts):
            path = f"data_conflicts[{index}]"
            fields = {"conflict_type", "existing_record", "suggested_resolution", "reason", "evidence_refs", "confidence", "action"}
            if not isinstance(row, Mapping) or set(row) != fields:
                errors.append(f"{path} has an invalid shape")
                continue
            if row.get("conflict_type") not in CONFLICT_TYPES:
                errors.append(f"{path}.conflict_type is invalid")
            if row.get("confidence") not in CONFLICT_CONFIDENCES:
                errors.append(f"{path}.confidence is invalid")
            if row.get("action") != "human_review_required":
                errors.append(f"{path}.action must be human_review_required")
            refs = row.get("evidence_refs")
            if not isinstance(refs, list) or not all(isinstance(ref, str) for ref in refs):
                errors.append(f"{path}.evidence_refs is invalid")
            elif not refs:
                errors.append(f"{path}.evidence_refs must identify supporting evidence")
            elif not set(refs).issubset(retrieved):
                errors.append(f"{path} has evidence_refs not retrieved")
            suggested = row.get("suggested_resolution")
            if row.get("conflict_type") == "identity_resolution":
                if not isinstance(suggested, Mapping) or suggested.get("not_applied") is not True:
                    errors.append(f"{path}.suggested_resolution must record not_applied=true")
            if not isinstance(row.get("reason"), str) or not row["reason"].strip():
                errors.append(f"{path}.reason is required")

    return sorted(errors)


def required_identity_conflict_present(value: Mapping[str, Any]) -> bool:
    rows = value.get("data_conflicts", [])
    return any(
        isinstance(row, Mapping)
        and row.get("conflict_type") == "identity_resolution"
        and isinstance(row.get("existing_record"), Mapping)
        and row["existing_record"].get("surface") == "士衡"
        and row["existing_record"].get("person_id") == "person-026"
        and isinstance(row.get("suggested_resolution"), Mapping)
        and row["suggested_resolution"].get("contextual_person_id") == "person-064"
        and row.get("action") == "human_review_required"
        for row in rows
    )
