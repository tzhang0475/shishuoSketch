"""A0R-L formal consistency adapters; no historical-language rules."""

from __future__ import annotations

from collections import defaultdict
from typing import Any, Mapping

from sfh2_a0r.consistency import (
    analyze_record as _analyze_record,
    hard_conflict,
    review_required,
)
from sfh2_a0r.common import text

CONSISTENCY_CONTRACT = "sfh2-a0r-l-formal-record-and-story-consistency-v1"


def analyze_record(*args: Any, **kwargs: Any) -> dict[str, Any]:
    result = _analyze_record(*args, **kwargs)
    result = dict(result)
    result["schema"] = "sfh2-a0r-l-consistency-v1"
    return result


def story_consistency(records: list[Mapping[str, Any]]) -> dict[str, Any]:
    """Find only explicit structured contradictions among a Story's rows.

    Repeated surfaces and different candidate strings are reported as
    diagnostics, never merged or resolved here.  The relation labels are
    already LLM semantic output; this function only checks incompatible labels
    on the same explicitly named endpoint pair.
    """

    relation_labels: dict[tuple[str, str], set[str]] = defaultdict(set)
    relation_evidence: dict[tuple[str, str], set[str]] = defaultdict(set)
    canonical_mentions: dict[str, list[str]] = defaultdict(list)
    flags: list[dict[str, Any]] = []
    for row in records:
        mention_id = text(row.get("mention_id"))
        record = row.get("selected_record") if isinstance(row.get("selected_record"), Mapping) else row.get("record")
        if not isinstance(record, Mapping):
            continue
        referent = record.get("referent") if isinstance(record.get("referent"), Mapping) else {}
        hint = text(referent.get("canonical_hint"))
        if hint:
            canonical_mentions[hint].append(mention_id)
        for relation in record.get("relations", []) or []:
            if not isinstance(relation, Mapping):
                continue
            label = text(relation.get("relation"))
            target = text(relation.get("target_hint"))
            if not label or not target:
                continue
            key = tuple(sorted((mention_id, target)))
            relation_labels[key].add(label)
            relation_evidence[key].update(text(value) for value in relation.get("evidence_ids", []) or [] if text(value))
    for key, labels in sorted(relation_labels.items()):
        if "same_person" in labels and "different_person" in labels:
            flags.append({
                "flag_type": "identity_distinctness_conflict",
                "severity": "hard",
                "involved": list(key),
                "challenged_fields": ["relations"],
                "evidence_ids": sorted(relation_evidence[key]),
                "formal_reason": "the same explicit endpoint pair carries incompatible same_person and different_person labels",
            })
    repeated = [
        {"canonical_hint": hint, "mention_ids": sorted(ids), "severity": "diagnostic", "formal_reason": "multiple occurrences proposed the same semantic canonical hint; no automatic merge performed"}
        for hint, ids in sorted(canonical_mentions.items())
        if len(ids) > 1
    ]
    return {
        "schema": "sfh2-a0r-l-story-consistency-v1",
        "flags": flags,
        "diagnostics": {"repeated_canonical_hints": repeated},
        "hard_conflict": bool(flags),
        "record_count": len(records),
        "candidate_only": True,
        "canonical_write_back": False,
    }


__all__ = ["CONSISTENCY_CONTRACT", "analyze_record", "hard_conflict", "review_required", "story_consistency"]
