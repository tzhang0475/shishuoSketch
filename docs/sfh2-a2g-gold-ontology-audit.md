# SFH2.2-A2G — Gold and Semantic Ontology Boundary Audit

SFH2.2-A2G is an offline, evaluation-only audit of the frozen 20-case A0
regression Gold against the current SFH2.2 semantic ontology. It uses no
provider calls and does not change Gold, the A2/A2R experiments, canonical
history, or either SC1 projection.

## Inputs and authority

The audit is anchored to baseline
`57af9d9bb4b418b15cc9b5aff7f4b2390d8c7608` and selection hash
`b8162d9d470c6359c67a8ed31aa31ef82149c12d92dd9a694b62327fc204bbc3`.
It reads:

- `data/annotation/sfh2-a0-evaluation-gold.json`;
- the frozen A0 selection and A2 source packets;
- cached A2/A2R Historian A, Historian B, and final records; and
- the current schema and Primary Historian prompt definitions.

The schema/prompt ontology is authoritative for this audit. A/B agreement is
only evidence that two hypotheses agree; it is not historical verification.
Python compares structured fields and reports review signals. It does not
infer identity equivalence, propose a replacement Gold value, or use string
similarity as an identity rule.

## Scope and outputs

All 20 frozen regression cases were audited, including exact source packets,
target spans, source-layer evidence, current Gold fields, and the A2/A2R
interpretations. There were 18 historical-identity-evaluable cases and six
Gold-evaluable occurrence-role cases. The machine-readable records are in
`data/generated/sfh2-a2g/`:

- `gold-ontology-audit.json` contains the case-level evidence and comparison;
- `gold-review-candidates.json` routes cases needing human review without
  proposing new Gold;
- `occurrence-role-audit.json` isolates the six role cases;
- `disagreement-taxonomy.json` separates substantive disagreement types;
- `metrics.json` records corrected evaluation metrics; and
- `recommendation.json` records the pre-consolidation recommendation.

`input-hashes.json` records the frozen input witnesses. Every new artifact is
deterministically serialized and contains `provider_calls: 0` where applicable.

## Ontology boundary finding

The one explicit Gold/ontology boundary candidate is:

| Story / surface | Frozen Gold | A/B/final interpretation | Audit disposition |
| --- | --- | --- | --- |
| `03-zhengshi-001` / `太丘長` | `historical_person`, canonical hint `陳寔` | `office`, `office_title`, `person_attribute`, with `陳仲弓` as bearer/antecedent | Human review; no replacement identity inferred |

The source says `陳仲弓為太丘長時`. Under the current semantic contract, an
office held by a person is represented as an office/person-attribute
occurrence unless the occurrence itself refers to a historical person. The
frozen Gold instead evaluates the occurrence as a historical person. This is
an ontology/evaluation-boundary issue, not permission for Python to choose
between `陳寔` and an office interpretation. It is therefore left unresolved
for human semantic review.

Other fields that do not match Gold are not silently promoted to ontology
conflicts. For example, `字景真` has the current `person_attribute` kind and
correct courtesy-name/value/bearer fields, while its model
`referent.surface_form` is the bearer rather than the current prompt's
attribute-value reference form. That is recorded as a field-level semantic
contract/model mismatch. Similar expanded-vs-source-form mismatches are
reported separately from historical identity.

## Occurrence-role audit

The six Gold role cases produce these findings:

| Surface | Frozen Gold role | A | B | Final | Finding |
| --- | --- | --- | --- | --- | --- |
| `薛瑩` | `citation_source_person` | same | same | same | Consistent with Gold |
| `齊桓公` | `historical_exemplum` | same | same | same | Consistent with Gold |
| `滔` | `annotation_person` | `scene_participant` | `scene_participant` | `scene_participant` | Model semantic error candidate |
| `王師` | `collective_reference` | same | `scene_reference` | `scene_reference` | Stage disagreement; human review |
| `字景真` | `person_attribute` | same | same | same | Consistent with Gold |
| `嘏` | `annotation_person` | `scene_participant` | `scene_participant` | `scene_participant` | Model semantic error candidate |

These findings preserve identity and occurrence role as independent evaluation
dimensions. In particular, a correct person identity with a wrong source-layer
role is not counted as a wrong historical person.

## Identity metric correction

The A2R `common_mode_errors` field required an A/B identity-agreement signal.
That is not the right definition for a joint failure. A2G defines a joint
identity failure as both valid, identity-evaluable records having
`identity_correct == false`, regardless of whether their identity strings
match. Under that definition:

- `joint_identity_failure_count = 1` (`太丘長`);
- A2R Historian A identity: `15/18`;
- A2R Historian B identity: `15/18`;
- A2R final identity: `17/18` with full resolution coverage;
- final semantic-kind accuracy: `19/20`;
- final canonicalization accuracy: `17/18`;
- final occurrence-role accuracy: `3/6`; and
- final strict full-record accuracy: `25%`.

Strict full-record and source/reference-form mismatches are retained for
diagnostics. They must not be described as historical identity failures when
the identity dimension is correct.

## A/B disagreement taxonomy

Across the 40 frozen A2 comparisons there are 33 substantive disagreements
and one metadata-only difference. The mutually exclusive primary taxonomy for
the substantive records is:

| Category | Count |
| --- | ---: |
| Identity or semantic-kind critical | 13 |
| Occurrence-role critical | 6 |
| Discourse/relation only | 11 |
| Contract-validity critical | 3 |
| Metadata-only within substantive disagreements | 0 |

The additional three contract-validity cases are kept separate so the four
substantive categories sum to 33. Raw overlapping field counts are retained
in `disagreement-taxonomy.json`; one comparison can contain more than one
field-level disagreement. Python reports these dimensions only and does not
alter review routing in this stage.

## Recommendation and limitations

The audit recommendation is:

```text
gold_review_required
```

Human semantic review must resolve the `太丘長` Gold/ontology boundary and
decide whether any Gold field conventions should be qualified. No Gold field
was changed automatically, and SFH2.2-F must not begin on the basis of this
audit alone.

The audit cannot determine whether a frozen Gold value is historically right
merely because a current model disagrees. It also cannot recover semantic
errors that have no formal inconsistency. Those remain responsibilities of
human semantic review and later controlled evaluation.

The protected SC1 frozen/current inputs were witnessed during generation and
remain unchanged: frozen SC1 retains SHA256
`cc82c6738fcbf4fc14c12005a459048e71ce329492867d0910562fc6fdfda0d8`, while
SC1 current retains SHA256
`b916530264285dd7fa1d2e27a7a1dff8cd2ed794dfb3b84985881f8f209d8f6a`.
