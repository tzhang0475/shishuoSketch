# ZTJ0：資治通鑑来源与证据层级

ZTJ0 只建立可追溯的《資治通鑑》机器来源层，为后续 H0A 提供检索材料。
它不为《世说新语》故事决定年代，不创建 HistoricalEvent，也不规定《通鉴》
优先于《晋书》或《三国志》。不同来源仍然是不同证据。

## 已登记来源

| ID | 作用 | 版本 / 状态 |
| --- | --- | --- |
| `zizhi-tongjian-kanripo-wyg` | primary-machine | KR2b0007，文淵閣四庫全書 / WYG；当前处理主来源 |
| `zizhi-tongjian-kanripo-sbck` | early-textual-reference | KR2b0007，四部叢刊 / SBCK；登记为独立身份，但检查到的仓库 revision 没有独立 SBCK 文件族 |
| `zizhi-tongjian-kaoyi-kanripo` | critical-chronology | KR2b0008，四部叢刊；《資治通鑑考異》三十卷 |
| `zizhi-tongjian-mulu-kanripo` | chronology-reference | KR2b0010；《資治通鑑目錄》三十卷的稀疏机器参考 |

来源注册表是 `sources/registry/zizhi-tongjian.yaml`。机器来源的上游 revision、
文件大小和 SHA-256 见各下载目录的 `manifest.lock.json`。原始 `*.txt` 文件
遵循仓库约定保持在 Git 忽略目录中；它们不是处理结果，也不会被处理器改写。

## 为什么 WYG 是主处理来源

KR2b0007 的 `Readme.org` 标题为 `資治通鑑 / WYG`，页码标记也实际使用
`KR2b0007_WYG_...`，所以 WYG 是 ZTJ0 的默认外交机器文本。检查到的每个文件
同时保留 `#+PROPERTY: BASEEDITION SBCK`，这与 README / 页码的 WYG 标识不一致。
ZTJ0 将这一观察写入处理结果和文档，但不修改上游字段，也不把同一组 WYG 字节
冒充成独立 SBCK witness。

四部叢刊身份仍然有意义：它作为登记的早期文本参照，未来若取得独立文件族，
可在不覆盖 WYG 的情况下做逐段比较。当前不对两个版本作无声合并。

## Kaoyi 与 Mulu

《資治通鑑考異》单独处理为证据语料。每个卷文件保留完整考异段落、页码和源坐标；
ZTJ0 不把“考異存在”转成日期结论，也不自动附着到任何生产 Story。

《資治通鑑目錄》按实际可用程度登记。当前获取到前置材料加 26 个编号文件，
其中 7 个达到轻量机器文本阈值，19 个主要是页码标记或稀疏文字。ZTJ0 不 OCR
这些页面，不用缺失文字填空，也不让完整 Mulu 转录成为本阶段成功条件。

## 后续边界

H0A 可以使用这里的来源、卷号、紀标题、年号表面和 Kaoyi 证据进行人工可审计的
时间比较；它仍需单独处理异文、年号换算、争议和 Story temporal anchors。ZTJ0
到此停止。
