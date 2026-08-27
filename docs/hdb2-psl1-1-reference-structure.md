# HDB2-PSL1.1 — Reference-Structure Safety Patch

PSL1.1 is a candidate-only safety layer over the frozen HDB2-PSL1
collective identity experiment.  It does not change PSL1 weights, the
historical corpus, canonical identities, or reviewed facts.

## Reference structure

Before identity inference, Python derives a small occurrence structure:

```text
reference_head
reference_type
holder
anchor_person
patron_or_possessor
syntactic_role
explicit_distinct_mentions
```

The structure keeps roles separate.  In `何充爲敦主簿`, 何充 is the office
holder and 敦 is the patron/possessor; `敦主簿` is not an alias for 王敦.  In
`王敦初尚主`, 主 is the marriage object and cannot resolve to the actor 王敦.
Explicitly separate local mentions receive a hard `Distinct` veto.  A
grounded kinship/name clue can add a catalogue candidate, but does not assert
identity by itself.

Alias and office predicates use exact referential forms.  Substring
containment, nearby occurrence, patronage, or co-occurrence is not identity
evidence.  Where the supplied source has an explicit syntactic holder
assignment such as `謝鯤爲長史`, the holder is retained as a direct reference
support path for the office mention; this is distinct from an alias match.

## Reviewer boundary

The existing PSL1 predicate and reviewer schemas remain the wire contract.
PSL1.1 applies the reference vetoes before scoring and applies valid
adversarial reviewer output fail-closed after scoring.  A reviewer rejection
cannot leave a non-direct candidate in a stable state.  Invalid payloads,
including the literal string `"null"` for a candidate key, do not mutate
state.

## Validation

The 44 PSL1 cases are replayed offline from the frozen PSL1 responses.  A
separate deterministic selection of ten existing-Person occurrences is frozen
before the live validation calls.  Only those ten cases receive new
predicate/reviewer calls; no retrieval, recursive controller, or canonical
write is involved.

All packets expose local candidate keys and supplied evidence only.  Provider
Person IDs are retained in Python-side candidate data for validation and are
never sent as answer labels.  Outputs and decisions are candidate-only.
