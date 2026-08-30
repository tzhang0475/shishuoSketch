# SFH2.2-P — Semantic Identity Resolution Pilot

SFH2.2-P is a bounded evaluation of the repaired SFH2R.1 semantic-precedence
pipeline. It does not expand the Story universe, change PSL weights, mutate
canonical data, or create production Person IDs. The experiment tests four
separate properties: candidate recall, semantic selection precision, registry
miss handling, and recurrence of the contamination mechanisms repaired by
SFH2R.1.

## Frozen design

The authoritative occurrence-level freeze is
`data/annotation/sfh2-2p-selection.json`; generated copies live under
`data/generated/sfh2-2p/`. Selection was computed from the existing SFH1
validated-mention ledger before any pilot provider call. It contains 30 cases:
25 reviewed-gold cases and 5 blind controls, with 24 distinct Stories. The
selection hash is:

`e6abd4ce1326600fc7615d9bbfbc0cfb86b82309973baf4bc445d51a4d0f5740`

The requested examples that are not validated occurrences in the frozen
188-Story SFH1 packet universe are recorded in `unavailable_reviewed_cases`
instead of expanding the experiment. No gold answer or evaluation label is
sent in a provider packet. The blind review bundle is
`data/generated/sfh2-2p/human-review.json`.

The pilot reuses SFH1 mention boundaries and source packets, then runs one L3
reference-semantics call per selected Story and one L5 identity-judgment call
per candidate-bearing occurrence. Python supplies candidate keys, exact
evidence provenance, and hard vetoes; the model supplies semantic
interpretation and historical fit. The final closeout replay used the cached
raw responses from the authoritative live run, so it made no additional
provider calls.

## Results

There were 23 gold cases with an expected identity (16 candidate-historical
and 7 production-person cases). The correct candidate entered Python's set in
20/23 cases (`candidate_recall = 0.8696`). Conditional on candidate recall,
18/18 non-abstaining identity decisions were correct
(`semantic_precision = 1.0` under that definition). The three recall misses
were `王子敬 → 王羲之`, `阮光禄 → 阮裕`, and `宣王 → 司馬懿`; `士龍 → 陸雲`
was recalled but remained review-required after an invalid/incomplete L3
semantic result.

Two explicit non-identity controls were promoted and are therefore reported
as semantic false positives rather than hidden as abstentions:

* `09-pinzao-018 / 潁`, a contextual safety control;
* `19-xianyuan-032 / 字景真`, a structural attribute control.

Neither promoted a forbidden production mapping, but both prevent a
`sfh2_2_ready` recommendation. The resulting recommendation is
`sfh2_2_candidate_retrieval_revision`.

The 16 reviewed registry-miss cases produced 13 candidate-only historical
entities with supported non-production names, including 石勒, 孫綽, 桓亮,
王濟, 孔坦, 康帝, 殷仲堪, 祖逖, 謝聘, 桓謙, 殷仲文, 桓伊, and 陸雲. No registry
miss was forced to an unrelated existing Person. Existing-person controls
resolved safely where recalled, while 劉尹 appropriately abstained and
王子敬 remained a candidate-recall failure.

## Semantic and graph safety

Candidate retrieval is broad but is not resolution: canonical forms, reviewed
forms, validated local whole mentions, and L3 referent hints only add Python
candidate keys; L5 must still support a candidate with grounded evidence. A
missing registry entity is represented by a stable candidate-only ID. The
pilot never writes `data/people.json` or `data/aliases.json`, never turns an
occurrence into a global alias, and preserves HDA2/SFH2R.1 wrong-bearer
suppression.

The final audit found zero new global aliases, zero occurrence-propagated
alias evidence, zero substring-derived candidates, zero profile-contamination
recurrences, and zero forbidden mappings. The alias file hash was unchanged.
Network roles were kept orthogonal to identity: historical-exemplum and
genealogy-ancestor records were marked ineligible for the core Story graph,
while narrative references remained eligible when resolved.

## Provider cost and replay

The authoritative live run used the fixed `deepseek-v4-flash` model at
temperature zero with thinking disabled and strict function tools. It made 24
L3 calls and 30 L5 calls (54 total), within the 40/40 stage budgets, with
151,681 prompt tokens and 36,244 completion tokens (187,925 total). L3 used
80,067 tokens with median/max latency 3.094/5.507 seconds; L5 used 107,858
tokens with median/max latency 4.538/7.651 seconds. Retries, provider
failures, invalid payloads, and truncations were all zero in that authoritative
run. Earlier failed/debug attempts are retained under the versioned `live/`
directories and are not mixed into the final semantic outputs.

`data/generated/sfh2-2p/transport.json` records the authoritative provider
cost, while `replay-transport.json` records the final zero-token cache
replay. No full 188-Story live run, canonical write, SFH2.2 consolidation, or
Story expansion was performed.

The pilot is not a claim of historical completeness. Its primary actionable
limitation is candidate recall below the 95% target, with two semantic
false-positive controls requiring review of the L3/L5 boundary. Future work
should improve grounded candidate retrieval and semantic guardrails in a new
pilot version before broader identity consolidation.
