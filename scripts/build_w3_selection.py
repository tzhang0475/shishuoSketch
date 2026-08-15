#!/usr/bin/env python3
"""Freeze the evidence-led W3 early Wei--Jin Person/Story selection.

W3 is deliberately a separate wave from M2.  The selected candidate IDs are
validated against the current P3A.1 artifact; scores, Story coverage, and
publication safety are derived from repository data and written into frozen
manifests.  No canonical source or existing publication manifest is edited.
"""

from __future__ import annotations

from collections import defaultdict
import hashlib
import json
from pathlib import Path
import re
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[1]
RANKING_INPUT = Path("data/derived/m2-person-expansion-ranking.json")
CANDIDATES_INPUT = Path("data/derived/person-identity-candidates.json")
OCCURRENCES_INPUT = Path("data/derived/person-candidate-occurrences.json")
CORPUS_INPUT = Path("data/shishuo-corpus-index.json")
PUNCTUATION_INPUT = Path("data/annotation/wp1-punctuation.json")
SOURCES_INPUT = Path("data/sources/wp1-sources.json")
SC1_INPUT = Path("data/derived/sc1-site.json")
GOLD_INPUT = Path("data/story-chain-gold-set.json")
M2_STORY_INPUT = Path("data/annotation/story-expansion-wave-1.json")

RANKING_OUTPUT = Path("data/derived/w3-person-expansion-ranking.json")
PERSON_WAVE_OUTPUT = Path("data/annotation/person-expansion-wave-3.json")
STORY_WAVE_OUTPUT = Path("data/annotation/story-expansion-wave-3.json")
COVERAGE_OUTPUT = Path("data/derived/c0-chronological-coverage.json")
REPORT_OUTPUT = Path("docs/c0-chronological-rebalance.md")

W3_PERSON_IDS = (
    "candidate-identity-033-liezhuan-001-93b1bfca17d8",  # 王祥
    "candidate-identity-033-liezhuan-005-ccf5f05810a6",  # 石苞
    "candidate-identity-034-liezhuan-001-2b4236eeee0a",  # 羊祜
    "candidate-identity-034-liezhuan-002-7bb7ba6f844a",  # 杜預
    "candidate-identity-036-liezhuan-002-b1d572be1e4a",  # 張華
    "candidate-identity-040-liezhuan-001-ffebaca31d7e",  # 賈充
    "candidate-identity-042-liezhuan-002-cb6970863171",  # 王濬
    "candidate-identity-043-liezhuan-001-b702608188dc",  # 山濤
    "candidate-identity-043-liezhuan-004-5488b610cb09",  # 樂廣
    "candidate-identity-049-liezhuan-001-cf9d5c7575f0",  # 阮籍
    "candidate-identity-049-liezhuan-002-f6c40f973e49",  # 嵇康
    "candidate-identity-049-liezhuan-004-e600e5725582",  # 劉伶
    "candidate-identity-055-liezhuan-002-18d531a477c2",  # 潘岳
    "candidate-identity-068-liezhuan-001-9f8cdd2f3404",  # 顧榮
    "candidate-identity-072-liezhuan-001-cb69da4fc658",  # 郭璞
)
W3_STORY_TARGET = 24
# Current deterministic provenance audit result.  This is a withheld Story
# record, not a publication-selection shortcut; its local supplemental
# witness is intentionally absent from the registered production witnesses.
W3_WITHHELD_STORY_IDS = ("18-qiyi-002",)


def read(path: Path) -> Any:
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


def write(path: Path, value: Any) -> None:
    target = ROOT / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def sha256(path: Path) -> str:
    return hashlib.sha256((ROOT / path).read_bytes()).hexdigest()


def candidate_volume(candidate_id: str) -> int | None:
    match = re.match(r"candidate-identity-(\d+)-", candidate_id)
    return int(match.group(1)) if match else None


def phase_for_volume(volume: int | None) -> tuple[str, str]:
    """Use Jinshu biography volume as a cautious phase-level orientation."""

    if volume is None:
        return "unknown", ""
    if volume <= 36:
        return "phase-1", "漢末餘緒／魏初"
    if volume <= 43:
        return "phase-2", "正始與曹魏後期"
    if volume <= 55:
        return "phase-3", "竹林—西晉初"
    if volume <= 68:
        return "phase-4", "西晉後期—永嘉南渡"
    return "phase-5", "東晉"


def story_phase(candidate_ids: set[str]) -> tuple[str, str]:
    values = [candidate_volume(item) for item in candidate_ids]
    values = [item for item in values if item is not None]
    return phase_for_volume(min(values) if values else None)


def _selected_candidate_rows() -> tuple[dict[str, Mapping[str, Any]], dict[str, Mapping[str, Any]]]:
    ranking = read(RANKING_INPUT)
    candidates_doc = read(CANDIDATES_INPUT)
    ranking_rows = {
        str(item["candidate_id"]): item
        for item in ranking.get("candidates", [])
        if isinstance(item, Mapping) and isinstance(item.get("candidate_id"), str)
    }
    candidate_rows = {
        str(item["candidate_id"]): item
        for item in candidates_doc.get("candidates", [])
        if isinstance(item, Mapping) and isinstance(item.get("candidate_id"), str)
    }
    missing = [item for item in W3_PERSON_IDS if item not in ranking_rows or item not in candidate_rows]
    if missing:
        raise ValueError(f"W3 selected candidate is absent from current identity artifacts: {missing}")
    for candidate_id in W3_PERSON_IDS:
        candidate = candidate_rows[candidate_id]
        if candidate.get("status") != "strong_candidate" or candidate.get("materialization_state") != "new_candidate":
            raise ValueError(f"W3 candidate is not a new strong identity candidate: {candidate_id}")
        if not candidate.get("identity_evidence_ids"):
            raise ValueError(f"W3 candidate has no identity evidence: {candidate_id}")
    return ranking_rows, candidate_rows


def build_person_ranking() -> dict[str, Any]:
    ranking_rows, candidates = _selected_candidate_rows()
    rows: list[dict[str, Any]] = []
    selected_set = set(W3_PERSON_IDS)
    for candidate_id, row in sorted(ranking_rows.items()):
        candidate = candidates.get(candidate_id)
        if candidate is None:
            continue
        metrics = candidate.get("metrics", {})
        volume = candidate_volume(candidate_id)
        phase_id, phase_label = phase_for_volume(volume)
        main_count = int(metrics.get("shishuo_main_story_count", 0))
        identity_quality = float(metrics.get("identity_evidence_quality", 0.0))
        citation_ratio = float(metrics.get("annotation_citation_author_ratio", 0.0))
        # This is a W3 selection score, not a replacement for P3A/M2 score.
        w3_score = round(
            main_count * 4.0
            + identity_quality * 8.0
            + (2.0 if phase_id in {"phase-1", "phase-2", "phase-3"} else 0.0)
            - citation_ratio * 10.0,
            6,
        )
        rows.append(
            {
                "candidate_id": candidate_id,
                "preferred_name": candidate.get("preferred_name", ""),
                "status": candidate.get("status"),
                "eligible": candidate_id in selected_set,
                "selected": candidate_id in selected_set,
                "rank": 0,
                "w3_score": w3_score,
                "score": w3_score,
                "phase_id": phase_id,
                "phase_label": phase_label,
                "components": {
                    "chronological_gap_value": 2.0 if phase_id in {"phase-1", "phase-2", "phase-3"} else 0.0,
                    "main_text_story_coverage": main_count,
                    "identity_evidence_quality": identity_quality,
                    "annotation_citation_penalty": round(citation_ratio * 10.0, 6),
                },
                "metrics": dict(metrics),
                "source_p3a_score": row.get("score"),
                "main_text_story_ids": list(candidate.get("shishuo_story_ids", [])),
                "identity_evidence_ids": list(candidate.get("identity_evidence_ids", [])),
                "risk_flags": list(candidate.get("risk_flags", [])),
            }
        )
    selected = sorted(
        [row for row in rows if row["selected"]],
        key=lambda item: (candidate_volume(str(item["candidate_id"])) or 10**9, str(item["candidate_id"])),
    )
    for rank, row in enumerate(selected, 1):
        row["rank"] = rank
    selected_ids = [str(item["candidate_id"]) for item in selected]
    output = {
        "schema": 1,
        "stage": "w3-early-weijin-person-expansion-ranking",
        "ranking_version": "w3-c0-v1",
        "generated_from": [str(RANKING_INPUT), str(CANDIDATES_INPUT)],
        "source_ranking_sha256": sha256(RANKING_INPUT),
        "selection_policy": "chronological phase gap + main-text coverage + identity quality, with annotation-citation penalty; frozen 15-person evidence-safe bridge roster",
        "selected_candidate_ids": selected_ids,
        "selected_person_count": len(selected_ids),
        "candidates": sorted(rows, key=lambda item: (not item["selected"], item["rank"] if item["selected"] else 10**9, str(item["candidate_id"]))),
    }
    write(RANKING_OUTPUT, output)
    return output


def build_person_wave(ranking: Mapping[str, Any]) -> dict[str, Any]:
    rows = {str(item["candidate_id"]): item for item in ranking["candidates"] if item.get("selected")}
    records = []
    for rank, candidate_id in enumerate(ranking["selected_candidate_ids"], 1):
        row = rows[candidate_id]
        records.append(
            {
                "candidate_id": candidate_id,
                "rank_at_selection": rank,
                "preferred_name": row["preferred_name"],
                "person_id": f"person-{35 + rank:03d}",
                "candidate_status": "strong_candidate",
                "materialization_status": "pending",
                "review_status": "candidate",
                "w3_score": row["w3_score"],
                "w3_phase_id": row["phase_id"],
                "w3_phase_label": row["phase_label"],
                "selection_reasons": [
                    "current production scope lacks a materialized identity for this strong candidate",
                    f"main-text coverage: {row['metrics'].get('shishuo_main_story_count', 0)} Stories",
                    f"chronological bridge: {row['phase_label'] or 'phase uncertain'}",
                ],
                "evidence_ids": sorted(set(row.get("identity_evidence_ids", []))),
                "risk_flags": list(row.get("risk_flags", [])),
            }
        )
    output = {
        "schema": 1,
        "stage": "p3b-materialization-wave",
        "wave_id": "w3-early-weijin-person-wave-1",
        "source_ranking_artifact": str(RANKING_OUTPUT),
        "source_ranking_sha256": sha256(RANKING_OUTPUT),
        "selection_policy": "W3 C0 chronological rebalance; IDs are allocated in the frozen phase order and never derived from names.",
        "members": records,
    }
    write(PERSON_WAVE_OUTPUT, output)
    return output


def safe_story_ids(
    selected_candidate_ids: set[str],
) -> tuple[dict[str, set[str]], dict[str, Mapping[str, Any]], set[str]]:
    occurrences = read(OCCURRENCES_INPUT).get("occurrences", [])
    punctuation = {str(item["entry_id"]): item for item in read(PUNCTUATION_INPUT).get("records", [])}
    candidate_evidence = {
        str(item.get("id")): item
        for item in read(CANDIDATES_INPUT).get("evidence", [])
        if isinstance(item, Mapping) and isinstance(item.get("id"), str)
    }
    registered_witnesses = {
        str(item.get("witness_id"))
        for item in read(SOURCES_INPUT).get("records", [])
        if isinstance(item, Mapping) and item.get("witness_id")
    }

    def registered_source_occurrence(occurrence: Mapping[str, Any]) -> bool:
        evidence_ids = [str(item) for item in occurrence.get("evidence_ids", [])]
        if not evidence_ids:
            return False
        for evidence_id in evidence_ids:
            evidence = candidate_evidence.get(evidence_id)
            witness_id = (
                evidence.get("locator", {})
                .get("source_provenance", {})
                .get("witness_id")
                if isinstance(evidence, Mapping)
                else None
            )
            if witness_id not in registered_witnesses:
                return False
        return True

    # W3 selection is evaluated against the frozen pre-W3 experience layer,
    # not against a later bundle that already contains this wave.
    current = {
        *[str(item.get("entry_id")) for item in read(GOLD_INPUT).get("records", [])],
        *[str(item.get("story_id")) for item in read(M2_STORY_INPUT).get("records", [])],
    }
    by_story: dict[str, set[str]] = defaultdict(set)
    unsafe_story_ids: set[str] = set()
    for occurrence in occurrences:
        if occurrence.get("candidate_id") not in selected_candidate_ids or occurrence.get("section") != "main_text":
            continue
        if not registered_source_occurrence(occurrence):
            # Keep the Story in the deterministic selection calculation so a
            # later provenance correction cannot silently substitute a
            # different Story.  It is removed from the frozen publication
            # records below rather than being relabeled as registered text.
            unsafe_story_ids.add(str(occurrence.get("source_id", "")))
        story_id = str(occurrence.get("source_id", ""))
        if story_id in current:
            continue
        main = punctuation.get(story_id, {}).get("sections", {}).get("main_text", {})
        if punctuation.get(story_id, {}).get("status") not in {"reviewed", "candidate", "aligned"}:
            continue
        if not main.get("punctuated_text"):
            continue
        by_story[story_id].add(str(occurrence["candidate_id"]))
    return by_story, punctuation, unsafe_story_ids


def choose_stories(selected_candidate_ids: set[str]) -> list[dict[str, Any]]:
    by_story, punctuation, unsafe_story_ids = safe_story_ids(selected_candidate_ids)
    corpus = {str(item["id"]): item for item in read(CORPUS_INPUT).get("entries", [])}
    if not by_story:
        raise ValueError("W3 has no safe unpublished Story candidates")
    selected: list[str] = []
    covered: set[str] = set()
    # Guarantee at least one readable main-text entrance for every selected
    # identity before optimizing bridges and chapter diversity.
    for candidate_id in sorted(selected_candidate_ids, key=lambda item: (candidate_volume(item) or 10**9, item)):
        candidates = [story for story, ids in by_story.items() if candidate_id in ids]
        story_id = min(candidates, key=lambda item: (int(corpus.get(item, {}).get("global_ordinal", 10**9)), item))
        if story_id not in selected:
            selected.append(story_id)
            covered.update(by_story[story_id])

    def score(story_id: str) -> tuple[float, str]:
        ids = by_story[story_id]
        new_people = len(ids - covered)
        bridge = 12.0 if len(ids) >= 2 else 0.0
        chapter = str(story_id.split("-", 1)[0])
        chapter_bonus = 1.5 if chapter not in {item.split("-", 1)[0] for item in selected} else 0.0
        early_bonus = max(0.0, 2.0 - float(corpus.get(story_id, {}).get("global_ordinal", 10**9)) / 1000.0)
        return (new_people * 20.0 + bridge + chapter_bonus + early_bonus + len(ids) * 2.0, story_id)

    while len(selected) < W3_STORY_TARGET:
        remaining = [story for story in by_story if story not in selected]
        if not remaining:
            break
        story_id = max(remaining, key=score)
        selected.append(story_id)
        covered.update(by_story[story_id])

    selected.sort(key=lambda item: (int(corpus.get(item, {}).get("global_ordinal", 10**9)), item))
    if len(selected) < W3_STORY_TARGET:
        raise ValueError(f"W3 safe Story pool has only {len(selected)} records")
    selected = [item for item in selected if item not in unsafe_story_ids]
    if not 20 <= len(selected) <= 30:
        raise ValueError(
            f"W3 evidence-safe Story selection has {len(selected)} records after provenance withholding"
        )
    records: list[dict[str, Any]] = []
    for rank, story_id in enumerate(selected, 1):
        phase_id, phase_label = story_phase(by_story[story_id])
        main = punctuation[story_id].get("sections", {}).get("main_text", {})
        records.append(
            {
                "story_id": story_id,
                "selection_rank": rank,
                "publication_state": "preview_ready" if punctuation[story_id].get("status") != "reviewed" else "production_ready",
                "review_status": "candidate",
                "phase_id": phase_id,
                "phase_label": phase_label,
                "source_candidate_ids": sorted(by_story[story_id]),
                "selection_score": round(max(0.0, float(score(story_id)[0])), 6),
                "selection_reasons": [
                    "main-text Person entrance for the chronological expansion wave",
                    "multi-Person bridge Story" if len(by_story[story_id]) >= 2 else "representative single-Person narrative entrance",
                    f"phase orientation: {phase_label}" if phase_label else "phase omitted because evidence is insufficient",
                ],
                "evidence_ids": [],
                "punctuation_status": punctuation[story_id].get("status"),
                "canonical_main_text_sha256": hashlib.sha256(str(main.get("punctuated_text", "")).encode("utf-8")).hexdigest(),
            }
        )
    return records


def build_story_wave(story_records: list[dict[str, Any]]) -> dict[str, Any]:
    gold_ids = [str(item["entry_id"]) for item in read(GOLD_INPUT).get("records", [])]
    output = {
        "schema": 1,
        "stage": "w3-story-expansion-wave",
        "wave_id": "w3-early-weijin-story-wave-1",
        "gold_story_ids": gold_ids,
        "expansion_story_ids": [str(item["story_id"]) for item in story_records],
        "selection_policy": "C0 chronological rebalance over unpublished main-text entrances, followed by strict registered-witness provenance filtering; no disputed or supplemental-only Story is force-published.",
        "selection_status": "24 ranked Story slots were audited; records requiring an unregistered supplemental witness are withheld after ranking rather than replaced by a weaker quota filler.",
        "withheld_story_ids": list(W3_WITHHELD_STORY_IDS),
        "records": story_records,
        "source_artifacts": [str(RANKING_OUTPUT), str(OCCURRENCES_INPUT), str(PUNCTUATION_INPUT)],
    }
    write(STORY_WAVE_OUTPUT, output)
    return output


def build_coverage(person_ranking: Mapping[str, Any], story_wave: Mapping[str, Any]) -> dict[str, Any]:
    people = read(Path("data/people.json")).get("people", [])
    current = read(SC1_INPUT)
    current_stories = [item for item in current.get("stories", []) if item.get("publication_state") != "blocked"]
    w3_ids = {str(item.get("story_id")) for item in story_wave.get("records", [])}

    # Rebuilds must not depend on Git history.  The clean pre-W3 scope is
    # defined by the frozen SC0 and M2 manifests, so the report remains stable
    # after W3 itself is committed and HEAD advances.
    baseline_story_ids = {
        *[str(item["entry_id"]) for item in read(GOLD_INPUT).get("records", [])],
        *[str(item["story_id"]) for item in read(M2_STORY_INPUT).get("records", [])],
    }
    current_story_ids = {str(item.get("id")) for item in current_stories}
    if baseline_story_ids <= current_story_ids:
        before_stories = [item for item in current_stories if str(item.get("id")) in baseline_story_ids]
        stories = current_stories
        before_people = len(people) - len(person_ranking["selected_candidate_ids"]) if w3_ids else len(people)
    else:
        # This branch supports a clean pre-W3 checkout while the selection is
        # being prepared; it does not synthesize Story records.
        before_stories = current_stories
        before_people = len(people)
        stories = current_stories + [
            item for item in story_wave.get("records", [])
            if str(item.get("story_id")) not in current_story_ids
        ]

    def phase_counts(items: list[Mapping[str, Any]]) -> dict[str, int]:
        counts: dict[str, int] = defaultdict(int)
        for story in items:
            counts[str(story.get("period_id") or story.get("phase_id") or "unknown")] += 1
        return dict(sorted(counts.items()))

    before = {
        "production_person_count": before_people,
        "published_story_count": len(before_stories),
        "phase_counts": phase_counts(before_stories),
        "uncertain_story_count": phase_counts(before_stories).get("unknown", 0),
        "method": "current bundle phase labels where present; unknown is preserved rather than guessed",
    }
    after_phase = phase_counts(stories)
    person_phases = defaultdict(set)
    for row in person_ranking["candidates"]:
        if row.get("selected"):
            person_phases[str(row.get("phase_id") or "unknown")].add(str(row.get("preferred_name")))
    after = {
        "production_person_count": len(people) if stories is current_stories else len(people) + len(person_ranking["selected_candidate_ids"]),
        "published_story_count": len(stories),
        "phase_counts": after_phase,
        "selected_person_phase_counts": {key: len(value) for key, value in sorted(person_phases.items())},
    }
    output = {
        "schema": 1,
        "stage": "c0-chronological-coverage",
        "generated_from": [str(SC1_INPUT), str(RANKING_OUTPUT), str(STORY_WAVE_OUTPUT)],
        "phase_definitions": {
            "phase-1": "漢末餘緒／魏初",
            "phase-2": "正始與曹魏後期",
            "phase-3": "竹林—西晉初",
            "phase-4": "西晉後期—永嘉南渡",
            "phase-5": "東晉",
            "unknown": "",
        },
        "before": before,
        "after_projection": after,
        "notes": [
            "C0 phase labels are product orientation bands, not exact dates or a definitive periodization.",
            "The current bundle is strongly Eastern-Jin weighted; W3 adds evidence-safe early and Western-Jin bridges.",
        ],
    }
    write(COVERAGE_OUTPUT, output)
    return output


def write_report(ranking: Mapping[str, Any], story_wave: Mapping[str, Any], coverage: Mapping[str, Any]) -> None:
    lines = [
        "# C0 Chronological Rebalance / W3 selection",
        "",
        "W3 uses a separate frozen Person and Story wave. It does not alter SC0, M2 manifests, canonical source text, or existing Person IDs.",
        "",
        "## Phase bands",
        "",
        "| Phase | Product orientation | Basis |",
        "|---|---|---|",
        "| phase-1 | 漢末餘緒／魏初 | processed identity evidence volume range |",
        "| phase-2 | 正始與曹魏後期 | processed identity evidence volume range |",
        "| phase-3 | 竹林—西晉初 | processed identity evidence volume range |",
        "| phase-4 | 西晉後期—永嘉南渡 | processed identity evidence volume range |",
        "| phase-5 | 東晉 | processed identity evidence volume range |",
        "",
        "Unknown bands are omitted from reader-facing orientation rather than displayed as 未詳.",
        "",
        "## Coverage before / projected after",
        "",
        f"- Persons: {coverage['before']['production_person_count']} → {coverage['after_projection']['production_person_count']}",
        f"- published Stories: {coverage['before']['published_story_count']} → {coverage['after_projection']['published_story_count']}",
        f"- selected W3 Persons: {len(ranking['selected_candidate_ids'])}",
        f"- selected W3 Stories: {len(story_wave['records'])}",
        "",
        "## Frozen W3 Persons",
        "",
        "| Rank | New Person ID | Name | Phase | Main-text Story count |",
        "|---:|---|---|---|---:|",
    ]
    for index, candidate_id in enumerate(ranking["selected_candidate_ids"], 1):
        row = next(item for item in ranking["candidates"] if item["candidate_id"] == candidate_id)
        lines.append(f"| {index} | person-{35 + index:03d} | {row['preferred_name']} | {row['phase_label'] or '—'} | {row['metrics'].get('shishuo_main_story_count', 0)} |")
    lines.extend(["", "## Frozen W3 Stories", ""])
    for record in story_wave["records"]:
        lines.append(f"- `{record['story_id']}` · {record.get('phase_label') or 'phase omitted'} · {', '.join(record['selection_reasons'])}")
    lines.extend([
        "",
        "## Safety boundary",
        "",
        "Only strong identity candidates with existing Shishuo main-text evidence and safe punctuation records entered the wave. Disputed punctuation and ambiguous identity candidates were not used to fill a quota. Sanguozhi is processed as SGZ0 evidence infrastructure; it does not create Persons, Relations, or a global chronology in C0.",
        "",
        "## Phase coverage before / after",
        "",
        "The clean pre-W3 scope preserves phase uncertainty rather than assigning guessed dates. After the evidence-safe W3 projection, the product has the following phase-level orientation counts:",
        "",
    ])
    for phase_id, label in (
        ("phase-1", "漢末餘緒／魏初"),
        ("phase-2", "正始與曹魏後期"),
        ("phase-3", "竹林—西晉初"),
        ("phase-4", "西晉後期—永嘉南渡"),
        ("phase-5", "東晉"),
        ("unknown", "unknown"),
    ):
        lines.append(f"- {label}: {coverage['after_projection']['phase_counts'].get(phase_id, 0)} Stories")
    lines.extend([
        "",
        "The initial 24 ranked Story slots yielded 23 published records after `18-qiyi-002` was withheld: its only local witness is an unregistered supplemental payload. The Story remains canonical and searchable; its source was not relabeled as the registered WYG witness.",
    ])
    (ROOT / REPORT_OUTPUT).parent.mkdir(parents=True, exist_ok=True)
    (ROOT / REPORT_OUTPUT).write_text("\n".join(lines), encoding="utf-8")


def build() -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]]:
    ranking = build_person_ranking()
    wave = build_person_wave(ranking)
    stories = build_story_wave(choose_stories(set(ranking["selected_candidate_ids"])))
    coverage = build_coverage(ranking, stories)
    write_report(ranking, stories, coverage)
    return ranking, wave, stories, coverage


if __name__ == "__main__":
    ranking, wave, stories, coverage = build()
    print(f"built W3 selection: {len(wave['members'])} Persons; {len(stories['records'])} Stories")
