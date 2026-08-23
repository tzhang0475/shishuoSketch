#!/usr/bin/env python3
"""SRM0.4B protocol helpers.

SRM0.4B deliberately lives beside, rather than inside, the SRM0.4A runner.
It reuses A's registered-source reader and lexical retriever, but gives the
live/fixture protocol its own fail-soft normalization and output contract.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import socket
import ssl
import urllib.error
from pathlib import Path
from typing import Any, Mapping, Sequence

try:
    from .ds1_common import ROOT, stable_json
    from .srm0_4a_common import (
        BOUNDARY_PUNCTUATION,
        COMMENTARY_SYSTEM_PROMPT,
        INITIAL_SYSTEM_PROMPT,
        RETRIEVAL_SYSTEM_PROMPT,
        _align_span,
        _normalize_quote,
        _text,
        build_commentary_messages,
        build_initial_messages,
        build_retrieval_messages,
        build_retrieval_registry,
        open_candidates,
        search_registry,
        story_material,
        working_answer,
    )
except ImportError:  # pragma: no cover - direct execution
    from ds1_common import ROOT, stable_json
    from srm0_4a_common import (
        BOUNDARY_PUNCTUATION,
        COMMENTARY_SYSTEM_PROMPT,
        INITIAL_SYSTEM_PROMPT,
        RETRIEVAL_SYSTEM_PROMPT,
        _align_span,
        _normalize_quote,
        _text,
        build_commentary_messages,
        build_initial_messages,
        build_retrieval_messages,
        build_retrieval_registry,
        open_candidates,
        search_registry,
        story_material,
        working_answer,
    )


SCHEMA_VERSION = 1
MODEL = "deepseek-v4-flash"
PROVIDER = "deepseek"
PROMPT_VERSION = "srm0.4b-robust-live-convergence-v1"
MAX_INITIAL_GAPS = 3
MAX_EVIDENCE_ROUNDS = 4
MAX_ANSWERED_ASPECTS = 3
MAX_UNANSWERED_ASPECTS = 3
MAX_CONFLICTS = 3
MAX_CHILDREN_PER_UPDATE = 2

# This is the frozen SRM0.4A pilot, in the order used for its live protocol
# run.  It is intentionally not recomputed from selection metadata.
FIXED_STORIES = (
    "25-paidiao-007",
    "19-xianyuan-010",
    "02-yanyu-053",
    "01-dexing-040",
    "09-pinzao-038",
    "33-youhui-012",
)

OUTPUT_BASE = Path("data/generated/srm0")
LIVE_SUMMARY_PATH = Path("data/generated/srm0/srm0-4b-live-summary.json")
FIXTURE_SUMMARY_PATH = Path("data/generated/srm0/srm0-4b-fixture-summary.json")
STATUS_PATH = Path("data/generated/srm0/srm0-4-status.json")
REVIEW_PATH = Path("data/annotation/srm0-4b-review.json")

SEARCHED_CORPORA = [
    "世說新語",
    "余嘉錫箋疏",
    "晉書",
    "三國志",
    "資治通鑑",
    "資治通鑑考異",
]

PYTHON_OWNED_FIELDS = {
    "state", "next_action", "terminal_reason", "working_answer",
    "parent_question_id", "parent_aspect_id", "question", "story_span",
    "gap", "active", "evidence_rounds", "claim_fingerprints",
}
SEMANTIC_UPDATE_FIELDS = {
    "question_id", "answered_aspects", "unanswered_aspects", "conflicts",
    "reading_sufficient", "historical_verification_open",
}
INITIAL_FIELDS = {"question_id", "story_span", "gap"}
GAP_LEAK_PATTERNS = (
    "可能是", "可能为", "可能為", "可能指", "应为", "應為", "应该是", "應該是",
    "即是", "即为", "即為", "也就是", "换言之", "換言之", "意为", "意為",
    "解释为", "解釋為", "可理解为", "可理解為",
)

TRANSPORT_FAILURE_CLASSES = {
    "sandbox_denied",
    "proxy_failure",
    "dns_failure",
    "connect_timeout",
    "read_timeout",
    "tls_failure",
    "auth_failure",
    "rate_limited",
    "server_error",
    "other_transport_failure",
}


def output_directory(story_id: str, *, execution_kind: str, run_id: str | None = None, fixture_version: str = "fixture-v1") -> Path:
    if execution_kind == "fixture":
        return OUTPUT_BASE / story_id / "convergence" / "fixture" / fixture_version
    if not run_id:
        raise ValueError("live output requires run_id")
    return OUTPUT_BASE / story_id / "convergence" / "live" / run_id


def run_id_for(material: Mapping[str, Any]) -> str:
    payload = {
        "story_id": material.get("story_id"),
        "main_text": material.get("main_text"),
        "liu_notes": material.get("liu_notes", []),
        "jianshu_notes": material.get("jianshu_notes", []),
        "prompt_version": PROMPT_VERSION,
    }
    digest = hashlib.sha256(stable_json(payload).encode("utf-8")).hexdigest()[:16]
    return f"srm0-4b-live-{digest}"


def fixture_version() -> str:
    return "fixture-v1"


def _exception_chain(exc: BaseException) -> list[BaseException]:
    chain: list[BaseException] = []
    current: BaseException | None = exc
    seen: set[int] = set()
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        chain.append(current)
        current = current.__cause__ or current.__context__
    return chain


def classify_deepseek_exception(exc: BaseException) -> str | None:
    """Classify client/API failures without turning them into model findings."""
    chain = _exception_chain(exc)
    text = " ".join(str(item) for item in chain).lower()
    if "deepseek_api_key is not set" in text or "401" in text or "403" in text:
        return "auth_failure"
    if "429" in text or "too many requests" in text or "rate limit" in text:
        return "rate_limited"
    for item in chain:
        if isinstance(item, urllib.error.HTTPError):
            if 500 <= item.code <= 599:
                return "server_error"
            if item.code in {401, 403}:
                return "auth_failure"
            if item.code == 429:
                return "rate_limited"
            return "other_transport_failure"
        if isinstance(item, ssl.SSLError):
            return "tls_failure"
        if isinstance(item, socket.gaierror):
            return "dns_failure"
        if isinstance(item, urllib.error.URLError):
            reason = getattr(item, "reason", item)
            reason_text = str(reason).lower()
            if "operation not permitted" in reason_text or "operation not permitted" in text:
                return "sandbox_denied"
            if isinstance(reason, socket.gaierror) or any(marker in reason_text for marker in ("name or service not known", "temporary failure in name resolution", "nodename nor servname")):
                return "dns_failure"
            if isinstance(reason, ssl.SSLError) or any(marker in reason_text for marker in ("ssl", "certificate", "tls")):
                return "tls_failure"
            if isinstance(reason, TimeoutError) or "timed out" in reason_text:
                return "connect_timeout"
            if ("127.0.0.1" in text or "localhost" in text or "proxy" in text) and any(marker in text for marker in ("refused", "failed to connect", "cannot connect")):
                return "proxy_failure"
            return "other_transport_failure"
    if isinstance(exc, TimeoutError) or "exceeded" in text and "deadline" in text:
        return "read_timeout"
    if "operation not permitted" in text:
        return "sandbox_denied"
    if "connection refused" in text and (os.environ.get("HTTPS_PROXY", "").startswith(("http://127.", "http://localhost", "https://127.", "https://localhost"))):
        return "proxy_failure"
    if "deepseek api request failed" in text:
        return "other_transport_failure"
    return None


def status_document(*, stage: str, fixture_results_present: bool, live_results_present: bool) -> dict[str, Any]:
    return {
        "stage": stage,
        "selected_story_count": len(FIXED_STORIES),
        "live_results_present": bool(live_results_present),
        "fixture_results_present": bool(fixture_results_present),
        "previous_live_results_reset": True,
        "canonical_write_back": False,
    }


def write_status(root: Path = ROOT, *, stage: str, fixture_results_present: bool, live_results_present: bool) -> None:
    path = root / STATUS_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(stable_json(status_document(stage=stage, fixture_results_present=fixture_results_present, live_results_present=live_results_present)), encoding="utf-8")


def reset_srm0_4_results(root: Path = ROOT) -> list[str]:
    """Remove only the frozen SRM0.4 generated result paths."""
    removed: list[str] = []
    for relative in (Path("data/generated/srm0/srm0-4a-batch-summary.json"), LIVE_SUMMARY_PATH, FIXTURE_SUMMARY_PATH):
        target = root / relative
        if target.is_file():
            target.unlink()
            removed.append(relative.as_posix())
    for story_id in FIXED_STORIES:
        target = root / OUTPUT_BASE / story_id / "convergence"
        if target.is_dir():
            shutil.rmtree(target)
            removed.append(target.relative_to(root).as_posix() + "/")
    write_status(root, stage="awaiting_clean_live_run", fixture_results_present=False, live_results_present=False)
    return removed


def parse_json_any(content: str) -> tuple[Any, str]:
    """Parse provider JSON while recording only structural fence cleanup."""
    value = str(content or "").strip()
    if value.startswith("```") and value.endswith("```"):
        lines = value.splitlines()
        if len(lines) >= 3:
            value = "\n".join(lines[1:-1]).strip()
            return json.loads(value), "markdown_fence_removed"
    return json.loads(value), "none"


def _normalization(stage: str, path: str, action: str, reason: str, **extra: Any) -> dict[str, Any]:
    row = {"stage": stage, "path": path, "action": action, "reason": reason}
    row.update(extra)
    return row


def _mapping_rows(value: Any, *, stage: str, path: str, normalizations: list[dict[str, Any]], rejected: list[dict[str, Any]], label: str) -> list[Any]:
    if isinstance(value, list):
        return value
    if isinstance(value, Mapping):
        normalizations.append(_normalization(stage, path, "wrap_singleton_array", f"{label} object normalized to one-item array"))
        return [value]
    if value is None:
        normalizations.append(_normalization(stage, path, "default_empty_array", f"missing {label} treated as empty"))
        return []
    rejected.append({"path": path, "reason": f"{label} is neither an array nor an object"})
    return []


def _drop_extra(row: Mapping[str, Any], allowed: set[str], *, stage: str, path: str, normalizations: list[dict[str, Any]]) -> None:
    extras = sorted(str(key) for key in set(row) - allowed)
    if extras:
        normalizations.append(_normalization(stage, path, "drop_extra_fields", "structural fields are not part of the B contract", fields=extras))


def _gap_rejection(row: Any, reason: str, index: int) -> dict[str, Any]:
    result = {"index": index, "reason": reason}
    if isinstance(row, Mapping):
        for key in ("question_id", "story_span", "gap"):
            if row.get(key):
                result[key] = str(row[key])
    return result


def self_resolution_reason(gap: Mapping[str, Any], main_text: str) -> str | None:
    span = str(gap.get("story_span", ""))
    start = main_text.find(span)
    if start < 0:
        return None
    gap_text = str(gap.get("gap", ""))
    quoted = re.findall(r"[『「“\"]([^』」”\"]{2,20})[』」”\"]", gap_text)
    for token in quoted:
        cursor = 0
        while True:
            position = main_text.find(token, cursor)
            if position < 0:
                break
            inside = start <= position and position + len(token) <= start + len(span)
            if not inside:
                window = main_text[max(0, position - 8): min(len(main_text), position + len(token) + 12)]
                if any(marker in window for marker in ("即", "乃", "是", "為", "为", "指", "謂", "谓")):
                    return f"same-story direct marker around {token}"
            cursor = position + max(1, len(token))
    return None


def low_leverage_reason(gap: Mapping[str, Any]) -> str | None:
    value = str(gap.get("gap", ""))
    low = ("姓名", "名字", "籍贯", "籍貫", "家世", "生平")
    high = ("为何", "為何", "何以", "如何", "关系", "關係", "职责", "職任", "处境", "處境", "局势", "局勢", "行动", "行動", "隐喻", "隱喻", "意味", "牵制", "牽制", "冲突", "衝突", "叙事", "敘事")
    if any(marker in value for marker in low) and not any(marker in value for marker in high):
        return "low_reading_leverage"
    return None


def normalize_initial_fail_soft(raw: Any, material: Mapping[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    normalizations: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    if isinstance(raw, Mapping):
        _drop_extra(raw, {"gaps"}, stage="initial", path="$", normalizations=normalizations)
        rows = _mapping_rows(raw.get("gaps"), stage="initial", path="$.gaps", normalizations=normalizations, rejected=rejected, label="gaps")
    elif isinstance(raw, list):
        normalizations.append(_normalization("initial", "$", "wrap_singleton_array", "top-level array normalized as gaps"))
        rows = raw
    else:
        rows = []
        rejected.append({"path": "$", "reason": "top-level JSON is not an object or array"})
    accepted: list[dict[str, Any]] = []
    for index, row in enumerate(rows):
        if index >= MAX_INITIAL_GAPS:
            rejected.append(_gap_rejection(row, "more_than_three_gaps", index))
            continue
        if not isinstance(row, Mapping):
            rejected.append(_gap_rejection(row, "gap_is_not_an_object", index))
            continue
        _drop_extra(row, INITIAL_FIELDS, stage="initial", path=f"$.gaps[{index}]", normalizations=normalizations)
        qid, span_raw, gap = _text(row.get("question_id")), _text(row.get("story_span")), _text(row.get("gap"))
        if not qid or not span_raw or not gap:
            rejected.append(_gap_rejection(row, "empty_required_field", index))
            continue
        span = _align_span(span_raw, str(material.get("main_text", "")))
        if span != span_raw:
            normalizations.append(_normalization("initial", f"$.gaps[{index}].story_span", "normalize_whitespace", "span whitespace aligned to canonical Story text", original=span_raw, normalized=span))
        if span not in str(material.get("main_text", "")):
            rejected.append(_gap_rejection(row, "story_span_not_found", index))
            continue
        if len(gap) > 120 or any(pattern in gap for pattern in GAP_LEAK_PATTERNS):
            rejected.append(_gap_rejection(row, "answer_or_explanation_leakage", index))
            continue
        candidate = {"question_id": qid, "story_span": span, "gap": gap}
        reason = self_resolution_reason(candidate, str(material.get("main_text", ""))) or low_leverage_reason(candidate)
        if reason:
            rejected.append(_gap_rejection(row, reason, index))
            continue
        if any(existing.get("question_id") == qid for existing in accepted):
            rejected.append(_gap_rejection(row, "duplicate_question_id", index))
            continue
        accepted.append(candidate)
    return {"gaps": accepted}, {"normalizations": normalizations, "rejected_gaps": rejected}


def _valid_quote(ref: str, quote: str, sources: Mapping[str, str]) -> tuple[str | None, str | None, str | None]:
    if ref not in sources:
        return None, None, "unknown_evidence_ref"
    if not quote:
        return None, None, "empty_quote"
    normalized, method = _normalize_quote(quote, str(sources[ref]))
    if normalized not in str(sources[ref]):
        return None, None, "quote_not_found"
    return normalized, method, None


def _evidence_rows(value: Any, *, stage: str, path: str, sources: Mapping[str, str], normalizations: list[dict[str, Any]], rejected: list[dict[str, Any]]) -> list[dict[str, str]]:
    rows = _mapping_rows(value, stage=stage, path=path, normalizations=normalizations, rejected=rejected, label="evidence")
    valid: list[dict[str, str]] = []
    for index, item in enumerate(rows):
        if not isinstance(item, Mapping):
            rejected.append({"path": f"{path}[{index}]", "reason": "evidence_is_not_an_object"})
            continue
        _drop_extra(item, {"ref", "quote"}, stage=stage, path=f"{path}[{index}]", normalizations=normalizations)
        ref, quote = _text(item.get("ref")), _text(item.get("quote"))
        normalized, method, reason = _valid_quote(ref, quote, sources)
        if reason:
            rejected.append({"path": f"{path}[{index}]", "ref": ref, "reason": reason})
            continue
        if normalized != quote:
            normalizations.append(_normalization(stage, f"{path}[{index}].quote", "normalize_quote", "only whitespace/boundary punctuation normalized", original=quote, normalized=normalized, method=method))
        valid.append({"ref": ref, "quote": str(normalized)})
    return valid


def normalize_delta_fail_soft(raw: Any, sources: Mapping[str, str], question_ids: set[str]) -> tuple[dict[str, Any], dict[str, Any]]:
    normalizations: list[dict[str, Any]] = []
    rejected_evidence: list[dict[str, Any]] = []
    rejected_claims: list[dict[str, Any]] = []
    rejected_aspects: list[dict[str, Any]] = []
    rejected_updates: list[dict[str, Any]] = []
    if isinstance(raw, Mapping):
        _drop_extra(raw, {"updates"}, stage="delta", path="$", normalizations=normalizations)
        rows = _mapping_rows(raw.get("updates"), stage="delta", path="$.updates", normalizations=normalizations, rejected=rejected_updates, label="updates")
    elif isinstance(raw, list):
        normalizations.append(_normalization("delta", "$", "wrap_singleton_array", "top-level array normalized as updates"))
        rows = raw
    else:
        rows = []
        rejected_updates.append({"path": "$", "reason": "top-level JSON is not an object or array"})
    updates: list[dict[str, Any]] = []
    seen: set[str] = set()
    for index, raw_row in enumerate(rows):
        path = f"$.updates[{index}]"
        if not isinstance(raw_row, Mapping):
            rejected_updates.append({"path": path, "reason": "update_is_not_an_object"})
            continue
        _drop_extra(raw_row, SEMANTIC_UPDATE_FIELDS, stage="delta", path=path, normalizations=normalizations)
        qid = _text(raw_row.get("question_id"))
        if not qid or qid not in question_ids:
            rejected_updates.append({"path": path, "question_id": qid, "reason": "unknown_or_missing_question_id"})
            continue
        if qid in seen:
            rejected_updates.append({"path": path, "question_id": qid, "reason": "duplicate_question_id"})
            continue
        if not isinstance(raw_row.get("reading_sufficient"), bool) or not isinstance(raw_row.get("historical_verification_open"), bool):
            rejected_updates.append({"path": path, "question_id": qid, "reason": "semantic_booleans_required"})
            continue
        seen.add(qid)
        answered_rows = _mapping_rows(raw_row.get("answered_aspects"), stage="delta", path=f"{path}.answered_aspects", normalizations=normalizations, rejected=rejected_aspects, label="answered_aspects")
        unanswered_rows = _mapping_rows(raw_row.get("unanswered_aspects"), stage="delta", path=f"{path}.unanswered_aspects", normalizations=normalizations, rejected=rejected_aspects, label="unanswered_aspects")
        conflict_rows = _mapping_rows(raw_row.get("conflicts"), stage="delta", path=f"{path}.conflicts", normalizations=normalizations, rejected=rejected_aspects, label="conflicts")
        answered: list[dict[str, Any]] = []
        unanswered: list[dict[str, Any]] = []
        for a_index, aspect in enumerate(answered_rows[:MAX_ANSWERED_ASPECTS]):
            a_path = f"{path}.answered_aspects[{a_index}]"
            if not isinstance(aspect, Mapping) or not _text(aspect.get("aspect_id")) or not _text(aspect.get("claim")):
                rejected_claims.append({"path": a_path, "question_id": qid, "reason": "claim_missing_id_or_text"})
                continue
            _drop_extra(aspect, {"aspect_id", "claim", "evidence"}, stage="delta", path=a_path, normalizations=normalizations)
            evidence = _evidence_rows(aspect.get("evidence"), stage="delta", path=f"{a_path}.evidence", sources=sources, normalizations=normalizations, rejected=rejected_evidence)
            if not evidence:
                rejected_claims.append({"path": a_path, "question_id": qid, "reason": "claim_has_no_valid_evidence"})
                continue
            answered.append({"aspect_id": _text(aspect.get("aspect_id")), "claim": _text(aspect.get("claim")), "evidence": evidence})
        for a_index, aspect in enumerate(unanswered_rows[:MAX_UNANSWERED_ASPECTS]):
            a_path = f"{path}.unanswered_aspects[{a_index}]"
            if not isinstance(aspect, Mapping) or not _text(aspect.get("aspect_id")) or not _text(aspect.get("gap")) or aspect.get("reading_impact") not in {"high", "medium", "low"}:
                rejected_aspects.append({"path": a_path, "question_id": qid, "reason": "unanswered_aspect_invalid"})
                continue
            _drop_extra(aspect, {"aspect_id", "gap", "reading_impact"}, stage="delta", path=a_path, normalizations=normalizations)
            # This is a semantic field; preserve it, but do not infer or edit it.
            unanswered_aspect = {"aspect_id": _text(aspect.get("aspect_id")), "gap": _text(aspect.get("gap")), "reading_impact": aspect.get("reading_impact")}
            if any(row.get("aspect_id") == unanswered_aspect["aspect_id"] for row in unanswered):
                rejected_aspects.append({"path": a_path, "question_id": qid, "reason": "duplicate_unanswered_aspect_id"})
                continue
            unanswered.append(unanswered_aspect)
        conflicts: list[dict[str, Any]] = []
        for c_index, conflict in enumerate(conflict_rows[:MAX_CONFLICTS]):
            c_path = f"{path}.conflicts[{c_index}]"
            if not isinstance(conflict, Mapping) or not _text(conflict.get("conflict_id")) or not _text(conflict.get("description")):
                rejected_aspects.append({"path": c_path, "question_id": qid, "reason": "conflict_missing_id_or_description"})
                continue
            _drop_extra(conflict, {"conflict_id", "description", "evidence"}, stage="delta", path=c_path, normalizations=normalizations)
            evidence = _evidence_rows(conflict.get("evidence"), stage="delta", path=f"{c_path}.evidence", sources=sources, normalizations=normalizations, rejected=rejected_evidence)
            if not evidence:
                rejected_aspects.append({"path": c_path, "question_id": qid, "reason": "conflict_has_no_valid_evidence"})
                continue
            conflicts.append({"conflict_id": _text(conflict.get("conflict_id")), "description": _text(conflict.get("description")), "evidence": evidence})
        if not answered and not unanswered and not conflicts and not raw_row.get("reading_sufficient"):
            rejected_updates.append({"path": path, "question_id": qid, "reason": "no_valid_interpretation_after_evidence_filter"})
            continue
        updates.append({
            "question_id": qid,
            "answered_aspects": answered,
            "unanswered_aspects": unanswered,
            "conflicts": conflicts,
            "reading_sufficient": raw_row["reading_sufficient"],
            "historical_verification_open": raw_row["historical_verification_open"],
        })
    return {"updates": updates}, {
        "normalizations": normalizations,
        "rejected_evidence": rejected_evidence,
        "rejected_claims": rejected_claims,
        "rejected_aspects": rejected_aspects,
        "rejected_updates": rejected_updates,
    }


def _claim_fingerprint(claim: str, refs: Sequence[str]) -> str:
    value = stable_json({"claim": claim, "refs": sorted(set(refs))})
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def derive_state_b(question: Mapping[str, Any], update: Mapping[str, Any]) -> dict[str, Any]:
    answered = update.get("answered_aspects", []) if isinstance(update.get("answered_aspects"), list) else []
    conflicts = update.get("conflicts", []) if isinstance(update.get("conflicts"), list) else []
    unanswered = update.get("unanswered_aspects", []) if isinstance(update.get("unanswered_aspects"), list) else []
    high = [row for row in unanswered if isinstance(row, Mapping) and row.get("reading_impact") == "high" and _text(row.get("gap"))]
    remaining_row = high[0] if high else next((row for row in unanswered if isinstance(row, Mapping) and _text(row.get("gap"))), None)
    refs = sorted({str(item.get("ref")) for aspect in answered if isinstance(aspect, Mapping) for item in aspect.get("evidence", []) if isinstance(item, Mapping)} | {str(item.get("ref")) for row in conflicts if isinstance(row, Mapping) for item in row.get("evidence", []) if isinstance(item, Mapping)})
    claim_fingerprints = []
    for aspect in answered:
        if isinstance(aspect, Mapping):
            claim_fingerprints.append(_claim_fingerprint(str(aspect.get("claim", "")), [str(item.get("ref")) for item in aspect.get("evidence", []) if isinstance(item, Mapping)]))
    conflict_fingerprints = sorted(_claim_fingerprint(str(row.get("description", "")), [str(item.get("ref")) for item in row.get("evidence", []) if isinstance(item, Mapping)]) for row in conflicts if isinstance(row, Mapping))
    sufficient = update.get("reading_sufficient") is True
    state = "conflicted" if conflicts else "substantially_explained" if sufficient else "partially_explained" if answered else "unexplained"
    terminal = "reading_sufficient" if sufficient else "not_worth_pursuing" if not high else None
    return {
        "question_id": question["question_id"],
        "parent_question_id": question.get("parent_question_id"),
        "parent_aspect_id": question.get("parent_aspect_id"),
        "story_span": question["story_span"],
        "gap": question["gap"],
        "state": state,
        "working_answer": working_answer(answered),
        "supporting_refs": refs,
        "claim_fingerprints": sorted(claim_fingerprints),
        "conflict_fingerprints": conflict_fingerprints,
        "remaining_gap": str(remaining_row.get("gap")) if isinstance(remaining_row, Mapping) else None,
        "reading_sufficient": bool(update.get("reading_sufficient")),
        "historical_verification_open": bool(update.get("historical_verification_open")),
        "next_action": "stop" if sufficient or not high else "retrieve_local",
        "terminal_reason": terminal,
        "active": not sufficient and bool(high),
        "conflict_ids": sorted(str(row.get("conflict_id")) for row in conflicts if isinstance(row, Mapping) and row.get("conflict_id")),
    }


def material_delta_b(previous: Mapping[str, Any] | None, current: Mapping[str, Any], *, used_refs: Sequence[str]) -> int:
    current_refs = set(str(ref) for ref in used_refs)
    if previous is None:
        return int(bool(current.get("claim_fingerprints") or current.get("conflict_fingerprints") or (current.get("reading_sufficient") and current_refs)))
    if current_refs and set(current.get("claim_fingerprints", [])) - set(previous.get("claim_fingerprints", [])):
        return 1
    # Working Answer is a Python projection of claims.  Compare its
    # evidence-backed semantic inputs rather than counting punctuation-only
    # wording edits as a delta.
    if current_refs and set(current.get("conflict_fingerprints", [])) != set(previous.get("conflict_fingerprints", [])):
        return 1
    if current_refs and current.get("reading_sufficient") != previous.get("reading_sufficient"):
        return 1
    if current_refs and current.get("remaining_gap") != previous.get("remaining_gap"):
        return 1
    return 0


def valid_child_b(parent: Mapping[str, Any], aspect: Mapping[str, Any], existing_ids: set[str]) -> tuple[dict[str, Any] | None, str | None]:
    aspect_id, gap = _text(aspect.get("aspect_id")), _text(aspect.get("gap"))
    if aspect.get("reading_impact") != "high" or not aspect_id or not gap:
        return None, "not_high_impact_or_empty"
    if gap == str(parent.get("gap")):
        return None, "not_a_narrowing"
    child_id = f"{parent['question_id']}.{len([value for value in existing_ids if str(value).startswith(str(parent['question_id']) + '.')]) + 1}"
    if child_id in existing_ids:
        return None, "duplicate_child_id"
    return {
        "question_id": child_id,
        "parent_question_id": parent["question_id"],
        "parent_aspect_id": aspect_id,
        "story_span": parent["story_span"],
        "gap": gap,
    }, None


def make_children_b(parent: Mapping[str, Any], update: Mapping[str, Any], existing_ids: set[str]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    children: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    for aspect in update.get("unanswered_aspects", []) if isinstance(update.get("unanswered_aspects"), list) else []:
        if len(children) >= MAX_CHILDREN_PER_UPDATE:
            rejected.append({"aspect_id": aspect.get("aspect_id") if isinstance(aspect, Mapping) else None, "reason": "child_cap"})
            continue
        child, reason = valid_child_b(parent, aspect if isinstance(aspect, Mapping) else {}, existing_ids | {row["question_id"] for row in children})
        if child is None:
            rejected.append({"aspect_id": aspect.get("aspect_id") if isinstance(aspect, Mapping) else None, "reason": reason})
            continue
        children.append(child)
    return children, rejected


def evidence_novelty_b(used_refs: Sequence[str], seen_refs: set[str]) -> tuple[float, list[str]]:
    unique = sorted(set(str(ref) for ref in used_refs))
    new = [ref for ref in unique if ref not in seen_refs]
    return (len(new) / len(unique) if unique else 0.0), new


def stop_reason_b(history: Sequence[Mapping[str, Any]], *, retrieval_attempts: int, adequate_attempts: int, evidence_round_count: int) -> str | None:
    if not history:
        return None
    last = history[-1]
    if last.get("reading_sufficient") is True:
        return "reading_sufficient"
    if len(history) >= 2 and all(row.get("D_t") == 0 and float(row.get("N_t", 0)) < 0.2 for row in history[-2:]):
        return "evidence_saturated"
    if len(history) >= 2 and history[-1].get("conflict_fingerprints") and history[-1].get("conflict_fingerprints") == history[-2].get("conflict_fingerprints") and history[-1].get("D_t") == 0:
        return "stable_conflict"
    if retrieval_attempts >= 2 and adequate_attempts == 0:
        return "unresolved_no_evidence"
    if evidence_round_count >= MAX_EVIDENCE_ROUNDS:
        return "hard_cap"
    if not last.get("active", True) and last.get("state") != "substantially_explained":
        return "not_worth_pursuing"
    return None


def review_template_b(story_ids: Sequence[str]) -> dict[str, Any]:
    return {"schema": "srm0-4b-review", "schema_version": SCHEMA_VERSION, "stories": {story_id: {"notes": ""} for story_id in FIXED_STORIES if story_id in set(story_ids)}}


def build_registry(root: Path = ROOT) -> dict[str, dict[str, Any]]:
    return build_retrieval_registry(root)


__all__ = [
    "BOUNDARY_PUNCTUATION", "COMMENTARY_SYSTEM_PROMPT", "FIXED_STORIES", "FIXTURE_SUMMARY_PATH",
    "INITIAL_SYSTEM_PROMPT", "LIVE_SUMMARY_PATH", "MAX_EVIDENCE_ROUNDS", "MODEL", "OUTPUT_BASE",
    "PROMPT_VERSION", "PROVIDER", "RETRIEVAL_SYSTEM_PROMPT", "REVIEW_PATH", "SCHEMA_VERSION",
    "SEARCHED_CORPORA", "STATUS_PATH", "TRANSPORT_FAILURE_CLASSES", "build_commentary_messages",
    "build_initial_messages", "build_registry", "classify_deepseek_exception",
    "build_retrieval_messages", "derive_state_b", "evidence_novelty_b", "fixture_version",
    "make_children_b", "material_delta_b", "normalize_delta_fail_soft", "normalize_initial_fail_soft",
    "open_candidates", "output_directory", "parse_json_any", "reset_srm0_4_results", "review_template_b",
    "run_id_for", "search_registry", "status_document", "stop_reason_b", "story_material", "write_status",
    "working_answer",
]
