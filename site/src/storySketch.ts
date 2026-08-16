import type { StorySketchEvidenceProjection, StorySketchProjection } from "./types";

export const NL0_STORY_IDS = new Set([
  "02-yanyu-035",
  "02-yanyu-036",
  "05-fangzheng-032",
  "06-yaliang-017",
  "09-pinzao-017",
  "19-xianyuan-026",
  "27-jiajue-008",
]);

const storySketchCache = new Map<string, Promise<StorySketchProjection | null>>();
const storySketchEvidenceCache = new Map<string, Promise<StorySketchEvidenceProjection | null>>();

function storySketchUrl(storyId: string): string {
  const base = import.meta.env.BASE_URL.endsWith("/")
    ? import.meta.env.BASE_URL
    : `${import.meta.env.BASE_URL}/`;
  return `${base}generated/nl0/story-sketch/${encodeURIComponent(storyId)}.json`;
}

function storySketchEvidenceUrl(evidenceId: string): string {
  const base = import.meta.env.BASE_URL.endsWith("/")
    ? import.meta.env.BASE_URL
    : `${import.meta.env.BASE_URL}/`;
  return `${base}generated/nl0/evidence/${encodeURIComponent(evidenceId)}.json`;
}

/** Load one accepted NL0 StorySketch shard after an explicit Sketch choice. */
export function loadStorySketch(storyId: string, signal?: AbortSignal): Promise<StorySketchProjection | null> {
  const cached = storySketchCache.get(storyId);
  if (cached) return cached;

  const request = fetch(storySketchUrl(storyId), {
    headers: { Accept: "application/json" },
    signal,
  })
    .then(async (response) => {
      if (response.status === 404) return null;
      if (!response.ok) throw new Error(`StorySketch request failed: ${response.status}`);
      return await response.json() as StorySketchProjection;
    })
    .catch((error: unknown) => {
      storySketchCache.delete(storyId);
      throw error;
    });

  storySketchCache.set(storyId, request);
  return request;
}

export function clearStorySketchCache(): void {
  storySketchCache.clear();
  storySketchEvidenceCache.clear();
}

export function loadStorySketchEvidence(
  evidenceIds: string[],
  signal?: AbortSignal,
): Promise<StorySketchEvidenceProjection[]> {
  const uniqueIds = [...new Set(evidenceIds)];
  return Promise.all(uniqueIds.map((evidenceId) => {
    const cached = storySketchEvidenceCache.get(evidenceId);
    if (cached) return cached;
    const request = fetch(storySketchEvidenceUrl(evidenceId), {
      headers: { Accept: "application/json" },
      signal,
    })
      .then(async (response) => {
        if (response.status === 404) return null;
        if (!response.ok) throw new Error(`StorySketch evidence request failed: ${response.status}`);
        return await response.json() as StorySketchEvidenceProjection;
      })
      .catch((error: unknown) => {
        storySketchEvidenceCache.delete(evidenceId);
        throw error;
      });
    storySketchEvidenceCache.set(evidenceId, request);
    return request;
  })).then((items) => items.filter((item): item is StorySketchEvidenceProjection => Boolean(item)));
}
