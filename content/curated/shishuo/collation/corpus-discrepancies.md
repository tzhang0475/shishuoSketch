# Shishuo Kanripo ↔ Wikisource corpus discrepancy scan

This is a deterministic machine-level scan of the 36 normalized chapter views and proposed entry openings. It compares Kanripo/SBCK to the Wikisource 四部叢刊 page witness after removing whitespace/layout and treating explicit unrendered glyph markers as alignment tokens. It does not prove semantic boundary correctness and it performs no repair.

## Aggregate

- chapters scanned: 36
- proposed Kanripo entries: 1124
- exact opening matches: 903
- prefix opening matches (character/markup difference remains): 47
- suffix opening matches (possible shifted/partial opening): 102
- unmatched openings: 72
- chapters with aggregate discrepancies: 28

## Per-chapter summary

| chapter | Kanripo entries | exact | prefix | suffix | unmatched | aggregate discrepancy |
|---|---:|---:|---:|---:|---:|---|
| `01-dexing` | 47 | 44 | 1 | 0 | 2 | yes |
| `02-yanyu` | 108 | 90 | 4 | 8 | 6 | yes |
| `03-zhengshi` | 26 | 22 | 1 | 0 | 3 | yes |
| `04-wenxue` | 104 | 87 | 1 | 7 | 9 | yes |
| `05-fangzheng` | 65 | 51 | 2 | 5 | 7 | yes |
| `06-yaliang` | 42 | 33 | 2 | 5 | 2 | yes |
| `07-shijian` | 28 | 21 | 3 | 2 | 2 | yes |
| `08-shangyu` | 154 | 115 | 5 | 21 | 13 | yes |
| `09-pinzao` | 88 | 65 | 7 | 12 | 4 | yes |
| `10-guizhen` | 27 | 20 | 2 | 3 | 2 | yes |
| `11-jiewu` | 7 | 5 | 0 | 1 | 1 | yes |
| `12-suhui` | 7 | 6 | 0 | 0 | 1 | yes |
| `13-haoshuang` | 13 | 7 | 1 | 5 | 0 | no |
| `14-rongzhi` | 39 | 31 | 2 | 3 | 3 | yes |
| `15-zixin` | 2 | 2 | 0 | 0 | 0 | no |
| `16-qixian` | 6 | 5 | 0 | 0 | 1 | yes |
| `17-shangshi` | 19 | 13 | 1 | 2 | 3 | yes |
| `18-qiyi` | 15 | 13 | 1 | 1 | 0 | yes |
| `19-xianyuan` | 31 | 28 | 1 | 1 | 1 | yes |
| `20-shujie` | 11 | 11 | 0 | 0 | 0 | yes |
| `21-qiaoyi` | 14 | 13 | 1 | 0 | 0 | no |
| `22-chongli` | 6 | 4 | 1 | 1 | 0 | no |
| `23-rendan` | 54 | 43 | 7 | 1 | 3 | yes |
| `24-jianao` | 17 | 17 | 0 | 0 | 0 | yes |
| `25-paidiao` | 65 | 57 | 1 | 6 | 1 | yes |
| `26-qingdi` | 33 | 24 | 0 | 7 | 2 | yes |
| `27-jiajue` | 14 | 10 | 0 | 2 | 2 | yes |
| `28-chumian` | 9 | 5 | 0 | 3 | 1 | yes |
| `29-jianshe` | 9 | 8 | 0 | 0 | 1 | yes |
| `30-taichi` | 12 | 10 | 1 | 1 | 0 | no |
| `31-fenjuan` | 8 | 6 | 0 | 1 | 1 | yes |
| `32-chanxian` | 4 | 2 | 1 | 1 | 0 | no |
| `33-youhui` | 17 | 14 | 0 | 3 | 0 | no |
| `34-pilou` | 8 | 8 | 0 | 0 | 0 | yes |
| `35-huoni` | 7 | 6 | 1 | 0 | 0 | no |
| `36-chouxi` | 8 | 7 | 0 | 0 | 1 | yes |

## Discrepancy records

### 01-dexing — 01-dexing-003 — `unmatched_entry_opening`

- classification: `unresolved`
- confidence: `low`
- requires visual verification: `True`
- recommended action: Inspect the same-edition page witness and the relevant glyph/character reading before classifying as a textual variant or source gap.
- Kanripo opening key: `郭林宗至汝南造袁奉髙`
- Kanripo opening text (source spelling): `郭林宗至汝南造袁奉髙(原介休人泰少孤年二十/續漢書曰郭泰字林宗太)
`
- Kanripo location: `content/processed/shishuo/chapters/chapter-01.md`; normalized line `716`; page `<pb:KR3l0002_SBCK_001-1b>`
- Wikisource match type: `none`
- Wikisource page: `not located`

```text
No aligned Wikisource reading.
```

---

### 01-dexing — 01-dexing-013 — `unmatched_entry_opening`

- classification: `unresolved`
- confidence: `low`
- requires visual verification: `True`
- recommended action: Inspect the same-edition page witness and the relevant glyph/character reading before classifying as a textual variant or source gap.
- Kanripo opening key: `華歆王朗俱乘船避難有一人`
- Kanripo opening text (source spelling): `華歆王朗俱乘船避難有一人`
- Kanripo location: `content/processed/shishuo/chapters/chapter-01.md`; normalized line `778`; page `<pb:KR3l0002_SBCK_001-4b>`
- Wikisource match type: `none`
- Wikisource page: `not located`

```text
No aligned Wikisource reading.
```

---

### 01-dexing — 01-dexing-046 — `non_exact_entry_opening`

- classification: `unresolved`
- confidence: `low`
- requires visual verification: `True`
- recommended action: Review the exact character/glyph and boundary context; no automatic repair is made.
- Kanripo opening key: `孔僕射為孝武侍中豫蒙眷接`
- Kanripo opening text (source spelling): `孔僕射為孝武侍中豫蒙眷接`
- Kanripo location: `content/processed/shishuo/chapters/chapter-01.md`; normalized line `1027`; page `<pb:KR3l0002_SBCK_001-16a>`
- Wikisource match type: `prefix`
- Wikisource page: `Page:Sibu Congkan0462-劉義慶-世説新語-3-1.djvu/40`

```text
吳郡袁府君即日便征遺己聚歛得數斗焦飯未展歸家遂帶以從軍戰於滬瀆敗軍人潰散逃走山澤皆多饑死遺獨以焦飯得活時人以為純孝之報也孔僕射為孝武侍中豫⟦{{SKchar|3681}}⟧眷接烈宗山陵孔時為太常形素羸瘦著重服竟日涕泗流漣見者以為真孝子吳道助附子兄弟居在丹陽郡後遭母童夫人艱朝夕哭臨及思至賓客弔省號踊哀絶路人為之落淚韓康伯時為丹陽尹母殷在郡每聞二吳之哭輙為悽惻語康伯曰汝若為⟦{{SKchar|3752}}⟧官當好料理此人康伯亦甚相知韓後果為吏部尚書大吳不免哀制小吳遂大貴達
```

---

### 01-dexing — `probable_one_character_shift`

- classification: `unresolved`
- confidence: `medium`
- requires visual verification: `True`
- recommended action: Use page-level visual witnesses to determine whether this is a missing/extra passage, a glyph/character variant, or a segmentation difference. No textual repair is performed.
- Kanripo main characters: 2766
- Wikisource main characters: 2766
- length delta (Wikisource − Kanripo): 0
- sequence ratio: 0.996023
- Kanripo location: `content/processed/shishuo/chapters/chapter-01.md`; page markers `['<pb:KR3l0002_SBCK_001-1b>', '<pb:KR3l0002_SBCK_001-2a>', '<pb:KR3l0002_SBCK_001-2b>', '<pb:KR3l0002_SBCK_001-3a>', '<pb:KR3l0002_SBCK_001-3b>', '<pb:KR3l0002_SBCK_001-4a>', '<pb:KR3l0002_SBCK_001-4b>', '<pb:KR3l0002_SBCK_001-5a>', '<pb:KR3l0002_SBCK_001-5b>', '<pb:KR3l0002_SBCK_001-6a>', '<pb:KR3l0002_SBCK_001-6b>', '<pb:KR3l0002_SBCK_001-7a>', '<pb:KR3l0002_SBCK_001-7b>', '<pb:KR3l0002_SBCK_001-8a>', '<pb:KR3l0002_SBCK_001-8b>', '<pb:KR3l0002_SBCK_001-9a>', '<pb:KR3l0002_SBCK_001-9b>', '<pb:KR3l0002_SBCK_001-10a>', '<pb:KR3l0002_SBCK_001-10b>', '<pb:KR3l0002_SBCK_001-11a>', '<pb:KR3l0002_SBCK_001-11b>', '<pb:KR3l0002_SBCK_001-12a>', '<pb:KR3l0002_SBCK_001-12b>', '<pb:KR3l0002_SBCK_001-13a>', '<pb:KR3l0002_SBCK_001-13b>', '<pb:KR3l0002_SBCK_001-14a>', '<pb:KR3l0002_SBCK_001-14b>', '<pb:KR3l0002_SBCK_001-15a>', '<pb:KR3l0002_SBCK_001-15b>', '<pb:KR3l0002_SBCK_001-16a>', '<pb:KR3l0002_SBCK_001-16b>']`
- Wikisource page range: `Page:Sibu Congkan0462-劉義慶-世説新語-3-1.djvu/10` through `Page:Sibu Congkan0462-劉義慶-世説新語-3-1.djvu/41` (32 pages)
- Wikisource source URL range: `https://zh.wikisource.org/wiki/Page%3ASibu%20Congkan0462-%E5%8A%89%E7%BE%A9%E6%85%B6-%E4%B8%96%E8%AA%AC%E6%96%B0%E8%AA%9E-3-1.djvu%2F10` through `https://zh.wikisource.org/wiki/Page%3ASibu%20Congkan0462-%E5%8A%89%E7%BE%A9%E6%85%B6-%E4%B8%96%E8%AA%AC%E6%96%B0%E8%AA%9E-3-1.djvu%2F41`

```text
陳仲舉言為士則行為世範登車攬轡有澄清天下之志為豫章太守至便問徐孺子所在欲先看之主簿白羣情欲府君先入廨陳曰武王式商容之閭席不暇煗吾之禮賢有何不可周子居常云吾時月不見黄叔度則鄙吝之心已復生矣郭林宗至汝南造袁奉髙車不停軌鸞不輟軛詣黄叔度乃彌日信宿人問其故林宗曰叔度汪汪如萬頃之陂澄之不清擾之不濁其器深廣難測量也李元禮風格秀整髙自標持欲以天下名教是非為己任後進之士有升其堂者皆以為登龍門李元禮嘗歎荀淑鍾皓曰荀君清識難尚鍾君至德可師陳太丘詣荀朗陵貧儉無僕役乃使元方將車季方持杖後從長文尚小載箸車中既至荀使叔慈應門慈明行酒餘六龍下食文若亦小坐箸䣛前于
```

```text
陳仲舉言為士則行為世範登車攬轡有澄清天下之志為豫章太守至便問徐孺子所在欲先看之主簿白羣情欲府君先入𪠘陳曰武王式商容之閭席不暇煗吾之禮賢有何不可周子居常云吾時月不見黄叔度則鄙吝之心已復生矣郭林宗至汝南造𡊮奉髙車不停軌鸞不輟軛詣黄叔度乃彌日信宿人問其故林宗曰叔度汪汪如萬頃之陂澄之不清擾之不濁其器深廣難測量也李元禮風格秀整髙自標持欲以天下名教是非為己任後進之士有升其堂者皆以為登龍門李元禮嘗歎荀淑鍾皓曰荀君清識難尚鍾君至德可師陳太丘詣荀朗陵貧儉無僕役乃使元方將車季方持杖後從長文尚小載箸車中既至荀使叔慈應門慈明行酒餘六龍下食文若亦小坐箸䣛前于
```

---

### 02-yanyu — 02-yanyu-012 — `non_exact_entry_opening`

- classification: `unresolved`
- confidence: `low`
- requires visual verification: `True`
- recommended action: Review the exact character/glyph and boundary context; no automatic repair is made.
- Kanripo opening key: `鍾毓兄弟小時值父晝寢因共`
- Kanripo opening text (source spelling): `鍾毓兄弟小時值父晝寢因共`
- Kanripo location: `content/processed/shishuo/chapters/chapter-02.md`; normalized line `1175`; page `<pb:KR3l0002_SBCK_001-22b>`
- Wikisource match type: `prefix`
- Wikisource page: `Page:Sibu Congkan0462-劉義慶-世説新語-3-1.djvu/53`

```text
魏文帝聞之語其父鍾繇曰可令二子來於是敕見毓面有汗帝曰卿面何以汗毓對曰戰戰惶惶汗出如漿復問㑹卿何以不汗對曰戰戰慄慄汗不敢出鍾毓兄弟小時值父晝⟦{{SKchar|3465}}⟧因共偷服藥酒其父時覺且託⟦{{SKchar|3461}}⟧以觀之毓拜而後飲㑹飲而不拜既而問毓何以拜毓曰酒以成禮不敢不拜又問㑹何以不拜㑹曰偷本非禮所以不拜魏明帝為外祖母築舘於甄氏既成自行視謂左右曰舘當以何為名侍中繆襲曰陛下聖思齊於哲王罔極過於曾閔此舘之興情鍾舅氏宜以渭陽為名何平叔云服五石散非唯治病亦覺神明開朗嵇中散語趙景眞卿瞳子白黑
```

---

### 02-yanyu — 02-yanyu-050 — `non_exact_entry_opening`

- classification: `unresolved`
- confidence: `low`
- requires visual verification: `True`
- recommended action: Review the exact character/glyph and boundary context; no automatic repair is made.
- Kanripo opening key: `孫齊由齊莊二人小時詣庾公`
- Kanripo opening text (source spelling): `孫齊由齊莊二人小時詣庾公`
- Kanripo location: `content/processed/shishuo/chapters/chapter-02.md`; normalized line `1446`; page `<pb:KR3l0002_SBCK_001-35a>`
- Wikisource match type: `prefix`
- Wikisource page: `Page:Sibu Congkan0462-劉義慶-世説新語-3-1.djvu/78`

```text
户或云卞令孫盛為庾公記室叅軍從獵將其二兒俱行庾公不知忽於獵塲見齊莊時年七八歳⟦{{SKchar|2928}}⟧謂曰君亦復來邪應聲荅曰所謂無小無大從公于邁孫齊由齊莊二人小時詣⟦{{SKchar|2928}}⟧公公問齊由何字荅曰字齊由公曰欲何齊邪曰齊許由齊莊何字荅曰字齊莊公曰欲何齊曰齊莊周公曰何不慕仲尼而慕莊周對曰聖人生知故難企慕⟦{{SKchar|2928}}⟧公大喜小兒對張𤣥之顧敷是顧和中外孫皆少而聦惠和並知之而常謂顧勝親重偏至張頗不懕于時張年九歲顧年七歲和與俱至寺中見佛般泥洹像弟子有泣者有不泣者和以問二孫𤣥謂被親故泣不被親故不泣
```

---

### 02-yanyu — 02-yanyu-051 — `non_exact_entry_opening`

- classification: `unresolved`
- confidence: `low`
- requires visual verification: `True`
- recommended action: Review the exact character/glyph and boundary context; no automatic repair is made.
- Kanripo opening key: `張玄之顧敷是顧和中外孫皆`
- Kanripo opening text (source spelling): `張玄之顧敷是顧和中外孫皆`
- Kanripo location: `content/processed/shishuo/chapters/chapter-02.md`; normalized line `1456`; page `<pb:KR3l0002_SBCK_001-35b>`
- Wikisource match type: `suffix`
- Wikisource page: `Page:Sibu Congkan0462-劉義慶-世説新語-3-1.djvu/79`

```text
齊由公曰欲何齊邪曰齊許由齊莊何字荅曰字齊莊公曰欲何齊曰齊莊周公曰何不慕仲尼而慕莊周對曰聖人生知故難企慕⟦{{SKchar|2928}}⟧公大喜小兒對張𤣥之顧敷是顧和中外孫皆少而聦惠和並知之而常謂顧勝親重偏至張頗不懕于時張年九歲顧年七歲和與俱至寺中見佛般泥洹像弟子有泣者有不泣者和以問二孫𤣥謂被親故泣不被親故不泣敷曰不然當由忘情故不泣不能忘情故泣𢈔法畼造𢈔太尉握麈尾至佳公曰此至佳那得在法畼曰廉者不求貪者不與故得在耳⟦{{SKchar|2928}}⟧穉恭為荆州以毛扇上武帝武帝疑是故物侍中劉劭曰栢梁雲構工匠
```

---

### 02-yanyu — 02-yanyu-052 — `unmatched_entry_opening`

- classification: `unresolved`
- confidence: `low`
- requires visual verification: `True`
- recommended action: Inspect the same-edition page witness and the relevant glyph/character reading before classifying as a textual variant or source gap.
- Kanripo opening key: `庾法畼造庾太尉握麈尾至佳`
- Kanripo opening text (source spelling): `庾法畼造庾太尉握麈尾至佳`
- Kanripo location: `content/processed/shishuo/chapters/chapter-02.md`; normalized line `1464`; page `<pb:KR3l0002_SBCK_001-35b>`
- Wikisource match type: `none`
- Wikisource page: `not located`

```text
No aligned Wikisource reading.
```

---

### 02-yanyu — 02-yanyu-053 — `non_exact_entry_opening`

- classification: `unresolved`
- confidence: `low`
- requires visual verification: `True`
- recommended action: Review the exact character/glyph and boundary context; no automatic repair is made.
- Kanripo opening key: `庾穉恭為荆州以毛扇上武帝`
- Kanripo opening text (source spelling): `庾穉恭為荆州(也少有大度時論以經畧許之兄太/庾翼别傳曰翼字穉恭潁川鄢陵人)
(七州進征南將軍荆州刺史/尉亮薨朝議推才乃以翼都督)以毛扇上武帝`
- Kanripo location: `content/processed/shishuo/chapters/chapter-02.md`; normalized line `1468`; page `<pb:KR3l0002_SBCK_001-36a>`
- Wikisource match type: `suffix`
- Wikisource page: `Page:Sibu Congkan0462-劉義慶-世説新語-3-1.djvu/80`

```text
泣不被親故不泣敷曰不然當由忘情故不泣不能忘情故泣𢈔法畼造𢈔太尉握麈尾至佳公曰此至佳那得在法畼曰廉者不求貪者不與故得在耳⟦{{SKchar|2928}}⟧穉恭為荆州以毛扇上武帝武帝疑是故物侍中劉劭曰栢梁雲構工匠先居其下管⟦{{SKchar|2959}}⟧繁奏鍾夔先聽其音穉恭上扇以好不以新⟦{{SKchar|2928}}⟧後聞之曰此人宜在帝左右何驃騎亡後徵禇公入既至石頭王長史劉尹同詣禇禇曰真長何以處我真長顧王曰此子能言禇因視王王曰國自有周公桓公北征經金城見前為琅邪時種柳皆已十圍慨然曰木猶如此人何以堪攀枝執條⟦{{SKchar|3178}}⟧然流淚簡文作撫軍時嘗與桓宣
```

---

### 02-yanyu — 02-yanyu-069 — `non_exact_entry_opening`

- classification: `unresolved`
- confidence: `low`
- requires visual verification: `True`
- recommended action: Review the exact character/glyph and boundary context; no automatic repair is made.
- Kanripo opening key: `劉真長為丹陽尹許玄度出都`
- Kanripo opening text (source spelling): `劉真長為丹陽尹許玄度出都`
- Kanripo location: `content/processed/shishuo/chapters/chapter-02.md`; normalized line `1558`; page `<pb:KR3l0002_SBCK_001-40a>`
- Wikisource match type: `prefix`
- Wikisource page: `Page:Sibu Congkan0462-劉義慶-世説新語-3-1.djvu/88`

```text
王謂劉曰卿更長進荅曰此若天之自髙耳劉尹云人想王荆産佳此想長松下當有清風耳王仲祖聞蠻語不解茫然曰若使介葛盧來朝故當不昩此語劉真長為丹陽尹許⟦{{SKchar|2593}}⟧度出都就劉宿牀帷新麗飲食豐甘許曰若保全此處殊勝東山劉曰卿若知吉凶由人吾安得不保此王逸少在坐曰令巢許遇稷契當無此言二人並有愧色王右軍與謝太傅共登冶城謝悠然逺想有髙世之志王謂謝曰夏禹勤王手足胼胝文王旰食日不暇給今四郊多壘宜人人自效而虛談廢務浮文妨要恐非當今所宜謝荅曰秦任商鞅二世而亡豈清言致患邪謝太傅寒雪日
```

---

### 02-yanyu — 02-yanyu-072 — `unmatched_entry_opening`

- classification: `unresolved`
- confidence: `low`
- requires visual verification: `True`
- recommended action: Inspect the same-edition page witness and the relevant glyph/character reading before classifying as a textual variant or source gap.
- Kanripo opening key: `王中郎令伏玄度習鑿齒論青`
- Kanripo opening text (source spelling): `王中郎令伏玄度習鑿齒(太原晉陽人祖東海太守/王中郎傳曰坦之字文度)
(至譽輯朝野標的當時累遷侍中中書令領北中郎/承清淡平逺父述貞貴簡正坦之器度淳深孝友天)
(人少有才學舉秀才大司馬桓温叅軍領大著作掌/將徐兖二州刺史中興書曰伏滔字玄度平昌安丘)
(善尺牘桓温在荆州辟為從事歴治中别駕遷滎陽/國史游撃將軍卒習鑿齒字彦威襄陽人少以文稱)
(守/太)論青`
- Kanripo location: `content/processed/shishuo/chapters/chapter-02.md`; normalized line `1580`; page `<pb:KR3l0002_SBCK_001-41a>`
- Wikisource match type: `none`
- Wikisource page: `not located`

```text
No aligned Wikisource reading.
```

---

### 02-yanyu — 02-yanyu-073 — `non_exact_entry_opening`

- classification: `unresolved`
- confidence: `low`
- requires visual verification: `True`
- recommended action: Review the exact character/glyph and boundary context; no automatic repair is made.
- Kanripo opening key: `劉尹云清風朗月輙思玄度荀`
- Kanripo opening text (source spelling): `劉尹云清風朗月輙思玄度(能清言于時士人皆欽/晉中興士人書曰許詢)
(愛之/慕仰)
荀`
- Kanripo location: `content/processed/shishuo/chapters/chapter-02.md`; normalized line `1598`; page `<pb:KR3l0002_SBCK_001-42a>`
- Wikisource match type: `prefix`
- Wikisource page: `Page:Sibu Congkan0462-劉義慶-世説新語-3-1.djvu/92`

```text
起公大笑樂即公大兄無奕女左將軍王凝之妻也王中郎令伏⟦{{SKchar|2593}}⟧度習鑿齒論青楚人物臨成以示韓康伯康伯都無言王曰何故不言韓曰無可無不可劉尹云清風朗月輙思𤣥度荀中郎在京口登北固望海云雖未覩三山便自使人有凌雲意若秦漢之君必當褰裳濡足謝公云賢聖去人其間亦邇子姪未之許公歎曰若郗超聞此語必不至河漢支公好鶴住剡東𡵙山有人遺其𩀱鶴少時翅長欲飛支意惜之乃鎩其翮鶴軒翥不復能飛乃反顧翅垂頭視之如有懊喪意林曰既有陵霄之姿何肻為人作耳目近玩養令翮成置使飛去謝中郎經曲阿後湖問
```

---

### 02-yanyu — 02-yanyu-076 — `unmatched_entry_opening`

- classification: `unresolved`
- confidence: `low`
- requires visual verification: `True`
- recommended action: Inspect the same-edition page witness and the relevant glyph/character reading before classifying as a textual variant or source gap.
- Kanripo opening key: `支公好鶴住剡東山有人遺其`
- Kanripo opening text (source spelling): `支公好鶴住剡東&KR2192;山(㑹稽二百里/支公書曰山去)有人遺其`
- Kanripo location: `content/processed/shishuo/chapters/chapter-02.md`; normalized line `1612`; page `<pb:KR3l0002_SBCK_001-42b>`
- Wikisource match type: `none`
- Wikisource page: `not located`

```text
No aligned Wikisource reading.
```

---

### 02-yanyu — 02-yanyu-079 — `unmatched_entry_opening`

- classification: `unresolved`
- confidence: `low`
- requires visual verification: `True`
- recommended action: Inspect the same-edition page witness and the relevant glyph/character reading before classifying as a textual variant or source gap.
- Kanripo opening key: `謝胡兒語庾道季諸人莫當就`
- Kanripo opening text (source spelling): `謝胡兒語庾道季(道季太尉亮子也風情率悟以文/道季庾龢小字徐廣晉紀曰龢字)
(丹陽尹兼中領軍/談致稱於時歷仕至)諸人莫當就`
- Kanripo location: `content/processed/shishuo/chapters/chapter-02.md`; normalized line `1625`; page `<pb:KR3l0002_SBCK_001-43a>`
- Wikisource match type: `none`
- Wikisource page: `not located`

```text
No aligned Wikisource reading.
```

---

### 02-yanyu — 02-yanyu-080 — `unmatched_entry_opening`

- classification: `unresolved`
- confidence: `low`
- requires visual verification: `True`
- recommended action: Inspect the same-edition page witness and the relevant glyph/character reading before classifying as a textual variant or source gap.
- Kanripo opening key: `李弘度常歎不被遇`
- Kanripo opening text (source spelling): `李弘度常歎不被遇(人也祖康父矩皆有美名充初/中興書曰李充字弘度江夏鄳)
`
- Kanripo location: `content/processed/shishuo/chapters/chapter-02.md`; normalized line `1629`; page `<pb:KR3l0002_SBCK_001-43a>`
- Wikisource match type: `none`
- Wikisource page: `not located`

```text
No aligned Wikisource reading.
```

---

### 02-yanyu — 02-yanyu-096 — `unmatched_entry_opening`

- classification: `unresolved`
- confidence: `low`
- requires visual verification: `True`
- recommended action: Inspect the same-edition page witness and the relevant glyph/character reading before classifying as a textual variant or source gap.
- Kanripo opening key: `毛伯成既負其才氣常稱寧為`
- Kanripo opening text (source spelling): `毛伯成既負其才氣常稱寧為`
- Kanripo location: `content/processed/shishuo/chapters/chapter-02.md`; normalized line `1714`; page `<pb:KR3l0002_SBCK_001-47a>`
- Wikisource match type: `none`
- Wikisource page: `not located`

```text
No aligned Wikisource reading.
```

---

### 02-yanyu — 02-yanyu-097 — `non_exact_entry_opening`

- classification: `unresolved`
- confidence: `low`
- requires visual verification: `True`
- recommended action: Review the exact character/glyph and boundary context; no automatic repair is made.
- Kanripo opening key: `范寗作豫章八日請佛有板衆`
- Kanripo opening text (source spelling): `范寗作豫章(學通覽累遷中書郎豫章太守/中興書曰寗字武子慎陽縣人博)八日
請佛有板衆`
- Kanripo location: `content/processed/shishuo/chapters/chapter-02.md`; normalized line `1716`; page `<pb:KR3l0002_SBCK_001-47a>`
- Wikisource match type: `suffix`
- Wikisource page: `Page:Sibu Congkan0462-劉義慶-世説新語-3-1.djvu/102`

```text
爾哭之狀其可見乎顧曰鼻如廣莫長風眼如懸河決溜或曰聲如震雷破山淚如傾河注海毛伯成既⟦{{SKchar|3688}}⟧其才氣常稱寧為蘭摧玉折不作蕭敷艾榮范⟦{{SKchar|1195}}⟧作豫章八日請佛有板衆僧疑或欲作荅有小沙彌在坐末曰世尊默然則為許可衆從其義司馬太傅齋中夜坐于時天月明淨都無纎翳太傅歎以為佳謝景重在坐荅曰意謂乃不如微雲點綴太傅因戲謝曰卿居心不淨乃復强欲滓穢太清邪王中郎甚愛張天錫問之曰卿觀過江諸人經緯江左軌轍有何偉異後來之彦復何如中原張曰研求幽䆳自王何以還因時脩制荀樂之風王曰卿知見有餘何故
```

---

### 02-yanyu — 02-yanyu-101 — `non_exact_entry_opening`

- classification: `unresolved`
- confidence: `low`
- requires visual verification: `True`
- recommended action: Review the exact character/glyph and boundary context; no automatic repair is made.
- Kanripo opening key: `桓玄義興還後見司馬太傅太`
- Kanripo opening text (source spelling): `桓玄義興還後見司馬太傅太`
- Kanripo location: `content/processed/shishuo/chapters/chapter-02.md`; normalized line `1742`; page `<pb:KR3l0002_SBCK_001-48b>`
- Wikisource match type: `suffix`
- Wikisource page: `Page:Sibu Congkan0462-劉義慶-世説新語-3-1.djvu/105`

```text
南門要望候拜時謂謝曰王⟦{{SKchar|1195}}⟧異謀云是卿為其計謝曾無懼色斂笏對曰樂彦輔有言豈以五男易一女太傅善其對因舉酒勸之曰故自佳故自佳桓𤣥義興還後見司馬太傅太傅已醉坐上多客問人云桓温來欲作賊如何桓𤣥伏不得起謝景重時爲長史舉板荅曰故宣武公黜昏暗登聖明功超伊霍紛紜之議裁之聖鑒太傅曰我知我知卽舉酒云桓義興勸卿酒桓出謝過宣武移鎭南州制街衢平直人謂王東亭曰丞相初營建康無所因承而制置紆曲方此為劣東亭曰此丞相乃所以為巧江左地促不如中國若使阡陌條暢則一覽而盡故紆餘委曲若
```

---

### 02-yanyu — 02-yanyu-103 — `non_exact_entry_opening`

- classification: `unresolved`
- confidence: `low`
- requires visual verification: `True`
- recommended action: Review the exact character/glyph and boundary context; no automatic repair is made.
- Kanripo opening key: `桓玄詣殷荆州殷在妾房晝眠`
- Kanripo opening text (source spelling): `桓玄詣殷荆州殷在妾房晝眠`
- Kanripo location: `content/processed/shishuo/chapters/chapter-02.md`; normalized line `1759`; page `<pb:KR3l0002_SBCK_001-49a>`
- Wikisource match type: `suffix`
- Wikisource page: `Page:Sibu Congkan0462-劉義慶-世説新語-3-1.djvu/106`

```text
丞相初營建康無所因承而制置紆曲方此為劣東亭曰此丞相乃所以為巧江左地促不如中國若使阡陌條暢則一覽而盡故紆餘委曲若不可測桓𤣥詣殷荆州殷在妾房晝眠左右辭不之通桓後言及此事殷云初不眠縱有此豈不以賢賢易色也桓𤣥問羊孚何以共重吳聲羊曰當以其妖而浮謝混問羊孚何以器舉瑚璉羊曰故當以為接神之器桓𤣥既簒位後御牀微陷羣臣失色侍中殷仲文進曰當由聖德淵重厚地所以不能載時人善之桓⟦{{SKchar|2593}}⟧既簒位將改置直舘問左右虎賁中郎省應在何處有人荅曰無省當時殊忤㫖問何以知無荅曰潘岳秋興
```

---

### 02-yanyu — 02-yanyu-104 — `non_exact_entry_opening`

- classification: `unresolved`
- confidence: `low`
- requires visual verification: `True`
- recommended action: Review the exact character/glyph and boundary context; no automatic repair is made.
- Kanripo opening key: `桓玄問羊孚何以共重吳聲羊`
- Kanripo opening text (source spelling): `桓玄問羊孚(郎父綏中書郎孚歴太學博士州别駕/羊氏譜曰孚字子道泰山人祖楷尚書)
(四十六卒/太尉叅軍年)何以共重吳聲羊`
- Kanripo location: `content/processed/shishuo/chapters/chapter-02.md`; normalized line `1763`; page `<pb:KR3l0002_SBCK_001-49b>`
- Wikisource match type: `suffix`
- Wikisource page: `Page:Sibu Congkan0462-劉義慶-世説新語-3-1.djvu/107`

```text
阡陌條暢則一覽而盡故紆餘委曲若不可測桓𤣥詣殷荆州殷在妾房晝眠左右辭不之通桓後言及此事殷云初不眠縱有此豈不以賢賢易色也桓𤣥問羊孚何以共重吳聲羊曰當以其妖而浮謝混問羊孚何以器舉瑚璉羊曰故當以為接神之器桓𤣥既簒位後御牀微陷羣臣失色侍中殷仲文進曰當由聖德淵重厚地所以不能載時人善之桓⟦{{SKchar|2593}}⟧既簒位將改置直舘問左右虎賁中郎省應在何處有人荅曰無省當時殊忤㫖問何以知無荅曰潘岳秋興賦敘曰余兼虎賁中郎將寓直散騎之省⟦{{SKchar|2593}}⟧咨嗟稱善謝靈運好戴曲柄笠孔𨼆士謂曰卿欲希心髙逺
```

---

### 02-yanyu — 02-yanyu-106 — `non_exact_entry_opening`

- classification: `unresolved`
- confidence: `low`
- requires visual verification: `True`
- recommended action: Review the exact character/glyph and boundary context; no automatic repair is made.
- Kanripo opening key: `桓玄既簒位後御牀微陷羣臣`
- Kanripo opening text (source spelling): `桓玄既簒位後御牀微陷羣臣`
- Kanripo location: `content/processed/shishuo/chapters/chapter-02.md`; normalized line `1768`; page `<pb:KR3l0002_SBCK_001-49b>`
- Wikisource match type: `suffix`
- Wikisource page: `Page:Sibu Congkan0462-劉義慶-世説新語-3-1.djvu/107`

```text
此事殷云初不眠縱有此豈不以賢賢易色也桓𤣥問羊孚何以共重吳聲羊曰當以其妖而浮謝混問羊孚何以器舉瑚璉羊曰故當以為接神之器桓𤣥既簒位後御牀微陷羣臣失色侍中殷仲文進曰當由聖德淵重厚地所以不能載時人善之桓⟦{{SKchar|2593}}⟧既簒位將改置直舘問左右虎賁中郎省應在何處有人荅曰無省當時殊忤㫖問何以知無荅曰潘岳秋興賦敘曰余兼虎賁中郎將寓直散騎之省⟦{{SKchar|2593}}⟧咨嗟稱善謝靈運好戴曲柄笠孔𨼆士謂曰卿欲希心髙逺何不能遺曲葢之貌謝荅曰將不畏影者未能忘懷世說新語巻上之上宋臨川王義慶撰梁劉孝標注
```

---

### 02-yanyu — 02-yanyu-107 — `non_exact_entry_opening`

- classification: `unresolved`
- confidence: `low`
- requires visual verification: `True`
- recommended action: Review the exact character/glyph and boundary context; no automatic repair is made.
- Kanripo opening key: `桓玄既簒位將改置直舘問左`
- Kanripo opening text (source spelling): `桓玄既簒位將改置直舘問左`
- Kanripo location: `content/processed/shishuo/chapters/chapter-02.md`; normalized line `1775`; page `<pb:KR3l0002_SBCK_001-50a>`
- Wikisource match type: `suffix`
- Wikisource page: `Page:Sibu Congkan0462-劉義慶-世説新語-3-1.djvu/108`

```text
混問羊孚何以器舉瑚璉羊曰故當以為接神之器桓𤣥既簒位後御牀微陷羣臣失色侍中殷仲文進曰當由聖德淵重厚地所以不能載時人善之桓⟦{{SKchar|2593}}⟧既簒位將改置直舘問左右虎賁中郎省應在何處有人荅曰無省當時殊忤㫖問何以知無荅曰潘岳秋興賦敘曰余兼虎賁中郎將寓直散騎之省⟦{{SKchar|2593}}⟧咨嗟稱善謝靈運好戴曲柄笠孔𨼆士謂曰卿欲希心髙逺何不能遺曲葢之貌謝荅曰將不畏影者未能忘懷世說新語巻上之上宋臨川王義慶撰梁劉孝標注
```

---

### 02-yanyu — `missing_kanripo_passage`

- classification: `unresolved`
- confidence: `medium`
- requires visual verification: `True`
- recommended action: Use page-level visual witnesses to determine whether this is a missing/extra passage, a glyph/character variant, or a segmentation difference. No textual repair is performed.
- Kanripo main characters: 5870
- Wikisource main characters: 5890
- length delta (Wikisource − Kanripo): 20
- sequence ratio: 0.990306
- Kanripo location: `content/processed/shishuo/chapters/chapter-02.md`; page markers `['<pb:KR3l0002_SBCK_001-17a>', '<pb:KR3l0002_SBCK_001-17b>', '<pb:KR3l0002_SBCK_001-18a>', '<pb:KR3l0002_SBCK_001-18b>', '<pb:KR3l0002_SBCK_001-19a>', '<pb:KR3l0002_SBCK_001-19b>', '<pb:KR3l0002_SBCK_001-20a>', '<pb:KR3l0002_SBCK_001-20b>', '<pb:KR3l0002_SBCK_001-21a>', '<pb:KR3l0002_SBCK_001-21b>', '<pb:KR3l0002_SBCK_001-22a>', '<pb:KR3l0002_SBCK_001-22b>', '<pb:KR3l0002_SBCK_001-23a>', '<pb:KR3l0002_SBCK_001-23b>', '<pb:KR3l0002_SBCK_001-24a>', '<pb:KR3l0002_SBCK_001-24b>', '<pb:KR3l0002_SBCK_001-25a>', '<pb:KR3l0002_SBCK_001-25b>', '<pb:KR3l0002_SBCK_001-26a>', '<pb:KR3l0002_SBCK_001-26b>', '<pb:KR3l0002_SBCK_001-27a>', '<pb:KR3l0002_SBCK_001-27b>', '<pb:KR3l0002_SBCK_001-28a>', '<pb:KR3l0002_SBCK_001-28b>', '<pb:KR3l0002_SBCK_001-29a>', '<pb:KR3l0002_SBCK_001-29b>', '<pb:KR3l0002_SBCK_001-30a>', '<pb:KR3l0002_SBCK_001-30b>', '<pb:KR3l0002_SBCK_001-31a>', '<pb:KR3l0002_SBCK_001-31b>', '<pb:KR3l0002_SBCK_001-32a>', '<pb:KR3l0002_SBCK_001-32b>', '<pb:KR3l0002_SBCK_001-33a>', '<pb:KR3l0002_SBCK_001-33b>', '<pb:KR3l0002_SBCK_001-34a>', '<pb:KR3l0002_SBCK_001-34b>', '<pb:KR3l0002_SBCK_001-35a>', '<pb:KR3l0002_SBCK_001-35b>', '<pb:KR3l0002_SBCK_001-36a>', '<pb:KR3l0002_SBCK_001-36b>', '<pb:KR3l0002_SBCK_001-37a>', '<pb:KR3l0002_SBCK_001-37b>', '<pb:KR3l0002_SBCK_001-38a>', '<pb:KR3l0002_SBCK_001-38b>', '<pb:KR3l0002_SBCK_001-39a>', '<pb:KR3l0002_SBCK_001-39b>', '<pb:KR3l0002_SBCK_001-40a>', '<pb:KR3l0002_SBCK_001-40b>', '<pb:KR3l0002_SBCK_001-41a>', '<pb:KR3l0002_SBCK_001-41b>', '<pb:KR3l0002_SBCK_001-42a>', '<pb:KR3l0002_SBCK_001-42b>', '<pb:KR3l0002_SBCK_001-43a>', '<pb:KR3l0002_SBCK_001-43b>', '<pb:KR3l0002_SBCK_001-44a>', '<pb:KR3l0002_SBCK_001-44b>', '<pb:KR3l0002_SBCK_001-45a>', '<pb:KR3l0002_SBCK_001-45b>', '<pb:KR3l0002_SBCK_001-46a>', '<pb:KR3l0002_SBCK_001-46b>', '<pb:KR3l0002_SBCK_001-47a>', '<pb:KR3l0002_SBCK_001-47b>', '<pb:KR3l0002_SBCK_001-48a>', '<pb:KR3l0002_SBCK_001-48b>', '<pb:KR3l0002_SBCK_001-49a>', '<pb:KR3l0002_SBCK_001-49b>', '<pb:KR3l0002_SBCK_001-50a>', '<pb:KR3l0002_SBCK_001-50b>']`
- Wikisource page range: `Page:Sibu Congkan0462-劉義慶-世説新語-3-1.djvu/41` through `Page:Sibu Congkan0462-劉義慶-世説新語-3-1.djvu/110` (70 pages)
- Wikisource source URL range: `https://zh.wikisource.org/wiki/Page%3ASibu%20Congkan0462-%E5%8A%89%E7%BE%A9%E6%85%B6-%E4%B8%96%E8%AA%AC%E6%96%B0%E8%AA%9E-3-1.djvu%2F41` through `https://zh.wikisource.org/wiki/Page%3ASibu%20Congkan0462-%E5%8A%89%E7%BE%A9%E6%85%B6-%E4%B8%96%E8%AA%AC%E6%96%B0%E8%AA%9E-3-1.djvu%2F110`

```text
由聖德淵重厚地所以不能載時人善之桓玄既簒位將改置直舘問左右虎賁中郎省應在何處有人荅曰無省當時殊忤㫖問何以知無荅曰潘岳秋興賦敘曰余兼虎賁中郎將寓直散騎之省玄咨嗟稱善謝靈運好戴曲柄笠孔隱士謂曰卿欲希心髙逺何不能遺曲葢之貌謝荅曰將不畏影者未能忘懷
```

```text
由聖德淵重厚地所以不能載時人善之桓⟦{{SKchar|2593}}⟧既簒位將改置直舘問左右虎賁中郎省應在何處有人荅曰無省當時殊忤㫖問何以知無荅曰潘岳秋興賦敘曰余兼虎賁中郎將寓直散騎之省⟦{{SKchar|2593}}⟧咨嗟稱善謝靈運好戴曲柄笠孔𨼆士謂曰卿欲希心髙逺何不能遺曲葢之貌謝荅曰將不畏影者未能忘懷世說新語巻上之上宋臨川王義慶撰梁劉孝標注
```

---

### 03-zhengshi — 03-zhengshi-003 — `unmatched_entry_opening`

- classification: `unresolved`
- confidence: `low`
- requires visual verification: `True`
- recommended action: Inspect the same-edition page witness and the relevant glyph/character reading before classifying as a textual variant or source gap.
- Kanripo opening key: `陳元方年十一時候袁公袁公`
- Kanripo opening text (source spelling): `陳元方年十一時(已見/陳紀)候袁公袁公`
- Kanripo location: `content/processed/shishuo/chapters/chapter-03.md`; normalized line `1808`; page `<pb:KR3l0002_SBCK_001-51b>`
- Wikisource match type: `none`
- Wikisource page: `not located`

```text
No aligned Wikisource reading.
```

---

### 03-zhengshi — 03-zhengshi-012 — `unmatched_entry_opening`

- classification: `unresolved`
- confidence: `low`
- requires visual verification: `True`
- recommended action: Inspect the same-edition page witness and the relevant glyph/character reading before classifying as a textual variant or source gap.
- Kanripo opening key: `王丞相拜揚州賓客數百人並`
- Kanripo opening text (source spelling): `王丞相拜揚州賓客數百人並`
- Kanripo location: `content/processed/shishuo/chapters/chapter-03.md`; normalized line `1884`; page `<pb:KR3l0002_SBCK_001-55a>`
- Wikisource match type: `none`
- Wikisource page: `not located`

```text
No aligned Wikisource reading.
```

---

### 03-zhengshi — 03-zhengshi-014 — `non_exact_entry_opening`

- classification: `unresolved`
- confidence: `low`
- requires visual verification: `True`
- recommended action: Review the exact character/glyph and boundary context; no automatic repair is made.
- Kanripo opening key: `丞相嘗夏月至石頭㸔庾公庾`
- Kanripo opening text (source spelling): `丞相嘗夏月至石頭㸔庾公庾`
- Kanripo location: `content/processed/shishuo/chapters/chapter-03.md`; normalized line `1895`; page `<pb:KR3l0002_SBCK_001-55b>`
- Wikisource match type: `prefix`
- Wikisource page: `Page:Sibu Congkan0462-劉義慶-世説新語-3-1.djvu/119`

```text
人前弹指云蘭闍蘭闍羣胡同笑四坐並懽陸太尉詣王丞相咨事過後輙翻異王公怪其如此後以問陸陸曰公長民短臨時不知所言既後覺其不可耳丞相嘗夏月至石頭㸔𢈔公𢈔公正料事丞相云暑可小簡之𢈔公曰公之遺事天下亦未以為允丞相末年略不復省事正封籙諾之自歎曰人言我憒憒後人當思此憒憒陶公性檢厲勤於事作荆州時敕船官悉録鋸木屑不限多少咸不⟦{{SKchar|3660}}⟧此意後正㑹值積雪始晴聽事前除雪後猶濕於是悉用木屑覆之都無所妨官用竹皆令録厚頭積之如山後桓宣武伐蜀裝船悉以作釘又云嘗發所在竹篙有一官長
```

---

### 03-zhengshi — 03-zhengshi-022 — `unmatched_entry_opening`

- classification: `unresolved`
- confidence: `low`
- requires visual verification: `True`
- recommended action: Inspect the same-edition page witness and the relevant glyph/character reading before classifying as a textual variant or source gap.
- Kanripo opening key: `殷浩始作揚州劉尹行日小欲`
- Kanripo opening text (source spelling): `殷浩始作揚州(識濮陽相父羡光禄勲浩少有重名/浩别傳曰浩字淵源陳郡長平人祖)
(弟何充等相尋薨太宗以撫軍輔政徵浩為揚州從/仕至揚州刺史中軍將軍中興書曰建元初庾亮兄)
(也/民譽)劉尹行日小欲`
- Kanripo location: `content/processed/shishuo/chapters/chapter-03.md`; normalized line `1944`; page `<pb:KR3l0002_SBCK_001-57b>`
- Wikisource match type: `none`
- Wikisource page: `not located`

```text
No aligned Wikisource reading.
```

---

### 03-zhengshi — `major_length_difference`

- classification: `structural_difference`
- confidence: `medium`
- requires visual verification: `True`
- recommended action: Use page-level visual witnesses to determine whether this is a missing/extra passage, a glyph/character variant, or a segmentation difference. No textual repair is performed.
- Kanripo main characters: 1509
- Wikisource main characters: 1541
- length delta (Wikisource − Kanripo): 32
- sequence ratio: 0.982295
- Kanripo location: `content/processed/shishuo/chapters/chapter-03.md`; page markers `['<pb:KR3l0002_SBCK_001-51b>', '<pb:KR3l0002_SBCK_001-52a>', '<pb:KR3l0002_SBCK_001-52b>', '<pb:KR3l0002_SBCK_001-53a>', '<pb:KR3l0002_SBCK_001-53b>', '<pb:KR3l0002_SBCK_001-54a>', '<pb:KR3l0002_SBCK_001-54b>', '<pb:KR3l0002_SBCK_001-55a>', '<pb:KR3l0002_SBCK_001-55b>', '<pb:KR3l0002_SBCK_001-56a>', '<pb:KR3l0002_SBCK_001-56b>', '<pb:KR3l0002_SBCK_001-57a>', '<pb:KR3l0002_SBCK_001-57b>', '<pb:KR3l0002_SBCK_001-58a>', '<pb:KR3l0002_SBCK_001-58b>']`
- Wikisource page range: `Page:Sibu Congkan0462-劉義慶-世説新語-3-1.djvu/110` through `Page:Sibu Congkan0462-劉義慶-世説新語-3-1.djvu/125` (16 pages)
- Wikisource source URL range: `https://zh.wikisource.org/wiki/Page%3ASibu%20Congkan0462-%E5%8A%89%E7%BE%A9%E6%85%B6-%E4%B8%96%E8%AA%AC%E6%96%B0%E8%AA%9E-3-1.djvu%2F110` through `https://zh.wikisource.org/wiki/Page%3ASibu%20Congkan0462-%E5%8A%89%E7%BE%A9%E6%85%B6-%E4%B8%96%E8%AA%AC%E6%96%B0%E8%AA%9E-3-1.djvu%2F125`

```text
竹皆令録厚頭積之如山後桓宣武伐蜀裝船悉以作釘又云嘗發所在竹篙有一官長連根取之仍當足乃超兩階用之何驃騎作㑹稽虞存弟謇作郡主簿以何見客勞損欲白斷常客使家人節量擇可通者作白事成以見存存時為何上佐正與謇共食語云白事甚好待我食畢作教食竟取筆題白事後云若得門庭長如郭林宗者當如所白汝何處得此人謇於是止王劉與林公共㸔何驃騎驃騎㸔文書不顧之王謂何曰我今故與林公來相㸔望卿擺撥常務應對玄言那得方低頭㸔此邪何曰我不㸔此卿等何以得存諸人以為佳桓公在荆州全欲以徳被江漢恥以威刑肅物令史受杖正從朱衣上過桓式年少從外來云向從閣下過見令史受杖上捎雲根下拂地足意譏不著桓公云我猶患其重簡文為相事動經年然後得過桓公甚患其遲常加勸勉太宗曰一日萬幾那得速山遐去東陽王長史就簡文索東陽云承藉猛政故可以和靜致治殷浩始作揚州
```

```text
竹皆令録厚頭積之如山後桓宣武伐蜀裝船悉以作釘又云嘗發所在竹篙有一官長連根取之仍當足乃超兩階用之何驃騎作㑹稽虞存弟謇作郡主簿以何見客勞損欲白斷常客使家人節量擇可通者作白事成以見存存時為何上佐正與謇共食語云白事甚好待我食畢作教食竟取筆題白事後云⟦{{SKchar2|590}}⟧得門庭長如郭林宗者當如所白汝何處得此人謇於是止王劉與林公共㸔何驃騎驃騎㸔文書不顧之王謂何曰我今故與林公來相㸔望卿擺撥常務應對𤣥言那得方低頭㸔此邪何曰我不㸔此卿等何以得存諸人以為佳桓公在荆州全欲以徳被江漢恥以威刑肅物令史受杖正從朱衣上過桓式年少從外來云向從閣下過見令史受杖上捎雲根下拂地足意譏不著桓公云我猶患其重簡文為相事動經年然後得過桓公甚患其遲常加勸勉太宗曰一日萬幾那得速山遐去東陽王長史就簡文索東陽云承
```

---

### 04-wenxue — 04-wenxue-001 — `unmatched_entry_opening`

- classification: `unresolved`
- confidence: `low`
- requires visual verification: `True`
- recommended action: Inspect the same-edition page witness and the relevant glyph/character reading before classifying as a textual variant or source gap.
- Kanripo opening key: `鄭玄在馬融門下`
- Kanripo opening text (source spelling): `鄭玄在馬融門下(人少而好問學無常師大将軍鄧/融自敘曰融字季長右扶風茂陵)
`
- Kanripo location: `content/processed/shishuo/chapters/chapter-04.md`; normalized line `1969`; page `<pb:KR3l0002_SBCK_001-58b>`
- Wikisource match type: `none`
- Wikisource page: `not located`

```text
No aligned Wikisource reading.
```

---

### 04-wenxue — 04-wenxue-002 — `unmatched_entry_opening`

- classification: `unresolved`
- confidence: `low`
- requires visual verification: `True`
- recommended action: Inspect the same-edition page witness and the relevant glyph/character reading before classifying as a textual variant or source gap.
- Kanripo opening key: `鄭玄欲注春秋傳尚未成時行`
- Kanripo opening text (source spelling): `鄭玄欲注春秋傳尚未成時行`
- Kanripo location: `content/processed/shishuo/chapters/chapter-04.md`; normalized line `1990`; page `<pb:KR3l0002_SBCK_001-59b>`
- Wikisource match type: `none`
- Wikisource page: `not located`

```text
No aligned Wikisource reading.
```

---

### 04-wenxue — 04-wenxue-003 — `non_exact_entry_opening`

- classification: `unresolved`
- confidence: `low`
- requires visual verification: `True`
- recommended action: Review the exact character/glyph and boundary context; no automatic repair is made.
- Kanripo opening key: `鄭玄家奴婢皆讀書嘗使一婢`
- Kanripo opening text (source spelling): `鄭玄家奴婢皆讀書嘗使一婢`
- Kanripo location: `content/processed/shishuo/chapters/chapter-04.md`; normalized line `1996`; page `<pb:KR3l0002_SBCK_001-60a>`
- Wikisource match type: `suffix`
- Wikisource page: `Page:Sibu Congkan0462-劉義慶-世説新語-3-1.djvu/128`

```text
未相識服在外車上與人說已注⟦{{SKchar|2652}}⟧意⟦{{SKchar|2593}}⟧聽之良乆多與己同⟦{{SKchar|2593}}⟧就車與語曰吾乆欲注尚未了聽君向言多與吾同今當盡以所注與君遂為服氏注鄭⟦{{SKchar|2593}}⟧家奴婢皆讀書嘗使一婢不稱㫖將撻之方自陳說⟦{{SKchar|2593}}⟧怒使人曵箸泥中須臾復有一婢來問曰胡為乎泥中荅曰薄言徃愬逢彼之怒服䖍既善春秋將為注欲叅考同異聞崔烈集門生講⟦{{SKchar|2652}}⟧遂匿姓名為烈門人賃作食每當至講時輙竊聽戸壁間既知不能踰己稍共諸生敘其短長烈聞不測何人然素聞䖍名意疑之明蚤徃及未窹便呼子慎子慎䖍不覺驚應遂相與友善鍾㑹撰四本論始畢甚欲使嵇公一
```

---

### 04-wenxue — 04-wenxue-009 — `non_exact_entry_opening`

- classification: `unresolved`
- confidence: `low`
- requires visual verification: `True`
- recommended action: Review the exact character/glyph and boundary context; no automatic repair is made.
- Kanripo opening key: `傅嘏善言虚勝荀粲談尚玄逺`
- Kanripo opening text (source spelling): `傅嘏善言虚勝(子之後也累遷河南尹尚書嘏嘗論/魏志曰嘏字蘭碩北地泥陽人傅介)
(有清理識要如論才性原本精㣲鮮能及之司隷鍾/才性同異鍾㑹集而論之傅子曰嘏既達治好正而)
(以明知交㑹/㑹年甚少嘏)荀粲談尚玄逺`
- Kanripo location: `content/processed/shishuo/chapters/chapter-04.md`; normalized line `2030`; page `<pb:KR3l0002_SBCK_001-61b>`
- Wikisource match type: `prefix`
- Wikisource page: `Page:Sibu Congkan0462-劉義慶-世説新語-3-1.djvu/131`

```text
冠詣裴徽徽問曰夫無者誠萬物之所資聖人莫肻致言而老子申之無已何邪弼曰聖人體無無又不可以訓故言必及有老荘未免於有恒訓其所不足傅嘏善言虚勝荀粲談尚⟦{{SKchar|2593}}⟧逺每至共語有爭而不相喻裴冀州釋二家之義通彼我之懷常使兩情皆得彼此俱畼何晏注老子未畢見王弼自說注老子㫖何意多所短不復得作聲但應諾諾遂不復注因作道德論中朝時有懷道之流有詣王夷甫咨疑者值王昨已語多小極不復相酬荅乃謂客曰身今少惡裴逸民亦近在此君可徃問裴成公作崇有論時人攻難之莫能折唯王夷甫來如小屈時人卽以王
```

---

### 04-wenxue — 04-wenxue-013 — `non_exact_entry_opening`

- classification: `unresolved`
- confidence: `low`
- requires visual verification: `True`
- recommended action: Review the exact character/glyph and boundary context; no automatic repair is made.
- Kanripo opening key: `諸葛厷年少不肻學問始與王`
- Kanripo opening text (source spelling): `諸葛厷年少不肻學問始與王`
- Kanripo location: `content/processed/shishuo/chapters/chapter-04.md`; normalized line `2052`; page `<pb:KR3l0002_SBCK_001-62b>`
- Wikisource match type: `suffix`
- Wikisource page: `Page:Sibu Congkan0462-劉義慶-世説新語-3-1.djvu/133`

```text
復相酬荅乃謂客曰身今少惡裴逸民亦近在此君可徃問裴成公作崇有論時人攻難之莫能折唯王夷甫來如小屈時人卽以王理難裴理還復申諸⟦{{SKchar|3575}}⟧厷年少不肻學問始與王夷甫談便已超詣王歎曰卿天才卓出若復小加研尋一無所愧厷後㸔荘老更與王語便足相抗衡衛玠總角時問樂令夢樂云是想衛曰形神所不接而夢豈是想邪樂云因也未嘗夢乘車入䑕穴擣𩐎噉鐡杵皆無想無因故也衛思因經日不得遂成病樂聞故命駕為剖析之衛即小差樂歎曰此兒胷中當必無膏肓之疾庾子嵩讀荘子開卷一尺許便放去曰了不異人意客問樂令
```

---

### 04-wenxue — 04-wenxue-041 — `non_exact_entry_opening`

- classification: `unresolved`
- confidence: `low`
- requires visual verification: `True`
- recommended action: Review the exact character/glyph and boundary context; no automatic repair is made.
- Kanripo opening key: `謝車騎在安西艱中林道人徃`
- Kanripo opening text (source spelling): `謝車騎在安西艱中(奕已見/安西謝)林道人徃`
- Kanripo location: `content/processed/shishuo/chapters/chapter-04.md`; normalized line `2248`; page `<pb:KR3l0002_SBCK_001-71b>`
- Wikisource match type: `suffix`
- Wikisource page: `Page:Sibu Congkan0462-劉義慶-世説新語-3-1.djvu/151`

```text
支道林許掾諸人共在㑹稽王齋頭支為法師許為都講支通一義四坐莫不厭心許送一難衆人莫不抃舞但共嗟詠二家之美不辯其理之所在謝車⟦{{SKchar|3853}}⟧在安西艱中林道人徃就語將夕乃⟦{{SKchar|2385}}⟧有人道上見者問云公何處來荅云今日與謝孝劇談一出來支道林初從東出住東安寺中王長史宿構精理并撰其才藻徃與支語不大當對王叙致作數百語自謂是名理竒藻支徐徐謂曰身與君别多年君義言了不長進王大慚而⟦{{SKchar|2385}}⟧殷中軍讀小品下二百籖皆是精微世之幽滯嘗欲與支道林辯之竟不得今小品猶存佛經以為祛練神明則聖人可致簡文云不知
```

---

### 04-wenxue — 04-wenxue-060 — `unmatched_entry_opening`

- classification: `unresolved`
- confidence: `low`
- requires visual verification: `True`
- recommended action: Inspect the same-edition page witness and the relevant glyph/character reading before classifying as a textual variant or source gap.
- Kanripo opening key: `殷仲堪精覈玄論人謂莫不研`
- Kanripo opening text (source spelling): `殷仲堪精覈玄論人謂莫不研`
- Kanripo location: `content/processed/shishuo/chapters/chapter-04.md`; normalized line `2365`; page `<pb:KR3l0002_SBCK_001-76b>`
- Wikisource match type: `none`
- Wikisource page: `not located`

```text
No aligned Wikisource reading.
```

---

### 04-wenxue — 04-wenxue-077 — `unmatched_entry_opening`

- classification: `unresolved`
- confidence: `low`
- requires visual verification: `True`
- recommended action: Inspect the same-edition page witness and the relevant glyph/character reading before classifying as a textual variant or source gap.
- Kanripo opening key: `庾闡始作揚都賦道温庾云温`
- Kanripo opening text (source spelling): `庾闡始作揚都賦道温庾云温`
- Kanripo location: `content/processed/shishuo/chapters/chapter-04.md`; normalized line `2482`; page `<pb:KR3l0002_SBCK_001-82a>`
- Wikisource match type: `none`
- Wikisource page: `not located`

```text
No aligned Wikisource reading.
```

---

### 04-wenxue — 04-wenxue-078 — `unmatched_entry_opening`

- classification: `unresolved`
- confidence: `low`
- requires visual verification: `True`
- recommended action: Inspect the same-edition page witness and the relevant glyph/character reading before classifying as a textual variant or source gap.
- Kanripo opening key: `孫興公作庾公誄袁羊曰見此`
- Kanripo opening text (source spelling): `孫興公作庾公誄袁羊曰見此`
- Kanripo location: `content/processed/shishuo/chapters/chapter-04.md`; normalized line `2486`; page `<pb:KR3l0002_SBCK_001-82a>`
- Wikisource match type: `none`
- Wikisource page: `not located`

```text
No aligned Wikisource reading.
```

---

### 04-wenxue — 04-wenxue-079 — `unmatched_entry_opening`

- classification: `unresolved`
- confidence: `low`
- requires visual verification: `True`
- recommended action: Inspect the same-edition page witness and the relevant glyph/character reading before classifying as a textual variant or source gap.
- Kanripo opening key: `庾仲初作揚都賦成以呈庾亮`
- Kanripo opening text (source spelling): `庾仲初作揚都賦成以呈庾亮`
- Kanripo location: `content/processed/shishuo/chapters/chapter-04.md`; normalized line `2489`; page `<pb:KR3l0002_SBCK_001-82b>`
- Wikisource match type: `none`
- Wikisource page: `not located`

```text
No aligned Wikisource reading.
```

---

### 04-wenxue — 04-wenxue-082 — `unmatched_entry_opening`

- classification: `unresolved`
- confidence: `low`
- requires visual verification: `True`
- recommended action: Inspect the same-edition page witness and the relevant glyph/character reading before classifying as a textual variant or source gap.
- Kanripo opening key: `謝太傅問主簿陸退張憑何以`
- Kanripo opening text (source spelling): `謝太傅問主簿陸退(祖凱吴丞相祖仰吏部郎父伊/陸氏譜曰退字黎民吴郡人髙)
(至光禄大夫/州主簿退仕)張憑何以`
- Kanripo location: `content/processed/shishuo/chapters/chapter-04.md`; normalized line `2505`; page `<pb:KR3l0002_SBCK_001-83a>`
- Wikisource match type: `none`
- Wikisource page: `not located`

```text
No aligned Wikisource reading.
```

---

### 04-wenxue — 04-wenxue-085 — `unmatched_entry_opening`

- classification: `unresolved`
- confidence: `low`
- requires visual verification: `True`
- recommended action: Inspect the same-edition page witness and the relevant glyph/character reading before classifying as a textual variant or source gap.
- Kanripo opening key: `簡文稱許掾云玄度五言詩可`
- Kanripo opening text (source spelling): `簡文稱許掾云玄度五言詩可`
- Kanripo location: `content/processed/shishuo/chapters/chapter-04.md`; normalized line `2518`; page `<pb:KR3l0002_SBCK_001-83b>`
- Wikisource match type: `none`
- Wikisource page: `not located`

```text
No aligned Wikisource reading.
```

---

### 04-wenxue — 04-wenxue-094 — `unmatched_entry_opening`

- classification: `unresolved`
- confidence: `low`
- requires visual verification: `True`
- recommended action: Inspect the same-edition page witness and the relevant glyph/character reading before classifying as a textual variant or source gap.
- Kanripo opening key: `袁彦伯作名士傳成見謝公公`
- Kanripo opening text (source spelling): `袁彦伯作名士傳成(為正始名士阮嗣宗嵇叔夜山/宏以夏侯太初何平叔王輔嗣)
(叔則樂彦輔王夷甫庾子嵩王安期阮千里衛叔寳/巨源向子期劉伯倫阮仲容王濬仲為竹林名士裴)
(中朝名士/謝㓜輿為)見謝公公`
- Kanripo location: `content/processed/shishuo/chapters/chapter-04.md`; normalized line `2565`; page `<pb:KR3l0002_SBCK_001-86a>`
- Wikisource match type: `none`
- Wikisource page: `not located`

```text
No aligned Wikisource reading.
```

---

### 04-wenxue — 04-wenxue-097 — `non_exact_entry_opening`

- classification: `unresolved`
- confidence: `low`
- requires visual verification: `True`
- recommended action: Review the exact character/glyph and boundary context; no automatic repair is made.
- Kanripo opening key: `袁宏始作東征賦都不道陶公`
- Kanripo opening text (source spelling): `袁宏始作東征賦都不道陶公`
- Kanripo location: `content/processed/shishuo/chapters/chapter-04.md`; normalized line `2576`; page `<pb:KR3l0002_SBCK_001-86b>`
- Wikisource match type: `suffix`
- Wikisource page: `Page:Sibu Congkan0462-劉義慶-世説新語-3-1.djvu/181`

```text
無復向一字桓宣武北征袁虎時從被責免官㑹須露布文喚⟦{{SKchar|2783}}⟧倚馬前令作手不輟筆俄得七紙殊可觀東亭在側極歎其才⟦{{SKchar|2783}}⟧虎云當令齒舌間得利⟦{{SKchar|2783}}⟧宏始作東征賦都不道陶公胡奴誘之狹室中臨以白刄曰先公勲業如是君作東征賦云何相忽略宏窘蹙無計便荅我大道公何以云無因誦曰精金百鍊在割能斷功則治人職思靖亂長沙之勲為史所讃或問顧長康君箏賦何如嵇康琴賦顧曰不賞者作後出相遺深識者亦以髙奇見貴殷仲文天才宏贍而讀書不甚廣博亮歎曰若使殷仲文讀書半⟦{{SKchar|2783}}⟧豹才不減班固羊孚作雪賛云資清以化乗氣以霏
```

---

### 04-wenxue — 04-wenxue-102 — `non_exact_entry_opening`

- classification: `unresolved`
- confidence: `low`
- requires visual verification: `True`
- recommended action: Review the exact character/glyph and boundary context; no automatic repair is made.
- Kanripo opening key: `桓玄嘗登江陵城南樓云我今`
- Kanripo opening text (source spelling): `桓玄嘗登江陵城南樓云我今`
- Kanripo location: `content/processed/shishuo/chapters/chapter-04.md`; normalized line `2605`; page `<pb:KR3l0002_SBCK_001-87b>`
- Wikisource match type: `suffix`
- Wikisource page: `Page:Sibu Congkan0462-劉義慶-世説新語-3-1.djvu/183`

```text
霏遇象能鮮即潔成輝桓𦙍遂以書扇王孝伯在京行散至其弟王睹户前問古詩中何句為最睹思未荅孝伯詠所遇無故物焉得不速老此句為佳桓𤣥嘗登江陵城南樓云我今欲為王孝伯作誄因吟嘯良乆隨而下筆一坐之間誄以之成桓⟦{{SKchar|2593}}⟧初并西夏領荆江二州二府一國于時始雪五處俱賀五版並入⟦{{SKchar|2593}}⟧在聽事上版至即荅版後皆粲然成章不相揉雜桓⟦{{SKchar|2593}}⟧下都羊孚時為兖州别駕從京來詣門牋云自頃世故睽離心事淪蕰明公啓晨光於積晦澄百流以一源桓見牋馳喚前云子道子道來何遲即用為記室叅軍孟昶為劉牢之主簿詣門謝見云羊侯
```

---

### 04-wenxue — 04-wenxue-103 — `non_exact_entry_opening`

- classification: `unresolved`
- confidence: `low`
- requires visual verification: `True`
- recommended action: Review the exact character/glyph and boundary context; no automatic repair is made.
- Kanripo opening key: `桓玄初并西夏領荆江二州二`
- Kanripo opening text (source spelling): `桓玄初并西夏領荆江二州二`
- Kanripo location: `content/processed/shishuo/chapters/chapter-04.md`; normalized line `2611`; page `<pb:KR3l0002_SBCK_001-88a>`
- Wikisource match type: `suffix`
- Wikisource page: `Page:Sibu Congkan0462-劉義慶-世説新語-3-1.djvu/184`

```text
最睹思未荅孝伯詠所遇無故物焉得不速老此句為佳桓𤣥嘗登江陵城南樓云我今欲為王孝伯作誄因吟嘯良乆隨而下筆一坐之間誄以之成桓⟦{{SKchar|2593}}⟧初并西夏領荆江二州二府一國于時始雪五處俱賀五版並入⟦{{SKchar|2593}}⟧在聽事上版至即荅版後皆粲然成章不相揉雜桓⟦{{SKchar|2593}}⟧下都羊孚時為兖州别駕從京來詣門牋云自頃世故睽離心事淪蕰明公啓晨光於積晦澄百流以一源桓見牋馳喚前云子道子道來何遲即用為記室叅軍孟昶為劉牢之主簿詣門謝見云羊侯羊侯百口賴卿宋臨川王義慶撰梁劉孝標注
```

---

### 04-wenxue — 04-wenxue-104 — `non_exact_entry_opening`

- classification: `unresolved`
- confidence: `low`
- requires visual verification: `True`
- recommended action: Review the exact character/glyph and boundary context; no automatic repair is made.
- Kanripo opening key: `桓玄下都羊孚時為兖州别駕`
- Kanripo opening text (source spelling): `桓玄下都羊孚時為兖州别駕`
- Kanripo location: `content/processed/shishuo/chapters/chapter-04.md`; normalized line `2615`; page `<pb:KR3l0002_SBCK_001-88a>`
- Wikisource match type: `suffix`
- Wikisource page: `Page:Sibu Congkan0462-劉義慶-世説新語-3-1.djvu/184`

```text
而下筆一坐之間誄以之成桓⟦{{SKchar|2593}}⟧初并西夏領荆江二州二府一國于時始雪五處俱賀五版並入⟦{{SKchar|2593}}⟧在聽事上版至即荅版後皆粲然成章不相揉雜桓⟦{{SKchar|2593}}⟧下都羊孚時為兖州别駕從京來詣門牋云自頃世故睽離心事淪蕰明公啓晨光於積晦澄百流以一源桓見牋馳喚前云子道子道來何遲即用為記室叅軍孟昶為劉牢之主簿詣門謝見云羊侯羊侯百口賴卿宋臨川王義慶撰梁劉孝標注
```

---

### 04-wenxue — `major_length_difference`

- classification: `structural_difference`
- confidence: `medium`
- requires visual verification: `True`
- recommended action: Use page-level visual witnesses to determine whether this is a missing/extra passage, a glyph/character variant, or a segmentation difference. No textual repair is performed.
- Kanripo main characters: 5819
- Wikisource main characters: 5879
- length delta (Wikisource − Kanripo): 60
- sequence ratio: 0.981364
- Kanripo location: `content/processed/shishuo/chapters/chapter-04.md`; page markers `['<pb:KR3l0002_SBCK_001-59a>', '<pb:KR3l0002_SBCK_001-59b>', '<pb:KR3l0002_SBCK_001-60a>', '<pb:KR3l0002_SBCK_001-60b>', '<pb:KR3l0002_SBCK_001-61a>', '<pb:KR3l0002_SBCK_001-61b>', '<pb:KR3l0002_SBCK_001-62a>', '<pb:KR3l0002_SBCK_001-62b>', '<pb:KR3l0002_SBCK_001-63a>', '<pb:KR3l0002_SBCK_001-63b>', '<pb:KR3l0002_SBCK_001-64a>', '<pb:KR3l0002_SBCK_001-64b>', '<pb:KR3l0002_SBCK_001-65a>', '<pb:KR3l0002_SBCK_001-65b>', '<pb:KR3l0002_SBCK_001-66a>', '<pb:KR3l0002_SBCK_001-66b>', '<pb:KR3l0002_SBCK_001-67a>', '<pb:KR3l0002_SBCK_001-67b>', '<pb:KR3l0002_SBCK_001-68a>', '<pb:KR3l0002_SBCK_001-68b>', '<pb:KR3l0002_SBCK_001-69a>', '<pb:KR3l0002_SBCK_001-69b>', '<pb:KR3l0002_SBCK_001-70a>', '<pb:KR3l0002_SBCK_001-70b>', '<pb:KR3l0002_SBCK_001-71a>', '<pb:KR3l0002_SBCK_001-71b>', '<pb:KR3l0002_SBCK_001-72a>', '<pb:KR3l0002_SBCK_001-72b>', '<pb:KR3l0002_SBCK_001-73a>', '<pb:KR3l0002_SBCK_001-73b>', '<pb:KR3l0002_SBCK_001-74a>', '<pb:KR3l0002_SBCK_001-74b>', '<pb:KR3l0002_SBCK_001-75a>', '<pb:KR3l0002_SBCK_001-75b>', '<pb:KR3l0002_SBCK_001-76a>', '<pb:KR3l0002_SBCK_001-76b>', '<pb:KR3l0002_SBCK_001-77a>', '<pb:KR3l0002_SBCK_001-77b>', '<pb:KR3l0002_SBCK_001-78a>', '<pb:KR3l0002_SBCK_001-78b>', '<pb:KR3l0002_SBCK_001-79a>', '<pb:KR3l0002_SBCK_001-79b>', '<pb:KR3l0002_SBCK_001-80a>', '<pb:KR3l0002_SBCK_001-80b>', '<pb:KR3l0002_SBCK_001-81a>', '<pb:KR3l0002_SBCK_001-81b>', '<pb:KR3l0002_SBCK_001-82a>', '<pb:KR3l0002_SBCK_001-82b>', '<pb:KR3l0002_SBCK_001-83a>', '<pb:KR3l0002_SBCK_001-83b>', '<pb:KR3l0002_SBCK_001-84a>', '<pb:KR3l0002_SBCK_001-84b>', '<pb:KR3l0002_SBCK_001-85a>', '<pb:KR3l0002_SBCK_001-85b>', '<pb:KR3l0002_SBCK_001-86a>', '<pb:KR3l0002_SBCK_001-86b>', '<pb:KR3l0002_SBCK_001-87a>', '<pb:KR3l0002_SBCK_001-87b>', '<pb:KR3l0002_SBCK_001-88a>', '<pb:KR3l0002_SBCK_001-88b>', '<pb:KR3l0002_SBCK_001-89a>']`
- Wikisource page range: `Page:Sibu Congkan0462-劉義慶-世説新語-3-1.djvu/125` through `Page:Sibu Congkan0463-劉義慶-世説新語-3-2.djvu/2` (62 pages)
- Wikisource source URL range: `https://zh.wikisource.org/wiki/Page%3ASibu%20Congkan0462-%E5%8A%89%E7%BE%A9%E6%85%B6-%E4%B8%96%E8%AA%AC%E6%96%B0%E8%AA%9E-3-1.djvu%2F125` through `https://zh.wikisource.org/wiki/Page%3ASibu%20Congkan0463-%E5%8A%89%E7%BE%A9%E6%85%B6-%E4%B8%96%E8%AA%AC%E6%96%B0%E8%AA%9E-3-2.djvu%2F2`

```text
是想邪樂云因也未嘗夢乘車入䑕穴擣&KR1366;噉鐡杵皆無想無因故也衛思因經日不得遂成病樂聞故命駕為剖析之衛即小差樂歎曰此兒胷中當必無膏肓之疾庾子嵩讀荘子開卷一尺許便放去曰了不異人意客問樂令㫖不至者樂亦不復剖析文句直以麈尾柄确几曰至不客曰至樂因又舉麈尾曰若至者那得去於是客乃悟服樂辭約而㫖達皆此類初注荘子者數十家莫能究其㫖要向秀於舊注外為解義妙析奇致大畼玄風唯秋水至樂二篇未竟而秀卒秀子㓜義遂零落然猶有别本郭象者為人薄行有儁才見秀義不傳於世遂竊以為已注乃自注秋水至樂二篇又易馬蹄一篇其餘衆篇或定㸃文句而已後秀義别本出故今有向郭二莊其義一也阮宣子有令聞太尉王夷甫見而問曰老莊與聖教同異對曰將無同太尉善其言辟之爲掾世謂三語掾衛玠嘲之曰一言可辟何假於三宣子曰茍是天下人望亦可無言而辟復何假一遂相與爲友
```

```text
是想邪樂云因也未嘗夢乘車入䑕穴擣𩐎噉鐡杵皆無想無因故也衛思因經日不得遂成病樂聞故命駕為剖析之衛即小差樂歎曰此兒胷中當必無膏肓之疾庾子嵩讀荘子開卷一尺許便放去曰了不異人意客問樂令㫖不至者樂亦不復剖析文句直以麈尾柄确几曰至不客曰至樂因又舉麈尾曰⟦{{SKchar2|590}}⟧至者那得去於是客乃悟服樂辭約而㫖達皆此⟦{{SKchar|3892}}⟧初注荘子者數十家莫能究其㫖要向秀於舊注外為⟦{{SKchar|3660}}⟧義妙析奇致大畼⟦{{SKchar|2593}}⟧風唯秋水至樂二篇未竟而秀卒秀子㓜義遂零落然猶有别本郭象者為人薄行有儁才見秀義不⟦{{SKchar|2652}}⟧於世遂竊以為已注乃自注秋水至樂二篇又易馬蹄一篇其餘衆篇或定㸃文句而已後秀義别本出故今有向郭二莊其義一也阮宣子有令聞太尉王夷甫見而問曰老莊與聖教同異對曰將無同太尉善其言辟之爲掾世謂三語掾衛玠嘲之曰一言可辟何假於三宣子曰茍是天下人
```

---

### 05-fangzheng — 05-fangzheng-019 — `unmatched_entry_opening`

- classification: `unresolved`
- confidence: `low`
- requires visual verification: `True`
- recommended action: Inspect the same-edition page witness and the relevant glyph/character reading before classifying as a textual variant or source gap.
- Kanripo opening key: `王太尉不與庾子嵩交庾卿之`
- Kanripo opening text (source spelling): `王太尉不與庾子嵩交(庾敱/王夷甫)庾卿之`
- Kanripo location: `content/processed/shishuo/chapters/chapter-05.md`; normalized line `264`; page `<pb:KR3l0002_SBCK_002-11b>`
- Wikisource match type: `none`
- Wikisource page: `not located`

```text
No aligned Wikisource reading.
```

---

### 05-fangzheng — 05-fangzheng-021 — `unmatched_entry_opening`

- classification: `unresolved`
- confidence: `low`
- requires visual verification: `True`
- recommended action: Inspect the same-edition page witness and the relevant glyph/character reading before classifying as a textual variant or source gap.
- Kanripo opening key: `阮宣子論鬼神有無者或以人`
- Kanripo opening text (source spelling): `阮宣子論鬼神有無者或以人`
- Kanripo location: `content/processed/shishuo/chapters/chapter-05.md`; normalized line `272`; page `<pb:KR3l0002_SBCK_002-12a>`
- Wikisource match type: `none`
- Wikisource page: `not located`

```text
No aligned Wikisource reading.
```

---

### 05-fangzheng — 05-fangzheng-024 — `non_exact_entry_opening`

- classification: `unresolved`
- confidence: `low`
- requires visual verification: `True`
- recommended action: Review the exact character/glyph and boundary context; no automatic repair is made.
- Kanripo opening key: `諸葛恢大女適太尉庾亮兒`
- Kanripo opening text (source spelling): `諸葛恢大女適太尉庾亮兒(邪陽都人祖誕司空父/恢别傳曰恢字道明琅)
`
- Kanripo location: `content/processed/shishuo/chapters/chapter-05.md`; normalized line `297`; page `<pb:KR3l0002_SBCK_002-13a>`
- Wikisource match type: `prefix`
- Wikisource page: `Page:Sibu Congkan0463-劉義慶-世説新語-3-2.djvu/24`

```text
侯方慨然愧歎曰我常自言勝茂弘今始知不如也王丞相初在江左欲結援吳人請㛰陸太尉對曰培塿無松栢薫蕕不同噐玩雖不才義不爲亂倫之始諸葛恢大女適太尉⟦{{SKchar|2928}}⟧亮兒次女適徐州刺史羊忱兒亮子被蘇峻害攺適江虨恢兒娶鄧攸女于時謝尚書求其小女㛰恢乃云羊鄧是世㛰江家我顧伊⟦{{SKchar|2928}}⟧家伊顧我不能復與謝裒兒㛰及恢亡遂㛰於是王右軍往謝家看新婦猶有恢之遺法威儀端詳容服光整王歎曰我在遣女裁得爾耳周叔治作晉陵太守周侯仲智徃别叔治以將别涕泗不止仲智恚之曰斯人乃婦女與人别唯啼泣便舎去周侯獨留
```

---

### 05-fangzheng — 05-fangzheng-034 — `non_exact_entry_opening`

- classification: `unresolved`
- confidence: `low`
- requires visual verification: `True`
- recommended action: Review the exact character/glyph and boundary context; no automatic repair is made.
- Kanripo opening key: `庾公臨去顧語鍾後事深以相`
- Kanripo opening text (source spelling): `庾公臨去顧語鍾後事深以相`
- Kanripo location: `content/processed/shishuo/chapters/chapter-05.md`; normalized line `372`; page `<pb:KR3l0002_SBCK_002-16b>`
- Wikisource match type: `suffix`
- Wikisource page: `Page:Sibu Congkan0463-劉義慶-世説新語-3-2.djvu/31`

```text
難而退古之道也君性亮直必不容於寇讎何不用隨時之宜而坐待其弊邪鍾曰國亂不能匡君危不能濟而各遜遁以求免吾懼董狐將執簡而進矣𢈔公臨去顧語鍾後事深以相委鍾曰棟折榱崩誰之責邪𢈔曰今日之事不容復言卿當期克復之效耳鍾曰想足下不愧荀林父耳蘇峻時孔羣在横塘爲匡術所逼王丞相保存術因衆坐戲語令術勸羣酒以釋横塘之憾羣荅曰德非孔子厄同匡人雖陽和布氣鷹化爲鳩至於識者猶憎其眼蘇子高事平王⟦{{SKchar|2928}}⟧諸公欲用孔廷尉爲丹陽亂離之後百姓彫弊孔慨然曰昔肅祖臨崩諸君親升御牀並⟦{{SKchar|3681}}⟧眷識共奉
```

---

### 05-fangzheng — 05-fangzheng-036 — `unmatched_entry_opening`

- classification: `unresolved`
- confidence: `low`
- requires visual verification: `True`
- recommended action: Inspect the same-edition page witness and the relevant glyph/character reading before classifying as a textual variant or source gap.
- Kanripo opening key: `蘇子高事平王庾諸公欲用孔`
- Kanripo opening text (source spelling): `蘇子高事平(石自破高山峻也碩峻弟也後諸公誅/靈鬼志謠徵曰明帝初有謡曰高山崩)
(散而逃追斬之/峻碩猶據石頭潰)王庾諸公欲用孔`
- Kanripo location: `content/processed/shishuo/chapters/chapter-05.md`; normalized line `388`; page `<pb:KR3l0002_SBCK_002-17b>`
- Wikisource match type: `none`
- Wikisource page: `not located`

```text
No aligned Wikisource reading.
```

---

### 05-fangzheng — 05-fangzheng-039 — `unmatched_entry_opening`

- classification: `unresolved`
- confidence: `low`
- requires visual verification: `True`
- recommended action: Inspect the same-edition page witness and the relevant glyph/character reading before classifying as a textual variant or source gap.
- Kanripo opening key: `王丞相作女伎施設牀席蔡公`
- Kanripo opening text (source spelling): `王丞相作女伎施設牀席蔡公`
- Kanripo location: `content/processed/shishuo/chapters/chapter-05.md`; normalized line `411`; page `<pb:KR3l0002_SBCK_002-18b>`
- Wikisource match type: `none`
- Wikisource page: `not located`

```text
No aligned Wikisource reading.
```

---

### 05-fangzheng — 05-fangzheng-040 — `non_exact_entry_opening`

- classification: `unresolved`
- confidence: `low`
- requires visual verification: `True`
- recommended action: Review the exact character/glyph and boundary context; no automatic repair is made.
- Kanripo opening key: `何次道庾季堅二人並爲元輔`
- Kanripo opening text (source spelling): `何次道庾季堅二人並爲元輔`
- Kanripo location: `content/processed/shishuo/chapters/chapter-05.md`; normalized line `414`; page `<pb:KR3l0002_SBCK_002-18b>`
- Wikisource match type: `suffix`
- Wikisource page: `Page:Sibu Congkan0463-劉義慶-世説新語-3-2.djvu/35`

```text
不可放乃遣人於江口奪之頥見陶公拜陶公止之頥曰梅仲真䣛明日豈可復屈邪王丞相作女𠆸施設牀席蔡公先在坐不説而去王亦不留何次道𢈔季堅二人並爲元輔成帝初崩于時嗣君未定何欲立嗣子𢈔及朝議以外寇方强嗣子沖幼乃立康帝康帝登阼會群臣謂何曰朕今所以承大業爲誰之議何荅曰陛下龍飛此是𢈔冰之功非臣之力于時用微臣之議今不覩盛明之世帝有慙色江僕射年少王丞相呼與共棊王手嘗不如兩道許而欲敵道戲試以觀之江不即下王曰君何以不行江曰恐不得爾傍有客曰此年少戲廼不惡王徐舉首曰此年
```

---

### 05-fangzheng — 05-fangzheng-042 — `unmatched_entry_opening`

- classification: `unresolved`
- confidence: `low`
- requires visual verification: `True`
- recommended action: Inspect the same-edition page witness and the relevant glyph/character reading before classifying as a textual variant or source gap.
- Kanripo opening key: `孔君平疾篤庾司空爲㑹稽省`
- Kanripo opening text (source spelling): `孔君平疾篤庾司空爲㑹稽省`
- Kanripo location: `content/processed/shishuo/chapters/chapter-05.md`; normalized line `429`; page `<pb:KR3l0002_SBCK_002-19a>`
- Wikisource match type: `none`
- Wikisource page: `not located`

```text
No aligned Wikisource reading.
```

---

### 05-fangzheng — 05-fangzheng-043 — `non_exact_entry_opening`

- classification: `unresolved`
- confidence: `low`
- requires visual verification: `True`
- recommended action: Review the exact character/glyph and boundary context; no automatic repair is made.
- Kanripo opening key: `桓大司馬詣劉尹臥不起桓彎`
- Kanripo opening text (source spelling): `桓大司馬詣劉尹臥不起桓彎`
- Kanripo location: `content/processed/shishuo/chapters/chapter-05.md`; normalized line `434`; page `<pb:KR3l0002_SBCK_002-19b>`
- Wikisource match type: `prefix`
- Wikisource page: `Page:Sibu Congkan0463-劉義慶-世説新語-3-2.djvu/37`

```text
勝孔君平疾篤𢈔司空爲㑹稽省之相問訊甚至爲之流涕⟦{{SKchar|2928}}⟧既下牀孔慨然曰大丈夫將終不問安國寧家之術廼作兒女子相問⟦{{SKchar|2928}}⟧聞回謝之請其話言桓大司馬詣劉尹臥不起⟦{{SKchar|3129}}⟧彎彈彈劉枕丸迸碎牀褥間劉作色而起曰使君如馨地寧可⟦{{SKchar|4486}}⟧戰求勝⟦{{SKchar|3129}}⟧甚有恨容後來年少多有道深公者深公謂曰黄吻年少勿爲評論宿士昔嘗與元明二帝王⟦{{SKchar|2928}}⟧二公周旋王中郎年少時江虨爲僕射領選欲擬之爲尚書郎有語王者王曰自過江來尚書郎正用第二人何得擬我江聞而止王述轉尚書令事行便拜文度曰故應讓杜許藍田云汝謂我堪此不文度曰何爲不
```

---

### 05-fangzheng — 05-fangzheng-047 — `unmatched_entry_opening`

- classification: `unresolved`
- confidence: `low`
- requires visual verification: `True`
- recommended action: Inspect the same-edition page witness and the relevant glyph/character reading before classifying as a textual variant or source gap.
- Kanripo opening key: `孫興公作庾公誄文多託寄之`
- Kanripo opening text (source spelling): `孫興公作庾公誄文多託寄之`
- Kanripo location: `content/processed/shishuo/chapters/chapter-05.md`; normalized line `451`; page `<pb:KR3l0002_SBCK_002-20a>`
- Wikisource match type: `none`
- Wikisource page: `not located`

```text
No aligned Wikisource reading.
```

---

### 05-fangzheng — 05-fangzheng-053 — `non_exact_entry_opening`

- classification: `unresolved`
- confidence: `low`
- requires visual verification: `True`
- recommended action: Review the exact character/glyph and boundary context; no automatic repair is made.
- Kanripo opening key: `王劉與桓公共至覆舟山看酒`
- Kanripo opening text (source spelling): `王劉與桓公共至覆舟山看酒`
- Kanripo location: `content/processed/shishuo/chapters/chapter-05.md`; normalized line `478`; page `<pb:KR3l0002_SBCK_002-21b>`
- Wikisource match type: `suffix`
- Wikisource page: `Page:Sibu Congkan0463-劉義慶-世説新語-3-2.djvu/41`

```text
追之既亦知時流必當逐巳乃遄疾而去至方山不相及劉尹時爲㑹稽乃嘆曰我入當泊安石渚下耳不敢復近思曠傍伊便能捉杖打人不易王劉與⟦{{SKchar|3129}}⟧公共至覆舟山看酒酣後劉牽脚加⟦{{SKchar|3129}}⟧公頸⟦{{SKchar|3129}}⟧公甚不堪舉手撥去既還王長史語劉曰伊詎可以形色加人不⟦{{SKchar|3129}}⟧公問⟦{{SKchar|3129}}⟧子野謝安石料萬石必敗何以不諫子野荅曰故當出於難犯耳⟦{{SKchar|3129}}⟧作色曰萬石撓弱凡才有何嚴顔難犯羅君章曾在人家主人令與坐上客共語荅曰相識巳多不煩復爾韓康伯病拄杖前庭消搖見諸謝皆富貴轟隱交路歎曰此復何異王莽時王文度爲⟦{{SKchar|3129}}⟧公長史時⟦{{SKchar|3129}}⟧爲兒求王女王許
```

---

### 05-fangzheng — 05-fangzheng-054 — `non_exact_entry_opening`

- classification: `unresolved`
- confidence: `low`
- requires visual verification: `True`
- recommended action: Review the exact character/glyph and boundary context; no automatic repair is made.
- Kanripo opening key: `桓公問桓子野謝安石料萬石`
- Kanripo opening text (source spelling): `桓公問桓子野謝安石料萬石`
- Kanripo location: `content/processed/shishuo/chapters/chapter-05.md`; normalized line `481`; page `<pb:KR3l0002_SBCK_002-21b>`
- Wikisource match type: `suffix`
- Wikisource page: `Page:Sibu Congkan0463-劉義慶-世説新語-3-2.djvu/41`

```text
伊便能捉杖打人不易王劉與⟦{{SKchar|3129}}⟧公共至覆舟山看酒酣後劉牽脚加⟦{{SKchar|3129}}⟧公頸⟦{{SKchar|3129}}⟧公甚不堪舉手撥去既還王長史語劉曰伊詎可以形色加人不⟦{{SKchar|3129}}⟧公問⟦{{SKchar|3129}}⟧子野謝安石料萬石必敗何以不諫子野荅曰故當出於難犯耳⟦{{SKchar|3129}}⟧作色曰萬石撓弱凡才有何嚴顔難犯羅君章曾在人家主人令與坐上客共語荅曰相識巳多不煩復爾韓康伯病拄杖前庭消搖見諸謝皆富貴轟隱交路歎曰此復何異王莽時王文度爲⟦{{SKchar|3129}}⟧公長史時⟦{{SKchar|3129}}⟧爲兒求王女王許咨藍田既還藍田愛念文度雖長大猶抱著䣛上文度因言⟦{{SKchar|3129}}⟧求已女㛰藍田大怒排文度下䣛曰惡見文度已復癡畏⟦{{SKchar|3129}}⟧
```

---

### 05-fangzheng — 05-fangzheng-057 — `unmatched_entry_opening`

- classification: `unresolved`
- confidence: `low`
- requires visual verification: `True`
- recommended action: Inspect the same-edition page witness and the relevant glyph/character reading before classifying as a textual variant or source gap.
- Kanripo opening key: `王文度爲桓公長史時桓爲兒`
- Kanripo opening text (source spelling): `王文度爲桓公長史時桓爲兒`
- Kanripo location: `content/processed/shishuo/chapters/chapter-05.md`; normalized line `494`; page `<pb:KR3l0002_SBCK_002-22a>`
- Wikisource match type: `none`
- Wikisource page: `not located`

```text
No aligned Wikisource reading.
```

---

### 05-fangzheng — 05-fangzheng-065 — `non_exact_entry_opening`

- classification: `unresolved`
- confidence: `low`
- requires visual verification: `True`
- recommended action: Review the exact character/glyph and boundary context; no automatic repair is made.
- Kanripo opening key: `張玄與王建武先不相識後遇`
- Kanripo opening text (source spelling): `張玄與王建武先不相識(安帝紀曰忱初作荆州剌/張玄巳見建武王忱也晉)
(武將軍/史後爲建)後遇`
- Kanripo location: `content/processed/shishuo/chapters/chapter-05.md`; normalized line `537`; page `<pb:KR3l0002_SBCK_002-24a>`
- Wikisource match type: `suffix`
- Wikisource page: `Page:Sibu Congkan0463-劉義慶-世説新語-3-2.djvu/46`

```text
臣不如恭忠孝亦何可以假人王爽與司馬太傅飲酒太傅醉呼王爲小子王曰亡祖長史與簡文皇帝爲布衣之交亡姑亡姊伉儷二宫何小子之有張𤣥與王建武先不相識後遇於范豫章許范令二人共語張因正坐斂衽王孰視良久不對張大失望便去范苦譬留之遂不肯住范是王之舅乃讓王曰張𤣥吳士之秀亦見遇於時而使至於此深不可解王笑曰張祖希若欲相識自應見詣范馳報張張便束帶造之遂舉觴對語賔主無愧色
```

---

### 05-fangzheng — `missing_kanripo_passage`

- classification: `unresolved`
- confidence: `medium`
- requires visual verification: `True`
- recommended action: Use page-level visual witnesses to determine whether this is a missing/extra passage, a glyph/character variant, or a segmentation difference. No textual repair is performed.
- Kanripo main characters: 4274
- Wikisource main characters: 4420
- length delta (Wikisource − Kanripo): 146
- sequence ratio: 0.970554
- Kanripo location: `content/processed/shishuo/chapters/chapter-05.md`; page markers `['<pb:KR3l0002_SBCK_002-1b>', '<pb:KR3l0002_SBCK_002-2a>', '<pb:KR3l0002_SBCK_002-2b>', '<pb:KR3l0002_SBCK_002-3a>', '<pb:KR3l0002_SBCK_002-3b>', '<pb:KR3l0002_SBCK_002-4a>', '<pb:KR3l0002_SBCK_002-4b>', '<pb:KR3l0002_SBCK_002-5a>', '<pb:KR3l0002_SBCK_002-6a>', '<pb:KR3l0002_SBCK_002-6b>', '<pb:KR3l0002_SBCK_002-7a>', '<pb:KR3l0002_SBCK_002-7b>', '<pb:KR3l0002_SBCK_002-8a>', '<pb:KR3l0002_SBCK_002-9a>', '<pb:KR3l0002_SBCK_002-9b>', '<pb:KR3l0002_SBCK_002-10a>', '<pb:KR3l0002_SBCK_002-10b>', '<pb:KR3l0002_SBCK_002-11a>', '<pb:KR3l0002_SBCK_002-11b>', '<pb:KR3l0002_SBCK_002-12a>', '<pb:KR3l0002_SBCK_002-12b>', '<pb:KR3l0002_SBCK_002-13a>', '<pb:KR3l0002_SBCK_002-13b>', '<pb:KR3l0002_SBCK_002-14a>', '<pb:KR3l0002_SBCK_002-14b>', '<pb:KR3l0002_SBCK_002-15a>', '<pb:KR3l0002_SBCK_002-15b>', '<pb:KR3l0002_SBCK_002-16a>', '<pb:KR3l0002_SBCK_002-16b>', '<pb:KR3l0002_SBCK_002-17a>', '<pb:KR3l0002_SBCK_002-17b>', '<pb:KR3l0002_SBCK_002-18a>', '<pb:KR3l0002_SBCK_002-18b>', '<pb:KR3l0002_SBCK_002-19a>', '<pb:KR3l0002_SBCK_002-19b>', '<pb:KR3l0002_SBCK_002-20a>', '<pb:KR3l0002_SBCK_002-20b>', '<pb:KR3l0002_SBCK_002-21a>', '<pb:KR3l0002_SBCK_002-21b>', '<pb:KR3l0002_SBCK_002-22a>', '<pb:KR3l0002_SBCK_002-22b>', '<pb:KR3l0002_SBCK_002-23a>', '<pb:KR3l0002_SBCK_002-23b>', '<pb:KR3l0002_SBCK_002-24a>', '<pb:KR3l0002_SBCK_002-24b>']`
- Wikisource page range: `Page:Sibu Congkan0463-劉義慶-世説新語-3-2.djvu/2` through `Page:Sibu Congkan0463-劉義慶-世説新語-3-2.djvu/47` (45 pages)
- Wikisource source URL range: `https://zh.wikisource.org/wiki/Page%3ASibu%20Congkan0463-%E5%8A%89%E7%BE%A9%E6%85%B6-%E4%B8%96%E8%AA%AC%E6%96%B0%E8%AA%9E-3-2.djvu%2F2` through `https://zh.wikisource.org/wiki/Page%3ASibu%20Congkan0463-%E5%8A%89%E7%BE%A9%E6%85%B6-%E4%B8%96%E8%AA%AC%E6%96%B0%E8%AA%9E-3-2.djvu%2F47`

```text
之它人能令踈親臣不能使親踈以此愧陛下杜預之荆州頓七里橋朝士悉祖預少賤好豪侠不爲物所許楊濟既名氏雄俊不堪不坐而去須臾和長輿來問楊右衛何在客曰向來不坐而去長輿曰必大夏門下盤馬往大夏門果大閲騎長輿抱內車共載歸坐如初杜預拜鎮南將軍朝士悉至皆在連榻坐山公大兒著短帢車中倚武帝欲見之山公不敢辭問兒兒不肯行時論乃云勝山公向雄爲河內主簿有公事不及雄而太守劉淮横怒遂與杖遣之雄後爲黄門郎劉爲侍中初不交言武帝聞之敕雄復君臣之好雄不得巳詣劉再拜曰向受詔而來而君臣之義絶何如於是即去武帝聞尚不和乃怒問雄曰我令卿復君臣之好何以猶絶雄曰古之君子進人以禮退人以禮今之君子進人若將加諸䣛退人若將墜諸淵臣於劉河內不爲戎首亦巳幸甚安復爲君臣之好武帝從之齊王冏爲大司馬輔政嵇紹爲侍中詣冏咨事冏設宰㑹召葛旟董艾等共論時冝
```

```text
之它人能令踈親臣不能使親踈以此愧陛下杜預之荆州頓七里橋朝士悉祖預少賤好豪侠不爲物所許楊濟既名氏雄俊不堪不坐而去須⟦{{SKchar|3099}}⟧和長輿來問楊右衛何在客曰向來不坐而去長輿曰必大夏門下盤馬往大夏門果大閲騎長輿抱內車共載歸坐如初杜預拜鎮南將軍朝士悉至皆在連榻坐時亦有裴叔則羊穉舒後至曰杜元凱乃復連榻坐客不坐便去杜請裴追之羊去數里住馬既而俱還杜許晉武帝時荀朂爲中書監和嶠爲令故事監令由來共車嶠性雅正常疾朂謟䛕後公車來嶠便登正向前坐不復容朂朂方更覓車然得去監令各給車自此始山公大兒著短帢車中倚武帝欲見之山公不敢辭問兒兒不肯行時論乃云勝山公向雄爲河內主簿有公事不及雄而太守劉淮横怒遂與杖遣之雄後爲黄門郎劉爲侍中初不交言武帝聞之敕雄復君臣之好雄不得巳詣劉再拜曰向受詔而來而君臣之義絶何如於是即去武帝聞尚不和乃怒問雄曰我令卿復君臣之好何以猶絶雄曰古之君子進人以禮退人以禮今之君子進人若將加諸䣛退人若
```

---

### 06-yaliang — 06-yaliang-005 — `unmatched_entry_opening`

- classification: `unresolved`
- confidence: `low`
- requires visual verification: `True`
- recommended action: Inspect the same-edition page witness and the relevant glyph/character reading before classifying as a textual variant or source gap.
- Kanripo opening key: `魏明帝於宣武埸上斷虎爪牙`
- Kanripo opening text (source spelling): `魏明帝於宣武埸上斷虎爪牙`
- Kanripo location: `content/processed/shishuo/chapters/chapter-06.md`; normalized line `580`; page `<pb:KR3l0002_SBCK_002-26a>`
- Wikisource match type: `none`
- Wikisource page: `not located`

```text
No aligned Wikisource reading.
```

---

### 06-yaliang — 06-yaliang-010 — `non_exact_entry_opening`

- classification: `unresolved`
- confidence: `low`
- requires visual verification: `True`
- recommended action: Review the exact character/glyph and boundary context; no automatic repair is made.
- Kanripo opening key: `劉慶孫在太傅府于時人士多爲所構唯庾子嵩縱`
- Kanripo opening text (source spelling): `劉慶孫在太傅府于時人士多爲所構唯庾子嵩縱`
- Kanripo location: `content/processed/shishuo/chapters/chapter-06.md`; normalized line `604`; page `<pb:KR3l0002_SBCK_002-27a>`
- Wikisource match type: `prefix`
- Wikisource page: `Page:Sibu Congkan0463-劉義慶-世説新語-3-2.djvu/52`

```text
與人圍棊馥司馬行酒遐正戲不時爲飲司馬恚因曳遐墜地遐還坐舉止如常顔色不變復戲如故王夷甫問遐當時何得顔色不異荅曰直是闇當故耳劉慶孫在太傅府于時人士多爲所構唯𢈔子嵩縱心事外無迹可間後以其性儉家富説太傅令換千萬冀其有吝於此可乗太傅於衆坐中問𢈔𢈔時頽然巳醉幘墮几上以頭就穿取徐荅云下官家故可有兩娑千萬隨公所取於是乃服後有人向𢈔道此𢈔曰可謂以小人之慮度君子之心王夷甫與裴景聲志好不同景聲惡欲取之卒不能回乃故詣王肆言極罵要王荅已欲以分謗王不爲動色徐曰白眼
```

---

### 06-yaliang — 06-yaliang-013 — `unmatched_entry_opening`

- classification: `unresolved`
- confidence: `low`
- requires visual verification: `True`
- recommended action: Inspect the same-edition page witness and the relevant glyph/character reading before classifying as a textual variant or source gap.
- Kanripo opening key: `有往來者云庾公有東下意`
- Kanripo opening text (source spelling): `有往來者云庾公有東下意`
- Kanripo location: `content/processed/shishuo/chapters/chapter-06.md`; normalized line `622`; page `<pb:KR3l0002_SBCK_002-28a>`
- Wikisource match type: `none`
- Wikisource page: `not located`

```text
No aligned Wikisource reading.
```

---

### 06-yaliang — 06-yaliang-017 — `non_exact_entry_opening`

- classification: `unresolved`
- confidence: `low`
- requires visual verification: `True`
- recommended action: Review the exact character/glyph and boundary context; no automatic repair is made.
- Kanripo opening key: `庾太尉風儀偉長不輕舉止`
- Kanripo opening text (source spelling): `庾太尉風儀偉長不輕舉止`
- Kanripo location: `content/processed/shishuo/chapters/chapter-06.md`; normalized line `644`; page `<pb:KR3l0002_SBCK_002-29a>`
- Wikisource match type: `suffix`
- Wikisource page: `Page:Sibu Congkan0463-劉義慶-世説新語-3-2.djvu/56`

```text
遇遊宴集聚略無不同嘗夜至丞相許戲二人歡極丞相便命使入巳帳眠顧至曉回轉不得快孰許上牀便咍臺大鼾丞相顧諸客曰此中亦難得眠處𢈔太尉風儀偉長不輕舉止時人皆以爲假亮有大兒數歲雅重之質便自如此人知是天性温太真嘗隱幔怛之此兒神色恬然乃徐跪曰君侯何以爲此論者謂不減亮蘇峻時遇害或云見阿恭知元規非假禇公於章安令遷太尉記室㕘軍名字巳顯而位微人未多識公東出乗估客船送故吏數人投錢唐亭住爾時吳興沈充爲縣令當送客過浙江客出亭吏驅公移牛屋下潮水至沈令起彷徨問牛屋下是何
```

---

### 06-yaliang — 06-yaliang-023 — `non_exact_entry_opening`

- classification: `unresolved`
- confidence: `low`
- requires visual verification: `True`
- recommended action: Review the exact character/glyph and boundary context; no automatic repair is made.
- Kanripo opening key: `庾太尉與蘇峻戰敗率左右十餘人乗小船西奔`
- Kanripo opening text (source spelling): `庾太尉與蘇峻戰敗率左右十餘人乗小船西奔`
- Kanripo location: `content/processed/shishuo/chapters/chapter-06.md`; normalized line `684`; page `<pb:KR3l0002_SBCK_002-31a>`
- Wikisource match type: `suffix`
- Wikisource page: `Page:Sibu Congkan0463-劉義慶-世説新語-3-2.djvu/60`

```text
丞相歷和車邊和覓蝨夷然不動周旣過反還指顧心曰此中何所有顧搏蝨如故徐應曰此中最是難測地周侯旣入語丞相曰卿州吏中有一令僕才⟦{{SKchar|2928}}⟧太尉與蘇峻戰敗率左右十餘人乗小船西奔亂兵相剝掠射誤中柂工應弦而倒舉船上咸失色分散亮不動容徐曰此手那可使箸賊衆迺安⟦{{SKchar|2928}}⟧小征西嘗出未還婦母阮是劉萬安妻與女上安陵城樓上俄頃翼歸策良馬盛輿衛阮語女聞⟦{{SKchar|2928}}⟧郎能騎我何由得見婦吿翼翼便爲於道開鹵簿盤馬始兩轉墜馬墮地意色自若宣武與簡文太宰共載密令人在輿前後鳴鼔大叫鹵簿中驚擾太宰惶怖求下輿顧
```

---

### 06-yaliang — 06-yaliang-024 — `non_exact_entry_opening`

- classification: `unresolved`
- confidence: `low`
- requires visual verification: `True`
- recommended action: Review the exact character/glyph and boundary context; no automatic repair is made.
- Kanripo opening key: `庾小征西嘗出未還婦母阮是劉萬安妻`
- Kanripo opening text (source spelling): `庾小征西嘗出未還婦母阮是劉萬安妻`
- Kanripo location: `content/processed/shishuo/chapters/chapter-06.md`; normalized line `688`; page `<pb:KR3l0002_SBCK_002-31a>`
- Wikisource match type: `suffix`
- Wikisource page: `Page:Sibu Congkan0463-劉義慶-世説新語-3-2.djvu/60`

```text
僕才⟦{{SKchar|2928}}⟧太尉與蘇峻戰敗率左右十餘人乗小船西奔亂兵相剝掠射誤中柂工應弦而倒舉船上咸失色分散亮不動容徐曰此手那可使箸賊衆迺安⟦{{SKchar|2928}}⟧小征西嘗出未還婦母阮是劉萬安妻與女上安陵城樓上俄頃翼歸策良馬盛輿衛阮語女聞⟦{{SKchar|2928}}⟧郎能騎我何由得見婦吿翼翼便爲於道開鹵簿盤馬始兩轉墜馬墮地意色自若宣武與簡文太宰共載密令人在輿前後鳴鼔大叫鹵簿中驚擾太宰惶怖求下輿顧看簡文穆然清恬宣武語人曰朝廷間故復有此賢王劭王薈共詣宣武正值收⟦{{SKchar|2928}}⟧希家薈不自安逡廵欲去劭堅坐不動待收信還得不定迺出論
```

---

### 06-yaliang — 06-yaliang-027 — `non_exact_entry_opening`

- classification: `unresolved`
- confidence: `low`
- requires visual verification: `True`
- recommended action: Review the exact character/glyph and boundary context; no automatic repair is made.
- Kanripo opening key: `桓宣武與郗超議芟夷朝臣條牒既定`
- Kanripo opening text (source spelling): `桓宣武與郗超議芟夷朝臣條牒既定`
- Kanripo location: `content/processed/shishuo/chapters/chapter-06.md`; normalized line `707`; page `<pb:KR3l0002_SBCK_002-32a>`
- Wikisource match type: `suffix`
- Wikisource page: `Page:Sibu Congkan0463-劉義慶-世説新語-3-2.djvu/62`

```text
穆然清恬宣武語人曰朝廷間故復有此賢王劭王薈共詣宣武正值收⟦{{SKchar|2928}}⟧希家薈不自安逡廵欲去劭堅坐不動待收信還得不定迺出論者以劭爲優⟦{{SKchar|3129}}⟧宣武與郗超議芟夷朝臣條牒既定其夜同宿明晨起呼謝安王坦之入擲䟽示之郗猶在帳内謝都無言王直擲還云多宣武取筆欲除郗不覺竊從帳中與宣武言謝含笑曰郗生可謂入幕賔也謝太傅盤桓東山時與孫興公諸人汎海戲風起浪涌孫王諸人色並⟦{{SKchar|3755}}⟧便唱使還太傅神情方王吟嘯不言舟人以公貌閑意説猶去不止既風轉急浪猛諸人皆諠動不坐公徐云如此將無歸衆人即承響而回於是
```

---

### 06-yaliang — 06-yaliang-029 — `non_exact_entry_opening`

- classification: `unresolved`
- confidence: `low`
- requires visual verification: `True`
- recommended action: Review the exact character/glyph and boundary context; no automatic repair is made.
- Kanripo opening key: `桓公伏甲設饌廣延朝士因此欲誅謝安王坦之`
- Kanripo opening text (source spelling): `桓公伏甲設饌廣延朝士因此欲誅謝安王坦之`
- Kanripo location: `content/processed/shishuo/chapters/chapter-06.md`; normalized line `719`; page `<pb:KR3l0002_SBCK_002-32b>`
- Wikisource match type: `suffix`
- Wikisource page: `Page:Sibu Congkan0463-劉義慶-世説新語-3-2.djvu/63`

```text
神情方王吟嘯不言舟人以公貌閑意説猶去不止既風轉急浪猛諸人皆諠動不坐公徐云如此將無歸衆人即承響而回於是審其量足以鎮安朝野⟦{{SKchar|3129}}⟧公伏甲設饌廣延朝士因此欲誅謝安王坦之王甚遽問謝曰當作何計謝神意不變謂文度曰晉阼存亡在此一行相與俱前王之恐狀轉見於色謝之寛容愈表於貌望階趨席方作洛生詠諷浩浩洪流⟦{{SKchar|3129}}⟧憚其曠逺乃趣解兵王謝舊齊名於此始判優劣謝太傅與王文度共詣郗超日旰未得前王便欲去謝曰不能爲性命忍俄頃支道林還東時賢並送於征虜亭蔡子叔前至坐近林公謝萬石後來坐小逺蔡
```

---

### 06-yaliang — 06-yaliang-035 — `non_exact_entry_opening`

- classification: `unresolved`
- confidence: `low`
- requires visual verification: `True`
- recommended action: Review the exact character/glyph and boundary context; no automatic repair is made.
- Kanripo opening key: `謝公與人圍棊俄而謝玄淮上信至`
- Kanripo opening text (source spelling): `謝公與人圍棊俄而謝玄淮上信至`
- Kanripo location: `content/processed/shishuo/chapters/chapter-06.md`; normalized line `756`; page `<pb:KR3l0002_SBCK_002-34a>`
- Wikisource match type: `prefix`
- Wikisource page: `Page:Sibu Congkan0463-劉義慶-世説新語-3-2.djvu/66`

```text
言及此事太傅深恨在心未盡謂同舟曰謝奉故是竒士戴公從東出謝太傅往看之謝本輕戴見但與論琴書戴既無吝色而談琴書愈妙謝悠然知其量謝公與人圍棊俄而謝𤣥淮上信至看書竟黙然無言徐向局客問淮上利害答曰小兒軰大破賊意色舉止不異於常王子猷子敬曾俱坐一室上忽發火子猷遽走避不遑取屐子敬神色恬然徐喚左右扶慿而出不異平常世以此定二王神宇符堅遊䰟近境謝太傅謂子敬曰可將當軸了其此處王僧彌謝車騎共王小奴許集僧彌舉酒勸謝云奉使君一觴謝曰可爾僧彌勃然起作色曰汝故是吳興溪中釣
```

---

### 06-yaliang — `probable_one_character_shift`

- classification: `unresolved`
- confidence: `medium`
- requires visual verification: `True`
- recommended action: Use page-level visual witnesses to determine whether this is a missing/extra passage, a glyph/character variant, or a segmentation difference. No textual repair is performed.
- Kanripo main characters: 2802
- Wikisource main characters: 2802
- length delta (Wikisource − Kanripo): 0
- sequence ratio: 0.991435
- Kanripo location: `content/processed/shishuo/chapters/chapter-06.md`; page markers `['<pb:KR3l0002_SBCK_002-25a>', '<pb:KR3l0002_SBCK_002-25b>', '<pb:KR3l0002_SBCK_002-26a>', '<pb:KR3l0002_SBCK_002-26b>', '<pb:KR3l0002_SBCK_002-27a>', '<pb:KR3l0002_SBCK_002-27b>', '<pb:KR3l0002_SBCK_002-28a>', '<pb:KR3l0002_SBCK_002-28b>', '<pb:KR3l0002_SBCK_002-29a>', '<pb:KR3l0002_SBCK_002-29b>', '<pb:KR3l0002_SBCK_002-30a>', '<pb:KR3l0002_SBCK_002-30b>', '<pb:KR3l0002_SBCK_002-31a>', '<pb:KR3l0002_SBCK_002-31b>', '<pb:KR3l0002_SBCK_002-32a>', '<pb:KR3l0002_SBCK_002-32b>', '<pb:KR3l0002_SBCK_002-33a>', '<pb:KR3l0002_SBCK_002-33b>', '<pb:KR3l0002_SBCK_002-34a>', '<pb:KR3l0002_SBCK_002-34b>', '<pb:KR3l0002_SBCK_002-35a>', '<pb:KR3l0002_SBCK_002-35b>', '<pb:KR3l0002_SBCK_002-36a>']`
- Wikisource page range: `Page:Sibu Congkan0463-劉義慶-世説新語-3-2.djvu/47` through `Page:Sibu Congkan0463-劉義慶-世説新語-3-2.djvu/70` (24 pages)
- Wikisource source URL range: `https://zh.wikisource.org/wiki/Page%3ASibu%20Congkan0463-%E5%8A%89%E7%BE%A9%E6%85%B6-%E4%B8%96%E8%AA%AC%E6%96%B0%E8%AA%9E-3-2.djvu%2F47` through `https://zh.wikisource.org/wiki/Page%3ASibu%20Congkan0463-%E5%8A%89%E7%BE%A9%E6%85%B6-%E4%B8%96%E8%AA%AC%E6%96%B0%E8%AA%9E-3-2.djvu%2F70`

```text
設主人遐與人圍棊馥司馬行酒遐正戲不時爲飲司馬恚因曳遐墜地遐還坐舉止如常顔色不變復戲如故王夷甫問遐當時何得顔色不異荅曰直是闇當故耳劉慶孫在太傅府于時人士多爲所構唯庾子嵩縱心事外無迹可間後以其性儉家富説太傅令換千萬冀其有吝於此可乗太傅於衆坐中問庾庾時頽然巳醉幘墮几上以頭就穿取徐荅云下官家故可有兩娑千萬隨公所取於是乃服後有人向庾道此庾曰可謂以小人之慮度君子之心王夷甫與裴景聲志好不同景聲惡欲取之卒不能回乃故詣王肆言極罵要王荅已欲以分謗王不爲動色徐曰白眼兒遂作王夷甫長裴成公四歲不與相知時共集一處皆當時名士謂王曰裴令令望何足計王便卿裴裴曰自可全君雅志有往來者云庾公有東下意或謂王公可潜稍嚴以備不虞王公曰我與元規雖俱王臣本懐布衣之好若其欲來吾角巾徑還烏衣何所稍嚴王丞相主簿欲檢校帳下公語主
```

```text
設主人遐與人圍棊馥司馬行酒遐正戲不時爲飲司馬恚因曳遐墜地遐還坐舉止如常顔色不變復戲如故王夷甫問遐當時何得顔色不異荅曰直是闇當故耳劉慶孫在太傅府于時人士多爲所構唯𢈔子嵩縱心事外無迹可間後以其性儉家富説太傅令換千萬冀其有吝於此可乗太傅於衆坐中問𢈔𢈔時頽然巳醉幘墮几上以頭就穿取徐荅云下官家故可有兩娑千萬隨公所取於是乃服後有人向𢈔道此𢈔曰可謂以小人之慮度君子之心王夷甫與裴景聲志好不同景聲惡欲取之卒不能回乃故詣王肆言極罵要王荅已欲以分謗王不爲動色徐曰白眼兒遂作王夷甫長裴成公四歲不與相知時共集一處皆當時名士謂王曰裴令令望何足計王便卿裴裴曰自可全君雅志有往來者云𢈔公有東下意或謂王公可潜稍嚴以備不虞王公曰我與元規雖俱王臣本懐布衣之好若其欲來吾角巾徑還烏衣何所稍嚴王丞相主簿欲檢校帳下公語主
```

---

### 07-shijian — 07-shijian-004 — `non_exact_entry_opening`

- classification: `unresolved`
- confidence: `low`
- requires visual verification: `True`
- recommended action: Review the exact character/glyph and boundary context; no automatic repair is made.
- Kanripo opening key: `晉武帝講武於宣武埸帝欲偃`
- Kanripo opening text (source spelling): `晉武帝講武於宣武埸帝欲偃`
- Kanripo location: `content/processed/shishuo/chapters/chapter-07.md`; normalized line `833`; page `<pb:KR3l0002_SBCK_002-37b>`
- Wikisource match type: `prefix`
- Wikisource page: `Page:Sibu Congkan0463-劉義慶-世説新語-3-2.djvu/73`

```text
躁博而寡要外好利而内無闗籥貴同惡異多言而妬前多言多釁妬前無親以吾觀之此三賢者皆敗德之人爾逺之猶恐罹禍況可親之邪後皆如其言晉武帝講武於宣武⟦{{SKchar|3949}}⟧帝欲偃武修文親自臨幸悉召羣臣山公謂不冝爾因與諸尚書言孫吳用兵本意遂究論舉坐無不咨嗟皆曰山少傅乃天下名言後諸王驕汰輕遘禍難於是寇盜處處蟻合郡國多以無備不能制服遂漸熾盛皆如公言時人以謂山濤不學孫吳而闇與之理會王夷甫亦歎云公闇與道合王夷甫父乂爲平北將軍有公事使行人論不得時夷甫在京師命駕見僕射羊祜尚書山濤夷甫
```

---

### 07-shijian — 07-shijian-010 — `non_exact_entry_opening`

- classification: `unresolved`
- confidence: `low`
- requires visual verification: `True`
- recommended action: Review the exact character/glyph and boundary context; no automatic repair is made.
- Kanripo opening key: `張季鷹辟齊王東曹掾在洛見`
- Kanripo opening text (source spelling): `張季鷹辟齊王東曹掾在洛見`
- Kanripo location: `content/processed/shishuo/chapters/chapter-07.md`; normalized line `877`; page `<pb:KR3l0002_SBCK_002-39b>`
- Wikisource match type: `prefix`
- Wikisource page: `Page:Sibu Congkan0463-劉義慶-世説新語-3-2.djvu/77`

```text
法當失云何得遂有天下至留侯諫廼曰賴有此耳衛玠年五歲神衿可愛祖太保曰此兒有異顧吾老不見其大耳劉越石云華彦夏識能不足彊果有餘張季鷹辟齊王東曹⟦{{SKchar|3044}}⟧在洛見秋風起因思吳中菰菜羮鱸魚膾曰人生貴得適意爾何能羈宦數千里以要名爵遂命駕便歸俄而齊王敗時人皆謂爲見機諸葛道明初過江左自名道明名亞王𢈔之下先爲臨沂令丞相謂曰明府當爲黒頭公王平子素不知眉子曰志大其量終當死塢壁間王大將軍始下楊朗苦諫不從遂爲王致力乗中鳴雲露車逕前曰聽下官鼔音一進而捷王先把其手曰事克當相用
```

---

### 07-shijian — 07-shijian-016 — `unmatched_entry_opening`

- classification: `unresolved`
- confidence: `low`
- requires visual verification: `True`
- recommended action: Inspect the same-edition page witness and the relevant glyph/character reading before classifying as a textual variant or source gap.
- Kanripo opening key: `武昌孟嘉作庾太尉州從事巳`
- Kanripo opening text (source spelling): `武昌孟嘉作庾太尉州從事巳`
- Kanripo location: `content/processed/shishuo/chapters/chapter-07.md`; normalized line `922`; page `<pb:KR3l0002_SBCK_002-41b>`
- Wikisource match type: `none`
- Wikisource page: `not located`

```text
No aligned Wikisource reading.
```

---

### 07-shijian — 07-shijian-019 — `non_exact_entry_opening`

- classification: `unresolved`
- confidence: `low`
- requires visual verification: `True`
- recommended action: Review the exact character/glyph and boundary context; no automatic repair is made.
- Kanripo opening key: `小庾臨終自表以子園客爲代`
- Kanripo opening text (source spelling): `小庾臨終自表以子園客爲代`
- Kanripo location: `content/processed/shishuo/chapters/chapter-07.md`; normalized line `943`; page `<pb:KR3l0002_SBCK_002-42b>`
- Wikisource match type: `suffix`
- Wikisource page: `Page:Sibu Congkan0463-劉義慶-世説新語-3-2.djvu/83`

```text
耳王仲祖謝仁祖劉眞長俱至丹陽墓所省殷⟦{{SKchar|3951}}⟧州殊有确然之志旣反王謝相謂曰淵源不起當如蒼生何深爲憂嘆劉曰卿諸人眞憂淵源不起邪小⟦{{SKchar|2928}}⟧臨終自表以子園客爲代朝廷慮其不從命未知所遣乃共議用⟦{{SKchar|3129}}⟧温劉尹曰使伊去必能克定西楚然恐不可復制⟦{{SKchar|3129}}⟧公將伐蜀在事諸賢咸以李勢在蜀既久承藉累葉且形據上流三峽未易可克唯劉尹云伊必能克蜀觀其蒱博不必得則不爲謝公在東山畜妓簡文曰安石必出既與人同樂亦不得不與人同憂郗超與謝玄不善符堅將問晉鼎既巳狼噬梁⟦{{SKchar|2891}}⟧又虎視淮隂矣于時朝議遣⟦{{SKchar|2593}}⟧北討人間頗有
```

---

### 07-shijian — 07-shijian-020 — `non_exact_entry_opening`

- classification: `unresolved`
- confidence: `low`
- requires visual verification: `True`
- recommended action: Review the exact character/glyph and boundary context; no automatic repair is made.
- Kanripo opening key: `桓公將伐蜀在事諸賢咸以李`
- Kanripo opening text (source spelling): `桓公將伐蜀在事諸賢咸以李`
- Kanripo location: `content/processed/shishuo/chapters/chapter-07.md`; normalized line `952`; page `<pb:KR3l0002_SBCK_002-43a>`
- Wikisource match type: `suffix`
- Wikisource page: `Page:Sibu Congkan0463-劉義慶-世説新語-3-2.djvu/84`

```text
劉曰卿諸人眞憂淵源不起邪小⟦{{SKchar|2928}}⟧臨終自表以子園客爲代朝廷慮其不從命未知所遣乃共議用⟦{{SKchar|3129}}⟧温劉尹曰使伊去必能克定西楚然恐不可復制⟦{{SKchar|3129}}⟧公將伐蜀在事諸賢咸以李勢在蜀既久承藉累葉且形據上流三峽未易可克唯劉尹云伊必能克蜀觀其蒱博不必得則不爲謝公在東山畜妓簡文曰安石必出既與人同樂亦不得不與人同憂郗超與謝玄不善符堅將問晉鼎既巳狼噬梁⟦{{SKchar|2891}}⟧又虎視淮隂矣于時朝議遣⟦{{SKchar|2593}}⟧北討人間頗有異同之論唯超曰是必濟事吾昔嘗與共在⟦{{SKchar|3129}}⟧宣武府見使才皆盡雖履屐之間亦得其任以此推之容必能立勲元功
```

---

### 07-shijian — 07-shijian-023 — `unmatched_entry_opening`

- classification: `unresolved`
- confidence: `low`
- requires visual verification: `True`
- recommended action: Inspect the same-edition page witness and the relevant glyph/character reading before classifying as a textual variant or source gap.
- Kanripo opening key: `韓康伯與謝玄亦無深好玄北`
- Kanripo opening text (source spelling): `韓康伯與謝玄亦無深好玄北`
- Kanripo location: `content/processed/shishuo/chapters/chapter-07.md`; normalized line `977`; page `<pb:KR3l0002_SBCK_002-44a>`
- Wikisource match type: `none`
- Wikisource page: `not located`

```text
No aligned Wikisource reading.
```

---

### 07-shijian — 07-shijian-024 — `non_exact_entry_opening`

- classification: `unresolved`
- confidence: `low`
- requires visual verification: `True`
- recommended action: Review the exact character/glyph and boundary context; no automatic repair is made.
- Kanripo opening key: `禇期生少時謝公甚知之恒云`
- Kanripo opening text (source spelling): `禇期生少時謝公甚知之恒云`
- Kanripo location: `content/processed/shishuo/chapters/chapter-07.md`; normalized line `982`; page `<pb:KR3l0002_SBCK_002-44b>`
- Wikisource match type: `prefix`
- Wikisource page: `Page:Sibu Congkan0463-劉義慶-世説新語-3-2.djvu/87`

```text
伯與謝⟦{{SKchar|2593}}⟧亦無深好⟦{{SKchar|2593}}⟧北征後巷議疑其不振康伯曰此人好名必能戰⟦{{SKchar|2593}}⟧聞之甚忿常於衆中厲色曰丈夫提千兵入死地以事君親故發不得復云爲名禇期生少時謝公甚知之𢘆云禇期生若不佳者僕不復相士郗超與傅瑗周旋瑗見其二子並緫髪超觀之良乆謂瑗曰小者才名皆勝然保卿家終當在兄即傅亮兄弟也王恭隨父在會稽王大自都來拜墓恭暫往墓下看之二人素善遂十餘日方還父問恭何故多日對曰與阿大語蟬連不得歸因語之曰恐阿大非爾之友終乖愛好果如其言車胤父作南平郡功曹太守王胡之避司馬無忌之難置郡于酆
```

---

### 07-shijian — `probable_one_character_shift`

- classification: `unresolved`
- confidence: `medium`
- requires visual verification: `True`
- recommended action: Use page-level visual witnesses to determine whether this is a missing/extra passage, a glyph/character variant, or a segmentation difference. No textual repair is performed.
- Kanripo main characters: 1841
- Wikisource main characters: 1841
- length delta (Wikisource − Kanripo): 0
- sequence ratio: 0.989136
- Kanripo location: `content/processed/shishuo/chapters/chapter-07.md`; page markers `['<pb:KR3l0002_SBCK_002-36b>', '<pb:KR3l0002_SBCK_002-37a>', '<pb:KR3l0002_SBCK_002-37b>', '<pb:KR3l0002_SBCK_002-38a>', '<pb:KR3l0002_SBCK_002-38b>', '<pb:KR3l0002_SBCK_002-39a>', '<pb:KR3l0002_SBCK_002-39b>', '<pb:KR3l0002_SBCK_002-40a>', '<pb:KR3l0002_SBCK_002-40b>', '<pb:KR3l0002_SBCK_002-41a>', '<pb:KR3l0002_SBCK_002-41b>', '<pb:KR3l0002_SBCK_002-42a>', '<pb:KR3l0002_SBCK_002-42b>', '<pb:KR3l0002_SBCK_002-43a>', '<pb:KR3l0002_SBCK_002-43b>', '<pb:KR3l0002_SBCK_002-44a>', '<pb:KR3l0002_SBCK_002-44b>', '<pb:KR3l0002_SBCK_002-45a>', '<pb:KR3l0002_SBCK_002-45b>', '<pb:KR3l0002_SBCK_002-46a>']`
- Wikisource page range: `Page:Sibu Congkan0463-劉義慶-世説新語-3-2.djvu/70` through `Page:Sibu Congkan0463-劉義慶-世説新語-3-2.djvu/89` (20 pages)
- Wikisource source URL range: `https://zh.wikisource.org/wiki/Page%3ASibu%20Congkan0463-%E5%8A%89%E7%BE%A9%E6%85%B6-%E4%B8%96%E8%AA%AC%E6%96%B0%E8%AA%9E-3-2.djvu%2F70` through `https://zh.wikisource.org/wiki/Page%3ASibu%20Congkan0463-%E5%8A%89%E7%BE%A9%E6%85%B6-%E4%B8%96%E8%AA%AC%E6%96%B0%E8%AA%9E-3-2.djvu%2F89`

```text
合則致隟二賢若穆則國之休此藺相如所以下廉頗也傅曰夏侯太初志大心勞能合虚譽誠所謂利口覆國之人何晏鄧颺有爲而躁博而寡要外好利而内無闗籥貴同惡異多言而妬前多言多釁妬前無親以吾觀之此三賢者皆敗德之人爾逺之猶恐罹禍況可親之邪後皆如其言晉武帝講武於宣武埸帝欲偃武修文親自臨幸悉召羣臣山公謂不冝爾因與諸尚書言孫吳用兵本意遂究論舉坐無不咨嗟皆曰山少傅乃天下名言後諸王驕汰輕遘禍難於是寇盜處處蟻合郡國多以無備不能制服遂漸熾盛皆如公言時人以謂山濤不學孫吳而闇與之理會王夷甫亦歎云公闇與道合王夷甫父乂爲平北將軍有公事使行人論不得時夷甫在京師命駕見僕射羊祜尚書山濤夷甫時總角姿才秀異叙致既快事加有理濤甚奇之既退看之不輟乃嘆曰生兒不當如王夷甫邪羊祜曰亂天下者必此子也潘陽仲見王敦小時謂曰君蜂目巳露但豺聲未振
```

```text
合則致隟二賢若穆則國之休此藺相如所以下廉頗也傅曰夏侯太初志大心勞能合虚譽誠所謂利口覆國之人何晏鄧颺有爲而躁博而寡要外好利而内無闗籥貴同惡異多言而妬前多言多釁妬前無親以吾觀之此三賢者皆敗德之人爾逺之猶恐罹禍況可親之邪後皆如其言晉武帝講武於宣武⟦{{SKchar|3949}}⟧帝欲偃武修文親自臨幸悉召羣臣山公謂不冝爾因與諸尚書言孫吳用兵本意遂究論舉坐無不咨嗟皆曰山少傅乃天下名言後諸王驕汰輕遘禍難於是寇盜處處蟻合郡國多以無備不能制服遂漸熾盛皆如公言時人以謂山濤不學孫吳而闇與之理會王夷甫亦歎云公闇與道合王夷甫父乂爲平北將軍有公事使行人論不得時夷甫在京師命駕見僕射羊祜尚書山濤夷甫時總角姿才秀異叙致既快事加有理濤甚奇之既退看之不輟乃嘆曰生兒不當如王夷甫邪羊祜曰亂天下者必此子也潘陽仲見王敦小時謂曰君蜂目巳露但豺聲未振
```

---

### 08-shangyu — 08-shangyu-015 — `non_exact_entry_opening`

- classification: `unresolved`
- confidence: `low`
- requires visual verification: `True`
- recommended action: Review the exact character/glyph and boundary context; no automatic repair is made.
- Kanripo opening key: `庾子嵩目和嶠森森如千丈松`
- Kanripo opening text (source spelling): `庾子嵩目和嶠森森如千丈松`
- Kanripo location: `content/processed/shishuo/chapters/chapter-08.md`; normalized line `1092`; page `<pb:KR3l0002_SBCK_002-49b>`
- Wikisource match type: `suffix`
- Wikisource page: `Page:Sibu Congkan0463-劉義慶-世説新語-3-2.djvu/97`

```text
曰從兄不亡矣山公舉阮咸爲吏部郎目曰淸眞寡欲萬物不能移也王戎目阮文業清倫有鑒識漢元以來未有此人武元夏目裴王曰戎尚約楷清通𢈔子嵩目和嶠森森如千丈松雖磊砢有節目施之大厦有棟梁之用王戎云太尉神姿高徹如瑶林瓊樹自然是風塵外物王汝南既除所生服遂停墓所兄子濟每來拜墓略不過叔叔亦不𠉀濟脱時過止寒温而已後𦕅試問近事荅對甚有音辭出濟意外濟極惋愕仍與語轉造精微濟先略無子姪之敬既聞其言不覺懔然心形俱肅遂留共語彌日累夜濟雖儁爽自視缺然乃喟然嘆曰家有名士三十年而不
```

---

### 08-shangyu — 08-shangyu-026 — `non_exact_entry_opening`

- classification: `unresolved`
- confidence: `low`
- requires visual verification: `True`
- recommended action: Review the exact character/glyph and boundary context; no automatic repair is made.
- Kanripo opening key: `郭子玄有儁才能言老莊庾敳`
- Kanripo opening text (source spelling): `郭子玄有儁才能言老莊庾敳`
- Kanripo location: `content/processed/shishuo/chapters/chapter-08.md`; normalized line `1181`; page `<pb:KR3l0002_SBCK_002-53b>`
- Wikisource match type: `prefix`
- Wikisource page: `Page:Sibu Congkan0463-劉義慶-世説新語-3-2.djvu/105`

```text
若披雲霧覩青天王太尉曰見裴令公精明朗然籠葢人上非凡識也若死而可作當與之同歸或云王戎語王夷甫自嘆我與樂令談未嘗不覺我言爲煩郭子玄有儁才能言老莊𢈔敳嘗稱之每曰郭子玄何必減𢈔子嵩王平子目太尉阿兄形似道而神鋒太儁太尉荅曰誠不如卿落落穆穆太傅府有三才劉慶孫長才潘陽仲大才裴景聲清才世⟦{{SKchar|3664}}⟧新語中之上宋臨川王義慶撰梁劉孝標注林下諸賢各有儁才子籍子渾噐量弘曠康子紹清逺雅正濤子簡踈通高素咸子瞻虚夷有逺志瞻弟孚爽朗多所遺秀子純悌並令淑有清流戎子萬子有大成之風苖
```

---

### 08-shangyu — 08-shangyu-030 — `non_exact_entry_opening`

- classification: `unresolved`
- confidence: `low`
- requires visual verification: `True`
- recommended action: Review the exact character/glyph and boundary context; no automatic repair is made.
- Kanripo opening key: `庾子躬有廢疾甚知名家在城`
- Kanripo opening text (source spelling): `庾子躬有廢疾甚知名家在城`
- Kanripo location: `content/processed/shishuo/chapters/chapter-08.md`; normalized line `69`; page `<pb:KR3l0002_SBCK_003-1b>`
- Wikisource match type: `suffix`
- Wikisource page: `Page:Sibu Congkan0463-劉義慶-世説新語-3-2.djvu/109`

```text
咸子瞻虚夷有逺志瞻弟孚爽朗多所遺秀子純悌並令淑有清流戎子萬子有大成之風苖而不秀唯伶子無聞凡此諸子唯瞻爲冠紹簡亦見重當世𢈔子躬有廢疾甚知名家在城西號曰城西公府王夷甫語樂令名士無多人故當容平子知王太尉云郭子玄語議如懸河冩水注而不竭司馬太傅府多名士一時儁異⟦{{SKchar|2928}}⟧文康云見子嵩在其中常自神王太傅東海王鎭許昌以王安期爲記室叅軍雅相知重敕世子毗曰夫學之所益者淺體之所安者深閑習禮度不如式瞻儀形諷味遺言不如親承音㫖王叅軍人倫之表汝其師之或曰王趙鄧三叅軍人倫之
```

---

### 08-shangyu — 08-shangyu-035 — `unmatched_entry_opening`

- classification: `unresolved`
- confidence: `low`
- requires visual verification: `True`
- recommended action: Inspect the same-edition page witness and the relevant glyph/character reading before classifying as a textual variant or source gap.
- Kanripo opening key: `庾太尉少爲王眉子所知庾過`
- Kanripo opening text (source spelling): `庾太尉少爲王眉子所知庾過`
- Kanripo location: `content/processed/shishuo/chapters/chapter-08.md`; normalized line `91`; page `<pb:KR3l0002_SBCK_003-2b>`
- Wikisource match type: `none`
- Wikisource page: `not located`

```text
No aligned Wikisource reading.
```

---

### 08-shangyu — 08-shangyu-038 — `non_exact_entry_opening`

- classification: `unresolved`
- confidence: `low`
- requires visual verification: `True`
- recommended action: Review the exact character/glyph and boundary context; no automatic repair is made.
- Kanripo opening key: `庾太尉在洛下問訊中郎中郎`
- Kanripo opening text (source spelling): `庾太尉在洛下問訊中郎(敳/庾)中郎`
- Kanripo location: `content/processed/shishuo/chapters/chapter-08.md`; normalized line `104`; page `<pb:KR3l0002_SBCK_003-3a>`
- Wikisource match type: `suffix`
- Wikisource page: `Page:Sibu Congkan0463-劉義慶-世説新語-3-2.djvu/112`

```text
子所知𢈔過江嘆王曰庇其宇下使人忘寒暑謝㓜輿曰友人王眉子清通簡畼嵇延祖𢎞雅劭長董仲道卓犖有致度王公目太尉巖巖清峙壁立千仞𢈔太尉在洛下問訊中郎中郎留之云諸人當來尋温元甫劉王喬裴叔則俱至酬酢終日𢈔公猶憶劉裴之才儁元甫之清中蔡司徒在洛見陸機兄弟住參佐廨中三間瓦屋士龍住東頭士衡住西頭士龍爲人文弱可愛士衡長七尺餘聲作鍾聲言多忼慨王長史是𢈔子躬外孫丞相目子躬云入理泓然我巳上人𢈔太尉目𢈔中郎家從談談之許𢈔公目中郎神氣融散差如得上劉琨稱祖車騎爲朗詣曰少爲
```

---

### 08-shangyu — 08-shangyu-040 — `unmatched_entry_opening`

- classification: `unresolved`
- confidence: `low`
- requires visual verification: `True`
- recommended action: Inspect the same-edition page witness and the relevant glyph/character reading before classifying as a textual variant or source gap.
- Kanripo opening key: `王長史是庾子躬外孫丞相目`
- Kanripo opening text (source spelling): `王長史是庾子躬外孫(州庾琮之女字三壽也/王氏譜曰濛父訥娶潁)丞相
目`
- Kanripo location: `content/processed/shishuo/chapters/chapter-08.md`; normalized line `115`; page `<pb:KR3l0002_SBCK_003-3b>`
- Wikisource match type: `none`
- Wikisource page: `not located`

```text
No aligned Wikisource reading.
```

---

### 08-shangyu — 08-shangyu-041 — `unmatched_entry_opening`

- classification: `unresolved`
- confidence: `low`
- requires visual verification: `True`
- recommended action: Inspect the same-edition page witness and the relevant glyph/character reading before classifying as a textual variant or source gap.
- Kanripo opening key: `庾太尉目庾中郎家從談談之`
- Kanripo opening text (source spelling): `庾太尉目庾中郎家從談談之`
- Kanripo location: `content/processed/shishuo/chapters/chapter-08.md`; normalized line `117`; page `<pb:KR3l0002_SBCK_003-3b>`
- Wikisource match type: `none`
- Wikisource page: `not located`

```text
No aligned Wikisource reading.
```

---

### 08-shangyu — 08-shangyu-042 — `non_exact_entry_opening`

- classification: `unresolved`
- confidence: `low`
- requires visual verification: `True`
- recommended action: Review the exact character/glyph and boundary context; no automatic repair is made.
- Kanripo opening key: `庾公目中郎神氣融散差如得`
- Kanripo opening text (source spelling): `庾公目中郎神氣融散差如得`
- Kanripo location: `content/processed/shishuo/chapters/chapter-08.md`; normalized line `120`; page `<pb:KR3l0002_SBCK_003-4a>`
- Wikisource match type: `suffix`
- Wikisource page: `Page:Sibu Congkan0463-劉義慶-世説新語-3-2.djvu/114`

```text
頭士龍爲人文弱可愛士衡長七尺餘聲作鍾聲言多忼慨王長史是𢈔子躬外孫丞相目子躬云入理泓然我巳上人𢈔太尉目𢈔中郎家從談談之許𢈔公目中郎神氣融散差如得上劉琨稱祖車騎爲朗詣曰少爲王敦所歎時人目⟦{{SKchar|2928}}⟧中郎善於託大長於自藏王平子邁世有儁才少所推服每聞衛玠言輒歎息絶倒王大將軍與元皇表云舒風槩簡正允作雅人自多於邃最是臣少所知拔中間夷甫澄見語卿知處明⟦{{SKchar|3561}}⟧⟦{{SKchar|2592}}⟧⟦{{SKchar|3561}}⟧⟦{{SKchar|2592}}⟧巳有令名眞副卿清論處明親踈無知之者吾常以卿言爲意殊未有得恐巳悔之臣慨然曰君以此試頃來始乃有稱之者言常人正
```

---

### 08-shangyu — 08-shangyu-044 — `non_exact_entry_opening`

- classification: `unresolved`
- confidence: `low`
- requires visual verification: `True`
- recommended action: Review the exact character/glyph and boundary context; no automatic repair is made.
- Kanripo opening key: `時人目庾中郎善於託大長於`
- Kanripo opening text (source spelling): `時人目庾中郎善於託大長於`
- Kanripo location: `content/processed/shishuo/chapters/chapter-08.md`; normalized line `131`; page `<pb:KR3l0002_SBCK_003-4b>`
- Wikisource match type: `suffix`
- Wikisource page: `Page:Sibu Congkan0463-劉義慶-世説新語-3-2.djvu/115`

```text
丞相目子躬云入理泓然我巳上人𢈔太尉目𢈔中郎家從談談之許𢈔公目中郎神氣融散差如得上劉琨稱祖車騎爲朗詣曰少爲王敦所歎時人目⟦{{SKchar|2928}}⟧中郎善於託大長於自藏王平子邁世有儁才少所推服每聞衛玠言輒歎息絶倒王大將軍與元皇表云舒風槩簡正允作雅人自多於邃最是臣少所知拔中間夷甫澄見語卿知處明⟦{{SKchar|3561}}⟧⟦{{SKchar|2592}}⟧⟦{{SKchar|3561}}⟧⟦{{SKchar|2592}}⟧巳有令名眞副卿清論處明親踈無知之者吾常以卿言爲意殊未有得恐巳悔之臣慨然曰君以此試頃來始乃有稱之者言常人正自患知之使過不知使負實周侯於荆州敗績還未得用王丞相與人書曰雅流弘
```

---

### 08-shangyu — 08-shangyu-048 — `non_exact_entry_opening`

- classification: `unresolved`
- confidence: `low`
- requires visual verification: `True`
- recommended action: Review the exact character/glyph and boundary context; no automatic repair is made.
- Kanripo opening key: `時人欲題目高坐而未能桓廷`
- Kanripo opening text (source spelling): `時人欲題目高坐而未能桓廷`
- Kanripo location: `content/processed/shishuo/chapters/chapter-08.md`; normalized line `148`; page `<pb:KR3l0002_SBCK_003-5a>`
- Wikisource match type: `prefix`
- Wikisource page: `Page:Sibu Congkan0463-劉義慶-世説新語-3-2.djvu/116`

```text
巳悔之臣慨然曰君以此試頃來始乃有稱之者言常人正自患知之使過不知使負實周侯於荆州敗績還未得用王丞相與人書曰雅流弘器何可得遺時人欲題目高坐而未能⟦{{SKchar|3129}}⟧廷尉以問周侯周侯曰可謂卓朗⟦{{SKchar|3129}}⟧公曰精神淵箸王大將軍稱其兒云其神候似欲可卞令目叔向朗朗如百間屋王敦爲大將軍鎭豫章衛玠避亂從洛投敦相見欣然談話彌日于時謝鯤爲長史敦謂鯤曰不意永嘉之中復聞正始之音阿平若在當復絶倒王平子與人書稱其兒風氣日上足散人懐胡毋彦國吐佳言如屑後進領䄂王丞相云刁玄亮之察察戴若思之巖巖卞望
```

---

### 08-shangyu — 08-shangyu-051 — `non_exact_entry_opening`

- classification: `unresolved`
- confidence: `low`
- requires visual verification: `True`
- recommended action: Review the exact character/glyph and boundary context; no automatic repair is made.
- Kanripo opening key: `王敦爲大將軍鎭豫章衛玠避`
- Kanripo opening text (source spelling): `王敦爲大將軍鎭豫章衛玠避`
- Kanripo location: `content/processed/shishuo/chapters/chapter-08.md`; normalized line `155`; page `<pb:KR3l0002_SBCK_003-5b>`
- Wikisource match type: `suffix`
- Wikisource page: `Page:Sibu Congkan0463-劉義慶-世説新語-3-2.djvu/117`

```text
可得遺時人欲題目高坐而未能⟦{{SKchar|3129}}⟧廷尉以問周侯周侯曰可謂卓朗⟦{{SKchar|3129}}⟧公曰精神淵箸王大將軍稱其兒云其神候似欲可卞令目叔向朗朗如百間屋王敦爲大將軍鎭豫章衛玠避亂從洛投敦相見欣然談話彌日于時謝鯤爲長史敦謂鯤曰不意永嘉之中復聞正始之音阿平若在當復絶倒王平子與人書稱其兒風氣日上足散人懐胡毋彦國吐佳言如屑後進領䄂王丞相云刁玄亮之察察戴若思之巖巖卞望之之峯距大將軍語右軍汝是我佳子弟當不減阮主簿世目周侯嶷如斷山王丞相招祖約夜語至曉不眠明旦有客公頭𩯭未理亦小倦客曰公
```

---

### 08-shangyu — 08-shangyu-057 — `non_exact_entry_opening`

- classification: `unresolved`
- confidence: `low`
- requires visual verification: `True`
- recommended action: Review the exact character/glyph and boundary context; no automatic repair is made.
- Kanripo opening key: `王丞相招祖約夜語至曉不眠`
- Kanripo opening text (source spelling): `王丞相招祖約夜語至曉不眠`
- Kanripo location: `content/processed/shishuo/chapters/chapter-08.md`; normalized line `176`; page `<pb:KR3l0002_SBCK_003-6b>`
- Wikisource match type: `suffix`
- Wikisource page: `Page:Sibu Congkan0463-劉義慶-世説新語-3-2.djvu/119`

```text
佳言如屑後進領䄂王丞相云刁玄亮之察察戴若思之巖巖卞望之之峯距大將軍語右軍汝是我佳子弟當不減阮主簿世目周侯嶷如斷山王丞相招祖約夜語至曉不眠明旦有客公頭𩯭未理亦小倦客曰公昨如是似失眠公曰昨與士少語遂使人忘疲王大將軍與丞相書稱楊朗曰世彦識器理致才𨼆明斷既爲國器且是楊侯淮之子位望殊爲陵遲卿亦足與之處何次道往丞相許丞相以麈尾指坐呼何共坐曰來來此是君坐丞相治楊州廨舍按行而言曰我正爲次道治此爾何少爲王公所重故屢發此嘆王丞相拜司徒而嘆曰劉王喬若過江我不
```

---

### 08-shangyu — 08-shangyu-064 — `non_exact_entry_opening`

- classification: `unresolved`
- confidence: `low`
- requires visual verification: `True`
- recommended action: Review the exact character/glyph and boundary context; no automatic repair is made.
- Kanripo opening key: `劉萬安即道眞從子庾公所謂`
- Kanripo opening text (source spelling): `劉萬安即道眞從子庾公(子躬/琮字)所謂`
- Kanripo location: `content/processed/shishuo/chapters/chapter-08.md`; normalized line `203`; page `<pb:KR3l0002_SBCK_003-7b>`
- Wikisource match type: `prefix`
- Wikisource page: `Page:Sibu Congkan0463-劉義慶-世説新語-3-2.djvu/121`

```text
發言衆人競賛之述於末坐曰主非堯舜何得事事皆是丞相甚相嘆賞世目楊朗沈審經斷蔡司徒云若使中朝不亂楊氏作公方未巳謝公云朗是大才劉萬安即道眞從子⟦{{SKchar|2928}}⟧公所謂灼然玉舉又云千人亦見百人亦見⟦{{SKchar|2928}}⟧公爲護軍屬栢廷尉覓一佳吏乃經年⟦{{SKchar|3129}}⟧後遇見徐寧而知之遂致於⟦{{SKchar|2928}}⟧公曰人所應有其不必有人所應無巳不必無眞海岱清士⟦{{SKchar|3129}}⟧茂倫云禇季野皮裏陽秋謂其裁中也何次道嘗送東人瞻望見賈寧在後輪中曰此人不死終爲諸侯上客杜弘治墓崩哀容不稱𢈔公顧謂諸客曰弘治至羸不可以致哀又曰弘治哭不可哀世稱𢈔文康爲
```

---

### 08-shangyu — 08-shangyu-065 — `non_exact_entry_opening`

- classification: `unresolved`
- confidence: `low`
- requires visual verification: `True`
- recommended action: Review the exact character/glyph and boundary context; no automatic repair is made.
- Kanripo opening key: `庾公爲護軍屬栢廷尉覓一佳`
- Kanripo opening text (source spelling): `庾公爲護軍屬栢廷尉覓一佳`
- Kanripo location: `content/processed/shishuo/chapters/chapter-08.md`; normalized line `206`; page `<pb:KR3l0002_SBCK_003-7b>`
- Wikisource match type: `suffix`
- Wikisource page: `Page:Sibu Congkan0463-劉義慶-世説新語-3-2.djvu/121`

```text
賞世目楊朗沈審經斷蔡司徒云若使中朝不亂楊氏作公方未巳謝公云朗是大才劉萬安即道眞從子⟦{{SKchar|2928}}⟧公所謂灼然玉舉又云千人亦見百人亦見⟦{{SKchar|2928}}⟧公爲護軍屬栢廷尉覓一佳吏乃經年⟦{{SKchar|3129}}⟧後遇見徐寧而知之遂致於⟦{{SKchar|2928}}⟧公曰人所應有其不必有人所應無巳不必無眞海岱清士⟦{{SKchar|3129}}⟧茂倫云禇季野皮裏陽秋謂其裁中也何次道嘗送東人瞻望見賈寧在後輪中曰此人不死終爲諸侯上客杜弘治墓崩哀容不稱𢈔公顧謂諸客曰弘治至羸不可以致哀又曰弘治哭不可哀世稱𢈔文康爲豐年玉穉恭爲荒年穀𢈔家論云是文康稱恭爲荒年穀𢈔長仁爲豐
```

---

### 08-shangyu — 08-shangyu-066 — `non_exact_entry_opening`

- classification: `unresolved`
- confidence: `low`
- requires visual verification: `True`
- recommended action: Review the exact character/glyph and boundary context; no automatic repair is made.
- Kanripo opening key: `桓茂倫云禇季野皮裏陽秋謂`
- Kanripo opening text (source spelling): `桓茂倫云禇季野皮裏陽秋謂`
- Kanripo location: `content/processed/shishuo/chapters/chapter-08.md`; normalized line `214`; page `<pb:KR3l0002_SBCK_003-8a>`
- Wikisource match type: `suffix`
- Wikisource page: `Page:Sibu Congkan0463-劉義慶-世説新語-3-2.djvu/122`

```text
人亦見百人亦見⟦{{SKchar|2928}}⟧公爲護軍屬栢廷尉覓一佳吏乃經年⟦{{SKchar|3129}}⟧後遇見徐寧而知之遂致於⟦{{SKchar|2928}}⟧公曰人所應有其不必有人所應無巳不必無眞海岱清士⟦{{SKchar|3129}}⟧茂倫云禇季野皮裏陽秋謂其裁中也何次道嘗送東人瞻望見賈寧在後輪中曰此人不死終爲諸侯上客杜弘治墓崩哀容不稱𢈔公顧謂諸客曰弘治至羸不可以致哀又曰弘治哭不可哀世稱𢈔文康爲豐年玉穉恭爲荒年穀𢈔家論云是文康稱恭爲荒年穀𢈔長仁爲豐年玉世目杜弘治標鮮季野穆少有人目杜弘治標鮮清令盛德之風可樂詠也⟦{{SKchar|2928}}⟧公云逸少國舉故⟦{{SKchar|2928}}⟧倪爲碑文云抜萃國舉⟦{{SKchar|2928}}⟧稺恭
```

---

### 08-shangyu — 08-shangyu-068 — `non_exact_entry_opening`

- classification: `unresolved`
- confidence: `low`
- requires visual verification: `True`
- recommended action: Review the exact character/glyph and boundary context; no automatic repair is made.
- Kanripo opening key: `杜弘治墓崩哀容不稱庾公顧`
- Kanripo opening text (source spelling): `杜弘治墓崩哀容不稱庾公顧`
- Kanripo location: `content/processed/shishuo/chapters/chapter-08.md`; normalized line `221`; page `<pb:KR3l0002_SBCK_003-8b>`
- Wikisource match type: `prefix`
- Wikisource page: `Page:Sibu Congkan0463-劉義慶-世説新語-3-2.djvu/123`

```text
其不必有人所應無巳不必無眞海岱清士⟦{{SKchar|3129}}⟧茂倫云禇季野皮裏陽秋謂其裁中也何次道嘗送東人瞻望見賈寧在後輪中曰此人不死終爲諸侯上客杜弘治墓崩哀容不稱𢈔公顧謂諸客曰弘治至羸不可以致哀又曰弘治哭不可哀世稱𢈔文康爲豐年玉穉恭爲荒年穀𢈔家論云是文康稱恭爲荒年穀𢈔長仁爲豐年玉世目杜弘治標鮮季野穆少有人目杜弘治標鮮清令盛德之風可樂詠也⟦{{SKchar|2928}}⟧公云逸少國舉故⟦{{SKchar|2928}}⟧倪爲碑文云抜萃國舉⟦{{SKchar|2928}}⟧稺恭與⟦{{SKchar|3129}}⟧温書稱劉道生日夕在事大小殊快義懐通樂既佳且足作友正實良器推此與君同濟艱不者也王藍
```

---

### 08-shangyu — 08-shangyu-069 — `non_exact_entry_opening`

- classification: `unresolved`
- confidence: `low`
- requires visual verification: `True`
- recommended action: Review the exact character/glyph and boundary context; no automatic repair is made.
- Kanripo opening key: `世稱庾文康爲豐年玉穉恭爲`
- Kanripo opening text (source spelling): `世稱庾文康爲豐年玉穉恭爲`
- Kanripo location: `content/processed/shishuo/chapters/chapter-08.md`; normalized line `224`; page `<pb:KR3l0002_SBCK_003-8b>`
- Wikisource match type: `suffix`
- Wikisource page: `Page:Sibu Congkan0463-劉義慶-世説新語-3-2.djvu/123`

```text
嘗送東人瞻望見賈寧在後輪中曰此人不死終爲諸侯上客杜弘治墓崩哀容不稱𢈔公顧謂諸客曰弘治至羸不可以致哀又曰弘治哭不可哀世稱𢈔文康爲豐年玉穉恭爲荒年穀𢈔家論云是文康稱恭爲荒年穀𢈔長仁爲豐年玉世目杜弘治標鮮季野穆少有人目杜弘治標鮮清令盛德之風可樂詠也⟦{{SKchar|2928}}⟧公云逸少國舉故⟦{{SKchar|2928}}⟧倪爲碑文云抜萃國舉⟦{{SKchar|2928}}⟧稺恭與⟦{{SKchar|3129}}⟧温書稱劉道生日夕在事大小殊快義懐通樂既佳且足作友正實良器推此與君同濟艱不者也王藍田拜⟦{{SKchar|3951}}⟧州主簿請諱教云亡祖先君名播海内逺近所知内諱不出於外餘無所諱蕭中郎孫
```

---

### 08-shangyu — 08-shangyu-071 — `non_exact_entry_opening`

- classification: `unresolved`
- confidence: `low`
- requires visual verification: `True`
- recommended action: Review the exact character/glyph and boundary context; no automatic repair is made.
- Kanripo opening key: `有人目杜弘治標鮮清令盛德`
- Kanripo opening text (source spelling): `有人目杜弘治標鮮清令盛德`
- Kanripo location: `content/processed/shishuo/chapters/chapter-08.md`; normalized line `228`; page `<pb:KR3l0002_SBCK_003-8b>`
- Wikisource match type: `suffix`
- Wikisource page: `Page:Sibu Congkan0463-劉義慶-世説新語-3-2.djvu/123`

```text
不可以致哀又曰弘治哭不可哀世稱𢈔文康爲豐年玉穉恭爲荒年穀𢈔家論云是文康稱恭爲荒年穀𢈔長仁爲豐年玉世目杜弘治標鮮季野穆少有人目杜弘治標鮮清令盛德之風可樂詠也⟦{{SKchar|2928}}⟧公云逸少國舉故⟦{{SKchar|2928}}⟧倪爲碑文云抜萃國舉⟦{{SKchar|2928}}⟧稺恭與⟦{{SKchar|3129}}⟧温書稱劉道生日夕在事大小殊快義懐通樂既佳且足作友正實良器推此與君同濟艱不者也王藍田拜⟦{{SKchar|3951}}⟧州主簿請諱教云亡祖先君名播海内逺近所知内諱不出於外餘無所諱蕭中郎孫丞公婦父劉尹在撫軍坐時擬為太常劉尹云蕭祖周不知便可作三公不自此以還無所不堪謝太傅未冠始出
```

---

### 08-shangyu — 08-shangyu-072 — `unmatched_entry_opening`

- classification: `unresolved`
- confidence: `low`
- requires visual verification: `True`
- recommended action: Inspect the same-edition page witness and the relevant glyph/character reading before classifying as a textual variant or source gap.
- Kanripo opening key: `庾公云逸少國舉故庾倪爲碑`
- Kanripo opening text (source spelling): `庾公云逸少國舉故庾倪爲碑`
- Kanripo location: `content/processed/shishuo/chapters/chapter-08.md`; normalized line `231`; page `<pb:KR3l0002_SBCK_003-9a>`
- Wikisource match type: `none`
- Wikisource page: `not located`

```text
No aligned Wikisource reading.
```

---

### 08-shangyu — 08-shangyu-073 — `unmatched_entry_opening`

- classification: `unresolved`
- confidence: `low`
- requires visual verification: `True`
- recommended action: Inspect the same-edition page witness and the relevant glyph/character reading before classifying as a textual variant or source gap.
- Kanripo opening key: `庾稺恭與桓温書稱劉道生日`
- Kanripo opening text (source spelling): `庾稺恭與桓温書稱劉道生日`
- Kanripo location: `content/processed/shishuo/chapters/chapter-08.md`; normalized line `234`; page `<pb:KR3l0002_SBCK_003-9a>`
- Wikisource match type: `none`
- Wikisource page: `not located`

```text
No aligned Wikisource reading.
```

---

### 08-shangyu — 08-shangyu-074 — `unmatched_entry_opening`

- classification: `unresolved`
- confidence: `low`
- requires visual verification: `True`
- recommended action: Inspect the same-edition page witness and the relevant glyph/character reading before classifying as a textual variant or source gap.
- Kanripo opening key: `王藍田拜揚州主簿請諱教云`
- Kanripo opening text (source spelling): `王藍田拜揚州主簿請諱教云`
- Kanripo location: `content/processed/shishuo/chapters/chapter-08.md`; normalized line `238`; page `<pb:KR3l0002_SBCK_003-9a>`
- Wikisource match type: `none`
- Wikisource page: `not located`

```text
No aligned Wikisource reading.
```

---

### 08-shangyu — 08-shangyu-079 — `non_exact_entry_opening`

- classification: `unresolved`
- confidence: `low`
- requires visual verification: `True`
- recommended action: Review the exact character/glyph and boundary context; no automatic repair is made.
- Kanripo opening key: `桓温行經王敦墓邊過望之云`
- Kanripo opening text (source spelling): `桓温行經王敦墓邊過望之云`
- Kanripo location: `content/processed/shishuo/chapters/chapter-08.md`; normalized line `252`; page `<pb:KR3l0002_SBCK_003-10a>`
- Wikisource match type: `suffix`
- Wikisource page: `Page:Sibu Congkan0463-劉義慶-世説新語-3-2.djvu/126`

```text
後茍子問曰向客何如尊長史曰向客亹亹爲來逼人王右軍語劉尹故當共推安石劉尹曰若安石東山志立當與天下共推之謝公稱藍田掇皮皆真⟦{{SKchar|3129}}⟧温行經王敦墓邊過望之云可兒可兒殷中軍道王右軍云逸少清貴人吾於之甚至一時無所後王仲祖稱殷淵源非以長勝人處長亦勝人王司州與殷中軍語嘆云巳之府奥蚤已傾冩而見殷陳勢浩汗衆源未可得測王長史謂林公真長可謂金玉滿堂林公曰金玉滿堂復何為簡選王曰非爲簡選直致言處自寡耳王長史道江道羣人所應有乃不必有人所應無已必無會稽孔沉魏顗虞球虞存謝奉並
```

---

### 08-shangyu — 08-shangyu-084 — `unmatched_entry_opening`

- classification: `unresolved`
- confidence: `low`
- requires visual verification: `True`
- recommended action: Inspect the same-edition page witness and the relevant glyph/character reading before classifying as a textual variant or source gap.
- Kanripo opening key: `真長可謂金玉滿堂林公曰金`
- Kanripo opening text (source spelling): `真長可謂金玉滿堂林公曰金`
- Kanripo location: `content/processed/shishuo/chapters/chapter-08.md`; normalized line `261`; page `<pb:KR3l0002_SBCK_003-10a>`
- Wikisource match type: `none`
- Wikisource page: `not located`

```text
No aligned Wikisource reading.
```

---

### 08-shangyu — 08-shangyu-087 — `non_exact_entry_opening`

- classification: `unresolved`
- confidence: `low`
- requires visual verification: `True`
- recommended action: Review the exact character/glyph and boundary context; no automatic repair is made.
- Kanripo opening key: `簡文目庾赤玉省率治除謝仁`
- Kanripo opening text (source spelling): `簡文目庾赤玉省率治除謝仁`
- Kanripo location: `content/processed/shishuo/chapters/chapter-08.md`; normalized line `273`; page `<pb:KR3l0002_SBCK_003-10b>`
- Wikisource match type: `suffix`
- Wikisource page: `Page:Sibu Congkan0463-劉義慶-世説新語-3-2.djvu/128`

```text
通而自然有節王右軍道謝萬石在林澤中爲自遒上歎林公器朗神儁道祖士少風領毛骨恐没世不復見如此人道劉真長標雲柯而不扶踈簡文目𢈔赤玉省率治除謝仁祖云𢈔赤玉𦙄中無宿物殷中軍道韓太常曰康伯少自標置居然是出羣器及其發言遣辭往往有情致簡文道王懷祖才既不長於榮利又不淡直以真率少許便足對人多多許林公謂王右軍云長史作數百語無非德音如恨不苦王曰長史自不欲苦物殷中軍與人書道謝萬文理轉遒成殊不易王長史云江思悛思懷所通不翅儒域許𤣥度送母始出都人問劉尹玄度定稱所聞不劉
```

---

### 08-shangyu — 08-shangyu-093 — `non_exact_entry_opening`

- classification: `unresolved`
- confidence: `low`
- requires visual verification: `True`
- recommended action: Review the exact character/glyph and boundary context; no automatic repair is made.
- Kanripo opening key: `許玄度送母始出都人問劉尹`
- Kanripo opening text (source spelling): `許玄度送母始出都人問劉尹`
- Kanripo location: `content/processed/shishuo/chapters/chapter-08.md`; normalized line `287`; page `<pb:KR3l0002_SBCK_003-11b>`
- Wikisource match type: `suffix`
- Wikisource page: `Page:Sibu Congkan0463-劉義慶-世説新語-3-2.djvu/130`

```text
右軍云長史作數百語無非德音如恨不苦王曰長史自不欲苦物殷中軍與人書道謝萬文理轉遒成殊不易王長史云江思悛思懷所通不翅儒域許𤣥度送母始出都人問劉尹玄度定稱所聞不劉曰才情過於所聞阮光禄云王家有三年少右軍安期長豫謝公道豫章若遇七賢必自把臂入林王長史歎林公尋微之功不減輔嗣殷淵源在墓所㡬十年于時朝野以擬管葛起不起以卜江左興亡殷中軍道右軍清鑒貴要謝太傅爲⟦{{SKchar|3129}}⟧公司馬⟦{{SKchar|3129}}⟧詣謝值謝梳頭⟦{{SKchar|3755}}⟧取衣幘⟦{{SKchar|3129}}⟧公云何煩此因下共語至暝既去謂左右曰頗曾見如此人不謝公作宣武司馬屬門生
```

---

### 08-shangyu — 08-shangyu-099 — `unmatched_entry_opening`

- classification: `unresolved`
- confidence: `low`
- requires visual verification: `True`
- recommended action: Inspect the same-edition page witness and the relevant glyph/character reading before classifying as a textual variant or source gap.
- Kanripo opening key: `謝太傅爲桓公司馬桓詣謝值`
- Kanripo opening text (source spelling): `謝太傅爲桓公司馬(敷文析理自娛桓温在西蕃欽/續晉陽秋曰初安優遊山水以)
(夷志存匡濟年四十起家應務也/其盛名諷朝廷請爲司馬以世道未)桓詣謝值`
- Kanripo location: `content/processed/shishuo/chapters/chapter-08.md`; normalized line `303`; page `<pb:KR3l0002_SBCK_003-12a>`
- Wikisource match type: `none`
- Wikisource page: `not located`

```text
No aligned Wikisource reading.
```

---

### 08-shangyu — 08-shangyu-101 — `non_exact_entry_opening`

- classification: `unresolved`
- confidence: `low`
- requires visual verification: `True`
- recommended action: Review the exact character/glyph and boundary context; no automatic repair is made.
- Kanripo opening key: `桓宣武表云謝尚神懷挺率少`
- Kanripo opening text (source spelling): `桓宣武表云謝尚神懷挺率少`
- Kanripo location: `content/processed/shishuo/chapters/chapter-08.md`; normalized line `312`; page `<pb:KR3l0002_SBCK_003-12b>`
- Wikisource match type: `suffix`
- Wikisource page: `Page:Sibu Congkan0463-劉義慶-世説新語-3-2.djvu/132`

```text
門生數十人於田曹中郎趙恱子恱子以告宣武宣武宣武云且爲用半趙俄而悉用之曰昔安石在東山搢紳敦逼恐不豫人事況今自鄉選反違之邪⟦{{SKchar|3129}}⟧宣武表云謝尚神懷挺率少致民譽世目謝尚爲令逹阮遥集云清畼似逹或云尚自然令上⟦{{SKchar|3129}}⟧大司馬病謝公往省病從東門入⟦{{SKchar|3129}}⟧公遥望嘆曰吾門中久不見如此人簡文目敬豫爲朗豫孫興公爲𢈔公叅軍共遊白石山衛君長在坐孫曰此子神情都不關山水而能作文𢈔公曰衛風韻雖不及卿諸人傾倒處亦不近孫遂沐浴此言王右軍目陳玄伯壘塊有正骨王長史云劉尹知我勝我自知王劉聽林公講
```

---

### 08-shangyu — 08-shangyu-103 — `non_exact_entry_opening`

- classification: `unresolved`
- confidence: `low`
- requires visual verification: `True`
- recommended action: Review the exact character/glyph and boundary context; no automatic repair is made.
- Kanripo opening key: `桓大司馬病謝公往省病從東`
- Kanripo opening text (source spelling): `桓大司馬病謝公往省病從東`
- Kanripo location: `content/processed/shishuo/chapters/chapter-08.md`; normalized line `317`; page `<pb:KR3l0002_SBCK_003-12b>`
- Wikisource match type: `suffix`
- Wikisource page: `Page:Sibu Congkan0463-劉義慶-世説新語-3-2.djvu/132`

```text
石在東山搢紳敦逼恐不豫人事況今自鄉選反違之邪⟦{{SKchar|3129}}⟧宣武表云謝尚神懷挺率少致民譽世目謝尚爲令逹阮遥集云清畼似逹或云尚自然令上⟦{{SKchar|3129}}⟧大司馬病謝公往省病從東門入⟦{{SKchar|3129}}⟧公遥望嘆曰吾門中久不見如此人簡文目敬豫爲朗豫孫興公爲𢈔公叅軍共遊白石山衛君長在坐孫曰此子神情都不關山水而能作文𢈔公曰衛風韻雖不及卿諸人傾倒處亦不近孫遂沐浴此言王右軍目陳玄伯壘塊有正骨王長史云劉尹知我勝我自知王劉聽林公講王語劉曰向高坐者故是凶物復更聽王又曰自是鉢釪後王何人也許玄度言琴賦所謂非至
```

---

### 08-shangyu — 08-shangyu-105 — `unmatched_entry_opening`

- classification: `unresolved`
- confidence: `low`
- requires visual verification: `True`
- recommended action: Inspect the same-edition page witness and the relevant glyph/character reading before classifying as a textual variant or source gap.
- Kanripo opening key: `孫興公爲庾公叅軍共遊白石`
- Kanripo opening text (source spelling): `孫興公爲庾公叅軍共遊白石`
- Kanripo location: `content/processed/shishuo/chapters/chapter-08.md`; normalized line `321`; page `<pb:KR3l0002_SBCK_003-13a>`
- Wikisource match type: `none`
- Wikisource page: `not located`

```text
No aligned Wikisource reading.
```

---

### 08-shangyu — 08-shangyu-114 — `non_exact_entry_opening`

- classification: `unresolved`
- confidence: `low`
- requires visual verification: `True`
- recommended action: Review the exact character/glyph and boundary context; no automatic repair is made.
- Kanripo opening key: `謝公云劉尹語審細桓公語嘉`
- Kanripo opening text (source spelling): `謝公云劉尹語審細(猶淵鏡言必珠玉/孫綽爲惔諫叙曰神)
桓公語嘉`
- Kanripo location: `content/processed/shishuo/chapters/chapter-08.md`; normalized line `349`; page `<pb:KR3l0002_SBCK_003-14a>`
- Wikisource match type: `prefix`
- Wikisource page: `Page:Sibu Congkan0463-劉義慶-世説新語-3-2.djvu/135`

```text
陳初法汰北來未知名王領軍供養之每與周旋行來往名勝許輒與俱不得汰便停車不行因此名遂重王長史與大司馬書道淵源識致安處足副時談謝公云劉尹語審細⟦{{SKchar|3129}}⟧公語嘉賔阿源有德有言向使作令僕足以儀刑百揆朝廷用違其才耳簡文語嘉賔劉尹語末後亦小異回復其言亦乃無過孫興公許𤣥度共在白樓亭共商略先往名達林公既非所關聽訖云二賢故自有才情王右軍道東陽我家阿林章清太出王長史與劉尹書道淵源觸事長易謝中郎云王脩載樂託之性出自門風林公云王敬仁是超悟人劉尹先推謝鎮西謝後雅重劉曰昔嘗
```

---

### 08-shangyu — 08-shangyu-115 — `non_exact_entry_opening`

- classification: `unresolved`
- confidence: `low`
- requires visual verification: `True`
- recommended action: Review the exact character/glyph and boundary context; no automatic repair is made.
- Kanripo opening key: `桓公語嘉賔阿源有德有言向`
- Kanripo opening text (source spelling): `桓公語嘉賔阿源有德有言向`
- Kanripo location: `content/processed/shishuo/chapters/chapter-08.md`; normalized line `350`; page `<pb:KR3l0002_SBCK_003-14a>`
- Wikisource match type: `suffix`
- Wikisource page: `Page:Sibu Congkan0463-劉義慶-世説新語-3-2.djvu/135`

```text
王領軍供養之每與周旋行來往名勝許輒與俱不得汰便停車不行因此名遂重王長史與大司馬書道淵源識致安處足副時談謝公云劉尹語審細⟦{{SKchar|3129}}⟧公語嘉賔阿源有德有言向使作令僕足以儀刑百揆朝廷用違其才耳簡文語嘉賔劉尹語末後亦小異回復其言亦乃無過孫興公許𤣥度共在白樓亭共商略先往名達林公既非所關聽訖云二賢故自有才情王右軍道東陽我家阿林章清太出王長史與劉尹書道淵源觸事長易謝中郎云王脩載樂託之性出自門風林公云王敬仁是超悟人劉尹先推謝鎮西謝後雅重劉曰昔嘗北靣謝太傅稱王脩齡
```

---

### 08-shangyu — 08-shangyu-117 — `unmatched_entry_opening`

- classification: `unresolved`
- confidence: `low`
- requires visual verification: `True`
- recommended action: Inspect the same-edition page witness and the relevant glyph/character reading before classifying as a textual variant or source gap.
- Kanripo opening key: `孫興公許玄度共在白樓亭共`
- Kanripo opening text (source spelling): `孫興公許玄度共在白樓亭(隂臨流映壑也/㑹稽記曰亭在山)共`
- Kanripo location: `content/processed/shishuo/chapters/chapter-08.md`; normalized line `355`; page `<pb:KR3l0002_SBCK_003-14b>`
- Wikisource match type: `none`
- Wikisource page: `not located`

```text
No aligned Wikisource reading.
```

---

### 08-shangyu — 08-shangyu-122 — `non_exact_entry_opening`

- classification: `unresolved`
- confidence: `low`
- requires visual verification: `True`
- recommended action: Review the exact character/glyph and boundary context; no automatic repair is made.
- Kanripo opening key: `劉尹先推謝鎮西謝後雅重劉`
- Kanripo opening text (source spelling): `劉尹先推謝鎮西謝後雅重劉`
- Kanripo location: `content/processed/shishuo/chapters/chapter-08.md`; normalized line `365`; page `<pb:KR3l0002_SBCK_003-15a>`
- Wikisource match type: `suffix`
- Wikisource page: `Page:Sibu Congkan0463-劉義慶-世説新語-3-2.djvu/137`

```text
故自有才情王右軍道東陽我家阿林章清太出王長史與劉尹書道淵源觸事長易謝中郎云王脩載樂託之性出自門風林公云王敬仁是超悟人劉尹先推謝鎮西謝後雅重劉曰昔嘗北靣謝太傅稱王脩齡曰司州可與林澤遊諺曰⟦{{SKchar|3951}}⟧州獨歩王文度後來出人郗嘉賔人問王長史江𨞹兄弟羣從王荅曰諸江皆復足自生活謝太傅道安北見之乃不使人厭然出戸去不復使人思謝公云司州造勝遍決劉尹云見何次道飲酒使人欲傾家釀謝太傅語真長阿齡於此事故欲太厲劉曰亦名士之高操者王子猷説世目士少爲朗我家亦以爲徹朗謝公云長史
```

---

### 08-shangyu — 08-shangyu-124 — `non_exact_entry_opening`

- classification: `unresolved`
- confidence: `low`
- requires visual verification: `True`
- recommended action: Review the exact character/glyph and boundary context; no automatic repair is made.
- Kanripo opening key: `諺曰揚州獨歩王文度後來出`
- Kanripo opening text (source spelling): `諺曰揚州獨歩王文度後來出`
- Kanripo location: `content/processed/shishuo/chapters/chapter-08.md`; normalized line `369`; page `<pb:KR3l0002_SBCK_003-15a>`
- Wikisource match type: `suffix`
- Wikisource page: `Page:Sibu Congkan0463-劉義慶-世説新語-3-2.djvu/137`

```text
謝中郎云王脩載樂託之性出自門風林公云王敬仁是超悟人劉尹先推謝鎮西謝後雅重劉曰昔嘗北靣謝太傅稱王脩齡曰司州可與林澤遊諺曰⟦{{SKchar|3951}}⟧州獨歩王文度後來出人郗嘉賔人問王長史江𨞹兄弟羣從王荅曰諸江皆復足自生活謝太傅道安北見之乃不使人厭然出戸去不復使人思謝公云司州造勝遍決劉尹云見何次道飲酒使人欲傾家釀謝太傅語真長阿齡於此事故欲太厲劉曰亦名士之高操者王子猷説世目士少爲朗我家亦以爲徹朗謝公云長史語甚不多可謂有令音謝鎮西道敬仁文學鏃鏃無能不新劉尹道江道羣不能言而
```

---

### 08-shangyu — 08-shangyu-125 — `unmatched_entry_opening`

- classification: `unresolved`
- confidence: `low`
- requires visual verification: `True`
- recommended action: Inspect the same-edition page witness and the relevant glyph/character reading before classifying as a textual variant or source gap.
- Kanripo opening key: `人問王長史江兄弟羣從王荅`
- Kanripo opening text (source spelling): `人問王長史江　兄弟羣從王荅`
- Kanripo location: `content/processed/shishuo/chapters/chapter-08.md`; normalized line `372`; page `<pb:KR3l0002_SBCK_003-15a>`
- Wikisource match type: `none`
- Wikisource page: `not located`

```text
No aligned Wikisource reading.
```

---

### 08-shangyu — 08-shangyu-128 — `non_exact_entry_opening`

- classification: `unresolved`
- confidence: `low`
- requires visual verification: `True`
- recommended action: Review the exact character/glyph and boundary context; no automatic repair is made.
- Kanripo opening key: `劉尹云見何次道飲酒使人欲`
- Kanripo opening text (source spelling): `劉尹云見何次道飲酒使人欲`
- Kanripo location: `content/processed/shishuo/chapters/chapter-08.md`; normalized line `380`; page `<pb:KR3l0002_SBCK_003-15b>`
- Wikisource match type: `suffix`
- Wikisource page: `Page:Sibu Congkan0463-劉義慶-世説新語-3-2.djvu/138`

```text
人郗嘉賔人問王長史江𨞹兄弟羣從王荅曰諸江皆復足自生活謝太傅道安北見之乃不使人厭然出戸去不復使人思謝公云司州造勝遍決劉尹云見何次道飲酒使人欲傾家釀謝太傅語真長阿齡於此事故欲太厲劉曰亦名士之高操者王子猷説世目士少爲朗我家亦以爲徹朗謝公云長史語甚不多可謂有令音謝鎮西道敬仁文學鏃鏃無能不新劉尹道江道羣不能言而能不言林公云見司州警悟交至使人不得住亦終日忘疲世稱茍子秀出阿興清和簡文云劉尹茗柯有實理謝胡兒作著作郎嘗作王堪傳不諳堪是何似人咨謝公謝公荅曰
```

---

### 08-shangyu — 08-shangyu-136 — `non_exact_entry_opening`

- classification: `unresolved`
- confidence: `low`
- requires visual verification: `True`
- recommended action: Review the exact character/glyph and boundary context; no automatic repair is made.
- Kanripo opening key: `簡文云劉尹茗柯有實理`
- Kanripo opening text (source spelling): `簡文云劉尹茗柯有實理(作仃又作打/柯一作打又)
`
- Kanripo location: `content/processed/shishuo/chapters/chapter-08.md`; normalized line `394`; page `<pb:KR3l0002_SBCK_003-16a>`
- Wikisource match type: `suffix`
- Wikisource page: `Page:Sibu Congkan0463-劉義慶-世説新語-3-2.djvu/139`

```text
音謝鎮西道敬仁文學鏃鏃無能不新劉尹道江道羣不能言而能不言林公云見司州警悟交至使人不得住亦終日忘疲世稱茍子秀出阿興清和簡文云劉尹茗柯有實理謝胡兒作著作郎嘗作王堪傳不諳堪是何似人咨謝公謝公荅曰世胄亦被遇堪烈之子阮千里姨兄弟潘安仁中外安仁詩所謂子親伊姑我父唯舅是許允壻謝太傅重鄧僕射常言天地無知使伯道無兒謝公與王右軍書曰敬和棲託好佳吳四姓舊目云張文朱武陸忠顧厚謝公語王孝伯君家藍田舉體無常人事許掾嘗詣簡文爾夜風恬月朗乃共作曲室中語⟦{{SKchar|3440}}⟧情之詠偏是許之
```

---

### 08-shangyu — 08-shangyu-143 — `unmatched_entry_opening`

- classification: `unresolved`
- confidence: `low`
- requires visual verification: `True`
- recommended action: Inspect the same-edition page witness and the relevant glyph/character reading before classifying as a textual variant or source gap.
- Kanripo opening key: `殷允出西郗超與袁虎書云子`
- Kanripo opening text (source spelling): `殷允出西郗超與袁虎書云子`
- Kanripo location: `content/processed/shishuo/chapters/chapter-08.md`; normalized line `418`; page `<pb:KR3l0002_SBCK_003-17b>`
- Wikisource match type: `none`
- Wikisource page: `not located`

```text
No aligned Wikisource reading.
```

---

### 08-shangyu — 08-shangyu-154 — `unmatched_entry_opening`

- classification: `unresolved`
- confidence: `low`
- requires visual verification: `True`
- recommended action: Inspect the same-edition page witness and the relevant glyph/character reading before classifying as a textual variant or source gap.
- Kanripo opening key: `殷仲堪䘮後桓玄問仲文卿家`
- Kanripo opening text (source spelling): `殷仲堪䘮後桓玄問仲文卿家`
- Kanripo location: `content/processed/shishuo/chapters/chapter-08.md`; normalized line `459`; page `<pb:KR3l0002_SBCK_003-19a>`
- Wikisource match type: `none`
- Wikisource page: `not located`

```text
No aligned Wikisource reading.
```

---

### 08-shangyu — `missing_kanripo_passage`

- classification: `unresolved`
- confidence: `medium`
- requires visual verification: `True`
- recommended action: Use page-level visual witnesses to determine whether this is a missing/extra passage, a glyph/character variant, or a segmentation difference. No textual repair is performed.
- Kanripo main characters: 4909
- Wikisource main characters: 5038
- length delta (Wikisource − Kanripo): 129
- sequence ratio: 0.973158
- Kanripo location: `content/processed/shishuo/chapters/chapter-08.md`; page markers `['<pb:KR3l0002_SBCK_002-46b>', '<pb:KR3l0002_SBCK_002-47a>', '<pb:KR3l0002_SBCK_002-47b>', '<pb:KR3l0002_SBCK_002-48a>', '<pb:KR3l0002_SBCK_002-48b>', '<pb:KR3l0002_SBCK_002-49a>', '<pb:KR3l0002_SBCK_002-49b>', '<pb:KR3l0002_SBCK_002-50a>', '<pb:KR3l0002_SBCK_002-50b>', '<pb:KR3l0002_SBCK_002-51a>', '<pb:KR3l0002_SBCK_002-51b>', '<pb:KR3l0002_SBCK_002-52a>', '<pb:KR3l0002_SBCK_002-52b>', '<pb:KR3l0002_SBCK_002-53a>', '<pb:KR3l0002_SBCK_002-53b>', '<pb:KR3l0002_SBCK_002-54a>', '<pb:KR3l0002_SBCK_002-54b>', '<pb:KR3l0002_SBCK_003-1b>', '<pb:KR3l0002_SBCK_003-2a>', '<pb:KR3l0002_SBCK_003-2b>', '<pb:KR3l0002_SBCK_003-3a>', '<pb:KR3l0002_SBCK_003-3b>', '<pb:KR3l0002_SBCK_003-4a>', '<pb:KR3l0002_SBCK_003-4b>', '<pb:KR3l0002_SBCK_003-5a>', '<pb:KR3l0002_SBCK_003-5b>', '<pb:KR3l0002_SBCK_003-6a>', '<pb:KR3l0002_SBCK_003-6b>', '<pb:KR3l0002_SBCK_003-7a>', '<pb:KR3l0002_SBCK_003-7b>', '<pb:KR3l0002_SBCK_003-8a>', '<pb:KR3l0002_SBCK_003-8b>', '<pb:KR3l0002_SBCK_003-9a>', '<pb:KR3l0002_SBCK_003-9b>', '<pb:KR3l0002_SBCK_003-10a>', '<pb:KR3l0002_SBCK_003-10b>', '<pb:KR3l0002_SBCK_003-10b>', '<pb:KR3l0002_SBCK_003-11a>', '<pb:KR3l0002_SBCK_003-11b>', '<pb:KR3l0002_SBCK_003-12a>', '<pb:KR3l0002_SBCK_003-12b>', '<pb:KR3l0002_SBCK_003-13a>', '<pb:KR3l0002_SBCK_003-13b>', '<pb:KR3l0002_SBCK_003-14a>', '<pb:KR3l0002_SBCK_003-14b>', '<pb:KR3l0002_SBCK_003-15a>', '<pb:KR3l0002_SBCK_003-15b>', '<pb:KR3l0002_SBCK_003-16a>', '<pb:KR3l0002_SBCK_003-16b>', '<pb:KR3l0002_SBCK_003-17a>', '<pb:KR3l0002_SBCK_003-17b>', '<pb:KR3l0002_SBCK_003-18a>', '<pb:KR3l0002_SBCK_003-18b>', '<pb:KR3l0002_SBCK_003-19a>', '<pb:KR3l0002_SBCK_003-19b>']`
- Wikisource page range: `Page:Sibu Congkan0463-劉義慶-世説新語-3-2.djvu/90` through `Page:Sibu Congkan0463-劉義慶-世説新語-3-2.djvu/145` (56 pages)
- Wikisource source URL range: `https://zh.wikisource.org/wiki/Page%3ASibu%20Congkan0463-%E5%8A%89%E7%BE%A9%E6%85%B6-%E4%B8%96%E8%AA%AC%E6%96%B0%E8%AA%9E-3-2.djvu%2F90` through `https://zh.wikisource.org/wiki/Page%3ASibu%20Congkan0463-%E5%8A%89%E7%BE%A9%E6%85%B6-%E4%B8%96%E8%AA%AC%E6%96%B0%E8%AA%9E-3-2.djvu%2F145`

```text
下共推之謝公稱藍田掇皮皆真桓温行經王敦墓邊過望之云可兒可兒殷中軍道王右軍云逸少清貴人吾於之甚至一時無所後王仲祖稱殷淵源非以長勝人處長亦勝人王司州與殷中軍語嘆云巳之府奥蚤已傾冩而見殷陳勢浩汗衆源未可得測王長史謂林公真長可謂金玉滿堂林公曰金玉滿淵源真可王曰卿故墮其雲霧中劉尹每稱王長史云性至通而自然有節王右軍道謝萬石在林澤中爲自遒上歎林公器朗神儁道祖士少風領毛骨恐没世不復見如此人道劉真長標雲柯而不扶踈簡文目庾赤玉省率治除謝仁祖云庾赤玉匈中無宿物殷中軍道韓太常曰康伯少自標置居然是出羣器及其發言遣辭往往有情致簡文道王懷祖才既不長於榮利又不淡直以真率少許便足對人多多許林公謂王右軍云長史作數百語無非德音如恨不苦王曰長史自不欲苦物殷中軍與人書道謝萬文理轉遒成殊不易王長史云江思悛思懷所通不
```

```text
下共推之謝公稱藍田掇皮皆真⟦{{SKchar|3129}}⟧温行經王敦墓邊過望之云可兒可兒殷中軍道王右軍云逸少清貴人吾於之甚至一時無所後王仲祖稱殷淵源非以長勝人處長亦勝人王司州與殷中軍語嘆云巳之府奥蚤已傾冩而見殷陳勢浩汗衆源未可得測王長史謂林公真長可謂金玉滿堂林公曰金玉滿堂復何為簡選王曰非爲簡選直致言處自寡耳王長史道江道羣人所應有乃不必有人所應無已必無會稽孔沉魏顗虞球虞存謝奉並是四族之儁于時之傑孫興公目之曰沉爲孔家金顗爲魏家玉虞爲長琳宗謝爲弘道伏王仲祖劉真長造殷中軍談談竟俱載去劉謂王曰淵源真可王曰卿故墮其雲霧中劉尹每稱王長史云性至通而自然有節王右軍道謝萬石在林澤中爲自遒上歎林公器朗神儁道祖士少風領毛骨恐没世不復見如此人道劉真長標雲柯而不扶踈簡文目𢈔赤玉省率治除謝仁祖云𢈔赤玉𦙄中無宿物殷中軍道韓太常曰康伯少自標置居然是出羣器及其發言遣辭往往有情致簡文道王懷祖才既不長於榮利又不淡直以真率少許便足對人多多
```

---

### 09-pinzao — 09-pinzao-011 — `non_exact_entry_opening`

- classification: `unresolved`
- confidence: `low`
- requires visual verification: `True`
- recommended action: Review the exact character/glyph and boundary context; no automatic repair is made.
- Kanripo opening key: `庾中郎與王平子鴈行王大將`
- Kanripo opening text (source spelling): `庾中郎與王平子鴈行(而輕薄無行兄夷甫有盛名/晉陽秋曰初王澄有通朗稱)
(嵩第二處仲第三敳以澄敦莫巳若也及澄䘮敦敗/時人許以人倫鑒識常爲天下士目曰阿平第一子)
(如初/敳世譽)
王大將`
- Kanripo location: `content/processed/shishuo/chapters/chapter-09.md`; normalized line `541`; page `<pb:KR3l0002_SBCK_003-23a>`
- Wikisource match type: `suffix`
- Wikisource page: `Page:Sibu Congkan0463-劉義慶-世説新語-3-2.djvu/153`

```text
用短杜方叔拙於用長王夷甫云閭丘沖優於滿奮郝隆此三人並是高才沖最先逹王夷甫以王東海比樂令故王中郎作碑云當時標榜爲樂廣之儷⟦{{SKchar|2928}}⟧中郎與王平子鴈行王大將軍在西朝時見周侯輒扇障靣不得住後度江左不能復爾王嘆曰不知我進伯仁⟦{{SKchar|2385}}⟧會稽虞⟦{{SKchar|801}}⟧元皇時與⟦{{SKchar|3129}}⟧宣武同俠其人有才理勝望王丞相嘗謂⟦{{SKchar|801}}⟧曰孔愉有公才而無公望丁潭有公望而無公才兼之者其在卿乎⟦{{SKchar|801}}⟧未逹而䘮明帝問周伯仁卿自謂何如郗鑒周曰鑒方臣如有功夫復問郗郗曰周顗比臣有國士門風王大將軍下𢈔公問聞卿有四友何者是荅曰君家中郎我
```

---

### 09-pinzao — 09-pinzao-012 — `non_exact_entry_opening`

- classification: `unresolved`
- confidence: `low`
- requires visual verification: `True`
- recommended action: Review the exact character/glyph and boundary context; no automatic repair is made.
- Kanripo opening key: `王大將軍在西朝時見周侯輒`
- Kanripo opening text (source spelling): `王大將軍在西朝時見周侯輒`
- Kanripo location: `content/processed/shishuo/chapters/chapter-09.md`; normalized line `544`; page `<pb:KR3l0002_SBCK_003-23a>`
- Wikisource match type: `suffix`
- Wikisource page: `Page:Sibu Congkan0463-劉義慶-世説新語-3-2.djvu/153`

```text
甫云閭丘沖優於滿奮郝隆此三人並是高才沖最先逹王夷甫以王東海比樂令故王中郎作碑云當時標榜爲樂廣之儷⟦{{SKchar|2928}}⟧中郎與王平子鴈行王大將軍在西朝時見周侯輒扇障靣不得住後度江左不能復爾王嘆曰不知我進伯仁⟦{{SKchar|2385}}⟧會稽虞⟦{{SKchar|801}}⟧元皇時與⟦{{SKchar|3129}}⟧宣武同俠其人有才理勝望王丞相嘗謂⟦{{SKchar|801}}⟧曰孔愉有公才而無公望丁潭有公望而無公才兼之者其在卿乎⟦{{SKchar|801}}⟧未逹而䘮明帝問周伯仁卿自謂何如郗鑒周曰鑒方臣如有功夫復問郗郗曰周顗比臣有國士門風王大將軍下𢈔公問聞卿有四友何者是荅曰君家中郎我家太尉阿平胡母彦國阿平
```

---

### 09-pinzao — 09-pinzao-013 — `non_exact_entry_opening`

- classification: `unresolved`
- confidence: `low`
- requires visual verification: `True`
- recommended action: Review the exact character/glyph and boundary context; no automatic repair is made.
- Kanripo opening key: `會稽虞元皇時與桓宣武同俠`
- Kanripo opening text (source spelling): `會稽虞&KR1294;元皇時與桓宣武同俠`
- Kanripo location: `content/processed/shishuo/chapters/chapter-09.md`; normalized line `548`; page `<pb:KR3l0002_SBCK_003-23a>`
- Wikisource match type: `prefix`
- Wikisource page: `Page:Sibu Congkan0463-劉義慶-世説新語-3-2.djvu/153`

```text
王中郎作碑云當時標榜爲樂廣之儷⟦{{SKchar|2928}}⟧中郎與王平子鴈行王大將軍在西朝時見周侯輒扇障靣不得住後度江左不能復爾王嘆曰不知我進伯仁⟦{{SKchar|2385}}⟧會稽虞⟦{{SKchar|801}}⟧元皇時與⟦{{SKchar|3129}}⟧宣武同俠其人有才理勝望王丞相嘗謂⟦{{SKchar|801}}⟧曰孔愉有公才而無公望丁潭有公望而無公才兼之者其在卿乎⟦{{SKchar|801}}⟧未逹而䘮明帝問周伯仁卿自謂何如郗鑒周曰鑒方臣如有功夫復問郗郗曰周顗比臣有國士門風王大將軍下𢈔公問聞卿有四友何者是荅曰君家中郎我家太尉阿平胡母彦國阿平故當最劣𢈔曰似未肯劣𢈔又問何者居其右王曰自有人又問何者是王曰噫其自
```

---

### 09-pinzao — 09-pinzao-015 — `unmatched_entry_opening`

- classification: `unresolved`
- confidence: `low`
- requires visual verification: `True`
- recommended action: Inspect the same-edition page witness and the relevant glyph/character reading before classifying as a textual variant or source gap.
- Kanripo opening key: `王大將軍下庾公問聞卿有四`
- Kanripo opening text (source spelling): `王大將軍下庾公問聞卿有四`
- Kanripo location: `content/processed/shishuo/chapters/chapter-09.md`; normalized line `561`; page `<pb:KR3l0002_SBCK_003-24a>`
- Wikisource match type: `none`
- Wikisource page: `not located`

```text
No aligned Wikisource reading.
```

---

### 09-pinzao — 09-pinzao-017 — `non_exact_entry_opening`

- classification: `unresolved`
- confidence: `low`
- requires visual verification: `True`
- recommended action: Review the exact character/glyph and boundary context; no automatic repair is made.
- Kanripo opening key: `明帝問謝鯤君自謂何如庾亮`
- Kanripo opening text (source spelling): `明帝問謝鯤君自謂何如庾亮`
- Kanripo location: `content/processed/shishuo/chapters/chapter-09.md`; normalized line `568`; page `<pb:KR3l0002_SBCK_003-24a>`
- Wikisource match type: `prefix`
- Wikisource page: `Page:Sibu Congkan0463-劉義慶-世説新語-3-2.djvu/155`

```text
平故當最劣𢈔曰似未肯劣𢈔又問何者居其右王曰自有人又問何者是王曰噫其自有公論左右躡公公乃止人問丞相周侯何如和嶠荅曰長輿嵯櫱明帝問謝鯤君自謂何如𢈔亮荅曰端委廟堂使百僚凖則臣不如亮一丘一壑自謂過之王丞相二弟不過江曰潁曰敝時論以潁比鄧伯道敝比温忠武議郎祭酒者也明帝問周侯論者以卿比郗鑒云何周曰陛下不須牽顗比王丞相云頃下論以我比安期千里亦推此二人唯共推太尉此君特秀宋禕曾爲王大將軍妾後屬謝鎮西鎮西問禕我何如王荅曰王比使君田舍貴人耳鎮西妖冶故也明帝問周
```

---

### 09-pinzao — 09-pinzao-022 — `non_exact_entry_opening`

- classification: `unresolved`
- confidence: `low`
- requires visual verification: `True`
- recommended action: Review the exact character/glyph and boundary context; no automatic repair is made.
- Kanripo opening key: `明帝問周伯仁卿自謂何如庾`
- Kanripo opening text (source spelling): `明帝問周伯仁卿自謂何如庾`
- Kanripo location: `content/processed/shishuo/chapters/chapter-09.md`; normalized line `585`; page `<pb:KR3l0002_SBCK_003-25a>`
- Wikisource match type: `prefix`
- Wikisource page: `Page:Sibu Congkan0463-劉義慶-世説新語-3-2.djvu/157`

```text
以我比安期千里亦推此二人唯共推太尉此君特秀宋禕曾爲王大將軍妾後屬謝鎮西鎮西問禕我何如王荅曰王比使君田舍貴人耳鎮西妖冶故也明帝問周伯仁卿自謂何如⟦{{SKchar|2928}}⟧元規對曰蕭條方外亮不如臣從容廊廟臣不如亮王丞相辟王藍田爲掾⟦{{SKchar|2928}}⟧公問丞相藍田何似王曰眞獨簡貴不減父祖然曠澹處故當不如爾卞望之云郗公體中有三反方於事上好下佞巳一反治身清貞大脩計校二反自好讀書憎人學問三反世論温太真是過江第二流之高者時名輩共説人物第一將盡之間温常失色王丞相云見謝仁祖恒令人得上與何次道語唯
```

---

### 09-pinzao — 09-pinzao-023 — `non_exact_entry_opening`

- classification: `unresolved`
- confidence: `low`
- requires visual verification: `True`
- recommended action: Review the exact character/glyph and boundary context; no automatic repair is made.
- Kanripo opening key: `王丞相辟王藍田爲掾庾公問`
- Kanripo opening text (source spelling): `王丞相辟王藍田爲掾庾公問`
- Kanripo location: `content/processed/shishuo/chapters/chapter-09.md`; normalized line `587`; page `<pb:KR3l0002_SBCK_003-25a>`
- Wikisource match type: `prefix`
- Wikisource page: `Page:Sibu Congkan0463-劉義慶-世説新語-3-2.djvu/157`

```text
謝鎮西鎮西問禕我何如王荅曰王比使君田舍貴人耳鎮西妖冶故也明帝問周伯仁卿自謂何如⟦{{SKchar|2928}}⟧元規對曰蕭條方外亮不如臣從容廊廟臣不如亮王丞相辟王藍田爲掾⟦{{SKchar|2928}}⟧公問丞相藍田何似王曰眞獨簡貴不減父祖然曠澹處故當不如爾卞望之云郗公體中有三反方於事上好下佞巳一反治身清貞大脩計校二反自好讀書憎人學問三反世論温太真是過江第二流之高者時名輩共説人物第一將盡之間温常失色王丞相云見謝仁祖恒令人得上與何次道語唯舉手指地曰正自爾馨何次道爲宰相人有譏其信任不得其人阮思曠慨然曰次
```

---

### 09-pinzao — 09-pinzao-035 — `non_exact_entry_opening`

- classification: `unresolved`
- confidence: `low`
- requires visual verification: `True`
- recommended action: Review the exact character/glyph and boundary context; no automatic repair is made.
- Kanripo opening key: `桓公少與殷侯齊名常有競心`
- Kanripo opening text (source spelling): `桓公少與殷侯齊名常有競心`
- Kanripo location: `content/processed/shishuo/chapters/chapter-09.md`; normalized line `630`; page `<pb:KR3l0002_SBCK_003-27a>`
- Wikisource match type: `suffix`
- Wikisource page: `Page:Sibu Congkan0463-劉義慶-世説新語-3-2.djvu/161`

```text
使子繼父業弟承家祀有何不可人問殷淵源當世王公以卿比裴叔道云何殷曰故當以識通暗處撫軍問殷浩卿定何如裴逸民良久荅曰故當勝耳⟦{{SKchar|3129}}⟧公少與殷侯齊名常有競心⟦{{SKchar|3129}}⟧問殷卿何如我殷云我與我周旋久寧作我撫軍問孫興公劉眞長何如曰清蔚簡令王仲祖何如曰温潤恬和⟦{{SKchar|3129}}⟧温何如曰高爽邁出謝仁祖何如曰清易令逹阮思曠何如曰⟦{{SKchar|2592}}⟧潤通長⟦{{SKchar|2783}}⟧羊何如曰洮洮清便殷洪逺何如曰逺有致思卿自謂何如曰下官才能所經悉不如諸賢至於斟酌時宜籠罩當世亦多所不及然以不才時復託懷玄勝逺詠老莊蕭條高寄不與時務經懷自
```

---

### 09-pinzao — 09-pinzao-037 — `non_exact_entry_opening`

- classification: `unresolved`
- confidence: `low`
- requires visual verification: `True`
- recommended action: Review the exact character/glyph and boundary context; no automatic repair is made.
- Kanripo opening key: `桓大司馬下都問真長曰聞會`
- Kanripo opening text (source spelling): `桓大司馬下都問真長曰聞會`
- Kanripo location: `content/processed/shishuo/chapters/chapter-09.md`; normalized line `641`; page `<pb:KR3l0002_SBCK_003-27b>`
- Wikisource match type: `suffix`
- Wikisource page: `Page:Sibu Congkan0463-劉義慶-世説新語-3-2.djvu/162`

```text
下官才能所經悉不如諸賢至於斟酌時宜籠罩當世亦多所不及然以不才時復託懷玄勝逺詠老莊蕭條高寄不與時務經懷自謂此心無所與讓也⟦{{SKchar|3129}}⟧大司馬下都問真長曰聞會稽王語竒進爾邪劉曰極進然故是第二流中人耳⟦{{SKchar|3129}}⟧曰第一流復是誰劉曰正是我輩耳殷侯既廢⟦{{SKchar|3129}}⟧公語諸人曰少時與淵源共騎竹馬我棄去巳輒取之故當出我下人問撫軍殷浩談竟何如荅曰不能勝人差可獻酬羣心簡文云謝安南清令不如其弟學義不及孔巖居然自勝未廢海西公時王元琳問⟦{{SKchar|3129}}⟧元子箕子比干迹異心同不審明公孰是孰非曰仁稱不異寧爲管仲劉
```

---

### 09-pinzao — 09-pinzao-038 — `unmatched_entry_opening`

- classification: `unresolved`
- confidence: `low`
- requires visual verification: `True`
- recommended action: Inspect the same-edition page witness and the relevant glyph/character reading before classifying as a textual variant or source gap.
- Kanripo opening key: `殷侯既廢桓公語諸人曰少時`
- Kanripo opening text (source spelling): `殷侯既廢桓公語諸人曰少時`
- Kanripo location: `content/processed/shishuo/chapters/chapter-09.md`; normalized line `645`; page `<pb:KR3l0002_SBCK_003-27b>`
- Wikisource match type: `none`
- Wikisource page: `not located`

```text
No aligned Wikisource reading.
```

---

### 09-pinzao — 09-pinzao-041 — `non_exact_entry_opening`

- classification: `unresolved`
- confidence: `low`
- requires visual verification: `True`
- recommended action: Review the exact character/glyph and boundary context; no automatic repair is made.
- Kanripo opening key: `未廢海西公時王元琳問桓元`
- Kanripo opening text (source spelling): `未廢海西公時王元琳問桓元`
- Kanripo location: `content/processed/shishuo/chapters/chapter-09.md`; normalized line `655`; page `<pb:KR3l0002_SBCK_003-28a>`
- Wikisource match type: `prefix`
- Wikisource page: `Page:Sibu Congkan0463-劉義慶-世説新語-3-2.djvu/163`

```text
共騎竹馬我棄去巳輒取之故當出我下人問撫軍殷浩談竟何如荅曰不能勝人差可獻酬羣心簡文云謝安南清令不如其弟學義不及孔巖居然自勝未廢海西公時王元琳問⟦{{SKchar|3129}}⟧元子箕子比干迹異心同不審明公孰是孰非曰仁稱不異寧爲管仲劉丹陽王長史在瓦官寺集⟦{{SKchar|3129}}⟧護軍亦在坐共商略西朝及江左人物或問杜⟦{{SKchar|2592}}⟧治何如衛虎⟦{{SKchar|3129}}⟧荅曰⟦{{SKchar|2592}}⟧治膚清衛虎弈弈神令王劉善其言劉尹撫王長史背曰阿奴比丞相但有都長劉尹王長史同坐長史酒酣起舞劉尹曰阿奴今日不復減向子期⟦{{SKchar|3129}}⟧公問孔西陽安石何如仲文孔思未對反問公曰何如荅曰安
```

---

### 09-pinzao — 09-pinzao-042 — `non_exact_entry_opening`

- classification: `unresolved`
- confidence: `low`
- requires visual verification: `True`
- recommended action: Review the exact character/glyph and boundary context; no automatic repair is made.
- Kanripo opening key: `劉丹陽王長史在瓦官寺集桓`
- Kanripo opening text (source spelling): `劉丹陽王長史在瓦官寺集桓`
- Kanripo location: `content/processed/shishuo/chapters/chapter-09.md`; normalized line `660`; page `<pb:KR3l0002_SBCK_003-28b>`
- Wikisource match type: `prefix`
- Wikisource page: `Page:Sibu Congkan0463-劉義慶-世説新語-3-2.djvu/164`

```text
簡文云謝安南清令不如其弟學義不及孔巖居然自勝未廢海西公時王元琳問⟦{{SKchar|3129}}⟧元子箕子比干迹異心同不審明公孰是孰非曰仁稱不異寧爲管仲劉丹陽王長史在瓦官寺集⟦{{SKchar|3129}}⟧護軍亦在坐共商略西朝及江左人物或問杜⟦{{SKchar|2592}}⟧治何如衛虎⟦{{SKchar|3129}}⟧荅曰⟦{{SKchar|2592}}⟧治膚清衛虎弈弈神令王劉善其言劉尹撫王長史背曰阿奴比丞相但有都長劉尹王長史同坐長史酒酣起舞劉尹曰阿奴今日不復減向子期⟦{{SKchar|3129}}⟧公問孔西陽安石何如仲文孔思未對反問公曰何如荅曰安石居然不可陵踐其處故乃勝也謝公與時賢共賞説遏胡兒並在坐公問李⟦{{SKchar|2592}}⟧度曰卿家平陽何
```

---

### 09-pinzao — 09-pinzao-045 — `non_exact_entry_opening`

- classification: `unresolved`
- confidence: `low`
- requires visual verification: `True`
- recommended action: Review the exact character/glyph and boundary context; no automatic repair is made.
- Kanripo opening key: `桓公問孔西陽安石何如仲文`
- Kanripo opening text (source spelling): `桓公問孔西陽安石何如仲文`
- Kanripo location: `content/processed/shishuo/chapters/chapter-09.md`; normalized line `669`; page `<pb:KR3l0002_SBCK_003-28b>`
- Wikisource match type: `suffix`
- Wikisource page: `Page:Sibu Congkan0463-劉義慶-世説新語-3-2.djvu/164`

```text
曰⟦{{SKchar|2592}}⟧治膚清衛虎弈弈神令王劉善其言劉尹撫王長史背曰阿奴比丞相但有都長劉尹王長史同坐長史酒酣起舞劉尹曰阿奴今日不復減向子期⟦{{SKchar|3129}}⟧公問孔西陽安石何如仲文孔思未對反問公曰何如荅曰安石居然不可陵踐其處故乃勝也謝公與時賢共賞説遏胡兒並在坐公問李⟦{{SKchar|2592}}⟧度曰卿家平陽何如樂令於是李澘然流涕曰趙王簒逆樂令親授璽綬亡伯雅正恥處亂朝遂至仰藥恐難以相比此自顯於事實非私親之言謝公語胡兒曰有識者果不異人意王脩齡問王長史我家臨川何如卿家宛陵長史未荅脩齡曰臨川譽貴長史曰宛陵未爲
```

---

### 09-pinzao — 09-pinzao-058 — `non_exact_entry_opening`

- classification: `unresolved`
- confidence: `low`
- requires visual verification: `True`
- recommended action: Review the exact character/glyph and boundary context; no automatic repair is made.
- Kanripo opening key: `劉尹目庾中郎雖言不愔愔似`
- Kanripo opening text (source spelling): `劉尹目庾中郎雖言不愔愔似`
- Kanripo location: `content/processed/shishuo/chapters/chapter-09.md`; normalized line `723`; page `<pb:KR3l0002_SBCK_003-31a>`
- Wikisource match type: `suffix`
- Wikisource page: `Page:Sibu Congkan0463-劉義慶-世説新語-3-2.djvu/169`

```text
許未荅王因曰安石故相爲雄阿萬當裂眼争邪劉尹云人言江虨田舍江乃自田宅屯謝公云金谷中蘇紹最勝紹是石崇姉夫蘇則孫愉子也劉尹目⟦{{SKchar|2928}}⟧中郎雖言不愔愔似道突兀差可以擬道孫承公云謝公清於無弈潤於林道或問林公司州何如二謝林公曰故當攀安提萬孫興公許玄度皆一時名流或重許高情則鄙孫穢行或愛孫才藻而無取於許郄嘉賔道謝公造䣛雖不深徹而⟦{{SKchar|3522}}⟧綿綸至又曰右軍詣嘉賔嘉賔聞之云不得稱詣政得謂之朋耳謝公以嘉賔言爲得⟦{{SKchar|2928}}⟧道季云思理倫和吾愧康伯志力彊正吾愧文度自此以還吾皆百之王僧恩輕林
```

---

### 09-pinzao — 09-pinzao-063 — `non_exact_entry_opening`

- classification: `unresolved`
- confidence: `low`
- requires visual verification: `True`
- recommended action: Review the exact character/glyph and boundary context; no automatic repair is made.
- Kanripo opening key: `庾道季云思理倫和吾愧康伯`
- Kanripo opening text (source spelling): `庾道季云思理倫和吾愧康伯`
- Kanripo location: `content/processed/shishuo/chapters/chapter-09.md`; normalized line `738`; page `<pb:KR3l0002_SBCK_003-32a>`
- Wikisource match type: `suffix`
- Wikisource page: `Page:Sibu Congkan0463-劉義慶-世説新語-3-2.djvu/171`

```text
穢行或愛孫才藻而無取於許郄嘉賔道謝公造䣛雖不深徹而⟦{{SKchar|3522}}⟧綿綸至又曰右軍詣嘉賔嘉賔聞之云不得稱詣政得謂之朋耳謝公以嘉賔言爲得⟦{{SKchar|2928}}⟧道季云思理倫和吾愧康伯志力彊正吾愧文度自此以還吾皆百之王僧恩輕林公藍田曰勿學汝兄汝兄自不如伊簡文問孫興公⟦{{SKchar|2783}}⟧羊何似荅曰不知者不⟦{{SKchar|3688}}⟧其才知之者無取其體蔡叔子云韓康伯雖無骨榦然亦膚立郗嘉賔問謝太傅曰林公談何如嵇公謝云嵇公勤著脚裁可得去耳又問殷何如支謝曰正爾有超㧞支乃過殷然亹亹論辯恐口欲制支⟦{{SKchar|2928}}⟧道季云廉頗藺相如雖千載上死人懔懔恒如
```

---

### 09-pinzao — 09-pinzao-065 — `unmatched_entry_opening`

- classification: `unresolved`
- confidence: `low`
- requires visual verification: `True`
- recommended action: Inspect the same-edition page witness and the relevant glyph/character reading before classifying as a textual variant or source gap.
- Kanripo opening key: `簡文問孫興公袁羊何似荅曰`
- Kanripo opening text (source spelling): `簡文問孫興公袁羊何似荅曰`
- Kanripo location: `content/processed/shishuo/chapters/chapter-09.md`; normalized line `743`; page `<pb:KR3l0002_SBCK_003-32a>`
- Wikisource match type: `none`
- Wikisource page: `not located`

```text
No aligned Wikisource reading.
```

---

### 09-pinzao — 09-pinzao-068 — `non_exact_entry_opening`

- classification: `unresolved`
- confidence: `low`
- requires visual verification: `True`
- recommended action: Review the exact character/glyph and boundary context; no automatic repair is made.
- Kanripo opening key: `庾道季云廉頗藺相如雖千載`
- Kanripo opening text (source spelling): `庾道季云廉頗藺相如雖千載`
- Kanripo location: `content/processed/shishuo/chapters/chapter-09.md`; normalized line `751`; page `<pb:KR3l0002_SBCK_003-32b>`
- Wikisource match type: `suffix`
- Wikisource page: `Page:Sibu Congkan0463-劉義慶-世説新語-3-2.djvu/172`

```text
榦然亦膚立郗嘉賔問謝太傅曰林公談何如嵇公謝云嵇公勤著脚裁可得去耳又問殷何如支謝曰正爾有超㧞支乃過殷然亹亹論辯恐口欲制支⟦{{SKchar|2928}}⟧道季云廉頗藺相如雖千載上死人懔懔恒如有生氣曹蜍李志雖見在厭厭如九泉下人人皆如此便可結繩而治但恐狐狸猯狢噉盡衛君長是蕭祖周婦兄謝公問孫僧奴君家道衛君長云何孫曰云是世業人謝曰殊不爾衛自是理義人于時以比殷洪逺王子敬問謝公林公何如𢈔公謝殊不受答曰先輩初無論𢈔公自足没林公謝遏諸人共道竹林優劣謝公云先輩初不臧貶士賢有人以王中郎比車
```

---

### 09-pinzao — 09-pinzao-070 — `non_exact_entry_opening`

- classification: `unresolved`
- confidence: `low`
- requires visual verification: `True`
- recommended action: Review the exact character/glyph and boundary context; no automatic repair is made.
- Kanripo opening key: `王子敬問謝公林公何如庾公`
- Kanripo opening text (source spelling): `王子敬問謝公林公何如庾公`
- Kanripo location: `content/processed/shishuo/chapters/chapter-09.md`; normalized line `765`; page `<pb:KR3l0002_SBCK_003-33a>`
- Wikisource match type: `prefix`
- Wikisource page: `Page:Sibu Congkan0463-劉義慶-世説新語-3-2.djvu/173`

```text
結繩而治但恐狐狸猯狢噉盡衛君長是蕭祖周婦兄謝公問孫僧奴君家道衛君長云何孫曰云是世業人謝曰殊不爾衛自是理義人于時以比殷洪逺王子敬問謝公林公何如𢈔公謝殊不受答曰先輩初無論𢈔公自足没林公謝遏諸人共道竹林優劣謝公云先輩初不臧貶士賢有人以王中郎比車騎車騎聞之曰伊窟窟成就謝太傅謂王孝伯劉尹亦奇自知然不言勝長史王黄門兄弟三人俱詣謝公子猷子重多説俗事子敬寒温而已既出坐客問謝公向三賢孰愈謝公曰小者最勝客曰何以知之謝公曰吉人之辭寡躁人之辭多推此知之謝公問王
```

---

### 09-pinzao — 09-pinzao-079 — `non_exact_entry_opening`

- classification: `unresolved`
- confidence: `low`
- requires visual verification: `True`
- recommended action: Review the exact character/glyph and boundary context; no automatic repair is made.
- Kanripo opening key: `袁彦伯爲吏部郎子敬與郄嘉`
- Kanripo opening text (source spelling): `袁彦伯爲吏部郎子敬與郄嘉`
- Kanripo location: `content/processed/shishuo/chapters/chapter-09.md`; normalized line `793`; page `<pb:KR3l0002_SBCK_003-34b>`
- Wikisource match type: `suffix`
- Wikisource page: `Page:Sibu Congkan0463-劉義慶-世説新語-3-2.djvu/176`

```text
二人邪謝云身意正爾也人有問太傅子敬可是先輩誰比謝曰阿敬近撮王劉之標謝公語孝伯君祖比劉尹故爲得逮孝伯云劉尹非不能逮直不逮⟦{{SKchar|2783}}⟧彦伯爲吏部郎子敬與郄嘉賔書曰彦伯巳入殊足頓興往之氣故知捶撻自難爲人冀小卻當復差耳王子猷子敬兄弟共賞高士傳人及賛子敬賞井丹高潔子猷云未若長卿慢世有人問⟦{{SKchar|2783}}⟧侍中曰殷仲堪何如韓康伯荅曰理義所得優劣乃復未辨然門庭蕭寂居然有名士風流殷不及韓故殷作誄云荆門晝掩閑庭晏然王子敬問謝公嘉賔何如道季荅曰道季誠復鈔撮清悟嘉賔故自上王珣疾臨困問
```

---

### 09-pinzao — 09-pinzao-081 — `non_exact_entry_opening`

- classification: `unresolved`
- confidence: `low`
- requires visual verification: `True`
- recommended action: Review the exact character/glyph and boundary context; no automatic repair is made.
- Kanripo opening key: `有人問袁侍中曰殷仲堪何如`
- Kanripo opening text (source spelling): `有人問袁侍中(祖王孫司徒從事中郎父綸臨汝令/袁氏譜曰恪之字元祖陳郡陽夏人)
(義熙初爲侍中/恪之仕黄門侍郎)曰殷仲堪何如`
- Kanripo location: `content/processed/shishuo/chapters/chapter-09.md`; normalized line `809`; page `<pb:KR3l0002_SBCK_003-35a>`
- Wikisource match type: `suffix`
- Wikisource page: `Page:Sibu Congkan0463-劉義慶-世説新語-3-2.djvu/177`

```text
伯巳入殊足頓興往之氣故知捶撻自難爲人冀小卻當復差耳王子猷子敬兄弟共賞高士傳人及賛子敬賞井丹高潔子猷云未若長卿慢世有人問⟦{{SKchar|2783}}⟧侍中曰殷仲堪何如韓康伯荅曰理義所得優劣乃復未辨然門庭蕭寂居然有名士風流殷不及韓故殷作誄云荆門晝掩閑庭晏然王子敬問謝公嘉賔何如道季荅曰道季誠復鈔撮清悟嘉賔故自上王珣疾臨困問王武岡曰世論以我家領軍比誰武岡曰世以比王北中郎東亭轉臥向壁嘆曰人固不可以無年王孝伯道謝公濃至又曰長史虚劉尹秀謝公融王孝伯問謝公林公何如右軍謝曰右軍勝林
```

---

### 09-pinzao — 09-pinzao-086 — `non_exact_entry_opening`

- classification: `unresolved`
- confidence: `low`
- requires visual verification: `True`
- recommended action: Review the exact character/glyph and boundary context; no automatic repair is made.
- Kanripo opening key: `桓玄爲太傅大會朝臣畢集坐`
- Kanripo opening text (source spelling): `桓玄爲太傅大會朝臣畢集坐`
- Kanripo location: `content/processed/shishuo/chapters/chapter-09.md`; normalized line `823`; page `<pb:KR3l0002_SBCK_003-35b>`
- Wikisource match type: `suffix`
- Wikisource page: `Page:Sibu Congkan0463-劉義慶-世説新語-3-2.djvu/178`

```text
向壁嘆曰人固不可以無年王孝伯道謝公濃至又曰長史虚劉尹秀謝公融王孝伯問謝公林公何如右軍謝曰右軍勝林公林公在司州前亦貴徹⟦{{SKchar|3129}}⟧⟦{{SKchar|2593}}⟧爲太傅大會朝臣畢集坐裁竟問王楨之曰我何如卿第七叔于時賔客爲之咽氣王徐徐荅曰亡叔是一時之標公是千載之英一坐懽然⟦{{SKchar|3129}}⟧⟦{{SKchar|2593}}⟧問劉太常曰我何如謝太傅劉荅曰公高太傅深又曰何如賢舅子敬荅曰樝梨橘柚各有其美舊以⟦{{SKchar|3129}}⟧謙比殷仲文⟦{{SKchar|3129}}⟧玄時仲文入⟦{{SKchar|3129}}⟧於庭中望見之謂同坐曰我家中軍那得及此也
```

---

### 09-pinzao — 09-pinzao-087 — `non_exact_entry_opening`

- classification: `unresolved`
- confidence: `low`
- requires visual verification: `True`
- recommended action: Review the exact character/glyph and boundary context; no automatic repair is made.
- Kanripo opening key: `桓玄問劉太常曰我何如謝太`
- Kanripo opening text (source spelling): `桓玄問劉太常曰我何如謝太`
- Kanripo location: `content/processed/shishuo/chapters/chapter-09.md`; normalized line `828`; page `<pb:KR3l0002_SBCK_003-36a>`
- Wikisource match type: `suffix`
- Wikisource page: `Page:Sibu Congkan0463-劉義慶-世説新語-3-2.djvu/179`

```text
貴徹⟦{{SKchar|3129}}⟧⟦{{SKchar|2593}}⟧爲太傅大會朝臣畢集坐裁竟問王楨之曰我何如卿第七叔于時賔客爲之咽氣王徐徐荅曰亡叔是一時之標公是千載之英一坐懽然⟦{{SKchar|3129}}⟧⟦{{SKchar|2593}}⟧問劉太常曰我何如謝太傅劉荅曰公高太傅深又曰何如賢舅子敬荅曰樝梨橘柚各有其美舊以⟦{{SKchar|3129}}⟧謙比殷仲文⟦{{SKchar|3129}}⟧玄時仲文入⟦{{SKchar|3129}}⟧於庭中望見之謂同坐曰我家中軍那得及此也
```

---

### 09-pinzao — 09-pinzao-088 — `unmatched_entry_opening`

- classification: `unresolved`
- confidence: `low`
- requires visual verification: `True`
- recommended action: Inspect the same-edition page witness and the relevant glyph/character reading before classifying as a textual variant or source gap.
- Kanripo opening key: `舊以桓謙比殷仲文桓玄時仲`
- Kanripo opening text (source spelling): `舊以桓謙比殷仲文(尚書僕射中軍將軍晉安帝紀/中興書曰謙字敬祖沖第三子)
(噐貌才思/曰仲文有)桓玄時仲`
- Kanripo location: `content/processed/shishuo/chapters/chapter-09.md`; normalized line `832`; page `<pb:KR3l0002_SBCK_003-36a>`
- Wikisource match type: `none`
- Wikisource page: `not located`

```text
No aligned Wikisource reading.
```

---

### 09-pinzao — `probable_one_character_shift`

- classification: `unresolved`
- confidence: `medium`
- requires visual verification: `True`
- recommended action: Use page-level visual witnesses to determine whether this is a missing/extra passage, a glyph/character variant, or a segmentation difference. No textual repair is performed.
- Kanripo main characters: 3354
- Wikisource main characters: 3354
- length delta (Wikisource − Kanripo): 0
- sequence ratio: 0.986285
- Kanripo location: `content/processed/shishuo/chapters/chapter-09.md`; page markers `['<pb:KR3l0002_SBCK_003-20a>', '<pb:KR3l0002_SBCK_003-20b>', '<pb:KR3l0002_SBCK_003-21a>', '<pb:KR3l0002_SBCK_003-21b>', '<pb:KR3l0002_SBCK_003-22a>', '<pb:KR3l0002_SBCK_003-22b>', '<pb:KR3l0002_SBCK_003-23a>', '<pb:KR3l0002_SBCK_003-23b>', '<pb:KR3l0002_SBCK_003-24a>', '<pb:KR3l0002_SBCK_003-24b>', '<pb:KR3l0002_SBCK_003-25a>', '<pb:KR3l0002_SBCK_003-25b>', '<pb:KR3l0002_SBCK_003-26a>', '<pb:KR3l0002_SBCK_003-26b>', '<pb:KR3l0002_SBCK_003-27a>', '<pb:KR3l0002_SBCK_003-27b>', '<pb:KR3l0002_SBCK_003-28a>', '<pb:KR3l0002_SBCK_003-28b>', '<pb:KR3l0002_SBCK_003-29a>', '<pb:KR3l0002_SBCK_003-29b>', '<pb:KR3l0002_SBCK_003-30a>', '<pb:KR3l0002_SBCK_003-30b>', '<pb:KR3l0002_SBCK_003-31a>', '<pb:KR3l0002_SBCK_003-31b>', '<pb:KR3l0002_SBCK_003-32a>', '<pb:KR3l0002_SBCK_003-32b>', '<pb:KR3l0002_SBCK_003-33a>', '<pb:KR3l0002_SBCK_003-33b>', '<pb:KR3l0002_SBCK_003-34a>', '<pb:KR3l0002_SBCK_003-34b>', '<pb:KR3l0002_SBCK_003-35a>', '<pb:KR3l0002_SBCK_003-35b>', '<pb:KR3l0002_SBCK_003-36a>', '<pb:KR3l0002_SBCK_003-36b>']`
- Wikisource page range: `Page:Sibu Congkan0463-劉義慶-世説新語-3-2.djvu/146` through `Page:Sibu Congkan0463-劉義慶-世説新語-3-2.djvu/179` (34 pages)
- Wikisource source URL range: `https://zh.wikisource.org/wiki/Page%3ASibu%20Congkan0463-%E5%8A%89%E7%BE%A9%E6%85%B6-%E4%B8%96%E8%AA%AC%E6%96%B0%E8%AA%9E-3-2.djvu%2F146` through `https://zh.wikisource.org/wiki/Page%3ASibu%20Congkan0463-%E5%8A%89%E7%BE%A9%E6%85%B6-%E4%B8%96%E8%AA%AC%E6%96%B0%E8%AA%9E-3-2.djvu%2F179`

```text
晏然王子敬問謝公嘉賔何如道季荅曰道季誠復鈔撮清悟嘉賔故自上王珣疾臨困問王武岡曰世論以我家領軍比誰武岡曰世以比王北中郎東亭轉臥向壁嘆曰人固不可以無年王孝伯道謝公濃至又曰長史虚劉尹秀謝公融王孝伯問謝公林公何如右軍謝曰右軍勝林公林公在司州前亦貴徹桓玄爲太傅大會朝臣畢集坐裁竟問王楨之曰我何如卿第七叔于時賔客爲之咽氣王徐徐荅曰亡叔是一時之標公是千載之英一坐懽然桓玄問劉太常曰我何如謝太傅劉荅曰公高太傅深又曰何如賢舅子敬荅曰樝梨橘柚各有其美舊以桓謙比殷仲文桓玄時仲文入桓於庭中望見之謂同坐曰我家中軍那得及此也
```

```text
晏然王子敬問謝公嘉賔何如道季荅曰道季誠復鈔撮清悟嘉賔故自上王珣疾臨困問王武岡曰世論以我家領軍比誰武岡曰世以比王北中郎東亭轉臥向壁嘆曰人固不可以無年王孝伯道謝公濃至又曰長史虚劉尹秀謝公融王孝伯問謝公林公何如右軍謝曰右軍勝林公林公在司州前亦貴徹⟦{{SKchar|3129}}⟧⟦{{SKchar|2593}}⟧爲太傅大會朝臣畢集坐裁竟問王楨之曰我何如卿第七叔于時賔客爲之咽氣王徐徐荅曰亡叔是一時之標公是千載之英一坐懽然⟦{{SKchar|3129}}⟧⟦{{SKchar|2593}}⟧問劉太常曰我何如謝太傅劉荅曰公高太傅深又曰何如賢舅子敬荅曰樝梨橘柚各有其美舊以⟦{{SKchar|3129}}⟧謙比殷仲文⟦{{SKchar|3129}}⟧玄時仲文入⟦{{SKchar|3129}}⟧於庭中望見之謂同坐曰我家中軍那得及此也
```

---

### 10-guizhen — 10-guizhen-011 — `non_exact_entry_opening`

- classification: `unresolved`
- confidence: `low`
- requires visual verification: `True`
- recommended action: Review the exact character/glyph and boundary context; no automatic repair is made.
- Kanripo opening key: `元帝過江猶好酒王茂弘與帝`
- Kanripo opening text (source spelling): `元帝過江猶好酒王茂弘與帝`
- Kanripo location: `content/processed/shishuo/chapters/chapter-10.md`; normalized line `927`; page `<pb:KR3l0002_SBCK_003-40b>`
- Wikisource match type: `prefix`
- Wikisource page: `Page:Sibu Congkan0463-劉義慶-世説新語-3-2.djvu/188`

```text
氏貪欲令婢路上儋糞平子諌之並言不可郭大怒謂平子曰昔夫人臨終以小郎囑新婦不以新婦囑小郎急捉衣⟦{{SKchar|3433}}⟧將與杖平子饒力爭得脱踰䆫而走元帝過江猶好酒王茂⟦{{SKchar|2592}}⟧與帝有舊常流涕諌帝許之命酌酒一酣從是遂斷謝鯤爲豫章太守從大將軍下至石頭敦謂鯤曰余不得復爲盛德之事矣鯤曰何爲其然但使自今巳後日亡日去耳敦又稱疾不朝鯤諭敦曰近者明公之舉雖欲大存社稷然四海之内實懷未逹若能朝天子使羣臣釋然萬物之心於是乃服仗民望以從衆懷盡沖𨓆以奉主上如斯則勲侔一匡名垂千載時人以爲名言元皇帝時
```

---

### 10-guizhen — 10-guizhen-015 — `unmatched_entry_opening`

- classification: `unresolved`
- confidence: `low`
- requires visual verification: `True`
- recommended action: Inspect the same-edition page witness and the relevant glyph/character reading before classifying as a textual variant or source gap.
- Kanripo opening key: `王丞相爲揚州遣八部從事之`
- Kanripo opening text (source spelling): `王丞相爲揚州遣八部從事之`
- Kanripo location: `content/processed/shishuo/chapters/chapter-10.md`; normalized line `960`; page `<pb:KR3l0002_SBCK_003-42a>`
- Wikisource match type: `none`
- Wikisource page: `not located`

```text
No aligned Wikisource reading.
```

---

### 10-guizhen — 10-guizhen-018 — `non_exact_entry_opening`

- classification: `unresolved`
- confidence: `low`
- requires visual verification: `True`
- recommended action: Review the exact character/glyph and boundary context; no automatic repair is made.
- Kanripo opening key: `小庾在荆州公朝大㑹問諸僚`
- Kanripo opening text (source spelling): `小庾在荆州公朝大㑹問諸僚`
- Kanripo location: `content/processed/shishuo/chapters/chapter-10.md`; normalized line `976`; page `<pb:KR3l0002_SBCK_003-42b>`
- Wikisource match type: `suffix`
- Wikisource page: `Page:Sibu Congkan0463-劉義慶-世説新語-3-2.djvu/192`

```text
爲亂階請從我家始峻遂止陸玩拜司空有人詣之索美酒得便自起㵼箸梁柱間地祝曰當今乏才以爾爲柱石之用莫傾人棟梁玩笑曰戢卿良箴小𢈔在荆州公朝大㑹問諸僚佐曰我欲爲漢高魏武何如一坐莫荅長史江虨曰願明公爲⟦{{SKchar|3129}}⟧文之事不願作漢高魏武也羅君章爲⟦{{SKchar|3129}}⟧宣武從事謝鎭西作江夏往檢校之羅既至初不問郡事徑就謝數日飲酒而還⟦{{SKchar|3129}}⟧公問有何事君章云不審公謂謝尚何似人⟦{{SKchar|3129}}⟧公曰仁祖是勝我許人君章云豈有勝公人而行非者故一無所問⟦{{SKchar|3129}}⟧公竒其意而不責也王右軍與王敬仁許⟦{{SKchar|2593}}⟧度並善二人亡後右軍爲論議更克孔
```

---

### 10-guizhen — 10-guizhen-019 — `unmatched_entry_opening`

- classification: `unresolved`
- confidence: `low`
- requires visual verification: `True`
- recommended action: Inspect the same-edition page witness and the relevant glyph/character reading before classifying as a textual variant or source gap.
- Kanripo opening key: `羅君章爲桓宣武從事謝鎭西`
- Kanripo opening text (source spelling): `羅君章爲桓宣武從事(爲部從事桓温臨州轉叅軍/含别傳曰刺史庾亮初命含)
謝鎭西`
- Kanripo location: `content/processed/shishuo/chapters/chapter-10.md`; normalized line `981`; page `<pb:KR3l0002_SBCK_003-43a>`
- Wikisource match type: `none`
- Wikisource page: `not located`

```text
No aligned Wikisource reading.
```

---

### 10-guizhen — 10-guizhen-020 — `non_exact_entry_opening`

- classification: `unresolved`
- confidence: `low`
- requires visual verification: `True`
- recommended action: Review the exact character/glyph and boundary context; no automatic repair is made.
- Kanripo opening key: `王右軍與王敬仁許玄度並善`
- Kanripo opening text (source spelling): `王右軍與王敬仁許玄度並善`
- Kanripo location: `content/processed/shishuo/chapters/chapter-10.md`; normalized line `987`; page `<pb:KR3l0002_SBCK_003-43a>`
- Wikisource match type: `prefix`
- Wikisource page: `Page:Sibu Congkan0463-劉義慶-世説新語-3-2.djvu/193`

```text
數日飲酒而還⟦{{SKchar|3129}}⟧公問有何事君章云不審公謂謝尚何似人⟦{{SKchar|3129}}⟧公曰仁祖是勝我許人君章云豈有勝公人而行非者故一無所問⟦{{SKchar|3129}}⟧公竒其意而不責也王右軍與王敬仁許⟦{{SKchar|2593}}⟧度並善二人亡後右軍爲論議更克孔巖誡之曰明府昔與王許周旋有情及逝沒之後無慎終之好民所不取右軍甚愧謝中郎在壽春敗臨奔走猶求玉帖鐙太傅在軍前後初無損益之言爾日猶云當今豈須煩此王大語東亭卿乃復論成不惡那得與僧彌戲殷覬病困看人政見半面殷荆州興晉陽之甲往與覬别涕零屬以消息所患覬荅曰我病自當差正憂汝患耳逺公在廬山中
```

---

### 10-guizhen — 10-guizhen-025 — `non_exact_entry_opening`

- classification: `unresolved`
- confidence: `low`
- requires visual verification: `True`
- recommended action: Review the exact character/glyph and boundary context; no automatic repair is made.
- Kanripo opening key: `桓南郡好獵每田狩車騎甚盛`
- Kanripo opening text (source spelling): `桓南郡好獵每田狩車騎甚盛`
- Kanripo location: `content/processed/shishuo/chapters/chapter-10.md`; normalized line `1013`; page `<pb:KR3l0002_SBCK_003-44b>`
- Wikisource match type: `suffix`
- Wikisource page: `Page:Sibu Congkan0463-劉義慶-世説新語-3-2.djvu/196`

```text
廬山中雖老講論不輟弟子中或有墮者逺公曰桑榆之光理無逺照但願朝陽之暉與時並明耳執經登坐諷誦朗畼詞色甚苦高足之徒皆肅然增敬⟦{{SKchar|3129}}⟧南郡好獵每田狩車騎甚盛五六十里中旌旗蔽隰騁良馬馳擊若飛雙甄所指不避陵壑或行陳不整麏兎騰逸參佐無不被繫束⟦{{SKchar|3129}}⟧道恭玄之族也時爲賊曹叅軍頗敢直言常自帶絳綿繩箸腰中玄問此何爲荅曰公獵好縛人士會當被縛手不能堪芒也⟦{{SKchar|2593}}⟧自此小差王緒王國寳相爲脣齒並上下權要王大不平其如此乃謂緒曰汝爲此歘歘曾不慮獄吏之爲貴乎⟦{{SKchar|3129}}⟧⟦{{SKchar|2593}}⟧欲以謝太傅宅爲營謝混曰召伯之
```

---

### 10-guizhen — 10-guizhen-027 — `non_exact_entry_opening`

- classification: `unresolved`
- confidence: `low`
- requires visual verification: `True`
- recommended action: Review the exact character/glyph and boundary context; no automatic repair is made.
- Kanripo opening key: `桓玄欲以謝太傅宅爲營謝混`
- Kanripo opening text (source spelling): `桓玄欲以謝太傅宅爲營謝混`
- Kanripo location: `content/processed/shishuo/chapters/chapter-10.md`; normalized line `1029`; page `<pb:KR3l0002_SBCK_003-45a>`
- Wikisource match type: `suffix`
- Wikisource page: `Page:Sibu Congkan0463-劉義慶-世説新語-3-2.djvu/197`

```text
好縛人士會當被縛手不能堪芒也⟦{{SKchar|2593}}⟧自此小差王緒王國寳相爲脣齒並上下權要王大不平其如此乃謂緒曰汝爲此歘歘曾不慮獄吏之爲貴乎⟦{{SKchar|3129}}⟧⟦{{SKchar|2593}}⟧欲以謝太傅宅爲營謝混曰召伯之仁猶惠及甘棠文靖之德更不保五畝之宅玄慙而止
```

---

### 10-guizhen — `probable_one_character_shift`

- classification: `unresolved`
- confidence: `medium`
- requires visual verification: `True`
- recommended action: Use page-level visual witnesses to determine whether this is a missing/extra passage, a glyph/character variant, or a segmentation difference. No textual repair is performed.
- Kanripo main characters: 1845
- Wikisource main characters: 1845
- length delta (Wikisource − Kanripo): 0
- sequence ratio: 0.990244
- Kanripo location: `content/processed/shishuo/chapters/chapter-10.md`; page markers `['<pb:KR3l0002_SBCK_003-37a>', '<pb:KR3l0002_SBCK_003-37b>', '<pb:KR3l0002_SBCK_003-38a>', '<pb:KR3l0002_SBCK_003-38b>', '<pb:KR3l0002_SBCK_003-39a>', '<pb:KR3l0002_SBCK_003-39b>', '<pb:KR3l0002_SBCK_003-40a>', '<pb:KR3l0002_SBCK_003-40b>', '<pb:KR3l0002_SBCK_003-41a>', '<pb:KR3l0002_SBCK_003-41b>', '<pb:KR3l0002_SBCK_003-42a>', '<pb:KR3l0002_SBCK_003-42b>', '<pb:KR3l0002_SBCK_003-43a>', '<pb:KR3l0002_SBCK_003-43b>', '<pb:KR3l0002_SBCK_003-44a>', '<pb:KR3l0002_SBCK_003-44b>', '<pb:KR3l0002_SBCK_003-45a>', '<pb:KR3l0002_SBCK_003-45b>']`
- Wikisource page range: `Page:Sibu Congkan0463-劉義慶-世説新語-3-2.djvu/180` through `Page:Sibu Congkan0463-劉義慶-世説新語-3-2.djvu/197` (18 pages)
- Wikisource source URL range: `https://zh.wikisource.org/wiki/Page%3ASibu%20Congkan0463-%E5%8A%89%E7%BE%A9%E6%85%B6-%E4%B8%96%E8%AA%AC%E6%96%B0%E8%AA%9E-3-2.djvu%2F180` through `https://zh.wikisource.org/wiki/Page%3ASibu%20Congkan0463-%E5%8A%89%E7%BE%A9%E6%85%B6-%E4%B8%96%E8%AA%AC%E6%96%B0%E8%AA%9E-3-2.djvu%2F197`

```text
擊若飛雙甄所指不避陵壑或行陳不整麏兎騰逸參佐無不被繫束桓道恭玄之族也時爲賊曹叅軍頗敢直言常自帶絳綿繩箸腰中玄問此何爲荅曰公獵好縛人士會當被縛手不能堪芒也玄自此小差王緒王國寳相爲脣齒並上下權要王大不平其如此乃謂緒曰汝爲此歘歘曾不慮獄吏之爲貴乎桓玄欲以謝太傅宅爲營謝混曰召伯之仁猶惠及甘棠文靖之德更不保五畝之宅玄慙而止
```

```text
擊若飛雙甄所指不避陵壑或行陳不整麏兎騰逸參佐無不被繫束⟦{{SKchar|3129}}⟧道恭玄之族也時爲賊曹叅軍頗敢直言常自帶絳綿繩箸腰中玄問此何爲荅曰公獵好縛人士會當被縛手不能堪芒也⟦{{SKchar|2593}}⟧自此小差王緒王國寳相爲脣齒並上下權要王大不平其如此乃謂緒曰汝爲此歘歘曾不慮獄吏之爲貴乎⟦{{SKchar|3129}}⟧⟦{{SKchar|2593}}⟧欲以謝太傅宅爲營謝混曰召伯之仁猶惠及甘棠文靖之德更不保五畝之宅玄慙而止
```

---

### 11-jiewu — 11-jiewu-004 — `non_exact_entry_opening`

- classification: `unresolved`
- confidence: `low`
- requires visual verification: `True`
- recommended action: Review the exact character/glyph and boundary context; no automatic repair is made.
- Kanripo opening key: `魏武征袁本初治裝餘有數十`
- Kanripo opening text (source spelling): `魏武征袁本初治裝餘有數十`
- Kanripo location: `content/processed/shishuo/chapters/chapter-11.md`; normalized line `1058`; page `<pb:KR3l0002_SBCK_003-46b>`
- Wikisource match type: `suffix`
- Wikisource page: `Page:Sibu Congkan0463-劉義慶-世説新語-3-2.djvu/200`

```text
絶幼婦少女也於字爲妙外孫女子也於字爲好䪡臼受辛也於字爲辭所謂絶妙好辭也魏武亦記之與脩同乃歎曰我才不及卿乃覺三十里魏武征𡊮本初治裝餘有數十斛竹片咸長數寸衆云並不堪用正令燒除太祖思所以用之謂可為竹椑楯而未顯其言馳使問主簿楊德祖應聲荅之與帝心同衆伏其辯悟王敦引軍垂至大桁明帝自出中堂温嶠為丹陽尹帝令斷大桁故未斷帝大怒瞋目左右莫不悚懼召諸公來嶠至不謝但求酒炙王導須吏至徒跣下地謝曰天威在顔遂使温嶠不容得謝嶠於是下謝帝廼釋然諸公共嘆王機悟名言郄司空在
```

---

### 11-jiewu — 11-jiewu-006 — `unmatched_entry_opening`

- classification: `unresolved`
- confidence: `low`
- requires visual verification: `True`
- recommended action: Inspect the same-edition page witness and the relevant glyph/character reading before classifying as a textual variant or source gap.
- Kanripo opening key: `郄司空在北府桓宣武惡其居`
- Kanripo opening text (source spelling): `郄司空在北府桓宣武惡其居`
- Kanripo location: `content/processed/shishuo/chapters/chapter-11.md`; normalized line `1069`; page `<pb:KR3l0002_SBCK_003-47a>`
- Wikisource match type: `none`
- Wikisource page: `not located`

```text
No aligned Wikisource reading.
```

---

### 11-jiewu — `probable_one_character_shift`

- classification: `unresolved`
- confidence: `medium`
- requires visual verification: `True`
- recommended action: Use page-level visual witnesses to determine whether this is a missing/extra passage, a glyph/character variant, or a segmentation difference. No textual repair is performed.
- Kanripo main characters: 552
- Wikisource main characters: 552
- length delta (Wikisource − Kanripo): 0
- sequence ratio: 0.992754
- Kanripo location: `content/processed/shishuo/chapters/chapter-11.md`; page markers `['<pb:KR3l0002_SBCK_003-46a>', '<pb:KR3l0002_SBCK_003-46b>', '<pb:KR3l0002_SBCK_003-47a>', '<pb:KR3l0002_SBCK_003-47b>']`
- Wikisource page range: `Page:Sibu Congkan0463-劉義慶-世説新語-3-2.djvu/198` through `Page:Sibu Congkan0463-劉義慶-世説新語-3-2.djvu/202` (5 pages)
- Wikisource source URL range: `https://zh.wikisource.org/wiki/Page%3ASibu%20Congkan0463-%E5%8A%89%E7%BE%A9%E6%85%B6-%E4%B8%96%E8%AA%AC%E6%96%B0%E8%AA%9E-3-2.djvu%2F198` through `https://zh.wikisource.org/wiki/Page%3ASibu%20Congkan0463-%E5%8A%89%E7%BE%A9%E6%85%B6-%E4%B8%96%E8%AA%AC%E6%96%B0%E8%AA%9E-3-2.djvu%2F202`

```text
字王正嫌門大也人餉魏武一桮酪魏武噉少許葢頭上題合字以示衆衆莫能解次至楊脩脩便噉曰公敎人噉一口也復何疑魏武嘗過曹娥碑下楊脩從碑背上見題作黄絹幼婦外孫䪡臼八字魏武謂脩曰解不荅曰解魏武曰卿未可言待我思之行三十里魏武乃曰吾巳得令脩别記所知脩曰黄絹色絲也於字爲絶幼婦少女也於字爲妙外孫女子也於字爲好䪡臼受辛也於字爲辭所謂絶妙好辭也魏武亦記之與脩同乃歎曰我才不及卿乃覺三十里魏武征袁本初治裝餘有數十斛竹片咸長數寸衆云並不堪用正令燒除太祖思所以用之謂可為竹椑楯而未顯其言馳使問主簿楊德祖應聲荅之與帝心同衆伏其辯悟王敦引軍垂至大桁明帝自出中堂温嶠為丹陽尹帝令斷大桁故未斷帝大怒瞋目左右莫不悚懼召諸公來嶠至不謝但求酒炙王導須吏至徒跣下地謝曰天威在顔遂使温嶠不容得謝嶠於是下謝帝廼釋然諸公共嘆王機悟名
```

```text
字王正嫌門大也人餉魏武一桮酪魏武噉少許葢頭上題合字以示衆衆莫能解次至楊脩脩便噉曰公敎人噉一口也復何疑魏武嘗過曹娥碑下楊脩從碑背上見題作黄絹幼婦外孫䪡臼八字魏武謂脩曰解不荅曰解魏武曰卿未可言待我思之行三十里魏武乃曰吾巳得令脩别記所知脩曰黄絹色𢇁也於字爲絶幼婦少女也於字爲妙外孫女子也於字爲好䪡臼受辛也於字爲辭所謂絶妙好辭也魏武亦記之與脩同乃歎曰我才不及卿乃覺三十里魏武征𡊮本初治裝餘有數十斛竹片咸長數寸衆云並不堪用正令燒除太祖思所以用之謂可為竹椑楯而未顯其言馳使問主簿楊德祖應聲荅之與帝心同衆伏其辯悟王敦引軍垂至大桁明帝自出中堂温嶠為丹陽尹帝令斷大桁故未斷帝大怒瞋目左右莫不悚懼召諸公來嶠至不謝但求酒炙王導須吏至徒跣下地謝曰天威在顔遂使温嶠不容得謝嶠於是下謝帝廼釋然諸公共嘆王機悟名
```

---

### 12-suhui — 12-suhui-007 — `unmatched_entry_opening`

- classification: `unresolved`
- confidence: `low`
- requires visual verification: `True`
- recommended action: Inspect the same-edition page witness and the relevant glyph/character reading before classifying as a textual variant or source gap.
- Kanripo opening key: `桓宣武薨桓南郡年五歲服始`
- Kanripo opening text (source spelling): `桓宣武薨桓南郡年五歲服始`
- Kanripo location: `content/processed/shishuo/chapters/chapter-12.md`; normalized line `1117`; page `<pb:KR3l0002_SBCK_003-49a>`
- Wikisource match type: `none`
- Wikisource page: `not located`

```text
No aligned Wikisource reading.
```

---

### 12-suhui — `annotation_range_difference`

- classification: `unresolved`
- confidence: `medium`
- requires visual verification: `True`
- recommended action: Use page-level visual witnesses to determine whether this is a missing/extra passage, a glyph/character variant, or a segmentation difference. No textual repair is performed.
- Kanripo main characters: 563
- Wikisource main characters: 563
- length delta (Wikisource − Kanripo): 0
- sequence ratio: 0.987567
- Kanripo location: `content/processed/shishuo/chapters/chapter-12.md`; page markers `['<pb:KR3l0002_SBCK_003-48a>', '<pb:KR3l0002_SBCK_003-48b>', '<pb:KR3l0002_SBCK_003-49a>', '<pb:KR3l0002_SBCK_003-49b>']`
- Wikisource page range: `Page:Sibu Congkan0463-劉義慶-世説新語-3-2.djvu/202` through `Page:Sibu Congkan0463-劉義慶-世説新語-3-2.djvu/206` (5 pages)
- Wikisource source URL range: `https://zh.wikisource.org/wiki/Page%3ASibu%20Congkan0463-%E5%8A%89%E7%BE%A9%E6%85%B6-%E4%B8%96%E8%AA%AC%E6%96%B0%E8%AA%9E-3-2.djvu%2F202` through `https://zh.wikisource.org/wiki/Page%3ASibu%20Congkan0463-%E5%8A%89%E7%BE%A9%E6%85%B6-%E4%B8%96%E8%AA%AC%E6%96%B0%E8%AA%9E-3-2.djvu%2F206`

```text
見日不見長安司空顧和與時賢共清言張玄之顧敷是中外孫年並七歲在牀邊戲于時聞語神情如不相屬瞑於燈下二兒共叙客主之言都無遺失顧公越席而提其耳曰不意衰宗復生此寳韓康伯數歲家酷貧至大寒止得襦母殷夫人自成之令康伯捉熨斗謂康伯曰且箸襦尋作複㡓兒云巳足不須複㡓也毋問其故荅曰火在熨斗中而柄熱今旣箸𥜗下亦當煗故不須耳毋甚異之知爲國噐晉孝武年十二時冬天晝日不箸複衣但箸單練衫五六重夜則累茵褥謝公諌曰聖體冝令有常陛下晝過冷夜過熱恐非攝養之術帝曰晝動夜静謝公出嘆曰上理不減先帝桓宣武薨桓南郡年五歲服始除桓車騎與送故文武别因指語南郡此皆汝家故吏佐玄應聲慟哭酸感傍人車騎每自目巳坐曰靈寳成人當以此坐還之鞠愛過於所生
```

```text
見日不見長安司空顧和與時賢共清言張玄之顧敷是中外孫年並七歲在牀邊戲于時聞語神情如不相屬瞑於燈下二兒共叙客主之言都無遺失顧公越席而提其耳曰不意衰宗復生此寳韓康伯數歲家酷貧至大寒止得襦母殷夫人自成之令康伯捉熨斗謂康伯曰且箸襦尋作複㡓兒云巳足不須⟦{{SKchar|3435}}⟧㡓也毋問其故荅曰火在熨斗中而柄⟦{{SKchar|3289}}⟧今旣箸⟦{{SKchar|383}}⟧下亦當煗故不須耳毋甚異之知爲國噐晉孝武年十二時冬天晝日不箸複衣但箸單練衫五六重夜則累茵褥謝公諌曰聖體冝令有常陛下晝過冷夜過⟦{{SKchar|3289}}⟧恐非攝養之術帝曰晝動夜静謝公出嘆曰上理不減先帝⟦{{SKchar|3129}}⟧宣武薨⟦{{SKchar|3129}}⟧南郡年五歲服始除⟦{{SKchar|3129}}⟧車騎與送故文武别因指語南郡此皆汝家故吏佐玄應聲慟哭酸感傍人車騎每自目巳坐曰靈寳成人當以此坐還之鞠愛過於所生
```

---

### 13-haoshuang — 13-haoshuang-007 — `non_exact_entry_opening`

- classification: `unresolved`
- confidence: `low`
- requires visual verification: `True`
- recommended action: Review the exact character/glyph and boundary context; no automatic repair is made.
- Kanripo opening key: `庾穉恭既常有中原之志文康`
- Kanripo opening text (source spelling): `庾穉恭既常有中原之志文康`
- Kanripo location: `content/processed/shishuo/chapters/chapter-13.md`; normalized line `1147`; page `<pb:KR3l0002_SBCK_003-50b>`
- Wikisource match type: `suffix`
- Wikisource page: `Page:Sibu Congkan0463-劉義慶-世説新語-3-2.djvu/208`

```text
樹置先遣㕘軍告朝廷諷㫖時賢祖車騎尚未鎮夀春瞋目厲聲語使人曰卿語阿黑何敢不遜催攝面去須⟦{{SKchar|3099}}⟧不爾我將三千兵槊腳令上王聞之而止⟦{{SKchar|2928}}⟧穉恭既常有中原之志文康時權重未在巳及季堅作相忌兵畏禍與穉恭歷同異者久之乃果行傾荆漢之力窮舟車之勢師次于襄陽大㑹叅佐陳其旌甲親授弧矢曰我之此行若此射矣遂三起三疊徒衆屬目其氣十倍⟦{{SKchar|3129}}⟧宣武平蜀集叅僚置酒於李勢殿巴蜀搢紳莫不來萃⟦{{SKchar|3129}}⟧既素有雄情爽氣加爾日音調英發叙古今成敗由人存亡繫才其狀磊落一坐嘆賞既散諸人追味餘言于時尋陽周馥曰恨卿
```

---

### 13-haoshuang — 13-haoshuang-008 — `non_exact_entry_opening`

- classification: `unresolved`
- confidence: `low`
- requires visual verification: `True`
- recommended action: Review the exact character/glyph and boundary context; no automatic repair is made.
- Kanripo opening key: `桓宣武平蜀集叅僚置酒於李`
- Kanripo opening text (source spelling): `桓宣武平蜀集叅僚置酒於李`
- Kanripo location: `content/processed/shishuo/chapters/chapter-13.md`; normalized line `1159`; page `<pb:KR3l0002_SBCK_003-51a>`
- Wikisource match type: `suffix`
- Wikisource page: `Page:Sibu Congkan0463-劉義慶-世説新語-3-2.djvu/209`

```text
恭歷同異者久之乃果行傾荆漢之力窮舟車之勢師次于襄陽大㑹叅佐陳其旌甲親授弧矢曰我之此行若此射矣遂三起三疊徒衆屬目其氣十倍⟦{{SKchar|3129}}⟧宣武平蜀集叅僚置酒於李勢殿巴蜀搢紳莫不來萃⟦{{SKchar|3129}}⟧既素有雄情爽氣加爾日音調英發叙古今成敗由人存亡繫才其狀磊落一坐嘆賞既散諸人追味餘言于時尋陽周馥曰恨卿軰不見王大將軍⟦{{SKchar|3129}}⟧公讀高士傳至於陵仲子便擲去曰誰能作此溪刻自處⟦{{SKchar|3129}}⟧石䖍司空豁之長庶也小字鎮惡年十七八未被舉而童⟦{{SKchar|1452}}⟧巳呼為鎮惡郎嘗住宣武齋頭從征枋頭車騎沖沒陳左右莫能先救宣武謂曰汝叔落
```

---

### 13-haoshuang — 13-haoshuang-009 — `non_exact_entry_opening`

- classification: `unresolved`
- confidence: `low`
- requires visual verification: `True`
- recommended action: Review the exact character/glyph and boundary context; no automatic repair is made.
- Kanripo opening key: `桓公讀高士傳至於陵仲子便`
- Kanripo opening text (source spelling): `桓公讀高士傳至於陵仲子便`
- Kanripo location: `content/processed/shishuo/chapters/chapter-13.md`; normalized line `1164`; page `<pb:KR3l0002_SBCK_003-51a>`
- Wikisource match type: `suffix`
- Wikisource page: `Page:Sibu Congkan0463-劉義慶-世説新語-3-2.djvu/209`

```text
萃⟦{{SKchar|3129}}⟧既素有雄情爽氣加爾日音調英發叙古今成敗由人存亡繫才其狀磊落一坐嘆賞既散諸人追味餘言于時尋陽周馥曰恨卿軰不見王大將軍⟦{{SKchar|3129}}⟧公讀高士傳至於陵仲子便擲去曰誰能作此溪刻自處⟦{{SKchar|3129}}⟧石䖍司空豁之長庶也小字鎮惡年十七八未被舉而童⟦{{SKchar|1452}}⟧巳呼為鎮惡郎嘗住宣武齋頭從征枋頭車騎沖沒陳左右莫能先救宣武謂曰汝叔落賊汝知不石䖍聞之氣甚奮命朱辟為副策馬於數萬衆中莫有抗者徑致沖還三軍嘆服河朔後以其名斷瘧陳林道在西岸都下諸人共要至牛渚會陳理既佳人欲共言折陳以如意拄頰望雞籠山嘆曰
```

---

### 13-haoshuang — 13-haoshuang-010 — `non_exact_entry_opening`

- classification: `unresolved`
- confidence: `low`
- requires visual verification: `True`
- recommended action: Review the exact character/glyph and boundary context; no automatic repair is made.
- Kanripo opening key: `桓石䖍司空豁之長庶也小字`
- Kanripo opening text (source spelling): `桓石䖍司空豁之長庶也(弟累遷荆州刺史贈司空/豁别傳曰豁字朗子温之)
小字`
- Kanripo location: `content/processed/shishuo/chapters/chapter-13.md`; normalized line `1170`; page `<pb:KR3l0002_SBCK_003-51b>`
- Wikisource match type: `suffix`
- Wikisource page: `Page:Sibu Congkan0463-劉義慶-世説新語-3-2.djvu/210`

```text
存亡繫才其狀磊落一坐嘆賞既散諸人追味餘言于時尋陽周馥曰恨卿軰不見王大將軍⟦{{SKchar|3129}}⟧公讀高士傳至於陵仲子便擲去曰誰能作此溪刻自處⟦{{SKchar|3129}}⟧石䖍司空豁之長庶也小字鎮惡年十七八未被舉而童⟦{{SKchar|1452}}⟧巳呼為鎮惡郎嘗住宣武齋頭從征枋頭車騎沖沒陳左右莫能先救宣武謂曰汝叔落賊汝知不石䖍聞之氣甚奮命朱辟為副策馬於數萬衆中莫有抗者徑致沖還三軍嘆服河朔後以其名斷瘧陳林道在西岸都下諸人共要至牛渚會陳理既佳人欲共言折陳以如意拄頰望雞籠山嘆曰孫伯符志業不遂於是竟坐不得談王司州在謝公坐詠入
```

---

### 13-haoshuang — 13-haoshuang-012 — `non_exact_entry_opening`

- classification: `unresolved`
- confidence: `low`
- requires visual verification: `True`
- recommended action: Review the exact character/glyph and boundary context; no automatic repair is made.
- Kanripo opening key: `王司州在謝公坐詠入不言兮`
- Kanripo opening text (source spelling): `王司州在謝公坐詠入不言兮`
- Kanripo location: `content/processed/shishuo/chapters/chapter-13.md`; normalized line `1185`; page `<pb:KR3l0002_SBCK_003-52a>`
- Wikisource match type: `prefix`
- Wikisource page: `Page:Sibu Congkan0463-劉義慶-世説新語-3-2.djvu/211`

```text
服河朔後以其名斷瘧陳林道在西岸都下諸人共要至牛渚會陳理既佳人欲共言折陳以如意拄頰望雞籠山嘆曰孫伯符志業不遂於是竟坐不得談王司州在謝公坐詠入不言⟦{{SKchar|2599}}⟧出不辭乗回風⟦{{SKchar|2599}}⟧載雲旗語人云當爾時覺一坐無人⟦{{SKchar|3129}}⟧⟦{{SKchar|2593}}⟧西下入石頭外白司馬梁王奔叛玄時事形巳濟在平乗上笳鼔並作直高詠云簫管有遺音梁王安在哉宋臨川王義慶撰梁劉孝標注
```

---

### 13-haoshuang — 13-haoshuang-013 — `non_exact_entry_opening`

- classification: `unresolved`
- confidence: `low`
- requires visual verification: `True`
- recommended action: Review the exact character/glyph and boundary context; no automatic repair is made.
- Kanripo opening key: `桓玄西下入石頭外白司馬梁`
- Kanripo opening text (source spelling): `桓玄西下入石頭外白司馬梁`
- Kanripo location: `content/processed/shishuo/chapters/chapter-13.md`; normalized line `1188`; page `<pb:KR3l0002_SBCK_003-52b>`
- Wikisource match type: `suffix`
- Wikisource page: `Page:Sibu Congkan0463-劉義慶-世説新語-3-2.djvu/212`

```text
以如意拄頰望雞籠山嘆曰孫伯符志業不遂於是竟坐不得談王司州在謝公坐詠入不言⟦{{SKchar|2599}}⟧出不辭乗回風⟦{{SKchar|2599}}⟧載雲旗語人云當爾時覺一坐無人⟦{{SKchar|3129}}⟧⟦{{SKchar|2593}}⟧西下入石頭外白司馬梁王奔叛玄時事形巳濟在平乗上笳鼔並作直高詠云簫管有遺音梁王安在哉宋臨川王義慶撰梁劉孝標注
```

---

### 14-rongzhi — 14-rongzhi-003 — `non_exact_entry_opening`

- classification: `unresolved`
- confidence: `low`
- requires visual verification: `True`
- recommended action: Review the exact character/glyph and boundary context; no automatic repair is made.
- Kanripo opening key: `魏明帝使后弟毛曽與夏侯玄`
- Kanripo opening text (source spelling): `魏明帝使后弟毛曽與夏侯玄`
- Kanripo location: `content/processed/shishuo/chapters/chapter-14.md`; normalized line `1212`; page `<pb:KR3l0002_SBCK_002-1b>`
- Wikisource match type: `prefix`
- Wikisource page: `Page:Sibu Congkan0464-劉義慶-世説新語-3-3.djvu/3`

```text
雅望非常然牀頭捉刀人此乃英雄也魏武聞之追殺此使何平叔美姿儀面至白魏眀帝疑其傅粉正夏月與⟦{{SKchar|3289}}⟧湯餅既噉大汗出以朱衣自拭色轉皎然魏明帝使后弟毛曽與夏侯⟦{{SKchar|2593}}⟧共坐時人謂蒹葭倚玉⟦{{SKchar|3141}}⟧時人目夏侯太初朗朗如日月之入懷李安國穨唐如玉山之⟦{{SKchar|2877}}⟧崩嵇康身長七尺八寸風姿特秀見者歎曰蕭蕭肅肅爽朗清舉或云肅肅如松下風髙而徐引山公曰嵇叔夜之為人也巖巖若孤松之獨立其醉也傀俄若玉山之將崩裴令公目王安豐眼爛爛如巖下電潘岳妙有姿容好神情少時挾彈出洛陽道婦人遇者莫不連手共縈之左太沖絶醜
```

---

### 14-rongzhi — 14-rongzhi-008 — `non_exact_entry_opening`

- classification: `unresolved`
- confidence: `low`
- requires visual verification: `True`
- recommended action: Review the exact character/glyph and boundary context; no automatic repair is made.
- Kanripo opening key: `王夷甫容貌整麗妙於談玄恒`
- Kanripo opening text (source spelling): `王夷甫容貌整麗妙於談玄恒`
- Kanripo location: `content/processed/shishuo/chapters/chapter-14.md`; normalized line `1232`; page `<pb:KR3l0002_SBCK_002-2b>`
- Wikisource match type: `prefix`
- Wikisource page: `Page:Sibu Congkan0464-劉義慶-世説新語-3-3.djvu/5`

```text
豐眼爛爛如巖下電潘岳妙有姿容好神情少時挾彈出洛陽道婦人遇者莫不連手共縈之左太沖絶醜亦復效岳遊遨於是羣嫗齊共亂唾之委頓而返王夷甫容貌整麗妙於談𤣥恒捉白玉柄麈尾與手都無分别潘安仁夏侯湛並有美容喜同行時人謂之連璧裴令公有儁容姿一旦有疾至困惠帝使王夷甫徃看裴方向壁臥聞王使至強回視之王出語人曰𩀱眸閃閃若巖下電精神挺動體中故小惡有人語王戎曰嵇延祖卓卓如野鶴之在雞羣荅曰君未見其父耳裴令公有儁容儀脫冠冕麤服亂頭皆好時人以為玉人見者曰見裴叔則如玉山上行光
```

---

### 14-rongzhi — 14-rongzhi-018 — `non_exact_entry_opening`

- classification: `unresolved`
- confidence: `low`
- requires visual verification: `True`
- recommended action: Review the exact character/glyph and boundary context; no automatic repair is made.
- Kanripo opening key: `庾子嵩長不滿七尺腰帶十圍`
- Kanripo opening text (source spelling): `庾子嵩長不滿七尺腰帶十圍`
- Kanripo location: `content/processed/shishuo/chapters/chapter-14.md`; normalized line `1257`; page `<pb:KR3l0002_SBCK_002-3b>`
- Wikisource match type: `suffix`
- Wikisource page: `Page:Sibu Congkan0464-劉義慶-世説新語-3-3.djvu/7`

```text
平子還語人曰今日之行觸目見琳琅珠玉王丞相見衛洗馬曰居然有羸形雖復終日調畼若不堪羅綺王大將軍稱太尉處衆人中似珠玉在瓦石間𢈔子嵩長不滿七尺腰帶十圍頽然自放衛玠從豫章至下都人久聞其名觀者如堵牆玠先有羸疾體不堪勞遂成病而死時人謂看殺衛玠周伯仁道桓茂倫嶔﨑歷落可笑人或云謝㓜輿言周侯說王長史父形貌既偉雅懐有槩保而用之可作諸許物也祖士少見衛君長云此人有旄仗下形石頭事故朝廷傾覆温忠武與⟦{{SKchar|2928}}⟧文康投陶公求救陶公云肅祖顧命不見及且蘇峻作亂釁由諸⟦{{SKchar|2928}}⟧誅其兄弟不足以
```

---

### 14-rongzhi — 14-rongzhi-024 — `non_exact_entry_opening`

- classification: `unresolved`
- confidence: `low`
- requires visual verification: `True`
- recommended action: Review the exact character/glyph and boundary context; no automatic repair is made.
- Kanripo opening key: `庾太尉在武昌秋夜氣佳景清`
- Kanripo opening text (source spelling): `庾太尉在武昌秋夜氣佳景清`
- Kanripo location: `content/processed/shishuo/chapters/chapter-14.md`; normalized line `1279`; page `<pb:KR3l0002_SBCK_002-4b>`
- Wikisource match type: `suffix`
- Wikisource page: `Page:Sibu Congkan0464-劉義慶-世説新語-3-3.djvu/9`

```text
時𢈔在温船後聞之憂怖無計别日温勸𢈔見陶𢈔猶豫未能徃温曰溪狗我所悉卿但見之必無憂也𢈔風姿神貌陶一見便改觀談宴竟日愛重頓至𢈔太尉在武昌秋夜氣佳景清使吏殷浩王胡之之徒登南樓理詠音調始遒聞函道中有屐聲甚厲定是𢈔公俄而率左右十許人步來諸賢欲起避之公徐云諸君少住老子於此處興復不淺因便據胡牀與諸人詠謔竟坐甚得任樂後王逸少下與丞相言及此事丞相曰元規爾時風範不得不小穨右軍荅曰唯丘壑獨存王敬豫有美形問訊王公王公撫其肩曰阿奴恨才不稱又云敬豫事事似王公王右軍見
```

---

### 14-rongzhi — 14-rongzhi-026 — `unmatched_entry_opening`

- classification: `unresolved`
- confidence: `low`
- requires visual verification: `True`
- recommended action: Inspect the same-edition page witness and the relevant glyph/character reading before classifying as a textual variant or source gap.
- Kanripo opening key: `王右軍見杜弘治歎曰面如凝`
- Kanripo opening text (source spelling): `王右軍見杜弘治歎曰面如凝`
- Kanripo location: `content/processed/shishuo/chapters/chapter-14.md`; normalized line `1291`; page `<pb:KR3l0002_SBCK_002-5a>`
- Wikisource match type: `none`
- Wikisource page: `not located`

```text
No aligned Wikisource reading.
```

---

### 14-rongzhi — 14-rongzhi-027 — `unmatched_entry_opening`

- classification: `unresolved`
- confidence: `low`
- requires visual verification: `True`
- recommended action: Inspect the same-edition page witness and the relevant glyph/character reading before classifying as a textual variant or source gap.
- Kanripo opening key: `劉尹道桓公鬢如反猬皮眉如`
- Kanripo opening text (source spelling): `劉尹道桓公鬢如反猬皮眉如`
- Kanripo location: `content/processed/shishuo/chapters/chapter-14.md`; normalized line `1295`; page `<pb:KR3l0002_SBCK_002-5a>`
- Wikisource match type: `none`
- Wikisource page: `not located`

```text
No aligned Wikisource reading.
```

---

### 14-rongzhi — 14-rongzhi-037 — `unmatched_entry_opening`

- classification: `unresolved`
- confidence: `low`
- requires visual verification: `True`
- recommended action: Inspect the same-edition page witness and the relevant glyph/character reading before classifying as a textual variant or source gap.
- Kanripo opening key: `謝公云見林公雙眼黯黯明黒`
- Kanripo opening text (source spelling): `謝公云見林公雙眼黯黯明黒`
- Kanripo location: `content/processed/shishuo/chapters/chapter-14.md`; normalized line `1325`; page `<pb:KR3l0002_SBCK_002-6b>`
- Wikisource match type: `none`
- Wikisource page: `not located`

```text
No aligned Wikisource reading.
```

---

### 14-rongzhi — 14-rongzhi-038 — `non_exact_entry_opening`

- classification: `unresolved`
- confidence: `low`
- requires visual verification: `True`
- recommended action: Review the exact character/glyph and boundary context; no automatic repair is made.
- Kanripo opening key: `庾長仁與諸弟入吳欲住亭中`
- Kanripo opening text (source spelling): `庾長仁與諸弟入吳欲住亭中`
- Kanripo location: `content/processed/shishuo/chapters/chapter-14.md`; normalized line `1327`; page `<pb:KR3l0002_SBCK_002-6b>`
- Wikisource match type: `suffix`
- Wikisource page: `Page:Sibu Congkan0464-劉義慶-世説新語-3-3.djvu/13`

```text
來軒軒如朝霞舉謝車騎道謝公遊肆復無乃髙唱但恭坐捻鼻顧睞便自有⟦{{SKchar|3462}}⟧處山澤閒儀謝公云見林公⟦{{SKchar|2814}}⟧眼黯黯明黒孫興公見林公稜稜露其爽⟦{{SKchar|2928}}⟧長仁與諸弟入吳欲住亭中⟦{{SKchar|2862}}⟧諸弟先上見羣小滿屋都無相避意長仁曰我試觀之乃䇿杖將一小兒始入門諸客望其神姿一時𨓆匿有人歎王恭形茂者云濯濯如春月柳
```

---

### 14-rongzhi — `probable_one_character_shift`

- classification: `unresolved`
- confidence: `medium`
- requires visual verification: `True`
- recommended action: Use page-level visual witnesses to determine whether this is a missing/extra passage, a glyph/character variant, or a segmentation difference. No textual repair is performed.
- Kanripo main characters: 1417
- Wikisource main characters: 1417
- length delta (Wikisource − Kanripo): 0
- sequence ratio: 0.983063
- Kanripo location: `content/processed/shishuo/chapters/chapter-14.md`; page markers `['<pb:KR3l0002_SBCK_002-1b>', '<pb:KR3l0002_SBCK_002-2a>', '<pb:KR3l0002_SBCK_002-2b>', '<pb:KR3l0002_SBCK_002-3a>', '<pb:KR3l0002_SBCK_002-3b>', '<pb:KR3l0002_SBCK_002-4a>', '<pb:KR3l0002_SBCK_002-4b>', '<pb:KR3l0002_SBCK_002-5a>', '<pb:KR3l0002_SBCK_002-5b>', '<pb:KR3l0002_SBCK_002-6a>', '<pb:KR3l0002_SBCK_002-6b>', '<pb:KR3l0002_SBCK_002-7a>']`
- Wikisource page range: `Page:Sibu Congkan0464-劉義慶-世説新語-3-3.djvu/2` through `Page:Sibu Congkan0464-劉義慶-世説新語-3-3.djvu/14` (13 pages)
- Wikisource source URL range: `https://zh.wikisource.org/wiki/Page%3ASibu%20Congkan0464-%E5%8A%89%E7%BE%A9%E6%85%B6-%E4%B8%96%E8%AA%AC%E6%96%B0%E8%AA%9E-3-3.djvu%2F2` through `https://zh.wikisource.org/wiki/Page%3ASibu%20Congkan0464-%E5%8A%89%E7%BE%A9%E6%85%B6-%E4%B8%96%E8%AA%AC%E6%96%B0%E8%AA%9E-3-3.djvu%2F14`

```text
魏武將見匈奴使自以形陋不足雄逺國使崔季珪代帝自捉刀立牀頭既畢令閒諜問曰魏王何如匈奴使荅曰魏王雅望非常然牀頭捉刀人此乃英雄也魏武聞之追殺此使何平叔美姿儀面至白魏眀帝疑其傅粉正夏月與熱湯餅既噉大汗出以朱衣自拭色轉皎然魏明帝使后弟毛曽與夏侯玄共坐時人謂蒹葭倚玉樹時人目夏侯太初朗朗如日月之入懷李安國穨唐如玉山之将崩嵇康身長七尺八寸風姿特秀見者歎曰蕭蕭肅肅爽朗清舉或云肅肅如松下風髙而徐引山公曰嵇叔夜之為人也巖巖若孤松之獨立其醉也傀俄若玉山之將崩裴令公目王安豐眼爛爛如巖下電潘岳妙有姿容好神情少時挾彈出洛陽道婦人遇者莫不連手共縈之左太沖絶醜亦復效岳遊遨於是羣嫗齊共亂唾之委頓而返王夷甫容貌整麗妙於談玄恒捉白玉柄麈尾與手都無分别
```

```text
魏武將見匈奴使自以形陋不足雄逺國使崔季珪代帝自捉刀立牀頭既畢令閒諜問曰魏王何如匈奴使荅曰魏王雅望非常然牀頭捉刀人此乃英雄也魏武聞之追殺此使何平叔美姿儀面至白魏眀帝疑其傅粉正夏月與⟦{{SKchar|3289}}⟧湯餅既噉大汗出以朱衣自拭色轉皎然魏明帝使后弟毛曽與夏侯⟦{{SKchar|2593}}⟧共坐時人謂蒹葭倚玉⟦{{SKchar|3141}}⟧時人目夏侯太初朗朗如日月之入懷李安國穨唐如玉山之⟦{{SKchar|2877}}⟧崩嵇康身長七尺八寸風姿特秀見者歎曰蕭蕭肅肅爽朗清舉或云肅肅如松下風髙而徐引山公曰嵇叔夜之為人也巖巖若孤松之獨立其醉也傀俄若玉山之將崩裴令公目王安豐眼爛爛如巖下電潘岳妙有姿容好神情少時挾彈出洛陽道婦人遇者莫不連手共縈之左太沖絶醜亦復效岳遊遨於是羣嫗齊共亂唾之委頓而返王夷甫容貌整麗妙於談𤣥恒捉白玉柄麈尾與手都無分别
```

---

### 16-qixian — 16-qixian-004 — `unmatched_entry_opening`

- classification: `unresolved`
- confidence: `low`
- requires visual verification: `True`
- recommended action: Inspect the same-edition page witness and the relevant glyph/character reading before classifying as a textual variant or source gap.
- Kanripo opening key: `王司州先為庾公記室叅軍後`
- Kanripo opening text (source spelling): `王司州先為庾公記室叅軍後`
- Kanripo location: `content/processed/shishuo/chapters/chapter-16.md`; normalized line `1371`; page `<pb:KR3l0002_SBCK_002-8b>`
- Wikisource match type: `none`
- Wikisource page: `not located`

```text
No aligned Wikisource reading.
```

---

### 16-qixian — `annotation_range_difference`

- classification: `unresolved`
- confidence: `medium`
- requires visual verification: `True`
- recommended action: Use page-level visual witnesses to determine whether this is a missing/extra passage, a glyph/character variant, or a segmentation difference. No textual repair is performed.
- Kanripo main characters: 217
- Wikisource main characters: 217
- length delta (Wikisource − Kanripo): 0
- sequence ratio: 0.990783
- Kanripo location: `content/processed/shishuo/chapters/chapter-16.md`; page markers `['<pb:KR3l0002_SBCK_002-8b>', '<pb:KR3l0002_SBCK_002-9a>']`
- Wikisource page range: `Page:Sibu Congkan0464-劉義慶-世説新語-3-3.djvu/16` through `Page:Sibu Congkan0464-劉義慶-世説新語-3-3.djvu/18` (3 pages)
- Wikisource source URL range: `https://zh.wikisource.org/wiki/Page%3ASibu%20Congkan0464-%E5%8A%89%E7%BE%A9%E6%85%B6-%E4%B8%96%E8%AA%AC%E6%96%B0%E8%AA%9E-3-3.djvu%2F16` through `https://zh.wikisource.org/wiki/Page%3ASibu%20Congkan0464-%E5%8A%89%E7%BE%A9%E6%85%B6-%E4%B8%96%E8%AA%AC%E6%96%B0%E8%AA%9E-3-3.djvu%2F18`

```text
丞相拜司空桓廷尉作兩髻葛帬䇿杖路邉窺之歎曰人言阿龍超阿龍故自超不覺至臺門王丞相過江自說昔在洛水邉數與裴成公阮千里諸賢共談道羊曼曰人久以此許卿何須復爾王曰亦不言我須此但欲爾時不可得耳王右軍得人以蘭亭集序方金谷詩序又以已敵石崇甚有欣色王司州先為庾公記室叅軍後取殷浩為長史始到庾公欲遣王使下都王自啓求住曰下官希見盛德淵源始至猶貪與少日周旋郄嘉賓得人以已比符堅大喜孟昶未逹時家在京口嘗見王恭乘高輿被鶴氅裘于時微雪昶於籬間窺之歎曰此真神仙中人
```

```text
丞相拜司空桓廷尉作兩髻葛帬䇿杖路邉窺之歎曰人言阿龍超阿龍故自超不覺至臺門王丞相過江自說昔在洛水邉數與裴成公阮千里諸賢共談道羊曼曰人久以此許卿何須復爾王曰亦不言我須此但欲爾時不可得耳王右軍得人以蘭亭集序方金谷詩序又以已敵石崇甚有欣色王司州先為⟦{{SKchar|2928}}⟧公記室叅軍後取殷浩為長史始到⟦{{SKchar|2928}}⟧公欲遣王使下都王自啓求住曰下官希見盛德淵源始至猶貪與少日周旋郄嘉賓得人以已比符堅大喜孟昶未逹時家在京口嘗見王恭乘高輿被鶴氅裘于時微雪昶於籬間窺之歎曰此真神仙中人
```

---

### 17-shangshi — 17-shangshi-006 — `unmatched_entry_opening`

- classification: `unresolved`
- confidence: `low`
- requires visual verification: `True`
- recommended action: Inspect the same-edition page witness and the relevant glyph/character reading before classifying as a textual variant or source gap.
- Kanripo opening key: `衛洗馬以永嘉六年喪謝鯤哭`
- Kanripo opening text (source spelling): `衛洗馬以永嘉六年喪謝鯤哭`
- Kanripo location: `content/processed/shishuo/chapters/chapter-17.md`; normalized line `1404`; page `<pb:KR3l0002_SBCK_002-10a>`
- Wikisource match type: `none`
- Wikisource page: `not located`

```text
No aligned Wikisource reading.
```

---

### 17-shangshi — 17-shangshi-008 — `non_exact_entry_opening`

- classification: `unresolved`
- confidence: `low`
- requires visual verification: `True`
- recommended action: Review the exact character/glyph and boundary context; no automatic repair is made.
- Kanripo opening key: `庾亮兒遭蘇峻難遇害諸葛道`
- Kanripo opening text (source spelling): `庾亮兒遭蘇峻難遇害諸葛道`
- Kanripo location: `content/processed/shishuo/chapters/chapter-17.md`; normalized line `1415`; page `<pb:KR3l0002_SBCK_002-10b>`
- Wikisource match type: `suffix`
- Wikisource page: `Page:Sibu Congkan0464-劉義慶-世説新語-3-3.djvu/21`

```text
先平生好琴及喪家人常以琴置靈牀上張季鷹徃哭之不勝其慟遂徑上牀鼓琴作數曲竟撫琴曰顧彦先頗復賞此不因又大慟遂不執孝子手而出𢈔亮兒遭蘇峻難遇害諸葛道明女為𢈔兒婦既寡將改適與亮書及之亮荅曰賢女尚少故其宜也感念亡兒若在初没⟦{{SKchar|2928}}⟧文康亡何⟦{{SKchar|3951}}⟧州臨葬云埋玉⟦{{SKchar|3141}}⟧箸土中使人情何能已已王長史病篤⟦{{SKchar|3462}}⟧卧燈下轉麈尾視之歎曰如此人曽不得四十及亡劉尹臨殯以犀柄麈尾箸柩中因慟絶支道林喪法䖍之後精神霣喪風味轉墜常謂人曰昔匠石廢斤於郢人牙生輟⟦{{SKchar|2959}}⟧於鍾子推已外求良不虚也⟦{{SKchar|2054}}⟧契既逝發言莫
```

---

### 17-shangshi — 17-shangshi-009 — `unmatched_entry_opening`

- classification: `unresolved`
- confidence: `low`
- requires visual verification: `True`
- recommended action: Inspect the same-edition page witness and the relevant glyph/character reading before classifying as a textual variant or source gap.
- Kanripo opening key: `庾文康亡何揚州臨葬云埋玉`
- Kanripo opening text (source spelling): `庾文康亡何揚州臨葬云埋玉`
- Kanripo location: `content/processed/shishuo/chapters/chapter-17.md`; normalized line `1419`; page `<pb:KR3l0002_SBCK_002-11a>`
- Wikisource match type: `none`
- Wikisource page: `not located`

```text
No aligned Wikisource reading.
```

---

### 17-shangshi — 17-shangshi-010 — `unmatched_entry_opening`

- classification: `unresolved`
- confidence: `low`
- requires visual verification: `True`
- recommended action: Inspect the same-edition page witness and the relevant glyph/character reading before classifying as a textual variant or source gap.
- Kanripo opening key: `王長史病篤寝卧燈下轉麈尾`
- Kanripo opening text (source spelling): `王長史病篤寝卧燈下轉麈尾`
- Kanripo location: `content/processed/shishuo/chapters/chapter-17.md`; normalized line `1424`; page `<pb:KR3l0002_SBCK_002-11a>`
- Wikisource match type: `none`
- Wikisource page: `not located`

```text
No aligned Wikisource reading.
```

---

### 17-shangshi — 17-shangshi-018 — `non_exact_entry_opening`

- classification: `unresolved`
- confidence: `low`
- requires visual verification: `True`
- recommended action: Review the exact character/glyph and boundary context; no automatic repair is made.
- Kanripo opening key: `羊孚年三十一卒桓玄與羊欣`
- Kanripo opening text (source spelling): `羊孚年三十一卒桓玄與羊欣`
- Kanripo location: `content/processed/shishuo/chapters/chapter-17.md`; normalized line `1467`; page `<pb:KR3l0002_SBCK_002-13a>`
- Wikisource match type: `prefix`
- Wikisource page: `Page:Sibu Congkan0464-劉義慶-世説新語-3-3.djvu/26`

```text
坐靈牀上取子敬琴彈⟦{{SKchar|2959}}⟧既不調擲地云子敬子敬人琴俱亡因慟絶良久月餘亦卒孝武山陵夕王孝伯入臨告其諸弟曰雖榱桷惟新便自有黍離之哀羊孚年三十一卒桓𤣥與羊欣書曰賢從情所信寄㬥疾而殞祝予之歎如何可言桓𤣥當簒位語卞鞠云昔羊子道恒禁吾此意今腹心喪羊孚爪牙失索元而怱怱作此詆突詎允天心
```

---

### 17-shangshi — 17-shangshi-019 — `non_exact_entry_opening`

- classification: `unresolved`
- confidence: `low`
- requires visual verification: `True`
- recommended action: Review the exact character/glyph and boundary context; no automatic repair is made.
- Kanripo opening key: `桓玄當簒位語卞鞠云昔羊子`
- Kanripo opening text (source spelling): `桓玄當簒位語卞鞠云(已見/卞範)昔羊子`
- Kanripo location: `content/processed/shishuo/chapters/chapter-17.md`; normalized line `1471`; page `<pb:KR3l0002_SBCK_002-13a>`
- Wikisource match type: `suffix`
- Wikisource page: `Page:Sibu Congkan0464-劉義慶-世説新語-3-3.djvu/26`

```text
武山陵夕王孝伯入臨告其諸弟曰雖榱桷惟新便自有黍離之哀羊孚年三十一卒桓𤣥與羊欣書曰賢從情所信寄㬥疾而殞祝予之歎如何可言桓𤣥當簒位語卞鞠云昔羊子道恒禁吾此意今腹心喪羊孚爪牙失索元而怱怱作此詆突詎允天心
```

---

### 17-shangshi — `major_length_difference`

- classification: `structural_difference`
- confidence: `medium`
- requires visual verification: `True`
- recommended action: Use page-level visual witnesses to determine whether this is a missing/extra passage, a glyph/character variant, or a segmentation difference. No textual repair is performed.
- Kanripo main characters: 899
- Wikisource main characters: 895
- length delta (Wikisource − Kanripo): -4
- sequence ratio: 0.983278
- Kanripo location: `content/processed/shishuo/chapters/chapter-17.md`; page markers `['<pb:KR3l0002_SBCK_002-9b>', '<pb:KR3l0002_SBCK_002-10a>', '<pb:KR3l0002_SBCK_002-10b>', '<pb:KR3l0002_SBCK_002-11a>', '<pb:KR3l0002_SBCK_002-11b>', '<pb:KR3l0002_SBCK_002-12a>', '<pb:KR3l0002_SBCK_002-12b>', '<pb:KR3l0002_SBCK_002-13a>', '<pb:KR3l0002_SBCK_002-13b>']`
- Wikisource page range: `Page:Sibu Congkan0464-劉義慶-世説新語-3-3.djvu/18` through `Page:Sibu Congkan0464-劉義慶-世説新語-3-3.djvu/27` (10 pages)
- Wikisource source URL range: `https://zh.wikisource.org/wiki/Page%3ASibu%20Congkan0464-%E5%8A%89%E7%BE%A9%E6%85%B6-%E4%B8%96%E8%AA%AC%E6%96%B0%E8%AA%9E-3-3.djvu%2F18` through `https://zh.wikisource.org/wiki/Page%3ASibu%20Congkan0464-%E5%8A%89%E7%BE%A9%E6%85%B6-%E4%B8%96%E8%AA%AC%E6%96%B0%E8%AA%9E-3-3.djvu%2F27`

```text
來臨屍慟哭賓客莫不垂涕哭畢向靈牀曰卿常好我作驢鳴今我為卿作體似真聲賓客皆笑孫舉頭曰使君輩存令此人死王戎喪兒萬子山簡徃省之王悲不自勝簡曰孩抱中物何至於此王曰聖人忘情最下不及情情之所鍾正在我輩簡服其言更為之慟有人哭和長輿曰峨峨若千丈松崩衛洗馬以永嘉六年喪謝鯤哭之感動路人咸和中丞相王公教曰衛洗馬當改葬此君風流名士海内所瞻可脩薄祭以敦舊好顧彦先平生好琴及喪家人常以琴置靈牀上張季鷹徃哭之不勝其慟遂徑上牀鼓琴作數曲竟撫琴曰顧彦先頗復賞此不因又大慟遂不執孝子手而出庾亮兒遭蘇峻難遇害諸葛道明女為庾兒婦既寡將改適與亮書及之亮荅曰賢女尚少故其宜也感念亡兒若在初没庾文康亡何揚州臨葬云埋玉樹箸土中使人情何能已已王長史病篤寝卧燈下轉麈尾視之歎曰如此人曽不得四十及亡劉尹臨殯以犀柄麈尾箸柩中因慟絶支道
```

```text
來臨屍慟哭賓客莫不垂涕哭畢向靈牀曰卿常好我作驢鳴今我為卿作體似真聲賓客皆笑孫舉頭曰使君輩存令此人死王戎喪兒萬子山簡徃省之王悲不自勝簡曰孩抱中物何至於此王曰聖人忘情最下不及情情之所鍾正在我輩簡服其言更為之慟有人哭和長輿曰峨峨若千丈松崩衛洗馬以喪謝鯤哭之感動路人咸和中丞相王公教曰衛洗馬當改葬此君風流名士海内所瞻可脩薄祭以敦舊好顧彦先平生好琴及喪家人常以琴置靈牀上張季鷹徃哭之不勝其慟遂徑上牀鼓琴作數曲竟撫琴曰顧彦先頗復賞此不因又大慟遂不執孝子手而出𢈔亮兒遭蘇峻難遇害諸葛道明女為𢈔兒婦既寡將改適與亮書及之亮荅曰賢女尚少故其宜也感念亡兒若在初没⟦{{SKchar|2928}}⟧文康亡何⟦{{SKchar|3951}}⟧州臨葬云埋玉⟦{{SKchar|3141}}⟧箸土中使人情何能已已王長史病篤⟦{{SKchar|3462}}⟧卧燈下轉麈尾視之歎曰如此人曽不得四十及亡劉尹臨殯以犀柄麈尾箸柩中因慟絶支道林喪法䖍
```

---

### 18-qiyi — 18-qiyi-011 — `non_exact_entry_opening`

- classification: `unresolved`
- confidence: `low`
- requires visual verification: `True`
- recommended action: Review the exact character/glyph and boundary context; no automatic repair is made.
- Kanripo opening key: `許玄度隱在永興南幽穴中每`
- Kanripo opening text (source spelling): `許玄度隱在永興南幽穴中每`
- Kanripo location: `content/processed/shishuo/chapters/chapter-18.md`; normalized line `1543`; page `<pb:KR3l0002_SBCK_002-17b>`
- Wikisource match type: `suffix`
- Wikisource page: `Page:Sibu Congkan0464-劉義慶-世説新語-3-3.djvu/35`

```text
亦有以自得聲名乃興後不堪遂出戴安道既厲操東山而其兄欲建式遏之功謝太傅曰卿兄弟志業何其太殊戴曰下官不堪其憂家弟不改其樂許𤣥度隱在永興南幽穴中每致四方諸侯之遺或謂許曰嘗聞箕山人似不爾耳許曰筐篚苞苴故當輕於天下之寳耳范宣未嘗入公門韓康伯與同載遂誘俱入郡范便於車後趨下郄超每聞欲高尚隱𨓆者輙為辦百萬資并為造立居宇在剡為戴公起宅甚精整戴始往舊居與所親書曰近至剡如官舍郄為傅約亦辦百萬資⟦{{SKchar|2652}}⟧隐事差互故不果遺許掾好遊山水而體便登陟時人云許非徒有勝情實有濟勝
```

---

### 18-qiyi — 18-qiyi-013 — `non_exact_entry_opening`

- classification: `unresolved`
- confidence: `low`
- requires visual verification: `True`
- recommended action: Review the exact character/glyph and boundary context; no automatic repair is made.
- Kanripo opening key: `郄超每聞欲高尚隱退者輙為`
- Kanripo opening text (source spelling): `郄超每聞欲高尚隱退者輙為`
- Kanripo location: `content/processed/shishuo/chapters/chapter-18.md`; normalized line `1549`; page `<pb:KR3l0002_SBCK_002-17b>`
- Wikisource match type: `prefix`
- Wikisource page: `Page:Sibu Congkan0464-劉義慶-世説新語-3-3.djvu/35`

```text
致四方諸侯之遺或謂許曰嘗聞箕山人似不爾耳許曰筐篚苞苴故當輕於天下之寳耳范宣未嘗入公門韓康伯與同載遂誘俱入郡范便於車後趨下郄超每聞欲高尚隱𨓆者輙為辦百萬資并為造立居宇在剡為戴公起宅甚精整戴始往舊居與所親書曰近至剡如官舍郄為傅約亦辦百萬資⟦{{SKchar|2652}}⟧隐事差互故不果遺許掾好遊山水而體便登陟時人云許非徒有勝情實有濟勝之具郄尚書與謝居士善常稱謝慶緒識見雖不絶人可以累心處都盡
```

---

### 18-qiyi — `missing_kanripo_passage`

- classification: `unresolved`
- confidence: `low`
- requires visual verification: `True`
- recommended action: Use page-level visual witnesses to determine whether this is a missing/extra passage, a glyph/character variant, or a segmentation difference. No textual repair is performed.
- Kanripo main characters: 732
- Wikisource main characters: 911
- length delta (Wikisource − Kanripo): 179
- sequence ratio: 0.881315
- Kanripo location: `content/processed/shishuo/chapters/chapter-18.md`; page markers `['<pb:KR3l0002_SBCK_002-14a>', '<pb:KR3l0002_SBCK_002-15a>', '<pb:KR3l0002_SBCK_002-15b>', '<pb:KR3l0002_SBCK_002-16a>', '<pb:KR3l0002_SBCK_002-16b>', '<pb:KR3l0002_SBCK_002-17a>', '<pb:KR3l0002_SBCK_002-17b>', '<pb:KR3l0002_SBCK_002-17b>', '<pb:KR3l0002_SBCK_002-18a>']`
- Wikisource page range: `Page:Sibu Congkan0464-劉義慶-世説新語-3-3.djvu/27` through `Page:Sibu Congkan0464-劉義慶-世説新語-3-3.djvu/36` (10 pages)
- Wikisource source URL range: `https://zh.wikisource.org/wiki/Page%3ASibu%20Congkan0464-%E5%8A%89%E7%BE%A9%E6%85%B6-%E4%B8%96%E8%AA%AC%E6%96%B0%E8%AA%9E-3-3.djvu%2F27` through `https://zh.wikisource.org/wiki/Page%3ASibu%20Congkan0464-%E5%8A%89%E7%BE%A9%E6%85%B6-%E4%B8%96%E8%AA%AC%E6%96%B0%E8%AA%9E-3-3.djvu%2F36`

```text
匱乏村人亦如之甚厚為鄉閭所安南陽翟道淵與汝南周子南少相友共隐于尋陽庾太尉說周以當世之務周遂仕翟秉志彌固其後周詣翟翟不與語孟萬年及弟少孤居武昌陽新縣萬年遊宦有盛名當世少孤未嘗出京邑人士思欲見之乃遣信報少孤云兄病篤狼狽至都時賢見之者莫不嗟重因相謝太傅曰卿兄弟志業何其太殊戴曰下官不堪其憂家弟不改其樂許玄度隱在永興南幽穴中每致四方諸侯之遺或謂許曰嘗聞箕山人似不爾耳許曰筐篚苞苴故當輕於天下之寳耳范宣未嘗入公門韓康伯與同載遂誘俱入郡范便於車後趨下郄超每聞欲高尚隱退者輙為辦百萬資并為造立居宇在剡為戴公起宅甚精整戴始往舊居與所親書曰近至剡如官舍郄為傅約亦辦百萬資傳隐事差互故不果遺許掾好遊山水而體便登陟時人云許非徒有勝情實有濟勝之具郄尚書與謝居士善常稱謝慶緒識見雖不絶人可以累心處都盡
```

```text
匱乏村人亦如之甚厚為鄉閭所安南陽翟道淵與汝南周子南少相友共隐于尋陽𢈔太尉說周以當世之務周遂仕翟秉志彌固其後周詣翟翟不與語孟萬年及弟少孤居武昌陽新縣萬年遊宦有盛名當世少孤未嘗出京邑人士思欲見之乃遣信報少孤云兄病篤狼狽至都時賢見之者莫不嗟重因相謂曰少孤如此萬年可死康僧淵在豫章去郭數十里立精舍㫄連嶺帶長川芳林列於軒庭清流激於堂宇乃閒居研講希心理味𢈔公諸人多往看之觀其運用吐納風流轉佳加已處之怡然亦有以自得聲名乃興後不堪遂出戴安道既厲操東山而其兄欲建式遏之功謝太傅曰卿兄弟志業何其太殊戴曰下官不堪其憂家弟不改其樂許𤣥度隱在永興南幽穴中每致四方諸侯之遺或謂許曰嘗聞箕山人似不爾耳許曰筐篚苞苴故當輕於天下之寳耳范宣未嘗入公門韓康伯與同載遂誘俱入郡范便於車後趨下郄超每聞欲高尚隱𨓆者輙為辦百萬資并為造立居宇在剡為戴公起宅甚精整戴始往舊居與所親書曰近至剡如官舍郄為傅約亦辦百萬資⟦{{SKchar|2652}}⟧隐事差
```

---

### 19-xianyuan — 19-xianyuan-021 — `non_exact_entry_opening`

- classification: `unresolved`
- confidence: `low`
- requires visual verification: `True`
- recommended action: Review the exact character/glyph and boundary context; no automatic repair is made.
- Kanripo opening key: `庾玉臺希之弟也希誅將戮玉`
- Kanripo opening text (source spelling): `庾玉臺希之弟也希誅將戮玉`
- Kanripo location: `content/processed/shishuo/chapters/chapter-19.md`; normalized line `1747`; page `<pb:KR3l0002_SBCK_002-27b>`
- Wikisource match type: `suffix`
- Wikisource page: `Page:Sibu Congkan0464-劉義慶-世説新語-3-3.djvu/54`

```text
著齋後主始不知既聞與數十婢㧞白刃襲之正值李梳頭髪委藉地膚色玉曜不為動容徐曰國破家亡無心至此今日若能見殺乃是本懷主慚而𨓆𢈔玉臺希之弟也希誅將戮玉臺玉臺子婦宣武弟桓豁女也徒跣求進閽禁不内女厲聲曰是何小人我伯父門不聽我前因突入號泣請曰𢈔玉臺常因人腳短三寸當復能作賊不宣武笑曰壻故自急遂原玉臺一門謝公夫人幃諸婢使在前作𠆸使太傅暫見便下幃太傅索更開夫人云恐傷盛德桓車騎不好箸新衣浴後婦故送新衣與車騎大怒催使持去婦更持還傳語云衣不經新何由而故桓公大笑箸
```

---

### 19-xianyuan — 19-xianyuan-022 — `non_exact_entry_opening`

- classification: `unresolved`
- confidence: `low`
- requires visual verification: `True`
- recommended action: Review the exact character/glyph and boundary context; no automatic repair is made.
- Kanripo opening key: `謝公夫人幃諸婢使在前作伎`
- Kanripo opening text (source spelling): `謝公夫人幃諸婢使在前作伎`
- Kanripo location: `content/processed/shishuo/chapters/chapter-19.md`; normalized line `1755`; page `<pb:KR3l0002_SBCK_002-28a>`
- Wikisource match type: `prefix`
- Wikisource page: `Page:Sibu Congkan0464-劉義慶-世説新語-3-3.djvu/55`

```text
跣求進閽禁不内女厲聲曰是何小人我伯父門不聽我前因突入號泣請曰𢈔玉臺常因人腳短三寸當復能作賊不宣武笑曰壻故自急遂原玉臺一門謝公夫人幃諸婢使在前作𠆸使太傅暫見便下幃太傅索更開夫人云恐傷盛德桓車騎不好箸新衣浴後婦故送新衣與車騎大怒催使持去婦更持還傳語云衣不經新何由而故桓公大笑箸之王右軍郄夫人謂二弟司空中郎曰王家見二謝傾筐倒𢇮見汝輩來平平爾汝可無煩復徃王凝之謝夫人既徃王氏太薄凝之既還謝家意大不說太傅慰釋之曰王郎逸少之子人身亦不惡汝何以恨廼爾荅曰
```

---

### 19-xianyuan — 19-xianyuan-029 — `unmatched_entry_opening`

- classification: `unresolved`
- confidence: `low`
- requires visual verification: `True`
- recommended action: Inspect the same-edition page witness and the relevant glyph/character reading before classifying as a textual variant or source gap.
- Kanripo opening key: `謝遏絶重其姊張玄常稱其妹`
- Kanripo opening text (source spelling): `謝遏絶重其姊張玄常稱其妹`
- Kanripo location: `content/processed/shishuo/chapters/chapter-19.md`; normalized line `1778`; page `<pb:KR3l0002_SBCK_002-29a>`
- Wikisource match type: `none`
- Wikisource page: `not located`

```text
No aligned Wikisource reading.
```

---

### 19-xianyuan — `missing_kanripo_passage`

- classification: `unresolved`
- confidence: `medium`
- requires visual verification: `True`
- recommended action: Use page-level visual witnesses to determine whether this is a missing/extra passage, a glyph/character variant, or a segmentation difference. No textual repair is performed.
- Kanripo main characters: 2398
- Wikisource main characters: 2481
- length delta (Wikisource − Kanripo): 83
- sequence ratio: 0.97643
- Kanripo location: `content/processed/shishuo/chapters/chapter-19.md`; page markers `['<pb:KR3l0002_SBCK_002-18b>', '<pb:KR3l0002_SBCK_002-19a>', '<pb:KR3l0002_SBCK_002-19b>', '<pb:KR3l0002_SBCK_002-20a>', '<pb:KR3l0002_SBCK_002-21a>', '<pb:KR3l0002_SBCK_002-21b>', '<pb:KR3l0002_SBCK_002-22a>', '<pb:KR3l0002_SBCK_002-22b>', '<pb:KR3l0002_SBCK_002-23a>', '<pb:KR3l0002_SBCK_002-23b>', '<pb:KR3l0002_SBCK_002-24a>', '<pb:KR3l0002_SBCK_002-24b>', '<pb:KR3l0002_SBCK_002-25a>', '<pb:KR3l0002_SBCK_002-25b>', '<pb:KR3l0002_SBCK_002-26a>', '<pb:KR3l0002_SBCK_002-26b>', '<pb:KR3l0002_SBCK_002-27a>', '<pb:KR3l0002_SBCK_002-27b>', '<pb:KR3l0002_SBCK_002-28a>', '<pb:KR3l0002_SBCK_002-28b>', '<pb:KR3l0002_SBCK_002-29a>', '<pb:KR3l0002_SBCK_002-29b>']`
- Wikisource page range: `Page:Sibu Congkan0464-劉義慶-世説新語-3-3.djvu/36` through `Page:Sibu Congkan0464-劉義慶-世説新語-3-3.djvu/58` (23 pages)
- Wikisource source URL range: `https://zh.wikisource.org/wiki/Page%3ASibu%20Congkan0464-%E5%8A%89%E7%BE%A9%E6%85%B6-%E4%B8%96%E8%AA%AC%E6%96%B0%E8%AA%9E-3-3.djvu%2F36` through `https://zh.wikisource.org/wiki/Page%3ASibu%20Congkan0464-%E5%8A%89%E7%BE%A9%E6%85%B6-%E4%B8%96%E8%AA%AC%E6%96%B0%E8%AA%9E-3-3.djvu%2F58`

```text
妾聞死生有命富貴在天脩善尚不蒙福爲邪欲以何望若鬼神有知不受邪佞之訴若其無知訴之何益故不爲也魏武帝崩文帝悉取武帝宫人自侍及帝病困卞后出看疾太后入户見直侍並是昔日所愛幸者太后問何時來邪云正伏魄時過因不復前而歎曰狗䑕不食汝餘死故應爾至山陵亦竟不臨婦曰無憂桓必勸入桓果語許云阮家既嫁醜女與卿故當有意卿宜察之許便回入内既見婦即欲出婦料其此出無復入理便捉𥚑停之許因謂曰婦有四德卿有其幾婦曰新婦所乏唯容爾然士有百行君有幾許云皆僃婦曰夫百行以徳為首君好色不好德何謂皆僃允有慚色遂相敬重許允為吏部郎多用其鄉里魏明帝遣虎賁收之其婦出誡允曰明主可以理奪難以情求既至帝覈問之允對曰舉爾所知臣之郷人臣所知也陛下檢校為稱職與不若不稱職臣受其罪既檢校皆官得其人於是乃釋允衣服敗壞詔賜新衣初允𬒳收舉家號哭阮新婦自
```

```text
妾聞死生有命富貴在天脩善尚不⟦{{SKchar|3681}}⟧福爲邪欲以何望若⟦{{SKchar|3932}}⟧神有知不受邪佞之訴若其無知訴之何益故不爲也魏武帝崩文帝悉取武帝宫人自侍及帝病困卞后出看疾太后入户見直侍並是昔日所愛幸者太后問何時來邪云正伏魄時過因不復前而歎曰狗䑕不食汝餘死故應爾至山陵亦竟不臨趙母嫁女女臨去敕之曰慎勿為好女曰不為好可為惡邪母曰好尚不可為其況惡乎許允婦是阮衛尉女德如妹竒醜交禮竟允無復入理家人深以為憂㑹允有客至婦令婢視之還荅曰是桓郎桓郎者桓範也婦曰無憂桓必勸入桓果語許云阮家既嫁醜女與卿故當有意卿宜察之許便回入内既見婦即欲出婦料其此出無復入理便捉𥚑停之許因謂曰婦有四德卿有其幾婦曰新婦所乏唯容爾然士有百行君有幾許云皆僃婦曰夫百行以徳為首君好色不好德何謂皆僃允有慚色遂相敬重許允為吏部郎多用其鄉里魏明帝遣虎賁收之其婦出誡允曰明主可以理奪難以情求既至帝覈問之允對曰舉爾
```

---

### 20-shujie — `annotation_range_difference`

- classification: `unresolved`
- confidence: `medium`
- requires visual verification: `True`
- recommended action: Use page-level visual witnesses to determine whether this is a missing/extra passage, a glyph/character variant, or a segmentation difference. No textual repair is performed.
- Kanripo main characters: 709
- Wikisource main characters: 709
- length delta (Wikisource − Kanripo): 0
- sequence ratio: 0.997179
- Kanripo location: `content/processed/shishuo/chapters/chapter-20.md`; page markers `['<pb:KR3l0002_SBCK_002-30a>', '<pb:KR3l0002_SBCK_002-30b>', '<pb:KR3l0002_SBCK_002-31a>', '<pb:KR3l0002_SBCK_002-31b>', '<pb:KR3l0002_SBCK_002-32a>', '<pb:KR3l0002_SBCK_002-32b>']`
- Wikisource page range: `Page:Sibu Congkan0464-劉義慶-世説新語-3-3.djvu/58` through `Page:Sibu Congkan0464-劉義慶-世説新語-3-3.djvu/64` (7 pages)
- Wikisource source URL range: `https://zh.wikisource.org/wiki/Page%3ASibu%20Congkan0464-%E5%8A%89%E7%BE%A9%E6%85%B6-%E4%B8%96%E8%AA%AC%E6%96%B0%E8%AA%9E-3-3.djvu%2F58` through `https://zh.wikisource.org/wiki/Page%3ASibu%20Congkan0464-%E5%8A%89%E7%BE%A9%E6%85%B6-%E4%B8%96%E8%AA%AC%E6%96%B0%E8%AA%9E-3-3.djvu%2F64`

```text
出天子能致天子問耳郭景純過江居于暨陽墓去水不盈百步時人以爲近水景純曰將當爲陸今沙漲去墓數十里皆爲桑田其詩曰北阜烈烈巨海混混壘壘三墳唯母與昆王丞相令郭璞試作一卦卦成郭意色甚惡云公有震厄王問有可消伏理不郭曰命駕西出數里得一栢樹截斷如公長置牀上常寝處災可消矣王從其語數日中果震栢粉碎子弟皆稱慶大將軍云君乃復委罪於樹木桓公有主簿善别酒有酒輙令先嘗好者謂青州從事惡者謂平原督郵青州有齊郡平原有鬲縣從事言到臍督郵言在鬲上住郗愔信道甚精勤常患腹内惡諸醫不可療聞于法開有名徃迎之旣來便脉云君侯所患正是精進太過所致耳合一劑湯與之一服卽大下去數叚許𥿄如拳大剖看乃先所服符也殷中軍妙解經脉中年都廢有常所給使忽叩頭流血浩問其故云有死事終不可說詰問良久乃云小人母年垂百嵗抱疾來久若䝉官一脉便有活理訖就屠戮無
```

```text
出天子能致天子問耳郭景純過江居于暨陽墓去水不盈百步時人以爲近水景純曰將當爲陸今沙漲去墓數十里皆爲桑田其詩曰北阜烈烈巨海混混壘壘三墳唯母與昆王丞相令郭璞試作一卦卦成郭意色甚惡云公有震厄王問有可消伏理不郭曰命駕西出數里得一栢樹截斷如公長置牀上常⟦{{SKchar|3462}}⟧處災可消矣王從其語數日中果震栢粉碎子弟皆稱慶大將軍云君乃復委罪於樹木桓公有主簿善别酒有酒輙令先嘗好者謂青州從事惡者謂平原督郵青州有齊郡平原有鬲縣從事言到臍督郵言在鬲上住郗愔信道甚精勤常患腹内惡諸醫不可療聞于法開有名徃迎之旣來便脉云君侯所患正是精進太過所致耳合一劑湯與之一服卽大下去數叚許⟦{{SKchar|3505}}⟧如拳大剖看乃先所服符也殷中軍妙解經脉中年都廢有常所給使忽叩頭流血浩問其故云有死事終不可說詰問良久乃云小人母年垂百嵗抱疾來久若䝉官一脉便有活理訖就屠戮無
```

---

### 21-qiaoyi — 21-qiaoyi-014 — `non_exact_entry_opening`

- classification: `unresolved`
- confidence: `low`
- requires visual verification: `True`
- recommended action: Review the exact character/glyph and boundary context; no automatic repair is made.
- Kanripo opening key: `顧長康道畫手揮五弦易目送`
- Kanripo opening text (source spelling): `顧長康道畫手揮五弦易目送`
- Kanripo location: `content/processed/shishuo/chapters/chapter-21.md`; normalized line `1912`; page `<pb:KR3l0002_SBCK_002-35a>`
- Wikisource match type: `prefix`
- Wikisource page: `Page:Sibu Congkan0464-劉義慶-世説新語-3-3.djvu/69`

```text
問其所以顧曰謝云一丘一壑自謂過之此子宐置丘壑中顧長康畫人或數年不㸃目精人問其故顧曰四體妍蚩本無關於妙處傳神寫照正在阿堵中顧長康道畫手揮五⟦{{SKchar|2959}}⟧易目送歸鴻難
```

---

### 22-chongli — 22-chongli-002 — `non_exact_entry_opening`

- classification: `unresolved`
- confidence: `low`
- requires visual verification: `True`
- recommended action: Review the exact character/glyph and boundary context; no automatic repair is made.
- Kanripo opening key: `桓宣武嘗請叅佐入宿袁宏伏`
- Kanripo opening text (source spelling): `桓宣武嘗請叅佐入宿袁宏伏`
- Kanripo location: `content/processed/shishuo/chapters/chapter-22.md`; normalized line `1918`; page `<pb:KR3l0002_SBCK_002-35b>`
- Wikisource match type: `prefix`
- Wikisource page: `Page:Sibu Congkan0464-劉義慶-世説新語-3-3.djvu/70`

```text
元帝正㑹引王丞相登御牀王公固辭中宗引之彌苦王公曰使太陽與萬物同暉臣下何以瞻仰桓宣武嘗請叅佐入宿𡊮宏伏滔相次而至蒞名府中復有𡊮叅軍彦伯疑焉令傳教更質傳教曰叅軍是𡊮伏之𡊮復何所疑王珣郄超並有竒才為大司馬所眷㧞珣為主簿超為記室叅軍超為人多須珣狀短小于時荆州為之語曰𩓿叅軍短主簿能令公喜能令公怒許𤣥度停都一月劉尹無日不徃乃歎曰卿復少時不去我成輕薄京尹孝武在西堂㑹伏滔預坐還下車呼其兒語之曰百人高㑹臨坐未得
```

---

### 22-chongli — 22-chongli-004 — `non_exact_entry_opening`

- classification: `unresolved`
- confidence: `low`
- requires visual verification: `True`
- recommended action: Review the exact character/glyph and boundary context; no automatic repair is made.
- Kanripo opening key: `許玄度停都一月劉尹無日不`
- Kanripo opening text (source spelling): `許玄度停都一月劉尹無日不`
- Kanripo location: `content/processed/shishuo/chapters/chapter-22.md`; normalized line `1925`; page `<pb:KR3l0002_SBCK_002-35b>`
- Wikisource match type: `suffix`
- Wikisource page: `Page:Sibu Congkan0464-劉義慶-世説新語-3-3.djvu/70`

```text
所疑王珣郄超並有竒才為大司馬所眷㧞珣為主簿超為記室叅軍超為人多須珣狀短小于時荆州為之語曰𩓿叅軍短主簿能令公喜能令公怒許𤣥度停都一月劉尹無日不徃乃歎曰卿復少時不去我成輕薄京尹孝武在西堂㑹伏滔預坐還下車呼其兒語之曰百人高㑹臨坐未得他語先問伏滔何在在此不此故未易得爲人作父如此何如卞範之爲丹陽尹羊孚南州暫還徃卞許云下官疾動不堪坐卞便開帳拂褥羊徑上大牀入⟦{{SKchar|3425}}⟧須枕卞回坐傾睞移晨逹莫羊去卞語曰我以第一理期卿卿莫⟦{{SKchar|3688}}⟧我
```

---

### 23-rendan — 23-rendan-003 — `non_exact_entry_opening`

- classification: `unresolved`
- confidence: `low`
- requires visual verification: `True`
- recommended action: Review the exact character/glyph and boundary context; no automatic repair is made.
- Kanripo opening key: `劉伶病酒渴甚從婦求酒婦捐`
- Kanripo opening text (source spelling): `劉伶病酒渴甚從婦求酒婦捐`
- Kanripo location: `content/processed/shishuo/chapters/chapter-23.md`; normalized line `1954`; page `<pb:KR3l0002_SBCK_002-37a>`
- Wikisource match type: `prefix`
- Wikisource page: `Page:Sibu Congkan0464-劉義慶-世説新語-3-3.djvu/73`

```text
阮籍以重喪顯於公坐飲酒食肉宐流之海外以正風教文王曰嗣宗毁頓如此君不能共憂之何謂且有疾而飲酒食肉固喪禮也籍飲噉不輟神色自若劉伶病酒渴甚從婦求酒婦⟦{{SKchar|3037}}⟧酒毁噐涕泣諫曰君飲太過非攝生之道必宐斷之伶曰甚善我不能自禁唯當祝⟦{{SKchar|3932}}⟧神自誓斷之耳便可具酒肉婦曰敬聞命供酒肉於神前請伶祝誓伶跪而祝曰天生劉伶以酒為名一飲一斛五斗解酲婦人之言慎不可聽便引酒進肉隗然已醉矣劉公榮與人飲酒雜⟦{{SKchar|3452}}⟧非⟦{{SKchar|3892}}⟧人或譏之荅曰勝公榮者不可不與飲不如公榮者亦不可不與飲是公榮輩者又不可不與飲故終
```

---

### 23-rendan — 23-rendan-004 — `non_exact_entry_opening`

- classification: `unresolved`
- confidence: `low`
- requires visual verification: `True`
- recommended action: Review the exact character/glyph and boundary context; no automatic repair is made.
- Kanripo opening key: `劉公榮與人飲酒雜穢非類人`
- Kanripo opening text (source spelling): `劉公榮與人飲酒雜穢非類人`
- Kanripo location: `content/processed/shishuo/chapters/chapter-23.md`; normalized line `1961`; page `<pb:KR3l0002_SBCK_002-37b>`
- Wikisource match type: `prefix`
- Wikisource page: `Page:Sibu Congkan0464-劉義慶-世説新語-3-3.djvu/74`

```text
耳便可具酒肉婦曰敬聞命供酒肉於神前請伶祝誓伶跪而祝曰天生劉伶以酒為名一飲一斛五斗解酲婦人之言慎不可聽便引酒進肉隗然已醉矣劉公榮與人飲酒雜⟦{{SKchar|3452}}⟧非⟦{{SKchar|3892}}⟧人或譏之荅曰勝公榮者不可不與飲不如公榮者亦不可不與飲是公榮輩者又不可不與飲故終日共飲而醉步兵校尉缺⟦{{SKchar|2936}}⟧中有貯酒數百斛阮籍乃求爲歩兵校尉劉伶恒縱酒放逹或脫衣祼形在屋中人見譏之伶曰我以天地為棟宇屋室為㡓衣諸君何為入吾㡓中阮籍㛮嘗還家籍見與别或譏之籍曰禮豈為我輩設也阮公鄰家婦有美色當壚酤酒阮與王安豐常從婦
```

---

### 23-rendan — 23-rendan-005 — `unmatched_entry_opening`

- classification: `unresolved`
- confidence: `low`
- requires visual verification: `True`
- recommended action: Inspect the same-edition page witness and the relevant glyph/character reading before classifying as a textual variant or source gap.
- Kanripo opening key: `步兵校尉缺厨中有貯酒數百`
- Kanripo opening text (source spelling): `步兵校尉缺厨中有貯酒數百`
- Kanripo location: `content/processed/shishuo/chapters/chapter-23.md`; normalized line `1965`; page `<pb:KR3l0002_SBCK_002-37b>`
- Wikisource match type: `none`
- Wikisource page: `not located`

```text
No aligned Wikisource reading.
```

---

### 23-rendan — 23-rendan-025 — `non_exact_entry_opening`

- classification: `unresolved`
- confidence: `low`
- requires visual verification: `True`
- recommended action: Review the exact character/glyph and boundary context; no automatic repair is made.
- Kanripo opening key: `有人譏周僕射與親友言戲穢`
- Kanripo opening text (source spelling): `有人譏周僕射與親友言戲穢`
- Kanripo location: `content/processed/shishuo/chapters/chapter-23.md`; normalized line `2057`; page `<pb:KR3l0002_SBCK_002-41b>`
- Wikisource match type: `prefix`
- Wikisource page: `Page:Sibu Congkan0464-劉義慶-世説新語-3-3.djvu/82`

```text
卿孔羣好飲酒王丞相語云卿何為恒飲酒不見酒家覆瓿布日月糜爛羣曰不爾不見糟肉乃更堪久羣嘗書與親舊今年田得七百斛秫米不了麴糵事有人譏周僕射與親友言戲⟦{{SKchar|3452}}⟧雜無檢節周曰吾若萬里長江何能不千里一曲温太真位未髙時屢與⟦{{SKchar|3951}}⟧州淮中估客樗蒱與輙不競嘗一過大輸物戲屈無因得反與庾亮善於舫中大喚亮曰卿可贖我庾即送直然後得還經此數四温公喜慢語卞令禮法自居至庾公許大相剖擊温發口鄙⟦{{SKchar|3452}}⟧庾公徐曰太真終日無鄙言周伯仁風徳雅重深逹危亂過江積年恒大飲酒嘗經三日不醒時人謂之三日僕射衛
```

---

### 23-rendan — 23-rendan-026 — `non_exact_entry_opening`

- classification: `unresolved`
- confidence: `low`
- requires visual verification: `True`
- recommended action: Review the exact character/glyph and boundary context; no automatic repair is made.
- Kanripo opening key: `温太真位未髙時屢與揚州淮`
- Kanripo opening text (source spelling): `温太真位未髙時屢與揚州淮`
- Kanripo location: `content/processed/shishuo/chapters/chapter-23.md`; normalized line `2061`; page `<pb:KR3l0002_SBCK_002-42a>`
- Wikisource match type: `prefix`
- Wikisource page: `Page:Sibu Congkan0464-劉義慶-世説新語-3-3.djvu/83`

```text
爾不見糟肉乃更堪久羣嘗書與親舊今年田得七百斛秫米不了麴糵事有人譏周僕射與親友言戲⟦{{SKchar|3452}}⟧雜無檢節周曰吾若萬里長江何能不千里一曲温太真位未髙時屢與⟦{{SKchar|3951}}⟧州淮中估客樗蒱與輙不競嘗一過大輸物戲屈無因得反與庾亮善於舫中大喚亮曰卿可贖我庾即送直然後得還經此數四温公喜慢語卞令禮法自居至庾公許大相剖擊温發口鄙⟦{{SKchar|3452}}⟧庾公徐曰太真終日無鄙言周伯仁風徳雅重深逹危亂過江積年恒大飲酒嘗經三日不醒時人謂之三日僕射衛君長為温公長史温公甚善之每率爾提酒脯就衛箕踞相對彌日衛徃温許亦
```

---

### 23-rendan — 23-rendan-030 — `unmatched_entry_opening`

- classification: `unresolved`
- confidence: `low`
- requires visual verification: `True`
- recommended action: Inspect the same-edition page witness and the relevant glyph/character reading before classifying as a textual variant or source gap.
- Kanripo opening key: `蘇峻亂諸庾逃散庾冰時為吳`
- Kanripo opening text (source spelling): `蘇峻亂諸庾逃散庾冰時為吳`
- Kanripo location: `content/processed/shishuo/chapters/chapter-23.md`; normalized line `2075`; page `<pb:KR3l0002_SBCK_002-42b>`
- Wikisource match type: `none`
- Wikisource page: `not located`

```text
No aligned Wikisource reading.
```

---

### 23-rendan — 23-rendan-032 — `non_exact_entry_opening`

- classification: `unresolved`
- confidence: `low`
- requires visual verification: `True`
- recommended action: Review the exact character/glyph and boundary context; no automatic repair is made.
- Kanripo opening key: `王長史謝仁祖同為王公掾長`
- Kanripo opening text (source spelling): `王長史謝仁祖同為王公掾(辟名士時賢恊贊中興/王濛别傳曰丞相王導)
(俊乂辟濛為掾/旌命所加必延)長`
- Kanripo location: `content/processed/shishuo/chapters/chapter-23.md`; normalized line `2089`; page `<pb:KR3l0002_SBCK_002-43a>`
- Wikisource match type: `prefix`
- Wikisource page: `Page:Sibu Congkan0464-劉義慶-世説新語-3-3.djvu/85`

```text
其身時謂此卒非唯有智且亦逹生殷洪喬作豫章郡臨去都下人因附百許函書既至石頭悉擲水中因祝曰沉者自沉浮者自浮殷洪喬不能作致書郵王長史謝仁祖同為王公⟦{{SKchar|3044}}⟧長史云謝⟦{{SKchar|3044}}⟧能作異舞謝便起舞神意甚暇王公熟視謂客曰使人思安豐王劉共在杭南酣宴於桓子野家謝鎮西徃尚書墓還葬後三日反哭諸人欲要之初遣一信猶未許然已停車重要便回駕諸人門外迎之把臂便下裁得脫幘箸帽酣宴半坐乃覺未脫衰桓宣武少家貧戲大輸債主敦求甚切思自振之方莫知所出陳郡𡊮躭俊邁多能宣武欲求救於躭躭時居艱恐致疑試
```

---

### 23-rendan — 23-rendan-037 — `non_exact_entry_opening`

- classification: `unresolved`
- confidence: `low`
- requires visual verification: `True`
- recommended action: Review the exact character/glyph and boundary context; no automatic repair is made.
- Kanripo opening key: `袁彦道有二妹一適殷淵源一`
- Kanripo opening text (source spelling): `袁彦道有二妹一適殷淵源一`
- Kanripo location: `content/processed/shishuo/chapters/chapter-23.md`; normalized line `2117`; page `<pb:KR3l0002_SBCK_002-44b>`
- Wikisource match type: `suffix`
- Wikisource page: `Page:Sibu Congkan0464-劉義慶-世説新語-3-3.djvu/88`

```text
百萬數投馬絶呌傍若無人探布帽擲對人曰汝竟識𡊮彦道不王光祿云酒正使人人自逺劉尹云孫承公狂士每至一處賞翫累日或回至半路却返𡊮彦道有二妹一適殷淵源一適謝仁祖語桓宣武云恨不更有一人配卿桓車騎在荆州張𤣥為侍中使至江陵路經陽歧村俄見一人持半小籠生魚徑來造船云有魚欲寄作膾張乃維舟而納之問其姓字稱是劉遺民張素聞其名大相忻待劉既知張銜命問謝安王文度並佳不張甚欲話言劉了無停意既進膾便去云向得此魚觀君船上當有膾具是故來耳於是便去張乃追至劉家為設酒殊不清㫖張高
```

---

### 23-rendan — 23-rendan-038 — `unmatched_entry_opening`

- classification: `unresolved`
- confidence: `low`
- requires visual verification: `True`
- recommended action: Inspect the same-edition page witness and the relevant glyph/character reading before classifying as a textual variant or source gap.
- Kanripo opening key: `桓車騎在荆州張玄為侍中使`
- Kanripo opening text (source spelling): `桓車騎在荆州張玄為侍中使`
- Kanripo location: `content/processed/shishuo/chapters/chapter-23.md`; normalized line `2119`; page `<pb:KR3l0002_SBCK_002-44b>`
- Wikisource match type: `none`
- Wikisource page: `not located`

```text
No aligned Wikisource reading.
```

---

### 23-rendan — 23-rendan-043 — `non_exact_entry_opening`

- classification: `unresolved`
- confidence: `low`
- requires visual verification: `True`
- recommended action: Review the exact character/glyph and boundary context; no automatic repair is made.
- Kanripo opening key: `張湛好於齋前種松柏時袁山`
- Kanripo opening text (source spelling): `張湛好於齋前種松柏(平人張氏譜曰湛祖嶷正員/晉東宫官名曰湛字處度髙)
(湛仕至中書郎/郎父曠鎮軍司馬)時袁山`
- Kanripo location: `content/processed/shishuo/chapters/chapter-23.md`; normalized line `2161`; page `<pb:KR3l0002_SBCK_002-46b>`
- Wikisource match type: `prefix`
- Wikisource page: `Page:Sibu Congkan0464-劉義慶-世説新語-3-3.djvu/92`

```text
在益州語兒云我有五百人食器家中大驚其由來清而忽有此物定是二百五十沓烏樏桓子野每聞清歌輙喚奈何謝公聞之曰子野可謂一徃有深情張湛好於齋前種松柏時⟦{{SKchar|2783}}⟧山松出遊每好令左右作挽歌時人謂張屋下陳屍⟦{{SKchar|2783}}⟧道上行殯羅友作荆州從事桓宣武為王車騎集别友進坐良乆辭出宣武曰卿向欲咨事何以便去荅曰友聞白羊肉美一生未曾得喫故冒求前耳無事可咨今已飽不復須駐了無慚色張驎酒後挽歌甚悽苦桓車⟦{{SKchar|3853}}⟧曰卿非田橫門人何乃頓爾至致王子猷嘗暫寄人空宅住便令種竹或問暫住何煩爾王嘯詠良久直指竹曰
```

---

### 23-rendan — 23-rendan-045 — `non_exact_entry_opening`

- classification: `unresolved`
- confidence: `low`
- requires visual verification: `True`
- recommended action: Review the exact character/glyph and boundary context; no automatic repair is made.
- Kanripo opening key: `張驎酒後挽歌甚悽苦桓車騎`
- Kanripo opening text (source spelling): `張驎酒後挽歌甚悽苦桓車騎`
- Kanripo location: `content/processed/shishuo/chapters/chapter-23.md`; normalized line `2172`; page `<pb:KR3l0002_SBCK_002-47a>`
- Wikisource match type: `prefix`
- Wikisource page: `Page:Sibu Congkan0464-劉義慶-世説新語-3-3.djvu/93`

```text
武為王車騎集别友進坐良乆辭出宣武曰卿向欲咨事何以便去荅曰友聞白羊肉美一生未曾得喫故冒求前耳無事可咨今已飽不復須駐了無慚色張驎酒後挽歌甚悽苦桓車⟦{{SKchar|3853}}⟧曰卿非田橫門人何乃頓爾至致王子猷嘗暫寄人空宅住便令種竹或問暫住何煩爾王嘯詠良久直指竹曰何可一日無此君王子猷居山隂夜大雪眠覺開室命酌酒四望皎然因起仿偟詠左思招隱詩忽憶戴安道時戴在剡即便夜乗小船就之經宿方至造門不前而返人問其故王曰吾本乗興而行興盡而返何必見戴王衛軍云酒正自引人箸勝地王子猷出都尚在渚下
```

---

### 23-rendan — `major_length_difference`

- classification: `structural_difference`
- confidence: `medium`
- requires visual verification: `True`
- recommended action: Use page-level visual witnesses to determine whether this is a missing/extra passage, a glyph/character variant, or a segmentation difference. No textual repair is performed.
- Kanripo main characters: 3097
- Wikisource main characters: 3093
- length delta (Wikisource − Kanripo): -4
- sequence ratio: 0.987076
- Kanripo location: `content/processed/shishuo/chapters/chapter-23.md`; page markers `['<pb:KR3l0002_SBCK_002-37a>', '<pb:KR3l0002_SBCK_002-37b>', '<pb:KR3l0002_SBCK_002-38a>', '<pb:KR3l0002_SBCK_002-38b>', '<pb:KR3l0002_SBCK_002-39a>', '<pb:KR3l0002_SBCK_002-39b>', '<pb:KR3l0002_SBCK_002-40a>', '<pb:KR3l0002_SBCK_002-40b>', '<pb:KR3l0002_SBCK_002-41a>', '<pb:KR3l0002_SBCK_002-41b>', '<pb:KR3l0002_SBCK_002-42a>', '<pb:KR3l0002_SBCK_002-42b>', '<pb:KR3l0002_SBCK_002-43a>', '<pb:KR3l0002_SBCK_002-43b>', '<pb:KR3l0002_SBCK_002-44a>', '<pb:KR3l0002_SBCK_002-44b>', '<pb:KR3l0002_SBCK_002-45a>', '<pb:KR3l0002_SBCK_002-45b>', '<pb:KR3l0002_SBCK_002-46a>', '<pb:KR3l0002_SBCK_002-46b>', '<pb:KR3l0002_SBCK_002-47a>', '<pb:KR3l0002_SBCK_002-47b>', '<pb:KR3l0002_SBCK_002-48a>', '<pb:KR3l0002_SBCK_002-48b>', '<pb:KR3l0002_SBCK_002-49a>']`
- Wikisource page range: `Page:Sibu Congkan0464-劉義慶-世説新語-3-3.djvu/72` through `Page:Sibu Congkan0464-劉義慶-世説新語-3-3.djvu/97` (26 pages)
- Wikisource source URL range: `https://zh.wikisource.org/wiki/Page%3ASibu%20Congkan0464-%E5%8A%89%E7%BE%A9%E6%85%B6-%E4%B8%96%E8%AA%AC%E6%96%B0%E8%AA%9E-3-3.djvu%2F72` through `https://zh.wikisource.org/wiki/Page%3ASibu%20Congkan0464-%E5%8A%89%E7%BE%A9%E6%85%B6-%E4%B8%96%E8%AA%AC%E6%96%B0%E8%AA%9E-3-3.djvu%2F97`

```text
民張素聞其名大相忻待劉既知張銜命問謝安王文度並佳不張甚欲話言劉了無停意既進膾便去云向得此魚觀君船上當有膾具是故來耳於是便去張乃追至劉家為設酒殊不清㫖張高其人不得已而飲之方共封飲劉便先起云今正伐荻不宐久廢張亦無以留之王子猷詣郄雍州雍州在内見有[翕*毛]㲪云阿乞那得此物令左右送還家郗出覓之王曰向有大力者負之而趨郄無忤色謝安始出西戯失車半便杖䇿步歸道逢劉尹語曰安石將無傷謝乃同載而歸襄陽羅友有大韻少時多謂之癡嘗伺人祠欲乞食徃太蚤門未開主人迎神出見問以非時何得在此荅曰聞卿祠欲乞一頓食耳遂隱門側至曉得食便退了無怍容為人有記功從桓宣武平蜀按行蜀城闕觀宇内外道陌廣狹植種果竹多少皆黙記之後宣武漂洲與簡文集友亦預焉共道蜀中事亦有所遺忘友皆名列曽無錯漏宣武驗以蜀城闕簿皆如其言坐者歎服謝公云羅友
```

```text
民張素聞其名大相忻待劉既知張銜命問謝安王文度並佳不張甚欲話言劉了無停意既進膾便去云向得此魚觀君船上當有膾具是故來耳於是便去張乃追至劉家為設酒殊不清㫖張高其人不得已而飲之方共封飲劉便先起云今正伐荻不宐久廢張亦無以留之王子猷詣郄雍州雍州在内見有⟦{{SKchar|1394}}⟧㲪云阿乞那得此物令左右送還家郗出覓之王曰向有大力者⟦{{SKchar|3688}}⟧之而趨郄無忤色謝安始出西戯失車半便杖䇿步歸道逢劉尹語曰安石將無傷謝乃同載而歸襄陽羅友有大韻少時多謂之癡嘗伺人祠欲乞食徃太蚤門未開主人迎神出見問以非時何得在此荅曰聞卿祠欲乞一頓食耳遂隱門側至曉得食便⟦{{SKchar|2385}}⟧了無怍容為人有記功從桓宣武平蜀按行蜀城闕觀宇内外道陌廣狹植種果竹多少皆黙記之後宣武漂洲與簡文集友亦預焉共道蜀中事亦有所遺忘友皆名列曽無錯漏宣武驗以蜀城闕簿皆如其言坐者歎服謝公云羅友詎減魏陽
```

---

### 24-jianao — `annotation_range_difference`

- classification: `unresolved`
- confidence: `medium`
- requires visual verification: `True`
- recommended action: Use page-level visual witnesses to determine whether this is a missing/extra passage, a glyph/character variant, or a segmentation difference. No textual repair is performed.
- Kanripo main characters: 1209
- Wikisource main characters: 1221
- length delta (Wikisource − Kanripo): 12
- sequence ratio: 0.993416
- Kanripo location: `content/processed/shishuo/chapters/chapter-24.md`; page markers `['<pb:KR3l0002_SBCK_002-49b>', '<pb:KR3l0002_SBCK_002-50a>', '<pb:KR3l0002_SBCK_002-50b>', '<pb:KR3l0002_SBCK_002-51a>', '<pb:KR3l0002_SBCK_002-51b>', '<pb:KR3l0002_SBCK_002-52a>', '<pb:KR3l0002_SBCK_002-52b>', '<pb:KR3l0002_SBCK_002-53a>', '<pb:KR3l0002_SBCK_002-53b>', '<pb:KR3l0002_SBCK_002-54a>']`
- Wikisource page range: `Page:Sibu Congkan0464-劉義慶-世説新語-3-3.djvu/97` through `Page:Sibu Congkan0464-劉義慶-世説新語-3-3.djvu/108` (12 pages)
- Wikisource source URL range: `https://zh.wikisource.org/wiki/Page%3ASibu%20Congkan0464-%E5%8A%89%E7%BE%A9%E6%85%B6-%E4%B8%96%E8%AA%AC%E6%96%B0%E8%AA%9E-3-3.djvu%2F97` through `https://zh.wikisource.org/wiki/Page%3ASibu%20Congkan0464-%E5%8A%89%E7%BE%A9%E6%85%B6-%E4%B8%96%E8%AA%AC%E6%96%B0%E8%AA%9E-3-3.djvu%2F108`

```text
以此賞主人乃留坐盡歡而去王子敬自㑹稽經吳聞顧辟疆有名園先不識主人徑徃其家值顧方集賔友酣燕而王遊歴既畢指麾好惡傍若無人顧勃然不堪曰傲主人非禮也以貴驕人非道也失此二者不足齒人傖耳便驅其左右出門王獨在輿上回轉顧望左右移時不至然後令送箸門外怡然不屑
```

```text
以此賞主人乃留坐盡歡而去王子敬自㑹稽經吳聞顧辟疆有名園先不識主人徑徃其家值顧方集賔友酣燕而王遊歴既畢指麾好惡傍若無人顧勃然不堪曰傲主人非禮也以貴驕人非道也失此二者不足齒人傖耳便驅其左右出門王獨在輿上回轉顧望左右移時不至然後令送箸門外怡然不屑宋臨川王義慶撰梁劉孝標注
```

---

### 25-paidiao — 25-paidiao-015 — `non_exact_entry_opening`

- classification: `unresolved`
- confidence: `low`
- requires visual verification: `True`
- recommended action: Review the exact character/glyph and boundary context; no automatic repair is made.
- Kanripo opening key: `謝幼輿謂周侯曰卿類社樹逺`
- Kanripo opening text (source spelling): `謝幼輿謂周侯曰卿類社樹逺`
- Kanripo location: `content/processed/shishuo/chapters/chapter-25.md`; normalized line `2428`; page `<pb:KR3l0002_SBCK_002-59b>`
- Wikisource match type: `prefix`
- Wikisource page: `Page:Sibu Congkan0464-劉義慶-世説新語-3-3.djvu/117`

```text
問見王公云何劉曰未見他異唯聞作吳語耳王公與朝士共飲酒舉瑠璃盌謂伯仁曰此盌腹殊空謂之寳器何邪荅曰此盌英英誠為清徹所以爲寳耳謝幼輿謂周侯曰卿𩔖社樹逺望之峨峨拂青天就而視之其根則羣狐所託下聚溷而已荅曰枝條拂青天不以爲高羣狐亂其下不以爲濁聚溷之穢卿之所保何足自稱王長豫㓜便和令丞相愛恣甚篤毎共圍棊丞相欲舉行長豫按指不聽丞相笑曰詎得爾相與似有𤓰葛明帝問周伯仁眞長何如人荅曰故是千斤犗特王公笑其言伯仁曰不如捲角牸有盤辟之好王丞相枕周伯仁䣛指其腹曰卿此中
```

---

### 25-paidiao — 25-paidiao-023 — `non_exact_entry_opening`

- classification: `unresolved`
- confidence: `low`
- requires visual verification: `True`
- recommended action: Review the exact character/glyph and boundary context; no automatic repair is made.
- Kanripo opening key: `庾征西大舉征胡既成行止鎮`
- Kanripo opening text (source spelling): `庾征西大舉征胡既成行止鎮`
- Kanripo location: `content/processed/shishuo/chapters/chapter-25.md`; normalized line `2458`; page `<pb:KR3l0002_SBCK_002-60b>`
- Wikisource match type: `suffix`
- Wikisource page: `Page:Sibu Congkan0464-劉義慶-世説新語-3-3.djvu/119`

```text
不清何次道徃瓦官寺禮拜甚勤阮思曠語之曰卿志大宇宙勇邁終古何曰卿今日何故忽見推阮曰我圖數千戸郡尚不能得卿廼圖作佛不亦大乎𢈔征西大舉征胡既成行止鎮襄陽殷豫章與書送一折角如意以調之⟦{{SKchar|2928}}⟧荅書曰得所致雖是敗物猶欲理而用之桓大司馬乘雪欲獵先過王劉諸人許真長見其裝束單急問老賊欲持此何作桓曰我若不為此卿輩亦那得坐談禇季野問孫盛卿國史何當成孫云久應竟在公無暇故至今日禇曰古人述而不作何必在⟦{{SKchar|3641}}⟧室中謝公在東山朝命屢降而不動後出為桓宣武司馬將發新亭朝士咸出瞻送髙靈
```

---

### 25-paidiao — 25-paidiao-033 — `non_exact_entry_opening`

- classification: `unresolved`
- confidence: `low`
- requires visual verification: `True`
- recommended action: Review the exact character/glyph and boundary context; no automatic repair is made.
- Kanripo opening key: `庾園客詣孫監值行見齊莊在`
- Kanripo opening text (source spelling): `庾園客詣孫監值行見齊莊在`
- Kanripo location: `content/processed/shishuo/chapters/chapter-25.md`; normalized line `2502`; page `<pb:KR3l0002_SBCK_002-62b>`
- Wikisource match type: `suffix`
- Wikisource page: `Page:Sibu Congkan0464-劉義慶-世説新語-3-3.djvu/123`

```text
草何一物而有二稱謝未即荅時郝隆在坐應聲荅曰此甚易解處則為逺志出則為小草謝甚有愧色桓公目謝而笑曰郝叅軍此過乃不惡亦極有㑹⟦{{SKchar|2928}}⟧園客詣孫監值行見齊莊在外尚㓜而有神意⟦{{SKchar|2928}}⟧試之曰孫安國何在即荅曰𢈔穉恭家𢈔大笑曰諸孫大盛有兒如此又荅曰未若諸𢈔之翼翼還語人曰我故勝得重喚奴父名范𤣥平在簡文坐談欲屈引王長史曰卿助我王曰此非㧞山力所能助郝隆為桓公南蠻叅軍三月三日㑹作詩不能者罰酒三升隆初以不能受罰既飲攬筆便作一句云娵隅躍清池桓問娵隅是何物荅曰蠻名魚為娵隅桓公曰作
```

---

### 25-paidiao — 25-paidiao-034 — `non_exact_entry_opening`

- classification: `unresolved`
- confidence: `low`
- requires visual verification: `True`
- recommended action: Review the exact character/glyph and boundary context; no automatic repair is made.
- Kanripo opening key: `范玄平在簡文坐談欲屈引王`
- Kanripo opening text (source spelling): `范玄平在簡文坐談欲屈引王`
- Kanripo location: `content/processed/shishuo/chapters/chapter-25.md`; normalized line `2509`; page `<pb:KR3l0002_SBCK_002-63a>`
- Wikisource match type: `suffix`
- Wikisource page: `Page:Sibu Congkan0464-劉義慶-世説新語-3-3.djvu/124`

```text
外尚㓜而有神意⟦{{SKchar|2928}}⟧試之曰孫安國何在即荅曰𢈔穉恭家𢈔大笑曰諸孫大盛有兒如此又荅曰未若諸𢈔之翼翼還語人曰我故勝得重喚奴父名范𤣥平在簡文坐談欲屈引王長史曰卿助我王曰此非㧞山力所能助郝隆為桓公南蠻叅軍三月三日㑹作詩不能者罰酒三升隆初以不能受罰既飲攬筆便作一句云娵隅躍清池桓問娵隅是何物荅曰蠻名魚為娵隅桓公曰作詩何以作蠻語隆曰千里投公始得蠻府叅軍那得不作蠻語也𡊮羊甞詣劉恢恢在内眠未起𡊮因作詩調之曰角枕粲文茵錦衾爛長筵劉尚晉明帝女主見詩不平曰𡊮羊古之遺
```

---

### 25-paidiao — 25-paidiao-036 — `non_exact_entry_opening`

- classification: `unresolved`
- confidence: `low`
- requires visual verification: `True`
- recommended action: Review the exact character/glyph and boundary context; no automatic repair is made.
- Kanripo opening key: `袁羊甞詣劉恢恢在内眠未起`
- Kanripo opening text (source spelling): `袁羊甞詣劉恢恢在内眠未起`
- Kanripo location: `content/processed/shishuo/chapters/chapter-25.md`; normalized line `2519`; page `<pb:KR3l0002_SBCK_002-63b>`
- Wikisource match type: `suffix`
- Wikisource page: `Page:Sibu Congkan0464-劉義慶-世説新語-3-3.djvu/125`

```text
罰既飲攬筆便作一句云娵隅躍清池桓問娵隅是何物荅曰蠻名魚為娵隅桓公曰作詩何以作蠻語隆曰千里投公始得蠻府叅軍那得不作蠻語也𡊮羊甞詣劉恢恢在内眠未起𡊮因作詩調之曰角枕粲文茵錦衾爛長筵劉尚晉明帝女主見詩不平曰𡊮羊古之遺狂殷洪逺荅孫興公詩云聊復放一曲劉真長笑其語拙問曰君欲云那放殷曰㯓臘亦放何必其鎗鈴邪桓公既廢海西立簡文侍中謝公見桓公拜桓驚笑曰安石卿何事至爾謝曰未有君拜於前臣立於後郄重熈與謝公書道王敬仁聞一年少懷問鼎不知桓公德衰為復後生可畏張蒼梧是
```

---

### 25-paidiao — 25-paidiao-049 — `unmatched_entry_opening`

- classification: `unresolved`
- confidence: `low`
- requires visual verification: `True`
- recommended action: Inspect the same-edition page witness and the relevant glyph/character reading before classifying as a textual variant or source gap.
- Kanripo opening key: `郄嘉賓書與袁虎道戴安道謝`
- Kanripo opening text (source spelling): `郄嘉賓書與袁虎道戴安道謝`
- Kanripo location: `content/processed/shishuo/chapters/chapter-25.md`; normalized line `2581`; page `<pb:KR3l0002_SBCK_002-66b>`
- Wikisource match type: `none`
- Wikisource page: `not located`

```text
No aligned Wikisource reading.
```

---

### 25-paidiao — 25-paidiao-062 — `non_exact_entry_opening`

- classification: `unresolved`
- confidence: `low`
- requires visual verification: `True`
- recommended action: Review the exact character/glyph and boundary context; no automatic repair is made.
- Kanripo opening key: `桓玄出射有一劉叅軍與周叅`
- Kanripo opening text (source spelling): `桓玄出射有一劉叅軍與周叅`
- Kanripo location: `content/processed/shishuo/chapters/chapter-25.md`; normalized line `2644`; page `<pb:KR3l0002_SBCK_002-69a>`
- Wikisource match type: `suffix`
- Wikisource page: `Page:Sibu Congkan0464-劉義慶-世説新語-3-3.djvu/136`

```text
語桓曰矛頭淅米劒頭炊殷曰百嵗老翁攀枯枝顧曰井上轆轤卧嬰兒殷有一叅軍在坐云盲人騎瞎馬夜半臨深池殷曰咄咄逼人仲堪眇目故也桓𤣥出射有一劉叅軍與周叅軍朋賭垂成唯少一破劉謂周曰卿此起不破我當撻卿周曰何至受卿撻劉曰伯禽之貴尚不免撻而況於卿周殊無忤色桓語𢈔伯鸞曰劉叅軍宜停讀書周叅軍且勤學問桓南郡與道曜講老子王侍中爲主簿在坐桓曰王主簿可顧名思義王未荅且大笑桓曰王思道能作大家兒笑祖廣行恒縮頭詣桓南郡始下車桓曰天甚晴朗祖叅軍如從屋漏中來桓𤣥素輕桓崖崖在京下
```

---

### 25-paidiao — 25-paidiao-065 — `non_exact_entry_opening`

- classification: `unresolved`
- confidence: `low`
- requires visual verification: `True`
- recommended action: Review the exact character/glyph and boundary context; no automatic repair is made.
- Kanripo opening key: `桓玄素輕桓崖崖在京下有好`
- Kanripo opening text (source spelling): `桓玄素輕桓崖崖在京下有好`
- Kanripo location: `content/processed/shishuo/chapters/chapter-25.md`; normalized line `2662`; page `<pb:KR3l0002_SBCK_002-70a>`
- Wikisource match type: `suffix`
- Wikisource page: `Page:Sibu Congkan0464-劉義慶-世説新語-3-3.djvu/138`

```text
簿在坐桓曰王主簿可顧名思義王未荅且大笑桓曰王思道能作大家兒笑祖廣行恒縮頭詣桓南郡始下車桓曰天甚晴朗祖叅軍如從屋漏中來桓𤣥素輕桓崖崖在京下有好桃𤣥連就求之遂不得佳者𤣥與殷仲文書以為嗤笑曰德之休明肅慎貢其楛矢如其不爾籬壁間物亦不可得也
```

---

### 25-paidiao — `probable_one_character_shift`

- classification: `unresolved`
- confidence: `medium`
- requires visual verification: `True`
- recommended action: Use page-level visual witnesses to determine whether this is a missing/extra passage, a glyph/character variant, or a segmentation difference. No textual repair is performed.
- Kanripo main characters: 3371
- Wikisource main characters: 3371
- length delta (Wikisource − Kanripo): 0
- sequence ratio: 0.988727
- Kanripo location: `content/processed/shishuo/chapters/chapter-25.md`; page markers `['<pb:KR3l0002_SBCK_002-55b>', '<pb:KR3l0002_SBCK_002-56a>', '<pb:KR3l0002_SBCK_002-56b>', '<pb:KR3l0002_SBCK_002-57a>', '<pb:KR3l0002_SBCK_002-57b>', '<pb:KR3l0002_SBCK_002-58a>', '<pb:KR3l0002_SBCK_002-58b>', '<pb:KR3l0002_SBCK_002-59a>', '<pb:KR3l0002_SBCK_002-59b>', '<pb:KR3l0002_SBCK_002-60a>', '<pb:KR3l0002_SBCK_002-60b>', '<pb:KR3l0002_SBCK_002-61a>', '<pb:KR3l0002_SBCK_002-61b>', '<pb:KR3l0002_SBCK_002-62a>', '<pb:KR3l0002_SBCK_002-62b>', '<pb:KR3l0002_SBCK_002-63a>', '<pb:KR3l0002_SBCK_002-63b>', '<pb:KR3l0002_SBCK_002-64a>', '<pb:KR3l0002_SBCK_002-64b>', '<pb:KR3l0002_SBCK_002-65a>', '<pb:KR3l0002_SBCK_002-65b>', '<pb:KR3l0002_SBCK_002-66a>', '<pb:KR3l0002_SBCK_002-66b>', '<pb:KR3l0002_SBCK_002-67a>', '<pb:KR3l0002_SBCK_002-67b>', '<pb:KR3l0002_SBCK_002-68a>', '<pb:KR3l0002_SBCK_002-68b>', '<pb:KR3l0002_SBCK_002-69a>', '<pb:KR3l0002_SBCK_002-69b>', '<pb:KR3l0002_SBCK_002-70a>', '<pb:KR3l0002_SBCK_002-70b>']`
- Wikisource page range: `Page:Sibu Congkan0464-劉義慶-世説新語-3-3.djvu/108` through `Page:Sibu Congkan0464-劉義慶-世説新語-3-3.djvu/138` (30 pages)
- Wikisource source URL range: `https://zh.wikisource.org/wiki/Page%3ASibu%20Congkan0464-%E5%8A%89%E7%BE%A9%E6%85%B6-%E4%B8%96%E8%AA%AC%E6%96%B0%E8%AA%9E-3-3.djvu%2F108` through `https://zh.wikisource.org/wiki/Page%3ASibu%20Congkan0464-%E5%8A%89%E7%BE%A9%E6%85%B6-%E4%B8%96%E8%AA%AC%E6%96%B0%E8%AA%9E-3-3.djvu%2F138`

```text
四凶在下荅曰非唯四凶亦有丹朱於是一坐大笑晉文帝與二陳共車過喚鍾㑹同載即駛車委去比出已逺既至因嘲之曰與人期行何以遲遲望卿遥遥不至㑹荅曰矯然懿實何必同羣帝復問㑹臯繇何如人荅曰上不及堯舜下不逮周孔亦一時之懿士鍾毓為黄門郎有機警在景王坐燕飲時陳羣子玄伯武周子元夏同在坐共嘲毓景王曰臯繇何如人對曰古之懿士顧謂玄伯元夏曰君子周而不比羣而不黨嵇阮山劉在竹林酣飲王戎後徃步兵曰俗物已復來敗人意王笑曰卿輩意亦復可敗邪晉武帝問孫皓聞南人好作爾汝歌頗能為不皓正飲酒因舉觴勸帝而言曰昔與汝為鄰今與汝為臣上汝一桮酒令汝壽萬春帝悔之孫子荆年少時欲隱語王武子當枕石漱流誤曰漱石枕流王曰流可枕石可漱乎孫曰所以枕流欲洗其耳所以漱石欲礪其齒頭責秦子羽云子曽不如太原温顒潁川荀㝢范陽張華士卿劉許義陽鄒湛河南鄭詡此數子者
```

```text
四凶在下荅曰非唯四凶亦有丹朱於是一坐大笑晉文帝與二陳共車過喚鍾㑹同載即駛車委去比出已逺既至因嘲之曰與人期行何以遲遲望卿遥遥不至㑹荅曰矯然懿實何必同羣帝復問㑹臯繇何如人荅曰上不及堯舜下不逮周孔亦一時之懿士鍾毓為黄門郎有機警在景王坐燕飲時陳羣子𤣥伯武周子元夏同在坐共嘲毓景王曰臯繇何如人對曰古之懿士顧謂𤣥伯元夏曰君子周而不比羣而不黨嵇阮山劉在竹林酣飲王戎後徃步兵曰俗物已復來敗人意王笑曰卿輩意亦復可敗邪晉武帝問孫皓聞南人好作爾汝歌頗能為不皓正飲酒因舉觴勸帝而言曰昔與汝為鄰今與汝為臣上汝一桮酒令汝壽萬春帝悔之孫子荆年少時欲隱語王武子當枕石漱流誤曰漱石枕流王曰流可枕石可漱乎孫曰所以枕流欲洗其耳所以漱石欲礪其齒頭責秦子羽云子曽不如太原温顒潁川荀㝢范陽張華士卿劉許義陽鄒湛河南鄭詡此數子者
```

---

### 26-qingdi — 26-qingdi-002 — `non_exact_entry_opening`

- classification: `unresolved`
- confidence: `low`
- requires visual verification: `True`
- recommended action: Review the exact character/glyph and boundary context; no automatic repair is made.
- Kanripo opening key: `庾元規語周伯仁諸人皆以君`
- Kanripo opening text (source spelling): `庾元規語周伯仁諸人皆以君`
- Kanripo location: `content/processed/shishuo/chapters/chapter-26.md`; normalized line `2673`; page `<pb:KR3l0002_SBCK_002-70b>`
- Wikisource match type: `suffix`
- Wikisource page: `Page:Sibu Congkan0464-劉義慶-世説新語-3-3.djvu/139`

```text
王太尉問眉子汝叔名士何以不相推重眉子曰何有名士終日妄語𢈔元規語周伯仁諸人皆以君方樂周曰何樂謂樂毅邪𢈔曰不爾樂令耳周曰何乃刻畫無鹽以唐突西子也深公云人謂⟦{{SKchar|2928}}⟧元規名士胷中柴⟦{{SKchar|3140}}⟧三斗許⟦{{SKchar|2928}}⟧公權重足傾王公⟦{{SKchar|2928}}⟧在石頭王在冶城坐大風⟦{{SKchar|3951}}⟧塵王以扇拂塵曰元規塵汙人王右軍少時甚澀訥在大將軍許王⟦{{SKchar|2928}}⟧二公後來右軍便起欲去大將軍留之曰爾家司空元規復可所難王丞相輕蔡公曰我與安期千里共遊洛水邊何處聞有蔡充兒禇太傅
```

---

### 26-qingdi — 26-qingdi-003 — `unmatched_entry_opening`

- classification: `unresolved`
- confidence: `low`
- requires visual verification: `True`
- recommended action: Inspect the same-edition page witness and the relevant glyph/character reading before classifying as a textual variant or source gap.
- Kanripo opening key: `深公云人謂庾元規名士胷中`
- Kanripo opening text (source spelling): `深公云人謂庾元規名士胷中`
- Kanripo location: `content/processed/shishuo/chapters/chapter-26.md`; normalized line `2680`; page `<pb:KR3l0002_SBCK_002-71a>`
- Wikisource match type: `none`
- Wikisource page: `not located`

```text
No aligned Wikisource reading.
```

---

### 26-qingdi — 26-qingdi-004 — `unmatched_entry_opening`

- classification: `unresolved`
- confidence: `low`
- requires visual verification: `True`
- recommended action: Inspect the same-edition page witness and the relevant glyph/character reading before classifying as a textual variant or source gap.
- Kanripo opening key: `庾公權重足傾王公庾在石頭`
- Kanripo opening text (source spelling): `庾公權重足傾王公庾在石頭`
- Kanripo location: `content/processed/shishuo/chapters/chapter-26.md`; normalized line `2681`; page `<pb:KR3l0002_SBCK_002-71a>`
- Wikisource match type: `none`
- Wikisource page: `not located`

```text
No aligned Wikisource reading.
```

---

### 26-qingdi — 26-qingdi-012 — `non_exact_entry_opening`

- classification: `unresolved`
- confidence: `low`
- requires visual verification: `True`
- recommended action: Review the exact character/glyph and boundary context; no automatic repair is made.
- Kanripo opening key: `袁虎伏滔同在桓公府桓公毎`
- Kanripo opening text (source spelling): `袁虎伏滔同在桓公府桓公毎`
- Kanripo location: `content/processed/shishuo/chapters/chapter-26.md`; normalized line `2737`; page `<pb:KR3l0002_SBCK_002-73b>`
- Wikisource match type: `suffix`
- Wikisource page: `Page:Sibu Congkan0464-劉義慶-世説新語-3-3.djvu/145`

```text
君頗聞劉景升不有大牛重千斤噉芻豆十倍於常牛負重致逺曽不若一羸牸魏武入荆州烹以饗士卒于時莫不稱快意以況𡊮四坐既駭𡊮亦失色𡊮虎伏滔同在桓公府桓公毎遊燕輙命𡊮伏𡊮甚耻之恒歎曰公之厚意未足以榮國士與伏滔比肩亦何辱如之高柔在東甚爲謝仁祖所重既出不爲王劉所知仁祖曰近見高柔大自敷奏然未有所得真長云故不可在偏地居輕在角䚥中爲人作議論髙柔聞之云我就伊無所求人有向真長學此言者真長曰我寔亦無可與伊者然遊燕猶與諸人書可要安固安固者髙柔也劉尹江虨王叔虎孫興公同坐
```

---

### 26-qingdi — 26-qingdi-016 — `non_exact_entry_opening`

- classification: `unresolved`
- confidence: `low`
- requires visual verification: `True`
- recommended action: Review the exact character/glyph and boundary context; no automatic repair is made.
- Kanripo opening key: `桓公欲遷都以張拓定之業孫`
- Kanripo opening text (source spelling): `桓公欲遷都以張拓定之業孫`
- Kanripo location: `content/processed/shishuo/chapters/chapter-26.md`; normalized line `2760`; page `<pb:KR3l0002_SBCK_002-74b>`
- Wikisource match type: `suffix`
- Wikisource page: `Page:Sibu Congkan0464-劉義慶-世説新語-3-3.djvu/147`

```text
特是醜言聲拙視瞻孫綽作列仙商丘子賛曰所牧何物殆非真豬儻遇風雲為我龍攄時人多以為能王藍田語人云近見孫家兒作文道何物真豬也⟦{{SKchar|3129}}⟧公欲遷都以張拓定之業孫長樂上表諫此議甚有理⟦{{SKchar|3129}}⟧見表心服而忿其為異令人致意孫云君何不尋遂初賦而彊知人家國事孫長樂兄弟就謝公宿言至欵雜劉夫人在壁後聽之具聞其語謝公明日還問昨客何似劉對曰亡兄門未有如此賔客謝深有愧色簡文與許玄度共語許云舉君親以為難簡文便不復答許去後而言曰玄度故可不至於此謝萬夀春敗後還書與王右軍云慙負宿顧右軍推書
```

---

### 26-qingdi — 26-qingdi-024 — `non_exact_entry_opening`

- classification: `unresolved`
- confidence: `low`
- requires visual verification: `True`
- recommended action: Review the exact character/glyph and boundary context; no automatic repair is made.
- Kanripo opening key: `庾道季詫謝公曰裴郎云謝安`
- Kanripo opening text (source spelling): `庾道季詫謝公曰裴郎云謝安`
- Kanripo location: `content/processed/shishuo/chapters/chapter-26.md`; normalized line `2790`; page `<pb:KR3l0002_SBCK_002-76a>`
- Wikisource match type: `suffix`
- Wikisource page: `Page:Sibu Congkan0464-劉義慶-世説新語-3-3.djvu/150`

```text
交非勢利心猶澄水同此玄味王孝伯見曰才士不遜亡祖何至與此人周旋謝太傅謂子姪曰中郎始是獨有千載車騎曰中郎衿抱未虚復那得獨有𢈔道季詫謝公曰裴郎云謝安謂裴郎乃可不惡何得為復飲酒裴郎又云謝安目支道林如九方臯之相馬略其玄黄取其儁逸謝公云都無此二語裴自為此辭耳𢈔意甚不以為好因陳東亭經酒壚下賦讀畢都不下賞裁直云君乃復作裴氏學於此語林遂廢今時有者皆是先寫無復謝語王北中郎不爲林公所知乃箸論沙門不得爲高士論大略云高士必在於縱心調畼沙門雖云俗外反更束於教非情性
```

---

### 26-qingdi — 26-qingdi-027 — `non_exact_entry_opening`

- classification: `unresolved`
- confidence: `low`
- requires visual verification: `True`
- recommended action: Review the exact character/glyph and boundary context; no automatic repair is made.
- Kanripo opening key: `殷顗庾恒並是謝鎮西外孫殷`
- Kanripo opening text (source spelling): `殷顗庾恒並是謝鎮西外孫(適庾龢次女僧韶適殷/謝氏譜曰尚長女僧要)
(歆)殷`
- Kanripo location: `content/processed/shishuo/chapters/chapter-26.md`; normalized line `2813`; page `<pb:KR3l0002_SBCK_002-77a>`
- Wikisource match type: `suffix`
- Wikisource page: `Page:Sibu Congkan0464-劉義慶-世説新語-3-3.djvu/152`

```text
得爲高士論大略云高士必在於縱心調畼沙門雖云俗外反更束於教非情性自得之謂也人問顧長康何以不作洛生詠荅曰何至作老婢聲殷顗𢈔𢘆並是謝鎮西外孫殷少而率悟𢈔毎不推甞俱詣謝公謝公熟視殷曰阿巢故似鎮西於是𢈔下聲語曰定何似謝公續復云巢頰似鎮西𢈔復云頰似足作徤不舊目韓康伯將肘無風骨符宏叛來歸國謝太傅毎加接引宏自以有才多好上人坐上無折之者適王子猷來太傅使共語子猷直孰視良久回語太傅云亦復竟不異人宏大慚而⟦{{SKchar|2385}}⟧支道林入東見王子猷兄弟還人問見諸王何如荅曰見一羣白頸烏
```

---

### 26-qingdi — 26-qingdi-029 — `non_exact_entry_opening`

- classification: `unresolved`
- confidence: `low`
- requires visual verification: `True`
- recommended action: Review the exact character/glyph and boundary context; no automatic repair is made.
- Kanripo opening key: `符宏叛來歸國謝太傅毎加接`
- Kanripo opening text (source spelling): `符宏叛來歸國謝太傅毎加接`
- Kanripo location: `content/processed/shishuo/chapters/chapter-26.md`; normalized line `2819`; page `<pb:KR3l0002_SBCK_002-77a>`
- Wikisource match type: `suffix`
- Wikisource page: `Page:Sibu Congkan0464-劉義慶-世説新語-3-3.djvu/152`

```text
不推甞俱詣謝公謝公熟視殷曰阿巢故似鎮西於是𢈔下聲語曰定何似謝公續復云巢頰似鎮西𢈔復云頰似足作徤不舊目韓康伯將肘無風骨符宏叛來歸國謝太傅毎加接引宏自以有才多好上人坐上無折之者適王子猷來太傅使共語子猷直孰視良久回語太傅云亦復竟不異人宏大慚而⟦{{SKchar|2385}}⟧支道林入東見王子猷兄弟還人問見諸王何如荅曰見一羣白頸烏但聞喚啞啞聲王中郎舉許玄度為吏部郎郗重熈曰相王好事不可使阿訥在坐頭王興道謂謝望蔡霍霍如失鷹師⟦{{SKchar|3129}}⟧南郡毎見人不快輒嗔云君得哀家梨當復不烝食不
```

---

### 26-qingdi — 26-qingdi-033 — `non_exact_entry_opening`

- classification: `unresolved`
- confidence: `low`
- requires visual verification: `True`
- recommended action: Review the exact character/glyph and boundary context; no automatic repair is made.
- Kanripo opening key: `桓南郡毎見人不快輒嗔云君`
- Kanripo opening text (source spelling): `桓南郡毎見人不快輒嗔云君`
- Kanripo location: `content/processed/shishuo/chapters/chapter-26.md`; normalized line `2831`; page `<pb:KR3l0002_SBCK_002-77b>`
- Wikisource match type: `suffix`
- Wikisource page: `Page:Sibu Congkan0464-劉義慶-世説新語-3-3.djvu/153`

```text
見諸王何如荅曰見一羣白頸烏但聞喚啞啞聲王中郎舉許玄度為吏部郎郗重熈曰相王好事不可使阿訥在坐頭王興道謂謝望蔡霍霍如失鷹師⟦{{SKchar|3129}}⟧南郡毎見人不快輒嗔云君得哀家梨當復不烝食不
```

---

### 26-qingdi — `probable_one_character_shift`

- classification: `unresolved`
- confidence: `medium`
- requires visual verification: `True`
- recommended action: Use page-level visual witnesses to determine whether this is a missing/extra passage, a glyph/character variant, or a segmentation difference. No textual repair is performed.
- Kanripo main characters: 1524
- Wikisource main characters: 1524
- length delta (Wikisource − Kanripo): 0
- sequence ratio: 0.982283
- Kanripo location: `content/processed/shishuo/chapters/chapter-26.md`; page markers `['<pb:KR3l0002_SBCK_002-71a>', '<pb:KR3l0002_SBCK_002-71b>', '<pb:KR3l0002_SBCK_002-72a>', '<pb:KR3l0002_SBCK_002-72b>', '<pb:KR3l0002_SBCK_002-73a>', '<pb:KR3l0002_SBCK_002-73b>', '<pb:KR3l0002_SBCK_002-74a>', '<pb:KR3l0002_SBCK_002-74b>', '<pb:KR3l0002_SBCK_002-75a>', '<pb:KR3l0002_SBCK_002-75b>', '<pb:KR3l0002_SBCK_002-76a>', '<pb:KR3l0002_SBCK_002-76b>', '<pb:KR3l0002_SBCK_002-77a>', '<pb:KR3l0002_SBCK_002-77b>', '<pb:KR3l0002_SBCK_002-78a>']`
- Wikisource page range: `Page:Sibu Congkan0464-劉義慶-世説新語-3-3.djvu/139` through `Page:Sibu Congkan0464-劉義慶-世説新語-3-3.djvu/153` (15 pages)
- Wikisource source URL range: `https://zh.wikisource.org/wiki/Page%3ASibu%20Congkan0464-%E5%8A%89%E7%BE%A9%E6%85%B6-%E4%B8%96%E8%AA%AC%E6%96%B0%E8%AA%9E-3-3.djvu%2F139` through `https://zh.wikisource.org/wiki/Page%3ASibu%20Congkan0464-%E5%8A%89%E7%BE%A9%E6%85%B6-%E4%B8%96%E8%AA%AC%E6%96%B0%E8%AA%9E-3-3.djvu%2F153`

```text
以為好因陳東亭經酒壚下賦讀畢都不下賞裁直云君乃復作裴氏學於此語林遂廢今時有者皆是先寫無復謝語王北中郎不爲林公所知乃箸論沙門不得爲高士論大略云高士必在於縱心調畼沙門雖云俗外反更束於教非情性自得之謂也人問顧長康何以不作洛生詠荅曰何至作老婢聲殷顗庾恒並是謝鎮西外孫殷少而率悟庾毎不推甞俱詣謝公謝公熟視殷曰阿巢故似鎮西於是庾下聲語曰定何似謝公續復云巢頰似鎮西庾復云頰似足作徤不舊目韓康伯將肘無風骨符宏叛來歸國謝太傅毎加接引宏自以有才多好上人坐上無折之者適王子猷來太傅使共語子猷直孰視良久回語太傅云亦復竟不異人宏大慚而退支道林入東見王子猷兄弟還人問見諸王何如荅曰見一羣白頸烏但聞喚啞啞聲王中郎舉許玄度為吏部郎郗重熈曰相王好事不可使阿訥在坐頭王興道謂謝望蔡霍霍如失鷹師桓南郡毎見人不快輒嗔云君
```

```text
以為好因陳東亭經酒壚下賦讀畢都不下賞裁直云君乃復作裴氏學於此語林遂廢今時有者皆是先寫無復謝語王北中郎不爲林公所知乃箸論沙門不得爲高士論大略云高士必在於縱心調畼沙門雖云俗外反更束於教非情性自得之謂也人問顧長康何以不作洛生詠荅曰何至作老婢聲殷顗𢈔𢘆並是謝鎮西外孫殷少而率悟𢈔毎不推甞俱詣謝公謝公熟視殷曰阿巢故似鎮西於是𢈔下聲語曰定何似謝公續復云巢頰似鎮西𢈔復云頰似足作徤不舊目韓康伯將肘無風骨符宏叛來歸國謝太傅毎加接引宏自以有才多好上人坐上無折之者適王子猷來太傅使共語子猷直孰視良久回語太傅云亦復竟不異人宏大慚而⟦{{SKchar|2385}}⟧支道林入東見王子猷兄弟還人問見諸王何如荅曰見一羣白頸烏但聞喚啞啞聲王中郎舉許玄度為吏部郎郗重熈曰相王好事不可使阿訥在坐頭王興道謂謝望蔡霍霍如失鷹師⟦{{SKchar|3129}}⟧南郡毎見人不快輒嗔云君
```

---

### 27-jiajue — 27-jiajue-001 — `unmatched_entry_opening`

- classification: `unresolved`
- confidence: `low`
- requires visual verification: `True`
- recommended action: Inspect the same-edition page witness and the relevant glyph/character reading before classifying as a textual variant or source gap.
- Kanripo opening key: `魏武少時甞與袁紹好為游俠`
- Kanripo opening text (source spelling): `魏武少時甞與袁紹好為游俠`
- Kanripo location: `content/processed/shishuo/chapters/chapter-27.md`; normalized line `2835`; page `<pb:KR3l0002_SBCK_002-78a>`
- Wikisource match type: `none`
- Wikisource page: `not located`

```text
No aligned Wikisource reading.
```

---

### 27-jiajue — 27-jiajue-005 — `non_exact_entry_opening`

- classification: `unresolved`
- confidence: `low`
- requires visual verification: `True`
- recommended action: Review the exact character/glyph and boundary context; no automatic repair is made.
- Kanripo opening key: `袁紹年少時曽遣人夜以劒擲`
- Kanripo opening text (source spelling): `袁紹年少時曽遣人夜以劒擲`
- Kanripo location: `content/processed/shishuo/chapters/chapter-27.md`; normalized line `2853`; page `<pb:KR3l0002_SBCK_002-78b>`
- Wikisource match type: `suffix`
- Wikisource page: `Page:Sibu Congkan0464-劉義慶-世説新語-3-3.djvu/155`

```text
為實謀逆者挫氣矣魏武常云我眠中不可妄近近便斫人亦不自覺左右冝深慎此後陽眠所幸一人竊以⟦{{SKchar|3425}}⟧覆之因便斫殺自爾毎眠左右莫敢近者⟦{{SKchar|2783}}⟧紹年少時曽遣人夜以劒擲魏武少下不箸魏武揆之其後來必高因帖臥牀上劒至果高王大將軍既為逆頓軍姑孰晉明帝以英武之才猶相猜憚乃箸戎服騎巴賨馬齎一金馬鞭隂察軍形勢未至十餘里有一客姥居店賣食帝過愒之謂姥曰王敦舉兵圖逆猜害忠良朝廷駭懼社稷是憂故劬勞晨夕用相覘察恐形迹危露或致狼狽追迫之日姥其匿之便與客姥馬鞭而去行敦營匝而出軍士覺曰此非
```

---

### 27-jiajue — 27-jiajue-010 — `unmatched_entry_opening`

- classification: `unresolved`
- confidence: `low`
- requires visual verification: `True`
- recommended action: Inspect the same-edition page witness and the relevant glyph/character reading before classifying as a textual variant or source gap.
- Kanripo opening key: `諸葛令女庾氏婦既寡誓云不`
- Kanripo opening text (source spelling): `諸葛令女庾氏婦既寡誓云不`
- Kanripo location: `content/processed/shishuo/chapters/chapter-27.md`; normalized line `2901`; page `<pb:KR3l0002_SBCK_002-81a>`
- Wikisource match type: `none`
- Wikisource page: `not located`

```text
No aligned Wikisource reading.
```

---

### 27-jiajue — 27-jiajue-013 — `non_exact_entry_opening`

- classification: `unresolved`
- confidence: `low`
- requires visual verification: `True`
- recommended action: Review the exact character/glyph and boundary context; no automatic repair is made.
- Kanripo opening key: `范玄平為人好用智數而有時`
- Kanripo opening text (source spelling): `范玄平為人好用智數而有時`
- Kanripo location: `content/processed/shishuo/chapters/chapter-27.md`; normalized line `2927`; page `<pb:KR3l0002_SBCK_002-82a>`
- Wikisource match type: `suffix`
- Wikisource page: `Page:Sibu Congkan0464-劉義慶-世説新語-3-3.djvu/162`

```text
不惡但吾寒士不宐與卿計欲令阿智娶之文度欣然而啓藍田云興公向來忽言欲與阿智㛰藍田驚喜既成㛰女之頑嚚欲過阿智方知興公之詐范⟦{{SKchar|2593}}⟧平為人好用智數而有時以多數失㑹嘗失官居東陽⟦{{SKchar|3129}}⟧大司馬在南州故往投之⟦{{SKchar|3129}}⟧時方欲招起屈滯以傾朝廷且⟦{{SKchar|2593}}⟧平在京素亦有譽⟦{{SKchar|3129}}⟧謂逺來投己喜躍非常比入至庭傾身引望語笑歡甚顧謂⟦{{SKchar|2783}}⟧虎曰范公且可作太常卿范裁坐⟦{{SKchar|3129}}⟧便謝其逺來意范雖實投⟦{{SKchar|3129}}⟧而恐以趨時損名乃曰雖懷朝宗㑹有亡兒瘞在此故來省視⟦{{SKchar|3129}}⟧悵然失望向之虚佇一時都盡謝遏年少時好箸紫羅香囊垂覆手太傅患之而不
```

---

### 27-jiajue — `probable_one_character_shift`

- classification: `unresolved`
- confidence: `medium`
- requires visual verification: `True`
- recommended action: Use page-level visual witnesses to determine whether this is a missing/extra passage, a glyph/character variant, or a segmentation difference. No textual repair is performed.
- Kanripo main characters: 1384
- Wikisource main characters: 1384
- length delta (Wikisource − Kanripo): 0
- sequence ratio: 0.981214
- Kanripo location: `content/processed/shishuo/chapters/chapter-27.md`; page markers `['<pb:KR3l0002_SBCK_002-78b>', '<pb:KR3l0002_SBCK_002-79a>', '<pb:KR3l0002_SBCK_002-79b>', '<pb:KR3l0002_SBCK_002-80a>', '<pb:KR3l0002_SBCK_002-80b>', '<pb:KR3l0002_SBCK_002-81a>', '<pb:KR3l0002_SBCK_002-81b>', '<pb:KR3l0002_SBCK_002-82a>', '<pb:KR3l0002_SBCK_002-82b>']`
- Wikisource page range: `Page:Sibu Congkan0464-劉義慶-世説新語-3-3.djvu/154` through `Page:Sibu Congkan0464-劉義慶-世説新語-3-3.djvu/163` (10 pages)
- Wikisource source URL range: `https://zh.wikisource.org/wiki/Page%3ASibu%20Congkan0464-%E5%8A%89%E7%BE%A9%E6%85%B6-%E4%B8%96%E8%AA%AC%E6%96%B0%E8%AA%9E-3-3.djvu%2F154` through `https://zh.wikisource.org/wiki/Page%3ASibu%20Congkan0464-%E5%8A%89%E7%BE%A9%E6%85%B6-%E4%B8%96%E8%AA%AC%E6%96%B0%E8%AA%9E-3-3.djvu%2F163`

```text
魏武少時甞與袁紹好為游俠觀人新婚因潜入主人園中夜呌呼云有偷兒賊青廬中人皆出觀魏武乃入抽刃劫新婦與紹還出失道墜枳棘中紹不能得動復大呌云偷兒在此紹遑迫自擲出遂以俱免魏武行役失汲道軍皆渇乃令曰前有大梅林饒子甘酸可以解渇士卒聞之口皆出水乗此得及前源魏武常言人欲危己已輒心動因語所親小人曰汝懷刃宻來我側我必說心動執汝使行刑汝但勿言其使無他當厚相報執者信焉不以為懼遂斬之此人至死不知也左右以為實謀逆者挫氣矣魏武常云我眠中不可妄近近便斫人亦不自覺左右冝深慎此後陽眠所
```

```text
魏武少時甞與𡊮紹好為游俠觀人新婚因潜入主人園中夜呌呼云有偷兒賊青廬中人皆出觀魏武乃入抽刃劫新婦與紹還出失道墜枳𣗥中紹不能得動復大呌云偷兒在此紹遑迫自擲出遂以俱免魏武行役失汲道軍皆渇乃令曰前有大梅林饒子甘酸可以解渇士卒聞之口皆出水乗此得及前源魏武常言人欲危己已輒心動因語所親小人曰汝懷刃宻來我側我必說心動執汝使行刑汝但勿言其使無他當厚相報執者信焉不以為懼遂斬之此人至死不知也左右以為實謀逆者挫氣矣魏武常云我眠中不可妄近近便斫人亦不自覺左右冝深慎此後陽眠所
```

---

### 28-chumian — 28-chumian-002 — `non_exact_entry_opening`

- classification: `unresolved`
- confidence: `low`
- requires visual verification: `True`
- recommended action: Review the exact character/glyph and boundary context; no automatic repair is made.
- Kanripo opening key: `桓公入蜀至三峽中部伍中有`
- Kanripo opening text (source spelling): `桓公入蜀至三峽中部伍中有`
- Kanripo location: `content/processed/shishuo/chapters/chapter-28.md`; normalized line `2947`; page `<pb:KR3l0002_SBCK_002-83a>`
- Wikisource match type: `suffix`
- Wikisource page: `Page:Sibu Congkan0464-劉義慶-世説新語-3-3.djvu/164`

```text
重時論亦以擬王後為繼母族黨所讒誣之為狂逆將逺徙友人王夷甫之徒詣檻車與别厷問朝廷何以徙我王曰言卿狂逆厷曰逆則應殺狂何所徙⟦{{SKchar|3129}}⟧公入蜀至三峽中部伍中有得猨子者其母縁岸哀號行百餘里不去遂跳上船至便即絶破視其腹中腸皆寸寸斷公聞之怒命黜其人殷中軍⟦{{SKchar|3425}}⟧廢在信安終日⟦{{SKchar|2989}}⟧書空作字⟦{{SKchar|3951}}⟧州吏民尋義逐之竊視唯作咄咄怪事四字而已桓公坐有參軍椅烝薤不時解共食者又不助而掎終不放舉坐皆笑⟦{{SKchar|3129}}⟧公曰同盤尚不相助況復危難乎敕令免官殷中軍廢後恨簡文曰上人箸百尺樓上儋梯將去鄧竟陵免官後赴
```

---

### 28-chumian — 28-chumian-003 — `unmatched_entry_opening`

- classification: `unresolved`
- confidence: `low`
- requires visual verification: `True`
- recommended action: Inspect the same-edition page witness and the relevant glyph/character reading before classifying as a textual variant or source gap.
- Kanripo opening key: `殷中軍𬒳廢在信安終日恒書`
- Kanripo opening text (source spelling): `殷中軍𬒳廢在信安終日恒書`
- Kanripo location: `content/processed/shishuo/chapters/chapter-28.md`; normalized line `2952`; page `<pb:KR3l0002_SBCK_002-83a>`
- Wikisource match type: `none`
- Wikisource page: `not located`

```text
No aligned Wikisource reading.
```

---

### 28-chumian — 28-chumian-007 — `non_exact_entry_opening`

- classification: `unresolved`
- confidence: `low`
- requires visual verification: `True`
- recommended action: Review the exact character/glyph and boundary context; no automatic repair is made.
- Kanripo opening key: `桓宣武既廢太宰父子仍上表`
- Kanripo opening text (source spelling): `桓宣武既廢太宰父子仍上表`
- Kanripo location: `content/processed/shishuo/chapters/chapter-28.md`; normalized line `2973`; page `<pb:KR3l0002_SBCK_002-84a>`
- Wikisource match type: `suffix`
- Wikisource page: `Page:Sibu Congkan0464-劉義慶-世説新語-3-3.djvu/166`

```text
殷中軍廢後恨簡文曰上人箸百尺樓上儋梯將去鄧竟陵免官後赴山陵過見大司馬⟦{{SKchar|3129}}⟧公公問之曰卿何以更瘦鄧曰有愧於叔達不能不恨於破甑⟦{{SKchar|3129}}⟧宣武既廢太宰父子仍上表曰應割近情以存逺計若除太宰父子可無後憂簡文手荅表曰所不忍言況過於言宣武又重表辭轉苦切簡文更荅曰若晉室靈長明公便宜奉行此詔如大運去矣請避賢路⟦{{SKchar|3129}}⟧公讀詔手戰流汗於此乃止太宰父子逺徙新安⟦{{SKchar|3129}}⟧⟦{{SKchar|2593}}⟧敗後殷仲文還為太司馬咨議意似二三非復往日大司馬府㕔前有一老槐甚扶踈殷因月朔與衆在㕔視槐良久嘆曰槐樹婆娑無復生意殷仲文
```

---

### 28-chumian — 28-chumian-008 — `non_exact_entry_opening`

- classification: `unresolved`
- confidence: `low`
- requires visual verification: `True`
- recommended action: Review the exact character/glyph and boundary context; no automatic repair is made.
- Kanripo opening key: `桓玄敗後殷仲文還為太司馬`
- Kanripo opening text (source spelling): `桓玄敗後殷仲文還為太司馬`
- Kanripo location: `content/processed/shishuo/chapters/chapter-28.md`; normalized line `2983`; page `<pb:KR3l0002_SBCK_002-84b>`
- Wikisource match type: `suffix`
- Wikisource page: `Page:Sibu Congkan0464-劉義慶-世説新語-3-3.djvu/167`

```text
於言宣武又重表辭轉苦切簡文更荅曰若晉室靈長明公便宜奉行此詔如大運去矣請避賢路⟦{{SKchar|3129}}⟧公讀詔手戰流汗於此乃止太宰父子逺徙新安⟦{{SKchar|3129}}⟧⟦{{SKchar|2593}}⟧敗後殷仲文還為太司馬咨議意似二三非復往日大司馬府㕔前有一老槐甚扶踈殷因月朔與衆在㕔視槐良久嘆曰槐樹婆娑無復生意殷仲文既素有名望自謂必當阿衡朝政忽作東陽太守意甚不平及之郡至富陽慨然嘆曰看此山川形勢當復出一孫伯符
```

---

### 28-chumian — `annotation_range_difference`

- classification: `unresolved`
- confidence: `medium`
- requires visual verification: `True`
- recommended action: Use page-level visual witnesses to determine whether this is a missing/extra passage, a glyph/character variant, or a segmentation difference. No textual repair is performed.
- Kanripo main characters: 474
- Wikisource main characters: 474
- length delta (Wikisource − Kanripo): 0
- sequence ratio: 0.978903
- Kanripo location: `content/processed/shishuo/chapters/chapter-28.md`; page markers `['<pb:KR3l0002_SBCK_002-83a>', '<pb:KR3l0002_SBCK_002-83b>', '<pb:KR3l0002_SBCK_002-84a>', '<pb:KR3l0002_SBCK_002-84b>', '<pb:KR3l0002_SBCK_002-85a>']`
- Wikisource page range: `Page:Sibu Congkan0464-劉義慶-世説新語-3-3.djvu/163` through `Page:Sibu Congkan0464-劉義慶-世説新語-3-3.djvu/168` (6 pages)
- Wikisource source URL range: `https://zh.wikisource.org/wiki/Page%3ASibu%20Congkan0464-%E5%8A%89%E7%BE%A9%E6%85%B6-%E4%B8%96%E8%AA%AC%E6%96%B0%E8%AA%9E-3-3.djvu%2F163` through `https://zh.wikisource.org/wiki/Page%3ASibu%20Congkan0464-%E5%8A%89%E7%BE%A9%E6%85%B6-%E4%B8%96%E8%AA%AC%E6%96%B0%E8%AA%9E-3-3.djvu%2F168`

```text
卿何以更瘦鄧曰有愧於叔達不能不恨於破甑桓宣武既廢太宰父子仍上表曰應割近情以存逺計若除太宰父子可無後憂簡文手荅表曰所不忍言況過於言宣武又重表辭轉苦切簡文更荅曰若晉室靈長明公便宜奉行此詔如大運去矣請避賢路桓公讀詔手戰流汗於此乃止太宰父子逺徙新安桓玄敗後殷仲文還為太司馬咨議意似二三非復往日大司馬府㕔前有一老槐甚扶踈殷因月朔與衆在㕔視槐良久嘆曰槐樹婆娑無復生意殷仲文既素有名望自謂必當阿衡朝政忽作東陽太守意甚不平及之郡至富陽慨然嘆曰看此山川形勢當復出一孫伯符
```

```text
卿何以更瘦鄧曰有愧於叔達不能不恨於破甑⟦{{SKchar|3129}}⟧宣武既廢太宰父子仍上表曰應割近情以存逺計若除太宰父子可無後憂簡文手荅表曰所不忍言況過於言宣武又重表辭轉苦切簡文更荅曰若晉室靈長明公便宜奉行此詔如大運去矣請避賢路⟦{{SKchar|3129}}⟧公讀詔手戰流汗於此乃止太宰父子逺徙新安⟦{{SKchar|3129}}⟧⟦{{SKchar|2593}}⟧敗後殷仲文還為太司馬咨議意似二三非復往日大司馬府㕔前有一老槐甚扶踈殷因月朔與衆在㕔視槐良久嘆曰槐樹婆娑無復生意殷仲文既素有名望自謂必當阿衡朝政忽作東陽太守意甚不平及之郡至富陽慨然嘆曰看此山川形勢當復出一孫伯符
```

---

### 29-jianshe — 29-jianshe-008 — `unmatched_entry_opening`

- classification: `unresolved`
- confidence: `low`
- requires visual verification: `True`
- recommended action: Inspect the same-edition page witness and the relevant glyph/character reading before classifying as a textual variant or source gap.
- Kanripo opening key: `蘇峻之亂庾太尉南奔見陶公`
- Kanripo opening text (source spelling): `蘇峻之亂庾太尉南奔見陶公`
- Kanripo location: `content/processed/shishuo/chapters/chapter-29.md`; normalized line `3019`; page `<pb:KR3l0002_SBCK_002-86a>`
- Wikisource match type: `none`
- Wikisource page: `not located`

```text
No aligned Wikisource reading.
```

---

### 29-jianshe — `annotation_range_difference`

- classification: `unresolved`
- confidence: `medium`
- requires visual verification: `True`
- recommended action: Use page-level visual witnesses to determine whether this is a missing/extra passage, a glyph/character variant, or a segmentation difference. No textual repair is performed.
- Kanripo main characters: 380
- Wikisource main characters: 380
- length delta (Wikisource − Kanripo): 0
- sequence ratio: 0.984211
- Kanripo location: `content/processed/shishuo/chapters/chapter-29.md`; page markers `['<pb:KR3l0002_SBCK_002-85b>', '<pb:KR3l0002_SBCK_002-86a>', '<pb:KR3l0002_SBCK_002-86b>']`
- Wikisource page range: `Page:Sibu Congkan0464-劉義慶-世説新語-3-3.djvu/168` through `Page:Sibu Congkan0464-劉義慶-世説新語-3-3.djvu/171` (4 pages)
- Wikisource source URL range: `https://zh.wikisource.org/wiki/Page%3ASibu%20Congkan0464-%E5%8A%89%E7%BE%A9%E6%85%B6-%E4%B8%96%E8%AA%AC%E6%96%B0%E8%AA%9E-3-3.djvu%2F168` through `https://zh.wikisource.org/wiki/Page%3ASibu%20Congkan0464-%E5%8A%89%E7%BE%A9%E6%85%B6-%E4%B8%96%E8%AA%AC%E6%96%B0%E8%AA%9E-3-3.djvu%2F171`

```text
李王武子求之與不過數十王武子因其上直率將少年能食之者持斧詣園飽共噉畢伐之送一車枝與和公問曰何如君李和既得唯笑而已王戎儉吝其從子㛰與一單衣後更責之司徒王戎既貴且富區宅僮牧膏田水碓之屬洛下無比契䟽鞅掌毎與夫人燭下散籌筭計王戎有好李賣之恐人得其種恒鑚其核王戎女適裴頠貸錢數萬女歸戎色不說女遽還錢乃釋然衞江州在尋陽有知舊人投之都不料理唯餉王不留行一斤此人得餉便命駕李弘範聞之曰家舅刻薄乃復驅使草木王丞相儉節帳下甘果盈溢不散渉春爛敗都督白之公令舍去曰慎不可令太郎知蘇峻之亂庾太尉南奔見陶公陶公雅相賞重陶性儉吝及食噉薤庾因留白陶問用此何為庾云故可種於是大嘆庾非唯風流兼有治實郗公大聚歛有錢數千萬嘉賔意甚不同常朝旦問訊郗家法子弟不坐因倚語移時遂及財貨事郗公曰汝正當欲得吾錢耳廼開庫一日令任意用郗
```

```text
李王武子求之與不過數十王武子因其上直率將少年能食之者持斧詣園飽共噉畢伐之送一車枝與和公問曰何如君李和既得唯笑而已王戎儉吝其從子㛰與一單衣後更責之司徒王戎既貴且富區宅僮牧膏田水碓之屬洛下無比契䟽鞅掌毎與夫人燭下散籌筭計王戎有好李賣之恐人得其種𢘆鑚其核王戎女適裴頠貸錢數萬女歸戎色不說女遽還錢乃釋然衞江州在尋陽有知舊人投之都不料理唯餉王不留行一斤此人得餉便命駕李⟦{{SKchar|2592}}⟧範聞之曰家舅刻薄乃復驅使草木王丞相儉節帳下甘果盈溢不散渉春爛敗都督白之公令舍去曰慎不可令太郎知蘇峻之亂⟦{{SKchar|2928}}⟧太尉南奔見陶公陶公雅相賞重陶性儉吝及食噉薤𢈔因留白陶問用此何為𢈔云故可種於是大嘆𢈔非唯風流兼有治實郗公大聚歛有錢數千萬嘉賔意甚不同常朝旦問訊郗家法子弟不坐因倚語移時遂及財貨事郗公曰汝正當欲得吾錢耳廼開庫一日令任意用郗
```

---

### 30-taichi — 30-taichi-005 — `non_exact_entry_opening`

- classification: `unresolved`
- confidence: `low`
- requires visual verification: `True`
- recommended action: Review the exact character/glyph and boundary context; no automatic repair is made.
- Kanripo opening key: `石崇為客作豆粥咄嗟便辦恒`
- Kanripo opening text (source spelling): `石崇為客作豆粥咄嗟便辦恒`
- Kanripo location: `content/processed/shishuo/chapters/chapter-30.md`; normalized line `3055`; page `<pb:KR3l0002_SBCK_002-88a>`
- Wikisource match type: `prefix`
- Wikisource page: `Page:Sibu Congkan0464-劉義慶-世説新語-3-3.djvu/174`

```text
王石所未知作王君夫以⟦{{SKchar|1579}}⟧糒澳釡石季倫用蠟燭作炊君夫作紫⟦{{SKchar|3274}}⟧布歩障碧綾裏四十里石崇作錦歩障五十里以敵之石以椒為泥王以赤石脂泥壁石崇為客作豆粥咄嗟便辦𢘆冬天得韭蓱䪢又牛形狀氣力不勝王愷牛而與愷出遊極晩發爭入洛城崇牛數十歩後迅若飛禽愷牛絶走不能及毎以此三事為搤腕乃宻貨崇帳下都督及御車人問所以都督曰豆至難煑唯豫作熟末客至作白粥以投之韭蓱䪡是搗韭根雜以麥苗爾復問馭人牛所以駛馭人云牛本不遲由將車人不及制之爾急時聽偏轅則駛矣愷悉從之遂争長石崇後聞皆殺告者
```

---

### 30-taichi — 30-taichi-009 — `non_exact_entry_opening`

- classification: `unresolved`
- confidence: `low`
- requires visual verification: `True`
- recommended action: Review the exact character/glyph and boundary context; no automatic repair is made.
- Kanripo opening key: `王武子𬒳責移第北邙下于時`
- Kanripo opening text (source spelling): `王武子𬒳責移第北邙下(不平濟爲河南尹未拜行/晉諸公賛曰濟與從兄恬)
(者以濟爲不長者尋轉太僕而王恬已見委任濟遂/過王宫吏不時下道濟於車前鞭之有司奏免官論)
(外/斥)于時`
- Kanripo location: `content/processed/shishuo/chapters/chapter-30.md`; normalized line `3091`; page `<pb:KR3l0002_SBCK_002-89b>`
- Wikisource match type: `suffix`
- Wikisource page: `Page:Sibu Congkan0464-劉義慶-世説新語-3-3.djvu/177`

```text
又以為疾已之寳聲色甚厲崇曰不足恨今還卿乃命左右悉取珊瑚樹有三尺四尺條榦絶世光彩溢目者六七枚如愷許比甚衆愷惘然自失王武子⟦{{SKchar|3425}}⟧責移第北邙下于時人多地貴濟好馬射買地作埒編錢匝地竟埒時人號曰金溝石崇每與王敦入學戲見顔原象而嘆曰若與同升孔堂去人何必有間王曰不知餘人云何子貢去卿差近石正色云士當令身名俱泰何至以𦉥牖語人彭城王有快牛至愛惜之王太尉與射賭得之彭城王曰君欲自乘則不論若欲噉者當以二十肥者代之既不廢噉又存所愛王遂殺噉王右軍少時在周侯末坐割牛心噉之
```

---

### 31-fenjuan — 31-fenjuan-004 — `unmatched_entry_opening`

- classification: `unresolved`
- confidence: `low`
- requires visual verification: `True`
- recommended action: Inspect the same-edition page witness and the relevant glyph/character reading before classifying as a textual variant or source gap.
- Kanripo opening key: `桓宣武與袁彦道樗蒱袁彦道`
- Kanripo opening text (source spelling): `桓宣武與袁彦道樗蒱袁彦道`
- Kanripo location: `content/processed/shishuo/chapters/chapter-31.md`; normalized line `3122`; page `<pb:KR3l0002_SBCK_002-91a>`
- Wikisource match type: `none`
- Wikisource page: `not located`

```text
No aligned Wikisource reading.
```

---

### 31-fenjuan — 31-fenjuan-008 — `non_exact_entry_opening`

- classification: `unresolved`
- confidence: `low`
- requires visual verification: `True`
- recommended action: Review the exact character/glyph and boundary context; no automatic repair is made.
- Kanripo opening key: `桓南郡小兒時與諸從兄弟各`
- Kanripo opening text (source spelling): `桓南郡小兒時與諸從兄弟各`
- Kanripo location: `content/processed/shishuo/chapters/chapter-31.md`; normalized line `3142`; page `<pb:KR3l0002_SBCK_002-92a>`
- Wikisource match type: `suffix`
- Wikisource page: `Page:Sibu Congkan0464-劉義慶-世説新語-3-3.djvu/182`

```text
之轉苦便各以帬帶繞手恭府近千人悉呼入齋大左右雖少亦命前意便欲相殺何僕射無計因起排坐二人之間方得分散所謂勢利之交古人羞之⟦{{SKchar|3129}}⟧南郡小兒時與諸從兄弟各養鵝共鬬南郡鵝毎不如甚以為忿廼夜往鵝欄間取諸兄弟鵝悉殺之既曉家人咸以驚駭云是變怪以白車騎車騎曰無所致怪當是南郡戲耳問果如之
```

---

### 31-fenjuan — `annotation_range_difference`

- classification: `unresolved`
- confidence: `medium`
- requires visual verification: `True`
- recommended action: Use page-level visual witnesses to determine whether this is a missing/extra passage, a glyph/character variant, or a segmentation difference. No textual repair is performed.
- Kanripo main characters: 510
- Wikisource main characters: 510
- length delta (Wikisource − Kanripo): 0
- sequence ratio: 0.986275
- Kanripo location: `content/processed/shishuo/chapters/chapter-31.md`; page markers `['<pb:KR3l0002_SBCK_002-90b>', '<pb:KR3l0002_SBCK_002-91a>', '<pb:KR3l0002_SBCK_002-91b>', '<pb:KR3l0002_SBCK_002-92a>']`
- Wikisource page range: `Page:Sibu Congkan0464-劉義慶-世説新語-3-3.djvu/178` through `Page:Sibu Congkan0464-劉義慶-世説新語-3-3.djvu/182` (5 pages)
- Wikisource source URL range: `https://zh.wikisource.org/wiki/Page%3ASibu%20Congkan0464-%E5%8A%89%E7%BE%A9%E6%85%B6-%E4%B8%96%E8%AA%AC%E6%96%B0%E8%AA%9E-3-3.djvu%2F178` through `https://zh.wikisource.org/wiki/Page%3ASibu%20Congkan0464-%E5%8A%89%E7%BE%A9%E6%85%B6-%E4%B8%96%E8%AA%AC%E6%96%B0%E8%AA%9E-3-3.djvu%2F182`

```text
魏武有一妓聲最清髙而情性酷惡欲殺則愛才欲置則不堪於是選百人一時俱教少時果有一人聲及之便殺惡性者王藍田性急嘗食雞子以筯刺之不得便大怒舉以擲地雞子於地圓轉未止仍下地以屐齒蹍之又不得瞋甚復於地取内口中齧破即吐之王右軍聞而大笑曰使安期有此性猶當無一豪可論況藍田邪王司州甞乘雪徃王螭許司州言氣少有牾逆於螭便作色不夷司州覺惡便輿牀就之持其臂曰汝詎復足與老兄計螭撥其手曰冷如鬼手馨彊來捉人臂桓宣武與袁彦道樗蒱袁彦道齒不合遂厲色擲去五木温太真云見袁生遷怒知顔子為貴謝無奕性麤彊以事不相得自往數王藍田肆言極罵王正色面壁不敢動半日謝去良久轉頭問左右小吏曰去未荅云已去然後復坐時人嘆其性急而能有所容王令詣謝公值習鑿齒已在坐當
```

```text
魏武有一妓聲最清髙而情性酷惡欲殺則愛才欲置則不堪於是選百人一時俱教少時果有一人聲及之便殺惡性者王藍田性急嘗食雞子以筯刺之不得便大怒舉以擲地雞子於地圓轉未止仍下地以⟦{{SKchar|2885}}⟧齒蹍之又不得瞋甚復於地取内口中齧破即吐之王右軍聞而大笑曰使安期有此性猶當無一豪可論況藍田邪王司州甞乘雪徃王螭許司州言氣少有牾逆於螭便作色不夷司州覺惡便輿牀就之持其臂曰汝詎復足與老兄計螭撥其手曰冷如⟦{{SKchar|3932}}⟧手馨彊來捉人臂⟦{{SKchar|3129}}⟧宣武與⟦{{SKchar|2783}}⟧彦道樗蒱⟦{{SKchar|2783}}⟧彦道齒不合遂厲色擲去五木温太真云見⟦{{SKchar|2783}}⟧生遷怒知顔子為貴謝無奕性麤彊以事不相得自往數王藍田肆言極罵王正色面壁不敢動半日謝去良久轉頭問左右小吏曰去未荅云已去然後復坐時人嘆其性急而能有所容王令詣謝公值習鑿齒已在坐當
```

---

### 32-chanxian — 32-chanxian-001 — `non_exact_entry_opening`

- classification: `unresolved`
- confidence: `low`
- requires visual verification: `True`
- recommended action: Review the exact character/glyph and boundary context; no automatic repair is made.
- Kanripo opening key: `王平子形甚散朗内實勁俠袁`
- Kanripo opening text (source spelling): `王平子形甚散朗内實勁俠(澄曰卿形雖散朗而内/鄧粲晉紀云劉琨甞謂)
(後果為王敦所害劉琨聞之曰自取死耳/勁狹以此處世難得其死澄黙然無以荅)
袁`
- Kanripo location: `content/processed/shishuo/chapters/chapter-32.md`; normalized line `3147`; page `<pb:KR3l0002_SBCK_002-92a>`
- Wikisource match type: `prefix`
- Wikisource page: `Page:Sibu Congkan0464-劉義慶-世説新語-3-3.djvu/182`

```text
王平子形甚散朗内實勁俠⟦{{SKchar|2783}}⟧恱有口才能短長說亦有精理始作謝玄參軍頗⟦{{SKchar|3425}}⟧禮遇後丁艱服除還都唯齎戰國䇿而已語人曰少年時讀論語老子又看莊易此皆是病痛事當何所益邪天下要物正有戰國策既下說司馬孝文王大見親待幾亂機軸俄而見誅孝武甚親敬王國寳王雅雅薦王珣於帝帝欲見之甞夜與國寳及雅相對帝微有酒色令喚珣垂至巳聞卒傳聲國寳自知才出珣下恐傾奪其寵
```

---

### 32-chanxian — 32-chanxian-002 — `non_exact_entry_opening`

- classification: `unresolved`
- confidence: `low`
- requires visual verification: `True`
- recommended action: Review the exact character/glyph and boundary context; no automatic repair is made.
- Kanripo opening key: `袁恱有口才能短長說亦有精`
- Kanripo opening text (source spelling): `袁恱有口才能短長說亦有精`
- Kanripo location: `content/processed/shishuo/chapters/chapter-32.md`; normalized line `3149`; page `<pb:KR3l0002_SBCK_002-92a>`
- Wikisource match type: `suffix`
- Wikisource page: `Page:Sibu Congkan0464-劉義慶-世説新語-3-3.djvu/182`

```text
王平子形甚散朗内實勁俠⟦{{SKchar|2783}}⟧恱有口才能短長說亦有精理始作謝玄參軍頗⟦{{SKchar|3425}}⟧禮遇後丁艱服除還都唯齎戰國䇿而已語人曰少年時讀論語老子又看莊易此皆是病痛事當何所益邪天下要物正有戰國策既下說司馬孝文王大見親待幾亂機軸俄而見誅孝武甚親敬王國寳王雅雅薦王珣於帝帝欲見之甞夜與國寳及雅相對帝微有酒色令喚珣垂至巳聞卒傳聲國寳自知才出珣下恐傾奪其寵因曰王珣當今名流陛下不宜
```

---

### 33-youhui — 33-youhui-012 — `non_exact_entry_opening`

- classification: `unresolved`
- confidence: `low`
- requires visual verification: `True`
- recommended action: Review the exact character/glyph and boundary context; no automatic repair is made.
- Kanripo opening key: `桓宣武對簡文帝不甚得語廢`
- Kanripo opening text (source spelling): `桓宣武對簡文帝不甚得語廢`
- Kanripo location: `content/processed/shishuo/chapters/chapter-33.md`; normalized line `3248`; page `<pb:KR3l0002_SBCK_002-96b>`
- Wikisource match type: `suffix`
- Wikisource page: `Page:Sibu Congkan0464-劉義慶-世説新語-3-3.djvu/191`

```text
奉大法敬信甚至大兒年未弱冠忽被篤疾兒既是偏所愛重為之祈請三寳晝夜不懈謂至誠有感者必當⟦{{SKchar|3681}}⟧祐而兒遂不濟於是結恨釋氏宿命都除⟦{{SKchar|3129}}⟧宣武對簡文帝不甚得語廢海西後宜自申叙乃豫撰數百語陳廢立之意既見簡文簡文便泣下數十行宣武矜愧不得一言⟦{{SKchar|3129}}⟧公卧語曰作此寂寂將為文景所笑既而屈起坐曰既不能㳅芳後世亦不足復遺臭萬載邪謝太傅於東船行小人引船或遲或速或停或待又放船從横撞人觸岸公初不呵譴人謂公常無嗔喜曽送兄征西葬還日莫雨駛小人皆醉不可處分公乃於車中手取車柱撞馭人聲色甚
```

---

### 33-youhui — 33-youhui-013 — `non_exact_entry_opening`

- classification: `unresolved`
- confidence: `low`
- requires visual verification: `True`
- recommended action: Review the exact character/glyph and boundary context; no automatic repair is made.
- Kanripo opening key: `桓公卧語曰作此寂寂將為文`
- Kanripo opening text (source spelling): `桓公卧語曰作此寂寂將為文`
- Kanripo location: `content/processed/shishuo/chapters/chapter-33.md`; normalized line `3252`; page `<pb:KR3l0002_SBCK_002-97a>`
- Wikisource match type: `suffix`
- Wikisource page: `Page:Sibu Congkan0464-劉義慶-世説新語-3-3.djvu/192`

```text
是結恨釋氏宿命都除⟦{{SKchar|3129}}⟧宣武對簡文帝不甚得語廢海西後宜自申叙乃豫撰數百語陳廢立之意既見簡文簡文便泣下數十行宣武矜愧不得一言⟦{{SKchar|3129}}⟧公卧語曰作此寂寂將為文景所笑既而屈起坐曰既不能㳅芳後世亦不足復遺臭萬載邪謝太傅於東船行小人引船或遲或速或停或待又放船從横撞人觸岸公初不呵譴人謂公常無嗔喜曽送兄征西葬還日莫雨駛小人皆醉不可處分公乃於車中手取車柱撞馭人聲色甚厲夫以水性沈柔入隘奔激方之人情固知迫隘之地無得保其夷粹簡文見田稻不識問是何草左右荅是稻簡文還三日不出
```

---

### 33-youhui — 33-youhui-016 — `non_exact_entry_opening`

- classification: `unresolved`
- confidence: `low`
- requires visual verification: `True`
- recommended action: Review the exact character/glyph and boundary context; no automatic repair is made.
- Kanripo opening key: `桓車騎在上明政獵東信至傳`
- Kanripo opening text (source spelling): `桓車騎在上明政獵東信至傳`
- Kanripo location: `content/processed/shishuo/chapters/chapter-33.md`; normalized line `3267`; page `<pb:KR3l0002_SBCK_002-97b>`
- Wikisource match type: `suffix`
- Wikisource page: `Page:Sibu Congkan0464-劉義慶-世説新語-3-3.djvu/193`

```text
以水性沈柔入隘奔激方之人情固知迫隘之地無得保其夷粹簡文見田稻不識問是何草左右荅是稻簡文還三日不出云寧有賴其末而不識其本⟦{{SKchar|3129}}⟧車騎在上明政獵東信至傳淮上大捷語左右云羣謝年少大破賊因發病薨談者以為此死賢於讓⟦{{SKchar|3951}}⟧之荆桓公初報破殷荆州曽講論語至富與貴是人之所欲不以其道得之不處𤣥意色甚惡
```

---

### 34-pilou — `annotation_range_difference`

- classification: `unresolved`
- confidence: `medium`
- requires visual verification: `True`
- recommended action: Use page-level visual witnesses to determine whether this is a missing/extra passage, a glyph/character variant, or a segmentation difference. No textual repair is performed.
- Kanripo main characters: 606
- Wikisource main characters: 607
- length delta (Wikisource − Kanripo): 1
- sequence ratio: 0.995878
- Kanripo location: `content/processed/shishuo/chapters/chapter-34.md`; page markers `['<pb:KR3l0002_SBCK_002-98b>', '<pb:KR3l0002_SBCK_002-99a>', '<pb:KR3l0002_SBCK_002-99b>', '<pb:KR3l0002_SBCK_002-100a>', '<pb:KR3l0002_SBCK_002-100b>']`
- Wikisource page range: `Page:Sibu Congkan0464-劉義慶-世説新語-3-3.djvu/194` through `Page:Sibu Congkan0464-劉義慶-世説新語-3-3.djvu/198` (5 pages)
- Wikisource source URL range: `https://zh.wikisource.org/wiki/Page%3ASibu%20Congkan0464-%E5%8A%89%E7%BE%A9%E6%85%B6-%E4%B8%96%E8%AA%AC%E6%96%B0%E8%AA%9E-3-3.djvu%2F194` through `https://zh.wikisource.org/wiki/Page%3ASibu%20Congkan0464-%E5%8A%89%E7%BE%A9%E6%85%B6-%E4%B8%96%E8%AA%AC%E6%96%B0%E8%AA%9E-3-3.djvu%2F198`

```text
有令名武帝崩選百二十挽郎一時之秀彦育長亦在其中王安豐選女壻從挽郎&KR0679;其勝者且擇取四人任猶在其中童少時神明可愛時人謂育長影亦好自過江便失志王丞相請先度時賢共至石頭迎之猶作疇日相待一見便覺有異坐席竟下飲便問人云此為茶為茗覺有異色乃自申明云向問飲為熱為冷耳甞行從棺邸下度流涕悲哀王丞相聞之曰此是有情癡謝虎子甞上屋熏鼠胡兒既無由知父為此事聞人道癡人有作此者戲笑之時道此非復一過太傅既了已之不知因其言次語胡兒曰世人以此謗中郎亦言我共作此胡兒懊熱一月日閉齋不出太傅虚託引已之過以相開悟可謂德敎殷仲堪父病虚悸聞牀下蟻動謂是牛鬬孝武不知是殷公問仲堪有一殷病如此不仲堪流涕而起曰臣進退唯谷虞嘯父為孝武侍中帝從容問曰卿在門下初不聞有所獻替虞家富春近海謂帝望其意氣對曰天時尚煗䱥魚蝦未可致尋當有所上獻帝撫
```

```text
有令名武帝崩選百二十挽郎一時之秀彦育長亦在其中王安豐選女壻從挽郎⟦{{SKchar|302}}⟧其勝者且擇取四人任猶在其中童少時神明可愛時人謂育長影亦好自過江便失志王丞相請先度時賢共至石頭迎之猶作疇日相待一見便覺有異坐席竟下飲便問人云此為茶為茗覺有異色乃自申明云向問飲為⟦{{SKchar|3289}}⟧為冷耳甞行從棺邸下度流涕悲哀王丞相聞之曰此是有情癡謝虎子甞上屋熏鼠胡兒既無由知父為此事聞人道癡人有作此者戲笑之時道此非復一過太傅既了已之不知因其言次語胡兒曰世人以此謗中郎亦言我共作此胡兒懊熱一月日閉齋不出太傅虚託引已之過以相開悟可謂德敎殷仲堪父病虚悸聞牀下蟻動謂是牛鬬孝武不知是殷公問仲堪有一殷病如此不仲堪流涕而起曰臣進𨓆唯谷虞嘯父為孝武侍中帝從容問曰卿在門下初不聞有所獻替虞家富春近海謂帝望其意氣對曰天時尚煗䱥魚蝦𩹦未可致尋當有所上獻帝
```

---

### 35-huoni — 35-huoni-001 — `non_exact_entry_opening`

- classification: `unresolved`
- confidence: `low`
- requires visual verification: `True`
- recommended action: Review the exact character/glyph and boundary context; no automatic repair is made.
- Kanripo opening key: `魏甄后惠而有色先為袁熈妻`
- Kanripo opening text (source spelling): `魏甄后惠而有色先為袁熈妻`
- Kanripo location: `content/processed/shishuo/chapters/chapter-35.md`; normalized line `3330`; page `<pb:KR3l0002_SBCK_002-100b>`
- Wikisource match type: `prefix`
- Wikisource page: `Page:Sibu Congkan0464-劉義慶-世説新語-3-3.djvu/199`

```text
魏甄后惠而有色先為⟦{{SKchar|2783}}⟧熈妻甚獲寵曹公之屠鄴也令疾召甄左右白五官中郎已將去公曰今年破賊正為奴荀奉倩與婦至篤冬月婦病熱乃出中庭自取冷還以身熨之婦亡奉倩後少時亦卒以是獲譏於世奉倩曰婦人德不足稱當以色為主裴令聞之曰此乃是興到之事非盛德言冀後人未昧此語賈公閭後妻郭氏酷妒有男兒名𥠖民生載周充自外還乳母抱兒在中庭兒見充喜踊充就乳母手中
```

---

### 36-chouxi — 36-chouxi-008 — `unmatched_entry_opening`

- classification: `unresolved`
- confidence: `low`
- requires visual verification: `True`
- recommended action: Inspect the same-edition page witness and the relevant glyph/character reading before classifying as a textual variant or source gap.
- Kanripo opening key: `桓玄將篡桓脩欲因玄在脩母`
- Kanripo opening text (source spelling): `桓玄將篡桓脩欲因玄在脩母`
- Kanripo location: `content/processed/shishuo/chapters/chapter-36.md`; normalized line `3455`; page `<pb:KR3l0002_SBCK_002-106a>`
- Wikisource match type: `none`
- Wikisource page: `not located`

```text
No aligned Wikisource reading.
```

---

### 36-chouxi — `missing_kanripo_passage`

- classification: `unresolved`
- confidence: `low`
- requires visual verification: `True`
- recommended action: Use page-level visual witnesses to determine whether this is a missing/extra passage, a glyph/character variant, or a segmentation difference. No textual repair is performed.
- Kanripo main characters: 659
- Wikisource main characters: 6978
- length delta (Wikisource − Kanripo): 6319
- sequence ratio: 0.17101
- Kanripo location: `content/processed/shishuo/chapters/chapter-36.md`; page markers `['<pb:KR3l0002_SBCK_002-103b>', '<pb:KR3l0002_SBCK_002-104a>', '<pb:KR3l0002_SBCK_002-104b>', '<pb:KR3l0002_SBCK_002-105a>', '<pb:KR3l0002_SBCK_002-105b>', '<pb:KR3l0002_SBCK_002-106a>', '<pb:KR3l0002_SBCK_002-106b>']`
- Wikisource page range: `Page:Sibu Congkan0464-劉義慶-世説新語-3-3.djvu/204` through `Page:Sibu Congkan0464-劉義慶-世説新語-3-3.djvu/256` (59 pages)
- Wikisource source URL range: `https://zh.wikisource.org/wiki/Page%3ASibu%20Congkan0464-%E5%8A%89%E7%BE%A9%E6%85%B6-%E4%B8%96%E8%AA%AC%E6%96%B0%E8%AA%9E-3-3.djvu%2F204` through `https://zh.wikisource.org/wiki/Page%3ASibu%20Congkan0464-%E5%8A%89%E7%BE%A9%E6%85%B6-%E4%B8%96%E8%AA%AC%E6%96%B0%E8%AA%9E-3-3.djvu%2F256`

```text
其宜右軍遂稱疾去郡以憤慨致終王東亭與孝伯語後漸異孝伯謂東亭曰卿便不可復測荅曰王陵廷争陳平從黙但問克終云何耳王孝伯死縣其首於大桁司馬太傅命駕出至標所孰視首曰卿何故趣欲殺我邪桓玄將篡桓脩欲因玄在脩母許襲之庾夫人云汝等近過我餘年我養之不忍見行此事
```

```text
其宜右軍遂稱疾去郡以憤慨致終王東亭與孝伯語後漸異孝伯謂東亭曰卿便不可復測荅曰王陵廷争陳平從黙但問克終云何耳王孝伯死縣其首於大桁司馬太傅命駕出至標所孰視首曰卿何故趣欲殺我邪桓玄將篡⟦{{SKchar|3129}}⟧脩欲因⟦{{SKchar|2593}}⟧在脩母許襲之⟦{{SKchar|2928}}⟧夫人云汝等近過我餘年我養之不忍見行此事世說新語下卷下刻世說新語序吳郡袁褧撰嘗攷載記所述晉人話言簡約玄澹爾雅有韻世言江左善淸談今閱新語信乎其言之也臨川撰爲此書採掇綜叙明畼不繁孝標所注能收錄諸家小史分釋其義詁訓之賞見於高似孫緯略余家藏宋本是放翁校刋本謝湖躬耕之暇毛披心寄自謂可觀爰付梓人傳之同好因嘆昔人論司馬氏之祚亡於淸談斯言也無乃過甚矣乎竹林之儔希慕沂樂䔵亭之集咏歌堯風陶荆州之勤敏謝東山之恬鎭解莊易則輔嗣平叔擅其宗析⟦{{SKchar|3133}}⟧言則道林法深領其乗或詞冷而趣遠或事⟦{{SKchar|1216}}⟧而意奧風旨各殊人有興託王⟦{{SKchar|3561}}⟧弘祖士雅之流才通氣峻心翼王室又斑斑載諸册簡是可非之者哉詩不云乎濟濟多士文王以寧余以琅琊王之渡江諸賢弘賛之力爲多非强說也夫諸晤言率遇藻裁遂爲終身品目故⟦{{SKchar|3841}}⟧以標格相高玄虚成習一時雅尚有東京㕑俊之流風焉然曠達拓落濫觴莫拯取譏世敎撫卷惜之此於諸賢不無遺憾焉耳矣刻成序之歳立秋日也世說新語目錄上卷德行言語上卷政事文學中卷方正雅量識鑒中卷賞譽品藻規箴捷悟夙惠豪爽下卷容止自新企羡傷逝棲逸賢媛術解巧藝寵禮任誕簡傲下卷排調輕詆假譎黜免儉嗇汰汐忿狷䜛險尤悔紕漏惑溺⟦{{SKchar|2631}}⟧隟世說新語目錄宋臨川王義慶采擷漢晉以來佳事佳話爲世說新語極爲精絶而猶未爲奇也梁劉孝標注此書引援詳確有不言之妙如引漢魏吳諸史及子傳地理之書皆不必言只如晉氏一朝史及晉諸公列傳譜錄文章凡一百六十六家皆岀於正史之外紀載特詳聞見未接寔爲注書之法右世⟦{{SKchar|3664}}⟧三十六篇世所傳⟦{{SKchar|3325}}⟧爲十卷或作四十五篇而末卷但重出前九卷中所載余家舊藏葢得之王原叔家後得晏元獻公手自校本盡去重復其注亦小加剪截最爲善本㬜人雅尚清談唐初史臣脩書率意竄㝎多非舊語尚頼此書以傳後世然字有譌舛語有難解以它書證之間有可是正處而注亦比晏本時爲增損至於所疑則不敢⟦{{SKchar|2836}}⟧下雌黄姑亦傳疑以竢通博夏四月癸亥廣川董弅題郡中舊有南史劉賔客集版皆廢于火世說亦不復在㳺到官始重刻之以存故事世說最後成因併識于卷末重五日新定郡守笠澤陸游書⟦{{SKchar|2902}}⟧吴郡袁氏嘉趣坣重雕世說新語校語宋本每半葉十行行十九字目錄作德行一言語二皆平行卷首款式如左世說新語上之上宋臨川王義慶撰梁劉孝標注郭林宗袁宏雖淸易挹也李元禮風格秀整有文武㑺才李元禮嘗歎荀淑鍾皓定陵陳稺叔後進之士分爲二提行起陳太丘持杖後從鯤華歆嚴若朝典管寧王朗臘之明日爲祝歳王祥使祥晝視鳥雀夜則趍鼠王戎云嵇本姓溪王戎和嶠王隠晉書曰梁王趙王梁孝王彤王戎云太保居在正始中理中淸遠王安豐遭艱毀濬不形王里父渾渾字長原有才望郗公翼爲剡縣顧榮在洛陽乃割炙以噉之周鎭罷臨川郡鎭淸約寡欲鄧攸以牛馬負妻子以叛王長豫丞相還臺及未行嘗不送至車後桓常侍父頴累遷散騎常侍以業慈淸淨朗縣東二百里𡵙山中庾公卽復害其生謝太傅父治武昌太守晉簡文意色不說仁聞有智度范宣人寧可使婦無㡓耶王僕射旣憂慽在貎桓南郡鮑季禮企生揮泣曰吳道助附子兄弟有貪泉邊文禮見袁奉高堯德末彰嶽至今不緫也孔文舉年十歲父宙泰世都尉輒引小者嘗與儀周旋乎孔文舉有二子偷那得行禮孔融被收安有巢覆而卵不破者太祖收寘法焉荀慈明與汝南袁閬相見依據者何經祁奚爲中軍尉禰衡乃今錄爲鼓吏南郡龐士元引士元爲軍帥中郎將但末遇耳劉公幹使楨隨侍太子鍾毓持此欲安歸乎何平叔云無所事任嵇中散先君嘗謂之曰雌鳴六鄧艾口喫嵇中散旣被誅其進止無不同不慮家之有無晉武帝始登阼字安宇各是一物所以爲主也滿奮畏風作琉璃屛諸葛靚在吳如斯諸名士共至洛水戲父又北平將軍樂令女樂令旣允朝望中朝有小兒故光武嘗謂景丹曰大將軍反病瘧耳庾公造周伯仁汝南賁泰淵通淸操之士伯仁將祛舊風過江諸人使稅之君蓋歸之顧司空吳郡劉琨以有殊勳乃知帝王自有貞也郗太尉拜司空語同坐曰上問揚雄李尋對曰高坐道人尸黎密冢曰高坐摯瞻太守故以此答敦第五琦佛圖澄開棺無屍陶公疾篤劉弘鎭沔南臨書振腕張玄之被親故泣不被親故不泣臥北首顧悅經霜彌茂臣蒲柳之質簡文入華林園覺鳥獸禽魚莊周釣在濮水曰願以境內累莊子吾亦寧曳尾於塗中支道林沈思道行冷然獨暢羊秉秉羣從父率禮相承劉尹云王微王氏譜曰劉眞長就劉宿王右軍衛商鞅諸庶孽子所著詩賦誄頌王中郎祖東海太守丞於陵仲子荀中郎荀羨字全則謝公云怪怖其言猶河漢而無極也支公好鶴鑿北阬山晉武帝玄答有辭致也袁彥伯魏中郎令煥孫綽賦遂初高柔字也桓征西目曰王子敬聞公哀孝武王混摘句王子敬云從山陰道上行摧榦竦條司馬太傅齋中夜坐重明秀有才會桓玄義興還後丈夫豈可以此事語人邪桓玄旣纂位當時殊忤旨謝靈運好戴曲柄笠以罪伏誅子修心守眞賀太傅並歷美官山公以器重朝望父曜寃句令賈充充起家爲尙書遷廷尉山司徒性高朗而率至累啓亮可爲左丞相非選官才王丞相網密刑峻少有悟者丞相嘗夏月至石頭然三捉三治陶公性檢厲又好督勸於人何驃騎作會稽欲白斷常客若得門庭山陰人也弿字道眞王劉與林公應對玄言王大王大甚以爲佳殷仲堪王東亭問曰鄭玄在馬融門下少而好間鄭玄欲注春秋傳鄭玄家奴婢皆讀書鍾會旣定便回急走何平叔注老子自然出拔過之何晏注老子但應諾諾遂不復注裴成公爲世名論初注莊子者數十家此書詎復須注太傅主簿阮宣子王裴弟子悉集鴻臚丞差有祿卿常無食衞玠始度江言必入眞舊云王丞相過江左麝食柏而香豈惟蒸之使重殷中軍爲庾公長史桓宣武語人曰殷中軍見佛經云浮屠者劉眞長與殷淵源談公輸般爲高雲梯宣武集諸名勝講易動靜有爲有北來道人上人常是逆風家莊子逍遙篇歷太常護國將軍尺鷃之起楡枋則同於大通矣殷中軍殷中軍雖思慮通長便苦湯池鐵城王逸少作會稽卿欲見不三乘佛家滯義方便則止行六度許椽及於法師並在會稽王脩小字也流淸舉熙乃歎曰殷謝諸人共集色閒則無空明則不能見彼謝有問殷無答殷中軍導則俱絕有相之流張憑舉孝廉及同舉者共笑之支道林謝顧謂諸人曲終而招子貢善談玄速殷中軍孫安國亦覺殊不及向僧意在瓦官寺中意謂王曰殷中軍被廢七覺之聲殷荆州曾問遠公誦鑒淹遠鐘王臨之女字英彥提婆初至爲東亭第符堅文帝漉敊以爲汁魏朝封晉文王爲公故怡退左太冲遭人而間武帝借其書二車劉伶沛鄴人以宇宙爲狹嘗與俗士相悟衢行無轍迹行則操巵執瓢奮髯箕踞習鑿齒出爲衡陽郡不推吳楚也孫興公云作文大治袁虎少貧辭文藻拔桓宣武北征殊可觀王孝伯至其弟王睹户前桓玄嘗登江陵城文多不盡載郭淮淮在關中三十餘年諸葛亮穎川徐元⟦{{SKchar2|32}}⟧夏侯玄此人尤能以通家少年遇我爲今史責人邪夏侯泰初無騫諤風高貴鄕公昭垂涕問陳泰曰和嶠語嶠曰東官文武之阼武帝語和嶠曰常山王况以天下之廣杜預拜鎭南將軍羊穉舒晉武帝時然得去晉紀山公大兒著短帢雄有器識向雄鄭玄曰爲兵主求攻代盧志見一麞然已見父手迹使歔歎無辭爲三日畢還見崔崔曰府君見人盌鬼魅又作充貎甥羊忱父繇車騎掾王太尉庾卿之不置元皇帝旣登阼以阿帝旨周叔治奴好自愛周伯仁刀協勃海敗至江南敗死明帝在西堂敦仗勇士路戎等因欲殺之蘇峻三千餘家庾公臨去瓜衍之田吾獲狄田蘇子高事平仕人膾截耳梅頤少好學而求實進止頤弟陶及侃將蒞廣州何次道盛明之世孔君平回謝之孫興公太和劉簡嘗聽記父挻阮光祿旣時爲會稽羅君章棗陽韓康伯五大司馬王文度爲桓公長史時惡見文度已復癡畏桓溫面王子敬歌者吹律太極殿始成魏阼縣橙上題之王恭虨張玄孰視嵇中散固不與無以淸潔王道夏候太初衣服焦然陪列於松柏下王戎爲侍中乃發口詔曰裴叔則以相婚黨裴遐遐正戲鎭壽陽王夷甫與裴景聲聞善人自謂理構多如王丞相主簿几案間事祖士少范陽遒人佔奪鄕里先人田地地主多恨許侍中不得快孰禇公於牽安令沈充爲縣令欲食䴵不郄鑒字子房庾太尉三師敗績王劭必有入禍謝太傅盤桓東山時太傅神情方玉桓公伏甲晉阼存亡弗能及明公何有命部左右支道林還東郄嘉賓謝公與人圍棋氏賊符堅十萬頭匹王子猷子敬不惶取屐符堅游魂近境王僧彌汝故是吳興溪中釣碣耳王珉謝玄王東亭公甚欲其爲人太元末至央星太元末曹公少時嚴明有才略何晏而復私讐也勸嘏結交云晉武帝講武息役弭兵無所標明潘陽仲見王敦與滔同潦雄勇好騎射豪傑勒手不能書衞玠年五歲傳嘏極貴重之張季鷹翰以疾歸府王平子志大其量王大將軍始下父淮冀州刺吏王大將軍旣亡必興愍惻以父名會武昌孟嘉子孫家焉戴安道王長史見之王仲祖殊有确然之志桓公將伐蜀三峽未易可克縣軍深入郗超與謝玄氏人也徤韓康伯與謝玄績晉陽秋郗超與傅瑗周旋在光祿大大夫車胤父夏月則練囊陳仲舉嘗歎曰嘗作常謝子微召功曹公孫度避地遼東王濬或裴叔則鐘會異之王戎目山巨源而其器亦入道山公舉阮咸爲散騎侍郎王戎目阮文業河淸太守王戎云太尉當可活不王汝南少所優濶加博措閑雅張華見褚陶作鷗鳥水硾二賦吳歸命世祖有問秀才吳舊姓何如陸士衡士龍容貎瓖偉衛伯玉猶廓雲霧而覩靑天王大尉大尉王夷甫吾等皆煩太傅府凝而禦之邈淸才也中之上止此宋本連林下諸賢以下爲一卷林下諸賢劉漠太傅東海王貞淑平粹十年日幼學明謝幼輿曰太始初到洛下會秋泉後胡當入洛劉琨稱祖車騎虞預晉書曰逖字士穉則中宵起坐天未欲滅寇王大將軍殊未有得卞令目叔向叔向羊舌盼也王敦爲大將軍當復絕倒王平子微王丞相云距戰不宜住拜王丞相招祖約頭鬢未理亦小倦王大將軍殊爲陵遲年二十有七世目揚朗淮仲庾公爲護軍有似廨署何次道字建寧杜弘治丹陽世目杜弘治淸標令上也有人目杜弘治標解甚淸盛德之風蕭中郎孫丞公丞會稽孔沈桀劉尹每稱王長史云篤義穆族不修小潔林公謂王右軍云謝太傅爲桓公司馬共語至瞑欽其盛名桓宣武表云入贊百揆世目謝尙招悟令上也王劉聽林公講濛云聽講許玄度稽叔夜簡文云至故有局陳爲一則初字提行起慕容晉乃分僧衆上勝可投法汰以十二卒劉尹先推謝鎭西謝後雅重劉人問王長史江虨簡文云劉尹打吳四姓舊目云謝車騎問謝公况眞長子謝公領中書監向見阿瓜正是使人不能已王詢王子敬弘雅有氣王恭而慮弗見令司馬太傅沈烈汝南陳仲舉劉叔朱寓劉佑龐士元至吳或問如所自爲勝耶周瑜領南郡琮字子黃顧劭覽倚仗之要害諸葛瑾弟亮時人謂諸葛因爲氏後有當不冀州剌史楊淮淮劉令言始入洛納叢王夷甫云閭丘冲不能虧損王夷甫以王東海比樂令江左名士博王大將軍在西朝時若斯儌狠囗言不然也王丞相二弟敝宋禕未詳宋禕王丞相辟王藍田爲掾然曠澹處郗司空家有傖奴簡私暱罕交遊時人共論晉武帝必舉朝會之不可撫軍問孫興公劉眞長曰淸易令達桓大司馬下都克復舊京桓公問孔西陽故乃勝也謝公與時賢共賞字茂重未之達也謝萬壽春敗後失士卒情失士衆之爲便向還南劉尹謂謝仁祖曰非奔走也王右軍問許玄度何如安石謝公云金谷中魚池士窟孫興公許玄度俱與負俗之談袁彥伯爲吏部郎郄嘉賓王子猷子敬兄弟歸成都後居貧王孝伯道謝公王孝伯問謝公桓玄爲太傅何如卿第七叔京房與漢元帝今治也亂也遂以房爲東郡孫皓問丞相陸凱曰不敢加誅也何宴鄧颺頃夢靑蠅鴟鴞食桑椹位重山岳見不談也大網羅永寧曠中懷王夷甫婦高尙人郗太尉晚節詣丞相丞相翹須蘇峻東征沈充將至吳密勑左右斬首於京都字功高小庾在荆州時若有斯言王右軍與王敬仁議更克王大語東亭卿民有㑺才並有名聲出珣右遠公在廬山中遂託空崖魏武嘗過曹娥碑下存其父尸曰何晏七歲其時泰宜祿韓康伯數歲兒云已足王大將軍年少時王大將軍自目高朗疎率王處仲每酒後轍詠老驥伏櫪晉明帝欲起池臺好養武士王大將軍始欲下都處分樹置庾穉恭然後議其所任耳雅有三志每以門第威重⟦{{SKchar2|32}}⟧指魏趙軍陳林道在西岸年一十有六魏武將見匈奴使魏□曰裴令公目王安豐目甚淸炤有人詣王太尉仕至修武令石頭事故求救陶公庾太尉使吏因便據胡床劉尹道桓公皆祿胙不終王敬倫持儀操也王長史步入尙書著公服簡文作相自然湛若神君舉止端詳周處年少時乃自吳戴淵少時狀見處士戴淵企羨第十六王右軍太原孫丞公等孫子荆孫曰諸君不死而令武子死乎顧彥先張季膺庾文康靈□志支道林喪法䖍郗嘉賓喪超年四十一王子猶子敬子敬子敬人琴俱亡阮步兵論五帝三王之義孔車騎游散名山南陽劉驎之縁道以乞窮乏去道近南陽翟道淵徵國子博士孟萬年絕人間之事康僧淵在豫章加已處之怡然郗超故不果遺陳嬰者嬰母見之漢元帝單于求朝昭君恚怒之趙母其况惡乎以諫作列女傳解許允爲晉景王所誅回遑不定允有正情王經笑而謂曰于寶山公與嵇阮君才致殊不如賈充前婦且郭槐彊狠陶公少有大志侃父丹娶新淦湛氏女陶公少時䱹常有飮限庾玉臺請溫有宥王右軍郗夫人傾筐倒屐荀勗善解音律鐘鼓金石絲竹旣鑄律管王武子武帝問杜預晋明帝靑鳥子郭景純永嘉中巧藝第二十一彈棋始自魏宮內用妝奩戲典論常自敍曰顧長康好寫起人形愷之圖寫特妙王珣郗超超爲人多須珣狀短小阮籍遭母喪加性仁孝劉伶恆縱酒阮公鄰家婦往哭盡哀而去阮籍當葬母⟦{{SKchar2|32}}⟧言窮矣阮仲容步兵詣阮庭中阮步兵喪母㫄若無人若裴公之制弔阮渾長成竹林諸賢之凧雖高阮仲容旣發定將去阮宣子常步行脩性簡仕山季倫蔆茨覆水張季鷹獨不爲身後名耶溫公喜慢語溫發口鄙穢王劉初尙辭然已無歸意桓宣武少家貧略無慊吝倜儻不羈有異才桓車騎路經陽岐村王子猷見有𣰅㲪襄陽羅友爲人有記功從桓宣武平蜀至日乃往友字它仁不擇士庶又好伺人祠桓溫常責之溫雖以才學遇之溫爲席起別首且出門民始怖終漸甚爲吏吏所安張驎酒後周勁以吹簫樂喪王衞軍云王䉕已見王長史恭使司馬劉牢之討廞廞敗王戎弱冠與戎酬酢終日鍾士季精有才理有人說鍛者嵇康與呂安善安字中悌謝公神氣傲邁逆呼太傅安曰王子敬自會稽經吳不足齒人傖耳晉武帝上汝一桮酒頭責秦子羽或謇喫無宮商則當如許由子威廓然離欲不閒禮義今欲使吾爲忠也欲使吾爲信也而以蟣蝨同情而猶文采可觀拳局剪蹙王渾與婦倫字太冲荀鳴鶴陸士龍張令其語諸葛令王丞相諸葛恢王公與朝士所以爲寶耳許文思取杭上新衣褚季野僕又茸之以蠶室張吳興張應聲答曰庾園郝隆爲桓公南蠻參軍罰酒三升袁羊嘗詣劉恢唐詩曰郗重熙郗曇王脩已見王子猷詣謝萬林公意甚惡郗司空拜北府以愛僧爲評也王文度說字上有一一字劉遵祖庾公甚忻然二郗奉道唯讀佛經營治寺廟而已矣范榮期何必勞神苦形所解數千牛祖廣行恆縮頭父台之仕光禄大夫輕詆二十六庾元規鍾離舂者折腰出胷庾公權重此爲金火相樂金陵本治王丞相輕蔡公蔡邕孫也吾昔與安期千里高柔在東淸婉辛切簡文與許玄度諸人紛葩謝萬壽春敗後故王嘉萬也庾道季甚不以爲好毛物牡牝之不知魏武行役軍皆渴魏武常言王大將軍旣爲逆居店賣食王右軍年減十歲乃剔吐孰眠方意右軍未起陶公陶又自要起同坐坐定溫公喪婦左司馬都督上前鋒諸軍事王文度弟阿智那得至今末有婚處䖍當以護軍起之故來迎之諸葛玄詣檻車與別桓公入蜀巫峽長猿鳴鄧竟陵因免遐官貿甑何儋殷仲文遂伏誅衞江州非弘範也郗公大聚斂卓犖而不羈王君夫有牛相牛經曰牛經出甯戚傳𩀱筋白尾骨屬頸其亦有陰虹也疎肋難齡齠王武子齊與從兄恬不平石崇毎與王敦史紀曰王令多矜咳王大王恭初桓石民爲荆州鎭上時上朋少時袁悅王粲聞其說孝武甚親敬王國寶王雅尤梅第三十三魏文帝我黃須兒可用也陸平原河橋敗劉琨抗行淵勒王大將軍視近日之言王導溫嶠胙安得長溫公初受其令入坐議庾公欲起周子南大丈夫乃爲庾元規所賣阮思曠奉大法必當蒙祐豈可以言神明之智者哉謝太傅於東船行或遲或速桓車騎在上明政獵元皇截一賀頭是誰蔡司徒渡江皆入足二螯讀爾雅不孰也謝虎子尙書襃第二子王大喪後而夜開閣魏甄后熙出在幽州見甄怖遂納之有玉荀奉倩粲不明於是力顧賈公閣後妻郭氏知后無子甚憂愛王丞相雷有寵生恬洽劉璵令作阬阬畢遊權貴之間王大將軍執司馬愍王相州剌史乃馳檄諸郡丞赴義應鎭南所謂入質之士襃與相景共免之王孝伯孰視首曰遺左將軍謝琰⟦{{SKchar|3129}}⟧玄將纂⟦{{SKchar|2989}}⟧沖後娶穎川庾蔑世說新語下卷下傳是樓宋槧本是刋於湘中者有江原張縯跋一篇舊爲南園俞氏藏書有耕雲俞彥春跋上粘王履約還書簡帖書法極古雅紙墨氣亦絕佳未知放翁所刋原本視此何如也吾友蔣篁亭並有對校本考正尤多四月雨牕校畢時館南城王氏淸蔭堂之左廂巖識二月得此本於玉峯書肆閏月從黃蕘圃假得沈寳硯校本用朱筆過校凡七日長洲吳嘉泰春生甫志于露凝書屋世說新語著錄家以明嘉靖中袁氏嘉趣堂本爲最善涵芬樓得一校本蓋沈寶硯以傳是樓宋本校袁本而嘉慶甲戌吳春生過錄者也袁本有戊申新定郡守陸遊跋則重開放翁本也傳是本沈跋云以刊於湘中有江原張縯跋兩本同出於宋玩其字句均以傳是本爲長袁刻遇宋諱多闕筆於明人翻刻本已爲謹嚴而不免貽誤是知書以舊本爲佳一經重刻遂不可恃錄其校語綴於卷末以爲讀是書者之助焉庚申十月無錫孫毓修識
```

---

## Mechanical-validation limitation

Exact/prefix/suffix matches and sequence ratios are evidence for review, not semantic proof. Page markers, annotation templates, glyph placeholders, one-character shifts, and entry-boundary differences can all produce a non-exact alignment. No corpus source or manifest was changed.
