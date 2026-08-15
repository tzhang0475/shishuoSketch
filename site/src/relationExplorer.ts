import type { Person, Relation, SiteBundle } from "./types";

export type PersonMentionRoute = {
  via_mention_id: string;
  from_story_id: string;
};

export type PersonRelationRoute = {
  via_relation_id: string;
  from_person_id: string;
  context_story_id?: string;
};

export type ExplorationNode =
  | { kind: "story"; id: string }
  | ({ kind: "person"; id: string } & Partial<PersonMentionRoute & PersonRelationRoute>)
  | ({ kind: "era"; id: string } & Partial<Pick<PersonRelationRoute, "context_story_id">>);

export interface RelationPerspective {
  relation: Relation;
  neighbor: Person;
  currentRole: string;
  neighborRole: string;
}

export interface LayoutPoint {
  x: number;
  y: number;
}

export interface EgoLayout {
  center: LayoutPoint;
  neighbors: LayoutPoint[];
}

export function appendExploration(stack: ExplorationNode[], node: ExplorationNode): ExplorationNode[] {
  const last = stack[stack.length - 1];
  if (last?.kind === node.kind && last.id === node.id) return stack;
  return [...stack, node];
}

export function backExploration(stack: ExplorationNode[]): ExplorationNode[] {
  return stack.length > 1 ? stack.slice(0, -1) : stack;
}

export function truncateExploration(stack: ExplorationNode[], index: number): ExplorationNode[] {
  if (index < 0 || index >= stack.length) return stack;
  return stack.slice(0, index + 1);
}

export function publishedStoryIds(data: SiteBundle): string[] {
  return data.stories
    .filter((story) => story.publication_state === "production_ready" || story.publication_state === "preview_ready")
    .map((story) => story.id);
}

function isPublishedStory(story: SiteBundle["stories"][number]): boolean {
  return story.publication_state === "production_ready" || story.publication_state === "preview_ready";
}

function storyOrderValue(story: SiteBundle["stories"][number]): [number, number, string] {
  return [
    typeof story.global_ordinal === "number" ? story.global_ordinal : Number.POSITIVE_INFINITY,
    typeof story.ordinal === "number" ? story.ordinal : Number.POSITIVE_INFINITY,
    story.id,
  ];
}

function compareStories(left: SiteBundle["stories"][number], right: SiteBundle["stories"][number]): number {
  const leftKey = storyOrderValue(left);
  const rightKey = storyOrderValue(right);
  return leftKey[0] - rightKey[0] || leftKey[1] - rightKey[1] || leftKey[2].localeCompare(rightKey[2]);
}

function storyHasMainTextEndpointMention(
  data: SiteBundle,
  storyId: string,
  endpointIds: string[],
): boolean {
  const endpoints = new Set(endpointIds);
  return data.mentions.some(
    (mention) =>
      mention.story_id === storyId &&
      mention.section === "main_text" &&
      mention.confidence !== "unresolved" &&
      mention.person_id !== null &&
      endpoints.has(mention.person_id),
  );
}

function selectPublishedStory(
  data: SiteBundle,
  candidateIds: string[],
  endpointIds: string[],
  currentStoryId?: string,
): string | null {
  const candidateSet = new Set(candidateIds);
  const candidates = data.stories
    .filter((story) => isPublishedStory(story) && candidateSet.has(story.id))
    .sort(compareStories);
  if (candidates.length === 0) return null;

  const mainTextCandidates = candidates.filter((story) =>
    storyHasMainTextEndpointMention(data, story.id, endpointIds),
  );
  const preferred = mainTextCandidates.length > 0 ? mainTextCandidates : candidates;
  const different = currentStoryId ? preferred.find((story) => story.id !== currentStoryId) : undefined;
  return (different ?? preferred[0])?.id ?? null;
}

/**
 * Select navigation context for a Relation traversal.
 *
 * This is intentionally a reader-routing decision, not a new historical
 * assertion.  Relation evidence is preferred; Person Story coverage is only
 * a deterministic fallback when no published supporting Story exists.
 */
export function relationContextStoryId(
  data: SiteBundle,
  relation: Relation,
  neighborPersonId: string,
  currentStoryId?: string,
): string | null {
  const endpointIds = [relation.subject_id, relation.object_id];
  for (const supportingIds of [relation.story_ids ?? [], relation.source_entry_ids ?? []]) {
    const selected = selectPublishedStory(data, supportingIds, endpointIds, currentStoryId);
    if (selected) return selected;
  }

  const mainTextIds = mainTextPublishedStoryIdsForPerson(data, neighborPersonId);
  const fallbackMain = selectPublishedStory(data, mainTextIds, [neighborPersonId], currentStoryId);
  if (fallbackMain) return fallbackMain;

  const fallbackAny = selectPublishedStory(
    data,
    publishedStoryIdsForPerson(data, neighborPersonId),
    [neighborPersonId],
    currentStoryId,
  );
  return fallbackAny;
}

/**
 * Return the published Story connections already projected for a Person.
 * Mention sections are consulted separately for main-text preference below.
 */
export function publishedStoryIdsForPerson(data: SiteBundle, personId: string): string[] {
  return data.stories
    .filter((story) => isPublishedStory(story) && story.person_ids.includes(personId))
    .map((story) => story.id);
}

export function mainTextPublishedStoryIdsForPerson(data: SiteBundle, personId: string): string[] {
  const publishedIds = new Set(publishedStoryIdsForPerson(data, personId));
  const mainTextMentionStoryIds = new Set(
    data.mentions
      .filter(
        (mention) =>
          mention.person_id === personId &&
          mention.section === "main_text" &&
          mention.confidence !== "unresolved",
      )
      .map((mention) => mention.story_id),
  );
  return data.stories
    .filter((story) => publishedIds.has(story.id) && mainTextMentionStoryIds.has(story.id))
    .map((story) => story.id);
}

export function randomPublishedStoryId(
  data: SiteBundle,
  random: () => number = Math.random,
  excludeId?: string,
): string | null {
  const allIds = publishedStoryIds(data);
  const ids = allIds.length > 1 && excludeId ? allIds.filter((id) => id !== excludeId) : allIds;
  if (ids.length === 0) return null;
  const value = Math.min(Math.max(random(), 0), 0.999999999);
  return ids[Math.floor(value * ids.length)] ?? ids[0];
}

export function randomPublishedStoryIdForPerson(
  data: SiteBundle,
  personId: string,
  random: () => number = Math.random,
  excludeStoryId?: string,
): string | null {
  const allIds = publishedStoryIdsForPerson(data, personId);
  const mainTextIds = mainTextPublishedStoryIdsForPerson(data, personId);
  const preferredIds = mainTextIds.length > 0 ? mainTextIds : allIds;
  const ids = preferredIds.length > 1 && excludeStoryId
    ? preferredIds.filter((id) => id !== excludeStoryId)
    : preferredIds;
  if (ids.length === 0) return null;
  const value = Math.min(Math.max(random(), 0), 0.999999999);
  return ids[Math.floor(value * ids.length)] ?? ids[0];
}

export function eligiblePersonIds(data: SiteBundle): string[] {
  return data.people
    .filter(
      (person) =>
        Boolean(data.person_sketches[person.id]) &&
        publishedStoryIdsForPerson(data, person.id).length > 0,
    )
    .map((person) => person.id);
}

export function randomEligiblePersonId(
  data: SiteBundle,
  random: () => number = Math.random,
  excludeId?: string,
): string | null {
  const allIds = eligiblePersonIds(data);
  const ids = allIds.length > 1 && excludeId ? allIds.filter((id) => id !== excludeId) : allIds;
  if (ids.length === 0) return null;
  const value = Math.min(Math.max(random(), 0), 0.999999999);
  return ids[Math.floor(value * ids.length)] ?? ids[0];
}

export function storyIdFromHash(hash: string): string | null {
  const match = hash.match(/^#story=([^&]+)$/u);
  if (!match) return null;
  try {
    const value = decodeURIComponent(match[1]);
    return value || null;
  } catch {
    return null;
  }
}

export function currentStoryFromExploration(
  stack: ExplorationNode[],
  validStoryIds?: ReadonlySet<string>,
): string | null {
  const isValid = (storyId: string): boolean => !validStoryIds || validStoryIds.has(storyId);
  for (const node of [...stack].reverse()) {
    if ((node.kind === "person" || node.kind === "era") && node.context_story_id && isValid(node.context_story_id)) {
      return node.context_story_id;
    }
    if (node.kind === "story" && isValid(node.id)) return node.id;
  }
  return null;
}

export function focusedPersonFromExploration(stack: ExplorationNode[]): string | null {
  return [...stack].reverse().find((node) => node.kind === "person")?.id ?? null;
}

export function focusedPersonNodeFromExploration(stack: ExplorationNode[]): ExplorationNode | null {
  return [...stack].reverse().find((node) => node.kind === "person") ?? null;
}

export function focusedEraFromExploration(stack: ExplorationNode[]): string | null {
  return [...stack].reverse().find((node) => node.kind === "era")?.id ?? null;
}

export function focusedEraNodeFromExploration(stack: ExplorationNode[]): ExplorationNode | null {
  return [...stack].reverse().find((node) => node.kind === "era") ?? null;
}

export function reviewedDirectRelations(data: SiteBundle): Relation[] {
  return data.relations.filter(
    (relation) => relation.review_status === "reviewed" && relation.relation_basis === "direct",
  );
}

export function directRelationPerspectives(personId: string, data: SiteBundle): RelationPerspective[] {
  const people = new Map(data.people.map((person) => [person.id, person]));
  return reviewedDirectRelations(data).flatMap((relation) => {
    if (relation.subject_id === personId && relation.object_id !== personId) {
      const neighbor = people.get(relation.object_id);
      if (!neighbor) return [];
      return [{ relation, neighbor, currentRole: relation.role_a ?? "", neighborRole: relation.role_b ?? "" }];
    }
    if (relation.object_id === personId && relation.subject_id !== personId) {
      const neighbor = people.get(relation.subject_id);
      if (!neighbor) return [];
      return [{ relation, neighbor, currentRole: relation.role_b ?? "", neighborRole: relation.role_a ?? "" }];
    }
    return [];
  });
}

export function derivedRelationsForPerson(personId: string, data: SiteBundle): Relation[] {
  return data.relations.filter(
    (relation) =>
      relation.review_status === "reviewed" &&
      relation.relation_basis === "derived" &&
      (relation.subject_id === personId || relation.object_id === personId),
  );
}

export function derivedPath(relation: Relation, data: SiteBundle): Relation[] {
  const relations = new Map(data.relations.map((item) => [item.id, item]));
  const remaining = (relation.derived_from_relation_ids ?? [])
    .map((id) => relations.get(id))
    .filter((item): item is Relation => Boolean(item));
  const path: Relation[] = [];
  let current = relation.subject_id;
  while (current !== relation.object_id && remaining.length > 0) {
    const index = remaining.findIndex(
      (candidate) => candidate.subject_id === current || candidate.object_id === current,
    );
    if (index < 0) return [];
    const [next] = remaining.splice(index, 1);
    path.push(next);
    current = next.subject_id === current ? next.object_id : next.subject_id;
  }
  return current === relation.object_id ? path : [];
}

export function pathPersonIds(path: Relation[], startId?: string): string[] {
  if (path.length === 0) return [];
  const ids = [startId ?? path[0].subject_id];
  for (const relation of path) {
    const last = ids[ids.length - 1];
    if (relation.subject_id === last) ids.push(relation.object_id);
    else if (relation.object_id === last) ids.push(relation.subject_id);
    else return [];
  }
  return ids;
}

export function egoLayout(neighborCount: number): EgoLayout {
  const center = { x: 50, y: 50 };
  if (neighborCount <= 0) return { center, neighbors: [] };
  if (neighborCount === 1) return { center, neighbors: [{ x: 78, y: 50 }] };
  const radius = neighborCount >= 5 ? 34 : 31;
  const neighbors = Array.from({ length: neighborCount }, (_, index) => {
    const angle = (-Math.PI / 2) + (index * (2 * Math.PI)) / neighborCount;
    return {
      x: 50 + radius * Math.cos(angle),
      y: 50 + radius * Math.sin(angle),
    };
  });
  return { center, neighbors };
}

export function focusHistory(current: string[], nextId: string): string[] {
  return current[current.length - 1] === nextId ? current : [...current, nextId];
}

export function backHistory(current: string[]): { history: string[]; focusedId: string | null } {
  if (current.length < 2) return { history: current, focusedId: current[0] ?? null };
  const history = current.slice(0, -1);
  return { history, focusedId: history[history.length - 1] ?? null };
}
