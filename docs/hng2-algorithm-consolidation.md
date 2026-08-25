# HNG2-C — Historical Context Algorithm Consolidation

HNG2-C.3 freezes the contextual historical extraction algorithm. The two
semantic lanes share evidence selection and strict item-level validation but
remain separate:

    Person
    SELECT
    → READ EVIDENCE ATOMS
    → GROUND
    → FILL
    → RESOLVE / NORMALIZE
    → CANDIDATE DB

    Temporal
    SELECT
    → VISIBLE ANCHOR SCAN
    → READ TEMPORAL ATOMS
    → GROUND
    → FILL
    → H0A NORMALIZATION
    → CANDIDATE DB

Python chooses the target and evidence windows, owns all identifiers, checks
exact provenance, reuses the existing historical entity resolver, normalizes
broad relation classes, and consults H0A for temporal normalization. The
output is candidate-only and cannot write canonical history.

DeepSeek receives only the selected target or Story and the already-selected
source passages. Person READ returns literal EvidenceAtoms; Person FILL maps
validated pointers into a bounded entity/relation card. Temporal READ receives
the same evidence plus lexical-only visible-anchor hints and decides their
contextual role; Temporal FILL maps validated pointers into a bounded temporal
card. DeepSeek never creates IDs, decides canonical truth, or controls
retrieval.

The visible-anchor scan is deterministic lexical recall only. A visible ruler,
reign, event, or explicit date string is not automatically Story time. Its
role—scene time, background, later outcome, quoted precedent, relative person
time, office context, or uncertainty—remains a contextual semantic decision,
and Python validates exact provenance before H0A-compatible normalization.

The default path deliberately excludes the earlier experimental controllers:

- large strict cards;
- SearchPlan model calls;
- recursive ResearchGap loops;
- SC2-P unresolved-observation follow-up;
- the unified Person + Temporal card;
- the one-pass HNG2-C card;
- multi-round discovery and frontier expansion;
- GraphRAG, embedding retrieval, and web search.

Those paths remain historical/experimental reference implementations. They
are not dependencies of the consolidation runner.

H0A remains the historical temporal backbone. E0/E0.1 remain reader-facing
projections; HNG2-C does not create a competing chronology system and does not
upgrade H0A anchors.
