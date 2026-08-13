# SC0 Story Chain Gold Set Review

本文件由 `scripts/build_story_chain_gold.py` 确定性生成。SC0 只选择已有 PersonStoryLink 支持的故事，并准备句读人工审核包；它不新增人物、关系、参与者判断或历史解释。

- selected Stories: 16
- candidate Stories examined: 78
- Story↔Person links in Gold Set: 22
- multi-Person Stories: 4
- bipartite connected components: 1
- covered reviewed direct Relations: 6 (relation-gold-001, relation-gold-002, relation-gold-003, relation-gold-004, relation-gold-005, relation-gold-006)
- covered reviewed derived Relations (display/audit only): 1 (relation-001)
- existing reviewed anchor: `06-yaliang-019`
- newly proposed records remain `candidate_for_review`; this build does not self-certify human review.

## 02-yanyu-069 · 言語第二

- selection_status: `candidate_for_review`
- linked Persons: 王羲之
- main-text Persons: 王羲之
- Liu-annotation-only Persons: （无）
- selection reasons: main_text_person_presence, crl1_exact_transfer, existing_p1a_candidate
- punctuation: `candidate` / `reference_candidate`
- exact_transfer: `True`
- alignment: `exact-agreement` / `exact_reference_agreement, single_reference_only`
- round-trip: `pass`
- canonical: 劉真長為丹陽尹許玄度出都就劉宿
牀帷新麗
飲食豐甘許曰若保全此處殊勝東山劉曰卿若知
吉凶由人吾安得不保此王逸少在
坐曰令巢許遇稷契當無此言二人並有愧色
- proposed punctuated reading: 劉真長為丹陽尹，許玄度出都，就劉宿牀帷新麗，飲食豐甘。許曰：“若保全此處，殊勝東山。”劉曰：“卿若知吉凶由人，吾安得不保此！”王逸少在坐，曰：“令巢、許遇稷、契，當無此言。”二人並有愧色。
- reference A: `sources/local/shishuo/reference-txt/shishuo.txt` (punctuation guidance; SHA-256 `843c8c55956454b623a4d6f28e3e5b6ce5e7c8722aecf24822eb605914b1a205`)
- reference B: `content/processed/shishuo/collation/wikisource-sbck/yanyu.md` (character/structure comparison; SHA-256 `58a99b27c5bdbbfc97f89b29f06fada2539bdcb500cf8d3855574983428a1774`; no sentence punctuation)
- ambiguity notes: machine candidate only; human approval is required before `reviewed` or `reader_ready` promotion.

## 02-yanyu-071 · 言語第二

- selection_status: `candidate_for_review`
- linked Persons: 王凝之
- main-text Persons: 王凝之
- Liu-annotation-only Persons: （无）
- selection reasons: main_text_person_presence, existing_p1a_candidate
- punctuation: `candidate` / `reference_candidate`
- exact_transfer: `False`
- alignment: `character-disagreement` / `reference_character_variant, single_reference_only`
- round-trip: `pass`
- canonical: 謝太傅寒雪日内集與兒女講論文義俄而雪驟
公欣然曰白雪紛紛何所似兄子胡兒曰
撒鹽空
中差可擬兄女曰未若栁絮因風起公大笑樂即公

大兄無奕女左將軍王凝之妻也
- proposed punctuated reading: 謝太傅寒雪日内集，與兒女講論文義。俄而雪驟，公欣然曰：“白雪紛紛何所似？”兄子胡兒曰：“撒鹽空中差可擬。”兄女曰：“未若栁絮因風起。”公大笑樂。即公大兄無奕女，左將軍王凝之妻也。
- reference A: `sources/local/shishuo/reference-txt/shishuo.txt` (punctuation guidance; SHA-256 `843c8c55956454b623a4d6f28e3e5b6ce5e7c8722aecf24822eb605914b1a205`)
- reference B: `content/processed/shishuo/collation/wikisource-sbck/yanyu.md` (character/structure comparison; SHA-256 `58a99b27c5bdbbfc97f89b29f06fada2539bdcb500cf8d3855574983428a1774`; no sentence punctuation)
- ambiguity notes: machine candidate only; human approval is required before `reviewed` or `reader_ready` promotion.

## 02-yanyu-083 · 言語第二

- selection_status: `candidate_for_review`
- linked Persons: 謝安
- main-text Persons: 謝安
- Liu-annotation-only Persons: （无）
- selection reasons: main_text_person_presence, crl1_exact_transfer, existing_p1a_candidate
- punctuation: `candidate` / `reference_candidate`
- exact_transfer: `True`
- alignment: `exact-agreement` / `exact_reference_agreement, single_reference_only`
- round-trip: `pass`
- canonical: 袁彦伯為謝安南司馬都下諸人送至瀨鄉
將别既自悽惘歎曰江山遼落居然有萬里之勢
- proposed punctuated reading: 袁彦伯為謝安南司馬，都下諸人送至瀨鄉。將别，既自悽惘，歎曰：“江山遼落，居然有萬里之勢。”
- reference A: `sources/local/shishuo/reference-txt/shishuo.txt` (punctuation guidance; SHA-256 `843c8c55956454b623a4d6f28e3e5b6ce5e7c8722aecf24822eb605914b1a205`)
- reference B: `content/processed/shishuo/collation/wikisource-sbck/yanyu.md` (character/structure comparison; SHA-256 `58a99b27c5bdbbfc97f89b29f06fada2539bdcb500cf8d3855574983428a1774`; no sentence punctuation)
- ambiguity notes: machine candidate only; human approval is required before `reviewed` or `reader_ready` promotion.

## 04-wenxue-024 · 文學第四

- selection_status: `candidate_for_review`
- linked Persons: 謝安
- main-text Persons: 謝安
- Liu-annotation-only Persons: （无）
- selection reasons: main_text_person_presence, crl1_exact_transfer, existing_p1a_candidate
- punctuation: `candidate` / `reference_candidate`
- exact_transfer: `True`
- alignment: `exact-agreement` / `exact_reference_agreement, single_reference_only`
- round-trip: `pass`
- canonical: 謝安年少時請阮光禄道白馬論
為論以示謝于時
謝不即解阮語重相咨盡阮乃歎曰非但能言人不

可得正索解人亦不可得
- proposed punctuated reading: 謝安年少時，請阮光禄道《白馬論》，為論以示謝，于時謝不即解阮語，重相咨盡。阮乃歎曰：“非但能言人不可得，正索解人亦不可得！”
- reference A: `sources/local/shishuo/reference-txt/shishuo.txt` (punctuation guidance; SHA-256 `843c8c55956454b623a4d6f28e3e5b6ce5e7c8722aecf24822eb605914b1a205`)
- reference B: `content/processed/shishuo/collation/wikisource-sbck/wenxue.md` (character/structure comparison; SHA-256 `33a069841f81f30dde8f3a9a02641b29a1a0dfade6180ae8290cb8cc39f46686`; no sentence punctuation)
- ambiguity notes: machine candidate only; human approval is required before `reviewed` or `reader_ready` promotion.

## 04-wenxue-036 · 文學第四

- selection_status: `candidate_for_review`
- linked Persons: 王羲之
- main-text Persons: 王羲之
- Liu-annotation-only Persons: （无）
- selection reasons: main_text_person_presence, existing_p1a_candidate
- punctuation: `candidate` / `reference_candidate`
- exact_transfer: `False`
- alignment: `character-disagreement` / `reference_character_variant, single_reference_only`
- round-trip: `pass`
- canonical: 王逸少作㑹稽初至支道林在焉孫興公謂王曰支
道林㧞新領異胷懷所及乃自佳卿欲見不王本自
有一徃雋氣殊自輕之後孫與支共載徃王許王都
領域不與交言須臾支退後正值王當行車已在門
支語王曰君未可去貧道與君小語因論莊子逍遥
逰支作數千言才藻新竒花爛映發王遂披襟解帶
留連不能已
- proposed punctuated reading: 王逸少作㑹稽，初至，支道林在焉。孫興公謂王曰：“支道林㧞新領異，胷懷所及乃自佳，卿欲見不？”王本自有一徃雋氣，殊自輕之。後孫與支共載徃王許，王都領域，不與交言。須臾支退。後正值王當行，車已在門。支語王曰：“君未可去，貧道與君小語。”因論《莊子·逍遥逰》。支作數千言，才藻新竒，花爛映發。王遂披襟解帶，留連不能已。
- reference A: `sources/local/shishuo/reference-txt/shishuo.txt` (punctuation guidance; SHA-256 `843c8c55956454b623a4d6f28e3e5b6ce5e7c8722aecf24822eb605914b1a205`)
- reference B: `content/processed/shishuo/collation/wikisource-sbck/wenxue.md` (character/structure comparison; SHA-256 `33a069841f81f30dde8f3a9a02641b29a1a0dfade6180ae8290cb8cc39f46686`; no sentence punctuation)
- ambiguity notes: machine candidate only; human approval is required before `reviewed` or `reader_ready` promotion.

## 04-wenxue-087 · 文學第四

- selection_status: `candidate_for_review`
- linked Persons: 謝安
- main-text Persons: 謝安
- Liu-annotation-only Persons: （无）
- selection reasons: main_text_person_presence, existing_p1a_candidate
- punctuation: `candidate` / `reference_candidate`
- exact_transfer: `False`
- alignment: `character-disagreement` / `reference_character_variant, single_reference_only`
- round-trip: `pass`
- canonical: 桓公見謝安石作簡文諡議㸔竟擲於坐上諸客曰
此是安石碎金
- proposed punctuated reading: 桓公見謝安石作簡文諡議，㸔竟，擲於坐上諸客曰：“此是安石碎金。”
- reference A: `sources/local/shishuo/reference-txt/shishuo.txt` (punctuation guidance; SHA-256 `843c8c55956454b623a4d6f28e3e5b6ce5e7c8722aecf24822eb605914b1a205`)
- reference B: `content/processed/shishuo/collation/wikisource-sbck/wenxue.md` (character/structure comparison; SHA-256 `33a069841f81f30dde8f3a9a02641b29a1a0dfade6180ae8290cb8cc39f46686`; no sentence punctuation)
- ambiguity notes: machine candidate only; human approval is required before `reviewed` or `reader_ready` promotion.

## 05-fangzheng-023 · 方正第五

- selection_status: `candidate_for_review`
- linked Persons: 王導
- main-text Persons: 王導
- Liu-annotation-only Persons: （无）
- selection reasons: main_text_person_presence, existing_p1a_candidate
- punctuation: `candidate` / `reference_candidate`
- exact_transfer: `False`
- alignment: `character-disagreement` / `reference_character_variant, single_reference_only`
- round-trip: `pass`
- canonical: 元皇帝既登阼以鄭后之寵欲舍明帝而立簡文時
議者咸謂舍長立少既於理非倫且明帝以聦亮英
斷益宜爲儲副周王諸公並苦爭懇切

唯刁玄亮獨欲奉少主
以阿帝旨元帝便欲施行慮諸公不奉詔於是先喚
周侯丞相入然後欲出詔付刁周王既入始至階
頭帝逆遣傳詔遏使就東廂周侯未悟即卻略下階
丞相披撥傳詔徑至御牀前曰不審陛下何以見臣

帝黙然無言乃探懐中黄𥿄詔裂擲之由此皇儲始
定周侯方慨然愧歎曰我常自言勝茂弘今始知不
如也
- proposed punctuated reading: 元皇帝既登阼，以鄭后之寵，欲舍明帝而立簡文。時議者咸謂：舍長立少，既於理非倫，且明帝以聦亮英斷，益宜爲儲副。周、王諸公並苦爭懇切。唯刁玄亮獨欲奉少主以阿帝旨，元帝便欲施行，慮諸公不奉詔。於是先喚周侯、丞相入，然後欲出詔付刁。周、王既入，始至階頭，帝逆遣傳詔遏使就東廂。周侯未悟，即卻略下階。丞相披撥傳詔，徑至御牀前，曰：“不審陛下何以見臣？”帝黙然無言，乃探懐中黄𥿄詔裂擲之。由此皇儲始定。周侯方慨然愧歎曰：“我常自言勝茂弘，今始知不如也！”
- reference A: `sources/local/shishuo/reference-txt/shishuo.txt` (punctuation guidance; SHA-256 `843c8c55956454b623a4d6f28e3e5b6ce5e7c8722aecf24822eb605914b1a205`)
- reference B: `content/processed/shishuo/collation/wikisource-sbck/fangzheng.md` (character/structure comparison; SHA-256 `c33d1bdebff2783b8c9956cfc1faf12d5de737dcad502019589b18ad51c2b1f9`; no sentence punctuation)
- ambiguity notes: machine candidate only; human approval is required before `reviewed` or `reader_ready` promotion.

## 05-fangzheng-053 · 方正第五

- selection_status: `candidate_for_review`
- linked Persons: 謝安
- main-text Persons: 謝安
- Liu-annotation-only Persons: （无）
- selection reasons: main_text_person_presence, existing_p1a_candidate
- punctuation: `candidate` / `reference_candidate`
- exact_transfer: `False`
- alignment: `character-disagreement` / `reference_character_variant, single_reference_only`
- round-trip: `pass`
- canonical: 阮光禄赴山陵至都不往殷劉許過事便還諸
人相與追之既亦知時流必當逐巳乃遄疾而去至

方山不相及劉尹時爲㑹稽
乃嘆曰我入當泊安石渚下耳不敢復近思曠傍伊
便能捉杖打人不易
- proposed punctuated reading: 阮光禄赴山陵，至都，不往殷、劉許，過事便還。諸人相與追之，既亦知時流必當逐巳，乃遄疾而去，至方山不相及。劉尹時爲㑹稽，乃嘆曰：“我入，當泊安石渚下耳，不敢復近思曠傍，伊便能捉杖打人，不易。”
- reference A: `sources/local/shishuo/reference-txt/shishuo.txt` (punctuation guidance; SHA-256 `843c8c55956454b623a4d6f28e3e5b6ce5e7c8722aecf24822eb605914b1a205`)
- reference B: `content/processed/shishuo/collation/wikisource-sbck/fangzheng.md` (character/structure comparison; SHA-256 `c33d1bdebff2783b8c9956cfc1faf12d5de737dcad502019589b18ad51c2b1f9`; no sentence punctuation)
- ambiguity notes: machine candidate only; human approval is required before `reviewed` or `reader_ready` promotion.

## 05-fangzheng-055 · 方正第五

- selection_status: `candidate_for_review`
- linked Persons: 謝安
- main-text Persons: 謝安
- Liu-annotation-only Persons: （无）
- selection reasons: main_text_person_presence, existing_p1a_candidate
- punctuation: `candidate` / `reference_candidate`
- exact_transfer: `False`
- alignment: `character-disagreement` / `reference_character_variant, single_reference_only`
- round-trip: `pass`
- canonical: 桓公問桓子野謝安石料萬石必敗何以不諫

子野荅曰故當出於難犯耳桓作
色曰萬石撓弱凡才有何嚴顔難犯
- proposed punctuated reading: 桓公問桓子野：“謝安石料萬石必敗，何以不諫？”子野荅曰：“故當出於難犯耳！”桓作色曰：“萬石撓弱凡才，有何嚴顔難犯？”
- reference A: `sources/local/shishuo/reference-txt/shishuo.txt` (punctuation guidance; SHA-256 `843c8c55956454b623a4d6f28e3e5b6ce5e7c8722aecf24822eb605914b1a205`)
- reference B: `content/processed/shishuo/collation/wikisource-sbck/fangzheng.md` (character/structure comparison; SHA-256 `c33d1bdebff2783b8c9956cfc1faf12d5de737dcad502019589b18ad51c2b1f9`; no sentence punctuation)
- ambiguity notes: machine candidate only; human approval is required before `reviewed` or `reader_ready` promotion.

## 06-yaliang-019 · 雅量第六

- selection_status: `gold_anchor`
- linked Persons: 郗璿、王羲之、郗鑒
- main-text Persons: 王羲之
- Liu-annotation-only Persons: 郗璿、郗鑒
- selection reasons: existing_reviewed_anchor, main_text_person_presence, multiple_resolved_network_persons, existing_p1a_candidate
- punctuation: `reviewed` / `human_reviewed`
- exact_transfer: `False`
- alignment: `None` / ``
- round-trip: `pass`
- canonical: 郗太傅在京口遣門生與王丞相書求女壻丞相語
郗信君往東廂任意選之門生歸白郗曰王家諸郎
亦皆可嘉聞來覓壻咸自矜持唯有一郎在東牀上
坦腹卧如不聞郗公云正此好訪之乃是逸少因嫁
女與焉
- proposed punctuated reading: 郗太傅在京口，遣門生與王丞相書，求女壻。丞相語郗信：「君往東廂，任意選之。」門生歸，白郗曰：「王家諸郎亦皆可嘉，聞來覓壻，咸自矜持。唯有一郎在東牀上坦腹卧，如不聞。」郗公云：「正此好！」訪之，乃是逸少，因嫁女與焉。
- reference A: `sources/local/shishuo/reference-txt/shishuo.txt` (punctuation guidance; SHA-256 `843c8c55956454b623a4d6f28e3e5b6ce5e7c8722aecf24822eb605914b1a205`)
- reference B: `content/processed/shishuo/collation/wikisource-sbck/yaliang.md` (character/structure comparison; SHA-256 `9ec7c49ce105bb949f27b3652aa2cc5280cf558d46582af43851fa9d5551ad74`; no sentence punctuation)
- ambiguity notes: machine candidate only; human approval is required before `reviewed` or `reader_ready` promotion.

## 06-yaliang-027 · 雅量第六

- selection_status: `candidate_for_review`
- linked Persons: 謝安
- main-text Persons: 謝安
- Liu-annotation-only Persons: （无）
- selection reasons: main_text_person_presence, existing_p1a_candidate
- punctuation: `candidate` / `reference_candidate`
- exact_transfer: `False`
- alignment: `character-disagreement` / `reference_character_variant, single_reference_only`
- round-trip: `pass`
- canonical: 桓宣武與郗超議芟夷朝臣條牒既定其夜同宿
明晨起
呼謝安王坦之入擲䟽示之郗猶在帳内謝都無言
王直擲還云多宣武取筆欲除郗不覺竊從帳中與
宣武言謝含笑曰郗生可謂入幕賔也
- proposed punctuated reading: 桓宣武與郗超議芟夷朝臣，條牒既定，其夜同宿。明晨起，呼謝安、王坦之入，擲䟽示之，郗猶在帳内，謝都無言，王直擲還，云：“多！”宣武取筆欲除，郗不覺，竊從帳中與宣武言。謝含笑曰：“郗生可謂入幕賔也。”
- reference A: `sources/local/shishuo/reference-txt/shishuo.txt` (punctuation guidance; SHA-256 `843c8c55956454b623a4d6f28e3e5b6ce5e7c8722aecf24822eb605914b1a205`)
- reference B: `content/processed/shishuo/collation/wikisource-sbck/yaliang.md` (character/structure comparison; SHA-256 `d9a15ea9b4627aa4223a2592adb64380d403a324551d475e90c6a8607f03403b`; no sentence punctuation)
- ambiguity notes: machine candidate only; human approval is required before `reviewed` or `reader_ready` promotion.

## 06-yaliang-029 · 雅量第六

- selection_status: `candidate_for_review`
- linked Persons: 王導、謝安
- main-text Persons: 謝安
- Liu-annotation-only Persons: 王導
- selection reasons: main_text_person_presence, multiple_resolved_network_persons, existing_p1a_candidate
- punctuation: `candidate` / `reference_candidate`
- exact_transfer: `False`
- alignment: `character-disagreement` / `reference_character_variant, single_reference_only`
- round-trip: `pass`
- canonical: 桓公伏甲設饌廣延朝士因此欲誅謝安王坦之

王甚遽問謝曰當作何
計謝神意不變謂文度曰晉阼存亡在此一行相與
俱前王之恐狀轉見於色謝之寛容愈表於貌望階
趨席方作洛生詠諷浩浩洪流桓憚其曠逺乃趣解
兵



王謝舊齊名於此始
判優劣
- proposed punctuated reading: 桓公伏甲設饌，廣延朝士，因此欲誅謝安、王坦之。王甚遽，問謝曰：“當作何計？”謝神意不變，謂文度曰：“晉阼存亡，在此一行。”相與俱前。王之恐狀，轉見於色。謝之寛容，愈表於貌，望階趨席，方作洛生詠，諷“浩浩洪流”。桓憚其曠逺，乃趣解兵。王、謝舊齊名，於此始判優劣。
- reference A: `sources/local/shishuo/reference-txt/shishuo.txt` (punctuation guidance; SHA-256 `843c8c55956454b623a4d6f28e3e5b6ce5e7c8722aecf24822eb605914b1a205`)
- reference B: `content/processed/shishuo/collation/wikisource-sbck/yaliang.md` (character/structure comparison; SHA-256 `d9a15ea9b4627aa4223a2592adb64380d403a324551d475e90c6a8607f03403b`; no sentence punctuation)
- ambiguity notes: machine candidate only; human approval is required before `reviewed` or `reader_ready` promotion.

## 07-shijian-021 · 識鑒第七

- selection_status: `candidate_for_review`
- linked Persons: 謝安
- main-text Persons: 謝安
- Liu-annotation-only Persons: （无）
- selection reasons: main_text_person_presence, crl1_exact_transfer
- punctuation: `candidate` / `reference_candidate`
- exact_transfer: `True`
- alignment: `exact-agreement` / `exact_reference_agreement, single_reference_only`
- round-trip: `pass`
- canonical: 謝公在東山畜妓簡文曰安石必出既與人同樂亦
不得不與人同憂
- proposed punctuated reading: 謝公在東山畜妓，簡文曰：“安石必出。既與人同樂，亦不得不與人同憂。”
- reference A: `sources/local/shishuo/reference-txt/shishuo.txt` (punctuation guidance; SHA-256 `843c8c55956454b623a4d6f28e3e5b6ce5e7c8722aecf24822eb605914b1a205`)
- reference B: `content/processed/shishuo/collation/wikisource-sbck/shijian.md` (character/structure comparison; SHA-256 `a05e86903f8b78e60a1dc38ebe3b79f98790e8e9d1cf1de0eac19fc2256667bd`; no sentence punctuation)
- ambiguity notes: machine candidate only; human approval is required before `reviewed` or `reader_ready` promotion.

## 08-shangyu-077 · 賞譽第八

- selection_status: `candidate_for_review`
- linked Persons: 謝安
- main-text Persons: 謝安
- Liu-annotation-only Persons: （无）
- selection reasons: main_text_person_presence, crl1_exact_transfer
- punctuation: `candidate` / `reference_candidate`
- exact_transfer: `True`
- alignment: `exact-agreement` / `exact_reference_agreement, single_reference_only`
- round-trip: `pass`
- canonical: 王右軍語劉尹故當共推安石劉尹曰若安石東山
志立當與天下共推之
- proposed punctuated reading: 王右軍語劉尹：“故當共推安石。”劉尹曰：“若安石東山志立，當與天下共推之。”
- reference A: `sources/local/shishuo/reference-txt/shishuo.txt` (punctuation guidance; SHA-256 `843c8c55956454b623a4d6f28e3e5b6ce5e7c8722aecf24822eb605914b1a205`)
- reference B: `content/processed/shishuo/collation/wikisource-sbck/shangyu.md` (character/structure comparison; SHA-256 `5d23dd7488f394be82938c662755c24216b55966963ea28d5e15db9a68027645`; no sentence punctuation)
- ambiguity notes: machine candidate only; human approval is required before `reviewed` or `reader_ready` promotion.

## 19-xianyuan-026 · 賢媛第十九

- selection_status: `candidate_for_review`
- linked Persons: 王凝之、王羲之
- main-text Persons: 王凝之、王羲之
- Liu-annotation-only Persons: （无）
- selection reasons: multi_person_main_text_bridge, main_text_person_presence, multiple_resolved_network_persons, existing_p1a_candidate
- punctuation: `candidate` / `reference_candidate`
- exact_transfer: `False`
- alignment: `character-disagreement` / `reference_character_variant, single_reference_only`
- round-trip: `pass`
- canonical: 王凝之謝夫人既徃王氏太薄凝之既還謝家意大
不說太傅慰釋之曰王郎逸少之子人身亦不惡汝
何以恨廼爾荅曰一門叔父則有阿大中郞羣從兄
弟則有封胡遏末

不意天壤之中乃有王郎
- proposed punctuated reading: 王凝之謝夫人既徃王氏，太薄凝之。既還謝家，意大不說。太傅慰釋之曰：“王郎，逸少之子，人身亦不惡，汝何以恨廼爾？”荅曰：“一門叔父，則有阿大、中郞。羣從兄弟，則有封、胡、遏、末。不意天壤之中，乃有王郎！”
- reference A: `sources/local/shishuo/reference-txt/shishuo.txt` (punctuation guidance; SHA-256 `843c8c55956454b623a4d6f28e3e5b6ce5e7c8722aecf24822eb605914b1a205`)
- reference B: `content/processed/shishuo/collation/wikisource-sbck/xianyuan.md` (character/structure comparison; SHA-256 `73883b6fe55e37d48a7516e1b45a2bf42bc4eb1caf7a4e357849ecffa496456b`; no sentence punctuation)
- ambiguity notes: machine candidate only; human approval is required before `reviewed` or `reader_ready` promotion.

## 25-paidiao-026 · 排調第二十五

- selection_status: `candidate_for_review`
- linked Persons: 王凝之、謝安、謝道韞
- main-text Persons: 謝安
- Liu-annotation-only Persons: 王凝之、謝道韞
- selection reasons: main_text_person_presence, multiple_resolved_network_persons, existing_p1a_candidate
- punctuation: `candidate` / `reference_candidate`
- exact_transfer: `False`
- alignment: `character-disagreement` / `reference_character_variant, single_reference_only`
- round-trip: `pass`
- canonical: 謝公在東山朝命屢降而不動後出為桓宣武司馬
將發新亭朝士咸出瞻送髙靈時為中丞亦徃相祖
先時多少飲酒因倚如醉戲曰卿屢違朝㫖髙卧東
山諸人毎相與言安石不肻出將如蒼生何今亦蒼
生將如卿何謝笑而不荅
- proposed punctuated reading: 謝公在東山，朝命屢降而不動。後出為桓宣武司馬，將發新亭，朝士咸出瞻送。髙靈時為中丞，亦徃相祖。先時，多少飲酒，因倚如醉，戲曰：“卿屢違朝㫖，髙卧東山，諸人毎相與言：‘安石不肻出，將如蒼生何？’今亦蒼生將如卿何？”謝笑而不荅。
- reference A: `sources/local/shishuo/reference-txt/shishuo.txt` (punctuation guidance; SHA-256 `843c8c55956454b623a4d6f28e3e5b6ce5e7c8722aecf24822eb605914b1a205`)
- reference B: `content/processed/shishuo/collation/wikisource-sbck/paidiao.md` (character/structure comparison; SHA-256 `739e96ca97dce337eddd4a9a5a546491a1e4a6dd4eaca8e10e8a0f00af50e7a0`; no sentence punctuation)
- ambiguity notes: machine candidate only; human approval is required before `reviewed` or `reader_ready` promotion.
