# ER1.1 + S2.1 阅读升级

本阶段只扩展构建时的称谓跨度、故事内短称承接与已有 Scene Card 的叙事显示；不增加 Person、Story 或 Relation。

## ER1.1

- canonical Mention 的 `anchor` 保持不变；`display_span` 是独立的、可审计的最大语义人物跨度。
- 只有身份资料中已有同一人物的完整称谓时，才会合并姓氏与字、官称等相邻字符。
- 故事内短称只在同一 Story/section 已有唯一兼容前件时承接；不会成为全局 Alias。
- 06-yaliang-017 的 `庾太尉` 与后文两个 `亮` 指向庾亮；`温太真` 作为一个完整跨度指向温嶠，嵌套的 `太真` 不再单独显示。
- `person-resolution-span-audit.json` 保留发布故事中自动修复的跨度及其证据；canonical Mention 文件没有被改写。

## S2.1 词汇层

Scene Card 的 reader-facing 分层为：

1. `入畫 / 入画`：这一刻真正进入叙事画面的行动与人物；
2. `畫外 / 画外`：不作为当下在场者、但从画外影响本则的人物或背景；
3. `底色`：理解场景所需的制度、政治、家族与历史背景；
4. `餘韻 / 余韵`：由本则结尾或刘注/Jinshu 证据延伸出的短小回声。

空层不显示。所有 claims 保留 `assertion_status`、`review_status` 与 Evidence IDs；这些层不生成 Relation。

## 06-yaliang-017

该则的 Scene Context 保留庾會（阿恭）为“在场但尚未建立人物卡”的不可导航人物。刘注补出的庾會、字会宗、小字阿恭，以及十九岁、咸和六年遇害，分别进入 `底色` 与 `余韵`。最后关于“论者谓不减亮”与“苏峻时遇害”的并置明确标为 `inferred`，没有补写死亡方式或人物心理。

## 一瞥

Person Sketch 的新增阅读层使用 `一瞥`，只承载少量、证据-backed 的生平坐标，并保持 candidate review status。当前以庾亮与温嶠的 06-yaliang-017 相关材料作为首批示例；它不替代故事卡、关系卡或完整传记。
