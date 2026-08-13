from __future__ import annotations

import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class SC11FrontendContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.bundle = json.loads((ROOT / "data/derived/sc1-site.json").read_text(encoding="utf-8"))
        cls.app = (ROOT / "site/src/App.tsx").read_text(encoding="utf-8")
        cls.explorer = (ROOT / "site/src/relationExplorer.ts").read_text(encoding="utf-8")
        cls.styles = (ROOT / "site/src/styles.css").read_text(encoding="utf-8")

    def test_random_landing_only_uses_published_story_states(self) -> None:
        stories = self.bundle["stories"]
        self.assertEqual(len(stories), 16)
        self.assertTrue(all(item["publication_state"] in {"production_ready", "preview_ready"} for item in stories))
        self.assertIn("randomPublishedStoryId", self.explorer)
        self.assertIn("initialStoryId", self.app)
        self.assertIn("writeStoryAddress", self.app)

    def test_stack_path_and_back_operations_are_shared(self) -> None:
        for name in ("truncateExploration", "backExploration", "appendExploration"):
            self.assertIn(name, self.explorer)
        self.assertIn("ExplorationPath", self.app)
        self.assertIn("onPathSelect", self.app)
        self.assertIn("personPanelOpen", self.app)
        self.assertNotIn("const [focusedPersonId", self.app)

    def test_reader_has_explicit_scroll_reset_and_no_global_scroll_reset(self) -> None:
        self.assertIn("readerRef", self.app)
        self.assertIn("reader.scrollTop = 0", self.app)
        self.assertIn("reader.scrollIntoView", self.app)
        self.assertNotIn("window.scrollTo(0, 0)", self.app)

    def test_responsive_shell_and_drawer_share_one_person_explorer(self) -> None:
        self.assertIn("PersonExplorerPanel", self.app)
        self.assertIn("person-panel-shell", self.styles)
        self.assertIn("exploration-layout.with-person-panel", self.styles)
        self.assertIn("@media (max-width: 699px)", self.styles)
        self.assertIn("person-panel-surface", self.styles)

    def test_reading_controls_and_publication_metadata_are_separate_elements(self) -> None:
        self.assertIn("story-reading-toolbar", self.app)
        self.assertIn("reading-controls", self.app)
        self.assertIn("publication-note", self.app)


if __name__ == "__main__":
    unittest.main()
