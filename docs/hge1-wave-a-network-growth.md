# HGE1-WA — Story-network growth wave A

HGE1-WA is a bounded, candidate-only expansion measurement. HDA1's input
snapshot and hashes were frozen first. The wave then selected 20 research-only
Stories from the local registered corpus, before semantic calls, with six
deterministic channels:

| selection channel | Stories |
| --- | ---: |
| graph-guided / frontier-rich | 4 |
| likely new-person-rich | 4 |
| relation-rich | 4 |
| underrepresented chapter | 3 |
| peripheral / low-connectivity | 3 |
| random control | 2 |

The exact selection and target snapshots are
`data/annotation/hge1-wave-a-selection.json` and
`data/annotation/hge1-wave-a-target-selection.json`. They contain no
production Story overlap and no prior HNG/HDB experiment overlap; their hashes
are checked by `scripts/validate_hge1.py`.

The frozen Story IDs are: `04-wenxue-054`, `11-jiewu-003`,
`04-wenxue-050`, `01-dexing-008`, `01-dexing-005`, `35-huoni-002`,
`05-fangzheng-007`, `05-fangzheng-022`, `21-qiaoyi-008`, `02-yanyu-076`,
`04-wenxue-003`, `14-rongzhi-019`, `23-rendan-018`, `10-guizhen-003`,
`05-fangzheng-021`, `26-qingdi-018`, `21-qiaoyi-006`, `34-pilou-006`,
`12-suhui-001`, and `16-qixian-005`.

## Wave execution

The live provider completed all 80 frozen HNG2 semantic calls (20 Person
READ/FILL pairs and 20 Temporal READ/FILL pairs). There were no retries,
provider failures, parse failures, or truncations. The run used 123,414
semantic response tokens, with median latency 2.175 seconds and maximum
latency 3.498 seconds. Raw responses are retained under
`data/generated/hge1/live/hge1-wa-final-live-network/`.

The resulting projection is candidate-only. It produced 20 target-level
candidate observations, 27 validated relation-card candidates, 24 temporal
candidate assertions, 38 rejected Person evidence items, and 20 P1 review
items. No existing production Person was recovered by the selected target
snapshot, and no production Person ID was allocated. These counts describe
the frozen run's candidate output; they are not canonical historical facts.

## Network delta

The graph baseline was 143 published Stories, 75 existing Persons, 13 HDB2-F
candidate Persons, 330 PersonStory links, 347 graph nodes, 996 graph edges,
and six connected components. The candidate-only after projection is:

| measure | baseline | after | delta |
| --- | ---: | ---: | ---: |
| Stories | 143 | 163 | +20 |
| existing Persons | 75 | 75 | +0 |
| candidate Persons | 13 | 33 | +20 |
| PersonStory links | 330 | 350 | +20 |
| identity occurrences | 425 | 445 | +20 |
| graph nodes | 347 | 387 | +40 |
| graph edges | 996 | 1,016 | +20 |
| connected components | 6 | 26 | +20 |
| largest component | 342 | 342 | +0 |
| social relation candidates | 231 | 258 | +27 |

The 20 new candidate Person/Story pairs remain separate components because
the live extraction did not safely resolve an existing Person endpoint. The
largest existing component therefore did not grow. The candidate and review
artifacts preserve the relation and temporal evidence for later human review;
they do not mutate H0A, H0B, canonical Persons, or canonical Relations.

## Marginal yield by channel

| channel | Stories | existing links | new candidate observations | relation candidates | review items |
| --- | ---: | ---: | ---: | ---: | ---: |
| graph-guided / frontier-rich | 4 | 0 | 4 | 4 | 4 |
| new-person-rich | 4 | 0 | 4 | 6 | 4 |
| relation-rich | 4 | 0 | 4 | 6 | 4 |
| underrepresented chapter | 3 | 0 | 3 | 7 | 3 |
| peripheral / low-connectivity | 3 | 0 | 3 | 3 | 3 |
| random control | 2 | 0 | 2 | 1 | 2 |

This single wave suggests useful relation-card yield varies by channel, with
underrepresented and relation-rich selections producing the most candidates
per Story in this run. It does not establish a saturation curve: all target
identities were candidate-only and no existing-network link was recovered.
The deterministic baseline, selection, growth series, and protected hashes
are the appropriate inputs for a later Wave B decision.
