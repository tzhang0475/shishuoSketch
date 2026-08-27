# HDB2-PSL1.2 — Candidate Rescue

HDB2-PSL1.2 is an additive, candidate-only experiment on top of the frozen
PSL1.1 occurrence resolver.  It does not change the PSL1.1 weights,
reference-structure rules, hard vetoes, or adversarial reviewer.

For an occurrence that remains `review_required`, `genuinely_unresolved`, or
has a reviewer rejection of its top candidate, one bounded diagnostic call may
ask whether the supplied candidate set is incomplete.  The diagnostic is not
an identity decision.  It may only point to a source-visible surface and
source evidence IDs.

Python then performs the only admissible rescue operation:

```text
PSL1.1 open/rejected occurrence
→ bounded rescue diagnosis
→ existing grounded-resource lookup
→ exact provenance validation
→ optional candidate-only addition
→ frozen PSL1.1 inference and reviewer
```

Grounded lookup is limited to the registered local corpus, the existing
catalogue/aliases and ruler data, and previously grounded identity evidence.
Same-surface similarity, co-occurrence, and an LLM diagnosis alone cannot add
or resolve a person.  New source-supported names remain local candidate nodes;
no production `person-NNN` ID is allocated.

The experiment freezes twelve independent occurrences in
`data/annotation/hdb2-psl1-2-selection.json`.  The live run stores packets,
raw provider responses, diagnoses, grounded rescue provenance, and the final
candidate-only decisions under `data/generated/hdb2-psl1-2/live/`.

The required offline regressions cover `宣王 → 司馬懿`, `祖車騎 → 祖逖`,
`孔廷尉 → 孔坦`, and `劉尹 → 劉惔`; the three PSL1.1 reference-structure false
resolutions (`主 → 王敦`, `謝豫章 → 謝尚`, `敦主簿 → 王敦`) must remain
blocked.  These checks validate the generic source patterns and do not add
fixture-specific identity rules.

Use `python3 scripts/run_hdb2_psl1_2.py --offline` for a local no-provider
candidate-only run, or pass `--replay` to rebuild a completed run from its
frozen packets and model output.  Neither mode writes canonical data.

## Bounded validation

The frozen validation selection contains twelve occurrences not used by the
earlier PSL selections.  The live run used `deepseek-v4-flash` with 24
semantic calls: 9 contextual predicate calls, 8 adversarial-review calls, and
7 rescue-diagnosis calls.  It had no provider failures, parse failures,
retries, or truncations.  Seven rescue diagnoses were valid; four diagnosed a
possibly missing candidate, but Python found no admissible source-grounded
candidate, so no rescue changed a decision.  Final states remained 5
`stable_entity_resolved`, 3 `review_required`, and 4
`genuinely_unresolved`.

One frozen reviewer response used the literal string `"null"` for a candidate
key.  The validator rejected it as invalid and it did not mutate state.  This
is retained in the validation-failure audit rather than repaired by the
rescue layer.  The offline required regressions recover `宣王 → 司馬懿`,
`祖車騎 → 祖逖`, and `孔廷尉 → 孔坦` through source-grounded Python lookup;
`劉尹 → 劉惔` remains supported.  All four are candidate-only checks, and the
three PSL1.1 reference-structure false-resolution checks remain blocked.
