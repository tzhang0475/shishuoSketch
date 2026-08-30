"""SFH2/HIR1 candidate-only identity consolidation package.

SFH2 consumes the frozen SFH1 semantic representation.  It never writes to
the production Person, relation, temporal, or family stores.

SFH2R.1 installs reviewed semantic-precedence retrieval, carries LLM referent
hints/source roles into observations, and lets those hints expand candidate
sets without granting Python semantic authority.
"""

from .common import OUTPUT_ROOT
from . import consolidation as _consolidation
from .semantic_precedence_retrieval import install as _install_semantic_precedence_retrieval
from .semantic_hint_retrieval import install as _install_semantic_hint_retrieval
from . import inputs as _inputs
from . import projections as _projections
from .graph_role_policy import install as _install_graph_role_policy
from .semantic_observation_bridge import install as _install_semantic_observation_bridge

_install_semantic_precedence_retrieval(_consolidation)
_install_semantic_hint_retrieval(_consolidation)
_install_semantic_observation_bridge(_inputs)
# ``pipeline`` imports these projection callables after package initialization.
# Install the occurrence-level role policy on the module that actually owns
# them; keeping the wrapper here avoids a second graph implementation and
# makes source-only semantic roles effective in every SFH2 entry point.
_install_graph_role_policy(_projections)

__all__ = ["OUTPUT_ROOT"]
