#!/usr/bin/env python3
"""Discover and safely download the registered secondary witnesses.

Internet Archive and Wikisource metadata APIs are used for discovery.  The
script does not scrape Chinese Text Project or Wikisource HTML and does not
parse or replace any diplomatic source text.  Downloaded OCR is recorded as
a non-authoritative derivative.

Examples::

    python scripts/download_witnesses.py --list
    python scripts/download_witnesses.py --shishuo-wikisource
    python scripts/download_witnesses.py --shishuo-ling
    python scripts/download_witnesses.py --shishuo-ling-volume 3
    python scripts/download_witnesses.py --shishuo
    python scripts/download_witnesses.py --jinshu-jiaozhu
    python scripts/download_witnesses.py --sanguozhi-song
    python scripts/download_witnesses.py --all
    python scripts/download_witnesses.py --verify

The normal test suite calls the parsing and selection functions with fixture
metadata.  Network access is confined to the command-line discovery and
download operations.
"""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time
from typing import Any, Callable, Iterable, Mapping, Sequence
from unicodedata import normalize as unicode_normalize
from urllib.error import HTTPError
from urllib.parse import quote, unquote, urlencode, urlparse
from urllib.request import Request, urlopen


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = Path("config/sources.yaml")
IA_METADATA_TEMPLATE = "https://archive.org/metadata/{identifier}"
IA_DOWNLOAD_TEMPLATE = "https://archive.org/download/{identifier}/{filename}"
IA_ADVANCEDSEARCH_ENDPOINT = "https://archive.org/advancedsearch.php"
WIKISOURCE_API_ENDPOINT = "https://zh.wikisource.org/w/api.php"
WIKISOURCE_SOURCE_RECORD = "https://zh.wikisource.org/wiki/世説新語_(四部叢刊本)"
WIKISOURCE_BASE_TITLE = "世説新語 (四部叢刊本)"
WIKISOURCE_PAGE_TITLES = (
    "序",
    "目録",
    "卷上之上",
    "卷上之下",
    "卷中之上",
    "卷中之下",
    "卷下之上",
    "卷下之下",
    "校語一卷",
)
SHISHUO_WIKISOURCE_WITNESS_ID = "shishuo-wikisource-sbck"
SHISHUO_LING_WITNESS_ID = "shishuo-ling-1615"
SHISHUO_LING_SEARCH_QUERY = 'title:"Shi shuo xin yu" AND year:1615'
SHISHUO_LING_VOLUMES = (1, 2, 3)
WIKISOURCE_PAGE_BATCH_SIZE = 25
WIKISOURCE_RETRY_LIMIT = 4
WIKISOURCE_RETRY_DELAY = 10
JINSHU_FIRST_IDENTIFIER = 18
JINSHU_LAST_IDENTIFIER = 75
JINSHU_WITNESS_ID = "jinshu-jiaozhu"
SANGUOZHI_WITNESS_ID = "sanguozhi-song-shoryobu"
SANGUOZHI_ARCHIVE_ITEM = "songkeben"
METADATA_WORKERS = 4
DOWNLOAD_WORKERS = 4
SANGUOZHI_TARGET_TITLE = (
    "三国志.六十五卷.晋陈寿撰.刘宋.裴松之注.日本宫内厅书陵部藏.有补抄.南宋刊本"
)
REQUIRED_REGISTRY_FIELDS = {
    "id",
    "work",
    "role",
    "edition",
    "source_provider",
    "source_type",
    "script",
    "annotations",
    "local",
    "local_path",
    "remote_record",
    "text_authority",
    "structure_authority",
    "notes",
}


class WitnessDownloadError(RuntimeError):
    """Raised when a witness cannot be safely discovered or selected."""


class AmbiguousFileError(WitnessDownloadError):
    """Raised when metadata does not identify one deterministic file."""


class NonMatchingItemError(WitnessDownloadError):
    """Raised when an Internet Archive item is not the requested witness."""


@dataclass(frozen=True)
class IAFile:
    """The metadata needed to identify one Internet Archive file."""

    name: str
    size: int | None
    file_format: str
    source: str
    raw: Mapping[str, Any]


@dataclass(frozen=True)
class IAMetadata:
    identifier: str
    title: str
    metadata: Mapping[str, Any]
    files: tuple[IAFile, ...]
    raw: Mapping[str, Any]


@dataclass(frozen=True)
class WikisourceRevision:
    """One wikitext revision returned by the Wikisource API."""

    page_title: str
    source_url: str
    api_url: str
    page_id: int | None
    revision_id: int | None
    parent_revision_id: int | None
    timestamp: str
    content: str


@dataclass(frozen=True)
class WikisourcePageRange:
    """One <pages> range declared by a Wikisource section page."""

    section_title: str
    first_page: int
    last_page: int
    index_title: str


def _timestamp() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _as_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _decoded_name(value: str) -> str:
    return unquote(value)


def parse_ia_metadata(
    payload: Mapping[str, Any], identifier: str | None = None
) -> IAMetadata:
    """Parse one IA metadata JSON payload without selecting a file."""

    if not isinstance(payload, Mapping):
        raise WitnessDownloadError("Internet Archive metadata is not an object")
    metadata = payload.get("metadata")
    if not isinstance(metadata, Mapping):
        raise WitnessDownloadError("Internet Archive metadata has no metadata object")
    raw_files = payload.get("files")
    if not isinstance(raw_files, list):
        raise WitnessDownloadError("Internet Archive metadata has no file list")
    resolved_identifier = str(identifier or metadata.get("identifier") or "")
    if not resolved_identifier:
        raise WitnessDownloadError("Internet Archive metadata has no identifier")

    files: list[IAFile] = []
    for raw_file in raw_files:
        if not isinstance(raw_file, Mapping) or not raw_file.get("name"):
            continue
        files.append(
            IAFile(
                name=str(raw_file["name"]),
                size=_as_int(raw_file.get("size")),
                file_format=str(raw_file.get("format") or ""),
                source=str(raw_file.get("source") or ""),
                raw=raw_file,
            )
        )
    title = str(metadata.get("title") or "")
    return IAMetadata(
        identifier=resolved_identifier,
        title=title,
        metadata=metadata,
        files=tuple(files),
        raw=payload,
    )


def fetch_ia_metadata(
    identifier: str,
    *,
    timeout: float = 60.0,
    opener: Callable[..., Any] = urlopen,
) -> IAMetadata:
    """Fetch and parse the IA metadata endpoint for one identifier."""

    url = IA_METADATA_TEMPLATE.format(identifier=quote(identifier, safe=""))
    request = Request(
        url,
        headers={
            "Accept": "application/json",
            "User-Agent": "shishuoSketch-source-infrastructure/1.0",
        },
    )
    try:
        response = opener(request, timeout=timeout)
    except TypeError:
        # Small fixture openers often expose only opener(request).
        response = opener(request)
    with response:
        payload = json.load(response)
    return parse_ia_metadata(payload, identifier=identifier)


def wikisource_api_url(
    title: str,
    *,
    endpoint: str = WIKISOURCE_API_ENDPOINT,
) -> str:
    """Build the MediaWiki API URL for one raw wikitext revision."""

    query = urlencode(
        {
            "action": "query",
            "format": "json",
            "formatversion": "2",
            "redirects": "1",
            "prop": "revisions",
            "rvprop": "ids|timestamp|content",
            "rvslots": "main",
            "titles": title,
        }
    )
    return f"{endpoint}?{query}"


def wikisource_page_url(title: str) -> str:
    return "https://zh.wikisource.org/wiki/" + quote(title, safe="()")


def _fetch_wikisource_json(
    api_url: str,
    *,
    timeout: float,
    opener: Callable[..., Any],
) -> Mapping[str, Any]:
    """Fetch one API response with bounded handling for Wikimedia 429s."""

    for attempt in range(WIKISOURCE_RETRY_LIMIT + 1):
        request = Request(
            api_url,
            headers={
                "Accept": "application/json",
                "User-Agent": "shishuoSketch-source-infrastructure/1.0",
            },
        )
        try:
            try:
                response = opener(request, timeout=timeout)
            except TypeError:
                response = opener(request)
            with response:
                payload = json.load(response)
            if not isinstance(payload, Mapping):
                raise WitnessDownloadError("Wikisource API response is not an object")
            return payload
        except HTTPError as error:
            if error.code != 429 or attempt >= WIKISOURCE_RETRY_LIMIT:
                raise
            retry_after = None
            if error.headers is not None:
                retry_after = error.headers.get("Retry-After")
            try:
                delay = int(retry_after) if retry_after else WIKISOURCE_RETRY_DELAY * (attempt + 1)
            except (TypeError, ValueError):
                delay = WIKISOURCE_RETRY_DELAY * (attempt + 1)
            time.sleep(min(max(delay, 1), 60))
    raise WitnessDownloadError("unreachable Wikisource API retry state")


def _wikisource_page_objects(payload: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    if not isinstance(payload, Mapping):
        raise WitnessDownloadError("Wikisource API response is not an object")
    query = payload.get("query")
    if not isinstance(query, Mapping):
        raise WitnessDownloadError("Wikisource API response has no query object")
    raw_pages = query.get("pages")
    if isinstance(raw_pages, list):
        return [page for page in raw_pages if isinstance(page, Mapping)]
    if isinstance(raw_pages, Mapping):
        return [page for page in raw_pages.values() if isinstance(page, Mapping)]
    raise WitnessDownloadError("Wikisource API response has no page list")


def _parse_wikisource_page(
    page: Mapping[str, Any],
    *,
    title: str,
    api_url: str,
) -> WikisourceRevision:
    if page.get("missing") is not None:
        raise WitnessDownloadError(f"Wikisource page is missing: {title}")
    revisions = page.get("revisions")
    if not isinstance(revisions, list) or len(revisions) != 1:
        raise WitnessDownloadError(f"Wikisource page has no unique current revision: {title}")
    revision = revisions[0]
    if not isinstance(revision, Mapping):
        raise WitnessDownloadError(f"Wikisource revision is not an object: {title}")
    slots = revision.get("slots")
    main = slots.get("main") if isinstance(slots, Mapping) else None
    content = main.get("content") if isinstance(main, Mapping) else revision.get("content")
    if not isinstance(content, str):
        raise WitnessDownloadError(f"Wikisource revision has no raw main-slot content: {title}")
    return WikisourceRevision(
        page_title=str(page.get("title") or title),
        source_url=wikisource_page_url(str(page.get("title") or title)),
        api_url=api_url or wikisource_api_url(title),
        page_id=_as_int(page.get("pageid")),
        revision_id=_as_int(revision.get("revid")),
        parent_revision_id=_as_int(revision.get("parentid")),
        timestamp=str(revision.get("timestamp") or ""),
        content=content,
    )


def parse_wikisource_revision(
    payload: Mapping[str, Any],
    *,
    title: str,
    api_url: str | None = None,
) -> WikisourceRevision:
    """Parse one raw Wikisource revision without interpreting its markup."""

    pages = _wikisource_page_objects(payload)
    if len(pages) != 1:
        raise AmbiguousFileError("Wikisource API did not identify exactly one page")
    return _parse_wikisource_page(
        pages[0], title=title, api_url=api_url or wikisource_api_url(title)
    )


def parse_wikisource_revisions(
    payload: Mapping[str, Any],
    *,
    titles: Sequence[str],
    api_url: str,
) -> list[WikisourceRevision]:
    """Parse a multi-title MediaWiki revision response in requested order."""

    pages = _wikisource_page_objects(payload)
    by_title = {str(page.get("title") or ""): page for page in pages}
    revisions: list[WikisourceRevision] = []
    for title in titles:
        page = by_title.get(title)
        if page is None:
            raise WitnessDownloadError(f"Wikisource batch response omitted page: {title}")
        revisions.append(_parse_wikisource_page(page, title=title, api_url=api_url))
    return revisions


def fetch_wikisource_revision(
    title: str,
    *,
    timeout: float = 60.0,
    opener: Callable[..., Any] = urlopen,
) -> WikisourceRevision:
    """Fetch raw wikitext through the Wikisource MediaWiki API."""

    api_url = wikisource_api_url(title)
    payload = _fetch_wikisource_json(api_url, timeout=timeout, opener=opener)
    return parse_wikisource_revision(payload, title=title, api_url=api_url)


def fetch_wikisource_revisions(
    titles: Sequence[str],
    *,
    timeout: float = 60.0,
    opener: Callable[..., Any] = urlopen,
) -> list[WikisourceRevision]:
    """Fetch several raw Wikisource revisions in one MediaWiki API call."""

    if not titles:
        return []
    api_url = wikisource_api_url("|".join(titles))
    payload = _fetch_wikisource_json(api_url, timeout=timeout, opener=opener)
    return parse_wikisource_revisions(payload, titles=titles, api_url=api_url)


def parse_wikisource_page_ranges(
    content: str,
    *,
    section_title: str,
) -> list[WikisourcePageRange]:
    """Read raw <pages> declarations without expanding or editing them."""

    ranges: list[WikisourcePageRange] = []
    for match in re.finditer(r"<pages\b(?P<attributes>[^>]*)/>", content):
        attributes = match.group("attributes")

        def attribute(name: str) -> str | None:
            value = re.search(rf"\b{name}\s*=\s*\"([^\"]+)\"", attributes)
            return value.group(1) if value else None

        first = _as_int(attribute("from"))
        last = _as_int(attribute("to"))
        index_title = attribute("index")
        if first is None or last is None or not index_title or first > last:
            raise WitnessDownloadError(
                f"unusable Wikisource <pages> declaration in {section_title!r}"
            )
        ranges.append(
            WikisourcePageRange(
                section_title=section_title,
                first_page=first,
                last_page=last,
                index_title=index_title,
            )
        )
    if not ranges:
        raise WitnessDownloadError(f"Wikisource section has no <pages> declaration: {section_title}")
    return ranges


def ia_advancedsearch_url(
    query: str = SHISHUO_LING_SEARCH_QUERY,
    *,
    rows: int = 100,
    page: int = 1,
) -> str:
    """Build an Internet Archive advanced-search API URL."""

    params = [
        ("q", query),
        ("fl[]", "identifier"),
        ("fl[]", "title"),
        ("fl[]", "date"),
        ("fl[]", "year"),
        ("fl[]", "call_number"),
        ("fl[]", "volume"),
        ("rows", str(rows)),
        ("page", str(page)),
        ("output", "json"),
    ]
    return f"{IA_ADVANCEDSEARCH_ENDPOINT}?{urlencode(params)}"


def parse_ia_search(payload: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    """Return advanced-search result documents in API order."""

    response = payload.get("response") if isinstance(payload, Mapping) else None
    docs = response.get("docs") if isinstance(response, Mapping) else None
    if not isinstance(docs, list):
        raise WitnessDownloadError("Internet Archive search has no result documents")
    return [doc for doc in docs if isinstance(doc, Mapping)]


def fetch_ia_search(
    query: str = SHISHUO_LING_SEARCH_QUERY,
    *,
    timeout: float = 60.0,
    opener: Callable[..., Any] = urlopen,
) -> Mapping[str, Any]:
    """Fetch IA advanced-search JSON without scraping search-result HTML."""

    api_url = ia_advancedsearch_url(query)
    request = Request(
        api_url,
        headers={
            "Accept": "application/json",
            "User-Agent": "shishuoSketch-source-infrastructure/1.0",
        },
    )
    try:
        response = opener(request, timeout=timeout)
    except TypeError:
        response = opener(request)
    with response:
        payload = json.load(response)
    if not isinstance(payload, Mapping):
        raise WitnessDownloadError("Internet Archive search response is not an object")
    parse_ia_search(payload)
    return payload


def title_contains(item: IAMetadata, required_text: str) -> bool:
    """Return whether the item title contains the required witness marker."""

    return required_text in item.title


def require_title(item: IAMetadata, required_text: str) -> None:
    if not title_contains(item, required_text):
        raise NonMatchingItemError(
            f"{item.identifier}: title {item.title!r} does not contain "
            f"required witness text {required_text!r}"
        )


_CHINESE_DIGITS = {
    "〇": 0,
    "零": 0,
    "一": 1,
    "二": 2,
    "兩": 2,
    "两": 2,
    "三": 3,
    "四": 4,
    "五": 5,
    "六": 6,
    "七": 7,
    "八": 8,
    "九": 9,
}
_CHINESE_UNITS = {"十": 10, "百": 100, "千": 1000, "萬": 10000, "万": 10000}
_NUMERAL_TOKEN = r"[0-9〇零一二兩两三四五六七八九十百千万萬]+"


def _parse_chinese_number(token: str) -> int | None:
    token = token.strip()
    if not token:
        return None
    if token.isdigit():
        return int(token)
    if all(character in _CHINESE_DIGITS for character in token):
        return int("".join(str(_CHINESE_DIGITS[character]) for character in token))

    total = 0
    section = 0
    number = 0
    for character in token:
        if character in _CHINESE_DIGITS:
            number = _CHINESE_DIGITS[character]
            continue
        unit = _CHINESE_UNITS.get(character)
        if unit is None:
            return None
        if unit < 10000:
            section += (number or 1) * unit
        else:
            total += (section + number) * unit
            section = 0
        number = 0
    return total + section + number


def extract_volume_number(text: str) -> int | None:
    """Extract a Chinese or Arabic volume number from IA title metadata.

    The Jinshu series currently uses titles such as ``晉書斠注(十一)``.  The
    additional ``第...卷`` and ``卷...`` forms make the helper useful for
    metadata variants without relying on the numeric IA identifier.
    """

    normalized = unicode_normalize("NFKC", _decoded_name(text))
    patterns = (
        rf"斠注\s*[（(]\s*(?P<number>{_NUMERAL_TOKEN})\s*[）)]",
        rf"第\s*(?P<number>{_NUMERAL_TOKEN})\s*[卷冊册]",
        rf"卷\s*(?P<number>{_NUMERAL_TOKEN})",
    )
    for pattern in patterns:
        match = re.search(pattern, normalized)
        if match:
            value = _parse_chinese_number(match.group("number"))
            if value is not None:
                return value
    return None


def _file_candidates(
    files: Iterable[IAFile],
    *,
    suffix: str,
    excluded_fragments: Sequence[str] = (),
) -> list[IAFile]:
    suffix = suffix.casefold()
    excluded = tuple(fragment.casefold() for fragment in excluded_fragments)
    return [
        item
        for item in files
        if _decoded_name(item.name).casefold().endswith(suffix)
        and not any(fragment in _decoded_name(item.name).casefold() for fragment in excluded)
    ]


def select_deterministic_file(
    files: Iterable[IAFile],
    *,
    suffix: str,
    preferred_suffixes: Sequence[str] = (),
    preferred_names: Sequence[str] = (),
    excluded_fragments: Sequence[str] = (),
) -> IAFile:
    """Select exactly one file, refusing ties rather than guessing."""

    candidates = _file_candidates(
        files, suffix=suffix, excluded_fragments=excluded_fragments
    )
    if not candidates:
        raise WitnessDownloadError(f"no {suffix} file is available in metadata")

    preferred_names_cf = {_decoded_name(name).casefold() for name in preferred_names}
    preferred_suffixes_cf = tuple(value.casefold() for value in preferred_suffixes)

    def score(item: IAFile) -> tuple[int, str]:
        name = _decoded_name(item.name).casefold()
        if name in preferred_names_cf:
            rank = 0
        else:
            rank = next(
                (index + 1 for index, value in enumerate(preferred_suffixes_cf) if name.endswith(value)),
                len(preferred_suffixes_cf) + 1,
            )
        return rank, name

    ranked = sorted(candidates, key=score)
    best_rank = score(ranked[0])[0]
    best = [item for item in ranked if score(item)[0] == best_rank]
    if len(best) != 1:
        names = ", ".join(item.name for item in best)
        raise AmbiguousFileError(f"ambiguous {suffix} file selection: {names}")
    return best[0]


def select_jinshu_files(item: IAMetadata) -> dict[str, IAFile]:
    """Choose the exact PDF and optional OCR derivative for one volume."""

    exact_pdf = f"{item.identifier}.pdf"
    pdf = select_deterministic_file(
        item.files,
        suffix=".pdf",
        preferred_names=(exact_pdf,),
        excluded_fragments=(".jp2.zip",),
    )
    ocr_candidates = _file_candidates(item.files, suffix="_djvu.txt")
    if len(ocr_candidates) > 1:
        raise AmbiguousFileError(
            "ambiguous Jinshu OCR selection: "
            + ", ".join(file.name for file in ocr_candidates)
        )
    selected = {"pdf": pdf}
    if ocr_candidates:
        selected["ocr"] = ocr_candidates[0]
    return selected


def _target_file(item: IAFile) -> bool:
    return SANGUOZHI_TARGET_TITLE in unicode_normalize(
        "NFKC", _decoded_name(item.name)
    )


def select_sanguozhi_files(
    item: IAMetadata, *, include_archival: bool = False
) -> dict[str, IAFile]:
    """Select the target Sanguozhi derivatives from ``songkeben`` metadata."""

    target_files = [file for file in item.files if _target_file(file)]
    if not target_files:
        raise WitnessDownloadError(
            "songkeben metadata has no file matching the registered Sanguozhi title"
        )
    text_pdfs = [
        file
        for file in target_files
        if _decoded_name(file.name).casefold().endswith("_text.pdf")
    ]
    if len(text_pdfs) > 1:
        raise AmbiguousFileError(
            "ambiguous Sanguozhi searchable PDF selection: "
            + ", ".join(file.name for file in text_pdfs)
        )
    if text_pdfs:
        pdf = text_pdfs[0]
    else:
        pdf = select_deterministic_file(
            target_files,
            suffix=".pdf",
            excluded_fragments=("_text.pdf", ".jp2.zip"),
        )

    selected = {"pdf": pdf}
    ocr = [
        file
        for file in target_files
        if _decoded_name(file.name).casefold().endswith("_djvu.txt")
    ]
    if len(ocr) > 1:
        raise AmbiguousFileError(
            "ambiguous Sanguozhi OCR selection: "
            + ", ".join(file.name for file in ocr)
        )
    if ocr:
        selected["ocr"] = ocr[0]

    if include_archival:
        archival = [
            file
            for file in target_files
            if _decoded_name(file.name).casefold().endswith("_jp2.zip")
        ]
        if len(archival) > 1:
            raise AmbiguousFileError(
                "ambiguous Sanguozhi archival selection: "
                + ", ".join(file.name for file in archival)
            )
        if archival:
            selected["archival"] = archival[0]
    return selected


def _optional_file(
    files: Iterable[IAFile],
    *,
    suffix: str,
    preferred_name: str,
    label: str,
) -> IAFile | None:
    candidates = _file_candidates(files, suffix=suffix)
    if not candidates:
        return None
    preferred = [item for item in candidates if _decoded_name(item.name) == preferred_name]
    if len(preferred) == 1:
        return preferred[0]
    if len(candidates) != 1:
        raise AmbiguousFileError(
            f"ambiguous Shishuo Ling {label} selection: "
            + ", ".join(file.name for file in candidates)
        )
    return candidates[0]


def select_shishuo_ling_files(item: IAMetadata) -> dict[str, IAFile]:
    """Select PDF, OCR, and optional page-index derivatives for one Ling volume."""

    exact_pdf = f"{item.identifier}.pdf"
    pdf = select_deterministic_file(
        item.files,
        suffix=".pdf",
        preferred_names=(exact_pdf,),
        excluded_fragments=(".jp2.zip",),
    )
    ocr = _optional_file(
        item.files,
        suffix="_djvu.txt",
        preferred_name=f"{item.identifier}_djvu.txt",
        label="FULL TEXT OCR",
    )
    if ocr is None:
        raise WitnessDownloadError("Internet Archive item has no FULL TEXT OCR file")
    hocr = _optional_file(
        item.files,
        suffix="_hocr.html",
        preferred_name=f"{item.identifier}_hocr.html",
        label="HOCR",
    )
    page_index = _optional_file(
        item.files,
        suffix="_scandata.xml",
        preferred_name=f"{item.identifier}_scandata.xml",
        label="page-index",
    )
    selected: dict[str, IAFile] = {"pdf": pdf, "ocr": ocr}
    if hocr is not None:
        selected["hocr"] = hocr
    if page_index is not None:
        selected["page_index"] = page_index
    return selected


def _ia_metadata_value(item: IAMetadata, key: str) -> str:
    value = item.metadata.get(key)
    if isinstance(value, list):
        return str(value[0]) if value else ""
    return str(value or "")


def _ling_volume(item: IAMetadata) -> int | None:
    return _as_int(item.metadata.get("volume"))


def require_shishuo_ling_metadata(item: IAMetadata) -> int:
    """Validate the IA metadata identity required for the 1615 witness."""

    title = unicode_normalize("NFKC", item.title).casefold()
    if "shi shuo xin yu" not in title:
        raise NonMatchingItemError(
            f"{item.identifier}: title {item.title!r} is not Shi shuo xin yu"
        )
    date_values = (
        _ia_metadata_value(item, "date"),
        _ia_metadata_value(item, "year"),
    )
    if not any(value.startswith("1615") for value in date_values):
        raise NonMatchingItemError(
            f"{item.identifier}: publication date is not 1615 ({date_values!r})"
        )
    call_number = _ia_metadata_value(item, "call_number")
    if call_number != "PL2666 .L55 S56 1615":
        raise NonMatchingItemError(
            f"{item.identifier}: call number {call_number!r} does not match the registered witness"
        )
    volume = _ling_volume(item)
    if volume not in SHISHUO_LING_VOLUMES:
        raise NonMatchingItemError(
            f"{item.identifier}: metadata volume {volume!r} is outside the requested volumes"
        )
    return volume


def discover_shishuo_ling(
    *,
    searcher: Callable[[], Mapping[str, Any]] = fetch_ia_search,
    fetcher: Callable[[str], IAMetadata] = fetch_ia_metadata,
) -> dict[str, Any]:
    """Discover the three requested Ling volumes from IA search and metadata."""

    search_payload = searcher()
    documents = parse_ia_search(search_payload)
    candidate_identifiers = [str(doc.get("identifier") or "") for doc in documents]
    accepted: list[dict[str, Any]] = []
    rejected: list[dict[str, str]] = []
    excluded: list[dict[str, str]] = []
    seen_volumes: dict[int, str] = {}
    duplicate_volumes: list[int] = []

    for identifier in candidate_identifiers:
        if not identifier:
            rejected.append({"identifier": "", "reason": "search result has no identifier"})
            continue
        try:
            item = fetcher(identifier)
            volume = require_shishuo_ling_metadata(item)
            selected = select_shishuo_ling_files(item)
        except NonMatchingItemError as error:
            # Search can return adjacent physical volumes (for example IA
            # records labelled 4 and 5). They are recorded, not guessed into
            # the requested three-volume witness.
            if "outside the requested volumes" in str(error):
                excluded.append({"identifier": identifier, "reason": str(error)})
            else:
                rejected.append({"identifier": identifier, "reason": str(error)})
            continue
        except HTTPError as error:
            rejected.append({"identifier": identifier, "reason": f"HTTP {error.code}"})
            continue
        except Exception as error:
            rejected.append(
                {"identifier": identifier, "reason": f"{type(error).__name__}: {error}"}
            )
            continue

        if volume in seen_volumes:
            duplicate_volumes.append(volume)
        else:
            seen_volumes[volume] = identifier
        accepted.append(
            {
                "identifier": item.identifier,
                "title": item.title,
                "volume": volume,
                "item": item,
                "files": selected,
            }
        )

    discovered_volumes = sorted(seen_volumes)
    missing_volumes = sorted(set(SHISHUO_LING_VOLUMES) - set(discovered_volumes))
    return {
        "search": search_payload,
        "candidate_identifiers": candidate_identifiers,
        "accepted": sorted(accepted, key=lambda record: (record["volume"], record["identifier"])),
        "rejected": rejected,
        "excluded": excluded,
        "discovered_volumes": discovered_volumes,
        "missing_volumes": missing_volumes,
        "duplicate_volumes": sorted(set(duplicate_volumes)),
        "complete": not rejected and not missing_volumes and not duplicate_volumes,
    }


def _candidate_identifier_range(
    first: int = JINSHU_FIRST_IDENTIFIER,
    last: int = JINSHU_LAST_IDENTIFIER,
) -> tuple[str, ...]:
    return tuple(f"020777{number:02d}.cn" for number in range(first, last + 1))


def discover_jinshu(
    *,
    fetcher: Callable[[str], IAMetadata] = fetch_ia_metadata,
    first: int = JINSHU_FIRST_IDENTIFIER,
    last: int = JINSHU_LAST_IDENTIFIER,
) -> dict[str, Any]:
    """Discover accepted Jinshu volumes and report all exceptions."""

    identifiers = _candidate_identifier_range(first, last)
    accepted: list[dict[str, Any]] = []
    rejected: list[dict[str, str]] = []
    seen_volumes: dict[int, str] = {}
    duplicate_volumes: list[int] = []

    def inspect(identifier: str) -> tuple[str, dict[str, Any] | None, dict[str, str] | None]:
        try:
            item = fetcher(identifier)
        except HTTPError as error:
            if error.code == 404:
                return identifier, None, {"identifier": identifier, "reason": "metadata 404"}
            return identifier, None, {"identifier": identifier, "reason": f"HTTP {error.code}"}
        except Exception as error:  # network exceptions belong in the lock report
            return identifier, None, {
                "identifier": identifier,
                "reason": f"{type(error).__name__}: {error}",
            }

        try:
            require_title(item, "晉書斠注")
            volume = extract_volume_number(item.title)
            if volume is None:
                raise WitnessDownloadError("volume number is absent from IA title metadata")
            selected = select_jinshu_files(item)
        except (WitnessDownloadError, ValueError) as error:
            return identifier, None, {"identifier": identifier, "reason": str(error)}

        return identifier, {
            "identifier": identifier,
            "title": item.title,
            "volume": volume,
            "item": item,
            "files": selected,
        }, None

    # Metadata requests are independent.  The resulting sequence is restored
    # to candidate-identifier order so lock manifests remain deterministic
    # apart from their explicitly recorded retrieval timestamps.
    with ThreadPoolExecutor(max_workers=METADATA_WORKERS) as pool:
        inspected = list(pool.map(inspect, identifiers))

    for identifier, accepted_record, rejected_record in inspected:
        if rejected_record is not None:
            rejected.append(rejected_record)
            continue
        if accepted_record is None:
            rejected.append(
                {"identifier": identifier, "reason": "candidate produced no discovery record"}
            )
            continue

        volume = int(accepted_record["volume"])
        if volume in seen_volumes:
            duplicate_volumes.append(volume)
        else:
            seen_volumes[volume] = identifier
        accepted.append(accepted_record)

    volumes = sorted(seen_volumes)
    expected = list(range(1, max(volumes) + 1)) if volumes else []
    missing_volumes = sorted(set(expected) - set(volumes))
    return {
        "candidate_identifiers": identifiers,
        "accepted": sorted(accepted, key=lambda record: (record["volume"], record["identifier"])),
        "rejected": rejected,
        "duplicate_volumes": sorted(set(duplicate_volumes)),
        "discovered_volumes": volumes,
        "missing_volumes": missing_volumes,
        "complete": not rejected and not duplicate_volumes and not missing_volumes,
    }


def discover_sanguozhi(
    *,
    fetcher: Callable[[str], IAMetadata] = fetch_ia_metadata,
    include_archival: bool = False,
) -> dict[str, Any]:
    """Resolve only the registered Sanguozhi target files."""

    try:
        item = fetcher(SANGUOZHI_ARCHIVE_ITEM)
        if item.identifier != SANGUOZHI_ARCHIVE_ITEM:
            # The identifier is a provenance field; do not silently relabel it.
            raise WitnessDownloadError(
                f"metadata identifier is {item.identifier!r}, expected {SANGUOZHI_ARCHIVE_ITEM!r}"
            )
        files = select_sanguozhi_files(item, include_archival=include_archival)
        return {"item": item, "files": files, "errors": []}
    except Exception as error:
        return {"item": None, "files": {}, "errors": [f"{type(error).__name__}: {error}"]}


def sha256_file(path: Path | str, *, chunk_size: int = 1024 * 1024) -> str:
    """Calculate a file digest by streaming it in bounded chunks."""

    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        while True:
            chunk = handle.read(chunk_size)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def archive_download_url(identifier: str, filename: str) -> str:
    return IA_DOWNLOAD_TEMPLATE.format(
        identifier=quote(identifier, safe=""),
        filename=quote(filename, safe="/"),
    )


def archive_mirror_download_url(
    item: IAMetadata, filename: str
) -> str | None:
    """Return an IA metadata-advertised mirror URL when one is available."""

    locations = item.raw.get("alternate_locations")
    if not isinstance(locations, Mapping):
        return None
    workable = locations.get("workable")
    if not isinstance(workable, list) or not workable:
        return None
    first = workable[0]
    if not isinstance(first, Mapping) or not first.get("server") or not first.get("dir"):
        return None
    return (
        f"https://{first['server']}{str(first['dir']).rstrip('/')}/"
        f"{quote(filename, safe='/')}"
    )


def _response_status(response: Any) -> int | None:
    value = getattr(response, "status", None)
    if value is not None:
        return int(value)
    getcode = getattr(response, "getcode", None)
    if getcode is None:
        return None
    value = getcode()
    return int(value) if value is not None else None


def stream_download(
    url: str,
    destination: Path | str,
    *,
    expected_sha256: str | None = None,
    timeout: float = 120.0,
    opener: Callable[..., Any] = urlopen,
    chunk_size: int = 1024 * 1024,
    expected_size: int | None = None,
) -> tuple[str, int, str]:
    """Download one file through a ``.part`` path and return status/size/hash.

    A completed destination is never overwritten.  Existing partial files are
    resumed when the server returns HTTP 206 and are safely restarted in the
    temporary path when the server ignores the range request.
    """

    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        actual = sha256_file(destination)
        if expected_sha256 and actual == expected_sha256:
            return "verified-existing", destination.stat().st_size, actual
        raise FileExistsError(
            f"refusing to overwrite existing file with unverified or different SHA-256: "
            f"{destination} ({actual})"
        )

    partial = destination.with_name(destination.name + ".part")
    resume_from = partial.stat().st_size if partial.exists() else 0
    if expected_size is not None and resume_from > expected_size:
        partial.unlink()
        resume_from = 0
    headers = {"User-Agent": "shishuoSketch-source-infrastructure/1.0"}
    headers["Accept-Encoding"] = "identity"
    headers["Connection"] = "close"
    if resume_from:
        headers["Range"] = f"bytes={resume_from}-"
    request = Request(url, headers=headers)
    try:
        response = opener(request, timeout=timeout)
    except TypeError:
        response = opener(request)
    status = _response_status(response)
    append = bool(resume_from and status == 206)
    mode = "ab" if append else "wb"
    written = resume_from if append else 0
    reader = getattr(response, "read1", None)
    with response, partial.open(mode) as handle:
        while True:
            # HTTPResponse.read(1 MiB) can wait for the entire requested
            # amount on a slow Archive mirror. read1() accepts whatever bytes
            # the mirror has made available and keeps resumable transfers
            # moving without changing the resulting digest.
            chunk = reader(chunk_size) if reader is not None else response.read(chunk_size)
            if not chunk:
                break
            if expected_size is not None and written + len(chunk) > expected_size:
                raise WitnessDownloadError(
                    f"download exceeded expected size for {url}: "
                    f"expected {expected_size} bytes"
                )
            handle.write(chunk)
            written += len(chunk)
    actual = sha256_file(partial)
    if expected_sha256 and actual != expected_sha256:
        raise WitnessDownloadError(
            f"SHA-256 mismatch for {url}: expected {expected_sha256}, got {actual}"
        )
    partial.replace(destination)
    return "downloaded", destination.stat().st_size, actual


def _safe_basename(filename: str) -> str:
    decoded = _decoded_name(filename)
    path = Path(decoded)
    if path.is_absolute() or ".." in path.parts:
        raise WitnessDownloadError(f"unsafe Internet Archive filename: {filename!r}")
    if not path.name:
        raise WitnessDownloadError(f"Internet Archive filename has no basename: {filename!r}")
    return path.name


def _relative_download_path(root: Path, kind: str, filename: str) -> Path:
    return root / kind / _safe_basename(filename)


def _old_file_record(
    previous_lock: Mapping[str, Any] | None,
    *,
    identifier: str,
    kind: str,
    filename: str,
) -> Mapping[str, Any] | None:
    if not previous_lock:
        return None
    for record in previous_lock.get("records", []):
        if record.get("identifier") != identifier:
            continue
        for file_record in record.get("files", []):
            if file_record.get("kind") == kind and file_record.get("filename") == filename:
                return file_record
    return None


def _download_record(
    *,
    identifier: str,
    item_file: IAFile,
    kind: str,
    root: Path,
    repository_root: Path,
    previous_lock: Mapping[str, Any] | None,
    timeout: float,
    retrieval_url: str | None = None,
    force_refresh: bool = False,
    expected_size: int | None = None,
) -> dict[str, Any]:
    destination = _relative_download_path(root, kind, item_file.name)
    relative = (
        destination.relative_to(repository_root).as_posix()
        if destination.is_absolute()
        else destination.as_posix()
    )
    url = archive_download_url(identifier, item_file.name)
    transfer_url = retrieval_url or url
    previous = _old_file_record(
        previous_lock,
        identifier=identifier,
        kind=kind,
        filename=item_file.name,
    )
    expected = (
        None
        if force_refresh
        else str(previous["sha256"])
        if previous and previous.get("sha256")
        else None
    )
    # A run interrupted after an atomic payload rename but before its final
    # lock write leaves a complete file without a prior digest record.  Do
    # not overwrite it: when IA supplies a size and it matches, hash the
    # existing file and record it as an already-present payload.  A size
    # mismatch still falls through to stream_download, which refuses to
    # overwrite the file.
    if destination.exists() and previous is None:
        actual_size = destination.stat().st_size
        if item_file.size is not None and actual_size == item_file.size:
            actual_hash = sha256_file(destination)
            return {
                "kind": kind,
                "identifier": identifier,
                "filename": item_file.name,
                "source_url": url,
                "retrieval_url": transfer_url,
                "path": relative,
                "size": actual_size,
                "sha256": actual_hash,
                "retrieved_at": _timestamp(),
                "status": "verified-existing",
                "verification_basis": "existing size matched IA metadata; SHA-256 recorded without overwrite",
                "text_authority": "non-authoritative OCR derivative" if kind == "ocr" else "scanned/page-image derivative",
            }
    try:
        download_destination = destination
        if force_refresh:
            # Keep the existing payload in place until the replacement has
            # streamed and hashed successfully.  A failed refresh therefore
            # cannot erase the last known witness payload.
            download_destination = destination.with_name(destination.name + ".refresh")
            refresh_partial = download_destination.with_name(download_destination.name + ".part")
            size_limit = expected_size if expected_size is not None else item_file.size
            if size_limit is not None and refresh_partial.exists() and refresh_partial.stat().st_size > size_limit:
                refresh_partial.unlink()
        status, size, digest = stream_download(
            transfer_url,
            download_destination,
            expected_sha256=expected,
            timeout=timeout,
            expected_size=(expected_size if expected_size is not None else item_file.size) if force_refresh else None,
        )
        size_limit = expected_size if expected_size is not None else item_file.size
        if force_refresh and size_limit is not None and size != size_limit:
            raise WitnessDownloadError(
                f"size mismatch for refreshed {item_file.name}: "
                f"expected {size_limit}, got {size}"
            )
        if force_refresh:
            download_destination.replace(destination)
            status = "refreshed"
        return {
            "kind": kind,
            "identifier": identifier,
            "filename": item_file.name,
            "source_url": url,
            "retrieval_url": transfer_url,
            "path": relative,
            "size": size,
            "sha256": digest,
            "retrieved_at": (
                previous.get("retrieved_at") if status == "verified-existing" and previous else _timestamp()
            ),
            "status": status,
            "text_authority": "non-authoritative OCR derivative" if kind == "ocr" else "scanned/page-image derivative",
        }
    except Exception as error:
        return {
            "kind": kind,
            "identifier": identifier,
            "filename": item_file.name,
            "source_url": url,
            "retrieval_url": transfer_url,
            "path": relative,
            "size": None,
            "sha256": None,
            "retrieved_at": _timestamp(),
            "status": "error",
            "error": f"{type(error).__name__}: {error}",
            "text_authority": "non-authoritative OCR derivative" if kind == "ocr" else "scanned/page-image derivative",
        }


def _old_wikisource_record(
    previous_lock: Mapping[str, Any] | None,
    *,
    page_title: str,
) -> Mapping[str, Any] | None:
    if not previous_lock:
        return None
    for record in previous_lock.get("records", []):
        if isinstance(record, Mapping) and record.get("page_title") == page_title:
            return record
    return None


def _wikisource_filename(page_title: str) -> str:
    page_key = page_title.rsplit("/", 1)[-1]
    if page_key not in WIKISOURCE_PAGE_TITLES:
        raise WitnessDownloadError(f"unregistered Wikisource page title: {page_title!r}")
    return f"{page_key}.wikitext"


def _wikisource_page_filename(page_title: str) -> str:
    if not page_title.startswith("Page:") or "/" not in page_title:
        raise WitnessDownloadError(f"unregistered Wikisource Page title: {page_title!r}")
    page_key = page_title[len("Page:") :].replace("/", "--")
    return f"pages/{page_key}.wikitext"


def _write_wikisource_record(
    *,
    revision: WikisourceRevision,
    root: Path,
    repository_root: Path,
    previous_lock: Mapping[str, Any] | None,
    filename: str | None = None,
    kind: str = "section",
    section_title: str | None = None,
    page_number: int | None = None,
    index_title: str | None = None,
) -> dict[str, Any]:
    filename = filename or _wikisource_filename(revision.page_title)
    destination = root / filename
    relative = (
        destination.relative_to(repository_root).as_posix()
        if destination.is_absolute()
        else destination.as_posix()
    )
    content = revision.content.encode("utf-8")
    digest = hashlib.sha256(content).hexdigest()
    previous = _old_wikisource_record(previous_lock, page_title=revision.page_title)
    if destination.exists():
        existing_digest = sha256_file(destination)
        if existing_digest != digest:
            raise FileExistsError(
                f"refusing to overwrite differing Wikisource source text: {destination}"
            )
        status = "verified-existing"
        retrieved_at = str(previous.get("retrieved_at") if previous else _timestamp())
    else:
        destination.parent.mkdir(parents=True, exist_ok=True)
        partial = destination.with_name(destination.name + ".part")
        partial.write_bytes(content)
        partial.replace(destination)
        status = "downloaded"
        retrieved_at = _timestamp()
    return {
        "witness_id": SHISHUO_WIKISOURCE_WITNESS_ID,
        "kind": kind,
        "page_title": revision.page_title,
        "source_url": revision.source_url,
        "api_url": revision.api_url,
        "filename": filename,
        "path": relative,
        "page_id": revision.page_id,
        "revision_id": revision.revision_id,
        "parent_revision_id": revision.parent_revision_id,
        "revision_timestamp": revision.timestamp,
        "size": len(content),
        "sha256": digest,
        "retrieved_at": retrieved_at,
        "retrieval_date": retrieved_at[:10],
        "status": status,
        "text_authority": "same-edition machine reference; not a replacement for Kanripo/SBCK",
        **(
            {"section_title": section_title}
            if section_title is not None
            else {}
        ),
        **({"page_number": page_number} if page_number is not None else {}),
        **({"index_title": index_title} if index_title is not None else {}),
    }


def run_shishuo_wikisource(
    root: Path,
    *,
    timeout: float = 60.0,
    fetcher: Callable[[str], WikisourceRevision] = fetch_wikisource_revision,
    batch_fetcher: Callable[[Sequence[str]], list[WikisourceRevision]] | None = None,
) -> tuple[Path, dict[str, Any]]:
    """Fetch section and Page-namespace text through the MediaWiki API."""

    destination_root = root / "sources/downloads/shishuo/wikisource-sbck"
    lock_path = destination_root / "manifest.lock.json"
    previous_lock = _read_json(lock_path)
    records: list[dict[str, Any]] = []
    errors: list[dict[str, str]] = []
    page_requests: list[tuple[str, str, int, str]] = []
    for page_title in WIKISOURCE_PAGE_TITLES:
        try:
            full_title = f"{WIKISOURCE_BASE_TITLE}/{page_title}"
            revision = fetcher(full_title)
            records.append(
                _write_wikisource_record(
                    revision=revision,
                    root=destination_root,
                    repository_root=root,
                    previous_lock=previous_lock,
                    kind="section",
                    section_title=page_title,
                )
            )
            for page_range in parse_wikisource_page_ranges(
                revision.content, section_title=page_title
            ):
                for page_number in range(page_range.first_page, page_range.last_page + 1):
                    page_title_api = f"Page:{page_range.index_title}/{page_number}"
                    page_requests.append(
                        (page_title, page_title_api, page_number, page_range.index_title)
                    )
        except Exception as error:
            errors.append(
                {
                    "page_title": page_title,
                    "reason": f"{type(error).__name__}: {error}",
                }
            )
    if batch_fetcher is None:
        if fetcher is fetch_wikisource_revision:
            batch_fetcher = lambda titles: fetch_wikisource_revisions(
                titles, timeout=timeout
            )
        else:
            batch_fetcher = lambda titles: [fetcher(title) for title in titles]
    for offset in range(0, len(page_requests), WIKISOURCE_PAGE_BATCH_SIZE):
        batch = page_requests[offset : offset + WIKISOURCE_PAGE_BATCH_SIZE]
        titles = [request[1] for request in batch]
        try:
            revisions = batch_fetcher(titles)
            by_title = {revision.page_title: revision for revision in revisions}
            for section_title, page_title, page_number, index_title in batch:
                revision = by_title.get(page_title)
                if revision is None:
                    raise WitnessDownloadError(
                        f"Wikisource batch response omitted page: {page_title}"
                    )
                records.append(
                    _write_wikisource_record(
                        revision=revision,
                        root=destination_root,
                        repository_root=root,
                        previous_lock=previous_lock,
                        filename=_wikisource_page_filename(page_title),
                        kind="page",
                        section_title=section_title,
                        page_number=page_number,
                        index_title=index_title,
                    )
                )
        except Exception as error:
            errors.append(
                {
                    "page_titles": f"{titles[0]} .. {titles[-1]}",
                    "reason": f"{type(error).__name__}: {error}",
                }
            )
    manifest: dict[str, Any] = {
        "schema": 1,
        "witness_id": SHISHUO_WIKISOURCE_WITNESS_ID,
        "source_record": WIKISOURCE_SOURCE_RECORD,
        "api_endpoint": WIKISOURCE_API_ENDPOINT,
        "base_title": WIKISOURCE_BASE_TITLE,
        "requested_pages": list(WIKISOURCE_PAGE_TITLES),
        "section_record_count": len(WIKISOURCE_PAGE_TITLES),
        "page_record_count": sum(1 for record in records if record.get("kind") == "page"),
        "retrieved_at": _timestamp(),
        "records": records,
        "errors": errors,
        "notes": [
            "Section files preserve the raw <pages> declarations; Page-namespace files preserve the raw machine-readable page wikitext behind those declarations.",
            "Revision IDs, source URLs, retrieval dates, byte sizes, and SHA-256 values are recorded for every section and page file.",
            "The text is used for same-edition alignment/search and never overwrites Kanripo/SBCK.",
        ],
    }
    _write_json(lock_path, manifest)
    return lock_path, manifest


def _read_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    with path.open(encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise WitnessDownloadError(f"lock manifest is not an object: {path}")
    return value


def _write_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def _manifest_path(root: Path, name: str) -> Path:
    return root / name / "manifest.lock.json"


def _discovery_record(
    *,
    identifier: str,
    title: str,
    volume: int | None,
    files: Sequence[dict[str, Any]],
    status: str = "discovered",
    error: str | None = None,
) -> dict[str, Any]:
    value: dict[str, Any] = {
        "identifier": identifier,
        "title": title,
        "volume": volume,
        "files": list(files),
        "status": status,
    }
    if error:
        value["error"] = error
    return value


def run_jinshu(
    root: Path,
    *,
    timeout: float = 120.0,
    fetcher: Callable[[str], IAMetadata] = fetch_ia_metadata,
) -> tuple[Path, dict[str, Any]]:
    """Discover/download the Jinshu series and always write its lock file."""

    destination_root = root / "sources/downloads/jinshu/jinshu-jiaozhu"
    lock_path = destination_root / "manifest.lock.json"
    previous_lock = _read_json(lock_path)
    discovery = discover_jinshu(fetcher=fetcher)
    jobs: list[tuple[dict[str, Any], str, IAFile]] = []
    for accepted in discovery["accepted"]:
        for kind, item_file in accepted["files"].items():
            jobs.append((accepted, kind, item_file))

    def download_job(
        job: tuple[dict[str, Any], str, IAFile]
    ) -> tuple[str, str, dict[str, Any]]:
        accepted, kind, item_file = job
        result = _download_record(
            identifier=accepted["identifier"],
            item_file=item_file,
            kind=kind,
            root=destination_root,
            repository_root=root,
            previous_lock=previous_lock,
            timeout=timeout,
        )
        return accepted["identifier"], kind, result

    # Transfers are independent.  Collecting them in submitted order keeps
    # the eventual lock manifest stable while four bounded workers avoid
    # making a 58-volume series needlessly serial.
    results_by_file: dict[tuple[str, str], dict[str, Any]] = {}
    with ThreadPoolExecutor(max_workers=DOWNLOAD_WORKERS) as pool:
        for identifier, kind, result in pool.map(download_job, jobs):
            results_by_file[(identifier, kind)] = result

    records: list[dict[str, Any]] = []
    for accepted in discovery["accepted"]:
        files: list[dict[str, Any]] = []
        for kind in accepted["files"]:
            files.append(results_by_file[(accepted["identifier"], kind)])
        status = "downloaded" if all(file["status"] in {"downloaded", "verified-existing"} for file in files) else "error"
        records.append(
            _discovery_record(
                identifier=accepted["identifier"],
                title=accepted["title"],
                volume=accepted["volume"],
                files=files,
                status=status,
                error=("one or more files failed" if status == "error" else None),
            )
        )

    errors = list(discovery["rejected"])
    for record in records:
        if record["status"] == "error":
            errors.append({"identifier": record["identifier"], "reason": record.get("error", "download error")})
    manifest: dict[str, Any] = {
        "schema": 1,
        "witness_id": JINSHU_WITNESS_ID,
        "metadata_endpoint": IA_METADATA_TEMPLATE,
        "candidate_identifiers": list(discovery["candidate_identifiers"]),
        "discovered_at": _timestamp(),
        "discovered_volumes": discovery["discovered_volumes"],
        "missing_volumes": discovery["missing_volumes"],
        "duplicate_volumes": discovery["duplicate_volumes"],
        "complete_discovery": discovery["complete"],
        "rejected_candidates": discovery["rejected"],
        "records": records,
        "errors": errors,
        "notes": [
            "PDF is the scanned/page-image derivative selected from IA metadata.",
            "OCR is downloaded only for search/alignment and is non-authoritative.",
            "A non-empty error list means the series must not be treated as complete.",
        ],
    }
    _write_json(lock_path, manifest)
    return lock_path, manifest


def run_sanguozhi(
    root: Path,
    *,
    timeout: float = 120.0,
    include_archival: bool = False,
    fetcher: Callable[[str], IAMetadata] = fetch_ia_metadata,
) -> tuple[Path, dict[str, Any]]:
    """Discover/download the selected Sanguozhi files."""

    destination_root = root / "sources/downloads/sanguozhi/song-edition"
    lock_path = destination_root / "manifest.lock.json"
    previous_lock = _read_json(lock_path)
    discovery = discover_sanguozhi(fetcher=fetcher, include_archival=include_archival)
    files: list[dict[str, Any]] = []
    errors = list(discovery["errors"])
    item = discovery.get("item")
    if item is not None:
        for kind, item_file in discovery["files"].items():
            files.append(
                _download_record(
                    identifier=item.identifier,
                    item_file=item_file,
                    kind=("archival" if kind == "archival" else kind),
                    root=destination_root,
                    repository_root=root,
                    previous_lock=previous_lock,
                    timeout=timeout,
                    retrieval_url=archive_mirror_download_url(item, item_file.name),
                )
            )
        errors.extend(
            file["error"] for file in files if file.get("status") == "error" and file.get("error")
        )
    record = None
    if item is not None:
        record = _discovery_record(
            identifier=item.identifier,
            title=item.title,
            volume=None,
            files=files,
            status=("downloaded" if not errors else "error"),
            error=("one or more files failed" if errors else None),
        )
    manifest: dict[str, Any] = {
        "schema": 1,
        "witness_id": SANGUOZHI_WITNESS_ID,
        "archive_item": SANGUOZHI_ARCHIVE_ITEM,
        "metadata_endpoint": IA_METADATA_TEMPLATE.format(identifier=SANGUOZHI_ARCHIVE_ITEM),
        "discovered_at": _timestamp(),
        "include_archival": include_archival,
        "target_title": SANGUOZHI_TARGET_TITLE,
        "records": [record] if record is not None else [],
        "errors": errors,
        "notes": [
            "The selected PDF is a searchable/text derivative when available.",
            "OCR is a convenience derivative for search/alignment; page images remain verification authority.",
            "The JP2 ZIP is excluded unless --include-archival is explicitly supplied.",
        ],
    }
    _write_json(lock_path, manifest)
    return lock_path, manifest


def run_shishuo_ling(
    root: Path,
    *,
    timeout: float = 120.0,
    searcher: Callable[[], Mapping[str, Any]] = fetch_ia_search,
    fetcher: Callable[[str], IAMetadata] = fetch_ia_metadata,
) -> tuple[Path, dict[str, Any]]:
    """Discover and download the requested three 1615 Ling volumes."""

    destination_root = root / "sources/downloads/shishuo/ling-1615"
    lock_path = destination_root / "manifest.lock.json"
    previous_lock = _read_json(lock_path)
    discovery = discover_shishuo_ling(searcher=searcher, fetcher=fetcher)
    jobs: list[tuple[dict[str, Any], str, IAFile]] = []
    for accepted in discovery["accepted"]:
        for kind, item_file in accepted["files"].items():
            jobs.append((accepted, kind, item_file))

    def download_job(
        job: tuple[dict[str, Any], str, IAFile]
    ) -> tuple[str, str, dict[str, Any]]:
        accepted, kind, item_file = job
        item = accepted["item"]
        result = _download_record(
            identifier=accepted["identifier"],
            item_file=item_file,
            kind=kind,
            root=destination_root,
            repository_root=root,
            previous_lock=previous_lock,
            timeout=timeout,
            retrieval_url=archive_mirror_download_url(item, item_file.name),
        )
        return accepted["identifier"], kind, result

    results_by_file: dict[tuple[str, str], dict[str, Any]] = {}
    with ThreadPoolExecutor(max_workers=DOWNLOAD_WORKERS) as pool:
        for identifier, kind, result in pool.map(download_job, jobs):
            results_by_file[(identifier, kind)] = result

    records: list[dict[str, Any]] = []
    errors: list[dict[str, str]] = list(discovery["rejected"])
    for accepted in discovery["accepted"]:
        files = [
            results_by_file[(accepted["identifier"], kind)]
            for kind in accepted["files"]
        ]
        status = (
            "downloaded"
            if all(file["status"] in {"downloaded", "verified-existing"} for file in files)
            else "error"
        )
        if status == "error":
            errors.append({"identifier": accepted["identifier"], "reason": "one or more files failed"})
        records.append(
            _discovery_record(
                identifier=accepted["identifier"],
                title=accepted["title"],
                volume=accepted["volume"],
                files=files,
                status=status,
                error=("one or more files failed" if status == "error" else None),
            )
        )
    manifest: dict[str, Any] = {
        "schema": 1,
        "witness_id": SHISHUO_LING_WITNESS_ID,
        "search_endpoint": ia_advancedsearch_url(),
        "search_query": SHISHUO_LING_SEARCH_QUERY,
        "metadata_endpoint": IA_METADATA_TEMPLATE,
        "retrieved_at": _timestamp(),
        "candidate_identifiers": discovery["candidate_identifiers"],
        "discovered_volumes": discovery["discovered_volumes"],
        "missing_volumes": discovery["missing_volumes"],
        "duplicate_volumes": discovery["duplicate_volumes"],
        "excluded_candidates": discovery["excluded"],
        "complete_discovery": discovery["complete"],
        "records": records,
        "errors": errors,
        "notes": [
            "The PDF is the scanned/page-image verification authority.",
            "FULL TEXT OCR, HOCR, and page-index files are convenience derivatives for search/alignment only.",
            "JP2 archives are excluded by design.",
        ],
    }
    _write_json(lock_path, manifest)
    return lock_path, manifest


def verify_pdf_readability(path: Path | str, *, timeout: float = 60.0) -> tuple[bool, str]:
    """Run an available PDF verifier without changing the PDF."""

    pdf_path = Path(path)
    try:
        result = subprocess.run(
            ["pdfinfo", str(pdf_path)],
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except FileNotFoundError:
        with pdf_path.open("rb") as handle:
            prefix = handle.read(8)
        with pdf_path.open("rb") as handle:
            handle.seek(max(0, pdf_path.stat().st_size - 1024))
            suffix = handle.read()
        readable = prefix.startswith(b"%PDF-") and b"%%EOF" in suffix
        return readable, "signature fallback (pdfinfo unavailable)"
    detail = (result.stdout or result.stderr or "").strip()
    return result.returncode == 0, detail[:2000]


def run_shishuo_ling_volume(
    root: Path,
    *,
    volume: int,
    timeout: float = 120.0,
    searcher: Callable[[], Mapping[str, Any]] = fetch_ia_search,
    fetcher: Callable[[str], IAMetadata] = fetch_ia_metadata,
) -> tuple[Path, dict[str, Any]]:
    """Refresh one Ling PDF while preserving all other locked payloads."""

    if volume not in SHISHUO_LING_VOLUMES:
        raise WitnessDownloadError(f"unsupported Shishuo Ling volume: {volume}")
    destination_root = root / "sources/downloads/shishuo/ling-1615"
    lock_path = destination_root / "manifest.lock.json"
    previous_lock = _read_json(lock_path)
    if previous_lock is None:
        raise WitnessDownloadError(f"missing existing Ling lock manifest: {lock_path}")
    discovery = discover_shishuo_ling(searcher=searcher, fetcher=fetcher)
    accepted = [item for item in discovery["accepted"] if item["volume"] == volume]
    if len(accepted) != 1:
        raise WitnessDownloadError(
            f"expected exactly one discovered Ling volume {volume}, got {len(accepted)}"
        )
    selected = accepted[0]
    pdf = selected["files"]["pdf"]
    previous_target_record = next(
        (
            record
            for record in previous_lock.get("records", [])
            if record.get("identifier") == selected["identifier"]
        ),
        None,
    )
    if previous_target_record is None:
        raise WitnessDownloadError(
            f"existing Ling lock has no record for {selected['identifier']}"
        )
    old_pdf_size = next(
        (
            file_record.get("size")
            for file_record in previous_target_record.get("files", [])
            if file_record.get("kind") == "pdf"
        ),
        None,
    )
    result = _download_record(
        identifier=selected["identifier"],
        item_file=pdf,
        kind="pdf",
        root=destination_root,
        repository_root=root,
        previous_lock=previous_lock,
        timeout=timeout,
        retrieval_url=archive_mirror_download_url(selected["item"], pdf.name),
        force_refresh=True,
        expected_size=(
            int(pdf.size)
            if pdf.size is not None
            else int(old_pdf_size)
            if old_pdf_size is not None
            else None
        ),
    )
    pdf_path = root / str(result["path"])
    if result["status"] not in {"error"}:
        readable, detail = verify_pdf_readability(pdf_path)
        result["pdf_readability"] = "passed" if readable else "failed"
        result["pdf_readability_detail"] = detail
        if not readable:
            result["status"] = "error"
            result["error"] = "replacement PDF failed readability verification"
    else:
        result["pdf_readability"] = "not_run"

    records = list(previous_lock.get("records", []))
    target_record = next(
        (record for record in records if record.get("identifier") == selected["identifier"]),
        None,
    )
    if target_record is None:
        raise WitnessDownloadError(
            f"existing Ling lock has no record for {selected['identifier']}"
        )
    old_pdf_sha256 = next(
        (
            file_record.get("sha256")
            for file_record in target_record.get("files", [])
            if file_record.get("kind") == "pdf"
        ),
        None,
    )
    old_files = list(target_record.get("files", []))
    updated_files = []
    replaced = False
    for file_record in old_files:
        if file_record.get("kind") == "pdf":
            updated_files.append(result if result["status"] != "error" else file_record)
            replaced = True
        else:
            updated_files.append(file_record)
    if not replaced:
        raise WitnessDownloadError(
            f"existing Ling lock has no PDF record for {selected['identifier']}"
        )
    target_record["files"] = updated_files
    if result["status"] != "error":
        target_record["status"] = "downloaded"
        target_record.pop("error", None)
        target_record.pop("refresh_status", None)
        target_record.pop("refresh_error", None)
        target_record.pop("refresh_fallback_derivatives", None)
    else:
        target_record["refresh_status"] = "failed"
        target_record["refresh_error"] = result.get("error", "volume refresh failed")
        target_record["refresh_fallback_derivatives"] = [
            file_record.get("path")
            for file_record in old_files
            if file_record.get("kind") in {"ocr", "hocr", "page_index"}
        ]
    errors = [
        error
        for error in previous_lock.get("errors", [])
        if str(error.get("identifier", "")) != selected["identifier"]
    ]
    if result["status"] == "error":
        errors.append(
            {
                "identifier": selected["identifier"],
                "reason": result.get("error", "volume refresh failed"),
            }
        )
    manifest = dict(previous_lock)
    manifest["records"] = records
    manifest["errors"] = errors
    manifest["retrieved_at"] = _timestamp()
    history = list(manifest.get("repair_history", []))
    history.append(
        {
            "volume": volume,
            "identifier": selected["identifier"],
            "kind": "pdf",
            "attempted_at": _timestamp(),
            "old_sha256": old_pdf_sha256,
            "result_status": result["status"],
            "result_error": result.get("error"),
            "pdf_readability": result.get("pdf_readability"),
        }
    )
    manifest["repair_history"] = history
    manifest["notes"] = list(manifest.get("notes", []))
    manifest["notes"].append(
        "Volume 3 PDF was refreshed independently; OCR, HOCR, and page-index payloads were not redownloaded."
    )
    _write_json(lock_path, manifest)
    return lock_path, manifest


def _config_value(config: Mapping[str, Any], key: str) -> str:
    downloads = config.get("downloads")
    if not isinstance(downloads, Mapping) or key not in downloads:
        raise WitnessDownloadError(f"config/sources.yaml has no downloads.{key} path")
    return str(downloads[key])


def _load_yaml(path: Path) -> Mapping[str, Any]:
    """Load YAML config with PyYAML, while keeping network code stdlib-only."""

    try:
        import yaml  # type: ignore
    except ImportError as error:
        raise WitnessDownloadError(
            "PyYAML is required to read the repository YAML config; install it or use the checked-in config with the test environment"
        ) from error
    with path.open(encoding="utf-8") as handle:
        value = yaml.safe_load(handle)
    if not isinstance(value, Mapping):
        raise WitnessDownloadError(f"configuration is not a mapping: {path}")
    return value


def _resolve_download_roots(root: Path, config_path: Path) -> tuple[Path, Path, Path, Path]:
    config = _load_yaml(config_path)
    shishuo_wikisource = root / _config_value(config, "shishuo_wikisource")
    shishuo_ling = root / _config_value(config, "shishuo_ling")
    jinshu = root / _config_value(config, "jinshu_jiaozhu")
    sanguozhi = root / _config_value(config, "sanguozhi_song")
    expected_shishuo_wikisource = root / "sources/downloads/shishuo/wikisource-sbck"
    expected_shishuo_ling = root / "sources/downloads/shishuo/ling-1615"
    expected_jinshu = root / "sources/downloads/jinshu/jinshu-jiaozhu"
    expected_sanguozhi = root / "sources/downloads/sanguozhi/song-edition"
    if (
        shishuo_wikisource != expected_shishuo_wikisource
        or shishuo_ling != expected_shishuo_ling
        or jinshu != expected_jinshu
        or sanguozhi != expected_sanguozhi
    ):
        raise WitnessDownloadError(
            "download roots in config/sources.yaml do not match the registered witness layout"
        )
    return jinshu, sanguozhi, shishuo_wikisource, shishuo_ling


def _verify_file_record(root: Path, record: Mapping[str, Any]) -> list[str]:
    errors: list[str] = []
    path = root / str(record.get("path", ""))
    if record.get("status") not in {"downloaded", "verified-existing", "refreshed"}:
        errors.append(f"{path}: status is {record.get('status')!r}")
        return errors
    if not path.is_file():
        return [f"{path}: file is missing"]
    actual_size = path.stat().st_size
    actual_hash = sha256_file(path)
    if record.get("size") != actual_size:
        errors.append(f"{path}: size {actual_size} != manifest {record.get('size')}")
    if record.get("sha256") != actual_hash:
        errors.append(f"{path}: SHA-256 {actual_hash} != manifest {record.get('sha256')}")
    return errors


def verify_lock_manifest(root: Path, path: Path) -> list[str]:
    """Verify all downloaded file hashes in one lock manifest."""

    if not path.exists():
        return [f"missing lock manifest: {path}"]
    try:
        manifest = _read_json(path)
    except Exception as error:
        return [f"{path}: {type(error).__name__}: {error}"]
    if manifest is None:
        return [f"missing lock manifest: {path}"]
    errors: list[str] = []
    for record in manifest.get("records", []):
        if isinstance(record, Mapping) and record.get("path"):
            errors.extend(_verify_file_record(root, record))
        if isinstance(record, Mapping):
            for file_record in record.get("files", []):
                errors.extend(_verify_file_record(root, file_record))
    if manifest.get("errors"):
        errors.append(f"{path}: manifest records discovery/download errors")
    return errors


def validate_registry_document(document: Mapping[str, Any]) -> list[str]:
    """Validate the common witness fields used by the three registries."""

    errors: list[str] = []
    witnesses = document.get("witnesses")
    if document.get("schema") != 1:
        errors.append("schema must be 1")
    if not isinstance(witnesses, list):
        return errors + ["witnesses must be a list"]
    identifiers: set[str] = set()
    for index, witness in enumerate(witnesses, start=1):
        if not isinstance(witness, Mapping):
            errors.append(f"witness {index} is not a mapping")
            continue
        missing = sorted(REQUIRED_REGISTRY_FIELDS - set(witness))
        if missing:
            errors.append(f"witness {index} missing: {', '.join(missing)}")
        identifier = str(witness.get("id", ""))
        if not identifier:
            errors.append(f"witness {index} has an empty id")
        elif identifier in identifiers:
            errors.append(f"duplicate witness id: {identifier}")
        identifiers.add(identifier)
        if witness.get("local") is True and not witness.get("local_path"):
            errors.append(f"local witness {identifier} has no local_path")
    return errors


def _print_jinshu_list(discovery: Mapping[str, Any]) -> None:
    print("Jinshu 晉書斠注 discovery")
    for record in discovery.get("accepted", []):
        names = ", ".join(file.name for file in record["files"].values())
        print(f"  volume {record['volume']:>2}: {record['identifier']} — {names}")
    for rejected in discovery.get("rejected", []):
        print(f"  rejected {rejected['identifier']}: {rejected['reason']}")
    print(f"  missing volumes: {discovery.get('missing_volumes', [])}")
    print(f"  duplicate volumes: {discovery.get('duplicate_volumes', [])}")


def _print_sanguozhi_list(discovery: Mapping[str, Any]) -> None:
    print("Sanguozhi 南宋刊本《三國志》 discovery")
    if discovery.get("item") is not None:
        item = discovery["item"]
        print(f"  item: {item.identifier} — {item.title}")
        for kind, file in discovery.get("files", {}).items():
            print(f"  {kind}: {file.name}")
    for error in discovery.get("errors", []):
        print(f"  error: {error}")


def _print_shishuo_list(discovery: Mapping[str, Any]) -> None:
    print("Shishuo Xinyu Wikisource 四部叢刊 witness")
    print("  pages: " + ", ".join(WIKISOURCE_PAGE_TITLES))
    print("Shishuo Xinyu 1615 凌氏刻本 discovery")
    for record in discovery.get("accepted", []):
        names = ", ".join(file.name for file in record["files"].values())
        print(f"  volume {record['volume']}: {record['identifier']} — {names}")
    for rejected in discovery.get("rejected", []):
        print(f"  rejected {rejected['identifier']}: {rejected['reason']}")
    for excluded in discovery.get("excluded", []):
        print(f"  excluded {excluded['identifier']}: {excluded['reason']}")
    print(f"  missing volumes: {discovery.get('missing_volumes', [])}")


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument("--list", action="store_true", help="discover and list files without downloading")
    modes.add_argument("--shishuo-wikisource", action="store_true", help="download the Shishuo Wikisource 四部叢刊 machine reference")
    modes.add_argument("--shishuo-ling", action="store_true", help="download the Shishuo 1615 凌氏刻本 PDF and OCR derivatives")
    modes.add_argument("--shishuo-ling-volume", type=int, choices=SHISHUO_LING_VOLUMES, help="refresh only one existing Shishuo 1615 Ling volume PDF")
    modes.add_argument("--shishuo", action="store_true", help="download registered downloadable Shishuo witnesses")
    modes.add_argument("--jinshu-jiaozhu", action="store_true", help="discover and download the Jinshu 斠注 series")
    modes.add_argument("--sanguozhi-song", action="store_true", help="discover and download the selected Sanguozhi Song-edition derivatives")
    modes.add_argument("--all", action="store_true", help="download both witnesses; excludes archival JP2")
    modes.add_argument("--verify", action="store_true", help="verify existing lock manifests and downloaded hashes")
    parser.add_argument("--root", type=Path, default=REPOSITORY_ROOT, help="repository root")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG, help="source configuration path")
    parser.add_argument("--timeout", type=float, default=120.0, help="network timeout in seconds")
    parser.add_argument(
        "--include-archival",
        action="store_true",
        help="with --sanguozhi-song only, include the large JP2 ZIP explicitly",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_argument_parser()
    args = parser.parse_args(argv)
    root = args.root.resolve()
    config = args.config if args.config.is_absolute() else root / args.config
    try:
        jinshu_root, sanguozhi_root, shishuo_wikisource_root, shishuo_ling_root = _resolve_download_roots(root, config)
        if args.list:
            _print_shishuo_list(discover_shishuo_ling())
            _print_jinshu_list(discover_jinshu())
            _print_sanguozhi_list(discover_sanguozhi(include_archival=False))
            return 0
        if args.verify:
            errors = verify_lock_manifest(root, shishuo_wikisource_root / "manifest.lock.json")
            errors.extend(verify_lock_manifest(root, shishuo_ling_root / "manifest.lock.json"))
            errors.extend(verify_lock_manifest(root, jinshu_root / "manifest.lock.json"))
            errors.extend(verify_lock_manifest(root, sanguozhi_root / "manifest.lock.json"))
            if errors:
                for error in errors:
                    print(f"ERROR: {error}", file=sys.stderr)
                return 1
            print("SHA-256 verification passed for all lock manifests")
            return 0

        results: list[tuple[Path, dict[str, Any]]] = []
        if args.shishuo_wikisource or args.shishuo or args.all:
            results.append((run_shishuo_wikisource(root, timeout=args.timeout)[0], {}))
        if args.shishuo_ling or args.shishuo or args.all:
            results.append((run_shishuo_ling(root, timeout=args.timeout)[0], {}))
        if args.shishuo_ling_volume is not None:
            results.append(
                (
                    run_shishuo_ling_volume(
                        root,
                        volume=args.shishuo_ling_volume,
                        timeout=args.timeout,
                    )[0],
                    {},
                )
            )
        if args.jinshu_jiaozhu or args.all:
            results.append((run_jinshu(root, timeout=args.timeout)[0], {}))
        if args.sanguozhi_song or args.all:
            if args.include_archival and args.all:
                parser.error("--include-archival is not enabled by --all; use --sanguozhi-song explicitly")
            results.append(
                (
                    run_sanguozhi(
                        root,
                        timeout=args.timeout,
                        include_archival=args.include_archival,
                    )[0],
                    {},
                )
            )
        errors: list[str] = []
        for lock_path, _ in results:
            print(f"wrote {lock_path}")
            manifest = _read_json(lock_path) or {}
            errors.extend(str(item) for item in manifest.get("errors", []))
        return 1 if errors else 0
    except (OSError, WitnessDownloadError, HTTPError) as error:
        parser.error(str(error))
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
