"""SFH2/HIR1 candidate-only identity consolidation package.

SFH2 consumes the frozen SFH1 semantic representation.  It never writes to
the production Person, relation, temporal, or family stores.

SFH2R.1 installs a reviewed semantic-precedence retrieval policy before the
pipeline imports consolidation functions.  The compatibility install keeps
legacy replay code available while disabling unsafe substring-based identity
candidate generation.
"""

from .common import OUTPUT_ROOT
from . import consolidation as _consolidation
from .semantic_precedence_retrieval import install as _install_semantic_precedence_retrieval

_install_semantic_precedence_retrieval(_consolidation)

__all__ = ["OUTPUT_ROOT"]
