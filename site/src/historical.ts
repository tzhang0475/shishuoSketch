import type {
  EraHistoricalProjection,
  HistoricalEvidenceProjection,
  PersonHistoricalProjection,
  RelationHistoricalProjection,
  StoryHistoricalProjection,
} from "./types";

export type HistoricalProjection =
  | PersonHistoricalProjection
  | StoryHistoricalProjection
  | EraHistoricalProjection
  | RelationHistoricalProjection
  | HistoricalEvidenceProjection;

export type HistoricalProjectionKind = "person" | "story" | "era" | "relation" | "evidence";

const projectionCache = new Map<string, Promise<HistoricalProjection | null>>();

function projectionUrl(kind: HistoricalProjectionKind, id: string): string {
  const base = import.meta.env.BASE_URL.endsWith("/")
    ? import.meta.env.BASE_URL
    : `${import.meta.env.BASE_URL}/`;
  return `${base}generated/history/${kind}/${encodeURIComponent(id)}.json`;
}

/**
 * Fetch one optional static historical projection.  The promise itself is
 * cached so repeated and concurrent panel opens share one request.  Failed
 * requests are removed from the cache so a later explicit open may retry.
 */
export function loadHistoricalProjection<T extends HistoricalProjection>(
  kind: HistoricalProjectionKind,
  id: string,
  signal?: AbortSignal,
): Promise<T | null> {
  const cacheKey = `${kind}:${id}`;
  const cached = projectionCache.get(cacheKey);
  if (cached) return cached as Promise<T | null>;

  const request = fetch(projectionUrl(kind, id), {
    headers: { Accept: "application/json" },
    signal,
  })
    .then(async (response) => {
      if (response.status === 404) return null;
      if (!response.ok) throw new Error(`historical projection request failed: ${response.status}`);
      return await response.json() as T;
    })
    .catch((error: unknown) => {
      projectionCache.delete(cacheKey);
      throw error;
    });

  projectionCache.set(cacheKey, request as Promise<HistoricalProjection | null>);
  return request;
}

export function loadHistoricalEvidence(
  evidenceIds: string[],
  signal?: AbortSignal,
): Promise<HistoricalEvidenceProjection[]> {
  const uniqueIds = [...new Set(evidenceIds)];
  return Promise.all(
    uniqueIds.map((id) => loadHistoricalProjection<HistoricalEvidenceProjection>("evidence", id, signal)),
  ).then((items) => items.filter((item): item is HistoricalEvidenceProjection => Boolean(item)));
}

export function clearHistoricalProjectionCache(): void {
  projectionCache.clear();
}

