"""Read-only inputs and deterministic helpers for SFH2.2-F-prep.

F-prep intentionally has no provider or mutation imports.  It inventories the
current semantic input universe and the already-qualified pilot contracts,
then writes only compact planning artifacts under its own namespace.
"""

from __future__ import annotations

import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable, Mapping


ROOT = Path(__file__).resolve().parents[2]
BASELINE_COMMIT = "879ee3aa97df13c2742f6d56654928f92ceda9d5"
OUT = ROOT / "data/generated/sfh2-f-prep"
FROZEN_OUT = ROOT / "data/frozen/sfh2/semantic-v1"

SFH1_STORY_PACKETS = ROOT / "data/generated/sfh1/story-packets.json"
SFH1_MENTIONS = ROOT / "data/generated/sfh1/validated-mentions.json"
SFH1_SEMANTICS = ROOT / "data/generated/sfh1/reference-semantics.json"
SFH1_FINAL = ROOT / "data/generated/sfh1/final-decisions.json"
SFH1_IDENTITIES = ROOT / "data/generated/sfh1/identity-judgments.json"
SFH1_CANDIDATES = ROOT / "data/generated/sfh1/candidate-sets.json"
UX2_STORY_INDEX = ROOT / "data/derived/ux2-story-index.json"

A2OR_ROOT = ROOT / "data/generated/sfh2-a2or"
A2OVB_ROOT = ROOT / "data/generated/sfh2-a2ovb"
IDENTITY_MANIFEST = ROOT / "data/frozen/sfh2/identity-v1/manifest.json"
GOLD = ROOT / "data/annotation/sfh2-a2o-evaluation-gold.json"
SC1_FROZEN = ROOT / "data/derived/sc1-site.json"
SC1_CURRENT = ROOT / "data/derived/sc1-current-site.json"
PEOPLE = ROOT / "data/people.json"
ALIASES = ROOT / "data/aliases.json"

NARRATIVE_FUNCTIONS = (
    "participant", "reference", "speaker", "addressee", "collective_reference",
    "person_attribute", "citation_source", "historical_exemplum",
    "genealogy_reference", "structural", "other", "uncertain",
)

IDENTITY_REQUIRED_FINAL_STATES = {
    "stable_entity_resolved", "local_candidate_resolved", "review_required",
    "genuinely_unresolved",
}


def text(value: Any) -> str:
    return str(value or "").strip()


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def stable_hash(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def text_hash(value: Any) -> str:
    return hashlib.sha256(text(value).encode("utf-8")).hexdigest()


def read_json(path: Path, default: Any = None) -> Any:
    if not path.is_file():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def rows(document: Any, *keys: str) -> list[dict[str, Any]]:
    if isinstance(document, list):
        return [dict(row) for row in document if isinstance(row, Mapping)]
    if not isinstance(document, Mapping):
        return []
    for key in keys or ("records",):
        value = document.get(key)
        if isinstance(value, list):
            return [dict(row) for row in value if isinstance(row, Mapping)]
    return []


def input_hashes() -> dict[str, str]:
    paths = [
        SFH1_STORY_PACKETS, SFH1_MENTIONS, SFH1_SEMANTICS, SFH1_FINAL,
        SFH1_IDENTITIES, SFH1_CANDIDATES, UX2_STORY_INDEX,
        PEOPLE, ALIASES, IDENTITY_MANIFEST, GOLD,
    ]
    return {
        str(path.relative_to(ROOT)): file_hash(path)
        for path in paths if path.is_file()
    }


def tree_digest(relative_path: str) -> dict[str, Any]:
    """Return a compact, content-addressed digest of a repository subtree."""

    base = ROOT / relative_path
    if not base.exists():
        return {"path": relative_path, "exists": False, "file_count": 0, "total_bytes": 0, "tree_sha256": None}
    files: list[dict[str, Any]] = []
    if base.is_file():
        paths = [base]
    else:
        paths = [path for path in base.rglob("*") if path.is_file()]
    for path in sorted(paths):
        files.append({
            "path": str(path.relative_to(ROOT)).replace("\\", "/"),
            "sha256": file_hash(path),
            "size_bytes": path.stat().st_size,
        })
    return {
        "path": relative_path,
        "exists": True,
        "file_count": len(files),
        "total_bytes": sum(row["size_bytes"] for row in files),
        "tree_sha256": stable_hash(files),
    }


def protected_hashes() -> dict[str, Any]:
    """Capture preflight witnesses without copying protected payloads."""

    exact_paths = [
        GOLD, IDENTITY_MANIFEST, SC1_FROZEN, SC1_CURRENT, PEOPLE, ALIASES,
        ROOT / "data/derived/person-resolution-effective.json",
        ROOT / "data/derived/h0c-historical-facts.json",
    ]
    trees = [
        "data/generated/sfh2-a2",
        "data/generated/sfh2-a2r",
        "data/generated/sfh2-a2g",
        "data/generated/sfh2-a2gr",
        "data/generated/sfh2-a2o",
        "data/generated/sfh2-a2ot",
        "data/generated/sfh2-a2or",
        "data/generated/sfh2-a2os",
        "data/generated/sfh2-a2osp",
        "data/generated/sfh2-a2ov",
        "data/generated/sfh2-a2ovb",
    ]
    return {
        "files": {
            str(path.relative_to(ROOT)): {
                "sha256": file_hash(path),
                "size_bytes": path.stat().st_size,
            }
            for path in exact_paths if path.is_file()
        },
        "trees": {path: tree_digest(path) for path in trees},
    }


def load_authority() -> dict[str, Any]:
    """Load the authoritative SFH1 semantic universe and current scope index."""

    packets_doc = read_json(SFH1_STORY_PACKETS, {}) or {}
    mentions_doc = read_json(SFH1_MENTIONS, {}) or {}
    semantics_doc = read_json(SFH1_SEMANTICS, {}) or {}
    final_doc = read_json(SFH1_FINAL, {}) or {}
    identities_doc = read_json(SFH1_IDENTITIES, {}) or {}
    candidates_doc = read_json(SFH1_CANDIDATES, {}) or {}
    ux2_doc = read_json(UX2_STORY_INDEX, {}) or {}
    packets = rows(packets_doc, "packets")
    mentions = rows(mentions_doc, "records")
    semantics = rows(semantics_doc, "records")
    final = rows(final_doc, "records")
    identities = rows(identities_doc, "records")
    candidates = rows(candidates_doc, "records")
    ux2 = rows(ux2_doc, "records")
    return {
        "story_packets_document": packets_doc,
        "mentions_document": mentions_doc,
        "semantics_document": semantics_doc,
        "final_document": final_doc,
        "identities_document": identities_doc,
        "candidates_document": candidates_doc,
        "ux2_document": ux2_doc,
        "packets": packets,
        "mentions": mentions,
        "semantics": semantics,
        "final": final,
        "identities": identities,
        "candidates": candidates,
        "ux2": ux2,
    }


def exact_occurrence_key(mention: Mapping[str, Any]) -> dict[str, Any]:
    mention_id = text(mention.get("mention_id"))
    return {
        "occurrence_id": mention_id,
        "case_id": mention_id,
        "mention_id": mention_id,
        "story_id": text(mention.get("story_id")),
        "source_evidence_id": text(mention.get("source_evidence_id")),
        "source_start": mention.get("source_start"),
        "source_end": mention.get("source_end"),
        "surface": text(mention.get("surface")),
    }


def key_tuple(key: Mapping[str, Any]) -> tuple[Any, ...]:
    return tuple(key.get(name) for name in (
        "occurrence_id", "mention_id", "story_id", "source_evidence_id",
        "source_start", "source_end", "surface",
    ))


def occurrence_key_hash(key: Mapping[str, Any]) -> str:
    return stable_hash(dict(key))


def _source_indexes(authority: Mapping[str, Any]) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    packets = {
        text(row.get("story_id")): row
        for row in authority["packets"] if text(row.get("story_id"))
    }
    evidence: dict[str, dict[str, Any]] = {}
    duplicate_evidence: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for packet in authority["packets"]:
        for item in packet.get("evidence", []) or []:
            if not isinstance(item, Mapping):
                continue
            evidence_id = text(item.get("evidence_id"))
            if not evidence_id:
                continue
            duplicate_evidence[evidence_id].append(dict(item))
    for evidence_id, values in duplicate_evidence.items():
        evidence[evidence_id] = values[0]
    mentions = {
        text(row.get("mention_id")): row
        for row in authority["mentions"] if text(row.get("mention_id"))
    }
    return packets, evidence, mentions


def build_occurrence_inventory(authority: Mapping[str, Any]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    packets, evidence, _ = _source_indexes(authority)
    semantic_index = {text(row.get("mention_id")): row for row in authority["semantics"]}
    final_index = {text(row.get("mention_id")): row for row in authority["final"]}
    evidence_id_counts = Counter(
        text(item.get("evidence_id"))
        for packet in authority["packets"]
        for item in (packet.get("evidence", []) or [])
        if isinstance(item, Mapping) and text(item.get("evidence_id"))
    )
    records: list[dict[str, Any]] = []
    invalid_offsets: list[dict[str, Any]] = []
    missing_evidence: list[str] = []
    dangling_stories: list[str] = []
    text_mismatches: list[dict[str, Any]] = []
    exact_groups: dict[tuple[Any, ...], list[str]] = defaultdict(list)
    repeated_groups: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    by_evidence: dict[str, list[dict[str, Any]]] = defaultdict(list)

    for mention in sorted(authority["mentions"], key=lambda row: (
        text(row.get("story_id")), text(row.get("source_evidence_id")),
        row.get("source_start") if isinstance(row.get("source_start"), int) else -1,
        row.get("source_end") if isinstance(row.get("source_end"), int) else -1,
        text(row.get("mention_id")),
    )):
        key = exact_occurrence_key(mention)
        occurrence_id = key["occurrence_id"]
        story_id = key["story_id"]
        evidence_id = key["source_evidence_id"]
        source = evidence.get(evidence_id)
        errors: list[str] = []
        if story_id not in packets:
            errors.append("story_not_in_authoritative_packets")
            dangling_stories.append(story_id)
        if source is None:
            errors.append("source_evidence_missing")
            missing_evidence.append(occurrence_id)
        source_text = text(source.get("text")) if source else ""
        start, end = mention.get("source_start"), mention.get("source_end")
        exact_span = None
        if not isinstance(start, int) or not isinstance(end, int):
            errors.append("offsets_not_integer")
        elif not (0 <= start < end <= len(source_text)):
            errors.append("offset_range_invalid")
        else:
            exact_span = source_text[start:end]
            if exact_span != key["surface"]:
                errors.append("target_text_mismatch")
                text_mismatches.append({"occurrence_id": occurrence_id, "expected": key["surface"], "actual": exact_span})
        if errors:
            invalid_offsets.append({"occurrence_id": occurrence_id, "errors": sorted(set(errors))})
        exact_groups[key_tuple(key)].append(occurrence_id)
        repeated_groups[(story_id, key["surface"])].append({
            "occurrence_id": occurrence_id,
            "mention_id": key["mention_id"],
            "source_evidence_id": evidence_id,
            "source_start": start,
            "source_end": end,
        })
        by_evidence[evidence_id].append({**key, "source_layer": text(source.get("source_layer")) if source else None})
        records.append({
            "occurrence_id": occurrence_id,
            "exact_occurrence_key": key,
            "exact_occurrence_key_hash": occurrence_key_hash(key),
            "source": {
                "source_evidence_id": evidence_id,
                "source_layer": text(source.get("source_layer")) if source else None,
                "source_ref": source.get("source_ref") if source else None,
                "source_text_sha256": text_hash(source_text) if source else None,
                "source_text_length": len(source_text) if source else None,
                "exact_span": exact_span,
                "target_text_matches": not errors and exact_span == key["surface"],
            },
            "mention_metadata": {
                "entity_kind": mention.get("entity_kind"),
                "reference_form": mention.get("reference_form"),
                "confidence": mention.get("confidence"),
            },
            "existing_semantic_state": {
                "semantic_type": semantic_index.get(occurrence_id, {}).get("semantic_type"),
                "semantic_record_present": occurrence_id in semantic_index,
                "final_state": final_index.get(occurrence_id, {}).get("final_state"),
                "final_record_present": occurrence_id in final_index,
            },
            "validation_status": "valid" if not errors else "blocked",
            "validation_errors": sorted(set(errors)),
            "candidate_only": True,
            "canonical_write_back": False,
        })

    duplicate_exact = [
        {"key": list(group), "occurrence_ids": sorted(ids)}
        for group, ids in sorted(exact_groups.items(), key=lambda item: repr(item[0]))
        if len(ids) > 1
    ]
    repeated_surface = [
        {
            "story_id": story_id,
            "surface": surface,
            "occurrence_count": len(items),
            "occurrences": sorted(items, key=lambda item: (item["source_evidence_id"], item["source_start"] or -1, item["occurrence_id"])),
        }
        for (story_id, surface), items in sorted(repeated_groups.items())
        if len(items) > 1
    ]
    overlaps: list[dict[str, Any]] = []
    nested: list[dict[str, Any]] = []
    for evidence_id, items in sorted(by_evidence.items()):
        ordered = sorted(items, key=lambda item: (item["source_start"] if isinstance(item["source_start"], int) else -1, -(item["source_end"] or 0), item["occurrence_id"]))
        for index, left in enumerate(ordered):
            if not isinstance(left["source_start"], int) or not isinstance(left["source_end"], int):
                continue
            for right in ordered[index + 1:]:
                if not isinstance(right["source_start"], int) or not isinstance(right["source_end"], int):
                    continue
                if right["source_start"] >= left["source_end"]:
                    break
                if max(left["source_start"], right["source_start"]) < min(left["source_end"], right["source_end"]):
                    pair = {
                        "source_evidence_id": evidence_id,
                        "left_occurrence_id": left["occurrence_id"],
                        "right_occurrence_id": right["occurrence_id"],
                        "left_span": [left["source_start"], left["source_end"]],
                        "right_span": [right["source_start"], right["source_end"]],
                        "left_surface": left["surface"],
                        "right_surface": right["surface"],
                    }
                    overlaps.append(pair)
                    if (left["source_start"] <= right["source_start"] and left["source_end"] >= right["source_end"]) or (right["source_start"] <= left["source_start"] and right["source_end"] >= left["source_end"]):
                        nested.append(pair)

    story_occurrence_counts = Counter(row["exact_occurrence_key"]["story_id"] for row in records)
    layer_counts = Counter(row["source"]["source_layer"] for row in records)
    entity_counts = Counter(row["mention_metadata"]["entity_kind"] for row in records)
    form_counts = Counter(row["mention_metadata"]["reference_form"] for row in records)
    audit = {
        "schema": "sfh2-f-prep-exact-occurrence-audit-v1",
        "occurrence_count": len(records),
        "story_count_with_occurrences": len(story_occurrence_counts),
        "duplicate_exact_key_count": len(duplicate_exact),
        "duplicate_exact_keys": duplicate_exact,
        "missing_source_evidence_count": len(missing_evidence),
        "missing_source_evidence_occurrence_ids": sorted(set(missing_evidence)),
        "dangling_story_count": len(set(dangling_stories)),
        "dangling_story_ids": sorted(set(dangling_stories)),
        "invalid_occurrence_count": len(invalid_offsets),
        "invalid_occurrences": invalid_offsets,
        "target_text_mismatch_count": len(text_mismatches),
        "target_text_mismatches": text_mismatches,
        "duplicate_source_evidence_id_count": sum(count > 1 for count in evidence_id_counts.values()),
        "overlap_pair_count": len(overlaps),
        "nested_span_pair_count": len(nested),
        "overlap_pairs": overlaps,
        "nested_span_pairs": nested,
        "repeated_surface_group_count": len(repeated_surface),
        "repeated_surface_groups": repeated_surface,
        "counts_by_source_layer": dict(sorted(layer_counts.items())),
        "counts_by_entity_kind": dict(sorted(entity_counts.items())),
        "counts_by_reference_form": dict(sorted(form_counts.items())),
        "occurrences_by_story": dict(sorted(story_occurrence_counts.items())),
        "exact_occurrence_identity_required": [
            "occurrence_id", "mention_id", "story_id", "source_evidence_id",
            "source_start", "source_end", "surface",
        ],
        "surface_only_selection_forbidden": True,
        "candidate_only": True,
        "canonical_write_back": False,
    }
    return records, audit


def qualified_cache_entries(authority: Mapping[str, Any], occurrence_records: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    """Find exact pilot reuse witnesses without relaxing request identity."""

    occurrence_by_mention = {
        text(row["exact_occurrence_key"].get("mention_id")): row
        for row in occurrence_records
    }
    entries: list[dict[str, Any]] = []
    a2or_packets_by_case = {
        text(item.get("case_id")): item.get("packet")
        for item in rows(read_json(A2OR_ROOT / "case-packets.json", {}), "packets")
        if isinstance(item, Mapping) and isinstance(item.get("packet"), Mapping)
    }
    for stage, root, file_name, unit_name in (
        ("occurrence_primary", A2OR_ROOT, "occurrence-results.json", "A2OR"),
        ("boundary_validator", A2OVB_ROOT, "boundary-results.json", "A2OVB"),
    ):
        document = read_json(root / file_name, {}) or {}
        for row in rows(document, "records"):
            key = row.get("exact_occurrence_key")
            if not isinstance(key, Mapping):
                # A2OR stores the exact target in its immutable case packet;
                # the result row repeats only mention/story/surface.
                packet = a2or_packets_by_case.get(text(row.get("case_id")))
                target = packet.get("target") if isinstance(packet, Mapping) else None
                key = {
                    "mention_id": row.get("mention_id"),
                    "story_id": row.get("story_id"),
                    "source_evidence_id": (target or {}).get("source_evidence_id") if isinstance(target, Mapping) else None,
                    "source_start": (target or {}).get("source_start") if isinstance(target, Mapping) else None,
                    "source_end": (target or {}).get("source_end") if isinstance(target, Mapping) else None,
                    "surface": (target or {}).get("surface") if isinstance(target, Mapping) else row.get("surface"),
                }
            mention_id = text(key.get("mention_id") or row.get("mention_id"))
            occurrence = occurrence_by_mention.get(mention_id)
            transport = row.get("transport") if isinstance(row.get("transport"), Mapping) else {}
            result_valid = (
                row.get("valid") is True
                or row.get("validator_valid") is True
                or transport.get("valid") is True
            )
            if occurrence is None or not result_valid:
                continue
            exact_key = occurrence["exact_occurrence_key"]
            # A2OR does not carry an explicit nested key, so compare only the
            # authoritative key fields and never fall back to surface alone.
            if any(key.get(field) != exact_key.get(field) for field in ("mention_id", "story_id", "source_evidence_id", "source_start", "source_end", "surface")):
                continue
            entries.append({
                "stage": stage,
                "source_stage": unit_name,
                "occurrence_id": occurrence["occurrence_id"],
                "exact_occurrence_key": exact_key,
                "request_hash": transport.get("request_hash"),
                "response_witness_sha256": transport.get("response_witness_sha256"),
                "model": transport.get("model"),
                "temperature": transport.get("temperature"),
                "thinking": transport.get("thinking"),
                "prompt_version": transport.get("prompt_version"),
                "source_result_path": str((root / file_name).relative_to(ROOT)),
                "source_result_sha256": file_hash(root / file_name),
                "exact_request_witness_present": bool(transport.get("request_hash")),
                "source_case_id": row.get("case_id"),
                "matching_key_fields": ["mention_id", "story_id", "source_evidence_id", "source_start", "source_end", "surface"],
                "exact_reuse_candidate": True,
                "reuse_requires_current_request_hash_equality": True,
            })
    entries.sort(key=lambda row: (row["stage"], row["occurrence_id"]))
    counts = Counter(row["stage"] for row in entries)
    return {
        "schema": "sfh2-f-prep-cache-reuse-plan-v1",
        "policy": {
            "reuse_requires_all_components": True,
            "components": [
                "stage", "prompt_version", "schema_hash", "model", "temperature",
                "thinking", "exact_provider_packet", "exact_occurrence_key",
                "relevant_source_hashes", "frozen_identity_input_hash", "request_hash",
            ],
            "case_id_surface_story_only_reuse_forbidden": True,
            "mismatched_request_hash_never_reused": True,
        },
        "exact_reusable_provider_result_count": len(entries),
        "counts_by_stage": dict(sorted(counts.items())),
        "qualified_identity_context_reuse_count": 0,
        "entries": entries,
        "candidate_only": True,
        "canonical_write_back": False,
    }
