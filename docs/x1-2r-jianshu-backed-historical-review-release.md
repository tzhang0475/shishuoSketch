# X1.2R — Jianshu-Backed Historical Review & Release

X1.2R is the review/materialization step after S1 made the local
《世说新语笺疏》 source family usable. It consumes exactly the frozen 20
Stories selected by X1.1; it does not select a replacement batch or rescore
the corpus.

## Source layers

The Story-local evidence bundle keeps the structured Jianshu blocks separate:

```text
base_text
liu_annotation
jianshu_note
collation_note
other_scholar_note
```

The base text is the primary participant evidence. Liu annotation can identify
an alias or historical context, but an annotation-only Person is never a hard
Story participant. A Jianshu note preserves its named scholar and modality.
A quotation or citation is recorded as a research candidate; citation is not
verification of the cited work. Jianshu remains a scholarly working reference,
not a replacement for the primary Shishuo witness.

## Frozen review pipeline

```text
X1.1 frozen selection
        ↓
20 Story-local evidence bundles
        ↓
participant review
        ↓
identity review
        ↓
selective fact reopening
        ↓
cross-fact conflict preservation
        ↓
extension-only canonical release
```

The selected Story IDs and their original channel provenance
(`graph_guided`, `coverage_guided`, `stratified_random`, and `counter_model`)
are loaded from `x1-1-selection-manifest.json`. No new Story selection is
performed.

## Participant review

Each observed Person surface receives a reviewed role from the existing
vocabulary:

```text
present / speaker / actor / referenced / off_frame /
annotation_only / uncertain
```

Only Story-local main-text `present`, `speaker`, or `actor` records can be hard
participants. `Mention` and `PersonStory` are not participation by themselves.
Jianshu biography or commentary cannot make a Person present in a scene. A
generic title remains an occurrence-level gap when the aligned evidence does
not establish its antecedent; no global title mapping is created. Stories with
no reviewed production-resolved main-text Person surface retain an explicit
hard-participant coverage gap; the pipeline does not infer one merely to pass
the extension gate.

The participant projection is an extension review artifact. The protected H0C
participant freeze and the 143-Story production projection are unchanged.

## Identity and fact review

The three still-unresolved X1.2A identity candidates are reopened with their
prior decision history preserved. An existing Person mapping is preferred, but
no new Person is created merely to improve connectivity.

The 58 punctuation-blocked X1.2A facts are classified before review:

```text
new_Jianshu_evidence_hit
participant_blocked
identity_blocked
semantic_uncertainty
other
```

Only a genuinely new evidence route is reopened. A Jianshu commentary claim,
source citation, background event, office-derived title, surname, or plausible
social association is not enough to materialize a fact. The current X1.2R
batch therefore preserves unresolved fact candidates rather than converting
commentary into canonical historical truth. Existing X1.2A’s nine reviewed
facts and three entities are referenced and protected, not copied under new
IDs.

## Citation candidates

The 20-Story pilot emits a compact Story → Jianshu note → cited work research
projection. Each record retains attribution, layer, source locator and quoted
passage, and is marked `citation_only`, `research_candidate`, and
`canonical_fact_created = false`. The cited historical works are not ingested
or treated as verified sources in X1.2R.

## Canonical release boundary

Stories whose S1 editorial gate and participant gate pass are written to
`x1-2r-canonical-extension.json` with source provenance and reviewed
participant records plus deterministic extension-only PersonStory/Mention
projections. This is an extension-only release:

```text
protected production Story universe = unchanged
X1.2A extension = unchanged
X1.2R extension = new, deterministic records
```

No canonical text, Mention span, PersonStory link, alias index, historical
fact, H0A/H0B/H0C projection, HG0 graph, or ML0 artifact is rewritten. A
production Story may have reviewed text and participant semantics while its
deeper historical context remains partial or unknown.

## Realized gain and remaining bottlenecks

`x1-2r-realized-yield.json` and `x1-2r-channel-audit.json` compare the four
selection channels after the common S1 editorial bottleneck was removed.
Counts are observed review yield, not historical importance or causal model
quality. Counter-model and stratified-random channels remain visible as
independent diagnostic channels.

The current release produces an extension Story projection but no new Person
or fact materialization. The main remaining bottlenecks are generic/title
identity, non-production historical endpoints, semantic fact precision, and
unverified cited works. Those gaps are preserved for later source review.

## HG1.1 readiness and stop boundary

The summary records whether the non-empty extension is sufficient to justify a
future `HG1.1 — Post-S1 Historical Graph Rebuild`. That recommendation is not
an implementation of HG1.1. X1.2R stops before:

```text
X1.2B
HG1.1
ML1.1
new GNNs or embeddings
ontology expansion
ER2
```

The epistemic boundary remains:

```text
Jianshu evidence ≠ primary fact automatically
Yujiaxi interpretation ≠ canonical historical truth automatically
citation ≠ source verification
Production Story ≠ fully enriched Gold Story
```
