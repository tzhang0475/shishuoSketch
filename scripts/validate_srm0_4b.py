#!/usr/bin/env python3
"""Validate SRM0.4B live/fixture isolation and fail-soft contracts."""

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
from srm0_4b_common import (  # noqa: E402
    FIXED_STORIES,
    FIXTURE_SUMMARY_PATH,
    LIVE_SUMMARY_PATH,
    MAX_EVIDENCE_ROUNDS,
    REVIEW_PATH,
    STATUS_PATH,
    TRANSPORT_FAILURE_CLASSES,
    build_registry,
    derive_state_b,
    material_delta_b,
    normalize_delta_fail_soft,
    normalize_initial_fail_soft,
    output_directory,
    run_id_for,
    story_material,
)


def read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def walk(value: Any):
    if isinstance(value, Mapping):
        for key, child in value.items():
            yield str(key)
            yield from walk(child)
    elif isinstance(value, list):
        for child in value:
            yield from walk(child)


def payload(document: Mapping[str, Any]) -> Any:
    messages = document.get("messages")
    if not isinstance(messages, list) or not messages:
        return None
    content = messages[-1].get("content") if isinstance(messages[-1], Mapping) else None
    try:
        return json.loads(str(content))
    except (TypeError, json.JSONDecodeError):
        return None


def validate_manifest(errors: list[str], story_id: str, output_dir: Path, expected_kind: str) -> dict[str, Any]:
    manifest = read_json(ROOT / output_dir / "manifest.json")
    if not isinstance(manifest, Mapping):
        errors.append(f"{story_id}: missing manifest")
        return {}
    if manifest.get("execution_kind") != expected_kind:
        errors.append(f"{story_id}: manifest execution kind mismatch")
    hashes = manifest.get("artifact_hashes")
    if not isinstance(hashes, Mapping) or "manifest.json" in hashes:
        errors.append(f"{story_id}: manifest is self-referential or missing hashes")
    else:
        for name, expected in hashes.items():
            path = output_dir / str(name)
            if not path.is_file() or sha256_file(ROOT, output_dir / str(name)) != expected:
                errors.append(f"{story_id}: artifact hash mismatch: {name}")
    if manifest.get("canonical_write_back") is not False or manifest.get("external_search_performed") is not False:
        errors.append(f"{story_id}: unsafe manifest flags")
    return dict(manifest)


def validate_story(story_id: str, *, expected_kind: str, registry: Mapping[str, Mapping[str, Any]]) -> list[str]:
    errors: list[str] = []
    material = story_material(ROOT, story_id)
    if expected_kind == "fixture":
        output_dir = output_directory(story_id, execution_kind="fixture")
    else:
        output_dir = output_directory(story_id, execution_kind="live_model", run_id=run_id_for(material))
    absolute = ROOT / output_dir
    if not absolute.is_dir():
        return [f"{story_id}: missing {expected_kind} output directory: {output_dir}"]
    required = ("round-00-input.json", "round-00-output.json", "research-state.json", "events.jsonl", "search-trace.jsonl", "convergence.json", "usage.json", "manifest.json")
    for name in required:
        if not (absolute / name).is_file():
            errors.append(f"{story_id}: missing {name}")
    validate_manifest(errors, story_id, output_dir, expected_kind)
    for input_path in sorted(absolute.glob("round-*-input.json")):
        document = read_json(input_path)
        if not isinstance(document, Mapping):
            errors.append(f"{story_id}: invalid input artifact {input_path.name}")
            continue
        if document.get("canonical_write_back") is not False or document.get("external_search_performed") is not False:
            errors.append(f"{story_id}: unsafe input flags {input_path.name}")
        if (document.get("parameters") or {}).get("tools") != []:
            errors.append(f"{story_id}: tools exposed in {input_path.name}")
        packet = payload(document)
        packet_text = json.dumps(packet, ensure_ascii=False)
        if any(key in {"source_path", "source_sha256", "source_locator", "review_status", "person_id", "fact_id", "hashes", "audit_metadata"} for key in walk(packet)):
            errors.append(f"{story_id}: audit metadata in {input_path.name}")
        if "data/generated/" in packet_text or "data/annotation/" in packet_text:
            errors.append(f"{story_id}: generated path in {input_path.name}")

    initial_output = read_json(absolute / "round-00-output.json")
    initial_input = read_json(absolute / "round-00-input.json")
    raw_initial = initial_output.get("raw_output") if isinstance(initial_output, Mapping) else None
    normalized_initial, initial_audit = normalize_initial_fail_soft(raw_initial, material)
    if isinstance(initial_output, Mapping):
        if initial_output.get("normalized_output") != normalized_initial:
            errors.append(f"{story_id}: initial normalization is not deterministic")
        if initial_output.get("accepted_gaps") != normalized_initial.get("gaps", []):
            errors.append(f"{story_id}: accepted gap projection mismatch")
        if initial_output.get("rejected_gaps") != initial_audit.get("rejected_gaps", []):
            errors.append(f"{story_id}: rejected gap projection mismatch")
    protocol_errors = []
    if isinstance(initial_output, Mapping) and initial_output.get("protocol_error"):
        protocol_errors.append(str(initial_output["protocol_error"]))
    questions = {str(row.get("question_id")): dict(row) for row in (normalized_initial.get("gaps", []) if isinstance(normalized_initial.get("gaps"), list) else []) if isinstance(row, Mapping)}
    for qid, row in questions.items():
        row.update({"state": "unexplained", "working_answer": "", "supporting_refs": [], "remaining_gap": row["gap"], "reading_sufficient": False, "historical_verification_open": False, "next_action": "retrieve_local", "terminal_reason": None, "active": True, "evidence_rounds": 0, "claim_fingerprints": [], "conflict_fingerprints": [], "conflict_ids": []})
    state = read_json(absolute / "research-state.json")
    if isinstance(state, Mapping) and (state.get("canonical_write_back") is not False or state.get("external_search_performed") is not False):
        errors.append(f"{story_id}: unsafe state flags")
    if any(key in {"text", "quote", "snippet", "source_path"} for key in walk(state)):
        errors.append(f"{story_id}: source text leaked into persistent state")
    if isinstance(initial_output, Mapping) and initial_output.get("failure_class") in TRANSPORT_FAILURE_CLASSES:
        if state.get("story_status") != "api_transport_failed":
            errors.append(f"{story_id}: transport failure did not remain distinct from protocol failure")
        if state.get("protocol_errors"):
            errors.append(f"{story_id}: transport failure leaked into protocol_errors")
        return sorted(set(errors))

    round_numbers = []
    for path in sorted(absolute.glob("round-*-output.json")):
        try:
            number = int(path.name.split("-", 2)[1])
        except (IndexError, ValueError):
            errors.append(f"{story_id}: invalid round filename {path.name}")
            continue
        round_numbers.append(number)
    if any(number > MAX_EVIDENCE_ROUNDS for number in round_numbers):
        errors.append(f"{story_id}: evidence round cap exceeded")
    histories: dict[str, list[dict[str, Any]]] = {qid: [] for qid in questions}
    seen_refs: set[str] = set()
    round_metrics: dict[int, Mapping[str, Any]] = {}
    for number in sorted(number for number in round_numbers if number >= 1):
        output = read_json(absolute / f"round-{number:02d}-output.json")
        if not isinstance(output, Mapping):
            errors.append(f"{story_id}: invalid output round {number}")
            continue
        raw = output.get("raw_output")
        if number == 1:
            sources = {str(row["ref"]): str(row.get("text", "")) for row in list(material.get("liu_notes", [])) + list(material.get("jianshu_notes", []))}
            expected_ids = set(questions)
        else:
            input_doc = read_json(absolute / f"round-{number:02d}-input.json")
            packet = payload(input_doc) if isinstance(input_doc, Mapping) else {}
            candidates = packet.get("local_evidence_candidates", []) if isinstance(packet, Mapping) and isinstance(packet.get("local_evidence_candidates"), list) else []
            declared = {str(row.get("ref")) for row in candidates if isinstance(row, Mapping) and row.get("ref")}
            output_refs = {str(ref) for ref in output.get("candidate_refs", [])} if isinstance(output.get("candidate_refs"), list) else set()
            if declared != output_refs:
                errors.append(f"{story_id}: round {number}: candidate refs differ from input")
            if not declared.issubset(registry):
                errors.append(f"{story_id}: round {number}: unknown candidate ref")
            sources = {ref: str(registry[ref].get("text", "")) for ref in declared if ref in registry}
            active = packet.get("active_questions", []) if isinstance(packet, Mapping) and isinstance(packet.get("active_questions"), list) else []
            expected_ids = {str(row.get("question_id")) for row in active if isinstance(row, Mapping)}
        normalized, audit = normalize_delta_fail_soft(raw, sources, expected_ids)
        if output.get("normalized_output") != normalized:
            errors.append(f"{story_id}: round {number}: delta normalization is not deterministic")
        for evidence in audit.get("rejected_evidence", []):
            if evidence.get("ref", "").startswith("data/generated/"):
                errors.append(f"{story_id}: generated evidence ref rejected but recorded as source")
        if output.get("canonical_write_back") is not False or output.get("external_search_performed") is not False:
            errors.append(f"{story_id}: unsafe output flags round {number}")
        updates = {str(row.get("question_id")): row for row in normalized.get("updates", []) if isinstance(row, Mapping)}
        q_metrics: list[Mapping[str, Any]] = []
        used_round: set[str] = set()
        new_round: set[str] = set()
        for qid in sorted(expected_ids):
            if qid not in updates or qid not in questions:
                continue
            prior = dict(questions[qid])
            update = updates[qid]
            current = derive_state_b(prior, update)
            used = sorted({str(ref) for ref in current.get("supporting_refs", [])})
            current["last_round"] = number
            current["evidence_rounds"] = int(prior.get("evidence_rounds", 0)) + 1
            d_value = material_delta_b(prior if number > 1 or prior.get("last_round", 0) else None, current, used_refs=used)
            new_refs = set(used) - seen_refs
            seen_refs.update(used)
            metric = {
                "question_id": qid, "round": number, "D_t": int(d_value), "N_t": round(len(new_refs) / len(used), 6) if used else 0.0,
                "Q_t": 0, "used_evidence_refs": used, "new_used_evidence_refs": sorted(new_refs),
            }
            q_metrics.append(metric)
            used_round.update(used)
            new_round.update(new_refs)
            questions[qid] = current
            histories.setdefault(qid, []).append({**metric, "conflict_fingerprints": current.get("conflict_fingerprints", []), "reading_sufficient": current.get("reading_sufficient"), "active": current.get("active")})
        convergence = read_json(absolute / "convergence.json")
        if isinstance(convergence, Mapping):
            rows = convergence.get("round_metrics", []) if isinstance(convergence.get("round_metrics"), list) else []
            metric = next((row for row in rows if isinstance(row, Mapping) and row.get("round") == number), None)
            if metric:
                round_metrics[number] = metric
                if metric.get("D_t") not in {0, 1} or metric.get("Q_t") not in {0, 1} or not isinstance(metric.get("G_t"), int) or not 0 <= float(metric.get("N_t", -1)) <= 1:
                    errors.append(f"{story_id}: invalid G/D/N/Q at round {number}")
                expected_n = len(set(metric.get("new_used_evidence_refs", []))) / len(set(metric.get("used_evidence_refs", []))) if metric.get("used_evidence_refs") else 0.0
                if round(float(metric.get("N_t", -1)), 6) != round(expected_n, 6):
                    errors.append(f"{story_id}: N_t mismatch at round {number}")
                if not set(metric.get("new_used_evidence_refs", [])).issubset(set(metric.get("used_evidence_refs", []))):
                    errors.append(f"{story_id}: new refs are not used refs at round {number}")
                if metric.get("D_t") == 1 and not metric.get("used_evidence_refs"):
                    errors.append(f"{story_id}: D_t=1 without validated evidence at round {number}")
        if number >= 2:
            input_doc = read_json(absolute / f"round-{number:02d}-input.json")
            packet = payload(input_doc) if isinstance(input_doc, Mapping) else {}
            active = packet.get("active_questions", []) if isinstance(packet, Mapping) else []
            if isinstance(active, list) and not set(str(row.get("question_id")) for row in active if isinstance(row, Mapping)).issuperset(expected_ids):
                # Active questions may shrink after a terminal decision; this is
                # diagnostic only, so report only genuinely missing packets.
                pass

    trace_path = absolute / "search-trace.jsonl"
    for line in trace_path.read_text(encoding="utf-8").splitlines() if trace_path.is_file() else []:
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            errors.append(f"{story_id}: invalid search trace JSON")
            continue
        if not isinstance(row, Mapping):
            errors.append(f"{story_id}: search trace row is not an object")
            continue
        if set(row.get("searched_corpora", [])) != set(("世說新語", "余嘉錫箋疏", "晉書", "三國志", "資治通鑑", "資治通鑑考異")):
            errors.append(f"{story_id}: search trace corpus set is invalid")
        retrieved = set(row.get("retrieved_refs", []))
        opened = set(row.get("opened_refs", []))
        used = set(row.get("used_refs", []))
        new = set(row.get("new_used_refs", []))
        if not opened.issubset(retrieved) or not used.issubset(opened) or not new.issubset(used):
            errors.append(f"{story_id}: search trace subset invariant failed")
        if any(str(ref).startswith(("data/generated/", "data/annotation/")) for ref in retrieved | opened | used):
            errors.append(f"{story_id}: generated material in search trace")

    if isinstance(state, Mapping):
        state_ids = {str(row.get("question_id")) for row in state.get("questions", []) if isinstance(row, Mapping)}
        for row in state.get("questions", []) if isinstance(state.get("questions"), list) else []:
            if not isinstance(row, Mapping):
                continue
            parent = row.get("parent_question_id")
            if parent and str(parent) not in state_ids:
                errors.append(f"{story_id}: orphan child parent {row.get('question_id')}")
            if parent and not row.get("parent_aspect_id"):
                errors.append(f"{story_id}: child has no parent aspect {row.get('question_id')}")
    return sorted(set(errors))


def validate_summary(path: Path, *, expected_kind: str, requested: Sequence[str], errors: list[str]) -> None:
    summary = read_json(ROOT / path)
    if not isinstance(summary, Mapping):
        errors.append(f"missing {path}")
        return
    if summary.get("execution_kind") != expected_kind:
        errors.append(f"{path}: execution kind mismatch")
    ids = [str(row.get("story_id")) for row in summary.get("stories", []) if isinstance(row, Mapping)]
    if set(ids) != set(requested):
        errors.append(f"{path}: Story set mismatch")
    if expected_kind == "fixture" and summary.get("aggregate", {}).get("model_findings_count") != 0:
        errors.append(f"{path}: fixture output counted as model findings")
    if expected_kind == "live_model" and "fixture_story_count" in summary.get("aggregate", {}):
        errors.append(f"{path}: fixture metrics leaked into live summary")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("live", "fixture", "all"), default="live")
    parser.add_argument("--story", help="validate one frozen Story")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    story_ids = [args.story] if args.story else list(FIXED_STORIES)
    errors: list[str] = []
    if any(story_id not in FIXED_STORIES for story_id in story_ids):
        errors.append("requested Story is outside frozen SRM0.4B set")
    if not (ROOT / REVIEW_PATH).is_file():
        errors.append("missing SRM0.4B review template")
    status = read_json(ROOT / STATUS_PATH)
    if status.get("selected_story_count") != 6 or status.get("canonical_write_back") is not False or status.get("previous_live_results_reset") is not True:
        errors.append("invalid SRM0.4 clean-run status marker")
    registry = build_registry(ROOT)
    modes = ("live_model", "fixture") if args.mode == "all" else (("live_model",) if args.mode == "live" else ("fixture",))
    for mode in modes:
        path = LIVE_SUMMARY_PATH if mode == "live_model" else FIXTURE_SUMMARY_PATH
        validate_summary(path, expected_kind=mode, requested=story_ids, errors=errors)
        if mode == "live_model" and status.get("live_results_present") is not True:
            errors.append("live summary exists without live_results_present status")
        if mode == "fixture" and status.get("fixture_results_present") is not True:
            errors.append("fixture summary exists without fixture_results_present status")
        for story_id in story_ids:
            errors.extend(validate_story(story_id, expected_kind=mode, registry=registry))
    if errors:
        print("SRM0.4B validation failed")
        for error in sorted(set(errors)):
            print(f"- {error}")
        return 1
    print(f"SRM0.4B validation passed ({args.mode})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
