# HNG0：历史导航图 Pilot

HNG0 是面向研究与人工核验的一跳人物导航投影。它把现有的 PersonStory、已经复核的关系材料，以及 H0C 中已有的职任、事件、地点和故事时代定位，整理为一个可追溯的候选层；它不是新的历史事实库。

## 范围与选择

`scripts/build_hng0.py` 根据 Story 覆盖、既有关系度、证据密度和晋书入口数计算确定性选择分数，从当前 Person registry 中选出 24 名人物，并保留高、中、低连接度分层。每个关系行至少有一条现有 evidence ref，且至少有一个端点是种子人物；不会递归扩展邻居。仅有故事共现、同姓或同一时期任官不会生成关系。`same_clan` 只使用已有显式族属记录。

## 数据层

候选数据位于 `data/generated/hng0/hng0-candidates.json`，包括：

- 人物身份提示、别名、字、职官称谓、已有族属与本地来源引用；
- `relations` 一跳关系候选；
- `temporal_items` 最小时间脊；
- 每条来源引用的原文（若当前证据登记已有原文）或明确的来源记录定位。

时间脊区分 `exact`、`circa`、`before`、`after`、`between`、`reign_period` 与 `unknown`。没有精确年代时不会补造年份。现有来源的 `review_status` 被保留在 `source_review_status`，HNG0 自身的 `review_status` 由评审覆盖层管理。

`data/annotation/hng0-review.json` 是独立的评审 overlay，`hng0-reviewed-projection.json` 是确定性合并投影。二者都带有 `canonical_write_back: false`；评审不会修改 Person、Relation、Fact、Event、Gold 或 SRM 数据。

## 证据与来源边界

构建器只读取仓库已有的世说、刘注、晋书及 H0C/已有复核投影。原始来源文本和规范化搜索文本在证据记录中分开保存；规范化只用于检索/显示，不改写引用内部字符。缺少直接原文的既有派生引用会标记为 `source_record_reference`，不会被伪造为引文。

## 前端评审

`site/src/generated/hng0-site.json` 是静态前端投影。人物面板中的 HNG0 区域提供 Relations、Timeline、Stories 和 Evidence：关系节点只显示一跳邻居，时间条目保留精确/近似区别，点击关系或时间条目可展开证据。Accept、Reject、Uncertain、Needs more evidence 只写入浏览器的 `localStorage`（`shishuoSketch.hng0-review`），不写回 canonical 数据。

HNG0 是 evidence infrastructure。它为后续图引导研究检索和人物页面核验提供入口，但不自动生成历史事实，也不接入 SRM 检索。
