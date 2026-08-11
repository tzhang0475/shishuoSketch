# Shishuo known-anomaly multi-witness comparison

This report is a read-only comparison layer. It does not modify raw or downloaded witnesses, normalized chapters, entries, manifests, or prior audit reports. The Kanripo/SBCK witness remains primary. Wikisource is a same-edition machine reference; Ling OCR is search-only and its PDF/page image is authoritative; 四庫 is external and was not bulk-scraped; the local TXT is structural reference only.

## Classification summary

| classification | cases |
|---|---:|
| `boundary_shift` | 3 |
| `kanripo_digitization_gap` | 6 |

## Cases

### 05-fangzheng-014 — `kanripo_digitization_gap` (high confidence)

- chapter: `05-fangzheng` (方正第五)
- expected ordinal: `14`
- recommended resolution: Retain the Kanripo source unchanged. Use the Wikisource same-edition page witness as missing-text evidence, then verify against Ling page images and/or 四庫本 before any future reviewed repair.
- missing-text supplier, if any: `shishuo-wikisource-sbck`

#### Kanripo/SBCK primary witness

- status: `structural_reference_opening_absent`
- proposed/opening reading: `山公大兒著短帢車中倚武帝`
- source location: `content/processed/shishuo/chapters/chapter-05.md`; normalized line `201`; page `<pb:KR3l0002_SBCK_002-9a>`

```text
坐而去長輿曰必大
夏門下盤馬往大夏門果大閲騎長輿抱內車共載
歸坐如初
杜預拜鎮南將軍朝士悉至皆在連榻坐(朝方鎮還/語林曰中)
<!-- kanripo-page source-line=142: <pb:KR3l0002_SBCK_002-8a> -->
<!-- kanripo-page source-line=143: <pb:KR3l0002_SBCK_002-9a> -->
(坐乃使監令異車自此始也/而荀朂爲監嶠意强抗專車而)
山公大兒著短帢車中倚武帝欲見之山公不敢辭
問兒兒不肯行時論乃云勝山公(字伯倫司徒濤長/晉諸公賛曰山該)
(仕至左衛將軍/子也雅有噐識)
向雄爲河內主簿有公事不及雄而太守劉淮横怒
遂與杖遣之雄後爲黄門郎劉爲侍中初不交言武
帝聞之敕雄復君臣之好雄不得巳詣劉再拜曰向
受詔而來而君臣之義絶何如於是即去武帝聞尚
不和乃怒問雄曰我令卿復君臣之好何以猶絶(晉/漢)
(門郎護軍將軍按王隱孫盛不與故君相聞議曰昔/春秋曰雄字茂伯河内人世語曰雄有節槩仕至黄)
<!-- kanripo-page source-line=154: <pb:KR3l0002_SBCK_002-9b> -->
(隨比送洛值天大熱郡送牛多暍死臺法甚重太守/在晉初河內温縣領校向雄送
```

#### Wikisource 四部叢刊 same-edition machine witness

- status: `located`; match type: `exact`
- page: `Page:Sibu Congkan0463-劉義慶-世説新語-3-2.djvu/15`
- page source: `https://zh.wikisource.org/wiki/Page%3ASibu%20Congkan0463-%E5%8A%89%E7%BE%A9%E6%85%B6-%E4%B8%96%E8%AA%AC%E6%96%B0%E8%AA%9E-3-2.djvu%2F15`

```text
下盤馬往大夏門果大閲騎長輿抱內車共載歸坐如初杜預拜鎮南將軍朝士悉至皆在連榻坐時亦有裴叔則羊穉舒後至曰杜元凱乃復連榻坐客不坐便去杜請裴追之羊去數里住馬既而俱還杜許晉武帝時荀朂爲中書監和嶠爲令故事監令由來共車嶠性雅正常疾朂謟䛕後公車來嶠便登正向前坐不復容朂朂方更覓車然得去監令各給車自此始山公大兒著短帢車中倚武帝欲見之山公不敢辭問兒兒不肯行時論乃云勝山公向雄爲河內主簿有公事不及雄而太守劉淮横怒遂與杖遣之雄後爲黄門郎劉爲侍中初不交言武帝聞之敕雄復君臣之好雄不得巳詣劉再拜曰向受詔而來而君臣之義絶何如於是即去武帝聞尚不和乃怒問雄曰我令卿復君臣之好何以猶絶雄曰古之君子進人以禮退人以禮今之君子進人若將加諸䣛退
```

#### Ling 1615 independent OCR + visual witness

- volume: `2`
- OCR result: no reliable exact Chinese hit for the anomaly anchor in the downloaded OCR
- PDF status: `available`
- reading asserted from Ling: `none`
- note: The OCR derivative is not usable for locating these anchors. The volume PDF is readable, but no anomaly page was deterministically located from the failed OCR; no reading is asserted from OCR.

#### 四庫本 witness family

- status: `external_only_not_scraped`
- CText visual record: `https://ctext.org/library.pl?if=gb&remap=gb&res=5115`
- reading asserted: `none`

#### Structural-reference TXT

- status: `alignment_guide_only`; authority: `low textual authority; high structural comparison utility`
- alignment reading: `晉武帝時荀勖為中書監和嶠為令故事監令由來共車嶠性雅正常疾勖諂諛後公車來嶠便登正向前坐不復容勖勖方更覓車然後得去監令各給車自此始`

```text
晉武帝時荀勖為中書監和嶠為令故事監令由來共車嶠性雅正常疾勖諂諛後公車來嶠便登正向前坐不復容勖勖方更覓車然後得去監令各給車自此始
```

The structural-reference reading is diagnostic only and is not used to overwrite Kanripo text.

### 08-shangyu-084 — `kanripo_digitization_gap` (high confidence)

- chapter: `08-shangyu` (賞譽第八)
- expected ordinal: `84`
- recommended resolution: Retain the Kanripo source unchanged. Use the Wikisource same-edition page witness as missing-text evidence, then verify against Ling page images and/or 四庫本 before any future reviewed repair.
- missing-text supplier, if any: `shishuo-wikisource-sbck`

#### Kanripo/SBCK primary witness

- status: `structural_reference_opening_absent`
- proposed/opening reading: `真長可謂金玉滿堂林公曰金`
- source location: `content/processed/shishuo/chapters/chapter-08.md`; normalized line `261`; page `<pb:KR3l0002_SBCK_003-10a>`

```text
pb:KR3l0002_SBCK_003-10a> -->
桓温行經王敦墓邊過望之云可兒可兒(亮牋曰王/孫綽與庾)
(數十年間也/敦可人之目)
殷中軍道王右軍云逸少清貴人吾於之甚至一時
無所後(有風氣不類常流也/文章志曰羲之高爽)
王仲祖稱殷淵源非以長勝人處長亦勝人(曰浩善/晉陽秋)
(接物也/以通和)
王司州與殷中軍語嘆云巳之府奥蚤已傾冩而見
殷陳勢浩汗衆源未可得測(辯玄致當時名流皆爲/徐廣晉紀曰浩清言妙)
(譽/其美)
王長史謂林公真長可謂金玉滿堂林公曰金玉滿
<!-- kanripo-page source-line=218: <pb:KR3l0002_SBCK_003-10b> -->
<!-- kanripo-page source-line=219: <pb:KR3l0002_SBCK_003-10b> -->
淵源真可王曰卿故墮其雲霧中(理談論精微長於/中興書曰浩能言)
(者皆宗歸之/老易故風流)
劉尹每稱王長史云性至通而自然有節(濛之交物/濛别傳曰)
(不敬而愛之然少孤事諸母甚謹篤義穆族不脩小/虛巳納善恕而後行希見其喜愠之色凡與一面莫)
(貧見稱/潔以清)
王右軍道謝萬石在林澤中爲自遒上歎林公器朗
神儁(心獨往風期高亮/支遁别傳曰遁任)道祖士少風領
```

#### Wikisource 四部叢刊 same-edition machine witness

- status: `located`; match type: `exact`
- page: `Page:Sibu Congkan0463-劉義慶-世説新語-3-2.djvu/127`
- page source: `https://zh.wikisource.org/wiki/Page%3ASibu%20Congkan0463-%E5%8A%89%E7%BE%A9%E6%85%B6-%E4%B8%96%E8%AA%AC%E6%96%B0%E8%AA%9E-3-2.djvu%2F127`

```text
非以長勝人處長亦勝人王司州與殷中軍語嘆云巳之府奥蚤已傾冩而見殷陳勢浩汗衆源未可得測王長史謂林公真長可謂金玉滿堂林公曰金玉滿堂復何為簡選王曰非爲簡選直致言處自寡耳王長史道江道羣人所應有乃不必有人所應無已必無會稽孔沉魏顗虞球虞存謝奉並是四族之儁于時之傑孫興公目之曰沉爲孔家金顗爲魏家玉虞爲長琳宗謝爲弘道伏王仲祖劉真長造殷中軍談談竟俱載去劉謂王曰淵源真可王曰卿故墮其雲霧中劉尹每稱王長史云性至通而自然有節王右軍道謝萬石在林澤中爲自遒上歎林公器朗神儁道祖士少風領毛骨恐没世不復見如此人道劉真長標雲柯而不扶踈簡文目𢈔赤玉省率治除謝仁祖云𢈔赤玉𦙄中無宿物殷中軍道韓太常曰康伯少自標置居然是出羣器及其發言遣辭往往有
```

#### Ling 1615 independent OCR + visual witness

- volume: `2`
- OCR result: no reliable exact Chinese hit for the anomaly anchor in the downloaded OCR
- PDF status: `available`
- reading asserted from Ling: `none`
- note: The OCR derivative is not usable for locating these anchors. The volume PDF is readable, but no anomaly page was deterministically located from the failed OCR; no reading is asserted from OCR.

#### 四庫本 witness family

- status: `external_only_not_scraped`
- CText visual record: `https://ctext.org/library.pl?if=gb&remap=gb&res=5115`
- reading asserted: `none`

#### Structural-reference TXT

- status: `alignment_guide_only`; authority: `low textual authority; high structural comparison utility`
- alignment reading: `王長史道江道群人可應有乃不必有人可應無己必無`

```text
王長史道江道群人可應有乃不必有人可應無己必無
```

The structural-reference reading is diagnostic only and is not used to overwrite Kanripo text.

### 08-shangyu-085 — `kanripo_digitization_gap` (high confidence)

- chapter: `08-shangyu` (賞譽第八)
- expected ordinal: `85`
- recommended resolution: Retain the Kanripo source unchanged. Use the Wikisource same-edition page witness as missing-text evidence, then verify against Ling page images and/or 四庫本 before any future reviewed repair.
- missing-text supplier, if any: `shishuo-wikisource-sbck`

#### Kanripo/SBCK primary witness

- status: `structural_reference_opening_absent`
- proposed/opening reading: `劉尹每稱王長史云性至通而`
- source location: `content/processed/shishuo/chapters/chapter-08.md`; normalized line `266`; page `<pb:KR3l0002_SBCK_003-10b>`

```text
流皆爲/徐廣晉紀曰浩清言妙)
(譽/其美)
王長史謂林公真長可謂金玉滿堂林公曰金玉滿
<!-- kanripo-page source-line=218: <pb:KR3l0002_SBCK_003-10b> -->
<!-- kanripo-page source-line=219: <pb:KR3l0002_SBCK_003-10b> -->
淵源真可王曰卿故墮其雲霧中(理談論精微長於/中興書曰浩能言)
(者皆宗歸之/老易故風流)
劉尹每稱王長史云性至通而自然有節(濛之交物/濛别傳曰)
(不敬而愛之然少孤事諸母甚謹篤義穆族不脩小/虛巳納善恕而後行希見其喜愠之色凡與一面莫)
(貧見稱/潔以清)
王右軍道謝萬石在林澤中爲自遒上歎林公器朗
神儁(心獨往風期高亮/支遁别傳曰遁任)道祖士少風領毛骨恐没世
不復見如此人道劉真長標雲柯而不扶踈(傳曰惔/劉尹别)
(淡榮利雖身登顯列而每挹降閑静自守而已/既令望姻婭帝室故屢居達官然性不偶俗心)
簡文目庾赤玉省率治除謝仁祖云庾赤玉匈中無
<!-- kanripo-page source-line=230: <pb:KR3l0002_SBCK_003-11a> -->
宿物(衛将軍擇子也少有令名仕至潯陽太守/赤王庾統小字中興書曰統字
```

#### Wikisource 四部叢刊 same-edition machine witness

- status: `located`; match type: `exact`
- page: `Page:Sibu Congkan0463-劉義慶-世説新語-3-2.djvu/127`
- page source: `https://zh.wikisource.org/wiki/Page%3ASibu%20Congkan0463-%E5%8A%89%E7%BE%A9%E6%85%B6-%E4%B8%96%E8%AA%AC%E6%96%B0%E8%AA%9E-3-2.djvu%2F127`

```text
府奥蚤已傾冩而見殷陳勢浩汗衆源未可得測王長史謂林公真長可謂金玉滿堂林公曰金玉滿堂復何為簡選王曰非爲簡選直致言處自寡耳王長史道江道羣人所應有乃不必有人所應無已必無會稽孔沉魏顗虞球虞存謝奉並是四族之儁于時之傑孫興公目之曰沉爲孔家金顗爲魏家玉虞爲長琳宗謝爲弘道伏王仲祖劉真長造殷中軍談談竟俱載去劉謂王曰淵源真可王曰卿故墮其雲霧中劉尹每稱王長史云性至通而自然有節王右軍道謝萬石在林澤中爲自遒上歎林公器朗神儁道祖士少風領毛骨恐没世不復見如此人道劉真長標雲柯而不扶踈簡文目𢈔赤玉省率治除謝仁祖云𢈔赤玉𦙄中無宿物殷中軍道韓太常曰康伯少自標置居然是出羣器及其發言遣辭往往有情致簡文道王懷祖才既不長於榮利又不淡直以真率
```

#### Ling 1615 independent OCR + visual witness

- volume: `2`
- OCR result: no reliable exact Chinese hit for the anomaly anchor in the downloaded OCR
- PDF status: `available`
- reading asserted from Ling: `none`
- note: The OCR derivative is not usable for locating these anchors. The volume PDF is readable, but no anomaly page was deterministically located from the failed OCR; no reading is asserted from OCR.

#### 四庫本 witness family

- status: `external_only_not_scraped`
- CText visual record: `https://ctext.org/library.pl?if=gb&remap=gb&res=5115`
- reading asserted: `none`

#### Structural-reference TXT

- status: `alignment_guide_only`; authority: `low textual authority; high structural comparison utility`
- alignment reading: `會稽孔沈魏顗虞球虞存謝奉並是四族之俊於時之桀孫興公目之曰沈為孔家金顗為魏家玉虞為長琳宗謝為弘道伏`

```text
會稽孔沈魏顗虞球虞存謝奉並是四族之俊於時之桀孫興公目之曰沈為孔家金顗為魏家玉虞為長琳宗謝為弘道伏
```

The structural-reference reading is diagnostic only and is not used to overwrite Kanripo text.

### 18-qiyi-002 — `kanripo_digitization_gap` (high confidence)

- chapter: `18-qiyi` (棲逸第十八)
- expected ordinal: `2`
- recommended resolution: Retain the Kanripo source unchanged. Use the Wikisource same-edition page witness as missing-text evidence, then verify against Ling page images and/or 四庫本 before any future reviewed repair.
- missing-text supplier, if any: `shishuo-wikisource-sbck`

#### Kanripo/SBCK primary witness

- status: `structural_reference_opening_absent`
- proposed/opening reading: `山公將去選曹欲舉嵇康康與`
- source location: `content/processed/shishuo/chapters/chapter-18.md`; normalized line `1493`; page `<pb:KR3l0002_SBCK_002-15a>`

```text
民共入山中見一人所居懸巖百仞叢)
(&KR1170;然歎息將别謂曰先生竟無言乎登乃曰子識火/從遊三年問其所圖終不荅然神謀所存良妙康每)
(而不用其才果然在於用才故用光在乎得薪所以/乎生而有光而不用其光果然在於用光人生有才)
(難乎免於今之世矣子無多求康不能用及遭吕安/保其曜用才在乎識物所以全其年今子才多識寡)
(曰孫登即阮籍所見者也嵇康執弟子禮而師焉魏/事在獄為詩自責云昔慚下惠今愧孫登王隐晉書)
(賤並没故登或黙也/晉去就易生嫌疑貴)
山公將去選曹欲舉嵇康康與書告絶(巨源為吏部/康别傳曰山)
(不以一官遇已情邪亦欲標不屈之節以杜舉者之/郎遷散騎常侍舉康康辭之并與山絶豈不識山之)
<!-- kanripo-page source-line=1439: <pb:KR3l0002_SBCK_002-15b> -->
(而非薄湯武大將軍聞而惡之/口耳乃荅濤書自說不堪流俗)
李廞是茂曽弟五子清貞有逺操而少羸病不肯婚
宦居在臨海住兄侍中墓下既有髙名王丞相欲招
禮之故辟為府掾廞得牋命笑曰茂弘乃復以一爵
假人(史父重平陽太守世有名望廞好學善草隷與/文字志曰廞字宗子江夏鍾武人祖景秦州刺)
(間王辟太尉掾以疾不赴後避難随兄南渡司徒王/兄式齊名躄疾不能行坐常仰卧彈琴讀誦不輟河)
(嘗為
```

#### Wikisource 四部叢刊 same-edition machine witness

- status: `located`; match type: `exact`
- page: `Page:Sibu Congkan0464-劉義慶-世説新語-3-3.djvu/28`
- page source: `https://zh.wikisource.org/wiki/Page%3ASibu%20Congkan0464-%E5%8A%89%E7%BE%A9%E6%85%B6-%E4%B8%96%E8%AA%AC%E6%96%B0%E8%AA%9E-3-3.djvu%2F28`

```text
盛德之美以問之仡然不應復叙有為之教棲神導氣之術以觀之彼猶如前凝矚不轉籍因對之長嘯良久乃笑曰可更作籍復嘯意盡⟦{{SKchar|2385}}⟧還半嶺許聞上𪡧然有聲如數部鼔吹林谷傳響顧看廼向人嘯也嵇康遊於汲郡山中遇道士孫登遂與之遊康臨去登曰君才則髙矣保身之道不足山公將去選曹欲舉嵇康康與書告絶李廞是茂曽弟五子清貞有逺操而少羸病不肯婚宦居在臨海住兄侍中墓下既有髙名王丞相欲招禮之故辟為府掾廞得牋命笑曰茂𢎞乃復以一爵假人何驃騎弟以髙情避世而驃騎勸之令仕荅曰予弟五之名何必減驃騎阮光禄在東山蕭然無事常内足於懷有人以問王右軍右軍曰此君近不驚寵辱雖古之沈㝠何以過此孔車騎少有嘉遁意年四十餘始應安東命未仕宦時常獨⟦{{SKchar|3462}}⟧歌吹自箴誨自稱孔郞遊散名山百姓謂有
```

#### Ling 1615 independent OCR + visual witness

- volume: `3`
- OCR result: no reliable exact Chinese hit for the anomaly anchor in the downloaded OCR
- PDF status: `local_pdf_integrity_failure`
- reading asserted from Ling: `none`
- note: The OCR derivative is not usable for locating these anchors. The local volume-3 PDF fails integrity checks; no reading is asserted from it.

#### 四庫本 witness family

- status: `external_only_not_scraped`
- CText visual record: `https://ctext.org/library.pl?if=gb&remap=gb&res=5115`
- reading asserted: `none`

#### Structural-reference TXT

- status: `alignment_guide_only`; authority: `low textual authority; high structural comparison utility`
- alignment reading: `嵇康游於汲郡山中遇道士孫登遂與之游康臨去登曰君才則高矣保身之道不足`

```text
嵇康游於汲郡山中遇道士孫登遂與之游康臨去登曰君才則高矣保身之道不足
```

The structural-reference reading is diagnostic only and is not used to overwrite Kanripo text.

### 18-qiyi-011 — `kanripo_digitization_gap` (high confidence)

- chapter: `18-qiyi` (棲逸第十八)
- expected ordinal: `11`
- recommended resolution: Retain the Kanripo source unchanged. Use the Wikisource same-edition page witness as missing-text evidence, then verify against Ling page images and/or 四庫本 before any future reviewed repair.
- missing-text supplier, if any: `shishuo-wikisource-sbck`

#### Kanripo/SBCK primary witness

- status: `structural_reference_opening_absent`
- proposed/opening reading: `許玄度隱在永興南幽穴中每`
- source location: `content/processed/shishuo/chapters/chapter-18.md`; normalized line `1543`; page `<pb:KR3l0002_SBCK_002-17b>`

```text
未嘗出京邑人士思欲見之乃遣信報少
孤云兄病篤狼狽至都時賢見之者莫不嗟重因相
<!-- kanripo-page source-line=1483: <pb:KR3l0002_SBCK_002-17b> -->
<!-- kanripo-page source-line=1484: <pb:KR3l0002_SBCK_002-17b> -->
(廣陵侯仕至大司農/逯以武勇顯有功封)謝太傅曰卿兄弟志業何其太
殊戴曰下官不堪其憂家弟不改其樂
許玄度隱在永興南幽穴中每致四方諸侯之遺或
謂許曰嘗聞箕山人似不爾耳許曰筐篚苞苴故當
輕於天下之寳耳(葦或以茅此言許由尚致堯帝之/鄭玄禮記注云苞苴裹肉也或以)
(豈非輕邪/讓筐篚之遺)
范宣未嘗入公門韓康伯與同載遂誘俱入郡范便
於車後趨下(家于豫章以清潔自立/續晉陽秋曰宣少尚隱遁)
郄超每聞欲高尚隱退者輙為辦百萬資并為造立
居宇在剡為戴公起宅甚精整戴始往舊居與所親
<!-- kanripo-page source-line=1495: <pb:KR3l0002_SBCK_002-18a> -->
書曰近至剡如官舍郄為傅約亦辦百萬資傳隐事
差互故不果遺(小字/約瓊)
許掾好遊山水而體便登陟時人云許非徒有勝情
實有濟勝之具
郄尚書與謝居士
```

#### Wikisource 四部叢刊 same-edition machine witness

- status: `located`; match type: `exact`
- page: `Page:Sibu Congkan0464-劉義慶-世説新語-3-3.djvu/34`
- page source: `https://zh.wikisource.org/wiki/Page%3ASibu%20Congkan0464-%E5%8A%89%E7%BE%A9%E6%85%B6-%E4%B8%96%E8%AA%AC%E6%96%B0%E8%AA%9E-3-3.djvu%2F34`

```text
固其後周詣翟翟不與語孟萬年及弟少孤居武昌陽新縣萬年遊宦有盛名當世少孤未嘗出京邑人士思欲見之乃遣信報少孤云兄病篤狼狽至都時賢見之者莫不嗟重因相謂曰少孤如此萬年可死康僧淵在豫章去郭數十里立精舍㫄連嶺帶長川芳林列於軒庭清流激於堂宇乃閒居研講希心理味𢈔公諸人多往看之觀其運用吐納風流轉佳加已處之怡然亦有以自得聲名乃興後不堪遂出戴安道既厲操東山而其兄欲建式遏之功謝太傅曰卿兄弟志業何其太殊戴曰下官不堪其憂家弟不改其樂許𤣥度隱在永興南幽穴中每致四方諸侯之遺或謂許曰嘗聞箕山人似不爾耳許曰筐篚苞苴故當輕於天下之寳耳范宣未嘗入公門韓康伯與同載遂誘俱入郡范便於車後趨下郄超每聞欲高尚隱𨓆者輙為辦百萬資并為造立居宇在剡為
```

#### Ling 1615 independent OCR + visual witness

- volume: `3`
- OCR result: no reliable exact Chinese hit for the anomaly anchor in the downloaded OCR
- PDF status: `local_pdf_integrity_failure`
- reading asserted from Ling: `none`
- note: The OCR derivative is not usable for locating these anchors. The local volume-3 PDF fails integrity checks; no reading is asserted from it.

#### 四庫本 witness family

- status: `external_only_not_scraped`
- CText visual record: `https://ctext.org/library.pl?if=gb&remap=gb&res=5115`
- reading asserted: `none`

#### Structural-reference TXT

- status: `alignment_guide_only`; authority: `low textual authority; high structural comparison utility`
- alignment reading: `康僧淵在豫章去郭數十里立精捨旁連嶺帶長川芳林列於軒庭清流激於堂宇乃閑居研講希心理味庾公諸人多往看之觀其運用吐納風流轉佳加已處之怡然亦有以自得聲名乃興後不堪遂出`

```text
康僧淵在豫章去郭數十里立精捨旁連嶺帶長川芳林列於軒庭清流激於堂宇乃閑居研講希心理味庾公諸人多往看之觀其運用吐納風流轉佳加已處之怡然亦有以自得聲名乃興後不堪遂出
```

The structural-reference reading is diagnostic only and is not used to overwrite Kanripo text.

### 19-xianyuan-005 — `kanripo_digitization_gap` (high confidence)

- chapter: `19-xianyuan` (賢媛第十九)
- expected ordinal: `5`
- recommended resolution: Retain the Kanripo source unchanged. Use the Wikisource same-edition page witness as missing-text evidence, then verify against Ling page images and/or 四庫本 before any future reviewed repair.
- missing-text supplier, if any: `shishuo-wikisource-sbck`

#### Kanripo/SBCK primary witness

- status: `structural_reference_opening_absent`
- proposed/opening reading: `停之許因謂曰婦
有四德卿有`
- source location: `content/processed/shishuo/chapters/chapter-19.md`; normalized line `1599`; page `<pb:KR3l0002_SBCK_002-21a>`

```text
满室移)
(不尚華麗有母儀徳行/十太祖納於譙性約儉)
<!-- kanripo-page source-line=1539: <pb:KR3l0002_SBCK_002-20a> -->
<!-- kanripo-page source-line=1540: <pb:KR3l0002_SBCK_002-21a> -->
(誅/所)婦曰無憂桓必勸入桓果語許云阮家既嫁醜女
與卿故當有意卿宜察之許便回入内既見婦即欲
出婦料其此出無復入理便捉𥚑停之許因謂曰婦
有四德卿有其幾(婦德婦言婦容婦功鄭注曰德謂/周禮九嬪掌婦學之法以教九御)
(謂婉娩功謂絲枲/貞順言謂辭令容)婦曰新婦所乏唯容爾然士有百
行君有幾許云皆僃婦曰夫百行以徳為首君好色
不好德何謂皆僃允有慚色遂相敬重
許允為吏部郎多用其鄉里魏明帝遣虎賁收之其
婦出誡允曰明主可以理奪難以情求既至帝覈問
之允對曰舉爾所知臣之郷人臣所知也陛下檢校
<!-- kanripo-page source-line=1551: <pb:KR3l0002_SBCK_002-21b> -->
為稱職與不若不稱職臣受其罪既檢校皆官得其
人於是乃釋允衣服敗壞詔賜新衣初允𬒳收舉家
號哭阮新婦自若云勿憂尋還作粟粥待頃之允至
(非次將加其罪允妻阮氏跣出謂
```

#### Wikisource 四部叢刊 same-edition machine witness

- status: `located`; match type: `exact`
- page: `Page:Sibu Congkan0464-劉義慶-世説新語-3-3.djvu/40`
- page source: `https://zh.wikisource.org/wiki/Page%3ASibu%20Congkan0464-%E5%8A%89%E7%BE%A9%E6%85%B6-%E4%B8%96%E8%AA%AC%E6%96%B0%E8%AA%9E-3-3.djvu%2F40`

```text
益故不爲也魏武帝崩文帝悉取武帝宫人自侍及帝病困卞后出看疾太后入户見直侍並是昔日所愛幸者太后問何時來邪云正伏魄時過因不復前而歎曰狗䑕不食汝餘死故應爾至山陵亦竟不臨趙母嫁女女臨去敕之曰慎勿為好女曰不為好可為惡邪母曰好尚不可為其況惡乎許允婦是阮衛尉女德如妹竒醜交禮竟允無復入理家人深以為憂㑹允有客至婦令婢視之還荅曰是桓郎桓郎者桓範也婦曰無憂桓必勸入桓果語許云阮家既嫁醜女與卿故當有意卿宜察之許便回入内既見婦即欲出婦料其此出無復入理便捉𥚑停之許因謂曰婦有四德卿有其幾婦曰新婦所乏唯容爾然士有百行君有幾許云皆僃婦曰夫百行以徳為首君好色不好德何謂皆僃允有慚色遂相敬重許允為吏部郎多用其鄉里魏明帝遣虎賁收之其婦出誡
```

#### Ling 1615 independent OCR + visual witness

- volume: `3`
- OCR result: no reliable exact Chinese hit for the anomaly anchor in the downloaded OCR
- PDF status: `local_pdf_integrity_failure`
- reading asserted from Ling: `none`
- note: The OCR derivative is not usable for locating these anchors. The local volume-3 PDF fails integrity checks; no reading is asserted from it.

#### 四庫本 witness family

- status: `external_only_not_scraped`
- CText visual record: `https://ctext.org/library.pl?if=gb&remap=gb&res=5115`
- reading asserted: `none`

#### Structural-reference TXT

- status: `alignment_guide_only`; authority: `low textual authority; high structural comparison utility`
- alignment reading: `趙母嫁女女臨去敕之曰慎勿為好女曰不為好可為惡邪母曰好尚不可為其況惡乎`

```text
趙母嫁女女臨去敕之曰慎勿為好女曰不為好可為惡邪母曰好尚不可為其況惡乎
```

The structural-reference reading is diagnostic only and is not used to overwrite Kanripo text.

### 18-qiyi-010 — `boundary_shift` (high confidence)

- chapter: `18-qiyi` (棲逸第十八)
- expected ordinal: `10`
- recommended resolution: Do not edit the source in this task. Review only the boundary manifest: remove the false continuation boundary or move it to the surviving entry opening described by the same-edition witness.
- missing-text supplier, if any: `none; this is a boundary case`

#### Kanripo/SBCK primary witness

- status: `present_as_current_proposal`
- proposed/opening reading: `病篤狼狽至都時賢見之者莫`
- source location: `content/processed/shishuo/chapters/chapter-18.md`; normalized line `1538`; page `<pb:KR3l0002_SBCK_002-17a>`

```text
翟道淵與汝南周子南少相友共隐于尋陽庾
太尉說周以當世之務周遂仕翟秉志彌固其後周
詣翟翟不與語(進之後也篤行任素義譲廉潔饋贈/晉陽秋曰翟湯字道淵南陽人漢方)
(初庾亮臨江州聞翟湯之風束帶躡屐而詣焉亮禮/一無所受值亂多宼聞湯名德皆不敢犯尋陽記曰)
(薦之徴國子博士不赴主簿張玄曰此君卧龍不可/甚恭湯曰使君直敬其枯木朽株耳亮稱其能言表)
(于家/動也終)
孟萬年及弟少孤居武昌陽新縣萬年遊宦有盛名
當世少孤未嘗出京邑人士思欲見之乃遣信報少
孤云兄病篤狼狽至都時賢見之者莫不嗟重因相
<!-- kanripo-page source-line=1483: <pb:KR3l0002_SBCK_002-17b> -->
<!-- kanripo-page source-line=1484: <pb:KR3l0002_SBCK_002-17b> -->
(廣陵侯仕至大司農/逯以武勇顯有功封)謝太傅曰卿兄弟志業何其太
殊戴曰下官不堪其憂家弟不改其樂
許玄度隱在永興南幽穴中每致四方諸侯之遺或
謂許曰嘗聞箕山人似不爾耳許曰筐篚苞苴故當
輕於天下之寳耳(葦或以茅此言許由尚致堯帝之/鄭玄禮記注云苞苴裹肉也或以)
(豈非輕邪/讓筐篚之遺)
范宣未嘗入公門韓康伯與同載遂誘俱入郡范便
於車後趨下(家
```

#### Wikisource 四部叢刊 same-edition machine witness

- status: `located`; match type: `exact`
- page: `Page:Sibu Congkan0464-劉義慶-世説新語-3-3.djvu/33`
- page source: `https://zh.wikisource.org/wiki/Page%3ASibu%20Congkan0464-%E5%8A%89%E7%BE%A9%E6%85%B6-%E4%B8%96%E8%AA%AC%E6%96%B0%E8%AA%9E-3-3.djvu%2F33`

```text
翛然而⟦{{SKchar|2385}}⟧居陽岐積年衣食有無常與村人共值已匱乏村人亦如之甚厚為鄉閭所安南陽翟道淵與汝南周子南少相友共隐于尋陽𢈔太尉說周以當世之務周遂仕翟秉志彌固其後周詣翟翟不與語孟萬年及弟少孤居武昌陽新縣萬年遊宦有盛名當世少孤未嘗出京邑人士思欲見之乃遣信報少孤云兄病篤狼狽至都時賢見之者莫不嗟重因相謂曰少孤如此萬年可死康僧淵在豫章去郭數十里立精舍㫄連嶺帶長川芳林列於軒庭清流激於堂宇乃閒居研講希心理味𢈔公諸人多往看之觀其運用吐納風流轉佳加已處之怡然亦有以自得聲名乃興後不堪遂出戴安道既厲操東山而其兄欲建式遏之功謝太傅曰卿兄弟志業何其太殊戴曰下官不堪其憂家弟不改其樂許𤣥度隱在永興南幽穴中每致四方諸侯之遺或謂許曰嘗聞箕山
```

- boundary observation: The full 孟萬年 / 少孤 continuation remains contiguous before the next independent 康僧淵 entry; 病篤... is not supported as an opening.

#### Ling 1615 independent OCR + visual witness

- volume: `3`
- OCR result: no reliable exact Chinese hit for the anomaly anchor in the downloaded OCR
- PDF status: `local_pdf_integrity_failure`
- reading asserted from Ling: `none`
- note: The OCR derivative is not usable for locating these anchors. The local volume-3 PDF fails integrity checks; no reading is asserted from it.

#### 四庫本 witness family

- status: `external_only_not_scraped`
- CText visual record: `https://ctext.org/library.pl?if=gb&remap=gb&res=5115`
- reading asserted: `none`

#### Structural-reference TXT

- status: `alignment_guide_only`; authority: `low textual authority; high structural comparison utility`
- alignment reading: `孟萬年及弟少孤居武昌陽新縣萬年游宦有盛名當世少孤未嘗出京邑人士思欲見之乃遣信報少孤雲兄病篤狼狽至都時賢見之者莫不嗟重因相謂曰少孤如此萬年可死`

```text
孟萬年及弟少孤居武昌陽新縣萬年游宦有盛名當世少孤未嘗出京邑人士思欲見之乃遣信報少孤雲兄病篤狼狽至都時賢見之者莫不嗟重因相謂曰少孤如此萬年可死
```

The structural-reference reading is diagnostic only and is not used to overwrite Kanripo text.

### 18-qiyi-015 — `boundary_shift` (high confidence)

- chapter: `18-qiyi` (棲逸第十八)
- expected ordinal: `15`
- recommended resolution: Do not edit the source in this task. Review only the boundary manifest: remove the false continuation boundary or move it to the surviving entry opening described by the same-edition witness.
- missing-text supplier, if any: `none; this is a boundary case`

#### Kanripo/SBCK primary witness

- status: `present_as_current_proposal`
- proposed/opening reading: `尚書與謝居士善常稱謝慶緒`
- source location: `content/processed/shishuo/chapters/chapter-18.md`; normalized line `1556`; page `<pb:KR3l0002_SBCK_002-18a>`

```text
未嘗入公門韓康伯與同載遂誘俱入郡范便
於車後趨下(家于豫章以清潔自立/續晉陽秋曰宣少尚隱遁)
郄超每聞欲高尚隱退者輙為辦百萬資并為造立
居宇在剡為戴公起宅甚精整戴始往舊居與所親
<!-- kanripo-page source-line=1495: <pb:KR3l0002_SBCK_002-18a> -->
書曰近至剡如官舍郄為傅約亦辦百萬資傳隐事
差互故不果遺(小字/約瓊)
許掾好遊山水而體便登陟時人云許非徒有勝情
實有濟勝之具
郄尚書與謝居士善常稱謝慶緒識見雖不絶人可
以累心處都盡(曰謝敷字慶緒㑹稽人崇信釋氏初/尚書郄恢也别見檀道鸞續晉陽秋)
(納不倦以母老還南山若邪中内史郗愔表薦之徵/入太平山中十餘年以長齋供養為業招引同事化)
(當之時戴逵居剡既美才藝而交游貴盛先敷著名/博士不就初月犯少㣲星一名處士星占云以處士)
(吳人云吳中高士便是求死不得/時人憂之俄而敷死㑹稽人士以嘲)

```

#### Wikisource 四部叢刊 same-edition machine witness

- status: `located`; match type: `exact`
- page: `Page:Sibu Congkan0464-劉義慶-世説新語-3-3.djvu/36`
- page source: `https://zh.wikisource.org/wiki/Page%3ASibu%20Congkan0464-%E5%8A%89%E7%BE%A9%E6%85%B6-%E4%B8%96%E8%AA%AC%E6%96%B0%E8%AA%9E-3-3.djvu%2F36`

```text
辦百萬資并為造立居宇在剡為戴公起宅甚精整戴始往舊居與所親書曰近至剡如官舍郄為傅約亦辦百萬資⟦{{SKchar|2652}}⟧隐事差互故不果遺許掾好遊山水而體便登陟時人云許非徒有勝情實有濟勝之具郄尚書與謝居士善常稱謝慶緒識見雖不絶人可以累心處都盡
```

- boundary observation: The page witness begins 郄尚書與謝居士善..., including 郄 before the Kanripo proposed anchor 尚書....

#### Ling 1615 independent OCR + visual witness

- volume: `3`
- OCR result: no reliable exact Chinese hit for the anomaly anchor in the downloaded OCR
- PDF status: `local_pdf_integrity_failure`
- reading asserted from Ling: `none`
- note: The OCR derivative is not usable for locating these anchors. The local volume-3 PDF fails integrity checks; no reading is asserted from it.

#### 四庫本 witness family

- status: `external_only_not_scraped`
- CText visual record: `https://ctext.org/library.pl?if=gb&remap=gb&res=5115`
- reading asserted: `none`

#### Structural-reference TXT

- status: `alignment_guide_only`; authority: `low textual authority; high structural comparison utility`
- alignment reading: `郗超每聞欲高尚隱退者輒為辦百萬資並為造立居宇在剡為戴公起宅甚精整戴始往舊居與所親書曰近至剡如官捨郗為傅約亦辦百萬資傅隱事差互故不果遺`

```text
郗超每聞欲高尚隱退者輒為辦百萬資並為造立居宇在剡為戴公起宅甚精整戴始往舊居與所親書曰近至剡如官捨郗為傅約亦辦百萬資傅隱事差互故不果遺
```

The structural-reference reading is diagnostic only and is not used to overwrite Kanripo text.

### 25-paidiao-019 — `boundary_shift` (high confidence)

- chapter: `25-paidiao` (排調第二十五)
- expected ordinal: `19`
- recommended resolution: Do not edit the source in this task. Review only the boundary manifest: remove the false continuation boundary or move it to the surviving entry opening described by the same-edition witness.
- missing-text supplier, if any: `none; this is a boundary case`

#### Kanripo/SBCK primary witness

- status: `present_as_current_proposal`
- proposed/opening reading: `人
于寳向劉真長(奮武將軍父瑩丹陽丞寳少以博學/中興書曰寳字令升新蔡人祖正吳)
(散騎常侍/才器著稱歷)叙其&KR0679;神記(寳母至妒葬寳父時因推/孔氏志怪曰寳父有嬖人)
(漸有氣息輿還家終日而蘇說寳父常致飲食與之/著藏中經十年而母䘮開墓其婢伏棺上就視猶煖)
(數年後方卒寳因作&KR0679;神記中云有所感起是也/接寢恩情如生家中吉凶輙語之校之悉驗平復)劉`
- source location: `content/processed/shishuo/chapters/chapter-25.md`; normalized line `2439`; page `<pb:KR3l0002_SBCK_002-60a>`

```text
下不以爲濁聚溷
之穢卿之所保何足自稱
王長豫㓜便和令丞相愛恣甚篤毎共圍棊丞相欲
舉行長豫按指不聽丞相笑曰詎得爾相與似有瓜
葛(葛踈親也/蔡邕曰瓜)
明帝問周伯仁眞長何如人荅曰故是千斤犗特王
公笑其言伯仁曰不如捲角牸有盤辟之好(王也/以戲)
<!-- kanripo-page source-line=2381: <pb:KR3l0002_SBCK_002-60a> -->
王丞相枕周伯仁䣛指其腹曰卿此中何所有荅曰
此中空洞無物然容卿輩數百人
于寳向劉真長(奮武將軍父瑩丹陽丞寳少以博學/中興書曰寳字令升新蔡人祖正吳)
(散騎常侍/才器著稱歷)叙其&KR0679;神記(寳母至妒葬寳父時因推/孔氏志怪曰寳父有嬖人)
(漸有氣息輿還家終日而蘇說寳父常致飲食與之/著藏中經十年而母䘮開墓其婢伏棺上就視猶煖)
(數年後方卒寳因作&KR0679;神記中云有所感起是也/接寢恩情如生家中吉凶輙語之校之悉驗平復)劉
曰卿可謂鬼之董狐(園趙宣子未出境而復太史書/春秋傳曰趙穿攻晉靈公於桃)
(反不討賊非子而誰孔子曰董狐古之良史也書法/趙盾弑其君宣子曰不然對曰子為正卿亡不越境)
(大夫也為法受惡/不隱趙盾古之賢)
許文思徃顧和許顧先在帳中眠許至便徑就牀角
<!-- kanripo-page s
```

#### Wikisource 四部叢刊 same-edition machine witness

- status: `located`; match type: `exact`
- page: `Page:Sibu Congkan0464-劉義慶-世説新語-3-3.djvu/118`
- page source: `https://zh.wikisource.org/wiki/Page%3ASibu%20Congkan0464-%E5%8A%89%E7%BE%A9%E6%85%B6-%E4%B8%96%E8%AA%AC%E6%96%B0%E8%AA%9E-3-3.djvu%2F118`

```text
曰詎得爾相與似有𤓰葛明帝問周伯仁眞長何如人荅曰故是千斤犗特王公笑其言伯仁曰不如捲角牸有盤辟之好王丞相枕周伯仁䣛指其腹曰卿此中何所有荅曰此中空洞無物然容卿輩數百人于寳向劉真長叙其⟦{{SKchar|302}}⟧神記劉曰卿可謂⟦{{SKchar|3932}}⟧之董狐許文思徃顧和許顧先在帳中眠許至便徑就牀角枕共語既而喚顧共行顧乃命左右取杭上新衣易己體上所著許笑曰卿乃復有行來衣乎康僧淵目深而鼻高王丞相毎調之僧淵曰鼻者面之山目者面之淵山不高則不靈淵不深則不清何次道徃瓦官寺禮拜甚勤阮思曠語之曰卿志大宇宙勇邁終古何曰卿今日何故忽見推阮曰我圖數千戸郡尚不能得卿廼圖作佛不亦大乎𢈔征西大舉征胡既成行止鎮襄陽殷豫章與書送一折角如意以調之⟦{{SKchar|2928}}⟧荅書曰得所致雖是敗物猶欲理而用之桓大司
```

- boundary observation: The page witness has the preceding 王丞相 / 周伯仁 text ending before 于寳向劉真長; the Kanripo 人 is not the new-entry opening.

#### Ling 1615 independent OCR + visual witness

- volume: `3`
- OCR result: no reliable exact Chinese hit for the anomaly anchor in the downloaded OCR
- PDF status: `local_pdf_integrity_failure`
- reading asserted from Ling: `none`
- note: The OCR derivative is not usable for locating these anchors. The local volume-3 PDF fails integrity checks; no reading is asserted from it.

#### 四庫本 witness family

- status: `external_only_not_scraped`
- CText visual record: `https://ctext.org/library.pl?if=gb&remap=gb&res=5115`
- reading asserted: `none`

#### Structural-reference TXT

- status: `alignment_guide_only`; authority: `low textual authority; high structural comparison utility`
- alignment reading: `乾寶向劉真長敘其搜神記劉曰卿可謂鬼之董狐`

```text
乾寶向劉真長敘其搜神記劉曰卿可謂鬼之董狐
```

The structural-reference reading is diagnostic only and is not used to overwrite Kanripo text.

## Interpretation limits

The six guide-gap cases are classified as `kanripo_digitization_gap` because the same-edition Wikisource page witness contains the expected passages while the current Kanripo witness does not. This identifies a likely digitization/source-file omission, not permission to patch the primary text. The three known boundary cases are `boundary_shift`; no textual source repair has been made. Ling and 四庫 readings remain unasserted where local/allowed machine evidence was insufficient.

No entity extraction, relationship extraction, translation, summary, or historical interpretation was performed.
## Targeted repair overlay (2026-08-11)

This overlay records the targeted repair pass. The evidence narrative below is retained as the earlier comparison record; no raw or normalized witness was rewritten.

| case | status | canonical entry | action |
|---|---|---|---|
| `05-fangzheng-014` | `supplemented` | `05-fangzheng-014` | explicit Wikisource supplement |
| `08-shangyu-084` | `supplemented` | `08-shangyu-084` | explicit Wikisource supplement |
| `08-shangyu-085` | `supplemented` | `08-shangyu-085` | explicit Wikisource supplement |
| `18-qiyi-002` | `supplemented` | `18-qiyi-002` | explicit Wikisource supplement |
| `18-qiyi-011` | `supplemented` | `18-qiyi-011` | explicit Wikisource supplement |
| `19-xianyuan-005` | `supplemented` | `19-xianyuan-005` | explicit Wikisource supplement |
| `18-qiyi-010` | `boundary_removed` | `18-qiyi-010` | boundary removed |
| `18-qiyi-015` | `boundary_shifted` | `18-qiyi-017` | boundary shifted |
| `25-paidiao-019` | `boundary_shifted` | `25-paidiao-019` | boundary shifted |

Ling 1615 volume 3 PDF refresh: `sources/downloads/shishuo/ling-1615/pdf/shishuoxinyu3jua03liuy.pdf`, 40809235 bytes, SHA-256 `2c5153438232105d04a1f5d2ed99585077117cf3fd367b104a1178f3b175d882`, readability `passed`.

The explicit supplements are recorded in `content/curated/shishuo/collation/supplemented-segments.yaml`; they are not replacements for Kanripo text.
