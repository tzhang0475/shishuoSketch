# Shishuo structural-high review

This report reviews only the 90 records classified `structural_high` in the existing triage file. It is a read-only structural audit; it does not run full-text collation, modify source text, repair a boundary, or regenerate entries.

The primary comparison is Kanripo SBCK against the Wikisource 四部叢刊本 machine witness. `SKchar` templates and the small attested glyph-form map are alignment aids only; every emitted reading preserves the witness spelling. No Ling 1615 or 四庫 fallback was needed for these structural classifications.

## Summary

| classification | records |
|---|---:|
| true boundary errors (`true_boundary_error`) | 0 |
| missing-entry cases (`missing_entry`) | 5 |
| extra boundaries (`extra_boundary`) | 0 |
| annotation-boundary issues (`annotation_boundary_only`) | 8 |
| textual differences not structural (`textual_difference_not_structural`) | 5 |
| harmless alignment differences (`harmless_alignment_difference`) | 72 |
| unresolved cases (`unresolved`) | 0 |

Current manifests contain **1130** entries across the 36 chapters. The 1130-entry total is structurally supported by manifest continuity and the reviewed same-edition anchor order: **True**.

The current canonical structure contains 6 explicit primary-witness gap entries. They are reported as missing-entry cases because the Kanripo primary is absent at those positions; the existing supplements are not new repairs in this audit.

## Review records

### 01-dexing — 德行第一

#### discrepancy-001 — 01-dexing-003

- classification: `harmless_alignment_difference`; confidence: `high`
- source discrepancy: `unmatched_entry_opening`; source record index: `1`
- review reason: The same-edition witness locates the same opening in the current boundary order; differences are glyph templates or attested witness forms.
- recommended action: No repair in this task. Preserve the current canonical boundary and all witness spellings.
- canonical boundary: `01-dexing-003` ordinal `3`, primary status `present`, anchor `郭林宗至汝南造袁奉髙(原介休人泰少孤年二十/續漢書曰郭泰字林宗太)\n`
- canonical source position: normalized line `716`, source line `659`, page `<pb:KR3l0002_SBCK_001-1b>`
- Kanripo SBCK: `present`; context: `\n(卿國有顔子寧知之乎奉髙曰卿見吾叔度邪戴良/川荀季和執憲手曰足下吾師範也後見袁奉髙曰)\n(不樂乎復從牛醫兒所來邪良曰瞻之在前忽焉在/少所服下見憲則自降薄悵然若有所失母問汝何)\n(之師也/後所謂良)\n郭林宗至汝南造袁奉髙(原介休人泰少孤年二十/續漢書曰郭泰字林宗太)\n<!-- kanripo-page source-line=661: <pb:KR3l0002_SBCK_001-2a> -->\n(道不改其樂李元禮一見稱之曰吾見士多矣無如/行學至城阜屈伯彦精廬乏食衣不蓋形而處約味)\n(不有慚容唯為郭有道碑頌無愧耳初以有道君子/林宗者也及卒蔡伯喈為作碑曰吾為人作銘未嘗)\n(疾汝南先賢傳曰袁宏字奉髙慎陽人友黄叔度於/徵泰曰吾觀乾象人事天之`
- Wikisource SBCK: `located`; page `Page:Sibu Congkan0462-劉義慶-世説新語-3-1.djvu/11`; bounded reading: `郭林宗至汝南造𡊮奉髙`
- adjacent-boundary order: `ordered`; positions `{'previous': 71, 'current': 93, 'next': 152}`

---

#### discrepancy-002 — 01-dexing-013

- classification: `harmless_alignment_difference`; confidence: `high`
- source discrepancy: `unmatched_entry_opening`; source record index: `2`
- review reason: The same-edition witness locates the same opening in the current boundary order; differences are glyph templates or attested witness forms.
- recommended action: No repair in this task. Preserve the current canonical boundary and all witness spellings.
- canonical boundary: `01-dexing-013` ordinal `13`, primary status `present`, anchor `華歆王朗俱乘船避難有一人`
- canonical source position: normalized line `778`, source line `721`, page `<pb:KR3l0002_SBCK_001-4b>`
- Kanripo SBCK: `present`; context: `臘之明日為祝嵗古之遺語也/五祀傳曰臘接也祭則新故交接也秦)嘗集子姪燕\n飲王亦學之有人向張華說此事張曰王之學華皆\n是形骸之外去之所以更逺(先范陽人也累遷司空/王隱晉書曰張華字茂)\n(倫所害/而為趙王)\n華歆王朗俱乘船避難有一人欲依附歆輙難之朗\n曰幸尚寛何為不可後賊追至王欲舍所攜人歆曰\n本所以疑正為此耳既已納其自託寧可以急相棄\n邪遂攜拯如初世以此定華王之優劣(歆為下邽令/華嶠譜叙曰)\n(出道遇一丈夫獨行願得與俱皆哀許之歆獨曰不/漢室方亂乃與同志士鄭太等六七人避世自武闗)\n<!-- kanripo-page source-line=727: <pb:KR3l0002_SBCK_001-5a> -->\n(知其義若有進退可中棄乎衆不忍卒與俱行`
- Wikisource SBCK: `located`; page `Page:Sibu Congkan0462-劉義慶-世説新語-3-1.djvu/17`; bounded reading: `華歆王朗俱乘⟦{{SKchar|3548}}⟧避難有一人`
- adjacent-boundary order: `ordered`; positions `{'previous': 621, 'current': 669, 'next': 744}`

---

### 02-yanyu — 言語第二

#### discrepancy-008 — 02-yanyu-052

- classification: `harmless_alignment_difference`; confidence: `high`
- source discrepancy: `unmatched_entry_opening`; source record index: `8`
- review reason: The same-edition witness locates the same opening in the current boundary order; differences are glyph templates or attested witness forms.
- recommended action: No repair in this task. Preserve the current canonical boundary and all witness spellings.
- canonical boundary: `02-yanyu-052` ordinal `52`, primary status `present`, anchor `庾法畼造庾太尉握麈尾至佳`
- canonical source position: normalized line `1464`, source line `1407`, page `<pb:KR3l0002_SBCK_001-35b>`
- Kanripo SBCK: `present`; context: `子有泣者有不\n泣者和以問二孫玄謂被親故泣不被親故不泣敷\n曰不然當由忘情故不泣不能忘情故泣(曰佛在隂/大智度論)\n(僉然不樂郁伊交涕諸無學人但念諸法一切無常/菴羅雙樹間入般湼槃卧北首大地震動諸三學人)\n庾法畼造庾太尉握麈尾至佳公曰此至佳那得在\n<!-- kanripo-page source-line=1409: <pb:KR3l0002_SBCK_001-36a> -->\n法畼曰廉者不求貪者不與故得在耳(出未詳法畼/法畼氏族所)\n(悟銳有神才辭通辯/著人物論自叙其美云)\n庾穉恭為荆州(也少有大度時論以經畧許之兄太/庾翼别傳曰翼字穉恭潁川鄢陵人)\n(七州進征南將軍荆州刺史/尉亮薨朝議推才乃以翼都督)以毛扇上武帝武帝\n疑是故物(之風不減`
- Wikisource SBCK: `located`; page `Page:Sibu Congkan0462-劉義慶-世説新語-3-1.djvu/79`; bounded reading: `𢈔法畼造𢈔太尉握麈尾至佳`
- adjacent-boundary order: `ordered`; positions `{'previous': 2982, 'current': 3080, 'next': 3115}`

---

#### discrepancy-011 — 02-yanyu-072

- classification: `harmless_alignment_difference`; confidence: `high`
- source discrepancy: `unmatched_entry_opening`; source record index: `11`
- review reason: The same-edition witness locates the same opening in the current boundary order; differences are glyph templates or attested witness forms.
- recommended action: No repair in this task. Preserve the current canonical boundary and all witness spellings.
- canonical boundary: `02-yanyu-072` ordinal `72`, primary status `present`, anchor `王中郎令伏玄度習鑿齒(太原晉陽人祖東海太守/王中郎傳曰坦之字文度)\n(至譽輯朝野標的當時累遷侍中中書令領北中郎/承清淡平逺父述貞貴簡正坦之器度淳深孝友天)\n(人少有才學舉秀才大司馬桓温叅軍領大著作掌/將徐兖二州刺史中興書曰伏滔字玄度平昌安丘)\n(善尺牘桓温在荆州辟為從事歴治中别駕遷滎陽/國史游撃將軍卒習鑿齒字彦威襄陽人少以文稱)\n(守/太)論青`
- canonical source position: normalized line `1580`, source line `1523`, page `<pb:KR3l0002_SBCK_001-41a>`
- Kanripo SBCK: `present`; context: `凝之事五斗米道孫恩之攻㑹稽凝之謂民吏曰/第二子也歴江州刺史左將軍㑹稽内史晉安帝紀)\n(不設備遂為恩所害婦人集曰謝夫人名道藴有文/不須備防吾已請大道許遣鬼兵相助賊自破矣既)\n(誄頌傳於世/才所著詩賦)\n王中郎令伏玄度習鑿齒(太原晉陽人祖東海太守/王中郎傳曰坦之字文度)\n(至譽輯朝野標的當時累遷侍中中書令領北中郎/承清淡平逺父述貞貴簡正坦之器度淳深孝友天)\n(人少有才學舉秀才大司馬桓温叅軍領大著作掌/將徐兖二州刺史中興書曰伏滔字玄度平昌安丘)\n(善尺牘桓温在荆州辟為從事歴治中别駕遷滎陽/國史游撃將軍卒習鑿齒字彦威襄陽人少以文稱)\n(守/太)論青楚人物(管仲隰朋召忽輪扁寗戚麥丘人逢/滔集載其論畧曰滔以春秋時鮑叔)\n(鄒奭莒大夫田子方檀子魯`
- Wikisource SBCK: `located`; page `Page:Sibu Congkan0462-劉義慶-世説新語-3-1.djvu/90`; bounded reading: `王中郎令伏⟦{{SKchar|2593}}⟧度習鑿齒論青`
- adjacent-boundary order: `ordered`; positions `{'previous': 4011, 'current': 4082, 'next': 4122}`

---

#### discrepancy-013 — 02-yanyu-076

- classification: `harmless_alignment_difference`; confidence: `high`
- source discrepancy: `unmatched_entry_opening`; source record index: `13`
- review reason: The same-edition witness locates the same opening in the current boundary order; differences are glyph templates or attested witness forms.
- recommended action: No repair in this task. Preserve the current canonical boundary and all witness spellings.
- canonical boundary: `02-yanyu-076` ordinal `76`, primary status `present`, anchor `支公好鶴住剡東&KR2192;山(㑹稽二百里/支公書曰山去)有人遺其`
- canonical source position: normalized line `1612`, source line `1555`, page `<pb:KR3l0002_SBCK_001-42b>`
- Kanripo SBCK: `present`; context: `> -->\n謝公云賢聖去人其間亦邇子姪未之許公歎曰若\n郗超聞此語必不至河漢(門支道林以為一時之俊/超别傳曰超精於理義沙)\n(無當徃而不反怪怖其言猶河漢而無極也/莊子曰肩吾問於連叔曰吾聞言於接輿大而)\n支公好鶴住剡東&KR2192;山(㑹稽二百里/支公書曰山去)有人遺其雙\n鶴少時翅長欲飛支意惜之乃鎩其翮鶴軒翥不復\n能飛乃反顧翅垂頭視之如有懊喪意林曰既有陵\n霄之姿何肻為人作耳目近玩養令翮成置使飛去\n謝中郎經曲阿後湖問左右此是何水(萬字萬石太/中興書曰謝)\n(部西中郎將豫州刺史散騎常侍/傅安弟也才氣髙俊蚤知名歴吏)荅曰曲阿湖(地記/六康)\n(其勢截其直道使其阿曲故曰曲阿也吴還為雲陽/曰曲阿本名雲陽秦始皇以有王氣鑿北阬山以敗)\n<!-- k`
- Wikisource SBCK: `located`; page `Page:Sibu Congkan0462-劉義慶-世説新語-3-1.djvu/93`; bounded reading: `支公好鶴住剡東𡵙山有人遺其`
- adjacent-boundary order: `ordered`; positions `{'previous': 4169, 'current': 4199, 'next': 4273}`

---

#### discrepancy-014 — 02-yanyu-079

- classification: `harmless_alignment_difference`; confidence: `high`
- source discrepancy: `unmatched_entry_opening`; source record index: `14`
- review reason: The same-edition witness locates the same opening in the current boundary order; differences are glyph templates or attested witness forms.
- recommended action: No repair in this task. Preserve the current canonical boundary and all witness spellings.
- canonical boundary: `02-yanyu-079` ordinal `79`, primary status `present`, anchor `謝胡兒語庾道季(道季太尉亮子也風情率悟以文/道季庾龢小字徐廣晉紀曰龢字)\n(丹陽尹兼中領軍/談致稱於時歷仕至)諸人莫當就`
- canonical source position: normalized line `1625`, source line `1568`, page `<pb:KR3l0002_SBCK_001-43a>`
- Kanripo SBCK: `present`; context: `弟車騎(也/玄)\n荅曰當由欲者不多而使與者忘少(玄字㓜度鎭西/謝車騎家傳曰)\n(燕集問武帝任山公以三事任以官人至於賜予不/奕第三子也神理明俊善微言叔父太傅嘗與子姪)\n(玄荅有辭致也/過斤合當有㫖不)\n謝胡兒語庾道季(道季太尉亮子也風情率悟以文/道季庾龢小字徐廣晉紀曰龢字)\n(丹陽尹兼中領軍/談致稱於時歷仕至)諸人莫當就卿談可堅城壘庾\n曰若文度來我以偏師待之康伯來濟河焚舟(傳曰/春秋)\n(舟杜預曰示必死/秦伯伐晉濟河焚)\n李弘度常歎不被遇(人也祖康父矩皆有美名充初/中興書曰李充字弘度江夏鄳)\n<!-- kanripo-page source-line=1574: <pb:KR3l0002_SBCK_001-43b> -->\n(求剡縣遷`
- Wikisource SBCK: `located`; page `Page:Sibu Congkan0462-劉義慶-世説新語-3-1.djvu/94`; bounded reading: `謝胡兒語⟦{{SKchar|2928}}⟧道季諸人莫當就`
- adjacent-boundary order: `ordered`; positions `{'previous': 4305, 'current': 4337, 'next': 4374}`

---

#### discrepancy-015 — 02-yanyu-080

- classification: `harmless_alignment_difference`; confidence: `high`
- source discrepancy: `unmatched_entry_opening`; source record index: `15`
- review reason: The same-edition witness locates the same opening in the current boundary order; differences are glyph templates or attested witness forms.
- recommended action: No repair in this task. Preserve the current canonical boundary and all witness spellings.
- canonical boundary: `02-yanyu-080` ordinal `80`, primary status `present`, anchor `李弘度常歎不被遇(人也祖康父矩皆有美名充初/中興書曰李充字弘度江夏鄳)\n`
- canonical source position: normalized line `1629`, source line `1572`, page `<pb:KR3l0002_SBCK_001-43a>`
- Kanripo SBCK: `present`; context: `亮子也風情率悟以文/道季庾龢小字徐廣晉紀曰龢字)\n(丹陽尹兼中領軍/談致稱於時歷仕至)諸人莫當就卿談可堅城壘庾\n曰若文度來我以偏師待之康伯來濟河焚舟(傳曰/春秋)\n(舟杜預曰示必死/秦伯伐晉濟河焚)\n李弘度常歎不被遇(人也祖康父矩皆有美名充初/中興書曰李充字弘度江夏鄳)\n<!-- kanripo-page source-line=1574: <pb:KR3l0002_SBCK_001-43b> -->\n(求剡縣遷大著作中書郎/辟丞相掾記室叅軍以貧)殷揚州(别見/殷浩)知其家貧問\n君能屈志百里不李荅曰北門之歎久已上聞(北門/衞詩)\n(得志也/刺仕不)窮猿奔林豈暇擇木遂授剡縣\n王司州至吳興印渚中看(齡琅邪臨沂人王廙之子/王胡之别傳曰胡之`
- Wikisource SBCK: `located`; page `Page:Sibu Congkan0462-劉義慶-世説新語-3-1.djvu/94`; bounded reading: `李⟦{{SKchar|2592}}⟧度常歎不被遇`
- adjacent-boundary order: `ordered`; positions `{'previous': 4337, 'current': 4374, 'next': 4420}`

---

#### discrepancy-016 — 02-yanyu-096

- classification: `harmless_alignment_difference`; confidence: `high`
- source discrepancy: `unmatched_entry_opening`; source record index: `16`
- review reason: The same-edition witness locates the same opening in the current boundary order; differences are glyph templates or attested witness forms.
- recommended action: No repair in this task. Preserve the current canonical boundary and all witness spellings.
- canonical boundary: `02-yanyu-096` ordinal `96`, primary status `present`, anchor `毛伯成既負其才氣常稱寧為`
- canonical source position: normalized line `1714`, source line `1657`, page `<pb:KR3l0002_SBCK_001-47a>`
- Kanripo SBCK: `present`; context: `甚被親暱/宋明帝文章志曰愷之)人問之曰卿慿重桓乃爾\n哭之狀其可見乎顧曰鼻如廣莫長風眼如懸河決\n溜(至廣莫者精大備也葢北風也一曰寒風/春秋考異郵曰距不周風四十五日廣莫風)或曰\n聲如震雷破山淚如傾河注海\n毛伯成既負其才氣常稱寧為蘭摧玉折不作蕭敷\n艾榮(潁川人仕至征西行軍叅軍/征西寮屬名曰毛玄字伯成)\n范寗作豫章(學通覽累遷中書郎豫章太守/中興書曰寗字武子慎陽縣人博)八日\n請佛有板衆僧疑或欲作荅有小沙彌在坐末曰世\n<!-- kanripo-page source-line=1662: <pb:KR3l0002_SBCK_001-47b> -->\n尊默然則為許可衆從其義\n司馬太傅齋中夜坐(帝第五子也封㑹稽王領司徒/孝文王傳曰王諱道子簡文皇)`
- Wikisource SBCK: `located`; page `Page:Sibu Congkan0462-劉義慶-世説新語-3-1.djvu/102`; bounded reading: `毛伯成既⟦{{SKchar|3688}}⟧其才氣常稱寧為`
- adjacent-boundary order: `ordered`; positions `{'previous': 5072, 'current': 5138, 'next': 5160}`

---

#### discrepancy-023 — missing_kanripo_passage

- classification: `harmless_alignment_difference`; confidence: `high`
- source discrepancy: `missing_kanripo_passage`; source record index: `23`
- review reason: The apparent missing passage is a chapter/edition-layout tail or witness markup difference; current entry order and count remain intact.
- recommended action: No repair in this task. Preserve current boundaries; treat the difference as annotation/layout evidence only.
- canonical chapter structure: `108` entries; gap ordinals `[]`; partial ordinals `[]`; ordinal continuity `True`
- Kanripo SBCK bounded record: `108` historical entries, `5870` main characters; context: `由聖德淵重厚地所以不能載時人善之桓玄既簒位將改置直舘問左右虎賁中郎省應在何處有人荅曰無省當時殊忤㫖問何以知無荅曰潘岳秋興賦敘曰余兼虎賁中郎將寓直散騎之省玄咨嗟稱善謝靈運好戴曲柄笠孔隱士謂曰卿欲希心髙逺何不能遺曲葢之貌謝荅曰將不畏影者未能忘懷`
- Wikisource SBCK bounded record: `5890` main characters; context: `由聖德淵重厚地所以不能載時人善之桓⟦{{SKchar|2593}}⟧既簒位將改置直舘問左右虎賁中郎省應在何處有人荅曰無省當時殊忤㫖問何以知無荅曰潘岳秋興賦敘曰余兼虎賁中郎將寓直散騎之省⟦{{SKchar|2593}}⟧咨嗟稱善謝靈運好戴曲柄笠孔𨼆士謂曰卿欲希心髙逺何不能遺曲葢之貌謝荅曰將不畏影者未能忘懷世說新語巻上之上宋臨川王義慶撰梁劉孝標注`
- comparison metrics: sequence ratio `0.990306`, length delta `20`, annotation delta `9`

---

### 03-zhengshi — 政事第三

#### discrepancy-024 — 03-zhengshi-003

- classification: `harmless_alignment_difference`; confidence: `high`
- source discrepancy: `unmatched_entry_opening`; source record index: `24`
- review reason: The same-edition witness locates the same opening in the current boundary order; differences are glyph templates or attested witness forms.
- recommended action: No repair in this task. Preserve the current canonical boundary and all witness spellings.
- canonical boundary: `03-zhengshi-003` ordinal `3`, primary status `present`, anchor `陳元方年十一時(已見/陳紀)候袁公袁公`
- canonical source position: normalized line `1808`, source line `1751`, page `<pb:KR3l0002_SBCK_001-51b>`
- Kanripo SBCK: `present`; context: `anripo-page source-line=1749: <pb:KR3l0002_SBCK_001-51b> -->\n大宜先按討仲弓曰盗殺財主何如骨肉相殘(漢時/按後)\n(不聞寔也/賈彪有此事)\n陳元方年十一時(已見/陳紀)候袁公袁公問曰賢家君在\n太丘逺近稱之何所履行元方曰老父在太丘彊者\n綏之以徳弱者撫之以仁恣其所安乆而益敬(漢紀/袁宏)\n(嚴而治百姓敬之/曰寔為太丘其政不)袁公曰孤徃者嘗為鄴令正行\n此事不知卿家君法孤孤法卿父(公未知誰為鄴令/檢衆漢書袁氏諸)\n(待通識者/故闕其文以)元方曰周公孔子異世而出周旋動靜\n萬里如一周公不師孔子孔子亦不師周公\n賀太傅作吳郡初不出門吳中諸强族輕之乃題府\n<!-- kanripo-page `
- Wikisource SBCK: `located`; page `Page:Sibu Congkan0462-劉義慶-世説新語-3-1.djvu/111`; bounded reading: `陳元方年十一時𠉀袁公袁公`
- adjacent-boundary order: `ordered`; positions `{'previous': 59, 'current': 117, 'next': 230}`

---

#### discrepancy-025 — 03-zhengshi-012

- classification: `harmless_alignment_difference`; confidence: `high`
- source discrepancy: `unmatched_entry_opening`; source record index: `25`
- review reason: The same-edition witness locates the same opening in the current boundary order; differences are glyph templates or attested witness forms.
- recommended action: No repair in this task. Preserve the current canonical boundary and all witness spellings.
- canonical boundary: `03-zhengshi-012` ordinal `12`, primary status `present`, anchor `王丞相拜揚州賓客數百人並`
- canonical source position: normalized line `1884`, source line `1827`, page `<pb:KR3l0002_SBCK_001-55a>`
- Kanripo SBCK: `present`; context: `是欲并宥之事奏帝曰讓是殺我侍中\n<!-- kanripo-page source-line=1826: <pb:KR3l0002_SBCK_001-55a> -->\n者不可宥諸公以少主不可違并斬二人\n王丞相拜揚州賓客數百人並加霑接人人有説色\n唯有臨海一客姓任(官在都預王公坐/語林曰任名顒時)及數胡人為\n未洽公因便還到過任邊云君出臨海便無復人任\n大喜說因過胡人前弹指云蘭闍蘭闍羣胡同笑四\n坐並懽(常賔一見多輸寫欵誠自謂為導所遇同之/晉陽秋曰王導接誘應㑹少有牾者雖疎交)\n(暱/舊)\n陸太尉詣王丞相咨事過後輙翻異王公怪其如此\n後以問陸(英仕郡有譽玩器量淹雅累遷侍中尚書/陸玩别傳曰玩字士瑶吴郡吴人祖瑁父)\n(令贈太尉/左僕射尚書)陸曰公長民短`
- Wikisource SBCK: `located`; page `Page:Sibu Congkan0462-劉義慶-世説新語-3-1.djvu/118`; bounded reading: `王丞相拜⟦{{SKchar|3951}}⟧州賓客數百人並`
- adjacent-boundary order: `ordered`; positions `{'previous': 596, 'current': 702, 'next': 778}`

---

#### discrepancy-027 — 03-zhengshi-022

- classification: `harmless_alignment_difference`; confidence: `high`
- source discrepancy: `unmatched_entry_opening`; source record index: `27`
- review reason: The same-edition witness locates the same opening in the current boundary order; differences are glyph templates or attested witness forms.
- recommended action: No repair in this task. Preserve the current canonical boundary and all witness spellings.
- canonical boundary: `03-zhengshi-022` ordinal `22`, primary status `present`, anchor `殷浩始作揚州(識濮陽相父羡光禄勲浩少有重名/浩别傳曰浩字淵源陳郡長平人祖)\n(弟何充等相尋薨太宗以撫軍輔政徵浩為揚州從/仕至揚州刺史中軍將軍中興書曰建元初庾亮兄)\n(也/民譽)劉尹行日小欲`
- canonical source position: normalized line `1944`, source line `1887`, page `<pb:KR3l0002_SBCK_001-57b>`
- Kanripo SBCK: `present`; context: `王長史就簡文索東陽云承藉猛政故\n可以和靜致治(徒父簡儀同三司遐歴武陵王友東/東陽記云遐字彦林河内人祖濤司)\n(内苦之惇隱東陽以仁恕懐物遐感其徳為㣲損威猛/陽太守江惇傳曰山遐為東陽風政嚴苛多任刑殺郡)\n殷浩始作揚州(識濮陽相父羡光禄勲浩少有重名/浩别傳曰浩字淵源陳郡長平人祖)\n(弟何充等相尋薨太宗以撫軍輔政徵浩為揚州從/仕至揚州刺史中軍將軍中興書曰建元初庾亮兄)\n(也/民譽)劉尹行日小欲晚便使左右取襆人問其故荅\n曰刺史嚴不敢夜行\n<!-- kanripo-page source-line=1892: <pb:KR3l0002_SBCK_001-58a> -->\n謝公時兵厮逋亡多近竄南塘下諸舫中或欲求一\n時&KR0679;索謝公不許云若`
- Wikisource SBCK: `located`; page `Page:Sibu Congkan0462-劉義慶-世説新語-3-1.djvu/123`; bounded reading: `殷浩始作⟦{{SKchar|3951}}⟧州劉尹行日小欲`
- adjacent-boundary order: `ordered`; positions `{'previous': 1271, 'current': 1297, 'next': 1329}`

---

#### discrepancy-028 — major_length_difference

- classification: `textual_difference_not_structural`; confidence: `medium`
- source discrepancy: `major_length_difference`; source record index: `28`
- review reason: The same-edition contexts are aligned and the length delta is explained by witness glyph/template or wording differences, not a new entry boundary.
- recommended action: No repair in this task. Preserve current boundaries; treat the difference as annotation/layout evidence only.
- canonical chapter structure: `26` entries; gap ordinals `[]`; partial ordinals `[]`; ordinal continuity `True`
- Kanripo SBCK bounded record: `26` historical entries, `1509` main characters; context: `竹皆令録厚頭積之如山後桓宣武伐蜀裝船悉以作釘又云嘗發所在竹篙有一官長連根取之仍當足乃超兩階用之何驃騎作㑹稽虞存弟謇作郡主簿以何見客勞損欲白斷常客使家人節量擇可通者作白事成以見存存時為何上佐正與謇共食語云白事甚好待我食畢作教食竟取筆題白事後云若得門庭長如郭林宗者當如所白汝何處得此人謇於是止王劉與林公共㸔何驃騎驃騎㸔文書不顧之王謂何曰我今故與林公來相㸔望卿擺撥常務應對玄言那得方低頭㸔此邪何曰我不㸔此卿等何以得存諸人以為佳桓公在荆州全欲以徳被江漢恥以威刑肅物令史受杖正從朱衣上過桓式年少從外來云向從閣下過見令史受杖上捎雲根下拂地足意譏不著桓公云我猶患其重簡文為相事動經年然後得過桓公甚患其遲常加勸勉太宗曰一日萬幾那得速山遐去東陽王長史就簡文索東陽云承藉猛政故可以和靜致治殷浩始作揚州`
- Wikisource SBCK bounded record: `1541` main characters; context: `竹皆令録厚頭積之如山後桓宣武伐蜀裝船悉以作釘又云嘗發所在竹篙有一官長連根取之仍當足乃超兩階用之何驃騎作㑹稽虞存弟謇作郡主簿以何見客勞損欲白斷常客使家人節量擇可通者作白事成以見存存時為何上佐正與謇共食語云白事甚好待我食畢作教食竟取筆題白事後云⟦{{SKchar2|590}}⟧得門庭長如郭林宗者當如所白汝何處得此人謇於是止王劉與林公共㸔何驃騎驃騎㸔文書不顧之王謂何曰我今故與林公來相㸔望卿擺撥常務應對𤣥言那得方低頭㸔此邪何曰我不㸔此卿等何以得存諸人以為佳桓公在荆州全欲以徳被江漢恥以威刑肅物令史受杖正從朱衣上過桓式年少從外來云向從閣下過見令史受杖上捎雲根下拂地足意譏不著桓公云我猶患其重簡文為相事動經年然後得過桓公甚患其遲常加勸勉太宗曰一日萬幾那得速山遐去東陽王長史就簡文索東陽云承`
- comparison metrics: sequence ratio `0.982295`, length delta `32`, annotation delta `1`

---

### 04-wenxue — 文學第四

#### discrepancy-029 — 04-wenxue-001

- classification: `harmless_alignment_difference`; confidence: `high`
- source discrepancy: `unmatched_entry_opening`; source record index: `29`
- review reason: The same-edition witness locates the same opening in the current boundary order; differences are glyph templates or attested witness forms.
- recommended action: No repair in this task. Preserve the current canonical boundary and all witness spellings.
- canonical boundary: `04-wenxue-001` ordinal `1`, primary status `present`, anchor `鄭玄在馬融門下(人少而好問學無常師大将軍鄧/融自敘曰融字季長右扶風茂陵)\n`
- canonical source position: normalized line `1969`, source line `1913`, page `<pb:KR3l0002_SBCK_001-58b>`
- Kanripo SBCK: `present`; context: `　　　文學第四\n鄭玄在馬融門下(人少而好問學無常師大将軍鄧/融自敘曰融字季長右扶風茂陵)\n<!-- kanripo-page source-line=1914: <pb:KR3l0002_SBCK_001-59a> -->\n(以謂古人有言左手據天下之圗而右手刎其喉愚/騭召為舎人棄逰武都㑹羗虜起自闗以西道㫁融)\n(無限之身哉因往應之為校書郎出為南郡太守/夫不為何則生貴於天下也豈以曲俗咫尺為羞滅)\n三年不得相見髙足弟子傳授而已嘗筭渾天不合\n諸弟子莫能解或言`
- Wikisource SBCK: `located`; page `Page:Sibu Congkan0462-劉義慶-世説新語-3-1.djvu/125`; bounded reading: `鄭⟦{{SKchar|2593}}⟧在馬融門下`
- adjacent-boundary order: `partially_ordered`; positions `{'previous': None, 'current': 0, 'next': 119}`

---

#### discrepancy-030 — 04-wenxue-002

- classification: `harmless_alignment_difference`; confidence: `high`
- source discrepancy: `unmatched_entry_opening`; source record index: `30`
- review reason: The same-edition witness locates the same opening in the current boundary order; differences are glyph templates or attested witness forms.
- recommended action: No repair in this task. Preserve the current canonical boundary and all witness spellings.
- canonical boundary: `04-wenxue-002` ordinal `2`, primary status `present`, anchor `鄭玄欲注春秋傳尚未成時行`
- canonical source position: normalized line `1990`, source line `1933`, page `<pb:KR3l0002_SBCK_001-59b>`
- Kanripo SBCK: `present`; context: `玄擅名而心忌\n焉玄亦疑有追乃坐橋下在水上據屐融果轉式逐\n之告左右曰玄在土下水上而據木此必死矣遂罷\n追玄竟以得免(門人親傳其業何猜忌而行鴆毒乎/馬融海内大儒被服仁義鄭玄名列)\n(夫人之子/委巷之言賊)\n鄭玄欲注春秋傳尚未成時行與服子慎遇宿客舎\n先未相識服在外車上與人說已注傳意(服䖍字子/漢南紀曰)\n<!-- kanripo-page source-line=1936: <pb:KR3l0002_SBCK_001-60a> -->\n(氏傳為作訓解舉孝廉為尚書郎九江太守/慎河南滎陽人少行清苦為諸生尤明春秋左)玄聽\n之良乆多與己同玄就車與語曰吾乆欲注尚未了\n聽君向言多與吾同今當盡以所注與君遂為服氏\n注鄭玄家奴婢皆讀書嘗使一婢不稱㫖將撻之方\n`
- Wikisource SBCK: `located`; page `Page:Sibu Congkan0462-劉義慶-世説新語-3-1.djvu/127`; bounded reading: `鄭⟦{{SKchar|2593}}⟧欲注春秋⟦{{SKchar|2652}}⟧尚未成時行`
- adjacent-boundary order: `ordered`; positions `{'previous': 0, 'current': 119, 'next': 198}`

---

#### discrepancy-035 — 04-wenxue-060

- classification: `harmless_alignment_difference`; confidence: `high`
- source discrepancy: `unmatched_entry_opening`; source record index: `35`
- review reason: The same-edition witness locates the same opening in the current boundary order; differences are glyph templates or attested witness forms.
- recommended action: No repair in this task. Preserve the current canonical boundary and all witness spellings.
- canonical boundary: `04-wenxue-060` ordinal `60`, primary status `present`, anchor `殷仲堪精覈玄論人謂莫不研`
- canonical source position: normalized line `2365`, source line `2308`, page `<pb:KR3l0002_SBCK_001-76b>`
- Kanripo SBCK: `present`; context: `謂卵有毛雞三足馬有卵犬可為羊火不熱目不)\n(葢辯者之囿也/口不能服人之心)\n殷中軍被廢徙東陽大讀佛經皆精解唯至事數處\n不解(二因縁五根五力七覺之聲/事數謂若五隂十二入四諦十)遇見一道人問\n所籖便釋然\n殷仲堪精覈玄論人謂莫不研究殷乃歎曰使我解\n<!-- kanripo-page source-line=2310: <pb:KR3l0002_SBCK_001-77a> -->\n四本談不翅爾(好學而有理思也/周祗隆安記曰仲堪)\n殷荆州曾問逺公(門樓煩人本姓賈氏世為冠族年/張野逺法師銘曰沙門釋惠逺鴈)\n(宣子學道阻不通遇釋道安以為師抽簮落髮研求/十二隨舅令狐氏逰學許洛年二十一欲南渡就范)\n(安常歎曰道流東國其在逺乎㐮陽既沒振錫南逰/法藏釋曇`
- Wikisource SBCK: `located`; page `Page:Sibu Congkan0462-劉義慶-世説新語-3-1.djvu/161`; bounded reading: `殷仲堪精覈⟦{{SKchar|2593}}⟧論人謂莫不研`
- adjacent-boundary order: `ordered`; positions `{'previous': 3816, 'current': 3849, 'next': 3875}`

---

#### discrepancy-036 — 04-wenxue-077

- classification: `harmless_alignment_difference`; confidence: `high`
- source discrepancy: `unmatched_entry_opening`; source record index: `36`
- review reason: The same-edition witness locates the same opening in the current boundary order; differences are glyph templates or attested witness forms.
- recommended action: No repair in this task. Preserve the current canonical boundary and all witness spellings.
- canonical boundary: `04-wenxue-077` ordinal `77`, primary status `present`, anchor `庾闡始作揚都賦道温庾云温`
- canonical source position: normalized line `2482`, source line `2425`, page `<pb:KR3l0002_SBCK_001-82a>`
- Kanripo SBCK: `present`; context: `穨索縱情)\n(害王敦取為叅軍敦縱兵都輦乃咨以大事璞極言/斧也璞曰吾所受有分恒恐用之不盡豈酒色之能)\n(害之詩璞幽思篇者/成敗不為回屈敦忌而)阮孚云(别見/阮孚)泓崢蕭瑟實不\n可言每讀此文輒覺神超形越\n庾闡始作揚都賦道温庾云温挺義之標庾作民之\n望方響則金聲比德則玉亮庾公聞賦成求㸔兼贈\n貺之闡更改望為儁以亮為潤云(初潁川人太尉亮/中興書曰闡字仲)\n(領大著作為揚都賦邈絶當時五十四卒/之族也少孤九嵗便能屬文遷散騎侍郎)\n孫興公作庾公誄袁羊曰見此張緩于時以為名賞\n<!-- kanripo-page source-line=2431: <pb:KR3l0002_SBCK_001-82b> -->\n(喬有文才/袁氏家傳曰)\n庾仲初作揚都賦成以呈`
- Wikisource SBCK: `located`; page `Page:Sibu Congkan0462-劉義慶-世説新語-3-1.djvu/172`; bounded reading: `⟦{{SKchar|2928}}⟧闡始作⟦{{SKchar|3951}}⟧都賦道温⟦{{SKchar|2928}}⟧云温`
- adjacent-boundary order: `ordered`; positions `{'previous': 4629, 'current': 4663, 'next': 4716}`

---

#### discrepancy-037 — 04-wenxue-078

- classification: `harmless_alignment_difference`; confidence: `high`
- source discrepancy: `unmatched_entry_opening`; source record index: `37`
- review reason: The same-edition witness locates the same opening in the current boundary order; differences are glyph templates or attested witness forms.
- recommended action: No repair in this task. Preserve the current canonical boundary and all witness spellings.
- canonical boundary: `04-wenxue-078` ordinal `78`, primary status `present`, anchor `孫興公作庾公誄袁羊曰見此`
- canonical source position: normalized line `2486`, source line `2429`, page `<pb:KR3l0002_SBCK_001-82a>`
- Kanripo SBCK: `present`; context: `庾云温挺義之標庾作民之\n望方響則金聲比德則玉亮庾公聞賦成求㸔兼贈\n貺之闡更改望為儁以亮為潤云(初潁川人太尉亮/中興書曰闡字仲)\n(領大著作為揚都賦邈絶當時五十四卒/之族也少孤九嵗便能屬文遷散騎侍郎)\n孫興公作庾公誄袁羊曰見此張緩于時以為名賞\n<!-- kanripo-page source-line=2431: <pb:KR3l0002_SBCK_001-82b> -->\n(喬有文才/袁氏家傳曰)\n庾仲初作揚都賦成以呈庾亮亮以親族之懷大為\n其名價云可三二京四三都於此人人競寫都下紙\n為之貴謝太傅云不得爾此是屋下架屋耳事事擬\n學而不免儉狹(非益也是以古人謂其屋下架屋/王隱論楊雄太玄經曰玄經雖妙)\n習鑿齒史才不常宣武甚器之未三十便用為荆州`
- Wikisource SBCK: `located`; page `Page:Sibu Congkan0462-劉義慶-世説新語-3-1.djvu/172`; bounded reading: `孫興公作⟦{{SKchar|2928}}⟧公誄袁羊曰見此`
- adjacent-boundary order: `ordered`; positions `{'previous': 4663, 'current': 4716, 'next': 4736}`

---

#### discrepancy-038 — 04-wenxue-079

- classification: `harmless_alignment_difference`; confidence: `high`
- source discrepancy: `unmatched_entry_opening`; source record index: `38`
- review reason: The same-edition witness locates the same opening in the current boundary order; differences are glyph templates or attested witness forms.
- recommended action: No repair in this task. Preserve the current canonical boundary and all witness spellings.
- canonical boundary: `04-wenxue-079` ordinal `79`, primary status `present`, anchor `庾仲初作揚都賦成以呈庾亮`
- canonical source position: normalized line `2489`, source line `2432`, page `<pb:KR3l0002_SBCK_001-82b>`
- Kanripo SBCK: `present`; context: `興公作庾公誄袁羊曰見此張緩于時以為名賞\n<!-- kanripo-page source-line=2431: <pb:KR3l0002_SBCK_001-82b> -->\n(喬有文才/袁氏家傳曰)\n庾仲初作揚都賦成以呈庾亮亮以親族之懷大為\n其名價云可三二京四三都於此人人競寫都下紙\n為之貴謝太傅云不得爾此是屋下架屋耳事事擬\n學而不免儉狹(非益也是以古人謂其屋下架屋/王隱論楊雄太玄經曰玄經雖妙)\n習鑿齒史才不常宣武甚器之未三十便用為荆州\n治中鑿齒謝牋亦云不遇明公荆州老從事耳後至\n都見簡文返命宣武問見相王何如荅云一生不曽\n見此人從此忤㫖出為衡陽郡性理遂錯於病中猶\n作漢晉春秋品評卓逸(才情秀逸温甚奇之自州從/續晉陽秋曰鑿齒少而博學)\n<!`
- Wikisource SBCK: `located`; page `Page:Sibu Congkan0462-劉義慶-世説新語-3-1.djvu/173`; bounded reading: `⟦{{SKchar|2928}}⟧仲初作⟦{{SKchar|3951}}⟧都賦成以呈⟦{{SKchar|2928}}⟧亮`
- adjacent-boundary order: `ordered`; positions `{'previous': 4716, 'current': 4736, 'next': 4802}`

---

#### discrepancy-039 — 04-wenxue-082

- classification: `harmless_alignment_difference`; confidence: `high`
- source discrepancy: `unmatched_entry_opening`; source record index: `39`
- review reason: The same-edition witness locates the same opening in the current boundary order; differences are glyph templates or attested witness forms.
- recommended action: No repair in this task. Preserve the current canonical boundary and all witness spellings.
- canonical boundary: `04-wenxue-082` ordinal `82`, primary status `present`, anchor `謝太傅問主簿陸退(祖凱吴丞相祖仰吏部郎父伊/陸氏譜曰退字黎民吴郡人髙)\n(至光禄大夫/州主簿退仕)張憑何以`
- canonical source position: normalized line `2505`, source line `2448`, page `<pb:KR3l0002_SBCK_001-83a>`
- Kanripo SBCK: `present`; context: `不足有静亂之功則孫劉鼎立共王秦政猶不見敘)\n(必自係於周不推吳楚也况長轡廟堂吴蜀兩定天/無所承魏之迹矣春秋之時吴楚稱王若推有徳彼)\n(功也/下之)\n孫興公云三都二京五經鼓吹(經典之羽翼/言此五賦是)\n謝太傅問主簿陸退(祖凱吴丞相祖仰吏部郎父伊/陸氏譜曰退字黎民吴郡人髙)\n(至光禄大夫/州主簿退仕)張憑何以作母誄而不作父誄退荅曰\n故當是丈夫之徳表於事行婦人之美非誄不顯(氏/陸)\n(憑壻也/譜曰退)\n<!-- kanripo-page source-line=2453: <pb:KR3l0002_SBCK_001-83b> -->\n王敬仁年十三作賢人論長史送示眞長眞長荅云\n見敬仁所作論便足參微言(稱賢人黃裳元吉茍未/脩集載其論曰或問易)`
- Wikisource SBCK: `located`; page `Page:Sibu Congkan0462-劉義慶-世説新語-3-1.djvu/174`; bounded reading: `謝太傅問主簿陸𨓆張憑何以`
- adjacent-boundary order: `ordered`; positions `{'previous': 4891, 'current': 4903, 'next': 4945}`

---

#### discrepancy-040 — 04-wenxue-085

- classification: `harmless_alignment_difference`; confidence: `high`
- source discrepancy: `unmatched_entry_opening`; source record index: `40`
- review reason: The same-edition witness locates the same opening in the current boundary order; differences are glyph templates or attested witness forms.
- recommended action: No repair in this task. Preserve the current canonical boundary and all witness spellings.
- canonical boundary: `04-wenxue-085` ordinal `85`, primary status `present`, anchor `簡文稱許掾云玄度五言詩可`
- canonical source position: normalized line `2518`, source line `2461`, page `<pb:KR3l0002_SBCK_001-83b>`
- Kanripo SBCK: `present`; context: `公云潘文爛若披錦無處不善(爲文選言簡章/續文章志曰岳)\n(絶倫/清綺)陸文若排沙簡金徃徃見寶(文司空張華見其/文章傳曰機善屬)\n(之作文患於不才至子爲文乃患太多也/文章篇篇稱善猶譏其作文大冶謂曰人)\n簡文稱許掾云玄度五言詩可謂妙絶時人(秋曰詢/續晉陽)\n(頌皆體則詩騷傍綜百家之言及至建安而詩章大/有才藻善屬文自司馬相如王褒揚雄諸賢世尚賦)\n<!-- kanripo-page source-line=2464: <pb:KR3l0002_SBCK_001-84a> -->\n(異也正始中王弼何晏好莊老玄勝之談而世遂貴/盛逮乎西朝之末潘陸之徒雖時有質文而宗歸不)\n(而韻之詢及太原孫綽轉相祖尚又加以三世之辭/焉至過江佛理尤盛故郭璞五言始㑹合`
- Wikisource SBCK: `located`; page `Page:Sibu Congkan0462-劉義慶-世説新語-3-1.djvu/175`; bounded reading: `簡文稱許⟦{{SKchar|3044}}⟧云⟦{{SKchar|2593}}⟧度五言詩可`
- adjacent-boundary order: `ordered`; positions `{'previous': 4976, 'current': 5001, 'next': 5018}`

---

#### discrepancy-041 — 04-wenxue-094

- classification: `harmless_alignment_difference`; confidence: `high`
- source discrepancy: `unmatched_entry_opening`; source record index: `41`
- review reason: The same-edition witness locates the same opening in the current boundary order; differences are glyph templates or attested witness forms.
- recommended action: No repair in this task. Preserve the current canonical boundary and all witness spellings.
- canonical boundary: `04-wenxue-094` ordinal `94`, primary status `present`, anchor `袁彦伯作名士傳成(為正始名士阮嗣宗嵇叔夜山/宏以夏侯太初何平叔王輔嗣)\n(叔則樂彦輔王夷甫庾子嵩王安期阮千里衛叔寳/巨源向子期劉伯倫阮仲容王濬仲為竹林名士裴)\n(中朝名士/謝㓜輿為)見謝公公`
- canonical source position: normalized line `2565`, source line `2508`, page `<pb:KR3l0002_SBCK_001-86a>`
- Kanripo SBCK: `present`; context: `邦國籍也負之者賤隷人也/子式負版者鄭氏注曰版謂)非無文采酷無裁製\n<!-- kanripo-page source-line=2508: <pb:KR3l0002_SBCK_001-86a> -->\n袁彦伯作名士傳成(為正始名士阮嗣宗嵇叔夜山/宏以夏侯太初何平叔王輔嗣)\n(叔則樂彦輔王夷甫庾子嵩王安期阮千里衛叔寳/巨源向子期劉伯倫阮仲容王濬仲為竹林名士裴)\n(中朝名士/謝㓜輿為)見謝公公笑曰我嘗與諸人道江北事特\n作狡獪耳彦伯遂以箸書\n王東亭到桓公吏既伏閣下桓令人竊取其白事東\n亭即於閣下更作無復向一字(涉通敏文髙當世/續晉陽秋曰珣學)\n桓宣武北征(四年上疏自征鮮卑/温别傳曰温以太和)袁虎時從被責免\n官㑹須露布文喚袁倚馬前令作手不輟筆俄`
- Wikisource SBCK: `located`; page `Page:Sibu Congkan0462-劉義慶-世説新語-3-1.djvu/180`; bounded reading: `袁彦伯作名士⟦{{SKchar|2652}}⟧成見謝公公`
- adjacent-boundary order: `ordered`; positions `{'previous': 5334, 'current': 5361, 'next': 5395}`

---

#### discrepancy-046 — major_length_difference

- classification: `textual_difference_not_structural`; confidence: `medium`
- source discrepancy: `major_length_difference`; source record index: `46`
- review reason: The same-edition contexts are aligned and the length delta is explained by witness glyph/template or wording differences, not a new entry boundary.
- recommended action: No repair in this task. Preserve current boundaries; treat the difference as annotation/layout evidence only.
- canonical chapter structure: `104` entries; gap ordinals `[]`; partial ordinals `[]`; ordinal continuity `True`
- Kanripo SBCK bounded record: `104` historical entries, `5819` main characters; context: `是想邪樂云因也未嘗夢乘車入䑕穴擣&KR1366;噉鐡杵皆無想無因故也衛思因經日不得遂成病樂聞故命駕為剖析之衛即小差樂歎曰此兒胷中當必無膏肓之疾庾子嵩讀荘子開卷一尺許便放去曰了不異人意客問樂令㫖不至者樂亦不復剖析文句直以麈尾柄确几曰至不客曰至樂因又舉麈尾曰若至者那得去於是客乃悟服樂辭約而㫖達皆此類初注荘子者數十家莫能究其㫖要向秀於舊注外為解義妙析奇致大畼玄風唯秋水至樂二篇未竟而秀卒秀子㓜義遂零落然猶有别本郭象者為人薄行有儁才見秀義不傳於世遂竊以為已注乃自注秋水至樂二篇又易馬蹄一篇其餘衆篇或定㸃文句而已後秀義别本出故今有向郭二莊其義一也阮宣子有令聞太尉王夷甫見而問曰老莊與聖教同異對曰將無同太尉善其言辟之爲掾世謂三語掾衛玠嘲之曰一言可辟何假於三宣子曰茍是天下人望亦可無言而辟復何假一遂相與爲友`
- Wikisource SBCK bounded record: `5879` main characters; context: `是想邪樂云因也未嘗夢乘車入䑕穴擣𩐎噉鐡杵皆無想無因故也衛思因經日不得遂成病樂聞故命駕為剖析之衛即小差樂歎曰此兒胷中當必無膏肓之疾庾子嵩讀荘子開卷一尺許便放去曰了不異人意客問樂令㫖不至者樂亦不復剖析文句直以麈尾柄确几曰至不客曰至樂因又舉麈尾曰⟦{{SKchar2|590}}⟧至者那得去於是客乃悟服樂辭約而㫖達皆此⟦{{SKchar|3892}}⟧初注荘子者數十家莫能究其㫖要向秀於舊注外為⟦{{SKchar|3660}}⟧義妙析奇致大畼⟦{{SKchar|2593}}⟧風唯秋水至樂二篇未竟而秀卒秀子㓜義遂零落然猶有别本郭象者為人薄行有儁才見秀義不⟦{{SKchar|2652}}⟧於世遂竊以為已注乃自注秋水至樂二篇又易馬蹄一篇其餘衆篇或定㸃文句而已後秀義别本出故今有向郭二莊其義一也阮宣子有令聞太尉王夷甫見而問曰老莊與…`
- comparison metrics: sequence ratio `0.981364`, length delta `60`, annotation delta `6`

---

### 05-fangzheng — 方正第五

#### discrepancy-047 — 05-fangzheng-019

- classification: `harmless_alignment_difference`; confidence: `high`
- source discrepancy: `unmatched_entry_opening`; source record index: `47`
- review reason: The same-edition witness locates the same opening in the current boundary order; differences are glyph templates or attested witness forms.
- recommended action: No repair in this task. Preserve the current canonical boundary and all witness spellings.
- canonical boundary: `05-fangzheng-019` ordinal `19`, primary status `present`, anchor `羊忱性甚貞烈趙王倫爲相國`
- canonical source position: normalized line `259`, source line `203`, page `<pb:KR3l0002_SBCK_002-11b>`
- Kanripo SBCK: `present`; context: `末可)\n(强也即字温休温休葢幽婚也其兆先彰矣兒遂成/充貌姨曰我舅甥三月末間産父曰春煗温也願休)\n(漢尚書植子毓爲魏司空冠葢相承至今也/爲令噐歷數郡二千石皆箸績其後生植爲)議者疑\n二陸優劣謝公以此定之\n羊忱性甚貞烈趙王倫爲相國忱爲太傅長史乃版\n以參相國軍事使者卒至忱深懼豫禍不暇被馬於\n是帖騎而避使者追之忱善射矢左右發使者不敢\n進遂得免(世爲冠族父繇車騎掾忱歷太傅長史揚/文字志曰忱字長和一名陶泰山平陽人)\n(年遭亂被害年五十餘/州刺史遷侍中永嘉五)\n王太尉不與庾子嵩交(庾敱/王夷甫)庾卿之不置王曰君\n<!-- kanripo-page source-line=209: <pb:KR3l0002_SBCK_002-12a> -->\n不得爲`
- Wikisource SBCK: `located`; page `Page:Sibu Congkan0463-劉義慶-世説新語-3-2.djvu/21`; bounded reading: `羊忱性甚貞烈趙王倫爲相國`
- adjacent-boundary order: `ordered`; positions `{'previous': 1323, 'current': 1402, 'next': 1466}`

---

#### discrepancy-048 — 05-fangzheng-021

- classification: `harmless_alignment_difference`; confidence: `high`
- source discrepancy: `unmatched_entry_opening`; source record index: `48`
- review reason: The same-edition witness locates the same opening in the current boundary order; differences are glyph templates or attested witness forms.
- recommended action: No repair in this task. Preserve the current canonical boundary and all witness spellings.
- canonical boundary: `05-fangzheng-021` ordinal `21`, primary status `present`, anchor `阮宣子伐社樹(勾龍爲后土后土爲社風俗通曰孝/阮修巳見春秋傳曰共工氏有子曰)\n(而祀之報功也然則社自祀勾龍非土之祭也/經稱社者土也廣博不可備敬故風士以爲社)有人\n止之宣子`
- canonical source position: normalized line `268`, source line `212`, page `<pb:KR3l0002_SBCK_002-12a>`
- Kanripo SBCK: `present`; context: `卿之不置王曰君\n<!-- kanripo-page source-line=209: <pb:KR3l0002_SBCK_002-12a> -->\n不得爲爾庾曰卿自君我我自卿卿我自用我法卿\n自用卿法\n阮宣子伐社樹(勾龍爲后土后土爲社風俗通曰孝/阮修巳見春秋傳曰共工氏有子曰)\n(而祀之報功也然則社自祀勾龍非土之祭也/經稱社者土也廣博不可備敬故風士以爲社)有人\n止之宣子曰社而爲樹伐樹則社亡樹而爲社伐樹\n則社移矣\n阮宣子論鬼神有無者或以人死有鬼宣子獨以爲\n無曰今見鬼者云箸生時衣服若人死有鬼衣服復\n有鬼邪(知不能害人如審鬼者死人精神人見之宜/論衡曰世謂人死爲鬼非也人死不爲鬼無)\n(由此言之見衣服象人則形體亦象人象人知非死/從裸袒之形無爲見衣`
- Wikisource SBCK: `located`; page `Page:Sibu Congkan0463-劉義慶-世説新語-3-2.djvu/22`; bounded reading: `阮宣子伐社樹有人止之宣子`
- adjacent-boundary order: `ordered`; positions `{'previous': 1466, 'current': 1507, 'next': 1539}`

---

#### discrepancy-051 — 05-fangzheng-036

- classification: `harmless_alignment_difference`; confidence: `high`
- source discrepancy: `unmatched_entry_opening`; source record index: `51`
- review reason: The same-edition witness locates the same opening in the current boundary order; differences are glyph templates or attested witness forms.
- recommended action: No repair in this task. Preserve the current canonical boundary and all witness spellings.
- canonical boundary: `05-fangzheng-036` ordinal `36`, primary status `present`, anchor `蘇峻時孔羣在横塘爲匡術所`
- canonical source position: normalized line `378`, source line `322`, page `<pb:KR3l0002_SBCK_002-17a>`
- Kanripo SBCK: `present`; context: `0002_SBCK_002-17a> -->\n(許之士貞子諫而止後林父敗赤狄于曲梁賞桓子/救鄭與楚戰於邲晉師敗績桓子歸請死晉平公將)\n(獲狄田子之功也微子吾䘮伯氏矣/狄臣子室亦賞士伯以瓜衍之田曰吾)\n蘇峻時孔羣在横塘爲匡術所逼王丞相保存術(稽/㑹)\n(父弈全椒令羣有智局仕至御史中丞晉陽秋曰匡/後賢記曰羣字敬休會稽山隂人祖笁吳豫章太守)\n(勸峻誅亮遂與峻同反後以宛城降/術爲阜陵令逃亡無行庾亮徵蘇峻術)因衆坐戲語\n令術勸羣酒以釋横塘之憾羣荅曰德非孔子厄同\n匡人(奮㦸將戰孔子止之曰夫詩書之不講禮樂之/家語曰孔子之宋匡簡子以甲士圍之子路怒)\n(也命也夫歌予和汝子路彈劒孔子和之曲三終匡/不習是丘之過也若述先王之道而爲咎者非丘罪)\n(甲罷/人解`
- Wikisource SBCK: `located`; page `Page:Sibu Congkan0463-劉義慶-世説新語-3-2.djvu/32`; bounded reading: `蘇峻時孔羣在横塘爲匡術所`
- adjacent-boundary order: `ordered`; positions `{'previous': 2598, 'current': 2650, 'next': 2713}`

---

#### discrepancy-052 — 05-fangzheng-039

- classification: `harmless_alignment_difference`; confidence: `high`
- source discrepancy: `unmatched_entry_opening`; source record index: `52`
- review reason: The same-edition witness locates the same opening in the current boundary order; differences are glyph templates or attested witness forms.
- recommended action: No repair in this task. Preserve the current canonical boundary and all witness spellings.
- canonical boundary: `05-fangzheng-039` ordinal `39`, primary status `present`, anchor `梅頥嘗有惠於陶公後爲豫章`
- canonical source position: normalized line `402`, source line `346`, page `<pb:KR3l0002_SBCK_002-18a>`
- Kanripo SBCK: `present`; context: `-->\n(左僕射贈車騎將軍中丞孔群也/印師以聞愉悟取而佩焉累遷尚書)在御道逢匡術\n賔從甚盛因往與車騎共語中丞初不視直云鷹化\n爲鳩衆鳥猶惡其眼術大怒便欲刃之車騎下車抱\n術曰族弟發狂卿爲我宥之始得全首領\n梅頥嘗有惠於陶公後爲豫章太守有事王丞相遣\n收之侃曰天子富於春秋萬機自諸侯出王公旣得\n錄陶公何爲不可放乃遣人於江口奪之(曰頥字仲/晉諸公賛)\n(名曰頥領軍司馬頥弟陶字叔眞鄧粲晉紀曰初有/眞汝南西平人少好學隱退而求實進止永嘉流人)\n(州侃文武距廙而求侃敦聞大怒及侃將莅廣州過/讃侃於王敦者乃以從弟廙代侃爲荆州左遷侃廣)\n(而遣之王隱晉書亦同按二書所敘則有惠於陶是/敦敦陳兵欲害侃敦咨議參軍梅陶諫敦乃止厚礼)\n<!-- kanripo-page `
- Wikisource SBCK: `located`; page `Page:Sibu Congkan0463-劉義慶-世説新語-3-2.djvu/34`; bounded reading: `梅頥嘗有惠於陶公後爲豫章`
- adjacent-boundary order: `ordered`; positions `{'previous': 2802, 'current': 2872, 'next': 2950}`

---

#### discrepancy-054 — 05-fangzheng-042

- classification: `harmless_alignment_difference`; confidence: `high`
- source discrepancy: `unmatched_entry_opening`; source record index: `54`
- review reason: The same-edition witness locates the same opening in the current boundary order; differences are glyph templates or attested witness forms.
- recommended action: No repair in this task. Preserve the current canonical boundary and all witness spellings.
- canonical boundary: `05-fangzheng-042` ordinal `42`, primary status `present`, anchor `江僕射年少王丞相呼與共棊`
- canonical source position: normalized line `424`, source line `368`, page `<pb:KR3l0002_SBCK_002-19a>`
- Kanripo SBCK: `present`; context: `臣\n之議今不覩盛明之世(議立長君何充謂宜奉皇子/晉陽秋曰初顯宗臨崩庾氷)\n(京馳還言於帝曰氷不宜出昔年陛下龍飛使晉德/爭之不得充不自安求處外任及氷出鎮武昌充自)\n(也臣無與焉/再隆者氷之勲)帝有慙色\n江僕射年少王丞相呼與共棊王手嘗不如兩道許\n而欲敵道戲試以觀之江不即下王曰君何以不行\n江曰恐不得爾(學知名兼善弈爲中興之冠累遷尚/徐廣晉紀曰江虨字思玄陳留人博)\n(護軍將軍/書左僕射)傍有客曰此年少戲廼不惡王徐舉首曰\n此年少非唯圍棊見勝(等棊第一品導第五品/范汪棊品曰虨與王恬)\n孔君平疾篤庾司空爲㑹稽省之(氷/庾)相問訊甚至爲\n<!-- kanripo-page source-line=374: <pb:KR3l0002_SBCK_002`
- Wikisource SBCK: `located`; page `Page:Sibu Congkan0463-劉義慶-世説新語-3-2.djvu/36`; bounded reading: `江僕射年少王丞相呼與共棊`
- adjacent-boundary order: `ordered`; positions `{'previous': 2973, 'current': 3073, 'next': 3144}`

---

#### discrepancy-056 — 05-fangzheng-047

- classification: `harmless_alignment_difference`; confidence: `high`
- source discrepancy: `unmatched_entry_opening`; source record index: `56`
- review reason: The same-edition witness locates the same opening in the current boundary order; differences are glyph templates or attested witness forms.
- recommended action: No repair in this task. Preserve the current canonical boundary and all witness spellings.
- canonical boundary: `05-fangzheng-047` ordinal `47`, primary status `present`, anchor `王述轉尚書令事行便拜文度`
- canonical source position: normalized line `446`, source line `390`, page `<pb:KR3l0002_SBCK_002-20a>`
- Kanripo SBCK: `present`; context: `年少時(巳見/坦之)江虨爲僕射領選欲擬之爲尚\n書郎有語王者王曰自過江來尚書郎正用第二人\n何得擬我江聞而止(謂彪之曰選曹舉汝爲尚書郎/按王彪之别傳曰彪之從伯導)\n(知郎官寒素之品也/幸可作諸王佐邪此)\n王述轉尚書令事行便拜文度曰故應讓杜許藍田\n云汝謂我堪此不文度曰何爲不堪但克讓自是美\n事恐不可闕藍田慨然曰既云堪何爲復讓人言汝\n勝我定不如我(量巳而後動義無虚讓是以應辭便/述别傳曰述常以謂人之處世當先)\n(不踰皆此類/當固執其貞正)\n孫興公作庾公誄文多託寄之辭(予與公風流同歸/綽集載誄文曰咨)\n<!-- kanripo-page source-line=396: <pb:KR3l0002_SBCK_002-20b> -->\n(吐誠誨非雖實`
- Wikisource SBCK: `located`; page `Page:Sibu Congkan0463-劉義慶-世説新語-3-2.djvu/38`; bounded reading: `王述轉尚書令事行便拜文度`
- adjacent-boundary order: `ordered`; positions `{'previous': 3284, 'current': 3330, 'next': 3396}`

---

#### discrepancy-059 — 05-fangzheng-057

- classification: `harmless_alignment_difference`; confidence: `high`
- source discrepancy: `unmatched_entry_opening`; source record index: `59`
- review reason: The same-edition witness locates the same opening in the current boundary order; differences are glyph templates or attested witness forms.
- recommended action: No repair in this task. Preserve the current canonical boundary and all witness spellings.
- canonical boundary: `05-fangzheng-057` ordinal `57`, primary status `present`, anchor `韓康伯病拄杖前庭消搖(巳見/韓伯)見諸`
- canonical source position: normalized line `492`, source line `436`, page `<pb:KR3l0002_SBCK_002-22a>`
- Kanripo SBCK: `present`; context: `衆坐曰此自江左之清秀豈唯/西池小洲上立茅茨伐木爲牀織葦爲席布衣𬞞食)\n(夫門施行馬含自在官舍有一白雀棲集堂宇及致/荆楚而已累遷散騎常侍廷尉長沙相致仕中散大)\n(生豈非至行之徴邪/仕還家階庭忽蘭菊挺)\n韓康伯病拄杖前庭消搖(巳見/韓伯)見諸謝皆富貴轟隱\n交路歎曰此復何異王莽時(侯五大司馬/漢書曰王莽宗族凡十)\n王文度爲桓公長史時桓爲兒求王女王許咨藍田\n(述並巳見/王坦之王)既還藍田愛念文度雖長大猶抱著䣛上\n<!-- kanripo-page source-line=440: <pb:KR3l0002_SBCK_002-22b> -->\n文度因言桓求已女㛰藍田大怒排文度下䣛曰惡\n見文度已復癡畏桓温靣兵那可嫁女與之文度還\n報云下官家中先得`
- Wikisource SBCK: `located`; page `Page:Sibu Congkan0463-劉義慶-世説新語-3-2.djvu/42`; bounded reading: `韓康伯病拄杖前庭消搖見諸`
- adjacent-boundary order: `ordered`; positions `{'previous': 3790, 'current': 3816, 'next': 3845}`

---

#### discrepancy-061 — missing_kanripo_passage

- classification: `missing_entry`; confidence: `high`
- source discrepancy: `missing_kanripo_passage`; source record index: `61`
- review reason: The primary witness omission corresponds to explicit current canonical gap entries supported by Wikisource; no additional entry is missing from the canonical structure.
- recommended action: No new repair in this task. The current manifest already records the primary-witness gap explicitly; do not alter raw Kanripo text.
- canonical chapter structure: `66` entries; gap ordinals `[14]`; partial ordinals `[]`; ordinal continuity `True`
- Kanripo SBCK bounded record: `65` historical entries, `4274` main characters; context: `之它人能令踈親臣不能使親踈以此愧陛下杜預之荆州頓七里橋朝士悉祖預少賤好豪侠不爲物所許楊濟既名氏雄俊不堪不坐而去須臾和長輿來問楊右衛何在客曰向來不坐而去長輿曰必大夏門下盤馬往大夏門果大閲騎長輿抱內車共載歸坐如初杜預拜鎮南將軍朝士悉至皆在連榻坐山公大兒著短帢車中倚武帝欲見之山公不敢辭問兒兒不肯行時論乃云勝山公向雄爲河內主簿有公事不及雄而太守劉淮横怒遂與杖遣之雄後爲黄門郎劉爲侍中初不交言武帝聞之敕雄復君臣之好雄不得巳詣劉再拜曰向受詔而來而君臣之義絶何如於是即去武帝聞尚不和乃怒問雄曰我令卿復君臣之好何以猶絶雄曰古之君子進人以禮退人以禮今之君子進人若將加諸䣛退人若將墜諸淵臣於劉河內不爲戎首亦巳幸甚安復爲君臣之好武帝從之齊王冏爲大司馬輔政嵇紹爲侍中詣冏咨事冏設宰㑹召葛旟董艾等共論時冝`
- Wikisource SBCK bounded record: `4420` main characters; context: `之它人能令踈親臣不能使親踈以此愧陛下杜預之荆州頓七里橋朝士悉祖預少賤好豪侠不爲物所許楊濟既名氏雄俊不堪不坐而去須⟦{{SKchar|3099}}⟧和長輿來問楊右衛何在客曰向來不坐而去長輿曰必大夏門下盤馬往大夏門果大閲騎長輿抱內車共載歸坐如初杜預拜鎮南將軍朝士悉至皆在連榻坐時亦有裴叔則羊穉舒後至曰杜元凱乃復連榻坐客不坐便去杜請裴追之羊去數里住馬既而俱還杜許晉武帝時荀朂爲中書監和嶠爲令故事監令由來共車嶠性雅正常疾朂謟䛕後公車來嶠便登正向前坐不復容朂朂方更覓車然得去監令各給車自此始山公大兒著短帢車中倚武帝欲見之山公不敢辭問兒兒不肯行時論乃云勝山公向雄爲河內主簿有公事不及雄而太守劉淮横怒遂與杖遣之雄後爲黄門郎劉爲侍中初不交言武帝聞之敕雄復君臣之好雄不得巳詣劉再拜曰向受詔而來而君臣之義絶何如於是即去武帝聞尚不和乃怒問雄曰…`
- comparison metrics: sequence ratio `0.970554`, length delta `146`, annotation delta `14`
- affected canonical boundary: `05-fangzheng-014` opening `晉武帝時荀朂爲中書監和嶠爲令故事監令由來共車嶠性`; primary status `gap`, supplement `shishuo-wikisource-sbck`

---

### 06-yaliang — 雅量第六

#### discrepancy-062 — 06-yaliang-005

- classification: `harmless_alignment_difference`; confidence: `high`
- source discrepancy: `unmatched_entry_opening`; source record index: `62`
- review reason: The same-edition witness locates the same opening in the current boundary order; differences are glyph templates or attested witness forms.
- recommended action: No repair in this task. Preserve the current canonical boundary and all witness spellings.
- canonical boundary: `06-yaliang-005` ordinal `5`, primary status `present`, anchor `魏明帝於宣武埸上斷虎爪牙`
- canonical source position: normalized line `580`, source line `524`, page `<pb:KR3l0002_SBCK_002-26a>`
- Kanripo SBCK: `present`; context: `拜陵陪列於松)\n(榮緒又以爲諸葛誕也/之皆伏太初顧色不攺臧)\n王戎七歲嘗與諸小兒遊看道邊李樹多子折枝諸\n兒競走取之唯戎不動人問之荅曰樹在道邊而多\n子此必苦李取之信然(㓜有神理之稱也/名士傳曰戎由是)\n魏明帝於宣武埸上斷虎爪牙縱百姓觀之王戎七\n歲亦往看虎承間攀欄而吼其聲震地觀者無不辟\n易顛仆戎湛然不動了無恐色(自閣上望見使人問/竹林七賢論曰明帝)\n(而異之/戎姓名)\n<!-- kanripo-page source-line=528: <pb:KR3l0002_SBCK_002-26b> -->\n王戎爲侍中南郡太守劉肈遺筒中箋布五端戎雖\n不受厚報其書(守劉肈以布五十疋雜物遺前豫州/晉陽秋曰司隷校尉劉毅奏南郡太)\n(未逹不坐竹林七賢論曰`
- Wikisource SBCK: `located`; page `Page:Sibu Congkan0463-劉義慶-世説新語-3-2.djvu/50`; bounded reading: `魏明帝於宣武⟦{{SKchar|3949}}⟧上斷虎爪牙`
- adjacent-boundary order: `ordered`; positions `{'previous': 180, 'current': 229, 'next': 281}`

---

#### discrepancy-064 — 06-yaliang-013

- classification: `harmless_alignment_difference`; confidence: `high`
- source discrepancy: `unmatched_entry_opening`; source record index: `64`
- review reason: The same-edition witness locates the same opening in the current boundary order; differences are glyph templates or attested witness forms.
- recommended action: No repair in this task. Preserve the current canonical boundary and all witness spellings.
- canonical boundary: `06-yaliang-013` ordinal `13`, primary status `present`, anchor `有往來者云庾公有東下意`
- canonical source position: normalized line `622`, source line `566`, page `<pb:KR3l0002_SBCK_002-28a>`
- Kanripo SBCK: `present`; context: `02_SBCK_002-28a> -->\n(雖非其才而以罕重稱也/事少為文士而經事爲將)\n王夷甫長裴成公四歲不與相知時共集一處皆當\n時名士謂王曰裴令令望何足計王便卿裴裴曰自\n可全君雅志(已見/裴頠)\n有往來者云庾公有東下意或謂王公可潜稍嚴以\n備不虞王公曰我與元規雖俱王臣本懐布衣之好\n若其欲來吾角巾徑還烏衣(時烏衣營處所也江左/丹陽記曰烏衣之起吳)\n(諸王所居/初立琅邪)何所稍嚴(塵自消内外緝穆/中興書曰於是風)\n王丞相主簿欲檢校帳下公語主簿欲與主簿周旋\n無爲知人几案間事\n<!-- kanripo-page source-line=572: <pb:KR3l0002_SBCK_002-28b> -->\n祖士少好財阮遥集好屐並恒自經營同`
- Wikisource SBCK: `located`; page `Page:Sibu Congkan0463-劉義慶-世説新語-3-2.djvu/54`; bounded reading: `有往來者云𢈔公有東下意`
- adjacent-boundary order: `ordered`; positions `{'previous': 649, 'current': 694, 'next': 749}`

---

### 07-shijian — 識鑒第七

#### discrepancy-074 — 07-shijian-016

- classification: `harmless_alignment_difference`; confidence: `high`
- source discrepancy: `unmatched_entry_opening`; source record index: `74`
- review reason: The same-edition witness locates the same opening in the current boundary order; differences are glyph templates or attested witness forms.
- recommended action: No repair in this task. Preserve the current canonical boundary and all witness spellings.
- canonical boundary: `07-shijian-016` ordinal `16`, primary status `present`, anchor `武昌孟嘉作庾太尉州從事巳`
- canonical source position: normalized line `922`, source line `865`, page `<pb:KR3l0002_SBCK_002-41b>`
- Kanripo SBCK: `present`; context: `舒器業)\n(討蘇峻有功封彭澤侯贈車騎大將軍/僕射出爲會稽太守以父名會累表自陳)彬聞應當\n來密具船以待之竟不得來深以爲恨(遣軍逆之含/含之投舒舒)\n(況販兄弟以求安舒非人矣/父子赴水死昔酈寄賣友見譏)\n武昌孟嘉作庾太尉州從事巳知名禇太傅有知人\n鑒罷豫章還過武昌問庾曰聞孟從事佳今在此不\n庾云試自求之禇眄睞良乆指嘉曰此君小異得無\n<!-- kanripo-page source-line=869: <pb:KR3l0002_SBCK_002-42a> -->\n是乎庾大笑曰然于時既歎禇之黙識又欣嘉之見\n賞(祖父揖晉廬陵太守宗葬武昌陽新縣子孫家焉/嘉别傳曰嘉字萬年江夏鄳人曾祖父宗吳司空)\n(事下都還亮引問風俗得失對曰待還當問從事吏/嘉少以清操`
- Wikisource SBCK: `located`; page `Page:Sibu Congkan0463-劉義慶-世説新語-3-2.djvu/81`; bounded reading: `武昌孟嘉作𢈔太尉州從事巳`
- adjacent-boundary order: `ordered`; positions `{'previous': 902, 'current': 1027, 'next': 1108}`

---

#### discrepancy-077 — 07-shijian-023

- classification: `harmless_alignment_difference`; confidence: `high`
- source discrepancy: `unmatched_entry_opening`; source record index: `77`
- review reason: The same-edition witness locates the same opening in the current boundary order; differences are glyph templates or attested witness forms.
- recommended action: No repair in this task. Preserve the current canonical boundary and all witness spellings.
- canonical boundary: `07-shijian-023` ordinal `23`, primary status `present`, anchor `韓康伯與謝玄亦無深好玄北`
- canonical source position: normalized line `977`, source line `920`, page `<pb:KR3l0002_SBCK_002-44a>`
- Kanripo SBCK: `present`; context: `推之容必能立勲元功既舉時人咸歎超\n之先覺又重其不以愛憎匿善(彊盛朝議求文武良/中興書曰于時氐賊)\n(事中書郎郗超聞而嘆曰安違衆舉親明也玄必不/將可鎮靖北方者衛大將軍安曰唯兄子玄可任此)\n(舉/負其)\n韓康伯與謝玄亦無深好玄北征後巷議疑其不振\n康伯曰此人好名必能戰(貞正有經國之才略/續晉陽秋曰玄識局)玄聞\n之甚忿常於衆中厲色曰丈夫提千兵入死地以事\n<!-- kanripo-page source-line=924: <pb:KR3l0002_SBCK_002-44b> -->\n君親故發不得復云爲名\n禇期生少時謝公甚知之恒云禇期生若不佳者僕\n不復相士(河南人太傅裒之孫秘書監韶之子太傅/期生禇爽小字也續晉陽秋曰爽字茂弘)\n(果俊邁有風氣好`
- Wikisource SBCK: `located`; page `Page:Sibu Congkan0463-劉義慶-世説新語-3-2.djvu/86`; bounded reading: `韓康伯與謝⟦{{SKchar|2593}}⟧亦無深好⟦{{SKchar|2593}}⟧北`
- adjacent-boundary order: `ordered`; positions `{'previous': 1328, 'current': 1430, 'next': 1492}`

---

### 08-shangyu — 賞譽第八

#### discrepancy-083 — 08-shangyu-035

- classification: `harmless_alignment_difference`; confidence: `high`
- source discrepancy: `unmatched_entry_opening`; source record index: `83`
- review reason: The same-edition witness locates the same opening in the current boundary order; differences are glyph templates or attested witness forms.
- recommended action: No repair in this task. Preserve the current canonical boundary and all witness spellings.
- canonical boundary: `08-shangyu-035` ordinal `35`, primary status `present`, anchor `庾太尉少爲王眉子所知庾過`
- canonical source position: normalized line `1231`, source line `47`, page `<pb:KR3l0002_SBCK_003-2b>`
- Kanripo SBCK: `present`; context: `可以漸先王之教也然學之所受)\n(聞道德之風欲屈諸君時以閑豫周旋燕誨也穆歷/諷味遺言不如親承辭㫖小兒毗既無令淑之資未)\n(吳郡太守封南鄉侯/晉明帝師冠軍將軍)袁宏作名士傳直云王叅軍或\n云趙家先猶有此本\n庾太尉少爲王眉子所知庾過江嘆王曰庇其宇下\n使人忘寒暑(曰玄爲陳留太守或勸玄過江投琅邪/晉諸公賛曰玄少希慕簡曠八王故事)\n(害豈能容我謂其噐宇不容於敦也/王玄曰王處仲得志於彼家叔猶不免)\n謝㓜輿曰友人王眉子清通簡畼嵇延祖弘雅劭長\n董仲道卓犖有致度(初到洛下于禄求榮永嘉中洛/王隱晉書曰董養字仲道太始)\n(不能飛問之博識者不能知養聞歎曰昔周時所盟/城東北角歩廣里中地陷中有二鵝蒼者飛去白者)\n<!-- kanripo-page source-l`
- Wikisource SBCK: `located`; page `Page:Sibu Congkan0463-劉義慶-世説新語-3-2.djvu/111`; bounded reading: `𢈔太尉少爲王眉子所知𢈔過`
- adjacent-boundary order: `ordered`; positions `{'previous': 1570, 'current': 1685, 'next': 1710}`

---

#### discrepancy-085 — 08-shangyu-040

- classification: `harmless_alignment_difference`; confidence: `high`
- source discrepancy: `unmatched_entry_opening`; source record index: `85`
- review reason: The same-edition witness locates the same opening in the current boundary order; differences are glyph templates or attested witness forms.
- recommended action: No repair in this task. Preserve the current canonical boundary and all witness spellings.
- canonical boundary: `08-shangyu-040` ordinal `40`, primary status `present`, anchor `王長史是庾子躬外孫(州庾琮之女字三壽也/王氏譜曰濛父訥娶潁)丞相\n目`
- canonical source position: normalized line `1255`, source line `71`, page `<pb:KR3l0002_SBCK_003-3b>`
- Kanripo SBCK: `present`; context: `\n之清中(作平/中一)\n蔡司徒在洛見陸機兄弟住參佐廨中三間瓦屋士\n龍住東頭士衡住西頭士龍爲人文弱可愛士衡長\n七尺餘聲作鍾聲言多忼慨(怡然爲士友所宗機清/文士傳曰雲性弘静怡)\n(鄉黨所憚/厲有風格爲)\n王長史是庾子躬外孫(州庾琮之女字三壽也/王氏譜曰濛父訥娶潁)丞相\n目子躬云入理泓然我巳上人(嵩兄也/子躬子)\n庾太尉目庾中郎家從談談之許(辨析之談而舉其/名士傳曰敳不爲)\n(家從談之祖從一作誦許一作辭/㫖要太尉王夷甫雅重之也一作)\n<!-- kanripo-page source-line=75: <pb:KR3l0002_SBCK_003-4a> -->\n庾公目中郎神氣融散差如得上(淵放莫有動其聽/晉陽秋曰敳頽然)\n(者)\n劉琨稱祖車`
- Wikisource SBCK: `located`; page `Page:Sibu Congkan0463-劉義慶-世説新語-3-2.djvu/113`; bounded reading: `王長史是𢈔子躬外孫丞相目`
- adjacent-boundary order: `ordered`; positions `{'previous': 1800, 'current': 1851, 'next': 1874}`

---

#### discrepancy-086 — 08-shangyu-041

- classification: `harmless_alignment_difference`; confidence: `high`
- source discrepancy: `unmatched_entry_opening`; source record index: `86`
- review reason: The same-edition witness locates the same opening in the current boundary order; differences are glyph templates or attested witness forms.
- recommended action: No repair in this task. Preserve the current canonical boundary and all witness spellings.
- canonical boundary: `08-shangyu-041` ordinal `41`, primary status `present`, anchor `庾太尉目庾中郎家從談談之`
- canonical source position: normalized line `1257`, source line `73`, page `<pb:KR3l0002_SBCK_003-3b>`
- Kanripo SBCK: `present`; context: `尺餘聲作鍾聲言多忼慨(怡然爲士友所宗機清/文士傳曰雲性弘静怡)\n(鄉黨所憚/厲有風格爲)\n王長史是庾子躬外孫(州庾琮之女字三壽也/王氏譜曰濛父訥娶潁)丞相\n目子躬云入理泓然我巳上人(嵩兄也/子躬子)\n庾太尉目庾中郎家從談談之許(辨析之談而舉其/名士傳曰敳不爲)\n(家從談之祖從一作誦許一作辭/㫖要太尉王夷甫雅重之也一作)\n<!-- kanripo-page source-line=75: <pb:KR3l0002_SBCK_003-4a> -->\n庾公目中郎神氣融散差如得上(淵放莫有動其聽/晉陽秋曰敳頽然)\n(者)\n劉琨稱祖車騎爲朗詣曰少爲王敦所歎(曰逖字士/虞預晉書)\n(與司空劉琨俱以雄豪著名年二十四與琨同辟司/穉范陽遒人豁蕩不修儀`
- Wikisource SBCK: `located`; page `Page:Sibu Congkan0463-劉義慶-世説新語-3-2.djvu/113`; bounded reading: `𢈔太尉目𢈔中郎家從談談之`
- adjacent-boundary order: `ordered`; positions `{'previous': 1851, 'current': 1874, 'next': 1887}`

---

#### discrepancy-098 — 08-shangyu-072

- classification: `harmless_alignment_difference`; confidence: `high`
- source discrepancy: `unmatched_entry_opening`; source record index: `98`
- review reason: The same-edition witness locates the same opening in the current boundary order; differences are glyph templates or attested witness forms.
- recommended action: No repair in this task. Preserve the current canonical boundary and all witness spellings.
- canonical boundary: `08-shangyu-072` ordinal `72`, primary status `present`, anchor `庾公云逸少國舉故庾倪爲碑`
- canonical source position: normalized line `1371`, source line `187`, page `<pb:KR3l0002_SBCK_003-9a>`
- Kanripo SBCK: `present`; context: `有/語林)\n<!-- kanripo-page source-line=185: <pb:KR3l0002_SBCK_003-9a> -->\n(怡容無韻盛德之風可樂詠也/人目杜弘治標解甚清令初若熙)\n庾公云逸少國舉故庾倪爲碑文云抜萃國舉(倩小/倪庾)\n(才具仕至太宰長史桓温以其宗彊使下邳王晃誣/字也徐廣晉紀曰倩字少彦司空氷子皇后兄也有)\n(而誅之/與謀反)\n庾稺恭與桓温書稱劉道生日夕在事大小殊快義\n懐通樂既佳且足作友正實良器推此與君同濟艱\n不者也(明濟有文武才王濛每稱其思理淹通蕃屏/宋明帝文章志曰劉恢字道生沛國人識局)\n(三十六卒贈前将軍/之高選爲車騎司馬年)\n王藍田拜揚州主簿請諱教云亡祖先君名播海内\n逺近所知内諱不出於外(之諱不出`
- Wikisource SBCK: `located`; page `Page:Sibu Congkan0463-劉義慶-世説新語-3-2.djvu/124`; bounded reading: `⟦{{SKchar|2928}}⟧公云逸少國舉故⟦{{SKchar|2928}}⟧倪爲碑`
- adjacent-boundary order: `ordered`; positions `{'previous': 2732, 'current': 2750, 'next': 2768}`

---

#### discrepancy-099 — 08-shangyu-073

- classification: `harmless_alignment_difference`; confidence: `high`
- source discrepancy: `unmatched_entry_opening`; source record index: `99`
- review reason: The same-edition witness locates the same opening in the current boundary order; differences are glyph templates or attested witness forms.
- recommended action: No repair in this task. Preserve the current canonical boundary and all witness spellings.
- canonical boundary: `08-shangyu-073` ordinal `73`, primary status `present`, anchor `庾稺恭與桓温書稱劉道生日`
- canonical source position: normalized line `1374`, source line `190`, page `<pb:KR3l0002_SBCK_003-9a>`
- Kanripo SBCK: `present`; context: `可樂詠也/人目杜弘治標解甚清令初若熙)\n庾公云逸少國舉故庾倪爲碑文云抜萃國舉(倩小/倪庾)\n(才具仕至太宰長史桓温以其宗彊使下邳王晃誣/字也徐廣晉紀曰倩字少彦司空氷子皇后兄也有)\n(而誅之/與謀反)\n庾稺恭與桓温書稱劉道生日夕在事大小殊快義\n懐通樂既佳且足作友正實良器推此與君同濟艱\n不者也(明濟有文武才王濛每稱其思理淹通蕃屏/宋明帝文章志曰劉恢字道生沛國人識局)\n(三十六卒贈前将軍/之高選爲車騎司馬年)\n王藍田拜揚州主簿請諱教云亡祖先君名播海内\n逺近所知内諱不出於外(之諱不出門/禮記曰婦人)餘無所諱\n<!-- kanripo-page source-line=196: <pb:KR3l0002_SBCK_003-9b> -->\n蕭中`
- Wikisource SBCK: `located`; page `Page:Sibu Congkan0463-劉義慶-世説新語-3-2.djvu/124`; bounded reading: `⟦{{SKchar|2928}}⟧稺恭與⟦{{SKchar|3129}}⟧温書稱劉道生日`
- adjacent-boundary order: `ordered`; positions `{'previous': 2750, 'current': 2768, 'next': 2811}`

---

#### discrepancy-100 — 08-shangyu-074

- classification: `harmless_alignment_difference`; confidence: `high`
- source discrepancy: `unmatched_entry_opening`; source record index: `100`
- review reason: The same-edition witness locates the same opening in the current boundary order; differences are glyph templates or attested witness forms.
- recommended action: No repair in this task. Preserve the current canonical boundary and all witness spellings.
- canonical boundary: `08-shangyu-074` ordinal `74`, primary status `present`, anchor `王藍田拜揚州主簿請諱教云`
- canonical source position: normalized line `1378`, source line `194`, page `<pb:KR3l0002_SBCK_003-9a>`
- Kanripo SBCK: `present`; context: `桓温書稱劉道生日夕在事大小殊快義\n懐通樂既佳且足作友正實良器推此與君同濟艱\n不者也(明濟有文武才王濛每稱其思理淹通蕃屏/宋明帝文章志曰劉恢字道生沛國人識局)\n(三十六卒贈前将軍/之高選爲車騎司馬年)\n王藍田拜揚州主簿請諱教云亡祖先君名播海内\n逺近所知内諱不出於外(之諱不出門/禮記曰婦人)餘無所諱\n<!-- kanripo-page source-line=196: <pb:KR3l0002_SBCK_003-9b> -->\n蕭中郎孫丞公婦父劉尹在撫軍坐時擬為太常劉\n尹云蕭祖周不知便可作三公不自此以還無所不\n堪(紀曰輪有才學善三禮歷常侍國子博士/晉百官名曰蕭輪字祖周樂安人劉謙之晉)\n謝太傅未冠始出西詣王長史清言良久去後茍子\n問曰(並巳`
- Wikisource SBCK: `located`; page `Page:Sibu Congkan0463-劉義慶-世説新語-3-2.djvu/124`; bounded reading: `王藍田拜⟦{{SKchar|3951}}⟧州主簿請諱教云`
- adjacent-boundary order: `ordered`; positions `{'previous': 2768, 'current': 2811, 'next': 2845}`

---

#### discrepancy-102 — 08-shangyu-084

- classification: `missing_entry`; confidence: `high`
- source discrepancy: `unmatched_entry_opening`; source record index: `102`
- review reason: The primary Kanripo witness has no surviving anchor; the current canonical entry is an explicit reviewed same-edition supplement.
- recommended action: No new repair in this task. Preserve the raw Kanripo gap and the existing explicit same-edition supplement.
- canonical boundary: `08-shangyu-084` ordinal `84`, primary status `gap`, anchor `王長史道江道羣人所應有乃不必有人所應無已必無`
- canonical source position: normalized line `None`, source line `None`, page `None`
- Kanripo SBCK: `gap`; context: `(none)`
- Wikisource SBCK: `located`; page `Page:Sibu Congkan0463-劉義慶-世説新語-3-2.djvu/127`; bounded reading: `王長史道江道羣人所應有乃不必有人所應無已必無`
- adjacent-boundary order: `ordered`; positions `{'previous': 3049, 'current': 3088, 'next': 3110}`

---

#### discrepancy-105 — 08-shangyu-099

- classification: `harmless_alignment_difference`; confidence: `high`
- source discrepancy: `unmatched_entry_opening`; source record index: `105`
- review reason: The same-edition witness locates the same opening in the current boundary order; differences are glyph templates or attested witness forms.
- recommended action: No repair in this task. Preserve the current canonical boundary and all witness spellings.
- canonical boundary: `08-shangyu-099` ordinal `99`, primary status `present`, anchor `殷淵源在墓所㡬十年于時朝`
- canonical source position: normalized line `1438`, source line `254`, page `<pb:KR3l0002_SBCK_003-12a>`
- Kanripo SBCK: `present`; context: `清識/支遁别傳曰遁)\n<!-- kanripo-page source-line=252: <pb:KR3l0002_SBCK_003-12a> -->\n(其造微之功不異王弼/玄逺嘗至京師王仲祖稱)\n殷淵源在墓所㡬十年于時朝野以擬管葛起不起\n以卜江左興亡(簡文親賢民望任登宰輔桓温有平/續晉陽秋曰時穆帝幼沖母后臨朝)\n(浩素有盛名時論比之管葛故徵浩為揚州温知意/蜀洛之勲擅彊西陜帝自料文弱無以抗之陳郡殷)\n(甚忿焉/在抗已)\n殷中軍道右軍清鑒貴要(之風骨清舉也/晉安帝紀曰羲)\n謝太傅爲桓公司馬(敷文析理自娛桓温在西蕃欽/續晉陽秋曰初安優遊山水以)\n(夷志存匡濟年四十起家應務也/其盛名諷朝廷請爲司馬以世道未)桓詣謝值謝梳\n頭遽取衣幘桓公云`
- Wikisource SBCK: `located`; page `Page:Sibu Congkan0463-劉義慶-世説新語-3-2.djvu/131`; bounded reading: `殷淵源在墓所㡬十年于時朝`
- adjacent-boundary order: `ordered`; positions `{'previous': 3459, 'current': 3473, 'next': 3499}`

---

#### discrepancy-108 — 08-shangyu-105

- classification: `harmless_alignment_difference`; confidence: `high`
- source discrepancy: `unmatched_entry_opening`; source record index: `108`
- review reason: The same-edition witness locates the same opening in the current boundary order; differences are glyph templates or attested witness forms.
- recommended action: No repair in this task. Preserve the current canonical boundary and all witness spellings.
- canonical boundary: `08-shangyu-105` ordinal `105`, primary status `present`, anchor `桓大司馬病謝公往省病從東`
- canonical source position: normalized line `1457`, source line `273`, page `<pb:KR3l0002_SBCK_003-12b>`
- Kanripo SBCK: `present`; context: `人譽是以入賛百揆出蕃方司宜進據洛陽撫/州既平宜時綏定鎮西將軍豫州刺史尚神懐挺率)\n(都督司州諸軍事/寧黎庶謂可本官)\n世目謝尚爲令逹阮遥集云清畼似逹或云尚自然\n令上(挺達超悟令上也/晉陽秋曰尚率易)\n桓大司馬病謝公往省病從東門入(姑孰/温時在)桓公遥\n<!-- kanripo-page source-line=274: <pb:KR3l0002_SBCK_003-13a> -->\n望嘆曰吾門中久不見如此人\n簡文目敬豫爲朗豫(理明貴爲後進冠冕也/王恬已見文字志曰恬識)\n孫興公爲庾公叅軍共遊白石山衛君長在坐(譜曰/衛氏)\n(位至左軍長史/永字君長成陽人)孫曰此子神情都不關山水而能\n作文庾公曰衛風韻雖不及卿諸人傾倒處亦不近\n孫遂沐浴此言\n`
- Wikisource SBCK: `located`; page `Page:Sibu Congkan0463-劉義慶-世説新語-3-2.djvu/132`; bounded reading: `⟦{{SKchar|3129}}⟧大司馬病謝公往省病從東`
- adjacent-boundary order: `ordered`; positions `{'previous': 3635, 'current': 3657, 'next': 3686}`

---

#### discrepancy-111 — 08-shangyu-117

- classification: `harmless_alignment_difference`; confidence: `high`
- source discrepancy: `unmatched_entry_opening`; source record index: `111`
- review reason: The same-edition witness locates the same opening in the current boundary order; differences are glyph templates or attested witness forms.
- recommended action: No repair in this task. Preserve the current canonical boundary and all witness spellings.
- canonical boundary: `08-shangyu-117` ordinal `117`, primary status `present`, anchor `桓公語嘉賔阿源有德有言向`
- canonical source position: normalized line `1490`, source line `306`, page `<pb:KR3l0002_SBCK_003-14a>`
- Kanripo SBCK: `present`; context: `綽爲汰賛曰淒風拂林明泉映)\n(宗詔曰法汰師䘮逝哀痛傷懐可贈錢十萬/起名隨後躍泰元起居注曰法汰以十年卒烈)\n王長史與大司馬書道淵源識致安處足副時談\n謝公云劉尹語審細(猶淵鏡言必珠玉/孫綽爲惔諫叙曰神)\n桓公語嘉賔阿源有德有言向使作令僕足以儀刑\n<!-- kanripo-page source-line=307: <pb:KR3l0002_SBCK_003-14b> -->\n百揆朝廷用違其才耳(也阿源殷浩也/嘉賔郄超小字)\n簡文語嘉賔劉尹語末後亦小異回復其言亦乃無\n過\n孫興公許玄度共在白樓亭(隂臨流映壑也/㑹稽記曰亭在山)共商\n略先往名達林公既非所關聽訖云二賢故自有才\n情\n王右軍道東陽我家阿林章清太出(譜曰臨之字仲/林應爲臨王氏)\n(子`
- Wikisource SBCK: `located`; page `Page:Sibu Congkan0463-劉義慶-世説新語-3-2.djvu/135`; bounded reading: `⟦{{SKchar|3129}}⟧公語嘉賔阿源有德有言向`
- adjacent-boundary order: `ordered`; positions `{'previous': 3954, 'current': 3962, 'next': 3991}`

---

#### discrepancy-114 — 08-shangyu-125

- classification: `harmless_alignment_difference`; confidence: `high`
- source discrepancy: `unmatched_entry_opening`; source record index: `114`
- review reason: The same-edition witness locates the same opening in the current boundary order; differences are glyph templates or attested witness forms.
- recommended action: No repair in this task. Preserve the current canonical boundary and all witness spellings.
- canonical boundary: `08-shangyu-125` ordinal `125`, primary status `present`, anchor `謝太傅稱王脩齡曰司州可與`
- canonical source position: normalized line `1507`, source line `323`, page `<pb:KR3l0002_SBCK_003-15a>`
- Kanripo SBCK: `present`; context: `-->\n(中書郎鄱陽太守給事中/邪人荆州刺史廙第三子歷)\n林公云王敬仁是超悟人(少有秀令之稱/文字志曰脩之)\n劉尹先推謝鎮西謝後雅重劉曰昔嘗北靣(年長於/按謝尚)\n(北靣於劉非可信/惔神頴夙彰而曰)\n謝太傅稱王脩齡曰司州可與林澤遊(曰胡之常遺/王胡之别傳)\n(與謝安相善也/世務以高尚爲情)\n諺曰揚州獨歩王文度後來出人郗嘉賔(曰超少有/續晉陽秋)\n(大才槃槃謝家安江東獨歩王文度盛德日新郗嘉/才氣越世負俗不循常檢時人爲一代盛譽者語曰)\n(故詳錄焉/賔其語小異)\n人問王長史江　兄弟羣從王荅曰諸江皆復足自\n<!-- kanripo-page source-line=329: <pb:KR3l0002_SBCK_003-15b> -->\n生活`
- Wikisource SBCK: `located`; page `Page:Sibu Congkan0463-劉義慶-世説新語-3-2.djvu/137`; bounded reading: `謝太傅稱王脩齡曰司州可與`
- adjacent-boundary order: `ordered`; positions `{'previous': 4099, 'current': 4116, 'next': 4131}`

---

#### discrepancy-117 — 08-shangyu-143

- classification: `harmless_alignment_difference`; confidence: `high`
- source discrepancy: `unmatched_entry_opening`; source record index: `117`
- review reason: The same-edition witness locates the same opening in the current boundary order; differences are glyph templates or attested witness forms.
- recommended action: No repair in this task. Preserve the current canonical boundary and all witness spellings.
- canonical boundary: `08-shangyu-143` ordinal `143`, primary status `present`, anchor `謝公語王孝伯君家藍田舉體`
- canonical source position: normalized line `1550`, source line `366`, page `<pb:KR3l0002_SBCK_003-17a>`
- Kanripo SBCK: `present`; context: `-line=362: <pb:KR3l0002_SBCK_003-17a> -->\n(俱有美稱/與頴川荀羡)\n吳四姓舊目云張文朱武陸忠顧厚(郡有顧陸朱張/吳錄士林曰吳)\n(間四姓盛焉/為四姓三國之)\n謝公語王孝伯君家藍田舉體無常人事(而性不寛/按述雖簡)\n(虚相褒飾則世説謬設斯語也/裕投火怒蠅方之未甚若非太傳)\n許掾嘗詣簡文爾夜風恬月朗乃共作曲室中語襟\n情之詠偏是許之所長辭寄清婉有逾平日簡文雖\n契素此遇尤相咨嗟不覺造䣛共义手語達于將旦\n既而曰玄度才情故未易多有許(言理曾出都迎姉/續晉陽秋曰詢能)\n(懐之詠每造䣛賞對夜以繫日/簡文皇帝劉真長説其情㫖及襟)\n<!-- kanripo-page source-line=373: <pb:K`
- Wikisource SBCK: `located`; page `Page:Sibu Congkan0463-劉義慶-世説新語-3-2.djvu/141`; bounded reading: `謝公語王孝伯君家藍田舉體`
- adjacent-boundary order: `ordered`; positions `{'previous': 4432, 'current': 4446, 'next': 4462}`

---

#### discrepancy-118 — 08-shangyu-154

- classification: `harmless_alignment_difference`; confidence: `high`
- source discrepancy: `unmatched_entry_opening`; source record index: `118`
- review reason: The same-edition witness locates the same opening in the current boundary order; differences are glyph templates or attested witness forms.
- recommended action: No repair in this task. Preserve the current canonical boundary and all witness spellings.
- canonical boundary: `08-shangyu-154` ordinal `154`, primary status `present`, anchor `司馬太傅爲二王目曰孝伯亭`
- canonical source position: normalized line `1595`, source line `411`, page `<pb:KR3l0002_SBCK_003-19a>`
- Kanripo SBCK: `present`; context: `慮弗見令乃令袁恱)\n(忱雖心不負恭而無以自亮於是情好大離而怨隟/同異疑誤朝野其言切厲恭雖惋悵謂忱爲搆巳也)\n(矣/成)然每至興㑹故有相思時恭嘗行散至京口射堂\n于時清露晨流新桐初引恭目之曰王大故自濯濯\n司馬太傅爲二王目曰孝伯亭亭直上阿大羅羅清\n踈(忱通朗誕放/恭正亮沈烈)\n王恭有清辭簡㫖能叙說而讀書少頗有重出(書曰/中興)\n(而清辯過人/恭雖才不多)有人道孝伯常有新意不覺爲煩\n殷仲堪䘮後桓玄問仲文卿家仲堪定是何似人仲\n文曰雖不能休明一世足以映徹九泉(仲堪仲文之/續晉陽秋曰)\n<!-- kanripo-page source-line=417: <pb:KR3l0002_SBCK_003-19b> -->\n(有美譽/從兄也少)\n`
- Wikisource SBCK: `located`; page `Page:Sibu Congkan0463-劉義慶-世説新語-3-2.djvu/145`; bounded reading: `司馬太傅爲二王目曰孝伯亭`
- adjacent-boundary order: `ordered`; positions `{'previous': 4892, 'current': 4951, 'next': 4972}`

---

#### discrepancy-119 — missing_kanripo_passage

- classification: `missing_entry`; confidence: `high`
- source discrepancy: `missing_kanripo_passage`; source record index: `119`
- review reason: The primary witness omission corresponds to explicit current canonical gap entries supported by Wikisource; no additional entry is missing from the canonical structure.
- recommended action: No new repair in this task. The current manifest already records the primary-witness gap explicitly; do not alter raw Kanripo text.
- canonical chapter structure: `156` entries; gap ordinals `[84, 85]`; partial ordinals `[86]`; ordinal continuity `True`
- Kanripo SBCK bounded record: `154` historical entries, `4909` main characters; context: `下共推之謝公稱藍田掇皮皆真桓温行經王敦墓邊過望之云可兒可兒殷中軍道王右軍云逸少清貴人吾於之甚至一時無所後王仲祖稱殷淵源非以長勝人處長亦勝人王司州與殷中軍語嘆云巳之府奥蚤已傾冩而見殷陳勢浩汗衆源未可得測王長史謂林公真長可謂金玉滿堂林公曰金玉滿淵源真可王曰卿故墮其雲霧中劉尹每稱王長史云性至通而自然有節王右軍道謝萬石在林澤中爲自遒上歎林公器朗神儁道祖士少風領毛骨恐没世不復見如此人道劉真長標雲柯而不扶踈簡文目庾赤玉省率治除謝仁祖云庾赤玉匈中無宿物殷中軍道韓太常曰康伯少自標置居然是出羣器及其發言遣辭往往有情致簡文道王懷祖才既不長於榮利又不淡直以真率少許便足對人多多許林公謂王右軍云長史作數百語無非德音如恨不苦王曰長史自不欲苦物殷中軍與人書道謝萬文理轉遒成殊不易王長史云江思悛思懷所通不`
- Wikisource SBCK bounded record: `5038` main characters; context: `下共推之謝公稱藍田掇皮皆真⟦{{SKchar|3129}}⟧温行經王敦墓邊過望之云可兒可兒殷中軍道王右軍云逸少清貴人吾於之甚至一時無所後王仲祖稱殷淵源非以長勝人處長亦勝人王司州與殷中軍語嘆云巳之府奥蚤已傾冩而見殷陳勢浩汗衆源未可得測王長史謂林公真長可謂金玉滿堂林公曰金玉滿堂復何為簡選王曰非爲簡選直致言處自寡耳王長史道江道羣人所應有乃不必有人所應無已必無會稽孔沉魏顗虞球虞存謝奉並是四族之儁于時之傑孫興公目之曰沉爲孔家金顗爲魏家玉虞爲長琳宗謝爲弘道伏王仲祖劉真長造殷中軍談談竟俱載去劉謂王曰淵源真可王曰卿故墮其雲霧中劉尹每稱王長史云性至通而自然有節王右軍道謝萬石在林澤中爲自遒上歎林公器朗神儁道祖士少風領毛骨恐没世不復見如此人道劉真長標雲柯而不扶踈簡文目𢈔赤玉省率治除謝仁祖云𢈔赤玉𦙄中無宿物殷中軍道韓太常曰康伯少自標置…`
- comparison metrics: sequence ratio `0.973158`, length delta `129`, annotation delta `6`
- affected canonical boundary: `08-shangyu-084` opening `王長史道江道羣人所應有乃不必有人所應無已必無`; primary status `gap`, supplement `shishuo-wikisource-sbck`
- affected canonical boundary: `08-shangyu-085` opening `會稽孔沉魏顗虞球虞存謝奉並是四族之儁于時之傑孫興`; primary status `gap`, supplement `shishuo-wikisource-sbck`

---

### 09-pinzao — 品藻第九

#### discrepancy-123 — 09-pinzao-015

- classification: `harmless_alignment_difference`; confidence: `high`
- source discrepancy: `unmatched_entry_opening`; source record index: `123`
- review reason: The same-edition witness locates the same opening in the current boundary order; differences are glyph templates or attested witness forms.
- recommended action: No repair in this task. Preserve the current canonical boundary and all witness spellings.
- canonical boundary: `09-pinzao-015` ordinal `15`, primary status `present`, anchor `王大將軍下庾公問聞卿有四`
- canonical source position: normalized line `561`, source line `516`, page `<pb:KR3l0002_SBCK_003-24a>`
- Kanripo SBCK: `present`; context: `曰周顗比臣有國士門風(曰伯仁清/鄧粲晉紀)\n(德望稱之/正嶷然以)\n<!-- kanripo-page source-line=516: <pb:KR3l0002_SBCK_003-24a> -->\n王大將軍下庾公問聞卿有四友何者是荅曰君家\n中郎我家太尉阿平胡母彦國(之少有雅俗鑒識與/八王故事曰胡母輔)\n(甫爲四友今故荅也/王澄庾敳王敦王夷)阿平故當最劣庾曰似未肯劣\n庾又問何者居其右王曰自有人又問何者是王曰\n噫其自有公論左右躡公公乃止(者在巳也/敦自謂右)\n人問丞相周侯何如和嶠荅曰長輿嵯櫱(曰嶠厚自/虞預晉書)\n(然不羣/封植嶷)\n明帝問謝鯤君自謂何如庾亮荅曰端委廟堂使百\n僚凖則臣不如亮一丘一壑自謂過之(隨王敦下入/晉陽秋曰鯤)\n(`
- Wikisource SBCK: `located`; page `Page:Sibu Congkan0463-劉義慶-世説新語-3-2.djvu/155`; bounded reading: `王大將軍下𢈔公問聞卿有四`
- adjacent-boundary order: `ordered`; positions `{'previous': 707, 'current': 743, 'next': 820}`

---

#### discrepancy-129 — 09-pinzao-038

- classification: `harmless_alignment_difference`; confidence: `high`
- source discrepancy: `unmatched_entry_opening`; source record index: `129`
- review reason: The same-edition witness locates the same opening in the current boundary order; differences are glyph templates or attested witness forms.
- recommended action: No repair in this task. Preserve the current canonical boundary and all witness spellings.
- canonical boundary: `09-pinzao-038` ordinal `38`, primary status `present`, anchor `殷侯既廢桓公語諸人曰少時`
- canonical source position: normalized line `645`, source line `600`, page `<pb:KR3l0002_SBCK_003-27b>`
- Kanripo SBCK: `present`; context: `讓也\n桓大司馬下都問真長曰聞會稽王語竒進爾邪(温/桓)\n(督中外諸軍事侍中大司馬加黄鉞使入㕘朝政/别傳曰興寧九年以温克復舊京肅静華夏進都)劉\n曰極進然故是第二流中人耳桓曰第一流復是誰\n劉曰正是我輩耳\n殷侯既廢桓公語諸人曰少時與淵源共騎竹馬我\n棄去巳輒取之故當出我下(引殷浩爲揚州欲以抗/續晉陽秋曰簡文輔政)\n(未之憚也/桓桓素輕浩)\n<!-- kanripo-page source-line=604: <pb:KR3l0002_SBCK_003-28a> -->\n人問撫軍殷浩談竟何如荅曰不能勝人差可獻酬\n羣心\n簡文云謝安南清令不如其弟(氏譜曰奉弟聘字弘/安南謝奉也巳見謝)\n(廷尉卿/逺歴侍中)學義不及孔巖(山隂人父儉黄門侍郎巖/中興書`
- Wikisource SBCK: `located`; page `Page:Sibu Congkan0463-劉義慶-世説新語-3-2.djvu/162`; bounded reading: `殷侯既廢⟦{{SKchar|3129}}⟧公語諸人曰少時`
- adjacent-boundary order: `ordered`; positions `{'previous': 1593, 'current': 1640, 'next': 1671}`

---

#### discrepancy-135 — 09-pinzao-065

- classification: `harmless_alignment_difference`; confidence: `high`
- source discrepancy: `unmatched_entry_opening`; source record index: `135`
- review reason: The same-edition witness locates the same opening in the current boundary order; differences are glyph templates or attested witness forms.
- recommended action: No repair in this task. Preserve the current canonical boundary and all witness spellings.
- canonical boundary: `09-pinzao-065` ordinal `65`, primary status `present`, anchor `簡文問孫興公袁羊何似荅曰`
- canonical source position: normalized line `743`, source line `698`, page `<pb:KR3l0002_SBCK_003-32a>`
- Kanripo SBCK: `present`; context: `自此以還吾皆百之(巳見/庾龢)\n王僧恩輕林公藍田曰勿學汝兄汝兄自不如伊(恩/僧)\n(知名尚尋陽公主仕至中書郎未三十而卒坦之悼/王禕之小字也王氏世家曰禕之字文劭述次子少)\n(贈散騎常侍/念與桓温稱之)\n簡文問孫興公袁羊何似荅曰不知者不負其才知\n之者無取其體(而無德也/言其有才)\n蔡叔子云韓康伯雖無骨榦然亦膚立\n郗嘉賔問謝太傅曰林公談何如嵇公謝云嵇公勤\n<!-- kanripo-page source-line=703: <pb:KR3l0002_SBCK_003-32b> -->\n著脚裁可得去耳(風期所得自然超邁也/支遁傳曰遁神悟機發)又問殷何\n如支謝曰正爾有超㧞支乃過殷然亹亹論辯恐口\n欲制支\n庾道季云廉頗藺相如雖千載上死人懔懔恒如有`
- Wikisource SBCK: `located`; page `Page:Sibu Congkan0463-劉義慶-世説新語-3-2.djvu/171`; bounded reading: `簡文問孫興公⟦{{SKchar|2783}}⟧羊何似荅曰`
- adjacent-boundary order: `ordered`; positions `{'previous': 2473, 'current': 2492, 'next': 2518}`

---

#### discrepancy-142 — 09-pinzao-088

- classification: `harmless_alignment_difference`; confidence: `high`
- source discrepancy: `unmatched_entry_opening`; source record index: `142`
- review reason: The same-edition witness locates the same opening in the current boundary order; differences are glyph templates or attested witness forms.
- recommended action: No repair in this task. Preserve the current canonical boundary and all witness spellings.
- canonical boundary: `09-pinzao-088` ordinal `88`, primary status `present`, anchor `舊以桓謙比殷仲文(尚書僕射中軍將軍晉安帝紀/中興書曰謙字敬祖沖第三子)\n(噐貌才思/曰仲文有)桓玄時仲`
- canonical source position: normalized line `832`, source line `787`, page `<pb:KR3l0002_SBCK_003-36a>`
- Kanripo SBCK: `present`; context: `常曰我何如謝太傅(仲璋南陽人祖遐/劉瑾集敘曰瑾字)\n(瑾有才力歷尚書太常卿/父畼畼娶王羲之女生瑾)劉荅曰公高太傅深又曰\n何如賢舅子敬荅曰樝梨橘柚各有其美(梨橘柚其/莊子曰樝)\n(可於口也/味相反皆)\n舊以桓謙比殷仲文(尚書僕射中軍將軍晉安帝紀/中興書曰謙字敬祖沖第三子)\n(噐貌才思/曰仲文有)桓玄時仲文入桓於庭中望見之謂同坐\n曰我家中軍那得及此也\n<!-- kanripo-page source-line=791: <pb:KR3l0002_SBCK_003-36b> -->\n`
- Wikisource SBCK: `located`; page `Page:Sibu Congkan0463-劉義慶-世説新語-3-2.djvu/179`; bounded reading: `舊以⟦{{SKchar|3129}}⟧謙比殷仲文⟦{{SKchar|3129}}⟧玄時仲`
- adjacent-boundary order: `partially_ordered`; positions `{'previous': 3281, 'current': 3320, 'next': None}`

---

### 10-guizhen — 規箴第十

#### discrepancy-145 — 10-guizhen-015

- classification: `harmless_alignment_difference`; confidence: `high`
- source discrepancy: `unmatched_entry_opening`; source record index: `145`
- review reason: The same-edition witness locates the same opening in the current boundary order; differences are glyph templates or attested witness forms.
- recommended action: No repair in this task. Preserve the current canonical boundary and all witness spellings.
- canonical boundary: `10-guizhen-015` ordinal `15`, primary status `present`, anchor `王丞相爲揚州遣八部從事之`
- canonical source position: normalized line `960`, source line `915`, page `<pb:KR3l0002_SBCK_003-42a>`
- Kanripo SBCK: `present`; context: `age source-line=912: <pb:KR3l0002_SBCK_003-42a> -->\n欲言其所見意滿口重辭殊不流王公攝其次曰後\n靣未期亦欲盡所懷願公勿復談郄遂大瞋冰衿而\n出不得一言\n王丞相爲揚州遣八部從事之職顧和時為下傳還\n同時俱見諸從事各奏二千石官長得失至和獨無\n言王問顧曰卿何所聞荅曰明公作輔寧使網漏吞\n舟何縁采聽風聞以爲察察之政丞相咨嗟稱佳諸\n從事自視缺然也\n蘇峻東征沈充(諂事王敦敦克京邑以充爲車騎將/晉陽秋曰充字士居吳興人少好兵)\n(曰男兒不建豹尾不復歸矣敦死充將吳儒斬首於/軍領吳國内史明帝伐王敦充率衆就王舍謂其妻)\n<!-- kanripo-page source-line=923: <pb:KR3l000`
- Wikisource SBCK: `located`; page `Page:Sibu Congkan0463-劉義慶-世説新語-3-2.djvu/191`; bounded reading: `王丞相爲⟦{{SKchar|3951}}⟧州遣八部從事之`
- adjacent-boundary order: `ordered`; positions `{'previous': 1002, 'current': 1117, 'next': 1204}`

---

#### discrepancy-147 — 10-guizhen-019

- classification: `harmless_alignment_difference`; confidence: `high`
- source discrepancy: `unmatched_entry_opening`; source record index: `147`
- review reason: The same-edition witness locates the same opening in the current boundary order; differences are glyph templates or attested witness forms.
- recommended action: No repair in this task. Preserve the current canonical boundary and all witness spellings.
- canonical boundary: `10-guizhen-019` ordinal `19`, primary status `present`, anchor `羅君章爲桓宣武從事(爲部從事桓温臨州轉叅軍/含别傳曰刺史庾亮初命含)\n謝鎭西`
- canonical source position: normalized line `981`, source line `936`, page `<pb:KR3l0002_SBCK_003-43a>`
- Kanripo SBCK: `present`; context: `名軰豈應狂)\n<!-- kanripo-page source-line=934: <pb:KR3l0002_SBCK_003-43a> -->\n一坐莫荅長史江虨曰願明公爲桓文之事不願作\n漢高魏武也\n羅君章爲桓宣武從事(爲部從事桓温臨州轉叅軍/含别傳曰刺史庾亮初命含)\n謝鎭西作江夏往檢校之(武將軍江夏相/中興書曰尚爲建)羅既至\n初不問郡事徑就謝數日飲酒而還桓公問有何事\n君章云不審公謂謝尚何似人桓公曰仁祖是勝我\n許人君章云豈有勝公人而行非者故一無所問桓\n公竒其意而不責也\n王右軍與王敬仁許玄度並善二人亡後右軍爲論\n議更克孔巖誡之曰明府昔與王許周旋有情及逝\n<!-- kanripo-page source-line=945: <pb:KR`
- Wikisource SBCK: `located`; page `Page:Sibu Congkan0463-劉義慶-世説新語-3-2.djvu/193`; bounded reading: `羅君章爲⟦{{SKchar|3129}}⟧宣武從事謝鎭西`
- adjacent-boundary order: `ordered`; positions `{'previous': 1309, 'current': 1357, 'next': 1447}`

---

### 11-jiewu — 捷悟第十一

#### discrepancy-153 — 11-jiewu-006

- classification: `harmless_alignment_difference`; confidence: `high`
- source discrepancy: `unmatched_entry_opening`; source record index: `153`
- review reason: The same-edition witness locates the same opening in the current boundary order; differences are glyph templates or attested witness forms.
- recommended action: No repair in this task. Preserve the current canonical boundary and all witness spellings.
- canonical boundary: `11-jiewu-006` ordinal `6`, primary status `present`, anchor `郄司空在北府桓宣武惡其居`
- canonical source position: normalized line `1069`, source line `1024`, page `<pb:KR3l0002_SBCK_003-47a>`
- Kanripo SBCK: `present`; context: `nripo-page source-line=1022: <pb:KR3l0002_SBCK_003-47a> -->\n吏至徒跣下地謝曰天威在顔遂使温嶠不容得謝\n嶠於是下謝帝廼釋然諸公共嘆王機悟名言\n郄司空在北府桓宣武惡其居兵權(州人多勁悍號/南徐州記曰徐)\n(酒可飲箕可用兵可使/精兵故桓温常曰京口)郄於事機素暗遣牋詣桓方\n欲共奬王室脩復園陵世子嘉賔出行於道上聞信\n至急取牋視竟寸寸毁裂便回還更作牋自陳老病\n不堪人間欲乞閑地自養宣武得牋大喜即詔轉公\n督五郡會稽太守(求申勸平北將軍愔及袁真等嚴/晉陽秋曰大司馬將討慕容暐表)\n(書愔辭此行温責其不從轉授會稽世説爲謬/辦愔以羸疾求退詔大司馬領愔所任按中興)\n王東亭作宣武主簿嘗春月與石頭兄弟乗`
- Wikisource SBCK: `located`; page `Page:Sibu Congkan0463-劉義慶-世説新語-3-2.djvu/201`; bounded reading: `郄司空在北府⟦{{SKchar|3129}}⟧宣武惡其居`
- adjacent-boundary order: `ordered`; positions `{'previous': 293, 'current': 385, 'next': 477}`

---

### 12-suhui — 夙惠第十二

#### discrepancy-155 — 12-suhui-007

- classification: `harmless_alignment_difference`; confidence: `high`
- source discrepancy: `unmatched_entry_opening`; source record index: `155`
- review reason: The same-edition witness locates the same opening in the current boundary order; differences are glyph templates or attested witness forms.
- recommended action: No repair in this task. Preserve the current canonical boundary and all witness spellings.
- canonical boundary: `12-suhui-007` ordinal `7`, primary status `present`, anchor `桓宣武薨桓南郡年五歲服始`
- canonical source position: normalized line `1117`, source line `1072`, page `<pb:KR3l0002_SBCK_003-49a>`
- Kanripo SBCK: `present`; context: `不箸複衣但箸單練衫\n五六重夜則累茵褥謝公諌曰聖體冝令有常陛下\n晝過冷夜過熱恐非攝養之術帝曰晝動夜静(曰躁/老子)\n(夜静寒宜重肅也/勝寒静勝熱此言)謝公出嘆曰上理不減先帝(帝善/簡文)\n(也/言理)\n桓宣武薨桓南郡年五歲服始除桓車騎與送故文\n武别(遷車騎將軍都督七州諸軍事/桓沖别傳曰沖字玄叔温弟也累)因指語南郡\n此皆汝家故吏佐玄應聲慟哭酸感傍人車騎每自\n目巳坐曰靈寳成人當以此坐還之(小字也/靈寳玄)鞠愛過\n<!-- kanripo-page source-line=1077: <pb:KR3l0002_SBCK_003-49b> -->\n於所生\n`
- Wikisource SBCK: `located`; page `Page:Sibu Congkan0463-劉義慶-世説新語-3-2.djvu/205`; bounded reading: `⟦{{SKchar|3129}}⟧宣武薨⟦{{SKchar|3129}}⟧南郡年五歲服始`
- adjacent-boundary order: `partially_ordered`; positions `{'previous': 427, 'current': 496, 'next': None}`

---

#### discrepancy-156 — annotation_range_difference

- classification: `annotation_boundary_only`; confidence: `medium`
- source discrepancy: `annotation_range_difference`; source record index: `156`
- review reason: Main-text length and sequence remain aligned; the discrepancy is confined to parenthetical/annotation coverage.
- recommended action: No repair in this task. Preserve current boundaries; treat the difference as annotation/layout evidence only.
- canonical chapter structure: `7` entries; gap ordinals `[]`; partial ordinals `[]`; ordinal continuity `True`
- Kanripo SBCK bounded record: `7` historical entries, `563` main characters; context: `見日不見長安司空顧和與時賢共清言張玄之顧敷是中外孫年並七歲在牀邊戲于時聞語神情如不相屬瞑於燈下二兒共叙客主之言都無遺失顧公越席而提其耳曰不意衰宗復生此寳韓康伯數歲家酷貧至大寒止得襦母殷夫人自成之令康伯捉熨斗謂康伯曰且箸襦尋作複㡓兒云巳足不須複㡓也毋問其故荅曰火在熨斗中而柄熱今旣箸𥜗下亦當煗故不須耳毋甚異之知爲國噐晉孝武年十二時冬天晝日不箸複衣但箸單練衫五六重夜則累茵褥謝公諌曰聖體冝令有常陛下晝過冷夜過熱恐非攝養之術帝曰晝動夜静謝公出嘆曰上理不減先帝桓宣武薨桓南郡年五歲服始除桓車騎與送故文武别因指語南郡此皆汝家故吏佐玄應聲慟哭酸感傍人車騎每自目巳坐曰靈寳成人當以此坐還之鞠愛過於所生`
- Wikisource SBCK bounded record: `563` main characters; context: `見日不見長安司空顧和與時賢共清言張玄之顧敷是中外孫年並七歲在牀邊戲于時聞語神情如不相屬瞑於燈下二兒共叙客主之言都無遺失顧公越席而提其耳曰不意衰宗復生此寳韓康伯數歲家酷貧至大寒止得襦母殷夫人自成之令康伯捉熨斗謂康伯曰且箸襦尋作複㡓兒云巳足不須⟦{{SKchar|3435}}⟧㡓也毋問其故荅曰火在熨斗中而柄⟦{{SKchar|3289}}⟧今旣箸⟦{{SKchar|383}}⟧下亦當煗故不須耳毋甚異之知爲國噐晉孝武年十二時冬天晝日不箸複衣但箸單練衫五六重夜則累茵褥謝公諌曰聖體冝令有常陛下晝過冷夜過⟦{{SKchar|3289}}⟧恐非攝養之術帝曰晝動夜静謝公出嘆曰上理不減先帝⟦{{SKchar|3129}}⟧宣武薨⟦{{SKchar|3129}}⟧南郡年五歲服始除⟦{{SKchar|3129}}⟧車騎與送故文武别因…`
- comparison metrics: sequence ratio `0.987567`, length delta `0`, annotation delta `4`

---

### 14-rongzhi — 容止第十四

#### discrepancy-167 — 14-rongzhi-026

- classification: `harmless_alignment_difference`; confidence: `high`
- source discrepancy: `unmatched_entry_opening`; source record index: `167`
- review reason: The same-edition witness locates the same opening in the current boundary order; differences are glyph templates or attested witness forms.
- recommended action: No repair in this task. Preserve the current canonical boundary and all witness spellings.
- canonical boundary: `14-rongzhi-026` ordinal `26`, primary status `present`, anchor `王右軍見杜弘治歎曰面如凝`
- canonical source position: normalized line `1291`, source line `1234`, page `<pb:KR3l0002_SBCK_002-5a>`
- Kanripo SBCK: `present`; context: `應世蠖屈其迹而/孫綽庾亮碑文曰公雅好所託常在)\n(以玄對山水/方寸湛然固)\n王敬豫有美形問訊王公王公撫其肩曰阿奴恨才\n不稱又云敬豫事事似王公(殿廷㑹見丞相便覺清/語林曰謝公云小時在)\n(拂人/風來)\n王右軍見杜弘治歎曰面如凝脂眼如㸃漆此神仙\n中人(中朝人士或曰杜弘治清標令上為後來之美/江左名士傳曰永和中劉真長謝仁祖共商略)\n(漆粗可得方諸衛玠/又面如凝脂眼如㸃)時人有稱王長史形者蔡公曰\n恨諸人不見杜弘治耳\n劉尹道桓公鬢如反猬皮眉如紫石稜自是孫仲謀\n<!-- kanripo-page source-line=1240: <pb:KR3l0002_SBCK_002-5b> -->\n司馬宣王一流人(故名温吳志曰孫權字仲謀䇿弟/宋明帝文章志`
- Wikisource SBCK: `located`; page `Page:Sibu Congkan0464-劉義慶-世説新語-3-3.djvu/10`; bounded reading: `王右軍見杜𢎞治歎曰面如凝`
- adjacent-boundary order: `ordered`; positions `{'previous': 926, 'current': 957, 'next': 1000}`

---

#### discrepancy-168 — 14-rongzhi-027

- classification: `harmless_alignment_difference`; confidence: `high`
- source discrepancy: `unmatched_entry_opening`; source record index: `168`
- review reason: The same-edition witness locates the same opening in the current boundary order; differences are glyph templates or attested witness forms.
- recommended action: No repair in this task. Preserve the current canonical boundary and all witness spellings.
- canonical boundary: `14-rongzhi-027` ordinal `27`, primary status `present`, anchor `劉尹道桓公鬢如反猬皮眉如`
- canonical source position: normalized line `1295`, source line `1238`, page `<pb:KR3l0002_SBCK_002-5a>`
- Kanripo SBCK: `present`; context: `弘治歎曰面如凝脂眼如㸃漆此神仙\n中人(中朝人士或曰杜弘治清標令上為後來之美/江左名士傳曰永和中劉真長謝仁祖共商略)\n(漆粗可得方諸衛玠/又面如凝脂眼如㸃)時人有稱王長史形者蔡公曰\n恨諸人不見杜弘治耳\n劉尹道桓公鬢如反猬皮眉如紫石稜自是孫仲謀\n<!-- kanripo-page source-line=1240: <pb:KR3l0002_SBCK_002-5b> -->\n司馬宣王一流人(故名温吳志曰孫權字仲謀䇿弟/宋明帝文章志曰温為温嶠所賞)\n(明逹皆禄胙不終唯中弟孝廉形貌魁偉骨體不恒/也漢使者劉琬語人曰吾觀孫氏兄弟雖並有才秀)\n(王天姿傑邁有英雄之略/有大貴之表晉陽秋曰宣)\n王敬倫風姿似父作侍中加授桓公公服從大門入\n桓公望之曰大奴`
- Wikisource SBCK: `located`; page `Page:Sibu Congkan0464-劉義慶-世説新語-3-3.djvu/10`; bounded reading: `劉尹道桓公𩯭如反猬皮眉如`
- adjacent-boundary order: `ordered`; positions `{'previous': 957, 'current': 1000, 'next': 1027}`

---

#### discrepancy-169 — 14-rongzhi-037

- classification: `harmless_alignment_difference`; confidence: `high`
- source discrepancy: `unmatched_entry_opening`; source record index: `169`
- review reason: The same-edition witness locates the same opening in the current boundary order; differences are glyph templates or attested witness forms.
- recommended action: No repair in this task. Preserve the current canonical boundary and all witness spellings.
- canonical boundary: `14-rongzhi-037` ordinal `37`, primary status `present`, anchor `謝公云見林公雙眼黯黯明黒`
- canonical source position: normalized line `1325`, source line `1268`, page `<pb:KR3l0002_SBCK_002-6b>`
- Kanripo SBCK: `present`; context: `若神君(帝美風姿舉/續晉陽秋日)\n(詳/止端)公亦萬夫之望不然僕射何得自没(謝安/僕射)\n海西時諸公每朝朝堂猶暗唯㑹稽王來軒軒如朝\n霞舉\n謝車騎道謝公遊肆復無乃髙唱但恭坐捻鼻顧睞\n便自有寝處山澤閒儀\n謝公云見林公雙眼黯黯明黒孫興公見林公稜稜\n露其爽\n庾長仁與諸弟入吳欲住亭中宿諸弟先上見羣小\n滿屋都無相避意長仁曰我試觀之乃䇿杖將一小\n<!-- kanripo-page source-line=1273: <pb:KR3l0002_SBCK_002-7a> -->\n兒始入門諸客望其神姿一時退匿(說是庾亮/長仁已見一)\n有人歎王恭形茂者云濯濯如春月柳\n`
- Wikisource SBCK: `located`; page `Page:Sibu Congkan0464-劉義慶-世説新語-3-3.djvu/13`; bounded reading: `謝公云見林公⟦{{SKchar|2814}}⟧眼黯黯明黒`
- adjacent-boundary order: `ordered`; positions `{'previous': 1296, 'current': 1325, 'next': 1348}`

---

### 16-qixian — 企羡第十六

#### discrepancy-172 — 16-qixian-004

- classification: `harmless_alignment_difference`; confidence: `high`
- source discrepancy: `unmatched_entry_opening`; source record index: `172`
- review reason: The same-edition witness locates the same opening in the current boundary order; differences are glyph templates or attested witness forms.
- recommended action: No repair in this task. Preserve the current canonical boundary and all witness spellings.
- canonical boundary: `16-qixian-004` ordinal `4`, primary status `present`, anchor `王司州先為庾公記室叅軍後`
- canonical source position: normalized line `1371`, source line `1314`, page `<pb:KR3l0002_SBCK_002-8b>`
- Kanripo SBCK: `present`; context: `雖無絲竹管弦之盛一觴一詠亦足以畼叙幽情/其次是日也天朗氣清惠風和畼娱目騁懐信可樂)\n(等二十六人賦詩如左前餘姚令㑹稽謝勝等十五/矣故列序時人録其所述右將軍司馬太原孫丞公)\n(罰酒各三斗/人不能賦詩)\n王司州先為庾公記室叅軍後取殷浩為長史始到\n庾公欲遣王使下都王自啓求住曰下官希見盛德\n<!-- kanripo-page source-line=1317: <pb:KR3l0002_SBCK_002-9a> -->\n淵源始至猶貪與少日周旋\n郄嘉賓得人以已比符堅大喜\n孟昶未逹時家在京口(人父馥中護軍昶矜嚴有志/晉安帝紀曰昶字彦逹平昌)\n(尹盧循既下昶慮事不濟仰藥而死/局少為王恭所知豫義旗之勲遷丹陽)嘗見王恭乘\n高輿被鶴氅裘于時微雪昶於籬間`
- Wikisource SBCK: `located`; page `Page:Sibu Congkan0464-劉義慶-世説新語-3-3.djvu/17`; bounded reading: `王司州先為⟦{{SKchar|2928}}⟧公記室叅軍後`
- adjacent-boundary order: `ordered`; positions `{'previous': 91, 'current': 116, 'next': 167}`

---

#### discrepancy-173 — annotation_range_difference

- classification: `annotation_boundary_only`; confidence: `medium`
- source discrepancy: `annotation_range_difference`; source record index: `173`
- review reason: Main-text length and sequence remain aligned; the discrepancy is confined to parenthetical/annotation coverage.
- recommended action: No repair in this task. Preserve current boundaries; treat the difference as annotation/layout evidence only.
- canonical chapter structure: `6` entries; gap ordinals `[]`; partial ordinals `[]`; ordinal continuity `True`
- Kanripo SBCK bounded record: `6` historical entries, `217` main characters; context: `丞相拜司空桓廷尉作兩髻葛帬䇿杖路邉窺之歎曰人言阿龍超阿龍故自超不覺至臺門王丞相過江自說昔在洛水邉數與裴成公阮千里諸賢共談道羊曼曰人久以此許卿何須復爾王曰亦不言我須此但欲爾時不可得耳王右軍得人以蘭亭集序方金谷詩序又以已敵石崇甚有欣色王司州先為庾公記室叅軍後取殷浩為長史始到庾公欲遣王使下都王自啓求住曰下官希見盛德淵源始至猶貪與少日周旋郄嘉賓得人以已比符堅大喜孟昶未逹時家在京口嘗見王恭乘高輿被鶴氅裘于時微雪昶於籬間窺之歎曰此真神仙中人`
- Wikisource SBCK bounded record: `217` main characters; context: `丞相拜司空桓廷尉作兩髻葛帬䇿杖路邉窺之歎曰人言阿龍超阿龍故自超不覺至臺門王丞相過江自說昔在洛水邉數與裴成公阮千里諸賢共談道羊曼曰人久以此許卿何須復爾王曰亦不言我須此但欲爾時不可得耳王右軍得人以蘭亭集序方金谷詩序又以已敵石崇甚有欣色王司州先為⟦{{SKchar|2928}}⟧公記室叅軍後取殷浩為長史始到⟦{{SKchar|2928}}⟧公欲遣王使下都王自啓求住曰下官希見盛德淵源始至猶貪與少日周旋郄嘉賓得人以已比符堅大喜孟昶未逹時家在京口嘗見王恭乘高輿被鶴氅裘于時微雪昶於籬間窺之歎曰此真神仙中人`
- comparison metrics: sequence ratio `0.990783`, length delta `0`, annotation delta `7`

---

### 17-shangshi — 傷逝第十七

#### discrepancy-174 — 17-shangshi-006

- classification: `textual_difference_not_structural`; confidence: `medium`
- source discrepancy: `unmatched_entry_opening`; source record index: `174`
- review reason: The same-edition witness locates the opening, but its bounded reading differs in wording/extent; the current boundary order remains supported.
- recommended action: No repair in this task. Preserve the current canonical boundary and all witness spellings.
- canonical boundary: `17-shangshi-006` ordinal `6`, primary status `present`, anchor `衛洗馬以永嘉六年喪謝鯤哭`
- canonical source position: normalized line `1404`, source line `1347`, page `<pb:KR3l0002_SBCK_002-10a>`
- Kanripo SBCK: `present`; context: `此王曰聖人忘情最下不及情情之所\n鍾正在我輩(蚤亡戎過傷痛不許人求之遂至老無/王隱晉書曰戎子綏欲取裴遁女綏既)\n(者/敢取)簡服其言更為之慟(喪子山簡弔之/一說是王夷甫)\n有人哭和長輿曰峨峨若千丈松崩\n衛洗馬以永嘉六年喪謝鯤哭之感動路人(人名曰/永嘉流)\n(薨謝㓜輿發哀於武昌感慟不自勝人問子可血而/玠以六年六月二十日亡葬南昌城許徴墓東玠之)\n<!-- kanripo-page source-line=1350: <pb:KR3l0002_SBCK_002-10b> -->\n(梁折矣何得不哀/致哀如是荅曰棟)咸和中丞相王公教曰衛洗馬當\n改葬此君風流名士海内所瞻可脩薄祭以敦舊好\n(馬明當改葬此君風流名士海内民望可脩三牲之/玠别傳曰玠咸和中`
- Wikisource SBCK: `located`; page `Page:Sibu Congkan0464-劉義慶-世説新語-3-3.djvu/20`; bounded reading: `衛洗馬以喪謝鯤哭之感動路`
- adjacent-boundary order: `ordered`; positions `{'previous': 241, 'current': 255, 'next': 301}`

---

#### discrepancy-176 — 17-shangshi-009

- classification: `harmless_alignment_difference`; confidence: `high`
- source discrepancy: `unmatched_entry_opening`; source record index: `176`
- review reason: The same-edition witness locates the same opening in the current boundary order; differences are glyph templates or attested witness forms.
- recommended action: No repair in this task. Preserve the current canonical boundary and all witness spellings.
- canonical boundary: `17-shangshi-009` ordinal `9`, primary status `present`, anchor `庾文康亡何揚州臨葬云埋玉`
- canonical source position: normalized line `1419`, source line `1362`, page `<pb:KR3l0002_SBCK_002-11a>`
- Kanripo SBCK: `present`; context: `亮子㑹㑹妻父)與亮書及之亮荅曰賢女尚\n<!-- kanripo-page source-line=1361: <pb:KR3l0002_SBCK_002-11a> -->\n少故其宜也感念亡兒若在初没\n庾文康亡何揚州臨葬云埋玉樹箸土中使人情何\n能已已(公於白石祠中許賽車下牛從來未解為此/&KR0679;神記曰初庾亮病術士戴洋曰昔蘇峻事)\n(初鎮武昌出石頭百姓看者於岸歌曰庾公上武昌/鬼所考不可救也明年亮果亡靈鬼志謡徴曰文康)\n(上時翩翩如飛鵶庾公還揚州白馬牽旐車後連徴/翩翩如飛鳥庾公還揚州白馬牽旒旐又曰庾公初)\n(下都葬焉/不入尋薨)\n王長史病篤寝卧燈下轉麈尾視之歎曰如此人曽\n不得四十及亡劉尹臨殯以犀柄麈尾箸柩中因慟\n絶(濛至交及卒惔深`
- Wikisource SBCK: `located`; page `Page:Sibu Congkan0464-劉義慶-世説新語-3-3.djvu/22`; bounded reading: `⟦{{SKchar|2928}}⟧文康亡何⟦{{SKchar|3951}}⟧州臨葬云埋玉`
- adjacent-boundary order: `ordered`; positions `{'previous': 362, 'current': 409, 'next': 432}`

---

#### discrepancy-177 — 17-shangshi-010

- classification: `harmless_alignment_difference`; confidence: `high`
- source discrepancy: `unmatched_entry_opening`; source record index: `177`
- review reason: The same-edition witness locates the same opening in the current boundary order; differences are glyph templates or attested witness forms.
- recommended action: No repair in this task. Preserve the current canonical boundary and all witness spellings.
- canonical boundary: `17-shangshi-010` ordinal `10`, primary status `present`, anchor `王長史病篤寝卧燈下轉麈尾`
- canonical source position: normalized line `1424`, source line `1367`, page `<pb:KR3l0002_SBCK_002-11a>`
- Kanripo SBCK: `present`; context: `(初鎮武昌出石頭百姓看者於岸歌曰庾公上武昌/鬼所考不可救也明年亮果亡靈鬼志謡徴曰文康)\n(上時翩翩如飛鵶庾公還揚州白馬牽旐車後連徴/翩翩如飛鳥庾公還揚州白馬牽旒旐又曰庾公初)\n(下都葬焉/不入尋薨)\n王長史病篤寝卧燈下轉麈尾視之歎曰如此人曽\n不得四十及亡劉尹臨殯以犀柄麈尾箸柩中因慟\n絶(濛至交及卒惔深悼之雖友于之愛不能過也/濛别傳曰濛以永和初卒年三十九沛國劉惔與)\n支道林喪法䖍之後精神霣喪風味轉墜(法䖍道林/支遁傳曰)\n<!-- kanripo-page source-line=1372: <pb:KR3l0002_SBCK_002-11b> -->\n(理義遁甚重之/同學也儁朗有)常謂人曰昔匠石廢斤於郢人(莊子)\n(斵之堊盡而鼻不傷`
- Wikisource SBCK: `located`; page `Page:Sibu Congkan0464-劉義慶-世説新語-3-3.djvu/22`; bounded reading: `王長史病篤⟦{{SKchar|3462}}⟧卧燈下轉麈尾`
- adjacent-boundary order: `ordered`; positions `{'previous': 409, 'current': 432, 'next': 473}`

---

#### discrepancy-180 — major_length_difference

- classification: `textual_difference_not_structural`; confidence: `medium`
- source discrepancy: `major_length_difference`; source record index: `180`
- review reason: The same-edition contexts are aligned and the length delta is explained by witness glyph/template or wording differences, not a new entry boundary.
- recommended action: No repair in this task. Preserve current boundaries; treat the difference as annotation/layout evidence only.
- canonical chapter structure: `19` entries; gap ordinals `[]`; partial ordinals `[]`; ordinal continuity `True`
- Kanripo SBCK bounded record: `19` historical entries, `899` main characters; context: `來臨屍慟哭賓客莫不垂涕哭畢向靈牀曰卿常好我作驢鳴今我為卿作體似真聲賓客皆笑孫舉頭曰使君輩存令此人死王戎喪兒萬子山簡徃省之王悲不自勝簡曰孩抱中物何至於此王曰聖人忘情最下不及情情之所鍾正在我輩簡服其言更為之慟有人哭和長輿曰峨峨若千丈松崩衛洗馬以永嘉六年喪謝鯤哭之感動路人咸和中丞相王公教曰衛洗馬當改葬此君風流名士海内所瞻可脩薄祭以敦舊好顧彦先平生好琴及喪家人常以琴置靈牀上張季鷹徃哭之不勝其慟遂徑上牀鼓琴作數曲竟撫琴曰顧彦先頗復賞此不因又大慟遂不執孝子手而出庾亮兒遭蘇峻難遇害諸葛道明女為庾兒婦既寡將改適與亮書及之亮荅曰賢女尚少故其宜也感念亡兒若在初没庾文康亡何揚州臨葬云埋玉樹箸土中使人情何能已已王長史病篤寝卧燈下轉麈尾視之歎曰如此人曽不得四十及亡劉尹臨殯以犀柄麈尾箸柩中因慟絶支道`
- Wikisource SBCK bounded record: `895` main characters; context: `來臨屍慟哭賓客莫不垂涕哭畢向靈牀曰卿常好我作驢鳴今我為卿作體似真聲賓客皆笑孫舉頭曰使君輩存令此人死王戎喪兒萬子山簡徃省之王悲不自勝簡曰孩抱中物何至於此王曰聖人忘情最下不及情情之所鍾正在我輩簡服其言更為之慟有人哭和長輿曰峨峨若千丈松崩衛洗馬以喪謝鯤哭之感動路人咸和中丞相王公教曰衛洗馬當改葬此君風流名士海内所瞻可脩薄祭以敦舊好顧彦先平生好琴及喪家人常以琴置靈牀上張季鷹徃哭之不勝其慟遂徑上牀鼓琴作數曲竟撫琴曰顧彦先頗復賞此不因又大慟遂不執孝子手而出𢈔亮兒遭蘇峻難遇害諸葛道明女為𢈔兒婦既寡將改適與亮書及之亮荅曰賢女尚少故其宜也感念亡兒若在初没⟦{{SKchar|2928}}⟧文康亡何⟦{{SKchar|3951}}⟧州臨葬云埋玉⟦{{SKchar|3141}}⟧箸土中使人情何能已已王長史病篤⟦{{SKchar|3462…`
- comparison metrics: sequence ratio `0.983278`, length delta `-4`, annotation delta `2`

---

### 18-qiyi — 棲逸第十八

#### discrepancy-183 — missing_kanripo_passage

- classification: `missing_entry`; confidence: `high`
- source discrepancy: `missing_kanripo_passage`; source record index: `183`
- review reason: The primary witness omission corresponds to explicit current canonical gap entries supported by Wikisource; no additional entry is missing from the canonical structure.
- recommended action: No new repair in this task. The current manifest already records the primary-witness gap explicitly; do not alter raw Kanripo text.
- canonical chapter structure: `17` entries; gap ordinals `[2, 11]`; partial ordinals `[12]`; ordinal continuity `True`
- Kanripo SBCK bounded record: `15` historical entries, `732` main characters; context: `匱乏村人亦如之甚厚為鄉閭所安南陽翟道淵與汝南周子南少相友共隐于尋陽庾太尉說周以當世之務周遂仕翟秉志彌固其後周詣翟翟不與語孟萬年及弟少孤居武昌陽新縣萬年遊宦有盛名當世少孤未嘗出京邑人士思欲見之乃遣信報少孤云兄病篤狼狽至都時賢見之者莫不嗟重因相謝太傅曰卿兄弟志業何其太殊戴曰下官不堪其憂家弟不改其樂許玄度隱在永興南幽穴中每致四方諸侯之遺或謂許曰嘗聞箕山人似不爾耳許曰筐篚苞苴故當輕於天下之寳耳范宣未嘗入公門韓康伯與同載遂誘俱入郡范便於車後趨下郄超每聞欲高尚隱退者輙為辦百萬資并為造立居宇在剡為戴公起宅甚精整戴始往舊居與所親書曰近至剡如官舍郄為傅約亦辦百萬資傳隐事差互故不果遺許掾好遊山水而體便登陟時人云許非徒有勝情實有濟勝之具郄尚書與謝居士善常稱謝慶緒識見雖不絶人可以累心處都盡`
- Wikisource SBCK bounded record: `911` main characters; context: `匱乏村人亦如之甚厚為鄉閭所安南陽翟道淵與汝南周子南少相友共隐于尋陽𢈔太尉說周以當世之務周遂仕翟秉志彌固其後周詣翟翟不與語孟萬年及弟少孤居武昌陽新縣萬年遊宦有盛名當世少孤未嘗出京邑人士思欲見之乃遣信報少孤云兄病篤狼狽至都時賢見之者莫不嗟重因相謂曰少孤如此萬年可死康僧淵在豫章去郭數十里立精舍㫄連嶺帶長川芳林列於軒庭清流激於堂宇乃閒居研講希心理味𢈔公諸人多往看之觀其運用吐納風流轉佳加已處之怡然亦有以自得聲名乃興後不堪遂出戴安道既厲操東山而其兄欲建式遏之功謝太傅曰卿兄弟志業何其太殊戴曰下官不堪其憂家弟不改其樂許𤣥度隱在永興南幽穴中每致四方諸侯之遺或謂許曰嘗聞箕山人似不爾耳許曰筐篚苞苴故當輕於天下之寳耳范宣未嘗入公門韓康伯與同載遂誘俱入郡范便於車後趨下郄超每聞欲高尚隱𨓆者輙為辦百萬資并為造立居宇在剡為戴公起宅甚精整戴始往…`
- comparison metrics: sequence ratio `0.881315`, length delta `179`, annotation delta `19`
- affected canonical boundary: `18-qiyi-002` opening `嵇康遊於汲郡山中遇道士孫登遂與之遊康臨去登曰君才`; primary status `gap`, supplement `shishuo-wikisource-sbck`
- affected canonical boundary: `18-qiyi-011` opening `康僧淵在豫章去郭數十里立精舍㫄連嶺帶長川芳林列於`; primary status `gap`, supplement `shishuo-wikisource-sbck`

---

### 19-xianyuan — 賢媛第十九

#### discrepancy-186 — 19-xianyuan-029

- classification: `harmless_alignment_difference`; confidence: `high`
- source discrepancy: `unmatched_entry_opening`; source record index: `186`
- review reason: The same-edition witness locates the same opening in the current boundary order; differences are glyph templates or attested witness forms.
- recommended action: No repair in this task. Preserve the current canonical boundary and all witness spellings.
- canonical boundary: `19-xianyuan-029` ordinal `29`, primary status `present`, anchor `郄嘉賔喪婦兄弟欲迎妺還終`
- canonical source position: normalized line `1775`, source line `1719`, page `<pb:KR3l0002_SBCK_002-29a>`
- Kanripo SBCK: `present`; context: `- kanripo-page source-line=1716: <pb:KR3l0002_SBCK_002-29a> -->\n王江州夫人語謝遏曰汝何以都不復進(之妺/夫人玄)為\n是塵務經心天分有限\n郄嘉賔喪婦兄弟欲迎妺還終不肯歸(娶汝南周閔/郗氏譜曰超)\n(馬頭/女名)曰生縱不得與郗郎同室死寜不同穴(榖則異/毛詩曰)\n(曰穴謂壙中墟也/室死則同穴鄭玄注)\n謝遏絶重其姊張玄常稱其妹欲以敵之有濟尼者\n並遊張謝二家人問其優劣荅曰王夫人神情散朗\n故有林下風氣顧家婦清心玉映自是閨房之秀\n王尚書惠嘗看王右軍夫人(人歷吏部尚書贈太常/宋書曰惠字令明琅邪)\n(卿)問眼耳未覺惡不(骸獨存願䝉哀矜賜其鞠養/婦人集載謝表曰妾年九十孤)\n<!-- kan`
- Wikisource SBCK: `located`; page `Page:Sibu Congkan0464-劉義慶-世説新語-3-3.djvu/57`; bounded reading: `郄嘉賔喪婦兄弟欲迎妺還終`
- adjacent-boundary order: `ordered`; positions `{'previous': 2230, 'current': 2256, 'next': 2286}`

---

#### discrepancy-187 — missing_kanripo_passage

- classification: `missing_entry`; confidence: `high`
- source discrepancy: `missing_kanripo_passage`; source record index: `187`
- review reason: The primary witness omission corresponds to explicit current canonical gap entries supported by Wikisource; no additional entry is missing from the canonical structure.
- recommended action: No new repair in this task. The current manifest already records the primary-witness gap explicitly; do not alter raw Kanripo text.
- canonical chapter structure: `32` entries; gap ordinals `[5]`; partial ordinals `[6]`; ordinal continuity `True`
- Kanripo SBCK bounded record: `31` historical entries, `2398` main characters; context: `妾聞死生有命富貴在天脩善尚不蒙福爲邪欲以何望若鬼神有知不受邪佞之訴若其無知訴之何益故不爲也魏武帝崩文帝悉取武帝宫人自侍及帝病困卞后出看疾太后入户見直侍並是昔日所愛幸者太后問何時來邪云正伏魄時過因不復前而歎曰狗䑕不食汝餘死故應爾至山陵亦竟不臨婦曰無憂桓必勸入桓果語許云阮家既嫁醜女與卿故當有意卿宜察之許便回入内既見婦即欲出婦料其此出無復入理便捉𥚑停之許因謂曰婦有四德卿有其幾婦曰新婦所乏唯容爾然士有百行君有幾許云皆僃婦曰夫百行以徳為首君好色不好德何謂皆僃允有慚色遂相敬重許允為吏部郎多用其鄉里魏明帝遣虎賁收之其婦出誡允曰明主可以理奪難以情求既至帝覈問之允對曰舉爾所知臣之郷人臣所知也陛下檢校為稱職與不若不稱職臣受其罪既檢校皆官得其人於是乃釋允衣服敗壞詔賜新衣初允𬒳收舉家號哭阮新婦自`
- Wikisource SBCK bounded record: `2481` main characters; context: `妾聞死生有命富貴在天脩善尚不⟦{{SKchar|3681}}⟧福爲邪欲以何望若⟦{{SKchar|3932}}⟧神有知不受邪佞之訴若其無知訴之何益故不爲也魏武帝崩文帝悉取武帝宫人自侍及帝病困卞后出看疾太后入户見直侍並是昔日所愛幸者太后問何時來邪云正伏魄時過因不復前而歎曰狗䑕不食汝餘死故應爾至山陵亦竟不臨趙母嫁女女臨去敕之曰慎勿為好女曰不為好可為惡邪母曰好尚不可為其況惡乎許允婦是阮衛尉女德如妹竒醜交禮竟允無復入理家人深以為憂㑹允有客至婦令婢視之還荅曰是桓郎桓郎者桓範也婦曰無憂桓必勸入桓果語許云阮家既嫁醜女與卿故當有意卿宜察之許便回入内既見婦即欲出婦料其此出無復入理便捉𥚑停之許因謂曰婦有四德卿有其幾婦曰新婦所乏唯容爾然士有百行君有幾許云皆僃婦曰夫百行以徳為首君好色不好德何謂皆僃允有慚色遂相敬重許允為吏部郎多用其鄉里…`
- comparison metrics: sequence ratio `0.97643`, length delta `83`, annotation delta `13`
- affected canonical boundary: `19-xianyuan-005` opening `趙母嫁女女臨去敕之曰慎勿為好女曰不為好可為惡邪母`; primary status `gap`, supplement `shishuo-wikisource-sbck`

---

### 20-shujie — 術解第二十

#### discrepancy-188 — annotation_range_difference

- classification: `annotation_boundary_only`; confidence: `medium`
- source discrepancy: `annotation_range_difference`; source record index: `188`
- review reason: Main-text length and sequence remain aligned; the discrepancy is confined to parenthetical/annotation coverage.
- recommended action: No repair in this task. Preserve current boundaries; treat the difference as annotation/layout evidence only.
- canonical chapter structure: `11` entries; gap ordinals `[]`; partial ordinals `[]`; ordinal continuity `True`
- Kanripo SBCK bounded record: `11` historical entries, `709` main characters; context: `出天子能致天子問耳郭景純過江居于暨陽墓去水不盈百步時人以爲近水景純曰將當爲陸今沙漲去墓數十里皆爲桑田其詩曰北阜烈烈巨海混混壘壘三墳唯母與昆王丞相令郭璞試作一卦卦成郭意色甚惡云公有震厄王問有可消伏理不郭曰命駕西出數里得一栢樹截斷如公長置牀上常寝處災可消矣王從其語數日中果震栢粉碎子弟皆稱慶大將軍云君乃復委罪於樹木桓公有主簿善别酒有酒輙令先嘗好者謂青州從事惡者謂平原督郵青州有齊郡平原有鬲縣從事言到臍督郵言在鬲上住郗愔信道甚精勤常患腹内惡諸醫不可療聞于法開有名徃迎之旣來便脉云君侯所患正是精進太過所致耳合一劑湯與之一服卽大下去數叚許𥿄如拳大剖看乃先所服符也殷中軍妙解經脉中年都廢有常所給使忽叩頭流血浩問其故云有死事終不可說詰問良久乃云小人母年垂百嵗抱疾來久若䝉官一脉便有活理訖就屠戮無`
- Wikisource SBCK bounded record: `709` main characters; context: `出天子能致天子問耳郭景純過江居于暨陽墓去水不盈百步時人以爲近水景純曰將當爲陸今沙漲去墓數十里皆爲桑田其詩曰北阜烈烈巨海混混壘壘三墳唯母與昆王丞相令郭璞試作一卦卦成郭意色甚惡云公有震厄王問有可消伏理不郭曰命駕西出數里得一栢樹截斷如公長置牀上常⟦{{SKchar|3462}}⟧處災可消矣王從其語數日中果震栢粉碎子弟皆稱慶大將軍云君乃復委罪於樹木桓公有主簿善别酒有酒輙令先嘗好者謂青州從事惡者謂平原督郵青州有齊郡平原有鬲縣從事言到臍督郵言在鬲上住郗愔信道甚精勤常患腹内惡諸醫不可療聞于法開有名徃迎之旣來便脉云君侯所患正是精進太過所致耳合一劑湯與之一服卽大下去數叚許⟦{{SKchar|3505}}⟧如拳大剖看乃先所服符也殷中軍妙解經脉中年都廢有常所給使忽叩頭流血浩問其故云有死事終不可說詰問良久乃云小人母年垂百嵗抱疾來久若䝉…`
- comparison metrics: sequence ratio `0.997179`, length delta `0`, annotation delta `8`

---

### 23-rendan — 任誕第二十三

#### discrepancy-194 — 23-rendan-005

- classification: `harmless_alignment_difference`; confidence: `high`
- source discrepancy: `unmatched_entry_opening`; source record index: `194`
- review reason: The same-edition witness locates the same opening in the current boundary order; differences are glyph templates or attested witness forms.
- recommended action: No repair in this task. Preserve the current canonical boundary and all witness spellings.
- canonical boundary: `23-rendan-005` ordinal `5`, primary status `present`, anchor `步兵校尉缺厨中有貯酒數百`
- canonical source position: normalized line `1965`, source line `1908`, page `<pb:KR3l0002_SBCK_002-37b>`
- Kanripo SBCK: `present`; context: `七賢論/見竹林)\n劉公榮與人飲酒雜穢非類人或譏之荅曰勝公榮\n者不可不與飲不如公榮者亦不可不與飲是公榮\n輩者又不可不與飲故終日共飲而醉(字公榮沛國/劉氏譜曰昶)\n(通逹仕至兖州刺史/人晉陽秋曰昶爲人)\n步兵校尉缺厨中有貯酒數百斛阮籍乃求爲歩兵\n校尉(親愛籍恒與談戲任其所欲不道以職事籍常/文士傳曰籍放誕有傲世情不樂仕宦晉文帝)\n(文帝說從其意籍便騎驢徑到郡皆壊府舍諸壁障/從容曰平生曽遊東平樂其土風願得爲東平太守)\n(聞步兵厨中有酒三百石忻然求爲校尉於是文府/使内外相望然後教令清寜十餘日便復騎驢去後)\n(厨中並醉而死此好事者爲之言籍景元中卒而劉/舍與劉伶酣飲竹林七賢論又云籍與伶共飲步兵)\n<!-- kanripo-page source-`
- Wikisource SBCK: `located`; page `Page:Sibu Congkan0464-劉義慶-世説新語-3-3.djvu/74`; bounded reading: `步兵校尉缺⟦{{SKchar|2936}}⟧中有貯酒數百`
- adjacent-boundary order: `ordered`; positions `{'previous': 263, 'current': 318, 'next': 340}`

---

#### discrepancy-197 — 23-rendan-030

- classification: `harmless_alignment_difference`; confidence: `high`
- source discrepancy: `unmatched_entry_opening`; source record index: `197`
- review reason: The same-edition witness locates the same opening in the current boundary order; differences are glyph templates or attested witness forms.
- recommended action: No repair in this task. Preserve the current canonical boundary and all witness spellings.
- canonical boundary: `23-rendan-030` ordinal `30`, primary status `present`, anchor `蘇峻亂諸庾逃散庾冰時為吳`
- canonical source position: normalized line `2075`, source line `2018`, page `<pb:KR3l0002_SBCK_002-42b>`
- Kanripo SBCK: `present`; context: `)\n(林曰伯仁正有姊喪三日醉姑喪二日醉大損資望/後屢以酒失庾亮曰周侯末年可謂鳯徳之衰也語)\n(常共屯守/每醉諸公)\n衛君長為温公長史温公甚善之每率爾提酒脯就\n衛箕踞相對彌日衛徃温許亦爾(已見/衛永)\n蘇峻亂諸庾逃散庾冰時為吳郡單身奔亡民吏皆\n去唯郡卒獨以小船載冰出錢塘口蘧篨覆之時峻\n賞募覓冰屬所在&KR0679;檢甚急卒捨船市渚因飲酒醉\n還舞棹向船曰何處覓庾吳郡此中便是冰大惶怖\n然不敢動監司見船小装狹謂卒狂醉都不復疑自\n<!-- kanripo-page source-line=2024: <pb:KR3l0002_SBCK_002-43a> -->\n送過淛江寄山隂魏家得免(峻作逆遣軍伐冰冰棄/中興書曰冰為吳郡蘇)\n(㑹稽/郡奔)後`
- Wikisource SBCK: `located`; page `Page:Sibu Congkan0464-劉義慶-世説新語-3-3.djvu/84`; bounded reading: `蘇峻亂諸⟦{{SKchar|2928}}⟧⟦{{SKchar|3745}}⟧散⟦{{SKchar|2928}}⟧冰時為吳`
- adjacent-boundary order: `ordered`; positions `{'previous': 1482, 'current': 1515, 'next': 1700}`

---

#### discrepancy-200 — 23-rendan-038

- classification: `harmless_alignment_difference`; confidence: `high`
- source discrepancy: `unmatched_entry_opening`; source record index: `200`
- review reason: The same-edition witness locates the same opening in the current boundary order; differences are glyph templates or attested witness forms.
- recommended action: No repair in this task. Preserve the current canonical boundary and all witness spellings.
- canonical boundary: `23-rendan-038` ordinal `38`, primary status `present`, anchor `桓車騎在荆州張玄為侍中使`
- canonical source position: normalized line `2119`, source line `2062`, page `<pb:KR3l0002_SBCK_002-44b>`
- Kanripo SBCK: `present`; context: `鄞縣遺心細務縱意游肆名阜勝/中興書曰承公少誕任不羈家於㑹稽性好)\n(歷覽/川靡不)\n袁彦道有二妹一適殷淵源一適謝仁祖(躭大妹名/袁氏譜曰)\n(名女正適謝尚/女皇適殷浩小妹)語桓宣武云恨不更有一人配卿\n桓車騎在荆州張玄為侍中使至江陵路經陽歧村\n(州二百里/村臨江去荆)俄見一人持半小籠生魚徑來造船云\n有魚欲寄作膾張乃維舟而納之問其姓字稱是劉\n遺民(一字遺民已見/中興書曰劉驎之)張素聞其名大相忻待劉既\n知張銜命問謝安王文度並佳不張甚欲話言劉了\n<!-- kanripo-page source-line=2068: <pb:KR3l0002_SBCK_002-45a> -->\n無停意既進膾便去云向得此魚觀君船上當有膾\n具是故來耳於是便去張乃`
- Wikisource SBCK: `located`; page `Page:Sibu Congkan0464-劉義慶-世説新語-3-3.djvu/88`; bounded reading: `桓車騎在荆州張𤣥為侍中使`
- adjacent-boundary order: `ordered`; positions `{'previous': 2018, 'current': 2047, 'next': 2210}`

---

#### discrepancy-203 — major_length_difference

- classification: `textual_difference_not_structural`; confidence: `medium`
- source discrepancy: `major_length_difference`; source record index: `203`
- review reason: The same-edition contexts are aligned and the length delta is explained by witness glyph/template or wording differences, not a new entry boundary.
- recommended action: No repair in this task. Preserve current boundaries; treat the difference as annotation/layout evidence only.
- canonical chapter structure: `54` entries; gap ordinals `[]`; partial ordinals `[]`; ordinal continuity `True`
- Kanripo SBCK bounded record: `54` historical entries, `3097` main characters; context: `民張素聞其名大相忻待劉既知張銜命問謝安王文度並佳不張甚欲話言劉了無停意既進膾便去云向得此魚觀君船上當有膾具是故來耳於是便去張乃追至劉家為設酒殊不清㫖張高其人不得已而飲之方共封飲劉便先起云今正伐荻不宐久廢張亦無以留之王子猷詣郄雍州雍州在内見有[翕*毛]㲪云阿乞那得此物令左右送還家郗出覓之王曰向有大力者負之而趨郄無忤色謝安始出西戯失車半便杖䇿步歸道逢劉尹語曰安石將無傷謝乃同載而歸襄陽羅友有大韻少時多謂之癡嘗伺人祠欲乞食徃太蚤門未開主人迎神出見問以非時何得在此荅曰聞卿祠欲乞一頓食耳遂隱門側至曉得食便退了無怍容為人有記功從桓宣武平蜀按行蜀城闕觀宇内外道陌廣狹植種果竹多少皆黙記之後宣武漂洲與簡文集友亦預焉共道蜀中事亦有所遺忘友皆名列曽無錯漏宣武驗以蜀城闕簿皆如其言坐者歎服謝公云羅友`
- Wikisource SBCK bounded record: `3093` main characters; context: `民張素聞其名大相忻待劉既知張銜命問謝安王文度並佳不張甚欲話言劉了無停意既進膾便去云向得此魚觀君船上當有膾具是故來耳於是便去張乃追至劉家為設酒殊不清㫖張高其人不得已而飲之方共封飲劉便先起云今正伐荻不宐久廢張亦無以留之王子猷詣郄雍州雍州在内見有⟦{{SKchar|1394}}⟧㲪云阿乞那得此物令左右送還家郗出覓之王曰向有大力者⟦{{SKchar|3688}}⟧之而趨郄無忤色謝安始出西戯失車半便杖䇿步歸道逢劉尹語曰安石將無傷謝乃同載而歸襄陽羅友有大韻少時多謂之癡嘗伺人祠欲乞食徃太蚤門未開主人迎神出見問以非時何得在此荅曰聞卿祠欲乞一頓食耳遂隱門側至曉得食便⟦{{SKchar|2385}}⟧了無怍容為人有記功從桓宣武平蜀按行蜀城闕觀宇内外道陌廣狹植種果竹多少皆黙記之後宣武漂洲與簡文集友亦預焉共道蜀中事亦有所遺忘友皆名列曽…`
- comparison metrics: sequence ratio `0.987076`, length delta `-4`, annotation delta `3`

---

### 24-jianao — 簡傲第二十四

#### discrepancy-204 — annotation_range_difference

- classification: `annotation_boundary_only`; confidence: `medium`
- source discrepancy: `annotation_range_difference`; source record index: `204`
- review reason: Main-text length and sequence remain aligned; the discrepancy is confined to parenthetical/annotation coverage.
- recommended action: No repair in this task. Preserve current boundaries; treat the difference as annotation/layout evidence only.
- canonical chapter structure: `17` entries; gap ordinals `[]`; partial ordinals `[]`; ordinal continuity `True`
- Kanripo SBCK bounded record: `17` historical entries, `1209` main characters; context: `以此賞主人乃留坐盡歡而去王子敬自㑹稽經吳聞顧辟疆有名園先不識主人徑徃其家值顧方集賔友酣燕而王遊歴既畢指麾好惡傍若無人顧勃然不堪曰傲主人非禮也以貴驕人非道也失此二者不足齒人傖耳便驅其左右出門王獨在輿上回轉顧望左右移時不至然後令送箸門外怡然不屑`
- Wikisource SBCK bounded record: `1221` main characters; context: `以此賞主人乃留坐盡歡而去王子敬自㑹稽經吳聞顧辟疆有名園先不識主人徑徃其家值顧方集賔友酣燕而王遊歴既畢指麾好惡傍若無人顧勃然不堪曰傲主人非禮也以貴驕人非道也失此二者不足齒人傖耳便驅其左右出門王獨在輿上回轉顧望左右移時不至然後令送箸門外怡然不屑宋臨川王義慶撰梁劉孝標注`
- comparison metrics: sequence ratio `0.993416`, length delta `12`, annotation delta `8`

---

### 25-paidiao — 排調第二十五

#### discrepancy-210 — 25-paidiao-049

- classification: `harmless_alignment_difference`; confidence: `high`
- source discrepancy: `unmatched_entry_opening`; source record index: `210`
- review reason: The same-edition witness locates the same opening in the current boundary order; differences are glyph templates or attested witness forms.
- recommended action: No repair in this task. Preserve the current canonical boundary and all witness spellings.
- canonical boundary: `25-paidiao-049` ordinal `49`, primary status `present`, anchor `郄嘉賓書與袁虎道戴安道謝`
- canonical source position: normalized line `2581`, source line `2525`, page `<pb:KR3l0002_SBCK_002-66b>`
- Kanripo SBCK: `present`; context: `公入咸陽召諸父老曰天下苦秦)\n(抵至也但至於罪/盗抵罪應劭注曰)\n<!-- kanripo-page source-line=2524: <pb:KR3l0002_SBCK_002-66b> -->\n郄嘉賓書與袁虎道戴安道謝居士云恒任之風當\n有所弘耳以袁無恒故以此激之(並已見/袁戴謝)\n范啓與郄嘉賓書曰子敬舉體無饒縱掇皮無餘潤\n郗荅曰舉體無餘潤何如舉體非真者范性矜假多\n煩故嘲之\n二郄奉道二何奉佛皆以財賄謝中郎云二郄謟於\n道二何佞於佛(陽秋曰何充性好佛道崇修佛寺供/中興書曰郗愔及弟曇奉天師道晉)\n(爲遐邇所譏充弟準亦精勤唯讀佛經營治寺廟而/給沙門以百數久在揚州徴役吏民功賞萬計是以)\n(矣/已)\n王文度在西州與林法師講韓孫諸人並在坐林公`
- Wikisource SBCK: `located`; page `Page:Sibu Congkan0464-劉義慶-世説新語-3-3.djvu/131`; bounded reading: `郄嘉賓書與⟦{{SKchar|2783}}⟧虎道戴安道謝`
- adjacent-boundary order: `ordered`; positions `{'previous': 2466, 'current': 2514, 'next': 2547}`

---

### 26-qingdi — 輕詆第二十六

#### discrepancy-215 — 26-qingdi-003

- classification: `harmless_alignment_difference`; confidence: `high`
- source discrepancy: `unmatched_entry_opening`; source record index: `215`
- review reason: The same-edition witness locates the same opening in the current boundary order; differences are glyph templates or attested witness forms.
- recommended action: No repair in this task. Preserve the current canonical boundary and all witness spellings.
- canonical boundary: `26-qingdi-003` ordinal `3`, primary status `present`, anchor `深公云人謂庾元規名士胷中`
- canonical source position: normalized line `2680`, source line `2623`, page `<pb:KR3l0002_SBCK_002-71a>`
- Kanripo SBCK: `present`; context: `不售乃自詣齊宣王乞備後宫因說王以四殆)\n(獻之吳王/子名曰西施)\n<!-- kanripo-page source-line=2623: <pb:KR3l0002_SBCK_002-71a> -->\n深公云人謂庾元規名士胷中柴棘三斗許\n庾公權重足傾王公庾在石頭王在冶城坐大風揚\n塵王以扇拂塵曰元規塵汙人(亮之在武昌傳其應/按王公雅量通濟庾)\n(乎王隱晉書戴洋傳曰丹陽太守王導問洋得病七/下公以識度裁之囂言自息豈或回貳有扇塵之事)\n(昭天此爲金火相爍水火相炒以故相害導呼冶令/年洋曰君侯命在申爲土地之主而於申上冶火光)\n(去宫三里吳時鼓鑄之所吳平猶不廢又云孫權築/奕遜使啓鎭東徙今東冶是也丹陽記曰丹陽冶城)\n(當是徙縣冶空城而置冶爾冶城疑是金`
- Wikisource SBCK: `located`; page `Page:Sibu Congkan0464-劉義慶-世説新語-3-3.djvu/140`; bounded reading: `深公云人謂⟦{{SKchar|2928}}⟧元規名士胷中`
- adjacent-boundary order: `ordered`; positions `{'previous': 27, 'current': 70, 'next': 87}`

---

#### discrepancy-216 — 26-qingdi-004

- classification: `harmless_alignment_difference`; confidence: `high`
- source discrepancy: `unmatched_entry_opening`; source record index: `216`
- review reason: The same-edition witness locates the same opening in the current boundary order; differences are glyph templates or attested witness forms.
- recommended action: No repair in this task. Preserve the current canonical boundary and all witness spellings.
- canonical boundary: `26-qingdi-004` ordinal `4`, primary status `present`, anchor `庾公權重足傾王公庾在石頭`
- canonical source position: normalized line `2681`, source line `2624`, page `<pb:KR3l0002_SBCK_002-71a>`
- Kanripo SBCK: `present`; context: `)\n(獻之吳王/子名曰西施)\n<!-- kanripo-page source-line=2623: <pb:KR3l0002_SBCK_002-71a> -->\n深公云人謂庾元規名士胷中柴棘三斗許\n庾公權重足傾王公庾在石頭王在冶城坐大風揚\n塵王以扇拂塵曰元規塵汙人(亮之在武昌傳其應/按王公雅量通濟庾)\n(乎王隱晉書戴洋傳曰丹陽太守王導問洋得病七/下公以識度裁之囂言自息豈或回貳有扇塵之事)\n(昭天此爲金火相爍水火相炒以故相害導呼冶令/年洋曰君侯命在申爲土地之主而於申上冶火光)\n(去宫三里吳時鼓鑄之所吳平猶不廢又云孫權築/奕遜使啓鎭東徙今東冶是也丹陽記曰丹陽冶城)\n(當是徙縣冶空城而置冶爾冶城疑是金陵本治漢/冶城爲鼓鑄之所旣立石頭大塢`
- Wikisource SBCK: `located`; page `Page:Sibu Congkan0464-劉義慶-世説新語-3-3.djvu/140`; bounded reading: `⟦{{SKchar|2928}}⟧公權重足傾王公⟦{{SKchar|2928}}⟧在石頭`
- adjacent-boundary order: `ordered`; positions `{'previous': 70, 'current': 87, 'next': 119}`

---

### 27-jiajue — 假譎第二十七

#### discrepancy-224 — 27-jiajue-001

- classification: `harmless_alignment_difference`; confidence: `high`
- source discrepancy: `unmatched_entry_opening`; source record index: `224`
- review reason: The same-edition witness locates the same opening in the current boundary order; differences are glyph templates or attested witness forms.
- recommended action: No repair in this task. Preserve the current canonical boundary and all witness spellings.
- canonical boundary: `27-jiajue-001` ordinal `1`, primary status `present`, anchor `魏武少時甞與袁紹好為游俠`
- canonical source position: normalized line `2835`, source line `2779`, page `<pb:KR3l0002_SBCK_002-78a>`
- Kanripo SBCK: `present`; context: `　　　　假譎第二十七\n魏武少時甞與袁紹好為游俠觀人新婚因潜入主\n人園中夜呌呼云有偷兒賊青廬中人皆出觀魏武\n乃入抽刃劫新婦與紹還出失道墜枳棘中紹不能\n得動復大呌云偷兒在此紹遑迫自擲出遂以俱免\n(語云武王少好俠放蕩不修行業甞私入常侍張讓/曹瞞傳曰操小字阿瞞少好譎詐逰放無度孫盛雜)\n(出有絶人力故莫之能害也/宅中讓乃手㦸於庭踰垣而)\n魏武行役失汲道軍皆渇乃令曰前有大梅林饒子\n甘酸可以解渇士卒聞之口皆出水乗此得及前源\n魏武常言人欲危己已輒心動因語所親小人曰汝\n<!-`
- Wikisource SBCK: `located`; page `Page:Sibu Congkan0464-劉義慶-世説新語-3-3.djvu/154`; bounded reading: `魏武少時甞與𡊮紹好為游俠`
- adjacent-boundary order: `partially_ordered`; positions `{'previous': None, 'current': 0, 'next': 80}`

---

#### discrepancy-226 — 27-jiajue-010

- classification: `harmless_alignment_difference`; confidence: `high`
- source discrepancy: `unmatched_entry_opening`; source record index: `226`
- review reason: The same-edition witness locates the same opening in the current boundary order; differences are glyph templates or attested witness forms.
- recommended action: No repair in this task. Preserve the current canonical boundary and all witness spellings.
- canonical boundary: `27-jiajue-010` ordinal `10`, primary status `present`, anchor `諸葛令女庾氏婦既寡誓云不`
- canonical source position: normalized line `2901`, source line `2844`, page `<pb:KR3l0002_SBCK_002-81a>`
- Kanripo SBCK: `present`; context: `亂起兵死聦嗣/琨假守左司馬都督上前鋒諸軍事討劉聦晉陽秋)\n<!-- kanripo-page source-line=2843: <pb:KR3l0002_SBCK_002-81a> -->\n(業)\n諸葛令女庾氏婦既寡誓云不復重出此女性甚正\n疆無有登車理(父虨已見上/即庾亮子㑹妻)恢既許江思玄㛰乃\n移家近之初誑女云宐徙於是家人一時去獨留女\n在後比其覺已不復得出江郎莫來女哭詈彌甚積\n日漸歇江虨暝入宿恒在對牀上後觀其意轉帖虨\n乃詐厭良久不悟聲氣轉急女乃呼婢云喚江郎覺\n江於是躍來就之曰我自是天下男子厭何預卿事\n而見喚邪既爾相關不得不與人語女黙然而慙情\n義遂篤(正典習蠻夷之穢行康王之言所輕多矣/葛令之清英江君之茂識必不背聖人之)\n<!-- `
- Wikisource SBCK: `located`; page `Page:Sibu Congkan0464-劉義慶-世説新語-3-3.djvu/160`; bounded reading: `諸葛令女⟦{{SKchar|2928}}⟧氏婦既寡誓云不`
- adjacent-boundary order: `ordered`; positions `{'previous': 700, 'current': 843, 'next': 1000}`

---

### 28-chumian — 黜免第二十八

#### discrepancy-230 — 28-chumian-003

- classification: `harmless_alignment_difference`; confidence: `high`
- source discrepancy: `unmatched_entry_opening`; source record index: `230`
- review reason: The same-edition witness locates the same opening in the current boundary order; differences are glyph templates or attested witness forms.
- recommended action: No repair in this task. Preserve the current canonical boundary and all witness spellings.
- canonical boundary: `28-chumian-003` ordinal `3`, primary status `present`, anchor `殷中軍𬒳廢在信安終日恒書`
- canonical source position: normalized line `2952`, source line `2895`, page `<pb:KR3l0002_SBCK_002-83a>`
- Kanripo SBCK: `present`; context: `/荆州記曰)\n(猨長嘯屬引清逺漁者歌曰巴東三峽巫峽長猿鳴/里兩㟁連山略無絶處重巖疊障隱天蔽日常有髙)\n(沾裳/一聲淚)其母縁岸哀號行百餘里不去遂跳上船至\n便即絶破視其腹中腸皆寸寸斷公聞之怒命黜其\n人\n殷中軍𬒳廢在信安終日恒書空作字揚州吏民尋\n義逐之竊視唯作咄咄怪事四字而已(浩以中軍將/晉陽秋曰初)\n<!-- kanripo-page source-line=2898: <pb:KR3l0002_SBCK_002-83b> -->\n(關中有變符徤死浩偽率軍而行云修復山陵襄前/軍鎮壽陽羌姚襄上書歸降後有罪浩隂圖誅之㑹)\n(據山桑焚其舟實至壽陽略流民而還浩士卒多叛/驅恐遂反軍至山桑聞襄將至棄輜重馳保譙襄至)\n(名為民浩馳還謝罪既而遷于東陽`
- Wikisource SBCK: `located`; page `Page:Sibu Congkan0464-劉義慶-世説新語-3-3.djvu/164`; bounded reading: `殷中軍⟦{{SKchar|3425}}⟧廢在信安終日⟦{{SKchar|2989}}⟧書`
- adjacent-boundary order: `ordered`; positions `{'previous': 74, 'current': 128, 'next': 163}`

---

#### discrepancy-233 — annotation_range_difference

- classification: `annotation_boundary_only`; confidence: `medium`
- source discrepancy: `annotation_range_difference`; source record index: `233`
- review reason: Main-text length and sequence remain aligned; the discrepancy is confined to parenthetical/annotation coverage.
- recommended action: No repair in this task. Preserve current boundaries; treat the difference as annotation/layout evidence only.
- canonical chapter structure: `9` entries; gap ordinals `[]`; partial ordinals `[]`; ordinal continuity `True`
- Kanripo SBCK bounded record: `9` historical entries, `474` main characters; context: `卿何以更瘦鄧曰有愧於叔達不能不恨於破甑桓宣武既廢太宰父子仍上表曰應割近情以存逺計若除太宰父子可無後憂簡文手荅表曰所不忍言況過於言宣武又重表辭轉苦切簡文更荅曰若晉室靈長明公便宜奉行此詔如大運去矣請避賢路桓公讀詔手戰流汗於此乃止太宰父子逺徙新安桓玄敗後殷仲文還為太司馬咨議意似二三非復往日大司馬府㕔前有一老槐甚扶踈殷因月朔與衆在㕔視槐良久嘆曰槐樹婆娑無復生意殷仲文既素有名望自謂必當阿衡朝政忽作東陽太守意甚不平及之郡至富陽慨然嘆曰看此山川形勢當復出一孫伯符`
- Wikisource SBCK bounded record: `474` main characters; context: `卿何以更瘦鄧曰有愧於叔達不能不恨於破甑⟦{{SKchar|3129}}⟧宣武既廢太宰父子仍上表曰應割近情以存逺計若除太宰父子可無後憂簡文手荅表曰所不忍言況過於言宣武又重表辭轉苦切簡文更荅曰若晉室靈長明公便宜奉行此詔如大運去矣請避賢路⟦{{SKchar|3129}}⟧公讀詔手戰流汗於此乃止太宰父子逺徙新安⟦{{SKchar|3129}}⟧⟦{{SKchar|2593}}⟧敗後殷仲文還為太司馬咨議意似二三非復往日大司馬府㕔前有一老槐甚扶踈殷因月朔與衆在㕔視槐良久嘆曰槐樹婆娑無復生意殷仲文既素有名望自謂必當阿衡朝政忽作東陽太守意甚不平及之郡至富陽慨然嘆曰看此山川形勢當復出一孫伯符`
- comparison metrics: sequence ratio `0.978903`, length delta `0`, annotation delta `6`

---

### 29-jianshe — 儉嗇第二十九

#### discrepancy-234 — 29-jianshe-008

- classification: `harmless_alignment_difference`; confidence: `high`
- source discrepancy: `unmatched_entry_opening`; source record index: `234`
- review reason: The same-edition witness locates the same opening in the current boundary order; differences are glyph templates or attested witness forms.
- recommended action: No repair in this task. Preserve the current canonical boundary and all witness spellings.
- canonical boundary: `29-jianshe-008` ordinal `8`, primary status `present`, anchor `蘇峻之亂庾太尉南奔見陶公`
- canonical source position: normalized line `3019`, source line `2962`, page `<pb:KR3l0002_SBCK_002-86a>`
- Kanripo SBCK: `present`; context: `身/輕)李弘範聞之曰家舅刻薄乃復驅使草木(曰李軌/中興書)\n(劉氏之甥此應弘度非弘範也/字弘範江夏人仕至尚書郎按軌)\n王丞相儉節帳下甘果盈溢不散渉春爛敗都督白\n之公令舍去曰慎不可令太郎知(也/王恱)\n蘇峻之亂庾太尉南奔見陶公陶公雅相賞重陶性\n<!-- kanripo-page source-line=2964: <pb:KR3l0002_SBCK_002-86b> -->\n儉吝及食噉薤庾因留白陶問用此何為庾云故可\n種於是大嘆庾非唯風流兼有治實\n郗公大聚歛有錢數千萬嘉賔意甚不同常朝旦問\n訊郗家法子弟不坐因倚語移時遂及財貨事郗公\n曰汝正當欲得吾錢耳廼開庫一日令任意用郗公\n始正謂損數百萬許嘉賔遂一日乞與親友周旋略\n盡郄公聞之驚怪不能巳巳(`
- Wikisource SBCK: `located`; page `Page:Sibu Congkan0464-劉義慶-世説新語-3-3.djvu/170`; bounded reading: `蘇峻之亂⟦{{SKchar|2928}}⟧太尉南奔見陶公`
- adjacent-boundary order: `ordered`; positions `{'previous': 202, 'current': 235, 'next': 289}`

---

#### discrepancy-235 — annotation_range_difference

- classification: `annotation_boundary_only`; confidence: `medium`
- source discrepancy: `annotation_range_difference`; source record index: `235`
- review reason: Main-text length and sequence remain aligned; the discrepancy is confined to parenthetical/annotation coverage.
- recommended action: No repair in this task. Preserve current boundaries; treat the difference as annotation/layout evidence only.
- canonical chapter structure: `9` entries; gap ordinals `[]`; partial ordinals `[]`; ordinal continuity `True`
- Kanripo SBCK bounded record: `9` historical entries, `380` main characters; context: `李王武子求之與不過數十王武子因其上直率將少年能食之者持斧詣園飽共噉畢伐之送一車枝與和公問曰何如君李和既得唯笑而已王戎儉吝其從子㛰與一單衣後更責之司徒王戎既貴且富區宅僮牧膏田水碓之屬洛下無比契䟽鞅掌毎與夫人燭下散籌筭計王戎有好李賣之恐人得其種恒鑚其核王戎女適裴頠貸錢數萬女歸戎色不說女遽還錢乃釋然衞江州在尋陽有知舊人投之都不料理唯餉王不留行一斤此人得餉便命駕李弘範聞之曰家舅刻薄乃復驅使草木王丞相儉節帳下甘果盈溢不散渉春爛敗都督白之公令舍去曰慎不可令太郎知蘇峻之亂庾太尉南奔見陶公陶公雅相賞重陶性儉吝及食噉薤庾因留白陶問用此何為庾云故可種於是大嘆庾非唯風流兼有治實郗公大聚歛有錢數千萬嘉賔意甚不同常朝旦問訊郗家法子弟不坐因倚語移時遂及財貨事郗公曰汝正當欲得吾錢耳廼開庫一日令任意用郗`
- Wikisource SBCK bounded record: `380` main characters; context: `李王武子求之與不過數十王武子因其上直率將少年能食之者持斧詣園飽共噉畢伐之送一車枝與和公問曰何如君李和既得唯笑而已王戎儉吝其從子㛰與一單衣後更責之司徒王戎既貴且富區宅僮牧膏田水碓之屬洛下無比契䟽鞅掌毎與夫人燭下散籌筭計王戎有好李賣之恐人得其種𢘆鑚其核王戎女適裴頠貸錢數萬女歸戎色不說女遽還錢乃釋然衞江州在尋陽有知舊人投之都不料理唯餉王不留行一斤此人得餉便命駕李⟦{{SKchar|2592}}⟧範聞之曰家舅刻薄乃復驅使草木王丞相儉節帳下甘果盈溢不散渉春爛敗都督白之公令舍去曰慎不可令太郎知蘇峻之亂⟦{{SKchar|2928}}⟧太尉南奔見陶公陶公雅相賞重陶性儉吝及食噉薤𢈔因留白陶問用此何為𢈔云故可種於是大嘆𢈔非唯風流兼有治實郗公大聚歛有錢數千萬嘉賔意甚不同常朝旦問訊郗家法子弟不坐因倚語移時遂及財貨事郗公曰汝正當欲得吾…`
- comparison metrics: sequence ratio `0.984211`, length delta `0`, annotation delta `4`

---

### 31-fenjuan — 忿狷第三十一

#### discrepancy-238 — 31-fenjuan-004

- classification: `harmless_alignment_difference`; confidence: `high`
- source discrepancy: `unmatched_entry_opening`; source record index: `238`
- review reason: The same-edition witness locates the same opening in the current boundary order; differences are glyph templates or attested witness forms.
- recommended action: No repair in this task. Preserve the current canonical boundary and all witness spellings.
- canonical boundary: `31-fenjuan-004` ordinal `4`, primary status `present`, anchor `桓宣武與袁彦道樗蒱袁彦道`
- canonical source position: normalized line `3122`, source line `3065`, page `<pb:KR3l0002_SBCK_002-91a>`
- Kanripo SBCK: `present`; context: `o-page source-line=3063: <pb:KR3l0002_SBCK_002-91a> -->\n之持其臂曰汝詎復足與老兄計(是恬從祖兄/按王氏譜胡之)螭\n撥其手曰冷如鬼手馨彊來捉人臂\n桓宣武與袁彦道樗蒱袁彦道齒不合遂厲色擲去\n五木温太真云見袁生遷怒知顔子為貴(公問弟子/論語曰哀)\n(不遷怒不貳過不幸短命死矣/孰為好學孔子曰有顔回者好學)\n謝無奕性麤彊以事不相得自往數王藍田肆言極\n罵王正色面壁不敢動半日謝去良久轉頭問左右\n小吏曰去未荅云已去然後復坐時人嘆其性急而\n能有所容\n王令詣謝公值習鑿齒已在坐當與併榻王徙倚不\n<!-- kanripo-page source-line=3074: <pb:KR3l0002_SBCK`
- Wikisource SBCK: `located`; page `Page:Sibu Congkan0464-劉義慶-世説新語-3-3.djvu/180`; bounded reading: `⟦{{SKchar|3129}}⟧宣武與⟦{{SKchar|2783}}⟧彦道樗蒱⟦{{SKchar|2783}}⟧彦道`
- adjacent-boundary order: `ordered`; positions `{'previous': 127, 'current': 188, 'next': 224}`

---

#### discrepancy-240 — annotation_range_difference

- classification: `annotation_boundary_only`; confidence: `medium`
- source discrepancy: `annotation_range_difference`; source record index: `240`
- review reason: Main-text length and sequence remain aligned; the discrepancy is confined to parenthetical/annotation coverage.
- recommended action: No repair in this task. Preserve current boundaries; treat the difference as annotation/layout evidence only.
- canonical chapter structure: `8` entries; gap ordinals `[]`; partial ordinals `[]`; ordinal continuity `True`
- Kanripo SBCK bounded record: `8` historical entries, `510` main characters; context: `魏武有一妓聲最清髙而情性酷惡欲殺則愛才欲置則不堪於是選百人一時俱教少時果有一人聲及之便殺惡性者王藍田性急嘗食雞子以筯刺之不得便大怒舉以擲地雞子於地圓轉未止仍下地以屐齒蹍之又不得瞋甚復於地取内口中齧破即吐之王右軍聞而大笑曰使安期有此性猶當無一豪可論況藍田邪王司州甞乘雪徃王螭許司州言氣少有牾逆於螭便作色不夷司州覺惡便輿牀就之持其臂曰汝詎復足與老兄計螭撥其手曰冷如鬼手馨彊來捉人臂桓宣武與袁彦道樗蒱袁彦道齒不合遂厲色擲去五木温太真云見袁生遷怒知顔子為貴謝無奕性麤彊以事不相得自往數王藍田肆言極罵王正色面壁不敢動半日謝去良久轉頭問左右小吏曰去未荅云已去然後復坐時人嘆其性急而能有所容王令詣謝公值習鑿齒已在坐當`
- Wikisource SBCK bounded record: `510` main characters; context: `魏武有一妓聲最清髙而情性酷惡欲殺則愛才欲置則不堪於是選百人一時俱教少時果有一人聲及之便殺惡性者王藍田性急嘗食雞子以筯刺之不得便大怒舉以擲地雞子於地圓轉未止仍下地以⟦{{SKchar|2885}}⟧齒蹍之又不得瞋甚復於地取内口中齧破即吐之王右軍聞而大笑曰使安期有此性猶當無一豪可論況藍田邪王司州甞乘雪徃王螭許司州言氣少有牾逆於螭便作色不夷司州覺惡便輿牀就之持其臂曰汝詎復足與老兄計螭撥其手曰冷如⟦{{SKchar|3932}}⟧手馨彊來捉人臂⟦{{SKchar|3129}}⟧宣武與⟦{{SKchar|2783}}⟧彦道樗蒱⟦{{SKchar|2783}}⟧彦道齒不合遂厲色擲去五木温太真云見⟦{{SKchar|2783}}⟧生遷怒知顔子為貴謝無奕性麤彊以事不相得自往數王藍田肆言極罵王正色面壁不敢動半日謝去良久轉頭問左右…`
- comparison metrics: sequence ratio `0.986275`, length delta `0`, annotation delta `9`

---

### 34-pilou — 紕漏第三十四

#### discrepancy-246 — annotation_range_difference

- classification: `annotation_boundary_only`; confidence: `medium`
- source discrepancy: `annotation_range_difference`; source record index: `246`
- review reason: Main-text length and sequence remain aligned; the discrepancy is confined to parenthetical/annotation coverage.
- recommended action: No repair in this task. Preserve current boundaries; treat the difference as annotation/layout evidence only.
- canonical chapter structure: `8` entries; gap ordinals `[]`; partial ordinals `[]`; ordinal continuity `True`
- Kanripo SBCK bounded record: `8` historical entries, `606` main characters; context: `有令名武帝崩選百二十挽郎一時之秀彦育長亦在其中王安豐選女壻從挽郎&KR0679;其勝者且擇取四人任猶在其中童少時神明可愛時人謂育長影亦好自過江便失志王丞相請先度時賢共至石頭迎之猶作疇日相待一見便覺有異坐席竟下飲便問人云此為茶為茗覺有異色乃自申明云向問飲為熱為冷耳甞行從棺邸下度流涕悲哀王丞相聞之曰此是有情癡謝虎子甞上屋熏鼠胡兒既無由知父為此事聞人道癡人有作此者戲笑之時道此非復一過太傅既了已之不知因其言次語胡兒曰世人以此謗中郎亦言我共作此胡兒懊熱一月日閉齋不出太傅虚託引已之過以相開悟可謂德敎殷仲堪父病虚悸聞牀下蟻動謂是牛鬬孝武不知是殷公問仲堪有一殷病如此不仲堪流涕而起曰臣進退唯谷虞嘯父為孝武侍中帝從容問曰卿在門下初不聞有所獻替虞家富春近海謂帝望其意氣對曰天時尚煗䱥魚蝦未可致尋當有所上獻帝撫`
- Wikisource SBCK bounded record: `607` main characters; context: `有令名武帝崩選百二十挽郎一時之秀彦育長亦在其中王安豐選女壻從挽郎⟦{{SKchar|302}}⟧其勝者且擇取四人任猶在其中童少時神明可愛時人謂育長影亦好自過江便失志王丞相請先度時賢共至石頭迎之猶作疇日相待一見便覺有異坐席竟下飲便問人云此為茶為茗覺有異色乃自申明云向問飲為⟦{{SKchar|3289}}⟧為冷耳甞行從棺邸下度流涕悲哀王丞相聞之曰此是有情癡謝虎子甞上屋熏鼠胡兒既無由知父為此事聞人道癡人有作此者戲笑之時道此非復一過太傅既了已之不知因其言次語胡兒曰世人以此謗中郎亦言我共作此胡兒懊熱一月日閉齋不出太傅虚託引已之過以相開悟可謂德敎殷仲堪父病虚悸聞牀下蟻動謂是牛鬬孝武不知是殷公問仲堪有一殷病如此不仲堪流涕而起曰臣進𨓆唯谷虞嘯父為孝武侍中帝從容問曰卿在門下初不聞有所獻替虞家富春近海謂帝望其意氣對曰天時尚煗䱥魚蝦…`
- comparison metrics: sequence ratio `0.995878`, length delta `1`, annotation delta `4`

---

### 36-chouxi — 仇隟第三十六

#### discrepancy-248 — 36-chouxi-008

- classification: `harmless_alignment_difference`; confidence: `high`
- source discrepancy: `unmatched_entry_opening`; source record index: `248`
- review reason: The same-edition witness locates the same opening in the current boundary order; differences are glyph templates or attested witness forms.
- recommended action: No repair in this task. Preserve the current canonical boundary and all witness spellings.
- canonical boundary: `36-chouxi-008` ordinal `8`, primary status `present`, anchor `桓玄將篡桓脩欲因玄在脩母`
- canonical source position: normalized line `3455`, source line `3398`, page `<pb:KR3l0002_SBCK_002-106a>`
- Kanripo SBCK: `present`; context: `傅命駕出至標所\n孰視首曰卿何故趣欲殺我邪(懼禍難抗表起兵於/續晉陽秋曰王恭深)\n(初道子與恭善欲載出都靣相折數聞西軍之逼乃/是遣左將軍謝琰討恭恭敗走曲阿為湖浦尉所擒)\n(梟首於東桁也/令於兒塘斬之)\n桓玄將篡桓脩欲因玄在脩母許襲之庾夫人云汝\n等近過我餘年我養之不忍見行此事(沖後娶潁川/桓氏譜曰恒)\n(之脩深憾焉宻有圖玄之意脩母曰靈寳視我如母/庾蔑女字姚晉安帝紀曰脩少為玄所侮言論常鄙)\n(相圖脩乃止/汝等何忍骨肉)\n<!-- kanripo-page source-line=3403: <pb:KR3l0002_SBCK_002-106b> -->\n\n世說新語下卷下(終)\n`
- Wikisource SBCK: `located`; page `Page:Sibu Congkan0464-劉義慶-世説新語-3-3.djvu/210`; bounded reading: `桓玄將篡⟦{{SKchar|3129}}⟧脩欲因⟦{{SKchar|2593}}⟧在脩母`
- adjacent-boundary order: `partially_ordered`; positions `{'previous': 592, 'current': 624, 'next': None}`

---

#### discrepancy-249 — missing_kanripo_passage

- classification: `harmless_alignment_difference`; confidence: `high`
- source discrepancy: `missing_kanripo_passage`; source record index: `249`
- review reason: The apparent missing passage is a chapter/edition-layout tail or witness markup difference; current entry order and count remain intact.
- recommended action: No repair in this task. Preserve current boundaries; treat the difference as annotation/layout evidence only.
- canonical chapter structure: `8` entries; gap ordinals `[]`; partial ordinals `[]`; ordinal continuity `True`
- Kanripo SBCK bounded record: `8` historical entries, `659` main characters; context: `其宜右軍遂稱疾去郡以憤慨致終王東亭與孝伯語後漸異孝伯謂東亭曰卿便不可復測荅曰王陵廷争陳平從黙但問克終云何耳王孝伯死縣其首於大桁司馬太傅命駕出至標所孰視首曰卿何故趣欲殺我邪桓玄將篡桓脩欲因玄在脩母許襲之庾夫人云汝等近過我餘年我養之不忍見行此事`
- Wikisource SBCK bounded record: `6978` main characters; context: `其宜右軍遂稱疾去郡以憤慨致終王東亭與孝伯語後漸異孝伯謂東亭曰卿便不可復測荅曰王陵廷争陳平從黙但問克終云何耳王孝伯死縣其首於大桁司馬太傅命駕出至標所孰視首曰卿何故趣欲殺我邪桓玄將篡⟦{{SKchar|3129}}⟧脩欲因⟦{{SKchar|2593}}⟧在脩母許襲之⟦{{SKchar|2928}}⟧夫人云汝等近過我餘年我養之不忍見行此事世說新語下卷下刻世說新語序吳郡袁褧撰嘗攷載記所述晉人話言簡約玄澹爾雅有韻世言江左善淸談今閱新語信乎其言之也臨川撰爲此書採掇綜叙明畼不繁孝標所注能收錄諸家小史分釋其義詁訓之賞見於高似孫緯略余家藏宋本是放翁校刋本謝湖躬耕之暇毛披心寄自謂可觀爰付梓人傳之同好因嘆昔人論司馬氏之祚亡於淸談斯言也無乃過甚矣乎竹林之儔希慕沂樂䔵亭之集咏歌堯風陶荆州之勤敏謝東山之恬鎭解莊易則輔嗣平叔擅其宗析⟦{{…`
- comparison metrics: sequence ratio `0.17101`, length delta `6319`, annotation delta `969`

---

## Interpretation limits

A same-edition machine witness can confirm that an opening and its adjacent text occur in the expected order. It does not by itself create a new canonical entry segmentation. The absence of `true_boundary_error` or `extra_boundary` findings therefore means that this targeted evidence found no supported repair request, not that semantic boundary correctness has been proven for every entry.

The overlapping records for the 08 賞譽 gap are retained separately because the source triage contains both an unmatched opening record and a chapter-level missing-passage record. They refer to the same existing primary-witness gap and do not imply two additional canonical entries.
