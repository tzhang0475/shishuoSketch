#!/usr/bin/env python3
"""Build deterministic before/after M2A experience metrics.

These metrics describe the reader's Person↔Story navigation graph.  They are
not historical Relation facts and must never be used to create Relation
records.
"""

from __future__ import annotations

from collections import defaultdict
import argparse
import gzip
from itertools import combinations
import hashlib
import json
from pathlib import Path
import statistics
import subprocess
from typing import Any, Iterable, Mapping


ROOT = Path(__file__).resolve().parents[1]
SC1_PATH = Path("data/derived/sc1-site.json")
LINKS_PATH = Path("data/derived/person-story-links.json")
SCENE_PATH = Path("data/derived/story-scene-contexts.json")
RELATIONS_PATH = Path("data/annotation/wp1-relations.json")
WAVE2_PATH = Path("data/annotation/person-expansion-wave-2.json")
STORY_WAVE_PATH = Path("data/annotation/story-expansion-wave-1.json")
RANKING_PATH = Path("data/derived/m2-person-expansion-ranking.json")
STORY_RANKING_PATH = Path("data/derived/m2-story-expansion-ranking.json")
R3A_PATH = Path("data/derived/person-relation-candidates-r3.json")
OUTPUT_PATH = Path("data/derived/m2-experience-metrics.json")
REPORT_PATH = Path("docs/m2-experience-scale-up.md")
DIST_ASSETS_PATH = Path("dist/assets")

# The parent P-ID1 build was measured with the same Vite/Node toolchain used
# for the current production artifact.  Dist is intentionally not committed,
# so these baseline numbers are an explicit performance-audit snapshot rather
# than a runtime input.  The current numbers are measured only when the
# post-Vite `--production-artifact` pass is requested.
BASELINE_FRONTEND_JS_BYTES = 3_533_126
BASELINE_FRONTEND_JS_GZIP_BYTES = 1_093_692


# These are the values audited immediately before M2A began.  They are a
# baseline snapshot, not a selection quota.  The graph-specific values below
# are recalculated from the committed pre-M2 SC1/link artifacts when possible.
BASELINE_SNAPSHOT = {
    "production_person_count": 17,
    "published_story_count": 16,
    "random_person_eligible_count": 13,
    "person_story_link_count": 330,
    "scene_card_count": 9,
    "reviewed_relation_count": 7,
}


def read_json(root: Path, path: Path) -> Any:
    return json.loads((root / path).read_text(encoding="utf-8"))


def write_json(root: Path, path: Path, value: Any) -> None:
    target = root / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _git_blob_size(root: Path, path: Path) -> int | None:
    result = subprocess.run(
        ["git", "show", f"HEAD:{path.as_posix()}"],
        cwd=root,
        check=False,
        capture_output=True,
    )
    return len(result.stdout) if result.returncode == 0 else None


def _frontend_js_metrics(root: Path) -> dict[str, Any] | None:
    assets = sorted((root / DIST_ASSETS_PATH).glob("*.js"))
    if not assets:
        return None
    raw_bytes = sum(path.stat().st_size for path in assets)
    gzip_bytes = sum(
        len(gzip.compress(path.read_bytes(), mtime=0))
        for path in assets
    )
    return {
        "asset_count": len(assets),
        "bytes": raw_bytes,
        "gzip_bytes": gzip_bytes,
    }


def _performance_metrics(root: Path, *, include_production_artifact: bool) -> dict[str, Any]:
    current_sc1_path = root / SC1_PATH
    current_sc1_bytes = current_sc1_path.stat().st_size if current_sc1_path.is_file() else None
    baseline_sc1_bytes = _git_blob_size(root, SC1_PATH)
    current_js = _frontend_js_metrics(root) if include_production_artifact else None
    return {
        "sc1_data_bytes": {
            "before": baseline_sc1_bytes,
            "after": current_sc1_bytes,
        },
        "frontend_js_bytes": {
            "before": BASELINE_FRONTEND_JS_BYTES,
            "after": current_js.get("bytes") if current_js else None,
        },
        "frontend_js_gzip_bytes": {
            "before": BASELINE_FRONTEND_JS_GZIP_BYTES,
            "after": current_js.get("gzip_bytes") if current_js else None,
        },
        "current_js_asset_count": current_js.get("asset_count") if current_js else None,
        "measurement": (
            "P-ID1 parent Vite build versus the post-M2 production artifact"
            if include_production_artifact
            else "SC1 data measured; JS artifact measurement deferred until the post-Vite pass"
        ),
    }


def _git_json(root: Path, path: Path) -> Any | None:
    """Read the P-ID1/M2A parent artifact without mutating the worktree."""

    result = subprocess.run(
        ["git", "show", f"HEAD:{path.as_posix()}"],
        cwd=root,
        check=False,
        capture_output=True,
    )
    if result.returncode != 0:
        return None
    try:
        return json.loads(result.stdout.decode("utf-8"))
    except json.JSONDecodeError:
        return None


def _published_stories(bundle: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    return [
        story for story in bundle.get("stories", [])
        if isinstance(story, Mapping) and story.get("publication_state") != "blocked"
    ]


def _story_persons(stories: Iterable[Mapping[str, Any]], person_ids: set[str]) -> dict[str, set[str]]:
    result: dict[str, set[str]] = {}
    for story in stories:
        story_id = str(story.get("id"))
        result[story_id] = {
            str(person_id)
            for person_id in story.get("person_ids", [])
            if str(person_id) in person_ids
        }
    return result


def _reviewed_relations(relations: Iterable[Mapping[str, Any]]) -> list[Mapping[str, Any]]:
    return [item for item in relations if item.get("review_status") == "reviewed"]


def _relation_neighbors(relations: Iterable[Mapping[str, Any]]) -> dict[str, set[str]]:
    neighbors: dict[str, set[str]] = defaultdict(set)
    for relation in _reviewed_relations(relations):
        left = str(relation.get("subject_id"))
        right = str(relation.get("object_id"))
        if left and right and left != right:
            neighbors[left].add(right)
            neighbors[right].add(left)
    return neighbors


def _components(graph: Mapping[str, set[str]]) -> list[set[str]]:
    remaining = set(graph)
    result: list[set[str]] = []
    while remaining:
        start = min(remaining)
        stack = [start]
        component: set[str] = set()
        while stack:
            node = stack.pop()
            if node in component:
                continue
            component.add(node)
            remaining.discard(node)
            stack.extend(sorted(graph.get(node, set()) - component, reverse=True))
        result.append(component)
    return sorted(result, key=lambda item: (-len(item), sorted(item)))


def _articulation_points(graph: Mapping[str, set[str]]) -> set[str]:
    """Tarjan articulation points for the product graph only."""

    discovery: dict[str, int] = {}
    low: dict[str, int] = {}
    parent: dict[str, str | None] = {}
    points: set[str] = set()
    counter = 0

    def visit(node: str) -> None:
        nonlocal counter
        counter += 1
        discovery[node] = counter
        low[node] = counter
        children = 0
        for neighbor in sorted(graph.get(node, set())):
            if neighbor not in discovery:
                parent[neighbor] = node
                children += 1
                visit(neighbor)
                low[node] = min(low[node], low[neighbor])
                if parent.get(node) is None and children > 1:
                    points.add(node)
                if parent.get(node) is not None and low[neighbor] >= discovery[node]:
                    points.add(node)
            elif neighbor != parent.get(node):
                low[node] = min(low[node], discovery[neighbor])

    for node in sorted(graph):
        if node not in discovery:
            parent[node] = None
            visit(node)
    return points


def _graph_metrics(
    person_ids: set[str],
    story_persons: Mapping[str, set[str]],
) -> dict[str, Any]:
    graph: dict[str, set[str]] = {
        f"person:{person_id}": set() for person_id in sorted(person_ids)
    }
    for story_id in sorted(story_persons):
        story_node = f"story:{story_id}"
        graph.setdefault(story_node, set())
        for person_id in sorted(story_persons[story_id]):
            person_node = f"person:{person_id}"
            graph.setdefault(person_node, set()).add(story_node)
            graph[story_node].add(person_node)
    components = _components(graph)
    articulation = _articulation_points(graph)
    person_degrees = [len(story_persons.get(story_id, set())) for story_id in story_persons]
    stories_by_person: dict[str, set[str]] = defaultdict(set)
    for story_id, persons in story_persons.items():
        for person_id in persons:
            stories_by_person[person_id].add(story_id)
    person_graph: dict[str, set[str]] = {person_id: set() for person_id in person_ids}
    for persons in story_persons.values():
        for left, right in combinations(sorted(persons), 2):
            person_graph[left].add(right)
            person_graph[right].add(left)
    return {
        "connected_component_count": len(components),
        "largest_component_nodes": len(components[0]) if components else 0,
        "largest_component_people": sum(node.startswith("person:") for node in components[0]) if components else 0,
        "isolated_person_ids": sorted(
            person_id for person_id in person_ids if not stories_by_person.get(person_id)
        ),
        "median_person_story_degree": statistics.median(
            [len(stories_by_person.get(person_id, set())) for person_id in sorted(person_ids)] or [0]
        ),
        "median_story_person_degree": statistics.median(person_degrees or [0]),
        "articulation_person_ids": sorted(
            node.removeprefix("person:")
            for node in articulation if node.startswith("person:")
        ),
        "articulation_story_ids": sorted(
            node.removeprefix("story:")
            for node in articulation if node.startswith("story:")
        ),
        "person_reachable_one_story_hop": {
            person_id: len(person_graph[person_id])
            for person_id in sorted(person_graph)
        },
        "stories_by_person": {
            person_id: sorted(stories_by_person.get(person_id, set()))
            for person_id in sorted(person_ids)
        },
        "story_person_degree": {
            story_id: len(persons) for story_id, persons in sorted(story_persons.items())
        },
    }


def _snapshot_metrics(
    bundle: Mapping[str, Any],
    links: Mapping[str, Any],
    scenes: Mapping[str, Any],
    relations: Mapping[str, Any],
    eligible_count: int,
) -> dict[str, Any]:
    people = {str(item.get("id")): item for item in bundle.get("people", []) if isinstance(item, Mapping)}
    person_ids = set(people)
    stories = _published_stories(bundle)
    story_persons = _story_persons(stories, person_ids)
    stories_by_person = defaultdict(set)
    for story_id, story_people in story_persons.items():
        for person_id in story_people:
            stories_by_person[person_id].add(story_id)
    reviewed_relations = _reviewed_relations(relations.get("records", []))
    relation_neighbors = _relation_neighbors(relations.get("records", []))
    scene_contexts = scenes.get("contexts", {})
    scene_stories_by_person: dict[str, set[str]] = defaultdict(set)
    for story_id, context in scene_contexts.items():
        for person in context.get("people_at_scene", []):
            person_id = str(person.get("person_id"))
            if person_id in person_ids:
                scene_stories_by_person[person_id].add(str(story_id))
    story_pairs = {
        tuple(pair)
        for persons in story_persons.values()
        for pair in combinations(sorted(persons), 2)
    }
    graph = _graph_metrics(person_ids, story_persons)
    return {
        "production_person_count": len(person_ids),
        "published_story_count": len(stories),
        "random_person_eligible_count": eligible_count,
        "person_story_link_count": int(links.get("link_count", len(links.get("links", [])))),
        "persons_with_at_least_one_published_story": sum(bool(stories_by_person.get(person_id)) for person_id in person_ids),
        "persons_with_at_least_three_published_stories": sum(len(stories_by_person.get(person_id, set())) >= 3 for person_id in person_ids),
        "multi_person_story_count": sum(len(persons) >= 2 for persons in story_persons.values()),
        "story_with_at_least_two_materialized_persons": sum(len(persons) >= 2 for persons in story_persons.values()),
        "scene_card_count": len(scene_contexts),
        "reviewed_relation_count": len(reviewed_relations),
        "reviewed_direct_relation_count": sum(item.get("relation_basis") == "direct" for item in reviewed_relations),
        "relation_isolated_person_count": sum(not relation_neighbors.get(person_id) for person_id in person_ids),
        "story_mediated_person_pair_count": len(story_pairs),
        "person_no_published_story_count": sum(not stories_by_person.get(person_id) for person_id in person_ids),
        "story_without_clickable_person_count": sum(not persons for persons in story_persons.values()),
        "person_only_one_isolated_story_count": sum(
            len(stories_by_person.get(person_id, set())) == 1
            and len(story_persons[next(iter(stories_by_person[person_id]))]) == 1
            for person_id in person_ids
        ),
        "scene_rich_story_count": len(set(scene_contexts)),
        "scene_rich_stories_by_person": {
            person_id: sorted(scene_stories_by_person.get(person_id, set()))
            for person_id in sorted(person_ids)
        },
        "reviewed_relation_neighbors": {
            person_id: sorted(relation_neighbors.get(person_id, set()))
            for person_id in sorted(person_ids)
        },
        "graph": graph,
    }


def _eligible_count(bundle: Mapping[str, Any]) -> int:
    # The generated UI contract carries the data-driven eligible set in the
    # person records rather than a hard-coded list.  A Person is eligible only
    # when its Sketch and a published Story route are both present.
    stories = _published_stories(bundle)
    story_people = {
        person_id
        for story in stories
        for person_id in story.get("person_ids", [])
    }
    sketches = bundle.get("person_sketches", {})
    if isinstance(sketches, Mapping):
        sketch_ids = {str(person_id) for person_id in sketches}
    else:
        sketch_ids = {
            str(item.get("person_id"))
            for item in sketches
            if isinstance(item, Mapping) and item.get("person_id")
        }
    return len(story_people & sketch_ids)


def _current_and_baseline(root: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    current_bundle = read_json(root, SC1_PATH)
    current_links = read_json(root, LINKS_PATH)
    current_scenes = read_json(root, SCENE_PATH)
    current_relations = read_json(root, RELATIONS_PATH)
    current = _snapshot_metrics(
        current_bundle,
        current_links,
        current_scenes,
        current_relations,
        _eligible_count(current_bundle),
    )

    baseline_bundle = _git_json(root, SC1_PATH)
    baseline_links = _git_json(root, LINKS_PATH)
    baseline_scenes = _git_json(root, Path("data/derived/story-scene-contexts.json"))
    baseline_relations = _git_json(root, RELATIONS_PATH)
    if baseline_bundle and baseline_links and baseline_scenes and baseline_relations:
        baseline_scenes_for_metrics = baseline_scenes
        # The pre-M2 scene artifact is source-shaped; convert it to the
        # derived context map expected by _snapshot_metrics.
        if "contexts" not in baseline_scenes_for_metrics:
            baseline_scenes_for_metrics = {
                "contexts": {
                    str(record["story_id"]): record
                    for record in baseline_scenes.get("records", [])
                }
            }
        baseline = _snapshot_metrics(
            baseline_bundle,
            baseline_links,
            baseline_scenes_for_metrics,
            baseline_relations,
            BASELINE_SNAPSHOT["random_person_eligible_count"],
        )
    else:
        baseline = dict(BASELINE_SNAPSHOT)
    # Preserve the explicitly audited baseline values even if a legacy
    # artifact has a different non-product field shape.
    for key, value in BASELINE_SNAPSHOT.items():
        baseline[key] = value
    return baseline, current


def build(root: Path = ROOT, *, include_production_artifact: bool = False) -> dict[str, Any]:
    baseline, current = _current_and_baseline(root)
    wave2 = read_json(root, WAVE2_PATH)
    story_wave = read_json(root, STORY_WAVE_PATH)
    r3a = read_json(root, R3A_PATH)
    ranking = read_json(root, RANKING_PATH)
    story_ranking = read_json(root, STORY_RANKING_PATH)
    people_by_id = {
        str(item.get("person_id")): str(item.get("canonical_name"))
        for item in read_json(root, Path("data/people.json")).get("people", [])
        if isinstance(item, Mapping)
    }
    selected_wave2 = [
        {
            "rank": int(item["rank_at_selection"]),
            "candidate_id": item["candidate_id"],
            "person_id": item["person_id"],
            "canonical_name": item["preferred_name"],
        }
        for item in sorted(wave2.get("members", []), key=lambda item: int(item["rank_at_selection"]))
    ]
    story_distribution = dict(story_ranking.get("chapter_distribution", {}))
    output = {
        "schema": 1,
        "stage": "m2a-experience-scale-up-metrics",
        "baseline_source": "P-ID1/M2A pre-mutation audit; graph details read from HEAD artifacts when available",
        "before": baseline,
        "after": current,
        "wave_2_person_selection": selected_wave2,
        "story_expansion": {
            "gold_story_count": len(story_wave.get("gold_story_ids", [])),
            "expansion_story_count": len(story_wave.get("expansion_story_ids", [])),
            "published_union_count": current["published_story_count"],
            "expansion_story_ids": list(story_wave.get("expansion_story_ids", [])),
            "chapter_distribution": story_distribution,
        },
        "relation_discovery": {
            "production_person_count": r3a.get("production_person_count"),
            "reviewed_relation_count": r3a.get("reviewed_relation_count"),
            "pair_count_audited": r3a.get("pair_count_audited"),
            "candidate_count": r3a.get("candidate_count"),
            "tier_counts": r3a.get("tier_counts", {}),
            "cooccurrence_only_pair_count": r3a.get("cooccurrence_only_pair_count"),
        },
        "performance": _performance_metrics(
            root,
            include_production_artifact=include_production_artifact,
        ),
        "input_sha256": {
            str(path): sha256_file(root / path)
            for path in (RANKING_PATH, STORY_RANKING_PATH, WAVE2_PATH, STORY_WAVE_PATH, SC1_PATH, SCENE_PATH, R3A_PATH)
        },
        "notes": [
            "PersonStory and Story-mediated graph edges are navigation data, not historical Relation facts.",
            "Scene-rich counts use the Story-owned Scene Context layer and do not imply physical presence beyond the stored scene roles.",
            "Wave 2 selection and Story expansion are frozen by their manifests; this artifact is an audit, not a selector.",
        ],
    }
    output["report_person_name_lookup"] = {
        person_id: people_by_id[person_id] for person_id in sorted(people_by_id)
    }
    write_json(root, OUTPUT_PATH, output)
    (root / REPORT_PATH).write_text(render_report(output), encoding="utf-8")
    return output


def _delta(before: Mapping[str, Any], after: Mapping[str, Any], key: str) -> str:
    left = before.get(key, 0)
    right = after.get(key, 0)
    if isinstance(left, (int, float)) and isinstance(right, (int, float)):
        return f"{left} → {right} ({right - left:+g})"
    return f"{left} → {right}"


def render_report(output: Mapping[str, Any]) -> str:
    before = output["before"]
    after = output["after"]
    lines = [
        "# M2A：Experience Scale-Up 审计",
        "",
        "本报告衡量静态 Person ↔ Story 阅读路径的扩展效果。PersonStory、共享故事和 Scene 都是导航/阅读数据；它们不自动产生历史 Relation。",
        "",
        "## Before → After",
        "",
        "| 指标 | Before | After |",
        "|---|---:|---:|",
    ]
    labels = [
        ("production_person_count", "生产人物"),
        ("published_story_count", "已发布阅读故事"),
        ("random_person_eligible_count", "随机认识人物可选数"),
        ("person_story_link_count", "PersonStory links"),
        ("persons_with_at_least_one_published_story", "至少一则发布故事的人物"),
        ("persons_with_at_least_three_published_stories", "至少三则发布故事的人物"),
        ("multi_person_story_count", "多人物故事"),
        ("scene_card_count", "Scene Cards"),
        ("reviewed_relation_count", "已审阅 Relation"),
        ("relation_isolated_person_count", "仅按 Relation 孤立的人物"),
        ("story_mediated_person_pair_count", "共享故事人物对"),
        ("person_no_published_story_count", "没有发布故事路径的人物"),
        ("story_without_clickable_person_count", "没有可点击人物的故事"),
        ("person_only_one_isolated_story_count", "仅有一则且该故事无其他人物的人物"),
    ]
    for key, label in labels:
        lines.append(f"| {label} | {before.get(key, '—')} | {after.get(key, '—')} |")

    if after.get("production_person_count") == 35 and after.get("random_person_eligible_count") == 34:
        lines.extend([
            "",
            "ER1 的身份校正移除了 `05-fangzheng-058` 中原本错误的“文度 → 孫晷”安全导航路径。因而 M2A 虽然物化了 35 位 Person，当前安全的“随便认识一个人” eligibility 是 34；`person-015` 仍是生产 Person，但没有安全的 published Story 入口。这里不以候选或歧义 Mention 补回路径。",
        ])
    if after.get("production_person_count") == 35 and after.get("random_person_eligible_count") == 33:
        lines.extend([
            "",
            "M2A 物化的 35 位 Person 均保留；ER1 先移除了 `05-fangzheng-058` 中错误的“文度 → 孫晷”路径，使安全 eligibility 由 M2A 当时的 35 降至 34。ER1.1.2 又移除了 `桓子` 前缀误归 `person-016` 王遐的路径，最终安全的“随便认识一个人” eligibility 为 33；`person-015` 与 `person-016` 仍在生产注册表中，但都没有安全的 published Story 入口。候选身份、歧义 Mention 和错误前缀均不用于补回导航。",
        ])
    if "person-016" in after.get("graph", {}).get("isolated_person_ids", []):
        lines.extend([
            "",
            "ER1.1.2 的桓子／桓子野身份校正移除了 6 条原先错误归给 `person-016` 王遐的 PersonStory 链接；其中 05-fangzheng-055 等较长称谓现解析为未物化的桓伊，05-fangzheng-035 的古引文保持未解析。因此王遐仍保留在 35 人生产注册表中，但当前没有安全的 published Story 入口，也不进入 Random Person eligibility；不以错误前缀或候选身份补回路径。",
        ])

    performance = output.get("performance", {})
    def performance_value(section: str, side: str) -> str:
        value = performance.get(section, {}).get(side)
        return f"{value:,}" if isinstance(value, int) else "待 production artifact pass"

    lines.extend([
        "",
        "## Performance guard",
        "",
        "静态架构保留不变；以下记录 SC1 数据和 Vite JS 的增长，JS 以 gzip 后体积作为下载参考。若只运行数据构建，JS 栏会在 production artifact pass 后补齐。",
        "",
        "| 产物 | Before | After |",
        "|---|---:|---:|",
        f"| `data/derived/sc1-site.json` bytes | {performance_value('sc1_data_bytes', 'before')} | {performance_value('sc1_data_bytes', 'after')} |",
        f"| Vite JS bytes | {performance_value('frontend_js_bytes', 'before')} | {performance_value('frontend_js_bytes', 'after')} |",
        f"| Vite JS gzip bytes | {performance_value('frontend_js_gzip_bytes', 'before')} | {performance_value('frontend_js_gzip_bytes', 'after')} |",
        f"| JS asset count | 1 | {performance.get('current_js_asset_count') if performance.get('current_js_asset_count') is not None else '待 production artifact pass'} |",
        "",
        "本阶段未引入 backend、runtime JSON fetch 或数据库；当前体积增长保留为后续静态 code-splitting 评估项。",
    ])

    lines.extend(["", "## Wave 2 人物", "", "| 顺位 | Person ID | 人物 | Candidate ID |", "|---:|---|---|---|"])
    for item in output["wave_2_person_selection"]:
        lines.append(f"| {item['rank']} | `{item['person_id']}` | {item['canonical_name']} | `{item['candidate_id']}` |")
    lines.extend([
        "",
        "Wave 2 只提升具备强身份证据、正文导航价值和安全投影路径的候选；未因引用作者频率而自动选择史家/注家身份。每个新 Person 的 review status 仍保留为 candidate。",
        "",
        "## Story Expansion",
        "",
        f"- SC0 Gold Set：{output['story_expansion']['gold_story_count']} 则（保持不变）。",
        f"- M2 expansion：{output['story_expansion']['expansion_story_count']} 则。",
        f"- 前端阅读并集：{output['story_expansion']['published_union_count']} 则。",
        f"- 章节分布：{', '.join(f'{key}={value}' for key, value in output['story_expansion']['chapter_distribution'].items())}。",
        "",
        "新增 Story IDs：",
        "",
    ])
    lines.extend(f"- `{story_id}`" for story_id in output["story_expansion"]["expansion_story_ids"])
    lines.extend(["", "## Navigation graph", "", "图节点为 production Persons 与已发布 Stories，边为生成的 PersonStory/解析人物路径；不是 Relation graph。", ""])
    graph = after["graph"]
    lines.extend([
        f"- connected components：{graph['connected_component_count']}；最大组件：{graph['largest_component_nodes']} nodes / {graph['largest_component_people']} Persons。",
        f"- median Person Story degree：{graph['median_person_story_degree']}；median Story Person degree：{graph['median_story_person_degree']}。",
        f"- articulation Persons：{', '.join(graph['articulation_person_ids']) or '无'}。",
        f"- articulation Stories：{', '.join(graph['articulation_story_ids']) or '无'}。",
        f"- Person no published Story：{', '.join(graph['isolated_person_ids']) or '无'}。",
        "",
        "## Relation discovery boundary",
        "",
        f"- 当前生产人物：{output['relation_discovery']['production_person_count']}；审计人物对：{output['relation_discovery']['pair_count_audited']}。",
        f"- 已审阅 Relation：{output['relation_discovery']['reviewed_relation_count']}；R3A candidate：{output['relation_discovery']['candidate_count']}；Tier：{output['relation_discovery']['tier_counts']}。",
        f"- 仅共现组合：{output['relation_discovery']['cooccurrence_only_pair_count']}；这些组合未进入 Relation card。",
        "",
        "## Provenance and determinism",
        "",
        "所有 Wave、Story、Scene 和 R3A 输出均由构建时数据生成；portable/full provenance 仍按既有严格规则验证。输入产物 SHA-256：",
        "",
    ])
    for path, digest in output["input_sha256"].items():
        lines.append(f"- `{path}`：`{digest}`")
    lines.extend([
        "",
            "本报告继承 M2A 的冻结选择与 60-Story 规模；ER1 安全解析影响已保留。S2.2 只加深现有 Story/Scene/Person Sketch 内容，R3B 仅物化明确批准的 Relation，Sanguozhi 与 P3B.2 均未启动。",
        "",
    ])
    return "\n".join(lines)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--production-artifact",
        action="store_true",
        help="measure the already-built Vite dist JS assets as well as generated data",
    )
    args = parser.parse_args()
    result = build(include_production_artifact=args.production_artifact)
    print(
        f"M2A metrics: {result['after']['production_person_count']} Persons, "
        f"{result['after']['published_story_count']} Stories, "
        f"{result['after']['scene_card_count']} Scene Cards"
    )
