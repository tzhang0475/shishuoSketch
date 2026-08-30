"""Deterministic application of reviewed historical-semantic authority.

This module does not infer semantics.  It only reads the manually reviewed
records in data/annotation/sfh2r-manual-semantic-authority.json and applies
those explicit decisions to downstream derived pipelines.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parents[1]
AUTHORITY_PATH = ROOT / "data/annotation/sfh2r-manual-semantic-authority.json"
VARIANTS = str.maketrans({"爲": "為", "髙": "高", "鳯": "鳳", "臺": "台", "台": "台"})


def _text(value: Any) -> str:
    return str(value or "").strip()


def normalize_form(value: Any) -> str:
    return re.sub(r"\s+", "", _text(value)).translate(VARIANTS)


def load_authority() -> dict[str, Any]:
    if not AUTHORITY_PATH.is_file():
        return {}
    return json.loads(AUTHORITY_PATH.read_text(encoding="utf-8"))


def blocked_global_forms() -> set[tuple[str, str]]:
    """Forms explicitly barred from global exact identity retrieval."""
    blocked: set[tuple[str, str]] = set()
    for row in load_authority().get("alias_repairs", []) or []:
        if not isinstance(row, Mapping):
            continue
        action = _text(row.get("action"))
        if action.startswith("downgrade_") or action == "replace_corrupt_alias_surface":
            surface = normalize_form(row.get("surface"))
            person_id = _text(row.get("current_person_id"))
            if surface and person_id:
                blocked.add((surface, person_id))
    return blocked


def replacement_exact_forms() -> list[dict[str, str]]:
    """Explicit reviewed replacement forms; currently used for 子玄→郭象."""
    rows: list[dict[str, str]] = []
    for row in load_authority().get("alias_repairs", []) or []:
        if not isinstance(row, Mapping) or _text(row.get("action")) != "replace_corrupt_alias_surface":
            continue
        surface = _text(row.get("corrected_surface"))
        person_id = _text(row.get("current_person_id"))
        if surface and person_id and _text(row.get("corrected_resolution_mode")) == "exact":
            rows.append({
                "surface": surface,
                "person_id": person_id,
                "basis": "manual_semantic_authority",
                "evidence_ref": str(AUTHORITY_PATH.relative_to(ROOT)),
            })
    return rows


def occurrence_repairs() -> dict[str, dict[str, Any]]:
    return {
        _text(row.get("observation_id")): dict(row)
        for row in load_authority().get("occurrence_repairs", []) or []
        if isinstance(row, Mapping) and _text(row.get("observation_id"))
    }


def _manual_candidate_id(display_name: str) -> str:
    digest = hashlib.sha256(display_name.encode("utf-8")).hexdigest()[:20]
    return f"sfh2r-manual-candidate-{digest}"


def apply_sfh2_observation(row: Mapping[str, Any]) -> dict[str, Any]:
    """Apply one explicit occurrence repair to an SFH2 observation, if any."""
    result = dict(row)
    repair = occurrence_repairs().get(_text(result.get("observation_id")))
    if not repair:
        return result

    action = _text(repair.get("action"))
    result["manual_semantic_repair"] = {
        "authority": str(AUTHORITY_PATH.relative_to(ROOT)),
        "action": action,
        "manual_verdict": repair.get("manual_verdict"),
    }

    if action in {
        "suppress_existing_person_link_and_replace_with_candidate_historical_entity",
        "replace_candidate_retrieval_failure_with_grounded_candidate_historical_entity",
        "replace_wrong_or_incomplete_existing_candidate_with_grounded_candidate_historical_entity",
    }:
        name = _text(repair.get("replacement_display_name"))
        candidate_id = _manual_candidate_id(name)
        result["classification"] = "candidate_observation"
        result["previous_candidate_person_id"] = candidate_id
        result["previous_identity_decision"] = {
            "final_state": "manual_reviewed_candidate",
            "person_id": None,
            "candidate_person_id": candidate_id,
            "candidate_display_name": name,
            "failure_stage": None,
            "evidence_ids": repair.get("supporting_evidence_ids", []),
        }
        result["previous_candidate_rows"] = [{
            "candidate_person_id": candidate_id,
            "display_name": name,
            "retrieval_basis": "manual_semantic_authority",
            "evidence_ids": repair.get("supporting_evidence_ids", []),
        }]
        return result

    if action in {
        "suppress_person_mention_and_reclassify_as_attribute_fragment",
        "suppress_person_entity_and_reclassify_as_person_attribute",
        "suppress_person_mention_and_reclassify_as_attribute_phrase",
    }:
        result["classification"] = "non_person"
        result["entity_kind"] = "non_person"
        result["semantic_reference_type"] = "person_attribute"
        result["previous_candidate_person_id"] = None
        result["previous_identity_decision"] = {
            "final_state": "non_person",
            "person_id": None,
            "candidate_person_id": None,
            "candidate_display_name": None,
            "failure_stage": None,
            "evidence_ids": repair.get("supporting_evidence_ids", []),
        }
        result["person_attribute"] = repair.get("replacement")
        return result

    if action == "retain_personhood_but_reclassify_network_role":
        replacement = repair.get("replacement") if isinstance(repair.get("replacement"), Mapping) else {}
        result["network_role"] = replacement.get("network_role", "historical_context")
        result["core_story_graph_eligible"] = bool(replacement.get("core_story_graph_eligible", False))
        # Keep the historical-person reading, but stop treating the occurrence
        # as a candidate/existing story participant in SFH2 entity projection.
        result["classification"] = "historical_context_reference"
        return result

    return result
