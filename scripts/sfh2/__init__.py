"""SFH2/HIR1 candidate-only identity consolidation package.

SFH2 consumes the frozen SFH1 semantic representation.  It never writes to
the production Person, relation, temporal, or family stores.
"""

from .common import OUTPUT_ROOT

__all__ = ["OUTPUT_ROOT"]
