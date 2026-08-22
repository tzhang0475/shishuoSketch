#!/usr/bin/env python3
"""Contracts for the SRM0.2M layered-commentary reading pilot."""

from __future__ import annotations

import hashlib
import json
import re
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

try:
    from .ds1_common import ROOT, read_json, sha256_file, stable_json, write_json
    from .srm0_2b_common import ENTRY_PATH, load_entry
except ImportError:  # pragma: no cover - direct script execution
    from ds1_common import ROOT, read_json, sha256_file, stable_json, write_json
    from srm0_2b_common import ENTRY_PATH, load_entry


STORY_ID = "03-zhengshi-005"
S1_ASSERTIONS_PATH = Path("data/derived/s1-jianshu-historical-assertions.json")
S1_CITATIONS_PATH = Path("data/derived/s1-jianshu-source-citations.json")
OUTPUT_ROOT = Path("data/generated/srm0") / STORY_ID / "layered-commentary"
REVIEW_PATH = Path("data/annotation/srm0-2m-layered-commentary-review.json")
BASELINE_ROOT = Path("data/generated/srm0") / STORY_ID / "discovery"
MODEL = "deepseek-v4-flash"
PROVIDER = "deepseek"
PROMPT_VERSION = "srm0.2m-layered-commentary-v1"
SCHEMA_VERSION = 1
MAX_READING_QUESTIONS = 3
MAX_COMMENTARY_ISSUES = 3
MAX_CONNECTIONS = 4
MAX_APPRAISALS = 4
JIANSU_CHAR_LIMIT = 2500

SYSTEM_PROMPT = """你正在第一次阅读一则《世说新语》。

材料分为三层：
1. 正文：当前真正要理解的对象；
2. 刘孝标注：早期注释和史料补充；
3. 余嘉锡《笺疏》：后世考辨、引证和解释。

注释可以帮助你理解正文，但不要因为注释更长，就把与正文阅读关系较弱的考据问题自动列为最重要的问题。

首先从正文中找出至多三个真正值得进一步研究的地方。每个主要问题必须绑定一段准确的正文文字，并说明：
- 为什么仅凭正文仍不容易充分理解；
- 刘注或笺疏提供了什么线索；
- 如果进一步查清，会怎样改变对这段正文的理解。

如果刘注或笺疏自身出现版本、作者、史源等值得考证的问题，可以另列为 commentary_issue，但不要与主要的正文阅读问题混为一类。

同时记录材料中明确显示或值得进一步核查的人物联系，以及有明确来源的人物评价。

不使用提供材料之外的历史知识。不搜索。不作最终历史断言。不把同现、同姓或推测自动当成人物关系。不把后来的材料自动作为先前行为的原因。

只返回 JSON，顶层字段必须是 reading_questions、commentary_issues、person_connections、appraisals。
reading_questions 最多 3 项；commentary_issues 最多 3 项；person_connections 最多 4 项；appraisals 最多 4 项。
不要输出问题分类、关系类别、搜索词、最终答案、事实数据库字段或 canonical 写回字段。"""

TOP_LEVEL_FIELDS = {"reading_questions", "commentary_issues", "person_connections", "appraisals"}
VALID_EVIDENCE_REFS = {"MAIN"}
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
    "claim_updates",
    "claims",
    "evidence_refs",
    "canonical_fact",
    "canonical_status",
    "is_canonical",
    "canonical_write_back",
    "person_id",
    "relation_id",
    "fact_id",
}
DYNAMIC_WORDS = ("关系密切", "亲密", "信任", "支配", "畏惧", "恐惧", "敌意", "dominance", "intimacy", "trust")
SAME_SURNAME_WORDS = ("同姓", "同族", "同宗", "同氏")
FUTURE_CONTACT_WORDS = ("将来", "后来", "后世", "必与", "将与", "将来会")
EXPLICIT_CONNECTION_MARKERS = (
    "善",
    "友",
    "親",
    "亲",
    "父",
    "子",
    "兄",
    "弟",
    "共",
    "同宿",
    "同僚",
    "荐",
    "薦",
    "任",
    "拜",
    "奉",
    "攻",
    "伐",
    "責",
    "责",
    "交",
)


def _text(value: Any) -> str:
    return str(value or "").strip()


def _walk_keys(value: Any) -> Iterable[str]:
    if isinstance(value, Mapping):
        for key, child in value.items():
            yield str(key)
            yield from _walk_keys(child)
    elif isinstance(value, list):
        for child in value:
            yield from _walk_keys(child)


def _hash(value: Any) -> str:
    return hashlib.sha256(stable_json(value).encode("utf-8")).hexdigest()


def _model_ref(index: int) -> str:
    return f"J{index:02d}"


def _citation_sources(root: Path) -> dict[str, list[str]]:
    if not (root / S1_CITATIONS_PATH).is_file():
        return {}
    document = read_json(root, S1_CITATIONS_PATH)
    result: dict[str, set[str]] = {}
    for row in document.get("records", []) if isinstance(document, Mapping) else []:
        if not isinstance(row, Mapping) or not row.get("assertion_id") or not row.get("normalized_source"):
            continue
        result.setdefault(str(row["assertion_id"]), set()).add(str(row["normalized_source"]))
    return {key: sorted(value) for key, value in sorted(result.items())}


def resolve_jianshu_material(root: Path = ROOT) -> dict[str, Any]:
    """Resolve only structured S1 assertions aligned to this Story."""

    entry = load_entry(root)
    document = read_json(root, S1_ASSERTIONS_PATH)
    rows = [
        row
        for row in document.get("records", [])
        if isinstance(row, Mapping) and row.get("story_id") == STORY_ID and row.get("assertion_id") and row.get("text")
    ]
    rows.sort(key=lambda row: (int((row.get("source_locator") or {}).get("block_index", 10**9)), str(row["assertion_id"])))
    citations = _citation_sources(root)
    notes: list[dict[str, Any]] = []
    for index, row in enumerate(rows, start=1):
        locator = dict(row.get("source_locator") or {})
        local_ref = str(row["assertion_id"])
        notes.append(
            {
                "note_id": _model_ref(index),
                "local_ref": local_ref,
                "layer": str(row.get("layer") or "unknown"),
                "speaker": str(row["attribution"]) if row.get("attribution") else None,
                "source_labels": citations.get(local_ref, []),
                "anchor": None,
                "source_locator": locator,
                "text": str(row["text"]),
                "text_sha256": str(row.get("text_sha256") or _hash(str(row["text"]))),
                "modality": str(row.get("modality") or "unknown"),
                "canonicalization_status": str(row.get("canonicalization_status") or "unknown"),
            }
        )
    jianshu_chars = sum(len(note["text"]) for note in notes)
    mode = "full" if jianshu_chars <= JIANSU_CHAR_LIMIT else "catalogue"
    if mode == "catalogue":
        model_notes = [
            {
                "note_id": note["note_id"],
                "anchor": note["anchor"],
                "speaker": note["speaker"],
                "source_labels": note["source_labels"],
                "layer": note["layer"],
                "preview": note["text"][:140],
                "full_char_count": len(note["text"]),
            }
            for note in notes[:8]
        ]
    else:
        model_notes = [
            {
                "note_id": note["note_id"],
                "anchor": note["anchor"],
                "speaker": note["speaker"],
                "source_labels": note["source_labels"],
                "layer": note["layer"],
                "text": note["text"],
            }
            for note in notes
        ]
    return {
        "story_id": STORY_ID,
        "entry": entry,
        "notes": notes,
        "model_notes": model_notes,
        "jianshu_mode": mode,
        "jianshu_chars": jianshu_chars,
        "source_artifacts": {
            S1_ASSERTIONS_PATH.as_posix(): sha256_file(root, S1_ASSERTIONS_PATH),
            S1_CITATIONS_PATH.as_posix(): sha256_file(root, S1_CITATIONS_PATH) if (root / S1_CITATIONS_PATH).is_file() else None,
            ENTRY_PATH.as_posix(): entry["entry_sha256"],
        },
    }


def build_model_payload(material: Mapping[str, Any]) -> dict[str, Any]:
    entry = material["entry"]
    return {
        "story_id": STORY_ID,
        "primary_text": {"label": "世說新語正文", "text": entry["story_text"]},
        "early_commentary": {
            "label": "劉孝標注",
            "notes": [
                {"note_id": f"L{index:02d}", "anchor": None, "text": row["text"]}
                for index, row in enumerate(entry["liu_annotations"], start=1)
            ],
        },
        "later_commentary": {
            "label": "余嘉錫箋疏",
            "mode": material["jianshu_mode"],
            "notes": material["model_notes"],
        },
    }


def build_messages(material: Mapping[str, Any]) -> list[dict[str, str]]:
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": stable_json(build_model_payload(material))},
    ]


def character_metrics(material: Mapping[str, Any], messages: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    entry = material["entry"]
    payload_chars = len(stable_json(build_model_payload(material)))
    return {
        "main_text_chars": len(str(entry["story_text"])),
        "liu_chars": sum(len(str(row["text"])) for row in entry["liu_annotations"]),
        "jianshu_full_available_chars": int(material["jianshu_chars"]),
        "jianshu_model_chars": sum(len(str(note.get("text") or note.get("preview") or "")) for note in material["model_notes"]),
        "instruction_chars": len(SYSTEM_PROMPT),
        "serialized_payload_chars": payload_chars,
        "serialized_prompt_chars": sum(len(str(message.get("content", ""))) for message in messages),
    }


def _ref_text(ref: str, material: Mapping[str, Any]) -> str:
    if ref == "MAIN":
        return str(material["entry"]["story_text"])
    if ref.startswith("L") and ref[1:].isdigit():
        index = int(ref[1:]) - 1
        rows = material["entry"]["liu_annotations"]
        return str(rows[index]["text"]) if 0 <= index < len(rows) else ""
    if ref.startswith("J") and ref[1:].isdigit():
        index = int(ref[1:]) - 1
        rows = material["notes"]
        return str(rows[index]["text"]) if 0 <= index < len(rows) else ""
    return ""


def allowed_refs(material: Mapping[str, Any]) -> set[str]:
    return {"MAIN"} | {f"L{index:02d}" for index in range(1, len(material["entry"]["liu_annotations"]) + 1)} | {note["note_id"] for note in material["notes"]}


def _refs(value: Any, allowed: set[str]) -> list[str]:
    values: list[Any]
    if isinstance(value, list):
        values = value
    elif value is None:
        values = []
    else:
        values = [value]
    return sorted({str(ref) for ref in values if str(ref) in allowed})


def _compact_text(value: Any) -> str:
    """Remove punctuation/spacing only for deterministic local matching."""

    return re.sub(r"[\s\W_]+", "", str(value or ""), flags=re.UNICODE)


def _match_score(query: str, candidate: str) -> tuple[int, int, int]:
    """Return a small deterministic character-overlap score."""

    q = _compact_text(query)
    c = _compact_text(candidate)
    if not q or not c:
        return (0, 0, 0)
    longest = SequenceMatcher(None, q, c, autojunk=False).find_longest_match(0, len(q), 0, len(c)).size
    common_bigrams = len({q[index : index + 2] for index in range(max(0, len(q) - 1))} & {c[index : index + 2] for index in range(max(0, len(c) - 1))})
    common_trigrams = len({q[index : index + 3] for index in range(max(0, len(q) - 2))} & {c[index : index + 3] for index in range(max(0, len(c) - 2))})
    return (common_trigrams * 4 + common_bigrams * 2 + longest, longest, common_trigrams)


def _infer_refs_from_text(
    value: Any,
    material: Mapping[str, Any],
    *,
    include_main: bool = False,
    limit: int = 4,
) -> list[str]:
    """Resolve provider prose to supplied local refs without adding evidence."""

    query = _text(value)
    if not query:
        return []
    refs = ["MAIN"] if include_main and "正文" in query else []
    candidates: list[tuple[tuple[int, int, int], str]] = []
    ordered_refs = (["MAIN"] if include_main else []) + [
        f"L{index:02d}" for index in range(1, len(material["entry"]["liu_annotations"]) + 1)
    ] + [note["note_id"] for note in material["notes"]]
    for ref in ordered_refs:
        source = _ref_text(ref, material)
        if ref.startswith("J"):
            note = material["notes"][int(ref[1:]) - 1]
            source += " " + " ".join(note.get("source_labels") or []) + " " + str(note.get("speaker") or "")
        score = _match_score(query, source)
        if score[0] >= 8 or score[1] >= 5:
            candidates.append((score, ref))
    candidates.sort(key=lambda item: (-item[0][0], -item[0][1], -item[0][2], item[1]))
    refs.extend(ref for _, ref in candidates if ref not in refs)
    return refs[:limit]


def _default_evidence_needed(clues: Any) -> str:
    clue_text = _text(clues)
    if "版本" in clue_text or "異文" in clue_text:
        return "进一步核对相关版本异文与笺疏考证。"
    if "作者" in clue_text or "潘岳" in clue_text or "潘尼" in clue_text:
        return "进一步核对作者归属相关史料与笺疏考证。"
    return "进一步核对相关刘注、笺疏及其所引史料。"


def _align_primary_span(value: Any, source: str) -> str:
    """Map a provider span that omitted source whitespace back to exact text."""

    candidate = _text(value)
    if not candidate or candidate in source:
        return candidate
    source_chars: list[str] = []
    source_offsets: list[int] = []
    for offset, char in enumerate(source):
        if not char.isspace():
            source_chars.append(char)
            source_offsets.append(offset)
    compact_source = "".join(source_chars)
    compact_candidate = "".join(char for char in candidate if not char.isspace())
    start = compact_source.find(compact_candidate)
    if start < 0 or not compact_candidate:
        return candidate
    end = start + len(compact_candidate) - 1
    return source[source_offsets[start] : source_offsets[end] + 1]


def _raw_clue_rows(value: Any) -> list[Mapping[str, Any]]:
    return [row for row in value if isinstance(row, Mapping)] if isinstance(value, list) else []


def _connection_persons(row: Mapping[str, Any]) -> list[str]:
    raw = row.get("persons")
    if isinstance(raw, list):
        return [_text(item) for item in raw if _text(item)]
    named = [_text(row.get("person_a")), _text(row.get("person_b"))]
    if all(named):
        return named
    connection = _text(row.get("connection"))
    lead = re.split(r"[：:]", connection, maxsplit=1)[0]
    return [part.strip(" ，,。；;：:") for part in re.split(r"[与、及]", lead) if part.strip(" ，,。；;：:")]


def _explicit_basis(refs: Sequence[str], material: Mapping[str, Any]) -> bool:
    text = "".join(_ref_text(ref, material) for ref in refs)
    return any(marker in text for marker in EXPLICIT_CONNECTION_MARKERS)


def normalize_layered(raw: Mapping[str, Any], material: Mapping[str, Any]) -> dict[str, Any]:
    allowed = allowed_refs(material)
    main_text = str(material["entry"]["story_text"])
    reading_questions: list[dict[str, Any]] = []
    raw_questions = raw.get("reading_questions", []) if isinstance(raw.get("reading_questions"), list) else []
    for row in raw_questions:
        if not isinstance(row, Mapping) or len(reading_questions) >= MAX_READING_QUESTIONS:
            continue
        clues_raw = row.get("commentary_clues", row.get("clues", []))
        clues: list[dict[str, str]] = []
        clue_rows = _raw_clue_rows(clues_raw)
        if clue_rows:
            for clue in clue_rows:
                ref = str(clue.get("ref") or "")
                effect = _text(clue.get("effect"))
                if ref in allowed and effect:
                    clues.append({"ref": ref, "effect": effect})
        elif _text(clues_raw):
            clue_text = _text(clues_raw)
            for ref in _infer_refs_from_text(clue_text, material, include_main=False):
                clues.append({"ref": ref, "effect": clue_text})
        reading_questions.append(
            {
                "story_span": _align_primary_span(row.get("story_span") or row.get("span") or row.get("anchor"), main_text),
                "question": _text(row.get("question")),
                "why_it_matters": _text(row.get("why_it_matters") or row.get("why") or row.get("why_unclear")),
                "commentary_clues": clues,
                "reading_change_if_answered": _text(row.get("reading_change_if_answered") or row.get("reading_change") or row.get("impact")),
                "additional_evidence_needed": _text(row.get("additional_evidence_needed") or row.get("needed_sources") or _default_evidence_needed(clues_raw)),
            }
        )

    issues: list[dict[str, Any]] = []
    raw_issues = raw.get("commentary_issues", []) if isinstance(raw.get("commentary_issues"), list) else []
    for row in raw_issues:
        if not isinstance(row, Mapping) or len(issues) >= MAX_COMMENTARY_ISSUES:
            continue
        trigger_ref = str(row.get("trigger_ref") or row.get("note_id") or "")
        if trigger_ref not in allowed:
            inferred = _infer_refs_from_text(row.get("issue") or row.get("detail"), material, include_main=False, limit=1)
            trigger_ref = inferred[0] if inferred else trigger_ref
        trigger_text = _text(row.get("trigger_text"))
        if not trigger_text and trigger_ref in allowed and trigger_ref != "MAIN":
            trigger_text = _ref_text(trigger_ref, material)
        issues.append(
            {
                "issue": _text(row.get("issue")),
                "trigger_ref": trigger_ref if trigger_ref in allowed else trigger_ref,
                "trigger_text": trigger_text,
                "relevance_to_story_reading": row.get("relevance_to_story_reading") if row.get("relevance_to_story_reading") in {"high", "medium", "low"} else "medium",
                "reason": _text(row.get("reason") or row.get("detail")),
            }
        )

    connections: list[dict[str, Any]] = []
    raw_connections = raw.get("person_connections", []) if isinstance(raw.get("person_connections"), list) else []
    for row in raw_connections:
        if not isinstance(row, Mapping) or len(connections) >= MAX_CONNECTIONS:
            continue
        persons = _connection_persons(row)
        observation = _text(row.get("observation") or row.get("connection"))
        raw_basis = row.get("basis_refs") or row.get("basis_ref") or row.get("refs") or row.get("evidence")
        refs = _refs(raw_basis, allowed)
        if not refs and _text(raw_basis):
            refs = _infer_refs_from_text(raw_basis, material, include_main=True)
        strength = row.get("evidence_strength") if row.get("evidence_strength") in {"explicit", "suggested"} else "suggested"
        needs = row.get("needs_verification") if isinstance(row.get("needs_verification"), bool) else True
        basis_text = "".join(_ref_text(ref, material) for ref in refs)
        if any(word in observation for word in DYNAMIC_WORDS + SAME_SURNAME_WORDS + FUTURE_CONTACT_WORDS) or not _explicit_basis(refs, material):
            strength = "suggested"
            needs = True
        if ("潘岳" in observation and "潘尼" in observation and any(word in observation for word in ("作謠", "作谣", "作者", "或云"))):
            continue
        connections.append(
            {
                "persons": persons,
                "observation": observation,
                "basis_refs": refs,
                "evidence_strength": strength,
                "needs_verification": needs,
            }
        )

    appraisals: list[dict[str, Any]] = []
    raw_appraisals = raw.get("appraisals", []) if isinstance(raw.get("appraisals"), list) else []
    for row in raw_appraisals:
        if not isinstance(row, Mapping) or len(appraisals) >= MAX_APPRAISALS:
            continue
        source = _text(row.get("source"))
        ref = str(row.get("basis_ref") or row.get("ref") or "")
        if ref not in allowed:
            inferred = _infer_refs_from_text(source or row.get("appraisal") or row.get("observation"), material, include_main=source == "正文", limit=1)
            ref = inferred[0] if inferred else ref
        evaluator_type = row.get("evaluator_type") if row.get("evaluator_type") in {"named_person", "historical_source", "collective", "later_scholar", "uncertain"} else "uncertain"
        evaluator = _text(row.get("evaluator"))
        if not evaluator:
            if "見劉注" in source or "见刘注" in source:
                evaluator = re.split(r"[，,。]", source)[0]
            elif source:
                evaluator = source
        if evaluator_type == "uncertain" and source:
            evaluator_type = "historical_source" if source == "正文" or "見劉注" in source or "见刘注" in source else "later_scholar" if "嘉錫" in source else "uncertain"
        appraisals.append(
            {
                "evaluator": evaluator,
                "evaluator_type": evaluator_type,
                "target": _text(row.get("target") or row.get("object") or row.get("person")),
                "appraisal_text": _text(row.get("appraisal_text") or row.get("appraisal") or row.get("observation")),
                "basis_ref": ref,
            }
        )

    return {
        "reading_questions": reading_questions,
        "commentary_issues": issues,
        "person_connections": connections,
        "appraisals": appraisals,
    }


def _contains_person_id(value: Any) -> bool:
    if isinstance(value, str):
        return bool(re.search(r"(?:^|\b)person-[A-Za-z0-9_-]+(?:\b|$)", value))
    if isinstance(value, Mapping):
        return any(_contains_person_id(key) or _contains_person_id(child) for key, child in value.items())
    if isinstance(value, list):
        return any(_contains_person_id(child) for child in value)
    return False


def validate_layered(raw: Mapping[str, Any], normalized: Mapping[str, Any], material: Mapping[str, Any]) -> list[str]:
    errors: list[str] = []
    allowed = allowed_refs(material)
    if set(raw) != TOP_LEVEL_FIELDS:
        errors.append("layered result must contain exactly the four required top-level fields")
    for key in _walk_keys(raw):
        if key in FORBIDDEN_KEYS:
            errors.append(f"forbidden layered field: {key}")
    if _contains_person_id(raw):
        errors.append("invented/canonical Person ID present")
    for key, maximum in (("reading_questions", MAX_READING_QUESTIONS), ("commentary_issues", MAX_COMMENTARY_ISSUES), ("person_connections", MAX_CONNECTIONS), ("appraisals", MAX_APPRAISALS)):
        rows = raw.get(key)
        if not isinstance(rows, list):
            errors.append(f"{key} must be an array")
        elif len(rows) > maximum:
            errors.append(f"{key} exceeds maximum of {maximum}")

    main_text = str(material["entry"]["story_text"])
    questions = normalized.get("reading_questions", [])
    for row in questions if isinstance(questions, list) else []:
        if not isinstance(row, Mapping) or any(not _text(row.get(key)) for key in ("story_span", "question", "why_it_matters", "reading_change_if_answered", "additional_evidence_needed")):
            errors.append("reading question has an empty required field")
            continue
        if row["story_span"] not in main_text:
            errors.append("reading question story_span is not exact primary text")
        for clue in row.get("commentary_clues", []):
            if not isinstance(clue, Mapping) or clue.get("ref") not in allowed or not _text(clue.get("effect")):
                errors.append("reading question has an invalid commentary clue")

    issues = normalized.get("commentary_issues", [])
    for row in issues if isinstance(issues, list) else []:
        if not isinstance(row, Mapping) or any(not _text(row.get(key)) for key in ("issue", "trigger_ref", "trigger_text", "reason")):
            errors.append("commentary issue has an empty required field")
            continue
        if row.get("trigger_ref") not in allowed or row.get("trigger_ref") == "MAIN":
            errors.append("commentary issue has an invalid trigger ref")
        elif str(row["trigger_text"]) not in _ref_text(str(row["trigger_ref"]), material):
            errors.append("commentary issue trigger_text is not exact referenced commentary")
        if row.get("relevance_to_story_reading") not in {"high", "medium", "low"}:
            errors.append("commentary issue has invalid relevance")

    connections = normalized.get("person_connections", [])
    for row in connections if isinstance(connections, list) else []:
        if (
            not isinstance(row, Mapping)
            or not isinstance(row.get("persons"), list)
            or len(row.get("persons", [])) < 2
            or any(not _text(person) for person in row.get("persons", []))
            or not _text(row.get("observation"))
            or not isinstance(row.get("basis_refs"), list)
            or not row.get("basis_refs")
            or not set(row.get("basis_refs", [])).issubset(allowed)
            or row.get("evidence_strength") not in {"explicit", "suggested"}
            or not isinstance(row.get("needs_verification"), bool)
        ):
            errors.append("invalid person connection")
            continue
        if any(word in row["observation"] for word in DYNAMIC_WORDS + SAME_SURNAME_WORDS + FUTURE_CONTACT_WORDS):
            if row["evidence_strength"] != "suggested" or row["needs_verification"] is not True:
                errors.append("unqualified dynamic/surname/future-contact relation")

    appraisals = normalized.get("appraisals", [])
    for row in appraisals if isinstance(appraisals, list) else []:
        if (
            not isinstance(row, Mapping)
            or any(not _text(row.get(key)) for key in ("evaluator", "target", "appraisal_text", "basis_ref"))
            or row.get("evaluator_type") not in {"named_person", "historical_source", "collective", "later_scholar", "uncertain"}
            or row.get("basis_ref") not in allowed
        ):
            errors.append("invalid appraisal")
    return sorted(set(errors))


def normalization_repairs(raw: Mapping[str, Any], normalized: Mapping[str, Any]) -> list[dict[str, Any]]:
    repairs: list[dict[str, Any]] = []
    raw_questions = raw.get("reading_questions", []) if isinstance(raw.get("reading_questions"), list) else []
    for index, row in enumerate(raw_questions):
        if not isinstance(row, Mapping) or index >= len(normalized.get("reading_questions", [])):
            continue
        normalized_row = normalized["reading_questions"][index]
        if "anchor" in row and "story_span" not in row:
            repairs.append({"kind": "field_alias", "field": "anchor", "normalized_field": "story_span", "index": index})
        if _text(row.get("anchor") or row.get("story_span")) != normalized_row.get("story_span"):
            repairs.append({"kind": "primary_span_whitespace_alignment", "index": index})
        if "why_unclear" in row and "why_it_matters" not in row:
            repairs.append({"kind": "field_alias", "field": "why_unclear", "normalized_field": "why_it_matters", "index": index})
        if "impact" in row and "reading_change_if_answered" not in row:
            repairs.append({"kind": "field_alias", "field": "impact", "normalized_field": "reading_change_if_answered", "index": index})
        if not _text(row.get("additional_evidence_needed") or row.get("needed_sources")):
            repairs.append({"kind": "defaulted_field", "field": "additional_evidence_needed", "index": index})
        if isinstance(row.get("clues"), str):
            repairs.append({"kind": "provenance_resolution", "field": "commentary_clues", "index": index, "refs": [item.get("ref") for item in normalized_row.get("commentary_clues", [])]})
    raw_connections = raw.get("person_connections", []) if isinstance(raw.get("person_connections"), list) else []
    normalized_observations = {row.get("observation") for row in normalized.get("person_connections", []) if isinstance(row, Mapping)}
    for row in raw_connections:
        if not isinstance(row, Mapping):
            continue
        observation = _text(row.get("observation") or row.get("connection"))
        if "person_a" in row or "person_b" in row:
            repairs.append({"kind": "field_alias", "field": "person_a/person_b", "normalized_field": "persons", "observation": observation})
        if "evidence" in row and not row.get("basis_refs"):
            normalized_row = next((item for item in normalized.get("person_connections", []) if item.get("observation") == observation), None)
            repairs.append({"kind": "provenance_resolution", "field": "evidence", "normalized_field": "basis_refs", "observation": observation, "refs": normalized_row.get("basis_refs", []) if normalized_row else []})
        if observation and observation not in normalized_observations and "潘岳" in observation and "潘尼" in observation:
            repairs.append({"kind": "person_connection_dropped", "reason": "authorship attribution conflict is not a person relation", "observation": observation})
        elif observation and observation in normalized_observations and row.get("evidence_strength") == "explicit":
            normalized_row = next(item for item in normalized["person_connections"] if item.get("observation") == observation)
            if normalized_row.get("evidence_strength") == "suggested":
                repairs.append({"kind": "person_connection_downgraded", "reason": "basis does not establish an explicit relation", "observation": observation})
    raw_issues = raw.get("commentary_issues", []) if isinstance(raw.get("commentary_issues"), list) else []
    for index, row in enumerate(raw_issues):
        if not isinstance(row, Mapping) or index >= len(normalized.get("commentary_issues", [])):
            continue
        if "note_id" in row and "trigger_ref" not in row:
            repairs.append({"kind": "field_alias", "field": "note_id", "normalized_field": "trigger_ref", "index": index})
        if "detail" in row and not row.get("reason"):
            repairs.append({"kind": "field_alias", "field": "detail", "normalized_field": "reason", "index": index})
        if not row.get("trigger_text"):
            repairs.append({"kind": "provenance_resolution", "field": "trigger_text", "index": index})
    raw_appraisals = raw.get("appraisals", []) if isinstance(raw.get("appraisals"), list) else []
    for index, row in enumerate(raw_appraisals):
        if not isinstance(row, Mapping) or index >= len(normalized.get("appraisals", [])):
            continue
        if "person" in row and "target" not in row:
            repairs.append({"kind": "field_alias", "field": "person", "normalized_field": "target", "index": index})
        if "source" in row and "basis_ref" not in row:
            repairs.append({"kind": "provenance_resolution", "field": "source", "normalized_field": "basis_ref", "index": index, "ref": normalized["appraisals"][index].get("basis_ref")})
    return repairs


def review_template() -> dict[str, Any]:
    return {
        "schema": "srm0-2m-layered-commentary-review",
        "schema_version": 1,
        "story_id": STORY_ID,
        "main_text_centrality": None,
        "reading_question_quality": None,
        "liu_usage": None,
        "jianshu_usage": None,
        "commentary_issue_separation": None,
        "person_connection_precision": None,
        "appraisal_precision": None,
        "overinterpretation": None,
        "token_efficiency": None,
        "notes": "",
    }


__all__ = [
    "BASELINE_ROOT",
    "ENTRY_PATH",
    "JIANSU_CHAR_LIMIT",
    "MODEL",
    "OUTPUT_ROOT",
    "PROMPT_VERSION",
    "PROVIDER",
    "REVIEW_PATH",
    "ROOT",
    "S1_ASSERTIONS_PATH",
    "S1_CITATIONS_PATH",
    "STORY_ID",
    "SYSTEM_PROMPT",
    "allowed_refs",
    "build_messages",
    "build_model_payload",
    "character_metrics",
    "load_entry",
    "normalization_repairs",
    "normalize_layered",
    "read_json",
    "resolve_jianshu_material",
    "review_template",
    "stable_json",
    "validate_layered",
    "write_json",
]
