# R3C：当前范围显式人物关系覆盖审计

R3C 是关系覆盖审计，不是关系扩张器。它扫描当前 50 位生产人物、83 则已发布 Story 的正文/Liu 注，以及当前 Evidence 中已处理的《晋书》材料；新发现只进入候选层，不进入生产 Relation。

## 范围与原则

- 生产人物：**50**；已发布 Story：**83**；无序人物对：**1225**。
- Evidence：Shishuo **649**；Jinshu **50**。
- 覆盖目标：解释每个高信号显式关系是已审阅、已暂缓、新候选、仅场景、不足或身份受阻；不是降低关系孤立人数。
- 硬规则：Scene ≠ Relation；共现、同席、一次褒贬、一次争论、官位高低都不能单独生成 Relation。

## 审计摘要

- 有关系语义 Evidence 的人物对：**7**。
- 当前已审阅 Relation：**12**；R3B 暂缓候选：**2**。
- 已审阅再发现：**12**；R3B 暂缓再发现：**2**。
- 新候选：**5**；仅场景：**27**；不足以建立关系：**3**；身份受阻：**7**；重复证据：**5**。
- 按已审阅 Relation 计算的孤立人物：**38**（描述性指标，不是质量目标）。

## Relation family hits

- institutional: **13** explicit pattern hits
- kinship: **1** explicit pattern hits
- marriage: **0** explicit pattern hits
- political: **0** explicit pattern hits
- social: **4** explicit pattern hits

- 本轮无需扩展 production Relation ontology；5 个新候选均可用现有 `institutional/service_under` 语义表达。
- 有 **7** 组证据因身份不确定而阻断；未将其强行连接到 Relation 端点。
- 未新增 H0/Clan/HistoricalEvent schema 或提示；可复用的事件、亲属、任职线索仍只留在当前 Evidence/审计范围内。

## R3C 新候选

### 王導 × 王濛

- Candidate ID：`r3c-candidate-1cd6d209f85057f58cea`；`institutional/service_under`；范围：`institutional_tenure`。
- 角色：任用者 — 被任用者。
- 来源：04-wenxue-022。Evidence：evidence-p3b-wave-1-b1b2ae83596c659a68e481bc, evidence-sc1-04-wenxue-022-annotation-004。
- 依据：局部語境以「王導」為任用側、以「王濛」為任職側。
- 证据摘录：(爲王導所辟王濛王述並)
- 风险：single_source_only。review_status 保持 `candidate`，没有 production_relation_id。

### 謝安 × 袁宏

- Candidate ID：`r3c-candidate-245a20d48e8f03f2875e`；`institutional/service_under`；范围：`institutional_tenure`。
- 角色：任用者 — 被任用者。
- 来源：02-yanyu-083。Evidence：evidence-p3b-wave-1-0327b51ec398e5307054694c, evidence-sc1-02-yanyu-083-main。
- 依据：「袁彦伯」與「謝安」之間有明示任職語式。
- 证据摘录：袁彦伯為謝安南司馬都下諸人送至瀨鄉 將别既自悽惘歎曰江山遼落居然有萬里之勢
- 风险：same_pair_has_r3a_candidate, single_source_only。review_status 保持 `candidate`，没有 production_relation_id。

### 王敦 × 謝鯤

- Candidate ID：`r3c-candidate-5b7008158d98f3b15760`；`institutional/service_under`；范围：`institutional_tenure`。
- 角色：任用者 — 被任用者。
- 来源：08-shangyu-051。Evidence：evidence-p3b-wave-1-b8b77718c95340aeb4e4c985, evidence-p3b-wave-2-f2ad7c9413c68b73825930c7, evidence-sc1-08-shangyu-051-main。
- 依据：局部語境以「王敦」為任用側、以「謝鯤」為任職側。
- 证据摘录：王敦爲大將軍鎭豫章衛玠避亂從洛投敦相見欣 然談話彌日于時謝鯤爲長史敦謂鯤曰不意永嘉 之中復聞正始之音阿平若在當復絶倒
- 风险：contextual_service_antecedent, single_source_only。review_status 保持 `candidate`，没有 production_relation_id。

### 王敦 × 何充

- Candidate ID：`r3c-candidate-8c03719e440ca6d4785d`；`institutional/service_under`；范围：`institutional_tenure`。
- 角色：任用者 — 被任用者。
- 来源：05-fangzheng-028。Evidence：evidence-p3b-wave-1-daa050b183b31ea5f9dfcbb9, evidence-p3b-wave-2-c8feff6575d843284166c5ea, evidence-sc1-05-fangzheng-028-main。
- 依据：局部語境以「王敦」為任用側、以「何充」為任職側。
- 证据摘录：王含作廬江郡貪濁狼籍王敦護其兄故於衆坐稱 家兄在郡定佳廬江人士咸稱之時何充爲敦主簿 在坐正色曰充即廬江人所聞異於此敦黙然旁人 爲之反側充晏然神意自若
- 风险：contextual_service_antecedent, single_source_only。review_status 保持 `candidate`，没有 production_relation_id。

### 王敦 × 温嶠

- Candidate ID：`r3c-candidate-cd3e7464596e0bf3b87f`；`institutional/service_under`；范围：`institutional_tenure`。
- 角色：任用者 — 被任用者。
- 来源：05-fangzheng-032。Evidence：evidence-p3b-wave-1-10d21ab22043839596b50a7e, evidence-p3b-wave-1-18462fb890be704f2c6ab941, evidence-sc1-05-fangzheng-032-main。
- 依据：局部語境以「王敦」為任用側、以「温太真」為任職側。
- 证据摘录：王敦既下住船石頭欲有廢明帝意賔客盈坐敦知 帝聦明欲以不孝廢之每言帝不孝之狀而皆云温 太真所説温嘗爲東宫率後爲吾司馬甚悉之須臾 温來敦便奮其威容問温曰皇太子作人何似温曰 小人無以測君子敦聲色並厲欲以威力使從巳乃 重問温太子何以稱佳温曰鈎深致逺葢非淺識所 測然以禮侍親可
- 风险：contextual_service_antecedent, single_source_only。review_status 保持 `candidate`，没有 production_relation_id。

## 关键负回归

- `05-fangzheng-031` 的伯仁与处仲政治争论只标为 `scene_only`，不生成周顗—王敦 Relation。
- 谢安 × 袁宏的赏识候选与王导 × 温峤的场景交流继续保留 R3B `deferred` 决定。
- 苏峻 × 庾亮、苏峻 × 温峤仍由既有 R3B 事件限定 Relation 覆盖，不重复生成。

## 后续边界

新候选需要后续人工审阅后才可进入 R3D/R3B 类物化流程。R3C 完成后进入 SGZ0 前的关系覆盖复核，不启动 Sanguozhi、Clan、HistoricalEvent 或其他扩张。
