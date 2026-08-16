#!/usr/bin/env python3
"""Build the isolated NL0 StorySketch review and frontend projection.

NL0 is deliberately a small, hand-reviewed narrative projection.  It reads
HR0/HR0.1 and existing reviewed historical-fact indexes, but never writes to
canonical Story, Person, Mention, Relation, or fact data.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Iterable, Mapping


ROOT = Path(__file__).resolve().parents[1]
SPEC_PATH = Path("data/annotation/nl0-story-sketch-review.json")
SCHEMA_PATH = Path("schema/story-sketch.schema.json")
SC1_PATH = Path("data/derived/sc1-site.json")
HR0_PATH = Path("data/derived/hr0-historical-situations.json")
HR01_PATH = Path("data/derived/hr0-1-ambiguity-benchmark.json")
H0C_FACTS_PATH = Path("data/derived/h0c-historical-facts.json")
X1_2RF_FACTS_PATH = Path("data/derived/x1-2rf-materialized-facts.json")
CANDIDATES_PATH = Path("data/derived/nl0-story-sketch-candidates.json")
GOLD_PATH = Path("data/derived/nl0-story-sketch-gold.json")
METRICS_PATH = Path("data/derived/nl0-metrics.json")
PROTECTION_PATH = Path("data/derived/nl0-protection-manifest.json")
PUBLIC_ROOT = Path("site/public/generated/nl0")
SHARD_ROOT = PUBLIC_ROOT / "story-sketch"
EVIDENCE_SHARD_ROOT = PUBLIC_ROOT / "evidence"
PUBLIC_MANIFEST_PATH = PUBLIC_ROOT / "manifest.json"

INPUT_PATHS = (
    SPEC_PATH,
    SCHEMA_PATH,
    SC1_PATH,
    HR0_PATH,
    HR01_PATH,
    H0C_FACTS_PATH,
    X1_2RF_FACTS_PATH,
)
PROTECTED_PATHS = (
    SC1_PATH,
    HR0_PATH,
    HR01_PATH,
    H0C_FACTS_PATH,
    X1_2RF_FACTS_PATH,
)

POLICY = {
    "canonical_data_write_back": False,
    "canonical_fact_materialization": False,
    "llm": False,
    "rag": False,
    "generated_fields_may_abstain": True,
    "frontend_requires_accepted_review": True,
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


def unique_sorted(values: Iterable[str]) -> list[str]:
    return sorted({str(value) for value in values})


def source_hashes(root: Path) -> dict[str, str]:
    return {path.as_posix(): sha256_file(root, path) for path in INPUT_PATHS}


def evidence_refs_by_id(record: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    return {str(ref["evidence_id"]): ref for ref in record.get("evidence_refs", [])}


def reviewed_fact_ids_for_story(
    story_id: str,
    story_evidence_ids: set[str],
    h0c: Mapping[str, Any],
    x1_2rf: Mapping[str, Any],
) -> list[str]:
    """Return read-only reviewed fact references that ground this Story.

    These IDs are metadata for review lineage only.  They are not copied into
    the display sketch as newly asserted facts.
    """

    result: set[str] = set()
    for fact in h0c.get("fact_index", []):
        subject_ids = {str(value) for value in fact.get("subject_ids", [])}
        evidence_ids = {str(value) for value in fact.get("evidence_ids", [])}
        if fact.get("review_status") == "reviewed" and (
            story_id in subject_ids or evidence_ids & story_evidence_ids
        ):
            result.add(str(fact["fact_id"]))
    for fact in x1_2rf.get("facts", []):
        evidence_ids = {str(value) for value in fact.get("evidence_ids", [])}
        if evidence_ids & story_evidence_ids:
            result.add(str(fact["fact_id"]))
    return sorted(result)


def claim_rows(record: Mapping[str, Any]) -> list[tuple[str, Mapping[str, Any]]]:
    rows: list[tuple[str, Mapping[str, Any]]] = []
    era = record.get("era_profile")
    if era is not None:
        rows.append(("era_profile", era))
    rows.append(("scene_core", record["scene_core"]))
    rows.extend(("essential_background", row) for row in record.get("essential_background", []))
    resonance = record.get("resonance")
    if resonance is not None:
        rows.append(("resonance", resonance))
    return rows


def build_record(
    spec_record: Mapping[str, Any],
    stories_by_id: Mapping[str, Mapping[str, Any]],
    hr0_by_story: Mapping[str, Mapping[str, Any]],
    hr01_by_story: Mapping[str, Mapping[str, Any]],
    h0c: Mapping[str, Any],
    x1_2rf: Mapping[str, Any],
) -> dict[str, Any]:
    story_id = str(spec_record["story_id"])
    story = stories_by_id[story_id]
    hr0 = hr0_by_story[story_id]
    hr01 = hr01_by_story[story_id]
    evidence_by_id = evidence_refs_by_id(hr0)
    story_evidence_ids = set(evidence_by_id)

    support_roles: dict[str, set[str]] = {}
    claims: dict[str, Any] = {}
    for role, claim in claim_rows(spec_record):
        claim_copy = {
            "claim_type": role,
            "text": claim["text"],
            "evidence_ids": unique_sorted(claim["evidence_ids"]),
            "grounding_note": claim["grounding_note"],
        }
        claims.setdefault(role, []).append(claim_copy) if role == "essential_background" else claims.__setitem__(role, claim_copy)
        for evidence_id in claim_copy["evidence_ids"]:
            support_roles.setdefault(evidence_id, set()).add(role)

    supporting_evidence: list[dict[str, Any]] = []
    for evidence_id in sorted(support_roles):
        ref = evidence_by_id[evidence_id]
        supporting_evidence.append(
            {
                "evidence_id": evidence_id,
                "source_id": str(ref["source_id"]),
                "source_layer": str(ref["source_layer"]),
                "evidence_type": str(ref["evidence_type"]),
                "source_review_status": str(ref["review_status"]),
                "nl0_review_status": "reviewed",
                "support_roles": sorted(support_roles[evidence_id]),
            }
        )

    result: dict[str, Any] = {
        "story_id": story_id,
        "sketch_id": f"story-sketch-nl0-{story_id}",
        "selection_categories": sorted(set(spec_record["selection_categories"])),
        "candidate_status": "candidate",
        "review_status": "reviewed",
        "review_decision": str(spec_record["review_decision"]),
        "review_note": str(spec_record["review_note"]),
        "era_profile": claims.get("era_profile"),
        "scene_core": claims["scene_core"],
        "essential_background": claims.get("essential_background", []),
        "resonance": claims.get("resonance"),
        "supporting_evidence": supporting_evidence,
        "grounded_inputs": {
            "hr0_situation_id": str(hr0["situation_id"]),
            "hr0_1_case_ids": sorted(set(hr01.get("case_ids", []))),
            "historical_fact_ids": reviewed_fact_ids_for_story(story_id, story_evidence_ids, h0c, x1_2rf),
        },
    }
    # The builder intentionally reads these objects to make the selected
    # Story/evidence boundary explicit, while the display projection remains
    # limited to reviewed narrative fields and evidence IDs.
    if str(story.get("id")) != story_id:
        raise ValueError(f"Story lookup mismatch for {story_id}")
    return result


def make_gold_record(candidate: Mapping[str, Any]) -> dict[str, Any]:
    record = dict(candidate)
    record["review_status"] = "accepted"
    record["review_decision"] = "accepted"
    return record


def display_shard(record: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "schema": 1,
        "projection": "nl0_story_sketch",
        "story_id": record["story_id"],
        "review_status": "accepted",
        "selection_categories": record["selection_categories"],
        "era_profile": record["era_profile"],
        "scene_core": record["scene_core"],
        "essential_background": record["essential_background"],
        "resonance": record["resonance"],
        "supporting_evidence": record["supporting_evidence"],
    }


def shorten_pair(pair_value: Mapping[str, Any], limit: int = 280) -> dict[str, str]:
    def shorten(value: Any) -> str:
        text = " ".join(str(value or "").split())
        return text if len(text) <= limit else f"{text[:limit - 1]}…"

    return {
        "original": shorten(pair_value.get("original")),
        "simplified": shorten(pair_value.get("simplified")),
    }


def evidence_shard(
    evidence_id: str,
    sc1_evidence: Mapping[str, Mapping[str, Any]],
    hr0_evidence: Mapping[str, Mapping[str, Any]],
    display_evidence: Mapping[str, Mapping[str, Any]],
    display_sources: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    item = sc1_evidence[evidence_id]
    ref = hr0_evidence[evidence_id]
    source_display = display_sources.get(str(item.get("source_id"))) or {}
    # D1.1 keeps bilingual evidence text in the shared display registry.
    # The NL0 shard copies only this short, explicitly requested excerpt.
    display = display_evidence.get(evidence_id) or {}
    if not display:
        display = {
            "original": str(item.get("quote") or ""),
            "simplified": str(item.get("quote") or ""),
        }
    locator = item.get("locator") or {}
    source_provenance = locator.get("source_provenance") or {}
    locator_text = " · ".join(
        str(value)
        for value in (
            locator.get("artifact_path"),
            source_provenance.get("witness_id"),
        )
        if value
    )
    return {
        "schema": 1,
        "projection": "nl0_story_sketch_evidence",
        "evidence_id": evidence_id,
        "source_label": {
            "work": source_display.get("work") or {"original": "世说新语", "simplified": "世说新语"},
            "edition": source_display.get("edition") or {"original": "", "simplified": ""},
        },
        "source_layer": str(ref["source_layer"]),
        "evidence_type": str(ref["evidence_type"]),
        "source_review_status": str(ref["review_status"]),
        "nl0_review_status": "reviewed",
        "locator": locator_text,
        "short_excerpt": shorten_pair(display),
    }


def build_documents(root: Path = ROOT) -> dict[str, Any]:
    spec = read_json(root, SPEC_PATH)
    sc1 = read_json(root, SC1_PATH)
    hr0 = read_json(root, HR0_PATH)
    hr01 = read_json(root, HR01_PATH)
    h0c = read_json(root, H0C_FACTS_PATH)
    x1_2rf = read_json(root, X1_2RF_FACTS_PATH)

    stories_by_id = {str(row["id"]): row for row in sc1.get("stories", [])}
    sc1_evidence_by_id = {str(row["id"]): row for row in sc1.get("evidence", [])}
    shared_display = sc1.get("display") or {}
    shared_evidence_display = shared_display.get("evidence") or {}
    shared_source_display = shared_display.get("sources") or {}
    hr0_by_story = {str(row["story_id"]): row for row in hr0.get("records", [])}
    hr01_by_story = {str(row["story_id"]): row for row in hr01.get("records", [])}
    selected_ids = sorted(str(value) for value in spec["scope"]["selected_story_ids"])
    if selected_ids != [str(row["story_id"]) for row in sorted(spec["records"], key=lambda item: str(item["story_id"]))]:
        raise ValueError("NL0 selection ordering does not match review records")

    candidates = [
        build_record(spec_record, stories_by_id, hr0_by_story, hr01_by_story, h0c, x1_2rf)
        for spec_record in sorted(spec["records"], key=lambda item: str(item["story_id"]))
    ]
    hashes = source_hashes(root)
    common = {
        "schema": "story-sketch",
        "stage": "NL0",
        "schema_version": "v0",
        "scope": {
            "story_count": len(selected_ids),
            "selected_story_ids": selected_ids,
            "selection_policy": str(spec["scope"]["selection_policy"]),
        },
        "source_hashes": hashes,
        "policy": POLICY,
    }
    candidate_document = {
        **common,
        "document_kind": "candidates",
        "counts": {
            "records": len(candidates),
            "candidate_records": len(candidates),
            "reviewed_records": len(candidates),
            "accepted_records": sum(row["review_decision"] == "accepted" for row in candidates),
            "rejected_records": sum(row["review_decision"] == "rejected" for row in candidates),
        },
        "records": candidates,
    }
    gold_records = [make_gold_record(row) for row in candidates if row["review_decision"] == "accepted"]
    gold_document = {
        **common,
        "document_kind": "gold",
        "counts": {
            "records": len(gold_records),
            "accepted_records": len(gold_records),
            "background_claims": sum(len(row["essential_background"]) for row in gold_records),
            "resonance_claims": sum(row["resonance"] is not None for row in gold_records),
            "abstained_era_profiles": sum(row["era_profile"] is None for row in gold_records),
            "abstained_resonance": sum(row["resonance"] is None for row in gold_records),
        },
        "records": gold_records,
    }

    claim_count = sum(len(claim_rows(row)) for row in candidates)
    evidence_id_count = sum(len(row["supporting_evidence"]) for row in candidates)
    selection_categories: dict[str, int] = {}
    source_layers: dict[str, int] = {}
    for row in candidates:
        for category in row["selection_categories"]:
            selection_categories[category] = selection_categories.get(category, 0) + 1
        for evidence in row["supporting_evidence"]:
            layer = evidence["source_layer"]
            source_layers[layer] = source_layers.get(layer, 0) + 1
    metrics = {
        "schema": "nl0-metrics",
        "stage": "NL0",
        "scope": {"story_count": len(gold_records), "selected_story_ids": selected_ids},
        "counts": {
            "stories_selected": len(selected_ids),
            "stories_reviewed": len(candidates),
            "stories_accepted": len(gold_records),
            "claims": claim_count,
            "supporting_evidence_links": evidence_id_count,
            "background_claims": sum(len(row["essential_background"]) for row in gold_records),
            "resonance_claims": sum(row["resonance"] is not None for row in gold_records),
            "abstained_fields": sum(row["era_profile"] is None for row in gold_records) + sum(row["resonance"] is None for row in gold_records),
        },
        "selection_category_counts": {key: selection_categories[key] for key in sorted(selection_categories)},
        "source_layer_counts": {key: source_layers[key] for key in sorted(source_layers)},
        "policy": POLICY,
        "source_hashes": hashes,
    }
    protection = {
        "schema": "nl0-protection-manifest",
        "stage": "NL0",
        "protected_inputs": {path.as_posix(): sha256_file(root, path) for path in PROTECTED_PATHS},
        "write_back": {
            "canonical_shishuo": False,
            "canonical_people": False,
            "canonical_facts": False,
            "hr0": False,
            "hr0_1": False,
            "sc1": False,
            "historical_fact_materialization": False,
        },
    }
    shards = {f"story-sketch/{row['story_id']}.json": display_shard(row) for row in gold_records}
    evidence_ids = sorted({
        str(evidence_id)
        for row in gold_records
        for evidence in row["supporting_evidence"]
        for evidence_id in [evidence["evidence_id"]]
    })
    evidence_shards = {
        f"evidence/{evidence_id}.json": evidence_shard(
            evidence_id,
            sc1_evidence_by_id,
            evidence_refs_by_id(hr0_by_story[story_id]),
            shared_evidence_display,
            shared_source_display,
        )
        for story_id in selected_ids
        for evidence_id in evidence_ids
        if evidence_id in evidence_refs_by_id(hr0_by_story[story_id])
    }
    shards.update(evidence_shards)
    return {
        "candidates": candidate_document,
        "gold": gold_document,
        "metrics": metrics,
        "protection": protection,
        "shards": shards,
        "manifest": {
            "schema": 1,
            "projection": "nl0_story_sketch",
            "stage": "NL0",
            "scope": {
                "story_count": len(gold_records),
                "story_ids": selected_ids,
            },
            "source_hashes": hashes,
            "policies": {
                "canonical_data_write_back": False,
                "candidate_display": False,
                "llm": False,
                "rag": False,
            },
            "shards": {},
        },
    }


def write_documents(root: Path = ROOT) -> None:
    documents = build_documents(root)
    existing_protection = root / PROTECTION_PATH
    if existing_protection.is_file():
        previous = read_json(root, PROTECTION_PATH)
        if previous.get("protected_inputs") != documents["protection"]["protected_inputs"]:
            raise RuntimeError("NL0 protected inputs changed; review the source change before rebuilding")

    for relative, payload_key in (
        (CANDIDATES_PATH, "candidates"),
        (GOLD_PATH, "gold"),
        (METRICS_PATH, "metrics"),
        (PROTECTION_PATH, "protection"),
    ):
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(stable_json(documents[payload_key]), encoding="utf-8")

    shard_root = root / SHARD_ROOT
    evidence_shard_root = root / EVIDENCE_SHARD_ROOT
    shard_root.mkdir(parents=True, exist_ok=True)
    evidence_shard_root.mkdir(parents=True, exist_ok=True)
    expected_files = set(documents["shards"])
    for relative, payload in sorted(documents["shards"].items()):
        path = root / PUBLIC_ROOT / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(stable_json(payload), encoding="utf-8")
    for directory in (shard_root, evidence_shard_root):
        prefix = f"{directory.relative_to(root / PUBLIC_ROOT).as_posix()}/"
        for path in sorted(directory.glob("*.json")):
            if f"{prefix}{path.name}" not in expected_files:
                path.unlink()

    manifest = documents["manifest"]
    for relative in sorted(documents["shards"]):
        path = root / PUBLIC_ROOT / relative
        manifest["shards"][relative] = {
            "sha256": sha256_file(root, PUBLIC_ROOT / relative),
            "bytes": path.stat().st_size,
        }
    manifest_path = root / PUBLIC_MANIFEST_PATH
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(stable_json(manifest), encoding="utf-8")


def main() -> int:
    write_documents(ROOT)
    print(json.dumps({"status": "built", "stories": 7, "output": PUBLIC_ROOT.as_posix()}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
