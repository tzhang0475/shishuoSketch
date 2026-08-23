#!/usr/bin/env python3
"""Build the small static HNG0.1 browser projection without calling a model."""

from __future__ import annotations

import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data/generated/hng0-1"
FRONTEND = ROOT / "site/src/generated/hng0-1-site.json"


def read(path: Path, default):
    if not path.is_file():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def build() -> dict:
    manifest = read(OUT / "manifest.json", {})
    relations_doc = read(OUT / "candidate-relations.json", {"relations": [], "evidence": {}})
    times_doc = read(OUT / "candidate-temporal-items.json", {"temporal_items": [], "evidence": {}})
    profiles_doc = read(OUT / "seed-search-profiles.json", {"profiles": {}})
    neighborhoods = read(OUT / "neighborhoods.json", {"people": {}})
    metrics = read(OUT / "metrics.json", {})
    relations = relations_doc.get("relations", [])
    times = times_doc.get("temporal_items", [])
    evidence = relations_doc.get("evidence", {})
    return {
        "schema": 1,
        "stage": "hng0-1-frontend-review",
        "canonical_write_back": False,
        "execution_kind": manifest.get("execution_kind", "not_run"),
        "run_id": manifest.get("run_id"),
        "people": neighborhoods.get("people", {}),
        "profiles": profiles_doc.get("profiles", {}),
        "relations": relations,
        "temporal_items": times,
        "evidence": evidence,
        "metrics": metrics,
        "review_storage": "localStorage:shishuoSketch.hng0-1-review",
        "source_label": "Newly extracted",
    }


def main() -> int:
    value = build()
    FRONTEND.parent.mkdir(parents=True, exist_ok=True)
    FRONTEND.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"status": "pass", "execution_kind": value["execution_kind"], "relations": len(value["relations"]), "temporal_items": len(value["temporal_items"])}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
