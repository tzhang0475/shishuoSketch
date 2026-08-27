# HDB2-PSL1.3A — Reference semantic pre-judgment

PSL1.3A is an additive validation layer for the frozen HDB2 occurrence
pipeline. It does not change PSL weights, candidate scoring, reviewer or
rescue behavior, and it does not write canonical data.

## Boundary

```text
Occurrence
  → Python ReferenceHypotheses
  → strict semantic arbitration only when ambiguous
  → finalized ReferenceStructure
  → existing candidate/PSL1.1 scorer
  → existing reviewer/rescue path
```

Python proposes structures from grounded local syntax. Complete constructions
such as `X爲Y主簿`, `X尚主`, `家兄`, and an anchored `X之子` bypass the model.
A suffix such as `子` is only a hypothesis when the whole form could also be a
personal/courtesy form; `武子` is the regression example. The arbitration call
receives no candidate keys or Person IDs. Its components and evidence IDs are
validated against the same supplied packet before the structure is accepted.

The accepted structure retains `anchor_person`, `patron_or_possessor`,
`holder`, and `referent_candidate` separately. Structural expressions never
reuse an anchor or patron as the final candidate. `家兄` therefore remains a
kinship referent, and `敦主簿` retains its holder/patron distinction.

## Frozen upstream behavior

The existing PSL1.1/PSL1.2/PSL1.3 artifacts and implementations remain the
historical regression baseline. PSL1.3A writes only under
`data/generated/hdb2-psl1-3a/`; its offline mode uses a test fixture for the
ambiguous `武子` arbitration and makes no provider call. Live mode uses the
existing DeepSeek strict beta transport and the same frozen predicate,
reviewer, and rescue stages afterward.

All outputs are candidate-only:

```text
candidate_only = true
canonical_write_back = false
```
