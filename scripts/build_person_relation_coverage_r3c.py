#!/usr/bin/env python3
"""Write the deterministic R3C coverage audit and candidate artifacts."""

from person_relation_coverage_r3c import build


if __name__ == "__main__":
    for path in build():
        print(path)
