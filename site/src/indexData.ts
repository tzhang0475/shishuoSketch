export type ReadingPair = { original: string; simplified: string };

export interface PersonIndexRecord {
  person_id: string;
  name: ReadingPair;
  surname: ReadingPair;
}

export interface StoryIndexRecord {
  story_id: string;
  category_id: string;
  category: ReadingPair;
  category_number: number;
  reference: ReadingPair;
  publication_state: "production_ready" | "preview_ready";
}

interface IndexDocument<T> {
  schema: number;
  projection: string;
  index_type: "person" | "story";
  count: number;
  source_bundle: { path: string; sha256: string };
  records: T[];
}

export interface UX2IndexProjection {
  people: IndexDocument<PersonIndexRecord>;
  stories: IndexDocument<StoryIndexRecord>;
}

let projectionPromise: Promise<UX2IndexProjection> | null = null;

function projectionUrl(name: string): string {
  return `${import.meta.env.BASE_URL}generated/ux2/${name}`;
}

async function loadDocument<T>(name: string): Promise<IndexDocument<T>> {
  const response = await fetch(projectionUrl(name), { headers: { Accept: "application/json" } });
  if (!response.ok) throw new Error(`UX2 index request failed: ${response.status}`);
  const value = await response.json() as IndexDocument<T>;
  if (!value || value.schema !== 1 || value.projection !== "ux2_production_index" || !Array.isArray(value.records)) {
    throw new Error(`Invalid UX2 index projection: ${name}`);
  }
  if (value.count !== value.records.length) throw new Error(`UX2 index count mismatch: ${name}`);
  return value;
}

export function loadUX2Index(): Promise<UX2IndexProjection> {
  if (!projectionPromise) {
    projectionPromise = Promise.all([
      loadDocument<PersonIndexRecord>("person-index.json"),
      loadDocument<StoryIndexRecord>("story-index.json"),
    ]).then(([people, stories]) => ({ people, stories }));
  }
  return projectionPromise;
}
