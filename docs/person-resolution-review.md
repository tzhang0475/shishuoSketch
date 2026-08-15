# Person resolution review

ER1 builds a deterministic effective-resolution overlay above the canonical Mention anchors. It does not materialize Persons or rewrite canonical text. A reviewed decision in `data/annotation/person-resolution-decisions.json` takes precedence over automatic output.

## Summary

- published Mention records audited: 294
- safely auto-resolved: 260
- candidate for review: 24
- unresolved: 2
- reviewed decisions applied: 9
- shared identity surfaces: 21

## Resolution precedence

1. reviewed human decision; 2. explicit full identity; 3. same-Story/section local antecedent; 4. explicit identity cue in the local Liu annotation; 5. unique exact alias; 6. shared alias as candidate_for_review; 7. insufficient evidence as unresolved.

Production status is a navigation capability, not an identity-confidence signal. An identity-candidate target is displayed as identified but remains non-navigable until a later materialization review.

## Known regression: 05-fangzheng-058

- identity candidate: `王坦之` (candidate-identity-067-liezhuan-002-e72bf92e965f)
- `王文度` is a local surname + courtesy-name cue; subsequent `文度` mentions inherit the same Story-local antecedent.
- all seven affected Mentions are reviewed to 王坦之 and no longer resolve to 孫晷 / `person-015`.
- 王坦之 is not a production Person, so these surfaces remain non-navigable in the reader.

## ER1.1.2 prefix collision: 桓子野 / 桓伊

- `person-016` 王遐 retains the exact identity evidence `桓子`, but that shorter surface is not allowed to win inside the longer `桓子野` appellation.
- The curated non-production identity target `桓伊` (`candidate-identity-er1-1-2-193fc44098a05235f63fc215`) is supported by the 05-fangzheng-055 Liu annotation and processed Jinshu evidence; it does not allocate a Person ID or create a PersonStory link.
- The six canonical prefix occurrences in 05-fangzheng-055, 23-rendan-033, 23-rendan-042, 23-rendan-049, and 26-qingdi-020 use the maximal `桓子野` span and remain non-navigable identity mentions wherever projected.
- In 05-fangzheng-055, the later `子野` is resolved only through the same-Story antecedent; `子野` is not a global exact alias.
- The two `桓子` occurrences in the ancient 春秋 quotation in 05-fangzheng-035 are reviewed unresolved rather than assigned to 王遐.

## Shared alias collisions

- `世英` → 陶璜、魯芝 · 0 published occurrences; never globally exact
- `仲容` → 阮咸、石苞 · 1 published occurrences; never globally exact
- `元禮陳郡` → 袁悦之、顧悦之 · 0 published occurrences; never globally exact
- `叔平` → 淳于智、王凝之 · 1 published occurrences; never globally exact
- `叔時` → 孟觀、魯勝 · 0 published occurrences; never globally exact
- `君叔少有` → 袁悦之、顧悦之 · 0 published occurrences; never globally exact
- `太傅` → 郗鑒、謝安 · 2 published occurrences; never globally exact
- `子安` → 范平、成公綏 · 0 published occurrences; never globally exact
- `子悌宣帝` → 譙剛王遜、王遜 · 0 published occurrences; never globally exact
- `張茂` → 張茂、張華 · 0 published occurrences; never globally exact
- `彦先` → 賀循、顧榮 · 0 published occurrences; never globally exact
- `思遠` → 紀瞻、應詹 · 0 published occurrences; never globally exact
- `文度` → 王坦之、孫晷 · 11 published occurrences; never globally exact
- `王丞相` → 王隱、王導 · 5 published occurrences; never globally exact
- `王公` → 王羲之、王導 · 2 published occurrences; never globally exact
- `王大將軍` → 王舒、王隱、王敦 · 0 published occurrences; never globally exact
- `芬兄思别` → 左貴嬪、胡貴嬪 · 0 published occurrences; never globally exact
- `芳父奮别` → 左貴嬪、胡貴嬪 · 0 published occurrences; never globally exact
- `道元` → 龔之、陳訓 · 0 published occurrences; never globally exact
- `道眀` → 蔡謨、諸葛恢 · 0 published occurrences; never globally exact
- `邵伯魏興` → 譙剛王遜、王遜 · 0 published occurrences; never globally exact

## Review queue

### 01-dexing-015 · 王公

- Mention: `shishuo-01-dexing-015-liu-annotation-001` · section: `liu_annotation` · status: `candidate_for_review` · review: `candidate`
- Context: (執事有恪亦各其慎也然天下之至慎者其唯阮嗣/尚書董仲達僕射【王公】仲上曰此諸人者温恭朝夕)
- Reasons: insufficient_unique_local_context、shared_alias_surface
- Candidates:
  - 王羲之 · production_person · supporting: ambiguous；medium · conflicting: insufficient_unique_local_context；shared_alias_surface
  - 王導 · production_person · supporting: ambiguous；medium · conflicting: insufficient_unique_local_context；shared_alias_surface

### 01-dexing-026 · 少孤

- Mention: `shishuo-p3b-wave-2-e72db7899b857ceab12efda4` · section: `main_text` · status: `unresolved` · review: `reviewed`
- Context: 祖光禄【少孤】貧性至孝常自為母炊㸑作食

王平北聞其佳名以兩婢餉之因取為中郎


有人戲之者曰奴價
- Reasons: human_reviewed_unresolved
- Candidates:
  - 孟陋 · production_person · supporting: exact；strong · conflicting: human_reviewed_unresolved
- Review note: 本則“少孤”是幼年喪父的普通敘事語，不是孟陋的字；不得由全局別名少孤解析為孟陋。

### 02-yanyu-036 · 丞相

- Mention: `shishuo-02-yanyu-036-liu-annotation-003` · section: `liu_annotation` · status: `candidate_for_review` · review: `candidate`
- Context: (相付託温公旣見【丞相】便游樂不住曰旣見管仲天/下不可以無主聞者莫不踴躍植髮穿冠王丞相㴱)
- Reasons: contextual_surface_requires_local_evidence
- Candidates:
  - 王導 · production_person · supporting: ambiguous；medium · conflicting: contextual_surface_requires_local_evidence

### 02-yanyu-036 · 王丞相

- Mention: `shishuo-02-yanyu-036-liu-annotation-004` · section: `liu_annotation` · status: `candidate_for_review` · review: `candidate`
- Context: (相付託温公旣見丞相便游樂不住曰旣見管仲天/下不可以無主聞者莫不踴躍植髮穿冠【王丞相】㴱)
- Reasons: insufficient_unique_local_context、shared_alias_surface
- Candidates:
  - 王隱 · identity_candidate · supporting: contextual；medium · conflicting: insufficient_unique_local_context；shared_alias_surface
  - 王導 · production_person · supporting: contextual；medium · conflicting: insufficient_unique_local_context；shared_alias_surface

### 02-yanyu-036 · 王丞相

- Mention: `shishuo-02-yanyu-036-main-text-001` · section: `main_text` · status: `candidate_for_review` · review: `candidate`
- Context: 温嶠初爲劉琨使來過江于時江左營建始爾綱紀
未舉温新至深有諸慮旣詣【王丞相】陳主上幽越社
稷焚滅山陵夷毁之酷有黍離之痛温忠慨深烈言
與泗俱丞相亦與之對泣叙情旣畢
- Reasons: insufficient_unique_local_context、shared_alias_surface
- Candidates:
  - 王隱 · identity_candidate · supporting: contextual；medium · conflicting: insufficient_unique_local_context；shared_alias_surface
  - 王導 · production_person · supporting: contextual；medium · conflicting: insufficient_unique_local_context；shared_alias_surface

### 02-yanyu-036 · 丞相

- Mention: `shishuo-02-yanyu-036-main-text-002` · section: `main_text` · status: `candidate_for_review` · review: `candidate`
- Context: 新至深有諸慮旣詣王丞相陳主上幽越社
稷焚滅山陵夷毁之酷有黍離之痛温忠慨深烈言
與泗俱【丞相】亦與之對泣叙情旣畢便深自陳結丞
相亦厚相酬納旣出懽然言曰江左自有管夷吾此
復何憂
- Reasons: contextual_surface_requires_local_evidence
- Candidates:
  - 王導 · production_person · supporting: ambiguous；medium · conflicting: contextual_surface_requires_local_evidence

### 02-yanyu-071 · 謝太傅

- Mention: `shishuo-02-yanyu-071-main-text-001` · section: `main_text` · status: `candidate_for_review` · review: `candidate`
- Context: 【謝太傅】寒雪日内集與兒女講論文義俄而雪驟
公欣然曰白雪紛紛何所似兄子胡兒曰
撒鹽空
中差可擬
- Reasons: contextual_surface_requires_local_evidence
- Candidates:
  - 謝安 · production_person · supporting: contextual；medium · conflicting: contextual_surface_requires_local_evidence

### 02-yanyu-078 · 謝太傅

- Mention: `shishuo-02-yanyu-078-main-text-001` · section: `main_text` · status: `candidate_for_review` · review: `candidate`
- Context: 晉武帝每餉山濤恒少【謝太傅】以問子弟車騎
荅曰當由欲者不多而使與者忘少
- Reasons: contextual_surface_requires_local_evidence
- Candidates:
  - 謝安 · production_person · supporting: contextual；medium · conflicting: contextual_surface_requires_local_evidence

### 02-yanyu-079 · 文度

- Mention: `shishuo-p3b-wave-1-00b8e87857ab4db7df23be0a` · section: `main_text` · status: `candidate_for_review` · review: `candidate`
- Context: 謝胡兒語庾道季
諸人莫當就卿談可堅城壘庾
曰若【文度】來我以偏師待之康伯來濟河焚舟
- Reasons: insufficient_unique_local_context、shared_alias_surface
- Candidates:
  - 王坦之 · identity_candidate · supporting: exact；strong · conflicting: insufficient_unique_local_context；shared_alias_surface
  - 孫晷 · production_person · supporting: ambiguous；strong · conflicting: insufficient_unique_local_context；shared_alias_surface

### 02-yanyu-083 · 太傅

- Mention: `shishuo-02-yanyu-083-liu-annotation-002` · section: `liu_annotation` · status: `candidate_for_review` · review: `candidate`
- Context: (郡乃祖之於冶亭時賢皆集安欲卒迫試之執手將/記室【太傅】謝安賞宏機捷辯速自吏部郎出為東陽)
- Reasons: insufficient_unique_local_context、shared_alias_surface
- Candidates:
  - 郗鑒 · production_person · supporting: ambiguous；medium · conflicting: insufficient_unique_local_context；shared_alias_surface
  - 謝安 · production_person · supporting: ambiguous；medium · conflicting: insufficient_unique_local_context；shared_alias_surface

### 04-wenxue-022 · 王丞相

- Mention: `shishuo-04-wenxue-022-main-text-001` · section: `main_text` · status: `candidate_for_review` · review: `candidate`
- Context: 殷中軍為庾公長史下都
【王丞相】為之集桓公王長史王藍田
謝
鎮西並在丞相自起解帳帶麈尾語殷曰身今日當

與君共談析理
- Reasons: insufficient_unique_local_context、shared_alias_surface
- Candidates:
  - 王隱 · identity_candidate · supporting: contextual；medium · conflicting: insufficient_unique_local_context；shared_alias_surface
  - 王導 · production_person · supporting: contextual；medium · conflicting: insufficient_unique_local_context；shared_alias_surface

### 04-wenxue-022 · 丞相

- Mention: `shishuo-04-wenxue-022-main-text-002` · section: `main_text` · status: `candidate_for_review` · review: `candidate`
- Context: 殷中軍為庾公長史下都
王丞相為之集桓公王長史王藍田
謝
鎮西並在【丞相】自起解帳帶麈尾語殷曰身今日當

與君共談析理旣共清言遂逹三更丞相與殷共相
徃反其餘諸
- Reasons: contextual_surface_requires_local_evidence
- Candidates:
  - 王導 · production_person · supporting: ambiguous；medium · conflicting: contextual_surface_requires_local_evidence

### 04-wenxue-022 · 丞相

- Mention: `shishuo-04-wenxue-022-main-text-003` · section: `main_text` · status: `candidate_for_review` · review: `candidate`
- Context: 王藍田
謝
鎮西並在丞相自起解帳帶麈尾語殷曰身今日當

與君共談析理旣共清言遂逹三更【丞相】與殷共相
徃反其餘諸賢略無所關旣彼我相盡丞相乃歎曰
向來語乃竟未知理源所歸至於辭喻不
- Reasons: contextual_surface_requires_local_evidence
- Candidates:
  - 王導 · production_person · supporting: ambiguous；medium · conflicting: contextual_surface_requires_local_evidence

### 04-wenxue-022 · 丞相

- Mention: `shishuo-04-wenxue-022-main-text-004` · section: `main_text` · status: `candidate_for_review` · review: `candidate`
- Context: 身今日當

與君共談析理旣共清言遂逹三更丞相與殷共相
徃反其餘諸賢略無所關旣彼我相盡【丞相】乃歎曰
向來語乃竟未知理源所歸至於辭喻不相負正始
之音正當爾耳明旦桓宣武語人曰昨夜聽
- Reasons: contextual_surface_requires_local_evidence
- Candidates:
  - 王導 · production_person · supporting: ambiguous；medium · conflicting: contextual_surface_requires_local_evidence

### 05-fangzheng-023 · 少孤

- Mention: `shishuo-p3b-wave-2-4d4702def6513f8bed5b32ab` · section: `liu_annotation` · status: `unresolved` · review: `candidate`
- Context: (虞氏先崩將納吳氏后與吳氏女遊後園有言之於/滎陽人【少孤】先嫁田氏夫亡依舅吳氏時中宗敬后)
- Reasons: homographic_lexical_alias_without_identity_basis
- Candidates:
  - 孟陋 · production_person · supporting: exact；strong · conflicting: homographic_lexical_alias_without_identity_basis
- Review note: 少孤既是孟陋的字，也是幼年喪父的普通語詞；没有同一故事中的明確身份語境時，不得按全局別名解析。

### 05-fangzheng-025 · 王右軍

- Mention: `shishuo-05-fangzheng-025-main-text-001` · section: `main_text` · status: `candidate_for_review` · review: `candidate`
- Context: 書求其小女㛰恢乃云羊鄧是世㛰江家我顧
伊庾家伊顧我不能復與謝裒兒㛰
及恢亡遂㛰
於是【王右軍】往謝家看
新婦猶有恢之遺法威儀端詳容服光整王歎曰我
在遣女裁得爾耳
- Reasons: contextual_surface_requires_local_evidence
- Candidates:
  - 王羲之 · production_person · supporting: contextual；medium · conflicting: contextual_surface_requires_local_evidence

### 05-fangzheng-058 · 文度

- Mention: `shishuo-p3b-wave-1-c74d10615d2c3d61660bbfe9` · section: `main_text` · status: `resolved` · review: `reviewed`
- Context: 王【文度】爲桓公長史時桓爲兒求王女王許咨藍田
既還藍田愛念文度雖長大猶抱著䣛上

文度因言桓求
- Recommendation: 王坦之
- Candidates:
  - 王坦之 · identity_candidate · supporting: exact；strong · conflicting: 无
  - 孫晷 · production_person · supporting: ambiguous；strong · conflicting: 无
- Review note: 本则“王文度”及后续“文度”为王坦之；不得解析为孙晷。

### 05-fangzheng-058 · 文度

- Mention: `shishuo-p3b-wave-1-a5b6b44b90a9b8f7e8230145` · section: `main_text` · status: `resolved` · review: `reviewed`
- Context: 王文度爲桓公長史時桓爲兒求王女王許咨藍田
既還藍田愛念【文度】雖長大猶抱著䣛上

文度因言桓求已女㛰藍田大怒排文度下䣛曰惡
見文度已復癡畏桓温靣兵
- Recommendation: 王坦之
- Candidates:
  - 王坦之 · identity_candidate · supporting: exact；strong · conflicting: 无
  - 孫晷 · production_person · supporting: ambiguous；strong · conflicting: 无
- Review note: 本则“王文度”及后续“文度”为王坦之；不得解析为孙晷。

### 05-fangzheng-058 · 文度

- Mention: `shishuo-p3b-wave-1-71e4635d7e8c619cf53f903f` · section: `main_text` · status: `resolved` · review: `reviewed`
- Context: 王文度爲桓公長史時桓爲兒求王女王許咨藍田
既還藍田愛念文度雖長大猶抱著䣛上

【文度】因言桓求已女㛰藍田大怒排文度下䣛曰惡
見文度已復癡畏桓温靣兵那可嫁女與之文度還
報云
- Recommendation: 王坦之
- Candidates:
  - 王坦之 · identity_candidate · supporting: exact；strong · conflicting: 无
  - 孫晷 · production_person · supporting: ambiguous；strong · conflicting: 无
- Review note: 本则“王文度”及后续“文度”为王坦之；不得解析为孙晷。

### 05-fangzheng-058 · 文度

- Mention: `shishuo-p3b-wave-1-e1e142645ac3d61d3231e967` · section: `main_text` · status: `resolved` · review: `reviewed`
- Context: 兒求王女王許咨藍田
既還藍田愛念文度雖長大猶抱著䣛上

文度因言桓求已女㛰藍田大怒排【文度】下䣛曰惡
見文度已復癡畏桓温靣兵那可嫁女與之文度還
報云下官家中先得㛰處桓公曰吾知矣
- Recommendation: 王坦之
- Candidates:
  - 王坦之 · identity_candidate · supporting: exact；strong · conflicting: 无
  - 孫晷 · production_person · supporting: ambiguous；strong · conflicting: 无
- Review note: 本则“王文度”及后续“文度”为王坦之；不得解析为孙晷。

### 05-fangzheng-058 · 文度

- Mention: `shishuo-p3b-wave-1-197c72e23308b4f6b31e4963` · section: `main_text` · status: `resolved` · review: `reviewed`
- Context: 田
既還藍田愛念文度雖長大猶抱著䣛上

文度因言桓求已女㛰藍田大怒排文度下䣛曰惡
見【文度】已復癡畏桓温靣兵那可嫁女與之文度還
報云下官家中先得㛰處桓公曰吾知矣此尊府君
不肯耳
- Recommendation: 王坦之
- Candidates:
  - 王坦之 · identity_candidate · supporting: exact；strong · conflicting: 无
  - 孫晷 · production_person · supporting: ambiguous；strong · conflicting: 无
- Review note: 本则“王文度”及后续“文度”为王坦之；不得解析为孙晷。

### 05-fangzheng-058 · 文度

- Mention: `shishuo-p3b-wave-1-995c939ec1285ead69dd0edd` · section: `main_text` · status: `resolved` · review: `reviewed`
- Context: 䣛上

文度因言桓求已女㛰藍田大怒排文度下䣛曰惡
見文度已復癡畏桓温靣兵那可嫁女與之【文度】還
報云下官家中先得㛰處桓公曰吾知矣此尊府君
不肯耳後桓女遂嫁文度兒
- Recommendation: 王坦之
- Candidates:
  - 王坦之 · identity_candidate · supporting: exact；strong · conflicting: 无
  - 孫晷 · production_person · supporting: ambiguous；strong · conflicting: 无
- Review note: 本则“王文度”及后续“文度”为王坦之；不得解析为孙晷。

### 05-fangzheng-058 · 文度

- Mention: `shishuo-p3b-wave-1-07c09f9b12fb863d97960b44` · section: `main_text` · status: `resolved` · review: `reviewed`
- Context: 温靣兵那可嫁女與之文度還
報云下官家中先得㛰處桓公曰吾知矣此尊府君
不肯耳後桓女遂嫁【文度】兒
- Recommendation: 王坦之
- Candidates:
  - 王坦之 · identity_candidate · supporting: exact；strong · conflicting: 无
  - 孫晷 · production_person · supporting: ambiguous；strong · conflicting: 无
- Review note: 本则“王文度”及后续“文度”为王坦之；不得解析为孙晷。

### 06-yaliang-019 · 太傅

- Mention: `shishuo-06-yaliang-019-liu-annotation-006` · section: `liu_annotation` · status: `candidate_for_review` · review: `candidate`
- Context: (妻【太傅】郗鑒女名璿字子房/王氏譜曰逸少羲之小字羲之)
- Reasons: insufficient_unique_local_context、shared_alias_surface
- Candidates:
  - 郗鑒 · production_person · supporting: ambiguous；medium · conflicting: insufficient_unique_local_context；shared_alias_surface
  - 謝安 · production_person · supporting: ambiguous；medium · conflicting: insufficient_unique_local_context；shared_alias_surface

### 06-yaliang-019 · 郗太傅

- Mention: `shishuo-06-yaliang-019-main-text-001` · section: `main_text` · status: `candidate_for_review` · review: `candidate`
- Context: 【郗太傅】在京口遣門生與王丞相書求女壻丞相語
郗信君往東廂任意選之門生歸白郗曰王家諸郎
亦皆可
- Reasons: contextual_surface_requires_local_evidence
- Candidates:
  - 郗鑒 · production_person · supporting: contextual；medium · conflicting: contextual_surface_requires_local_evidence

### 06-yaliang-019 · 王丞相

- Mention: `shishuo-06-yaliang-019-main-text-002` · section: `main_text` · status: `candidate_for_review` · review: `candidate`
- Context: 郗太傅在京口遣門生與【王丞相】書求女壻丞相語
郗信君往東廂任意選之門生歸白郗曰王家諸郎
亦皆可嘉聞來覓壻咸自矜持唯
- Reasons: insufficient_unique_local_context、shared_alias_surface
- Candidates:
  - 王隱 · identity_candidate · supporting: contextual；medium · conflicting: insufficient_unique_local_context；shared_alias_surface
  - 王導 · production_person · supporting: contextual；medium · conflicting: insufficient_unique_local_context；shared_alias_surface

### 06-yaliang-019 · 丞相

- Mention: `shishuo-06-yaliang-019-main-text-003` · section: `main_text` · status: `candidate_for_review` · review: `candidate`
- Context: 郗太傅在京口遣門生與王丞相書求女壻【丞相】語
郗信君往東廂任意選之門生歸白郗曰王家諸郎
亦皆可嘉聞來覓壻咸自矜持唯有一郎在東牀
- Reasons: contextual_surface_requires_local_evidence
- Candidates:
  - 王導 · production_person · supporting: ambiguous；medium · conflicting: contextual_surface_requires_local_evidence

### 06-yaliang-019 · 郗公

- Mention: `shishuo-06-yaliang-019-main-text-004` · section: `main_text` · status: `candidate_for_review` · review: `candidate`
- Context: 任意選之門生歸白郗曰王家諸郎
亦皆可嘉聞來覓壻咸自矜持唯有一郎在東牀上
坦腹卧如不聞【郗公】云正此好訪之乃是逸少因嫁
女與焉
- Reasons: contextual_surface_requires_local_evidence
- Candidates:
  - 郗鑒 · production_person · supporting: contextual；medium · conflicting: contextual_surface_requires_local_evidence

### 08-shangyu-077 · 王右軍

- Mention: `shishuo-08-shangyu-077-main-text-001` · section: `main_text` · status: `candidate_for_review` · review: `candidate`
- Context: 【王右軍】語劉尹故當共推安石劉尹曰若安石東山
志立當與天下共推之
- Reasons: contextual_surface_requires_local_evidence
- Candidates:
  - 王羲之 · production_person · supporting: contextual；medium · conflicting: contextual_surface_requires_local_evidence

### 09-pinzao-026 · 王公

- Mention: `shishuo-09-pinzao-026-liu-annotation-002` · section: `liu_annotation` · status: `candidate_for_review` · review: `candidate`
- Context: (謂必代巳相而此章以手指地/前篇及諸書皆云【王公】重何充)
- Reasons: insufficient_unique_local_context、shared_alias_surface
- Candidates:
  - 王羲之 · production_person · supporting: ambiguous；medium · conflicting: insufficient_unique_local_context；shared_alias_surface
  - 王導 · production_person · supporting: ambiguous；medium · conflicting: insufficient_unique_local_context；shared_alias_surface

### 09-pinzao-026 · 王丞相

- Mention: `shishuo-09-pinzao-026-main-text-001` · section: `main_text` · status: `candidate_for_review` · review: `candidate`
- Context: 【王丞相】云見謝仁祖恒令人得上與何次道語唯舉
手指地曰正自爾馨
- Reasons: insufficient_unique_local_context、shared_alias_surface
- Candidates:
  - 王隱 · identity_candidate · supporting: contextual；medium · conflicting: insufficient_unique_local_context；shared_alias_surface
  - 王導 · production_person · supporting: contextual；medium · conflicting: insufficient_unique_local_context；shared_alias_surface

### 09-pinzao-030 · 右軍

- Mention: `shishuo-09-pinzao-030-main-text-001` · section: `main_text` · status: `candidate_for_review` · review: `candidate`
- Context: 時人道阮思曠骨氣不及【右軍】簡秀不如真長韶潤
不如仲祖思致不如淵源而兼有諸人之美
- Reasons: contextual_surface_requires_local_evidence
- Candidates:
  - 王羲之 · production_person · supporting: contextual；medium · conflicting: contextual_surface_requires_local_evidence

### 09-pinzao-063 · 文度

- Mention: `shishuo-p3b-wave-1-904b54b78dd74ee3c584d112` · section: `main_text` · status: `candidate_for_review` · review: `candidate`
- Context: 庾道季云思理倫和吾愧康伯志力彊正吾愧【文度】
自此以還吾皆百之
- Reasons: insufficient_unique_local_context、shared_alias_surface
- Candidates:
  - 王坦之 · identity_candidate · supporting: exact；strong · conflicting: insufficient_unique_local_context；shared_alias_surface
  - 孫晷 · production_person · supporting: ambiguous；strong · conflicting: insufficient_unique_local_context；shared_alias_surface

### 23-rendan-013 · 仲容

- Mention: `shishuo-w3-38231138347d766d147ad8bc` · section: `main_text` · status: `resolved` · review: `reviewed`
- Context: 阮渾長成風氣韻度似父亦欲作逹步兵曰【仲容】已
預之卿不得復爾
- Recommendation: 阮咸
- Candidates:
  - 阮咸 · identity_candidate · supporting: contextual；strong · conflicting: 无
  - 石苞 · production_person · supporting: exact；strong · conflicting: 无
- Review note: 本则“步兵”即阮籍；“仲容”承接阮咸（阮仲容），不得因石苞亦字仲容而解析为石苞。
- Automatic-review conflict: automatic=candidate_for_review/无目标；已审核决定优先保留。

## Manual correction workflow

审阅此报告后，编辑 `data/annotation/person-resolution-decisions.json`，保留稳定的 Mention ID 与 Evidence ID；然后重新运行 `python3 scripts/build_person_resolution.py`，再重建 PersonStory 与 SC1。自动解析器更新不得覆盖已审核决定；若新证据与决定冲突，应进入报告而不是静默改写决定。
