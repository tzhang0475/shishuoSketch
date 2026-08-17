from __future__ import annotations

import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class BUG005ATests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = (ROOT / "site/src/App.tsx").read_text(encoding="utf-8")
        cls.styles = (ROOT / "site/src/styles.css").read_text(encoding="utf-8")
        cls.bundle = json.loads((ROOT / "data/derived/sc1-site.json").read_text(encoding="utf-8"))

    def test_candidate_identity_surface_is_an_ordinary_inline_projection(self) -> None:
        self.assertIn('className="inline-identity-candidate"', self.app)
        self.assertIn("data-mention-id={segment.mention_id}", self.app)
        self.assertNotIn('className="inline-identity-review"', self.app)
        candidate_style = self.styles[self.styles.index(".inline-identity-candidate {"):]
        candidate_style = candidate_style[:candidate_style.index("}") + 1]
        self.assertIn("display: inline", candidate_style)
        self.assertNotIn("inline-block", candidate_style)
        self.assertNotIn("inline-flex", candidate_style)

    def test_candidate_data_and_evidence_are_not_removed_from_projection(self) -> None:
        segments = [
            segment
            for story in self.bundle["stories"]
            for reading in [story["reading"]["main_text"], *story["reading"]["annotations"]]
            for segment in reading["segments"]
            if segment.get("type") == "identity_mention" and segment.get("resolution_status") == "candidate_for_review"
        ]
        self.assertTrue(segments)
        self.assertTrue(all(segment["candidate_names"] for segment in segments))
        mention_ids = {segment["mention_id"] for segment in segments}
        evidence_ids = {
            evidence_id
            for story in self.bundle["stories"]
            for evidence_id in story.get("evidence_ids", [])
        }
        self.assertTrue(mention_ids)
        self.assertTrue(evidence_ids)

    def test_candidate_is_not_a_person_navigation_control(self) -> None:
        candidate_start = self.app.index('if (segment.resolution_status === "candidate_for_review")')
        candidate_end = self.app.index('          }\n          return (', candidate_start)
        candidate_block = self.app[candidate_start:candidate_end]
        self.assertNotIn('role="button"', candidate_block)
        self.assertNotIn("onActivate", candidate_block)
        self.assertNotIn("<button", candidate_block)


if __name__ == "__main__":
    unittest.main()
