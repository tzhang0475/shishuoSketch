export interface DS1Claim {
  text: string | null;
  evidence_refs: string[];
}

export interface DS1ParticipantState {
  person_id: string | null;
  surface: string;
  state: string | null;
  evidence_refs: string[];
}

export interface DS1SceneContext {
  scene_summary: DS1Claim;
  participant_states: DS1ParticipantState[];
  relationship_context: DS1Claim[];
  reader_needed_context: DS1Claim[];
  uncertainties: DS1Claim[];
}

export interface DS1Preview {
  schema: "ds1-scene-context-preview";
  schema_version: 1;
  stage: "DS1";
  story_id: string;
  review_status: "accepted" | "edited";
  candidate_sha256: string;
  evidence_bundle_ids: string[];
  scene_context: DS1SceneContext;
}

const ds1PreviewCache = new Map<string, Promise<DS1Preview | null>>();

function ds1PreviewUrl(storyId: string): string {
  const base = import.meta.env.BASE_URL.endsWith("/")
    ? import.meta.env.BASE_URL
    : `${import.meta.env.BASE_URL}/`;
  return `${base}generated/ds1/${encodeURIComponent(storyId)}.json`;
}

/** Load the optional, human-reviewed DS1 preview without enlarging SC1. */
export function loadDs1Preview(storyId: string, signal?: AbortSignal): Promise<DS1Preview | null> {
  const cached = ds1PreviewCache.get(storyId);
  if (cached) return cached;
  const request = fetch(ds1PreviewUrl(storyId), {
    headers: { Accept: "application/json" },
    signal,
  })
    .then(async (response) => {
      if (response.status === 404) return null;
      if (!response.ok) throw new Error(`DS1 preview request failed: ${response.status}`);
      return await response.json() as DS1Preview;
    })
    .catch((error: unknown) => {
      ds1PreviewCache.delete(storyId);
      throw error;
    });
  ds1PreviewCache.set(storyId, request);
  return request;
}

export function clearDs1PreviewCache(): void {
  ds1PreviewCache.clear();
}
