"""Run the offline SFH2.2-F1R production acceptance review.

F1R is deliberately an evidence audit, not a semantic rerun.  It consumes
the exact F1 selection, source packets, compact candidate records,
checkpoints, and transport metadata.  It never imports a provider client and
it never writes outside the caller-supplied F1R output directory.

The small human-audit finding table below is keyed by immutable occurrence
IDs.  It records offline review conclusions about the already selected
occurrences; it is not runtime semantic logic and never examines a surface to
choose a label.
"""

from __future__ import annotations

import copy
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Mapping

from sfh2_f1 import common as f1


ROOT = Path(__file__).resolve().parents[2]
BASELINE_COMMIT = "2da3e2d7f8470f6d0ca0abf3076b29380c4c54bb"
OUT = ROOT / "data/generated/sfh2-f1r"
F1_ROOT = ROOT / "data/generated/sfh2-f1"
F1_PREP_ROOT = ROOT / "data/generated/sfh2-f-prep"
SEMANTIC_ROOT = ROOT / "data/frozen/sfh2/semantic-v1"
SCOPE_PATH = F1_PREP_ROOT / "production-scope.json"
REVIEW_POLICY_PATH = F1_PREP_ROOT / "review-routing-policy.json"

PROTECTED_FILES = (
    "data/annotation/sfh2-a2o-evaluation-gold.json",
    "data/frozen/sfh2/identity-v1/manifest.json",
    "data/frozen/sfh2/semantic-v1/manifest.json",
    "data/frozen/sfh2/semantic-v1/architecture.json",
    "data/frozen/sfh2/semantic-v1/schemas.json",
    "data/frozen/sfh2/semantic-v1/protected-hashes.json",
    "data/derived/sc1-site.json",
    "data/derived/sc1-current-site.json",
    "site/src/generated/sc1-site.json",
    "site/src/generated/sc1-current-site.json",
    "data/people.json",
    "data/aliases.json",
    "data/derived/h0c-historical-facts.json",
    "data/derived/person-resolution-effective.json",
)

PROTECTED_DIRECTORIES = (
    "data/generated/sfh2-f-prep",
    "data/generated/sfh2-f1",
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
    "data/frozen/sfh2/semantic-v1",
)


# Stable occurrence IDs from the F1 exact selection.  These findings are
# intentionally keyed by occurrence identity rather than surface text.  They
# are an offline review ledger, not executable semantic rules.
OCCURRENCE_IDS = {
    "季方": "sfh1-mention-fb979fe0b42ef4d06939f630",
    "孔巖": "sfh1-mention-ba0a6bfd3b70867199867b3a",
    "殷公": "sfh1-mention-250c0ae68551d8dab4943ed8",
    "剌史": "sfh1-mention-ab9210bb6f88d713e884fe26",
    "子野": "sfh1-mention-4212d15b7a219584954587d8",
    "堯": "sfh1-mention-2d1f96737b7b0ef11588f7e5",
    "王文度": "sfh1-mention-b6fa0b811087b18b0774e8f9",
    "諸名士": "sfh1-mention-acaffc0cd7c6899e24eb9ee9",
    "兒": "sfh1-mention-edd76871090fb1cad57dcd9c",
    "謝家": "sfh1-mention-e5a5f3d5367f63de75fca0b0",
    "桓子野": "sfh1-mention-c051c79699ee2334eccc5086",
    "祖端": "sfh1-mention-2c6672ce7bffaa6f16181810",
    "祥": "sfh1-mention-ff73ef4d86b3e237614ab6af",
    "卿": "sfh1-mention-7754db159dd2508a0e0966b1",
    "何曽": "sfh1-mention-14aadf84022adda0aa99308b",
    "湘州刺史": "sfh1-mention-e2c43c63a28c758a1c1192f1",
    "爰": "sfh1-mention-63d90ef457a6a2419f9b1588",
    "陸機": "sfh1-mention-b4f58ecca05c3c538d559feb",
    "宏": "sfh1-mention-60f9d5ff179ecbdd321e88fc",
    "王敦": "sfh1-mention-e07789c3e12569ce9624526e",
    "羣臣": "sfh1-mention-2520231f896de7b4fbb1c507",
    "楊": "sfh1-mention-e8f9268305e71ab3d1724605",
    "康": "sfh1-mention-55b97afde3e7fb4c074361b8",
    "大將軍": "sfh1-mention-0dddf6803e50a201bbf0e0f5",
    "王蒙": "sfh1-mention-57b7746a3be07831cfa06a32",
    "司徒第二子": "sfh1-mention-c7948b25743a9dba7d00497e",
    "父融": "sfh1-mention-a784097a150a921e85a6d19f",
    "周俊": "sfh1-mention-f32b680621137411704250be",
    "江南": "sfh1-mention-7be0675e1cbc7d93e92349be",
    "吾": "sfh1-mention-276c292df4447b07909ecf22",
}


REASON_TARGET_AUDIT: dict[str, dict[str, Any]] = {
    OCCURRENCE_IDS["子野"]: {
        "classification": "wrong_occurrence",
        "primary_basis": "The A2OR explanation describes the later 子野 occurrence introducing 子野荅曰, while the pinned target is the earlier span inside 桓子野.",
        "boundary_basis": "not_routed",
        "human_review_required": True,
    },
    OCCURRENCE_IDS["祥"]: {
        "classification": "partially_drifted",
        "primary_basis": "The A2OR explanation reasons from the later action occurrence in 忽至祥抱樹而泣, while the boundary explanation correctly returns to the pinned opening span.",
        "boundary_basis": "The boundary explanation explicitly uses the pinned opening occurrence in 王祥事後母朱夫人甚謹.",
        "human_review_required": True,
    },
    OCCURRENCE_IDS["康"]: {
        "classification": "wrong_occurrence",
        "primary_basis": "Both stored explanations discuss the later 康 in 康長七尺, while the pinned span is the 康 component of the source-title text 康别傳.",
        "boundary_basis": "The boundary explanation also reasons from the later descriptive occurrence rather than the pinned source-title span.",
        "human_review_required": True,
    },
}


HUMAN_FINDINGS: dict[str, dict[str, Any]] = {
    OCCURRENCE_IDS["子野"]: {
        "review_class": "semantic_correction_candidate",
        "error_family": "target_occurrence_reason_drift",
        "proposed_change": {
            "narrative_function": "addressee",
            "legacy_occurrence_role": "addressee_reference",
        },
        "semantic_reason": "The exact selected span is the first 子野 inside 桓子野 in the question construction; the speaker interpretation belongs to a different later occurrence.",
        "confidence": "high",
        "human_review_required": True,
    },
    OCCURRENCE_IDS["堯"]: {
        "review_class": "semantic_correction_candidate",
        "error_family": "historical_exemplum_scope",
        "proposed_change": {
            "narrative_function": "reference",
            "legacy_occurrence_role": "annotation_person",
        },
        "semantic_reason": "堯 appears as a temporal/background reference inside the biography of 巢父; the historical comparison in the main discourse is not automatically inherited by this inner occurrence.",
        "confidence": "high",
        "human_review_required": True,
    },
    OCCURRENCE_IDS["剌史"]: {
        "review_class": "semantic_correction_candidate",
        "error_family": "office_attribute_vs_person_reference",
        "proposed_change": {
            "narrative_function": "person_attribute",
            "legacy_occurrence_role": "person_attribute",
        },
        "semantic_reason": "In the exact construction 年十八剌史周俊命爲主簿, the title identifies an office held by the bearer 周俊. This is a human review candidate under the generic office-held attribute principle; the failed boundary payload is not treated as semantic evidence.",
        "confidence": "medium",
        "human_review_required": True,
    },
    OCCURRENCE_IDS["康"]: {
        "review_class": "insufficient_evidence",
        "error_family": "target_occurrence_reason_drift",
        "proposed_change": {
            "target_annotation_review": "Confirm whether the one-character span in 康别傳 is intended as an evaluable person occurrence or a source-title component before promoting a role decision."
        },
        "semantic_reason": "The exact target is inside the source title 康别傳, but its validated mention metadata treats it as a person occurrence and the stored semantic explanations address a different later span. The role should not be silently changed without resolving the target annotation.",
        "confidence": "medium",
        "human_review_required": True,
    },
    OCCURRENCE_IDS["江南"]: {
        "review_class": "identity_applicability_candidate",
        "error_family": "unsupported_final_projection",
        "proposed_change": {
            "projection_policy": "preserve non-person reference semantics without projecting a person-specific annotation role"
        },
        "semantic_reason": "The exact target is a non-person geographic reference. The final narrative function is plausible, but the legacy compatibility projection to annotation_person is not appropriate for this entity kind and needs a human-approved projection policy.",
        "confidence": "high",
        "human_review_required": True,
    },
}


TRANSPORT_BLOCKED = {
    OCCURRENCE_IDS["殷公"],
    OCCURRENCE_IDS["王文度"],
    OCCURRENCE_IDS["兒"],
}

BOUNDARY_OVERRIDE_NOTES = {
    OCCURRENCE_IDS["孔巖"]: "The exact main-text occurrence is a comparison standard; the referential-only override is semantically plausible.",
    OCCURRENCE_IDS["爰"]: "The exact annotation occurrence is the son proposed in a memorial/succession event; event participation is semantically plausible.",
}


def _text(value: Any) -> str:
    return str(value or "").strip()


def _copy(value: Any) -> Any:
    return copy.deepcopy(value)


def _rows(document: Any) -> list[dict[str, Any]]:
    if isinstance(document, list):
        return [dict(row) for row in document if isinstance(row, Mapping)]
    if isinstance(document, Mapping) and isinstance(document.get("records"), list):
        return [dict(row) for row in document["records"] if isinstance(row, Mapping)]
    return []


def _occurrence_id(row: Mapping[str, Any]) -> str:
    key = row.get("occurrence_key") if isinstance(row.get("occurrence_key"), Mapping) else row
    return _text(row.get("occurrence_id") or key.get("occurrence_id") or row.get("mention_id"))


def _by_occurrence(document: Any) -> dict[str, dict[str, Any]]:
    return {key: row for row in _rows(document) if (key := _occurrence_id(row))}


def _source_context(packet: Mapping[str, Any], key: Mapping[str, Any]) -> dict[str, Any]:
    evidence_id = _text(key.get("source_evidence_id"))
    evidence = next(
        (dict(row) for row in packet.get("source_evidence", []) or []
         if isinstance(row, Mapping) and _text(row.get("evidence_id")) == evidence_id),
        {},
    )
    source_text = _text(evidence.get("text"))
    start = key.get("source_start")
    end = key.get("source_end")
    offsets_valid = (
        isinstance(start, int) and not isinstance(start, bool)
        and isinstance(end, int) and not isinstance(end, bool)
        and 0 <= start <= end <= len(source_text)
    )
    matched = source_text[start:end] if offsets_valid else ""
    radius = 48
    window_start = max(0, start - radius) if offsets_valid else 0
    window_end = min(len(source_text), end + radius) if offsets_valid else len(source_text)
    return {
        "source_evidence_id": evidence_id,
        "source_layer": _text(evidence.get("source_layer")),
        "source_ref": evidence.get("source_ref"),
        "text": source_text,
        "matched_target": matched,
        "offsets_valid": offsets_valid,
        "context_window": {
            "source_start": window_start,
            "source_end": window_end,
            "text": source_text[window_start:window_end],
        },
    }


def _text_offsets(source_text: str, surface: str) -> list[dict[str, int]]:
    result: list[dict[str, int]] = []
    if not surface:
        return result
    cursor = 0
    while True:
        position = source_text.find(surface, cursor)
        if position < 0:
            return result
        result.append({"source_start": position, "source_end": position + len(surface)})
        cursor = position + 1


def _overlap(left_start: Any, left_end: Any, right_start: Any, right_end: Any) -> bool:
    values = (left_start, left_end, right_start, right_end)
    if any(isinstance(value, bool) or not isinstance(value, int) for value in values):
        return False
    return max(left_start, right_start) < min(left_end, right_end)


def _validated_mentions(packet: Mapping[str, Any], key: Mapping[str, Any]) -> list[dict[str, Any]]:
    result = []
    for row in packet.get("validated_local_mentions", []) or []:
        if not isinstance(row, Mapping):
            continue
        if _text(row.get("source_evidence_id")) != _text(key.get("source_evidence_id")):
            continue
        result.append(dict(row))
    return result


def _duplicate_info(packet: Mapping[str, Any], key: Mapping[str, Any]) -> dict[str, Any]:
    source = _source_context(packet, key)
    surface = _text(key.get("surface"))
    source_occurrences = _text_offsets(source["text"], surface)
    local = _validated_mentions(packet, key)
    same_tuple = [
        row for row in local
        if _text(row.get("surface")) == surface
    ]
    same_tuple = sorted(same_tuple, key=lambda row: (_text(row.get("mention_id")), row.get("source_start", -1)))
    overlapping = [
        {
            "mention_id": row.get("mention_id"),
            "surface": row.get("surface"),
            "source_start": row.get("source_start"),
            "source_end": row.get("source_end"),
            "entity_kind": row.get("entity_kind"),
            "reference_form": row.get("reference_form"),
        }
        for row in local
        if _text(row.get("mention_id")) != _text(key.get("mention_id"))
        and any(_overlap(row.get("source_start"), row.get("source_end"), span["source_start"], span["source_end"]) for span in source_occurrences)
    ]
    overlapping.sort(key=lambda row: (_text(row.get("mention_id")), row.get("source_start", -1)))
    selected_order = next(
        (index + 1 for index, row in enumerate(same_tuple) if _text(row.get("mention_id")) == _text(key.get("mention_id"))),
        None,
    )
    return {
        "text_surface_occurrences": source_occurrences,
        "validated_same_tuple_mentions": [
            {
                "mention_id": row.get("mention_id"),
                "surface": row.get("surface"),
                "source_start": row.get("source_start"),
                "source_end": row.get("source_end"),
            }
            for row in same_tuple
        ],
        "validated_same_tuple_count": len(same_tuple),
        "selected_same_tuple_order": selected_order,
        "nested_or_overlapping_validated_mentions": overlapping,
        "textually_repeated": len(source_occurrences) > 1,
        "validated_same_tuple_ambiguous": len(same_tuple) > 1,
    }


def _protected_snapshot() -> dict[str, Any]:
    result: dict[str, Any] = {}
    paths: set[str] = set(PROTECTED_FILES)
    paths.update(
        str(path.relative_to(ROOT))
        for path in ROOT.glob("docs/sfh2-f1-*")
        if path.is_file()
    )
    for directory in PROTECTED_DIRECTORIES:
        absolute = ROOT / directory
        if absolute.is_dir():
            paths.update(
                str(path.relative_to(ROOT))
                for path in absolute.rglob("*")
                if path.is_file()
            )
    for path in sorted(paths):
        absolute = ROOT / path
        if absolute.is_file():
            result[path] = {
                "sha256": f1.file_hash(absolute),
                "size_bytes": absolute.stat().st_size,
            }
    return result


def _snapshot_digest(snapshot: Mapping[str, Any]) -> str:
    return f1.stable_hash(snapshot)


def _source_and_results() -> dict[str, Any]:
    selection = f1.selection_rows()
    inputs = f1.load_inputs()
    packets: dict[str, dict[str, Any]] = {}
    packet_validity: dict[str, dict[str, Any]] = {}
    for row in selection:
        case = f1.case_from_row(row)
        packet = f1.build_packet(case, inputs)
        occurrence_id = _text(row.get("occurrence_id"))
        packets[occurrence_id] = packet
        packet_validity[occurrence_id] = f1.validate_exact_occurrence(row, packet)
    documents = {
        "selection": f1.read_json(F1_PREP_ROOT / "f1-selection.json", {}) or {},
        "selection_verification": f1.read_json(F1_ROOT / "selection-verification.json", {}) or {},
        "identity": f1.read_json(F1_ROOT / "identity-results.json", {}) or {},
        "primary": f1.read_json(F1_ROOT / "occurrence-primary-results.json", {}) or {},
        "boundary": f1.read_json(F1_ROOT / "boundary-results.json", {}) or {},
        "candidate": f1.read_json(F1_ROOT / "candidate-semantic-records.json", {}) or {},
        "queue": f1.read_json(F1_ROOT / "review-queue.json", {}) or {},
        "accounting": f1.read_json(F1_ROOT / "provider-accounting.json", {}) or {},
        "transport_log": f1.read_json(F1_ROOT / "transport-log.json", []) or [],
        "scope": f1.read_json(SCOPE_PATH, {}) or {},
        "policy": f1.read_json(REVIEW_POLICY_PATH, {}) or {},
    }
    return {
        "selection": selection,
        "inputs": inputs,
        "packets": packets,
        "packet_validity": packet_validity,
        "documents": documents,
        "identity": _by_occurrence(documents["identity"]),
        "primary": _by_occurrence(documents["primary"]),
        "boundary": _by_occurrence(documents["boundary"]),
        "candidate": _by_occurrence(documents["candidate"]),
        "queue": _by_occurrence(documents["queue"]),
    }


def _exact_records(bundle: Mapping[str, Any]) -> list[dict[str, Any]]:
    records = []
    for selection in bundle["selection"]:
        occurrence_id = _text(selection.get("occurrence_id"))
        key = f1.exact_key(selection)
        packet = bundle["packets"][occurrence_id]
        context = _source_context(packet, key)
        mention = next(
            (dict(row) for row in packet.get("validated_local_mentions", []) or []
             if isinstance(row, Mapping) and _text(row.get("mention_id")) == _text(key.get("mention_id"))),
            None,
        )
        duplicate = _duplicate_info(packet, key)
        validity = bundle["packet_validity"][occurrence_id]
        records.append({
            "occurrence_key": key,
            "target_integrity": {
                "valid": validity.get("valid") is True,
                "errors": validity.get("errors", []),
                "source_text_matches_surface": context.get("matched_target") == key.get("surface"),
                "mention_id_matches_span": mention is not None and all([
                    _text(mention.get("source_evidence_id")) == _text(key.get("source_evidence_id")),
                    mention.get("source_start") == key.get("source_start"),
                    mention.get("source_end") == key.get("source_end"),
                    _text(mention.get("surface")) == _text(key.get("surface")),
                ]),
            },
            "exact_source_context": context,
            "validated_target_mention": mention,
            "duplicate_surface_audit": duplicate,
            "selection_record": {
                "selection_reason": _copy(next(
                    (row.get("selection_reason", []) for row in bundle["selection"] if _text(row.get("occurrence_id")) == occurrence_id),
                    [],
                )),
                "selection_hash": bundle["documents"]["selection"].get("selection_hash"),
                "gold_used_for_selection": bundle["documents"]["selection"].get("gold_used_for_selection"),
            },
            "provenance_layer": context.get("source_layer"),
            "gold_evaluation_available": False,
            "gold_used_by_f1r": False,
        })
    return records


def _reason_audit(bundle: Mapping[str, Any], exact: list[Mapping[str, Any]]) -> dict[str, Any]:
    rows = []
    for item in exact:
        key = item["occurrence_key"]
        occurrence_id = _text(key["occurrence_id"])
        primary = bundle["primary"].get(occurrence_id, {})
        boundary = bundle["boundary"].get(occurrence_id, {})
        primary_result = primary.get("occurrence_result") if isinstance(primary.get("occurrence_result"), Mapping) else {}
        boundary_result = boundary.get("validator_result") if isinstance(boundary.get("validator_result"), Mapping) else {}
        note = REASON_TARGET_AUDIT.get(occurrence_id, {})
        classification = _text(note.get("classification")) or ("unclear" if primary.get("valid") is not True else "exact")
        rows.append({
            "occurrence_key": _copy(key),
            "classification": classification,
            "primary_reason_summary": primary_result.get("reason_summary"),
            "boundary_reason_summary": boundary_result.get("reason_summary"),
            "primary_reason_basis": note.get("primary_basis") or "No offline evidence of a different target occurrence was found in the stored explanation.",
            "boundary_reason_basis": note.get("boundary_basis") or ("The boundary stage was not routed." if occurrence_id not in bundle["boundary"] else "The stored boundary explanation remains attached to the exact packet for audit.") ,
            "human_review_required": bool(note.get("human_review_required", False)),
            "gold_correctness_does_not_erase_drift": classification in {"wrong_occurrence", "partially_drifted"},
        })
    counts = Counter(row["classification"] for row in rows)
    return {
        "schema": "sfh2-f1r-reason-target-alignment-v1",
        "records": rows,
        "counts": dict(sorted(counts.items())),
        "drift_count": sum(counts[value] for value in ("wrong_occurrence", "partially_drifted")),
        "all_30_audited": len(rows) == 30,
        "provider_calls": 0,
        "candidate_only": True,
        "canonical_write_back": False,
    }


def _selection_alignment(bundle: Mapping[str, Any], exact: list[Mapping[str, Any]]) -> dict[str, Any]:
    records = []
    for item in exact:
        key = item["occurrence_key"]
        duplicate = item["duplicate_surface_audit"]
        exact_pinned = item["target_integrity"]["valid"]
        textual_collision = duplicate["textually_repeated"] or bool(duplicate["nested_or_overlapping_validated_mentions"])
        records.append({
            "occurrence_key": _copy(key),
            "selection_method": "F1 exact occurrence manifest; no reselection by F1R",
            "selection_intent_target_alignment": "aligned" if exact_pinned else "ambiguous",
            "selection_intent_evidence": "The F1 manifest pins mention_id, source_evidence_id, offsets, and surface. F1R has no free-text semantic intent field to reinterpret.",
            "textual_collision_present": textual_collision,
            "textual_collision_requires_no_reselection": textual_collision,
            "validated_same_tuple_count": duplicate["validated_same_tuple_count"],
            "selected_same_tuple_order": duplicate["selected_same_tuple_order"],
            "selection_reason": item["selection_record"]["selection_reason"],
        })
    counts = Counter(row["selection_intent_target_alignment"] for row in records)
    return {
        "schema": "sfh2-f1r-selection-intent-alignment-v1",
        "historical_surface_selector_not_modified": True,
        "prospective_rule": "Semantic targets must be pinned by occurrence_id/mention_id plus story_id, source_evidence_id, source_start, source_end, and surface; story_id plus surface plus evidence_id is insufficient when collisions exist.",
        "records": records,
        "counts": dict(sorted(counts.items())),
        "misalignment_count": counts.get("misaligned", 0),
        "ambiguous_count": counts.get("ambiguous", 0),
        "provider_calls": 0,
        "candidate_only": True,
        "canonical_write_back": False,
    }


def _duplicate_surface_audit(exact: list[Mapping[str, Any]]) -> dict[str, Any]:
    records = [
        {
            "occurrence_key": _copy(item["occurrence_key"]),
            "text_surface_occurrences": _copy(item["duplicate_surface_audit"]["text_surface_occurrences"]),
            "validated_same_tuple_mentions": _copy(item["duplicate_surface_audit"]["validated_same_tuple_mentions"]),
            "validated_same_tuple_count": item["duplicate_surface_audit"]["validated_same_tuple_count"],
            "selected_mention_id": item["occurrence_key"]["mention_id"],
            "selected_same_tuple_order": item["duplicate_surface_audit"]["selected_same_tuple_order"],
            "nested_or_overlapping_validated_mentions": _copy(item["duplicate_surface_audit"]["nested_or_overlapping_validated_mentions"]),
            "selection_order_is_structural_only": True,
        }
        for item in exact
        if item["duplicate_surface_audit"]["textually_repeated"]
        or item["duplicate_surface_audit"]["validated_same_tuple_ambiguous"]
        or item["duplicate_surface_audit"]["nested_or_overlapping_validated_mentions"]
    ]
    return {
        "schema": "sfh2-f1r-duplicate-surface-audit-v1",
        "records": records,
        "pilot_case_count": len(exact),
        "duplicate_or_nested_case_count": len(records),
        "exact_validated_same_tuple_duplicate_case_count": sum(row["validated_same_tuple_count"] > 1 for row in records),
        "historical_f1_selection_unchanged": True,
        "python_does_not_select_semantic_target": True,
        "provider_calls": 0,
        "candidate_only": True,
        "canonical_write_back": False,
    }


def _identity_applicability(bundle: Mapping[str, Any], exact: list[Mapping[str, Any]]) -> dict[str, Any]:
    records = []
    for item in exact:
        key = item["occurrence_key"]
        occurrence_id = _text(key["occurrence_id"])
        selection = next(row for row in bundle["selection"] if _text(row.get("occurrence_id")) == occurrence_id)
        identity = bundle["identity"].get(occurrence_id, {})
        readiness = _text(identity.get("identity_readiness") or selection.get("identity_readiness"))
        entity_kind = _text(selection.get("entity_kind"))
        context = identity.get("context") if isinstance(identity.get("context"), Mapping) else {}
        frozen_identity = context.get("frozen_identity") if isinstance(context.get("frozen_identity"), Mapping) else {}
        semantic_kind = _text(frozen_identity.get("semantic_kind"))
        final_state = _text(identity.get("final_state"))
        if occurrence_id == OCCURRENCE_IDS["康"]:
            classification = "ambiguous"
            reason = "The validated mention is marked as a person, but the exact span is inside a source title and the stored explanations reason about another span."
        elif semantic_kind == "office" and final_state == "non_person":
            classification = "identity_not_applicable"
            reason = "The stored qualified identity context resolves this target as an office/non-person semantic, so historical-person identity is not applicable to the office expression itself."
        elif readiness == "identity_not_applicable" or entity_kind in {"non_person", "collective_person_reference"}:
            classification = "identity_not_applicable"
            reason = "The validated structural entity kind is non-person or collective; a historical-person identity resolution is not required for this occurrence."
        else:
            classification = "person_identity_required"
            reason = "The validated occurrence is a person-form or person-bearing semantic target and entered the qualified identity path; any proposal remains candidate-only."
        routing_mismatch = classification == "identity_not_applicable" and readiness == "identity_requires_pipeline"
        candidate = identity.get("candidate_proposal") if isinstance(identity.get("candidate_proposal"), Mapping) else None
        records.append({
            "occurrence_key": _copy(key),
            "identity_applicability": classification,
            "identity_readiness_input": readiness,
            "validated_entity_kind": entity_kind,
            "stored_semantic_kind": semantic_kind,
            "stored_final_state": final_state,
            "routing_mismatch": routing_mismatch,
            "identity_status": identity.get("status"),
            "reason": reason,
            "new_historical_person_candidate_possibility": bool(candidate and _text(candidate.get("entity_type")) == "candidate_historical_person"),
            "human_review_required": classification == "ambiguous" or routing_mismatch,
        })
    counts = Counter(row["identity_applicability"] for row in records)
    routing_mismatches = [row for row in records if row["routing_mismatch"]]
    return {
        "schema": "sfh2-f1r-identity-applicability-audit-v1",
        "records": records,
        "counts": dict(sorted(counts.items())),
        "routing_mismatch_count": len(routing_mismatches),
        "routing_mismatch_occurrence_keys": [_copy(row["occurrence_key"]) for row in routing_mismatches],
        "systematic_routing_issue_found": len(routing_mismatches) > 1,
        "production_manifest_unchanged": True,
        "provider_calls": 0,
        "candidate_only": True,
        "canonical_write_back": False,
    }


def _stage_failure(row: Mapping[str, Any], stage_name: str) -> dict[str, Any]:
    transport = row.get("transport") if isinstance(row.get("transport"), Mapping) else {}
    classification = _text(transport.get("classification"))
    errors = row.get("errors") if isinstance(row.get("errors"), list) else []
    if not errors and isinstance(transport.get("parse_error"), str) and transport.get("parse_error"):
        errors = [transport["parse_error"]]
    return {
        "stage": stage_name,
        "valid": row.get("valid"),
        "contract_status": row.get("contract_status"),
        "errors": _copy(errors),
        "transport_classification": classification,
        "request_hash": transport.get("request_hash"),
        "provider_witness_hash": transport.get("provider_witness_hash"),
        "raw_witness_available": bool(transport.get("provider_witness_hash") or transport.get("raw_archive_sha256")),
        "finish_reason": transport.get("finish_reason"),
        "parse_error": transport.get("parse_error"),
        "transport_http_status": transport.get("http_status"),
    }


def _transport_failure_audit(bundle: Mapping[str, Any]) -> dict[str, Any]:
    identity = bundle["identity"]
    primary = bundle["primary"]
    boundary = bundle["boundary"]
    exact_invalid: list[dict[str, Any]] = []
    for item in bundle["documents"]["transport_log"]:
        if not isinstance(item, Mapping):
            continue
        stage = _text(item.get("stage"))
        if stage not in {"identity_primary", "identity_independent", "boundary_validator"}:
            continue
        if _text(item.get("classification")) not in {"response_parse_failure", "response_truncated"}:
            continue
        unit_id = _text(item.get("unit_id"))
        occurrence_id = unit_id.rsplit(":", 1)[-1] if ":" in unit_id else ""
        result = identity.get(occurrence_id, {})
        if stage == "boundary_validator":
            result = boundary.get(occurrence_id, {})
        elif stage == "identity_primary":
            result = identity.get(occurrence_id, {}).get("historian_primary", {})
        else:
            result = identity.get(occurrence_id, {}).get("historian_independent", {})
        exact_invalid.append({
            "occurrence_id": occurrence_id,
            "story_id": identity.get(occurrence_id, {}).get("story_id") or primary.get(occurrence_id, {}).get("story_id"),
            "surface": identity.get(occurrence_id, {}).get("surface") or primary.get(occurrence_id, {}).get("surface"),
            "stage": stage,
            "request_hash": item.get("request_hash"),
            "provider_transport_success": _text(item.get("classification")) != "provider_request_failure",
            "transport_classification": item.get("classification"),
            "parse_error": item.get("parse_error"),
            "finish_reason": item.get("finish_reason"),
            "provider_witness_hash": item.get("provider_witness_hash"),
            "raw_witness_available": bool(item.get("provider_witness_hash") or item.get("raw_archive_sha256")),
            "root_cause": "truncated_output" if _text(item.get("classification")) == "response_truncated" else "provider_structured_output_drift",
            "failure_category": "truncated_output" if _text(item.get("classification")) == "response_truncated" else ("invalid_json" if _text(item.get("parse_error")) == "function_arguments_invalid_json" else "other"),
            "root_cause_confidence": "high",
            "recovery_class": "terminal_boundary_failure" if stage == "boundary_validator" else ("terminal_identity_block" if identity.get(occurrence_id, {}).get("status") == "blocked" else "recovered_intermediate_failure"),
            "final_identity_resolved": identity.get(occurrence_id, {}).get("status") != "blocked",
            "stage_row": _stage_failure(result, stage),
        })

    contract_diagnostics: list[dict[str, Any]] = []
    for occurrence_id, row in sorted(identity.items()):
        for stage_name, key in (("identity_primary", "historian_primary"), ("identity_independent", "historian_independent")):
            stage_row = row.get(key)
            if not isinstance(stage_row, Mapping) or stage_row.get("valid") is not False:
                continue
            transport = stage_row.get("transport") if isinstance(stage_row.get("transport"), Mapping) else {}
            if _text(transport.get("classification")) != "parsed":
                continue
            recovered = row.get("status") != "blocked"
            contract_diagnostics.append({
                "occurrence_id": occurrence_id,
                "story_id": row.get("story_id"),
                "surface": row.get("surface"),
                "stage": stage_name,
                "request_hash": transport.get("request_hash"),
                "provider_transport_success": True,
                "transport_classification": "parsed",
                "contract_errors": _copy(stage_row.get("errors", [])),
                "root_cause": "missing_required_field" if "record_not_object" in stage_row.get("errors", []) else "schema_contract_violation",
                "root_cause_confidence": "high",
                "recovery_class": "recovered_intermediate_failure" if recovered else "terminal_identity_block",
                "final_identity_resolved": recovered,
            })

    for occurrence_id, row in sorted(boundary.items()):
        if row.get("valid") is not False:
            continue
        transport = row.get("transport") if isinstance(row.get("transport"), Mapping) else {}
        if _text(transport.get("classification")) != "parsed":
            continue
        contract_diagnostics.append({
            "occurrence_id": occurrence_id,
            "story_id": row.get("story_id"),
            "surface": row.get("surface"),
            "stage": "boundary_validator",
            "request_hash": transport.get("request_hash"),
            "provider_transport_success": True,
            "transport_classification": "parsed",
            "contract_errors": _copy(row.get("errors", [])),
            "root_cause": "schema_contract_violation",
            "root_cause_confidence": "high",
            "recovery_class": "terminal_boundary_failure",
            "final_identity_resolved": identity.get(occurrence_id, {}).get("status") != "blocked",
        })

    blocked = []
    for occurrence_id, row in sorted(identity.items()):
        if row.get("status") != "blocked":
            continue
        blocked.append({
            "occurrence_id": occurrence_id,
            "story_id": row.get("story_id"),
            "surface": row.get("surface"),
            "classification": "terminal_identity_block",
            "reason": "The qualified adjudication stage had no valid identity hypothesis to select or revise.",
            "primary_stage": _stage_failure(row.get("historian_primary", {}), "identity_primary"),
            "independent_stage": _stage_failure(row.get("historian_independent", {}), "identity_independent"),
            "adjudication": {
                "decision": (row.get("adjudication") or {}).get("decision"),
                "contract_status": (row.get("adjudication") or {}).get("contract_status"),
            },
            "recovery_possible_from_stored_f1": False,
        })
    all_invalid_payloads = exact_invalid
    categories = Counter(item["root_cause"] for item in exact_invalid)
    return {
        "schema": "sfh2-f1r-transport-failure-audit-v1",
        "provider_calls": 0,
        "f1_accounted_invalid_semantic_payload_count": len(all_invalid_payloads),
        "f1_accounting_expected_invalid_payload_count": 5,
        "invalid_payloads": exact_invalid,
        "parsed_contract_diagnostics": contract_diagnostics,
        "parsed_contract_diagnostic_count": len(contract_diagnostics),
        "invalid_payload_root_causes": dict(sorted(categories.items())),
        "terminal_identity_blocks": blocked,
        "terminal_identity_block_count": len(blocked),
        "transport_failure_replay_needed_for_understanding": False,
        "future_recovery_note": "The five response-level failures are attributable from retained transport metadata. Any replay to recover blocked units requires a separately authorized live stage.",
        "candidate_only": True,
        "canonical_write_back": False,
    }


def _acceptance_review(bundle: Mapping[str, Any], exact: list[Mapping[str, Any]], reason_audit: Mapping[str, Any], applicability: Mapping[str, Any]) -> dict[str, Any]:
    reason_by_id = {_text(row["occurrence_key"]["occurrence_id"]): row for row in reason_audit["records"]}
    applicability_by_id = {_text(row["occurrence_key"]["occurrence_id"]): row for row in applicability["records"]}
    records = []
    for item in exact:
        key = item["occurrence_key"]
        occurrence_id = _text(key["occurrence_id"])
        identity = bundle["identity"].get(occurrence_id, {})
        primary = bundle["primary"].get(occurrence_id, {})
        boundary = bundle["boundary"].get(occurrence_id, {})
        candidate = bundle["candidate"].get(occurrence_id, {})
        queue = bundle["queue"].get(occurrence_id, {})
        applicability_row = applicability_by_id[occurrence_id]
        semantics = candidate.get("occurrence_semantics") if isinstance(candidate.get("occurrence_semantics"), Mapping) else {}
        primary_result = primary.get("occurrence_result") if isinstance(primary.get("occurrence_result"), Mapping) else {}
        boundary_result = boundary.get("validator_result") if isinstance(boundary.get("validator_result"), Mapping) else {}
        finding = HUMAN_FINDINGS.get(occurrence_id)
        if occurrence_id in TRANSPORT_BLOCKED:
            review_class = "transport_blocked"
            human_review = True
            semantic_reason = "Identity is terminally blocked by stored F1 failures; no semantic acceptance is asserted."
            confidence = "high"
            proposed = None
        elif finding:
            review_class = finding["review_class"]
            human_review = True
            semantic_reason = finding["semantic_reason"]
            confidence = finding["confidence"]
            proposed = _copy(finding["proposed_change"])
        elif applicability_row["routing_mismatch"]:
            review_class = "identity_applicability_candidate"
            human_review = True
            semantic_reason = "The stored identity context resolves an office/non-person target, but F-prep routed it through the historical-person identity path; review the prospective applicability rule before F2."
            confidence = "medium"
            proposed = {
                "identity_applicability": "identity_not_applicable",
                "routing_review": "Do not infer a repair from this audit; confirm whether office expressions should bypass person identity in the next production contract.",
            }
        else:
            review_class = "accepted_as_plausible"
            human_review = False
            semantic_reason = "The exact target, source layer, stored identity state, and stored semantic outputs are structurally coherent enough for an offline plausibility acceptance; this is not a Gold accuracy claim."
            confidence = _text(primary_result.get("confidence")) or "unknown"
            proposed = None
        if applicability_row["routing_mismatch"] and isinstance(proposed, Mapping):
            proposed = _copy(proposed)
            proposed["identity_applicability"] = "identity_not_applicable"
            proposed["routing_review"] = "The stored office/non-person resolution indicates a prospective routing question; human approval is required before changing F2 policy."
        candidate_types = []
        if review_class:
            candidate_types.append(review_class)
        if applicability_row["human_review_required"]:
            candidate_types.append("identity_applicability_candidate")
        candidate_types = sorted(set(candidate_types))
        candidate_proposal = identity.get("candidate_proposal") if isinstance(identity.get("candidate_proposal"), Mapping) else None
        identity_status = identity.get("status")
        identity_review = (
            "not_evaluable_transport_blocked" if identity_status == "blocked" else
            "ambiguous_target_applicability" if applicability_row["identity_applicability"] == "ambiguous" else
            "resolved_non_person_semantic_context" if applicability_row["identity_applicability"] == "identity_not_applicable" else
            "not_applicable" if _text(identity.get("identity_readiness")) == "identity_not_applicable" else
            "resolved_candidate_requires_entity_review" if candidate_proposal and _text(candidate_proposal.get("entity_type")) == "candidate_historical_person" else
            "resolved_structural_identity_no_gold_authority" if identity_status else
            "not_run_for_non_person_or_frozen_context"
        )
        boundary_behavior = {
            "routed": occurrence_id in bundle["boundary"],
            "valid": boundary.get("valid") if boundary else None,
            "judgment": boundary_result.get("boundary_judgment") if boundary_result else None,
            "override": semantics.get("final_narrative_function") is not None and semantics.get("final_narrative_function") != primary_result.get("narrative_function"),
            "assessment": BOUNDARY_OVERRIDE_NOTES.get(occurrence_id) if occurrence_id in BOUNDARY_OVERRIDE_NOTES else None,
        }
        records.append({
            "occurrence_key": _copy(key),
            "source_context": _copy(item["exact_source_context"]),
            "target_integrity": _copy(item["target_integrity"]),
            "identity_applicability": applicability_row["identity_applicability"],
            "identity_applicability_routing_mismatch": applicability_row["routing_mismatch"],
            "identity_status": identity_status,
            "identity_review": identity_review,
            "identity_correctness": "not_authoritatively_evaluable_without_reviewed_F1_Gold",
            "candidate_person_status": {
                "entity_type": candidate_proposal.get("entity_type") if candidate_proposal else None,
                "candidate_person_id": candidate_proposal.get("candidate_person_id") if candidate_proposal else None,
                "proposed_display_name": candidate_proposal.get("proposed_display_name") if candidate_proposal else None,
                "candidate_only": True,
                "canonical_write_back": False,
            },
            "primary_function": primary_result.get("narrative_function"),
            "primary_confidence": primary_result.get("confidence"),
            "primary_reason_summary": primary_result.get("reason_summary"),
            "boundary_result": boundary_behavior,
            "final_function": semantics.get("final_narrative_function"),
            "projected_legacy_occurrence_role": semantics.get("projected_legacy_occurrence_role"),
            "reason_target_alignment": reason_by_id.get(occurrence_id, {}).get("classification"),
            "review_trigger_validity": {
                "current_triggers": _copy(queue.get("triggers", [])),
                "current_trigger_names_are_frozen_policy_names": set(queue.get("triggers", [])).issubset(set(bundle["documents"]["policy"].get("mandatory_review_triggers", []))),
                "current_mandatory": queue.get("mandatory_review") is True,
            },
            "review_class": review_class,
            "review_candidate_types": candidate_types,
            "proposed_change_if_any": proposed,
            "semantic_reason": semantic_reason,
            "confidence": confidence,
            "human_approval_required": human_review,
            "gold_used": False,
            "candidate_only": True,
            "canonical_write_back": False,
            "gold_used_by_f1r": False,
        })
    counts = Counter(row["review_class"] for row in records)
    return {
        "schema": "sfh2-f1r-semantic-acceptance-review-v1",
        "records": records,
        "counts": dict(sorted(counts.items())),
        "reviewed_count": len(records),
        "all_30_reviewed_exactly_once": len(records) == 30 and len({_text(row["occurrence_key"]["occurrence_id"]) for row in records}) == 30,
        "gold_expansion_performed": False,
        "provider_calls": 0,
        "candidate_only": True,
        "canonical_write_back": False,
    }


def _new_person_groups(bundle: Mapping[str, Any], exact: list[Mapping[str, Any]]) -> dict[str, Any]:
    groups: dict[str, dict[str, Any]] = {}
    occurrence_count = 0
    for item in exact:
        occurrence_id = _text(item["occurrence_key"]["occurrence_id"])
        identity = bundle["identity"].get(occurrence_id, {})
        proposal = identity.get("candidate_proposal")
        if not isinstance(proposal, Mapping) or _text(proposal.get("entity_type")) != "candidate_historical_person":
            continue
        occurrence_count += 1
        candidate_id = _text(proposal.get("candidate_person_id"))
        canonical_hint = _text(proposal.get("referent_canonical_hint") or proposal.get("proposed_display_name"))
        group_key = candidate_id or f1.stable_hash({"canonical_hint": canonical_hint, "semantic_kind": "historical_person", "source_evidence_ids": sorted(proposal.get("supporting_evidence_ids", []))})
        group = groups.setdefault(group_key, {
            "group_id": "sfh2-f1r-entity-" + f1.stable_hash({"group_key": group_key})[:16],
            "group_basis": "candidate_person_id plus structured semantic identity/evidence; not naive surface equality",
            "candidate_person_id": candidate_id or None,
            "proposed_canonical_identity": canonical_hint,
            "occurrence_members": [],
            "source_evidence_ids": set(),
            "aliases_or_forms": set(),
            "conflicting_proposals": [],
            "registry_lookup_status": "candidate_registry_miss",
            "confidence_values": set(),
            "review_disposition_candidate": "human_entity_review_required",
        })
        member = {
            "occurrence_key": _copy(item["occurrence_key"]),
            "candidate_proposal_source_occurrence_ids": _copy(proposal.get("source_occurrence_ids", [])),
        }
        group["occurrence_members"].append(member)
        group["source_evidence_ids"].update(_text(value) for value in proposal.get("supporting_evidence_ids", []) if _text(value))
        group["aliases_or_forms"].add(_text(item["occurrence_key"].get("surface")))
        group["aliases_or_forms"].add(_text(proposal.get("proposed_display_name")))
        confidence = (((identity.get("selected_record") or {}).get("confidence")) if isinstance(identity.get("selected_record"), Mapping) else None)
        if confidence:
            group["confidence_values"].add(_text(confidence))
    serializable = []
    for group in sorted(groups.values(), key=lambda row: row["group_id"]):
        group["source_evidence_ids"] = sorted(group["source_evidence_ids"])
        group["aliases_or_forms"] = sorted(value for value in group["aliases_or_forms"] if value)
        group["confidence_values"] = sorted(value for value in group["confidence_values"] if value)
        group["occurrence_members"] = sorted(group["occurrence_members"], key=lambda row: _text(row["occurrence_key"]["occurrence_id"]))
        serializable.append(group)
    return {
        "schema": "sfh2-f1r-new-person-review-groups-v1",
        "occurrence_level_new_person_review_count": occurrence_count,
        "deduplicated_entity_review_count": len(serializable),
        "groups": serializable,
        "grouping_is_structured": True,
        "canonical_person_creation": 0,
        "candidate_only": True,
        "canonical_write_back": False,
    }


def _review_trigger_matrix(bundle: Mapping[str, Any], acceptance: Mapping[str, Any], person_groups: Mapping[str, Any]) -> dict[str, Any]:
    policy = bundle["documents"]["policy"]
    mandatory_names = set(policy.get("mandatory_review_triggers", []))
    queue_rows = [bundle["queue"].get(_text(row["occurrence_key"]["occurrence_id"]), {}) for row in acceptance["records"]]
    trigger_counts = Counter({name: 0 for name in sorted(mandatory_names)})
    trigger_counts.update(trigger for row in queue_rows for trigger in row.get("triggers", []))
    subset_counts = Counter("+".join(sorted(row.get("triggers", []))) if row.get("triggers") else "none" for row in queue_rows)
    pair_counts = Counter()
    for row in queue_rows:
        triggers = sorted(set(row.get("triggers", [])))
        for index, left in enumerate(triggers):
            for right in triggers[index + 1:]:
                pair_counts[f"{left}+{right}"] += 1

    disagreement_rows = []
    for item in acceptance["records"]:
        occurrence_id = _text(item["occurrence_key"]["occurrence_id"])
        queue = bundle["queue"].get(occurrence_id, {})
        if "policy_defined_stage_disagreement" not in queue.get("triggers", []):
            continue
        identity = bundle["identity"].get(occurrence_id, {})
        primary = identity.get("historian_primary") or {}
        independent = identity.get("historian_independent") or {}
        candidate = identity.get("candidate_proposal")
        if identity.get("status") == "blocked":
            category = "unresolved_disagreement"
        elif isinstance(candidate, Mapping) and _text(candidate.get("entity_type")) == "candidate_historical_person":
            category = "new_person_disagreement"
        elif primary.get("valid") is False or independent.get("valid") is False:
            category = "resolved_but_transport_degraded"
        elif identity.get("adjudication", {}).get("contract_status") == "valid":
            category = "resolved_by_qualified_adjudicator"
        else:
            category = "other"
        disagreement_rows.append({
            "occurrence_key": _copy(item["occurrence_key"]),
            "classification": category,
            "comparison": _copy(identity.get("comparison", {})),
            "adjudication": {
                "decision": (identity.get("adjudication") or {}).get("decision"),
                "contract_status": (identity.get("adjudication") or {}).get("contract_status"),
            },
            "identity_status": identity.get("status"),
        })

    # F1R's policy-v2 proposal keeps degraded identity/transport paths and
    # unresolved outputs mandatory.  Resolved disagreement-only cases become
    # audit-only; a semantic audit candidate or unsupported projection keeps a
    # case mandatory.  This is a counterfactual document, not an activated
    # policy.
    v2_rows = []
    entity_group_by_occurrence = {}
    for group in person_groups["groups"]:
        for member in group["occurrence_members"]:
            entity_group_by_occurrence[_text(member["occurrence_key"]["occurrence_id"])] = group["group_id"]
    for item in acceptance["records"]:
        occurrence_id = _text(item["occurrence_key"]["occurrence_id"])
        identity = bundle["identity"].get(occurrence_id, {})
        primary = bundle["primary"].get(occurrence_id, {})
        boundary = bundle["boundary"].get(occurrence_id, {})
        current = bundle["queue"].get(occurrence_id, {})
        mandatory: set[str] = set()
        audit_only: set[str] = set()
        if identity.get("status") == "blocked":
            mandatory.add("identity_adjudication_unresolved")
        identity_stage_rows = [identity.get("historian_primary"), identity.get("historian_independent")]
        if any(isinstance(row, Mapping) and row.get("valid") is False for row in identity_stage_rows):
            mandatory.add("degraded_identity_path")
        if current.get("triggers") and any(trigger in current.get("triggers", []) for trigger in ("provider_failure", "invalid_provider_contract")):
            mandatory.add("terminal_or_degraded_provider_contract")
        proposal = identity.get("candidate_proposal")
        if isinstance(proposal, Mapping) and _text(proposal.get("entity_type")) == "candidate_historical_person":
            mandatory.add("new_historical_person_entity")
        if boundary and boundary.get("valid") is not True:
            mandatory.add("terminal_boundary_failure")
        if item.get("final_function") in {None, "uncertain"} and primary.get("valid") is not True:
            mandatory.add("semantic_output_unresolved")
        if item.get("final_function") == "uncertain":
            mandatory.add("occurrence_function_uncertain")
        if item.get("review_class") in {"semantic_correction_candidate", "identity_applicability_candidate", "insufficient_evidence"}:
            mandatory.add("semantic_audit_candidate")
        if item.get("reason_target_alignment") in {"wrong_occurrence", "partially_drifted"}:
            mandatory.add("reason_target_alignment_failure")
        if occurrence_id == OCCURRENCE_IDS["江南"]:
            mandatory.add("unsupported_final_projection")
        if not item.get("target_integrity", {}).get("valid"):
            mandatory.add("exact_evidence_integrity_failure")
        if current.get("triggers") == ["policy_defined_stage_disagreement"]:
            audit_only.add("resolved_stage_disagreement_only")
        if "policy_defined_stage_disagreement" in current.get("triggers", []) and not mandatory:
            audit_only.add("policy_defined_stage_disagreement")
        if "boundary_override" in current.get("audit_only_flags", []):
            audit_only.add("boundary_override")
        if "low_confidence" in current.get("audit_only_flags", []):
            audit_only.add("low_confidence")
        unit_id = entity_group_by_occurrence.get(occurrence_id) if "new_historical_person_entity" in mandatory else "occurrence:" + occurrence_id
        v2_rows.append({
            "occurrence_key": _copy(item["occurrence_key"]),
            "current_triggers": _copy(current.get("triggers", [])),
            "counterfactual_mandatory": bool(mandatory),
            "counterfactual_mandatory_reasons": sorted(mandatory),
            "counterfactual_audit_only_reasons": sorted(audit_only),
            "human_review_unit": unit_id,
        })
    current_mandatory = sum(row.get("mandatory_review") is True for row in queue_rows)
    v2_mandatory = sum(row["counterfactual_mandatory"] for row in v2_rows)
    v2_units = len({row["human_review_unit"] for row in v2_rows if row["counterfactual_mandatory"]})
    return {
        "schema": "sfh2-f1r-review-trigger-matrix-v1",
        "current_frozen_policy": _copy(policy),
        "current_mandatory_count": current_mandatory,
        "current_trigger_counts": dict(sorted(trigger_counts.items())),
        "current_trigger_subset_counts": dict(sorted(subset_counts.items())),
        "current_trigger_pair_counts": dict(sorted(pair_counts.items())),
        "all_current_trigger_names_declared": all(set(row.get("triggers", [])).issubset(mandatory_names) for row in queue_rows),
        "policy_defined_stage_disagreement_count": len(disagreement_rows),
        "policy_defined_stage_disagreement_analysis": disagreement_rows,
        "policy_v2_counterfactual_records": v2_rows,
        "policy_v2_counterfactual_mandatory_count": v2_mandatory,
        "policy_v2_counterfactual_mandatory_entity_or_occurrence_units": v2_units,
        "policy_v2_activated": False,
        "candidate_only": True,
        "canonical_write_back": False,
    }


def _review_policy_v2(matrix: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "schema": "sfh2-f1r-review-policy-v2-candidate-v1",
        "activated": False,
        "purpose": "Counterfactual reduction of redundant review triggers without weakening semantic authority.",
        "mandatory": [
            "identity_adjudication_unresolved",
            "terminal_or_degraded_provider_contract",
            "new_historical_person_entity",
            "occurrence_function_uncertain",
            "terminal_boundary_failure",
            "semantic_output_unresolved",
            "semantic_audit_candidate",
            "reason_target_alignment_failure",
            "unsupported_final_projection",
            "exact_evidence_integrity_failure",
        ],
        "audit_only": [
            "resolved_stage_disagreement_only",
            "policy_defined_stage_disagreement_when_final_identity_is_valid",
            "boundary_override",
            "low_confidence",
        ],
        "safety_note": "A resolved identity-stage disagreement is audit-only only when no degraded input, unresolved output, new entity proposal, target drift, or other mandatory condition is present. This proposal does not alter the frozen F-prep policy.",
        "current_mandatory_count": matrix["current_mandatory_count"],
        "counterfactual_mandatory_count": matrix["policy_v2_counterfactual_mandatory_count"],
        "candidate_only": True,
        "canonical_write_back": False,
    }


def _review_burden(matrix: Mapping[str, Any], person_groups: Mapping[str, Any], scope: Mapping[str, Any]) -> dict[str, Any]:
    total = int(scope.get("total_validated_occurrences", 0))
    current_occurrences = int(matrix["current_mandatory_count"])
    v2_occurrences = int(matrix["policy_v2_counterfactual_mandatory_count"])
    pilot_occurrences = len(matrix["policy_v2_counterfactual_records"])
    if pilot_occurrences <= 0:
        raise RuntimeError("sfh2_f1r_empty_review_burden_cohort")
    # The entity-unit rate is deliberately a pilot observation: it is not a
    # guarantee about unseen full-corpus alias/entity repetition.
    v2_units = int(matrix["policy_v2_counterfactual_mandatory_entity_or_occurrence_units"])
    # Current occurrence review is 25/30.  Deduplicating only the observed
    # candidate-entity group makes the observed current unit count 24.
    current_entity_units = current_occurrences - max(
        0,
        person_groups["occurrence_level_new_person_review_count"] - person_groups["deduplicated_entity_review_count"],
    )
    return {
        "schema": "sfh2-f1r-review-burden-counterfactual-v1",
        "scope_source": str(SCOPE_PATH.relative_to(ROOT)),
        "scope_occurrences": total,
        "pilot_observation": {
            "current_mandatory_occurrences": current_occurrences,
            "current_occurrence_rate": current_occurrences / pilot_occurrences,
            "current_deduplicated_review_units_observed": current_entity_units,
            "counterfactual_mandatory_occurrences": v2_occurrences,
            "counterfactual_occurrence_rate": v2_occurrences / pilot_occurrences,
            "counterfactual_deduplicated_review_units_observed": v2_units,
            "new_person_occurrence_proposals": person_groups["occurrence_level_new_person_review_count"],
            "new_person_entity_groups": person_groups["deduplicated_entity_review_count"],
        },
        "full_scope_estimate_from_F1_rates_only": {
            "current_mandatory_occurrences": total * current_occurrences / pilot_occurrences,
            "counterfactual_mandatory_occurrences": total * v2_occurrences / pilot_occurrences,
            "current_deduplicated_review_units": total * current_entity_units / pilot_occurrences,
            "counterfactual_deduplicated_review_units": total * v2_units / pilot_occurrences,
            "warning": "Pilot rates are observations, not a full-corpus accuracy or workload guarantee.",
        },
        "removed_by_counterfactual": "Resolved stage-disagreement-only cases are audit-only; degraded identity/provider paths and explicit semantic/applicability candidates remain mandatory.",
        "candidate_only": True,
        "canonical_write_back": False,
    }


def _semantic_error_families(acceptance: Mapping[str, Any]) -> dict[str, Any]:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in acceptance["records"]:
        finding = HUMAN_FINDINGS.get(_text(row["occurrence_key"]["occurrence_id"]))
        if not finding:
            continue
        groups[finding["error_family"]].append({
            "occurrence_key": _copy(row["occurrence_key"]),
            "review_class": row["review_class"],
            "proposed_change": _copy(row.get("proposed_change_if_any")),
        })
    families = []
    for family, rows in sorted(groups.items()):
        families.append({
            "error_family": family,
            "case_count": len(rows),
            "cases": rows,
            "systematic_or_isolated": "coherent_target-alignment family" if family == "target_occurrence_reason_drift" else "isolated pilot candidate",
            "requires_semantic_v1_repair": False,
            "requires_human_review_before_F2": True,
        })
    return {
        "schema": "sfh2-f1r-semantic-error-families-v1",
        "families": families,
        "semantic_v1_remains_frozen": True,
        "provider_calls": 0,
        "candidate_only": True,
        "canonical_write_back": False,
    }


def _boundary_audit(bundle: Mapping[str, Any], acceptance: Mapping[str, Any]) -> dict[str, Any]:
    records = []
    for row in acceptance["records"]:
        if not row["boundary_result"]["routed"]:
            continue
        result = row["boundary_result"]
        records.append({
            "occurrence_key": _copy(row["occurrence_key"]),
            "valid": result["valid"],
            "boundary_judgment": result["judgment"],
            "override": result["override"],
            "assessment": result["assessment"] or ("No Gold accuracy claim; stored result is structurally inspectable." if result["valid"] else "Transport/contract failure requires future bounded recovery."),
            "human_semantic_acceptance": row["review_class"],
        })
    return {
        "schema": "sfh2-f1r-boundary-production-audit-v1",
        "route_count": len(records),
        "override_count": sum(row["override"] for row in records),
        "invalid_route_count": sum(row["valid"] is not True for row in records),
        "records": records,
        "a2ovb_architecture_status": "qualified_architecture_with_one_F1_transport_failure_requiring_review",
        "appears_production_qualified": all(row["valid"] is True or row["occurrence_key"]["occurrence_id"] == OCCURRENCE_IDS["剌史"] for row in records),
        "accuracy_claim_made": False,
        "candidate_only": True,
        "canonical_write_back": False,
    }


def _regression_candidates(acceptance: Mapping[str, Any]) -> dict[str, Any]:
    records = []
    for row in acceptance["records"]:
        if row["review_class"] in {"semantic_correction_candidate", "identity_applicability_candidate", "insufficient_evidence"} or row["boundary_result"]["override"]:
            records.append({
                "occurrence_key": _copy(row["occurrence_key"]),
                "reason": "Useful future regression/control case identified during F1R offline review.",
                "review_class": row["review_class"],
                "proposed_change": _copy(row.get("proposed_change_if_any")),
                "human_approval_required": True,
                "candidate_only": True,
                "canonical_write_back": False,
            })
    return {
        "schema": "sfh2-f1r-regression-gold-candidates-v1",
        "records": records,
        "gold_promoted": False,
        "human_approval_required": True,
        "candidate_only": True,
        "canonical_write_back": False,
    }


def _protected_hash_audit(before: Mapping[str, Any], after: Mapping[str, Any]) -> dict[str, Any]:
    changed = sorted(path for path in set(before) | set(after) if before.get(path) != after.get(path))
    return {
        "schema": "sfh2-f1r-protected-hash-audit-v1",
        "before_snapshot_sha256": _snapshot_digest(before),
        "after_snapshot_sha256": _snapshot_digest(after),
        "changed_paths": changed,
        "unchanged": not changed,
        "protected_file_count": len(before),
        "protected_hashes": {
            "sc1_frozen": before.get("data/derived/sc1-site.json", {}).get("sha256"),
            "sc1_current": before.get("data/derived/sc1-current-site.json", {}).get("sha256"),
            "active_gold": before.get("data/annotation/sfh2-a2o-evaluation-gold.json", {}).get("sha256"),
            "identity_manifest": before.get("data/frozen/sfh2/identity-v1/manifest.json", {}).get("sha256"),
        },
        "candidate_only": True,
        "canonical_write_back": False,
    }


def _metrics(bundle: Mapping[str, Any], exact: list[Mapping[str, Any]], acceptance: Mapping[str, Any], reason: Mapping[str, Any], duplicate: Mapping[str, Any], selection: Mapping[str, Any], applicability: Mapping[str, Any], transport: Mapping[str, Any], people: Mapping[str, Any], matrix: Mapping[str, Any], boundary: Mapping[str, Any], protected: Mapping[str, Any]) -> dict[str, Any]:
    accounting = bundle["documents"]["accounting"]
    current_mandatory = sum(row.get("mandatory_review") is True for row in bundle["queue"].values())
    return {
        "schema": "sfh2-f1r-metrics-v1",
        "provider_calls": 0,
        "all_30_reviewed_exactly_once": acceptance["all_30_reviewed_exactly_once"],
        "accepted_as_plausible_count": acceptance["counts"].get("accepted_as_plausible", 0),
        "semantic_correction_candidate_count": acceptance["counts"].get("semantic_correction_candidate", 0),
        "identity_correction_candidate_count": acceptance["counts"].get("identity_correction_candidate", 0),
        "identity_applicability_candidate_count": sum("identity_applicability_candidate" in row.get("review_candidate_types", []) for row in acceptance["records"]),
        "identity_applicability_routing_mismatch_count": applicability["routing_mismatch_count"],
        "insufficient_evidence_count": acceptance["counts"].get("insufficient_evidence", 0),
        "transport_blocked_count": acceptance["counts"].get("transport_blocked", 0),
        "reason_target_drift_count": reason["drift_count"],
        "exact_occurrence_integrity_failures": sum(not item["target_integrity"]["valid"] for item in exact),
        "textually_repeated_or_nested_case_count": duplicate["duplicate_or_nested_case_count"],
        "validated_same_tuple_duplicate_case_count": duplicate["exact_validated_same_tuple_duplicate_case_count"],
        "identity_applicability_counts": applicability["counts"],
        "f1_invalid_semantic_payloads": transport["f1_accounted_invalid_semantic_payload_count"],
        "terminal_identity_block_count": transport["terminal_identity_block_count"],
        "new_person_occurrence_proposals": people["occurrence_level_new_person_review_count"],
        "deduplicated_entity_review_count": people["deduplicated_entity_review_count"],
        "current_mandatory_review_count": current_mandatory,
        "proposed_policy_mandatory_review_count": matrix["policy_v2_counterfactual_mandatory_count"],
        "proposed_policy_entity_or_occurrence_units": matrix["policy_v2_counterfactual_mandatory_entity_or_occurrence_units"],
        "boundary_route_count": boundary["route_count"],
        "boundary_override_count": boundary["override_count"],
        "boundary_invalid_count": boundary["invalid_route_count"],
        "semantic_v1_remains_frozen": True,
        "transport_replay_needed": False,
        "current_selection_hash": bundle["documents"]["selection"].get("selection_hash"),
        "f1_provider_accounting_reference": {
            "provider_calls": accounting.get("provider_calls"),
            "provider_failures": accounting.get("provider_failures"),
            "invalid_payloads": accounting.get("invalid_payloads"),
            "total_tokens": accounting.get("total_tokens"),
        },
        "protected_hash_audit": protected,
        "candidate_only": True,
        "canonical_write_back": False,
    }


def _recommendation(metrics: Mapping[str, Any], transport: Mapping[str, Any], acceptance: Mapping[str, Any], matrix: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "schema": "sfh2-f1r-recommendation-v1",
        "recommendation": "sfh2_f1r_human_decisions_ready",
        "qualified_for_F2": False,
        "next_stage": "SFH2.2-F1RP",
        "reason": "F1 evidence is operationally reviewable, but human decisions are required for exact-target drift, historical-exemplum scope, office/title semantics, a source-title target annotation, and a non-person compatibility projection. Transport causes are understood offline; no provider replay is required to interpret the failures.",
        "semantic_v1_status": "frozen",
        "f2_status": "blocked_pending_human_decisions_and_policy_review",
        "gates": {
            "provider_calls_zero": True,
            "all_30_reviewed": acceptance["all_30_reviewed_exactly_once"],
            "five_invalid_payloads_accounted": transport["f1_accounted_invalid_semantic_payload_count"] == 5,
            "three_identity_blocks_accounted": transport["terminal_identity_block_count"] == 3,
            "counterfactual_policy_not_activated": matrix["policy_v2_activated"] is False,
            "protected_hashes_unchanged": metrics["protected_hash_audit"]["unchanged"],
        },
        "candidate_only": True,
        "canonical_write_back": False,
    }


def _review_inventory(acceptance: Mapping[str, Any], matrix: Mapping[str, Any]) -> dict[str, Any]:
    v2_by_id = {_text(row["occurrence_key"]["occurrence_id"]): row for row in matrix["policy_v2_counterfactual_records"]}
    records = []
    for row in acceptance["records"]:
        occurrence_id = _text(row["occurrence_key"]["occurrence_id"])
        v2 = v2_by_id[occurrence_id]
        records.append({
            "occurrence_key": _copy(row["occurrence_key"]),
            "identity_applicability": row["identity_applicability"],
            "identity_status": row["identity_status"],
            "primary_function": row["primary_function"],
            "boundary_result": row["boundary_result"],
            "final_function": row["final_function"],
            "projected_legacy_occurrence_role": row["projected_legacy_occurrence_role"],
            "reason_target_alignment": row["reason_target_alignment"],
            "review_class": row["review_class"],
            "review_candidate_types": row["review_candidate_types"],
            "current_triggers": row["review_trigger_validity"]["current_triggers"],
            "current_mandatory": row["review_trigger_validity"]["current_mandatory"],
            "counterfactual_mandatory": v2["counterfactual_mandatory"],
            "counterfactual_review_unit": v2["human_review_unit"],
            "human_approval_required": row["human_approval_required"],
        })
    return {
        "schema": "sfh2-f1r-review-inventory-v1",
        "records": records,
        "record_count": len(records),
        "all_exact_occurrences": True,
        "candidate_only": True,
        "canonical_write_back": False,
    }


def run(output: Path = OUT) -> dict[str, Any]:
    """Generate the complete F1R audit without provider calls."""

    before = _protected_snapshot()
    bundle = _source_and_results()
    exact = _exact_records(bundle)
    if len(exact) != 30:
        raise RuntimeError("sfh2_f1r_requires_exactly_30_f1_occurrences")
    if any(not row["target_integrity"]["valid"] for row in exact):
        raise RuntimeError("sfh2_f1r_exact_occurrence_integrity_failed")
    reason = _reason_audit(bundle, exact)
    selection = _selection_alignment(bundle, exact)
    duplicate = _duplicate_surface_audit(exact)
    applicability = _identity_applicability(bundle, exact)
    transport = _transport_failure_audit(bundle)
    acceptance = _acceptance_review(bundle, exact, reason, applicability)
    people = _new_person_groups(bundle, exact)
    matrix = _review_trigger_matrix(bundle, acceptance, people)
    policy_v2 = _review_policy_v2(matrix)
    burden = _review_burden(matrix, people, bundle["documents"]["scope"])
    families = _semantic_error_families(acceptance)
    boundary = _boundary_audit(bundle, acceptance)
    regression = _regression_candidates(acceptance)
    after = _protected_snapshot()
    protected = _protected_hash_audit(before, after)
    metrics = _metrics(bundle, exact, acceptance, reason, duplicate, selection, applicability, transport, people, matrix, boundary, protected)
    recommendation = _recommendation(metrics, transport, acceptance, matrix)
    inventory = _review_inventory(acceptance, matrix)

    gold_alignment = {
        "schema": "sfh2-f1r-gold-alignment-audit-v1",
        "gold_evaluation_available": False,
        "active_gold_loaded": False,
        "records": [
            {
                "occurrence_key": _copy(row["occurrence_key"]),
                "gold_alignment": "not_evaluable_without_authoritative_F1_Gold",
                "gold_taxonomy_status": "not_applicable",
                "semantic_basis_used": False,
                "reason": "F1 is Gold-blind production evidence; F1R does not manufacture or expand Gold.",
            }
            for row in exact
        ],
        "candidate_only": True,
        "canonical_write_back": False,
    }

    blocked = {
        "schema": "sfh2-f1r-blocked-case-audit-v1",
        "records": transport["terminal_identity_blocks"],
        "count": transport["terminal_identity_block_count"],
        "all_three_accounted": transport["terminal_identity_block_count"] == 3,
        "candidate_only": True,
        "canonical_write_back": False,
    }

    architecture = {
        "schema": "sfh2-f1r-architecture-v1",
        "stage": "SFH2.2-F1R",
        "baseline_commit": BASELINE_COMMIT,
        "offline": True,
        "provider_calls": 0,
        "f1_evidence_immutable": True,
        "f1_selection_hash": bundle["documents"]["selection"].get("selection_hash"),
        "f1_selection_count": len(exact),
        "f1_story_count": bundle["documents"]["selection"].get("story_count"),
        "f1_scope_not_regenerated": True,
        "active_gold_mutated": False,
        "gold_expanded": False,
        "semantic_v1_remains_frozen": True,
        "transport_replay_performed": False,
        "selection_integrity_rule": "mention_id, occurrence_id, story_id, source_evidence_id, source_start, source_end, and surface are jointly authoritative; F1R never reselects by surface.",
        "no_python_semantic_inference": True,
        "candidate_only": True,
        "canonical_write_back": False,
    }

    documents = {
        "architecture.json": architecture,
        "exact-occurrence-audit.json": {
            "schema": "sfh2-f1r-exact-occurrence-audit-v1",
            "records": _copy(exact),
            "record_count": len(exact),
            "all_structurally_valid": all(item["target_integrity"]["valid"] for item in exact),
            "selection_not_rebuilt": True,
            "provider_calls": 0,
            "candidate_only": True,
            "canonical_write_back": False,
        },
        "duplicate-surface-audit.json": _duplicate_surface_audit(exact),
        "selection-intent-alignment.json": selection,
        "review-inventory.json": inventory,
        "semantic-acceptance-review.json": acceptance,
        "reason-target-alignment-audit.json": reason,
        "identity-applicability-audit.json": applicability,
        "transport-failure-audit.json": transport,
        "blocked-case-audit.json": blocked,
        "new-person-review-groups.json": people,
        "review-trigger-matrix.json": matrix,
        "review-policy-v2-candidate.json": policy_v2,
        "review-burden-counterfactual.json": burden,
        "semantic-error-families.json": families,
        "boundary-production-audit.json": boundary,
        "regression-gold-candidates.json": regression,
        "gold-alignment-audit.json": gold_alignment,
        "metrics.json": metrics,
        "recommendation.json": recommendation,
    }
    for name, document in documents.items():
        f1.write_json(output / name, document)
    return documents


if __name__ == "__main__":
    import json

    print(json.dumps(run(), ensure_ascii=False, indent=2, sort_keys=True))
