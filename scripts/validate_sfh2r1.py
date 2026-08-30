#!/usr/bin/env python3
"""Validate the SFH2R.1 semantic-precedence closeout.

This validator is intentionally mechanical.  The two authority documents
contain the historical judgments; this file checks that the second authority
was materialized, that active retrieval respects its scopes, and that the
derived-input transition is explicit.  It never infers or repairs semantics.
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import manual_semantic_authority as authority  # noqa: E402
import sfh2r_contract  # noqa: E402


OUT = ROOT / "data/generated/sfh2r1"
ALIASES = ROOT / "data/aliases.json"
PROFILE = ROOT / "data/derived/hdb2-f-person-knowledge.json"
CANDIDATE_PROFILE = ROOT / "data/derived/hdb2-f-candidate-person-knowledge.json"
PROFILE_AUDIT = ROOT / "data/derived/hdb2-f-profile-integrity-audit.json"
REQUIRED = (
    "alias-before-after.json",
    "profile-before-after.json",
    "active-identity-index-audit.json",
    "repair-manifest.json",
    "closeout-summary.json",
    "offline-replay-effects.json",
)


def _read(path: Path, default: Any = None) -> Any:
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else default


def _hash(path: Path) -> str | None:
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None


def _text(value: Any) -> str:
    return str(value or "").strip()


def _forms(profile: Mapping[str, Any]) -> set[str]:
    identity = profile.get("identity") if isinstance(profile.get("identity"), Mapping) else {}
    return {
        _text(value)
        for key in ("aliases", "courtesy_names", "titles", "observed_surfaces")
        for value in identity.get(key, []) or []
        if _text(value)
    }


def _add(errors: list[str], condition: bool, message: str) -> None:
    if not condition:
        errors.append(message)


def _synthetic_hint_bridge_check() -> dict[str, Any]:
    """Exercise the installed SFH1→SFH2 hint bridge without an API call."""
    from sfh2 import inputs

    documents = {
        "packets": {"packets": [{"story_id": "synthetic", "evidence": [{"evidence_id": "e0", "text": "勒"}]}]},
        "mentions": {"records": [{
            "mention_id": "mention-synthetic",
            "story_id": "synthetic",
            "surface": "勒",
            "entity_kind": "person",
            "reference_form": "abbreviated_reference",
            "source_evidence_id": "e0",
            "source_start": 0,
            "source_end": 1,
        }]},
        "semantics": {"records": [{
            "mention_id": "mention-synthetic",
            "semantic_type": "abbreviated_person_reference",
            "referent_hint": "石勒",
            "network_role": "narrative_reference",
        }]},
        "candidate_sets": {"records": []},
        "final": {"records": []},
        "relations": {"records": []},
        "temporal": {"records": []},
    }
    result = inputs.build_candidate_observations(documents)
    row = next((item for item in result.get("records", []) if isinstance(item, Mapping)), {})
    return {
        "preserved": row.get("semantic_referent_hint") == "石勒" and row.get("reference_semantics", {}).get("referent_hint") == "石勒",
        "observation_hint": row.get("semantic_referent_hint"),
        "observation_role": row.get("network_role"),
    }


def validate() -> dict[str, Any]:
    errors: list[str] = []
    missing = [name for name in REQUIRED if not (OUT / name).is_file()]
    errors.extend(f"missing_output:{name}" for name in missing)
    if missing:
        return {"schema": "sfh2r1-validation-v1", "valid": False, "errors": sorted(errors), "candidate_only": True, "canonical_write_back": False}

    document = _read(OUT / "alias-before-after.json", {}) or {}
    audit_rows = {
        _text(row.get("alias_id")): row
        for row in document.get("records", []) or []
        if isinstance(row, Mapping) and _text(row.get("alias_id"))
    }
    active = _read(ALIASES, {}) or {}
    active_rows = {
        _text(row.get("alias_id")): row
        for row in active.get("aliases", []) or []
        if isinstance(row, Mapping) and _text(row.get("alias_id"))
    }
    repairs = authority.second_alias_repairs()
    _add(errors, len(repairs) == 4, "second_authority_repair_count")
    for repair in repairs:
        alias_id = _text(repair.get("alias_id"))
        row = active_rows.get(alias_id)
        audited = audit_rows.get(alias_id, {})
        _add(errors, row is not None, f"alias_missing:{alias_id}")
        _add(errors, audited.get("after") == row, f"alias_audit_after_mismatch:{alias_id}")
        if not row:
            continue
        _add(errors, _text(row.get("surface")) == _text(repair.get("surface")), f"surface_drift:{alias_id}")
        _add(errors, row.get("sfh2r1_manual_repair", {}).get("alias_id") == alias_id, f"authority_trace_missing:{alias_id}")
        current_evidence = {_text(item.get("evidence_id")) for item in row.get("source_evidence", []) or [] if isinstance(item, Mapping)}
        removed = {_text(value) for value in repair.get("remove_evidence_ids", []) or [] if _text(value)}
        keep = {_text(value) for value in repair.get("keep_evidence_ids", []) or [] if _text(value)}
        _add(errors, removed.isdisjoint(current_evidence), f"rejected_evidence_active:{alias_id}")
        _add(errors, keep.issubset(current_evidence), f"retained_evidence_missing:{alias_id}")
        if repair.get("remove_all_current_surface_evidence"):
            _add(errors, not row.get("person_ids") and not row.get("resolved_person_ids"), f"suppressed_person_ids_active:{alias_id}")
            _add(errors, not current_evidence, f"suppressed_evidence_active:{alias_id}")

    bolun = active_rows.get("alias-w3-9f1bc708fc909ce405824de4", {})
    _add(errors, bolun.get("resolution_mode") == "contextual", "bolun_not_contextual")
    _add(errors, bolun.get("status") == "shared_or_contextual", "bolun_status")
    bolun_ids = {_text(item.get("evidence_id")) for item in bolun.get("source_evidence", []) or [] if isinstance(item, Mapping)}
    _add(errors, "evidence-w3-person-ba50566714ba7c916e6e18b6" not in bolun_ids, "shan_gai_evidence_reentered")

    for alias_id in (
        "alias-w4-a0ab8bf1bf64e009032c292a",
        "alias-w4-c1809e42cafae4ba815946be",
        "alias-w4-ef14e8dd614bfb5c6425ce7d",
    ):
        row = active_rows.get(alias_id, {})
        _add(errors, not row.get("person_ids") and not row.get("resolved_person_ids"), f"wang_yin_reentry:{alias_id}")
        _add(errors, not row.get("source_evidence"), f"wang_yin_evidence_reentry:{alias_id}")

    # Active SFH2 retrieval must contain the shared courtesy form only in its
    # contextual bucket, and must not return person-054 for the suppressed
    # title/collective forms.
    try:
        from sfh2.consolidation import build_existing_form_index
        from sfh2.inputs import load_documents
        index = build_existing_form_index(load_documents())
        _add(errors, not any(row.get("person_id") == "person-047" for row in index.get("exact_forms", {}).get("伯倫", [])), "bolun_exact_retrieval")
        _add(errors, any(row.get("person_id") == "person-047" for row in index.get("contextual_forms", {}).get("伯倫", [])), "bolun_contextual_retrieval")
        for surface in ("王丞相", "王大將軍", "王庾諸公"):
            rows = [*index.get("exact_forms", {}).get(surface, []), *index.get("contextual_forms", {}).get(surface, [])]
            _add(errors, all(row.get("person_id") != "person-054" for row in rows), f"wang_yin_retrieval:{surface}")
        people = load_documents().get("people", {}).get("people", []) if isinstance(load_documents().get("people"), Mapping) else []
        direct_names = {_text(row.get("canonical_name")) for row in people if isinstance(row, Mapping)}
        for name in ("趙至", "束晳", "王隱", "劉伶"):
            if name in direct_names:
                _add(errors, bool(index.get("exact_forms", {}).get(name)), f"direct_name_unusable:{name}")
    except Exception as exc:  # pragma: no cover - surfaced as a validation failure
        errors.append(f"retrieval_check_error:{type(exc).__name__}:{exc}")

    profiles = [*_read(PROFILE, {}).get("records", []), *_read(CANDIDATE_PROFILE, {}).get("records", [])]
    for row in profiles:
        if not isinstance(row, Mapping):
            continue
        name = _text(row.get("canonical_name"))
        if name == "王隱":
            _add(errors, not ({"王丞相", "王大將軍", "王庾諸公"} & _forms(row)), "wang_yin_profile_contamination")
    integrity = _read(PROFILE_AUDIT, {}) or {}
    _add(errors, not integrity.get("known_contamination_remaining"), "known_profile_contamination_remaining")
    _add(errors, not integrity.get("known_regression_failures"), "profile_known_regression")

    manifest = _read(OUT / "repair-manifest.json", {}) or {}
    _add(errors, manifest.get("authority") == authority.authority_reference(authority.AUTHORITY_V2_PATH), "authority_reference")
    _add(errors, manifest.get("authority_sha256") == _hash(authority.AUTHORITY_V2_PATH), "authority_hash")
    _add(errors, manifest.get("candidate_only") is True, "manifest_candidate_only")
    _add(errors, manifest.get("canonical_write_back") is False, "manifest_canonical_write_back")
    transition = manifest.get("active_input_transition") or {}
    _add(errors, sfh2r_contract.transition_is_valid(), "derived_transition_invalid")
    _add(errors, transition.get("after_hashes") == sfh2r_contract.current_repair_input_hashes(), "derived_after_hashes")
    before_protected = manifest.get("protected_canonical_hashes_before") or {}
    after_protected = manifest.get("protected_canonical_hashes_after") or {}
    _add(errors, before_protected == after_protected, "protected_canonical_hash_changed")
    for path, expected in after_protected.items():
        _add(errors, _hash(ROOT / path) == expected, f"protected_hash:{path}")

    hint_bridge = _synthetic_hint_bridge_check()
    _add(errors, hint_bridge.get("preserved") is True, "referent_hint_not_preserved")

    replay = _read(OUT / "offline-replay-effects.json", {}) or {}
    _add(errors, replay.get("candidate_only") is True, "offline_replay_candidate_only")
    _add(errors, replay.get("canonical_write_back") is False, "offline_replay_canonical_write_back")
    _add(errors, replay.get("stories_retained") == 188, "offline_replay_story_universe")
    _add(errors, replay.get("new_live_llm_calls") == 0, "offline_replay_live_calls")
    _add(errors, replay.get("forbidden_identity_merge_count") == 0, "offline_replay_forbidden_merges")
    _add(errors, replay.get("explicit_distinct_cluster_violations") == 0, "offline_replay_distinct_violations")
    _add(errors, replay.get("suppressed_hda2_claim_reentry_count") == 0, "offline_replay_hda2_reentry")

    return {
        "schema": "sfh2r1-validation-v1",
        "valid": not errors,
        "errors": sorted(set(errors)),
        "second_pass_alias_repairs": len(repairs),
        "profile_form_count": sum(len(_forms(row)) for row in profiles if isinstance(row, Mapping)),
        "semantic_hint_bridge": hint_bridge,
        "offline_replay_effects": replay,
        "canonical_hashes_checked": len(after_protected),
        "candidate_only": True,
        "canonical_write_back": False,
    }


def main() -> int:
    result = validate()
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if result["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
