#!/usr/bin/env python3
"""HDA1: blind, candidate-only audit of existing identity claims.

The HDA1 input is deliberately downstream of the frozen HDB2-F projection but
the audit itself does not write that projection.  Claims, blind packets, and
provider results are separate artifacts so an audit cannot silently become an
identity repair.  The small deterministic helpers in this module are also
used by the HDA1 validator and by tests without making a network request.
"""

from __future__ import annotations

import argparse
import collections
import datetime as dt
import hashlib
import json
import os
import re
import statistics
import sys
import time
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import hng2_schema_controller as controller  # noqa: E402
import sfh2r_contract  # noqa: E402
from smoke_deepseek import call_deepseek  # noqa: E402


OUT = ROOT / "data/generated/hda1"
MODEL = "deepseek-v4-flash"
RUN_VERSION = "hda1-existing-identity-audit-v1"
PROMPT_VERSION = "hda1-blind-identity-verification-v1"
SCHEMA = "hda1-identity-audit-v1"
VERDICTS = {"support", "contradict", "ambiguous", "insufficient_evidence"}
REASON_TYPES = {
    "explicit_identity",
    "courtesy_name_assertion",
    "title_holder",
    "local_coreference",
    "comparison_distinctness",
    "different_named_person",
    "surface_only_match",
    "insufficient_context",
    "other",
}


def read_json(path: Path, default: Any = None) -> Any:
    if not path.is_file():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def stable_hash(value: Any) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _text(value: Any) -> str:
    return str(value or "").strip()


def _story_rows() -> list[dict[str, Any]]:
    document = read_json(ROOT / "data/derived/ds2-1a-shishuo-search-corpus.json", {}) or {}
    return [dict(row) for row in document.get("records", []) if isinstance(row, Mapping)]


def story_index() -> dict[str, dict[str, Any]]:
    return {_text(row.get("story_id")): row for row in _story_rows() if _text(row.get("story_id"))}


def _story_id_from_ref(ref: str) -> str:
    value = _text(ref)
    match = re.search(r"(?:hng2c1|hdb2)-shishuo-(.+?)-(?:liu-annotation-[^-]+|main)$", value)
    return match.group(1) if match else ""


def _annotation_id_from_ref(ref: str) -> str:
    match = re.search(r"-liu-(annotation-[^-]+)$", _text(ref))
    return match.group(1) if match else ""


def _source_unit(ref: str, stories: Mapping[str, Mapping[str, Any]]) -> dict[str, Any] | None:
    """Resolve a frozen HNG/HDB source ref to the same visible corpus text."""
    value = _text(ref)
    story_id = _story_id_from_ref(value)
    row = stories.get(story_id)
    if not row:
        return None
    if value.endswith("-main"):
        text = _text(row.get("main_text"))
        return {
            "source_ref": value,
            "source_work": "世說正文",
            "source_layer": "main_text",
            "evidence_text": text,
            "locator": {"story_id": story_id, "chapter": row.get("chapter_heading")},
            "source_path": row.get("source_path"),
            "source_sha256": row.get("source_sha256"),
        } if text else None
    annotation_id = _annotation_id_from_ref(value)
    for annotation in row.get("liu_annotations", []) or []:
        if annotation_id and _text(annotation.get("annotation_id")) != annotation_id:
            continue
        text = _text(annotation.get("text"))
        if text:
            return {
                "source_ref": value,
                "source_work": "劉注",
                "source_layer": "liu_annotation",
                "evidence_text": text,
                "locator": {"story_id": story_id, "annotation_id": annotation.get("annotation_id")},
                "source_path": row.get("source_path"),
                "source_sha256": row.get("source_sha256"),
            }
    return None


def _window(text: str, surface: str, span: str, radius: int = 480) -> str:
    needle = span or surface
    position = text.find(needle) if needle else -1
    if position < 0 and surface:
        position = text.find(surface)
        needle = surface
    if position < 0:
        return text[: max(1000, min(len(text), radius * 2))]
    return text[max(0, position - radius): min(len(text), position + len(needle) + radius)]


def _claim_id(material: Mapping[str, Any]) -> str:
    return f"hda1-claim-{stable_hash(dict(material))[:24]}"


def _claim(
    *,
    person_id: str,
    canonical_name: str,
    surface: str,
    occurrence_id: str,
    story_id: str,
    evidence_ref: str,
    exact_span: str,
    source_section: str,
    claim_type: str,
    identity_status: str,
    identity_basis: str,
    source_origin: str,
    source_hash: str | None = None,
    source_detail: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    material = {
        "person_id": person_id,
        "surface": surface,
        "occurrence_id": occurrence_id,
        "story_id": story_id,
        "evidence_ref": evidence_ref,
        "exact_span": exact_span,
        "claim_type": claim_type,
        "source_origin": source_origin,
    }
    return {
        "claim_id": _claim_id(material),
        **material,
        "canonical_name": canonical_name,
        "source_section": source_section,
        "identity_status": identity_status,
        "identity_basis": identity_basis,
        "source_origin": source_origin,
        "source_hash": source_hash,
        "source_detail": dict(source_detail or {}),
    }


def _hdb2_claims(stories: Mapping[str, Mapping[str, Any]], people: Mapping[str, Mapping[str, Any]]) -> list[dict[str, Any]]:
    document = read_json(ROOT / "data/derived/hdb2-f-identity-claim-integrity-audit.json", {}) or {}
    claims: list[dict[str, Any]] = []
    for row in document.get("audited_identity_claims", []) or []:
        if not isinstance(row, Mapping):
            continue
        pid = _text(row.get("target_person_id"))
        if not pid:
            continue
        person = people.get(pid, {})
        ref = _text(row.get("evidence_ref"))
        claims.append(_claim(
            person_id=pid,
            canonical_name=_text(person.get("canonical_name")) or pid,
            surface=_text(row.get("surface")),
            occurrence_id=_text(row.get("occurrence_id")),
            story_id=_text(row.get("story_id")) or _story_id_from_ref(ref),
            evidence_ref=ref,
            exact_span=_text(row.get("exact_span")) or _text(row.get("surface")),
            source_section="liu_annotation" if "-liu-" in ref else "main_text",
            claim_type="hdb2_f_identity_claim",
            identity_status=_text(row.get("identity_status")),
            identity_basis=_text(row.get("identity_basis")),
            source_origin="hdb2_f_identity_claim_integrity_audit",
            source_hash=_text(row.get("source_hash")) or None,
            source_detail={"profile_form_retained": row.get("profile_form_retained"), "entity_kind": row.get("entity_kind")},
        ))
    return claims


def _catalogue_claims(people: Mapping[str, Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Represent each registered alias once, using its first source witness.

    Alias records can have hundreds of repeated observations.  HDA1 audits
    the claim represented by the registry row and keeps the complete source
    evidence count in source_detail; it does not turn repetition into an
    artificial LLM workload.
    """
    aliases = read_json(ROOT / "data/aliases.json", {}) or {}
    result: list[dict[str, Any]] = []
    for alias in aliases.get("aliases", []) or []:
        if not isinstance(alias, Mapping):
            continue
        pids = [_text(x) for x in alias.get("resolved_person_ids", []) or [] if _text(x) in people]
        if not pids:
            pids = [_text(x) for x in alias.get("person_ids", []) or [] if _text(x) in people]
        if not pids:
            continue
        evidence = [x for x in alias.get("source_evidence", []) or [] if isinstance(x, Mapping)]
        witness = dict(evidence[0]) if evidence else {}
        ref = _text(witness.get("mention_id")) or f"alias:{_text(alias.get('alias_id'))}"
        story_id = _text(witness.get("source_id"))
        surface = _text(alias.get("surface"))
        snippet = _text(witness.get("evidence_snippet"))
        for pid in sorted(set(pids)):
            result.append(_claim(
                person_id=pid,
                canonical_name=_text(people[pid].get("canonical_name")) or pid,
                surface=surface,
                occurrence_id=ref,
                story_id=story_id,
                evidence_ref=ref,
                exact_span=surface if surface and surface in snippet else "",
                source_section=_text(witness.get("section")) or "registered_alias",
                claim_type="catalogue_alias",
                identity_status=_text(alias.get("status")),
                identity_basis="catalogue_exact_match" if _text(alias.get("status")) == "resolved" else "catalogue_registry",
                source_origin="aliases_registry",
                source_hash=_text((witness.get("provenance") or {}).get("source_sha256")) or None,
                source_detail={"alias_id": alias.get("alias_id"), "alias_type": alias.get("alias_type"), "observed_count": alias.get("observed_count"), "source_evidence_count": len(evidence), "evidence_snippet": snippet},
            ))
    return result


def _people_source_claims(people: Mapping[str, Mapping[str, Any]]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for pid, person in people.items():
        for evidence in person.get("source_evidence", []) or []:
            if not isinstance(evidence, Mapping):
                continue
            surface = _text(evidence.get("surface"))
            snippet = _text(evidence.get("snippet"))
            source_id = _text(evidence.get("source_id"))
            mention_id = _text(evidence.get("mention_id"))
            result.append(_claim(
                person_id=pid,
                canonical_name=_text(person.get("canonical_name")) or pid,
                surface=surface,
                occurrence_id=mention_id,
                story_id=source_id,
                evidence_ref=mention_id or f"people:{pid}:{source_id}",
                exact_span=surface if surface and surface in snippet else "",
                source_section="liu_annotation" if "annotation" in mention_id else "main_text",
                claim_type="person_catalogue_source_evidence",
                identity_status=_text(evidence.get("confidence")),
                identity_basis="catalogue_source_evidence",
                source_origin="people_registry",
                source_hash=_text((evidence.get("provenance") or {}).get("source_sha256")) or None,
                source_detail={"source": evidence.get("source"), "snippet": snippet},
            ))
    return result


def build_claims() -> dict[str, Any]:
    people_doc = read_json(ROOT / "data/people.json", {}) or {}
    people = {_text(row.get("person_id")): dict(row) for row in people_doc.get("people", []) or [] if _text(row.get("person_id"))}
    stories = story_index()
    all_claims = [*_hdb2_claims(stories, people), *_catalogue_claims(people), *_people_source_claims(people)]
    unique: dict[tuple[str, ...], dict[str, Any]] = {}
    for claim in all_claims:
        key = tuple(_text(claim.get(k)) for k in ("person_id", "surface", "occurrence_id", "evidence_ref", "exact_span", "claim_type"))
        unique[key] = claim
    claims = sorted(unique.values(), key=lambda row: (_text(row.get("claim_id")), _text(row.get("person_id"))))
    return {
        "schema": SCHEMA,
        "run_version": RUN_VERSION,
        "prompt_version": PROMPT_VERSION,
        "model": MODEL,
        "claim_count": len(claims),
        "claims": claims,
        "source_scope": ["HDB2-F identity claim integrity audit", "registered aliases", "Person source evidence"],
        "candidate_only": True,
        "canonical_write_back": False,
    }


def _evidence_item(claim: Mapping[str, Any], stories: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    ref = _text(claim.get("evidence_ref"))
    unit = _source_unit(ref, stories)
    detail = claim.get("source_detail") if isinstance(claim.get("source_detail"), Mapping) else {}
    if unit:
        text = _text(unit.get("evidence_text"))
        span = _text(claim.get("exact_span"))
        return {
            "evidence_id": f"ev-{stable_hash({'claim': claim.get('claim_id'), 'ref': ref})[:20]}",
            "source_ref": ref,
            "source_work": unit.get("source_work"),
            "source_section": unit.get("source_layer"),
            "evidence_text": _window(text, _text(claim.get("surface")), span),
            "exact_span": span,
            # A witness may preserve a visual/name span with an intervening
            # line break (for example 士\n龍).  Keep the original claim and
            # record that it is not byte-contiguous; never repair it here.
            "exact_span_grounded": bool(span and span in text),
            "locator": unit.get("locator", {}),
            "source_hash": unit.get("source_sha256"),
        }
    snippet = _text(detail.get("evidence_snippet")) or _text(detail.get("snippet"))
    return {
        "evidence_id": f"ev-{stable_hash({'claim': claim.get('claim_id'), 'ref': ref})[:20]}",
        "source_ref": ref,
        "source_work": "registered source evidence",
        "source_section": _text(claim.get("source_section")),
        "evidence_text": snippet,
        "exact_span": _text(claim.get("exact_span")),
        "exact_span_grounded": bool(_text(claim.get("exact_span")) and _text(claim.get("exact_span")) in snippet),
        "locator": {"story_id": claim.get("story_id"), "occurrence_id": claim.get("occurrence_id")},
        "source_hash": claim.get("source_hash"),
    }


def _relevant_annotations(story_id: str, surface: str, stories: Mapping[str, Mapping[str, Any]]) -> list[dict[str, Any]]:
    row = stories.get(story_id, {})
    result = []
    for ann in row.get("liu_annotations", []) or []:
        text = _text(ann.get("text"))
        if surface and surface not in text:
            continue
        result.append({
            "annotation_id": ann.get("annotation_id"),
            "text": text[:1800],
            "source_ref": f"hda1-shishuo-liu-{story_id}-{ann.get('annotation_id')}",
        })
    return result[:4]


def build_audit_packets(claim_document: Mapping[str, Any] | None = None) -> dict[str, Any]:
    claims = list((claim_document or build_claims()).get("claims", []) or [])
    stories = story_index()
    packets: list[dict[str, Any]] = []
    for claim in claims:
        evidence = _evidence_item(claim, stories)
        story_id = _text(claim.get("story_id"))
        main_text = _text((stories.get(story_id) or {}).get("main_text"))
        packets.append({
            "claim_id": claim.get("claim_id"),
            "person_id": claim.get("person_id"),
            "canonical_name": claim.get("canonical_name"),
            "target_surface": claim.get("surface"),
            "occurrence_id": claim.get("occurrence_id"),
            "story_id": story_id,
            "claim_type": claim.get("claim_type"),
            "evidence_items": [evidence] if evidence else [],
            "short_story_context": _window(main_text, _text(claim.get("surface")), _text(claim.get("exact_span"))) if main_text else "",
            "relevant_liu_annotation": _relevant_annotations(story_id, _text(claim.get("surface")), stories),
            "source_evidence_ids": [evidence.get("evidence_id")] if evidence else [],
        })
    packets.sort(key=lambda row: _text(row.get("claim_id")))
    return {
        "schema": "hda1-blind-audit-packets-v1",
        "claim_count": len(packets),
        "packets": packets,
        "candidate_only": True,
        "canonical_write_back": False,
    }


def audit_tool() -> dict[str, Any]:
    return {
        "type": "function",
        "function": {
            "name": "submit_identity_audit_verdict",
            "description": "Return only a grounded verification verdict for the supplied identity claim.",
            "strict": True,
            "parameters": {
                "type": "object",
                "properties": {
                    "verdict": {"type": "string", "enum": sorted(VERDICTS)},
                    "supporting_evidence_ids": {"type": "array", "items": {"type": "string"}},
                    "contradicting_evidence_ids": {"type": "array", "items": {"type": "string"}},
                    "reason_types": {"type": "array", "items": {"type": "string", "enum": sorted(REASON_TYPES)}},
                    # DeepSeek's strict JSON-schema implementation accepts a
                    # standards-compliant anyOf more reliably than the
                    # shorthand union form.  Keep null a real JSON null so a
                    # missing suggestion cannot be mistaken for a surface.
                    "suggested_identity_surface": {"anyOf": [{"type": "string"}, {"type": "null"}]},
                    "explanation": {"type": "string"},
                },
                "required": ["verdict", "supporting_evidence_ids", "contradicting_evidence_ids", "reason_types", "suggested_identity_surface", "explanation"],
                "additionalProperties": False,
            },
        },
    }


def audit_prompt(packet: Mapping[str, Any]) -> dict[str, Any]:
    # Deliberately do not copy status, basis, accepted flags, or prior model
    # output from the claim into the blind packet.
    return {
        "task": "independent historical identity claim verification",
        "instruction": "Does the supplied evidence support that target_surface refers to the claimed Person? Use only supplied evidence IDs. Do not infer from a name string alone. A comparison, co-occurrence, title context, or unrelated named person is not identity support.",
        "claim": {
            "person_id": packet.get("person_id"),
            "canonical_name": packet.get("canonical_name"),
            "target_surface": packet.get("target_surface"),
            "occurrence_id": packet.get("occurrence_id"),
            "story_id": packet.get("story_id"),
            "claim_type": packet.get("claim_type"),
        },
        "short_story_context": packet.get("short_story_context", ""),
        "relevant_liu_annotation": packet.get("relevant_liu_annotation", []),
        "evidence_items": packet.get("evidence_items", []),
    }


def validate_audit_payload(payload: Any, packet: Mapping[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    if not isinstance(payload, Mapping):
        return {"valid": False, "errors": ["payload_not_object"], "payload": None}
    expected = {"verdict", "supporting_evidence_ids", "contradicting_evidence_ids", "reason_types", "suggested_identity_surface", "explanation"}
    if set(payload) != expected:
        errors.append("field_set_mismatch")
    if payload.get("verdict") not in VERDICTS:
        errors.append("invalid_verdict")
    evidence_ids = set(_text(x) for x in packet.get("source_evidence_ids", []) or [])
    for field in ("supporting_evidence_ids", "contradicting_evidence_ids"):
        value = payload.get(field)
        if not isinstance(value, list) or any(not isinstance(x, str) or not x for x in value):
            errors.append(f"{field}_invalid")
        elif not set(value).issubset(evidence_ids):
            errors.append(f"{field}_unknown_evidence_id")
    reasons = payload.get("reason_types")
    if not isinstance(reasons, list) or any(x not in REASON_TYPES for x in reasons):
        errors.append("reason_types_invalid")
    surface = payload.get("suggested_identity_surface")
    if surface is not None and (not isinstance(surface, str) or not surface.strip()):
        errors.append("suggested_surface_invalid")
    if not isinstance(payload.get("explanation"), str) or len(payload.get("explanation", "")) > 800:
        errors.append("explanation_invalid")
    if payload.get("verdict") == "support" and not payload.get("supporting_evidence_ids"):
        errors.append("support_without_evidence")
    if payload.get("verdict") == "contradict" and not payload.get("contradicting_evidence_ids"):
        errors.append("contradict_without_evidence")
    return {"valid": not errors, "errors": errors, "payload": dict(payload) if not errors else None}


def blind_packet_forbidden_fields(packet: Mapping[str, Any]) -> set[str]:
    forbidden = {
        "accepted", "canonical", "confidence", "previous_model_verdict", "psl_score",
        "reviewer_acceptance", "production_status", "previous_verdict", "resolved_person_id",
        "identity_resolution_basis", "identity_status", "review_status",
    }
    return forbidden & set(packet)


def _usage(response: Mapping[str, Any] | None) -> dict[str, int]:
    raw = response.get("usage") if isinstance(response, Mapping) and isinstance(response.get("usage"), Mapping) else {}
    return {key: int(raw.get(key) or 0) for key in ("prompt_tokens", "completion_tokens", "total_tokens")}


def _finish_reason(response: Mapping[str, Any]) -> str | None:
    choices = response.get("choices") if isinstance(response, Mapping) else None
    if not isinstance(choices, list) or not choices or not isinstance(choices[0], Mapping):
        return None
    return _text(choices[0].get("finish_reason")) or None


def _safe_error(exc: Exception) -> dict[str, Any]:
    message = str(exc)
    secret = os.environ.get("DEEPSEEK_API_KEY")
    if secret:
        message = message.replace(secret, "[REDACTED]")
    return {"exception_class": type(exc).__name__, "exception_message": message, "http_status": getattr(exc, "http_status", None)}


def preflight(timeout: int = 20) -> dict[str, Any]:
    started = time.monotonic()
    row: dict[str, Any] = {"model": MODEL, "start_time": utc_now()}
    try:
        response = call_deepseek([{"role": "user", "content": "Reply only with OK"}], model=MODEL, temperature=0, max_tokens=8, thinking={"type": "disabled"}, timeout=timeout)
        row.update({"status": "reachable", "usage": _usage(response), "response_model": response.get("model")})
    except Exception as exc:
        row.update({"status": "live_network_unavailable", **_safe_error(exc)})
    row.update({"elapsed_seconds": round(time.monotonic() - started, 3), "end_time": utc_now()})
    return row


def call_audit(packet: Mapping[str, Any], raw_dir: Path, sequence: int, timeout: int = 120) -> tuple[dict[str, Any], Mapping[str, Any] | None]:
    started = time.monotonic()
    record: dict[str, Any] = {"sequence": sequence, "claim_id": packet.get("claim_id"), "model": MODEL, "prompt_version": PROMPT_VERSION, "input_hash": stable_hash(audit_prompt(packet)), "start_time": utc_now()}
    try:
        response = call_deepseek(
            [{"role": "system", "content": "You are a blind historical identity auditor. Use only supplied evidence and return the forced function call."}, {"role": "user", "content": json.dumps(audit_prompt(packet), ensure_ascii=False, sort_keys=True)}],
            model=MODEL,
            temperature=0,
            thinking={"type": "disabled"},
            max_tokens=700,
            timeout=timeout,
            endpoint="https://api.deepseek.com/beta/chat/completions",
            tools=[audit_tool()],
            tool_choice={"type": "function", "function": {"name": "submit_identity_audit_verdict"}},
        )
        raw_path = raw_dir / f"{sequence:05d}-{_text(packet.get('claim_id'))}.json"
        if raw_path.exists():
            raise RuntimeError(f"immutable_raw_response_exists:{raw_path.name}")
        write_json(raw_path, response)
        record.update({"status": "response", "classification": "response_truncated" if _finish_reason(response) == "length" else "response", "finish_reason": _finish_reason(response), "usage": _usage(response), "raw_path": str(raw_path.relative_to(ROOT))})
        if record["classification"] == "response_truncated":
            return record, None
        payload, channel, error = controller.extract_strict_tool_payload(response, expected_function_name="submit_identity_audit_verdict")
        if error:
            record.update({"classification": "response_parse_failure", "response_channel": channel, "parse_error": error})
            return record, None
        record.update({"classification": "parsed", "response_channel": channel})
        return record, payload
    except Exception as exc:
        record.update({"status": "provider_request_failure", "classification": "provider_request_failure", **_safe_error(exc)})
        return record, None
    finally:
        record.update({"elapsed_seconds": round(time.monotonic() - started, 3), "end_time": utc_now()})


def _packet_evidence_adequate(packet: Mapping[str, Any]) -> bool:
    """Whether the packet has a contiguous, source-grounded audit anchor.

    A context-only or line-break-separated witness is retained for audit but
    is not presented as sufficient evidence.  HDA1 therefore reports it as
    an evidence limitation rather than fabricating an LLM verdict.
    """
    return any(
        bool(item.get("evidence_text"))
        and bool(item.get("exact_span"))
        and item.get("exact_span_grounded") is True
        for item in packet.get("evidence_items", []) or []
        if isinstance(item, Mapping)
    )


def _priority(claim: Mapping[str, Any], frequency: Mapping[str, int], degree: Mapping[str, int]) -> tuple[int, int, int, str]:
    surface = _text(claim.get("surface"))
    pid = _text(claim.get("person_id"))
    return (-int(claim.get("verdict_rank", 0)), -frequency.get(surface, 0), -degree.get(pid, 0), _text(claim.get("claim_id")))


def summarize_results(results: Sequence[Mapping[str, Any]], claims: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    claim_by_id = {_text(x.get("claim_id")): x for x in claims}
    counts = collections.Counter(_text(row.get("verdict")) for row in results if _text(row.get("execution_status")) == "validated")
    by_type: dict[str, collections.Counter[str]] = collections.defaultdict(collections.Counter)
    by_status: dict[str, collections.Counter[str]] = collections.defaultdict(collections.Counter)
    by_person: dict[str, collections.Counter[str]] = collections.defaultdict(collections.Counter)
    invalid = 0
    inadequate = 0
    for row in results:
        claim = claim_by_id.get(_text(row.get("claim_id")), {})
        verdict = _text(row.get("verdict"))
        if _text(row.get("execution_status")) == "invalid_provider_payload":
            invalid += 1
        if row.get("adequate_evidence") is False:
            inadequate += 1
        if _text(row.get("execution_status")) == "validated":
            by_type[_text(claim.get("claim_type"))][verdict] += 1
            by_status[_text(claim.get("identity_status"))][verdict] += 1
            by_person[_text(claim.get("person_id"))][verdict] += 1
    validated_total = sum(counts.values())
    claim_total = len(claims)
    verdict_rates = {
        f"{verdict}_rate_validated": round(counts[verdict] / validated_total, 6) if validated_total else 0
        for verdict in sorted(VERDICTS)
    }
    verdict_rates.update({
        f"{verdict}_rate_claims": round(counts[verdict] / claim_total, 6) if claim_total else 0
        for verdict in sorted(VERDICTS)
    })
    return {
        "schema": "hda1-identity-audit-metrics-v1",
        "total_claims_audited": len(claims),
        "persons_covered": len({_text(x.get("person_id")) for x in claims if _text(x.get("person_id"))}),
        "existing_persons_covered": len({
            _text(x.get("person_id"))
            for x in claims
            if _text(x.get("person_id")).startswith("person-")
        }),
        "candidate_entities_covered": len({
            _text(x.get("person_id"))
            for x in claims
            if _text(x.get("person_id")) and not _text(x.get("person_id")).startswith("person-")
        }),
        "source_claim_count": sum(
            1 for x in claims if _text(x.get("claim_type")) == "hdb2_f_identity_claim"
        ),
        "catalogue_alias_claim_count": sum(
            1 for x in claims if _text(x.get("claim_type")) == "catalogue_alias"
        ),
        "person_source_evidence_claim_count": sum(
            1 for x in claims if _text(x.get("claim_type")) == "person_catalogue_source_evidence"
        ),
        "support_count": counts["support"],
        "contradict_count": counts["contradict"],
        "ambiguous_count": counts["ambiguous"],
        "insufficient_count": counts["insufficient_evidence"],
        "validated_claim_count": sum(counts.values()),
        "verdict_rate_denominators": {
            "validated": validated_total,
            "all_claims": claim_total,
        },
        **verdict_rates,
        "invalid_provider_payloads": invalid,
        "not_executed_claim_count": sum(1 for row in results if _text(row.get("execution_status")) == "not_executed"),
        "provider_unavailable_claim_count": sum(1 for row in results if "live_provider_unavailable" in (row.get("validation_errors") or [])),
        "claims_lacking_adequate_evidence": inadequate,
        "verdict_by_claim_type": {key: dict(sorted(value.items())) for key, value in sorted(by_type.items())},
        "verdict_by_identity_status": {key: dict(sorted(value.items())) for key, value in sorted(by_status.items())},
        "per_person": {key: dict(sorted(value.items())) for key, value in sorted(by_person.items())},
        "contradicts_among_direct_existing": sum(1 for row in results if row.get("verdict") == "contradict" and _text(claim_by_id.get(_text(row.get("claim_id")), {}).get("identity_status")) in {"direct_existing", "resolved_existing"}),
        "contradicts_among_catalogue_exact_match": sum(1 for row in results if row.get("verdict") == "contradict" and _text(claim_by_id.get(_text(row.get("claim_id")), {}).get("identity_basis")) == "catalogue_exact_match"),
        "candidate_only": True,
        "canonical_write_back": False,
    }


def build_review_queue(results: Sequence[Mapping[str, Any]], claims: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    claim_by_id = {_text(x.get("claim_id")): x for x in claims}
    frequency = collections.Counter(_text(x.get("surface")) for x in claims)
    degree = collections.Counter(_text(x.get("person_id")) for x in claims)
    rank = {"contradict": 0, "ambiguous": 1, "insufficient_evidence": 2, "support": 3}
    queue: list[dict[str, Any]] = []
    for result in results:
        verdict = _text(result.get("verdict"))
        if verdict not in {"contradict", "ambiguous", "insufficient_evidence"}:
            continue
        claim = claim_by_id.get(_text(result.get("claim_id")), {})
        queue.append({
            "priority": verdict,
            "priority_key": list(_priority({**claim, "verdict_rank": rank.get(verdict, 9)}, frequency, degree)),
            "claim": dict(claim),
            "audit": {key: result.get(key) for key in ("verdict", "supporting_evidence_ids", "contradicting_evidence_ids", "reason_types", "suggested_identity_surface", "explanation", "execution_status", "validation_errors")},
            "candidate_only": True,
            "canonical_write_back": False,
        })
    return sorted(queue, key=lambda row: tuple(row.get("priority_key", [])))


def protected_hashes() -> dict[str, str]:
    names = [
        "data/people.json", "data/relations.json", "data/personStory.json",
        "data/annotation/story-temporal-anchors-h0a.json", "data/annotation/kinship-h0b1.json",
        "data/annotation/marriages-h0b1.json", "data/annotation/office-tenures-h0b1.json",
        "data/derived/hdb1-cross-wave-candidate-historical-db.json",
        "data/derived/hdb2-f-occurrence-ledger.json", "data/derived/hdb2-f-occurrence-cases.json",
        "data/derived/hdb2-f-person-knowledge.json", "data/derived/hdb2-f-candidate-person-knowledge.json",
    ]
    current = {name: file_hash(ROOT / name) for name in names if (ROOT / name).is_file()}
    # HDA1/HGE1 are completed snapshots.  SFH2R intentionally repairs the
    # active derived profile projection after those snapshots were frozen.
    # Preserve their pre-repair protection value only across the explicit
    # SFH2R transition; canonical and HNG/HDB evidence hashes still come from
    # the current checkout and remain fail-closed.
    baseline_path = ROOT / "data/generated/hge1/baseline.json"
    baseline = read_json(baseline_path, {}) or {}
    frozen = baseline.get("protected_hashes") if isinstance(baseline, Mapping) else None
    if isinstance(frozen, Mapping) and sfh2r_contract.frozen_hashes_are_current_or_authorized(frozen, current):
        return {str(key): str(value) for key, value in frozen.items()}
    return current


def prepare() -> dict[str, Any]:
    claims = build_claims()
    packets = build_audit_packets(claims)
    write_json(OUT / "claims.json", claims)
    write_json(OUT / "audit-packets.json", packets)
    manifest = {
        "schema": "hda1-manifest-v1",
        "run_version": RUN_VERSION,
        "prompt_version": PROMPT_VERSION,
        "model": MODEL,
        "claims_hash": stable_hash(claims),
        "packets_hash": stable_hash(packets),
        "protected_hashes_before": protected_hashes(),
        "hdb2_f_snapshot_hash": file_hash(ROOT / "data/derived/hdb2-f-person-knowledge.json") if (ROOT / "data/derived/hdb2-f-person-knowledge.json").is_file() else None,
        "candidate_only": True,
        "canonical_write_back": False,
        "blind_audit": True,
    }
    write_json(OUT / "manifest.json", manifest)
    return {"claims": claims, "packets": packets, "manifest": manifest}


def run(*, live: bool, run_id: str | None = None, retry_provider: bool = True) -> dict[str, Any]:
    prepared = prepare()
    packets = list(prepared["packets"].get("packets", []))
    run_name = run_id or (dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ") if live else "offline")
    base = OUT / "live" / run_name
    raw_dir = base / "raw-api"
    raw_dir.mkdir(parents=True, exist_ok=True)
    preflight_row = preflight() if live else {"status": "offline_not_requested", "model": MODEL}
    results: list[dict[str, Any]] = []
    transport: list[dict[str, Any]] = []
    sequence = 0
    for packet in packets:
        sequence += 1
        if not live or preflight_row.get("status") != "reachable":
            results.append({"claim_id": packet.get("claim_id"), "execution_status": "not_executed", "verdict": "insufficient_evidence", "adequate_evidence": _packet_evidence_adequate(packet), "validation_errors": ["live_provider_unavailable" if live else "offline_run"], "supporting_evidence_ids": [], "contradicting_evidence_ids": [], "reason_types": ["insufficient_context"]})
            continue
        record, payload = call_audit(packet, raw_dir, sequence)
        transport.append(record)
        validation = validate_audit_payload(payload, packet) if payload is not None else {"valid": False, "errors": [record.get("classification", "provider_failure")], "payload": None}
        if not validation.get("valid") and retry_provider and record.get("classification") in {"provider_request_failure", "response_parse_failure", "response_truncated"}:
            sequence += 1
            retry_record, retry_payload = call_audit(packet, raw_dir, sequence)
            retry_record["retry_of_sequence"] = record.get("sequence")
            transport.append(retry_record)
            retry_validation = validate_audit_payload(retry_payload, packet) if retry_payload is not None else {"valid": False, "errors": [retry_record.get("classification", "provider_failure")], "payload": None}
            if retry_validation.get("valid"):
                record, payload, validation = retry_record, retry_payload, retry_validation
        payload_value = validation.get("payload") if validation.get("valid") else {}
        results.append({"claim_id": packet.get("claim_id"), "execution_status": "validated" if validation.get("valid") else "invalid_provider_payload", "verdict": payload_value.get("verdict", "insufficient_evidence"), "adequate_evidence": _packet_evidence_adequate(packet), "validation_errors": validation.get("errors", []), "supporting_evidence_ids": payload_value.get("supporting_evidence_ids", []), "contradicting_evidence_ids": payload_value.get("contradicting_evidence_ids", []), "reason_types": payload_value.get("reason_types", []), "suggested_identity_surface": payload_value.get("suggested_identity_surface"), "explanation": payload_value.get("explanation", ""), "transport_sequence": record.get("sequence")})
    metrics = summarize_results(results, prepared["claims"].get("claims", []))
    metrics.update({"model": MODEL, "prompt_version": PROMPT_VERSION, "provider_preflight": preflight_row, "api_call_count": len(transport), "retry_count": sum(1 for x in transport if x.get("retry_of_sequence")), "prompt_tokens": sum(_usage(x).get("prompt_tokens", 0) for x in transport), "completion_tokens": sum(_usage(x).get("completion_tokens", 0) for x in transport), "total_tokens": sum(_usage(x).get("total_tokens", 0) for x in transport), "latency_median": statistics.median([float(x.get("elapsed_seconds", 0)) for x in transport]) if transport else 0, "latency_max": max([float(x.get("elapsed_seconds", 0)) for x in transport], default=0)})
    write_json(base / "manifest.json", {"run_version": RUN_VERSION, "run_id": run_name, "claims_hash": prepared["manifest"]["claims_hash"], "packets_hash": prepared["manifest"]["packets_hash"], "preflight": preflight_row, "live": live, "candidate_only": True, "canonical_write_back": False, "protected_hashes_before": prepared["manifest"]["protected_hashes_before"]})
    write_json(base / "preflight.json", preflight_row)
    write_json(base / "transport.json", transport)
    write_json(base / "audit-results.json", {"schema": "hda1-audit-results-v1", "results": results, "candidate_only": True, "canonical_write_back": False})
    write_json(base / "metrics.json", metrics)
    queue = build_review_queue(results, prepared["claims"].get("claims", []))
    write_json(base / "human-review-queue.json", {"schema": "hda1-human-review-queue-v1", "items": queue, "candidate_only": True, "canonical_write_back": False})
    for name, predicate in (("contradictions.json", lambda r: r.get("verdict") == "contradict"), ("ambiguous.json", lambda r: r.get("verdict") == "ambiguous"), ("insufficient.json", lambda r: r.get("verdict") == "insufficient_evidence")):
        write_json(base / name, {"records": [x for x in results if predicate(x)], "candidate_only": True, "canonical_write_back": False})
    # Keep a stable top-level pointer for offline validators and humans.
    write_json(OUT / "metrics.json", metrics)
    write_json(OUT / "audit-results.json", {"run_id": run_name, "results_path": str((base / "audit-results.json").relative_to(ROOT)), "metrics_path": str((base / "metrics.json").relative_to(ROOT)), "candidate_only": True, "canonical_write_back": False})
    write_json(OUT / "contradictions.json", {"run_id": run_name, "records": [x for x in results if x.get("verdict") == "contradict"]})
    write_json(OUT / "ambiguous.json", {"run_id": run_name, "records": [x for x in results if x.get("verdict") == "ambiguous"]})
    write_json(OUT / "insufficient.json", {"run_id": run_name, "records": [x for x in results if x.get("verdict") == "insufficient_evidence"]})
    write_json(OUT / "human-review-queue.json", {"run_id": run_name, "items": queue, "candidate_only": True, "canonical_write_back": False})
    return {"run_id": run_name, "output": str(base.relative_to(ROOT)), "metrics": metrics, "claim_count": len(prepared["claims"].get("claims", [])), "api_calls": len(transport)}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prepare", action="store_true")
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--offline", action="store_true")
    parser.add_argument("--run-id")
    args = parser.parse_args()
    if args.prepare or (not args.live and not args.offline):
        result = prepare()
        print(json.dumps({"claim_count": result["claims"]["claim_count"], "packet_count": result["packets"]["claim_count"], "claims_hash": result["manifest"]["claims_hash"]}, ensure_ascii=False, indent=2))
        return 0
    print(json.dumps(run(live=args.live, run_id=args.run_id), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
