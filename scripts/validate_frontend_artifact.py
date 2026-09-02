#!/usr/bin/env python3
"""Validate the generated Vite input and the actual production bundle.

The WP1 builder writes the research-side derived archive and the Vite input
from one in-memory bundle.  This check prevents those generated views from
drifting and verifies that the production JavaScript contains the data the
application imports at build time.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any

try:
    from .sc1_paths import CURRENT_SC1_DERIVED_PATH, CURRENT_SC1_VITE_PATH
except ImportError:  # direct script execution
    from sc1_paths import CURRENT_SC1_DERIVED_PATH, CURRENT_SC1_VITE_PATH


ROOT = Path(__file__).resolve().parents[1]
DERIVED_PATH = ROOT / "data/derived/wp1-site.json"
VITE_INPUT_PATH = ROOT / "site/src/generated/wp1-site.json"
SC1_DERIVED_PATH = ROOT / CURRENT_SC1_DERIVED_PATH
SC1_VITE_INPUT_PATH = ROOT / CURRENT_SC1_VITE_PATH
DIST_PATH = ROOT / "dist"


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def generated_errors(root: Path = ROOT) -> list[str]:
    errors: list[str] = []
    derived_path = root / DERIVED_PATH.relative_to(ROOT)
    vite_path = root / VITE_INPUT_PATH.relative_to(ROOT)
    try:
        if derived_path.read_bytes() != vite_path.read_bytes():
            errors.append("Vite input bytes differ from data/derived/wp1-site.json")
    except OSError as exc:
        errors.append(f"cannot compare generated bundle bytes: {exc}")
    try:
        derived = read_json(derived_path)
    except (OSError, ValueError) as exc:
        return [f"cannot read derived bundle {derived_path}: {exc}"]
    try:
        vite_input = read_json(vite_path)
    except (OSError, ValueError) as exc:
        return [f"cannot read Vite input {vite_path}: {exc}"]
    if derived != vite_input:
        errors.append("Vite input differs from data/derived/wp1-site.json")
    stories = vite_input.get("stories") if isinstance(vite_input, dict) else None
    story = next(
        (item for item in stories or [] if isinstance(item, dict) and item.get("id") == "06-yaliang-019"),
        None,
    )
    if story is None:
        errors.append("generated bundle lacks Story 06-yaliang-019")
        return errors
    reading = story.get("reading")
    if not isinstance(reading, dict):
        errors.append("06-yaliang-019 lacks reading")
        return errors
    for key in ("main_text", "annotations", "labels", "person_display", "mention_display", "source_display", "relation_display", "evidence_display"):
        if key not in reading:
            errors.append(f"06-yaliang-019 reading lacks {key}")
    return errors


def sc1_generated_errors(root: Path = ROOT) -> list[str]:
    """Validate the actual SC1 bundle imported by the deployed app."""
    try:
        from .validate_sc1_frontend_data import validate
    except ImportError:  # direct script execution
        from validate_sc1_frontend_data import validate
    return validate(root, mode=os.environ.get("WP1_PROVENANCE_MODE", "full"))


def _production_markers(bundle: dict[str, Any]) -> set[str]:
    story = next(item for item in bundle["stories"] if item["id"] == "06-yaliang-019")
    reading = story["reading"]
    markers = {
        story["id"],
        "reading",
        "display",
        "person_sketches",
        "evidence",
        "relations",
        reading["main_text"]["original"],
        reading["main_text"]["simplified"],
    }
    markers.update(person["id"] for person in bundle["people"])
    markers.update(
        sketch["identity"]["canonical_name"]["original"]
        for sketch in bundle.get("person_sketches", {}).values()
    )
    markers.update(relation["id"] for relation in bundle["relations"])
    markers.update(evidence["id"] for evidence in bundle["evidence"])
    return markers


def production_errors(root: Path = ROOT) -> list[str]:
    errors = generated_errors(root) + sc1_generated_errors(root)
    bundle = read_json(root / SC1_DERIVED_PATH.relative_to(ROOT))
    dist = root / DIST_PATH.relative_to(ROOT)
    assets = sorted((dist / "assets").glob("*.js")) if (dist / "assets").is_dir() else []
    if not assets:
        errors.append(f"production JavaScript assets are missing under {dist / 'assets'}")
        return errors
    javascript = "\n".join(path.read_text(encoding="utf-8") for path in assets)
    for marker in sorted(_production_markers(bundle)):
        if marker not in javascript:
            errors.append(f"production JavaScript does not contain frontend-data marker: {marker}")
    if "data/wp1-site.json" in javascript:
        errors.append("production JavaScript still references the obsolete runtime JSON URL")
    if (dist / "data/wp1-site.json").exists():
        errors.append("production artifact contains obsolete dist/data/wp1-site.json")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--production", action="store_true", help="also inspect the Vite dist artifact")
    args = parser.parse_args()
    errors = production_errors() if args.production else generated_errors()
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1
    print("frontend artifact validation passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
