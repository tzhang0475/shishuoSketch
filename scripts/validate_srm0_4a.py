#!/usr/bin/env python3
"""Validate SRM0.4A selection, convergence artifacts, and local evidence use."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Mapping

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from ds1_common import ROOT, sha256_file  # noqa: E402
from srm0_4a_common import (  # noqa: E402
    BATCH_SUMMARY_PATH,
    EXCLUDED_STORIES,
    MAX_EVIDENCE_ROUNDS,
    SELECTION_PATH,
    apply_gap_gates,
    build_retrieval_registry,
    selection,
    story_material,
    validate_delta,
    validate_initial,
)


OUTPUT_BASE = Path("data/generated/srm0")
STATUS_PATH = Path("data/generated/srm0/srm0-4-status.json")
REVIEW_PATH = Path("data/annotation/srm0-4a-review.json")
ALLOWED_SEARCH_CORPORA = {
    "世說新語", "余嘉錫箋疏", "晉書", "三國志", "資治通鑑", "資治通鑑考異"
}


def read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def walk(value: Any):
    if isinstance(value, Mapping):
        for key, child in value.items():
            yield str(key)
            yield from walk(child)
    elif isinstance(value, list):
        for child in value:
            yield from walk(child)


def message_payload(document: Mapping[str, Any]) -> dict[str, Any]:
    messages = document.get("messages")
    if not isinstance(messages, list) or not messages:
        return {}
    last = messages[-1]
    content = last.get("content") if isinstance(last, Mapping) else ""
    try:
        value = json.loads(str(content))
    except (TypeError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def add_error(errors: list[str], prefix: str, message: str) -> None:
    errors.append(f"{prefix}: {message}")


def validate_story(story_id: str, registry: Mapping[str, Mapping[str, Any]]) -> tuple[list[str], dict[str, Any]]:
    errors: list[str] = []
    material = story_material(ROOT, story_id)
    output_dir = ROOT / OUTPUT_BASE / story_id / "convergence"
    if not output_dir.is_dir():
        return [f"{story_id}: missing convergence directory"], {}
    required = (
        "round-00-input.json", "round-00-output.json", "research-state.json",
        "events.jsonl", "search-trace.jsonl", "convergence.json", "usage.json", "manifest.json",
    )
    for name in required:
        if not (output_dir / name).is_file():
            add_error(errors, story_id, f"missing {name}")

    manifest = read_json(output_dir / "manifest.json")
    hashes = manifest.get("artifact_hashes")
    if not isinstance(hashes, Mapping) or "manifest.json" in hashes:
        add_error(errors, story_id, "manifest self-reference or missing artifact hashes")
    else:
        for name, expected in hashes.items():
            path = output_dir / str(name)
            if not path.is_file() or sha256_file(ROOT, OUTPUT_BASE / story_id / "convergence" / str(name)) != expected:
                add_error(errors, story_id, f"artifact hash mismatch: {name}")
    if manifest.get("canonical_write_back") is not False or manifest.get("external_search_performed") is not False:
        add_error(errors, story_id, "unsafe manifest flags")

    state = read_json(output_dir / "research-state.json")
    if state.get("canonical_write_back") is not False or state.get("external_search_performed") is not False:
        add_error(errors, story_id, "unsafe research-state flags")
    if any(key in {"snippet", "quote", "text", "source_path"} for key in walk(state)):
        add_error(errors, story_id, "research state contains source-text fields")
    convergence = read_json(output_dir / "convergence.json")
    metrics = convergence.get("round_metrics", []) if isinstance(convergence.get("round_metrics"), list) else []
    for metric in metrics:
        if not isinstance(metric, Mapping) or not isinstance(metric.get("round"), int) or not 1 <= metric.get("round") <= MAX_EVIDENCE_ROUNDS:
            add_error(errors, story_id, "invalid convergence round metric")
            continue
        if metric.get("D_t") not in {0, 1} or not isinstance(metric.get("G_t"), int) or metric.get("G_t") < 0 or not isinstance(metric.get("N_t"), (int, float)) or not 0 <= float(metric.get("N_t")) <= 1:
            add_error(errors, story_id, "invalid G_t/D_t/N_t metric")
        used_metric = set(metric.get("used_evidence_refs", []))
        new_metric = set(metric.get("new_used_evidence_refs", []))
        if not new_metric.issubset(used_metric):
            add_error(errors, story_id, "new evidence metric is not a subset of used evidence")
        expected_novelty = len(new_metric) / len(used_metric) if used_metric else 0.0
        if round(float(metric.get("N_t", 0)), 6) != round(expected_novelty, 6):
            add_error(errors, story_id, "N_t does not match used/new evidence refs")

    initial_input = read_json(output_dir / "round-00-input.json")
    initial_output = read_json(output_dir / "round-00-output.json")
    if initial_input.get("canonical_write_back") is not False or initial_input.get("external_search_performed") is not False:
        add_error(errors, story_id, "unsafe initial-input flags")
    if (initial_input.get("parameters") or {}).get("tools") != []:
        add_error(errors, story_id, "initial input exposes tools")
    forbidden_packet_keys = {"source_path", "source_sha256", "source_locator", "review_status", "person_id", "fact_id", "hashes", "audit_metadata"}
    for input_path in sorted(output_dir.glob("round-*-input.json")):
        input_doc = read_json(input_path)
        packet = message_payload(input_doc)
        if forbidden_packet_keys.intersection(set(walk(packet))):
            add_error(errors, story_id, f"model packet exposes audit/source metadata: {input_path.name}")
        if "data/generated/" in json.dumps(packet, ensure_ascii=False) or "data/annotation/" in json.dumps(packet, ensure_ascii=False):
            add_error(errors, story_id, f"model packet exposes generated path: {input_path.name}")
    raw_initial = initial_output.get("raw_output") if isinstance(initial_output.get("raw_output"), Mapping) else {}
    normalized_initial = initial_output.get("normalized_output") if isinstance(initial_output.get("normalized_output"), Mapping) else {}
    initial_errors = validate_initial(raw_initial, normalized_initial, material)
    errors.extend(f"{story_id}: round 0: {item}" for item in initial_errors)
    accepted, audit = apply_gap_gates(normalized_initial.get("gaps", []) if isinstance(normalized_initial.get("gaps"), list) else [], material)
    frozen_compare = [
        {key: row.get(key) for key in ("question_id", "story_span", "gap")}
        for row in initial_output.get("frozen_questions", [])
        if isinstance(row, Mapping)
    ]
    if initial_output.get("gate_audit") != audit or frozen_compare != accepted:
        add_error(errors, story_id, "gap gates are not deterministic")
    frozen = initial_output.get("frozen_questions", []) if isinstance(initial_output.get("frozen_questions"), list) else []
    question_ids = {str(row.get("question_id")) for row in frozen if isinstance(row, Mapping)}
    if initial_output.get("validation_errors"):
        errors.extend(f"{story_id}: round 0 artifact records validation error: {item}" for item in initial_output["validation_errors"])

    attached_sources = {str(row["ref"]): str(row.get("text", "")) for row in list(material.get("liu_notes", [])) + list(material.get("jianshu_notes", []))}
    output_rounds: list[int] = []
    for path in sorted(output_dir.glob("round-*-output.json")):
        try:
            output_rounds.append(int(path.name.split("-", 2)[1]))
        except (IndexError, ValueError):
            add_error(errors, story_id, f"invalid round filename: {path.name}")
    if any(number > MAX_EVIDENCE_ROUNDS for number in output_rounds):
        add_error(errors, story_id, "evidence-round hard cap exceeded")

    for number in sorted(number for number in output_rounds if number >= 1):
        output = read_json(output_dir / f"round-{number:02d}-output.json")
        raw = output.get("raw_output") if isinstance(output.get("raw_output"), Mapping) else {}
        normalized = output.get("normalized_output") if isinstance(output.get("normalized_output"), Mapping) else {}
        if number == 1:
            sources = attached_sources
            expected_ids = question_ids
        else:
            input_doc = read_json(output_dir / f"round-{number:02d}-input.json")
            payload = message_payload(input_doc)
            candidates = payload.get("local_evidence_candidates", []) if isinstance(payload.get("local_evidence_candidates"), list) else []
            input_refs = {str(row.get("ref")) for row in candidates if isinstance(row, Mapping) and row.get("ref")}
            declared_refs = {str(value) for value in output.get("candidate_refs", [])}
            if input_refs != declared_refs:
                add_error(errors, story_id, f"round {number}: candidate refs differ from input")
            if not input_refs.issubset(registry):
                add_error(errors, story_id, f"round {number}: unknown candidate ref")
            sources = {ref: str(registry[ref].get("text", "")) for ref in input_refs if ref in registry}
            active = payload.get("active_questions", []) if isinstance(payload.get("active_questions"), list) else []
            expected_ids = {str(row.get("question_id")) for row in active if isinstance(row, Mapping)}
            if (input_doc.get("parameters") or {}).get("tools") != []:
                add_error(errors, story_id, f"round {number}: tools exposed")
        errors.extend(f"{story_id}: round {number}: {item}" for item in validate_delta(raw, normalized, sources, expected_ids))
        if output.get("canonical_write_back") is not False or output.get("external_search_performed") is not False:
            add_error(errors, story_id, f"round {number}: unsafe output flags")
        if number > 1:
            used = {
                str(item.get("ref"))
                for update in normalized.get("updates", []) if isinstance(update, Mapping)
                for aspect in update.get("answered_aspects", []) if isinstance(aspect, Mapping)
                for item in aspect.get("evidence", []) if isinstance(item, Mapping)
            }
            if not used.issubset(set(sources)):
                add_error(errors, story_id, f"round {number}: used ref was not opened")

    trace_rows: list[dict[str, Any]] = []
    trace_path = output_dir / "search-trace.jsonl"
    if trace_path.is_file():
        for line in trace_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                add_error(errors, story_id, "invalid search trace JSON")
                continue
            if isinstance(row, Mapping):
                trace_rows.append(dict(row))
    for row in trace_rows:
        if set(row.get("searched_corpora", [])) != ALLOWED_SEARCH_CORPORA:
            add_error(errors, story_id, "search trace has an unregistered corpus")
        retrieved = set(row.get("retrieved_refs", []))
        opened = set(row.get("opened_refs", []))
        used = set(row.get("used_refs", []))
        new = set(row.get("new_used_refs", []))
        if not opened.issubset(retrieved) or not used.issubset(opened) or not new.issubset(used):
            add_error(errors, story_id, "search trace subset invariant failed")
        if any(str(ref).startswith(("data/generated/", "data/annotation/")) for ref in retrieved | opened | used):
            add_error(errors, story_id, "generated material appears in search trace")

    state_rows = state.get("questions", []) if isinstance(state.get("questions"), list) else []
    state_ids = {str(row.get("question_id")) for row in state_rows if isinstance(row, Mapping)}
    for row in state_rows:
        if not isinstance(row, Mapping):
            add_error(errors, story_id, "state question is not an object")
            continue
        parent = row.get("parent_question_id")
        if parent and str(parent) not in state_ids:
            add_error(errors, story_id, f"orphan parent question: {row.get('question_id')}")
        if parent and not row.get("parent_aspect_id"):
            add_error(errors, story_id, f"child has no parent aspect: {row.get('question_id')}")
        if parent:
            parent_row = next((other for other in state_rows if isinstance(other, Mapping) and other.get("question_id") == parent), None)
            if isinstance(parent_row, Mapping) and row.get("story_span") != parent_row.get("story_span"):
                add_error(errors, story_id, f"child changed Story span: {row.get('question_id')}")
    summary = {
        "story_id": story_id,
        "validation_errors": sorted(set(errors)),
        "rounds": sorted(output_rounds),
        "trace_rows": len(trace_rows),
        "status": state.get("story_status"),
    }
    return sorted(set(errors)), summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("portable", "full"), default="portable")
    parser.add_argument("--story", help="validate one selected Story only")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    errors: list[str] = []
    selection_doc = selection(ROOT)
    saved_selection = read_json(ROOT / SELECTION_PATH)
    if saved_selection and saved_selection != selection_doc:
        errors.append("selection artifact is not deterministic")
    selected = selection_doc.get("selected", [])
    expected_ids = [str(row.get("story_id")) for row in selected if isinstance(row, Mapping)]
    if len(expected_ids) != 6 or len(set(expected_ids)) != 6:
        errors.append("selection does not contain exactly six unique Stories")
    if set(expected_ids) & set(EXCLUDED_STORIES):
        errors.append("selection includes an excluded prior pilot Story")
    story_ids = [args.story] if args.story else expected_ids
    if args.story and args.story not in expected_ids:
        errors.append(f"requested Story is not selected: {args.story}")
    status = read_json(ROOT / STATUS_PATH)
    legacy_results_present = any((ROOT / OUTPUT_BASE / story_id / "convergence" / "round-00-input.json").is_file() for story_id in expected_ids)
    if status.get("previous_live_results_reset") is True and not (ROOT / BATCH_SUMMARY_PATH).is_file() and not legacy_results_present:
        print("SRM0.4A validation passed (generated results reset)")
        return 0
    has_trace = any((ROOT / OUTPUT_BASE / story_id / "convergence" / "search-trace.jsonl").is_file() and (ROOT / OUTPUT_BASE / story_id / "convergence" / "search-trace.jsonl").stat().st_size for story_id in story_ids)
    registry = build_retrieval_registry(ROOT) if has_trace else {}
    summaries: list[dict[str, Any]] = []
    for story_id in story_ids:
        story_errors, summary = validate_story(story_id, registry)
        errors.extend(story_errors)
        summaries.append(summary)
    if not (ROOT / REVIEW_PATH).is_file():
        errors.append("missing SRM0.4A review template")
    batch = read_json(ROOT / BATCH_SUMMARY_PATH)
    if batch and {str(row.get("story_id")) for row in batch.get("stories", []) if isinstance(row, Mapping)} != set(story_ids):
        errors.append("batch summary Story set differs from requested validation set")
    if errors:
        print("SRM0.4A validation failed")
        for item in sorted(set(errors)):
            print(f"- {item}")
        return 1
    print(f"SRM0.4A validation passed ({args.mode})")
    for row in summaries:
        print(f"- {row['story_id']}: {row['status']} rounds={row['rounds']} trace_rows={row['trace_rows']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
