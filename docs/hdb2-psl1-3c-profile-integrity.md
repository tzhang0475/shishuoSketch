# HDB2-PSL1.3C — Candidate Profile Integrity

PSL1.3C is an isolated, candidate-only repair on top of the frozen
PSL1.3B run. It does not issue semantic/API calls and does not change the
PSL weights, thresholds, canonical Persons, relations, or prior experiment
artifacts.

## Repairs

- HDB2-F Person profile forms are admitted only from an exact occurrence
  identity decision with form-level provenance. Same-Story participation,
  relation neighborhoods, comparison syntax, unresolved observations, and
  candidate clustering are not alias or courtesy-name evidence.
- A missing, malformed, truncated, or otherwise invalid reviewer response can
  no longer leave a required stable resolution in place. The candidate is
  always demoted to `review_required` so the failed safety gate is visible to
  a human reviewer.
- Single-character surfaces are not lexicalized from a catalogue alias alone.
  Local occurrence names and explicit comparison syntax are retained as audit
  hypotheses/distinctness signals, not as global identity propagation.
- Office structure retains a holder only when the local construction and its
  evidence ID prove that holder; structural anchors and patrons remain
  separate from the referent.

## Profile provenance

Each profile form carries `form_provenance` with the surface, form type,
Person/candidate key, occurrence and identity-observation IDs, evidence ref,
identity state, and identity basis. `contextual_name_projection` remains
distinct from direct identity evidence and is never promoted to canonical
truth.

## Replay

The committed PSL1.3B ten-Story selection is reused byte-for-byte. Its saved
raw/model records are replayed offline into
`data/generated/hdb2-psl1-3c/`; no new DeepSeek call is made. The C protected
input contract keeps canonical, reviewed, frozen semantic, and prior raw
artifacts immutable while allowing the two explicitly regenerated
candidate-only HDB2-F profile projections.

The profile integrity audit is at
`data/derived/hdb2-f-profile-integrity-audit.json`. It records removed known
contamination, provenance coverage, orphan forms, cross-person surface
collisions, and known-regression status.
