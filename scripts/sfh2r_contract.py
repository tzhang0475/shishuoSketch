"""Shared, explicit compatibility checks for the SFH2R derived-input repair.

SFH2R intentionally changes the active alias/profile projections.  Earlier
SFH2/HDA2 experiments have frozen snapshots of those *derived* inputs.  This
module lets their validators recognize the documented, chained derived input
transitions recorded by SFH2R and SFH2R.1.  It never accepts an arbitrary
current file or relaxes canonical protection.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parents[1]
TRANSITION_PATH = ROOT / "data/generated/sfh2r/repair-manifest.json"
TRANSITION_V2_PATH = ROOT / "data/generated/sfh2r1/repair-manifest.json"

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
    # A later repair may be chained on top of an earlier one.  Accept only a
    # hash that is an exact recorded snapshot on that chain and an actual hash
    # from a later exact snapshot.  This is deliberately narrower than
    # accepting the current file: every intermediate byte state still has to
    # be present in the signed-by-content transition records.
    transitions = _transition_chain_hashes()
    snapshots: list[dict[str, str]] = []
    if transitions:
        snapshots.append(transitions[0][0])
        snapshots.extend(after for _, after in transitions)
    for earlier_index, snapshot in enumerate(snapshots):
        if snapshot.get(relative_path) != str(frozen_hash):
            continue
        for later_snapshot in snapshots[earlier_index + 1 :]:
            if later_snapshot.get(relative_path) == actual:
                return True
    return False


def transition_manifest() -> dict[str, Any]:
    value = _read(TRANSITION_PATH, {})
    return dict(value) if isinstance(value, Mapping) else {}


def transition_manifests() -> list[dict[str, Any]]:
    """Return the explicit SFH2R → SFH2R.1 transition chain.

    The second manifest is optional for checkouts containing only SFH2R.  Once
    present, it must be a chained transition rather than a blanket exemption
    for arbitrary current derived files.
    """
    result: list[dict[str, Any]] = []
    for path in (TRANSITION_PATH, TRANSITION_V2_PATH):
        value = _read(path, {})
        if isinstance(value, Mapping) and value:
            item = dict(value)
            item["_path"] = path
            result.append(item)
    return result


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


def _transition_chain_hashes() -> list[tuple[dict[str, str], dict[str, str]]]:
    """Read all explicitly recorded before/after hash pairs in order."""
    result: list[tuple[dict[str, str], dict[str, str]]] = []
    for manifest in transition_manifests():
        transition = manifest.get("active_input_transition")
        if not isinstance(transition, Mapping):
            continue
        before = transition.get("before_hashes")
        after = transition.get("after_hashes")
        if not isinstance(before, Mapping) or not isinstance(after, Mapping):
            continue
        result.append((
            {str(key): str(value) for key, value in before.items() if str(key) and str(value)},
            {str(key): str(value) for key, value in after.items() if str(key) and str(value)},
        ))
    return result


def _authority_hash_for_manifest(manifest: Mapping[str, Any]) -> str | None:
    path = manifest.get("_path")
    if path == TRANSITION_V2_PATH:
        return file_hash(ROOT / "data/annotation/sfh2r1-manual-semantic-authority.json")
    return _authority_hash()


def transition_is_valid() -> bool:
    manifests = transition_manifests()
    if not manifests:
        return False
    transitions = _transition_chain_hashes()
    if len(transitions) != len(manifests):
        return False
    previous_after: dict[str, str] | None = None
    for manifest, (before, after) in zip(manifests, transitions):
        if manifest.get("authority_sha256") != _authority_hash_for_manifest(manifest):
            return False
        if manifest.get("candidate_only") is not True or manifest.get("canonical_write_back") is not False:
            return False
        if not before or not after:
            return False
        if previous_after is not None:
            # Each repair must start from the exact bytes produced by its
            # predecessor.  This is the explicit version/baseline transition,
            # not a general waiver for regenerated derived artifacts.
            keys = set(previous_after) | set(before)
            if any(previous_after.get(key) != before.get(key) for key in keys):
                return False
        previous_after = after
    current = current_repair_input_hashes()
    return bool(previous_after and current == previous_after)


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
    chain = _transition_chain_hashes()
    if not chain:
        return False

    # The ordered snapshots are: before SFH2R, after SFH2R/before SFH2R.1,
    # and (when present) after SFH2R.1.  A prior frozen experiment may match
    # an earlier complete stage, but never an unrecorded mixture.
    snapshots: list[dict[str, str]] = [chain[0][0]]
    snapshots.extend(after for _, after in chain)
    target_index = next(
        (index for index, snapshot in enumerate(snapshots) if current_map == snapshot),
        len(snapshots) - 1,
    )

    active_keys = set(ACTIVE_REPAIR_INPUTS)
    frozen_active = {key: value for key, value in frozen_map.items() if key in active_keys}
    frozen_nonactive = {key: value for key, value in frozen_map.items() if key not in active_keys}
    if any(current_map.get(key) != value for key, value in frozen_nonactive.items()):
        return False
    if not frozen_active:
        return frozen_map == current_map

    # Callers such as HDA2 can carry a narrower snapshot than the full active
    # input set.  Matching an explicitly recorded earlier stage keeps that
    # compatibility while still requiring the complete transition chain to be
    # valid above.
    return any(
        all(snapshot.get(key) == value for key, value in frozen_active.items())
        for snapshot in snapshots[: target_index + 1]
    )


def frozen_snapshot_matches_current_or_authorized(
    frozen: Mapping[str, Any] | None,
    current: Mapping[str, Any] | None = None,
) -> bool:
    """Alias with a name suitable for snapshot validators."""
    return frozen_hashes_are_current_or_authorized(frozen, current)
