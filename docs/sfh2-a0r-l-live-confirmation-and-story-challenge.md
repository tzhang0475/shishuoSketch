# SFH2.2-A0R-L — Live Confirmation and Five-Story Challenge

SFH2.2-A0R-L is an isolated validation of the repaired A0R review contract.
It keeps the A0R semantic authority model and tests two cohorts: the frozen
20-case A0 regression set and 20 occurrence-level cases (four each) from five
new difficult Stories. It does not run a full corpus live pass, add Stories,
change production graph data, or write canonical history.

## Frozen protocol

The five challenge Stories are `09-pinzao-063`, `25-paidiao-015`,
`21-qiaoyi-011`, `10-guizhen-011`, and `02-yanyu-060`. Their exact mention
IDs and evidence witnesses are frozen in
`data/annotation/sfh2-a0r-l-challenge-selection.json`; the selection contains
no expected identities. `帝` in `10-guizhen-011` is represented by two
different mention IDs, and the two `某`/other repeated surfaces remain
occurrence-level inputs rather than identity keys.

The A0R prompts, schemas, consistency contract, model, and storage policy are
fingerprinted in `data/generated/sfh2-a0r-l/architecture-freeze.json`.
The model is `deepseek-v4-flash`, temperature 0, with thinking disabled. The
provider probe is a single minimal request. A failed environmental probe stops
the live phase; it is never converted into a retry storm.

The initial probe was executed before semantic inference and failed with
`Operation not permitted`, classified as an environmental network failure.
During the resumed execution, the API key was present and exactly one fresh
probe was attempted with the same frozen configuration. It failed with the
same environmental error, so the authoritative live phase was stopped without
any Pass 1/2/3 provider calls. The initial record remains unchanged at
`provider-preflight.json`; the resumed result is preserved separately at
`provider-preflight-resume.json`. The frozen offline run records this
explicitly; its 40 logical Pass-1 cache lookups are offline misses, not
provider attempts. Both occurrence-level and Story-level overlap with the
earlier A0/P1/P2 targeted selections are checked and empty.

## Routing and safety

Pass 1 is run for each occurrence. Pass 2 is routed only by A0R hard/review
severity. Pass 3 uses the repaired selector contract and is routed only when
the post-review conditions require it. Selecting Pass 1 or Pass 2 copies its
validated record exactly. Revisions are narrow, whitelist-checked patches.
Python supplies formal consistency and storage controls, not a replacement
historical identity.

The challenge review bundle is deliberately unevaluated by the tested model:
`data/generated/sfh2-a0r-l/challenge-human-review.json` and `.md` leave the
historical answer and notes blank for external review. A0 regression gold is
consumed only after inference. All outputs remain `candidate_only` with
`canonical_write_back=false`; aliases, profiles, Persons, relations, and
canonical graph facts are not mutated.

## Results

The machine-readable result is in `data/generated/sfh2-a0r-l/metrics.json`.
It records provider preflight, cohort routing, dimension-separated A0
evaluation, challenge structural behavior, transport accounting, and safety
counts. If the provider is unavailable, the regression and challenge semantic
results are explicitly marked unavailable rather than scored as historical
model performance; challenge correctness remains `pending_external_review`.

The A0R offline counterfactual remains the relevant contract baseline:
selector-copy repair changed strict final accuracy from 70% to 75% and reduced
reviewer damage from one case to zero. The A0R-L challenge is not a saturation
or coverage experiment.

The dependency-complete portable repository suite completed with 1,280 tests
passing. A system-Python replay was also attempted and exposed only the
pre-existing missing `opencc` dependency; the repository virtual environment
contains that declared dependency and passed the full suite. Offline A0R-L
derived outputs were replayed twice with byte-identical hashes for every
root-level artifact. The final recommendation remains
`sfh2_live_semantic_architecture_provider_unavailable`, not a claim about
semantic accuracy.

## Limitations

The five Stories are a targeted difficulty sample, not a random estimate of
corpus accuracy. Existing SFH1 semantic packets are reused, and old retrieval
metadata is evidence context only. Formal consistency can expose structured
contradictions but cannot discover every historical-semantic mistake; those
cases require external review of the frozen challenge bundle. No full SFH2.2,
Wave C, or production migration follows this pilot.
