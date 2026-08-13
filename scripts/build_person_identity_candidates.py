#!/usr/bin/env python3
"""Build deterministic P3A.1 open-world identity discovery artifacts."""

from person_identity_discovery import build


if __name__ == "__main__":
    for path in build():
        print(path)
