# SFH2.2-P1 — LLM-First Historical Entity Proposal Pilot

SFH2.2-P1 is a bounded, candidate-only experiment on ten frozen occurrence
cases. It tests proposal-first identity handling without changing the 188-Story
SFH1/SFH2 projection, PSL weights, canonical Persons, aliases, or historical
facts.

The authority boundary under test is:

```text
source evidence → LLM entity proposal → Python registry/candidate realization
                → LLM identity-equivalence review → Python safety/storage gate
```

The LLM may propose a historically supported name that is absent from the
registry. Python only validates the schema and evidence, looks up an existing
Person, allocates a deterministic candidate-only ID on a registry miss, applies
explicit hard vetoes, and controls storage. In particular, `related_person`,
`office_relation`, `kinship_relation`, `citation_relation`, and `attribute_of`
can never cross the identity boundary: only `same_person` can resolve an
identity. A `person_attribute` proposal such as `字景真` never creates a Person.

## Frozen pilot

The selection is
`data/annotation/sfh2-2p1-selection.json`, with generated copies under
`data/generated/sfh2-2p1/`. The same ten occurrence selections were retained
through the versioned prompt corrections; the final frozen selection hash is:

`b42d08a8757c4451c9f4b1a01926d0d5f3821b81f6e1b649a00dbc6330067134`

The final run used `deepseek-v4-flash`, temperature `0`, thinking disabled,
strict function tools, pilot version `sfh2-2p1-v4`, proposal prompt
`sfh2-2p1-entity-proposal-v3`, and equivalence prompt
`sfh2-2p1-identity-equivalence-v1`. Gold/evaluation fields were kept in the
selection only and were not copied into provider packets.

The ten cases are: 勒, 齊桓公, 車騎, 王子敬, 阮光禄, 嚴仲弼, 潁, 字景真,
桓宣武, and 宣王. There were no blind controls in this deliberately reviewed
ten-case pilot; the resulting artifacts are an evaluation, not historical
gold for the whole corpus.

## Results

All ten entity proposals passed strict validation and matched the reviewed
case definition. The nine historical-person proposals were all realized as an
existing Person or a candidate historical entity (`9/9`, 100%); 字景真 was
correctly retained as a structural/person-attribute result with no Person
candidate. Nine historical-person cases reached a `same_person` identity
decision: 桓宣武 resolved to existing `person-008` (桓溫), and the other eight
were candidate-only entities. 潁 was preserved as the short referent in the
source while the model supplied the supported display form 王潁; this does not
create a canonical Person.

| surface | proposal | final state | realized identity |
|---|---|---|---|
| 勒 | 石勒 | local_candidate_resolved | candidate-only 石勒 |
| 齊桓公 | 齊桓公 | local_candidate_resolved | candidate-only; historical exemplum |
| 車騎 | 謝玄 | local_candidate_resolved | candidate-only 謝玄 |
| 王子敬 | 王獻之 | local_candidate_resolved | candidate-only 王獻之 |
| 阮光禄 | 阮裕 | local_candidate_resolved | candidate-only 阮裕 |
| 嚴仲弼 | 嚴隱 | local_candidate_resolved | candidate-only 嚴隱 |
| 潁 | 王潁 / surface 潁 | local_candidate_resolved | candidate-only; short form retained |
| 字景真 | person attribute 景真 | structural_reference | no Person created |
| 桓宣武 | 桓溫 | stable_entity_resolved | production `person-008` |
| 宣王 | 司馬懿 | local_candidate_resolved | candidate-only 司馬懿 |

Proposal accuracy was `10/10` (100%), including `9/9` historical-person
proposals. Proposal realization was 100% for the nine correct historical-person
proposals. Conditional identity decisions were correct in all nine historical
cases. Appropriate abstentions were zero after the final equivalence gate was
fixed to honor the declared `same_person_candidate_key` when the alternative
dossier contained duplicate representations of the same entity. No wrong
resolution or high-confidence false positive was recorded.

The equivalence reviewer sometimes marked multiple temporary representations as
`same_person` (for example a full name and a short form). The Python gate used
the explicitly declared key, rather than incorrectly requiring exactly one
same-person row. This is deduplication of the candidate dossier, not a semantic
Python identity decision.

## Safety and storage

The pilot recorded zero related-person promotions, zero attribute promotions,
zero forbidden mappings, zero substring-derived candidates, zero profile
contamination, and zero HDA2-suppressed-claim reentries. The hashes of
`data/aliases.json`, `hdb2-f-person-knowledge.json`, and
`hdb2-f-candidate-person-knowledge.json` were unchanged. No production Person
ID, alias, profile, canonical relation, or other canonical fact was written;
every P1 result has `candidate_only=true` and `canonical_write_back=false`.

Network-role handling remained separate from identity. The historical-exemplum
cases 齊桓公 and 宣王, and the person-attribute case 字景真, were excluded from
the core Story-network projection while their semantic results remained in the
pilot artifacts.

## Comparison with SFH2.2-P

P1 changes the order of authority rather than merely enlarging the old
candidate list. On overlapping cases:

* P had no final resolution for 王子敬, 阮光禄, or 宣王; P1 proposed and
  realized 王獻之, 阮裕, and 司馬懿 as candidate-only entities.
* P treated 齊桓公 as the local candidate 管夷吾; P1 represented 齊桓公 as the
  proposed target and classified 管仲/管夷吾 as alternatives rather than
  allowing a related person to become identity.
* P promoted `字景真` as a local candidate 桓亮; P1 classified it as a
  person-attribute and created no Person.
* P left 嚴仲弼 as a short candidate; P1 proposed 嚴隱 and kept the full form,
  courtesy-name evidence, and candidate realization together.
* Both pilots recovered 勒 → 石勒, 車騎 → 謝玄, 桓宣武 → 桓溫, and the short
  潁 case without a forbidden production mapping.

The prior P run contained 30 cases (25 gold and 5 blind), with candidate recall
20/23 (`0.8696`) and conditional semantic precision `1.0`; its artifacts remain
unchanged. P1's 10-case results are not directly comparable as a corpus metric,
but they demonstrate the intended registry-miss and related-person safety
behavior on the selected cases.

## Provider cost and replay

The authoritative live run was `data/generated/sfh2-2p1/live/sfh2-2p1-live-v4/`.
It used 10 proposal calls and 9 equivalence calls, 19 new provider calls in
total, with no retries, failures, invalid payloads, or truncations. It consumed
63,180 prompt tokens and 9,909 completion tokens (73,089 total). Median/max
latency was 2.843/7.581 seconds. The stored provider cost is selected only from
the current versioned prompt contract; earlier failed/debug runs remain
separate provenance and are not mixed into the final cost.

Two offline replays used the cached v4 responses. After excluding operational
run IDs and mode fields, all deterministic JSON output payloads were byte/
structure identical. No additional provider call was made during replay, and
the authoritative raw responses remain under the immutable live-run directory.

## Limitations and recommendation

This is a small reviewed pilot with no blind cases. It establishes that a
proposal-first path can preserve registry-miss referents and block related or
attribute candidates from crossing the identity boundary, but it does not
establish whole-corpus historical accuracy. The corrected 潁 display expansion
also illustrates that short-form normalization needs continued human audit.

The pilot recommendation is:

`sfh2_2_proposal_first_ready`

This recommendation is limited to continuing bounded proposal-first validation;
it does not authorize full SFH2.2 consolidation, a 188-Story live run, new
production Persons, graph materialization, HGX1, or Story expansion.
