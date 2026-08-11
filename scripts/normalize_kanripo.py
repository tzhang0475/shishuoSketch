#!/usr/bin/env python3
"""Normalize Kanripo TXT files into provenance-preserving Markdown.

This module deliberately performs only structural normalization.  It does not
try to identify people, relationships, or even all semantic text boundaries.
The source text is read as UTF-8, Kanripo page markers are moved into HTML
comments, and the Kanripo pilcrow line terminator is replaced by a normal LF.
All character data in source content is otherwise left alone.

The command line interface processes one or more TXT files, or the two source
collections below ``shishuoSources/`` when no paths are supplied::

    python scripts/normalize_kanripo.py
    python scripts/normalize_kanripo.py --book shishuo
    python scripts/normalize_kanripo.py shishuoSources/jinshu/KR2a0015_006.txt

One source file produces one Markdown file at the corresponding path below
``content/processed/``.  The source tree is never written.
"""

from __future__ import annotations

import argparse
from collections import OrderedDict
import hashlib
import json
from pathlib import Path
import re
import sys
from typing import Iterable, Mapping, Sequence

try:
    from .source_paths import (
        DEFAULT_CONFIG_PATH,
        load_sources_config,
        repository_root_for_config,
    )
except ImportError:  # pragma: no cover - exercised by direct script execution
    from source_paths import (
        DEFAULT_CONFIG_PATH,
        load_sources_config,
        repository_root_for_config,
    )


PILCROW = "¶"
PAGE_MARKER_RE = re.compile(r"<pb:[^>]+>")
PROPERTY_RE = re.compile(
    r"^#\+PROPERTY:[ \t]+([^ \t]+)(?:[ \t](.*))?$"
)
ORG_KEYWORD_RE = re.compile(
    r"^#\+([A-Za-z][A-Za-z0-9_-]*):(?:[ \t](.*))?$"
)
EMACS_MODE_RE = re.compile(r"^# -\*-.*-\*-$")

NORMALIZER_VERSION = 1
DEFAULT_SOURCE_ROOT = Path("shishuoSources")
DEFAULT_OUTPUT_ROOT = Path("content/processed")
BOOKS = ("shishuo", "jinshu")


def _yaml_string(value: str) -> str:
    """Return a JSON-quoted scalar, which is also valid YAML."""

    return json.dumps(value, ensure_ascii=False)


def _yaml_key(value: str) -> str:
    """Quote dynamic YAML keys so unusual Kanripo keys remain safe."""

    if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_-]*", value):
        return value
    return _yaml_string(value)


def _without_line_ending(line: str) -> str:
    """Remove only the physical newline, preserving all other whitespace."""

    if line.endswith("\n"):
        line = line[:-1]
    if line.endswith("\r"):
        line = line[:-1]
    return line


def _parse_metadata_line(line: str) -> tuple[str, str, str] | None:
    """Return ``(kind, key, value)`` for a recognized metadata line.

    ``value`` is retained exactly, including trailing spaces.  The raw line is
    also stored in the output front matter, so no header spelling or spacing is
    lost by this convenience parser.
    """

    if EMACS_MODE_RE.fullmatch(line):
        return ("emacs", "mode", line)

    property_match = PROPERTY_RE.fullmatch(line)
    if property_match:
        return ("property", property_match.group(1), property_match.group(2) or "")

    keyword_match = ORG_KEYWORD_RE.fullmatch(line)
    if keyword_match:
        return ("keyword", keyword_match.group(1), keyword_match.group(2) or "")

    return None


def _display_path(path: Path) -> str:
    """Use a repository-relative path when possible, never a cwd-dependent one."""

    resolved = path.resolve()
    try:
        return resolved.relative_to(Path.cwd().resolve()).as_posix()
    except ValueError:
        return resolved.as_posix()


def _first_clean(mapping: Mapping[str, Sequence[str]], key: str) -> str:
    values = mapping.get(key, ())
    return values[0].strip() if values else ""


def _summary_property(properties: Mapping[str, Sequence[str]], key: str) -> str:
    """Return a human-friendly summary while retaining raw values elsewhere."""

    return _first_clean(properties, key)


def _append_yaml_list(lines: list[str], values: Sequence[str], indent: str = "  ") -> None:
    if not values:
        lines.append(f"{indent}[]")
        return
    for value in values:
        lines.append(f"{indent}- {_yaml_string(value)}")


def _append_yaml_mapping(
    lines: list[str], mapping: Mapping[str, Sequence[str]], indent: str = "  "
) -> None:
    if not mapping:
        lines.append(f"{indent}{{}}")
        return
    for key, values in mapping.items():
        lines.append(f"{indent}{_yaml_key(key)}:")
        _append_yaml_list(lines, values, indent + "  ")


def _frontmatter(
    *,
    source_path: str,
    source_bytes: int,
    source_line_count: int,
    source_sha256: str,
    page_marker_count: int,
    pilcrow_count: int,
    headers: Sequence[str],
    keywords: Mapping[str, Sequence[str]],
    properties: Mapping[str, Sequence[str]],
) -> str:
    """Build deterministic YAML front matter for one normalized source file."""

    title = _first_clean(keywords, "TITLE")
    lines = [
        "---",
        "schema: 1",
        f"normalizer: {_yaml_string('scripts/normalize_kanripo.py')}",
        f"normalizer_version: {NORMALIZER_VERSION}",
        f"source_path: {_yaml_string(source_path)}",
        f"source_encoding: {_yaml_string('UTF-8')}",
        f"source_sha256: {_yaml_string(source_sha256)}",
        f"source_bytes: {source_bytes}",
        f"source_line_count: {source_line_count}",
        f"source_page_marker_count: {page_marker_count}",
        f"source_pilcrow_count: {pilcrow_count}",
        f"kanripo_title: {_yaml_string(title)}",
        f"kanripo_id: {_yaml_string(_summary_property(properties, 'ID'))}",
        f"kanripo_baseedition: {_yaml_string(_summary_property(properties, 'BASEEDITION'))}",
        f"kanripo_witness: {_yaml_string(_summary_property(properties, 'WITNESS'))}",
        "kanripo_juans:",
    ]
    _append_yaml_list(lines, [value.strip() for value in properties.get("JUAN", ())], "  ")
    lines.append("kanripo_files:")
    _append_yaml_list(lines, [value.strip() for value in properties.get("FILE", ())], "  ")
    lines.append("kanripo_keywords:")
    _append_yaml_mapping(lines, keywords, "  ")
    lines.append("kanripo_properties:")
    _append_yaml_mapping(lines, properties, "  ")
    lines.append("kanripo_headers:")
    _append_yaml_list(lines, headers, "  ")
    lines.extend(
        [
            "text_policy:",
            f"  character_normalization: {_yaml_string('none')}",
            f"  punctuation_normalization: {_yaml_string('none')}",
            f"  entity_references: {_yaml_string('preserved literally')}",
            f"  page_markers: {_yaml_string('Markdown comments with source line numbers')}",
            f"  pilcrow: {_yaml_string('removed as Kanripo physical-line terminator')}",
            "---",
        ]
    )
    return "\n".join(lines)


def normalize_text(
    source_text: str,
    *,
    source_path: str,
    source_sha256: str | None = None,
    source_bytes: int | None = None,
) -> str:
    """Return normalized Markdown for decoded Kanripo text.

    The function accepts decoded text to make fixture tests and callers that
    already own the bytes straightforward.  ``normalize_file`` should be used
    for normal operation because it computes the digest from the original
    bytes before decoding.
    """

    lines = source_text.splitlines(keepends=True)
    if source_text and not lines:
        lines = [source_text]

    if source_sha256 is None:
        source_sha256 = hashlib.sha256(source_text.encode("utf-8")).hexdigest()
    if source_bytes is None:
        source_bytes = len(source_text.encode("utf-8"))

    headers: list[str] = []
    keywords: OrderedDict[str, list[str]] = OrderedDict()
    properties: OrderedDict[str, list[str]] = OrderedDict()
    body_lines: list[str] = []
    seen_source_body = False
    page_marker_count = 0
    pilcrow_count = source_text.count(PILCROW)

    for source_line_number, raw_line in enumerate(lines, start=1):
        line = _without_line_ending(raw_line)
        metadata = _parse_metadata_line(line)

        if metadata is not None:
            kind, key, value = metadata
            headers.append(line)
            if kind == "keyword":
                keywords.setdefault(key, []).append(value)
            elif kind == "property":
                properties.setdefault(key, []).append(value)

            if seen_source_body:
                # Repeated FILE/JUAN declarations occur inside Shishuo TXT
                # files.  Keep them at their original location as comments.
                body_lines.append(
                    f"<!-- kanripo-directive source-line={source_line_number}: {line} -->\n"
                )
            continue

        if not seen_source_body and (
            PAGE_MARKER_RE.search(line) or PILCROW in line or line.strip()
        ):
            seen_source_body = True

        page_markers = PAGE_MARKER_RE.findall(line)
        page_marker_count += len(page_markers)

        def page_comment(match: re.Match[str]) -> str:
            return (
                f"<!-- kanripo-page source-line={source_line_number}: "
                f"{match.group(0)} -->"
            )

        normalized_line = PAGE_MARKER_RE.sub(page_comment, line)
        # In the observed repositories ¶ is a line terminator, not text.  Only
        # remove it at the end of a physical line; an unexpected interior ¶ is
        # left visible rather than silently treated as content.
        if normalized_line.endswith(PILCROW):
            normalized_line = normalized_line[:-1]
        body_lines.append(normalized_line + "\n")

    metadata = _frontmatter(
        source_path=source_path,
        source_bytes=source_bytes,
        source_line_count=len(lines),
        source_sha256=source_sha256,
        page_marker_count=page_marker_count,
        pilcrow_count=pilcrow_count,
        headers=headers,
        keywords=keywords,
        properties=properties,
    )
    return metadata + "\n\n" + "".join(body_lines)


def normalize_file(
    source_path: Path | str,
    output_path: Path | str,
    *,
    source_root: Path | str | None = None,
) -> Path:
    """Normalize one UTF-8 source file and write one UTF-8 Markdown file."""

    source = Path(source_path)
    output = Path(output_path)
    if source_root is not None:
        _assert_output_is_not_source_tree(Path(source_root), output)
    raw_bytes = source.read_bytes()
    raw_text = raw_bytes.decode("utf-8")
    markdown = normalize_text(
        raw_text,
        source_path=_display_path(source),
        source_sha256=hashlib.sha256(raw_bytes).hexdigest(),
        source_bytes=len(raw_bytes),
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    # Explicit newline handling makes generated files stable on every host.
    with output.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(markdown)
    return output


def _assert_output_is_not_source_tree(source_root: Path, output_root: Path) -> None:
    source_resolved = source_root.resolve()
    output_resolved = output_root.resolve()
    try:
        output_resolved.relative_to(source_resolved)
    except ValueError:
        return
    raise ValueError(
        f"refusing to write output inside immutable source tree: "
        f"{output_resolved} is under {source_resolved}"
    )


def discover_sources(source_root: Path | str, book: str = "all") -> list[Path]:
    """Discover repository TXT sources in stable lexical order."""

    root = Path(source_root)
    books = BOOKS if book == "all" else (book,)
    paths: list[Path] = []
    for collection in books:
        collection_root = root / collection
        paths.extend(path for path in collection_root.glob("*.txt") if path.is_file())
    return sorted(paths, key=lambda path: path.as_posix())


def discover_configured_sources(
    config_path: Path | str, book: str = "all"
) -> list[Path]:
    """Discover primary source files through ``config/sources.yaml``.

    The default command still resolves to the historical ``shishuoSources``
    layout.  This opt-in/configured path lets future processing use the
    registry architecture without changing any existing provenance strings.
    """

    path = Path(config_path)
    config = load_sources_config(path)
    configured_sources = config["sources"]
    books = BOOKS if book == "all" else (book,)
    paths: list[Path] = []
    config_root = repository_root_for_config(path)
    for collection in books:
        work_config = configured_sources.get(collection)
        if not isinstance(work_config, Mapping):
            raise ValueError(f"source configuration has no entry for {collection}")
        primary = work_config.get("primary")
        if not primary:
            raise ValueError(f"source configuration has no primary path for {collection}")
        primary_root = Path(str(primary))
        if not primary_root.is_absolute():
            primary_root = config_root / primary_root
        paths.extend(
            candidate for candidate in primary_root.glob("*.txt") if candidate.is_file()
        )
    return sorted(paths, key=lambda candidate: candidate.as_posix())


def _expand_explicit_sources(sources: Iterable[Path | str]) -> list[Path]:
    paths: list[Path] = []
    for source in sources:
        path = Path(source)
        if path.is_dir():
            paths.extend(candidate for candidate in path.glob("*.txt") if candidate.is_file())
        elif path.is_file():
            if path.suffix.lower() != ".txt":
                raise ValueError(f"source is not a TXT file: {path}")
            paths.append(path)
        else:
            raise FileNotFoundError(path)

    unique: dict[Path, Path] = {}
    for path in paths:
        unique[path.resolve()] = path
    return sorted(unique.values(), key=lambda path: path.as_posix())


def _output_path(source: Path, source_root: Path, output_root: Path) -> Path:
    try:
        relative = source.resolve().relative_to(source_root.resolve())
    except ValueError:
        relative = Path(source.name)
    return output_root / relative.with_suffix(".md")


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "sources",
        nargs="*",
        help="TXT files or directories; defaults to both Kanripo collections",
    )
    parser.add_argument(
        "--source-root",
        type=Path,
        default=None,
        help="root containing shishuo/ and jinshu/; overrides --config",
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=DEFAULT_CONFIG_PATH,
        help="source registry configuration (default: config/sources.yaml)",
    )
    parser.add_argument(
        "--output-root",
        type=Path,
        default=DEFAULT_OUTPUT_ROOT,
        help="Markdown output root (default: content/processed)",
    )
    parser.add_argument(
        "--book",
        choices=("all",) + BOOKS,
        default="all",
        help="collection to process when no explicit source paths are given",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_argument_parser()
    args = parser.parse_args(argv)
    source_root = args.source_root or DEFAULT_SOURCE_ROOT
    output_root = args.output_root

    try:
        _assert_output_is_not_source_tree(source_root, output_root)
        if args.sources:
            sources = _expand_explicit_sources(args.sources)
        elif args.source_root is not None:
            sources = discover_sources(source_root, args.book)
        else:
            sources = discover_configured_sources(args.config, args.book)
        if not sources:
            raise FileNotFoundError(
                f"no TXT sources found below {source_root} for book={args.book}"
            )
        for source in sources:
            output = _output_path(source, source_root, output_root)
            normalize_file(source, output, source_root=source_root)
            print(f"{_display_path(source)} -> {_display_path(output)}")
    except (FileNotFoundError, OSError, UnicodeDecodeError, ValueError) as error:
        parser.error(str(error))
    return 0


if __name__ == "__main__":
    sys.exit(main())
