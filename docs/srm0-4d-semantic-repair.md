# SRM0.4D — Semantic Failure Triage & Convergence Repair

SRM0.4D is a derived projection over the frozen SRM0.4C live artifacts. It
does not change the DeepSeek transport layer, prompts, retrieval registry,
Story selection, or the raw model responses.

The repair order is deterministic:

1. audit every current protocol/semantic failure;
2. reject unsupported evidence claims at claim level;
3. apply the existing two-round `D=0` / `N<0.2` saturation rule;
4. preserve unresolved questions as active instead of manufacturing a stop;
5. allow at most one targeted completion only when a required response is
   genuinely absent.

The `aspect → claim` projection used for the 33-youhui-012 response is a
structural field alias. The evidence object is still validated against the
local source before the claim is retained. Invalid sibling claims and
unstructured unanswered strings are rejected independently.

`data/generated/srm0/*/convergence/live/*/repair/` contains only derived
repair state. The original C raw outputs and attempt history remain immutable.
The rebuilt live summary retains the C transport metrics byte-for-byte and
adds question-level terminal counts for `reading_sufficient`,
`evidence_saturated`, `stable_conflict`, and active/unresolved questions.

`reading_sufficient` is a reading decision, not a claim that all historical
verification is complete. A genuine conflict can remain visible alongside a
reading-sufficient result; it is not silently converted into an accepted
canonical fact. No repaired state has canonical write-back authority.

