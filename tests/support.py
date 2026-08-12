from __future__ import annotations

import os
from pathlib import Path
import unittest


def skip_if_portable_payload_missing(
    testcase: unittest.TestCase,
    root: Path,
    *relative_paths: str,
) -> None:
    """Keep source-payload tests strict locally and explicit in portable CI."""
    if (
        os.environ.get("WP1_PROVENANCE_MODE") != "portable"
        or os.environ.get("SHISHUO_SKIP_SOURCE_PAYLOAD_TESTS") != "1"
    ):
        return
    missing = [path for path in relative_paths if not (root / path).exists()]
    if missing:
        testcase.skipTest(
            "portable CI does not download ignored source payloads: " + ", ".join(missing)
        )
