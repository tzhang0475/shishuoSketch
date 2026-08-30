"""SFH2.2-P bounded semantic identity-resolution pilot.

The pilot is deliberately isolated from the SFH1/SFH2 production projections.
It consumes frozen SFH1 reading packets and writes candidate-only evaluation
artifacts under ``data/generated/sfh2-2p``.
"""

from .common import MODEL, SCHEMA_VERSION

__all__ = ["MODEL", "SCHEMA_VERSION"]
