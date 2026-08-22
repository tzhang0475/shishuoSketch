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
    python scripts/download_witnesses.py --shishuo-jianshu
    python scripts/download_witnesses.py --shishuo
    python scripts/download_witnesses.py --jinshu-jiaozhu
    python scripts/download_witnesses.py --jinshu-wikisource-siku
    python scripts/download_witnesses.py --sanguozhi-wikisource
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
import tempfile
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
CTEXT_API_ENDPOINT = "https://api.ctext.org/gettext"
CTEXT_JIANSHU_SOURCE_RECORD = "https://ctext.org/wiki.pl?if=gb&res=40889"
CTEXT_JIANSHU_URN = "ctp:wb40889"
CTEXT_JIANSHU_WITNESS_ID = "shishuo-jianshu-yujiaxi"
CTEXT_JIANSHU_ROOT = "sources/references/shishuo/yujiaxi-jianshu"
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
JINSHU_WIKISOURCE_SOURCE_RECORD = "https://zh.wikisource.org/wiki/晉書_(四庫全書本)"
JINSHU_WIKISOURCE_BASE_TITLE = "晉書 (四庫全書本)"
JINSHU_WIKISOURCE_WITNESS_ID = "jinshu-wikisource-siku"
JINSHU_WIKISOURCE_ROOT = "sources/downloads/jinshu/wikisource-siku"
JINSHU_WIKISOURCE_VOLUME_COUNT = 130
JINSHU_WIKISOURCE_BATCH_SIZE = 10
JINSHU_FIRST_IDENTIFIER = 18
JINSHU_LAST_IDENTIFIER = 75
JINSHU_WITNESS_ID = "jinshu-jiaozhu"
SANGUOZHI_WITNESS_ID = "sanguozhi-song-shoryobu"
SANGUOZHI_ARCHIVE_ITEM = "songkeben"
SANGUOZHI_WIKISOURCE_WITNESS_ID = "sanguozhi-wikisource"
SANGUOZHI_WIKISOURCE_ROOT = "sources/downloads/sanguozhi/wikisource"
SANGUOZHI_WIKISOURCE_SOURCE_RECORD = "https://zh.wikisource.org/wiki/三國志"
SANGUOZHI_WIKISOURCE_BASE_TITLE = "三國志"
SANGUOZHI_WIKISOURCE_VOLUME_COUNT = 65
SANGUOZHI_WIKISOURCE_BATCH_SIZE = 25
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


class CTextAPIError(WitnessDownloadError):
    """Raised for a structured error returned by the official CText API."""

    def __init__(self, code: str, description: str) -> None:
        self.code = code
        self.description = description
        super().__init__(f"CText API {code}: {description}")


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


@dataclass(frozen=True)
class CTextAPIResponse:
    """One raw response from the CText ``gettext`` JSON API."""

    urn: str
    api_url: str
    response_identifier: str
    title: str
    fulltext: tuple[str, ...]
    subsections: tuple[str, ...]
    raw_bytes: bytes
    payload: Mapping[str, Any]


def _timestamp() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def ctext_api_url(
    urn: str,
    *,
    endpoint: str = CTEXT_API_ENDPOINT,
    api_key: str | None = None,
) -> str:
    """Build a CText ``gettext`` URL without ever recording an API key."""

    query: dict[str, str] = {"urn": urn}
    if api_key:
        query["apikey"] = api_key
    return f"{endpoint}?{urlencode(query)}"


def _ctext_list_of_strings(value: Any, field: str) -> tuple[str, ...]:
    if not isinstance(value, list):
        raise WitnessDownloadError(f"CText API {field} is not a list")
    if not all(isinstance(item, str) for item in value):
        raise WitnessDownloadError(f"CText API {field} contains a non-string item")
    return tuple(value)


def _ctext_subsection_urns(value: Any) -> tuple[str, ...]:
    if not isinstance(value, list):
        raise WitnessDownloadError("CText API subsections is not a list")
    result: list[str] = []
    for item in value:
        if isinstance(item, str):
            urn = item
        elif isinstance(item, Mapping):
            urn = item.get("urn") or item.get("textRef")
        else:
            urn = None
        if not isinstance(urn, str) or not urn:
            raise WitnessDownloadError("CText API subsection has no URN")
        result.append(urn)
    return tuple(result)


def parse_ctext_gettext(
    payload: Mapping[str, Any],
    *,
    urn: str,
    raw_bytes: bytes = b"",
    api_url: str | None = None,
) -> CTextAPIResponse:
    """Parse one official CText ``gettext`` response without text editing."""

    if not isinstance(payload, Mapping):
        raise WitnessDownloadError("CText API response is not an object")
    error = payload.get("error")
    if isinstance(error, Mapping):
        code = str(error.get("code") or "ERR_GENERIC")
        description = str(error.get("description") or error.get("html") or "")
        raise CTextAPIError(code, description)
    has_fulltext = "fulltext" in payload
    has_subsections = "subsections" in payload
    if not has_fulltext and not has_subsections:
        raise WitnessDownloadError(
            f"CText API response for {urn} has neither fulltext nor subsections"
        )
    fulltext = (
        _ctext_list_of_strings(payload.get("fulltext"), "fulltext")
        if has_fulltext
        else ()
    )
    subsections = (
        _ctext_subsection_urns(payload.get("subsections"))
        if has_subsections
        else ()
    )
    title = str(payload.get("title") or urn)
    identifier = str(payload.get("id") or payload.get("urn") or urn)
    return CTextAPIResponse(
        urn=urn,
        api_url=api_url or ctext_api_url(urn),
        response_identifier=identifier,
        title=title,
        fulltext=fulltext,
        subsections=subsections,
        raw_bytes=raw_bytes,
        payload=payload,
    )


def fetch_ctext_gettext(
    urn: str,
    *,
    timeout: float = 120.0,
    api_key: str | None = None,
    opener: Callable[..., Any] = urlopen,
) -> CTextAPIResponse:
    """Fetch one CText response from the JSON API, never from HTML."""

    resolved_key = api_key if api_key is not None else os.environ.get("CTEXT_API_KEY")
    request_url = ctext_api_url(urn, api_key=resolved_key)
    recorded_url = ctext_api_url(urn)
    request = Request(
        request_url,
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
            raw_bytes = response.read()
    except HTTPError as error:
        raise WitnessDownloadError(
            f"CText API HTTP error {error.code} for {urn}"
        ) from error
    try:
        payload = json.loads(raw_bytes.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise WitnessDownloadError(f"CText API returned invalid UTF-8 JSON for {urn}") from error
    return parse_ctext_gettext(
        payload,
        urn=urn,
        raw_bytes=raw_bytes,
        api_url=recorded_url,
    )


def _ctext_response_filename(ordinal: int, urn: str, suffix: str) -> str:
    digest = hashlib.sha256(urn.encode("utf-8")).hexdigest()[:16]
    return f"{ordinal:04d}-{digest}.{suffix}"


def _ctext_text_bytes(response: CTextAPIResponse) -> bytes:
    # CText returns an ordered list of paragraphs.  The derived convenience
    # file only joins those supplied paragraphs with the documented paragraph
    # separator; no characters within a paragraph are changed.
    return "\n\n".join(response.fulltext).encode("utf-8")


def _walk_ctext_tree(
    root_urn: str,
    fetcher: Callable[[str], CTextAPIResponse],
) -> tuple[list[CTextAPIResponse], dict[str, list[str]], dict[str, list[str]], dict[str, int]]:
    responses: dict[str, CTextAPIResponse] = {}
    order: list[str] = []
    children: dict[str, list[str]] = {}
    parents: dict[str, list[str]] = {}
    depths: dict[str, int] = {}

    def visit(urn: str, parent: str | None, depth: int, path: tuple[str, ...]) -> None:
        if urn in path:
            raise WitnessDownloadError(f"CText subsection cycle detected at {urn}")
        if parent is not None:
            children.setdefault(parent, []).append(urn)
            parents.setdefault(urn, []).append(parent)
        if urn in responses:
            depths[urn] = min(depths[urn], depth)
            return
        response = fetcher(urn)
        responses[urn] = response
        order.append(urn)
        depths[urn] = depth
        children.setdefault(urn, [])
        for child in response.subsections:
            visit(child, urn, depth + 1, path + (urn,))

    visit(root_urn, None, 0, ())
    return [responses[urn] for urn in order], children, parents, depths


def _write_ctext_metadata(path: Path, data: Mapping[str, Any]) -> None:
    """Write the small successful-retrieval metadata file without text edits."""

    lines: list[str] = []
    scalar_order = (
        "schema",
        "id",
        "work",
        "role",
        "edition",
        "source_provider",
        "source_type",
        "local",
        "local_path",
        "ctp_urn",
        "source_url",
        "api_endpoint",
        "retrieval_date",
        "retrieved_response_count",
        "total_characters",
        "local_copy_status",
        "text_authority",
        "structure_authority",
    )
    for key in scalar_order:
        if key not in data:
            continue
        value = data[key]
        if isinstance(value, bool):
            rendered = "true" if value else "false"
        elif value is None:
            rendered = "null"
        elif isinstance(value, int):
            rendered = str(value)
        else:
            rendered = json.dumps(str(value), ensure_ascii=False)
        lines.append(f"{key}: {rendered}")
    lines.append("section_titles:")
    for title in data.get("section_titles", []):
        lines.append(f"  - {json.dumps(str(title), ensure_ascii=False)}")
    lines.append("notes:")
    for note in data.get("notes", []):
        lines.append(f"  - {json.dumps(str(note), ensure_ascii=False)}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")


def _ctext_file_record(path: Path, *, kind: str) -> dict[str, Any]:
    data = path.read_bytes()
    return {
        "kind": kind,
        "path": path.name,
        "size": len(data),
        "sha256": hashlib.sha256(data).hexdigest(),
    }


def run_shishuo_jianshu(
    root: Path,
    *,
    timeout: float = 120.0,
    api_key: str | None = None,
    fetcher: Callable[[str], CTextAPIResponse] | None = None,
) -> tuple[Path | None, dict[str, Any]]:
    """Retrieve the complete CText witness recursively through ``gettext``.

    Retrieval is staged and committed only after every API subsection has
    been fetched.  An authentication failure therefore leaves no partial
    local scholarly-reference copy.
    """

    resolved_key = api_key if api_key is not None else os.environ.get("CTEXT_API_KEY")
    if fetcher is None:
        fetcher = lambda urn: fetch_ctext_gettext(
            urn, timeout=timeout, api_key=resolved_key
        )
    try:
        responses, children, parents, depths = _walk_ctext_tree(
            CTEXT_JIANSHU_URN, fetcher
        )
    except CTextAPIError as error:
        status = (
            "blocked_requires_authentication"
            if error.code in {"ERR_REQUIRES_AUTHENTICATION", "ERR_INVALID_APIKEY"}
            else "api_error"
        )
        return None, {
            "schema": 1,
            "witness_id": CTEXT_JIANSHU_WITNESS_ID,
            "ctp_urn": CTEXT_JIANSHU_URN,
            "source_url": CTEXT_JIANSHU_SOURCE_RECORD,
            "api_endpoint": CTEXT_API_ENDPOINT,
            "status": status,
            "errors": [{"code": error.code, "description": error.description}],
            "local_copy_created": False,
            "api_key_source": "CTEXT_API_KEY environment variable" if resolved_key else "not provided",
        }
    except WitnessDownloadError as error:
        return None, {
            "schema": 1,
            "witness_id": CTEXT_JIANSHU_WITNESS_ID,
            "ctp_urn": CTEXT_JIANSHU_URN,
            "source_url": CTEXT_JIANSHU_SOURCE_RECORD,
            "api_endpoint": CTEXT_API_ENDPOINT,
            "status": "api_error",
            "errors": [{"code": "LOCAL_RETRIEVAL_ERROR", "description": str(error)}],
            "local_copy_created": False,
            "api_key_source": "CTEXT_API_KEY environment variable" if resolved_key else "not provided",
        }

    if not responses:
        raise WitnessDownloadError("CText API returned no responses")
    retrieved_at = _timestamp()
    section_titles = [response.title for response in responses]
    total_characters = sum(
        len(paragraph) for response in responses for paragraph in response.fulltext
    )
    destination_root = root / CTEXT_JIANSHU_ROOT
    destination_parent = destination_root.parent
    destination_parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(
        dir=destination_parent, prefix=".yujiaxi-jianshu-"
    ) as temporary:
        stage = Path(temporary) / destination_root.name
        (stage / "raw").mkdir(parents=True)
        (stage / "text/sections").mkdir(parents=True)
        records: list[dict[str, Any]] = []
        for ordinal, response in enumerate(responses):
            raw_path = stage / "raw" / _ctext_response_filename(ordinal, response.urn, "json")
            text_path = stage / "text/sections" / _ctext_response_filename(ordinal, response.urn, "txt")
            raw_path.write_bytes(response.raw_bytes)
            text_path.write_bytes(_ctext_text_bytes(response))
            raw_record = _ctext_file_record(raw_path, kind="api-response")
            text_record = _ctext_file_record(text_path, kind="derived-text")
            # The paths above are staged; rewrite them to their eventual
            # repository-relative names without exposing the temporary path.
            raw_record["path"] = f"{CTEXT_JIANSHU_ROOT}/raw/{raw_path.name}"
            text_record["path"] = f"{CTEXT_JIANSHU_ROOT}/text/sections/{text_path.name}"
            records.append(
                {
                    "ordinal": ordinal,
                    "urn": response.urn,
                    "api_response_identifier": response.response_identifier,
                    "title": response.title,
                    "parent_urns": parents.get(response.urn, []),
                    "depth": depths[response.urn],
                    "subsections": list(response.subsections),
                    "api_url": ctext_api_url(response.urn),
                    "fulltext_paragraph_count": len(response.fulltext),
                    "character_count": sum(len(paragraph) for paragraph in response.fulltext),
                    "files": [raw_record, text_record],
                }
            )

        hierarchy = {
            "schema": 1,
            "root_urn": CTEXT_JIANSHU_URN,
            "nodes": [
                {
                    "ordinal": record["ordinal"],
                    "urn": record["urn"],
                    "title": record["title"],
                    "parent_urns": record["parent_urns"],
                    "depth": record["depth"],
                    "children": children.get(record["urn"], []),
                }
                for record in records
            ],
        }
        hierarchy_path = stage / "text/hierarchy.json"
        hierarchy_path.write_text(
            json.dumps(hierarchy, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
            newline="\n",
        )
        auxiliary_files = [
            _ctext_file_record(hierarchy_path, kind="hierarchy")
        ]
        auxiliary_files[0]["path"] = f"{CTEXT_JIANSHU_ROOT}/text/hierarchy.json"
        metadata = {
            "schema": 1,
            "id": CTEXT_JIANSHU_WITNESS_ID,
            "work": "世說新語",
            "role": "scholarly-reference-machine",
            "edition": "世說新語箋疏",
            "source_provider": "Chinese Text Project",
            "source_type": "scholarly-machine-reference",
            "local": True,
            "local_path": CTEXT_JIANSHU_ROOT,
            "ctp_urn": CTEXT_JIANSHU_URN,
            "source_url": CTEXT_JIANSHU_SOURCE_RECORD,
            "api_endpoint": CTEXT_API_ENDPOINT,
            "retrieval_date": retrieved_at[:10],
            "retrieved_response_count": len(responses),
            "total_characters": total_characters,
            "local_copy_status": "complete",
            "section_titles": section_titles,
            "text_authority": "scholarly reference; not a textual witness or replacement for the primary text",
            "structure_authority": "CText gettext subsection hierarchy only",
            "notes": [
                "Raw API response bytes are preserved under raw/.",
                "UTF-8 section files under text/ are convenience derivatives made from the ordered fulltext paragraphs.",
                "The API key is read only from CTEXT_API_KEY and is never recorded.",
            ],
        }
        lock = {
            "schema": 1,
            "witness_id": CTEXT_JIANSHU_WITNESS_ID,
            "work": "世說新語",
            "edition": "世說新語箋疏",
            "ctp_urn": CTEXT_JIANSHU_URN,
            "source_url": CTEXT_JIANSHU_SOURCE_RECORD,
            "api_endpoint": CTEXT_API_ENDPOINT,
            "status": "complete",
            "retrieved_at": retrieved_at,
            "retrieval_date": retrieved_at[:10],
            "api_key_source": "CTEXT_API_KEY environment variable (not recorded)",
            "response_count": len(responses),
            "section_titles": section_titles,
            "total_characters": total_characters,
            "records": records,
            "auxiliary_files": auxiliary_files,
            "notes": [
                "Every response was retrieved through the official CText gettext API recursively from the root URN.",
                "Raw API responses are preserved byte-for-byte; derived text files do not replace them.",
                "This scholarly reference is not a textual witness and must not overwrite the primary text.",
            ],
        }
        _write_json(stage / "manifest.lock.json", lock)
        _write_ctext_metadata(stage / "metadata.yaml", metadata)

        if destination_root.exists():
            stage_files = {path.relative_to(stage) for path in stage.rglob("*") if path.is_file()}
            existing_files = {path.relative_to(destination_root) for path in destination_root.rglob("*") if path.is_file()}
            if stage_files != existing_files:
                raise FileExistsError(
                    f"refusing to merge differing CText reference file set: {destination_root}"
                )
            for relative in sorted(stage_files):
                if (stage / relative).read_bytes() != (destination_root / relative).read_bytes():
                    raise FileExistsError(
                        f"refusing to overwrite differing CText reference file: {destination_root / relative}"
                    )
            existing_lock = _read_json(destination_root / "manifest.lock.json") or lock
            return destination_root / "manifest.lock.json", existing_lock
        stage.replace(destination_root)
    return destination_root / "manifest.lock.json", lock


def verify_ctext_lock_manifest(root: Path, path: Path) -> list[str]:
    """Verify raw/derived CText files against their lock manifest."""

    if not path.exists():
        return [f"missing CText lock manifest: {path}"]
    try:
        manifest = _read_json(path)
    except Exception as error:
        return [f"{path}: {type(error).__name__}: {error}"]
    if not manifest or manifest.get("status") != "complete":
        return [f"{path}: CText retrieval is not complete"]
    errors: list[str] = []
    file_records: list[Mapping[str, Any]] = []
    for record in manifest.get("records", []):
        if isinstance(record, Mapping):
            file_records.extend(
                item for item in record.get("files", []) if isinstance(item, Mapping)
            )
    file_records.extend(
        item for item in manifest.get("auxiliary_files", []) if isinstance(item, Mapping)
    )
    for record in file_records:
        file_path = root / str(record.get("path", ""))
        if not file_path.is_file():
            errors.append(f"{file_path}: file is missing")
            continue
        data = file_path.read_bytes()
        if len(data) != record.get("size"):
            errors.append(f"{file_path}: size differs from manifest")
        if hashlib.sha256(data).hexdigest() != record.get("sha256"):
            errors.append(f"{file_path}: SHA-256 differs from manifest")
    return errors


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


def _fetch_wikisource_json_bytes(
    api_url: str,
    *,
    timeout: float,
    opener: Callable[..., Any],
) -> tuple[bytes, Mapping[str, Any]]:
    """Fetch one MediaWiki response while retaining its exact API bytes."""

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
                raw_bytes = response.read()
            if not isinstance(raw_bytes, bytes):
                raise WitnessDownloadError("Wikisource API response was not bytes")
            payload = json.loads(raw_bytes.decode("utf-8"))
            if not isinstance(payload, Mapping):
                raise WitnessDownloadError("Wikisource API response is not an object")
            return raw_bytes, payload
        except HTTPError as error:
            if error.code != 429 or attempt >= WIKISOURCE_RETRY_LIMIT:
                raise
            retry_after = error.headers.get("Retry-After") if error.headers else None
            try:
                delay = int(retry_after) if retry_after else WIKISOURCE_RETRY_DELAY * (attempt + 1)
            except (TypeError, ValueError):
                delay = WIKISOURCE_RETRY_DELAY * (attempt + 1)
            time.sleep(min(max(delay, 1), 60))
    raise WitnessDownloadError("unreachable Wikisource API retry state")


def fetch_wikisource_revisions_with_raw(
    titles: Sequence[str],
    *,
    timeout: float = 60.0,
    opener: Callable[..., Any] = urlopen,
) -> tuple[list[WikisourceRevision], bytes, str]:
    """Fetch a batch of revisions and retain the exact JSON response bytes."""

    if not titles:
        return [], b"", wikisource_api_url("")
    api_url = wikisource_api_url("|".join(titles))
    raw_bytes, payload = _fetch_wikisource_json_bytes(
        api_url, timeout=timeout, opener=opener
    )
    return parse_wikisource_revisions(payload, titles=titles, api_url=api_url), raw_bytes, api_url


def sanguozhi_wikisource_volume_titles(
    volume_count: int = SANGUOZHI_WIKISOURCE_VOLUME_COUNT,
) -> dict[int, str]:
    """Return the observed zero-padded Sanguozhi Wikisource page titles."""

    if volume_count < 1:
        raise ValueError("volume_count must be positive")
    return {
        number: f"{SANGUOZHI_WIKISOURCE_BASE_TITLE}/卷{number:02d}"
        for number in range(1, volume_count + 1)
    }


def sanguozhi_section_for_juan(global_juan: int) -> tuple[str, int]:
    """Map a global juan to the canonical section and section-local number."""

    if 1 <= global_juan <= 30:
        return "魏書", global_juan
    if 31 <= global_juan <= 45:
        return "蜀書", global_juan - 30
    if 46 <= global_juan <= 65:
        return "吳書", global_juan - 45
    raise ValueError(f"Sanguozhi global juan is outside 1-65: {global_juan}")


def parse_sanguozhi_wikisource_section(
    content: str,
    *,
    global_juan: int,
) -> dict[str, Any]:
    """Read the structured Wikisource header section without editing text.

    The source pages expose ``|section = 魏書...``/``蜀書``/``呉書`` in a
    ``header`` or ``header2`` template.  The section is checked against the
    expected global-juan map; the page filename is never the sole authority.
    """

    expected_section, section_juan = sanguozhi_section_for_juan(global_juan)
    match = re.search(r"(?m)^\|\s*section\s*=\s*([^\n]+)", content)
    if match is None:
        raise WitnessDownloadError(
            f"Sanguozhi Wikisource juan {global_juan} has no structured header section"
        )
    header_section = match.group(1).strip()
    normalized = (
        unicode_normalize("NFKC", header_section)
        .replace("呉", "吳")
        .replace("吴", "吳")
    )
    observed_section = next(
        (candidate for candidate in ("魏書", "蜀書", "吳書") if candidate in normalized),
        None,
    )
    if observed_section is None:
        raise WitnessDownloadError(
            f"Sanguozhi Wikisource juan {global_juan} has an unrecognized section: {header_section!r}"
        )
    if observed_section != expected_section:
        raise WitnessDownloadError(
            f"Sanguozhi Wikisource juan {global_juan} is labeled {observed_section}, expected {expected_section}"
        )
    return {
        "section": expected_section,
        "section_juan": section_juan,
        "header_section": header_section,
    }


def jinshu_wikisource_discovery_url(
    *, endpoint: str = WIKISOURCE_API_ENDPOINT
) -> str:
    """Build the API query used to discover the numbered volume subpages."""

    query = urlencode(
        {
            "action": "query",
            "format": "json",
            "formatversion": "2",
            "list": "allpages",
            "apnamespace": "0",
            "apprefix": f"{JINSHU_WIKISOURCE_BASE_TITLE}/卷",
            "aplimit": "max",
        }
    )
    return f"{endpoint}?{query}"


def jinshu_wikisource_volume_titles(
    volume_count: int = JINSHU_WIKISOURCE_VOLUME_COUNT,
) -> dict[int, str]:
    """Return the discovered source-page convention for the 130 volumes.

    Wikisource stores volume one in the base page.  Volumes two onward use
    zero-padded ``/卷NNN`` subpages; this mapping is later checked against the
    API's prefix discovery response before any source text is accepted.
    """

    if volume_count < 1:
        raise ValueError("volume_count must be positive")
    return {
        1: JINSHU_WIKISOURCE_BASE_TITLE,
        **{
            number: f"{JINSHU_WIKISOURCE_BASE_TITLE}/卷{number:03d}"
            for number in range(2, volume_count + 1)
        },
    }


def parse_jinshu_wikisource_discovery(
    payload: Mapping[str, Any],
) -> dict[str, Any]:
    """Parse the API prefix listing without interpreting source text."""

    query = payload.get("query")
    if not isinstance(query, Mapping):
        raise WitnessDownloadError("Jinshu Wikisource discovery has no query object")
    pages = query.get("allpages")
    if not isinstance(pages, list):
        raise WitnessDownloadError("Jinshu Wikisource discovery has no allpages list")
    page_titles = [
        str(page["title"])
        for page in pages
        if isinstance(page, Mapping) and isinstance(page.get("title"), str)
    ]
    pattern = re.compile(
        rf"^{re.escape(JINSHU_WIKISOURCE_BASE_TITLE)}/卷(?P<number>\d{{3}})$"
    )
    by_volume: dict[int, list[str]] = {}
    unexpected: list[str] = []
    for title in page_titles:
        match = pattern.fullmatch(title)
        if match is None:
            unexpected.append(title)
            continue
        number = int(match.group("number"))
        by_volume.setdefault(number, []).append(title)
    duplicates = sorted(number for number, titles in by_volume.items() if len(titles) > 1)
    return {
        "page_titles": page_titles,
        "volume_titles": {
            number: titles[0]
            for number, titles in sorted(by_volume.items())
            if len(titles) == 1
        },
        "discovered_volumes": sorted(by_volume),
        "duplicate_volumes": duplicates,
        "unexpected_pages": sorted(unexpected),
    }


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


def _write_bytes_without_overwrite(path: Path, data: bytes) -> tuple[str, int, str]:
    """Write a payload atomically, refusing a differing existing payload."""

    digest = hashlib.sha256(data).hexdigest()
    if path.exists():
        existing_digest = sha256_file(path)
        if existing_digest != digest:
            raise FileExistsError(f"refusing to overwrite differing payload: {path}")
        return "verified-existing", len(data), digest
    path.parent.mkdir(parents=True, exist_ok=True)
    partial = path.with_name(path.name + ".part")
    partial.write_bytes(data)
    partial.replace(path)
    return "downloaded", len(data), digest


def _write_sanguozhi_wikisource_metadata(path: Path, data: Mapping[str, Any]) -> None:
    """Write the small tracked metadata companion for the 65-juan witness."""

    scalar_keys = (
        "schema",
        "id",
        "work",
        "role",
        "edition",
        "source_provider",
        "source_type",
        "local",
        "local_path",
        "source_record",
        "api_endpoint",
        "coverage",
        "expected_juan_count",
        "retrieved_juan_count",
        "status",
        "text_authority",
        "structure_authority",
    )
    lines: list[str] = []
    for key in scalar_keys:
        if key not in data:
            continue
        value = data[key]
        if isinstance(value, bool):
            rendered = "true" if value else "false"
        elif value is None:
            rendered = "null"
        elif isinstance(value, int):
            rendered = str(value)
        else:
            rendered = json.dumps(str(value), ensure_ascii=False)
        lines.append(f"{key}: {rendered}")
    lines.append("section_counts:")
    for section, count in sorted(data.get("section_counts", {}).items()):
        lines.append(f"  {section}: {int(count)}")
    lines.append("notes:")
    for note in data.get("notes", []):
        lines.append(f"  - {json.dumps(str(note), ensure_ascii=False)}")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    temporary.replace(path)


def run_sanguozhi_wikisource(
    root: Path,
    *,
    timeout: float = 120.0,
    batch_fetcher: Callable[
        [Sequence[str]], tuple[list[WikisourceRevision], bytes, str]
    ] | None = None,
) -> tuple[Path, dict[str, Any]]:
    """Retrieve all 65 Sanguozhi juan through the MediaWiki API.

    The page title supplies the requested coordinate, but the structured
    header section is checked before a page enters the witness manifest.  Raw
    API JSON and raw returned wikitext remain separate ignored payloads.
    """

    destination_root = root / SANGUOZHI_WIKISOURCE_ROOT
    raw_root = destination_root / "raw"
    text_root = destination_root / "text"
    lock_path = destination_root / "manifest.lock.json"
    previous_lock = _read_json(lock_path)
    volume_titles = sanguozhi_wikisource_volume_titles()
    errors: list[dict[str, Any]] = []
    records: list[dict[str, Any]] = []
    auxiliary_files: list[dict[str, Any]] = []
    duplicate_titles: list[str] = []

    if batch_fetcher is None:
        batch_fetcher = lambda titles: fetch_wikisource_revisions_with_raw(
            titles, timeout=timeout
        )

    for batch_number, offset in enumerate(
        range(0, len(volume_titles), SANGUOZHI_WIKISOURCE_BATCH_SIZE), start=1
    ):
        batch_numbers = sorted(volume_titles)[offset : offset + SANGUOZHI_WIKISOURCE_BATCH_SIZE]
        titles = [volume_titles[number] for number in batch_numbers]
        raw_path = raw_root / f"batch-{batch_number:03d}.json"
        try:
            revisions, raw_bytes, api_url = batch_fetcher(titles)
            raw_status, raw_size, raw_digest = _write_bytes_without_overwrite(
                raw_path, raw_bytes
            )
            auxiliary_files.append(
                {
                    "kind": "api-revision-batch",
                    "path": raw_path.relative_to(root).as_posix(),
                    "size": raw_size,
                    "sha256": raw_digest,
                    "status": raw_status,
                    "source_url": api_url,
                    "page_titles": list(titles),
                }
            )
            by_title: dict[str, WikisourceRevision] = {}
            for revision in revisions:
                if revision.page_title in by_title:
                    duplicate_titles.append(revision.page_title)
                else:
                    by_title[revision.page_title] = revision
            for number, title in zip(batch_numbers, titles):
                revision = by_title.get(title)
                if revision is None:
                    raise WitnessDownloadError(
                        f"Sanguozhi Wikisource batch omitted page: {title}"
                    )
                if revision.revision_id is None or not revision.timestamp:
                    raise WitnessDownloadError(
                        f"Sanguozhi Wikisource page has no resolvable revision: {title}"
                    )
                section = parse_sanguozhi_wikisource_section(
                    revision.content, global_juan=number
                )
                text_bytes = revision.content.encode("utf-8")
                text_path = text_root / f"volume-{number:03d}.wikitext"
                text_status, text_size, text_digest = _write_bytes_without_overwrite(
                    text_path, text_bytes
                )
                previous = _old_wikisource_record(
                    previous_lock, page_title=revision.page_title
                )
                retrieved_at = str(
                    previous.get("retrieved_at") if previous else _timestamp()
                )
                records.append(
                    {
                        "witness_id": SANGUOZHI_WIKISOURCE_WITNESS_ID,
                        "global_juan": number,
                        "section": section["section"],
                        "section_juan": section["section_juan"],
                        "title": section["header_section"],
                        "page_title": revision.page_title,
                        "source_url": revision.source_url,
                        "api_url": revision.api_url,
                        "page_id": revision.page_id,
                        "revision_id": revision.revision_id,
                        "source_revision": revision.revision_id,
                        "parent_revision_id": revision.parent_revision_id,
                        "revision_timestamp": revision.timestamp,
                        "raw_api_path": raw_path.relative_to(root).as_posix(),
                        "raw_api_size": raw_size,
                        "raw_api_sha256": raw_digest,
                        "source_path": text_path.relative_to(root).as_posix(),
                        "source_size": text_size,
                        "source_sha256": text_digest,
                        "retrieved_at": retrieved_at,
                        "retrieval_date": retrieved_at[:10],
                        "status": text_status,
                        "text_authority": "complete machine-text witness; not a replacement for Kanripo/WYG",
                        "structure_authority": "MediaWiki page title and structured header section",
                    }
                )
        except Exception as error:
            errors.append(
                {
                    "kind": "juan-batch",
                    "global_juans": list(batch_numbers),
                    "page_titles": list(titles),
                    "reason": f"{type(error).__name__}: {error}",
                }
            )

    records.sort(key=lambda record: int(record["global_juan"]))
    expected_juans = set(volume_titles)
    seen_juans = [int(record["global_juan"]) for record in records]
    duplicate_juans = sorted(
        number for number in set(seen_juans) if seen_juans.count(number) > 1
    )
    missing_juans = sorted(expected_juans - set(seen_juans))
    if duplicate_titles:
        errors.append(
            {
                "kind": "duplicate-pages",
                "page_titles": sorted(set(duplicate_titles)),
                "reason": "duplicate page titles returned by Wikisource API",
            }
        )
    if duplicate_juans:
        errors.append(
            {
                "kind": "duplicate-juans",
                "global_juans": duplicate_juans,
                "reason": "duplicate global juan records",
            }
        )
    if missing_juans:
        errors.append(
            {
                "kind": "missing-juans",
                "global_juans": missing_juans,
                "reason": "Sanguozhi Wikisource coverage is not complete 1-65",
            }
        )
    status = (
        "complete"
        if len(records) == SANGUOZHI_WIKISOURCE_VOLUME_COUNT
        and not errors
        and seen_juans == list(range(1, 66))
        else "incomplete"
    )
    section_counts = {
        section: sum(record.get("section") == section for record in records)
        for section in ("魏書", "蜀書", "吳書")
    }
    manifest: dict[str, Any] = {
        "schema": 1,
        "witness_id": SANGUOZHI_WIKISOURCE_WITNESS_ID,
        "source_record": SANGUOZHI_WIKISOURCE_SOURCE_RECORD,
        "api_endpoint": WIKISOURCE_API_ENDPOINT,
        "base_title": SANGUOZHI_WIKISOURCE_BASE_TITLE,
        "coverage": "1-65",
        "expected_juan_count": SANGUOZHI_WIKISOURCE_VOLUME_COUNT,
        "retrieved_juan_count": len(records),
        "section_counts": section_counts,
        "missing_juans": missing_juans,
        "duplicate_juans": duplicate_juans,
        "retrieved_at": _timestamp(),
        "status": status,
        "records": records,
        "auxiliary_files": auxiliary_files,
        "errors": errors,
        "notes": [
            "The 65 page titles are fetched through the MediaWiki API as raw wikitext; rendered HTML is not scraped.",
            "Global juan to 魏書/蜀書/吳書 mapping is checked against each page's structured header section.",
            "Raw API JSON and returned source wikitext are retained without textual correction or simplification.",
            "The witness is complete machine-text evidence infrastructure and does not overwrite Kanripo/WYG or create historical facts.",
        ],
    }
    _write_json(lock_path, manifest)
    metadata = {
        "schema": 1,
        "id": SANGUOZHI_WIKISOURCE_WITNESS_ID,
        "work": "三國志",
        "role": "secondary / complete-machine-text",
        "edition": "中文維基文庫《三國志》",
        "source_provider": "Wikisource",
        "source_type": "MediaWiki-wikitext",
        "local": True,
        "local_path": SANGUOZHI_WIKISOURCE_ROOT,
        "source_record": SANGUOZHI_WIKISOURCE_SOURCE_RECORD,
        "api_endpoint": WIKISOURCE_API_ENDPOINT,
        "coverage": "1-65",
        "expected_juan_count": SANGUOZHI_WIKISOURCE_VOLUME_COUNT,
        "retrieved_juan_count": len(records),
        "section_counts": section_counts,
        "status": status,
        "text_authority": "complete machine-text witness for SGZ1; not a replacement for Kanripo/WYG",
        "structure_authority": "MediaWiki page titles, structured header sections, and explicit annotation templates",
        "notes": manifest["notes"],
    }
    _write_sanguozhi_wikisource_metadata(destination_root / "metadata.yaml", metadata)
    return lock_path, manifest


def _write_jinshu_wikisource_metadata(path: Path, data: Mapping[str, Any]) -> None:
    """Write compact, trackable metadata for the Wikisource completion witness."""

    scalar_keys = (
        "schema",
        "id",
        "work",
        "role",
        "edition",
        "source_provider",
        "source_type",
        "local",
        "local_path",
        "source_record",
        "api_endpoint",
        "coverage",
        "expected_volume_count",
        "discovered_volume_page_count",
        "retrieved_volume_count",
        "retrieval_date",
        "status",
        "text_authority",
        "structure_authority",
    )
    lines: list[str] = []
    for key in scalar_keys:
        if key not in data:
            continue
        value = data[key]
        if isinstance(value, bool):
            rendered = "true" if value else "false"
        elif value is None:
            rendered = "null"
        elif isinstance(value, int):
            rendered = str(value)
        else:
            rendered = json.dumps(str(value), ensure_ascii=False)
        lines.append(f"{key}: {rendered}")
    lines.append("volume_page_titles:")
    for number, title in sorted(data.get("volume_page_titles", {}).items(), key=lambda item: int(item[0])):
        lines.append(f"  - volume: {int(number)}")
        lines.append(f"    page_title: {json.dumps(str(title), ensure_ascii=False)}")
    lines.append("missing_volumes:")
    for number in data.get("missing_volumes", []):
        lines.append(f"  - {int(number)}")
    lines.append("notes:")
    for note in data.get("notes", []):
        lines.append(f"  - {json.dumps(str(note), ensure_ascii=False)}")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    temporary.replace(path)


def run_jinshu_wikisource(
    root: Path,
    *,
    timeout: float = 120.0,
    discovery_fetcher: Callable[[], tuple[bytes, Mapping[str, Any]]] | None = None,
    batch_fetcher: Callable[
        [Sequence[str]], tuple[list[WikisourceRevision], bytes, str]
    ] | None = None,
) -> tuple[Path, dict[str, Any]]:
    """Retrieve the 130 Wikisource 四庫全書本 volume pages through the API."""

    destination_root = root / JINSHU_WIKISOURCE_ROOT
    raw_root = destination_root / "raw"
    text_root = destination_root / "text"
    lock_path = destination_root / "manifest.lock.json"
    volume_titles = jinshu_wikisource_volume_titles()
    errors: list[dict[str, Any]] = []
    records: list[dict[str, Any]] = []
    auxiliary_files: list[dict[str, Any]] = []

    discovery_url = jinshu_wikisource_discovery_url()
    try:
        if discovery_fetcher is None:
            discovery_bytes, discovery_payload = _fetch_wikisource_json_bytes(
                discovery_url, timeout=timeout, opener=urlopen
            )
        else:
            discovery_bytes, discovery_payload = discovery_fetcher()
        discovery = parse_jinshu_wikisource_discovery(discovery_payload)
        discovery_path = raw_root / "discovery-allpages.json"
        status, size, digest = _write_bytes_without_overwrite(discovery_path, discovery_bytes)
        auxiliary_files.append(
            {
                "kind": "api-discovery",
                "path": discovery_path.relative_to(root).as_posix(),
                "size": size,
                "sha256": digest,
                "status": status,
                "source_url": discovery_url,
            }
        )
    except Exception as error:
        discovery = {
            "page_titles": [],
            "volume_titles": {},
            "discovered_volumes": [],
            "duplicate_volumes": [],
            "unexpected_pages": [],
        }
        errors.append(
            {
                "kind": "discovery",
                "reason": f"{type(error).__name__}: {error}",
            }
        )

    discovered_volumes = set(discovery["discovered_volumes"])
    expected_subpages = set(range(2, JINSHU_WIKISOURCE_VOLUME_COUNT + 1))
    missing_discovered = sorted(expected_subpages - discovered_volumes)
    if discovery["duplicate_volumes"]:
        errors.append(
            {
                "kind": "discovery",
                "reason": f"duplicate volume page numbers: {discovery['duplicate_volumes']}",
            }
        )
    if missing_discovered:
        errors.append(
            {
                "kind": "discovery",
                "reason": f"missing volume page numbers: {missing_discovered}",
            }
        )

    all_titles = [volume_titles[number] for number in sorted(volume_titles)]
    if batch_fetcher is None:
        batch_fetcher = lambda titles: fetch_wikisource_revisions_with_raw(
            titles, timeout=timeout
        )
    seen_volumes: set[int] = set()
    for batch_number, offset in enumerate(
        range(0, len(all_titles), JINSHU_WIKISOURCE_BATCH_SIZE), start=1
    ):
        titles = all_titles[offset : offset + JINSHU_WIKISOURCE_BATCH_SIZE]
        raw_path = raw_root / f"batch-{batch_number:03d}.json"
        try:
            revisions, raw_bytes, api_url = batch_fetcher(titles)
            raw_status, raw_size, raw_digest = _write_bytes_without_overwrite(
                raw_path, raw_bytes
            )
            auxiliary_files.append(
                {
                    "kind": "api-revision-batch",
                    "path": raw_path.relative_to(root).as_posix(),
                    "size": raw_size,
                    "sha256": raw_digest,
                    "status": raw_status,
                    "source_url": api_url,
                    "page_titles": list(titles),
                }
            )
            by_title = {revision.page_title: revision for revision in revisions}
            for number, title in sorted(volume_titles.items()):
                if title not in titles:
                    continue
                revision = by_title.get(title)
                if revision is None:
                    raise WitnessDownloadError(
                        f"Wikisource batch response omitted page: {title}"
                    )
                if number in seen_volumes:
                    raise WitnessDownloadError(f"duplicate fetched volume: {number}")
                if not revision.content:
                    raise WitnessDownloadError(f"empty Wikisource source page: {title}")
                if number == 1 and not re.search(r"晉書[卷巻]一", revision.content):
                    raise WitnessDownloadError(
                        "the base Wikisource page does not contain the volume-one heading"
                    )
                text_path = text_root / f"volume-{number:03d}.txt"
                text_status, text_size, text_digest = _write_bytes_without_overwrite(
                    text_path, revision.content.encode("utf-8")
                )
                retrieved_at = _timestamp()
                records.append(
                    {
                        "witness_id": JINSHU_WIKISOURCE_WITNESS_ID,
                        "volume": number,
                        "page_title": revision.page_title,
                        "source_url": revision.source_url,
                        "api_url": revision.api_url,
                        "page_id": revision.page_id,
                        "revision_id": revision.revision_id,
                        "parent_revision_id": revision.parent_revision_id,
                        "revision_timestamp": revision.timestamp,
                        "raw_api_path": raw_path.relative_to(root).as_posix(),
                        "raw_api_size": raw_size,
                        "raw_api_sha256": raw_digest,
                        "text_path": text_path.relative_to(root).as_posix(),
                        "text_size": text_size,
                        "text_sha256": text_digest,
                        "retrieved_at": retrieved_at,
                        "retrieval_date": retrieved_at[:10],
                        "status": text_status,
                        "files": [
                            {
                                "kind": "source-text",
                                "path": text_path.relative_to(root).as_posix(),
                                "size": text_size,
                                "sha256": text_digest,
                                "status": text_status,
                            }
                        ],
                        "text_authority": "same-edition machine completion/reference; not a replacement for Kanripo",
                    }
                )
                seen_volumes.add(number)
        except Exception as error:
            errors.append(
                {
                    "kind": "volume-batch",
                    "page_titles": list(titles),
                    "reason": f"{type(error).__name__}: {error}",
                }
            )

    missing_fetched = sorted(set(volume_titles) - seen_volumes)
    if missing_fetched:
        errors.append(
            {
                "kind": "retrieval",
                "reason": f"volume source pages not retrieved: {missing_fetched}",
            }
        )
    records.sort(key=lambda record: int(record["volume"]))
    status = "complete" if len(records) == JINSHU_WIKISOURCE_VOLUME_COUNT and not errors else "incomplete"
    manifest: dict[str, Any] = {
        "schema": 1,
        "witness_id": JINSHU_WIKISOURCE_WITNESS_ID,
        "source_record": JINSHU_WIKISOURCE_SOURCE_RECORD,
        "api_endpoint": WIKISOURCE_API_ENDPOINT,
        "base_title": JINSHU_WIKISOURCE_BASE_TITLE,
        "coverage": "1-130",
        "expected_volume_count": JINSHU_WIKISOURCE_VOLUME_COUNT,
        "retrieved_volume_count": len(records),
        "discovered_volume_page_count": len(discovered_volumes),
        "discovery_page_titles": discovery["page_titles"],
        "discovery_unexpected_pages": discovery["unexpected_pages"],
        "missing_volumes": missing_fetched,
        "duplicate_volumes": discovery["duplicate_volumes"],
        "retrieved_at": _timestamp(),
        "status": status,
        "records": records,
        "auxiliary_files": auxiliary_files,
        "errors": errors,
        "notes": [
            "Volume one is the base page 晉書 (四庫全書本); volume pages two through 130 use zero-padded /卷NNN titles discovered through the MediaWiki API.",
            "Raw API JSON responses and returned UTF-8 source text are retained without markup normalization or textual correction.",
            "This witness completes source coverage for comparison and does not overwrite the partial Kanripo machine witness.",
        ],
    }
    _write_json(lock_path, manifest)
    metadata = {
        "schema": 1,
        "id": JINSHU_WIKISOURCE_WITNESS_ID,
        "work": "晉書",
        "role": "same-edition-machine-completion",
        "edition": "欽定四庫全書本",
        "source_provider": "Wikisource",
        "source_type": "MediaWiki-wikitext",
        "local": True,
        "local_path": JINSHU_WIKISOURCE_ROOT,
        "source_record": JINSHU_WIKISOURCE_SOURCE_RECORD,
        "api_endpoint": WIKISOURCE_API_ENDPOINT,
        "coverage": "1-130",
        "expected_volume_count": JINSHU_WIKISOURCE_VOLUME_COUNT,
        "discovered_volume_page_count": len(discovered_volumes),
        "retrieved_volume_count": len(records),
        "retrieval_date": manifest["retrieved_at"][:10],
        "status": status,
        "volume_page_titles": {str(number): title for number, title in volume_titles.items()},
        "missing_volumes": missing_fetched,
        "text_authority": "same-edition machine completion/reference; not a replacement for Kanripo",
        "structure_authority": "MediaWiki page titles and explicit source volume headings",
        "notes": manifest["notes"],
    }
    _write_jinshu_wikisource_metadata(destination_root / "metadata.yaml", metadata)
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


def _resolve_download_roots(root: Path, config_path: Path) -> tuple[Path, Path, Path, Path, Path, Path]:
    config = _load_yaml(config_path)
    shishuo_wikisource = root / _config_value(config, "shishuo_wikisource")
    shishuo_ling = root / _config_value(config, "shishuo_ling")
    jinshu = root / _config_value(config, "jinshu_jiaozhu")
    sanguozhi = root / _config_value(config, "sanguozhi_song")
    sanguozhi_wikisource = root / _config_value(config, "sanguozhi_wikisource")
    jinshu_wikisource = root / _config_value(config, "jinshu_wikisource_siku")
    expected_shishuo_wikisource = root / "sources/downloads/shishuo/wikisource-sbck"
    expected_shishuo_ling = root / "sources/downloads/shishuo/ling-1615"
    expected_jinshu = root / "sources/downloads/jinshu/jinshu-jiaozhu"
    expected_sanguozhi = root / "sources/downloads/sanguozhi/song-edition"
    expected_sanguozhi_wikisource = root / SANGUOZHI_WIKISOURCE_ROOT
    expected_jinshu_wikisource = root / JINSHU_WIKISOURCE_ROOT
    if (
        shishuo_wikisource != expected_shishuo_wikisource
        or shishuo_ling != expected_shishuo_ling
        or jinshu != expected_jinshu
        or sanguozhi != expected_sanguozhi
        or sanguozhi_wikisource != expected_sanguozhi_wikisource
        or jinshu_wikisource != expected_jinshu_wikisource
    ):
        raise WitnessDownloadError(
            "download roots in config/sources.yaml do not match the registered witness layout"
        )
    return (
        jinshu,
        sanguozhi,
        sanguozhi_wikisource,
        shishuo_wikisource,
        shishuo_ling,
        jinshu_wikisource,
    )


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
            # Wikisource completion manifests keep source/API payloads as
            # explicit path/hash fields on each juan record rather than in a
            # nested ``files`` list.  Verify those fields too.
            for path_key, size_key, hash_key in (
                ("source_path", "source_size", "source_sha256"),
                ("text_path", "text_size", "text_sha256"),
                ("raw_api_path", "raw_api_size", "raw_api_sha256"),
            ):
                if not record.get(path_key):
                    continue
                inline_record = {
                    "path": record[path_key],
                    "size": record.get(size_key),
                    "sha256": record.get(hash_key),
                    "status": record.get("status", "downloaded"),
                }
                errors.extend(_verify_file_record(root, inline_record))
    for file_record in manifest.get("auxiliary_files", []):
        if isinstance(file_record, Mapping):
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


def _print_sanguozhi_wikisource_list() -> None:
    print("Sanguozhi Wikisource complete machine witness")
    print(
        "  pages: "
        + ", ".join(sanguozhi_wikisource_volume_titles().values())
    )
    for global_juan in (1, 31, 46, 65):
        section, section_juan = sanguozhi_section_for_juan(global_juan)
        print(f"  juan {global_juan:02d}: {section} 卷{section_juan}")


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
    modes.add_argument("--shishuo-jianshu", action="store_true", help="retrieve 余嘉錫《箋疏》 through the official CText gettext API")
    modes.add_argument("--shishuo", action="store_true", help="download registered downloadable Shishuo witnesses")
    modes.add_argument("--jinshu-jiaozhu", action="store_true", help="discover and download the Jinshu 斠注 series")
    modes.add_argument("--jinshu-wikisource-siku", action="store_true", help="download the Jinshu 四庫全書本 completion from Wikisource's MediaWiki API")
    modes.add_argument("--sanguozhi-wikisource", action="store_true", help="download the complete 65-juan Sanguozhi machine witness from Wikisource")
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
        (
            jinshu_root,
            sanguozhi_root,
            sanguozhi_wikisource_root,
            shishuo_wikisource_root,
            shishuo_ling_root,
            jinshu_wikisource_root,
        ) = _resolve_download_roots(root, config)
        if args.list:
            _print_shishuo_list(discover_shishuo_ling())
            _print_jinshu_list(discover_jinshu())
            _print_sanguozhi_list(discover_sanguozhi(include_archival=False))
            _print_sanguozhi_wikisource_list()
            return 0
        if args.verify:
            errors = verify_lock_manifest(root, shishuo_wikisource_root / "manifest.lock.json")
            errors.extend(verify_lock_manifest(root, shishuo_ling_root / "manifest.lock.json"))
            errors.extend(verify_lock_manifest(root, jinshu_root / "manifest.lock.json"))
            errors.extend(verify_lock_manifest(root, sanguozhi_root / "manifest.lock.json"))
            errors.extend(
                verify_lock_manifest(root, sanguozhi_wikisource_root / "manifest.lock.json")
            )
            if (jinshu_wikisource_root / "manifest.lock.json").exists():
                errors.extend(
                    verify_lock_manifest(root, jinshu_wikisource_root / "manifest.lock.json")
                )
            ctext_lock = root / CTEXT_JIANSHU_ROOT / "manifest.lock.json"
            if ctext_lock.exists():
                errors.extend(verify_ctext_lock_manifest(root, ctext_lock))
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
        if args.shishuo_jianshu:
            ctext_lock, ctext_manifest = run_shishuo_jianshu(
                root, timeout=args.timeout
            )
            if ctext_lock is None:
                for error in ctext_manifest.get("errors", []):
                    print(
                        f"CText retrieval not completed: {error.get('code')}: "
                        f"{error.get('description')}",
                        file=sys.stderr,
                    )
                return 1
            results.append((ctext_lock, {}))
        if args.jinshu_jiaozhu or args.all:
            results.append((run_jinshu(root, timeout=args.timeout)[0], {}))
        if args.jinshu_wikisource_siku or args.all:
            results.append((run_jinshu_wikisource(root, timeout=args.timeout)[0], {}))
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
        if args.sanguozhi_wikisource or args.all:
            results.append(
                (
                    run_sanguozhi_wikisource(root, timeout=args.timeout)[0],
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
