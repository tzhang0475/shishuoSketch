#!/usr/bin/env python3
"""Build the deterministic P3A Person expansion analysis artifacts."""

from person_expansion import build


if __name__ == "__main__":
    for path in build():
        print(path)
