"""Occurrence-centric taxonomy definitions for the A2OT audit.

This module is descriptive only.  It does not interpret historical strings or
make a semantic decision for any occurrence.
"""

from __future__ import annotations

from typing import Any


NARRATIVE_FUNCTIONS = (
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
)


TAXONOMY_DEFINITIONS: dict[str, dict[str, Any]] = {
    "participant": {
        "definition": "The referent actively participates in the narrated event represented by the target occurrence, when the target itself does not perform a more specific speaker/addressee/source/exemplum/attribute function.",
        "specificity": "event_function",
    },
    "reference": {
        "definition": "The target occurrence refers to or describes an entity without itself marking a more specific event, discourse, source, exemplum, or attribute function.",
        "specificity": "generic",
    },
    "speaker": {
        "definition": "The target occurrence itself identifies the speaker of the current utterance, or is the speaker's self-reference within that utterance.",
        "specificity": "discourse_function",
    },
    "addressee": {
        "definition": "The target occurrence itself identifies the directly addressed recipient in the discourse, including vocative or direct-address references.",
        "specificity": "discourse_function",
        "caution": "Do not classify the grammatical object of every communication or interaction verb as addressee; an object of summoning or remonstrance is not automatically a direct-address occurrence.",
    },
    "citation_source": {
        "definition": "The target occurrence itself attributes or identifies the source, author, or work from which cited material is introduced.",
        "specificity": "source_function",
        "caution": "An entity merely mentioned inside quoted source content is not thereby the citation source.",
    },
    "historical_exemplum": {
        "definition": "A historical person or entity invoked as historical comparison, precedent, example, or explanatory background for the current discourse.",
        "specificity": "source_or_exemplum_function",
    },
    "person_attribute": {
        "definition": "The target occurrence itself expresses an attribute or value of a bearer.",
        "specificity": "special_semantic_form",
        "example": "A style-name statement such as 字景真 expresses an attribute; a person occurrence in a predicate describing that person does not automatically do so.",
    },
    "collective_reference": {
        "definition": "The target occurrence itself denotes a collective entity.",
        "specificity": "special_semantic_form",
    },
    "genealogy_reference": {
        "definition": "The target occurrence functions specifically in genealogical or kinship identification.",
        "specificity": "special_semantic_form",
    },
    "structural": {
        "definition": "A structural or non-narrative reference under the existing ontology.",
        "specificity": "fallback_structural",
    },
    "other": {
        "definition": "Use only when the defined functions genuinely do not apply.",
        "specificity": "fallback",
    },
    "uncertain": {
        "definition": "Use when the evidence is insufficient to resolve among the defined functions.",
        "specificity": "fallback",
    },
}


PRECEDENCE = [
    {
        "rank": 1,
        "group": "special_semantic_form",
        "functions": ["person_attribute", "collective_reference", "genealogy_reference"],
    },
    {
        "rank": 2,
        "group": "source_or_exemplum",
        "functions": ["citation_source", "historical_exemplum"],
    },
    {
        "rank": 3,
        "group": "discourse",
        "functions": ["speaker", "addressee"],
    },
    {"rank": 4, "group": "event", "functions": ["participant"]},
    {"rank": 5, "group": "generic", "functions": ["reference"]},
    {"rank": 6, "group": "fallback", "functions": ["other", "uncertain"]},
]


def taxonomy_document() -> dict[str, Any]:
    return {
        "schema": "sfh2-a2ot-taxonomy-definition-v1",
        "stage": "SFH2.2-A2OT",
        "authority": "current SFH2.2 occurrence ontology plus offline human taxonomy audit",
        "occurrence_centric": True,
        "functions": list(NARRATIVE_FUNCTIONS),
        "definitions": TAXONOMY_DEFINITIONS,
        "precedence": PRECEDENCE,
        "semantic_guidance_not_runtime_rules": True,
        "no_surface_specific_logic": True,
        "no_automatic_object_to_addressee_rule": True,
        "notes": [
            "The target occurrence is the unit of classification.",
            "Provenance remains a structural source-evidence property and is not inferred by this taxonomy.",
            "The most occurrence-specific applicable function takes precedence over a generic participant or reference label.",
            "The precedence ordering guides LLM and human review; it is not a Chinese lexical heuristic or executable identity rule.",
        ],
    }
