# SFH2.2-A1R Challenge Review

Historical correctness is pending external review.

## sfh2-a0r-l-challenge-ca38e15c71e9339ddfee
- Story: `02-yanyu-060`
- Mention: `sfh1-mention-1663ef91cb1ebbf7819c2c5a` / `簡文`
- 正文: 簡文在暗室中坐召宣武宣武至問上何在簡文曰
某在斯時人以為能
- 刘注/证据: (及席子曰席也皆坐子告之曰/論語曰師冕見及階子曰階也) | (歴告坐中人也/某在斯某在斯注)
- Pass 1 valid: `True` record=`{"abstain": false, "attribute_type": "", "attribute_value": "", "bearer_hint": "", "confidence": "high", "discourse": {"addressee_hint": "", "antecedent_hint": "", "self_reference_hint": "", "speaker_hint": ""}, "explanation": "簡文 is the abbreviated ruler title for 簡文帝 (Emperor Jianwen of Jin), who is the subject of the anecdote sitting in a dark room and summoning 宣武 (桓溫). The validated local mention also classifies this as a ruler_title reference to a person.", "mention_id": "sfh1-mention-1663ef91cb1ebbf7819c2c5a", "occurrence_role": "scene_participant", "reference_type": "ruler_title", "referent": {"canonical_hint": "簡文帝", "confidence": "high", "surface_form": "簡文"}, "relations": [], "semantic_kind": "historical_person", "supporting_evidence_ids": ["sfh1-ev-02-yanyu-060-main"], "surface": "簡文"}`
- Python flags: `[]`
- Pass 2: `not_run` patch_ops=`[]`
- Pass 3: `` patch_ops=`[]`
- Final: `{"abstain": false, "attribute_type": "", "attribute_value": "", "bearer_hint": "", "confidence": "high", "discourse": {"addressee_hint": "", "antecedent_hint": "", "self_reference_hint": "", "speaker_hint": ""}, "explanation": "簡文 is the abbreviated ruler title for 簡文帝 (Emperor Jianwen of Jin), who is the subject of the anecdote sitting in a dark room and summoning 宣武 (桓溫). The validated local mention also classifies this as a ruler_title reference to a person.", "mention_id": "sfh1-mention-1663ef91cb1ebbf7819c2c5a", "occurrence_role": "scene_participant", "reference_type": "ruler_title", "referent": {"canonical_hint": "簡文帝", "confidence": "high", "surface_form": "簡文"}, "relations": [], "semantic_kind": "historical_person", "supporting_evidence_ids": ["sfh1-ev-02-yanyu-060-main"], "surface": "簡文"}`
- Historical correctness: pending external review
- Reviewer: [ ] correct  [ ] identity/canonicalization  [ ] semantic kind  [ ] role  [ ] discourse  [ ] wrong person  [ ] abstain  [ ] insufficient evidence
- Expected referent:
- Notes:

## sfh2-a0r-l-challenge-4da0dbd5f09e683bf525
- Story: `02-yanyu-060`
- Mention: `sfh1-mention-8735904c09b16a5eacd70ddd` / `上`
- 正文: 簡文在暗室中坐召宣武宣武至問上何在簡文曰
某在斯時人以為能
- 刘注/证据: (及席子曰席也皆坐子告之曰/論語曰師冕見及階子曰階也) | (歴告坐中人也/某在斯某在斯注)
- Pass 1 valid: `True` record=`{"abstain": false, "attribute_type": "", "attribute_value": "", "bearer_hint": "", "confidence": "high", "discourse": {"addressee_hint": "簡文", "antecedent_hint": "簡文", "self_reference_hint": "", "speaker_hint": "宣武"}, "explanation": "The target '上' is a ruler title referring to the emperor, who in this passage is 簡文 (簡文帝). 宣武 asks '上何在' (where is His Majesty), and 簡文 replies '某在斯' (I am here), confirming that '上' refers to 簡文帝 himself. The validated local mention sfh1-mention-1663ef91cb1ebbf7819c2c5a identifies 簡文 as the ruler in this scene.", "mention_id": "sfh1-mention-8735904c09b16a5eacd70ddd", "occurrence_role": "scene_participant", "reference_type": "ruler_title", "referent": {"canonical_hint": "簡文帝", "confidence": "high", "surface_form": "簡文"}, "relations": [{"confidence": "high", "evidence_ids": ["sfh1-ev-02-yanyu-060-main"], "relation": "same_person", "target_hint": "簡文"}], "semantic_kind": "historical_person", "supporting_evidence_ids": ["sfh1-ev-02-yanyu-060-main"], "surface": "上"}`
- Python flags: `[]`
- Pass 2: `not_run` patch_ops=`[]`
- Pass 3: `` patch_ops=`[]`
- Final: `{"abstain": false, "attribute_type": "", "attribute_value": "", "bearer_hint": "", "confidence": "high", "discourse": {"addressee_hint": "簡文", "antecedent_hint": "簡文", "self_reference_hint": "", "speaker_hint": "宣武"}, "explanation": "The target '上' is a ruler title referring to the emperor, who in this passage is 簡文 (簡文帝). 宣武 asks '上何在' (where is His Majesty), and 簡文 replies '某在斯' (I am here), confirming that '上' refers to 簡文帝 himself. The validated local mention sfh1-mention-1663ef91cb1ebbf7819c2c5a identifies 簡文 as the ruler in this scene.", "mention_id": "sfh1-mention-8735904c09b16a5eacd70ddd", "occurrence_role": "scene_participant", "reference_type": "ruler_title", "referent": {"canonical_hint": "簡文帝", "confidence": "high", "surface_form": "簡文"}, "relations": [{"confidence": "high", "evidence_ids": ["sfh1-ev-02-yanyu-060-main"], "relation": "same_person", "target_hint": "簡文"}], "semantic_kind": "historical_person", "supporting_evidence_ids": ["sfh1-ev-02-yanyu-060-main"], "surface": "上"}`
- Historical correctness: pending external review
- Reviewer: [ ] correct  [ ] identity/canonicalization  [ ] semantic kind  [ ] role  [ ] discourse  [ ] wrong person  [ ] abstain  [ ] insufficient evidence
- Expected referent:
- Notes:

## sfh2-a0r-l-challenge-d6f905cd870a3ab36901
- Story: `02-yanyu-060`
- Mention: `sfh1-mention-95c98b3b3f964502ef5e978a` / `某`
- 正文: 簡文在暗室中坐召宣武宣武至問上何在簡文曰
某在斯時人以為能
- 刘注/证据: (及席子曰席也皆坐子告之曰/論語曰師冕見及階子曰階也) | (歴告坐中人也/某在斯某在斯注)
- Pass 1 valid: `True` record=`{"abstain": false, "attribute_type": "", "attribute_value": "", "bearer_hint": "", "confidence": "high", "discourse": {"addressee_hint": "宣武", "antecedent_hint": "上", "self_reference_hint": "某", "speaker_hint": "簡文"}, "explanation": "簡文 (簡文帝) is sitting in a dark room and summons 宣武. When 宣武 asks where 上 (the emperor, i.e., 簡文) is, 簡文 replies '某在斯' — '某' is a self-referential pronoun used by 簡文 referring to himself. The Liu annotation cites the Analects passage about 師冕 where '某在斯' is used similarly as self-reference. Thus 某 refers to 簡文帝 himself.", "mention_id": "sfh1-mention-95c98b3b3f964502ef5e978a", "occurrence_role": "scene_participant", "reference_type": "pronoun_reference", "referent": {"canonical_hint": "簡文帝", "confidence": "high", "surface_form": "簡文"}, "relations": [{"confidence": "high", "evidence_ids": ["sfh1-ev-02-yanyu-060-main"], "relation": "same_person", "target_hint": "簡文"}, {"confidence": "high", "evidence_ids": ["sfh1-ev-02-yanyu-060-main"], "relation": "same_person", "target_hint": "上"}], "semantic_kind": "historical_person", "supporting_evidence_ids": ["sfh1-ev-02-yanyu-060-liu-annotation-002", "sfh1-ev-02-yanyu-060-main"], "surface": "某"}`
- Python flags: `[{"challenged_fields": ["relations", "referent.canonical_hint"], "evidence_ids": ["sfh1-ev-02-yanyu-060-liu-annotation-002", "sfh1-ev-02-yanyu-060-main"], "flag_type": "multi_candidate_ambiguity", "formal_reason": "the record supplies more than one structured relation target", "involved": ["relations"], "severity": "review"}]`
- Pass 2: `confirm` patch_ops=`[]`
- Pass 3: `` patch_ops=`[]`
- Final: `{"abstain": false, "attribute_type": "", "attribute_value": "", "bearer_hint": "", "confidence": "high", "discourse": {"addressee_hint": "宣武", "antecedent_hint": "上", "self_reference_hint": "某", "speaker_hint": "簡文"}, "explanation": "簡文 (簡文帝) is sitting in a dark room and summons 宣武. When 宣武 asks where 上 (the emperor, i.e., 簡文) is, 簡文 replies '某在斯' — '某' is a self-referential pronoun used by 簡文 referring to himself. The Liu annotation cites the Analects passage about 師冕 where '某在斯' is used similarly as self-reference. Thus 某 refers to 簡文帝 himself.", "mention_id": "sfh1-mention-95c98b3b3f964502ef5e978a", "occurrence_role": "scene_participant", "reference_type": "pronoun_reference", "referent": {"canonical_hint": "簡文帝", "confidence": "high", "surface_form": "簡文"}, "relations": [{"confidence": "high", "evidence_ids": ["sfh1-ev-02-yanyu-060-main"], "relation": "same_person", "target_hint": "簡文"}, {"confidence": "high", "evidence_ids": ["sfh1-ev-02-yanyu-060-main"], "relation": "same_person", "target_hint": "上"}], "semantic_kind": "historical_person", "supporting_evidence_ids": ["sfh1-ev-02-yanyu-060-liu-annotation-002", "sfh1-ev-02-yanyu-060-main"], "surface": "某"}`
- Historical correctness: pending external review
- Reviewer: [ ] correct  [ ] identity/canonicalization  [ ] semantic kind  [ ] role  [ ] discourse  [ ] wrong person  [ ] abstain  [ ] insufficient evidence
- Expected referent:
- Notes:

## sfh2-a0r-l-challenge-c07bd51ac298529ddbc6
- Story: `02-yanyu-060`
- Mention: `sfh1-mention-ab67a4ad2c4c7c6e27fa4921` / `宣武`
- 正文: 簡文在暗室中坐召宣武宣武至問上何在簡文曰
某在斯時人以為能
- 刘注/证据: (及席子曰席也皆坐子告之曰/論語曰師冕見及階子曰階也) | (歴告坐中人也/某在斯某在斯注)
- Pass 1 valid: `True` record=`{"abstain": false, "attribute_type": "", "attribute_value": "", "bearer_hint": "", "confidence": "high", "discourse": {"addressee_hint": "宣武", "antecedent_hint": "", "self_reference_hint": "", "speaker_hint": "簡文"}, "explanation": "宣武 is the posthumous title (ruler title) of 桓溫 (Huan Wen), the famous Eastern Jin general and statesman. In the Shishuo Xinyu, 宣武 is a standard epithet referring to 桓溫. The text describes 簡文 (Emperor Jianwen) summoning 宣武, who arrives and asks where the emperor is. The mention functions as a scene participant in the narrative.", "mention_id": "sfh1-mention-ab67a4ad2c4c7c6e27fa4921", "occurrence_role": "scene_participant", "reference_type": "ruler_title", "referent": {"canonical_hint": "桓溫", "confidence": "high", "surface_form": "宣武"}, "relations": [], "semantic_kind": "historical_person", "supporting_evidence_ids": ["sfh1-ev-02-yanyu-060-main"], "surface": "宣武"}`
- Python flags: `[]`
- Pass 2: `not_run` patch_ops=`[]`
- Pass 3: `` patch_ops=`[]`
- Final: `{"abstain": false, "attribute_type": "", "attribute_value": "", "bearer_hint": "", "confidence": "high", "discourse": {"addressee_hint": "宣武", "antecedent_hint": "", "self_reference_hint": "", "speaker_hint": "簡文"}, "explanation": "宣武 is the posthumous title (ruler title) of 桓溫 (Huan Wen), the famous Eastern Jin general and statesman. In the Shishuo Xinyu, 宣武 is a standard epithet referring to 桓溫. The text describes 簡文 (Emperor Jianwen) summoning 宣武, who arrives and asks where the emperor is. The mention functions as a scene participant in the narrative.", "mention_id": "sfh1-mention-ab67a4ad2c4c7c6e27fa4921", "occurrence_role": "scene_participant", "reference_type": "ruler_title", "referent": {"canonical_hint": "桓溫", "confidence": "high", "surface_form": "宣武"}, "relations": [], "semantic_kind": "historical_person", "supporting_evidence_ids": ["sfh1-ev-02-yanyu-060-main"], "surface": "宣武"}`
- Historical correctness: pending external review
- Reviewer: [ ] correct  [ ] identity/canonicalization  [ ] semantic kind  [ ] role  [ ] discourse  [ ] wrong person  [ ] abstain  [ ] insufficient evidence
- Expected referent:
- Notes:

## sfh2-a0r-l-challenge-9f9ed8dfbf2c970a72e2
- Story: `09-pinzao-063`
- Mention: `sfh1-mention-276c292df4447b07909ecf22` / `吾`
- 正文: 庾道季云思理倫和吾愧康伯志力彊正吾愧文度
自此以還吾皆百之
- 刘注/证据: (巳見/庾龢)
- Pass 1 valid: `True` record=`{"abstain": false, "attribute_type": "", "attribute_value": "", "bearer_hint": "", "confidence": "high", "discourse": {"addressee_hint": "", "antecedent_hint": "庾道季", "self_reference_hint": "吾", "speaker_hint": "庾道季"}, "explanation": "The pronoun 吾 is the first-person self-reference of the speaker 庾道季 (庾龢), who opens the passage with '庾道季云'. The Liu annotation confirms 庾道季 is 庾龢. The pronoun refers to the speaker himself.", "mention_id": "sfh1-mention-276c292df4447b07909ecf22", "occurrence_role": "speaker_reference", "reference_type": "pronoun_reference", "referent": {"canonical_hint": "庾龢", "confidence": "high", "surface_form": "庾道季"}, "relations": [{"confidence": "high", "evidence_ids": ["sfh1-ev-09-pinzao-063-main"], "relation": "same_person", "target_hint": "庾道季"}, {"confidence": "high", "evidence_ids": ["sfh1-ev-09-pinzao-063-liu-annotation-001"], "relation": "same_person", "target_hint": "庾龢"}], "semantic_kind": "historical_person", "supporting_evidence_ids": ["sfh1-ev-09-pinzao-063-liu-annotation-001", "sfh1-ev-09-pinzao-063-main"], "surface": "吾"}`
- Python flags: `[{"challenged_fields": ["relations", "referent.canonical_hint"], "evidence_ids": ["sfh1-ev-09-pinzao-063-liu-annotation-001", "sfh1-ev-09-pinzao-063-main"], "flag_type": "multi_candidate_ambiguity", "formal_reason": "the record supplies more than one structured relation target", "involved": ["relations"], "severity": "review"}]`
- Pass 2: `confirm` patch_ops=`[]`
- Pass 3: `` patch_ops=`[]`
- Final: `{"abstain": false, "attribute_type": "", "attribute_value": "", "bearer_hint": "", "confidence": "high", "discourse": {"addressee_hint": "", "antecedent_hint": "庾道季", "self_reference_hint": "吾", "speaker_hint": "庾道季"}, "explanation": "The pronoun 吾 is the first-person self-reference of the speaker 庾道季 (庾龢), who opens the passage with '庾道季云'. The Liu annotation confirms 庾道季 is 庾龢. The pronoun refers to the speaker himself.", "mention_id": "sfh1-mention-276c292df4447b07909ecf22", "occurrence_role": "speaker_reference", "reference_type": "pronoun_reference", "referent": {"canonical_hint": "庾龢", "confidence": "high", "surface_form": "庾道季"}, "relations": [{"confidence": "high", "evidence_ids": ["sfh1-ev-09-pinzao-063-main"], "relation": "same_person", "target_hint": "庾道季"}, {"confidence": "high", "evidence_ids": ["sfh1-ev-09-pinzao-063-liu-annotation-001"], "relation": "same_person", "target_hint": "庾龢"}], "semantic_kind": "historical_person", "supporting_evidence_ids": ["sfh1-ev-09-pinzao-063-liu-annotation-001", "sfh1-ev-09-pinzao-063-main"], "surface": "吾"}`
- Historical correctness: pending external review
- Reviewer: [ ] correct  [ ] identity/canonicalization  [ ] semantic kind  [ ] role  [ ] discourse  [ ] wrong person  [ ] abstain  [ ] insufficient evidence
- Expected referent:
- Notes:

## sfh2-a0r-l-challenge-f56a3b1584f60d143182
- Story: `09-pinzao-063`
- Mention: `sfh1-mention-5bb2371849b54e407a64c88f` / `康伯`
- 正文: 庾道季云思理倫和吾愧康伯志力彊正吾愧文度
自此以還吾皆百之
- 刘注/证据: (巳見/庾龢)
- Pass 1 valid: `True` record=`{"abstain": false, "attribute_type": "", "attribute_value": "", "bearer_hint": "", "confidence": "high", "discourse": {"addressee_hint": "", "antecedent_hint": "", "self_reference_hint": "", "speaker_hint": "庾道季"}, "explanation": "庾道季（庾龢）在品藻篇中自述，稱自己在思理倫和方面不如康伯，在志力彊正方面不如文度。康伯即韓康伯（韓伯），字康伯，東晉名士，為庾道季品評的對象。此處以字稱之，屬個人名號指稱。", "mention_id": "sfh1-mention-5bb2371849b54e407a64c88f", "occurrence_role": "scene_reference", "reference_type": "personal_name", "referent": {"canonical_hint": "韓康伯", "confidence": "high", "surface_form": "康伯"}, "relations": [], "semantic_kind": "historical_person", "supporting_evidence_ids": ["sfh1-ev-09-pinzao-063-main"], "surface": "康伯"}`
- Python flags: `[]`
- Pass 2: `not_run` patch_ops=`[]`
- Pass 3: `` patch_ops=`[]`
- Final: `{"abstain": false, "attribute_type": "", "attribute_value": "", "bearer_hint": "", "confidence": "high", "discourse": {"addressee_hint": "", "antecedent_hint": "", "self_reference_hint": "", "speaker_hint": "庾道季"}, "explanation": "庾道季（庾龢）在品藻篇中自述，稱自己在思理倫和方面不如康伯，在志力彊正方面不如文度。康伯即韓康伯（韓伯），字康伯，東晉名士，為庾道季品評的對象。此處以字稱之，屬個人名號指稱。", "mention_id": "sfh1-mention-5bb2371849b54e407a64c88f", "occurrence_role": "scene_reference", "reference_type": "personal_name", "referent": {"canonical_hint": "韓康伯", "confidence": "high", "surface_form": "康伯"}, "relations": [], "semantic_kind": "historical_person", "supporting_evidence_ids": ["sfh1-ev-09-pinzao-063-main"], "surface": "康伯"}`
- Historical correctness: pending external review
- Reviewer: [ ] correct  [ ] identity/canonicalization  [ ] semantic kind  [ ] role  [ ] discourse  [ ] wrong person  [ ] abstain  [ ] insufficient evidence
- Expected referent:
- Notes:

## sfh2-a0r-l-challenge-a1f887b7602c151cfbbd
- Story: `09-pinzao-063`
- Mention: `sfh1-mention-8c4dd2dce67987b657849bbb` / `文度`
- 正文: 庾道季云思理倫和吾愧康伯志力彊正吾愧文度
自此以還吾皆百之
- 刘注/证据: (巳見/庾龢)
- Pass 1 valid: `True` record=`{"abstain": false, "attribute_type": "", "attribute_value": "", "bearer_hint": "", "confidence": "high", "discourse": {"addressee_hint": "", "antecedent_hint": "", "self_reference_hint": "", "speaker_hint": "庾道季"}, "explanation": "文度 is the courtesy name (字) of 王坦之, a well-known Eastern Jin figure. In this passage, 庾道季 (庾龢) compares himself to 康伯 (韓伯) and 文度 (王坦之), saying he is inferior to them in reasoning and willpower respectively. The context of self-comparison with named contemporaries confirms 文度 refers to 王坦之.", "mention_id": "sfh1-mention-8c4dd2dce67987b657849bbb", "occurrence_role": "scene_reference", "reference_type": "personal_name", "referent": {"canonical_hint": "王坦之", "confidence": "high", "surface_form": "文度"}, "relations": [], "semantic_kind": "historical_person", "supporting_evidence_ids": ["sfh1-ev-09-pinzao-063-main"], "surface": "文度"}`
- Python flags: `[]`
- Pass 2: `not_run` patch_ops=`[]`
- Pass 3: `` patch_ops=`[]`
- Final: `{"abstain": false, "attribute_type": "", "attribute_value": "", "bearer_hint": "", "confidence": "high", "discourse": {"addressee_hint": "", "antecedent_hint": "", "self_reference_hint": "", "speaker_hint": "庾道季"}, "explanation": "文度 is the courtesy name (字) of 王坦之, a well-known Eastern Jin figure. In this passage, 庾道季 (庾龢) compares himself to 康伯 (韓伯) and 文度 (王坦之), saying he is inferior to them in reasoning and willpower respectively. The context of self-comparison with named contemporaries confirms 文度 refers to 王坦之.", "mention_id": "sfh1-mention-8c4dd2dce67987b657849bbb", "occurrence_role": "scene_reference", "reference_type": "personal_name", "referent": {"canonical_hint": "王坦之", "confidence": "high", "surface_form": "文度"}, "relations": [], "semantic_kind": "historical_person", "supporting_evidence_ids": ["sfh1-ev-09-pinzao-063-main"], "surface": "文度"}`
- Historical correctness: pending external review
- Reviewer: [ ] correct  [ ] identity/canonicalization  [ ] semantic kind  [ ] role  [ ] discourse  [ ] wrong person  [ ] abstain  [ ] insufficient evidence
- Expected referent:
- Notes:

## sfh2-a0r-l-challenge-085c578513fc50a423b8
- Story: `09-pinzao-063`
- Mention: `sfh1-mention-bdb58dbb3ac4499e9b54af71` / `庾道季`
- 正文: 庾道季云思理倫和吾愧康伯志力彊正吾愧文度
自此以還吾皆百之
- 刘注/证据: (巳見/庾龢)
- Pass 1 valid: `True` record=`{"abstain": false, "attribute_type": "", "attribute_value": "", "bearer_hint": "", "confidence": "high", "discourse": {"addressee_hint": "", "antecedent_hint": "", "self_reference_hint": "", "speaker_hint": ""}, "explanation": "庾道季 is the courtesy name (字) of 庾龢, as confirmed by the Liu Xiaobiao annotation which explicitly identifies 庾道季 as 庾龢 (巳見/庾龢). The annotation directly links the courtesy name to the person 庾龢.", "mention_id": "sfh1-mention-bdb58dbb3ac4499e9b54af71", "occurrence_role": "scene_participant", "reference_type": "courtesy_name", "referent": {"canonical_hint": "庾龢", "confidence": "high", "surface_form": "庾龢"}, "relations": [{"confidence": "high", "evidence_ids": ["sfh1-ev-09-pinzao-063-liu-annotation-001"], "relation": "same_person", "target_hint": "庾龢"}], "semantic_kind": "historical_person", "supporting_evidence_ids": ["sfh1-ev-09-pinzao-063-liu-annotation-001", "sfh1-ev-09-pinzao-063-main"], "surface": "庾道季"}`
- Python flags: `[]`
- Pass 2: `not_run` patch_ops=`[]`
- Pass 3: `` patch_ops=`[]`
- Final: `{"abstain": false, "attribute_type": "", "attribute_value": "", "bearer_hint": "", "confidence": "high", "discourse": {"addressee_hint": "", "antecedent_hint": "", "self_reference_hint": "", "speaker_hint": ""}, "explanation": "庾道季 is the courtesy name (字) of 庾龢, as confirmed by the Liu Xiaobiao annotation which explicitly identifies 庾道季 as 庾龢 (巳見/庾龢). The annotation directly links the courtesy name to the person 庾龢.", "mention_id": "sfh1-mention-bdb58dbb3ac4499e9b54af71", "occurrence_role": "scene_participant", "reference_type": "courtesy_name", "referent": {"canonical_hint": "庾龢", "confidence": "high", "surface_form": "庾龢"}, "relations": [{"confidence": "high", "evidence_ids": ["sfh1-ev-09-pinzao-063-liu-annotation-001"], "relation": "same_person", "target_hint": "庾龢"}], "semantic_kind": "historical_person", "supporting_evidence_ids": ["sfh1-ev-09-pinzao-063-liu-annotation-001", "sfh1-ev-09-pinzao-063-main"], "surface": "庾道季"}`
- Historical correctness: pending external review
- Reviewer: [ ] correct  [ ] identity/canonicalization  [ ] semantic kind  [ ] role  [ ] discourse  [ ] wrong person  [ ] abstain  [ ] insufficient evidence
- Expected referent:
- Notes:

## sfh2-a0r-l-challenge-658f5ff4b4c73e39fcc7
- Story: `10-guizhen-011`
- Mention: `sfh1-mention-5b43c6c928ff32f0bdcf27f2` / `身`
- 正文: 元帝過江猶好酒王茂弘與帝有舊常流涕諌帝許
之命酌酒一酣從是遂斷
- 刘注/证据: (以先時務性素好酒将渡/鄧粲晉紀曰上身服儉約) | (遂不復飲克己復禮官修其方而中興之業隆焉/江王導深以諌帝乃令左右進觴飲而覆之自是)
- Pass 1 valid: `True` record=`{"abstain": false, "attribute_type": "", "attribute_value": "", "bearer_hint": "", "confidence": "high", "discourse": {"addressee_hint": "", "antecedent_hint": "元帝", "self_reference_hint": "", "speaker_hint": "鄧粲"}, "explanation": "The character 身 in the Liu annotation (鄧粲晉紀曰上身服儉約) is a self-referential pronoun used by the emperor (元帝/司馬睿) in the quoted Jin Annals text, referring to himself. The main text establishes 元帝 as the subject, and the annotation quotes 鄧粲's 晉紀 where the emperor speaks of his own frugality. The pronoun 身 refers to the emperor himself.", "mention_id": "sfh1-mention-5b43c6c928ff32f0bdcf27f2", "occurrence_role": "scene_participant", "reference_type": "pronoun_reference", "referent": {"canonical_hint": "司馬睿", "confidence": "high", "surface_form": "元帝"}, "relations": [{"confidence": "high", "evidence_ids": ["sfh1-ev-10-guizhen-011-liu-annotation-001", "sfh1-ev-10-guizhen-011-main"], "relation": "same_person", "target_hint": "元帝"}], "semantic_kind": "historical_person", "supporting_evidence_ids": ["sfh1-ev-10-guizhen-011-liu-annotation-001", "sfh1-ev-10-guizhen-011-main"], "surface": "身"}`
- Python flags: `[]`
- Pass 2: `not_run` patch_ops=`[]`
- Pass 3: `` patch_ops=`[]`
- Final: `{"abstain": false, "attribute_type": "", "attribute_value": "", "bearer_hint": "", "confidence": "high", "discourse": {"addressee_hint": "", "antecedent_hint": "元帝", "self_reference_hint": "", "speaker_hint": "鄧粲"}, "explanation": "The character 身 in the Liu annotation (鄧粲晉紀曰上身服儉約) is a self-referential pronoun used by the emperor (元帝/司馬睿) in the quoted Jin Annals text, referring to himself. The main text establishes 元帝 as the subject, and the annotation quotes 鄧粲's 晉紀 where the emperor speaks of his own frugality. The pronoun 身 refers to the emperor himself.", "mention_id": "sfh1-mention-5b43c6c928ff32f0bdcf27f2", "occurrence_role": "scene_participant", "reference_type": "pronoun_reference", "referent": {"canonical_hint": "司馬睿", "confidence": "high", "surface_form": "元帝"}, "relations": [{"confidence": "high", "evidence_ids": ["sfh1-ev-10-guizhen-011-liu-annotation-001", "sfh1-ev-10-guizhen-011-main"], "relation": "same_person", "target_hint": "元帝"}], "semantic_kind": "historical_person", "supporting_evidence_ids": ["sfh1-ev-10-guizhen-011-liu-annotation-001", "sfh1-ev-10-guizhen-011-main"], "surface": "身"}`
- Historical correctness: pending external review
- Reviewer: [ ] correct  [ ] identity/canonicalization  [ ] semantic kind  [ ] role  [ ] discourse  [ ] wrong person  [ ] abstain  [ ] insufficient evidence
- Expected referent:
- Notes:

## sfh2-a0r-l-challenge-02fa84b24af39e8f8201
- Story: `10-guizhen-011`
- Mention: `sfh1-mention-7c1312947bb4dfbe3311f264` / `帝`
- 正文: 元帝過江猶好酒王茂弘與帝有舊常流涕諌帝許
之命酌酒一酣從是遂斷
- 刘注/证据: (以先時務性素好酒将渡/鄧粲晉紀曰上身服儉約) | (遂不復飲克己復禮官修其方而中興之業隆焉/江王導深以諌帝乃令左右進觴飲而覆之自是)
- Pass 1 valid: `True` record=`{"abstain": false, "attribute_type": "", "attribute_value": "", "bearer_hint": "", "confidence": "high", "discourse": {"addressee_hint": "帝", "antecedent_hint": "元帝", "self_reference_hint": "", "speaker_hint": "王導"}, "explanation": "The target '帝' in the Liu annotation refers to the emperor (元帝), who is the subject of the anecdote about giving up wine. The main text establishes 元帝 as the emperor who crossed the Yangtze and loved wine; the Liu annotation continues this narrative with 王導 advising the emperor (帝), who then orders wine to be poured and pours it out. The ruler title '帝' refers to 元帝 (Emperor Yuan of Jin).", "mention_id": "sfh1-mention-7c1312947bb4dfbe3311f264", "occurrence_role": "scene_participant", "reference_type": "ruler_title", "referent": {"canonical_hint": "元帝", "confidence": "high", "surface_form": "帝"}, "relations": [{"confidence": "high", "evidence_ids": ["sfh1-ev-10-guizhen-011-liu-annotation-002", "sfh1-ev-10-guizhen-011-main"], "relation": "same_person", "target_hint": "元帝"}, {"confidence": "high", "evidence_ids": ["sfh1-ev-10-guizhen-011-liu-annotation-002"], "relation": "related_person", "target_hint": "王導"}], "semantic_kind": "historical_person", "supporting_evidence_ids": ["sfh1-ev-10-guizhen-011-liu-annotation-002", "sfh1-ev-10-guizhen-011-main"], "surface": "帝"}`
- Python flags: `[{"challenged_fields": ["relations", "referent.canonical_hint"], "evidence_ids": ["sfh1-ev-10-guizhen-011-liu-annotation-002", "sfh1-ev-10-guizhen-011-main"], "flag_type": "multi_candidate_ambiguity", "formal_reason": "the record supplies more than one structured relation target", "involved": ["relations"], "severity": "review"}]`
- Pass 2: `confirm` patch_ops=`[]`
- Pass 3: `` patch_ops=`[]`
- Final: `{"abstain": false, "attribute_type": "", "attribute_value": "", "bearer_hint": "", "confidence": "high", "discourse": {"addressee_hint": "帝", "antecedent_hint": "元帝", "self_reference_hint": "", "speaker_hint": "王導"}, "explanation": "The target '帝' in the Liu annotation refers to the emperor (元帝), who is the subject of the anecdote about giving up wine. The main text establishes 元帝 as the emperor who crossed the Yangtze and loved wine; the Liu annotation continues this narrative with 王導 advising the emperor (帝), who then orders wine to be poured and pours it out. The ruler title '帝' refers to 元帝 (Emperor Yuan of Jin).", "mention_id": "sfh1-mention-7c1312947bb4dfbe3311f264", "occurrence_role": "scene_participant", "reference_type": "ruler_title", "referent": {"canonical_hint": "元帝", "confidence": "high", "surface_form": "帝"}, "relations": [{"confidence": "high", "evidence_ids": ["sfh1-ev-10-guizhen-011-liu-annotation-002", "sfh1-ev-10-guizhen-011-main"], "relation": "same_person", "target_hint": "元帝"}, {"confidence": "high", "evidence_ids": ["sfh1-ev-10-guizhen-011-liu-annotation-002"], "relation": "related_person", "target_hint": "王導"}], "semantic_kind": "historical_person", "supporting_evidence_ids": ["sfh1-ev-10-guizhen-011-liu-annotation-002", "sfh1-ev-10-guizhen-011-main"], "surface": "帝"}`
- Historical correctness: pending external review
- Reviewer: [ ] correct  [ ] identity/canonicalization  [ ] semantic kind  [ ] role  [ ] discourse  [ ] wrong person  [ ] abstain  [ ] insufficient evidence
- Expected referent:
- Notes:

## sfh2-a0r-l-challenge-89f9145a59affa7c29dd
- Story: `10-guizhen-011`
- Mention: `sfh1-mention-cc8016114f176363bb5353de` / `帝`
- 正文: 元帝過江猶好酒王茂弘與帝有舊常流涕諌帝許
之命酌酒一酣從是遂斷
- 刘注/证据: (以先時務性素好酒将渡/鄧粲晉紀曰上身服儉約) | (遂不復飲克己復禮官修其方而中興之業隆焉/江王導深以諌帝乃令左右進觴飲而覆之自是)
- Pass 1 valid: `True` record=`{"abstain": false, "attribute_type": "", "attribute_value": "", "bearer_hint": "", "confidence": "high", "discourse": {"addressee_hint": "", "antecedent_hint": "元帝", "self_reference_hint": "", "speaker_hint": ""}, "explanation": "The target '帝' in the main text refers to 元帝 (Emperor Yuan of Jin), who is the subject of the story about crossing the Yangtze and loving wine. The preceding mention '元帝' establishes the referent, and '帝' is a ruler title referring to the same person. The Liu annotation confirms this with '帝' referring to the same emperor, and 王導 (王茂弘) advising him.", "mention_id": "sfh1-mention-cc8016114f176363bb5353de", "occurrence_role": "scene_participant", "reference_type": "ruler_title", "referent": {"canonical_hint": "元帝", "confidence": "high", "surface_form": "帝"}, "relations": [{"confidence": "high", "evidence_ids": ["sfh1-ev-10-guizhen-011-main"], "relation": "same_person", "target_hint": "元帝"}], "semantic_kind": "historical_person", "supporting_evidence_ids": ["sfh1-ev-10-guizhen-011-main"], "surface": "帝"}`
- Python flags: `[]`
- Pass 2: `not_run` patch_ops=`[]`
- Pass 3: `` patch_ops=`[]`
- Final: `{"abstain": false, "attribute_type": "", "attribute_value": "", "bearer_hint": "", "confidence": "high", "discourse": {"addressee_hint": "", "antecedent_hint": "元帝", "self_reference_hint": "", "speaker_hint": ""}, "explanation": "The target '帝' in the main text refers to 元帝 (Emperor Yuan of Jin), who is the subject of the story about crossing the Yangtze and loving wine. The preceding mention '元帝' establishes the referent, and '帝' is a ruler title referring to the same person. The Liu annotation confirms this with '帝' referring to the same emperor, and 王導 (王茂弘) advising him.", "mention_id": "sfh1-mention-cc8016114f176363bb5353de", "occurrence_role": "scene_participant", "reference_type": "ruler_title", "referent": {"canonical_hint": "元帝", "confidence": "high", "surface_form": "帝"}, "relations": [{"confidence": "high", "evidence_ids": ["sfh1-ev-10-guizhen-011-main"], "relation": "same_person", "target_hint": "元帝"}], "semantic_kind": "historical_person", "supporting_evidence_ids": ["sfh1-ev-10-guizhen-011-main"], "surface": "帝"}`
- Historical correctness: pending external review
- Reviewer: [ ] correct  [ ] identity/canonicalization  [ ] semantic kind  [ ] role  [ ] discourse  [ ] wrong person  [ ] abstain  [ ] insufficient evidence
- Expected referent:
- Notes:

## sfh2-a0r-l-challenge-e02bee5567f8f9ad36ed
- Story: `10-guizhen-011`
- Mention: `sfh1-mention-f76e3acfc72f5c31b635e5e5` / `元帝`
- 正文: 元帝過江猶好酒王茂弘與帝有舊常流涕諌帝許
之命酌酒一酣從是遂斷
- 刘注/证据: (以先時務性素好酒将渡/鄧粲晉紀曰上身服儉約) | (遂不復飲克己復禮官修其方而中興之業隆焉/江王導深以諌帝乃令左右進觴飲而覆之自是)
- Pass 1 valid: `True` record=`{"abstain": false, "attribute_type": "", "attribute_value": "", "bearer_hint": "", "confidence": "high", "discourse": {"addressee_hint": "", "antecedent_hint": "", "self_reference_hint": "", "speaker_hint": ""}, "explanation": "元帝 refers to Emperor Yuan of Jin (司馬睿), the founding emperor of the Eastern Jin dynasty. The main text describes him crossing the Yangtze and loving wine, with 王茂弘 (Wang Dao) advising him. The Liu annotation confirms this with 王導 (Wang Dao) admonishing 帝 (the emperor), establishing the referent as 晉元帝司馬睿.", "mention_id": "sfh1-mention-f76e3acfc72f5c31b635e5e5", "occurrence_role": "scene_participant", "reference_type": "ruler_title", "referent": {"canonical_hint": "晉元帝司馬睿", "confidence": "high", "surface_form": "元帝"}, "relations": [{"confidence": "high", "evidence_ids": ["sfh1-ev-10-guizhen-011-main"], "relation": "related_person", "target_hint": "王茂弘"}, {"confidence": "high", "evidence_ids": ["sfh1-ev-10-guizhen-011-liu-annotation-002"], "relation": "same_person", "target_hint": "王導"}], "semantic_kind": "historical_person", "supporting_evidence_ids": ["sfh1-ev-10-guizhen-011-liu-annotation-002", "sfh1-ev-10-guizhen-011-main"], "surface": "元帝"}`
- Python flags: `[{"challenged_fields": ["relations", "referent.canonical_hint"], "evidence_ids": ["sfh1-ev-10-guizhen-011-liu-annotation-002", "sfh1-ev-10-guizhen-011-main"], "flag_type": "multi_candidate_ambiguity", "formal_reason": "the record supplies more than one structured relation target", "involved": ["relations"], "severity": "review"}]`
- Pass 2: `confirm` patch_ops=`[]`
- Pass 3: `` patch_ops=`[]`
- Final: `{"abstain": false, "attribute_type": "", "attribute_value": "", "bearer_hint": "", "confidence": "high", "discourse": {"addressee_hint": "", "antecedent_hint": "", "self_reference_hint": "", "speaker_hint": ""}, "explanation": "元帝 refers to Emperor Yuan of Jin (司馬睿), the founding emperor of the Eastern Jin dynasty. The main text describes him crossing the Yangtze and loving wine, with 王茂弘 (Wang Dao) advising him. The Liu annotation confirms this with 王導 (Wang Dao) admonishing 帝 (the emperor), establishing the referent as 晉元帝司馬睿.", "mention_id": "sfh1-mention-f76e3acfc72f5c31b635e5e5", "occurrence_role": "scene_participant", "reference_type": "ruler_title", "referent": {"canonical_hint": "晉元帝司馬睿", "confidence": "high", "surface_form": "元帝"}, "relations": [{"confidence": "high", "evidence_ids": ["sfh1-ev-10-guizhen-011-main"], "relation": "related_person", "target_hint": "王茂弘"}, {"confidence": "high", "evidence_ids": ["sfh1-ev-10-guizhen-011-liu-annotation-002"], "relation": "same_person", "target_hint": "王導"}], "semantic_kind": "historical_person", "supporting_evidence_ids": ["sfh1-ev-10-guizhen-011-liu-annotation-002", "sfh1-ev-10-guizhen-011-main"], "surface": "元帝"}`
- Historical correctness: pending external review
- Reviewer: [ ] correct  [ ] identity/canonicalization  [ ] semantic kind  [ ] role  [ ] discourse  [ ] wrong person  [ ] abstain  [ ] insufficient evidence
- Expected referent:
- Notes:

## sfh2-a0r-l-challenge-403815fa3c873916f991
- Story: `21-qiaoyi-011`
- Mention: `sfh1-mention-009afca0c45e584746b5fb51` / `殷荆州`
- 正文: 顧長康好寫起人形欲圖殷荆州殷
曰我形惡不煩耳顧曰明府正為眼爾但明
㸃童子飛白拂其上使如輕雲之蔽日
- 刘注/证据: (之圖寫特妙/續晉陽秋曰愷) | (目故也/仲堪眇) | (作月/日一)
- Pass 1 valid: `True` record=`{"abstain": false, "attribute_type": "", "attribute_value": "", "bearer_hint": "", "confidence": "high", "discourse": {"addressee_hint": "殷仲堪", "antecedent_hint": "殷仲堪", "self_reference_hint": "", "speaker_hint": "顧長康"}, "explanation": "殷荆州 is an office title (荆州刺史) used to refer to 殷仲堪, as confirmed by the Liu annotation identifying 仲堪. The main text shows 顧長康 wanting to paint 殷荆州's portrait, and 殷荆州 responds with 我形惡, establishing him as a scene participant. The annotation '仲堪眇' confirms the referent is 殷仲堪.", "mention_id": "sfh1-mention-009afca0c45e584746b5fb51", "occurrence_role": "scene_participant", "reference_type": "office_title", "referent": {"canonical_hint": "殷仲堪", "confidence": "high", "surface_form": "殷仲堪"}, "relations": [{"confidence": "high", "evidence_ids": ["sfh1-ev-21-qiaoyi-011-liu-annotation-002"], "relation": "same_person", "target_hint": "仲堪"}, {"confidence": "high", "evidence_ids": ["sfh1-ev-21-qiaoyi-011-main"], "relation": "related_person", "target_hint": "顧長康"}], "semantic_kind": "historical_person", "supporting_evidence_ids": ["sfh1-ev-21-qiaoyi-011-liu-annotation-002", "sfh1-ev-21-qiaoyi-011-main"], "surface": "殷荆州"}`
- Python flags: `[{"challenged_fields": ["relations", "referent.canonical_hint"], "evidence_ids": ["sfh1-ev-21-qiaoyi-011-liu-annotation-002", "sfh1-ev-21-qiaoyi-011-main"], "flag_type": "multi_candidate_ambiguity", "formal_reason": "the record supplies more than one structured relation target", "involved": ["relations"], "severity": "review"}]`
- Pass 2: `confirm` patch_ops=`[]`
- Pass 3: `` patch_ops=`[]`
- Final: `{"abstain": false, "attribute_type": "", "attribute_value": "", "bearer_hint": "", "confidence": "high", "discourse": {"addressee_hint": "殷仲堪", "antecedent_hint": "殷仲堪", "self_reference_hint": "", "speaker_hint": "顧長康"}, "explanation": "殷荆州 is an office title (荆州刺史) used to refer to 殷仲堪, as confirmed by the Liu annotation identifying 仲堪. The main text shows 顧長康 wanting to paint 殷荆州's portrait, and 殷荆州 responds with 我形惡, establishing him as a scene participant. The annotation '仲堪眇' confirms the referent is 殷仲堪.", "mention_id": "sfh1-mention-009afca0c45e584746b5fb51", "occurrence_role": "scene_participant", "reference_type": "office_title", "referent": {"canonical_hint": "殷仲堪", "confidence": "high", "surface_form": "殷仲堪"}, "relations": [{"confidence": "high", "evidence_ids": ["sfh1-ev-21-qiaoyi-011-liu-annotation-002"], "relation": "same_person", "target_hint": "仲堪"}, {"confidence": "high", "evidence_ids": ["sfh1-ev-21-qiaoyi-011-main"], "relation": "related_person", "target_hint": "顧長康"}], "semantic_kind": "historical_person", "supporting_evidence_ids": ["sfh1-ev-21-qiaoyi-011-liu-annotation-002", "sfh1-ev-21-qiaoyi-011-main"], "surface": "殷荆州"}`
- Historical correctness: pending external review
- Reviewer: [ ] correct  [ ] identity/canonicalization  [ ] semantic kind  [ ] role  [ ] discourse  [ ] wrong person  [ ] abstain  [ ] insufficient evidence
- Expected referent:
- Notes:

## sfh2-a0r-l-challenge-cddad0e22815a9ca438e
- Story: `21-qiaoyi-011`
- Mention: `sfh1-mention-70e56661cb36fdfacd1b68f6` / `明府`
- 正文: 顧長康好寫起人形欲圖殷荆州殷
曰我形惡不煩耳顧曰明府正為眼爾但明
㸃童子飛白拂其上使如輕雲之蔽日
- 刘注/证据: (之圖寫特妙/續晉陽秋曰愷) | (目故也/仲堪眇) | (作月/日一)
- Pass 1 valid: `True` record=`{"abstain": false, "attribute_type": "", "attribute_value": "", "bearer_hint": "", "confidence": "high", "discourse": {"addressee_hint": "殷仲堪", "antecedent_hint": "殷荆州", "self_reference_hint": "", "speaker_hint": "顧長康"}, "explanation": "明府 is an honorific title used to address a prefect/governor in the Eastern Jin period. In context, 顧長康 (Gu Kaizhi) addresses 殷仲堪 (Yin Zhongkan), who is referred to earlier in the text as 殷荆州 (Yin, Governor of Jingzhou). The Liu Xiaobiao annotation confirms 仲堪 as the person referred to. The speaker is 顧長康 addressing 殷仲堪 directly.", "mention_id": "sfh1-mention-70e56661cb36fdfacd1b68f6", "occurrence_role": "addressee_reference", "reference_type": "honorific", "referent": {"canonical_hint": "殷仲堪", "confidence": "high", "surface_form": "殷仲堪"}, "relations": [{"confidence": "high", "evidence_ids": ["sfh1-ev-21-qiaoyi-011-main"], "relation": "same_person", "target_hint": "殷荆州"}, {"confidence": "high", "evidence_ids": ["sfh1-ev-21-qiaoyi-011-liu-annotation-002"], "relation": "same_person", "target_hint": "仲堪"}], "semantic_kind": "historical_person", "supporting_evidence_ids": ["sfh1-ev-21-qiaoyi-011-liu-annotation-002", "sfh1-ev-21-qiaoyi-011-main"], "surface": "明府"}`
- Python flags: `[{"challenged_fields": ["relations", "referent.canonical_hint"], "evidence_ids": ["sfh1-ev-21-qiaoyi-011-liu-annotation-002", "sfh1-ev-21-qiaoyi-011-main"], "flag_type": "multi_candidate_ambiguity", "formal_reason": "the record supplies more than one structured relation target", "involved": ["relations"], "severity": "review"}]`
- Pass 2: `confirm` patch_ops=`[]`
- Pass 3: `` patch_ops=`[]`
- Final: `{"abstain": false, "attribute_type": "", "attribute_value": "", "bearer_hint": "", "confidence": "high", "discourse": {"addressee_hint": "殷仲堪", "antecedent_hint": "殷荆州", "self_reference_hint": "", "speaker_hint": "顧長康"}, "explanation": "明府 is an honorific title used to address a prefect/governor in the Eastern Jin period. In context, 顧長康 (Gu Kaizhi) addresses 殷仲堪 (Yin Zhongkan), who is referred to earlier in the text as 殷荆州 (Yin, Governor of Jingzhou). The Liu Xiaobiao annotation confirms 仲堪 as the person referred to. The speaker is 顧長康 addressing 殷仲堪 directly.", "mention_id": "sfh1-mention-70e56661cb36fdfacd1b68f6", "occurrence_role": "addressee_reference", "reference_type": "honorific", "referent": {"canonical_hint": "殷仲堪", "confidence": "high", "surface_form": "殷仲堪"}, "relations": [{"confidence": "high", "evidence_ids": ["sfh1-ev-21-qiaoyi-011-main"], "relation": "same_person", "target_hint": "殷荆州"}, {"confidence": "high", "evidence_ids": ["sfh1-ev-21-qiaoyi-011-liu-annotation-002"], "relation": "same_person", "target_hint": "仲堪"}], "semantic_kind": "historical_person", "supporting_evidence_ids": ["sfh1-ev-21-qiaoyi-011-liu-annotation-002", "sfh1-ev-21-qiaoyi-011-main"], "surface": "明府"}`
- Historical correctness: pending external review
- Reviewer: [ ] correct  [ ] identity/canonicalization  [ ] semantic kind  [ ] role  [ ] discourse  [ ] wrong person  [ ] abstain  [ ] insufficient evidence
- Expected referent:
- Notes:

## sfh2-a0r-l-challenge-f245371d8f0cdf9c8773
- Story: `21-qiaoyi-011`
- Mention: `sfh1-mention-7bf42600cd19ef3230d8b8fb` / `顧`
- 正文: 顧長康好寫起人形欲圖殷荆州殷
曰我形惡不煩耳顧曰明府正為眼爾但明
㸃童子飛白拂其上使如輕雲之蔽日
- 刘注/证据: (之圖寫特妙/續晉陽秋曰愷) | (目故也/仲堪眇) | (作月/日一)
- Pass 1 valid: `True` record=`{"abstain": false, "attribute_type": "", "attribute_value": "", "bearer_hint": "", "confidence": "high", "discourse": {"addressee_hint": "", "antecedent_hint": "顧長康", "self_reference_hint": "", "speaker_hint": ""}, "explanation": "The target 顧 is the surname reference at the start of the main text, referring to 顧長康 (顧愷之), the famous painter. The full name 顧長康 appears immediately at the same position (source_start 0), and the Liu annotation glosses 愷 (愷之). The surname 顧 is used as a shorthand for the same person.", "mention_id": "sfh1-mention-7bf42600cd19ef3230d8b8fb", "occurrence_role": "scene_participant", "reference_type": "surname_reference", "referent": {"canonical_hint": "顧愷之", "confidence": "high", "surface_form": "顧愷之"}, "relations": [{"confidence": "high", "evidence_ids": ["sfh1-ev-21-qiaoyi-011-main"], "relation": "same_person", "target_hint": "顧長康"}, {"confidence": "high", "evidence_ids": ["sfh1-ev-21-qiaoyi-011-liu-annotation-001"], "relation": "same_person", "target_hint": "愷"}], "semantic_kind": "historical_person", "supporting_evidence_ids": ["sfh1-ev-21-qiaoyi-011-liu-annotation-001", "sfh1-ev-21-qiaoyi-011-main"], "surface": "顧"}`
- Python flags: `[{"challenged_fields": ["relations", "referent.canonical_hint"], "evidence_ids": ["sfh1-ev-21-qiaoyi-011-liu-annotation-001", "sfh1-ev-21-qiaoyi-011-main"], "flag_type": "multi_candidate_ambiguity", "formal_reason": "the record supplies more than one structured relation target", "involved": ["relations"], "severity": "review"}]`
- Pass 2: `confirm` patch_ops=`[]`
- Pass 3: `` patch_ops=`[]`
- Final: `{"abstain": false, "attribute_type": "", "attribute_value": "", "bearer_hint": "", "confidence": "high", "discourse": {"addressee_hint": "", "antecedent_hint": "顧長康", "self_reference_hint": "", "speaker_hint": ""}, "explanation": "The target 顧 is the surname reference at the start of the main text, referring to 顧長康 (顧愷之), the famous painter. The full name 顧長康 appears immediately at the same position (source_start 0), and the Liu annotation glosses 愷 (愷之). The surname 顧 is used as a shorthand for the same person.", "mention_id": "sfh1-mention-7bf42600cd19ef3230d8b8fb", "occurrence_role": "scene_participant", "reference_type": "surname_reference", "referent": {"canonical_hint": "顧愷之", "confidence": "high", "surface_form": "顧愷之"}, "relations": [{"confidence": "high", "evidence_ids": ["sfh1-ev-21-qiaoyi-011-main"], "relation": "same_person", "target_hint": "顧長康"}, {"confidence": "high", "evidence_ids": ["sfh1-ev-21-qiaoyi-011-liu-annotation-001"], "relation": "same_person", "target_hint": "愷"}], "semantic_kind": "historical_person", "supporting_evidence_ids": ["sfh1-ev-21-qiaoyi-011-liu-annotation-001", "sfh1-ev-21-qiaoyi-011-main"], "surface": "顧"}`
- Historical correctness: pending external review
- Reviewer: [ ] correct  [ ] identity/canonicalization  [ ] semantic kind  [ ] role  [ ] discourse  [ ] wrong person  [ ] abstain  [ ] insufficient evidence
- Expected referent:
- Notes:

## sfh2-a0r-l-challenge-291f5eb01eb17f80c68b
- Story: `21-qiaoyi-011`
- Mention: `sfh1-mention-aea4db203ae94538a025b6cb` / `我`
- 正文: 顧長康好寫起人形欲圖殷荆州殷
曰我形惡不煩耳顧曰明府正為眼爾但明
㸃童子飛白拂其上使如輕雲之蔽日
- 刘注/证据: (之圖寫特妙/續晉陽秋曰愷) | (目故也/仲堪眇) | (作月/日一)
- Pass 1 valid: `True` record=`{"abstain": false, "attribute_type": "", "attribute_value": "", "bearer_hint": "", "confidence": "high", "discourse": {"addressee_hint": "顧長康", "antecedent_hint": "殷荆州", "self_reference_hint": "我", "speaker_hint": "殷仲堪"}, "explanation": "The pronoun 我 is spoken by 殷仲堪 (referred to as 殷荆州 in the main text). He says '我形惡' (my appearance is ugly), responding to 顧長康's request to paint him. The Liu annotation confirms 仲堪 (殷仲堪) is the person referred to by 殷荆州.", "mention_id": "sfh1-mention-aea4db203ae94538a025b6cb", "occurrence_role": "scene_participant", "reference_type": "pronoun_reference", "referent": {"canonical_hint": "殷仲堪", "confidence": "high", "surface_form": "殷仲堪"}, "relations": [{"confidence": "high", "evidence_ids": ["sfh1-ev-21-qiaoyi-011-main"], "relation": "same_person", "target_hint": "殷荆州"}, {"confidence": "high", "evidence_ids": ["sfh1-ev-21-qiaoyi-011-liu-annotation-002"], "relation": "same_person", "target_hint": "仲堪"}], "semantic_kind": "historical_person", "supporting_evidence_ids": ["sfh1-ev-21-qiaoyi-011-liu-annotation-002", "sfh1-ev-21-qiaoyi-011-main"], "surface": "我"}`
- Python flags: `[{"challenged_fields": ["relations", "referent.canonical_hint"], "evidence_ids": ["sfh1-ev-21-qiaoyi-011-liu-annotation-002", "sfh1-ev-21-qiaoyi-011-main"], "flag_type": "multi_candidate_ambiguity", "formal_reason": "the record supplies more than one structured relation target", "involved": ["relations"], "severity": "review"}]`
- Pass 2: `confirm` patch_ops=`[]`
- Pass 3: `` patch_ops=`[]`
- Final: `{"abstain": false, "attribute_type": "", "attribute_value": "", "bearer_hint": "", "confidence": "high", "discourse": {"addressee_hint": "顧長康", "antecedent_hint": "殷荆州", "self_reference_hint": "我", "speaker_hint": "殷仲堪"}, "explanation": "The pronoun 我 is spoken by 殷仲堪 (referred to as 殷荆州 in the main text). He says '我形惡' (my appearance is ugly), responding to 顧長康's request to paint him. The Liu annotation confirms 仲堪 (殷仲堪) is the person referred to by 殷荆州.", "mention_id": "sfh1-mention-aea4db203ae94538a025b6cb", "occurrence_role": "scene_participant", "reference_type": "pronoun_reference", "referent": {"canonical_hint": "殷仲堪", "confidence": "high", "surface_form": "殷仲堪"}, "relations": [{"confidence": "high", "evidence_ids": ["sfh1-ev-21-qiaoyi-011-main"], "relation": "same_person", "target_hint": "殷荆州"}, {"confidence": "high", "evidence_ids": ["sfh1-ev-21-qiaoyi-011-liu-annotation-002"], "relation": "same_person", "target_hint": "仲堪"}], "semantic_kind": "historical_person", "supporting_evidence_ids": ["sfh1-ev-21-qiaoyi-011-liu-annotation-002", "sfh1-ev-21-qiaoyi-011-main"], "surface": "我"}`
- Historical correctness: pending external review
- Reviewer: [ ] correct  [ ] identity/canonicalization  [ ] semantic kind  [ ] role  [ ] discourse  [ ] wrong person  [ ] abstain  [ ] insufficient evidence
- Expected referent:
- Notes:

## sfh2-a0r-l-challenge-510dea782abc9e9b618f
- Story: `25-paidiao-015`
- Mention: `sfh1-mention-19b9115e7b9a534351ffd25e` / `周侯`
- 正文: 謝幼輿謂周侯曰卿類社樹逺望之峨峨拂青天就
而視之其根則羣狐所託下聚溷而已荅曰
枝條拂青天不以爲高羣狐亂其下不以爲濁聚溷
之穢卿之所保何足自稱
- 刘注/证据: (媟瀆故/謂顗好)
- Pass 1 valid: `True` record=`{"abstain": false, "attribute_type": "", "attribute_value": "", "bearer_hint": "", "confidence": "high", "discourse": {"addressee_hint": "周侯", "antecedent_hint": "", "self_reference_hint": "", "speaker_hint": "謝幼輿"}, "explanation": "周侯 is an office title referring to 周顗 (Zhou Yi), who was enfeoffed as a marquis (侯). The Liu Xiaobiao annotation explicitly glosses 顗 as the person referred to, confirming the referent. 謝幼輿 addresses 周侯 directly in the dialogue.", "mention_id": "sfh1-mention-19b9115e7b9a534351ffd25e", "occurrence_role": "scene_participant", "reference_type": "office_title", "referent": {"canonical_hint": "周顗", "confidence": "high", "surface_form": "周顗"}, "relations": [{"confidence": "high", "evidence_ids": ["sfh1-ev-25-paidiao-015-liu-annotation-001"], "relation": "same_person", "target_hint": "顗"}], "semantic_kind": "historical_person", "supporting_evidence_ids": ["sfh1-ev-25-paidiao-015-liu-annotation-001", "sfh1-ev-25-paidiao-015-main"], "surface": "周侯"}`
- Python flags: `[]`
- Pass 2: `not_run` patch_ops=`[]`
- Pass 3: `` patch_ops=`[]`
- Final: `{"abstain": false, "attribute_type": "", "attribute_value": "", "bearer_hint": "", "confidence": "high", "discourse": {"addressee_hint": "周侯", "antecedent_hint": "", "self_reference_hint": "", "speaker_hint": "謝幼輿"}, "explanation": "周侯 is an office title referring to 周顗 (Zhou Yi), who was enfeoffed as a marquis (侯). The Liu Xiaobiao annotation explicitly glosses 顗 as the person referred to, confirming the referent. 謝幼輿 addresses 周侯 directly in the dialogue.", "mention_id": "sfh1-mention-19b9115e7b9a534351ffd25e", "occurrence_role": "scene_participant", "reference_type": "office_title", "referent": {"canonical_hint": "周顗", "confidence": "high", "surface_form": "周顗"}, "relations": [{"confidence": "high", "evidence_ids": ["sfh1-ev-25-paidiao-015-liu-annotation-001"], "relation": "same_person", "target_hint": "顗"}], "semantic_kind": "historical_person", "supporting_evidence_ids": ["sfh1-ev-25-paidiao-015-liu-annotation-001", "sfh1-ev-25-paidiao-015-main"], "surface": "周侯"}`
- Historical correctness: pending external review
- Reviewer: [ ] correct  [ ] identity/canonicalization  [ ] semantic kind  [ ] role  [ ] discourse  [ ] wrong person  [ ] abstain  [ ] insufficient evidence
- Expected referent:
- Notes:

## sfh2-a0r-l-challenge-da872c4c726a2d9b3e85
- Story: `25-paidiao-015`
- Mention: `sfh1-mention-275057994b778ebdb11e909c` / `卿`
- 正文: 謝幼輿謂周侯曰卿類社樹逺望之峨峨拂青天就
而視之其根則羣狐所託下聚溷而已荅曰
枝條拂青天不以爲高羣狐亂其下不以爲濁聚溷
之穢卿之所保何足自稱
- 刘注/证据: (媟瀆故/謂顗好)
- Pass 1 valid: `True` record=`{"abstain": false, "attribute_type": "", "attribute_value": "", "bearer_hint": "", "confidence": "high", "discourse": {"addressee_hint": "周侯", "antecedent_hint": "周侯", "self_reference_hint": "", "speaker_hint": "謝幼輿"}, "explanation": "謝幼輿 speaks to 周侯, addressing him with the second-person pronoun 卿. The Liu annotation identifies 顗 (周顗) as the referent of 周侯, confirming that 卿 refers to 周顗.", "mention_id": "sfh1-mention-275057994b778ebdb11e909c", "occurrence_role": "addressee_reference", "reference_type": "pronoun_reference", "referent": {"canonical_hint": "周顗", "confidence": "high", "surface_form": "周顗"}, "relations": [{"confidence": "high", "evidence_ids": ["sfh1-ev-25-paidiao-015-main"], "relation": "same_person", "target_hint": "周侯"}, {"confidence": "high", "evidence_ids": ["sfh1-ev-25-paidiao-015-liu-annotation-001"], "relation": "same_person", "target_hint": "顗"}], "semantic_kind": "historical_person", "supporting_evidence_ids": ["sfh1-ev-25-paidiao-015-liu-annotation-001", "sfh1-ev-25-paidiao-015-main"], "surface": "卿"}`
- Python flags: `[{"challenged_fields": ["relations", "referent.canonical_hint"], "evidence_ids": ["sfh1-ev-25-paidiao-015-liu-annotation-001", "sfh1-ev-25-paidiao-015-main"], "flag_type": "multi_candidate_ambiguity", "formal_reason": "the record supplies more than one structured relation target", "involved": ["relations"], "severity": "review"}]`
- Pass 2: `confirm` patch_ops=`[]`
- Pass 3: `` patch_ops=`[]`
- Final: `{"abstain": false, "attribute_type": "", "attribute_value": "", "bearer_hint": "", "confidence": "high", "discourse": {"addressee_hint": "周侯", "antecedent_hint": "周侯", "self_reference_hint": "", "speaker_hint": "謝幼輿"}, "explanation": "謝幼輿 speaks to 周侯, addressing him with the second-person pronoun 卿. The Liu annotation identifies 顗 (周顗) as the referent of 周侯, confirming that 卿 refers to 周顗.", "mention_id": "sfh1-mention-275057994b778ebdb11e909c", "occurrence_role": "addressee_reference", "reference_type": "pronoun_reference", "referent": {"canonical_hint": "周顗", "confidence": "high", "surface_form": "周顗"}, "relations": [{"confidence": "high", "evidence_ids": ["sfh1-ev-25-paidiao-015-main"], "relation": "same_person", "target_hint": "周侯"}, {"confidence": "high", "evidence_ids": ["sfh1-ev-25-paidiao-015-liu-annotation-001"], "relation": "same_person", "target_hint": "顗"}], "semantic_kind": "historical_person", "supporting_evidence_ids": ["sfh1-ev-25-paidiao-015-liu-annotation-001", "sfh1-ev-25-paidiao-015-main"], "surface": "卿"}`
- Historical correctness: pending external review
- Reviewer: [ ] correct  [ ] identity/canonicalization  [ ] semantic kind  [ ] role  [ ] discourse  [ ] wrong person  [ ] abstain  [ ] insufficient evidence
- Expected referent:
- Notes:

## sfh2-a0r-l-challenge-d47e242dae08241905e8
- Story: `25-paidiao-015`
- Mention: `sfh1-mention-3d2dca8e9199a9e979811441` / `謝幼輿`
- 正文: 謝幼輿謂周侯曰卿類社樹逺望之峨峨拂青天就
而視之其根則羣狐所託下聚溷而已荅曰
枝條拂青天不以爲高羣狐亂其下不以爲濁聚溷
之穢卿之所保何足自稱
- 刘注/证据: (媟瀆故/謂顗好)
- Pass 1 valid: `True` record=`{"abstain": false, "attribute_type": "", "attribute_value": "", "bearer_hint": "", "confidence": "high", "discourse": {"addressee_hint": "周侯", "antecedent_hint": "", "self_reference_hint": "", "speaker_hint": "謝幼輿"}, "explanation": "謝幼輿 is the speaker in this passage, addressing 周侯. The Liu annotation glosses 顗 (referring to 周顗, the 周侯) as the target of 謝幼輿's remark. 謝幼輿 is the courtesy name of 謝鯤, a well-known figure in the Shishuo xinyu. The mention is a full name (surname + courtesy name) used as the speaker in the scene.", "mention_id": "sfh1-mention-3d2dca8e9199a9e979811441", "occurrence_role": "scene_participant", "reference_type": "full_name", "referent": {"canonical_hint": "謝鯤", "confidence": "high", "surface_form": "謝幼輿"}, "relations": [{"confidence": "high", "evidence_ids": ["sfh1-ev-25-paidiao-015-main"], "relation": "related_person", "target_hint": "周侯"}], "semantic_kind": "historical_person", "supporting_evidence_ids": ["sfh1-ev-25-paidiao-015-liu-annotation-001", "sfh1-ev-25-paidiao-015-main"], "surface": "謝幼輿"}`
- Python flags: `[]`
- Pass 2: `not_run` patch_ops=`[]`
- Pass 3: `` patch_ops=`[]`
- Final: `{"abstain": false, "attribute_type": "", "attribute_value": "", "bearer_hint": "", "confidence": "high", "discourse": {"addressee_hint": "周侯", "antecedent_hint": "", "self_reference_hint": "", "speaker_hint": "謝幼輿"}, "explanation": "謝幼輿 is the speaker in this passage, addressing 周侯. The Liu annotation glosses 顗 (referring to 周顗, the 周侯) as the target of 謝幼輿's remark. 謝幼輿 is the courtesy name of 謝鯤, a well-known figure in the Shishuo xinyu. The mention is a full name (surname + courtesy name) used as the speaker in the scene.", "mention_id": "sfh1-mention-3d2dca8e9199a9e979811441", "occurrence_role": "scene_participant", "reference_type": "full_name", "referent": {"canonical_hint": "謝鯤", "confidence": "high", "surface_form": "謝幼輿"}, "relations": [{"confidence": "high", "evidence_ids": ["sfh1-ev-25-paidiao-015-main"], "relation": "related_person", "target_hint": "周侯"}], "semantic_kind": "historical_person", "supporting_evidence_ids": ["sfh1-ev-25-paidiao-015-liu-annotation-001", "sfh1-ev-25-paidiao-015-main"], "surface": "謝幼輿"}`
- Historical correctness: pending external review
- Reviewer: [ ] correct  [ ] identity/canonicalization  [ ] semantic kind  [ ] role  [ ] discourse  [ ] wrong person  [ ] abstain  [ ] insufficient evidence
- Expected referent:
- Notes:

## sfh2-a0r-l-challenge-d3c8fa925020f0c2c62a
- Story: `25-paidiao-015`
- Mention: `sfh1-mention-8ba0099c01f2b05135478b23` / `顗`
- 正文: 謝幼輿謂周侯曰卿類社樹逺望之峨峨拂青天就
而視之其根則羣狐所託下聚溷而已荅曰
枝條拂青天不以爲高羣狐亂其下不以爲濁聚溷
之穢卿之所保何足自稱
- 刘注/证据: (媟瀆故/謂顗好)
- Pass 1 valid: `True` record=`{"abstain": false, "attribute_type": "", "attribute_value": "", "bearer_hint": "", "confidence": "high", "discourse": {"addressee_hint": "", "antecedent_hint": "周侯", "self_reference_hint": "", "speaker_hint": "劉孝標"}, "explanation": "The Liu Xiaobiao annotation glosses 顗 as referring to 周顗 (the person addressed as 周侯 in the main text). The annotation text '(媟瀆故/謂顗好)' explains that the preceding content is about 周顗's fondness for something, confirming 顗 is the personal name of 周顗 (Zhou Yi), the person referred to as 周侯 in the main text.", "mention_id": "sfh1-mention-8ba0099c01f2b05135478b23", "occurrence_role": "annotation_person", "reference_type": "personal_name", "referent": {"canonical_hint": "周顗", "confidence": "high", "surface_form": "周顗"}, "relations": [{"confidence": "high", "evidence_ids": ["sfh1-ev-25-paidiao-015-liu-annotation-001", "sfh1-ev-25-paidiao-015-main"], "relation": "same_person", "target_hint": "周侯"}], "semantic_kind": "historical_person", "supporting_evidence_ids": ["sfh1-ev-25-paidiao-015-liu-annotation-001", "sfh1-ev-25-paidiao-015-main"], "surface": "顗"}`
- Python flags: `[]`
- Pass 2: `not_run` patch_ops=`[]`
- Pass 3: `` patch_ops=`[]`
- Final: `{"abstain": false, "attribute_type": "", "attribute_value": "", "bearer_hint": "", "confidence": "high", "discourse": {"addressee_hint": "", "antecedent_hint": "周侯", "self_reference_hint": "", "speaker_hint": "劉孝標"}, "explanation": "The Liu Xiaobiao annotation glosses 顗 as referring to 周顗 (the person addressed as 周侯 in the main text). The annotation text '(媟瀆故/謂顗好)' explains that the preceding content is about 周顗's fondness for something, confirming 顗 is the personal name of 周顗 (Zhou Yi), the person referred to as 周侯 in the main text.", "mention_id": "sfh1-mention-8ba0099c01f2b05135478b23", "occurrence_role": "annotation_person", "reference_type": "personal_name", "referent": {"canonical_hint": "周顗", "confidence": "high", "surface_form": "周顗"}, "relations": [{"confidence": "high", "evidence_ids": ["sfh1-ev-25-paidiao-015-liu-annotation-001", "sfh1-ev-25-paidiao-015-main"], "relation": "same_person", "target_hint": "周侯"}], "semantic_kind": "historical_person", "supporting_evidence_ids": ["sfh1-ev-25-paidiao-015-liu-annotation-001", "sfh1-ev-25-paidiao-015-main"], "surface": "顗"}`
- Historical correctness: pending external review
- Reviewer: [ ] correct  [ ] identity/canonicalization  [ ] semantic kind  [ ] role  [ ] discourse  [ ] wrong person  [ ] abstain  [ ] insufficient evidence
- Expected referent:
- Notes:
