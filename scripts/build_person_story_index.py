#!/usr/bin/env python3
"""Build the deterministic Shishuo Person ↔ Story pilot index.

This is navigation data, not a new historical assertion layer.  Links are
derived from resolved Shishuo mentions.  Main-text presence is deliberately
classified as ``mentioned`` until a separate reviewed participation decision
exists; a person is never made a participant merely by appearing in an entry.
"""

from __future__ import annotations

from collections import defaultdict
import hashlib
import json
from pathlib import Path
from typing import Any, Iterable

try:
    from .build_six_person_pilot import markdown_body, parse_frontmatter
except ImportError:  # direct execution: python scripts/build_person_story_index.py
    from build_six_person_pilot import markdown_body, parse_frontmatter


ROOT = Path(__file__).resolve().parents[1]
PEOPLE_PATH = ROOT / "data/people.json"
SHISHUO_MENTIONS_PATH = ROOT / "data/mentions/shishuo.json"
CORPUS_INDEX_PATH = ROOT / "data/shishuo-corpus-index.json"
PUNCTUATION_PATH = ROOT / "data/annotation/wp1-punctuation.json"
FRONTEND_BUNDLE_PATH = ROOT / "data/derived/wp1-site.json"
EVIDENCE_PATH = ROOT / "data/evidence/wp1-evidence.json"
LINKS_PATH = ROOT / "data/derived/person-story-links.json"
INDEX_PATH = ROOT / "data/derived/person-story-index.json"
REPORT_PATH = ROOT / "docs/person-story-pilot.md"

PRIMARY_PERSON_IDS = {
    "wang-xizhi",
    "xi-jian",
    "wang-dao",
    "wang-ningzhi",
    "xie-daoyun",
    "xie-an",
}


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=False) + "\n",
        encoding="utf-8",
    )


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_entry_metadata(entry: dict[str, Any]) -> dict[str, Any]:
    path = ROOT / entry["path"]
    values = parse_frontmatter(path.read_text(encoding="utf-8"))
    return {
        "chapter_id": values.get("chapter_id", "-".join(entry["id"].split("-")[:-1])),
        "chapter_heading": values.get("chapter_heading", ""),
        "path": entry["path"],
        "character_count": len(markdown_body(path.read_text(encoding="utf-8"))),
    }


def mention_id(mention: dict[str, Any]) -> str:
    value = mention.get("mention_id")
    if not isinstance(value, str) or not value:
        raise ValueError("Shishuo mention has no stable mention_id")
    return value


def mention_entry_id(mention: dict[str, Any]) -> str:
    value = mention.get("entry_id") or mention.get("source_id")
    if not isinstance(value, str) or not value:
        raise ValueError(f"Shishuo mention {mention_id(mention)} has no entry_id")
    return value


def sorted_unique(values: Iterable[str]) -> list[str]:
    return sorted(set(values))


def build_mention_link(
    person_id: str,
    entry_id: str,
    mentions: list[dict[str, Any]],
) -> dict[str, Any]:
    mentions = sorted(mentions, key=mention_id)
    high_mentions = [mention for mention in mentions if mention.get("confidence") == "high"]
    candidate_mentions = [mention for mention in mentions if mention.get("confidence") != "high"]
    has_high = bool(high_mentions)
    confidence = "high" if has_high else "medium"
    review_status = "reviewed" if has_high else "candidate"
    resolution_status = (
        "deterministic"
        if has_high and not candidate_mentions
        else "mixed"
        if has_high
        else "contextual"
    )
    presences: list[dict[str, Any]] = []
    by_section: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for mention in mentions:
        by_section[str(mention["section"])].append(mention)
    for source_layer in sorted(by_section):
        section_mentions = sorted(by_section[source_layer], key=mention_id)
        high_section_mentions = [
            mention for mention in section_mentions
            if mention.get("confidence") == "high"
        ]
        candidate_section_mentions = [
            mention for mention in section_mentions
            if mention.get("confidence") != "high"
        ]
        presences.append(
            {
                "source_layer": source_layer,
                "presence_kind": "mentioned",
                "supporting_mention_ids": [mention_id(item) for item in high_section_mentions],
                "candidate_mention_ids": [mention_id(item) for item in candidate_section_mentions],
            }
        )
    contextual = [
        mention["surface"]
        for mention in mentions
        if mention.get("confidence") != "high"
    ]
    notes = (
        "Main-text and Liu Xiaobiao appearances are indexed as mentioned; "
        "no participant status is inferred from appearance alone."
    )
    if contextual:
        notes += " Contextual forms retained as candidate evidence: " + "、".join(sorted_unique(contextual)) + "。"
    return {
        "id": f"person-story-{person_id}-{entry_id}",
        "person_id": person_id,
        "entry_id": entry_id,
        "link_basis": "mention",
        "presences": presences,
        "supporting_mention_ids": [mention_id(mention) for mention in high_mentions],
        "candidate_mention_ids": [mention_id(mention) for mention in candidate_mentions],
        "evidence_ids": sorted_unique(
            evidence_id
            for mention in mentions
            for evidence_id in mention.get("evidence", {}).get("evidence_ids", [])
        ),
        "resolution_status": resolution_status,
        "confidence": confidence,
        "review_status": review_status,
        "notes": notes,
    }


def build_supporting_bridge_link(
    person: dict[str, Any],
    evidence_records: list[dict[str, Any]],
) -> dict[str, Any] | None:
    if person.get("person_id") != "person-007":
        return None
    source_evidence = next(
        (
            item
            for item in person.get("source_evidence", [])
            if item.get("source") == "shishuo" and item.get("source_id") == "06-yaliang-019"
        ),
        None,
    )
    if source_evidence is None:
        return None
    evidence = next(
        (
            item
            for item in evidence_records
            if item.get("locator", {}).get("entry_id") == "06-yaliang-019"
            and item.get("quote") == "妻太傅郗鑒女名璿字子房"
        ),
        None,
    )
    if evidence is None:
        raise ValueError("supporting Person person-007 lacks a matching evidence record")
    return {
        "id": "person-story-person-007-06-yaliang-019",
        "person_id": "person-007",
        "entry_id": "06-yaliang-019",
        "link_basis": "explicit_evidence",
        "presences": [
            {
                "source_layer": "liu_annotation",
                "presence_kind": "mentioned",
                "supporting_mention_ids": [],
                "candidate_mention_ids": [],
            }
        ],
        "supporting_mention_ids": [],
        "candidate_mention_ids": [],
        "evidence_ids": [evidence["id"]],
        "resolution_status": "explicit_evidence",
        "confidence": "high",
        "review_status": "reviewed",
        "notes": (
            "Supporting bridge Person indexed from the existing explicit Liu Xiaobiao "
            "annotation evidence. The six-person mention scan did not emit a standalone "
            "Mention for person-007, so no synthetic Mention is created."
        ),
    }


def story_readiness(
    entry_id: str,
    entry: dict[str, Any],
    entry_meta: dict[str, Any],
    punctuation_by_entry: dict[str, dict[str, Any]],
    frontend_stories: dict[str, dict[str, Any]],
    reviewed_links: list[dict[str, Any]],
    all_mentions: list[dict[str, Any]],
) -> dict[str, Any]:
    reasons: list[str] = []
    entry_path = ROOT / entry["path"]
    canonical_entry = (
        entry_path.is_file()
        and sha256_file(entry_path) == entry.get("entry_sha256")
    )
    if not canonical_entry:
        reasons.append("canonical entry is missing or its hash differs from the corpus index")

    punctuation = punctuation_by_entry.get(entry_id)
    reviewed_punctuation = False
    if punctuation is not None:
        reviewed_punctuation = (
            punctuation.get("status") == "reviewed"
            and punctuation.get("base_canonical_entry_path") == entry["path"]
            and punctuation.get("base_canonical_entry_sha256") == entry.get("entry_sha256")
        )
    if not reviewed_punctuation:
        reasons.append("reviewed punctuation record is unavailable for this entry")

    story = frontend_stories.get(entry_id)
    reading = story.get("reading") if isinstance(story, dict) else None
    simplified_reading = bool(
        isinstance(reading, dict)
        and reading.get("status") == "reviewed"
        and isinstance(reading.get("main_text"), dict)
        and isinstance(reading["main_text"].get("original"), str)
        and isinstance(reading["main_text"].get("simplified"), str)
        and reading["main_text"].get("original")
        and reading["main_text"].get("simplified")
        and isinstance(reading.get("annotations"), list)
    )
    if not simplified_reading:
        reasons.append("reviewed original/simplified reading representation is unavailable")

    resolved_person_mentions = bool(reviewed_links)
    if not resolved_person_mentions:
        reasons.append("no reviewed resolved Person mention link is available")
    entry_mentions = [mention for mention in all_mentions if mention_entry_id(mention) == entry_id]
    unresolved_mention_count = sum(mention.get("person_id") is None for mention in entry_mentions)
    reviewed_link_count = len(reviewed_links)
    reader_ready = all(
        (canonical_entry, reviewed_punctuation, simplified_reading, resolved_person_mentions)
    )
    return {
        "entry_id": entry_id,
        "canonical_entry": canonical_entry,
        "reviewed_punctuation": reviewed_punctuation,
        "simplified_reading": simplified_reading,
        "resolved_person_mentions": resolved_person_mentions,
        "reviewed_link_count": reviewed_link_count,
        "unresolved_mention_count": unresolved_mention_count,
        "reader_ready": reader_ready,
        "reasons": reasons,
    }


def story_reference(
    entry: dict[str, Any],
    entry_meta: dict[str, Any],
    links: list[dict[str, Any]],
    readiness: dict[str, Any],
) -> dict[str, Any]:
    return {
        "entry_id": entry["id"],
        "chapter_id": entry_meta["chapter_id"],
        "chapter_heading": entry_meta["chapter_heading"],
        "ordinal": entry["ordinal"],
        "global_ordinal": entry["global_ordinal"],
        "link_ids": [link["id"] for link in links],
        "source_layers": sorted_unique(
            presence["source_layer"]
            for link in links
            for presence in link["presences"]
        ),
        "presence_kinds": sorted_unique(
            presence["presence_kind"]
            for link in links
            for presence in link["presences"]
        ),
        "reader_ready": readiness["reader_ready"],
    }


def select_pilot_candidates(
    reviewed_links: list[dict[str, Any]],
    readiness_by_entry: dict[str, dict[str, Any]],
    entry_by_id: dict[str, dict[str, Any]],
) -> list[str]:
    by_entry: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for link in reviewed_links:
        by_entry[link["entry_id"]].append(link)

    def key(entry_id: str) -> tuple[int, int, int, int, int, int]:
        links = by_entry[entry_id]
        persons = len({link["person_id"] for link in links})
        main_text_persons = sum(
            any(presence["source_layer"] == "main_text" for presence in link["presences"])
            for link in links
        )
        all_explicit = sum(link["confidence"] == "high" for link in links)
        entry = entry_by_id[entry_id]
        # These are editorial selection flags, not importance scores.
        return (
            int(readiness_by_entry[entry_id]["reader_ready"]),
            int(persons >= 2),
            persons,
            main_text_persons,
            all_explicit,
            -entry["global_ordinal"],
        )

    return [
        entry_id
        for entry_id in sorted(by_entry, key=key, reverse=True)[:16]
    ]


def report_excerpt(
    link: dict[str, Any],
    mentions_by_id: dict[str, dict[str, Any]],
    evidence_by_id: dict[str, dict[str, Any]],
) -> str:
    mention_candidates = [
        mentions_by_id[mention_id]
        for mention_id in link["supporting_mention_ids"]
        if mention_id in mentions_by_id
    ]
    if mention_candidates:
        preferred = sorted(
            mention_candidates,
            key=lambda mention: (mention.get("section") != "main_text", mention_id(mention)),
        )[0]
        return str(preferred.get("context") or preferred.get("evidence", {}).get("snippet") or "")
    evidence_candidates = [
        evidence_by_id[evidence_id]
        for evidence_id in link["evidence_ids"]
        if evidence_id in evidence_by_id
    ]
    return str(evidence_candidates[0].get("quote", "")) if evidence_candidates else ""


def render_report(
    people: list[dict[str, Any]],
    links: list[dict[str, Any]],
    index: dict[str, Any],
    entry_by_id: dict[str, dict[str, Any]],
    entry_meta_by_id: dict[str, dict[str, Any]],
    mentions_by_id: dict[str, dict[str, Any]],
    evidence_by_id: dict[str, dict[str, Any]],
    pilot_candidates: list[str],
) -> str:
    lines = [
        "# Person ↔ Story pilot",
        "",
        "This is deterministic navigation/index data for the unified materialized Shishuo Person registry. The six-person pilot is the historical bootstrap stage; this index is not a personality interpretation, participation claim, or new historical assertion.",
        "",
        "## Semantics",
        "",
        "- Links are derived from resolved Shishuo mentions, plus the existing explicit evidence link for supporting Person `person-007` 郗璿.",
        "- `main_text` and `liu_annotation` are source layers. Current links use `presence_kind: mentioned`; no `participant` status is inferred from appearance alone.",
        "- A high-confidence exact-name/courtesy-name or otherwise deterministic resolved mention produces a reviewed link. Medium contextual forms remain candidate mention evidence attached to that link and never establish review by themselves.",
        "- The PersonStoryIndex contains reviewed links only. Candidate links remain in the link artifact and are listed for human review; contextual candidate Mentions attached to a reviewed link remain candidate evidence rather than a second semantic link.",
        "- `reader_ready` requires a canonical entry, reviewed punctuation, both original/simplified reading forms, and at least one reviewed resolved Person link. Unresolved contextual titles may remain in the source, as they do in the current reader.",
        "",
        "## Summary",
        "",
        f"- primary people: {len([person for person in people if person.get('scope_role') == 'primary'])}",
        f"- supporting people: {len([person for person in people if person.get('scope_role') == 'supporting'])}",
        f"- reviewed PersonStoryLinks: {index['reviewed_link_count']}",
        f"- candidate PersonStoryLinks: {index['candidate_link_count']}",
        f"- candidate contextual mentions retained: {index['candidate_mention_count']}",
        f"- reader-ready linked Stories: {sum(item['reader_ready'] for item in index['story_readiness'])}",
        "",
        "## Person review lists",
        "",
        "No Story is listed as directly participating unless a future reviewed presence explicitly uses `participant`; this pilot currently has none.",
        "",
    ]

    by_person: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for link in links:
        by_person[link["person_id"]].append(link)
    for person in people:
        person_id = person.get("person_id")
        if person.get("scope_role") != "primary":
            continue
        person_links = sorted(
            by_person.get(person_id, []),
            key=lambda link: entry_by_id[link["entry_id"]]["global_ordinal"],
        )
        main_links = [
            link
            for link in person_links
            if any(presence["source_layer"] == "main_text" for presence in link["presences"])
        ]
        liu_only_links = [
            link
            for link in person_links
            if all(presence["source_layer"] == "liu_annotation" for presence in link["presences"])
        ]
        reviewed_count = sum(link["review_status"] == "reviewed" for link in person_links)
        ready_count = sum(
            index["story_readiness_by_entry"][link["entry_id"]]["reader_ready"]
            for link in person_links
            if link["review_status"] == "reviewed"
        )
        lines.extend(
            [
                f"### {person['canonical_name']} (`{person_id}`)",
                "",
                "- directly participating Stories: none currently classified; main-text appearance is retained as `mentioned` pending explicit participation review.",
                f"- reviewed linked Stories: {reviewed_count}; reader-ready: {ready_count}; candidate links: {len(person_links) - reviewed_count}; candidate contextual Mentions: {sum(len(link.get('candidate_mention_ids', [])) for link in person_links)}",
                "- main-text presence:",
            ]
        )
        if not main_links:
            lines.append("  - none")
        for link in main_links:
            entry = entry_by_id[link["entry_id"]]
            meta = entry_meta_by_id[link["entry_id"]]
            status = link["review_status"]
            ready = index["story_readiness_by_entry"][link["entry_id"]]["reader_ready"]
            surfaces = sorted_unique(
                mentions_by_id[mention_id]["surface"]
                for mention_id in link["supporting_mention_ids"]
                if mention_id in mentions_by_id
            )
            excerpt = report_excerpt(link, mentions_by_id, evidence_by_id)
            lines.extend(
                [
                    f"  - `{link['entry_id']}` · {meta['chapter_heading']} · {status} · reader_ready={str(ready).lower()} · surface: {'、'.join(surfaces) or 'explicit annotation evidence'}",
                    "    ```text",
                    excerpt,
                    "    ```",
                ]
            )
        lines.append("- Liu-annotation-only presence:")
        if not liu_only_links:
            lines.append("  - none")
        for link in liu_only_links:
            meta = entry_meta_by_id[link["entry_id"]]
            ready = index["story_readiness_by_entry"][link["entry_id"]]["reader_ready"]
            surfaces = sorted_unique(
                mentions_by_id[mention_id]["surface"]
                for mention_id in link["supporting_mention_ids"]
                if mention_id in mentions_by_id
            )
            excerpt = report_excerpt(link, mentions_by_id, evidence_by_id)
            lines.extend(
                [
                    f"  - `{link['entry_id']}` · {meta['chapter_heading']} · {link['review_status']} · reader_ready={str(ready).lower()} · surface: {'、'.join(surfaces) or 'explicit annotation evidence'}",
                    "    ```text",
                    excerpt,
                    "    ```",
                ]
            )
        lines.append("")

    lines.extend(["## Proposed first multi-story pilot candidates", ""])
    lines.append(
        "These 16 candidates are selected deterministically from reviewed links using only editorial flags: reader-ready representation, multiple reviewed people, main-text presence, explicit/high-confidence resolution, and canonical order. They are not importance scores or interpretations."
    )
    lines.append("")
    links_by_entry: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for link in links:
        if link["review_status"] == "reviewed":
            links_by_entry[link["entry_id"]].append(link)
    for entry_id in pilot_candidates:
        entry = entry_by_id[entry_id]
        meta = entry_meta_by_id[entry_id]
        entry_links = links_by_entry[entry_id]
        person_names = [
            next(person["canonical_name"] for person in people if person.get("person_id") == link["person_id"])
            for link in entry_links
        ]
        flags = []
        if index["story_readiness_by_entry"][entry_id]["reader_ready"]:
            flags.append("reader-ready")
        if len(set(person_names)) >= 2:
            flags.append("multiple reviewed people")
        if any(any(p["source_layer"] == "main_text" for p in link["presences"]) for link in entry_links):
            flags.append("main-text presence")
        if all(link["confidence"] == "high" for link in entry_links):
            flags.append("explicit/high-confidence resolution")
        lines.append(
            f"- `{entry_id}` · {meta['chapter_heading']} · {'、'.join(sorted_unique(person_names))} · "
            + "; ".join(flags)
        )
    lines.extend(
        [
            "",
            "## Candidate and unresolved mentions",
            "",
            "Medium contextual resolutions remain candidate mention evidence in the machine-readable link artifact. Unresolved title-only mentions have `person_id: null` in the existing Mention data and do not create links. No co-occurrence, relation edge, surname, Jinshu biography, or semantic similarity creates a PersonStoryLink.",
            "",
            "The current supporting 郗璿 link is the only link without a legacy Mention ID; it is backed by the existing explicit Liu Xiaobiao evidence record and is kept visible as `link_basis: explicit_evidence` rather than creating a synthetic Mention.",
            "",
        ]
    )
    for person in people:
        person_id = person.get("person_id")
        candidate_mentions = [
            mentions_by_id[mention_id]
            for link in by_person.get(person_id, [])
            for mention_id in link.get("candidate_mention_ids", [])
            if mention_id in mentions_by_id
        ]
        if not candidate_mentions:
            continue
        lines.append(f"- {person['canonical_name']} (`{person_id}`):")
        for mention in sorted(candidate_mentions, key=lambda item: (item.get("entry_id", ""), mention_id(item))):
            lines.append(
                f"  - `{mention.get('entry_id')}` · {mention.get('section')} · `{mention.get('surface')}` · confidence={mention.get('confidence')} · context_identity_hits={','.join(mention.get('context_identity_hits', [])) or 'none'}"
            )
    lines.append("")
    return "\n".join(lines)


def build(root: Path = ROOT) -> tuple[dict[str, Any], dict[str, Any], str]:
    global ROOT, PEOPLE_PATH, SHISHUO_MENTIONS_PATH, CORPUS_INDEX_PATH
    global PUNCTUATION_PATH, FRONTEND_BUNDLE_PATH, EVIDENCE_PATH
    global LINKS_PATH, INDEX_PATH, REPORT_PATH
    ROOT = root
    PEOPLE_PATH = root / "data/people.json"
    SHISHUO_MENTIONS_PATH = root / "data/mentions/shishuo.json"
    CORPUS_INDEX_PATH = root / "data/shishuo-corpus-index.json"
    PUNCTUATION_PATH = root / "data/annotation/wp1-punctuation.json"
    FRONTEND_BUNDLE_PATH = root / "data/derived/wp1-site.json"
    EVIDENCE_PATH = root / "data/evidence/wp1-evidence.json"
    LINKS_PATH = root / "data/derived/person-story-links.json"
    INDEX_PATH = root / "data/derived/person-story-index.json"
    REPORT_PATH = root / "docs/person-story-pilot.md"

    people_document = read_json(PEOPLE_PATH)
    people = people_document["people"]
    person_ids = {person["person_id"] for person in people}
    if not PRIMARY_PERSON_IDS <= person_ids:
        raise ValueError("unified Person registry is missing a primary pilot person")
    mentions = read_json(SHISHUO_MENTIONS_PATH)["mentions"]
    mentions_by_id = {mention_id(mention): mention for mention in mentions}
    corpus_entries = read_json(CORPUS_INDEX_PATH)["entries"]
    entry_by_id = {entry["id"]: entry for entry in corpus_entries}
    entry_meta_by_id = {entry_id: load_entry_metadata(entry) for entry_id, entry in entry_by_id.items()}
    punctuation_records = read_json(PUNCTUATION_PATH)["records"]
    punctuation_by_entry = {record["entry_id"]: record for record in punctuation_records}
    frontend_stories = {
        story["id"]: story
        for story in read_json(FRONTEND_BUNDLE_PATH).get("stories", [])
    }
    evidence_records = read_json(EVIDENCE_PATH)["records"]
    evidence_by_id = {record["id"]: record for record in evidence_records}

    grouped: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for mention in mentions:
        person_id = mention.get("person_id")
        if person_id is None:
            continue
        if person_id not in person_ids:
            raise ValueError(f"resolved Shishuo mention points to unknown Person: {person_id}")
        entry_id = mention_entry_id(mention)
        if entry_id not in entry_by_id:
            raise ValueError(f"resolved Shishuo mention points to unknown entry: {entry_id}")
        grouped[(person_id, entry_id)].append(mention)

    links = [
        build_mention_link(person_id, entry_id, grouped[(person_id, entry_id)])
        for person_id, entry_id in sorted(grouped)
    ]
    supporting_link = next(
        (
            build_supporting_bridge_link(person, evidence_records)
            for person in people
            if person.get("person_id") == "person-007"
        ),
        None,
    )
    if supporting_link is not None:
        links.append(supporting_link)
    links.sort(key=lambda link: (entry_by_id[link["entry_id"]]["global_ordinal"], link["person_id"]))

    reviewed_links = [link for link in links if link["review_status"] == "reviewed"]
    candidate_links = [link for link in links if link["review_status"] == "candidate"]
    reviewed_by_entry: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for link in reviewed_links:
        reviewed_by_entry[link["entry_id"]].append(link)
    all_linked_entry_ids = sorted(
        {link["entry_id"] for link in links},
        key=lambda entry_id: entry_by_id[entry_id]["global_ordinal"],
    )
    readiness_by_entry = {
        entry_id: story_readiness(
            entry_id,
            entry_by_id[entry_id],
            entry_meta_by_id[entry_id],
            punctuation_by_entry,
            frontend_stories,
            reviewed_by_entry.get(entry_id, []),
            mentions,
        )
        for entry_id in all_linked_entry_ids
    }

    person_records: list[dict[str, Any]] = []
    for person in people:
        person_id = person["person_id"]
        person_reviewed = [link for link in reviewed_links if link["person_id"] == person_id]
        person_candidates = [link for link in candidate_links if link["person_id"] == person_id]
        refs_by_entry: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for link in person_reviewed:
            refs_by_entry[link["entry_id"]].append(link)
        story_refs = [
            story_reference(
                entry_by_id[entry_id],
                entry_meta_by_id[entry_id],
                refs_by_entry[entry_id],
                readiness_by_entry[entry_id],
            )
            for entry_id in sorted(
                refs_by_entry,
                key=lambda item: entry_by_id[item]["global_ordinal"],
            )
        ]
        person_records.append(
            {
                "person_id": person_id,
                "scope_role": person.get("scope_role"),
                "story_refs": story_refs,
                "candidate_story_ids": [
                    entry_id
                    for entry_id in sorted(
                        {link["entry_id"] for link in person_candidates},
                        key=lambda item: entry_by_id[item]["global_ordinal"],
                    )
                ],
            }
        )

    readiness_records = [
        readiness_by_entry[entry_id]
        for entry_id in all_linked_entry_ids
    ]
    # Keep a private lookup in the in-memory object for report generation; it
    # is removed before the JSON artifact is written.
    index: dict[str, Any] = {
        "schema": 1,
        "stage": "person-story-indexing",
        "work": "世說新語",
        "generated_from": "scripts/build_person_story_index.py",
        "person_scope": [person["person_id"] for person in people],
        "reviewed_link_count": len(reviewed_links),
        "candidate_link_count": len(candidate_links),
        "candidate_mention_count": sum(len(link["candidate_mention_ids"]) for link in links),
        "persons": person_records,
        "story_readiness": readiness_records,
        "story_readiness_by_entry": readiness_by_entry,
    }
    pilot_candidates = select_pilot_candidates(reviewed_links, readiness_by_entry, entry_by_id)
    report = render_report(
        people,
        links,
        index,
        entry_by_id,
        entry_meta_by_id,
        mentions_by_id,
        evidence_by_id,
        pilot_candidates,
    )
    index.pop("story_readiness_by_entry")
    links_document = {
        "schema": 1,
        "stage": "person-story-linking",
        "work": "世說新語",
        "generated_from": "scripts/build_person_story_index.py",
        "person_scope": [person["person_id"] for person in people],
        "link_count": len(links),
        "reviewed_link_count": len(reviewed_links),
        "candidate_link_count": len(candidate_links),
        "candidate_mention_count": sum(len(link["candidate_mention_ids"]) for link in links),
        "links": links,
    }
    index["candidate_selection"] = {
        "count": len(pilot_candidates),
        "entry_ids": pilot_candidates,
        "criteria": [
            "reader-ready representation",
            "multiple reviewed people",
            "main-text presence",
            "explicit/high-confidence resolution",
            "canonical order",
        ],
    }
    return links_document, index, report


def main() -> int:
    links, index, report = build()
    write_json(LINKS_PATH, links)
    write_json(INDEX_PATH, index)
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(report, encoding="utf-8")
    print(
        f"built PersonStory pilot: {links['reviewed_link_count']} reviewed links, "
        f"{links['candidate_link_count']} candidate links, "
        f"{len(index['candidate_selection']['entry_ids'])} proposed Stories"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
