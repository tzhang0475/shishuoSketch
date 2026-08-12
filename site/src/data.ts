import type { SiteBundle } from "./types";
import generatedSiteBundle from "./generated/wp1-site.json";

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

function requireArray(value: unknown, key: string): unknown[] {
  if (!isRecord(value) || !Array.isArray(value[key])) {
    throw new Error(`静态数据缺少数组: ${key}`);
  }
  return value[key];
}

export function parseSiteBundle(value: unknown): SiteBundle {
  if (!isRecord(value) || value.schema !== 1 || typeof value.generated_from !== "string") {
    throw new Error("静态数据不是受支持的 WP1 bundle");
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
      throw new Error("Story 缺少 reviewed reading layer");
    }
    const reading = story.reading;
    if (reading.entry_id !== story.id || reading.status !== "reviewed") {
      throw new Error(`Story ${String(story.id)} 的 reading layer 标识不一致`);
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
  return value as unknown as SiteBundle;
}

export function loadSiteBundle(): SiteBundle {
  return parseSiteBundle(generatedSiteBundle);
}
