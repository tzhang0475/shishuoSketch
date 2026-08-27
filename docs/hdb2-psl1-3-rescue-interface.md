# HDB2-PSL1.3 — Rescue interface

PSL1.3 is an additive validation layer over the frozen PSL1.1/PSL1.2
occurrence resolver.  It changes the candidate-rescue diagnostic contract;
it does not change the identity algorithm, canonical data, or the earlier
experimental artifacts.

## Interface

The rescue call is forced through the DeepSeek strict function
`submit_hdb2_candidate_rescue_interface`.  Its response separates:

- `surface_type`: the linguistic form (`person_name`, `courtesy_name`,
  `office_title`, `ruler_title`, `kinship_reference`, or `other`);
- `referent_type`: what the form may denote (`person`, `ruler`,
  `non_person`, or `uncertain`); and
- per-candidate grounded assessments.

`candidate_set_sufficient` is valid only when a supplied candidate is
explicitly supported by supplied evidence.  A title or ruler form may still
refer to a person/ruler.  A missing-candidate diagnosis is only a hint: it
never changes state and cannot create a Person ID.

## Grounding boundary

Python validates every candidate and evidence ID against the exact packet
before using the diagnostic.  Proposed surfaces and search hints must be
visible in the supplied evidence.  Python then searches the registered local
historical witnesses and admits only source-grounded identity-bearing rows.
Traditional/variant matching is used for lookup, while the stored source
reference and exact witness span remain unchanged.  Invalid model payloads
are audit failures and cannot mutate the candidate graph.

The existing PSL1.1 contextual predicate and adversarial review calls are
reused unchanged.  Any grounded candidate is added as a local candidate and
the frozen inference/reviewer path is rerun.  Existing catalogue candidates
are not duplicated, and no model output is trusted as a Person ID.

## Frozen validation scope

The selection is ten occurrences from ten Stories in the untouched HDB2-F
occurrence ledger, excluding prior PSL0/PSL1/PSL1.1/PSL1.2 selections.  The
selection is frozen before provider access.  The run is candidate-only and
does not write canonical or reviewed data.  Offline interface regressions
cover `劉尹`, `朕`, `陛下`, `中丞`, `阮光禄`, `聘`, and `鳯`; the latter two
also verify direction/variant-aware grounded lookup.

The live runner performs the existing contextual/reviewer calls followed by
at most one rescue-interface call for each eligible occurrence.  It permits
only the existing transport/parse retry behavior.  Replay revalidates saved
packets and responses without API access and rebuilds the deterministic
candidate state.

All outputs under `data/generated/hdb2-psl1-3/` are experimental audit data.
They do not alter HDB2-F decisions, canonical Persons, relations, or
historical source files.
