import { useEffect, useMemo, useState } from "react";
import { loadSiteBundle } from "./data";
import {
  derivedPath,
  derivedRelationsForPerson,
  directRelationPerspectives,
  egoLayout,
  backHistory,
  focusHistory,
  pathPersonIds,
  type RelationPerspective,
} from "./relationExplorer";
import type { Evidence, Mention, Person, ReadingPair, Relation, SiteBundle, Story } from "./types";

const STORY_ID = "06-yaliang-019";
const READING_MODE_STORAGE_KEY = "shishuoSketch.reading-mode";
type ReadingMode = "simplified" | "original";

function initialReadingMode(): ReadingMode {
  if (typeof window === "undefined") return "simplified";
  const stored = window.localStorage.getItem(READING_MODE_STORAGE_KEY);
  return stored === "original" ? "original" : "simplified";
}

function storyReference(story: Story): string {
  const parts = story.id.split("-");
  const ordinal = parts[parts.length - 1] ?? "";
  const chapter = parts[1] === "yaliang" ? "雅量" : parts[1] ?? "";
  return `${chapter} · ${ordinal}`;
}

function resolvedMentions(story: Story, data: SiteBundle): Mention[] {
  return story.mention_ids
    .map((id) => data.mentions.find((mention) => mention.id === id))
    .filter((mention): mention is Mention => Boolean(mention?.person_id));
}

function personMentions(story: Story, person: Person, data: SiteBundle): Mention[] {
  return resolvedMentions(story, data).filter((mention) => mention.person_id === person.id);
}

function readingValue(pair: ReadingPair | undefined, mode: ReadingMode, fallback: string): string {
  return pair?.[mode] ?? fallback;
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
        readingValue(
          story.reading.mention_display[mention.id]?.surface,
          readingMode,
          mention.surface,
        ),
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

function PersonDetailCard({
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
  const aliases = story.reading.person_display[focusedPerson.id]?.aliases ?? [];
  const directRelations = perspectives;
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
        {directRelations.length === 0 && <p className="relation-empty">{story.reading.labels.no_direct_relations[readingMode]}</p>}
        {directRelations.map((perspective) => (
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
    </section>
  );
}

function RelationExplorer({
  story,
  data,
  focusedPersonId,
  readingMode,
  history,
  onFocus,
  onBack,
}: {
  story: Story;
  data: SiteBundle;
  focusedPersonId: string;
  readingMode: ReadingMode;
  history: string[];
  onFocus: (personId: string) => void;
  onBack: () => void;
}) {
  const focusedPerson = data.people.find((person) => person.id === focusedPersonId);
  if (!focusedPerson) return null;
  const perspectives = directRelationPerspectives(focusedPerson.id, data);
  const previousPersonId = history[history.length - 2];
  return (
    <section className="relation-explorer" aria-labelledby="relation-explorer-heading">
      <div className="relation-explorer-header">
        <div>
          <p className="section-label">{story.reading.labels.relation_section[readingMode]}</p>
          <h2 id="relation-explorer-heading">{personDisplayName(story, focusedPerson, readingMode)}</h2>
        </div>
        {previousPersonId && (
          <button type="button" className="back-button" onClick={onBack}>
            ← {story.reading.labels.back_label[readingMode]} {personNameById(story, data, previousPersonId, readingMode)}
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

function ReadingPage({ story, data }: { story: Story; data: SiteBundle }) {
  const [readingMode, setReadingMode] = useState<ReadingMode>(initialReadingMode);
  const [focusedPersonId, setFocusedPersonId] = useState<string | null>(null);
  const [personHistory, setPersonHistory] = useState<string[]>([]);
  const people = story.person_ids
    .map((id) => data.people.find((person) => person.id === id))
    .filter((person): person is Person => Boolean(person));
  const mentions = resolvedMentions(story, data);
  const readingText = story.reading.main_text[readingMode];
  const annotationReading = story.reading.annotations[0];

  useEffect(() => {
    window.localStorage.setItem(READING_MODE_STORAGE_KEY, readingMode);
  }, [readingMode]);

  function focusPerson(personId: string) {
    if (!data.people.some((person) => person.id === personId)) return;
    setFocusedPersonId(personId);
    setPersonHistory((history) => focusHistory(history, personId));
  }

  function goBack() {
    setPersonHistory((history) => {
      const result = backHistory(history);
      setFocusedPersonId(result.focusedId);
      return result.history;
    });
  }

  return (
    <main className="page-shell">
      <header className="site-header">
        <div>
          <p className="brand">世说Sketch</p>
          <p className="tagline">从一则故事，走进魏晋</p>
        </div>
        <span className="prototype-badge">WP1 Prototype</span>
      </header>

      <article className="reading-column">
        <p className="story-reference">{storyReference(story)}</p>
        <h1>{story.title}</h1>
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
                focused={focusedPersonId === person.id}
                onFocus={() => focusPerson(person.id)}
              />
            ))}
          </div>
          <div className="mention-strip" aria-label={story.reading.labels.resolved_mentions_heading[readingMode]}>
            {mentions.map((mention) => (
              <button className="mention-chip" type="button" key={mention.id} onClick={() => mention.person_id && focusPerson(mention.person_id)} disabled={!mention.person_id}>
                {readingValue(story.reading.mention_display[mention.id]?.surface, readingMode, mention.surface)}
                {" → "}
                {mentionPersonDisplayName(story, data, mention, readingMode)}
              </button>
            ))}
          </div>
        </section>

        {focusedPersonId && (
          <RelationExplorer
            story={story}
            data={data}
            focusedPersonId={focusedPersonId}
            readingMode={readingMode}
            history={personHistory}
            onFocus={focusPerson}
            onBack={goBack}
          />
        )}

        <EvidenceDetails story={story} data={data} readingMode={readingMode} />
      </article>

      <footer className="site-footer">
        <span>static-first · {data.generated_from}</span>
        <span>{story.review_status}</span>
      </footer>
    </main>
  );
}

function App() {
  const [data, setData] = useState<SiteBundle | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    try {
      setData(loadSiteBundle());
    } catch (reason: unknown) {
      setError(reason instanceof Error ? reason.message : String(reason));
    }
  }, []);

  const story = useMemo(
    () => data?.stories.find((item) => item.id === STORY_ID) ?? data?.stories[0],
    [data],
  );

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
  return <ReadingPage story={story} data={data} />;
}

export default App;
