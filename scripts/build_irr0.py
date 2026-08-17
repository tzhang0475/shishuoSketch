#!/usr/bin/env python3
"""Build the deterministic IRR0.1 iterative-reading experiment.

IRR0.1 is a reviewed annotation/projection layer.  It reads the fixed pilot
Stories and existing HR0/HR0.1/NL0/NL1/S1 evidence, then emits structured
reading states and diagnostic gain vectors.  It never writes canonical
historical data and performs no retrieval or model inference.
"""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
from typing import Any, Iterable, Mapping


ROOT = Path(__file__).resolve().parents[1]

REVIEW_PATH = Path("data/annotation/irr0-iterative-reading-review.json")
SCHEMA_PATH = Path("schema/iterative-reading-state.schema.json")
SC1_PATH = Path("data/derived/sc1-site.json")
HR0_PATH = Path("data/derived/hr0-historical-situations.json")
HR01_PATH = Path("data/derived/hr0-1-ambiguity-benchmark.json")
NL0_GOLD_PATH = Path("data/derived/nl0-story-sketch-gold.json")
NL1_CONTEXT_PATH = Path("data/derived/nl1-narrative-context.json")
NL1_SELECTION_PATH = Path("data/derived/nl1-narrative-selection-gold.json")
S1_ASSERTIONS_PATH = Path("data/derived/s1-jianshu-historical-assertions.json")

GOLD_PATH = Path("data/derived/irr0-iterative-reading-gold.json")
REPORT_PATH = Path("data/derived/irr0-gain-report.json")

PILOT_STORY_IDS = (
    "27-jiajue-008",
    "06-yaliang-017",
    "09-pinzao-017",
    "19-xianyuan-026",
    "05-fangzheng-032",
)

INPUT_PATHS = (
    REVIEW_PATH,
    SCHEMA_PATH,
    SC1_PATH,
    HR0_PATH,
    HR01_PATH,
    NL0_GOLD_PATH,
    NL1_CONTEXT_PATH,
    NL1_SELECTION_PATH,
    S1_ASSERTIONS_PATH,
)

ALLOWED_DELTA_FIELDS = (
    "historical_changes",
    "newly_salient_spans",
    "reinterpretations",
    "newly_understood_omissions",
    "new_connections",
    "resolved_questions",
    "new_questions",
)

POLICY = {
    "canonical_data_write_back": False,
    "canonical_fact_materialization": False,
    "llm_calls": False,
    "retrieval": False,
    "persistent_memory": False,
    "frontend_changes": False,
    "new_historical_facts": False,
    "review_model": "reviewed_deterministic_annotation",
}

SCORING_POLICY = {
    "normalization": (
        "G_H=min(1,historical_changes/3); G_L is the mean positive critical-span "
        "depth increase divided by 3; G_A=min(1,(omissions+reinterpretations)/2); "
        "G_C=min(1,new_connections/2); G_U=min(1,resolved_questions/2); "
        "G_D=min(1,distraction_flags/2). Each component is clipped to [0,1]."
    ),
    "mrg_definition": "MRG = G_H + G_L + G_A + G_C + G_U - G_D; diagnostic only, not an authoritative score.",
}


def read_json(root: Path, relative: Path) -> Any:
    return json.loads((root / relative).read_text(encoding="utf-8"))


def sha256_file(root: Path, relative: Path) -> str:
    digest = hashlib.sha256()
    with (root / relative).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def stable_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def write_json(root: Path, relative: Path, value: Any) -> None:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(stable_json(value), encoding="utf-8")


def source_hashes(root: Path) -> dict[str, str]:
    return {path.as_posix(): sha256_file(root, path) for path in INPUT_PATHS}


def source_layer(evidence_type: str) -> str:
    return {
        "primary_text": "base_text",
        "annotation": "liu_annotation",
        "editorial": "editorial",
        "secondary_reference": "secondary_reference",
    }.get(evidence_type, "unknown")


def sorted_unique(values: Iterable[Any]) -> list[str]:
    return sorted({str(value) for value in values})


def collect_evidence_refs(value: Any) -> set[str]:
    """Collect only explicit evidence references, not arbitrary IDs."""

    refs: set[str] = set()
    if isinstance(value, Mapping):
        if isinstance(value.get("evidence_refs"), list):
            refs.update(str(item) for item in value["evidence_refs"])
        if isinstance(value.get("evidence_ref"), str):
            refs.add(value["evidence_ref"])
        for child in value.values():
            refs.update(collect_evidence_refs(child))
    elif isinstance(value, list):
        for child in value:
            refs.update(collect_evidence_refs(child))
    return refs


def normalize_delta(raw: Any) -> dict[str, list[dict[str, Any]]]:
    if not isinstance(raw, Mapping):
        raise ValueError("IRR0.1 context rounds require a structured delta annotation")
    unknown = sorted(set(raw) - set(ALLOWED_DELTA_FIELDS))
    if unknown:
        raise ValueError(f"IRR0.1 delta has unknown fields: {unknown}")
    result: dict[str, list[dict[str, Any]]] = {}
    for field in ALLOWED_DELTA_FIELDS:
        rows = raw.get(field, [])
        if not isinstance(rows, list):
            raise ValueError(f"IRR0.1 delta field is not a list: {field}")
        result[field] = copy.deepcopy(rows)
    return result


def evidence_descriptor(
    ref: str,
    story_id: str,
    story_evidence: Mapping[str, Mapping[str, Any]],
    assertions: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    if ref in story_evidence:
        row = story_evidence[ref]
        return {
            "evidence_ref": ref,
            "kind": "story_evidence",
            "source_layer": source_layer(str(row.get("evidence_type"))),
            "source_id": str(row.get("source_id")),
            "assertion_status": str(row.get("assertion_status")),
            "review_status": str(row.get("review_status")),
            "quote_sha256": hashlib.sha256(str(row.get("quote", "")).encode("utf-8")).hexdigest(),
            "locator": copy.deepcopy(row.get("locator", {})),
        }
    if ref in assertions:
        row = assertions[ref]
        locator = copy.deepcopy(row.get("source_locator", {}))
        locator.setdefault("artifact_type", "jianshu_assertion")
        return {
            "evidence_ref": ref,
            "kind": "s1_assertion",
            "source_layer": str(row.get("layer", "unknown")),
            "source_id": "shishuo-jianshu",
            "assertion_status": str(row.get("modality", "unknown")),
            "review_status": str(row.get("candidate_status", "candidate")),
            "quote_sha256": str(row.get("text_sha256", "")),
            "locator": locator,
        }
    raise ValueError(f"unknown IRR0.1 evidence reference: {story_id}/{ref}")


def depth_rows(record: Mapping[str, Any], round_number: int) -> list[dict[str, Any]]:
    spans = [row for row in record["rounds"][round_number]["text_reading"]["salient_spans"] if row.get("critical")]
    current = {str(row["span"]): int(row["depth"]) for row in spans}
    if round_number == 0:
        return [
            {"span": span, "before": 0, "after": current[span]}
            for span in sorted(current)
        ]
    previous_rows = record["rounds"][round_number - 1]["text_reading"]["salient_spans"]
    previous = {str(row["span"]): int(row["depth"]) for row in previous_rows if row.get("critical")}
    return [
        {"span": span, "before": previous.get(span, 0), "after": current[span]}
        for span in sorted(current)
    ]


def gain_vector(record: Mapping[str, Any], round_number: int, delta: dict[str, list[dict[str, Any]]] | None) -> dict[str, float]:
    if round_number == 0:
        return {"G_H": 0.0, "G_L": 0.0, "G_A": 0.0, "G_C": 0.0, "G_U": 0.0, "G_D": 0.0, "MRG": 0.0}
    assert delta is not None
    transitions = depth_rows(record, round_number)
    positive_depth = [max(0, row["after"] - row["before"]) for row in transitions]
    gl = (sum(positive_depth) / len(positive_depth) / 3) if positive_depth else 0.0
    gh = min(1.0, len(delta["historical_changes"]) / 3)
    ga = min(1.0, (len(delta["newly_understood_omissions"]) + len(delta["reinterpretations"])) / 2)
    gc = min(1.0, len(delta["new_connections"]) / 2)
    gu = min(1.0, len(delta["resolved_questions"]) / 2)
    gd = min(1.0, len(record["rounds"][round_number].get("distraction_flags", [])) / 2)
    values = {
        "G_H": round(min(1.0, gh), 6),
        "G_L": round(min(1.0, gl), 6),
        "G_A": round(min(1.0, ga), 6),
        "G_C": round(min(1.0, gc), 6),
        "G_U": round(min(1.0, gu), 6),
        "G_D": round(min(1.0, gd), 6),
    }
    values["MRG"] = round(sum(values[key] for key in ("G_H", "G_L", "G_A", "G_C", "G_U")) - values["G_D"], 6)
    return values


def build_record(
    review_record: Mapping[str, Any],
    stories: Mapping[str, Mapping[str, Any]],
    hr0_by_story: Mapping[str, Mapping[str, Any]],
    hr01_by_story: Mapping[str, Mapping[str, Any]],
    nl0_by_story: Mapping[str, Mapping[str, Any]],
    nl1_context_by_story: Mapping[str, Mapping[str, Any]],
    nl1_selection_by_story: Mapping[str, Mapping[str, Any]],
    story_evidence: Mapping[str, Mapping[str, Any]],
    assertions: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    story_id = str(review_record["story_id"])
    if story_id not in stories:
        raise ValueError(f"IRR0.1 references unknown Story: {story_id}")
    if story_id not in hr0_by_story or story_id not in hr01_by_story:
        raise ValueError(f"IRR0.1 Story lacks HR0/HR0.1 grounding: {story_id}")
    if story_id not in nl0_by_story or story_id not in nl1_context_by_story or story_id not in nl1_selection_by_story:
        raise ValueError(f"IRR0.1 Story lacks NL0/NL1 grounding: {story_id}")
    record_evidence = {ref: story_evidence[ref] for ref in story_evidence if ref in set(stories[story_id].get("evidence_ids", []))}
    refs = collect_evidence_refs(review_record)
    for ref in refs:
        if ref in assertions and str(assertions[ref].get("story_id")) != story_id:
            raise ValueError(f"IRR0.1 assertion belongs to another Story: {story_id}/{ref}")
        if ref not in record_evidence and ref not in assertions:
            raise ValueError(f"IRR0.1 reference is not in the Story evidence catalog: {story_id}/{ref}")
    evidence_index = [evidence_descriptor(ref, story_id, record_evidence, assertions) for ref in sorted(refs)]

    output_rounds: list[dict[str, Any]] = []
    for index, source_round in enumerate(review_record.get("rounds", [])):
        if int(source_round.get("round")) != index:
            raise ValueError(f"IRR0.1 round ordering is not contiguous: {story_id}")
        round_copy = copy.deepcopy(source_round)
        delta = None if index == 0 else normalize_delta(source_round.get("delta_annotations"))
        round_copy.pop("delta_annotations", None)
        round_copy["reading_delta"] = delta
        round_copy["gain_vector"] = gain_vector(review_record, index, delta)
        output_rounds.append(round_copy)

    # The source review file is intentionally compact.  The derived record
    # carries a fully explicit critical-span list for downstream benchmarks.
    critical_spans = sorted({str(value) for value in review_record.get("critical_spans", [])})
    if not critical_spans:
        raise ValueError(f"IRR0.1 requires at least one critical span: {story_id}")
    for span in critical_spans:
        if not any(span == str(row.get("span")) for current in output_rounds for row in current["text_reading"]["salient_spans"]):
            raise ValueError(f"IRR0.1 critical span is not annotated: {story_id}/{span}")

    return {
        "story_id": story_id,
        "state_id": str(review_record["state_id"]),
        "review_status": "reviewed_gold",
        "grounding": copy.deepcopy(review_record["grounding"]),
        "evidence_index": evidence_index,
        "critical_spans": critical_spans,
        "rounds": output_rounds,
    }


def build_documents(root: Path = ROOT) -> tuple[dict[str, Any], dict[str, Any]]:
    review = read_json(root, REVIEW_PATH)
    schema = read_json(root, SCHEMA_PATH)
    sc1 = read_json(root, SC1_PATH)
    hr0 = read_json(root, HR0_PATH)
    hr01 = read_json(root, HR01_PATH)
    nl0 = read_json(root, NL0_GOLD_PATH)
    nl1_context = read_json(root, NL1_CONTEXT_PATH)
    nl1_selection = read_json(root, NL1_SELECTION_PATH)
    s1 = read_json(root, S1_ASSERTIONS_PATH)

    review_ids = [str(row.get("story_id")) for row in review.get("records", [])]
    if review_ids != sorted(review_ids) or set(review_ids) != set(PILOT_STORY_IDS):
        raise ValueError("IRR0.1 review scope must contain exactly the fixed five pilot Stories")
    stories = {str(row["id"]): row for row in sc1.get("stories", [])}
    global_evidence = {str(row["id"]): row for row in sc1.get("evidence", [])}
    assertions = {str(row["assertion_id"]): row for row in s1.get("records", [])}
    hr0_by_story = {str(row["story_id"]): row for row in hr0.get("records", [])}
    hr01_by_story = {str(row["story_id"]): row for row in hr01.get("records", [])}
    nl0_by_story = {str(row["story_id"]): row for row in nl0.get("records", [])}
    nl1_context_by_story = {str(row["story_id"]): row for row in nl1_context.get("records", [])}
    nl1_selection_by_story = {str(row["story_id"]): row for row in nl1_selection.get("records", [])}

    output_records: list[dict[str, Any]] = []
    for story_id in PILOT_STORY_IDS:
        review_record = next(row for row in review.get("records", []) if str(row["story_id"]) == story_id)
        output_records.append(
            build_record(
                review_record,
                stories,
                hr0_by_story,
                hr01_by_story,
                nl0_by_story,
                nl1_context_by_story,
                nl1_selection_by_story,
                global_evidence,
                assertions,
            )
        )

    hashes = source_hashes(root)
    rounds = sum(len(row["rounds"]) for row in output_records)
    context_rounds = sum(max(0, len(row["rounds"]) - 1) for row in output_records)
    evidence_added = sum(len(current["evidence_added"]) for row in output_records for current in row["rounds"])
    hard_negative_rounds = sum(
        1
        for row in output_records
        for current in row["rounds"]
        if any(item.get("expected_role") == "hard_negative" for item in current.get("evidence_added", []))
    )
    progression = []
    for row in output_records:
        depths = []
        for current in row["rounds"]:
            critical = [int(item["depth"]) for item in current["text_reading"]["salient_spans"] if item.get("critical")]
            depths.append(round(sum(critical) / len(critical), 6) if critical else 0.0)
        if len(depths) >= 3 and depths[0] < depths[1] < depths[2]:
            progression.append(row["story_id"])

    gold = {
        "schema": "iterative-reading-state-gold",
        "stage": "IRR0.1",
        "schema_version": "v0",
        "scope": {
            "story_count": len(output_records),
            "story_ids": list(PILOT_STORY_IDS),
            "rounds_per_story": {row["story_id"]: len(row["rounds"]) for row in output_records},
        },
        "records": output_records,
        "counts": {
            "stories": len(output_records),
            "rounds": rounds,
            "context_rounds": context_rounds,
            "evidence_added": evidence_added,
            "hard_negative_rounds": hard_negative_rounds,
            "critical_spans": sum(len(row["critical_spans"]) for row in output_records),
            "progressive_depth_stories": len(progression),
        },
        "source_hashes": hashes,
        "policy": POLICY,
        "scoring_policy": SCORING_POLICY,
    }

    report_rows: list[dict[str, Any]] = []
    for row in output_records:
        round_rows: list[dict[str, Any]] = []
        for index, current in enumerate(row["rounds"]):
            transitions = depth_rows(row, index)
            before = 0.0 if index == 0 else round(sum(item["before"] for item in transitions) / len(transitions), 6)
            after = round(sum(item["after"] for item in transitions) / len(transitions), 6)
            round_rows.append(
                {
                    "round": index,
                    "critical_depth_before": before,
                    "critical_depth_after": after,
                    "critical_span_depths": transitions,
                    "evidence_added": [item["evidence_ref"] for item in current.get("evidence_added", [])],
                    "expected_roles": [item["expected_role"] for item in current.get("evidence_added", [])],
                    **current["gain_vector"],
                }
            )
        report_rows.append({"story_id": row["story_id"], "rounds": round_rows})

    report = {
        "schema": "irr0-gain-report",
        "stage": "IRR0.1",
        "schema_version": "v0",
        "source_hashes": hashes,
        "scoring_policy": SCORING_POLICY,
        "per_story": report_rows,
        "summary": {
            "story_count": len(output_records),
            "round_count": rounds,
            "context_round_count": context_rounds,
            "progressive_depth_stories": progression,
            "hard_negative_rounds": hard_negative_rounds,
            "expected_role_counts": {
                role: sum(
                    1
                    for row in output_records
                    for current in row["rounds"]
                    for item in current.get("evidence_added", [])
                    if item.get("expected_role") == role
                )
                for role in ("high_gain", "medium_gain", "hard_negative")
            },
            "interpretation": "Gain vectors are structured experimental diagnostics; MRG is not historical truth or a Story quality ranking.",
        },
    }
    return gold, report


def build(root: Path = ROOT) -> None:
    gold, report = build_documents(root)
    write_json(root, GOLD_PATH, gold)
    write_json(root, REPORT_PATH, report)


if __name__ == "__main__":
    build()
    print(f"wrote {GOLD_PATH}")
    print(f"wrote {REPORT_PATH}")
