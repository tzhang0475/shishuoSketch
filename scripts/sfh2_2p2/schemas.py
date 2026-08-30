"""P2 schema facade.

The blind run uses the exact P1 strict tools and validators.  Re-exporting
them here makes the dependency explicit without creating a second semantic
contract.
"""

from sfh2_2p1.schemas import (  # noqa: F401
    entity_proposal_tool,
    identity_equivalence_tool,
    validate_entity_proposal_payload,
    validate_equivalence_payload,
)
