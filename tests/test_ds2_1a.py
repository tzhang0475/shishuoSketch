from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
import unittest

from scripts.build_ds2_1a_person_research import (
    ASSOCIATION_AUDIT_PATH,
    OUTPUT_PATH,
    ROOT,
    SHISHUO_SEARCH_OUTPUT_PATH,
    build_document,
)
from scripts.query_person_research import query_document
from scripts.search_shishuo_research import search_records
from scripts.validate_ds2_1a import validate


def read(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class DS21APersonResearchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.surface = read(ROOT / OUTPUT_PATH)
        cls.search = read(ROOT / SHISHUO_SEARCH_OUTPUT_PATH)
        cls.audit = read(ROOT / ASSOCIATION_AUDIT_PATH)

    def test_surface_validates(self) -> None:
        self.assertEqual(validate(ROOT), [])

    def test_scope_matches_exposed_person_projection(self) -> None:
        sc1 = read(ROOT / "data/derived/sc1-site.json")
        expected = {
            row["id"]
            for row in sc1["people"]
            if row.get("scope_role") in {"primary", "supporting"}
            and row.get("scope") in {"primary", "supporting"}
        }
        self.assertEqual(set(self.surface["people"]), expected)
        self.assertEqual(len(self.surface["people"]), len(expected))

    def test_layer_specific_story_links_are_preserved(self) -> None:
        yu = self.surface["people"]["person-010"]["shishuo_stories"]
        tao = self.surface["people"]["person-064"]["shishuo_stories"]
        self.assertEqual(
            next(row for row in yu if row["story_id"] == "27-jiajue-008")["relation_to_person"],
            "both",
        )
        self.assertEqual(
            next(row for row in tao if row["story_id"] == "27-jiajue-008")["relation_to_person"],
            "liu_annotation_only",
        )
        tao_row = next(row for row in tao if row["story_id"] == "27-jiajue-008")
        self.assertEqual(tao_row["scene_roles"], ["annotation_only"])
        self.assertEqual(tao_row["research_presence"], {"main_text": False, "liu_annotation": True})
        self.assertEqual(tao_row["research_priority_class"], "reviewed_liu_only")
        self.assertEqual(tao_row["association_strength"], "reviewed_textual")
        source_types = {source["type"] for source in tao_row["association_sources"]}
        self.assertEqual(source_types, {"person_story", "reviewed_participant"})
        participant = next(
            source for source in tao_row["association_sources"] if source["type"] == "reviewed_participant"
        )
        self.assertEqual(participant["role"], "annotation_only")
        self.assertEqual(participant["source_sections"], ["liu_annotation"])

    def test_all_existing_global_links_and_scope_counts_are_exposed(self) -> None:
        links = read(ROOT / "data/derived/person-story-links.json")["links"]
        rows = [row for person in self.surface["people"].values() for row in person["shishuo_stories"]]
        self.assertGreaterEqual(len(rows), len(links))
        person_story_ids = {
            source["record_id"]
            for row in rows
            for source in row["association_sources"]
            if source["type"] == "person_story"
        }
        self.assertEqual(
            person_story_ids,
            {row["person_story_link_id"] for row in rows if row["person_story_link_id"] is not None},
        )
        self.assertEqual(person_story_ids, {row["id"] for row in links})
        self.assertTrue(any(row["research_scope"] == "research_only" for row in rows))
        self.assertTrue(any(row["review_status"] == "candidate" for row in rows))
        self.assertTrue(any(row["source_presence"] == "both" for row in rows))
        self.assertEqual(len(rows), self.audit["counts"]["union_pairs"])
        self.assertEqual(self.audit["counts"]["participant_only_pairs"], 6)
        for person in self.surface["people"].values():
            self.assertEqual(
                person["story_count_total"],
                person["story_count_published"] + person["story_count_research_only"],
            )
            person_story_rows = [
                row
                for row in person["shishuo_stories"]
                if any(source["type"] == "person_story" for source in row["association_sources"])
            ]
            self.assertEqual(
                person["reviewed_link_count"] + person["candidate_link_count"],
                len(person_story_rows),
            )

    def test_participant_only_pairs_are_reviewed_union_rows(self) -> None:
        self.assertTrue(self.audit["participant_only_pairs"])
        pair = self.audit["participant_only_pairs"][0]
        person = self.surface["people"][pair["person_id"]]
        row = next(item for item in person["shishuo_stories"] if item["story_id"] == pair["story_id"])
        self.assertIsNone(row["person_story_link_id"])
        self.assertEqual({source["type"] for source in row["association_sources"]}, {"reviewed_participant"})
        self.assertEqual(row["review_status"], "reviewed")
        self.assertNotEqual(row["association_strength"], "candidate_textual")

    def test_association_audit_partitions_union_and_records_disagreements(self) -> None:
        counts = self.audit["counts"]
        self.assertEqual(
            counts["union_pairs"],
            counts["both_pairs"] + counts["person_story_only_pairs"] + counts["participant_only_pairs"],
        )
        self.assertEqual(len(self.audit["both_pairs"]), counts["both_pairs"])
        self.assertEqual(len(self.audit["person_story_only_pairs"]), counts["person_story_only_pairs"])
        self.assertEqual(len(self.audit["participant_only_pairs"]), counts["participant_only_pairs"])
        self.assertEqual(len(self.audit["source_layer_disagreements"]), counts["source_layer_disagreement_count"])
        self.assertEqual(len(self.audit["role_disagreements"]), counts["role_disagreement_count"])
        self.assertEqual(len(self.audit["unresolved_provenance_anomalies"]), 0)

    def test_query_prioritizes_reviewed_scene_before_textual_and_liu_rows(self) -> None:
        result = query_document(self.surface, "person-010", "27-jiajue-008")
        priority = {
            "reviewed_hard_scene": 0,
            "reviewed_main_text": 1,
            "reviewed_contextual": 2,
            "reviewed_liu_only": 3,
            "candidate_textual": 4,
        }
        values = [priority[row["research_priority_class"]] for row in result["related_shishuo"]]
        self.assertEqual(values, sorted(values))
        self.assertEqual(result["related_shishuo"][0]["research_priority_class"], "reviewed_hard_scene")

    def test_complete_search_corpus_preserves_layers(self) -> None:
        index = read(ROOT / "data/shishuo-corpus-index.json")
        self.assertEqual(len(self.search["records"]), index["entry_count"])
        self.assertEqual(
            {row["story_id"] for row in self.search["records"]},
            {row["id"] for row in index["entries"]},
        )
        self.assertTrue(all(row["main_text"] for row in self.search["records"]))
        self.assertTrue(any(row["liu_annotations"] for row in self.search["records"]))
        self.assertTrue(all("main_text" in row and "liu_annotations" in row for row in self.search["records"]))

    def test_exact_phrase_search_hits_canonical_main_text(self) -> None:
        result = search_records(self.search["records"], "一丘一壑", top_k=10)
        hit = next(row for row in result["hits"] if row["story_id"] == "09-pinzao-017")
        self.assertEqual(hit["source_layer"], "main_text")
        self.assertIn("一丘一壑", hit["excerpt"])

    def test_global_search_includes_unlinked_story_without_creating_link(self) -> None:
        links = read(ROOT / "data/derived/person-story-links.json")["links"]
        linked_stories = {row["entry_id"] for row in links}
        target = next(row for row in self.search["records"] if row["story_id"] not in linked_stories)
        needle = "".join(character for character in target["main_text"] if not character.isspace())[:5]
        result = search_records(self.search["records"], needle, links=links, top_k=50)
        self.assertIn(target["story_id"], {row["story_id"] for row in result["hits"]})
        self.assertFalse(next(row for row in result["hits"] if row["story_id"] == target["story_id"])["existing_person_link"])
        self.assertEqual(
            {row["id"] for row in links},
            {
                row["person_story_link_id"]
                for person in self.surface["people"].values()
                for row in person["shishuo_stories"]
                if row["person_story_link_id"] is not None
            },
        )

    def test_search_order_is_deterministic(self) -> None:
        links = read(ROOT / "data/derived/person-story-links.json")["links"]
        first = search_records(self.search["records"], "王敦", links=links, top_k=10)
        second = search_records(self.search["records"], "王敦", links=links, top_k=10)
        self.assertEqual(first, second)

    def test_jinshu_entries_are_local_candidates_and_confirmed_support_is_explicit(self) -> None:
        xie_an = self.surface["people"]["person-006"]["historical_biography_entries"]
        self.assertTrue(xie_an)
        self.assertTrue(any(row["match_status"] == "confirmed" for row in xie_an))
        for person in self.surface["people"].values():
            for row in person["historical_biography_entries"]:
                self.assertTrue(row["source_path"].startswith("content/processed/jinshu/units/"))
                self.assertNotIn("generated", row["source_path"])

    def test_only_resolved_aliases_enter_reviewed_context(self) -> None:
        for person in self.surface["people"].values():
            for alias in person["reviewed_context"]["aliases"]:
                self.assertEqual(alias["status"], "resolved")
                self.assertEqual(alias["resolution_mode"], "exact")
            for key in ("relations", "kinship", "offices", "events"):
                self.assertTrue(all(row["review_status"] == "reviewed" for row in person["reviewed_context"][key]))

    def test_query_marks_only_requested_story_current(self) -> None:
        result = query_document(self.surface, "person-010", "27-jiajue-008")
        self.assertEqual(result["current_story"]["story_id"], "27-jiajue-008")
        self.assertEqual(
            [row["story_id"] for row in result["related_shishuo"] if row["current_story"]],
            ["27-jiajue-008"],
        )

    def test_rebuild_is_byte_deterministic(self) -> None:
        protected_inputs = [
            ROOT / "data/derived/person-story-links.json",
            ROOT / "data/derived/h0c-participant-freeze.json",
            ROOT / "data/derived/sc1-site.json",
        ]
        protected_before = {path: digest(path) for path in protected_inputs}
        before = digest(ROOT / OUTPUT_PATH)
        search_before = digest(ROOT / SHISHUO_SEARCH_OUTPUT_PATH)
        audit_before = digest(ROOT / ASSOCIATION_AUDIT_PATH)
        first = build_document(ROOT)
        second = build_document(ROOT)
        self.assertEqual(first, second)
        self.assertEqual(before, digest(ROOT / OUTPUT_PATH))
        self.assertEqual(search_before, digest(ROOT / SHISHUO_SEARCH_OUTPUT_PATH))
        self.assertEqual(audit_before, digest(ROOT / ASSOCIATION_AUDIT_PATH))
        subprocess.run(
            ["python3", "scripts/build_ds2_1a_person_research.py"],
            cwd=ROOT,
            check=True,
            stdout=subprocess.DEVNULL,
        )
        first_hash = digest(ROOT / OUTPUT_PATH)
        first_search_hash = digest(ROOT / SHISHUO_SEARCH_OUTPUT_PATH)
        first_audit_hash = digest(ROOT / ASSOCIATION_AUDIT_PATH)
        subprocess.run(
            ["python3", "scripts/build_ds2_1a_person_research.py"],
            cwd=ROOT,
            check=True,
            stdout=subprocess.DEVNULL,
        )
        self.assertEqual(first_hash, digest(ROOT / OUTPUT_PATH))
        self.assertEqual(first_search_hash, digest(ROOT / SHISHUO_SEARCH_OUTPUT_PATH))
        self.assertEqual(first_audit_hash, digest(ROOT / ASSOCIATION_AUDIT_PATH))
        self.assertEqual(protected_before, {path: digest(path) for path in protected_inputs})


if __name__ == "__main__":
    unittest.main()
