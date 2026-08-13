import { useEffect, useMemo, useState } from "react";
import { loadSiteBundle } from "./data";
import {
  derivedPath,
  derivedRelationsForPerson,
  directRelationPerspectives,
  egoLayout,
  appendExploration,
  backExploration,
  currentStoryFromExploration,
  pathPersonIds,
  focusedPersonFromExploration,
  type RelationPerspective,
  type ExplorationNode,
} from "./relationExplorer";
import type {
  Evidence,
  Mention,
  Person,
  ReadingPair,
  Relation,
  SiteBundle,
  Story,
} from "./types";

const DEFAULT_STORY_ID = "06-yaliang-019";
const READING_MODE_STORAGE_KEY = "shishuoSketch.reading-mode";
type ReadingMode = "simplified" | "original";

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
  key: "person_stories_heading" | "primary_story_label" | "annotation_story_label" | "read_story" | "reviewed_punctuation" | "preview_punctuation",
  mode: ReadingMode,
  fallback: string,
): string {
  return readingValue(data.ui?.[key], mode, fallback);
}

function resolvedMentions(story: Story, data: SiteBundle): Mention[] {
  return story.mention_ids
    .map((id) => data.mentions.find((mention) => mention.id === id))
    .filter((mention): mention is Mention => Boolean(mention?.person_id));
}

function personMentions(story: Story, person: Person, data: SiteBundle): Mention[] {
  return resolvedMentions(story, data).filter((mention) => mention.person_id === person.id);
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

function storyExcerpt(story: Story, mode: ReadingMode): string {
  const text = story.reading.main_text[mode].replace(/\s+/gu, "");
  return text.length > 54 ? `${text.slice(0, 54)}……` : text;
}

function PersonCard({
  person,
  mentions,
  story,
  readingMode,
  focused,
  onFocus,
}: {
  person: Person;
  mentions: Mention[];
  story: Story;
  readingMode: ReadingMode;
  focused: boolean;
  onFocus: () => void;
}) {
  const surfaces = Array.from(
    new Set(
      mentions.map((mention) =>
        readingValue(story.reading.mention_display[mention.id]?.surface, readingMode, mention.surface),
      ),
    ),
  );
  const labels = story.reading.labels;
  return (
    <button
      type="button"
      className={focused ? "person-card focused" : "person-card"}
      aria-pressed={focused}
      onClick={onFocus}
    >
      <span className="person-card-heading">
        <span className="person-name">{personDisplayName(story, person, readingMode)}</span>
        <span className="person-hint">{labels.alias_hint[readingMode]}</span>
      </span>
      <span className="person-card-body">
        <span className="person-label">{labels.resolved_alias_label[readingMode]}</span>
        <span className="surface-list">{surfaces.join("、") || labels.empty_alias[readingMode]}</span>
        <span className="person-status">
          {person.assertion_status} · {person.review_status}
        </span>
      </span>
    </button>
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
  const sourceLocations = [
    ...(relation.source_entry_ids ?? []).map((id) => `entry · ${id}`),
    ...(relation.source_unit_ids ?? []).map((id) => `unit · ${id}`),
  ];

  return (
    <details className="relation-evidence">
      <summary>
        <span>{neighborName} · {neighborRole}</span>
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
  onFocus: (personId: string) => void;
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
      <p className="relation-detail-heading">{uiLabel(data, "person_stories_heading", readingMode, "《世說》中的故事")}</p>
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

function PersonDetailCard({
  story,
  data,
  focusedPerson,
  perspectives,
  readingMode,
  onFocus,
  onStorySelect,
}: {
  story: Story;
  data: SiteBundle;
  focusedPerson: Person;
  perspectives: RelationPerspective[];
  readingMode: ReadingMode;
  onFocus: (personId: string) => void;
  onStorySelect: (storyId: string) => void;
}) {
  const aliases = story.reading.person_display[focusedPerson.id]?.aliases ?? [];
  const derivedRelations = derivedRelationsForPerson(focusedPerson.id, data);
  return (
    <section className="person-detail-card" aria-labelledby="focused-person-heading">
      <p className="section-label">{story.reading.labels.focused_person_label[readingMode]}</p>
      <h3 id="focused-person-heading">{personDisplayName(story, focusedPerson, readingMode)}</h3>
      <p className="person-detail-aliases">
        {aliases.length ? aliases.map((alias) => readingValue(alias.surface, readingMode, "")).join("、") : story.reading.labels.empty_alias[readingMode]}
      </p>
      <div className="relation-detail-group">
        <p className="relation-detail-heading">{story.reading.labels.direct_relation_label[readingMode]}</p>
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
      <PersonStories
        data={data}
        focusedPerson={focusedPerson}
        readingMode={readingMode}
        onStorySelect={onStorySelect}
      />
    </section>
  );
}

function EgoRelationExplorer({
  story,
  data,
  focusedPersonId: focusedId,
  readingMode,
  backTarget,
  onFocus,
  onBack,
  onStorySelect,
}: {
  story: Story;
  data: SiteBundle;
  focusedPersonId: string;
  readingMode: ReadingMode;
  backTarget: ExplorationNode | null;
  onFocus: (personId: string) => void;
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

function nodeLabel(node: ExplorationNode, story: Story, data: SiteBundle, mode: ReadingMode): string {
  if (node.kind === "story") {
    return storyReference(storyById(data, node.id) ?? story, mode);
  }
  return personNameById(story, data, node.id, mode);
}

function ReadingPage({
  story,
  data,
  readingMode,
  setReadingMode,
  stack,
  focusedPersonId: focusedId,
  onFocus,
  onBack,
  onStorySelect,
}: {
  story: Story;
  data: SiteBundle;
  readingMode: ReadingMode;
  setReadingMode: (mode: ReadingMode) => void;
  stack: ExplorationNode[];
  focusedPersonId: string | null;
  onFocus: (personId: string) => void;
  onBack: () => void;
  onStorySelect: (storyId: string) => void;
}) {
  const people = story.person_ids
    .map((id) => data.people.find((person) => person.id === id))
    .filter((person): person is Person => Boolean(person));
  const mentions = resolvedMentions(story, data);
  const readingText = story.reading.main_text[readingMode];
  const annotationReading = story.reading.annotations[0];
  const backTarget = focusedId && stack.length > 1
    ? [...stack.slice(0, -1)].reverse().find((node) => node.kind === "person") ?? stack[stack.length - 2] ?? null
    : null;

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
        <span className="prototype-badge">SC1 Preview</span>
      </header>

      {stack.length > 1 && (
        <nav className="exploration-breadcrumb" aria-label="探索路径">
          {stack.map((node, index) => (
            <span key={`${node.kind}-${node.id}-${index}`}>
              {index > 0 && <span aria-hidden="true"> › </span>}
              {nodeLabel(node, story, data, readingMode)}
            </span>
          ))}
        </nav>
      )}

      <article className="reading-column">
        <p className="story-reference">{storyReference(story, readingMode)}</p>
        <h1>{storyHeading(story, readingMode)}</h1>
        <p className="story-meta">{story.id}</p>

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

        <section className="story-panel" aria-label="故事正文">
          <p className="story-text">{readingText}</p>
        </section>

        {annotationReading && (
          <section className="annotation-panel" key={annotationReading.id}>
            <p className="section-label">{story.reading.labels.annotation_label[readingMode]}</p>
            <p className="annotation-text">{annotationReading[readingMode]}</p>
          </section>
        )}

        <section className="people-section" aria-labelledby="people-heading" aria-label={story.reading.labels.people_section[readingMode]}>
          <div className="section-heading">
            <p className="section-label">{story.reading.labels.people_section[readingMode]}</p>
            <h2 id="people-heading">{story.reading.labels.resolved_mentions_heading[readingMode]}</h2>
          </div>
          <div className="people-grid">
            {people.map((person) => (
              <PersonCard
                key={person.id}
                person={person}
                mentions={personMentions(story, person, data)}
                story={story}
                readingMode={readingMode}
                focused={focusedId === person.id}
                onFocus={() => onFocus(person.id)}
              />
            ))}
          </div>
          <div className="mention-strip" aria-label={story.reading.labels.resolved_mentions_heading[readingMode]}>
            {mentions.map((mention) => (
              <button className="mention-chip" type="button" key={mention.id} onClick={() => mention.person_id && onFocus(mention.person_id)} disabled={!mention.person_id}>
                {readingValue(story.reading.mention_display[mention.id]?.surface, readingMode, mention.surface)}
                {" → "}
                {mentionPersonDisplayName(story, data, mention, readingMode)}
              </button>
            ))}
          </div>
        </section>

        {focusedId && (
          <EgoRelationExplorer
            story={story}
            data={data}
            focusedPersonId={focusedId}
            readingMode={readingMode}
            backTarget={backTarget}
            onFocus={onFocus}
            onBack={onBack}
            onStorySelect={onStorySelect}
          />
        )}

        <EvidenceDetails story={story} data={data} readingMode={readingMode} />
      </article>

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
  const [stack, setStack] = useState<ExplorationNode[]>([{ kind: "story", id: DEFAULT_STORY_ID }]);

  useEffect(() => {
    try {
      setData(loadSiteBundle());
    } catch (reason: unknown) {
      setError(reason instanceof Error ? reason.message : String(reason));
    }
  }, []);

  const story = useMemo(() => {
    if (!data) return undefined;
    return storyById(data, currentStoryFromExploration(stack) ?? DEFAULT_STORY_ID) ?? data.stories[0];
  }, [data, stack]);
  const currentFocusedPersonId = focusedPersonFromExploration(stack);

  function focusPerson(personId: string) {
    if (!data?.people.some((person) => person.id === personId)) return;
    setStack((current) => appendExploration(current, { kind: "person", id: personId }));
  }

  function selectStory(storyId: string) {
    if (!data?.stories.some((candidate) => candidate.id === storyId)) return;
    setStack((current) => appendExploration(current, { kind: "story", id: storyId }));
  }

  function goBack() {
    setStack((current) => backExploration(current));
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
      onFocus={focusPerson}
      onBack={goBack}
      onStorySelect={selectStory}
    />
  );
}

export default App;
