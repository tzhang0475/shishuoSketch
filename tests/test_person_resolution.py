from __future__ import annotations

import hashlib
import json
from pathlib import Path
import unittest

from scripts.person_resolution import HUAN_YI_CANDIDATE_ID, apply_reviewed_decision, build, resolve_mention
from scripts.validate_person_resolution import validate


ROOT = Path(__file__).resolve().parents[1]
WANG_TANZHI = {
    "target_kind": "identity_candidate",
    "candidate_id": "candidate-identity-067-liezhuan-002-e72bf92e965f",
    "canonical_name": "王坦之",
}
SUN_GUI = {
    "target_kind": "production_person",
    "person_id": "person-015",
    "canonical_name": "孫晷",
}
HUAN_YI = {
    "target_kind": "identity_candidate",
    "candidate_id": HUAN_YI_CANDIDATE_ID,
    "canonical_name": "桓伊",
}


def association(
    target: dict[str, str],
    surface: str = "文度",
    mode: str = "exact",
    alias_type: str = "courtesy_name",
) -> dict[str, object]:
    return {
        "target": target,
        "surface": surface,
        "alias_type": alias_type,
        "association_mode": mode,
        "association_strength": "strong",
        "evidence_ids": ["fixture-evidence"],
        "basis": "synthetic_test_fixture",
    }


def target_map(*targets: dict[str, str]) -> dict[str, dict[str, str]]:
    return {
        f"{target['target_kind']}:{target.get('person_id', target.get('candidate_id'))}": target
        for target in targets
    }


class PersonResolutionTests(unittest.TestCase):
    def test_huan_ziye_longest_safe_span_beats_person_016_prefix_alias(self) -> None:
        result = resolve_mention(
            {
                "mention_id": "fixture-huan-ziye",
                "surface": "桓子",
                "person_id": "person-016",
                "evidence": {"section_offset": 0},
            },
            text="桓子野善吹笛",
            alias_index={
                "桓子": [association({"target_kind": "production_person", "person_id": "person-016", "canonical_name": "王遐"}, "桓子")],
                "桓子野": [association(HUAN_YI, "桓子野", alias_type="established_appellation")],
            },
            targets_by_key=target_map(
                {"target_kind": "production_person", "person_id": "person-016", "canonical_name": "王遐"},
                HUAN_YI,
            ),
        )
        self.assertEqual(result["status"], "resolved")
        self.assertEqual(result["target"], HUAN_YI)
        self.assertEqual(result["semantic_span"]["text"], "桓子野")
        self.assertEqual(result["resolution_method"], "er1_1_2_longest_safe_semantic_span")

    def test_ziye_is_not_a_global_exact_alias_but_local_antecedent_resolves(self) -> None:
        contextual = association(HUAN_YI, "子野", mode="contextual", alias_type="textual_shorthand")
        global_result = resolve_mention(
            {"mention_id": "fixture-ziye-global", "surface": "子野", "evidence": {}},
            text="子野",
            alias_index={"子野": [contextual]},
            targets_by_key=target_map(HUAN_YI),
        )
        self.assertEqual(global_result["status"], "candidate_for_review")
        local_result = resolve_mention(
            {"mention_id": "fixture-ziye-local", "surface": "子野", "evidence": {"section_offset": 3}},
            text="桓子野子野",
            alias_index={"子野": [contextual]},
            targets_by_key=target_map(HUAN_YI),
            prior_entities=[{"span_surface": "桓子野", "surface": "桓子", "target": HUAN_YI}],
        )
        self.assertEqual(local_result["status"], "resolved")
        self.assertEqual(local_result["target"], HUAN_YI)
        self.assertIn("story_local_short_form_coreference", local_result["signals"])

    def test_huan_ziye_published_projection_keeps_full_span_and_no_person_016_links(self) -> None:
        effective = json.loads(
            (ROOT / "data/derived/person-resolution-effective.json").read_text(encoding="utf-8")
        )
        target_rows = [
            row
            for row in effective["mentions"]
            if row.get("entry_id") in {
                "05-fangzheng-055",
                "23-rendan-033",
                "23-rendan-042",
                "23-rendan-049",
                "26-qingdi-020",
            }
            and row.get("surface") == "桓子"
        ]
        self.assertEqual(len(target_rows), 6)
        for row in target_rows:
            self.assertEqual(row["resolution_target"], HUAN_YI)
            self.assertIsNone(row["person_id"])
            self.assertEqual(row["display_span"]["text"], "桓子野")
        short_rows = [
            row
            for row in effective["derived_mentions"]
            if row.get("entry_id") == "05-fangzheng-055" and row.get("surface") == "子野"
        ]
        self.assertEqual(len(short_rows), 1)
        self.assertEqual(short_rows[0]["resolution_target"], HUAN_YI)
        self.assertEqual(
            short_rows[0]["coreference_antecedent_mention_id"],
            "shishuo-p3b-wave-1-78fd849d96483f177986b7e2",
        )

        bundle = json.loads((ROOT / "data/derived/sc1-site.json").read_text(encoding="utf-8"))
        story = next(row for row in bundle["stories"] if row["id"] == "05-fangzheng-055")
        identity_segments = [
            segment
            for segment in story["reading"]["main_text"]["segments"]
            if segment.get("type") == "identity_mention"
        ]
        self.assertEqual(
            [segment["display"]["original"] for segment in identity_segments],
            ["桓子野", "子野"],
        )
        self.assertTrue(all(segment.get("canonical_name", {}).get("original") == "桓伊" for segment in identity_segments))

        links = json.loads((ROOT / "data/derived/person-story-links.json").read_text(encoding="utf-8"))["links"]
        self.assertFalse(any(link["person_id"] == "person-016" for link in links))

    def test_ancient_quoted_huan_zi_is_reviewed_unresolved(self) -> None:
        effective = json.loads(
            (ROOT / "data/derived/person-resolution-effective.json").read_text(encoding="utf-8")
        )
        ids = {
            "shishuo-p3b-wave-1-6e59def2507645e74bf6a736",
            "shishuo-p3b-wave-1-49ee363817c8c77394cecf83",
        }
        rows = {row["mention_id"]: row for row in effective["mentions"] if row.get("mention_id") in ids}
        self.assertEqual(set(rows), ids)
        for row in rows.values():
            self.assertEqual(row["resolution_status"], "unresolved")
            self.assertIsNone(row["resolution_target"])
            self.assertIsNone(row["person_id"])
            self.assertEqual(row["resolution_decision_source"], "human_review")

    def test_person_016_exact_alias_evidence_remains_in_registry(self) -> None:
        aliases = json.loads((ROOT / "data/aliases.json").read_text(encoding="utf-8"))["aliases"]
        self.assertTrue(
            any(
                alias.get("surface") == "桓子"
                and alias.get("person_ids") == ["person-016"]
                and alias.get("resolution_mode") == "exact"
                for alias in aliases
            )
        )

    def test_known_wang_wendu_regression_is_reviewed_nonmaterialized(self) -> None:
        document = json.loads(
            (ROOT / "data/derived/person-resolution-effective.json").read_text(encoding="utf-8")
        )
        rows = [
            row for row in document["mentions"]
            if row.get("entry_id") == "05-fangzheng-058" and row.get("surface") == "文度"
        ]
        self.assertEqual(len(rows), 7)
        for row in rows:
            self.assertEqual(row["resolution_status"], "resolved")
            self.assertEqual(row["resolution_decision_source"], "human_review")
            self.assertEqual(row["resolution_target"], WANG_TANZHI)
            self.assertIsNone(row["person_id"])
            self.assertNotEqual(row["person_id"], "person-015")

    def test_collision_registry_keeps_wang_and_sun_as_distinct_identities(self) -> None:
        document = json.loads(
            (ROOT / "data/derived/person-alias-collisions.json").read_text(encoding="utf-8")
        )
        record = next(row for row in document["records"] if row["surface"] == "文度")
        identities = {
            (row["target_kind"], row.get("person_id", row.get("candidate_id")))
            for row in record["candidate_identities"]
        }
        self.assertIn(("identity_candidate", WANG_TANZHI["candidate_id"]), identities)
        self.assertIn(("production_person", SUN_GUI["person_id"]), identities)

    def test_er1_1_yaliang_017_projects_maximal_spans_and_local_coreference(self) -> None:
        effective = json.loads(
            (ROOT / "data/derived/person-resolution-effective.json").read_text(encoding="utf-8")
        )
        derived = [row for row in effective["derived_mentions"] if row.get("entry_id") == "06-yaliang-017"]
        self.assertEqual({row["surface"] for row in derived}, {"庾太尉", "亮"})
        self.assertEqual(sum(row["surface"] == "亮" for row in derived), 2)
        for row in derived:
            self.assertEqual(row["resolution_target"]["canonical_name"], "庾亮")
            self.assertTrue(row["derived_only"])
            self.assertEqual(row["display_span"]["text"], row["surface"])
        canonical = json.loads((ROOT / "data/mentions/shishuo.json").read_text(encoding="utf-8"))
        raw = [row for row in canonical["mentions"] if row.get("entry_id") == "06-yaliang-017"]
        self.assertFalse(any(row.get("surface") in {"庾太尉", "亮"} for row in raw))

    def test_short_form_coreference_requires_same_local_antecedent(self) -> None:
        target = {"target_kind": "production_person", "person_id": "person-010", "canonical_name": "庾亮"}
        local = resolve_mention(
            {"mention_id": "fixture-short", "surface": "亮", "person_id": None, "evidence": {}},
            text="庾太尉亮",
            alias_index={},
            targets_by_key=target_map(target),
            prior_entities=[{"span_surface": "庾太尉", "surface": "太尉", "target": target}],
        )
        self.assertEqual(local["status"], "resolved")
        self.assertEqual(local["target"], target)
        outside = resolve_mention(
            {"mention_id": "fixture-short-outside", "surface": "亮", "person_id": None, "evidence": {}},
            text="亮",
            alias_index={},
            targets_by_key=target_map(target),
        )
        self.assertEqual(outside["status"], "unresolved")

    def test_span_audit_is_deterministic_and_reports_published_projection(self) -> None:
        audit = json.loads((ROOT / "data/derived/person-resolution-span-audit.json").read_text(encoding="utf-8"))
        self.assertEqual(audit["published_story_count"], 60)
        self.assertEqual(audit["audited_story_count"], 60)
        self.assertEqual(audit["review_required_count"], 0)
        records = [row for row in audit["records"] if row["story_id"] == "06-yaliang-017"]
        self.assertTrue(any(row["proposed_surface"] == "庾太尉" for row in records))
        self.assertTrue(any(row["proposed_surface"] == "亮" for row in records))

    def test_resolved_identity_candidate_is_not_a_production_navigation_target(self) -> None:
        bundle = json.loads((ROOT / "data/derived/sc1-site.json").read_text(encoding="utf-8"))
        story = next(row for row in bundle["stories"] if row["id"] == "05-fangzheng-058")
        segments = story["reading"]["main_text"]["segments"]
        identity_segments = [row for row in segments if row.get("type") == "identity_mention"]
        self.assertTrue(identity_segments)
        self.assertTrue(all(row["target_kind"] == "identity_candidate" for row in identity_segments))
        self.assertTrue(any(row.get("canonical_name", {}).get("original") == "王坦之" for row in identity_segments))

    def test_unique_alias_can_resolve(self) -> None:
        target = {"target_kind": "production_person", "person_id": "person-001", "canonical_name": "王羲之"}
        result = resolve_mention(
            {"mention_id": "fixture-unique", "surface": "逸少", "person_id": None, "evidence": {}},
            text="逸少",
            alias_index={"逸少": [association(target, "逸少")]},
            targets_by_key=target_map(target),
        )
        self.assertEqual(result["status"], "resolved")
        self.assertEqual(result["target"], target)

    def test_shared_alias_without_context_requires_review(self) -> None:
        result = resolve_mention(
            {"mention_id": "fixture-shared", "surface": "文度", "person_id": "person-015", "evidence": {}},
            text="文度",
            alias_index={"文度": [association(WANG_TANZHI), association(SUN_GUI)]},
            targets_by_key=target_map(WANG_TANZHI, SUN_GUI),
        )
        self.assertEqual(result["status"], "candidate_for_review")
        self.assertIsNone(result["target"])
        self.assertEqual({row["canonical_name"] for row in result["candidates"]}, {"王坦之", "孫晷"})

    def test_single_contextual_alias_never_becomes_global_exact(self) -> None:
        target = {"target_kind": "production_person", "person_id": "person-003", "canonical_name": "王導"}
        contextual = association(target, "丞相", mode="contextual")
        unresolved_surface = resolve_mention(
            {"mention_id": "fixture-contextual", "surface": "丞相", "person_id": None, "evidence": {}},
            text="丞相",
            alias_index={"丞相": [contextual]},
            targets_by_key=target_map(target),
        )
        self.assertEqual(unresolved_surface["status"], "candidate_for_review")
        existing_context = resolve_mention(
            {"mention_id": "fixture-contextual-existing", "surface": "丞相", "person_id": "person-003", "evidence": {}},
            text="丞相",
            alias_index={"丞相": [contextual]},
            targets_by_key=target_map(target),
        )
        self.assertEqual(existing_context["status"], "resolved")
        self.assertEqual(existing_context["resolution_mode"], "contextual")

    def test_surname_plus_courtesy_and_local_antecedent(self) -> None:
        alias_index = {
            "王文度": [association(WANG_TANZHI, "王文度")],
            "文度": [association(WANG_TANZHI), association(SUN_GUI)],
        }
        targets = target_map(WANG_TANZHI, SUN_GUI)
        first = resolve_mention(
            {"mention_id": "fixture-full", "surface": "文度", "person_id": None, "evidence": {"section_offset": 1}},
            text="王文度",
            alias_index=alias_index,
            targets_by_key=targets,
        )
        self.assertEqual(first["status"], "resolved")
        self.assertEqual(first["target"], WANG_TANZHI)
        later = resolve_mention(
            {"mention_id": "fixture-later", "surface": "文度", "person_id": None, "evidence": {"section_offset": 4}},
            text="王文度文度",
            alias_index=alias_index,
            targets_by_key=targets,
            prior_targets=[first["target"]],
        )
        self.assertEqual(later["status"], "resolved")
        self.assertEqual(later["target"], WANG_TANZHI)

    def test_conflicting_local_antecedents_require_review(self) -> None:
        alias_index = {"文度": [association(WANG_TANZHI), association(SUN_GUI)]}
        result = resolve_mention(
            {"mention_id": "fixture-conflict", "surface": "文度", "person_id": None, "evidence": {}},
            text="文度文度",
            alias_index=alias_index,
            targets_by_key=target_map(WANG_TANZHI, SUN_GUI),
            prior_targets=[WANG_TANZHI, SUN_GUI],
        )
        self.assertEqual(result["status"], "candidate_for_review")
        self.assertIn("multiple_compatible_local_antecedents", result["reasons"])

    def test_materialization_status_does_not_break_shared_alias(self) -> None:
        result = resolve_mention(
            {"mention_id": "fixture-bias", "surface": "文度", "person_id": None, "evidence": {}},
            text="文度",
            alias_index={"文度": [association(SUN_GUI), association(WANG_TANZHI)]},
            targets_by_key=target_map(SUN_GUI, WANG_TANZHI),
        )
        self.assertEqual(result["status"], "candidate_for_review")

    def test_reviewed_decision_always_wins(self) -> None:
        decision = {
            "mention_id": "fixture-review",
            "resolution_status": "resolved",
            "target": WANG_TANZHI,
            "review_status": "reviewed",
            "review_note": "fixture",
            "evidence_ids": ["fixture-evidence"],
        }
        result = resolve_mention(
            {"mention_id": "fixture-review", "surface": "文度", "person_id": "person-015", "evidence": {}},
            text="文度",
            alias_index={"文度": [association(SUN_GUI)]},
            targets_by_key=target_map(WANG_TANZHI, SUN_GUI),
            decision=decision,
        )
        self.assertEqual(result["decision_source"], "human_review")
        self.assertEqual(result["target"], WANG_TANZHI)

    def test_review_conflict_is_retained_without_overwriting_reviewed_target(self) -> None:
        automatic = {
            "status": "candidate_for_review",
            "target": None,
            "reasons": ["shared_alias_surface"],
        }
        reviewed = {
            "status": "resolved",
            "target": WANG_TANZHI,
            "reasons": [],
            "decision_source": "human_review",
        }
        result = apply_reviewed_decision(automatic, reviewed)
        self.assertEqual(result["target"], WANG_TANZHI)
        self.assertEqual(result["review_conflict"]["automatic_status"], "candidate_for_review")

    def test_effective_artifacts_are_deterministic(self) -> None:
        paths = [
            ROOT / "data/derived/person-resolution-effective.json",
            ROOT / "data/derived/person-resolution-review-queue.json",
            ROOT / "data/derived/person-alias-collisions.json",
            ROOT / "docs/person-resolution-review.md",
        ]

        def hashes() -> list[str]:
            return [hashlib.sha256(path.read_bytes()).hexdigest() for path in paths]

        before = hashes()
        build(ROOT)
        first = hashes()
        build(ROOT)
        second = hashes()
        self.assertEqual(before, first)
        self.assertEqual(first, second)

    def test_validator_passes(self) -> None:
        self.assertEqual(validate(ROOT), [])


if __name__ == "__main__":
    unittest.main()
