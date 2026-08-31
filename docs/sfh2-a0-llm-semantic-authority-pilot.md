# SFH2.2-A0 — LLM Semantic Authority + Logical Consistency Review Pilot

SFH2.2-A0 is an isolated 20-occurrence experiment. It tests whether
historical-semantic decisions can be moved out of Python heuristics while
retaining deterministic safety, provenance, and storage controls. It does not
replace SFH2, update canonical history, add production Persons, or run a
full-corpus live pass.

## Authority boundary

The pilot uses this order of authority:

```text
reviewed human semantics > validated LLM semantics > soft consistency > retrieval hint
```

Pass 1 (Primary Historian) receives the evidence packet without candidate IDs
or evaluation labels and produces one structured semantic record. Python then
performs only formal checks and candidate-only realization. Pass 2 (Critical
Reviewer) rereads every case, including cases with no Python flag. Pass 3
(Adjudicator) runs only for disagreement, abstention, invalid review output, or
remaining formal flags. Python never supplies a replacement historical answer.

The Python consistency engine checks evidence references, schema/storage type,
structured field contradictions, explicit identity distinctness, prohibited
reflexive graph facts, and source-role projection conflicts. These are review
signals or hard safety vetoes, not historical interpretations. Graph facts are
used as hypothesis challengers, never as an identity oracle.

All results carry `candidate_only=true` and `canonical_write_back=false`.

## Controlled set and isolation

The fixed selection contains the 20 requested cases, resolved from the frozen
SFH1 mention ledger. Its selection hash is:

```text
b8162d9d470c6359c67a8ed31aa31ef82149c12d92dd9a694b62327fc204bbc3
```

Evaluation labels live only in `data/annotation/sfh2-a0-evaluation-gold.json`.
The selection, source packets, semantic prompts, consistency checks, and
candidate realization never receive those labels. The provider payloads also
contain no production Person IDs. The first v1 provider run exposed a
structured-output formatting problem; it is retained under the live raw
artifacts for provenance but is not combined with the authoritative run. The
v2 contract was frozen and all 20 cases were rerun as one authoritative run.

## v2 run results

The authoritative run used `deepseek-v4-flash`, temperature `0`, and disabled
thinking. It used 46 provider attempts: 21 Pass 1 attempts (one retry), 20
Pass 2 attempts, and 5 Pass 3 attempts. There were no provider request
failures; two Pass 1 attempts were invalid before the bounded retry succeeded.

| measure | result |
| --- | ---: |
| cases | 20 |
| Pass 1 exact evaluation | 15/20 (75%) |
| Pass 2 exact evaluation | 15/20 (75%) |
| Pass 1/Pass 2 agreement | 19/20 (95%) |
| Pass 3 cases | 5 |
| final exact evaluation | 14/20 (70%) |
| Pass 1 errors recovered by final result | 0 |
| new errors introduced by review | 1 |
| reviewer damage | 1 |
| appropriate abstentions | 0 |
| high-confidence final false identities under the frozen evaluation labels | 6 |
| formal Pass 1 flagged cases | 5 |
| formal Pass 2 flagged cases | 4 |

The exact evaluation is deliberately strict: a semantically related answer or
an answer with the wrong occurrence role is not counted as correct. The run
therefore does not meet the A0 `>=95%` readiness target. The result is an
evaluation finding, not a reason to insert Python answer mappings.

Notable outcomes include correct proposal/final records for `王子敬→王獻之`,
`阮光禄→阮裕`, `宣王→司馬懿`, `齊桓公` as a historical exemplum,
`太丘長→陳寔`, `王藍田→王述`, `茂弘→王導`, `卿→庾亮`, `康→嵇康`,
`鍾士季→鍾會`, and `嚴仲弼→嚴隱`. `字景真` was semantically identified as
桓亮 but classified as a historical person rather than the expected
person-attribute record. `吾` and `之` were resolved to evidence-local forms
(`魏武` and `劉遺民`) rather than the stricter evaluation canonical labels.
`滔` and `嘏` were identified but assigned narrative rather than annotation
roles. These distinctions remain visible in the case-level evaluation and are
not repaired by Python.

The v2 run did not demonstrate a Pass-2 correction of a strict evaluation
error: Pass 2 largely confirmed Pass 1 and the one final review change counted
as reviewer damage under the frozen labels. In particular, the pilot shows
that a multi-pass architecture needs better review routing/contracts before it
can be made the default, even though the storage and authority boundary held.

## Safety and storage

The structural validator passed. The run produced:

```text
production Person creations: 0
canonical writes: 0
alias mutations: 0
profile mutations: 0
Python identity replacements: 0
substring candidate creation: 0
source-role graph conflicts: 0
internal consistency errors: 0
```

Annotation/source roles are excluded from the core graph eligibility path,
including `annotation_person`, `citation_source_person`,
`historical_exemplum`, `person_attribute`, and collective/structural roles.
Existing registry matches are lookup results attached after the semantic
record; they are not provider-created production identities.

## Cost and replay

The live v2 run used 179,392 prompt tokens and 25,797 completion tokens,
205,189 tokens total, with median request latency of 3.764 seconds and a
maximum of 5.505 seconds. The pass breakdown was:

| stage | attempts | prompt | completion | total |
| --- | ---: | ---: | ---: | ---: |
| Primary Historian | 21 | 80,916 | 9,061 | 89,977 |
| Critical Reviewer | 20 | 77,694 | 13,375 | 91,069 |
| Adjudicator | 5 | 20,782 | 3,361 | 24,143 |

Two subsequent offline replays used the cached v2 raw responses; their cache
miss count was zero and they made no provider calls. A further hash comparison
of the deterministic A0 root artifacts was byte-identical. Operational
transport metadata remains separate from the semantic/derived payloads.

## Artifacts and follow-up

The implementation is isolated under `scripts/sfh2_a0/`, with the generated
selection, packets, pass outputs, consistency audits, evaluation, transport,
and cached raw responses under `data/generated/sfh2-a0/`. The v2 contract
transition is constrained to unchanged input hashes and selection hash; it
cannot silently authorize a different case set.

The preliminary recommendation is:

```text
sfh2_semantic_authority_needs_review_routing_revision
```

The next engineering step should improve semantic contract adherence and
review routing in another isolated experiment. Historical correctness of the
remaining ambiguous cases must continue to be judged by semantic review, not
by Python lexical rules. No full SFH2.2 live run is authorized by this pilot.
