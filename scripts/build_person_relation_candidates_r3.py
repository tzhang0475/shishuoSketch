#!/usr/bin/env python3
"""Build R3A explicit Person Relation candidate artifacts."""

from person_relation_candidates_r3 import build


if __name__ == "__main__":
    for path in build():
        print(path)
