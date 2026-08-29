"""Small deterministic utilities shared by the SFH2 projection."""

from __future__ import annotations

import datetime as _datetime
import hashlib
import json
import os
import re
from pathlib import Path
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parents[2]
SFH1_ROOT = ROOT / "data/generated/sfh1"
OUTPUT_ROOT = ROOT / "data/generated/sfh2"
LIVE_ROOT = OUTPUT_ROOT / "live"
MODEL = "deepseek-v4-flash"
RUN_VERSION = "sfh2-hir1-v1"
SCHEMA_VERSION = "sfh2-hir1-v1"

VARIANT_TRANSLATION = str.maketrans({
    "爲": "為", "髙": "高", "鳯": "鳳", "臺": "台", "台": "台",
    "裏": "裡", "𪟝": "懿",
})

INPUT_FILES = (
    "data/generated/sfh1/story-packets.json",
    "data/generated/sfh1/validated-mentions.json",
    "data/generated/sfh1/reference-semantics.json",
    "data/generated/sfh1/candidate-sets.json",
    "data/generated/sfh1/identity-judgments.json",
    "data/generated/sfh1/constrained-decisions.json",
    "data/generated/sfh1/final-decisions.json",
    "data/generated/sfh1/relation-assertions.json",
    "data/generated/sfh1/temporal-semantics.json",
    "data/people.json",
    "data/aliases.json",
    "data/derived/hdb2-f-person-knowledge.json",
    "data/derived/hdb2-f-candidate-person-knowledge.json",
    "data/derived/hdb2-f-profile-integrity-audit.json",
    "data/generated/hda2/repair-overlay.json",
    "data/generated/sfh1/hge1-recalibrated-growth-series.json",
)


def read_json(path: Path, default: Any = None) -> Any:
    if not path.is_file():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def stable_hash(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def text(value: Any) -> str:
    return str(value or "").strip()


def normalize_form(value: Any) -> str:
    return re.sub(r"\s+", "", text(value)).translate(VARIANT_TRANSLATION)


def relative(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return str(path)


def utc_now() -> str:
    return _datetime.datetime.now(_datetime.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def flags(value: Mapping[str, Any] | None = None) -> dict[str, Any]:
    result = dict(value or {})
    result.setdefault("candidate_only", True)
    result.setdefault("canonical_write_back", False)
    return result


def sorted_unique(values: Any) -> list[str]:
    if not isinstance(values, (list, tuple, set)):
        return []
    return sorted({text(value) for value in values if text(value)})


def compact_text(value: Any, limit: int = 900) -> str:
    result = text(value)
    if len(result) <= limit:
        return result
    return result[: max(0, limit - 1)] + "…"


def as_records(document: Any, *keys: str) -> list[dict[str, Any]]:
    if not isinstance(document, Mapping):
        return []
    for key in keys:
        value = document.get(key)
        if isinstance(value, list):
            return [dict(item) for item in value if isinstance(item, Mapping)]
    return []
