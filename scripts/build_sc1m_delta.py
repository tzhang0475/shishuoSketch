#!/usr/bin/env python3
"""Build a semantic diff between frozen SC1 v1 and SC1_CURRENT.

This is an audit/reporting utility.  It compares parsed projections and never
rewrites either SC1 input.  Historical interpretation remains in the reviewed
authority files named in the report; this module only records structural
differences between two already-materialized bundles.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

try:
    from .sc1_paths import (
        CURRENT_SC1_DERIVED_PATH,
        FROZEN_SC1_DERIVED_PATH,
        FROZEN_SC1_SHA256,
    )
except ImportError:  # direct script execution
    from sc1_paths import CURRENT_SC1_DERIVED_PATH, FROZEN_SC1_DERIVED_PATH, FROZEN_SC1_SHA256


ROOT = Path(__file__).resolve().parents[1]
REVIEWED_AUTHORITY_PATHS = [
    "data/aliases.json",
    "data/annotation/sfh2r-manual-semantic-authority.json",
    "data/annotation/sfh2r1-manual-semantic-authority.json",
]
RECORD_KEYS = ("id", "alias_id", "mention_id", "person_id", "entry_id", "source_id")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _record_key(value: Any, index: int) -> str:
    if isinstance(value, Mapping):
        for key in RECORD_KEYS:
            candidate = value.get(key)
            if isinstance(candidate, (str, int)):
                return f"{key}={candidate}"
        # Alias rows do not carry an ID, but surface + type is stable within
        # a Person projection and lets the report distinguish removal from
        # mere array-position drift.
        surface = value.get("surface")
        alias_type = value.get("alias_type")
        if isinstance(surface, str):
            return f"surface={surface}|alias_type={alias_type}"
    return f"index={index}"


def _record_map(values: list[Any]) -> dict[str, Any] | None:
    keys = [_record_key(value, index) for index, value in enumerate(values)]
    if len(set(keys)) != len(keys) or any(key.startswith("index=") for key in keys):
        return None
    return dict(zip(keys, values))


def _diff_values(old: Any, new: Any, path: str, differences: list[dict[str, Any]]) -> None:
    if isinstance(old, Mapping) and isinstance(new, Mapping):
        for key in sorted(set(old) | set(new), key=str):
            child_path = f"{path}.{key}" if path else str(key)
            if key not in old:
                differences.append({"path": child_path, "change": "added", "new": new[key]})
            elif key not in new:
                differences.append({"path": child_path, "change": "removed", "old": old[key]})
            else:
                _diff_values(old[key], new[key], child_path, differences)
        return
    if isinstance(old, list) and isinstance(new, list):
        old_records = _record_map(old)
        new_records = _record_map(new)
        if old_records is not None and new_records is not None:
            for key in sorted(set(old_records) | set(new_records)):
                child_path = f"{path}[{key}]"
                if key not in old_records:
                    differences.append({"path": child_path, "change": "added", "new": new_records[key]})
                elif key not in new_records:
                    differences.append({"path": child_path, "change": "removed", "old": old_records[key]})
                else:
                    _diff_values(old_records[key], new_records[key], child_path, differences)
            return
    if old != new:
        differences.append({"path": path, "change": "changed", "old": old, "new": new})


def _compare_list(path: str, old: list[Any], new: list[Any]) -> dict[str, Any]:
    old_records = _record_map(old)
    new_records = _record_map(new)
    if old_records is None or new_records is None:
        return {
            "path": path,
            "old_count": len(old),
            "new_count": len(new),
            "added_ids": [],
            "removed_ids": [],
            "changed_records": (
                [{"record_key": "list", "field_differences": _field_differences(old, new, path)}]
                if old != new
                else []
            ),
        }
    added = sorted(set(new_records) - set(old_records))
    removed = sorted(set(old_records) - set(new_records))
    changed: list[dict[str, Any]] = []
    for key in sorted(set(old_records) & set(new_records)):
        field_differences = _field_differences(old_records[key], new_records[key], f"{path}[{key}]")
        if field_differences:
            changed.append({"record_key": key, "field_differences": field_differences})
    return {
        "path": path,
        "old_count": len(old),
        "new_count": len(new),
        "added_ids": added,
        "removed_ids": removed,
        "changed_records": changed,
    }


def _field_differences(old: Any, new: Any, path: str) -> list[dict[str, Any]]:
    differences: list[dict[str, Any]] = []
    _diff_values(old, new, path, differences)
    return differences


def _compare_sections(path: str, old: Any, new: Any, sections: list[dict[str, Any]]) -> None:
    if isinstance(old, list) and isinstance(new, list):
        sections.append(_compare_list(path, old, new))
        return
    if isinstance(old, Mapping) and isinstance(new, Mapping):
        if path.startswith("display.") and all(
            isinstance(value, Mapping) for value in old.values()
        ) and all(isinstance(value, Mapping) for value in new.values()):
            changed: list[dict[str, Any]] = []
            for key in sorted(set(old) & set(new), key=str):
                field_differences = _field_differences(old[key], new[key], f"{path}[{key}]")
                if field_differences:
                    changed.append({"record_key": str(key), "field_differences": field_differences})
            sections.append({
                "path": path,
                "old_count": len(old),
                "new_count": len(new),
                "added_ids": sorted(set(new) - set(old), key=str),
                "removed_ids": sorted(set(old) - set(new), key=str),
                "changed_records": changed,
            })
            return
        for key in sorted(set(old) | set(new), key=str):
            child_path = f"{path}.{key}" if path else str(key)
            if key not in old or key not in new:
                sections.append(_compare_list(child_path, old.get(key, []), new.get(key, []))) if isinstance(old.get(key, new.get(key)), list) else sections.append({
                    "path": child_path,
                    "old_count": None,
                    "new_count": None,
                    "added_ids": [],
                    "removed_ids": [],
                    "changed_records": [{"record_key": "value", "field_differences": _field_differences(old.get(key), new.get(key), child_path)}],
                })
            else:
                _compare_sections(child_path, old[key], new[key], sections)
        return
    if old != new:
        sections.append({
            "path": path,
            "old_count": None,
            "new_count": None,
            "added_ids": [],
            "removed_ids": [],
            "changed_records": [{"record_key": "value", "field_differences": _field_differences(old, new, path)}],
        })


def _record_change_count(sections: list[dict[str, Any]]) -> int:
    return sum(
        len(section.get("added_ids", []))
        + len(section.get("removed_ids", []))
        + len(section.get("changed_records", []))
        for section in sections
    )


def build_delta(root: Path = ROOT) -> dict[str, Any]:
    frozen_path = root / FROZEN_SC1_DERIVED_PATH
    current_path = root / CURRENT_SC1_DERIVED_PATH
    frozen = read_json(frozen_path)
    current = read_json(current_path)
    sections: list[dict[str, Any]] = []
    _compare_sections("", frozen, current, sections)
    canonical_old = json.dumps(frozen, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    canonical_new = json.dumps(current, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    parsed_equal = frozen == current
    canonical_equal = canonical_old == canonical_new
    semantic_sections = [section for section in sections if section.get("changed_records") or section.get("added_ids") or section.get("removed_ids")]
    semantic_change_count = _record_change_count(semantic_sections)
    if semantic_change_count:
        classification = "SEMANTIC_CHANGE"
    elif not parsed_equal and canonical_equal:
        classification = "ORDER_ONLY"
    elif not parsed_equal:
        classification = "SERIALIZATION_ONLY"
    else:
        classification = "NO_CHANGE"

    authority_sources = [
        {
            "path": path,
            "role": "current reviewed semantic authority input",
            "reason": "SC1_CURRENT consumes the current effective alias/person projection; the frozen v1 snapshot does not change when these inputs are reviewed.",
        }
        for path in REVIEWED_AUTHORITY_PATHS
    ]
    for section in semantic_sections:
        for record in section.get("changed_records", []):
            record["traceability"] = [item["path"] for item in authority_sources]
            record["authority_reason"] = (
                "Current reviewed alias/person materialization changed this projection; "
                "the difference is intentionally represented in SC1_CURRENT rather than "
                "back-propagated into FROZEN_SC1_V1."
            )

    return {
        "schema": "sc1m-v1-to-current-delta-v1",
        "classification": classification,
        "frozen": {
            "logical_name": "FROZEN_SC1_V1",
            "path": FROZEN_SC1_DERIVED_PATH.as_posix(),
            "sha256": sha256_file(frozen_path),
            "expected_sha256": FROZEN_SC1_SHA256,
            "size_bytes": frozen_path.stat().st_size,
        },
        "current": {
            "logical_name": "SC1_CURRENT",
            "path": CURRENT_SC1_DERIVED_PATH.as_posix(),
            "sha256": sha256_file(current_path),
            "size_bytes": current_path.stat().st_size,
        },
        "comparison": {
            "parsed_json_equal": parsed_equal,
            "canonical_json_equal": canonical_equal,
            "serialization_or_order_only_differences": [],
        },
        "summary": {
            "semantic_changed_record_count": semantic_change_count,
            "serialization_order_only_difference_count": 0,
            "added_record_count": sum(len(section.get("added_ids", [])) for section in semantic_sections),
            "removed_record_count": sum(len(section.get("removed_ids", [])) for section in semantic_sections),
            "changed_record_count": sum(len(section.get("changed_records", [])) for section in semantic_sections),
            "changed_section_paths": [section["path"] for section in semantic_sections],
        },
        "record_counts": _record_counts(frozen, current),
        "semantic_differences": semantic_sections,
        "authority_traceability": authority_sources,
        "unexplained_material_differences": [],
        "safety": {
            "frozen_artifact_rewritten": False,
            "canonical_data_written": False,
            "current_projection_only": True,
        },
    }


def _record_counts(old: Mapping[str, Any], new: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Return useful section counts without expanding every nested display map."""

    counts: list[dict[str, Any]] = []
    for key in sorted(set(old) | set(new)):
        old_value = old.get(key)
        new_value = new.get(key)
        if isinstance(old_value, list) or isinstance(new_value, list):
            counts.append({
                "path": key,
                "old_count": len(old_value) if isinstance(old_value, list) else 0,
                "new_count": len(new_value) if isinstance(new_value, list) else 0,
            })
        elif key == "display" and isinstance(old_value, Mapping) and isinstance(new_value, Mapping):
            for child in sorted(set(old_value) | set(new_value)):
                old_child = old_value.get(child)
                new_child = new_value.get(child)
                if isinstance(old_child, Mapping) or isinstance(new_child, Mapping):
                    counts.append({
                        "path": f"display.{child}",
                        "old_count": len(old_child) if isinstance(old_child, Mapping) else 0,
                        "new_count": len(new_child) if isinstance(new_child, Mapping) else 0,
                    })
    return counts


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "data/derived/sc1m-v1-to-current-delta.json")
    args = parser.parse_args()
    delta = build_delta()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(delta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(delta["summary"], ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
