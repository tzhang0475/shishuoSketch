# H0A 历史时间骨架

H0A 将当前生产 Story 放入有证据支撑的时间分辨率中。它是时间证据与阅读定位层，不是完整年表，也不把《资治通鉴》设为自动最高权威。

## 坐标层

- 产品阶段沿用 W3/C0 的五个稳定 ID；本次保留 5 个阶段定义。
- 从 ZTJ0 实际纪年标题构建 42 个 ReignPeriod、71 个 EraYear。
- 年号年可在证据确定时归一化为公元年；不做日级传统历法换算。

## 证据与事件

当前 83 则 Story 均有一个 StoryTemporalAnchor；生成 5 个当前范围确实需要的 HistoricalEvent：王敦之亂, 蘇峻之亂, 永嘉之亂與南渡, 八王之亂, 孫恩之亂。事件记录保留 Story/Liu 的表面和来源层，不把事件共现转为人物 Relation。

## 重点回归

- `05-fangzheng-031`：王敦举兵相关证据是事件范围证据；伯仁的政治批评仍是本则舞台语境，不生成周顗—王敦 Relation。
- `06-yaliang-017`：刘注的“咸和六年遇害”记录为 `later_outcome`，不把庾会后来的命运误定为童年场景年份。
- `05-fangzheng-055`：桓子野／桓伊的身份修复不被时间抽取改写。
- `01-dexing-026`：“少孤”仍是普通叙事词，不恢复孟陋的错误 Mention。
- W3 的曹魏、竹林—西晋初、西晋后期样本沿用冻结阶段定位，没有虚构精确年份。

## 前端

Story 头部只显示有意义的自然中文时间定位；unknown 不显示“未详”、unknown 或内部 precision。若已有 W3 阶段，H0A 的 temporal orientation 取代旧的独立时间系统，避免重复标签。

## 边界

H0A 不创建 Clan、OfficeTenure、HistoricalCircle、Timeline UI 或完整 HistoricalEvent 图。后续 H0B/P4/ES0 必须先审阅本层的 unknown 与冲突。

## 当前分布

精度分布：`{"exact_date": 0, "exact_year": 0, "year_range": 0, "event_bounded": 10, "reign_bounded": 7, "phase_only": 22, "unknown": 44}`。前端有定位标签的 Story：39。

## H0A.1 缺口缩减

H0A.1 从已完成 H0A 的基线继续工作：基线 unknown 为 54，本次以故事正文中明确君主／年号、直接事件和南渡语境为优先，不以人物生卒年单独推定故事年份。本次升级 10 则，仍 unknown 44 则；每一项升级都保留 TemporalEvidence 与 resolution_basis。

04-wenxue-022 的“正始之音”保留为 quoted_ancient_precedent，不误作故事发生年代；06-yaliang-017 的“咸和六年遇害”仍是 later_outcome。
