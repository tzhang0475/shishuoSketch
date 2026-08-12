import { useEffect, useMemo, useState } from "react";
import { loadSiteBundle } from "./data";
import type { Era, Person, Relation, SiteBundle, Story } from "./types";

function link(path: string, label: string) {
  return <a href={path}>{label}</a>;
}

function Layout({ children, data }: { children: React.ReactNode; data: SiteBundle }) {
  const story = data.stories[0];
  return (
    <main className="shell">
      <header className="masthead">
        <div>
          <p className="eyebrow">世说Sketch · WP1</p>
          <h1>{link(`/stories/${story.id}`, "从一则故事，走进魏晋")}</h1>
        </div>
        <nav>
          {link(`/stories/${story.id}`, "故事")}
          {link(`/eras/${data.eras[0].id}`, "候选母题")}
        </nav>
      </header>
      {children}
      <footer>static-first · {data.generated_from}</footer>
    </main>
  );
}

function StoryPage({ story, data }: { story: Story; data: SiteBundle }) {
  const people = story.person_ids
    .map((id) => data.people.find((person) => person.id === id))
    .filter((person): person is Person => Boolean(person));
  const relations = story.relation_ids
    .map((id) => data.relations.find((relation) => relation.id === id))
    .filter((relation): relation is Relation => Boolean(relation));
  const eras = story.era_ids
    .map((id) => data.eras.find((era) => era.id === id))
    .filter((era): era is Era => Boolean(era));
  return (
    <article>
      <p className="crumb">Story / {story.id}</p>
      <h2>{story.title}</h2>
      <p className="meta">{story.source_entry_id} · {story.review_status} · {story.assertion_status}</p>
      <section className="card story-text">
        <h3>正文</h3>
        <p>{story.text}</p>
      </section>
      {story.annotations.map((annotation) => (
        <section className="card annotation" key={annotation.id}>
          <h3>刘孝标注 · {annotation.id}</h3>
          <p>{annotation.text}</p>
        </section>
      ))}
      <section className="card">
        <h3>这一幕中的人</h3>
        <div className="links">{people.map((person) => link(`/people/${person.id}`, person.canonical_name))}</div>
        <h3>关系入口</h3>
        <div className="links">{relations.map((relation) => link(`/relations/${relation.id}`, relation.label))}</div>
        <h3>候选 Era Sketch</h3>
        <div className="links">{eras.map((era) => link(`/eras/${era.id}`, `${era.title}（${era.review_status}）`))}</div>
      </section>
    </article>
  );
}

function PersonPage({ person, data }: { person: Person; data: SiteBundle }) {
  const stories = data.stories.filter((story) => story.person_ids.includes(person.id));
  return (
    <article>
      <p className="crumb">Person / {person.id}</p>
      <h2>{person.canonical_name}</h2>
      <p className="meta">{person.review_status} · {person.assertion_status}</p>
      <section className="card">
        <h3>已观察称谓</h3>
        <p>{person.aliases.map((alias) => alias.surface).join("、") || "尚无本样本中的直接别名"}</p>
      </section>
      <section className="card">
        <h3>故事</h3>
        <div className="links">{stories.map((story) => link(`/stories/${story.id}`, story.title))}</div>
      </section>
    </article>
  );
}

function RelationPage({ relation, data }: { relation: Relation; data: SiteBundle }) {
  const subject = data.people.find((person) => person.id === relation.subject_id);
  const object = data.people.find((person) => person.id === relation.object_id);
  return (
    <article>
      <p className="crumb">Relation / {relation.id}</p>
      <h2>{relation.label}</h2>
      <p className="meta">{relation.assertion_status} · {relation.review_status}</p>
      <section className="card">
        <p>{subject ? link(`/people/${subject.id}`, subject.canonical_name) : relation.subject_id} → {object ? link(`/people/${object.id}`, object.canonical_name) : relation.object_id}</p>
        <p>{relation.notes}</p>
        <h3>相关故事</h3>
        <div className="links">{relation.story_ids.map((id) => { const story = data.stories.find((item) => item.id === id); return story ? link(`/stories/${id}`, story.title) : id; })}</div>
      </section>
    </article>
  );
}

function EraPage({ era, data }: { era: Era; data: SiteBundle }) {
  return (
    <article>
      <p className="crumb">Era / {era.id}</p>
      <h2>{era.title}</h2>
      <p className="meta">{era.review_status} · {era.assertion_status}</p>
      <section className="card">
        <p>{era.description}</p>
        <h3>关联故事</h3>
        <div className="links">{era.story_ids.map((id) => { const story = data.stories.find((item) => item.id === id); return story ? link(`/stories/${id}`, story.title) : id; })}</div>
        <h3>关联人物</h3>
        <div className="links">{era.person_ids.map((id) => { const person = data.people.find((item) => item.id === id); return person ? link(`/people/${id}`, person.canonical_name) : id; })}</div>
      </section>
    </article>
  );
}

function RoutedPage({ data }: { data: SiteBundle }) {
  const parts = window.location.pathname.split("/").filter(Boolean).map(decodeURIComponent);
  const [type, id] = parts;
  if (!type) return <StoryPage story={data.stories[0]} data={data} />;
  if (type === "stories") {
    const story = data.stories.find((item) => item.id === id);
    return story ? <StoryPage story={story} data={data} /> : <NotFound />;
  }
  if (type === "people") {
    const person = data.people.find((item) => item.id === id);
    return person ? <PersonPage person={person} data={data} /> : <NotFound />;
  }
  if (type === "relations") {
    const relation = data.relations.find((item) => item.id === id);
    return relation ? <RelationPage relation={relation} data={data} /> : <NotFound />;
  }
  if (type === "eras") {
    const era = data.eras.find((item) => item.id === id);
    return era ? <EraPage era={era} data={data} /> : <NotFound />;
  }
  return <NotFound />;
}

function NotFound() {
  return <section className="card"><h2>没有找到这个 WP1 对象</h2><p>请从现有故事入口继续阅读。</p></section>;
}

export default function App() {
  const [data, setData] = useState<SiteBundle | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => { loadSiteBundle().then(setData).catch((reason: unknown) => setError(reason instanceof Error ? reason.message : String(reason))); }, []);
  const page = useMemo(() => data && <RoutedPage data={data} />, [data]);
  if (error) return <main className="shell"><section className="card error"><h1>静态数据加载失败</h1><p>{error}</p></section></main>;
  if (!data) return <main className="shell"><p>正在读取静态数据……</p></main>;
  return <Layout data={data}>{page}</Layout>;
}
