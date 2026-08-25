#!/usr/bin/env python3
"""Build the lightweight HDB2 review projection and compact rescue traces.

This script is deliberately offline.  It reads frozen HDB2-F/HDB1 artifacts,
never calls a model, and never writes canonical or reviewed historical data.
"""

from __future__ import annotations

import argparse
import collections
import json
import subprocess
from pathlib import Path
from typing import Any, Mapping, Sequence

import hdb2_full_frontier_common as common


ROOT = Path(__file__).resolve().parents[1]
RUN_ROOT = ROOT / "data/generated/hdb2-f/live"
REVIEW_ROOT = ROOT / "site/public/generated/review/hdb2"
DEFAULT_RUN_ID = "20260826T-HDB2-F-03"


def read(path: Path, default: Any = None) -> Any:
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else default


def write(path: Path, value: Any) -> None:
    common.write_json(path, value)


def _baseline_blob_size(path: Path) -> int | None:
    """Read the pre-compaction blob size when the artifact is versioned."""
    try:
        relative = path.relative_to(ROOT).as_posix()
        result = subprocess.run(
            ["git", "cat-file", "-s", f"HEAD:{relative}"],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
        return int(result.stdout.strip())
    except (OSError, ValueError, subprocess.CalledProcessError):
        return None


def compact_run(run_dir: Path, *, preserve_debug: bool = True) -> dict[str, Any]:
    """Persist the same ranked search result without passage-body duplication."""
    path = run_dir / "rescue-search-results.json"
    if not path.is_file():
        return {"run_id": run_dir.name, "status": "absent"}
    document = read(path, {}) or {}
    rows = list(document.get("records", []))
    if not any(isinstance(row, Mapping) and row.get("hits") for row in rows):
        current_bytes = path.stat().st_size
        baseline_bytes = _baseline_blob_size(path)
        return {
            "run_id": run_dir.name,
            "status": "already_compact",
            "old_bytes": baseline_bytes,
            "new_bytes": current_bytes,
            "reduction_ratio": round(1 - (current_bytes / baseline_bytes), 6) if baseline_bytes else None,
        }

    debug_dir = run_dir / "debug/rescue-search-traces"
    debug_rows: list[dict[str, Any]] = []
    compact_rows: list[dict[str, Any]] = []
    for row in rows:
        if preserve_debug:
            occurrence_id = str(row.get("occurrence_id") or common.stable_hash(row)[:20])
            shard = debug_dir / f"{occurrence_id}.json"
            write(shard, {"schema": "hdb2-f-rescue-search-trace-debug-v1", **row})
            debug_rows.append({"occurrence_id": row.get("occurrence_id"), "path": str(shard.relative_to(ROOT))})
        compact_rows.append(common.compact_rescue_search_result(row))

    before = path.stat().st_size
    compact_document = {
        "schema": "hdb2-f-rescue-search-results-compact-v1",
        "candidate_only": bool(document.get("candidate_only", True)),
        "canonical_write_back": bool(document.get("canonical_write_back", False)),
        "records": compact_rows,
    }
    temporary = path.with_suffix(path.suffix + ".tmp")
    write(temporary, compact_document)
    temporary.replace(path)
    if preserve_debug:
        write(debug_dir / "index.json", {
            "schema": "hdb2-f-rescue-search-trace-debug-index-v1",
            "records": debug_rows,
            "note": "Optional per-occurrence full search traces; not required for replay.",
        })
    after = path.stat().st_size
    return {
        "run_id": run_dir.name,
        "status": "compacted",
        "old_bytes": before,
        "new_bytes": after,
        "reduction_ratio": round(1 - (after / before), 6) if before else 0,
        "records": len(rows),
        "debug_shards": len(debug_rows),
    }


def _story_text(story: Mapping[str, Any]) -> str:
    reading = story.get("reading") if isinstance(story.get("reading"), Mapping) else {}
    main = reading.get("main_text") if isinstance(reading.get("main_text"), Mapping) else {}
    return str(main.get("original") or story.get("text") or "")


def _annotation_texts(story: Mapping[str, Any], terms: Sequence[str]) -> list[str]:
    annotations = story.get("annotations") if isinstance(story.get("annotations"), list) else []
    normalized_terms = [str(term) for term in terms if term]
    relevant = [
        str(item.get("text") or "")
        for item in annotations
        if isinstance(item, Mapping)
        and any(term in str(item.get("text") or "") for term in normalized_terms)
    ]
    if relevant:
        return list(dict.fromkeys(relevant))[:4]
    return []


def _excerpt(text: str, terms: Sequence[str], limit: int = 1800) -> str:
    text = str(text or "")
    if len(text) <= limit:
        return text
    position = -1
    for term in terms:
        if term:
            position = text.find(str(term))
            if position >= 0:
                break
    if position < 0:
        return text[:limit] + "…"
    radius = max(100, (limit - len(str(terms[0] if terms else ""))) // 2)
    start = max(0, position - radius)
    end = min(len(text), start + limit)
    prefix = "…" if start else ""
    suffix = "…" if end < len(text) else ""
    return prefix + text[start:end] + suffix


def _candidate_label(person_id: str | None, candidates: Sequence[Mapping[str, Any]], catalog: Mapping[str, Mapping[str, Any]]) -> str | None:
    if person_id and person_id in catalog:
        return str(catalog[person_id].get("canonical_name") or person_id)
    for candidate in candidates:
        if str(candidate.get("person_id") or "") == str(person_id or "") and candidate.get("display_name"):
            return str(candidate.get("display_name"))
    return None


def _review_type(status: str, occurrence_type: str, affected: Mapping[str, Sequence[Mapping[str, Any]]]) -> str:
    if status == "resolved_new_candidate":
        return "candidate_person"
    if occurrence_type == "compositional_kinship" or affected.get("kinship") or affected.get("marriage"):
        return "compositional_kinship"
    if occurrence_type in {"title_reference", "office_reference", "ruler_reference"} or affected.get("office"):
        return "office_or_title_holder"
    return "identity"


def _priority(status: str, affected: Mapping[str, Sequence[Mapping[str, Any]]], support: Sequence[str]) -> tuple[str, int]:
    if status == "resolved_new_candidate":
        return "P1", 1000
    if affected.get("marriage"):
        return "P1", 950
    if affected.get("kinship"):
        return "P1", 900
    if len(affected.get("relations", [])) >= 2:
        return "P1", 850
    if status == "contextually_resolved":
        return "P2", 700
    if affected.get("office"):
        return "P2", 650
    if support:
        return "P2", 600
    return "P3", 300


def _fact_projection_maps() -> dict[str, list[dict[str, Any]]]:
    names = {
        "relations": "hdb2-f-relation-projection.json",
        "kinship": "hdb2-f-kinship-projection.json",
        "marriage": "hdb2-f-marriage-projection.json",
        "office": "hdb2-f-office-projection.json",
    }
    result: dict[str, list[dict[str, Any]]] = {}
    for kind, name in names.items():
        doc = read(ROOT / "data/derived" / name, {}) or {}
        result[kind] = [dict(row) for row in doc.get("records", [])]
    return result


def _affected_facts(case: Mapping[str, Any], row: Mapping[str, Any], projections: Mapping[str, Sequence[Mapping[str, Any]]]) -> dict[str, list[dict[str, Any]]]:
    local_ids = {str(x.get("candidate_id")) for x in case.get("local_relations", []) if x.get("candidate_id")}
    story_id = str(row.get("story_id") or case.get("story_id") or "")
    refs = {str(case.get("source_ref") or "")}
    refs.update(str(x.get("source_ref")) for x in case.get("evidence_items", []) if x.get("source_ref"))
    result: dict[str, list[dict[str, Any]]] = {key: [] for key in projections}
    for kind, records in projections.items():
        for fact in records:
            if str(fact.get("candidate_id")) not in local_ids and not (str(fact.get("story_id")) == story_id and str(fact.get("evidence_ref")) in refs):
                continue
            result[kind].append({
                "candidate_id": fact.get("candidate_id"),
                "relation_surface": fact.get("relation_surface"),
                "relation_class": fact.get("relation_class"),
                "state": (fact.get("after") or {}).get("state"),
                "before_state": (fact.get("before") or {}).get("state"),
                "primary_blocker": fact.get("primary_blocker"),
                "newly_unblocked_candidate_fact": bool(fact.get("newly_unblocked_candidate_fact")),
                "evidence_ref": fact.get("evidence_ref"),
                "exact_span": fact.get("exact_span"),
            })
    return result


def _evidence_items(case: Mapping[str, Any], story: Mapping[str, Any], decision: Mapping[str, Any], atom_rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    raw = list(case.get("evidence_items", []))
    if not raw:
        raw = [{
            "source_ref": f"story:{story.get('id')}",
            "source_work": "世說正文",
            "source_layer": "main_text",
            "text": _story_text(story),
            "locator": {"story_id": story.get("id")},
        }]
    target = [str(case.get("target_surface") or decision.get("surface") or "")]
    target.extend(str(x.get("display_name")) for x in case.get("candidates", []) if x.get("display_name"))
    atoms_by_ref: dict[str, list[str]] = collections.defaultdict(list)
    for atom in atom_rows:
        if str(atom.get("occurrence_id")) == str(case.get("occurrence_id")):
            if atom.get("exact_span"):
                atoms_by_ref[str(atom.get("evidence_ref"))].append(str(atom.get("exact_span")))
    output: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in raw:
        ref = str(item.get("source_ref") or item.get("ref") or "")
        if not ref or ref in seen:
            continue
        seen.add(ref)
        text = str(item.get("text") or item.get("evidence_text") or "")
        output.append({
            "evidence_ref": ref,
            "source_work": item.get("source_work"),
            "source_layer": item.get("source_layer"),
            "locator": item.get("locator", {}),
            "exact_spans": atoms_by_ref.get(ref, []),
            "excerpt": _excerpt(text, target + atoms_by_ref.get(ref, [])),
        })
        if len(output) >= 8:
            break
    return output


def _build_item(row: Mapping[str, Any], case: Mapping[str, Any], decision: Mapping[str, Any], story: Mapping[str, Any], catalog: Mapping[str, Mapping[str, Any]], projections: Mapping[str, Sequence[Mapping[str, Any]]], atom_rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    affected = _affected_facts(case, row, projections)
    support = list(decision.get("support_families") or [])
    status = str(decision.get("status") or row.get("status") or "unresolved")
    occurrence_type = str(case.get("occurrence_type") or decision.get("occurrence_type") or "unclear")
    review_type = _review_type(status, occurrence_type, affected)
    priority, priority_score = _priority(status, affected, support)
    review_id = f"hdb2-review-{common.stable_hash({'occurrence_id': row.get('occurrence_id')})[:20]}"
    candidates = list(case.get("candidates", []))
    candidate_people: list[dict[str, Any]] = []
    seen_candidates: set[tuple[str, str]] = set()
    for candidate in candidates:
        name = str(candidate.get("display_name") or "")
        pid = str(candidate.get("person_id") or "") or None
        key = (pid or "", name)
        if not name or key in seen_candidates:
            continue
        seen_candidates.add(key)
        candidate_people.append({
            "candidate_key": candidate.get("candidate_key"),
            "display_name": name,
            "person_id": pid,
            "semantic_type": candidate.get("semantic_type"),
            "source": candidate.get("source"),
        })
    resolved_pid = str(decision.get("resolved_person_id") or "") or None
    proposed_label = _candidate_label(resolved_pid, candidates, catalog)
    if not proposed_label and decision.get("new_candidate_label"):
        proposed_label = str(decision.get("new_candidate_label"))
    if not proposed_label and decision.get("candidate_key"):
        proposed_label = next((x["display_name"] for x in candidate_people if x.get("candidate_key") == decision.get("candidate_key")), None)
    annotation_context = [str(x) for x in case.get("annotation_context", []) if isinstance(x, str) and x]
    if not annotation_context:
        annotation_context = _annotation_texts(story, [str(row.get("surface") or ""), str(row.get("exact_span") or ""), proposed_label or ""])
    context = _story_text(story) or str(case.get("local_story_context") or "")
    compositional = decision.get("compositional_referent") if isinstance(decision.get("compositional_referent"), Mapping) else None
    return {
        "schema": "hdb2-review-item-v1",
        "review_id": review_id,
        "priority": priority,
        "priority_score": priority_score,
        "review_type": review_type,
        "occurrence_id": row.get("occurrence_id"),
        "identity_observation_id": row.get("identity_observation_id"),
        "story_id": row.get("story_id"),
        "target_surface": row.get("surface") or case.get("target_surface"),
        "occurrence_type": occurrence_type,
        "story_context": context,
        "relevant_annotation_context": annotation_context,
        "proposed_identity": {
            "status": status,
            "label": proposed_label,
            "person_id": resolved_pid,
            "candidate_person_id": decision.get("candidate_person_id") or decision.get("new_candidate_id"),
            "candidate_key": decision.get("candidate_key"),
            "basis": decision.get("identity_resolution_basis") or row.get("identity_resolution_basis"),
        },
        "candidate_people": candidate_people,
        "selected_evidence": _evidence_items(case, story, decision, atom_rows),
        "support_families": support,
        "affected_facts": {
            **affected,
            "person_story": [{"story_id": row.get("story_id"), "occurrence_id": row.get("occurrence_id"), "status": status, "person_id": resolved_pid}] if resolved_pid else [],
        },
        "current_state": {
            "status": status,
            "original_hdb1_status": row.get("original_hdb1_status"),
            "identity_resolution_basis": decision.get("identity_resolution_basis") or row.get("identity_resolution_basis"),
            "cascade_stage": decision.get("cascade_stage") or row.get("cascade_stage"),
            "candidate_set": list(decision.get("candidate_set_after") or case.get("candidate_set_before") or []),
            "hard_constraint_rejections": list(decision.get("hard_constraint_rejections") or []),
            "rescue_attempted": bool(decision.get("rescue_attempted") or row.get("rescue_attempted")),
            "rescue_useful": bool(decision.get("rescue_useful") or row.get("rescue_useful")),
            "compositional_referent": compositional,
            "candidate_only": True,
            "canonical_write_back": False,
        },
    }


def build_review_projection(run_id: str = DEFAULT_RUN_ID) -> dict[str, Any]:
    run_dir = RUN_ROOT / run_id
    queue_doc = read(ROOT / "data/annotation/hdb2-f-review-queue.json", {}) or {}
    queue = list(queue_doc.get("records", []))
    full_decisions = {str(x.get("occurrence_id")): dict(x) for x in (read(ROOT / "data/annotation/hdb2-f-occurrence-decisions.json", {}) or {}).get("records", [])}
    live_decisions = {str(x.get("occurrence_id")): dict(x) for x in (read(run_dir / "python-decisions.json", {}) or {}).get("records", [])}
    contexts = {str(x.get("occurrence_id")): dict(x) for x in (read(run_dir / "occurrence-contexts.json", {}) or {}).get("cases", [])}
    atoms = list((read(run_dir / "rescue-evidence-atoms.json", {}) or {}).get("records", []))
    site = read(ROOT / "data/derived/sc1-site.json", {}) or {}
    stories = {str(x.get("id")): dict(x) for x in site.get("stories", [])}
    identity = {str(x.get("identity_observation_id")): dict(x) for x in (read(ROOT / "data/derived/hdb1-cross-wave-candidate-historical-db.json", {}) or {}).get("identity_observations", [])}
    catalog = common.hng02.person_catalog()
    projections = _fact_projection_maps()
    items: list[dict[str, Any]] = []
    for queue_row in queue:
        occurrence = str(queue_row.get("occurrence_id"))
        base = identity.get(str(queue_row.get("identity_observation_id")), {})
        case = contexts.get(occurrence, {})
        story = stories.get(str(queue_row.get("story_id")), {"id": queue_row.get("story_id"), "text": "", "annotations": []})
        if not case:
            case = {
                "occurrence_id": occurrence,
                "target_surface": queue_row.get("surface"),
                "occurrence_type": base.get("entity_kind") or "unclear",
                "source_ref": base.get("evidence_ref"),
                "annotation_context": [],
                "evidence_items": [],
                "candidates": [],
                "local_relations": [],
            }
            for pid in base.get("candidate_set") or []:
                if str(pid) in catalog:
                    case["candidates"].append({"candidate_key": None, "display_name": catalog[str(pid)].get("canonical_name"), "person_id": str(pid), "semantic_type": "person", "source": "hdb1_candidate_set"})
        decision = live_decisions.get(occurrence) or full_decisions.get(occurrence) or {
            "status": queue_row.get("status"),
            "resolved_person_id": base.get("resolved_person_id"),
            "identity_resolution_basis": base.get("identity_resolution_basis"),
        }
        row = {**base, **queue_row, "surface": queue_row.get("surface") or base.get("surface")}
        items.append(_build_item(row, case, decision, story, catalog, projections, atoms))
    items.sort(key=lambda x: (-int(x.get("priority_score") or 0), str(x.get("story_id")), str(x.get("target_surface")), str(x.get("review_id"))))
    counts_type = collections.Counter(str(x.get("review_type")) for x in items)
    counts_priority = collections.Counter(str(x.get("priority")) for x in items)
    index = {
        "schema": "hdb2-review-index-v1",
        "run_id": run_id,
        "candidate_only": True,
        "canonical_write_back": False,
        "item_count": len(items),
        "counts_by_type": dict(sorted(counts_type.items())),
        "counts_by_priority": dict(sorted(counts_priority.items())),
        "items": [{
            "review_id": item["review_id"],
            "priority": item["priority"],
            "review_type": item["review_type"],
            "story_id": item["story_id"],
            "target_surface": item["target_surface"],
            "status": item["proposed_identity"]["status"],
            "proposed_label": item["proposed_identity"].get("label"),
            "item_path": f"items/{item['review_id']}.json",
        } for item in items],
    }
    return {"index": index, "items": items}


def write_review_projection(run_id: str = DEFAULT_RUN_ID) -> dict[str, Any]:
    projection = build_review_projection(run_id)
    item_dir = REVIEW_ROOT / "items"
    item_dir.mkdir(parents=True, exist_ok=True)
    for item in projection["items"]:
        write(item_dir / f"{item['review_id']}.json", item)
    write(REVIEW_ROOT / "index.json", projection["index"])
    return projection["index"]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id", default=DEFAULT_RUN_ID)
    parser.add_argument("--compact-run-id", action="append", dest="compact_run_ids")
    parser.add_argument("--skip-compaction", action="store_true")
    args = parser.parse_args()
    compact_ids = args.compact_run_ids or ["20260826T-HDB2-F-02", "20260826T-HDB2-F-03"]
    compaction: list[dict[str, Any]] = []
    if args.skip_compaction:
        previous_report = read(ROOT / "data/generated/hdb2-f/review-build-report.json", {}) or {}
        compaction = list(previous_report.get("compaction", []))
        if not compaction:
            compaction = [compact_run(RUN_ROOT / run_id, preserve_debug=False) for run_id in compact_ids]
    else:
        for run_id in compact_ids:
            compaction.append(compact_run(RUN_ROOT / run_id))
    index = write_review_projection(args.run_id)
    report = {
        "schema": "hdb2-review-build-report-v1",
        "candidate_only": True,
        "canonical_write_back": False,
        "compaction": compaction,
        "review_index": {
            "item_count": index.get("item_count"),
            "counts_by_type": index.get("counts_by_type"),
            "counts_by_priority": index.get("counts_by_priority"),
        },
    }
    write(ROOT / "data/generated/hdb2-f/review-build-report.json", report)
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
