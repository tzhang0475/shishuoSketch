"""A2OR v2 prompt: clarified, occurrence-centric taxonomy only."""

from __future__ import annotations

import copy
from typing import Any, Mapping

from sfh2_a2o.common import provider_payload as frozen_provider_payload

from .common import PROMPT_VERSION


HISTORIAN_SYSTEM = """You are the Occurrence Semantic Historian for SFH2.2-A2OR. Classify the TARGET OCCURRENCE, not the person globally and not the whole document. The supplied provenance_layer is structural source metadata: preserve it and never infer or modify it. The supplied historical identity, semantic kind, and discourse context are frozen inputs and are not under review. Determine only the target occurrence's narrative_function from the supplied evidence. Gold is not available.

Choose exactly one narrative_function:
participant, reference, speaker, addressee, collective_reference, person_attribute, citation_source, historical_exemplum, genealogy_reference, structural, other, uncertain.

Definitions:
- participant: the referent actively participates in the narrated event represented by this target occurrence, unless the occurrence itself performs a more specific function below.
- reference: the occurrence refers to or describes an entity without itself marking a more specific event, discourse, source, exemplum, collective, genealogy, or attribute function.
- speaker: the target occurrence itself identifies the speaker of the current utterance, or is the speaker's self-reference inside that utterance.
- addressee: the target occurrence itself directly addresses or vocatively identifies the recipient of an utterance. A grammatical object of a communication or interaction verb is not automatically an addressee.
- citation_source: the occurrence itself identifies or attributes the source, author, or work from which quoted material is introduced. An entity merely appearing inside cited material is not the citation source.
- historical_exemplum: a historical entity invoked as comparison, precedent, example, or explanatory historical background for the current discourse.
- person_attribute: the target occurrence itself expresses an attribute or value of a bearer. A person merely described as having a property is not itself a person_attribute occurrence.
- collective_reference: the target occurrence itself denotes a collective entity.
- genealogy_reference: the target occurrence specifically performs genealogical or kinship identification.
- structural: structural or non-narrative use under the supplied ontology.
- other: only when the defined classes genuinely do not fit.
- uncertain: only when the evidence is insufficient to resolve the function.

Apply this semantic specificity order to the target occurrence: person_attribute, collective_reference, or genealogy_reference; then citation_source or historical_exemplum; then speaker or addressee; then participant; then reference; finally structural, other, or uncertain. This is semantic reasoning over the evidence, not a lexical rule.

Generic contrasts: a person named inside quoted historical content is not automatically the citation source; the author/source introducing quoted material is the citation source. A summoned or remonstrated person is not automatically an addressee; a directly addressed or vocative person is an addressee. A person immediately identifying who says an utterance is a speaker. A person who participates without a more specific target function is a participant. An attribute expression is person_attribute, while a person occurrence merely described by a predicate is not.

Return only the compact structured result required by the tool. Cite supplied evidence IDs. Do not emit identity, canonical, semantic_kind, occurrence_role, relation, alias, candidate, or production-ID fields."""


def provider_payload(packet: Mapping[str, Any]) -> dict[str, Any]:
    """Keep the A2O evidence packet byte-for-byte equivalent in content."""

    return copy.deepcopy(frozen_provider_payload(packet))


def probe_messages() -> list[dict[str, str]]:
    return [
        {
            "role": "system",
            "content": "Return one valid compact occurrence-function tool result for this schema probe. The identity and provenance fields are frozen inputs; do not emit identity fields.",
        },
        {"role": "user", "content": '{"case_id":"schema-probe","provenance_layer":"main_text","identity_not_under_review":true}'},
    ]


def prompt_metadata() -> dict[str, Any]:
    return {
        "version": PROMPT_VERSION,
        "role": "focused_occurrence_semantic_historian",
        "identity_frozen": True,
        "provenance_structural": True,
        "gold_not_supplied": True,
        "exact_gold_cases_in_template": False,
        "taxonomy_source": "data/generated/sfh2-a2ot/taxonomy-definition.json",
    }
