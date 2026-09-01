# C0 — Repository hygiene and legacy artifact audit

## Scope

C0 removes only unquestionably obsolete workspace debris and records the
dependencies of generated experiment stages. It does not delete generated
experiment data, refresh frozen selections, change protected hashes, or alter
historical/semantic data.

## Phase A changes

- Removed the tracked editor swap file `content/.shishuo.txt.swp`.
- Removed the tracked Python bytecode files under `scripts/__pycache__/` and
  `tests/__pycache__/`.
- Added the repository-wide editor, OS, and Python test/type-check cache ignore
  rules to `.gitignore`, while retaining the existing rules.
- Moved `milestone-1-development-tasks.md` to
  `docs/archive/milestone-1-development-tasks.md` without changing its
  contents. `docs/archive/README.md` identifies archived files as historical
  design/provenance documents rather than current contracts.
- Removed `data/raw/` and `data/normalized/`. Each contained only `.gitkeep`.
  An exact repository-wide search found no live reference to either path or
  placeholder in scripts, tests, package/frontend files, manifests,
  protection registries, or generated input-hash contracts. The only prior
  references were in the archived Milestone-1 planning document.

## Generated-stage dependency findings

The complete inventory is in
`data/derived/repository-retirement-inventory.json`. It covers all 62
top-level directories under `data/generated/`, plus the retired empty
Milestone-1 paths. Dependency types are recorded explicitly:

- **A — semantic/runtime:** an active builder, projection, retrieval, or
  storage path reads the stage.
- **B — validation-only:** a validator or test enforces a stage contract.
- **C — provenance/hash-only:** a manifest, selection hash, input hash, or
  later audit preserves the stage.
- **D — documentation-only:** documentation records the stage.
- **E — no live reference:** the exact repository-wide scan found no live
  consumer.

The active dependency spine is:

```text
reviewed source inputs
  → HNG0 → HNG0.1 → HNG0.2 → HNG0.2R
  → HNG1 → HNG1R → HNG1R2 → HNG2
  → HDB1 Wave 1/Wave 2 → HDB2 inputs and frozen rescue stages

HNG2/HDB2/HGE1 fixed baselines → HGE validation and network-growth audits

SFH1 → SFH2 → SFH2R/SFH2R.1 reviewed repair materialization

HNG2 schema/controller/replay ← SRM0 frozen research-memory evidence
```

This is a dependency description, not a recommendation to rebuild any stage.
The HNG2 C1/C2/C3 validation outputs, HDB1 frozen selections, HDB2 rescue
stages, SFH2R manual-authority artifacts, and D1.0/D1.1 protected baselines
remain retained.

### DS2 and other future candidates

The DS1 → DS1.2 → DS1.2R → DS2 local-evidence pilot is classified as
`RETIREMENT_CANDIDATE`. Static analysis found only stage-local scripts,
validators, tests, review files, and historical documentation; no current
production, canonical, graph, retrieval, frontend, or active algorithm path
consumes the bundle. DS2 must still be retired as one provenance-preserving
bundle with its prerequisites, not as an isolated directory. C0 deliberately
does not delete it.

No other generated stage is classified as a retirement candidate. HDA/HNG/HDB
baselines are active inputs or current protected baselines. HNG2 schema/live
variants, HDB2 PSL/rescue variants, HGE runs, SRM0, SFH pilots, and SFH2R
outputs are frozen provenance because later manifests, validators, selection
contracts, input hashes, or reviewed repair records refer to them.

## Test-suite classification

All 153 `tests/test_*.py` modules were classified in
`data/derived/test-suite-classification-c0.json`:

| Class | Count | Use |
| --- | ---: | --- |
| `CURRENT_REQUIRED` | 57 | Current product, protected canonical, active pipeline, or frontend/graph contracts. |
| `HISTORICAL_REPRODUCIBILITY` | 86 | Numbered experiments, frozen outputs, research pilots, and historical builders. |
| `SOURCE_PAYLOAD_OPTIONAL` | 8 | Tests explicitly gated by the portable source-payload helper. |
| `LIVE_NETWORK_EXPERIMENT` | 2 | SRM live/transport behavior; network execution must remain opt-in. |

The classification is a suite-selection aid, not a proposal to move tests in
C0. A future split could expose `tests/current/` and `tests/historical/`
through separate discovery commands while leaving module locations stable;
source-payload and live-network tests should remain explicit opt-in markers.

## Protected scope confirmation

C0 does not modify SC1/WP1 inputs, canonical Persons, relations, Gold data,
reviewed semantic authority, or generated experiment stages. It does not
perform the pending SC1 semantic migration. Any existing SC1 rebuild/hash
mutation seen in CI remains a separate issue and is not repaired by this
cleanup.

## Recommended C1 sequence

1. Add a machine-readable dependency/protection manifest for each stage and
   require a two-phase retirement review: dependency removal, then deletion
   only after the complete provenance bundle is archived and hash-verified.
2. Prepare a DS1/DS1.2/DS1.2R/DS2 archive plan, retaining manifests, review
   annotations, source hashes, and the C0 inventory before any deletion.
3. Add explicit current-versus-historical test suite commands/markers without
   moving the existing test files wholesale.
4. Audit the remaining large frozen HDB2/SFH pilot trees for duplicate raw
   payloads only after downstream hash and review references are mapped.
5. Handle the known SC1/WP1 CI regeneration issue in its own protected-artifact
   investigation; do not fold it into artifact retirement.

## C0 validation notes

The focused DS1/DS1.2/DS1.2R/DS2 suite passed all 24 tests, and the
repository/source-protection subset passed all 30 tests. The DS1, DS1.2, and
DS1.2R validators pass. The DS2 validator is blocked by four pre-existing
protected-hash drifts (`s1-jianshu-source-registration.json`,
`sgz0-processed-corpus.json`, `site/src/App.tsx`, and `site/src/styles.css`)
recorded in the old DS2 manifest. No C0 change touches those files; expected
hashes were not updated.

An isolated portable full-suite attempt ran 1,162 tests but could not be a
green environmental result: the first disposable source copy lacked Git for
four Git-based assertions, and the host Python environment lacks the declared
`opencc-python-reimplemented` dependency for 15 imports. Four tests were
skipped. The main worktree was not used for that builder-writing run, so its
protected inputs stayed unchanged. These limitations are reported rather than
waived or repaired by C0.

## C1 follow-up status

C1 completed the safe retirement of the generated DS1/DS1.2/DS1.2R/DS2
research bundle. The C0 inventory remains the before-state; the post-retirement
inventory is `data/derived/repository-retirement-inventory-c1.json`, and the
pre-deletion hashes and dependency proof are in
`data/retired/ds-research-family-c1.json`. The optional site DS1 loader remains
as a dormant 404-safe compatibility consumer, while the obsolete preview
producer is no longer part of `build:site`. The separate active DS2.1A
derived research surface was not part of this retirement.
