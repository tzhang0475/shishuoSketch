#!/usr/bin/env python3
"""Align Jianshu Story records to the canonical and frozen X1.1 universes."""

from __future__ import annotations

import re
from pathlib import Path
import sys
import unicodedata

from s1_jianshu_common import (
    ALIGNMENT_PATH,
    CORPUS_INDEX_PATH,
    SC1_PATH,
    X1_SELECTION_PATH,
    load_story_records,
    read_json,
    sha256_file,
    FULLWIDTH_DIGITS,
    write_json,
    x1_selection_by_story,
)


ROOT = Path(__file__).resolve().parents[1]


def compact_text(text: str) -> str:
    text = unicodedata.normalize("NFC", text)
    return re.sub(r"[\s\W_]+", "", text, flags=re.UNICODE)


def source_ordinal(story_id: str) -> tuple[str, int] | None:
    match = re.match(r"^(\d{2}-[^-]+)-(\d+)$", story_id)
    if not match:
        return None
    return match.group(1), int(match.group(2))


def canonical_main_text(story_id: str) -> str:
    chapter, ordinal = source_ordinal(story_id) or (None, None)
    if not chapter or ordinal is None:
        return ""
    path = ROOT / "content/processed/shishuo/entries" / chapter / f"entry-{ordinal:03d}.md"
    if not path.exists():
        return ""
    text = path.read_text(encoding="utf-8")
    match = re.search(r"^## Main text\s*$", text, flags=re.MULTILINE)
    if not match:
        return ""
    remainder = text[match.end():]
    remainder = re.split(r"^## ", remainder, maxsplit=1, flags=re.MULTILINE)[0]
    return remainder.strip()


def opening_compatibility(opening: str, base_text: str) -> tuple[str, int]:
    opening_compact = compact_text(opening)
    base_compact = compact_text(base_text)
    base_compact = re.sub(r"^[0-9]+", "", base_compact.translate(FULLWIDTH_DIGITS))
    if not opening_compact:
        return "unknown", 0
    # Jianshu begins each entry with the same text but includes punctuation,
    # Liu annotations, and occasionally a minor character variant later on.
    max_prefix = min(len(opening_compact), 20)
    prefix = 0
    for left, right in zip(opening_compact[:max_prefix], base_compact):
        if left != right:
            break
        prefix += 1
    positional_mismatches = sum(
        left != right for left, right in zip(opening_compact[:max_prefix], base_compact[:max_prefix])
    )
    if prefix >= min(16, max_prefix):
        return "exact", prefix
    if prefix >= min(4, max_prefix):
        return "near_exact", prefix
    # A one-character traditional/variant form at the opening is a known
    # minor variant when the surrounding opening remains aligned.  This keeps
    # common 呉/吳 and 温/溫 cases from becoming false structural failures.
    if max_prefix >= 8 and positional_mismatches <= 2:
        return "near_exact", prefix
    if prefix >= 1 or (opening_compact[:8] and opening_compact[:8] in base_compact[:80]):
        return "known_minor_variant", prefix
    return "structural_ambiguity", prefix


def build_alignment() -> dict:
    records = load_story_records()
    by_key = {(str(row["chapter_id"]), int(row["ordinal"])): row for row in records}
    corpus = read_json(CORPUS_INDEX_PATH)
    corpus_entries = {str(row["id"]): row for row in corpus.get("entries", [])}
    sc1 = read_json(SC1_PATH)
    production_ids = {str(row.get("source_entry_id", row.get("id"))) for row in sc1.get("stories", [])}
    selection = x1_selection_by_story()
    target_ids = sorted(production_ids | set(selection))
    output_records: list[dict] = []
    for story_id in target_ids:
        key = source_ordinal(story_id)
        entry = corpus_entries.get(story_id)
        jianshu = by_key.get(key) if key else None
        provenance = selection.get(story_id, {})
        row = {
            "alignment_id": f"s1-alignment-{story_id}",
            "story_id": story_id,
            "scope": "x1_1_frozen_selection" if story_id in selection else "current_production",
            "selection_provenance": {
                "selection_epoch": provenance.get("selection_epoch"),
                "selection_mode": provenance.get("selection_mode"),
                "source_graph_version": provenance.get("source_graph_version"),
                "source_ml_version": provenance.get("source_ml_version"),
                "candidate_pool_hash": provenance.get("candidate_pool_hash"),
                "selection_seed": provenance.get("selection_seed"),
            }
            if provenance
            else None,
            "canonical_entry_exists": entry is not None,
            "jianshu_record_exists": jianshu is not None,
            "alignment_basis": ["chapter", "entry_ordinal"],
            "alignment_class": "unmatched",
            "editorial_segmentation_available": False,
            "meaningful_variant": False,
            "source_locator": jianshu.get("source_locator") if jianshu else None,
            "source_story_key": jianshu.get("story_key") if jianshu else None,
            "evidence": [],
        }
        if key and jianshu is not None:
            canonical_text = canonical_main_text(story_id)
            comparison_text = canonical_text or (str(entry.get("opening_text", "")) if entry else "")
            compatibility, prefix = opening_compatibility(comparison_text, str(jianshu.get("base_text", "")))
            row["alignment_class"] = compatibility
            row["opening_prefix_match_length"] = prefix
            row["editorial_segmentation_available"] = bool(jianshu.get("base_text") and jianshu.get("blocks"))
            row["meaningful_variant"] = compatibility == "structural_ambiguity"
            row["evidence"] = [
                {
                    "source_id": "shishuo-jianshu-yujiaxi-local-epub",
                    "source_locator": jianshu.get("source_locator"),
                    "source_story_key": jianshu.get("story_key"),
                    "base_text_sha256": jianshu.get("base_text_sha256"),
                    "canonical_opening_text": entry.get("opening_text") if entry else None,
                    "canonical_main_text_available": bool(canonical_text),
                    "basis": "chapter-and-entry-ordinal; opening text compatibility is secondary verification",
                }
            ]
            if row["meaningful_variant"]:
                row["alignment_note"] = "Ordinal identity is present, but the canonical opening is not safely found in the Jianshu entry; semantic review remains required."
            elif compatibility == "known_minor_variant":
                row["alignment_note"] = "The Story identity is stable by chapter and ordinal; character/text variation is retained as a known minor variant and does not overwrite canonical text."
            else:
                row["alignment_note"] = "The Story identity is stable by chapter and ordinal and the opening is compatible."
        else:
            row["alignment_note"] = "No deterministic chapter/ordinal Jianshu record was found."
        output_records.append(row)
    output_records.sort(key=lambda row: (0 if row["scope"] == "current_production" else 1, row["story_id"]))
    result = {
        "schema": "s1-jianshu-story-alignment-1",
        "stage": "S1.3",
        "source_sha256": {
            "epub": sha256_file(Path("sources/downloads/shishuo/ssjx-2016-epub-transcription") / next(Path("sources/downloads/shishuo/ssjx-2016-epub-transcription").glob("*.epub")).name),
            "corpus_index": sha256_file(CORPUS_INDEX_PATH),
            "sc1_site": sha256_file(SC1_PATH),
            "x1_1_selection": sha256_file(X1_SELECTION_PATH),
        },
        "scope": {
            "production_story_count": len(production_ids),
            "frozen_x1_1_story_count": len(selection),
            "target_story_count": len(target_ids),
            "new_story_selection_performed": False,
        },
        "counts": {
            "exact": sum(row["alignment_class"] == "exact" for row in output_records),
            "near_exact": sum(row["alignment_class"] == "near_exact" for row in output_records),
            "known_minor_variant": sum(row["alignment_class"] == "known_minor_variant" for row in output_records),
            "structural_ambiguity": sum(row["alignment_class"] == "structural_ambiguity" for row in output_records),
            "meaningful_variant": sum(bool(row["meaningful_variant"]) for row in output_records),
            "unmatched": sum(row["alignment_class"] == "unmatched" for row in output_records),
        },
        "records": output_records,
        "policy": {
            "chapter_and_ordinal_dominate_fuzzy_similarity": True,
            "minor_character_variants_do_not_replace_canonical_text": True,
            "meaningful_variants_remain_review_required": True,
            "selection_channel_is_not_textual_evidence": True,
        },
    }
    write_json(ALIGNMENT_PATH, result)
    return result


def main() -> int:
    try:
        result = build_alignment()
    except Exception as exc:
        print(f"S1 Jianshu alignment failed: {exc}", file=sys.stderr)
        return 2
    print(result["scope"], result["counts"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
