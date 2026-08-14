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
        self.assertEqual(len(stories), 60)
        self.assertTrue(all(item["publication_state"] in {"production_ready", "preview_ready"} for item in stories))
        self.assertIn("randomPublishedStoryId", self.explorer)
        self.assertIn("initialStoryId", self.app)
        self.assertIn("writeStoryAddress", self.app)

    def test_random_person_entry_uses_generated_eligible_data(self) -> None:
        self.assertIn("randomEligiblePersonId", self.explorer)
        self.assertIn("eligiblePersonIds", self.explorer)
        self.assertIn("publishedStoryIdsForPerson", self.explorer)
        self.assertIn("randomPublishedStoryIdForPerson", self.explorer)
        self.assertIn("onRandomPerson", self.app)
        self.assertIn("随便认识一个人", self.app)
        self.assertNotIn('"person-001"', self.app)

    def test_random_person_resets_to_related_story_then_person(self) -> None:
        self.assertIn(
            "randomPublishedStoryIdForPerson(\n      data,\n      personId,\n      Math.random,\n      currentStoryFromExploration(stack) ?? undefined,\n    )",
            self.app,
        )
        self.assertIn(
            "setStack([\n      { kind: \"story\", id: storyId },\n      { kind: \"person\", id: personId },\n    ]);",
            self.app,
        )
        self.assertIn("setPersonPanelOpen(true);", self.app)
        self.assertIn("writeStoryAddress(storyId);", self.app)
        random_person_start = self.app.index("function chooseRandomPerson()")
        random_person_end = self.app.index("\n  if (error)", random_person_start)
        random_person_body = self.app[random_person_start:random_person_end]
        self.assertNotIn("focusPerson(personId)", random_person_body)
        focus_start = self.app.index("function focusPerson(personId: string")
        focus_end = self.app.index("\n  function selectStory", focus_start)
        focus_body = self.app[focus_start:focus_end]
        self.assertIn("setStack((current) => appendExploration(current, {", focus_body)
        self.assertNotIn("writeStoryAddress", focus_body)
        self.assertIn("onFocus={onFocus}", self.app)

    def test_random_person_story_helper_prefers_main_text_and_falls_back_to_liu(self) -> None:
        node = shutil.which("node")
        if node is None:
            self.skipTest("node is unavailable")
        typescript_runtime = ROOT / "node_modules/typescript/lib/typescript.js"
        if not typescript_runtime.exists():
            self.skipTest("installed TypeScript runtime is unavailable")
        with tempfile.TemporaryDirectory() as temporary:
            temporary_root = Path(temporary)
            runner = temporary_root / "run-person-story-helper.mjs"
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
const {{
  mainTextPublishedStoryIdsForPerson,
  publishedStoryIdsForPerson,
  randomPublishedStoryIdForPerson,
}} = await import(pathToFileURL({json.dumps(str(compiled))}).href);
const data = {{
  stories: [
    {{ id: "main-a", publication_state: "production_ready", person_ids: ["person-x"] }},
    {{ id: "liu-only", publication_state: "preview_ready", person_ids: ["person-x"] }},
    {{ id: "main-b", publication_state: "production_ready", person_ids: ["person-x"] }},
    {{ id: "blocked", publication_state: "blocked", person_ids: ["person-x"] }},
  ],
  mentions: [
    {{ story_id: "main-a", person_id: "person-x", section: "main_text", confidence: "high" }},
    {{ story_id: "liu-only", person_id: "person-x", section: "liu_annotation", confidence: "high" }},
    {{ story_id: "main-b", person_id: "person-x", section: "main_text", confidence: "high" }},
  ],
}};
const all = publishedStoryIdsForPerson(data, "person-x");
const main = mainTextPublishedStoryIdsForPerson(data, "person-x");
const selected = randomPublishedStoryIdForPerson(data, "person-x", () => 0, "main-a");
const fallbackData = {{
  stories: [{{ id: "liu-fallback", publication_state: "production_ready", person_ids: ["person-y"] }}],
  mentions: [{{ story_id: "liu-fallback", person_id: "person-y", section: "liu_annotation", confidence: "high" }}],
}};
const fallback = randomPublishedStoryIdForPerson(fallbackData, "person-y", () => 0);
const singleData = {{
  stories: [{{ id: "single", publication_state: "production_ready", person_ids: ["person-z"] }}],
  mentions: [],
}};
const single = randomPublishedStoryIdForPerson(singleData, "person-z", () => 0, "single");
console.log(JSON.stringify({{ all, main, selected, fallback, single }}));
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
                "Node Person→Story helper failed "
                f"(stderr):\n{result.stderr}\nstdout:\n{result.stdout}"
            )
        value = json.loads(result.stdout)
        self.assertEqual(value["all"], ["main-a", "liu-only", "main-b"])
        self.assertEqual(value["main"], ["main-a", "main-b"])
        self.assertEqual(value["selected"], "main-b")
        self.assertEqual(value["fallback"], "liu-fallback")
        self.assertEqual(value["single"], "single")

    def test_runtime_parse_site_bundle_accepts_all_inline_resolution_projections(self) -> None:
        node = shutil.which("node")
        if node is None:
            self.skipTest("node is unavailable")
        typescript_runtime = ROOT / "node_modules/typescript/lib/typescript.js"
        if not typescript_runtime.exists():
            self.skipTest("installed TypeScript runtime is unavailable")
        with tempfile.TemporaryDirectory() as temporary:
            temporary_root = Path(temporary)
            runner = temporary_root / "run-site-parser.mjs"
            compiled = temporary_root / "data.mjs"
            script = f'''
import fs from "node:fs";
import {{ createRequire }} from "node:module";
import {{ pathToFileURL }} from "node:url";

const require = createRequire(import.meta.url);
const ts = require({json.dumps(str(typescript_runtime))});
const source = fs.readFileSync({json.dumps(str(ROOT / "site/src/data.ts"))}, "utf8");
const bundle = JSON.parse(fs.readFileSync({json.dumps(str(ROOT / "site/src/generated/sc1-site.json"))}, "utf8"));
const sourceWithBundle = source.replace(
  'import generatedSiteBundle from "./generated/sc1-site.json";',
  "const generatedSiteBundle = " + JSON.stringify(bundle) + ";",
);
const transpiled = ts.transpileModule(sourceWithBundle, {{
  compilerOptions: {{
    target: ts.ScriptTarget.ES2020,
    module: ts.ModuleKind.ESNext,
  }},
}});
fs.writeFileSync({json.dumps(str(compiled))}, transpiled.outputText);
const {{ parseSiteBundle }} = await import(pathToFileURL({json.dumps(str(compiled))}).href);
const parsed = parseSiteBundle(bundle);
const story = parsed.stories.find((item) => item.id === "02-yanyu-036");
const annotation = story.reading.annotations.find((item) => item.id === "annotation-003");
console.log(JSON.stringify({{
  storyCount: parsed.stories.length,
  targetCount: annotation.segments.filter((item) => item.mention_id === "shishuo-02-yanyu-036-liu-annotation-004").length,
  targetType: annotation.segments.find((item) => item.mention_id === "shishuo-02-yanyu-036-liu-annotation-004")?.type,
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
                "Node SiteBundle parser failed "
                f"(stderr):\n{result.stderr}\nstdout:\n{result.stdout}"
            )
        value = json.loads(result.stdout)
        self.assertEqual(value["storyCount"], 60)
        self.assertEqual(value["targetCount"], 1)
        self.assertEqual(value["targetType"], "identity_mention")

    def test_random_story_and_person_actions_share_control_family(self) -> None:
        self.assertIn(".random-story-button, .random-person-button", self.styles)
        self.assertIn(".random-story-button:hover, .random-story-button:focus-visible,", self.styles)
        self.assertIn(".random-person-button:hover, .random-person-button:focus-visible", self.styles)

    def test_scene_card_is_story_owned_and_keeps_relations_separate(self) -> None:
        self.assertIn("scene_contexts", self.bundle)
        self.assertEqual(len(self.bundle["scene_contexts"]), 20)
        self.assertTrue(
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
            }
            <= set(self.bundle["scene_contexts"])
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
const {{ eligiblePersonIds, randomEligiblePersonId, randomPublishedStoryIdForPerson }} = await import(pathToFileURL({json.dumps(str(compiled))}).href);
const data = JSON.parse(fs.readFileSync({json.dumps(str(ROOT / "data/derived/sc1-site.json"))}, "utf8"));
const ids = eligiblePersonIds(data);
const first = randomEligiblePersonId(data, () => 0);
const second = randomEligiblePersonId(data, () => 0, first ?? undefined);
const landingStories = ids.map((id) => randomPublishedStoryIdForPerson(data, id, () => 0));
const sunGuiLanding = randomPublishedStoryIdForPerson(data, "person-015", () => 0);
const allLandingNavigable = landingStories.every((storyId, index) => Boolean(
  storyId &&
  data.stories.some((story) => story.id === storyId &&
    (story.publication_state === "production_ready" || story.publication_state === "preview_ready") &&
    story.person_ids.includes(ids[index]))
));
console.log(JSON.stringify({{
  count: ids.length,
  ids,
  first,
  second,
  sunGuiLanding,
  allNavigable: ids.every((id) => Boolean(data.person_sketches[id]) && data.stories.some((story) =>
    (story.publication_state === "production_ready" || story.publication_state === "preview_ready") &&
    story.person_ids.includes(id))),
  allLandingNavigable,
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

        # Derive the expected set independently from the generated bundle.
        # `eligiblePersonIds` is the production helper under test; this
        # assertion must not merely repeat its implementation or freeze the
        # current count.  `story.person_ids` is the safe, navigable projection
        # and therefore excludes candidate_for_review/unresolved identities.
        published_states = {"production_ready", "preview_ready"}
        published_story_people = {
            person_id
            for story in self.bundle["stories"]
            if story.get("publication_state") in published_states
            for person_id in story.get("person_ids", [])
        }
        sketch_ids = set(self.bundle["person_sketches"])
        production_ids = {person["id"] for person in self.bundle["people"]}
        expected_ids = production_ids & published_story_people & sketch_ids

        self.assertEqual(set(value["ids"]), expected_ids)
        self.assertEqual(value["count"], len(expected_ids))
        self.assertGreaterEqual(value["count"], 30)
        self.assertTrue(value["allNavigable"])
        self.assertTrue(value["allLandingNavigable"])
        self.assertNotEqual(value["first"], value["second"])
        self.assertIsNone(value["sunGuiLanding"])

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
