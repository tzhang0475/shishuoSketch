# HDB2 PSL1.2/PSL1.3 portable grounded resources

The PSL1.2 and PSL1.3 offline regressions use the same generic grounded-resource
parsers in every environment. In a full source checkout those parsers read the
registered physical witnesses first. When a portable checkout does not contain
an ignored/downloaded witness, they additionally read the committed
`data/derived/hdb2-portable-grounded-source-index.json` projection. Physical
units win when a source reference is present in both inputs.

The earlier portable failures were source-availability failures, not identity
ranking failures. The `祖車騎` and `劉尹` recoveries, and the PSL1.3
`朕`, `阮光禄`, `聘`, and `鳯` resource rows, depended on local Jianshu
(`箋疏`) blocks that are not included in a portable checkout. The Jinshu
physical witnesses have the same local-payload property. Committed Shishuo,
Liu annotation, SGZ, and ZTJ resources remain loaded through the normal source
index. The projection supplies only the missing payload-backed source
families.

## What is committed

The projection contains 3,423 bounded windows (about 6.7 MB), selected by
generic identity-bearing syntax: name/identity markers, compact kinship
patterns, office/title constructions, and ruler context. It contains no
Person IDs, candidate answers, expected mappings, or model decisions. Each
window retains its registered source reference, source work/layer, source
locator, source witness hash, original source form, and an exact window hash.
The window text is copied from the registered witness; it is not rewritten or
normalized into canonical historical text.

`hdb2_portable_grounded_source.py` validates the projection, adapts its rows to
the existing HDB2-P1 source-unit shape, and merges it with physical units by
stable source reference. The existing PSL1.2/PSL1.3 parsers then infer
title/name, office, ruler, kinship, directional, and variant identities from
the supplied historical text. This is a derived candidate-only resource
cache, not a replacement source, accepted identity resolution, or canonical
data (`candidate_only=true`, `canonical_write_back=false`).

The builder is deterministic and can be checked with:

```text
python3 scripts/build_hdb2_portable_grounded_source_index.py --check
python3 scripts/validate_hdb2_portable_grounded_source_index.py
```

The portable tests simulate absent local Jianshu/Jinshu units, verify that the
old missing-resource condition is reproduced without the projection, and then
verify that the same generic grounded-resource functions recover the required
candidate directions with the projection. No live provider or network call is
required, and the false-resolution safeguards remain unchanged.
