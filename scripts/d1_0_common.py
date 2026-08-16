#!/usr/bin/env python3
"""Shared deterministic measurements for the D1.0 runtime-bundle audit.

This module is intentionally read-only with respect to production data.  It
measures the two existing SC1 views, scans textual consumers, and records a
small protection manifest.  It does not build, rewrite, or normalize SC1.
"""

from __future__ import annotations

from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[1]
SC1_DERIVED_PATH = ROOT / "data/derived/sc1-site.json"
SC1_GENERATED_PATH = ROOT / "site/src/generated/sc1-site.json"

AUDIT_PATH = ROOT / "data/derived/d1-0-bundle-size-audit.json"
DEPENDENCY_PATH = ROOT / "data/derived/d1-0-dependency-audit.json"

REQUIRED_TOP_LEVEL_FIELDS = [
    "schema",
    "generated_from",
    "stories",
    "people",
    "mentions",
    "relations",
    "eras",
    "evidence",
    "sources",
    "ruler_identities",
    "era_cards",
    "ruler_mentions",
    "historical_events",
    "story_era_orientations",
    "person_sketches",
    "scene_contexts",
    "story_chain",
    "ui",
]

# These are the source/data layers whose accidental mutation would invalidate
# the D1.0 comparison.  The manifest is a protection check, not a replacement
# for the project's existing validators.
PROTECTED_PATHS = [
    "data/people.json",
    "data/aliases.json",
    "data/mentions/shishuo.json",
    "data/derived/person-story-index.json",
    "data/annotation/wp1-punctuation.json",
    "data/annotation/wp1-relations.json",
    "data/evidence/wp1-evidence.json",
    "data/derived/h0c-participant-freeze.json",
    "data/derived/h0c-historical-facts.json",
    "data/derived/hg0-ontology.json",
    "data/derived/hg0-graph-projection.json",
    "data/derived/ml0-dataset-manifest.json",
    "data/derived/x1-1-selection-manifest.json",
    "data/derived/x1-2a-review-manifest.json",
    "data/derived/x1-2p-summary.json",
]

DEPENDENCY_TERMS = [
    "data/derived/sc1-site.json",
    "site/src/generated/sc1-site.json",
    "SiteBundle",
    "loadSiteBundle",
    "parseSiteBundle",
]

EXCLUDED_SCAN_PARTS = {".git", "node_modules", "dist", "__pycache__"}
EXCLUDED_SCAN_FILES = {
    "data/derived/sc1-site.json",
    "site/src/generated/sc1-site.json",
    "data/derived/d1-0-bundle-size-audit.json",
    "data/derived/d1-0-dependency-audit.json",
    "scripts/d1_0_common.py",
    "scripts/build_d1_0_audit.py",
    "scripts/validate_d1_0.py",
    "tests/test_d1_0.py",
    "docs/d1-0-runtime-bundle-audit.md",
}


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def compact_bytes(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def compact_size(value: Any) -> int:
    return len(compact_bytes(value))


def pretty_size(value: Any) -> int:
    return len(json.dumps(value, ensure_ascii=False, indent=2).encode("utf-8"))


def pct(value: int | float, total: int) -> float:
    return round((100.0 * value / total), 6) if total else 0.0


def display_key(value: Any, fallback: str) -> str:
    if isinstance(value, dict):
        for key in ("id", "story_id", "person_id", "era_card_id", "ruler_id", "mention_id", "event_id"):
            candidate = value.get(key)
            if isinstance(candidate, str):
                return candidate
    return fallback


def record_items(name: str, value: Any) -> list[tuple[str, Any]]:
    if isinstance(value, list):
        return [(display_key(item, str(index)), item) for index, item in enumerate(value)]
    if isinstance(value, dict) and name in {"person_sketches", "scene_contexts"}:
        return [(str(key), item) for key, item in value.items()]
    return []


def record_count(name: str, value: Any) -> int:
    if isinstance(value, list):
        return len(value)
    if isinstance(value, dict) and name in {"person_sketches", "scene_contexts"}:
        return len(value)
    return 1


def largest_records(name: str, value: Any, limit: int = 10) -> list[dict[str, Any]]:
    rows = [
        {"record_id": key, "bytes": compact_size(item)}
        for key, item in record_items(name, value)
    ]
    return sorted(rows, key=lambda row: (-row["bytes"], row["record_id"]))[:limit]


def field_metric(
    path: str,
    value: Any,
    total_bytes: int,
    *,
    record_name: str | None = None,
    notes: str | None = None,
) -> dict[str, Any]:
    name = record_name or path.rsplit(".", 1)[-1]
    items = record_items(name, value)
    item_bytes = [compact_size(item) for _, item in items]
    result: dict[str, Any] = {
        "path": path,
        "value_kind": type(value).__name__,
        "serialized_bytes": compact_size(value),
        "percentage_of_compact_bundle": pct(compact_size(value), total_bytes),
        "record_count": record_count(name, value),
        "average_record_bytes": round(sum(item_bytes) / len(item_bytes), 3) if item_bytes else None,
        "largest_records": largest_records(name, value),
    }
    if notes:
        result["notes"] = notes
    return result


def nested_story_metrics(bundle: dict[str, Any], total_bytes: int) -> list[dict[str, Any]]:
    metrics: list[dict[str, Any]] = []

    def value_at_path(story: dict[str, Any], path: str) -> Any:
        current: Any = story
        for part in path.split("."):
            if part == "stories[]":
                continue
            if isinstance(current, dict):
                current = current.get(part)
            else:
                return None
        return current

    def add(path: str, values: Iterable[Any], notes: str | None = None) -> None:
        materialized = list(values)
        sizes = [compact_size(value) for value in materialized]
        total = sum(sizes)
        largest = sorted(
            [
                {"record_id": story["id"], "bytes": compact_size(value_at_path(story, path))}
                for story in bundle["stories"]
            ],
            key=lambda row: (-row["bytes"], row["record_id"]),
        )[:10]
        row: dict[str, Any] = {
            "path": path,
            "serialized_bytes_across_stories": total,
            "percentage_of_compact_bundle": pct(total, total_bytes),
            "story_count": len(materialized),
            "average_story_bytes": round(total / len(materialized), 3) if materialized else 0,
            "largest_story_records": largest,
        }
        if notes:
            row["notes"] = notes
        metrics.append(row)

    add("stories[].text", (story.get("text") for story in bundle["stories"]))
    add("stories[].annotations", (story.get("annotations") for story in bundle["stories"]))
    add("stories[].reading", (story.get("reading") for story in bundle["stories"]))
    for key in [
        "entry_id",
        "status",
        "punctuation_record_id",
        "base_canonical_entry_sha256",
        "conversion",
        "main_text",
        "annotations",
        "mention_projection",
        "labels",
        "person_display",
        "mention_display",
        "source_display",
        "relation_display",
        "evidence_display",
        "display_overrides",
    ]:
        notes = None
        if key == "evidence_display":
            notes = "Currently a complete global evidence display map is repeated inside every Story reading."
        elif key in {"labels", "person_display", "source_display", "relation_display"}:
            notes = "Measured as a per-Story projection; identical copies are reported separately in duplication_findings."
        add(f"stories[].reading.{key}", (story.get("reading", {}).get(key) for story in bundle["stories"]), notes)
    for key in ["original", "simplified", "segments"]:
        add(
            f"stories[].reading.main_text.{key}",
            (story.get("reading", {}).get("main_text", {}).get(key) for story in bundle["stories"]),
            "Reader-facing punctuation/conversion projection; canonical source text remains separate.",
        )
    return metrics


def nested_collection_metrics(bundle: dict[str, Any], total_bytes: int) -> list[dict[str, Any]]:
    metrics: list[dict[str, Any]] = []

    def add(path: str, values: Iterable[Any], notes: str | None = None) -> None:
        materialized = list(values)
        total = sum(compact_size(value) for value in materialized)
        row: dict[str, Any] = {
            "path": path,
            "serialized_bytes_across_records": total,
            "percentage_of_compact_bundle": pct(total, total_bytes),
            "record_count": len(materialized),
            "average_record_bytes": round(total / len(materialized), 3) if materialized else 0,
        }
        if notes:
            row["notes"] = notes
        metrics.append(row)

    evidence = bundle["evidence"]
    for key in ["quote", "locator", "assertion_status", "review_status", "notes"]:
        add(f"evidence[].{key}", (item.get(key) for item in evidence))
    add(
        "evidence[].locator.source_provenance",
        (item.get("locator", {}).get("source_provenance") for item in evidence),
        "Repeated source/witness metadata; some repetition is intentional provenance, but it is a candidate shared table in D1.1.",
    )
    for key in ["artifact_path", "artifact_sha256", "entry_id", "unit_id"]:
        add(f"evidence[].locator.{key}", (item.get("locator", {}).get(key) for item in evidence))

    sketches = list(bundle["person_sketches"].values())
    for key in ["identity", "profile_evidence_ids", "aliases", "story_counts", "life_glimpse"]:
        add(f"person_sketches[].{key}", (item.get(key) for item in sketches))

    scenes = list(bundle["scene_contexts"].values())
    for key in [
        "evidence_ids",
        "date",
        "places",
        "people_at_scene",
        "unmaterialized_people",
        "positional_context",
        "event_background",
        "narrative_layers",
        "notes",
    ]:
        add(f"scene_contexts[].{key}", (item.get(key) for item in scenes))
    return metrics


def duplicate_map_stats(values: list[Any]) -> dict[str, Any]:
    hashes = Counter(compact_bytes(value) for value in values)
    total = sum(len(encoded) for encoded in hashes for _ in range(hashes[encoded]))
    unique = sum(len(encoded) for encoded in hashes)
    return {
        "record_count": len(values),
        "unique_serializations": len(hashes),
        "serialized_bytes": total,
        "unique_serialized_bytes": unique,
        "repeat_serialized_bytes_upper_bound": total - unique,
        "largest_duplicate_groups": [
            {"copies": count, "bytes_per_copy": len(encoded)}
            for encoded, count in sorted(
                ((encoded, count) for encoded, count in hashes.items() if count > 1),
                key=lambda pair: (-pair[1] * len(pair[0]), -pair[1], len(pair[0])),
            )[:10]
        ],
    }


def evidence_display_duplication(bundle: dict[str, Any]) -> dict[str, Any]:
    entries: list[tuple[str, str, Any]] = []
    by_evidence: defaultdict[str, list[Any]] = defaultdict(list)
    for story in bundle["stories"]:
        display = story.get("reading", {}).get("evidence_display", {})
        if not isinstance(display, dict):
            continue
        for evidence_id, value in display.items():
            entries.append((story["id"], str(evidence_id), value))
            by_evidence[str(evidence_id)].append(value)
    unique_map = {evidence_id: values[0] for evidence_id, values in sorted(by_evidence.items())}
    occurrence_bytes = sum(compact_size(value) for _, _, value in entries)
    unique_value_bytes = sum(compact_size(value) for value in unique_map.values())
    return {
        "path": "stories[].reading.evidence_display",
        "story_count": len(bundle["stories"]),
        "entry_occurrences": len(entries),
        "unique_evidence_ids": len(by_evidence),
        "serialized_bytes_in_current_bundle": sum(
            compact_size(story.get("reading", {}).get("evidence_display", {}))
            for story in bundle["stories"]
        ),
        "value_bytes_across_occurrences": occurrence_bytes,
        "value_bytes_for_one_shared_value_per_evidence_id": unique_value_bytes,
        "repeat_value_bytes_upper_bound": occurrence_bytes - unique_value_bytes,
        "shared_map_serialized_bytes_estimate": compact_size(unique_map),
        "interpretation": "The current builder passes the complete global Evidence list to each reading projection. This is display duplication, not independent source evidence.",
    }


def source_provenance_duplication(bundle: dict[str, Any]) -> dict[str, Any]:
    values = [item.get("locator", {}).get("source_provenance") for item in bundle["evidence"]]
    stats = duplicate_map_stats(values)
    stats.update(
        {
            "path": "evidence[].locator.source_provenance",
            "source_record_count": len(values),
            "interpretation": "Witness/source identity is meaningful provenance; repeated source metadata could be normalized behind an Evidence-side reference without deleting provenance.",
        }
    )
    return stats


def runtime_necessity() -> dict[str, Any]:
    """Static usage classification based on the current reader and parser."""

    top_level = {
        "schema": ("startup_required", "parseSiteBundle schema guard; no reader rendering.", "parser_contract"),
        "generated_from": ("build_only", "Build provenance; not read by the reader.", "none"),
        "stories": ("startup_required", "Initial Story, random Story, Story→Person and navigation indexes use the full published list.", "whole_bundle"),
        "people": ("startup_required", "Person lookup, Person panel, random Person, and relation traversal use the registry.", "whole_bundle"),
        "mentions": ("story_required", "Story inline resolution and Person route context use mentions.", "field_subset"),
        "relations": ("relation_required", "Relation rows, ego map, and relation-context navigation use reviewed Relations.", "field_subset"),
        "eras": ("validation_only", "Required by parseSiteBundle shape checks; current reader does not directly read data.eras.", "parser_contract"),
        "evidence": ("evidence_on_demand", "Collapsed Story/Person/Relation/Scene evidence panels read it after navigation; currently parsed at startup.", "field_subset"),
        "sources": ("validation_only", "Current reader uses reading.source_display; it does not directly read data.sources.", "parser_contract"),
        "ruler_identities": ("validation_only", "Validated for ruler Mention integrity; current reader uses projected era-card data.", "parser_contract"),
        "era_cards": ("era_required", "Story orientation, Era panel, and Story↔Era navigation use Era Cards.", "field_subset"),
        "ruler_mentions": ("validation_only", "Validated against projected ruler segments; current reader does not directly query the registry.", "parser_contract"),
        "historical_events": ("era_required", "Era/event panels resolve event IDs through this array.", "field_subset"),
        "story_era_orientations": ("validation_only", "Story-local era_orientation is rendered; this parallel list is currently parser-validated only.", "parser_contract"),
        "person_sketches": ("person_required", "Person panel and Person Explorer read sketches for the focused Person.", "field_subset"),
        "scene_contexts": ("story_required", "Scene card is Story-local and only rendered when a record exists; it is currently loaded globally.", "field_subset"),
        "story_chain": ("person_required", "Person→Story lists use the projected chain index; it can be deferred until Person navigation.", "field_subset"),
        "ui": ("startup_required", "Small reader labels and scene labels are used throughout the current UI.", "field_subset"),
    }
    nested = [
        ("stories[].reading.main_text", "story_required", "Primary reader prose and inline segment interaction."),
        ("stories[].reading.annotations", "story_required", "Story annotation panel and annotation evidence links."),
        ("stories[].reading.person_display", "story_required", "Story-local display names for resolved Persons; currently repeats the global Person display map."),
        ("stories[].reading.mention_display", "story_required", "Inline Mention labels/explanations and Person route context."),
        ("stories[].reading.source_display", "evidence_on_demand", "Source work/edition labels in evidence panels; only needed with evidence display."),
        ("stories[].reading.relation_display", "relation_required", "Relation labels/scopes; only needed with relation panels."),
        ("stories[].reading.evidence_display", "evidence_on_demand", "Evidence reading pairs are used when evidence is opened; current builder repeats the complete global map per Story."),
        ("stories[].reading.labels", "startup_required", "Reader labels; identical copies could be a shared UI table."),
        ("stories[].reading.mention_projection", "validation_only", "Projection integrity is checked by the parser; current components consume already projected segments."),
        ("stories[].text", "validation_only", "Canonical source-line text is retained for validation/provenance; current reader renders reading.main_text."),
        ("stories[].annotations", "validation_only", "Source annotation records support build/validation; reader renders reading.annotations instead."),
        ("stories[].evidence_ids", "story_required", "Cross-reference IDs select evidence on Story panels."),
        ("stories[].source_ids", "validation_only", "Current reader resolves source display through reading.source_display, not this raw ID list."),
        ("stories[].time", "era_required", "Available in the Story contract; current reader mostly uses projected Era orientation."),
        ("stories[].era_orientation", "era_required", "Story-local primary Era orientation is rendered and navigated."),
        ("stories[].reading.main_text.original/simplified", "story_required", "Two reader modes; not redundant with physical-line canonical text."),
    ]
    return {
        "method": "static inspection of site/src/App.tsx, site/src/relationExplorer.ts, site/src/data.ts, and site/src/types.ts",
        "current_loading_behavior": "All fields enter the browser in one statically imported JSON module and are parsed by loadSiteBundle at application startup.",
        "top_level": {
            key: {
                "classification": value[0],
                "current_frontend_use": value[1],
                "semantic_dependency": value[2],
            }
            for key, value in top_level.items()
        },
        "nested": [
            {"path": path, "classification": classification, "current_frontend_use": use}
            for path, classification, use in nested
        ],
        "unused_or_parser_only_fields": [
            "generated_from",
            "eras",
            "sources",
            "ruler_identities",
            "ruler_mentions",
            "story_era_orientations",
            "stories[].text",
            "stories[].annotations",
            "stories[].source_ids",
            "stories[].reading.mention_projection",
        ],
    }


def protection_manifest(root: Path = ROOT) -> list[dict[str, Any]]:
    paths = set(PROTECTED_PATHS)
    for pattern in (
        "data/derived/h0c-*.json",
        "data/derived/hg0-*.json",
        "data/derived/ml0-*.json",
        "data/derived/x1-2a-*.json",
        "data/derived/x1-2p-*.json",
    ):
        paths.update(path.relative_to(root).as_posix() for path in sorted(root.glob(pattern)))
    rows: list[dict[str, Any]] = []
    for relative in sorted(paths):
        path = root / relative
        rows.append(
            {
                "path": relative,
                "exists": path.is_file(),
                "bytes": path.stat().st_size if path.is_file() else None,
                "sha256": sha256_file(path) if path.is_file() else None,
            }
        )
    return rows


def classify_dependency(relative: str, terms: list[str]) -> dict[str, Any]:
    path = Path(relative)
    if relative.startswith("site/src/"):
        category = "frontend runtime"
        if path.name == "data.ts":
            semantic = "whole_bundle"
            risk = "high"
            notes = "Static JSON import, runtime shape validation, and returned SiteBundle API."
        elif path.name == "App.tsx":
            semantic = "whole_bundle"
            risk = "high"
            notes = "Application receives the monolithic SiteBundle and routes across Story/Person/Relation/Era fields."
        elif path.name == "relationExplorer.ts":
            semantic = "field_subset"
            risk = "high"
            notes = "Typed SiteBundle consumer; sharding would require a data-access boundary or adapter."
        else:
            semantic = "schema_contract"
            risk = "medium"
            notes = "Type contract; changes only if the SiteBundle interface is split."
    elif relative.startswith("tests/"):
        category = "test"
        semantic = "whole_bundle" if "sc1_1_frontend_contract" in relative else "field_subset"
        risk = "medium" if semantic == "whole_bundle" else "low"
        notes = "Regression fixture currently reads the monolith; future shard tests should preserve an equivalent aggregate fixture."
    elif relative.startswith("docs/"):
        category = "documentation"
        semantic = "documentation_only"
        risk = "low"
        notes = "Contract or historical documentation; no runtime load."
    elif relative.startswith("scripts/"):
        if path.name.startswith("build_"):
            category = "builder"
            risk = "high" if path.name == "build_sc1_frontend_data.py" else "medium"
            semantic = "whole_bundle" if path.name == "build_sc1_frontend_data.py" else "field_subset"
            notes = "Build/research input; migration requires a compatibility projection or shard reader."
        elif path.name.startswith("validate_"):
            category = "validator"
            semantic = "whole_bundle"
            risk = "medium"
            notes = "Validation currently parses the complete derived bundle even when assertions are field-specific."
        elif path.name.startswith("migrate_"):
            category = "other"
            semantic = "whole_bundle"
            risk = "high"
            notes = "Migration script writes both generated views; must be audited before any shard transition."
        else:
            category = "research/audit script"
            semantic = "field_subset"
            risk = "medium"
            notes = "Research artifact or metrics consumer; update only if its selected fields move behind an adapter."
    elif relative.startswith("data/"):
        category = "research/audit script"
        semantic = "metadata_reference"
        risk = "low"
        notes = "Derived/annotation metadata records the monolith as an upstream artifact; it does not load it at runtime."
    else:
        category = "other"
        semantic = "uncertain"
        risk = "medium"
        notes = "Needs explicit review during D1.1 migration."
    literal = [term for term in terms if term in {DEPENDENCY_TERMS[0], DEPENDENCY_TERMS[1]}]
    return {
        "path": relative,
        "category": category,
        "dependency_terms": sorted(terms),
        "literal_bundle_path_terms": sorted(literal),
        "semantic_dependency": semantic,
        "physical_dependency": "whole_file" if literal else "none",
        "migration_risk": risk,
        "notes": notes,
    }


def scan_dependencies(root: Path = ROOT) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        relative = path.relative_to(root).as_posix()
        if relative in EXCLUDED_SCAN_FILES or any(part in EXCLUDED_SCAN_PARTS for part in path.relative_to(root).parts):
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        terms = [term for term in DEPENDENCY_TERMS if term in text]
        if terms:
            rows.append(classify_dependency(relative, terms))
    rows.sort(key=lambda row: row["path"])
    counts = Counter(row["category"] for row in rows)
    semantic_counts = Counter(row["semantic_dependency"] for row in rows)
    literal_paths = [row["path"] for row in rows if row["literal_bundle_path_terms"]]
    api_paths = [
        row["path"]
        for row in rows
        if any(term in row["dependency_terms"] for term in DEPENDENCY_TERMS[2:])
    ]
    return {
        "schema": 1,
        "scope": "repository text consumers excluding the two SC1 bundle payloads, build output, dependencies, and D1.0 self-artifacts",
        "terms": DEPENDENCY_TERMS,
        "consumer_count": len(rows),
        "direct_literal_bundle_consumer_count": len(literal_paths),
        "site_bundle_api_consumer_count": len(api_paths),
        "category_counts": dict(sorted(counts.items())),
        "semantic_dependency_counts": dict(sorted(semantic_counts.items())),
        "duplicate_path_count": len(rows) - len({row["path"] for row in rows}),
        "consumers": rows,
    }


def build_bundle_audit(root: Path = ROOT) -> dict[str, Any]:
    derived_path = root / "data/derived/sc1-site.json"
    generated_path = root / "site/src/generated/sc1-site.json"
    raw = derived_path.read_bytes()
    generated = generated_path.read_bytes()
    bundle = json.loads(raw.decode("utf-8"))
    compact_total = compact_size(bundle)
    top_fields = [
        field_metric(
            key,
            bundle.get(key),
            compact_total,
            notes=("Required top-level key; value is intentionally kept for the current SiteBundle contract."),
        )
        for key in REQUIRED_TOP_LEVEL_FIELDS
        if key in bundle
    ]
    field_bytes_sum = sum(item["serialized_bytes"] for item in top_fields)
    story_metrics = nested_story_metrics(bundle, compact_total)
    collection_metrics = nested_collection_metrics(bundle, compact_total)
    story_reading_map_fields = ["labels", "person_display", "source_display", "relation_display"]
    duplication_findings = {
        "generated_views": {
            "paths": [
                "data/derived/sc1-site.json",
                "site/src/generated/sc1-site.json",
            ],
            "byte_identical": raw == generated,
            "sha256": sha256_bytes(raw),
            "bytes_per_copy": len(raw),
            "working_tree_duplicate_bytes": len(raw) if raw == generated else 0,
            "interpretation": "One research-side archive and one Vite input are kept as exact generated views. Git can deduplicate identical blob content, but checkout/deployment/runtime still carry both copies before bundling.",
        },
        "story_reading_evidence_display": evidence_display_duplication(bundle),
        "story_common_reading_maps": {
            field: duplicate_map_stats([story["reading"].get(field) for story in bundle["stories"]])
            for field in story_reading_map_fields
        },
        "evidence_source_provenance": source_provenance_duplication(bundle),
        "intentional_or_semantic_repetition": [
            {
                "path": "stories[].reading.main_text.original/simplified",
                "reason": "The reader needs an evidence-backed punctuation/conversion projection. It is not interchangeable with physical-line canonical Story.text or source Evidence.",
            },
            {
                "path": "stories[].reading.main_text.segments",
                "reason": "Inline Mention/ruler/annotation-marker interaction is a Story-local projection; it preserves display spans and target IDs.",
            },
            {
                "path": "stories[].evidence_ids / person_ids / mention_ids / relation_ids",
                "reason": "These are cross-reference IDs, not copies of the referenced payloads; they are comparatively small and preserve local traversal.",
            },
            {
                "path": "evidence[].locator.source_provenance",
                "reason": "Repeated provenance is semantically meaningful, although stable source records could be referenced indirectly in a later runtime representation.",
            },
        ],
    }
    dedup_candidates = []
    for field, stats in duplication_findings["story_common_reading_maps"].items():
        dedup_candidates.append(
            {
                "path": f"stories[].reading.{field}",
                "current_serialized_bytes": stats["serialized_bytes"],
                "one_shared_copy_bytes": stats["unique_serialized_bytes"],
                "repeat_bytes_upper_bound": stats["repeat_serialized_bytes_upper_bound"],
            }
        )
    evidence_stats = duplication_findings["story_reading_evidence_display"]
    dedup_candidates.append(
        {
            "path": "stories[].reading.evidence_display",
            "current_serialized_bytes": evidence_stats["serialized_bytes_in_current_bundle"],
            "one_shared_copy_bytes": evidence_stats["shared_map_serialized_bytes_estimate"],
            "repeat_bytes_upper_bound": evidence_stats["serialized_bytes_in_current_bundle"] - evidence_stats["shared_map_serialized_bytes_estimate"],
        }
    )
    dedup_upper_bound = sum(item["repeat_bytes_upper_bound"] for item in dedup_candidates)
    contributor_candidates = [
        {
            "path": item["path"],
            "serialized_bytes": item["serialized_bytes"],
            "percentage_of_compact_bundle": item["percentage_of_compact_bundle"],
        }
        for item in top_fields
        if item["path"] != "stories"
    ]
    contributor_candidates.extend(
        {
            "path": item["path"],
            "serialized_bytes": item["serialized_bytes_across_stories"],
            "percentage_of_compact_bundle": item["percentage_of_compact_bundle"],
        }
        for item in story_metrics
        if item["path"] != "stories[].reading"
    )
    contributor_candidates.extend(
        {
            "path": item["path"],
            "serialized_bytes": item["serialized_bytes_across_records"],
            "percentage_of_compact_bundle": item["percentage_of_compact_bundle"],
        }
        for item in collection_metrics
    )
    largest_contributors = sorted(
        contributor_candidates,
        key=lambda row: (-row["serialized_bytes"], row["path"]),
    )[:10]
    return {
        "schema": 1,
        "audit": "D1.0",
        "baseline": {
            "git_head": "7b1c4ab361a8db097607b5fc9f0931302a529345",
            "branch": "main",
            "frozen_state": "X1.2P",
        },
        "inputs": {
            "derived_path": str(derived_path.relative_to(root)),
            "generated_path": str(generated_path.relative_to(root)),
            "derived_sha256": sha256_bytes(raw),
            "generated_sha256": sha256_bytes(generated),
            "byte_identical": raw == generated,
            "required_top_level_fields": REQUIRED_TOP_LEVEL_FIELDS,
        },
        "bundle_size": {
            "raw_file_bytes": len(raw),
            "raw_file_mib": round(len(raw) / (1024 * 1024), 6),
            "compact_serialized_bytes": compact_total,
            "compact_serialized_mib": round(compact_total / (1024 * 1024), 6),
            "formatted_payload_bytes_without_trailing_newline": max(0, len(raw) - 1),
            "top_level_field_serialized_bytes": field_bytes_sum,
            "top_level_syntax_overhead_bytes": compact_total - field_bytes_sum,
            "top_level_field_percentages_sum": round(sum(item["percentage_of_compact_bundle"] for item in top_fields), 6),
        },
        "top_level_fields": top_fields,
        "nested_metrics": {
            "story_and_reading": story_metrics,
            "evidence_person_sketch_scene": collection_metrics,
        },
        "largest_contributors": largest_contributors,
        "duplication_findings": {
            **duplication_findings,
            "runtime_projection_dedup_upper_bound": {
                "components": dedup_candidates,
                "repeat_bytes_upper_bound": dedup_upper_bound,
                "percentage_of_compact_bundle": pct(dedup_upper_bound, compact_total),
                "interpretation": "Upper bound if repeated display maps become shared/indexed runtime data. It is not a D1.0 deletion estimate and does not remove canonical source/evidence data.",
            },
        },
        "runtime_necessity": runtime_necessity(),
        "git_and_runtime_observations": {
            "github_large_file_warning_threshold_bytes": 50 * 1024 * 1024,
            "github_large_file_hard_limit_bytes": 100 * 1024 * 1024,
            "warning_threshold_crossed": len(raw) > 50 * 1024 * 1024,
            "hard_limit_crossed": len(raw) > 100 * 1024 * 1024,
            "vite_static_import": True,
            "vite_import_path": "site/src/data.ts -> site/src/generated/sc1-site.json",
            "dist_javascript_bytes": sum(path.stat().st_size for path in sorted((root / "dist/assets").glob("*.js"))) if (root / "dist/assets").is_dir() else None,
            "dist_javascript_files": [
                {"path": str(path.relative_to(root)), "bytes": path.stat().st_size}
                for path in sorted((root / "dist/assets").glob("*.js"))
            ] if (root / "dist/assets").is_dir() else [],
            "initial_parse_behavior": "The JSON module is included in the initial Vite JavaScript asset; loadSiteBundle then calls parseSiteBundle on the complete imported object. No runtime JSON fetch or lazy shard boundary exists.",
            "git_note": "The two identical files point to one identical Git blob when Git object deduplication applies, but each generated update creates a large changed artifact/diff surface and both copies remain in checkout/deployment inputs.",
        },
        "protection_manifest": protection_manifest(root),
    }


def write_json(path: Path, value: Any) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
