"""Evidence-provenance derivation and generic legacy-role projection.

The functions in this module consume already structured source metadata and an
already structured LLM narrative-function value.  They never inspect a
surface string and never choose a historical identity.
"""

from __future__ import annotations

from typing import Any, Mapping


NARRATIVE_FUNCTIONS = frozenset({
    "participant",
    "reference",
    "speaker",
    "addressee",
    "collective_reference",
    "person_attribute",
    "citation_source",
    "historical_exemplum",
    "genealogy_reference",
    "structural",
    "other",
    "uncertain",
})


def text(value: Any) -> str:
    return str(value or "").strip()


def source_evidence_by_id(packet: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    return {
        text(row.get("evidence_id")): row
        for row in packet.get("source_evidence", []) or []
        if isinstance(row, Mapping) and text(row.get("evidence_id"))
    }


def derive_provenance_layer(packet: Mapping[str, Any]) -> tuple[str | None, list[str]]:
    """Derive the layer solely from target.source_evidence_id metadata."""

    target = packet.get("target") if isinstance(packet.get("target"), Mapping) else {}
    evidence_id = text(target.get("source_evidence_id"))
    if not evidence_id:
        return None, ["target_source_evidence_id_missing"]
    source = source_evidence_by_id(packet).get(evidence_id)
    if source is None:
        return None, ["target_source_evidence_missing"]
    layer = text(source.get("source_layer"))
    if not layer:
        return None, ["target_source_layer_missing"]
    return layer, []


def project_legacy_occurrence_role(provenance_layer: str, narrative_function: str) -> str:
    """Project structured axes to the compatibility role used by older data."""

    layer = text(provenance_layer)
    function = text(narrative_function)
    if function == "historical_exemplum":
        return "historical_exemplum"
    if function == "collective_reference":
        return "collective_reference"
    if function == "person_attribute":
        return "person_attribute"
    if function == "genealogy_reference":
        return "genealogy_reference"
    if function == "citation_source":
        return "citation_source_person"
    if function == "speaker":
        return "speaker_reference"
    if function == "addressee":
        return "addressee_reference"
    if layer == "liu_annotation" and function in {"participant", "reference"}:
        return "annotation_person"
    if layer == "main_text" and function == "participant":
        return "scene_participant"
    if layer == "main_text" and function == "reference":
        return "scene_reference"
    if function == "structural":
        return "structural"
    return "other"
