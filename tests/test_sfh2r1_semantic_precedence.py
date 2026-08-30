from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _alias(alias_id: str) -> dict:
    document = json.loads((ROOT / "data/aliases.json").read_text(encoding="utf-8"))
    return next(row for row in document.get("aliases", []) if row.get("alias_id") == alias_id)


def test_second_pass_manual_authority_is_candidate_only() -> None:
    doc = json.loads((ROOT / "data/annotation/sfh2r1-manual-semantic-authority.json").read_text(encoding="utf-8"))
    assert doc["candidate_only"] is True
    assert doc["canonical_write_back"] is False
    assert len(doc["alias_repairs"]) == 4


def test_liu_ling_bolun_is_contextual_and_shan_gai_evidence_filtered() -> None:
    from identity_resolution_policy import alias_retrieval_scope, filtered_alias_evidence

    row = _alias("alias-w3-9f1bc708fc909ce405824de4")
    assert alias_retrieval_scope(row) == "contextual"
    evidence_ids = {item.get("evidence_id") for item in filtered_alias_evidence(row)}
    assert "evidence-w3-person-ba50566714ba7c916e6e18b6" not in evidence_ids
    assert "evidence-w3-person-ea7273483165995805d45824" in evidence_ids


def test_wrong_wang_yin_title_aliases_are_fully_blocked() -> None:
    from identity_resolution_policy import alias_retrieval_scope

    for alias_id in (
        "alias-w4-a0ab8bf1bf64e009032c292a",  # 王丞相 -> 王導 context, not 王隱
        "alias-w4-c1809e42cafae4ba815946be",  # 王大將軍 -> 王敦 context, not 王隱
        "alias-w4-ef14e8dd614bfb5c6425ce7d",  # 王庾諸公 collective
    ):
        assert alias_retrieval_scope(_alias(alias_id)) == "blocked"


def test_bare_courtesy_names_are_not_global_exact_keys() -> None:
    from identity_resolution_policy import alias_retrieval_scope

    # Previously reviewed valid aliases remain historically valid, but their
    # bare courtesy-name surfaces require semantic context.
    for alias_id in (
        "alias-w4-30a821417d77b80c94883fde",  # 士居 / 沈充
        "alias-w4-6f0e6b979061a333767b4b13",  # 彦胄 / 鍾雅
        "alias-w4-67e4494a3b56d155d500b45d",  # 叔寧 / 虞預
        "alias-w4-c4c4b4dffa703ed405e1e6e5",  # 彦威 / 習鑿齒
    ):
        assert alias_retrieval_scope(_alias(alias_id)) == "contextual"


def test_full_personal_names_remain_exact() -> None:
    from identity_resolution_policy import alias_retrieval_scope

    assert alias_retrieval_scope(_alias("alias-w4-7180baa0e76911b435b331d6")) == "exact"  # 孫盛
    assert alias_retrieval_scope(_alias("alias-w4-cb9fc438ff6a35ac5b80dd86")) == "exact"  # 干寳


def test_sfh2_installs_no_substring_candidate_scan_policy() -> None:
    import sfh2.consolidation as consolidation
    from sfh2.inputs import load_documents

    documents = load_documents()
    index = consolidation.build_existing_form_index(documents)
    assert index["policy"]["substring_context_scan"] is False
    assert index["policy"]["occurrence_resolution_implies_global_alias"] is False

    # The polluted 王隱 title forms must be absent even as contextual candidates.
    for surface in ("王丞相", "王大將軍", "王庾諸公"):
        rows = index.get("contextual_forms", {}).get(surface, [])
        assert all(row.get("person_id") != "person-054" for row in rows)


def test_semantic_first_package_installs_v2_retrieval() -> None:
    import semantic_first.candidate_retrieval as retrieval

    people, exact, contextual = retrieval._form_rows()
    assert "person-054" in people
    assert all(row.get("person_id") != "person-054" for row in contextual.get("王丞相", []))
    assert "伯倫" in contextual
    assert "伯倫" not in exact
