#!/usr/bin/env python3
"""Validate that derived Person aliases do not merge adjacent repetitions."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

try:
    from .materialize_person_expansion import _is_synthetic_repeated_title_surface
except ImportError:  # direct execution
    from materialize_person_expansion import _is_synthetic_repeated_title_surface


ROOT = Path(__file__).resolve().parents[1]


def _read(root: Path, relative: str) -> Any:
    return json.loads((root / relative).read_text(encoding="utf-8"))


def validate(root: Path = ROOT) -> list[str]:
    errors: list[str] = []
    aliases = _read(root, "data/aliases.json").get("aliases", [])
    for alias in aliases:
        if not isinstance(alias, dict):
            continue
        if _is_synthetic_repeated_title_surface(
            str(alias.get("surface", "")),
            str(alias.get("alias_type", "")),
        ):
            errors.append(
                "production Alias is a synthetic adjacent repetition: "
                f"{alias.get('alias_id')}/{alias.get('surface')}"
            )

    materialization = _read(
        root, "data/derived/person-expansion-wave-2-materialization.json"
    )
    for member in materialization.get("members", []):
        if not isinstance(member, dict):
            continue
        for occurrence in member.get("withheld_occurrences", []):
            if not isinstance(occurrence, dict):
                continue
            if _is_synthetic_repeated_title_surface(
                str(occurrence.get("surface", "")),
                "contextual_title",
            ):
                errors.append(
                    "Wave-2 occurrence is a synthetic adjacent repetition: "
                    f"{occurrence.get('occurrence_id')}/{occurrence.get('surface')}"
                )
    return sorted(errors)


if __name__ == "__main__":
    problems = validate()
    if problems:
        print("Person alias segmentation validation failed:")
        print("\n".join(f"- {problem}" for problem in problems))
        raise SystemExit(1)
    print("Person alias segmentation validation passed")
