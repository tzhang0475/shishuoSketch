"""SFH1 semantic-first historical parsing.

Semantic authority belongs to the model.  Deterministic authority belongs to
Python.  This package is an additive candidate-only experiment and has no
canonical write path.

SFH2R.1 hardens candidate retrieval so short names, courtesy names, titles and
profile observed surfaces remain contextual hints rather than global identity
answers.  L3 referent hints and narrative/source roles are carried forward so
registry misses do not erase semantic judgments already made by the LLM.
"""

from .common import MODEL, RUN_VERSION
from . import candidate_retrieval as _candidate_retrieval
from .retrieval_policy_v3 import install as _install_retrieval_policy_v3

_install_retrieval_policy_v3(_candidate_retrieval)

__all__ = ["MODEL", "RUN_VERSION"]
