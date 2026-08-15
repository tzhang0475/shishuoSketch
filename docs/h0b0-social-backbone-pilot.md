# H0B-0：Social Backbone Pilot

H0B-0 是当前 50 位 production Person、83 则 production Story 上的数据模型
试点。它不扩展人物或故事，也不把现有 Relation graph 改造成一个“万能社会
网络”。

本阶段的基本原则是：

> 先保存可审计的原子事实，再由后续产品层派生导航关系。

## 四类原子对象

### Clan 与 ClanMembership

Clan 是有来源支持的族属/地域层级，ClanMembership 把当前 production Person
连到 Clan。姓氏本身不是族属证据；同姓人物不会因为共现、同官或同一故事自动
合并。Pilot 只保存了三条保守的族属范围：

- 琅邪王氏；
- 陈郡谢氏；
- 太原温氏。

这些记录的 branch 精度保持在来源实际支持的层级。没有证据的支系不被补写。
族属归属本身也不创建 reviewed Relation。

### KinshipFact

Kinship 先以最小的原子谱系事实保存，优先使用有明确方向的 parent_child，
并保留直接来源中的角色。叔侄、从伯/从子等直接文字也可以作为原子事实，但
不会从姓氏或同场共现推导亲属。

本 Pilot 的五条 direct KinshipFact 包括王羲之—王凝之父子、郗鉴—郗璿父女、
谢安—谢道韫叔侄、谢鲲—谢尚父子，以及王导—王羲之的从亲事实。新记录仍为
candidate；既有 R1 reviewed Relation 只在兼容性表中被引用。

只有将来已有 reviewed 原子事实构成确定路径时，才可生成 derived kinship；
本 Pilot 没有为填充数量而添加派生亲属。

### MarriageUnion

婚姻是一个 canonical endpoint order 的 union，而不是两个独立的正反向边。
Pilot 保存王羲之—郗璿、王凝之—谢道韫两条直接婚姻事实，婚年未知就保持
null 与 temporal_status: unknown。婚姻不自动推出两族联盟、政治合作或情感
判断。

### OfficeTenure

OfficeTenure 是“某人曾以某职衔出现/任职”的制度事实，不是人物之间的
Relation。Pilot 只保存当前结构试点所需的 17 个职官片段，例如丞相、太尉、
大司马、记室参军、吏部尚书、步兵校尉。职衔文字足以支持标题事实时，仍不足
以假造任期；因此这些记录保留 temporal_precision: unknown，不重建完整官历。

现有 service_under Relation 仍由 Relation 层负责。以桓温—袁宏为例，袁宏的
“大司马记室参军”作为 OfficeTenure 与该 Relation 兼容，但不是一条重复的
Office→Person 边。OfficeTenure 也不自动生成同僚、上下级、友谊或政治联盟。

## 试点选择与证据

data/annotation/h0b0-pilot-selection.json 冻结了 20 位现有 production Person。
选择覆盖王氏婚姻/亲属核心、谢氏父子与婚姻结构、东晋府僚，以及魏晋早期的
制度位置。选择 audit 会列出 50 位人物的 Story 数、Relation degree、原子
事实信号与桥接缺口；分数只是可解释性指标，不是历史重要性，也不在构建时
重新选人。

事实种子位于 data/annotation/h0b0-fact-seeds.json，构建器将其与
data/evidence/wp1-evidence.json 的定位、来源文件哈希和 source/unit 坐标装配为：

- data/annotation/clans-h0b0.json
- data/annotation/clan-memberships-h0b0.json
- data/annotation/kinship-h0b0.json
- data/annotation/marriages-h0b0.json
- data/annotation/office-tenures-h0b0.json

所有新增事实默认是 candidate，脚本生成不等于人工复核。

## 与 Relation、H0A、E0 的边界

现有 12 条 reviewed Relation 不被重写。兼容性审计
data/derived/h0b0-social-backbone.json 逐条标记：

- 可由 H0B 原子事实支持的既有边；
- 结构上更丰富、但不等价的 Relation；
- 仍只属于 friendship / political / institutional Relation 层的事实；
- 潜在语义冲突。

H0B 的 OfficeTenure 可在未来为 H0A 的 PersonActivityAnchor 提供可复用证据，
但本阶段不自动改写故事年代。H0B 也不改变 E0/E0.1 的纪元卡或故事方向。
Clan、婚姻和亲属事实不会自动成为历史事件、时代卡或人物 Relation。

## 当前 scope 的结构缺口

data/derived/h0b0-structural-gap-audit.json 明确保留当前 50 人注册表无法闭合的
端点，例如：

- 阮籍—阮咸；
- 庾亮—庾会及其婚姻端点；
- 桓温之女—王坦之之子的婚姻端点；
- 桓温府僚的可排序职官时序；
- 温嶠“太原祁人”之外尚未有的支系精度。

这些是 missing_bridge_identity、marriage_spouse_not_production、
office_chronology_incomplete、clan_branch_unresolved 等 audit 状态，不是
本阶段偷偷补建的人物。

data/derived/h0b0-w4-readiness.json 是非生产规划输出。它只建议未来哪些桥接
人物或故事最有结构价值，明确禁止分配 Person ID、发布 Story 或直接改变当前
导航。

## 运行与不变式

    python3 scripts/build_h0b0_social_backbone.py
    python3 scripts/validate_h0b0.py

构建是确定性的，稳定 ID 来自冻结的 annotation seed，而不是姓名、族名、职衔
或数组位置。校验要求：

- 原子事实所有端点都在当前 production/Pilot；
- 每条 direct fact 有 Evidence；
- 婚姻端点 canonical 且无 A-B/B-A 重复；
- 未知办公室时间不带伪造 bounds；
- 现有 12 条 Relation 全部被审计且数量不变；
- 50 Persons、83 Stories、704 PersonStory、45 Random Person、44 Scene
  Context、83/83 Era orientation、0 orphan Mentions 不变；
- 身份修复（仲容、少孤、桓子野、周侯）不会被结构层重新投影。

H0B-0 不实现 W4、P4、ES0、家谱 UI、办公室时间线或社会图谱。下一阶段的产品
决策应先审阅事实语义、缺失桥接身份和证据精度。
