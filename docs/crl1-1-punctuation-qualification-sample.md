# CRL1.1 句读来源资格抽样包

本文件由 `scripts/build_shishuo_reading_layer.py` 确定性生成，供人工检查本地 structural-reference TXT 是否足以承担全书句读参考作用。它不把任何机器候选标记为人工 reviewed。

- 抽样条目：77
- 覆盖章节：36
- 选择方式：每章优先选择最短条目与句读复杂度最高的条目；另列已知结构异常条目。
- 资格结论：本地 TXT 当前仅为 `provisionally_qualified`，抽样不改变该结论。

## 判定说明

`exact_transfer` 只表示去除句读后本地参考字符与 canonical 字符序列完全相等；它不表示来源已经取得 editorial trust。Wikisource comparison view 用于字符/结构核对，当前不提供第二套句读。

### 01-dexing-016 ·  · short_entry

- 自动分类：exact-agreement / exact_reference_agreement, single_reference_only
- transfer_class：`exact_character_transfer`；reference_case：`single_reference_but_exact`
- exact_transfer：`True`
- round-trip：`pass`
- canonical：王戎云與嵇康居二十年未嘗見其喜愠之色
- 转移句读：王戎云：“與嵇康居二十年，未嘗見其喜愠之色。”
- local TXT reference：王戎云：“与嵇康居二十年，未尝见其喜愠之色。”
- Wikisource comparison：`content/processed/shishuo/collation/wikisource-sbck/dexing.md`（字符/结构参考；当前无句读）

### 01-dexing-017 ·  · punctuation_complexity

- 自动分类：exact-agreement / exact_reference_agreement, single_reference_only
- transfer_class：`exact_character_transfer`；reference_case：`single_reference_but_exact`
- exact_transfer：`True`
- round-trip：`pass`
- canonical：王戎和嶠同時遭大喪俱以孝稱王雞骨支牀和哭
泣備禮


武帝謂劉仲雄曰


卿數省王和
不聞和哀苦過禮使人憂之仲雄曰和嶠雖備禮神
氣不損王戎雖不備禮而哀毁骨立臣以和嶠生孝
王戎死孝陛下不應憂嶠而應憂戎
- 转移句读：王戎、和嶠同時遭大喪，俱以孝稱。王雞骨支牀，和哭泣備禮。武帝謂劉仲雄曰：“卿數省王、和不？聞和哀苦過禮，使人憂之。”仲雄曰：“和嶠雖備禮，神氣不損；王戎雖不備禮，而哀毁骨立。臣以和嶠生孝，王戎死孝。陛下不應憂嶠，而應憂戎。”
- local TXT reference：王戎、和峤同时遭大丧，俱以孝称。王鸡骨支床，和哭泣备礼。武帝谓刘仲雄曰：“卿数省王、和不？闻和哀苦过礼，使人忧之。”仲雄曰：“和峤虽备礼，神气不损；王戎虽不备礼，而哀毁骨立。臣以和峤生孝，王戎死孝。陛下不应忧峤，而应忧戎。”
- Wikisource comparison：`content/processed/shishuo/collation/wikisource-sbck/dexing.md`（字符/结构参考；当前无句读）

### 02-yanyu-087 ·  · short_entry

- 自动分类：exact-agreement / exact_reference_agreement, single_reference_only
- transfer_class：`exact_character_transfer`；reference_case：`single_reference_but_exact`
- exact_transfer：`True`
- round-trip：`pass`
- canonical：林公見東陽長山曰何其坦迤
- 转移句读：林公見東陽長山曰：“何其坦迤！”
- local TXT reference：林公见东阳长山曰：“何其坦迤！”
- Wikisource comparison：`content/processed/shishuo/collation/wikisource-sbck/yanyu.md`（字符/结构参考；当前无句读）

### 02-yanyu-090 ·  · punctuation_complexity

- 自动分类：exact-agreement / exact_reference_agreement, single_reference_only
- transfer_class：`exact_character_transfer`；reference_case：`single_reference_but_exact`
- exact_transfer：`True`
- round-trip：`pass`
- canonical：孝武將講孝經謝公兄弟與諸人私庭講習

車武子難苦問謝謂袁羊曰
不問則德音有遺多問則重勞二謝
袁曰必
無此嫌車曰何以知爾袁曰何嘗見明鏡疲於屢照

清流憚於惠風
- 转移句读：孝武將講《孝經》，謝公兄弟與諸人私庭講習。車武子難苦問謝，謂袁羊曰：“不問則德音有遺，多問則重勞二謝。”袁曰：“必無此嫌。”車曰：“何以知爾？”袁曰：“何嘗見明鏡疲於屢照，清流憚於惠風？”
- local TXT reference：孝武将讲《孝经》，谢公兄弟与诸人私庭讲习。车武子难苦问谢，谓袁羊曰：“不问则德音有遗，多问则重劳二谢。”袁曰：“必无此嫌。”车曰：“何以知尔？”袁曰：“何尝见明镜疲于屡照，清流惮于惠风？”
- Wikisource comparison：`content/processed/shishuo/collation/wikisource-sbck/yanyu.md`（字符/结构参考；当前无句读）

### 03-zhengshi-001 ·  · punctuation_complexity

- 自动分类：exact-agreement / exact_reference_agreement, single_reference_only
- transfer_class：`exact_character_transfer`；reference_case：`single_reference_but_exact`
- exact_transfer：`True`
- round-trip：`pass`
- canonical：陳仲弓為太丘長時吏有詐稱母病求假事覺收之
令吏殺焉主簿請付獄考衆姦仲弓曰欺君不忠病
母不孝不忠不孝其罪莫大考求衆姦豈復過此
- 转移句读：陳仲弓為太丘長，時吏有詐稱母病求假。事覺，收之，令吏殺焉。主簿請付獄考衆姦，仲弓曰：“欺君不忠，病母不孝。不忠不孝，其罪莫大。考求衆姦，豈復過此？”
- local TXT reference：陈仲弓为太丘长，时吏有诈称母病求假。事觉，收之，令吏杀焉。主簿请付狱考众奸，仲弓曰：“欺君不忠，病母不孝。不忠不孝，其罪莫大。考求众奸，岂复过此？”
- Wikisource comparison：`content/processed/shishuo/collation/wikisource-sbck/zhengshi.md`（字符/结构参考；当前无句读）

### 03-zhengshi-021 ·  · short_entry

- 自动分类：exact-agreement / exact_reference_agreement, single_reference_only
- transfer_class：`exact_character_transfer`；reference_case：`single_reference_but_exact`
- exact_transfer：`True`
- round-trip：`pass`
- canonical：山遐去東陽王長史就簡文索東陽云承藉猛政故
可以和靜致治
- 转移句读：山遐去東陽，王長史就簡文索東陽云：“承藉猛政，故可以和靜致治。”
- local TXT reference：山遐去东阳，王长史就简文索东阳云：“承藉猛政，故可以和静致治。”
- Wikisource comparison：`content/processed/shishuo/collation/wikisource-sbck/zhengshi.md`（字符/结构参考；当前无句读）

### 04-wenxue-027 ·  · short_entry

- 自动分类：exact-agreement / exact_reference_agreement, single_reference_only
- transfer_class：`exact_character_transfer`；reference_case：`single_reference_but_exact`
- exact_transfer：`True`
- round-trip：`pass`
- canonical：殷中軍云康伯未得我牙後慧
- 转移句读：殷中軍云：“康伯未得我牙後慧。”
- local TXT reference：殷中军云：“康伯未得我牙后慧。”
- Wikisource comparison：`content/processed/shishuo/collation/wikisource-sbck/wenxue.md`（字符/结构参考；当前无句读）

### 04-wenxue-079 ·  · punctuation_complexity

- 自动分类：exact-agreement / exact_reference_agreement, single_reference_only
- transfer_class：`exact_character_transfer`；reference_case：`single_reference_but_exact`
- exact_transfer：`True`
- round-trip：`pass`
- canonical：庾仲初作揚都賦成以呈庾亮亮以親族之懷大為
其名價云可三二京四三都於此人人競寫都下紙
為之貴謝太傅云不得爾此是屋下架屋耳事事擬
學而不免儉狹
- 转移句读：庾仲初作《揚都賦》成，以呈庾亮。亮以親族之懷，大為其名價，云：“可三《二京》，四《三都》。”於此人人競寫，都下紙為之貴。謝太傅云：“不得爾，此是屋下架屋耳，事事擬學，而不免儉狹。”
- local TXT reference：庾仲初作《扬都赋》成，以呈庾亮。亮以亲族之怀，大为其名价，云：“可三《二京》，四《三都》。”于此人人竞写，都下纸为之贵。谢太傅云：“不得尔，此是屋下架屋耳，事事拟学，而不免俭狭。”
- Wikisource comparison：`content/processed/shishuo/collation/wikisource-sbck/wenxue.md`（字符/结构参考；当前无句读）

### 05-fangzheng-012 ·  · punctuation_complexity

- 自动分类：exact-agreement / exact_reference_agreement, single_reference_only
- transfer_class：`exact_character_transfer`；reference_case：`single_reference_but_exact`
- exact_transfer：`True`
- round-trip：`pass`
- canonical：杜預之荆州頓七里橋朝士悉祖


預少賤好
豪侠不爲物所許楊濟既名氏雄俊不堪不坐而去
須臾和長輿
來問楊右衛何在客曰向來不坐而去長輿曰必大
夏門下盤馬往大夏門果大閲騎長輿抱內車共載
歸坐如初
- 转移句读：杜預之荆州，頓七里橋，朝士悉祖。預少賤，好豪侠，不爲物所許。楊濟既名氏雄俊，不堪，不坐而去。須臾，和長輿來，問：“楊右衛何在？”客曰：“向來，不坐而去。”長輿曰：“必大夏門下盤馬。”往大夏門，果大閲騎。長輿抱內車，共載歸，坐如初。
- local TXT reference：杜预之荆州，顿七里桥，朝士悉祖。预少贱，好豪侠，不为物所许。杨济既名氏雄俊，不堪，不坐而去。须臾，和长舆来，问：“杨右卫何在？”客曰：“向来，不坐而去。”长舆曰：“必大夏门下盘马。”往大夏门，果大阅骑。长舆抱内车，共载归，坐如初。
- Wikisource comparison：`content/processed/shishuo/collation/wikisource-sbck/fangzheng.md`（字符/结构参考；当前无句读）

### 05-fangzheng-014 ·  · known_segmentation_anomaly

- 自动分类：alignment-failure / reference_insertion, structural_alignment_failure
- transfer_class：`structural_or_boundary_mismatch`；reference_case：`character_count_mismatch`
- exact_transfer：`False`
- round-trip：`not_available`
- canonical：晉武帝時荀朂爲中書監和嶠爲令故事監令由來共車嶠性雅正常疾朂謟䛕後公車來嶠便登正向前坐不復容朂朂方更覓車然得去監令各給車自此始
- 转移句读：（无安全候选）
- local TXT reference：晋武帝时，荀勖为中书监，和峤为令。故事，监、令由来共车。峤性雅正，常疾勖谄谀。后公车来，峤便登，正向前坐，不复容勖。勖方更觅车，然后得去。监、令各给车自此始。
- Wikisource comparison：`content/processed/shishuo/collation/wikisource-sbck/fangzheng.md`（字符/结构参考；当前无句读）

### 05-fangzheng-040 ·  · short_entry

- 自动分类：exact-agreement / exact_reference_agreement, single_reference_only
- transfer_class：`exact_character_transfer`；reference_case：`single_reference_but_exact`
- exact_transfer：`True`
- round-trip：`pass`
- canonical：王丞相作女伎施設牀席蔡公先在坐不説而去王
亦不留
- 转移句读：王丞相作女伎，施設牀席。蔡公先在坐，不説而去，王亦不留。
- local TXT reference：王丞相作女伎，施设床席。蔡公先在坐，不说而去，王亦不留。
- Wikisource comparison：`content/processed/shishuo/collation/wikisource-sbck/fangzheng.md`（字符/结构参考；当前无句读）

### 06-yaliang-006 ·  · short_entry

- 自动分类：exact-agreement / exact_reference_agreement, single_reference_only
- transfer_class：`exact_character_transfer`；reference_case：`single_reference_but_exact`
- exact_transfer：`True`
- round-trip：`pass`
- canonical：王戎爲侍中南郡太守劉肈遺筒中箋布五端戎雖
不受厚報其書
- 转移句读：王戎爲侍中，南郡太守劉肈遺筒中箋布五端，戎雖不受，厚報其書。
- local TXT reference：王戎为侍中，南郡太守刘肈遗筒中笺布五端，戎虽不受，厚报其书。
- Wikisource comparison：`content/processed/shishuo/collation/wikisource-sbck/yaliang.md`（字符/结构参考；当前无句读）

### 06-yaliang-038 ·  · punctuation_complexity

- 自动分类：exact-agreement / exact_reference_agreement, single_reference_only
- transfer_class：`exact_character_transfer`；reference_case：`single_reference_but_exact`
- exact_transfer：`True`
- round-trip：`pass`
- canonical：王僧彌謝車騎共王小奴許集僧
彌舉酒勸謝云奉使君一觴謝曰可爾

僧彌勃然起作色曰汝故是吳興溪中釣碣耳何敢
譸張謝徐撫掌而笑曰衛軍
僧彌殊不肅省乃侵陵上國也
- 转移句读：王僧彌、謝車騎共王小奴許集，僧彌舉酒勸謝云：“奉使君一觴。”謝曰：“可爾。”僧彌勃然起，作色曰：“汝故是吳興溪中釣碣耳！何敢譸張！”謝徐撫掌而笑曰：“衛軍，僧彌殊不肅省，乃侵陵上國也。”
- local TXT reference：王僧弥、谢车骑共王小奴许集，僧弥举酒劝谢云：“奉使君一觞。”谢曰：“可尔。”僧弥勃然起，作色曰：“汝故是吴兴溪中钓碣耳！何敢诪张！”谢徐抚掌而笑曰：“卫军，僧弥殊不肃省，乃侵陵上国也。”
- Wikisource comparison：`content/processed/shishuo/collation/wikisource-sbck/yaliang.md`（字符/结构参考；当前无句读）

### 07-shijian-005 ·  · punctuation_complexity

- 自动分类：exact-agreement / exact_reference_agreement, single_reference_only
- transfer_class：`exact_character_transfer`；reference_case：`single_reference_but_exact`
- exact_transfer：`True`
- round-trip：`pass`
- canonical：王夷甫父乂爲平北將軍有公事使行人論不得時
夷甫在京師命駕見僕射羊祜尚書山濤夷甫時總
角姿才秀異叙致既快事加有理濤甚奇之既退看

之不輟乃嘆曰生兒不當如王夷甫邪羊祜曰亂天
下者必此子也
- 转移句读：王夷甫父乂爲平北將軍，有公事，使行人論，不得。時夷甫在京師，命駕見僕射羊祜、尚書山濤。夷甫時總角，姿才秀異，叙致既快，事加有理，濤甚奇之。既退，看之不輟，乃嘆曰：“生兒不當如王夷甫邪？”羊祜曰：“亂天下者，必此子也！”
- local TXT reference：王夷甫父乂为平北将军，有公事，使行人论，不得。时夷甫在京师，命驾见仆射羊祜、尚书山涛。夷甫时总角，姿才秀异，叙致既快，事加有理，涛甚奇之。既退，看之不辍，乃叹曰：“生儿不当如王夷甫邪？”羊祜曰：“乱天下者，必此子也！”
- Wikisource comparison：`content/processed/shishuo/collation/wikisource-sbck/shijian.md`（字符/结构参考；当前无句读）

### 07-shijian-012 ·  · short_entry

- 自动分类：exact-agreement / exact_reference_agreement, single_reference_only
- transfer_class：`exact_character_transfer`；reference_case：`single_reference_but_exact`
- exact_transfer：`True`
- round-trip：`pass`
- canonical：王平子素不知眉子曰志大其量終當死塢壁間
- 转移句读：王平子素不知眉子，曰：“志大其量，終當死塢壁間。”
- local TXT reference：王平子素不知眉子，曰：“志大其量，终当死坞壁间。”
- Wikisource comparison：`content/processed/shishuo/collation/wikisource-sbck/shijian.md`（字符/结构参考；当前无句读）

### 08-shangyu-003 ·  · punctuation_complexity

- 自动分类：exact-agreement / exact_reference_agreement, single_reference_only
- transfer_class：`exact_character_transfer`；reference_case：`single_reference_but_exact`
- exact_transfer：`True`
- round-trip：`pass`
- canonical：謝子微見許子將兄弟曰平輿之淵有二龍焉見許

子政弱冠之時歎曰若許子政者有榦國之器正色
忠謇則陳仲舉之匹






伐惡退不肖范孟
博之風
- 转移句读：謝子微見許子將兄弟，曰：“平輿之淵，有二龍焉。”見許子政弱冠之時，歎曰：“若許子政者，有榦國之器。正色忠謇，則陳仲舉之匹；伐惡退不肖，范孟博之風。”
- local TXT reference：谢子微见许子将兄弟，曰：“平舆之渊，有二龙焉。”见许子政弱冠之时，叹曰：“若许子政者，有干国之器。正色忠謇，则陈仲举之匹；伐恶退不肖，范孟博之风。”
- Wikisource comparison：`content/processed/shishuo/collation/wikisource-sbck/shangyu.md`（字符/结构参考；当前无句读）

### 08-shangyu-056 ·  · short_entry

- 自动分类：exact-agreement / exact_reference_agreement, single_reference_only
- transfer_class：`exact_character_transfer`；reference_case：`single_reference_but_exact`
- exact_transfer：`True`
- round-trip：`pass`
- canonical：世目周侯嶷如斷山
- 转移句读：世目周侯：嶷如斷山。
- local TXT reference：世目周侯：嶷如断山。
- Wikisource comparison：`content/processed/shishuo/collation/wikisource-sbck/shangyu.md`（字符/结构参考；当前无句读）

### 08-shangyu-084 ·  · known_segmentation_anomaly

- 自动分类：character-disagreement / reference_character_variant, single_reference_only
- transfer_class：`character_mismatch_around_punctuation`；reference_case：`single_reference_character_variant`
- exact_transfer：`False`
- round-trip：`pass`
- canonical：王長史道江道羣人所應有乃不必有人所應無已必無
- 转移句读：王長史道江道羣：“人所應有，乃不必有；人所應無，已必無。”
- local TXT reference：王长史道江道群：“人可应有，乃不必有；人可应无，己必无。”
- Wikisource comparison：`content/processed/shishuo/collation/wikisource-sbck/shangyu.md`（字符/结构参考；当前无句读）

### 08-shangyu-085 ·  · known_segmentation_anomaly

- 自动分类：character-disagreement / reference_character_variant, single_reference_only
- transfer_class：`character_mismatch_around_punctuation`；reference_case：`single_reference_character_variant`
- exact_transfer：`False`
- round-trip：`pass`
- canonical：會稽孔沉魏顗虞球虞存謝奉並是四族之儁于時之傑孫興公目之曰沉爲孔家金顗爲魏家玉虞爲長琳宗謝爲弘道伏
- 转移句读：會稽孔沉、魏顗、虞球、虞存、謝奉並是四族之儁，于時之傑。孫興公目之曰：“沉爲孔家金，顗爲魏家玉，虞爲長、琳宗，謝爲弘道伏。”
- local TXT reference：会稽孔沈、魏顗、虞球、虞存、谢奉并是四族之俊，于时之桀。孙兴公目之曰：“沈为孔家金，顗为魏家玉，虞为长、琳宗，谢为弘道伏。”
- Wikisource comparison：`content/processed/shishuo/collation/wikisource-sbck/shangyu.md`（字符/结构参考；当前无句读）

### 09-pinzao-051 ·  · short_entry

- 自动分类：exact-agreement / exact_reference_agreement, single_reference_only
- transfer_class：`exact_character_transfer`；reference_case：`single_reference_but_exact`
- exact_transfer：`True`
- round-trip：`pass`
- canonical：世目殷中軍思緯淹通比羊叔子
- 转移句读：世目殷中軍：“思緯淹通，比羊叔子。”
- local TXT reference：世目殷中军：“思纬淹通，比羊叔子。”
- Wikisource comparison：`content/processed/shishuo/collation/wikisource-sbck/pinzao.md`（字符/结构参考；当前无句读）

### 09-pinzao-076 ·  · punctuation_complexity

- 自动分类：exact-agreement / exact_reference_agreement, single_reference_only
- transfer_class：`exact_character_transfer`；reference_case：`single_reference_but_exact`
- exact_transfer：`True`
- round-trip：`pass`
- canonical：王孝伯問謝太傅林公何如長史太傅曰長史韶興
問何如劉尹謝曰噫劉尹秀王曰若如公言並不如
此二人邪謝云身意正爾也
- 转移句读：王孝伯問謝太傅：“林公何如長史？”太傅曰：“長史韶興。”問：“何如劉尹？”謝曰：“噫！劉尹秀。”王曰：“若如公言，並不如此二人邪？”謝云：“身意正爾也。”
- local TXT reference：王孝伯问谢太傅：“林公何如长史？”太傅曰：“长史韶兴。”问：“何如刘尹？”谢曰：“噫！刘尹秀。”王曰：“若如公言，并不如此二人邪？”谢云：“身意正尔也。”
- Wikisource comparison：`content/processed/shishuo/collation/wikisource-sbck/pinzao.md`（字符/结构参考；当前无句读）

### 10-guizhen-001 ·  · punctuation_complexity

- 自动分类：exact-agreement / exact_reference_agreement, single_reference_only
- transfer_class：`exact_character_transfer`；reference_case：`single_reference_but_exact`
- exact_transfer：`True`
- round-trip：`pass`
- canonical：漢武帝乳母嘗於外犯事帝欲申憲乳母求救東方
朔
朔曰此非脣舌所爭爾必望濟
者將去時但當屢顧帝慎勿言此或可萬一冀耳乳
母既至朔亦侍側因謂曰汝癡耳帝豈復憶汝乳哺
時恩邪帝雖才雄心忍亦深有情戀乃悽然愍之即
敕免罪
- 转移句读：漢武帝乳母嘗於外犯事，帝欲申憲，乳母求救東方朔。朔曰：“此非脣舌所爭，爾必望濟者，將去時但當屢顧帝，慎勿言，此或可萬一冀耳。”乳母既至，朔亦侍側，因謂曰：“汝癡耳！帝豈復憶汝乳哺時恩邪？”帝雖才雄心忍，亦深有情戀，乃悽然愍之，即敕免罪。
- local TXT reference：汉武帝乳母尝于外犯事，帝欲申宪，乳母求救东方朔。朔曰：“此非唇舌所争，尔必望济者，将去时但当屡顾帝，慎勿言，此或可万一冀耳。”乳母既至，朔亦侍侧，因谓曰：“汝痴耳！帝岂复忆汝乳哺时恩邪？”帝虽才雄心忍，亦深有情恋，乃凄然愍之，即敕免罪。
- Wikisource comparison：`content/processed/shishuo/collation/wikisource-sbck/guizhen.md`（字符/结构参考；当前无句读）

### 10-guizhen-022 ·  · short_entry

- 自动分类：exact-agreement / exact_reference_agreement, single_reference_only
- transfer_class：`exact_character_transfer`；reference_case：`single_reference_but_exact`
- exact_transfer：`True`
- round-trip：`pass`
- canonical：王大語東亭卿乃復論成不惡那得與僧彌戲
- 转移句读：王大語東亭：“卿乃復論成不惡，那得與僧彌戲！”
- local TXT reference：王大语东亭：“卿乃复论成不恶，那得与僧弥戏！”
- Wikisource comparison：`content/processed/shishuo/collation/wikisource-sbck/guizhen.md`（字符/结构参考；当前无句读）

### 11-jiewu-002 ·  · short_entry

- 自动分类：character-disagreement / reference_character_variant, single_reference_only
- transfer_class：`character_mismatch_around_punctuation`；reference_case：`single_reference_character_variant`
- exact_transfer：`False`
- round-trip：`pass`
- canonical：人餉魏武一桮酪魏武噉少許葢頭上題合字以示
衆衆莫能解次至楊脩脩便噉曰公敎人噉一口也
復何疑
- 转移句读：人餉魏武一桮酪，魏武噉少許，葢頭上題“合”字以示衆。衆莫能解。次至楊脩，脩便噉，曰：“公敎人噉一口也，復何疑？”
- local TXT reference：人饷魏武一杯酪，魏武噉少许，盖头上题“合”字以示众。众莫能解。次至杨修，修便噉，曰：“公教人噉一口也，复何疑？”
- Wikisource comparison：`content/processed/shishuo/collation/wikisource-sbck/jiewu.md`（字符/结构参考；当前无句读）

### 11-jiewu-005 ·  · punctuation_complexity

- 自动分类：character-disagreement / reference_character_variant, single_reference_only
- transfer_class：`character_mismatch_around_punctuation`；reference_case：`single_reference_character_variant`
- exact_transfer：`False`
- round-trip：`pass`
- canonical：王敦引軍垂至大桁明帝自出中堂温嶠為丹陽尹
帝令斷大桁故未斷帝大怒瞋目左右莫不悚懼

召諸公來嶠至不謝但求酒炙王導須

吏至徒跣下地謝曰天威在顔遂使温嶠不容得謝
嶠於是下謝帝廼釋然諸公共嘆王機悟名言
- 转移句读：王敦引軍垂至大桁，明帝自出中堂。温嶠為丹陽尹，帝令斷大桁，故未斷，帝大怒，瞋目，左右莫不悚懼。召諸公來。嶠至，不謝，但求酒炙。王導須吏至，徒跣下地，謝曰：“天威在顔，遂使温嶠不容得謝。”嶠於是下謝，帝廼釋然。諸公共嘆王機悟名言。
- local TXT reference：王敦引军垂至大桁，明帝自出中堂。温峤为丹阳尹，帝令断大桁，故未断，帝大怒，瞋目，左右莫不悚惧。召诸公来。峤至，不谢，但求酒炙。王导须臾至，徒跣下地，谢曰：“天威在颜，遂使温峤不容得谢。”峤于是下谢，帝乃释然。诸公共叹王机悟名言。
- Wikisource comparison：`content/processed/shishuo/collation/wikisource-sbck/jiewu.md`（字符/结构参考；当前无句读）

### 12-suhui-001 ·  · punctuation_complexity

- 自动分类：character-disagreement / reference_character_variant, single_reference_only
- transfer_class：`character_mismatch_around_punctuation`；reference_case：`single_reference_character_variant`
- exact_transfer：`False`
- round-trip：`pass`
- canonical：賔客詣陳太丘宿太丘使元方季方炊客與太丘論
議二人進火俱委而竊聽炊忘箸箄飯落釡中太丘
問炊何不餾元方季方長跪曰大人與客語乃俱竊
聽炊忘箸箄飯今成糜太丘曰爾頗有所識不對曰
仿佛志之二子俱説更相易奪言無遺失太丘曰如

此但糜自可何必飯也
- 转移句读：賔客詣陳太丘宿，太丘使元方、季方炊。客與太丘論議，二人進火，俱委而竊聽。炊忘箸箄，飯落釡中。太丘問：“炊何不餾？”元方、季方長跪曰：“大人與客語，乃俱竊聽，炊忘箸箄，飯今成糜。”太丘曰：“爾頗有所識不？”對曰：“仿佛志之。”二子俱説，更相易奪，言無遺失。太丘曰：“如此，但糜自可，何必飯也？”
- local TXT reference：宾客诣陈太丘宿，太丘使元方、季方炊。客与太丘论议，二人进火，俱委而窃听。炊忘着箄，饭落釜中。太丘问：“炊何不馏？”元方、季方长跪曰：“大人与客语，乃俱窃听，炊忘着箄，饭今成糜。”太丘曰：“尔颇有所识不？”对曰：“仿佛志之。”二子俱说，更相易夺，言无遗失。太丘曰：“如此，但糜自可，何必饭也？”
- Wikisource comparison：`content/processed/shishuo/collation/wikisource-sbck/suhui.md`（字符/结构参考；当前无句读）

### 12-suhui-002 ·  · short_entry

- 自动分类：character-disagreement / reference_character_variant, single_reference_only
- transfer_class：`character_mismatch_around_punctuation`；reference_case：`single_reference_character_variant`
- exact_transfer：`False`
- round-trip：`pass`
- canonical：何晏七歲明惠若神魏武竒愛之因晏在宫内欲以
為子晏乃畫地令方自處其中人問其故答曰何氏
之廬也魏武知之即遣還
- 转移句读：何晏七歲，明惠若神，魏武竒愛之。因晏在宫内，欲以為子。晏乃畫地令方，自處其中。人問其故，答曰：“何氏之廬也。”魏武知之，即遣還。
- local TXT reference：何晏七岁，明惠若神，魏武奇爱之。因晏在宫内，欲以为子。晏乃画地令方，自处其中。人问其故，答曰：“何氏之庐也。”魏武知之，即遣还。
- Wikisource comparison：`content/processed/shishuo/collation/wikisource-sbck/suhui.md`（字符/结构参考；当前无句读）

### 13-haoshuang-009 ·  · short_entry

- 自动分类：exact-agreement / exact_reference_agreement, single_reference_only
- transfer_class：`exact_character_transfer`；reference_case：`single_reference_but_exact`
- exact_transfer：`True`
- round-trip：`pass`
- canonical：桓公讀高士傳至於陵仲子便擲去曰誰能作此溪

刻自處
- 转移句读：桓公讀《高士傳》至於陵仲子，便擲去，曰：“誰能作此溪刻自處！”
- local TXT reference：桓公读《高士传》至于陵仲子，便掷去，曰：“谁能作此溪刻自处！”
- Wikisource comparison：`content/processed/shishuo/collation/wikisource-sbck/haoshuang.md`（字符/结构参考；当前无句读）

### 13-haoshuang-011 ·  · punctuation_complexity

- 自动分类：exact-agreement / exact_reference_agreement, single_reference_only
- transfer_class：`exact_character_transfer`；reference_case：`single_reference_but_exact`
- exact_transfer：`True`
- round-trip：`pass`
- canonical：陳林道在西岸都下諸人共
要至牛渚會陳理既佳人欲共言折陳以如意拄頰
望雞籠山嘆曰孫伯符志業不遂



於是竟坐不得談
- 转移句读：陳林道在西岸，都下諸人共要至牛渚會。陳理既佳，人欲共言折。陳以如意拄頰，望雞籠山嘆曰：“孫伯符志業不遂！”於是竟坐不得談。
- local TXT reference：陈林道在西岸，都下诸人共要至牛渚会。陈理既佳，人欲共言折。陈以如意拄颊，望鸡笼山叹曰：“孙伯符志业不遂！”于是竟坐不得谈。
- Wikisource comparison：`content/processed/shishuo/collation/wikisource-sbck/haoshuang.md`（字符/结构参考；当前无句读）

### 14-rongzhi-006 ·  · short_entry

- 自动分类：exact-agreement / exact_reference_agreement, single_reference_only
- transfer_class：`exact_character_transfer`；reference_case：`single_reference_but_exact`
- exact_transfer：`True`
- round-trip：`pass`
- canonical：裴令公目王安豐眼爛爛如巖下電
- 转移句读：裴令公目王安豐：“眼爛爛如巖下電。”
- local TXT reference：裴令公目王安丰：“眼烂烂如岩下电。”
- Wikisource comparison：`content/processed/shishuo/collation/wikisource-sbck/rongzhi.md`（字符/结构参考；当前无句读）

### 14-rongzhi-034 ·  · punctuation_complexity

- 自动分类：exact-agreement / exact_reference_agreement, single_reference_only
- transfer_class：`exact_character_transfer`；reference_case：`single_reference_but_exact`
- exact_transfer：`True`
- round-trip：`pass`
- canonical：簡文作相王時與謝公共詣桓宣武王珣先在内桓
語王卿嘗欲見相王可住帳裏二客既去桓謂王曰

定何如王曰相王作輔自然湛若神君
公亦萬夫之望不然僕射何得自没
- 转移句读：簡文作相王時，與謝公共詣桓宣武。王珣先在内，桓語王：“卿嘗欲見相王，可住帳裏。”二客既去，桓謂王曰：“定何如？”王曰：“相王作輔，自然湛若神君。公亦萬夫之望，不然，僕射何得自没？”
- local TXT reference：简文作相王时，与谢公共诣桓宣武。王珣先在内，桓语王：“卿尝欲见相王，可住帐里。”二客既去，桓谓王曰：“定何如？”王曰：“相王作辅，自然湛若神君。公亦万夫之望，不然，仆射何得自没？”
- Wikisource comparison：`content/processed/shishuo/collation/wikisource-sbck/rongzhi.md`（字符/结构参考；当前无句读）

### 15-zixin-001 ·  · punctuation_complexity

- 自动分类：character-disagreement / reference_character_variant, single_reference_only
- transfer_class：`character_mismatch_around_punctuation`；reference_case：`single_reference_character_variant`
- exact_transfer：`False`
- round-trip：`pass`
- canonical：周處年少時兇彊俠氣為鄉里所患
又義興水中有
蛟山中有邅跡虎並皆㬥犯百姓義興人謂為
三横而處尤劇或說處殺虎斬蛟實冀三横唯餘其
一處即刺殺虎又入水擊蛟蛟或浮或没行數十里
處與之俱經三日三夜鄉里皆謂已死更相慶竟殺
蛟而出聞里人相慶始知為人情所患有自改意

乃自吳
尋二陸平原不在正見清河具以情告并云欲自修
改而年已蹉跎終無所成清河曰古人貴朝聞夕死
况君前途尚可且人患志之不立亦何憂令名不彰
耶處遂改勵終為忠臣孝子
- 转移句读：周處年少時，兇彊俠氣，為鄉里所患。又義興水中有蛟，山中有邅跡虎，並皆㬥犯百姓，義興人謂為三横，而處尤劇。或說處殺虎斬蛟，實冀三横唯餘其一。處即刺殺虎，又入水擊蛟，蛟或浮或没，行數十里，處與之俱。經三日三夜，鄉里皆謂已死，更相慶。竟殺蛟而出，聞里人相慶，始知為人情所患，有自改意。乃自吳尋二陸，平原不在，正見清河，具以情告，并云欲自修改而年已蹉跎，終無所成。清河曰：“古人貴朝聞夕死，况君前途尚可。且人患志之不立，亦何憂令名不彰耶？”處遂改勵，終為忠臣孝子。
- local TXT reference：周处年少时，凶强侠气，为乡里所患。又义兴水中有蛟，山中有邅迹虎，并皆暴犯百姓，义兴人谓为三横，而处尤剧。或说处杀虎斩蛟，实冀三横唯余其一。处即刺杀虎，又入水击蛟，蛟或浮或没，行数十里，处与之俱。经三日三夜，乡里皆谓已死，更相庆。竟杀蛟而出，闻里人相庆，始知为人情所患，有自改意。乃自吴寻二陆，平原不在，正见清河，具以情告，并云欲自修改而年已蹉跎，终无所成。清河曰：“古人贵朝闻夕死，况君前途尚可。且人患志之不立，亦何忧令名不彰邪？”处遂改励，终为忠臣孝子。
- Wikisource comparison：`content/processed/shishuo/collation/wikisource-sbck/zixin.md`（字符/结构参考；当前无句读）

### 15-zixin-002 ·  · short_entry

- 自动分类：character-disagreement / reference_character_variant, single_reference_only
- transfer_class：`character_mismatch_around_punctuation`；reference_case：`single_reference_character_variant`
- exact_transfer：`False`
- round-trip：`pass`
- canonical：戴淵少時遊俠不治行檢嘗在江淮間攻掠商旅陸
機赴假還洛輜重甚盛淵使少年掠刼淵在岸上據
胡牀指麾左右皆得其宜淵既神姿峰頴雖處鄙事

神氣猶異機於船屋上遥謂之曰卿才如此亦復作
刼邪淵便泣涕投劒歸機辭厲非常機彌重之定交
作筆薦焉


過江仕至征西將軍
- 转移句读：戴淵少時遊俠，不治行檢，嘗在江、淮間攻掠商旅。陸機赴假還洛，輜重甚盛，淵使少年掠刼。淵在岸上，據胡牀指麾左右，皆得其宜。淵既神姿峰頴，雖處鄙事，神氣猶異。機於船屋上遥謂之曰：“卿才如此，亦復作刼邪？”淵便泣涕，投劒歸機，辭厲非常。機彌重之，定交，作筆薦焉。過江，仕至征西將軍。
- local TXT reference：戴渊少时游侠，不治行检，尝在江、淮间攻掠商旅。陆机赴假还洛，辎重甚盛，渊使少年掠劫。渊在岸上，据胡床指麾左右，皆得其宜。渊既神姿峰颖，虽处鄙事，神气犹异。机于船屋上遥谓之曰：“卿才如此，亦复作劫邪？”渊便泣涕，投剑归机，辞厉非常。机弥重之，定交，作笔荐焉。过江，仕至征西将军。
- Wikisource comparison：`content/processed/shishuo/collation/wikisource-sbck/zixin.md`（字符/结构参考；当前无句读）

### 16-qixian-002 ·  · punctuation_complexity

- 自动分类：character-disagreement / reference_character_variant, single_reference_only
- transfer_class：`character_mismatch_around_punctuation`；reference_case：`single_reference_character_variant`
- exact_transfer：`False`
- round-trip：`pass`
- canonical：王丞相過江自說昔在洛水邉數與裴成公阮千里

諸賢共談道羊曼曰人久以此許卿何須復爾王曰
亦不言我須此但欲爾時不可得耳
- 转移句读：王丞相過江，自說昔在洛水邉，數與裴成公、阮千里諸賢共談道。羊曼曰：“人久以此許卿，何須復爾？”王曰：“亦不言我須此，但欲爾時不可得耳！”
- local TXT reference：王丞相过江，自说昔在洛水边，数与裴成公、阮千里诸贤共谈道。羊曼曰：“人久以此许卿，何须复尔？”王曰：“亦不言我须此，但欲尔时不可得耳！”
- Wikisource comparison：`content/processed/shishuo/collation/wikisource-sbck/qixian.md`（字符/结构参考；当前无句读）

### 16-qixian-005 ·  · short_entry

- 自动分类：character-disagreement / reference_character_variant, single_reference_only
- transfer_class：`character_mismatch_around_punctuation`；reference_case：`single_reference_character_variant`
- exact_transfer：`False`
- round-trip：`pass`
- canonical：郄嘉賓得人以已比符堅大喜
- 转移句读：郄嘉賓得人以已比符堅，大喜。
- local TXT reference：郗嘉宾得人以己比苻坚，大喜。
- Wikisource comparison：`content/processed/shishuo/collation/wikisource-sbck/qixian.md`（字符/结构参考；当前无句读）

### 17-shangshi-005 ·  · short_entry

- 自动分类：exact-agreement / exact_reference_agreement, single_reference_only
- transfer_class：`exact_character_transfer`；reference_case：`single_reference_but_exact`
- exact_transfer：`True`
- round-trip：`pass`
- canonical：有人哭和長輿曰峨峨若千丈松崩
- 转移句读：有人哭和長輿曰：“峨峨若千丈松崩。”
- local TXT reference：有人哭和长舆曰：“峨峨若千丈松崩。”
- Wikisource comparison：`content/processed/shishuo/collation/wikisource-sbck/shangshi.md`（字符/结构参考；当前无句读）

### 17-shangshi-016 ·  · punctuation_complexity

- 自动分类：exact-agreement / exact_reference_agreement, single_reference_only
- transfer_class：`exact_character_transfer`；reference_case：`single_reference_but_exact`
- exact_transfer：`True`
- round-trip：`pass`
- canonical：王子猷子敬俱病篤而子敬先亡
子猷問左右何以都不聞消息此已喪矣語時了不
悲便索輿來奔喪都不哭子敬素好琴便徑入坐靈
牀上取子敬琴彈弦既不調擲地云子敬子敬人琴
俱亡因慟絶良久月餘亦卒
- 转移句读：王子猷、子敬俱病篤，而子敬先亡。子猷問左右：“何以都不聞消息？此已喪矣！”語時了不悲。便索輿來奔喪，都不哭。子敬素好琴，便徑入坐靈牀上，取子敬琴彈，弦既不調，擲地云：“子敬，子敬，人琴俱亡！”因慟絶良久，月餘亦卒。
- local TXT reference：王子猷、子敬俱病笃，而子敬先亡。子猷问左右：“何以都不闻消息？此已丧矣！”语时了不悲。便索舆来奔丧，都不哭。子敬素好琴，便径入坐灵床上，取子敬琴弹，弦既不调，掷地云：“子敬，子敬，人琴俱亡！”因恸绝良久，月余亦卒。
- Wikisource comparison：`content/processed/shishuo/collation/wikisource-sbck/shangshi.md`（字符/结构参考；当前无句读）

### 18-qiyi-002 ·  · known_segmentation_anomaly

- 自动分类：character-disagreement / reference_character_variant, single_reference_only
- transfer_class：`character_mismatch_around_punctuation`；reference_case：`single_reference_character_variant`
- exact_transfer：`False`
- round-trip：`pass`
- canonical：嵇康遊於汲郡山中遇道士孫登遂與之遊康臨去登曰君才則髙矣保身之道不足
- 转移句读：嵇康遊於汲郡山中，遇道士孫登，遂與之遊。康臨去，登曰：“君才則髙矣，保身之道不足。”
- local TXT reference：嵇康游于汲郡山中，遇道士孙登，遂与之游。康临去，登曰：“君才则高矣，保身之道不足。”
- Wikisource comparison：`content/processed/shishuo/collation/wikisource-sbck/qiyi.md`（字符/结构参考；当前无句读）

### 18-qiyi-003 ·  · short_entry

- 自动分类：exact-agreement / exact_reference_agreement, single_reference_only
- transfer_class：`exact_character_transfer`；reference_case：`single_reference_but_exact`
- exact_transfer：`True`
- round-trip：`pass`
- canonical：山公將去選曹欲舉嵇康康與書告絶
- 转移句读：山公將去選曹，欲舉嵇康，康與書告絶。
- local TXT reference：山公将去选曹，欲举嵇康，康与书告绝。
- Wikisource comparison：`content/processed/shishuo/collation/wikisource-sbck/qiyi.md`（字符/结构参考；当前无句读）

### 18-qiyi-009 ·  · punctuation_complexity

- 自动分类：exact-agreement / exact_reference_agreement, single_reference_only
- transfer_class：`exact_character_transfer`；reference_case：`single_reference_but_exact`
- exact_transfer：`True`
- round-trip：`pass`
- canonical：南陽翟道淵與汝南周子南少相友共隐于尋陽庾
太尉說周以當世之務周遂仕翟秉志彌固其後周
詣翟翟不與語
- 转移句读：南陽翟道淵與汝南周子南少相友，共隐于尋陽。庾太尉說周以當世之務，周遂仕，翟秉志彌固。其後周詣翟，翟不與語。
- local TXT reference：南阳翟道渊与汝南周子南少相友，共隐于寻阳。庾太尉说周以当世之务，周遂仕，翟秉志弥固。其后周诣翟，翟不与语。
- Wikisource comparison：`content/processed/shishuo/collation/wikisource-sbck/qiyi.md`（字符/结构参考；当前无句读）

### 18-qiyi-010 ·  · known_segmentation_anomaly

- 自动分类：alignment-failure / reference_insertion, structural_alignment_failure
- transfer_class：`structural_or_boundary_mismatch`；reference_case：`character_count_mismatch`
- exact_transfer：`False`
- round-trip：`not_available`
- canonical：孟萬年及弟少孤居武昌陽新縣萬年遊宦有盛名
當世少孤未嘗出京邑人士思欲見之乃遣信報少
孤云兄病篤狼狽至都時賢見之者莫不嗟重因相
- 转移句读：（无安全候选）
- local TXT reference：孟万年及弟少孤居武昌阳新县。万年游宦，有盛名当世，少孤未尝出，京邑人士思欲见之，乃遣信报少孤云兄病笃。狼狈至都，时贤见之者，莫不嗟重，因相谓曰：“少孤如此，万年可死。”
- Wikisource comparison：`content/processed/shishuo/collation/wikisource-sbck/qiyi.md`（字符/结构参考；当前无句读）

### 18-qiyi-011 ·  · known_segmentation_anomaly

- 自动分类：character-disagreement / reference_character_variant, single_reference_only
- transfer_class：`character_mismatch_around_punctuation`；reference_case：`single_reference_character_variant`
- exact_transfer：`False`
- round-trip：`pass`
- canonical：康僧淵在豫章去郭數十里立精舍㫄連嶺帶長川芳林列於軒庭清流激於堂宇乃閒居研講希心理味𢈔公諸人多往看之觀其運用吐納風流轉佳加已處之怡然亦有以自得聲名乃興後不堪遂出
- 转移句读：康僧淵在豫章，去郭數十里，立精舍。㫄連嶺，帶長川，芳林列於軒庭，清流激於堂宇。乃閒居研講，希心理味，𢈔公諸人多往看之。觀其運用吐納，風流轉佳。加已處之怡然，亦有以自得，聲名乃興。後不堪，遂出。
- local TXT reference：康僧渊在豫章，去郭数十里，立精舍。旁连岭，带长川，芳林列于轩庭，清流激于堂宇。乃闲居研讲，希心理味，庾公诸人多往看之。观其运用吐纳，风流转佳。加已处之怡然，亦有以自得，声名乃兴。后不堪，遂出。
- Wikisource comparison：`content/processed/shishuo/collation/wikisource-sbck/qiyi.md`（字符/结构参考；当前无句读）

### 18-qiyi-015 ·  · known_segmentation_anomaly

- 自动分类：character-disagreement / reference_character_variant, single_reference_only
- transfer_class：`character_mismatch_around_punctuation`；reference_case：`single_reference_character_variant`
- exact_transfer：`False`
- round-trip：`pass`
- canonical：郄超每聞欲高尚隱退者輙為辦百萬資并為造立
居宇在剡為戴公起宅甚精整戴始往舊居與所親

書曰近至剡如官舍郄為傅約亦辦百萬資傳隐事
差互故不果遺
- 转移句读：郄超每聞欲高尚隱退者，輙為辦百萬資，并為造立居宇。在剡為戴公起宅，甚精整。戴始往舊居，與所親書曰：“近至剡，如官舍。”郄為傅約亦辦百萬資，傳隐事差互，故不果遺。
- local TXT reference：郗超每闻欲高尚隐退者，辄为办百万资，并为造立居宇。在剡为戴公起宅，甚精整。戴始往旧居，与所亲书曰：“近至剡，如官舍。”郗为傅约亦办百万资，傅隐事差互，故不果遗。
- Wikisource comparison：`content/processed/shishuo/collation/wikisource-sbck/qiyi.md`（字符/结构参考；当前无句读）

### 19-xianyuan-005 ·  · punctuation_complexity

- 自动分类：exact-agreement / exact_reference_agreement, single_reference_only
- transfer_class：`exact_character_transfer`；reference_case：`single_reference_but_exact`
- exact_transfer：`True`
- round-trip：`pass`
- canonical：趙母嫁女女臨去敕之曰慎勿為好女曰不為好可為惡邪母曰好尚不可為其況惡乎
- 转移句读：趙母嫁女，女臨去，敕之曰：“慎勿為好！”女曰：“不為好，可為惡邪？”母曰：“好尚不可為，其況惡乎？”
- local TXT reference：赵母嫁女，女临去，敕之曰：“慎勿为好！”女曰：“不为好，可为恶邪？”母曰：“好尚不可为，其况恶乎？”
- Wikisource comparison：`content/processed/shishuo/collation/wikisource-sbck/xianyuan.md`（字符/结构参考；当前无句读）

### 19-xianyuan-028 ·  · short_entry

- 自动分类：exact-agreement / exact_reference_agreement, single_reference_only
- transfer_class：`exact_character_transfer`；reference_case：`single_reference_but_exact`
- exact_transfer：`True`
- round-trip：`pass`
- canonical：王江州夫人語謝遏曰汝何以都不復進為
是塵務經心天分有限
- 转移句读：王江州夫人語謝遏曰：“汝何以都不復進？為是塵務經心，天分有限？”
- local TXT reference：王江州夫人语谢遏曰：“汝何以都不复进？为是尘务经心，天分有限？”
- Wikisource comparison：`content/processed/shishuo/collation/wikisource-sbck/xianyuan.md`（字符/结构参考；当前无句读）

### 20-shujie-003 ·  · short_entry

- 自动分类：exact-agreement / exact_reference_agreement, single_reference_only
- transfer_class：`exact_character_transfer`；reference_case：`single_reference_but_exact`
- exact_transfer：`True`
- round-trip：`pass`
- canonical：人有相羊祜父墓後應出受命君祜惡其言遂掘斷
墓後以壞其勢相者立視之曰猶應出折臂三公俄
而祜墜馬折臂位果至公
- 转移句读：人有相羊祜父墓，後應出受命君。祜惡其言，遂掘斷墓後以壞其勢。相者立視之，曰：“猶應出折臂三公。”俄而祜墜馬折臂，位果至公。
- local TXT reference：人有相羊祜父墓，后应出受命君。祜恶其言，遂掘断墓后以坏其势。相者立视之，曰：“犹应出折臂三公。”俄而祜坠马折臂，位果至公。
- Wikisource comparison：`content/processed/shishuo/collation/wikisource-sbck/shujie.md`（字符/结构参考；当前无句读）

### 20-shujie-007 ·  · punctuation_complexity

- 自动分类：exact-agreement / exact_reference_agreement, single_reference_only
- transfer_class：`exact_character_transfer`；reference_case：`single_reference_but_exact`
- exact_transfer：`True`
- round-trip：`pass`
- canonical：郭景純過江居于暨陽墓去水不盈百步時人以爲
近水景純曰將當爲陸
今沙漲去墓數十里
皆爲桑田其詩曰北阜烈烈巨海混混壘壘三墳唯
母與昆
- 转移句读：郭景純過江，居于暨陽，墓去水不盈百步，時人以爲近水。景純曰：“將當爲陸。”今沙漲，去墓數十里皆爲桑田。其詩曰：“北阜烈烈，巨海混混，壘壘三墳，唯母與昆。”
- local TXT reference：郭景纯过江，居于暨阳，墓去水不盈百步，时人以为近水。景纯曰：“将当为陆。”今沙涨，去墓数十里皆为桑田。其诗曰：“北阜烈烈，巨海混混，垒垒三坟，唯母与昆。”
- Wikisource comparison：`content/processed/shishuo/collation/wikisource-sbck/shujie.md`（字符/结构参考；当前无句读）

### 21-qiaoyi-007 ·  · short_entry

- 自动分类：exact-agreement / exact_reference_agreement, single_reference_only
- transfer_class：`exact_character_transfer`；reference_case：`single_reference_but_exact`
- exact_transfer：`True`
- round-trip：`pass`
- canonical：謝太傅云顧長康畫有蒼生來所無
- 转移句读：謝太傅云：“顧長康畫，有蒼生來所無。”
- local TXT reference：谢太傅云：“顾长康画，有苍生来所无。”
- Wikisource comparison：`content/processed/shishuo/collation/wikisource-sbck/qiaoyi.md`（字符/结构参考；当前无句读）

### 21-qiaoyi-009 ·  · punctuation_complexity

- 自动分类：exact-agreement / exact_reference_agreement, single_reference_only
- transfer_class：`exact_character_transfer`；reference_case：`single_reference_but_exact`
- exact_transfer：`True`
- round-trip：`pass`
- canonical：顧長康畫裴叔則頰上益三毛人問其故顧曰裴楷
儁朗有識具正此是其識具看畫者尋之定覺益三
毛如有神明殊勝未安時
- 转移句读：顧長康畫裴叔則，頰上益三毛。人問其故，顧曰：“裴楷儁朗有識具，正此是其識具。”看畫者尋之，定覺益三毛如有神明，殊勝未安時。”
- local TXT reference：顾长康画裴叔则，颊上益三毛。人问其故，顾曰：“裴楷俊朗有识具，正此是其识具。”看画者寻之，定觉益三毛如有神明，殊胜未安时。”
- Wikisource comparison：`content/processed/shishuo/collation/wikisource-sbck/qiaoyi.md`（字符/结构参考；当前无句读）

### 22-chongli-004 ·  · short_entry

- 自动分类：character-disagreement / reference_character_variant, single_reference_only
- transfer_class：`character_mismatch_around_punctuation`；reference_case：`single_reference_character_variant`
- exact_transfer：`False`
- round-trip：`pass`
- canonical：許玄度停都一月劉尹無日不徃乃歎曰卿復少時

不去我成輕薄京尹
- 转移句读：許玄度停都一月，劉尹無日不徃，乃歎曰：“卿復少時不去，我成輕薄京尹！”
- local TXT reference：许玄度停都一月，刘尹无日不往，乃叹曰：“卿复少时不去，我成轻薄京尹！”
- Wikisource comparison：`content/processed/shishuo/collation/wikisource-sbck/chongli.md`（字符/结构参考；当前无句读）

### 22-chongli-006 ·  · punctuation_complexity

- 自动分类：character-disagreement / reference_character_variant, single_reference_only
- transfer_class：`character_mismatch_around_punctuation`；reference_case：`single_reference_character_variant`
- exact_transfer：`False`
- round-trip：`pass`
- canonical：卞範之爲丹陽尹羊孚南州暫還徃卞許云下官疾
動不堪坐卞便開帳拂褥羊徑上大牀入𬒳須枕卞
回坐傾睞移晨逹莫羊去卞語曰我以第一理期卿
卿莫負我
- 转移句读：卞範之爲丹陽尹，羊孚南州暫還，徃卞許，云：“下官疾動不堪坐。”卞便開帳拂褥，羊徑上大牀，入𬒳須枕。卞回坐傾睞，移晨逹莫。羊去，卞語曰：“我以第一理期卿，卿莫負我。”
- local TXT reference：卞范之为丹阳尹，羊孚南州暂还，往卞许，云：“下官疾动不堪坐。”卞便开帐拂褥，羊径上大床，入被须枕。卞回坐倾睐，移晨达莫。羊去，卞语曰：“我以第一理期卿，卿莫负我。”
- Wikisource comparison：`content/processed/shishuo/collation/wikisource-sbck/chongli.md`（字符/结构参考；当前无句读）

### 23-rendan-049 ·  · punctuation_complexity

- 自动分类：exact-agreement / exact_reference_agreement, single_reference_only
- transfer_class：`exact_character_transfer`；reference_case：`single_reference_but_exact`
- exact_transfer：`True`
- round-trip：`pass`
- canonical：王子猷出都尚在渚下舊聞桓子野善吹笛


而不相識遇桓於岸上過王在船中客有
識之者云是桓子野王便令人與相聞云聞君善吹
笛試為我一奏桓時已貴顯素聞王名即便回下車
踞胡牀為作三調弄畢便上車去客主不交一言
- 转移句读：王子猷出都，尚在渚下。舊聞桓子野善吹笛，而不相識。遇桓於岸上過，王在船中，客有識之者云：“是桓子野。”王便令人與相聞，云：“聞君善吹笛，試為我一奏。”桓時已貴顯，素聞王名，即便回下車，踞胡牀，為作三調。弄畢，便上車去。客主不交一言。
- local TXT reference：王子猷出都，尚在渚下。旧闻桓子野善吹笛，而不相识。遇桓于岸上过，王在船中，客有识之者云：“是桓子野。”王便令人与相闻，云：“闻君善吹笛，试为我一奏。”桓时已贵显，素闻王名，即便回下车，踞胡床，为作三调。弄毕，便上车去。客主不交一言。
- Wikisource comparison：`content/processed/shishuo/collation/wikisource-sbck/rendan.md`（字符/结构参考；当前无句读）

### 23-rendan-052 ·  · short_entry

- 自动分类：exact-agreement / exact_reference_agreement, single_reference_only
- transfer_class：`exact_character_transfer`；reference_case：`single_reference_but_exact`
- exact_transfer：`True`
- round-trip：`pass`
- canonical：王佛大歎言三日不飲酒覺形神不復相親
- 转移句读：王佛大歎言：“三日不飲酒，覺形神不復相親。”
- local TXT reference：王佛大叹言：“三日不饮酒，觉形神不复相亲。”
- Wikisource comparison：`content/processed/shishuo/collation/wikisource-sbck/rendan.md`（字符/结构参考；当前无句读）

### 24-jianao-006 ·  · punctuation_complexity

- 自动分类：exact-agreement / exact_reference_agreement, single_reference_only
- transfer_class：`exact_character_transfer`；reference_case：`single_reference_but_exact`
- exact_transfer：`True`
- round-trip：`pass`
- canonical：王平子出為荆州


王太尉及時賢送者傾路時庭中有大
樹上有鵲巢平子脫衣巾徑上樹取鵲子涼衣拘閡
樹枝便復脫去得鵲子還下弄神色自若傍若無人
- 转移句读：王平子出為荆州，王太尉及時賢送者傾路。時庭中有大樹，上有鵲巢。平子脫衣巾，徑上樹取鵲子。涼衣拘閡樹枝，便復脫去。得鵲子還，下弄，神色自若，傍若無人。
- local TXT reference：王平子出为荆州，王太尉及时贤送者倾路。时庭中有大树，上有鹊巢。平子脱衣巾，径上树取鹊子。凉衣拘阂树枝，便复脱去。得鹊子还，下弄，神色自若，傍若无人。
- Wikisource comparison：`content/processed/shishuo/collation/wikisource-sbck/jianao.md`（字符/结构参考；当前无句读）

### 24-jianao-009 ·  · short_entry

- 自动分类：exact-agreement / exact_reference_agreement, single_reference_only
- transfer_class：`exact_character_transfer`；reference_case：`single_reference_but_exact`
- exact_transfer：`True`
- round-trip：`pass`
- canonical：謝萬在兄前欲起索便器于時阮思曠在坐曰新出
門户篤而無禮
- 转移句读：謝萬在兄前，欲起索便器。于時阮思曠在坐曰：“新出門户，篤而無禮。”
- local TXT reference：谢万在兄前，欲起索便器。于时阮思旷在坐曰：“新出门户，笃而无礼。”
- Wikisource comparison：`content/processed/shishuo/collation/wikisource-sbck/jianao.md`（字符/结构参考；当前无句读）

### 25-paidiao-006 ·  · punctuation_complexity

- 自动分类：exact-agreement / exact_reference_agreement, single_reference_only
- transfer_class：`exact_character_transfer`；reference_case：`single_reference_but_exact`
- exact_transfer：`True`
- round-trip：`pass`
- canonical：孫子荆年少時欲隱語王武子當枕石漱流誤曰漱
石枕流王曰流可枕石可漱乎孫曰所以枕流欲洗

其耳
所以漱石欲礪其齒
- 转移句读：孫子荆年少時欲隱，語王武子“當枕石漱流”，誤曰“漱石枕流”。王曰：“流可枕，石可漱乎？”孫曰：“所以枕流，欲洗其耳；所以漱石，欲礪其齒。”
- local TXT reference：孙子荆年少时欲隐，语王武子“当枕石漱流”，误曰“漱石枕流”。王曰：“流可枕，石可漱乎？”孙曰：“所以枕流，欲洗其耳；所以漱石，欲砺其齿。”
- Wikisource comparison：`content/processed/shishuo/collation/wikisource-sbck/paidiao.md`（字符/结构参考；当前无句读）

### 25-paidiao-012 ·  · short_entry

- 自动分类：exact-agreement / exact_reference_agreement, single_reference_only
- transfer_class：`exact_character_transfer`；reference_case：`single_reference_but_exact`
- exact_transfer：`True`
- round-trip：`pass`
- canonical：諸葛令王丞相共爭姓族先後王曰何不言葛王而
云王葛令曰譬言驢馬不言馬驢驢寧勝馬邪
- 转移句读：諸葛令、王丞相共爭姓族先後，王曰：“何不言葛、王，而云王、葛？”令曰：“譬言驢馬，不言馬驢，驢寧勝馬邪？”
- local TXT reference：诸葛令、王丞相共争姓族先后，王曰：“何不言葛、王，而云王、葛？”令曰：“譬言驴马，不言马驴，驴宁胜马邪？”
- Wikisource comparison：`content/processed/shishuo/collation/wikisource-sbck/paidiao.md`（字符/结构参考；当前无句读）

### 25-paidiao-019 ·  · known_segmentation_anomaly

- 自动分类：alignment-failure / reference_deletion, structural_alignment_failure
- transfer_class：`structural_or_boundary_mismatch`；reference_case：`character_count_mismatch`
- exact_transfer：`False`
- round-trip：`not_available`
- canonical：于寳向劉真長
叙其&KR0679;神記

劉
曰卿可謂鬼之董狐
- 转移句读：（无安全候选）
- local TXT reference：干宝向刘真长叙其搜神记，刘曰：“卿可谓鬼之董狐。”
- Wikisource comparison：`content/processed/shishuo/collation/wikisource-sbck/paidiao.md`（字符/结构参考；当前无句读）

### 26-qingdi-002 ·  · punctuation_complexity

- 自动分类：exact-agreement / exact_reference_agreement, single_reference_only
- transfer_class：`exact_character_transfer`；reference_case：`single_reference_but_exact`
- exact_transfer：`True`
- round-trip：`pass`
- canonical：庾元規語周伯仁諸人皆以君方樂周曰何樂謂樂
毅邪庾曰不爾樂令
耳周曰何乃刻畫無鹽以唐突西子也
- 转移句读：庾元規語周伯仁：“諸人皆以君方樂。”周曰：“何樂？謂樂毅邪？”庾曰：“不爾。樂令耳！”周曰：“何乃刻畫無鹽，以唐突西子也？”
- local TXT reference：庾元规语周伯仁：“诸人皆以君方乐。”周曰：“何乐？谓乐毅邪？”庾曰：“不尔。乐令耳！”周曰：“何乃刻画无盐，以唐突西子也？”
- Wikisource comparison：`content/processed/shishuo/collation/wikisource-sbck/qingdi.md`（字符/结构参考；当前无句读）

### 26-qingdi-028 ·  · short_entry

- 自动分类：exact-agreement / exact_reference_agreement, single_reference_only
- transfer_class：`exact_character_transfer`；reference_case：`single_reference_but_exact`
- exact_transfer：`True`
- round-trip：`pass`
- canonical：舊目韓康伯將肘無風骨
- 转移句读：舊目韓康伯：將肘無風骨。
- local TXT reference：旧目韩康伯：将肘无风骨。
- Wikisource comparison：`content/processed/shishuo/collation/wikisource-sbck/qingdi.md`（字符/结构参考；当前无句读）

### 27-jiajue-006 ·  · punctuation_complexity

- 自动分类：character-disagreement / reference_character_variant, single_reference_only
- transfer_class：`character_mismatch_around_punctuation`；reference_case：`single_reference_character_variant`
- exact_transfer：`False`
- round-trip：`pass`
- canonical：王大將軍既為逆頓軍姑孰晉明帝以英武之才猶
相猜憚乃箸戎服騎巴賨馬齎一金馬鞭隂察軍形
勢未至十餘里有一客姥居店賣食帝過愒之謂姥
曰王敦舉兵圖逆猜害忠良朝廷駭懼社稷是憂故
劬勞晨夕用相覘察恐形迹危露或致狼狽追迫之
日姥其匿之便與客姥馬鞭而去行敦營匝而出軍
士覺曰此非常人也敦卧心動曰此必黄須鮮卑奴
來命騎追之已覺多許里追士因問向姥不見一黄
須人騎馬度此邪姥曰去已久矣不可復及於是騎

人息意而反
- 转移句读：王大將軍既為逆，頓軍姑孰。晉明帝以英武之才，猶相猜憚，乃箸戎服，騎巴賨馬，齎一金馬鞭，隂察軍形勢。未至十餘里，有一客姥居店賣食。帝過愒之，謂姥曰：“王敦舉兵圖逆，猜害忠良，朝廷駭懼，社稷是憂。故劬勞晨夕，用相覘察，恐形迹危露，或致狼狽。追迫之日，姥其匿之。”便與客姥馬鞭而去。行敦營匝而出，軍士覺，曰：“此非常人也！”敦卧心動，曰：“此必黄須鮮卑奴來！”命騎追之，已覺多許里，追士因問向姥：“不見一黄須人騎馬度此邪？”姥曰：“去已久矣，不可復及。”於是騎人息意而反。
- local TXT reference：王大将军既为逆，顿军姑孰。晋明帝以英武之才，犹相猜惮，乃着戎服，骑巴賨马，赍一金马鞭，阴察军形势。未至十余里，有一客姥居店卖食。帝过愒之，谓姥曰：“王敦举兵图逆，猜害忠良，朝廷骇惧，社稷是忧。故劬劳晨夕，用相觇察，恐形迹危露，或致狼狈。追迫之日，姥其匿之。”便与客姥马鞭而去。行敦营匝而出，军士觉，曰：“此非常人也！”敦卧心动，曰：“此必黄须鲜卑奴来！”命骑追之，已觉多许里，追士因问向姥：“不见一黄须人骑马度此邪？”姥曰：“去已久矣，不可复及。”于是骑人息意而反。
- Wikisource comparison：`content/processed/shishuo/collation/wikisource-sbck/jiajue.md`（字符/结构参考；当前无句读）

### 27-jiajue-014 ·  · short_entry

- 自动分类：character-disagreement / reference_character_variant, single_reference_only
- transfer_class：`character_mismatch_around_punctuation`；reference_case：`single_reference_character_variant`
- exact_transfer：`False`
- round-trip：`pass`
- canonical：謝遏年少時好箸紫羅香囊垂覆手太傅患之而不
欲傷其意乃譎與賭得即燒之
- 转移句读：謝遏年少時，好箸紫羅香囊，垂覆手。太傅患之，而不欲傷其意，乃譎與賭，得即燒之。
- local TXT reference：谢遏年少时，好着紫罗香囊，垂覆手。太傅患之，而不欲伤其意，乃谲与赌，得即烧之。
- Wikisource comparison：`content/processed/shishuo/collation/wikisource-sbck/jiajue.md`（字符/结构参考；当前无句读）

### 28-chumian-006 ·  · short_entry

- 自动分类：exact-agreement / exact_reference_agreement, single_reference_only
- transfer_class：`exact_character_transfer`；reference_case：`single_reference_but_exact`
- exact_transfer：`True`
- round-trip：`pass`
- canonical：鄧竟陵免官後赴山陵過見大司馬桓公公問之曰
卿何以更瘦

鄧曰有愧於叔達不能不恨於破甑
- 转移句读：鄧竟陵免官後赴山陵，過見大司馬桓公。公問之曰：“卿何以更瘦？”鄧曰：“有愧於叔達，不能不恨於破甑！”
- local TXT reference：邓竟陵免官后赴山陵，过见大司马桓公。公问之曰：“卿何以更瘦？”邓曰：“有愧于叔达，不能不恨于破甑！”
- Wikisource comparison：`content/processed/shishuo/collation/wikisource-sbck/chumian.md`（字符/结构参考；当前无句读）

### 28-chumian-009 ·  · punctuation_complexity

- 自动分类：exact-agreement / exact_reference_agreement, single_reference_only
- transfer_class：`exact_character_transfer`；reference_case：`single_reference_but_exact`
- exact_transfer：`True`
- round-trip：`pass`
- canonical：殷仲文既素有名望自謂必當阿衡朝政忽作東陽
太守意甚不平
及之郡至富陽慨然嘆曰看此山川形勢
當復出一孫伯符
- 转移句读：殷仲文既素有名望，自謂必當阿衡朝政。忽作東陽太守，意甚不平。及之郡，至富陽，慨然嘆曰：“看此山川形勢，當復出一孫伯符！”
- local TXT reference：殷仲文既素有名望，自谓必当阿衡朝政。忽作东阳太守，意甚不平。及之郡，至富阳，慨然叹曰：“看此山川形势，当复出一孙伯符！”
- Wikisource comparison：`content/processed/shishuo/collation/wikisource-sbck/chumian.md`（字符/结构参考；当前无句读）

### 29-jianshe-001 ·  · punctuation_complexity

- 自动分类：exact-agreement / exact_reference_agreement, single_reference_only
- transfer_class：`exact_character_transfer`；reference_case：`single_reference_but_exact`
- exact_transfer：`True`
- round-trip：`pass`
- canonical：和嶠性至儉家有好李王武子求之與不過數十王
武子因其上直率將少年能食之者持斧詣園飽共
噉畢伐之送一車枝與和公問曰何如君李和既得
唯笑而已
- 转移句读：和嶠性至儉，家有好李，王武子求之，與不過數十。王武子因其上直，率將少年能食之者，持斧詣園，飽共噉畢，伐之，送一車枝與和公。問曰：“何如君李？”和既得，唯笑而已。
- local TXT reference：和峤性至俭，家有好李，王武子求之，与不过数十。王武子因其上直，率将少年能食之者，持斧诣园，饱共噉毕，伐之，送一车枝与和公。问曰：“何如君李？”和既得，唯笑而已。
- Wikisource comparison：`content/processed/shishuo/collation/wikisource-sbck/jianshe.md`（字符/结构参考；当前无句读）

### 29-jianshe-008 ·  · short_entry

- 自动分类：exact-agreement / exact_reference_agreement, single_reference_only
- transfer_class：`exact_character_transfer`；reference_case：`single_reference_but_exact`
- exact_transfer：`True`
- round-trip：`pass`
- canonical：蘇峻之亂庾太尉南奔見陶公陶公雅相賞重陶性

儉吝及食噉薤庾因留白陶問用此何為庾云故可
種於是大嘆庾非唯風流兼有治實
- 转移句读：蘇峻之亂，庾太尉南奔見陶公，陶公雅相賞重。陶性儉吝，及食，噉薤，庾因留白。陶問：“用此何為？”庾云：“故可種。”於是大嘆庾非唯風流，兼有治實。
- local TXT reference：苏峻之乱，庾太尉南奔见陶公，陶公雅相赏重。陶性俭吝，及食，噉薤，庾因留白。陶问：“用此何为？”庾云：“故可种。”于是大叹庾非唯风流，兼有治实。
- Wikisource comparison：`content/processed/shishuo/collation/wikisource-sbck/jianshe.md`（字符/结构参考；当前无句读）

### 30-taichi-011 ·  · punctuation_complexity

- 自动分类：exact-agreement / exact_reference_agreement, single_reference_only
- transfer_class：`exact_character_transfer`；reference_case：`single_reference_but_exact`
- exact_transfer：`True`
- round-trip：`pass`
- canonical：彭城王有快牛至愛惜之
王太尉與射賭得之彭城王曰君欲自乘則不
論若欲噉者當以二十肥者代之既不廢噉又存所
愛王遂殺噉
- 转移句读：彭城王有快牛，至愛惜之。王太尉與射，賭得之。彭城王曰：“君欲自乘則不論，若欲噉者，當以二十肥者代之。既不廢噉，又存所愛。”王遂殺噉。
- local TXT reference：彭城王有快牛，至爱惜之。王太尉与射，赌得之。彭城王曰：“君欲自乘则不论，若欲噉者，当以二十肥者代之。既不废噉，又存所爱。”王遂杀噉。
- Wikisource comparison：`content/processed/shishuo/collation/wikisource-sbck/taichi.md`（字符/结构参考；当前无句读）

### 30-taichi-012 ·  · short_entry

- 自动分类：exact-agreement / exact_reference_agreement, single_reference_only
- transfer_class：`exact_character_transfer`；reference_case：`single_reference_but_exact`
- exact_transfer：`True`
- round-trip：`pass`
- canonical：王右軍少時在周侯末坐割牛心噉之於此改觀
- 转移句读：王右軍少時，在周侯末坐，割牛心噉之。於此改觀。
- local TXT reference：王右军少时，在周侯末坐，割牛心噉之。于此改观。
- Wikisource comparison：`content/processed/shishuo/collation/wikisource-sbck/taichi.md`（字符/结构参考；当前无句读）

### 31-fenjuan-002 ·  · punctuation_complexity

- 自动分类：exact-agreement / exact_reference_agreement, single_reference_only
- transfer_class：`exact_character_transfer`；reference_case：`single_reference_but_exact`
- exact_transfer：`True`
- round-trip：`pass`
- canonical：王藍田性急嘗食雞子以筯刺之不得便大怒舉以
擲地雞子於地圓轉未止仍下地以屐齒蹍之又不
得瞋甚復於地取内口中齧破即吐之王右軍聞而
大笑曰使安期有此性猶當無一豪可論況藍田邪
- 转移句读：王藍田性急。嘗食雞子，以筯刺之，不得，便大怒，舉以擲地。雞子於地圓轉未止，仍下地以屐齒蹍之，又不得，瞋甚，復於地取内口中，齧破即吐之。王右軍聞而大笑曰：“使安期有此性，猶當無一豪可論，況藍田邪？”
- local TXT reference：王蓝田性急。尝食鸡子，以筯刺之，不得，便大怒，举以掷地。鸡子于地圆转未止，仍下地以屐齿蹍之，又不得，瞋甚，复于地取内口中，啮破即吐之。王右军闻而大笑曰：“使安期有此性，犹当无一豪可论，况蓝田邪？”
- Wikisource comparison：`content/processed/shishuo/collation/wikisource-sbck/fenjuan.md`（字符/结构参考；当前无句读）

### 31-fenjuan-004 ·  · short_entry

- 自动分类：exact-agreement / exact_reference_agreement, single_reference_only
- transfer_class：`exact_character_transfer`；reference_case：`single_reference_but_exact`
- exact_transfer：`True`
- round-trip：`pass`
- canonical：桓宣武與袁彦道樗蒱袁彦道齒不合遂厲色擲去
五木温太真云見袁生遷怒知顔子為貴
- 转移句读：桓宣武與袁彦道樗蒱，袁彦道齒不合，遂厲色擲去五木。温太真云：“見袁生遷怒，知顔子為貴。”
- local TXT reference：桓宣武与袁彦道樗蒱，袁彦道齿不合，遂厉色掷去五木。温太真云：“见袁生迁怒，知颜子为贵。”
- Wikisource comparison：`content/processed/shishuo/collation/wikisource-sbck/fenjuan.md`（字符/结构参考；当前无句读）

### 32-chanxian-001 ·  · short_entry

- 自动分类：exact-agreement / exact_reference_agreement, single_reference_only
- transfer_class：`exact_character_transfer`；reference_case：`single_reference_but_exact`
- exact_transfer：`True`
- round-trip：`pass`
- canonical：王平子形甚散朗内實勁俠
- 转移句读：王平子形甚散朗，内實勁俠。
- local TXT reference：王平子形甚散朗，内实劲侠。
- Wikisource comparison：`content/processed/shishuo/collation/wikisource-sbck/chanxian.md`（字符/结构参考；当前无句读）

### 33-youhui-001 ·  · punctuation_complexity

- 自动分类：exact-agreement / exact_reference_agreement, single_reference_only
- transfer_class：`exact_character_transfer`；reference_case：`single_reference_but_exact`
- exact_transfer：`True`
- round-trip：`pass`
- canonical：魏文帝忌弟任城王驍壯因在卞太后閤共圍棊並
噉棗文帝以毒置諸棗蔕中自選可食者而進王弗

悟遂雜進之既中毒太后索水救之帝預敕左右毁
缾罐太后徒跣趨井無以汲須臾遂卒

復欲
害東阿太后曰汝已殺我任城不得復殺我東阿
- 转移句读：魏文帝忌弟任城王驍壯，因在卞太后閤共圍棊，並噉棗，文帝以毒置諸棗蔕中，自選可食者而進。王弗悟，遂雜進之。既中毒，太后索水救之。帝預敕左右毁缾罐，太后徒跣趨井，無以汲。須臾，遂卒。復欲害東阿，太后曰：“汝已殺我任城，不得復殺我東阿。”
- local TXT reference：魏文帝忌弟任城王骁壮，因在卞太后合共围棋，并噉枣，文帝以毒置诸枣蔕中，自选可食者而进。王弗悟，遂杂进之。既中毒，太后索水救之。帝预敕左右毁缾罐，太后徒跣趋井，无以汲。须臾，遂卒。复欲害东阿，太后曰：“汝已杀我任城，不得复杀我东阿。”
- Wikisource comparison：`content/processed/shishuo/collation/wikisource-sbck/youhui.md`（字符/结构参考；当前无句读）

### 33-youhui-005 ·  · short_entry

- 自动分类：exact-agreement / exact_reference_agreement, single_reference_only
- transfer_class：`exact_character_transfer`；reference_case：`single_reference_but_exact`
- exact_transfer：`True`
- round-trip：`pass`
- canonical：王平子始下丞相語大將軍不可復使羌人東行平
子面似羌
- 转移句读：王平子始下，丞相語大將軍：“不可復使羌人東行。”平子面似羌。
- local TXT reference：王平子始下，丞相语大将军：“不可复使羌人东行。”平子面似羌。
- Wikisource comparison：`content/processed/shishuo/collation/wikisource-sbck/youhui.md`（字符/结构参考；当前无句读）

### 34-pilou-003 ·  · short_entry

- 自动分类：exact-agreement / exact_reference_agreement, single_reference_only
- transfer_class：`exact_character_transfer`；reference_case：`single_reference_but_exact`
- exact_transfer：`True`
- round-trip：`pass`
- canonical：蔡司徒渡江見彭蜞大喜曰蟹有八足加以二螯令
烹之既食吐下委頓方知非蟹後向謝仁祖說此事
謝曰卿讀爾雅不熟幾為勸學死
- 转移句读：蔡司徒渡江，見彭蜞，大喜曰：“蟹有八足，加以二螯。”令烹之。既食，吐下委頓，方知非蟹。後向謝仁祖說此事，謝曰：“卿讀《爾雅》不熟，幾為《勸學》死。”
- local TXT reference：蔡司徒渡江，见彭蜞，大喜曰：“蟹有八足，加以二螯。”令烹之。既食，吐下委顿，方知非蟹。后向谢仁祖说此事，谢曰：“卿读《尔雅》不熟，几为《劝学》死。”
- Wikisource comparison：`content/processed/shishuo/collation/wikisource-sbck/pilou.md`（字符/结构参考；当前无句读）

### 35-huoni-002 ·  · punctuation_complexity

- 自动分类：exact-agreement / exact_reference_agreement, single_reference_only
- transfer_class：`exact_character_transfer`；reference_case：`single_reference_but_exact`
- exact_transfer：`True`
- round-trip：`pass`
- canonical：荀奉倩與婦至篤冬月婦病熱乃出中庭自取冷還

以身熨之婦亡奉倩後少時亦卒以是獲譏於世




奉倩曰婦人德不
足稱當以色為主裴令聞之曰此乃是興到之事非
盛德言冀後人未昧此語
- 转移句读：荀奉倩與婦至篤，冬月婦病熱，乃出中庭自取冷，還以身熨之。婦亡，奉倩後少時亦卒，以是獲譏於世。奉倩曰：“婦人德不足稱，當以色為主。”裴令聞之曰：“此乃是興到之事，非盛德言，冀後人未昧此語。”
- local TXT reference：荀奉倩与妇至笃，冬月妇病热，乃出中庭自取冷，还以身熨之。妇亡，奉倩后少时亦卒，以是获讥于世。奉倩曰：“妇人德不足称，当以色为主。”裴令闻之曰：“此乃是兴到之事，非盛德言，冀后人未昧此语。”
- Wikisource comparison：`content/processed/shishuo/collation/wikisource-sbck/huoni.md`（字符/结构参考；当前无句读）

### 35-huoni-007 ·  · short_entry

- 自动分类：exact-agreement / exact_reference_agreement, single_reference_only
- transfer_class：`exact_character_transfer`；reference_case：`single_reference_but_exact`
- exact_transfer：`True`
- round-trip：`pass`
- canonical：王丞相有幸妾姓雷頗預政事納貨蔡公謂之雷尚
書
- 转移句读：王丞相有幸妾姓雷，頗預政事，納貨。蔡公謂之“雷尚書”。
- local TXT reference：王丞相有幸妾姓雷，颇预政事，纳货。蔡公谓之“雷尚书”。
- Wikisource comparison：`content/processed/shishuo/collation/wikisource-sbck/huoni.md`（字符/结构参考；当前无句读）

### 36-chouxi-007 ·  · short_entry

- 自动分类：exact-agreement / exact_reference_agreement, single_reference_only
- transfer_class：`exact_character_transfer`；reference_case：`single_reference_but_exact`
- exact_transfer：`True`
- round-trip：`pass`
- canonical：王孝伯死縣其首於大桁司馬太傅命駕出至標所
孰視首曰卿何故趣欲殺我邪
- 转移句读：王孝伯死，縣其首於大桁。司馬太傅命駕出至標所，孰視首，曰：“卿何故趣欲殺我邪？”
- local TXT reference：王孝伯死，县其首于大桁。司马太傅命驾出至标所，孰视首，曰：“卿何故趣欲杀我邪？”
- Wikisource comparison：`content/processed/shishuo/collation/wikisource-sbck/chouxi.md`（字符/结构参考；当前无句读）
