import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import hdb2_psl1_1_common as common  # noqa: E402


class HDB2PSL11Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.regression, cls.holdout = common.load_psl1_graphs()
        cls.predicates = []
        for record in common.load_frozen_predicate_records():
            for predicate in (record.get("payload") or {}).get("predicates", []) or []:
                cls.predicates.append({"mention_id": record.get("mention_id"), **predicate})

    def _case(self, story_id, surface):
        return next(
            case
            for graph in (self.regression, self.holdout)
            for case in graph.get("cases", [])
            if str(case.get("story_id")) == story_id and str(case.get("target_surface")) == surface
        )

    def _decision(self, story_id, surface):
        case = self._case(story_id, surface)
        graph = {"cases": [case], "distinct_pairs": []}
        return common.infer_graph(graph, self.predicates).get("records", [])[0]

    def test_reference_structure_development_cases(self):
        marriage = common.build_reference_structure(self._case("34-pilou-001", "主"))
        self.assertEqual(marriage["reference_head"], "主")
        self.assertEqual(marriage["reference_type"], "marriage_object_reference")
        self.assertEqual(marriage["anchor_person"], "王敦")
        self.assertIn("王敦", marriage["explicit_distinct_mentions"])

        office = common.build_reference_structure(self._case("05-fangzheng-028", "敦主簿"))
        self.assertEqual(office["holder"], "何充")
        self.assertEqual(office["patron_or_possessor"], "敦")
        self.assertEqual(office["reference_head"], "主簿")

        distinct = common.build_reference_structure(self._case("02-yanyu-046", "謝豫章"))
        self.assertIn("謝仁祖", distinct["explicit_distinct_mentions"])
        self.assertIn("謝豫章", distinct["explicit_distinct_mentions"])

    def test_role_vetoes_remove_all_three_false_resolutions(self):
        for story_id, surface, wrong in (
            ("34-pilou-001", "主", "王敦"),
            ("02-yanyu-046", "謝豫章", "謝尚"),
            ("05-fangzheng-028", "敦主簿", "王敦"),
        ):
            case = self._case(story_id, surface)
            candidate = next((row for row in case["candidates"] if row.get("display_name") == wrong), None)
            self.assertIsNotNone(candidate, (story_id, surface, wrong))
            self.assertIn(str(candidate["candidate_key"]), case["psl1_1_role_vetoes"])
            decision = self._decision(story_id, surface)
            self.assertNotEqual(decision.get("top_candidate"), wrong)
            # A syntactically identified office holder (何充 in 敦主簿) may
            # resolve safely; the protected invariant is that the patron/
            # actor false resolution is never retained.
            if decision.get("result_state") in {"stable_entity_resolved", "local_candidate_resolved"}:
                self.assertNotEqual(decision.get("top_candidate"), wrong)

    def test_dun_secretary_uses_exact_head_not_substring_alias(self):
        case = self._case("05-fangzheng-028", "敦主簿")
        wang = next(row for row in case["candidates"] if row.get("display_name") == "王敦")
        alias_rows = [
            row for row in case["deterministic_predicates"]
            if row.get("candidate_key") == wang.get("candidate_key") and row.get("predicate") == "AliasMatch"
        ]
        self.assertEqual(len(alias_rows), 1)
        self.assertEqual(alias_rows[0].get("value"), 0.5)
        self.assertIn("PossessorVsHolderMismatch", case["psl1_1_role_vetoes"][wang["candidate_key"]])

    def test_explicit_office_holder_is_not_lost_when_reviewer_rejects_old_top(self):
        case = self._case("08-shangyu-051", "長史")
        self.assertEqual(case["reference_structure"]["holder"], "謝鯤")
        self.assertEqual(case["reference_structure"]["syntactic_role"], "office_holder")
        self.assertEqual(case["reference_structure_direct_support"], ["c1"])
        decision = self._decision("08-shangyu-051", "長史")
        self.assertEqual(decision["top_candidate"], "謝鯤")
        self.assertEqual(decision["result_state"], "stable_entity_resolved")
        self.assertTrue(decision["direct_reference_support"])

    def test_xie_yuzhang_adds_existing_xie_kun_without_merging_xie_shang(self):
        case = self._case("02-yanyu-046", "謝豫章")
        self.assertTrue(any(row.get("display_name") == "謝鯤" and row.get("person_id") == "person-023" for row in case["candidates"]))
        xie_shang = next(row for row in case["candidates"] if row.get("display_name") == "謝尚")
        self.assertIn("ExplicitDistinct", case["psl1_1_role_vetoes"][xie_shang["candidate_key"]])

    def test_known_supported_cases_remain_available_before_reviewer(self):
        expected = {
            ("02-yanyu-107", "虎賁中郎將"): "潘岳",
            ("25-paidiao-038", "侍中"): "謝安",
            ("05-fangzheng-030", "僕射"): "周顗",
            ("10-guizhen-012", "豫章太守"): "謝鯤",
            ("02-yanyu-036", "丞相"): "王導",
            ("02-yanyu-054", "劉尹"): "劉惔",
            ("02-yanyu-069", "丹陽尹"): "劉惔",
            ("08-shangyu-051", "長史"): "謝鯤",
            ("19-xianyuan-026", "太傅"): "謝安",
        }
        for (story_id, surface), candidate in expected.items():
            decision = self._decision(story_id, surface)
            self.assertEqual(decision.get("top_candidate"), candidate, (story_id, surface, decision))

    def test_packets_include_structure_without_provider_ids(self):
        graph = self.regression
        case = self._case("05-fangzheng-028", "敦主簿")
        packet = common.wire_packet(case, graph["cases"], graph)
        rendered = json.dumps(packet, ensure_ascii=False, sort_keys=True)
        self.assertIn("reference_structure", packet)
        self.assertNotIn("person_id", rendered)
        self.assertNotIn("candidate_id", rendered)

    def test_reviewer_reject_top_downgrades_non_direct_stable_state(self):
        graph = {
            "cases": [{
                "mention_id": "m1",
                "occurrence_id": "o1",
                "target_surface": "甲",
                "candidates": [{
                    "candidate_key": "c0",
                    "display_name": "甲人",
                    "person_id": "person-a",
                    "candidate_node_id": "person:person-a",
                }],
                "deterministic_predicates": [],
                "psl1_hard_vetoes": {},
                "reference_structure": {},
            }],
            "distinct_pairs": [],
        }
        initial = {
            "records": [{
                "mention_id": "m1",
                "occurrence_id": "o1",
                "candidate_rankings": [{
                    "candidate_key": "c0",
                    "candidate": "甲人",
                    "candidate_person_id": "person-a",
                    "candidate_node_id": "person:person-a",
                    "hard_conflict": False,
                    "link": 1.0,
                }],
                "top_candidate_key": "c0",
                "top_candidate": "甲人",
                "top_candidate_person_id": "person-a",
                "result_state": "stable_entity_resolved",
            }],
        }
        final = common.apply_reviewer(initial, [{
            "mention_id": "m1",
            "validation": {"valid": True},
            "payload": {
                "verdict": "reject_top_candidate",
                "accepted_candidate_key": None,
                "direct_identity_support": [],
                "identity_contradictions": ["ev0"],
                "reason_types": ["contextual_compatibility_only"],
            },
        }], graph)
        self.assertEqual(final["records"][0]["result_state"], "review_required")
        self.assertTrue(final["records"][0]["reviewer_rejected_top_candidate"])

    def test_independent_selection_is_exactly_ten_and_unseen(self):
        with tempfile.TemporaryDirectory() as directory:
            selection = common.build_independent_selection(Path(directory) / "selection.json")
        self.assertEqual(selection["independent_count"], 10)
        self.assertTrue(selection["frozen_before_live"])
        self.assertTrue(selection["candidate_only"])
        self.assertFalse(selection["canonical_write_back"])
        psl1 = common.read_json(common.PSL1_SELECTION, {}) or {}
        excluded = {str(row.get("occurrence_id")) for row in [*psl1.get("regression_cases", []), *psl1.get("holdout_cases", [])]}
        self.assertFalse(excluded & {str(row.get("occurrence_id")) for row in selection["independent_cases"]})
        self.assertTrue(all(row.get("candidate_set") for row in selection["independent_cases"]))


if __name__ == "__main__":
    unittest.main()
