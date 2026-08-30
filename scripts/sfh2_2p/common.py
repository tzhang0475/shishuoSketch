"""Deterministic inputs, packet construction, and output helpers for SFH2.2-P."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parents[2]
SFH1_ROOT = ROOT / "data/generated/sfh1"
OUT = ROOT / "data/generated/sfh2-2p"
SELECTION_PATH = ROOT / "data/annotation/sfh2-2p-selection.json"
MODEL = "deepseek-v4-flash"
SCHEMA_VERSION = "sfh2-2p-v1"
PILOT_VERSION = "sfh2-2p-v2"
PROMPT_VERSIONS = {
    "reference_semantics": "sfh2-2p-l3-reference-semantics-v1",
    "identity_judgment": "sfh2-2p-l5-identity-judgment-v1",
}
STRICT_ENDPOINT = "https://api.deepseek.com/beta/chat/completions"

VARIANT_TRANSLATION = str.maketrans({
    "爲": "為", "髙": "高", "鳯": "鳳", "臺": "台", "裏": "裡",
})


def text(value: Any) -> str:
    return str(value or "").strip()


def normalize(value: Any) -> str:
    return re.sub(r"\s+", "", text(value)).translate(VARIANT_TRANSLATION)


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


def records(document: Any, *keys: str) -> list[dict[str, Any]]:
    if isinstance(document, list):
        return [dict(row) for row in document if isinstance(row, Mapping)]
    if not isinstance(document, Mapping):
        return []
    for key in keys:
        value = document.get(key)
        if isinstance(value, list):
            return [dict(row) for row in value if isinstance(row, Mapping)]
    return []


def load_inputs() -> dict[str, Any]:
    def load(name: str, default: Any = None) -> Any:
        return read_json(SFH1_ROOT / name, default) or default

    return {
        "packets": load("story-packets.json", {}),
        "mentions": load("validated-mentions.json", {}),
        "semantics": load("reference-semantics.json", {}),
        "candidate_sets": load("candidate-sets.json", {}),
        "identity_judgments": load("identity-judgments.json", {}),
        "final": load("final-decisions.json", {}),
        "relations": load("relation-assertions.json", {}),
        "people": read_json(ROOT / "data/people.json", {}) or {},
        "aliases": read_json(ROOT / "data/aliases.json", {}) or {},
        "profiles": read_json(ROOT / "data/derived/hdb2-f-person-knowledge.json", {}) or {},
        "candidate_profiles": read_json(ROOT / "data/derived/hdb2-f-candidate-person-knowledge.json", {}) or {},
        "hda2_overlay": read_json(ROOT / "data/generated/hda2/repair-overlay.json", {}) or {},
    }


def packet_index(inputs: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    return {text(row.get("story_id")): row for row in records(inputs.get("packets"), "packets") if text(row.get("story_id"))}


def mention_index(inputs: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    return {text(row.get("mention_id")): row for row in records(inputs.get("mentions"), "records") if text(row.get("mention_id"))}


def semantic_index(inputs: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    return {text(row.get("mention_id")): row for row in records(inputs.get("semantics"), "records") if text(row.get("mention_id"))}


def candidate_index(inputs: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    return {text(row.get("mention_id")): row for row in records(inputs.get("candidate_sets"), "records") if text(row.get("mention_id"))}


def final_index(inputs: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    return {text(row.get("mention_id")): row for row in records(inputs.get("final"), "records") if text(row.get("mention_id"))}


def evidence_index(packet: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    # L0 packets use ``source_evidence`` while the upstream SFH1 packet uses
    # ``evidence``.  Treating both as the same evidence namespace is required
    # for strict grounding of live L3/L5 payloads; an earlier pilot build
    # accidentally rejected every valid live evidence ID from the compact
    # case packet.
    values = packet.get("evidence")
    if not isinstance(values, list):
        values = packet.get("source_evidence")
    return {text(row.get("evidence_id")): dict(row) for row in values or [] if isinstance(row, Mapping) and text(row.get("evidence_id"))}


def exact_span(mention: Mapping[str, Any], packet: Mapping[str, Any]) -> str:
    source = evidence_index(packet).get(text(mention.get("source_evidence_id")), {})
    value = text(source.get("text"))
    start = mention.get("source_start")
    end = mention.get("source_end")
    if isinstance(start, int) and isinstance(end, int) and 0 <= start <= end <= len(value):
        return value[start:end]
    return text(mention.get("surface"))


def compact_context(value: Any, limit: int = 900) -> str:
    result = text(value)
    if len(result) <= limit:
        return result
    return result[: max(0, limit - 1)] + "…"


def build_case_packet(case: Mapping[str, Any], inputs: Mapping[str, Any]) -> dict[str, Any]:
    """Build a gold-free L0 packet for one already validated occurrence."""
    mentions = mention_index(inputs)
    packets = packet_index(inputs)
    mention = mentions.get(text(case.get("mention_id")), {})
    packet = packets.get(text(case.get("story_id")), {})
    evidence = evidence_index(packet)
    target_id = text(mention.get("mention_id"))
    surface = text(mention.get("surface"))
    source_id = text(mention.get("source_evidence_id"))
    source = evidence.get(source_id, {})
    local_mentions = [
        {
            "mention_id": row.get("mention_id"),
            "surface": row.get("surface"),
            "source_evidence_id": row.get("source_evidence_id"),
            "source_start": row.get("source_start"),
            "source_end": row.get("source_end"),
            "entity_kind": row.get("entity_kind"),
            "reference_form": row.get("reference_form"),
        }
        for row in records(inputs.get("mentions"), "records")
        if text(row.get("story_id")) == text(case.get("story_id"))
    ]
    all_evidence = [row for row in packet.get("evidence", []) or [] if isinstance(row, Mapping)]
    local_surfaces = {
        text(row.get("surface"))
        for row in records(inputs.get("mentions"), "records")
        if text(row.get("story_id")) == text(case.get("story_id")) and text(row.get("surface"))
    }
    all_liu = [row for row in all_evidence if text(row.get("source_layer")) == "liu_annotation"]
    relevant = []
    for row in all_evidence:
        if not isinstance(row, Mapping):
            continue
        row_id = text(row.get("evidence_id"))
        row_text = text(row.get("text"))
        layer = text(row.get("source_layer"))
        # A small Liu bundle is part of the relevant source context even when
        # it does not repeat the target surface (for example 劉尹 is resolved
        # through the story's nearby 劉遐/真長 evidence).  For large bundles,
        # retain only fragments touching a validated local surface.  This is
        # deterministic packet preparation, not a semantic identity guess.
        liu_relevant = layer == "liu_annotation" and (
            len(all_liu) <= 8 or surface in row_text or any(local_surface in row_text for local_surface in local_surfaces)
        )
        if row_id == source_id or layer == "main_text" or surface in row_text or liu_relevant:
            relevant.append({
                "evidence_id": row_id,
                "source_layer": row.get("source_layer"),
                "source_ref": row.get("source_ref"),
                "text": compact_context(row_text, 1200),
            })
    # Keep the compact packet bounded even when the main source is large.
    # The Liu selection above has already retained the relevant small bundle;
    # this final guard removes only excess annotation fragments by stable
    # source order.
    liu = [row for row in relevant if row.get("source_layer") == "liu_annotation"]
    if len(relevant) > 24 and liu:
        keep_liu = [row for row in liu if surface in text(row.get("text")) or row.get("evidence_id") == source_id or any(local_surface in text(row.get("text")) for local_surface in local_surfaces)]
        keep_ids = {text(row.get("evidence_id")) for row in keep_liu}
        relevant = [row for row in relevant if row.get("source_layer") != "liu_annotation" or text(row.get("evidence_id")) in keep_ids]
    return {
        "case_id": text(case.get("case_id")),
        "story_id": text(case.get("story_id")),
        "mention_id": target_id,
        "target": {
            "surface": surface,
            "source_evidence_id": source_id,
            "source_start": mention.get("source_start"),
            "source_end": mention.get("source_end"),
            "exact_span": exact_span(mention, packet),
        },
        "story_context": {
            "chapter_id": packet.get("chapter_id"),
            "source_path": packet.get("source_path"),
            "source_sha256": packet.get("source_sha256"),
        },
        "source_evidence": relevant,
        "validated_local_mentions": local_mentions,
        "candidate_neutral_instruction": "Known forms are retrieval hints only. Do not infer a canonical identity from a string match; use only supplied evidence.",
        "gold_visible_to_model": False,
        "candidate_only": True,
        "canonical_write_back": False,
    }


def input_hashes(inputs: Mapping[str, Any]) -> dict[str, str]:
    names = (
        "story-packets.json", "validated-mentions.json", "reference-semantics.json",
        "candidate-sets.json", "identity-judgments.json", "final-decisions.json",
        "relation-assertions.json", "people.json", "aliases.json",
        "hdb2-f-person-knowledge.json", "hdb2-f-candidate-person-knowledge.json",
    )
    result: dict[str, str] = {}
    for name in names:
        path = (SFH1_ROOT / name) if name.endswith(".json") and name not in {"people.json", "aliases.json", "hdb2-f-person-knowledge.json", "hdb2-f-candidate-person-knowledge.json"} else None
        if name == "people.json":
            path = ROOT / "data/people.json"
        elif name == "aliases.json":
            path = ROOT / "data/aliases.json"
        elif name == "hdb2-f-person-knowledge.json":
            path = ROOT / "data/derived/hdb2-f-person-knowledge.json"
        elif name == "hdb2-f-candidate-person-knowledge.json":
            path = ROOT / "data/derived/hdb2-f-candidate-person-knowledge.json"
        if path and path.is_file():
            result[str(path.relative_to(ROOT))] = file_hash(path)
    return dict(sorted(result.items()))
