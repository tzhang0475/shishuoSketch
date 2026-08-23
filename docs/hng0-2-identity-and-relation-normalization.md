# HNG0.2：标点优先检索、身份解析与关系规范化

HNG0.2 是 HNG0.1 候选层的离线、确定性研究投影。它不调用模型，不新增
Person，也不向 canonical Person、Relation、Fact 或 Gold 写回。

## 输入与来源

固定使用 HNG0 的 24 位 seed Persons，以及 HNG0.1 已生成的 160 条关系候选、
83 条时间候选和其证据注册表。HNG0.1 原始响应与生成物视为只读输入。

检索比较优先读取 WREF1 锁定的标点参考 witness：

- `jinshu-wikisource-punctuated`：130 卷《晉書》；
- `zizhi-tongjian-wikisource-hu`：294 卷《資治通鑑》及胡三省音注。

Wikisource 原始 wikitext 只作查找、定位和窗口比较，不替换既有主 witness。
没有安全的标点边界时回退到既有本地文本。标点优先的比较窗口以命中处附近的
结构段为基础，单段过长时限制为局部窗口；原始文本和 SHA-256 provenance 不被
改写。HNG0.2 本身不执行新的模型检索，模型调用数固定为 0。

## 身份解析

解析顺序是：上下文复合姓名、canonical/alias、传记标题局部上下文、亲属上下文、
seed 共指和标题/职官线索。每次解析都保留 surface、方法、置信度和证据引用。
例如，全局别名仍可把裸面 `士衡` 指向陆机；只有在证据上下文明确出现 `陶士衡`
时，HNG0.2 的局部上下文规则才把该表面解析为陶侃。无法确定的表面会保留为
`hng02-provisional-*` 研究节点或 unresolved 项，不会产生 canonical Person。

## 关系层级

关系保留 HNG0.1 的 `original_relation_type`，并投影为：

- `hard_relation`：亲属、婚姻、上下属、任用等明确结构关系；
- `documented_interaction`：一次有出处的政治/社会交往、共同事件等；
- `interpreted_relation`：需要较强证据的友谊、合作或对立等解释性关系。

单一争论、指责或会面不会自动升级为长期政治合作/对立。弱政治候选降为
`documented_political_interaction`，仍保留原始类型和全部证据。显式祖、孙关系
使用 `grandparent_grandchild`，不再压成 `same_clan`。

所有关系、时间条目和身份解析均是 `candidate`，前端评审写入浏览器本地 review
overlay；它不是 canonical 历史事实。

## 构建与验证

```bash
python3 scripts/build_hng0_2.py
python3 scripts/validate_hng0_2.py --mode portable
python3 scripts/validate_hng0_2.py --mode full
python3 -m unittest tests.test_hng0_2
```

`portable` 只依赖已锁定的 manifest，适用于没有 gitignored 原始下载物的干净检出；
`full` 还会逐卷核对 WREF1 本地 raw payload 的 SHA-256。输出在
`data/generated/hng0-2/`，前端只读取 `site/src/generated/hng0-2-site.json`。

HNG0.2 是证据导航和人工核验基础设施，不是历史事实发布或自动 canonicalization
阶段。
