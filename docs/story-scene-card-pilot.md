# P3B.1.1 + S1：随机人物入口与场景卡试点

## 随便认识一个人

“随便认识一个人”直接使用 SC1 build-time bundle 中的当前生产 Person、Person
Sketch 与已发布 Story 连接计算 eligible set，不建立目录页，也不创建第二套焦点状态。

当前 eligible 数量为 **13 / 17**。其余 4 人虽然有 Person Sketch，但在当前 16 则
Story 的前端投影中没有可用的 Story 人物连接，因此不进入随机入口。随机选择使用
可注入的 RNG，并排除当前 focused Person（当候选多于一人时），随后沿用现有
`explorationStack` 和 Person Explorer drawer/sidebar。

## 场景卡试点

场景卡是 Story-owned 的候选编辑层，不属于 Person Sketch，也不写入 Relation。
本轮选择 3 则：

| Story | 选择理由 |
|---|---|
| `06-yaliang-029` | 必选；正文和刘注共同保存简文帝晏驾、遗诏、桓温设宴伏甲及新亭召见等场景线索。 |
| `02-yanyu-083` | 正文有瀨乡送别，刘注补充袁宏字彦伯、仕历及谢安赏识，适合展示“出行/送别”场景。 |
| `05-fangzheng-023` | 正文与刘注保存元帝立嗣争议及王导在朝廷中的发言位置，适合展示朝廷场景。 |

没有为了凑足五则而加入证据较弱的 Story。

### `06-yaliang-029`

- 时间：`简文帝晏驾后（年月未详）`，reported，candidate；没有项目内足够年代证据，年龄全部保持未知。
- 地点：新亭，reported，candidate。
- 已物化人物：桓温、谢安，均标为本则 `present`；场景状态分别为伏甲设宴/陈兵卫，以及被召入席中。
- 尚未物化的来源人物：王坦之。其来源表述保留为场景中的“在场”人物，但不建立新的 Person 或 Mention。
- 场景位置：政治对峙场景。该描述只解释本则中的行动位置，不新增桓温—谢安 Relation。
- 背景：刘注所引《帝纪》与相关刘注材料被分为 reported claims，说明简文帝晏驾后的遗诏和桓温对谢安、王坦之的疑虑，以及新亭陈兵召见的背景。

### `02-yanyu-083`

- 时间：未详。
- 地点：瀨乡，attested，candidate。
- 袁宏标为 `present`，状态为安南司马；谢安标为 `referenced_in_context`，不把称名/职属直接改写为在场。
- 背景是袁宏出行、诸人送别，刘注补充其字与仕历，并记谢安赏识。
- 年龄没有可用的项目内年代输入，保持未知。

### `05-fangzheng-023`

- 时间：东晋元帝在位、立嗣之议时（年月未详），attested，candidate。
- 地点：未填写；没有安全的直接地点证据。
- 王导标为 `present`，状态为文中所称丞相并参与皇储议论。
- 场景位置：朝廷场景。它描述王导在本则中的位置，不复制或扩展长期 Relation。
- 背景只保留元帝立嗣争议及王导发言；刘注异文仍标为 reported。
- 年龄保持未知。

## 语义边界

`Mention` 不等于在场，`PersonStoryLink` 不等于 participant；场景卡中的
`scene_role` 是逐则、逐 claim 的候选编辑判断。`Relation` 仍只表示现有 reviewed
Person ↔ Person 事实；场景位置、同场出现和政治语境没有写入
`data/annotation/wp1-relations.json`。

## 产物与不确定性

- curated source：`data/annotation/story-scene-contexts.json`
- schema：`schema/story-scene-context.schema.json`
- derived projection：`data/derived/story-scene-contexts.json`
- SC1 bundle：`data/derived/sc1-site.json` / `site/src/generated/sc1-site.json`
- 新场景 claims、人物状态、地点和时间记录均为 `candidate`；没有自动变成 reviewed。
- 年龄推导器只在日期与出生年范围都有项目证据时计算 exact/range；当前三则均因输入不足显示未知。

## 构建与验证记录

- SC1 与场景卡重复构建字节一致：`data/derived/sc1-site.json` 与
  `site/src/generated/sc1-site.json` 的 SHA-256 为
  `a36fc22203af1ec4d728354db86a5dd01649a50af60536fc1416212748406ed0`；
  `data/derived/story-scene-contexts.json` 的 SHA-256 为
  `778c30fa67262bdaaa9941d4f753060796417756f641f6baede0c44ef10a1e68`。
- 随机人物入口的 eligible set 为 13/17；另 4 人（庾亮、王敦、温嶠、蘇峻）虽有
  Person Sketch，但当前发布前端没有可用 Story 人物连接，因此不进入该入口。
- 283 个 Python 测试在 full 与 portable provenance 模式均通过；场景/随机人物聚焦
  测试 16 个通过；TypeScript typecheck、Vite production build、production artifact
  validation、SC1 full/portable validation 与 `git diff --check` 均通过。
- 本轮只新增场景上下文投影与随机人物入口；没有启动 P3B.2、Relation expansion，
  没有修改来源文本、标点、出版选择、Person/Relation 事实或 raw payload。
