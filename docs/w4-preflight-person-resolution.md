# W4 前置：称谓与人名解析缺口审计

W4 会增加新的故事和人物表面。开始扩展前，先对当前 83 则已发布故事的
称谓、人名和故事内短称做一次可复核的缺口审计。审计结果保存在
`data/derived/w4-preflight-person-resolution-gap-audit.json`，由
`scripts/build_w4_preflight_person_resolution_gap_audit.py` 从当前生产人物、
ER1 有效解析层和本地《世说》源段确定性生成。

这份报告不是新的解析器，也不把候选自动提升为生产 Mention。它只记录：

- `safe_story_local`：已有有效 Mention 或已提交的 ER1.1 故事内 span/coreference
  决定；
- `ambiguous`：共享称谓、泛称或现有候选仍需故事语境；
- `non_production_identity`：源文身份有依据，但目前只能落到非生产身份候选；
- `lexical_non_identity`：表面同时是普通词语，不能由全局别名直接解析；
- `unresolved`：发现了像人名/称谓的表面，但当前证据不足。

全局原则仍是：字符串匹配不是身份事实，生产人物状态也不是身份证据。
姓氏加官称、单独的 `太尉`、单独的 `公` 和同名/共享字，必须经过故事内
上下文；不能建立诸如“太尉 = 庾亮”或“公 = 庾亮”的全局别名。审计中的
`candidate_targets` 是待检查的证据方向，不是导航边。

## 14-rongzhi-024 修正

本则开头 `庾太尉` 的源段为 main text offset `0–3`。ER1.1 span decision
将它限定为本故事内的 `person-010`（庾亮），并以同一决定把后文 `庾公`
作为故事内承接；刘注中的 `孫綽庾亮碑文曰` 提供独立身份依据。已有的
`元規`、`殷浩`、`王逸少`、`右軍` 保持原有解析。

`王胡之` 在当前生产人物登记中没有安全导航目标，审计保留为
`unresolved`，不为此分配新 Person。两处 `丞相` 仍是需要上下文的泛官称，
不会因王导已有生产身份而自动变成 Person Mention。

修正后 `person-010 ↔ 14-rongzhi-024` 仍只有一条 PersonStory 边；构建层
没有通过新 span 复制已有的语义链接。

## 审计边界与 W4 闸门

审计覆盖当前发布集合的全部 83 则故事，检查 main text 和刘注中由现有
称谓/字/短称登记、姓氏加官称形态以及少量已确认高信号表面产生的记录。
没有改写 canonical source、Person 注册表、Story 集合或 Relation。

安全缺口已修复后，剩余含糊项会作为 W4 的输入保留；含糊项本身不是扩展
阻塞条件。W4 新增数据应继续复用 ER1 的故事内决定和“最长安全语义 span”
规则，而不是把本报告变成全局称谓字典。
