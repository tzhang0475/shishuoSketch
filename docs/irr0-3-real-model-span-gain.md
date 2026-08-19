# IRR0.3 — Real-model Re-reading & Span-level Gain Validation

IRR0.3 extends the five-Story IRR0.1/IRR0.2 pilot. It is an isolated
experiment: its model outputs and human review records are research artifacts,
not canonical history, Gold annotations, StorySketch data, or graph input.

## Experimental contract

The frozen Stories are:

```text
27-jiajue-008
06-yaliang-017
09-pinzao-017
19-xianyuan-026
05-fangzheng-032
```

The runner executes the same three conditions with one provider/configuration:

```text
TEXT_ONLY    Story text only
ALL_AT_ONCE  Story text + the complete reviewed context union
ITERATIVE    Story text, then the same context in frozen review-round order
```

The all-at-once evidence set is validated to equal the final iterative-round
union. The difference between those conditions is presentation order and the
iterative previous-reading state, not evidence content. Context roles and
Gold-only fields are kept in the review inputs and are never sent to the model.

Every Story has a reviewed hard-negative addition. A hard negative is related
and historically supported but low-value for the current scene; the fixture
therefore permits an empty `affected_spans` transition. The model is not
rewarded for inventing a reinterpretation when evidence does not affect the
text.

## Runner and provider boundary

`scripts/run_irr0_3.py` reuses the IRR0.2 output schema and accepts either the
deterministic fixture or a small provider module. A provider module is loaded
with `--provider-module` or `IRR0_3_PROVIDER_MODULE` and must expose:

```python
def run_reading(payload: dict) -> dict:
    ...
```

The payload contains only the Story, allowed evidence, the prior model reading
when applicable, mode/round metadata, and output-contract instructions. A
provider returns the model reading; iterative rounds after R0 must also return
`affected_spans`. The runner records provider, model, parameters, prompt
version, run ID, timestamp, and input hash. Use `--model` or `IRR0_3_MODEL` to
label the model. Provider credentials and API behavior remain outside this
repository.

Example real run:

```bash
IRR0_3_PROVIDER_MODULE=my_irr_provider \
IRR0_3_MODEL=my-model \
python3 scripts/run_irr0_3.py --mode all --provider-module my_irr_provider --model my-model
python3 scripts/score_irr0_3.py
python3 scripts/validate_irr0_3.py
```

When no provider module/credentials are available, the checked-in outputs are
explicitly `run_type = fixture` and `scientific_status =
fixture_pipeline_only`. They validate the contracts and UI, but are not real
model findings. No real-model result is fabricated.

## Span-level review

`transition.affected_spans` is the primary Evidence → Span → Delta unit. It
contains the exact source span, before/after interpretations, model-reported
historical and aesthetic depths, and an unsupported-interpretation flag. An
empty list is valid and represents no material change.

The `/review/irr0` developer page has a separate **Span Review** surface. It
shows the original Story, added evidence, model before/after interpretations,
and lets a reviewer record:

* affected span, `其他`, or `没有影响`;
* interpretation depth 0–4;
* salience, compression, omission, and selection dimensions;
* supported / unsupported / misleading interpretation;
* continue-reading choice and stop reason.

These records are stored separately in local browser storage and can be
exported as `irr0-3-span-review.json`. They are not written to the frozen
IRR0.1 Gold file. Blind review hides Gold-only target information and expected
context roles.

## Scoring

`scripts/score_irr0_3.py` compares model outputs with the frozen IRR0.1 Gold
only after inference. It reports per Story and per iterative round:

```text
historical depth
aesthetic depth
question depth and gain
critical-span coverage
unsupported interpretation count
G_H, G_L, G_A, G_C, G_U, G_D, MRG
human span re-reading gain when review exists
```

For compatibility with IRR0.2 it also retains the deterministic condition
scores `historical_score`, `critical_span_score`,
`linguistic_salience_score`, `aesthetic_operation_score`,
`omission_context_score`, `uncertainty_score`, and
`distraction_error_count`. These are transparent overlap/structure
diagnostics, not an authoritative quality scalar. Pairwise condition reports
include their deltas as well as the span-level trajectory.

MRG remains a backward-compatible diagnostic and is not the primary decision
metric. Human span depth, aesthetic depth, question depth, unsupported
interpretation, and continue/stop decisions are primary IRR0.3 signals.
Automatic aesthetic-operation overlap is secondary. Comparison artifacts make
the three pairwise condition comparisons and hard-negative behavior explicit,
including negative results.

## Artifacts and protection

Generated experiment artifacts live under `data/derived/irr0-3/` and are copied
byte-for-byte to `site/public/generated/irr0-3/` for the review page. The
separate context schedule is `data/annotation/irr0-3-context-review.json`; the
human review schema and empty initial review file are separate from Gold.

`scripts/validate_irr0_3.py` checks the frozen five-Story scope, input hashes,
Gold-field isolation, all-at-once/iterative evidence equality, transition
shape, hard-negative coverage, model schema, manifest hashes, human-review
schema, and derived/public byte identity. It also rejects self-hashing
manifests and invalid run-type mixtures.

IRR0.3 does not change canonical data, HR0/HR0.1, NL0/NL1, IRR0.1 Gold,
StorySketch, or the production reader. It does not retrieve sources, call a
model from the browser, train a model, update Gold, or materialize facts.

## Current experiment status

The repository includes deterministic fixture outputs so the pipeline and
review surface can be tested without credentials. Real-model execution is a
separate explicit run using a provider module; until that is supplied, no
claim is made about whether iterative re-reading improves historical or
aesthetic understanding.

IRR0.3 is the substrate for a later real evaluation. It does not implement
IRR0.4, retrieval, CHM, fine-tuning, automatic Gold updates, or production
StorySketch changes.
