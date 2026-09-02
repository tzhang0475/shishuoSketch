from __future__ import annotations

import json
from pathlib import Path
import subprocess
import tempfile
import unittest

from scripts.audit_repository_growth import audit_repository


POLICY = {
    "schema": "generated-artifact-lifecycle-policy-v1",
    "generated_roots": ["data/generated/"],
    "classes": {
        "GIT_COMPACT_RESULT": {},
        "EXTERNAL_ARCHIVE_DEFAULT": {},
        "EPHEMERAL_REBUILDABLE": {},
    },
    "default_git_policy": {
        "new_paths_only": True,
        "grandfather_existing_baseline_paths": True,
        "unclassified_generated_default_class": "GIT_COMPACT_RESULT",
        "unclassified_generated_is_explicit": False,
    },
    "thresholds": {
        "warn_generated_file_bytes": 10,
        "require_explicit_classification_bytes": 20,
    },
    "path_classifications": [
        {
            "pattern": "data/generated/**/raw-api/**",
            "artifact_class": "EXTERNAL_ARCHIVE_DEFAULT",
            "explicit": True,
        },
        {
            "pattern": "data/generated/**",
            "artifact_class": "GIT_COMPACT_RESULT",
            "explicit": False,
        },
    ],
    "allowed_exceptions": [],
}


class GeneratedArtifactLifecycleTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tempdir.name)
        (self.root / "data/generated").mkdir(parents=True)
        self._git("init", "-q")
        self._git("config", "user.email", "c3-test@example.invalid")
        self._git("config", "user.name", "C3 test")
        self.policy_path = self.root / "policy.json"
        self.policy_path.write_text(json.dumps(POLICY), encoding="utf-8")

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def _git(self, *args: str) -> str:
        return subprocess.check_output(["git", *args], cwd=self.root, text=True).strip()

    def _commit(self, message: str) -> str:
        self._git("add", ".")
        self._git("commit", "-qm", message)
        return self._git("rev-parse", "HEAD")

    def test_existing_large_payload_is_grandfathered(self) -> None:
        target = self.root / "data/generated/legacy/result.json"
        target.parent.mkdir(parents=True)
        target.write_bytes(b"x" * 25)
        baseline = self._commit("baseline")

        report = audit_repository(self.root, baseline=baseline, policy_path=self.policy_path, include_untracked=False)

        self.assertEqual(report["artifact_policy_violations"], [])
        self.assertEqual(report["new_generated_file_count"], 0)
        self.assertTrue(report["grandfathered_existing_generated_files"])

    def test_new_large_generated_file_is_a_new_violation(self) -> None:
        baseline = self._commit("empty baseline")
        target = self.root / "data/generated/new/result.json"
        target.parent.mkdir(parents=True)
        target.write_bytes(b"x" * 25)

        report = audit_repository(self.root, baseline=baseline, policy_path=self.policy_path, include_untracked=True)

        self.assertIn("data/generated/new/result.json", report["new_generated_files"])
        self.assertTrue(any(item["code"] == "new_large_generated_file_without_explicit_classification" for item in report["artifact_policy_violations"]))

    def test_new_raw_provider_response_requires_exception(self) -> None:
        baseline = self._commit("empty baseline")
        target = self.root / "data/generated/run/raw-api/response.json"
        target.parent.mkdir(parents=True)
        target.write_text("{}", encoding="utf-8")

        report = audit_repository(self.root, baseline=baseline, policy_path=self.policy_path, include_untracked=True)

        self.assertEqual(report["new_raw_provider_files"], ["data/generated/run/raw-api/response.json"])
        self.assertTrue(any(item["code"] == "new_generated_artifact_requires_approved_exception" for item in report["artifact_policy_violations"]))

    def test_approved_exception_allows_raw_provider_response(self) -> None:
        policy = dict(POLICY)
        policy["allowed_exceptions"] = [{
            "id": "test-raw-exception",
            "path_or_pattern": "data/generated/run/raw-api/response.json",
            "artifact_class": "EXTERNAL_ARCHIVE_DEFAULT",
            "reason": "fixture for a reviewed transport contract",
            "review_reference": "C3-test",
        }]
        self.policy_path.write_text(json.dumps(policy), encoding="utf-8")
        baseline = self._commit("empty baseline")
        target = self.root / "data/generated/run/raw-api/response.json"
        target.parent.mkdir(parents=True)
        target.write_text("{}", encoding="utf-8")

        report = audit_repository(self.root, baseline=baseline, policy_path=self.policy_path, include_untracked=True)

        self.assertEqual(report["artifact_policy_violations"], [])

    def test_normal_compact_generated_result_passes(self) -> None:
        baseline = self._commit("empty baseline")
        target = self.root / "data/generated/run/metrics.json"
        target.parent.mkdir(parents=True)
        target.write_text('{"count": 1}', encoding="utf-8")

        report = audit_repository(self.root, baseline=baseline, policy_path=self.policy_path, include_untracked=True)

        self.assertEqual(report["artifact_policy_violations"], [])
        self.assertEqual(report["new_generated_bytes"], target.stat().st_size)


if __name__ == "__main__":
    unittest.main()
