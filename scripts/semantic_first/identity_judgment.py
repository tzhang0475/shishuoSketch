"""L5 LLM historical identity assessment over Python-owned candidate keys."""

from __future__ import annotations

from typing import Any, Mapping

from .candidate_retrieval import candidate_evidence
from .common import StrictStageClient, text
from .schemas import ASSESSMENT_VERDICTS, RESOLUTIONS, identity_tool
from .source_packets import evidence_index

SYSTEM = """Assess whether each supplied candidate is the historical referent of each validated mention. Candidate keys are temporary Python keys; never invent or alter them and never emit Person IDs. Judge historical identity, not mere coexistence or chronology compatibility. Cite only supplied evidence IDs. A candidate may be plausible without being supported. Return candidate_missing when the supplied set lacks the likely referent, and insufficient_evidence when the text does not decide. Return only the forced structured function."""


def prompt(packet: Mapping[str, Any], ledger: Mapping[str, Any], semantics: Mapping[str, Any], candidate_sets: Mapping[str, Any], target_ids: set[str] | None = None) -> dict[str, Any]:
    mentions = {text(row.get("mention_id")): row for row in ledger.get("valid_mentions", []) or []}
    semantic_index = {text(row.get("mention_id")): row for row in semantics.get("records", []) or []}
    cases: list[dict[str, Any]] = []
    for row in candidate_sets.get("records", []) or []:
        if not row.get("candidates"):
            continue
        mention_id = text(row.get("mention_id"))
        if target_ids is not None and mention_id not in target_ids:
            continue
        cases.append({
            "mention": mentions.get(mention_id),
            "reference_semantics": semantic_index.get(mention_id),
            "candidates": [
                {
                    "candidate_key": candidate.get("candidate_key"),
                    "name": candidate.get("display_name"),
                    "entity_type": candidate.get("entity_type"),
                    "matched_surface": candidate.get("matched_surface"),
                    "retrieval_basis": candidate.get("retrieval_basis"),
                    "evidence": candidate.get("evidence", []),
                }
                for candidate in row.get("candidates", []) or []
            ],
        })
    return {
        "task": "historical identity judgment for supplied candidates",
        "story_id": packet.get("story_id"),
        "source_evidence": [
            {"evidence_id": item.get("evidence_id"), "source_layer": item.get("source_layer"), "text": item.get("text")}
            for item in packet.get("evidence", []) or []
        ],
        "cases": cases,
    }


def judge_identities(client: StrictStageClient, packet: Mapping[str, Any], ledger: Mapping[str, Any], semantics: Mapping[str, Any], candidate_sets: Mapping[str, Any]) -> Mapping[str, Any] | None:
    case_ids = [text(row.get("mention_id")) for row in candidate_sets.get("records", []) or [] if row.get("candidates")]
    if not case_ids:
        return {"judgments": []}
    tool = identity_tool()
    judgments: list[Any] = []
    provider_failure = False
    chunk_size = 4
    for index in range(0, len(case_ids), chunk_size):
        target_ids = set(case_ids[index:index + chunk_size])
        response = client.call(
            stage="identity_judgment",
            unit_id=f"{packet.get('story_id')}-part{index // chunk_size + 1}",
            system=SYSTEM,
            payload=prompt(packet, ledger, semantics, candidate_sets, target_ids),
            function=tool,
            function_name=tool["function"]["name"],
            max_tokens=3000,
        )
        if not isinstance(response, Mapping) or not isinstance(response.get("judgments"), list):
            provider_failure = True
            continue
        judgments.extend(response.get("judgments", []) or [])
    return {"judgments": judgments, "_provider_failure": provider_failure}


def validate_identity_judgments(packet: Mapping[str, Any], candidate_sets: Mapping[str, Any], payload: Mapping[str, Any] | None) -> dict[str, Any]:
    candidate_records = {text(row.get("mention_id")): dict(row) for row in candidate_sets.get("records", []) or []}
    source_ids = set(evidence_index(packet))
    rows = payload.get("judgments") if isinstance(payload, Mapping) else None
    if not isinstance(rows, list):
        return {"story_id": packet.get("story_id"), "judgments": [], "rejected": [{"reason": "provider_or_schema_failure"}], "provider_failure": True}
    accepted: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    seen: set[str] = set()
    for index, raw in enumerate(rows):
        if not isinstance(raw, Mapping):
            rejected.append({"index": index, "reason": "judgment_not_object"})
            continue
        mention_id = text(raw.get("mention_id"))
        record = candidate_records.get(mention_id)
        errors: list[str] = []
        if not record or mention_id in seen:
            errors.append("unknown_or_duplicate_mention")
            record = {"candidates": []}
        keys = {text(row.get("candidate_key")) for row in record.get("candidates", []) or []}
        evidence_ids = source_ids | {text(item.get("evidence_id")) for item in candidate_evidence(record)}
        assessments = raw.get("candidate_assessments")
        if not isinstance(assessments, list):
            errors.append("assessments_not_array")
            assessments = []
        cleaned: list[dict[str, Any]] = []
        assessed_keys: set[str] = set()
        for assessment in assessments:
            if not isinstance(assessment, Mapping):
                errors.append("assessment_not_object")
                continue
            key = text(assessment.get("candidate_key"))
            verdict = text(assessment.get("verdict"))
            support = assessment.get("supporting_evidence_ids")
            contradict = assessment.get("contradicting_evidence_ids")
            if key not in keys or key in assessed_keys:
                errors.append("invalid_or_duplicate_candidate_key")
            if verdict not in ASSESSMENT_VERDICTS:
                errors.append("invalid_assessment_verdict")
            if not isinstance(support, list) or not all(text(value) in evidence_ids for value in support):
                errors.append("invalid_supporting_evidence")
                support = []
            if not isinstance(contradict, list) or not all(text(value) in evidence_ids for value in contradict):
                errors.append("invalid_contradicting_evidence")
                contradict = []
            assessed_keys.add(key)
            cleaned.append({
                "candidate_key": key, "verdict": verdict,
                "supporting_evidence_ids": sorted(set(text(value) for value in support)),
                "contradicting_evidence_ids": sorted(set(text(value) for value in contradict)),
                "reason_types": sorted(set(text(value) for value in assessment.get("reason_types", []) or [] if text(value))),
            })
        preferred = raw.get("preferred_candidate_key")
        if preferred == "null":
            errors.append("literal_null_candidate_key")
        if preferred is not None and text(preferred) not in keys:
            errors.append("invalid_preferred_candidate_key")
        resolution = text(raw.get("resolution"))
        if resolution not in RESOLUTIONS:
            errors.append("invalid_resolution")
        if resolution == "candidate_supported" and (preferred is None or not any(row["candidate_key"] == preferred and row["verdict"] == "support" and row["supporting_evidence_ids"] for row in cleaned)):
            errors.append("supported_resolution_requires_grounded_support")
        if errors:
            rejected.append({"index": index, "mention_id": mention_id, "errors": sorted(set(errors))})
            continue
        seen.add(mention_id)
        accepted.append({
            "mention_id": mention_id,
            "candidate_assessments": cleaned,
            "preferred_candidate_key": preferred,
            "resolution": resolution,
            "alternative_search_surfaces": sorted(set(text(value) for value in raw.get("alternative_search_surfaces", []) or [] if text(value))),
            "explanation": text(raw.get("explanation")),
            "candidate_only": True,
            "canonical_write_back": False,
        })
    return {
        "story_id": packet.get("story_id"),
        "judgments": sorted(accepted, key=lambda row: row["mention_id"]),
        "rejected": rejected,
        "provider_failure": bool(payload.get("_provider_failure")) if isinstance(payload, Mapping) else False,
    }
