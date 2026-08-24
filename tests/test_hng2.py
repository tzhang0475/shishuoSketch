#!/usr/bin/env python3
"""Focused offline tests for HNG2's resolver and bounded projection."""

from __future__ import annotations

import json
import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import historical_entity_resolver as resolver  # noqa: E402


class HNG2ResolverTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.catalog = resolver.person_catalog()
        cls.index = resolver.forms_index(cls.catalog)

    def test_systematic_script_fold(self):
        for left, right in [("山涛", "山濤"), ("桓温", "桓溫"), ("刘伶", "劉伶")]:
            self.assertEqual(resolver.matching_normalize(left), resolver.matching_normalize(right))
            result = resolver.resolve_identity(
                surface=left, seed=self.catalog["person-043"], context=left,
                evidence={}, catalog=self.catalog, index=self.index,
            )
            self.assertEqual(result["resolution_status"], "resolved_existing_person")

    def test_decorated_name_suffix(self):
        result = resolver.resolve_identity(
            surface="沛國劉惔", seed=self.catalog["person-009"], context="沛國劉惔",
            evidence={}, catalog=self.catalog, index=self.index,
        )
        self.assertEqual(result["resolved_person_id"], "person-009")
        self.assertEqual(result["resolution_method"], "decorated_name_suffix")

    def test_contextual_title_is_not_global_alias(self):
        result = resolver.resolve_identity(
            surface="庾太尉", seed=self.catalog["person-010"],
            context="庾太尉風儀偉長，庾亮領江州",
            evidence={}, catalog=self.catalog, index=self.index,
        )
        self.assertEqual(result["resolved_person_id"], "person-010")
        self.assertEqual(result["resolution_method"], "title")

    def test_kinship_family_guard_does_not_bind_wang_dun(self):
        seed = self.catalog["person-029"]  # 卞壼
        result = resolver.resolve_identity(
            surface="敦", seed=seed, context="卞壼（從父兄敦）",
            evidence={}, catalog=self.catalog, index=self.index,
        )
        self.assertNotEqual(result.get("resolved_person_id"), next((pid for pid, p in self.catalog.items() if p.get("canonical_name") == "王敦"), "__none__"))
        self.assertIn(result["resolution_status"], {"provisional", "unresolved", "ambiguous"})
        self.assertEqual(result.get("kinship_parse", {}).get("family_surname"), "卞")

    def test_maternal_and_affinal_kinship_do_not_inherit_seed_surname(self):
        parsed = resolver.parse_kinship_surface("外祖敦", seed_surname="卞")
        self.assertFalse(parsed["surname_inheriting"])
        result = resolver.resolve_identity(
            surface="外祖敦", seed=self.catalog["person-029"], context="外祖敦",
            evidence={}, catalog=self.catalog, index=self.index,
        )
        self.assertNotEqual(result.get("resolved_person_id"), next((pid for pid, p in self.catalog.items() if p.get("canonical_name") == "王敦"), "__none__"))

    def test_structural_kinship_chain_is_not_a_person(self):
        parsed = resolver.parse_kinship_surface("喜弟預女", seed_surname="虞")
        self.assertTrue(parsed["malformed_person_surface"])
        self.assertTrue(parsed["relation_chain"])
        result = resolver.resolve_identity(
            surface="喜弟預女", seed=self.catalog["person-015"], context="娉喜弟預女為妻",
            evidence={}, catalog=self.catalog, index=self.index,
        )
        self.assertEqual(result["resolution_status"], "unresolved")

    def test_generic_roles_fail_closed(self):
        for surface in ("父母", "兄", "客", "帝", "太子"):
            result = resolver.resolve_identity(
                surface=surface, seed=self.catalog["person-010"], context=surface,
                evidence={}, catalog=self.catalog, index=self.index,
            )
            self.assertEqual(result["resolution_status"], "unresolved")

    def test_temporal_gate_rejects_liang_for_jin_seed(self):
        result = resolver.temporal_gate(
            {"canonical_name": "虞預", "dynasty": "東晉"},
            {"evidence_ref": "fixture", "original_text": "梁太清三年，虞預出現"},
        )
        self.assertEqual(result["status"], "conflict")

    def test_graph_alone_cannot_resolve_and_circular_is_excluded(self):
        edges = [{"relation_id": "current", "person_a": "person-010", "person_b": "person-043", "evidence_refs": ["r1"]}]
        support = resolver.graph_support(
            seed_id="person-010", candidate_id="person-043", edges=edges,
            current_evidence_refs=["r1"], current_candidate_id="current",
        )
        self.assertEqual(support["independent_graph_support_count"], 0)
        self.assertEqual(len(support["excluded_circular_edges"]), 1)
        result = resolver.resolve_identity(
            surface="玄", seed=self.catalog["person-006"], context="玄",
            evidence={}, catalog=self.catalog, index=self.index,
            graph_edges=[{"relation_id": "independent", "person_a": "person-006", "person_b": "person-043", "evidence_refs": ["other"]}],
        )
        self.assertNotEqual(result.get("decision_level"), "AUTO_SUPPORTED")

    def test_frontier_rejects_malformed_kinship(self):
        state = resolver.frontier_state(
            {"resolution_status": "provisional", "resolved_label": "喜弟預女", "kinship_parse": {"malformed_person_surface": True}},
            evidence_traceable=True, no_temporal_conflict=True, direct_source_hit=True,
        )
        self.assertEqual(state, "blocked_frontier")


class HNG2ProjectionTests(unittest.TestCase):
    def test_frozen_projection_and_two_wave_boundary(self):
        out = ROOT / "data/generated/hng2"
        self.assertTrue((out / "manifest.json").is_file())
        manifest = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
        self.assertFalse(manifest["canonical_write_back"])
        self.assertEqual(manifest["model"]["model_calls"], 0)
        identity = json.loads((out / "identity-resolution.json").read_text(encoding="utf-8"))
        frozen = json.loads((ROOT / "data/generated/hng1r2/identity-resolution.json").read_text(encoding="utf-8"))
        self.assertEqual(len(identity["resolutions"]), len(frozen["resolutions"]))
        wave2 = json.loads((out / "frontier-wave-2.json").read_text(encoding="utf-8"))
        self.assertFalse(wave2["wave_3_created"])
        self.assertFalse(any(int(row.get("wave", 0)) > 2 for row in wave2["frontiers"]))
        relation_rows = json.loads((out / "relations.json").read_text(encoding="utf-8"))["relations"]
        dun = [row for row in relation_rows if row.get("counterpart_surface") == "敦"]
        self.assertTrue(dun)
        self.assertTrue(all(row.get("person_b") != next((pid for pid, p in resolver.person_catalog().items() if p.get("canonical_name") == "王敦"), "__none__") for row in dun))


if __name__ == "__main__":
    unittest.main()
