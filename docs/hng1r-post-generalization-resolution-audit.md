# HNG1R — Post-Generalization Identity Audit & Repair

HNG1R is an offline projection over the immutable HNG1 live evaluation. It
does not call DeepSeek, rerun retrieval, or alter HNG1 raw responses.

The only new resolver stage is `contextual_short_name`. It runs after the
frozen HNG1/HNG0.2R decisions and considers only short or abbreviated
surfaces. Existing Persons whose canonical or known form ends with the
surface are ranked using deterministic evidence from the current opened
passage: biography or source-unit title, an explicit full name in the local
passage, the current seed, an already-known HNG one-hop neighbor, and temporal
compatibility. A unique context-compatible candidate is resolved; ties and
generic role words such as `兄`, `父母`, `客`, `帝`, and `太子` remain
unresolved or ambiguous.

The repair records the original surface, candidate set, context signals,
resolution method, and confidence. Provisional HNG identities are not
promoted to canonical Persons. Relation and temporal projections are rebuilt
only when the identity projection changes, and all evidence references remain
bound to the frozen HNG1 source registry.

The audit sample contains no automatic human judgments. Every identity has a
local review field with `correct`, `false_merge`, `uncertain`, and
`not_reviewed`. The HNG2 readiness report therefore remains
`awaiting_meaningful_human_audit` until reviewers assess the sample. A false
merge rate is not invented from model output.

Run the deterministic repair with:

```text
python3 scripts/build_hng1r.py
python3 scripts/validate_hng1r.py --mode portable
```

HNG1R writes only under `data/generated/hng1r/` and
`data/annotation/hng1r-review.json`. It does not write canonical Persons,
Relations, Facts, Events, Gold data, SRM data, or frontend production data.
