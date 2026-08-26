# HDB2-LJ0 — Grounded Identity Inference Test

LJ0 is an isolated, candidate-only test of whether deterministic hard
exclusions plus evidence-family scoring, cross-Story consistency, and a
separate falsification pass can reduce the current HDB2 review burden.

It consumes a deterministic 24-occurrence sample from the frozen
`data/annotation/hdb2-f-review-queue.json` projection.  The required
`05-fangzheng-011 / 武帝` occurrence is included together with candidate
Person, ambiguous identity, office/title, and compositional-reference cases.

The model sees only the occurrence context, compact existing candidate
dossiers, and locally named evidence IDs.  It never sees production Person
IDs and cannot create them.  Python validates candidate/evidence keys, applies
the hard structural/semantic exclusions, computes a transparent
`identity_score` (not a probability), applies the conservative high-confidence
threshold, and checks that a separate falsification response is grounded.

The two strict calls are:

```text
candidate generation (Python)
→ evidence-family evaluation (DeepSeek)
→ Python score/rank
→ falsification pass (DeepSeek)
→ Python veto/decision
```

`high_confidence_contextual` is allowed only when the leading candidate has at
least two supporting families, a strong supporting family, a sufficient score
and margin, no hard conflict, and survives the falsification gate.  Otherwise
the item remains `review_required` or `genuinely_unresolved`.

LJ0 writes only under `data/generated/hdb2-lj0/` and
`data/annotation/hdb2-lj0-selection.json`.  It does not modify HDB2-F
decisions, the HDB2 review queue, canonical data, or production Person IDs.

The experiment must not be interpreted as a probability calibration or as
automatic historical truth.  Its decision is a prioritization/review
diagnostic for the question: can grounded consistency evidence safely remove
some review items?

In the live run, `current_review_count` remains the full frozen HDB2 queue
(73).  `experiment_baseline_review_count` and `new_review_count` describe only
the selected 24-item pilot slice; the full HDB2 queue is never rewritten.
