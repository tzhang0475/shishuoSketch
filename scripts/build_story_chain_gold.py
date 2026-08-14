#!/usr/bin/env python3
"""Build the deterministic SC0 Story Chain Gold Set and review packet.

SC0 is editorial selection data.  It projects existing reviewed
PersonStoryLinks and CRL1.1 reading records; it does not create Persons,
Mentions, Relations, or punctuation approvals.
"""

from __future__ import annotations

from collections import defaultdict
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

try:
    from .build_six_person_pilot import PERSON_DEFINITIONS, parse_frontmatter, parse_shishuo_sections
    from .reading_layers import strip_display_punctuation
except ImportError:  # direct execution
    from build_six_person_pilot import PERSON_DEFINITIONS, parse_frontmatter, parse_shishuo_sections
    from reading_layers import strip_display_punctuation


ROOT = Path(__file__).resolve().parents[1]
LINKS_PATH = ROOT / "data/derived/person-story-links.json"
PERSON_INDEX_PATH = ROOT / "data/derived/person-story-index.json"
CORPUS_INDEX_PATH = ROOT / "data/shishuo-corpus-index.json"
PEOPLE_PATH = ROOT / "data/people.json"
PUNCTUATION_PATH = ROOT / "data/annotation/wp1-punctuation.json"
READING_PATH = ROOT / "data/derived/shishuo-reading-layer.json"
RELATIONS_PATH = ROOT / "data/annotation/wp1-relations.json"
GOLD_PATH = ROOT / "data/story-chain-gold-set.json"
CHAIN_INDEX_PATH = ROOT / "data/derived/story-chain-gold-index.json"
CONNECTIVITY_PATH = ROOT / "data/derived/story-chain-connectivity.json"
REVIEW_PATH = ROOT / "docs/story-chain-gold-review.md"

PRIMARY_PERSON_IDS = tuple(item["person_id"] for item in PERSON_DEFINITIONS)
SUPPORTING_PERSON_IDS = ("person-007",)
PILOT_PERSON_IDS = set(PRIMARY_PERSON_IDS) | set(SUPPORTING_PERSON_IDS)

# The first candidate pass starts with existing P1A candidates.  The final
# deterministic selector may add other reviewed-linked entries when they add
# main-text coverage or improve the connected component.
P1A_CANDIDATES = (
    "06-yaliang-019",
    "25-paidiao-026",
    "19-xianyuan-026",
    "06-yaliang-029",
    "07-shijian-024",
    "10-guizhen-017",
    "02-yanyu-069",
    "02-yanyu-071",
    "02-yanyu-083",
    "04-wenxue-024",
    "04-wenxue-036",
    "04-wenxue-087",
    "05-fangzheng-023",
    "05-fangzheng-053",
    "05-fangzheng-055",
    "06-yaliang-027",
)


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_main_text(path: Path) -> str:
    for section, body, _metadata in parse_shishuo_sections(path.read_text(encoding="utf-8")):
        if section == "main_text":
            return body.strip("\n")
    raise ValueError(f"canonical entry has no main_text: {path}")


def compact(text: str) -> str:
    return "".join(character for character in text if not character.isspace())


def load_inputs() -> dict[str, Any]:
    links_document = read_json(LINKS_PATH)
    links = [
        link for link in links_document["links"]
        if link.get("review_status") == "reviewed"
        and link.get("person_id") in PILOT_PERSON_IDS
    ]
    entries = read_json(CORPUS_INDEX_PATH)["entries"]
    entry_by_id = {entry["id"]: entry for entry in entries}
    people = {person["person_id"]: person for person in read_json(PEOPLE_PATH)["people"]}
    punctuation = {record["entry_id"]: record for record in read_json(PUNCTUATION_PATH)["records"]}
    reading = {record["entry_id"]: record for record in read_json(READING_PATH)["records"]}
    return {
        "links_document": links_document,
        "links": links,
        "entries": entries,
        "entry_by_id": entry_by_id,
        "people": people,
        "punctuation": punctuation,
        "reading": reading,
        "relations": read_json(RELATIONS_PATH)["records"],
    }


def link_layers(link: Mapping[str, Any]) -> tuple[list[str], list[str]]:
    main: list[str] = []
    annotation: list[str] = []
    for presence in link.get("presences", []):
        if presence.get("source_layer") == "main_text":
            main.append(link["person_id"])
        elif presence.get("source_layer") == "liu_annotation":
            annotation.append(link["person_id"])
    return sorted(set(main)), sorted(set(annotation))


def candidate_report(inputs: Mapping[str, Any]) -> list[dict[str, Any]]:
    by_entry: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for link in inputs["links"]:
        by_entry[link["entry_id"]].append(link)
    result: list[dict[str, Any]] = []
    for entry_id, links in by_entry.items():
        entry = inputs["entry_by_id"][entry_id]
        entry_frontmatter = parse_frontmatter(
            (ROOT / entry["path"]).read_text(encoding="utf-8")
        )
        main_ids = sorted({person_id for link in links for person_id in link_layers(link)[0]})
        annotation_ids = sorted({person_id for link in links for person_id in link_layers(link)[1]})
        # A person present in main text is not repeated as annotation-only.
        annotation_only_ids = [person_id for person_id in annotation_ids if person_id not in main_ids]
        punctuation = inputs["punctuation"].get(entry_id, {})
        reading = inputs["reading"].get(entry_id, {})
        text = canonical_main_text(ROOT / entry["path"])
        result.append(
            {
                "entry_id": entry_id,
                "chapter_id": entry_id.rsplit("-", 1)[0],
                "chapter_heading": entry_frontmatter.get("chapter_heading", entry.get("chapter_heading", "")),
                "global_ordinal": entry["global_ordinal"],
                "linked_person_ids": sorted({link["person_id"] for link in links}),
                "main_text_person_ids": main_ids,
                "liu_annotation_only_person_ids": annotation_only_ids,
                "pilot_network_link_count": len(links),
                "punctuation_status": punctuation.get("status"),
                "punctuation_basis": punctuation.get("punctuation_basis"),
                "exact_transfer": punctuation.get("exact_transfer", False),
                "reader_ready": reading.get("story_reader_ready", False),
                "canonical_character_count": len(compact(text)),
                "candidate_source": "p1a" if entry_id in P1A_CANDIDATES else "other_deterministic_person_story_link",
            }
        )
    return sorted(result, key=lambda item: item["global_ordinal"])


def _selection_score(item: Mapping[str, Any]) -> tuple[int, int, int, int, int, int, int]:
    """Deterministic editorial score; not a historical importance score."""

    return (
        int(item["reader_ready"]),
        int(item["entry_id"] == "06-yaliang-019"),
        int(len(item["main_text_person_ids"]) >= 2),
        len(item["main_text_person_ids"]),
        int(bool(item["main_text_person_ids"])),
        int(item["exact_transfer"]),
        -item["global_ordinal"],
    )


def select_gold(candidate_records: list[dict[str, Any]]) -> list[str]:
    by_id = {record["entry_id"]: record for record in candidate_records}
    selected: list[str] = ["06-yaliang-019"]

    # Preserve strong P1A bridge candidates first when they have main-text
    # presence or multiple network persons.  This keeps the initial story
    # world legible while the score chooses replacements deterministically.
    preferred = [
        record for record in candidate_records
        if record["entry_id"] in P1A_CANDIDATES
        and record["entry_id"] != "06-yaliang-019"
        and record["main_text_person_ids"]
    ]
    for record in sorted(preferred, key=_selection_score, reverse=True):
        if record["entry_id"] not in selected:
            selected.append(record["entry_id"])

    # Add the strongest deterministic main-text stories until the requested
    # small world reaches 16 stories.  No graph edge is invented here.
    remaining = [record for record in candidate_records if record["entry_id"] not in selected]
    for record in sorted(remaining, key=_selection_score, reverse=True):
        if len(selected) >= 16:
            break
        if record["main_text_person_ids"]:
            selected.append(record["entry_id"])

    return sorted(selected, key=lambda entry_id: by_id[entry_id]["global_ordinal"])


def selection_reason_codes(record: Mapping[str, Any]) -> list[str]:
    reasons: list[str] = []
    if record["entry_id"] == "06-yaliang-019":
        reasons.append("existing_reviewed_anchor")
    if len(record["main_text_person_ids"]) >= 2:
        reasons.append("multi_person_main_text_bridge")
    if record["main_text_person_ids"]:
        reasons.append("main_text_person_presence")
    if len(record["linked_person_ids"]) >= 2:
        reasons.append("multiple_resolved_network_persons")
    if record["exact_transfer"]:
        reasons.append("crl1_exact_transfer")
    if record["candidate_source"] == "p1a":
        reasons.append("existing_p1a_candidate")
    if not reasons:
        reasons.append("deterministic_person_story_link")
    return reasons


def compute_components(selected: list[dict[str, Any]]) -> list[list[str]]:
    graph: dict[str, set[str]] = defaultdict(set)
    for record in selected:
        story_node = f"story:{record['entry_id']}"
        for person_id in record["linked_person_ids"]:
            person_node = f"person:{person_id}"
            graph[story_node].add(person_node)
            graph[person_node].add(story_node)
    components: list[list[str]] = []
    unseen = set(graph)
    while unseen:
        start = sorted(unseen)[0]
        stack = [start]
        component: set[str] = set()
        while stack:
            node = stack.pop()
            if node in component:
                continue
            component.add(node)
            unseen.discard(node)
            stack.extend(graph[node] - component)
        components.append(sorted(component))
    return sorted(components, key=lambda component: (len(component), component))


def build(root: Path = ROOT) -> dict[str, Any]:
    global ROOT
    ROOT = root.resolve()
    inputs = load_inputs()
    candidates = candidate_report(inputs)
    selected_ids = select_gold(candidates)
    candidates_by_id = {record["entry_id"]: record for record in candidates}
    selected_records: list[dict[str, Any]] = []
    for entry_id in selected_ids:
        record = candidates_by_id[entry_id]
        selected_records.append(
            {
                "entry_id": entry_id,
                "selection_status": "gold_anchor" if entry_id == "06-yaliang-019" else "candidate_for_review",
                "selection_reason_codes": selection_reason_codes(record),
                "linked_person_ids": record["linked_person_ids"],
                "reading_layer_status": {
                    "punctuation_status": record["punctuation_status"],
                    "punctuation_basis": record["punctuation_basis"],
                    "exact_transfer": record["exact_transfer"],
                    "story_reader_ready": record["reader_ready"],
                },
            }
        )

    selected_candidate_records = [candidates_by_id[item["entry_id"]] for item in selected_records]
    per_person = {person_id: 0 for person_id in PRIMARY_PERSON_IDS + SUPPORTING_PERSON_IDS}
    per_person_main_text = {person_id: 0 for person_id in PRIMARY_PERSON_IDS + SUPPORTING_PERSON_IDS}
    for record in selected_candidate_records:
        for person_id in record["linked_person_ids"]:
            per_person[person_id] = per_person.get(person_id, 0) + 1
        for person_id in record["main_text_person_ids"]:
            per_person_main_text[person_id] = per_person_main_text.get(person_id, 0) + 1
    multi_person_count = sum(len(record["linked_person_ids"]) >= 2 for record in selected_candidate_records)
    main_text_story_count = sum(bool(record["main_text_person_ids"]) for record in selected_candidate_records)
    annotation_only_story_count = sum(
        bool(record["liu_annotation_only_person_ids"]) and not bool(record["main_text_person_ids"])
        for record in selected_candidate_records
    )
    components = compute_components(selected_candidate_records)
    represented_person_ids = {
        person_id
        for record in selected_candidate_records
        for person_id in record["linked_person_ids"]
    }
    direct_relations = [
        relation
        for relation in inputs["relations"]
        if relation.get("review_status") == "reviewed"
        and relation.get("relation_basis") == "direct"
        and relation.get("subject_id") in represented_person_ids
        and relation.get("object_id") in represented_person_ids
    ]
    derived_relations = [
        relation
        for relation in inputs["relations"]
        if relation.get("review_status") == "reviewed"
        and relation.get("relation_basis") == "derived"
        and relation.get("subject_id") in represented_person_ids
        and relation.get("object_id") in represented_person_ids
    ]
    connectivity = {
        "candidate_count": len(candidates),
        "candidate_records": candidates,
        "gold_set_count": len(selected_records),
        "gold_set_entry_ids": selected_ids,
        "unique_person_count": len({p for record in selected_candidate_records for p in record["linked_person_ids"]}),
        "story_person_link_count": sum(len(record["linked_person_ids"]) for record in selected_candidate_records),
        "multi_person_story_count": multi_person_count,
        "main_text_story_count": main_text_story_count,
        "annotation_only_story_count": annotation_only_story_count,
        "per_person_story_counts": per_person,
        "per_person_main_text_story_counts": per_person_main_text,
        "bipartite_components": components,
        "main_component_count": len(components),
        "covered_direct_relation_ids": [relation["id"] for relation in direct_relations],
        "covered_direct_relation_count": len(direct_relations),
        "covered_derived_relation_ids": [relation["id"] for relation in derived_relations],
        "covered_derived_relation_count": len(derived_relations),
    }
    write_json(root / CONNECTIVITY_PATH.relative_to(ROOT), {
        "schema": 1,
        "stage": "sc0-story-chain-connectivity",
        "work": "世說新語",
        "generated_from": ["data/derived/person-story-links.json", "data/derived/person-story-index.json"],
        **connectivity,
    })

    gold_document = {
        "schema": 1,
        "stage": "sc0-story-chain-gold-set",
        "work": "世說新語",
        "generated_from": [
            "data/derived/person-story-links.json",
            "data/derived/person-story-index.json",
            "data/derived/shishuo-reading-layer.json",
        ],
        "selection_policy": "Small connected factual/editorial pilot; main-text presence preferred; no relations or participation are inferred.",
        "records": selected_records,
    }
    write_json(root / GOLD_PATH.relative_to(ROOT), gold_document)

    chain_records = []
    for record in selected_records:
        candidate = candidates_by_id[record["entry_id"]]
        chain_records.append(
            {
                "entry_id": record["entry_id"],
                "global_ordinal": inputs["entry_by_id"][record["entry_id"]]["global_ordinal"],
                "linked_person_ids": record["linked_person_ids"],
                "reader_ready": record["reading_layer_status"]["story_reader_ready"],
                "punctuation_status": record["reading_layer_status"]["punctuation_status"],
                "punctuation_basis": record["reading_layer_status"]["punctuation_basis"],
                "exact_transfer": record["reading_layer_status"]["exact_transfer"],
                "main_text_person_ids": candidate["main_text_person_ids"],
                "liu_annotation_only_person_ids": candidate["liu_annotation_only_person_ids"],
            }
        )
    person_story_refs: dict[str, list[str]] = defaultdict(list)
    for record in chain_records:
        for person_id in record["linked_person_ids"]:
            person_story_refs[person_id].append(record["entry_id"])
    chain_index = {
        "schema": 1,
        "stage": "sc0-story-chain-gold-index",
        "work": "世說新語",
        "generated_from": "data/story-chain-gold-set.json",
        "story_count": len(chain_records),
        "stories": chain_records,
        "person_story_refs": [
            {"person_id": person_id, "entry_ids": sorted(entry_ids, key=lambda eid: inputs["entry_by_id"][eid]["global_ordinal"])}
            for person_id, entry_ids in sorted(person_story_refs.items())
        ],
    }
    write_json(root / CHAIN_INDEX_PATH.relative_to(ROOT), chain_index)

    write_review(root, inputs, selected_records, candidates_by_id, connectivity)
    return {
        "candidate_count": len(candidates),
        "gold_set_count": len(selected_records),
        "gold_set_entry_ids": selected_ids,
        "reader_ready_count": sum(item["reading_layer_status"]["story_reader_ready"] for item in selected_records),
        "exact_transfer_count": sum(item["reading_layer_status"]["exact_transfer"] for item in selected_records),
        "multi_person_story_count": multi_person_count,
        "component_count": len(components),
        "per_person_story_counts": per_person,
        "per_person_main_text_story_counts": per_person_main_text,
        "main_text_story_count": main_text_story_count,
        "annotation_only_story_count": annotation_only_story_count,
    }


def write_review(
    root: Path,
    inputs: Mapping[str, Any],
    selected_records: list[dict[str, Any]],
    candidates_by_id: Mapping[str, dict[str, Any]],
    connectivity: Mapping[str, Any],
) -> None:
    people = inputs["people"]
    entry_by_id = inputs["entry_by_id"]
    punctuation_by_id = inputs["punctuation"]
    lines = [
        "# SC0 Story Chain Gold Set Review",
        "",
        "本文件由 `scripts/build_story_chain_gold.py` 确定性生成。SC0 只选择已有 PersonStoryLink 支持的故事，并准备句读人工审核包；它不新增人物、关系、参与者判断或历史解释。",
        "",
        f"- selected Stories: {len(selected_records)}",
        f"- candidate Stories examined: {connectivity['candidate_count']}",
        f"- Story↔Person links in Gold Set: {connectivity['story_person_link_count']}",
        f"- multi-Person Stories: {connectivity['multi_person_story_count']}",
        f"- bipartite connected components: {connectivity['main_component_count']}",
        f"- covered reviewed direct Relations: {connectivity['covered_direct_relation_count']} ({', '.join(connectivity['covered_direct_relation_ids'])})",
        f"- covered reviewed derived Relations (display/audit only): {connectivity['covered_derived_relation_count']} ({', '.join(connectivity['covered_derived_relation_ids']) or 'none'})",
        "- existing reviewed anchor: `06-yaliang-019`",
        "- newly proposed records remain `candidate_for_review`; this build does not self-certify human review.",
        "",
    ]
    for selected in selected_records:
        entry_id = selected["entry_id"]
        candidate = candidates_by_id[entry_id]
        entry = entry_by_id[entry_id]
        punctuation = punctuation_by_id[entry_id]
        section = punctuation.get("sections", {}).get("main_text", {})
        path = root / entry["path"]
        canonical = canonical_main_text(path)
        linked_names = [people[pid]["canonical_name"] for pid in selected["linked_person_ids"]]
        main_names = [people[pid]["canonical_name"] for pid in candidate["main_text_person_ids"]]
        annotation_names = [people[pid]["canonical_name"] for pid in candidate["liu_annotation_only_person_ids"]]
        alignment = punctuation.get("alignment", {})
        lines.extend(
            [
                f"## {entry_id} · {candidate.get('chapter_heading', entry.get('chapter_heading', ''))}",
                "",
                f"- selection_status: `{selected['selection_status']}`",
                f"- linked Persons: {'、'.join(linked_names) or '（无）'}",
                f"- main-text Persons: {'、'.join(main_names) or '（无）'}",
                f"- Liu-annotation-only Persons: {'、'.join(annotation_names) or '（无）'}",
                f"- selection reasons: {', '.join(selected['selection_reason_codes'])}",
                f"- punctuation: `{punctuation.get('status')}` / `{punctuation.get('punctuation_basis')}`",
                f"- exact_transfer: `{punctuation.get('exact_transfer')}`",
                f"- alignment: `{alignment.get('alignment_class')}` / `{', '.join(alignment.get('reason_codes', []))}`",
                f"- round-trip: `{'pass' if section.get('punctuated_text') and strip_display_punctuation(section['punctuated_text']) == strip_display_punctuation(canonical) else 'not_available_or_failed'}`",
                f"- canonical: {canonical}",
                f"- proposed punctuated reading: {section.get('punctuated_text') or '（无安全候选）'}",
                f"- reference A: `sources/local/shishuo/reference-txt/shishuo.txt` (punctuation guidance; SHA-256 `{next((item.get('sha256') for item in punctuation.get('references', []) if item.get('witness_id') == 'shishuo-local-reference-txt'), 'unavailable')}`)",
                f"- reference B: `content/processed/shishuo/collation/wikisource-sbck/{entry_id.split('-', 2)[1]}.md` (character/structure comparison; SHA-256 `{next((item.get('sha256') for item in punctuation.get('references', []) if item.get('witness_id') == 'shishuo-wikisource-sbck'), 'unavailable')}`; no sentence punctuation)",
                "- ambiguity notes: machine candidate only; human approval is required before `reviewed` or `reader_ready` promotion.",
                "",
            ]
        )
    (root / REVIEW_PATH.relative_to(ROOT)).parent.mkdir(parents=True, exist_ok=True)
    (root / REVIEW_PATH.relative_to(ROOT)).write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    print(json.dumps(build(), ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
