# X1.2R-F — Jianshu Fact Materialization Policy Revision

X1.2R-F corrects the boundary used after S1 and X1.2R.  Jianshu does not
automatically establish a historical fact, but an explicit, semantically
clear, endpoint-resolved, non-modal assertion may be reviewed as a
structured historical proposition.  Acceptance means that ShishuoSketch has
accepted a provenance-bearing assertion; it does not claim unquestionable
historical truth.

The milestone consumed only the frozen X1.1/X1.2R 20-Story universe and the
34 X1.2R fact reviews marked `reopened_due_to_new_source`.  It did not select
Stories, parse a new Jianshu corpus, retrieve cited works, or modify the
X1.2R participant/identity decisions.

## Policy correction

The former effective rule treated Jianshu commentary, quotations, and
context as useful for reopening a candidate but not as a possible source of
an independent structured assertion.  X1.2R-F evaluates those questions
separately:

```text
original X1.2R candidate ── remains independently reviewed
Jianshu assertion unit   ── may become a reviewed extension fact
```

Materialization requires an explicit proposition, safe endpoints, an
existing H0C relation, non-modal semantics, a stable source locator and
evidence hash, preserved transmission provenance, explicit review acceptance,
and no duplicate semantic fact.  No model score, graph topology, fame, or
historical plausibility is evidence for acceptance.

Modal and disputed material (`probable`, `possible`, `disputed`, `unknown`,
and source language such as `疑`, `或`, `恐`, `未詳`) remains a scholarly or
unresolved assertion.  A parent block can therefore remain non-canonical while
an explicit child clause is reviewed separately.

## Source-layer and transmission semantics

The assertion review preserves the S1 layer rather than flattening it:

| Layer | X1.2R-F treatment |
| --- | --- |
| `liu_annotation` | May state a direct annotation assertion or transmit a named quotation. |
| `jianshu_note` | Preserves the named scholar and distinguishes source reporting from interpretation. |
| `collation_note` | Remains editorial/scholarly evidence, not an automatic historical fact. |
| named quoted work | Retained in `quoted_source` and `transmission_status`; it is not independently verified by this milestone. |
| citation-only lead | Remains `citation_only`; the 76 X1.2R citation candidates are not changed. |

The extension distinguishes, for example, `liu_annotation_assertion` from
`quoted_via_liu_annotation` and `scholarly_assertion`.  A quotation transmitted
through Jianshu is not represented as an independently inspected copy of the
quoted work.

## Review results

The assertion-level artifact reviewed 132 S1 assertion records attached to
the 20 frozen Stories.  The 34 original X1.2R candidates remain separate:
all 34 retain their prior `unresolved` outcome and no candidate was mutated
into a different fact.  Independent assertion review found one accepted
fact unit associated with those original cases and two additional accepted
facts elsewhere in the same frozen evidence universe.

The new extension contains three facts:

| Fact | Source assertion | Transmission | Precision |
| --- | --- | --- | --- |
| `person-061` held `州從事` | `鑿齒謝牋` in Liu annotation | `liu_annotation_assertion` | unknown chronology |
| `person-065` held `長史` | explicit Liu annotation | `liu_annotation_assertion` | unknown chronology |
| `person-003` held office at `丹陽` | explicit `丹陽太守王導` clause quoted from `王隱晉書` through Liu | `quoted_via_liu_annotation` | unknown chronology |

The `續晉陽秋` statement repeating the `習鑿齒` office proposition is
retained as one same-epoch corroboration record, not a duplicate fact.  The
`王隱晉書` parent block also contains later disputed/conjectural geography;
that material remains scholarly-only while the explicit quoted clause is a
separate accepted assertion unit.

No new Person or Story was created.  No existing H0C fact was rewritten and
no existing canonical fact was duplicated.  The extension is intentionally a
future HG1.1 input rather than a write-back to the protected H0C or HG0
projection.

## Artifacts

The deterministic outputs are:

* `x1-2rf-policy.json` — materialization conditions and input/protection hashes;
* `x1-2rf-assertion-review.json` — source-block and assertion-unit review;
* `x1-2rf-original-candidate-review.json` — the 34 original outcomes and
  independent yield;
* `x1-2rf-materialized-facts.json` — accepted extension facts only;
* `x1-2rf-corroboration.json` — non-duplicating support records;
* `x1-2rf-scholarly-assertions.json` — non-canonical scholarly, modal and
  citation-only material;
* `x1-2rf-summary.json` and `x1-2rf-next-step-recommendation.json` — metrics
  and the next-step decision.

All records retain the S1 source locator, assertion text hash, source layer,
attribution where present, quoted source where identified, and transmission
status.  The cited-source graph remains research metadata; no cited book was
ingested.

## Decision gate and stop boundary

The result is classified as:

```text
policy_correction_materially_increases_fact_yield
```

The change is material relative to X1.2R's zero accepted facts, but still
small relative to the full historical backlog.  X1.2B should wait until a
future HG1.1 rebuild consumes this extension and measures its graph effect.
Endpoint-unsafe and modal cases remain unresolved rather than being forced.

X1.2R-F does not implement X1.2B, S2, HG1.1, ML1.1, new embeddings, ER2,
Story/Person expansion, ontology changes, political-faction inference, or
importance ranking.
