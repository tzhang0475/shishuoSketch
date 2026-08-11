# Shishuo Xinyu proposed-boundary anomaly audit

This is a read-only Phase 1 audit of the proposed entry-boundary manifests. It does not generate final entry Markdown, perform entity/relationship extraction, or alter traditional text, punctuation, page markers, annotations, manifests, or chapter sources.

The existing `boundary-review-report.md`, `manual-review.md`, all chapter sources, all manifests, and the golden 雅量第六 segmentation remain traceable. Findings below are proposed fixes only; none is applied automatically.

## Proposed fixes (not applied)

This section is a review queue only. Existing manifests, chapter sources, `boundary-review-report.md`, `manual-review.md`, and the golden 雅量第六 outputs were not modified. No new entry Markdown was generated.

| classification | boundary or guide exception | proposed action |
| --- | --- | --- |
| boundary_shift | 18-qiyi-010 | Remove the proposed boundary; the `病篤...` text remains with the preceding 孟萬年 / 少孤 entry unless human evidence establishes another boundary. |
| boundary_shift | 18-qiyi-015 | Shift the proposed start one source character backward to the surviving `郄尚書...` beginning. Do not apply automatically. |
| boundary_shift | 25-paidiao-019 | Shift the proposed start one source character forward from `人` to the surviving `于寳...` beginning; keep `人` with the preceding entry. |
| source_gap | 19-xianyuan-005 | Do not invent the absent opening. Require a second textual witness; retain the surviving continuation as unresolved evidence. |
| source_gap | 05/14, 08/84–85, 18/2, 18/11, 19/5 | Do not synthesize missing guide entries or text. Use the page-marker/context evidence below to request a second witness. |

The classifications are deliberately separate: `boundary_shift` identifies a proposed start at the wrong surviving character; `source_gap` identifies text whose expected opening is absent; `reference_mismatch` identifies ordinal drift caused by omitted guide entries; `genuine_ambiguity` is a remaining below-high-confidence proposal without a deterministic shift signal.

## Confirmed boundary anomalies

The following findings are source-position anomalies, not entity or historical interpretation.

### 18-qiyi-010 — boundary_shift

- chapter: `18-qiyi` (棲逸第十八)
- manifest: `content/curated/shishuo/boundaries/18-qiyi.yaml`
- source: `content/processed/shishuo/chapters/chapter-18.md`
- confidence: `medium`; review_status: `auto`
- source normalized line: `1538`; source line: `1481`; page marker: `<pb:KR3l0002_SBCK_002-17a>`
- structural-guide alignment ordinal: `12`
**exact proposed opening anchor**
~~~text
病篤狼狽至都時賢見之者莫
~~~

**verbatim source immediately before the proposed boundary**
~~~text
也終)
孟萬年及弟少孤居武昌陽新縣萬年遊宦有盛名
當世少孤未嘗出京邑人士思欲見之乃遣信報少
孤云兄
~~~

**verbatim source immediately after the proposed boundary**
~~~text
病篤狼狽至都時賢見之者莫不嗟重因相
<!-- kanripo-page source-line=1483: <pb:KR3l0002_SBCK_002-17b> -->
<!-- kanripo-page source-line=1484: <pb:KR3l0002_SBCK_002-17b> -->
(廣陵侯仕至大司農/逯以武勇顯有功封)謝太傅曰卿兄弟志業何其太
殊戴曰下官不堪其憂家弟不改其樂
~~~

**audit reason**
- The proposed anchor begins inside the surviving 孟萬年 / 少孤 text. The preceding entry continues through the exact source sequence before this anchor; this is not an independent opening supported by the witness.
- The proposed opening is a verbatim continuation found inside the preceding structural-reference entry, rather than a new opening.
- The surviving-source alignment maps this proposed ordinal to structural-guide ordinal 12, not 10; this is a guide-count mismatch, not a source rewrite.
- **proposed action (not applied):** Remove this proposed boundary from the eventual reviewed segmentation and retain the text with the preceding entry; no source text is to be invented or moved during this audit. Do not treat this continuation as a new entry boundary without human evidence; review removal of the proposed boundary.

### 18-qiyi-015 — boundary_shift

- chapter: `18-qiyi` (棲逸第十八)
- manifest: `content/curated/shishuo/boundaries/18-qiyi.yaml`
- source: `content/processed/shishuo/chapters/chapter-18.md`
- confidence: `medium`; review_status: `auto`
- source normalized line: `1556`; source line: `1499`; page marker: `<pb:KR3l0002_SBCK_002-18a>`
- structural-guide alignment ordinal: `17`
**exact proposed opening anchor**
~~~text
尚書與謝居士善常稱謝慶緒
~~~

**verbatim source immediately before the proposed boundary**
~~~text
亦辦百萬資傳隐事
差互故不果遺(小字/約瓊)
許掾好遊山水而體便登陟時人云許非徒有勝情
實有濟勝之具
郄
~~~

**verbatim source immediately after the proposed boundary**
~~~text
尚書與謝居士善常稱謝慶緒識見雖不絶人可
以累心處都盡(曰謝敷字慶緒㑹稽人崇信釋氏初/尚書郄恢也别見檀道鸞續晉陽秋)
(納不倦以母老還
~~~

**audit reason**
- The proposed anchor begins one source character late. The surviving source has 郄 immediately before 尚書, so the boundary omits the first character of the entry.
- The source at the proposed position matches the structural opening after its first character, indicating a one-character late start.
- The surviving-source alignment maps this proposed ordinal to structural-guide ordinal 17, not 15; this is a guide-count mismatch, not a source rewrite.
- **proposed action (not applied):** Move the start one Han character backward to the exact source beginning '郄尚書與謝居士善常稱謝慶緒識見雖不'; do not modernize 郄 to 郗. Review a one-character backward shift to '郄尚書與謝居士善常稱謝慶緒識見雖'; do not apply automatically.

### 25-paidiao-019 — boundary_shift

- chapter: `25-paidiao` (排調第二十五)
- manifest: `content/curated/shishuo/boundaries/25-paidiao.yaml`
- source: `content/processed/shishuo/chapters/chapter-25.md`
- confidence: `low`; review_status: `auto`
- source normalized line: `2439`; source line: `2382`; page marker: `<pb:KR3l0002_SBCK_002-60a>`
- structural-guide alignment ordinal: `19`
**exact proposed opening anchor**
~~~text
人
于寳向劉真長(奮武將軍父瑩丹陽丞寳少以博學/中興書曰寳字令升新蔡人祖正吳)
(散騎常侍/才器著稱歷)叙其&KR0679;神記(寳母至妒葬寳父時因推/孔氏志怪曰寳父有嬖人)
(漸有氣息輿還家終日而蘇說寳父常致飲食與之/著藏中經十年而母䘮開墓其婢伏棺上就視猶煖)
(數年後方卒寳因作&KR0679;神記中云有所感起是也/接寢恩情如生家中吉凶輙語之校之悉驗平復)劉
~~~

**verbatim source immediately before the proposed boundary**
~~~text
如捲角牸有盤辟之好(王也/以戲)
<!-- kanripo-page source-line=2381: <pb:KR3l0002_SBCK_002-60a> -->
王丞相枕周伯仁䣛指其腹曰卿此中何所有荅曰
此中空洞無物然容卿輩數百
~~~

**verbatim source immediately after the proposed boundary**
~~~text
人
于寳向劉真長(奮武將軍父瑩丹陽丞寳少以博學/中興書曰寳字令升新蔡人祖正吳)
(散騎常侍/才器著稱歷)叙其&KR0679;神記(寳母至妒葬寳父時因推/孔氏
~~~

**audit reason**
- The proposed anchor starts with the final character 人 of the preceding source entry; the next surviving entry begins at 于寳.
- **proposed action (not applied):** Move the start one Han character forward to the exact surviving source beginning '于寳向劉真長叙其神記劉曰卿可謂鬼'; do not alter source text.

The all-manifest adjacent-shift and continuation scan found no additional `boundary_shift` signal beyond 18-qiyi-010, 18-qiyi-015, and 25-paidiao-019. This is a deterministic anomaly signal, not a semantic proof; the remaining medium/low proposals stay in human review.

## Structural-reference exceptions and ordinal mismatches

The guide is authoritative for expected order/count diagnostics, while the normalized witness remains authoritative for emitted source text. A proposed ordinal after a source gap is therefore not the same thing as the missing guide ordinal.

| chapter | expected guide exception(s) | surviving proposed mapping around the exception | classification |
| --- | --- | --- | --- |
| 05-fangzheng | #14 | proposed 014–065 -> guide 015–066 (delta +1) | source_gap + reference_mismatch |
| 08-shangyu | #84, #85 | proposed 084–154 -> guide 086–156 (delta +2) | source_gap + reference_mismatch |
| 18-qiyi | #2, #11 | proposed 002–009 -> guide 003–010 (delta +1); proposed 010–015 -> guide 012–017 (delta +2) | source_gap + reference_mismatch |
| 19-xianyuan | #5 | proposed 005–031 -> guide 006–032 (delta +1) | source_gap + reference_mismatch |

The six missing guide ordinals are not present as source openings: 05/#14; 08/#84 and #85; 18/#2 and #11; 19/#5. The mismatch ranges shown in the chapter summary are the downstream ordinal effects, not automatic repairs.

## Kanripo page-marker scan around structural exceptions

Marker continuity is reported separately from text continuity. A skipped marker does not prove that a page of text is absent, and a duplicated marker does not prove duplicate text.

### 05-fangzheng (方正第五)

#### expected guide ordinal #14

- marker sequence in local window: <pb:KR3l0002_SBCK_002-7b> (source-line 131; page comment) → <pb:KR3l0002_SBCK_002-8a> (source-line 142; page comment) → <pb:KR3l0002_SBCK_002-9a> (source-line 143; page comment) → <pb:KR3l0002_SBCK_002-9b> (source-line 154; page comment) → <pb:KR3l0002_SBCK_002-10a> (source-line 165; page comment) → <pb:KR3l0002_SBCK_002-10b> (source-line 176; page comment)
- marker finding: skipped/discontinuous folio marker: <pb:KR3l0002_SBCK_002-8a> -> <pb:KR3l0002_SBCK_002-9a>; expected <pb:KR3l0002_SBCK_002-8b>
- likely missing page/leaf if determinable: <pb:KR3l0002_SBCK_002-8b>
- second textual witness required: yes

### 08-shangyu (賞譽第八)

#### expected guide ordinal #84

- marker sequence in local window: <pb:KR3l0002_SBCK_003-10a> (source-line 207; page comment) → <pb:KR3l0002_SBCK_003-10b> (source-line 218; page comment) → <pb:KR3l0002_SBCK_003-10b> (source-line 219; page comment) → <pb:KR3l0002_SBCK_003-11a> (source-line 230; page comment)
- marker finding: duplicated marker <pb:KR3l0002_SBCK_003-10b> at source lines 218 and 219
- likely missing page/leaf if determinable: No missing folio/leaf is determinable from the local marker sequence.
- second textual witness required: yes

#### expected guide ordinal #85

- marker sequence in local window: <pb:KR3l0002_SBCK_003-10a> (source-line 207; page comment) → <pb:KR3l0002_SBCK_003-10b> (source-line 218; page comment) → <pb:KR3l0002_SBCK_003-10b> (source-line 219; page comment) → <pb:KR3l0002_SBCK_003-11a> (source-line 230; page comment)
- marker finding: duplicated marker <pb:KR3l0002_SBCK_003-10b> at source lines 218 and 219
- likely missing page/leaf if determinable: No missing folio/leaf is determinable from the local marker sequence.
- second textual witness required: yes

### 18-qiyi (棲逸第十八)

#### expected guide ordinal #2

- marker sequence in local window: <pb:KR3l0002_SBCK_002-13b> (source-line 1421; FILE segment start provenance) → <pb:KR3l0002_SBCK_002-14a> (source-line 1427; page comment) → <pb:KR3l0002_SBCK_002-15a> (source-line 1428; page comment) → <pb:KR3l0002_SBCK_002-15b> (source-line 1439; page comment) → <pb:KR3l0002_SBCK_002-16a> (source-line 1450; page comment) → <pb:KR3l0002_SBCK_002-16b> (source-line 1461; page comment)
- marker finding: skipped/discontinuous folio marker: <pb:KR3l0002_SBCK_002-14a> -> <pb:KR3l0002_SBCK_002-15a>; expected <pb:KR3l0002_SBCK_002-14b>
- likely missing page/leaf if determinable: <pb:KR3l0002_SBCK_002-14b>
- second textual witness required: yes

#### expected guide ordinal #11

- marker sequence in local window: <pb:KR3l0002_SBCK_002-17a> (source-line 1472; page comment) → <pb:KR3l0002_SBCK_002-17b> (source-line 1483; page comment) → <pb:KR3l0002_SBCK_002-17b> (source-line 1484; page comment) → <pb:KR3l0002_SBCK_002-18a> (source-line 1495; page comment)
- marker finding: duplicated marker <pb:KR3l0002_SBCK_002-17b> at source lines 1483 and 1484
- likely missing page/leaf if determinable: No missing folio/leaf is determinable from the local marker sequence.
- second textual witness required: yes

### 19-xianyuan (賢媛第十九)

#### expected guide ordinal #5

- marker sequence in local window: <pb:KR3l0002_SBCK_002-19b> (source-line 1528; page comment) → <pb:KR3l0002_SBCK_002-20a> (source-line 1539; page comment) → <pb:KR3l0002_SBCK_002-21a> (source-line 1540; page comment) → <pb:KR3l0002_SBCK_002-21b> (source-line 1551; page comment) → <pb:KR3l0002_SBCK_002-22a> (source-line 1562; page comment) → <pb:KR3l0002_SBCK_002-22b> (source-line 1573; page comment)
- marker finding: skipped/discontinuous folio marker: <pb:KR3l0002_SBCK_002-20a> -> <pb:KR3l0002_SBCK_002-21a>; expected <pb:KR3l0002_SBCK_002-20b>
- likely missing page/leaf if determinable: <pb:KR3l0002_SBCK_002-20b>
- second textual witness required: yes

The local windows show: 05/#14 has 002-8a → 002-9a (the expected 002-8b marker is skipped); 08/#84–85 has duplicated 003-10b comments at source lines 218 and 219 but no local folio skip; 18/#2 has 002-14a → 002-15a (002-14b skipped); 18/#11 has duplicated 002-17b comments at source lines 1483 and 1484; and 19/#5 has 002-20a → 002-21a (002-20b skipped).

## Source-gap evidence (verbatim context; no invented repair)

Each context below is copied as a contiguous slice from the indicated normalized chapter source. It may contain line breaks, parenthetical annotation text, or Kanripo page-marker comments exactly as present in that source. The guide opening itself is not substituted into the witness.

### 05-fangzheng — expected reference ordinal #14

- chapter: `05-fangzheng` (方正第五)
- expected reference ordinal: `14`
- guide diagnostic: reference opening is absent from normalized main text
- preceding surviving structural ordinal: `13`
- following surviving structural ordinal: `15`
- likely missing page/leaf if determinable: <pb:KR3l0002_SBCK_002-8b>
- whether a second textual witness is required: **yes**

**preceding surviving text**
~~~text
所許楊濟既名氏雄俊不堪不坐而去
(也有才識累遷太子太保與駿同誅/八王故事曰濟字文通弘農人楊駿弟)須臾和長輿
來問楊右衛何在客曰向來不坐而去長輿曰必大
夏門下盤馬往大夏門果大閲騎長輿抱內車共載
歸坐如初
杜預拜鎮南將軍朝士悉至皆在連榻坐(朝方鎮還/語林曰中)
<!-- kanripo-page source-line=142: <pb:KR3l0002_SBCK_002-8a> -->
<!-- kanripo-page source-line=143: <pb:KR3l0002_SBCK_002-9a> -->
(坐乃使監令異車自此始也/而荀朂爲監嶠意强抗專車而)

~~~

**following surviving text**
~~~text
山公大兒著短帢車中倚武帝欲見之山公不敢辭
問兒兒不肯行時論乃云勝山公(字伯倫司徒濤長/晉諸公賛曰山該)
(仕至左衛將軍/子也雅有噐識)
向雄爲河內主簿有公事不及雄而太守劉淮横怒
遂與杖遣之雄後爲黄門郎劉爲侍中初不交言武
帝聞之敕雄復君臣之好雄不得巳詣劉再拜曰向
受詔而來而君臣之義絶何如於是即去武帝聞尚
不和乃怒問雄曰我令卿復君臣之好何以猶絶(晉/漢)
(門郎護軍將軍按王隱孫盛不與故君相聞議曰昔
~~~

**relevant Kanripo page markers**
- <pb:KR3l0002_SBCK_002-7b> (source-line 131; page comment)
- <pb:KR3l0002_SBCK_002-8a> (source-line 142; page comment)
- <pb:KR3l0002_SBCK_002-9a> (source-line 143; page comment)
- <pb:KR3l0002_SBCK_002-9b> (source-line 154; page comment)
- <pb:KR3l0002_SBCK_002-10a> (source-line 165; page comment)
- <pb:KR3l0002_SBCK_002-10b> (source-line 176; page comment)
- marker audit: skipped/discontinuous folio marker: <pb:KR3l0002_SBCK_002-8a> -> <pb:KR3l0002_SBCK_002-9a>; expected <pb:KR3l0002_SBCK_002-8b>

No source text is supplied for the gap. The next phase must obtain and compare a second textual witness before deciding whether the guide entry is absent from this witness, represented elsewhere, or affected by a source-file omission.

### 08-shangyu — expected reference ordinal #84

- chapter: `08-shangyu` (賞譽第八)
- expected reference ordinal: `84`
- guide diagnostic: reference opening is absent from normalized main text
- preceding surviving structural ordinal: `83`
- following surviving structural ordinal: `86`
- likely missing page/leaf if determinable: No missing folio/leaf is determinable from the local marker sequence.
- whether a second textual witness is required: **yes**

**preceding surviving text**
~~~text
孫綽與庾)
(數十年間也/敦可人之目)
殷中軍道王右軍云逸少清貴人吾於之甚至一時
無所後(有風氣不類常流也/文章志曰羲之高爽)
王仲祖稱殷淵源非以長勝人處長亦勝人(曰浩善/晉陽秋)
(接物也/以通和)
王司州與殷中軍語嘆云巳之府奥蚤已傾冩而見
殷陳勢浩汗衆源未可得測(辯玄致當時名流皆爲/徐廣晉紀曰浩清言妙)
(譽/其美)
王長史謂林公
~~~

**following surviving text**
~~~text
真長可謂金玉滿堂林公曰金玉滿
<!-- kanripo-page source-line=218: <pb:KR3l0002_SBCK_003-10b> -->
<!-- kanripo-page source-line=219: <pb:KR3l0002_SBCK_003-10b> -->
淵源真可王曰卿故墮其雲霧中(理談論精微長於/中興書曰浩能言)
(者皆宗歸之/老易故風流)
劉尹每稱王長史云性至通而自然有節(濛之交物/濛别傳曰)
(不敬而愛之然少孤事諸母甚謹篤義穆族不脩小/虛巳納善恕而後行希見其喜愠之色凡與一面莫)
(貧見稱/潔以清)
王右軍道謝萬石在林澤中爲自遒上歎林公器朗
神儁(心獨往風期高亮/支遁别傳曰遁任)道祖士少風領毛骨恐没世
不復見如此人道劉真長標雲
~~~

**relevant Kanripo page markers**
- <pb:KR3l0002_SBCK_003-10a> (source-line 207; page comment)
- <pb:KR3l0002_SBCK_003-10b> (source-line 218; page comment)
- <pb:KR3l0002_SBCK_003-10b> (source-line 219; page comment)
- <pb:KR3l0002_SBCK_003-11a> (source-line 230; page comment)
- marker audit: duplicated marker <pb:KR3l0002_SBCK_003-10b> at source lines 218 and 219

No source text is supplied for the gap. The next phase must obtain and compare a second textual witness before deciding whether the guide entry is absent from this witness, represented elsewhere, or affected by a source-file omission.

### 08-shangyu — expected reference ordinal #85

- chapter: `08-shangyu` (賞譽第八)
- expected reference ordinal: `85`
- guide diagnostic: reference opening is absent from normalized main text
- preceding surviving structural ordinal: `83`
- following surviving structural ordinal: `86`
- likely missing page/leaf if determinable: No missing folio/leaf is determinable from the local marker sequence.
- whether a second textual witness is required: **yes**

**preceding surviving text**
~~~text
孫綽與庾)
(數十年間也/敦可人之目)
殷中軍道王右軍云逸少清貴人吾於之甚至一時
無所後(有風氣不類常流也/文章志曰羲之高爽)
王仲祖稱殷淵源非以長勝人處長亦勝人(曰浩善/晉陽秋)
(接物也/以通和)
王司州與殷中軍語嘆云巳之府奥蚤已傾冩而見
殷陳勢浩汗衆源未可得測(辯玄致當時名流皆爲/徐廣晉紀曰浩清言妙)
(譽/其美)
王長史謂林公
~~~

**following surviving text**
~~~text
真長可謂金玉滿堂林公曰金玉滿
<!-- kanripo-page source-line=218: <pb:KR3l0002_SBCK_003-10b> -->
<!-- kanripo-page source-line=219: <pb:KR3l0002_SBCK_003-10b> -->
淵源真可王曰卿故墮其雲霧中(理談論精微長於/中興書曰浩能言)
(者皆宗歸之/老易故風流)
劉尹每稱王長史云性至通而自然有節(濛之交物/濛别傳曰)
(不敬而愛之然少孤事諸母甚謹篤義穆族不脩小/虛巳納善恕而後行希見其喜愠之色凡與一面莫)
(貧見稱/潔以清)
王右軍道謝萬石在林澤中爲自遒上歎林公器朗
神儁(心獨往風期高亮/支遁别傳曰遁任)道祖士少風領毛骨恐没世
不復見如此人道劉真長標雲
~~~

**relevant Kanripo page markers**
- <pb:KR3l0002_SBCK_003-10a> (source-line 207; page comment)
- <pb:KR3l0002_SBCK_003-10b> (source-line 218; page comment)
- <pb:KR3l0002_SBCK_003-10b> (source-line 219; page comment)
- <pb:KR3l0002_SBCK_003-11a> (source-line 230; page comment)
- marker audit: duplicated marker <pb:KR3l0002_SBCK_003-10b> at source lines 218 and 219

No source text is supplied for the gap. The next phase must obtain and compare a second textual witness before deciding whether the guide entry is absent from this witness, represented elsewhere, or affected by a source-file omission.

### 18-qiyi — expected reference ordinal #2

- chapter: `18-qiyi` (棲逸第十八)
- expected reference ordinal: `2`
- guide diagnostic: reference opening is absent from normalized main text
- preceding surviving structural ordinal: `1`
- following surviving structural ordinal: `3`
- likely missing page/leaf if determinable: <pb:KR3l0002_SBCK_002-14b>
- whether a second textual witness is required: **yes**

**preceding surviving text**
~~~text
良妙康每)
(而不用其才果然在於用才故用光在乎得薪所以/乎生而有光而不用其光果然在於用光人生有才)
(難乎免於今之世矣子無多求康不能用及遭吕安/保其曜用才在乎識物所以全其年今子才多識寡)
(曰孫登即阮籍所見者也嵇康執弟子禮而師焉魏/事在獄為詩自責云昔慚下惠今愧孫登王隐晉書)
(賤並没故登或黙也/晉去就易生嫌疑貴)

~~~

**following surviving text**
~~~text
山公將去選曹欲舉嵇康康與書告絶(巨源為吏部/康别傳曰山)
(不以一官遇已情邪亦欲標不屈之節以杜舉者之/郎遷散騎常侍舉康康辭之并與山絶豈不識山之)
<!-- kanripo-page source-line=1439: <pb:KR3l0002_SBCK_002-15b> -->
(而非薄湯武大將軍聞而惡之/口耳乃荅濤書自說不堪流俗)
李廞是茂曽弟五子清貞有逺操而少羸病不肯婚
宦居在臨海住兄侍中墓下既有髙名王丞相欲招
禮之故辟為府掾廞得牋命笑曰茂弘乃復以一爵
假人(史父重平陽太守世有名望廞好學善草隷與/文字志曰廞字宗子江夏鍾
~~~

**relevant Kanripo page markers**
- <pb:KR3l0002_SBCK_002-13b> (source-line 1421; FILE segment start provenance)
- <pb:KR3l0002_SBCK_002-14a> (source-line 1427; page comment)
- <pb:KR3l0002_SBCK_002-15a> (source-line 1428; page comment)
- <pb:KR3l0002_SBCK_002-15b> (source-line 1439; page comment)
- <pb:KR3l0002_SBCK_002-16a> (source-line 1450; page comment)
- <pb:KR3l0002_SBCK_002-16b> (source-line 1461; page comment)
- marker audit: skipped/discontinuous folio marker: <pb:KR3l0002_SBCK_002-14a> -> <pb:KR3l0002_SBCK_002-15a>; expected <pb:KR3l0002_SBCK_002-14b>

No source text is supplied for the gap. The next phase must obtain and compare a second textual witness before deciding whether the guide entry is absent from this witness, represented elsewhere, or affected by a source-file omission.

### 18-qiyi — expected reference ordinal #11

- chapter: `18-qiyi` (棲逸第十八)
- expected reference ordinal: `11`
- guide diagnostic: reference opening is absent from normalized main text
- preceding surviving structural ordinal: `10`
- following surviving structural ordinal: `12`
- likely missing page/leaf if determinable: No missing folio/leaf is determinable from the local marker sequence.
- whether a second textual witness is required: **yes**

**preceding surviving text**
~~~text
秋曰翟湯字道淵南陽人漢方)
(初庾亮臨江州聞翟湯之風束帶躡屐而詣焉亮禮/一無所受值亂多宼聞湯名德皆不敢犯尋陽記曰)
(薦之徴國子博士不赴主簿張玄曰此君卧龍不可/甚恭湯曰使君直敬其枯木朽株耳亮稱其能言表)
(于家/動也終)
孟萬年及弟少孤居武昌陽新縣萬年遊宦有盛名
當世少孤未嘗出京邑人士思欲見之乃遣信報少
孤云兄
~~~

**following surviving text**
~~~text
病篤狼狽至都時賢見之者莫不嗟重因相
<!-- kanripo-page source-line=1483: <pb:KR3l0002_SBCK_002-17b> -->
<!-- kanripo-page source-line=1484: <pb:KR3l0002_SBCK_002-17b> -->
(廣陵侯仕至大司農/逯以武勇顯有功封)謝太傅曰卿兄弟志業何其太
殊戴曰下官不堪其憂家弟不改其樂
許玄度隱在永興南幽穴中每致四方諸侯之遺或
謂許曰嘗聞箕山人似不爾耳許曰筐篚苞苴故當
輕於天下之寳耳(葦或以茅此言許由尚致堯帝之/鄭玄禮記注云苞苴裹肉也或以)
(豈非輕邪/讓筐篚之遺)
范宣未嘗入公門韓康伯與同載遂誘俱入郡范便
於車後趨下(家于豫章以清潔自立/續晉陽秋
~~~

**relevant Kanripo page markers**
- <pb:KR3l0002_SBCK_002-17a> (source-line 1472; page comment)
- <pb:KR3l0002_SBCK_002-17b> (source-line 1483; page comment)
- <pb:KR3l0002_SBCK_002-17b> (source-line 1484; page comment)
- <pb:KR3l0002_SBCK_002-18a> (source-line 1495; page comment)
- marker audit: duplicated marker <pb:KR3l0002_SBCK_002-17b> at source lines 1483 and 1484

No source text is supplied for the gap. The next phase must obtain and compare a second textual witness before deciding whether the guide entry is absent from this witness, represented elsewhere, or affected by a source-file omission.

### 19-xianyuan — expected reference ordinal #5

- chapter: `19-xianyuan` (賢媛第十九)
- expected reference ordinal: `5`
- guide diagnostic: reference opening is absent from normalized main text
- preceding surviving structural ordinal: `4`
- following surviving structural ordinal: `6`
- likely missing page/leaf if determinable: <pb:KR3l0002_SBCK_002-20b>
- whether a second textual witness is required: **yes**

**preceding surviving text**
~~~text
曰狗䑕
不食汝餘死故應爾至山陵亦竟不臨(卞皇后琅邪/魏書曰武宣)
(日父敬侯怪之以問卜者王越越曰此吉祥也年二/開陽人以漢延熹三年生齊郡白亭有黄氣满室移)
(不尚華麗有母儀徳行/十太祖納於譙性約儉)
<!-- kanripo-page source-line=1539: <pb:KR3l0002_SBCK_002-20a> -->
<!-- kanripo-page source-line=1540: <pb:KR3l0002_SBCK_002-21a> -->
(誅/所)婦曰無憂桓必勸入桓果語許云阮家既嫁醜女
與卿故當有意卿宜察之許便回入内既見婦即欲
出婦料其此出無復入理便捉𥚑
~~~

**following surviving text**
~~~text
停之許因謂曰婦
有四德卿有其幾(婦德婦言婦容婦功鄭注曰德謂/周禮九嬪掌婦學之法以教九御)
(謂婉娩功謂絲枲/貞順言謂辭令容)婦曰新婦所乏唯容爾然士有百
行君有幾許云皆僃婦曰夫百行以徳為首君好色
不好德何謂皆僃允有慚色遂相敬重
許允為吏部郎多用其鄉里魏明帝遣虎賁收之其
婦出誡允曰明主可以理奪難以情求既至帝覈問
之允對曰舉爾所知臣之郷人臣所知也陛下檢校
<!-- kanripo-page source-line=1551: <pb:KR3l0002_SBCK_002-21b> -->
為稱職與不若不稱職臣受其罪既檢校皆官
~~~

**relevant Kanripo page markers**
- <pb:KR3l0002_SBCK_002-19b> (source-line 1528; page comment)
- <pb:KR3l0002_SBCK_002-20a> (source-line 1539; page comment)
- <pb:KR3l0002_SBCK_002-21a> (source-line 1540; page comment)
- <pb:KR3l0002_SBCK_002-21b> (source-line 1551; page comment)
- <pb:KR3l0002_SBCK_002-22a> (source-line 1562; page comment)
- <pb:KR3l0002_SBCK_002-22b> (source-line 1573; page comment)
- marker audit: skipped/discontinuous folio marker: <pb:KR3l0002_SBCK_002-20a> -> <pb:KR3l0002_SBCK_002-21a>; expected <pb:KR3l0002_SBCK_002-20b>

No source text is supplied for the gap. The next phase must obtain and compare a second textual witness before deciding whether the guide entry is absent from this witness, represented elsewhere, or affected by a source-file omission.

## Remaining genuine ambiguity

After removing the three confirmed boundary shifts and the one partial source-gap boundary from the below-high proposals, the audit classifies the remaining 238 medium-confidence proposals as `genuine_ambiguity`. This is a review classification, not an automatic acceptance. The two low-confidence proposals are the known 19/#5 source gap and 25/#19 boundary shift.

The complete medium/low context queue remains in `content/curated/shishuo/boundaries/manual-review.md`; no confidence or review status was changed here.

Focus chapters with unresolved genuine-ambiguity proposals:

- `05-fangzheng`: 5 — 05-fangzheng-004, 05-fangzheng-008, 05-fangzheng-009, 05-fangzheng-012, 05-fangzheng-013
- `08-shangyu`: 20 — 08-shangyu-005, 08-shangyu-006, 08-shangyu-016, 08-shangyu-019, 08-shangyu-023, 08-shangyu-028, 08-shangyu-032, 08-shangyu-036, 08-shangyu-047, 08-shangyu-051, 08-shangyu-053, 08-shangyu-054, 08-shangyu-060, 08-shangyu-062, 08-shangyu-065, 08-shangyu-066, 08-shangyu-072, 08-shangyu-073, 08-shangyu-079, 08-shangyu-083
- `18-qiyi`: 0 — none
- `19-xianyuan`: 1 — 19-xianyuan-002
- `25-paidiao`: 21 — 25-paidiao-003, 25-paidiao-006, 25-paidiao-016, 25-paidiao-020, 25-paidiao-022, 25-paidiao-023, 25-paidiao-025, 25-paidiao-029, 25-paidiao-034, 25-paidiao-036, 25-paidiao-037, 25-paidiao-039, 25-paidiao-044, 25-paidiao-046, 25-paidiao-049, 25-paidiao-050, 25-paidiao-051, 25-paidiao-053, 25-paidiao-057, 25-paidiao-058, 25-paidiao-064

## Corpus and chapter summary

Guide counts below are read from `content/shishuo.txt` during this audit; they are not hard-coded expectations.

| chapter | proposed | guide | high | medium | low | boundary shift | guide source gaps | reference-mismatch boundaries | genuine ambiguity | mechanical |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| 01-dexing (德行第一) | 47 | 47 | 38 | 9 | 0 | 0 | 0 | 0 | 9 | passed |
| 02-yanyu (言語第二) | 108 | 108 | 88 | 20 | 0 | 0 | 0 | 0 | 20 | passed |
| 03-zhengshi (政事第三) | 26 | 26 | 23 | 3 | 0 | 0 | 0 | 0 | 3 | passed |
| 04-wenxue (文學第四) | 104 | 104 | 83 | 21 | 0 | 0 | 0 | 0 | 21 | passed |
| 05-fangzheng (方正第五) | 65 | 66 | 52 | 13 | 0 | 0 | 1 | 52 | 5 | passed |
| 06-yaliang (雅量第六) | 42 | 42 | 42 | 0 | 0 | 0 | 0 | 0 | 0 | passed |
| 07-shijian (識鑒第七) | 28 | 28 | 25 | 3 | 0 | 0 | 0 | 0 | 3 | passed |
| 08-shangyu (賞譽第八) | 154 | 156 | 113 | 41 | 0 | 0 | 2 | 71 | 20 | passed |
| 09-pinzao (品藻第九) | 88 | 88 | 66 | 22 | 0 | 0 | 0 | 0 | 22 | passed |
| 10-guizhen (規箴第十) | 27 | 27 | 19 | 8 | 0 | 0 | 0 | 0 | 8 | passed |
| 11-jiewu (捷悟第十一) | 7 | 7 | 4 | 3 | 0 | 0 | 0 | 0 | 3 | passed |
| 12-suhui (夙惠第十二) | 7 | 7 | 6 | 1 | 0 | 0 | 0 | 0 | 1 | passed |
| 13-haoshuang (豪爽第十三) | 13 | 13 | 12 | 1 | 0 | 0 | 0 | 0 | 1 | passed |
| 14-rongzhi (容止第十四) | 39 | 39 | 37 | 2 | 0 | 0 | 0 | 0 | 2 | passed |
| 15-zixin (自新第十五) | 2 | 2 | 2 | 0 | 0 | 0 | 0 | 0 | 0 | passed |
| 16-qixian (企羡第十六) | 6 | 6 | 4 | 2 | 0 | 0 | 0 | 0 | 2 | passed |
| 17-shangshi (傷逝第十七) | 19 | 19 | 14 | 5 | 0 | 0 | 0 | 0 | 5 | passed |
| 18-qiyi (棲逸第十八) | 15 | 17 | 9 | 6 | 0 | 2 | 2 | 14 | 0 | passed |
| 19-xianyuan (賢媛第十九) | 31 | 32 | 24 | 6 | 1 | 0 | 1 | 27 | 1 | passed |
| 20-shujie (術解第二十) | 11 | 11 | 9 | 2 | 0 | 0 | 0 | 0 | 2 | passed |
| 21-qiaoyi (巧蓺第二十一) | 14 | 14 | 8 | 6 | 0 | 0 | 0 | 0 | 6 | passed |
| 22-chongli (寵禮第二十二) | 6 | 6 | 3 | 3 | 0 | 0 | 0 | 0 | 3 | passed |
| 23-rendan (任誕第二十三) | 54 | 54 | 42 | 12 | 0 | 0 | 0 | 0 | 12 | passed |
| 24-jianao (簡傲第二十四) | 17 | 17 | 13 | 4 | 0 | 0 | 0 | 0 | 4 | passed |
| 25-paidiao (排調第二十五) | 65 | 65 | 43 | 21 | 1 | 1 | 0 | 0 | 21 | passed |
| 26-qingdi (輕詆第二十六) | 33 | 33 | 26 | 7 | 0 | 0 | 0 | 0 | 7 | passed |
| 27-jiajue (假譎第二十七) | 14 | 14 | 11 | 3 | 0 | 0 | 0 | 0 | 3 | passed |
| 28-chumian (黜免第二十八) | 9 | 9 | 8 | 1 | 0 | 0 | 0 | 0 | 1 | passed |
| 29-jianshe (儉嗇第二十九) | 9 | 9 | 8 | 1 | 0 | 0 | 0 | 0 | 1 | passed |
| 30-taichi (汰侈第三十) | 12 | 12 | 7 | 5 | 0 | 0 | 0 | 0 | 5 | passed |
| 31-fenjuan (忿狷第三十一) | 8 | 8 | 7 | 1 | 0 | 0 | 0 | 0 | 1 | passed |
| 32-chanxian (讒險第三十二) | 4 | 4 | 3 | 1 | 0 | 0 | 0 | 0 | 1 | passed |
| 33-youhui (尤悔第三十三) | 17 | 17 | 14 | 3 | 0 | 0 | 0 | 0 | 3 | passed |
| 34-pilou (紕漏第三十四) | 8 | 8 | 6 | 2 | 0 | 0 | 0 | 0 | 2 | passed |
| 35-huoni (惑溺第三十五) | 7 | 7 | 6 | 1 | 0 | 0 | 0 | 0 | 1 | passed |
| 36-chouxi (仇隟第三十六) | 8 | 8 | 7 | 1 | 0 | 0 | 0 | 0 | 1 | passed |

The structural guide contains 1088 entries in the 35 non-Yaliang chapters, 42 entries in 雅量第六, and 1130 entries total.
The current manifests contain 1124 proposed boundaries: 1082 outside 雅量第六 and 42 in the golden chapter.

The six-guide-entry difference is the explicit source-gap set: 05/14, 08/84–85, 18/2, 18/11, and 19/5. It is not repaired or silently folded into a source boundary.

## Re-run mechanical validation

The audit re-ran the existing manifest checks for all 36 chapter manifests, including the reviewed 雅量第六 manifest. The checks were: anchors exactly once, unique anchors, continuous ordinals, no empty entries, page-marker traceability, parentheses balance, and source-provenance agreement.

| check | chapters passed | result |
| --- | ---: | --- |
| anchors exactly once | 36/36 | passed |
| unique anchors | 36/36 | passed |
| continuous ordinals | 36/36 | passed |
| no empty entries | 36/36 | passed |
| page markers traceable | 36/36 | passed |
| parentheses balanced | 36/36 | passed |
| source provenance agrees | 36/36 | passed |

Overall mechanical manifest validation: passed.

Mechanical validation does **not** prove semantic boundary correctness. In particular, all current manifests can pass exact-anchor/order/marker checks while a boundary still starts one character late, includes a preceding entry's final character, or begins inside a syntactic continuation. The confirmed findings above are why semantic human review remains required.
