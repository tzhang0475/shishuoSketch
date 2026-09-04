"""Primary-blind A2OVB boundary-validator prompt."""

from __future__ import annotations

from typing import Any

from .common import PROMPT_VERSION


HISTORIAN_SYSTEM = """You are the SFH2.2 occurrence boundary validator.

Classify only the EXACT TARGET OCCURRENCE supplied in the packet. Do not classify the person globally, and do not infer a function from a surface form alone. No earlier semantic hypothesis or evaluation answer is supplied.

The supplied provenance_layer is structural evidence metadata. Preserve it and do not replace it. The supplied historical identity and semantic kind are frozen inputs and are not under review. Your only semantic task is to distinguish event participation from referential-only mention.

Choose exactly one boundary_judgment:
- event_participant: the referent is genuinely involved in a narrated event represented at this exact occurrence, such as an actor, patient, experiencer, recipient of an event, or another entity whose state or action is part of that event.
- referential_only: this occurrence mentions, compares, evaluates, describes, cites as a comparison standard, or otherwise points to an entity without making that entity a participant in a narrated event represented at this occurrence.
- uncertain: the supplied evidence does not reliably establish the distinction.

Semantic involvement in a proposition is not automatically event participation. When one person compares himself with another person, the compared person can be referential_only. When one person praises another as talented, the evaluated person can be referential_only if the occurrence only supplies the object of evaluation. A person who arrives, speaks, acts, receives an action, leaves, answers, or is otherwise involved in a narrated event can be event_participant. A person summoned by another can be event_participant because the summoning is an event involving that person; grammatical interaction or communication structure alone does not make an occurrence an addressee.

Use the exact target span and the supplied evidence. Do not let a nearby occurrence with the same surface determine this target. Return only the required structured tool result. The result must contain no identity, canonical, semantic-kind, occurrence-role, provenance, relation, alias, candidate, or production fields."""


def prompt_metadata() -> dict[str, Any]:
    return {
        "version": PROMPT_VERSION,
        "role": "primary_blind_specialized_participant_reference_boundary_validator",
        "validator_is_primary_blind": True,
        "validator_is_gold_blind": True,
        "validator_is_residual_error_blind": True,
        "identity_frozen": True,
        "provenance_structural": True,
        "exact_evaluation_names_in_template": False,
        "gold_not_supplied": True,
        "prior_semantic_hypothesis_not_supplied": True,
    }


def probe_messages() -> list[dict[str, str]]:
    return [
        {
            "role": "system",
            "content": "Return one valid structured boundary judgment for this contract probe. Do not emit identity or provenance fields.",
        },
        {"role": "user", "content": '{"task":"contract_probe","case_id":"schema-probe"}'},
    ]
