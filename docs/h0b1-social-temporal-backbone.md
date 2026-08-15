# H0B-1：Social & Temporal Backbone Scale-Up

H0B-1 把冻结的 H0B-0 试点提升为当前 production corpus 的历史上下文层。
它覆盖现有 75 位 Person、143 则 Story，但不新增 Person、Story 或 reviewed
Relation。目标是为后续的历史图一致性检查提供可审计的中间事实，而不是把
社会结构“补满”。本阶段坚持：

> quality > coverage；unknown 胜过伪造的 precision。

## H0B-0 frozen，H0B-1 consolidated

H0B-0 的 50-Person / 83-Story 选择、原子事实 ID、gap audit 和 metrics 都是
历史试点记录。H0B-1 从这些文件按原 ID 导入仍然有效的 Clan、ClanMembership、
KinshipFact、MarriageUnion、OfficeTenure，再从
`data/annotation/h0b1-fact-seeds.json` 加入少量当前 scope 内、已有本地 Evidence
支持的 candidate 事实。旧事实不会复制为新的 H0B-1 ID，H0B-0 文件也不会被
构建器改写。

合并投影是：

```text
frozen H0B-0 facts + H0B-1 candidate facts
                    ↓
        data/derived/h0b1-social-backbone.json
```

当前投影保留 7 个 Clan、11 条 ClanMembership、5 条 direct KinshipFact、2 条
MarriageUnion 和 26 条 OfficeTenure。新增的 4 个 Clan、4 条 Membership 与 9
条 OfficeTenure 都保留 `review_status: candidate`；脚本生成不等于人工复核。
本轮没有新增 Kinship 或 Marriage，避免以不足的端点证据填充指标。

## StoryParticipant 与 Mention 的分离

`PersonStory` 或有效 Mention 只说明一个身份与 Story 有联系，不等于这个人
参与了现场。`data/derived/h0b1-story-participants.json` 为全部 143 则 Story
提供一条记录，并把人物分为：

- `present`、`speaker`、`actor`：可以进入 hard social-temporal intersection；
- `referenced`：正文提及，但不自动视为在场；
- `off_frame`：Scene Context 标出的画外人物；
- `annotation_only`：仅刘注/传记层出现；
- `uncertain`：语义参与尚未足够确定。

已有 Scene Context 的 `people_at_scene` 优先；非 Scene Story 只有在主文本语义
明确时才由种子补充参与记录。Mention-only rows 仍保留证据，供身份审计使用，
但不能单独约束 Story 年代。`08-shangyu-079` 的 standalone `望之` 继续是
lexical verb-pronoun，不会通过 alias fallback 重新成为 person-029，也不会
成为该 Story 的 participant。

## OfficeTenure 与 PersonActivityAnchor

OfficeTenure 是“某 Person 在来源中以某职官出现/任职”的可复用制度事实，
不是 Person 间 Relation。相对任序仍保留为 `sequence_bounded` 或 `unknown`，
没有从“后为某官”反推绝对年份。本轮 26 条 OfficeTenure 中只有一条有事件边界，
其余保留 unknown。

H0A 的 `PersonActivityAnchor` 仍是已审核的最小时间约束。H0B-1 可以从强的
Office/Event 事实提出兼容性或扩展候选，但不会静默复制或改写 H0A。更重要的
是，OfficeTenure 只有同时满足以下条件才可能进入 hard Story constraint：

1. Story 明确激活该职官；
2. Person 是 `present` / `speaker` / `actor`；
3. OfficeTenure 有有效绝对区间；
4. 事实已达到 `review_status: reviewed`。

当前新 office facts 仍是 candidate，因此其有界信息只出现在
`candidate_office_constraints`，不会给 H0A 或 Story chronology 造出硬日期。

## Kinship、Marriage、Clan 与 Relation

四类结构事实保持原子化：

- ClanMembership 要求来源支持；姓氏、同 Story、同官不能推出 Clan；
- Kinship 优先保存有方向的 parent-child，derived kinship 必须列出已审核的
  `derived_from_kinship_ids`；
- MarriageUnion 是 canonical endpoint order 的一个 union，不复制 A→B/B→A；
- OfficeTenure 不产生同僚、上下级、友情或政治关系。

现有 12 条 reviewed Relation 不被复制或自动升级。`h0b1-relation-temporal-
contexts.json` 只是挂在既有 Relation 上的适用性 metadata：事件边界的
opposition 可被标为 scoped，friendship/appreciation 等没有可信时间边界的
Relation 则明确 `intentionally_unscoped`。同 Clan、同姓、同 Story 共现都不能
单独产生 Relation 或日期。

## Social-temporal constraint engine

`data/derived/h0b1-social-temporal-constraints.json` 覆盖全部 143 则 Story。
约束层级大致为：显式日期/年号、已审核事件、Story-activated OfficeTenure 或
事件型 Relation；其次是多个真实参与者的活动区间交集；婚姻、生命阶段、迁徙
只能在 Story 明确激活且证据足够时提供较粗边界；姓氏、Clan、泛泛友谊和刘注
人物传记不能定时。

区间相交时，输出所有输入与 supporting IDs；相交为空时保留
`temporal_conflict`，不取平均值或“最方便”的日期。`h0b1-h0a-upgrade-queue.json`
只记录候选，不改写 H0A。当前 H0A anchors 未改变，只有 2 个候选升级记录。

这明确区分三个层次：

```text
H0A StoryTemporalAnchor  = 历史断言层，证据不足可以 unknown
H0B-1 social constraint  = 研究投影，可保留候选区间与冲突
E0/E0.1 Era orientation  = 读者导航层，可给较宽的时代方向
```

因此 `H0A = unknown`、H0B-1 有一个候选宽区间、E0 仍给出 broad Era orientation
是合法且预期的状态。H0B-1 不以减少 unknown 数量为成功标准，也不强制把 Story
绑定到具体帝王。

## Gaps 与未来 readiness

`data/derived/h0b1-gap-audit.json` 把缺失端点、婚姻端点、职官年代、参与角色、
Relation 时间范围、identity compatibility、source conflict 和 temporal
conflict 作为一等研究状态。支持的 gap category 会固定出现在
`category_catalog` 与 summary，即使某一类别当前为 0；缺失的 bridge Person
只记录 secure surface、相关 production IDs、Evidence 与未来价值，不分配
`person-076`。

`h0b1-h0b0-reconciliation.json` 不修改旧 gap 文件。本轮 H0B-0 gap 的结果是
1 条 partial、6 条仍 blocked；W4 或 identity hotfix 没有凭空闭合家族、婚姻或
支系端点。`h0b1-p4-readiness.json` 与 `h0b1-es0-readiness.json` 只是规划投影，
不实现 P4、ES0、家谱 UI、Clan browser、office timeline 或 social graph。

## 产物、确定性与保护边界

主要产物包括：

- `data/annotation/h0b1-fact-seeds.json` 与五类 H0B-1 annotation projection；
- `h0b1-person-coverage-audit.json`；
- `h0b1-story-participants.json`；
- `h0b1-social-backbone.json`、`h0b1-relation-temporal-contexts.json`；
- `h0b1-social-temporal-constraints.json` 与 H0A upgrade queue；
- gap、H0B-0 reconciliation、P4/ES0 readiness 和 metrics。

构建器 `scripts/build_h0b1_social_temporal_backbone.py` 只读取仓库已有来源，
使用语义坐标生成稳定 ID，按稳定排序序列化。它不写 canonical source、Person、
Story、PersonStory、Relation、Scene 或 Era 原始层。metrics 同时记录 H0B-0
family/projection hashes、H0A anchor hash 与 seed hash，validator 会检查冻结层。

本阶段完成后的保护值为：75 Persons、143 Stories、875 PersonStory（870 reviewed）、
69 Random Person、12 reviewed Relations、44 Scene Contexts、0 orphan Mentions，
以及 143/143 primary Era orientation。后续应先审阅参与角色、OfficeTenure 的
candidate/review 边界和剩余 structural gaps，再决定是否足以进行 Historical
Graph Sufficiency Audit；H0B-1 本身不执行该审计。
