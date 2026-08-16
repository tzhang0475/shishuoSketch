from __future__ import annotations

import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]


class W41ReaderConsistencyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.bundle = json.loads((ROOT / "data/derived/sc1-site.json").read_text(encoding="utf-8"))
        cls.app = (ROOT / "site/src/App.tsx").read_text(encoding="utf-8")
        cls.explorer = (ROOT / "site/src/relationExplorer.ts").read_text(encoding="utf-8")
        cls.reader_display = (ROOT / "site/src/readerDisplay.ts").read_text(encoding="utf-8")
        cls.styles = (ROOT / "site/src/styles.css").read_text(encoding="utf-8")

    def story(self, story_id: str) -> dict:
        return next(item for item in self.bundle["stories"] if item["id"] == story_id)

    def test_canonical_line_boundaries_remain_provenance_but_not_reader_breaks(self) -> None:
        story = self.story("06-yaliang-019")
        source_entry = (ROOT / "content/processed/shishuo/entries/06-yaliang/entry-019.md").read_text(encoding="utf-8")
        for boundary in ("丞相語\n郗信", "諸郎\n亦皆可嘉", "嫁\n女與焉"):
            self.assertIn(boundary, source_entry)
            self.assertIn(boundary, story["text"])

        reading = story["reading"]["main_text"]
        rendered = "".join(segment["display"]["original"] for segment in reading["segments"])
        self.assertNotIn("\n", reading["original"])
        self.assertNotIn("\n", rendered)
        self.assertNotIn("丞相語\n郗信", rendered)
        self.assertNotIn("諸郎\n亦皆可嘉", rendered)
        self.assertNotIn("嫁\n女與焉", rendered)

        # This is a corpus-wide reader invariant, not a Story-specific patch.
        for candidate in self.bundle["stories"]:
            self.assertNotRegex(candidate["reading"]["main_text"]["original"], r"\r?\n")
            for segment in candidate["reading"]["main_text"]["segments"]:
                self.assertNotRegex(segment["display"]["original"], r"\r?\n")

        self.assertIn("normalizeReaderText", self.app)
        self.assertIn("replace(/\\r\\n?/gu, \"\")", self.reader_display)
        story_style = next(line for line in self.styles.splitlines() if line.startswith(".story-text {"))
        self.assertIn("white-space: normal", story_style)
        self.assertNotIn("white-space: pre-wrap", story_style)

    def test_project_label_is_retained_as_data_but_has_no_special_story_heading(self) -> None:
        story = self.story("06-yaliang-019")
        self.assertEqual(story["title"], "东床坦腹")
        self.assertEqual(story["title_source"], "project_label")
        self.assertNotIn("function storyHeading", self.app)
        self.assertNotIn('title_source === "project_label"', self.app)
        self.assertNotIn("className=\"story-reference\"", self.app)
        self.assertIn('<h1 id="story-heading">{storyReference(story, readingMode)}</h1>', self.app)

    def test_flowing_entity_mentions_use_fragmentable_inline_keyboard_controls(self) -> None:
        helper_start = self.app.index("function InlineEntityMention")
        helper_end = self.app.index("function InlineReadingSegments")
        helper = self.app[helper_start:helper_end]

        self.assertIn('<span\n      role="button"', helper)
        self.assertIn("tabIndex={0}", helper)
        self.assertIn("onClick={onActivate}", helper)
        self.assertIn('event.key !== "Enter"', helper)
        self.assertIn('event.key !== " "', helper)
        self.assertIn("event.preventDefault()", helper)
        self.assertIn("onActivate()", helper)
        self.assertNotRegex(self.app, r"<button\s+[^>]*inline-person-mention")
        self.assertNotRegex(self.app, r"<button\s+[^>]*inline-ruler-mention")
        self.assertEqual(self.app.count("<InlineEntityMention"), 2)

        flowing_styles = self.styles[
            self.styles.index(".inline-person-mention {"):
            self.styles.index(".inline-identity-mention {")
        ]
        self.assertIn("display: inline", flowing_styles)
        self.assertIn("text-decoration-line: underline", flowing_styles)
        self.assertNotIn("white-space: nowrap", flowing_styles)
        self.assertNotIn("word-break: keep-all", flowing_styles)
        self.assertNotIn("border-bottom", flowing_styles)
        self.assertNotIn("inline-block", flowing_styles)
        self.assertNotIn("inline-flex", flowing_styles)

        self.assertRegex(
            self.styles,
            r"\.inline-identity-review > summary \{[^}]*text-decoration-line: underline;",
        )

    def test_entity_surfaces_keep_normal_cjk_wrapping_contract(self) -> None:
        flowing_blocks = []
        for selector in (
            ".inline-person-mention",
            ".inline-ruler-mention",
            ".inline-identity-mention",
            ".inline-identity-review > summary",
        ):
            start = self.styles.index(selector)
            end = self.styles.find("}", start)
            self.assertNotEqual(end, -1, selector)
            flowing_blocks.append(self.styles[start:end + 1])

        for block in flowing_blocks:
            self.assertNotIn("white-space: nowrap", block)
            self.assertNotIn("word-break: keep-all", block)
            self.assertNotIn("display: inline-block", block)
            self.assertNotIn("display: inline-flex", block)
            self.assertIn("text-decoration-line: underline", block)

        regression_surfaces = [
            ("02-yanyu-071", "谢太傅"),
            ("04-wenxue-094", "谢公"),
            ("05-fangzheng-025", "王右军"),
            ("05-fangzheng-032", "温太真"),
            ("05-fangzheng-032", "明帝"),
        ]
        for story_id, surface in regression_surfaces:
            story = self.story(story_id)
            mention_surfaces = {
                segment["display"]["simplified"]
                for segment in story["reading"]["main_text"]["segments"]
                if segment.get("type") in {"person_mention", "ruler_mention", "identity_mention"}
            }
            self.assertIn(surface, mention_surfaces, story_id)

    def test_relation_navigation_is_explicit_and_shared_by_row_and_ego_map(self) -> None:
        self.assertEqual(self.app.count("onClick={() => onRelationFocus(perspective)}"), 2)
        self.assertIn("relationContextStoryId", self.app)
        self.assertIn("via_relation_id", self.app)
        self.assertIn("from_person_id", self.app)
        self.assertIn("context_story_id", self.app)
        self.assertIn("writeStoryAddress(visibleStoryId)", self.app)
        self.assertIn("currentStoryFromExploration(next, publishedStoryIdSet)", self.app)
        self.assertIn("onRelationFocus={onRelationFocus}", self.app)

    def test_relation_context_and_back_are_deterministic(self) -> None:
        node = shutil.which("node")
        if node is None:
            self.skipTest("node is unavailable")
        typescript_runtime = ROOT / "node_modules/typescript/lib/typescript.js"
        if not typescript_runtime.exists():
            self.skipTest("installed TypeScript runtime is unavailable")

        with tempfile.TemporaryDirectory() as temporary:
            temporary_root = Path(temporary)
            runner = temporary_root / "run-w4-1-navigation.mjs"
            compiled = temporary_root / "relationExplorer.mjs"
            script = f'''
import fs from "node:fs";
import {{ createRequire }} from "node:module";
import {{ pathToFileURL }} from "node:url";

const require = createRequire(import.meta.url);
const ts = require({json.dumps(str(typescript_runtime))});
const source = fs.readFileSync({json.dumps(str(ROOT / "site/src/relationExplorer.ts"))}, "utf8");
const transpiled = ts.transpileModule(source, {{
  compilerOptions: {{ target: ts.ScriptTarget.ES2020, module: ts.ModuleKind.ESNext }},
}});
fs.writeFileSync({json.dumps(str(compiled))}, transpiled.outputText);
const {{ relationContextStoryId, currentStoryFromExploration, backExploration }} = await import(pathToFileURL({json.dumps(str(compiled))}).href);
const data = {{
  stories: [
    {{ id: "story-a", publication_state: "production_ready", person_ids: ["person-a"], global_ordinal: 2, ordinal: 1 }},
    {{ id: "story-b", publication_state: "production_ready", person_ids: ["person-a", "person-b"], global_ordinal: 1, ordinal: 1 }},
    {{ id: "story-c", publication_state: "production_ready", person_ids: ["person-b"], global_ordinal: 3, ordinal: 1 }},
    {{ id: "blocked", publication_state: "blocked", person_ids: ["person-b"], global_ordinal: 0, ordinal: 1 }},
  ],
  mentions: [
    {{ story_id: "story-b", person_id: "person-a", section: "main_text", confidence: "high" }},
    {{ story_id: "story-b", person_id: "person-b", section: "main_text", confidence: "high" }},
    {{ story_id: "story-c", person_id: "person-b", section: "main_text", confidence: "high" }},
  ],
}};
const relation = {{ id: "relation-test", subject_id: "person-a", object_id: "person-b", story_ids: ["blocked", "story-c", "story-b"], source_entry_ids: [] }};
const fallbackRelation = {{ id: "relation-fallback", subject_id: "person-a", object_id: "person-b", story_ids: [], source_entry_ids: [] }};
const valid = new Set(["story-a", "story-b", "story-c"]);
const stack = [
  {{ kind: "story", id: "story-a" }},
  {{ kind: "person", id: "person-a" }},
  {{ kind: "person", id: "person-b", context_story_id: "story-b" }},
];
const prior = backExploration(stack);
const value = {{
  relationFromA: relationContextStoryId(data, relation, "person-b", "story-a"),
  relationFromB: relationContextStoryId(data, relation, "person-b", "story-b"),
  fallback: relationContextStoryId(data, fallbackRelation, "person-b", "story-a"),
  current: currentStoryFromExploration(stack, valid),
  back: currentStoryFromExploration(prior, valid),
  invalidContext: currentStoryFromExploration([{{ kind: "story", id: "story-a" }}, {{ kind: "person", id: "person-b", context_story_id: "blocked" }}], valid),
  unavailable: relationContextStoryId(data, {{ ...fallbackRelation, object_id: "person-missing" }}, "person-missing", "story-a"),
}};
console.log(JSON.stringify(value));
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
            self.fail(f"relation navigation helper failed:\n{result.stderr}\n{result.stdout}")
        value = json.loads(result.stdout)
        self.assertEqual(value["relationFromA"], "story-b")
        self.assertEqual(value["relationFromB"], "story-c")
        self.assertEqual(value["fallback"], "story-b")
        self.assertEqual(value["current"], "story-b")
        self.assertEqual(value["back"], "story-a")
        self.assertEqual(value["invalidContext"], "story-a")
        self.assertIsNone(value["unavailable"])


if __name__ == "__main__":
    unittest.main()
