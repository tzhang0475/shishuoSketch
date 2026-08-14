# Person ↔ Story pilot

This is deterministic navigation/index data for the unified materialized Shishuo Person registry. The six-person pilot is the historical bootstrap stage; this index is not a personality interpretation, participation claim, or new historical assertion.

## Semantics

- Links are derived from resolved Shishuo mentions, plus the existing explicit evidence link for supporting Person `person-007` 郗璿.
- `main_text` and `liu_annotation` are source layers. Current links use `presence_kind: mentioned`; no `participant` status is inferred from appearance alone.
- A high-confidence exact-name/courtesy-name or otherwise deterministic resolved mention produces a reviewed link. Medium contextual forms remain candidate mention evidence attached to that link and never establish review by themselves.
- The PersonStoryIndex contains reviewed links only. Candidate links remain in the link artifact and are listed for human review; contextual candidate Mentions attached to a reviewed link remain candidate evidence rather than a second semantic link.
- `reader_ready` requires a canonical entry, reviewed punctuation, both original/simplified reading forms, and at least one reviewed resolved Person link. Unresolved contextual titles may remain in the source, as they do in the current reader.

## Summary

- primary people: 16
- supporting people: 1
- reviewed PersonStoryLinks: 330
- candidate PersonStoryLinks: 0
- candidate contextual mentions retained: 22
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
- reviewed linked Stories: 14; reader-ready: 0; candidate links: 0; candidate contextual Mentions: 0
- main-text presence:
  - `02-yanyu-079` · 言語第二 · reviewed · reader_ready=false · surface: 文度
    ```text
謝胡兒語庾道季
諸人莫當就卿談可堅城壘庾
曰若文度來我以偏師待之康伯來濟河焚舟


    ```
  - `05-fangzheng-047` · 方正第五 · reviewed · reader_ready=false · surface: 文度
    ```text
王述轉尚書令事行便拜文度曰故應讓杜許藍田
云汝謂我堪此不文度曰何爲不堪但克讓自是美
事恐不可闕藍田慨然曰既云堪何爲復讓人言汝
勝我定不如我


    ```
  - `05-fangzheng-058` · 方正第五 · reviewed · reader_ready=false · surface: 文度
    ```text

既還藍田愛念文度雖長大猶抱著䣛上

文度因言桓求已女㛰藍田大怒排文度下䣛曰惡
見文度已復癡畏桓温靣兵那可嫁女與之文度還
報云下官家中先得㛰處桓公曰吾知矣此尊府君
不肯耳後桓女遂嫁文度兒


    ```
  - `06-yaliang-029` · 雅量第六 · reviewed · reader_ready=false · surface: 文度
    ```text
桓公伏甲設饌廣延朝士因此欲誅謝安王坦之

王甚遽問謝曰當作何
計謝神意不變謂文度曰晉阼存亡在此一行相與
俱前王之恐狀轉見於色謝之寛容愈表於貌望階
趨席方作洛生詠諷浩浩洪流桓憚其曠逺乃趣解
兵



王謝舊齊名於此始
判優劣

    ```
  - `06-yaliang-030` · 雅量第六 · reviewed · reader_ready=false · surface: 文度
    ```text
謝太傅與王文度共詣郗超日旰未得前王便欲去
謝曰不能爲性命忍俄頃

    ```
  - `08-shangyu-126` · 賞譽第八 · reviewed · reader_ready=false · surface: 文度
    ```text
諺曰揚州獨歩王文度後來出人郗嘉賔



    ```
  - `08-shangyu-149` · 賞譽第八 · reviewed · reader_ready=false · surface: 文度
    ```text
謝車騎初見王文度曰見文度雖蕭灑相遇其復愔
愔竟夕

    ```
  - `09-pinzao-063` · 品藻第九 · reviewed · reader_ready=false · surface: 文度
    ```text
庾道季云思理倫和吾愧康伯志力彊正吾愧文度
自此以還吾皆百之

    ```
  - `23-rendan-038` · 任誕第二十三 · reviewed · reader_ready=false · surface: 文度
    ```text
桓車騎在荆州張玄為侍中使至江陵路經陽歧村
俄見一人持半小籠生魚徑來造船云
有魚欲寄作膾張乃維舟而納之問其姓字稱是劉
遺民張素聞其名大相忻待劉既
知張銜命問謝安王文度並佳不張甚欲話言劉了

無停意既進膾便去云向得此魚觀君船上當有膾
具是故來耳於是便去張乃追至劉家為設酒殊不
清㫖張高其人不得已而飲之方共封飲劉便先起
云今正伐荻不宐久廢張亦無以留之
    ```
  - `25-paidiao-046` · 排調第二十五 · reviewed · reader_ready=false · surface: 文度
    ```text
王文度范榮期俱爲簡文所要范年大而位小王年
小而位大將前更相推在前旣移乆王遂在范後王
因謂曰簸之揚之穅秕在前范曰洮之汰之沙礫在
後


    ```
  - `25-paidiao-052` · 排調第二十五 · reviewed · reader_ready=false · surface: 文度
    ```text
王文度在西州與林法師講韓孫諸人並在坐林公

理毎欲小屈孫興公曰法師今日如著弊絮在荆棘
中觸地挂閡

    ```
  - `27-jiajue-012` · 假譎第二十七 · reviewed · reader_ready=false · surface: 文度
    ```text
王文度弟阿智惡乃不翅當年長而無人與㛰孫興
公有一女亦僻錯又無嫁娶理因詣文度求見阿智

既見便陽言此定可殊不如人所傳那得至今未有
㛰處我有一女乃不惡但吾寒士不宐與卿計欲令
阿智娶之文度欣然
    ```
- Liu-annotation-only presence:
  - `02-yanyu-072` · 言語第二 · reviewed · reader_ready=false · surface: 文度
    ```text
(太原晉陽人祖東海太守/王中郎傳曰坦之字文度)
    ```
  - `26-qingdi-021` · 輕詆第二十六 · reviewed · reader_ready=false · surface: 文度
    ```text
(箸膩顔挾左傳逐鄭康成自為高足弟/中郎坦之帢㡌也裴子曰林公云文度)
    ```

### 王遐 (`person-016`)

- directly participating Stories: none currently classified; main-text appearance is retained as `mentioned` pending explicit participation review.
- reviewed linked Stories: 6; reader-ready: 0; candidate links: 0; candidate contextual Mentions: 0
- main-text presence:
  - `05-fangzheng-055` · 方正第五 · reviewed · reader_ready=false · surface: 桓子
    ```text
桓公問桓子野謝安石料萬石必敗何以不諫

子野荅曰故當出於難犯耳桓作
色曰萬石撓弱凡才有何嚴顔難犯


    ```
  - `23-rendan-033` · 任誕第二十三 · reviewed · reader_ready=false · surface: 桓子
    ```text
王劉共在杭南酣宴於桓子野家謝鎮西徃尚
書墓還葬後三日反哭諸人欲要之初遣一信猶未
許然已停車重要便回駕諸人門外迎之把臂便下
裁得脫幘箸帽酣宴半坐乃覺未脫衰



    ```
  - `23-rendan-042` · 任誕第二十三 · reviewed · reader_ready=false · surface: 桓子
    ```text
桓子野每聞清歌輙喚奈何謝公聞之曰子野可謂
一徃有深情

    ```
  - `23-rendan-049` · 任誕第二十三 · reviewed · reader_ready=false · surface: 桓子
    ```text
王子猷出都尚在渚下舊聞桓子野善吹笛


而不相識遇桓於岸上過王在船中客有
識之者云是桓子野王便令人與相聞云聞君善吹
笛試為我一奏桓時已貴顯素聞王名即便回下車
踞胡牀為作三調弄畢便上車去客主不交一言

    ```
- Liu-annotation-only presence:
  - `05-fangzheng-035` · 方正第五 · reviewed · reader_ready=false · surface: 桓子
    ```text
(許之士貞子諫而止後林父敗赤狄于曲梁賞桓子/救鄭與楚戰於邲晉師敗績桓子歸請死晉平公將)
    ```
  - `26-qingdi-020` · 輕詆第二十六 · reviewed · reader_ready=false · surface: 桓子
    ```text
(製也初邕避難江南宿於柯亭之館以竹為椽邕仰/同寮桓子野有故長笛傳之耆老云蔡邕伯喈之所)
    ```

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

## Proposed first multi-story pilot candidates

These 16 candidates are selected deterministically from reviewed links using only editorial flags: reader-ready representation, multiple reviewed people, main-text presence, explicit/high-confidence resolution, and canonical order. They are not importance scores or interpretations.

- `06-yaliang-019` · 雅量第六 · 王羲之、郗璿、郗鑒 · reader-ready; multiple reviewed people; main-text presence; explicit/high-confidence resolution
- `05-fangzheng-055` · 方正第五 · 劉惔、王濛、王遐、謝安 · multiple reviewed people; main-text presence; explicit/high-confidence resolution
- `06-yaliang-029` · 雅量第六 · 孫晷、桓溫、王導、謝安 · multiple reviewed people; main-text presence; explicit/high-confidence resolution
- `27-jiajue-008` · 假譎第二十七 · 庾亮、温嶠、王導、蘇峻 · multiple reviewed people; main-text presence; explicit/high-confidence resolution
- `14-rongzhi-023` · 容止第十四 · 庾亮、温嶠、王導、蘇峻 · multiple reviewed people; main-text presence; explicit/high-confidence resolution
- `02-yanyu-102` · 言語第二 · 桓溫、温嶠、王導、蘇峻 · multiple reviewed people; explicit/high-confidence resolution
- `06-yaliang-017` · 雅量第六 · 庾亮、温嶠、蘇峻 · multiple reviewed people; main-text presence; explicit/high-confidence resolution
- `11-jiewu-005` · 捷悟第十一 · 温嶠、王導、王敦 · multiple reviewed people; main-text presence; explicit/high-confidence resolution
- `25-paidiao-060` · 排調第二十五 · 劉惔、桓溫、王敦 · multiple reviewed people; main-text presence; explicit/high-confidence resolution
- `02-yanyu-101` · 言語第二 · 桓溫、袁宏、謝安 · multiple reviewed people; main-text presence; explicit/high-confidence resolution
- `23-rendan-033` · 任誕第二十三 · 劉惔、王濛、王遐 · multiple reviewed people; main-text presence; explicit/high-confidence resolution
- `25-paidiao-026` · 排調第二十五 · 王凝之、謝安、謝道韞 · multiple reviewed people; main-text presence; explicit/high-confidence resolution
- `36-chouxi-003` · 仇隟第三十六 · 庾亮、王導、王敦 · multiple reviewed people; main-text presence; explicit/high-confidence resolution
- `02-yanyu-090` · 言語第二 · 桓溫、袁宏、謝安 · multiple reviewed people; explicit/high-confidence resolution
- `04-wenxue-022` · 文學第四 · 庾亮、王導、王濛 · multiple reviewed people; explicit/high-confidence resolution
- `08-shangyu-054` · 賞譽第八 · 王導、王敦、蘇峻 · multiple reviewed people; explicit/high-confidence resolution

## Candidate and unresolved mentions

Medium contextual resolutions remain candidate mention evidence in the machine-readable link artifact. Unresolved title-only mentions have `person_id: null` in the existing Mention data and do not create links. No co-occurrence, relation edge, surname, Jinshu biography, or semantic similarity creates a PersonStoryLink.

The current supporting 郗璿 link is the only link without a legacy Mention ID; it is backed by the existing explicit Liu Xiaobiao evidence record and is kept visible as `link_basis: explicit_evidence` rather than creating a synthetic Mention.

- 王羲之 (`person-001`):
  - `08-shangyu-080` · main_text · `王右軍` · confidence=medium · context_identity_hits=逸少
  - `09-pinzao-028` · main_text · `王右軍` · confidence=medium · context_identity_hits=逸少
  - `14-rongzhi-024` · main_text · `右軍` · confidence=medium · context_identity_hits=王逸少,逸少
- 郗鑒 (`person-002`):
  - `06-yaliang-019` · liu_annotation · `太傅` · confidence=medium · context_identity_hits=郗鑒
- 王導 (`person-003`):
  - `01-dexing-027` · liu_annotation · `丞相` · confidence=medium · context_identity_hits=王導,茂弘
  - `05-fangzheng-023` · main_text · `丞相` · confidence=medium · context_identity_hits=茂弘
  - `05-fangzheng-023` · main_text · `丞相` · confidence=medium · context_identity_hits=茂弘
  - `08-shangyu-054` · liu_annotation · `丞相` · confidence=medium · context_identity_hits=王茂弘,茂弘
  - `09-pinzao-047` · liu_annotation · `丞相` · confidence=medium · context_identity_hits=王導
  - `18-qiyi-004` · main_text · `王丞相` · confidence=medium · context_identity_hits=茂弘
  - `23-rendan-032` · liu_annotation · `丞相` · confidence=medium · context_identity_hits=王導
- 謝安 (`person-006`):
  - `02-yanyu-083` · liu_annotation · `太傅` · confidence=medium · context_identity_hits=謝安
  - `06-yaliang-033` · main_text · `謝太傅` · confidence=medium · context_identity_hits=謝安
  - `06-yaliang-033` · main_text · `太傅` · confidence=medium · context_identity_hits=謝安
  - `06-yaliang-033` · main_text · `太傅` · confidence=medium · context_identity_hits=謝安
  - `07-shijian-021` · main_text · `謝公` · confidence=medium · context_identity_hits=安石
  - `08-shangyu-102` · main_text · `謝公` · confidence=medium · context_identity_hits=安石
  - `10-guizhen-026` · liu_annotation · `太傅` · confidence=medium · context_identity_hits=謝安
  - `25-paidiao-026` · main_text · `謝公` · confidence=medium · context_identity_hits=安石
  - `25-paidiao-038` · main_text · `謝公` · confidence=medium · context_identity_hits=安石
  - `26-qingdi-024` · main_text · `謝公` · confidence=medium · context_identity_hits=謝安
  - `26-qingdi-024` · main_text · `謝公` · confidence=medium · context_identity_hits=謝安
