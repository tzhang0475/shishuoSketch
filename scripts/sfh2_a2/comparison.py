"""Generic structural comparison of two semantic hypotheses."""

from __future__ import annotations

from typing import Any, Mapping

from sfh2_a0r.contracts import semantic_diff_paths, substantive_semantic_diff_paths
from .common import text

METADATA_PATHS = frozenset({"confidence", "referent.confidence", "supporting_evidence_ids"})


def _classes(paths: list[str]) -> list[str]:
    result: set[str] = set()
    for path in paths:
        if path in METADATA_PATHS:
            continue
        if path == "semantic_kind":
            result.add("semantic_kind_disagreement")
        elif path == "reference_type":
            result.add("reference_type_disagreement")
        elif path.startswith("referent."):
            result.add("identity_disagreement")
        elif path == "occurrence_role":
            result.add("occurrence_role_disagreement")
        elif path.startswith("discourse."):
            result.add("discourse_disagreement")
        elif path == "relations":
            result.add("relation_disagreement")
        elif path == "abstain":
            result.add("abstention_disagreement")
        else:
            result.add("semantic_field_disagreement")
    return sorted(result)


def compare_records(
    a: Mapping[str, Any] | None,
    b: Mapping[str, Any] | None,
    *,
    a_valid: bool,
    b_valid: bool,
) -> dict[str, Any]:
    if not a_valid or not b_valid:
        classes = ["contract_validity_disagreement"] if a_valid != b_valid else []
        return {
            "a_valid": a_valid,
            "b_valid": b_valid,
            "agreement": bool(a_valid and b_valid),
            "substantive_disagreement": True if a_valid != b_valid else False,
            "semantic_fields": ["record"] if a_valid != b_valid else [],
            "substantive_fields": ["record"] if a_valid != b_valid else [],
            "disagreement_classes": classes,
            "metadata_only_difference": False,
            "historical_identity_disagreement": a_valid != b_valid,
        }
    fields = semantic_diff_paths(a, b)
    substantive = substantive_semantic_diff_paths(a, b)
    classes = _classes(fields)
    metadata_only = bool(fields) and not substantive
    return {
        "a_valid": True,
        "b_valid": True,
        "agreement": not bool(substantive),
        "substantive_disagreement": bool(substantive),
        "semantic_fields": fields,
        "substantive_fields": substantive,
        "disagreement_classes": ["metadata_only_difference"] if metadata_only else classes,
        "metadata_only_difference": metadata_only,
        "historical_identity_disagreement": any(path.startswith("referent.") for path in substantive),
    }


def challenge_summary(comparisons: list[Mapping[str, Any]]) -> dict[str, Any]:
    counts: dict[str, int] = {}
    for row in comparisons:
        for label in row.get("disagreement_classes", []) or []:
            counts[text(label)] = counts.get(text(label), 0) + 1
    return {
        "case_count": len(comparisons),
        "agreement_count": sum(row.get("agreement") is True for row in comparisons),
        "substantive_disagreement_count": sum(row.get("substantive_disagreement") is True for row in comparisons),
        "metadata_only_difference_count": sum(row.get("metadata_only_difference") is True for row in comparisons),
        "class_counts": dict(sorted(counts.items())),
    }
