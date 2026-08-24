# HNG2-S — Historical Entity Schema V1

HNG2-S is an offline schema refactor and replay boundary.  It reads the
immutable HNG1R2, HNG2, and HNG2-L generated layers and writes a new
`data/generated/hng2-schema/` projection.  It performs no historical
expansion and makes zero DeepSeek/API calls.

The pipeline is explicit:

`Source Passage → MentionObservation → EntityInterpretation → CandidateEntity → ConstraintCheck → SemanticAssessment → IdentityRecommendation → IdentityDecision → GraphAction / ResearchGap`

`MentionObservation` contains only a source surface, exact span, source ref,
work, locator, and optional offsets.  Interpretation is separate and uses
controlled `entity_kind`, `mention_scope`, and `discourse_role` values.  A
title such as `文帝` can therefore remain ambiguous even when a source
passage is available; it does not become a provisional person automatically.

Candidates are Python-generated local keys (`c0`, `c1`, …).  Hard constraints
are Python-owned `ConstraintCheck` records and are not writable by a future
semantic-assist response.  `IdentityDecision` deliberately has no
`provisional` status: a new person is `resolved_new_candidate`, while its
separate `GraphAction` may create a `provisional_person` node.  Structural
expressions such as `喜弟預女` produce `not_single_person`, no single graph
node, and a blocked frontier action.

The future Chinese semantic-assist contract is stored in `manifest.json` only
as a JSON contract.  This stage does not invoke it.  `SearchPlan` and
`ResearchGap` are planning structures; the replay does not run searches.

Validation protects the prior HNG output trees and project inputs with stable
hashes.  The regression cases cover script-folded `山涛/山濤`, reviewed
`庾太尉`, the `卞壼（從父兄敦）` surname guard, structural kinship,
title-only `文帝`, metatextual `袁宏《紀》`, exact canonical names, and the
separation of relation semantics description from the strict semantic-level
enum.

The resulting schema is suitable for a next targeted live LLM validation,
but this replay itself is not a semantic model evaluation.
