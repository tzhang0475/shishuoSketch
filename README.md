![世说Sketch](shishuoSketch.png)

# 世说Sketch

> **从一则故事，走进魏晋。**

世说Sketch不是《世说新语》知识图谱，也不是古籍AI问答系统。

它希望利用《世说新语》留下的大量人物片段，为一个个人物作“素描”，并通过许多人物、关系与故事，逐渐勾勒出一个时代的神情。

项目最初想解决的问题很简单：

> 现代读者阅读《世说新语》时，经常被人物称谓、复杂关系、时代背景和碎片化叙事挡在故事之外。

世说Sketch希望尽量拿掉这些障碍，但不过度解释。

用户最终感受到的应该仍然是《世说》，而不是数据库。

---

# 1. 核心理念

## 1.1 人物不是由履历组成，而由瞬间组成

《世说》很少完整介绍一个人的一生。

它留下的是一个个瞬间：

* 谢安临危时的从容；
* 王羲之坦腹东床；
* 王子猷雪夜访戴；
* 人物之间一句意味深长的评价；
* 宴会中的政治压力；
* 面对死亡、友情、门第和礼法时的反应。

一个人的 Sketch，应当由这些故事逐渐叠出来。

因此我们首先问：

> **《世说》让我们看见了怎样一个人？**

而不是：

> 这个人的完整生平是什么？

---

## 1.2 时代也可以被“素描”

时代不是只有：

* 年表；
* 战争；
* 制度；
* 帝王；
* 政治事件。

一个时代还存在反复出现的姿态：

* 从容；
* 任诞；
* 清谈；
* 人物品评；
* 门第意识；
* 婚姻；
* 家族；
* 友情；
* 伤逝；
* 政治恐惧；
* 对死亡的态度；
* 对自然与礼法的理解。

世说Sketch希望从故事本身出发，让这些气质逐渐显现，而不是预先给用户一套“魏晋风度”的标准答案。

---

# 2. 产品目标

最终产品应当是一部：

> **可漫游的沉浸式《世说新语》注本。**

或者：

> **Interactive Annotated Narrative Edition**

用户的基本体验不是“查询”，而是“进入”。

理想路径类似：

```text
读一则故事
    ↓
知道这些人是谁
    ↓
点进一个人物
    ↓
看到他在其他故事中的样子
    ↓
沿一条人物关系走到另一个人
    ↓
进入新的故事
    ↓
发现一组气质相似的故事
    ↓
逐渐理解一个人物
    ↓
逐渐理解一个时代
```

一个用户可能只是想看看“东床坦腹”。

半小时以后，他可能已经从：

```text
王羲之
→ 郗鉴
→ 王导
→ 王凝之
→ 谢道韫
→ 谢安
```

走进整个东晋士族社会。

这就是项目希望创造的体验。

---

# 3. 四个核心对象

前端最终尽量只向用户暴露四种对象：

## Story

《世说》中的一则故事。

它是整个系统最基本的内容原子。

## Person

一个人物在不同故事中的反复出现。

Person Page 不是传统百科，而是人物素描。

## Relation

人与人之间有证据支持的关系。

一条 Relation 不只是图上的一条线，而应当通向相关故事和史料。

## Theme / Motif

跨越人物和篇目的时代气质、场景和母题。

例如：

* 雅量；
* 任诞；
* 伤逝；
* 人物品评；
* 门第婚姻；
* 清谈；
* 政治危险。

---

# 4. 阅读体验：一则一幕

每一则首先应该被当成一个场景。

阅读界面采用逐层展开，而不是一次展示全部知识。

## Level 1 — 读故事

尽量保持原文。

只解决最直接的阅读障碍，例如：

```text
郗太傅 → 郗鉴
王丞相 → 王导
逸少   → 王羲之
```

目标：

> **让我能够继续读下去。**

---

## Level 2 — 看见这一幕

帮助读者重建场景：

* 谁在场；
* 人物是什么关系；
* 为什么会发生这件事情；
* 必要的门第、婚姻、政治和社会背景；
* 故事真正的戏剧张力在哪里。

目标：

> **让我看见当时发生了什么。**

---

## Level 3 — 追史料

进一步展开：

* 《世说新语》正文；
* 刘孝标注；
* 《晋书》；
* 《三国志》及裴注；
* 其他早期史料；
* 《世说新语笺疏》；
* 现代研究。

目标：

> **让我知道为什么可以这样理解。**

史料事实、后世考证和现代解释必须明确区分。

---

# 5. Person Sketch

Person Sketch 不应首先呈现完整生平。

例如谢安页面可以从若干代表性场景开始：

```text
海上风急
↓
众人失色，谢安吟啸自若

桓温设伏
↓
谢安从容赴会

淝水捷报
↓
看完信仍继续下棋

客去之后
↓
入户折屐齿而不觉
```

经过若干场景以后，用户自己逐渐形成：

> “我好像知道谢安是怎样一个人了。”

Person Sketch 可以逐步包含：

* 代表性故事；
* 反复出现的姿态；
* 人物言语；
* 他人评价；
* 重要关系；
* 不同人生阶段；
* 《世说》与正史之间的差异。

关键原则：

> **不要先给结论，再找故事证明结论。**

应让人物从故事中自己显形。

---

# 6. Relation 不只是 Edge

知识图谱中的：

```text
A ───── B
```

只是一个入口。

真正的 Relation 应当包含：

```text
两个人是什么关系
        ↓
这段关系如何形成
        ↓
哪些故事表现了它
        ↓
不同时期是否发生变化
        ↓
《世说》如何记录
        ↓
《晋书》等史料如何旁证
```

因此：

```text
co-occurrence ≠ historical relationship
```

两个人共同出现，只能首先产生 co-occurrence evidence。

友情、政治联盟、评价关系等必须有进一步证据。

---

# 7. Era Sketch

Era Sketch 不以传统历史年表为中心。

它从故事中寻找反复出现的：

## 场景

* 宴会；
* 清谈；
* 访友；
* 婚姻；
* 战争；
* 临终；
* 服丧；
* 饮酒；
* 人物品评。

## 姿态

* 从容；
* 狂放；
* 矜持；
* 羞耻；
* 悲伤；
* 机锋；
* 任性；
* 恐惧。

## 社会结构

* 门第；
* 家族；
* 婚姻；
* 名望；
* 官职；
* 师友；
* 政治集团。

最终才逐渐进入一些更大的问题：

> 什么是名士？

> 为什么魏晋如此重视人物风度？

> “自然”究竟是真的自然，还是一种社会表演？

> 为什么人物评价具有如此大的力量？

> 为什么死亡感在《世说》中如此强烈？

时代 Sketch 应从故事向抽象生长，而不是把预先存在的理论套在故事上。

---

# 8. Semantic Search 的角色

Semantic Search 非常重要，但不是事实判断系统。

它是：

> **发现层。**

主要帮助完成：

```text
Story → Similar Stories

Story → Motif

Motif → Stories

Motif → People

Corpus → Previously unnoticed patterns
```

例如：

> “还有哪些人在危险中仍然表现得若无其事？”

这类问题很难靠简单关键词搜索。

Semantic Search 可以寻找语义邻居，然后由人工或经过审核的数据决定它们是否真正属于同一 motif。

因此：

```text
Structured Graph
→ 主要负责“谁和谁”

Semantic Space
→ 主要负责“哪些瞬间具有相似气质”
```

两者最终在 Story 层汇合。

---

# 9. AI 的角色

项目采用：

> **AI is a build dependency, not a runtime dependency.**

AI主要用于离线数据构建：

* entity candidate；
* alias candidate；
* relation candidate；
* story metadata；
* reader difficulty；
* motif discovery；
* semantic embedding；
* semantic reranking；
* Sketch 草稿。

AI产生的内容原则上首先是：

```text
candidate
```

而不是：

```text
fact
```

统一状态：

```text
candidate
reviewed
rejected
```

重要解释经过人工审核以后才进入最终网站。

---

# 10. Runtime 尽量不依赖 AI

默认产品采用 static-first 架构：

```text
离线 GPU
    ↓
AI / Embedding / Reranker
    ↓
人工 Review
    ↓
JSON / Markdown
    ↓
Static Build
    ↓
GitHub Pages / CDN
    ↓
User
```

最终用户浏览：

* Person Sketch；
* Era Sketch；
* Story；
* Relation；
* Similar Stories；

原则上都不需要在线 LLM 调用。

这样即使访问量增长，AI inference cost 仍然可以接近零。

---

# 11. 当前数据基础

项目已经建立了较稳定的文本基础设施。

## 《世说新语》

目前已经形成：

```text
36篇
1130 canonical entries
```

并经过：

* 多 witness 校核；
* 已知数字化缺失修补；
* boundary audit；
* structural review；
* stable entry IDs；
* provenance validation。

这些 entry 是后续所有 Sketch 的故事基础。

## 《晋书》

目前采用完整四库本作为 machine primary：

```text
130卷
```

已生成结构化 historical units，可按人物和传记检索。

《晋书》的主要角色是：

* 人物身份确认；
* 生平背景；
* 家族关系；
* 官职；
* 时间；
* 《世说》故事的正史旁证。

它不需要像《世说》一样切成故事。

---

# 12. 数据管线

整体数据流：

```text
Raw Witnesses
      ↓
Normalization
      ↓
Canonical Units
      ↓
Mention
      ↓
Alias
      ↓
Person
      ↓
Evidence-backed Relation
      ↓
Story Interpretation
      ↓
Motif / Semantic Space
      ↓
Person Sketch / Era Sketch
      ↓
Interactive Experience
```

---

# 13. Evidence First

系统中的所有历史判断尽量能够回到来源。

原则：

```text
史料
≠
学术考证
≠
AI判断
≠
现代解释
```

例如：

```text
《世说》正文
刘孝标注
《晋书》
余嘉锡《笺疏》
现代研究
AI推断
```

必须保持不同 provenance。

任何 Relation、Alias 和重要人物身份判断，都应尽可能留下证据链。

---

# 14. 当前开发策略：两个并行 Track

## Track A — Experience

先证明产品是不是值得使用：

```text
6个核心人物
↓
约20个代表故事
↓
Story Reader
↓
Person Sketch
↓
Relation Navigation
↓
第一个 Era Sketch
```

核心问题：

> **用户有没有真正进入《世说》？**

## Track B — Data / AI

为未来规模化准备：

```text
Mention Resolution
↓
Relation Evidence
↓
Story Metadata
↓
Semantic Benchmark
↓
Motif Candidate
↓
Human Review
```

核心问题：

> **这套方法能不能从6个人扩展到30个人，再扩到更多人物？**

Track B 不应阻塞 Track A。

---

# 15. 当前 MVP

第一阶段只使用现有六个人：

```text
王羲之
郗鉴
王导
王凝之
谢道韫
谢安
```

挑选约15–30则最有表现力的故事。

先完成：

```text
Story
Person
Relation
Theme
```

四种基本体验。

不需要先覆盖所有人物。

---

# 16. 第一个 Person Sketch

优先考虑：

> **谢安**

原因：

* 《世说》出现频繁；
* 有大量表现性场景；
* 《晋书》材料丰富；
* 家族、政治、清谈、人物品评均有体现；
* “雅量”特征非常鲜明；
* 可以观察人物不同阶段。

成功标准：

> 用户连续读完若干谢安故事以后，不需要百科介绍，也能形成一个具体的人物印象。

---

# 17. 第一个 Era Sketch

优先考虑：

> **雅量**

但：

```text
Era Sketch: 雅量
≠
《雅量》第六所有故事
```

需要结合：

* 《世说》篇目；
* 人工阅读；
* semantic retrieval；
* cross-chapter stories。

目标不是定义“雅量”。

而是让读者连续看到一组人物在压力、危险、巨大情绪中表现出的姿态，然后自己逐渐理解这个词。

---

# 18. Semantic Benchmark

在引入正式 semantic recommendation 前，建立：

> **Shishuo Semantic Benchmark**

人工设计一批查询，例如：

```text
临危从容
故作自然
真正不在意别人评价
朋友死亡后的强烈悲痛
门第影响婚姻
人物相互品评
政治宴会中的危险
面对死亡仍然旷达
表面平静但内心激动
突然访友
```

比较不同 embedding / reranker 对《世说》语义的理解能力。

实验室 GPU 可用于：

* embedding benchmark；
* reranker；
* batch LLM analysis。

最终选择：

> **最理解《世说》的模型**

而不是单纯依赖公开 benchmark 排名。

---

# 19. 暂时不做

为了避免项目无限膨胀，当前阶段明确暂缓：

* 全魏晋人物数据库；
* 所有人物自动关系抽取；
* 完整古代官职数据库；
* 完整地理系统；
* Neo4j；
* Postgres；
* 在线向量数据库；
* 在线 LLM 必需依赖；
* AI Chat 作为首页；
* 用户账户体系；
* 全史书 RAG；
* 全自动 Person Biography；
* 全自动 Era Interpretation；
* 大规模 70B 模型部署。

这些都可以以后增加，但不是项目成立的前提。

---

# 20. 资料扩展原则

采用：

> **Just-in-time enrichment**

例如：

```text
做谢安
→ 补谢安需要的材料

做嵇康
→ 再加强《三国志》、裴注等资料

做门第婚姻
→ 再集中补婚姻与士族研究
```

而不是先试图完成“整个魏晋数据库”。

---

# 21. 项目成功标准

不以：

* 人物数量；
* edge数量；
* embedding数量；
* AI模型大小；

作为主要成功指标。

真正的 Milestones 是：

## Milestone 1

一个第一次接触《世说》的用户能够自然读懂“东床坦腹”。

## Milestone 2

他能够从王羲之沿人物关系自然走到谢道韞、谢安。

## Milestone 3

读完一个 Person Sketch 后，他形成了一个有细节的人物印象。

## Milestone 4

读完“雅量” Era Sketch 后，他开始凭自己的感受理解所谓“魏晋风度”。

## Milestone 5

Semantic recommendation 能让他连续读下去，并感觉：

> “这些故事之间确实存在某种说不清但能够感受到的相似。”

到这里，世说Sketch才真正成立。

---

# 22. 最终原则

在今后的功能和数据设计中，可以反复用下面的问题校准方向：

### 这个功能是在帮助用户进入《世说》，还是只是在展示技术？

如果只是展示技术，不做。

### 这个解释是在拿掉阅读障碍，还是替用户把故事解释完了？

如果解释过度，删减。

### 这个AI结果是帮助发现，还是在替代历史判断？

如果替代历史判断，退回 candidate。

### 这个新数据库真的服务当前 Sketch 吗？

如果没有明确用途，暂缓建设。

### 这个功能直接问 ChatGPT 是否已经可以很好完成？

如果可以，就不把它作为项目核心竞争力。

---

# 23. 一句话定义

> **世说Sketch，是用《世说新语》的碎片，为人作素描，也为时代作素描。**

人物不是由履历组成，而由一幕幕被记住的瞬间组成。

时代也不是由年表组成，而由无数人在相似情境下反复表现出的姿态组成。

技术的任务不是取代阅读，而是让那些原本因为称谓、关系、时代距离而难以被感受到的东西重新显现。

---

# 24. 开发总路线

```text
可靠史料
   ↓
读懂故事
   ↓
认出人物
   ↓
理解关系
   ↓
重建场景
   ↓
发现反复出现的姿态
   ↓
Person Sketch
   ↓
Era Sketch
   ↓
关系漫游 + 语义漫游
```

最终希望达到的状态不是：

> “我查到了很多关于魏晋的知识。”

而是：

> **“我好像认识这些人了，也开始感觉到那个时代是什么样子。”**

---

## 当前开发入口

### Source processing

Kanripo source-processing pipeline 记录在
[docs/source-processing.md](docs/source-processing.md) 中。它将不可变的 TXT
源文件转换为保留 provenance 的 Markdown，并将《世说新语》切分为篇目和编辑性记录；不会简化繁体字，也不会抽取关系。

运行测试：

```sh
python3 -m unittest discover -s tests -v
```

### Scholarly lookup

如需按需查询余嘉锡《世说新语箋疏》，使用 Codex live web search；不会下载完整笺疏：

```sh
python3 scripts/lookup_shishuo_reference.py "谢太傅"
python3 scripts/lookup_shishuo_reference.py "谢太傅" --entry 06-yaliang-019
python3 scripts/lookup_shishuo_reference.py "谢太傅" --refresh
python3 scripts/lookup_shishuo_reference.py "谢太傅" --no-cache
```

查询报告缓存于 `.cache/shishuo-reference/`（已加入 Git ignore）。该工具使用
`codex exec --search --ephemeral --sandbox read-only`，不会抓取 CText HTML、绕过 CText 认证，也不会修改 canonical Shishuo entries 或 metadata。

## WP1 / SC1 static prototype

The first static vertical slice is anchored on `06-yaliang-019`（东床坦腹）.
It is generated from the existing canonical entry and the six-person pilot;
the source and normalized corpus are not copied by hand or modified.

Install the frontend dependencies and the Python schema validator in a fresh
environment:

```sh
npm install
python3 -m pip install -r requirements-dev.txt
```

Validate the WP1 schemas, IDs, cross-references, evidence links, scope
manifest, and generated static bundle:

```sh
npm run validate
```

Local research checkouts can require all ignored source payloads explicitly:

```sh
python3 scripts/validate_wp1.py --mode full
```

Clean CI/Pages checkouts use committed lock metadata for intentionally absent
source payloads without weakening artifact hashing:

```sh
python3 scripts/validate_wp1.py --mode portable
```

Build the static React/Vite/TypeScript site:

```sh
npm run build
```

Run the local development server:

```sh
npm run dev
```

The current prototype is a static reading page under the Vite base path
`/shishuoSketch/`. SC1 publishes the 16-story Story Chain Gold Set as an
experimental preview: `npm run build:sc1` generates the build-time bundle,
and `npm run validate:sc1` checks its publication states and Story ↔ Person
projections. The 15 candidate punctuation records remain unreviewed; only
their valid deterministic reading layers are marked `preview_ready`. No
runtime API or source-corpus fetch is used.
