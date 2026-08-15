#!/usr/bin/env python3
"""Acquire the registered Zizhi Tongjian Kanripo witnesses.

The source payloads under ``sources/downloads/zizhi-tongjian`` are ignored by
Git, just like the existing historical-source payloads.  This command copies
only the immutable Kanripo text files and a small README from a checked-out
upstream repository, then records the upstream revision and exact file hashes
in a committed lock manifest.  It never edits a source character.

For reproducible local processing, an existing checkout can be supplied with
``--from-clone slug=/path``.  Without that option the command performs a
shallow clone of the approved repository into a temporary directory.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[1]
DOWNLOAD_ROOT = ROOT / "sources/downloads/zizhi-tongjian"

TARGETS: dict[str, dict[str, str]] = {
    "kanripo-wyg": {
        "witness_id": "zizhi-tongjian-kanripo-wyg",
        "work": "資治通鑑",
        "edition": "文淵閣四庫全書 / WYG",
        "repository": "https://github.com/kanripo/KR2b0007.git",
        "prefix": "KR2b0007_",
        "role": "primary-machine",
    },
    "kaoyi-kanripo": {
        "witness_id": "zizhi-tongjian-kaoyi-kanripo",
        "work": "資治通鑑考異",
        "edition": "四部叢刊 / SBCK",
        "repository": "https://github.com/kanripo/KR2b0008.git",
        "prefix": "KR2b0008_",
        "role": "critical-chronology",
    },
    "mulu-kanripo": {
        "witness_id": "zizhi-tongjian-mulu-kanripo",
        "work": "資治通鑑目錄",
        "edition": "文淵閣四庫全書 / WYG",
        "repository": "https://github.com/kanripo/KR2b0010.git",
        "prefix": "KR2b0010_",
        "role": "chronology-reference",
    },
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def source_commit(source_dir: Path) -> str:
    try:
        result = subprocess.run(
            ["git", "-C", str(source_dir), "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return "unavailable"
    return result.stdout.strip()


def clone_to_temp(repository: str) -> tuple[tempfile.TemporaryDirectory[str], Path]:
    temporary = tempfile.TemporaryDirectory(prefix="ztj0-source-")
    destination = Path(temporary.name) / "source"
    subprocess.run(
        ["git", "clone", "--depth", "1", repository, str(destination)],
        check=True,
    )
    return temporary, destination


def parse_from_clone(values: list[str]) -> dict[str, Path]:
    result: dict[str, Path] = {}
    for value in values:
        if "=" not in value:
            raise ValueError(f"--from-clone must use slug=/path: {value}")
        slug, raw_path = value.split("=", 1)
        if slug not in TARGETS:
            raise ValueError(f"unknown ZTJ0 source slug: {slug}")
        path = Path(raw_path).expanduser().resolve()
        if not path.is_dir():
            raise FileNotFoundError(f"source clone does not exist: {path}")
        result[slug] = path
    return result


def yaml_scalar(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False)


def write_small_metadata(slug: str, config: Mapping[str, str], lock: Mapping[str, Any]) -> None:
    target = DOWNLOAD_ROOT / slug
    metadata_lines = [
        f"schema: 1",
        f"witness_id: {yaml_scalar(config['witness_id'])}",
        f"work: {yaml_scalar(config['work'])}",
        f"edition: {yaml_scalar(config['edition'])}",
        f"role: {yaml_scalar(config['role'])}",
        f"source_provider: {yaml_scalar('Kanripo')}",
        f"remote_record: {yaml_scalar(config['repository'])}",
        f"upstream_commit: {yaml_scalar(lock['upstream_commit'])}",
        f"payload_policy: {yaml_scalar('ignored immutable upstream text; see manifest.lock.json')}",
    ]
    (target / "manifest.yaml").write_text("\n".join(metadata_lines) + "\n", encoding="utf-8")
    readme = (
        f"# {config['witness_id']}\n\n"
        f"Immutable Kanripo payload acquired from `{config['repository']}` at\n"
        f"commit `{lock['upstream_commit']}`. Raw `*.txt` files are ignored by\n"
        "Git. Exact file sizes and SHA-256 values are recorded in\n"
        "`manifest.lock.json`; processed data must never overwrite this witness.\n"
    )
    (target / "README.md").write_text(readme, encoding="utf-8")
    (target / "manifest.lock.json").write_text(
        json.dumps(lock, ensure_ascii=False, indent=2, sort_keys=False) + "\n",
        encoding="utf-8",
    )


def acquire_one(slug: str, source_dir: Path | None) -> dict[str, Any]:
    config = TARGETS[slug]
    temporary: tempfile.TemporaryDirectory[str] | None = None
    if source_dir is None:
        temporary, source_dir = clone_to_temp(config["repository"])
    try:
        commit = source_commit(source_dir)
        source_files = sorted(source_dir.glob(f"{config['prefix']}*.txt"), key=lambda path: path.name)
        if not source_files:
            raise FileNotFoundError(f"no {config['prefix']}*.txt files in {source_dir}")
        target = DOWNLOAD_ROOT / slug
        target.mkdir(parents=True, exist_ok=True)
        records: list[dict[str, Any]] = []
        for source_file in source_files:
            destination = target / source_file.name
            source_digest = sha256(source_file)
            if destination.exists():
                if sha256(destination) != source_digest:
                    raise ValueError(f"refusing to overwrite changed payload: {destination}")
            else:
                shutil.copyfile(source_file, destination)
            records.append(
                {
                    "source_file": source_file.name,
                    "source_path": f"sources/downloads/zizhi-tongjian/{slug}/{source_file.name}",
                    "source_bytes": source_file.stat().st_size,
                    "source_sha256": source_digest,
                    "upstream_commit": commit,
                }
            )
        lock_path = target / "manifest.lock.json"
        retrieval_date: str
        if lock_path.is_file():
            try:
                existing = json.loads(lock_path.read_text(encoding="utf-8"))
                retrieval_date = str(existing.get("retrieved_at") or "")
            except json.JSONDecodeError:
                retrieval_date = ""
        else:
            retrieval_date = ""
        if not retrieval_date:
            retrieval_date = datetime.now(timezone.utc).isoformat(timespec="seconds")
        lock = {
            "schema": 1,
            "stage": "ztj0-source-acquisition-lock",
            "witness_id": config["witness_id"],
            "work": config["work"],
            "edition": config["edition"],
            "role": config["role"],
            "source_provider": "Kanripo",
            "repository": config["repository"],
            "upstream_commit": commit,
            "retrieved_at": retrieval_date,
            "payload_policy": "git-ignored immutable upstream payload",
            "records": records,
        }
        write_small_metadata(slug, config, lock)
        return lock
    finally:
        if temporary is not None:
            temporary.cleanup()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--from-clone",
        action="append",
        default=[],
        metavar="SLUG=/PATH",
        help="use an existing checked-out approved repository instead of cloning it",
    )
    parser.add_argument(
        "--only",
        action="append",
        choices=sorted(TARGETS),
        help="acquire only the named source slug; may be repeated",
    )
    args = parser.parse_args()
    from_clones = parse_from_clone(args.from_clone)
    slugs = args.only or list(TARGETS)
    results = []
    for slug in slugs:
        lock = acquire_one(slug, from_clones.get(slug))
        results.append((slug, lock))
        print(f"acquired {slug}: {len(lock['records'])} files at {lock['upstream_commit']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
