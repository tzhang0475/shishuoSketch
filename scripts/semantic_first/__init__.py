"""SFH1 semantic-first historical parsing.

Semantic authority belongs to the model.  Deterministic authority belongs to
Python.  This package is an additive candidate-only experiment and has no
canonical write path.

SFH2R.1 hardens candidate retrieval so short names, courtesy names, titles and
profile observed surfaces remain contextual hints rather than global identity
answers.  The installed policy does not infer semantics; it only restricts
what deterministic retrieval is allowed to claim.
"""

from .common import MODEL, RUN_VERSION
from . import candidate_retrieval as _candidate_retrieval
from .retrieval_policy_v2 import install as _install_retrieval_policy_v2

_install_retrieval_policy_v2(_candidate_retrieval)

__all__ = ["MODEL", "RUN_VERSION"]
