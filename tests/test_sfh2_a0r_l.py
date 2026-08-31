from __future__ import annotations

import copy
import json
import re
import unittest
from pathlib import Path

import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from sfh2_a0r import pipeline as a0r_pipeline  # noqa: E402
from sfh2_a0r.contracts import (  # noqa: E402
    apply_patch,
    effective_adjudication,
    semantic_diff_paths,
)
from sfh2_a0r_l.common import (  # noqa: E402
    A0R_ROOT,
    CHALLENGE_SELECTION_PATH,
    MODEL,
    PROMPT_VERSIONS,
    build_case_packet,
    load_inputs,
    read_json,
)
from sfh2_a0r_l.consistency import story_consistency  # noqa: E402
from sfh2_a0r_l.selection import build_selection  # noqa: E402
from sfh2_a0r_l.transport import classify_preflight_failure  # noqa: E402


class SFH22A0RLTests(unittest.TestCase):
    def test_challenge_selection_is_five_stories_and_four_occurrences_each(self):
        selection = build_selection()
        self.assertEqual(20, selection["case_count"])
        self.assertEqual(5, selection["story_count"])
        self.assertEqual(set(selection["story_ids"]), set(selection["cases_per_story"]))
        self.assertTrue(all(value == 4 for value in selection["cases_per_story"].values()))
        for story_id in selection["story_ids"]:
            self.assertEqual(4, sum(row["story_id"] == story_id for row in selection["cases"]))

    def test_challenge_selection_has_no_prior_target_overlap(self):
        selection = build_selection()
        self.assertEqual([], selection["previous_targeted_overlap"])
        self.assertEqual([], selection["previous_targeted_story_overlap"])
        prior = set()
        for name in ("sfh2-a0-selection.json", "sfh2-2p1-selection.json", "sfh2-2p2-selection.json"):
            document = json.loads((ROOT / "data/annotation" / name).read_text())
            prior.update((row["story_id"], row["mention_id"]) for row in document.get("cases", []))
        selected = {(row["story_id"], row["mention_id"]) for row in selection["cases"]}
        self.assertFalse(prior & selected)
        self.assertFalse({story_id for story_id, _ in prior} & set(selection["story_ids"]))

    def test_repeated帝_occurrences_are_independent_mentions(self):
        rows = [row for row in build_selection()["cases"] if row["story_id"] == "10-guizhen-011" and row["surface"] == "帝"]
        self.assertEqual(2, len(rows))
        self.assertNotEqual(rows[0]["mention_id"], rows[1]["mention_id"])
        self.assertNotEqual(rows[0]["source_evidence_id"], rows[1]["source_evidence_id"])

    def test_selection_and_packets_are_gold_free(self):
        selection_text = CHALLENGE_SELECTION_PATH.read_text(encoding="utf-8")
        self.assertNotIn("expected_canonical_hint", selection_text)
        self.assertNotIn("must_not_resolve_to", selection_text)
        case = build_selection()["cases"][0]
        packet = build_case_packet(case, load_inputs())
        payload = a0r_pipeline.primary_payload(packet)
        encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True)
        self.assertNotIn("expected_canonical_hint", encoded)
        self.assertNotIn("must_not_resolve_to", encoded)
        self.assertNotIn("risk_dimensions", encoded)

    def test_a0r_architecture_is_the_frozen_input(self):
        architecture = read_json(A0R_ROOT / "architecture-freeze.json", {})
        self.assertTrue(architecture.get("architecture_hash"))
        self.assertEqual("deepseek-v4-flash", architecture["model_config"]["model"])
        self.assertEqual(0, architecture["model_config"]["temperature"])
        self.assertEqual({"type": "disabled"}, architecture["model_config"]["thinking"])
        self.assertEqual(MODEL, architecture["model_config"]["model"])
        self.assertEqual(PROMPT_VERSIONS, architecture["model_config"]["prompt_versions"])

    def test_preflight_environment_failure_is_classified_without_retry_policy(self):
        self.assertEqual("environmental_network_failure", classify_preflight_failure(RuntimeError("Operation not permitted")))
        self.assertEqual("environmental_network_failure", classify_preflight_failure(RuntimeError("DNS name or service not known")))
        source = (ROOT / "scripts/sfh2_a0r_l/transport.py").read_text(encoding="utf-8")
        probe_source = source.split("def summarize_transport_records", 1)[0]
        self.assertNotIn("for attempt", probe_source.split("def run_connectivity_probe", 1)[1])

    def test_selector_select_pass1_copies_exact_record(self):
        first = {"semantic_kind": "historical_person", "referent": {"surface_form": "甲", "canonical_hint": "乙", "confidence": "high"}}
        second = {"semantic_kind": "historical_person", "referent": {"surface_form": "甲", "canonical_hint": "丙", "confidence": "high"}}
        result = effective_adjudication(first, second, {"valid": True, "decision": "select_pass1", "patch": {}, "reviewed_fields": []}, {"source_evidence": []})
        self.assertEqual(first, result["record"])
        self.assertEqual([], semantic_diff_paths(first, result["record"]))

    def test_selector_select_pass2_copies_effective_record(self):
        first = {"semantic_kind": "historical_person", "referent": {"surface_form": "甲", "canonical_hint": "乙", "confidence": "high"}}
        second = {"semantic_kind": "historical_person", "referent": {"surface_form": "甲", "canonical_hint": "丙", "confidence": "high"}}
        result = effective_adjudication(first, second, {"valid": True, "decision": "select_pass2", "patch": {}, "reviewed_fields": []}, {"source_evidence": []})
        self.assertEqual(second, result["record"])

    def test_revision_changes_only_declared_paths(self):
        first = {"mention_id": "m", "surface": "甲", "semantic_kind": "historical_person", "reference_type": "full_name", "referent": {"surface_form": "甲", "canonical_hint": "乙", "confidence": "high"}, "occurrence_role": "scene_reference", "discourse": {"speaker_hint": "", "addressee_hint": "", "antecedent_hint": "", "self_reference_hint": ""}, "relations": [], "confidence": "high", "supporting_evidence_ids": ["ev"], "attribute_type": "", "attribute_value": "", "bearer_hint": "", "abstain": False, "explanation": ""}
        packet = {"source_evidence": [{"evidence_id": "ev", "text": "甲"}]}
        result = apply_patch(first, {"referent.canonical_hint": "丙"}, ["referent.canonical_hint"], packet)
        self.assertTrue(result["valid"])
        self.assertEqual(["referent.canonical_hint"], result["changed_fields"])
        self.assertFalse(apply_patch(first, {"referent.canonical_hint": "丙"}, ["confidence"], packet)["valid"])

    def test_same_surface_does_not_create_story_identity(self):
        records = [
            {"mention_id": "m-a", "selected_record": {"referent": {"canonical_hint": "A"}, "relations": []}},
            {"mention_id": "m-b", "selected_record": {"referent": {"canonical_hint": "B"}, "relations": []}},
        ]
        result = story_consistency(records)
        self.assertEqual([], result["flags"])
        self.assertEqual([], result["diagnostics"]["repeated_canonical_hints"])

    def test_story_consistency_only_reports_explicit_relation_conflict(self):
        records = [
            {"mention_id": "m-a", "selected_record": {"referent": {"canonical_hint": "A"}, "relations": [{"target_hint": "m-b", "relation": "same_person", "evidence_ids": ["ev"]}]}},
            {"mention_id": "m-a", "selected_record": {"referent": {"canonical_hint": "A"}, "relations": [{"target_hint": "m-b", "relation": "different_person", "evidence_ids": ["ev"]}]}},
        ]
        result = story_consistency(records)
        self.assertEqual(1, len(result["flags"]))
        self.assertEqual("identity_distinctness_conflict", result["flags"][0]["flag_type"])

    def test_no_lexical_identity_rules_in_new_runtime_package(self):
        for path in (ROOT / "scripts/sfh2_a0r_l").glob("*.py"):
            source = path.read_text(encoding="utf-8")
            self.assertNotRegex(source, re.compile(r"surface\s*=="))
            self.assertNotRegex(source, re.compile(r"surface\s+in\s+"))

    def test_candidate_and_write_contract_is_always_explicit(self):
        selection = build_selection()
        self.assertTrue(selection["candidate_only"])
        self.assertFalse(selection["canonical_write_back"])
        packet = build_case_packet(selection["cases"][0], load_inputs())
        self.assertTrue(packet["candidate_only"])
        self.assertFalse(packet["canonical_write_back"])


if __name__ == "__main__":
    unittest.main()
