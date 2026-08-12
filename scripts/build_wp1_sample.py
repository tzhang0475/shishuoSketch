#!/usr/bin/env python3
"""Build the deterministic WP1 sample bundle from existing repository data.

The canonical Shishuo entry remains the source of truth.  This script reads
it, reads the existing six-person pilot outputs, and writes only annotation
and derived/static data files.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
from typing import Any

from opencc import OpenCC

try:
    from .build_six_person_pilot import markdown_body, parse_frontmatter
    from .reading_layers import (
        PUNCTUATION_RELATIVE_PATH,
        build_display_reading,
        validate_punctuation_round_trip,
    )
except ImportError:  # direct execution: python scripts/build_wp1_sample.py
    from build_six_person_pilot import markdown_body, parse_frontmatter
    from reading_layers import (
        PUNCTUATION_RELATIVE_PATH,
        build_display_reading,
        validate_punctuation_round_trip,
    )


ROOT = Path(__file__).resolve().parents[1]
ENTRY_ID = "06-yaliang-019"
ENTRY_PATH = ROOT / "content/processed/shishuo/entries/06-yaliang/entry-019.md"
PEOPLE_PATH = ROOT / "data/people.json"
ALIASES_PATH = ROOT / "data/aliases.json"
MENTIONS_PATH = ROOT / "data/mentions/shishuo.json"

TARGET_PERSON_IDS = (
    "wang-xizhi",
    "xi-jian",
    "wang-dao",
    "wang-ningzhi",
    "xie-daoyun",
    "xie-an",
)

JINSHU_UNIT_PATHS = {
    "065-liezhuan-001": "content/processed/jinshu/units/liezhuan/065-liezhuan-001.md",
    "096-liezhuan-016": "content/processed/jinshu/units/liezhuan/096-liezhuan-016.md",
    "079-liezhuan-002": "content/processed/jinshu/units/liezhuan/079-liezhuan-002.md",
}


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=False) + "\n",
        encoding="utf-8",
    )


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def parse_entry_sections(text: str) -> tuple[str, list[dict[str, Any]]]:
    body = markdown_body(text)
    marker = "## Main text\n\n"
    if marker not in body:
        raise ValueError(f"missing main text section in {ENTRY_PATH}")
    after_main = body.split(marker, 1)[1]
    annotation_marker = "\n## Top-level parenthetical annotation blocks\n"
    main_text, separator, annotation_section = after_main.partition(annotation_marker)
    if not separator:
        return main_text.rstrip("\n"), []
    main_text = main_text.rstrip("\n")
    annotation_section = annotation_section.split("\n## Kanripo page markers", 1)[0]
    matches = list(re.finditer(r"(?m)^### (annotation-\d+)\n", annotation_section))
    annotations: list[dict[str, Any]] = []
    for index, match in enumerate(matches):
        stop = matches[index + 1].start() if index + 1 < len(matches) else len(annotation_section)
        block = annotation_section[match.end() : stop].strip("\n")
        if "\n\n" not in block:
            continue
        metadata_text, annotation_text = block.split("\n\n", 1)
        metadata: dict[str, Any] = {"id": match.group(1)}
        for line in metadata_text.splitlines():
            if ":" not in line:
                continue
            key, raw = line.split(":", 1)
            value = raw.strip()
            if value.startswith('"') and value.endswith('"'):
                value = value[1:-1]
            elif re.fullmatch(r"\d+", value):
                value = int(value)
            metadata[key.strip()] = value
        annotations.append({"metadata": metadata, "text": annotation_text.strip("\n")})
    return main_text, annotations


def assertion_for_mention(mention: dict[str, Any]) -> str:
    if mention.get("person_id") is None:
        return "unknown"
    if str(mention.get("resolution_method", "")).startswith("exact"):
        return "attested"
    return "inferred"


def resolution_mode_for_mention(mention: dict[str, Any]) -> str:
    method = str(mention.get("resolution_method", ""))
    if method.startswith("exact") or method == "orthographic_variant":
        return "exact"
    if "ambiguous" in method:
        return "ambiguous"
    return "contextual"


def main() -> int:
    entry_text = ENTRY_PATH.read_text(encoding="utf-8")
    metadata = parse_frontmatter(entry_text)
    main_text, annotations = parse_entry_sections(entry_text)
    punctuation_document = read_json(ROOT / PUNCTUATION_RELATIVE_PATH)
    punctuation_records = punctuation_document.get("records", [])
    punctuation_record = next(
        (record for record in punctuation_records if record.get("entry_id") == ENTRY_ID),
        None,
    )
    if punctuation_record is None:
        raise ValueError(f"missing reviewed punctuation record for {ENTRY_ID}")
    canonical_entry_path = ENTRY_PATH.relative_to(ROOT).as_posix()
    if punctuation_record.get("base_canonical_entry_path") != canonical_entry_path:
        raise ValueError("punctuation record points to a different canonical entry path")
    if punctuation_record.get("base_canonical_entry_sha256") != sha256_file(ENTRY_PATH):
        raise ValueError("punctuation record base hash does not match the canonical entry")
    annotation_by_id = {annotation["metadata"]["id"]: annotation for annotation in annotations}
    canonical_reading_sections = {
        "main_text": main_text,
        "liu_annotation": annotation_by_id["annotation-001"]["text"],
    }
    punctuation_errors = validate_punctuation_round_trip(
        punctuation_record,
        canonical_reading_sections,
    )
    if punctuation_errors:
        raise ValueError("invalid reviewed punctuation record: " + "; ".join(punctuation_errors))
    reading = build_display_reading(punctuation_record, OpenCC("t2s"))
    existing_people = read_json(PEOPLE_PATH)["people"]
    existing_aliases = read_json(ALIASES_PATH)["aliases"]
    existing_mentions = [
        mention
        for mention in read_json(MENTIONS_PATH)["mentions"]
        if mention.get("entry_id") == ENTRY_ID
    ]
    existing_mentions.sort(key=lambda item: item["mention_id"])

    source = {
        "id": "source-001",
        "work": "世說新語",
        "witness_id": "shishuo-kanripo-wyg",
        "edition": "文淵閣四庫全書 / WYG",
        "source_type": "machine-text",
        "local_path": "shishuoSources/shishuo",
        "remote_record": "https://github.com/kanripo/KR3l0002.git",
        "provenance_status": "resolved",
        "text_authority": "default diplomatic machine-text witness",
        "structure_authority": "canonical reviewed Shishuo entry",
        "review_status": "reviewed",
        "notes": "WP1 source record points to the existing canonical entry; no source text is edited.",
    }
    jinshu_source = {
        "id": "source-002",
        "work": "晉書",
        "witness_id": "jinshu-wikisource-siku",
        "edition": "欽定四庫全書本",
        "source_type": "machine-text",
        "local_path": "sources/downloads/jinshu/wikisource-siku",
        "remote_record": "https://zh.wikisource.org/wiki/晉書_(四庫全書本)",
        "provenance_status": "resolved",
        "text_authority": "default diplomatic machine-text witness for the complete local Jinshu corpus",
        "structure_authority": "reviewed Jinshu structural unit",
        "review_status": "reviewed",
        "notes": "Direct local attestations for the WP1 person sample use exact text from processed Jinshu units; no reference-witness text is merged.",
    }

    main_mention = next((item for item in existing_mentions if item["section"] == "main_text"), None)
    annotation_mention = next((item for item in existing_mentions if item["section"] == "liu_annotation"), None)
    if main_mention is None or annotation_mention is None:
        raise ValueError("06-yaliang-019 must contain main text and Liu Xiaobiao annotation mentions")

    def locator(mention: dict[str, Any], *, annotation_id: str | None = None) -> dict[str, Any]:
        span = mention["evidence"]["provenance"]["source_span"]
        start = span.get("start", {})
        end = span.get("end", {})
        return {
            "artifact_type": "shishuo_entry",
            "entry_id": ENTRY_ID,
            "chapter_id": metadata.get("chapter_id"),
            "artifact_path": ENTRY_PATH.relative_to(ROOT).as_posix(),
            "artifact_sha256": sha256_file(ENTRY_PATH),
            "source_normalized_filename": metadata.get("source_normalized_filename"),
            "normalized_line_start": start.get("normalized_line"),
            "normalized_line_end": end.get("normalized_line"),
            "page_marker_start": start.get("page_marker"),
            "page_marker_end": end.get("page_marker"),
            "annotation_id": annotation_id,
            "source_provenance": {
                "witness_id": source["witness_id"],
                "source_path": metadata.get("source_path"),
                "source_sha256": metadata.get("source_sha256"),
            },
        }

    def unit_locator(unit_id: str, quote: str) -> dict[str, Any]:
        relative_path = JINSHU_UNIT_PATHS[unit_id]
        unit_path = ROOT / relative_path
        unit_text = unit_path.read_text(encoding="utf-8")
        unit_metadata = parse_frontmatter(unit_text)
        if quote not in unit_text:
            raise ValueError(f"Jinshu evidence quote is absent from {relative_path}: {quote!r}")
        return {
            "artifact_type": "jinshu_unit",
            "unit_id": unit_id,
            "artifact_path": relative_path,
            "artifact_sha256": sha256_file(unit_path),
            "source_provenance": {
                "witness_id": unit_metadata["source_witness"],
                "source_path": unit_metadata["source_path"],
                "source_sha256": unit_metadata["source_sha256"],
            },
        }

    annotation_metadata = annotation_by_id.get("annotation-001", {}).get("metadata", {})
    evidence = [
        {
            "id": "evidence-001",
            "source_id": source["id"],
            "evidence_type": "primary_text",
            "quote": main_text,
            "locator": locator(main_mention),
            "assertion_status": "attested",
            "review_status": "reviewed",
            "notes": "Exact main-text section generated from the canonical entry.",
        },
        {
            "id": "evidence-002",
            "source_id": source["id"],
            "evidence_type": "annotation",
            "quote": annotation_by_id["annotation-001"]["text"],
            "locator": locator(annotation_mention, annotation_id="annotation-001"),
            "assertion_status": "attested",
            "review_status": "reviewed",
            "notes": "Exact top-level Liu Xiaobiao annotation block.",
        },
        {
            "id": "evidence-003",
            "source_id": source["id"],
            "evidence_type": "editorial",
            "quote": metadata["chapter_heading"],
            "locator": locator(main_mention),
            "assertion_status": "attested",
            "review_status": "reviewed",
            "notes": "Canonical chapter heading retained as structural provenance.",
        },
        {
            "id": "evidence-004",
            "source_id": jinshu_source["id"],
            "evidence_type": "primary_text",
            "quote": "王導字茂",
            "locator": unit_locator("065-liezhuan-001", "王導字茂"),
            "assertion_status": "attested",
            "review_status": "reviewed",
            "notes": "Direct biography opening in the processed Jinshu unit for 王導.",
        },
        {
            "id": "evidence-005",
            "source_id": jinshu_source["id"],
            "evidence_type": "primary_text",
            "quote": "王凝之妻謝氏字道韞",
            "locator": unit_locator("096-liezhuan-016", "王凝之妻謝氏字道韞"),
            "assertion_status": "attested",
            "review_status": "reviewed",
            "notes": "Direct opening of the processed Jinshu unit identifying 王凝之 and 謝氏字道韞.",
        },
        {
            "id": "evidence-006",
            "source_id": jinshu_source["id"],
            "evidence_type": "primary_text",
            "quote": "謝安字安石",
            "locator": unit_locator("079-liezhuan-002", "謝安字安石"),
            "assertion_status": "attested",
            "review_status": "reviewed",
            "notes": "Direct biography opening in the processed Jinshu unit for 謝安.",
        },
    ]

    evidence_for_section = {
        "main_text": "evidence-001",
        "liu_annotation": "evidence-002",
    }
    sample_mentions: list[dict[str, Any]] = []
    for mention in existing_mentions:
        evidence_id = evidence_for_section[mention["section"]]
        sample_mentions.append(
            {
                "id": mention["mention_id"],
                "story_id": ENTRY_ID,
                "surface": mention["surface"],
                "section": mention["section"],
                "person_id": mention.get("person_id"),
                "candidate_person_ids": mention.get("candidate_person_ids", []),
                "alias_type": mention["alias_type"],
                "resolution_mode": resolution_mode_for_mention(mention),
                "confidence": "high" if mention.get("confidence") == "high" else (
                    "medium" if mention.get("confidence") == "medium" else "unresolved"
                ),
                "anchor": {
                    "text": mention["surface"],
                    "section": mention["section"],
                    "offset": mention["evidence"]["section_offset"],
                },
                "evidence_ids": [evidence_id],
                "assertion_status": assertion_for_mention(mention),
                "review_status": "candidate",
                "notes": "Copied from the existing conservative six-person mention pilot; unresolved titles remain unresolved.",
            }
        )

    sample_person_ids = [
        person_id
        for person_id in TARGET_PERSON_IDS
        if person_id in {mention.get("person_id") for mention in sample_mentions}
    ]
    aliases_by_id = {alias["alias_id"]: alias for alias in existing_aliases}
    sample_aliases: dict[str, list[dict[str, Any]]] = {person_id: [] for person_id in TARGET_PERSON_IDS}
    for mention in existing_mentions:
        person_id = mention.get("person_id")
        if person_id not in sample_aliases:
            continue
        alias = aliases_by_id.get(mention["alias_id"])
        if alias is None or any(item["surface"] == alias["surface"] for item in sample_aliases[person_id]):
            continue
        sample_aliases[person_id].append(
            {
                "surface": alias["surface"],
                "alias_type": alias["alias_type"],
                "resolution_mode": "exact" if alias["resolution_mode"] == "exact" else "contextual",
                "evidence_ids": [evidence_for_section[mention["section"]]],
                "review_status": "candidate",
            }
        )

    people_by_id = {person["person_id"]: person for person in existing_people}
    direct_jinshu_evidence = {
        "wang-dao": ["evidence-004"],
        "wang-ningzhi": ["evidence-005"],
        "xie-daoyun": ["evidence-005"],
        "xie-an": ["evidence-006"],
    }
    sample_people: list[dict[str, Any]] = []
    for person_id in TARGET_PERSON_IDS:
        person = people_by_id[person_id]
        person_evidence = sorted(
            {
                evidence_id
                for mention in sample_mentions
                if mention.get("person_id") == person_id
                for evidence_id in mention["evidence_ids"]
            }
        )
        person_evidence = sorted(set(person_evidence + direct_jinshu_evidence.get(person_id, [])))
        sample_people.append(
            {
                "id": person_id,
                "canonical_name": person["canonical_name"],
                "aliases": sample_aliases[person_id],
                "story_ids": [ENTRY_ID] if person_id in sample_person_ids else [],
                "evidence_ids": person_evidence,
                "assertion_status": "attested",
                "review_status": "candidate",
                "notes": "Identity carried forward from data/people.json; full Person Sketch remains outside WP1.",
            }
        )

    relation = {
        "id": "relation-001",
        "subject_id": "xi-jian",
        "object_id": "wang-xizhi",
        "relation_type": "kinship",
        "label": "婚姻亲属",
        "story_ids": [ENTRY_ID],
        "evidence_ids": ["evidence-002"],
        "time": {"status": "unknown", "label": None, "start_year": None, "end_year": None},
        "assertion_status": "attested",
        "review_status": "candidate",
        "notes": "The source annotation identifies the wife as 郗鑒's daughter and the story records the marriage; direction is a reader-facing label, not a reconstructed genealogy.",
    }

    era = {
        "id": "era-001",
        "title": "雅量",
        "theme": "雅量",
        "period": {"status": "unknown", "label": None, "start_year": None, "end_year": None},
        "description": "候选 Era Sketch；当前仅连接首个故事，跨篇目范围待人工审核。",
        "story_ids": [ENTRY_ID],
        "person_ids": sample_person_ids,
        "evidence_ids": ["evidence-003"],
        "assertion_status": "unknown",
        "review_status": "candidate",
        "notes": "This is a WP1 motif/reading candidate, not a completed historical period claim.",
    }

    story = {
        "id": ENTRY_ID,
        "title": "东床坦腹",
        "title_source": "project_label",
        "text": main_text,
        "source_entry_id": ENTRY_ID,
        "source_ids": [source["id"]],
        "evidence_ids": ["evidence-001", "evidence-002"],
        "person_ids": sample_person_ids,
        "mention_ids": [mention["id"] for mention in sample_mentions],
        "relation_ids": [relation["id"]],
        "era_ids": [era["id"]],
        "annotations": [
            {
                "id": annotation["metadata"]["id"],
                "text": annotation["text"],
                "source_location": "content/processed/shishuo/entries/06-yaliang/entry-019.md",
            }
            for annotation in annotations
        ],
        "summary": None,
        "time": {"status": "unknown", "label": None, "start_year": None, "end_year": None},
        "places": [
            {
                "name": "京口",
                "assertion_status": "attested",
                "review_status": "candidate",
                "evidence_ids": ["evidence-001"],
            }
        ],
        "assertion_status": "attested",
        "review_status": "reviewed",
        "notes": "Generated from the existing reviewed canonical entry; the title is a project reading label and the summary is intentionally TODO.",
    }

    manifest = {
        "schema": 1,
        "milestone": "milestone-1",
        "status": "in_progress",
        "reading_path": ["story", "person", "relation", "related_story", "era"],
        "scope": {
            "people": {
                "target_count": 6,
                "status": "candidate",
                "record_path": "data/annotation/wp1-people.json",
                "ids": list(TARGET_PERSON_IDS),
                "note": "Existing six-person pilot IDs are reused; final Person Sketch review is pending.",
            },
            "stories": {
                "target_min": 15,
                "target_max": 30,
                "status": "candidate/TODO",
                "validated_ids": [ENTRY_ID],
                "candidate_ids": [],
                "note": "Do not infer the remaining story set in WP1.",
            },
            "eras": {
                "target_min": 1,
                "status": "candidate",
                "validated_ids": [],
                "candidate_ids": [era["id"]],
                "note": "雅量 is a candidate reading motif, not yet a completed Era Sketch.",
            },
        },
        "sample": {"story_id": ENTRY_ID, "relation_id": relation["id"], "era_id": era["id"]},
    }

    records = {
        "sources": {"schema": 1, "records": [source, jinshu_source]},
        "stories": {"schema": 1, "records": [story]},
        "people": {"schema": 1, "records": sample_people},
        "mentions": {"schema": 1, "records": sample_mentions},
        "relations": {"schema": 1, "records": [relation]},
        "eras": {"schema": 1, "records": [era]},
        "evidence": {"schema": 1, "records": evidence},
    }
    paths = {
        "sources": ROOT / "data/sources/wp1-sources.json",
        "stories": ROOT / "data/annotation/wp1-stories.json",
        "people": ROOT / "data/annotation/wp1-people.json",
        "mentions": ROOT / "data/annotation/wp1-mentions.json",
        "relations": ROOT / "data/annotation/wp1-relations.json",
        "eras": ROOT / "data/annotation/wp1-eras.json",
        "evidence": ROOT / "data/evidence/wp1-evidence.json",
    }
    for key, path in paths.items():
        write_json(path, records[key])
    write_json(ROOT / "data/manifest/milestone-1.json", manifest)

    bundle_story = dict(story)
    bundle_story["reading"] = reading
    bundle = {
        "schema": 1,
        "generated_from": "scripts/build_wp1_sample.py",
        "stories": [bundle_story],
        "people": records["people"]["records"],
        "mentions": records["mentions"]["records"],
        "relations": records["relations"]["records"],
        "eras": records["eras"]["records"],
        "evidence": records["evidence"]["records"],
        "sources": records["sources"]["records"],
    }
    write_json(ROOT / "data/derived/wp1-site.json", bundle)
    write_json(ROOT / "site/public/data/wp1-site.json", bundle)
    print(f"built WP1 sample: {ENTRY_ID}; {len(sample_people)} people; {len(sample_mentions)} mentions")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
