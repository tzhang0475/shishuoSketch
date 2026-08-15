# H0A.1 时间缺口缩减

## 目标与边界

H0A.1 复用 H0A 的 HistoricalPhase、ReignPeriod、EraYear、TemporalEvidence、PersonActivityAnchor 与 StoryTemporalAnchor；它只审查当前生产 Story 中原本为 unknown 的记录，不建立第二套时间系统，也不下载新史料。

核心原则是区分“本地证据尚未建模”与“现存证据确实不能定年”。人物有已知生卒年、同篇相邻、或一般文化常识，都不能单独把一则《世说》故事提升为具体年份。

## 规则

1. 正文直接点出的年号年可成为 exact_year；正文明确的年号／君主只给出 reign_bounded。
2. 直接故事事件（例如孙恩贼出吴郡、王敦大将军下至石头、来过江）才可成为 event_bounded；刘注后续命运不回推故事时间。
3. “正始之音”等文学比较归为 quoted_ancient_precedent，不约束故事时间。
4. 多个真正适用于故事当下的区间才允许求交；矛盾约束保留冲突并降级，不静默选源。
5. 仲容、少孤、桓子野、周侯周侯、文度等身份修复先于时间抽取；生产 Person 状态不增加历史身份可信度。

## 本次结果

- H0A 基线 unknown：54
- 升级数量：10
- 升级后仍 unknown：101
- 剩余 unknown 分类：{"genuine_unknown": 36, "source_conflict": 0, "identity_blocked": 17, "evidence_too_broad": 22, "local_source_search_gap": 26}

升级记录：

- 01-dexing-017：unknown → reign_bounded（explicit_story_local_ruler_reference）
- 01-dexing-045：unknown → event_bounded（explicit_story_event_context）
- 02-yanyu-036：unknown → event_bounded（explicit_story_event_context）
- 05-fangzheng-023：unknown → reign_bounded（explicit_story_local_ruler_reference）
- 09-pinzao-006：unknown → reign_bounded（explicit_story_local_reign_reference）
- 09-pinzao-014：unknown → reign_bounded（explicit_story_local_ruler_reference）
- 09-pinzao-017：unknown → reign_bounded（explicit_story_local_ruler_reference）
- 09-pinzao-022：unknown → reign_bounded（explicit_story_local_ruler_reference）
- 10-guizhen-012：unknown → event_bounded（explicit_story_event_context）
- 33-youhui-007：unknown → reign_bounded（explicit_story_local_ruler_reference）

## 重点回归

- 05-fangzheng-031 仍以王敦之乱的事件范围表达舞台语境，不从政治冲突生成 Relation。
- 06-yaliang-017 中庾会咸和六年遇害是 later_outcome，不能把童年场景定在咸和六年。
- 23-rendan-013 的仲容保持阮咸，不给石苞添加活动或时间证据。
- 01-dexing-026 的少孤仍是普通叙事词。

## 未解决缺口

genuine_unknown、evidence_too_broad 与 identity_blocked 都是合法结果。local_source_search_gap 只表示本地已有官称／君主表面，未来仍可能通过当前已获取的材料改善；本阶段不以补齐数量为目标。

H0A.1 停在时间证据与缺口审计；不开始 H0B、OfficeTenure、Clan、P4、ES0 或时间线 UI。
