from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from scripts.materialize_frontend_routes import materialize_routes


class FrontendRouteMaterializationTests(unittest.TestCase):
    def test_route_shells_copy_root_index_exactly_and_are_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            dist = Path(temporary) / "dist"
            dist.mkdir()
            content = b'<html><script src="/assets/index.js"></script></html>\n'
            (dist / "index.html").write_bytes(content)

            first = materialize_routes(dist)
            first_bytes = {path: path.read_bytes() for path in first}
            second = materialize_routes(dist)
            second_bytes = {path: path.read_bytes() for path in second}

            self.assertEqual(first, second)
            self.assertEqual(first_bytes, second_bytes)
            self.assertEqual(set(first_bytes.values()), {content})
            self.assertEqual((dist / "index/index.html").read_bytes(), content)
            self.assertEqual((dist / "review/irr0/index.html").read_bytes(), content)
            self.assertEqual((dist / "review/hdb2/index.html").read_bytes(), content)

    def test_route_materialization_requires_root_shell(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            with self.assertRaises(FileNotFoundError):
                materialize_routes(Path(temporary) / "dist")

    def test_build_and_pages_workflow_wire_route_materialization(self) -> None:
        root = Path(__file__).resolve().parents[1]
        package = json.loads((root / "package.json").read_text(encoding="utf-8"))
        workflow = (root / ".github/workflows/deploy-pages.yml").read_text(encoding="utf-8")

        self.assertIn("python3 scripts/materialize_frontend_routes.py", package["scripts"]["build:site"])
        self.assertIn("test -f dist/index/index.html", workflow)
        self.assertIn("test -f dist/review/irr0/index.html", workflow)
        self.assertIn("test -f dist/review/hdb2/index.html", workflow)


if __name__ == "__main__":
    unittest.main()
