#!/usr/bin/env python3
"""Controlled local-evidence retrieval for the DS1.2 experiment.

This module is intentionally a small, deterministic boundary around the
registered evidence indexes.  It never searches generated/model output and it
does not write canonical or Gold data.
"""

from __future__ import annotations

import hashlib
import html
import json
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping, Sequence

try:  # Support both ``python scripts/run_ds1_2.py`` and package imports in tests.
    from .ds1_common import ROOT, read_json, sha256_file, stable_json
except ImportError:  # pragma: no cover - exercised by direct script execution
    from ds1_common import ROOT, read_json, sha256_file, stable_json


STORY_ID = "27-jiajue-008"
MODEL = "deepseek-v4-flash"
PROMPT_VERSION = "ds1-2-local-evidence-v1"
SCHEMA_VERSION = 1

SC1_PATH = Path("data/derived/sc1-site.json")
HR0_PATH = Path("data/derived/hr0-historical-situations.json")
HR01_PATH = Path("data/derived/hr0-1-ambiguity-benchmark.json")
WP1_EVIDENCE_PATH = Path("data/evidence/wp1-evidence.json")
WP1_SOURCES_PATH = Path("data/sources/wp1-sources.json")
S1_ASSERTIONS_PATH = Path("data/derived/s1-jianshu-historical-assertions.json")
S1_REGISTRATION_PATH = Path("data/derived/s1-jianshu-source-registration.json")
SEARCHED_SOURCE_PATHS = (WP1_EVIDENCE_PATH.as_posix(), S1_ASSERTIONS_PATH.as_posix())

OUTPUT_DIR = Path("data/generated/ds1-2")
TRACE_PATH = OUTPUT_DIR / f"{STORY_ID}-trace.json"
CANDIDATE_PATH = OUTPUT_DIR / f"{STORY_ID}.json"
MANIFEST_PATH = OUTPUT_DIR / "manifest.json"

MAX_TOP_K = 5
MAX_TOOL_ROUNDS = 6
MAX_TOTAL_RETURNED_CHARS = 24000
MAX_SEARCH_QUOTE_CHARS = 900
MAX_OPEN_QUOTE_CHARS = 6000
MAX_QUERY_CHARS = 240
MAX_ENTITY_HINTS = 12
MAX_SOURCE_LAYERS = 8

ALLOWED_WP1_EVIDENCE_TYPES = {"primary_text", "annotation", "editorial"}
ALLOWED_SOURCE_LAYERS = {
    "base_text",
    "liu_annotation",
    "jianshu_note",
    "collation_note",
    "other_scholar_note",
    "editorial",
    "reviewed_canonical_fact",
}
PROJECT_STATUSES = {"accepted", "not_materialized", "disputed", "unknown"}
LAYER_ALIASES = {
    "primary_text": "base_text",
    "annotation": "liu_annotation",
    "liu": "liu_annotation",
    "liu_annotation": "liu_annotation",
    "base": "base_text",
    "base_text": "base_text",
    "editorial": "editorial",
    "jianshu": "jianshu_note",
    "jianshu_note": "jianshu_note",
    "collation": "collation_note",
    "collation_note": "collation_note",
    "scholar": "other_scholar_note",
    "other_scholar_note": "other_scholar_note",
    "reviewed_canonical_fact": "reviewed_canonical_fact",
}

# A small, explicit fold is preferable to making retrieval depend on the
# optional OpenCC installation used by some repository validators.
TRADITIONAL_FOLD = str.maketrans(
    {
        "蘇": "苏",
        "溫": "温",
        "嶠": "峤",
        "尋": "寻",
        "陽": "阳",
        "亂": "乱",
        "難": "难",
        "責": "责",
        "躬": "躬",
        "會": "会",
        "見": "见",
        "從": "从",
        "爲": "为",
        "為": "为",
        "與": "与",
        "後": "后",
        "國": "国",
        "將": "将",
        "軍": "军",
        "門": "门",
        "書": "书",
        "應": "应",
        "說": "说",
        "時": "时",
        "開": "开",
        "發": "发",
        "從": "从",
        "於": "于",
        "無": "无",
        "並": "并",
        "為": "为",
    }
)


def _fold(value: str) -> str:
    return unicodedata.normalize("NFKC", value).translate(TRADITIONAL_FOLD).lower()


def _safe_locator(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        return {}
    allowed = (
        "artifact_type",
        "entry_id",
        "chapter_id",
        "annotation_id",
        "artifact_path",
        "source_normalized_filename",
        "normalized_line_start",
        "normalized_line_end",
        "page_marker_start",
        "page_marker_end",
        "witness_id",
        "source_path",
        "source_sha256",
        "epub_file",
        "spine_index",
        "block_index",
        "tag",
        "page",
        "physical_page",
        "fact_id",
    )
    return {key: value[key] for key in allowed if key in value}


def _source_label(record: Mapping[str, Any], source_records: Mapping[str, Mapping[str, Any]]) -> str:
    source_id = str(record.get("source_id", ""))
    source = source_records.get(source_id)
    if source:
        return f"{source.get('work', source_id)} · {source.get('witness_id', source_id)}"
    if source_id:
        return source_id
    return str(record.get("source_family", "local scholarly reference"))


def _text_terms(value: str) -> list[str]:
    folded = _fold(value)
    words = [word for word in re.split(r"[^\w\u3400-\u9fff]+", folded) if word]
    terms: set[str] = set(words)
    for word in words:
        if len(word) >= 2 and any("\u3400" <= char <= "\u9fff" for char in word):
            terms.update(word[index : index + 2] for index in range(len(word) - 1))
        if len(word) >= 3 and any("\u3400" <= char <= "\u9fff" for char in word):
            terms.update(word[index : index + 3] for index in range(len(word) - 2))
    return sorted(term for term in terms if term)


@dataclass(frozen=True)
class EvidenceRecord:
    evidence_ref: str
    source: str
    source_layer: str
    locator: dict[str, Any]
    quote: str
    searchable_text: str
    source_path: str
    assertion_status: str | None = None
    review_status: str | None = None
    attribution: str | None = None
    quoted_source: str | None = None

    def public(self, *, score: int | None = None, quote_limit: int = MAX_OPEN_QUOTE_CHARS) -> dict[str, Any]:
        result: dict[str, Any] = {
            "evidence_ref": self.evidence_ref,
            "source": self.source,
            "source_layer": self.source_layer,
            "project_status": project_status_for_record(self),
            "locator": self.locator,
            "quote": self.quote[:quote_limit],
        }
        if score is not None:
            result["score"] = score
        if self.attribution:
            result["attribution"] = self.attribution
        if self.quoted_source:
            result["quoted_source"] = self.quoted_source
        if self.assertion_status:
            result["assertion_status"] = self.assertion_status
        if self.review_status:
            result["review_status"] = self.review_status
        return result


def project_status_for_record(record: EvidenceRecord) -> str:
    """Map project acceptance metadata without changing source assertion status."""

    status = (record.review_status or "").strip().lower()
    if status in {"accepted", "reviewed", "reviewed_gold", "canonical", "published"}:
        return "accepted"
    if status in {"not_materialized", "not-materialized"}:
        return "not_materialized"
    if status == "disputed":
        return "disputed"
    return "unknown"


def _registry_source_hashes(root: Path) -> dict[str, str]:
    paths = (WP1_EVIDENCE_PATH, WP1_SOURCES_PATH, S1_ASSERTIONS_PATH, S1_REGISTRATION_PATH, SC1_PATH, HR0_PATH, HR01_PATH)
    return {path.as_posix(): sha256_file(root, path) for path in paths if (root / path).is_file()}


def build_evidence_registry(root: Path = ROOT) -> tuple[dict[str, EvidenceRecord], dict[str, str]]:
    """Build only from explicit, registered evidence indexes."""

    source_doc = read_json(root, WP1_SOURCES_PATH)
    source_records = {
        str(row.get("id")): row
        for row in source_doc.get("records", [])
        if isinstance(row, Mapping) and row.get("id") and row.get("review_status") == "reviewed"
    }
    registry: dict[str, EvidenceRecord] = {}

    wp1 = read_json(root, WP1_EVIDENCE_PATH)
    for row in wp1.get("records", []):
        if not isinstance(row, Mapping) or not row.get("id"):
            continue
        source_id = str(row.get("source_id", ""))
        if source_id not in source_records or str(row.get("evidence_type", "")) not in ALLOWED_WP1_EVIDENCE_TYPES:
            continue
        quote = str(row.get("quote", ""))
        if not quote.strip():
            continue
        layer = {
            "primary_text": "base_text",
            "annotation": "liu_annotation",
            "editorial": "editorial",
        }[str(row.get("evidence_type"))]
        ref = str(row["id"])
        registry[ref] = EvidenceRecord(
            evidence_ref=ref,
            source=_source_label(row, source_records),
            source_layer=layer,
            locator=_safe_locator(row.get("locator")),
            quote=quote,
            searchable_text=" ".join(
                [
                    quote,
                    str(row.get("locator", {}).get("entry_id", "")) if isinstance(row.get("locator"), Mapping) else "",
                    str(row.get("locator", {}).get("chapter_id", "")) if isinstance(row.get("locator"), Mapping) else "",
                ]
            ),
            source_path=WP1_EVIDENCE_PATH.as_posix(),
            assertion_status=str(row.get("assertion_status")) if row.get("assertion_status") else None,
            review_status=str(row.get("review_status")) if row.get("review_status") else None,
        )

    s1 = read_json(root, S1_ASSERTIONS_PATH)
    for row in s1.get("records", []):
        if not isinstance(row, Mapping) or not row.get("assertion_id"):
            continue
        quote = str(row.get("text", ""))
        if not quote.strip():
            continue
        layer = LAYER_ALIASES.get(str(row.get("layer", "")), "other_scholar_note")
        ref = str(row["assertion_id"])
        registry[ref] = EvidenceRecord(
            evidence_ref=ref,
            source="世说新语笺疏 · shishuo-jianshu-yujiaxi-local",
            source_layer=layer,
            locator=_safe_locator(row.get("source_locator")),
            quote=quote,
            searchable_text=" ".join(
                [quote, str(row.get("attribution", "")), str(row.get("story_id", "")), str(row.get("quoted_source", ""))]
            ),
            source_path=S1_ASSERTIONS_PATH.as_posix(),
            assertion_status=str(row.get("modality")) if row.get("modality") else None,
            review_status=str(row.get("canonicalization_status")) if row.get("canonicalization_status") else None,
            attribution=str(row.get("attribution")) if row.get("attribution") else None,
            quoted_source=str(row.get("quoted_source")) if row.get("quoted_source") else None,
        )

    if len(registry) != len(set(registry)):
        raise ValueError("duplicate evidence_ref in controlled registry")
    return {key: registry[key] for key in sorted(registry)}, _registry_source_hashes(root)


class LocalEvidenceSearch:
    """Bounded search session with an explicit open allowlist."""

    def __init__(
        self,
        registry: Mapping[str, EvidenceRecord],
        *,
        max_total_chars: int = MAX_TOTAL_RETURNED_CHARS,
        story_id: str = STORY_ID,
    ):
        self.registry = dict(registry)
        self.max_total_chars = max_total_chars
        self.story_id = story_id
        self.returned_refs: set[str] = set()
        self.opened_refs: set[str] = set()
        self.total_returned_chars = 0

    def _check_budget(self, value: str) -> bool:
        if self.total_returned_chars + len(value) > self.max_total_chars:
            return False
        self.total_returned_chars += len(value)
        return True

    def search(
        self,
        query: str,
        *,
        entity_hints: Sequence[str] = (),
        source_layers: Sequence[str] = (),
        top_k: int = MAX_TOP_K,
        deduplicate: bool = False,
    ) -> dict[str, Any]:
        query = query.strip()
        if not query or len(query) > MAX_QUERY_CHARS:
            raise ValueError("query must be non-empty and at most 240 characters")
        if len(entity_hints) > MAX_ENTITY_HINTS:
            raise ValueError("too many entity_hints")
        if len(source_layers) > MAX_SOURCE_LAYERS:
            raise ValueError("too many source_layers")
        if not isinstance(top_k, int) or isinstance(top_k, bool) or not 1 <= top_k <= MAX_TOP_K:
            raise ValueError("top_k must be an integer from 1 to 5")
        normalized_layers = {LAYER_ALIASES.get(str(layer), str(layer)) for layer in source_layers}
        invalid_layers = sorted(normalized_layers - ALLOWED_SOURCE_LAYERS)
        if invalid_layers:
            raise ValueError("unsupported source_layers: " + ", ".join(invalid_layers))

        query_fold = _fold(query)
        query_terms = set(_text_terms(query))
        hint_folds = [_fold(str(hint)) for hint in entity_hints if str(hint).strip()]
        scored: list[tuple[int, str, EvidenceRecord]] = []
        for ref, record in self.registry.items():
            if normalized_layers and record.source_layer not in normalized_layers:
                continue
            haystack = _fold(record.searchable_text)
            score = 0
            if query_fold and query_fold in haystack:
                score += 20
            for term in query_terms:
                if term in haystack:
                    score += 2 if len(term) <= 2 else 4
            for hint in hint_folds:
                if hint and hint in haystack:
                    score += 8
            entry_id = str(record.locator.get("entry_id", ""))
            chapter_id = str(record.locator.get("chapter_id", ""))
            if self.story_id in haystack or self.story_id == entry_id:
                score += 3
            if entry_id == self.story_id:
                score += 8
            if chapter_id and chapter_id in query_fold:
                score += 3
            if score:
                scored.append((score, ref, record))
        scored.sort(key=lambda item: (-item[0], item[1]))

        raw_match_count = len(scored)
        if deduplicate:
            best_by_key: dict[str, tuple[int, str, EvidenceRecord]] = {}
            for score, ref, record in scored:
                duplicate_key = "|".join(
                    (
                        _fold(record.source),
                        stable_json(record.locator),
                        re.sub(r"\s+", "", _fold(record.quote)),
                    )
                )
                if duplicate_key not in best_by_key:
                    best_by_key[duplicate_key] = (score, ref, record)
            scored = sorted(best_by_key.values(), key=lambda item: (-item[0], item[1]))

        hits: list[dict[str, Any]] = []
        for score, ref, record in scored[:top_k]:
            snippet = record.quote[:MAX_SEARCH_QUOTE_CHARS]
            if not self._check_budget(snippet):
                break
            self.returned_refs.add(ref)
            hits.append(record.public(score=score, quote_limit=MAX_SEARCH_QUOTE_CHARS))
        result: dict[str, Any] = {"query": query, "hits": hits, "result_count": len(hits)}
        if deduplicate:
            result["raw_match_count"] = raw_match_count
            result["deduplicated_match_count"] = len(scored)
            result["duplicate_match_count"] = raw_match_count - len(scored)
        return result

    def open(self, evidence_ref: str) -> dict[str, Any]:
        if evidence_ref not in self.returned_refs:
            raise ValueError("evidence_ref must have been returned by search_local_evidence")
        record = self.registry.get(evidence_ref)
        if record is None:
            raise ValueError("unknown evidence_ref")
        quote = record.quote[:MAX_OPEN_QUOTE_CHARS]
        if not self._check_budget(quote):
            raise ValueError("evidence return budget exceeded")
        self.opened_refs.add(evidence_ref)
        return record.public(quote_limit=MAX_OPEN_QUOTE_CHARS)


def build_story_minimal_input(root: Path = ROOT, story_id: str = STORY_ID) -> dict[str, Any]:
    sc1 = read_json(root, SC1_PATH)
    story = next((row for row in sc1.get("stories", []) if row.get("id") == story_id), None)
    if not isinstance(story, Mapping):
        raise ValueError(f"story not found: {story_id}")
    people = {str(row.get("id")): row for row in sc1.get("people", []) if row.get("id")}
    mentions = {str(row.get("id")): row for row in sc1.get("mentions", []) if row.get("id")}

    participant_map: dict[tuple[str, str], dict[str, Any]] = {}
    for mention_id in story.get("mention_ids", []):
        mention = mentions.get(str(mention_id))
        if not isinstance(mention, Mapping) or not mention.get("person_id"):
            continue
        if mention.get("section") not in {None, "main_text", "main"}:
            continue
        person_id = str(mention["person_id"])
        surface = str(mention.get("surface", mention.get("text", "")))
        participant_map[(person_id, surface)] = {
            "person_id": person_id,
            "canonical_name": str(people.get(person_id, {}).get("canonical_name", person_id)),
            "surface": surface,
            "mention_role": str(mention.get("role", "resolved_mention")),
            "resolution_status": str(mention.get("resolution_status", "resolved")),
        }

    # HR0.1 is used only to expose reviewed identity/presence labels, never its
    # expected effects or gold interpretations.
    hr0 = read_json(root, HR0_PATH)
    hr01 = read_json(root, HR01_PATH)
    hr0_record = next((row for row in hr0.get("records", []) if row.get("story_id") == story_id), {})
    hr01_record = next((row for row in hr01.get("records", []) if row.get("story_id") == story_id), {})
    resolved = hr01_record.get("evidence_resolved_gold", {}) if isinstance(hr01_record, Mapping) else {}
    for row in resolved.get("participant_states", hr0_record.get("participant_states", [])):
        if not isinstance(row, Mapping) or not row.get("person_id"):
            continue
        person_id = str(row["person_id"])
        surface = str(row.get("surface", ""))
        participant_map.setdefault(
            (person_id, surface),
            {
                "person_id": person_id,
                "canonical_name": str(people.get(person_id, {}).get("canonical_name", person_id)),
                "surface": surface,
                "mention_role": str(row.get("role", "reviewed_participant")),
                "resolution_status": str(row.get("resolution_status", "reviewed")),
            },
        )

    temporal = story.get("temporal_orientation", {})
    if isinstance(temporal, Mapping):
        temporal_value = {
            "original": str(temporal.get("original", "")),
            "simplified": str(temporal.get("simplified", temporal.get("original", ""))),
        }
    else:
        temporal_value = {"original": "", "simplified": ""}
    return {
        "schema": "ds1-2-minimal-story-input",
        "schema_version": 1,
        "story_id": story_id,
        "chapter": str(story.get("chapter_heading", story.get("chapter_display", ""))),
        "story_text_original": str(story.get("reading", {}).get("main_text", {}).get("original", story.get("text", ""))),
        "reviewed_participants": [participant_map[key] for key in sorted(participant_map)],
        "broad_temporal_orientation": temporal_value,
    }


def build_minimal_story_input(root: Path = ROOT, story_id: str = STORY_ID) -> dict[str, Any]:
    """Preserve the DS1.2 single-Story contract."""

    if story_id != STORY_ID:
        raise ValueError(f"DS1.2 is intentionally scoped to {STORY_ID}, not {story_id}")
    return build_story_minimal_input(root, story_id)


DS1_2_TOOLS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "search_local_evidence",
            "description": "Search only registered local Shishuo historical evidence. Retrieval scores are ranking signals, not historical truth.",
            "parameters": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "query": {"type": "string", "minLength": 1, "maxLength": MAX_QUERY_CHARS},
                    "entity_hints": {"type": "array", "items": {"type": "string", "maxLength": 80}, "maxItems": MAX_ENTITY_HINTS},
                    "source_layers": {
                        "type": "array",
                        "items": {"type": "string", "enum": sorted(ALLOWED_SOURCE_LAYERS)},
                        "maxItems": MAX_SOURCE_LAYERS,
                    },
                    "top_k": {"type": "integer", "minimum": 1, "maximum": MAX_TOP_K},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "open_local_evidence",
            "description": "Open a larger context window only for an evidence_ref previously returned by search_local_evidence.",
            "parameters": {
                "type": "object",
                "additionalProperties": False,
                "properties": {"evidence_ref": {"type": "string", "minLength": 1, "maxLength": 200}},
                "required": ["evidence_ref"],
            },
        },
    },
]


SYSTEM_PROMPT = """You are performing cautious historical-context reconstruction for one Shishuo story.
The Story text tells you what happens in the scene. Your task is to determine what is not explicit in that scene but is needed to understand the participants' historical and relationship positions.
Use the local evidence tools when context is missing. You must search before the final synthesis; search iteratively if a returned source creates a new historical question. Do not use pretrained knowledge as evidence, and do not browse or invent retrieval.
Distinguish textual fact, historical evidence, supported inference, and uncertainty. Do not write literary appreciation, 余韵, or authorial-intent claims.
Every substantive final claim must cite evidence_ref values actually returned by a tool call. If evidence is insufficient, abstain with null text or an explicit uncertainty that does not pretend to resolve the gap.
When you are ready, return JSON only with exactly these top-level fields:
historical_preconditions, participant_historical_states, relationship_state_before_scene, reader_needed_context, context_to_text_links, uncertainties.
Use claim objects with text and evidence_refs. participant_historical_states may additionally include person_id. context_to_text_links must contain context, text_span, reading_effect, and evidence_refs. Do not include scores or facts not supported by retrieved evidence.
"""


def build_initial_messages(minimal_input: Mapping[str, Any]) -> list[dict[str, Any]]:
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "user",
            "content": "Start with only this minimal reviewed Story input. Use the controlled local evidence tools before final synthesis.\n\n" + stable_json(minimal_input),
        },
    ]


def parse_json_content(content: str) -> Any:
    text = content.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError as error:
        preview = text[:1000].replace("\n", "\\n")
        raise ValueError(f"final model content is not one JSON object: {preview!r}") from error


def parse_dsml_tool_calls(content: Any) -> list[dict[str, Any]]:
    """Accept the provider's text-wrapped tool-call form when returned.

    The normal OpenAI-compatible response is preferred.  The configured
    DeepSeek endpoint can nevertheless serialize calls as DSML markup inside
    ``message.content``; translating that narrow form keeps the same two-tool
    boundary without exposing a general text-command interpreter.
    """

    if not isinstance(content, str) or "DSML" not in content or "invoke name=" not in content:
        return []
    calls: list[dict[str, Any]] = []
    invoke_pattern = re.compile(r"<[^>]*DSML[^>]*invoke\s+name=\"([^\"]+)\"[^>]*>(.*?)</[^>]*DSML[^>]*invoke>", re.S)
    parameter_pattern = re.compile(
        r"<[^>]*DSML[^>]*parameter\s+name=\"([^\"]+)\"(?:\s+string=\"([^\"]+)\")?[^>]*>(.*?)</[^>]*DSML[^>]*parameter>",
        re.S,
    )
    for index, match in enumerate(invoke_pattern.finditer(content), start=1):
        arguments: dict[str, Any] = {}
        for parameter in parameter_pattern.finditer(match.group(2)):
            name, string_flag, raw_value = parameter.groups()
            value_text = html.unescape(raw_value).strip()
            if string_flag == "true":
                arguments[name] = value_text
            else:
                try:
                    arguments[name] = json.loads(value_text)
                except json.JSONDecodeError as error:
                    raise ValueError(f"DSML tool parameter {name!r} is not valid JSON") from error
        calls.append(
            {
                "id": f"dsml-call-{index}",
                "type": "function",
                "function": {"name": match.group(1), "arguments": arguments},
            }
        )
    return calls


FINAL_FIELDS = (
    "historical_preconditions",
    "participant_historical_states",
    "relationship_state_before_scene",
    "reader_needed_context",
    "context_to_text_links",
    "uncertainties",
)


def _final_claim_errors(value: Any, retrieved: set[str], path: str, fields: set[str] | None = None) -> list[str]:
    errors: list[str] = []
    if not isinstance(value, Mapping):
        return [f"{path} must be an object"]
    required = fields or {"text", "evidence_refs"}
    if set(value) != required:
        errors.append(f"{path} keys must be {sorted(required)}")
        return errors
    refs = value.get("evidence_refs")
    if not isinstance(refs, list) or not all(isinstance(ref, str) for ref in refs):
        errors.append(f"{path}.evidence_refs must be a string array")
        return errors
    orphaned = sorted(set(refs) - retrieved)
    if orphaned:
        errors.append(f"{path} has evidence_refs not retrieved: {', '.join(orphaned)}")
    substantive = any(value.get(key) not in (None, "", []) for key in required if key != "evidence_refs")
    if substantive and not refs:
        errors.append(f"{path} has a substantive claim without retrieved evidence_refs")
    return errors


def validate_final_result(value: Any, retrieved_refs: Iterable[str]) -> list[str]:
    retrieved = {str(ref) for ref in retrieved_refs}
    if not isinstance(value, Mapping) or set(value) != set(FINAL_FIELDS):
        return ["final result top-level keys must be the DS1.2 six fields"]
    errors: list[str] = []
    for field in FINAL_FIELDS:
        rows = value[field]
        if not isinstance(rows, list):
            errors.append(f"{field} must be an array")
            continue
        for index, row in enumerate(rows):
            if field == "participant_historical_states":
                errors.extend(
                    _final_claim_errors(
                        row,
                        retrieved,
                        f"{field}[{index}]",
                        {"person_id", "text", "evidence_refs"},
                    )
                )
            elif field == "context_to_text_links":
                errors.extend(
                    _final_claim_errors(
                        row,
                        retrieved,
                        f"{field}[{index}]",
                        {"context", "text_span", "reading_effect", "evidence_refs"},
                    )
                )
            else:
                errors.extend(_final_claim_errors(row, retrieved, f"{field}[{index}]"))
    return sorted(errors)


def input_hash(value: Any) -> str:
    return hashlib.sha256(stable_json(value).encode("utf-8")).hexdigest()


def protected_hashes(root: Path = ROOT) -> dict[str, str]:
    paths = (
        Path("data/derived/sc1-site.json"),
        Path("data/derived/hr0-historical-situations.json"),
        Path("data/derived/hr0-1-ambiguity-benchmark.json"),
        Path("data/derived/h0c-historical-facts.json"),
        Path("data/derived/x1-2rf-materialized-facts.json"),
        Path("data/derived/s1-jianshu-historical-assertions.json"),
        Path("data/generated/ds1/27-jiajue-008-context.json"),
        Path("data/generated/ds1/27-jiajue-008.json"),
        Path("data/annotation/ds1-review.json"),
    )
    return {path.as_posix(): sha256_file(root, path) for path in paths if (root / path).is_file()}


def call_args(raw: Any) -> dict[str, Any]:
    if isinstance(raw, str):
        try:
            value = json.loads(raw)
        except json.JSONDecodeError as error:
            # Some OpenAI-compatible gateways append a stray delimiter or
            # duplicate whitespace after the JSON object.  Decode one object
            # without accepting arbitrary text as arguments.
            decoder = json.JSONDecoder()
            try:
                value, end = decoder.raw_decode(raw.lstrip())
            except json.JSONDecodeError:
                preview = raw[:500].replace("\n", "\\n")
                raise ValueError(f"tool arguments are not valid JSON: {preview!r}") from error
            if raw.lstrip()[end:].strip():
                # A single object followed by a duplicate closing delimiter
                # is recoverable; any other trailing payload is rejected.
                trailing = raw.lstrip()[end:].strip()
                if trailing not in {"}", "]"}:
                    raise ValueError("tool arguments contain trailing data") from error
    else:
        value = raw
    if not isinstance(value, Mapping):
        raise ValueError("tool arguments must be an object")
    return dict(value)


def validate_tool_call(name: str, arguments: Mapping[str, Any]) -> None:
    if name == "search_local_evidence":
        query = arguments.get("query")
        if not isinstance(query, str) or not query.strip() or len(query) > MAX_QUERY_CHARS:
            raise ValueError("invalid search query")
        hints = arguments.get("entity_hints", [])
        layers = arguments.get("source_layers", [])
        if not isinstance(hints, list) or len(hints) > MAX_ENTITY_HINTS or not all(isinstance(item, str) for item in hints):
            raise ValueError("invalid entity_hints")
        if not isinstance(layers, list) or len(layers) > MAX_SOURCE_LAYERS or not all(isinstance(item, str) for item in layers):
            raise ValueError("invalid source_layers")
        top_k = arguments.get("top_k", MAX_TOP_K)
        if not isinstance(top_k, int) or isinstance(top_k, bool) or not 1 <= top_k <= MAX_TOP_K:
            raise ValueError("invalid top_k")
        return
    if name == "open_local_evidence":
        ref = arguments.get("evidence_ref")
        if not isinstance(ref, str) or not ref.strip() or len(ref) > 200:
            raise ValueError("invalid evidence_ref")
        return
    raise ValueError(f"unsupported tool: {name}")


def run_tool_loop(
    *,
    messages: list[dict[str, Any]],
    search: LocalEvidenceSearch,
    model_call: Callable[..., Mapping[str, Any]],
    tools: Sequence[Mapping[str, Any]] = DS1_2_TOOLS,
    max_tool_rounds: int = MAX_TOOL_ROUNDS,
    model: str = MODEL,
    thinking: Mapping[str, Any] | None = None,
) -> tuple[Any, list[dict[str, Any]], dict[str, Any]]:
    """Run a bounded OpenAI-compatible tool loop.

    ``model_call`` is injected so tests can exercise the loop without an API
    call.  The production runner passes ``call_deepseek``.
    """

    if not 1 <= max_tool_rounds <= MAX_TOOL_ROUNDS:
        raise ValueError(f"max_tool_rounds must be between 1 and {MAX_TOOL_ROUNDS}")
    trace_steps: list[dict[str, Any]] = []
    tool_rounds = 0
    tool_calls = 0
    usage_records: list[dict[str, Any]] = []
    final_response: Mapping[str, Any] | None = None
    forced_finalization = False

    while True:
        if tool_rounds >= max_tool_rounds and not forced_finalization:
            messages.append(
                {
                    "role": "user",
                    "content": (
                        "The local-evidence budget is exhausted. Do not call any tool. "
                        "Synthesize the final JSON now using only evidence already returned. "
                        "Preserve uncertainty and cite retrieved evidence_ref values."
                    ),
                }
            )
            forced_finalization = True
        response = model_call(
            messages,
            model=model,
            temperature=0,
            tools=tools if tool_rounds < max_tool_rounds else None,
            tool_choice="auto" if tool_rounds < max_tool_rounds else None,
            response_format={"type": "json_object"} if forced_finalization else None,
            thinking=thinking,
        )
        if response.get("usage"):
            usage_records.append(dict(response["usage"]))
        choices = response.get("choices")
        if not isinstance(choices, list) or not choices or not isinstance(choices[0], Mapping):
            raise ValueError("DeepSeek response has no choice")
        assistant = choices[0].get("message")
        if not isinstance(assistant, Mapping):
            raise ValueError("DeepSeek response has no assistant message")
        assistant_message = dict(assistant)
        raw_tool_calls = assistant.get("tool_calls", [])
        if not raw_tool_calls:
            raw_tool_calls = parse_dsml_tool_calls(assistant.get("content"))
            if raw_tool_calls:
                assistant_message["tool_calls"] = raw_tool_calls
        messages.append(assistant_message)
        if not raw_tool_calls:
            content = assistant.get("content")
            if not isinstance(content, str) or not content.strip():
                raise ValueError("DeepSeek stopped without final JSON content")
            try:
                final_response = parse_json_content(content)
            except (ValueError, json.JSONDecodeError):
                # One no-tools JSON repair turn is permitted; it cannot search
                # and therefore cannot exceed the retrieval round budget.
                messages.append({"role": "user", "content": "Return only the required final JSON object. Do not call tools."})
                repaired = model_call(
                    messages,
                    model=model,
                    temperature=0,
                    response_format={"type": "json_object"},
                    tools=None,
                    tool_choice=None,
                    thinking=thinking,
                )
                if repaired.get("usage"):
                    usage_records.append(dict(repaired["usage"]))
                repaired_message = repaired.get("choices", [{}])[0].get("message", {})
                messages.append(dict(repaired_message))
                final_content = repaired_message.get("content")
                if not isinstance(final_content, str):
                    raise ValueError("DeepSeek JSON repair returned no content")
                final_response = parse_json_content(final_content)
            break

        if tool_rounds >= max_tool_rounds:
            raise ValueError("DeepSeek requested another tool round after max_tool_rounds")
        tool_rounds += 1
        for raw_call in raw_tool_calls:
            if not isinstance(raw_call, Mapping):
                raise ValueError("malformed tool call")
            function = raw_call.get("function")
            if not isinstance(function, Mapping):
                raise ValueError("malformed tool function")
            name = str(function.get("name", ""))
            arguments = call_args(function.get("arguments", {}))
            tool_call_id = str(raw_call.get("id", f"tool-call-{tool_calls + 1}"))
            step: dict[str, Any] = {
                "step": len(trace_steps) + 1,
                "round": tool_rounds,
                "tool_call_id": tool_call_id,
                "tool_name": name,
                "arguments": arguments,
                "token_usage": dict(response.get("usage", {})) if isinstance(response.get("usage", {}), Mapping) else {},
                "model_query": arguments.get("query") if name == "search_local_evidence" else None,
                "entity_hints": arguments.get("entity_hints", []) if name == "search_local_evidence" else [],
                "source_layers": arguments.get("source_layers", []) if name == "search_local_evidence" else [],
                "returned_evidence_refs": [],
                "returned_scores": {},
                "evidence_refs_opened": [],
                "open_status": "not_applicable" if name == "search_local_evidence" else "pending",
                "returned_hits": [],
                "opened_results": [],
            }
            try:
                validate_tool_call(name, arguments)
                if name == "search_local_evidence":
                    result = search.search(
                        str(arguments["query"]),
                        entity_hints=arguments.get("entity_hints", []),
                        source_layers=arguments.get("source_layers", []),
                        top_k=arguments.get("top_k", MAX_TOP_K),
                    )
                    step["returned_evidence_refs"] = [hit["evidence_ref"] for hit in result["hits"]]
                    step["returned_scores"] = {hit["evidence_ref"]: hit.get("score") for hit in result["hits"]}
                    step["returned_hits"] = result["hits"]
                    for key in ("raw_match_count", "deduplicated_match_count", "duplicate_match_count"):
                        if key in result:
                            step[key] = result[key]
                else:
                    result = search.open(str(arguments["evidence_ref"]))
                    step["evidence_refs_opened"] = [str(arguments["evidence_ref"])]
                    step["opened_results"] = [result]
                    step["open_status"] = "success"
                tool_content = stable_json(result)
            except (ValueError, TypeError, KeyError) as error:
                tool_content = stable_json({"error": str(error), "tool_name": name})
                step["error"] = str(error)
                if name == "open_local_evidence":
                    step["open_status"] = "rejected"
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tool_call_id,
                    "name": name,
                    "content": tool_content,
                }
            )
            trace_steps.append(step)
            tool_calls += 1

    if final_response is None:
        raise ValueError("no final response")
    return final_response, trace_steps, {
        "tool_rounds": tool_rounds,
        "tool_calls": tool_calls,
        "usage_records": usage_records,
        "returned_evidence_refs": sorted(search.returned_refs),
        "opened_evidence_refs": sorted(search.opened_refs),
        "total_returned_chars": search.total_returned_chars,
    }


def source_hashes(root: Path = ROOT) -> dict[str, str]:
    return _registry_source_hashes(root)
