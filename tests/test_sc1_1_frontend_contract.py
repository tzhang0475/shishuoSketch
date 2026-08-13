from __future__ import annotations

import json
from pathlib import Path
import shutil
import subprocess
import tempfile
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

    def test_random_person_entry_uses_generated_eligible_data(self) -> None:
        self.assertIn("randomEligiblePersonId", self.explorer)
        self.assertIn("eligiblePersonIds", self.explorer)
        self.assertIn("onRandomPerson", self.app)
        self.assertIn("随便认识一个人", self.app)
        self.assertNotIn('"wang-xizhi"', self.app)

    def test_random_story_and_person_actions_share_control_family(self) -> None:
        self.assertIn(".random-story-button, .random-person-button", self.styles)
        self.assertIn(".random-story-button:hover, .random-story-button:focus-visible,", self.styles)
        self.assertIn(".random-person-button:hover, .random-person-button:focus-visible", self.styles)

    def test_scene_card_is_story_owned_and_keeps_relations_separate(self) -> None:
        self.assertIn("scene_contexts", self.bundle)
        self.assertEqual(
            set(self.bundle["scene_contexts"]),
            {
                "02-yanyu-069",
                "02-yanyu-083",
                "04-wenxue-036",
                "05-fangzheng-023",
                "05-fangzheng-055",
                "06-yaliang-027",
                "06-yaliang-029",
                "08-shangyu-077",
                "19-xianyuan-026",
            },
        )
        self.assertIn("SceneCard", self.app)
        self.assertIn("if (!scene) return null", self.app)
        self.assertIn("onFocus(person.person_id)", self.app)

    def test_random_person_helper_is_data_driven_and_avoids_immediate_repeat(self) -> None:
        node = shutil.which("node")
        if node is None:
            self.skipTest("node is unavailable")
        typescript_runtime = ROOT / "node_modules/typescript/lib/typescript.js"
        if not typescript_runtime.exists():
            self.skipTest("installed TypeScript runtime is unavailable")
        with tempfile.TemporaryDirectory() as temporary:
            temporary_root = Path(temporary)
            runner = temporary_root / "run-random-person.mjs"
            compiled = temporary_root / "relationExplorer.mjs"
            script = f'''
import fs from "node:fs";
import {{ createRequire }} from "node:module";
import {{ pathToFileURL }} from "node:url";

const require = createRequire(import.meta.url);
const ts = require({json.dumps(str(typescript_runtime))});
const source = fs.readFileSync({json.dumps(str(ROOT / "site/src/relationExplorer.ts"))}, "utf8");
const transpiled = ts.transpileModule(source, {{
  compilerOptions: {{
    target: ts.ScriptTarget.ES2020,
    module: ts.ModuleKind.ESNext,
  }},
}});
fs.writeFileSync({json.dumps(str(compiled))}, transpiled.outputText);
const {{ eligiblePersonIds, randomEligiblePersonId }} = await import(pathToFileURL({json.dumps(str(compiled))}).href);
const data = JSON.parse(fs.readFileSync({json.dumps(str(ROOT / "data/derived/sc1-site.json"))}, "utf8"));
const ids = eligiblePersonIds(data);
const first = randomEligiblePersonId(data, () => 0);
const second = randomEligiblePersonId(data, () => 0, first ?? undefined);
console.log(JSON.stringify({{
  count: ids.length,
  first,
  second,
  allNavigable: ids.every((id) => Boolean(data.person_sketches[id]) && data.stories.some((story) => story.person_ids.includes(id))),
}}));
'''
            runner.write_text(script, encoding="utf-8")
            result = subprocess.run(
                [node, str(runner)],
                cwd=ROOT,
                check=False,
                capture_output=True,
                text=True,
            )
        if result.returncode != 0:
            self.fail(
                "Node random-person helper failed "
                f"(stderr):\n{result.stderr}\nstdout:\n{result.stdout}"
            )
        value = json.loads(result.stdout)
        self.assertEqual(value["count"], 13)
        self.assertTrue(value["allNavigable"])
        self.assertNotEqual(value["first"], value["second"])

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
