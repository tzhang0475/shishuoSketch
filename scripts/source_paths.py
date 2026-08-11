"""Resolve repository source paths from ``config/sources.yaml``.

This small module is shared by processing and audit scripts so a migrated
witness has one configured default path and an explicit command-line or API
override can still be used when required.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping


DEFAULT_CONFIG_PATH = Path("config/sources.yaml")
DEFAULT_STRUCTURAL_REFERENCE = Path(
    "sources/local/shishuo/reference-txt/shishuo.txt"
)


def load_sources_config(config_path: Path | str = DEFAULT_CONFIG_PATH) -> Mapping[str, Any]:
    """Load and minimally validate the repository source configuration."""

    try:
        import yaml  # type: ignore
    except ImportError as error:  # pragma: no cover - environment dependent
        raise ValueError("PyYAML is required to read the source configuration") from error

    path = Path(config_path)
    with path.open(encoding="utf-8") as handle:
        config = yaml.safe_load(handle)
    if not isinstance(config, Mapping):
        raise ValueError(f"source configuration is not a mapping: {path}")
    sources = config.get("sources")
    if not isinstance(sources, Mapping):
        raise ValueError(f"source configuration has no sources mapping: {path}")
    return config


def repository_root_for_config(config_path: Path | str) -> Path:
    """Return the repository root against which relative config paths resolve."""

    path = Path(config_path).resolve()
    if path.parent.name == "config":
        return path.parent.parent
    return path.parent


def resolve_source_path(
    config_path: Path | str,
    work: str,
    role: str,
) -> Path:
    """Resolve one configured work/role path without changing its value."""

    config = load_sources_config(config_path)
    works = config["sources"]
    work_config = works.get(work)
    if not isinstance(work_config, Mapping):
        raise ValueError(f"source configuration has no entry for {work}")
    value = work_config.get(role)
    if not value:
        raise ValueError(f"source configuration has no {role} path for {work}")
    path = Path(str(value))
    if not path.is_absolute():
        path = repository_root_for_config(config_path) / path
    return path


def resolve_structural_reference(
    config_path: Path | str = DEFAULT_CONFIG_PATH,
) -> Path:
    """Resolve the configured Shishuo structural-reference witness."""

    return resolve_source_path(config_path, "shishuo", "structural_reference")


def resolve_primary_source(config_path: Path | str, work: str) -> Path:
    """Resolve the configured primary source root for a work."""

    return resolve_source_path(config_path, work, "primary")
