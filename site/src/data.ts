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
    if (!Array.isArray(reading.annotations) || reading.annotations.some((item) => {
      return !isRecord(item) || typeof item.id !== "string" || typeof item.original !== "string" || typeof item.simplified !== "string";
    })) {
      throw new Error(`Story ${String(story.id)} 的 reading.annotations 不完整`);
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
