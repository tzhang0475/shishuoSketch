#!/usr/bin/env python3
"""Build the corpus-wide CRL1 Shishuo reading layer.

The builder treats the canonical entry Markdown as the only character
authority.  The local structural TXT supplies punctuation guidance; the
tracked Wikisource comparison views supply same-edition alignment context but
contain no sentence punctuation.  Consequently the current build can produce
``candidate`` punctuation, but cannot promote a machine result to ``aligned``
without a second punctuation-bearing reference.
"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import re
import unicodedata
from typing import Any, Iterable, Mapping

import yaml
from opencc import OpenCC

try:
    from .build_six_person_pilot import parse_shishuo_sections
    from .reading_layers import strip_display_punctuation, validate_punctuation_round_trip
except ImportError:  # pragma: no cover - direct script execution
    from build_six_person_pilot import parse_shishuo_sections
    from reading_layers import strip_display_punctuation, validate_punctuation_round_trip


CORPUS_INDEX = "data/shishuo-corpus-index.json"
PUNCTUATION_DATA = "data/annotation/wp1-punctuation.json"
READING_DATA = "data/derived/shishuo-reading-layer.json"
QUALIFICATION_DATA = "data/reading-source-qualification.json"
REVIEW_QUEUE_JSON = "data/derived/punctuation-review-queue.json"
QUEUE_DATA = "content/curated/shishuo/reading-layer/review-queue.yaml"
QUEUE_MARKDOWN = "content/curated/shishuo/reading-layer/review-queue.md"
AUDIT_MARKDOWN = "docs/corpus-reading-layer-audit.md"
QUALIFICATION_SAMPLE_MARKDOWN = "docs/crl1-1-punctuation-qualification-sample.md"
REFERENCE_TEXT = "sources/local/shishuo/reference-txt/shishuo.txt"
WIKISOURCE_COLLATION = "content/processed/shishuo/collation/wikisource-sbck"

PUNCTUATION_RECORD_ID = "punctuation-06-yaliang-019"
STATUS_VALUES = {"reviewed", "aligned", "candidate", "disputed"}
REVIEW_STATUS_VALUES = {"reviewed", "unreviewed"}
PUNCTUATION_BASIS_VALUES = {
    "human_reviewed",
    "trusted_reference_exact",
    "reference_candidate",
    "disputed",
}

CHINESE_NUMBERS = {
    "一": 1,
    "二": 2,
    "三": 3,
    "四": 4,
    "五": 5,
    "六": 6,
    "七": 7,
    "八": 8,
    "九": 9,
    "十": 10,
    "百": 100,
}
LOCAL_HEADING_RE = re.compile(
    r"^([\u4e00-\u9fff]+?)(?:\[\d+\])?第([一二三四五六七八九十百]+)([上下]?)$"
)
LOCAL_ENTRY_RE = re.compile(r"^(\d+)[\u3000 ]")
REFERENCE_NOTE_RE = re.compile(r"\(\d+\)|\[\d+\]")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def load_punctuation_qualification(root: Path) -> dict[str, Any]:
    document = read_json(root / QUALIFICATION_DATA)
    records = document.get("records", [])
    if len(records) != 1:
        raise ValueError("CRL1.1 currently requires exactly one punctuation qualification record")
    record = records[0]
    if record.get("qualification") not in {"qualified", "provisionally_qualified", "unqualified"}:
        raise ValueError("invalid punctuation source qualification")
    source = record.get("source", {})
    if not source.get("path") or not source.get("sha256"):
        raise ValueError("punctuation qualification lacks source identity")
    return record


def _machine_punctuation_basis(
    *,
    status: str,
    exact_transfer: bool,
    qualification: Mapping[str, Any],
) -> str:
    if status == "disputed" or not exact_transfer and status not in {"candidate", "aligned"}:
        return "disputed"
    if (
        exact_transfer
        and qualification.get("qualification") == "qualified"
        and qualification.get("allows_trusted_reference_promotion") is True
    ):
        return "trusted_reference_exact"
    return "reference_candidate"


def _review_bucket(
    *,
    review_status: str,
    punctuation_basis: str,
    exact_transfer: bool,
    status: str,
    story_reader_ready: bool,
) -> str:
    if story_reader_ready and punctuation_basis in {"human_reviewed", "trusted_reference_exact"}:
        return "A_trusted_reference_ready"
    if (
        review_status == "unreviewed"
        and punctuation_basis == "reference_candidate"
        and exact_transfer
    ):
        return "B_exact_transfer_awaiting_source_qualification"
    if review_status == "unreviewed" and punctuation_basis == "reference_candidate" and status == "candidate":
        return "C_punctuation_review_candidate"
    if status == "disputed" or punctuation_basis == "disputed":
        return "D_disputed_structural_review"
    raise ValueError(
        f"cannot assign CRL1.1 review bucket: {review_status=} {punctuation_basis=} "
        f"{exact_transfer=} {status=} {story_reader_ready=}"
    )


KNOWN_ANOMALY_ENTRY_IDS = {
    "05-fangzheng-014",
    "08-shangyu-084",
    "08-shangyu-085",
    "18-qiyi-002",
    "18-qiyi-011",
    "19-xianyuan-005",
    "18-qiyi-010",
    "18-qiyi-015",
    "25-paidiao-019",
}


def chinese_number(value: str) -> int:
    if "百" in value:
        before, after = value.split("百", 1)
        hundreds = CHINESE_NUMBERS.get(before, 1) if before else 1
        return hundreds * 100 + (chinese_number(after) if after else 0)
    if "十" in value:
        before, after = value.split("十", 1)
        tens = CHINESE_NUMBERS.get(before, 1) if before else 1
        return tens * 10 + (CHINESE_NUMBERS.get(after, 0) if after else 0)
    return CHINESE_NUMBERS[value]


def canonical_main_text(path: Path) -> str:
    for section, body, _metadata in parse_shishuo_sections(path.read_text(encoding="utf-8")):
        if section == "main_text":
            return body.strip("\n")
    raise ValueError(f"canonical entry has no main text: {path}")


def compact_canonical_text(text: str) -> str:
    """Remove only display whitespace from the canonical main section."""

    return "".join(character for character in text if not character.isspace())


def alignment_key(text: str, converter: Any) -> str:
    """Build a comparison-only key; never write this key as source text."""

    return "".join(
        converter.convert(character)
        for character in strip_display_punctuation(text)
    )


def _reference_main_and_punctuation(raw: str) -> dict[str, Any]:
    """Extract one local reference paragraph and its punctuation offsets.

    The local TXT marks Liu annotation references with numeric parentheses or
    brackets.  Those markers are removed for alignment only; the source file
    itself is never changed.
    """

    main = raw.split("\n\n", 1)[0]
    main = REFERENCE_NOTE_RE.sub("", main).strip()
    characters: list[str] = []
    punctuation: list[dict[str, Any]] = []
    offset = 0
    for character in main:
        if character.isspace():
            continue
        if unicodedata.category(character).startswith("P"):
            punctuation.append({"offset": offset, "text": character})
            continue
        characters.append(character)
        offset += 1
    return {
        "text": main,
        "characters": "".join(characters),
        "punctuation": punctuation,
    }


def parse_structural_reference(path: Path) -> dict[tuple[int, int], dict[str, Any]]:
    """Parse the numbered main paragraphs in the local structural witness."""

    lines = path.read_text(encoding="utf-8").splitlines(True)
    headings: list[tuple[int, str]] = []
    for index, line in enumerate(lines):
        if not 180 <= index + 1 <= 8000:
            continue
        if LOCAL_HEADING_RE.match(line.strip()):
            headings.append((index + 1, line.strip()))

    result: dict[tuple[int, int], dict[str, Any]] = {}
    for heading_index, (heading_line, heading) in enumerate(headings):
        match = LOCAL_HEADING_RE.match(heading)
        if match is None:  # pragma: no cover - guarded above
            continue
        chapter_number = chinese_number(match.group(2))
        end_line = (
            headings[heading_index + 1][0]
            if heading_index + 1 < len(headings)
            else len(lines) + 1
        )
        starts: list[tuple[int, int]] = []
        for line_number in range(heading_line, end_line):
            entry_match = LOCAL_ENTRY_RE.match(lines[line_number - 1])
            if entry_match:
                starts.append((line_number, int(entry_match.group(1))))

        for entry_index, (start_line, ordinal) in enumerate(starts):
            stop_line = (
                starts[entry_index + 1][0]
                if entry_index + 1 < len(starts)
                else end_line
            )
            raw = "".join(lines[start_line - 1 : stop_line - 1])
            raw = re.sub(r"^\d+[\u3000 ]", "", raw, count=1)
            result[(chapter_number, ordinal)] = _reference_main_and_punctuation(raw)
    return result


def _reference_record(
    *,
    kind: str,
    witness_id: str,
    path: str,
    sha256: str,
    notes: str,
) -> dict[str, str]:
    return {
        "kind": kind,
        "witness_id": witness_id,
        "path": path,
        "sha256": sha256,
        "notes": notes,
    }


def punctuation_from_reference(canonical_text: str, punctuation: Iterable[Mapping[str, Any]]) -> str:
    """Insert reference punctuation at canonical character offsets."""

    compact = compact_canonical_text(canonical_text)
    by_offset: dict[int, list[str]] = defaultdict(list)
    for item in punctuation:
        by_offset[int(item["offset"])].append(str(item["text"]))
    output: list[str] = []
    for offset in range(len(compact) + 1):
        output.extend(by_offset.get(offset, []))
        if offset < len(compact):
            output.append(compact[offset])
    return "".join(output)


def classify_alignment(
    canonical_text: str,
    reference: Mapping[str, Any] | None,
    converter: Any,
    *,
    punctuation_reference_count: int = 1,
    punctuation_boundaries: Iterable[Iterable[int]] | None = None,
) -> dict[str, Any]:
    """Classify character alignment and punctuation transferability.

    A one-to-one comparison can transfer punctuation offsets even when the
    reference uses a different character variant.  Insertions/deletions are
    conservatively disputed rather than repaired by guessing.
    """

    canonical_key = alignment_key(canonical_text, converter)
    if reference is None:
        return {
            "alignment_class": "alignment-failure",
            "transfer_class": "missing_reference",
            "reference_case": "no_usable_reference",
            "status": "disputed",
            "reason_codes": ["structural_alignment_failure"],
            "canonical_character_count": len(canonical_key),
            "reference_character_count": 0,
            "mismatch_offsets": [],
            "punctuation_reference_count": 0,
        }

    reference_key = str(reference["characters"])
    mismatch_offsets = [
        index
        for index, (left, right) in enumerate(zip(canonical_key, reference_key))
        if left != right
    ]
    if len(canonical_key) == len(reference_key):
        if mismatch_offsets:
            alignment_class = "character-disagreement"
            transfer_class = "character_mismatch_around_punctuation"
            reference_case = "single_reference_character_variant"
            reason_codes = ["reference_character_variant"]
        else:
            alignment_class = "exact-agreement"
            transfer_class = "exact_character_transfer"
            reference_case = (
                "single_reference_but_exact"
                if punctuation_reference_count < 2
                else "exact_reference_agreement"
            )
            reason_codes = ["exact_reference_agreement"]
        boundary_sets = [set(boundaries) for boundaries in (punctuation_boundaries or [])]
        if len(boundary_sets) >= 2 and any(item != boundary_sets[0] for item in boundary_sets[1:]):
            transfer_class = "punctuation_boundary_disagreement"
            reference_case = "punctuation_reference_disagreement"
            reason_codes.append("punctuation_boundary_disagreement")
            status = "disputed"
        else:
            if punctuation_reference_count < 2:
                reason_codes.append("single_reference_only")
            status = "aligned" if punctuation_reference_count >= 2 else "candidate"
        return {
            "alignment_class": alignment_class,
            "transfer_class": transfer_class,
            "reference_case": reference_case,
            "status": status,
            "reason_codes": reason_codes,
            "canonical_character_count": len(canonical_key),
            "reference_character_count": len(reference_key),
            "mismatch_offsets": mismatch_offsets,
            "punctuation_reference_count": punctuation_reference_count,
        }

    if len(canonical_key) > len(reference_key):
        reason = "reference_deletion"
    elif len(canonical_key) < len(reference_key):
        reason = "reference_insertion"
    else:  # pragma: no cover - lengths cannot differ here
        reason = "structural_alignment_failure"
    return {
        "alignment_class": "alignment-failure",
        "transfer_class": "structural_or_boundary_mismatch",
        "reference_case": "character_count_mismatch",
        "status": "disputed",
        "reason_codes": [reason, "structural_alignment_failure"],
        "canonical_character_count": len(canonical_key),
        "reference_character_count": len(reference_key),
        "mismatch_offsets": mismatch_offsets,
        "punctuation_reference_count": punctuation_reference_count,
    }


def _new_punctuation_record(
    entry: Mapping[str, Any],
    canonical_text: str,
    reference: Mapping[str, Any] | None,
    assessment: Mapping[str, Any],
    local_reference_path: str,
    local_reference_hash: str,
    wikisource_path: str,
    wikisource_hash: str,
    converter: Any,
    qualification: Mapping[str, Any],
) -> dict[str, Any]:
    status = str(assessment["status"])
    punctuated: str | None = None
    if reference is not None and status in {"candidate", "aligned"}:
        # A canonical source containing source-markup punctuation is not
        # eligible for automatic transfer; it must be reviewed explicitly.
        canonical_markup_punctuation = any(
            not character.isspace()
            and unicodedata.category(character).startswith("P")
            for character in canonical_text
        )
        if not canonical_markup_punctuation:
            punctuated = punctuation_from_reference(canonical_text, reference["punctuation"])

    if punctuated is None and status in {"candidate", "aligned"}:
        assessment = dict(assessment)
        assessment["status"] = "disputed"
        assessment["alignment_class"] = "alignment-failure"
        assessment["reason_codes"] = list(assessment["reason_codes"]) + [
            "structural_alignment_failure"
        ]
        status = "disputed"

    exact_transfer = bool(
        punctuated is not None
        and assessment.get("alignment_class") == "exact-agreement"
        and strip_display_punctuation(punctuated) == compact_canonical_text(canonical_text)
    )
    review_status = "unreviewed"
    punctuation_basis = _machine_punctuation_basis(
        status=status,
        exact_transfer=exact_transfer,
        qualification=qualification,
    )

    return {
        "id": f"crl1-punctuation-{entry['id']}",
        "entry_id": entry["id"],
        "base_canonical_entry_path": entry["path"],
        "base_canonical_entry_sha256": entry["entry_sha256"],
        "status": status,
        "review_status": review_status,
        "punctuation_basis": punctuation_basis,
        "exact_transfer": exact_transfer,
        "source_qualification_id": qualification["id"],
        "references": [
            _reference_record(
                kind="canonical_entry",
                witness_id="shishuo-kanripo-wyg",
                path=str(entry["path"]),
                sha256=str(entry["entry_sha256"]),
                notes="Authoritative canonical entry artifact and character sequence.",
            ),
            _reference_record(
                kind="structural_reference",
                witness_id="shishuo-local-reference-txt",
                path=local_reference_path,
                sha256=local_reference_hash,
                notes=(
                    "Punctuation guidance only. The local witness is simplified-or-mixed; "
                    "its characters never replace the canonical sequence."
                ),
            ),
            _reference_record(
                kind="same_edition_alignment",
                witness_id="shishuo-wikisource-sbck",
                path=wikisource_path,
                sha256=wikisource_hash,
                notes=(
                    "Tracked Wikisource SBCK comparison view for character/structure "
                    "alignment. It contains no sentence punctuation and is not counted "
                    "as a punctuation reference."
                ),
            ),
        ],
        "sections": {
            "main_text": {
                "canonical_text": canonical_text,
                "punctuated_text": punctuated,
                "notes": (
                    "Machine punctuation candidate derived from the local structural "
                    "reference; canonical characters remain authoritative."
                    if punctuated is not None
                    else "No safe machine punctuation transfer was produced; manual review required."
                ),
            }
        },
        "display_overrides": [],
        "alignment": dict(assessment),
        "notes": (
            "CRL1 machine assessment. This record is not human-reviewed and does not "
            "replace the primary Kanripo/SBCK text."
        ),
    }


def _priority(record: Mapping[str, Any]) -> int:
    reasons = set(record.get("alignment", {}).get("reason_codes", []))
    if "structural_alignment_failure" in reasons:
        return 1
    if "punctuation_boundary_disagreement" in reasons:
        return 2
    if "reference_character_variant" in reasons:
        return 3
    if "single_reference_only" in reasons:
        return 4
    return 5


def _yaml_dump(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        yaml.safe_dump(
            value,
            allow_unicode=True,
            sort_keys=False,
            width=120,
            default_flow_style=False,
        ),
        encoding="utf-8",
    )


def _punctuation_complexity(text: str | None) -> tuple[int, int, int]:
    if not text:
        return (0, 0, 0)
    punctuation_count = sum(
        1 for character in text if unicodedata.category(character).startswith("P")
    )
    quotation_count = sum(text.count(mark) for mark in ("「", "」", "『", "』", "《", "》"))
    compact_length = len(strip_display_punctuation(text))
    return (punctuation_count, quotation_count, compact_length)


def select_qualification_sample(
    entries: list[Mapping[str, Any]],
    records_by_entry: Mapping[str, Mapping[str, Any]],
    canonical_texts: Mapping[str, str],
) -> dict[str, str]:
    """Select a deterministic, chapter-stratified human qualification pack."""

    by_chapter: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for entry in entries:
        by_chapter[str(entry["id"]).split("-", 1)[0]].append(entry)

    selected: dict[str, str] = {}

    def available(entry: Mapping[str, Any]) -> bool:
        section = records_by_entry[entry["id"]].get("sections", {}).get("main_text", {})
        return isinstance(section.get("punctuated_text"), str) and bool(section.get("punctuated_text"))

    for chapter in sorted(by_chapter):
        chapter_entries = by_chapter[chapter]
        exact = [
            entry
            for entry in chapter_entries
            if records_by_entry[entry["id"]].get("exact_transfer") is True
        ]
        pool = exact or [entry for entry in chapter_entries if available(entry)] or chapter_entries
        shortest = min(
            pool,
            key=lambda entry: (len(strip_display_punctuation(canonical_texts[entry["id"]])), entry["global_ordinal"]),
        )
        selected.setdefault(shortest["id"], "short_entry")
        remaining = [entry for entry in pool if entry["id"] != shortest["id"]]
        if remaining:
            richest = max(
                remaining,
                key=lambda entry: (
                    _punctuation_complexity(
                        records_by_entry[entry["id"]].get("sections", {}).get("main_text", {}).get("punctuated_text")
                    ),
                    len(strip_display_punctuation(canonical_texts[entry["id"]])),
                    -entry["global_ordinal"],
                ),
            )
            selected.setdefault(richest["id"], "punctuation_complexity")

    for entry in entries:
        if entry["id"] in KNOWN_ANOMALY_ENTRY_IDS:
            selected.setdefault(entry["id"], "known_segmentation_anomaly")

    # The chapter pass normally yields 72 records.  If a chapter has only one
    # usable candidate, fill deterministically from the remaining longest and
    # most punctuation-rich records so the pack still covers all chapters.
    if len(selected) < 72:
        remaining = [entry for entry in entries if entry["id"] not in selected]
        remaining.sort(
            key=lambda entry: (
                _punctuation_complexity(
                    records_by_entry[entry["id"]].get("sections", {}).get("main_text", {}).get("punctuated_text")
                ),
                len(strip_display_punctuation(canonical_texts[entry["id"]])),
                -entry["global_ordinal"],
            ),
            reverse=True,
        )
        for entry in remaining[: 72 - len(selected)]:
            selected[entry["id"]] = "corpus_complexity_fill"
    return selected


def write_qualification_sample(
    root: Path,
    entries: list[Mapping[str, Any]],
    records_by_entry: Mapping[str, Mapping[str, Any]],
    derived_by_entry: Mapping[str, Mapping[str, Any]],
    canonical_texts: Mapping[str, str],
    reference_texts: Mapping[str, str | None],
    sample_reasons: Mapping[str, str],
) -> None:
    entry_by_id = {entry["id"]: entry for entry in entries}
    selected_ids = sorted(
        sample_reasons,
        key=lambda entry_id: entry_by_id[entry_id]["global_ordinal"],
    )
    lines = [
        "# CRL1.1 句读来源资格抽样包",
        "",
        "本文件由 `scripts/build_shishuo_reading_layer.py` 确定性生成，供人工检查本地 structural-reference TXT 是否足以承担全书句读参考作用。它不把任何机器候选标记为人工 reviewed。",
        "",
        f"- 抽样条目：{len(selected_ids)}",
        "- 覆盖章节：36",
        "- 选择方式：每章优先选择最短条目与句读复杂度最高的条目；另列已知结构异常条目。",
        "- 资格结论：本地 TXT 当前仅为 `provisionally_qualified`，抽样不改变该结论。",
        "",
        "## 判定说明",
        "",
        "`exact_transfer` 只表示去除句读后本地参考字符与 canonical 字符序列完全相等；它不表示来源已经取得 editorial trust。Wikisource comparison view 用于字符/结构核对，当前不提供第二套句读。",
        "",
    ]
    for entry_id in selected_ids:
        entry = entry_by_id[entry_id]
        punctuation = records_by_entry[entry_id]
        section = punctuation.get("sections", {}).get("main_text", {})
        derived = derived_by_entry[entry_id]
        assessment = punctuation.get("alignment", {})
        lines.extend(
            [
                f"### {entry_id} · {entry.get('chapter_heading', '')} · {sample_reasons[entry_id]}",
                "",
                f"- 自动分类：{assessment.get('alignment_class')} / {', '.join(assessment.get('reason_codes', []))}",
                f"- transfer_class：`{assessment.get('transfer_class')}`；reference_case：`{assessment.get('reference_case')}`",
                f"- exact_transfer：`{punctuation.get('exact_transfer')}`",
                f"- round-trip：`{'pass' if not derived.get('round_trip_errors') and section.get('punctuated_text') else 'not_available'}`",
                f"- canonical：{canonical_texts[entry_id]}",
                f"- 转移句读：{section.get('punctuated_text') or '（无安全候选）'}",
                f"- local TXT reference：{reference_texts.get(entry_id) or '（该编号段缺失）'}",
                f"- Wikisource comparison：`{WIKISOURCE_COLLATION}/{entry_id.split('-', 2)[1]}.md`（字符/结构参考；当前无句读）",
                "",
            ]
        )
    (root / QUALIFICATION_SAMPLE_MARKDOWN).parent.mkdir(parents=True, exist_ok=True)
    (root / QUALIFICATION_SAMPLE_MARKDOWN).write_text("\n".join(lines), encoding="utf-8")


def build(root: Path) -> dict[str, Any]:
    index_document = read_json(root / CORPUS_INDEX)
    entries = sorted(index_document["entries"], key=lambda item: item["global_ordinal"])
    qualification = load_punctuation_qualification(root)
    qualification_source = root / qualification["source"]["path"]
    if not qualification_source.is_file():
        raise ValueError(f"missing qualified punctuation source: {qualification_source}")
    if sha256_file(qualification_source) != qualification["source"]["sha256"]:
        raise ValueError("punctuation qualification source SHA-256 does not match the source file")
    existing_document = read_json(root / PUNCTUATION_DATA)
    existing_records = existing_document.get("records", [])
    existing_by_entry = {record.get("entry_id"): record for record in existing_records}
    preserved_records = [
        record for record in existing_records if record.get("status") == "reviewed"
    ]

    local_path = root / REFERENCE_TEXT
    local_hash = sha256_file(local_path)
    local_reference = parse_structural_reference(local_path)
    converter = OpenCC("t2s")

    records_by_entry: dict[str, dict[str, Any]] = {}
    assessments: dict[str, dict[str, Any]] = {}
    canonical_texts: dict[str, str] = {}
    reference_texts: dict[str, str | None] = {}

    for entry in entries:
        entry_id = str(entry["id"])
        chapter_id = entry_id.split("-", 1)[0]
        ordinal = int(entry_id.rsplit("-", 1)[1])
        canonical_text = canonical_main_text(root / entry["path"])
        canonical_texts[entry_id] = canonical_text
        reference = local_reference.get((int(chapter_id), ordinal))
        reference_texts[entry_id] = reference["text"] if reference else None
        assessment = classify_alignment(canonical_text, reference, converter)

        existing = existing_by_entry.get(entry_id)
        if existing is not None and existing.get("status") == "reviewed":
            # Existing reviewed records are compatibility baselines.  Their
            # punctuation and source fields are not downgraded by CRL1.1.
            # The orthogonal calibration fields are added explicitly.
            reviewed_record = dict(existing)
            reviewed_record["review_status"] = "reviewed"
            reviewed_record["punctuation_basis"] = "human_reviewed"
            reviewed_record["exact_transfer"] = False
            reviewed_record["source_qualification_id"] = None
            records_by_entry[entry_id] = reviewed_record
            assessments[entry_id] = assessment
            continue

        chapter_slug = entry_id.split("-", 2)[1]
        wikisource_path = f"{WIKISOURCE_COLLATION}/{chapter_slug}.md"
        wikisource_file = root / wikisource_path
        if not wikisource_file.is_file():
            raise ValueError(f"missing Wikisource comparison view: {wikisource_path}")
        record = _new_punctuation_record(
            entry,
            canonical_text,
            reference,
            assessment,
            REFERENCE_TEXT,
            local_hash,
            wikisource_path,
            sha256_file(wikisource_file),
            converter,
            qualification,
        )
        records_by_entry[entry_id] = record
        assessments[entry_id] = dict(record["alignment"])

    # Keep the pre-existing reviewed record first for WP1 compatibility; all
    # generated records thereafter follow canonical corpus order.
    output_records: list[dict[str, Any]] = []
    seen: set[str] = set()
    for record in preserved_records:
        entry_id = record["entry_id"]
        if entry_id in records_by_entry and entry_id not in seen:
            output_records.append(records_by_entry[entry_id])
            seen.add(entry_id)
    for entry in entries:
        entry_id = entry["id"]
        if entry_id not in seen:
            output_records.append(records_by_entry[entry_id])
            seen.add(entry_id)

    write_json(root / PUNCTUATION_DATA, {"schema": 1, "records": output_records})

    derived_records: list[dict[str, Any]] = []
    queue_records: list[dict[str, Any]] = []
    status_counts: Counter[str] = Counter()
    alignment_counts: Counter[str] = Counter()
    reason_counts: Counter[str] = Counter()
    disputed_reason_counts: Counter[str] = Counter()
    basis_counts: Counter[str] = Counter()
    review_status_counts: Counter[str] = Counter()
    bucket_counts: Counter[str] = Counter()
    transfer_counts: Counter[str] = Counter()
    transfer_class_counts: Counter[str] = Counter()
    reference_case_counts: Counter[str] = Counter()
    chapter_counts: dict[str, Counter[str]] = defaultdict(Counter)
    bucket_projection: list[dict[str, Any]] = []

    for entry in entries:
        entry_id = entry["id"]
        record = records_by_entry[entry_id]
        status = str(record.get("status"))
        review_status = str(record.get("review_status"))
        punctuation_basis = str(record.get("punctuation_basis"))
        exact_transfer = bool(record.get("exact_transfer"))
        assessment = dict(assessments[entry_id])
        alignment_counts[assessment["alignment_class"]] += 1
        for reason in assessment.get("reason_codes", []):
            reason_counts[reason] += 1
            if status == "disputed":
                disputed_reason_counts[reason] += 1
        status_counts[status] += 1
        review_status_counts[review_status] += 1
        basis_counts[punctuation_basis] += 1
        transfer_counts["exact_transfer" if exact_transfer else "not_exact_transfer"] += 1
        transfer_class_counts[str(assessment.get("transfer_class"))] += 1
        reference_case_counts[str(assessment.get("reference_case"))] += 1
        chapter_counts[entry_id.split("-", 1)[0]][status] += 1

        main_section = record.get("sections", {}).get("main_text", {})
        original = main_section.get("punctuated_text")
        if not isinstance(original, str) or not original:
            original = None
        simplified = converter.convert(original) if original is not None else None
        round_trip_errors: list[str] = []
        if original is not None:
            round_trip_errors = validate_punctuation_round_trip(
                {"id": record["id"], "sections": {"main_text": main_section}},
                {"main_text": canonical_texts[entry_id]},
                section_names=("main_text",),
            )
        reader_ready = bool(
            original
            and not round_trip_errors
            and simplified is not None
            and (
                (review_status == "reviewed" and punctuation_basis == "human_reviewed")
                or (
                    review_status == "unreviewed"
                    and punctuation_basis == "trusted_reference_exact"
                )
            )
        )
        annotation_section = record.get("sections", {}).get("liu_annotation")
        annotation_ready = bool(
            isinstance(annotation_section, Mapping)
            and isinstance(annotation_section.get("punctuated_text"), str)
            and annotation_section.get("punctuated_text")
        )
        derived_records.append(
            {
                "entry_id": entry_id,
                "global_ordinal": entry["global_ordinal"],
                "chapter": entry_id.split("-", 1)[0],
                "punctuation_record_id": record["id"],
                "base_canonical_entry_path": entry["path"],
                "base_canonical_entry_sha256": entry["entry_sha256"],
                "status": status,
                "review_status": review_status,
                "punctuation_basis": punctuation_basis,
                "exact_transfer": exact_transfer,
                "source_qualification_id": record.get("source_qualification_id"),
                "main_text": {
                    "original": original,
                    "simplified": simplified,
                    "available": original is not None,
                },
                "story_reader_ready": reader_ready,
                "annotation_reader_ready": annotation_ready,
                "round_trip_errors": round_trip_errors,
                "alignment": assessment,
                "automatic_comparison": assessment if status == "reviewed" else None,
                "display_overrides": list(record.get("display_overrides", [])),
            }
        )
        bucket = _review_bucket(
            review_status=review_status,
            punctuation_basis=punctuation_basis,
            exact_transfer=exact_transfer,
            status=status,
            story_reader_ready=reader_ready,
        )
        bucket_counts[bucket] += 1
        bucket_projection.append(
            {
                "entry_id": entry_id,
                "global_ordinal": entry["global_ordinal"],
                "chapter": entry_id.split("-", 1)[0],
                "chapter_heading": entry.get("chapter_heading", ""),
                "bucket": bucket,
                "status": status,
                "review_status": review_status,
                "punctuation_basis": punctuation_basis,
                "exact_transfer": exact_transfer,
                "source_qualification_id": record.get("source_qualification_id"),
                "alignment_class": assessment["alignment_class"],
                "transfer_class": assessment.get("transfer_class"),
                "reference_case": assessment.get("reference_case"),
                "reason_codes": list(assessment.get("reason_codes", [])),
                "candidate_punctuation_available": original is not None,
                "story_reader_ready": reader_ready,
            }
        )

        # The detailed human queue excludes exact transfers awaiting source
        # qualification.  Those remain visible in the machine-readable
        # bucket projection above, but do not require one-by-one review until
        # the source itself is editorially qualified.
        if bucket in {"C_punctuation_review_candidate", "D_disputed_structural_review"}:
            reasons = list(assessment.get("reason_codes", []))
            reference = local_reference.get((int(entry_id.split("-", 1)[0]), int(entry_id.rsplit("-", 1)[1])))
            chapter_heading = entry.get("chapter_heading", "")
            queue_records.append(
                {
                    "entry_id": entry_id,
                    "global_ordinal": entry["global_ordinal"],
                    "chapter": entry_id.split("-", 1)[0],
                    "chapter_heading": chapter_heading,
                    "status": status,
                    "review_status": review_status,
                    "punctuation_basis": punctuation_basis,
                    "exact_transfer": exact_transfer,
                    "bucket": bucket,
                    "priority": _priority(record),
                    "canonical_text": canonical_texts[entry_id],
                    "candidate_punctuated_text": original,
                    "reference_a_text": reference_texts[entry_id],
                    "reference_a_witness_id": "shishuo-local-reference-txt",
                    "reference_a_path": REFERENCE_TEXT,
                    "reference_b": {
                        "witness_id": "shishuo-wikisource-sbck",
                        "path": f"{WIKISOURCE_COLLATION}/{entry_id.split('-', 2)[1]}.md",
                        "punctuation_available": False,
                        "notes": "Same-edition tracked comparison view; no sentence punctuation is present.",
                    },
                    "alignment_class": assessment["alignment_class"],
                    "transfer_class": assessment.get("transfer_class"),
                    "reference_case": assessment.get("reference_case"),
                    "reason_codes": reasons,
                    "mismatch_offsets": list(assessment.get("mismatch_offsets", [])),
                    "canonical_character_count": assessment["canonical_character_count"],
                    "reference_character_count": assessment["reference_character_count"],
                    "notes": (
                        "Review the candidate only as punctuation guidance; preserve the canonical "
                        "traditional character sequence exactly."
                    ),
                }
            )

    queue_records.sort(key=lambda item: (item["priority"], item["global_ordinal"]))
    derived = {
        "schema": 1,
        "stage": "crl1-corpus-reading-layer",
        "work": "世說新語",
        "entry_count": len(derived_records),
        "source_annotation": PUNCTUATION_DATA,
        "conversion": {
            "library": "opencc-python-reimplemented",
            "config": "t2s",
            "role": "derived display only; never used for canonical comparison",
        },
        "records": derived_records,
    }
    write_json(root / READING_DATA, derived)

    review_queue_document = {
        "schema": 1,
        "stage": "crl1-1-punctuation-review-buckets",
        "work": "世說新語",
        "source": READING_DATA,
        "entry_count": len(bucket_projection),
        "bucket_order": [
            "A_trusted_reference_ready",
            "B_exact_transfer_awaiting_source_qualification",
            "C_punctuation_review_candidate",
            "D_disputed_structural_review",
        ],
        "bucket_counts": dict(bucket_counts),
        "records": sorted(bucket_projection, key=lambda item: item["global_ordinal"]),
        "notes": "All 1,130 entries are represented. Detailed human review focuses on buckets C and D; bucket B is technically exact but awaits source qualification.",
    }
    write_json(root / REVIEW_QUEUE_JSON, review_queue_document)

    derived_by_entry = {record["entry_id"]: record for record in derived_records}
    sample_reasons = select_qualification_sample(entries, records_by_entry, canonical_texts)
    write_qualification_sample(
        root,
        entries,
        records_by_entry,
        derived_by_entry,
        canonical_texts,
        reference_texts,
        sample_reasons,
    )

    queue_document = {
        "schema": 1,
        "stage": "crl1-1-detailed-punctuation-review-queue",
        "work": "世說新語",
        "source": READING_DATA,
        "entry_count": len(queue_records),
        "bucket_counts": {
            "C_punctuation_review_candidate": bucket_counts["C_punctuation_review_candidate"],
            "D_disputed_structural_review": bucket_counts["D_disputed_structural_review"],
        },
        "excluded_exact_transfer_count": bucket_counts["B_exact_transfer_awaiting_source_qualification"],
        "records": queue_records,
    }
    _yaml_dump(root / QUEUE_DATA, queue_document)

    markdown: list[str] = [
        "# CRL1.1 句读人工复核队列",
        "",
        "本队列由 `scripts/build_shishuo_reading_layer.py` 确定性生成。Canonical 字符序列始终优先；候选句读只作参考，不能改写原文。精确字符转移但尚待来源资格判断的条目列在 `data/derived/punctuation-review-queue.json` 的 B bucket，不重复进入本详细队列。",
        "",
        f"- 队列条目：{len(queue_records)}",
        f"- C（句读人工复核候选）：{bucket_counts['C_punctuation_review_candidate']}",
        f"- D（争议/结构复核）：{bucket_counts['D_disputed_structural_review']}",
        f"- B（精确转移、等待来源资格）：{bucket_counts['B_exact_transfer_awaiting_source_qualification']}",
        f"- A（可信/已具备阅读资格）：{bucket_counts['A_trusted_reference_ready']}",
        "",
        f"- 优先级 1（对齐失败/参考缺字插字）：{sum(1 for item in queue_records if item['priority'] == 1)}",
        f"- 优先级 2（句读分歧）：{sum(1 for item in queue_records if item['priority'] == 2)}",
        f"- 优先级 3（字符差异）：{sum(1 for item in queue_records if item['priority'] == 3)}",
        f"- 优先级 4（单句读参考）：{sum(1 for item in queue_records if item['priority'] == 4)}",
        "",
        "## Review items",
        "",
    ]
    for item in queue_records:
        markdown.extend(
            [
                f"### {item['entry_id']} · {item['status']} · P{item['priority']}",
                "",
                f"- 原文：{item['canonical_text']}",
                f"- 候选句读：{item['candidate_punctuated_text'] or '（无安全候选）'}",
                f"- 本地参考：{item['reference_a_text'] or '（该编号段缺失）'}",
                f"- 原因：{', '.join(item['reason_codes'])}",
                f"- 字符长度：canonical {item['canonical_character_count']} / reference {item['reference_character_count']}",
                f"- 字符差异位置：{', '.join(str(x) for x in item['mismatch_offsets']) or '无'}",
                "",
            ]
        )
    (root / QUEUE_MARKDOWN).parent.mkdir(parents=True, exist_ok=True)
    (root / QUEUE_MARKDOWN).write_text("\n".join(markdown), encoding="utf-8")

    report: list[str] = [
        "# CRL1 Corpus Reading Layer Audit",
        "",
        "本报告由 `scripts/build_shishuo_reading_layer.py` 生成；CRL1.1 将 review status 与 punctuation basis 分开记录。它不包含自动句读的人工背书。Wikisource 四部叢刊 comparison view 当前没有句读，因此不能作为第二个句读参考。",
        "",
        f"- canonical entries: {len(entries)}",
        f"- reviewed: {status_counts['reviewed']}",
        f"- aligned: {status_counts['aligned']}",
        f"- candidate: {status_counts['candidate']}",
        f"- disputed: {status_counts['disputed']}",
        f"- review_status=reviewed: {review_status_counts['reviewed']}",
        f"- review_status=unreviewed: {review_status_counts['unreviewed']}",
        f"- punctuation_basis=human_reviewed: {basis_counts['human_reviewed']}",
        f"- punctuation_basis=trusted_reference_exact: {basis_counts['trusted_reference_exact']}",
        f"- punctuation_basis=reference_candidate: {basis_counts['reference_candidate']}",
        f"- punctuation_basis=disputed: {basis_counts['disputed']}",
        f"- story_reader_ready: {sum(1 for record in derived_records if record['story_reader_ready'])}",
        f"- punctuation generated: {sum(1 for record in derived_records if record['main_text']['original'] is not None)}",
        f"- technically exact transfers: {transfer_counts['exact_transfer']}",
        f"- transfer class exact_character_transfer: {transfer_class_counts['exact_character_transfer']}",
        f"- transfer class character_mismatch_around_punctuation: {transfer_class_counts['character_mismatch_around_punctuation']}",
        f"- transfer class structural_or_boundary_mismatch: {transfer_class_counts['structural_or_boundary_mismatch']}",
        f"- transfer class missing_reference: {transfer_class_counts['missing_reference']}",
        f"- simplified reading available: {sum(1 for record in derived_records if record['main_text']['simplified'] is not None)}",
        f"- display overrides: {sum(len(record['display_overrides']) for record in derived_records)}",
        f"- exact character alignments: {alignment_counts['exact-agreement']}",
        f"- one-to-one character-disagreement alignments: {alignment_counts['character-disagreement']}",
        f"- exact two-reference punctuation agreements: 0",
        f"- one-reference-only exact/transfer candidates: {reason_counts['single_reference_only']}",
        f"- punctuation disagreements: {reason_counts['punctuation_boundary_disagreement']}",
        f"- character disagreements: {reason_counts['reference_character_variant']}",
        f"- alignment failures: {alignment_counts['alignment-failure']}",
        f"- persisted disputed records after reviewed overrides: {status_counts['disputed']}",
        f"- queue A trusted/reference-ready: {bucket_counts['A_trusted_reference_ready']}",
        f"- queue B exact-transfer awaiting source qualification: {bucket_counts['B_exact_transfer_awaiting_source_qualification']}",
        f"- queue C punctuation-review candidate: {bucket_counts['C_punctuation_review_candidate']}",
        f"- queue D disputed/structural review: {bucket_counts['D_disputed_structural_review']}",
        "",
        "## Source qualification",
        "",
        f"- witness: `{qualification['witness_id']}`",
        f"- qualification: `{qualification['qualification']}`",
        f"- source: `{qualification['source']['path']}`",
        f"- source SHA-256: `{qualification['source']['sha256']}`",
        "- trusted_reference_exact promotion: disabled because tracked provenance remains unresolved and the witness is only provisionally qualified.",
        "",
        "## Persisted disputed-case categories",
        "",
        f"- structural alignment failure: {disputed_reason_counts['structural_alignment_failure']}",
        f"- reference deletion: {disputed_reason_counts['reference_deletion']}",
        f"- reference insertion: {disputed_reason_counts['reference_insertion']}",
        f"- missing usable numbered reference: {sum(1 for record in derived_records if record['status'] == 'disputed' and record['alignment']['reference_character_count'] == 0)}",
        "",
        "## Chapter counts",
        "",
        "| chapter | reviewed | aligned | candidate | disputed | reader-ready |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for chapter in sorted(chapter_counts):
        chapter_records = [record for record in derived_records if record["chapter"] == chapter]
        counts = chapter_counts[chapter]
        report.append(
            f"| {chapter} | {counts['reviewed']} | {counts['aligned']} | {counts['candidate']} | {counts['disputed']} | "
            f"{sum(1 for record in chapter_records if record['story_reader_ready'])} |"
        )
    report.extend(
        [
            "",
            "## Method and limits",
            "",
            "1. Canonical main text comes from the existing entry Markdown and is never rewritten.",
            "2. The local structural TXT is parsed by chapter and printed ordinal; it supplies the only punctuation-bearing reference in this run and is provisionally qualified for exact-transfer analysis only.",
            "3. Traditional-to-simplified conversion is used only for comparison keys and derived display text; it is never used to replace canonical characters.",
            "4. Exact or one-to-one variant alignment produces an unreviewed `reference_candidate`; exact character equality is recorded separately as `exact_transfer=true`.",
            "5. The local reference has no 文學第23 and no 賞譽第100 numbered paragraph; those entries remain `disputed` and are not repaired by neighboring text.",
            "6. The existing reviewed `06-yaliang-019` record remains authoritative and is the only current `human_reviewed` record. Its machine comparison is retained only in the derived audit record.",
            "7. Detailed human review is limited to C and D; B is a technically exact intermediate class awaiting source qualification, not silent publication.",
        ]
    )
    (root / AUDIT_MARKDOWN).parent.mkdir(parents=True, exist_ok=True)
    (root / AUDIT_MARKDOWN).write_text("\n".join(report) + "\n", encoding="utf-8")

    return {
        "entries": len(entries),
        "status_counts": dict(status_counts),
        "alignment_counts": dict(alignment_counts),
        "reason_counts": dict(reason_counts),
        "reader_ready": sum(1 for record in derived_records if record["story_reader_ready"]),
        "queue_count": len(queue_records),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    summary = build(args.root.resolve())
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
