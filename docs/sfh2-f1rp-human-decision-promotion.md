# SFH2.2-F1RP — Human Decision Promotion & Production Policy Approval

This is an offline authority and policy stage based on the immutable SFH2.2-F1R
acceptance review. It does not rewrite F1/F1R predictions, active Gold, or
canonical data. Provider calls: **0**.

## Materialized decisions

Nine exact-occurrence human decisions were recorded in
`data/annotation/sfh2-f1rp-human-authority.json`. The active A2 Gold remains
unchanged. Eight reviewed production controls were carried forward; `康` is
kept only as an upstream-target-blocked control with no semantic label.

The reviewed decisions are:

- `子野` → `addressee`; the pinned nested occurrence is the recipient of the
  question, while the later reply occurrence is different.
- `堯` → `reference`; it is a temporal anchor inside the biography of 巢父.
- `剌史` and `湘州刺史` → `person_attribute`; office expressions are not
  historical-person identity targets.
- `孔巖` → `reference` and `爰` → `participant`; both A2OVB overrides are
  accepted as reviewed controls.
- `祥` remains `participant`, with reviewed reason-target drift.
- `江南` remains `reference`, with a non-person-compatible legacy fallback of
  `other`.
- `康` remains blocked until the upstream mention annotation is repaired.

The 11 F1R candidate entity groups are confirmed only in
`data/annotation/sfh2-reviewed-candidate-person-registry.json`. They are not
canonical Persons and cannot create canonical records.

## Approved production policy v2

`data/frozen/sfh2/production-policy-v2/` is a new approved policy namespace;
the historical F-prep/F1 policy remains unchanged. Reviewed candidate entity
hits are audit-only for entity reuse. Unresolved adjudication, degraded or
terminal provider paths, uncertain semantics, target drift, unsupported
projection, evidence-integrity failures, and upstream mention repair remain
mandatory review triggers. Boundary overrides and low confidence alone remain
audit-only.

Compatibility projection v2 consumes structured `provenance_layer`,
`narrative_function`, `entity_kind`, and `semantic_kind`. A known non-person
cannot emit the person-specific `annotation_person` role. The historical
`scripts/sfh2_a2o/provenance.py` projector is not changed.

## Queue impact and blocker

The stored F1 queue had 25 mandatory
occurrences. F1R's inactive policy-v2 counterfactual had
22. After
human decisions and reviewed-entity reuse, the approved policy yields
13 mandatory occurrences and
0 unconfirmed entity review units.
The remaining queue is dominated by degraded/terminal transport paths plus the
upstream `康` target and the invalid `剌史` boundary response.

F1's five invalid semantic responses and three terminal identity blocks are
carried into the handoff for **SFH2.2-F1RT**. No transport replay is performed
here, and F2 is blocked until that bounded recovery stage qualifies the failure
path.

## Safety boundary

All outputs remain candidate-only with `canonical_write_back=false`. The
protected snapshot digest is unchanged, and no active Gold, semantic-v1,
historical experiment output, SC1, canonical Person/alias/fact, or frontend
artifact was modified. F1/F1R outputs remain historical evidence rather than
retrospectively rewritten predictions.
