# IRR0.4 — Semantic Escalation Re-reading

IRR0.4 is a controlled experiment on three existing IRR Stories:

```text
27-jiajue-008
09-pinzao-017
06-yaliang-017
```

It tests whether a staged semantic ladder makes the same original Shishuo
span visibly deepen without treating a later model output as a historical
fact.

## Experimental design

The primary branch is:

```text
R0 literal
→ R1 event context
→ R2 relational / retrospective context
→ R3 aesthetic re-reading
```

Each stage is represented by a reviewed evidence bundle, a driving question,
and hidden expected effects/target spans. The hidden fields are used only by
the fixture controller and post-inference scoring; they are never included
in model inference inputs. The original Story and supplied evidence remain
the only content available to a provider.

Every stage after R0 runs in two conditions:

* **Memory** receives the preceding model reading and tests incremental
  anchoring.
* **Fresh** receives the same accumulated evidence without the preceding
  model reading and tests re-reading from the source again.

The evidence union is identical across the main ladder and the corresponding
all-at-once inputs; only order and prior-reading presentation differ.

Each Story also has a separate `1N` negative-control branch. Its evidence is
historically related and source-backed but selected as low-value for the
target scene. It is not inserted into the main semantic ladder. A lack of
changed spans or gain is a valid result.

## Span-centered output

The model output is organized around the critical source spans. Each span
records its literal reading, current interpretation, change type, supporting
evidence IDs, unsupported-inference flag, and separate dimensions for scene
historical, relational, retrospective, and aesthetic depth. The generated
trajectory report prints the interpretations in order so a reviewer can see
the proposed escalation directly rather than relying on an aggregate score.

The fixture provider deliberately demonstrates the intended shape of the
ladder, including political action meaning for `27-jiajue-008`, intellectual
comparison for `09-pinzao-017`, and retrospective rather than scene-level
change for `06-yaliang-017`. These are plumbing fixtures, not model results.

## Human review

The `/review/irr0` developer page includes an **IRR0.4 Semantic Ladder**
surface with Memory/Fresh and Main/Negative Control switches. Gold target
spans and expected effects are hidden when Blind review is enabled. Local
review records are kept in browser storage and can be exported separately;
they do not modify IRR0.1 Gold, canonical history, or model artifacts.

Reviewers can record visible deepening, historical and aesthetic depth,
unsupported or misleading interpretation, anchoring, and whether to continue
reading. Those judgments are deliberately separate from the generated
fixture/model output.

## Execution status and boundaries

`run_irr0_4.py --fixture` produces deterministic, reviewable pipeline output.
The provider adapter accepts a user-supplied `run_reading(payload)` module and
records provider, model, run ID, prompt version, temperature, timestamp, and
input hash. A real provider run is marked `run_type = real_model`; fixture
output is never presented as a real experiment.

IRR0.4 does not tune MRG, perform retrieval, call an LLM from the browser,
create facts, update Gold, train a model, or change the production reader. It
is an experimental substrate for deciding whether a later real-model run can
show semantic escalation and where the reading saturates.

