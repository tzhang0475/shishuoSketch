#!/usr/bin/env python3
"""Build the HNG0.2 research-only identity/relation projection.

HNG0.2 is deliberately an offline projection of the immutable HNG0.1
candidate layer.  It never calls a model and never writes canonical history.
The punctuated Wikisource witnesses are loaded only as reference/search
material; their raw wikitext is never rewritten.
"""

from __future__ import annotations

import argparse
import collections
import datetime as dt
import hashlib
import json
import re
import sys
import time
import unicodedata
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

ROOT = Path(__file__).resolve().parents[1]
SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from hng0_1_common import (  # noqa: E402
    build_search_profiles,
    quote_matches,
    search_normalize,
    sha256_file,
    stable_hash,
    write_json,
)


OUTPUT_ROOT = ROOT / "data/generated/hng0-2"
FRONTEND_PATH = ROOT / "site/src/generated/hng0-2-site.json"
HNG01_ROOT = ROOT / "data/generated/hng0-1"
HNG0_ROOT = ROOT / "data/generated/hng0"

RELATION_INPUT = HNG01_ROOT / "candidate-relations.json"
TEMPORAL_INPUT = HNG01_ROOT / "candidate-temporal-items.json"
UNRESOLVED_INPUT = HNG01_ROOT / "unresolved-identities.json"
EVIDENCE_INPUT = HNG01_ROOT / "source-evidence-registry.json"
PROFILE_INPUT = HNG01_ROOT / "seed-search-profiles.json"
SELECTION_INPUT = HNG0_ROOT / "hng0-selection.json"

WREF1_SOURCES = {
    "jinshu-wikisource-punctuated": {
        "manifest": ROOT / "sources/downloads/jinshu/wikisource-punctuated/manifest.lock.json",
        "work": "晉書",
    },
    "zizhi-tongjian-wikisource-hu": {
        "manifest": ROOT / "sources/downloads/zizhi-tongjian/wikisource-hu/manifest.lock.json",
        "work": "資治通鑑",
    },
}

HARD_RELATIONS = {
    "parent_child",
    "grandparent_grandchild",
    "sibling",
    "uncle_nephew",
    "cousin_clan_kin",
    "marriage",
    "affinal_relation",
    "same_clan",
    "superior_subordinate",
    "recruitment_served_under",
    "teacher_student",
}
DOCUMENTED_INTERACTIONS = {
    "documented_social_interaction",
    "documented_political_interaction",
    "shared_explicit_event",
    "debate_or_disagreement",
    "recommendation_or_intercession",
    "visit_or_association",
}
INTERPRETED_RELATIONS = {
    "friendship",
    "political_cooperation",
    "political_opposition",
    "rivalry",
    "factional_alignment",
}
RELATION_LEVELS = {"hard_relation", "documented_interaction", "interpreted_relation"}
REVIEW_STATUSES = {"candidate", "accepted", "rejected", "uncertain", "needs_more_evidence"}

KINSHIP_MARKERS = ("祖", "孫", "父", "母", "子", "兄", "弟", "叔", "舅", "從兄", "從弟", "兄子")
GENERIC_SURFACES = {
    "父", "母", "子", "女", "兄", "弟", "姊", "妹", "叔", "舅", "妻", "婿", "友",
    "帝", "太子", "皇太子", "師", "帳下人", "其妻", "父母", "長子", "嗣",
}
TITLE_PREFIXES = ("元", "明", "成", "文", "武", "簡文", "康獻", "明穆", "景獻", "東海", "琅邪", "太傅", "丞相", "司徒", "大將軍", "侯", "王")

# This fold is only for lookup/ranking.  It is never applied to stored quotes.
LOOKUP_FOLD = str.maketrans({
    "寳": "寶", "宝": "寶", "彞": "彝", "彛": "彝", "温": "溫", "陆": "陸", "机": "機",
    "导": "導", "谢": "謝", "刘": "劉", "陈": "陳", "苏": "蘇", "隐": "隱", "鉴": "鑒",
    "侃": "侃", "峻": "峻", "桓": "桓", "王": "王", "庾": "庾", "陶": "陶", "郗": "郗", "郄": "郄",
    "龛": "龕", "瑾": "瑾", "铨": "銓", "瑩": "瑩", "琛": "琛", "憺": "憺", "抗": "抗",
})


def read_json(path: Path, default: Any = None) -> Any:
    if not path.is_file():
        if default is not None:
            return default
        raise FileNotFoundError(path)
    return json.loads(path.read_text(encoding="utf-8"))


def json_hash(value: Any) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def now_utc() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def lookup(value: Any) -> str:
    text = unicodedata.normalize("NFKC", str(value or "")).translate(LOOKUP_FOLD)
    return "".join(text.split())


def compact(value: Any) -> str:
    return " ".join(str(value or "").split())


def surface_values(value: Any) -> list[str]:
    if isinstance(value, Mapping):
        return sorted({compact(value.get("original")), compact(value.get("simplified"))} - {""})
    if isinstance(value, (list, tuple, set)):
        values: list[str] = []
        for item in value:
            values.extend(surface_values(item))
        return sorted(set(values))
    return [compact(value)] if compact(value) else []


def first_surname(name: str) -> str:
    chars = [c for c in str(name or "") if "\u4e00" <= c <= "\u9fff"]
    return chars[0] if chars else ""


def person_catalog() -> dict[str, dict[str, Any]]:
    people_doc = read_json(ROOT / "data/people.json", {"people": []})
    aliases_doc = read_json(ROOT / "data/aliases.json", {"aliases": []})
    aliases_by_person: dict[str, list[Mapping[str, Any]]] = collections.defaultdict(list)
    for row in aliases_doc.get("aliases", []):
        if not isinstance(row, Mapping):
            continue
        for pid in row.get("person_ids", []) if isinstance(row.get("person_ids"), list) else []:
            aliases_by_person[str(pid)].append(row)

    catalog: dict[str, dict[str, Any]] = {}
    for raw in people_doc.get("people", []):
        if not isinstance(raw, Mapping) or not raw.get("person_id"):
            continue
        pid = str(raw["person_id"])
        canonical = compact(raw.get("canonical_name") or raw.get("name"))
        canonical_forms = set(surface_values(canonical))
        courtesy_forms = set(surface_values(raw.get("courtesy_name") or raw.get("zi")))
        alias_forms = set(surface_values(raw.get("aliases")))
        forms: set[str] = canonical_forms | courtesy_forms | alias_forms
        office: set[str] = set()
        for alias in aliases_by_person.get(pid, []):
            values = surface_values(alias.get("surface") or alias.get("name"))
            forms.update(values)
            if "title" in str(alias.get("alias_type") or "") or "office" in str(alias.get("alias_type") or "") or "contextual" in str(alias.get("alias_type") or ""):
                office.update(values)
            elif "courtesy" in str(alias.get("alias_type") or ""):
                courtesy_forms.update(values)
            else:
                alias_forms.update(values)
        clan = raw.get("clan")
        clan_name = ""
        if isinstance(clan, Mapping):
            clan_name = compact(clan.get("canonical_name") or clan.get("name"))
            forms.update(surface_values(clan_name))
        catalog[pid] = {
            "person_id": pid,
            "canonical_name": canonical,
            "forms": sorted({x for x in forms if x}),
            "canonical_forms": sorted(canonical_forms),
            "courtesy_forms": sorted(courtesy_forms),
            "alias_forms": sorted(alias_forms),
            "office_titles": sorted(office),
            "surname": first_surname(canonical),
            "review_status": raw.get("review_status"),
        }
    return catalog


def forms_index(catalog: Mapping[str, Mapping[str, Any]]) -> dict[str, list[str]]:
    index: dict[str, list[str]] = collections.defaultdict(list)
    for pid, person in sorted(catalog.items()):
        for form in person.get("forms", []):
            key = lookup(form)
            if key:
                index[key].append(pid)
    return {key: sorted(set(value)) for key, value in index.items()}


def load_hng_inputs() -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, dict[str, Any]], dict[str, Any]]:
    rel_doc = read_json(RELATION_INPUT)
    time_doc = read_json(TEMPORAL_INPUT)
    unresolved_doc = read_json(UNRESOLVED_INPUT)
    evidence = dict(rel_doc.get("evidence", {}))
    evidence.update(time_doc.get("evidence", {}))
    return list(rel_doc.get("relations", [])), list(time_doc.get("temporal_items", [])), evidence, unresolved_doc


def evidence_context(candidate: Mapping[str, Any], evidence: Mapping[str, Mapping[str, Any]]) -> tuple[str, list[str], list[dict[str, Any]]]:
    refs = [str(ref) for ref in candidate.get("evidence_refs", []) if ref]
    if not refs:
        refs = [str(item.get("ref")) for item in candidate.get("evidence_quotes", []) if item.get("ref")]
    passages: list[str] = []
    records: list[dict[str, Any]] = []
    for ref in sorted(set(refs)):
        row = evidence.get(ref, {})
        if not isinstance(row, Mapping):
            continue
        text = str(row.get("original_text") or "")
        if text:
            passages.append(text)
        records.append({
            "evidence_ref": ref,
            "source_work": row.get("source_work"),
            "source_layer": row.get("source_layer"),
            "source_path": row.get("source_path"),
            "source_sha256": row.get("source_sha256"),
            "locator": row.get("locator", {}),
            "original_text": text,
        })
    return "\n".join(passages), refs, records


def provisional_id(label: str) -> str:
    return f"hng02-provisional-{stable_hash({'label': label})[:20]}"


def label_from_surface(surface: str, candidate: Mapping[str, Any], seed: Mapping[str, Any], context: str) -> tuple[str, str] | None:
    """Return (label, method hint) only when the surface has enough structure."""

    raw = compact(surface)
    if not raw or raw in GENERIC_SURFACES:
        return None
    # Role prefixes are source surfaces, not part of the person's name.
    for prefix in ("妻", "母", "父", "子", "兄", "弟", "女", "長子"):
        if raw.startswith(prefix) and len(raw) > len(prefix):
            raw = raw[len(prefix):]
            break
    if not raw or raw in GENERIC_SURFACES:
        return None
    old_type = str(candidate.get("relation_type") or candidate.get("temporal_type") or "")
    quote_text = "".join(str(x.get("quote") or "") for x in candidate.get("evidence_quotes", []) if isinstance(x, Mapping))
    kinship = old_type in HARD_RELATIONS or any(marker in quote_text for marker in KINSHIP_MARKERS)
    # A one-character kinship name is often recorded without its family name.
    if len(raw) == 1 and kinship:
        surname = first_surname(str(seed.get("canonical_name") or ""))
        if surname and raw not in GENERIC_SURFACES:
            return surname + raw, "kinship_context"
    # Full named/title surfaces are useful HNG-only nodes even if canonical
    # identity data does not yet contain that person.
    if len(raw) >= 2:
        return raw, "title" if raw.startswith(TITLE_PREFIXES) else "biography_local_context"
    # A one-character surface can be a current seed's abbreviated name.
    seed_name = lookup(seed.get("canonical_name"))
    if seed_name and seed_name.endswith(lookup(raw)):
        return str(seed.get("canonical_name")), "seed_coreference"
    return None


def exact_resolution_method(person: Mapping[str, Any], surface: str) -> str:
    """Name the deterministic catalogue match without changing its identity."""

    key = lookup(surface)
    if key in {lookup(value) for value in person.get("canonical_forms", [])}:
        return "exact_name"
    if key in {lookup(value) for value in person.get("courtesy_forms", [])}:
        return "courtesy_name"
    if key in {lookup(value) for value in person.get("office_titles", [])}:
        return "title"
    if key in {lookup(value) for value in person.get("alias_forms", [])}:
        return "alias"
    return "exact_name"


def resolve_identity(
    *,
    surface: str,
    seed: Mapping[str, Any],
    candidate: Mapping[str, Any],
    context: str,
    evidence_records: Sequence[Mapping[str, Any]],
    catalog: Mapping[str, Mapping[str, Any]],
    exact_index: Mapping[str, Sequence[str]],
) -> dict[str, Any]:
    raw = compact(surface)
    refs = [str(row.get("evidence_ref")) for row in evidence_records if row.get("evidence_ref")]
    title_values = [compact(row.get("locator", {}).get("title")) for row in evidence_records if isinstance(row.get("locator"), Mapping)]
    title_values = [x for x in title_values if x]
    context_lookup = lookup(context)
    direct_context_lookup = lookup(" ".join([
        str(candidate.get("claim") or ""),
        *[str(item.get("quote") or "") for item in candidate.get("evidence_quotes", []) if isinstance(item, Mapping)],
    ]))

    def result(status: str, method: str, *, pid: str | None = None, provisional: str | None = None, label: str | None = None, matches: Sequence[str] = (), confidence: str = "low", note: str = "") -> dict[str, Any]:
        return {
            "surface": raw,
            "resolved_person_id": pid,
            "provisional_person_id": provisional,
            "resolved_label": label,
            "resolution_status": status,
            "resolution_method": method,
            "supporting_evidence_refs": sorted(set(refs)),
            "supporting_passage": str(candidate.get("evidence_quotes", [{}])[0].get("quote") or "") if candidate.get("evidence_quotes") else context[:500],
            "confidence": confidence,
            "matches": sorted(set(matches)),
            "note": note,
        }

    if not raw:
        return result("unresolved_identity", "unresolved", confidence="low", note="empty surface")

    # Contextual compound names take precedence over a bare ambiguous courtesy
    # name.  This captures e.g. 陶士衡 in the current Shishuo passage without
    # changing the global 士衡→陸機 alias record.
    compound_matches: list[str] = []
    for pid, person in sorted(catalog.items()):
        surname = str(person.get("surname") or "")
        if surname and lookup(surname + raw) in direct_context_lookup:
            compound_matches.append(pid)
    if len(compound_matches) == 1:
        pid = compound_matches[0]
        return result("resolved_existing_person", "biography_local_context", pid=pid, label=catalog[pid].get("canonical_name"), matches=[pid], confidence="medium", note="contextual compound surface")

    exact = list(exact_index.get(lookup(raw), []))
    if len(exact) == 1:
        pid = exact[0]
        return result("resolved_existing_person", exact_resolution_method(catalog[pid], raw), pid=pid, label=catalog[pid].get("canonical_name"), matches=exact, confidence="high")
    if len(exact) > 1:
        # Biography heading and a full name in the passage can disambiguate a
        # shared courtesy name; otherwise preserve the ambiguity.
        contextual: list[str] = []
        for pid in exact:
            person = catalog[pid]
            if any(lookup(form) in context_lookup for form in person.get("forms", []) if len(lookup(form)) > len(lookup(raw))):
                contextual.append(pid)
        if len(contextual) == 1:
            pid = contextual[0]
            return result("resolved_existing_person", "biography_local_context", pid=pid, label=catalog[pid].get("canonical_name"), matches=contextual, confidence="high")
        return result("ambiguous_identity", "ambiguous", matches=exact, confidence="low", note="multiple canonical alias matches")

    # A biography title is a strong local-context signal for abbreviated
    # names such as 鑒 in a 郄鑒 biography.
    title_candidates: list[str] = []
    for title in title_values:
        for pid, person in sorted(catalog.items()):
            if lookup(title) == lookup(person.get("canonical_name")) or lookup(title) in {lookup(x) for x in person.get("forms", [])}:
                if lookup(title).endswith(lookup(raw)) or lookup(raw) == lookup(title):
                    title_candidates.append(pid)
    if len(set(title_candidates)) == 1:
        pid = sorted(set(title_candidates))[0]
        return result("resolved_existing_person", "biography_local_context", pid=pid, label=catalog[pid].get("canonical_name"), matches=[pid], confidence="high", note="biography title context")

    structured = label_from_surface(raw, candidate, seed, context)
    if structured:
        label, hint = structured
        # If the derived full label is already in the catalogue, use that
        # canonical identity; otherwise keep a provisional HNG-only node.
        derived = list(exact_index.get(lookup(label), []))
        if len(derived) == 1:
            pid = derived[0]
            return result("resolved_existing_person", hint, pid=pid, label=catalog[pid].get("canonical_name"), matches=derived, confidence="medium")
        return result("resolved_provisional_person", hint, provisional=provisional_id(label), label=label, confidence="medium", note="HNG-only provisional identity; no canonical Person created")
    return result("unresolved_identity", "unresolved", confidence="low", note="insufficient contextual identity")


def resolution_for_candidate(
    candidate: Mapping[str, Any],
    *,
    seed_profiles: Mapping[str, Mapping[str, Any]],
    evidence: Mapping[str, Mapping[str, Any]],
    catalog: Mapping[str, Mapping[str, Any]],
    exact_index: Mapping[str, Sequence[str]],
    surface_key: str,
) -> dict[str, Any]:
    seed_id = str(candidate.get("person_a") or candidate.get("person_id") or candidate.get("seed_person_id") or "")
    seed = seed_profiles.get(seed_id, catalog.get(seed_id, {"person_id": seed_id, "canonical_name": seed_id}))
    context, refs, records = evidence_context(candidate, evidence)
    # Include the candidate's claim and exact quotes in the local context; this
    # is frozen HNG0.1 evidence metadata, not new model interpretation.
    context = "\n".join([context, str(candidate.get("claim") or ""), *[str(x.get("quote") or "") for x in candidate.get("evidence_quotes", []) if isinstance(x, Mapping)]])
    surface = str(candidate.get(surface_key) or "")
    resolution = resolve_identity(surface=surface, seed=seed, candidate=candidate, context=context, evidence_records=records, catalog=catalog, exact_index=exact_index)
    resolution["candidate_id"] = str(candidate.get("relation_id") or candidate.get("temporal_id") or "")
    resolution["candidate_kind"] = "relation" if "relation_type" in candidate else "temporal"
    resolution["seed_person_id"] = seed_id
    resolution["evidence_refs"] = refs
    return resolution


def relation_level_and_type(row: Mapping[str, Any], evidence_text: str) -> tuple[str, str, str]:
    original = str(row.get("relation_type") or "")
    q = lookup(evidence_text)
    if original in HARD_RELATIONS:
        normalized = original
        # HNG0.1 used same_clan as a fallback for explicit 祖/孫 statements.
        if original == "same_clan" and any(marker in q for marker in ("祖", "孫", "祖父", "孫也", "世孫")):
            normalized = "grandparent_grandchild"
        return "hard_relation", normalized, "kinship_ontology_repair" if normalized != original else "preserved_hard_relation"
    if original == "shared_explicit_event":
        return "documented_interaction", "shared_explicit_event", "documented_episode"
    if original == "explicit_friendship_association":
        # Explicit source language can remain an interpreted relation, but it
        # remains candidate-only and historical_verification_open.
        if any(marker in q for marker in ("相親善", "親善", "友善", "相善")):
            return "interpreted_relation", "friendship", "explicit_source_friendship"
        return "documented_interaction", "documented_social_interaction", "weak_friendship_reclassified"
    if original == "explicit_political_cooperation_opposition":
        return "documented_interaction", "documented_political_interaction", "single_passage_political_interaction"
    if original in DOCUMENTED_INTERACTIONS:
        return "documented_interaction", original, "preserved_documented_interaction"
    if original in INTERPRETED_RELATIONS:
        return "interpreted_relation", original, "preserved_interpreted_relation"
    return "documented_interaction", "documented_social_interaction", "unknown_type_conservatively_downgraded"


def merge_evidence(target: dict[str, Any], row: Mapping[str, Any]) -> None:
    refs = set(target.get("evidence_refs", [])) | set(row.get("evidence_refs", []))
    target["evidence_refs"] = sorted(str(x) for x in refs if x)
    quotes = {(str(x.get("ref")), str(x.get("quote"))) for x in target.get("evidence_quotes", []) if isinstance(x, Mapping)}
    quotes.update((str(x.get("ref")), str(x.get("quote"))) for x in row.get("evidence_quotes", []) if isinstance(x, Mapping))
    target["evidence_quotes"] = [{"ref": ref, "quote": quote} for ref, quote in sorted(quotes)]
    target["source_works"] = sorted(set(target.get("source_works", [])) | set(row.get("source_works", [])))
    target["source_forms"] = sorted(set(target.get("source_forms", [])) | set(row.get("source_forms", [])))
    target["candidate_ids"] = sorted(set(target.get("candidate_ids", [])) | set(row.get("candidate_ids", [])))
    variants = list(target.get("claim_variants", []))
    for claim in [target.get("claim"), row.get("claim")]:
        if claim and claim not in variants:
            variants.append(claim)
    if len(variants) > 1:
        target["claim_variants"] = sorted(set(variants))
    if row.get("claim") and row.get("claim") != target.get("claim"):
        conflicts = list(target.get("conflicts", []))
        item = {"claim": row.get("claim"), "evidence_refs": row.get("evidence_refs", [])}
        if item not in conflicts:
            conflicts.append(item)
        target["conflicts"] = conflicts


def normalize_relations(
    rows: Sequence[Mapping[str, Any]],
    *,
    resolutions: Mapping[str, Mapping[str, Any]],
    evidence: Mapping[str, Mapping[str, Any]],
    catalog: Mapping[str, Mapping[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    merged: dict[tuple[str, str, str, str], dict[str, Any]] = {}
    rejected: list[dict[str, Any]] = []
    for raw in rows:
        rid = str(raw.get("relation_id") or "")
        identity = resolutions.get(rid, {})
        seed_id = str(raw.get("person_a") or "")
        counterpart = identity.get("resolved_person_id")
        provisional = identity.get("provisional_person_id")
        original_provisional = str(raw.get("provisional_neighbor_id") or "") or None
        if not counterpart:
            # Keep unresolved neighbors inside the HNG0.2 namespace.  The
            # HNG0.1 provisional ID is retained only as trace metadata; it is
            # not a canonical identity and must not leak into the new graph.
            provisional = provisional or provisional_id(str(identity.get("resolved_label") or raw.get("counterpart_surface") or "unresolved"))
        if counterpart and counterpart == seed_id:
            rejected.append({"candidate_id": rid, "reason": "self_relation_after_identity_resolution"})
            continue
        b_key = str(counterpart or provisional or f"unresolved:{raw.get('counterpart_surface')}")
        direction = raw.get("direction") if isinstance(raw.get("direction"), Mapping) else {"kind": "undirected"}
        kind = str(direction.get("kind") or "undirected")
        # Relation normalization is driven by the frozen candidate evidence,
        # not by an unrelated marker elsewhere in a whole biography.  Using
        # the exact quoted passages keeps an explicit friendship marker from
        # leaking across distinct episodes in the same source unit.
        evidence_text = "\n".join(
            str(item.get("quote") or "")
            for item in raw.get("evidence_quotes", [])
            if isinstance(item, Mapping)
        )
        level, normalized_type, normalization_reason = relation_level_and_type(raw, evidence_text)
        key = (seed_id, b_key, normalized_type, kind)
        source_forms = ["legacy_local"]
        row = {
            "relation_id": f"hng02-relation-{stable_hash(key)[:20]}",
            "person_a": seed_id or None,
            "person_b": counterpart,
            "person_a_name": catalog.get(seed_id, {}).get("canonical_name") or raw.get("person_a_name"),
            "person_b_name": catalog.get(str(counterpart), {}).get("canonical_name") if counterpart else None,
            "counterpart_surface": raw.get("counterpart_surface"),
            "provisional_neighbor_id": provisional,
            "provisional_neighbor_label": (identity.get("resolved_label") or raw.get("counterpart_surface")) if provisional else None,
            "original_provisional_neighbor_id": original_provisional,
            "resolution_status": identity.get("resolution_status") or raw.get("resolution_status"),
            "resolution_matches": identity.get("matches", raw.get("resolution_matches", [])),
            "identity_resolution": identity,
            "relation_type": normalized_type,
            "normalized_relation_type": normalized_type,
            "original_relation_type": raw.get("relation_type"),
            "semantic_level": level,
            "direction": {"kind": kind, "from": seed_id if kind == "seed_to_counterpart" else (counterpart or provisional) if kind == "counterpart_to_seed" else None, "to": (counterpart or provisional) if kind == "seed_to_counterpart" else seed_id if kind == "counterpart_to_seed" else None},
            "temporal_scope": raw.get("temporal_scope", {}),
            "certainty": raw.get("certainty") or "low",
            "ambiguity": raw.get("ambiguity") or "",
            "historical_verification_open": True,
            "claim": raw.get("claim") or "",
            "evidence_refs": sorted(set(raw.get("evidence_refs", []))),
            "evidence_quotes": raw.get("evidence_quotes", []),
            "source_works": sorted(set(raw.get("source_works", []))),
            "source_forms": source_forms,
            "extraction_method": raw.get("extraction_method") or "hng0-1-frozen-candidate",
            "normalization_reason": normalization_reason,
            "review_status": "candidate",
            "source_review_status": raw.get("source_review_status") or "candidate_model_output",
            "origin": "hng0-1-frozen-candidate",
            "one_hop_only": True,
            "temporal_warnings": raw.get("temporal_warnings", []),
            "candidate_ids": [rid],
        }
        if key not in merged:
            merged[key] = row
        else:
            merge_evidence(merged[key], row)
    return sorted(merged.values(), key=lambda x: x["relation_id"]), rejected


def normalize_temporal(
    rows: Sequence[Mapping[str, Any]],
    *,
    resolutions: Mapping[str, Mapping[str, Any]],
    catalog: Mapping[str, Mapping[str, Any]],
) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for raw in rows:
        tid = str(raw.get("temporal_id") or "")
        identity = resolutions.get(tid, {})
        pid = identity.get("resolved_person_id")
        provisional = identity.get("provisional_person_id")
        if not pid and not provisional and raw.get("person_id"):
            pid = str(raw.get("person_id"))
        if not pid and not provisional:
            provisional = provisional_id(str(identity.get("resolved_label") or raw.get("subject_surface") or "unresolved"))
        key = (str(pid or provisional or raw.get("subject_surface") or ""), str(raw.get("temporal_type") or ""), json_hash(raw.get("temporal_scope", {}))[:10], str(raw.get("claim") or ""))
        row = {
            "temporal_id": f"hng02-time-{stable_hash(key)[:20]}",
            "person_id": pid,
            "provisional_subject_id": provisional,
            "subject_surface": raw.get("subject_surface"),
            "subject_label": identity.get("resolved_label") or catalog.get(str(pid), {}).get("canonical_name"),
            "subject_resolution_status": identity.get("resolution_status") or raw.get("subject_resolution_status"),
            "subject_matches": identity.get("matches", raw.get("subject_matches", [])),
            "identity_resolution": identity,
            "temporal_type": raw.get("temporal_type"),
            "claim": raw.get("claim") or "",
            "temporal_scope": raw.get("temporal_scope", {}),
            "precision": raw.get("precision") or "unknown",
            "certainty": raw.get("certainty") or "low",
            "ambiguity": raw.get("ambiguity") or "",
            "historical_verification_open": True,
            "evidence_refs": sorted(set(raw.get("evidence_refs", []))),
            "evidence_quotes": raw.get("evidence_quotes", []),
            "source_works": sorted(set(raw.get("source_works", []))),
            "source_forms": ["legacy_local"],
            "extraction_method": raw.get("extraction_method") or "hng0-1-frozen-candidate",
            "review_status": "candidate",
            "source_review_status": raw.get("source_review_status") or "candidate_model_output",
            "origin": "hng0-1-frozen-candidate",
            "temporal_warnings": raw.get("temporal_warnings", []),
            "candidate_ids": [tid],
        }
        result.append(row)
    # Same temporal claim may occur twice in the frozen candidate layer.
    unique: dict[str, dict[str, Any]] = {}
    for row in result:
        key = json_hash({k: row.get(k) for k in ("person_id", "provisional_subject_id", "temporal_type", "claim", "temporal_scope")})
        if key not in unique:
            unique[key] = row
        else:
            merge_evidence(unique[key], row)
    return sorted(unique.values(), key=lambda x: x["temporal_id"])


def source_unit(source_ref: str, work: str, text: str, path: str, *, source_form: str, locator: Mapping[str, Any], source_sha256: str | None = None, metadata: Mapping[str, Any] | None = None) -> dict[str, Any] | None:
    if not text:
        return None
    row: dict[str, Any] = {
        "source_ref": source_ref,
        "work": work,
        "source_layer": "reference_text",
        "text": text,
        "source_path": path,
        "source_sha256": source_sha256,
        "source_form": source_form,
        "locator": dict(locator),
    }
    if metadata:
        row.update(dict(metadata))
    return row


def load_punctuated_units() -> list[dict[str, Any]]:
    units: list[dict[str, Any]] = []
    for witness_id, config in WREF1_SOURCES.items():
        manifest_path = config["manifest"]
        manifest = read_json(manifest_path)
        for record in sorted(manifest.get("records", []), key=lambda x: int(x.get("global_juan", 0))):
            path = ROOT / str(record.get("source_path"))
            if not path.is_file():
                raise FileNotFoundError(f"locked WREF1 payload missing: {path}")
            text = path.read_text(encoding="utf-8")
            row = source_unit(
                f"hng02-{witness_id}-{int(record['global_juan']):03d}",
                str(config["work"]),
                text,
                str(record["source_path"]),
                source_form="punctuated",
                source_sha256=str(record.get("source_sha256") or sha256_file(path)),
                locator={"global_juan": record.get("global_juan"), "page_title": record.get("page_title"), "witness_id": witness_id, "revision_id": record.get("revision_id")},
                metadata={"source_witness": witness_id, "source_url": record.get("source_url"), "revision_id": record.get("revision_id"), "revision_timestamp": record.get("revision_timestamp")},
            )
            if row:
                units.append(row)
    return units


def load_legacy_units(evidence: Mapping[str, Mapping[str, Any]]) -> list[dict[str, Any]]:
    units: list[dict[str, Any]] = []
    seen: set[str] = set()
    for ref, row in sorted(evidence.items()):
        text = str(row.get("original_text") or "")
        if not text:
            continue
        unit = source_unit(ref, str(row.get("source_work") or ""), text, str(row.get("source_path") or ""), source_form="legacy_local", source_sha256=row.get("source_sha256"), locator=row.get("locator", {}), metadata={"source_witness": ((row.get("source_provenance") or {}).get("witness_id") if isinstance(row.get("source_provenance"), Mapping) else None)})
        if unit and ref not in seen:
            units.append(unit)
            seen.add(ref)
    # The canonical punctuated Shishuo projection is a local reference source,
    # and is useful for the controlled comparison without importing generated
    # HNG text.
    try:
        from hng0_1_common import _load_shishuo_units  # type: ignore
        for row in _load_shishuo_units(ROOT):
            ref = str(row.get("source_ref"))
            if ref in seen:
                continue
            units.append({**row, "source_form": "punctuated", "source_witness": "shishuo-canonical-punctuated"})
            seen.add(ref)
    except Exception:
        # HNG0.2 can still build the candidate projection if the optional
        # Shishuo source inventory is incomplete; the validator reports it.
        pass
    return sorted(units, key=lambda x: str(x["source_ref"]))


def term_list(profile: Mapping[str, Any]) -> list[str]:
    terms: set[str] = set()
    for value in [*profile.get("search_terms_original", []), profile.get("canonical_name")]:
        text = compact(value)
        if not text or "{" in text or len(lookup(text)) < 2:
            continue
        terms.add(text)
    return sorted(terms, key=lambda x: (-len(lookup(x)), lookup(x), x))


def find_units(profile: Mapping[str, Any], units: Sequence[Mapping[str, Any]], *, punctuated_first: bool, top_k: int = 8) -> list[dict[str, Any]]:
    terms = term_list(profile)
    scored: list[dict[str, Any]] = []
    for unit in units:
        text = str(unit.get("text") or "")
        folded = lookup(text)
        hits = sorted({term for term in terms if lookup(term) in folded}, key=lambda x: (-len(lookup(x)), x))
        if not hits:
            continue
        exact_name = lookup(str(profile.get("canonical_name") or "")) in folded
        relation_hits = sum(1 for term in ("父", "子", "祖", "孫", "友善", "親善", "辟", "引", "討", "攻", "謀", "舉兵") if term in text)
        score = len(hits) * 10 + (35 if exact_name else 0) + min(relation_hits, 8) * 2
        if unit.get("source_form") == "punctuated" and punctuated_first:
            score += 20
        if unit.get("work") == "晉書" and "biography" in str(unit.get("locator", {}).get("category") or ""):
            score += 8
        scored.append({
            "source_ref": unit.get("source_ref"),
            "work": unit.get("work"),
            "source_layer": unit.get("source_layer"),
            "source_form": unit.get("source_form"),
            "locator": unit.get("locator", {}),
            "matched_terms": hits,
            "score": score,
            "text_chars": len(text),
        })
    # Mark a hit as both when the same work has a hit in both local forms.
    forms_by_work_term: dict[tuple[str, str], set[str]] = collections.defaultdict(set)
    for row in scored:
        for term in row["matched_terms"]:
            forms_by_work_term[(str(row.get("work")), lookup(term))].add(str(row.get("source_form")))
    for row in scored:
        forms = set().union(*(forms_by_work_term[(str(row.get("work")), lookup(term))] for term in row["matched_terms"]))
        if {"punctuated", "legacy_local"}.issubset(forms):
            row["source_form"] = "both"
    scored.sort(key=lambda x: (-int(x["score"]), 0 if x.get("source_form") in {"punctuated", "both"} and punctuated_first else 1, str(x.get("work")), str(x.get("source_ref"))))
    return scored[: max(1, min(8, int(top_k)))]


def sentence_segments(text: str) -> list[tuple[int, int]]:
    if not text:
        return []
    boundaries = [m.end() for m in re.finditer(r"[。！？；]\s*|\n{2,}", text)]
    segments: list[tuple[int, int]] = []
    start = 0
    for end in boundaries:
        if end > start:
            segments.append((start, end))
            start = end
    if start < len(text):
        segments.append((start, len(text)))
    return segments or [(0, len(text))]


def open_hit(hit: Mapping[str, Any], units_by_ref: Mapping[str, Mapping[str, Any]], *, short: bool) -> dict[str, Any] | None:
    ref = str(hit.get("source_ref") or "")
    unit = units_by_ref.get(ref)
    if not unit:
        return None
    text = str(unit.get("text") or "")
    folded = lookup(text)
    centers: list[int] = []
    for term in hit.get("matched_terms", []):
        index = folded.find(lookup(term))
        if index >= 0:
            # lookup folding removes spaces, so raw character centering is
            # intentionally approximate and only used to choose a window.
            centers.append(min(len(text) - 1, index))
    center = min(centers) if centers else 0
    if short:
        segments = sentence_segments(text)
        containing = next((i for i, (a, b) in enumerate(segments) if a <= center < b), 0)
        lo = max(0, containing - 1)
        hi = min(len(segments), containing + 3)
        while hi > lo + 1 and sum(segments[i][1] - segments[i][0] for i in range(lo, hi)) > 520:
            lo += 1
        start, end = segments[lo][0], segments[hi - 1][1]
        # Wikisource reference pages sometimes contain one very long
        # unpunctuated paragraph.  Keep the window local to the match even
        # when no sentence boundary can safely reduce it.
        if end - start > 520:
            start = max(0, center - 260)
            end = min(len(text), start + 520)
            start = max(0, end - 520)
        snippet = text[start:end]
    else:
        width = 1400
        start = max(0, center - width // 2)
        end = min(len(text), start + width)
        snippet = text[start:end]
    return {
        "source_ref": ref,
        "work": unit.get("work"),
        "source_layer": unit.get("source_layer"),
        "source_form": hit.get("source_form") or unit.get("source_form"),
        "locator": unit.get("locator", {}),
        "snippet": snippet,
        "snippet_chars": len(snippet),
        "window_start": start,
        "window_end": end,
        "matched_terms": hit.get("matched_terms", []),
        "score": hit.get("score", 0),
    }


def run_retrieval_comparison(profiles: Mapping[str, Mapping[str, Any]], evidence: Mapping[str, Mapping[str, Any]], punctuated: Sequence[Mapping[str, Any]], legacy: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    seed_ids = sorted(profiles, key=lambda pid: (stable_hash({"seed": pid}), pid))[:6]
    report: dict[str, Any] = {
        "schema": 1,
        "stage": "hng0-2-retrieval-comparison",
        "execution_kind": "offline_deterministic",
        "model_calls": 0,
        "comparison_seed_ids": seed_ids,
        "modes": {},
        "canonical_write_back": False,
    }
    for mode in ("legacy", "punctuated_first"):
        units = legacy if mode == "legacy" else [*punctuated, *legacy]
        unit_map = {str(x["source_ref"]): x for x in units}
        per_seed: list[dict[str, Any]] = []
        all_opened_chars: list[int] = []
        all_refs: list[str] = []
        form_counts: collections.Counter[str] = collections.Counter()
        for pid in seed_ids:
            hits = find_units(profiles[pid], units, punctuated_first=mode == "punctuated_first", top_k=8)
            opened = [open_hit(hit, unit_map, short=mode == "punctuated_first") for hit in hits]
            opened = [x for x in opened if x]
            all_refs.extend(str(x["source_ref"]) for x in opened)
            all_opened_chars.extend(int(x["snippet_chars"]) for x in opened)
            form_counts.update(str(x.get("source_form")) for x in opened)
            per_seed.append({
                "person_id": pid,
                "retrieved_count": len(hits),
                "opened_count": len(opened),
                "opened_refs": [x["source_ref"] for x in opened],
                "opened_chars": [x["snippet_chars"] for x in opened],
                "source_forms": dict(sorted(collections.Counter(str(x.get("source_form")) for x in opened).items())),
                "used_evidence_count": len(opened),
                "prompt_tokens": 0,
                "completion_tokens": 0,
            })
        report["modes"][mode] = {
            "seed_count": len(seed_ids),
            "per_seed": per_seed,
            "retrieved_passages": sum(x["retrieved_count"] for x in per_seed),
            "opened_passages": len(all_refs),
            "used_evidence_refs": sorted(set(all_refs)),
            "source_form_counts": dict(sorted(form_counts.items())),
            "average_open_chars": round(sum(all_opened_chars) / len(all_opened_chars), 2) if all_opened_chars else 0,
            "median_open_chars": sorted(all_opened_chars)[len(all_opened_chars) // 2] if all_opened_chars else 0,
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "api_calls": 0,
            # This is an offline deterministic comparison.  Do not persist
            # wall-clock noise into a build artifact that must be replayable.
            "elapsed_seconds": 0.0,
        }
    old = report["modes"]["legacy"]
    new = report["modes"]["punctuated_first"]
    report["delta"] = {
        "open_chars_change": round(float(new["average_open_chars"]) - float(old["average_open_chars"]), 2),
        "open_chars_reduction_percent": round((1 - float(new["average_open_chars"]) / float(old["average_open_chars"])) * 100, 2) if old["average_open_chars"] else 0,
        "evidence_use_rate_change": 0,
        "prompt_token_change": 0,
        "latency_change_seconds": 0.0,
    }
    return report


def build_evidence_projection(evidence: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    projected: dict[str, Any] = {}
    for ref, row in sorted(evidence.items()):
        projected[ref] = {
            "evidence_ref": ref,
            "source_work": row.get("source_work"),
            "source_layer": row.get("source_layer"),
            "original_text": row.get("original_text", ""),
            "model_snippet": row.get("model_snippet", ""),
            "locator": row.get("locator", {}),
            "source_path": row.get("source_path"),
            "source_sha256": row.get("source_sha256"),
            "source_form": "legacy_local",
        }
    return projected


def build_frontend_bundle(relations: Sequence[Mapping[str, Any]], temporal: Sequence[Mapping[str, Any]], evidence: Mapping[str, Any], profiles: Mapping[str, Mapping[str, Any]], metrics: Mapping[str, Any], manifest: Mapping[str, Any]) -> dict[str, Any]:
    people: dict[str, dict[str, Any]] = {}
    for pid in sorted(profiles):
        people[pid] = {
            "person_id": pid,
            "canonical_name": profiles[pid].get("canonical_name"),
            "normalized_relations": [],
            "normalized_temporal_items": [],
            "nearby_person_ids": [],
        }
    for row in relations:
        pid = str(row.get("person_a") or "")
        if pid in people:
            people[pid]["normalized_relations"].append(row)
        for other in (row.get("person_b"),):
            if other and pid in people and other not in people[pid]["nearby_person_ids"]:
                people[pid]["nearby_person_ids"].append(other)
    for row in temporal:
        pid = str(row.get("person_id") or "")
        if pid in people:
            people[pid]["normalized_temporal_items"].append(row)
    for person in people.values():
        person["normalized_relations"].sort(key=lambda x: str(x.get("relation_id")))
        person["normalized_temporal_items"].sort(key=lambda x: str(x.get("temporal_id")))
        person["nearby_person_ids"].sort()
    return {
        "schema": 1,
        "stage": "hng0-2-frontend-review",
        "canonical_write_back": False,
        "execution_kind": manifest.get("execution_kind"),
        "source_label": "Newly normalized",
        "people": people,
        "relations": list(relations),
        "temporal_items": list(temporal),
        "evidence": dict(evidence),
        "profiles": dict(profiles),
        "metrics": dict(metrics),
        "review_storage": "localStorage:shishuoSketch.hng0-2-review",
    }


def build() -> dict[str, Any]:
    relations, temporal, evidence, unresolved_doc = load_hng_inputs()
    catalog = person_catalog()
    exact_index = forms_index(catalog)
    profiles = build_search_profiles(ROOT)
    # Keep the frozen HNG0.1 profile identity fields but use robust canonical
    # catalog forms for resolution.
    for pid, profile in profiles.items():
        if pid in catalog:
            profile["canonical_name"] = catalog[pid].get("canonical_name") or profile.get("canonical_name")

    resolution_rows: list[dict[str, Any]] = []
    resolution_map: dict[str, dict[str, Any]] = {}
    for row in relations:
        rid = str(row.get("relation_id") or "")
        res = resolution_for_candidate(row, seed_profiles=profiles, evidence=evidence, catalog=catalog, exact_index=exact_index, surface_key="counterpart_surface")
        resolution_rows.append(res)
        resolution_map[rid] = res
    for row in temporal:
        tid = str(row.get("temporal_id") or "")
        res = resolution_for_candidate(row, seed_profiles=profiles, evidence=evidence, catalog=catalog, exact_index=exact_index, surface_key="subject_surface")
        resolution_rows.append(res)
        resolution_map[tid] = res

    normalized_relations, rejected_relations = normalize_relations(relations, resolutions=resolution_map, evidence=evidence, catalog=catalog)
    normalized_temporal = normalize_temporal(temporal, resolutions=resolution_map, catalog=catalog)

    unresolved_items: list[dict[str, Any]] = []
    seen_unresolved: set[tuple[str, str, str]] = set()
    for res in resolution_rows:
        if res.get("resolution_status") in {"unresolved_identity", "ambiguous_identity"}:
            key = (str(res.get("seed_person_id")), str(res.get("surface")), str(res.get("resolution_status")))
            if key in seen_unresolved:
                continue
            seen_unresolved.add(key)
            unresolved_items.append(res)

    punctuated_units = load_punctuated_units()
    legacy_units = load_legacy_units(evidence)
    retrieval_comparison = run_retrieval_comparison(profiles, evidence, punctuated_units, legacy_units)

    relation_counts = collections.Counter((str(x.get("semantic_level")), str(x.get("normalized_relation_type"))) for x in normalized_relations)
    level_counts = collections.Counter(str(x.get("semantic_level")) for x in normalized_relations)
    type_counts = collections.Counter(str(x.get("normalized_relation_type")) for x in normalized_relations)
    old_political = sum(1 for x in relations if x.get("relation_type") == "explicit_political_cooperation_opposition")
    political_reclassified = sum(1 for x in normalized_relations if x.get("original_relation_type") == "explicit_political_cooperation_opposition" and x.get("normalized_relation_type") == "documented_political_interaction")
    kinship_corrections = sum(1 for x in normalized_relations if x.get("normalization_reason") == "kinship_ontology_repair")
    before_provisional = len({str(x.get("provisional_neighbor_id")) for x in relations if x.get("provisional_neighbor_id")})
    resolved_existing = [x for x in resolution_rows if x.get("resolution_status") == "resolved_existing_person"]
    resolved_provisional = [x for x in resolution_rows if x.get("resolution_status") == "resolved_provisional_person"]
    unresolved_occurrences_before = sum(1 for x in relations if x.get("resolution_status") == "unresolved_identity") + sum(1 for x in temporal if x.get("subject_resolution_status") == "unresolved_identity")
    unresolved_occurrences_after = sum(1 for x in resolution_rows if x.get("resolution_status") == "unresolved_identity")
    ambiguous_after = sum(1 for x in resolution_rows if x.get("resolution_status") == "ambiguous_identity")
    provisional_after = len({str(x.get("provisional_neighbor_id")) for x in normalized_relations if x.get("provisional_neighbor_id")})
    unresolved_provisional_after = len({str(x.get("provisional_neighbor_id")) for x in normalized_relations if x.get("resolution_status") == "unresolved_identity" and x.get("provisional_neighbor_id")})
    source_forms = collections.Counter()
    for mode in retrieval_comparison["modes"].values():
        source_forms.update(mode.get("source_form_counts", {}))

    metrics = {
        "schema": 1,
        "stage": "hng0-2-metrics",
        "canonical_write_back": False,
        "execution_kind": "offline_deterministic",
        "model_calls": 0,
        "seed_count": len(profiles),
        "seed_person_ids": sorted(profiles),
        "input_relation_candidates": len(relations),
        "input_temporal_candidates": len(temporal),
        "input_unresolved_occurrences": len(unresolved_doc.get("items", [])),
        "unresolved_provisional_neighbor_count_before": before_provisional,
        "provisional_neighbor_count_after": provisional_after,
        "unresolved_provisional_neighbor_count_after": unresolved_provisional_after,
        "unresolved_occurrences_before": unresolved_occurrences_before,
        "unresolved_occurrences_after": unresolved_occurrences_after,
        "ambiguous_identity_count_after": ambiguous_after,
        "resolved_existing_count": len(resolved_existing),
        "resolved_provisional_count": len(resolved_provisional),
        "resolved_by_method": dict(sorted(collections.Counter(str(x.get("resolution_method")) for x in resolved_existing + resolved_provisional).items())),
        "normalized_relation_count": len(normalized_relations),
        "normalized_temporal_count": len(normalized_temporal),
        "relation_level_counts": dict(sorted(level_counts.items())),
        "relation_type_counts": dict(sorted(type_counts.items())),
        "relation_level_type_counts": {f"{level}:{kind}": count for (level, kind), count in sorted(relation_counts.items())},
        "political_candidates_before": old_political,
        "political_candidates_reclassified_to_documented_interaction": political_reclassified,
        "kinship_ontology_corrections": kinship_corrections,
        "rejected_after_normalization": len(rejected_relations),
        "remaining_unresolved_identity_count": len([x for x in resolution_rows if x.get("resolution_status") == "unresolved_identity"]),
        "remaining_ambiguous_identity_count": ambiguous_after,
        "source_form_usage": dict(sorted(source_forms.items())),
        "punctuated_unit_count": len(punctuated_units),
        "legacy_comparison_unit_count": len(legacy_units),
        "api_usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
        "latency": {"model_calls": 0},
    }

    identity_doc = {
        "schema": 1,
        "stage": "hng0-2-identity-resolution",
        "canonical_write_back": False,
        "source_policy": "HNG0.1 candidate evidence and registered local source text only; no generated text corpus",
        "input_relation_count": len(relations),
        "input_temporal_count": len(temporal),
        "resolutions": sorted(resolution_rows, key=lambda x: (str(x.get("candidate_kind")), str(x.get("candidate_id")), str(x.get("surface")))),
    }
    relation_doc = {"schema": 1, "stage": "hng0-2-normalized-relations", "canonical_write_back": False, "relations": normalized_relations, "evidence": build_evidence_projection(evidence), "rejected": rejected_relations}
    temporal_doc = {"schema": 1, "stage": "hng0-2-normalized-temporal", "canonical_write_back": False, "temporal_items": normalized_temporal, "evidence": build_evidence_projection(evidence)}
    interaction_doc = {"schema": 1, "stage": "hng0-2-interaction-edges", "canonical_write_back": False, "relations": [x for x in normalized_relations if x.get("semantic_level") in {"documented_interaction", "interpreted_relation"}]}
    unresolved_out = {"schema": 1, "stage": "hng0-2-unresolved-identities", "canonical_write_back": False, "items": sorted(unresolved_items, key=lambda x: (str(x.get("seed_person_id")), str(x.get("surface")), str(x.get("resolution_status"))))}

    audit_rows: list[dict[str, Any]] = []
    for item in sorted(resolved_existing + resolved_provisional, key=lambda x: (str(x.get("candidate_kind")), str(x.get("candidate_id"))))[:10]:
        audit_rows.append({"kind": "identity", "candidate_id": item.get("candidate_id"), "surface": item.get("surface"), "resolution": item})
    for row in [x for x in normalized_relations if x.get("normalization_reason") != "preserved_hard_relation"][:10]:
        audit_rows.append({"kind": "relation", "candidate_id": row.get("candidate_ids", [None])[0], "original_relation_type": row.get("original_relation_type"), "normalized_relation": {k: row.get(k) for k in ("relation_id", "person_a_name", "counterpart_surface", "normalized_relation_type", "semantic_level", "normalization_reason", "claim", "evidence_refs", "evidence_quotes")}})
    for row in normalized_relations:
        if row.get("normalization_reason") == "kinship_ontology_repair":
            audit_rows.append({"kind": "kinship_correction", "candidate_id": row.get("candidate_ids", [None])[0], "original_relation_type": row.get("original_relation_type"), "normalized_relation": row})
    for item in unresolved_items:
        if item.get("resolution_status") == "ambiguous_identity":
            audit_rows.append({"kind": "ambiguous_identity", "candidate_id": item.get("candidate_id"), "resolution": item})
    audit_doc = {"schema": 1, "stage": "hng0-2-audit-sample", "canonical_write_back": False, "items": audit_rows}

    input_paths = [RELATION_INPUT, TEMPORAL_INPUT, UNRESOLVED_INPUT, EVIDENCE_INPUT, PROFILE_INPUT, SELECTION_INPUT]
    protected = {str(path.relative_to(ROOT)): sha256_file(path) for path in input_paths if path.is_file()}
    wref_locks = {wid: sha256_file(config["manifest"]) for wid, config in WREF1_SOURCES.items() if config["manifest"].is_file()}
    manifest = {
        "schema": 1,
        "stage": "hng0-2-manifest",
        "canonical_write_back": False,
        "execution_kind": "offline_deterministic",
        "model_calls": 0,
        "seed_person_ids": sorted(profiles),
        "one_hop_only": True,
        "input_hashes": protected,
        "wref1_manifest_hashes": wref_locks,
        "outputs": ["identity-resolution.json", "normalized-relations.json", "normalized-temporal-items.json", "unresolved-identities.json", "interaction-edges.json", "retrieval-comparison.json", "metrics.json", "audit-sample.json", "manifest.json"],
        "parameters": {"punctuated_source_first": True, "comparison_seed_count": 6, "punctuated_open_target_chars": "150-520", "legacy_open_chars": 1400},
        "source_policy": "raw WREF1 wikitext is read-only reference input; no semantic source rewrite; generated/model directories are excluded",
    }

    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    write_json(OUTPUT_ROOT / "identity-resolution.json", identity_doc)
    write_json(OUTPUT_ROOT / "normalized-relations.json", relation_doc)
    write_json(OUTPUT_ROOT / "normalized-temporal-items.json", temporal_doc)
    write_json(OUTPUT_ROOT / "unresolved-identities.json", unresolved_out)
    write_json(OUTPUT_ROOT / "interaction-edges.json", interaction_doc)
    write_json(OUTPUT_ROOT / "retrieval-comparison.json", retrieval_comparison)
    write_json(OUTPUT_ROOT / "metrics.json", metrics)
    write_json(OUTPUT_ROOT / "audit-sample.json", audit_doc)
    write_json(OUTPUT_ROOT / "manifest.json", manifest)
    review = {
        "schema": 1,
        "stage": "hng0-2-review-overlay",
        "canonical_write_back": False,
        "relation_decisions": {str(x["relation_id"]): {"review_status": "candidate", "reviewer_note": ""} for x in normalized_relations},
        "temporal_decisions": {str(x["temporal_id"]): {"review_status": "candidate", "reviewer_note": ""} for x in normalized_temporal},
        "identity_decisions": {str(x["candidate_id"]): {"review_status": "candidate", "reviewer_note": ""} for x in resolution_rows},
    }
    write_json(ROOT / "data/annotation/hng0-2-review.json", review)
    frontend = build_frontend_bundle(normalized_relations, normalized_temporal, relation_doc["evidence"], profiles, metrics, manifest)
    FRONTEND_PATH.parent.mkdir(parents=True, exist_ok=True)
    write_json(FRONTEND_PATH, frontend)
    return {"manifest": manifest, "metrics": metrics, "relations": normalized_relations, "temporal": normalized_temporal, "resolution": resolution_rows, "unresolved": unresolved_items, "retrieval": retrieval_comparison}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args()
    result = build()
    if not args.quiet:
        print(json.dumps({"status": "pass", "stage": "hng0-2", "metrics": result["metrics"]}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
