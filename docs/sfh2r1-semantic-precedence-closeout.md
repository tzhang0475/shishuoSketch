# SFH2R.1 — Semantic Precedence Repair Sync and Closeout

SFH2R.1 is a deterministic closeout of the second manually reviewed semantic
repair pass.  It does not start a new Story wave, rerun the 188-Story LLM
pipeline, tune PSL, or write canonical history.  The authority files are
applied in order:

1. `data/annotation/sfh2r-manual-semantic-authority.json`
2. `data/annotation/sfh2r1-manual-semantic-authority.json`

Historical semantics in those files were reviewed by a human.  Python only
locates the named records, applies the exact evidence/status edits, validates
provenance, rebuilds derived candidate indexes, and enforces storage safety.

## Authority and materialized repairs

The second pass materializes four alias repairs in `data/aliases.json`:

* `伯倫` remains a valid form for 劉伶, but is `contextual` /
  `shared_or_contextual`; the 山該 witness
  `evidence-w3-person-ba50566714ba7c916e6e18b6` is removed from the active
  劉伶 evidence while the four reviewed 劉伶 witnesses remain.
* `王丞相` and `王大將軍` are suppressed from 王隱 and retain their removed
  witness provenance.  The active rows have no resolved Person IDs and do not
  create global 王導/王敦 aliases.
* `王庾諸公` is suppressed from 王隱 and reclassified as a collective
  reference, not a single-Person alias.

The active rows retain `sfh2r_manual_repair` and
`sfh2r1_manual_repair` traces.  The isolated
`data/generated/sfh2r1/alias-before-after.json` records before/after bytes,
removed evidence, retained evidence, and the authority hash.  Earlier
SFH2R snapshots remain audit witnesses and are not silently overwritten.

The active profile builder only admits canonical or occurrence-level identity
claims with valid identity provenance.  It does not turn a surface occurrence,
co-occurrence, relation neighbor, or `observed_count` into a global alias.
Shared courtesy/style/title forms remain contextual retrieval evidence; only
reviewed exact forms can be global exact keys.  In particular:

> Occurrence(surface S) → Person P does not imply Alias(P, S).

## Semantic precedence and referent hints

The active authority order is:

1. reviewed human semantic decision;
2. validated LLM semantic judgment;
3. soft collective consistency;
4. deterministic retrieval hint.

Python hard constraints can veto an unsafe write, but Python lexical or
nearest-neighbor heuristics cannot overturn reviewed or validated semantic
meaning.  SFH1 `referent_hint` and `network_role` fields now survive the
SFH1 → SFH2 observation bridge and the existing-Person retrieval record.
They are preserved as semantic provenance, not used as an automatic identity
selection.  A missing registry entry therefore remains eligible for a
candidate historical entity instead of silently falling back to an unrelated
Person.

## Graph-role policy

`scripts/sfh2/graph_role_policy.py` is installed from `scripts/sfh2/__init__.py`
before the SFH2 pipeline imports projection functions.  The policy is
occurrence-level and applies only to explicit semantic roles.  The following
roles cannot create core Story-network nodes or edges:

`citation_author`, `historical_exemplum`, `person_attribute`,
`collective_reference`, `structural_reference`, and `genealogy_ancestor`.

The historical/source identity remains available in source/context data.  For
example, a validated `王隱晉書曰……` occurrence can remain a historical person
with role `citation_author` while being excluded from that Story's core social
graph.  Relation projection is filtered as well as observation-node
projection, preventing a source-only occurrence from re-entering through a
relation endpoint path.  Legacy observations with no explicit role preserve
their prior state rather than receiving a Python-invented semantic label.

## Derived transition contract

The active alias/profile inputs are intentionally changed derived projections,
not canonical historical truth.  `data/generated/sfh2r1/repair-manifest.json`
records an explicit byte-level before/after transition chained after the
original SFH2R manifest.  Earlier validators accept only exact snapshots in
that chain and only when the current files equal the recorded final bytes;
arbitrary future regeneration is still rejected.  Canonical Person, relation,
Story-time, kinship, marriage, office, and other protected historical hashes
remain equal before and after.  HNG0/HNG0.2/HNG0.2R rebuild compatibility uses
the preserved pre-repair alias witness and frozen selection signals, so a
derived identity cleanup cannot rewrite an older historical publication
artifact.

## Offline replay

The isolated replay at
`data/generated/sfh2r1/offline-replay/` uses existing cached semantic outputs
and makes no provider calls.  It retains 188 Stories, 2,864 Person mentions,
and 598 candidate observations.  It reports 543 original SFH1 candidate IDs,
236 candidate-ID merges, 358 unique candidate entities, and 834
anonymous/structural references.  Existing-Person links are unchanged in the
offline/no-provider replay (56 Persons reached); 1,479 entity references
remain unresolved.  Relation endpoint reprojection has 542 complete rows
(153 both-existing, 208 existing-plus-candidate, and 181 both-candidate),
with 886 structural-reference-blocked rows.  The isolated graph has 1,584
nodes, 3,413 edges, 50 components, and a largest component of 1,339 nodes;
the corresponding pre-repair SFH2 replay values are 468, 1,105, 45, and 345.
These are candidate/research projections, not a canonical graph migration;
the graph-size change also reflects explicit source-role exclusion and the
full candidate projection scope.

The replay recorded zero LLM calls, zero new live tokens, zero forbidden
identity merges, zero explicit-distinct cluster violations, and zero HDA2
suppression re-entries.  Fifteen dense packets remain fail-closed from the
existing SFH1 cache and were not fabricated or retried live.

## Validation and limits

`scripts/validate_sfh2r1.py` validates the second authority, active evidence
filters, direct-name retrieval, contextual `伯倫`, 王隱 suppression, profile
integrity, the chained derived transition, protected hashes, and the
referent-hint bridge.  `data/generated/sfh2r1/closeout-summary.json` and
`offline-replay-effects.json` are the compact machine-readable closeout
records; the full before/after and isolated replay files remain available for
audit.

This stage removes reviewed contamination; it does not establish historical
completeness.  Remaining short-form ambiguity, unresolved identity, and
provider/cache gaps should stay unresolved or contextual.  No HGE Wave C,
new production Person, canonical fact, or canonical alias acceptance is
created here.

The closeout recommendation is `sfh2r1_closeout_passed` only after the
focused, full portable, validator, frontend, protected-state, and deterministic
replay checks all pass.
