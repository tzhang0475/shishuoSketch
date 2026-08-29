"""L1 blind LLM mention reading."""

from __future__ import annotations

from typing import Any, Mapping

from .common import StrictStageClient
from .schemas import mention_tool

SYSTEM = """You read classical Chinese historical text. Identify every actual person or person-reference mention in the supplied Story and relevant annotation evidence. Work from the text itself: no Python-proposed entity labels or expected identities are provided. Copy each surface exactly from one cited evidence item. ALWAYS return JSON null for source_start and source_end: Python will locate the copied surface deterministically, avoiding offset-counting convention errors. One passage may contain multiple mentions. Distinguish people, collective person references, and conspicuous non-person spans that might otherwise be mistaken for people. Do not resolve canonical identity and do not invent Person IDs. Return only the forced structured function."""


def prompt(packet: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "task": "blind historical person-mention reading",
        "story_id": packet.get("story_id"),
        "source_evidence": [
            {
                "evidence_id": row.get("evidence_id"),
                "source_layer": row.get("source_layer"),
                "text": row.get("text"),
            }
            for row in packet.get("evidence", []) or []
        ],
        "instructions": [
            "Extract all person-related mentions, not just full names.",
            "Use exact source surfaces and source evidence IDs.",
            "Set both source_start and source_end to JSON null.",
            "Do not resolve canonical historical identity.",
            "Do not treat works, objects, places, or whole prose clauses as named people.",
        ],
    }


def read_mentions(client: StrictStageClient, packet: Mapping[str, Any]) -> Mapping[str, Any] | None:
    tool = mention_tool()
    return client.call(
        stage="mention_reading",
        unit_id=str(packet.get("story_id")),
        system=SYSTEM,
        payload=prompt(packet),
        function=tool,
        function_name=tool["function"]["name"],
        # Dense Liu-annotation packets can legitimately contain many distinct
        # references.  Keep the required one-Story/one-reading contract while
        # allowing the strict response enough room to finish.
        max_tokens=8000,
    )
