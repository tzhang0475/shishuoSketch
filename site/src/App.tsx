import { useEffect, useMemo, useRef, useState } from "react";
import { loadSiteBundle } from "./data";
import {
  derivedPath,
  derivedRelationsForPerson,
  directRelationPerspectives,
  egoLayout,
  appendExploration,
  backExploration,
  currentStoryFromExploration,
  randomEligiblePersonId,
  randomPublishedStoryId,
  randomPublishedStoryIdForPerson,
  storyIdFromHash,
  truncateExploration,
  pathPersonIds,
  focusedPersonFromExploration,
  focusedPersonNodeFromExploration,
  type PersonMentionRoute,
  type RelationPerspective,
  type ExplorationNode,
} from "./relationExplorer";
import type {
  Evidence,
  Mention,
  Person,
  ReadingPair,
  ReadingSegment,
  Relation,
  SiteBundle,
  Story,
  StorySceneContext,
} from "./types";

const FALLBACK_STORY_ID = "06-yaliang-019";
const READING_MODE_STORAGE_KEY = "shishuoSketch.reading-mode";
type ReadingMode = "simplified" | "original";
type ResolvedMention = Mention & { person_id: string };
type PersonFocus = (personId: string, route?: PersonMentionRoute) => void;

function initialReadingMode(): ReadingMode {
  if (typeof window === "undefined") return "simplified";
  const stored = window.localStorage.getItem(READING_MODE_STORAGE_KEY);
  return stored === "original" ? "original" : "simplified";
}

function readingValue(pair: ReadingPair | undefined, mode: ReadingMode, fallback: string): string {
  return pair?.[mode] ?? fallback;
}

function storyReference(story: Story, mode: ReadingMode): string {
  const idParts = story.id.split("-");
  const ordinal = story.ordinal ?? Number(idParts[idParts.length - 1] ?? 0);
  const chapter = readingValue(story.chapter_display, mode, story.chapter_heading ?? story.id);
  return `${chapter} · ${String(ordinal).padStart(3, "0")}`;
}

function storyHeading(story: Story, mode: ReadingMode): string {
  return story.title_source === "project_label" ? story.title : storyReference(story, mode);
}

function uiLabel(
  data: SiteBundle,
  key: keyof NonNullable<SiteBundle["ui"]>,
  mode: ReadingMode,
  fallback: string,
): string {
  return readingValue(data.ui?.[key], mode, fallback);
}

function resolvedMentions(story: Story, data: SiteBundle): ResolvedMention[] {
  return story.mention_ids
    .map((id) => data.mentions.find((mention) => mention.id === id))
    .filter((mention): mention is ResolvedMention => Boolean(mention?.person_id && mention.confidence !== "unresolved"));
}

function personDisplayName(story: Story, person: Person, mode: ReadingMode): string {
  return readingValue(story.reading.person_display[person.id]?.name, mode, person.canonical_name);
}

function mentionPersonDisplayName(
  story: Story,
  data: SiteBundle,
  mention: Mention,
  mode: ReadingMode,
): string {
  const person = data.people.find((candidate) => candidate.id === mention.person_id);
  return person ? personDisplayName(story, person, mode) : "";
}

function relationDisplayPair(
  story: Story,
  relation: Relation,
  role: "role_a" | "role_b" | "label",
  mode: ReadingMode,
  fallback: string,
): string {
  return readingValue(story.reading.relation_display[relation.id]?.[role] ?? undefined, mode, fallback);
}

function perspectiveNeighborRole(
  story: Story,
  perspective: RelationPerspective,
  mode: ReadingMode,
): string {
  const role = perspective.relation.subject_id === perspective.neighbor.id ? "role_a" : "role_b";
  return relationDisplayPair(story, perspective.relation, role, mode, perspective.neighborRole)
    || relationDisplayPair(story, perspective.relation, "label", mode, perspective.relation.label);
}

function personNameById(story: Story, data: SiteBundle, personId: string, mode: ReadingMode): string {
  const person = data.people.find((candidate) => candidate.id === personId);
  return person ? personDisplayName(story, person, mode) : personId;
}

function storyById(data: SiteBundle, storyId: string): Story | undefined {
  return data.stories.find((story) => story.id === storyId);
}

function writeStoryAddress(storyId: string): void {
  if (typeof window === "undefined") return;
  const next = `${window.location.pathname}${window.location.search}#story=${encodeURIComponent(storyId)}`;
  window.history.replaceState(null, "", next);
}

function initialStoryId(data: SiteBundle): string {
  const target = typeof window === "undefined" ? null : storyIdFromHash(window.location.hash);
  const addressed = target ? storyById(data, target) : undefined;
  if (addressed && addressed.publication_state !== "blocked") return addressed.id;
  return randomPublishedStoryId(data) ?? FALLBACK_STORY_ID;
}

function storyExcerpt(story: Story, mode: ReadingMode): string {
  const text = story.reading.main_text[mode].replace(/\s+/gu, "");
  return text.length > 54 ? `${text.slice(0, 54)}……` : text;
}

function InlineReadingSegments({
  segments,
  story,
  data,
  readingMode,
  focusedPersonId,
  onFocus,
  annotations,
  openAnnotationIds,
  onToggleAnnotation,
  showAnnotationMarkers = true,
}: {
  segments: ReadingSegment[];
  story: Story;
  data: SiteBundle;
  readingMode: ReadingMode;
  focusedPersonId: string | null;
  onFocus: PersonFocus;
  annotations: Story["reading"]["annotations"];
  openAnnotationIds: Set<string>;
  onToggleAnnotation: (annotationId: string) => void;
  showAnnotationMarkers?: boolean;
}) {
  function annotationEvidence(annotation: Story["reading"]["annotations"][number]): Evidence[] {
    const ids = annotation.evidence_ids ?? story.evidence_ids.filter((id) => {
      const item = data.evidence.find((candidate) => candidate.id === id);
      return item?.locator.annotation_id === annotation.id;
    });
    return ids
      .map((id) => data.evidence.find((item) => item.id === id))
      .filter((item): item is Evidence => Boolean(item));
  }

  function annotationExpansion(annotation: Story["reading"]["annotations"][number]): JSX.Element {
    const evidence = annotationEvidence(annotation);
    return (
      <span
        className="inline-annotation-expansion"
        id={`inline-annotation-${story.id}-${annotation.id}`}
        role="region"
        aria-label={readingValue(story.reading.labels.annotation_label, readingMode, "刘孝标注")}
      >
        <span className="inline-annotation-heading">
          {readingValue(story.reading.labels.annotation_label, readingMode, "刘孝标注")}
          {annotation.punctuation_status === "unavailable" && <span className="inline-annotation-status"> · 原文</span>}
        </span>
        <span className="inline-annotation-text">
          <InlineReadingSegments
            segments={annotation.segments}
            story={story}
            data={data}
            readingMode={readingMode}
            focusedPersonId={focusedPersonId}
            onFocus={onFocus}
            annotations={annotations}
            openAnnotationIds={openAnnotationIds}
            onToggleAnnotation={onToggleAnnotation}
            showAnnotationMarkers={false}
          />
        </span>
        {evidence.length > 0 && (
          <details className="inline-annotation-evidence">
            <summary>查看出处 ›</summary>
            {evidence.map((item) => (
              <span key={item.id}>
                <span className="inline-annotation-source">
                  {item.locator.annotation_id ? "刘孝标注" : item.source_id}
                </span>
                <blockquote>{readingValue(story.reading.evidence_display[item.id], readingMode, item.quote)}</blockquote>
              </span>
            ))}
          </details>
        )}
      </span>
    );
  }

  return (
    <>
      {segments.map((segment, index) => {
        const text = readingValue(segment.display, readingMode, "");
        if (segment.type === "text") {
          return <span key={`text-${index}`}>{text}</span>;
        }
        if (segment.type === "annotation_marker") {
          const annotation = annotations.find((candidate) => candidate.id === segment.annotation_id);
          if (!showAnnotationMarkers || !annotation) return null;
          const isOpen = openAnnotationIds.has(annotation.id);
          return (
            <span className="inline-annotation-marker-wrap" key={`annotation-marker-${segment.annotation_id}-${index}`}>
              <button
                type="button"
                className="inline-annotation-marker"
                aria-expanded={isOpen}
                aria-controls={`inline-annotation-${story.id}-${annotation.id}`}
                aria-label={`${readingValue(segment.label, readingMode, "〔注〕")}，打开刘孝标注`}
                onClick={() => onToggleAnnotation(annotation.id)}
              >
                {readingValue(segment.label, readingMode, "〔注〕")}
              </button>
              {isOpen && annotationExpansion(annotation)}
            </span>
          );
        }
        if (segment.type === "identity_mention") {
          const candidateNames = segment.candidate_names
            .map((candidate) => readingValue(candidate, readingMode, ""))
            .filter(Boolean);
          const resolvedName = segment.canonical_name
            ? readingValue(segment.canonical_name, readingMode, "")
            : "";
          if (segment.resolution_status === "candidate_for_review") {
            return (
              <details className="inline-identity-review" key={`${segment.mention_id}-${index}`}>
                <summary aria-label={`${text}，人物尚待确认`}>{text}</summary>
                <span className="inline-identity-review-body" role="note">
                  <span className="inline-identity-review-heading">人物尚待确认</span>
                  {candidateNames.length > 0 && (
                    <span>可能是：{candidateNames.join("、")}</span>
                  )}
                  <span>当前证据不足以唯一判断。</span>
                </span>
              </details>
            );
          }
          return (
            <span
              className="inline-identity-mention"
              key={`${segment.mention_id}-${index}`}
              title={resolvedName ? `${text} · ${resolvedName} · 人物卡尚未建立` : undefined}
            >
              {text}
            </span>
          );
        }
        const mention = data.mentions.find((candidate) => candidate.id === segment.mention_id);
        const person = data.people.find((candidate) => candidate.id === segment.person_id);
        const personName = person ? personDisplayName(story, person, readingMode) : segment.person_id;
        const active = focusedPersonId === segment.person_id;
        return (
          <button
            type="button"
            key={`${segment.mention_id}-${index}`}
            className={active ? "inline-person-mention active" : "inline-person-mention"}
            aria-label={`${text}，已解析为${personName}，查看人物`}
            title={mention ? `${text} → ${personName}` : personName}
            onClick={() => onFocus(segment.person_id, { via_mention_id: segment.mention_id, from_story_id: story.id })}
          >
            {text}
          </button>
        );
      })}
    </>
  );
}

function MentionSummaryGroup({
  label,
  mentions,
  story,
  data,
  readingMode,
  onFocus,
}: {
  label: string;
  mentions: ResolvedMention[];
  story: Story;
  data: SiteBundle;
  readingMode: ReadingMode;
  onFocus: PersonFocus;
}) {
  if (mentions.length === 0) return null;
  return (
    <div className="mention-summary-group">
      <p className="mention-summary-label">{label}</p>
      <ul className="mention-summary-list">
        {mentions.map((mention) => (
          <li key={mention.id}>
            <button
              type="button"
              className="mention-summary-link"
              onClick={() => onFocus(mention.person_id, { via_mention_id: mention.id, from_story_id: story.id })}
            >
              {readingValue(story.reading.mention_display[mention.id]?.surface, readingMode, mention.surface)}
              {" · "}
              {mentionPersonDisplayName(story, data, mention, readingMode)}
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}

function RelationEvidence({
  relation,
  story,
  data,
  readingMode,
  perspective,
}: {
  relation: Relation;
  story: Story;
  data: SiteBundle;
  readingMode: ReadingMode;
  perspective: RelationPerspective;
}) {
  const evidence = relation.evidence_ids
    .map((id) => data.evidence.find((item) => item.id === id))
    .filter((item): item is Evidence => Boolean(item));
  const neighborRole = perspectiveNeighborRole(story, perspective, readingMode);
  const neighborName = personDisplayName(story, perspective.neighbor, readingMode);
  const relationScope = readingValue(
    story.reading.relation_display[relation.id]?.scope ?? undefined,
    readingMode,
    relation.scope_event ?? "",
  );
  const sourceLocations = [
    ...(relation.source_entry_ids ?? []).map((id) => `entry · ${id}`),
    ...(relation.source_unit_ids ?? []).map((id) => `unit · ${id}`),
  ];

  return (
    <details className="relation-evidence">
      <summary>
        <span>{neighborName} · {neighborRole}{relationScope ? ` · ${relationScope}` : ""}</span>
        <span className="relation-evidence-summary">{story.reading.labels.relation_evidence_toggle[readingMode]}</span>
      </summary>
      <div className="relation-evidence-body">
        {evidence.map((item) => {
          const source = story.reading.source_display[item.source_id];
          const quote = readingValue(story.reading.evidence_display[item.id], readingMode, item.quote);
          return (
            <article className="relation-evidence-item" key={item.id}>
              <p className="relation-source-title">
                {source ? `${source.work[readingMode]} · ${source.edition[readingMode]}` : item.source_id}
              </p>
              <blockquote>{quote}</blockquote>
              <p className="relation-source-location">{sourceLocations.join("；") || item.locator.artifact_path}</p>
              <details className="relation-provenance">
                <summary>provenance</summary>
                <p>{item.locator.artifact_path} · {item.locator.artifact_sha256.slice(0, 12)}…</p>
                <p>{item.locator.source_provenance.witness_id}</p>
              </details>
            </article>
          );
        })}
      </div>
    </details>
  );
}

function DerivedRelationDetails({
  relation,
  story,
  data,
  readingMode,
  focusedPersonId,
}: {
  relation: Relation;
  story: Story;
  data: SiteBundle;
  readingMode: ReadingMode;
  focusedPersonId: string;
}) {
  const forwardPath = derivedPath(relation, data);
  const isReverse = focusedPersonId === relation.object_id;
  const path = isReverse ? [...forwardPath].reverse() : forwardPath;
  const displayIds = pathPersonIds(path, focusedPersonId);
  const otherPersonId = focusedPersonId === relation.subject_id ? relation.object_id : relation.subject_id;
  return (
    <details className="derived-relation">
      <summary>
        <span>{personNameById(story, data, otherPersonId, readingMode)} · {relationDisplayPair(story, relation, "label", readingMode, relation.label)}</span>
        <span className="relation-basis-note">{story.reading.labels.derived_relation_note[readingMode]}</span>
      </summary>
      <div className="derived-path" aria-label={story.reading.labels.derived_relation_label[readingMode]}>
        {path.length === 0 ? (
          <p>{story.reading.labels.derived_relation_note[readingMode]}</p>
        ) : (
          path.map((edge, index) => {
            const fromId = displayIds[index] ?? edge.subject_id;
            const toId = displayIds[index + 1] ?? edge.object_id;
            const fromName = personNameById(story, data, fromId, readingMode);
            const toName = personNameById(story, data, toId, readingMode);
            const edgeLabel = relationDisplayPair(story, edge, "label", readingMode, edge.label);
            return (
              <div className="derived-path-step" key={edge.id}>
                <span>{fromName}</span>
                <span className="derived-path-connector">↓ {edgeLabel} ↓</span>
                <span>{toName}</span>
              </div>
            );
          })
        )}
        <p className="derived-no-quotation">{story.reading.labels.derived_relation_note[readingMode]}</p>
      </div>
    </details>
  );
}

function EgoRelationMap({
  story,
  data,
  focusedPerson,
  perspectives,
  readingMode,
  onFocus,
}: {
  story: Story;
  data: SiteBundle;
  focusedPerson: Person;
  perspectives: RelationPerspective[];
  readingMode: ReadingMode;
  onFocus: PersonFocus;
}) {
  const layout = egoLayout(perspectives.length);
  return (
    <section className="ego-map-panel" aria-labelledby="ego-map-heading">
      <div className="section-heading">
        <p className="section-label">{story.reading.labels.relation_section[readingMode]}</p>
        <h3 id="ego-map-heading">{story.reading.labels.direct_relation_label[readingMode]}</h3>
      </div>
      {perspectives.length === 0 ? (
        <p className="relation-empty">{story.reading.labels.no_direct_relations[readingMode]}</p>
      ) : (
        <div className="ego-map" aria-label={story.reading.labels.direct_relation_label[readingMode]}>
          <svg className="ego-map-edges" viewBox="0 0 100 100" aria-hidden="true" preserveAspectRatio="none">
            {perspectives.map((perspective, index) => {
              const point = layout.neighbors[index];
              const edgeLabel = perspectiveNeighborRole(story, perspective, readingMode);
              const midpoint = { x: (layout.center.x + point.x) / 2, y: (layout.center.y + point.y) / 2 };
              return (
                <g key={perspective.relation.id}>
                  <line x1={layout.center.x} y1={layout.center.y} x2={point.x} y2={point.y} />
                  <text x={midpoint.x} y={midpoint.y - 2} textAnchor="middle">{edgeLabel}</text>
                </g>
              );
            })}
          </svg>
          <span
            className="ego-node ego-node-center"
            aria-label={personDisplayName(story, focusedPerson, readingMode)}
            aria-current="true"
          >
            {personDisplayName(story, focusedPerson, readingMode)}
          </span>
          {perspectives.map((perspective, index) => {
            const point = layout.neighbors[index];
            return (
              <button
                type="button"
                className="ego-node ego-node-neighbor"
                style={{ left: `${point.x}%`, top: `${point.y}%` }}
                key={perspective.relation.id}
                onClick={() => onFocus(perspective.neighbor.id)}
                aria-label={`${personDisplayName(story, perspective.neighbor, readingMode)} · ${perspectiveNeighborRole(story, perspective, readingMode)}`}
              >
                {personDisplayName(story, perspective.neighbor, readingMode)}
              </button>
            );
          })}
        </div>
      )}
    </section>
  );
}

function StoryCard({
  story,
  data,
  readingMode,
  annotationOnly,
  onSelect,
}: {
  story: Story;
  data: SiteBundle;
  readingMode: ReadingMode;
  annotationOnly: boolean;
  onSelect: () => void;
}) {
  return (
    <button type="button" className="story-card" onClick={onSelect}>
      <span className="story-card-reference">{storyReference(story, readingMode)}</span>
      <span className="story-card-excerpt">「{storyExcerpt(story, readingMode)}」</span>
      <span className="story-card-footer">
        <span>{annotationOnly ? uiLabel(data, "annotation_story_label", readingMode, "史料提及") : uiLabel(data, "read_story", readingMode, "閱讀")} →</span>
        <span className="story-card-status">
          {story.publication_state === "preview_ready"
            ? uiLabel(data, "preview_punctuation", readingMode, "句讀：參考底本整理 · 待復核")
            : uiLabel(data, "reviewed_punctuation", readingMode, "句讀：已復核")}
        </span>
      </span>
    </button>
  );
}

function PersonStories({
  data,
  focusedPerson,
  readingMode,
  onStorySelect,
}: {
  data: SiteBundle;
  focusedPerson: Person;
  readingMode: ReadingMode;
  onStorySelect: (storyId: string) => void;
}) {
  const reference = data.story_chain?.person_story_refs.find((item) => item.person_id === focusedPerson.id);
  const primaryIds = reference?.main_text_story_ids ?? [];
  const annotationIds = reference?.liu_annotation_only_story_ids ?? [];
  const primaryStories = primaryIds.map((id) => storyById(data, id)).filter((item): item is Story => Boolean(item));
  const annotationStories = annotationIds.map((id) => storyById(data, id)).filter((item): item is Story => Boolean(item));
  return (
    <div className="person-stories-group">
      <p className="relation-detail-heading">{uiLabel(data, "person_sketch_stories", readingMode, "《世說》中的他／她")}</p>
      {primaryStories.length === 0 ? (
        <p className="relation-empty">—</p>
      ) : (
        <div className="story-card-list">
          {primaryStories.map((candidate) => (
            <StoryCard
              key={candidate.id}
              story={candidate}
              data={data}
              readingMode={readingMode}
              annotationOnly={false}
              onSelect={() => onStorySelect(candidate.id)}
            />
          ))}
        </div>
      )}
      {annotationStories.length > 0 && (
        <div className="annotation-story-group">
          <p className="relation-detail-heading">{uiLabel(data, "annotation_story_label", readingMode, "史料提及")}</p>
          <div className="story-card-list">
            {annotationStories.map((candidate) => (
              <StoryCard
                key={candidate.id}
                story={candidate}
                data={data}
                readingMode={readingMode}
                annotationOnly
                onSelect={() => onStorySelect(candidate.id)}
              />
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function MentionOriginExplanation({
  story,
  data,
  focusedPerson,
  routeNode,
  readingMode,
}: {
  story: Story;
  data: SiteBundle;
  focusedPerson: Person;
  routeNode: ExplorationNode | null;
  readingMode: ReadingMode;
}) {
  if (!routeNode || routeNode.kind !== "person" || !routeNode.via_mention_id || !routeNode.from_story_id) {
    return null;
  }
  const originStory = storyById(data, routeNode.from_story_id);
  const mention = data.mentions.find((candidate) => candidate.id === routeNode.via_mention_id);
  if (!originStory || !mention || mention.person_id !== focusedPerson.id || mention.confidence === "unresolved") {
    return null;
  }
  const mentionDisplay = originStory.reading.mention_display[mention.id];
  const surface = readingValue(mentionDisplay?.surface, readingMode, mention.surface);
  const explanation = readingValue(mentionDisplay?.explanation, readingMode, "本项目已将此称谓解析为此人。");
  const evidence = mention.evidence_ids
    .map((id) => data.evidence.find((item) => item.id === id))
    .filter((item): item is Evidence => Boolean(item));
  return (
    <section className="mention-origin-explanation" aria-label="称谓解析说明">
      <p className="mention-origin-kicker">你从这里来到他 / 她</p>
      <p className="mention-origin-label">本则称谓</p>
      <p className="mention-origin-surface">{surface}</p>
      <p className="mention-origin-question">为什么这里指{personDisplayName(originStory, focusedPerson, readingMode)}？</p>
      <p className="mention-origin-reason">{explanation}</p>
      {evidence.length > 0 && (
        <details className="mention-origin-evidence">
          <summary>查看完整依据 ›</summary>
          {evidence.map((item) => (
            <article key={item.id}>
              <p className="mention-origin-source">
                {item.locator.annotation_id ? "刘孝标注" : "正文"}
              </p>
              <blockquote>{readingValue(originStory.reading.evidence_display[item.id], readingMode, item.quote)}</blockquote>
            </article>
          ))}
        </details>
      )}
    </section>
  );
}

function PersonSketchIdentity({
  story,
  data,
  focusedPerson,
  readingMode,
}: {
  story: Story;
  data: SiteBundle;
  focusedPerson: Person;
  readingMode: ReadingMode;
}) {
  const sketch = data.person_sketches[focusedPerson.id];
  if (!sketch) return null;
  const identity = sketch.identity;
  const roles = identity.identity_roles.map((role) => readingValue(role, readingMode, ""));
  return (
    <section className="person-sketch-identity" aria-label={uiLabel(data, "person_sketch_identity", readingMode, "人物概览")}>
      <p className="person-sketch-review-status">
        {sketch.review_status === "candidate"
          ? uiLabel(data, "person_sketch_candidate", readingMode, "資料整理預覽")
          : uiLabel(data, "person_sketch_reviewed", readingMode, "已復核資料")}
      </p>
      <dl className="person-sketch-metadata">
        {identity.courtesy_name && (
          <>
            <dt>{uiLabel(data, "person_sketch_courtesy_name", readingMode, "字")}</dt>
            <dd>{readingValue(identity.courtesy_name, readingMode, "")}</dd>
          </>
        )}
        {identity.clan && (
          <>
            <dt>{uiLabel(data, "person_sketch_clan", readingMode, "族属")}</dt>
            <dd>{readingValue(identity.clan, readingMode, "")}</dd>
          </>
        )}
        {roles.length > 0 && (
          <>
            <dt>{uiLabel(data, "person_sketch_roles", readingMode, "身份")}</dt>
            <dd>{roles.join("、")}</dd>
          </>
        )}
      </dl>
      {identity.brief_intro && (
        <p className="person-sketch-intro">
          {readingValue(identity.brief_intro, readingMode, "")}
        </p>
      )}
    </section>
  );
}

function PersonSketchAliasRows({
  story,
  data,
  focusedPerson,
  readingMode,
}: {
  story: Story;
  data: SiteBundle;
  focusedPerson: Person;
  readingMode: ReadingMode;
}) {
  const sketch = data.person_sketches[focusedPerson.id];
  if (!sketch) return null;
  return (
    <section className="person-sketch-naming" aria-label={uiLabel(data, "person_sketch_aliases", readingMode, "《世说》怎样称呼他／她")}>
      <p className="relation-detail-heading">{uiLabel(data, "person_sketch_aliases", readingMode, "《世说》怎样称呼他／她")}</p>
      {sketch.aliases.length === 0 ? (
        <p className="relation-empty">{story.reading.labels.empty_alias[readingMode]}</p>
      ) : (
        <div className="person-sketch-alias-list">
          {sketch.aliases.map((alias) => {
            const layers = alias.source_layers.map((layer) => layer === "main_text"
              ? uiLabel(data, "primary_story_label", readingMode, "正文出现")
              : uiLabel(data, "annotation_story_label", readingMode, "刘注提及"));
            const evidence = alias.evidence_ids
              .map((id) => data.evidence.find((item) => item.id === id))
              .filter((item): item is Evidence => Boolean(item));
            return (
              <article className="person-sketch-alias-row" key={alias.alias_id}>
                <div className="person-sketch-alias-main">
                  <span className="person-sketch-alias-surface">{readingValue(alias.surface, readingMode, "")}</span>
                  <span className="person-sketch-alias-label">{readingValue(alias.label, readingMode, "称谓")}</span>
                  <span className={alias.semantic_status === "exact" ? "person-sketch-alias-status exact" : "person-sketch-alias-status contextual"}>
                    {readingValue(alias.semantic_label, readingMode, "需结合上下文")}
                  </span>
                </div>
                <p className="person-sketch-alias-meta">
                  {layers.join("、") || "—"} · {alias.occurrence_count}次
                </p>
                {evidence.length > 0 && (
                  <details className="person-sketch-alias-evidence">
                    <summary>{uiLabel(data, "person_sketch_evidence", readingMode, "依据")} ›</summary>
                    {evidence.map((item) => {
                      const source = story.reading.source_display[item.source_id];
                      const quote = story.reading.evidence_display[item.id]?.[readingMode] ?? item.quote;
                      return (
                        <div key={item.id}>
                          <p>{source ? `${source.work[readingMode]} · ${source.edition[readingMode]}` : item.source_id}</p>
                          <blockquote>{quote}</blockquote>
                        </div>
                      );
                    })}
                  </details>
                )}
              </article>
            );
          })}
        </div>
      )}
    </section>
  );
}

function PersonSketchEvidence({
  story,
  data,
  focusedPerson,
  readingMode,
}: {
  story: Story;
  data: SiteBundle;
  focusedPerson: Person;
  readingMode: ReadingMode;
}) {
  const sketch = data.person_sketches[focusedPerson.id];
  if (!sketch) return null;
  const evidenceIds = [...new Set([...sketch.identity.evidence_ids, ...sketch.profile_evidence_ids])];
  const evidence = evidenceIds
    .map((id) => data.evidence.find((item) => item.id === id))
    .filter((item): item is Evidence => Boolean(item));
  if (evidence.length === 0) return null;
  return (
    <details className="person-sketch-evidence">
      <summary>{uiLabel(data, "person_sketch_evidence", readingMode, "人物依据")} ›</summary>
      {evidence.map((item) => {
        const source = story.reading.source_display[item.source_id];
        const quote = story.reading.evidence_display[item.id]?.[readingMode] ?? item.quote;
        return (
          <article key={item.id}>
            <p>{source ? `${source.work[readingMode]} · ${source.edition[readingMode]}` : item.source_id}</p>
            <blockquote>{quote}</blockquote>
          </article>
        );
      })}
    </details>
  );
}

function PersonSketchLifeGlimpse({
  story,
  data,
  focusedPerson,
  readingMode,
}: {
  story: Story;
  data: SiteBundle;
  focusedPerson: Person;
  readingMode: ReadingMode;
}) {
  const sketch = data.person_sketches[focusedPerson.id];
  const points = sketch?.life_glimpse ?? [];
  if (points.length === 0) return null;
  return (
    <section className="person-sketch-life-glimpse" aria-label={uiLabel(data, "person_sketch_life_glimpse", readingMode, "一瞥")}>
      <p className="relation-detail-heading">{uiLabel(data, "person_sketch_life_glimpse", readingMode, "一瞥")}</p>
      <div className="person-sketch-life-list">
        {points.map((point, index) => {
          const evidence = point.evidence_ids
            .map((id) => data.evidence.find((item) => item.id === id))
            .filter((item): item is Evidence => Boolean(item));
          return (
            <article className="person-sketch-life-point" key={`${point.text.original}-${index}`}>
              <p>{readingValue(point.text, readingMode, "")}</p>
              {evidence.length > 0 && (
                <details className="person-sketch-life-evidence">
                  <summary>{uiLabel(data, "person_sketch_evidence", readingMode, "依据")} ›</summary>
                  {evidence.map((item) => (
                    <blockquote key={item.id}>{story.reading.evidence_display[item.id]?.[readingMode] ?? item.quote}</blockquote>
                  ))}
                </details>
              )}
            </article>
          );
        })}
      </div>
    </section>
  );
}

function PersonDetailCard({
  story,
  data,
  focusedPerson,
  perspectives,
  readingMode,
  routeNode,
  onFocus,
  onStorySelect,
}: {
  story: Story;
  data: SiteBundle;
  focusedPerson: Person;
  perspectives: RelationPerspective[];
  readingMode: ReadingMode;
  routeNode: ExplorationNode | null;
  onFocus: PersonFocus;
  onStorySelect: (storyId: string) => void;
}) {
  const derivedRelations = derivedRelationsForPerson(focusedPerson.id, data);
  const sketch = data.person_sketches[focusedPerson.id];
  const storyCounts = sketch?.story_counts;
  return (
    <section className="person-detail-card" aria-labelledby="focused-person-heading">
      <p className="section-label">{story.reading.labels.focused_person_label[readingMode]}</p>
      <h3 id="focused-person-heading">{personDisplayName(story, focusedPerson, readingMode)}</h3>
      <PersonSketchIdentity story={story} data={data} focusedPerson={focusedPerson} readingMode={readingMode} />
      <MentionOriginExplanation
        story={story}
        data={data}
        focusedPerson={focusedPerson}
        routeNode={routeNode}
        readingMode={readingMode}
      />
      <PersonSketchAliasRows story={story} data={data} focusedPerson={focusedPerson} readingMode={readingMode} />
      {storyCounts && (
        <p className="person-sketch-story-summary">
          {storyCounts.main_text} {uiLabel(data, "person_sketch_main_story_count", readingMode, "正文故事")} · {storyCounts.liu_annotation_only} {uiLabel(data, "person_sketch_annotation_story_count", readingMode, "刘注提及")}
        </p>
      )}
      <PersonStories
        data={data}
        focusedPerson={focusedPerson}
        readingMode={readingMode}
        onStorySelect={onStorySelect}
      />
      <PersonSketchLifeGlimpse
        story={story}
        data={data}
        focusedPerson={focusedPerson}
        readingMode={readingMode}
      />
      <div className="relation-detail-group">
        <p className="relation-detail-heading">{uiLabel(data, "person_sketch_relations", readingMode, "人物关系")}</p>
        <p className="relation-detail-subheading">{story.reading.labels.direct_relation_label[readingMode]}</p>
        {perspectives.length === 0 && <p className="relation-empty">{story.reading.labels.no_direct_relations[readingMode]}</p>}
        {perspectives.map((perspective) => (
          <div className="relation-detail-row" key={perspective.relation.id}>
            <button type="button" className="person-link" onClick={() => onFocus(perspective.neighbor.id)}>
              {personDisplayName(story, perspective.neighbor, readingMode)} · {perspectiveNeighborRole(story, perspective, readingMode)}
            </button>
            <RelationEvidence
              relation={perspective.relation}
              story={story}
              data={data}
              readingMode={readingMode}
              perspective={perspective}
            />
          </div>
        ))}
      </div>
      {derivedRelations.length > 0 && (
        <div className="relation-detail-group derived-group">
          <p className="relation-detail-heading">{story.reading.labels.derived_relation_label[readingMode]}</p>
          {derivedRelations.map((relation) => (
            <DerivedRelationDetails key={relation.id} relation={relation} story={story} data={data} readingMode={readingMode} focusedPersonId={focusedPerson.id} />
          ))}
        </div>
      )}
      <PersonSketchEvidence story={story} data={data} focusedPerson={focusedPerson} readingMode={readingMode} />
    </section>
  );
}

function EgoRelationExplorer({
  story,
  data,
  focusedPersonId: focusedId,
  focusedPersonNode,
  readingMode,
  backTarget,
  onFocus,
  onBack,
  onStorySelect,
}: {
  story: Story;
  data: SiteBundle;
  focusedPersonId: string;
  focusedPersonNode: ExplorationNode | null;
  readingMode: ReadingMode;
  backTarget: ExplorationNode | null;
  onFocus: PersonFocus;
  onBack: () => void;
  onStorySelect: (storyId: string) => void;
}) {
  const focusedPerson = data.people.find((person) => person.id === focusedId);
  if (!focusedPerson) return null;
  const perspectives = directRelationPerspectives(focusedPerson.id, data);
  const backLabel = backTarget?.kind === "person"
    ? personNameById(story, data, backTarget.id, readingMode)
    : backTarget?.kind === "story"
      ? storyReference(storyById(data, backTarget.id) ?? story, readingMode)
      : "";
  return (
    <section className="relation-explorer" aria-labelledby="relation-explorer-heading">
      <div className="relation-explorer-header">
        <div>
          <p className="section-label">{story.reading.labels.relation_section[readingMode]}</p>
          <h2 id="relation-explorer-heading">{personDisplayName(story, focusedPerson, readingMode)}</h2>
        </div>
        {backTarget && (
          <button type="button" className="back-button" onClick={onBack}>
            ← {story.reading.labels.back_label[readingMode]} {backLabel}
          </button>
        )}
      </div>
      <div className="relation-explorer-grid">
        <PersonDetailCard
          story={story}
          data={data}
          focusedPerson={focusedPerson}
          perspectives={perspectives}
          readingMode={readingMode}
          routeNode={focusedPersonNode}
          onFocus={onFocus}
          onStorySelect={onStorySelect}
        />
        <EgoRelationMap
          story={story}
          data={data}
          focusedPerson={focusedPerson}
          perspectives={perspectives}
          readingMode={readingMode}
          onFocus={onFocus}
        />
      </div>
    </section>
  );
}

function PersonExplorerPanel({
  story,
  data,
  focusedPersonId,
  focusedPersonNode,
  readingMode,
  backTarget,
  onFocus,
  onBack,
  onStorySelect,
  onClose,
}: {
  story: Story;
  data: SiteBundle;
  focusedPersonId: string | null;
  focusedPersonNode: ExplorationNode | null;
  readingMode: ReadingMode;
  backTarget: ExplorationNode | null;
  onFocus: PersonFocus;
  onBack: () => void;
  onStorySelect: (storyId: string) => void;
  onClose: () => void;
}) {
  if (!focusedPersonId) return null;
  return (
    <aside className="person-panel-shell" aria-label="人物探索">
      <button
        type="button"
        className="person-panel-backdrop"
        aria-label="关闭人物探索"
        onClick={onClose}
      />
      <div className="person-panel-surface" role="dialog" aria-modal="true" aria-labelledby="relation-explorer-heading">
        <div className="person-panel-toolbar">
          <span>人物探索</span>
          <button type="button" className="panel-close-button" onClick={onClose} aria-label="关闭人物探索">
            ×
          </button>
        </div>
        <EgoRelationExplorer
          story={story}
          data={data}
          focusedPersonId={focusedPersonId}
          focusedPersonNode={focusedPersonNode}
          readingMode={readingMode}
          backTarget={backTarget}
          onFocus={onFocus}
          onBack={onBack}
          onStorySelect={onStorySelect}
        />
      </div>
    </aside>
  );
}

function EvidenceDetails({
  story,
  data,
  readingMode,
}: {
  story: Story;
  data: SiteBundle;
  readingMode: ReadingMode;
}) {
  const evidence = story.evidence_ids
    .map((id) => data.evidence.find((item) => item.id === id))
    .filter((item): item is Evidence => Boolean(item));

  return (
    <details className="evidence-details">
      <summary>{story.reading.labels.evidence_heading[readingMode]}</summary>
      <p className="evidence-intro">{story.reading.labels.evidence_intro[readingMode]}</p>
      <div className="evidence-list">
        {evidence.map((item) => (
          <article className="evidence-item" key={item.id}>
            <div className="evidence-heading">
              <span>
                {item.evidence_type}
                {story.reading.source_display[item.source_id] && (
                  <> · {story.reading.source_display[item.source_id].work[readingMode]} · {story.reading.source_display[item.source_id].edition[readingMode]}</>
                )}
              </span>
              <code>{item.id}</code>
            </div>
            <blockquote>{readingValue(story.reading.evidence_display[item.id], readingMode, item.quote)}</blockquote>
            <dl className="provenance-grid">
              <dt>artifact</dt>
              <dd>
                {item.locator.artifact_path} · {item.locator.artifact_sha256.slice(0, 12)}…
              </dd>
              <dt>witness</dt>
              <dd>{item.locator.source_provenance.witness_id}</dd>
              <dt>source</dt>
              <dd>
                {item.locator.source_provenance.source_path} · {item.locator.source_provenance.source_sha256.slice(0, 12)}…
              </dd>
            </dl>
          </article>
        ))}
      </div>
    </details>
  );
}

function SceneCard({
  story,
  data,
  readingMode,
  onFocus,
}: {
  story: Story;
  data: SiteBundle;
  readingMode: ReadingMode;
  onFocus: PersonFocus;
}) {
  const scene: StorySceneContext | undefined = data.scene_contexts[story.id];
  if (!scene) return null;

  const evidence = scene.evidence_ids
    .map((id) => data.evidence.find((item) => item.id === id))
    .filter((item): item is Evidence => Boolean(item));
  const dateLabel = scene.date.status !== "unknown" && scene.date.label
    ? readingValue(scene.date.label, readingMode, "")
    : "";
  const placeLabel = scene.places.map((place) => readingValue(place.name, readingMode, "")).filter(Boolean).join(" · ");
  const narrative = scene.narrative_layers;
  const sceneFocus = narrative?.scene_focus ?? [];
  const offFrameClaims = narrative?.off_frame_context ?? [];
  const groundClaims = narrative?.historical_ground ?? [];
  const resonanceClaims = narrative?.resonance ?? [];
  const inFramePeople = scene.people_at_scene.filter((person) => person.scene_role === "present");
  const offFramePeople = scene.people_at_scene.filter((person) => person.scene_role !== "present");
  const inFrameUnmaterialized = scene.unmaterialized_people.filter((person) => person.scene_role === "present");
  const offFrameUnmaterialized = scene.unmaterialized_people.filter((person) => person.scene_role !== "present");
  const stageClaims: StorySceneContext["event_background"] = sceneFocus.length > 0
    ? sceneFocus
    : scene.positional_context.map((position) => ({
      text: position.text,
      assertion_status: position.assertion_status,
      review_status: position.review_status,
      evidence_ids: position.evidence_ids,
    }));

  function claimList(claims: StorySceneContext["event_background"], className = "scene-context-text") {
    return claims.map((claim, index) => (
      <p className={className} key={`${claim.text.original}-${index}`}>
        {readingValue(claim.text, readingMode, "")}
      </p>
    ));
  }

  function personRows(people: StorySceneContext["people_at_scene"]) {
    return people.map((person) => {
      const resolved = data.people.find((candidate) => candidate.id === person.person_id);
      const name = resolved ? personDisplayName(story, resolved, readingMode) : readingValue(person.surface, readingMode, person.person_id);
      return (
        <article className="scene-person-row" key={`${person.person_id}-${person.surface.original}`}>
          <div className="scene-person-heading">
            <button type="button" className="scene-person-link" onClick={() => onFocus(person.person_id)}>
              {name}
            </button>
            <span className="scene-person-surface">（{readingValue(person.surface, readingMode, "")}）</span>
            <span className="scene-person-role">{readingValue(person.scene_role_label, readingMode, person.scene_role)}</span>
          </div>
          <div className="scene-person-details">
            {person.age.status !== "unknown" && person.age.label && (
              <span>{readingValue(person.age.label, readingMode, "")}</span>
            )}
            {person.status && <span>{readingValue(person.status.text, readingMode, "")}</span>}
          </div>
        </article>
      );
    });
  }

  function unmaterializedRows(people: StorySceneContext["unmaterialized_people"]) {
    return people.map((person, index) => (
      <p key={`${person.surface.original}-${index}`} className="scene-unmaterialized-person">
        {readingValue(person.surface, readingMode, "")} · {readingValue(person.scene_role_label, readingMode, person.scene_role)}
      </p>
    ));
  }

  return (
    <section className="scene-card" aria-labelledby={`scene-heading-${story.id}`}>
      <div className="scene-card-header">
        <div>
          <h2 id={`scene-heading-${story.id}`}>{uiLabel(data, "scene_heading", readingMode, "舞台")}</h2>
        </div>
      </div>
      {(dateLabel || placeLabel) && (
        <p className="scene-date-place">{[dateLabel, placeLabel].filter(Boolean).join(" · ")}</p>
      )}

      {stageClaims.length > 0 && (
        <div className="scene-context-group scene-stage-group">
          {claimList(stageClaims)}
        </div>
      )}

      {(inFramePeople.length > 0 || inFrameUnmaterialized.length > 0) && (
        <div className="scene-people" aria-labelledby={`scene-people-heading-${story.id}`}>
          <p className="scene-card-label" id={`scene-people-heading-${story.id}`}>{uiLabel(data, "scene_people_heading", readingMode, "入画")}</p>
          <div className="scene-person-list">
            {personRows(inFramePeople)}
          </div>
          {inFrameUnmaterialized.length > 0 && (
            <div className="scene-unmaterialized-people">
              <p className="scene-card-label">{uiLabel(data, "scene_not_materialized", readingMode, "人物卡尚未建立")}</p>
              {unmaterializedRows(inFrameUnmaterialized)}
            </div>
          )}
        </div>
      )}

      {(offFramePeople.length > 0 || offFrameUnmaterialized.length > 0 || offFrameClaims.length > 0) && (
        <div className="scene-context-group">
          <p className="scene-card-label">{uiLabel(data, "scene_off_frame_heading", readingMode, "画外")}</p>
          {claimList(offFrameClaims)}
          <div className="scene-person-list">{personRows(offFramePeople)}</div>
          {offFrameUnmaterialized.length > 0 && <div className="scene-unmaterialized-people">{unmaterializedRows(offFrameUnmaterialized)}</div>}
        </div>
      )}

      {groundClaims.length > 0 && (
        <div className="scene-context-group">
          <p className="scene-card-label">{uiLabel(data, "scene_ground_heading", readingMode, "底色")}</p>
          {claimList(groundClaims)}
        </div>
      )}

      {resonanceClaims.length > 0 && (
        <div className="scene-context-group scene-resonance-group">
          <p className="scene-card-label">{uiLabel(data, "scene_resonance_heading", readingMode, "余韵")}</p>
          {claimList(resonanceClaims)}
        </div>
      )}

      {evidence.length > 0 && (
        <details className="scene-evidence">
          <summary>{uiLabel(data, "scene_evidence_heading", readingMode, "查看依据")} ›</summary>
          {evidence.map((item) => {
            const source = story.reading.source_display[item.source_id];
            return (
              <article key={item.id}>
                <p>{source ? `${source.work[readingMode]} · ${source.edition[readingMode]}` : item.source_id}</p>
                <blockquote>{readingValue(story.reading.evidence_display[item.id], readingMode, item.quote)}</blockquote>
              </article>
            );
          })}
        </details>
      )}
    </section>
  );
}

function nodeLabel(node: ExplorationNode, story: Story, data: SiteBundle, mode: ReadingMode): string {
  if (node.kind === "story") {
    return storyReference(storyById(data, node.id) ?? story, mode);
  }
  return personNameById(story, data, node.id, mode);
}

function ExplorationPath({
  stack,
  story,
  data,
  readingMode,
  onSelect,
}: {
  stack: ExplorationNode[];
  story: Story;
  data: SiteBundle;
  readingMode: ReadingMode;
  onSelect: (index: number) => void;
}) {
  const [menuOpen, setMenuOpen] = useState(false);
  if (stack.length <= 1) return null;
  const compact = stack.length > 4;
  const visible = compact
    ? [
        { node: stack[0], index: 0 },
        { node: null, index: -1 },
        ...stack.slice(-2).map((node, offset) => ({ node, index: stack.length - 2 + offset })),
      ]
    : stack.map((node, index) => ({ node, index }));
  const previous = stack[stack.length - 2];
  if (!previous) return null;

  function select(index: number) {
    setMenuOpen(false);
    onSelect(index);
  }

  return (
    <div className="exploration-path-shell">
      <nav className="exploration-breadcrumb desktop-path" aria-label="探索路径">
        {visible.map((item, visibleIndex) => (
          <span key={`${item.index}-${visibleIndex}`}>
            {visibleIndex > 0 && <span aria-hidden="true"> › </span>}
            {item.node ? (
              <button
                type="button"
                className="path-item"
                aria-current={item.index === stack.length - 1 ? "page" : undefined}
                onClick={() => select(item.index)}
              >
                {nodeLabel(item.node, story, data, readingMode)}
              </button>
            ) : (
              <button
                type="button"
                className="path-ellipsis"
                aria-label="显示完整探索路径"
                aria-expanded={menuOpen}
                onClick={() => setMenuOpen((current) => !current)}
              >
                …
              </button>
            )}
          </span>
        ))}
      </nav>
      <div className="mobile-path-bar">
        <button type="button" className="mobile-path-back" onClick={() => select(stack.length - 2)}>
          ← {nodeLabel(previous, story, data, readingMode)}
        </button>
        <button
          type="button"
          className="mobile-path-menu-button"
          aria-label="打开探索路径"
          aria-expanded={menuOpen}
          onClick={() => setMenuOpen((current) => !current)}
        >
          ···
        </button>
      </div>
      {menuOpen && (
        <div className="path-menu" role="menu" aria-label="探索路径">
          <p className="path-menu-heading">探索路径</p>
          {stack.map((node, index) => (
            <button
              type="button"
              role="menuitem"
              className="path-menu-item"
              key={`${node.kind}-${node.id}-${index}`}
              onClick={() => select(index)}
            >
              {nodeLabel(node, story, data, readingMode)}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

function StoryReader({
  story,
  data,
  readingMode,
  setReadingMode,
  focusedPersonId,
  onFocus,
}: {
  story: Story;
  data: SiteBundle;
  readingMode: ReadingMode;
  setReadingMode: (mode: ReadingMode) => void;
  focusedPersonId: string | null;
  onFocus: PersonFocus;
}) {
  const readerRef = useRef<HTMLDivElement>(null);
  const [openAnnotationIds, setOpenAnnotationIds] = useState<Set<string>>(() => new Set());
  const mentions = resolvedMentions(story, data);
  const mainTextMentions = mentions.filter((mention) => mention.section === "main_text");
  const annotationMentions = mentions.filter((mention) => mention.section === "liu_annotation");

  useEffect(() => {
    setOpenAnnotationIds(new Set());
    const reader = readerRef.current;
    if (!reader) return;
    reader.scrollTop = 0;
    reader.scrollIntoView({ behavior: "auto", block: "start" });
  }, [story.id]);

  function toggleAnnotation(annotationId: string): void {
    setOpenAnnotationIds((current) => {
      const next = new Set(current);
      if (next.has(annotationId)) next.delete(annotationId);
      else next.add(annotationId);
      return next;
    });
  }

  return (
    <div className="story-reader-stage" ref={readerRef} tabIndex={-1} aria-labelledby="story-heading">
      <article className="reading-column">
        <p className="story-reference">{storyReference(story, readingMode)}</p>
        <h1 id="story-heading">{storyHeading(story, readingMode)}</h1>
        {(story.temporal_orientation ?? story.period_label) && (
          <p className="story-period-label">{readingValue(story.temporal_orientation ?? story.period_label, readingMode, "")}</p>
        )}
        <p className="story-meta">{story.id}</p>

        <div className="story-reading-toolbar">
          <div className="reading-controls" role="group" aria-label="阅读模式">
            <button
              type="button"
              className={readingMode === "simplified" ? "reading-mode-button active" : "reading-mode-button"}
              aria-pressed={readingMode === "simplified"}
              onClick={() => setReadingMode("simplified")}
            >
              简体阅读
            </button>
            <span className="reading-mode-separator" aria-hidden="true">|</span>
            <button
              type="button"
              className={readingMode === "original" ? "reading-mode-button active" : "reading-mode-button"}
              aria-pressed={readingMode === "original"}
              onClick={() => setReadingMode("original")}
            >
              原文
            </button>
          </div>
          <p className={story.publication_state === "preview_ready" ? "publication-note preview" : "publication-note"}>
            {story.publication_state === "preview_ready"
              ? uiLabel(data, "preview_punctuation", readingMode, "句读：参考底本整理 · 待复核")
              : uiLabel(data, "reviewed_punctuation", readingMode, "句读：已复核")}
          </p>
        </div>

        <section className="story-panel" aria-label="故事正文">
          <p className="story-text">
            <InlineReadingSegments
              segments={story.reading.main_text.segments}
              story={story}
              data={data}
              readingMode={readingMode}
              focusedPersonId={focusedPersonId}
              onFocus={onFocus}
              annotations={story.reading.annotations}
              openAnnotationIds={openAnnotationIds}
              onToggleAnnotation={toggleAnnotation}
            />
          </p>
        </section>

        <SceneCard story={story} data={data} readingMode={readingMode} onFocus={onFocus} />

        <section className="annotation-hook" aria-label="进一步读">
          <p className="section-label">进一步读</p>
          <details className="annotation-index">
            <summary>
              {readingValue(story.reading.labels.annotation_label, readingMode, "刘孝标注")} · {story.reading.annotations.length}条
            </summary>
            <div className="annotation-index-list">
              {story.reading.annotations.map((annotation) => (
                <details className="annotation-panel" key={annotation.id}>
                  <summary>
                    {annotation.insertion.status === "safe" ? `〔注${annotation.insertion.label}〕` : "未定位注释"}
                    {annotation.punctuation_status === "unavailable" && <span className="annotation-index-status"> · 原文</span>}
                  </summary>
                  <p className="annotation-text">
                    <InlineReadingSegments
                      segments={annotation.segments}
                      story={story}
                      data={data}
                      readingMode={readingMode}
                      focusedPersonId={focusedPersonId}
                      onFocus={onFocus}
                      annotations={story.reading.annotations}
                      openAnnotationIds={openAnnotationIds}
                      onToggleAnnotation={toggleAnnotation}
                      showAnnotationMarkers={false}
                    />
                  </p>
                </details>
              ))}
            </div>
          </details>
        </section>

        <section className="people-section" aria-labelledby="people-heading" aria-label={story.reading.labels.people_section[readingMode]}>
          <div className="section-heading">
            <p className="section-label">{story.reading.labels.people_section[readingMode]}</p>
            <h2 id="people-heading">{uiLabel(data, "story_people_heading", readingMode, "本则人物")}</h2>
          </div>
          <div className="mention-summary" aria-label={uiLabel(data, "story_people_heading", readingMode, "本则人物")}>
            <MentionSummaryGroup
              label={uiLabel(data, "primary_story_label", readingMode, "正文出现")}
              mentions={mainTextMentions}
              story={story}
              data={data}
              readingMode={readingMode}
              onFocus={onFocus}
            />
            <MentionSummaryGroup
              label={uiLabel(data, "annotation_story_label", readingMode, "刘注提及")}
              mentions={annotationMentions}
              story={story}
              data={data}
              readingMode={readingMode}
              onFocus={onFocus}
            />
          </div>
        </section>

        <EvidenceDetails story={story} data={data} readingMode={readingMode} />
      </article>
    </div>
  );
}

function ReadingPage({
  story,
  data,
  readingMode,
  setReadingMode,
  stack,
  focusedPersonId,
  focusedPersonNode,
  personPanelOpen,
  onFocus,
  onBack,
  onStorySelect,
  onPathSelect,
  onClosePerson,
  onRandomPerson,
  onRandomStory,
}: {
  story: Story;
  data: SiteBundle;
  readingMode: ReadingMode;
  setReadingMode: (mode: ReadingMode) => void;
  stack: ExplorationNode[];
  focusedPersonId: string | null;
  focusedPersonNode: ExplorationNode | null;
  personPanelOpen: boolean;
  onFocus: PersonFocus;
  onBack: () => void;
  onStorySelect: (storyId: string) => void;
  onPathSelect: (index: number) => void;
  onClosePerson: () => void;
  onRandomPerson: () => void;
  onRandomStory: () => void;
}) {
  const backTarget = focusedPersonId && stack.length > 1 ? stack[stack.length - 2] ?? null : null;
  useEffect(() => {
    window.localStorage.setItem(READING_MODE_STORAGE_KEY, readingMode);
  }, [readingMode]);

  return (
    <main className="page-shell">
      <header className="site-header">
        <div>
          <p className="brand">世说Sketch</p>
          <p className="tagline">从一则故事，走进魏晋</p>
        </div>
        <div className="site-header-actions">
          <button type="button" className="random-story-button" onClick={onRandomStory}>
            {uiLabel(data, "random_story", readingMode, "随便读一则")}
          </button>
          <button type="button" className="random-person-button" onClick={onRandomPerson}>
            {uiLabel(data, "random_person", readingMode, "随便认识一个人")}
          </button>
          <span className="prototype-badge">SC1 Preview</span>
        </div>
      </header>

      <ExplorationPath
        stack={stack}
        story={story}
        data={data}
        readingMode={readingMode}
        onSelect={onPathSelect}
      />

      <div className={personPanelOpen ? "exploration-layout with-person-panel" : "exploration-layout"}>
        <StoryReader
          key={story.id}
          story={story}
          data={data}
          readingMode={readingMode}
          setReadingMode={setReadingMode}
          focusedPersonId={focusedPersonId}
          onFocus={onFocus}
        />
        {personPanelOpen && focusedPersonId && (
          <PersonExplorerPanel
            story={story}
            data={data}
            focusedPersonId={focusedPersonId}
            focusedPersonNode={focusedPersonNode}
            readingMode={readingMode}
            backTarget={backTarget}
            onFocus={onFocus}
            onBack={onBack}
            onStorySelect={onStorySelect}
            onClose={onClosePerson}
          />
        )}
      </div>

      <footer className="site-footer">
        <span>static-first · {data.generated_from}</span>
        <span>{story.publication_state}</span>
      </footer>
    </main>
  );
}

function App() {
  const [data, setData] = useState<SiteBundle | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [readingMode, setReadingMode] = useState<ReadingMode>(initialReadingMode);
  const [stack, setStack] = useState<ExplorationNode[]>([]);
  const [personPanelOpen, setPersonPanelOpen] = useState(false);
  const initialized = useRef(false);

  useEffect(() => {
    if (initialized.current) return;
    initialized.current = true;
    try {
      const loaded = loadSiteBundle();
      const storyId = initialStoryId(loaded);
      setData(loaded);
      setStack([{ kind: "story", id: storyId }]);
      writeStoryAddress(storyId);
    } catch (reason: unknown) {
      setError(reason instanceof Error ? reason.message : String(reason));
    }
  }, []);

  const story = useMemo(() => {
    if (!data || stack.length === 0) return undefined;
    const storyId = currentStoryFromExploration(stack);
    return storyId ? storyById(data, storyId) : undefined;
  }, [data, stack]);
  const currentFocusedPersonId = focusedPersonFromExploration(stack);
  const currentFocusedPersonNode = focusedPersonNodeFromExploration(stack);

  function focusPerson(personId: string, route?: PersonMentionRoute) {
    if (!data?.people.some((person) => person.id === personId)) return;
    setStack((current) => appendExploration(current, {
      kind: "person",
      id: personId,
      ...(route ?? {}),
    }));
    setPersonPanelOpen(true);
  }

  function selectStory(storyId: string) {
    if (!data?.stories.some((candidate) => candidate.id === storyId)) return;
    const next = appendExploration(stack, { kind: "story", id: storyId });
    setStack(next);
    setPersonPanelOpen(false);
    writeStoryAddress(storyId);
  }

  function goBack() {
    const next = backExploration(stack);
    setStack(next);
    setPersonPanelOpen(next[next.length - 1]?.kind === "person");
    const storyId = currentStoryFromExploration(next);
    if (storyId) writeStoryAddress(storyId);
  }

  function selectPath(index: number) {
    const next = truncateExploration(stack, index);
    setStack(next);
    setPersonPanelOpen(next[next.length - 1]?.kind === "person");
    const storyId = currentStoryFromExploration(next);
    if (storyId) writeStoryAddress(storyId);
  }

  function chooseRandomStory() {
    if (!data) return;
    const storyId = randomPublishedStoryId(data, Math.random, currentStoryFromExploration(stack) ?? undefined);
    if (!storyId) return;
    setStack([{ kind: "story", id: storyId }]);
    setPersonPanelOpen(false);
    writeStoryAddress(storyId);
  }

  function chooseRandomPerson() {
    if (!data) return;
    const personId = randomEligiblePersonId(data, Math.random, currentFocusedPersonId ?? undefined);
    if (!personId) return;
    const storyId = randomPublishedStoryIdForPerson(
      data,
      personId,
      Math.random,
      currentStoryFromExploration(stack) ?? undefined,
    );
    if (!storyId) return;
    setStack([
      { kind: "story", id: storyId },
      { kind: "person", id: personId },
    ]);
    setPersonPanelOpen(true);
    writeStoryAddress(storyId);
  }

  if (error) {
    return (
      <main className="page-shell">
        <section className="error-panel">
          <p className="brand">世说Sketch</p>
          <h1>静态数据加载失败</h1>
          <p>{error}</p>
        </section>
      </main>
    );
  }
  if (!data || !story) {
    return (
      <main className="page-shell loading-state">
        <p className="brand">世说Sketch</p>
        <p>正在读取故事……</p>
      </main>
    );
  }
  return (
    <ReadingPage
      story={story}
      data={data}
      readingMode={readingMode}
      setReadingMode={setReadingMode}
      stack={stack}
      focusedPersonId={currentFocusedPersonId}
      focusedPersonNode={currentFocusedPersonNode}
      personPanelOpen={personPanelOpen}
      onFocus={focusPerson}
      onBack={goBack}
      onStorySelect={selectStory}
      onPathSelect={selectPath}
      onClosePerson={() => setPersonPanelOpen(false)}
      onRandomPerson={chooseRandomPerson}
      onRandomStory={chooseRandomStory}
    />
  );
}

export default App;
