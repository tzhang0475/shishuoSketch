from __future__ import annotations

import unittest

from scripts.run_test_suite import MODE_TO_CLASSIFICATION, load_classification, selected_test_paths


class TestSuiteRunnerContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.document = load_classification()

    def test_each_contract_has_existing_classified_modules(self) -> None:
        for classification in MODE_TO_CLASSIFICATION.values():
            paths = selected_test_paths(self.document, classification)
            self.assertEqual(paths, sorted(set(paths)))
            self.assertTrue(all(path.startswith("tests/") and path.endswith(".py") for path in paths))

    def test_current_contract_excludes_retired_ds_tests(self) -> None:
        paths = {
            row["path"]
            for row in self.document["tests"]
            if row["classification"] == "CURRENT_REQUIRED"
        }
        self.assertTrue(paths)
        self.assertNotIn("tests/test_ds1.py", paths)
        self.assertNotIn("tests/test_ds1_2.py", paths)
        self.assertNotIn("tests/test_ds1_2r.py", paths)
        self.assertNotIn("tests/test_ds2.py", paths)

    def test_active_ds21a_contract_remains_registered(self) -> None:
        paths = {row["path"] for row in self.document["tests"]}
        self.assertIn("tests/test_ds2_1a.py", paths)


if __name__ == "__main__":
    unittest.main()
