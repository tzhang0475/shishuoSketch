# SFH2.2-A0R — Selective Semantic Review and Adjudication Contract Repair

SFH2.2-A0R is an isolated closeout experiment for the 20-case SFH2.2-A0
semantic-authority set. It does not replace SFH2, rerun the 188-story corpus,
write canonical history, or add a production Person.

## Failure being repaired

The A0 review contract asked Pass 2 and Pass 3 to return complete semantic
records. A selector such as `select_pass1` therefore still carried a newly
generated record. The record could be semantically changed while the selector
itself said to preserve Pass 1. The `阮嗣宗` case exposed this: the original
record preserved `referent.surface_form = 阮嗣宗`, while the regenerated
selector record changed it to `阮籍`. The damage was orchestration drift, not
an authorized semantic correction.

## Repaired contract

Pass 1 remains the only complete-record semantic call. Pass 2 returns one of:

* `confirm` with no patch;
* `revise` with a whitelist-checked field patch and an explicit
  `reviewed_fields` list; or
* `abstain`.

Pass 3 returns one of:

* `select_pass1`;
* `select_pass2`;
* `revise` against `pass1` or `pass2` with a narrow patch; or
* `abstain`.

For selection decisions Python deep-copies the selected prior LLM record. It
never asks the selecting model to reproduce that record. For revisions,
Python validates the path whitelist, applies the patch, revalidates the full
record, and rejects any undeclared semantic mutation. Explanations are kept
outside semantic equality, so wording changes do not trigger adjudication.

The authority boundary remains:

```text
reviewed human semantics > validated LLM semantics > soft consistency > retrieval hints
```

Python performs schema/evidence validation, formal consistency analysis,
review routing, deterministic record selection, candidate-only realization,
and storage safety. It does not provide a replacement historical identity or
Classical Chinese lexical rule.

## Routing

Pass 2 is routed only for Pass 1 `hard` or `review` severity signals. A
diagnostic-only signal does not escalate. Pass 3 is routed only when the
review is invalid/abstained, a Pass 2 revision produces substantive semantic
disagreement, or a hard formal conflict persists after Pass 2. This is the
production-oriented policy; the closeout replay uses the frozen A0 responses
as a compatibility input and does not reinterpret them.

## Offline counterfactual

Before any new provider call, the implementation replays the frozen A0
outputs while applying the repaired exact-copy selector semantics. The
counterfactual is stored in:

```text
data/generated/sfh2-a0r/offline-counterfactual.json
```

The recorded baseline is 14/20 strict final records (70%) with one reviewer
damage case. The repaired selector counterfactual is 15/20 (75%) with zero
reviewer damage. The only semantic record changed by selector-copy repair is
the known `阮嗣宗` case, where the Pass 1 surface is preserved. Differences in
explanation prose are not counted as semantic changes.

The first bounded live attempt used the frozen v1 transport contract and was
blocked before any provider response by the sandbox (`Operation not
permitted`). It made 45 recorded provider attempts, received zero responses,
and consumed zero provider tokens. No live semantic result was accepted. A
mechanical post-attempt replay-contract correction then started protocol v2:
it distinguishes substantive semantic changes from confidence/evidence
metadata for Pass 3 routing and preserves case identifiers in compatibility
audit rows. The v1 freeze and failed transport remain under the isolated
`live/` audit directory; the root artifacts are the deterministic v2 replay.

## Evaluation dimensions

The A0R evaluation reports historical identity, semantic kind, referent
surface, canonicalization, occurrence role, discourse, relation, and
serialization dimensions separately. A strict full-record score remains for
comparability, but representation/canonicalization differences are not
automatically described as historical identity errors.

## Scope and limitations

`字景真` remains a useful example of a semantic error that may have no formal
Python contradiction; A0R intentionally does not add a lexical rule to catch
it. Formal consistency is a review router and safety gate, not a historical
answer oracle. Live provider results, when available, are isolated under the
A0R run directory and are evaluated under the frozen A0 gold labels only
after the semantic records have been selected.

All A0R artifacts are candidate-only and carry
`canonical_write_back = false`. No live result mutates aliases, profiles,
canonical Persons, or canonical relations.

The v2 replay records 5 Pass 2 review routes, 1 Pass 3 route, zero copy-drift
errors, zero undeclared patch mutations, and zero reviewer damage. A live
provider regression remains pending only because network access was unavailable
in this environment; it is not represented as a successful semantic run.
