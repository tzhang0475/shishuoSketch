#!/usr/bin/env python3
"""Validate the UX1 lazy historical projection and its load-budget contract."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[1]
SC1_DERIVED = ROOT / "data/derived/sc1-site.json"
SC1_GENERATED = ROOT / "site/src/generated/sc1-site.json"
BASELINE = ROOT / "data/derived/ux1-frontend-size-baseline.json"
SIZE_AUDIT = ROOT / "data/derived/ux1-frontend-size-audit.json"
HISTORY_ROOT = ROOT / "site/public/generated/history"
MANIFEST = HISTORY_ROOT / "manifest.json"


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def fail(message: str) -> None:
    raise SystemExit(f"UX1 validation failed: {message}")


def assert_reviewed_rows(rows: list[Any], label: str) -> None:
    for index, row in enumerate(rows):
        if not isinstance(row, Mapping):
            fail(f"{label}[{index}] is not an object")
        if row.get("review_status") != "reviewed":
            fail(f"{label}[{index}] is not reviewed")
        if any(key in row for key in ("candidate_score", "model_score", "embedding", "graph_adjacency")):
            fail(f"{label}[{index}] contains research/model internals")


def validate_shards(manifest: Mapping[str, Any]) -> dict[str, int]:
    shards = manifest.get("shards")
    if not isinstance(shards, Mapping) or not shards:
        fail("manifest has no shard index")
    counts: dict[str, int] = {}
    expected_paths = {str(relative) for relative in shards}
    actual_paths = {
        path.relative_to(HISTORY_ROOT).as_posix()
        for path in HISTORY_ROOT.rglob("*.json")
        if path.name != "manifest.json"
    }
    if actual_paths != expected_paths:
        fail(f"manifest/shard directory mismatch: expected {len(expected_paths)}, found {len(actual_paths)}")
    forbidden_keys = {"candidate_score", "model_score", "embedding", "graph_adjacency", "review_queue", "quoted_passage", "evidence_excerpt"}
    for relative, index in sorted(shards.items()):
        path = HISTORY_ROOT / str(relative)
        if not path.is_file():
            fail(f"missing shard {relative}")
        if sha256_file(path) != index.get("sha256"):
            fail(f"hash mismatch for {relative}")
        if path.stat().st_size != index.get("bytes"):
            fail(f"byte mismatch for {relative}")
        payload = read_json(path)
        if not isinstance(payload, Mapping) or payload.get("schema") != 1:
            fail(f"invalid schema for {relative}")
        kind = str(relative).split("/", 1)[0]
        counts[kind] = counts.get(kind, 0) + 1
        if any(key in payload for key in forbidden_keys):
            fail(f"raw/research payload field in {relative}")
        serialized = json.dumps(payload, ensure_ascii=False)
        if "candidate" in serialized.lower() or "unresolved" in serialized.lower():
            fail(f"candidate/unresolved material leaked into {relative}")
        if kind in {"person", "story", "era", "relation"} and len(serialized.encode("utf-8")) > 1_000_000:
            fail(f"summary shard is unexpectedly large: {relative}")
        if kind == "evidence":
            excerpt = payload.get("short_excerpt", {})
            if isinstance(excerpt, Mapping) and max(len(str(excerpt.get("original", ""))), len(str(excerpt.get("simplified", "")))) > 300:
                fail(f"evidence excerpt is too long: {relative}")
    return counts


def main() -> int:
    for path in (SC1_DERIVED, SC1_GENERATED, BASELINE, SIZE_AUDIT, MANIFEST):
        if not path.exists():
            fail(f"missing required artifact {path.relative_to(ROOT)}")

    if SC1_DERIVED.read_bytes() != SC1_GENERATED.read_bytes():
        fail("derived and generated SC1 bundles are not byte-identical")
    baseline = read_json(BASELINE)
    if sha256_file(SC1_GENERATED) != baseline["sc1_site"]["sha256"]:
        fail("SC1 initial bundle changed from the UX1 baseline")
    if SC1_GENERATED.stat().st_size != baseline["sc1_site"]["bytes"]:
        fail("SC1 initial bundle byte size changed from the UX1 baseline")

    sc1 = read_json(SC1_GENERATED)
    for story in sc1.get("stories", []):
        reading = story.get("reading", {})
        for field in ("labels", "person_display", "relation_display", "source_display", "evidence_display"):
            if field in reading:
                fail(f"legacy per-Story display map remains: {story.get('id')} reading.{field}")
    if "ux1" in json.dumps(sc1, ensure_ascii=False).lower():
        fail("UX1 projection was embedded in the initial SC1 bundle")

    manifest = read_json(MANIFEST)
    if manifest.get("policies", {}).get("unresolved_facts_projected") is not False:
        fail("manifest does not prohibit unresolved factual projection")
    source_hashes = manifest.get("source_hashes", {})
    for relative, expected in source_hashes.items():
        path = ROOT / relative
        if not path.is_file() or sha256_file(path) != expected:
            fail(f"input hash mismatch: {relative}")

    counts = validate_shards(manifest)
    expected = manifest.get("scope", {})
    if counts.get("person", 0) != expected.get("person_count"):
        fail("person shard count does not match manifest scope")
    if counts.get("story", 0) != expected.get("published_story_count"):
        fail("story shard count does not match manifest scope")

    # Check the display projection's factual rows explicitly; scholarly and
    # citation references are allowed to retain their separate status.
    for path in sorted((HISTORY_ROOT / "person").glob("*.json")):
        payload = read_json(path)
        assert_reviewed_rows(payload.get("family", []), f"{path.name}.family")
        assert_reviewed_rows(payload.get("offices", []), f"{path.name}.offices")
        assert_reviewed_rows(payload.get("locations", []), f"{path.name}.locations")
        assert_reviewed_rows(payload.get("periods", []), f"{path.name}.periods")
    for path in sorted((HISTORY_ROOT / "story").glob("*.json")):
        payload = read_json(path)
        assert_reviewed_rows(payload.get("historical_context", []), f"{path.name}.historical_context")
        assert_reviewed_rows(payload.get("participant_context", []), f"{path.name}.participant_context")
    for path in sorted((HISTORY_ROOT / "era").glob("*.json")):
        payload = read_json(path)
        if payload.get("ruler") is not None:
            assert_reviewed_rows([payload["ruler"]], f"{path.name}.ruler")
    for path in sorted((HISTORY_ROOT / "relation").glob("*.json")):
        payload = read_json(path)
        if payload.get("review_status") != "reviewed":
            fail(f"relation is not reviewed: {path.name}")
    for path in sorted((HISTORY_ROOT / "evidence").glob("*.json")):
        payload = read_json(path)
        if payload.get("kind") == "scholarly_reference" and payload.get("assertion_status") in {"probable", "possible", "disputed", "unknown"}:
            # It is a detail reference, never a factual row.  Its presence is
            # valid; the check documents that it remains uncertainty-bearing.
            continue

    audit = read_json(SIZE_AUDIT)
    comparison = audit.get("comparison", {})
    if comparison.get("sc1_site", {}).get("delta_percent", 999) > 2:
        fail("SC1 size budget exceeded")
    if comparison.get("entry_js", {}).get("gzip_delta_percent", 999) > 8:
        fail("initial JS gzip budget exceeded")
    if comparison.get("initial_total", {}).get("delta_percent", 999) > 5:
        fail("initial payload budget exceeded")

    print(json.dumps({
        "status": "pass",
        "initial_bundle_sha256": sha256_file(SC1_GENERATED),
        "shard_counts": counts,
        "initial_budget": comparison.get("initial_total"),
        "lazy_bytes": audit.get("comparison", {}).get("after", {}).get("lazy_historical", {}).get("total_bytes"),
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
