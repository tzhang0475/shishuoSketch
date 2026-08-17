import { useEffect, useMemo, useState } from "react";
import {
  loadIRRGold,
  loadIRRReviewBundle,
  type IRRClaim,
  type IRRComparison,
  type IRRDeltaItem,
  type IRREvidence,
  type IRRGoldRecord,
  type IRRGoldRound,
  type IRRGainVector,
  type IRRModelOutput,
  type IRRModelRecord,
  type IRRReviewBundle,
  type IRRReviewMode,
  type IRRReadingDelta,
  type IRRScoredRound,
} from "./irrReview";

const PILOT_STORIES = [
  "27-jiajue-008",
  "06-yaliang-017",
  "09-pinzao-017",
  "19-xianyuan-026",
  "05-fangzheng-032",
];
const REVIEW_STORAGE_KEY = "shishuoSketch.irr0-2-blind-review";
const REVIEW_OPTIONS = ["明显深化", "轻微深化", "无明显变化", "变差"] as const;
type ReviewChoice = typeof REVIEW_OPTIONS[number];

function recordFor(records: IRRModelRecord[], storyId: string): IRRModelRecord | undefined {
  return records.find((record) => record.story_id === storyId);
}

function asRecord(value: unknown): Record<string, unknown> {
  return value && typeof value === "object" && !Array.isArray(value)
    ? value as Record<string, unknown>
    : {};
}

function asClaims(value: unknown): IRRClaim[] {
  if (!Array.isArray(value)) return [];
  return value.flatMap((row) => {
    if (!row || typeof row !== "object") return [];
    const current = row as Record<string, unknown>;
    const text = current.text ?? current.state ?? current.description ?? current.question;
    if (typeof text !== "string" || !text) return [];
    return [{
      text,
      evidence_refs: Array.isArray(current.evidence_refs) ? current.evidence_refs.map(String) : [],
      status: typeof current.status === "string" ? current.status : undefined,
    }];
  });
}

function claimText(claim: IRRClaim): string {
  return claim.text;
}

function evidenceLabel(refs: string[]): string {
  return refs.length > 0 ? `依据 ${refs.join("、")}` : "原文输入";
}

function ModelReading({ output }: { output: IRRModelOutput }) {
  const history = output.historical_reading;
  const groups: Array<[string, IRRClaim[]]> = [
    ["在场与人物", history.participant_states],
    ["关系", history.relationship_states],
    ["前情", history.prior_events],
    ["后续", history.later_events],
    ["场景压力", history.scene_pressure],
    ["不确定", history.uncertainties],
  ];
  return (
    <div className="irr0-model-reading">
      <section className="irr0-reading-block">
        <p className="irr0-label">历史理解</p>
        {history.era && <p className="irr0-era-line">{history.era}</p>}
        {groups.map(([label, claims]) => claims.length > 0 && (
          <div className="irr0-claim-group" key={label}>
            <p className="irr0-sublabel">{label}</p>
            <ul>
              {claims.map((claim, index) => (
                <li key={`${label}-${index}`}>
                  {claimText(claim)} <small>{evidenceLabel(claim.evidence_refs)}</small>
                </li>
              ))}
            </ul>
          </div>
        ))}
      </section>

      <section className="irr0-reading-block">
        <p className="irr0-label">语言焦点</p>
        <div className="irr0-span-list">
          {output.text_reading.salient_spans.map((span, index) => (
            <article className="irr0-span-card" key={`${span.span}-${index}`}>
              <p className="irr0-span-text">{span.span}</p>
              <p>{span.literal_meaning}</p>
              {span.contextual_meaning && <p className="irr0-muted">{span.contextual_meaning}</p>}
              <small>自评深度 {span.depth_self_assessment} · {evidenceLabel(span.evidence_refs)}</small>
            </article>
          ))}
        </div>
      </section>

      <section className="irr0-reading-block">
        <p className="irr0-label">审美阅读</p>
        {output.aesthetic_reading.map((item, index) => (
          <article className="irr0-aesthetic-item" key={`${item.span}-${index}`}>
            <p><strong>{item.span}</strong> · {item.operations.join("、") || "未指定操作"}</p>
            {item.omitted_context.length > 0 && <p className="irr0-muted">省略：{item.omitted_context.join("；")}</p>}
            {item.interpretation && <p>{item.interpretation}</p>}
            <small>{evidenceLabel(item.evidence_refs)}</small>
          </article>
        ))}
      </section>

      <section className="irr0-reading-block">
        <p className="irr0-label">开放问题</p>
        <ul>
          {output.open_questions.map((item, index) => (
            <li key={`${item.question}-${index}`}>{item.question} <small>{evidenceLabel(item.evidence_refs)}</small></li>
          ))}
        </ul>
      </section>
    </div>
  );
}

function GoldReading({ round }: { round: IRRGoldRound }) {
  const historical = asRecord(round.historical_reading);
  const era = asRecord(historical.era);
  const groups: Array<[string, IRRClaim[]]> = [
    ["人物", asClaims(historical.participant_states)],
    ["关系", asClaims(historical.relationship_states)],
    ["前情", asClaims(historical.prior_events)],
    ["后续", asClaims(historical.later_events)],
    ["场景压力", asClaims(historical.scene_pressure)],
    ["不确定", asClaims(historical.uncertainties)],
  ];
  return (
    <div className="irr0-gold-reading">
      <section className="irr0-reading-block">
        <p className="irr0-label">Gold 历史理解</p>
        {typeof era.label === "string" && <p className="irr0-era-line">{era.label}</p>}
        {groups.map(([label, claims]) => claims.length > 0 && (
          <div className="irr0-claim-group" key={label}>
            <p className="irr0-sublabel">{label}</p>
            <ul>{claims.map((claim, index) => <li key={`${label}-${index}`}>{claimText(claim)} <small>{evidenceLabel(claim.evidence_refs)}</small></li>)}</ul>
          </div>
        ))}
      </section>
      <section className="irr0-reading-block">
        <p className="irr0-label">Gold 关键跨度</p>
        <div className="irr0-span-list">
          {round.text_reading.salient_spans.map((span, index) => (
            <article className="irr0-span-card" key={`${span.span}-${index}`}>
              <p className="irr0-span-text">{span.span}</p>
              <p>{span.literal_meaning}</p>
              {span.contextual_meaning && <p className="irr0-muted">{span.contextual_meaning}</p>}
              <small>目标深度 {span.depth} · {span.critical ? "关键" : "补充"}</small>
            </article>
          ))}
        </div>
      </section>
      <section className="irr0-reading-block">
        <p className="irr0-label">Gold 审美操作</p>
        {round.aesthetic_reading.map((item, index) => <p key={`${item.span}-${index}`}><strong>{item.span}</strong> · {item.operations.join("、")}</p>)}
      </section>
    </div>
  );
}

function EvidenceList({ evidence, title = "本轮新增史料" }: { evidence: IRREvidence[]; title?: string }) {
  if (evidence.length === 0) return <p className="irr0-muted">本轮没有新增史料。</p>;
  return (
    <section className="irr0-evidence-section">
      <p className="irr0-label">{title}</p>
      {evidence.map((item) => (
        <details className="irr0-evidence" key={item.evidence_ref}>
          <summary>{item.source_layer} · {item.source} · {item.evidence_ref}</summary>
          <blockquote>{item.quote}</blockquote>
          {item.quoted_source && <p className="irr0-muted">引自：{item.quoted_source}</p>}
          {item.locator && <small>{Object.entries(item.locator).map(([key, value]) => `${key}=${String(value)}`).join(" · ")}</small>}
        </details>
      ))}
    </section>
  );
}

function GainVector({
  vector,
  label,
  hidden,
}: {
  vector: IRRGainVector | undefined;
  label: string;
  hidden?: boolean;
}) {
  if (!vector || hidden) return null;
  const keys: Array<keyof IRRGainVector> = ["G_H", "G_L", "G_A", "G_C", "G_U", "G_D"];
  return (
    <div className="irr0-gain-vector">
      <p className="irr0-sublabel">{label}</p>
      <div className="irr0-gain-grid">
        {keys.map((key) => (
          <div className="irr0-gain-row" key={key}>
            <span>{key}</span>
            <span className="irr0-gain-track"><span style={{ width: `${Math.min(1, Math.max(0, vector[key])) * 100}%` }} /></span>
            <strong>{vector[key].toFixed(3)}</strong>
          </div>
        ))}
      </div>
      <p className="irr0-mrg">MRG = {vector.MRG.toFixed(3)} <small>实验诊断值</small></p>
    </div>
  );
}

function Delta({ output }: { output: IRRModelOutput }) {
  if (!output.reading_delta) return null;
  const delta = output.reading_delta;
  const groups: Array<[keyof IRRReadingDelta, IRRDeltaItem[]]> = [
    ["historical_changes", delta.historical_changes],
    ["newly_salient_spans", delta.newly_salient_spans],
    ["reinterpretations", delta.reinterpretations],
    ["newly_understood_omissions", delta.newly_understood_omissions],
    ["new_connections", delta.new_connections],
    ["resolved_questions", delta.resolved_questions],
    ["new_questions", delta.new_questions],
  ];
  const rows = groups.flatMap(([key, items]) => items.map((item) => ({ key, item })));
  return (
    <section className="irr0-delta">
      <p className="irr0-label">Reading delta</p>
      {rows.length === 0 && <p className="irr0-muted">本轮没有结构化变化。</p>}
      {rows.map(({ key, item }, index) => <p key={`${key}-${index}`}><strong>{key}</strong>：{item.text} <small>{evidenceLabel(item.evidence_refs)}</small></p>)}
    </section>
  );
}

function scoredIterativeRound(bundle: IRRReviewBundle, storyId: string, round: number): IRRScoredRound | undefined {
  const row = bundle.report.records.find((candidate) => candidate.story_id === storyId);
  if (!row) return undefined;
  const conditions = asRecord(row.conditions);
  const iterative = asRecord(conditions.iterative);
  const rounds = iterative.rounds;
  if (!Array.isArray(rounds)) return undefined;
  return rounds.find((candidate): candidate is IRRScoredRound => asRecord(candidate).round === round) as IRRScoredRound | undefined;
}

function IterativeRounds({
  bundle,
  storyId,
  record,
  blind,
}: {
  bundle: IRRReviewBundle;
  storyId: string;
  record: IRRModelRecord;
  blind: boolean;
}) {
  const rounds = record.rounds ?? [];
  return (
    <div className="irr0-rounds">
      {rounds.map((round, index) => {
        const scored = scoredIterativeRound(bundle, storyId, round.round);
        const modelGain = scored?.model_gain_vector;
        const goldGain = scored?.gold_gain_vector;
        return (
          <section className="irr0-round" key={round.round}>
            <div className="irr0-round-heading">
              <h3>Round {round.round}</h3>
              {index > 0 && <span>↓ 证据加入后重读</span>}
            </div>
            {round.round > 0 && <EvidenceList evidence={round.evidence_added} />}
            <div className="irr0-model-tag">模型理解</div>
            <ModelReading output={round.output} />
            <Delta output={round.output} />
            <div className="irr0-depth-line">
              Depth: {scored?.predicted_reading_depth ?? "—"}{scored ? ` → Gold ${scored.gold_reading_depth}` : ""}
            </div>
            <GainVector vector={modelGain} label="模型 gain" />
            <GainVector vector={goldGain} label="Gold gain" hidden={blind} />
          </section>
        );
      })}
    </div>
  );
}

function GoldRounds({ record }: { record: IRRGoldRecord }) {
  return (
    <div className="irr0-rounds irr0-gold-rounds">
      {record.rounds.map((round) => (
        <section className="irr0-round" key={round.round}>
          <div className="irr0-round-heading"><h3>Gold Round {round.round}</h3></div>
          <GoldReading round={round} />
        </section>
      ))}
    </div>
  );
}

function loadStoredReviews(): Record<string, ReviewChoice> {
  if (typeof window === "undefined") return {};
  try {
    const value = JSON.parse(window.localStorage.getItem(REVIEW_STORAGE_KEY) ?? "{}") as Record<string, ReviewChoice>;
    return value && typeof value === "object" ? value : {};
  } catch {
    return {};
  }
}

function downloadReviews(value: Record<string, ReviewChoice>): void {
  const blob = new Blob([JSON.stringify({ schema: "irr0.2-local-review", records: value }, null, 2)], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = "irr0-2-local-review.json";
  anchor.click();
  URL.revokeObjectURL(url);
}

function conditionLabel(mode: IRRReviewMode): string {
  return {
    text_only: "Text only",
    all_at_once: "All context",
    iterative: "Iterative",
    gold: "Gold",
  }[mode];
}

export function IRRReviewPage() {
  const [bundle, setBundle] = useState<IRRReviewBundle | null>(null);
  const [gold, setGold] = useState<IRRGoldRecord[] | null>(null);
  const [selectedStory, setSelectedStory] = useState(PILOT_STORIES[0]);
  const [mode, setMode] = useState<IRRReviewMode>("text_only");
  const [blind, setBlind] = useState(false);
  const [reviews, setReviews] = useState<Record<string, ReviewChoice>>(loadStoredReviews);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    void loadIRRReviewBundle()
      .then((next) => { if (active) { setBundle(next); setLoading(false); } })
      .catch((reason: unknown) => { if (active) { setError(reason instanceof Error ? reason.message : String(reason)); setLoading(false); } });
    return () => { active = false; };
  }, []);

  useEffect(() => {
    if (mode !== "gold" || gold) return;
    void loadIRRGold().then((next) => setGold(next.records)).catch(() => setGold([]));
  }, [gold, mode]);

  const selectedModelRecord = useMemo(() => {
    if (!bundle || mode === "gold") return undefined;
    const records = mode === "text_only" ? bundle.textOnly.records : mode === "all_at_once" ? bundle.allAtOnce.records : bundle.iterative.records;
    return recordFor(records, selectedStory);
  }, [bundle, mode, selectedStory]);
  const selectedGold = gold?.find((record) => record.story_id === selectedStory);
  const currentReviewKey = `${selectedStory}:${mode}`;

  function chooseReview(value: ReviewChoice): void {
    const next = { ...reviews, [currentReviewKey]: value };
    setReviews(next);
    window.localStorage.setItem(REVIEW_STORAGE_KEY, JSON.stringify(next));
  }

  if (loading) return <main className="page-shell loading-state"><p className="brand">世说Sketch</p><p>正在读取 IRR 重读实验……</p></main>;
  if (error || bundle === null) return <main className="page-shell"><section className="error-panel"><p className="brand">世说Sketch</p><h1>IRR 实验载入失败</h1><p>{error ?? "实验数据不可用。"}</p></section></main>;
  const storyInput = recordFor(bundle.textOnly.records, selectedStory)?.inference_input?.story;

  return (
    <main className="page-shell irr0-review-page">
      <header className="site-header irr0-review-header">
        <div>
          <p className="brand">世说Sketch · Research</p>
          <h1>IRR0.2 模型重读实验</h1>
          <p className="tagline">比较 Text only、All context 与 Iterative；模型输出不是史实。</p>
        </div>
        <a className="ux2-index-back" href={import.meta.env.BASE_URL}>返回阅读</a>
      </header>

      <section className="irr0-review-toolbar" aria-label="实验控制">
        <div className="irr0-story-selector">
          <p className="irr0-label">Stories</p>
          {PILOT_STORIES.map((storyId) => <button type="button" key={storyId} className={selectedStory === storyId ? "active" : ""} onClick={() => setSelectedStory(storyId)}>{storyId}</button>)}
        </div>
        <div className="irr0-condition-selector" role="tablist" aria-label="阅读条件">
          {(["text_only", "all_at_once", "iterative"] as IRRReviewMode[]).map((current) => <button type="button" role="tab" aria-selected={mode === current} key={current} className={mode === current ? "active" : ""} onClick={() => setMode(current)}>{conditionLabel(current)}</button>)}
          {!blind && <button type="button" role="tab" aria-selected={mode === "gold"} className={mode === "gold" ? "gold active" : "gold"} onClick={() => setMode("gold")}>Gold</button>}
        </div>
        <div className="irr0-blind-controls">
          <button type="button" onClick={() => { setBlind((value) => !value); if (!blind && mode === "gold") setMode("text_only"); }}>Blind review: {blind ? "ON" : "OFF"}</button>
          <button type="button" onClick={() => downloadReviews(reviews)}>导出本地判断</button>
        </div>
      </section>

      <article className="irr0-story-source">
        <p className="irr0-label">原文</p>
        <p className="irr0-story-id">{selectedStory}</p>
        {storyInput && <p className="irr0-story-text">{storyInput.text.simplified}</p>}
        {selectedModelRecord?.inference_input && selectedModelRecord.inference_input.evidence.length > 0 && mode === "all_at_once" && <EvidenceList evidence={selectedModelRecord.inference_input.evidence} title="全部可用史料" />}
      </article>

      <section className={mode === "gold" ? "irr0-condition-panel gold" : "irr0-condition-panel"}>
        <div className="irr0-condition-heading">
          <h2>{conditionLabel(mode)}</h2>
          {bundle.manifest.execution.real_model_run
            ? <span className="irr0-provider-badge">{bundle.manifest.execution.provider} · {bundle.manifest.execution.model}</span>
            : <span className="irr0-fixture-badge">fixture pipeline only</span>}
        </div>
        {mode === "iterative" && selectedModelRecord
          ? <IterativeRounds bundle={bundle} storyId={selectedStory} record={selectedModelRecord} blind={blind} />
          : mode === "gold"
            ? selectedGold ? <GoldRounds record={selectedGold} /> : <p className="irr0-muted">Gold 载入中……</p>
            : selectedModelRecord?.output
              ? <><ModelReading output={selectedModelRecord.output} /><p className="irr0-model-note">模型输入哈希：{selectedModelRecord.input_hash ?? "—"}</p></>
              : <p className="irr0-muted">该条件没有可用输出。</p>}
      </section>

      {!blind && <section className="irr0-analysis-panel">
        <p className="irr0-label">实验摘要</p>
        <p className="irr0-muted">{bundle.comparison.scientific_status === "fixture_pipeline_only" ? "当前为结构化 fixture，仅验证实验管线；没有真实模型凭据，因此不作性能结论。" : "当前结果来自已记录的模型运行。"}</p>
        <div className="irr0-summary-grid">
          {Object.entries(bundle.comparison.condition_summary).map(([condition, metrics]) => <div key={condition}><strong>{conditionLabel(condition as IRRReviewMode)}</strong><span>历史 {metrics.historical_score?.toFixed(3)} · 语言 {metrics.linguistic_salience_score?.toFixed(3)} · 审美 {metrics.aesthetic_operation_score?.toFixed(3)}</span></div>)}
        </div>
        <p className="irr0-muted">问题检查：context over text-only = {bundle.comparison.questions.context_improves_over_text_only ? "是" : "否"}；iterative over all-at-once = {bundle.comparison.questions.iterative_outperforms_all_at_once ? "是" : "否"}；hard-negative = {bundle.comparison.questions.hard_negative_recognized ? "识别" : "未识别"}；degradation = {bundle.comparison.questions.any_degradation ? "有" : "无"}。</p>
      </section>}

      {mode !== "gold" && <section className="irr0-local-review" aria-label="本地盲审判断">
        <p className="irr0-label">本地判断（不写入 Gold）</p>
        <div className="irr0-review-choice-list">
          {REVIEW_OPTIONS.map((option) => <button type="button" key={option} className={reviews[currentReviewKey] === option ? "active" : ""} onClick={() => chooseReview(option)}>{option}</button>)}
        </div>
        {reviews[currentReviewKey] && <p className="irr0-muted">已保存：{reviews[currentReviewKey]}</p>}
      </section>}
    </main>
  );
}
