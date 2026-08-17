# IRR0.2 — Model Re-reading Experiment

IRR0.2 is an isolated experiment on the five fixed IRR0.1 Stories:

```text
27-jiajue-008
06-yaliang-017
09-pinzao-017
19-xianyuan-026
05-fangzheng-032
```

It compares three model conditions:

```text
TEXT_ONLY   Story text only
ALL_AT_ONCE Story text plus all already-reviewed context evidence
ITERATIVE   R0, then cumulative reviewed evidence round by round
```

The IRR0.1 Gold file is a scoring input only. The fixed IRR0.1 review schedule
is used to identify the already-reviewed evidence sequence, but its
annotation fields are not sent to a provider. The runner builds a sanitized
inference payload containing the Story text and the evidence allowed for the
current condition. Gold-only fields such as `expected_role`, `gain_vector`,
`critical_spans`, target depths, review grounding and human annotations are
checked out of those payloads before a provider is called. The scorer reads
Gold only after inference.

## Provider boundary

No provider credentials are stored in the repository. Running without an
injected provider uses a deterministic structural fixture:

```bash
python3 scripts/run_irr0_2.py --mode all --fixture
python3 scripts/score_irr0_2.py
python3 scripts/validate_irr0_2.py
```

Fixture output is marked `fixture_pipeline_only` and is not a model result.
It exists to validate schemas, input isolation, scoring, deterministic
artifacts and the review instrument.

A provider can be supplied by setting `IRR0_2_PROVIDER_MODULE` to a Python
module exposing:

```python
def run_reading(payload):
    # payload contains only story, allowed evidence, previous model output,
    # mode, round and the fixed prompt version.
    return model_output
```

The model and provider labels are supplied through `IRR0_2_MODEL` or the CLI.
The adapter does not select a provider, hold credentials, retrieve sources,
or call an LLM from the browser.

One Story can be run for a condition with:

```bash
python3 scripts/run_irr0_2.py --story 27-jiajue-008 --mode iterative
```

The full experiment is normally regenerated before scoring so the three
condition files remain a complete comparison.

## Artifacts and scoring

The model outputs and comparison artifacts live under
`data/derived/irr0-2/`. A compact copy is generated under
`site/public/generated/irr0-2/` for the developer-only review route. Neither
location is canonical historical data, and normal SC1 builders do not depend
on these outputs.

The deterministic scorer reports historical, critical-span, linguistic,
aesthetic-operation, omission/context and uncertainty diagnostics, together
with unsupported-reference errors. Iterative rounds additionally report
model and Gold gain vectors and depth transitions. `MRG` is retained as an
experimental diagnostic; it is not collapsed into an authoritative score and
does not represent historical importance.

Round-to-round degradation is checked separately against the same final Gold
target. This prevents a later, more demanding Gold round from being mistaken
for a deterioration caused by the added context.

The default fixture deliberately makes the execution status visible. A
fixture comparison must not be used to claim that iterative reading improves a
real model. Real model outputs must be generated with an explicitly recorded
provider and rerun through the same validator and scorer.

## Review route

Open `/review/irr0` (under the configured site base path) to compare the five
Stories. The route loads IRR artifacts with runtime `fetch`, keeps Gold behind
an explicit Gold tab, and provides an Iterative round view with expandable
evidence, model/Gold gain vectors and depth values. Blind review hides Gold
material and stores the four local judgments in browser `localStorage`; the
export is a separate local JSON file and never enters Gold or canonical data.

## Limits

IRR0.2 does not retrieve sources, train or fine-tune a model, create facts,
modify IRR0.1 Gold, update the reader, or implement RAG. It is a small
algorithm-validation substrate for a later experiment comparing actual model
readings under the same controlled evidence sequence.
