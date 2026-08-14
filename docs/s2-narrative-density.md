# S2.2：叙事密度精选

S2.2 不增加 Story；它从现有 60 则发布故事中冻结 20 则高价值入口，集中补强 `舞台`、`入画`、`画外`、`底色` 和有证据的 `余韵`。精选文件是 `data/annotation/s2-narrative-density-selection.json`，不是新的出版清单。

## 选择原则

排序使用固定的场景价值、刘注解释价值、政治/制度/家族背景、多人互动和命运回声维度。`06-yaliang-017`、`05-fangzheng-031`、`02-yanyu-036` 为强制回归入口；其余按同一套可审计维度排序。任何共现都只用于阅读连接，不会生成 Relation。

精选的 20 则为：

`06-yaliang-017`、`05-fangzheng-031`、`02-yanyu-036`、`06-yaliang-029`、`11-jiewu-005`、`27-jiajue-008`、`05-fangzheng-032`、`06-yaliang-027`、`05-fangzheng-023`、`02-yanyu-083`、`04-wenxue-036`、`19-xianyuan-026`、`08-shangyu-051`、`08-shangyu-077`、`09-pinzao-017`、`05-fangzheng-028`、`05-fangzheng-055`、`02-yanyu-035`、`02-yanyu-069`、`05-fangzheng-025`。

## 密度层

- `舞台` 只写当前动作、对话与张力；`05-fangzheng-031` 中伯仁的政治批评在这里，不把处仲或王平子列为在场者。
- `入画` 来自 Scene Context 的明确 `present` 判断；被讨论或仅作为背景出现的人物留在 `画外`。
- `画外` 只保留真正改变本则理解的人物或事件，不是相关人物列表。
- `底色` 延续现有正文、刘注与《晋书》证据，不写完整人物传记。
- 20 则精选均有一条证据-backed `舞台`；其中 10 则 Scene Context 带有实质性 `余韵`，其余只在证据足够时保留空层。

## 一瞥

新增 `data/annotation/s2-person-life-glimpses.json` 覆盖 10 位生产 Person。每位最多四条 overlay 坐标，所有点均保留 Evidence、Story 回链和 `review_status=candidate`；它们是帮助读者定位故事的少量坐标，不是百科式生平。

## 不确定性

无法由当前项目 Evidence 支持的年龄、地点、动机、心理与后续细节保持未知或不写。S2.2 不改变 60 Story 出版清单、canonical source、Mention anchor 或 reviewed Relation 事实。
