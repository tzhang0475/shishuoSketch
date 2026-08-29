"""L8 adversarial LLM review with fail-closed validation."""

from __future__ import annotations

from typing import Any, Mapping

from .candidate_retrieval import candidate_evidence
from .common import StrictStageClient, text
from .schemas import REVIEW_VERDICTS, review_tool
from .source_packets import evidence_index

SYSTEM = """Act as an adversarial historical identity reviewer. For each risky proposed existing-Person resolution, ask how it could be wrong. Check the original source, mention boundary, reference semantics, explicit distinctness, and candidate evidence. Accept only when supplied evidence specifically supports identity; compatibility and model confidence are insufficient. Cite only supplied evidence IDs, never invent candidates or Person IDs, and return only the forced structured function."""


def proposed_reviews(constrained: Mapping[str, Any]) -> list[dict[str, Any]]:
    proposals: list[dict[str, Any]] = []
    for row in constrained.get("records", []) or []:
        judgment = row.get("judgment") if isinstance(row.get("judgment"), Mapping) else {}
        preferred = judgment.get("preferred_candidate_key")
        if judgment.get("resolution") != "candidate_supported" or preferred is None:
            continue
        candidate = next((item for item in row.get("candidates", []) or [] if item.get("candidate_key") == preferred), None)
        assessment = next((item for item in judgment.get("candidate_assessments", []) or [] if item.get("candidate_key") == preferred), None)
        if not candidate or candidate.get("entity_type") != "existing_person" or not assessment or assessment.get("verdict") != "support" or not assessment.get("supporting_evidence_ids"):
            continue
        if preferred in (row.get("hard_vetoes") or {}):
            continue
        proposals.append({"record": row, "candidate": candidate, "assessment": assessment})
    return proposals


def review(client: StrictStageClient, packet: Mapping[str, Any], semantics: Mapping[str, Any], constrained: Mapping[str, Any]) -> Mapping[str, Any] | None:
    proposals = proposed_reviews(constrained)
    if not proposals:
        return {"reviews": []}
    semantic_index = {text(row.get("mention_id")): row for row in semantics.get("records", []) or []}
    tool = review_tool()
    proposal_payloads = [
            {
                "mention_id": item["record"].get("mention_id"),
                "surface": item["record"].get("surface"),
                "reference_semantics": semantic_index.get(text(item["record"].get("mention_id"))),
                "candidate": {
                    "candidate_key": item["candidate"].get("candidate_key"),
                    "name": item["candidate"].get("display_name"),
                    "matched_surface": item["candidate"].get("matched_surface"),
                    "retrieval_basis": item["candidate"].get("retrieval_basis"),
                    "evidence": item["candidate"].get("evidence", []),
                },
                "identity_assessment": item["assessment"],
                "hard_vetoes": item["record"].get("hard_vetoes", {}),
            }
            for item in proposals
        ]
    reviews: list[Any] = []
    provider_failure = False
    for index in range(0, len(proposal_payloads), 4):
        payload = {
            "task": "adversarial review of risky existing-Person resolutions",
            "story_id": packet.get("story_id"),
            "source_evidence": [
                {"evidence_id": row.get("evidence_id"), "source_layer": row.get("source_layer"), "text": row.get("text")}
                for row in packet.get("evidence", []) or []
            ],
            "proposals": proposal_payloads[index:index + 4],
        }
        response = client.call(
            stage="adversarial_review",
            unit_id=f"{packet.get('story_id')}-part{index // 4 + 1}",
            system=SYSTEM,
            payload=payload,
            function=tool,
            function_name=tool["function"]["name"],
            max_tokens=1800,
        )
        if not isinstance(response, Mapping) or not isinstance(response.get("reviews"), list):
            provider_failure = True
            continue
        reviews.extend(response.get("reviews", []) or [])
    return {"reviews": reviews, "_provider_failure": provider_failure}


def validate_reviews(packet: Mapping[str, Any], constrained: Mapping[str, Any], payload: Mapping[str, Any] | None) -> dict[str, Any]:
    proposals = {text(item["record"].get("mention_id")): item for item in proposed_reviews(constrained)}
    source_ids = set(evidence_index(packet))
    rows = payload.get("reviews") if isinstance(payload, Mapping) else None
    if not isinstance(rows, list):
        return {"story_id": packet.get("story_id"), "reviews": [], "rejected": [{"reason": "provider_or_schema_failure"}], "provider_failure": True, "required_mentions": sorted(proposals)}
    accepted: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    seen: set[str] = set()
    for index, raw in enumerate(rows):
        if not isinstance(raw, Mapping):
            rejected.append({"index": index, "reason": "review_not_object"})
            continue
        mention_id = text(raw.get("mention_id"))
        proposal = proposals.get(mention_id)
        errors: list[str] = []
        if not proposal or mention_id in seen:
            errors.append("unknown_or_duplicate_mention")
            proposal = {"candidate": {"candidate_key": "", "evidence": []}}
        candidate_key = raw.get("candidate_key")
        if candidate_key == "null" or text(candidate_key) != text(proposal["candidate"].get("candidate_key")):
            errors.append("invalid_candidate_key")
        verdict = text(raw.get("verdict"))
        if verdict not in REVIEW_VERDICTS:
            errors.append("invalid_verdict")
        allowed_evidence = source_ids | {text(item.get("evidence_id")) for item in candidate_evidence({"candidates": [proposal["candidate"]]})}
        support = raw.get("supporting_evidence_ids")
        contradict = raw.get("contradicting_evidence_ids")
        if not isinstance(support, list) or not all(text(value) in allowed_evidence for value in support):
            errors.append("invalid_support_evidence")
            support = []
        if not isinstance(contradict, list) or not all(text(value) in allowed_evidence for value in contradict):
            errors.append("invalid_contradiction_evidence")
            contradict = []
        if verdict == "accept" and not support:
            errors.append("accept_requires_grounded_support")
        if errors:
            rejected.append({"index": index, "mention_id": mention_id, "errors": sorted(set(errors))})
            continue
        seen.add(mention_id)
        accepted.append({
            "mention_id": mention_id, "candidate_key": candidate_key,
            "verdict": verdict,
            "supporting_evidence_ids": sorted(set(text(value) for value in support)),
            "contradicting_evidence_ids": sorted(set(text(value) for value in contradict)),
            "reason_types": sorted(set(text(value) for value in raw.get("reason_types", []) or [] if text(value))),
            "explanation": text(raw.get("explanation")),
        })
    missing = sorted(set(proposals) - seen)
    return {"story_id": packet.get("story_id"), "reviews": accepted, "rejected": rejected, "provider_failure": bool(payload.get("_provider_failure")) if isinstance(payload, Mapping) else False, "required_mentions": sorted(proposals), "missing_required_reviews": missing}
