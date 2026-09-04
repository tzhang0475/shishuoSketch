#!/usr/bin/env python3
"""Run the offline SFH2.2-A2OSP Gold promotion audit."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

from sfh2_a2osp.common import OUT  # noqa: E402
from sfh2_a2osp.pipeline import run  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--offline", action="store_true", help="required offline mode; no provider is available")
    parser.add_argument("--output", type=Path, default=OUT)
    args = parser.parse_args(argv)
    if not args.offline:
        parser.error("A2OSP is offline-only; pass --offline")
    documents = run(args.output)
    evaluation = documents["a2or-post-promotion-evaluation.json"]
    post = evaluation["post_promotion_metrics"]["narrative_function"]
    print(f"A2OSP offline promotion: {evaluation['case_count']} cases; provider_calls=0; post_score={post['correct']}/{post['evaluable']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
