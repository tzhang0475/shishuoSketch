# SFH2.2-F1R Human Review Sheet

This sheet is a compact index for human review. It is not Gold and does not
promote any candidate. Each row is pinned by the exact occurrence key in the
machine-readable artifacts. Use `semantic-acceptance-review.json` for the
source context, model explanations, transport state, and proposed change.

| Story / target | Exact target | Identity state | Primary → final | Reason alignment | F1R class |
|---|---|---|---|---|---|
| 01-dexing-008 / 季方 | [2,4] liu-annotation-004 | resolved candidate | reference → reference | exact | plausible |
| 09-pinzao-040 / 孔巖 | [17,19] main | resolved candidate | participant → reference | exact | plausible; boundary override |
| 34-pilou-006 / 殷公 | [23,25] main | blocked | — | unclear | transport-blocked |
| 08-shangyu-020 / 剌史 | [18,20] liu-annotation-008 | resolved office context | reference → reference | exact | semantic + applicability candidate |
| 05-fangzheng-055 / 子野 | [4,6] main | resolved candidate | speaker → speaker | wrong occurrence | semantic candidate |
| 25-paidiao-028 / 堯 | [26,27] liu-annotation-001 | resolved candidate | historical_exemplum → historical_exemplum | exact | semantic candidate |
| 05-fangzheng-058 / 王文度 | [0,3] main | blocked | — | unclear | transport-blocked |
| 09-pinzao-008 / 諸名士 | [8,11] main | not applicable | collective_reference → collective_reference | exact | plausible |
| 01-dexing-028 / 兒 | [2,3] liu-annotation-006 | blocked | — | unclear | transport-blocked |
| 19-xianyuan-026 / 謝家 | [16,18] main | not applicable | collective_reference → collective_reference | exact | plausible |
| 05-fangzheng-055 / 桓子野 | [3,6] main | resolved candidate | addressee → addressee | exact | plausible |
| 06-yaliang-033 / 祖端 | [15,17] liu-annotation-002 | resolved candidate | genealogy_reference → genealogy_reference | exact | plausible |
| 01-dexing-014 / 祥 | [1,2] main | resolved | participant → participant | partially drifted | plausible; explanation audit |
| 02-yanyu-066 / 卿 | [17,18] main | resolved | addressee → addressee | exact | plausible |
| 24-jianao-001 / 何曽 | [14,16] liu-annotation-002 | resolved candidate | participant → participant | exact | plausible |
| 01-dexing-023 / 湘州刺史 | [16,20] liu-annotation-001 | resolved office context | person_attribute → person_attribute | exact | applicability candidate |
| 07-shijian-019 / 爰 | [25,26] liu-annotation-003 | resolved candidate | reference → participant | exact | plausible; boundary override |
| 08-shangyu-020 / 陸機 | [3,5] liu-annotation-010 | resolved | reference → reference | exact | plausible |
| 04-wenxue-097 / 宏 | [1,2] liu-annotation-003 | resolved | participant → participant | exact | plausible |
| 36-chouxi-003 / 王敦 | [13,15] liu-annotation-001 | resolved | reference → reference | exact | plausible |
| 04-wenxue-023 / 羣臣 | [38,40] liu-annotation-002 | not applicable | collective_reference → collective_reference | exact | plausible |
| 11-jiewu-003 / 楊 | [41,42] liu-annotation-004 | resolved candidate | reference → reference | exact | plausible |
| 14-rongzhi-005 / 康 | [10,11] liu-annotation-001 | target ambiguous | reference → reference | wrong occurrence | insufficient evidence |
| 10-guizhen-012 / 大將軍 | [8,11] main | resolved | participant → participant | exact | plausible |
| 05-fangzheng-055 / 王蒙 | [19,21] liu-annotation-002 | resolved | reference → reference | exact | plausible |
| 05-fangzheng-007 / 司徒第二子 | [15,20] liu-annotation-005 | resolved candidate | genealogy_reference → genealogy_reference | exact | plausible |
| 34-pilou-006 / 父融 | [25,27] liu-annotation-002 | resolved candidate | genealogy_reference → genealogy_reference | exact | plausible |
| 08-shangyu-020 / 周俊 | [3,5] liu-annotation-001 | resolved candidate | citation_source → citation_source | exact | plausible |
| 05-fangzheng-027 / 江南 | [1,3] liu-annotation-003 | not applicable | reference → reference | exact | applicability candidate |
| 09-pinzao-063 / 吾 | [8,9] main | frozen context reused | speaker → speaker | exact | plausible |

Counts: 30 occurrences; 22 plausible; 3 semantic-correction candidates; 2
identity-applicability/projection review classes, with two additional office
route discrepancies recorded in the applicability audit; 1
insufficient-evidence target; 3 transport-blocked. There are 12
occurrence-level candidate historical Person proposals in 11 structured entity
groups. No row authorizes a canonical write, Gold promotion, or F2 execution.

## Review order

1. Resolve target/semantic/applicability candidates (`子野`, `堯`, `剌史`,
   `湘州刺史`, `康`, `江南`).
2. Inspect the three blocked identity units and authorize any future bounded
   replay separately if recovery is desired.
3. Review candidate Person groups at entity level while preserving every
   occurrence link.
4. Decide whether the inactive review-policy-v2 proposal is acceptable; do not
   edit the frozen F-prep policy in this stage.
