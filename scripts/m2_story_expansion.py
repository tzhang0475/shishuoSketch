#!/usr/bin/env python3
"""Joint deterministic Story selection for the M2A experience layer."""

from __future__ import annotations

from collections import Counter, defaultdict
import hashlib
import json
import math
from pathlib import Path
from typing import Any, Iterable, Mapping

try:
    from .build_six_person_pilot import parse_frontmatter, parse_shishuo_sections
    from .reading_layers import strip_display_punctuation
except ImportError:  # direct execution
    from build_six_person_pilot import parse_frontmatter, parse_shishuo_sections
    from reading_layers import strip_display_punctuation


ROOT = Path(__file__).resolve().parents[1]
CORPUS_INDEX_PATH = Path("data/shishuo-corpus-index.json")
PUNCTUATION_PATH = Path("data/annotation/wp1-punctuation.json")
MENTIONS_PATH = Path("data/mentions/shishuo.json")
PEOPLE_PATH = Path("data/people.json")
GOLD_PATH = Path("data/story-chain-gold-set.json")
WAVE2_PATH = Path("data/annotation/person-expansion-wave-2.json")
PERSON_RANKING_PATH = Path("data/derived/m2-person-expansion-ranking.json")
RANKING_PATH = Path("data/derived/m2-story-expansion-ranking.json")
MANIFEST_PATH = Path("data/annotation/story-expansion-wave-1.json")
REPORT_PATH = Path("docs/m2-story-expansion-ranking.md")

WAVE_ID = "m2-story-expansion-wave-1"
TARGET_EXPANSION_COUNT = 44

WEIGHTS = {
    "multi_person_bridge_value": 0.22,
    "selected_person_coverage": 0.20,
    "existing_person_depth": 0.12,
    "person_sketch_value": 0.14,
    "scene_context_value": 0.10,
    "main_text_identity_quality": 0.08,
    "punctuation_readiness": 0.08,
    "chapter_diversity_bonus": 0.06,
    "isolated_story_penalty": 0.12,
    "liu_only_person_penalty": 0.14,
}


def read_json(root: Path, path: Path) -> Any:
    return json.loads((root / path).read_text(encoding="utf-8"))


def write_json(root: Path, path: Path, value: Any) -> None:
    target = root / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _log_norm(value: int | float, maximum: int | float) -> float:
    if value <= 0 or maximum <= 0:
        return 0.0
    return round(math.log1p(float(value)) / math.log1p(float(maximum)), 8)


def _entry_parts(root: Path, entry: Mapping[str, Any]) -> tuple[dict[str, Any], str, str, list[dict[str, str]]]:
    text = (root / str(entry["path"])).read_text(encoding="utf-8")
    metadata = parse_frontmatter(text)
    main_text = ""
    source_text = ""
    annotations: list[dict[str, str]] = []
    for section, body, section_metadata in parse_shishuo_sections(text):
        if section == "main_text":
            main_text = body
            source_text = body
        elif section == "liu_annotation":
            annotations.append(
                {
                    "id": str(section_metadata.get("annotation_id", f"annotation-{len(annotations)+1:03d}")),
                    "text": body,
                }
            )
    return metadata, main_text, source_text, annotations


def _publication_state(punctuation: Mapping[str, Any], main_text: str) -> str:
    if punctuation.get("status") == "reviewed" and punctuation.get("review_status") == "reviewed":
        return "production_ready"
    main = punctuation.get("sections", {}).get("main_text", {})
    if (
        punctuation.get("status") in {"candidate", "aligned"}
        and isinstance(main.get("punctuated_text"), str)
        and main.get("punctuated_text")
        and strip_display_punctuation(main["punctuated_text"]) == strip_display_punctuation(main_text)
    ):
        return "preview_ready"
    return "blocked"


def _unique(values: Iterable[str]) -> list[str]:
    return sorted({str(value) for value in values if isinstance(value, str) and value})


def build_story_ranking(root: Path = ROOT) -> dict[str, Any]:
    entries = {
        str(item["id"]): item
        for item in read_json(root, CORPUS_INDEX_PATH).get("entries", [])
        if isinstance(item, Mapping) and isinstance(item.get("id"), str)
    }
    punctuation = {
        str(item["entry_id"]): item
        for item in read_json(root, PUNCTUATION_PATH).get("records", [])
        if isinstance(item, Mapping) and isinstance(item.get("entry_id"), str)
    }
    people = {
        str(item["person_id"]): item
        for item in read_json(root, PEOPLE_PATH).get("people", [])
        if isinstance(item, Mapping) and isinstance(item.get("person_id"), str)
    }
    production_ids = set(people)
    gold_ids = [str(item["entry_id"]) for item in read_json(root, GOLD_PATH).get("records", [])]
    gold_set = set(gold_ids)
    wave = read_json(root, WAVE2_PATH)
    wave_person_ids = {
        str(item["person_id"])
        for item in wave.get("members", [])
        if isinstance(item, Mapping) and isinstance(item.get("person_id"), str)
    }
    mentions_by_story: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for mention in read_json(root, MENTIONS_PATH).get("mentions", []):
        if isinstance(mention, Mapping):
            mentions_by_story[str(mention.get("entry_id") or mention.get("source_id"))].append(mention)

    rows: list[dict[str, Any]] = []
    for story_id, entry in sorted(entries.items(), key=lambda item: int(item[1].get("global_ordinal", 10**9))):
        if story_id in gold_set:
            continue
        punctuation_record = punctuation.get(story_id)
        if punctuation_record is None:
            continue
        metadata, main_text, _source_text, annotations = _entry_parts(root, entry)
        state = _publication_state(punctuation_record, main_text)
        story_mentions = mentions_by_story.get(story_id, [])
        main_person_ids = _unique(
            str(mention.get("person_id"))
            for mention in story_mentions
            if mention.get("section") == "main_text" and mention.get("person_id") in production_ids
        )
        annotation_person_ids = _unique(
            str(mention.get("person_id"))
            for mention in story_mentions
            if mention.get("section") == "liu_annotation" and mention.get("person_id") in production_ids
        )
        materialized_ids = sorted(set(main_person_ids) | set(annotation_person_ids))
        selected_main_ids = sorted(set(main_person_ids) & wave_person_ids)
        current_main_ids = sorted(set(main_person_ids) - wave_person_ids)
        main_mentions = [
            mention for mention in story_mentions
            if mention.get("section") == "main_text" and mention.get("person_id") in production_ids
        ]
        exact_main_mentions = [
            mention for mention in main_mentions
            if mention.get("confidence") in {"high", "very_high"}
            and str(mention.get("resolution_method", "")).startswith("exact")
        ]
        chapter = story_id.split("-", 1)[0]
        reader_ready = state != "blocked"
        # A Story with only an annotation Person is still a valid secondary
        # route, but is penalized and cannot outrank a narrative Story merely
        # because citation volume is high.
        liu_only = bool(annotation_person_ids) and not bool(main_person_ids)
        scene_context_value = min(
            1.0,
            (0.55 if annotations else 0.0)
            + (0.25 if len(annotations) >= 2 else 0.0)
            + (0.20 if len(main_person_ids) >= 2 else 0.0),
        )
        row = {
            "story_id": story_id,
            "title": str(metadata.get("chapter_heading", story_id)),
            "chapter": chapter,
            "global_ordinal": int(entry.get("global_ordinal", 10**9)),
            "publication_state": state,
            "eligible": reader_ready and bool(materialized_ids),
            "main_person_ids": main_person_ids,
            "selected_wave_person_ids": selected_main_ids,
            "current_main_person_ids": current_main_ids,
            "annotation_person_ids": annotation_person_ids,
            "materialized_person_ids": materialized_ids,
            "metrics": {
                "main_materialized_person_count": len(main_person_ids),
                "wave2_main_person_count": len(selected_main_ids),
                "current_main_person_count": len(current_main_ids),
                "annotation_materialized_person_count": len(annotation_person_ids),
                "main_mention_count": len(main_mentions),
                "exact_main_mention_count": len(exact_main_mentions),
                "annotation_count": len(annotations),
                "main_text_length": len(main_text),
            },
            "flags": {
                "liu_only_person_path": liu_only,
                "has_scene_context_material": bool(annotations),
                "has_multiple_main_persons": len(main_person_ids) >= 2,
            },
            "components": {},
        }
        rows.append(row)

    max_persons = max((row["metrics"]["main_materialized_person_count"] for row in rows), default=0)
    max_wave_persons = max((row["metrics"]["wave2_main_person_count"] for row in rows), default=0)
    max_main_mentions = max((row["metrics"]["main_mention_count"] for row in rows), default=0)
    for row in rows:
        metrics = row["metrics"]
        state = row["publication_state"]
        components = {
            "multi_person_bridge_value": _log_norm(max(0, len(row["main_person_ids"]) - 1), max(1, max_persons - 1)),
            "selected_person_coverage": _log_norm(len(row["selected_wave_person_ids"]), max_wave_persons),
            "existing_person_depth": _log_norm(len(row["current_main_person_ids"]), max(1, max_persons)),
            "person_sketch_value": _log_norm(len(row["main_person_ids"]), max_persons),
            "scene_context_value": 0.0 if state == "blocked" else (0.55 if row["flags"]["has_scene_context_material"] else 0.0),
            "main_text_identity_quality": (metrics["exact_main_mention_count"] / metrics["main_mention_count"] if metrics["main_mention_count"] else 0.0),
            "punctuation_readiness": {"production_ready": 1.0, "preview_ready": 0.72, "blocked": 0.0}[state],
            "chapter_diversity_bonus": 0.0,
            "isolated_story_penalty": 1.0 if len(row["materialized_person_ids"]) <= 1 else 0.0,
            "liu_only_person_penalty": 1.0 if row["flags"]["liu_only_person_path"] else 0.0,
        }
        row["components"] = {key: round(value, 8) for key, value in components.items()}
        row["base_score"] = round(
            100.0 * (
                sum(
                    WEIGHTS[key] * components[key]
                    for key in WEIGHTS
                    if key not in {"isolated_story_penalty", "liu_only_person_penalty"}
                )
                - WEIGHTS["isolated_story_penalty"] * components["isolated_story_penalty"]
                - WEIGHTS["liu_only_person_penalty"] * components["liu_only_person_penalty"]
            ),
            4,
        )

    # Joint selection: first guarantee one representative Story for every
    # Wave-2 Person that has a safe narrative occurrence, then greedily fill
    # the remaining slots with a small chapter/uncovered-person bonus.
    eligible_rows = [row for row in rows if row["eligible"]]
    selected: list[dict[str, Any]] = []
    selected_ids: set[str] = set()
    represented_wave: set[str] = set()
    represented_chapters: Counter[str] = Counter()

    def best_key(row: Mapping[str, Any]) -> tuple[Any, ...]:
        return (-float(row["base_score"]), -int(row["metrics"]["main_materialized_person_count"]), int(row["global_ordinal"]), str(row["story_id"]))

    for person_id in sorted(wave_person_ids):
        options = [row for row in eligible_rows if person_id in row["selected_wave_person_ids"] and row["story_id"] not in selected_ids]
        if not options:
            continue
        chosen = sorted(options, key=best_key)[0]
        selected.append(chosen)
        selected_ids.add(chosen["story_id"])
        represented_wave.update(chosen["selected_wave_person_ids"])
        represented_chapters[chosen["chapter"]] += 1

    while len(selected) < min(TARGET_EXPANSION_COUNT, len(eligible_rows)):
        remaining = [row for row in eligible_rows if row["story_id"] not in selected_ids]
        if not remaining:
            break
        for row in remaining:
            uncovered = len(set(row["selected_wave_person_ids"]) - represented_wave)
            chapter_bonus = 0.16 if represented_chapters[row["chapter"]] == 0 else 0.0
            row["components"]["chapter_diversity_bonus"] = round(chapter_bonus, 8)
            row["selection_score"] = round(float(row["base_score"]) + 10.0 * chapter_bonus + 2.0 * min(1, uncovered), 4)
        chosen = sorted(
            remaining,
            key=lambda row: (
                -float(row["selection_score"]),
                -float(row["base_score"]),
                int(row["global_ordinal"]),
                str(row["story_id"]),
            ),
        )[0]
        selected.append(chosen)
        selected_ids.add(chosen["story_id"])
        represented_wave.update(chosen["selected_wave_person_ids"])
        represented_chapters[chosen["chapter"]] += 1

    selected.sort(key=lambda row: (int(row["global_ordinal"]), str(row["story_id"])))
    selected_rank_by_id = {row["story_id"]: rank for rank, row in enumerate(selected, start=1)}
    for row in rows:
        row["selected"] = row["story_id"] in selected_ids
        row["selection_rank"] = selected_rank_by_id.get(row["story_id"])
        if row["selected"]:
            reasons = []
            if row["metrics"]["main_materialized_person_count"] >= 2:
                reasons.append("多位已物化人物在正文中形成桥接")
            if row["selected_wave_person_ids"]:
                reasons.append(f"为 Wave 2 人物提供正文故事（{len(row['selected_wave_person_ids'])} 位）")
            if row["metrics"]["current_main_person_count"]:
                reasons.append("加深既有 Person Sketch 的正文路径")
            if row["flags"]["has_scene_context_material"]:
                reasons.append("刘注/结构材料适合继续制作 Scene Card")
            if not reasons:
                reasons.append("满足安全阅读投影并补充章节/网络覆盖")
            row["selection_reasons"] = reasons
        else:
            row["selection_reasons"] = []
        # Keep the interpretable story score in the frozen ranking.  The
        # greedy fill bonus is an ordering aid, not part of the base score
        # reviewers compare across stories.
        row["score"] = round(float(row.get("base_score", 0.0)), 6)
        row.pop("base_score", None)
        row.pop("selection_score", None)

    rows.sort(key=lambda row: (int(row["global_ordinal"]), str(row["story_id"])))
    document = {
        "schema": 1,
        "stage": "m2a-story-experience-ranking",
        "generated_from": [str(CORPUS_INDEX_PATH), str(PUNCTUATION_PATH), str(MENTIONS_PATH), str(PEOPLE_PATH), str(GOLD_PATH), str(WAVE2_PATH), str(PERSON_RANKING_PATH)],
        "weights": WEIGHTS,
        "selection_policy": "Exclude the frozen SC0 Gold Set; require a safe non-blocked reading projection and at least one materialized Person path; choose one representative narrative Story per Wave-2 Person where available, then greedily fill by score with chapter/uncovered-person diversity bonuses.",
        "gold_story_ids": gold_ids,
        "candidate_story_count": len(rows),
        "eligible_story_count": len(eligible_rows),
        "selected_expansion_story_count": len(selected),
        "selected_expansion_story_ids": [row["story_id"] for row in selected],
        "chapter_distribution": dict(sorted(represented_chapters.items())),
        "stories": rows,
        "notes": [
            "SC0 remains unchanged; this artifact is a separate experience publication layer.",
            "Story co-occurrence is a navigation signal only and never creates Relation facts.",
            "Blocked/disputed punctuation Stories are not selected.",
            "Unmaterialized historical figures remain ordinary readable text unless existing production Mention data safely resolves them.",
        ],
    }
    return document


def freeze_manifest(root: Path = ROOT, document: Mapping[str, Any] | None = None) -> dict[str, Any]:
    ranking_path = root / RANKING_PATH
    if document is None:
        document = build_story_ranking(root)
    selected = [row for row in document["stories"] if row.get("selected")]
    manifest = {
        "schema": 1,
        "stage": "m2a-story-expansion-wave",
        "wave_id": WAVE_ID,
        "source_ranking_artifact": str(RANKING_PATH),
        "source_ranking_sha256": sha256_file(ranking_path),
        "gold_story_ids": list(document["gold_story_ids"]),
        "expansion_story_ids": list(document["selected_expansion_story_ids"]),
        "selection_policy": document["selection_policy"],
        "records": [
            {
                "story_id": row["story_id"],
                "selection_rank": row["selection_rank"],
                "score": row["score"],
                "score_components": row["components"],
                "selection_reasons": row["selection_reasons"],
                "publication_state": row["publication_state"],
                "review_status": "candidate",
                "source_entry_id": row["story_id"],
            }
            for row in selected
        ],
        "notes": [
            "SC0 Gold Set is a frozen regression layer and is not rewritten by this manifest.",
            "Expansion publication remains a deterministic union of SC0 and this manifest.",
        ],
    }
    path = root / MANIFEST_PATH
    if path.is_file():
        existing = read_json(root, MANIFEST_PATH)
        if existing != manifest:
            raise ValueError("existing M2 Story expansion manifest differs from deterministic selection")
    else:
        write_json(root, MANIFEST_PATH, manifest)
    return manifest


def render_report(document: Mapping[str, Any]) -> str:
    selected = [row for row in document["stories"] if row.get("selected")]
    lines = [
        "# M2A Story Expansion Ranking",
        "",
        "本报告将冻结的 SC0 16 则 Gold Stories 与独立的 M2 Story Expansion 层分开。它只选择安全、可漫游的阅读投影，不改变 SC0 文件。",
        "",
        "## 摘要",
        "",
        f"- SC0 Gold Stories：**{len(document['gold_story_ids'])}**（冻结不变）",
        f"- Story 候选：**{document['candidate_story_count']}**；安全候选：**{document['eligible_story_count']}**；Expansion：**{len(selected)}**",
        f"- 前端联合集合：**{len(document['gold_story_ids']) + len(selected)}**",
        f"- 章节分布：{', '.join(f'{key}={value}' for key, value in document['chapter_distribution'].items())}",
        "",
        "## 选择纪律",
        "",
        "- 先为有安全正文路径的 Wave 2 人物各选一个代表 Story，再用桥接、Person Sketch 深度、Scene 潜力和章节多样性补齐。",
        "- 争议/阻断句读不发布；preview_ready 仍明确保留候选阅读状态。",
        "- Story 共现是产品导航指标，不是历史 Relation。",
        "",
        "## Expansion Stories",
        "",
        "| Rank | Story | Chapter | State | Main Persons | Wave 2 Persons | Reasons |",
        "|---:|---|---|---|---:|---:|---|",
    ]
    for row in selected:
        lines.append(
            f"| {row['selection_rank']} | `{row['story_id']}` | `{row['chapter']}` | {row['publication_state']} | "
            f"{row['metrics']['main_materialized_person_count']} | {row['metrics']['wave2_main_person_count']} | {'；'.join(row['selection_reasons'])} |"
        )
    lines.extend(["", "## 未选高价值但受限项", ""])
    for row in sorted(
        (row for row in document["stories"] if not row.get("selected") and row.get("eligible")),
        key=lambda row: (-len(row["main_person_ids"]), int(row["global_ordinal"]), str(row["story_id"])),
    )[:20]:
        lines.append(f"- `{row['story_id']}`：{len(row['main_person_ids'])} 位正文人物；未进入本轮联合集合。")
    lines.append("")
    return "\n".join(lines)


def build(root: Path = ROOT) -> tuple[Path, Path, Path]:
    document = build_story_ranking(root)
    write_json(root, RANKING_PATH, document)
    manifest = freeze_manifest(root, document)
    target = root / REPORT_PATH
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(render_report(document), encoding="utf-8")
    return root / RANKING_PATH, root / MANIFEST_PATH, target


if __name__ == "__main__":
    for path in build():
        print(path)
