# HDB2-PSL1.3B — Conservative reference parsing

PSL1.3B is an additive validation layer over the frozen PSL1.3A semantic
pre-judgment boundary.  It changes only deterministic reference parsing:
office holders are assigned only when the holder and office occur in one
explicit, source-grounded construction.  A nearby person, arbitrary character
window, candidate order, or graph proximity is never a holder signal.

The provider-facing semantic tool, prompt, schema, predicate weights, review,
rescue behavior, and candidate-only protections are reused from PSL1.3A.
When an office/title surface is visible but its holder is not proven, the
derived structure keeps `holder`, `anchor_person`, and `referent_candidate`
empty/null and emits no positive syntactic office support.

The validation selection contains exactly ten occurrences from ten Stories.
Story-level exclusion is collected from prior PSL artifacts, documentation,
and tests before the selection is frozen.  The selection is stored at
`data/annotation/hdb2-psl1-3b-selection.json`; live and offline outputs are
isolated under `data/generated/hdb2-psl1-3b/`.

Required regressions include `僕射羊祜`, `司空劉琨`, `敦主簿` (holder 何充,
patron 敦), `武子`, `家兄`, `主`, and `謝豫章`.  This run is candidate-only;
it does not allocate production Person IDs, write canonical data, or modify
the previous PSL artifacts.
