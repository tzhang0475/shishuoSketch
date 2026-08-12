#!/usr/bin/env python3
"""Build a conservative Mention -> Alias -> Person pilot for six people.

This script reads only the already materialized Shishuo entries and Jinshu
units.  It never writes to either source tree.  Exact names and source-backed
courtesy names resolve directly; contextual titles are resolved only when a
strong identity cue occurs in the same rendered section.  Otherwise the
mention remains unresolved.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
import argparse
import json
from pathlib import Path
import re
from typing import Any, Iterable, Mapping, Sequence


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
SHISHUO_ENTRIES = REPOSITORY_ROOT / "content/processed/shishuo/entries"
JINSHU_UNITS = REPOSITORY_ROOT / "content/processed/jinshu/units"
PEOPLE_PATH = REPOSITORY_ROOT / "data/people.json"
ALIASES_PATH = REPOSITORY_ROOT / "data/aliases.json"
SHISHUO_MENTIONS_PATH = REPOSITORY_ROOT / "data/mentions/shishuo.json"
JINSHU_MENTIONS_PATH = REPOSITORY_ROOT / "data/mentions/jinshu.json"
REPORT_PATH = REPOSITORY_ROOT / "content/curated/entities/six-person-pilot.md"

PERSON_DEFINITIONS: tuple[dict[str, Any], ...] = (
    {"person_id": "wang-xizhi", "canonical_name": "王羲之"},
    {"person_id": "xi-jian", "canonical_name": "郗鑒"},
    {"person_id": "wang-dao", "canonical_name": "王導"},
    {"person_id": "wang-ningzhi", "canonical_name": "王凝之"},
    {"person_id": "xie-daoyun", "canonical_name": "謝道韞"},
    {"person_id": "xie-an", "canonical_name": "謝安"},
)
PERSON_IDS = frozenset(item["person_id"] for item in PERSON_DEFINITIONS)


@dataclass(frozen=True)
class AliasSpec:
    alias_id: str
    surface: str
    alias_type: str
    candidate_person_ids: tuple[str, ...]
    resolution_mode: str
    resolution_method: str
    direct_person_id: str | None = None
    scan_policy: str = "all"
    suppress_if_contained: bool = False


ALIAS_SPECS: tuple[AliasSpec, ...] = (
    # Direct names and source-backed personal/courtesy spellings.
    AliasSpec("wang-xizhi-name", "王羲之", "personal_name", ("wang-xizhi",), "exact", "exact_person_name", "wang-xizhi"),
    AliasSpec("wang-xizhi-wang-yishao", "王逸少", "courtesy_name", ("wang-xizhi",), "exact", "exact_courtesy_name", "wang-xizhi"),
    AliasSpec("wang-xizhi-wang-youjun", "王右軍", "office_title", ("wang-xizhi",), "contextual", "contextual_title", scan_policy="contextual"),
    AliasSpec("wang-xizhi-yishao", "逸少", "courtesy_name", ("wang-xizhi",), "exact", "exact_courtesy_name", "wang-xizhi", suppress_if_contained=True),
    AliasSpec("wang-xizhi-youjun", "右軍", "textual_shorthand", ("wang-xizhi",), "contextual", "contextual_title", scan_policy="contextual", suppress_if_contained=True),
    AliasSpec("xi-jian-name", "郗鑒", "personal_name", ("xi-jian",), "exact", "exact_person_name", "xi-jian"),
    AliasSpec("xi-jian-variant-name", "郄鑒", "orthographic_variant", ("xi-jian",), "exact", "orthographic_variant", "xi-jian"),
    AliasSpec("xi-jian-dao-hui", "道徽", "courtesy_name", ("xi-jian",), "exact", "exact_courtesy_name", "xi-jian", suppress_if_contained=True),
    AliasSpec("xi-jian-variant-dao-hui", "郄道徽", "orthographic_variant", ("xi-jian",), "exact", "orthographic_variant", "xi-jian"),
    AliasSpec("xi-jian-taifu", "郗太傅", "office_title", ("xi-jian",), "contextual", "contextual_title", scan_policy="contextual"),
    AliasSpec("xi-jian-gong", "郗公", "contextual_title", ("xi-jian",), "contextual", "contextual_title", scan_policy="contextual"),
    AliasSpec("wang-dao-name", "王導", "personal_name", ("wang-dao",), "exact", "exact_person_name", "wang-dao"),
    AliasSpec("wang-dao-wang-maohong", "王茂弘", "courtesy_name", ("wang-dao",), "exact", "exact_courtesy_name", "wang-dao"),
    AliasSpec("wang-dao-maohong", "茂弘", "courtesy_name", ("wang-dao",), "exact", "exact_courtesy_name", "wang-dao", suppress_if_contained=True),
    AliasSpec("wang-dao-chengxiang", "王丞相", "office_title", ("wang-dao",), "contextual", "contextual_title", scan_policy="contextual"),
    AliasSpec("wang-ningzhi-name", "王凝之", "personal_name", ("wang-ningzhi",), "exact", "exact_person_name", "wang-ningzhi"),
    AliasSpec("wang-ningzhi-shuping", "叔平", "courtesy_name", ("wang-ningzhi",), "exact", "annotation_context", "wang-ningzhi"),
    AliasSpec("xie-daoyun-courtesy", "道韞", "courtesy_name", ("xie-daoyun",), "exact", "exact_courtesy_name", "xie-daoyun"),
    AliasSpec("xie-daoyun-kinship-name", "王凝之妻謝氏", "kinship_reference", ("xie-daoyun",), "exact", "exact_kinship_reference", "xie-daoyun"),
    AliasSpec("xie-an-name", "謝安", "personal_name", ("xie-an",), "exact", "exact_person_name", "xie-an", suppress_if_contained=True),
    AliasSpec("xie-an-xie-anshi", "謝安石", "courtesy_name", ("xie-an",), "exact", "exact_courtesy_name", "xie-an"),
    AliasSpec("xie-an-anshi", "安石", "courtesy_name", ("xie-an",), "exact", "exact_courtesy_name", "xie-an", suppress_if_contained=True),
    AliasSpec("xie-an-taifu", "謝太傅", "office_title", ("xie-an",), "contextual", "contextual_title", scan_policy="contextual"),
    # Contextual and potentially shared forms.  These never resolve without
    # a strong identity cue in the same section/unit.
    AliasSpec("shared-wang-gong", "王公", "contextual_title", ("wang-dao", "wang-xizhi"), "ambiguous", "contextual_title", scan_policy="all"),
    AliasSpec("shared-xie-gong", "謝公", "contextual_title", ("xie-an",), "ambiguous", "contextual_title", scan_policy="all"),
    AliasSpec("generic-taifu", "太傅", "office_title", ("xie-an", "xi-jian"), "ambiguous", "contextual_title", scan_policy="contextual", suppress_if_contained=True),
    AliasSpec("generic-chengxiang", "丞相", "office_title", ("wang-dao",), "ambiguous", "contextual_title", scan_policy="contextual", suppress_if_contained=True),
)
SPEC_BY_SURFACE = {spec.surface: spec for spec in ALIAS_SPECS}
STRONG_BY_PERSON: dict[str, tuple[str, ...]] = {
    "wang-xizhi": ("王羲之", "王逸少", "逸少"),
    "xi-jian": ("郗鑒", "郄鑒", "郄道徽", "道徽"),
    "wang-dao": ("王導", "王茂弘", "茂弘"),
    "wang-ningzhi": ("王凝之", "叔平"),
    "xie-daoyun": ("道韞", "王凝之妻謝氏"),
    "xie-an": ("謝安", "謝安石", "安石"),
}
CONTEXT_SURFACES = frozenset(
    spec.surface for spec in ALIAS_SPECS if spec.scan_policy in {"contextual", "all"}
)
STRUCTURAL_CONTEXT_SURFACES = frozenset(
    {"王右軍", "右軍", "王丞相", "謝太傅", "謝公", "郗太傅", "郗公"}
)


def parse_scalar(raw: str) -> Any:
    value = raw.strip()
    if value.startswith('"') and value.endswith('"'):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return value[1:-1]
    if value in {"true", "false"}:
        return value == "true"
    if value == "null":
        return None
    if re.fullmatch(r"-?\d+", value):
        return int(value)
    return value


def parse_frontmatter(text: str) -> dict[str, Any]:
    if not text.startswith("---\n"):
        raise ValueError("Markdown has no YAML front matter")
    end = text.find("\n---\n", 4)
    if end < 0:
        raise ValueError("Markdown has no front matter terminator")
    header = text[4:end]
    values: dict[str, Any] = {}
    for line in header.splitlines():
        if not line or line[0].isspace() or ":" not in line:
            continue
        key, raw = line.split(":", 1)
        values[key.strip()] = parse_scalar(raw)
    # Some existing Shishuo files use a hand-written nested block whose
    # indentation is not valid YAML.  Parse that block line-by-line so the
    # start and end locations remain distinct and reproducible.
    active_edge: str | None = None
    for line in header.splitlines():
        edge_match = re.fullmatch(r"  (start|end):\s*", line)
        if edge_match:
            active_edge = edge_match.group(1)
            values[f"{active_edge}_location"] = {}
            continue
        nested_match = re.fullmatch(r"    ([A-Za-z_][A-Za-z0-9_]*):\s*(.*)", line)
        if nested_match and active_edge:
            key, raw = nested_match.groups()
            values[f"{active_edge}_location"][key] = parse_scalar(raw)
            continue
        if line and not line.startswith(" "):
            active_edge = None
    return values


def markdown_body(text: str) -> str:
    end = text.find("\n---\n", 4)
    if end < 0:
        raise ValueError("Markdown has no front matter terminator")
    body_start = end + len("\n---\n")
    return text[body_start:]


def parse_shishuo_sections(text: str) -> list[tuple[str, str, dict[str, Any]]]:
    """Return main text and exact annotation-block bodies."""

    body = markdown_body(text)
    marker = "## Main text\n\n"
    if marker not in body:
        return []
    after_main = body.split(marker, 1)[1]
    annotation_marker = "\n## Top-level parenthetical annotation blocks\n"
    main, separator, annotations = after_main.partition(annotation_marker)
    if not separator:
        main = main.split("\n## Kanripo page markers", 1)[0]
        return [("main_text", main, {})]
    sections: list[tuple[str, str, dict[str, Any]]] = [("main_text", main, {})]
    annotations = annotations.split("\n## Kanripo page markers", 1)[0]
    starts = list(re.finditer(r"(?m)^### (annotation-\d+)\n", annotations))
    for index, match in enumerate(starts):
        stop = starts[index + 1].start() if index + 1 < len(starts) else len(annotations)
        block = annotations[match.end() : stop].strip("\n")
        if "\n\n" not in block:
            continue
        metadata_text, annotation_body = block.split("\n\n", 1)
        metadata: dict[str, Any] = {"annotation_id": match.group(1)}
        for line in metadata_text.splitlines():
            if ":" in line:
                key, raw = line.split(":", 1)
                metadata[key.strip()] = parse_scalar(raw)
        sections.append(("liu_annotation", annotation_body.strip("\n"), metadata))
    return sections


def source_context(text: str, start: int, end: int, radius: int = 90) -> str:
    return text[max(0, start - radius) : min(len(text), end + radius)]


def mask_markup_comments(text: str) -> str:
    """Mask generated HTML comments without changing character offsets."""

    def replacement(match: re.Match[str]) -> str:
        return "".join("\n" if char == "\n" else " " for char in match.group(0))

    return re.sub(r"<!--.*?-->", replacement, text, flags=re.DOTALL)


def strong_hits(text: str, person_id: str) -> list[str]:
    return [surface for surface in STRONG_BY_PERSON[person_id] if surface in text]


def contextual_resolution(
    spec: AliasSpec,
    section_text: str,
    start: int,
    end: int,
    *,
    structural_identity: str | None = None,
) -> tuple[str | None, str, str, list[str]]:
    """Resolve only with strong same-section evidence."""

    # A title is evidence only in a nearby local context.  Searching an
    # entire biography would incorrectly attach titles used for unrelated
    # historical figures to the biography's subject.
    context_radius = 120
    local_text = section_text[max(0, start - context_radius) : min(len(section_text), end + context_radius)]
    hits: dict[str, list[str]] = {
        person_id: strong_hits(local_text, person_id)
        for person_id in spec.candidate_person_ids
    }
    if (
        structural_identity
        and spec.surface in STRUCTURAL_CONTEXT_SURFACES
        and len(spec.candidate_person_ids) == 1
    ):
        only_candidate = spec.candidate_person_ids[0]
        if structural_identity == only_candidate:
            hits[only_candidate].append("unit_heading")
    active = [person_id for person_id, values in hits.items() if values]
    if len(active) == 1:
        return active[0], "medium", "contextual_title", hits[active[0]]
    if len(active) > 1:
        return None, "unresolved", "contextual_title_ambiguous", [item for values in hits.values() for item in values]
    return None, "unresolved", "unresolved_contextual_title", []


def resolve_spec(
    spec: AliasSpec,
    section_text: str,
    start: int,
    end: int,
    *,
    structural_identity: str | None = None,
) -> tuple[str | None, str, str, list[str]]:
    if spec.direct_person_id is not None:
        return spec.direct_person_id, "high", spec.resolution_method, [spec.surface]
    return contextual_resolution(
        spec,
        section_text,
        start,
        end,
        structural_identity=structural_identity,
    )


def match_specs(section_text: str, *, source_kind: str) -> list[tuple[int, int, AliasSpec]]:
    available: list[AliasSpec] = []
    for spec in ALIAS_SPECS:
        if spec.scan_policy != "contextual":
            available.append(spec)
            continue
        if spec.surface in {"太傅", "丞相"}:
            relevant = (
                any(surface in section_text for surface in ("謝公", "謝太傅", "謝安", "安石", "郗公", "郗太傅", "郗鑒", "郄鑒"))
                if spec.surface == "太傅"
                else any(surface in section_text for surface in ("王公", "王丞相", "王導", "王茂弘", "茂弘"))
            )
            if not relevant:
                continue
        available.append(spec)
    raw_matches: list[tuple[int, int, AliasSpec]] = []
    # Search each surface independently.  A single alternation regex would
    # make longer aliases hide shorter, simultaneous mentions such as the
    # 王凝之 inside 王凝之妻謝氏 kinship reference.
    for spec in available:
        for match in re.finditer(re.escape(spec.surface), section_text):
            raw_matches.append((match.start(), match.end(), spec))
    raw_matches.sort(key=lambda item: (item[0], -(item[1] - item[0]), item[2].alias_id))
    selected: list[tuple[int, int, AliasSpec]] = []
    for start, end, spec in raw_matches:
        contained = False
        if spec.suppress_if_contained:
            for other_start, other_end, _other_spec in raw_matches:
                if (
                    other_start <= start
                    and end <= other_end
                    and (other_start, other_end) != (start, end)
                ):
                    contained = True
                    break
        if not contained:
            selected.append((start, end, spec))
    return selected


def entry_provenance(metadata: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "source_normalized_filename": metadata.get("source_normalized_filename"),
        "source_path": metadata.get("source_path"),
        "source_sha256": metadata.get("source_sha256"),
        "source_chapter": metadata.get("source_chapter"),
        "FILE": metadata.get("FILE"),
        "source_span": {
            "start": metadata.get("start_location", {}),
            "end": metadata.get("end_location", {}),
        },
    }


def unit_provenance(metadata: Mapping[str, Any]) -> dict[str, Any]:
    span = {
        key: metadata[key]
        for key in ("source_line_start", "source_line_end", "start_anchor", "end_anchor")
        if key in metadata
    }
    return {
        "source_witness": metadata.get("source_witness"),
        "source_file": metadata.get("source_file"),
        "source_path": metadata.get("source_path"),
        "source_sha256": metadata.get("source_sha256"),
        "normalized_file_sha256": metadata.get("normalized_file_sha256"),
        "source_span": span,
    }


def build_mention(
    *,
    source_kind: str,
    source_id: str,
    section: str,
    section_text: str,
    start: int,
    end: int,
    spec: AliasSpec,
    provenance: Mapping[str, Any],
    extra: Mapping[str, Any] | None = None,
    resolution_text: str | None = None,
    structural_identity: str | None = None,
) -> dict[str, Any]:
    person_id, confidence, method, context_hits = resolve_spec(
        spec,
        resolution_text if resolution_text is not None else section_text,
        start,
        end,
        structural_identity=structural_identity,
    )
    mention: dict[str, Any] = {
        "source": source_kind,
        "source_id": source_id,
        "section": section,
        "surface": spec.surface,
        "alias_id": spec.alias_id,
        "alias_type": spec.alias_type,
        "person_id": person_id,
        "candidate_person_ids": list(spec.candidate_person_ids),
        "confidence": confidence,
        "resolution_method": method,
        "context_identity_hits": context_hits,
        "context": source_context(section_text, start, end),
        "evidence": {
            "snippet": source_context(section_text, start, end),
            "section_offset": start,
            "provenance": dict(provenance),
        },
    }
    if extra:
        mention.update(extra)
    return mention


def read_shishuo_mentions(root: Path = SHISHUO_ENTRIES) -> list[dict[str, Any]]:
    mentions: list[dict[str, Any]] = []
    for path in sorted(root.rglob("entry-*.md")):
        text = path.read_text(encoding="utf-8")
        metadata = parse_frontmatter(text)
        entry_id = str(metadata.get("entry_id"))
        provenance = entry_provenance(metadata)
        per_section: list[tuple[str, str, dict[str, Any]]] = parse_shishuo_sections(text)
        ordinal = 0
        for section, section_text, section_metadata in per_section:
            for start, end, spec in match_specs(section_text, source_kind="shishuo"):
                ordinal += 1
                extra = {
                    "mention_id": f"shishuo-{entry_id}-{section.replace('_', '-')}-{ordinal:03d}",
                    "entry_id": entry_id,
                    "chapter_id": metadata.get("chapter_id"),
                    "chapter_heading": metadata.get("chapter_heading"),
                    "source_section_metadata": section_metadata,
                }
                mentions.append(
                    build_mention(
                        source_kind="shishuo",
                        source_id=entry_id,
                        section=section,
                        section_text=section_text,
                        start=start,
                        end=end,
                        spec=spec,
                        provenance=provenance,
                        extra=extra,
                    )
                )
    return mentions


def biography_scope(person_id: str | None, metadata: Mapping[str, Any]) -> str:
    title = str(metadata.get("title") or "")
    unit_id = str(metadata.get("unit_id") or "")
    own_unit_ids = {
        "wang-xizhi": {"080-liezhuan-001"},
        "xi-jian": {"067-liezhuan-002"},
        "wang-dao": {"065-liezhuan-001"},
        "xie-an": {"079-liezhuan-002"},
        "xie-daoyun": {"096-liezhuan-016"},
        "wang-ningzhi": set(),
    }
    if person_id and unit_id in own_unit_ids.get(person_id, set()):
        return "own_biography"
    if metadata.get("category") == "liezhuan":
        return "other_biography"
    return "other_unit"


def read_jinshu_mentions(root: Path = JINSHU_UNITS) -> list[dict[str, Any]]:
    mentions: list[dict[str, Any]] = []
    for path in sorted(root.rglob("*.md")):
        text = path.read_text(encoding="utf-8")
        if "## Original source (exact)\n\n" not in text:
            continue
        metadata = parse_frontmatter(text)
        section_text = text.split("## Original source (exact)\n\n", 1)[1]
        resolution_text = mask_markup_comments(section_text)
        unit_heading_identity = {
            "王羲之": "wang-xizhi",
            "郗鑒": "xi-jian",
            "郄鑒": "xi-jian",
            "王導": "wang-dao",
            "謝安": "xie-an",
            "王凝之妻謝氏": "xie-daoyun",
        }.get(str(metadata.get("title") or ""))
        for match_index, (start, end, spec) in enumerate(match_specs(resolution_text, source_kind="jinshu"), start=1):
            mention = build_mention(
                source_kind="jinshu",
                source_id=str(metadata.get("unit_id")),
                section="unit_text",
                section_text=section_text,
                start=start,
                end=end,
                spec=spec,
                provenance=unit_provenance(metadata),
                extra={
                    "mention_id": f"jinshu-{metadata.get('unit_id')}-{match_index:04d}",
                    "unit_id": metadata.get("unit_id"),
                    "volume": metadata.get("volume"),
                    "category": metadata.get("category"),
                    "title": metadata.get("title"),
                },
                resolution_text=resolution_text,
                structural_identity=unit_heading_identity,
            )
            mention["biography_scope"] = biography_scope(mention.get("person_id"), metadata)
            mentions.append(mention)
    return mentions


def all_mentions(shishuo_root: Path = SHISHUO_ENTRIES, jinshu_root: Path = JINSHU_UNITS) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    return read_shishuo_mentions(shishuo_root), read_jinshu_mentions(jinshu_root)


def alias_records(shishuo: Sequence[Mapping[str, Any]], jinshu: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    mentions = list(shishuo) + list(jinshu)
    records: list[dict[str, Any]] = []
    for spec in sorted(ALIAS_SPECS, key=lambda item: item.alias_id):
        observed = [mention for mention in mentions if mention.get("alias_id") == spec.alias_id]
        if not observed:
            continue
        resolved = sorted({mention["person_id"] for mention in observed if mention.get("person_id")})
        if len(spec.candidate_person_ids) > 1:
            status = "shared_or_contextual"
        elif any(mention.get("person_id") is None for mention in observed):
            status = "context_dependent"
        else:
            status = "resolved"
        evidence: list[dict[str, Any]] = []
        for mention in observed[:5]:
            evidence.append(
                {
                    "mention_id": mention["mention_id"],
                    "source": mention["source"],
                    "source_id": mention["source_id"],
                    "section": mention["section"],
                    "surface": mention["surface"],
                    "evidence_snippet": mention["evidence"]["snippet"],
                    "provenance": mention["evidence"]["provenance"],
                }
            )
        records.append(
            {
                "alias_id": spec.alias_id,
                "surface": spec.surface,
                "person_ids": list(spec.candidate_person_ids),
                "alias_type": spec.alias_type,
                "resolution_mode": spec.resolution_mode,
                "status": status,
                "observed_count": len(observed),
                "resolved_person_ids": resolved,
                "source_evidence": evidence,
            }
        )
    return records


def person_records(aliases: Sequence[Mapping[str, Any]], shishuo: Sequence[Mapping[str, Any]], jinshu: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    mentions = list(shishuo) + list(jinshu)
    records: list[dict[str, Any]] = []
    for definition in PERSON_DEFINITIONS:
        person_id = definition["person_id"]
        linked_aliases = [record["alias_id"] for record in aliases if person_id in record.get("person_ids", [])]
        evidence: list[dict[str, Any]] = []
        for mention in mentions:
            if person_id not in mention.get("candidate_person_ids", []):
                continue
            evidence.append(
                {
                    "mention_id": mention["mention_id"],
                    "source": mention["source"],
                    "source_id": mention["source_id"],
                    "surface": mention["surface"],
                    "confidence": mention["confidence"],
                    "snippet": mention["evidence"]["snippet"],
                    "provenance": mention["evidence"]["provenance"],
                }
            )
            if len(evidence) >= 3:
                break
        records.append(
            {
                "person_id": person_id,
                "canonical_name": definition["canonical_name"],
                "identity_scope": "six-person pilot; canonical identity is separate from observed textual spellings",
                "alias_ids": linked_aliases,
                "source_evidence": evidence,
            }
        )
    return records


def report_text(aliases: Sequence[Mapping[str, Any]], shishuo: Sequence[Mapping[str, Any]], jinshu: Sequence[Mapping[str, Any]]) -> str:
    all_records = list(shishuo) + list(jinshu)
    lines = [
        "# Six-person Mention → Alias → Person pilot",
        "",
        "This pilot scans only the materialized Shishuo entries and Jinshu units.",
        "It performs no relationship extraction, historical interpretation, or source-text repair.",
        "Full names, source-backed courtesy names, and orthographic variants resolve conservatively.",
        "Contextual titles resolve only with a strong cue in the same section/unit; otherwise they remain unresolved.",
        "No online scholarly lookup was required for this local-evidence pilot.",
        "",
        "## Per-person summary",
        "",
        "| canonical name | aliases discovered | Shishuo resolved | Jinshu resolved | unresolved candidate mentions | potentially ambiguous aliases |",
        "|---|---|---:|---:|---:|---|",
    ]
    for person in PERSON_DEFINITIONS:
        person_id = person["person_id"]
        person_aliases = [record for record in aliases if person_id in record.get("person_ids", [])]
        surfaces = ", ".join(f"{record['surface']} ({record['status']})" for record in person_aliases) or "—"
        shishuo_count = sum(mention.get("person_id") == person_id for mention in shishuo)
        jinshu_count = sum(mention.get("person_id") == person_id for mention in jinshu)
        unresolved = sum(
            mention.get("person_id") is None and person_id in mention.get("candidate_person_ids", [])
            for mention in all_records
        )
        ambiguous = [
            record["surface"]
            for record in person_aliases
            if len(record.get("person_ids", [])) > 1 or record.get("status") != "resolved"
        ]
        lines.append(
            f"| {person['canonical_name']} | {surfaces} | {shishuo_count} | {jinshu_count} | {unresolved} | {', '.join(ambiguous) or '—'} |"
        )
    lines.extend(["", "## Shared or potentially ambiguous aliases", ""])
    shared = [record for record in aliases if len(record.get("person_ids", [])) > 1 or record.get("status") != "resolved"]
    if shared:
        for record in shared:
            lines.append(
                f"- `{record['surface']}` — candidates: {', '.join(record['person_ids'])}; "
                f"status: `{record['status']}`; observed: {record['observed_count']}."
            )
    else:
        lines.append("None.")
    lines.extend(["", "## Unresolved mention samples", ""])
    unresolved_mentions = [mention for mention in all_records if mention.get("person_id") is None]
    if unresolved_mentions:
        for mention in unresolved_mentions[:40]:
            lines.append(
                f"- `{mention['mention_id']}` `{mention['surface']}` — candidates: "
                f"{', '.join(mention.get('candidate_person_ids', [])) or 'none'}; "
                f"source: `{mention['source_id']}`; section: `{mention['section']}`; "
                f"snippet: {mention['evidence']['snippet'].replace(chr(10), ' ')}"
            )
        if len(unresolved_mentions) > 40:
            lines.append(f"- … {len(unresolved_mentions) - 40} additional unresolved mentions are retained in the JSON output.")
    else:
        lines.append("None.")
    lines.extend(["", "## Scope and non-actions", "", "- Exactly six person IDs are present in `data/people.json`.", "- Source texts under `content/processed/` were read only; no source text was modified.", "- Generic title-only forms are not treated as resolved identities without same-section evidence.", "- No people outside this six-person scope are emitted, and no relationships are extracted.", ""])
    return "\n".join(lines)


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")


def count_markdown_files(root: Path, pattern: str) -> int:
    return sum(1 for path in root.rglob(pattern) if path.is_file())


def build_outputs(
    *,
    root: Path = REPOSITORY_ROOT,
    shishuo_root: Path | None = None,
    jinshu_root: Path | None = None,
) -> dict[str, Any]:
    shishuo_root = shishuo_root or root / "content/processed/shishuo/entries"
    jinshu_root = jinshu_root or root / "content/processed/jinshu/units"
    shishuo, jinshu = all_mentions(shishuo_root, jinshu_root)
    aliases = alias_records(shishuo, jinshu)
    people = person_records(aliases, shishuo, jinshu)
    people_document = {
        "schema": 1,
        "stage": "six-person-pilot",
        "work_scope": ["世說新語", "晉書"],
        "people": people,
    }
    aliases_document = {
        "schema": 1,
        "stage": "six-person-pilot",
        "resolution_policy": "exact/contextual/ambiguous; unresolved identity is retained as null",
        "aliases": aliases,
    }
    shishuo_document = {
        "schema": 1,
        "stage": "mention-detection",
        "source": "世說新語",
        "person_scope": sorted(PERSON_IDS),
        "scanned_entry_count": count_markdown_files(shishuo_root, "entry-*.md"),
        "mention_count": len(shishuo),
        "mentions": shishuo,
    }
    jinshu_document = {
        "schema": 1,
        "stage": "mention-detection",
        "source": "晉書",
        "person_scope": sorted(PERSON_IDS),
        "scanned_unit_count": count_markdown_files(jinshu_root, "*.md"),
        "mention_count": len(jinshu),
        "mentions": jinshu,
    }
    outputs = {
        "people": people_document,
        "aliases": aliases_document,
        "shishuo": shishuo_document,
        "jinshu": jinshu_document,
        "report": report_text(aliases, shishuo, jinshu),
    }
    write_json(root / "data/people.json", people_document)
    write_json(root / "data/aliases.json", aliases_document)
    write_json(root / "data/mentions/shishuo.json", shishuo_document)
    write_json(root / "data/mentions/jinshu.json", jinshu_document)
    report_path = root / "content/curated/entities/six-person-pilot.md"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(outputs["report"], encoding="utf-8", newline="\n")
    return outputs


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=REPOSITORY_ROOT)
    args = parser.parse_args(argv)
    outputs = build_outputs(root=args.root)
    print(f"people: {len(outputs['people']['people'])}")
    print(f"aliases: {len(outputs['aliases']['aliases'])}")
    print(f"shishuo mentions: {outputs['shishuo']['mention_count']}")
    print(f"jinshu mentions: {outputs['jinshu']['mention_count']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
