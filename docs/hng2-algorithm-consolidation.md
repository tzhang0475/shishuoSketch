# HNG2-C — Historical Context Algorithm Consolidation

HNG2-C defines the mainline historical semantic extraction path:

    existing local evidence
    → small contextual evidence bundle
    → DeepSeek Historical Evidence Card
    → Python evidence validation
    → identity/relation/temporal normalization
    → candidate historical projection

Python chooses the target and evidence windows, owns all identifiers, checks
exact provenance, reuses the existing historical entity resolver, normalizes
broad relation classes, and consults H0A for temporal normalization. The
output is candidate-only and cannot write canonical history.

DeepSeek receives only the selected target and source passages. It returns
the compact entities, relations, and temporal_assertions card through a
strict function call. It does not receive candidates, graph state, a
ResearchGap, or prior model interpretation. It does not create IDs, decide
canonical truth, or control retrieval.

The default path deliberately excludes the earlier experimental controllers:

- large strict cards;
- SearchPlan model calls;
- recursive ResearchGap loops;
- SC2-P unresolved-observation follow-up;
- multi-round discovery and frontier expansion;
- GraphRAG, embedding retrieval, and web search.

Those paths remain historical/experimental reference implementations. They
are not dependencies of the consolidation runner.

H0A remains the historical temporal backbone. E0/E0.1 remain reader-facing
projections; HNG2-C does not create a competing chronology system and does not
upgrade H0A anchors.
