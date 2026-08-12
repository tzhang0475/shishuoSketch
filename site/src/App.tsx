import { useEffect, useMemo, useState } from "react";
import { loadSiteBundle } from "./data";
import type { Evidence, Mention, Person, ReadingPair, SiteBundle, Story } from "./types";

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

function PersonCard({
  person,
  mentions,
  story,
  readingMode,
}: {
  person: Person;
  mentions: Mention[];
  story: Story;
  readingMode: ReadingMode;
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
    <details className="person-card">
      <summary>
        <span className="person-name">{personDisplayName(story, person, readingMode)}</span>
        <span className="person-hint">{labels.alias_hint[readingMode]}</span>
      </summary>
      <div className="person-card-body">
        <p className="person-label">{labels.resolved_alias_label[readingMode]}</p>
        <p className="surface-list">{surfaces.join("、") || labels.empty_alias[readingMode]}</p>
        <p className="person-status">
          {person.assertion_status} · {person.review_status}
        </p>
      </div>
    </details>
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
            <blockquote>{item.quote}</blockquote>
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
  const people = story.person_ids
    .map((id) => data.people.find((person) => person.id === id))
    .filter((person): person is Person => Boolean(person));
  const mentions = resolvedMentions(story, data);
  const readingText = story.reading.main_text[readingMode];
  const annotationReading = story.reading.annotations[0];

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
              />
            ))}
          </div>
          <div className="mention-strip" aria-label={story.reading.labels.resolved_mentions_heading[readingMode]}>
            {mentions.map((mention) => (
              <span className="mention-chip" key={mention.id}>
                {readingValue(story.reading.mention_display[mention.id]?.surface, readingMode, mention.surface)}
                {" → "}
                {mentionPersonDisplayName(story, data, mention, readingMode)}
              </span>
            ))}
          </div>
        </section>

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
    loadSiteBundle()
      .then(setData)
      .catch((reason: unknown) => setError(reason instanceof Error ? reason.message : String(reason)));
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
