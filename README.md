![世说Sketch](shishuoSketch.png)

![世说Sketch](shishuoSketch.png)

# 世说Sketch

> **从一则故事，走进魏晋。**

世说Sketch是一个以《世说新语》为中心的互动阅读与数字人文项目。

它试图解决一个很简单的问题：

> 两千年以后，我们怎样才能重新读到《世说》里的“人”？

现代读者打开《世说新语》，常常很快遇到人物称谓、家族关系、时代背景和碎片化叙事的障碍。

世说Sketch希望把这些障碍轻轻拿掉。

你可以从一则故事开始，认出其中的人；
从一个人走到他的其他故事；
沿一段关系认识另一个人；
再从另一个人进入新的故事。

最终留下的仍然应该是《世说》，而不是数据库。

---

## 一次阅读，也是一段漫游

世说Sketch的基本路径不是搜索，而是：

```text
Story
  ↓
Person
  ↓
Relation
  ↓
Person
  ↓
Story
```

比如从“东床坦腹”开始：

```text
王羲之
→ 郗鉴
→ 王导
→ 王凝之
→ 谢道韫
→ 谢安
```

一个原本孤立的故事，会慢慢展开成家族、婚姻、友情、政治与人物品评组成的世界。

我们希望这种探索始终保留来路。

不是不断跳向新的页面，而是逐渐走进魏晋。

---

## 人物不是由履历组成，而由瞬间组成

《世说》很少完整介绍一个人的一生。

它留下的是一幕幕瞬间：

* 王羲之坦腹东床；
* 谢安临危而从容；
* 王子猷雪夜访戴；
* 嵇康临刑索琴；
* 阮籍穷途而哭；
* 朋友死后的一句话；
* 宴席中的一次沉默；
* 面对权势、礼法和死亡时的一种姿态。

所以这里的 Person 不是传统人物百科。

我们更希望：

> **让一个人从许多故事中慢慢显形。**

而不是先告诉读者：

> “这个人是怎样的人。”

再用故事证明这个结论。

这也是 **Sketch** 这个名字的含义。

---

## 从人物，逐渐看见一个时代

人物可以被素描，时代也可以。

魏晋并不只存在于帝王、战争、制度和年表中。

它还存在于一些不断重现的东西里：

```text
雅量
任诞
清谈
伤逝
人物品评
门第与婚姻
友情
政治恐惧
对死亡的态度
```

世说Sketch希望从具体故事开始，让这些气质自己出现。

不是先定义“魏晋风度”，再把故事放进去。

而是读过足够多的故事以后：

> **你开始自己感觉到，那个时代似乎有一种不同的神情。**

---

# 当前可以探索什么

世说Sketch已经从最初的小规模人物实验进入更完整的历史结构阶段。

目前的数据基础包括：

```text
《世说新语》
36 篇
1130 canonical entries

当前发布研究范围
143 Stories
75 Persons
330 Person ↔ Story links
```

在 Story 与 Person 之外，历史上下文正在逐渐加入：

```text
Person
Story
Family
Clan
Office
Event
Location
Regime
Time
```

这些结构不是为了建立一个“万能魏晋知识图谱”。

它们首先服务一个目的：

> **让故事更容易被读懂，也让人物之间原本隐约的联系重新可见。**

---

# 阅读方式

## 读故事

Story 是整个产品的中心。

正文尽量保持原来的阅读节奏，只在必要的位置提供帮助。

例如原文中的：

```text
郗太傅
王丞相
逸少
```

可以被解析为具体人物。

这些称谓不是被替换掉，而是成为进入人物世界的入口。

---

## 认出人物

点击已经解析的称谓，可以直接查看人物。

人物信息不是与正文分离的百科页面，而是阅读过程的一部分：

```text
Story
  ↓
Person
  ↓
他的关系
  ↓
他的其他故事
```

多个故事共同构成一个 Person Sketch。

---

## 沿关系继续走

人物关系不是一个孤立的：

```text
A ───── B
```

一条 Relation 应该能够回答：

```text
他们是什么关系？
        ↓
依据来自哪里？
        ↓
哪些故事与这段关系有关？
        ↓
还能从这里走向谁？
```

人物关系因此既是历史信息，也是阅读路径。

---

## 继续追史料

如果读者想知道：

> 为什么可以这样理解？

可以继续展开证据。

目前项目逐步整合：

* 《世说新语》正文；
* 刘孝标注；
* 《晋书》；
* 其他早期史料；
* 后世考证与现代研究。

这些来源不会被混成一个“答案”。

项目尽量保持：

```text
史料事实
≠ 学术考证
≠ 数据推导
≠ AI 判断
≠ 现代解释
```

---

# Evidence First

世说Sketch的底层原则之一是：

> **重要的历史判断应该能够回到证据。**

Person、Alias、Relation、Story context 等数据尽量保留 provenance 和 review status。

例如：

```text
candidate
reviewed
rejected
```

共同出现也不自动等于历史关系：

```text
co-occurrence ≠ historical relationship
```

不知道的关系保持未知。

缺失的边也不是“没有关系”的证据。

---

# AI 在这里做什么

世说Sketch并不把“和古人聊天”作为产品中心。

我们的原则是：

> **AI is a build dependency, not a runtime dependency.**

AI与机器学习主要用于离线研究与数据构建，例如：

```text
entity / alias candidates
relation candidates
semantic retrieval
motif discovery
historical graph representation
story / person representation
```

它们首先帮助：

> **发现值得进一步看的东西。**

而不是自动决定：

> **历史事实是什么。**

最终进入阅读界面的重要事实与解释，需要经过来源约束与审核。

网站本身因此可以保持 static-first，并不要求用户每阅读一则故事都调用一次 LLM。

---

# Historical Graph

随着人物与故事范围扩大，项目正在形成一个 provenance-aware historical graph。

它连接的并不只有 Person 与 Story，还包括：

```text
Person ─ Story
Person ─ Family
Person ─ Clan
Person ─ Office
Story  ─ Event
Story  ─ Location
Person / Story ─ Time
```

这个 graph 有两个用途。

第一，是为阅读提供可靠的历史上下文。

第二，是为后续机器学习提供结构化的研究空间。

但 graph 本身不是历史真相。

它受到现存史料、编辑范围、人物覆盖程度以及 review status 的限制，因此项目同时保留 graph scope、coverage 和 bias audit。

---

# 我们在做什么

当前开发重点已经从“能不能做出一页《世说》阅读器”，转向：

```text
可靠文本
   ↓
人物识别
   ↓
关系与历史上下文
   ↓
可漫游的阅读体验
   ↓
Person Sketch
   ↓
语义与 motif 发现
   ↓
Era Sketch
```

接下来的问题不是单纯增加更多人物和更多故事。

而是：

> **这些结构能不能真正帮助读者更好地认识一个人？**

以及：

> **当许多人物和故事连接起来以后，我们能不能看到一些单独阅读时不容易看到的东西？**

---

# 设计原则

### Story first

故事始终是内容原子。

数据库、图结构和模型都不能取代阅读本身。

### Progressive disclosure

第一次阅读只提供继续读下去所需要的信息。

更多人物、关系、史料和历史背景逐层展开。

### Preserve context

探索人物和关系时，尽量保留用户从哪里来。

漫游不应该破坏阅读上下文。

### Evidence before interpretation

先建立可追溯的事实层，再增加解释。

### Let people emerge from stories

不要先替人物下结论。

让许多故事共同构成人物。

### Restraint

技术的任务是让原本难以被感受到的东西重新显现。

不是把《世说》解释完。

---

# 项目结构

整体数据流大致为：

```text
Raw Witnesses
      ↓
Normalization
      ↓
Canonical Story Units
      ↓
Mention / Alias / Person
      ↓
Historical Context
      ↓
Evidence-backed Relations
      ↓
Historical Graph
      ↓
Semantic / ML Layer
      ↓
Person Sketch / Era Sketch
      ↓
Interactive Reading
```

前端主要围绕四种对象展开：

```text
Story
Person
Relation
Theme / Motif
```

---

# 本地开发

安装依赖：

```bash
npm install
python3 -m pip install -r requirements-dev.txt
```

运行校验：

```bash
npm run validate
```

构建网站：

```bash
npm run build
```

本地开发：

```bash
npm run dev
```

项目使用 React / TypeScript / Vite 构建静态阅读界面，并使用 Python 完成文本处理、数据构建、schema validation 与历史图生成。

---

# 项目状态

世说Sketch仍然是一个持续发展的 research / product prototype。

当前重点不是追求：

```text
最多的人物
最多的关系
最大的知识图谱
最大的语言模型
```

而是验证一个更基本的问题：

> **数字工具能不能减少两千年的阅读距离，却不替读者把《世说》读完？**

如果答案是可以，那么一个人可以从一则故事出发，沿着人物、关系和记忆不断走下去。

最后得到的也许不是一张完整的魏晋地图。

而是一幅逐渐显影的素描。

---

> **世说Sketch，用《世说新语》的碎片，为人作素描，也为时代作素描。**
