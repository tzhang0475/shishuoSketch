"""Deterministic identity-retrieval policy after the SFH2R manual audit.

This module does NOT interpret historical text.  It enforces a storage and
retrieval contract derived from manually reviewed failure modes:

* a valid courtesy name/title is not necessarily globally unique;
* occurrence resolution does not create a global alias;
* substring occurrence in nearby source text is not identity evidence;
* human/LLM semantics have precedence over lexical retrieval hints.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parents[1]
AUTHORITY_V1 = ROOT / "data/annotation/sfh2r-manual-semantic-authority.json"
AUTHORITY_V2 = ROOT / "data/annotation/sfh2r1-manual-semantic-authority.json"
VARIANTS = str.maketrans({"爲": "為", "髙": "高", "鳯": "鳳", "臺": "台", "台": "台"})

DIRECT_EXACT_TYPES = {"personal_name", "surname_plus_courtesy_name", "orthographic_variant"}
CONTEXTUAL_TYPES = {
    "courtesy_name", "style_name", "nickname", "office_title", "contextual_title",
    "honorific", "ruler_title", "surname_reference", "abbreviated_reference",
    "observed_surface", "alias", "title",
}
CONTEXTUAL_MODES = {"contextual", "shared_or_contextual", "context_dependent"}
SUPPRESS_ACTIONS = {
    "suppress_wrong_bearer_alias",
    "suppress_person_alias_and_reclassify_collective",
}


def _text(value: Any) -> str:
    return str(value or "").strip()


def normalize_form(value: Any) -> str:
    return re.sub(r"\s+", "", _text(value)).translate(VARIANTS)


def _read(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def authority_documents() -> list[dict[str, Any]]:
    return [_read(path) for path in (AUTHORITY_V1, AUTHORITY_V2) if path.is_file()]


def alias_repairs() -> list[dict[str, Any]]:
    return [
        dict(row)
        for document in authority_documents()
        for row in document.get("alias_repairs", []) or []
        if isinstance(row, Mapping)
    ]


def explicit_alias_action(alias_id: Any) -> str:
    target = _text(alias_id)
    for row in reversed(alias_repairs()):
        if _text(row.get("alias_id")) == target:
            return _text(row.get("action"))
    return ""


def explicitly_blocked_alias_ids() -> set[str]:
    return {
        _text(row.get("alias_id"))
        for row in alias_repairs()
        if _text(row.get("alias_id")) and _text(row.get("action")) in SUPPRESS_ACTIONS
    }


def explicitly_blocked_form_person_pairs() -> set[tuple[str, str]]:
    result: set[tuple[str, str]] = set()
    for row in alias_repairs():
        action = _text(row.get("action"))
        if action.startswith("downgrade_") or action in SUPPRESS_ACTIONS or action == "replace_corrupt_alias_surface":
            surface = normalize_form(row.get("surface"))
            person_id = _text(row.get("current_person_id"))
            if surface and person_id:
                result.add((surface, person_id))
    return result


def alias_retrieval_scope(alias: Mapping[str, Any]) -> str:
    """Return blocked, exact, or contextual for one stored alias.

    This is a data-contract decision, not a historical identity judgment.
    """
    alias_id = _text(alias.get("alias_id"))
    if alias_id in explicitly_blocked_alias_ids():
        return "blocked"
    surface = normalize_form(alias.get("surface"))
    if not surface:
        return "blocked"
    if len(surface) <= 1:
        return "contextual"
    mode = _text(alias.get("resolution_mode"))
    status = _text(alias.get("status"))
    form_type = _text(alias.get("alias_type"))
    if mode in CONTEXTUAL_MODES or status in {"context_dependent", "shared_or_contextual", "collective_reference", "suppressed_wrong_bearer"}:
        return "contextual"
    if form_type in CONTEXTUAL_TYPES:
        return "contextual"
    if form_type in DIRECT_EXACT_TYPES and mode == "exact" and status == "resolved":
        return "exact"
    return "contextual"


def profile_form_retrieval_scope(form: Mapping[str, Any]) -> str:
    """Profile forms are contextual unless they encode a full-name class.

    observed_surface/courtesy/title provenance remains valuable dossier
    evidence, but is never a direct global identity key.
    """
    surface = normalize_form(form.get("surface"))
    if not surface or len(surface) <= 1:
        return "contextual"
    form_type = _text(form.get("form_type"))
    if form_type in {"personal_name", "surname_plus_courtesy_name", "orthographic_variant"}:
        return "exact"
    return "contextual"


def split_aliases(document: Mapping[str, Any]) -> dict[str, list[dict[str, Any]]]:
    result = {"exact": [], "contextual": [], "blocked": []}
    for row in document.get("aliases", []) or []:
        if not isinstance(row, Mapping):
            continue
        result[alias_retrieval_scope(row)].append(dict(row))
    return result


def policy_summary() -> dict[str, Any]:
    return {
        "semantic_precedence": [
            "reviewed_human_decision",
            "validated_llm_semantic_judgment",
            "soft_collective_consistency",
            "deterministic_retrieval_hint",
        ],
        "direct_exact_form_types": sorted(DIRECT_EXACT_TYPES),
        "contextual_form_types": sorted(CONTEXTUAL_TYPES),
        "single_character_forms": "contextual_only",
        "substring_context_scan": "forbidden_for_identity_candidate_generation",
        "occurrence_resolution_implies_global_alias": False,
        "observed_count_is_identity_strength": False,
    }
