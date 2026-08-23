# HNG1R2：全量离线身份重放与审计修复

HNG1R2 是 HNG1 的离线派生层。它不重新检索，不调用 DeepSeek，也不修改 HNG1、HNG1R、规范人物或历史事实。HNG1 的原始抽取继续作为不可变的评估证据。

## 修复范围

HNG1 曾以 `hng0_1_common.build_people_catalog()` 生成一种人物目录结构，却把它传给期望 HNG0.2 目录结构的身份解析器。结果是王敦、王導、桓温、郗鑒、王戎、劉伶、蘇峻等已登记人物的完整姓名仍被拆成 HNG 临时人物。

HNG1R2 对全部 103 个身份出现重新执行同一套目录与解析接口：

1. `build_hng0_2.person_catalog()`；
2. `build_hng0_2.forms_index()`；
3. `build_hng0_2.resolution_for_candidate()`；
4. HNG1R 已冻结的 `contextual_short_name` 上下文评分。

解析顺序覆盖准确名、别名、字、称号、装饰名后缀、亲属语境、传记局部语境和上下文短名。所有判断只使用 HNG1 已保存的逐字引文及其所在本地来源窗口。

## 亲属姓氏保护

单字人名处在明确亲属表达中时，当前家族或传记姓氏优先于一般后缀匹配。例如：

```text
卞壼（從父兄敦）
```

这里先尝试“卞敦”。若项目人物目录没有唯一对应者，结果保持为 HNG 临时人物或未决身份，不能因为“敦”是“王敦”的末字而绑定王敦。规则按亲属结构和局部姓氏工作，没有人物专用映射。

“兄”“父母”“客”“帝”“太子”等一般角色表面仍然关闭解析，除非来源局部结构另有独立、明确的身份支持。

## 证据与审计

审计展示：

- 来源中的准确短引文；
- 围绕该短引文截取的本地解析上下文；
- 来源单元或传记标题；
- 抽取表面、解析方法、候选集合与上下文信号。

审计不使用无关的 `model_snippet` 作为主展示段落。人工决定支持：

```text
correct
false_merge
false_split
uncertain
not_reviewed
```

所有决定只写入 `data/annotation/hng1r2-review.json`，不回写规范数据。HNG2 准备报告始终等待有意义的人工审计，不自动批准扩图。

## 产物与运行

```bash
python3 scripts/build_hng1r2.py
python3 scripts/validate_hng1r2.py --mode portable
python3 scripts/validate_hng1r2.py --mode full
python3 -m unittest tests.test_hng1r2
```

派生产物位于 `data/generated/hng1r2/`。构建清单锁定 HNG1 与 HNG1R 的整棵文件哈希，并记录模型/API 调用数为零。

HNG1R2 仍是候选研究基础设施。身份修复和关系重投影不会自动建立 Person、Relation、Fact 或任何规范历史事实。
