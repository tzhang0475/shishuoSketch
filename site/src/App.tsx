import { useEffect, useMemo, useState } from "react";
import { loadSiteBundle } from "./data";
import type { Evidence, Mention, Person, SiteBundle, Story } from "./types";

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

function PersonCard({ person, mentions }: { person: Person; mentions: Mention[] }) {
  const surfaces = Array.from(new Set(mentions.map((mention) => mention.surface)));
  return (
    <details className="person-card">
      <summary>
        <span className="person-name">{person.canonical_name}</span>
        <span className="person-hint">查看称谓</span>
      </summary>
      <div className="person-card-body">
        <p className="person-label">本则中已解析的称谓</p>
        <p className="surface-list">{surfaces.join("、") || "—"}</p>
        <p className="person-status">
          {person.assertion_status} · {person.review_status}
        </p>
      </div>
    </details>
  );
}

function EvidenceDetails({ story, data }: { story: Story; data: SiteBundle }) {
  const evidence = story.evidence_ids
    .map((id) => data.evidence.find((item) => item.id === id))
    .filter((item): item is Evidence => Boolean(item));

  return (
    <details className="evidence-details">
      <summary>证据与出处</summary>
      <p className="evidence-intro">
        以下信息来自已验证的 WP1 静态数据；artifact 是页面所引用的派生文件，source provenance
        保留其上游见证信息。
      </p>
      <div className="evidence-list">
        {evidence.map((item) => (
          <article className="evidence-item" key={item.id}>
            <div className="evidence-heading">
              <span>{item.evidence_type}</span>
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
            <p className="section-label">刘孝标注</p>
            <p className="annotation-text">{annotationReading[readingMode]}</p>
          </section>
        )}

        <section className="people-section" aria-labelledby="people-heading">
          <div className="section-heading">
            <p className="section-label">人物</p>
            <h2 id="people-heading">文中已解析的称谓</h2>
          </div>
          <div className="people-grid">
            {people.map((person) => (
              <PersonCard
                key={person.id}
                person={person}
                mentions={personMentions(story, person, data)}
              />
            ))}
          </div>
          <div className="mention-strip" aria-label="已解析称谓列表">
            {mentions.map((mention) => (
              <span className="mention-chip" key={mention.id}>
                {mention.surface} → {data.people.find((person) => person.id === mention.person_id)?.canonical_name}
              </span>
            ))}
          </div>
        </section>

        <EvidenceDetails story={story} data={data} />
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
