# SFH2.2-A2O — Occurrence Semantics Decomposition

SFH2.2-A2O is an isolated offline/live pilot for occurrence semantics. The
historical-person identity result is frozen by SFH2.2-A2GR and is supplied as
context; A2O never re-resolves or replaces it.

The pilot separates two concepts that the earlier `occurrence_role` field
mixed together:

1. `provenance_layer` is copied deterministically from the target's
   `source_evidence_id` and that evidence row's explicit `source_layer`.
2. `narrative_function` is the only new semantic judgment made by the
   Occurrence Semantic Historian.

The compatibility role used by older consumers is then projected from the two
structured values. That projection is generic: it has no Chinese surface
table, name dictionary, substring rule, or identity lookup. It does not decide
who a person is.

## Pilot cohort and Gold

The deterministic 26-case cohort contains the six reviewed role cases from
A2G/A2GR and all 20 frozen A0R-L challenge mentions across the five challenge
Stories. The selection file contains only occurrence and source metadata; it
does not contain expected answers and is not chosen from model outputs.

`data/annotation/sfh2-a2o-evaluation-gold.json` is a separate human-reviewed
authority for the occurrence-function experiment. It carries the six A2GR role
decisions forward and records source-grounded reviews for the challenge
occurrences. Identity references in it are context/provenance for the frozen
identity input, not new identity resolution.

## Authority and safety

The provider receives the exact target evidence, nearby source evidence,
structural provenance, and frozen identity context. It is explicitly told that
identity is not under review and may return only the compact function result.
The strict tool schema has no identity, canonical, relation, or legacy-role
output fields. Python validates case/evidence IDs and types, derives
provenance, performs the compatibility projection, and writes candidate-only
artifacts. No Person, canonical fact, alias, or profile is created or mutated.

Raw provider envelopes are written to an external temporary witness directory
and are not committed in `data/generated/sfh2-a2o/`. The compact outputs retain
parsed results, usage/latency accounting, and hashes sufficient to audit the
run. Offline replay consumes the compact live result and makes no provider
calls.

## Interpretation

The important contrast is `滔` and `嘏`: each is a participant in the Liu
annotation narrative, but neither is a participant in the Shishuo main-text
scene. A2O can represent that distinction as
`liu_annotation + participant`, which projects to the legacy
`annotation_person` role. `薛瑩`, `齊桓公`, `王師`, and `字景真` retain their
source/citation, exemplum, collective, and attribute functions respectively.

The result and recommendation are recorded in
`data/generated/sfh2-a2o/`. A successful pilot may hand off to
`SFH2.2-F-prep`; it does not start the 188-Story production run automatically.
