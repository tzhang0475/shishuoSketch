# SC1M — Frozen SC1 v1 and Current Production Projection

## Purpose

SC1 previously served two different contracts: it was both a historical
experiment snapshot and the input to the current reader. Those contracts now
have separate names and validation rules.

`FROZEN_SC1_V1` is the historical snapshot. `SC1_CURRENT` is a deterministic
projection of the current reviewed authority. A current alias or identity
review may change `SC1_CURRENT`; it must never rewrite the historical bytes.

## The two contracts

| logical contract | physical path | use | mutability |
| --- | --- | --- | --- |
| `FROZEN_SC1_V1` | `data/derived/sc1-site.json` and `site/src/generated/sc1-site.json` | historical reproducibility, frozen downstream experiments, provenance | immutable |
| `SC1_CURRENT` | `data/derived/sc1-current-site.json` and `site/src/generated/sc1-current-site.json` | current production projection and frontend | rebuildable |

The frozen v1 manifest is
`data/frozen/sc1/v1/manifest.json`. Both frozen views remain byte-identical
and have SHA-256
`cc82c6738fcbf4fc14c12005a459048e71ce329492867d0910562fc6fdfda0d8`.

The current builder accepts only `--target current` (also the default). Its
write guard rejects either frozen output path. It generates the two current
views from one in-memory bundle, so the current derived and Vite inputs remain
byte-identical. The checked-in current views currently have SHA-256
`b916530264285dd7fa1d2e27a7a1dff8cd2ed794dfb3b84985881f8f209d8f6a`.

## Consumers and validation

The deployed reader imports
`site/src/generated/sc1-current-site.json` through `site/src/data.ts`.
Production frontend-data validation likewise checks the current paths. The
Pages workflow explicitly builds the current projection and then runs both
current validation and frozen-v1 integrity validation; it cannot refresh the
frozen snapshot as a build side effect.

The optional UX1 historical-depth shards remain a separate frozen downstream
display contract. Their historical validator and manifest intentionally retain
the v1 SC1 source hash; they do not import the SC1 reader bundle at runtime,
and a current-versus-frozen UX1 migration is outside SC1M. D1/H0/HNG/HDB/SFH
and other numbered experiment consumers likewise remain on v1 where their
frozen manifests require it. This preserves historical reproducibility while
the primary production reader uses SC1_CURRENT.

Use:

```text
npm run build:sc1
npm run validate:sc1
npm run validate:sc1:frozen
```

Historical experiments and validators that explicitly record the old SC1 path
remain attached to v1. They verify or consume the historical contract rather
than silently switching to current semantics. A future migration of a
downstream experiment should introduce its own current/frozen split instead
of changing that experiment's baseline in place.

## Why the bytes differ

The comparison in
`data/derived/sc1m-v1-to-current-delta.json` is a parsed semantic comparison,
not a raw-text diff. It records 13 changed projection records and no
serialization/order-only differences:

* 11 `people` records changed. The current reviewed alias authority downgrades
  shared or context-dependent forms from global exact resolution, removes
  three incorrectly borne title/collective aliases from the historical
  profile, and replaces the reviewed malformed `子少` alias surface with
  `子玄`.
* 2 derived `display.people` records follow those person-alias changes.
* All `stories`, `mentions`, `relations`, `evidence`, `story_chain`, scene
  contexts, and other top-level publication sections have the same parsed
  content and counts.

The traceable current inputs are `data/aliases.json`,
`data/annotation/sfh2r-manual-semantic-authority.json`, and
`data/annotation/sfh2r1-manual-semantic-authority.json`. The delta report
contains the exact field-level changes and these provenance paths. No
material difference is unexplained by this reviewed current authority.

The current projection is therefore suitable for the production reader while
the old snapshot remains suitable for historical reproducibility. This is a
semantic correction boundary, not an expected-hash refresh.

## Operating rule for future revisions

When reviewed semantic authority changes:

1. rebuild `SC1_CURRENT`;
2. validate its schema, provenance, and frontend contract;
3. generate and review a v1-to-current semantic delta;
4. keep all frozen SC1 snapshots and their hashes unchanged.

Do not add a `--target frozen` mode unless a genuinely frozen input stack can
reproduce that snapshot. Preserving a snapshot is safer than presenting a
non-reproducible regeneration command.

## Scope boundary

This migration does not migrate WP1 or historical HNG/HDB/HGE/SFH/SRM
pipelines. Several downstream research and frozen validation paths still
refer explicitly to v1 by design. WP1 has the same possible ambiguity and
should receive a separately audited WPM migration if it becomes necessary.

No canonical historical data, Gold data, reviewed annotations, or frozen
experiment artifacts are rewritten by SC1M.
