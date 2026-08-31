"""Read-only access to the frozen A0 selection for the A0R replay."""

from __future__ import annotations

from typing import Any, Mapping

from sfh2_a0.selection import build_selection as _build_selection
from sfh2_a0.common import load_inputs


def build_selection(inputs: Mapping[str, Any] | None = None) -> dict[str, Any]:
    return _build_selection(inputs or load_inputs())
