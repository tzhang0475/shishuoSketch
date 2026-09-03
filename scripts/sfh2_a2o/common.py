"""Frozen A2O inputs, source packets, and deterministic audit helpers."""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

from sfh2_a2 import common as a2_common
from sfh2_a0r_l.common import CHALLENGE_STORIES

from .provenance import derive_provenance_layer, text


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "data/generated/sfh2-a2o"
BASELINE_COMMIT = "be322c9a25476214a7c58ed7e3fa592e5168c4d4"
MODEL = "deepseek-v4-flash"
TEMPERATURE = 0
THINKING = {"type": "disabled"}
STRICT_ENDPOINT = "https://api.deepseek.com/beta/chat/completions"
PILOT_VERSION = "sfh2-a2o-v1"
SCHEMA_VERSION = "sfh2-a2o-v1"
PROMPT_VERSION = "sfh2-a2o-occurrence-function-historian-v1"
MAX_PROVIDER_ATTEMPTS = 40
A0_SELECTION_PATH = ROOT / "data/annotation/sfh2-a0-selection.json"
CHALLENGE_SELECTION_PATH = ROOT / "data/annotation/sfh2-a0r-l-challenge-selection.json"
A2G_ROLE_AUDIT_PATH = ROOT / "data/generated/sfh2-a2g/occurrence-role-audit.json"
A2R_FINAL_PATH = ROOT / "data/generated/sfh2-a2r/final-results.json"
GOLD_PATH = ROOT / "data/annotation/sfh2-a2o-evaluation-gold.json"
IDENTITY_MANIFEST_PATH = ROOT / "data/frozen/sfh2/identity-v1/manifest.json"


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
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _rows(document: Any, key: str = "records") -> list[dict[str, Any]]:
    if isinstance(document, list):
        return [dict(row) for row in document if isinstance(row, Mapping)]
    if isinstance(document, Mapping) and isinstance(document.get(key), list):
        return [dict(row) for row in document[key] if isinstance(row, Mapping)]
    return []


def cases_by_cohort() -> dict[str, list[dict[str, Any]]]:
    a0 = _rows(read_json(A0_SELECTION_PATH, {}), "cases")
    challenge = _rows(read_json(CHALLENGE_SELECTION_PATH, {}), "cases")
    role_ids = {
        text(row.get("case_id"))
        for row in _rows(read_json(A2G_ROLE_AUDIT_PATH, {}))
        if text(row.get("case_id"))
    }
    role_cases = [dict(row) for row in a0 if text(row.get("case_id")) in role_ids]
    if len(role_cases) != 6:
        raise RuntimeError("sfh2_a2o_requires_six_frozen_reviewed_role_cases")
    if len(challenge) != 20:
        raise RuntimeError("sfh2_a2o_requires_twenty_frozen_challenge_cases")
    if {text(row.get("story_id")) for row in challenge} != set(CHALLENGE_STORIES):
        raise RuntimeError("sfh2_a2o_challenge_story_set_changed")
    return {"reviewed_role": role_cases, "challenge": [dict(row) for row in challenge]}


def all_cases() -> list[dict[str, Any]]:
    cohorts = cases_by_cohort()
    result: list[dict[str, Any]] = []
    seen: set[str] = set()
    for cohort in ("reviewed_role", "challenge"):
        for row in cohorts[cohort]:
            case = dict(row)
            case["cohort"] = cohort
            case_id = text(case.get("case_id"))
            if not case_id or case_id in seen:
                raise RuntimeError("sfh2_a2o_duplicate_or_missing_case_id")
            seen.add(case_id)
            result.append(case)
    if len(result) != 26:
        raise RuntimeError("sfh2_a2o_requires_26_case_pilot")
    return result


def load_inputs() -> dict[str, Any]:
    return a2_common.load_inputs()


def _mention_rows(inputs: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    document = inputs.get("mentions")
    rows = document.get("records", []) if isinstance(document, Mapping) else document
    return {
        text(row.get("mention_id")): row
        for row in rows or []
        if isinstance(row, Mapping) and text(row.get("mention_id"))
    }


def _frozen_identity_index() -> dict[str, Mapping[str, Any]]:
    records = _rows(read_json(A2R_FINAL_PATH, {}))
    return {
        text(row.get("case_id")): row.get("selected_record")
        for row in records
        if text(row.get("case_id")) and isinstance(row.get("selected_record"), Mapping)
    }


def frozen_identity_context(case_id: str) -> dict[str, Any]:
    record = _frozen_identity_index().get(text(case_id))
    if not isinstance(record, Mapping):
        raise RuntimeError(f"missing_frozen_identity_for:{case_id}")
    # This allow-list deliberately excludes occurrence_role and all generated
    # candidate/production identifiers.  The frozen identity result is input,
    # never an A2O output field.
    return {
        "semantic_kind": record.get("semantic_kind"),
        "reference_type": record.get("reference_type"),
        "referent": copy.deepcopy(record.get("referent", {})),
        "attribute_type": record.get("attribute_type", ""),
        "attribute_value": record.get("attribute_value", ""),
        "bearer_hint": record.get("bearer_hint", ""),
        "abstain": record.get("abstain", False),
    }


def frozen_discourse_context(case_id: str) -> dict[str, str]:
    record = _frozen_identity_index().get(text(case_id))
    discourse = record.get("discourse") if isinstance(record, Mapping) else {}
    return {
        key: text(discourse.get(key))
        for key in ("speaker_hint", "addressee_hint", "antecedent_hint", "self_reference_hint")
    } if isinstance(discourse, Mapping) else {key: "" for key in ("speaker_hint", "addressee_hint", "antecedent_hint", "self_reference_hint")}


def _risk_dimensions(case: Mapping[str, Any], inputs: Mapping[str, Any], provenance_layer: str) -> list[str]:
    mention = _mention_rows(inputs).get(text(case.get("mention_id")), {})
    form = text(mention.get("reference_form"))
    values: list[str] = ["source_provenance:" + provenance_layer]
    form_dimensions = {
        "pronoun_reference": "anaphoric_reference",
        "discourse_reference": "discourse_reference",
        "office_title": "title_or_honorific",
        "ruler_title": "title_or_honorific",
        "honorific": "title_or_honorific",
        "courtesy_name": "style_or_courtesy_form",
        "style_name": "style_or_courtesy_form",
        "abbreviated_reference": "abbreviated_reference",
        "surname_reference": "abbreviated_reference",
        "citation_reference": "source_reference",
        "attribute_reference": "person_attribute",
    }
    if form in form_dimensions:
        values.append(form_dimensions[form])
    if text(case.get("cohort")) == "reviewed_role":
        values.append("reviewed_role_case")
    if text(mention.get("entity_kind")) == "collective_person_reference":
        values.append("collective_control")
    return sorted(set(values))


def build_case_packet(case: Mapping[str, Any], inputs: Mapping[str, Any]) -> dict[str, Any]:
    packet = dict(a2_common.build_case_packet(case, inputs))
    provenance_layer, errors = derive_provenance_layer(packet)
    if errors or not provenance_layer:
        raise RuntimeError(";".join(errors or ["provenance_layer_missing"]))
    packet["provenance_layer"] = provenance_layer
    packet["frozen_identity_context"] = frozen_identity_context(text(case.get("case_id")))
    packet["frozen_discourse_context"] = frozen_discourse_context(text(case.get("case_id")))
    packet["a2o_pilot"] = "provenance_layer_structural_narrative_function_llm"
    packet["identity_is_frozen"] = True
    packet["gold_visible_to_model"] = False
    packet["candidate_only"] = True
    packet["canonical_write_back"] = False
    packet["selection_risk_dimensions"] = _risk_dimensions(case, inputs, provenance_layer)
    return packet


def provider_payload(packet: Mapping[str, Any]) -> dict[str, Any]:
    """Allow-list A2O provider input; no Gold or legacy role is included."""

    source_evidence = copy.deepcopy(packet.get("source_evidence", []))
    target = copy.deepcopy(packet.get("target", {}))
    target_id = text(target.get("source_evidence_id")) if isinstance(target, Mapping) else ""
    target_source = next((copy.deepcopy(row) for row in source_evidence if isinstance(row, Mapping) and text(row.get("evidence_id")) == target_id), {})
    return {
        "task": "determine only the narrative function of the target occurrence",
        "case_id": packet.get("case_id"),
        "story_id": packet.get("story_id"),
        "target": target,
        "target_source_evidence": target_source,
        "nearby_source_evidence": source_evidence,
        "validated_local_mentions": copy.deepcopy(packet.get("validated_local_mentions", [])),
        "provenance_layer": packet.get("provenance_layer"),
        "frozen_identity": copy.deepcopy(packet.get("frozen_identity_context", {})),
        "relevant_discourse_context": copy.deepcopy(packet.get("frozen_discourse_context", {})),
        "narrative_function_ontology": [
            "participant", "reference", "speaker", "addressee", "collective_reference",
            "person_attribute", "citation_source", "historical_exemplum", "genealogy_reference",
            "structural", "other", "uncertain",
        ],
        "identity_not_under_review": True,
        "do_not_output_identity_fields": True,
        "gold_not_supplied": True,
        "candidate_only": True,
        "canonical_write_back": False,
    }


def selection_document(cases: list[Mapping[str, Any]], inputs: Mapping[str, Any], packets: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    rows = []
    for case in cases:
        case_id = text(case.get("case_id"))
        packet = packets[case_id]
        rows.append({
            "case_id": case_id,
            "cohort": case.get("cohort"),
            "story_id": case.get("story_id"),
            "mention_id": case.get("mention_id"),
            "surface": case.get("surface"),
            "source_evidence_id": case.get("source_evidence_id"),
            "provenance_layer": packet.get("provenance_layer"),
            "risk_dimensions": packet.get("selection_risk_dimensions", []),
            "selection_reason": "all frozen A2G reviewed role cases plus all frozen A0R-L challenge mentions",
        })
    return {
        "schema": "sfh2-a2o-selection-v1",
        "selection_method": "frozen_role_cases_plus_complete_frozen_challenge_cohort",
        "selection_is_deterministic": True,
        "gold_used_for_selection": False,
        "case_count": len(rows),
        "reviewed_role_case_count": sum(row.get("cohort") == "reviewed_role" for row in rows),
        "challenge_case_count": sum(row.get("cohort") == "challenge" for row in rows),
        "challenge_stories": list(CHALLENGE_STORIES),
        "cases": rows,
        "selection_hash": stable_hash(rows),
        "candidate_only": True,
        "canonical_write_back": False,
    }


def input_hashes() -> dict[str, str]:
    paths = [
        A0_SELECTION_PATH,
        CHALLENGE_SELECTION_PATH,
        A2G_ROLE_AUDIT_PATH,
        A2R_FINAL_PATH,
        ROOT / "data/generated/sfh1/story-packets.json",
        ROOT / "data/generated/sfh1/validated-mentions.json",
        ROOT / "data/frozen/sfh2/identity-v1/manifest.json",
    ]
    return {str(path.relative_to(ROOT)): file_hash(path) for path in paths if path.is_file()}
