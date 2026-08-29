"""SFH1 orchestration and deterministic projection assembly."""

from __future__ import annotations

import collections
import concurrent.futures
import statistics
from pathlib import Path
from typing import Any, Mapping

from . import adversarial_review, candidate_retrieval, collective_inference, hard_constraints, identity_judgment, mention_reader, mention_validation, reference_semantics, storage_gate, temporal_semantics
from .analysis import heuristic_audit, mention_regression_audit, old_target_comparison, protected_hashes, random_blind_audit, recalibrated_growth
from .common import MODEL, OUT, RUN_VERSION, StrictStageClient, read_json, stable_hash, text, utc_now, write_json
from .source_packets import build_story_packets, validation_universe


def _checkpoint_path(run_dir: Path, story_id: str) -> Path:
    return run_dir / "checkpoints" / f"{story_id}.json"


def process_story(client: StrictStageClient, packet: Mapping[str, Any], *, include_temporal: bool = True) -> dict[str, Any]:
    raw_mentions = mention_reader.read_mentions(client, packet)
    ledger = mention_validation.validate_mentions(packet, raw_mentions)
    raw_semantics = reference_semantics.read_reference_semantics(client, packet, ledger)
    semantics = reference_semantics.validate_reference_semantics(packet, ledger, raw_semantics)
    candidate_sets = candidate_retrieval.build_candidate_sets(packet, ledger, semantics)
    raw_judgments = identity_judgment.judge_identities(client, packet, ledger, semantics, candidate_sets)
    judgments = identity_judgment.validate_identity_judgments(packet, candidate_sets, raw_judgments)
    constrained = hard_constraints.constrain_candidates(ledger, semantics, candidate_sets, judgments)
    collective = collective_inference.infer_collectively(constrained)
    raw_reviews = adversarial_review.review(client, packet, semantics, constrained)
    reviews = adversarial_review.validate_reviews(packet, constrained, raw_reviews)
    final = storage_gate.finalize_story(ledger, semantics, constrained, collective, reviews)
    temporal = {"story_id": packet.get("story_id"), "records": [], "provider_failure": False}
    if include_temporal:
        temporal = temporal_semantics.validate_temporal(packet, temporal_semantics.read_temporal(client, packet))
    return {
        "story_id": packet.get("story_id"), "packet_hash": packet.get("packet_hash"),
        "mention_result": raw_mentions, "validated_mentions": ledger,
        "reference_semantics": semantics, "candidate_sets": candidate_sets,
        "identity_judgments": judgments, "constrained": constrained,
        "collective": collective, "reviews": reviews, "final": final, "temporal": temporal,
        "candidate_only": True, "canonical_write_back": False,
    }


def _has_provider_failure(result: Mapping[str, Any], *, include_temporal: bool) -> bool:
    keys = ("validated_mentions", "reference_semantics", "identity_judgments", "reviews")
    if any(bool((result.get(key) or {}).get("provider_failure")) for key in keys):
        return True
    return include_temporal and bool((result.get("temporal") or {}).get("provider_failure"))


def run(*, run_id: str, live: bool, include_temporal: bool = True, story_limit: int | None = None, workers: int = 6, retry_failed: bool = False, rebuild_all: bool = False) -> dict[str, Any]:
    universe = validation_universe()
    packet_doc = build_story_packets(universe)
    packets = list(packet_doc.get("packets", []) or [])
    if story_limit is not None:
        packets = packets[:story_limit]
    run_dir = OUT / "live" / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "checkpoints").mkdir(parents=True, exist_ok=True)
    client = StrictStageClient(run_dir, live=live)
    results: list[dict[str, Any] | None] = [None] * len(packets)
    pending: list[tuple[int, Mapping[str, Any], Path]] = []
    for index, packet in enumerate(packets):
        checkpoint = _checkpoint_path(run_dir, text(packet.get("story_id")))
        if checkpoint.is_file():
            existing = read_json(checkpoint, {}) or {}
            if text(existing.get("packet_hash")) != text(packet.get("packet_hash")):
                raise RuntimeError(f"sfh1_checkpoint_packet_drift:{packet.get('story_id')}")
            if not rebuild_all and (not retry_failed or not _has_provider_failure(existing, include_temporal=include_temporal)):
                results[index] = existing
                print(f"SFH1 [{index + 1}/{len(packets)}] replay {packet.get('story_id')}", flush=True)
                continue
            print(f"SFH1 retry provider-failed stages {packet.get('story_id')}", flush=True)
        pending.append((index, packet, checkpoint))

    def work(item: tuple[int, Mapping[str, Any], Path]) -> tuple[int, dict[str, Any]]:
        index, packet, checkpoint = item
        result = process_story(client, packet, include_temporal=include_temporal)
        write_json(checkpoint, result)
        return index, result

    completed = sum(result is not None for result in results)
    with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, workers)) as executor:
        futures = {executor.submit(work, item): item for item in pending}
        for future in concurrent.futures.as_completed(futures):
            index, packet, _ = futures[future]
            result_index, result = future.result()
            results[result_index] = result
            completed += 1
            print(f"SFH1 [{completed}/{len(packets)}] live {packet.get('story_id')}", flush=True)
            write_json(run_dir / "progress.json", {"completed": completed, "total": len(packets), "last_story_id": packet.get("story_id"), "updated_at": utc_now()})
    if any(result is None for result in results):
        raise RuntimeError("sfh1_incomplete_story_results")
    return assemble(run_id=run_id, universe=universe, packet_doc=packet_doc, results=[result for result in results if result is not None], client=client, include_temporal=include_temporal)


def replay(*, run_id: str, include_temporal: bool = True) -> dict[str, Any]:
    universe = validation_universe()
    packet_doc = build_story_packets(universe)
    run_dir = OUT / "live" / run_id
    results = []
    for packet in packet_doc.get("packets", []) or []:
        checkpoint = _checkpoint_path(run_dir, text(packet.get("story_id")))
        if not checkpoint.is_file():
            raise RuntimeError(f"sfh1_missing_checkpoint:{packet.get('story_id')}")
        result = read_json(checkpoint, {}) or {}
        if text(result.get("packet_hash")) != text(packet.get("packet_hash")):
            raise RuntimeError(f"sfh1_checkpoint_packet_drift:{packet.get('story_id')}")
        results.append(result)
    client = StrictStageClient(run_dir, live=False)
    transport = read_json(run_dir / "transport.json", []) or []
    client.records = list(transport)
    return assemble(run_id=run_id, universe=universe, packet_doc=packet_doc, results=results, client=client, include_temporal=include_temporal)


def _stage_document(schema: str, results: list[Mapping[str, Any]], key: str, child: str | None = None) -> dict[str, Any]:
    records: list[Any] = []
    rejected: list[Any] = []
    for result in results:
        value = result.get(key) if isinstance(result, Mapping) else None
        if child and isinstance(value, Mapping):
            value = value.get(child)
        if isinstance(value, list):
            records.extend(value)
        elif value is not None:
            records.append(value)
        parent = result.get(key) if isinstance(result, Mapping) else None
        if isinstance(parent, Mapping):
            rejected.extend(parent.get("rejected", []) or [])
    return {"schema": schema, "records": records, "rejected": rejected, "candidate_only": True, "canonical_write_back": False}


def assemble(*, run_id: str, universe: Mapping[str, Any], packet_doc: Mapping[str, Any], results: list[Mapping[str, Any]], client: StrictStageClient, include_temporal: bool) -> dict[str, Any]:
    run_dir = OUT / "live" / run_id
    packets = list(packet_doc.get("packets", []) or [])
    mentions = [row for result in results for row in (result.get("validated_mentions") or {}).get("valid_mentions", []) or []]
    mention_rejects = [row for result in results for row in (result.get("validated_mentions") or {}).get("rejected_mentions", []) or []]
    semantics = [row for result in results for row in (result.get("reference_semantics") or {}).get("records", []) or []]
    candidate_sets = [row for result in results for row in (result.get("candidate_sets") or {}).get("records", []) or []]
    judgments = [row for result in results for row in (result.get("identity_judgments") or {}).get("judgments", []) or []]
    constrained = [row for result in results for row in (result.get("constrained") or {}).get("records", []) or []]
    final = [row for result in results for row in (result.get("final") or {}).get("records", []) or []]
    temporal = [row for result in results for row in (result.get("temporal") or {}).get("assertions", []) or []]
    relation_projection = storage_gate.project_relations([result.get("reference_semantics") or {} for result in results], final)
    mention_provider_failed = {text(result.get("story_id")) for result in results if bool((result.get("validated_mentions") or {}).get("provider_failure"))}
    regression = mention_regression_audit(mentions, final, mention_provider_failed)
    comparison = old_target_comparison(mentions)
    recalibrated = recalibrated_growth(final, relation_projection)
    comparison_counts = comparison.get("counts") or {}
    recalibrated["old_candidate_person_artifacts_removed"] = sum(int(comparison_counts.get(key) or 0) for key in ("boundary_too_long", "boundary_too_short", "missed_multiple_mentions", "non_person"))
    blind = random_blind_audit(packets, mentions, semantics, final, relation_projection.get("records", []))
    states = collections.Counter(text(row.get("final_state")) for row in final)
    failure = collections.Counter(text(row.get("failure_stage")) for row in final if text(row.get("failure_stage")))
    entity_kinds = collections.Counter(text(row.get("entity_kind")) for row in mentions)
    person_mentions = sum(entity_kinds[kind] for kind in ("person", "collective_person_reference"))
    anonymous = sum(text(row.get("reference_form")) in {"pronoun_reference", "descriptive_person_reference"} for row in mentions)
    unique_candidates = {text(row.get("candidate_person_id")) for row in final if text(row.get("candidate_person_id"))}
    unique_existing = {text(row.get("person_id")) for row in final if text(row.get("person_id"))}
    stage_metrics = client.metrics()
    pending_by_stage = {
        key: sum(bool((result.get(key) or {}).get("provider_failure")) for result in results)
        for key in ("validated_mentions", "reference_semantics", "identity_judgments", "reviews", "temporal")
    }
    stage_metrics["pending_stage_story_counts"] = pending_by_stage
    stage_metrics["live_incomplete"] = any(pending_by_stage.values())
    metrics = {
        "schema": "sfh1-metrics-v1", "run_id": run_id, "model": MODEL,
        "scope": {"story_count": len(packets), "production_story_count": universe.get("production_story_count"), "wave_a_story_count": universe.get("wave_a_story_count"), "wave_b_story_count": universe.get("wave_b_story_count")},
        "mentions": {"validated": len(mentions), "rejected": len(mention_rejects), "entity_kinds": dict(sorted(entity_kinds.items())), "person_mentions": person_mentions, "mentions_per_story": round(len(mentions) / len(packets), 6) if packets else 0, "person_mentions_per_story": round(person_mentions / len(packets), 6) if packets else 0, "anonymous_person_references_per_story": round(anonymous / len(packets), 6) if packets else 0},
        "identity": {"final_states": dict(sorted(states.items())), "failure_attribution": dict(sorted(failure.items())), "existing_persons_recovered": len(unique_existing), "candidate_person_count": len(unique_candidates)},
        "relations": {"validated": len(relation_projection.get("records", []) or []), "rejected": len(relation_projection.get("rejected", []) or []), "complete_endpoints": sum(row.get("endpoint_state") == "complete" for row in relation_projection.get("records", []) or [])},
        "temporal": {"validated": len(temporal), "provider_failures": sum(bool((result.get("temporal") or {}).get("provider_failure")) for result in results)},
        "old_new": {key: comparison.get(key) for key in ("old_target_count", "old_target_precision", "old_boundary_error_rate", "old_non_person_contamination_rate", "counts")},
        "safety": {"known_boundary_failures": regression.get("known_boundary_failures"), "pending_provider_controls": regression.get("pending_provider_controls"), "forbidden_stable_resolutions": regression.get("forbidden_stable_resolution_count"), "candidate_only": all(row.get("candidate_only") is True for row in final), "canonical_write_back": any(row.get("canonical_write_back") is True for row in final)},
        "provider": stage_metrics, "candidate_only": True, "canonical_write_back": False,
    }
    artifacts = {
        "story-packets.json": dict(packet_doc),
        "mention-results.json": {"schema": "sfh1-mention-results-v1", "records": [{"story_id": result.get("story_id"), "payload": result.get("mention_result")} for result in results], "candidate_only": True, "canonical_write_back": False},
        "validated-mentions.json": {"schema": "sfh1-validated-mention-ledger-v1", "records": mentions, "rejected": mention_rejects, "candidate_only": True, "canonical_write_back": False},
        "reference-semantics.json": {"schema": "sfh1-reference-semantics-ledger-v1", "records": semantics, "candidate_only": True, "canonical_write_back": False},
        "candidate-sets.json": {"schema": "sfh1-candidate-sets-v1", "records": candidate_sets, "candidate_only": True, "canonical_write_back": False},
        "identity-judgments.json": {"schema": "sfh1-identity-judgments-v1", "records": judgments, "candidate_only": True, "canonical_write_back": False},
        "constrained-decisions.json": {"schema": "sfh1-constrained-decisions-v1", "records": constrained, "candidate_only": True, "canonical_write_back": False},
        "final-decisions.json": {"schema": "sfh1-final-decisions-v1", "records": final, "candidate_only": True, "canonical_write_back": False},
        "relation-assertions.json": relation_projection,
        "temporal-semantics.json": {"schema": "sfh1-temporal-semantics-v1", "records": temporal, "candidate_only": True, "canonical_write_back": False},
        "mention-audit.json": {"schema": "sfh1-mention-audit-v1", "known_regressions": regression, "old_new_target_comparison": comparison, "random_blind_audit_ref": "data/generated/sfh1/random-blind-audit.json", "candidate_only": True, "canonical_write_back": False},
        "random-blind-audit.json": blind,
        "hge1-recalibrated-growth-series.json": recalibrated,
        "python-semantic-heuristic-audit.json": heuristic_audit(),
        "metrics.json": metrics,
    }
    for name, value in artifacts.items():
        write_json(OUT / name, value)
    write_json(run_dir / "transport.json", client.records)
    manifest = {
        "schema": "sfh1-manifest-v1", "run_version": RUN_VERSION, "run_id": run_id, "model": MODEL,
        "universe_hash": universe.get("universe_hash"), "story_count": len(packets), "include_temporal": include_temporal,
        "artifact_hashes": {name: stable_hash(value) for name, value in sorted(artifacts.items())},
        "protected_hashes": protected_hashes(), "candidate_only": True, "canonical_write_back": False,
    }
    write_json(OUT / "manifest.json", manifest)
    write_json(run_dir / "manifest.json", manifest)
    return {"manifest": manifest, "metrics": metrics, "regression": regression, "recalibrated": recalibrated, "artifacts": artifacts}
