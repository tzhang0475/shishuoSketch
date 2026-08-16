#!/usr/bin/env python3
"""Parse the local Jianshu EPUB into an ignored, structured cache.

The cache is deliberately not a tracked full-text mirror.  Tracked outputs
are structural audits and compact candidate-oriented projections; the full
normalized blocks stay under `.cache/shishuo-reference/jianshu/`.
"""

from __future__ import annotations

from collections import Counter, defaultdict
import hashlib
import re
from pathlib import Path
import sys
from zipfile import ZipFile

from s1_jianshu_common import (
    CACHE_ROOT,
    CORPUS_INDEX_PATH,
    GLYPH_AUDIT_PATH,
    STRUCTURE_AUDIT_PATH,
    classify_attribution,
    category_number,
    discover_payloads,
    epub_layout,
    leading_ordinal,
    load_story_records,
    normalize_source_text,
    parse_xhtml_blocks,
    pdf_metadata,
    relative_path,
    sha256_path,
    stable_id,
    write_json,
    write_jsonl,
)
from s1_jianshu_common import read_json


ROOT = Path(__file__).resolve().parents[1]


def chapter_catalog() -> dict[int, dict[str, str]]:
    document = read_json(CORPUS_INDEX_PATH)
    result: dict[int, dict[str, str]] = {}
    for row in document.get("chapters", []):
        match = re.match(r"^(\d+)-", str(row.get("id", "")))
        if match:
            result[int(match.group(1))] = {
                "chapter_id": str(row["id"]),
                "heading": str(row.get("heading", "")),
            }
    return result


def is_category_heading(text: str, categories: dict[int, dict[str, str]]) -> int | None:
    """Recognize a real category heading, not a short note citing ``第...``."""

    compact = re.sub(r"\s+", "", text)
    if compact.startswith(("〔", "（", "(", "[")):
        return None
    number = category_number(compact)
    if number not in categories:
        return None
    match = re.search(r"第[零〇一二三四五六七八九十百0-9０１２３４５６７８９]+", compact)
    if not match:
        return None
    prefix = compact[: match.start()]
    if prefix.startswith("世說新語卷"):
        return number
    canonical_prefix = re.sub(r"第.*$", "", categories[number]["heading"])
    # The supplied reference uses 仇隙 while the current canonical heading is
    # 仇隟; retain that established minor heading variant explicitly.
    allowed_prefixes = {canonical_prefix, "仇隙" if number == 36 else canonical_prefix}
    return number if prefix in allowed_prefixes else None


def classify_note_mode(text: str) -> str | None:
    compact = re.sub(r"\s+", "", text)
    if compact == "【校文】":
        return "collation_note"
    if compact == "【箋疏】" or compact == "【笺疏】":
        return "jianshu_note"
    return None


def is_appendix_heading(text: str) -> bool:
    compact = re.sub(r"\s+", "", text)
    return any(
        phrase in compact
        for phrase in (
            "常見人名異稱表",
            "常⾒⼈名異稱表",
            "人名索引",
            "引書索引",
            "序目",
            "序目",
            "舊題",
            "總目提要",
        )
    )


def glyph_issues(text: str, locator: dict, story_id: str | None) -> list[dict]:
    issues: list[dict] = []
    for index, char in enumerate(text):
        codepoint = ord(char)
        severity: str | None = None
        kind: str | None = None
        if char == "�" or codepoint == 0xFFFD:
            severity, kind = "high", "replacement_symbol"
        elif char == "●":
            severity, kind = "medium", "placeholder_circle"
        elif 0xE000 <= codepoint <= 0xF8FF or 0xF0000 <= codepoint <= 0xFFFFD or 0x100000 <= codepoint <= 0x10FFFD:
            severity, kind = "medium", "private_use_area"
        elif codepoint < 32 and char not in {"\t", "\n", "\r"}:
            severity, kind = "high", "control_character"
        if severity:
            left = max(0, index - 12)
            right = min(len(text), index + 13)
            issues.append(
                {
                    "issue_id": stable_id("s1-glyph", locator.get("file"), locator.get("block_index"), index, codepoint),
                    "story_id": story_id,
                    "source_locator": locator,
                    "character": char,
                    "code_point": f"U+{codepoint:04X}",
                    "character_index": index,
                    "kind": kind,
                    "severity": severity,
                    "context": text[left:right],
                }
            )
    return issues


def annotation_segments(text: str) -> list[str]:
    # The EPUB interleaves base text and Liu's parenthetical annotation.  The
    # marker-delimited pieces are retained as an explicitly approximate layer;
    # this is not presented as a canonical re-segmentation of the witness.
    parts = re.split(r"(?=〔[一二三四五六七八九十百零〇0-9]+〕)", text)
    return [part.strip() for part in parts[1:] if part.strip()]


def make_block(block_type: str, text: str, locator: dict, **extra: object) -> dict:
    record = {
        "block_id": stable_id("s1-jianshu-block", block_type, locator.get("file"), locator.get("block_index"), text),
        "block_type": block_type,
        "text": text,
        "text_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
        "source_locator": locator,
    }
    record.update(extra)
    return record


def parse_epub() -> dict:
    payloads = discover_payloads()
    epub_path = payloads["epub"]
    layout = epub_layout(epub_path)
    chapters = chapter_catalog()
    category_by_number = {number: item for number, item in chapters.items()}
    story_records: list[dict] = []
    unknown_blocks: list[dict] = []
    appendix_records: list[dict] = []
    glyph_records: list[dict] = []
    block_counts: Counter[str] = Counter()
    attribution_counts: Counter[str] = Counter()
    chapter_sources: defaultdict[str, set[str]] = defaultdict(set)
    chapter_current: int | None = None
    current_story: dict | None = None
    note_mode: str | None = None

    def finalize_story() -> None:
        nonlocal current_story, note_mode
        if current_story is None:
            return
        current_story["block_count"] = len(current_story["blocks"])
        current_story["block_type_counts"] = dict(sorted(Counter(block["block_type"] for block in current_story["blocks"]).items()))
        story_records.append(current_story)
        current_story = None
        note_mode = None

    with ZipFile(epub_path) as archive:
        for spine_row in layout["spine"]:
            if spine_row["media_type"] != "application/xhtml+xml":
                continue
            member = spine_row["path"]
            if member not in archive.namelist():
                unknown_blocks.append({"source_locator": spine_row, "reason": "spine_member_missing"})
                continue
            blocks = parse_xhtml_blocks(archive.read(member))
            for block_index, parsed in enumerate(blocks):
                text = parsed["text"]
                if not text:
                    continue
                locator = {
                    "epub_file": member,
                    "spine_index": spine_row["spine_index"],
                    "block_index": block_index,
                    "tag": parsed.get("tag"),
                }
                if is_appendix_heading(text):
                    finalize_story()
                    appendix_records.append(
                        {
                            "appendix_id": stable_id("s1-appendix", member, block_index, text),
                            "heading": text,
                            "source_locator": locator,
                            "available_in_spine": False,
                            "detection": "TOC_or_structural_heading",
                        }
                    )
                    block_counts["appendix"] += 1
                    continue
                number = is_category_heading(text, category_by_number)
                if number in category_by_number:
                    finalize_story()
                    chapter_current = number
                    chapter_sources[category_by_number[number]["chapter_id"]].add(member)
                    block_counts["chapter_heading"] += 1
                    continue
                ordinal = leading_ordinal(text) if chapter_current is not None else None
                mode = classify_note_mode(text)
                ordinal_match = re.match(r"^[0-9０１２３４５６７８９]+", text) if ordinal is not None else None
                entry_remainder = text[ordinal_match.end():].lstrip(" .-—") if ordinal_match else ""
                entry_has_cjk = bool(re.search(r"[\u3400-\u9fff]", entry_remainder))
                if ordinal is not None and chapter_current in category_by_number and len(text) > 2 and entry_has_cjk:
                    finalize_story()
                    chapter = category_by_number[chapter_current]
                    story_id = f"{chapter['chapter_id']}-{ordinal:03d}"
                    marker_count = len(re.findall(r"〔[一二三四五六七八九十百零〇0-9]+〕", text))
                    base_block = make_block("base_text", text, locator, segmentation="full_entry_paragraph")
                    blocks_for_story = [base_block]
                    block_counts["base_text"] += 1
                    glyph_records.extend(glyph_issues(text, locator, story_id))
                    if marker_count:
                        for segment_index, segment in enumerate(annotation_segments(text)):
                            annotation_block = make_block(
                                "liu_annotation",
                                segment,
                                locator,
                                embedded=True,
                                segmentation="marker_delimited_structural_approximation",
                                marker_index=segment_index + 1,
                            )
                            blocks_for_story.append(annotation_block)
                            block_counts["liu_annotation"] += 1
                            glyph_records.extend(glyph_issues(segment, locator, story_id))
                    current_story = {
                        "story_key": stable_id("s1-jianshu-story", chapter["chapter_id"], ordinal),
                        "story_id": story_id,
                        "chapter_id": chapter["chapter_id"],
                        "chapter_heading": chapter["heading"],
                        "chapter_number": chapter_current,
                        "ordinal": ordinal,
                        "base_text": text,
                        "base_text_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
                        "liu_marker_count": marker_count,
                        "source_locator": locator,
                        "blocks": blocks_for_story,
                    }
                    note_mode = None
                    continue
                if mode is not None:
                    if current_story is None:
                        unknown_blocks.append({"source_locator": locator, "text_excerpt": text[:240], "reason": "note_heading_without_story"})
                    else:
                        note_mode = mode
                    continue
                if current_story is not None and note_mode in {"collation_note", "jianshu_note"}:
                    block_type = note_mode
                    attribution = classify_attribution(text)
                    note_block = make_block(
                        block_type,
                        text,
                        locator,
                        attribution=attribution,
                        attribution_explicit=attribution is not None,
                    )
                    current_story["blocks"].append(note_block)
                    block_counts[block_type] += 1
                    if attribution:
                        attribution_counts[attribution] += 1
                    glyph_records.extend(glyph_issues(text, locator, current_story["story_id"]))
                    continue
                unknown_blocks.append({"source_locator": locator, "text_excerpt": text[:240], "reason": "front_matter_or_unparsed_block"})
                block_counts["unknown"] += 1
        finalize_story()

    story_records.sort(key=lambda row: (int(row["chapter_number"]), int(row["ordinal"]), row["story_id"]))
    for row in story_records:
        chapter_sources[row["chapter_id"]].add(row["source_locator"]["epub_file"])
    chapters_out = []
    for number, chapter in sorted(category_by_number.items()):
        rows = [row for row in story_records if row["chapter_number"] == number]
        chapters_out.append(
            {
                "chapter_number": number,
                "chapter_id": chapter["chapter_id"],
                "canonical_heading": chapter["heading"],
                "source_story_count": len(rows),
                "source_ordinals": [row["ordinal"] for row in rows],
                "source_files": sorted(chapter_sources.get(chapter["chapter_id"], set())),
                "detected": bool(rows),
            }
        )

    cache = ROOT / CACHE_ROOT
    cache.mkdir(parents=True, exist_ok=True)
    write_jsonl(CACHE_ROOT / "story-records.jsonl", story_records)
    write_json(CACHE_ROOT / "chapter-index.json", {"chapters": chapters_out})
    write_json(CACHE_ROOT / "alias-appendix.json", {"records": appendix_records})

    # Jianshu citation extraction is intentionally kept in cache too; the
    # tracked candidate projection is generated by the next S1 stage.
    citation_rows = []
    for story in story_records:
        for block in story["blocks"]:
            if block["block_type"] in {"liu_annotation", "jianshu_note", "collation_note"}:
                citation_rows.append(
                    {
                        "story_id": story["story_id"],
                        "chapter_id": story["chapter_id"],
                        "block_id": block["block_id"],
                        "layer": block["block_type"],
                        "attribution": block.get("attribution"),
                        "source_locator": block["source_locator"],
                        "text": block["text"],
                    }
                )
    write_jsonl(CACHE_ROOT / "citation-blocks.jsonl", sorted(citation_rows, key=lambda row: (row["story_id"], row["block_id"])))

    pdf_index_status = build_pdf_page_index(payloads["pdf"])
    write_json(CACHE_ROOT / "parse-metadata.json", {
        "schema": "s1-jianshu-cache-1",
        "epub_sha256": sha256_path(epub_path),
        "pdf_sha256": sha256_path(payloads["pdf"]),
        "spine": layout["spine"],
        "story_record_count": len(story_records),
        "pdf_page_index": pdf_index_status,
        "normalization": "NFC plus whitespace cleanup only; no character/script conversion or emendation",
    })

    glyph_records.sort(key=lambda row: (row.get("source_locator", {}).get("epub_file", ""), row.get("source_locator", {}).get("block_index", -1), row.get("character_index", -1), row["issue_id"]))
    write_json(GLYPH_AUDIT_PATH, {
        "schema": "s1-jianshu-glyph-audit-1",
        "stage": "S1.2",
        "source_sha256": sha256_path(epub_path),
        "issue_count": len(glyph_records),
        "severity_counts": dict(sorted(Counter(row["severity"] for row in glyph_records).items())),
        "kind_counts": dict(sorted(Counter(row["kind"] for row in glyph_records).items())),
        "issues": glyph_records,
        "policy": "Issues are audited, not automatically repaired; PDF fallback is reserved for identity, meaning, or boundary-relevant cases.",
    })
    write_json(STRUCTURE_AUDIT_PATH, {
        "schema": "s1-jianshu-structure-audit-1",
        "stage": "S1.2",
        "source_family": "shishuo-jianshu-yujiaxi-local",
        "source_sha256": {"epub": sha256_path(epub_path), "pdf": sha256_path(payloads["pdf"])},
        "spine_document_count": layout["spine_document_count"],
        "chapters_detected": len([row for row in chapters_out if row["detected"]]),
        "chapter_count_expected": len(chapters_out),
        "chapters": chapters_out,
        "story_entries_detected": len(story_records),
        "story_entry_count_by_chapter": {row["chapter_id"]: row["source_story_count"] for row in chapters_out},
        "block_counts": dict(sorted(block_counts.items())),
        "attributed_scholar_notes": dict(sorted(attribution_counts.items())),
        "appendices_detected": appendix_records,
        "unknown_unparsed_block_count": len(unknown_blocks),
        "unknown_unparsed_block_samples": unknown_blocks[:100],
        "glyph_anomaly_count": len(glyph_records),
        "policy": {
            "primary_witness_unchanged": True,
            "epub_is_machine_reference": True,
            "pdf_is_visual_fallback": True,
            "full_text_cache_ignored": True,
        },
    })
    return {"stories": len(story_records), "chapters": len(chapters_out), "glyphs": len(glyph_records)}


def build_pdf_page_index(pdf_path: Path) -> dict:
    cache_path = ROOT / CACHE_ROOT / "pdf-page-index.jsonl"
    try:
        import subprocess

        completed = subprocess.run(
            ["pdftotext", "-layout", str(pdf_path), "-"],
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
        )
        if completed.returncode != 0:
            raise RuntimeError(completed.stderr.strip() or "pdftotext failed")
        pages = completed.stdout.split("\f")
        rows = []
        for index, text in enumerate(pages, start=1):
            normalized = normalize_source_text(text)
            anchors = sorted(set(re.findall(r"[\u3400-\u9fff]{2,8}", normalized)))[:12]
            rows.append(
                {
                    "physical_page": index,
                    "text_sha256": hashlib.sha256(normalized.encode("utf-8")).hexdigest(),
                    "character_count": len(normalized),
                    "search_anchors": anchors,
                    "excerpt": normalized[:160],
                }
            )
        write_jsonl(CACHE_ROOT / "pdf-page-index.jsonl", rows)
        return {"status": "built", "page_count": len(rows), "text_layer": True, "cache": relative_path(cache_path)}
    except (FileNotFoundError, subprocess.SubprocessError, RuntimeError) as exc:
        metadata = pdf_metadata(pdf_path)
        write_jsonl(CACHE_ROOT / "pdf-page-index.jsonl", [])
        return {"status": "unavailable", "page_count": metadata.get("page_count"), "text_layer": metadata.get("has_text_layer"), "reason": str(exc), "cache": relative_path(cache_path)}


def main() -> int:
    try:
        result = parse_epub()
    except Exception as exc:
        print(f"S1 Jianshu ingestion failed: {exc}", file=sys.stderr)
        return 2
    print(f"parsed {result['stories']} Story entries across {result['chapters']} chapters; glyph issues={result['glyphs']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
