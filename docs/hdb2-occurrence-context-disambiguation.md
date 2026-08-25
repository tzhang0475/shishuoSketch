# HDB2-P1.1 — Occurrence-Level Contextual Identity Disambiguation

This pilot tests a single boundary: an abbreviated or ambiguous historical
surface is resolved per textual occurrence, not as one global surface
cluster.

## Frozen input and algorithm

The input is an offline projection of HDB1 and HDB2-P1 observations.  Each
selected observation becomes its own `ContextualIdentityCase` with a Story
window, local annotation context, local relations, temporal context, and a
Python-generated candidate set.  No new corpus search is performed.

```text
HDB1/HDB2-P1 observation
  → occurrence split
  → Python candidate generation and dossier
  → one strict DeepSeek contextual-disambiguation call
  → Python evidence/candidate/hard-constraint validation
  → occurrence-level candidate decision
```

The model sees only local candidate keys (`c0`, `c1`, …), supplied evidence
IDs, and the restrained context packet.  It never receives production Person
IDs and never writes a Person, relation, or canonical fact.

The final states are `explicit_resolved`, `contextually_resolved`,
`contextually_preferred`, `unresolved`, `compositional_reference`, and
`not_person`.  A contextual resolution requires high model confidence, two
independent support families, and no Python hard conflict.  Confidence alone
does not resolve an occurrence.

Expressions such as `庾亮兒`, `X子`, `X女`, and `X弟` are compositional
kinship references.  They do not resolve to the base Person.  Ruler/title
surfaces are kept distinct from ordinary catalogue aliases, and all evidence
references are validated against the exact supplied passage text.

## Comparison

Each result is compared with the prior HDB2-P1 surface-cluster decision.  The
comparison can therefore show a split of one surface into multiple Persons,
correction of a base-person collapse, a newly preferred/resolved occurrence,
or a remaining unresolved occurrence.  This is a candidate/audit projection;
it does not alter HDB1, HDB2-P1, the Person catalogue, or canonical history.

## Outputs

Selection is frozen in
`data/annotation/hdb2-p1-1-occurrence-selection.json`.  The offline cases are
in `data/derived/hdb2-p1-1-occurrence-cases.json`.  Live run artifacts are
under `data/generated/hdb2-p1-1/live/<run_id>/`, with review and comparison
projections under `data/annotation/` and `data/derived/`.
