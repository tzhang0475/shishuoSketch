from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import unittest

from scripts.validate_person_story_index import validate


ROOT = Path(__file__).resolve().parents[1]
LINKS_PATH = ROOT / "data/derived/person-story-links.json"
INDEX_PATH = ROOT / "data/derived/person-story-index.json"
MENTIONS_PATH = ROOT / "data/mentions/shishuo.json"


class PersonStoryIndexTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.links = json.loads(LINKS_PATH.read_text(encoding="utf-8"))
        cls.index = json.loads(INDEX_PATH.read_text(encoding="utf-8"))
        cls.mentions = json.loads(MENTIONS_PATH.read_text(encoding="utf-8"))["mentions"]

    def errors_after(self, mutate) -> list[str]:
        links = deepcopy(self.links)
        index = deepcopy(self.index)
        mutate(links, index)
        return validate(ROOT, links_document=links, index=index)

    def test_generated_artifacts_validate(self) -> None:
        self.assertEqual(validate(ROOT), [])

    def test_scope_is_the_unified_registry_and_supporting_person_is_first_class(self) -> None:
        people = json.loads((ROOT / "data/people.json").read_text(encoding="utf-8"))["people"]
        registry_ids = {person["person_id"] for person in people}
        self.assertEqual(set(self.links["person_scope"]), registry_ids)
        self.assertEqual(set(self.index["person_scope"]), registry_ids)
        self.assertIn("person-007", registry_ids)
        self.assertTrue(any(person["person_id"] == "person-007" and person["scope_role"] == "supporting" for person in people))

    def test_presence_layers_are_explicit_and_participation_is_not_inferred(self) -> None:
        for link in self.links["links"]:
            for presence in link["presences"]:
                self.assertIn(presence["source_layer"], {"main_text", "liu_annotation"})
                self.assertEqual(presence["presence_kind"], "mentioned")
        self.assertFalse(any(
            presence["presence_kind"] == "participant"
            for link in self.links["links"]
            for presence in link["presences"]
        ))

    def test_candidate_contextual_mentions_do_not_create_second_semantic_links(self) -> None:
        candidate_links = [
            link for link in self.links["links"]
            if link["review_status"] == "candidate"
        ]
        self.assertEqual(self.links["candidate_link_count"], len(candidate_links))
        self.assertEqual(
            self.links["candidate_mention_count"],
            sum(len(link["candidate_mention_ids"]) for link in self.links["links"]),
        )
        self.assertTrue(any(link["candidate_mention_ids"] for link in self.links["links"]))
        keys = [(link["person_id"], link["entry_id"]) for link in self.links["links"]]
        self.assertEqual(len(keys), len(set(keys)))
        # ER1 must remove the known false production link rather than retain
        # it as a reviewed PersonStory fact.  Other contextual candidates may
        # remain visible as review-only links.
        self.assertFalse(any(
            link["person_id"] == "person-015"
            and link["entry_id"] == "05-fangzheng-058"
            for link in self.links["links"]
        ))

    def test_index_projects_reviewed_links_exactly(self) -> None:
        reviewed_by_person: dict[str, set[str]] = {}
        for link in self.links["links"]:
            if link["review_status"] == "reviewed":
                reviewed_by_person.setdefault(link["person_id"], set()).add(link["id"])
        for person in self.index["persons"]:
            actual = {
                link_id
                for story_ref in person["story_refs"]
                for link_id in story_ref["link_ids"]
            }
            self.assertEqual(actual, reviewed_by_person.get(person["person_id"], set()))

    def test_index_cannot_place_a_link_under_another_person_or_story(self) -> None:
        def mutate(_links, index):
            person = next(person for person in index["persons"] if person["person_id"] == "person-001")
            person["story_refs"][0]["entry_id"] = "02-yanyu-069"

        errors = self.errors_after(mutate)
        self.assertTrue(any("includes a link for another entry" in error for error in errors))

    def test_reader_ready_requires_all_reading_layer_prerequisites(self) -> None:
        def mutate(_links, index):
            item = next(item for item in index["story_readiness"] if item["entry_id"] == "06-yaliang-019")
            item["simplified_reading"] = False

        errors = self.errors_after(mutate)
        self.assertTrue(any("06-yaliang-019.simplified_reading" in error for error in errors))

    def test_nonexistent_person_is_rejected(self) -> None:
        errors = self.errors_after(lambda links, _index: links["links"][0].__setitem__("person_id", "person-missing"))
        self.assertTrue(any("nonexistent Person" in error for error in errors))

    def test_nonexistent_story_is_rejected(self) -> None:
        errors = self.errors_after(lambda links, _index: links["links"][0].__setitem__("entry_id", "99-missing-001"))
        self.assertTrue(any("nonexistent entry" in error for error in errors))

    def test_annotation_only_presence_cannot_be_participant(self) -> None:
        def mutate(links, _index):
            link = next(link for link in links["links"] if any(p["source_layer"] == "liu_annotation" for p in link["presences"]))
            presence = next(p for p in link["presences"] if p["source_layer"] == "liu_annotation")
            presence["presence_kind"] = "participant"

        errors = self.errors_after(mutate)
        self.assertTrue(any("annotation-only presence cannot be participant" in error for error in errors))

    def test_relation_edges_cannot_create_person_story_links(self) -> None:
        mention_pairs = {
            (mention["person_id"], mention.get("entry_id") or mention.get("source_id"))
            for mention in self.mentions
            if mention.get("person_id") is not None
        }
        link_pairs = {
            (link["person_id"], link["entry_id"])
            for link in self.links["links"]
            if link["link_basis"] == "mention"
        }
        self.assertTrue(link_pairs <= mention_pairs)
        self.assertTrue(all("relation_id" not in link for link in self.links["links"]))
        self.assertTrue(all(link["link_basis"] in {"mention", "explicit_evidence"} for link in self.links["links"]))

    def test_relation_id_cannot_be_added_as_link_support(self) -> None:
        def mutate(links, _index):
            links["links"][0]["relation_id"] = "relation-gold-001"

        errors = self.errors_after(mutate)
        self.assertTrue(any("relation_id" in error and "Additional properties" in error for error in errors))

    def test_supporting_person_link_has_resolving_evidence(self) -> None:
        link = next(link for link in self.links["links"] if link["person_id"] == "person-007")
        self.assertEqual(link["link_basis"], "explicit_evidence")
        self.assertTrue(link["evidence_ids"])
        self.assertEqual(link["entry_id"], "06-yaliang-019")


if __name__ == "__main__":
    unittest.main()
