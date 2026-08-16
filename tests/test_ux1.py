from __future__ import annotations

import hashlib
import json
import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
HISTORY = ROOT / "site/public/generated/history"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


class UX1ProjectionTests(unittest.TestCase):
    def test_initial_bundle_is_protected_and_not_enriched(self):
        baseline = read(ROOT / "data/derived/ux1-frontend-size-baseline.json")
        generated = ROOT / "site/src/generated/sc1-site.json"
        self.assertEqual(sha256(generated), baseline["sc1_site"]["sha256"])
        self.assertEqual(generated.stat().st_size, baseline["sc1_site"]["bytes"])
        self.assertEqual(
            (ROOT / "data/derived/sc1-site.json").read_bytes(),
            generated.read_bytes(),
        )
        bundle = read(generated)
        self.assertNotIn("ux1", json.dumps(bundle, ensure_ascii=False).lower())
        for story in bundle["stories"]:
            for field in ("labels", "person_display", "relation_display", "source_display", "evidence_display"):
                self.assertNotIn(field, story["reading"])

    def test_manifest_scope_and_shards(self):
        manifest = read(HISTORY / "manifest.json")
        self.assertEqual(manifest["scope"]["published_story_count"], 143)
        self.assertEqual(manifest["scope"]["selected_x1_1_story_count"], 20)
        self.assertFalse(manifest["policies"]["unresolved_facts_projected"])
        self.assertFalse(manifest["policies"]["scholarly_assertions_as_facts"])
        self.assertEqual(len(list((HISTORY / "person").glob("*.json"))), 75)
        self.assertEqual(len(list((HISTORY / "story").glob("*.json"))), 143)

    def test_factual_rows_are_reviewed_only(self):
        for path in sorted((HISTORY / "person").glob("*.json")):
            payload = read(path)
            for field in ("family", "offices", "locations", "periods"):
                for row in payload[field]:
                    self.assertEqual(row["review_status"], "reviewed", (path, field, row))
        for path in sorted((HISTORY / "story").glob("*.json")):
            payload = read(path)
            for row in payload["historical_context"] + payload["participant_context"]:
                self.assertEqual(row["review_status"], "reviewed", (path, row))
        for path in sorted((HISTORY / "relation").glob("*.json")):
            self.assertEqual(read(path)["review_status"], "reviewed")

    def test_scholarly_and_citation_layers_remain_references(self):
        found_scholarly = False
        for path in sorted((HISTORY / "person").glob("*.json")):
            for ref in read(path)["scholarly_refs"]:
                found_scholarly = True
                self.assertIn(ref["kind"], {"scholarly", "citation"})
                self.assertNotEqual(ref["kind"], "fact")
        self.assertTrue(found_scholarly)
        for path in sorted((HISTORY / "evidence").glob("*.json")):
            payload = read(path)
            if payload["kind"] == "scholarly_reference":
                self.assertIn(payload["source_layer"], {"liu_annotation", "jianshu_note", "collation_note"})

    def test_lazy_loader_has_runtime_fetch_and_cache_contract(self):
        loader = (ROOT / "site/src/historical.ts").read_text(encoding="utf-8")
        self.assertIn("fetch(projectionUrl", loader)
        self.assertIn("projectionCache", loader)
        self.assertIn("AbortSignal", loader)
        self.assertNotIn("import(\"./generated/history", loader)
        app = (ROOT / "site/src/App.tsx").read_text(encoding="utf-8")
        self.assertNotIn('import "./generated/history', app)
        self.assertNotIn("fetchHistoricalCorpus", app)

    def test_manifest_has_only_relative_nonvolatile_metadata(self):
        manifest_path = HISTORY / "manifest.json"
        manifest = read(manifest_path)
        self.assertNotIn("manifest.json", manifest["shards"])
        self.assertTrue(all(not path.startswith("/") for path in manifest["source_hashes"]))
        text = manifest_path.read_text(encoding="utf-8")
        for volatile_key in ("generated_at", "timestamp", "build_time", "built_at"):
            self.assertNotIn(volatile_key, text)
        self.assertNotIn(str(ROOT), text)

    def test_summary_shards_do_not_contain_large_source_payloads(self):
        for kind in ("person", "story", "era", "relation"):
            for path in (HISTORY / kind).glob("*.json"):
                self.assertLess(path.stat().st_size, 1_000_000, path)
                text = path.read_text(encoding="utf-8")
                self.assertNotIn("quoted_passage", text)
                self.assertNotIn("evidence_excerpt", text)
                self.assertNotIn("model_score", text)

    def test_size_budget_audit_passes(self):
        audit = read(ROOT / "data/derived/ux1-frontend-size-audit.json")
        comparison = audit["comparison"]
        self.assertLessEqual(comparison["sc1_site"]["delta_percent"], 2)
        self.assertLessEqual(comparison["entry_js"]["gzip_delta_percent"], 8)
        self.assertLessEqual(comparison["initial_total"]["delta_percent"], 5)

    def test_projection_rebuild_is_deterministic(self):
        def snapshot():
            return {path.relative_to(HISTORY).as_posix(): sha256(path) for path in HISTORY.rglob("*.json")}

        before = snapshot()
        subprocess.run(
            ["python3", "scripts/build_ux1_historical_projection.py"],
            cwd=ROOT,
            check=True,
            stdout=subprocess.DEVNULL,
        )
        first = snapshot()
        subprocess.run(
            ["python3", "scripts/build_ux1_historical_projection.py"],
            cwd=ROOT,
            check=True,
            stdout=subprocess.DEVNULL,
        )
        second = snapshot()

        def changed(left, right):
            return sorted(path for path in set(left) | set(right) if left.get(path) != right.get(path))

        self.assertEqual(before, first, f"committed projection differs after rebuild: {changed(before, first)}")
        self.assertEqual(first, second, f"consecutive projection rebuilds differ: {changed(first, second)}")


if __name__ == "__main__":
    unittest.main()
