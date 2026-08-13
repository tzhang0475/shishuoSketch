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

function validateReadingSegments(
  segments: unknown,
  expectedOriginal: string,
  expectedSimplified: string,
  layer: "main_text" | "liu_annotation",
  annotationId?: string,
): void {
  if (!Array.isArray(segments)) {
    throw new Error(`reading ${layer} 缺少 segments`);
  }
  let original = "";
  let simplified = "";
  for (const segment of segments) {
    if (!isRecord(segment) || (segment.type !== "text" && segment.type !== "person_mention")) {
      throw new Error(`reading ${layer} 存在无效 segment`);
    }
    const display = segment.display;
    if (!isRecord(display) || typeof display.original !== "string" || typeof display.simplified !== "string") {
      throw new Error(`reading ${layer} segment display 不完整`);
    }
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
  const keys = ["stories", "people", "mentions", "relations", "eras", "evidence", "sources"];
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
  for (const story of arrays.stories) {
    if (!isRecord(story) || !isRecord(story.reading)) {
      throw new Error("Story 缺少 reading layer");
    }
    if (!isRuntimeStoryRecord(story)) {
      throw new Error(`Story ${String(story.id)} 的 publication_state 无效`);
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
    validateReadingSegments(
      reading.main_text.segments,
      reading.main_text.original,
      reading.main_text.simplified,
      "main_text",
    );
    if (!Array.isArray(reading.annotations) || reading.annotations.some((item) => {
      return !isRecord(item) || typeof item.id !== "string" || typeof item.original !== "string" || typeof item.simplified !== "string" || !Array.isArray(item.segments);
    })) {
      throw new Error(`Story ${String(story.id)} 的 reading.annotations 不完整`);
    }
    for (const annotation of reading.annotations) {
      if (!isRecord(annotation)) continue;
      validateReadingSegments(
        annotation.segments,
        String(annotation.original),
        String(annotation.simplified),
        "liu_annotation",
        String(annotation.id),
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
  }
  for (const mention of arrays.mentions) {
    if (!isRecord(mention) || typeof mention.story_id !== "string" || !storyIds.has(mention.story_id)) {
      throw new Error("Mention 引用了不存在的 Story");
    }
  }
  const peopleIds = new Set(arrays.people.map((item) => (item as Record<string, unknown>).id));
  const mentionById = new Map(
    arrays.mentions
      .filter(isRecord)
      .filter((item) => typeof item.id === "string")
      .map((item) => [String(item.id), item]),
  );
  const relationIds = new Set(arrays.relations.map((item) => (item as Record<string, unknown>).id));
  const evidenceIds = new Set(arrays.evidence.map((item) => (item as Record<string, unknown>).id));
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
    const suppressed = new Set<string>();
    const inspectSegments = (segments: unknown, layer: "main_text" | "liu_annotation", annotationId?: string) => {
      if (!Array.isArray(segments)) return;
      for (const segment of segments) {
        if (!isRecord(segment) || segment.type !== "person_mention") continue;
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
        if (segment.person_id !== mention.person_id || typeof mention.person_id !== "string" || mention.confidence === "unresolved" || !peopleIds.has(mention.person_id)) {
          throw new Error(`Story ${story.id} inline Mention 的 Person 不一致: ${mentionId}`);
        }
        if (layer === "liu_annotation" && segment.annotation_id !== annotationId) {
          throw new Error(`Story ${story.id} annotation Mention 所属 block 不一致: ${mentionId}`);
        }
      }
    };
    const mainText = reading.main_text;
    if (isRecord(mainText)) inspectSegments(mainText.segments, "main_text");
    const annotations = reading.annotations;
    if (Array.isArray(annotations)) {
      for (const annotation of annotations) {
        if (isRecord(annotation)) inspectSegments(annotation.segments, "liu_annotation", String(annotation.id));
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
      if (mention && typeof mention.person_id === "string" && mention.confidence !== "unresolved" && !placed.has(String(mentionId)) && !suppressed.has(String(mentionId))) {
        throw new Error(`Story ${story.id} resolved Mention 未投影: ${mentionId}`);
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
