"""P2 proposal realization with a separate candidate-only namespace."""

from __future__ import annotations

from typing import Any, Mapping

from sfh2_2p1.retrieval import build_proposal_candidate_set as _p1_build_candidate_set

from .common import normalize, stable_hash, text


def _candidate_id(display_name: str) -> str:
    return "sfh2-2p2-candidate-person-" + stable_hash({
        "display_name": normalize(display_name),
        "namespace": "blind-entity-proposal",
    })[:20]


def build_candidate_set(case: Mapping[str, Any], proposal: Mapping[str, Any] | None, inputs: Mapping[str, Any], packet: Mapping[str, Any]) -> dict[str, Any]:
    """Reuse P1's safe realization and isolate P2 candidate IDs.

    P1's function is retrieval/realization code, not semantic judgment.  The
    wrapper only changes the experimental candidate namespace for provenance;
    it never changes candidate ordering or overrides the proposal.
    """
    result = _p1_build_candidate_set(case, proposal, inputs, packet)
    candidates = result.get("candidates", []) or []
    for candidate in candidates:
        if not isinstance(candidate, dict):
            continue
        if text(candidate.get("candidate_key")) == "c0" and text(candidate.get("entity_type")) == "candidate_historical_person":
            candidate["candidate_person_id"] = _candidate_id(text(candidate.get("display_name")))
            candidate["retrieval_basis"] = sorted(set((candidate.get("retrieval_basis") or []) + ["p2_candidate_namespace"]))
    result["candidate_namespace"] = "sfh2-2p2-candidate-person"
    result["candidate_only"] = True
    result["canonical_write_back"] = False
    return result
