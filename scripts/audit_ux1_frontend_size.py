#!/usr/bin/env python3
"""Measure the UX1 initial payload and lazy historical projection.

The initial reader is deliberately measured separately from the generated
historical shards.  This keeps the UX1 performance contract explicit: the
reader bundle is the baseline, while historical depth is an on-demand static
projection.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SC1_PATH = ROOT / "site/src/generated/sc1-site.json"
BASELINE_PATH = ROOT / "data/derived/ux1-frontend-size-baseline.json"
AUDIT_PATH = ROOT / "data/derived/ux1-frontend-size-audit.json"
DIST_PATH = ROOT / "dist"
HISTORY_PATH = ROOT / "site/public/generated/history"


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def file_metrics(path: Path) -> dict[str, Any]:
    payload = path.read_bytes()
    return {
        "path": path.relative_to(ROOT).as_posix(),
        "bytes": len(payload),
        "gzip_bytes": len(gzip.compress(payload, mtime=0)),
        "sha256": sha256_bytes(payload),
    }


def current_commit() -> str | None:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            cwd=ROOT,
            text=True,
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        return None


def dist_metrics() -> dict[str, Any]:
    assets = sorted(
        path for path in DIST_PATH.rglob("*")
        if path.is_file() and path.name != ".gitkeep"
    ) if DIST_PATH.exists() else []
    js = sorted(path for path in assets if path.suffix == ".js")
    css = sorted(path for path in assets if path.suffix == ".css")
    html = sorted(path for path in assets if path.suffix == ".html")
    initial_paths = js + css + html
    return {
        "entry_js": file_metrics(js[0]) if js else None,
        "css": file_metrics(css[0]) if css else None,
        "index_html": file_metrics(html[0]) if html else None,
        "initial_assets": [file_metrics(path) for path in initial_paths],
        "initial_total": {
            "bytes": sum(file_metrics(path)["bytes"] for path in initial_paths),
            "gzip_bytes": sum(file_metrics(path)["gzip_bytes"] for path in initial_paths),
        },
    }


def lazy_metrics() -> dict[str, Any]:
    files = sorted(path for path in HISTORY_PATH.rglob("*.json") if path.is_file()) if HISTORY_PATH.exists() else []
    by_kind: dict[str, list[dict[str, Any]]] = {}
    manifest_metrics: dict[str, Any] | None = None
    for path in files:
        relative = path.relative_to(HISTORY_PATH)
        if relative.as_posix() == "manifest.json":
            manifest_metrics = file_metrics(path)
            continue
        kind = relative.parts[0] if relative.parts else "unknown"
        by_kind.setdefault(kind, []).append(file_metrics(path))
    all_metrics = [metric for metrics in by_kind.values() for metric in metrics]
    raw_sizes = sorted(metric["bytes"] for metric in all_metrics)
    median = raw_sizes[len(raw_sizes) // 2] if raw_sizes else 0
    return {
        "total_files": len(all_metrics),
        "total_bytes": sum(metric["bytes"] for metric in all_metrics),
        "total_gzip_bytes": sum(metric["gzip_bytes"] for metric in all_metrics),
        "manifest": manifest_metrics,
        "median_bytes": median,
        "max_bytes": max(raw_sizes, default=0),
        "by_kind": {
            kind: {
                "count": len(metrics),
                "bytes": sum(metric["bytes"] for metric in metrics),
                "gzip_bytes": sum(metric["gzip_bytes"] for metric in metrics),
                "max_bytes": max((metric["bytes"] for metric in metrics), default=0),
            }
            for kind, metrics in sorted(by_kind.items())
        },
    }


def measure() -> dict[str, Any]:
    sc1 = file_metrics(SC1_PATH)
    return {
        "schema": 1,
        "stage": "UX1",
        "sc1_site": sc1,
        "initial": dist_metrics(),
        "lazy_historical": lazy_metrics(),
    }


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_baseline() -> dict[str, Any]:
    measured = measure()
    baseline = {
        "schema": 1,
        "stage": "UX1",
        "kind": "initial_frontend_size_baseline",
        "baseline_commit": current_commit(),
        "sc1_site": measured["sc1_site"],
        "initial": measured["initial"],
        "protected_contract": {
            "sc1_site_is_initial_bundle": True,
            "historical_shards_are_not_initial_assets": True,
        },
    }
    write_json(BASELINE_PATH, baseline)
    return baseline


def compare(baseline: dict[str, Any], current: dict[str, Any]) -> dict[str, Any]:
    def delta(path: tuple[str, ...]) -> dict[str, Any]:
        old: Any = baseline
        new: Any = current
        for key in path:
            old = old[key]
            new = new[key]
        old_bytes = old.get("bytes", 0)
        new_bytes = new.get("bytes", 0)
        old_gzip = old.get("gzip_bytes", 0)
        new_gzip = new.get("gzip_bytes", 0)
        return {
            "before_bytes": old_bytes,
            "after_bytes": new_bytes,
            "delta_bytes": new_bytes - old_bytes,
            "delta_percent": round(((new_bytes - old_bytes) / old_bytes * 100) if old_bytes else 0, 4),
            "before_gzip_bytes": old_gzip,
            "after_gzip_bytes": new_gzip,
            "gzip_delta_bytes": new_gzip - old_gzip,
            "gzip_delta_percent": round(((new_gzip - old_gzip) / old_gzip * 100) if old_gzip else 0, 4),
        }

    return {
        "sc1_site": delta(("sc1_site",)),
        "entry_js": delta(("initial", "entry_js")),
        "css": delta(("initial", "css")),
        "initial_total": delta(("initial", "initial_total")),
        "before": baseline,
        "after": current,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write-baseline", action="store_true")
    parser.add_argument("--output", type=Path, default=AUDIT_PATH)
    args = parser.parse_args()

    current = measure()
    if args.write_baseline:
        write_baseline()
        print(json.dumps(current, ensure_ascii=False, indent=2))
        return 0
    if not BASELINE_PATH.exists():
        raise SystemExit(f"missing UX1 baseline: {BASELINE_PATH}")
    baseline = json.loads(BASELINE_PATH.read_text(encoding="utf-8"))
    audit = {
        "schema": 1,
        "stage": "UX1",
        "kind": "initial_frontend_size_audit",
        "baseline_commit": baseline.get("baseline_commit"),
        "comparison": compare(baseline, current),
        "budget": {
            "sc1_site_max_delta_percent": 2.0,
            "entry_js_gzip_max_delta_percent": 8.0,
            "css_gzip_target_delta_percent": 5.0,
            "initial_total_max_delta_percent": 5.0,
        },
    }
    write_json(args.output, audit)
    print(json.dumps(audit, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
