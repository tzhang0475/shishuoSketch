import { useEffect, useMemo, useRef, useState, type KeyboardEvent } from "react";
import {
  evidenceDisplay,
  loadSiteBundle,
  personDisplay,
  readingLabel,
  relationDisplay,
  sourceDisplay,
} from "./data";
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
  focusedEraFromExploration,
  focusedEraNodeFromExploration,
  publishedStoryIds,
  relationContextStoryId,
  type PersonMentionRoute,
  type PersonRelationRoute,
  type RelationPerspective,
  type ExplorationNode,
} from "./relationExplorer";
import { loadUX2Index, type PersonIndexRecord, type StoryIndexRecord } from "./indexData";
import { FeedbackButton, FeedbackReviewPanel } from "./Feedback";
import { normalizeReaderText } from "./readerDisplay";
import {
  loadHistoricalEvidence,
  loadHistoricalProjection,
  type HistoricalProjection,
} from "./historical";
import { loadStorySketch, loadStorySketchEvidence, NL0_STORY_IDS } from "./storySketch";
import { loadDs1Preview, type DS1Preview } from "./ds1";
import {
  loadHng0Site,
  readHng0Review,
  writeHng0Review,
  type Hng0Evidence,
  type Hng0Relation,
  type Hng0ReviewOverlay,
  type Hng0TemporalItem,
  type HngReviewStatus,
} from "./hng0";
import {
  loadHng01Site,
  readHng01Review,
  writeHng01Review,
  type Hng01Evidence,
  type Hng01Relation,
  type Hng01ReviewOverlay,
  type Hng01TemporalItem,
  type Hng01ReviewStatus,
} from "./hng01";
import {
  loadHng02Site,
  readHng02Review,
  writeHng02Review,
  type Hng02Evidence,
  type Hng02Relation,
  type Hng02ReviewOverlay,
  type Hng02ReviewStatus,
  type Hng02TemporalItem,
} from "./hng02";
import { IRRReviewPage } from "./IRRReviewPage";
import { HDB2ReviewPage } from "./HDB2ReviewPage";
import type {
  Evidence,
  EraCard,
  EraHistoricalProjection,
  HistoricalEvidenceProjection,
  HistoricalReferenceProjection,
  PersonHistoricalProjection,
  Mention,
  Person,
  ReadingPair,
  ReadingSegment,
  RelationHistoricalProjection,
  Relation,
  SiteBundle,
  Story,
  StoryHistoricalProjection,
  StorySketchProjection,
  StorySketchEvidenceProjection,
  StorySceneContext,
  StoryReadingLabels,
} from "./types";

const FALLBACK_STORY_ID = "06-yaliang-019";
const READING_MODE_STORAGE_KEY = "shishuoSketch.reading-mode";
const NL0_STORY_SKETCH_ENABLED = import.meta.env.DEV || import.meta.env.VITE_NL0_STORY_SKETCH === "1";
const HNG0_SITE = loadHng0Site();
const HNG01_SITE = loadHng01Site();
const HNG02_SITE = loadHng02Site();
type ReadingMode = "simplified" | "original";
type ResolvedMention = Mention & { person_id: string };
type PersonFocus = (personId: string, route?: PersonMentionRoute) => void;
type RelationFocus = (perspective: RelationPerspective) => void;
type EraFocus = (eraCardId: string) => void;

function initialReadingMode(): ReadingMode {
  if (typeof window === "undefined") return "simplified";
  const stored = window.localStorage.getItem(READING_MODE_STORAGE_KEY);
  return stored === "original" ? "original" : "simplified";
}

function isIndexLocation(): boolean {
  if (typeof window === "undefined") return false;
  const base = import.meta.env.BASE_URL.replace(/\/+$/u, "");
  const path = window.location.pathname.replace(/\/+$/u, "");
  return path === `${base}/index`;
}

function isIRRReviewLocation(): boolean {
  if (typeof window === "undefined") return false;
  const base = import.meta.env.BASE_URL.replace(/\/+$/u, "");
  const path = window.location.pathname.replace(/\/+$/u, "");
  return path === `${base}/review/irr0`;
}

function isHDB2ReviewLocation(): boolean {
  if (typeof window === "undefined") return false;
  const base = import.meta.env.BASE_URL.replace(/\/+$/u, "");
  const path = window.location.pathname.replace(/\/+$/u, "");
  return path === `${base}/review/hdb2`;
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

function uiLabel(
  data: SiteBundle,
  key: keyof NonNullable<SiteBundle["ui"]>,
  mode: ReadingMode,
  fallback: string,
): string {
  return readingValue(data.ui?.[key], mode, fallback);
}

function storyLabel(
  data: SiteBundle,
  key: keyof StoryReadingLabels,
  mode: ReadingMode,
  fallback: string,
): string {
  return readingValue(readingLabel(data, key), mode, fallback);
}

function resolvedMentions(story: Story, data: SiteBundle): ResolvedMention[] {
  return story.mention_ids
    .map((id) => data.mentions.find((mention) => mention.id === id))
    .filter((mention): mention is ResolvedMention => Boolean(mention?.person_id && mention.confidence !== "unresolved"));
}

function personDisplayName(story: Story, data: SiteBundle, person: Person, mode: ReadingMode): string {
  return readingValue(personDisplay(data, person.id)?.name, mode, person.canonical_name);
}

function mentionPersonDisplayName(
  story: Story,
  data: SiteBundle,
  mention: Mention,
  mode: ReadingMode,
): string {
  const person = data.people.find((candidate) => candidate.id === mention.person_id);
  return person ? personDisplayName(story, data, person, mode) : "未解析人物";
}

function relationDisplayPair(
  story: Story,
  data: SiteBundle,
  relation: Relation,
  role: "role_a" | "role_b" | "label",
  mode: ReadingMode,
  fallback: string,
): string {
  return readingValue(relationDisplay(data, relation.id)?.[role] ?? undefined, mode, fallback);
}

function perspectiveNeighborRole(
  story: Story,
  data: SiteBundle,
  perspective: RelationPerspective,
  mode: ReadingMode,
): string {
  const role = perspective.relation.subject_id === perspective.neighbor.id ? "role_a" : "role_b";
  return relationDisplayPair(story, data, perspective.relation, role, mode, perspective.neighborRole)
    || relationDisplayPair(story, data, perspective.relation, "label", mode, perspective.relation.label);
}

function personNameById(story: Story, data: SiteBundle, personId: string, mode: ReadingMode): string {
  const person = data.people.find((candidate) => candidate.id === personId);
  return person ? personDisplayName(story, data, person, mode) : "未解析人物";
}

function storyById(data: SiteBundle, storyId: string): Story | undefined {
  return data.stories.find((story) => story.id === storyId);
}

type StoryAddressMode = "replace" | "push";

function writeStoryAddress(storyId: string, mode: StoryAddressMode = "replace", pathname?: string): void {
  if (typeof window === "undefined") return;
  const nextPathname = pathname ?? window.location.pathname;
  const nextSearch = pathname === undefined ? window.location.search : "";
  const next = `${nextPathname}${nextSearch}#story=${encodeURIComponent(storyId)}`;
  if (mode === "push") {
    window.history.pushState(null, "", next);
  } else {
    window.history.replaceState(null, "", next);
  }
}

function initialStoryId(data: SiteBundle): string {
  const target = typeof window === "undefined" ? null : storyIdFromHash(window.location.hash);
  const addressed = target ? storyById(data, target) : undefined;
  if (addressed && addressed.publication_state !== "blocked") return addressed.id;
  return randomPublishedStoryId(data) ?? FALLBACK_STORY_ID;
}

function historicalSourceLabel(
  sourceLabel: HistoricalEvidenceProjection["source_label"],
  mode: ReadingMode,
): string {
  if ("work" in sourceLabel) {
    const work = readingValue(sourceLabel.work, mode, "");
    const edition = readingValue(sourceLabel.edition, mode, "");
    return [work, edition].filter(Boolean).join(" · ");
  }
  return readingValue(sourceLabel, mode, "");
}

function historicalModalityLabel(modality: string | null | undefined): string {
  return {
    disputed: "存疑",
    probable: "或然",
    possible: "可能",
    unknown: "未详",
  }[modality ?? ""] ?? "";
}

function useHistoricalProjection<T extends HistoricalProjection>(
  kind: "person" | "story" | "era" | "relation" | "evidence",
  id: string | null,
): { value: T | null; loading: boolean; failed: boolean } {
  const [value, setValue] = useState<T | null>(null);
  const [loading, setLoading] = useState(Boolean(id));
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    if (!id) {
      setValue(null);
      setLoading(false);
      setFailed(false);
      return;
    }
    let active = true;
    setLoading(true);
    setFailed(false);
    // The shared loader owns the in-flight request.  Keeping it alive across
    // a React remount avoids aborting the promise that a concurrent panel
    // consumer is already waiting for.
    void loadHistoricalProjection<T>(kind, id)
      .then((next) => {
        if (!active) return;
        setValue(next);
        setLoading(false);
      })
      .catch(() => {
        if (!active) return;
        setValue(null);
        setLoading(false);
        setFailed(true);
      });
    return () => {
      active = false;
    };
  }, [kind, id]);

  return { value, loading, failed };
}

function HistoricalEvidenceDisclosure({
  evidenceIds,
  readingMode,
  data,
  feedbackStoryId,
}: {
  evidenceIds: string[];
  readingMode: ReadingMode;
  data?: SiteBundle;
  feedbackStoryId?: string;
}) {
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [failed, setFailed] = useState(false);
  const [evidence, setEvidence] = useState<HistoricalEvidenceProjection[]>([]);
  if (evidenceIds.length === 0) return null;

  async function toggle(): Promise<void> {
    const nextOpen = !open;
    setOpen(nextOpen);
    if (!nextOpen || evidence.length > 0 || failed) return;
    setLoading(true);
    try {
      setEvidence(await loadHistoricalEvidence(evidenceIds));
    } catch {
      setFailed(true);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="ux1-evidence-disclosure">
      <button type="button" className="ux1-evidence-button" aria-expanded={open} onClick={() => void toggle()}>
        查看依据
      </button>
      {open && (
        <div className="ux1-evidence-detail">
          {loading && <p className="ux1-loading">依据载入中…</p>}
          {failed && <p className="ux1-muted">依据暂时不可用。</p>}
          {evidence.map((item) => (
            <article key={item.evidence_id} className="ux1-evidence-item">
              <p className="ux1-evidence-source">
                {historicalSourceLabel(item.source_label, readingMode)}
                {item.attribution ? ` · ${item.attribution}` : ""}
                {item.quoted_source ? ` · 引${item.quoted_source}` : ""}
                {historicalModalityLabel(item.modality) ? ` · ${historicalModalityLabel(item.modality)}` : ""}
                {historicalModalityLabel(item.parent_assertion_modality) ? ` · 上位断言${historicalModalityLabel(item.parent_assertion_modality)}` : ""}
              </p>
              <blockquote>{readingValue(item.short_excerpt, readingMode, "")}</blockquote>
              {item.locator && <p className="ux1-evidence-locator">{item.locator}</p>}
              {feedbackStoryId && data && (
                <FeedbackButton
                  data={data}
                  storyId={feedbackStoryId}
                  targetType="evidence"
                  targetId={item.evidence_id}
                  targetTextSnapshot={readingValue(item.short_excerpt, readingMode, "")}
                  label="反馈此依据"
                />
              )}
            </article>
          ))}
          {!loading && !failed && evidence.length === 0 && <p className="ux1-muted">暂无可展开的依据。</p>}
        </div>
      )}
    </div>
  );
}

function StorySketchEvidenceDisclosure({
  evidenceIds,
  readingMode,
  data,
  feedbackStoryId,
}: {
  evidenceIds: string[];
  readingMode: ReadingMode;
  data?: SiteBundle;
  feedbackStoryId?: string;
}) {
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [failed, setFailed] = useState(false);
  const [evidence, setEvidence] = useState<StorySketchEvidenceProjection[]>([]);
  if (evidenceIds.length === 0) return null;

  async function toggle(): Promise<void> {
    const nextOpen = !open;
    setOpen(nextOpen);
    if (!nextOpen || evidence.length > 0 || failed) return;
    setLoading(true);
    try {
      setEvidence(await loadStorySketchEvidence(evidenceIds));
    } catch {
      setFailed(true);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="ux1-evidence-disclosure">
      <button type="button" className="ux1-evidence-button" aria-expanded={open} onClick={() => void toggle()}>
        查看依据
      </button>
      {open && (
        <div className="ux1-evidence-detail">
          {loading && <p className="ux1-loading">依据载入中…</p>}
          {failed && <p className="ux1-muted">依据暂时不可用。</p>}
          {evidence.map((item) => (
            <article key={item.evidence_id} className="ux1-evidence-item">
              <p className="ux1-evidence-source">
                {readingValue(item.source_label.work, readingMode, "世说新语")}
                {item.source_layer ? ` · ${item.source_layer}` : ""}
              </p>
              <blockquote>{readingValue(item.short_excerpt, readingMode, "")}</blockquote>
              {item.locator && <p className="ux1-evidence-locator">{item.locator}</p>}
              {feedbackStoryId && data && (
                <FeedbackButton
                  data={data}
                  storyId={feedbackStoryId}
                  targetType="evidence"
                  targetId={item.evidence_id}
                  targetTextSnapshot={readingValue(item.short_excerpt, readingMode, "")}
                  label="反馈此依据"
                />
              )}
            </article>
          ))}
          {!loading && !failed && evidence.length === 0 && <p className="ux1-muted">暂无可展开的依据。</p>}
        </div>
      )}
    </div>
  );
}

function HistoricalReferenceList({
  refs,
  readingMode,
  data,
  storyId,
}: {
  refs: HistoricalReferenceProjection[];
  readingMode: ReadingMode;
  data?: SiteBundle;
  storyId?: string;
}) {
  if (refs.length === 0) return null;
  return (
    <section className="ux1-further-reading">
      <p className="relation-detail-heading">进一步读</p>
      <ul className="ux1-reference-list">
        {refs.slice(0, 3).map((ref) => (
          <li key={ref.evidence_id} className="ux1-reference-row">
            <span>
              {readingValue(ref.label, readingMode, "进一步读")}
              {ref.attribution ? ` · ${ref.attribution}` : ""}
              {ref.quoted_source ? ` · 引${ref.quoted_source}` : ""}
              {ref.modality && ref.modality !== "explicit" ? ` · ${ref.modality}` : ""}
            </span>
            <HistoricalEvidenceDisclosure evidenceIds={[ref.evidence_id]} readingMode={readingMode} data={data} feedbackStoryId={storyId} />
          </li>
        ))}
      </ul>
      {refs.length > 3 && <p className="ux1-muted">另有 {refs.length - 3} 条，按需展开。</p>}
    </section>
  );
}

function PersonHistoricalProfile({
  personId,
  readingMode,
  onFocus,
}: {
  personId: string;
  readingMode: ReadingMode;
  onFocus: PersonFocus;
}) {
  const { value, loading, failed } = useHistoricalProjection<PersonHistoricalProjection>("person", personId);
  if (loading) return <p className="ux1-loading ux1-person-history-loading">史事载入中…</p>;
  if (failed || !value) return null;
  const hasProfile = value.family.length > 0 || value.offices.length > 0 || value.locations.length > 0
    || value.periods.length > 0 || value.scholarly_refs.length > 0;
  if (!hasProfile) return null;
  const evidenceIds = [...new Set([
    ...value.family.flatMap((row) => row.evidence_ids),
    ...value.offices.flatMap((row) => row.evidence_ids),
    ...value.locations.flatMap((row) => row.evidence_ids),
    ...value.periods.flatMap((row) => row.evidence_ids),
  ])];
  return (
    <section className="ux1-person-history" aria-label="历史">
      <p className="relation-detail-heading">历史</p>
      {value.family.length > 0 && (
        <div className="ux1-history-group">
          <p className="ux1-history-label">家世</p>
          {value.family.map((row) => (
            <button type="button" className="ux1-history-link" key={row.relation_id} onClick={() => onFocus(row.person_id)}>
              {readingValue(row.name, readingMode, row.person_id)} · {readingValue(row.relation_label, readingMode, "关系")}
              {row.relation_basis === "derived" ? "（推得）" : ""}
            </button>
          ))}
        </div>
      )}
      {value.offices.length > 0 && (
        <div className="ux1-history-group">
          <p className="ux1-history-label">仕宦</p>
          {value.offices.map((row) => (
            <p className="ux1-history-value" key={row.fact_id}>
              {readingValue(row.name, readingMode, "官职")}
              {row.temporal_label && ` · ${readingValue(row.temporal_label, readingMode, "")}`}
              {row.temporal_precision !== "unknown" && <small>（{row.temporal_precision}）</small>}
            </p>
          ))}
        </div>
      )}
      {value.locations.length > 0 && (
        <div className="ux1-history-group">
          <p className="ux1-history-label">所到</p>
          {value.locations.map((row) => (
            <p className="ux1-history-value" key={row.fact_id}>
              {readingValue(row.name, readingMode, "地点")} · {readingValue(row.role, readingMode, "历史地点")}
            </p>
          ))}
        </div>
      )}
      {value.periods.length > 0 && (
        <div className="ux1-history-group">
          <p className="ux1-history-label">所处</p>
          {value.periods.map((row) => (
            <p className="ux1-history-value" key={`${row.label.original}-${row.story_ids.join(",")}`}>
              {readingValue(row.label, readingMode, "时代定位")}
            </p>
          ))}
        </div>
      )}
      <HistoricalReferenceList refs={value.scholarly_refs} readingMode={readingMode} />
      <HistoricalEvidenceDisclosure evidenceIds={evidenceIds} readingMode={readingMode} />
    </section>
  );
}

function RelationHistoricalContext({ relationId, readingMode }: { relationId: string; readingMode: ReadingMode }) {
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [value, setValue] = useState<RelationHistoricalProjection | null>(null);
  const [failed, setFailed] = useState(false);

  async function reveal(): Promise<void> {
    const nextOpen = !open;
    setOpen(nextOpen);
    if (!nextOpen || value || failed) return;
    setLoading(true);
    try {
      setValue(await loadHistoricalProjection<RelationHistoricalProjection>("relation", relationId));
    } catch {
      setFailed(true);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="ux1-relation-context">
      <button type="button" className="ux1-evidence-button" aria-expanded={open} onClick={() => void reveal()}>
        历史语境
      </button>
      {open && (
        <div className="ux1-relation-context-body">
          {loading && <p className="ux1-loading">史事载入中…</p>}
          {failed && <p className="ux1-muted">历史语境暂时不可用。</p>}
          {value && (
            <>
              <p>{readingValue(value.context_label, readingMode, "已审阅关系")}</p>
              {value.time.label && <p>{readingValue(value.time.label, readingMode, "")}</p>}
              {value.notes && <p className="ux1-muted">{value.notes}</p>}
              <HistoricalEvidenceDisclosure evidenceIds={value.evidence_ids} readingMode={readingMode} />
            </>
          )}
          {!loading && !failed && !value && <p className="ux1-muted">暂无补充语境。</p>}
        </div>
      )}
    </div>
  );
}

function StoryHistoricalDepth({
  storyId,
  data,
  readingMode,
  onFocus,
}: {
  storyId: string;
  data: SiteBundle;
  readingMode: ReadingMode;
  onFocus: PersonFocus;
}) {
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [value, setValue] = useState<StoryHistoricalProjection | null>(null);
  const [failed, setFailed] = useState(false);

  async function reveal(): Promise<void> {
    const nextOpen = !open;
    setOpen(nextOpen);
    if (!nextOpen || value || failed) return;
    setLoading(true);
    try {
      setValue(await loadHistoricalProjection<StoryHistoricalProjection>("story", storyId));
    } catch {
      setFailed(true);
    } finally {
      setLoading(false);
    }
  }

  return (
    <section className="ux1-story-history" aria-label="历史上下文">
      <button type="button" className="ux1-further-reading-toggle" aria-expanded={open} onClick={() => void reveal()}>
        进一步读
      </button>
      {open && (
        <div className="ux1-story-history-body">
          {loading && <p className="ux1-loading">史事载入中…</p>}
          {failed && <p className="ux1-muted">历史资料暂时不可用。</p>}
          {value && (
            <>
              {value.historical_context.length > 0 && (
                <div className="ux1-story-history-group">
                  <p className="ux1-history-label">此时</p>
                  {value.historical_context.map((row) => <p key={`${row.kind}-${row.label?.original}`}>{readingValue(row.label ?? undefined, readingMode, "")}</p>)}
                </div>
              )}
              {value.participant_context.length > 0 && (
                <div className="ux1-story-history-group">
                  <p className="ux1-history-label">在场</p>
                  {value.participant_context.map((row) => (
                    <button type="button" className="ux1-history-link" key={`${row.person_id}-${row.role}`} onClick={() => onFocus(row.person_id, { via_mention_id: "ux1-history", from_story_id: storyId })}>
                      {readingValue(row.name, readingMode, "未解析人物")} · {row.role}
                    </button>
                  ))}
                </div>
              )}
              <HistoricalReferenceList refs={value.scholarly_refs} readingMode={readingMode} data={data} storyId={storyId} />
              <HistoricalReferenceList refs={value.citation_refs} readingMode={readingMode} data={data} storyId={storyId} />
              <HistoricalEvidenceDisclosure evidenceIds={value.evidence_ids} readingMode={readingMode} data={data} feedbackStoryId={storyId} />
              {value.historical_context.length === 0 && value.participant_context.length === 0 && value.scholarly_refs.length === 0 && value.citation_refs.length === 0 && <p className="ux1-muted">暂无可补充的已审阅历史资料。</p>}
            </>
          )}
          {!loading && !failed && !value && <p className="ux1-muted">暂无可补充的已审阅历史资料。</p>}
        </div>
      )}
    </section>
  );
}

function StorySketchView({
  value,
  data,
  readingMode,
}: {
  value: StorySketchProjection;
  data: SiteBundle;
  readingMode: ReadingMode;
}) {
  const evidenceIds = [...new Set(value.supporting_evidence.map((row) => row.evidence_id))];
  const [ds1Preview, setDs1Preview] = useState<DS1Preview | null>(null);
  const [ds1Loading, setDs1Loading] = useState(false);

  useEffect(() => {
    if (value.story_id !== "27-jiajue-008") {
      setDs1Preview(null);
      setDs1Loading(false);
      return;
    }
    const controller = new AbortController();
    let active = true;
    setDs1Loading(true);
    void loadDs1Preview(value.story_id, controller.signal)
      .then((preview) => {
        if (active) setDs1Preview(preview);
      })
      .catch(() => {
        if (active) setDs1Preview(null);
      })
      .finally(() => {
        if (active) setDs1Loading(false);
      });
    return () => {
      active = false;
      controller.abort();
    };
  }, [value.story_id]);

  return (
    <section className="nl0-story-sketch" aria-label="Story Sketch">
      <div className="nl0-sketch-heading">
        <p className="section-label">Sketch</p>
        <span className="nl0-sketch-review">已审阅投影</span>
        <FeedbackButton
          data={data}
          storyId={value.story_id}
          targetType="narrative"
          targetId={`story-sketch-nl0-${value.story_id}`}
          targetTextSnapshot={readingValue(value.scene_core.text, readingMode, "")}
          label="反馈此段"
        />
      </div>
      {(ds1Loading || ds1Preview) && (
        <section className="nl0-sketch-group ds1-story-context" aria-label="此刻">
          <p className="nl0-sketch-label">此刻</p>
          {ds1Loading && <p className="nl0-sketch-text">史事载入中…</p>}
          {ds1Preview && (
            <>
              {ds1Preview.scene_context.scene_summary.text && (
                <p className="nl0-sketch-text">{ds1Preview.scene_context.scene_summary.text}</p>
              )}
              {ds1Preview.scene_context.participant_states.length > 0 && (
                <p className="ds1-preview-detail">
                  {ds1Preview.scene_context.participant_states
                    .filter((row) => row.state)
                    .map((row) => `${row.surface}：${row.state}`)
                    .join("；")}
                </p>
              )}
              <span className="ds1-preview-meta">DS1 已审阅预览 · {ds1Preview.evidence_bundle_ids.length} 条依据</span>
            </>
          )}
        </section>
      )}
      {value.era_profile && (
        <div className="nl0-sketch-group nl0-sketch-era">
          <p className="nl0-sketch-label">Era</p>
          <p className="nl0-sketch-text">{readingValue(value.era_profile.text, readingMode, "")}</p>
        </div>
      )}
      <div className="nl0-sketch-group nl0-sketch-core">
        <p className="nl0-sketch-label">Scene Core</p>
        <p className="nl0-sketch-text">{readingValue(value.scene_core.text, readingMode, "")}</p>
      </div>
      {value.essential_background.length > 0 && (
        <div className="nl0-sketch-group">
          <p className="nl0-sketch-label">Essential Background</p>
          {value.essential_background.map((claim) => (
            <p className="nl0-sketch-text" key={claim.text.original}>{readingValue(claim.text, readingMode, "")}</p>
          ))}
        </div>
      )}
      {value.resonance && (
        <div className="nl0-sketch-group nl0-sketch-resonance">
          <p className="nl0-sketch-label">Resonance</p>
          <p className="nl0-sketch-text">{readingValue(value.resonance.text, readingMode, "")}</p>
        </div>
      )}
      <div className="nl0-sketch-evidence">
        <span>{value.supporting_evidence.length} 条依据</span>
        <StorySketchEvidenceDisclosure evidenceIds={evidenceIds} readingMode={readingMode} data={data} feedbackStoryId={value.story_id} />
      </div>
    </section>
  );
}

function EraHistoricalDepth({
  eraId,
  readingMode,
  onFocus,
  onStorySelect,
}: {
  eraId: string;
  readingMode: ReadingMode;
  onFocus: PersonFocus;
  onStorySelect: (storyId: string) => void;
}) {
  const { value, loading, failed } = useHistoricalProjection<EraHistoricalProjection>("era", eraId);
  if (loading) return <p className="ux1-loading ux1-era-history-loading">史事载入中…</p>;
  if (failed || !value) return null;
  const hasContent = Boolean(value.ruler) || value.people.length > 0 || value.events.length > 0 || value.offices.length > 0 || value.locations.length > 0 || value.story_ids.length > 0;
  if (!hasContent) return null;
  return (
    <section className="ux1-era-history" aria-label="时代历史">
      <p className="relation-detail-heading">历史</p>
      {value.ruler && (
        <div className="ux1-era-ruler">
          <p>{readingValue(value.ruler.title, readingMode, "")}{value.ruler.personal_name ? ` · ${readingValue(value.ruler.personal_name, readingMode, "")}` : ""}</p>
          <small>{[value.ruler.reign_start_year, value.ruler.reign_end_year].every((year) => typeof year === "number") ? `${value.ruler.reign_start_year}–${value.ruler.reign_end_year}` : ""}</small>
        </div>
      )}
      {value.people.length > 0 && <div className="ux1-history-group"><p className="ux1-history-label">人物</p>{value.people.slice(0, 5).map((row: any) => <button type="button" className="ux1-history-link" key={row.person_id} onClick={() => onFocus(row.person_id)}>{readingValue(row.name, readingMode, "未解析人物")}</button>)}</div>}
      {value.events.length > 0 && <div className="ux1-history-group"><p className="ux1-history-label">此时</p>{value.events.slice(0, 3).map((row: any) => <p className="ux1-history-value" key={row.event_id}>{readingValue(row.name, readingMode, row.event_id)}</p>)}</div>}
      {value.offices.length > 0 && <div className="ux1-history-group"><p className="ux1-history-label">仕宦</p>{value.offices.slice(0, 3).map((row: any) => <p className="ux1-history-value" key={row.office_id}>{readingValue(row.name, readingMode, row.office_id)}</p>)}</div>}
      {value.locations.length > 0 && <div className="ux1-history-group"><p className="ux1-history-label">所及</p>{value.locations.slice(0, 3).map((row: any) => <p className="ux1-history-value" key={row.location_id}>{readingValue(row.name, readingMode, row.location_id)}</p>)}</div>}
      {value.story_ids.length > 0 && (
        <div className="ux1-history-group"><p className="ux1-history-label">相关故事</p>{value.story_ids.slice(0, 5).map((storyId) => <button type="button" className="ux1-history-link" key={storyId} onClick={() => onStorySelect(storyId)}>{storyId}</button>)}</div>
      )}
      <HistoricalEvidenceDisclosure evidenceIds={value.evidence_ids} readingMode={readingMode} />
    </section>
  );
}

function storyExcerpt(story: Story, mode: ReadingMode): string {
  const text = story.reading.main_text[mode].replace(/\s+/gu, "");
  return text.length > 54 ? `${text.slice(0, 54)}……` : text;
}

function InlineEntityMention({
  className,
  text,
  ariaLabel,
  title,
  onActivate,
}: {
  className: string;
  text: string;
  ariaLabel: string;
  title: string;
  onActivate: () => void;
}) {
  function handleKeyDown(event: KeyboardEvent<HTMLSpanElement>): void {
    if (event.key !== "Enter" && event.key !== " ") return;
    event.preventDefault();
    onActivate();
  }

  return (
    <span
      role="button"
      tabIndex={0}
      className={className}
      aria-label={ariaLabel}
      title={title}
      onClick={onActivate}
      onKeyDown={handleKeyDown}
    >
      {text}
    </span>
  );
}

function InlineReadingSegments({
  segments,
  story,
  data,
  readingMode,
  focusedPersonId,
  onFocus,
  onEraFocus,
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
  onEraFocus: EraFocus;
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
        aria-label={storyLabel(data, "annotation_label", readingMode, "刘孝标注")}
      >
        <span className="inline-annotation-heading">
          {storyLabel(data, "annotation_label", readingMode, "刘孝标注")}
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
            onEraFocus={onEraFocus}
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
                <blockquote>{readingValue(evidenceDisplay(data, item.id), readingMode, item.quote)}</blockquote>
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
        const text = normalizeReaderText(readingValue(segment.display, readingMode, ""));
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
          const resolvedName = segment.canonical_name
            ? readingValue(segment.canonical_name, readingMode, "")
            : "";
          if (segment.resolution_status === "candidate_for_review") {
            return (
              <span
                className="inline-identity-candidate"
                key={`${segment.mention_id}-${index}`}
                data-mention-id={segment.mention_id}
                aria-label={`${text}，人物尚待确认`}
                title="人物尚待确认；候选与依据保留在资料层"
              >
                {text}
              </span>
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
        if (segment.type === "ruler_mention") {
          const card = data.era_cards.find((candidate) => candidate.era_card_id === segment.era_card_id);
          const title = card ? readingValue(card.title, readingMode, "纪元") : "纪元";
          return (
            <InlineEntityMention
              className="inline-ruler-mention"
              key={`${segment.mention_id}-${index}`}
              text={text}
              ariaLabel={`${text}，打开${title}纪元卡`}
              title={`${text} · ${title}`}
              onActivate={() => onEraFocus(segment.era_card_id)}
            />
          );
        }
        const mention = data.mentions.find((candidate) => candidate.id === segment.mention_id);
        const person = data.people.find((candidate) => candidate.id === segment.person_id);
        const personName = person ? personDisplayName(story, data, person, readingMode) : "未解析人物";
        const active = focusedPersonId === segment.person_id;
        return (
          <InlineEntityMention
            className={active ? "inline-person-mention active" : "inline-person-mention"}
            key={`${segment.mention_id}-${index}`}
            text={text}
            ariaLabel={`${text}，已解析为${personName}，查看人物`}
            title={mention ? `${text} → ${personName}` : personName}
            onActivate={() => onFocus(segment.person_id, { via_mention_id: segment.mention_id, from_story_id: story.id })}
          />
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
  const neighborRole = perspectiveNeighborRole(story, data, perspective, readingMode);
  const neighborName = personDisplayName(story, data, perspective.neighbor, readingMode);
  const relationScope = readingValue(
    relationDisplay(data, relation.id)?.scope ?? undefined,
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
        <span className="relation-evidence-summary">{storyLabel(data, "relation_evidence_toggle", readingMode, "查看关系依据")}</span>
      </summary>
      <div className="relation-evidence-body">
        {evidence.map((item) => {
          const source = sourceDisplay(data, item.source_id);
          const quote = readingValue(evidenceDisplay(data, item.id), readingMode, item.quote);
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
        <RelationHistoricalContext relationId={relation.id} readingMode={readingMode} />
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
        <span>{personNameById(story, data, otherPersonId, readingMode)} · {relationDisplayPair(story, data, relation, "label", readingMode, relation.label)}</span>
        <span className="relation-basis-note">{storyLabel(data, "derived_relation_note", readingMode, "由关系链推得")}</span>
      </summary>
      <div className="derived-path" aria-label={storyLabel(data, "derived_relation_label", readingMode, "推得关系")}>
        {path.length === 0 ? (
          <p>{storyLabel(data, "derived_relation_note", readingMode, "由关系链推得")}</p>
        ) : (
          path.map((edge, index) => {
            const fromId = displayIds[index] ?? edge.subject_id;
            const toId = displayIds[index + 1] ?? edge.object_id;
            const fromName = personNameById(story, data, fromId, readingMode);
            const toName = personNameById(story, data, toId, readingMode);
            const edgeLabel = relationDisplayPair(story, data, edge, "label", readingMode, edge.label);
            return (
              <div className="derived-path-step" key={edge.id}>
                <span>{fromName}</span>
                <span className="derived-path-connector">↓ {edgeLabel} ↓</span>
                <span>{toName}</span>
              </div>
            );
          })
        )}
        <p className="derived-no-quotation">{storyLabel(data, "derived_relation_note", readingMode, "由关系链推得")}</p>
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
  onRelationFocus,
}: {
  story: Story;
  data: SiteBundle;
  focusedPerson: Person;
  perspectives: RelationPerspective[];
  readingMode: ReadingMode;
  onRelationFocus: RelationFocus;
}) {
  const layout = egoLayout(perspectives.length);
  return (
    <section className="ego-map-panel" aria-labelledby="ego-map-heading">
      <div className="section-heading">
        <p className="section-label">{storyLabel(data, "relation_section", readingMode, "人物关系")}</p>
        <h3 id="ego-map-heading">{storyLabel(data, "direct_relation_label", readingMode, "已审阅的直接关系")}</h3>
      </div>
      {perspectives.length === 0 ? (
        <p className="relation-empty">{storyLabel(data, "no_direct_relations", readingMode, "目前尚无已审核的人物关系。")}</p>
      ) : (
        <div className="ego-map" aria-label={storyLabel(data, "direct_relation_label", readingMode, "已审阅的直接关系")}>
          <svg className="ego-map-edges" viewBox="0 0 100 100" aria-hidden="true" preserveAspectRatio="none">
            {perspectives.map((perspective, index) => {
              const point = layout.neighbors[index];
              const edgeLabel = perspectiveNeighborRole(story, data, perspective, readingMode);
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
            aria-label={personDisplayName(story, data, focusedPerson, readingMode)}
            aria-current="true"
          >
            {personDisplayName(story, data, focusedPerson, readingMode)}
          </span>
          {perspectives.map((perspective, index) => {
            const point = layout.neighbors[index];
            return (
              <button
                type="button"
                className="ego-node ego-node-neighbor"
                style={{ left: `${point.x}%`, top: `${point.y}%` }}
                key={perspective.relation.id}
                onClick={() => onRelationFocus(perspective)}
                aria-label={`${personDisplayName(story, data, perspective.neighbor, readingMode)} · ${perspectiveNeighborRole(story, data, perspective, readingMode)}`}
              >
                {personDisplayName(story, data, perspective.neighbor, readingMode)}
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
      <p className="mention-origin-question">为什么这里指{personDisplayName(originStory, data, focusedPerson, readingMode)}？</p>
      <p className="mention-origin-reason">{explanation}</p>
      {evidence.length > 0 && (
        <details className="mention-origin-evidence">
          <summary>查看完整依据 ›</summary>
          {evidence.map((item) => (
            <article key={item.id}>
              <p className="mention-origin-source">
                {item.locator.annotation_id ? "刘孝标注" : "正文"}
              </p>
              <blockquote>{readingValue(evidenceDisplay(data, item.id), readingMode, item.quote)}</blockquote>
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
        <p className="relation-empty">{storyLabel(data, "empty_alias", readingMode, "—")}</p>
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
                      const source = sourceDisplay(data, item.source_id);
                      const quote = evidenceDisplay(data, item.id)?.[readingMode] ?? item.quote;
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
        const source = sourceDisplay(data, item.source_id);
        const quote = evidenceDisplay(data, item.id)?.[readingMode] ?? item.quote;
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
                    <blockquote key={item.id}>{evidenceDisplay(data, item.id)?.[readingMode] ?? item.quote}</blockquote>
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

function hngPairValue(pair: { original: string; simplified: string } | null | undefined, readingMode: ReadingMode): string {
  return pair?.[readingMode] ?? "";
}

function hngStatusLabel(status: HngReviewStatus): string {
  return {
    candidate: "候选",
    accepted: "接受",
    rejected: "拒绝",
    uncertain: "不确定",
    needs_more_evidence: "需要更多证据",
  }[status];
}

function hngRelationLabel(relation: Hng0Relation): string {
  return {
    parent_child: "亲子",
    sibling: "兄弟姐妹",
    uncle_nephew: "叔侄／舅甥",
    cousin_clan_kin: "从亲／族亲",
    marriage: "婚姻",
    affinal_relation: "姻亲",
    same_clan: "同族",
    superior_subordinate: "上下属",
    recruitment_served_under: "任用／事奉",
    teacher_student: "师生",
    explicit_friendship_association: "明确交游",
    explicit_political_cooperation_opposition: "政治合作／对立",
    shared_explicit_event: "共同事件",
  }[relation.relation_type] ?? relation.relation_type;
}

function hngTimeLabel(item: Hng0TemporalItem): string {
  if (item.precision === "exact" && item.start_year !== null) return `${item.start_year}`;
  if (item.precision === "between" && item.start_year !== null && item.end_year !== null) return `${item.start_year}–${item.end_year}`;
  if (item.precision === "circa" && item.start_year !== null) return `约${item.start_year}`;
  if (item.precision === "before" && item.start_year !== null) return `${item.start_year}以前`;
  if (item.precision === "after" && item.start_year !== null) return `${item.start_year}以后`;
  if (item.precision === "reign_period") return "年号／时代范围";
  return "年代未定";
}

function hngInitialReview(): Hng0ReviewOverlay {
  const relationDecisions: Hng0ReviewOverlay["relation_decisions"] = {};
  const temporalDecisions: Hng0ReviewOverlay["temporal_decisions"] = {};
  for (const relation of HNG0_SITE.relations) {
    relationDecisions[relation.relation_id] = { review_status: relation.review_status, reviewer_note: "" };
  }
  for (const item of HNG0_SITE.temporal_items) {
    temporalDecisions[item.temporal_id] = { review_status: item.review_status, reviewer_note: "" };
  }
  const saved = readHng0Review();
  return {
    schema: 1,
    stage: "hng0-local-review",
    canonical_write_back: false,
    relation_decisions: { ...relationDecisions, ...(saved?.relation_decisions ?? {}) },
    temporal_decisions: { ...temporalDecisions, ...(saved?.temporal_decisions ?? {}) },
  };
}

function Hng0ReviewControls({
  status,
  onChange,
}: {
  status: HngReviewStatus;
  onChange: (status: HngReviewStatus) => void;
}) {
  const choices: HngReviewStatus[] = ["accepted", "rejected", "uncertain", "needs_more_evidence"];
  return (
    <div className="hng0-review-controls" aria-label="HNG0 本地评审">
      {choices.map((choice) => (
        <button
          type="button"
          key={choice}
          className={status === choice ? "hng0-review-button active" : "hng0-review-button"}
          onClick={() => onChange(choice)}
        >
          {hngStatusLabel(choice)}
        </button>
      ))}
    </div>
  );
}

function Hng0EvidenceDetails({
  refs,
  selected,
}: {
  refs: string[];
  selected: boolean;
}) {
  return (
    <div className={selected ? "hng0-evidence-panel selected" : "hng0-evidence-panel"}>
      <p className="hng0-evidence-heading">证据 {refs.length} 条</p>
      {refs.length === 0 && <p className="hng0-muted">暂无证据引用。</p>}
      {refs.map((ref) => {
        const evidence: Hng0Evidence | undefined = HNG0_SITE.evidence[ref];
        if (!evidence) return null;
        return (
          <article className="hng0-evidence-item" key={ref}>
            <p className="hng0-evidence-meta">{evidence.source_work} · {evidence.source_layer} · {ref}</p>
            {evidence.original_text ? <blockquote>{evidence.original_text}</blockquote> : <p className="hng0-muted">此引用保留了来源记录与定位；当前投影没有重复载入原文。</p>}
            <p className="hng0-evidence-provenance">{evidence.source_path ?? "来源定位未展开"} · {evidence.assertion_status} · {evidence.source_review_status}</p>
          </article>
        );
      })}
    </div>
  );
}

function PersonHng0Surface({
  focusedPersonId,
  data,
  readingMode,
  onFocus,
  onStorySelect,
}: {
  focusedPersonId: string;
  data: SiteBundle;
  readingMode: ReadingMode;
  onFocus: PersonFocus;
  onStorySelect: (storyId: string) => void;
}) {
  const neighborhood = HNG0_SITE.people[focusedPersonId];
  const [review, setReview] = useState<Hng0ReviewOverlay>(hngInitialReview);
  const [selectedRelationId, setSelectedRelationId] = useState<string | null>(null);
  const [selectedTemporalId, setSelectedTemporalId] = useState<string | null>(null);
  useEffect(() => {
    writeHng0Review(review);
  }, [review]);
  if (!neighborhood) {
    return (
      <section className="hng0-surface" aria-label="HNG0 历史导航">
        <p className="relation-detail-heading">HNG0 历史导航</p>
        <p className="hng0-muted">此人物未进入本轮种子范围；HNG0 不递归扩展关系邻居。</p>
      </section>
    );
  }
  const setRelationStatus = (relationId: string, status: HngReviewStatus) => {
    setReview((current) => ({
      ...current,
      relation_decisions: {
        ...current.relation_decisions,
        [relationId]: { ...current.relation_decisions[relationId], review_status: status },
      },
    }));
  };
  const setTemporalStatus = (temporalId: string, status: HngReviewStatus) => {
    setReview((current) => ({
      ...current,
      temporal_decisions: {
        ...current.temporal_decisions,
        [temporalId]: { ...current.temporal_decisions[temporalId], review_status: status },
      },
    }));
  };
  const relationStatus = (relation: Hng0Relation): HngReviewStatus => review.relation_decisions[relation.relation_id]?.review_status ?? relation.review_status;
  const temporalStatus = (item: Hng0TemporalItem): HngReviewStatus => review.temporal_decisions[item.temporal_id]?.review_status ?? item.review_status;
  const selectedRelation = neighborhood.relations.find((relation) => relation.relation_id === selectedRelationId) ?? null;
  const selectedTemporal = neighborhood.temporal_spine.find((item) => item.temporal_id === selectedTemporalId) ?? null;
  const personStories = neighborhood.stories;
  return (
    <section className="hng0-surface" aria-label="HNG0 历史导航">
      <div className="hng0-heading-row">
        <div>
          <p className="relation-detail-heading">HNG0 历史导航</p>
          <p className="hng0-subtitle">一跳候选图 · 本地评审，不写回历史事实</p>
        </div>
        <span className="hng0-status-note">{neighborhood.nearby_person_ids.length} 位邻近人物</span>
      </div>
      <div className="hng0-summary-grid">
        <span>关系 {neighborhood.relations.length}</span>
        <span>时间条目 {neighborhood.temporal_spine.length}</span>
        <span>故事 {neighborhood.stories.length}</span>
        <span>时间窗 {neighborhood.approximate_temporal_window.start_year ?? "?"}–{neighborhood.approximate_temporal_window.end_year ?? "?"}</span>
      </div>

      <div className="hng0-section">
        <p className="relation-detail-heading">Relations · 一跳关系</p>
        <div className="hng0-graph" aria-label="一跳人物关系图">
          <div className="hng0-graph-center">{hngPairValue(neighborhood.person.name, readingMode)}</div>
          {neighborhood.relations.length === 0 && <p className="hng0-muted">暂无有证据的关系候选。</p>}
          {neighborhood.relations.map((relation) => {
            const otherId = relation.person_a === focusedPersonId ? relation.person_b : relation.person_a;
            const otherName = relation.person_a === focusedPersonId ? relation.person_b_name : relation.person_a_name;
            const status = relationStatus(relation);
            return (
              <div className="hng0-graph-row" key={relation.relation_id}>
                <button type="button" className="hng0-node" onClick={() => onFocus(otherId)}>{otherName ?? HNG0_SITE.person_labels[otherId] ?? "未解析人物"}</button>
                <button
                  type="button"
                  className={selectedRelationId === relation.relation_id ? "hng0-edge active" : "hng0-edge"}
                  onClick={() => { setSelectedRelationId(relation.relation_id); setSelectedTemporalId(null); }}
                >
                  {hngRelationLabel(relation)} · {hngStatusLabel(status)}
                </button>
              </div>
            );
          })}
        </div>
        {selectedRelation && (
          <article className="hng0-detail-card">
            <div className="hng0-detail-title">
              <span>{selectedRelation.person_a_name} — {hngRelationLabel(selectedRelation)} — {selectedRelation.person_b_name}</span>
              <span>{hngStatusLabel(relationStatus(selectedRelation))}</span>
            </div>
            <p className="hng0-detail-meta">{selectedRelation.certainty} · {selectedRelation.extraction_method} · {selectedRelation.source_review_status}</p>
            <Hng0ReviewControls status={relationStatus(selectedRelation)} onChange={(status) => setRelationStatus(selectedRelation.relation_id, status)} />
            <Hng0EvidenceDetails refs={selectedRelation.evidence_refs} selected />
          </article>
        )}
      </div>

      <div className="hng0-section">
        <p className="relation-detail-heading">Timeline · 最小时间脊</p>
        <div className="hng0-timeline">
          {neighborhood.temporal_spine.length === 0 && <p className="hng0-muted">暂无带证据的时间条目。</p>}
          {neighborhood.temporal_spine.map((item) => {
            const status = temporalStatus(item);
            return (
              <article className={item.precision === "exact" ? "hng0-timeline-item exact" : "hng0-timeline-item approximate"} key={item.temporal_id}>
                <button type="button" className="hng0-timeline-main" onClick={() => { setSelectedTemporalId(item.temporal_id); setSelectedRelationId(null); }}>
                  <span className="hng0-time-label">{hngTimeLabel(item)}</span>
                  <span>{item.label}</span>
                  <span className="hng0-time-kind">{item.kind} · {hngStatusLabel(status)}</span>
                </button>
                {selectedTemporalId === item.temporal_id && (
                  <div className="hng0-detail-card inline">
                    <p className="hng0-detail-meta">时间精度：{item.precision} · {item.certainty} · {item.source_review_status}</p>
                    <Hng0ReviewControls status={status} onChange={(next) => setTemporalStatus(item.temporal_id, next)} />
                    <Hng0EvidenceDetails refs={item.evidence_refs} selected />
                  </div>
                )}
              </article>
            );
          })}
        </div>
      </div>

      <div className="hng0-section">
        <p className="relation-detail-heading">Stories · 相关故事</p>
        <div className="hng0-story-list">
          {personStories.map((item) => {
            const story = data.stories.find((candidate) => candidate.id === item.story_id);
            const canOpen = Boolean(story);
            return (
              <button type="button" className="hng0-story-row" key={`${item.story_id}-${item.person_story_link_id ?? "link"}`} disabled={!canOpen} onClick={() => canOpen && onStorySelect(item.story_id)}>
                <span className="hng0-story-ref">{item.chapter_heading} · {String(item.story_ordinal ?? "?").padStart(3, "0")}</span>
                <span className="hng0-story-excerpt">{item.short_excerpt || "（仅有注释层关联）"}</span>
                <span className="hng0-story-meta">{item.source_presence} · {item.research_scope === "published" ? "已出版范围" : "研究范围"} · {item.review_status ?? "未标记"}</span>
              </button>
            );
          })}
        </div>
      </div>

      {(selectedRelation || selectedTemporal) && (
        <div className="hng0-section">
          <p className="relation-detail-heading">Evidence · 证据面板</p>
          <Hng0EvidenceDetails refs={selectedRelation?.evidence_refs ?? selectedTemporal?.evidence_refs ?? []} selected />
        </div>
      )}
    </section>
  );
}

function hng01RelationLabel(relation: Hng01Relation): string {
  return {
    parent_child: "亲子",
    sibling: "兄弟姐妹",
    uncle_nephew: "叔侄／舅甥",
    cousin_clan_kin: "从亲／族亲",
    marriage: "婚姻",
    affinal_relation: "姻亲",
    same_clan: "同族",
    superior_subordinate: "上下属",
    recruitment_served_under: "任用／事奉",
    teacher_student: "师生",
    explicit_friendship_association: "明确交游",
    explicit_political_cooperation_opposition: "政治合作／对立",
    shared_explicit_event: "共同事件",
  }[relation.relation_type] ?? relation.relation_type;
}

function hng01InitialReview(): Hng01ReviewOverlay {
  const relationDecisions: Hng01ReviewOverlay["relation_decisions"] = {};
  const temporalDecisions: Hng01ReviewOverlay["temporal_decisions"] = {};
  for (const relation of HNG01_SITE.relations) {
    relationDecisions[relation.relation_id] = { review_status: relation.review_status, reviewer_note: "" };
  }
  for (const item of HNG01_SITE.temporal_items) {
    temporalDecisions[item.temporal_id] = { review_status: item.review_status, reviewer_note: "" };
  }
  const saved = readHng01Review();
  return {
    schema: 1,
    stage: "hng0-1-local-review",
    canonical_write_back: false,
    relation_decisions: { ...relationDecisions, ...(saved?.relation_decisions ?? {}) },
    temporal_decisions: { ...temporalDecisions, ...(saved?.temporal_decisions ?? {}) },
  };
}

function Hng01ReviewControls({
  status,
  onChange,
}: {
  status: Hng01ReviewStatus;
  onChange: (status: Hng01ReviewStatus) => void;
}) {
  const choices: Hng01ReviewStatus[] = ["accepted", "rejected", "uncertain", "needs_more_evidence"];
  return (
    <div className="hng0-review-controls" aria-label="HNG0.1 本地评审">
      {choices.map((choice) => (
        <button
          type="button"
          key={choice}
          className={status === choice ? "hng0-review-button active" : "hng0-review-button"}
          onClick={() => onChange(choice)}
        >
          {hngStatusLabel(choice)}
        </button>
      ))}
    </div>
  );
}

function Hng01EvidenceDetails({ refs }: { refs: string[] }) {
  return (
    <div className="hng0-evidence-panel selected">
      <p className="hng0-evidence-heading">Newly extracted · 证据 {refs.length} 条</p>
      {refs.map((ref) => {
        const evidence: Hng01Evidence | undefined = HNG01_SITE.evidence[ref];
        if (!evidence) return null;
        return (
          <article className="hng0-evidence-item" key={ref}>
            <p className="hng0-evidence-meta">{evidence.source_work} · {evidence.source_layer} · {ref}</p>
            <blockquote>{evidence.model_snippet ?? evidence.original_text}</blockquote>
            <p className="hng0-evidence-provenance">{evidence.source_path ?? "来源定位未展开"}</p>
          </article>
        );
      })}
    </div>
  );
}

function hng01TimeLabel(item: Hng01TemporalItem): string {
  const start = item.temporal_scope?.start_year;
  const end = item.temporal_scope?.end_year;
  if (typeof start === "number" && typeof end === "number") return start === end ? `${start}` : `${start}–${end}`;
  if (typeof start === "number") return `${start}（${item.precision}）`;
  return "年代未定";
}

function PersonHng01Surface({
  focusedPersonId,
  onFocus,
}: {
  focusedPersonId: string;
  onFocus: PersonFocus;
}) {
  const neighborhood = HNG01_SITE.people[focusedPersonId];
  const [review, setReview] = useState<Hng01ReviewOverlay>(hng01InitialReview);
  const [selectedRelationId, setSelectedRelationId] = useState<string | null>(null);
  const [selectedTemporalId, setSelectedTemporalId] = useState<string | null>(null);
  useEffect(() => {
    writeHng01Review(review);
  }, [review]);
  if (!neighborhood) return null;
  const relations = neighborhood.newly_extracted_relations ?? [];
  const temporalItems = neighborhood.newly_extracted_temporal_items ?? [];
  const relationStatus = (row: Hng01Relation): Hng01ReviewStatus => review.relation_decisions[row.relation_id]?.review_status ?? row.review_status;
  const temporalStatus = (row: Hng01TemporalItem): Hng01ReviewStatus => review.temporal_decisions[row.temporal_id]?.review_status ?? row.review_status;
  const setRelationStatus = (id: string, status: Hng01ReviewStatus) => setReview((current) => ({
    ...current,
    relation_decisions: { ...current.relation_decisions, [id]: { ...current.relation_decisions[id], review_status: status } },
  }));
  const setTemporalStatus = (id: string, status: Hng01ReviewStatus) => setReview((current) => ({
    ...current,
    temporal_decisions: { ...current.temporal_decisions, [id]: { ...current.temporal_decisions[id], review_status: status } },
  }));
  const selectedRelation = relations.find((row) => row.relation_id === selectedRelationId) ?? null;
  const selectedTemporal = temporalItems.find((row) => row.temporal_id === selectedTemporalId) ?? null;
  return (
    <section className="hng0-surface hng01-surface" aria-label="HNG0.1 证据引导人物增长">
      <div className="hng0-heading-row">
        <div>
          <p className="relation-detail-heading">HNG0.1 Evidence-Guided Growth</p>
          <p className="hng0-subtitle">Newly extracted · 源文检索候选，不写回历史事实</p>
        </div>
        <span className="hng0-status-note">{HNG01_SITE.execution_kind}</span>
      </div>
      {relations.length === 0 && temporalItems.length === 0 ? (
        <p className="hng0-muted">当前没有可展示的真实模型候选；本地检索与运行状态保留在 HNG0.1 生成层。</p>
      ) : (
        <>
          <div className="hng0-summary-grid">
            <span>新关系 {relations.length}</span>
            <span>新时间条目 {temporalItems.length}</span>
            <span>邻居 {neighborhood.new_neighbor_ids?.length ?? 0}</span>
          </div>
          <div className="hng0-section">
            <p className="relation-detail-heading">Newly extracted · Relations</p>
            <div className="hng0-graph" aria-label="HNG0.1 一跳候选关系">
              {relations.map((relation) => {
                const otherId = relation.person_a === focusedPersonId ? relation.person_b : relation.person_a;
                const otherName = relation.person_a === focusedPersonId ? relation.person_b_name : relation.person_a_name;
                return (
                  <div className="hng0-graph-row" key={relation.relation_id}>
                    <button type="button" className="hng0-node" disabled={!otherId} onClick={() => otherId && onFocus(otherId)}>{otherName ?? relation.counterpart_surface}</button>
                    <button type="button" className={selectedRelationId === relation.relation_id ? "hng0-edge active" : "hng0-edge"} onClick={() => { setSelectedRelationId(relation.relation_id); setSelectedTemporalId(null); }}>
                      {hng01RelationLabel(relation)} · {hngStatusLabel(relationStatus(relation))}
                    </button>
                  </div>
                );
              })}
            </div>
            {selectedRelation && (
              <article className="hng0-detail-card">
                <div className="hng0-detail-title"><span>{selectedRelation.person_a_name ?? "未解析人物"} — {hng01RelationLabel(selectedRelation)} — {selectedRelation.person_b_name ?? selectedRelation.counterpart_surface}</span><span>{hngStatusLabel(relationStatus(selectedRelation))}</span></div>
                <p className="hng0-detail-meta">{selectedRelation.claim} · {selectedRelation.certainty} · {selectedRelation.resolution_status}</p>
                {selectedRelation.temporal_warnings.length > 0 && <p className="hng0-muted">时间警告：{selectedRelation.temporal_warnings.join("；")}</p>}
                <Hng01ReviewControls status={relationStatus(selectedRelation)} onChange={(status) => setRelationStatus(selectedRelation.relation_id, status)} />
                <Hng01EvidenceDetails refs={selectedRelation.evidence_refs} />
              </article>
            )}
          </div>
          <div className="hng0-section">
            <p className="relation-detail-heading">Newly extracted · Timeline</p>
            <div className="hng0-timeline">
              {temporalItems.map((item) => (
                <article className="hng0-timeline-item approximate" key={item.temporal_id}>
                  <button type="button" className="hng0-timeline-main" onClick={() => { setSelectedTemporalId(item.temporal_id); setSelectedRelationId(null); }}>
                    <span className="hng0-time-label">{hng01TimeLabel(item)}</span><span>{item.claim}</span><span className="hng0-time-kind">{item.temporal_type} · {hngStatusLabel(temporalStatus(item))}</span>
                  </button>
                  {selectedTemporalId === item.temporal_id && (
                    <div className="hng0-detail-card inline">
                      <p className="hng0-detail-meta">{item.certainty} · {item.subject_resolution_status}{item.temporal_warnings.length > 0 ? ` · ${item.temporal_warnings.join("；")}` : ""}</p>
                      <Hng01ReviewControls status={temporalStatus(item)} onChange={(status) => setTemporalStatus(item.temporal_id, status)} />
                      <Hng01EvidenceDetails refs={item.evidence_refs} />
                    </div>
                  )}
                </article>
              ))}
            </div>
          </div>
        </>
      )}
    </section>
  );
}

function hng02RelationLabel(relation: Hng02Relation): string {
  const level = {
    hard_relation: "Hard relation",
    documented_interaction: "Documented interaction",
    interpreted_relation: "Interpreted relation",
  }[relation.semantic_level];
  const type = {
    parent_child: "亲子",
    grandparent_grandchild: "祖孙",
    sibling: "兄弟姐妹",
    uncle_nephew: "叔侄／舅甥",
    cousin_clan_kin: "从亲／族亲",
    marriage: "婚姻",
    affinal_relation: "姻亲",
    same_clan: "同族",
    superior_subordinate: "上下属",
    recruitment_served_under: "任用／事奉",
    teacher_student: "师生",
    documented_social_interaction: "社会交往事件",
    documented_political_interaction: "政治交往事件",
    shared_explicit_event: "共同事件",
    friendship: "友善关系候选",
    political_cooperation: "政治合作候选",
    political_opposition: "政治对立候选",
  }[relation.relation_type] ?? relation.relation_type;
  return `${level} · ${type}`;
}

function hng02StatusLabel(status: Hng02ReviewStatus): string {
  return {
    candidate: "候选",
    accepted: "接受",
    rejected: "拒绝",
    uncertain: "不确定",
    needs_more_evidence: "需要更多证据",
  }[status];
}

function hng02InitialReview(): Hng02ReviewOverlay {
  const relationDecisions: Hng02ReviewOverlay["relation_decisions"] = {};
  const temporalDecisions: Hng02ReviewOverlay["temporal_decisions"] = {};
  const identityDecisions: Hng02ReviewOverlay["identity_decisions"] = {};
  for (const relation of HNG02_SITE.relations) {
    relationDecisions[relation.relation_id] = { review_status: relation.review_status, reviewer_note: "" };
  }
  for (const item of HNG02_SITE.temporal_items) {
    temporalDecisions[item.temporal_id] = { review_status: item.review_status, reviewer_note: "" };
  }
  const saved = readHng02Review();
  return {
    schema: 1,
    stage: "hng0-2-local-review",
    canonical_write_back: false,
    relation_decisions: { ...relationDecisions, ...(saved?.relation_decisions ?? {}) },
    temporal_decisions: { ...temporalDecisions, ...(saved?.temporal_decisions ?? {}) },
    identity_decisions: { ...identityDecisions, ...(saved?.identity_decisions ?? {}) },
  };
}

function Hng02ReviewControls({
  status,
  onChange,
}: {
  status: Hng02ReviewStatus;
  onChange: (status: Hng02ReviewStatus) => void;
}) {
  const choices: Hng02ReviewStatus[] = ["accepted", "rejected", "uncertain", "needs_more_evidence"];
  return (
    <div className="hng0-review-controls" aria-label="HNG0.2 本地评审">
      {choices.map((choice) => (
        <button
          type="button"
          key={choice}
          className={status === choice ? "hng0-review-button active" : "hng0-review-button"}
          onClick={() => onChange(choice)}
        >
          {hng02StatusLabel(choice)}
        </button>
      ))}
    </div>
  );
}

function Hng02EvidenceDetails({
  refs,
  quotes,
}: {
  refs: string[];
  quotes?: Array<{ ref: string; quote: string }>;
}) {
  const quoteByRef = new Map((quotes ?? []).map((item) => [item.ref, item.quote]));
  return (
    <div className="hng0-evidence-panel selected">
      <p className="hng0-evidence-heading">Evidence · 证据 {refs.length} 条</p>
      {refs.map((ref) => {
        const evidence: Hng02Evidence | undefined = HNG02_SITE.evidence[ref];
        if (!evidence) return null;
        return (
          <article className="hng0-evidence-item" key={ref}>
            <p className="hng0-evidence-meta">{evidence.source_work} · {evidence.source_layer} · {ref}</p>
            <blockquote>{quoteByRef.get(ref) ?? evidence.original_text}</blockquote>
            <p className="hng0-evidence-provenance">{evidence.source_path ?? "来源定位未展开"} · {evidence.source_form ?? "legacy_local"}</p>
          </article>
        );
      })}
    </div>
  );
}

function hng02TimeLabel(item: Hng02TemporalItem): string {
  const start = item.temporal_scope?.start_year;
  const end = item.temporal_scope?.end_year;
  if (typeof start === "number" && typeof end === "number") return start === end ? `${start}` : `${start}–${end}`;
  if (typeof start === "number") return `${start}（${item.precision}）`;
  return `年代未定（${item.precision}）`;
}

function PersonHng02Surface({
  focusedPersonId,
  onFocus,
}: {
  focusedPersonId: string;
  onFocus: PersonFocus;
}) {
  const neighborhood = HNG02_SITE.people[focusedPersonId];
  const [review, setReview] = useState<Hng02ReviewOverlay>(hng02InitialReview);
  const [selectedRelationId, setSelectedRelationId] = useState<string | null>(null);
  const [selectedTemporalId, setSelectedTemporalId] = useState<string | null>(null);
  useEffect(() => {
    writeHng02Review(review);
  }, [review]);
  if (!neighborhood) return null;
  const relations = neighborhood.normalized_relations ?? [];
  const temporalItems = neighborhood.normalized_temporal_items ?? [];
  const relationStatus = (row: Hng02Relation): Hng02ReviewStatus => review.relation_decisions[row.relation_id]?.review_status ?? row.review_status;
  const temporalStatus = (row: Hng02TemporalItem): Hng02ReviewStatus => review.temporal_decisions[row.temporal_id]?.review_status ?? row.review_status;
  const setRelationStatus = (id: string, status: Hng02ReviewStatus) => setReview((current) => ({
    ...current,
    relation_decisions: { ...current.relation_decisions, [id]: { ...current.relation_decisions[id], review_status: status } },
  }));
  const setTemporalStatus = (id: string, status: Hng02ReviewStatus) => setReview((current) => ({
    ...current,
    temporal_decisions: { ...current.temporal_decisions, [id]: { ...current.temporal_decisions[id], review_status: status } },
  }));
  const selectedRelation = relations.find((row) => row.relation_id === selectedRelationId) ?? null;
  const selectedTemporal = temporalItems.find((row) => row.temporal_id === selectedTemporalId) ?? null;
  return (
    <section className="hng0-surface hng02-surface" aria-label="HNG0.2 一跳历史导航候选">
      <div className="hng0-heading-row">
        <div>
          <p className="relation-detail-heading">HNG0.2 Punctuated &amp; Resolved Neighborhood</p>
          <p className="hng0-subtitle">Newly extracted · normalized candidate · 证据可追溯，不写回历史事实</p>
        </div>
        <span className="hng0-status-note">{HNG02_SITE.execution_kind}</span>
      </div>
      <div className="hng0-summary-grid">
        <span>关系 {relations.length}</span>
        <span>时间条目 {temporalItems.length}</span>
        <span>邻居 {neighborhood.nearby_person_ids.length}</span>
      </div>
      <div className="hng0-section">
        <p className="relation-detail-heading">Relations · 一跳关系</p>
        {relations.length === 0 ? <p className="hng0-muted">当前人物没有 HNG0.2 候选关系。</p> : (
          <div className="hng0-graph" aria-label="HNG0.2 一跳关系候选">
            {relations.map((relation) => {
              const otherId = relation.person_a === focusedPersonId ? relation.person_b : relation.person_a;
              const otherName = relation.person_a === focusedPersonId
                ? relation.person_b_name ?? relation.provisional_neighbor_label ?? relation.counterpart_surface
                : relation.person_a_name;
              return (
                <div className="hng0-graph-row" key={relation.relation_id}>
                  <button type="button" className="hng0-node" disabled={!otherId} onClick={() => otherId && onFocus(otherId)}>{otherName ?? "未解析人物"}</button>
                  <button type="button" className={selectedRelationId === relation.relation_id ? "hng0-edge active" : "hng0-edge"} onClick={() => { setSelectedRelationId(relation.relation_id); setSelectedTemporalId(null); }}>
                    {hng02RelationLabel(relation)} · {hng02StatusLabel(relationStatus(relation))}
                  </button>
                </div>
              );
            })}
          </div>
        )}
        {selectedRelation && (
          <article className="hng0-detail-card">
            <div className="hng0-detail-title"><span>{selectedRelation.person_a_name ?? "未解析人物"} — {hng02RelationLabel(selectedRelation)} — {selectedRelation.person_b_name ?? selectedRelation.provisional_neighbor_label ?? selectedRelation.counterpart_surface}</span><span>{hng02StatusLabel(relationStatus(selectedRelation))}</span></div>
            <p className="hng0-detail-meta">{selectedRelation.claim} · 原始类型：{selectedRelation.original_relation_type} · {selectedRelation.certainty}</p>
            {selectedRelation.normalization_reason && <p className="hng0-muted">规范化：{selectedRelation.normalization_reason}</p>}
            {selectedRelation.temporal_warnings.length > 0 && <p className="hng0-muted">时间警告：{selectedRelation.temporal_warnings.join("；")}</p>}
            <Hng02ReviewControls status={relationStatus(selectedRelation)} onChange={(status) => setRelationStatus(selectedRelation.relation_id, status)} />
            <Hng02EvidenceDetails refs={selectedRelation.evidence_refs} quotes={selectedRelation.evidence_quotes} />
          </article>
        )}
      </div>
      <div className="hng0-section">
        <p className="relation-detail-heading">Timeline · 最小时间脊柱</p>
        {temporalItems.length === 0 ? <p className="hng0-muted">当前人物没有 HNG0.2 时间候选。</p> : (
          <div className="hng0-timeline">
            {temporalItems.map((item) => (
              <article className={item.precision === "exact" ? "hng0-timeline-item exact" : "hng0-timeline-item approximate"} key={item.temporal_id}>
                <button type="button" className="hng0-timeline-main" onClick={() => { setSelectedTemporalId(item.temporal_id); setSelectedRelationId(null); }}>
                  <span className="hng0-time-label">{hng02TimeLabel(item)}</span><span>{item.claim}</span><span className="hng0-time-kind">{item.temporal_type} · {hng02StatusLabel(temporalStatus(item))}</span>
                </button>
                {selectedTemporalId === item.temporal_id && (
                  <div className="hng0-detail-card inline">
                    <p className="hng0-detail-meta">{item.subject_resolution_status} · {item.certainty} · {item.source_works.join("／")}</p>
                    <Hng02ReviewControls status={temporalStatus(item)} onChange={(status) => setTemporalStatus(item.temporal_id, status)} />
                    <Hng02EvidenceDetails refs={item.evidence_refs} quotes={item.evidence_quotes} />
                  </div>
                )}
              </article>
            ))}
          </div>
        )}
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
  onRelationFocus,
  onStorySelect,
}: {
  story: Story;
  data: SiteBundle;
  focusedPerson: Person;
  perspectives: RelationPerspective[];
  readingMode: ReadingMode;
  routeNode: ExplorationNode | null;
  onFocus: PersonFocus;
  onRelationFocus: RelationFocus;
  onStorySelect: (storyId: string) => void;
}) {
  const derivedRelations = derivedRelationsForPerson(focusedPerson.id, data);
  const sketch = data.person_sketches[focusedPerson.id];
  const storyCounts = sketch?.story_counts;
  return (
    <section className="person-detail-card" aria-labelledby="focused-person-heading">
      <p className="section-label">{storyLabel(data, "focused_person_label", readingMode, "当前人物")}</p>
      <h3 id="focused-person-heading">{personDisplayName(story, data, focusedPerson, readingMode)}</h3>
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
      <PersonHng0Surface
        focusedPersonId={focusedPerson.id}
        data={data}
        readingMode={readingMode}
        onFocus={onFocus}
        onStorySelect={onStorySelect}
      />
      <PersonHng01Surface focusedPersonId={focusedPerson.id} onFocus={onFocus} />
      <PersonHng02Surface focusedPersonId={focusedPerson.id} onFocus={onFocus} />
      <PersonHistoricalProfile personId={focusedPerson.id} readingMode={readingMode} onFocus={onFocus} />
      <div className="relation-detail-group">
        <p className="relation-detail-heading">{uiLabel(data, "person_sketch_relations", readingMode, "人物关系")}</p>
        <p className="relation-detail-subheading">{storyLabel(data, "direct_relation_label", readingMode, "已审阅的直接关系")}</p>
        {perspectives.length === 0 && <p className="relation-empty">{storyLabel(data, "no_direct_relations", readingMode, "目前尚无已审核的人物关系。")}</p>}
        {perspectives.map((perspective) => (
          <div className="relation-detail-row" key={perspective.relation.id}>
            <button type="button" className="person-link" onClick={() => onRelationFocus(perspective)}>
              {personDisplayName(story, data, perspective.neighbor, readingMode)} · {perspectiveNeighborRole(story, data, perspective, readingMode)}
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
          <p className="relation-detail-heading">{storyLabel(data, "derived_relation_label", readingMode, "推得关系")}</p>
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
  onRelationFocus,
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
  onRelationFocus: RelationFocus;
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
          <p className="section-label">{storyLabel(data, "relation_section", readingMode, "人物关系")}</p>
          <h2 id="relation-explorer-heading">{personDisplayName(story, data, focusedPerson, readingMode)}</h2>
        </div>
        {backTarget && (
          <button type="button" className="back-button" onClick={onBack}>
            ← {storyLabel(data, "back_label", readingMode, "返回")} {backLabel}
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
          onRelationFocus={onRelationFocus}
          onStorySelect={onStorySelect}
        />
        <EgoRelationMap
          story={story}
          data={data}
          focusedPerson={focusedPerson}
          perspectives={perspectives}
          readingMode={readingMode}
          onRelationFocus={onRelationFocus}
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
  onRelationFocus,
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
  onRelationFocus: RelationFocus;
  onBack: () => void;
  onStorySelect: (storyId: string) => void;
  onClose: () => void;
}) {
  const surfaceRef = useExplorerDialog(onClose);
  if (!focusedPersonId) return null;
  return (
    <aside className="person-panel-shell" aria-label="人物探索">
      <button
        type="button"
        className="person-panel-backdrop"
        aria-label="关闭人物探索"
        tabIndex={-1}
        onClick={onClose}
      />
      <div ref={surfaceRef} className="person-panel-surface" role="dialog" aria-modal="true" aria-labelledby="relation-explorer-heading">
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
          onRelationFocus={onRelationFocus}
          onBack={onBack}
          onStorySelect={onStorySelect}
        />
      </div>
    </aside>
  );
}

function eraLabel(mode: ReadingMode, original: string, simplified: string = original): string {
  return mode === "original" ? original : simplified;
}

function useExplorerDialog(onClose: () => void) {
  const surfaceRef = useRef<HTMLDivElement>(null);
  const closeRef = useRef(onClose);
  closeRef.current = onClose;

  useEffect(() => {
    const previousFocus = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    surfaceRef.current?.querySelector<HTMLButtonElement>(".panel-close-button")?.focus();

    function handleKeyDown(event: globalThis.KeyboardEvent): void {
      if (event.key !== "Escape") return;
      event.preventDefault();
      closeRef.current();
    }

    document.addEventListener("keydown", handleKeyDown);
    return () => {
      document.removeEventListener("keydown", handleKeyDown);
      if (previousFocus?.isConnected) previousFocus.focus();
    };
  }, []);

  return surfaceRef;
}

function EraStoryLinks({
  card,
  data,
  readingMode,
  linkType,
  onStorySelect,
}: {
  card: EraCard;
  data: SiteBundle;
  readingMode: ReadingMode;
  linkType: "appears" | "referenced" | "reign_context";
  onStorySelect: (storyId: string) => void;
}) {
  const links = card.ruler_story_links.filter((link) => link.link_type === linkType);
  if (links.length === 0) return null;
  return (
    <div className="era-story-group">
      <p className="relation-detail-heading">
        {linkType === "appears"
          ? eraLabel(readingMode, "《世說》中的他", "《世说》中的他")
          : linkType === "referenced"
            ? eraLabel(readingMode, "被提及", "被提及")
            : eraLabel(readingMode, "這一時期", "这一时期")}
      </p>
      <div className="story-card-list">
        {links.map((link) => {
          const candidate = storyById(data, link.story_id);
          if (!candidate) return null;
          return (
            <StoryCard
              key={`${link.link_type}-${link.story_id}`}
              story={candidate}
              data={data}
              readingMode={readingMode}
              annotationOnly={false}
              onSelect={() => onStorySelect(candidate.id)}
            />
          );
        })}
      </div>
    </div>
  );
}

function EraOrientationStoryLinks({
  card,
  data,
  readingMode,
  onStorySelect,
}: {
  card: EraCard;
  data: SiteBundle;
  readingMode: ReadingMode;
  onStorySelect: (storyId: string) => void;
}) {
  if (card.card_kind === "ruler_reign" || card.story_ids.length === 0) return null;
  return (
    <div className="era-story-group">
      <p className="relation-detail-heading">{eraLabel(readingMode, "這一時期", "这一时期")}</p>
      <div className="story-card-list">
        {card.story_ids.map((storyId) => {
          const candidate = storyById(data, storyId);
          if (!candidate) return null;
          return (
            <StoryCard
              key={storyId}
              story={candidate}
              data={data}
              readingMode={readingMode}
              annotationOnly={false}
              onSelect={() => onStorySelect(storyId)}
            />
          );
        })}
      </div>
    </div>
  );
}

function EraCardDetail({
  story,
  data,
  card,
  readingMode,
  onFocus,
  onStorySelect,
}: {
  story: Story;
  data: SiteBundle;
  card: EraCard;
  readingMode: ReadingMode;
  onFocus: PersonFocus;
  onStorySelect: (storyId: string) => void;
}) {
  const directByStory = new Map<string, EraCard["ruler_story_links"][number]>();
  for (const link of card.ruler_story_links) {
    if (link.link_type !== "appears" && link.link_type !== "referenced") continue;
    const existing = directByStory.get(link.story_id);
    if (!existing || (existing.link_type === "referenced" && link.link_type === "appears")) {
      directByStory.set(link.story_id, link);
    }
  }
  const directLinks = [...directByStory.values()];
  const appearsLinks = directLinks.filter((link) => link.link_type === "appears");
  const referencedLinks = directLinks.filter((link) => link.link_type === "referenced");
  const directStories = new Set(directLinks.map((link) => link.story_id));
  const contextLinks = card.ruler_story_links.filter(
    (link) => link.link_type === "reign_context" && !directStories.has(link.story_id),
  );
  const events = card.historical_event_ids
    .map((id) => data.historical_events.find((event) => event.id === id))
    .filter((event): event is SiteBundle["historical_events"][number] => Boolean(event));
  events.sort((left, right) => (
    (left.start_year_ce ?? Number.POSITIVE_INFINITY) - (right.start_year_ce ?? Number.POSITIVE_INFINITY)
    || (left.end_year_ce ?? Number.POSITIVE_INFINITY) - (right.end_year_ce ?? Number.POSITIVE_INFINITY)
    || left.id.localeCompare(right.id)
  ));
  return (
    <section className="era-detail-card" aria-labelledby="focused-era-heading">
      <div className="era-card-identity">
        <p className="section-label">{eraLabel(readingMode, "紀元", "纪元")}</p>
        <h3 id="focused-era-heading">{readingValue(card.title, readingMode, "紀元")}</h3>
        {card.personal_name && <p className="era-card-personal-name">{readingValue(card.personal_name, readingMode, "")}</p>}
        {readingValue(card.reign_label, readingMode, "") && (
          <p className="era-card-reign">{readingValue(card.reign_label, readingMode, "")}</p>
        )}
        <div className="era-name-strip" aria-label={eraLabel(readingMode, "年號序列", "年号序列")}>
          {card.era_names.map((era) => (
            <span key={era.reign_period_id} className="era-name-chip">
              {readingValue(era.name, readingMode, "")}
              {typeof era.start_year_ce === "number" && typeof era.end_year_ce === "number" && (
                <small>{era.start_year_ce}–{era.end_year_ce}</small>
              )}
            </span>
          ))}
        </div>
      </div>

      <section className="era-context-block">
        <p className="relation-detail-heading">{eraLabel(readingMode, "時代一瞥", "时代一瞥")}</p>
        <p>{readingValue(card.era_context.text, readingMode, "")}</p>
      </section>

      <EraStoryLinks card={{ ...card, ruler_story_links: appearsLinks }} data={data} readingMode={readingMode} linkType="appears" onStorySelect={onStorySelect} />
      <EraStoryLinks card={{ ...card, ruler_story_links: referencedLinks }} data={data} readingMode={readingMode} linkType="referenced" onStorySelect={onStorySelect} />
      <EraOrientationStoryLinks card={card} data={data} readingMode={readingMode} onStorySelect={onStorySelect} />

      {card.person_intersections.length > 0 && (
        <section className="era-intersections">
          <p className="relation-detail-heading">{eraLabel(readingMode, "人物交集", "人物交集")}</p>
          <div className="era-person-list">
            {card.person_intersections.map((intersection) => {
              const person = data.people.find((candidate) => candidate.id === intersection.person_id);
              if (!person) return null;
              return (
                <button
                  type="button"
                  className="era-person-link"
                  key={intersection.person_id}
                  onClick={() => onFocus(intersection.person_id)}
                >
                  {personDisplayName(story, data, person, readingMode)} · {intersection.story_count}{eraLabel(readingMode, "則", "则")}
                </button>
              );
            })}
          </div>
        </section>
      )}

      {contextLinks.length > 0 && (
        <EraStoryLinks
          card={{ ...card, ruler_story_links: contextLinks }}
          data={data}
          readingMode={readingMode}
          linkType="reign_context"
          onStorySelect={onStorySelect}
        />
      )}

      {events.length > 0 && (
        <section className="era-events">
          <p className="relation-detail-heading">{eraLabel(readingMode, "時代節點", "时代节点")}</p>
          {events.map((event) => (
            <article className="era-event-row" key={event.id}>
              <span>{readingValue(event.canonical_name, readingMode, "")}</span>
              {typeof event.start_year_ce === "number" && typeof event.end_year_ce === "number" && (
                <small>{event.start_year_ce}–{event.end_year_ce}</small>
              )}
            </article>
          ))}
        </section>
      )}
      <EraHistoricalDepth
        eraId={card.era_card_id}
        readingMode={readingMode}
        onFocus={onFocus}
        onStorySelect={onStorySelect}
      />
    </section>
  );
}

function EraExplorerPanel({
  story,
  data,
  focusedEraId,
  focusedEraNode,
  readingMode,
  backTarget,
  onFocus,
  onBack,
  onStorySelect,
  onClose,
}: {
  story: Story;
  data: SiteBundle;
  focusedEraId: string | null;
  focusedEraNode: ExplorationNode | null;
  readingMode: ReadingMode;
  backTarget: ExplorationNode | null;
  onFocus: PersonFocus;
  onBack: () => void;
  onStorySelect: (storyId: string) => void;
  onClose: () => void;
}) {
  const surfaceRef = useExplorerDialog(onClose);
  if (!focusedEraId) return null;
  const card = data.era_cards.find((candidate) => candidate.era_card_id === focusedEraId);
  if (!card) return null;
  const backLabel = backTarget?.kind === "person"
    ? personNameById(story, data, backTarget.id, readingMode)
    : backTarget?.kind === "era"
      ? data.era_cards.find((candidate) => candidate.era_card_id === backTarget.id)?.orientation_label[readingMode] ?? eraLabel(readingMode, "紀元", "纪元")
      : backTarget?.kind === "story"
        ? storyReference(storyById(data, backTarget.id) ?? story, readingMode)
        : "";
  return (
    <aside className="person-panel-shell era-panel-shell" aria-label={eraLabel(readingMode, "紀元探索", "纪元探索")}>
      <button type="button" className="person-panel-backdrop" aria-label={eraLabel(readingMode, "關閉紀元探索", "关闭纪元探索")} tabIndex={-1} onClick={onClose} />
      <div ref={surfaceRef} className="person-panel-surface era-panel-surface" role="dialog" aria-modal="true" aria-labelledby="focused-era-heading">
        <div className="person-panel-toolbar">
          <span>{eraLabel(readingMode, "紀元", "纪元")}</span>
          <button type="button" className="panel-close-button" onClick={onClose} aria-label={eraLabel(readingMode, "關閉紀元探索", "关闭纪元探索")}>×</button>
        </div>
        {backTarget && (
          <button type="button" className="back-button era-panel-back" onClick={onBack}>
            ← {eraLabel(readingMode, "返回", "返回")} {backLabel}
          </button>
        )}
        <EraCardDetail
          story={story}
          data={data}
          card={card}
          readingMode={readingMode}
          onFocus={onFocus}
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
      <summary>{storyLabel(data, "evidence_heading", readingMode, "证据与出处")}</summary>
      <p className="evidence-intro">{storyLabel(data, "evidence_intro", readingMode, "以下资讯来自已验证的 WP1 静态资料；artifact 是页面所引用的派生档案，source provenance 保留其上游见证资讯。")}</p>
      <div className="evidence-list">
        {evidence.map((item) => (
          <article className="evidence-item" key={item.id}>
            <div className="evidence-heading">
              <span>
                {item.evidence_type}
                {sourceDisplay(data, item.source_id) && (
                  <> · {sourceDisplay(data, item.source_id)?.work[readingMode]} · {sourceDisplay(data, item.source_id)?.edition[readingMode]}</>
                )}
              </span>
              <code>{item.id}</code>
            </div>
            <blockquote>{readingValue(evidenceDisplay(data, item.id), readingMode, item.quote)}</blockquote>
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
      const name = resolved ? personDisplayName(story, data, resolved, readingMode) : readingValue(person.surface, readingMode, person.person_id);
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
            const source = sourceDisplay(data, item.source_id);
            return (
              <article key={item.id}>
                <p>{source ? `${source.work[readingMode]} · ${source.edition[readingMode]}` : item.source_id}</p>
                <blockquote>{readingValue(evidenceDisplay(data, item.id), readingMode, item.quote)}</blockquote>
                <FeedbackButton
                  data={data}
                  storyId={story.id}
                  targetType="evidence"
                  targetId={item.id}
                  targetTextSnapshot={readingValue(evidenceDisplay(data, item.id), readingMode, item.quote)}
                  label="反馈此依据"
                />
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
  if (node.kind === "era") {
    const card = data.era_cards.find((candidate) => candidate.era_card_id === node.id);
    return card ? readingValue(card.orientation_label, mode, eraLabel(mode, "紀元", "纪元")) : eraLabel(mode, "紀元", "纪元");
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
  onEraFocus,
}: {
  story: Story;
  data: SiteBundle;
  readingMode: ReadingMode;
  setReadingMode: (mode: ReadingMode) => void;
  focusedPersonId: string | null;
  onFocus: PersonFocus;
  onEraFocus: EraFocus;
}) {
  const readerRef = useRef<HTMLDivElement>(null);
  const [openAnnotationIds, setOpenAnnotationIds] = useState<Set<string>>(() => new Set());
  const [storyView, setStoryView] = useState<"original" | "sketch">("original");
  const [storySketch, setStorySketch] = useState<StorySketchProjection | null>(null);
  const [storySketchLoading, setStorySketchLoading] = useState(false);
  const [storySketchFailed, setStorySketchFailed] = useState(false);
  const mentions = resolvedMentions(story, data);
  const mainTextMentions = mentions.filter((mention) => mention.section === "main_text");
  const annotationMentions = mentions.filter((mention) => mention.section === "liu_annotation");
  const primaryEraCard = data.era_cards.find((card) => card.era_card_id === story.primary_era_card_id);
  const storySketchAvailable = NL0_STORY_SKETCH_ENABLED && NL0_STORY_IDS.has(story.id);

  useEffect(() => {
    setOpenAnnotationIds(new Set());
    setStoryView("original");
    setStorySketch(null);
    setStorySketchLoading(false);
    setStorySketchFailed(false);
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

  async function chooseStoryView(next: "original" | "sketch"): Promise<void> {
    setStoryView(next);
    if (next !== "sketch" || storySketch || storySketchFailed) return;
    setStorySketchLoading(true);
    try {
      setStorySketch(await loadStorySketch(story.id));
    } catch {
      setStorySketchFailed(true);
    } finally {
      setStorySketchLoading(false);
    }
  }

  return (
    <div className="story-reader-stage" ref={readerRef} tabIndex={-1} aria-labelledby="story-heading">
      <article className="reading-column">
        <h1 id="story-heading">{storyReference(story, readingMode)}</h1>
        {primaryEraCard && (
          <button
            type="button"
            className="story-era-orientation"
            onClick={() => onEraFocus(primaryEraCard.era_card_id)}
            aria-label={readingValue(primaryEraCard.orientation_label, readingMode, "纪元")}
          >
            {readingValue(primaryEraCard.orientation_label, readingMode, "纪元")} ›
          </button>
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
          {storySketchAvailable && (
            <div className="nl0-view-controls" role="group" aria-label="Story view">
              <button
                type="button"
                className={storyView === "original" ? "nl0-view-button active" : "nl0-view-button"}
                aria-pressed={storyView === "original"}
                onClick={() => void chooseStoryView("original")}
              >
                Original
              </button>
              <span className="nl0-view-separator" aria-hidden="true">|</span>
              <button
                type="button"
                className={storyView === "sketch" ? "nl0-view-button active" : "nl0-view-button"}
                aria-pressed={storyView === "sketch"}
                onClick={() => void chooseStoryView("sketch")}
              >
                Sketch
              </button>
            </div>
          )}
          <p className={story.publication_state === "preview_ready" ? "publication-note preview" : "publication-note"}>
            {story.publication_state === "preview_ready"
              ? uiLabel(data, "preview_punctuation", readingMode, "句读：参考底本整理 · 待复核")
              : uiLabel(data, "reviewed_punctuation", readingMode, "句读：已复核")}
          </p>
          <FeedbackButton
            data={data}
            storyId={story.id}
            targetType="story"
            targetId={story.id}
            targetTextSnapshot={readingValue(story.reading.main_text, readingMode, story.text)}
          />
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
              onEraFocus={onEraFocus}
              annotations={story.reading.annotations}
              openAnnotationIds={openAnnotationIds}
              onToggleAnnotation={toggleAnnotation}
            />
          </p>
        </section>

        {storyView === "sketch" ? (
          storySketchLoading ? (
            <p className="nl0-sketch-loading">历史素描载入中…</p>
          ) : storySketchFailed ? (
            <p className="nl0-sketch-unavailable">Story Sketch 暂时不可用。</p>
          ) : storySketch ? (
            <StorySketchView value={storySketch} data={data} readingMode={readingMode} />
          ) : (
            <p className="nl0-sketch-unavailable">本则暂无已审阅 Story Sketch。</p>
          )
        ) : (
          <SceneCard story={story} data={data} readingMode={readingMode} onFocus={onFocus} />
        )}

        <StoryHistoricalDepth storyId={story.id} data={data} readingMode={readingMode} onFocus={onFocus} />

        <section className="annotation-hook" aria-label="进一步读">
          <p className="section-label">进一步读</p>
          <details className="annotation-index">
            <summary>
              {storyLabel(data, "annotation_label", readingMode, "刘孝标注")} · {story.reading.annotations.length}条
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
                      onEraFocus={onEraFocus}
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

        <section className="people-section" aria-labelledby="people-heading" aria-label={storyLabel(data, "people_section", readingMode, "人物")}>
          <div className="section-heading">
            <p className="section-label">{storyLabel(data, "people_section", readingMode, "人物")}</p>
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

function UX2IndexPage({
  readingMode,
  onPersonSelect,
  onStorySelect,
}: {
  readingMode: ReadingMode;
  onPersonSelect: (personId: string) => void;
  onStorySelect: (storyId: string) => void;
}) {
  const [index, setIndex] = useState<{ people: PersonIndexRecord[]; stories: StoryIndexRecord[] } | null>(null);
  const [loading, setLoading] = useState(true);
  const [failed, setFailed] = useState(false);
  const [tab, setTab] = useState<"people" | "stories">("people");
  const [query, setQuery] = useState("");

  useEffect(() => {
    let active = true;
    void loadUX2Index()
      .then((projection) => {
        if (!active) return;
        setIndex({ people: projection.people.records, stories: projection.stories.records });
        setLoading(false);
      })
      .catch(() => {
        if (!active) return;
        setLoading(false);
        setFailed(true);
      });
    return () => {
      active = false;
    };
  }, []);

  const normalizedQuery = query.trim().toLocaleLowerCase();
  const people = (index?.people ?? []).filter((person) => {
    if (!normalizedQuery) return true;
    return [person.name.original, person.name.simplified, person.surname.original, person.surname.simplified]
      .some((value) => value.toLocaleLowerCase().includes(normalizedQuery));
  });
  const peopleBySurname = new Map<string, PersonIndexRecord[]>();
  for (const person of people) {
    const key = readingMode === "original" ? person.surname.original : person.surname.simplified;
    const rows = peopleBySurname.get(key) ?? [];
    rows.push(person);
    peopleBySurname.set(key, rows);
  }
  const storiesByCategory = new Map<string, StoryIndexRecord[]>();
  for (const story of index?.stories ?? []) {
    const rows = storiesByCategory.get(story.category_id) ?? [];
    rows.push(story);
    storiesByCategory.set(story.category_id, rows);
  }

  return (
    <main className="page-shell ux2-index-page">
      <header className="site-header">
        <div>
          <p className="brand">世说Sketch</p>
          <h1 className="ux2-index-title">人物与篇目</h1>
          <p className="tagline">从索引回到故事，也从故事认识人物</p>
        </div>
        <a className="ux2-index-back" href={import.meta.env.BASE_URL}>返回阅读</a>
      </header>
      <nav className="ux2-index-tabs" aria-label="索引分类" role="tablist">
        <button
          type="button"
          role="tab"
          aria-selected={tab === "people"}
          className={tab === "people" ? "ux2-index-tab active" : "ux2-index-tab"}
          onClick={() => setTab("people")}
        >
          人物
        </button>
        <button
          type="button"
          role="tab"
          aria-selected={tab === "stories"}
          className={tab === "stories" ? "ux2-index-tab active" : "ux2-index-tab"}
          onClick={() => setTab("stories")}
        >
          篇目
        </button>
      </nav>

      {loading && <p className="ux2-index-status">索引载入中…</p>}
      {failed && <p className="ux2-index-status">索引暂时不可用。</p>}
      {!loading && !failed && index && tab === "people" && (
        <section className="ux2-index-section" aria-labelledby="ux2-people-heading">
          <div className="ux2-index-section-heading">
            <div>
              <p className="section-label">人物</p>
              <h2 id="ux2-people-heading">《世说》人物</h2>
            </div>
            <label className="ux2-index-search">
              <span>查找人物</span>
              <input
                type="search"
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                placeholder="姓名"
                aria-label="查找人物"
              />
            </label>
          </div>
          <div className="ux2-index-groups">
            {[...peopleBySurname.entries()].map(([surname, rows]) => (
              <section className="ux2-index-group" key={surname}>
                <h3>{surname}</h3>
                <div className="ux2-index-person-list">
                  {rows.map((person) => (
                    <button
                      type="button"
                      className="ux2-index-person"
                      key={person.person_id}
                      data-person-id={person.person_id}
                      onClick={() => onPersonSelect(person.person_id)}
                    >
                      {readingMode === "original" ? person.name.original : person.name.simplified}
                    </button>
                  ))}
                </div>
              </section>
            ))}
          </div>
          {people.length === 0 && <p className="ux2-index-status">没有符合条件的人物。</p>}
        </section>
      )}
      {!loading && !failed && index && tab === "stories" && (
        <section className="ux2-index-section" aria-labelledby="ux2-stories-heading">
          <div className="ux2-index-section-heading">
            <div>
              <p className="section-label">篇目</p>
              <h2 id="ux2-stories-heading">《世说新语》门类</h2>
            </div>
            <span className="ux2-index-count">{index.stories.length} 则</span>
          </div>
          <div className="ux2-index-groups">
            {[...storiesByCategory.entries()].map(([categoryId, rows]) => {
              const label = readingMode === "original" ? rows[0].category.original : rows[0].category.simplified;
              return (
                <section className="ux2-index-group" key={categoryId}>
                  <h3>{label}</h3>
                  <div className="ux2-index-story-list">
                    {rows.map((story) => (
                      <button
                        type="button"
                        className="ux2-index-story"
                        key={story.story_id}
                        data-story-id={story.story_id}
                        onClick={() => onStorySelect(story.story_id)}
                      >
                        {readingMode === "original" ? story.reference.original : story.reference.simplified}
                      </button>
                    ))}
                  </div>
                </section>
              );
            })}
          </div>
        </section>
      )}
    </main>
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
  focusedEraId,
  focusedEraNode,
  personPanelOpen,
  eraPanelOpen,
  onFocus,
  onRelationFocus,
  onEraFocus,
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
  focusedEraId: string | null;
  focusedEraNode: ExplorationNode | null;
  personPanelOpen: boolean;
  eraPanelOpen: boolean;
  onFocus: PersonFocus;
  onRelationFocus: RelationFocus;
  onEraFocus: EraFocus;
  onBack: () => void;
  onStorySelect: (storyId: string) => void;
  onPathSelect: (index: number) => void;
  onClosePerson: () => void;
  onRandomPerson: () => void;
  onRandomStory: () => void;
}) {
  const backTarget = stack.length > 1 && (personPanelOpen || eraPanelOpen) ? stack[stack.length - 2] ?? null : null;
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
          <a className="index-link" href={`${import.meta.env.BASE_URL}index`} target="_blank" rel="noreferrer">
            人物 / 篇目
          </a>
          <a className="index-link" href={`${import.meta.env.BASE_URL}review/hdb2`}>
            HDB2 人物审阅
          </a>
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

      <div className={personPanelOpen || eraPanelOpen ? "exploration-layout with-person-panel" : "exploration-layout"}>
        <StoryReader
          key={story.id}
          story={story}
          data={data}
          readingMode={readingMode}
          setReadingMode={setReadingMode}
          focusedPersonId={focusedPersonId}
          onFocus={onFocus}
          onEraFocus={onEraFocus}
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
            onRelationFocus={onRelationFocus}
            onBack={onBack}
            onStorySelect={onStorySelect}
            onClose={onClosePerson}
          />
        )}
        {eraPanelOpen && focusedEraId && (
          <EraExplorerPanel
            story={story}
            data={data}
            focusedEraId={focusedEraId}
            focusedEraNode={focusedEraNode}
            readingMode={readingMode}
            backTarget={backTarget}
            onFocus={onFocus}
            onBack={onBack}
            onStorySelect={onStorySelect}
            onClose={onClosePerson}
          />
        )}
      </div>

      <FeedbackReviewPanel storyId={story.id} />

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
  const [eraPanelOpen, setEraPanelOpen] = useState(false);
  const [indexPage, setIndexPage] = useState(isIndexLocation);
  const initialized = useRef(false);

  useEffect(() => {
    if (initialized.current) return;
    initialized.current = true;
    if (isIRRReviewLocation() || isHDB2ReviewLocation()) return;
    try {
      const loaded = loadSiteBundle();
      const storyId = initialStoryId(loaded);
      setData(loaded);
      setStack([{ kind: "story", id: storyId }]);
      if (!isIndexLocation()) writeStoryAddress(storyId);
    } catch (reason: unknown) {
      setError(reason instanceof Error ? reason.message : String(reason));
    }
  }, []);

  useEffect(() => {
    if (!data || typeof window === "undefined") return;
    const loadedData = data;

    function syncFromAddress(): void {
      if (isIndexLocation()) {
        setIndexPage(true);
        setPersonPanelOpen(false);
        setEraPanelOpen(false);
        return;
      }
      const addressedId = storyIdFromHash(window.location.hash);
      const addressed = addressedId ? storyById(loadedData, addressedId) : undefined;
      if (!addressed || addressed.publication_state === "blocked") return;
      setIndexPage(false);
      setStack([{ kind: "story", id: addressed.id }]);
      setPersonPanelOpen(false);
      setEraPanelOpen(false);
    }

    window.addEventListener("popstate", syncFromAddress);
    window.addEventListener("hashchange", syncFromAddress);
    return () => {
      window.removeEventListener("popstate", syncFromAddress);
      window.removeEventListener("hashchange", syncFromAddress);
    };
  }, [data]);

  const publishedStoryIdSet = useMemo(
    () => (data ? new Set(publishedStoryIds(data)) : undefined),
    [data],
  );

  const story = useMemo(() => {
    if (!data || stack.length === 0) return undefined;
    const storyId = currentStoryFromExploration(stack, publishedStoryIdSet);
    return storyId ? storyById(data, storyId) : undefined;
  }, [data, publishedStoryIdSet, stack]);
  const currentFocusedPersonId = focusedPersonFromExploration(stack);
  const currentFocusedPersonNode = focusedPersonNodeFromExploration(stack);
  const currentFocusedEraId = focusedEraFromExploration(stack);
  const currentFocusedEraNode = focusedEraNodeFromExploration(stack);

  if (isIRRReviewLocation()) {
    return <IRRReviewPage />;
  }
  if (isHDB2ReviewLocation()) {
    return <HDB2ReviewPage />;
  }

  function focusPerson(personId: string, route?: PersonMentionRoute) {
    if (!data?.people.some((person) => person.id === personId)) return;
    setStack((current) => appendExploration(current, {
      kind: "person",
      id: personId,
      ...(route ?? {}),
    }));
    setPersonPanelOpen(true);
    setEraPanelOpen(false);
  }

  function focusRelation(perspective: RelationPerspective) {
    if (!data || !currentFocusedPersonId) return;
    if (!data.people.some((person) => person.id === perspective.neighbor.id)) return;
    const currentStoryId = currentStoryFromExploration(stack, publishedStoryIdSet) ?? undefined;
    const contextStoryId = relationContextStoryId(
      data,
      perspective.relation,
      perspective.neighbor.id,
      currentStoryId,
    );
    const route: PersonRelationRoute = {
      via_relation_id: perspective.relation.id,
      from_person_id: currentFocusedPersonId,
      ...(contextStoryId ? { context_story_id: contextStoryId } : {}),
    };
    const next = appendExploration(stack, {
      kind: "person",
      id: perspective.neighbor.id,
      ...route,
    });
    setStack(next);
    setPersonPanelOpen(true);
    setEraPanelOpen(false);
    const visibleStoryId = currentStoryFromExploration(next, publishedStoryIdSet);
    if (visibleStoryId) writeStoryAddress(visibleStoryId);
  }

  function focusPersonFromIndex(personId: string): void {
    if (!data?.people.some((person) => person.id === personId)) return;
    const storyId = randomPublishedStoryIdForPerson(data, personId, () => 0)
      ?? currentStoryFromExploration(stack, publishedStoryIdSet)
      ?? publishedStoryIds(data)[0];
    if (!storyId) return;
    setIndexPage(false);
    setStack([{ kind: "story", id: storyId }, { kind: "person", id: personId }]);
    setPersonPanelOpen(true);
    setEraPanelOpen(false);
    writeStoryAddress(storyId, "push", import.meta.env.BASE_URL);
  }

  function focusEra(eraCardId: string) {
    if (!data?.era_cards.some((card) => card.era_card_id === eraCardId)) return;
    setStack((current) => appendExploration(current, { kind: "era", id: eraCardId }));
    setPersonPanelOpen(false);
    setEraPanelOpen(true);
  }

  function selectStory(storyId: string) {
    if (!data?.stories.some((candidate) => candidate.id === storyId && candidate.publication_state !== "blocked")) return;
    const next = appendExploration(stack, { kind: "story", id: storyId });
    setStack(next);
    setPersonPanelOpen(false);
    setEraPanelOpen(false);
    writeStoryAddress(storyId, "push");
  }

  function selectStoryFromIndex(storyId: string): void {
    if (!data?.stories.some((storyCandidate) => storyCandidate.id === storyId && storyCandidate.publication_state !== "blocked")) return;
    setIndexPage(false);
    setStack([{ kind: "story", id: storyId }]);
    setPersonPanelOpen(false);
    setEraPanelOpen(false);
    writeStoryAddress(storyId, "push", import.meta.env.BASE_URL);
  }

  function goBack() {
    const next = backExploration(stack);
    setStack(next);
    setPersonPanelOpen(next[next.length - 1]?.kind === "person");
    setEraPanelOpen(next[next.length - 1]?.kind === "era");
    const storyId = currentStoryFromExploration(next, publishedStoryIdSet);
    if (storyId) writeStoryAddress(storyId);
  }

  function selectPath(index: number) {
    const next = truncateExploration(stack, index);
    setStack(next);
    setPersonPanelOpen(next[next.length - 1]?.kind === "person");
    setEraPanelOpen(next[next.length - 1]?.kind === "era");
    const storyId = currentStoryFromExploration(next, publishedStoryIdSet);
    if (storyId) writeStoryAddress(storyId);
  }

  function chooseRandomStory() {
    if (!data) return;
    const storyId = randomPublishedStoryId(data, Math.random, currentStoryFromExploration(stack, publishedStoryIdSet) ?? undefined);
    if (!storyId) return;
    setStack([{ kind: "story", id: storyId }]);
    setPersonPanelOpen(false);
    setEraPanelOpen(false);
    writeStoryAddress(storyId, "push");
  }

  function chooseRandomPerson() {
    if (!data) return;
    const personId = randomEligiblePersonId(data, Math.random, currentFocusedPersonId ?? undefined);
    if (!personId) return;
    const storyId = randomPublishedStoryIdForPerson(
      data,
      personId,
      Math.random,
      currentStoryFromExploration(stack, publishedStoryIdSet) ?? undefined,
    );
    if (!storyId) return;
    setStack([
      { kind: "story", id: storyId },
      { kind: "person", id: personId },
    ]);
    setPersonPanelOpen(true);
    setEraPanelOpen(false);
    writeStoryAddress(storyId, "push");
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
  if (!data) {
    return (
      <main className="page-shell loading-state">
        <p className="brand">世说Sketch</p>
        <p>正在读取故事……</p>
      </main>
    );
  }
  if (indexPage) {
    return (
      <UX2IndexPage
        readingMode={readingMode}
        onPersonSelect={focusPersonFromIndex}
        onStorySelect={selectStoryFromIndex}
      />
    );
  }
  if (!story) {
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
      focusedEraId={currentFocusedEraId}
      focusedEraNode={currentFocusedEraNode}
      personPanelOpen={personPanelOpen}
      eraPanelOpen={eraPanelOpen}
      onFocus={focusPerson}
      onRelationFocus={focusRelation}
      onEraFocus={focusEra}
      onBack={goBack}
      onStorySelect={selectStory}
      onPathSelect={selectPath}
      onClosePerson={() => { setPersonPanelOpen(false); setEraPanelOpen(false); }}
      onRandomPerson={chooseRandomPerson}
      onRandomStory={chooseRandomStory}
    />
  );
}

export default App;
