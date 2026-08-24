# HNG2-SC — Structured Semantic Card & Closed-loop Controller

HNG2-SC validates the controller boundary around Historical Entity Schema v1.
It does not expand the HNG frontier or write canonical data.

The data flow is:

```text
source passage
  -> model EvidenceInterpretation card
  -> strict Python validation
  -> catalogue candidates and provenance-bearing ConstraintChecks
  -> Python StateDelta
  -> ResearchGap recalculation
  -> typed SearchPlan or a second semantic call
```

The model can use only local `eN` entity keys, `aN` assertion keys, and the
provided candidate keys. Python owns catalogue IDs, provisional graph IDs,
IdentityDecision, GraphAction, and the ResearchGap state. A
`new_person_candidate` recommendation may create a separate provisional
GraphAction; it never writes a canonical Person.

## Response envelope

The controller reads `message.content` first. When content is empty it can
recover one JSON object from `message.reasoning_content`, recording the
response channel. Both channels go through the same card validator. Invalid
cards leave the gap open and do not update candidates or constraints.

## Offline replay

```bash
python3 scripts/run_hng2_schema_controller.py --mode replay
python3 scripts/validate_hng2_schema_controller.py --mode replay
```

Replay uses frozen HNG2-S/HNG2-SL material and deterministic fixtures. It
makes no API calls.

## Targeted live validation

Live mode freezes a deterministic 6–8-case selection from existing open
ResearchGap records, performs one authenticated SearchPlan preflight, and
allows at most one local retrieval round and two semantic calls per case:

```bash
python3 scripts/run_hng2_schema_controller.py --mode live --run-id <run-id>
python3 scripts/validate_hng2_schema_controller.py --mode live
```

Run live mode only with approved network access. Raw provider responses are
stored under `data/generated/hng2-schema-controller-live/raw-api/` and are
not used as a cache or research memory. No frontier expansion is performed.

After a controller-only fix, the same raw run can be reprojected without an
API call:

```bash
python3 scripts/run_hng2_schema_controller.py \
  --mode replay-live --run-id <existing-run-id> --quiet
```

## Safety invariants

- evidence references and spans must validate against supplied source text;
- Python hard constraints are never overwritten by the model;
- a candidate without a catalogue `person_id` cannot be treated as an
  existing-person resolution;
- `IdentityDecision` and `GraphAction` remain separate;
- `reasoning_content` recovery is envelope handling, not semantic bypass;
- canonical, Gold, SRM, frontend, and prior HNG artifacts remain untouched.
