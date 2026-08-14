# P3B.1 Person Expansion Wave 1

> This report records the frozen Top-10 materialization. New identity, alias, Mention, and Person Sketch records remain candidate data; no Relation or Story publication fact is created here.

## Selection freeze

- Wave: `p3b-wave-1`
- Ranking artifact: `data/derived/person-expansion-wave-1-ranking.json`
- Ranking SHA-256: `a81eefefea58f7910dd5ad997a84b395a5220a906ee46f19f44ef630362dcab2`
- Person registry: 7 → 17
- Selection authority: pre-mutation P3A ranks 1–10; no rank substitution.

## Materialized Persons

| Rank | Person | Candidate ID | Score | Exact aliases | Contextual aliases | Shishuo main/Liu Stories | Jinshu units | Promoted | Withheld | SC1 stories | Relations |
|---:|---|---|---:|---|---|---:|---:|---:|---:|---:|---:|
| 1 | 桓溫 (`person-008`) | `candidate-identity-098-liezhuan-003-7859332a18d3` | 59.112247 | 元子, 桓元子, 桓温, 桓溫 | 桓公, 桓宣武 | 12/34 | 1 | 51 | 3 | 1 | 0 |
| 2 | 劉惔 (`person-009`) | `candidate-identity-075-liezhuan-006-8fa047488139` | 51.311118 | 劉惔, 劉真長, 真長 | 劉與林公 | 24/18 | 1 | 63 | 1 | 2 | 0 |
| 3 | 庾亮 (`person-010`) | `candidate-identity-073-liezhuan-001-57cfabf05a69` | 50.804676 | 元規, 庾亮, 庾元規 | 庾公, 庾謂曰君 | 18/23 | 1 | 47 | 4 | 0 | 0 |
| 4 | 王敦 (`person-011`) | `candidate-identity-098-liezhuan-001-100db758183c` | 46.281037 | 王敦, 王處仲, 處仲 | 王大將軍, 王敦聞君 | 21/28 | 1 | 57 | 7 | 0 | 0 |
| 5 | 袁宏 (`person-012`) | `candidate-identity-092-liezhuan-013-76b547bbee32` | 44.569684 | 彦伯, 袁宏, 袁彦伯 | 袁公 | 8/8 | 1 | 15 | 2 | 1 | 0 |
| 6 | 温嶠 (`person-013`) | `candidate-identity-067-liezhuan-001-1769bc7aa348` | 41.050457 | 太真, 温太真, 温嶠 | 温公 | 10/12 | 1 | 28 | 1 | 0 | 0 |
| 7 | 王濛 (`person-014`) | `candidate-identity-093-liezhuan-010-e8abd34dc108` | 39.928571 | 仲祖, 王仲祖, 王濛, 王蒙 | — | 7/15 | 1 | 31 | 0 | 1 | 0 |
| 8 | 孫晷 (`person-015`) | `candidate-identity-088-liezhuan-007-ca650e9ceb0f` | 39.321433 | 孫晷, 文度 | — | 12/3 | 1 | 25 | 0 | 1 | 0 |
| 9 | 王遐 (`person-016`) | `candidate-identity-093-liezhuan-011-9b983af9b748` | 37.362249 | 桓子, 王遐 | — | 4/2 | 1 | 8 | 0 | 1 | 0 |
| 10 | 蘇峻 (`person-017`) | `candidate-identity-100-liezhuan-009-cd60f50d80a7` | 37.349490 | 子高, 蘇子高, 蘇峻 | — | 12/13 | 1 | 29 | 0 | 0 | 0 |

## Occurrence policy

Only strong-candidate exact associations with a validated section-local anchor were promoted to production Mention records. Contextual, ambiguous, generic-title, and unsafe-anchor occurrences remain in the machine-readable withheld report. Promotion preserves main-text versus Liu-annotation sections and does not infer participant status.

## Relations and publication

No Relation records were created. PersonStory links may cover the full Shishuo corpus, but the SC0/SC1 Story publication set is unchanged.

### Withheld surfaces — 桓溫

- `02-yanyu-055` · main_text · `桓公` · `contextual_association`
- `06-yaliang-029` · main_text · `桓公` · `contextual_association`
- `28-chumian-007` · main_text · `桓宣武` · `contextual_association`

### Withheld surfaces — 劉惔

- `03-zhengshi-018` · main_text · `劉與林公` · `contextual_association`

### Withheld surfaces — 庾亮

- `01-dexing-031` · main_text · `庾公` · `contextual_association`
- `02-yanyu-049` · main_text · `庾謂曰君` · `contextual_association`
- `08-shangyu-065` · main_text · `庾公` · `contextual_association`
- `33-youhui-010` · main_text · `庾公` · `contextual_association`

### Withheld surfaces — 王敦

- `05-fangzheng-031` · main_text · `王大將軍` · `contextual_association`
- `05-fangzheng-033` · main_text · `王大將軍` · `contextual_association`
- `09-pinzao-015` · main_text · `王大將軍` · `contextual_association`
- `27-jiajue-006` · main_text · `王大將軍` · `contextual_association`
- `30-taichi-001` · liu_annotation · `王敦聞君` · `contextual_association`
- `33-youhui-008` · main_text · `王大將軍` · `contextual_association`
- `36-chouxi-003` · main_text · `王大將軍` · `contextual_association`

### Withheld surfaces — 袁宏

- `03-zhengshi-003` · main_text · `袁公` · `contextual_association`
- `03-zhengshi-003` · main_text · `袁公` · `contextual_association`

### Withheld surfaces — 温嶠

- `33-youhui-009` · main_text · `温公` · `contextual_association`
