#!/usr/bin/env python3
"""Normalize the downloaded Wikisource 四庫本 Jinshu pages.

The input is the locked MediaWiki API text under
``sources/downloads/jinshu/wikisource-siku``.  This normalizer removes
Wikisource presentation wrappers while retaining source-visible Chinese and
turning glyph placeholders, notes, and section markers into explicit comments.
It does not consult another witness and does not repair any reading.

The output is one UTF-8 Markdown file per canonical volume.  The complete
output hashes are recorded in ``normalization-manifest.lock.json`` because a
file cannot contain its own whole-file hash without a circular dependency;
each file also records the normalized-body hash in its front matter.
"""

from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import sys
from typing import Any, Mapping, Sequence


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE_ROOT = REPOSITORY_ROOT / "sources/downloads/jinshu/wikisource-siku"
DEFAULT_OUTPUT_DIR = REPOSITORY_ROOT / "content/processed/jinshu"
DEFAULT_MANIFEST = DEFAULT_OUTPUT_DIR / "normalization-manifest.lock.json"
WITNESS_ID = "jinshu-wikisource-siku"
WORK = "晉書"

TEMPLATE_START = "{{"
TEMPLATE_END = "}}"
SECTION_TAG_RE = re.compile(r"^\s*<(?P<value>史部,[^>]+)>\s*$")
ORIGINAL_HTML_COMMENT_RE = re.compile(r"<!--.*?-->", re.DOTALL)
RAW_MARKUP_RE = re.compile(r"</?(?:onlyinclude|poem)>")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_text(value: str) -> str:
    return sha256_bytes(value.encode("utf-8"))


def quote(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False)


def comment(kind: str, value: Any) -> str:
    """Return a structured comment whose payload preserves Chinese exactly."""

    return f"<!-- wikisource-{kind}: {quote(value)} -->"


def split_template_fields(body: str) -> list[str]:
    fields: list[str] = []
    start = 0
    depth = 0
    cursor = 0
    while cursor < len(body):
        if body.startswith(TEMPLATE_START, cursor):
            depth += 1
            cursor += 2
        elif body.startswith(TEMPLATE_END, cursor):
            depth = max(0, depth - 1)
            cursor += 2
        elif body[cursor] == "|" and depth == 0:
            fields.append(body[start:cursor])
            start = cursor + 1
            cursor += 1
        else:
            cursor += 1
    fields.append(body[start:])
    return fields


def matching_template_end(text: str, start: int) -> int:
    depth = 1
    cursor = start + 2
    while cursor < len(text) - 1:
        if text.startswith(TEMPLATE_START, cursor):
            depth += 1
            cursor += 2
        elif text.startswith(TEMPLATE_END, cursor):
            depth -= 1
            cursor += 2
            if depth == 0:
                return cursor
        else:
            cursor += 1
    raise ValueError(f"unclosed Wikisource template at character {start}")


def render_template_body(body: str, counters: Counter[str]) -> str:
    fields = split_template_fields(body)
    name = fields[0].strip()
    arguments = [field.strip() for field in fields[1:]]
    counters[name] += 1

    if name in {"SK anchor", "YL"}:
        return render_templates(arguments[0] if arguments else "", counters)
    if name == "SK notes":
        # Keep the complete annotation wikitext in one structured comment.
        # Rendering nested SKchar templates here would create nested HTML
        # comments and make the annotation scope ambiguous.  The raw source
        # remains locked separately, while this payload keeps every supplied
        # annotation character and placeholder traceable.
        return comment("note", {"wikitext": body})
    if name in {"SKchar", "SKchar2"}:
        value = render_templates(arguments[0] if arguments else "", counters)
        return comment(name, {"value": value})
    if name in {"SKQS header", "SKQS footer"}:
        return comment(name.lower().replace(" ", "-"), {"wikitext": body})
    if name == "PD-old":
        return comment("license", {"template": body})
    if name == "SK list":
        return comment("navigation", {"template": "SK list", "status": "removed"})

    # Unknown templates are retained as structured source metadata rather than
    # being rendered or silently discarded.
    return comment("template", {"wikitext": body})


def render_templates(text: str, counters: Counter[str]) -> str:
    pieces: list[str] = []
    cursor = 0
    while cursor < len(text):
        start = text.find(TEMPLATE_START, cursor)
        if start < 0:
            pieces.append(text[cursor:])
            break
        pieces.append(text[cursor:start])
        end = matching_template_end(text, start)
        pieces.append(render_template_body(text[start + 2 : end - 2], counters))
        cursor = end
    return "".join(pieces)


def render_section_tag(line: str) -> tuple[str, dict[str, Any] | None]:
    match = SECTION_TAG_RE.fullmatch(line)
    if match is None:
        return line, None
    value = match.group("value")
    metadata: dict[str, Any] = {"value": value}
    if value == "史部,正史類,晉書,卷一":
        # Wikisource puts the first volume's body after this section tag and
        # does not repeat the normal 卷一/帝紀第一 headings in that section.
        metadata.update(
            {
                "volume": 1,
                "section_role": "main-volume-start",
                "category": "benji",
                "category_heading": "帝紀第一",
                "reason": "explicit Wikisource section tag; category mapping is present in the page catalogue",
            }
        )
        return (
            comment("section", metadata)
            + "\n"
            + "<!-- wikisource-volume-start: "
            + quote(
                {
                    "volume": 1,
                    "category": "benji",
                    "category_heading": "帝紀第一",
                }
            )
            + " -->",
            metadata,
        )
    return comment("section", metadata), metadata


def normalize_body(raw_text: str) -> tuple[str, dict[str, int], list[str]]:
    """Return normalized body, template statistics, and unusual markup notes."""

    counters: Counter[str] = Counter()
    notes: list[str] = []
    # The leading Wikisource editing instruction is presentation metadata, not
    # historical text.  It is deliberately excluded before template parsing.
    text = ORIGINAL_HTML_COMMENT_RE.sub("", raw_text)
    text = text.replace("<onlyinclude>", "").replace("</onlyinclude>", "")
    text = text.replace("<poem>", "").replace("</poem>", "")
    rendered = render_templates(text, counters)
    # The API export places the UTF-8 BOM after the opening <poem> wrapper on
    # volume one.  Once the wrapper is removed it can occur mid-line; it is
    # still only an encoding marker.
    rendered = rendered.replace("\ufeff", "")

    lines: list[str] = []
    for line in rendered.splitlines():
        normalized, section_metadata = render_section_tag(line)
        if section_metadata is not None and section_metadata.get("value") == "史部,正史類,晉書":
            # This is a Wikisource category presentation tag.  The structured
            # comment retains its value but contributes no historical text.
            lines.append(normalized)
        else:
            lines.extend(normalized.splitlines())

    # The API text can contain a BOM at the start of the first body line.  It
    # is an encoding marker, not a historical character.
    if lines:
        lines[0] = lines[0].lstrip("\ufeff")
    body = "\n".join(lines).rstrip("\n") + "\n"

    known = {
        "SK anchor",
        "YL",
        "SK notes",
        "SKchar",
        "SKchar2",
        "SKQS header",
        "SKQS footer",
        "PD-old",
        "SK list",
    }
    for name in sorted(set(counters) - known):
        notes.append(f"unknown template retained as metadata: {name}")
    return body, dict(sorted(counters.items())), notes


def parse_manifest(source_root: Path) -> dict[str, Any]:
    manifest_path = source_root / "manifest.lock.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    records = manifest.get("records")
    if not isinstance(records, list):
        raise ValueError("Jinshu Wikisource lock manifest has no records list")
    by_volume = {int(record["volume"]): record for record in records}
    expected = list(range(1, 131))
    if sorted(by_volume) != expected or len(by_volume) != len(records):
        raise ValueError("Jinshu Wikisource lock manifest is not exactly volumes 1-130")
    return manifest


def record_path(root: Path, value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else root / path


def front_matter(fields: Mapping[str, Any]) -> str:
    lines = ["---"]
    for key, value in fields.items():
        if value is None:
            rendered = "null"
        elif isinstance(value, bool):
            rendered = "true" if value else "false"
        elif isinstance(value, (int, float)):
            rendered = str(value)
        else:
            rendered = quote(str(value))
        lines.append(f"{key}: {rendered}")
    lines.extend(["---", ""])
    return "\n".join(lines)


def normalize_all(
    *,
    source_root: Path = DEFAULT_SOURCE_ROOT,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    manifest_path: Path = DEFAULT_MANIFEST,
    root: Path = REPOSITORY_ROOT,
) -> dict[str, Any]:
    lock = parse_manifest(source_root)
    output_dir.mkdir(parents=True, exist_ok=True)
    records: list[dict[str, Any]] = []
    for record in sorted(lock["records"], key=lambda item: int(item["volume"])):
        volume = int(record["volume"])
        raw_path = record_path(root, str(record["text_path"]))
        raw_bytes = raw_path.read_bytes()
        actual_raw_sha = sha256_bytes(raw_bytes)
        expected_raw_sha = str(record.get("text_sha256", ""))
        if expected_raw_sha and actual_raw_sha != expected_raw_sha:
            raise ValueError(f"volume {volume}: raw text SHA-256 differs from lock manifest")
        raw_text = raw_bytes.decode("utf-8")
        body, template_counts, normalization_notes = normalize_body(raw_text)
        body_sha = sha256_text(body)
        output_path = output_dir / f"volume-{volume:03d}.md"
        try:
            raw_relative = raw_path.relative_to(root).as_posix()
        except ValueError:
            raw_relative = raw_path.as_posix()
        fields: dict[str, Any] = {
            "schema": 1,
            "normalizer": "scripts/normalize_jinshu_wikisource.py",
            "normalizer_version": 1,
            "source_witness": WITNESS_ID,
            "source_work": WORK,
            "source_page_title": record.get("page_title"),
            "source_url": record.get("source_url"),
            "source_api_url": record.get("api_url"),
            "source_page_id": record.get("page_id"),
            "source_revision_id": record.get("revision_id"),
            "source_revision_timestamp": record.get("revision_timestamp"),
            "source_volume": volume,
            "source_text_path": raw_relative,
            "source_text_sha256": actual_raw_sha,
            "source_text_bytes": len(raw_bytes),
            "source_text_line_count": len(raw_text.splitlines()),
            "source_raw_api_path": record.get("raw_api_path"),
            "source_raw_api_sha256": record.get("raw_api_sha256"),
            "normalized_body_sha256": body_sha,
            "normalized_output_hash_scope": "whole Markdown file; complete hash is in normalization-manifest.lock.json",
            "markup_policy": "Remove Wikisource presentation wrappers; retain source text and structured metadata for notes, glyph placeholders, anchors, and section markers.",
        }
        document = front_matter(fields) + body
        output_bytes = document.encode("utf-8")
        output_path.write_bytes(output_bytes)
        try:
            output_relative = output_path.relative_to(root).as_posix()
        except ValueError:
            output_relative = output_path.as_posix()
        records.append(
            {
                "volume": volume,
                "source_witness": WITNESS_ID,
                "source_page_title": record.get("page_title"),
                "source_url": record.get("source_url"),
                "source_api_url": record.get("api_url"),
                "source_page_id": record.get("page_id"),
                "source_revision_id": record.get("revision_id"),
                "source_revision_timestamp": record.get("revision_timestamp"),
                "source_text_path": raw_relative,
                "source_text_sha256": actual_raw_sha,
                "source_text_bytes": len(raw_bytes),
                "source_raw_api_path": record.get("raw_api_path"),
                "source_raw_api_sha256": record.get("raw_api_sha256"),
                "normalized_path": output_relative,
                "normalized_body_sha256": body_sha,
                "normalized_output_sha256": sha256_bytes(output_bytes),
                "normalized_output_bytes": len(output_bytes),
                "normalized_output_line_count": len(document.splitlines()),
                "template_counts": template_counts,
                "normalization_notes": normalization_notes,
            }
        )

    output_manifest = {
        "schema": 1,
        "stage": "jinshu-wikisource-normalization",
        "witness_id": WITNESS_ID,
        "work": WORK,
        "source_lock_manifest": str((source_root / "manifest.lock.json").relative_to(root)),
        "volume_count": len(records),
        "volumes": records,
        "policy": "No character, punctuation, or historical correction; only MediaWiki presentation markup is removed or represented as structured comments.",
    }
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(
        json.dumps(output_manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return output_manifest


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", type=Path, default=DEFAULT_SOURCE_ROOT)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--root", type=Path, default=REPOSITORY_ROOT)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_argument_parser().parse_args(argv)
    try:
        result = normalize_all(
            source_root=args.source_root,
            output_dir=args.output_dir,
            manifest_path=args.manifest,
            root=args.root,
        )
    except (OSError, UnicodeError, ValueError, json.JSONDecodeError) as error:
        print(str(error), file=sys.stderr)
        return 1
    print(f"normalized {result['volume_count']} Jinshu volumes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
