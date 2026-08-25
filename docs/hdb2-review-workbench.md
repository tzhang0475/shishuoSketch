# HDB2 review workbench

The HDB2 human-review interface is available at `/review/hdb2`.  It reuses the
IRR review page’s two-panel shell and local browser review/export pattern, but
loads only the lightweight projection under
`site/public/generated/review/hdb2/`.

The left queue is ordered by structural impact and can be filtered by priority
and review type.  The right panel shows the story, relevant annotation,
selected evidence excerpts, candidate identities, support families, and
affected candidate facts.  Compositional references are presented as a base
person/relation question; they are never displayed as an automatic base-person
identity.

Actions are stored in `localStorage` and exported as
`hdb2-human-review-decisions.json`.  The export is sorted by `review_id` and is
candidate-only; it does not materialize canonical Persons or facts.

HDB2-F rescue search persistence is compacted offline.  The normal
`rescue-search-results.json` contains queries, counts, source counts, selected
refs, and lightweight unselected-hit metadata.  Passage bodies remain only in
`rescue-selected-passages.json`; optional full per-occurrence traces are under
the run’s debug directory and are not required for replay.
