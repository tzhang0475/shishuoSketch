# WP1 data conventions

## Stable IDs

IDs are opaque, assigned identifiers. They are never generated from a
person's name, a title, a URL, or generated text. Existing reviewed IDs are
retained for compatibility; in particular, `06-yaliang-019` remains the
canonical Story ID and the six existing person IDs remain unchanged.

IDs are unique within an object type and should also be globally unique in a
published data bundle. Human-readable labels belong in separate fields.

## Aliases

`Person.canonical_name` is the identity label. `Person.aliases` stores observed
surface forms separately, with an alias type, resolution mode, and evidence
references. Orthographic variants remain distinct strings; the source text is
never rewritten to match a canonical name.

## Dates and periods

Dates use a small explicit status: `exact`, `range`, `approximate`, or
`unknown`. Missing dates are represented by `null` values and `unknown`, not by
invented years. A period label may be supplied when the source or reviewed
scope supports it.

## Locations

Locations are source-backed labels with evidence references. A location name
does not imply a modern geocoding or a precise historical boundary. Unknown
locations are omitted or represented with an explicit unresolved status.

## Evidence references

Evidence is a separate object. Claims refer to Evidence IDs rather than
embedding untraceable quotations. Evidence locators have two explicit layers:

* `artifact_path` and `artifact_sha256` identify the exact derived entry or
  Jinshu unit containing the quoted text;
* `source_provenance.source_path` and `source_provenance.source_sha256`
  identify the upstream witness artifact, together with its `witness_id`.

The path and hash within each layer must identify the same file. A Shishuo
locator uses `entry_id` and a Jinshu locator uses `unit_id`; the validator
checks these IDs, paths, metadata, hashes, and exact quote containment against
the canonical indexes and files. Derived text may be copied into a static
bundle only by a reproducible builder and must retain this full provenance
chain.

Provenance validation has two explicit modes:

* `python3 scripts/validate_wp1.py --mode full` is the default local-research
  mode. It requires every upstream source payload and recomputes its hash.
* `python3 scripts/validate_wp1.py --mode portable` is for clean CI checkouts.
  A missing upstream payload is accepted only when its exact path, witness, and
  SHA-256 occur in committed trusted metadata (the relevant lock manifest or
  source provenance lock) and that metadata explicitly identifies an ignored or
  external payload. Canonical derived artifacts are still required physically
  and are always hashed from disk in both modes.

The portable mode verifies identity; it does not treat a missing payload as
validated text and never copies or substitutes source content.

## Relations

Relations are one semantic edge, using the existing `subject_id` and
`object_id` fields rather than duplicated forward/reverse records. Hard
relations may declare a `relation_subtype`, `role_a`, and `role_b`; source
entry/unit IDs identify the canonical anchors in addition to the resolving
Evidence IDs. Reviewed R1 relations are limited to directly supported kinship
and marriage edges. `relation_basis: direct` identifies a directly attested
edge and requires direct Evidence; `relation_basis: derived` identifies a
deterministic path over reviewed direct relations and uses
`derived_from_relation_ids` instead of an additional quotation. Symmetric
spouse edges use one canonical endpoint order.
Co-occurrence, shared surnames or titles, and graph transitivity never create a
reviewed relation by themselves.

The unified `data/people.json` registry is the Person identity source of truth.
Its `scope_role` is `primary` for the six-person pilot or `supporting` for a
minimal evidence-backed bridge Person. WP1 annotation records are generated
projections of this registry; scope does not change identity or evidence
semantics.

## Assertion status

Every historical or interpretive assertion uses exactly one of:

* `attested` — directly present in the cited source;
* `reported` — reported by a cited source rather than directly witnessed by
  the project;
* `inferred` — a reasoned interpretation from cited evidence;
* `unknown` — not established in the current data.

Assertion status is not a confidence score.

An `attested` record with an `evidence_ids` field must have at least one
resolving Evidence ID. The validator enforces this invariant; it does not
permit an empty evidence list merely because a record is still a candidate for
review.

## Review status

Review status describes the data workflow:

* `candidate` — generated or proposed, awaiting human review;
* `reviewed` — checked for the current scope;
* `rejected` — explicitly excluded;
* `todo` — known work not yet started.

AI- or script-generated records begin as `candidate`; they do not become
historical facts merely because they validate against JSON Schema.

## Unresolved ambiguity

When a mention cannot be safely resolved, `person_id` is `null`, candidates
remain in `candidate_person_ids`, and `assertion_status` is `unknown`.
Contextual titles such as `太傅`, `丞相`, and `王公` must not be resolved by
string matching alone.

## Generated versus reviewed data

Raw and canonical source files are immutable inputs. `data/annotation/` holds
reviewable annotations and candidates. `data/derived/` is the reproducible
research-side build output, while `site/src/generated/` is the Vite build
input generated from that same bundle. They are synchronized by the builder
and exact-identity validation; the frontend does not publish a separate
runtime JSON copy. The WP1 sample builder records its input entry path and
source hashes; it does not edit the source entry.
