# SFH2.2-F1 Semantic Audit Bundle

This is a candidate-only production audit. It contains no Gold judgment and makes no unseen-corpus accuracy claim.

## 1. 01-dexing-008 / 季方

- occurrence_id: `sfh1-mention-fb979fe0b42ef4d06939f630`
- mention_id: `sfh1-mention-fb979fe0b42ef4d06939f630`
- source_evidence_id: `sfh1-ev-01-dexing-008-liu-annotation-004`
- offsets: `2:4`
- source layer: `liu_annotation`
- exact target: `季方`
- context:
  - `main_text` `sfh1-ev-01-dexing-008-main`: 陳元方子長文有英才

與季方子孝先各論
其父功德爭之不能决咨於太丘太丘曰元方難為
兄季方難為弟
  - `liu_annotation` `sfh1-ev-01-dexing-008-liu-annotation-001`: (謂宗人曰此兒必興吾宗及/魏書曰陳羣字長文祖寔嘗)
  - `liu_annotation` `sfh1-ev-01-dexing-008-liu-annotation-002`: (所善皆父黨/長有識度其)
  - `liu_annotation` `sfh1-ev-01-dexing-008-liu-annotation-003`: (字孝先州辟不就/陳氏譜曰諶子忠)
  - `liu_annotation` `sfh1-ev-01-dexing-008-liu-annotation-004`: (弟季方難為兄/一作元方難為)
- identity status: `resolved`
- identity: `{"abstain": false, "attribute_type": "", "attribute_value": "", "bearer_hint": "", "reference_type": "courtesy_name", "referent": {"canonical_hint": "陳諶", "confidence": "high", "surface_form": "陳諶"}, "semantic_kind": "historical_person"}`
- identity candidate proposal: `{"candidate_only": true, "candidate_origin": "llm_semantic_proposal_registry_miss", "candidate_person_id": "sfh2-a0-candidate-person-587ede0dd5b24a81412f", "canonical_write_back": false, "display_name": "陳諶", "entity_type": "candidate_historical_person", "person_id": "", "proposed_display_name": "陳諶", "referent_canonical_hint": "陳諶", "source_occurrence_ids": ["sfh1-mention-fb979fe0b42ef4d06939f630"], "supporting_evidence_ids": ["sfh1-ev-01-dexing-008-liu-annotation-003", "sfh1-ev-01-dexing-008-liu-annotation-004", "sfh1-ev-01-dexing-008-main"]}`
- A2OR primary: `reference` (medium)
- A2OR reason: The target occurrence "季方" appears in the Liu annotation fragment "(弟季方難為兄/一作元方難為)" which is a variant-text note quoting/echoing the main text's phrase about 元方 and 季方 being hard to be elder/younger brother. In this annotation context, 季方 is simply referred to/mentioned as part of the quoted variant phrasing. The occurrence does not itself perform speaker, addressee, citation_source, genealogy, attribute, collective, or exemplum functions within this annotation fragment. It is a plain reference to the person 季方 within the annotation's textual variant note.
- A2OVB boundary: `referential_only` (high)
- A2OVB reason: The target occurrence "季方" appears in the Liu annotation fragment "(弟季方難為兄/一作元方難為)". This is a variant-text annotation noting an alternative reading of the main text's phrase "季方難為弟" (季方 is hard to be a younger brother). The occurrence is part of a textual/critical annotation comparing variant readings, not a narrated event in which 季方 (陳諶) participates as an actor or patient. The phrase "難為弟" is an evaluation/description of 季方's relational position, not an event involving him as a participant. This is referential-only mention within an annotation apparatus.
- final function: `reference`
- legacy projection: `annotation_person`
- review status: `mandatory_review`
- review triggers: `invalid_provider_contract, new_historical_person_candidate, policy_defined_stage_disagreement`
- audit flags: `none`

## 2. 09-pinzao-040 / 孔巖

- occurrence_id: `sfh1-mention-ba0a6bfd3b70867199867b3a`
- mention_id: `sfh1-mention-ba0a6bfd3b70867199867b3a`
- source_evidence_id: `sfh1-ev-09-pinzao-040-main`
- offsets: `17:19`
- source layer: `main_text`
- exact target: `孔巖`
- context:
  - `main_text` `sfh1-ev-09-pinzao-040-main`: 簡文云謝安南清令不如其弟
學義不及孔巖
居然自勝
  - `liu_annotation` `sfh1-ev-09-pinzao-040-liu-annotation-001`: (氏譜曰奉弟聘字弘/安南謝奉也巳見謝)
  - `liu_annotation` `sfh1-ev-09-pinzao-040-liu-annotation-002`: (廷尉卿/逺歴侍中)
  - `liu_annotation` `sfh1-ev-09-pinzao-040-liu-annotation-003`: (山隂人父儉黄門侍郎巖/中興書曰巖字彭祖會稽)
  - `liu_annotation` `sfh1-ev-09-pinzao-040-liu-annotation-004`: (匡正爲吳興太守大得民和後卒于家/有才學歴丹陽尹尚書西陽侯在朝多所)
  - `liu_annotation` `sfh1-ev-09-pinzao-040-liu-annotation-005`: (天真也/言奉任)
- identity status: `resolved`
- identity: `{"abstain": false, "attribute_type": "", "attribute_value": "", "bearer_hint": "", "reference_type": "full_name", "referent": {"canonical_hint": "孔巖", "confidence": "high", "surface_form": "孔巖"}, "semantic_kind": "historical_person"}`
- identity candidate proposal: `{"candidate_only": true, "candidate_origin": "llm_semantic_proposal_registry_miss", "candidate_person_id": "sfh2-a0-candidate-person-29b136644b842fb3eb46", "canonical_write_back": false, "display_name": "孔巖", "entity_type": "candidate_historical_person", "person_id": "", "proposed_display_name": "孔巖", "referent_canonical_hint": "孔巖", "source_occurrence_ids": ["sfh1-mention-ba0a6bfd3b70867199867b3a"], "supporting_evidence_ids": ["sfh1-ev-09-pinzao-040-liu-annotation-003", "sfh1-ev-09-pinzao-040-liu-annotation-004", "sfh1-ev-09-pinzao-040-main"]}`
- A2OR primary: `participant` (high)
- A2OR reason: The target occurrence 孔巖 appears in the main text where 簡文 (Emperor Jianwen) states that 謝安南's learning/righteousness does not match 孔巖's. 孔巖 is the object of comparison in the narrated statement — he is the person being compared against in the evaluation. He is not the speaker (簡文 is), not the addressee, not a citation source, not a collective, not a genealogy reference, and not merely a descriptive attribute. He is an active participant in the narrated comparison/evaluation event, being the standard against which 謝安南 is measured. Thus participant is the most fitting function.
- A2OVB boundary: `referential_only` (high)
- A2OVB reason: The text reads: 簡文云謝安南清令不如其弟 / 學義不及孔巖 / 居然自勝. Emperor Jianwen (簡文) is making an evaluative comparison: Xie Annan's learning and righteousness does not measure up to (不及) Kong Yan. The occurrence of 孔巖 functions as the comparison standard in an evaluative judgment about Xie Annan's qualities. Kong Yan is not an actor, patient, experiencer, or participant in any narrated event at this occurrence; he is merely the referential object against whom Xie Annan is being compared. This is a classic referential-only mention in a comparative evaluation.
- final function: `reference`
- legacy projection: `scene_reference`
- review status: `mandatory_review`
- review triggers: `new_historical_person_candidate`
- audit flags: `boundary_override, primary_boundary_disagreement`

## 3. 34-pilou-006 / 殷公

- occurrence_id: `sfh1-mention-250c0ae68551d8dab4943ed8`
- mention_id: `sfh1-mention-250c0ae68551d8dab4943ed8`
- source_evidence_id: `sfh1-ev-34-pilou-006-main`
- offsets: `23:25`
- source layer: `main_text`
- exact target: `殷公`
- context:
  - `main_text` `sfh1-ev-34-pilou-006-main`: 殷仲堪父病虚悸聞牀下蟻動謂是牛鬬

孝武不知是殷公問仲堪有一殷病如此不仲堪流

涕而起曰臣進退唯谷
  - `liu_annotation` `sfh1-ev-34-pilou-006-liu-annotation-001`: (殷師字師/殷氏譜曰)
  - `liu_annotation` `sfh1-ev-34-pilou-006-liu-annotation-002`: (秋曰仲堪父曽有失心病仲堪腰不解帶彌年父卒/子祖識父融並有名師至驃騎咨議生仲堪續晉陽)
  - `liu_annotation` `sfh1-ev-34-pilou-006-liu-annotation-003`: (注曰谷窮也/大雅詩也毛公)
- identity status: `blocked`
- identity: `{}`
- identity candidate proposal: `null`
- A2OR primary: `None` (None)
- A2OR reason:
- final function: `None`
- legacy projection: `None`
- review status: `mandatory_review`
- review triggers: `identity_adjudication_unresolved, invalid_provider_contract, provider_failure`
- audit flags: `none`

## 4. 08-shangyu-020 / 剌史

- occurrence_id: `sfh1-mention-ab9210bb6f88d713e884fe26`
- mention_id: `sfh1-mention-ab9210bb6f88d713e884fe26`
- source_evidence_id: `sfh1-ev-08-shangyu-020-liu-annotation-008`
- offsets: `18:20`
- source layer: `liu_annotation`
- exact target: `剌史`
- context:
  - `main_text` `sfh1-ev-08-shangyu-020-main`: 有問秀才吳舊姓何如荅曰吳府君聖王之老成明
時之儁乂朱永長理物之至德清選之高望嚴仲弼
九臯之鳴鶴空谷之白駒顧彦先八音之琴瑟五色
之龍章張威伯歲寒之茂松幽夜之逸光陸士衡士
龍鴻鵠之裵回懸鼔之待槌








凡此諸
君以洪筆爲鉏耒以𥿄札爲良田以玄黙爲稼穡以
義理爲豐年以談論爲英華以忠恕爲珍寳著文章
爲錦繡藴五經爲繒帛坐謙虚爲席薦張義讓爲帷
幙行仁義爲室宇修道德爲廣宅
  - `liu_annotation` `sfh1-ev-08-shangyu-020-liu-annotation-001`: (剌史周俊書曰一日侍/秀才蔡洪也集載洪與)
  - `liu_annotation` `sfh1-ev-08-shangyu-020-liu-annotation-002`: (舉敕令條列名狀退輒思之今稱䟽所知吳展字士/坐言及吳士詢于芻蕘遂見下問造次承顔載辭不)
  - `liu_annotation` `sfh1-ev-08-shangyu-020-liu-annotation-003`: (仕吳爲廣州剌史吳郡太守吳平還下邳閉門自守/季下邳人忠足矯非清足厲俗信可結神才堪榦世)
  - `liu_annotation` `sfh1-ev-08-shangyu-020-liu-annotation-004`: (長吳郡人體履清和黄中通理吳朝舉賢良累遷議/不交賔客誠聖王之老成明時之儁乂也朱誕字永)
  - `liu_annotation` `sfh1-ev-08-shangyu-020-liu-annotation-005`: (仲弼吳郡人禀氣清純思度淵偉吳朝舉賢良宛陵/郎今歸在家誠理物之至德清選之高望也嚴隱字)
  - `liu_annotation` `sfh1-ev-08-shangyu-020-liu-annotation-006`: (伯吳郡人禀性堅明志行清朗居磨涅之中無淄磷/令吳平去職九臯之鳴鶴空谷之白駒也張畼字威)
  - `liu_annotation` `sfh1-ev-08-shangyu-020-liu-annotation-007`: (士龍吳大司馬抗之第五子機同母之弟也儒雅有/之損歲寒之松栢幽夜之逸光也陸雲别傳曰雲字)
  - `liu_annotation` `sfh1-ev-08-shangyu-020-liu-annotation-008`: (能賦詩時人以爲項託掦烏之疇也年十八剌史周/俊才容貌瓌偉口敏能談博聞彊記善著述六歲便)
  - `liu_annotation` `sfh1-ev-08-shangyu-020-liu-annotation-009`: (也累遷太子舍人清河内史爲成都王所害/俊命爲主簿俊常嘆曰陸士龍當今之顔淵)
  - `liu_annotation` `sfh1-ev-08-shangyu-020-liu-annotation-010`: (人無陸機兄弟又/按蔡所論士十六)
  - `liu_annotation` `sfh1-ev-08-shangyu-020-liu-annotation-011`: (以下疑益之/無凡此諸君)
- identity status: `resolved`
- identity: `{"abstain": false, "attribute_type": "", "attribute_value": "", "bearer_hint": "周俊", "reference_type": "office_title", "referent": {"canonical_hint": "剌史", "confidence": "high", "surface_form": "剌史"}, "semantic_kind": "office"}`
- identity candidate proposal: `null`
- A2OR primary: `reference` (medium)
- A2OR reason: The target occurrence "剌史" (office title for 周俊) appears in the Liu Xiaobiao annotation at annotation-008: "年十八剌史周俊命爲主簿" (at age eighteen, Inspector Zhou Jun appointed him as registrar). The occurrence is an office title used to identify 周俊, who is the agent performing the action of appointing 陸雲 as 主簿. The office title functions as part of the identification of the person 周俊 within the narrated biographical account. It does not itself perform a more specific function (not speaker, addressee, citation source, exemplum, genealogy, collective, or attribute). The occurrence refers to/identifies the person 周俊 via his office title within the narrative of the annotation. Thus it functions as a reference to the person in the narrated context.
- A2OVB boundary: `None` (None)
- A2OVB reason:
- final function: `reference`
- legacy projection: `annotation_person`
- review status: `mandatory_review`
- review triggers: `invalid_provider_contract, provider_failure`
- audit flags: `none`

## 5. 05-fangzheng-055 / 子野

- occurrence_id: `sfh1-mention-4212d15b7a219584954587d8`
- mention_id: `sfh1-mention-4212d15b7a219584954587d8`
- source_evidence_id: `sfh1-ev-05-fangzheng-055-main`
- offsets: `4:6`
- source layer: `main_text`
- exact target: `子野`
- context:
  - `main_text` `sfh1-ev-05-fangzheng-055-main`: 桓公問桓子野謝安石料萬石必敗何以不諫

子野荅曰故當出於難犯耳桓作
色曰萬石撓弱凡才有何嚴顔難犯
  - `liu_annotation` `sfh1-ev-05-fangzheng-055-liu-annotation-001`: (桓伊/子野)
  - `liu_annotation` `sfh1-ev-05-fangzheng-055-liu-annotation-002`: (將軍伊少有才蓺又善聲律加以標悟省率爲王蒙/小字也續晉陽秋曰伊字叔夏譙國銍人父景護軍)
  - `liu_annotation` `sfh1-ev-05-fangzheng-055-liu-annotation-003`: (州剌史贈右將軍/劉惔所知累遷豫)
- identity status: `resolved`
- identity: `{"abstain": false, "attribute_type": "", "attribute_value": "", "bearer_hint": "", "reference_type": "courtesy_name", "referent": {"canonical_hint": "桓伊", "confidence": "high", "surface_form": "桓伊"}, "semantic_kind": "historical_person"}`
- identity candidate proposal: `{"candidate_only": true, "candidate_origin": "llm_semantic_proposal_registry_miss", "candidate_person_id": "sfh2-a0-candidate-person-096a4840c340494f35a4", "canonical_write_back": false, "display_name": "桓伊", "entity_type": "candidate_historical_person", "person_id": "", "proposed_display_name": "桓伊", "referent_canonical_hint": "桓伊", "source_occurrence_ids": ["sfh1-mention-4212d15b7a219584954587d8"], "supporting_evidence_ids": ["sfh1-ev-05-fangzheng-055-liu-annotation-001", "sfh1-ev-05-fangzheng-055-main"]}`
- A2OR primary: `speaker` (high)
- A2OR reason: The target occurrence "子野" appears at the start of the second clause "子野荅曰故當出於難犯耳" where 子野 (桓子野/桓伊) is the one who answers (荅曰). This occurrence directly identifies the speaker of the quoted utterance that follows. The discourse context confirms 桓公 asks the question and 子野 responds, making this occurrence a speaker self-identification within the utterance.
- final function: `speaker`
- legacy projection: `speaker_reference`
- review status: `mandatory_review`
- review triggers: `new_historical_person_candidate, policy_defined_stage_disagreement`
- audit flags: `none`

## 6. 25-paidiao-028 / 堯

- occurrence_id: `sfh1-mention-2d1f96737b7b0ef11588f7e5`
- mention_id: `sfh1-mention-2d1f96737b7b0ef11588f7e5`
- source_evidence_id: `sfh1-ev-25-paidiao-028-liu-annotation-001`
- offsets: `26:27`
- source layer: `liu_annotation`
- exact target: `堯`
- context:
  - `main_text` `sfh1-ev-25-paidiao-028-main`: 支道林因人就深公買印山深公荅曰未聞巢由買
山而隱
  - `liu_annotation` `sfh1-ev-25-paidiao-028-liu-annotation-001`: (年老以樹為巢而寢其上故號巢父髙逸沙/逸士傳曰巢父者堯時隱人山居不營世利)
  - `liu_annotation` `sfh1-ev-25-paidiao-028-liu-annotation-002`: (之言慙恧而已/門傳曰遁得深公)
- identity status: `resolved`
- identity: `{"abstain": false, "attribute_type": "", "attribute_value": "", "bearer_hint": "", "reference_type": "ruler_title", "referent": {"canonical_hint": "堯", "confidence": "high", "surface_form": "堯"}, "semantic_kind": "historical_person"}`
- identity candidate proposal: `{"candidate_only": true, "candidate_origin": "llm_semantic_proposal_registry_miss", "candidate_person_id": "sfh2-a0-candidate-person-73d8d001b4cabecfafb3", "canonical_write_back": false, "display_name": "堯", "entity_type": "candidate_historical_person", "person_id": "", "proposed_display_name": "堯", "referent_canonical_hint": "堯", "source_occurrence_ids": ["sfh1-mention-2d1f96737b7b0ef11588f7e5"], "supporting_evidence_ids": ["sfh1-ev-25-paidiao-028-liu-annotation-001"]}`
- A2OR primary: `historical_exemplum` (high)
- A2OR reason: The target occurrence 堯 appears in Liu Xiaobiao's annotation quoting the 逸士傳, which describes 巢父 as "堯時隱人" (a recluse of the time of Yao). The annotation is providing historical background about 巢父, who is invoked in the main text as a comparison/exemplum (the main text mentions 巢由 buying a mountain to hide). 堯 here functions as a temporal-historical anchor identifying the era of the exemplary figure 巢父, serving as explanatory historical background for the current discourse. This fits historical_exemplum: a historical entity invoked as explanatory historical background.
- final function: `historical_exemplum`
- legacy projection: `historical_exemplum`
- review status: `mandatory_review`
- review triggers: `new_historical_person_candidate, policy_defined_stage_disagreement`
- audit flags: `none`

## 7. 05-fangzheng-058 / 王文度

- occurrence_id: `sfh1-mention-b6fa0b811087b18b0774e8f9`
- mention_id: `sfh1-mention-b6fa0b811087b18b0774e8f9`
- source_evidence_id: `sfh1-ev-05-fangzheng-058-main`
- offsets: `0:3`
- source layer: `main_text`
- exact target: `王文度`
- context:
  - `main_text` `sfh1-ev-05-fangzheng-058-main`: 王文度爲桓公長史時桓爲兒求王女王許咨藍田
既還藍田愛念文度雖長大猶抱著䣛上

文度因言桓求已女㛰藍田大怒排文度下䣛曰惡
見文度已復癡畏桓温靣兵那可嫁女與之文度還
報云下官家中先得㛰處桓公曰吾知矣此尊府君
不肯耳後桓女遂嫁文度兒
  - `liu_annotation` `sfh1-ev-05-fangzheng-058-liu-annotation-001`: (述並巳見/王坦之王)
  - `liu_annotation` `sfh1-ev-05-fangzheng-058-liu-annotation-002`: (桓温第二女字伯子中/王氏譜曰坦之子愷娶)
  - `liu_annotation` `sfh1-ev-05-fangzheng-058-liu-annotation-003`: (國内史丹陽尹贈太常/興書曰愷字茂仁歷吳)
- identity status: `blocked`
- identity: `{}`
- identity candidate proposal: `null`
- A2OR primary: `None` (None)
- A2OR reason:
- final function: `None`
- legacy projection: `None`
- review status: `mandatory_review`
- review triggers: `identity_adjudication_unresolved, invalid_provider_contract, provider_failure`
- audit flags: `none`

## 8. 09-pinzao-008 / 諸名士

- occurrence_id: `sfh1-mention-acaffc0cd7c6899e24eb9ee9`
- mention_id: `sfh1-mention-acaffc0cd7c6899e24eb9ee9`
- source_evidence_id: `sfh1-ev-09-pinzao-008-main`
- offsets: `8:11`
- source layer: `main_text`
- exact target: `諸名士`
- context:
  - `main_text` `sfh1-ev-09-pinzao-008-main`: 劉令言始入洛
見諸名士而歎曰王夷甫太解明樂彦輔我所敬
張茂先我所不解周弘武巧於用短
杜方叔拙於用長
  - `liu_annotation` `sfh1-ev-09-pinzao-008-liu-annotation-001`: (瑾樂安長父甝魏洛陽令納歷司隷/劉氏譜曰納字令言彭城叢亭人祖)
  - `liu_annotation` `sfh1-ev-09-pinzao-008-liu-annotation-002`: (尉/校)
  - `liu_annotation` `sfh1-ev-09-pinzao-008-liu-annotation-003`: (恢字弘武汝南/王隱晉書曰周)
  - `liu_annotation` `sfh1-ev-09-pinzao-008-liu-annotation-004`: (事恢仕至秦相秩中二千石/人祖斐永寧少府父隆州從)
  - `liu_annotation` `sfh1-ev-09-pinzao-008-liu-annotation-005`: (公賛/晉諸)
  - `liu_annotation` `sfh1-ev-09-pinzao-008-liu-annotation-006`: (號神童及長美風姿有才藻時人號曰杜聖累遷國/曰杜育字方叔襄城鄧陵人杜襲孫也育㓜便岐嶷)
  - `liu_annotation` `sfh1-ev-09-pinzao-008-liu-annotation-007`: (没爲賊所殺/子祭酒洛陽將)
- identity status: `not_applicable`
- identity: `{}`
- identity candidate proposal: `null`
- A2OR primary: `collective_reference` (high)
- A2OR reason: The target occurrence "諸名士" (the various famous scholars) is a collective person reference denoting a group of people whom Liu Lingyan saw upon entering Luoyang. The validated local mention classifies it as "collective_person_reference." In the narrative, it denotes a collective entity (the assembled famous scholars) rather than a single individual performing a specific function. It is not a speaker, addressee, citation source, exemplum, or attribute expression. It functions as a collective reference to the group of people being observed and commented upon.
- final function: `collective_reference`
- legacy projection: `collective_reference`
- review status: `no_mandatory_review`
- review triggers: `none`
- audit flags: `none`

## 9. 01-dexing-028 / 兒

- occurrence_id: `sfh1-mention-edd76871090fb1cad57dcd9c`
- mention_id: `sfh1-mention-edd76871090fb1cad57dcd9c`
- source_evidence_id: `sfh1-ev-01-dexing-028-liu-annotation-006`
- offsets: `2:3`
- source layer: `liu_annotation`
- exact target: `兒`
- context:
  - `main_text` `sfh1-ev-01-dexing-028-main`: 鄧攸始避難於道中棄己子全弟子






既過江取一妾甚寵愛
歴年後訊其所由妾具說是北人遭亂憶父母姓名
乃攸之甥也攸素有德業言行無玷聞之哀恨終身
遂不復畜妾
  - `liu_annotation` `sfh1-ev-01-dexing-028-liu-annotation-001`: (伯道平陽襄陵/晉陽秋曰攸字)
  - `liu_annotation` `sfh1-ev-01-dexing-028-liu-annotation-002`: (粲晉紀曰永嘉中攸為石勒所獲召見立幕下與語/人七歲喪父母及祖父母持重九年性清慎平簡鄧)
  - `liu_annotation` `sfh1-ev-01-dexing-028-liu-annotation-003`: (車營勒吏案問胡胡誣攸攸度不可與爭乃曰向為/說之坐而飯焉攸車所止與胡人鄰轂胡人失火燒)
  - `liu_annotation` `sfh1-ev-01-dexing-028-liu-annotation-004`: (德攸遺其驢馬䕶送令得逸王隱晉書曰攸以路逺/老姥作粥失火延逸罪應萬死勒知遣之所誣胡厚)
  - `liu_annotation` `sfh1-ev-01-dexing-028-liu-annotation-005`: (曰吾弟早亡唯有遺民今當步走儋兩兒盡死不如/斫壞車以牛馬負妻子以叛賊又掠其牛馬攸語妻)
  - `liu_annotation` `sfh1-ev-01-dexing-028-liu-annotation-006`: (棄兒於草中兒啼呼追之至莫復及攸明日繋兒於/棄己兒抱遺民吾後猶當有兒婦從之中興書曰攸)
  - `liu_annotation` `sfh1-ev-01-dexing-028-liu-annotation-007`: (射卒弟子綏服攸齊衰三年/樹而去遂渡江至尚書左僕)
- identity status: `blocked`
- identity: `{}`
- identity candidate proposal: `null`
- A2OR primary: `None` (None)
- A2OR reason:
- final function: `None`
- legacy projection: `None`
- review status: `mandatory_review`
- review triggers: `identity_adjudication_unresolved, invalid_provider_contract, provider_failure`
- audit flags: `none`

## 10. 19-xianyuan-026 / 謝家

- occurrence_id: `sfh1-mention-e5a5f3d5367f63de75fca0b0`
- mention_id: `sfh1-mention-e5a5f3d5367f63de75fca0b0`
- source_evidence_id: `sfh1-ev-19-xianyuan-026-main`
- offsets: `16:18`
- source layer: `main_text`
- exact target: `謝家`
- context:
  - `main_text` `sfh1-ev-19-xianyuan-026-main`: 王凝之謝夫人既徃王氏太薄凝之既還謝家意大
不說太傅慰釋之曰王郎逸少之子人身亦不惡汝
何以恨廼爾荅曰一門叔父則有阿大中郞羣從兄
弟則有封胡遏末

不意天壤之中乃有王郎
  - `liu_annotation` `sfh1-ev-19-xianyuan-026-liu-annotation-001`: (字穆度萬子車騎司馬淵字叔度/封胡謝韶小字遏末謝淵小字韶)
  - `liu_annotation` `sfh1-ev-19-xianyuan-026-liu-annotation-002`: (遏末封謂朗遏謂玄末謂韶朗玄淵一作胡謂淵遏/奕第二子義興太守時人稱其尤彦秀者或曰封胡)
  - `liu_annotation` `sfh1-ev-19-xianyuan-026-liu-annotation-003`: (謂韶也/謂玄末)
- identity status: `not_applicable`
- identity: `{}`
- identity candidate proposal: `null`
- A2OR primary: `collective_reference` (high)
- A2OR reason: The target occurrence "謝家" (the Xie family/clan) is a surname-based collective reference denoting the Xie household as a group. In the text, 王凝之 returns to the Xie family home (既還謝家), referring to the collective family unit rather than an individual person. The validated_local_mentions also classify this occurrence as "collective_person_reference" with reference_form "surname_reference." The occurrence denotes a collective entity (the Xie family), fitting the collective_reference narrative function.
- final function: `collective_reference`
- legacy projection: `collective_reference`
- review status: `no_mandatory_review`
- review triggers: `none`
- audit flags: `none`

## 11. 05-fangzheng-055 / 桓子野

- occurrence_id: `sfh1-mention-c051c79699ee2334eccc5086`
- mention_id: `sfh1-mention-c051c79699ee2334eccc5086`
- source_evidence_id: `sfh1-ev-05-fangzheng-055-main`
- offsets: `3:6`
- source layer: `main_text`
- exact target: `桓子野`
- context:
  - `main_text` `sfh1-ev-05-fangzheng-055-main`: 桓公問桓子野謝安石料萬石必敗何以不諫

子野荅曰故當出於難犯耳桓作
色曰萬石撓弱凡才有何嚴顔難犯
  - `liu_annotation` `sfh1-ev-05-fangzheng-055-liu-annotation-001`: (桓伊/子野)
  - `liu_annotation` `sfh1-ev-05-fangzheng-055-liu-annotation-002`: (將軍伊少有才蓺又善聲律加以標悟省率爲王蒙/小字也續晉陽秋曰伊字叔夏譙國銍人父景護軍)
  - `liu_annotation` `sfh1-ev-05-fangzheng-055-liu-annotation-003`: (州剌史贈右將軍/劉惔所知累遷豫)
- identity status: `resolved`
- identity: `{"abstain": false, "attribute_type": "", "attribute_value": "", "bearer_hint": "", "reference_type": "full_name", "referent": {"canonical_hint": "桓伊", "confidence": "high", "surface_form": "桓伊"}, "semantic_kind": "historical_person"}`
- identity candidate proposal: `{"candidate_only": true, "candidate_origin": "llm_semantic_proposal_registry_miss", "candidate_person_id": "sfh2-a0-candidate-person-096a4840c340494f35a4", "canonical_write_back": false, "display_name": "桓伊", "entity_type": "candidate_historical_person", "person_id": "", "proposed_display_name": "桓伊", "referent_canonical_hint": "桓伊", "source_occurrence_ids": ["sfh1-mention-c051c79699ee2334eccc5086"], "supporting_evidence_ids": ["sfh1-ev-05-fangzheng-055-liu-annotation-001", "sfh1-ev-05-fangzheng-055-liu-annotation-002", "sfh1-ev-05-fangzheng-055-main"]}`
- A2OR primary: `addressee` (high)
- A2OR reason: The target occurrence "桓子野" appears in the main text: "桓公問桓子野謝安石料萬石必敗何以不諫". Here 桓公 (桓公) asks 桓子野 a question. The discourse context confirms speaker_hint is 桓公 and addressee_hint is 桓子野. The target occurrence is the direct recipient of the question posed by 桓公, making it the addressee of the utterance.
- final function: `addressee`
- legacy projection: `addressee_reference`
- review status: `mandatory_review`
- review triggers: `new_historical_person_candidate, policy_defined_stage_disagreement`
- audit flags: `none`

## 12. 06-yaliang-033 / 祖端

- occurrence_id: `sfh1-mention-2c6672ce7bffaa6f16181810`
- mention_id: `sfh1-mention-2c6672ce7bffaa6f16181810`
- source_evidence_id: `sfh1-ev-06-yaliang-033-liu-annotation-002`
- offsets: `15:17`
- source layer: `liu_annotation`
- exact target: `祖端`
- context:
  - `main_text` `sfh1-ev-06-yaliang-033-main`: 謝安南免吏部尚書還東
謝太傅赴桓公司
馬出西相遇破岡既當逺别遂停三日共語太傅欲

慰其失官安南輒引以它端雖信宿中塗竟不言及
此事太傅深恨在心未盡謂同舟曰謝奉故是竒士
  - `liu_annotation` `sfh1-ev-06-yaliang-033-liu-annotation-001`: (會稽山隂人謝氏譜曰奉/晉百官名曰謝奉字弘道)
  - `liu_annotation` `sfh1-ev-06-yaliang-033-liu-annotation-002`: (歷安南將軍廣州剌史吏部尚書/祖端散騎常侍父鳯丞相主簿奉)
- identity status: `resolved`
- identity: `{"abstain": false, "attribute_type": "", "attribute_value": "", "bearer_hint": "", "reference_type": "kinship_reference", "referent": {"canonical_hint": "謝端", "confidence": "high", "surface_form": "謝端"}, "semantic_kind": "historical_person"}`
- identity candidate proposal: `{"candidate_only": true, "candidate_origin": "llm_semantic_proposal_registry_miss", "candidate_person_id": "sfh2-a0-candidate-person-5b5b9cf6628ff5a66efa", "canonical_write_back": false, "display_name": "謝端", "entity_type": "candidate_historical_person", "person_id": "", "proposed_display_name": "謝端", "referent_canonical_hint": "謝端", "source_occurrence_ids": ["sfh1-mention-2c6672ce7bffaa6f16181810"], "supporting_evidence_ids": ["sfh1-ev-06-yaliang-033-liu-annotation-002"]}`
- A2OR primary: `genealogy_reference` (high)
- A2OR reason: The target occurrence "祖端" (grandfather Duan) appears in Liu Xiaobiao's annotation providing genealogical information about 謝奉 (Xie Feng). The annotation states "祖端散騎常侍父鳯丞相主簿奉" — identifying 端 as 謝奉's grandfather (祖). The occurrence performs kinship/genealogical identification, explicitly marking the familial relationship between 端 and 謝奉. This is a genealogy_reference function.
- final function: `genealogy_reference`
- legacy projection: `genealogy_reference`
- review status: `mandatory_review`
- review triggers: `invalid_provider_contract, new_historical_person_candidate, policy_defined_stage_disagreement, provider_failure`
- audit flags: `none`

## 13. 01-dexing-014 / 祥

- occurrence_id: `sfh1-mention-ff73ef4d86b3e237614ab6af`
- mention_id: `sfh1-mention-ff73ef4d86b3e237614ab6af`
- source_evidence_id: `sfh1-ev-01-dexing-014-main`
- offsets: `1:2`
- source layer: `main_text`
- exact target: `祥`
- context:
  - `main_text` `sfh1-ev-01-dexing-014-main`: 王祥事後母朱夫人甚謹



家有一李樹結子殊好母恒使守之時風雨
忽至祥抱樹而泣
祥嘗在别牀眠母自徃闇斫
之值祥私起空斫得被既還知母憾之不巳因跪前

請死母於是感悟愛之如己子
  - `liu_annotation` `sfh1-ev-01-dexing-014-liu-annotation-001`: (邪臨沂人祥世家曰祥父/晉諸公贊曰祥字休徵琅)
  - `liu_annotation` `sfh1-ev-01-dexing-014-liu-annotation-002`: (曰後母數譖祥屢以非理使祥弟覽輙與祥俱又虐/融娶髙平薛氏生祥繼室以廬江朱氏生覽晉陽秋)
  - `liu_annotation` `sfh1-ev-01-dexing-014-liu-annotation-003`: (魚祥解衣将剖氷求之㑹有處氷小解魚出蕭廣濟/使祥婦覽妻亦趨而共之母患方盛寒氷凍母欲生)
  - `liu_annotation` `sfh1-ev-01-dexing-014-liu-annotation-004`: (數十黄雀飛入其幕母之所須必自奔走無不得焉/孝子傳曰祥後母忽欲黄雀炙祥念難卒致須臾有)
  - `liu_annotation` `sfh1-ev-01-dexing-014-liu-annotation-006`: (李始結子使祥晝視鳥雀夜則趍/蕭廣濟孝子傳曰祥後母庭中有)
  - `liu_annotation` `sfh1-ev-01-dexing-014-liu-annotation-007`: (泣至曉母見之惻然/鼠一夜風雨大至祥抱)
  - `liu_annotation` `sfh1-ev-01-dexing-014-liu-annotation-008`: (母故陵遲不仕年向/虞預晉書曰祥以後)
  - `liu_annotation` `sfh1-ev-01-dexing-014-liu-annotation-009`: (康寔賴王祥邦國不空别駕之功累遷太保/六十刺史呂䖍檄為别駕時人歌之曰海沂之)
- identity status: `resolved`
- identity: `{"abstain": false, "attribute_type": "", "attribute_value": "", "bearer_hint": "", "reference_type": "personal_name", "referent": {"canonical_hint": "王祥", "confidence": "high", "surface_form": "王祥"}, "semantic_kind": "historical_person"}`
- identity candidate proposal: `{"candidate_only": true, "candidate_origin": "python_registry_lookup_after_llm_semantics", "candidate_person_id": "", "canonical_write_back": false, "display_name": "王祥", "entity_type": "existing_person", "person_id": "person-036", "proposed_display_name": "王祥", "referent_canonical_hint": "王祥"}`
- A2OR primary: `participant` (high)
- A2OR reason: The target occurrence "祥" (Wang Xiang) at position 1-2 in the main text refers to the protagonist actively participating in the narrated events. In the sentence "忽至祥抱樹而泣" (suddenly wind and rain arrived, Xiang hugged the tree and wept), Wang Xiang is the subject performing the action of hugging the tree and weeping. He is an active participant in the narrated event, not serving as speaker, addressee, citation source, exemplum, or any other more specific function. The occurrence is a direct narrative participant in the story about his filial piety toward his stepmother.
- A2OVB boundary: `event_participant` (high)
- A2OVB reason: The target occurrence "祥" (source_start 1, source_end 2) is the second character of "王祥" at the very beginning of the main text: "王祥事後母朱夫人甚謹". Here 王祥 is the subject/actor of the verb 事 (to serve/attend to), making him an active participant in the narrated event of serving his stepmother with great care. This is genuine event participation, not a referential-only mention.
- final function: `participant`
- legacy projection: `scene_participant`
- review status: `mandatory_review`
- review triggers: `invalid_provider_contract, policy_defined_stage_disagreement`
- audit flags: `none`

## 14. 02-yanyu-066 / 卿

- occurrence_id: `sfh1-mention-7754db159dd2508a0e0966b1`
- mention_id: `sfh1-mention-7754db159dd2508a0e0966b1`
- source_evidence_id: `sfh1-ev-02-yanyu-066-main`
- offsets: `17:18`
- source layer: `main_text`
- exact target: `卿`
- context:
  - `main_text` `sfh1-ev-02-yanyu-066-main`: 王長史與劉真長别後相見

王謂劉曰卿更
長進荅曰此若天之自髙耳
  - `liu_annotation` `sfh1-ev-02-yanyu-066-liu-annotation-001`: (仲祖太原晉陽人其/王長史别傳曰濛字)
  - `liu_annotation` `sfh1-ev-02-yanyu-066-liu-annotation-002`: (訥葉令濛神氣清韶年十餘歲放邁不羣弱冠檢尚/先出自周室經漢魏世為大族祖父佐北軍中候父)
  - `liu_annotation` `sfh1-ev-02-yanyu-066-liu-annotation-003`: (徒掾中書郎以后父贈光禄大夫/風流雅正外絶榮競内寡私欲辟司)
  - `liu_annotation` `sfh1-ev-02-yanyu-066-liu-annotation-004`: (卿近大進劉曰卿仰看/語林曰仲祖語真長曰)
  - `liu_annotation` `sfh1-ev-02-yanyu-066-liu-annotation-005`: (爾何由測天之髙也/邪王問何意劉曰不)
- identity status: `resolved`
- identity: `{"abstain": false, "attribute_type": "", "attribute_value": "", "bearer_hint": "", "reference_type": "pronoun_reference", "referent": {"canonical_hint": "劉惔", "confidence": "high", "surface_form": "劉真長"}, "semantic_kind": "historical_person"}`
- identity candidate proposal: `{"candidate_only": true, "candidate_origin": "python_registry_lookup_after_llm_semantics", "candidate_person_id": "", "canonical_write_back": false, "display_name": "劉惔", "entity_type": "existing_person", "person_id": "person-009", "proposed_display_name": "劉惔", "referent_canonical_hint": "劉惔"}`
- A2OR primary: `addressee` (high)
- A2OR reason: The target occurrence "卿" (you) appears in the main text "王謂劉曰卿更長進" where 王長史 (Wang Changshi) addresses 劉真長 (Liu Zhenchang). The discourse context confirms speaker_hint is 王長史 and addressee_hint is 劉真長. The pronoun "卿" is the direct vocative/address form used by the speaker to address Liu Zhenchang within the quoted utterance, making it an addressee occurrence.
- final function: `addressee`
- legacy projection: `addressee_reference`
- review status: `mandatory_review`
- review triggers: `policy_defined_stage_disagreement`
- audit flags: `none`

## 15. 24-jianao-001 / 何曽

- occurrence_id: `sfh1-mention-14aadf84022adda0aa99308b`
- mention_id: `sfh1-mention-14aadf84022adda0aa99308b`
- source_evidence_id: `sfh1-ev-24-jianao-001-liu-annotation-002`
- offsets: `14:16`
- source layer: `liu_annotation`
- exact target: `何曽`
- context:
  - `main_text` `sfh1-ev-24-jianao-001-main`: 晉文王功德盛大坐席嚴敬擬於王者
唯阮籍在坐箕踞嘯歌酣放

自若
  - `liu_annotation` `sfh1-ev-24-jianao-001-liu-annotation-001`: (文王進爵為/漢晉春秋曰)
  - `liu_annotation` `sfh1-ev-24-jianao-001-liu-annotation-002`: (盡禮唯王祥長揖不拜/王司徒何曽與朝臣皆)
- identity status: `resolved`
- identity: `{"abstain": false, "attribute_type": "", "attribute_value": "", "bearer_hint": "", "reference_type": "full_name", "referent": {"canonical_hint": "何曾", "confidence": "high", "surface_form": "何曾"}, "semantic_kind": "historical_person"}`
- identity candidate proposal: `{"candidate_only": true, "candidate_origin": "llm_semantic_proposal_registry_miss", "candidate_person_id": "sfh2-a0-candidate-person-330ba714eb3b19282394", "canonical_write_back": false, "display_name": "何曾", "entity_type": "candidate_historical_person", "person_id": "", "proposed_display_name": "何曾", "referent_canonical_hint": "何曾", "source_occurrence_ids": ["sfh1-mention-14aadf84022adda0aa99308b"], "supporting_evidence_ids": ["sfh1-ev-24-jianao-001-liu-annotation-002"]}`
- A2OR primary: `participant` (medium)
- A2OR reason: The target occurrence 何曽 appears in Liu Xiaobiao's annotation quoting a passage (likely from 漢晉春秋) that describes how, when 文王 received the title, only 王祥 performed a long bow without prostrating, while 王司徒何曽 and the court officials all [performed full ritual]. 何曽 is named as one of the participants in the narrated event of the court officials' ritual behavior. He is not the speaker, addressee, citation source, exemplum, or bearer of an attribute; he is an active participant in the described historical scene within the annotation's quoted content.
- A2OVB boundary: `event_participant` (medium)
- A2OVB reason: The annotation text reads "王司徒何曽與朝臣皆" (Minister of Works He Zeng, together with the court officials, all...). The fragment indicates that He Zeng, along with the court officials, performed some action (likely related to showing ritual respect, contrasting with Wang Xiang who only bowed without prostrating). This places He Zeng as an actor participating in a narrated event of ritual conduct, not merely a referential mention.
- final function: `participant`
- legacy projection: `annotation_person`
- review status: `mandatory_review`
- review triggers: `invalid_provider_contract, new_historical_person_candidate, policy_defined_stage_disagreement`
- audit flags: `none`

## 16. 01-dexing-023 / 湘州刺史

- occurrence_id: `sfh1-mention-e2c43c63a28c758a1c1192f1`
- mention_id: `sfh1-mention-e2c43c63a28c758a1c1192f1`
- source_evidence_id: `sfh1-ev-01-dexing-023-liu-annotation-001`
- offsets: `16:20`
- source layer: `liu_annotation`
- exact target: `湘州刺史`
- context:
  - `main_text` `sfh1-ev-01-dexing-023-main`: 王平子胡母彦國諸人皆以任放為達或有祼體者


樂廣
笑曰名教中自有樂地何為乃爾也
  - `liu_annotation` `sfh1-ev-01-dexing-023-liu-annotation-001`: (人名曰胡母輔之字彦國泰山奉髙人湘州刺史王/晉諸公贊曰王澄字平子有達識荆州刺史永嘉流)
  - `liu_annotation` `sfh1-ev-01-dexing-023-liu-annotation-002`: (其後貴游子弟阮瞻王澄謝鯤胡母輔之之徒皆祖/隱晉書曰魏末阮籍嗜酒荒放露頭散髮裸袒箕踞)
  - `liu_annotation` `sfh1-ev-01-dexing-023-liu-annotation-003`: (惡同禽獸甚者名之為通次者名之為達也/述於籍謂得大道之本故去巾幘脫衣服露醜)
- identity status: `resolved`
- identity: `{"abstain": false, "attribute_type": "office_held", "attribute_value": "湘州刺史", "bearer_hint": "胡母輔之", "reference_type": "office_title", "referent": {"canonical_hint": "湘州刺史", "confidence": "high", "surface_form": "湘州刺史"}, "semantic_kind": "office"}`
- identity candidate proposal: `null`
- A2OR primary: `person_attribute` (high)
- A2OR reason: The target occurrence "湘州刺史" is an office title (office_held attribute) identifying the office held by 胡母輔之 within the Liu Xiaobiao annotation. The frozen identity confirms attribute_type is "office_held" with attribute_value "湘州刺史". The occurrence itself expresses an attribute (the office held) of the bearer 胡母輔之, functioning as a person_attribute expression rather than a participant, reference, or other narrative function.
- final function: `person_attribute`
- legacy projection: `person_attribute`
- review status: `mandatory_review`
- review triggers: `policy_defined_stage_disagreement`
- audit flags: `none`

## 17. 07-shijian-019 / 爰

- occurrence_id: `sfh1-mention-63d90ef457a6a2419f9b1588`
- mention_id: `sfh1-mention-63d90ef457a6a2419f9b1588`
- source_evidence_id: `sfh1-ev-07-shijian-019-liu-annotation-003`
- offsets: `25:26`
- source layer: `liu_annotation`
- exact target: `爰`
- context:
  - `main_text` `sfh1-ev-07-shijian-019-main`: 小庾臨終自表以子園客爲代
朝廷慮其不從命
未知所遣乃共議用桓温劉尹曰使伊去必能克定
西楚然恐不可復制
  - `liu_annotation` `sfh1-ev-07-shijian-019-liu-annotation-001`: (氏譜曰爰之字仲眞/園客爰之小字也庾)
  - `liu_annotation` `sfh1-ev-07-shijian-019-liu-annotation-002`: (風桓温徙于豫章年三十六而卒/翼弟二子中興書曰爰之有父翼)
  - `liu_annotation` `sfh1-ev-07-shijian-019-liu-annotation-003`: (之代爲荆州何充曰陶公重勲/陶侃别傳曰庾翼薨表其子爰)
  - `liu_annotation` `sfh1-ev-07-shijian-019-liu-annotation-004`: (親則道恩優㳺散騎未有超卓若此之授乃以徐州/也臨終高讓丞相未薨敬豫爲四品將軍于今不攺)
  - `liu_annotation` `sfh1-ev-07-shijian-019-liu-annotation-005`: (翼表其子代任朝廷畏憚之議者欲以授桓温時簡/刺史桓温爲安西將軍荆州刺史宋明帝文章志曰)
  - `liu_annotation` `sfh1-ev-07-shijian-019-liu-annotation-006`: (制願大王自鎮上流惔請爲從軍司馬簡文不許温/文輔政然之劉惔曰温去必能定西楚然恐不能復)
  - `liu_annotation` `sfh1-ev-07-shijian-019-liu-annotation-007`: (所筭也/後果如惔)
- identity status: `resolved`
- identity: `{"abstain": false, "attribute_type": "", "attribute_value": "", "bearer_hint": "", "reference_type": "personal_name", "referent": {"canonical_hint": "庾爰之", "confidence": "high", "surface_form": "爰之"}, "semantic_kind": "historical_person"}`
- identity candidate proposal: `{"candidate_only": true, "candidate_origin": "llm_semantic_proposal_registry_miss", "candidate_person_id": "sfh2-a0-candidate-person-be86131bfd97b9f0f535", "canonical_write_back": false, "display_name": "庾爰之", "entity_type": "candidate_historical_person", "person_id": "", "proposed_display_name": "庾爰之", "referent_canonical_hint": "庾爰之", "source_occurrence_ids": ["sfh1-mention-63d90ef457a6a2419f9b1588"], "supporting_evidence_ids": ["sfh1-ev-07-shijian-019-liu-annotation-001", "sfh1-ev-07-shijian-019-liu-annotation-002", "sfh1-ev-07-shijian-019-liu-annotation-003"]}`
- A2OR primary: `reference` (medium)
- A2OR reason: The target occurrence "爰" appears in the Liu annotation quoting the 陶侃别傳: "庾翼薨表其子爰" (Yu Yi on his death memorialized his son Yuan). The occurrence refers to 庾爰之 (Yu Yuanzhi), the son of 庾翼, who was proposed as successor to his father's post. The occurrence is within quoted historical/biographical material from the 陶侃别傳, functioning as a plain reference to the person within that cited narrative. It does not itself perform speaker, addressee, citation_source, genealogy, attribute, collective, or exemplum functions — it simply names the person being discussed in the quoted source material.
- A2OVB boundary: `event_participant` (high)
- A2OVB reason: The target occurrence "爰" appears in the Liu annotation text: "陶侃别傳曰庾翼薨表其子爰" (Tao Kan's biography says: when Yu Yi died, he memorialized [requesting] his son Yuan [Ai Zhi] [to succeed him]). The character 爰 here is the object of the verb 表 (to memorialize/request), referring to Yu Yi's son Ai Zhi being formally proposed as successor. This is a narrated event — Yu Yi's memorializing his son as replacement — in which Ai Zhi (爰/爰之) is the patient/recipient of the memorial action. He is genuinely involved in the narrated event of being nominated/succeeded, not merely mentioned referentially. The occurrence describes an actual historical action (the memorial requesting his appointment) that directly involves him as the person being put forward.
- final function: `participant`
- legacy projection: `annotation_person`
- review status: `mandatory_review`
- review triggers: `new_historical_person_candidate, policy_defined_stage_disagreement`
- audit flags: `boundary_override, primary_boundary_disagreement`

## 18. 08-shangyu-020 / 陸機

- occurrence_id: `sfh1-mention-b4f58ecca05c3c538d559feb`
- mention_id: `sfh1-mention-b4f58ecca05c3c538d559feb`
- source_evidence_id: `sfh1-ev-08-shangyu-020-liu-annotation-010`
- offsets: `3:5`
- source layer: `liu_annotation`
- exact target: `陸機`
- context:
  - `main_text` `sfh1-ev-08-shangyu-020-main`: 有問秀才吳舊姓何如荅曰吳府君聖王之老成明
時之儁乂朱永長理物之至德清選之高望嚴仲弼
九臯之鳴鶴空谷之白駒顧彦先八音之琴瑟五色
之龍章張威伯歲寒之茂松幽夜之逸光陸士衡士
龍鴻鵠之裵回懸鼔之待槌








凡此諸
君以洪筆爲鉏耒以𥿄札爲良田以玄黙爲稼穡以
義理爲豐年以談論爲英華以忠恕爲珍寳著文章
爲錦繡藴五經爲繒帛坐謙虚爲席薦張義讓爲帷
幙行仁義爲室宇修道德爲廣宅
  - `liu_annotation` `sfh1-ev-08-shangyu-020-liu-annotation-001`: (剌史周俊書曰一日侍/秀才蔡洪也集載洪與)
  - `liu_annotation` `sfh1-ev-08-shangyu-020-liu-annotation-002`: (舉敕令條列名狀退輒思之今稱䟽所知吳展字士/坐言及吳士詢于芻蕘遂見下問造次承顔載辭不)
  - `liu_annotation` `sfh1-ev-08-shangyu-020-liu-annotation-003`: (仕吳爲廣州剌史吳郡太守吳平還下邳閉門自守/季下邳人忠足矯非清足厲俗信可結神才堪榦世)
  - `liu_annotation` `sfh1-ev-08-shangyu-020-liu-annotation-004`: (長吳郡人體履清和黄中通理吳朝舉賢良累遷議/不交賔客誠聖王之老成明時之儁乂也朱誕字永)
  - `liu_annotation` `sfh1-ev-08-shangyu-020-liu-annotation-005`: (仲弼吳郡人禀氣清純思度淵偉吳朝舉賢良宛陵/郎今歸在家誠理物之至德清選之高望也嚴隱字)
  - `liu_annotation` `sfh1-ev-08-shangyu-020-liu-annotation-006`: (伯吳郡人禀性堅明志行清朗居磨涅之中無淄磷/令吳平去職九臯之鳴鶴空谷之白駒也張畼字威)
  - `liu_annotation` `sfh1-ev-08-shangyu-020-liu-annotation-007`: (士龍吳大司馬抗之第五子機同母之弟也儒雅有/之損歲寒之松栢幽夜之逸光也陸雲别傳曰雲字)
  - `liu_annotation` `sfh1-ev-08-shangyu-020-liu-annotation-008`: (能賦詩時人以爲項託掦烏之疇也年十八剌史周/俊才容貌瓌偉口敏能談博聞彊記善著述六歲便)
  - `liu_annotation` `sfh1-ev-08-shangyu-020-liu-annotation-009`: (也累遷太子舍人清河内史爲成都王所害/俊命爲主簿俊常嘆曰陸士龍當今之顔淵)
  - `liu_annotation` `sfh1-ev-08-shangyu-020-liu-annotation-010`: (人無陸機兄弟又/按蔡所論士十六)
  - `liu_annotation` `sfh1-ev-08-shangyu-020-liu-annotation-011`: (以下疑益之/無凡此諸君)
- identity status: `resolved`
- identity: `{"abstain": false, "attribute_type": "", "attribute_value": "", "bearer_hint": "", "reference_type": "full_name", "referent": {"canonical_hint": "陸機", "confidence": "high", "surface_form": "陸機"}, "semantic_kind": "historical_person"}`
- identity candidate proposal: `{"candidate_only": true, "candidate_origin": "python_registry_lookup_after_llm_semantics", "candidate_person_id": "", "canonical_write_back": false, "display_name": "陸機", "entity_type": "existing_person", "person_id": "person-026", "proposed_display_name": "陸機", "referent_canonical_hint": "陸機"}`
- A2OR primary: `reference` (medium)
- A2OR reason: The target occurrence 陸機 appears in the Liu annotation fragment "(人無陸機兄弟又/按蔡所論士十六)". This is part of the commentator's annotation discussing the people listed by Cai (蔡洪). The occurrence of 陸機 here refers to the person 陸機 in the context of the annotation's commentary about the list of scholars discussed. It is not the speaker, addressee, citation source, historical exemplum, genealogy reference, collective reference, or person attribute. It functions as a reference to the historical person within the annotation's discussion. The fragment is incomplete and the surrounding context is partially obscured, but the occurrence appears to simply refer to 陸機 as one of the persons under discussion in the annotation, making "reference" the most appropriate classification.
- A2OVB boundary: `referential_only` (high)
- A2OVB reason: The target occurrence "陸機" appears in Liu Xiaobiao's annotation text: "(人無陸機兄弟又/按蔡所論士十六)". This is a commentarial note stating that among the people discussed by Cai (蔡), there were none like the Lu brothers (陸機兄弟). The occurrence is purely referential — it names 陸機 as part of a comparison/evaluation about who was included in Cai's list of sixteen scholars. 陸機 is not participating in any narrated event at this occurrence; he is merely referenced as a comparison standard or as someone whose absence from the list is being noted. This is referential-only mention.
- final function: `reference`
- legacy projection: `annotation_person`
- review status: `mandatory_review`
- review triggers: `invalid_provider_contract, policy_defined_stage_disagreement`
- audit flags: `none`

## 19. 04-wenxue-097 / 宏

- occurrence_id: `sfh1-mention-60f9d5ff179ecbdd321e88fc`
- mention_id: `sfh1-mention-60f9d5ff179ecbdd321e88fc`
- source_evidence_id: `sfh1-ev-04-wenxue-097-liu-annotation-003`
- offsets: `1:2`
- source layer: `liu_annotation`
- exact target: `宏`
- context:
  - `main_text` `sfh1-ev-04-wenxue-097-main`: 袁宏始作東征賦都不道陶公胡奴誘之狹室中臨
以白刄曰先公勲業如是君作東征賦云何
相忽略宏窘蹙無計便荅我大道公何以云無因誦
曰精金百鍊在割能斷功則治人職思靖亂長沙之
勲為史所讃
  - `liu_annotation` `sfh1-ev-04-wenxue-097-liu-annotation-001`: (範别見/胡奴陶)
  - `liu_annotation` `sfh1-ev-04-wenxue-097-liu-annotation-002`: (為東征賦悉稱過江諸名望時桓温在/續晉陽秋曰宏為大司馬記室叅軍後)
  - `liu_annotation` `sfh1-ev-04-wenxue-097-liu-annotation-003`: (宏善苦諌之宏笑而不荅滔宻以啓温温甚忿以宏/南州宏語衆云我决不及桓宣城時伏滔在温府與)
  - `liu_annotation` `sfh1-ev-04-wenxue-097-liu-annotation-004`: (山飲酌既歸公命宏同載衆為危懼行數里問宏曰/一時文宗又聞此賦有聲不欲令人顯問之後逰青)
  - `liu_annotation` `sfh1-ev-04-wenxue-097-liu-annotation-005`: (公稱謂自非下官所敢専故未呈啓不敢顯之耳温/聞君作東征賦多稱先賢何故不及家君宏荅曰尊)
  - `liu_annotation` `sfh1-ev-04-wenxue-097-liu-annotation-006`: (雖可亡道不可隕則宣城之節信為允也温泫然而/乃云君欲為何辭宏即荅云風鑒散朗或&KR0679;或引身)
  - `liu_annotation` `sfh1-ev-04-wenxue-097-liu-annotation-007`: (故詳載焉/止二説不同)
- identity status: `resolved`
- identity: `{"abstain": false, "attribute_type": "", "attribute_value": "", "bearer_hint": "", "reference_type": "personal_name", "referent": {"canonical_hint": "袁宏", "confidence": "high", "surface_form": "袁宏"}, "semantic_kind": "historical_person"}`
- identity candidate proposal: `{"candidate_only": true, "candidate_origin": "python_registry_lookup_after_llm_semantics", "candidate_person_id": "", "canonical_write_back": false, "display_name": "袁宏", "entity_type": "existing_person", "person_id": "person-012", "proposed_display_name": "袁宏", "referent_canonical_hint": "袁宏"}`
- A2OR primary: `participant` (high)
- A2OR reason: The target occurrence "宏" (Yuan Hong) in liu-annotation-003 appears in the clause "宏善苦諌之宏笑而不荅滔宻以啓温温甚忿以宏/南州宏語衆云我决不及桓宣城". Here Yuan Hong is the subject who actively participates in the narrated events: he remonstrates (苦諌), laughs without answering (笑而不荅), and speaks to the crowd (語衆云). The occurrence is not performing a more specific function such as speaker self-reference within quoted speech, addressee, citation source, exemplum, genealogy, or attribute. It is an active participant in the narrative events described in the annotation. The subsequent "我" pronoun in the same clause is the speaker self-reference within the quoted utterance, but this target occurrence "宏" is the narrative subject introducing that speech, functioning as a participant in the narrated event.
- A2OVB boundary: `event_participant` (high)
- A2OVB reason: The target occurrence "宏" (Yuan Hong) at the start of annotation-003 appears in the clause "宏善苦諌之" — Yuan Hong earnestly remonstrated/admonished (someone). This is a narrated event in which Yuan Hong is the actor performing the action of remonstrating. This is genuine event participation, not merely a referential mention.
- final function: `participant`
- legacy projection: `annotation_person`
- review status: `mandatory_review`
- review triggers: `policy_defined_stage_disagreement`
- audit flags: `none`

## 20. 36-chouxi-003 / 王敦

- occurrence_id: `sfh1-mention-e07789c3e12569ce9624526e`
- mention_id: `sfh1-mention-e07789c3e12569ce9624526e`
- source_evidence_id: `sfh1-ev-36-chouxi-003-liu-annotation-001`
- offsets: `13:15`
- source layer: `liu_annotation`
- exact target: `王敦`
- context:
  - `main_text` `sfh1-ev-36-chouxi-003-main`: 王大將軍執司馬愍王夜遣世將載王於車而殺之
當時不盡知也


雖愍王家亦
未之皆悉而無忌兄弟皆稺

王胡之與無忌長甚相暱胡之甞共
遊無忌入告母請為饌母流涕曰王敦昔肆酷汝父
假手世將

吾所以積年不告汝
者王氏門彊汝兄弟尚幼不欲使此聲著葢以避禍
耳無忌驚號抽刃而出胡之去已逺
  - `liu_annotation` `sfh1-ev-36-chouxi-003-liu-annotation-001`: (也為中宗相州刺史路過武昌王敦/晉陽秋曰司馬丞字元敬譙王遜子)
  - `liu_annotation` `sfh1-ev-36-chouxi-003-liu-annotation-002`: (曰焉知鈆刀不能一割乎敦將謀逆召丞為軍司馬/與燕㑹酒酣謂丞曰大王篤實佳士非將御之才對)
  - `liu_annotation` `sfh1-ev-36-chouxi-003-liu-annotation-003`: (死王事義也死忠與義又何求焉乃馳檄諸郡丞赴/丞嘆曰吾其死矣地荒民解勢孤援絶赴君難忠也)
  - `liu_annotation` `sfh1-ev-36-chouxi-003-liu-annotation-004`: (之薨於車敦既滅追贈驃騎諡曰愍王/義敦遣從母弟魏乂攻丞王廙使賊迎)
  - `liu_annotation` `sfh1-ev-36-chouxi-003-liu-annotation-005`: (夀丞子也才器兼濟有/無忌别傳曰無忌字公)
  - `liu_annotation` `sfh1-ev-36-chouxi-003-liu-annotation-006`: (王衛軍將軍/文武幹襲封譙)
  - `liu_annotation` `sfh1-ev-36-chouxi-003-liu-annotation-007`: (曰廙字世將祖覽父正廙髙朗豪率王導/司馬氏譜曰丞娶南陽趙氏女王廙别傳)
  - `liu_annotation` `sfh1-ev-36-chouxi-003-liu-annotation-008`: (嘯神氣甚逸導謂亮曰世將為復識事亮曰正足舒/庾亮遊于石頭㑹廙至爾日迅風飛颿廙倚船樓長)
- identity status: `resolved`
- identity: `{"abstain": false, "attribute_type": "", "attribute_value": "", "bearer_hint": "", "reference_type": "full_name", "referent": {"canonical_hint": "王敦", "confidence": "high", "surface_form": "王敦"}, "semantic_kind": "historical_person"}`
- identity candidate proposal: `{"candidate_only": true, "candidate_origin": "python_registry_lookup_after_llm_semantics", "candidate_person_id": "", "canonical_write_back": false, "display_name": "王敦", "entity_type": "existing_person", "person_id": "person-011", "proposed_display_name": "王敦", "referent_canonical_hint": "王敦"}`
- A2OR primary: `reference` (medium)
- A2OR reason: The target occurrence 王敦 appears in Liu Xiaobiao's annotation (liu_annotation-001) within the phrase "路過武昌王敦" which is part of the annotation text introducing the Jin Yangqiu quotation about Sima Cheng. The occurrence of 王敦 here is a passing reference to Wang Dun in the annotation's narrative context — he is mentioned as someone whose location (Wuchang) Sima Cheng passed through. This is not the speaker, addressee, citation source, exemplum, genealogy, or attribute. It is a simple reference to the historical person within the annotation's narrative. The occurrence does not itself actively participate in a narrated event in a way that would make it a participant; it functions as a referential mention of Wang Dun in the annotation context.
- A2OVB boundary: `referential_only` (medium)
- A2OVB reason: The target occurrence "王敦" appears in the Liu Xiaobiao annotation text: "(也為中宗相州刺史路過武昌王敦/晉陽秋曰司馬丞字元敬譙王遜子)". This is a fragment of annotation text where 王敦 appears as part of a locative/contextual reference — 司馬丞 (司馬愍王) was passing through Wuchang where 王敦 was stationed. The annotation is providing biographical/contextual background information about the location and circumstances, not narrating an event in which 王敦 actively participates at this exact occurrence. The mention identifies 王敦 as the person whose territory/position is being referenced contextually (passing through Wuchang where Wang Dun was), which is a referential/descriptive mention rather than depicting Wang Dun as an actor, patient, or participant in a narrated event at this specific occurrence.
- final function: `reference`
- legacy projection: `annotation_person`
- review status: `mandatory_review`
- review triggers: `policy_defined_stage_disagreement`
- audit flags: `none`

## 21. 04-wenxue-023 / 羣臣

- occurrence_id: `sfh1-mention-2520231f896de7b4fbb1c507`
- mention_id: `sfh1-mention-2520231f896de7b4fbb1c507`
- source_evidence_id: `sfh1-ev-04-wenxue-023-liu-annotation-002`
- offsets: `38:40`
- source layer: `liu_annotation`
- exact target: `羣臣`
- context:
  - `main_text` `sfh1-ev-04-wenxue-023-main`: 殷中軍見佛經云理亦應阿堵上
  - `liu_annotation` `sfh1-ev-04-wenxue-023-liu-annotation-001`: (矣莫詳其始牟子/佛經之行中國尚)
  - `liu_annotation` `sfh1-ev-04-wenxue-023-liu-annotation-002`: (傅毅對曰臣聞天竺有道者號曰佛輕舉能飛身有/曰漢明帝夜夢神人身有日光明日博問羣臣通人)
  - `liu_annotation` `sfh1-ev-04-wenxue-023-liu-annotation-003`: (王遵等十二人之大月氏國寫取佛經四十二部在/日光殆將其神也於是遣羽林將軍秦景博士弟子)
  - `liu_annotation` `sfh1-ev-04-wenxue-023-liu-annotation-004`: (驗得仙者百四十六人其七十四人巳在佛經故撰/蘭臺石室劉子政列仙傳曰歷觀百家之中以相檢)
  - `liu_annotation` `sfh1-ev-04-wenxue-023-liu-annotation-005`: (間已有經矣與牟子傳記便為不同魏略西戎傳曰/得七十可以多聞博識者遐觀焉如此即漢成哀之)
  - `liu_annotation` `sfh1-ev-04-wenxue-023-liu-annotation-006`: (者太子也父曰屑頭邪母曰莫邪浮屠者身服色黃/天竺城中有臨兒國浮屠經云其國王生浮圗浮圗)
  - `liu_annotation` `sfh1-ev-04-wenxue-023-liu-annotation-007`: (而有髻墜地能行七歩天竺又有神人曰沙律昔漢/髮如青絲爪如銅其母夢白象而孕及生從右脅出)
  - `liu_annotation` `sfh1-ev-04-wenxue-023-liu-annotation-008`: (口傳浮屠經曰復豆者其人也漢武故事曰昆邪王/哀帝元夀元年博士弟子景慮受大月氏王使伊存)
  - `liu_annotation` `sfh1-ev-04-wenxue-023-liu-annotation-009`: (金人皆長丈餘其祭不用牛羊唯燒香禮拜上使依/殺休屠王以其衆來降得其金人之神置之甘泉宫)
  - `liu_annotation` `sfh1-ev-04-wenxue-023-liu-annotation-010`: (行於中土而但神明事之邪故驗劉向魚豢之説佛/其國俗祀之此神全類於佛豈當漢武之時其經未)
  - `liu_annotation` `sfh1-ev-04-wenxue-023-liu-annotation-011`: (今存非妄葢明帝遣使廣求異聞非是時無經也/至自哀成之世明矣然則牟傳所言四十二者其文)
- identity status: `not_applicable`
- identity: `{}`
- identity candidate proposal: `null`
- A2OR primary: `collective_reference` (high)
- A2OR reason: The target occurrence "羣臣" (the assembled ministers/officials) is a collective person reference. In the Liu annotation text, 漢明帝 (Emperor Ming of Han) "博問羣臣通人" (broadly consulted the assembled ministers and learned men). The occurrence denotes a collective entity — the group of court officials — rather than a single individual. It functions as a collective_reference denoting the group being consulted, not a specific participant, speaker, addressee, or other more specific function.
- final function: `collective_reference`
- legacy projection: `collective_reference`
- review status: `no_mandatory_review`
- review triggers: `none`
- audit flags: `none`

## 22. 11-jiewu-003 / 楊

- occurrence_id: `sfh1-mention-e8f9268305e71ab3d1724605`
- mention_id: `sfh1-mention-e8f9268305e71ab3d1724605`
- source_evidence_id: `sfh1-ev-11-jiewu-003-liu-annotation-004`
- offsets: `41:42`
- source layer: `liu_annotation`
- exact target: `楊`
- context:
  - `main_text` `sfh1-ev-11-jiewu-003-main`: 魏武嘗過曹娥碑下楊脩從碑背上見題作黄絹幼
婦外孫䪡臼八字魏武謂脩曰解不荅曰解魏武曰
卿未可言待我思之行三十里魏武乃曰吾巳得令
脩别記所知脩曰黄絹色絲也於字爲絶幼婦少女
也於字爲妙外孫女子也於字爲好䪡臼受辛也於
字爲辭所謂絶妙好辭也魏武亦記之與脩同乃歎
曰我才不及卿乃覺三十里
  - `liu_annotation` `sfh1-ev-11-jiewu-003-liu-annotation-001`: (者上虞人父盱能撫節/會稽典錄曰孝女曹娥)
  - `liu_annotation` `sfh1-ev-11-jiewu-003-liu-annotation-002`: (所淹不得其尸娥年十四號慕思盱乃投瓜于江存/按歌婆娑樂神漢安二年迎伍君神泝濤而上為水)
  - `liu_annotation` `sfh1-ev-11-jiewu-003-liu-annotation-003`: (於江而死縣長度尚悲憐其義爲之攺葬命其弟子/其父尸曰父在此瓜當沈旬有七日瓜偶沈遂自投)
  - `liu_annotation` `sfh1-ev-11-jiewu-003-liu-annotation-004`: (修未嘗過江也異苑曰陳留蔡邕避難過吳讀碑父/邯鄲子禮爲之作碑按曹娥碑在㑹稽中而魏武楊)
  - `liu_annotation` `sfh1-ev-11-jiewu-003-liu-annotation-005`: (而不能了以問羣寮莫有解者有婦人浣於汾渚曰/以為詩人之作無詭妄也因刻石旁作八字魏武見)
  - `liu_annotation` `sfh1-ev-11-jiewu-003-liu-annotation-006`: (合義解之或謂此婦人即娥靈也/弟四車解既而禰正平也衡即以離)
- identity status: `resolved`
- identity: `{"abstain": false, "attribute_type": "", "attribute_value": "", "bearer_hint": "", "reference_type": "surname_reference", "referent": {"canonical_hint": "楊脩", "confidence": "high", "surface_form": "楊脩"}, "semantic_kind": "historical_person"}`
- identity candidate proposal: `{"candidate_only": true, "candidate_origin": "llm_semantic_proposal_registry_miss", "candidate_person_id": "sfh2-a0-candidate-person-95bb9ed30d56b5f3fb03", "canonical_write_back": false, "display_name": "楊脩", "entity_type": "candidate_historical_person", "person_id": "", "proposed_display_name": "楊脩", "referent_canonical_hint": "楊脩", "source_occurrence_ids": ["sfh1-mention-e8f9268305e71ab3d1724605"], "supporting_evidence_ids": ["sfh1-ev-11-jiewu-003-liu-annotation-004", "sfh1-ev-11-jiewu-003-main"]}`
- A2OR primary: `reference` (medium)
- A2OR reason: The target occurrence is the surname 楊 (referring to 楊脩) within the Liu Xiaobiao annotation text: "按曹娥碑在㑹稽中而魏武楊..." The annotation is discussing the location of the Cao E stele and noting that Wei Wu (魏武) and Yang (楊, i.e., Yang Xiu) never crossed the river (修未嘗過江也). The occurrence of 楊 here refers to Yang Xiu as part of the annotation's argumentative/commentarial discussion about the historical facts of the stele's location. Yang Xiu is not actively participating in a narrated event at this occurrence, nor is he a speaker, addressee, citation source, exemplum, or genealogical reference. He is simply being referenced/mentioned as a historical person in the annotation's explanatory discourse. The occurrence functions as a plain reference to the person within the annotation's argument.
- A2OVB boundary: `referential_only` (high)
- A2OVB reason: The target occurrence is the character 楊 in the Liu Xiaobiao annotation text "按曹娥碑在㑹稽中而魏武楊..." This is part of a scholarly annotation discussing the location of the Cao'e stele and noting that Wei Wu (Cao Cao) and Yang Xiu (楊脩) had not crossed the river. The annotation is a commentary/note that references Yang Xiu as part of a factual observation about the historical circumstances, not narrating an event in which Yang Xiu participates. The annotation text "修未嘗過江也" (Xiu had never crossed the river) and the subsequent "按曹娥碑在㑹稽中而魏武楊..." is a critical note evaluating the plausibility of the main text's story. Yang Xiu is mentioned referentially as part of the annotation's argumentative/commentarial content, not as a participant in a narrated event at this occurrence.
- final function: `reference`
- legacy projection: `annotation_person`
- review status: `mandatory_review`
- review triggers: `invalid_provider_contract, new_historical_person_candidate, policy_defined_stage_disagreement`
- audit flags: `none`

## 23. 14-rongzhi-005 / 康

- occurrence_id: `sfh1-mention-55b97afde3e7fb4c074361b8`
- mention_id: `sfh1-mention-55b97afde3e7fb4c074361b8`
- source_evidence_id: `sfh1-ev-14-rongzhi-005-liu-annotation-001`
- offsets: `10:11`
- source layer: `liu_annotation`
- exact target: `康`
- context:
  - `main_text` `sfh1-ev-14-rongzhi-005-main`: 嵇康身長七尺八寸風姿特秀

見者歎曰蕭蕭
肅肅爽朗清舉或云肅肅如松下風髙而徐引山公
曰嵇叔夜之為人也巖巖若孤松之獨立其醉也傀
俄若玉山之將崩
  - `liu_annotation` `sfh1-ev-14-rongzhi-005-liu-annotation-001`: (八寸偉容色土木形/康别傳曰康長七尺)
  - `liu_annotation` `sfh1-ev-14-rongzhi-005-liu-annotation-002`: (正爾在羣形之中便自知非常之器/骸不加餙厲而龍章鳯姿天質自然)
- identity status: `resolved`
- identity: `{"abstain": false, "attribute_type": "", "attribute_value": "", "bearer_hint": "", "reference_type": "personal_name", "referent": {"canonical_hint": "嵇康", "confidence": "high", "surface_form": "嵇康"}, "semantic_kind": "historical_person"}`
- identity candidate proposal: `{"candidate_only": true, "candidate_origin": "python_registry_lookup_after_llm_semantics", "candidate_person_id": "", "canonical_write_back": false, "display_name": "嵇康", "entity_type": "existing_person", "person_id": "person-046", "proposed_display_name": "嵇康", "referent_canonical_hint": "嵇康"}`
- A2OR primary: `reference` (high)
- A2OR reason: The target occurrence "康" appears within Liu Xiaobiao's annotation quoting the "康别传" (Biography of Ji Kang), stating "康長七尺" (Kang was seven chi tall). The occurrence refers to Ji Kang within the quoted biographical source material. It does not function as speaker, addressee, citation source (the citation source is the 康别传 itself, not Ji Kang), historical exemplum, collective reference, genealogy reference, or person_attribute. The occurrence simply refers to/describes Ji Kang within the quoted annotation content, making it a reference occurrence.
- A2OVB boundary: `referential_only` (high)
- A2OVB reason: The target occurrence "康" appears within Liu Xiaobiao's annotation quoting the 康别傳: "康長七尺" (Kang was seven chi tall). This is a descriptive statement about Ji Kang's physical stature — a static attribute description, not a narrated event in which Kang participates as an actor, patient, or experiencer. The occurrence merely describes a property of the referent.
- final function: `reference`
- legacy projection: `annotation_person`
- review status: `mandatory_review`
- review triggers: `policy_defined_stage_disagreement`
- audit flags: `none`

## 24. 10-guizhen-012 / 大將軍

- occurrence_id: `sfh1-mention-0dddf6803e50a201bbf0e0f5`
- mention_id: `sfh1-mention-0dddf6803e50a201bbf0e0f5`
- source_evidence_id: `sfh1-ev-10-guizhen-012-main`
- offsets: `8:11`
- source layer: `main_text`
- exact target: `大將軍`
- context:
  - `main_text` `sfh1-ev-10-guizhen-012-main`: 謝鯤爲豫章太守從大將軍下至石頭敦謂鯤曰余
不得復爲盛德之事矣鯤曰何爲其然但使自今巳
後日亡日去耳敦又稱疾不朝鯤
諭敦曰近者明公之舉雖欲大存社稷然四海之内

實懷未逹若能朝天子使羣臣釋然萬物之心於是
乃服仗民望以從衆懷盡沖退以奉主上如斯則勲
侔一匡名垂千載時人以爲名言
  - `liu_annotation` `sfh1-ev-10-guizhen-012-liu-annotation-001`: (切雅正皆此類也/鯤别傳曰鯤之諷)
  - `liu_annotation` `sfh1-ev-10-guizhen-012-liu-annotation-002`: (章太守王敦將肆/晉陽秋曰鯤爲豫)
  - `liu_annotation` `sfh1-ev-10-guizhen-012-liu-annotation-003`: (不就朝覲鯤懼天下私議也敦曰君能保無變乎對/逆以鯤有時望逼與俱行既克京邑將旋武昌鯤曰)
  - `liu_annotation` `sfh1-ev-10-guizhen-012-liu-annotation-004`: (不虞之慮公若入朝鯤請侍從敦曰正復殺君等數/曰鯤近日入覲主上側席遲得見公宫省穆然必無)
  - `liu_annotation` `sfh1-ev-10-guizhen-012-liu-annotation-005`: (遂不朝而去/百何損於時)
- identity status: `resolved`
- identity: `{"abstain": false, "attribute_type": "", "attribute_value": "", "bearer_hint": "", "reference_type": "office_title", "referent": {"canonical_hint": "王敦", "confidence": "high", "surface_form": "王敦"}, "semantic_kind": "historical_person"}`
- identity candidate proposal: `{"candidate_only": true, "candidate_origin": "python_registry_lookup_after_llm_semantics", "candidate_person_id": "", "canonical_write_back": false, "display_name": "王敦", "entity_type": "existing_person", "person_id": "person-011", "proposed_display_name": "王敦", "referent_canonical_hint": "王敦"}`
- A2OR primary: `participant` (high)
- A2OR reason: The target occurrence "大將軍" (Grand General) refers to 王敦 (Wang Dun), who is the person Xie Kun accompanies ("從大將軍下至石頭"). The occurrence identifies Wang Dun as an active participant in the narrated event — he travels with Xie Kun to Stone City and subsequently engages in dialogue. The office title "大將軍" functions here as a way of referring to Wang Dun as an active participant in the narrative, not as a speaker, addressee, citation source, exemplum, or attribute. The subsequent text confirms Wang Dun's active role (敦謂鯤曰...敦又稱疾不朝).
- A2OVB boundary: `event_participant` (high)
- A2OVB reason: The target occurrence "大將軍" (referring to 王敦) appears in the clause "謝鯤爲豫章太守從大將軍下至石頭" — Xie Kun, as governor of Yuzhang, followed the Grand General (Wang Dun) down to Stone City (石頭). The Grand General is the entity being followed in the narrated event of traveling/descending to Stone City. Wang Dun is genuinely a participant in this narrated movement event, as the person whom Xie Kun accompanied. This is not merely a referential mention, comparison, or evaluation; the Grand General is an active participant in the narrated journey event.
- final function: `participant`
- legacy projection: `scene_participant`
- review status: `mandatory_review`
- review triggers: `policy_defined_stage_disagreement`
- audit flags: `none`

## 25. 05-fangzheng-055 / 王蒙

- occurrence_id: `sfh1-mention-57b7746a3be07831cfa06a32`
- mention_id: `sfh1-mention-57b7746a3be07831cfa06a32`
- source_evidence_id: `sfh1-ev-05-fangzheng-055-liu-annotation-002`
- offsets: `19:21`
- source layer: `liu_annotation`
- exact target: `王蒙`
- context:
  - `main_text` `sfh1-ev-05-fangzheng-055-main`: 桓公問桓子野謝安石料萬石必敗何以不諫

子野荅曰故當出於難犯耳桓作
色曰萬石撓弱凡才有何嚴顔難犯
  - `liu_annotation` `sfh1-ev-05-fangzheng-055-liu-annotation-001`: (桓伊/子野)
  - `liu_annotation` `sfh1-ev-05-fangzheng-055-liu-annotation-002`: (將軍伊少有才蓺又善聲律加以標悟省率爲王蒙/小字也續晉陽秋曰伊字叔夏譙國銍人父景護軍)
  - `liu_annotation` `sfh1-ev-05-fangzheng-055-liu-annotation-003`: (州剌史贈右將軍/劉惔所知累遷豫)
- identity status: `resolved`
- identity: `{"abstain": false, "attribute_type": "", "attribute_value": "", "bearer_hint": "", "reference_type": "full_name", "referent": {"canonical_hint": "王蒙", "confidence": "high", "surface_form": "王蒙"}, "semantic_kind": "historical_person"}`
- identity candidate proposal: `{"candidate_only": true, "candidate_origin": "python_registry_lookup_after_llm_semantics", "candidate_person_id": "", "canonical_write_back": false, "display_name": "王濛", "entity_type": "existing_person", "person_id": "person-014", "proposed_display_name": "王蒙", "referent_canonical_hint": "王蒙"}`
- A2OR primary: `reference` (medium)
- A2OR reason: The target occurrence 王蒙 appears in Liu Xiaobiao's annotation to the Shishuo entry. In the annotation text, 王蒙 is identified as the 小字 (childhood name) of 桓伊 (子野). The annotation reads "爲王蒙/小字也" — meaning that 王蒙 is the childhood name of the person being discussed. This occurrence functions as a reference identifying/describing the entity 王蒙 as the childhood name of 桓伊. It is not a participant in a narrated event, not a speaker/addressee, not a citation source (the annotation itself is the source context), not a historical exemplum, not a collective, not a genealogy reference (it identifies a name, not a kinship relation), and not a person_attribute (the occurrence itself is the name being referenced, not an attribute expression about a bearer). It functions as a plain reference to the person 王蒙 within the annotation's explanatory content.
- A2OVB boundary: `referential_only` (high)
- A2OVB reason: The target occurrence "王蒙" appears in Liu Xiaobiao's annotation, where it is used to gloss the childhood name (小字) of Huan Yi (桓伊). The text reads "爲王蒙/小字也" — meaning that "王蒙" is identified as Huan Yi's childhood name. This is a purely referential/identificatory use: the annotation states that the name "王蒙" was the childhood name of Huan Yi. Wang Meng himself is not a participant in any narrated event at this occurrence; he is merely referenced as the name-form used for Huan Yi's childhood name. No event involving Wang Meng as actor, patient, or experiencer is narrated here.
- final function: `reference`
- legacy projection: `annotation_person`
- review status: `mandatory_review`
- review triggers: `invalid_provider_contract, policy_defined_stage_disagreement`
- audit flags: `none`

## 26. 05-fangzheng-007 / 司徒第二子

- occurrence_id: `sfh1-mention-c7948b25743a9dba7d00497e`
- mention_id: `sfh1-mention-c7948b25743a9dba7d00497e`
- source_evidence_id: `sfh1-ev-05-fangzheng-007-liu-annotation-005`
- offsets: `15:20`
- source layer: `liu_annotation`
- exact target: `司徒第二子`
- context:
  - `main_text` `sfh1-ev-05-fangzheng-007-main`: 夏侯泰初與廣陵陳本善本與玄在本母前宴飲


本弟騫
行還徑入至堂戸泰初
因起曰可得同不可得而雜
  - `liu_annotation` `sfh1-ev-05-fangzheng-007-liu-annotation-001`: (語/世)
  - `liu_annotation` `sfh1-ev-05-fangzheng-007-liu-annotation-002`: (矯司徒本歷郡守廷尉所在操綱領舉大體能使羣/曰本字休元臨淮東陽人魏志曰本廣陵東陽人父)
  - `liu_annotation` `sfh1-ev-05-fangzheng-007-liu-annotation-003`: (法律而得廷尉之稱遷鎮北將軍/下自盡有率御之才不親小事不讀)
  - `liu_annotation` `sfh1-ev-05-fangzheng-007-liu-annotation-004`: (曰騫字/晉陽秋)
  - `liu_annotation` `sfh1-ev-05-fangzheng-007-liu-annotation-005`: (滑稽而多智謀仕至大司馬/休淵司徒第二子無謇諤風)
  - `liu_annotation` `sfh1-ev-05-fangzheng-007-liu-annotation-006`: (齒本不論德位年長者/名士傳曰玄以鄉黨貴)
  - `liu_annotation` `sfh1-ev-05-fangzheng-007-liu-annotation-007`: (出其可得同不可得而雜者也/必爲拜與陳本母前飲騫來而)
- identity status: `resolved`
- identity: `{"abstain": false, "attribute_type": "", "attribute_value": "", "bearer_hint": "", "reference_type": "kinship_reference", "referent": {"canonical_hint": "陳騫", "confidence": "high", "surface_form": "騫"}, "semantic_kind": "historical_person"}`
- identity candidate proposal: `{"candidate_only": true, "candidate_origin": "llm_semantic_proposal_registry_miss", "candidate_person_id": "sfh2-a0-candidate-person-f2f890987c4c9595d2db", "canonical_write_back": false, "display_name": "陳騫", "entity_type": "candidate_historical_person", "person_id": "", "proposed_display_name": "陳騫", "referent_canonical_hint": "陳騫", "source_occurrence_ids": ["sfh1-mention-c7948b25743a9dba7d00497e"], "supporting_evidence_ids": ["sfh1-ev-05-fangzheng-007-liu-annotation-002", "sfh1-ev-05-fangzheng-007-liu-annotation-004", "sfh1-ev-05-fangzheng-007-liu-annotation-005"]}`
- A2OR primary: `genealogy_reference` (high)
- A2OR reason: The target occurrence "司徒第二子" (second son of the Minister of Works) is a kinship reference identifying 騫 (Chen Qian) as the second son of 司徒 (Sima/Chancellor). The reference_type is frozen as "kinship_reference" and the surface form explicitly performs genealogical identification by specifying the father (司徒) and birth order (第二子). This directly matches the genealogy_reference function, which covers occurrences that specifically perform genealogical or kinship identification.
- final function: `genealogy_reference`
- legacy projection: `genealogy_reference`
- review status: `mandatory_review`
- review triggers: `invalid_provider_contract, new_historical_person_candidate, policy_defined_stage_disagreement`
- audit flags: `none`

## 27. 34-pilou-006 / 父融

- occurrence_id: `sfh1-mention-a784097a150a921e85a6d19f`
- mention_id: `sfh1-mention-a784097a150a921e85a6d19f`
- source_evidence_id: `sfh1-ev-34-pilou-006-liu-annotation-002`
- offsets: `25:27`
- source layer: `liu_annotation`
- exact target: `父融`
- context:
  - `main_text` `sfh1-ev-34-pilou-006-main`: 殷仲堪父病虚悸聞牀下蟻動謂是牛鬬

孝武不知是殷公問仲堪有一殷病如此不仲堪流

涕而起曰臣進退唯谷
  - `liu_annotation` `sfh1-ev-34-pilou-006-liu-annotation-001`: (殷師字師/殷氏譜曰)
  - `liu_annotation` `sfh1-ev-34-pilou-006-liu-annotation-002`: (秋曰仲堪父曽有失心病仲堪腰不解帶彌年父卒/子祖識父融並有名師至驃騎咨議生仲堪續晉陽)
  - `liu_annotation` `sfh1-ev-34-pilou-006-liu-annotation-003`: (注曰谷窮也/大雅詩也毛公)
- identity status: `resolved`
- identity: `{"abstain": false, "attribute_type": "", "attribute_value": "", "bearer_hint": "", "reference_type": "kinship_reference", "referent": {"canonical_hint": "殷融", "confidence": "high", "surface_form": "殷融"}, "semantic_kind": "historical_person"}`
- identity candidate proposal: `{"candidate_only": true, "candidate_origin": "llm_semantic_proposal_registry_miss", "candidate_person_id": "sfh2-a0-candidate-person-7e1949512e7bb485e200", "canonical_write_back": false, "display_name": "殷融", "entity_type": "candidate_historical_person", "person_id": "", "proposed_display_name": "殷融", "referent_canonical_hint": "殷融", "source_occurrence_ids": ["sfh1-mention-a784097a150a921e85a6d19f"], "supporting_evidence_ids": ["sfh1-ev-34-pilou-006-liu-annotation-002"]}`
- A2OR primary: `genealogy_reference` (high)
- A2OR reason: The target occurrence "父融" (father Rong) appears in the Liu Xiaobiao annotation genealogical passage. The surface form is a kinship reference identifying 殷融 as the father of 祖識 (and grandfather of 仲堪). The occurrence specifically performs genealogical/kinship identification within the family lineage being traced in the annotation, matching the genealogy_reference function.
- final function: `genealogy_reference`
- legacy projection: `genealogy_reference`
- review status: `mandatory_review`
- review triggers: `new_historical_person_candidate, policy_defined_stage_disagreement`
- audit flags: `none`

## 28. 08-shangyu-020 / 周俊

- occurrence_id: `sfh1-mention-f32b680621137411704250be`
- mention_id: `sfh1-mention-f32b680621137411704250be`
- source_evidence_id: `sfh1-ev-08-shangyu-020-liu-annotation-001`
- offsets: `3:5`
- source layer: `liu_annotation`
- exact target: `周俊`
- context:
  - `main_text` `sfh1-ev-08-shangyu-020-main`: 有問秀才吳舊姓何如荅曰吳府君聖王之老成明
時之儁乂朱永長理物之至德清選之高望嚴仲弼
九臯之鳴鶴空谷之白駒顧彦先八音之琴瑟五色
之龍章張威伯歲寒之茂松幽夜之逸光陸士衡士
龍鴻鵠之裵回懸鼔之待槌








凡此諸
君以洪筆爲鉏耒以𥿄札爲良田以玄黙爲稼穡以
義理爲豐年以談論爲英華以忠恕爲珍寳著文章
爲錦繡藴五經爲繒帛坐謙虚爲席薦張義讓爲帷
幙行仁義爲室宇修道德爲廣宅
  - `liu_annotation` `sfh1-ev-08-shangyu-020-liu-annotation-001`: (剌史周俊書曰一日侍/秀才蔡洪也集載洪與)
  - `liu_annotation` `sfh1-ev-08-shangyu-020-liu-annotation-002`: (舉敕令條列名狀退輒思之今稱䟽所知吳展字士/坐言及吳士詢于芻蕘遂見下問造次承顔載辭不)
  - `liu_annotation` `sfh1-ev-08-shangyu-020-liu-annotation-003`: (仕吳爲廣州剌史吳郡太守吳平還下邳閉門自守/季下邳人忠足矯非清足厲俗信可結神才堪榦世)
  - `liu_annotation` `sfh1-ev-08-shangyu-020-liu-annotation-004`: (長吳郡人體履清和黄中通理吳朝舉賢良累遷議/不交賔客誠聖王之老成明時之儁乂也朱誕字永)
  - `liu_annotation` `sfh1-ev-08-shangyu-020-liu-annotation-005`: (仲弼吳郡人禀氣清純思度淵偉吳朝舉賢良宛陵/郎今歸在家誠理物之至德清選之高望也嚴隱字)
  - `liu_annotation` `sfh1-ev-08-shangyu-020-liu-annotation-006`: (伯吳郡人禀性堅明志行清朗居磨涅之中無淄磷/令吳平去職九臯之鳴鶴空谷之白駒也張畼字威)
  - `liu_annotation` `sfh1-ev-08-shangyu-020-liu-annotation-007`: (士龍吳大司馬抗之第五子機同母之弟也儒雅有/之損歲寒之松栢幽夜之逸光也陸雲别傳曰雲字)
  - `liu_annotation` `sfh1-ev-08-shangyu-020-liu-annotation-008`: (能賦詩時人以爲項託掦烏之疇也年十八剌史周/俊才容貌瓌偉口敏能談博聞彊記善著述六歲便)
  - `liu_annotation` `sfh1-ev-08-shangyu-020-liu-annotation-009`: (也累遷太子舍人清河内史爲成都王所害/俊命爲主簿俊常嘆曰陸士龍當今之顔淵)
  - `liu_annotation` `sfh1-ev-08-shangyu-020-liu-annotation-010`: (人無陸機兄弟又/按蔡所論士十六)
  - `liu_annotation` `sfh1-ev-08-shangyu-020-liu-annotation-011`: (以下疑益之/無凡此諸君)
- identity status: `resolved`
- identity: `{"abstain": false, "attribute_type": "", "attribute_value": "", "bearer_hint": "", "reference_type": "full_name", "referent": {"canonical_hint": "周俊", "confidence": "high", "surface_form": "周俊"}, "semantic_kind": "historical_person"}`
- identity candidate proposal: `{"candidate_only": true, "candidate_origin": "llm_semantic_proposal_registry_miss", "candidate_person_id": "sfh2-a0-candidate-person-1f5c9f1f122f7af8f1ae", "canonical_write_back": false, "display_name": "周俊", "entity_type": "candidate_historical_person", "person_id": "", "proposed_display_name": "周俊", "referent_canonical_hint": "周俊", "source_occurrence_ids": ["sfh1-mention-f32b680621137411704250be"], "supporting_evidence_ids": ["sfh1-ev-08-shangyu-020-liu-annotation-001", "sfh1-ev-08-shangyu-020-liu-annotation-008", "sfh1-ev-08-shangyu-020-liu-annotation-009"]}`
- A2OR primary: `citation_source` (high)
- A2OR reason: The target occurrence "周俊" appears in the Liu Xiaobiao annotation (liu_annotation layer) in the phrase "剌史周俊書曰" — "the Inspector Zhou Jun wrote, saying...". This identifies Zhou Jun as the author/source of the quoted letter that follows ("一日侍/秀才蔡洪也集載洪與"). The occurrence functions to attribute the quoted material to Zhou Jun as its source, which matches the citation_source function.
- final function: `citation_source`
- legacy projection: `citation_source_person`
- review status: `mandatory_review`
- review triggers: `new_historical_person_candidate, policy_defined_stage_disagreement`
- audit flags: `none`

## 29. 05-fangzheng-027 / 江南

- occurrence_id: `sfh1-mention-7be0675e1cbc7d93e92349be`
- mention_id: `sfh1-mention-7be0675e1cbc7d93e92349be`
- source_evidence_id: `sfh1-ev-05-fangzheng-027-liu-annotation-003`
- offsets: `1:3`
- source layer: `liu_annotation`
- exact target: `江南`
- context:
  - `main_text` `sfh1-ev-05-fangzheng-027-main`: 周伯仁爲吏部尚書在省內夜疾危急時刁玄亮爲
尚書令營救備親好之至良乆小損

明旦報仲智仲智狼狽來始入戸刁下牀

對之大泣説伯仁昨危急之狀仲智手批之刁爲辟
易於戸側既前都不問病直云君在中朝與和長輿
齊名那與佞人刁協有情逕便出
  - `liu_annotation` `sfh1-ev-05-fangzheng-027-liu-annotation-001`: (協字玄亮勃海/虞預晉書曰刁)
  - `liu_annotation` `sfh1-ev-05-fangzheng-027-liu-annotation-002`: (禀於協累遷尚書令中宗信重之爲王敦所忌舉兵/饒安人少好學雖不研精而多所博渉中興制度皆)
  - `liu_annotation` `sfh1-ev-05-fangzheng-027-liu-annotation-003`: (江南敗死/討之奔至)
- identity status: `not_applicable`
- identity: `{}`
- identity candidate proposal: `null`
- A2OR primary: `reference` (medium)
- A2OR reason: The target occurrence "江南" appears in the Liu annotation fragment "(江南敗死/討之奔至)". This is a geographical reference (Jiangnan, south of the Yangtze) within the annotation text describing where someone was defeated and died. The entity is classified as non_person (a place). It does not function as a participant in a narrated event, speaker, addressee, citation source, historical exemplum, genealogy reference, collective reference, or person attribute. It is a plain reference to a location within the annotation's narrative content.
- A2OVB boundary: `referential_only` (high)
- A2OVB reason: The target occurrence "江南" appears in the Liu Xiaobiao annotation fragment "(江南敗死/討之奔至)". This is a geographical place name (Jiangnan, south of the Yangtze) used as a locative reference describing where Diao Xie fled to and died. The annotation is biographical background about Diao Xie's fate — it narrates that he fled to Jiangnan and died there. However, "江南" itself is a place, not a person, and the target occurrence is a location reference within a narrative about Diao Xie's death. The place is not an event participant in the sense of an actor/patient/experiencer; it functions as a locative setting. The occurrence is referential-only — it points to a location without that location being a participant in a narrated event.
- final function: `reference`
- legacy projection: `annotation_person`
- review status: `no_mandatory_review`
- review triggers: `none`
- audit flags: `none`

## 30. 09-pinzao-063 / 吾

- occurrence_id: `sfh1-mention-276c292df4447b07909ecf22`
- mention_id: `sfh1-mention-276c292df4447b07909ecf22`
- source_evidence_id: `sfh1-ev-09-pinzao-063-main`
- offsets: `8:9`
- source layer: `main_text`
- exact target: `吾`
- context:
  - `main_text` `sfh1-ev-09-pinzao-063-main`: 庾道季云思理倫和吾愧康伯志力彊正吾愧文度
自此以還吾皆百之
  - `liu_annotation` `sfh1-ev-09-pinzao-063-liu-annotation-001`: (巳見/庾龢)
- identity status: `reused_frozen_context`
- identity: `{"abstain": false, "attribute_type": "", "attribute_value": "", "bearer_hint": "", "reference_type": "pronoun_reference", "referent": {"canonical_hint": "庾龢", "confidence": "high", "surface_form": "庾道季"}, "semantic_kind": "historical_person"}`
- identity candidate proposal: `null`
- A2OR primary: `speaker` (high)
- A2OR reason: The target occurrence "吾" (I/me) is the first-person self-reference used by 庾道季 (Yu Daoji), who is identified as the speaker at the start of the utterance ("庾道季云..."). The pronoun "吾" is the speaker's self-reference inside his own quoted speech, functioning as the speaker of the current utterance.
- final function: `speaker`
- legacy projection: `speaker_reference`
- review status: `no_mandatory_review`
- review triggers: `none`
- audit flags: `none`
