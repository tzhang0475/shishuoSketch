"""L3 LLM semantic reference and relation interpretation."""

from __future__ import annotations

import copy
from typing import Any, Mapping

from .common import StrictStageClient, text
from .schemas import CONFIDENCES, RELATION_TYPES, SEMANTIC_TYPES, reference_tool
from .source_packets import evidence_index

NETWORK_ROLES = {
    "narrative_participant",
    "narrative_reference",
    "annotation_biographical_person",
    "citation_author",
    "historical_exemplum",
    "genealogy_ancestor",
    "anonymous_person",
    "person_attribute",
    "structural_reference",
    "uncertain",
}

SYSTEM = """You interpret reference structure and relations in classical Chinese. Python has already validated mention boundaries; do not alter them or assign canonical Person IDs. For each supplied person-related mention, identify its semantic reference type, holder/anchor/patron roles, local coreference, explicit distinctness, and source-grounded relations. Co-occurrence alone is not identity. Comparison normally indicates distinct participants. Distinguish office holder from patron or possessor. A suffix such as 子 is not automatically kinship; judge the whole expression in context. Every relation predicate must be copied from the cited source evidence.

Semantic authority is yours, not Python's lexical matcher. If the source context makes the historical referent readable, provide a short referent_hint using the historical name/form supported by the text (for example 勒 in 石勒所獲 may yield 石勒). Do not invent a canonical database ID. Leave referent_hint empty when the text does not support one. Also classify the occurrence's network_role: distinguish narrative participants/references from citation authors, historical exempla, genealogy ancestors, anonymous persons, person attributes, and structural references. A real historical person can still be ineligible for the core Story social graph in a citation-author or exemplum occurrence. Return only the forced structured function."""


def reference_tool_v2() -> dict[str, Any]:
    """Extend the frozen SFH1 tool with semantic hints for future live runs.

    Old cached responses remain replayable because validation below treats the
    new fields as optional when reading historical payloads.
    """
    tool = copy.deepcopy(reference_tool())
    item = tool["function"]["parameters"]["properties"]["records"]["items"]
    item["properties"]["referent_hint"] = {"type": "string"}
    item["properties"]["network_role"] = {"type": "string", "enum": sorted(NETWORK_ROLES)}
    item["required"] = [*item["required"], "referent_hint", "network_role"]
    tool["function"]["name"] = "submit_sfh1_reference_semantics_v2"
    tool["function"]["description"] = "Interpret reference structure, historical referent hints, narrative/source roles, and source-grounded relations."
    return tool


def prompt(packet: Mapping[str, Any], ledger: Mapping[str, Any], target_ids: list[str] | None = None) -> dict[str, Any]:
    mentions = [row for row in ledger.get("valid_mentions", []) or [] if row.get("entity_kind") != "non_person"]
    return {
        "task": "interpret validated historical references and relations",
        "story_id": packet.get("story_id"),
        "source_evidence": [
            {"evidence_id": row.get("evidence_id"), "source_layer": row.get("source_layer"), "text": row.get("text")}
            for row in packet.get("evidence", []) or []
        ],
        "validated_mentions": [
            {
                "mention_id": row.get("mention_id"),
                "surface": row.get("surface"),
                "source_evidence_id": row.get("source_evidence_id"),
                "source_start": row.get("source_start"),
                "source_end": row.get("source_end"),
                "reference_form": row.get("reference_form"),
                "entity_kind": row.get("entity_kind"),
            }
            for row in mentions
        ],
        "target_mention_ids": target_ids or [row.get("mention_id") for row in mentions],
        "target_instruction": "Return records only for target_mention_ids. Other validated mentions remain available for coreference, distinctness, relation endpoints, referent interpretation, and role classification.",
    }


def read_reference_semantics(client: StrictStageClient, packet: Mapping[str, Any], ledger: Mapping[str, Any]) -> Mapping[str, Any] | None:
    person_mentions = [row for row in ledger.get("valid_mentions", []) or [] if row.get("entity_kind") != "non_person"]
    if not person_mentions:
        return {"records": []}
    tool = reference_tool_v2()
    records: list[Any] = []
    provider_failure = False
    mention_ids = [text(row.get("mention_id")) for row in person_mentions]
    chunk_size = 4
    for index in range(0, len(mention_ids), chunk_size):
        target_ids = mention_ids[index:index + chunk_size]
        response = client.call(
            stage="reference_semantics_v2",
            unit_id=f"{packet.get('story_id')}-part{index // chunk_size + 1}",
            system=SYSTEM,
            payload=prompt(packet, ledger, target_ids),
            function=tool,
            function_name=tool["function"]["name"],
            max_tokens=3800,
        )
        if not isinstance(response, Mapping) or not isinstance(response.get("records"), list):
            provider_failure = True
            continue
        records.extend(response.get("records", []) or [])
    return {"records": records, "_provider_failure": provider_failure}


def validate_reference_semantics(packet: Mapping[str, Any], ledger: Mapping[str, Any], payload: Mapping[str, Any] | None) -> dict[str, Any]:
    mentions = {text(row.get("mention_id")): dict(row) for row in ledger.get("valid_mentions", []) or [] if row.get("entity_kind") != "non_person"}
    evidence = evidence_index(packet)
    rows = payload.get("records") if isinstance(payload, Mapping) else None
    if not isinstance(rows, list):
        return {
            "story_id": packet.get("story_id"),
            "records": [], "relations": [],
            "rejected": [{"reason": "provider_or_schema_failure"}],
            "provider_failure": True,
        }
    accepted: list[dict[str, Any]] = []
    relations: dict[tuple[Any, ...], dict[str, Any]] = {}
    rejected: list[dict[str, Any]] = []
    seen_mentions: set[str] = set()
    for index, raw in enumerate(rows):
        if not isinstance(raw, Mapping):
            rejected.append({"index": index, "reason": "record_not_object"})
            continue
        mention_id = text(raw.get("mention_id"))
        semantic_type = text(raw.get("semantic_type"))
        confidence = text(raw.get("confidence"))
        network_role = text(raw.get("network_role")) or "uncertain"
        errors: list[str] = []
        if mention_id not in mentions or mention_id in seen_mentions:
            errors.append("unknown_or_duplicate_mention")
        if semantic_type not in SEMANTIC_TYPES:
            errors.append("invalid_semantic_type")
        if confidence not in CONFIDENCES:
            errors.append("invalid_confidence")
        if network_role not in NETWORK_ROLES:
            errors.append("invalid_network_role")
        link_fields: dict[str, list[str]] = {}
        for field in ("anchor_mentions", "holder_mentions", "patron_or_possessor_mentions", "coreference_with", "distinct_from"):
            value = raw.get(field)
            if not isinstance(value, list):
                errors.append(f"{field}_not_array")
                value = []
            ids = [text(item) for item in value if text(item)]
            if any(item not in mentions or item == mention_id for item in ids):
                errors.append(f"{field}_unknown_or_self")
            link_fields[field] = sorted(set(ids))
        relation_rows = raw.get("semantic_relations")
        if not isinstance(relation_rows, list):
            errors.append("semantic_relations_not_array")
            relation_rows = []
        local_relations: list[dict[str, Any]] = []
        for rel_index, relation in enumerate(relation_rows):
            if not isinstance(relation, Mapping):
                errors.append(f"relation_{rel_index}_not_object")
                continue
            relation_type = text(relation.get("type"))
            subject = text(relation.get("subject_mention_id"))
            object_id = text(relation.get("object_mention_id"))
            predicate = text(relation.get("predicate_surface"))
            evidence_id = text(relation.get("evidence_id"))
            if relation_type not in RELATION_TYPES:
                errors.append(f"relation_{rel_index}_invalid_type")
            if subject not in mentions or object_id not in mentions:
                errors.append(f"relation_{rel_index}_invalid_endpoint")
            if subject == object_id and relation_type not in {"other"}:
                errors.append(f"relation_{rel_index}_self_endpoint")
            if evidence_id not in evidence:
                errors.append(f"relation_{rel_index}_invalid_evidence")
            elif predicate and predicate not in text(evidence[evidence_id].get("text")):
                errors.append(f"relation_{rel_index}_predicate_not_grounded")
            local_relations.append({
                "relation_type": relation_type,
                "subject_mention_id": subject,
                "object_mention_id": object_id,
                "predicate_surface": predicate,
                "evidence_id": evidence_id,
                "candidate_only": True,
                "canonical_write_back": False,
            })
        if errors:
            rejected.append({"index": index, "mention_id": mention_id, "errors": sorted(set(errors))})
            continue
        seen_mentions.add(mention_id)
        record = {
            "mention_id": mention_id,
            "semantic_type": semantic_type,
            "referent_role": text(raw.get("referent_role")),
            "referent_hint": text(raw.get("referent_hint")),
            "network_role": network_role,
            **link_fields,
            "confidence": confidence,
            "explanation": text(raw.get("explanation")),
            "candidate_only": True,
            "canonical_write_back": False,
        }
        accepted.append(record)
        for relation in local_relations:
            key = (
                relation["relation_type"], relation["subject_mention_id"],
                relation["object_mention_id"], relation["predicate_surface"], relation["evidence_id"],
            )
            relations[key] = relation
    for mention_id in sorted(set(mentions) - seen_mentions):
        accepted.append({
            "mention_id": mention_id,
            "semantic_type": "uncertain",
            "referent_role": "",
            "referent_hint": "",
            "network_role": "uncertain",
            "anchor_mentions": [], "holder_mentions": [],
            "patron_or_possessor_mentions": [], "coreference_with": [], "distinct_from": [],
            "confidence": "low",
            "explanation": "No valid semantic record was returned; fail closed.",
            "candidate_only": True,
            "canonical_write_back": False,
        })
    return {
        "story_id": packet.get("story_id"),
        "records": sorted(accepted, key=lambda row: row["mention_id"]),
        "relations": sorted(relations.values(), key=lambda row: (row["evidence_id"], row["subject_mention_id"], row["object_mention_id"], row["relation_type"])),
        "rejected": rejected,
        "provider_failure": bool(payload.get("_provider_failure")) if isinstance(payload, Mapping) else False,
        "semantic_schema_version": "reference_semantics_v2",
    }
