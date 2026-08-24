# HNG2 — Hybrid resolver and controlled frontier growth

HNG2 is a generated research layer over the frozen HNG1R2 evidence.  It does
not write `data/people.json`, canonical relations, facts, Gold, NL, SRM, or
any earlier HNG output.

## Resolver

`scripts/historical_entity_resolver.py` uses the catalogue produced by
`build_hng0_2.person_catalog()` and builds a separate systematic matching
index.  Matching uses NFKC, traditional/simplified forms, and the small set of
historical glyph variants needed by the local catalogue.  This fold is never
applied to stored source quotations.

Resolution is ordered from exact catalogue forms through conditional reviewed
context, title/decorated-name parsing, kinship structure, local context,
temporal compatibility, and independent graph support.  Graph support only
ranks a textual candidate; edges sharing the current candidate, passage,
claim, or evidence refs are recorded as circular and excluded.  Remaining
semantic cases are eligible for constrained DeepSeek Flash assistance, but the
default HNG2 build is offline and made zero model calls.

Kinship parsing distinguishes surname-inheriting forms (`父`, `兄`, `弟`,
`從兄`, `兄子`, and related forms) from maternal/affinal forms (`母`, `外祖`,
`舅`, `妻`, `婿`).  Thus `卞壼（從父兄敦）` can produce a provisional `卞敦`
candidate, but never `王敦` merely because `敦` is a suffix.  A structural
chain such as `喜弟預女` is retained as unresolved structure and cannot become
a frontier person.

## Frontier waves

The default `scripts/run_hng2.py` / `scripts/build_hng2.py` run starts with
existing canonical Persons and eligible, traceable HNG1R2 provisional nodes.
It performs exactly two research waves.  Wave 2 can research an independently
eligible new neighbor once; no Wave 3 artifact is created.  Punctuated local
reference sources are searched first, with the smaller legacy local set used
only when no punctuated hit exists.  Retrieval trace, temporal-gate decisions,
exact evidence quotes, and candidate/review status are stored under
`data/generated/hng2/`.

The output is candidate-only.  Human decisions belong in
`data/annotation/hng2-review.json`; the review overlay has separate values for
correct, false merge, false split, bad seed match, bad temporal rejection,
uncertain, and not reviewed.

Useful commands:

```bash
python3 scripts/run_hng2.py
python3 scripts/validate_hng2.py --mode portable
python3 scripts/validate_hng2.py --mode full
```
