# ZTJ0：处理、索引与停止边界

## 输出层

`scripts/acquire_ztj0_sources.py` 负责从登记的 Kanripo 仓库浅克隆并只复制批准的
文本文件；现有下载目录不允许不同 SHA 的 payload 被覆盖。锁文件记录 provider、
repository、upstream commit、文件名、字节数和 SHA-256。

`scripts/build_ztj0_corpus.py` 生成：

- `content/processed/zizhi-tongjian/volumes/volume-001.json` … `volume-294.json`；
  每个记录含完整源文本、源 hash、Org 属性、页码、结构单元和一个观测到的
  chronicle block；
- `content/processed/zizhi-tongjian/kaoyi/kaoyi-001.json` … `kaoyi-030.json`；
  每卷一个完整、证据用途的 Kaoyi block；
- `content/processed/zizhi-tongjian/mulu/`；前置材料及实际获取到的稀疏目录文件；
- `data/derived/ztj0-processed-corpus.json`；处理总清单；
- `data/derived/ztj0-chronology-index.json`；按卷、纪表面、人物/年号表面和轻量
  文本 token 的静态检索索引；
- `data/derived/ztj0-kaoyi-index.json`；Kaoyi 证据 block 索引；
- `data/derived/ztj0-weijin-range.json`；从实际 `漢紀`、`魏紀`、`晉紀/晉記`
  头部推导的未来 H0A 搜索范围。

## 当前处理量

当前本地上游：

- 通鑑：294 个卷记录，294 个纪 block，92,274 个正文分层单元，133,664 个
  平衡括号注层单元；另有一个锁定但未分配的 `_295` stub；
- 考異：30 个证据 block；
- 目錄：实际 7 个编号文件有轻量机器文本，19 个编号文件稀疏或主要为页标。

通鑑的观测魏晋范围是卷 9–118：`漢紀` 卷 9–68、`魏紀` 卷 69–78、
`晉紀` 卷 79–118，卷一百二的实际表面 `晉記二十四` 另列。这是搜索范围，
不是对 Story 的年代判定。

## 层级与 provenance

主卷 block 的 `main_text` 保持司馬光正文便利投影；`annotations[]` 只在实际
平衡括号边界可靠时标为胡三省。每个注和 block 都保留源文件、字符范围、行号和
页码标记；完整原文仍在同一处理记录的 `source_text` 中。源 hash 同时与锁文件
和实际 payload 对照。

Kaoyi 的完整段落保持独立，`parse_status=source_evidence_only`。没有任何处理
步骤产生 HistoricalEvent、Story temporal anchor、PersonActivityAnchor 或跨来源
胜负判断。

## 验证与确定性

`scripts/validate_ztj0.py` 在 portable 模式使用锁和处理记录，在 full 模式还要求
忽略的 payload 在本地存在并逐一验证 hash。它检查卷覆盖、唯一 block ID、源文本
字节保持、注层作者与范围、Kaoyi/Mulu 状态和索引 hash。

构建输出不写当前时间、不使用随机 ID、不依赖文件系统遍历顺序。稳定 ID 由
`witness + source_file + source coordinates + layer` 计算；获取日期只存在于不可
用于处理 hash 的 acquisition lock metadata。每次构建都应产生相同字节。

## H0A 之前的限制

ZTJ0 不把年号转成公历，不为八十三个生产 Stories 配 temporal anchors，不把一个
chronicle block 当作 HistoricalEvent，不自动解决 Kaoyi 与其他史料的冲突，也不
添加前端时间线。下一阶段 H0A 才负责这些经过证据与人工审阅的历史推理。
