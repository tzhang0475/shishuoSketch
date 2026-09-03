# SFH2.2-A2GR — Human Gold Resolution and Identity Freeze

SFH2.2-A2GR is an offline closeout of the A2G ontology audit. It used no
provider calls and did not regenerate Historian A, Historian B, or adjudicator
outputs. The A2/A2R/A2G directories remain immutable experiment evidence.

## Reviewed Gold promotion

Human semantic review resolved one Gold boundary case:

* `03-zhengshi-001 / 太丘長` is an `office` occurrence with
  `person_attribute` role (`office_held`), borne by 陳仲弓. It is not an
  independently identity-evaluable historical-person occurrence in this
  construction.

The reviewed authority record is
`data/annotation/sfh2-a2gr-human-semantic-authority.json`. The active
evaluation Gold is now v3 and records its predecessor SHA256 and promotion
reason. `滔`, `嘏`, and `王師` were explicitly reaffirmed; their Gold content
was not mutated.

## Identity qualification

The frozen A2R results were evaluated against the reviewed Gold after all
semantic outputs were already frozen. The historical-person cohort changed
from 18 to 17 cases. The final result is 17/17, with 100% resolution coverage,
zero unresolved historical-person cases, and zero adjudicator damage.

The identity freeze manifest is
`data/frozen/sfh2/identity-v1/manifest.json`. It records hashes for the
reviewed authority, frozen experiment trees, source semantic caches, final
results, evaluation code, and protected canonical inputs.

## Frozen authority boundary

Historical evidence is interpreted by Historian A and an independent
Historian B, compared structurally, and adjudicated where required. Python
performs integrity, consistency, deterministic selection, and storage-safety
checks only. Human semantic review promotes evaluation Gold and canonical
truth. Semantic inference never writes production Persons, aliases, profiles,
or canonical facts.

The freeze has no retrieval candidate gate, no lexical identity rules, no
substring identity, no automatic alias-string identity equivalence, and no
production canonical write-back.

The next proposed experiment is SFH2.2-A2O, which is documented separately.
No A2O implementation or full 188-Story run is part of A2GR.
