#!/usr/bin/env python3
"""Finalize the offline SFH2.2-A2GR Gold review and identity freeze.

This stage deliberately performs no inference.  It reads the human-reviewed
Gold promotion and the immutable A2R records, then derives evaluation and
provenance artifacts.  Historical semantics come from the reviewed Gold and
the frozen LLM records; this script has no identity resolver or provider
client.
"""

from __future__ import annotations

import copy
import hashlib
import json
import re
import subprocess
from pathlib import Path
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data/generated/sfh2-a2gr"
SELECTION_PATH = ROOT / "data/annotation/sfh2-a0-selection.json"
GOLD_PATH = ROOT / "data/annotation/sfh2-a0-evaluation-gold.json"
AUTHORITY_PATH = ROOT / "data/annotation/sfh2-a2gr-human-semantic-authority.json"
A2_ROOT = ROOT / "data/generated/sfh2-a2"
A2R_ROOT = ROOT / "data/generated/sfh2-a2r"
A2G_ROOT = ROOT / "data/generated/sfh2-a2g"
FREEZE_PATH = ROOT / "data/frozen/sfh2/identity-v1/manifest.json"
BASELINE_COMMIT = "c57bf17ff2ca783b98d492e412114edf5dd776b0"
SELECTION_HASH = "b8162d9d470c6359c67a8ed31aa31ef82149c12d92dd9a694b62327fc204bbc3"
OLD_GOLD_SHA256 = "82f36497b632032bc164c09fd5db97e35e20c256fc9654ac0d2c9b4c704b0b93"
FROZEN_SC1_SHA256 = "cc82c6738fcbf4fc14c12005a459048e71ce329492867d0910562fc6fdfda0d8"
CURRENT_SC1_SHA256 = "b916530264285dd7fa1d2e27a7a1dff8cd2ed794dfb3b84985881f8f209d8f6a"
PROVIDER_CALLS = 0

PROTECTED_FILES = (
    ROOT / "data/derived/sc1-site.json",
    ROOT / "data/derived/sc1-current-site.json",
    ROOT / "site/src/generated/sc1-site.json",
    ROOT / "site/src/generated/sc1-current-site.json",
    ROOT / "data/people.json",
    ROOT / "data/aliases.json",
    ROOT / "data/derived/person-relations-r3b.json",
    ROOT / "data/generated/sfh1/final-decisions.json",
    ROOT / "data/generated/sfh1/identity-judgments.json",
)


def text(value: Any) -> str:
    return str(value or "").strip()


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def stable_hash(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


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


def normalize(value: Any) -> str:
    """Normalize representation only; never infer historical identity."""

    translation = str.maketrans({
        "爲": "為",
        "髙": "高",
        "鳯": "鳳",
        "臺": "台",
        "裏": "裡",
        "禄": "祿",
        "隱": "隐",
        "獻": "献",
        "綽": "绰",
    })
    return re.sub(r"\s+", "", text(value)).translate(translation)


def _rows(document: Mapping[str, Any], key: str = "records") -> list[Mapping[str, Any]]:
    value = document.get(key, [])
    return [row for row in value if isinstance(row, Mapping)] if isinstance(value, list) else []


def _by_case(document: Mapping[str, Any], key: str = "records") -> dict[str, Mapping[str, Any]]:
    return {text(row.get("case_id")): row for row in _rows(document, key) if text(row.get("case_id"))}


def _by_story_surface(document: Mapping[str, Any]) -> dict[tuple[str, str], Mapping[str, Any]]:
    return {
        (text(row.get("story_id")), text(row.get("surface"))): row
        for row in _rows(document)
        if text(row.get("story_id")) and text(row.get("surface"))
    }


def _record(row: Mapping[str, Any] | None, key: str = "record") -> Mapping[str, Any] | None:
    if not isinstance(row, Mapping) or row.get("valid") is not True:
        return None
    value = row.get(key)
    return value if isinstance(value, Mapping) else None


def _referent(record: Mapping[str, Any] | None) -> Mapping[str, Any]:
    value = record.get("referent") if isinstance(record, Mapping) else None
    return value if isinstance(value, Mapping) else {}


def _attribute_fields(record: Mapping[str, Any], gold: Mapping[str, Any]) -> bool | None:
    expected_type = text(gold.get("expected_attribute_type"))
    expected_value = text(gold.get("expected_attribute_value"))
    expected_bearer = text(gold.get("expected_bearer"))
    if not any((expected_type, expected_value, expected_bearer)):
        return True
    return (
        text(record.get("attribute_type")) == expected_type
        and text(record.get("attribute_value")) == expected_value
        and text(record.get("bearer_hint")) == expected_bearer
    )


def dimensions(
    record: Mapping[str, Any] | None,
    gold: Mapping[str, Any],
    *,
    candidate: Mapping[str, Any] | None = None,
) -> dict[str, bool | None]:
    """Evaluate independently observable fields against reviewed Gold.

    This is post-inference evaluation.  It does not turn representation
    similarity into an identity decision, and non-person Gold is outside the
    historical-person identity cohort.
    """

    if not isinstance(record, Mapping):
        return {
            "identity_correct": None,
            "semantic_kind_correct": None,
            "referent_surface_correct": None,
            "canonicalization_correct": None,
            "occurrence_role_correct": None,
            "attribute_fields_correct": None,
            "discourse_correct": None,
            "relation_correct": None,
            "serialization_contract_correct": False,
        }
    referent = _referent(record)
    expected_kind = text(gold.get("expected_semantic_kind"))
    expected_surface = text(gold.get("expected_referent_surface"))
    expected_hint = text(gold.get("expected_canonical_hint"))
    expected_role = text(gold.get("expected_role"))
    kind_ok = text(record.get("semantic_kind")) == expected_kind if expected_kind else None
    surface_ok = normalize(referent.get("surface_form")) == normalize(expected_surface) if expected_surface else None
    canonical_ok = normalize(referent.get("canonical_hint")) == normalize(expected_hint) if expected_hint else None
    role_ok = text(record.get("occurrence_role")) == expected_role if expected_role else None
    attribute_ok = _attribute_fields(record, gold)
    forbidden = {normalize(value) for value in gold.get("must_not_resolve_to", []) or []}
    candidate_name = candidate.get("display_name") if isinstance(candidate, Mapping) else ""
    forbidden_hit = normalize(referent.get("canonical_hint")) in forbidden or normalize(candidate_name) in forbidden
    if expected_kind == "historical_person":
        identity_ok: bool | None = bool(canonical_ok) and not forbidden_hit if canonical_ok is not None else None
    else:
        identity_ok = None
    return {
        "identity_correct": identity_ok,
        "semantic_kind_correct": kind_ok,
        "referent_surface_correct": surface_ok,
        "canonicalization_correct": canonical_ok,
        "occurrence_role_correct": role_ok,
        "attribute_fields_correct": attribute_ok,
        "discourse_correct": None,
        "relation_correct": None,
        "serialization_contract_correct": True,
    }


def strict_full_record(dims: Mapping[str, Any]) -> bool:
    return all(
        dims.get(field) is not False
        for field in (
            "semantic_kind_correct",
            "referent_surface_correct",
            "canonicalization_correct",
            "occurrence_role_correct",
            "attribute_fields_correct",
        )
    )


def identity_evaluable(gold: Mapping[str, Any]) -> bool:
    return text(gold.get("expected_semantic_kind")) == "historical_person" and bool(text(gold.get("expected_canonical_hint")))


def _status(value: bool | None, evaluable: bool) -> str:
    if not evaluable:
        return "not_identity_evaluable"
    if value is True:
        return "semantic_correct"
    if value is False:
        return "semantic_wrong"
    return "unresolved"


def _stage_view(
    row: Mapping[str, Any] | None,
    gold: Mapping[str, Any],
    *,
    record_key: str = "record",
    candidate_key: str = "provisional_realization",
) -> dict[str, Any]:
    row = row if isinstance(row, Mapping) else {}
    record = _record(row, record_key)
    realization = row.get(candidate_key) if isinstance(row.get(candidate_key), Mapping) else {}
    candidate = realization.get("candidate") if isinstance(realization.get("candidate"), Mapping) else None
    evaluated = dimensions(record, gold, candidate=candidate)
    evaluable = identity_evaluable(gold)
    return {
        "valid": record is not None,
        "contract_status": text(row.get("contract_status")) or ("valid" if record is not None else "contract_invalid"),
        "semantic_record": copy.deepcopy(record) if record is not None else None,
        "candidate": copy.deepcopy(candidate) if candidate is not None else None,
        "dimensions": evaluated,
        "identity_status": _status(evaluated.get("identity_correct"), evaluable),
        "strict_full_record_correct": strict_full_record(evaluated) if record is not None else False,
    }


def _final_view(row: Mapping[str, Any] | None, gold: Mapping[str, Any]) -> dict[str, Any]:
    row = row if isinstance(row, Mapping) else {}
    record = row.get("selected_record") if isinstance(row.get("selected_record"), Mapping) else None
    candidate = row.get("selected_candidate") if isinstance(row.get("selected_candidate"), Mapping) else None
    evaluated = dimensions(record, gold, candidate=candidate)
    evaluable = identity_evaluable(gold)
    return {
        "valid": record is not None,
        "contract_status": "valid" if record is not None else "unresolved",
        "semantic_record": copy.deepcopy(record) if record is not None else None,
        "candidate": copy.deepcopy(candidate) if candidate is not None else None,
        "dimensions": evaluated,
        "identity_status": _status(evaluated.get("identity_correct"), evaluable),
        "strict_full_record_correct": strict_full_record(evaluated) if record is not None else False,
        "final_state": row.get("final_state"),
        "selected_record_source": row.get("selected_record_source"),
    }


def _snapshot_tree(path: Path) -> dict[str, Any]:
    files: list[dict[str, Any]] = []
    if path.is_dir():
        for child in sorted(path.rglob("*")):
            if child.is_file():
                files.append({
                    "path": str(child.relative_to(ROOT)),
                    "sha256": file_hash(child),
                    "size_bytes": child.stat().st_size,
                })
    return {
        "path": str(path.relative_to(ROOT)),
        "file_count": len(files),
        "total_bytes": sum(row["size_bytes"] for row in files),
        "tree_sha256": stable_hash(files),
        "files": files,
    }


def protected_hashes() -> dict[str, str]:
    return {
        str(path.relative_to(ROOT)): file_hash(path)
        for path in PROTECTED_FILES
        if path.is_file()
    }


def _deep_diff(before: Any, after: Any, path: str = "") -> list[str]:
    if type(before) is not type(after):
        return [path or "$" ]
    if isinstance(before, Mapping):
        keys = sorted(set(before) | set(after), key=str)
        result: list[str] = []
        for key in keys:
            child = f"{path}.{key}" if path else str(key)
            if key not in before or key not in after:
                result.append(child)
            else:
                result.extend(_deep_diff(before[key], after[key], child))
        return result
    if isinstance(before, list):
        result = []
        for index in range(max(len(before), len(after))):
            child = f"{path}[{index}]"
            if index >= len(before) or index >= len(after):
                result.append(child)
            else:
                result.extend(_deep_diff(before[index], after[index], child))
        return result
    return [] if before == after else [path or "$" ]


def _baseline_gold() -> dict[str, Any]:
    """Read the predecessor Gold from Git, never from a mutable worktree copy."""

    result = subprocess.run(
        ["git", "show", f"{BASELINE_COMMIT}:data/annotation/sfh2-a0-evaluation-gold.json"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(result.stdout)


def _gold_delta(
    authority: Mapping[str, Any],
    previous_document: Mapping[str, Any],
    reviewed: Mapping[str, Any],
) -> dict[str, Any]:
    old_map = {text(row.get("case_key")): row for row in _rows(previous_document) if text(row.get("case_key"))}
    new_map = {text(row.get("case_key")): row for row in _rows(reviewed) if text(row.get("case_key"))}
    changed: list[dict[str, Any]] = []
    for key in sorted(set(old_map) | set(new_map)):
        before = old_map.get(key)
        after = new_map.get(key)
        if isinstance(after, Mapping) and "case_key" in after:
            after = {k: v for k, v in after.items() if k not in {"revision"}}
        if before != after:
            changed.append({
                "case_key": key,
                "story_id": (after or before or {}).get("story_id"),
                "surface": (after or before or {}).get("surface"),
                "changed_fields": _deep_diff(before, after),
                "before": copy.deepcopy(before),
                "after": copy.deepcopy(after),
                "semantic_class": "reviewed_ontology_boundary",
            })
    reaffirmed = sorted(
        text(row.get("case_key"))
        for row in _rows(authority, "records")
        if text(row.get("decision")) == "reaffirm_gold"
    )
    return {
        "schema": "sfh2-a2gr-reviewed-gold-delta-v1",
        "stage": "SFH2.2-A2GR",
        "source_gold_path": str(GOLD_PATH.relative_to(ROOT)),
        "source_gold_sha256": OLD_GOLD_SHA256,
        "reviewed_gold_path": str(GOLD_PATH.relative_to(ROOT)),
        "reviewed_gold_sha256": file_hash(GOLD_PATH),
        "substantive_mutation_count": len(changed),
        "changed_cases": changed,
        "reaffirmed_cases": reaffirmed,
        "reaffirmed_case_count": len(reaffirmed),
        "authority_record": str(AUTHORITY_PATH.relative_to(ROOT)),
        "authority": "human_semantic_review",
        "gold_mutated_by_human_promotion": True,
        "provider_calls": PROVIDER_CALLS,
        "candidate_only": True,
        "canonical_write_back": False,
    }


def _identity_stats(rows: list[Mapping[str, Any]], stage: str) -> dict[str, Any]:
    values = [row.get(stage, {}).get("dimensions", {}).get("identity_correct") for row in rows]
    resolved = [value for value in values if value is not None]
    return {
        "correct": sum(value is True for value in values),
        "wrong": sum(value is False for value in values),
        "unresolved": sum(value is None for value in values),
        "evaluable": len(values),
        "resolved": len(resolved),
        "resolution_coverage": round(len(resolved) / len(values), 4) if values else None,
        "accuracy_on_resolved": round(sum(value is True for value in resolved) / len(resolved), 4) if resolved else None,
        "full_cohort_accuracy": round(sum(value is True for value in values) / len(values), 4) if values else None,
    }


def _dimension_counts(rows: list[Mapping[str, Any]], stage: str) -> dict[str, dict[str, Any]]:
    fields = (
        "identity_correct",
        "semantic_kind_correct",
        "referent_surface_correct",
        "canonicalization_correct",
        "occurrence_role_correct",
        "attribute_fields_correct",
        "discourse_correct",
        "relation_correct",
        "serialization_contract_correct",
    )
    return {
        field: {
            "correct": sum(row.get(stage, {}).get("dimensions", {}).get(field) is True for row in rows),
            "incorrect": sum(row.get(stage, {}).get("dimensions", {}).get(field) is False for row in rows),
            "evaluable": sum(row.get(stage, {}).get("dimensions", {}).get(field) is not None for row in rows),
        }
        for field in fields
    }


def _evaluation_metrics(rows: list[Mapping[str, Any]]) -> dict[str, Any]:
    identity_rows = [row for row in rows if row.get("historical_identity_evaluable")]
    def stats(stage: str) -> dict[str, Any]:
        return _identity_stats(identity_rows, stage)
    a_errors = [row for row in identity_rows if row["historian_a"]["dimensions"].get("identity_correct") is False]
    common_mode = [
        row for row in identity_rows
        if row["historian_a"]["dimensions"].get("identity_correct") is False
        and row["historian_b"]["dimensions"].get("identity_correct") is False
        and row.get("identity_agreement") is True
    ]
    damage = [
        row for row in identity_rows
        if row["final"]["dimensions"].get("identity_correct") is False
        and (
            row["historian_a"]["dimensions"].get("identity_correct") is True
            or row["historian_b"]["dimensions"].get("identity_correct") is True
        )
    ]
    return {
        "case_count": len(rows),
        "historical_identity_evaluable": len(identity_rows),
        "historian_a_identity": stats("historian_a"),
        "historian_b_identity": stats("historian_b"),
        "final_identity": stats("final"),
        "resolution_coverage": stats("final")["resolution_coverage"],
        "identity_accuracy_on_resolved": stats("final")["accuracy_on_resolved"],
        "dimension_counts": {stage: _dimension_counts(rows, stage) for stage in ("historian_a", "historian_b", "final")},
        "strict_full_record_accuracy": {
            stage: round(sum(row[stage].get("strict_full_record_correct") is True for row in rows) / len(rows), 4) if rows else None
            for stage in ("historian_a", "historian_b", "final")
        },
        "a_identity_errors": len(a_errors),
        "joint_identity_failure_count": len(common_mode),
        "reviewer_damage": len(damage),
        "errors_recovered": sum(
            row["historian_a"]["dimensions"].get("identity_correct") is False
            and row["final"]["dimensions"].get("identity_correct") is True
            for row in identity_rows
        ),
        "new_identity_errors_introduced": sum(
            row["historian_a"]["dimensions"].get("identity_correct") is True
            and row["final"]["dimensions"].get("identity_correct") is False
            for row in identity_rows
        ),
        "final_unresolved_identity_cases": sum(row["final"]["identity_status"] == "unresolved" for row in identity_rows),
        "provider_calls": PROVIDER_CALLS,
        "candidate_only": True,
        "canonical_write_back": False,
    }


def _protected_trees() -> dict[str, dict[str, Any]]:
    return {str(path.relative_to(ROOT)): _snapshot_tree(path) for path in (A2_ROOT, A2R_ROOT, A2G_ROOT)}


def build_outputs() -> dict[str, Any]:
    selection = read_json(SELECTION_PATH, {}) or {}
    reviewed_gold = read_json(GOLD_PATH, {}) or {}
    authority = read_json(AUTHORITY_PATH, {}) or {}
    previous_document = _baseline_gold()
    old_gold_map = {
        text(row.get("case_key")): row
        for row in _rows(previous_document)
        if text(row.get("case_key"))
    }
    new_gold_map = {text(row.get("case_key")): row for row in _rows(reviewed_gold) if text(row.get("case_key"))}

    a_doc = read_json(A2R_ROOT / "historian-a-cache-index.json", {}) or {}
    b_doc = read_json(A2R_ROOT / "historian-b-cache-reuse.json", {}) or {}
    final_doc = read_json(A2R_ROOT / "final-results.json", {}) or {}
    adj_doc = read_json(A2R_ROOT / "adjudicator-results.json", {}) or {}
    packets_doc = read_json(A2_ROOT / "case-packets.json", {}) or {}
    a_map = _by_case(a_doc)
    b_map = _by_case(b_doc)
    final_map = _by_case(final_doc)
    adj_map = _by_case(adj_doc)
    packet_map = {
        text(row.get("case_id")): row.get("packet", {})
        for row in _rows(packets_doc, "packets")
        if isinstance(row.get("packet"), Mapping)
    }

    rows: list[dict[str, Any]] = []
    for case in _rows(selection, "cases"):
        case_id = text(case.get("case_id"))
        case_key = next(
            (text(row.get("case_key")) for row in _rows(reviewed_gold) if text(row.get("story_id")) == text(case.get("story_id")) and text(row.get("surface")) == text(case.get("surface"))),
            "",
        )
        gold = dict(new_gold_map.get(case_key, {}))
        old_gold = dict(old_gold_map.get(case_key, {}))
        a = a_map.get(case_id, {})
        b = b_map.get(case_id, {})
        final = final_map.get(case_id, {})
        comparison = adj_map.get(case_id, {}).get("ab_comparison") if isinstance(adj_map.get(case_id), Mapping) else None
        if not isinstance(comparison, Mapping):
            comparison = {}
        a_view = _stage_view(a, gold)
        b_view = _stage_view(b, gold)
        final_view = _final_view(final, gold)
        a_record = a_view.get("semantic_record")
        b_record = b_view.get("semantic_record")
        rows.append({
            "case_id": case_id,
            "case_key": case_key,
            "story_id": case.get("story_id"),
            "surface": case.get("surface"),
            "mention_id": case.get("mention_id"),
            "source_evidence_id": case.get("source_evidence_id"),
            "gold_before": old_gold,
            "gold_reviewed": gold,
            "historical_identity_evaluable": identity_evaluable(gold),
            "source_evidence": copy.deepcopy(packet_map.get(case_id, {}).get("source_evidence", [])) if isinstance(packet_map.get(case_id), Mapping) else [],
            "historian_a": a_view,
            "historian_b": b_view,
            "final": final_view,
            "identity_agreement": comparison.get("historical_identity_disagreement") is False if comparison else None,
            "ab_comparison": copy.deepcopy(comparison),
            "adjudicator_decision": (adj_map.get(case_id) or {}).get("decision"),
            "selector_copy_drift": False,
            "candidate_only": True,
            "canonical_write_back": False,
        })

    before_rows: list[dict[str, Any]] = []
    for row in rows:
        before = copy.deepcopy(row)
        before["gold_reviewed"] = before.get("gold_before", {})
        before["historical_identity_evaluable"] = identity_evaluable(before["gold_reviewed"])
        before["historian_a"] = _stage_view(a_map.get(row["case_id"], {}), before["gold_reviewed"])
        before["historian_b"] = _stage_view(b_map.get(row["case_id"], {}), before["gold_reviewed"])
        before["final"] = _final_view(final_map.get(row["case_id"], {}), before["gold_reviewed"])
        before_rows.append(before)

    a2r_semantic = read_json(A2R_ROOT / "semantic-preservation-audit.json", {}) or {}
    a2r_storage = read_json(A2R_ROOT / "storage-safety-audit.json", {}) or {}
    selector_drift = int(a2r_semantic.get("selector_copy_drift") or 0)
    undeclared = int(a2r_semantic.get("undeclared_patch_mutations") or 0)
    after_metrics = _evaluation_metrics(rows)
    before_metrics = _evaluation_metrics(before_rows)
    delta = _gold_delta(authority, previous_document, reviewed_gold)

    identity_re_evaluation = {
        "schema": "sfh2-a2gr-identity-re-evaluation-v1",
        "stage": "SFH2.2-A2GR",
        "provider_calls": PROVIDER_CALLS,
        "gold_before_sha256": OLD_GOLD_SHA256,
        "gold_reviewed_sha256": file_hash(GOLD_PATH),
        "identity_evaluable_before": before_metrics["historical_identity_evaluable"],
        "identity_evaluable_after": after_metrics["historical_identity_evaluable"],
        "before": before_metrics,
        "after": after_metrics,
        "records": rows,
        "gold_evaluation_only": True,
        "candidate_only": True,
        "canonical_write_back": False,
    }

    safety_counts = {
        "production_person_creations": int(a2r_storage.get("production_person_creations") or 0),
        "canonical_writes": int(a2r_storage.get("canonical_writes") or 0),
        "alias_mutations": int(a2r_storage.get("alias_mutations") or 0),
        "profile_mutations": int(a2r_storage.get("profile_mutations") or 0),
        "related_person_promotions": int(a2r_storage.get("related_person_promotions") or 0),
        "attribute_person_promotions": int(a2r_storage.get("attribute_person_promotions") or 0),
        "collective_person_promotions": int(a2r_storage.get("collective_person_promotions") or 0),
        "substring_candidate_generation": int(a2r_storage.get("substring_candidate_generation") or 0),
        "python_historical_identity_replacements": int(a2r_storage.get("python_historical_identity_replacements") or 0),
    }
    gate_checks = {
        "final_identity_accuracy_at_least_95_percent": (after_metrics["final_identity"].get("accuracy_on_resolved") or 0) >= 0.95,
        "final_resolution_coverage_100_percent": after_metrics["final_identity"].get("resolution_coverage") == 1.0,
        "adjudicator_damage_zero": after_metrics["reviewer_damage"] == 0,
        "no_unresolved_historical_person_gold_case": after_metrics["final_unresolved_identity_cases"] == 0,
        "selector_copy_drift_zero": selector_drift == 0,
        "undeclared_patch_mutations_zero": undeclared == 0,
        "python_historical_semantic_replacement_zero": safety_counts["python_historical_identity_replacements"] == 0,
        "canonical_write_zero": safety_counts["canonical_writes"] == 0,
        "production_person_creation_zero": safety_counts["production_person_creations"] == 0,
        "gold_provenance_valid": (
            text(reviewed_gold.get("schema")) == "sfh2-a0-evaluation-gold-v3"
            and text(reviewed_gold.get("revision", {}).get("authority")) == "human_semantic_review"
            and reviewed_gold.get("revision", {}).get("previous_sha256") == OLD_GOLD_SHA256
            and delta.get("substantive_mutation_count") == 1
        ),
    }
    qualified = all(gate_checks.values())

    metrics = {
        "schema": "sfh2-a2gr-metrics-v1",
        "stage": "SFH2.2-A2GR",
        "provider_calls": PROVIDER_CALLS,
        "gold_mutation": {
            "previous_sha256": OLD_GOLD_SHA256,
            "reviewed_sha256": file_hash(GOLD_PATH),
            "substantive_mutation_count": delta.get("substantive_mutation_count"),
            "reaffirmed_case_count": delta.get("reaffirmed_case_count"),
        },
        "identity_evaluable_before": before_metrics["historical_identity_evaluable"],
        "identity_evaluable_after": after_metrics["historical_identity_evaluable"],
        "before": before_metrics,
        "after": after_metrics,
        "joint_identity_failure_count_before": sum(
            row["historian_a"]["dimensions"].get("identity_correct") is False
            and row["historian_b"]["dimensions"].get("identity_correct") is False
            for row in before_rows
            if row.get("historical_identity_evaluable")
        ),
        "joint_identity_failure_count_after": sum(
            row["historian_a"]["dimensions"].get("identity_correct") is False
            and row["historian_b"]["dimensions"].get("identity_correct") is False
            for row in rows
            if row.get("historical_identity_evaluable")
        ),
        "reviewer_damage": after_metrics["reviewer_damage"],
        "selector_copy_drift": selector_drift,
        "undeclared_patch_mutations": undeclared,
        "safety": safety_counts,
        "candidate_only": True,
        "canonical_write_back": False,
    }

    qualification = {
        "schema": "sfh2-a2gr-identity-qualification-v1",
        "stage": "SFH2.2-A2GR",
        "identity_pipeline_status": "qualified_and_frozen" if qualified else "not_qualified",
        "gate_passed": qualified,
        "checks": gate_checks,
        "final_identity": after_metrics["final_identity"],
        "historical_identity_evaluable": after_metrics["historical_identity_evaluable"],
        "provider_calls": PROVIDER_CALLS,
        "candidate_only": True,
        "canonical_write_back": False,
    }

    protected = _protected_trees()
    freeze = {
        "schema": "sfh2-identity-freeze-v1",
        "stage": "SFH2.2-A2GR",
        "baseline_commit": BASELINE_COMMIT,
        "a2r_source_commit": "32e5081d57766f43456becfcb340206acae1f950",
        "a2g_source_commit": "c57bf17ff2ca783b98d492e412114edf5dd776b0",
        "a2gr_commit_placeholder": "pending-final-commit",
        "reviewed_gold_sha256": file_hash(GOLD_PATH),
        "reviewed_gold_path": str(GOLD_PATH.relative_to(ROOT)),
        "human_authority_path": str(AUTHORITY_PATH.relative_to(ROOT)),
        "historian_a_source_hash": file_hash(A2R_ROOT / "historian-a-cache-index.json"),
        "historian_b_source_hash": file_hash(A2R_ROOT / "historian-b-cache-reuse.json"),
        "a2r_final_result_hash": file_hash(A2R_ROOT / "final-results.json"),
        "a2r_evaluation_hash": file_hash(A2R_ROOT / "regression-evaluation.json"),
        "a2g_tree": protected[str(A2G_ROOT.relative_to(ROOT))],
        "protected_experiment_trees": protected,
        "protected_file_hashes": protected_hashes(),
        "evaluation_code_hash": file_hash(Path(__file__)),
        "identity_metrics": after_metrics["final_identity"],
        "identity_pipeline_status": "qualified_and_frozen" if qualified else "not_qualified",
        "architecture_statement": {
            "historical_evidence_to_historian_a_and_b": True,
            "semantic_comparison_to_adjudicator": True,
            "candidate_semantic_layer": True,
            "python_validates_integrity_and_consistency": True,
            "human_review_promotes_gold_and_canonical_truth": True,
            "no_retrieval_candidate_gate": True,
            "no_lexical_identity_rules": True,
            "no_substring_identity": True,
            "no_automatic_alias_string_identity_equivalence": True,
            "no_production_canonical_write_back": True,
        },
        "provider_calls": PROVIDER_CALLS,
        "candidate_only": True,
        "canonical_write_back": False,
    }

    return {
        "reviewed-gold-delta.json": delta,
        "identity-re-evaluation.json": identity_re_evaluation,
        "identity-qualification.json": qualification,
        "metrics.json": metrics,
        "recommendation.json": {
            "schema": "sfh2-a2gr-recommendation-v1",
            "recommendation": "sfh2_identity_pipeline_frozen" if qualified else "sfh2_identity_pipeline_not_qualified",
            "identity_pipeline_status": qualification["identity_pipeline_status"],
            "reason": "The reviewed Gold removes one ontology-boundary case from the historical-person cohort; the frozen A2R final outputs qualify all remaining historical-person identities." if qualified else "The reviewed Gold promotion did not satisfy every deterministic identity qualification gate.",
            "next_stage": "SFH2.2-A2O" if qualified else "Resolve failed qualification gates before A2O.",
            "provider_calls": PROVIDER_CALLS,
            "candidate_only": True,
            "canonical_write_back": False,
        },
        "protected-hash-snapshot.json": {
            "schema": "sfh2-a2gr-protected-hash-snapshot-v1",
            "stage": "SFH2.2-A2GR",
            "baseline_commit": BASELINE_COMMIT,
            "trees": protected,
            "files": protected_hashes(),
            "provider_calls": PROVIDER_CALLS,
            "candidate_only": True,
            "canonical_write_back": False,
        },
        str(FREEZE_PATH.relative_to(ROOT)): freeze,
    }


def run() -> Path:
    outputs = build_outputs()
    for relative, value in outputs.items():
        destination = ROOT / relative if relative.startswith("data/") else OUT / relative
        write_json(destination, value)
    return OUT


if __name__ == "__main__":
    print(f"wrote offline SFH2.2-A2GR outputs to {run()}")
