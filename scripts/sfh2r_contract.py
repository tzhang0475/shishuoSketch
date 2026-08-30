"""Shared, explicit compatibility checks for the SFH2R derived-input repair.

SFH2R intentionally changes the active alias/profile projections.  Earlier
SFH2/HDA2 experiments have frozen snapshots of those *derived* inputs.  This
module lets their validators recognize exactly one documented transition:
the pre-repair bytes recorded by the SFH2R manifest to the post-repair bytes
recorded by that same manifest.  It never accepts an arbitrary current file
or relaxes canonical protection.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parents[1]
TRANSITION_PATH = ROOT / "data/generated/sfh2r/repair-manifest.json"

ACTIVE_REPAIR_INPUTS = (
    "data/aliases.json",
    "data/derived/s1-jianshu-source-registration.json",
    "data/derived/hdb2-f-person-knowledge.json",
    "data/derived/hdb2-f-candidate-person-knowledge.json",
    "data/derived/hdb2-f-profile-integrity-audit.json",
    "data/derived/hdb2-f-identity-claim-integrity-audit.json",
)


def _read(path: Path, default: Any = None) -> Any:
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else default


def file_hash(path: Path) -> str | None:
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None


def path_hash_is_current_or_authorized(
    relative_path: str,
    frozen_hash: str | None,
    current_hash: str | None = None,
) -> bool:
    """Check one derived input against the explicit SFH2R transition.

    Older experiments keep their own frozen manifests.  A reviewed SFH2R
    repair may intentionally change a derived input, but only the exact
    before/after bytes recorded by the SFH2R manifest are accepted here.
    Canonical files are never routed through this helper.
    """
    if not relative_path or not frozen_hash:
        return False
    actual = current_hash if current_hash is not None else file_hash(ROOT / relative_path)
    if actual == frozen_hash:
        return True
    if not transition_is_valid():
        return False
    before, after = _transition_hashes()
    return (
        relative_path in before
        and relative_path in after
        and str(frozen_hash) == before[relative_path]
        and actual == after[relative_path]
    )


def transition_manifest() -> dict[str, Any]:
    value = _read(TRANSITION_PATH, {})
    return dict(value) if isinstance(value, Mapping) else {}


def pre_repair_alias_document() -> dict[str, Any] | None:
    """Return the preserved pre-SFH2R alias witness for frozen projections.

    SFH2R deliberately changes the active alias registry.  Older publication
    and experiment projections remain byte-frozen to their pre-repair input;
    they may use this preserved witness for deterministic rebuilding.  This
    is not an active identity index and is never used by SFH2R retrieval.
    """
    audit = _read(ROOT / "data/generated/sfh2r/alias-before-after.json", {})
    document = audit.get("before_document") if isinstance(audit, Mapping) else None
    return dict(document) if isinstance(document, Mapping) else None


def pre_repair_alias_file_hash() -> str | None:
    audit = _read(ROOT / "data/generated/sfh2r/alias-before-after.json", {})
    value = audit.get("before_file_sha256") if isinstance(audit, Mapping) else None
    return str(value) if isinstance(value, str) and value else None


def pre_repair_registration_file_hash() -> str | None:
    """Return the pre-repair S1 registration witness when it is recorded.

    X1.2R and X1.2R-F contain frozen source-registration metadata.  The
    active registration is intentionally updated by SFH2R because it carries
    the repaired alias-input hash, so those older projections use this
    explicit transition witness for their historical input field only.
    """
    before, _ = _transition_hashes()
    value = before.get("data/derived/s1-jianshu-source-registration.json")
    return str(value) if isinstance(value, str) and value else None


def current_repair_input_hashes() -> dict[str, str]:
    return {
        path: digest
        for path in ACTIVE_REPAIR_INPUTS
        if (digest := file_hash(ROOT / path)) is not None
    }


def _transition_hashes() -> tuple[dict[str, str], dict[str, str]]:
    manifest = transition_manifest()
    transition = manifest.get("active_input_transition")
    if not isinstance(transition, Mapping):
        return {}, {}
    before = transition.get("before_hashes")
    after = transition.get("after_hashes")
    if not isinstance(before, Mapping) or not isinstance(after, Mapping):
        return {}, {}
    return (
        {str(key): str(value) for key, value in before.items() if str(key) and str(value)},
        {str(key): str(value) for key, value in after.items() if str(key) and str(value)},
    )


def transition_is_valid() -> bool:
    manifest = transition_manifest()
    if not manifest or manifest.get("authority_sha256") != _authority_hash():
        return False
    if manifest.get("candidate_only") is not True or manifest.get("canonical_write_back") is not False:
        return False
    before, after = _transition_hashes()
    current = current_repair_input_hashes()
    return bool(before and after and current == after)


def _authority_hash() -> str | None:
    return file_hash(ROOT / "data/annotation/sfh2r-manual-semantic-authority.json")


def frozen_hashes_are_current_or_authorized(
    frozen: Mapping[str, Any] | None,
    current: Mapping[str, Any] | None = None,
) -> bool:
    """Return whether a prior snapshot is unchanged or exactly SFH2R-pre.

    Keys outside the SFH2R active-input transition must match current bytes.
    Changed active keys must match the recorded pre-repair bytes, and the
    transition manifest must prove that the active files are its recorded
    post-repair bytes.  This is deliberately fail-closed.
    """
    if not isinstance(frozen, Mapping):
        return False
    current_map = {str(key): str(value) for key, value in (current or current_repair_input_hashes()).items()}
    frozen_map = {str(key): str(value) for key, value in frozen.items()}
    if frozen_map == current_map:
        return True
    if not transition_is_valid():
        return False
    before, after = _transition_hashes()
    # Callers such as HDA2 carry a narrower snapshot than the full SFH2R
    # active-input set.  Validate every key they do provide, while the
    # transition manifest itself validates the complete current set above.
    if any(key in current_map and current_map[key] != value for key, value in after.items()):
        return False
    for key, value in frozen_map.items():
        if key in before:
            if value != before[key]:
                return False
        elif current_map.get(key) != value:
            return False
    # A snapshot cannot omit an active transition key that was present in the
    # historical input; omission would turn this into a partial hash check.
    return all(key not in frozen_map or frozen_map[key] == before.get(key) for key in before)


def frozen_snapshot_matches_current_or_authorized(
    frozen: Mapping[str, Any] | None,
    current: Mapping[str, Any] | None = None,
) -> bool:
    """Alias with a name suitable for snapshot validators."""
    return frozen_hashes_are_current_or_authorized(frozen, current)
