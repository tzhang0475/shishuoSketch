import type { PublicationState, SiteBundle } from "./types";
import generatedSiteBundle from "./generated/sc1-site.json";

type RuntimeStoryRecord = Record<string, unknown> & {
  id: string;
  publication_state: PublicationState;
};

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

function requireArray(value: unknown, key: string): unknown[] {
  if (!isRecord(value) || !Array.isArray(value[key])) {
    throw new Error(`静态数据缺少数组: ${key}`);
  }
  return value[key];
}

function isPublicationState(value: unknown): value is PublicationState {
  return value === "production_ready" || value === "preview_ready" || value === "blocked";
}

function isRuntimeStoryRecord(value: unknown): value is RuntimeStoryRecord {
  return isRecord(value) && typeof value.id === "string" && isPublicationState(value.publication_state);
}

function isReadingPair(value: unknown): value is { original: string; simplified: string } {
  return isRecord(value) && typeof value.original === "string" && typeof value.simplified === "string";
}

function validatePersonSketches(
  value: unknown,
  people: unknown[],
  mentions: unknown[],
  evidenceIds: Set<string>,
): void {
  if (!isRecord(value)) throw new Error("静态数据缺少 person_sketches");
  const peopleById = new Map<string, Record<string, unknown>>();
  for (const person of people) {
    if (isRecord(person) && typeof person.id === "string") peopleById.set(person.id, person);
  }
  const mentionIds = new Set(
    mentions
      .filter(isRecord)
      .filter((mention) => typeof mention.id === "string")
      .map((mention) => String(mention.id)),
  );
  const sketchIds = Object.keys(value);
  if (sketchIds.length !== peopleById.size || sketchIds.some((id) => !peopleById.has(id))) {
    throw new Error("person_sketches 必须覆盖且仅覆盖 canonical Person registry");
  }
  for (const [personId, sketch] of Object.entries(value)) {
    if (!isRecord(sketch) || sketch.person_id !== personId) {
      throw new Error(`Person Sketch ${personId} 的 person_id 不一致`);
    }
    if (sketch.scope_role !== "primary" && sketch.scope_role !== "supporting") {
      throw new Error(`Person Sketch ${personId} 的 scope_role 无效`);
    }
    if (sketch.review_status !== "candidate" && sketch.review_status !== "reviewed") {
      throw new Error(`Person Sketch ${personId} 的 review_status 无效`);
    }
    const person = peopleById.get(personId);
    const identity = sketch.identity;
    if (!person || !isRecord(identity) || !isReadingPair(identity.canonical_name)) {
      throw new Error(`Person Sketch ${personId} 的 identity 不完整`);
    }
    if (identity.canonical_name.original !== person.canonical_name) {
      throw new Error(`Person Sketch ${personId} 不得改写 canonical Person name`);
    }
    for (const key of ["courtesy_name", "clan", "brief_intro"]) {
      const field = identity[key];
      if (field !== null && !isReadingPair(field)) throw new Error(`Person Sketch ${personId} 的 ${key} 不完整`);
    }
    if (!Array.isArray(identity.identity_roles) || identity.identity_roles.some((item) => !isReadingPair(item))) {
      throw new Error(`Person Sketch ${personId} 的 identity_roles 无效`);
    }
    if (!Array.isArray(identity.evidence_ids) || identity.evidence_ids.length === 0 || identity.evidence_ids.some((id) => typeof id !== "string" || !evidenceIds.has(id))) {
      throw new Error(`Person Sketch ${personId} 的 identity Evidence 无效`);
    }
    if (!Array.isArray(sketch.profile_evidence_ids) || sketch.profile_evidence_ids.some((id) => typeof id !== "string" || !evidenceIds.has(id))) {
      throw new Error(`Person Sketch ${personId} 的 profile Evidence 无效`);
    }
    if (!Array.isArray(sketch.aliases)) throw new Error(`Person Sketch ${personId} 缺少 alias rows`);
    const aliasIds = new Set<string>();
    let previousOrder = -1;
    for (const alias of sketch.aliases) {
      if (!isRecord(alias) || typeof alias.alias_id !== "string" || aliasIds.has(alias.alias_id)) {
        throw new Error(`Person Sketch ${personId} 的 alias row 无效或重复`);
      }
      aliasIds.add(alias.alias_id);
      if (!isReadingPair(alias.surface) || !isReadingPair(alias.label) || !isReadingPair(alias.semantic_label)) {
        throw new Error(`Person Sketch ${personId} 的 alias display 不完整`);
      }
      if (alias.semantic_status !== "exact" && alias.semantic_status !== "contextual" && alias.semantic_status !== "ambiguous") {
        throw new Error(`Person Sketch ${personId} 的 alias semantic status 无效`);
      }
      if (typeof alias.display_order !== "number" || !Number.isInteger(alias.display_order) || alias.display_order <= previousOrder) {
        throw new Error(`Person Sketch ${personId} 的 alias order 不确定`);
      }
      previousOrder = alias.display_order;
      if (!Array.isArray(alias.mention_ids) || alias.mention_ids.some((id) => typeof id !== "string" || !mentionIds.has(id))) {
        throw new Error(`Person Sketch ${personId} 的 alias Mention 引用无效`);
      }
      if (!Array.isArray(alias.evidence_ids) || alias.evidence_ids.some((id) => typeof id !== "string" || !evidenceIds.has(id))) {
        throw new Error(`Person Sketch ${personId} 的 alias Evidence 引用无效`);
      }
      if (!isRecord(alias.observed_in_shishuo) || typeof alias.observed_in_shishuo.main_text !== "boolean" || typeof alias.observed_in_shishuo.liu_annotation !== "boolean") {
        throw new Error(`Person Sketch ${personId} 的 alias source layer 无效`);
      }
      if (!Array.isArray(alias.source_layers) || alias.source_layers.some((layer) => layer !== "main_text" && layer !== "liu_annotation")) {
        throw new Error(`Person Sketch ${personId} 的 alias source_layers 无效`);
      }
      if (typeof alias.occurrence_count !== "number" || !Number.isInteger(alias.occurrence_count) || alias.occurrence_count < 0) {
        throw new Error(`Person Sketch ${personId} 的 alias occurrence_count 无效`);
      }
    }
    const storyCounts = sketch.story_counts;
    if (!isRecord(storyCounts) || ["total", "main_text", "liu_annotation_only", "reader_ready"].some((key) => {
      const count = storyCounts[key];
      return typeof count !== "number" || !Number.isInteger(count) || count < 0;
    })) {
      throw new Error(`Person Sketch ${personId} 的 story_counts 无效`);
    }
    if (!Array.isArray(sketch.life_glimpse)) {
      throw new Error(`Person Sketch ${personId} 缺少 一瞥 数据`);
    }
    for (const [index, point] of sketch.life_glimpse.entries()) {
      if (!isRecord(point) || !isReadingPair(point.text) || !Array.isArray(point.evidence_ids) || point.evidence_ids.length === 0 || point.evidence_ids.some((id) => typeof id !== "string" || !evidenceIds.has(id))) {
        throw new Error(`Person Sketch ${personId} 的 一瞥 ${index} 无效`);
      }
      if (point.assertion_status !== "attested" && point.assertion_status !== "reported" && point.assertion_status !== "inferred" && point.assertion_status !== "unknown") {
        throw new Error(`Person Sketch ${personId} 的 一瞥 assertion_status 无效`);
      }
      if (point.review_status !== "candidate" && point.review_status !== "reviewed") {
        throw new Error(`Person Sketch ${personId} 的 一瞥 review_status 无效`);
      }
      if (!Array.isArray(point.story_ids) || point.story_ids.some((id) => typeof id !== "string")) {
        throw new Error(`Person Sketch ${personId} 的 一瞥 Story 引用无效`);
      }
    }
  }
}

function validateSceneContexts(
  value: unknown,
  stories: unknown[],
  people: unknown[],
  evidenceIds: Set<string>,
): void {
  if (!isRecord(value)) throw new Error("静态数据缺少 scene_contexts");
  const storyIds = new Set(
    stories.filter(isRecord).filter((story) => typeof story.id === "string").map((story) => String(story.id)),
  );
  const peopleIds = new Set(
    people.filter(isRecord).filter((person) => typeof person.id === "string").map((person) => String(person.id)),
  );
  const checkEvidence = (owner: string, ids: unknown): void => {
    if (!Array.isArray(ids) || ids.some((id) => typeof id !== "string" || !evidenceIds.has(id))) {
      throw new Error(`${owner} 的 Scene Evidence 引用无效`);
    }
  };
  const checkPair = (owner: string, valueToCheck: unknown): void => {
    if (valueToCheck !== null && !isReadingPair(valueToCheck)) throw new Error(`${owner} 的 Scene display 不完整`);
  };
  const checkClaim = (owner: string, claim: unknown): void => {
    if (!isRecord(claim)) throw new Error(`${owner} 的 Scene claim 不完整`);
    checkPair(`${owner}.text`, claim.text);
    checkEvidence(owner, claim.evidence_ids);
  };
  for (const [storyId, scene] of Object.entries(value)) {
    if (!storyIds.has(storyId) || !isRecord(scene) || scene.story_id !== storyId) {
      throw new Error(`Scene Context ${storyId} 的 Story 引用无效`);
    }
    if (scene.review_status !== "candidate" && scene.review_status !== "reviewed" && scene.review_status !== "rejected" && scene.review_status !== "todo") {
      throw new Error(`Scene Context ${storyId} 的 review_status 无效`);
    }
    checkEvidence(`Scene Context ${storyId}`, scene.evidence_ids);
    if (!isRecord(scene.date)) throw new Error(`Scene Context ${storyId} 缺少 date`);
    checkPair(`Scene Context ${storyId}.date.label`, scene.date.label);
    checkEvidence(`Scene Context ${storyId}.date`, scene.date.evidence_ids);
    if (!Array.isArray(scene.places) || !Array.isArray(scene.people_at_scene) || !Array.isArray(scene.unmaterialized_people) || !Array.isArray(scene.positional_context) || !Array.isArray(scene.event_background) || !isRecord(scene.narrative_layers)) {
      throw new Error(`Scene Context ${storyId} 的分层数据不完整`);
    }
    for (const key of ["scene_focus", "off_frame_context", "historical_ground", "resonance"]) {
      const claims = scene.narrative_layers[key];
      if (!Array.isArray(claims)) throw new Error(`Scene Context ${storyId} 的 ${key} 不完整`);
      for (const [index, claim] of claims.entries()) checkClaim(`Scene Context ${storyId}.${key} ${index}`, claim);
    }
    for (const [index, place] of scene.places.entries()) {
      if (!isRecord(place)) throw new Error(`Scene Context ${storyId} place ${index} 无效`);
      checkPair(`Scene Context ${storyId}.place`, place.name);
      checkEvidence(`Scene Context ${storyId}.place`, place.evidence_ids);
    }
    for (const [index, person] of scene.people_at_scene.entries()) {
      if (!isRecord(person) || typeof person.person_id !== "string" || !peopleIds.has(person.person_id)) {
        throw new Error(`Scene Context ${storyId} Person ${index} 无效`);
      }
      checkPair(`Scene Context ${storyId}.person.surface`, person.surface);
      checkPair(`Scene Context ${storyId}.person.scene_role_label`, person.scene_role_label);
      checkEvidence(`Scene Context ${storyId}.person`, person.evidence_ids);
      if (!isRecord(person.age)) throw new Error(`Scene Context ${storyId} Person age 不完整`);
      checkPair(`Scene Context ${storyId}.person.age.label`, person.age.label);
      checkEvidence(`Scene Context ${storyId}.person.age`, person.age.evidence_ids);
      if (person.status !== null) checkClaim(`Scene Context ${storyId}.person.status`, person.status);
    }
    for (const [index, person] of scene.unmaterialized_people.entries()) {
      if (!isRecord(person)) throw new Error(`Scene Context ${storyId} unmaterialized Person ${index} 无效`);
      checkPair(`Scene Context ${storyId}.unmaterialized.surface`, person.surface);
      checkPair(`Scene Context ${storyId}.unmaterialized.reason`, person.reason);
      checkEvidence(`Scene Context ${storyId}.unmaterialized`, person.evidence_ids);
    }
    for (const [index, position] of scene.positional_context.entries()) {
      if (!isRecord(position) || !Array.isArray(position.person_ids) || position.person_ids.some((id) => typeof id !== "string" || !peopleIds.has(id))) {
        throw new Error(`Scene Context ${storyId} positional context ${index} 无效`);
      }
      checkPair(`Scene Context ${storyId}.position.classification_label`, position.classification_label);
      checkClaim(`Scene Context ${storyId}.position`, position);
    }
    for (const [index, claim] of scene.event_background.entries()) checkClaim(`Scene Context ${storyId}.background ${index}`, claim);
    if (!Array.isArray(scene.notes) || scene.notes.some((note) => !isReadingPair(note))) {
      throw new Error(`Scene Context ${storyId} notes 无效`);
    }
  }
}

function validateReadingSegments(
  segments: unknown,
  expectedOriginal: string,
  expectedSimplified: string,
  layer: "main_text" | "liu_annotation",
  annotationId?: string,
  rulerMentionIds?: Set<string>,
): void {
  if (!Array.isArray(segments)) {
    throw new Error(`reading ${layer} 缺少 segments`);
  }
  let original = "";
  let simplified = "";
  for (const segment of segments) {
    if (!isRecord(segment) || (segment.type !== "text" && segment.type !== "person_mention" && segment.type !== "identity_mention" && segment.type !== "ruler_mention" && segment.type !== "annotation_marker")) {
      throw new Error(`reading ${layer} 存在无效 segment`);
    }
    const display = segment.display;
    if (!isRecord(display) || typeof display.original !== "string" || typeof display.simplified !== "string") {
      throw new Error(`reading ${layer} segment display 不完整`);
    }
    const displayRecord = display;
    if (segment.type === "person_mention") {
      if (typeof segment.mention_id !== "string" || typeof segment.person_id !== "string") {
        throw new Error(`reading ${layer} person segment 缺少 Mention/Person ID`);
      }
      if (layer === "main_text" && segment.annotation_id !== undefined) {
        throw new Error("main_text person segment 不得携带 annotation_id");
      }
      if (layer === "liu_annotation" && segment.annotation_id !== annotationId) {
        throw new Error(`annotation ${String(annotationId)} 的 person segment 层级不一致`);
      }
    }
    if (segment.type === "identity_mention") {
      if (typeof segment.mention_id !== "string" || segment.target_kind !== "identity_candidate" || (segment.resolution_status !== "resolved" && segment.resolution_status !== "candidate_for_review") || !Array.isArray(segment.candidate_names)) {
        throw new Error(`reading ${layer} identity segment 不完整`);
      }
      if (segment.canonical_name !== null && !isReadingPair(segment.canonical_name)) {
        throw new Error(`reading ${layer} identity segment canonical_name 不完整`);
      }
      if (layer === "main_text" && segment.annotation_id !== undefined) {
        throw new Error("main_text identity segment 不得携带 annotation_id");
      }
      if (layer === "liu_annotation" && segment.annotation_id !== annotationId) {
        throw new Error(`annotation ${String(annotationId)} 的 identity segment 层级不一致`);
      }
    }
    if (segment.type === "ruler_mention") {
      if (typeof segment.mention_id !== "string" || !rulerMentionIds?.has(segment.mention_id) || typeof segment.ruler_id !== "string" || typeof segment.era_card_id !== "string") {
        throw new Error(`reading ${layer} ruler segment 不完整`);
      }
      if (layer === "main_text" && segment.annotation_id !== undefined) {
        throw new Error("main_text ruler segment 不得携带 annotation_id");
      }
      if (layer === "liu_annotation" && segment.annotation_id !== annotationId) {
        throw new Error(`annotation ${String(annotationId)} 的 ruler segment 层级不一致`);
      }
    }
    if (segment.type === "annotation_marker") {
      if (layer !== "main_text" || typeof segment.annotation_id !== "string" || !isRecord(segment.label)) {
        throw new Error("annotation_marker 只能出现在主文本并且必须引用注释");
      }
      if (displayRecord.original !== "" || displayRecord.simplified !== "") {
        throw new Error("annotation_marker 不得改变正文重建字符");
      }
      if (typeof segment.label.original !== "string" || typeof segment.label.simplified !== "string") {
        throw new Error("annotation_marker label 不完整");
      }
    }
    original += display.original;
    simplified += display.simplified;
  }
  if (original !== expectedOriginal || simplified !== expectedSimplified) {
    throw new Error(`reading ${layer} segments 无法重建显示文本`);
  }
}

export function parseSiteBundle(value: unknown): SiteBundle {
  if (!isRecord(value) || value.schema !== 1 || typeof value.generated_from !== "string") {
    throw new Error("静态数据不是受支持的 frontend bundle");
  }
  const keys = ["stories", "people", "mentions", "relations", "eras", "evidence", "sources", "historical_events"];
  const arrays = Object.fromEntries(keys.map((key) => [key, requireArray(value, key)]));
  const ids = new Set<string>();
  for (const key of keys) {
    for (const item of arrays[key]) {
      if (!isRecord(item) || typeof item.id !== "string") {
        throw new Error(`${key} 中存在没有 id 的记录`);
      }
      if (ids.has(item.id)) {
        throw new Error(`静态数据存在重复 id: ${item.id}`);
      }
      ids.add(item.id);
    }
  }
  const storyIds = new Set(arrays.stories.map((item) => (item as Record<string, unknown>).id));
  const peopleIds = new Set(arrays.people.map((item) => (item as Record<string, unknown>).id));
  const evidenceIds = new Set<string>(
    arrays.evidence
      .map((item) => (item as Record<string, unknown>).id)
      .filter((id): id is string => typeof id === "string"),
  );
  if (!Array.isArray(value.ruler_identities) || !Array.isArray(value.era_cards) || !Array.isArray(value.ruler_mentions)) {
    throw new Error("静态数据缺少 E0 纪元投影数组");
  }
  const rulerIds = new Set<string>();
  for (const identity of value.ruler_identities) {
    if (!isRecord(identity) || typeof identity.ruler_id !== "string" || rulerIds.has(identity.ruler_id)) {
      throw new Error("E0 ruler identity ID 无效或重复");
    }
    rulerIds.add(identity.ruler_id);
    if (peopleIds.has(identity.ruler_id)) throw new Error(`E0 ruler ID 不得占用 Person ID: ${identity.ruler_id}`);
    if (!isReadingPair(identity.canonical_title) || !Array.isArray(identity.reign_period_ids) || !Array.isArray(identity.era_year_ids) || !Array.isArray(identity.evidence_ids)) {
      throw new Error(`E0 ruler identity ${identity.ruler_id} 结构不完整`);
    }
    if (identity.reign_start_year !== null && typeof identity.reign_start_year !== "number") throw new Error(`E0 ruler ${identity.ruler_id} 起年无效`);
    if (identity.reign_end_year !== null && typeof identity.reign_end_year !== "number") throw new Error(`E0 ruler ${identity.ruler_id} 终年无效`);
    if (typeof identity.reign_start_year === "number" && typeof identity.reign_end_year === "number" && identity.reign_start_year > identity.reign_end_year) throw new Error(`E0 ruler ${identity.ruler_id} 年界倒置`);
  }
  const eventIds = new Set(arrays.historical_events.map((item) => (item as Record<string, unknown>).id));
  for (const event of arrays.historical_events) {
    if (!isRecord(event) || typeof event.id !== "string") throw new Error("E0 HistoricalEvent projection 无效");
    if (!isReadingPair(event.canonical_name) || !Array.isArray(event.source_evidence_ids) || event.source_evidence_ids.some((id) => typeof id !== "string" || !evidenceIds.has(id))) {
      throw new Error(`E0 HistoricalEvent ${event.id} 依据无效`);
    }
    if (typeof event.start_year_ce === "number" && typeof event.end_year_ce === "number" && event.start_year_ce > event.end_year_ce) throw new Error(`E0 HistoricalEvent ${event.id} 年界倒置`);
  }
  const eraCardIds = new Set<string>();
  for (const card of value.era_cards) {
    if (!isRecord(card) || typeof card.era_card_id !== "string" || eraCardIds.has(card.era_card_id) || typeof card.ruler_id !== "string" || !rulerIds.has(card.ruler_id)) {
      throw new Error("E0 Era Card ID 或 ruler 引用无效/重复");
    }
    eraCardIds.add(card.era_card_id);
    if (!isReadingPair(card.title) || !isReadingPair(card.reign_label) || !isRecord(card.era_context) || !isReadingPair(card.era_context.text)) {
      throw new Error(`E0 Era Card ${card.era_card_id} display 不完整`);
    }
    if (typeof card.reign_start_year === "number" && typeof card.reign_end_year === "number" && card.reign_start_year > card.reign_end_year) throw new Error(`E0 Era Card ${card.era_card_id} 年界倒置`);
    if (!Array.isArray(card.historical_event_ids) || card.historical_event_ids.some((id) => typeof id !== "string" || !eventIds.has(id))) throw new Error(`E0 Era Card ${card.era_card_id} HistoricalEvent 引用无效`);
  }
  const rulerMentionIds = new Set<string>();
  const rulerMentionById = new Map<string, Record<string, unknown>>();
  for (const mention of value.ruler_mentions) {
    if (!isRecord(mention) || typeof mention.mention_id !== "string" || rulerMentionIds.has(mention.mention_id) || typeof mention.story_id !== "string" || !storyIds.has(mention.story_id) || typeof mention.ruler_id !== "string" || !rulerIds.has(mention.ruler_id) || typeof mention.era_card_id !== "string" || !eraCardIds.has(mention.era_card_id)) {
      throw new Error("E0 ruler Mention 无效或重复");
    }
    rulerMentionIds.add(mention.mention_id);
    rulerMentionById.set(mention.mention_id, mention);
    if (!Array.isArray(mention.evidence_ids) || mention.evidence_ids.some((id) => typeof id !== "string" || !evidenceIds.has(id))) throw new Error(`E0 ruler Mention ${mention.mention_id} 依据无效`);
  }
  for (const story of arrays.stories) {
    if (!isRecord(story) || !isRecord(story.reading)) {
      throw new Error("Story 缺少 reading layer");
    }
    if (!isRuntimeStoryRecord(story)) {
      throw new Error(`Story ${String(story.id)} 的 publication_state 无效`);
    }
    if (story.temporal_anchor_id !== undefined && typeof story.temporal_anchor_id !== "string") {
      throw new Error(`Story ${String(story.id)} 的 temporal_anchor_id 无效`);
    }
    if (story.temporal_orientation !== undefined && !isReadingPair(story.temporal_orientation)) {
      throw new Error(`Story ${String(story.id)} 的 temporal_orientation 无效`);
    }
    const reading = story.reading;
    if (reading.entry_id !== story.id || typeof reading.status !== "string") {
      throw new Error(`Story ${String(story.id)} 的 reading layer 标识不一致`);
    }
    const publicationState = story.publication_state;
    if (publicationState === "production_ready" && reading.status !== "reviewed") {
      throw new Error(`Story ${String(story.id)} 的 production reading 必须是 reviewed`);
    }
    if (publicationState === "preview_ready" && reading.status === "disputed") {
      throw new Error(`Story ${String(story.id)} 的 preview reading 不能是 disputed`);
    }
    if (!isRecord(reading.main_text) || typeof reading.main_text.original !== "string" || typeof reading.main_text.simplified !== "string") {
      throw new Error(`Story ${String(story.id)} 的 reading.main_text 不完整`);
    }
    if (/[\r\n]/u.test(reading.main_text.original)) {
      throw new Error(`Story ${String(story.id)} 的 reader projection 包含物理 source line break`);
    }
    validateReadingSegments(
      reading.main_text.segments,
      reading.main_text.original,
      reading.main_text.simplified,
      "main_text",
      undefined,
      rulerMentionIds,
    );
    if (!Array.isArray(reading.annotations) || reading.annotations.some((item) => {
      return !isRecord(item) || typeof item.id !== "string" || typeof item.original !== "string" || typeof item.simplified !== "string" || !Array.isArray(item.segments) || !isRecord(item.insertion);
    })) {
      throw new Error(`Story ${String(story.id)} 的 reading.annotations 不完整`);
    }
    if (!Array.isArray(story.annotations) || story.annotations.length !== reading.annotations.length) {
      throw new Error(`Story ${String(story.id)} 的 canonical/reading annotation 数量不一致`);
    }
    for (const [index, sourceAnnotation] of story.annotations.entries()) {
      const readingAnnotation = reading.annotations[index];
      if (!isRecord(sourceAnnotation) || !readingAnnotation || sourceAnnotation.id !== readingAnnotation.id) {
        throw new Error(`Story ${String(story.id)} 的 annotation 顺序或 ID 不一致`);
      }
    }
    for (const annotation of reading.annotations) {
      if (!isRecord(annotation)) continue;
      if (/[\r\n]/u.test(String(annotation.original))) {
        throw new Error(`Story ${String(story.id)} 的 Liu annotation reader projection 包含物理 source line break: ${String(annotation.id)}`);
      }
      const insertion = annotation.insertion;
      if (!isRecord(insertion)) {
        throw new Error(`Story ${String(story.id)} 的 annotation insertion 不完整`);
      }
      if (
        (insertion.status !== "safe" && insertion.status !== "unavailable") ||
        (insertion.status === "safe" && typeof insertion.main_text_offset !== "number")
      ) {
        throw new Error(`Story ${String(story.id)} 的 annotation insertion 不完整`);
      }
      validateReadingSegments(
        annotation.segments,
        String(annotation.original),
        String(annotation.simplified),
        "liu_annotation",
        String(annotation.id),
        rulerMentionIds,
      );
    }
    const projection = reading.mention_projection;
    if (!isRecord(projection) || !Array.isArray(projection.suppressed)) {
      throw new Error(`Story ${String(story.id)} 的 mention projection 不完整`);
    }
    if (!isRecord(reading.labels) || !isRecord(reading.person_display) || !isRecord(reading.mention_display) || !isRecord(reading.source_display)) {
      throw new Error(`Story ${String(story.id)} 的 reading display layer 不完整`);
    }
    if (!isRecord(reading.relation_display) || !isRecord(reading.evidence_display)) {
      throw new Error(`Story ${String(story.id)} 的 relation reading layer 不完整`);
    }
    const annotationIds = new Set(reading.annotations.map((annotation) => String(annotation.id)));
    const mainSegments = isRecord(reading.main_text) && Array.isArray(reading.main_text.segments)
      ? reading.main_text.segments
      : [];
    for (const segment of mainSegments) {
      if (isRecord(segment) && segment.type === "annotation_marker" && !annotationIds.has(String(segment.annotation_id))) {
        throw new Error(`Story ${String(story.id)} annotation_marker 引用了不存在的注释`);
      }
      if (isRecord(segment) && segment.type === "annotation_marker") {
        const annotation = reading.annotations.find((candidate) => candidate.id === segment.annotation_id);
        if (!annotation || !isRecord(annotation.insertion) || annotation.insertion.status !== "safe") {
          throw new Error(`Story ${String(story.id)} annotation_marker 没有安全的 insertion point`);
        }
      }
    }
    for (const annotation of reading.annotations) {
      for (const evidenceId of annotation.evidence_ids ?? []) {
        if (!evidenceIds.has(evidenceId) || !Array.isArray(story.evidence_ids) || !story.evidence_ids.includes(evidenceId)) {
          throw new Error(`Story ${String(story.id)} annotation Evidence 覆盖不完整: ${evidenceId}`);
        }
      }
    }
    const mentionDisplay = isRecord(reading.mention_display) ? reading.mention_display : {};
    for (const [mentionId, display] of Object.entries(mentionDisplay)) {
      if (!isRecord(display) || !isRecord(display.surface) || !isRecord(display.explanation)) {
        throw new Error(`Story ${String(story.id)} Mention display 不完整: ${mentionId}`);
      }
      if (typeof display.surface.original !== "string" || typeof display.surface.simplified !== "string" || typeof display.explanation.original !== "string" || typeof display.explanation.simplified !== "string") {
        throw new Error(`Story ${String(story.id)} Mention display 文本不完整: ${mentionId}`);
      }
    }
  }
  for (const mention of arrays.mentions) {
    if (!isRecord(mention) || typeof mention.story_id !== "string" || !storyIds.has(mention.story_id)) {
      throw new Error("Mention 引用了不存在的 Story");
    }
  }
  validatePersonSketches(value.person_sketches, arrays.people, arrays.mentions, evidenceIds);
  validateSceneContexts(value.scene_contexts, arrays.stories, arrays.people, evidenceIds);
  const mentionById = new Map(
    arrays.mentions
      .filter(isRecord)
      .filter((item) => typeof item.id === "string")
      .map((item) => [String(item.id), item]),
  );
  const relationIds = new Set(arrays.relations.map((item) => (item as Record<string, unknown>).id));
  for (const relation of arrays.relations) {
    if (!isRecord(relation)) throw new Error("Relation 记录格式无效");
    if (typeof relation.subject_id !== "string" || typeof relation.object_id !== "string") {
      throw new Error(`Relation ${String(relation.id)} 缺少人物端点`);
    }
    if (!peopleIds.has(relation.subject_id) || !peopleIds.has(relation.object_id)) {
      throw new Error(`Relation ${String(relation.id)} 引用了不存在的人物`);
    }
    if (!Array.isArray(relation.evidence_ids) || relation.evidence_ids.some((id) => typeof id !== "string" || !evidenceIds.has(id))) {
      throw new Error(`Relation ${String(relation.id)} 引用了不存在的依据`);
    }
    if (relation.relation_basis === "derived") {
      if (!Array.isArray(relation.derived_from_relation_ids) || relation.derived_from_relation_ids.length === 0) {
        throw new Error(`Relation ${String(relation.id)} 缺少推导来源`);
      }
      for (const sourceId of relation.derived_from_relation_ids) {
        if (typeof sourceId !== "string" || !relationIds.has(sourceId)) {
          throw new Error(`Relation ${String(relation.id)} 引用了不存在的推导关系`);
        }
      }
    }
  }
  for (const story of arrays.stories) {
    if (!isRecord(story) || !isRecord(story.reading) || typeof story.id !== "string") continue;
    const reading = story.reading;
    const placed = new Set<string>();
    const placedRuler = new Set<string>();
    const suppressed = new Set<string>();
    const inspectSegments = (segments: unknown, layer: "main_text" | "liu_annotation", annotationId?: string) => {
      if (!Array.isArray(segments)) return;
      for (const segment of segments) {
        if (isRecord(segment) && segment.type === "ruler_mention") {
          const rulerMentionId = segment.mention_id;
          const rulerMention = typeof rulerMentionId === "string" ? rulerMentionById.get(rulerMentionId) : undefined;
          if (typeof rulerMentionId === "string" && placedRuler.has(rulerMentionId)) {
            throw new Error(`Story ${story.id} 重复渲染 ruler Mention: ${rulerMentionId}`);
          }
          if (!rulerMention || rulerMention.story_id !== story.id || rulerMention.ruler_id !== segment.ruler_id || rulerMention.era_card_id !== segment.era_card_id) {
            throw new Error(`Story ${story.id} ruler segment 引用无效: ${String(rulerMentionId)}`);
          }
          if (rulerMention.section !== layer) {
            throw new Error(`Story ${story.id} ruler Mention 层级不一致: ${String(rulerMentionId)}`);
          }
          placedRuler.add(rulerMentionId as string);
          if (layer === "liu_annotation" && segment.annotation_id !== annotationId) {
            throw new Error(`Story ${story.id} annotation ruler Mention 所属 block 不一致: ${String(rulerMentionId)}`);
          }
          continue;
        }
        if (!isRecord(segment) || (segment.type !== "person_mention" && segment.type !== "identity_mention")) continue;
        const mentionId = segment.mention_id;
        if (typeof mentionId !== "string") continue;
        if (placed.has(mentionId)) {
          throw new Error(`Story ${story.id} 重复渲染 Mention: ${mentionId}`);
        }
        placed.add(mentionId);
        const mention = mentionById.get(mentionId);
        if (!mention) {
          throw new Error(`Story ${story.id} inline segment 引用了不存在的 Mention: ${mentionId}`);
        }
        if (mention.story_id !== story.id || mention.section !== layer) {
          throw new Error(`Story ${story.id} inline Mention 层级不一致: ${mentionId}`);
        }
        if (segment.type === "identity_mention") {
          if (mention.resolution_status !== segment.resolution_status || segment.target_kind !== "identity_candidate") {
            throw new Error(`Story ${story.id} identity Mention resolution 不一致: ${mentionId}`);
          }
          if (isRecord(mention.resolution_target) && mention.resolution_target.target_kind === "production_person") {
            throw new Error(`Story ${story.id} identity Mention 不得指向 production Person: ${mentionId}`);
          }
          if (layer === "liu_annotation" && segment.annotation_id !== annotationId) {
            throw new Error(`Story ${story.id} annotation identity Mention 所属 block 不一致: ${mentionId}`);
          }
          // Continue scanning this annotation block.  An annotation may
          // contain more than one resolved/identity Mention; returning here
          // would make later segments invisible to the runtime projection
          // invariant and produce a false "Mention 未投影" error.
          continue;
        }
        if (segment.person_id !== mention.person_id || typeof mention.person_id !== "string" || mention.confidence === "unresolved" || !peopleIds.has(mention.person_id)) {
          throw new Error(`Story ${story.id} inline Mention 的 Person 不一致: ${mentionId}`);
        }
        if (layer === "liu_annotation" && segment.annotation_id !== annotationId) {
          throw new Error(`Story ${story.id} annotation Mention 所属 block 不一致: ${mentionId}`);
        }
      }
    };
    const mainText = reading.main_text;
    const mentionDisplay = isRecord(reading.mention_display) ? reading.mention_display : {};
    if (isRecord(mainText)) inspectSegments(mainText.segments, "main_text");
    const annotations = reading.annotations;
    if (Array.isArray(annotations)) {
      for (const annotation of annotations) {
        if (isRecord(annotation)) inspectSegments(annotation.segments, "liu_annotation", String(annotation.id));
      }
    }
    for (const [rulerMentionId, rulerMention] of rulerMentionById.entries()) {
      if (rulerMention.story_id === story.id && !placedRuler.has(rulerMentionId)) {
        throw new Error(`Story ${story.id} resolved ruler Mention 未投影: ${rulerMentionId}`);
      }
    }
    const projectionRecord = reading.mention_projection;
    if (!isRecord(projectionRecord) || !Array.isArray(projectionRecord.suppressed)) {
      throw new Error(`Story ${story.id} mention projection 不完整`);
    }
    for (const item of projectionRecord.suppressed) {
      if (!isRecord(item) || typeof item.mention_id !== "string") {
        throw new Error(`Story ${story.id} mention projection suppression 无效`);
      }
      if (placed.has(item.mention_id) || suppressed.has(item.mention_id)) {
        throw new Error(`Story ${story.id} Mention 重复 projection: ${item.mention_id}`);
      }
      suppressed.add(item.mention_id);
      const mention = mentionById.get(item.mention_id);
      if (!mention || mention.story_id !== story.id || mention.section !== item.section) {
        throw new Error(`Story ${story.id} suppressed Mention 引用无效: ${item.mention_id}`);
      }
    }
    const storyMentionIds = Array.isArray(story.mention_ids) ? story.mention_ids : [];
    for (const mentionId of storyMentionIds) {
      const mention = mentionById.get(String(mentionId));
      const visibleResolution = Boolean(
        mention
        && (
          (typeof mention.person_id === "string" && mention.confidence !== "unresolved")
          || mention.resolution_status === "resolved"
          || mention.resolution_status === "candidate_for_review"
        )
      );
      if (visibleResolution && !placed.has(String(mentionId)) && !suppressed.has(String(mentionId))) {
        throw new Error(`Story ${story.id} resolved Mention 未投影: ${mentionId}`);
      }
      if (visibleResolution && !isRecord(mentionDisplay[String(mentionId)])) {
        throw new Error(`Story ${story.id} resolved Mention 缺少 explanation display: ${mentionId}`);
      }
    }
  }
  if (isRecord(value.story_chain)) {
    const chain = value.story_chain;
    if (!Array.isArray(chain.story_ids) || chain.story_ids.some((id) => typeof id !== "string" || !storyIds.has(id))) {
      throw new Error("story_chain.story_ids 引用了不存在的 Story");
    }
    if (!Array.isArray(chain.person_story_refs) || chain.person_story_refs.some((ref) => {
      return !isRecord(ref) || typeof ref.person_id !== "string" || !peopleIds.has(ref.person_id) || !Array.isArray(ref.story_ids) || ref.story_ids.some((id) => !storyIds.has(id));
    })) {
      throw new Error("story_chain.person_story_refs 引用了不存在的 Person 或 Story");
    }
    if (!Array.isArray(chain.story_person_refs) || chain.story_person_refs.some((ref) => {
      return !isRecord(ref) || typeof ref.entry_id !== "string" || !storyIds.has(ref.entry_id) || !Array.isArray(ref.linked_person_ids) || ref.linked_person_ids.some((id) => !peopleIds.has(id));
    })) {
      throw new Error("story_chain.story_person_refs 引用了不存在的 Person 或 Story");
    }
    for (const storyId of chain.story_ids) {
      const story = arrays.stories.find(
        (item): item is RuntimeStoryRecord => isRuntimeStoryRecord(item) && item.id === storyId,
      );
      if (story && story.publication_state === "blocked") {
        throw new Error(`story_chain 不得发布 blocked Story: ${storyId}`);
      }
    }
  }
  return value as unknown as SiteBundle;
}

export function loadSiteBundle(): SiteBundle {
  return parseSiteBundle(generatedSiteBundle);
}
