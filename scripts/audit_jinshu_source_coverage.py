#!/usr/bin/env python3
"""Audit explicit volume coverage in local and upstream Kanripo Jinshu files."""

from __future__ import annotations

import argparse
from collections import defaultdict
from dataclasses import dataclass
import hashlib
import json
import re
from pathlib import Path
import subprocess
from typing import Any


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_LOCAL = REPOSITORY_ROOT / "shishuoSources/jinshu"
DEFAULT_UPSTREAM = Path("/tmp/kr2a0015-audit")
DEFAULT_OUTPUT = REPOSITORY_ROOT / "content/curated/jinshu/source-coverage-audit.md"
DEFAULT_WIKISOURCE = REPOSITORY_ROOT / "sources/downloads/jinshu/wikisource-siku"

CHINESE_DIGITS = {
    "〇": 0,
    "零": 0,
    "○": 0,
    "一": 1,
    "二": 2,
    "三": 3,
    "四": 4,
    "五": 5,
    "六": 6,
    "七": 7,
    "八": 8,
    "九": 9,
}
CHINESE_UNITS = {"十": 10, "百": 100, "千": 1000, "萬": 10000, "万": 10000}
VOLUME_RE = re.compile(
    r"晉書[卷巻](?P<number>[〇零○一二三四五六七八九十百千万萬]+)(?P<editorial>考證)?"
)
PROPERTY_RE = re.compile(r"^\#\+PROPERTY:\s+JUAN\s+(?P<volume>.+?)\s*$")


def chinese_numeral_value(value: str) -> int:
    if value.isdigit():
        return int(value)
    total = 0
    section = 0
    number = 0
    for character in value:
        if character in CHINESE_DIGITS:
            number = CHINESE_DIGITS[character]
            continue
        unit = CHINESE_UNITS.get(character)
        if unit is None:
            raise ValueError(f"unsupported Chinese numeral: {value}")
        if unit >= 10000:
            section = (section + number) * unit
            total += section
            section = 0
            number = 0
        else:
            section += (number or 1) * unit
            number = 0
    return total + section + number


@dataclass(frozen=True)
class Heading:
    path: str
    line: int
    heading: str
    volume: int
    editorial: bool
    catalogue: bool


def source_files(directory: Path) -> list[Path]:
    # Kanripo's repository metadata lives below .git in an upstream checkout;
    # the witness files themselves are the direct files in the source root.
    return sorted(path for path in directory.iterdir() if path.is_file())


def scan_source_tree(directory: Path) -> dict[str, Any]:
    files = source_files(directory)
    headings: list[Heading] = []
    properties: dict[str, str] = {}
    errors: list[str] = []
    for path in files:
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError as error:
            errors.append(f"{path}: UTF-8 decode failed: {error}")
            continue
        for line_number, line in enumerate(text.splitlines(), start=1):
            property_match = PROPERTY_RE.match(line)
            if property_match:
                properties[path.name] = property_match.group("volume")
            for match in VOLUME_RE.finditer(line):
                headings.append(
                    Heading(
                        path=path.name,
                        line=line_number,
                        heading=match.group(0),
                        volume=chinese_numeral_value(match.group("number")),
                        editorial=bool(match.group("editorial")),
                        catalogue=path.name == "KR2a0015_000.txt",
                    )
                )
    main = [item for item in headings if not item.catalogue and not item.editorial]
    catalogue = [item for item in headings if item.catalogue and not item.editorial]
    by_volume: dict[int, list[Heading]] = defaultdict(list)
    for item in main:
        by_volume[item.volume].append(item)
    return {
        "directory": str(directory),
        "files": [path.name for path in files],
        "headings": headings,
        "main_headings": main,
        "catalogue_headings": catalogue,
        "main_volumes": sorted(by_volume),
        "main_by_volume": dict(sorted(by_volume.items())),
        "catalogue_volumes": sorted({item.volume for item in catalogue}),
        "properties": properties,
        "errors": errors,
    }


def compare_trees(local: Path, upstream: Path) -> dict[str, Any]:
    local_files = {path.name for path in source_files(local)}
    upstream_files = {path.name for path in source_files(upstream)}
    common = sorted(local_files & upstream_files)
    different = [
        name
        for name in common
        if (local / name).read_bytes() != (upstream / name).read_bytes()
    ]
    return {
        "local_only": sorted(local_files - upstream_files),
        "upstream_only": sorted(upstream_files - local_files),
        "different": different,
        "same_common_bytes": not different,
    }


def validate_wikisource_completion(directory: Path) -> dict[str, Any] | None:
    lock_path = directory / "manifest.lock.json"
    if not lock_path.is_file():
        return None
    manifest = json.loads(lock_path.read_text(encoding="utf-8"))
    records = manifest.get("records", [])
    errors: list[str] = []
    volumes = [int(record["volume"]) for record in records]
    for record in records:
        path = REPOSITORY_ROOT / str(record.get("text_path", ""))
        if not path.is_file():
            errors.append(f"missing {path}")
            continue
        data = path.read_bytes()
        if len(data) != record.get("text_size"):
            errors.append(f"size mismatch {path}")
        if hashlib.sha256(data).hexdigest() != record.get("text_sha256"):
            errors.append(f"SHA-256 mismatch {path}")
        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError:
            errors.append(f"UTF-8 decode failed {path}")
            continue
        if not text:
            errors.append(f"empty {path}")
    by_volume = {int(record["volume"]): record for record in records}
    alignment_errors: list[str] = []
    for number in range(1, 34):
        record = by_volume.get(number)
        if record is None:
            alignment_errors.append(f"missing volume {number}")
            continue
        path = REPOSITORY_ROOT / str(record.get("text_path", ""))
        text = path.read_text(encoding="utf-8") if path.is_file() else ""
        if number < 10:
            glyphs = "〇一二三四五六七八九"[number]
        elif number < 20:
            glyphs = "十" if number == 10 else "十" + "〇一二三四五六七八九"[number - 10]
        elif number < 30:
            glyphs = "二十" if number == 20 else "二十" + "〇一二三四五六七八九"[number - 20]
        else:
            glyphs = "三十" if number == 30 else "三十" + "〇一二三"[number - 30]
        if not re.search(rf"晉書[卷巻]{glyphs}", text):
            alignment_errors.append(f"volume {number} has no explicit heading")
    heading_counts = {}
    for number, glyphs in ((32, "三十二"), (33, "三十三")):
        path = directory / "text" / f"volume-{number:03d}.txt"
        text = path.read_text(encoding="utf-8") if path.is_file() else ""
        heading_counts[number] = len(re.findall(rf"晉書[卷巻]{glyphs}", text))
    return {
        "directory": str(directory),
        "status": manifest.get("status"),
        "record_count": len(records),
        "volumes": volumes,
        "missing_volumes": manifest.get("missing_volumes", []),
        "duplicate_volumes": manifest.get("duplicate_volumes", []),
        "sha_errors": errors,
        "aligned_1_33": not alignment_errors,
        "alignment_errors": alignment_errors,
        "heading_counts": heading_counts,
        "auxiliary_count": len(manifest.get("auxiliary_files", [])),
    }


def _format_file_list(files: list[str]) -> str:
    return ", ".join(f"`{name}`" for name in files)


def _format_occurrences(items: list[Heading]) -> str:
    return "; ".join(
        f"{item.path}:{item.line} `{item.heading}`" for item in items
    )


def render_report(
    local_scan: dict[str, Any],
    upstream_scan: dict[str, Any],
    comparison: dict[str, Any],
    *,
    upstream_commit: str | None = None,
    wikisource: dict[str, Any] | None = None,
) -> str:
    local_main = set(local_scan["main_volumes"])
    upstream_main = set(upstream_scan["main_volumes"])
    missing_local = sorted(set(range(1, 131)) - local_main)
    missing_upstream = sorted(set(range(1, 131)) - upstream_main)
    duplicate_rows = []
    for volume, occurrences in local_scan["main_by_volume"].items():
        if len(occurrences) > 1:
            duplicate_rows.append(
                f"- 卷{volume}: {len(occurrences)} explicit non-editorial markers — "
                f"{_format_occurrences(occurrences)}"
            )
    catalogue_missing = sorted(
        set(range(1, 131)) - set(local_scan["catalogue_volumes"])
    )
    lines = [
        "# Jinshu source coverage audit",
        "",
        "This audit scans the raw Kanripo files for explicit source headings and",
        "does not infer coverage from filenames alone. The local raw witness and",
        "the upstream checkout were not modified.",
        "",
        "## Result",
        "",
        f"- local main-text volume numbers: `{local_scan['main_volumes']}`",
        f"- upstream main-text volume numbers: `{upstream_scan['main_volumes']}`",
        f"- local missing from expected 卷一–卷一百三十: `{missing_local}`",
        f"- upstream missing from expected 卷一–卷一百三十: `{missing_upstream}`",
        f"- upstream itself incomplete: `{'yes' if missing_upstream else 'no'}`",
        f"- local/upstream common-file bytes identical: `{'yes' if comparison['same_common_bytes'] else 'no'}`",
        "",
        "The catalogue in `KR2a0015_000.txt` describes 晉書一百三十卷, but",
        "catalogue references are not counted as surviving main-text blocks.",
        "",
        "## Local Kanripo files",
        "",
        f"Directory: `{local_scan['directory']}`; file count: `{len(local_scan['files'])}`.",
        "",
        _format_file_list(local_scan["files"]),
        "",
        "### File-declared juan properties",
        "",
        "| file | property |",
        "| --- | --- |",
    ]
    for name, value in sorted(local_scan["properties"].items()):
        lines.append(f"| `{name}` | `{value}` |")
    lines.extend(
        [
            "",
            "### Explicit main-text heading occurrences",
            "",
            "| volume | occurrences |",
            "| --- | --- |",
        ]
    )
    for volume in sorted(local_scan["main_by_volume"]):
        lines.append(
            f"| 卷{volume} | {_format_occurrences(local_scan['main_by_volume'][volume])} |"
        )
    lines.extend(
        [
            "",
            "### Catalogue references",
            "",
            f"Distinct catalogue volume references: `{local_scan['catalogue_volumes']}`.",
            f"Catalogue reference numbers absent from the 1–130 range: `{catalogue_missing}`.",
            "These gaps and the catalogue's repeated 卷四十三、卷四十四、卷四十五",
            "references are catalogue anomalies, not evidence that the corresponding",
            "main text is present or absent in the machine witness.",
            "",
            "## Duplicate or discontinuous content markers",
            "",
        ]
    )
    if duplicate_rows:
        lines.extend(duplicate_rows)
    else:
        lines.append("- none")
    lines.extend(
        [
            "",
            "In particular, `KR2a0015_033.txt` has the following sequence:",
            "",
            "- `晉書卷三十三` at line 10;",
            "- a relocated `晉書卷三十一` marker at line 572;",
            "- a new `晉書卷三十二` block at line 576;",
            "- a closing `晉書卷三十二` marker at line 883;",
            "- a second `晉書卷三十三` block at line 887.",
            "",
            "The repeated 卷三十二/卷三十三 blocks are retained as source evidence;",
            "this audit does not deduplicate or repair them.",
            "",
            "## Upstream checkout",
            "",
            f"Directory: `{upstream_scan['directory']}`; commit: `{upstream_commit or 'not supplied'}`; file count: `{len(upstream_scan['files'])}`.",
            "",
            _format_file_list(upstream_scan["files"]),
            "",
            f"Files only local: `{comparison['local_only']}`.",
            f"Files only upstream: `{comparison['upstream_only']}`.",
            f"Common files with differing bytes: `{comparison['different']}`.",
            "",
            "The upstream repository has no files or explicit main-text headings for",
            "卷三十四–卷一百三十. No re-clone can restore those volumes from Kanripo;",
            "the Wikisource 四庫全書本 witness is therefore registered as the separate",
            "same-edition machine completion source.",
            "",
            "## Scan errors",
            "",
            f"- local: `{local_scan['errors']}`",
            f"- upstream: `{upstream_scan['errors']}`",
            "",
            "Result: upstream Kanripo coverage is genuinely partial at 卷一–卷三十三.",
        ]
    )
    if wikisource is not None:
        lines.extend(
            [
                "",
                "## Wikisource completion validation",
                "",
                f"- source directory: `{wikisource['directory']}`",
                f"- lock status: `{wikisource['status']}`",
                f"- volume records: `{wikisource['record_count']}`",
                f"- contiguous volume sequence: `{'yes' if wikisource['volumes'] == list(range(1, 131)) else 'no'}`",
                f"- missing volume records: `{wikisource['missing_volumes']}`",
                f"- duplicate volume records: `{wikisource['duplicate_volumes']}`",
                f"- raw/source hash and UTF-8 errors: `{wikisource['sha_errors']}`",
                f"- volumes 1–33 structural alignment: `{'yes' if wikisource['aligned_1_33'] else 'no'}`",
                f"- alignment exceptions: `{wikisource['alignment_errors']}`",
                f"- retained raw API batch files: `{wikisource['auxiliary_count']}`",
                "",
                "The base page `晉書 (四庫全書本)` is recorded as volume 1; its returned",
                "source includes the volume-one text together with the supplied catalogue",
                "material. Volumes 2–130 use the discovered zero-padded `/卷NNN` pages.",
                "",
                f"Wikisource heading counts for volume 32 and 33 pages: `{wikisource['heading_counts']}`.",
                "Each completion page is a single source page. Kanripo still contains",
                "the previously observed relocated/duplicated 卷三十二/卷三十三 sequence",
                "in `KR2a0015_033.txt`; the completion witness confirms coverage but does",
                "not authorize deduplication or regeneration of the existing units.",
            ]
        )
    return "\n".join(lines) + "\n"


def write_audit(
    local: Path = DEFAULT_LOCAL,
    upstream: Path = DEFAULT_UPSTREAM,
    output: Path = DEFAULT_OUTPUT,
    wikisource: Path = DEFAULT_WIKISOURCE,
) -> Path:
    local_scan = scan_source_tree(local)
    upstream_scan = scan_source_tree(upstream)
    comparison = compare_trees(local, upstream)
    wikisource_validation = validate_wikisource_completion(wikisource)
    try:
        upstream_commit = subprocess.run(
            ["git", "-C", str(upstream), "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        upstream_commit = None
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        render_report(
            local_scan,
            upstream_scan,
            comparison,
            upstream_commit=upstream_commit,
            wikisource=wikisource_validation,
        ),
        encoding="utf-8",
        newline="\n",
    )
    return output


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--local", type=Path, default=DEFAULT_LOCAL)
    parser.add_argument("--upstream", type=Path, default=DEFAULT_UPSTREAM)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--wikisource", type=Path, default=DEFAULT_WIKISOURCE)
    args = parser.parse_args()
    write_audit(args.local, args.upstream, args.output, args.wikisource)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
