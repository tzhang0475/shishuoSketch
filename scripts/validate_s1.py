#!/usr/bin/env python3
"""Validate S1 registration, cache/projections, and protected-layer boundaries."""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys

from s1_jianshu_common import (
    ALIGNMENT_PATH,
    CORPUS_INDEX_PATH,
    GLYPH_AUDIT_PATH,
    REGISTRATION_PATH,
    STRUCTURE_AUDIT_PATH,
    X1_SELECTION_PATH,
    X1_2P_PATHS,
    CACHE_ROOT,
    discover_payloads,
    load_story_records,
    protected_s1_input_hashes,
    primary_witness_snapshot,
    read_json,
    relative_path,
    sha256_file,
    x1_selection_by_story,
)

try:
    from scripts import sfh2r_contract
except ImportError:  # direct execution from scripts/
    import sfh2r_contract


ROOT = Path(__file__).resolve().parents[1]
BACKLOG_PATH = Path("data/derived/s1-jianshu-backlog-reresolution.json")
MATERIALIZATION_PATH = Path("data/derived/s1-jianshu-materialization-manifest.json")
READINESS_PATH = Path("data/derived/s1-jianshu-candidate-punctuation-readiness.json")
GATE_PATH = Path("data/derived/s1-jianshu-punctuation-gate-audit.json")
ALIAS_PATH = Path("data/derived/s1-jianshu-alias-candidates.json")
ASSERTION_PATH = Path("data/derived/s1-jianshu-historical-assertions.json")
CITATION_PATH = Path("data/derived/s1-jianshu-source-citations.json")
X1_2A_MATERIALIZATION_PATH = Path("data/derived/x1-2a-materialization-manifest.json")
X1_2A_CANONICAL_PATH = Path("data/derived/x1-2a-canonical-facts.json")


def json_read(path: Path) -> dict:
    return read_json(path)


def validate() -> list[str]:
    errors: list[str] = []
    registration = json_read(REGISTRATION_PATH)
    payloads = discover_payloads()
    by_id = {str(row["source_id"]): row for row in registration.get("payloads", [])}
    expected_ids = {"shishuo-jianshu-yujiaxi-local-epub", "shishuo-jianshu-yujiaxi-local-pdf"}
    if set(by_id) != expected_ids:
        errors.append(f"registration source IDs are {sorted(by_id)}, expected {sorted(expected_ids)}")
    for kind, path in payloads.items():
        source_id = "shishuo-jianshu-yujiaxi-local-epub" if kind == "epub" else "shishuo-jianshu-yujiaxi-local-pdf"
        row = by_id.get(source_id, {})
        actual_hash = sha256_file(Path(relative_path(path)))
        if row.get("sha256") != actual_hash:
            errors.append(f"{kind} SHA-256 does not match registration")
        if row.get("byte_size") != path.stat().st_size:
            errors.append(f"{kind} byte size does not match registration")
        if row.get("local_path") != relative_path(path):
            errors.append(f"{kind} local path does not match registration")
        lock_path = path.parent / "manifest.lock.json"
        if not lock_path.exists():
            errors.append(f"missing lock manifest for {kind}")
        else:
            lock = json.loads(lock_path.read_text(encoding="utf-8"))
            if lock.get("payload", {}).get("sha256") != actual_hash:
                errors.append(f"{kind} lock SHA-256 does not match payload")
    try:
        tracked = subprocess.run(["git", "ls-files", "sources/downloads/shishuo"], capture_output=True, text=True, check=False).stdout.splitlines()
        if any(path.suffix.lower() in {".epub", ".pdf"} for path in (ROOT / "sources/downloads/shishuo").rglob("*")) and any(line.lower().endswith((".epub", ".pdf")) for line in tracked):
            errors.append("Jianshu binary payload appears tracked")
        all_tracked = subprocess.run(["git", "ls-files"], capture_output=True, text=True, check=False).stdout.splitlines()
        forbidden_cache_names = {"story-records.jsonl", "citation-blocks.jsonl", "pdf-page-index.jsonl"}
        if any(line.startswith(".cache/shishuo-reference/jianshu/") for line in all_tracked):
            errors.append("full Jianshu cache appears tracked")
        if any(Path(line).name in forbidden_cache_names for line in all_tracked):
            errors.append("full Jianshu extraction cache file appears tracked")
    except OSError as exc:
        errors.append(f"could not inspect Git-tracked source payloads: {exc}")

    structure = json_read(STRUCTURE_AUDIT_PATH)
    if structure.get("chapters_detected") != 36 or structure.get("chapter_count_expected") != 36:
        errors.append("Jianshu structure does not report all 36 categories")
    if structure.get("story_entries_detected") != 1130:
        errors.append(f"Jianshu Story entry count is {structure.get('story_entries_detected')}, expected 1130")
    if structure.get("block_counts", {}).get("base_text", 0) != 1130:
        errors.append("Jianshu base-text block count does not match Story count")
    if structure.get("block_counts", {}).get("jianshu_note", 0) <= 0 or structure.get("block_counts", {}).get("collation_note", 0) <= 0:
        errors.append("Jianshu note layers are not represented")
    cache_metadata = json_read(CACHE_ROOT / "parse-metadata.json")
    if cache_metadata.get("epub_sha256") != by_id.get("shishuo-jianshu-yujiaxi-local-epub", {}).get("sha256"):
        errors.append("cache EPUB hash does not match registration")
    if cache_metadata.get("pdf_sha256") != by_id.get("shishuo-jianshu-yujiaxi-local-pdf", {}).get("sha256"):
        errors.append("cache PDF hash does not match registration")
    if len(load_story_records()) != 1130:
        errors.append("cache Story record count does not match structure audit")

    alignment = json_read(ALIGNMENT_PATH)
    selection_ids = set(x1_selection_by_story())
    alignment_ids = {str(row["story_id"]) for row in alignment.get("records", [])}
    if len(alignment.get("records", [])) != 163:
        errors.append("alignment scope is not 143 production plus 20 frozen X1.1 Stories")
    if not selection_ids <= alignment_ids:
        errors.append("alignment is missing a frozen X1.1 Story")
    if alignment.get("scope", {}).get("new_story_selection_performed"):
        errors.append("alignment claims a new Story selection")

    backlog = json_read(BACKLOG_PATH)
    counts = backlog.get("counts", {})
    for key, expected in (("stories_total", 20), ("facts_total", 58), ("identities_total", 3)):
        if counts.get(key) != expected:
            errors.append(f"S1 backlog {key}={counts.get(key)!r}, expected {expected}")
    if {row.get("story_id") for row in backlog.get("stories", [])} != selection_ids:
        errors.append("S1 backlog Story scope differs from frozen X1.1 selection")
    if any(row.get("selection_epoch") != "X1.1" for row in backlog.get("stories", [])):
        errors.append("S1 backlog lost X1.1 selection provenance")
    if counts.get("facts_accepted") != 0 or counts.get("identities_new_persons") != 0:
        errors.append("S1 backlog reports unauthorized fact or Person acceptance")
    if not all(row.get("candidate_assertions_are_not_canonical_facts", True) for row in [backlog.get("policy", {})]):
        errors.append("S1 candidate/canonical policy is missing")

    materialization = json_read(MATERIALIZATION_PATH)
    if any(materialization.get(key) for key in ("canonical_story_additions", "canonical_person_additions", "canonical_fact_additions", "canonical_entity_additions")):
        errors.append("S1 materialization manifest contains additions without an accepted release review")
    if materialization.get("protected_x1_2a_materialization_sha256") != sha256_file(X1_2A_MATERIALIZATION_PATH):
        errors.append("X1.2A materialization manifest hash is not protected")
    if backlog.get("existing_x1_2a_extension", {}).get("canonical_fact_index_sha256") != sha256_file(X1_2A_CANONICAL_PATH):
        errors.append("X1.2A canonical extension hash is not protected")

    registered_primary = registration.get("primary_shishuo_witness", {})
    current_primary = primary_witness_snapshot()
    if registered_primary != current_primary:
        errors.append("primary Shishuo witness snapshot changed")
    if current_primary.get("status") != "verified":
        errors.append(f"primary Shishuo witness is not verified: {current_primary.get('status')}")
    if not registration.get("primary_shishuo_witness_unchanged"):
        errors.append("registration does not attest a verified unchanged primary Shishuo witness")

    readiness = json_read(READINESS_PATH)
    if readiness.get("counts", {}).get("candidate_records") != len(read_json(Path("data/derived/x1-1-candidate-pool.json")).get("records", [])):
        errors.append("S1 candidate punctuation readiness does not cover the X1.1 pool")
    gate = json_read(GATE_PATH)
    if gate.get("classification", {}).get("result") != "intentional_two_tier_policy_resolved_by_s1_source_policy":
        errors.append("S1 punctuation gate classification is not explicit")

    for path in (ALIAS_PATH, ASSERTION_PATH, CITATION_PATH):
        if not json_read(path).get("records"):
            errors.append(f"candidate extraction artifact is empty: {path}")
    glyph = json_read(GLYPH_AUDIT_PATH)
    if glyph.get("issue_count") != len(glyph.get("issues", [])):
        errors.append("glyph audit issue count is inconsistent")

    protected = registration.get("protected_input_hashes", {})
    current_protected = protected_s1_input_hashes()
    for path, expected_hash in protected.items():
        if current_protected.get(path) != expected_hash:
            if not sfh2r_contract.path_hash_is_current_or_authorized(
                str(path), str(expected_hash), current_protected.get(path)
            ):
                errors.append(f"protected upstream artifact changed: {path}")
    for path in X1_2P_PATHS:
        if path.as_posix() not in protected:
            errors.append(f"X1.2P artifact missing from S1 protection set: {path}")
    if not Path("sources/registry/shishuo.yaml").read_text(encoding="utf-8").count("shishuo-jianshu-yujiaxi") >= 3:
        errors.append("local and external Jianshu registry records are incomplete")
    config_text = Path("config/sources.yaml").read_text(encoding="utf-8")
    if "scholarly_reference_machine_local" not in config_text or "scholarly_reference_visual_local" not in config_text:
        errors.append("local Jianshu machine/visual config paths are missing")
    # S1 is not allowed to introduce later milestone outputs.
    for pattern in ("data/derived/x1-2b-*", "data/derived/hg1.1-*", "data/derived/ml1.1-*"):
        if list(ROOT.glob(pattern)):
            errors.append(f"later-milestone artifacts unexpectedly present: {pattern}")
    return errors


def main() -> int:
    errors = validate()
    if errors:
        print("S1 validation failed:")
        for error in errors:
            print(f"- {error}")
        return 1
    print("S1 validation passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
