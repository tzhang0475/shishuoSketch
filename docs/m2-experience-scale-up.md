# M2A：Experience Scale-Up 审计

本报告衡量静态 Person ↔ Story 阅读路径的扩展效果。PersonStory、共享故事和 Scene 都是导航/阅读数据；它们不自动产生历史 Relation。

## Before → After

| 指标 | Before | After |
|---|---:|---:|
| 生产人物 | 17 | 50 |
| 已发布阅读故事 | 16 | 83 |
| 随机认识人物可选数 | 13 | 46 |
| PersonStory links | 330 | 709 |
| 至少一则发布故事的人物 | 33 | 46 |
| 至少三则发布故事的人物 | 19 | 28 |
| 多人物故事 | 48 | 58 |
| Scene Cards | 9 | 44 |
| 已审阅 Relation | 7 | 12 |
| 仅按 Relation 孤立的人物 | 23 | 38 |
| 共享故事人物对 | 77 | 105 |
| 没有发布故事路径的人物 | 2 | 4 |
| 没有可点击人物的故事 | 0 | 0 |
| 仅有一则且该故事无其他人物的人物 | 1 | 2 |

身份校正后，生产注册表保留 50 位 Person，但安全的“随便认识一个人” eligibility 为 46。候选身份、歧义 Mention 和错误前缀均不用于补回导航；没有安全 published Story 入口的人物仍保留在生产数据中。

ER1.1.2 的桓子／桓子野身份校正移除了 6 条原先错误归给 `person-016` 王遐的 PersonStory 链接；其中 05-fangzheng-055 等较长称谓现解析为未物化的桓伊，05-fangzheng-035 的古引文保持未解析。因此王遐仍保留在 50 人生产注册表中，但当前没有安全的 published Story 入口，也不进入 Random Person eligibility；不以错误前缀或候选身份补回路径。

## Performance guard

静态架构保留不变；以下记录 SC1 数据和 Vite JS 的增长，JS 以 gzip 后体积作为下载参考。若只运行数据构建，JS 栏会在 production artifact pass 后补齐。

| 产物 | Before | After |
|---|---:|---:|
| `data/derived/sc1-site.json` bytes | 19,898,089 | 33,265,875 |
| Vite JS bytes | 3,533,126 | 待 production artifact pass |
| Vite JS gzip bytes | 1,093,692 | 待 production artifact pass |
| JS asset count | 1 | 待 production artifact pass |

本阶段未引入 backend、runtime JSON fetch 或数据库；当前体积增长保留为后续静态 code-splitting 评估项。

## Wave 2 人物

| 顺位 | Person ID | 人物 | Candidate ID |
|---:|---|---|---|
| 1 | `person-018` | 謝尚 | `candidate-identity-079-liezhuan-001-df72bb359476` |
| 2 | `person-019` | 周顗 | `candidate-identity-069-liezhuan-004-cdd8afdd3f4a` |
| 3 | `person-020` | 王戎 | `candidate-identity-043-liezhuan-002-01e116bde4f6` |
| 4 | `person-021` | 劉琨 | `candidate-identity-062-liezhuan-001-26111f51e2e0` |
| 5 | `person-022` | 鄧攸 | `candidate-identity-090-liezhuan-011-1e0fed969fe4` |
| 6 | `person-023` | 謝鯤 | `candidate-identity-049-liezhuan-005-149410f87660` |
| 7 | `person-024` | 韓伯 | `candidate-identity-075-liezhuan-008-5a35631d586c` |
| 8 | `person-025` | 何充 | `candidate-identity-077-liezhuan-002-bf4a50599e20` |
| 9 | `person-026` | 陸機 | `candidate-identity-054-liezhuan-001-94fefefff861` |
| 10 | `person-027` | 向秀 | `candidate-identity-049-liezhuan-003-1e8de1e68064` |
| 11 | `person-028` | 殷浩 | `candidate-identity-077-liezhuan-006-d194dde2c30b` |
| 12 | `person-029` | 卞壼 | `candidate-identity-070-liezhuan-004-e1fcfab15d98` |
| 13 | `person-030` | 王恭 | `candidate-identity-084-liezhuan-001-71807a49cd63` |
| 14 | `person-031` | 朱伺 | `candidate-identity-081-liezhuan-006-d93552731f2b` |
| 15 | `person-032` | 孟陋 | `candidate-identity-094-liezhuan-016-86bd1f390c7b` |
| 16 | `person-033` | 孫恩 | `candidate-identity-100-liezhuan-010-96bcbe2d3579` |
| 17 | `person-034` | 伏滔 | `candidate-identity-092-liezhuan-014-6cf8948b83ef` |
| 18 | `person-035` | 和嶠 | `candidate-identity-045-liezhuan-003-e55f9d569cb4` |

Wave 2 只提升具备强身份证据、正文导航价值和安全投影路径的候选；未因引用作者频率而自动选择史家/注家身份。每个新 Person 的 review status 仍保留为 candidate。

## Story Expansion

- SC0 Gold Set：16 则（保持不变）。
- M2 expansion：44 则。
- 前端阅读并集：83 则。
- 章节分布：01=3, 02=4, 03=1, 04=1, 05=7, 06=1, 07=1, 08=4, 09=9, 10=1, 11=1, 14=1, 17=1, 22=1, 23=3, 25=2, 26=1, 27=1, 33=1。

新增 Story IDs：

- `01-dexing-017`
- `01-dexing-026`
- `01-dexing-045`
- `02-yanyu-035`
- `02-yanyu-036`
- `02-yanyu-079`
- `02-yanyu-086`
- `03-zhengshi-022`
- `04-wenxue-022`
- `05-fangzheng-025`
- `05-fangzheng-027`
- `05-fangzheng-028`
- `05-fangzheng-031`
- `05-fangzheng-032`
- `05-fangzheng-051`
- `05-fangzheng-058`
- `06-yaliang-017`
- `07-shijian-018`
- `08-shangyu-034`
- `08-shangyu-043`
- `08-shangyu-051`
- `08-shangyu-079`
- `09-pinzao-006`
- `09-pinzao-014`
- `09-pinzao-017`
- `09-pinzao-022`
- `09-pinzao-026`
- `09-pinzao-030`
- `09-pinzao-036`
- `09-pinzao-045`
- `09-pinzao-063`
- `10-guizhen-012`
- `11-jiewu-005`
- `14-rongzhi-024`
- `17-shangshi-008`
- `22-chongli-002`
- `23-rendan-001`
- `23-rendan-026`
- `23-rendan-038`
- `25-paidiao-015`
- `25-paidiao-060`
- `26-qingdi-002`
- `27-jiajue-008`
- `33-youhui-007`

## Navigation graph

图节点为 production Persons 与已发布 Stories，边为生成的 PersonStory/解析人物路径；不是 Relation graph。

- connected components：7；最大组件：125 nodes / 44 Persons。
- median Person Story degree：3.0；median Story Person degree：2。
- articulation Persons：person-003, person-006, person-008, person-012, person-013, person-020, person-024, person-033, person-035, person-036, person-038, person-039, person-040, person-041, person-043, person-044, person-045, person-046, person-047, person-049。
- articulation Stories：01-dexing-023, 02-yanyu-079, 02-yanyu-086, 03-zhengshi-006, 05-fangzheng-012, 06-yaliang-019, 07-shijian-005, 08-shangyu-019, 09-pinzao-008, 09-pinzao-045, 22-chongli-002, 23-rendan-001, 23-rendan-013, 25-paidiao-026, 27-jiajue-008。
- Person no published Story：person-015, person-016, person-032, person-042。

## Relation discovery boundary

- 当前生产人物：50；当前人物对：1225。
- R3A 冻结历史审计范围：35 人、595 对；已审阅 Relation：12；R3A candidate：7；Tier：{'A': 2, 'B': 3, 'C': 2}。
- 仅共现组合：30；这些组合未进入 Relation card。

## Provenance and determinism

所有 Wave、Story、Scene 和 R3A 输出均由构建时数据生成；portable/full provenance 仍按既有严格规则验证。输入产物 SHA-256：

- `data/derived/m2-person-expansion-ranking.json`：`19af87d57dbdbfb9fb71f81f2de70b2ba0e2b87711afe962b0f5eb52b3b657cf`
- `data/derived/m2-story-expansion-ranking.json`：`989e99cde1f75d8daa2fd31f9ede904d64619a44a41e99566174ac6705f79406`
- `data/annotation/person-expansion-wave-2.json`：`1a1443678502b9875c433783b3e9995ed1a41113d263f20f6319f800d28c4936`
- `data/annotation/story-expansion-wave-1.json`：`0d80f92be763ca7e765a6c0fc742910bbf7f2e2ba787efc84b52cff6524ea4af`
- `data/annotation/person-expansion-wave-3.json`：`be7c6a7d408c39bea79673be94bb1ed86b933c23edf7cfd8622c1932903a105a`
- `data/annotation/story-expansion-wave-3.json`：`41caaa834d3f5758162bf9c194ba6b9cb4b3c45b153f9fb0f6463044884541ec`
- `data/derived/sc1-site.json`：`779497663e03e42ddbf1cc3f9b379f181501a37a75f78af783587a4e1ae60a6d`
- `data/derived/story-scene-contexts.json`：`fd4aafd88cc26914d1a17b0b3338d70cf7814cdf69b9309f7d3a5053ac848645`
- `data/derived/person-relation-candidates-r3.json`：`4bee7e4f793b113ebcf49c3e798657c5b8cc9f551b7887a884b591f712f54086`

本报告继承 M2A 的冻结选择；ER1 安全解析影响已保留。W3 在此基础上增加了证据安全的早期魏晋 Person/Story 层与 SGZ0 处理层；S2.2 只加深现有 Story/Scene/Person Sketch 内容，R3B 仅物化明确批准的 Relation，P3B.2、H0、P4 与 ES0 均未启动。
