# IRR0.1 — Controlled Iterative Re-reading Prototype

IRR0.1 is a five-Story, deterministic annotation experiment.  It asks a
narrow question: when reviewed historical context is added in controlled
rounds, do both historical understanding and reading of the original Shishuo
language become more precise?

The fixed pilot is:

- `27-jiajue-008`
- `06-yaliang-017`
- `09-pinzao-017`
- `19-xianyuan-026`
- `05-fangzheng-032`

No Story is selected by IRR0.1.  The review input is
`data/annotation/irr0-iterative-reading-review.json`; the builder reads the
existing SC1, HR0, HR0.1, NL0, NL1, and selected S1 Jianshu assertion records.
The result is a downstream reading state, not a canonical fact or graph
update.

## R0 → R1 → R2

Each Story has a baseline `R0` with no added context and two reviewed context
rounds.  `evidence_added` records the exact evidence reference, source layer,
support summary, and expected experimental role:

- `high_gain` — context expected to clarify a historical or linguistic issue;
- `medium_gain` — useful but bounded context;
- `hard_negative` — context deliberately expected to add little or distract.

The pilot includes a hard-negative round for `06-yaliang-017`: the `阿恭`
name note is retained as evidence, but it does not change the scene's central
action or its reading of `神色恬然`.

The state schema is `schema/iterative-reading-state.schema.json`.  It keeps
historical reading, text salience, aesthetic operations, open questions, and
structured deltas separate.  Critical span depth is:

```text
0 unresolved
1 literal
2 contextual
3 explanatory historical
4 aesthetic: why this wording/action/omission matters here
```

The pilot preserves the source wording for the required critical passages,
including `陶自起止之` / reviewed phrase `陶公起止拜`,
`庾乃引咎責躬，深相遜謝` / reviewed phrase `引咎自谢`,
`一丘一壑，自謂過之`, and `不意天壤之中，乃有王郎！`.

## Gain diagnostics

`data/derived/irr0-gain-report.json` reports, for every round:

```text
G_H  historical understanding
G_L  linguistic salience
G_A  aesthetic understanding
G_C  supported connection gain
G_U  uncertainty-resolution gain
G_D  distraction/redundancy penalty
MRG  positive components minus G_D
```

The components are simple clipped counts and critical-span depth changes;
they are not a single authoritative score.  `MRG` is an experimental
diagnostic, not historical truth, Story quality, or historical importance.
The first pilot shows strict depth progression for four Stories, while the
Yaliang control round has no further critical-span depth increase and carries
a non-zero distraction penalty.

## Epistemic boundary

All substantive state, delta, and aesthetic annotations carry existing Story
evidence or S1 assertion references.  Jianshu references remain transmitted
scholarly evidence; they are not independently verified source facts.  Open
questions and source uncertainty are retained.  IRR0.1 makes no LLM calls,
does no retrieval, adds no historical facts, changes no frontend code, and
does not write to SC1, HR0, HR0.1, NL0, NL1, or canonical data.

The experiment is intended as the substrate for IRR0.2, where the same fixed
states could be supplied to an actual reading model.  IRR0.2, retrieval,
RAG, training, persistent memory, and frontend projection are outside this
milestone.
