# Person ↔ Story pilot

This is deterministic navigation/index data for the unified materialized Shishuo Person registry. The six-person pilot is the historical bootstrap stage; this index is not a personality interpretation, participation claim, or new historical assertion.

## Semantics

- Links are derived from resolved Shishuo mentions, plus the existing explicit evidence link for supporting Person `person-007` 郗璿.
- `main_text` and `liu_annotation` are source layers. Current links use `presence_kind: mentioned`; no `participant` status is inferred from appearance alone.
- A high-confidence exact-name/courtesy-name or otherwise deterministic resolved mention produces a reviewed link. Medium contextual forms remain candidate mention evidence attached to that link and never establish review by themselves.
- The PersonStoryIndex contains reviewed links only. Candidate links remain in the link artifact and are listed for human review; contextual candidate Mentions attached to a reviewed link remain candidate evidence rather than a second semantic link.
- `reader_ready` requires a canonical entry, reviewed punctuation, both original/simplified reading forms, and at least one reviewed resolved Person link. Unresolved contextual titles may remain in the source, as they do in the current reader.

## Summary

- primary people: 74
- supporting people: 1
- reviewed PersonStoryLinks: 870
- candidate PersonStoryLinks: 5
- candidate contextual mentions retained: 28
- reader-ready linked Stories: 1

## Person review lists

No Story is listed as directly participating unless a future reviewed presence explicitly uses `participant`; this pilot currently has none.

### 王羲之 (`person-001`)

- directly participating Stories: none currently classified; main-text appearance is retained as `mentioned` pending explicit participation review.
- reviewed linked Stories: 13; reader-ready: 1; candidate links: 0; candidate contextual Mentions: 3
- main-text presence:
  - `02-yanyu-069` · 言語第二 · reviewed · reader_ready=false · surface: 王逸少
    ```text
劉真長為丹陽尹許玄度出都就劉宿
牀帷新麗
飲食豐甘許曰若保全此處殊勝東山劉曰卿若知
吉凶由人吾安得不保此王逸少在
坐曰令巢許遇稷契當無此言二人並有愧色

    ```
  - `04-wenxue-036` · 文學第四 · reviewed · reader_ready=false · surface: 王逸少
    ```text
王逸少作㑹稽初至支道林在焉孫興公謂王曰支
道林㧞新領異胷懷所及乃自佳卿欲見不王本自
有一徃雋氣殊自輕之後孫與支共載徃王許王都
領域不與交言須臾支退後正值王當行車已在門
支語王曰君未可去貧
    ```
  - `06-yaliang-019` · 雅量第六 · reviewed · reader_ready=true · surface: 逸少
    ```text
郗太傅在京口遣門生與王丞相書求女壻丞相語
郗信君往東廂任意選之門生歸白郗曰王家諸郎
亦皆可嘉聞來覓壻咸自矜持唯有一郎在東牀上
坦腹卧如不聞郗公云正此好訪之乃是逸少因嫁
女與焉

    ```
  - `08-shangyu-072` · 賞譽第八 · reviewed · reader_ready=false · surface: 逸少
    ```text
庾公云逸少國舉故庾倪爲碑文云抜萃國舉



    ```
  - `08-shangyu-080` · 賞譽第八 · reviewed · reader_ready=false · surface: 逸少
    ```text
殷中軍道王右軍云逸少清貴人吾於之甚至一時
無所後

    ```
  - `09-pinzao-028` · 品藻第九 · reviewed · reader_ready=false · surface: 逸少
    ```text
王右軍少時丞相云逸少何縁復減萬安邪

    ```
  - `14-rongzhi-024` · 容止第十四 · reviewed · reader_ready=false · surface: 王逸少
    ```text
秋夜氣佳景清使吏殷浩王胡之之
徒登南樓理詠音調始遒聞函道中有屐聲甚厲定
是庾公俄而率左右十許人步來諸賢欲起避之公
徐云諸君少住老子於此處興復不淺因便據胡牀
與諸人詠謔竟坐甚得任樂後王逸少下與丞相言
及此事丞相曰元規爾時風範不得不小穨右軍荅

曰唯丘壑獨存


    ```
  - `19-xianyuan-026` · 賢媛第十九 · reviewed · reader_ready=false · surface: 逸少
    ```text
王凝之謝夫人既徃王氏太薄凝之既還謝家意大
不說太傅慰釋之曰王郎逸少之子人身亦不惡汝
何以恨廼爾荅曰一門叔父則有阿大中郞羣從兄
弟則有封胡遏末

不意天壤之中乃有王郎

    ```
- Liu-annotation-only presence:
  - `02-yanyu-062` · 言語第二 · reviewed · reader_ready=false · surface: 王羲之、逸少
    ```text
(父曠淮南太守羲之少朗拔為叔父廙/文字志曰王羲之字逸少琅邪臨沂人)
    ```
  - `06-yaliang-028` · 雅量第六 · reviewed · reader_ready=false · surface: 王羲之
    ```text
(漁弋山水入則談説屬文未嘗有處世意也/居會稽與支道林王羲之許詢共游處出則)
    ```
  - `09-pinzao-087` · 品藻第九 · reviewed · reader_ready=false · surface: 王羲之
    ```text
(瑾有才力歷尚書太常卿/父畼畼娶王羲之女生瑾)
    ```
  - `16-qixian-003` · 企羡第十六 · reviewed · reader_ready=false · surface: 王羲之
    ```text
(莫春之初㑹于㑹稽山隂之蘭亭脩禊/王羲之臨河叙曰永和九年嵗在癸丑)
    ```
  - `36-chouxi-005` · 仇隟第三十六 · reviewed · reader_ready=false · surface: 王羲之
    ```text
(能述為㑹稽艱居郡境王羲之後為郡申/中興書曰羲之與述志尚不同而兩不相)
    ```

### 郗鑒 (`person-002`)

- directly participating Stories: none currently classified; main-text appearance is retained as `mentioned` pending explicit participation review.
- reviewed linked Stories: 6; reader-ready: 1; candidate links: 0; candidate contextual Mentions: 1
- main-text presence:
  - `09-pinzao-014` · 品藻第九 · reviewed · reader_ready=false · surface: 郗鑒
    ```text
明帝問周伯仁卿自謂何如郗鑒周曰鑒方臣如有
功夫復問郗郗曰周顗比臣有國士門風



    ```
  - `09-pinzao-019` · 品藻第九 · reviewed · reader_ready=false · surface: 郗鑒
    ```text
明帝問周侯論者以卿比郗鑒云何周曰陛下不須
牽顗比

    ```
- Liu-annotation-only presence:
  - `01-dexing-024` · 德行第一 · reviewed · reader_ready=false · surface: 道徽、郗鑒
    ```text
(人漢御史大夫郗慮後也少有體/郗鑒别傳曰鑒字道徽髙平金鄉)
    ```
  - `01-dexing-030` · 德行第一 · reviewed · reader_ready=false · surface: 道徽
    ```text
(嘉亂投迹楊土居止京邑内持法綱外允具瞻弘道/之胤也道徽髙扇譽播山東為中州劉公弟子值永)
    ```
  - `06-yaliang-019` · 雅量第六 · reviewed · reader_ready=true · surface: 郗鑒
    ```text
(妻太傅郗鑒女名璿字子房/王氏譜曰逸少羲之小字羲之)
    ```
  - `10-guizhen-017` · 規箴第十 · reviewed · reader_ready=false · surface: 郄鑒
    ```text
(殂朝野憂懼以玩德望乃拜司空玩辭/玩别傳曰是時王導郄鑒庾亮相繼薨)
    ```

### 王導 (`person-003`)

- directly participating Stories: none currently classified; main-text appearance is retained as `mentioned` pending explicit participation review.
- reviewed linked Stories: 25; reader-ready: 0; candidate links: 0; candidate contextual Mentions: 7
- main-text presence:
  - `05-fangzheng-023` · 方正第五 · reviewed · reader_ready=false · surface: 王導、茂弘
    ```text
出詔付刁周王既入始至階
頭帝逆遣傳詔遏使就東廂周侯未悟即卻略下階
丞相披撥傳詔徑至御牀前曰不審陛下何以見臣

帝黙然無言乃探懐中黄𥿄詔裂擲之由此皇儲始
定周侯方慨然愧歎曰我常自言勝茂弘今始知不
如也




    ```
  - `08-shangyu-046` · 賞譽第八 · reviewed · reader_ready=false · surface: 茂弘
    ```text
王大將軍與元皇表云舒風槩簡正允作雅人自多
於邃
最是臣少所知拔中間夷甫澄見語卿知
處明茂弘茂弘巳有令名眞副卿清論處明親踈無

知之者吾常以卿言爲意殊未有得恐巳悔之臣慨
然曰君以此試頃來始乃有稱之者言常人正自患
知之使過不知使負實

    ```
  - `09-pinzao-006` · 品藻第九 · reviewed · reader_ready=false · surface: 王導
    ```text
正始中人士比論以五荀方五陳荀淑方陳寔荀靖
方陳諶

荀爽方陳紀荀彧方陳群


荀顗方陳泰

又以八裴方八王裴徽方王祥裴楷
方王夷甫裴康方王綏
裴綽方王澄裴
瓉方王敦裴遐方王導裴
頠方王戎裴邈方王玄

    ```
  - `10-guizhen-011` · 規箴第十 · reviewed · reader_ready=false · surface: 王導、王茂弘
    ```text
元帝過江猶好酒王茂弘與帝有舊常流涕諌帝許
之命酌酒一酣從是遂斷


    ```
  - `11-jiewu-005` · 捷悟第十一 · reviewed · reader_ready=false · surface: 王導
    ```text
王敦引軍垂至大桁明帝自出中堂温嶠為丹陽尹
帝令斷大桁故未斷帝大怒瞋目左右莫不悚懼

召諸公來嶠至不謝但求酒炙王導須

吏至徒跣下地謝曰天威在顔遂使温嶠不容得謝
嶠於是下謝帝廼釋然諸公共嘆王機悟名言

    ```
  - `18-qiyi-004` · 棲逸第十八 · reviewed · reader_ready=false · surface: 茂弘
    ```text
李廞是茂曽弟五子清貞有逺操而少羸病不肯婚
宦居在臨海住兄侍中墓下既有髙名王丞相欲招
禮之故辟為府掾廞得牋命笑曰茂弘乃復以一爵
假人




    ```
  - `33-youhui-007` · 尤悔第三十三 · reviewed · reader_ready=false · surface: 王導
    ```text
王導温嶠俱見明帝帝問温前世所以得天下之由
温未荅頃王曰温嶠年少未諳臣爲陛下陳之王廼
具叙宣王創業之始誅夷名族寵樹同已及文王之

末高貴鄉公事明帝
聞之覆面箸牀曰若如公言胙安得長

    ```
- Liu-annotation-only presence:
  - `01-dexing-027` · 德行第一 · reviewed · reader_ready=false · surface: 王導、茂弘
    ```text
(行稱父裁侍御史導少知名家世貧約恬畼/丞相别傳曰王導字茂弘琅邪人祖覽以德)
    ```
  - `02-yanyu-037` · 言語第二 · reviewed · reader_ready=false · surface: 王導
    ```text
(巳舉兵討之故含南奔武昌朝廷始警備也/王導恊贊中興敦有方面之功敦以劉隗為間)
    ```
  - `02-yanyu-070` · 言語第二 · reviewed · reader_ready=false · surface: 茂弘
    ```text
(治也/茂弘所)
    ```
  - `02-yanyu-102` · 言語第二 · reviewed · reader_ready=false · surface: 王導
    ```text
(不宜遷都建業徃之秣陵古者既有帝王所治之表/即豐全朝士及三吳豪傑謂可遷都㑹稽王導獨謂)
    ```
  - `03-zhengshi-012` · 政事第三 · reviewed · reader_ready=false · surface: 王導
    ```text
(常賔一見多輸寫欵誠自謂為導所遇同之/晉陽秋曰王導接誘應㑹少有牾者雖疎交)
    ```
  - `04-wenxue-022` · 文學第四 · reviewed · reader_ready=false · surface: 王導
    ```text
(爲王導所辟/王濛王述並)
    ```
  - `06-yaliang-029` · 雅量第六 · reviewed · reader_ready=false · surface: 王導
    ```text
(大怒以爲黜其權謝安王坦之所建也入赴山陵百/帝紀曰簡文晏駕遺詔桓温依諸葛亮王導故事温)
    ```
  - `07-shijian-024` · 識鑒第七 · reviewed · reader_ready=false · surface: 茂弘
    ```text
(河南人太傅裒之孫秘書監韶之子太傅/期生禇爽小字也續晉陽秋曰爽字茂弘)
    ```
  - `08-shangyu-054` · 賞譽第八 · reviewed · reader_ready=false · surface: 王導、王茂弘
    ```text
(教罪莫斯甚中朝傾覆實由於此欲奏治之王導庾/者慕王平子謝幼輿等為達壼厲色於朝曰悖禮傷)
    ```
  - `09-pinzao-047` · 品藻第九 · reviewed · reader_ready=false · surface: 王導
    ```text
(爾述荅曰足自當止時人未之達也後屢臨州郡無/丞相王導使人謂之曰名父之子屈臨小縣甚不宜)
    ```
  - `10-guizhen-017` · 規箴第十 · reviewed · reader_ready=false · surface: 王導
    ```text
(殂朝野憂懼以玩德望乃拜司空玩辭/玩别傳曰是時王導郄鑒庾亮相繼薨)
    ```
  - `14-rongzhi-023` · 容止第十四 · reviewed · reader_ready=false · surface: 王導
    ```text
(臣官陶侃祖約不在其例侃約疑亮寢遺詔也中/徐廣晉紀曰肅祖遺詔庾亮王導輔㓜主而進大)
    ```
  - `22-chongli-001` · 寵禮第二十二 · reviewed · reader_ready=false · surface: 王導
    ```text
(王導升御坐固辭然後止/元帝登尊號百官陪位詔)
    ```
  - `23-rendan-025` · 任誕第二十三 · reviewed · reader_ready=false · surface: 王導
    ```text
(曰王導與/鄧粲晉紀)
    ```
  - `23-rendan-032` · 任誕第二十三 · reviewed · reader_ready=false · surface: 王導
    ```text
(辟名士時賢恊贊中興/王濛别傳曰丞相王導)
    ```
  - `26-qingdi-004` · 輕詆第二十六 · reviewed · reader_ready=false · surface: 王導
    ```text
(乎王隱晉書戴洋傳曰丹陽太守王導問洋得病七/下公以識度裁之囂言自息豈或回貳有扇塵之事)
    ```
  - `27-jiajue-008` · 假譎第二十七 · reviewed · reader_ready=false · surface: 王導
    ```text
(不欲亮曰蘇峻豺狼終為禍亂晁錯所謂削亦反不/海而峻擁兵近甸為逋逃藪亮圖召峻王導卞壷並)
    ```
  - `36-chouxi-003` · 仇隟第三十六 · reviewed · reader_ready=false · surface: 王導
    ```text
(曰廙字世將祖覽父正廙髙朗豪率王導/司馬氏譜曰丞娶南陽趙氏女王廙别傳)
    ```

### 王凝之 (`person-004`)

- directly participating Stories: none currently classified; main-text appearance is retained as `mentioned` pending explicit participation review.
- reviewed linked Stories: 3; reader-ready: 0; candidate links: 0; candidate contextual Mentions: 0
- main-text presence:
  - `02-yanyu-071` · 言語第二 · reviewed · reader_ready=false · surface: 叔平、王凝之
    ```text
謝太傅寒雪日内集與兒女講論文義俄而雪驟
公欣然曰白雪紛紛何所似兄子胡兒曰
撒鹽空
中差可擬兄女曰未若栁絮因風起公大笑樂即公

大兄無奕女左將軍王凝之妻也




    ```
  - `19-xianyuan-026` · 賢媛第十九 · reviewed · reader_ready=false · surface: 王凝之
    ```text
王凝之謝夫人既徃王氏太薄凝之既還謝家意大
不說太傅慰釋之曰王郎逸少之子人身亦不惡汝
何以恨廼爾荅曰一門叔父則有阿大中郞羣從兄
弟則有封胡遏末

不意天壤之中乃有王郎

    ```
- Liu-annotation-only presence:
  - `25-paidiao-026` · 排調第二十五 · reviewed · reader_ready=false · surface: 王凝之
    ```text
(問王凝之妻謝氏曰太傅/髙靈已見婦人集載桓玄)
    ```

### 謝道韞 (`person-005`)

- directly participating Stories: none currently classified; main-text appearance is retained as `mentioned` pending explicit participation review.
- reviewed linked Stories: 1; reader-ready: 0; candidate links: 0; candidate contextual Mentions: 0
- main-text presence:
  - none
- Liu-annotation-only presence:
  - `25-paidiao-026` · 排調第二十五 · reviewed · reader_ready=false · surface: 王凝之妻謝氏
    ```text
(問王凝之妻謝氏曰太傅/髙靈已見婦人集載桓玄)
    ```

### 謝安 (`person-006`)

- directly participating Stories: none currently classified; main-text appearance is retained as `mentioned` pending explicit participation review.
- reviewed linked Stories: 37; reader-ready: 0; candidate links: 0; candidate contextual Mentions: 11
- main-text presence:
  - `02-yanyu-083` · 言語第二 · reviewed · reader_ready=false · surface: 謝安
    ```text
袁彦伯為謝安南司馬都下諸人送至瀨鄉
將别既自悽惘歎曰江山遼落居然有萬里之勢






    ```
  - `04-wenxue-024` · 文學第四 · reviewed · reader_ready=false · surface: 謝安
    ```text
謝安年少時請阮光禄道白馬論
為論以示謝于時
謝不即解阮語重相咨盡阮乃歎曰非但能言人不

可得正索解人亦不可得

    ```
  - `04-wenxue-087` · 文學第四 · reviewed · reader_ready=false · surface: 安石、謝安石
    ```text
桓公見謝安石作簡文諡議㸔竟擲於坐上諸客曰
此是安石碎金



    ```
  - `05-fangzheng-053` · 方正第五 · reviewed · reader_ready=false · surface: 安石
    ```text
阮光禄赴山陵至都不往殷劉許過事便還諸
人相與追之既亦知時流必當逐巳乃遄疾而去至

方山不相及劉尹時爲㑹稽
乃嘆曰我入當泊安石渚下耳不敢復近思曠傍伊
便能捉杖打人不易

    ```
  - `05-fangzheng-055` · 方正第五 · reviewed · reader_ready=false · surface: 謝安石
    ```text
桓公問桓子野謝安石料萬石必敗何以不諫

子野荅曰故當出於難犯耳桓作
色曰萬石撓弱凡才有何嚴顔難犯


    ```
  - `06-yaliang-027` · 雅量第六 · reviewed · reader_ready=false · surface: 謝安
    ```text
桓宣武與郗超議芟夷朝臣條牒既定其夜同宿
明晨起
呼謝安王坦之入擲䟽示之郗猶在帳内謝都無言
王直擲還云多宣武取筆欲除郗不覺竊從帳中與
宣武言謝含笑曰郗生可謂入幕賔也

    ```
  - `06-yaliang-029` · 雅量第六 · reviewed · reader_ready=false · surface: 謝安
    ```text
桓公伏甲設饌廣延朝士因此欲誅謝安王坦之

王甚遽問謝曰當作何
計謝神意不變謂文度曰晉阼存亡在此一行相與
俱前王之恐狀轉見於色謝之寛容愈表於貌望階
趨席方作洛生詠諷浩浩洪流桓憚其曠逺乃趣解
兵



王謝舊齊名於此
    ```
  - `06-yaliang-033` · 雅量第六 · reviewed · reader_ready=false · surface: 謝安
    ```text
謝安南免吏部尚書還東
謝太傅赴桓公司
馬出西相遇破岡既當逺别遂停三日共語太傅欲

慰其失官安南輒引以它端雖信宿中塗竟不言及
此事太傅深恨在心未盡謂同舟曰謝奉故是竒士

    ```
  - `07-shijian-021` · 識鑒第七 · reviewed · reader_ready=false · surface: 安石
    ```text
謝公在東山畜妓簡文曰安石必出既與人同樂亦
不得不與人同憂

    ```
  - `08-shangyu-077` · 賞譽第八 · reviewed · reader_ready=false · surface: 安石
    ```text
王右軍語劉尹故當共推安石劉尹曰若安石東山
志立當與天下共推之


    ```
  - `08-shangyu-102` · 賞譽第八 · reviewed · reader_ready=false · surface: 安石
    ```text
謝公作宣武司馬屬門生數十人於田曹中郎趙恱
子恱子以告宣武宣武
宣武云且爲用半趙俄而悉用之曰昔安石在東山
搢紳敦逼恐不豫人事況今自鄉選反違之邪

    ```
  - `09-pinzao-040` · 品藻第九 · reviewed · reader_ready=false · surface: 謝安
    ```text
簡文云謝安南清令不如其弟
學義不及孔巖
居然自勝


    ```
  - `09-pinzao-045` · 品藻第九 · reviewed · reader_ready=false · surface: 安石
    ```text
桓公問孔西陽安石何如仲文孔思未對反

問公曰何如荅曰安石居然不可陵踐其處故乃勝
也

    ```
  - `09-pinzao-052` · 品藻第九 · reviewed · reader_ready=false · surface: 謝安石
    ```text
有人問謝安石王坦之優劣於桓公桓公停欲言中
悔曰卿喜傳人語不能復語卿


    ```
  - `09-pinzao-055` · 品藻第九 · reviewed · reader_ready=false · surface: 安石
    ```text
王右軍問許玄度卿自言何如安石許未荅王因曰
安石故相爲雄阿萬當裂眼争邪


    ```
  - `23-rendan-038` · 任誕第二十三 · reviewed · reader_ready=false · surface: 謝安
    ```text
桓車騎在荆州張玄為侍中使至江陵路經陽歧村
俄見一人持半小籠生魚徑來造船云
有魚欲寄作膾張乃維舟而納之問其姓字稱是劉
遺民張素聞其名大相忻待劉既
知張銜命問謝安王文度並佳不張甚欲話言劉了

無停意既進膾便去云向得此魚觀君船上當有膾
具是故來耳於是便去張乃追至劉家為設酒殊不
清㫖張高其人不得已而飲之方共封飲劉便先起
云今正伐荻不宐久廢張亦無
    ```
  - `23-rendan-040` · 任誕第二十三 · reviewed · reader_ready=false · surface: 安石、謝安
    ```text
謝安始出西戯失車半便杖䇿步歸道逢劉尹語曰

安石將無傷謝乃同載而歸

    ```
  - `25-paidiao-026` · 排調第二十五 · reviewed · reader_ready=false · surface: 安石
    ```text
謝公在東山朝命屢降而不動後出為桓宣武司馬
將發新亭朝士咸出瞻送髙靈時為中丞亦徃相祖
先時多少飲酒因倚如醉戲曰卿屢違朝㫖髙卧東
山諸人毎相與言安石不肻出將如蒼生何今亦蒼
生將如卿何謝笑而不荅



    ```
  - `25-paidiao-027` · 排調第二十五 · reviewed · reader_ready=false · surface: 謝安
    ```text
初謝安在東山居布衣時兄弟已有富貴者翕集家

門傾動人物劉夫人戲謂安曰大丈夫不當如此乎
謝乃捉鼻曰但恐不免耳

    ```
  - `25-paidiao-038` · 排調第二十五 · reviewed · reader_ready=false · surface: 安石
    ```text
桓公既廢海西立簡文

侍中謝公見桓公拜桓驚笑曰安石卿何事至爾謝
曰未有君拜於前臣立於後

    ```
  - `26-qingdi-024` · 輕詆第二十六 · reviewed · reader_ready=false · surface: 謝安
    ```text
庾道季詫謝公曰裴郎云謝安謂裴郎乃可不惡何
得為復飲酒裴郎又云謝安目支道林如九
方臯之相馬略其玄黄取其儁逸




謝公云都無此二語裴自為此辭耳庾
意甚不以為好因陳東亭經酒壚下賦讀畢都不下
賞裁直云君乃復作
    ```
- Liu-annotation-only presence:
  - `01-dexing-034` · 德行第一 · reviewed · reader_ready=false · surface: 安石、謝安
    ```text
(粹通逺温雅融畼桓彛見其四嵗時稱之曰此/文字志曰謝安字安石奕弟也世有學行安弘)
    ```
  - `01-dexing-036` · 德行第一 · reviewed · reader_ready=false · surface: 安石
    ```text
(子真之意也/邪安石之㫖同)
    ```
  - `02-yanyu-090` · 言語第二 · reviewed · reader_ready=false · surface: 謝安
    ```text
(書陸納兼侍中卞耽讀黄門侍郎謝石吏部袁宏兼/康三年九月九日帝講孝經僕射謝安侍坐吏部尚)
    ```
  - `02-yanyu-101` · 言語第二 · reviewed · reader_ready=false · surface: 謝安
    ```text
(朝廷求九錫謝安使吏部/晉安帝紀曰温在姑孰諷)
    ```
  - `03-zhengshi-014` · 政事第三 · reviewed · reader_ready=false · surface: 謝安石
    ```text
(能行無理事謝安石毎歎詠此唱庾赤玉曽問羡王/卿軰自是網目不失皆是小道小善耳至如王公故)
    ```
  - `04-wenxue-048` · 文學第四 · reviewed · reader_ready=false · surface: 謝安
    ```text
(謝安/殷浩)
    ```
  - `05-fangzheng-062` · 方正第五 · reviewed · reader_ready=false · surface: 謝安
    ```text
(韋仲將縣橙上題之比下須髮盡白裁餘氣息還語/寳謝安與王語次因及魏時起陵雲閣忘題榜乃使)
    ```
  - `06-yaliang-031` · 雅量第六 · reviewed · reader_ready=false · surface: 謝安
    ```text
(軍謝安立此亭因以爲名/丹陽記曰太安中征虜將)
    ```
  - `06-yaliang-035` · 雅量第六 · reviewed · reader_ready=false · surface: 謝安
    ```text
(謝安無懼色方命駕出墅與兄子玄/續晉陽秋曰初符堅南冦京師大震)
    ```
  - `07-shijian-024` · 識鑒第七 · reviewed · reader_ready=false · surface: 謝安
    ```text
(果俊邁有風氣好老莊之言當世榮譽弗之屑也唯/謝安見其少時嘆曰若期生不佳我不復論士及長)
    ```
  - `08-shangyu-125` · 賞譽第八 · reviewed · reader_ready=false · surface: 謝安
    ```text
(與謝安相善也/世務以高尚爲情)
    ```
  - `08-shangyu-128` · 賞譽第八 · reviewed · reader_ready=false · surface: 謝安
    ```text
(好養志海濵襟情超畼尤好聲律然抑之以禮/安北王坦之也續晉陽秋曰謝安初擕幼穉同)
    ```
  - `10-guizhen-026` · 規箴第十 · reviewed · reader_ready=false · surface: 謝安
    ```text
(平北将軍坦之弟三子太傅謝安國寳婦父也惡而/期同舉内匡朝廷及恭表至乃斬緒以説諸侯國寳)
    ```
  - `14-rongzhi-034` · 容止第十四 · reviewed · reader_ready=false · surface: 謝安
    ```text
(謝安/僕射)
    ```
  - `23-rendan-049` · 任誕第二十三 · reviewed · reader_ready=false · surface: 謝安
    ```text
(伊神色無忤既吹一弄乃放笛云臣於筝乃不如笛/將軍桓伊善音樂孝武飲燕謝安侍坐帝命伊吹笛)
    ```
  - `33-youhui-016` · 尤悔第三十三 · reviewed · reader_ready=false · surface: 謝安
    ```text
(忖己德量不及謝安故解揚州以讓安自謂/續晉陽秋曰桓沖本以將相異宜才用不同)
    ```

### 桓溫 (`person-008`)

- directly participating Stories: none currently classified; main-text appearance is retained as `mentioned` pending explicit participation review.
- reviewed linked Stories: 41; reader-ready: 0; candidate links: 0; candidate contextual Mentions: 0
- main-text presence:
  - `02-yanyu-101` · 言語第二 · reviewed · reader_ready=false · surface: 桓温
    ```text
桓玄義興還後見司馬太傅太傅已醉坐上多客問
人云桓温來欲作賊如何

桓玄伏不得起謝景重時爲長史舉
板荅曰故宣武公黜昏暗登聖明功超伊霍紛紜之
議裁之聖鑒太傅曰我知我知卽舉酒云桓義興勸
卿酒桓出謝過

    ```
  - `05-fangzheng-058` · 方正第五 · reviewed · reader_ready=false · surface: 桓温
    ```text
王文度爲桓公長史時桓爲兒求王女王許咨藍田
既還藍田愛念文度雖長大猶抱著䣛上

文度因言桓求已女㛰藍田大怒排文度下䣛曰惡
見文度已復癡畏桓温靣兵那可嫁女與之文度還
報云下官家中先得㛰處桓公曰吾知矣此尊府君
不肯耳後桓女遂嫁文度兒


    ```
  - `07-shijian-019` · 識鑒第七 · reviewed · reader_ready=false · surface: 桓温
    ```text
小庾臨終自表以子園客爲代
朝廷慮其不從命
未知所遣乃共議用桓温劉尹曰使伊去必能克定
西楚然恐不可復制






    ```
  - `08-shangyu-073` · 賞譽第八 · reviewed · reader_ready=false · surface: 桓温
    ```text
庾稺恭與桓温書稱劉道生日夕在事大小殊快義
懐通樂既佳且足作友正實良器推此與君同濟艱
不者也


    ```
  - `08-shangyu-079` · 賞譽第八 · reviewed · reader_ready=false · surface: 桓温
    ```text
桓温行經王敦墓邊過望之云可兒可兒


    ```
  - `09-pinzao-032` · 品藻第九 · reviewed · reader_ready=false · surface: 桓温
    ```text
時人共論晉武帝出齊王之與立惠帝其失孰多






多謂立惠帝爲重桓温曰不然使子繼
父業弟承家祀有何不可



    ```
  - `09-pinzao-036` · 品藻第九 · reviewed · reader_ready=false · surface: 桓温
    ```text
撫軍問孫興公劉眞長何如曰清蔚簡令王仲祖何
如曰温潤恬和桓温何如曰
高爽邁出謝仁祖何如曰清易令逹阮思曠何如曰
弘潤通長袁羊何如曰洮洮清便殷洪逺何如曰逺
有致思卿自謂何如曰下官才能所經悉不如諸賢

至於斟酌時宜籠罩當世亦多所不及然以不才時
復
    ```
  - `09-pinzao-041` · 品藻第九 · reviewed · reader_ready=false · surface: 元子、桓元子
    ```text
未廢海西公時王元琳問桓元子箕子比干迹異心
同不審明公孰是孰非曰仁稱不異寧爲管仲




    ```
  - `25-paidiao-060` · 排調第二十五 · reviewed · reader_ready=false · surface: 桓温
    ```text
孝武屬王珣求女壻曰王敦桓温磊砢之流既不可
復得且小如意亦好豫人家事酷非所須正如真長
子敬比最佳珣舉謝混後袁山松欲擬謝婚

王曰卿莫近禁

臠

    ```
- Liu-annotation-only presence:
  - `01-dexing-037` · 德行第一 · reviewed · reader_ready=false · surface: 桓温
    ```text
(西公而立帝在位三年而崩/撫軍輔政大司馬桓温廢海)
    ```
  - `02-yanyu-055` · 言語第二 · reviewed · reader_ready=false · surface: 元子、桓温
    ```text
(别傳/桓温)
    ```
  - `02-yanyu-059` · 言語第二 · reviewed · reader_ready=false · surface: 桓温
    ```text
(枋頭奔敗知民望之去也乃屠袁真於夀陽既而謂/月大司馬桓温廢帝為海西公晉安帝紀曰桓温於)
    ```
  - `02-yanyu-065` · 言語第二 · reviewed · reader_ready=false · surface: 元子
    ```text
(守續曾孫大父魏郡府君卽車騎掾元子也/羊秉敘曰秉字長逹太山平陽人漢南陽太)
    ```
  - `02-yanyu-072` · 言語第二 · reviewed · reader_ready=false · surface: 桓温
    ```text
(善尺牘桓温在荆州辟為從事歴治中别駕遷滎陽/國史游撃將軍卒習鑿齒字彦威襄陽人少以文稱)
    ```
  - `02-yanyu-090` · 言語第二 · reviewed · reader_ready=false · surface: 桓温
    ```text
(江夏相從桓温平蜀封湘西伯益州刺史/字彥升陳郡人父瓌光禄大夫喬歴尚書郎)
    ```
  - `02-yanyu-095` · 言語第二 · reviewed · reader_ready=false · surface: 桓温
    ```text
(為桓温叅軍甚被親暱/宋明帝文章志曰愷之)
    ```
  - `02-yanyu-102` · 言語第二 · reviewed · reader_ready=false · surface: 桓温
    ```text
(大司馬桓温辟爲主簿從討袁真封交趾望海縣東/珣字元琳丞相導之孫領軍洽之子也少以清秀稱)
    ```
  - `04-wenxue-097` · 文學第四 · reviewed · reader_ready=false · surface: 桓温
    ```text
(為東征賦悉稱過江諸名望時桓温在/續晉陽秋曰宏為大司馬記室叅軍後)
    ```
  - `04-wenxue-098` · 文學第四 · reviewed · reader_ready=false · surface: 桓温
    ```text
(長康體中癡黠各半合而論之正平平耳世云有三/鈍而自矜尚為時所笑宋明帝文章志曰桓温云顧)
    ```
  - `05-fangzheng-006` · 方正第五 · reviewed · reader_ready=false · surface: 元子
    ```text
(通家年少遇我子元子上不吾容也後中書令李豐/無復憂矣玄歎曰士宗卿何不見事乎此人尤能以)
    ```
  - `06-yaliang-025` · 雅量第六 · reviewed · reader_ready=false · surface: 桓温
    ```text
(温密勑令無因鳴角鼓譟部伍並驚馳温陽駭異晞/深雅有局鎮嘗與桓温太宰武陵王晞同乗至板橋)
    ```
  - `06-yaliang-026` · 雅量第六 · reviewed · reader_ready=false · surface: 桓温
    ```text
(敬文丞相最小子有清譽夷㤗無競仕至鎮軍將軍/司馬桓温稱爲鳳鶵累遷尚書僕射吳國内史薈字)
    ```
  - `06-yaliang-029` · 雅量第六 · reviewed · reader_ready=false · surface: 桓温
    ```text
(大怒以爲黜其權謝安王坦之所建也入赴山陵百/帝紀曰簡文晏駕遺詔桓温依諸葛亮王導故事温)
    ```
  - `06-yaliang-030` · 雅量第六 · reviewed · reader_ready=false · surface: 桓温
    ```text
(專殺生之威/超得寵桓温)
    ```
  - `06-yaliang-039` · 雅量第六 · reviewed · reader_ready=false · surface: 桓温
    ```text
(常稱王掾必爲黒頭公未易才也/曰珣初辟大司馬掾桓温至重之)
    ```
  - `07-shijian-016` · 識鑒第七 · reviewed · reader_ready=false · surface: 桓温
    ```text
(龍山參寮畢集時佐史並著戎服風吹嘉帽墮落温/所得乃益器之後爲征西桓温參軍九月九日温遊)
    ```
  - `07-shijian-027` · 識鑒第七 · reviewed · reader_ready=false · surface: 桓温
    ```text
(治中胤既博學多聞又善於激賞當時每有盛坐胤/風姿美劭機悟敏率桓温在荆州取爲從事一歲至)
    ```
  - `08-shangyu-072` · 賞譽第八 · reviewed · reader_ready=false · surface: 桓温
    ```text
(才具仕至太宰長史桓温以其宗彊使下邳王晃誣/字也徐廣晉紀曰倩字少彦司空氷子皇后兄也有)
    ```
  - `08-shangyu-099` · 賞譽第八 · reviewed · reader_ready=false · surface: 桓温
    ```text
(簡文親賢民望任登宰輔桓温有平/續晉陽秋曰時穆帝幼沖母后臨朝)
    ```
  - `08-shangyu-101` · 賞譽第八 · reviewed · reader_ready=false · surface: 桓温
    ```text
(敷文析理自娛桓温在西蕃欽/續晉陽秋曰初安優遊山水以)
    ```
  - `09-pinzao-064` · 品藻第九 · reviewed · reader_ready=false · surface: 桓温
    ```text
(贈散騎常侍/念與桓温稱之)
    ```
  - `10-guizhen-019` · 規箴第十 · reviewed · reader_ready=false · surface: 桓温
    ```text
(爲部從事桓温臨州轉叅軍/含别傳曰刺史庾亮初命含)
    ```
  - `11-jiewu-006` · 捷悟第十一 · reviewed · reader_ready=false · surface: 桓温
    ```text
(酒可飲箕可用兵可使/精兵故桓温常曰京口)
    ```
  - `13-haoshuang-007` · 豪爽第十三 · reviewed · reader_ready=false · surface: 桓温
    ```text
(後議其所任耳其意氣如此唯與桓温友善相期以/翼未之貴也常曰此軰冝束之高閣俟天下清定然)
    ```
  - `17-shangshi-012` · 傷逝第十七 · reviewed · reader_ready=false · surface: 桓温
    ```text
(密計愔見即大怒曰小子死恨晚後不復哭/果慟悼成疾門生乃如超㫖則與桓温徃反)
    ```
  - `19-xianyuan-022` · 賢媛第十九 · reviewed · reader_ready=false · surface: 桓温
    ```text
(希弟倩希聞難而逃/中興書曰桓温殺庾)
    ```
  - `23-rendan-041` · 任誕第二十三 · reviewed · reader_ready=false · surface: 桓温
    ```text
(須食何不就身求乃至於此友傲然不屑荅曰就公/雖復營署壚肆不以為羞桓温常責之云君太不逮)
    ```
  - `24-jianao-015` · 簡傲第二十四 · reviewed · reader_ready=false · surface: 桓温
    ```text
(且獲寵於桓温/愔子超有盛名)
    ```
  - `27-jiajue-013` · 假譎第二十七 · reviewed · reader_ready=false · surface: 桓温
    ```text
(江州並不就還都因求爲東陽太守温甚恨之/中興書曰初桓温請范汪爲征西長史復表爲)
    ```
  - `28-chumian-006` · 黜免第二十八 · reviewed · reader_ready=false · surface: 桓温
    ```text
(守枋頭之役温既懷恥忿且憚遐因免遐官病卒/時人方之樊噲為桓温參軍數從温征伐歷竟陵太)
    ```
  - `28-chumian-007` · 黜免第二十八 · reviewed · reader_ready=false · surface: 桓温
    ```text
(位新蔡王晃首辭引與晞及子綜謀逆有司奏晞等/長不得執權常懷憤慨欲因桓温入朝殺之太宗郎)
    ```

### 劉惔 (`person-009`)

- directly participating Stories: none currently classified; main-text appearance is retained as `mentioned` pending explicit participation review.
- reviewed linked Stories: 36; reader-ready: 0; candidate links: 0; candidate contextual Mentions: 0
- main-text presence:
  - `01-dexing-035` · 德行第一 · reviewed · reader_ready=false · surface: 真長
    ```text
劉尹在郡臨終綿惙聞閣下祀神鼓舞正色曰莫得
淫祀
外請殺車中牛祭神真長
荅曰丘之禱久矣勿復為煩


    ```
  - `02-yanyu-054` · 言語第二 · reviewed · reader_ready=false · surface: 真長
    ```text
何驃騎亡後徵禇公入既至石頭王長史劉尹
同詣禇禇曰真長何以處我真長顧王曰此子能言
禇因視王王曰國自有周公



    ```
  - `02-yanyu-066` · 言語第二 · reviewed · reader_ready=false · surface: 劉真長、真長
    ```text
王長史與劉真長别後相見

王謂劉曰卿更
長進荅曰此若天之自髙耳


    ```
  - `02-yanyu-069` · 言語第二 · reviewed · reader_ready=false · surface: 劉真長、真長
    ```text
劉真長為丹陽尹許玄度出都就劉宿
牀帷新麗
飲食豐甘許曰若保全此處殊勝東山劉曰卿若知
吉凶由人吾安得不保此王逸少在
坐曰令巢許遇稷契當無此言二人並有愧色

    ```
  - `04-wenxue-026` · 文學第四 · reviewed · reader_ready=false · surface: 劉真長、真長
    ```text
劉真長與殷淵源談劉理如小屈殷曰惡卿不欲作
將善雲梯仰攻




    ```
  - `04-wenxue-053` · 文學第四 · reviewed · reader_ready=false · surface: 真長
    ```text
其才氣謂必參時彦欲詣劉尹
郷里及同舉者共笑之張遂詣劉劉洗濯料事處之
下坐唯通寒暑神意不接張欲自發無端頃之長史

諸賢來清言客主有不通處張乃遥於末坐判之言
約㫖逺足畼彼我之懷一坐皆驚真長延之上坐清
言彌日因留宿至曉張退劉曰卿且去正當取卿共
詣撫軍張還船同侣問何處宿張笑而不荅須臾真
長遣傳教覓張孝廉船同侣惋愕卽同載詣撫軍至
門劉前進謂撫軍曰下官今日為公得一太常博士

    ```
  - `05-fangzheng-051` · 方正第五 · reviewed · reader_ready=false · surface: 劉真長、真長
    ```text
劉真長王仲祖共行日旰未食有相識小人貽其餐
肴案甚盛真長辭焉仲祖曰聊以充虚何苦辭真長
曰小人都不可與作緣


    ```
  - `05-fangzheng-059` · 方正第五 · reviewed · reader_ready=false · surface: 真長
    ```text
王子敬數歲時嘗看諸門生樗蒱見有勝負因曰南
風不競
門生軰輕其小兒廼曰此郎亦管
中窺豹時見一斑子敬瞋目曰逺慙荀奉倩近愧劉
真長遂拂衣而去


    ```
  - `08-shangyu-022` · 賞譽第八 · reviewed · reader_ready=false · surface: 真長
    ```text
洛中雅雅有三嘏劉粹字純嘏宏字終嘏漠字沖嘏
是親兄弟王安豐甥並是王安豐女壻宏真長祖也


洛中錚錚馮惠卿名蓀是播子

蓀與邢喬俱司徒李胤外孫及胤子順並知名
時稱馮才清李才明純粹邢



    ```
  - `08-shangyu-083` · 賞譽第八 · reviewed · reader_ready=false · surface: 真長
    ```text
王長史謂林公真長可謂金玉滿堂林公曰金玉滿



    ```
  - `08-shangyu-088` · 賞譽第八 · reviewed · reader_ready=false · surface: 劉真長、真長
    ```text
王右軍道謝萬石在林澤中爲自遒上歎林公器朗
神儁道祖士少風領毛骨恐没世
不復見如此人道劉真長標雲柯而不扶踈


    ```
  - `08-shangyu-131` · 賞譽第八 · reviewed · reader_ready=false · surface: 真長
    ```text
謝太傅語真長阿齡於此事故欲太厲劉
曰亦名士之高操者

    ```
  - `08-shangyu-146` · 賞譽第八 · reviewed · reader_ready=false · surface: 真長
    ```text
謝車騎問謝公真長性至峭何足乃重荅曰是不見
耳阿見子敬尚使人不能巳



    ```
  - `09-pinzao-030` · 品藻第九 · reviewed · reader_ready=false · surface: 真長
    ```text
時人道阮思曠骨氣不及右軍簡秀不如真長韶潤
不如仲祖思致不如淵源而兼有諸人之美


    ```
  - `09-pinzao-037` · 品藻第九 · reviewed · reader_ready=false · surface: 真長
    ```text
桓大司馬下都問真長曰聞會稽王語竒進爾邪
劉
曰極進然故是第二流中人耳桓曰第一流復是誰
劉曰正是我輩耳

    ```
  - `25-paidiao-013` · 排調第二十五 · reviewed · reader_ready=false · surface: 劉真長、真長
    ```text
劉真長始見王丞相時盛暑之月丞相以腹熨彈棊
局曰何乃渹劉既出人問見王公云何劉曰
未見他異唯聞作吳語耳

    ```
  - `25-paidiao-019` · 排調第二十五 · reviewed · reader_ready=false · surface: 劉真長、真長
    ```text
于寳向劉真長
叙其&KR0679;神記

劉
曰卿可謂鬼之董狐



    ```
  - `25-paidiao-024` · 排調第二十五 · reviewed · reader_ready=false · surface: 真長
    ```text
桓大司馬乘雪欲獵先過王劉諸人許真長見其裝
束單急問老賊欲持此何作桓曰我若不為此卿輩
亦那得坐談


    ```
  - `25-paidiao-037` · 排調第二十五 · reviewed · reader_ready=false · surface: 劉真長、真長
    ```text
殷洪逺荅孫興公詩云聊復放一曲劉真長笑其語
拙問曰君欲云那放殷曰㯓臘亦放何必其鎗鈴邪



    ```
  - `25-paidiao-060` · 排調第二十五 · reviewed · reader_ready=false · surface: 真長
    ```text
孝武屬王珣求女壻曰王敦桓温磊砢之流既不可
復得且小如意亦好豫人家事酷非所須正如真長
子敬比最佳珣舉謝混後袁山松欲擬謝婚

王曰卿莫近禁

臠

    ```
  - `26-qingdi-009` · 輕詆第二十六 · reviewed · reader_ready=false · surface: 真長
    ```text
禇太傅南下孫長樂於船中視之言次及劉真
長死孫流涕因諷詠曰人之云亡邦國殄瘁
禇大怒曰真長平生何甞相比數而卿今日
作此面向人孫回泣向禇曰卿當念我時咸笑其才
而性鄙

    ```
  - `26-qingdi-010` · 輕詆第二十六 · reviewed · reader_ready=false · surface: 真長
    ```text
謝鎮西書與殷揚州為真長求㑹稽殷荅曰真長標

同伐異俠之大者常謂使君降階為甚乃復為之驅
馳邪

    ```
  - `26-qingdi-013` · 輕詆第二十六 · reviewed · reader_ready=false · surface: 真長
    ```text
高柔在東甚爲謝仁祖所重既出不爲王劉所知仁
祖曰近見高柔大自敷奏然未有所得真長云故不
可在偏地居輕在角䚥中爲人作議論髙柔聞
之云我就伊無所求人有向真長學此言者真長曰
我寔亦無可與伊者然遊燕猶與諸人書可要安固

安固者髙柔也




    ```
- Liu-annotation-only presence:
  - `03-zhengshi-018` · 政事第三 · reviewed · reader_ready=false · surface: 劉惔
    ```text
(不同由此見譏於當世/何充與王濛劉惔好尚)
    ```
  - `04-wenxue-033` · 文學第四 · reviewed · reader_ready=false · surface: 劉惔
    ```text
(已見/劉惔)
    ```
  - `05-fangzheng-044` · 方正第五 · reviewed · reader_ready=false · surface: 真長
    ```text
(巳見/真長)
    ```
  - `05-fangzheng-055` · 方正第五 · reviewed · reader_ready=false · surface: 劉惔
    ```text
(州剌史贈右將軍/劉惔所知累遷豫)
    ```
  - `07-shijian-019` · 識鑒第七 · reviewed · reader_ready=false · surface: 劉惔
    ```text
(制願大王自鎮上流惔請爲從軍司馬簡文不許温/文輔政然之劉惔曰温去必能定西楚然恐不能復)
    ```
  - `08-shangyu-109` · 賞譽第八 · reviewed · reader_ready=false · surface: 劉惔
    ```text
(劉惔齊名時人以濛/濛别傳曰濛與沛國)
    ```
  - `08-shangyu-111` · 賞譽第八 · reviewed · reader_ready=false · surface: 劉惔、真長
    ```text
(陽尹/真長丹)
    ```
  - `08-shangyu-144` · 賞譽第八 · reviewed · reader_ready=false · surface: 劉真長、真長
    ```text
(懐之詠每造䣛賞對夜以繫日/簡文皇帝劉真長説其情㫖及襟)
    ```
  - `09-pinzao-042` · 品藻第九 · reviewed · reader_ready=false · surface: 劉真長、真長
    ```text
(治可方衛洗馬不謝曰安得比其間可容數人江左/曰永和中劉真長謝仁祖共商略中朝人或問杜弘)
    ```
  - `09-pinzao-048` · 品藻第九 · reviewed · reader_ready=false · surface: 劉惔
    ```text
(理㑹所歸王濛略同而叙致過之其/劉惔别傳曰惔有儁才其談詠虚勝)
    ```
  - `14-rongzhi-026` · 容止第十四 · reviewed · reader_ready=false · surface: 劉真長、真長
    ```text
(中朝人士或曰杜弘治清標令上為後來之美/江左名士傳曰永和中劉真長謝仁祖共商略)
    ```
  - `17-shangshi-010` · 傷逝第十七 · reviewed · reader_ready=false · surface: 劉惔
    ```text
(濛至交及卒惔深悼之雖友于之愛不能過也/濛别傳曰濛以永和初卒年三十九沛國劉惔與)
    ```
  - `23-rendan-033` · 任誕第二十三 · reviewed · reader_ready=false · surface: 劉惔
    ```text
(王濛劉惔共遊新亭濛欲招尚先以問惔曰謝仁祖/明帝文章志曰尚性輕率不拘細行兄葬後徃墓還)
    ```

### 庾亮 (`person-010`)

- directly participating Stories: none currently classified; main-text appearance is retained as `mentioned` pending explicit participation review.
- reviewed linked Stories: 33; reader-ready: 0; candidate links: 0; candidate contextual Mentions: 0
- main-text presence:
  - `04-wenxue-079` · 文學第四 · reviewed · reader_ready=false · surface: 庾亮
    ```text
庾仲初作揚都賦成以呈庾亮亮以親族之懷大為
其名價云可三二京四三都於此人人競寫都下紙
為之貴謝太傅云不得爾此是屋下架屋耳事事擬
學而不免儉狹

    ```
  - `05-fangzheng-025` · 方正第五 · reviewed · reader_ready=false · surface: 庾亮
    ```text
諸葛恢大女適太尉庾亮兒


次女適徐州刺史羊忱兒
亮子被蘇峻害攺適江虨
恢兒娶鄧攸女于時
謝尚書求其小女㛰恢乃云羊鄧是世㛰江家我顧
伊庾家伊顧我不能復與謝裒兒㛰
及恢亡遂㛰
於是王右軍往謝家看
新婦猶
    ```
  - `06-yaliang-013` · 雅量第六 · reviewed · reader_ready=false · surface: 元規
    ```text
有往來者云庾公有東下意或謂王公可潜稍嚴以
備不虞王公曰我與元規雖俱王臣本懐布衣之好
若其欲來吾角巾徑還烏衣
何所稍嚴

    ```
  - `06-yaliang-017` · 雅量第六 · reviewed · reader_ready=false · surface: 元規
    ```text
庾太尉風儀偉長不輕舉止時人皆以爲假亮有大
兒數歲雅重之質便自如此人知是天性温太真嘗
隱幔怛之此兒神色恬然乃徐跪曰君侯何以爲此
論者謂不減亮蘇峻時遇害
或云見阿恭知元規非假

    ```
  - `09-pinzao-017` · 品藻第九 · reviewed · reader_ready=false · surface: 庾亮
    ```text
明帝問謝鯤君自謂何如庾亮荅曰端委廟堂使百
僚凖則臣不如亮一丘一壑自謂過之





    ```
  - `09-pinzao-022` · 品藻第九 · reviewed · reader_ready=false · surface: 元規、庾元規
    ```text
明帝問周伯仁卿自謂何如庾元規對曰蕭條方外
亮不如臣從容廊廟臣不如亮

    ```
  - `14-rongzhi-024` · 容止第十四 · reviewed · reader_ready=false · surface: 元規、庾亮
    ```text
徒登南樓理詠音調始遒聞函道中有屐聲甚厲定
是庾公俄而率左右十許人步來諸賢欲起避之公
徐云諸君少住老子於此處興復不淺因便據胡牀
與諸人詠謔竟坐甚得任樂後王逸少下與丞相言
及此事丞相曰元規爾時風範不得不小穨右軍荅

曰唯丘壑獨存


    ```
  - `17-shangshi-008` · 傷逝第十七 · reviewed · reader_ready=false · surface: 庾亮
    ```text
庾亮兒遭蘇峻難遇害諸葛道明女為庾兒婦既寡
將改適與亮書及之亮荅曰賢女尚

少故其宜也感念亡兒若在初没

    ```
  - `23-rendan-026` · 任誕第二十三 · reviewed · reader_ready=false · surface: 庾亮
    ```text
温太真位未髙時屢與揚州淮中估客樗蒱與輙不
競嘗一過大輸物戲屈無因得反與庾亮善於舫中
大喚亮曰卿可贖我庾即送直然後得還經此數四


    ```
  - `26-qingdi-002` · 輕詆第二十六 · reviewed · reader_ready=false · surface: 元規、庾元規
    ```text
庾元規語周伯仁諸人皆以君方樂周曰何樂謂樂
毅邪庾曰不爾樂令
耳周曰何乃刻畫無鹽以唐突西子也





    ```
  - `26-qingdi-003` · 輕詆第二十六 · reviewed · reader_ready=false · surface: 元規、庾元規
    ```text
深公云人謂庾元規名士胷中柴棘三斗許

    ```
  - `26-qingdi-004` · 輕詆第二十六 · reviewed · reader_ready=false · surface: 元規
    ```text
庾公權重足傾王公庾在石頭王在冶城坐大風揚
塵王以扇拂塵曰元規塵汙人






    ```
  - `26-qingdi-005` · 輕詆第二十六 · reviewed · reader_ready=false · surface: 元規
    ```text
王右軍少時甚澀訥在大將軍許王庾二公後來右
軍便起欲去大將軍留之曰爾家司空元規

復可所難

    ```
  - `27-jiajue-008` · 假譎第二十七 · reviewed · reader_ready=false · surface: 元規、庾亮、庾元規
    ```text
陶公自上流來赴蘇峻之難令誅庾公謂必戮庾可
以謝峻


庾
欲奔竄則不可欲㑹恐見執進退無計温公勸庾詣
陶曰卿但遥拜必無它我為卿保之庾從温言詣陶
至便拜陶自起止之曰庾元規何縁拜陶士衡畢又
降就下坐陶又自要起同坐坐定庾乃引咎責躬深
相遜謝陶不覺釋然


    ```
  - `33-youhui-010` · 尤悔第三十三 · reviewed · reader_ready=false · surface: 元規、庾亮、庾元規
    ```text
執辭愈固庾毎詣周庾從南
門入周從後門出庾甞一往奄至周不及去相對終
日庾從周索食周出𬞞食庾亦彊飯極歡并語世故
約相推引同佐世之任既仕至將軍二千石


而不稱
意中宵慨然曰大丈夫乃為庾元規所賣一嘆遂發

背而卒

    ```
- Liu-annotation-only presence:
  - `01-dexing-031` · 德行第一 · reviewed · reader_ready=false · surface: 元規、庾亮
    ```text
(人明穆皇后長兄也淵雅有德量/晉陽秋曰庾亮字元規潁川鄢陵)
    ```
  - `02-yanyu-049` · 言語第二 · reviewed · reader_ready=false · surface: 庾亮
    ```text
(征西主簿累遷祕書監/陽令庾亮為荆州以為)
    ```
  - `03-zhengshi-022` · 政事第三 · reviewed · reader_ready=false · surface: 庾亮
    ```text
(弟何充等相尋薨太宗以撫軍輔政徵浩為揚州從/仕至揚州刺史中軍將軍中興書曰建元初庾亮兄)
    ```
  - `04-wenxue-022` · 文學第四 · reviewed · reader_ready=false · surface: 庾亮
    ```text
(浩為亮司馬非為長史也/按庾亮僚屬名及中興書)
    ```
  - `05-fangzheng-036` · 方正第五 · reviewed · reader_ready=false · surface: 庾亮
    ```text
(勸峻誅亮遂與峻同反後以宛城降/術爲阜陵令逃亡無行庾亮徵蘇峻術)
    ```
  - `06-yaliang-018` · 雅量第六 · reviewed · reader_ready=false · surface: 庾亮
    ```text
(裒時直爲參軍不/按庾亮啓參佐名)
    ```
  - `07-shijian-016` · 識鑒第七 · reviewed · reader_ready=false · surface: 庾亮
    ```text
(事下都還亮引問風俗得失對曰待還當問從事吏/嘉少以清操知名太尉庾亮領江州辟嘉部廬陵從)
    ```
  - `08-shangyu-048` · 賞譽第八 · reviewed · reader_ready=false · surface: 庾亮
    ```text
(彞一代名士一見和尚/高坐傳曰庾亮周顗桓)
    ```
  - `08-shangyu-065` · 賞譽第八 · reviewed · reader_ready=false · surface: 庾亮
    ```text
(别至都謂庾亮曰吾爲卿得一佳吏部郎亮問所在/清惠博涉相遇怡然遂停宿因留數夕與寧結交而)
    ```
  - `10-guizhen-017` · 規箴第十 · reviewed · reader_ready=false · surface: 庾亮
    ```text
(殂朝野憂懼以玩德望乃拜司空玩辭/玩别傳曰是時王導郄鑒庾亮相繼薨)
    ```
  - `10-guizhen-019` · 規箴第十 · reviewed · reader_ready=false · surface: 庾亮
    ```text
(爲部從事桓温臨州轉叅軍/含别傳曰刺史庾亮初命含)
    ```
  - `14-rongzhi-023` · 容止第十四 · reviewed · reader_ready=false · surface: 庾亮
    ```text
(起兵衛帝室亮不聽下制曰妄起兵者誅故峻得作/興書曰初庾亮欲徵蘇峻卞壼不許温嶠及三吳欲)
    ```
  - `14-rongzhi-038` · 容止第十四 · reviewed · reader_ready=false · surface: 庾亮
    ```text
(說是庾亮/長仁已見一)
    ```
  - `17-shangshi-009` · 傷逝第十七 · reviewed · reader_ready=false · surface: 庾亮
    ```text
(公於白石祠中許賽車下牛從來未解為此/&KR0679;神記曰初庾亮病術士戴洋曰昔蘇峻事)
    ```
  - `18-qiyi-009` · 棲逸第十八 · reviewed · reader_ready=false · surface: 庾亮
    ```text
(初庾亮臨江州聞翟湯之風束帶躡屐而詣焉亮禮/一無所受值亂多宼聞湯名德皆不敢犯尋陽記曰)
    ```
  - `23-rendan-028` · 任誕第二十三 · reviewed · reader_ready=false · surface: 庾亮
    ```text
(林曰伯仁正有姊喪三日醉姑喪二日醉大損資望/後屢以酒失庾亮曰周侯末年可謂鳯徳之衰也語)
    ```
  - `27-jiajue-010` · 假譎第二十七 · reviewed · reader_ready=false · surface: 庾亮
    ```text
(父虨已見上/即庾亮子㑹妻)
    ```
  - `36-chouxi-003` · 仇隟第三十六 · reviewed · reader_ready=false · surface: 庾亮
    ```text
(嘯神氣甚逸導謂亮曰世將為復識事亮曰正足舒/庾亮遊于石頭㑹廙至爾日迅風飛颿廙倚船樓長)
    ```

### 王敦 (`person-011`)

- directly participating Stories: none currently classified; main-text appearance is retained as `mentioned` pending explicit participation review.
- reviewed linked Stories: 40; reader-ready: 0; candidate links: 0; candidate contextual Mentions: 0
- main-text presence:
  - `02-yanyu-037` · 言語第二 · reviewed · reader_ready=false · surface: 王敦
    ```text
王敦兄含爲光禄勲

敦既逆謀屯據南州含委職奔姑孰
王丞
相詣闕謝司
徒丞相揚州官僚問訊倉卒不知何辭顧司空時為
揚州别駕援翰曰王光禄逺避流言明公蒙塵路次
羣下不寧不審尊體起居何如

    ```
  - `02-yanyu-042` · 言語第二 · reviewed · reader_ready=false · surface: 王敦
    ```text
摯瞻曾作四郡太守大將軍户曹叅軍復出作内史



年始二十九嘗别王敦敦
謂瞻曰卿年未三十已為萬石亦太蚤瞻曰方於將
軍少為太蚤比之甘羅已為太老





    ```
  - `05-fangzheng-028` · 方正第五 · reviewed · reader_ready=false · surface: 王敦
    ```text
王含作廬江郡貪濁狼籍王敦護其兄故於衆坐稱
家兄在郡定佳廬江人士咸稱之時何充爲敦主簿
在坐正色曰充即廬江人所聞異於此敦黙然旁人
爲之反側充晏然神意自若



    ```
  - `05-fangzheng-031` · 方正第五 · reviewed · reader_ready=false · surface: 王敦、處仲
    ```text
王大將軍當下時咸謂無緣爾伯仁曰今主非堯
舜何能無過且人臣安得稱兵以向朝廷處仲狼抗
剛愎王平子何在







    ```
  - `05-fangzheng-032` · 方正第五 · reviewed · reader_ready=false · surface: 王敦
    ```text
王敦既下住船石頭欲有廢明帝意賔客盈坐敦知
帝聦明欲以不孝廢之每言帝不孝之狀而皆云温
太真所説温嘗爲東宫率後爲吾司馬甚悉之須臾
温來敦便奮其威容問温曰皇太子作人何似温曰
小人無以測君子敦
    ```
  - `07-shijian-006` · 識鑒第七 · reviewed · reader_ready=false · surface: 王敦、王處仲、處仲
    ```text
潘陽仲見王敦小時謂曰君蜂目巳露但豺聲未振
耳必能食人亦當爲人所食





    ```
  - `08-shangyu-043` · 賞譽第八 · reviewed · reader_ready=false · surface: 王敦
    ```text
劉琨稱祖車騎爲朗詣曰少爲王敦所歎









    ```
  - `08-shangyu-051` · 賞譽第八 · reviewed · reader_ready=false · surface: 王敦
    ```text
王敦爲大將軍鎭豫章衛玠避亂從洛投敦相見欣
然談話彌日于時謝鯤爲長史敦謂鯤曰不意永嘉
之中復聞正始之音阿平若在當復絶倒



    ```
  - `08-shangyu-079` · 賞譽第八 · reviewed · reader_ready=false · surface: 王敦
    ```text
桓温行經王敦墓邊過望之云可兒可兒


    ```
  - `09-pinzao-006` · 品藻第九 · reviewed · reader_ready=false · surface: 王敦
    ```text
正始中人士比論以五荀方五陳荀淑方陳寔荀靖
方陳諶

荀爽方陳紀荀彧方陳群


荀顗方陳泰

又以八裴方八王裴徽方王祥裴楷
方王夷甫裴康方王綏
裴綽方王澄裴
瓉方王敦裴遐方王導裴
頠方王戎裴邈方王玄

    ```
  - `11-jiewu-005` · 捷悟第十一 · reviewed · reader_ready=false · surface: 王敦
    ```text
王敦引軍垂至大桁明帝自出中堂温嶠為丹陽尹
帝令斷大桁故未斷帝大怒瞋目左右莫不悚懼

召諸公來嶠至不謝但求酒炙王導須

吏至徒跣下地謝曰天威在顔遂使温嶠不容得謝
嶠於是下謝帝廼釋然諸公共
    ```
  - `13-haoshuang-002` · 豪爽第十三 · reviewed · reader_ready=false · surface: 王處仲、處仲
    ```text
王處仲世許高尚之目嘗荒恣於色體爲之弊左右
諫之處仲曰吾乃不覺爾如此者甚易耳乃開後閤

驅諸婢妾數十人出路任其所之時人嘆焉


    ```
  - `13-haoshuang-004` · 豪爽第十三 · reviewed · reader_ready=false · surface: 王處仲、處仲
    ```text
王處仲每酒後轍詠老驥伏櫪志在千里烈士暮年
壯心不巳以如意打唾壷壷口盡缺

    ```
  - `25-paidiao-060` · 排調第二十五 · reviewed · reader_ready=false · surface: 王敦
    ```text
孝武屬王珣求女壻曰王敦桓温磊砢之流既不可
復得且小如意亦好豫人家事酷非所須正如真長
子敬比最佳珣舉謝混後袁山松欲擬謝婚

王曰卿莫近禁

臠

    ```
  - `27-jiajue-006` · 假譎第二十七 · reviewed · reader_ready=false · surface: 王敦
    ```text
王大將軍既為逆頓軍姑孰晉明帝以英武之才猶
相猜憚乃箸戎服騎巴賨馬齎一金馬鞭隂察軍形
勢未至十餘里有一客姥居店賣食帝過愒之謂姥
曰王敦舉兵圖逆猜害忠良朝廷駭懼社稷是憂故
劬勞晨夕用相覘察恐形迹危露或致狼狽追迫之
日姥其匿之便與客姥馬鞭而去行敦營匝而出軍
士覺曰此非常人也敦卧心動曰此必黄須鮮卑奴
來命騎追之已覺多許
    ```
  - `30-taichi-010` · 汰侈第三十 · reviewed · reader_ready=false · surface: 王敦
    ```text
石崇每與王敦入學戲見顔原象
而嘆曰若與同升孔堂去人何

必有間王曰不知餘人云何子貢去卿差近
石正色云士當令身名俱泰何
至以&KR1805;牖語人

    ```
  - `34-pilou-001` · 紕漏第三十四 · reviewed · reader_ready=false · surface: 王敦
    ```text
王敦初尚主如厠見漆箱盛乾棗本
以塞鼻王謂廁上亦下果食遂至盡既還婢擎金澡
盤盛水瑠璃盌盛澡豆因倒箸水中而飲之謂是乾
飯羣婢莫不掩口而笑之

    ```
  - `36-chouxi-003` · 仇隟第三十六 · reviewed · reader_ready=false · surface: 王敦
    ```text
王大將軍執司馬愍王夜遣世將載王於車而殺之
當時不盡知也


雖愍王家亦
未之皆悉而無忌兄弟皆稺

王胡之與無忌長甚相暱胡之甞共
遊無忌入告母請為饌母流涕曰王敦昔肆酷汝父
假手世將

吾所以積年不告汝
者王氏門彊汝兄弟尚幼不欲使此聲著葢以避禍
耳無忌驚號抽刃而出胡之去已逺

    ```
- Liu-annotation-only presence:
  - `02-yanyu-030` · 言語第二 · reviewed · reader_ready=false · surface: 王敦
    ```text
(我邦族矣舉寒素累遷尚書僕射爲王敦所害/遲雅道殆衰今復見周伯仁伯仁將祛舊風清)
    ```
  - `04-wenxue-018` · 文學第四 · reviewed · reader_ready=false · surface: 王處仲、處仲
    ```text
(無食能作不脩曰爲復可耳遂爲鴻臚丞太子洗馬/也琅邪王處仲爲鴻臚卿謂曰鴻臚丞差有禄卿常)
    ```
  - `04-wenxue-020` · 文學第四 · reviewed · reader_ready=false · surface: 王敦、處仲
    ```text
(傳曰鯤四十三卒贈太常/章太守王敦引為長史鯤别)
    ```
  - `04-wenxue-076` · 文學第四 · reviewed · reader_ready=false · surface: 王敦
    ```text
(害王敦取為叅軍敦縱兵都輦乃咨以大事璞極言/斧也璞曰吾所受有分恒恐用之不盡豈酒色之能)
    ```
  - `05-fangzheng-026` · 方正第五 · reviewed · reader_ready=false · surface: 王敦
    ```text
(天下無義人所殺復何所弔敦甚銜之猶取爲從事/物顗被害王敦使人弔焉嵩曰亡兄天下有義人爲)
    ```
  - `05-fangzheng-027` · 方正第五 · reviewed · reader_ready=false · surface: 王敦
    ```text
(禀於協累遷尚書令中宗信重之爲王敦所忌舉兵/饒安人少好學雖不研精而多所博渉中興制度皆)
    ```
  - `05-fangzheng-030` · 方正第五 · reviewed · reader_ready=false · surface: 王敦
    ```text
(王敦所殺此説非也/按明帝未即位顗巳爲)
    ```
  - `05-fangzheng-033` · 方正第五 · reviewed · reader_ready=false · surface: 王敦
    ```text
(郝嘏及左右文武勸顗避難顗曰吾備/晉陽秋曰王敦既下六軍敗績顗長史)
    ```
  - `05-fangzheng-039` · 方正第五 · reviewed · reader_ready=false · surface: 王敦
    ```text
(州侃文武距廙而求侃敦聞大怒及侃將莅廣州過/讃侃於王敦者乃以從弟廙代侃爲荆州左遷侃廣)
    ```
  - `08-shangyu-035` · 賞譽第八 · reviewed · reader_ready=false · surface: 王處仲、處仲
    ```text
(害豈能容我謂其噐宇不容於敦也/王玄曰王處仲得志於彼家叔猶不免)
    ```
  - `08-shangyu-047` · 賞譽第八 · reviewed · reader_ready=false · surface: 王敦
    ```text
(選侃代顗顗還建康未即得用也/侃救之得免顗至武昌投王敦敦更)
    ```
  - `08-shangyu-054` · 賞譽第八 · reviewed · reader_ready=false · surface: 王敦
    ```text
(將軍爲王敦所害贈左光禄大夫儀同三司/思廣陵人才義辯濟有風標鋒頴累遷征西)
    ```
  - `08-shangyu-055` · 賞譽第八 · reviewed · reader_ready=false · surface: 王敦
    ```text
(為主簿知敦有不臣之心縱酒昬酣不綜/中興書曰阮裕少有德行王敦聞其名召)
    ```
  - `09-pinzao-011` · 品藻第九 · reviewed · reader_ready=false · surface: 處仲
    ```text
(嵩第二處仲第三敳以澄敦莫巳若也及澄䘮敦敗/時人許以人倫鑒識常爲天下士目曰阿平第一子)
    ```
  - `09-pinzao-015` · 品藻第九 · reviewed · reader_ready=false · surface: 王敦
    ```text
(甫爲四友今故荅也/王澄庾敳王敦王夷)
    ```
  - `09-pinzao-017` · 品藻第九 · reviewed · reader_ready=false · surface: 王敦
    ```text
(隨王敦下入/晉陽秋曰鯤)
    ```
  - `10-guizhen-012` · 規箴第十 · reviewed · reader_ready=false · surface: 王敦
    ```text
(章太守王敦將肆/晉陽秋曰鯤爲豫)
    ```
  - `10-guizhen-016` · 規箴第十 · reviewed · reader_ready=false · surface: 王敦
    ```text
(曰男兒不建豹尾不復歸矣敦死充將吳儒斬首於/軍領吳國内史明帝伐王敦充率衆就王舍謂其妻)
    ```
  - `30-taichi-001` · 汰侈第三十 · reviewed · reader_ready=false · surface: 王敦
    ```text
(君夫問王敦聞君從弟佳人又解音律欲一作妓可/以致巨富王丞相德音記曰丞相素為諸父所重王)
    ```
  - `32-chanxian-001` · 讒險第三十二 · reviewed · reader_ready=false · surface: 王敦
    ```text
(後果為王敦所害劉琨聞之曰自取死耳/勁狹以此處世難得其死澄黙然無以荅)
    ```
  - `33-youhui-005` · 尤悔第三十三 · reviewed · reader_ready=false · surface: 王敦
    ```text
(相名德豈應有斯言也/按王澄自為王敦所害丞)
    ```
  - `33-youhui-008` · 尤悔第三十三 · reviewed · reader_ready=false · surface: 王敦
    ```text
(馬頭𬒳殺因謂曰周家奕世令望而位不至三公/鄧粲晉紀曰王敦參軍有於敦坐樗蒱臨當成都)
    ```

### 袁宏 (`person-012`)

- directly participating Stories: none currently classified; main-text appearance is retained as `mentioned` pending explicit participation review.
- reviewed linked Stories: 14; reader-ready: 0; candidate links: 0; candidate contextual Mentions: 0
- main-text presence:
  - `02-yanyu-083` · 言語第二 · reviewed · reader_ready=false · surface: 袁宏、袁彦伯
    ```text
袁彦伯為謝安南司馬都下諸人送至瀨鄉
將别既自悽惘歎曰江山遼落居然有萬里之勢






    ```
  - `04-wenxue-092` · 文學第四 · reviewed · reader_ready=false · surface: 袁彦伯
    ```text
桓宣武命袁彦伯作北征賦
既成公與時賢共㸔咸嗟歎之時王珣在坐云

恨少一句得寫字足韻當佳袁即於坐攬筆益云感
不絶於余心泝流風而獨寫公謂王曰當今不得不
以此事推袁





    ```
  - `04-wenxue-094` · 文學第四 · reviewed · reader_ready=false · surface: 袁彦伯
    ```text
袁彦伯作名士傳成

見謝公公笑曰我嘗與諸人道江北事特
作狡獪耳彦伯遂以箸書

    ```
  - `04-wenxue-097` · 文學第四 · reviewed · reader_ready=false · surface: 袁宏
    ```text
袁宏始作東征賦都不道陶公胡奴誘之狹室中臨
以白刄曰先公勲業如是君作東征賦云何
相忽略宏窘蹙無計便荅我大道公何以云無因誦
曰精金百鍊在割能斷功則治人職思靖亂長沙之
勲為史所讃






    ```
  - `08-shangyu-034` · 賞譽第八 · reviewed · reader_ready=false · surface: 袁宏
    ```text
室叅軍雅相知
重敕世子毗曰夫學之所益者淺體之所安者深閑
習禮度不如式瞻儀形諷味遺言不如親承音㫖王
叅軍人倫之表汝其師之或曰王趙鄧三叅軍人倫
之表汝其師之謂安期鄧伯道趙穆也




袁宏作名士傳直云王叅軍或
云趙家先猶有此本

    ```
  - `09-pinzao-079` · 品藻第九 · reviewed · reader_ready=false · surface: 袁彦伯
    ```text
袁彦伯爲吏部郎子敬與郄嘉賔書曰彦伯巳入殊
足頓興往之氣故知捶撻自難爲人冀小卻當復差
耳

    ```
  - `22-chongli-002` · 寵禮第二十二 · reviewed · reader_ready=false · surface: 袁宏
    ```text
桓宣武嘗請叅佐入宿袁宏伏滔相次而至蒞名府
中復有袁叅軍彦伯疑焉令傳教更質傳教曰叅軍
是袁伏之袁復何所疑

    ```
- Liu-annotation-only presence:
  - `01-dexing-001` · 德行第一 · reviewed · reader_ready=false · surface: 袁宏
    ```text
(章為穉獨設一榻去/袁宏漢紀曰蕃在豫)
    ```
  - `01-dexing-003` · 德行第一 · reviewed · reader_ready=false · surface: 袁宏
    ```text
(疾汝南先賢傳曰袁宏字奉髙慎陽人友黄叔度於/徵泰曰吾觀乾象人事天之所廢不可支也遂辭以)
    ```
  - `02-yanyu-090` · 言語第二 · reviewed · reader_ready=false · surface: 袁宏
    ```text
(書陸納兼侍中卞耽讀黄門侍郎謝石吏部袁宏兼/康三年九月九日帝講孝經僕射謝安侍坐吏部尚)
    ```
  - `02-yanyu-101` · 言語第二 · reviewed · reader_ready=false · surface: 袁宏
    ```text
(豈可以此事語人邪安徐問其計彪之曰聞其疾已/郎袁宏具其草以示僕射王彪之彪之作色曰丈夫)
    ```
  - `03-zhengshi-003` · 政事第三 · reviewed · reader_ready=false · surface: 袁宏
    ```text
(漢紀/袁宏)
    ```
  - `04-wenxue-088` · 文學第四 · reviewed · reader_ready=false · surface: 袁宏
    ```text
(小字也/虎袁宏)
    ```
  - `05-fangzheng-006` · 方正第五 · reviewed · reader_ready=false · surface: 袁宏
    ```text
(袁宏名士傳最後出不依前史以爲鍾毓可謂謬矣/事多詳覈孫盛之徒皆采以著書並云玄距鍾㑹而)
    ```

### 温嶠 (`person-013`)

- directly participating Stories: none currently classified; main-text appearance is retained as `mentioned` pending explicit participation review.
- reviewed linked Stories: 20; reader-ready: 0; candidate links: 0; candidate contextual Mentions: 0
- main-text presence:
  - `02-yanyu-035` · 言語第二 · reviewed · reader_ready=false · surface: 太真、温嶠
    ```text
劉琨雖隔閡寇戎志存本朝


謂温嶠曰班彪識劉氏之復興馬
援知漢光之可輔

今晉祚雖衰天
命未改吾欲立功於河北使卿延譽於江南子其行
乎温曰嶠雖不敏才非昔人明公以桓文之姿建匡
立之功豈敢辭命




    ```
  - `02-yanyu-036` · 言語第二 · reviewed · reader_ready=false · surface: 温嶠
    ```text
温嶠初爲劉琨使來過江于時江左營建始爾綱紀
未舉温新至深有諸慮旣詣王丞相陳主上幽越社
稷焚滅山陵夷毁之酷有黍離之痛温忠慨深烈言
與泗俱丞相亦與之對泣叙情旣畢便深自陳結丞
相亦厚相酬納旣出
    ```
  - `05-fangzheng-032` · 方正第五 · reviewed · reader_ready=false · surface: 太真
    ```text
王敦既下住船石頭欲有廢明帝意賔客盈坐敦知
帝聦明欲以不孝廢之每言帝不孝之狀而皆云温
太真所説温嘗爲東宫率後爲吾司馬甚悉之須臾
温來敦便奮其威容問温曰皇太子作人何似温曰
小人無以測君子敦聲色並厲欲以威力使從巳乃

重問温太子何以稱佳温曰鈎深致逺葢非淺識所
測然以禮侍親可
    ```
  - `06-yaliang-017` · 雅量第六 · reviewed · reader_ready=false · surface: 太真、温太真
    ```text
庾太尉風儀偉長不輕舉止時人皆以爲假亮有大
兒數歲雅重之質便自如此人知是天性温太真嘗
隱幔怛之此兒神色恬然乃徐跪曰君侯何以爲此
論者謂不減亮蘇峻時遇害
或云見阿恭知元規非假

    ```
  - `09-pinzao-025` · 品藻第九 · reviewed · reader_ready=false · surface: 太真、温太真
    ```text
世論温太真是過江第二流之高者時名輩共説人
物第一將盡之間温常失色


    ```
  - `11-jiewu-005` · 捷悟第十一 · reviewed · reader_ready=false · surface: 温嶠
    ```text
王敦引軍垂至大桁明帝自出中堂温嶠為丹陽尹
帝令斷大桁故未斷帝大怒瞋目左右莫不悚懼

召諸公來嶠至不謝但求酒炙王導須

吏至徒跣下地謝曰天威在顔遂使温嶠不容得謝
嶠於是下謝帝廼釋然諸公共嘆王機悟名言

    ```
  - `23-rendan-026` · 任誕第二十三 · reviewed · reader_ready=false · surface: 太真、温太真
    ```text
温太真位未髙時屢與揚州淮中估客樗蒱與輙不
競嘗一過大輸物戲屈無因得反與庾亮善於舫中
大喚亮曰卿可贖我庾即送直然後得還經此數四


    ```
  - `31-fenjuan-004` · 忿狷第三十一 · reviewed · reader_ready=false · surface: 太真、温太真
    ```text
桓宣武與袁彦道樗蒱袁彦道齒不合遂厲色擲去
五木温太真云見袁生遷怒知顔子為貴


    ```
  - `33-youhui-007` · 尤悔第三十三 · reviewed · reader_ready=false · surface: 温嶠
    ```text
王導温嶠俱見明帝帝問温前世所以得天下之由
温未荅頃王曰温嶠年少未諳臣爲陛下陳之王廼
具叙宣王創業之始誅夷名族寵樹同已及文王之

末高貴鄉公事明帝
聞之覆面箸牀曰若如公言胙安得長

    ```
- Liu-annotation-only presence:
  - `01-dexing-026` · 德行第一 · reviewed · reader_ready=false · surface: 温嶠
    ```text
(操能清言歴太子中庶子廷尉卿避地江南温嶠薦/納字士言范陽遒人九世孝廉納諸母三兄最治行)
    ```
  - `02-yanyu-046` · 言語第二 · reviewed · reader_ready=false · surface: 温嶠
    ```text
(訴有異常童嶠竒之由是知名仕至鎮西將軍豫州/過人及遭父喪温嶠喭之尚號呌極哀既而收涕告)
    ```
  - `02-yanyu-055` · 言語第二 · reviewed · reader_ready=false · surface: 温嶠
    ```text
(識鑒温少有豪邁風氣為温嶠所知累遷琅邪内史/曰温字元子譙國龍亢人漢五更桓榮後也父彛有)
    ```
  - `02-yanyu-102` · 言語第二 · reviewed · reader_ready=false · surface: 温嶠
    ```text
(後都邑殘荒温嶠議徙都豫章以/晉陽秋曰蘇峻既誅大事克平之)
    ```
  - `05-fangzheng-031` · 方正第五 · reviewed · reader_ready=false · surface: 太真、温太真
    ```text
(爲東宫庶子在承華門外與顗相/顗别傳曰王敦討劉隗時温太真)
    ```
  - `06-yaliang-023` · 雅量第六 · reviewed · reader_ready=false · surface: 温嶠
    ```text
(門外王師敗績亮於陳㰎三弟奔温嶠/秋曰蘇峻作逆詔亮都督征討戰于建陽)
    ```
  - `14-rongzhi-023` · 容止第十四 · reviewed · reader_ready=false · surface: 温嶠
    ```text
(起兵衛帝室亮不聽下制曰妄起兵者誅故峻得作/興書曰初庾亮欲徵蘇峻卞壼不許温嶠及三吳欲)
    ```
  - `14-rongzhi-027` · 容止第十四 · reviewed · reader_ready=false · surface: 温嶠
    ```text
(故名温吳志曰孫權字仲謀䇿弟/宋明帝文章志曰温為温嶠所賞)
    ```
  - `23-rendan-021` · 任誕第二十三 · reviewed · reader_ready=false · surface: 温嶠
    ```text
(知愛卓請爲平南長史卒/人燕&KR1805;側取醉而去温嶠素)
    ```
  - `27-jiajue-008` · 假譎第二十七 · reviewed · reader_ready=false · surface: 温嶠
    ```text
(殺我也遂克京邑平南温嶠聞亂號泣登舟遣叅軍/削亦反遂下優詔以大司農徵之峻怒曰庾亮欲誘)
    ```
  - `33-youhui-009` · 尤悔第三十三 · reviewed · reader_ready=false · surface: 温嶠
    ```text
(嶠以母亡逼賊不得往臨葬固辭詔曰嶠以/虞預晉書曰元帝即位以温嶠為散騎侍郎)
    ```

### 王濛 (`person-014`)

- directly participating Stories: none currently classified; main-text appearance is retained as `mentioned` pending explicit participation review.
- reviewed linked Stories: 21; reader-ready: 0; candidate links: 0; candidate contextual Mentions: 0
- main-text presence:
  - `02-yanyu-068` · 言語第二 · reviewed · reader_ready=false · surface: 仲祖、王仲祖
    ```text
王仲祖聞蠻語不解茫然曰若使介葛盧來朝故當
不昩此語


    ```
  - `05-fangzheng-049` · 方正第五 · reviewed · reader_ready=false · surface: 仲祖、王濛
    ```text
王長史求東陽撫軍不用後疾篤臨終撫軍哀歎
曰吾將負仲祖於此命用之長史曰人言會稽王癡
真癡

    ```
  - `05-fangzheng-051` · 方正第五 · reviewed · reader_ready=false · surface: 仲祖、王仲祖
    ```text
劉真長王仲祖共行日旰未食有相識小人貽其餐
肴案甚盛真長辭焉仲祖曰聊以充虚何苦辭真長
曰小人都不可與作緣


    ```
  - `07-shijian-018` · 識鑒第七 · reviewed · reader_ready=false · surface: 仲祖、王仲祖
    ```text
王仲祖謝仁祖劉眞長俱至丹陽墓所省殷揚州殊
有确然之志旣反王謝相謂曰淵
源不起當如蒼生何深爲憂嘆劉曰卿諸人眞憂淵
源不起邪

    ```
  - `08-shangyu-081` · 賞譽第八 · reviewed · reader_ready=false · surface: 仲祖、王仲祖
    ```text
王仲祖稱殷淵源非以長勝人處長亦勝人


    ```
  - `09-pinzao-030` · 品藻第九 · reviewed · reader_ready=false · surface: 仲祖
    ```text
時人道阮思曠骨氣不及右軍簡秀不如真長韶潤
不如仲祖思致不如淵源而兼有諸人之美


    ```
  - `09-pinzao-036` · 品藻第九 · reviewed · reader_ready=false · surface: 仲祖、王仲祖
    ```text
撫軍問孫興公劉眞長何如曰清蔚簡令王仲祖何
如曰温潤恬和桓温何如曰
高爽邁出謝仁祖何如曰清易令逹阮思曠何如曰
弘潤通長袁羊何如曰洮洮清便殷洪逺何如曰逺
有致思卿自謂何如曰下官才能所經悉不如諸賢

至於斟酌時宜籠罩當世亦多
    ```
- Liu-annotation-only presence:
  - `02-yanyu-066` · 言語第二 · reviewed · reader_ready=false · surface: 仲祖
    ```text
(卿近大進劉曰卿仰看/語林曰仲祖語真長曰)
    ```
  - `03-zhengshi-018` · 政事第三 · reviewed · reader_ready=false · surface: 王濛
    ```text
(不同由此見譏於當世/何充與王濛劉惔好尚)
    ```
  - `04-wenxue-022` · 文學第四 · reviewed · reader_ready=false · surface: 王濛
    ```text
(爲王導所辟/王濛王述並)
    ```
  - `04-wenxue-055` · 文學第四 · reviewed · reader_ready=false · surface: 王濛
    ```text
(安王濛/許詢謝)
    ```
  - `05-fangzheng-055` · 方正第五 · reviewed · reader_ready=false · surface: 王蒙
    ```text
(將軍伊少有才蓺又善聲律加以標悟省率爲王蒙/小字也續晉陽秋曰伊字叔夏譙國銍人父景護軍)
    ```
  - `05-fangzheng-065` · 方正第五 · reviewed · reader_ready=false · surface: 王濛
    ```text
(皇后王藴女諱法惠爲孝武皇后/中興書曰王濛女諱穆之爲哀帝)
    ```
  - `08-shangyu-073` · 賞譽第八 · reviewed · reader_ready=false · surface: 王濛
    ```text
(明濟有文武才王濛每稱其思理淹通蕃屏/宋明帝文章志曰劉恢字道生沛國人識局)
    ```
  - `08-shangyu-076` · 賞譽第八 · reviewed · reader_ready=false · surface: 王濛
    ```text
(並巳見/王濛子脩)
    ```
  - `08-shangyu-098` · 賞譽第八 · reviewed · reader_ready=false · surface: 仲祖、王仲祖
    ```text
(其造微之功不異王弼/玄逺嘗至京師王仲祖稱)
    ```
  - `08-shangyu-133` · 賞譽第八 · reviewed · reader_ready=false · surface: 王濛
    ```text
(性和畼能清言/王濛别傳曰濛)
    ```
  - `09-pinzao-048` · 品藻第九 · reviewed · reader_ready=false · surface: 王濛
    ```text
(理㑹所歸王濛略同而叙致過之其/劉惔别傳曰惔有儁才其談詠虚勝)
    ```
  - `14-rongzhi-029` · 容止第十四 · reviewed · reader_ready=false · surface: 仲祖、王仲祖
    ```text
(王仲祖/語林曰)
    ```
  - `23-rendan-032` · 任誕第二十三 · reviewed · reader_ready=false · surface: 王濛
    ```text
(辟名士時賢恊贊中興/王濛别傳曰丞相王導)
    ```
  - `23-rendan-033` · 任誕第二十三 · reviewed · reader_ready=false · surface: 王濛
    ```text
(王濛劉惔共遊新亭濛欲招尚先以問惔曰謝仁祖/明帝文章志曰尚性輕率不拘細行兄葬後徃墓還)
    ```

### 孫晷 (`person-015`)

- directly participating Stories: none currently classified; main-text appearance is retained as `mentioned` pending explicit participation review.
- reviewed linked Stories: 0; reader-ready: 0; candidate links: 4; candidate contextual Mentions: 5
- main-text presence:
  - `02-yanyu-079` · 言語第二 · candidate · reader_ready=false · surface: explicit annotation evidence
    ```text
謝胡兒語庾道季
諸人莫當就卿談可堅城壘庾
曰若文度來我以偏師待之康伯來濟河焚舟


    ```
  - `05-fangzheng-047` · 方正第五 · candidate · reader_ready=false · surface: explicit annotation evidence
    ```text
王述轉尚書令事行便拜文度曰故應讓杜許藍田
云汝謂我堪此不文度曰何爲不堪但克讓自是美
事恐不可闕藍田慨然曰既云堪何爲復讓人言汝
勝我定不如我


    ```
  - `09-pinzao-063` · 品藻第九 · candidate · reader_ready=false · surface: explicit annotation evidence
    ```text
庾道季云思理倫和吾愧康伯志力彊正吾愧文度
自此以還吾皆百之

    ```
- Liu-annotation-only presence:
  - `26-qingdi-021` · 輕詆第二十六 · candidate · reader_ready=false · surface: explicit annotation evidence
    ```text
(箸膩顔挾左傳逐鄭康成自為高足弟/中郎坦之帢㡌也裴子曰林公云文度)
    ```

### 王遐 (`person-016`)

- directly participating Stories: none currently classified; main-text appearance is retained as `mentioned` pending explicit participation review.
- reviewed linked Stories: 0; reader-ready: 0; candidate links: 0; candidate contextual Mentions: 0
- main-text presence:
  - none
- Liu-annotation-only presence:
  - none

### 蘇峻 (`person-017`)

- directly participating Stories: none currently classified; main-text appearance is retained as `mentioned` pending explicit participation review.
- reviewed linked Stories: 19; reader-ready: 0; candidate links: 0; candidate contextual Mentions: 0
- main-text presence:
  - `05-fangzheng-025` · 方正第五 · reviewed · reader_ready=false · surface: 蘇峻
    ```text
諸葛恢大女適太尉庾亮兒


次女適徐州刺史羊忱兒
亮子被蘇峻害攺適江虨
恢兒娶鄧攸女于時
謝尚書求其小女㛰恢乃云羊鄧是世㛰江家我顧
伊庾家伊顧我不能復與謝裒兒㛰
及恢亡遂㛰
於是王右軍往謝家看
新婦猶有恢之遺法威儀端詳容服光整王歎曰我
在遣
    ```
  - `05-fangzheng-034` · 方正第五 · reviewed · reader_ready=false · surface: 子高、蘇峻
    ```text
蘇峻既至石頭百僚奔散




唯侍中鍾雅獨在帝側或謂鍾曰見可
而進知難而退古之道也君性亮直必不容於寇讎
何不用隨時之宜而坐待其弊邪鍾曰國亂不能匡
君危不能濟而各遜遁以求免吾懼董狐將執簡
    ```
  - `05-fangzheng-036` · 方正第五 · reviewed · reader_ready=false · surface: 蘇峻
    ```text
蘇峻時孔羣在横塘爲匡術所逼王丞相保存術

因衆坐戲語
令術勸羣酒以釋横塘之憾羣荅曰德非孔子厄同
匡人

雖陽和布氣鷹化爲鳩至於識者猶憎其眼




    ```
  - `05-fangzheng-037` · 方正第五 · reviewed · reader_ready=false · surface: 子高、蘇子高、蘇峻
    ```text
蘇子高事平
王庾諸公欲用孔廷尉爲丹陽
亂離之後百姓彫弊孔慨然曰昔肅祖臨崩諸君親
升御牀並蒙眷識共奉遺詔孔坦疎賤不在顧命之
列既有艱難則以微臣爲先今猶爼上腐肉任人膾
截耳於是拂衣而去諸公亦
    ```
  - `06-yaliang-017` · 雅量第六 · reviewed · reader_ready=false · surface: 蘇峻
    ```text
庾太尉風儀偉長不輕舉止時人皆以爲假亮有大
兒數歲雅重之質便自如此人知是天性温太真嘗
隱幔怛之此兒神色恬然乃徐跪曰君侯何以爲此
論者謂不減亮蘇峻時遇害
或云見阿恭知元規非假

    ```
  - `06-yaliang-023` · 雅量第六 · reviewed · reader_ready=false · surface: 蘇峻
    ```text
庾太尉與蘇峻戰敗率左右十餘人乗小船西奔
亂兵相剝
掠射誤中柂工應弦而倒舉船上咸失色分散亮不
動容徐曰此手那可使箸賊衆迺安

    ```
  - `10-guizhen-016` · 規箴第十 · reviewed · reader_ready=false · surface: 蘇峻
    ```text
蘇峻東征沈充


請吏部郎陸邁與俱
將至吳密勑左右令入閶門放火以示威
陸知其意謂峻曰吳治平未久必將有亂若爲亂階
請從我家始峻遂止

    ```
  - `14-rongzhi-023` · 容止第十四 · reviewed · reader_ready=false · surface: 蘇峻
    ```text
石頭事故朝廷傾覆

温忠武與庾文康投陶公求救陶公云肅祖顧命不
見及且蘇峻作亂釁由諸庾誅其兄弟不足以謝天
下


于時庾在温船後聞之憂怖無計别日温勸庾
見陶庾猶豫未能徃温曰溪狗我所悉卿但見之必
無憂也庾風姿神貌陶一見便改觀談宴竟日愛重
頓至

    ```
  - `17-shangshi-008` · 傷逝第十七 · reviewed · reader_ready=false · surface: 蘇峻
    ```text
庾亮兒遭蘇峻難遇害諸葛道明女為庾兒婦既寡
將改適與亮書及之亮荅曰賢女尚

少故其宜也感念亡兒若在初没

    ```
  - `23-rendan-030` · 任誕第二十三 · reviewed · reader_ready=false · surface: 蘇峻
    ```text
蘇峻亂諸庾逃散庾冰時為吳郡單身奔亡民吏皆
去唯郡卒獨以小船載冰出錢塘口蘧篨覆之時峻
賞募覓冰屬所在&KR0679;檢甚急卒捨船市渚因飲酒醉
還舞棹向船曰何處覓庾吳郡此中便是冰大惶怖
然
    ```
  - `27-jiajue-008` · 假譎第二十七 · reviewed · reader_ready=false · surface: 蘇峻
    ```text
陶公自上流來赴蘇峻之難令誅庾公謂必戮庾可
以謝峻


庾
欲奔竄則不可欲㑹恐見執進退無計温公勸庾詣
陶曰卿但遥拜必無它我為卿保之庾從温言詣陶
至便拜陶自起止之曰庾元規何縁拜陶士衡畢又
降就下坐陶又自
    ```
  - `29-jianshe-008` · 儉嗇第二十九 · reviewed · reader_ready=false · surface: 蘇峻
    ```text
蘇峻之亂庾太尉南奔見陶公陶公雅相賞重陶性

儉吝及食噉薤庾因留白陶問用此何為庾云故可
種於是大嘆庾非唯風流兼有治實

    ```
- Liu-annotation-only presence:
  - `02-yanyu-102` · 言語第二 · reviewed · reader_ready=false · surface: 蘇峻
    ```text
(後都邑殘荒温嶠議徙都豫章以/晉陽秋曰蘇峻既誅大事克平之)
    ```
  - `03-zhengshi-011` · 政事第三 · reviewed · reader_ready=false · surface: 蘇峻
    ```text
(以衆㑹峻既克京師拜丹陽尹後以罪誅/栁妻祖逖子渙女蘇峻招祖約為逆約遣栁)
    ```
  - `06-yaliang-015` · 雅量第六 · reviewed · reader_ready=false · surface: 蘇峻
    ```text
(平西將軍豫州剌史鎮壽陽與蘇峻反/祖約别傳曰約字士少范陽遒人累遷)
    ```
  - `07-shijian-015` · 識鑒第七 · reviewed · reader_ready=false · surface: 蘇峻
    ```text
(討蘇峻有功封彭澤侯贈車騎大將軍/僕射出爲會稽太守以父名會累表自陳)
    ```
  - `08-shangyu-054` · 賞譽第八 · reviewed · reader_ready=false · surface: 蘇峻
    ```text
(俱死王難鄧粲晉紀曰初咸和中貴遊子弟能談嘲/屏迹轉領軍尚書令蘇峻作亂率衆距戰父子二人)
    ```
  - `08-shangyu-067` · 賞譽第八 · reviewed · reader_ready=false · surface: 蘇峻
    ```text
(峻甚暱之以爲謀主及峻聞義軍起自姑孰屯于石/敗浮遊吳㑹吳人咸侮辱之聞京師亂馳出投蘇峻)
    ```
  - `17-shangshi-009` · 傷逝第十七 · reviewed · reader_ready=false · surface: 蘇峻
    ```text
(公於白石祠中許賽車下牛從來未解為此/&KR0679;神記曰初庾亮病術士戴洋曰昔蘇峻事)
    ```

### 謝尚 (`person-018`)

- directly participating Stories: none currently classified; main-text appearance is retained as `mentioned` pending explicit participation review.
- reviewed linked Stories: 24; reader-ready: 0; candidate links: 0; candidate contextual Mentions: 0
- main-text presence:
  - `02-yanyu-046` · 言語第二 · reviewed · reader_ready=false · surface: 仁祖、謝仁祖、謝尚
    ```text
謝仁祖年八嵗謝豫章將送客爾時語已神悟

自參上流諸人咸共歎之曰年少一坐之顔回仁祖
曰坐無尼父焉别顔回



    ```
  - `02-yanyu-047` · 言語第二 · reviewed · reader_ready=false · surface: 仁祖
    ```text
陶公疾篤都無獻替之言朝士以為恨







仁祖聞之曰時無竪刁故不
貽陶公話言
時賢以為德音

    ```
  - `04-wenxue-022` · 文學第四 · reviewed · reader_ready=false · surface: 仁祖
    ```text
當

與君共談析理旣共清言遂逹三更丞相與殷共相
徃反其餘諸賢略無所關旣彼我相盡丞相乃歎曰
向來語乃竟未知理源所歸至於辭喻不相負正始
之音正當爾耳明旦桓宣武語人曰昨夜聽殷王清
言甚佳仁祖亦不寂寞我亦時復造心顧看兩王掾
輙翣如生母狗馨

    ```
  - `05-fangzheng-025` · 方正第五 · reviewed · reader_ready=false · surface: 謝尚
    ```text
諸葛恢大女適太尉庾亮兒


次女適徐州刺史羊忱兒
亮子被蘇峻害攺適江虨
恢兒娶鄧攸女于時
謝尚書求其小女㛰恢乃云羊鄧是世㛰江家我顧
伊庾家伊顧我不能復與謝裒兒㛰
及恢亡遂㛰
於是王右軍往謝家看
新婦猶有恢之遺法威儀端詳容服光整王歎曰我
在遣女裁得爾耳


    ```
  - `05-fangzheng-052` · 方正第五 · reviewed · reader_ready=false · surface: 謝仁祖
    ```text
王脩齡嘗在東山甚貧乏陶胡奴爲烏程令

送一船米遺之卻不肯取直荅語王脩齡若飢自當
就謝仁祖索食不須陶胡奴米

    ```
  - `07-shijian-018` · 識鑒第七 · reviewed · reader_ready=false · surface: 謝仁祖
    ```text
王仲祖謝仁祖劉眞長俱至丹陽墓所省殷揚州殊
有确然之志旣反王謝相謂曰淵
源不起當如蒼生何深爲憂嘆劉曰卿諸人眞憂淵
源不起邪

    ```
  - `08-shangyu-089` · 賞譽第八 · reviewed · reader_ready=false · surface: 謝仁祖
    ```text
簡文目庾赤玉省率治除謝仁祖云庾赤玉匈中無

宿物

    ```
  - `08-shangyu-103` · 賞譽第八 · reviewed · reader_ready=false · surface: 謝尚
    ```text
桓宣武表云謝尚神懷挺率少致民譽



    ```
  - `08-shangyu-104` · 賞譽第八 · reviewed · reader_ready=false · surface: 謝尚
    ```text
世目謝尚爲令逹阮遥集云清畼似逹或云尚自然
令上

    ```
  - `09-pinzao-026` · 品藻第九 · reviewed · reader_ready=false · surface: 謝仁祖
    ```text
王丞相云見謝仁祖恒令人得上與何次道語唯舉
手指地曰正自爾馨


    ```
  - `09-pinzao-036` · 品藻第九 · reviewed · reader_ready=false · surface: 謝仁祖
    ```text
撫軍問孫興公劉眞長何如曰清蔚簡令王仲祖何
如曰温潤恬和桓温何如曰
高爽邁出謝仁祖何如曰清易令逹阮思曠何如曰
弘潤通長袁羊何如曰洮洮清便殷洪逺何如曰逺
有致思卿自謂何如曰下官才能所經悉不如諸賢

至於斟酌時宜籠罩當世亦多所不及然以不才時
復託懷玄勝逺詠老莊蕭條高
    ```
  - `09-pinzao-050` · 品藻第九 · reviewed · reader_ready=false · surface: 謝仁祖
    ```text
劉尹謂謝仁祖曰自吾有四友門人加親謂許玄度
曰自吾有由惡言不及於耳二人皆受而不恨



    ```
  - `10-guizhen-019` · 規箴第十 · reviewed · reader_ready=false · surface: 仁祖、謝尚
    ```text
羅君章爲桓宣武從事
謝鎭西作江夏往檢校之羅既至
初不問郡事徑就謝數日飲酒而還桓公問有何事
君章云不審公謂謝尚何似人桓公曰仁祖是勝我
許人君章云豈有勝公人而行非者故一無所問桓
公竒其意而不責也

    ```
  - `14-rongzhi-032` · 容止第十四 · reviewed · reader_ready=false · surface: 仁祖、謝仁祖
    ```text
或以方謝仁祖不乃重者桓大司馬曰諸君莫輕道
仁祖企腳北窻下彈琵琶故自有天際真人想


    ```
  - `23-rendan-032` · 任誕第二十三 · reviewed · reader_ready=false · surface: 謝仁祖
    ```text
王長史謝仁祖同為王公掾
長史云謝掾能作異舞謝便起舞神

意甚暇
王公熟視謂客曰使人思安豐

    ```
  - `23-rendan-037` · 任誕第二十三 · reviewed · reader_ready=false · surface: 謝仁祖、謝尚
    ```text
袁彦道有二妹一適殷淵源一適謝仁祖
語桓宣武云恨不更有一人配卿

    ```
  - `26-qingdi-013` · 輕詆第二十六 · reviewed · reader_ready=false · surface: 謝仁祖
    ```text
高柔在東甚爲謝仁祖所重既出不爲王劉所知仁
祖曰近見高柔大自敷奏然未有所得真長云故不
可在偏地居輕在角䚥中爲人作議論髙柔聞
之云我就伊無所求人有向真長學此言者真長曰
我寔亦無可與伊者然遊燕猶與諸人書可
    ```
  - `34-pilou-003` · 紕漏第三十四 · reviewed · reader_ready=false · surface: 謝仁祖
    ```text
蔡司徒渡江見彭蜞大喜曰蟹有八足加以二螯令
烹之既食吐下委頓方知非蟹後向謝仁祖說此事
謝曰卿讀爾雅不熟幾為勸學死





    ```
- Liu-annotation-only presence:
  - `04-wenxue-028` · 文學第四 · reviewed · reader_ready=false · surface: 謝尚
    ```text
(是時流或當貴其勝致/按殷浩大謝尚三嵗便)
    ```
  - `04-wenxue-088` · 文學第四 · reviewed · reader_ready=false · surface: 謝尚
    ```text
(㑹虎在運租船中諷詠聲既清㑹辭文藻抜非尚所/謝尚時鎮牛渚乗狄佳風月率爾與左右㣲服泛江)
    ```
  - `08-shangyu-124` · 賞譽第八 · reviewed · reader_ready=false · surface: 謝尚
    ```text
(年長於/按謝尚)
    ```
  - `09-pinzao-042` · 品藻第九 · reviewed · reader_ready=false · surface: 謝仁祖
    ```text
(治可方衛洗馬不謝曰安得比其間可容數人江左/曰永和中劉真長謝仁祖共商略中朝人或問杜弘)
    ```
  - `14-rongzhi-026` · 容止第十四 · reviewed · reader_ready=false · surface: 謝仁祖
    ```text
(中朝人士或曰杜弘治清標令上為後來之美/江左名士傳曰永和中劉真長謝仁祖共商略)
    ```
  - `23-rendan-033` · 任誕第二十三 · reviewed · reader_ready=false · surface: 仁祖、謝仁祖
    ```text
(尚初辭然已無歸意及再請即回軒焉其率如此/正當不為異同耳惔曰仁祖韻中自應來乃遣要之)
    ```

### 周顗 (`person-019`)

- directly participating Stories: none currently classified; main-text appearance is retained as `mentioned` pending explicit participation review.
- reviewed linked Stories: 24; reader-ready: 0; candidate links: 0; candidate contextual Mentions: 0
- main-text presence:
  - `02-yanyu-030` · 言語第二 · reviewed · reader_ready=false · surface: 伯仁、周伯仁、周顗
    ```text
庾公造周伯仁

伯仁
曰君何所欣說而忽肥庾曰君復何所憂慘而忽瘦
伯仁曰吾無所憂直是清虚日來滓穢日去耳

    ```
  - `05-fangzheng-027` · 方正第五 · reviewed · reader_ready=false · surface: 伯仁、周伯仁
    ```text
周伯仁爲吏部尚書在省內夜疾危急時刁玄亮爲
尚書令營救備親好之至良乆小損

明旦報仲智仲智狼狽來始入戸刁下牀

對之大泣説伯仁昨危急之狀仲智手批之刁爲辟
易於戸側既前都不問病直云君在中朝與和長輿
齊名那與佞人刁協有情逕便出

    ```
  - `05-fangzheng-029` · 方正第五 · reviewed · reader_ready=false · surface: 伯仁、周伯仁
    ```text
顧孟著嘗以酒勸周伯仁伯仁不受顧因移勸柱而

語柱曰詎可便作棟梁自遇周得之欣然遂爲衿契


    ```
  - `05-fangzheng-030` · 方正第五 · reviewed · reader_ready=false · surface: 周伯仁
    ```text
明帝在西堂會諸公飲酒未大醉帝問今名臣共集
何如堯舜時周伯仁爲僕射因厲聲曰今雖同人主
復那得等於聖治帝大怒還内作手詔滿一黄𥿄遂
付廷尉令收因欲殺之後數
日詔出周羣臣往省之周曰近知當不死罪不足至
此

    ```
  - `05-fangzheng-031` · 方正第五 · reviewed · reader_ready=false · surface: 伯仁
    ```text
王大將軍當下時咸謂無緣爾伯仁曰今主非堯
舜何能無過且人臣安得稱兵以向朝廷處仲狼抗
剛愎王平子何在







    ```
  - `05-fangzheng-033` · 方正第五 · reviewed · reader_ready=false · surface: 周伯仁
    ```text
王大將軍既反至石頭周伯仁往見之謂周曰卿何
以相負對曰公戎車犯正下官忝率六軍而王師不
振以此負公



    ```
  - `06-yaliang-021` · 雅量第六 · reviewed · reader_ready=false · surface: 伯仁
    ```text
周仲智飮酒醉瞋目還靣謂伯仁曰君才不如弟而
橫得重名須臾舉蠟燭火擲伯仁伯仁笑曰阿奴火
攻固出下策耳


    ```
  - `07-shijian-014` · 識鑒第七 · reviewed · reader_ready=false · surface: 伯仁、周伯仁
    ```text
周伯仁母冬至舉酒賜三子曰吾本謂度江託足無
所爾家有相爾等並羅列吾前復何憂周嵩起長跪
而泣曰不如阿母言伯仁爲人志大而才短名重而
識闇好乗人之弊此非自全之道嵩性狼抗亦不容

於世唯阿奴碌碌當
    ```
  - `09-pinzao-012` · 品藻第九 · reviewed · reader_ready=false · surface: 伯仁、周顗
    ```text
王大將軍在西朝時見周侯輒扇障靣不得住
後度江左不能
復爾王嘆曰不知我進伯仁退


    ```
  - `09-pinzao-014` · 品藻第九 · reviewed · reader_ready=false · surface: 伯仁、周伯仁、周顗
    ```text
明帝問周伯仁卿自謂何如郗鑒周曰鑒方臣如有
功夫復問郗郗曰周顗比臣有國士門風



    ```
  - `09-pinzao-022` · 品藻第九 · reviewed · reader_ready=false · surface: 周伯仁、周顗
    ```text
明帝問周伯仁卿自謂何如庾元規對曰蕭條方外
亮不如臣從容廊廟臣不如亮

    ```
  - `14-rongzhi-020` · 容止第十四 · reviewed · reader_ready=false · surface: 周伯仁
    ```text
周伯仁道桓茂倫嶔﨑歷落可笑人或云謝㓜輿言

    ```
  - `19-xianyuan-018` · 賢媛第十九 · reviewed · reader_ready=false · surface: 伯仁
    ```text
男子不在有女名絡秀聞外有貴人與一婢於内
宰豬羊作數十人飮食事事精辦不聞有人聲密覘
之獨見一女子狀貌非常浚因求爲妾父兄不許絡
秀曰門戸殄瘁何惜一女若連姻貴族將來或大益
父兄從之
遂生伯仁兄弟絡秀語伯仁等我所以
屈節爲汝家作妾門户計耳
汝若不與吾家作親親者吾亦不惜餘年伯仁等悉
從命由此李氏在世得方幅齒遇


    ```
  - `23-rendan-028` · 任誕第二十三 · reviewed · reader_ready=false · surface: 伯仁、周伯仁
    ```text
周伯仁風徳雅重深逹危亂過江積年恒大飲酒嘗

經三日不醒時人謂之三日僕射



    ```
  - `25-paidiao-014` · 排調第二十五 · reviewed · reader_ready=false · surface: 伯仁
    ```text
王公與朝士共飲酒舉瑠璃盌謂伯仁曰此盌腹殊
空謂之寳器何邪荅曰此盌英英誠為清徹

所以爲寳耳

    ```
  - `25-paidiao-017` · 排調第二十五 · reviewed · reader_ready=false · surface: 伯仁、周伯仁
    ```text
明帝問周伯仁眞長何如人荅曰故是千斤犗特王
公笑其言伯仁曰不如捲角牸有盤辟之好


    ```
  - `25-paidiao-018` · 排調第二十五 · reviewed · reader_ready=false · surface: 周伯仁
    ```text
王丞相枕周伯仁䣛指其腹曰卿此中何所有荅曰
此中空洞無物然容卿輩數百人

    ```
  - `26-qingdi-002` · 輕詆第二十六 · reviewed · reader_ready=false · surface: 周伯仁
    ```text
庾元規語周伯仁諸人皆以君方樂周曰何樂謂樂
毅邪庾曰不爾樂令
耳周曰何乃刻畫無鹽以唐突西子也





    ```
- Liu-annotation-only presence:
  - `02-yanyu-040` · 言語第二 · reviewed · reader_ready=false · surface: 伯仁
    ```text
(偉善於俛仰應荅精神足/鄧粲晉紀曰伯仁儀容弘)
    ```
  - `07-shijian-015` · 識鑒第七 · reviewed · reader_ready=false · surface: 伯仁、周伯仁
    ```text
(敦怪其有慘容而問之荅曰向哭周伯仁情不能巳/頭害周伯仁彬與顗素善往哭其尸甚慟既而見敦)
    ```
  - `08-shangyu-048` · 賞譽第八 · reviewed · reader_ready=false · surface: 周顗
    ```text
(彞一代名士一見和尚/高坐傳曰庾亮周顗桓)
    ```
  - `23-rendan-025` · 任誕第二十三 · reviewed · reader_ready=false · surface: 周顗
    ```text
(顗於衆中欲通其妾露其醜穢顔無怍色有司奏免/周顗及朝士詣尚書紀瞻觀伎瞻有愛妾能為新聲)
    ```
  - `33-youhui-006` · 尤悔第三十三 · reviewed · reader_ready=false · surface: 周顗
    ```text
(言無慙懼之色若不除之役將未歇也敦卽然之遂/漪說敦曰周顗戴淵皆有名望足以惑衆視近日之)
    ```
  - `33-youhui-008` · 尤悔第三十三 · reviewed · reader_ready=false · surface: 伯仁
    ```text
(仁緫角時與於東宫相遇一面披衿便許之三司何/伯仁垂作而不果有似下官此馬敦慨然㳅涕曰伯)
    ```

### 王戎 (`person-020`)

- directly participating Stories: none currently classified; main-text appearance is retained as `mentioned` pending explicit participation review.
- reviewed linked Stories: 33; reader-ready: 0; candidate links: 0; candidate contextual Mentions: 0
- main-text presence:
  - `01-dexing-016` · 德行第一 · reviewed · reader_ready=false · surface: 王戎、王濬沖
    ```text
王戎云與嵇康居二十年未嘗見其喜愠之色





    ```
  - `01-dexing-017` · 德行第一 · reviewed · reader_ready=false · surface: 濬沖、王戎
    ```text
王戎和嶠同時遭大喪俱以孝稱王雞骨支牀和哭
泣備禮


武帝謂劉仲雄曰


卿數省王和
不聞和哀苦過禮使人憂之仲雄曰和嶠雖備禮神
氣不損王戎雖不備禮而哀毁骨立臣以和嶠生孝
王戎死孝陛下不應憂嶠而應憂戎


    ```
  - `01-dexing-019` · 德行第一 · reviewed · reader_ready=false · surface: 王戎
    ```text
王戎云太保居在正始中不在能言之流及與之言
理中清逺將無以德掩其言

    ```
  - `01-dexing-020` · 德行第一 · reviewed · reader_ready=false · surface: 濬沖
    ```text
王安豐遭艱至性過人裴令徃弔之曰若使一慟果
能傷人濬沖必不免滅性之譏


    ```
  - `01-dexing-021` · 德行第一 · reviewed · reader_ready=false · surface: 王戎
    ```text
王戎父渾有令名官至凉州刺史
渾薨所歴九郡義故懷其德惠相率致賻數百
萬戎悉不受


    ```
  - `06-yaliang-004` · 雅量第六 · reviewed · reader_ready=false · surface: 王戎
    ```text
王戎七歲嘗與諸小兒遊看道邊李樹多子折枝諸
兒競走取之唯戎不動人問之荅曰樹在道邊而多
子此必苦李取之信然

    ```
  - `06-yaliang-005` · 雅量第六 · reviewed · reader_ready=false · surface: 王戎
    ```text
魏明帝於宣武埸上斷虎爪牙縱百姓觀之王戎七
歲亦往看虎承間攀欄而吼其聲震地觀者無不辟
易顛仆戎湛然不動了無恐色



    ```
  - `06-yaliang-006` · 雅量第六 · reviewed · reader_ready=false · surface: 王戎
    ```text
王戎爲侍中南郡太守劉肈遺筒中箋布五端戎雖
不受厚報其書



    ```
  - `08-shangyu-005` · 賞譽第八 · reviewed · reader_ready=false · surface: 王戎
    ```text
鍾士季目王安豐阿戎了了解人意
謂裴公之談經日不竭吏部郎闕文帝問其人

於鍾會會曰裴楷清通王戎簡要皆其選也於是用
裴

    ```
  - `08-shangyu-006` · 賞譽第八 · reviewed · reader_ready=false · surface: 王戎、王濬沖
    ```text
王濬沖裴叔則二人緫角詣鍾士季須臾去後客問
鍾曰向二童何如鍾曰裴楷清通王戎簡要後二十
年此二賢當爲吏部尚書冀爾時天下無滯才


    ```
  - `08-shangyu-010` · 賞譽第八 · reviewed · reader_ready=false · surface: 王戎
    ```text
王戎目山巨源如璞玉渾金人皆欽其寳莫知名其
噐

    ```
  - `08-shangyu-013` · 賞譽第八 · reviewed · reader_ready=false · surface: 王戎
    ```text
王戎目阮文業清倫有鑒識漢元以來未有此人




    ```
  - `08-shangyu-016` · 賞譽第八 · reviewed · reader_ready=false · surface: 王戎
    ```text
王戎云太尉神姿高徹如瑶林瓊樹自然是風塵外
物


    ```
  - `08-shangyu-024` · 賞譽第八 · reviewed · reader_ready=false · surface: 王戎
    ```text
王太尉曰見裴令公精明朗然籠葢人上非凡識也
若死而可作當與之同歸或云王戎語


    ```
  - `09-pinzao-006` · 品藻第九 · reviewed · reader_ready=false · surface: 王戎
    ```text
始中人士比論以五荀方五陳荀淑方陳寔荀靖
方陳諶

荀爽方陳紀荀彧方陳群


荀顗方陳泰

又以八裴方八王裴徽方王祥裴楷
方王夷甫裴康方王綏
裴綽方王澄裴
瓉方王敦裴遐方王導裴
頠方王戎裴邈方王玄

    ```
  - `14-rongzhi-011` · 容止第十四 · reviewed · reader_ready=false · surface: 王戎
    ```text
有人語王戎曰嵇延祖卓卓如野鶴之在雞羣荅曰

君未見其父耳

    ```
  - `17-shangshi-002` · 傷逝第十七 · reviewed · reader_ready=false · surface: 王濬沖
    ```text
王濬沖為尚書令著公服乘軺車經黄公酒壚下過
顧謂後車客吾昔與嵇叔
夜阮嗣宗共酣飲於此壚竹林之逰亦預其末自嵇
生夭阮公亡以來便為時所羈紲今日視此雖近邈
若山河


    ```
  - `17-shangshi-004` · 傷逝第十七 · reviewed · reader_ready=false · surface: 王戎
    ```text
王戎喪兒萬子山簡徃省之王悲不自勝簡曰孩抱
中物何至於此王曰聖人忘情最下不及情情之所
鍾正在我輩
簡服其言更為之慟

    ```
  - `23-rendan-001` · 任誕第二十三 · reviewed · reader_ready=false · surface: 王戎
    ```text
陳留阮籍譙國嵇康河内山濤三人年皆相比康年
少亞之預此契者沛國劉伶陳留阮咸河内向秀琅
邪王戎七人常集于竹林之下肆意酣畼故世謂竹
林七賢

    ```
  - `23-rendan-014` · 任誕第二十三 · reviewed · reader_ready=false · surface: 王戎
    ```text
裴成公婦王戎女王戎晨徃裴許不通徑前裴從牀
南下女從北下相對作賓主了無異色

    ```
  - `24-jianao-002` · 簡傲第二十四 · reviewed · reader_ready=false · surface: 濬沖、王戎
    ```text
王戎弱冠詣阮籍時劉公榮在坐阮謂王曰偶有二
斗美酒當與君共飲彼公榮者無預焉二人交觴酬
酢公榮遂不得一桮而言語談戯三人無異或有問
之者阮荅曰勝公榮者不得不與飲酒不如公榮者
不可不與飲酒唯公
    ```
  - `25-paidiao-004` · 排調第二十五 · reviewed · reader_ready=false · surface: 王戎
    ```text
嵇阮山劉在竹林酣飲王戎後徃步兵曰俗物已復
來敗人意王笑曰卿輩意亦復可
敗邪

    ```
  - `29-jianshe-002` · 儉嗇第二十九 · reviewed · reader_ready=false · surface: 王戎
    ```text
王戎儉吝其從子㛰與一單衣後更責之


    ```
  - `29-jianshe-003` · 儉嗇第二十九 · reviewed · reader_ready=false · surface: 王戎
    ```text
司徒王戎既貴且富區宅僮牧膏田水碓之屬洛下
無比契䟽鞅掌毎與夫人燭下散籌筭計





    ```
  - `29-jianshe-004` · 儉嗇第二十九 · reviewed · reader_ready=false · surface: 王戎
    ```text
王戎有好李賣之恐人得其種恒鑚其核


    ```
  - `29-jianshe-005` · 儉嗇第二十九 · reviewed · reader_ready=false · surface: 王戎
    ```text
王戎女適裴頠貸錢數萬女歸戎色不說女遽還錢
乃釋然

    ```
- Liu-annotation-only presence:
  - `02-yanyu-025` · 言語第二 · reviewed · reader_ready=false · surface: 王戎
    ```text
(其貞貴代王戎為尚書令八王故事曰司馬頴字叔/有理識累遷侍中河南尹在朝廷用心虚淡時人重)
    ```
  - `05-fangzheng-011` · 方正第五 · reviewed · reader_ready=false · surface: 王戎
    ```text
(而甄德王濟連遣婦入来生哭人邪濟等尚爾况餘/祖甚恚謂王戎曰我兄弟至親今出齊王自朕家計)
    ```
  - `06-yaliang-007` · 雅量第六 · reviewed · reader_ready=false · surface: 王戎
    ```text
(秋曰楷與王戎俱加儀同三司/變舉動自若諸人請救得免晉陽)
    ```
  - `07-shijian-005` · 識鑒第七 · reviewed · reader_ready=false · surface: 王戎
    ```text
(甫又忿祜言其必敗不相貴重天下爲之語曰二王/必此人也漢晉春秋曰初羊祜以軍法欲斬王戎夷)
    ```
  - `09-pinzao-071` · 品藻第九 · reviewed · reader_ready=false · surface: 王戎
    ```text
(才於時之談以阮為首王戎次之山向之徒皆其/魏氏春秋曰山濤通簡有德秀咸戎伶朗達有儁)
    ```
  - `14-rongzhi-006` · 容止第十四 · reviewed · reader_ready=false · surface: 王戎
    ```text
(而目甚清炤視/王戎形狀短小)
    ```
  - `25-paidiao-007` · 排調第二十五 · reviewed · reader_ready=false · surface: 王戎
    ```text
(中丞世語曰㝢少與裴楷王戎杜黙俱有名仕晉至/温顒已見荀氏譜曰㝢字景伯祖式太尉父保御史)
    ```

### 劉琨 (`person-021`)

- directly participating Stories: none currently classified; main-text appearance is retained as `mentioned` pending explicit participation review.
- reviewed linked Stories: 7; reader-ready: 0; candidate links: 0; candidate contextual Mentions: 0
- main-text presence:
  - `02-yanyu-035` · 言語第二 · reviewed · reader_ready=false · surface: 劉琨、越石
    ```text
劉琨雖隔閡寇戎志存本朝


謂温嶠曰班彪識劉氏之復興馬
援知漢光之可輔

今晉祚雖衰天
命未改吾欲立功於河北使卿延譽於江南子其行
乎温曰嶠雖不敏才非昔人明公以桓文之姿建匡
立之功豈敢辭
    ```
  - `02-yanyu-036` · 言語第二 · reviewed · reader_ready=false · surface: 劉琨
    ```text
温嶠初爲劉琨使來過江于時江左營建始爾綱紀
未舉温新至深有諸慮旣詣王丞相陳主上幽越社
稷焚滅山陵夷毁之酷有黍離之痛温忠慨深烈言
與泗俱丞相亦與之對泣叙情旣畢便深自陳結丞
相亦厚相酬納旣出懽然言曰
    ```
  - `07-shijian-009` · 識鑒第七 · reviewed · reader_ready=false · surface: 劉琨、劉越石
    ```text
劉越石云華彦夏識能不足彊果有餘



    ```
  - `08-shangyu-043` · 賞譽第八 · reviewed · reader_ready=false · surface: 劉琨
    ```text
劉琨稱祖車騎爲朗詣曰少爲王敦所歎









    ```
  - `27-jiajue-009` · 假譎第二十七 · reviewed · reader_ready=false · surface: 劉越石
    ```text
敗之餘乞粗存活便足慰吾餘
年何敢希汝比卻後少日公報姑云已覓得㛰處門
地粗可壻身名宦盡不減嶠因下玉鏡臺一枚姑大
喜既㛰交禮女以手披紗扇撫掌大笑曰我固疑是
老奴果如所卜
玉鏡臺
是公為劉越石長史北征劉聦所得




    ```
  - `33-youhui-004` · 尤悔第三十三 · reviewed · reader_ready=false · surface: 劉琨
    ```text
劉琨善能招延而拙於撫御一日雖有數千人歸投
其逃散而去亦復如此所以卒無所建




    ```
- Liu-annotation-only presence:
  - `32-chanxian-001` · 讒險第三十二 · reviewed · reader_ready=false · surface: 劉琨
    ```text
(澄曰卿形雖散朗而内/鄧粲晉紀云劉琨甞謂)
    ```

### 鄧攸 (`person-022`)

- directly participating Stories: none currently classified; main-text appearance is retained as `mentioned` pending explicit participation review.
- reviewed linked Stories: 6; reader-ready: 0; candidate links: 0; candidate contextual Mentions: 0
- main-text presence:
  - `01-dexing-028` · 德行第一 · reviewed · reader_ready=false · surface: 伯道、鄧攸
    ```text
鄧攸始避難於道中棄己子全弟子






既過江取一妾甚寵愛
歴年後訊其所由妾具說是北人遭亂憶父母姓名
乃攸之甥也攸素有德業言行無玷聞之哀恨終身
遂不復畜妾

    ```
  - `05-fangzheng-025` · 方正第五 · reviewed · reader_ready=false · surface: 鄧攸
    ```text
諸葛恢大女適太尉庾亮兒


次女適徐州刺史羊忱兒
亮子被蘇峻害攺適江虨
恢兒娶鄧攸女于時
謝尚書求其小女㛰恢乃云羊鄧是世㛰江家我顧
伊庾家伊顧我不能復與謝裒兒㛰
及恢亡遂㛰
於是王右軍往謝家看
新婦猶有恢之遺法威儀端詳容服光整王歎曰我
在遣女裁得爾耳


    ```
  - `08-shangyu-034` · 賞譽第八 · reviewed · reader_ready=false · surface: 鄧伯道、鄧攸
    ```text
海王鎭許昌以王安期爲記室叅軍雅相知
重敕世子毗曰夫學之所益者淺體之所安者深閑
習禮度不如式瞻儀形諷味遺言不如親承音㫖王
叅軍人倫之表汝其師之或曰王趙鄧三叅軍人倫
之表汝其師之謂安期鄧伯道趙穆也




袁宏作名士傳直云王叅軍或
云趙家先猶有此本

    ```
  - `08-shangyu-140` · 賞譽第八 · reviewed · reader_ready=false · surface: 伯道、鄧攸
    ```text
謝太傅重鄧僕射常言天地無知使伯道無兒


    ```
  - `09-pinzao-018` · 品藻第九 · reviewed · reader_ready=false · surface: 鄧伯道
    ```text
王丞相二弟不過江曰潁曰敝時論以潁比鄧伯道
敝比温忠武議郎祭酒者也


    ```
- Liu-annotation-only presence:
  - `11-jiewu-007` · 捷悟第十一 · reviewed · reader_ready=false · surface: 伯道
    ```text
(字伯道温長子也仕至豫州/石頭桓遐小字中興書曰遐)
    ```

### 謝鯤 (`person-023`)

- directly participating Stories: none currently classified; main-text appearance is retained as `mentioned` pending explicit participation review.
- reviewed linked Stories: 10; reader-ready: 0; candidate links: 0; candidate contextual Mentions: 0
- main-text presence:
  - `08-shangyu-051` · 賞譽第八 · reviewed · reader_ready=false · surface: 謝鯤
    ```text
王敦爲大將軍鎭豫章衛玠避亂從洛投敦相見欣
然談話彌日于時謝鯤爲長史敦謂鯤曰不意永嘉
之中復聞正始之音阿平若在當復絶倒



    ```
  - `09-pinzao-017` · 品藻第九 · reviewed · reader_ready=false · surface: 幼輿、謝鯤
    ```text
明帝問謝鯤君自謂何如庾亮荅曰端委廟堂使百
僚凖則臣不如亮一丘一壑自謂過之





    ```
  - `10-guizhen-012` · 規箴第十 · reviewed · reader_ready=false · surface: 謝鯤
    ```text
謝鯤爲豫章太守從大將軍下至石頭敦謂鯤曰余
不得復爲盛德之事矣鯤曰何爲其然但使自今巳
後日亡日去耳敦又稱疾不朝鯤
諭敦曰近者明公之舉雖欲大存社稷然四海之内

實懷未逹若能朝天子使羣臣釋然
    ```
  - `17-shangshi-006` · 傷逝第十七 · reviewed · reader_ready=false · surface: 謝鯤
    ```text
衛洗馬以永嘉六年喪謝鯤哭之感動路人


咸和中丞相王公教曰衛洗馬當
改葬此君風流名士海内所瞻可脩薄祭以敦舊好



    ```
  - `25-paidiao-015` · 排調第二十五 · reviewed · reader_ready=false · surface: 謝幼輿
    ```text
謝幼輿謂周侯曰卿類社樹逺望之峨峨拂青天就
而視之其根則羣狐所託下聚溷而已荅曰
枝條拂青天不以爲高羣狐亂其下不以爲濁聚溷
之穢卿之所保何足自稱

    ```
- Liu-annotation-only presence:
  - `01-dexing-023` · 德行第一 · reviewed · reader_ready=false · surface: 謝鯤
    ```text
(其後貴游子弟阮瞻王澄謝鯤胡母輔之之徒皆祖/隱晉書曰魏末阮籍嗜酒荒放露頭散髮裸袒箕踞)
    ```
  - `04-wenxue-020` · 文學第四 · reviewed · reader_ready=false · surface: 幼輿、謝鯤
    ```text
(通簡好老易善音樂以琴書為業避亂江東為豫/晉陽秋曰謝鯤字幼輿陳郡人父衡晉碩儒鯤性)
    ```
  - `08-shangyu-036` · 賞譽第八 · reviewed · reader_ready=false · surface: 謝鯤
    ```text
(深藏矣乃與妻荷擔入蜀莫知其所終/謂謝鯤阮孚曰易稱知幾其神乎君等可)
    ```
  - `08-shangyu-054` · 賞譽第八 · reviewed · reader_ready=false · surface: 幼輿
    ```text
(教罪莫斯甚中朝傾覆實由於此欲奏治之王導庾/者慕王平子謝幼輿等為達壼厲色於朝曰悖禮傷)
    ```
  - `09-pinzao-022` · 品藻第九 · reviewed · reader_ready=false · surface: 謝鯤
    ```text
(比亮不聞周顗/按諸書皆以謝鯤)
    ```

### 韓伯 (`person-024`)

- directly participating Stories: none currently classified; main-text appearance is retained as `mentioned` pending explicit participation review.
- reviewed linked Stories: 18; reader-ready: 0; candidate links: 0; candidate contextual Mentions: 0
- main-text presence:
  - `01-dexing-047` · 德行第一 · reviewed · reader_ready=false · surface: 康伯、韓康伯
    ```text
吳道助附子兄弟居在丹陽郡後遭母童夫人艱

朝夕哭臨及思至賓客弔省號踊哀絶路人為之
落淚韓康伯時為丹陽尹母殷在郡每聞二吳之哭
輙為悽惻語康伯曰汝若為選官當好料理此人康

伯亦甚相知韓後果為吏部尚書大吳不免哀制小
吳遂大貴達







    ```
  - `02-yanyu-072` · 言語第二 · reviewed · reader_ready=false · surface: 康伯、韓康伯
    ```text
王中郎令伏玄度習鑿齒



論青楚人物










臨成以示韓康伯康伯都無言王曰何故不言
韓曰無可無不可


    ```
  - `02-yanyu-079` · 言語第二 · reviewed · reader_ready=false · surface: 康伯
    ```text
謝胡兒語庾道季
諸人莫當就卿談可堅城壘庾
曰若文度來我以偏師待之康伯來濟河焚舟


    ```
  - `04-wenxue-027` · 文學第四 · reviewed · reader_ready=false · surface: 康伯
    ```text
殷中軍云康伯未得我牙後慧


    ```
  - `05-fangzheng-057` · 方正第五 · reviewed · reader_ready=false · surface: 韓伯、韓康伯
    ```text
韓康伯病拄杖前庭消搖見諸謝皆富貴轟隱
交路歎曰此復何異王莽時

    ```
  - `07-shijian-023` · 識鑒第七 · reviewed · reader_ready=false · surface: 康伯、韓康伯
    ```text
韓康伯與謝玄亦無深好玄北征後巷議疑其不振
康伯曰此人好名必能戰玄聞
之甚忿常於衆中厲色曰丈夫提千兵入死地以事

君親故發不得復云爲名

    ```
  - `08-shangyu-090` · 賞譽第八 · reviewed · reader_ready=false · surface: 康伯
    ```text
殷中軍道韓太常曰康伯少自標置居然是出羣器
及其發言遣辭往往有情致

    ```
  - `09-pinzao-063` · 品藻第九 · reviewed · reader_ready=false · surface: 康伯
    ```text
庾道季云思理倫和吾愧康伯志力彊正吾愧文度
自此以還吾皆百之

    ```
  - `09-pinzao-066` · 品藻第九 · reviewed · reader_ready=false · surface: 韓康伯
    ```text
蔡叔子云韓康伯雖無骨榦然亦膚立

    ```
  - `09-pinzao-081` · 品藻第九 · reviewed · reader_ready=false · surface: 韓康伯
    ```text
有人問袁侍中
曰殷仲堪何如韓康伯荅曰理義
所得優劣乃復未辨然門庭蕭寂居然有名士風流
殷不及韓故殷作誄云荆門晝掩閑庭晏然


    ```
  - `12-suhui-005` · 夙惠第十二 · reviewed · reader_ready=false · surface: 康伯、韓康伯
    ```text
韓康伯數歲家酷貧至大寒止得襦母殷夫人自成
之令康伯捉熨斗謂康伯曰且箸襦尋作複㡓兒云
巳足不須複㡓也毋問其故荅曰火在熨斗中而柄
熱今旣箸𥜗下亦當煗故不須耳毋甚異之知爲國

噐

    ```
  - `18-qiyi-014` · 棲逸第十八 · reviewed · reader_ready=false · surface: 韓康伯
    ```text
范宣未嘗入公門韓康伯與同載遂誘俱入郡范便
於車後趨下

    ```
  - `19-xianyuan-027` · 賢媛第十九 · reviewed · reader_ready=false · surface: 韓康伯
    ```text
韓康伯母隱古几毀壊卞鞠見几惡欲易之
荅曰我若不隱此汝何以得見古物


    ```
  - `19-xianyuan-032` · 賢媛第十九 · reviewed · reader_ready=false · surface: 康伯、韓康伯
    ```text
韓康伯母殷隨孫繪之之衡陽
於闔廬洲中逢桓南郡卞鞠是其外孫時
來問訊謂鞠曰我不死見此竪二世作賊在衡陽數
年繪之遇桓景真之難也

殷撫屍哭曰汝父昔罷豫章徴書朝至夕發
汝去郡邑數年為物不得動遂
    ```
  - `25-paidiao-053` · 排調第二十五 · reviewed · reader_ready=false · surface: 韓康伯
    ```text
范榮期見郗超俗情不淡戲之曰夷齊巢許一詣垂
名何必勞神苦形支䇿據梧邪郗未荅韓康伯曰何
不使遊刃皆虚



    ```
  - `26-qingdi-028` · 輕詆第二十六 · reviewed · reader_ready=false · surface: 韓康伯
    ```text
舊目韓康伯將肘無風骨

    ```
- Liu-annotation-only presence:
  - `01-dexing-038` · 德行第一 · reviewed · reader_ready=false · surface: 康伯、韓伯
    ```text
(潁川人好學善言理歴豫章太守領軍將軍/厚餉給之宣又不受續晉陽秋曰韓伯字康伯)
    ```
  - `28-chumian-005` · 黜免第二十八 · reviewed · reader_ready=false · surface: 韓伯
    ```text
(不見其有流放之戚外生韓伯始隨至徙所周年還/續晉陽秋曰浩雖廢黜夷神委命雅詠不輟雖家人)
    ```

### 何充 (`person-025`)

- directly participating Stories: none currently classified; main-text appearance is retained as `mentioned` pending explicit participation review.
- reviewed linked Stories: 17; reader-ready: 0; candidate links: 0; candidate contextual Mentions: 0
- main-text presence:
  - `05-fangzheng-028` · 方正第五 · reviewed · reader_ready=false · surface: 何充
    ```text
王含作廬江郡貪濁狼籍王敦護其兄故於衆坐稱
家兄在郡定佳廬江人士咸稱之時何充爲敦主簿
在坐正色曰充即廬江人所聞異於此敦黙然旁人
爲之反側充晏然神意自若



    ```
  - `05-fangzheng-041` · 方正第五 · reviewed · reader_ready=false · surface: 何充、何次道
    ```text
何次道庾季堅二人並爲元輔
成帝初崩于時嗣君
未定何欲立嗣子庾及朝議以外寇方强嗣子沖幼
乃立康帝康帝登
阼會群臣謂何曰朕今所以承大業爲誰之議何荅

曰陛下龍飛此是庾冰之功非臣之力于時用微臣
    ```
  - `08-shangyu-059` · 賞譽第八 · reviewed · reader_ready=false · surface: 何充、何次道
    ```text
何次道往丞相許丞相以麈尾指坐呼何共坐曰來
來此是君坐

    ```
  - `08-shangyu-060` · 賞譽第八 · reviewed · reader_ready=false · surface: 次道
    ```text
丞相治楊州廨舍按行而言曰我正爲次道治此爾
何少爲王公所重故屢發此嘆



    ```
  - `08-shangyu-067` · 賞譽第八 · reviewed · reader_ready=false · surface: 何次道
    ```text
何次道嘗送東人瞻望見賈寧在後輪中曰此人不
死終爲諸侯上客




    ```
  - `08-shangyu-130` · 賞譽第八 · reviewed · reader_ready=false · surface: 何次道
    ```text
劉尹云見何次道飲酒使人欲傾家釀

    ```
  - `09-pinzao-026` · 品藻第九 · reviewed · reader_ready=false · surface: 何充、何次道
    ```text
王丞相云見謝仁祖恒令人得上與何次道語唯舉
手指地曰正自爾馨


    ```
  - `09-pinzao-027` · 品藻第九 · reviewed · reader_ready=false · surface: 何次道、次道
    ```text
何次道爲宰相人有譏其信任不得其人
阮思曠慨然曰次道自不至此但布衣超居
宰相之位可恨唯此一條而巳



    ```
  - `25-paidiao-022` · 排調第二十五 · reviewed · reader_ready=false · surface: 何次道
    ```text
何次道徃瓦官寺禮拜甚勤阮思曠語之
曰卿志大宇宙勇邁終古
何曰卿今日何故忽見推阮曰我圖
數千戸郡尚不能得卿廼圖作佛不亦大乎

    ```
- Liu-annotation-only presence:
  - `02-yanyu-054` · 言語第二 · reviewed · reader_ready=false · surface: 何充
    ```text
(别見/何充)
    ```
  - `03-zhengshi-017` · 政事第三 · reviewed · reader_ready=false · surface: 何充、次道
    ```text
(淹通有文義才情累遷㑹稽内史侍/晉陽秋曰何充字次道廬江人思韻)
    ```
  - `03-zhengshi-018` · 政事第三 · reviewed · reader_ready=false · surface: 何充
    ```text
(不同由此見譏於當世/何充與王濛劉惔好尚)
    ```
  - `03-zhengshi-022` · 政事第三 · reviewed · reader_ready=false · surface: 何充
    ```text
(弟何充等相尋薨太宗以撫軍輔政徵浩為揚州從/仕至揚州刺史中軍將軍中興書曰建元初庾亮兄)
    ```
  - `07-shijian-019` · 識鑒第七 · reviewed · reader_ready=false · surface: 何充
    ```text
(之代爲荆州何充曰陶公重勲/陶侃别傳曰庾翼薨表其子爰)
    ```
  - `25-paidiao-051` · 排調第二十五 · reviewed · reader_ready=false · surface: 何充
    ```text
(陽秋曰何充性好佛道崇修佛寺供/中興書曰郗愔及弟曇奉天師道晉)
    ```
  - `26-qingdi-013` · 輕詆第二十六 · reviewed · reader_ready=false · surface: 何充
    ```text
(何充取為冠軍叅軍僶俛應命眷戀綢繆不能相舍/馳動之情既薄又愛翫賢妻便有終焉之志尚書令)
    ```
  - `36-chouxi-004` · 仇隟第三十六 · reviewed · reader_ready=false · surface: 何充
    ```text
(之士累遷江州刺史鎮南將軍/以文才司徒何充嘆曰所謂文質)
    ```

### 陸機 (`person-026`)

- directly participating Stories: none currently classified; main-text appearance is retained as `mentioned` pending explicit participation review.
- reviewed linked Stories: 8; reader-ready: 0; candidate links: 0; candidate contextual Mentions: 0
- main-text presence:
  - `02-yanyu-026` · 言語第二 · reviewed · reader_ready=false · surface: 士衡、陸機
    ```text
陸機詣王武子

武子前置數斛羊酪指以示陸曰卿江東何以敵
此陸云有千里蓴羮但未下鹽䜴耳


    ```
  - `05-fangzheng-018` · 方正第五 · reviewed · reader_ready=false · surface: 士衡、陸士衡
    ```text
盧志於衆坐
問陸士衡陸遜陸抗是君何物
荅曰如卿於盧毓盧珽

士龍失色既出戸謂兄曰何至如此彼
容不相知也士衡正色曰我父祖名播海內寧有不
知鬼子敢爾

















議者疑
二陸優劣謝公
    ```
  - `08-shangyu-020` · 賞譽第八 · reviewed · reader_ready=false · surface: 陸士衡、陸機
    ```text
有問秀才吳舊姓何如荅曰吳府君聖王之老成明
時之儁乂朱永長理物之至德清選之高望嚴仲弼
九臯之鳴鶴空谷之白駒顧彦先八音之琴瑟五色
之龍章張威伯歲寒之茂松幽夜之逸光陸士衡士
龍鴻鵠之裵回懸鼔之待槌








凡此諸
君以洪筆爲鉏耒以𥿄札爲良田以玄黙爲稼穡以
義理爲豐年以談論爲英華以忠恕爲珍寳著文章
爲錦繡藴五經爲繒帛坐謙虚爲席薦張義讓爲帷
幙
    ```
  - `08-shangyu-039` · 賞譽第八 · reviewed · reader_ready=false · surface: 士衡、陸機
    ```text
蔡司徒在洛見陸機兄弟住參佐廨中三間瓦屋士
龍住東頭士衡住西頭士龍爲人文弱可愛士衡長
七尺餘聲作鍾聲言多忼慨


    ```
  - `24-jianao-005` · 簡傲第二十四 · reviewed · reader_ready=false · surface: 陸士衡
    ```text
陸士衡初入洛咨張公所宜詣劉道真是其一陸既
徃劉尚在哀制中性嗜酒禮畢初無他言唯問東吳
有長柄壺盧卿得種來不陸兄弟殊失望乃悔徃

    ```
  - `27-jiajue-008` · 假譎第二十七 · reviewed · reader_ready=false · surface: 士衡
    ```text
陶公自上流來赴蘇峻之難令誅庾公謂必戮庾可
以謝峻


庾
欲奔竄則不可欲㑹恐見執進退無計温公勸庾詣
陶曰卿但遥拜必無它我為卿保之庾從温言詣陶
至便拜陶自起止之曰庾元規何縁拜陶士衡畢又
降就下坐陶又自要起同坐坐定庾乃引咎責躬深
相遜謝陶不覺釋然


    ```
- Liu-annotation-only presence:
  - `02-yanyu-047` · 言語第二 · reviewed · reader_ready=false · surface: 士衡
    ```text
(字士衡其先/陶氏叙曰侃)
    ```
  - `33-youhui-003` · 尤悔第三十三 · reviewed · reader_ready=false · surface: 陸機
    ```text
(也有清泉茂林吳平後陸機兄弟共/八王故事曰華亭吳由拳縣郊外墅)
    ```

### 向秀 (`person-027`)

- directly participating Stories: none currently classified; main-text appearance is retained as `mentioned` pending explicit participation review.
- reviewed linked Stories: 9; reader-ready: 0; candidate links: 0; candidate contextual Mentions: 0
- main-text presence:
  - `02-yanyu-018` · 言語第二 · reviewed · reader_ready=false · surface: 向子期、向秀、子期
    ```text
嵇中散既被誅向子期舉郡計入洛文王引進問曰

聞君有箕山之志何以在此對曰巢許狷介之士不
足多慕王大咨嗟






    ```
  - `04-wenxue-017` · 文學第四 · reviewed · reader_ready=false · surface: 向秀
    ```text
初注荘子者數十家莫能究其㫖要向秀於舊注外
為解義妙析奇致大畼玄風





唯秋
水至樂二篇未竟而秀卒秀子㓜義遂零落然猶有
别本郭象者為人薄行有儁才
見秀義不傳於世遂
竊以為已注乃自注秋水至樂二篇又易馬蹄一篇
其
    ```
  - `09-pinzao-044` · 品藻第九 · reviewed · reader_ready=false · surface: 向子期
    ```text
劉尹王長史同坐長史酒酣起舞劉尹曰阿奴今日
不復減向子期

    ```
  - `23-rendan-001` · 任誕第二十三 · reviewed · reader_ready=false · surface: 向秀
    ```text
陳留阮籍譙國嵇康河内山濤三人年皆相比康年
少亞之預此契者沛國劉伶陳留阮咸河内向秀琅
邪王戎七人常集于竹林之下肆意酣畼故世謂竹
林七賢

    ```
  - `24-jianao-003` · 簡傲第二十四 · reviewed · reader_ready=false · surface: 向子期
    ```text
鍾士季精有才理先不識嵇康鍾要于時賢儁之士
俱徃尋康康方大樹下鍜向子期為佐鼔排康揚槌
不輟傍若無人移時不交一言鍾起去康曰何所聞
而來何所見而去鍾曰聞所聞而來見所見而去





    ```
- Liu-annotation-only presence:
  - `04-wenxue-032` · 文學第四 · reviewed · reader_ready=false · surface: 向子期
    ```text
(大鵬之上九萬尺鷃之起榆/向子期郭子玄逍遥義曰夫)
    ```
  - `04-wenxue-036` · 文學第四 · reviewed · reader_ready=false · surface: 向秀
    ```text
(遁比向秀雅尚莊老二子異時風尚玄同也/勝咸味其音㫖道賢論以七沙門比竹林七賢)
    ```
  - `04-wenxue-094` · 文學第四 · reviewed · reader_ready=false · surface: 向子期
    ```text
(叔則樂彦輔王夷甫庾子嵩王安期阮千里衛叔寳/巨源向子期劉伯倫阮仲容王濬仲為竹林名士裴)
    ```
  - `17-shangshi-011` · 傷逝第十七 · reviewed · reader_ready=false · surface: 子期
    ```text
(太山子期曰善哉平/琴巍巍乎若太山莫景之/韓詩外傳曰伯牙鼓琴鍾子期聽之方鼓琴志在)
    ```

### 殷浩 (`person-028`)

- directly participating Stories: none currently classified; main-text appearance is retained as `mentioned` pending explicit participation review.
- reviewed linked Stories: 18; reader-ready: 0; candidate links: 0; candidate contextual Mentions: 0
- main-text presence:
  - `03-zhengshi-022` · 政事第三 · reviewed · reader_ready=false · surface: 殷浩
    ```text
殷浩始作揚州

劉尹行日小欲晚便使左右取襆人問其故荅
曰刺史嚴不敢夜行


    ```
  - `04-wenxue-028` · 文學第四 · reviewed · reader_ready=false · surface: 殷浩
    ```text
謝鎮西少時聞殷浩能清言故徃造之殷未過有所
通為謝標榜諸義作數百語既有佳致兼辭條豐蔚
甚足以動心駭聽謝注神傾意不覺流汗交面殷徐
語左右取手巾與謝郎拭面


    ```
  - `09-pinzao-034` · 品藻第九 · reviewed · reader_ready=false · surface: 殷浩
    ```text
撫軍問殷浩卿定何如裴逸民良久荅曰故當勝耳

    ```
  - `09-pinzao-039` · 品藻第九 · reviewed · reader_ready=false · surface: 殷浩
    ```text
人問撫軍殷浩談竟何如荅曰不能勝人差可獻酬
羣心

    ```
  - `14-rongzhi-024` · 容止第十四 · reviewed · reader_ready=false · surface: 殷浩
    ```text
庾太尉在武昌秋夜氣佳景清使吏殷浩王胡之之
徒登南樓理詠音調始遒聞函道中有屐聲甚厲定
是庾公俄而率左右十許人步來諸賢欲起避之公
徐云諸君少住老子於此處興復不淺因便據胡牀
與諸人詠謔竟坐甚得任樂後王逸少下與丞相言
及
    ```
  - `16-qixian-004` · 企羡第十六 · reviewed · reader_ready=false · surface: 殷浩
    ```text
王司州先為庾公記室叅軍後取殷浩為長史始到
庾公欲遣王使下都王自啓求住曰下官希見盛德

淵源始至猶貪與少日周旋

    ```
- Liu-annotation-only presence:
  - `01-dexing-031` · 德行第一 · reviewed · reader_ready=false · surface: 殷浩
    ```text
(勸公賣馬/語林曰殷浩)
    ```
  - `01-dexing-047` · 德行第一 · reviewed · reader_ready=false · surface: 殷浩
    ```text
(哭康伯母輙輟事流涕悲不自勝終其䘮如此謂康/居康伯母揚州刺史殷浩之妹聰明婦人也隱之毎)
    ```
  - `02-yanyu-057` · 言語第二 · reviewed · reader_ready=false · surface: 殷浩
    ```text
(陵人初為殷浩揚州别/中興書曰悅字君叔晉)
    ```
  - `02-yanyu-074` · 言語第二 · reviewed · reader_ready=false · surface: 殷浩
    ```text
(義興吳郡超授北中郎將徐州刺史以蕃屏焉中興/壻為駙馬都尉是時殷浩叅謀百揆引羨為援頻蒞)
    ```
  - `02-yanyu-080` · 言語第二 · reviewed · reader_ready=false · surface: 殷浩
    ```text
(别見/殷浩)
    ```
  - `04-wenxue-031` · 文學第四 · reviewed · reader_ready=false · surface: 殷浩
    ```text
(名一時能與劇談相抗者唯盛而已/曰孫盛善理義時中軍將軍殷浩擅)
    ```
  - `04-wenxue-043` · 文學第四 · reviewed · reader_ready=false · surface: 殷浩
    ```text
(有所不達欲訪之於遁遂邂逅不遇/髙逸沙門傳曰殷浩能言名理自以)
    ```
  - `04-wenxue-048` · 文學第四 · reviewed · reader_ready=false · surface: 殷浩
    ```text
(謝安/殷浩)
    ```
  - `08-shangyu-090` · 賞譽第八 · reviewed · reader_ready=false · surface: 殷浩
    ```text
(思理幼為舅殷浩所稱/續晉陽秋曰康伯清和有)
    ```
  - `08-shangyu-117` · 賞譽第八 · reviewed · reader_ready=false · surface: 殷浩
    ```text
(也阿源殷浩也/嘉賔郄超小字)
    ```
  - `09-pinzao-038` · 品藻第九 · reviewed · reader_ready=false · surface: 殷浩
    ```text
(引殷浩爲揚州欲以抗/續晉陽秋曰簡文輔政)
    ```
  - `23-rendan-037` · 任誕第二十三 · reviewed · reader_ready=false · surface: 殷浩
    ```text
(名女正適謝尚/女皇適殷浩小妹)
    ```

### 卞壼 (`person-029`)

- directly participating Stories: none currently classified; main-text appearance is retained as `mentioned` pending explicit participation review.
- reviewed linked Stories: 3; reader-ready: 0; candidate links: 0; candidate contextual Mentions: 0
- main-text presence:
  - `08-shangyu-054` · 賞譽第八 · reviewed · reader_ready=false · surface: 卞望之
    ```text
王丞相云刁玄亮之察察戴若思之巖巖
卞望之
之峯距





    ```
  - `09-pinzao-024` · 品藻第九 · reviewed · reader_ready=false · surface: 卞望之
    ```text
卞望之云郗公體中有三反方於事上好下佞巳一
反治身清貞大脩計校二反自好讀書憎人學問三
反



    ```
- Liu-annotation-only presence:
  - `24-jianao-007` · 簡傲第二十四 · reviewed · reader_ready=false · surface: 卞望之
    ```text
(偃伏悟言神解見尚書令卞望之便/髙坐傳曰王公曽詣和上和上解帶)
    ```

### 王恭 (`person-030`)

- directly participating Stories: none currently classified; main-text appearance is retained as `mentioned` pending explicit participation review.
- reviewed linked Stories: 32; reader-ready: 0; candidate links: 0; candidate contextual Mentions: 0
- main-text presence:
  - `02-yanyu-086` · 言語第二 · reviewed · reader_ready=false · surface: 王孝伯
    ```text
王子敬語王孝伯曰羊叔子自復佳耳然亦何與人
事

故不如
銅雀臺上妓


    ```
  - `02-yanyu-100` · 言語第二 · reviewed · reader_ready=false · surface: 孝伯、王孝伯、王恭
    ```text
謝景重女適王孝伯兒二門公甚相愛美
謝為太傅長史被彈王即取作長史帶晉陵
郡太傅巳構嫌孝伯不欲使其得謝還取作咨議外
示縶維而實以乖閒之及孝伯敗後太傅繞東府城
行散
僚屬悉在南門要望候拜時謂謝曰王寗異謀
云是卿為其計謝曾無懼色斂笏對曰樂
彦輔有言豈以五男易一女太傅善其對因
    ```
  - `04-wenxue-101` · 文學第四 · reviewed · reader_ready=false · surface: 孝伯、王孝伯
    ```text
王孝伯在京行散至其弟王睹户前
問古詩中何句為最睹思未
荅孝伯詠所遇無故物焉得不速老此句為佳

    ```
  - `04-wenxue-102` · 文學第四 · reviewed · reader_ready=false · surface: 王孝伯
    ```text
桓玄嘗登江陵城南樓云我今欲為王孝伯作誄因
吟嘯良乆隨而下筆一坐之間誄以之成





    ```
  - `05-fangzheng-063` · 方正第五 · reviewed · reader_ready=false · surface: 王恭
    ```text
王恭欲請江盧奴爲長史晨往詣江江猶在帳中王
坐不敢卽言良久乃得及江不應

直喚人取酒自飮一盌又不與王王且笑且言
那得獨飮江云卿亦復須邪更使酌與王王飮酒畢
因得自解去未出戸江歎曰人自量固爲
    ```
  - `06-yaliang-041` · 雅量第六 · reviewed · reader_ready=false · surface: 王恭
    ```text
殷荆州有所識作賦是束晳慢戲之流


殷甚以爲
有才語王恭適見新文甚可觀便於手巾函中出之
王讀殷笑之不自勝王看竟既不笑亦不言好惡但

以如意帖之而巳殷悵然自失

    ```
  - `06-yaliang-042` · 雅量第六 · reviewed · reader_ready=false · surface: 孝伯
    ```text
不眄唯脚委几上詠矚自若謝
與王叙寒温數語畢還與羊談賞王方悟其竒乃合
共語須臾食下二王都不得餐唯屬羊不暇羊不大
應對之而盛進食食畢便退遂苦相留羊義不住直
云向者不得從命中國尚虚二王是孝伯兩弟

    ```
  - `07-shijian-026` · 識鑒第七 · reviewed · reader_ready=false · surface: 王恭
    ```text
王恭隨父在會稽王大自都來拜墓恭暫

往墓下看之二人素善遂十餘日方還父問恭何故
多日對曰與阿大語蟬連不得歸因語之曰恐阿大
非爾之友終乖愛好果如其言

    ```
  - `08-shangyu-143` · 賞譽第八 · reviewed · reader_ready=false · surface: 王孝伯
    ```text
謝公語王孝伯君家藍田舉體無常人事


    ```
  - `08-shangyu-153` · 賞譽第八 · reviewed · reader_ready=false · surface: 王恭
    ```text
王恭始與王建武甚有情後遇袁恱之間遂致疑隟





然每至興㑹故有相思時恭嘗行散至京口射堂
于時清露晨流新桐初引恭目之曰王大故自濯濯

    ```
  - `08-shangyu-154` · 賞譽第八 · reviewed · reader_ready=false · surface: 孝伯
    ```text
司馬太傅爲二王目曰孝伯亭亭直上阿大羅羅清
踈

    ```
  - `08-shangyu-155` · 賞譽第八 · reviewed · reader_ready=false · surface: 孝伯、王恭
    ```text
王恭有清辭簡㫖能叙說而讀書少頗有重出
有人道孝伯常有新意不覺爲煩

    ```
  - `09-pinzao-073` · 品藻第九 · reviewed · reader_ready=false · surface: 王孝伯
    ```text
謝太傅謂王孝伯劉尹亦奇自知然不言勝長史

    ```
  - `09-pinzao-076` · 品藻第九 · reviewed · reader_ready=false · surface: 王孝伯
    ```text
王孝伯問謝太傅林公何如長史太傅曰長史韶興
問何如劉尹謝曰噫劉尹秀王曰若如公言並不如
此二人邪謝云身意正爾也

    ```
  - `09-pinzao-078` · 品藻第九 · reviewed · reader_ready=false · surface: 孝伯
    ```text
謝公語孝伯君祖比劉尹故爲得逮孝伯云劉尹非

不能逮直不逮

    ```
  - `09-pinzao-085` · 品藻第九 · reviewed · reader_ready=false · surface: 王孝伯
    ```text
王孝伯問謝公林公何如右軍謝曰右軍勝林公
林公在司州前亦貴徹

    ```
  - `14-rongzhi-039` · 容止第十四 · reviewed · reader_ready=false · surface: 王恭
    ```text
有人歎王恭形茂者云濯濯如春月柳

    ```
  - `16-qixian-006` · 企羡第十六 · reviewed · reader_ready=false · surface: 王恭
    ```text
孟昶未逹時家在京口
嘗見王恭乘
高輿被鶴氅裘于時微雪昶於籬間窺之歎曰此真
神仙中人

    ```
  - `17-shangshi-017` · 傷逝第十七 · reviewed · reader_ready=false · surface: 王孝伯、王恭
    ```text
孝武山陵夕王孝伯入臨告其諸弟曰雖榱桷惟新
便自有黍離之哀


    ```
  - `23-rendan-051` · 任誕第二十三 · reviewed · reader_ready=false · surface: 王孝伯
    ```text
王孝伯問王大阮籍何如司馬相如王大曰阮籍胷
中壘塊故須酒澆之

    ```
  - `23-rendan-053` · 任誕第二十三 · reviewed · reader_ready=false · surface: 王孝伯
    ```text
王孝伯言名士不必須竒才但使常得無事痛飲酒
熟讀離騷便可稱名士

    ```
  - `25-paidiao-054` · 排調第二十五 · reviewed · reader_ready=false · surface: 孝伯、王孝伯
    ```text
簡文在殿上行右軍與孫興公在後右軍指簡文語
孫曰此噉名客簡文顧曰天下自有利齒兒後王光
禄作㑹稽謝車騎出曲阿祖之王孝伯罷祕

書丞在坐謝言及此事因視孝伯曰王丞齒似不鈍
王曰不鈍頗亦驗

    ```
  - `26-qingdi-022` · 輕詆第二十六 · reviewed · reader_ready=false · surface: 王孝伯
    ```text
孫長樂作王長史誄云余與夫子交非勢利心猶澄
水同此玄味王孝伯見曰才
士不遜亡祖何至與此人周旋

    ```
  - `31-fenjuan-007` · 忿狷第三十一 · reviewed · reader_ready=false · surface: 王恭
    ```text
王大王恭甞俱在何僕射坐
恭時為丹陽尹大始拜荆州
訖將乖
之際大勸恭酒恭不為飲大逼彊之轉苦便各以帬
帶繞手恭府近千人悉呼入齋大左右雖少亦命前
意便欲相殺何僕射無計因起排坐二人之間方得
分散所
    ```
  - `36-chouxi-006` · 仇隟第三十六 · reviewed · reader_ready=false · surface: 孝伯、王恭
    ```text
王東亭與孝伯語後漸異孝伯謂東亭曰卿便不可
復測荅曰王陵廷争陳平從黙但問克終云何耳





    ```
  - `36-chouxi-007` · 仇隟第三十六 · reviewed · reader_ready=false · surface: 王孝伯、王恭
    ```text
王孝伯死縣其首於大桁司馬太傅命駕出至標所
孰視首曰卿何故趣欲殺我邪



    ```
- Liu-annotation-only presence:
  - `01-dexing-042` · 德行第一 · reviewed · reader_ready=false · surface: 王恭
    ```text
(遽奔臨川為玄所得玄簒位遷尚書左僕射/楊佺期舉兵以應王恭乘流奄至愉無防惶)
    ```
  - `01-dexing-044` · 德行第一 · reviewed · reader_ready=false · surface: 孝伯
    ```text
(人祖父濛司徒左長史風流標望父/周祗隆安記曰恭字孝伯太原晉陽)
    ```
  - `04-wenxue-104` · 文學第四 · reviewed · reader_ready=false · surface: 王恭
    ```text
(軍符堅之役以驍猛成功及平王恭轉徐州刺史桓/以將顯父遁征虜将軍牢之沈毅多計數為謝玄叅)
    ```
  - `10-guizhen-026` · 規箴第十 · reviewed · reader_ready=false · surface: 王恭
    ```text
(佞邪親幸王珣王恭惡國寳與緒亂政與殷仲堪克/延父乂撫軍晉安帝紀曰緒爲㑹稽王從事中郎以)
    ```
  - `23-rendan-054` · 任誕第二十三 · reviewed · reader_ready=false · surface: 王恭
    ```text
(長史周祗隆安記曰初王恭將唱義使喻三吳廞居/王氏譜曰廞字伯輿琅邪人父薈衛將軍廞歷司徒)
    ```
  - `32-chanxian-003` · 讒險第三十二 · reviewed · reader_ready=false · surface: 王恭
    ```text
(見禮至於親幸莫及雅者上毎置酒燕集或召雅未/雅之為侍中孝武甚信而重之王珣王恭特以地望)
    ```

### 朱伺 (`person-031`)

- directly participating Stories: none currently classified; main-text appearance is retained as `mentioned` pending explicit participation review.
- reviewed linked Stories: 9; reader-ready: 0; candidate links: 0; candidate contextual Mentions: 0
- main-text presence:
  - `02-yanyu-106` · 言語第二 · reviewed · reader_ready=false · surface: 仲文
    ```text
桓玄既簒位後御牀微陷羣臣失色侍中殷仲文進
曰


當由聖德淵重厚地所以不

能載時人善之

    ```
  - `04-wenxue-099` · 文學第四 · reviewed · reader_ready=false · surface: 仲文
    ```text
殷仲文天才宏贍而讀書不甚
廣博亮歎曰若使殷仲文讀書半袁豹

才不減班固



    ```
  - `08-shangyu-156` · 賞譽第八 · reviewed · reader_ready=false · surface: 仲文
    ```text
殷仲堪䘮後桓玄問仲文卿家仲堪定是何似人仲
文曰雖不能休明一世足以映徹九泉



    ```
  - `09-pinzao-045` · 品藻第九 · reviewed · reader_ready=false · surface: 仲文
    ```text
桓公問孔西陽安石何如仲文孔思未對反

問公曰何如荅曰安石居然不可陵踐其處故乃勝
也

    ```
  - `09-pinzao-088` · 品藻第九 · reviewed · reader_ready=false · surface: 仲文
    ```text
舊以桓謙比殷仲文
桓玄時仲文入桓於庭中望見之謂同坐
曰我家中軍那得及此也


    ```
  - `25-paidiao-065` · 排調第二十五 · reviewed · reader_ready=false · surface: 仲文
    ```text
桓玄素輕桓崖崖在京下有好桃玄連就求之遂不
得佳者玄與殷仲文
書以為嗤笑曰德之休明肅慎貢其楛矢如其不爾
籬壁間物亦不可得也





    ```
  - `28-chumian-008` · 黜免第二十八 · reviewed · reader_ready=false · surface: 仲文
    ```text
桓玄敗後殷仲文還為太司馬咨議意似二三非復
往日大司馬府㕔前有一老槐甚扶踈殷因月朔與
衆在㕔視槐良久嘆曰槐樹婆娑無復生意




    ```
  - `28-chumian-009` · 黜免第二十八 · reviewed · reader_ready=false · surface: 仲文
    ```text
殷仲文既素有名望自謂必當阿衡朝政忽作東陽
太守意甚不平
及之郡至富陽慨然嘆曰看此山川形勢
當復出一孫伯符

    ```
- Liu-annotation-only presence:
  - `02-yanyu-013` · 言語第二 · reviewed · reader_ready=false · surface: 仲文
    ```text
(元仲文帝太子以其/魏末傳曰帝諱叡字)
    ```

### 孟陋 (`person-032`)

- directly participating Stories: none currently classified; main-text appearance is retained as `mentioned` pending explicit participation review.
- reviewed linked Stories: 1; reader-ready: 0; candidate links: 0; candidate contextual Mentions: 0
- main-text presence:
  - `18-qiyi-010` · 棲逸第十八 · reviewed · reader_ready=false · surface: 少孤
    ```text
孟萬年及弟少孤居武昌陽新縣萬年遊宦有盛名
當世少孤未嘗出京邑人士思欲見之乃遣信報少
孤云兄病篤狼狽至都時賢見之者莫不嗟重因相



    ```
- Liu-annotation-only presence:
  - none

### 孫恩 (`person-033`)

- directly participating Stories: none currently classified; main-text appearance is retained as `mentioned` pending explicit participation review.
- reviewed linked Stories: 4; reader-ready: 0; candidate links: 0; candidate contextual Mentions: 0
- main-text presence:
  - `01-dexing-045` · 德行第一 · reviewed · reader_ready=false · surface: 孫恩、靈秀
    ```text
呉郡陳遺家至孝母好食鐺底焦飯遺作郡主簿
恒裝一囊每煮食輙貯録焦飯歸以遺母後值孫恩
賊出吳郡
袁府君即日便征
遺己聚歛得數斗焦飯未展歸家遂帶以從軍戰於
滬瀆敗軍人潰散逃走山澤皆多饑死遺獨以焦飯

得活時人以為純孝之報也

    ```
- Liu-annotation-only presence:
  - `02-yanyu-071` · 言語第二 · reviewed · reader_ready=false · surface: 孫恩
    ```text
(曰凝之事五斗米道孫恩之攻㑹稽凝之謂民吏曰/第二子也歴江州刺史左將軍㑹稽内史晉安帝紀)
    ```
  - `17-shangshi-015` · 傷逝第十七 · reviewed · reader_ready=false · surface: 孫恩
    ```text
(率有大度為孫恩所害贈侍中司空/末婢謝琰小字琰字瑗度安少子開)
    ```
  - `25-paidiao-060` · 排調第二十五 · reviewed · reader_ready=false · surface: 孫恩
    ```text
(秘書監吳國内史孫恩作亂見害初帝為晉陵公主/松陳郡人祖喬益州刺史父方平義興太守山松歷)
    ```

### 伏滔 (`person-034`)

- directly participating Stories: none currently classified; main-text appearance is retained as `mentioned` pending explicit participation review.
- reviewed linked Stories: 7; reader-ready: 0; candidate links: 0; candidate contextual Mentions: 0
- main-text presence:
  - `22-chongli-002` · 寵禮第二十二 · reviewed · reader_ready=false · surface: 伏滔
    ```text
桓宣武嘗請叅佐入宿袁宏伏滔相次而至蒞名府
中復有袁叅軍彦伯疑焉令傳教更質傳教曰叅軍
是袁伏之袁復何所疑

    ```
  - `22-chongli-005` · 寵禮第二十二 · reviewed · reader_ready=false · surface: 伏滔
    ```text
孝武在西堂㑹伏滔預坐還下車呼其兒
語之曰百人高㑹臨坐未得他語
先問伏滔何在在此不此故未易得爲人作父如此
何如

    ```
  - `26-qingdi-012` · 輕詆第二十六 · reviewed · reader_ready=false · surface: 伏滔
    ```text
袁虎伏滔同在桓公府桓公毎遊燕輙命袁伏袁甚
耻之恒歎曰公之厚意未足以榮國士與伏滔比肩
亦何辱如之

    ```
- Liu-annotation-only presence:
  - `02-yanyu-072` · 言語第二 · reviewed · reader_ready=false · surface: 伏滔、度平
    ```text
(人少有才學舉秀才大司馬桓温叅軍領大著作掌/將徐兖二州刺史中興書曰伏滔字玄度平昌安丘)
    ```
  - `04-wenxue-092` · 文學第四 · reviewed · reader_ready=false · surface: 伏滔
    ```text
(於天下於此改韻云此韻所詠慨深千載今於天下/宏嘗與王珣伏滔同侍温坐温令滔讀其賦至致傷)
    ```
  - `04-wenxue-097` · 文學第四 · reviewed · reader_ready=false · surface: 伏滔
    ```text
(宏善苦諌之宏笑而不荅滔宻以啓温温甚忿以宏/南州宏語衆云我决不及桓宣城時伏滔在温府與)
    ```
  - `26-qingdi-020` · 輕詆第二十六 · reviewed · reader_ready=false · surface: 伏滔
    ```text
(賦叙曰余/伏滔長笛)
    ```

### 和嶠 (`person-035`)

- directly participating Stories: none currently classified; main-text appearance is retained as `mentioned` pending explicit participation review.
- reviewed linked Stories: 12; reader-ready: 0; candidate links: 0; candidate contextual Mentions: 0
- main-text presence:
  - `01-dexing-017` · 德行第一 · reviewed · reader_ready=false · surface: 和嶠
    ```text
王戎和嶠同時遭大喪俱以孝稱王雞骨支牀和哭
泣備禮


武帝謂劉仲雄曰


卿數省王和
不聞和哀苦過禮使人憂之仲雄曰和嶠雖備禮神
氣不損王戎雖不備禮而哀毁骨立臣以和嶠生孝
王戎死孝陛下不應憂嶠而應憂戎


    ```
  - `03-zhengshi-005` · 政事第三 · reviewed · reader_ready=false · surface: 和嶠
    ```text
山公以器重朝望年踰七十猶知管時任





貴勝年少若和裴王之徒並共宗詠有署
閣柱曰閣東有大牛和嶠鞅裴楷鞦王濟剔嬲不得
休
或云潘尼作之


    ```
  - `05-fangzheng-009` · 方正第五 · reviewed · reader_ready=false · surface: 和嶠、長輿
    ```text
和嶠爲武帝所親重語嶠曰東官頃似更成進卿試
往看還問何如荅云皇太子聖質如初









    ```
  - `05-fangzheng-011` · 方正第五 · reviewed · reader_ready=false · surface: 和嶠
    ```text
武帝語和嶠曰我欲先痛罵王武子然後爵之嶠曰
武子儁爽恐不可屈帝遂召武子苦責之因曰知愧
不

武子曰尺布斗粟之謠常爲陛下
耻之

它人能令踈親臣不能使親踈以此愧陛下


    ```
  - `05-fangzheng-012` · 方正第五 · reviewed · reader_ready=false · surface: 和長輿、長輿
    ```text
杜預之荆州頓七里橋朝士悉祖


預少賤好
豪侠不爲物所許楊濟既名氏雄俊不堪不坐而去
須臾和長輿
來問楊右衛何在客曰向來不坐而去長輿曰必大
夏門下盤馬往大夏門果大閲騎長輿抱內車共載
歸坐如初

    ```
  - `05-fangzheng-027` · 方正第五 · reviewed · reader_ready=false · surface: 和長輿
    ```text
爲吏部尚書在省內夜疾危急時刁玄亮爲
尚書令營救備親好之至良乆小損

明旦報仲智仲智狼狽來始入戸刁下牀

對之大泣説伯仁昨危急之狀仲智手批之刁爲辟
易於戸側既前都不問病直云君在中朝與和長輿
齊名那與佞人刁協有情逕便出

    ```
  - `08-shangyu-015` · 賞譽第八 · reviewed · reader_ready=false · surface: 和嶠
    ```text
庾子嵩目和嶠森森如千丈松雖磊砢有節目施之
大厦有棟梁之用


    ```
  - `09-pinzao-016` · 品藻第九 · reviewed · reader_ready=false · surface: 和嶠、長輿
    ```text
人問丞相周侯何如和嶠荅曰長輿嵯櫱


    ```
  - `17-shangshi-005` · 傷逝第十七 · reviewed · reader_ready=false · surface: 和長輿
    ```text
有人哭和長輿曰峨峨若千丈松崩

    ```
  - `23-rendan-016` · 任誕第二十三 · reviewed · reader_ready=false · surface: 和嶠
    ```text
任愷既失權勢不復自檢括或謂和嶠曰卿何以坐
視元裒敗而不救和曰元裒如北夏門拉攞自欲壞
非一木所能支


    ```
  - `29-jianshe-001` · 儉嗇第二十九 · reviewed · reader_ready=false · surface: 和嶠
    ```text
和嶠性至儉家有好李王武子求之與不過數十王
武子因其上直率將少年能食之者持斧詣園飽共
噉畢伐之送一車枝與和公問曰何如君李和既得
唯笑而已



    ```
- Liu-annotation-only presence:
  - `20-shujie-004` · 術解第二十 · reviewed · reader_ready=false · surface: 和長輿
    ```text
(和長輿有錢癖武帝問杜預卿有何癖對曰臣有左/曰武子性愛馬亦甚别之故杜預道王武子有馬癖)
    ```

### 王祥 (`person-036`)

- directly participating Stories: none currently classified; main-text appearance is retained as `mentioned` pending explicit participation review.
- reviewed linked Stories: 3; reader-ready: 0; candidate links: 0; candidate contextual Mentions: 0
- main-text presence:
  - `01-dexing-014` · 德行第一 · reviewed · reader_ready=false · surface: 王祥
    ```text
王祥事後母朱夫人甚謹



家有一李樹結子殊好母恒使守之時風雨
忽至祥抱樹而泣
祥嘗在别牀眠母自徃闇斫
之值祥私起空斫得被既還知母憾之不巳因跪前

請死母於是感悟愛之如己子


    ```
  - `09-pinzao-006` · 品藻第九 · reviewed · reader_ready=false · surface: 王祥
    ```text
正始中人士比論以五荀方五陳荀淑方陳寔荀靖
方陳諶

荀爽方陳紀荀彧方陳群


荀顗方陳泰

又以八裴方八王裴徽方王祥裴楷
方王夷甫裴康方王綏
裴綽方王澄裴
瓉方王敦裴遐方王導裴
頠方王戎裴邈方王玄

    ```
- Liu-annotation-only presence:
  - `24-jianao-001` · 簡傲第二十四 · reviewed · reader_ready=false · surface: 王祥
    ```text
(盡禮唯王祥長揖不拜/王司徒何曽與朝臣皆)
    ```

### 石苞 (`person-037`)

- directly participating Stories: none currently classified; main-text appearance is retained as `mentioned` pending explicit participation review.
- reviewed linked Stories: 0; reader-ready: 0; candidate links: 1; candidate contextual Mentions: 1
- main-text presence:
  - `23-rendan-012` · 任誕第二十三 · candidate · reader_ready=false · surface: explicit annotation evidence
    ```text
諸阮皆能飲酒仲容至宗人閒共集不復用常桮斟
酌以大&KR1805;盛酒圍坐相向大酌時有羣豬來飲直接
去上便共飲之

    ```
- Liu-annotation-only presence:
  - none

### 羊祜 (`person-038`)

- directly participating Stories: none currently classified; main-text appearance is retained as `mentioned` pending explicit participation review.
- reviewed linked Stories: 8; reader-ready: 0; candidate links: 0; candidate contextual Mentions: 0
- main-text presence:
  - `02-yanyu-086` · 言語第二 · reviewed · reader_ready=false · surface: 叔子、羊叔子、羊祜
    ```text
王子敬語王孝伯曰羊叔子自復佳耳然亦何與人
事

故不如
銅雀臺上妓


    ```
  - `03-zhengshi-006` · 政事第三 · reviewed · reader_ready=false · surface: 羊祜
    ```text
賈充初定律令

與羊祜共咨太傅鄭冲
冲曰臯陶

嚴明之㫖非僕闇懦所探羊曰上意欲令小加弘潤
冲乃粗下意


    ```
  - `07-shijian-005` · 識鑒第七 · reviewed · reader_ready=false · surface: 羊祜
    ```text
王夷甫父乂爲平北將軍有公事使行人論不得時
夷甫在京師命駕見僕射羊祜尚書山濤夷甫時總
角姿才秀異叙致既快事加有理濤甚奇之既退看

之不輟乃嘆曰生兒不當如王夷甫邪羊祜曰亂天
下者必此子也




    ```
  - `08-shangyu-009` · 賞譽第八 · reviewed · reader_ready=false · surface: 叔子、羊叔子
    ```text
羊公還洛郭弈爲野王令
羊至界遣人要之郭便自往既見嘆曰
羊叔子何必減郭太業復往羊許小悉還又歎曰羊
叔子去人逺矣羊既去郭送之彌日一舉數百里遂
以出境免官復嘆曰羊叔子何必減顔子


    ```
  - `09-pinzao-051` · 品藻第九 · reviewed · reader_ready=false · surface: 羊叔子、羊祜
    ```text
世目殷中軍思緯淹通比羊叔子


    ```
  - `09-pinzao-066` · 品藻第九 · reviewed · reader_ready=false · surface: 叔子
    ```text
蔡叔子云韓康伯雖無骨榦然亦膚立

    ```
  - `20-shujie-003` · 術解第二十 · reviewed · reader_ready=false · surface: 羊祜
    ```text
人有相羊祜父墓後應出受命君祜惡其言遂掘斷
墓後以壞其勢相者立視之曰猶應出折臂三公俄
而祜墜馬折臂位果至公



    ```
  - `25-paidiao-047` · 排調第二十五 · reviewed · reader_ready=false · surface: 羊叔子
    ```text
劉遵祖少為殷中軍所知稱之於庾公庾公甚忻然
便取為佐既見坐之獨榻上與語劉爾日殊不稱庾
小失望遂名之為羊公鶴昔羊叔子有鶴善舞嘗向
客稱之客試使驅來氃氋而不肻舞故稱比之


    ```
- Liu-annotation-only presence:
  - none

### 杜預 (`person-039`)

- directly participating Stories: none currently classified; main-text appearance is retained as `mentioned` pending explicit participation review.
- reviewed linked Stories: 9; reader-ready: 0; candidate links: 0; candidate contextual Mentions: 0
- main-text presence:
  - `05-fangzheng-012` · 方正第五 · reviewed · reader_ready=false · surface: 元凱、杜預
    ```text
杜預之荆州頓七里橋朝士悉祖


預少賤好
豪侠不爲物所許楊濟既名氏雄俊不堪不坐而去
須臾和長輿
來問楊右衛何在客曰向來不坐而去長輿曰必大
夏門下盤馬往大夏門果大閲騎長輿抱內車共載
歸坐
    ```
  - `05-fangzheng-013` · 方正第五 · reviewed · reader_ready=false · surface: 杜預
    ```text
杜預拜鎮南將軍朝士悉至皆在連榻坐




    ```
- Liu-annotation-only presence:
  - `02-yanyu-068` · 言語第二 · reviewed · reader_ready=false · surface: 杜預
    ```text
(三犧皆用之矣其音云問之而信杜預注/春秋傳曰介葛盧來朝魯聞牛鳴曰是生)
    ```
  - `02-yanyu-079` · 言語第二 · reviewed · reader_ready=false · surface: 杜預
    ```text
(舟杜預曰示必死/秦伯伐晉濟河焚)
    ```
  - `05-fangzheng-024` · 方正第五 · reviewed · reader_ready=false · surface: 杜預
    ```text
(栢大木也薰香草蕕臭草/杜預左傳注曰培塿小阜松)
    ```
  - `05-fangzheng-059` · 方正第五 · reviewed · reader_ready=false · surface: 杜預
    ```text
(南風不競多死聲楚必無功杜預曰歌者吹/春秋傳曰楚伐鄭師曠曰不害吾驟歌南風)
    ```
  - `10-guizhen-006` · 規箴第十 · reviewed · reader_ready=false · surface: 元凱
    ```text
(之相重華宣慈惠和仁義之至也周公之翼成王坐/輅心過草木注情葵藿敢不盡忠唯察之爾昔元凱)
    ```
  - `20-shujie-004` · 術解第二十 · reviewed · reader_ready=false · surface: 杜預
    ```text
(和長輿有錢癖武帝問杜預卿有何癖對曰臣有左/曰武子性愛馬亦甚别之故杜預道王武子有馬癖)
    ```
  - `23-rendan-045` · 任誕第二十三 · reviewed · reader_ready=false · surface: 杜預
    ```text
(勃以吹簫樂喪然則挽歌之來乆矣非始起於田橫/杜預曰虞殯送葬歌示必死也史記絳侯世家曰周)
    ```

### 張華 (`person-040`)

- directly participating Stories: none currently classified; main-text appearance is retained as `mentioned` pending explicit participation review.
- reviewed linked Stories: 11; reader-ready: 0; candidate links: 0; candidate contextual Mentions: 0
- main-text presence:
  - `01-dexing-012` · 德行第一 · reviewed · reader_ready=false · surface: 張華
    ```text
王朗每以識度推華歆歆蜡日



嘗集子姪燕
飲王亦學之有人向張華說此事張曰王之學華皆
是形骸之外去之所以更逺


    ```
  - `02-yanyu-023` · 言語第二 · reviewed · reader_ready=false · surface: 張茂先
    ```text
諸名士共至洛水戲
還樂令問王夷甫曰今日戲樂乎

王曰裴僕射善談名理混混有雅致

張茂先論史漢靡靡可聽
我與王
安豐說延陵子房亦超超玄箸



    ```
  - `08-shangyu-019` · 賞譽第八 · reviewed · reader_ready=false · surface: 張華
    ```text
張華見禇陶語陸平原曰君兄弟龍躍雲津顧彦先
鳳鳴朝陽謂東南之寳巳盡不意復見禇生陸曰公
未覩不鳴不躍者耳






    ```
  - `09-pinzao-008` · 品藻第九 · reviewed · reader_ready=false · surface: 張茂先
    ```text
劉令言始入洛
見諸名士而歎曰王夷甫太解明樂彦輔我所敬
張茂先我所不解周弘武巧於用短
杜方叔拙於用長




    ```
  - `25-paidiao-007` · 排調第二十五 · reviewed · reader_ready=false · surface: 張茂先、張華
    ```text
頭責秦子羽云子曽不如太原温顒潁川荀㝢

范陽張華士卿劉許
義陽鄒湛
河南鄭詡
此數子者或謇喫無宫商或尫陋希
言語或淹伊多姿態或讙譁少智諝或口如含膠飴
或頭如巾韲杵

而猶以文采可觀意思詳
序攀龍附鳯並登天府











    ```
  - `25-paidiao-009` · 排調第二十五 · reviewed · reader_ready=false · surface: 張茂先、張華
    ```text
荀鳴鶴陸士龍二人未相識俱㑹張茂先坐張令其
語以其並有大才可勿作常語陸舉手曰雲間陸士
龍荀荅曰日下荀鳴鶴陸曰既開青雲覩白雉何不
張爾弓布爾矢荀荅曰本謂雲龍騤騤定是山鹿野
麋獸弱弩彊是以發遲張乃撫掌大笑



    ```
- Liu-annotation-only presence:
  - `02-yanyu-026` · 言語第二 · reviewed · reader_ready=false · surface: 張華
    ```text
(傳曰博學善屬文非禮不動入晉仕著作郎至平原/才司空張華見而說之曰平吳之利在獲二儁機别)
    ```
  - `02-yanyu-047` · 言語第二 · reviewed · reader_ready=false · surface: 張華
    ```text
(廉入洛司空張華見而謂曰後來匡主寧民君其人/鄱陽人後徙尋陽侃少有逺槩綱維宇宙之志察孝)
    ```
  - `04-wenxue-068` · 文學第四 · reviewed · reader_ready=false · surface: 張華
    ```text
(長博覽名文遍閱百家司空張華辟爲祭酒賈謐舉/練爲殿中御史思蚤䘮母雍憐之不甚教其書學及)
    ```
  - `04-wenxue-084` · 文學第四 · reviewed · reader_ready=false · surface: 張華
    ```text
(文司空張華見其/文章傳曰機善屬)
    ```
  - `06-yaliang-041` · 雅量第六 · reviewed · reader_ready=false · surface: 張華
    ```text
(枚上兩行科斗書司空張華以問晳晳曰此明帝顯/多識問無不對元康中有人自嵩高山下得竹簡一)
    ```

### 賈充 (`person-041`)

- directly participating Stories: none currently classified; main-text appearance is retained as `mentioned` pending explicit participation review.
- reviewed linked Stories: 9; reader-ready: 0; candidate links: 0; candidate contextual Mentions: 0
- main-text presence:
  - `03-zhengshi-006` · 政事第三 · reviewed · reader_ready=false · surface: 公閭、賈充
    ```text
賈充初定律令

與羊祜共咨太傅鄭冲
冲曰臯陶

嚴明之㫖非僕闇懦所探羊曰上意欲令小加弘潤
冲乃粗下意


    ```
  - `19-xianyuan-013` · 賢媛第十九 · reviewed · reader_ready=false · surface: 賈充
    ```text
賈充前婦是李豐女豐被誅離婚徙邉
後遇赦得還充先已取郭配女
武帝特聽置左右夫人李氏别住外不肯還
充舍
郭氏語充
欲就省李充曰彼剛介有才氣卿徃不如不去
郭氏於是盛威儀多將侍婢既至入户李
氏
    ```
  - `19-xianyuan-014` · 賢媛第十九 · reviewed · reader_ready=false · surface: 賈充
    ```text
賈充妻李氏作女訓行於世李氏女齊獻王妃郭氏
女惠帝后充卒李郭女各欲令其母合葬經年不決
賈后廢李氏乃祔葬遂定



    ```
  - `35-huoni-003` · 惑溺第三十五 · reviewed · reader_ready=false · surface: 公閭、賈公閭
    ```text
賈公閭後妻郭氏

酷妒有男兒名黎民生載周充自外還乳母抱兒在
中庭兒見充喜踊充就乳母手中嗚之郭遥望見謂
充愛乳母即殺之兒悲思啼泣不飲它乳遂死郭後
終無子




    ```
  - `35-huoni-005` · 惑溺第三十五 · reviewed · reader_ready=false · surface: 賈充
    ```text
韓壽美姿容賈充辟以為掾充毎聚㑹賈女於青璅
中看見壽說之恒懷存想發於吟詠後婢往壽家具
述如此并言女光麗夀聞之心動遂請婢潜修音問
及期往宿夀蹻捷絶人踰牆而入家中莫知

自是充覺女盛自拂拭說畼有異於常
    ```
- Liu-annotation-only presence:
  - `03-zhengshi-007` · 政事第三 · reviewed · reader_ready=false · surface: 賈充
    ```text
(常陸乂兄也性髙明而率至為賈充所/晉諸公賛曰亮字長興河内野王人太)
    ```
  - `05-fangzheng-008` · 方正第五 · reviewed · reader_ready=false · surface: 公閭、賈充
    ```text
(可以自明也昭曰公閭不可得殺也卿更思餘計泰/垂美於後一旦有殺君之事不亦惜乎速斬賈充猶)
    ```
  - `05-fangzheng-009` · 方正第五 · reviewed · reader_ready=false · surface: 賈充
    ```text
(所知每向世祖稱之歷尚書太子少傅干寳晉紀曰/南西平人父逌太常知名嶠少以雅量稱深爲賈充)
    ```
  - `10-guizhen-007` · 規箴第十 · reviewed · reader_ready=false · surface: 賈充
    ```text
(語妃曰衛瓘老奴㡬敗汝家妃由是怨瓘後遂誅之/之弘具草奏令太子書呈帝大說以示瓘於是賈充)
    ```

### 王濬 (`person-042`)

- directly participating Stories: none currently classified; main-text appearance is retained as `mentioned` pending explicit participation review.
- reviewed linked Stories: 1; reader-ready: 0; candidate links: 0; candidate contextual Mentions: 0
- main-text presence:
  - none
- Liu-annotation-only presence:
  - `04-wenxue-094` · 文學第四 · reviewed · reader_ready=false · surface: 王濬
    ```text
(叔則樂彦輔王夷甫庾子嵩王安期阮千里衛叔寳/巨源向子期劉伯倫阮仲容王濬仲為竹林名士裴)
    ```

### 山濤 (`person-043`)

- directly participating Stories: none currently classified; main-text appearance is retained as `mentioned` pending explicit participation review.
- reviewed linked Stories: 17; reader-ready: 0; candidate links: 0; candidate contextual Mentions: 0
- main-text presence:
  - `02-yanyu-078` · 言語第二 · reviewed · reader_ready=false · surface: 山濤
    ```text
晉武帝每餉山濤恒少謝太傅以問子弟車騎
荅曰當由欲者不多而使與者忘少



    ```
  - `07-shijian-004` · 識鑒第七 · reviewed · reader_ready=false · surface: 山濤
    ```text
幸悉
召羣臣山公謂不冝爾因與諸尚書言孫吳用兵本
意遂究論舉坐無不咨嗟皆曰山少傅乃天下名言




後諸王驕汰輕遘禍難於是
寇盜處處蟻合郡國多以無備不能制服遂漸熾盛
皆如公言時人以謂山濤不學孫吳而闇與之理會
王夷甫亦歎云公闇與道合


    ```
  - `07-shijian-005` · 識鑒第七 · reviewed · reader_ready=false · surface: 山濤
    ```text
王夷甫父乂爲平北將軍有公事使行人論不得時
夷甫在京師命駕見僕射羊祜尚書山濤夷甫時總
角姿才秀異叙致既快事加有理濤甚奇之既退看

之不輟乃嘆曰生兒不當如王夷甫邪羊祜曰亂天
下者必此子也




    ```
  - `08-shangyu-008` · 賞譽第八 · reviewed · reader_ready=false · surface: 山巨源
    ```text
裴令公目夏侯太初肅肅如入廊廟中不脩敬而人
自敬一曰如入宗廟
琅琅但見禮樂器見鍾士季如觀武庫但覩矛㦸見
傳蘭碩汪廧靡所不有見山巨源如登山臨下幽然
深逺

    ```
  - `08-shangyu-010` · 賞譽第八 · reviewed · reader_ready=false · surface: 山巨源
    ```text
王戎目山巨源如璞玉渾金人皆欽其寳莫知名其
噐

    ```
  - `08-shangyu-017` · 賞譽第八 · reviewed · reader_ready=false · surface: 山濤
    ```text
還渾問濟何以暫行累日濟曰始得一叔渾
問其故濟具歎述如此渾曰何如我濟曰濟以上人
武帝每見濟輒以湛調之曰卿家癡叔死未濟常無
以荅既而得叔後武帝又問如前濟曰臣叔不癡稱
其實美帝曰誰比濟曰山濤以下魏舒以上







於是顯名年二十八始宦

    ```
  - `08-shangyu-021` · 賞譽第八 · reviewed · reader_ready=false · surface: 山巨源
    ```text
人問王夷甫山巨源義理何如是誰軰王曰此人初

不肯以談自居然不讀老莊時聞其詠往往與其旨
合

    ```
  - `23-rendan-001` · 任誕第二十三 · reviewed · reader_ready=false · surface: 山濤
    ```text
陳留阮籍譙國嵇康河内山濤三人年皆相比康年
少亞之預此契者沛國劉伶陳留阮咸河内向秀琅
邪王戎七人常集于竹林之下肆意酣畼故世謂竹
林七賢

    ```
- Liu-annotation-only presence:
  - `02-yanyu-018` · 言語第二 · reviewed · reader_ready=false · surface: 山濤
    ```text
(為同郡山濤所知又與譙國嵇康/向秀别傳曰秀字子期河内人少)
    ```
  - `03-zhengshi-005` · 政事第三 · reviewed · reader_ready=false · surface: 山濤、巨源
    ```text
(貧少有器量宿士猶不慢之年十七宗人謂宣帝曰/巨源河内懐人祖本郡孝廉父曜宛句令濤蚤孤而)
    ```
  - `03-zhengshi-007` · 政事第三 · reviewed · reader_ready=false · surface: 山濤
    ```text
(世祖所敬選用之事與充咨論充毎不得其所欲好/親待山濤為左僕射領選濤行業既與充異自以為)
    ```
  - `03-zhengshi-008` · 政事第三 · reviewed · reader_ready=false · surface: 山濤
    ```text
(有文才山濤啓武帝云云/王隱晉書曰紹字延祖雅)
    ```
  - `04-wenxue-094` · 文學第四 · reviewed · reader_ready=false · surface: 巨源
    ```text
(叔則樂彦輔王夷甫庾子嵩王安期阮千里衛叔寳/巨源向子期劉伯倫阮仲容王濬仲為竹林名士裴)
    ```
  - `08-shangyu-012` · 賞譽第八 · reviewed · reader_ready=false · surface: 山濤
    ```text
(咸曰真素寡欲深識清濁萬物不能移也若在官人/酒以卒山濤啓事曰吏部郎史曜山處缺當選濤薦)
    ```
  - `09-pinzao-057` · 品藻第九 · reviewed · reader_ready=false · surface: 山濤
    ```text
(百官名曰愉字休豫則次子山濤啓事曰愉忠義有/人剛直疾惡常慕汲黯之爲人仕至侍中河東相晉)
    ```
  - `09-pinzao-071` · 品藻第九 · reviewed · reader_ready=false · surface: 山濤
    ```text
(才於時之談以阮為首王戎次之山向之徒皆其/魏氏春秋曰山濤通簡有德秀咸戎伶朗達有儁)
    ```
  - `18-qiyi-003` · 棲逸第十八 · reviewed · reader_ready=false · surface: 巨源
    ```text
(巨源為吏部/康别傳曰山)
    ```

### 樂廣 (`person-044`)

- directly participating Stories: none currently classified; main-text appearance is retained as `mentioned` pending explicit participation review.
- reviewed linked Stories: 12; reader-ready: 0; candidate links: 0; candidate contextual Mentions: 0
- main-text presence:
  - `01-dexing-023` · 德行第一 · reviewed · reader_ready=false · surface: 樂廣
    ```text
王平子胡母彦國諸人皆以任放為達或有祼體者


樂廣
笑曰名教中自有樂地何為乃爾也

    ```
  - `02-yanyu-100` · 言語第二 · reviewed · reader_ready=false · surface: 彦輔
    ```text
即取作長史帶晉陵
郡太傅巳構嫌孝伯不欲使其得謝還取作咨議外
示縶維而實以乖閒之及孝伯敗後太傅繞東府城
行散
僚屬悉在南門要望候拜時謂謝曰王寗異謀
云是卿為其計謝曾無懼色斂笏對曰樂
彦輔有言豈以五男易一女太傅善其對因舉酒勸

之曰故自佳故自佳

    ```
  - `08-shangyu-023` · 賞譽第八 · reviewed · reader_ready=false · surface: 樂廣
    ```text
衛伯玉爲尚書令見樂廣與中朝名士談議竒之曰
自昔諸人没巳來常恐微言將絶今乃復聞斯言於
君矣命子弟造之曰此人人之水鏡也見之若披雲
霧覩青天


    ```
  - `09-pinzao-007` · 品藻第九 · reviewed · reader_ready=false · surface: 樂廣
    ```text
冀州剌史楊淮二子喬與髦俱緫角爲成噐淮與裴
頠樂廣友善遣見之頠性弘方愛喬之有高韻謂淮

曰喬當及卿髦小減也廣性清淳愛髦之有神檢謂
淮曰喬自及卿然髦尤精出淮笑曰我二兒之優劣
乃裴樂之優劣論者評之以爲喬雖高韻而檢不匝
樂言爲得然並爲後
    ```
  - `09-pinzao-008` · 品藻第九 · reviewed · reader_ready=false · surface: 樂彦輔
    ```text
劉令言始入洛
見諸名士而歎曰王夷甫太解明樂彦輔我所敬
張茂先我所不解周弘武巧於用短
杜方叔拙於用長




    ```
  - `09-pinzao-010` · 品藻第九 · reviewed · reader_ready=false · surface: 樂廣
    ```text
王夷甫以王東海比樂令

故王中郎作碑
云當時標榜爲樂廣之儷

    ```
- Liu-annotation-only presence:
  - `02-yanyu-025` · 言語第二 · reviewed · reader_ready=false · surface: 樂廣
    ```text
(輔南陽人清夷沖曠加/虞預晉書曰樂廣字彦)
    ```
  - `02-yanyu-032` · 言語第二 · reviewed · reader_ready=false · surface: 樂廣
    ```text
(王三子不如衛家一兒娶樂廣女裴叔道曰妻父有/之禮論者以為出王眉子平子武子之右世咸謂諸)
    ```
  - `04-wenxue-012` · 文學第四 · reviewed · reader_ready=false · surface: 樂廣
    ```text
(理而頠辭喻豐博廣自以體虚無笑而不復言恵帝/折之才博喻廣學者不能究後樂廣與頠清閒欲説)
    ```
  - `04-wenxue-094` · 文學第四 · reviewed · reader_ready=false · surface: 樂彦輔
    ```text
(叔則樂彦輔王夷甫庾子嵩王安期阮千里衛叔寳/巨源向子期劉伯倫阮仲容王濬仲為竹林名士裴)
    ```
  - `08-shangyu-025` · 賞譽第八 · reviewed · reader_ready=false · surface: 樂廣
    ```text
(甫光禄大夫裴叔則能清言常曰與樂君言覺其簡/樂廣善以約言厭人心其所不知黙如也太尉王夷)
    ```
  - `23-rendan-013` · 任誕第二十三 · reviewed · reader_ready=false · surface: 樂廣
    ```text
(至放蕩越禮樂廣譏之曰名教中自有樂地何至於/是時竹林諸賢之風雖髙而禮教尚峻迨元康中遂)
    ```

### 阮籍 (`person-045`)

- directly participating Stories: none currently classified; main-text appearance is retained as `mentioned` pending explicit participation review.
- reviewed linked Stories: 19; reader-ready: 0; candidate links: 0; candidate contextual Mentions: 0
- main-text presence:
  - `01-dexing-015` · 德行第一 · reviewed · reader_ready=false · surface: 嗣宗、阮嗣宗、阮籍
    ```text
晉文王稱阮嗣宗至慎每與之言言皆玄逺未嘗臧
否人物








    ```
  - `04-wenxue-067` · 文學第四 · reviewed · reader_ready=false · surface: 阮籍
    ```text
魏朝封晉文王為公備禮九錫文王固讓不受公卿
將校當詣府敦喻司空鄭冲馳遣信就阮籍求
文籍時在袁孝尼家

宿醉扶起書札為之無所㸃定乃寫付使時
人以為神筆



    ```
  - `17-shangshi-002` · 傷逝第十七 · reviewed · reader_ready=false · surface: 阮嗣宗
    ```text
王濬沖為尚書令著公服乘軺車經黄公酒壚下過
顧謂後車客吾昔與嵇叔
夜阮嗣宗共酣飲於此壚竹林之逰亦預其末自嵇
生夭阮公亡以來便為時所羈紲今日視此雖近邈
若山河


    ```
  - `18-qiyi-001` · 棲逸第十八 · reviewed · reader_ready=false · surface: 阮籍
    ```text
阮步兵嘯聞數百步蘇門山中忽有真人樵伐者咸
共傳說阮籍往觀見其人擁䣛巖側籍登嶺就之箕
踞相對籍商略終古上陳黄農玄寂之道下考三代
盛德之美以問之仡然不應復叙有為之教棲神導
氣之術以觀之彼猶如前凝矚不轉籍因對之長嘯











    ```
  - `23-rendan-001` · 任誕第二十三 · reviewed · reader_ready=false · surface: 阮籍
    ```text
陳留阮籍譙國嵇康河内山濤三人年皆相比康年
少亞之預此契者沛國劉伶陳留阮咸河内向秀琅
邪王戎七人常集于竹林之下肆意酣畼故世謂竹
林七賢

    ```
  - `23-rendan-002` · 任誕第二十三 · reviewed · reader_ready=false · surface: 阮籍
    ```text
阮籍遭母喪在晉文王坐進酒肉司隷何曽亦在坐

曰明公方以孝治天下而阮籍以重喪顯
於公坐飲酒食肉宐流之海外以正風教文王曰嗣

宗毁頓如此君不能共憂之何謂且有疾而飲酒食
肉固喪禮也籍飲噉不輟
    ```
  - `23-rendan-005` · 任誕第二十三 · reviewed · reader_ready=false · surface: 阮籍
    ```text
步兵校尉缺厨中有貯酒數百斛阮籍乃求爲歩兵
校尉






    ```
  - `23-rendan-007` · 任誕第二十三 · reviewed · reader_ready=false · surface: 阮籍
    ```text
阮籍㛮嘗還家籍見與别或譏之籍曰
禮豈為我輩設也

    ```
  - `23-rendan-009` · 任誕第二十三 · reviewed · reader_ready=false · surface: 阮籍
    ```text
阮籍當葬母蒸一肥豚飲酒二斗然後臨訣直言竆
矣都得一號因吐血廢頓良久


    ```
  - `23-rendan-051` · 任誕第二十三 · reviewed · reader_ready=false · surface: 阮籍
    ```text
王孝伯問王大阮籍何如司馬相如王大曰阮籍胷
中壘塊故須酒澆之

    ```
  - `24-jianao-001` · 簡傲第二十四 · reviewed · reader_ready=false · surface: 阮籍
    ```text
晉文王功德盛大坐席嚴敬擬於王者
唯阮籍在坐箕踞嘯歌酣放

自若

    ```
  - `24-jianao-002` · 簡傲第二十四 · reviewed · reader_ready=false · surface: 阮籍
    ```text
王戎弱冠詣阮籍時劉公榮在坐阮謂王曰偶有二
斗美酒當與君共飲彼公榮者無預焉二人交觴酬
酢公榮遂不得一桮而言語談戯三人無異或有問
之者阮荅曰勝公榮者不得不與飲酒不如公榮者
不可不與飲酒唯公榮可不與飲
    ```
- Liu-annotation-only presence:
  - `01-dexing-023` · 德行第一 · reviewed · reader_ready=false · surface: 阮籍
    ```text
(其後貴游子弟阮瞻王澄謝鯤胡母輔之之徒皆祖/隱晉書曰魏末阮籍嗜酒荒放露頭散髮裸袒箕踞)
    ```
  - `04-wenxue-012` · 文學第四 · reviewed · reader_ready=false · surface: 阮籍
    ```text
(吏部即劉漢亦體道而言約尚書令王夷甫講理而/侯玄歩兵校尉阮籍等皆著道徳論于時侍中樂廣)
    ```
  - `04-wenxue-094` · 文學第四 · reviewed · reader_ready=false · surface: 阮嗣宗
    ```text
(為正始名士阮嗣宗嵇叔夜山/宏以夏侯太初何平叔王輔嗣)
    ```
  - `13-haoshuang-013` · 豪爽第十三 · reviewed · reader_ready=false · surface: 阮籍
    ```text
(懷詩也/阮籍詠)
    ```
  - `19-xianyuan-011` · 賢媛第十九 · reviewed · reader_ready=false · surface: 阮籍
    ```text
(諸人箸忘言之契至於羣子屯蹇於世濤獨保浩然/逹度量弘逺心存事外而與時俛仰嘗與阮籍嵇康)
    ```
  - `23-rendan-011` · 任誕第二十三 · reviewed · reader_ready=false · surface: 阮籍
    ```text
(楷徃弔之遇籍方醉散髪箕踞㫄/名士傳曰阮籍喪親不率常禮裴)
    ```
  - `24-jianao-004` · 簡傲第二十四 · reviewed · reader_ready=false · surface: 阮籍
    ```text
(以白眼對之及喜徃籍不哭見其白眼喜不懌而退/兄也阮籍遭喪徃弔之籍能為青白眼見凡俗之士)
    ```

### 嵇康 (`person-046`)

- directly participating Stories: none currently classified; main-text appearance is retained as `mentioned` pending explicit participation review.
- reviewed linked Stories: 21; reader-ready: 0; candidate links: 0; candidate contextual Mentions: 0
- main-text presence:
  - `01-dexing-016` · 德行第一 · reviewed · reader_ready=false · surface: 嵇康
    ```text
王戎云與嵇康居二十年未嘗見其喜愠之色





    ```
  - `01-dexing-043` · 德行第一 · reviewed · reader_ready=false · surface: 嵇康
    ```text
佐十許人咨議羅企
生亦在焉桓

素待企生厚將有所戮先遣人語云若謝我當釋罪
企生荅曰為殷荆州吏今荆州奔亡存亡未判我何
顔謝桓公








既出市桓又遣人問欲何言荅曰
昔晉文王殺嵇康而嵇紹為晉忠臣

從公乞一弟以養老母桓
亦如言宥之桓先曾以一羔裘與企生母胡胡時在
豫章企生問至即日焚裘

    ```
  - `03-zhengshi-008` · 政事第三 · reviewed · reader_ready=false · surface: 嵇康
    ```text
嵇康被誅後山公舉康子紹爲秘書丞


紹咨公出處
公曰爲君思之乆矣天地四時猶有消息而况
人乎

    ```
  - `04-wenxue-098` · 文學第四 · reviewed · reader_ready=false · surface: 嵇康
    ```text
或問顧長康君箏賦何如嵇康琴賦顧曰不賞者作
後出相遺深識者亦以髙奇見貴





    ```
  - `09-pinzao-031` · 品藻第九 · reviewed · reader_ready=false · surface: 嵇叔夜
    ```text
簡文云何平叔巧累於理嵇叔夜儁傷其道



    ```
  - `14-rongzhi-005` · 容止第十四 · reviewed · reader_ready=false · surface: 嵇叔夜、嵇康
    ```text
嵇康身長七尺八寸風姿特秀

見者歎曰蕭蕭
肅肅爽朗清舉或云肅肅如松下風髙而徐引山公
曰嵇叔夜之為人也巖巖若孤松之獨立其醉也傀
俄若玉山之將崩

    ```
  - `18-qiyi-003` · 棲逸第十八 · reviewed · reader_ready=false · surface: 嵇康
    ```text
山公將去選曹欲舉嵇康康與書告絶




    ```
  - `23-rendan-001` · 任誕第二十三 · reviewed · reader_ready=false · surface: 嵇康
    ```text
陳留阮籍譙國嵇康河内山濤三人年皆相比康年
少亞之預此契者沛國劉伶陳留阮咸河内向秀琅
邪王戎七人常集于竹林之下肆意酣畼故世謂竹
林七賢

    ```
  - `24-jianao-003` · 簡傲第二十四 · reviewed · reader_ready=false · surface: 嵇康
    ```text
鍾士季精有才理先不識嵇康鍾要于時賢儁之士
俱徃尋康康方大樹下鍜向子期為佐鼔排康揚槌
不輟傍若無人移時不交一言鍾起去康曰何所聞
而來何所見而去鍾曰聞所聞而來見所見而去





    ```
  - `24-jianao-004` · 簡傲第二十四 · reviewed · reader_ready=false · surface: 嵇康
    ```text
嵇康與吕安善每一相思千里命駕

安後
來值康不在喜出户延之不入


題門上作鳯字而去
喜不覺猶以為欣故作鳯字凡鳥也

    ```
- Liu-annotation-only presence:
  - `02-yanyu-018` · 言語第二 · reviewed · reader_ready=false · surface: 嵇康
    ```text
(事營生業亦不異常與嵇康偶鍛於洛邑與呂安灌/東平呂安友善並有拔俗之韻其進止無不同而造)
    ```
  - `03-zhengshi-005` · 政事第三 · reviewed · reader_ready=false · surface: 嵇康
    ```text
(此快人邪好荘老與嵇康善為河内從事與石鑒共/濤當與景文共綱紀天下者也帝戱曰卿小族那得)
    ```
  - `04-wenxue-017` · 文學第四 · reviewed · reader_ready=false · surface: 嵇康
    ```text
(安為友趣舎不同嵇康/秀别傳曰秀與嵇康吕)
    ```
  - `04-wenxue-021` · 文學第四 · reviewed · reader_ready=false · surface: 嵇叔夜、嵇康
    ```text
(食柏而香頸處險而癭齒居晉而黄/嵇叔夜養生論曰夫蝨箸頭而黑麝)
    ```
  - `04-wenxue-091` · 文學第四 · reviewed · reader_ready=false · surface: 嵇康
    ```text
(屈原季主賈誼楚老龔勝孫登嵇康也其㫖以處者/能談論萬集載其敘四隱四顯為八賢之論謂漁父)
    ```
  - `04-wenxue-094` · 文學第四 · reviewed · reader_ready=false · surface: 嵇叔夜
    ```text
(為正始名士阮嗣宗嵇叔夜山/宏以夏侯太初何平叔王輔嗣)
    ```
  - `05-fangzheng-010` · 方正第五 · reviewed · reader_ready=false · surface: 嵇康
    ```text
(隂之役談者咸曰觀紹靚二人然後知忠孝之道區/中於是以至孝發名時嵇康亦被法而康子紹死蕩)
    ```
  - `08-shangyu-111` · 賞譽第八 · reviewed · reader_ready=false · surface: 叔夜
    ```text
(賦也劉惔/稽叔夜琴)
    ```
  - `09-pinzao-080` · 品藻第九 · reviewed · reader_ready=false · surface: 嵇康
    ```text
(春扶風郿人博學高論/嵇康高士傳曰丹字大)
    ```
  - `18-qiyi-001` · 棲逸第十八 · reviewed · reader_ready=false · surface: 嵇康
    ```text
(曰孫登即阮籍所見者也嵇康執弟子禮而師焉魏/事在獄為詩自責云昔慚下惠今愧孫登王隐晉書)
    ```
  - `19-xianyuan-011` · 賢媛第十九 · reviewed · reader_ready=false · surface: 嵇康
    ```text
(諸人箸忘言之契至於羣子屯蹇於世濤獨保浩然/逹度量弘逺心存事外而與時俛仰嘗與阮籍嵇康)
    ```

### 劉伶 (`person-047`)

- directly participating Stories: none currently classified; main-text appearance is retained as `mentioned` pending explicit participation review.
- reviewed linked Stories: 8; reader-ready: 0; candidate links: 0; candidate contextual Mentions: 0
- main-text presence:
  - `04-wenxue-069` · 文學第四 · reviewed · reader_ready=false · surface: 伯倫、劉伶
    ```text
劉伶著酒徳頌意氣所寄










    ```
  - `14-rongzhi-013` · 容止第十四 · reviewed · reader_ready=false · surface: 伯倫、劉伶
    ```text
劉伶身長六尺貌甚醜顇而悠悠忽忽土木形骸


    ```
  - `23-rendan-001` · 任誕第二十三 · reviewed · reader_ready=false · surface: 劉伶
    ```text
陳留阮籍譙國嵇康河内山濤三人年皆相比康年
少亞之預此契者沛國劉伶陳留阮咸河内向秀琅
邪王戎七人常集于竹林之下肆意酣畼故世謂竹
林七賢

    ```
  - `23-rendan-003` · 任誕第二十三 · reviewed · reader_ready=false · surface: 劉伶
    ```text
劉伶病酒渴甚從婦求酒婦捐酒毁噐涕泣諫曰君
飲太過非攝生之道必宐斷之伶曰甚善我不能自
禁唯當祝鬼神自誓斷之耳便可具酒肉婦曰敬聞
命供酒肉於神前請伶祝誓伶跪而祝曰天生劉伶
以酒為名一飲一斛五斗解酲婦人之言

慎不可聽便引酒進肉隗然已醉矣

    ```
  - `23-rendan-006` · 任誕第二十三 · reviewed · reader_ready=false · surface: 劉伶
    ```text
劉伶恒縱酒放逹或脫衣祼形在屋中人見譏之伶
曰我以天地為棟宇屋室為㡓衣諸君何為入吾㡓
中


    ```
- Liu-annotation-only presence:
  - `04-wenxue-094` · 文學第四 · reviewed · reader_ready=false · surface: 劉伯倫
    ```text
(叔則樂彦輔王夷甫庾子嵩王安期阮千里衛叔寳/巨源向子期劉伯倫阮仲容王濬仲為竹林名士裴)
    ```
  - `05-fangzheng-015` · 方正第五 · reviewed · reader_ready=false · surface: 伯倫
    ```text
(字伯倫司徒濤長/晉諸公賛曰山該)
    ```
  - `23-rendan-005` · 任誕第二十三 · reviewed · reader_ready=false · surface: 劉伶
    ```text
(厨中並醉而死此好事者爲之言籍景元中卒而劉/舍與劉伶酣飲竹林七賢論又云籍與伶共飲步兵)
    ```

### 潘岳 (`person-048`)

- directly participating Stories: none currently classified; main-text appearance is retained as `mentioned` pending explicit participation review.
- reviewed linked Stories: 8; reader-ready: 0; candidate links: 0; candidate contextual Mentions: 0
- main-text presence:
  - `02-yanyu-107` · 言語第二 · reviewed · reader_ready=false · surface: 潘岳
    ```text
桓玄既簒位將改置直舘問左右虎賁中郎省應在
何處有人荅曰無省當時殊忤㫖問何以知無荅曰
潘岳秋興賦敘曰余兼虎賁中郎將寓直散騎之省


玄咨嗟稱善



    ```
  - `04-wenxue-070` · 文學第四 · reviewed · reader_ready=false · surface: 安仁、潘岳
    ```text
樂令善於清言而不長於手筆將讓河南尹請潘岳
為表
潘云可作耳要當得君意樂為述已所以為
讓標位二百許語潘直取錯綜便成名筆時人咸云
若樂不假潘之文潘不取樂之㫖則無以成斯矣

    ```
  - `04-wenxue-071` · 文學第四 · reviewed · reader_ready=false · surface: 安仁、潘安仁、潘岳
    ```text
夏侯湛作周詩成

示潘安仁安仁曰此非徒温雅

乃别見孝悌之性
潘因此遂作家風詩

    ```
  - `08-shangyu-139` · 賞譽第八 · reviewed · reader_ready=false · surface: 安仁、潘安仁
    ```text
謝胡兒作著作郎嘗作王堪傳
不諳堪是何似人咨謝
公謝公荅曰世胄亦被遇堪烈之子

阮千里姨兄弟潘安仁中外安仁詩所謂子親伊姑
我父唯舅是許允壻


    ```
  - `14-rongzhi-007` · 容止第十四 · reviewed · reader_ready=false · surface: 安仁、潘岳
    ```text
潘岳妙有姿容好神情少時挾彈
出洛陽道婦人遇者莫不連手共縈之左太沖絶醜
亦復效岳遊遨於是羣嫗齊共亂
唾之委頓而返



    ```
  - `14-rongzhi-009` · 容止第十四 · reviewed · reader_ready=false · surface: 潘安仁
    ```text
潘安仁夏侯湛並有美容喜同行時人謂之連璧


    ```
  - `36-chouxi-001` · 仇隟第三十六 · reviewed · reader_ready=false · surface: 安仁、潘岳
    ```text



又憾潘岳昔遇之不以禮後秀爲
中書令岳省内見之因喚曰孫令憶疇昔周旋不秀
曰中心藏之何日忘之岳於是始知必不免

後收石崇歐陽
堅石同日收岳



石先送市亦不相知潘
後至石謂潘曰安仁卿亦復爾邪潘曰可謂白首同
所歸潘
金谷集詩云投分寄石友白首同所歸乃成其䜟

    ```
- Liu-annotation-only presence:
  - `03-zhengshi-005` · 政事第三 · reviewed · reader_ready=false · surface: 潘岳
    ```text
(曰閣東有大牛王濟鞅裴楷鞦和嶠刺促不得休/王隱晉書曰初濤領吏部潘岳内非之宻為作謡)
    ```

### 顧榮 (`person-049`)

- directly participating Stories: none currently classified; main-text appearance is retained as `mentioned` pending explicit participation review.
- reviewed linked Stories: 8; reader-ready: 0; candidate links: 0; candidate contextual Mentions: 0
- main-text presence:
  - `01-dexing-025` · 德行第一 · reviewed · reader_ready=false · surface: 顧榮
    ```text
顧榮在洛陽嘗應人請覺行炙人有欲炙之色因輟
己施焉同坐嗤之榮曰豈有終日執之而不知其味

者乎後遭亂渡江每經危急常有一人左右己問其
所以乃受炙人也





    ```
  - `08-shangyu-019` · 賞譽第八 · reviewed · reader_ready=false · surface: 顧彦先
    ```text
張華見禇陶語陸平原曰君兄弟龍躍雲津顧彦先
鳳鳴朝陽謂東南之寳巳盡不意復見禇生陸曰公
未覩不鳴不躍者耳






    ```
  - `08-shangyu-020` · 賞譽第八 · reviewed · reader_ready=false · surface: 顧彦先
    ```text
有問秀才吳舊姓何如荅曰吳府君聖王之老成明
時之儁乂朱永長理物之至德清選之高望嚴仲弼
九臯之鳴鶴空谷之白駒顧彦先八音之琴瑟五色
之龍章張威伯歲寒之茂松幽夜之逸光陸士衡士
龍鴻鵠之裵回懸鼔之待槌








凡此諸
君以洪筆爲鉏耒以𥿄札爲良田以玄黙爲稼穡以
義理爲豐年以談論爲英華以忠恕爲珍
    ```
  - `17-shangshi-007` · 傷逝第十七 · reviewed · reader_ready=false · surface: 顧彦先
    ```text
顧彦先平生好琴及喪家人常以琴置靈牀上張季
鷹徃哭之不勝其慟遂徑上牀鼓琴作數曲竟撫琴
曰顧彦先頗復賞此不因又大慟遂不執孝子手而
出

    ```
  - `19-xianyuan-019` · 賢媛第十九 · reviewed · reader_ready=false · surface: 顧榮
    ```text
悉割半為薪剉諸薦以為馬草日夕遂設
精食從者皆無所乏逵既歎其才辯又深愧其厚意
明旦去侃追送不已且百里許逵曰路已逺君宜還
侃猶不返逵曰卿可去矣至洛陽當相為美談侃廼
返逵及洛遂稱之於羊晫顧榮諸人大獲美譽







    ```
- Liu-annotation-only presence:
  - `02-yanyu-033` · 言語第二 · reviewed · reader_ready=false · surface: 顧榮
    ```text
(之騏驥也必振衰族累遷尚書令/名族人顧榮雅相器愛曰此吾家)
    ```
  - `06-yaliang-016` · 雅量第六 · reviewed · reader_ready=false · surface: 顧榮
    ```text
(吾宗仕至尚書令五子治隗淳履之/知名族人顧榮曰此吾家騏驥也必興)
    ```
  - `07-shijian-010` · 識鑒第七 · reviewed · reader_ready=false · surface: 顧榮
    ```text
(夫有四海之名者求退良難吾本山林間人無望於/王冏辟爲東曹掾翰謂同郡顧榮曰天下紛紛未巳)
    ```

### 郭璞 (`person-050`)

- directly participating Stories: none currently classified; main-text appearance is retained as `mentioned` pending explicit participation review.
- reviewed linked Stories: 7; reader-ready: 0; candidate links: 0; candidate contextual Mentions: 0
- main-text presence:
  - `04-wenxue-076` · 文學第四 · reviewed · reader_ready=false · surface: 郭景純、郭璞
    ```text
郭景純詩云林無静樹川無停流




阮孚云泓崢蕭瑟實不
可言每讀此文輒覺神超形越

    ```
  - `20-shujie-005` · 術解第二十 · reviewed · reader_ready=false · surface: 郭璞
    ```text
陳述為大將軍掾甚見愛重及亡郭璞徃哭之甚哀
乃呼曰嗣祖焉知非福俄而大將軍作亂如其所言


    ```
  - `20-shujie-006` · 術解第二十 · reviewed · reader_ready=false · surface: 郭璞
    ```text
晉明帝解占塜宅聞郭璞為人葬帝㣲服徃看因問
主人何以葬龍角此法當滅族主人曰郭云此葬龍

耳不出三年當致天子帝問爲是出天子邪荅曰非
出天子能致天子問耳

    ```
  - `20-shujie-007` · 術解第二十 · reviewed · reader_ready=false · surface: 景純、郭景純
    ```text
郭景純過江居于暨陽墓去水不盈百步時人以爲
近水景純曰將當爲陸
今沙漲去墓數十里
皆爲桑田其詩曰北阜烈烈巨海混混壘壘三墳唯
母與昆

    ```
  - `20-shujie-008` · 術解第二十 · reviewed · reader_ready=false · surface: 郭璞
    ```text
王丞相令郭璞試作一卦卦成郭意色甚惡云公有
震厄王問有可消伏理不郭曰命駕西出數里得一
栢樹截斷如公長置牀上常寝處災可消矣王從其

語數日中果震栢粉碎子弟皆稱慶
大將軍云君乃復委罪於樹木

    ```
- Liu-annotation-only presence:
  - `04-wenxue-085` · 文學第四 · reviewed · reader_ready=false · surface: 郭璞
    ```text
(而韻之詢及太原孫綽轉相祖尚又加以三世之辭/焉至過江佛理尤盛故郭璞五言始㑹合道家之言)
    ```
  - `06-yaliang-026` · 雅量第六 · reviewed · reader_ready=false · surface: 郭璞
    ```text
(大禍唯固三陽可以有後故希求鎮山陽弟友爲東/忌之諷免希官遂奔于暨陽初郭璞筮冰子孫必有)
    ```

### 荀顗 (`person-051`)

- directly participating Stories: none currently classified; main-text appearance is retained as `mentioned` pending explicit participation review.
- reviewed linked Stories: 4; reader-ready: 0; candidate links: 0; candidate contextual Mentions: 0
- main-text presence:
  - `09-pinzao-006` · 品藻第九 · reviewed · reader_ready=false · surface: 荀顗
    ```text
正始中人士比論以五荀方五陳荀淑方陳寔荀靖
方陳諶

荀爽方陳紀荀彧方陳群


荀顗方陳泰

又以八裴方八王裴徽方王祥裴楷
方王夷甫裴康方王綏
裴綽方王澄裴
瓉方王敦裴遐方王導裴
頠方王戎裴邈方王玄

    ```
- Liu-annotation-only presence:
  - `01-dexing-015` · 德行第一 · reviewed · reader_ready=false · surface: 景倩
    ```text
(之矣可舉近世能慎者誰乎吾乃舉故太尉茍景倩/慎之道相須而成必不得已慎乃為大上曰卿言得)
    ```
  - `02-yanyu-020` · 言語第二 · reviewed · reader_ready=false · surface: 荀顗
    ```text
(雅有曾祖寵之風遷尚書令為荀顗所害/郎出為冀州刺史晉諸公贊曰奮體量清)
    ```
  - `02-yanyu-099` · 言語第二 · reviewed · reader_ready=false · surface: 荀顗
    ```text
(定法制樂則/荀顗荀朂修)
    ```

### 祖約 (`person-052`)

- directly participating Stories: none currently classified; main-text appearance is retained as `mentioned` pending explicit participation review.
- reviewed linked Stories: 7; reader-ready: 0; candidate links: 0; candidate contextual Mentions: 0
- main-text presence:
  - `06-yaliang-015` · 雅量第六 · reviewed · reader_ready=false · surface: 士少、祖士少、祖約
    ```text
祖士少好財阮遥集好屐並恒自經營同是一累而
未判其得失


人有詣祖見料視財物客至屏當未盡餘兩小簏
箸背後傾身障之意未能平或有詣阮見自吹火蠟
屐因歎曰未知一生當箸幾量屐神色閑畼於是勝
負始
    ```
  - `08-shangyu-057` · 賞譽第八 · reviewed · reader_ready=false · surface: 士少、祖約
    ```text
王丞相招祖約夜語至曉不眠明旦有客公頭鬢未
理亦小倦客曰公昨如是似失眠公曰昨與士少語
遂使人忘疲

    ```
  - `08-shangyu-088` · 賞譽第八 · reviewed · reader_ready=false · surface: 祖士少
    ```text
王右軍道謝萬石在林澤中爲自遒上歎林公器朗
神儁道祖士少風領毛骨恐没世
不復見如此人道劉真長標雲柯而不扶踈


    ```
  - `08-shangyu-132` · 賞譽第八 · reviewed · reader_ready=false · surface: 士少
    ```text
王子猷説世目士少爲朗我家亦以爲徹朗



    ```
  - `14-rongzhi-022` · 容止第十四 · reviewed · reader_ready=false · surface: 祖士少
    ```text
祖士少見衛君長云此人有旄仗下形

    ```
- Liu-annotation-only presence:
  - `03-zhengshi-011` · 政事第三 · reviewed · reader_ready=false · surface: 祖約
    ```text
(以衆㑹峻既克京師拜丹陽尹後以罪誅/栁妻祖逖子渙女蘇峻招祖約為逆約遣栁)
    ```
  - `14-rongzhi-023` · 容止第十四 · reviewed · reader_ready=false · surface: 祖約
    ```text
(臣官陶侃祖約不在其例侃約疑亮寢遺詔也中/徐廣晉紀曰肅祖遺詔庾亮王導輔㓜主而進大)
    ```

### 王廙 (`person-053`)

- directly participating Stories: none currently classified; main-text appearance is retained as `mentioned` pending explicit participation review.
- reviewed linked Stories: 5; reader-ready: 0; candidate links: 0; candidate contextual Mentions: 0
- main-text presence:
  - `36-chouxi-003` · 仇隟第三十六 · reviewed · reader_ready=false · surface: 世將、王廙
    ```text
王大將軍執司馬愍王夜遣世將載王於車而殺之
當時不盡知也


雖愍王家亦
未之皆悉而無忌兄弟皆稺

王胡之與無忌長甚相暱胡之甞共
遊無忌入告母請為饌母流涕曰王敦昔肆酷汝父
假手世將

吾所以積年不告汝
者王氏
    ```
- Liu-annotation-only presence:
  - `02-yanyu-006` · 言語第二 · reviewed · reader_ready=false · surface: 王廙
    ```text
(辭曰金至/王廙注繋)
    ```
  - `02-yanyu-081` · 言語第二 · reviewed · reader_ready=false · surface: 王廙
    ```text
(齡琅邪臨沂人王廙之子/王胡之别傳曰胡之字脩)
    ```
  - `08-shangyu-004` · 賞譽第八 · reviewed · reader_ready=false · surface: 世將
    ```text
(覽洽聞金玉其行知世將亂避地遼東公孫度厚禮/泣耳師惻然曰苟欲學不須資也於是就業長則博)
    ```
  - `36-chouxi-004` · 仇隟第三十六 · reviewed · reader_ready=false · surface: 王廙
    ```text
(其事且王廙之害司馬丞遐邇共悉脩齡兄弟豈容/詔以贖論前章既言無忌母告之而此章復云客叙)
    ```

### 王隱 (`person-054`)

- directly participating Stories: none currently classified; main-text appearance is retained as `mentioned` pending explicit participation review.
- reviewed linked Stories: 47; reader-ready: 0; candidate links: 0; candidate contextual Mentions: 0
- main-text presence:
  - none
- Liu-annotation-only presence:
  - `01-dexing-012` · 德行第一 · reviewed · reader_ready=false · surface: 王隱
    ```text
(先范陽人也累遷司空/王隱晉書曰張華字茂)
    ```
  - `01-dexing-016` · 德行第一 · reviewed · reader_ready=false · surface: 王隱
    ```text
(怨徙上虞移譙國銍縣以出自㑹稽取國一支音同/康字叔夜譙國銍人王隱晉書曰嵇本姓奚其先避)
    ```
  - `01-dexing-017` · 德行第一 · reviewed · reader_ready=false · surface: 王隱
    ```text
(字仲雄東萊掖人/王隱晉書曰劉毅)
    ```
  - `01-dexing-026` · 德行第一 · reviewed · reader_ready=false · surface: 王隱
    ```text
(書曰祖/王隱晉)
    ```
  - `01-dexing-028` · 德行第一 · reviewed · reader_ready=false · surface: 王隱
    ```text
(德攸遺其驢馬䕶送令得逸王隱晉書曰攸以路逺/老姥作粥失火延逸罪應萬死勒知遣之所誣胡厚)
    ```
  - `01-dexing-043` · 德行第一 · reviewed · reader_ready=false · surface: 王隱
    ```text
(字延祖譙國銍/王隱晉書曰紹)
    ```
  - `02-yanyu-022` · 言語第二 · reviewed · reader_ready=false · surface: 王隱
    ```text
(朝太康中本州從事舉秀才王隱晉書曰洪/洪集録曰洪字叔開吳郡人有才辯初仕呉)
    ```
  - `02-yanyu-035` · 言語第二 · reviewed · reader_ready=false · surface: 王隱
    ```text
(中山魏昌人祖邁有經/王隱晉書曰琨字越石)
    ```
  - `02-yanyu-043` · 言語第二 · reviewed · reader_ready=false · surface: 王隱
    ```text
(字君平㑹稽山隂/王隱晉書曰孔坦)
    ```
  - `02-yanyu-047` · 言語第二 · reviewed · reader_ready=false · surface: 王隱
    ```text
(拜不名劒履上殿進太尉贈大司馬謚桓公按王隱/廣荆三州刺史加羽葆鼓吹封長沙郡公大將軍贊)
    ```
  - `03-zhengshi-006` · 政事第三 · reviewed · reader_ready=false · surface: 王隱
    ```text
(文和滎陽開封人/王隱晉書曰冲字)
    ```
  - `03-zhengshi-008` · 政事第三 · reviewed · reader_ready=false · surface: 王隱
    ```text
(晉書曰時以紹父康被法選官不敢舉年二十八山/晉諸公賛曰康遇事後二十年紹乃爲濤所㧞王隱)
    ```
  - `04-wenxue-013` · 文學第四 · reviewed · reader_ready=false · surface: 王隱
    ```text
(琅邪人魏雍州刺史緒/王隱晉書曰厷字茂逺)
    ```
  - `04-wenxue-068` · 文學第四 · reviewed · reader_ready=false · surface: 王隱
    ```text
(嵩曾孫也祖叔獻灞陵令父叔侯舉孝廉謐/王隱晉書曰謐字士安安定朝那人漢太尉)
    ```
  - `04-wenxue-073` · 文學第四 · reviewed · reader_ready=false · surface: 王隱
    ```text
(使詣洛廣子孫多在洛慮害乃自殺摰虞字仲治京/王隱晉書曰廣字季思東平人拜成都王為太弟欲)
    ```
  - `04-wenxue-076` · 文學第四 · reviewed · reader_ready=false · surface: 王隱
    ```text
(字景純河東聞喜/王隱晉書曰郭璞)
    ```
  - `04-wenxue-079` · 文學第四 · reviewed · reader_ready=false · surface: 王隱
    ```text
(非益也是以古人謂其屋下架屋/王隱論楊雄太玄經曰玄經雖妙)
    ```
  - `05-fangzheng-012` · 方正第五 · reviewed · reader_ready=false · surface: 王隱
    ```text
(元凱京兆杜陵人/王隱晉書曰預字)
    ```
  - `05-fangzheng-016` · 方正第五 · reviewed · reader_ready=false · surface: 王隱
    ```text
(門郎護軍將軍按王隱孫盛不與故君相聞議曰昔/春秋曰雄字茂伯河内人世語曰雄有節槩仕至黄)
    ```
  - `05-fangzheng-034` · 方正第五 · reviewed · reader_ready=false · surface: 王隱
    ```text
(廣掖人少有才學仕郡主/王隱晉書曰峻字子高長)
    ```
  - `05-fangzheng-037` · 方正第五 · reviewed · reader_ready=false · surface: 王隱
    ```text
(平陶侃欲將坦上用/按王隱晉書蘇峻事)
    ```
  - `05-fangzheng-039` · 方正第五 · reviewed · reader_ready=false · surface: 王隱
    ```text
(而遣之王隱晉書亦同按二書所敘則有惠於陶是/敦敦陳兵欲害侃敦咨議參軍梅陶諫敦乃止厚礼)
    ```
  - `05-fangzheng-043` · 方正第五 · reviewed · reader_ready=false · surface: 王隱
    ```text
(方直而有雅望/王隱晉書曰坦)
    ```
  - `06-yaliang-002` · 雅量第六 · reviewed · reader_ready=false · surface: 王隱
    ```text
(太學生數千人請之于/王隱晉書曰康之下獄)
    ```
  - `07-shijian-013` · 識鑒第七 · reviewed · reader_ready=false · surface: 王隱
    ```text
(州刺史王隱晉書曰朗有器識才量善能當世仕至/字世彦弘農人楊氏譜曰朗祖囂典軍校尉父淮冀)
    ```
  - `08-shangyu-005` · 賞譽第八 · reviewed · reader_ready=false · surface: 王隱
    ```text
(少清明曉悟/王隱晉書曰戎)
    ```
  - `08-shangyu-017` · 賞譽第八 · reviewed · reader_ready=false · surface: 王隱
    ```text
(城人㓜孤爲外氏寗家所養寗氏起宅相者曰當出/欲以我處季孟之間乎王隱晉書曰魏舒字陽元任)
    ```
  - `08-shangyu-027` · 賞譽第八 · reviewed · reader_ready=false · surface: 王隱
    ```text
(好人倫情無所撃/王隱晉書曰澄通朗)
    ```
  - `08-shangyu-036` · 賞譽第八 · reviewed · reader_ready=false · surface: 王隱
    ```text
(初到洛下于禄求榮永嘉中洛/王隱晉書曰董養字仲道太始)
    ```
  - `09-pinzao-008` · 品藻第九 · reviewed · reader_ready=false · surface: 王隱
    ```text
(恢字弘武汝南/王隱晉書曰周)
    ```
  - `10-guizhen-009` · 規箴第十 · reviewed · reader_ready=false · surface: 王隱
    ```text
(貨利之事王隱晉書曰夷甫求富貴得冨貴資財山/秋曰夷甫善施舍父時有假貸者皆與焚券未嘗謀)
    ```
  - `17-shangshi-004` · 傷逝第十七 · reviewed · reader_ready=false · surface: 王隱
    ```text
(蚤亡戎過傷痛不許人求之遂至老無/王隱晉書曰戎子綏欲取裴遁女綏既)
    ```
  - `18-qiyi-001` · 棲逸第十八 · reviewed · reader_ready=false · surface: 王隐
    ```text
(曰孫登即阮籍所見者也嵇康執弟子禮而師焉魏/事在獄為詩自責云昔慚下惠今愧孫登王隐晉書)
    ```
  - `19-xianyuan-011` · 賢媛第十九 · reviewed · reader_ready=false · surface: 王隱
    ```text
(曰忍寒我當作三公不知卿堪為夫人否耳/之度王隱晉書曰韓氏有才識濤未仕時戲之)
    ```
  - `19-xianyuan-013` · 賢媛第十九 · reviewed · reader_ready=false · surface: 王隱
    ```text
(城陽太守郭配女名槐李禁錮解詔充置左右夫人/㫁不得往還而王隱晉書亦云充既與李絶婚更取)
    ```
  - `19-xianyuan-014` · 賢媛第十九 · reviewed · reader_ready=false · surface: 王隐
    ```text
(典式八篇王隐晉書曰賈后字南風爲趙王所誅/亦才明即齊王妃婦人集曰李氏至樂浪遺二女)
    ```
  - `19-xianyuan-019` · 賢媛第十九 · reviewed · reader_ready=false · surface: 王隱
    ```text
(俊也王隱晉書曰侃母既截髪供客聞者歎曰非此/章顧榮或責羊晫曰君奈何與小人同輿晫曰此寒)
    ```
  - `20-shujie-008` · 術解第二十 · reviewed · reader_ready=false · surface: 王隱
    ```text
(消災轉禍扶厄/王隱晉書曰璞)
    ```
  - `23-rendan-008` · 任誕第二十三 · reviewed · reader_ready=false · surface: 王隱
    ```text
(親生不相識徃哭盡哀而去其逹而無檢皆此類也/王隱晉書曰籍鄰家處子有才色未嫁而卒籍與無)
    ```
  - `25-paidiao-044` · 排調第二十五 · reviewed · reader_ready=false · surface: 王隱
    ```text
(巴西安漢人好學善著述仕至中庶子初壽父爲馬/功葢應變將略非其所長也王隱晉書曰壽字承祚)
    ```
  - `26-qingdi-004` · 輕詆第二十六 · reviewed · reader_ready=false · surface: 王隱
    ```text
(乎王隱晉書戴洋傳曰丹陽太守王導問洋得病七/下公以識度裁之囂言自息豈或回貳有扇塵之事)
    ```
  - `27-jiajue-009` · 假譎第二十七 · reviewed · reader_ready=false · surface: 王隱
    ```text
(興二年嶠為劉/王隱晉書曰建)
    ```
  - `29-jianshe-002` · 儉嗇第二十九 · reviewed · reader_ready=false · surface: 王隱
    ```text
(曰戎性至/王隱晉書)
    ```
  - `29-jianshe-003` · 儉嗇第二十九 · reviewed · reader_ready=false · surface: 王隱
    ```text
(之望不重王隱晉書曰戎好治生園田周徧天下翁/要不治儀望自遇甚薄而産業過豐論者以為台輔)
    ```
  - `30-taichi-001` · 汰侈第三十 · reviewed · reader_ready=false · surface: 王隱
    ```text
(荆州刺史劫奪殺人/王隱晉書曰石崇為)
    ```
  - `36-chouxi-001` · 仇隟第三十六 · reviewed · reader_ready=false · surface: 王隱
    ```text
(腹心撓亂關中建毎匡正由是有隟王隱晉書曰石/堅石初建為馮翊太守趙王倫為征西將軍孫秀為)
    ```
  - `36-chouxi-004` · 仇隟第三十六 · reviewed · reader_ready=false · surface: 王隱
    ```text
(人璩曽孫也為人弘長有淹度飾之/王隱晉書曰應詹字思逺汝南南頓)
    ```

### 氾騰 (`person-055`)

- directly participating Stories: none currently classified; main-text appearance is retained as `mentioned` pending explicit participation review.
- reviewed linked Stories: 3; reader-ready: 0; candidate links: 0; candidate contextual Mentions: 0
- main-text presence:
  - `07-shijian-027` · 識鑒第七 · reviewed · reader_ready=false · surface: 無忌
    ```text
車胤父作南平郡功曹太守王胡之避司馬無忌之
難置郡于酆隂是時胤十餘歲胡之每出嘗於籬中
見而異焉謂胤父曰此兒當致高名後遊集恒命之
胤長又爲桓宣武所知清通於多士之世官至選曹
尚書





    ```
  - `36-chouxi-003` · 仇隟第三十六 · reviewed · reader_ready=false · surface: 無忌
    ```text
王大將軍執司馬愍王夜遣世將載王於車而殺之
當時不盡知也


雖愍王家亦
未之皆悉而無忌兄弟皆稺

王胡之與無忌長甚相暱胡之甞共
遊無忌入告母請為饌母流涕曰王敦昔肆酷汝父
假手世將

吾所以積年不告汝
者王氏門彊汝兄弟尚幼不欲使此聲著葢以避禍
耳無忌驚號抽刃而出胡之去
    ```
- Liu-annotation-only presence:
  - `36-chouxi-004` · 仇隟第三十六 · reviewed · reader_ready=false · surface: 無忌
    ```text
(其事且王廙之害司馬丞遐邇共悉脩齡兄弟豈容/詔以贖論前章既言無忌母告之而此章復云客叙)
    ```

### 李重 (`person-056`)

- directly participating Stories: none currently classified; main-text appearance is retained as `mentioned` pending explicit participation review.
- reviewed linked Stories: 3; reader-ready: 0; candidate links: 0; candidate contextual Mentions: 0
- main-text presence:
  - `18-qiyi-004` · 棲逸第十八 · reviewed · reader_ready=false · surface: 茂曽
    ```text
李廞是茂曽弟五子清貞有逺操而少羸病不肯婚
宦居在臨海住兄侍中墓下既有髙名王丞相欲招
禮之故辟為府掾廞得牋命笑曰茂弘乃復以一爵
假人




    ```
  - `19-xianyuan-017` · 賢媛第十九 · reviewed · reader_ready=false · surface: 李重
    ```text
李平陽秦州子中夏名
士于時以比王夷甫孫秀初欲立威權咸云樂令名
望不可殺減李重者又不足殺

遂逼重自裁初重在家
有人走從門入出髻中䟽示重重看之色動入内示
其女女直呌絶了其意出則自裁

此女甚高明重每咨焉


    ```
- Liu-annotation-only presence:
  - `09-pinzao-046` · 品藻第九 · reviewed · reader_ready=false · surface: 李重
    ```text
(鍾武人少以清尚見稱歴吏部/晉諸公賛曰李重字茂重江夏)
    ```

### 沈充 (`person-057`)

- directly participating Stories: none currently classified; main-text appearance is retained as `mentioned` pending explicit participation review.
- reviewed linked Stories: 3; reader-ready: 0; candidate links: 0; candidate contextual Mentions: 0
- main-text presence:
  - `06-yaliang-018` · 雅量第六 · reviewed · reader_ready=false · surface: 沈充
    ```text
禇公於章安令遷太尉記室㕘軍

名字巳顯而位微人未多識公東出乗估客船
送故吏數人投錢唐亭住
爾時吳興沈充爲縣令當送客過浙
江客出亭吏驅公移牛屋下潮水至沈令起彷徨問
牛屋下是何物人吏云昨有一傖父來寄亭中
有尊貴客權移之令有酒色因遥問傖父
欲食䴵不姓何等可共語禇因舉手答曰河南禇季
野逺近
    ```
  - `10-guizhen-016` · 規箴第十 · reviewed · reader_ready=false · surface: 士居、沈充
    ```text
蘇峻東征沈充


請吏部郎陸邁與俱
將至吳密勑左右令入閶門放火以示威
陸知其意謂峻曰吳治平未久必將有亂若爲亂階
請從我家始峻遂止

    ```
- Liu-annotation-only presence:
  - `09-pinzao-013` · 品藻第九 · reviewed · reader_ready=false · surface: 沈充
    ```text
(吳郡果爲沈充所殺/然象以齒䘮身後爲)
    ```

### 鍾雅 (`person-058`)

- directly participating Stories: none currently classified; main-text appearance is retained as `mentioned` pending explicit participation review.
- reviewed linked Stories: 2; reader-ready: 0; candidate links: 0; candidate contextual Mentions: 0
- main-text presence:
  - `03-zhengshi-011` · 政事第三 · reviewed · reader_ready=false · surface: 彦胄、鍾雅
    ```text
成帝在石頭任讓在帝前
戮侍中鍾雅

右衛將軍劉超


帝泣曰
還我侍中讓不奉詔遂斬超雅
事平之後陶公與讓有
舊欲宥之許栁
兒思妣
者至佳諸公欲全之若全思妣則不得不
為陶全讓於是欲并宥之事奏帝曰讓是殺我侍中

者不
    ```
  - `05-fangzheng-034` · 方正第五 · reviewed · reader_ready=false · surface: 鍾雅
    ```text
蘇峻既至石頭百僚奔散




唯侍中鍾雅獨在帝側或謂鍾曰見可
而進知難而退古之道也君性亮直必不容於寇讎
何不用隨時之宜而坐待其弊邪鍾曰國亂不能匡
君危不能濟而各遜遁以求免吾懼董狐將執簡而
進矣

    ```
- Liu-annotation-only presence:
  - none

### 孫盛 (`person-059`)

- directly participating Stories: none currently classified; main-text appearance is retained as `mentioned` pending explicit participation review.
- reviewed linked Stories: 22; reader-ready: 0; candidate links: 0; candidate contextual Mentions: 0
- main-text presence:
  - `02-yanyu-049` · 言語第二 · reviewed · reader_ready=false · surface: 孫盛、安國
    ```text
孫盛為庾公記室叅軍
從獵將其二兒俱行庾公不

知忽於獵塲見齊莊時年七八歳庾謂曰君亦復來
邪應聲荅曰所謂無小無大從公于邁

    ```
  - `04-wenxue-025` · 文學第四 · reviewed · reader_ready=false · surface: 孫安國、孫盛
    ```text
禇季野語孫安國云北人學問淵綜廣博
孫荅曰南人學問清通簡要支道林聞之曰聖賢固
所忘言自中人以還北人㸔書如顯處視月南人學
問如牖中窺日


    ```
  - `04-wenxue-031` · 文學第四 · reviewed · reader_ready=false · surface: 孫安國、孫盛
    ```text
孫安國徃殷中軍許共論徃反精苦客主無間左右
進食冷而復煗者數四彼我奮擲麈尾悉脫落滿餐
飯中賓主遂至莫忘食殷乃語孫曰卿莫作强口馬
我當穿卿鼻孫曰卿不見决鼻牛人當穿卿頰


    ```
  - `04-wenxue-056` · 文學第四 · reviewed · reader_ready=false · surface: 孫安國
    ```text
殷中軍孫安國王謝能言諸賢悉在㑹稽王許殷與
孫共論易象妙於見形



孫語道合意
氣干雲一坐咸不安孫理而辭不能屈㑹稽王慨然
歎曰使眞長來故應有以制彼卽迎眞長孫意己不
如眞長旣至先令孫自叙本理孫麤
    ```
  - `05-fangzheng-043` · 方正第五 · reviewed · reader_ready=false · surface: 安國
    ```text
孔君平疾篤庾司空爲㑹稽省之相問訊甚至爲

之流涕庾既下牀孔慨然曰大丈夫將終不問安國
寧家之術廼作兒女子相問庾聞回謝之請其話言


    ```
  - `14-rongzhi-004` · 容止第十四 · reviewed · reader_ready=false · surface: 安國
    ```text
時人目夏侯太初朗朗如日月之入懷李安國穨唐
如玉山之将崩



    ```
  - `25-paidiao-025` · 排調第二十五 · reviewed · reader_ready=false · surface: 孫盛
    ```text
禇季野問孫盛卿國史何當成孫云久應竟在公無
暇故至今日禇曰古人述而不作何必在𧖟室中





    ```
  - `25-paidiao-033` · 排調第二十五 · reviewed · reader_ready=false · surface: 孫安國
    ```text
庾園客詣孫監值行見齊莊在外尚㓜而有神意庾

試之曰孫安國何在即荅曰庾穉恭家庾大笑曰諸
孫大盛有兒如此又荅曰未若諸庾之翼翼還語人
曰我故勝得重喚奴父名



    ```
- Liu-annotation-only presence:
  - `01-dexing-046` · 德行第一 · reviewed · reader_ready=false · surface: 安國
    ```text
(第六子也少而孤貧能善樹節以儒素見稱歴侍/續晉陽秋曰孔安國字安國㑹稽山隂人車騎愉)
    ```
  - `02-yanyu-005` · 言語第二 · reviewed · reader_ready=false · surface: 孫盛
    ```text
(俱死猶差可安孫盛之言誠所未譬八歳小兒能懸/如此復何所辟裴松之以爲世語云融兒不辟知必)
    ```
  - `02-yanyu-009` · 言語第二 · reviewed · reader_ready=false · surface: 安國
    ```text
(景公有馬千駟民無德而稱焉孔安國曰千駟四千/陽十萬户號文信侯以詐獲爵故曰竊也論語曰齊)
    ```
  - `02-yanyu-022` · 言語第二 · reviewed · reader_ready=false · surface: 安國
    ```text
(心不則德義之經故徙於王都邇教誨也/成遷殷頑民作多士孔安國注曰殷大夫)
    ```
  - `02-yanyu-103` · 言語第二 · reviewed · reader_ready=false · surface: 安國
    ```text
(好色之心好賢人則善/孔安國注論語曰言以)
    ```
  - `03-zhengshi-020` · 政事第三 · reviewed · reader_ready=false · surface: 安國
    ```text
(機孔安國曰㡬㣲也/尚書臯陶謨一日萬)
    ```
  - `05-fangzheng-006` · 方正第五 · reviewed · reader_ready=false · surface: 孫盛
    ```text
(袁宏名士傳最後出不依前史以爲鍾毓可謂謬矣/事多詳覈孫盛之徒皆采以著書並云玄距鍾㑹而)
    ```
  - `05-fangzheng-016` · 方正第五 · reviewed · reader_ready=false · surface: 孫盛
    ```text
(門郎護軍將軍按王隱孫盛不與故君相聞議曰昔/春秋曰雄字茂伯河内人世語曰雄有節槩仕至黄)
    ```
  - `07-shijian-001` · 識鑒第七 · reviewed · reader_ready=false · surface: 孫盛
    ```text
(將子將納焉孫盛雜語曰太祖嘗問許子將我何如/語曰玄謂太祖君未有名可交許子將太祖乃造子)
    ```
  - `07-shijian-016` · 識鑒第七 · reviewed · reader_ready=false · surface: 孫盛
    ```text
(還之令孫盛作文嘲之成著嘉坐嘉還即荅四坐嗟/戒左右勿言以觀其舉止嘉初不覺良久如厠命取)
    ```
  - `25-paidiao-003` · 排調第二十五 · reviewed · reader_ready=false · surface: 安國
    ```text
(忠信為周阿黨為/孔安國注論語曰)
    ```
  - `25-paidiao-039` · 排調第二十五 · reviewed · reader_ready=false · surface: 安國
    ```text
(生可畏焉知來者之不如今孔安國曰後生少年/春秋傳曰齊桓公伐楚責苞茅之不貢論語曰後)
    ```
  - `27-jiajue-001` · 假譎第二十七 · reviewed · reader_ready=false · surface: 孫盛
    ```text
(語云武王少好俠放蕩不修行業甞私入常侍張讓/曹瞞傳曰操小字阿瞞少好譎詐逰放無度孫盛雜)
    ```
  - `33-youhui-017` · 尤悔第三十三 · reviewed · reader_ready=false · surface: 安國
    ```text
(不以其道得/孔安國注曰)
    ```

### 虞預 (`person-060`)

- directly participating Stories: none currently classified; main-text appearance is retained as `mentioned` pending explicit participation review.
- reviewed linked Stories: 19; reader-ready: 0; candidate links: 0; candidate contextual Mentions: 0
- main-text presence:
  - none
- Liu-annotation-only presence:
  - `01-dexing-014` · 德行第一 · reviewed · reader_ready=false · surface: 虞預
    ```text
(母故陵遲不仕年向/虞預晉書曰祥以後)
    ```
  - `01-dexing-021` · 德行第一 · reviewed · reader_ready=false · surface: 虞預
    ```text
(戎由是顯名/虞預晉書曰)
    ```
  - `02-yanyu-023` · 言語第二 · reviewed · reader_ready=false · surface: 虞預
    ```text
(晉書/虞預)
    ```
  - `02-yanyu-025` · 言語第二 · reviewed · reader_ready=false · surface: 虞預
    ```text
(輔南陽人清夷沖曠加/虞預晉書曰樂廣字彦)
    ```
  - `02-yanyu-035` · 言語第二 · reviewed · reader_ready=false · surface: 虞預
    ```text
(少標俊清徹英穎顯名為司空劉/虞預晉書曰嶠字太真太原祁人)
    ```
  - `03-zhengshi-005` · 政事第三 · reviewed · reader_ready=false · surface: 虞預
    ```text
(曰山濤字/虞預晉書)
    ```
  - `05-fangzheng-017` · 方正第五 · reviewed · reader_ready=false · surface: 虞預
    ```text
(攸子也少聦惠及長謙約好/虞預晉書曰冏字景治齊王)
    ```
  - `05-fangzheng-027` · 方正第五 · reviewed · reader_ready=false · surface: 虞預
    ```text
(協字玄亮勃海/虞預晉書曰刁)
    ```
  - `07-shijian-009` · 識鑒第七 · reviewed · reader_ready=false · surface: 虞預
    ```text
(華軼字彦夏/虞預晉書曰)
    ```
  - `08-shangyu-007` · 賞譽第八 · reviewed · reader_ready=false · surface: 虞預
    ```text
(聞喜人父潜魏太常秀有風/虞預晉書曰秀字季彦河東)
    ```
  - `08-shangyu-014` · 賞譽第八 · reviewed · reader_ready=false · surface: 虞預
    ```text
(字元夏沛國竹邑/虞預晉書曰武陔)
    ```
  - `08-shangyu-029` · 賞譽第八 · reviewed · reader_ready=false · surface: 虞預
    ```text
(紹劉漠等齊名遷尚書出爲征南将軍/虞預晉書曰簡字季倫平雅有父風與嵇)
    ```
  - `08-shangyu-043` · 賞譽第八 · reviewed · reader_ready=false · surface: 虞預
    ```text
(曰逖字士/虞預晉書)
    ```
  - `08-shangyu-054` · 賞譽第八 · reviewed · reader_ready=false · surface: 虞預
    ```text
(戴儼字若/虞預書曰)
    ```
  - `09-pinzao-016` · 品藻第九 · reviewed · reader_ready=false · surface: 虞預
    ```text
(曰嶠厚自/虞預晉書)
    ```
  - `15-zixin-002` · 自新第十五 · reviewed · reader_ready=false · surface: 虞預
    ```text
(弱登御然後髙墉之功顯孤竹在肆然後/虞預晉書曰機薦淵於趙王倫曰葢聞繁)
    ```
  - `19-xianyuan-012` · 賢媛第十九 · reviewed · reader_ready=false · surface: 虞預
    ```text
(晉陽人魏司徒昶子仕至司/虞預晉書曰渾字玄沖太原)
    ```
  - `33-youhui-006` · 尤悔第三十三 · reviewed · reader_ready=false · surface: 虞預
    ```text
(充京邑㕘軍吕/虞預晉書曰敦)
    ```
  - `33-youhui-009` · 尤悔第三十三 · reviewed · reader_ready=false · surface: 虞預
    ```text
(嶠以母亡逼賊不得往臨葬固辭詔曰嶠以/虞預晉書曰元帝即位以温嶠為散騎侍郎)
    ```

### 習鑿齒 (`person-061`)

- directly participating Stories: none currently classified; main-text appearance is retained as `mentioned` pending explicit participation review.
- reviewed linked Stories: 5; reader-ready: 0; candidate links: 0; candidate contextual Mentions: 0
- main-text presence:
  - `02-yanyu-072` · 言語第二 · reviewed · reader_ready=false · surface: 習鑿齒
    ```text
王中郎令伏玄度習鑿齒



論青楚人物










臨成以示韓康伯康伯都無言王曰何故不言
韓曰無可無不可


    ```
  - `04-wenxue-080` · 文學第四 · reviewed · reader_ready=false · surface: 習鑿齒
    ```text
習鑿齒史才不常宣武甚器之未三十便用為荆州
治中鑿齒謝牋亦云不遇明公荆州老從事耳後至
都見簡文返命宣武問見相王何如荅云一生不曽
見此人從此忤㫖出為衡陽郡性理遂錯於病中猶
作漢晉春秋品評卓逸
    ```
  - `25-paidiao-041` · 排調第二十五 · reviewed · reader_ready=false · surface: 習鑿齒
    ```text
習鑿齒孫興公未相識同在桓公坐桓語孫可與習
參軍共語孫云蠢爾蠻荆敢與大邦為讐習云薄伐
獫狁至于太原


    ```
  - `31-fenjuan-006` · 忿狷第三十一 · reviewed · reader_ready=false · surface: 習鑿齒
    ```text
王令詣謝公值習鑿齒已在坐當與併榻王徙倚不

坐公引之與對榻去後語胡兒曰子敬實自清立但
人為爾多矜咳殊足損其自然


    ```
- Liu-annotation-only presence:
  - `25-paidiao-046` · 排調第二十五 · reviewed · reader_ready=false · surface: 習鑿齒
    ```text
(說是孫綽習鑿齒言/王坦之范啓已見上)
    ```

### 郭奕 (`person-062`)

- directly participating Stories: none currently classified; main-text appearance is retained as `mentioned` pending explicit participation review.
- reviewed linked Stories: 1; reader-ready: 0; candidate links: 0; candidate contextual Mentions: 0
- main-text presence:
  - `05-fangzheng-041` · 方正第五 · reviewed · reader_ready=false · surface: 大業
    ```text
何次道庾季堅二人並爲元輔
成帝初崩于時嗣君
未定何欲立嗣子庾及朝議以外寇方强嗣子沖幼
乃立康帝康帝登
阼會群臣謂何曰朕今所以承大業爲誰之議何荅

曰陛下龍飛此是庾冰之功非臣之力于時用微臣
之議今不覩盛明之世

帝有慙色

    ```
- Liu-annotation-only presence:
  - none

### 郭象 (`person-063`)

- directly participating Stories: none currently classified; main-text appearance is retained as `mentioned` pending explicit participation review.
- reviewed linked Stories: 9; reader-ready: 0; candidate links: 0; candidate contextual Mentions: 0
- main-text presence:
  - `04-wenxue-017` · 文學第四 · reviewed · reader_ready=false · surface: 郭象
    ```text
初注荘子者數十家莫能究其㫖要向秀於舊注外
為解義妙析奇致大畼玄風





唯秋
水至樂二篇未竟而秀卒秀子㓜義遂零落然猶有
别本郭象者為人薄行有儁才
見秀義不傳於世遂
竊以為已注乃自注秋水至樂二篇又易馬蹄一篇
其餘衆篇或定㸃文句而已後
秀義别本出故今有向郭二莊其義一也

    ```
- Liu-annotation-only presence:
  - `01-dexing-033` · 德行第一 · reviewed · reader_ready=false · surface: 子少
    ```text
(衡太子少傳父裒吏部尚書奕少有器/中興書曰謝奕字無奕陳郡陽夏人祖)
    ```
  - `03-zhengshi-005` · 政事第三 · reviewed · reader_ready=false · surface: 子少
    ```text
(隱身不交世務累遷吏部尚書僕射太子少傅司徒/曰咄石生無事馬蹄閒也投傳而去果有曹爽事遂)
    ```
  - `05-fangzheng-009` · 方正第五 · reviewed · reader_ready=false · surface: 子少
    ```text
(所知每向世祖稱之歷尚書太子少傅干寳晉紀曰/南西平人父逌太常知名嶠少以雅量稱深爲賈充)
    ```
  - `06-yaliang-010` · 雅量第六 · reviewed · reader_ready=false · surface: 子少
    ```text
(王故事曰司馬越字元超高密王泰長子少尚布衣/陽王虓所䁥虓薨太傅召之大相委仗用爲長史八)
    ```
  - `07-shijian-003` · 識鑒第七 · reviewed · reader_ready=false · surface: 子少
    ```text
(徒黨鬻聲名於閭閻夏侯玄以貴臣子少有重名皆/曰是時何晏以才辯顯於貴戚之間鄧颺好交通合)
    ```
  - `08-shangyu-026` · 賞譽第八 · reviewed · reader_ready=false · surface: 郭象
    ```text
(太傅主簿任事用勢傾動一府敳謂/名士傳曰郭象字子玄自黄門郎爲)
    ```
  - `09-pinzao-064` · 品藻第九 · reviewed · reader_ready=false · surface: 子少
    ```text
(知名尚尋陽公主仕至中書郎未三十而卒坦之悼/王禕之小字也王氏世家曰禕之字文劭述次子少)
    ```
  - `11-jiewu-001` · 捷悟第十一 · reviewed · reader_ready=false · surface: 子少
    ```text
(弘農人太尉彪子少有/文士傳曰楊脩字德祖)
    ```

### 陶侃 (`person-064`)

- directly participating Stories: none currently classified; main-text appearance is retained as `mentioned` pending explicit participation review.
- reviewed linked Stories: 5; reader-ready: 0; candidate links: 0; candidate contextual Mentions: 0
- main-text presence:
  - none
- Liu-annotation-only presence:
  - `05-fangzheng-037` · 方正第五 · reviewed · reader_ready=false · surface: 陶侃
    ```text
(平陶侃欲將坦上用/按王隱晉書蘇峻事)
    ```
  - `05-fangzheng-052` · 方正第五 · reviewed · reader_ready=false · surface: 陶侃
    ```text
(諸子中最知名歷尚書秘書監何法盛以爲第九子/陶範小字也陶侃别傳曰範字道則侃第十子也侃)
    ```
  - `07-shijian-019` · 識鑒第七 · reviewed · reader_ready=false · surface: 陶侃
    ```text
(之代爲荆州何充曰陶公重勲/陶侃别傳曰庾翼薨表其子爰)
    ```
  - `14-rongzhi-023` · 容止第十四 · reviewed · reader_ready=false · surface: 陶侃
    ```text
(臣官陶侃祖約不在其例侃約疑亮寢遺詔也中/徐廣晉紀曰肅祖遺詔庾亮王導輔㓜主而進大)
    ```
  - `27-jiajue-008` · 假譎第二十七 · reviewed · reader_ready=false · surface: 陶侃
    ```text
(奔嶠人皆尤而少之嶠愈相崇重分兵以配給之/王愆期推征西陶侃為盟主俱赴京師時亮敗績)
    ```

### 孟嘉 (`person-065`)

- directly participating Stories: none currently classified; main-text appearance is retained as `mentioned` pending explicit participation review.
- reviewed linked Stories: 4; reader-ready: 0; candidate links: 0; candidate contextual Mentions: 0
- main-text presence:
  - `07-shijian-016` · 識鑒第七 · reviewed · reader_ready=false · surface: 孟嘉、萬年
    ```text
武昌孟嘉作庾太尉州從事巳知名禇太傅有知人
鑒罷豫章還過武昌問庾曰聞孟從事佳今在此不
庾云試自求之禇眄睞良乆指嘉曰此君小異得無

是乎庾大笑曰然于時既歎禇之黙識又欣嘉之見
賞








    ```
  - `18-qiyi-010` · 棲逸第十八 · reviewed · reader_ready=false · surface: 孟萬年、萬年
    ```text
孟萬年及弟少孤居武昌陽新縣萬年遊宦有盛名
當世少孤未嘗出京邑人士思欲見之乃遣信報少
孤云兄病篤狼狽至都時賢見之者莫不嗟重因相



    ```
- Liu-annotation-only presence:
  - `09-pinzao-032` · 品藻第九 · reviewed · reader_ready=false · surface: 萬年
    ```text
(下萬年後太子不得立也帝曰何故朂曰百寮内外/訊朝士皆屬目於攸而不在太子至是朂從容曰陛)
    ```
  - `15-zixin-001` · 自新第十五 · reviewed · reader_ready=false · surface: 萬年
    ```text
(曰忠孝之道何當得兩全乃進戰斬首萬計弦絶矢/齊萬年反乃令處距萬年伏波孫秀欲表處母老處)
    ```

### 卞範之 (`person-066`)

- directly participating Stories: none currently classified; main-text appearance is retained as `mentioned` pending explicit participation review.
- reviewed linked Stories: 3; reader-ready: 0; candidate links: 0; candidate contextual Mentions: 0
- main-text presence:
  - `22-chongli-006` · 寵禮第二十二 · reviewed · reader_ready=false · surface: 卞範之、敬祖
    ```text
卞範之爲丹陽尹羊孚南州暫還徃卞許云下官疾
動不堪坐卞便開帳拂褥羊徑上大牀入𬒳須枕卞
回坐傾睞移晨逹莫羊去卞語曰我以第一理期卿
卿莫負我



    ```
- Liu-annotation-only presence:
  - `02-yanyu-106` · 言語第二 · reviewed · reader_ready=false · surface: 卞範之
    ```text
(少禮其寵遇隆重兼於王卞矣及玄簒位以佐命親/引為咨議叅軍時王謐見禮而不親卞範之被親而)
    ```
  - `09-pinzao-088` · 品藻第九 · reviewed · reader_ready=false · surface: 敬祖
    ```text
(尚書僕射中軍將軍晉安帝紀/中興書曰謙字敬祖沖第三子)
    ```

### 周浚 (`person-067`)

- directly participating Stories: none currently classified; main-text appearance is retained as `mentioned` pending explicit participation review.
- reviewed linked Stories: 1; reader-ready: 0; candidate links: 0; candidate contextual Mentions: 0
- main-text presence:
  - `19-xianyuan-018` · 賢媛第十九 · reviewed · reader_ready=false · surface: 周浚、開林
    ```text
周浚作安東時行獵值㬥雨過汝南李氏李氏富足
而男子不在有女名絡秀聞外有貴人與一婢於内
宰豬羊作數十人飮食事事精辦不聞有人聲密覘
之獨見一女子狀貌非常浚因求爲妾父兄不許絡
秀曰門戸殄瘁何惜
    ```
- Liu-annotation-only presence:
  - none

### 崔遊 (`person-068`)

- directly participating Stories: none currently classified; main-text appearance is retained as `mentioned` pending explicit participation review.
- reviewed linked Stories: 4; reader-ready: 0; candidate links: 0; candidate contextual Mentions: 0
- main-text presence:
  - `05-fangzheng-043` · 方正第五 · reviewed · reader_ready=false · surface: 子相
    ```text
孔君平疾篤庾司空爲㑹稽省之相問訊甚至爲

之流涕庾既下牀孔慨然曰大丈夫將終不問安國
寧家之術廼作兒女子相問庾聞回謝之請其話言


    ```
- Liu-annotation-only presence:
  - `02-yanyu-022` · 言語第二 · reviewed · reader_ready=false · surface: 子相
    ```text
(對皆與此言不異無容二人同有此辭/按華令思舉秀才入洛與王武子相酬)
    ```
  - `02-yanyu-047` · 言語第二 · reviewed · reader_ready=false · surface: 子相
    ```text
(諱誰代子相者竪刁何如管仲曰自宫/呂氏春秋曰管仲病桓公問曰子如不)
    ```
  - `20-shujie-006` · 術解第二十 · reviewed · reader_ready=false · surface: 子相
    ```text
(之角㬥富貴後當滅門/青鳥子相冡書曰葬龍)
    ```

### 束晳 (`person-069`)

- directly participating Stories: none currently classified; main-text appearance is retained as `mentioned` pending explicit participation review.
- reviewed linked Stories: 1; reader-ready: 0; candidate links: 0; candidate contextual Mentions: 0
- main-text presence:
  - `06-yaliang-041` · 雅量第六 · reviewed · reader_ready=false · surface: 廣微、束晳
    ```text
殷荆州有所識作賦是束晳慢戲之流


殷甚以爲
有才語王恭適見新文甚可觀便於手巾函中出之
王讀殷笑之不自勝王看竟既不笑亦不言好惡但

以如意帖之而巳殷悵然自失

    ```
- Liu-annotation-only presence:
  - none

### 趙至 (`person-070`)

- directly participating Stories: none currently classified; main-text appearance is retained as `mentioned` pending explicit participation review.
- reviewed linked Stories: 2; reader-ready: 0; candidate links: 0; candidate contextual Mentions: 0
- main-text presence:
  - `19-xianyuan-032` · 賢媛第十九 · reviewed · reader_ready=false · surface: 景真
    ```text
韓康伯母殷隨孫繪之之衡陽
於闔廬洲中逢桓南郡卞鞠是其外孫時
來問訊謂鞠曰我不死見此竪二世作賊在衡陽數
年繪之遇桓景真之難也

殷撫屍哭曰汝父昔罷豫章徴書朝至夕發
汝去郡邑數年為物不得動遂及於難夫復何言

    ```
- Liu-annotation-only presence:
  - `02-yanyu-015` · 言語第二 · reviewed · reader_ready=false · surface: 趙至
    ```text
(漢末其祖流宕客緱氏令新之官/嵇紹趙至叙曰至字景眞代郡人)
    ```

### 劉遐 (`person-071`)

- directly participating Stories: none currently classified; main-text appearance is retained as `mentioned` pending explicit participation review.
- reviewed linked Stories: 1; reader-ready: 0; candidate links: 0; candidate contextual Mentions: 0
- main-text presence:
  - none
- Liu-annotation-only presence:
  - `02-yanyu-054` · 言語第二 · reviewed · reader_ready=false · surface: 劉遐
    ```text
(國之周公也足下宜以大政付之裒長史王胡之亦/裒自丹徒入朝吏部尚書劉遐勸裒曰㑹稽王令德)
    ```

### 劉隗 (`person-072`)

- directly participating Stories: none currently classified; main-text appearance is retained as `mentioned` pending explicit participation review.
- reviewed linked Stories: 2; reader-ready: 0; candidate links: 0; candidate contextual Mentions: 0
- main-text presence:
  - none
- Liu-annotation-only presence:
  - `02-yanyu-037` · 言語第二 · reviewed · reader_ready=false · surface: 劉隗
    ```text
(子弟二十餘人旦旦到公車泥首謝罪/中興書曰導從兄敦舉兵討劉隗導率)
    ```
  - `05-fangzheng-031` · 方正第五 · reviewed · reader_ready=false · surface: 劉隗
    ```text
(爲東宫庶子在承華門外與顗相/顗别傳曰王敦討劉隗時温太真)
    ```

### 吳隱之 (`person-073`)

- directly participating Stories: none currently classified; main-text appearance is retained as `mentioned` pending explicit participation review.
- reviewed linked Stories: 1; reader-ready: 0; candidate links: 0; candidate contextual Mentions: 0
- main-text presence:
  - none
- Liu-annotation-only presence:
  - `01-dexing-047` · 德行第一 · reviewed · reader_ready=false · surface: 吳隱之
    ```text
(貪泉失廉潔之性吳隱之為刺史自酌貪泉飲之題/京師歴尚書領軍將軍晉中興書曰舊云徃廣州飲)
    ```

### 干寳 (`person-074`)

- directly participating Stories: none currently classified; main-text appearance is retained as `mentioned` pending explicit participation review.
- reviewed linked Stories: 8; reader-ready: 0; candidate links: 0; candidate contextual Mentions: 0
- main-text presence:
  - none
- Liu-annotation-only presence:
  - `04-wenxue-076` · 文學第四 · reviewed · reader_ready=false · surface: 令升
    ```text
(嫚惰時有醉飽之失友人于令升戒之曰此伐性之/言造次詠語常人無異又不持儀檢形質穨索縱情)
    ```
  - `05-fangzheng-006` · 方正第五 · reviewed · reader_ready=false · surface: 干寳
    ```text
(収玄送廷尉干寳晉紀曰初豐之謀也使告玄玄荅/惡大將軍執政遂謀以玄代之大將軍聞其謀誅豐)
    ```
  - `19-xianyuan-010` · 賢媛第十九 · reviewed · reader_ready=false · surface: 干寳
    ```text
(以止汝者恐不得其所也以此并命何恨之有干寳/死垂泣謝母母顔色不變笑而謂曰人誰不死徃所)
    ```
  - `20-shujie-001` · 術解第二十 · reviewed · reader_ready=false · surface: 干寳
    ```text
(晉紀曰荀朂始造正徳大象之舞以魏杜䕫所制律/度朂今尺短四分方明咸果解音然無能正者干寳)
    ```
  - `23-rendan-002` · 任誕第二十三 · reviewed · reader_ready=false · surface: 干寳
    ```text
(曽嘗謂阮籍曰/干寳晉紀曰何)
    ```
  - `24-jianao-004` · 簡傲第二十四 · reviewed · reader_ready=false · surface: 干寳
    ```text
(安嘗從康或遇其行康兄喜拭席而待之弗顧獨坐/康聞之乃齎酒挾琴而造之遂相與善干寳晉紀曰)
    ```
  - `25-paidiao-019` · 排調第二十五 · reviewed · reader_ready=false · surface: 令升
    ```text
(奮武將軍父瑩丹陽丞寳少以博學/中興書曰寳字令升新蔡人祖正吳)
    ```
  - `36-chouxi-001` · 仇隟第三十六 · reviewed · reader_ready=false · surface: 干寳
    ```text
(緑珠美而工笛孫秀使人/干寳晉紀曰石崇有妓人)
    ```

### 徐廣 (`person-075`)

- directly participating Stories: none currently classified; main-text appearance is retained as `mentioned` pending explicit participation review.
- reviewed linked Stories: 15; reader-ready: 0; candidate links: 0; candidate contextual Mentions: 0
- main-text presence:
  - none
- Liu-annotation-only presence:
  - `02-yanyu-059` · 言語第二 · reviewed · reader_ready=false · surface: 徐廣
    ```text
(太微至二年七月猶在焉帝懲海西之事心/徐廣晉紀曰咸安元年十二月熒惑逆行入)
    ```
  - `02-yanyu-079` · 言語第二 · reviewed · reader_ready=false · surface: 徐廣
    ```text
(道季太尉亮子也風情率悟以文/道季庾龢小字徐廣晉紀曰龢字)
    ```
  - `03-zhengshi-015` · 政事第三 · reviewed · reader_ready=false · surface: 徐廣
    ```text
(綸夷險政務寛恕事從簡易/徐廣歷紀曰導阿衡三世經)
    ```
  - `05-fangzheng-029` · 方正第五 · reviewed · reader_ready=false · surface: 徐廣
    ```text
(少有重名泰興中爲騎郎蚤卒時爲悼惜之/徐廣晉紀曰顧顯字孟著吳郡人驃騎榮兄子)
    ```
  - `05-fangzheng-042` · 方正第五 · reviewed · reader_ready=false · surface: 徐廣
    ```text
(學知名兼善弈爲中興之冠累遷尚/徐廣晉紀曰江虨字思玄陳留人博)
    ```
  - `05-fangzheng-048` · 方正第五 · reviewed · reader_ready=false · surface: 徐廣
    ```text
(亮第三子拔尚率到位建威將軍吳國内史/道恩庾羲小字徐廣晉紀曰羲字叔和太和)
    ```
  - `05-fangzheng-062` · 方正第五 · reviewed · reader_ready=false · surface: 徐廣
    ```text
(彪之等啓攺作新宫太元三年二月内/徐廣晉紀曰孝武寧康二年尚書令王)
    ```
  - `06-yaliang-040` · 雅量第六 · reviewed · reader_ready=false · surface: 徐廣
    ```text
(十年九月有蓬星如/徐廣晉紀曰泰元二)
    ```
  - `08-shangyu-072` · 賞譽第八 · reviewed · reader_ready=false · surface: 徐廣
    ```text
(才具仕至太宰長史桓温以其宗彊使下邳王晃誣/字也徐廣晉紀曰倩字少彦司空氷子皇后兄也有)
    ```
  - `08-shangyu-078` · 賞譽第八 · reviewed · reader_ready=false · surface: 徐廣
    ```text
(貞審真意不顯/徐廣晉紀曰述)
    ```
  - `08-shangyu-082` · 賞譽第八 · reviewed · reader_ready=false · surface: 徐廣
    ```text
(辯玄致當時名流皆爲/徐廣晉紀曰浩清言妙)
    ```
  - `08-shangyu-094` · 賞譽第八 · reviewed · reader_ready=false · surface: 徐廣
    ```text
(江惇字思悛/徐廣晉紀曰)
    ```
  - `09-pinzao-036` · 品藻第九 · reviewed · reader_ready=false · surface: 徐廣
    ```text
(者皆舉王劉爲宗焉/徐廣晉紀曰凡稱風流)
    ```
  - `14-rongzhi-023` · 容止第十四 · reviewed · reader_ready=false · surface: 徐廣
    ```text
(臣官陶侃祖約不在其例侃約疑亮寢遺詔也中/徐廣晉紀曰肅祖遺詔庾亮王導輔㓜主而進大)
    ```
  - `25-paidiao-047` · 排調第二十五 · reviewed · reader_ready=false · surface: 徐廣
    ```text
(晉紀/徐廣)
    ```

## Proposed first multi-story pilot candidates

These 16 candidates are selected deterministically from reviewed links using only editorial flags: reader-ready representation, multiple reviewed people, main-text presence, explicit/high-confidence resolution, and canonical order. They are not importance scores or interpretations.

- `06-yaliang-019` · 雅量第六 · 王羲之、郗璿、郗鑒 · reader-ready; multiple reviewed people; main-text presence; explicit/high-confidence resolution
- `04-wenxue-094` · 文學第四 · 劉伶、向秀、山濤、嵇康、樂廣、王濬、袁宏、阮籍 · multiple reviewed people; main-text presence; explicit/high-confidence resolution
- `14-rongzhi-023` · 容止第十四 · 庾亮、徐廣、温嶠、王導、祖約、蘇峻、陶侃 · multiple reviewed people; main-text presence; explicit/high-confidence resolution
- `23-rendan-001` · 任誕第二十三 · 劉伶、向秀、山濤、嵇康、王戎、阮籍 · multiple reviewed people; main-text presence; explicit/high-confidence resolution
- `27-jiajue-008` · 假譎第二十七 · 庾亮、温嶠、王導、蘇峻、陶侃、陸機 · multiple reviewed people; main-text presence; explicit/high-confidence resolution
- `03-zhengshi-005` · 政事第三 · 和嶠、山濤、嵇康、潘岳、虞預、郭象 · multiple reviewed people; main-text presence; explicit/high-confidence resolution
- `08-shangyu-054` · 賞譽第八 · 卞壼、王導、王敦、蘇峻、虞預、謝鯤 · multiple reviewed people; main-text presence; explicit/high-confidence resolution
- `09-pinzao-006` · 品藻第九 · 王導、王戎、王敦、王祥、荀顗 · multiple reviewed people; main-text presence; explicit/high-confidence resolution
- `36-chouxi-003` · 仇隟第三十六 · 庾亮、氾騰、王導、王廙、王敦 · multiple reviewed people; main-text presence; explicit/high-confidence resolution
- `02-yanyu-047` · 言語第二 · 崔遊、張華、王隱、謝尚、陸機 · multiple reviewed people; main-text presence; explicit/high-confidence resolution
- `05-fangzheng-025` · 方正第五 · 庾亮、蘇峻、謝尚、鄧攸 · multiple reviewed people; main-text presence; explicit/high-confidence resolution
- `09-pinzao-036` · 品藻第九 · 徐廣、桓溫、王濛、謝尚 · multiple reviewed people; main-text presence; explicit/high-confidence resolution
- `25-paidiao-060` · 排調第二十五 · 劉惔、孫恩、桓溫、王敦 · multiple reviewed people; main-text presence; explicit/high-confidence resolution
- `02-yanyu-035` · 言語第二 · 劉琨、温嶠、王隱、虞預 · multiple reviewed people; main-text presence; explicit/high-confidence resolution
- `02-yanyu-072` · 言語第二 · 伏滔、桓溫、習鑿齒、韓伯 · multiple reviewed people; main-text presence; explicit/high-confidence resolution
- `05-fangzheng-027` · 方正第五 · 周顗、和嶠、王敦、虞預 · multiple reviewed people; main-text presence; explicit/high-confidence resolution

## Candidate and unresolved mentions

Medium contextual resolutions remain candidate mention evidence in the machine-readable link artifact. Unresolved title-only mentions have `person_id: null` in the existing Mention data and do not create links. No co-occurrence, relation edge, surname, Jinshu biography, or semantic similarity creates a PersonStoryLink.

The current supporting 郗璿 link is the only link without a legacy Mention ID; it is backed by the existing explicit Liu Xiaobiao evidence record and is kept visible as `link_basis: explicit_evidence` rather than creating a synthetic Mention.

- 王羲之 (`person-001`):
  - `08-shangyu-080` · main_text · `王右軍` · confidence=medium · context_identity_hits=逸少
  - `09-pinzao-028` · main_text · `王右軍` · confidence=medium · context_identity_hits=逸少
  - `14-rongzhi-024` · main_text · `右軍` · confidence=medium · context_identity_hits=王逸少,逸少
- 郗鑒 (`person-002`):
  - `06-yaliang-019` · liu_annotation · `太傅` · confidence=low · context_identity_hits=郗鑒
- 王導 (`person-003`):
  - `01-dexing-027` · liu_annotation · `丞相` · confidence=medium · context_identity_hits=王導,茂弘
  - `05-fangzheng-023` · main_text · `丞相` · confidence=medium · context_identity_hits=茂弘
  - `05-fangzheng-023` · main_text · `丞相` · confidence=medium · context_identity_hits=茂弘
  - `08-shangyu-054` · liu_annotation · `丞相` · confidence=medium · context_identity_hits=王茂弘,茂弘
  - `09-pinzao-047` · liu_annotation · `丞相` · confidence=medium · context_identity_hits=王導
  - `18-qiyi-004` · main_text · `王丞相` · confidence=low · context_identity_hits=茂弘
  - `23-rendan-032` · liu_annotation · `丞相` · confidence=medium · context_identity_hits=王導
- 謝安 (`person-006`):
  - `02-yanyu-083` · liu_annotation · `太傅` · confidence=low · context_identity_hits=謝安
  - `06-yaliang-033` · main_text · `謝太傅` · confidence=medium · context_identity_hits=謝安
  - `06-yaliang-033` · main_text · `太傅` · confidence=medium · context_identity_hits=謝安
  - `06-yaliang-033` · main_text · `太傅` · confidence=medium · context_identity_hits=謝安
  - `07-shijian-021` · main_text · `謝公` · confidence=medium · context_identity_hits=安石
  - `08-shangyu-102` · main_text · `謝公` · confidence=medium · context_identity_hits=安石
  - `10-guizhen-026` · liu_annotation · `太傅` · confidence=low · context_identity_hits=謝安
  - `25-paidiao-026` · main_text · `謝公` · confidence=medium · context_identity_hits=安石
  - `25-paidiao-038` · main_text · `謝公` · confidence=medium · context_identity_hits=安石
  - `26-qingdi-024` · main_text · `謝公` · confidence=medium · context_identity_hits=謝安
  - `26-qingdi-024` · main_text · `謝公` · confidence=medium · context_identity_hits=謝安
- 孫晷 (`person-015`):
  - `02-yanyu-079` · main_text · `文度` · confidence=low · context_identity_hits=孫晷
  - `05-fangzheng-047` · main_text · `文度` · confidence=low · context_identity_hits=孫晷
  - `05-fangzheng-047` · main_text · `文度` · confidence=low · context_identity_hits=孫晷
  - `09-pinzao-063` · main_text · `文度` · confidence=low · context_identity_hits=孫晷
  - `26-qingdi-021` · liu_annotation · `文度` · confidence=low · context_identity_hits=孫晷
- 石苞 (`person-037`):
  - `23-rendan-012` · main_text · `仲容` · confidence=low · context_identity_hits=石苞
