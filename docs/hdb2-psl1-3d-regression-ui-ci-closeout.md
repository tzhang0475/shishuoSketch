# HDB2-PSL1.3D closeout

HDB2-PSL1.3D is a boundary repair over the frozen HDB2 occurrence
decisions.  It does not issue semantic/API calls and does not write
canonical history.

## Root causes and fixes

The remaining `仲文` problem was a source-level identity-claim collision,
not merely profile propagation: the HDB1 direct catalogue match cited
`仲文` inside a context that explicitly names `殷仲文`.  The profile builder
now applies the source-local support gate before admitting a form, and writes
`data/derived/hdb2-f-identity-claim-integrity-audit.json` with the retained or
rejected claim, evidence coordinates, source context, and reason.  The frozen
HDB1/HDB2 observations themselves remain unchanged.  This keeps valid
occurrence-scoped forms such as `仲文` in 09-pinzao-045 while rejecting the
09-pinzao-088 collision.  Profile forms retain exact occurrence/evidence
provenance; a relation neighbor or co-occurring name is not an alias.

The existing rescue grounding remains fail-closed and uses independently
grounded catalogue, source-local, annotation, explicit name-marker, title,
ruler, and variant evidence.  It does not restore surface-wide propagation.

XE0 now has an explicit `hdb2-xe0-baseline-v2` contract.  Its immutable
protected hash set covers the HDB2-F semantic occurrence/fact projections;
the candidate-only HDB2-F profile projections are handled by the separately
versioned `hdb2-f-profile-integrity-v2` transition.  Thus an authorized
candidate-profile rebuild is visible and reproducible without allowing
canonical or reviewed-data drift.

The HDB2 review projection now presents structural roles separately and
does not show an anchor, patron, or office-context person as an accepted
referent.  Reviewer-facing fields are presentation data; they do not alter
the HDB2-F semantic frontier.

## Frozen replay

The PSL1.3D replay uses the existing PSL1.3C ten-Story set, rebuilds only the
candidate-only profile projection, and makes zero API calls.  The C safety
regressions remain intact: no forbidden stable identity survives, the
`仲文@09-pinzao-088` source claim is audited as rejected, and profile forms
remain fully provenance-backed.

## Portable and live CI behavior

GitHub Pages runs offline/replay validation, the portable test suite, and the
frontend build.  It does not invoke live provider experiments.  Live
validation scripts remain explicitly opt-in and retain their preflight
classification; an unavailable provider is not a semantic result, while a
reachable provider's schema or transport failure remains visible.  Raw
ignored source-payload rebuild tests use the existing narrow portable skip
only when portable mode, explicit skipping, and the actual missing payload
all agree.

## Validation record

Focused HDB2-PSL1.3D, review-projection, and XE0 tests pass offline.  HDB2-C
and C.1/C.2/C.3 validators, H0A/H0B validators, and HNG2 closeout replay are
run as part of the closeout.  Final portable-suite and frontend results are
recorded in the handoff accompanying the commit; no canonical or historical
dataset is regenerated.

Known limitation: this environment may not have a live DeepSeek endpoint.
That affects only optional provider validation, not the deterministic replay
or committed artifact checks.
