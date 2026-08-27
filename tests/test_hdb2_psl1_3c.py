import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import hdb2_psl1_3c_common as common  # noqa: E402
import hdb2_psl1_3b_common as prior_b  # noqa: E402
import historical_context_algorithm as hng2_context  # noqa: E402
import rebuild_hdb2_f_profiles as profiles  # noqa: E402
import validate_hdb2_psl1_3c as validator  # noqa: E402


def fixture_case(surface, text, *, local_neighbors=(), candidates=()):
    return {
        "mention_id": f"m-{surface}",
        "occurrence_id": f"o-{surface}",
        "story_id": "fixture-story",
        "target_surface": surface,
        "occurrence_type": "abbreviated_person_name",
        "story_context": text,
        "annotation_context": [],
        "local_neighbors": list(local_neighbors),
        "candidates": list(candidates),
        "evidence_items": [{
            "evidence_id": "ev0",
            "family": "relevant_source_evidence",
            "source_ref": "fixture-source",
            "text": text,
        }],
    }


def person(name, person_id=None):
    row = {"display_name": name, "semantic_type": "person"}
    if person_id:
        row["person_id"] = person_id
    return row


class HDB2PSL13CTests(unittest.TestCase):
    def test_frozen_b_selection_is_reused_without_new_cases(self):
        current = common.freeze_selection()
        self.assertEqual(current, prior_b.read_json(prior_b.SELECTION_PATH, {}))
        self.assertEqual(current["selection_hash"], "2a9f65124320e153cb554e503e512e572779671f4fe789f4385d550f4a3404e9")
        self.assertTrue(current["candidate_only"])
        self.assertFalse(current["canonical_write_back"])

    def test_single_character_alias_does_not_force_lexicalized_person(self):
        current = fixture_case(
            "桓",
            "桓子野與客談",
            local_neighbors=[person("桓子野")],
            candidates=[person("桓溫", "person-008")],
        )
        info = common.reference_hypotheses(current)
        self.assertFalse(info["deterministic"])
        self.assertNotIn(
            "lexicalized_personal_form",
            {row.get("surface_structure") for row in info["hypotheses"]},
        )
        self.assertEqual(info["local_antecedent_hypotheses"][0]["surface"], "桓子野")

    def test_local_context_does_not_turn_unrelated_neighbors_into_antecedents(self):
        current = fixture_case(
            "桓",
            "桓玄時仲文入桓於庭中望見之",
            local_neighbors=[person("朱伺", "person-031"), person("卞範之", "person-066")],
        )
        surfaces = {row["surface"] for row in common._local_occurrence_surfaces(current)}
        self.assertEqual(surfaces, {"桓玄"})
        # A graph neighbour not named by this source is not a local
        # antecedent candidate.  The concrete ``桓謙`` case is covered by
        # the frozen replay.
        self.assertNotIn("朱伺", surfaces)
        self.assertNotIn("卞範之", surfaces)

    def test_invalid_reviewer_without_rankings_still_demotes_to_review(self):
        decisions = {
            "records": [{
                "mention_id": "m-empty",
                "result_state": "stable_entity_resolved",
                "reviewer_required": True,
                "candidate_rankings": [],
            }]
        }
        result = common.apply_reviewer(
            decisions,
            [{"mention_id": "m-empty", "validation": {"valid": False, "errors": ["payload_not_object"]}}],
            {"cases": []},
        )
        self.assertEqual(result["records"][0]["result_state"], "review_required")

    def test_comparison_adds_distinctness_without_identity(self):
        current = fixture_case(
            "潁",
            "王丞相二弟不過江曰潁曰敝時論以潁比鄧伯道",
            local_neighbors=[person("鄧伯道", "person-022")],
        )
        info = common.reference_hypotheses(current)
        self.assertIn("鄧伯道", info["comparison_distinct_mentions"])
        structure = common.finalize_reference_structure(current)
        self.assertIn("鄧伯道", structure["comparison_distinctness"])

    def test_invalid_reviewer_demotes_pre_review_stable_state(self):
        decisions = {
            "records": [{
                "mention_id": "m0",
                "result_state": "stable_entity_resolved",
                "reviewer_required": True,
                "candidate_rankings": [{"candidate_key": "c0", "hard_conflict": False}],
            }]
        }
        reviewer = [{
            "mention_id": "m0",
            "validation": {"valid": False, "errors": ["literal_null_invalid:accepted_candidate_key"]},
        }]
        result = common.apply_reviewer(decisions, reviewer, {"cases": []})
        row = result["records"][0]
        self.assertEqual(row["result_state"], "review_required")
        self.assertTrue(row["reviewer_invalid_demoted"])
        self.assertEqual(result["reviewer_invalid_demotions"], 1)

    def test_profile_integrity_artifact_has_provenance_and_no_known_contamination(self):
        audit = common.read_json(profiles.AUDIT_PATH, {})
        self.assertEqual(audit.get("forms_without_identity_provenance"), 0)
        self.assertEqual(audit.get("orphan_profile_forms"), 0)
        self.assertEqual(audit.get("ambiguous_forms"), [])
        self.assertEqual(audit.get("known_regression_failures"), [])
        self.assertEqual(audit.get("known_contamination_remaining"), [])
        self.assertGreater(audit.get("contaminated_profile_forms_removed", 0), 0)
        for path in (profiles.EXISTING_PROFILE, profiles.CANDIDATE_PROFILE):
            document = common.read_json(path, {})
            self.assertTrue(document["candidate_only"])
            self.assertFalse(document["canonical_write_back"])
            for profile in document["records"]:
                for form in (profile.get("identity") or {}).get("form_provenance", []):
                    for key in ("surface", "form_type", "person_id", "occurrence_id", "identity_observation_id", "evidence_ref", "identity_status", "identity_basis"):
                        self.assertIn(key, form)

    def test_contextual_identity_propagation_has_distinct_basis(self):
        window = hng2_context.prepare_evidence_window({
            "ref": "fixture",
            "text": "眾拒王廙，廙遂行",
            "evidence_text": "眾拒王廙，廙遂行",
        })
        validation = {
            "valid_entities": [{
                "entity_key": "e0",
                "surface": "廙",
                "entity_kind": "abbreviated_name",
                "reference_form": "abbreviated",
                "evidence_refs": ["fixture"],
            }],
            "valid_relations": [],
        }
        case = {
            "observation": {"surface": "廙"},
            "candidates": [{
                "candidate_key": "c0",
                "person_id": "person-053",
                "canonical_name": "王廙",
                "known_forms": ["王廙"],
            }],
            "constraint_checks": [],
            "seed": {},
        }
        result = hng2_context.normalize_person_fill(validation, case=case, windows=[window])
        target = next(row for row in result["entities"] if row["surface"] == "廙")
        self.assertEqual(target["resolved_person_id"], "person-053")
        self.assertEqual(target["identity_resolution_basis"], "contextual_name_projection")
        self.assertNotEqual(target["identity_resolution_basis"], "evidence_identity_assertion")
        self.assertEqual(result["source_grounded_identity_expansions"][0]["full_name_surface"], "王廙")

    def test_known_profiles_keep_valid_names_without_contaminated_forms(self):
        document = common.read_json(profiles.EXISTING_PROFILE, {})
        by_name = {row.get("canonical_name"): row for row in document.get("records", [])}
        deng = by_name["鄧攸"]["identity"]
        self.assertIn("鄧伯道", deng["observed_surfaces"])
        self.assertNotIn("潁", deng["observed_surfaces"])
        wang = by_name["王羲之"]["identity"]
        self.assertIn("羲之", wang["observed_surfaces"])
        self.assertNotIn("孫興公", wang["observed_surfaces"])
        self.assertNotIn("支道林", wang["observed_surfaces"])
        bian = by_name["卞範之"]["identity"]
        self.assertNotIn("謙", bian["observed_surfaces"])
        self.assertNotIn("敬祖", bian["observed_surfaces"])

    def test_reference_regressions_and_offline_run_validate(self):
        self.assertTrue(common.reference_regression_records()["all_pass"])
        result = validator.validate(validator.DEFAULT_RUN)
        self.assertTrue(result["valid"], json.dumps(result, ensure_ascii=False, indent=2))
        self.assertEqual(result["run_dir"], str(validator.DEFAULT_RUN.relative_to(ROOT)))

    def test_c_protection_excludes_only_rebuilt_profile_projections(self):
        hashes = validator.runner._c_protected_hashes()
        self.assertNotIn("data/derived/hdb2-f-person-knowledge.json", hashes)
        self.assertNotIn("data/derived/hdb2-f-candidate-person-knowledge.json", hashes)
        self.assertIn("data/people.json", hashes)
        self.assertIn("data/annotation/hdb2-f-review-queue.json", hashes)


if __name__ == "__main__":
    unittest.main()
