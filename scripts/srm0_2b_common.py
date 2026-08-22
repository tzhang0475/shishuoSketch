#!/usr/bin/env python3
"""Contracts and deterministic packet handling for the SRM0.2B blind pilot.

SRM0.2B deliberately exposes only one canonical Story entry and its Liu
annotations.  It does not import the project's person, relation, fact, Gold,
or prior SRM layers.
"""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

try:
    from .ds1_common import ROOT, sha256_file, stable_json, write_json
    from .srm0_1_common import parse_json_content
except ImportError:  # pragma: no cover - direct script execution
    from ds1_common import ROOT, sha256_file, stable_json, write_json
    from srm0_1_common import parse_json_content


STORY_ID = "03-zhengshi-005"
ENTRY_PATH = Path("content/processed/shishuo/entries/03-zhengshi/entry-005.md")
OUTPUT_ROOT = Path("data/generated/srm0") / STORY_ID / "discovery"
REVIEW_PATH = Path("data/annotation/srm0-2b-discovery-review.json")
MODEL = "deepseek-v4-flash"
PROVIDER = "deepseek"
PROMPT_VERSION = "srm0.2b-blind-discovery-v1"
SCHEMA_VERSION = 1

SYSTEM_PROMPT = """你正在第一次阅读一则《世说新语》正文及刘注。
只根据当前提供的材料观察，不使用外部历史知识补足事实，不搜索，不回答尚无证据的问题。

请指出：
1. 最值得进一步查证的至多三个问题；
2. 当前材料中你注意到的、可能值得进一步确认的人物之间联系；
3. 当前材料中出现的明确或可能的人物评价。

问题必须由正文或刘注中的具体内容触发，而不是泛泛询问人物生平。对每个问题说明：
- 哪段文字触发；
- 为什么值得查；
- 还需要什么类型的史料才能继续判断。

人物联系只描述当前材料显示出的现象，不要把猜测写成事实，不要预设关系类别。
人物评价必须说明谁评价谁、评价依据是什么。如果无法确定评价者或对象，可以明确保留不确定。
此阶段只观察和提问，不搜索，不作最终解释。

只返回 JSON，顶层字段必须是 questions、person_connections、appraisals。
questions 最多 3 项；person_connections 最多 5 项；appraisals 最多 5 项。
不要输出问题分类、关系类别、搜索词、最终答案、事实数据库字段或任何 canonical 写回字段。"""

TOP_LEVEL_FIELDS = {"questions", "person_connections", "appraisals"}
FORBIDDEN_KEYS = {
    "question_type",
    "category",
    "relation_type",
    "relation_category",
    "search_probe",
    "search_probes",
    "probes",
    "active_question",
    "next_question",
    "final_answer",
    "historical_answer",
    "resolved_answer",
    "claim_updates",
    "claims",
    "evidence_refs",
    "evidence_decisions",
    "canonical_fact",
    "canonical_status",
    "is_canonical",
    "canonical_write_back",
    "person_id",
    "relation_id",
    "fact_id",
}

DISCOVERY_FOLD = str.maketrans(
    {
        "劉": "刘",
        "隱": "隐",
        "晉": "晋",
        "濤": "涛",
        "領": "领",
        "內": "内",
        "宻": "密",
        "爲": "为",
        "為": "为",
        "謠": "谣",
        "賢": "贤",
        "論": "论",
        "處": "处",
        "傳": "传",
        "溫": "温",
        "清": "清",
    }
)


def _hash(value: Any) -> str:
    return hashlib.sha256(stable_json(value).encode("utf-8")).hexdigest()


def _frontmatter_value(text: str, key: str) -> str:
    frontmatter = text.split("---", 2)
    if len(frontmatter) < 3:
        return ""
    match = re.search(rf"^{re.escape(key)}:\s*['\"]?(.*?)['\"]?\s*$", frontmatter[1], flags=re.MULTILINE)
    return match.group(1) if match else ""


def _section(text: str, heading: str) -> str:
    match = re.search(rf"^## {re.escape(heading)}\s*$", text, flags=re.MULTILINE)
    if not match:
        raise ValueError(f"entry is missing section: {heading}")
    remainder = text[match.end() :]
    next_heading = re.search(r"^## ", remainder, flags=re.MULTILINE)
    return remainder[: next_heading.start() if next_heading else None].strip("\n")


def _annotation_rows(text: str) -> list[dict[str, str]]:
    section = _section(text, "Top-level parenthetical annotation blocks")
    matches = list(re.finditer(r"^### (annotation-[0-9]{3})\s*$", section, flags=re.MULTILINE))
    rows: list[dict[str, str]] = []
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(section)
        block = section[match.end() : end].strip("\n")
        parts = re.split(r"\n\s*\n", block, maxsplit=1)
        if len(parts) != 2:
            raise ValueError(f"annotation block has no source text: {match.group(1)}")
        annotation_text = parts[1].strip("\n")
        if not annotation_text:
            raise ValueError(f"annotation block is empty: {match.group(1)}")
        rows.append({"annotation_id": match.group(1), "text": annotation_text})
    return rows


def load_entry(root: Path = ROOT) -> dict[str, Any]:
    path = root / ENTRY_PATH
    text = path.read_text(encoding="utf-8")
    story_text = _section(text, "Main text")
    annotations = _annotation_rows(text)
    chapter = _frontmatter_value(text, "chapter_heading")
    if not chapter:
        raise ValueError("entry has no chapter heading")
    return {
        "story_id": STORY_ID,
        "chapter": chapter,
        "story_text": story_text,
        "liu_annotations": annotations,
        "annotation_count": len(annotations),
        "entry_sha256": sha256_file(root, ENTRY_PATH),
    }


def model_payload(entry: Mapping[str, Any]) -> dict[str, Any]:
    """Return the only content exposed to the model."""

    return {
        "story_id": entry["story_id"],
        "chapter": entry["chapter"],
        "story_text": entry["story_text"],
        "liu_annotations": [
            {"annotation_id": row["annotation_id"], "text": row["text"]}
            for row in entry["liu_annotations"]
        ],
    }


def build_messages(entry: Mapping[str, Any]) -> list[dict[str, str]]:
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": stable_json(model_payload(entry))},
    ]


def character_metrics(entry: Mapping[str, Any], messages: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    story_chars = len(str(entry["story_text"]))
    liu_chars = sum(len(str(row["text"])) for row in entry["liu_annotations"])
    payload_chars = len(stable_json(model_payload(entry)))
    instruction_chars = len(SYSTEM_PROMPT)
    return {
        "story_chars": story_chars,
        "liu_annotation_chars": liu_chars,
        "instruction_chars": instruction_chars,
        "serialized_payload_chars": payload_chars,
        "serialized_prompt_chars": sum(len(str(message.get("content", ""))) for message in messages),
    }


def _source_surfaces(entry: Mapping[str, Any]) -> tuple[str, ...]:
    return (str(entry["story_text"]),) + tuple(str(row["text"]) for row in entry["liu_annotations"])


def _walk_keys(value: Any) -> Iterable[str]:
    if isinstance(value, Mapping):
        for key, child in value.items():
            yield str(key)
            yield from _walk_keys(child)
    elif isinstance(value, list):
        for child in value:
            yield from _walk_keys(child)


def _contains_person_id(value: Any) -> bool:
    if isinstance(value, str):
        return bool(re.search(r"(?:^|\b)person-[A-Za-z0-9_-]+(?:\b|$)", value))
    if isinstance(value, Mapping):
        return any(_contains_person_id(key) or _contains_person_id(child) for key, child in value.items())
    if isinstance(value, list):
        return any(_contains_person_id(child) for child in value)
    return False


def _connection_person_surfaces(value: str) -> list[str]:
    """Extract conservative name surfaces from a model's natural-language lead."""

    lead = re.split(r"[：:]", value, maxsplit=1)[0]
    lead = lead.strip(" ，,。；;：:")
    return [part.strip(" ，,。；;：:") for part in re.split(r"[与、及]", lead) if part.strip(" ，,。；;：:")]


def _fold_for_alignment(value: str) -> list[tuple[str, int]]:
    result: list[tuple[str, int]] = []
    for index, char in enumerate(value):
        folded = unicodedata.normalize("NFKC", char).translate(DISCOVERY_FOLD).lower()
        if "\u3400" <= folded <= "\u9fff":
            result.append((folded, index))
    return result


def _exact_source_trigger(proposed: str, entry: Mapping[str, Any]) -> str:
    surfaces = _source_surfaces(entry)
    if proposed and any(proposed in source for source in surfaces):
        return proposed
    proposed_chars = [char for char, _ in _fold_for_alignment(proposed)]
    best: tuple[int, str] = (0, "")
    for source in surfaces:
        source_chars = _fold_for_alignment(source)
        previous = [0] * (len(source_chars) + 1)
        best_end = (0, 0)
        for proposed_char in proposed_chars:
            current = [0] * (len(source_chars) + 1)
            for source_index, (source_char, _) in enumerate(source_chars, start=1):
                if proposed_char == source_char:
                    current[source_index] = previous[source_index - 1] + 1
                    if current[source_index] > best_end[0]:
                        best_end = (current[source_index], source_index)
            previous = current
        length, end = best_end
        if length > best[0] and end:
            start = end - length
            source_start = source_chars[start][1]
            source_end = source_chars[end - 1][1] + 1
            best = (length, source[source_start:source_end])
    return best[1] if best[0] >= 2 else proposed


def normalize_discovery(raw: Mapping[str, Any], entry: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """Keep only the intentionally weak discovery schema."""

    def text(value: Any) -> str:
        return str(value or "").strip()

    questions: list[dict[str, str]] = []
    for row in raw.get("questions", []) if isinstance(raw.get("questions"), list) else []:
        if not isinstance(row, Mapping) or len(questions) >= 3:
            continue
        trigger = text(row.get("trigger_text") or row.get("trigger"))
        if entry is not None:
            trigger = _exact_source_trigger(trigger, entry)
        questions.append(
            {
                "question": text(row.get("question")),
                "trigger_text": trigger,
                "why_it_matters": text(row.get("why_it_matters") or row.get("why")),
                "what_more_evidence_is_needed": text(row.get("what_more_evidence_is_needed") or row.get("needed_sources")),
            }
        )

    connections: list[dict[str, Any]] = []
    for row in raw.get("person_connections", []) if isinstance(raw.get("person_connections"), list) else []:
        if not isinstance(row, Mapping) or len(connections) >= 5:
            continue
        persons = [text(person) for person in row.get("persons", [])] if isinstance(row.get("persons"), list) else []
        connections.append(
            {
                "persons": persons or _connection_person_surfaces(text(row.get("connection"))),
                "observation": text(row.get("observation") or row.get("connection")),
                "basis": text(row.get("basis") or row.get("evidence")),
                "needs_verification": row.get("needs_verification") if isinstance(row.get("needs_verification"), bool) else True,
            }
        )

    appraisals: list[dict[str, str]] = []
    for row in raw.get("appraisals", []) if isinstance(raw.get("appraisals"), list) else []:
        if not isinstance(row, Mapping) or len(appraisals) >= 5:
            continue
        appraisals.append(
            {
                "evaluator": text(row.get("evaluator")),
                "target": text(row.get("target") or row.get("object")),
                "observation": text(row.get("observation") or row.get("appraisal")),
                "basis": text(row.get("basis")),
            }
        )
    return {"questions": questions, "person_connections": connections, "appraisals": appraisals}


def normalization_repairs(raw: Mapping[str, Any], normalized: Mapping[str, Any]) -> list[dict[str, str]]:
    repairs: list[dict[str, str]] = []
    raw_questions = raw.get("questions", []) if isinstance(raw.get("questions"), list) else []
    normalized_questions = normalized.get("questions", []) if isinstance(normalized.get("questions"), list) else []
    for index, row in enumerate(normalized_questions):
        if index >= len(raw_questions) or not isinstance(raw_questions[index], Mapping):
            continue
        original = str(raw_questions[index].get("trigger_text") or raw_questions[index].get("trigger") or "").strip()
        resolved = str(row.get("trigger_text") or "")
        if original and resolved and original != resolved:
            repairs.append({"field": f"questions[{index}].trigger_text", "from": original, "to": resolved})
    return repairs


def validate_discovery(raw: Mapping[str, Any], normalized: Mapping[str, Any], entry: Mapping[str, Any]) -> list[str]:
    errors: list[str] = []
    if set(raw) != TOP_LEVEL_FIELDS:
        errors.append("discovery output must contain exactly questions, person_connections, appraisals")
    for key, maximum in (("questions", 3), ("person_connections", 5), ("appraisals", 5)):
        raw_rows = raw.get(key)
        if not isinstance(raw_rows, list):
            errors.append(f"{key} must be an array")
        elif len(raw_rows) > maximum:
            errors.append(f"{key} exceeds maximum of {maximum}")
    for key in _walk_keys(raw):
        if key in FORBIDDEN_KEYS:
            errors.append(f"forbidden discovery field: {key}")
    if _contains_person_id(raw):
        errors.append("invented/canonical Person ID present in discovery output")

    questions = normalized.get("questions")
    if not isinstance(questions, list) or len(questions) > 3:
        errors.append("questions must contain at most three items")
    surfaces = _source_surfaces(entry)
    for row in questions if isinstance(questions, list) else []:
        if not isinstance(row, Mapping) or any(not str(row.get(key) or "").strip() for key in ("question", "trigger_text", "why_it_matters", "what_more_evidence_is_needed")):
            errors.append("question has an empty required field")
        elif not any(str(row["trigger_text"]) in source for source in surfaces):
            errors.append("question trigger_text is not an exact supplied source surface")

    connections = normalized.get("person_connections")
    if not isinstance(connections, list) or len(connections) > 5:
        errors.append("person_connections must contain at most five items")
    for row in connections if isinstance(connections, list) else []:
        if (
            not isinstance(row, Mapping)
            or not isinstance(row.get("persons"), list)
            or len(row.get("persons", [])) < 2
            or any(not str(person).strip() for person in row.get("persons", []))
            or not str(row.get("observation") or "").strip()
            or not str(row.get("basis") or "").strip()
            or not isinstance(row.get("needs_verification"), bool)
        ):
            errors.append("invalid person_connections item")

    appraisals = normalized.get("appraisals")
    if not isinstance(appraisals, list) or len(appraisals) > 5:
        errors.append("appraisals must contain at most five items")
    for row in appraisals if isinstance(appraisals, list) else []:
        if not isinstance(row, Mapping) or any(not str(row.get(key) or "").strip() for key in ("evaluator", "target", "observation", "basis")):
            errors.append("appraisal has an empty required field")
    return sorted(set(errors))


def review_template() -> dict[str, Any]:
    return {
        "schema": "srm0-2b-discovery-review",
        "schema_version": 1,
        "story_id": STORY_ID,
        "question_naturalness": None,
        "question_text_grounding": None,
        "question_research_value": None,
        "person_connection_discovery": None,
        "appraisal_discovery": None,
        "overinterpretation": None,
        "restraint": None,
        "token_efficiency": None,
        "notes": "",
    }


def write_json_artifact(root: Path, relative: Path, value: Any) -> None:
    write_json(root, relative, value)


def artifact_hashes(root: Path, names: Sequence[str]) -> dict[str, str]:
    return {name: sha256_file(root, OUTPUT_ROOT / name) for name in sorted(names)}


__all__ = [
    "ENTRY_PATH",
    "MODEL",
    "OUTPUT_ROOT",
    "PROMPT_VERSION",
    "PROVIDER",
    "REVIEW_PATH",
    "ROOT",
    "STORY_ID",
    "SYSTEM_PROMPT",
    "artifact_hashes",
    "build_messages",
    "character_metrics",
    "load_entry",
    "model_payload",
    "normalize_discovery",
    "normalization_repairs",
    "parse_json_content",
    "review_template",
    "stable_json",
    "validate_discovery",
    "write_json_artifact",
    "_hash",
]
