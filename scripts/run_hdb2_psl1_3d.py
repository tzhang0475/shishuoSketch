#!/usr/bin/env python3
"""Build the offline HDB2-PSL1.3D regression/replay namespace.

PSL1.3D is a closeout boundary repair.  It does not rerun DeepSeek or change
the frozen C decisions.  The replay rebuilds the candidate-only profile
projection, records the source-level identity-claim audit, and verifies the
same twelve known C safety expectations in a new isolated namespace.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import shutil
import sys
from pathlib import Path
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import hdb2_full_frontier_common as common  # noqa: E402
import rebuild_hdb2_f_profiles as profiles  # noqa: E402


SOURCE_RUN = ROOT / "data/generated/hdb2-psl1-3c/live/20260828T-HDB2-PSL1-3C-REPLAY-12"
OUT_ROOT = ROOT / "data/generated/hdb2-psl1-3d/live"
DEFAULT_RUN_ID = "20260828T-HDB2-PSL1-3D-OFFLINE-01"
EXPECTED_STORIES = (
    "10-guizhen-016",
    "23-rendan-033",
    "06-yaliang-041",
    "23-rendan-049",
    "09-pinzao-088",
    "08-shangyu-020",
    "01-dexing-028",
    "09-pinzao-018",
    "09-pinzao-008",
    "02-yanyu-086",
)
FORBIDDEN_STABLE_RESOLUTIONS = {
    ("09-pinzao-018", "潁"): {"鄧攸"},
    ("09-pinzao-088", "桓"): {"朱伺", "卞範之"},
    ("23-rendan-049", "桓"): {"朱伺", "卞範之"},
    ("06-yaliang-041", "殷荆州"): {"王恭"},
    ("02-yanyu-086", "王子敬"): {"王恭"},
}


def read(path: Path, default: Any = None) -> Any:
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else default


def write(path: Path, value: Any) -> None:
    common.write_json(path, value)


def _source_selection() -> dict[str, Any]:
    selection = read(SOURCE_RUN / "selection.json", {}) or {}
    if not selection:
        raise RuntimeError(f"missing_c3_selection:{SOURCE_RUN}")
    stories = tuple(str(row.get("story_id")) for row in selection.get("independent_cases", []) if row.get("story_id"))
    if stories != EXPECTED_STORIES:
        raise RuntimeError(f"c3_selection_changed:{stories}")
    if selection.get("candidate_only") is not True or selection.get("canonical_write_back") is not False:
        raise RuntimeError("c3_selection_safety_invalid")
    return selection


def _final_rows() -> list[dict[str, Any]]:
    rows = read(SOURCE_RUN / "decisions-final.json", {}) or {}
    return [dict(row) for row in rows.get("records", []) or [] if isinstance(row, Mapping)]


def _safety_audit(rows: list[dict[str, Any]], claim_audit: Mapping[str, Any], profile_audit: Mapping[str, Any]) -> dict[str, Any]:
    forbidden: list[dict[str, Any]] = []
    for row in rows:
        key = (str(row.get("story_id") or ""), str(row.get("surface") or ""))
        state = str(row.get("result_state") or "")
        top = str(row.get("top_candidate") or "")
        if state in {"stable_entity_resolved", "local_candidate_resolved"} and top in FORBIDDEN_STABLE_RESOLUTIONS.get(key, set()):
            forbidden.append({"story_id": key[0], "surface": key[1], "state": state, "top_candidate": top})

    source_collision = [
        row
        for row in claim_audit.get("invalid_source_identity_claims", []) or []
        if row.get("story_id") == "09-pinzao-088"
        and row.get("surface") == "仲文"
        and row.get("target_person_id") == "person-031"
    ]
    checks = {
        "false_stable_resolutions_zero": not forbidden,
        "known_仲文_source_claim_rejected": len(source_collision) == 1 and source_collision[0].get("source_claim_supported") is False,
        "profile_forms_have_provenance": profile_audit.get("forms_without_identity_provenance", 0) == 0,
        "known_profile_contamination_zero": not profile_audit.get("known_contamination_remaining"),
        "candidate_only": profile_audit.get("candidate_only") is True and claim_audit.get("candidate_only") is True,
        "canonical_write_back_false": profile_audit.get("canonical_write_back") is False and claim_audit.get("canonical_write_back") is False,
        "no_api_calls": True,
    }
    return {
        "known_forbidden_stable_resolutions": forbidden,
        "source_level_collision_audit": source_collision,
        "safety_checks": checks,
        "safety_gates_pass": all(checks.values()),
    }


def replay(*, run_id: str = DEFAULT_RUN_ID) -> Path:
    selection = _source_selection()
    source_manifest = read(SOURCE_RUN / "manifest.json", {}) or {}
    destination = OUT_ROOT / run_id
    if destination.exists():
        raise RuntimeError(f"hdb2_psl1_3d_run_exists:{destination}")

    # Rebuild only candidate-only profile projections.  The HDB2-F semantic
    # occurrence/relation decisions remain read-only inputs to this replay.
    profile_audit = profiles.rebuild(write=True)
    claim_audit = read(profiles.IDENTITY_CLAIM_AUDIT_PATH, {}) or {}
    rows = _final_rows()
    if len(rows) != len(EXPECTED_STORIES):
        raise RuntimeError(f"c3_final_shape_invalid:{len(rows)}")
    destination.mkdir(parents=True, exist_ok=False)

    selection_hash = str(selection.get("selection_hash") or common.stable_hash(selection))
    profile_audit_path = profiles.AUDIT_PATH.relative_to(ROOT).as_posix()
    claim_audit_path = profiles.IDENTITY_CLAIM_AUDIT_PATH.relative_to(ROOT).as_posix()
    safety = _safety_audit(rows, claim_audit, profile_audit)
    manifest = {
        "schema": "hdb2-psl1-3d-offline-replay-manifest-v1",
        "run_id": run_id,
        "run_version": "hdb2-psl1-3d-v1",
        "source_run": SOURCE_RUN.relative_to(ROOT).as_posix(),
        "source_run_selection_hash": selection_hash,
        "source_run_manifest_hash": common.stable_hash(source_manifest),
        "replayed_without_api": True,
        "api_calls_this_run": 0,
        "semantic_calls_this_run": 0,
        "candidate_only": True,
        "canonical_write_back": False,
        "profile_audit_path": profile_audit_path,
        "identity_claim_audit_path": claim_audit_path,
        "profile_integrity_version": "hdb2-f-profile-integrity-v2",
        "source_decisions_unchanged": True,
        "created_at": dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
    }
    write(destination / "manifest.json", manifest)
    write(destination / "selection.json", selection)
    write(destination / "python-decisions.json", {
        "schema": "hdb2-psl1-3d-python-decisions-v1",
        "records": rows,
        "candidate_only": True,
        "canonical_write_back": False,
        "source_decisions_hash": common.stable_hash(rows),
    })
    write(destination / "profile-integrity-audit.json", profile_audit)
    write(destination / "identity-claim-integrity-audit.json", claim_audit)
    write(destination / "validation-summary.json", {
        "schema": "hdb2-psl1-3d-validation-summary-v1",
        "replayed_without_api": True,
        "api_calls_this_run": 0,
        "candidate_only": True,
        "canonical_write_back": False,
        "source_decisions_unchanged": True,
        "profile_audit_path": profile_audit_path,
        "identity_claim_audit_path": claim_audit_path,
        **safety,
    })
    write(destination / "audit.json", {
        "schema": "hdb2-psl1-3d-audit-v1",
        "story_ids": list(EXPECTED_STORIES),
        "state_counts": {
            state: sum(str(row.get("result_state") or "") == state for row in rows)
            for state in sorted({str(row.get("result_state") or "") for row in rows})
        },
        "source_decisions_hash": common.stable_hash(rows),
        **safety,
    })
    return destination


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id", default=DEFAULT_RUN_ID)
    args = parser.parse_args()
    result = replay(run_id=args.run_id)
    print(json.dumps({"run_dir": result.relative_to(ROOT).as_posix(), "replayed_without_api": True, "api_calls_this_run": 0}, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
