# R3A：显式人物关系发现候选

本报告是当前生产人物的关系发现审计，不是 Relation 生产写入。所有候选的 `review_status` 均为 `candidate`；同则共现、Scene 场景位置和 PersonStory 连接不会单独生成关系候选。

## 审计摘要

- 当前生产人物：**35**
- 已审阅 Relation：**7**（其中 direct **6**）
- 人物无序对审计：**595**
- 显式候选：**7**（Tier A 2 / B 3 / C 2）
- 已审阅关系再发现控制项：**7**
- 仅共现、未形成候选的组合（报告上限 30）：**30**
- Wave-1 中已有候选端点的人物：**5**；Wave-2：**0**
- 仅按已审阅 Relation 仍孤立的人物：**28**

## 候选关系

### 温嶠 × 庾亮

- Rank：1 · Tier A · Candidate ID：`r3-candidate-abe9424bc5d46f8b10fa`
- 建议类别：`social_intellectual`；范围：`long_term_social`
- 角色：温嶠（友人）— 庾亮（友人）
- 来源：23-rendan-026
- 发现依据：「温太真……與庾亮善」直接記載温嶠與庾亮的友善交往。
- 风险：single_source_only, alias_surface_requires_existing_resolution
- 证据（shishuo_main_text · evidence-p3b-wave-1-edc469e15ce4dac030dbfe58）：“温太真位未髙時屢與揚州淮中估客樗蒱與輙不 競嘗一過大輸物戲屈無因得反與庾亮善於舫中 大喚亮曰卿可贖我庾即送直然後得還經此數四”

### 王導 × 庾亮

- Rank：2 · Tier A · Candidate ID：`r3-candidate-4050b8666e90aca0eb44`
- 建议类别：`social_intellectual`；范围：`long_term_social`
- 角色：王導（友人）— 庾亮（友人）
- 来源：06-yaliang-013
- 发现依据：「本懷布衣之好」明示王公與元規的交誼；不是由同則共現推定。
- 风险：single_source_only
- 证据（shishuo_main_text · evidence-p3b-wave-1-f114427662a639c512fd86d1）：“有往來者云庾公有東下意或謂王公可潜稍嚴以 備不虞王公曰我與元規雖俱王臣本懐布衣之好 若其欲來吾角巾徑還烏衣 何所稍嚴”

### 王導 × 温嶠

- Rank：3 · Tier B · Candidate ID：`r3-candidate-edd1312c55b4aa1283f4`
- 建议类别：`service_institutional`；范围：`institutional_service`
- 角色：王導（朝廷同僚）— 温嶠（朝廷同僚）
- 来源：02-yanyu-036
- 发现依据：温嶠初渡江謁王丞相，記載二人對泣、深自陳結與厚相酬納；不只依同場出現。
- 风险：single_source_only, scene_and_institutional_scope_overlap
- 证据（shishuo_main_text · evidence-p3b-wave-1-3c064306bd13f1f31e074056）：“温嶠初爲劉琨使來過江于時江左營建始爾綱紀 未舉温新至深有諸慮旣詣王丞相陳主上幽越社 稷焚滅山陵夷毁之酷有黍離之痛温忠慨深烈言 與泗俱丞相亦與之對泣叙情旣畢便深自陳結丞 相亦厚相酬納旣出”

### 謝安 × 袁宏

- Rank：4 · Tier B · Candidate ID：`r3-candidate-e66f8bb10ffc3350284a`
- 建议类别：`social_intellectual`；范围：`long_term_social`
- 角色：謝安（賞識者）— 袁宏（被賞識者）
- 来源：02-yanyu-083
- 发现依据：劉注明言太傅謝安賞袁宏機捷辯速；這是來源記載的賞識，不以送別共現代替關係證據。
- 风险：single_source_only, reported_annotation
- 证据（shishuo_liu_annotation · evidence-sc1-02-yanyu-083-annotation-004）：“(郡乃祖之於冶亭時賢皆集安欲卒迫試之執手將/記室太傅謝安賞宏機捷辯速自吏部郎出為東陽)”

### 桓溫 × 袁宏

- Rank：5 · Tier B · Candidate ID：`r3-candidate-ebce58f2d02c1c137ec9`
- 建议类别：`service_institutional`；范围：`institutional_service`
- 角色：桓溫（任用者）— 袁宏（大司馬記室參軍）
- 来源：04-wenxue-097
- 发现依据：劉注在桓温語境下記袁宏後為大司馬記室參軍；職屬關係保留為候選，未推廣為永久人格評價。
- 风险：single_source_only, reported_annotation
- 证据（shishuo_liu_annotation · evidence-p3b-wave-1-1c294f971d7f94ecb6d1358b）：“(為東征賦悉稱過江諸名望時桓温在/續晉陽秋曰宏為大司馬記室叅軍後)”

### 蘇峻 × 庾亮

- Rank：6 · Tier C · Candidate ID：`r3-candidate-53b688ea4c8b5d624fac`
- 建议类别：`political_counterposition`；范围：`historical_political`
- 角色：蘇峻（叛軍首領）— 庾亮（征討與被攻者）
- 来源：05-fangzheng-036, 06-yaliang-023, 27-jiajue-008
- 发现依据：多則來源直接記載蘇峻之亂與庾亮的征戰、追捕或被害語境；候選只描述政治對立，不把一次場景衝突改寫成性格或私人仇怨。
- 风险：reported_annotation, political_scope_requires_review
- 证据（shishuo_main_text · evidence-p3b-wave-1-2acdb676ee4ffa7eed9e48cb）：“庾太尉與蘇峻戰敗率左右十餘人乗小船西奔 亂兵相剝 掠射誤中柂工應弦而倒舉船上咸失色分散亮不 動容徐曰此手那可使箸賊衆迺安”
- 证据（shishuo_main_text · evidence-p3b-wave-1-9e8d06f2417607578b8f8576）：“陶公自上流來赴蘇峻之難令誅庾公謂必戮庾可 以謝峻 庾 欲奔竄則不可欲㑹恐見執進退無計温公勸庾詣 陶曰卿但遥拜必無它我為卿保之庾從温言詣陶 至便拜陶自起止之曰庾元規何縁拜陶士衡畢又 降就下坐陶又自”
- 证据（shishuo_liu_annotation · evidence-p3b-wave-1-7d58f8b8a3bc7f627efc44c7）：“(勸峻誅亮遂與峻同反後以宛城降/術爲阜陵令逃亡無行庾亮徵蘇峻術)”

### 蘇峻 × 温嶠

- Rank：7 · Tier C · Candidate ID：`r3-candidate-396dcefe02b3110bf363`
- 建议类别：`political_counterposition`；范围：`historical_political`
- 角色：蘇峻（叛軍首領）— 温嶠（起兵衛帝者）
- 来源：02-yanyu-102, 06-yaliang-023, 14-rongzhi-023
- 发现依据：劉注明載温嶠及三吳欲起兵衛帝、蘇峻作逆及亂後處置；候選保留事件範圍，不推定私人關係。
- 风险：reported_annotation, event_bounded, political_scope_requires_review
- 证据（shishuo_liu_annotation · evidence-p3b-wave-1-9057aaf9b2a6e7700f2e059f）：“(起兵衛帝室亮不聽下制曰妄起兵者誅故峻得作/興書曰初庾亮欲徵蘇峻卞壼不許温嶠及三吳欲)”
- 证据（shishuo_liu_annotation · evidence-p3b-wave-1-8ca29f2f621170206c99ddbd）：“(門外王師敗績亮於陳㰎三弟奔温嶠/秋曰蘇峻作逆詔亮都督征討戰于建陽)”
- 证据（shishuo_liu_annotation · evidence-p3b-wave-1-08618cd2a0ad0dcf1c3185b9）：“(後都邑殘荒温嶠議徙都豫章以/晉陽秋曰蘇峻既誅大事克平之)”

## 已审阅关系再发现控制

- `relation-001`：王羲之 × 郗鑒 · 婚姻亲属
- `relation-gold-001`：王羲之 × 王導 · 從父與從子
- `relation-gold-002`：王羲之 × 王凝之 · 父與子
- `relation-gold-003`：王凝之 × 謝道韞 · 夫妻
- `relation-gold-004`：謝道韞 × 謝安 · 叔父與姪女
- `relation-gold-005`：王羲之 × 郗璿 · 夫妻
- `relation-gold-006`：郗鑒 × 郗璿 · 父女

## Scene / Relation 交叉审计

Scene 只解释本则人物为何在此相遇；只有来源独立明确写出长期、社会或制度关系，才进入上面的候选。

- `02-yanyu-035`：温嶠 × 劉琨 — 仅场景相遇，未生成 Relation 候选。
- `02-yanyu-069`：王羲之 × 劉惔 — 仅场景相遇，未生成 Relation 候选。
- `02-yanyu-079`：孫晷 × 韓伯 — 仅场景相遇，未生成 Relation 候选。
- `05-fangzheng-025`：庾亮 × 謝尚 — 仅场景相遇，未生成 Relation 候选。
- `05-fangzheng-025`：庾亮 × 鄧攸 — 仅场景相遇，未生成 Relation 候选。
- `05-fangzheng-025`：蘇峻 × 謝尚 — 仅场景相遇，未生成 Relation 候选。
- `05-fangzheng-025`：蘇峻 × 鄧攸 — 仅场景相遇，未生成 Relation 候选。
- `05-fangzheng-025`：謝尚 × 鄧攸 — 仅场景相遇，未生成 Relation 候选。
- `05-fangzheng-028`：王敦 × 何充 — 仅场景相遇，未生成 Relation 候选。
- `05-fangzheng-031`：王敦 × 周顗 — 仅场景相遇，未生成 Relation 候选。
- `05-fangzheng-032`：王敦 × 温嶠 — 仅场景相遇，未生成 Relation 候选。
- `05-fangzheng-055`：謝安 × 桓溫 — 仅场景相遇，未生成 Relation 候选。
- `06-yaliang-027`：謝安 × 桓溫 — 仅场景相遇，未生成 Relation 候选。
- `06-yaliang-029`：謝安 × 桓溫 — 仅场景相遇，未生成 Relation 候选。
- `08-shangyu-051`：王敦 × 謝鯤 — 仅场景相遇，未生成 Relation 候选。
- `08-shangyu-077`：王羲之 × 謝安 — 仅场景相遇，未生成 Relation 候选。
- `08-shangyu-077`：王羲之 × 劉惔 — 仅场景相遇，未生成 Relation 候选。
- `08-shangyu-077`：謝安 × 劉惔 — 仅场景相遇，未生成 Relation 候选。
- `09-pinzao-017`：庾亮 × 謝鯤 — 仅场景相遇，未生成 Relation 候选。
- `11-jiewu-005`：王導 × 王敦 — 仅场景相遇，未生成 Relation 候选。
- `11-jiewu-005`：王敦 × 温嶠 — 仅场景相遇，未生成 Relation 候选。
- `19-xianyuan-026`：王羲之 × 謝道韞 — 仅场景相遇，未生成 Relation 候选。
- `19-xianyuan-026`：王羲之 × 謝安 — 仅场景相遇，未生成 Relation 候选。
- `19-xianyuan-026`：王凝之 × 謝安 — 仅场景相遇，未生成 Relation 候选。
- `27-jiajue-008`：庾亮 × 陸機 — 仅场景相遇，未生成 Relation 候选。
- `27-jiajue-008`：温嶠 × 陸機 — 仅场景相遇，未生成 Relation 候选。
- `27-jiajue-008`：蘇峻 × 陸機 — 仅场景相遇，未生成 Relation 候选。

## 仅共现审计（不是关系）

- 劉惔 × 王濛：共享 3 则 Story（05-fangzheng-051, 05-fangzheng-055, 09-pinzao-030）。
- 王敦 × 温嶠：共享 3 则 Story（05-fangzheng-031, 05-fangzheng-032, 11-jiewu-005）。
- 王敦 × 謝鯤：共享 3 则 Story（08-shangyu-051, 09-pinzao-017, 10-guizhen-012）。
- 王濛 × 謝尚：共享 3 则 Story（04-wenxue-022, 07-shijian-018, 09-pinzao-036）。
- 王導 × 王敦：共享 2 则 Story（09-pinzao-006, 11-jiewu-005）。
- 桓溫 × 王敦：共享 2 则 Story（08-shangyu-079, 25-paidiao-060）。
- 庾亮 × 謝尚：共享 2 则 Story（04-wenxue-022, 05-fangzheng-025）。
- 庾亮 × 周顗：共享 2 则 Story（09-pinzao-022, 26-qingdi-002）。
- 庾亮 × 謝鯤：共享 2 则 Story（09-pinzao-017, 09-pinzao-022）。
- 庾亮 × 殷浩：共享 2 则 Story（03-zhengshi-022, 14-rongzhi-024）。
- 王敦 × 周顗：共享 2 则 Story（05-fangzheng-027, 05-fangzheng-031）。
- 温嶠 × 劉琨：共享 2 则 Story（02-yanyu-035, 02-yanyu-036）。

## 下一步

本产物只供 R3B 人工审阅使用。任何候选在没有单独审阅前，都不会出现在读者端 Relation card，也不会写入 `wp1-relations.json`。
