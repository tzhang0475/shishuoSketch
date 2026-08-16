#!/usr/bin/env python3
"""Shared, deterministic helpers for S1's local Jianshu integration.

The local EPUB/PDF pair is a scholarly-reference family.  This module keeps
source discovery, hashing, EPUB structure parsing, and ignored-cache paths in
one place so the registration, ingestion, alignment, extraction, and review
stages cannot silently disagree about the input payloads.
"""

from __future__ import annotations

from collections import Counter
from html.parser import HTMLParser
import hashlib
import json
from pathlib import Path
import re
import subprocess
from typing import Any, Iterable, Mapping
import unicodedata
from zipfile import ZipFile
import xml.etree.ElementTree as ET


ROOT = Path(__file__).resolve().parents[1]
DOWNLOAD_ROOT = Path("sources/downloads/shishuo")
EPUB_SOURCE_DIR = DOWNLOAD_ROOT / "ssjx-2016-epub-transcription"
PDF_SOURCE_DIR = DOWNLOAD_ROOT / "ssjx-yujiaxi-2009-digital-pdf"
CACHE_ROOT = Path(".cache/shishuo-reference/jianshu")

EPUB_ID = "shishuo-jianshu-yujiaxi-local-epub"
PDF_ID = "shishuo-jianshu-yujiaxi-local-pdf"
SOURCE_FAMILY = "shishuo-jianshu-yujiaxi-local"

STRUCTURE_AUDIT_PATH = Path("data/derived/s1-jianshu-structure-audit.json")
GLYPH_AUDIT_PATH = Path("data/derived/s1-jianshu-glyph-audit.json")
REGISTRATION_PATH = Path("data/derived/s1-jianshu-source-registration.json")
ALIGNMENT_PATH = Path("data/derived/s1-jianshu-story-alignment.json")
PRIMARY_WITNESS_LOCK_PATH = Path("sources/registry/shishuo-provenance.lock.json")

CORPUS_INDEX_PATH = Path("data/shishuo-corpus-index.json")
SC1_PATH = Path("data/derived/sc1-site.json")
X1_SELECTION_PATH = Path("data/derived/x1-1-selection-manifest.json")
X1_2A_REVIEW_MANIFEST_PATH = Path("data/derived/x1-2a-review-manifest.json")
X1_2A_STORY_REVIEW_PATH = Path("data/derived/x1-2a-story-review.json")
X1_2A_FACT_REVIEW_PATH = Path("data/derived/x1-2a-fact-review.json")
X1_2A_PERSON_REVIEW_PATH = Path("data/derived/x1-2a-person-review.json")
X1_2A_ONTOLOGY_REVIEW_PATH = Path("data/derived/x1-2a-ontology-gap-review.json")
X1_2P_PATHS = tuple(sorted(Path("data/derived").glob("x1-2p-*.json")))

FULLWIDTH_DIGITS = str.maketrans("０１２３４５６７８９", "0123456789")
CHINESE_DIGITS = {
    "零": 0,
    "〇": 0,
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
CHINESE_UNITS = {"十": 10, "百": 100}

ATTRIBUTION_ALIASES = (
    ("嘉錫", "余嘉錫"),
    ("嘉锡", "余嘉锡"),
    ("程炎震", "程炎震"),
    ("李慈銘", "李慈銘"),
    ("李慈铭", "李慈铭"),
    ("李詳", "李詳"),
    ("李详", "李详"),
    ("張文檒", "張文檒"),
    ("张文檒", "张文檒"),
    ("劉盼遂", "劉盼遂"),
    ("刘盼遂", "刘盼遂"),
    ("周亮工", "周亮工"),
    ("葉夢得", "葉夢得"),
    ("葉梦得", "葉梦得"),
    ("翟灝", "翟灝"),
    ("翟灏", "翟灏"),
)


def read_json(relative: Path) -> Any:
    return json.loads((ROOT / relative).read_text(encoding="utf-8"))


def write_json(relative: Path, value: Any) -> None:
    path = ROOT / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def write_jsonl(relative: Path, values: Iterable[Mapping[str, Any]]) -> None:
    path = ROOT / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for value in values:
            handle.write(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
            handle.write("\n")


def sha256_path(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_file(relative: Path) -> str:
    return sha256_path(ROOT / relative)


def hash_value(value: Any) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def stable_id(prefix: str, *parts: object, length: int = 20) -> str:
    raw = "|".join(str(part) for part in parts)
    return f"{prefix}-{hashlib.sha256(raw.encode('utf-8')).hexdigest()[:length]}"


def relative_path(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


class SourceDiscoveryError(RuntimeError):
    pass


def _discover_one(directory: Path, suffix: str) -> Path:
    directory = ROOT / directory
    candidates = sorted((path for path in directory.glob(f"*{suffix}") if path.is_file()), key=lambda p: p.name)
    if len(candidates) != 1:
        names = [relative_path(path) for path in candidates]
        raise SourceDiscoveryError(
            f"expected exactly one {suffix} in {relative_path(directory)}, found {len(candidates)}: {names}"
        )
    return candidates[0]


def discover_payloads() -> dict[str, Path]:
    """Discover the intended user-provided Jianshu pair, never by filename guess."""

    return {
        "epub": _discover_one(EPUB_SOURCE_DIR, ".epub"),
        "pdf": _discover_one(PDF_SOURCE_DIR, ".pdf"),
    }


def local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def parse_xml(path_or_bytes: Path | bytes) -> ET.Element:
    if isinstance(path_or_bytes, Path):
        return ET.fromstring(path_or_bytes.read_bytes())
    return ET.fromstring(path_or_bytes)


def epub_layout(epub_path: Path) -> dict[str, Any]:
    with ZipFile(epub_path) as archive:
        names = archive.namelist()
        if "mimetype" not in names:
            raise SourceDiscoveryError("EPUB has no mimetype member")
        container = parse_xml(archive.read("META-INF/container.xml"))
        rootfiles = [
            element.attrib.get("full-path")
            for element in container.iter()
            if local_name(element.tag) == "rootfile" and element.attrib.get("full-path")
        ]
        if len(rootfiles) != 1:
            raise SourceDiscoveryError(f"EPUB rootfile count is {len(rootfiles)}, expected one")
        opf_name = rootfiles[0]
        opf = parse_xml(archive.read(opf_name))
        manifest: dict[str, dict[str, str]] = {}
        for item in opf.iter():
            if local_name(item.tag) == "item" and item.attrib.get("id"):
                manifest[item.attrib["id"]] = {
                    "href": item.attrib.get("href", ""),
                    "media_type": item.attrib.get("media-type", ""),
                    "properties": item.attrib.get("properties", ""),
                }
        spine: list[dict[str, Any]] = []
        for index, itemref in enumerate(element for element in opf.iter() if local_name(element.tag) == "itemref"):
            idref = itemref.attrib.get("idref", "")
            item = manifest.get(idref, {})
            href = item.get("href", "")
            full_path = str((Path(opf_name).parent / href).as_posix())
            spine.append(
                {
                    "spine_index": index,
                    "idref": idref,
                    "href": href,
                    "path": full_path,
                    "media_type": item.get("media_type", ""),
                    "properties": item.get("properties", ""),
                }
            )
        metadata: dict[str, list[str]] = {}
        for element in opf.iter():
            tag = local_name(element.tag)
            if tag in {"title", "creator", "date", "publisher", "language", "identifier"}:
                value = " ".join((element.text or "").split())
                if value:
                    metadata.setdefault(tag, []).append(value)
        return {
            "container_rootfile": opf_name,
            "manifest_count": len(manifest),
            "spine": spine,
            "spine_document_count": sum(row["media_type"] == "application/xhtml+xml" for row in spine),
            "metadata": metadata,
            "zip_member_count": len(names),
            "zip_members": sorted(names),
        }


def pdf_metadata(pdf_path: Path) -> dict[str, Any]:
    result: dict[str, Any] = {"page_count": None, "page_count_method": None, "has_text_layer": None}
    try:
        info = subprocess.run(
            ["pdfinfo", str(pdf_path)], capture_output=True, text=True, timeout=30, check=False
        )
        match = re.search(r"^Pages:\s*(\d+)\s*$", info.stdout, flags=re.MULTILINE)
        if match:
            result["page_count"] = int(match.group(1))
            result["page_count_method"] = "pdfinfo"
    except (FileNotFoundError, subprocess.SubprocessError):
        pass
    if result["page_count"] is None:
        raw = pdf_path.read_bytes()
        result["page_count"] = len(re.findall(rb"/Type\s*/Page(?:\s|/|>)", raw)) or None
        result["page_count_method"] = "pdf_page_object_fallback" if result["page_count"] else None
    try:
        text = subprocess.run(
            ["pdftotext", "-f", "1", "-l", "1", "-layout", str(pdf_path), "-"],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        result["has_text_layer"] = bool(text.stdout.strip())
        result["text_layer_probe"] = "pdftotext_first_page"
    except (FileNotFoundError, subprocess.SubprocessError):
        result["has_text_layer"] = None
        result["text_layer_probe"] = "unavailable"
    return result


class ParagraphParser(HTMLParser):
    """Small HTML parser for the predictable XHTML paragraph structure."""

    BLOCK_TAGS = {"p", "h1", "h2", "h3", "h4", "h5", "h6", "li", "td"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.blocks: list[dict[str, Any]] = []
        self.current: dict[str, Any] | None = None
        self.depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in self.BLOCK_TAGS and self.current is None:
            self.current = {"tag": tag, "attrs": dict(attrs), "parts": []}
            self.depth = 1
        elif self.current is not None:
            self.depth += 1
            if tag == "br":
                self.current["parts"].append("\n")

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if self.current is not None and tag == "br":
            self.current["parts"].append("\n")

    def handle_endtag(self, tag: str) -> None:
        if self.current is None:
            return
        self.depth -= 1
        if self.depth <= 0:
            text = normalize_source_text("".join(self.current["parts"]))
            self.blocks.append({"tag": self.current["tag"], "attrs": self.current["attrs"], "text": text})
            self.current = None
            self.depth = 0

    def handle_data(self, data: str) -> None:
        if self.current is not None:
            self.current["parts"].append(data)


def normalize_source_text(value: str) -> str:
    # NFC is safe for canonically equivalent sequences; no script conversion,
    # punctuation rewriting, rare-glyph replacement, or emendation occurs.
    value = unicodedata.normalize("NFC", value)
    return re.sub(r"\s+", " ", value).strip()


def parse_xhtml_blocks(raw: bytes) -> list[dict[str, Any]]:
    parser = ParagraphParser()
    parser.feed(raw.decode("utf-8", errors="replace"))
    parser.close()
    return parser.blocks


def chinese_number(value: str) -> int | None:
    value = value.strip()
    if not value:
        return None
    if value.isdigit():
        return int(value)
    if len(value) == 1 and value in CHINESE_DIGITS:
        return CHINESE_DIGITS[value]
    total = 0
    current = 0
    for char in value:
        if char in CHINESE_DIGITS:
            current = CHINESE_DIGITS[char]
        elif char in CHINESE_UNITS:
            unit = CHINESE_UNITS[char]
            total += (current or 1) * unit
            current = 0
        else:
            return None
    return total + current


def leading_ordinal(text: str) -> int | None:
    match = re.match(r"^([0-9０１２３４５６７８９]+)", text)
    if not match:
        return None
    return int(match.group(1).translate(FULLWIDTH_DIGITS))


def category_number(text: str) -> int | None:
    compact = re.sub(r"\s+", "", text)
    match = re.search(r"第([零〇一二三四五六七八九十百0-9０１２３４５６７８９]+)", compact)
    if not match:
        return None
    return chinese_number(match.group(1).translate(FULLWIDTH_DIGITS))


def classify_attribution(text: str) -> str | None:
    for surface, canonical in ATTRIBUTION_ALIASES:
        if surface in text:
            return canonical
    return None


def normalize_identifier_text(text: str) -> str:
    text = unicodedata.normalize("NFC", text).translate(FULLWIDTH_DIGITS)
    text = re.sub(r"[\s\u3000\u200b]+", "", text)
    return text


def source_file_hashes() -> dict[str, str]:
    payloads = discover_payloads()
    return {kind: sha256_path(path) for kind, path in payloads.items()}


def primary_witness_snapshot() -> dict[str, Any]:
    """Verify the existing Kanripo payload against its committed provenance lock."""

    lock_path = ROOT / PRIMARY_WITNESS_LOCK_PATH
    lock = json.loads(lock_path.read_text(encoding="utf-8"))
    files: list[dict[str, Any]] = []
    for record in lock.get("files", []):
        path = Path(str(record["path"]))
        absolute = ROOT / path
        actual = sha256_path(absolute) if absolute.exists() else None
        files.append(
            {
                "path": path.as_posix(),
                "expected_size": record.get("size"),
                "expected_sha256": record.get("sha256"),
                "available": absolute.exists(),
                "actual_size": absolute.stat().st_size if absolute.exists() else None,
                "actual_sha256": actual,
                "unchanged": actual == record.get("sha256") if actual is not None else None,
            }
        )
    available = all(row["available"] for row in files)
    unchanged = available and all(row["unchanged"] for row in files)
    return {
        "witness_id": lock.get("witness_id"),
        "lock_path": PRIMARY_WITNESS_LOCK_PATH.as_posix(),
        "lock_sha256": sha256_file(PRIMARY_WITNESS_LOCK_PATH),
        "status": "verified" if unchanged else ("unavailable" if not available else "mismatch"),
        "files": files,
    }


def protected_s1_input_hashes() -> dict[str, str]:
    paths: list[Path] = [
        X1_SELECTION_PATH,
        X1_2A_REVIEW_MANIFEST_PATH,
        X1_2A_STORY_REVIEW_PATH,
        X1_2A_FACT_REVIEW_PATH,
        X1_2A_PERSON_REVIEW_PATH,
        X1_2A_ONTOLOGY_REVIEW_PATH,
        Path("data/people.json"),
        Path("data/aliases.json"),
        Path("data/mentions/shishuo.json"),
        Path("data/derived/person-story-index.json"),
        Path("data/shishuo-corpus-index.json"),
        PRIMARY_WITNESS_LOCK_PATH,
    ]
    paths.extend(X1_2P_PATHS)
    # These are downstream protected truth/audit layers.  S1 may consume them
    # but must not silently rewrite them while adding the scholarly reference.
    for pattern in ("data/derived/h0c-*.json", "data/derived/hg0-*.json", "data/derived/ml0-*.json"):
        paths.extend(Path(path.relative_to(ROOT)) for path in ROOT.glob(pattern) if path.is_file())
    return {path.as_posix(): sha256_file(path) for path in sorted(set(paths), key=lambda p: p.as_posix()) if (ROOT / path).exists()}


def load_story_records() -> list[dict[str, Any]]:
    path = ROOT / CACHE_ROOT / "story-records.jsonl"
    if not path.exists():
        raise FileNotFoundError(f"Jianshu story cache is missing: {relative_path(path)}")
    records: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            records.append(json.loads(line))
    return records


def load_story_selection() -> list[dict[str, Any]]:
    document = read_json(X1_SELECTION_PATH)
    return sorted((dict(row) for row in document.get("records", [])), key=lambda row: row.get("global_selection_rank", 0))


def selected_story_ids() -> list[str]:
    return [str(row["story_id"]) for row in load_story_selection()]


def x1_selection_by_story() -> dict[str, dict[str, Any]]:
    return {str(row["story_id"]): row for row in load_story_selection()}


def json_hash(relative: Path) -> str:
    return sha256_file(relative)


def counter_snapshot(values: Iterable[str]) -> dict[str, int]:
    return dict(sorted(Counter(values).items()))
