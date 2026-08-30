from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import manual_semantic_authority as authority  # noqa: E402
import sfh2r_contract  # noqa: E402
import validate_sfh2r1  # noqa: E402


class SFH2R1CloseoutTests(unittest.TestCase):
    def test_validator_passes_materialized_second_authority(self):
        result = validate_sfh2r1.validate()
        self.assertTrue(result["valid"], result["errors"])
        self.assertEqual(4, result["second_pass_alias_repairs"])

    def test_shared_form_is_contextual_and_wrong_bearer_is_absent(self):
        aliases = json.loads((ROOT / "data/aliases.json").read_text(encoding="utf-8"))
        rows = {row.get("alias_id"): row for row in aliases["aliases"]}
        bolun = rows["alias-w3-9f1bc708fc909ce405824de4"]
        self.assertEqual("contextual", bolun["resolution_mode"])
        self.assertEqual("shared_or_contextual", bolun["status"])
        evidence = {row.get("evidence_id") for row in bolun["source_evidence"]}
        self.assertNotIn("evidence-w3-person-ba50566714ba7c916e6e18b6", evidence)
        self.assertTrue({
            "evidence-w3-person-836e3a2915da2a94ba0ba897",
            "evidence-w3-person-ea7273483165995805d45824",
            "evidence-w3-person-2a31d49d2a7acf0c0d0e95f3",
            "evidence-w3-person-c64569859384c914a84dddaf",
        } <= evidence)
        for alias_id in (
            "alias-w4-a0ab8bf1bf64e009032c292a",
            "alias-w4-c1809e42cafae4ba815946be",
            "alias-w4-ef14e8dd614bfb5c6425ce7d",
        ):
            row = rows[alias_id]
            self.assertEqual([], row.get("person_ids"))
            self.assertEqual([], row.get("resolved_person_ids"))
            self.assertEqual([], row.get("source_evidence"))

    def test_active_retrieval_preserves_direct_names_but_not_suppressed_titles(self):
        from sfh2.consolidation import build_existing_form_index
        from sfh2.inputs import load_documents

        index = build_existing_form_index(load_documents())
        self.assertTrue(index["exact_forms"].get("趙至"))
        self.assertTrue(index["exact_forms"].get("束晳"))
        self.assertTrue(index["exact_forms"].get("王隱"))
        self.assertTrue(index["exact_forms"].get("劉伶"))
        self.assertFalse(index["exact_forms"].get("伯倫"))
        self.assertTrue(index["contextual_forms"].get("伯倫"))
        for surface in ("王丞相", "王大將軍", "王庾諸公"):
            rows = [*index["exact_forms"].get(surface, []), *index["contextual_forms"].get(surface, [])]
            self.assertNotIn("person-054", {row.get("person_id") for row in rows})

    def test_unrelated_local_context_substring_is_not_a_candidate(self):
        """A cited local name is not identity evidence for another surface."""
        from sfh2.consolidation import build_existing_link_candidates

        documents = {
            "people": {"people": [
                {"person_id": "person-001", "canonical_name": "王隱"},
            ]},
            "aliases": {"aliases": []},
            "profiles": {"records": []},
            "hda2_overlay": [],
        }
        observations = {"records": [{
            "observation_id": "observation-substring",
            "mention_id": "mention-substring",
            "story_id": "synthetic",
            "surface": "某",
            "classification": "candidate_observation",
            "reference_semantics": {},
            "source_evidence_ids": ["e0"],
            "local_context": {"evidence": [{
                "evidence_id": "e0",
                "source_layer": "liu_annotation",
                "text": "王隱晉書曰某",
            }]},
        }]}
        result = build_existing_link_candidates(observations, documents)
        self.assertEqual([], result["records"][0]["candidates"])

    def test_referent_hint_survives_sfh1_to_sfh2_bridge_without_selecting_identity(self):
        from sfh2 import inputs
        from sfh2.consolidation import build_existing_link_candidates

        synthetic = {
            "packets": {"packets": [{"story_id": "synthetic", "evidence": [{"evidence_id": "e0", "text": "勒"}]}]},
            "mentions": {"records": [{
                "mention_id": "mention-synthetic",
                "story_id": "synthetic",
                "surface": "勒",
                "entity_kind": "person",
                "reference_form": "abbreviated_reference",
                "source_evidence_id": "e0",
                "source_start": 0,
                "source_end": 1,
            }]},
            "semantics": {"records": [{
                "mention_id": "mention-synthetic",
                "semantic_type": "abbreviated_person_reference",
                "referent_hint": "石勒",
                "network_role": "narrative_reference",
            }]},
            "candidate_sets": {"records": []},
            "final": {"records": []},
            "relations": {"records": []},
            "temporal": {"records": []},
        }
        observations = inputs.build_candidate_observations(synthetic)
        row = observations["records"][0]
        self.assertEqual("石勒", row["semantic_referent_hint"])
        self.assertEqual("石勒", row["reference_semantics"]["referent_hint"])
        from sfh2.inputs import load_documents
        links = build_existing_link_candidates(observations, load_documents())
        link = links["records"][0]
        self.assertEqual("石勒", link["referent_hint"])
        self.assertEqual("narrative_reference", link["network_role"])

    def test_explicit_source_roles_are_occurrence_level_graph_exclusions(self):
        import sfh2.projections as projections

        observations = {"records": [
            {"observation_id": "obs-source", "mention_id": "mention-source", "story_id": "synthetic", "network_role": "citation_author"},
            {"observation_id": "obs-person", "mention_id": "mention-person", "story_id": "synthetic", "network_role": "narrative_participant"},
        ]}
        consolidation = {"observation_entities": [
            {"observation_id": "obs-source", "mention_id": "mention-source", "entity_id": "person-054", "entity_type": "production_person"},
            {"observation_id": "obs-person", "mention_id": "mention-person", "entity_id": "person-003", "entity_type": "production_person"},
        ]}
        source_relation = {"relation_id": "synthetic-relation", "story_id": "synthetic", "relation_type": "social", "predicate_surface": "同", "evidence_id": "e0", "subject_mention_id": "mention-source", "object_mention_id": "mention-person"}
        documents = {"relations": {"records": [source_relation]}}
        relation = projections.relation_endpoint_reprojection(observations, consolidation, documents)
        self.assertEqual("semantic_reference_blocked", relation["records"][0]["endpoint_state"])
        self.assertIsNone(relation["records"][0]["subject_endpoint"])
        graph = projections.build_consolidated_graph(observations, consolidation, relation, documents, {"synthetic"})
        story_edges = [row for row in graph["edges"] if row.get("story_id") == "synthetic"]
        self.assertFalse(any(row.get("relation_id") == "synthetic-relation" for row in story_edges))
        self.assertFalse(any((row.get("source") or {}).get("node_id") == "person-054" and row.get("edge_type", "").startswith("sfh2_") for row in story_edges))

    def test_chained_derived_transition_is_explicit_and_valid(self):
        self.assertTrue(sfh2r_contract.transition_is_valid())
        self.assertEqual(2, len(sfh2r_contract.transition_manifests()))
        for document in sfh2r_contract.transition_manifests():
            self.assertTrue(document["authority_sha256"])
            self.assertTrue(document["candidate_only"])
            self.assertFalse(document["canonical_write_back"])

    def test_authority_accessors_keep_first_pass_compatibility_and_second_pass_scope(self):
        self.assertEqual(len(authority.load_authority().get("alias_repairs", [])), len(authority.alias_repairs()))
        self.assertEqual(4, len(authority.second_alias_repairs()))
        self.assertEqual(len(authority.alias_repairs()) + 4, len(authority.all_alias_repairs()))
        self.assertEqual({("王丞相", "person-054"), ("王大將軍", "person-054"), ("王庾諸公", "person-054")}, {
            (surface, person_id) for surface, person_id in authority.fully_blocked_forms()
            if person_id == "person-054"
        })


if __name__ == "__main__":
    unittest.main()
