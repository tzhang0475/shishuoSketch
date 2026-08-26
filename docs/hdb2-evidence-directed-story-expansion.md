# HDB2-XE0 — Evidence-Directed Story Expansion Pilot

XE0 is an isolated candidate-only pilot over the frozen HDB2-F review
frontier.  It does not change HNG2/HDB2 identity logic, canonical data, or
the existing `/review/hdb2` projection.

## Frozen procedure

The current 73-item HDB2-F semantic frontier is frozen in
`data/generated/hdb2-xe0/baseline.json` (schema
`hdb2-xe0-baseline-v2`) from
`data/annotation/hdb2-f-review-queue.json`.  The reviewer-facing
`site/public/generated/review/hdb2/` projection is validated for exact
occurrence coverage, but its questions, labels, and explanation fields are
not part of the semantic fingerprint.  The v1 baseline accidentally froze
that physical UI representation; the explicit v2 migration preserves the
legacy selection compatibility hash without making presentation changes
historical frontier changes.

A deterministic scan of the 1,130
registered Shishuo Stories excludes the 143 current production Stories and
selects 24 outside-scope Stories using frontier term matches, structural
impact, office/kinship/name markers, and a stable tie-break hash.  The frozen
selection is in `data/annotation/hdb2-xe0-story-selection.json`.

Selected Stories use the existing frozen HNG2-C.3/HNG2-V1 evidence selector and
Person/Temporal read-fill calls.  Python continues to own grounding,
normalization, candidate state, and the review audit.  Same-surface equality
does not close an old review item: an outside occurrence must have compatible
existing candidate evidence.  No separate rescue round was necessary for this
run because the selected Story windows supplied the direct evidence packet.

## Outputs

The live run is `data/generated/hdb2-xe0/live/20260826T-HDB2-XE0-02/`.
Its review projection is separate from the baseline at
`site/public/generated/review/hdb2-xe0/`; the existing
`site/public/generated/review/hdb2/` files are unchanged.

The offline validator is:

```text
python3 scripts/validate_hdb2_xe0.py --run-id 20260826T-HDB2-XE0-02
```

## Result

The run processed 24 Stories and 42 Person targets, with 132 semantic calls.
One compatible old review item was resolved.  The selected Stories also
created 157 new candidate-review items, so:

```text
baseline_review_items   = 73
old_review_items_resolved = 1
old_review_items_remaining = 72
new_review_items_created = 157
net_review_reduction = 1 - 157 = -156
```

The recommendation rule therefore says **STOP expansion → proceed to human
review**.  This is an experiment result, not a prompt or resolver tuning
signal.  The next useful step is review of the existing frontier, not a second
Story expansion round.
