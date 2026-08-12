#!/usr/bin/env python3
"""Look up Shishuo scholarly references through an on-demand Codex search.

This is intentionally an online lookup tool, not a CText downloader.  It
passes a focused prompt to ``codex exec --search`` and stores only the
resulting Markdown report when caching is enabled.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
from typing import Any, Iterable, Mapping, Sequence
from urllib.parse import urlparse


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
INDEX_PATH = REPOSITORY_ROOT / "data/shishuo-corpus-index.json"
CACHE_ROOT = REPOSITORY_ROOT / ".cache/shishuo-reference"
SCHOLARLY_URL = "https://ctext.org/wiki.pl?if=gb&res=40889"
SCHOLARLY_TITLE = "余嘉錫《世說新語箋疏》"
CODEX_COMMAND = ("codex", "exec", "--search", "--ephemeral", "--sandbox", "read-only")
DEFAULT_TIMEOUT = 120.0


@dataclass(frozen=True)
class LocalContext:
    query: str
    entry_id: str | None
    status: str
    text: str
    source_urls: tuple[str, ...]


@dataclass(frozen=True)
class SearchResult:
    status: str
    stdout: str
    stderr: str
    returncode: int


def _timestamp() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _cache_filename(query: str, entry_id: str | None) -> str:
    slug_source = query if not entry_id else f"{query}-{entry_id}"
    slug = re.sub(r"[^a-z0-9]+", "-", slug_source.lower()).strip("-")
    if not slug:
        slug = "query"
    digest = hashlib.sha256(
        (query + "\0" + (entry_id or "")).encode("utf-8")
    ).hexdigest()[:12]
    return f"{slug[:72]}-{digest}.md"


def cache_path(query: str, entry_id: str | None = None) -> Path:
    return CACHE_ROOT / _cache_filename(query, entry_id)


def _load_json(path: Path) -> Mapping[str, Any] | None:
    if not path.exists():
        return None
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, Mapping):
        return None
    return value


def _root_frontmatter_fields(text: str) -> dict[str, str]:
    """Read simple root fields from the repository's provenance front matter."""

    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}
    try:
        closing = next(index for index in range(1, len(lines)) if lines[index].strip() == "---")
    except StopIteration:
        return {}
    fields: dict[str, str] = {}
    for line in lines[1:closing]:
        if not line or line[0].isspace() or ":" not in line:
            continue
        key, value = line.split(":", 1)
        fields[key.strip()] = value.strip().strip('"')
    return fields


def _exact_source_section(text: str) -> str:
    marker = "## Original source (exact)\n\n"
    if marker not in text:
        return ""
    start = text.index(marker) + len(marker)
    end = text.find("\n## Main text\n\n", start)
    if end < 0:
        return text[start:]
    source = text[start:end]
    # The renderer adds one Markdown separator newline for source spans that
    # do not end with one.  Keep source text exactly, without that separator.
    if source.endswith("\n"):
        source = source[:-1]
    return source


def _chapter_body(text: str) -> str:
    lines = text.splitlines(keepends=True)
    if not lines or lines[0].strip() != "---":
        return text
    try:
        closing = next(index for index in range(1, len(lines)) if lines[index].strip() == "---")
    except StopIteration:
        return text
    body_start = closing + 1
    if body_start < len(lines) and lines[body_start].strip() == "":
        body_start += 1
    return "".join(lines[body_start:])


def _entry_context(entry_id: str, record: Mapping[str, Any], root: Path) -> str:
    path = root / str(record.get("path", ""))
    lines = [f"entry_id: {entry_id}"]
    if path.is_file():
        text = path.read_text(encoding="utf-8")
        fields = _root_frontmatter_fields(text)
        for field in ("chapter_heading", "opening_text", "source_chapter", "source_path"):
            value = fields.get(field, str(record.get(field, "")))
            lines.append(f"{field}: {value}")
        for field in (
            "source_normalized_filename",
            "FILE",
            "source_body_offset_start",
            "source_body_offset_end_exclusive",
        ):
            if field in fields:
                lines.append(f"{field}: {fields[field]}")
        source = _exact_source_section(text)
        try:
            start = int(fields["source_body_offset_start"])
            end = int(fields["source_body_offset_end_exclusive"])
            chapter_path = root / fields["source_chapter"]
            if chapter_path.is_file():
                source = _chapter_body(chapter_path.read_text(encoding="utf-8"))[start:end]
        except (KeyError, ValueError, OSError):
            pass
        lines.extend(["", "exact_local_source:", source])
    else:
        for field in ("chapter_heading", "opening_text", "source_chapter", "source_path"):
            lines.append(f"{field}: {record.get(field, '')}")
        lines.append("local_entry_file: unavailable")
    return "\n".join(lines)


def load_local_context(
    query: str,
    entry_id: str | None = None,
    *,
    root: Path = REPOSITORY_ROOT,
) -> LocalContext:
    """Load only local structural/source metadata; never infer entities."""

    index = _load_json(root / "data/shishuo-corpus-index.json")
    if index is None or not isinstance(index.get("entries"), list):
        return LocalContext(
            query=query,
            entry_id=entry_id,
            status="index_unavailable",
            text="No local Shishuo corpus index is available.",
            source_urls=(),
        )

    entries = [item for item in index["entries"] if isinstance(item, Mapping)]
    if entry_id:
        match = next((item for item in entries if item.get("id") == entry_id), None)
        if match is None:
            return LocalContext(
                query=query,
                entry_id=entry_id,
                status="entry_not_found",
                text=f"No local entry with id {entry_id!r} was found.",
                source_urls=(),
            )
        return LocalContext(
            query=query,
            entry_id=entry_id,
            status="entry_loaded",
            text=_entry_context(entry_id, match, root),
            source_urls=(str(match.get("path", "")),),
        )

    matches = [
        item
        for item in entries
        if query in str(item.get("opening_text", ""))
    ][:8]
    if not matches:
        return LocalContext(
            query=query,
            entry_id=None,
            status="no_local_entry_match",
            text="No exact local entry-opening match was found; no local text was inferred.",
            source_urls=(),
        )
    lines = ["Exact local entry-opening matches:"]
    for item in matches:
        lines.append(
            f"- {item.get('id')}: {item.get('opening_text')} "
            f"({item.get('path')})"
        )
    return LocalContext(
        query=query,
        entry_id=None,
        status="opening_matches",
        text="\n".join(lines),
        source_urls=tuple(str(item.get("path", "")) for item in matches),
    )


def build_search_prompt(query: str, local: LocalContext) -> str:
    """Build a bounded prompt that forbids source replacement and scraping."""

    return f"""You are performing a focused scholarly-reference lookup for Shishuo Xinyu.
Use live web search in this invocation. Do not use a local model or cached web
content as a substitute for live search.

Query: {query}

Primary scholarly target:
- {SCHOLARLY_TITLE}
- {SCHOLARLY_URL}

Search specifically with combinations such as:
- \"{query}\" \"世說新語箋疏\"
- site:ctext.org \"{query}\" \"世說新語箋疏\"
- \"{query}\" \"余嘉錫\"

When useful, consult official-history evidence in 晉書, 三國志, or 裴松之注,
and cite the exact source URL. Do not scrape CText HTML programmatically,
bypass CText authentication, download the complete 箋疏, or treat search
snippets as authoritative primary text. Distinguish the local Kanripo witness
from scholarly reference, official history, and your own web-search inference.

Return Markdown using exactly these headings, in this order:
## person_entity_resolution
## scholarly_reference
## official_history
## web_search_inference
## source_urls
## confidence
## unresolved_ambiguity

Keep wording cautious. If evidence is unavailable, say so explicitly. Do not
modify or propose edits to the local Shishuo text.

Local source context (read-only, may be unavailable):
local_context_status: {local.status}
{local.text}
"""


def run_codex_search(
    prompt: str,
    *,
    timeout: float = DEFAULT_TIMEOUT,
    runner: Any = subprocess.run,
) -> SearchResult:
    """Run the exact non-interactive Codex live-search command."""

    if shutil.which("codex") is None:
        return SearchResult("codex_unavailable", "", "codex executable was not found", 127)
    try:
        completed = runner(
            list(CODEX_COMMAND) + [prompt],
            cwd=REPOSITORY_ROOT,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except FileNotFoundError:
        return SearchResult("codex_unavailable", "", "codex executable was not found", 127)
    except subprocess.TimeoutExpired as error:
        return SearchResult("web_search_failed", "", f"Codex search timed out: {error}", 124)
    except OSError as error:
        return SearchResult("web_search_failed", "", f"Could not run Codex: {error}", 1)
    stdout = completed.stdout or ""
    stderr = completed.stderr or ""
    if completed.returncode != 0:
        return SearchResult("web_search_failed", stdout, stderr, completed.returncode)
    if not stdout.strip():
        return SearchResult("web_search_failed", stdout, stderr or "Codex returned no report", 1)
    return SearchResult("ok", stdout, stderr, completed.returncode)


SECTION_NAMES = (
    "person_entity_resolution",
    "scholarly_reference",
    "official_history",
    "web_search_inference",
    "source_urls",
    "confidence",
    "unresolved_ambiguity",
)
SECTION_RE = re.compile(r"^#{1,6}\s+(?P<name>[a-z_]+)\s*$", re.IGNORECASE)


def _split_codex_sections(markdown: str) -> dict[str, str]:
    sections: dict[str, list[str]] = {}
    current: str | None = None
    for line in markdown.splitlines():
        match = SECTION_RE.match(line.strip())
        if match and match.group("name").lower() in SECTION_NAMES:
            current = match.group("name").lower()
            sections.setdefault(current, [])
            continue
        if current is not None:
            sections[current].append(line)
    return {name: "\n".join(lines).strip() for name, lines in sections.items()}


def _urls_from_text(text: str) -> list[str]:
    urls: list[str] = []
    for token in re.findall(r"https?://[^\s)<>]+", text):
        url = token.rstrip(".,;\"")
        if url not in urls and urlparse(url).scheme in {"http", "https"}:
            urls.append(url)
    return urls


def render_report(
    query: str,
    entry_id: str | None,
    local: LocalContext,
    result: SearchResult,
    *,
    cache_file: Path | None,
) -> str:
    sections = _split_codex_sections(result.stdout)
    primary_urls = [SCHOLARLY_URL]
    primary_urls.extend(_urls_from_text(result.stdout))
    source_urls = []
    for url in primary_urls:
        if url not in source_urls:
            source_urls.append(url)

    if cache_file is None:
        displayed_cache_path = None
    else:
        try:
            displayed_cache_path = str(cache_file.relative_to(REPOSITORY_ROOT))
        except ValueError:
            displayed_cache_path = str(cache_file)
    lines = [
        "---",
        "schema: 1",
        "stage: online-scholarly-reference-lookup",
        f"query: {json.dumps(query, ensure_ascii=False)}",
        f"entry_id: {json.dumps(entry_id, ensure_ascii=False)}",
        f"status: {json.dumps(result.status)}",
        f"generated_at: {json.dumps(_timestamp())}",
        f"cache_path: {json.dumps(displayed_cache_path, ensure_ascii=False)}",
        "local_corpus_modified: false",
        "ctext_complete_download: false",
        "---",
        "",
        "# Shishuo scholarly-reference lookup",
        "",
        f"Query: `{query}`",
        "",
        "## local_source",
        "",
        "This section contains only local Shishuo provenance and exact source context. It is not an entity resolution.",
        "",
        local.text,
        "",
        "## person_entity_resolution",
        "",
        sections.get("person_entity_resolution") or "No separately labeled resolution was returned.",
        "",
        "## scholarly_reference",
        "",
        sections.get("scholarly_reference") or "No separately labeled 箋疏 finding was returned.",
        "",
        "## official_history",
        "",
        sections.get("official_history") or "No separately labeled official-history finding was returned.",
        "",
        "## web_search_inference",
        "",
        sections.get("web_search_inference") or result.stdout.strip() or "No web-search inference was returned.",
        "",
        "## source_urls",
        "",
    ]
    lines.extend(f"- {url}" for url in source_urls)
    lines.extend(
        [
            "",
            "## confidence",
            "",
            sections.get("confidence") or "Not separately stated by Codex.",
            "",
            "## unresolved_ambiguity",
            "",
            sections.get("unresolved_ambiguity") or "Not separately stated by Codex.",
            "",
            "## lookup_metadata",
            "",
            f"- Codex command: `{' '.join(CODEX_COMMAND)}`",
            f"- Local context status: `{local.status}`",
            "- Primary text and canonical corpus were not modified.",
            "- CText HTML was not scraped and the complete 箋疏 was not downloaded.",
        ]
    )
    if result.stderr.strip():
        lines.extend(["", "## codex_stderr", "", "```text", result.stderr.rstrip(), "```"])
    return "\n".join(lines) + "\n"


def _failure_report(
    query: str,
    entry_id: str | None,
    local: LocalContext,
    result: SearchResult,
) -> str:
    return render_report(query, entry_id, local, result, cache_file=None)


def lookup(
    query: str,
    entry_id: str | None = None,
    *,
    refresh: bool = False,
    no_cache: bool = False,
    timeout: float = DEFAULT_TIMEOUT,
    root: Path = REPOSITORY_ROOT,
    runner: Any = subprocess.run,
) -> tuple[str, Path | None, bool]:
    """Return ``(report, cache_path, from_cache)`` for one lookup."""

    local = load_local_context(query, entry_id, root=root)
    target_cache = root / ".cache/shishuo-reference" / _cache_filename(query, entry_id)
    if not refresh and not no_cache and target_cache.is_file():
        return target_cache.read_text(encoding="utf-8"), target_cache, True

    result = run_codex_search(
        build_search_prompt(query, local), timeout=timeout, runner=runner
    )
    report = render_report(
        query,
        entry_id,
        local,
        result,
        cache_file=None if no_cache or result.status != "ok" else target_cache,
    )
    if result.status != "ok":
        return report, None, False
    if not no_cache:
        target_cache.parent.mkdir(parents=True, exist_ok=True)
        target_cache.write_text(report, encoding="utf-8", newline="\n")
    return report, (None if no_cache else target_cache), False


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("query", help="person, phrase, or other focused Shishuo query")
    parser.add_argument("--entry", help="optional canonical Shishuo entry id")
    parser.add_argument("--refresh", action="store_true", help="ignore an existing cache report")
    parser.add_argument("--no-cache", action="store_true", help="do not read or write a cache report")
    parser.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT, help="Codex subprocess timeout in seconds")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_argument_parser().parse_args(argv)
    report, _cache_file, from_cache = lookup(
        args.query,
        args.entry,
        refresh=args.refresh,
        no_cache=args.no_cache,
        timeout=args.timeout,
    )
    print(report, end="")
    if from_cache:
        return 0
    status_match = re.search(r"^status: \"?([^\"\n]+)", report, re.MULTILINE)
    return 0 if status_match and status_match.group(1) == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
