"""Deterministic application of reviewed historical-semantic authority.

This module does not infer semantics.  It only reads the manually reviewed
records in the SFH2R authority files and applies those explicit decisions to
downstream derived pipelines.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parents[1]
AUTHORITY_PATH = ROOT / "data/annotation/sfh2r-manual-semantic-authority.json"
AUTHORITY_V2_PATH = ROOT / "data/annotation/sfh2r1-manual-semantic-authority.json"
VARIANTS = str.maketrans({"爲": "為", "髙": "高", "鳯": "鳳", "臺": "台", "台": "台"})


def _text(value: Any) -> str:
    return str(value or "").strip()


def normalize_form(value: Any) -> str:
    return re.sub(r"\s+", "", _text(value)).translate(VARIANTS)


def load_authority() -> dict[str, Any]:
    if not AUTHORITY_PATH.is_file():
        return {}
    return json.loads(AUTHORITY_PATH.read_text(encoding="utf-8"))


def load_authority_v2() -> dict[str, Any]:
    if not AUTHORITY_V2_PATH.is_file():
        return {}
    return json.loads(AUTHORITY_V2_PATH.read_text(encoding="utf-8"))


def authority_reference(path: Path | None = None) -> str:
    """Return the stable repository reference for the reviewed authority."""
    return str((path or AUTHORITY_PATH).relative_to(ROOT))


def authority_documents() -> list[tuple[Path, dict[str, Any]]]:
    """Return reviewed authorities in application order.

    SFH2R.1 is a second, independent manual pass.  Keeping the path beside
    each document lets materializers preserve which human authority supplied
    each edit rather than collapsing both passes into one opaque label.
    """
    return [
        (path, document)
        for path in (AUTHORITY_PATH, AUTHORITY_V2_PATH)
        if (document := (json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}))
    ]


def alias_repairs() -> list[dict[str, Any]]:
    """Return reviewed alias repairs in file order.

    This accessor deliberately returns the authority records verbatim.  The
    records are reviewed semantic decisions; callers may apply them, but may
    not infer additional repairs from their surface strings.
    """
    return [
        dict(row)
        for row in load_authority().get("alias_repairs", []) or []
        if isinstance(row, Mapping)
    ]


def second_alias_repairs() -> list[dict[str, Any]]:
    """Return only the SFH2R.1 records for its isolated materializer."""
    return [
        dict(row)
        for row in load_authority_v2().get("alias_repairs", []) or []
        if isinstance(row, Mapping)
    ]


def all_alias_repairs() -> list[dict[str, Any]]:
    """Return both manual passes in deterministic application order."""
    return [*alias_repairs(), *second_alias_repairs()]


def blocked_global_forms() -> set[tuple[str, str]]:
    """Forms that must not be used as global exact identity keys.

    A downgraded/shared form is returned here for legacy exact-key callers,
    but it remains a valid contextual retrieval hint.  Callers that build a
    broad suppression overlay must use :func:`fully_blocked_forms` instead.
    """
    blocked: set[tuple[str, str]] = set()
    for row in all_alias_repairs():
        if not isinstance(row, Mapping):
            continue
        action = _text(row.get("action"))
        if action.startswith("downgrade_") or action == "replace_corrupt_alias_surface":
            surface = normalize_form(row.get("surface"))
            person_id = _text(row.get("current_person_id"))
            if surface and person_id:
                blocked.add((surface, person_id))
    return blocked


def fully_blocked_forms() -> set[tuple[str, str]]:
    """Return only reviewed wrong-bearer/corrupt pairs barred at all scopes."""
    blocked: set[tuple[str, str]] = set()
    for row in all_alias_repairs():
        if _text(row.get("action")) not in {
            "suppress_wrong_bearer_alias",
            "suppress_person_alias_and_reclassify_collective",
            "replace_corrupt_alias_surface",
        }:
            continue
        surface = normalize_form(row.get("surface"))
        person_id = _text(row.get("current_person_id"))
        if surface and person_id:
            blocked.add((surface, person_id))
    return blocked


def replacement_exact_forms() -> list[dict[str, str]]:
    """Explicit reviewed replacement forms; currently used for 子玄→郭象."""
    rows: list[dict[str, str]] = []
    for row in all_alias_repairs():
        if not isinstance(row, Mapping) or _text(row.get("action")) != "replace_corrupt_alias_surface":
            continue
        surface = _text(row.get("corrected_surface"))
        person_id = _text(row.get("current_person_id"))
        if surface and person_id and _text(row.get("corrected_resolution_mode")) == "exact":
            rows.append({
                "surface": surface,
                "person_id": person_id,
                "basis": "manual_semantic_authority",
                "evidence_ref": authority_reference(
                    AUTHORITY_V2_PATH if row in second_alias_repairs() else AUTHORITY_PATH
                ),
            })
    return rows


def occurrence_repairs() -> dict[str, dict[str, Any]]:
    return {
        _text(row.get("observation_id")): dict(row)
        for row in load_authority().get("occurrence_repairs", []) or []
        if isinstance(row, Mapping) and _text(row.get("observation_id"))
    }


def all_occurrence_repairs() -> dict[str, dict[str, Any]]:
    """Return occurrence repairs from both passes, with later authority last."""
    result: dict[str, dict[str, Any]] = {}
    for _, document in authority_documents():
        for row in document.get("occurrence_repairs", []) or []:
            if isinstance(row, Mapping) and _text(row.get("observation_id")):
                result[_text(row.get("observation_id"))] = dict(row)
    return result


def _source_id_for_evidence(evidence_id: str, aliases: Mapping[str, Any]) -> str:
    """Resolve an authority evidence id to its registered source id.

    Alias evidence is the only source of this mapping here.  No semantic
    interpretation is performed: this is an exact provenance lookup used to
    apply a reviewed rejection to the same source witness.
    """
    for alias in aliases.get("aliases", []) or []:
        if not isinstance(alias, Mapping):
            continue
        for evidence in alias.get("source_evidence", []) or []:
            if isinstance(evidence, Mapping) and _text(evidence.get("evidence_id")) == evidence_id:
                return _text(evidence.get("source_id"))
        for trace_key in ("sfh2r_manual_repair", "sfh2r1_manual_repair"):
            repair_trace = alias.get(trace_key)
            if isinstance(repair_trace, Mapping):
                for evidence in repair_trace.get("removed_evidence_provenance", []) or []:
                    if isinstance(evidence, Mapping) and _text(evidence.get("evidence_id")) == evidence_id:
                        return _text(evidence.get("source_id"))
    return ""


def _claim_source_ids(source_row: Mapping[str, Any] | None, decision: Mapping[str, Any]) -> set[str]:
    values: set[str] = set()
    for item in (source_row or {}, decision):
        for key in ("story_id", "source_id", "source_ref", "evidence_ref"):
            value = _text(item.get(key))
            if value:
                values.add(value)
    return values


def _claim_surfaces(decision: Mapping[str, Any], source_row: Mapping[str, Any] | None) -> set[str]:
    values = {_text(decision.get("surface")), _text(decision.get("exact_span"))}
    if source_row:
        values.update({_text(source_row.get("surface")), _text(source_row.get("exact_span"))})
    return {normalize_form(value) for value in values if value}


def manual_profile_claim_rejection(
    decision: Mapping[str, Any],
    source_row: Mapping[str, Any] | None = None,
    *,
    aliases_document: Mapping[str, Any] | None = None,
) -> str | None:
    """Return a reviewed rejection reason for one profile identity claim.

    This is an authority application gate, not a semantic classifier.  It
    only matches the exact person/source/evidence coordinates named by the
    reviewed alias records.  In particular, a catalogue match cannot restore
    a form whose cited witness was explicitly assigned to another bearer.
    """
    target = _text(decision.get("resolved_person_id") or decision.get("candidate_person_id"))
    if not target:
        return None
    if aliases_document is None:
        aliases_path = ROOT / "data/aliases.json"
        aliases = json.loads(aliases_path.read_text(encoding="utf-8")) if aliases_path.is_file() else {}
    else:
        aliases = aliases_document
    claim_sources = _claim_source_ids(source_row, decision)
    claim_surfaces = _claim_surfaces(decision, source_row)
    claim_story = _text(decision.get("story_id") or (source_row or {}).get("story_id"))
    claim_surface = normalize_form(decision.get("surface"))
    for repair in all_alias_repairs():
        if _text(repair.get("current_person_id")) != target:
            continue
        action = _text(repair.get("action"))
        alias_surface = normalize_form(repair.get("surface"))
        if action == "replace_corrupt_alias_surface" and claim_surface == alias_surface:
            return f"manual_alias_surface_replaced:{repair.get('alias_id')}"
        removed_ids = {
            _text(value)
            for value in repair.get("remove_evidence_ids", []) or []
            if _text(value)
        }
        if repair.get("remove_all_current_surface_evidence") and claim_surface == alias_surface:
            return f"manual_alias_surface_removed:{repair.get('alias_id')}"
        if not removed_ids:
            continue
        removed_source_ids = {
            source_id
            for evidence_id in removed_ids
            if (source_id := _source_id_for_evidence(evidence_id, aliases))
        }
        if not (removed_source_ids & claim_sources or any(source_id and source_id in claim_story for source_id in removed_source_ids)):
            continue
        # Keep both fields from every reviewed other-referent record.  The
        # authority deliberately uses ``surface`` for the shared form and
        # ``display_name`` for the bearer (for example 景真 / 桓亮).  Using
        # ``surface or display_name`` here loses the bearer and lets an
        # occurrence-level full-name claim bypass the reviewed rejection.
        other_surfaces = {normalize_form(repair.get("surface"))}
        for item in repair.get("other_referents", []) or []:
            if not isinstance(item, Mapping):
                continue
            for raw in (item.get("surface"), item.get("display_name")):
                normalized = normalize_form(raw)
                if normalized:
                    other_surfaces.add(normalized)
        other_surfaces.discard("")
        # The exact authority records identify both the rejected witness and,
        # where needed, its reviewed other bearer.  Matching the claim's
        # cited span against those reviewed forms prevents a longer direct
        # projection such as 桓亮/桓景真 from bypassing the 景真 repair.
        if claim_surface in other_surfaces or any(
            surface and surface in claim_surfaces
            for surface in other_surfaces
        ) or any(
            surface and any(surface in candidate for candidate in claim_surfaces)
            for surface in other_surfaces
        ):
            return f"manual_removed_evidence_bearer_conflict:{repair.get('alias_id')}"
        if claim_surface == alias_surface:
            return f"manual_removed_evidence:{repair.get('alias_id')}"
    return None


def _apply_alias_repairs(
    aliases_document: Mapping[str, Any],
    repairs: list[Mapping[str, Any]],
    authority_path: Path,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Mechanically materialize one explicitly reviewed authority set.

    The function validates the expected alias id/surface/person coordinates,
    filters only explicitly removed evidence, and preserves the alias id and
    all non-target fields.  It never decides whether an unlisted row should
    be changed.
    """
    document = json.loads(json.dumps(aliases_document, ensure_ascii=False))
    rows = document.get("aliases") if isinstance(document.get("aliases"), list) else []
    by_id = {
        _text(row.get("alias_id")): row
        for row in rows
        if isinstance(row, Mapping) and _text(row.get("alias_id"))
    }
    evidence_lookup: dict[str, dict[str, Any]] = {}
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        for evidence in row.get("source_evidence", []) or []:
            if isinstance(evidence, Mapping) and _text(evidence.get("evidence_id")):
                evidence_lookup[_text(evidence.get("evidence_id"))] = dict(evidence)
    audit: list[dict[str, Any]] = []
    for repair in repairs:
        alias_id = _text(repair.get("alias_id"))
        current = by_id.get(alias_id)
        if current is None:
            raise RuntimeError(f"manual_alias_missing:{alias_id}")
        expected_surface = _text(repair.get("surface"))
        expected_person = _text(repair.get("current_person_id"))
        if _text(current.get("surface")) != expected_surface:
            raise RuntimeError(f"manual_alias_surface_drift:{alias_id}")
        if expected_person not in [str(value) for value in current.get("person_ids", []) or []]:
            raise RuntimeError(f"manual_alias_person_drift:{alias_id}")
        before = json.loads(json.dumps(current, ensure_ascii=False))
        remove_ids = {
            _text(value)
            for value in repair.get("remove_evidence_ids", []) or []
            if _text(value)
        }
        keep_ids = {
            _text(value)
            for value in repair.get("keep_evidence_ids", []) or []
            if _text(value)
        }
        old_evidence = [dict(value) for value in current.get("source_evidence", []) or [] if isinstance(value, Mapping)]
        old_evidence_ids = {_text(value.get("evidence_id")) for value in old_evidence if _text(value.get("evidence_id"))}
        audit_removed_ids = set(remove_ids)
        if repair.get("remove_all_current_surface_evidence"):
            audit_removed_ids.update(old_evidence_ids)
        if keep_ids:
            new_evidence = [value for value in old_evidence if _text(value.get("evidence_id")) in keep_ids]
        elif repair.get("remove_all_current_surface_evidence"):
            new_evidence = []
        else:
            new_evidence = [value for value in old_evidence if _text(value.get("evidence_id")) not in remove_ids]
        replacement_ids = [
            _text(value)
            for value in repair.get("replacement_evidence_ids", []) or []
            if _text(value)
        ]
        if replacement_ids:
            replacements = []
            for evidence_id in replacement_ids:
                evidence = evidence_lookup.get(evidence_id)
                if evidence is None:
                    raise RuntimeError(f"manual_replacement_evidence_missing:{evidence_id}")
                replacement = dict(evidence)
                replacement["surface"] = repair.get("corrected_surface") or replacement.get("surface")
                replacements.append(replacement)
            new_evidence = replacements
        current["source_evidence"] = sorted(new_evidence, key=lambda row: _text(row.get("evidence_id")))
        if repair.get("corrected_surface"):
            current["surface"] = repair.get("corrected_surface")
        if repair.get("corrected_alias_type"):
            current["alias_type"] = repair.get("corrected_alias_type")
        for key in ("corrected_resolution_mode", "corrected_status"):
            if repair.get(key):
                current[key.removeprefix("corrected_")] = repair.get(key)
        current["observed_count"] = int(repair.get("corrected_observed_support_count") or len(current["source_evidence"]))
        if repair.get("remove_all_current_surface_evidence") or _text(repair.get("action")) in {
            "suppress_wrong_bearer_alias",
            "suppress_person_alias_and_reclassify_collective",
        }:
            # Preserve the alias row and its audit trace, but remove it from
            # all active person retrieval keys.  The authority explicitly
            # says this surface was assigned to another bearer/collective.
            current["person_ids"] = []
            current["resolved_person_ids"] = []
        else:
            current["resolved_person_ids"] = list(current.get("resolved_person_ids") or current.get("person_ids") or [])
        current["sfh2r_manual_repair"] = {
            "authority": authority_reference(authority_path),
            "alias_id": alias_id,
            "action": repair.get("action"),
            "manual_verdict": repair.get("manual_verdict"),
            "removed_evidence_ids": sorted(audit_removed_ids),
            "retained_evidence_ids": sorted(_text(row.get("evidence_id")) for row in current["source_evidence"]),
            "removed_evidence_provenance": [
                value
                for value in old_evidence
                if _text(value.get("evidence_id")) in audit_removed_ids
            ],
        }
        audit.append({
            "alias_id": alias_id,
            "surface_before": before.get("surface"),
            "surface_after": current.get("surface"),
            "person_ids": current.get("person_ids", []),
            "before": before,
            "after": json.loads(json.dumps(current, ensure_ascii=False)),
            "manual_authority": repair,
            "removed_evidence_ids": sorted(audit_removed_ids),
            "retained_evidence_ids": sorted(_text(row.get("evidence_id")) for row in current["source_evidence"]),
        })
    return document, audit


def apply_alias_repairs(
    aliases_document: Mapping[str, Any],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Apply the original SFH2R authority (kept for compatibility)."""
    return _apply_alias_repairs(aliases_document, alias_repairs(), AUTHORITY_PATH)


def apply_sfh2r1_alias_repairs(
    aliases_document: Mapping[str, Any],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Apply the second reviewed authority after the original SFH2R pass."""
    return _apply_alias_repairs(aliases_document, second_alias_repairs(), AUTHORITY_V2_PATH)


def _manual_candidate_id(display_name: str) -> str:
    digest = hashlib.sha256(display_name.encode("utf-8")).hexdigest()[:20]
    return f"sfh2r-manual-candidate-{digest}"


def apply_sfh2_observation(row: Mapping[str, Any]) -> dict[str, Any]:
    """Apply one explicit occurrence repair to an SFH2 observation, if any."""
    result = dict(row)
    repair = all_occurrence_repairs().get(_text(result.get("observation_id")))
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
