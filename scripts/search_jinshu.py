#!/usr/bin/env python3
"""Search materialized Jinshu structural units locally.

This command reads ``data/jinshu-unit-index.json`` and the generated unit
files only.  It never uses the network or a secondary Jinshu witness.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Mapping, Sequence


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INDEX = REPOSITORY_ROOT / "data/jinshu-unit-index.json"
SOURCE_MARKER = "## Original source (exact)\n\n"


def load_index(path: Path = DEFAULT_INDEX) -> Mapping[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, Mapping) or not isinstance(value.get("units"), list):
        raise ValueError(f"invalid Jinshu unit index: {path}")
    return value


def extract_source_text(markdown: str) -> str:
    if SOURCE_MARKER not in markdown:
        raise ValueError("generated Jinshu unit has no exact-source section")
    return markdown.split(SOURCE_MARKER, 1)[1]


def make_snippet(text: str, start: int, context: int) -> str:
    left = max(0, start - context)
    right = min(len(text), start + context)
    return text[left:right]


def search_records(
    query: str,
    *,
    index_path: Path = DEFAULT_INDEX,
    category: str | None = None,
    context: int = 100,
    root: Path = REPOSITORY_ROOT,
    limit: int | None = None,
) -> list[dict[str, Any]]:
    index = load_index(index_path)
    results: list[dict[str, Any]] = []
    for record in index["units"]:
        if not isinstance(record, Mapping):
            continue
        if category and record.get("category") != category:
            continue
        path = Path(str(record.get("file_path", "")))
        if not path.is_absolute():
            path = root / path
        if not path.is_file():
            continue
        text = extract_source_text(path.read_text(encoding="utf-8"))
        cursor = 0
        while True:
            position = text.find(query, cursor)
            if position < 0:
                break
            results.append(
                {
                    "unit_id": record.get("unit_id"),
                    "volume": record.get("volume"),
                    "category": record.get("category"),
                    "title": record.get("title"),
                    "file_path": record.get("file_path"),
                    "snippet": make_snippet(text, position, context),
                    "match_offset": position,
                }
            )
            cursor = position + max(1, len(query))
            if limit is not None and len(results) >= limit:
                return results
    return results


def render_results(query: str, results: Sequence[Mapping[str, Any]]) -> str:
    lines = [f"Query: {query}", f"Matches: {len(results)}", ""]
    if not results:
        lines.append("No local Jinshu unit matched the query.")
        return "\n".join(lines) + "\n"
    for number, result in enumerate(results, start=1):
        lines.extend(
            [
                f"## {number}. {result.get('unit_id')}",
                "",
                f"- volume: {result.get('volume')}",
                f"- category: {result.get('category')}",
                f"- title: {result.get('title')}",
                f"- local file: {result.get('file_path')}",
                f"- match offset: {result.get('match_offset')}",
                "",
                "```text",
                str(result.get("snippet", "")),
                "```",
                "",
            ]
        )
    return "\n".join(lines)


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("query", help="exact Chinese text to search")
    parser.add_argument("--context", type=int, default=100, help="characters before and after each match")
    parser.add_argument("--category", help="filter by category, such as liezhuan or zhi")
    parser.add_argument("--limit", type=int, help="maximum number of matching occurrences")
    parser.add_argument("--index", type=Path, default=DEFAULT_INDEX)
    parser.add_argument("--root", type=Path, default=REPOSITORY_ROOT)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_argument_parser().parse_args(argv)
    if args.context < 0:
        raise SystemExit("--context must be non-negative")
    if args.limit is not None and args.limit < 1:
        raise SystemExit("--limit must be positive")
    try:
        results = search_records(
            args.query,
            index_path=args.index,
            category=args.category,
            context=args.context,
            root=args.root,
            limit=args.limit,
        )
    except (OSError, ValueError, json.JSONDecodeError) as error:
        print(str(error))
        return 1
    print(render_results(args.query, results), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
